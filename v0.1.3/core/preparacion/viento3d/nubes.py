# -*- coding: utf-8 -*-
"""Fichero de nubes de `meteo.viento3d` (lectura libre: «"CLOUDFRA" AAAAJJJHH» y NX·NY fracciones
de 0 a 1, fila 1 = sur). Viene del proyecto de La Galera (2026-10-23). Necesita pandas."""
from pathlib import Path

import numpy as np


def escribir(ruta, sfc, horas, nx, ny):
    """La MISMA nubosidad en todas las celdas: la de la tabla sfc (time, tcc 0-1) en cada hora."""
    s = sfc.drop_duplicates("time", keep="last").set_index("time")
    L = []
    for ts in horas:
        cc = min(max(float(s.loc[ts, "tcc"]), 0.0), 1.0)
        ndathr = ts.year * 100000 + ts.dayofyear * 100 + ts.hour
        L.append(f'"CLOUDFRA" {ndathr} ' + " ".join([f"{cc:.3f}"] * (nx * ny)))
    Path(ruta).write_text("\n".join(L) + "\n")


def escribir_zonas(ruta, df, malla, xs, ys, horas):
    """Cada celda con la nubosidad (cloud_cover, %) de la columna más cercana de una malla de
    columnas (xs, ys en m; df con filas time, i, j desde 1). malla: {"nx", "ny", "celda_m", "ext"}."""
    ny, nx = malla["ny"], malla["nx"]
    dg = malla["celda_m"]
    xc = malla["ext"][0] + (np.arange(nx) + 0.5) * dg
    yc = malla["ext"][2] + (np.arange(ny) + 0.5) * dg
    ii = np.abs(xc[None, :] - xs[:, None]).argmin(0) + 1             # (nx,) columna i
    jj = np.abs(yc[None, :] - ys[:, None]).argmin(0) + 1             # (ny,) columna j
    d = df.set_index(["time", "i", "j"])["cloud_cover"].sort_index()
    L = []
    for ts in horas:
        c = d.xs(ts, level="time")
        tabla = {k: min(max(v / 100.0, 0.0), 1.0) for k, v in c.items()}
        vals = [f"{tabla[(ii[x], jj[y])]:.3f}" for y in range(ny) for x in range(nx)]
        L.append(f'"CLOUDFRA" {ts.year * 100000 + ts.dayofyear * 100 + ts.hour} ' + " ".join(vals))
    Path(ruta).write_text("\n".join(L) + "\n")
