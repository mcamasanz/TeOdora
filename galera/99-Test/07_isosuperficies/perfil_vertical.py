# -*- coding: utf-8 -*-
"""Validación 2, segunda parte: forma del perfil vertical en la corrida «vol» del plan Base.

Para varias horas, en la columna con más concentración a 1-2,5 km de la planta: C(z) / C(0), y el ajuste a la gaussiana
de un foco a nivel de suelo con su reflexión, C(z) = C(0) · exp(−z² / 2σz²). Son varios focos a 1,5-14 m de altura: a
esa distancia, la altura de emisión apenas cuenta frente a σz. Si la tapa de la capa de mezcla entra en el perfil, se dice.
"""
import json
import sys

import comun as K
import numpy as np
from teodors.meteo.viento3d import almacen
from scipy.optimize import curve_fit

sys.stdout.reconfigure(encoding="utf-8")
d = np.load(K.TRABAJO / "vol.npz")
C, xs, ys, Z, fines = d["C"], d["x"], d["y"], d["alturas"], [str(f) for f in d["fines"]]
fz, ZI = almacen.leer_campo(K.CMZ, "ZI      ")
ext, dg = K.INFO["ext"], K.INFO["celda_m"]
X, Y = np.meshgrid(xs, ys)
dist = np.hypot(X - K.CENTRO[0], Y - K.CENTRO[1])
anillo = (dist >= 1000) & (dist <= 2500)
sal = []
for fin in ("2026-10-21 02:00", "2026-10-21 07:00", "2026-10-21 13:00", "2026-10-21 15:00", "2026-10-21 23:00"):
    t = fines.index(fin)
    suelo = np.where(anillo, C[t, 0], 0.0)
    j, i = np.unravel_index(np.argmax(suelo), suelo.shape)
    p = C[t, :, j, i].astype(float)
    r = p / p[0]
    H = int(fin[11:13])
    k = 24 + H
    zi = float(ZI[k, int((Y[j, i] - ext[2]) / dg), int((X[j, i] - ext[0]) / dg)])
    bajo = Z <= zi

    def g(z, s):
        return np.exp(-z * z / (2 * s * s))
    s, _ = curve_fit(g, Z[bajo], r[bajo], p0=[50.0], bounds=(1.0, 5000.0))
    ajuste = g(Z, s[0])
    r2 = 1 - ((r[bajo] - ajuste[bajo]) ** 2).sum() / ((r[bajo] - r[bajo].mean()) ** 2).sum()
    fila = {"fin": fin, "dist_m": round(float(dist[j, i])), "C0": round(float(p[0]), 3), "ZI_m": round(zi), "sigma_z_m": round(float(s[0]), 1),
            "r2": round(float(r2), 4), "C_z_entre_C0": {str(int(h)): round(float(v), 3) for h, v in zip(Z, r)},
            "tope_800m_entre_max": round(float(C[t, -1].max() / max(C[t].max(), 1e-30)), 4),
            "altura_max_con_1ou": float(Z[(C[t] >= 1).any(axis=(1, 2))].max()) if (C[t] >= 1).any() else None}
    sal.append(fila)
    print(fila, flush=True)
(K.AQUI / "resultados_perfil.json").write_text(json.dumps(sal, ensure_ascii=False, indent=1), encoding="utf-8")
