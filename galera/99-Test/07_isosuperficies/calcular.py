# -*- coding: utf-8 -*-
"""Una corrida del plan Base sobre una malla de ±3 km cada 100 m, a las alturas que se pidan.

    python calcular.py --nombre suelo --alturas 0
    python calcular.py --nombre vol --alturas 0,2,5,10,20,35,50,75,100,150,200,300,400,600,800 --ini "2026-10-20 06:00" --fin "2026-10-21 13:00"

Por defecto arranca a las 06 UTC del día anterior, como gui/tareas/respuestas_dia.py. La salida (fines, x, y, alturas,
C[periodo, altura, j, i] en ou_E/m³) va a %TEMP%/ence_galera/99-Test/07_isosuperficies/<nombre>.npz, y sus tiempos a
resultados_<nombre>.json en esta carpeta.
"""
import argparse
import json
import sys

import comun as K
import numpy as np
import pandas as pd

sys.stdout.reconfigure(encoding="utf-8")
a = argparse.ArgumentParser()
a.add_argument("--nombre", required=True)
a.add_argument("--alturas", default="0")
a.add_argument("--ini", default="2026-10-20 06:00")
a.add_argument("--fin", default="2026-10-21 23:00")
a.add_argument("--semilado", type=float, default=3000.0)
a.add_argument("--paso", type=float, default=100.0)
a.add_argument("--procesos", type=int, default=4)
A = a.parse_args()

alturas = [float(x) for x in A.alturas.split(",")]
ini, fin = pd.Timestamp(A.ini), pd.Timestamp(A.fin)
nhoras = int((fin - ini) / pd.Timedelta(hours=1)) + 1                  # el 1.er periodo lleva fin = hora de inicio
xs, ys = K.rejilla_100m(A.semilado, A.paso)
recs = [(x, y, K.cota(x, y), h) for h in alturas for y in ys for x in xs]
salen, fuera, total = K.fuentes_plan_base()
print(f"{len(recs)} receptores ({len(xs)} × {len(ys)} × {len(alturas)}) · {nhoras} periodos · emisión de referencia "
      f"{total:,.0f} ou_E/s · {sum(map(len, salen.values()))} fuentes · fuera: {fuera}", flush=True)
carpeta = K.TRABAJO / ("caso_" + A.nombre)
K.limpia(carpeta)
fines, C, med = K.correr(carpeta, ini, nhoras, salen, recs, procesos=A.procesos, nombre=A.nombre)
C = C.reshape(len(fines), len(alturas), len(ys), len(xs))
print(f"Motor: {med['segundos']:.0f} s · memoria máxima por proceso {max(med['memoria_MB'])} MB · conc {med['fichero_conc_MB']} MB", flush=True)
print("Máximo por altura y periodo final:", np.round(C[-1].max(axis=(1, 2)), 3).tolist(), flush=True)
np.savez_compressed(K.TRABAJO / (A.nombre + ".npz"), C=C, x=xs, y=ys, alturas=np.array(alturas),
                    fines=fines.strftime("%Y-%m-%d %H:%M").to_numpy().astype("U16"))
us = med["segundos"] * A.procesos / (len(recs) * nhoras) * 1e6
res = dict(med, receptores=len(recs), periodos=nhoras, alturas=alturas, ini=A.ini, fin=A.fin, procesos=A.procesos,
           fuentes=sum(map(len, salen.values())), us_por_receptor_periodo_y_proceso=round(us, 1),
           npz_MB=round((K.TRABAJO / (A.nombre + ".npz")).stat().st_size / 1e6, 2))
(K.AQUI / f"resultados_{A.nombre}.json").write_text(json.dumps(res, ensure_ascii=False, indent=1), encoding="utf-8")
print(res, flush=True)
K.shutil.rmtree(carpeta, ignore_errors=True)
