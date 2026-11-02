# -*- coding: utf-8 -*-
"""Validación 2: ¿la concentración EN ALTURA conserva la masa?

Un foco (el biofiltro F03, 1 g/s constante) y una caja de ±L alrededor. Lo que sale por las cuatro paredes verticales
tiene que ser, de media, lo que se emite:   Φ = Σ_paredes ∬ C(z, s) · u_n(z, s) dz ds  ≈  Q.
C sale del motor en receptores a 30 alturas en las paredes; u_n, de los vientos por capas del fichero de viento (en el
periodo con fin T, el registro T, como hace el motor). La tapa de la caja queda por encima de lo que llega el penacho.

No es exacto por construcción y conviene saber por qué: el motor mueve cada puff entero con la media del viento en
[H − σz, H + σz], mientras que aquí cada altura lleva su propio viento; C y u son medias de la hora (se ignora su
covarianza dentro de la hora); y la masa guardada dentro de la caja cambia de una hora a otra.
"""
import json
import sys

import comun as K
import numpy as np
import pandas as pd
from teodors.meteo.viento3d import almacen

sys.stdout.reconfigure(encoding="utf-8")
L, DS = 1500.0, 50.0
ALTURAS = [0, 2, 5, 10, 15, 20, 30, 40, 50, 65, 80, 100, 125, 150, 175, 200, 250, 300, 350, 400, 500, 600, 700, 800,
           900, 1000, 1200, 1400, 1600, 2000]
foco = next(f for f in K.focos() if f["id"] == "F03")
xc, yc = np.mean(foco["ubicacion"]["poligono"], axis=0)
m, d = K.fuente(foco, 1.0, None)
salen = {"superficie": [], "punto": [], "volumen": []}
salen[m].append(d)
s = -L + (np.arange(int(2 * L / DS)) + 0.5) * DS
caras = {"este": (xc + L + 0 * s, yc + s, (1.0, 0.0)), "oeste": (xc - L + 0 * s, yc + s, (-1.0, 0.0)),
         "norte": (xc + s, yc + L + 0 * s, (0.0, 1.0)), "sur": (xc + s, yc - L + 0 * s, (0.0, -1.0))}
X = np.concatenate([c[0] for c in caras.values()])
Y = np.concatenate([c[1] for c in caras.values()])
NX_ = np.concatenate([np.full(len(s), c[2][0]) for c in caras.values()])
NY_ = np.concatenate([np.full(len(s), c[2][1]) for c in caras.values()])
recs = [(float(x), float(y), K.cota(float(x), float(y)), float(h)) for h in ALTURAS for x, y in zip(X, Y)]
ini = pd.Timestamp("2026-10-20 06:00")
carpeta = K.TRABAJO / "caso_balance"
K.limpia(carpeta)
fines, C, med = K.correr(carpeta, ini, 42, salen, recs, procesos=4, nombre="balance")
print(f"Motor: {med['segundos']:.0f} s, {len(recs)} receptores, máx. {C.max():.3g} g/m³", flush=True)
C = C.reshape(len(fines), len(ALTURAS), len(X))

# ── viento en los puntos de las paredes ─────────────────────────────────────────────────
zf = np.array(K.config.VIENTO3D_ZFACE, float)
zc = 0.5 * (zf[:-1] + zf[1:])
fz, _ = almacen.leer_campo(K.CMZ, "U-LEV  1")


