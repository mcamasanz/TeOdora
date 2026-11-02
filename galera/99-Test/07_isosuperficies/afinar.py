# -*- coding: utf-8 -*-
"""Segunda pasada: una hora con más detalle horizontal, solo donde hay penacho.

Con 100 m, un penacho estrecho que cruza la malla en diagonal sale a dientes de sierra: los nudos lo cogen a ratos. Para
no calcular 871 815 receptores (241² × 15), la corrida «vol» dice dónde hay penacho esa hora (≥ `umbral` a cualquier
altura, más un margen y un cuadrado alrededor de la planta) y solo ahí se ponen receptores cada `paso` metros. El motor
arranca `previas` horas antes de esa hora: lo emitido antes ya ha salido de los ±3 km, y se comprueba con «vol».

    python afinar.py --horas 7,15,23,13   →  %TEMP%/…/07_isosuperficies/fino_HH.npz + resultados_fino.json
"""
import argparse
import json
import sys

import comun as K
import numpy as np
import pandas as pd
from scipy.ndimage import binary_dilation

sys.stdout.reconfigure(encoding="utf-8")
a = argparse.ArgumentParser()
a.add_argument("--horas", default="7,15,23,13")
a.add_argument("--paso", type=float, default=25.0)
a.add_argument("--umbral", type=float, default=0.3)
a.add_argument("--margen", type=float, default=200.0)
a.add_argument("--previas", type=int, default=2)
a.add_argument("--procesos", type=int, default=4)
A = a.parse_args()
d = np.load(K.TRABAJO / "vol.npz")
Cg, xg, yg, Z, fines = d["C"], d["x"], d["y"], d["alturas"], [str(f) for f in d["fines"]]
xs, ys = K.rejilla_100m(3000.0, A.paso)
factor = int(round((xg[1] - xg[0]) / A.paso))
salen, _, _ = K.fuentes_plan_base()
sal = []
for H in (int(h) for h in A.horas.split(",")):
    t = fines.index(f"2026-10-21 {H:02d}:00")
    grueso = (Cg[t] >= A.umbral).any(axis=0)
    grueso = binary_dilation(grueso, iterations=int(np.ceil(A.margen / (xg[1] - xg[0]))))
    # a cada nudo fino le toca el nudo grueso más cercano
    mascara = grueso[np.clip(((np.arange(len(ys)) + factor // 2) // factor), 0, len(yg) - 1)[:, None],
                     np.clip(((np.arange(len(xs)) + factor // 2) // factor), 0, len(xg) - 1)[None, :]]
    X, Y = np.meshgrid(xs, ys)
    mascara |= (np.abs(X - K.CENTRO[0]) <= 400) & (np.abs(Y - K.CENTRO[1]) <= 400)
    jj, ii = np.nonzero(mascara)
    recs = [(float(xs[i]), float(ys[j]), K.cota(float(xs[i]), float(ys[j])), float(h)) for h in Z for j, i in zip(jj, ii)]
    fin = pd.Timestamp(f"2026-10-21 {H:02d}:00")
    ini = fin - pd.Timedelta(hours=A.previas)
    carpeta = K.TRABAJO / f"caso_fino_{H:02d}"
    K.limpia(carpeta)
    print(f"{H:02d} UTC: {len(jj)} nudos × {len(Z)} alturas = {len(recs)} receptores, {A.previas + 1} periodos", flush=True)
    finz, C, med = K.correr(carpeta, ini, A.previas + 1, salen, recs, procesos=A.procesos, nombre="fino")
    if str(finz[-1])[:16] != str(fin)[:16]:
        raise RuntimeError(f"último periodo {finz[-1]}, no {fin}")
    v = C[-1].reshape(len(Z), len(jj))
    campo = np.zeros((len(Z), len(ys), len(xs)), np.float32)
    campo[:, jj, ii] = v
    np.savez_compressed(K.TRABAJO / f"fino_{H:02d}.npz", C=campo, x=xs, y=ys, alturas=Z)
    # ── comprobaciones: nudos comunes con «vol», y que el penacho no toca el borde de la máscara ──
    com = campo[:, ::factor, ::factor]
    if com.shape != Cg[t].shape:
        raise RuntimeError(f"nudos comunes {com.shape} frente a {Cg[t].shape}")
    hay = mascara[::factor, ::factor]
    ref, val = Cg[t][:, hay], com[:, hay]
    grande = ref > 0.1
    borde = mascara & binary_dilation(~mascara, iterations=1)
    fila = dict(fin_utc=H, nudos=len(jj), receptores=len(recs), periodos=A.previas + 1, **med,
                us_por_receptor_periodo_y_proceso=round(med["segundos"] * A.procesos / (len(recs) * (A.previas + 1)) * 1e6, 1),
                dif_max_nudos_comunes=float(np.abs(ref - val).max()), dif_rel_max_c_mayor_0_1=float((np.abs(ref - val)[grande] / ref[grande]).max()),
                fuera_de_mascara_max_grueso=float(Cg[t][:, ~hay].max()) if (~hay).any() else 0.0,
                max_en_borde_mascara=float(campo[:, borde].max()) if borde.any() else 0.0, maximo=float(campo.max()),
                npz_MB=round((K.TRABAJO / f"fino_{H:02d}.npz").stat().st_size / 1e6, 2))
    print(fila, flush=True)
    sal.append(fila)
    K.shutil.rmtree(carpeta, ignore_errors=True)
(K.AQUI / "resultados_fino.json").write_text(json.dumps(sal, ensure_ascii=False, indent=1), encoding="utf-8")
