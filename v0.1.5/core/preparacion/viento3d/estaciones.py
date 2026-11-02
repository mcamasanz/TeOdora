# -*- coding: utf-8 -*-
"""Estaciones de superficie de `meteo.viento3d`: medias horarias de medidas semihorarias y fichero
de estaciones (formato libre que lee `entradas.leer_surf`: cabecera con 8 valores «IBYR IBJUL IBHR
IEYR IEJUL IEHR IBTZ NSTA», sin segundos, y un registro por hora con la fecha de la hora FINAL).
Viene del proyecto de La Galera (2026-10-23). Necesita pandas."""
from pathlib import Path

import numpy as np
import pandas as pd

FALTA = 9999


def medias_horarias(df, conv="inicio"):
    """Medias horarias centradas en cada hora H (las dos semihorarias que la rodean; el viento se
    promedia como vector) de una tabla de medidas (time, ws, wd, t, rh, p). `conv`: «inicio» si la
    hora de cada medida es la del INICIO de su intervalo, «fin» si es la del final. Una hora con una
    sola medida (bordes, huecos) también vale. Devuelve (time, ws, wd, t, rh, p)."""
    d = df.copy()
    rad = np.radians(d["wd"])
    d["u"], d["v"] = -d["ws"] * np.sin(rad), -d["ws"] * np.cos(rad)
    desfase = pd.Timedelta(minutes=30) if conv == "inicio" else pd.Timedelta(0)
    d["hora"] = (d["time"] + desfase).dt.floor("h")
    g = d.groupby("hora").agg(ws=("ws", "mean"), u=("u", "mean"), v=("v", "mean"),
                              t=("t", "mean"), rh=("rh", "mean"), p=("p", "mean"),
                              n=("time", "size"))
    g = g[g["n"] >= 1]
    g["wd"] = (np.degrees(np.arctan2(-g["u"], -g["v"])) + 360.0) % 360.0
    return g.reset_index().rename(columns={"hora": "time"})[["time", "ws", "wd", "t", "rh", "p"]]


def escribir(ruta, estaciones_obs, horas, sfc,
             comentario="Observaciones de superficie (medias horarias centradas)"):
    """Fichero de estaciones. estaciones_obs: [(id, tabla horaria de `medias_horarias`)]; sfc:
    tabla (time, tcc 0-1) de la que salen nubosidad y techo, que no se miden. Devuelve el número de
    estaciones."""
    s = sfc.drop_duplicates("time", keep="last").set_index("time")
    tablas = [(i, df.set_index("time")) for i, df in estaciones_obs]
    h0, h1 = horas[0], horas[-1]
    L = [f"{'SURF.DAT':<16}{'2.1':<16}{'Hour Start and End Times with Seconds':<64}",
         "   1",
         comentario,
         "NONE",
         f"{h0.year} {h0.dayofyear} {h0.hour} {h1.year} {h1.dayofyear} {h1.hour} 0 {len(tablas)}"]
    L += [f"{i}" for i, _ in tablas]
    for h in horas:
        L.append(f"{h.year} {h.dayofyear} {h.hour}")
        cc = float(s.loc[h, "tcc"]) if h in s.index else np.nan
        icc = FALTA if np.isnan(cc) else int(round(min(max(cc, 0.0), 1.0) * 10))
        iceil = FALTA if icc == FALTA else (999 if icc < 5 else 30)
        for _, df in tablas:
            if h in df.index:
                r = df.loc[h]
                ws = r.ws if np.isfinite(r.ws) else FALTA
                wd = r.wd if np.isfinite(r.wd) and np.isfinite(r.ws) else FALTA
                tk = r.t + 273.15 if np.isfinite(r.t) else FALTA
                rh = int(round(r.rh)) if np.isfinite(r.rh) else FALTA
                pr = r.p if np.isfinite(r.p) else FALTA
            else:
                ws = wd = tk = pr = FALTA
                rh = FALTA
            L.append(f"{ws:.2f} {wd:.1f} {iceil} {icc} {tk:.2f} {rh} {pr:.1f} 0")
    Path(ruta).write_text("\n".join(L) + "\n")
    return len(tablas)