def fecha(f):
    f = int(f)
    return pd.Timestamp(f // 100000, 1, 1) + pd.Timedelta(days=(f // 100) % 1000 - 1) + pd.Timedelta(hours=f % 100)


T = [fecha(f) for f in fz]
U = np.stack([almacen.leer_campo(K.CMZ, "U-LEV %2d" % (k + 1))[1] for k in range(12)])     # [nivel, hora, j, i]
V = np.stack([almacen.leer_campo(K.CMZ, "V-LEV %2d" % (k + 1))[1] for k in range(12)])
z0 = almacen.leer_campo(K.CMZ, "Z0      ")[1]
z0 = z0[0] if z0.ndim == 3 else z0
ext, dg = K.INFO["ext"], K.INFO["celda_m"]
gi = (X - (ext[0] + dg / 2)) / dg
gj = (Y - (ext[2] + dg / 2)) / dg
i0, j0 = np.floor(gi).astype(int), np.floor(gj).astype(int)
fx, fy = gi - i0, gj - j0


def en_puntos(A):
    return ((A[..., j0, i0] * (1 - fx) + A[..., j0, i0 + 1] * fx) * (1 - fy)
            + (A[..., j0 + 1, i0] * (1 - fx) + A[..., j0 + 1, i0 + 1] * fx) * fy)


z0p = np.maximum(en_puntos(z0), 0.01)
ZA = np.array(ALTURAS, float)
_, IPGT = almacen.leer_campo(K.CMZ, "IPGT    ")
filas = []
for t, fin in enumerate(fines):
    k = T.index(fin)
    up, vp = en_puntos(U[:, k]), en_puntos(V[:, k])                    # [nivel, punto]
    un_c = up * NX_ + vp * NY_
    un = np.zeros((len(ALTURAS), len(X)))
    for p in range(len(X)):
        un[:, p] = np.interp(ALTURAS, zc, un_c[:, p])
    # por debajo del centro de la 1.ª capa, perfil logarítmico con la rugosidad de la celda
    for a, h in enumerate(ALTURAS):
        if h < zc[0]:
            un[a] = un_c[0] * np.log(np.maximum(h, z0p) / z0p) / np.log(zc[0] / z0p)
    F = C[t] * un
    por_columna = np.trapezoid(F, ALTURAS, axis=0)
    masa_columna = np.trapezoid(C[t], ALTURAS, axis=0)
    # σz de cada columna (2.º momento de una semigaussiana) y el viento con que el motor movería ese puff: media por
    # espesor de las capas en [0, σz], con H ≈ 0 frente a σz
    m2 = np.trapezoid(C[t] * ZA[:, None] ** 2, ALTURAS, axis=0)
    sz = np.sqrt(m2 / np.maximum(masa_columna, 1e-30))
    con = masa_columna > 1e-12
    flujo_puff = 0.0
    for p in np.flatnonzero(con):
        w = np.maximum(np.minimum(zf[1:], sz[p]) - zf[:-1], 0.0)
        flujo_puff += masa_columna[p] * (w * un_c[:, p]).sum() / w.sum() * DS
    p = int(np.argmax(masa_columna))
    filas.append({"fin": str(fin), "flujo": float(por_columna.sum() * DS), "flujo_viento_del_puff": float(flujo_puff),
                  "sale": float(np.maximum(por_columna, 0).sum() * DS), "entra": float(np.minimum(por_columna, 0).sum() * DS),
                  "columna_max": float(masa_columna.max()), "sigma_z_m": float(sz[p]),
                  "clase": int(IPGT[k, int((Y[p] - ext[2]) / dg), int((X[p] - ext[0]) / dg)]),
                  "clase_foco": int(IPGT[k, int((yc - ext[2]) / dg), int((xc - ext[0]) / dg)]),
                  "dist_m": float(np.hypot(X[p] - xc, Y[p] - yc)),
                  "tope": float(C[t, -1].max() / max(C[t].max(), 1e-30))})
df = pd.DataFrame(filas)
ult = df.iloc[-24:]
res = {"caja_m": 2 * L, "paso_m": DS, "alturas": len(ALTURAS), "motor": med, "Q_g_s": 1.0,
       "flujo_medio_24h": float(ult.flujo.mean()), "flujo_min_hora": float(ult.flujo.min()),
       "flujo_max_hora": float(ult.flujo.max()), "flujo_mediana_hora": float(ult.flujo.median()),
       "flujo_viento_del_puff_medio_24h": float(ult.flujo_viento_del_puff.mean()),
       "flujo_viento_del_puff_min_hora": float(ult.flujo_viento_del_puff.min()),
       "flujo_viento_del_puff_max_hora": float(ult.flujo_viento_del_puff.max()),
       "horas": [{k: (round(v, 4) if isinstance(v, float) else v) for k, v in f.items()} for f in filas[-24:]]}
print(df.iloc[-24:][["fin", "flujo", "flujo_viento_del_puff", "sigma_z_m", "clase", "clase_foco", "dist_m"]].round(3).to_string(), flush=True)
print(f"Φ/Q en las últimas 24 h: media {res['flujo_medio_24h']:.3f}, mediana {res['flujo_mediana_hora']:.3f}, de "
      f"{res['flujo_min_hora']:.3f} a {res['flujo_max_hora']:.3f}", flush=True)
print(f"Con el viento del puff: media {res['flujo_viento_del_puff_medio_24h']:.3f}, de "
      f"{res['flujo_viento_del_puff_min_hora']:.3f} a {res['flujo_viento_del_puff_max_hora']:.3f}", flush=True)
(K.AQUI / "resultados_balance.json").write_text(json.dumps(res, ensure_ascii=False, indent=1), encoding="utf-8")
K.shutil.rmtree(carpeta, ignore_errors=True)
