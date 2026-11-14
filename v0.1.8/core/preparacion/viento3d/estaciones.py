# -*- coding: utf-8 -*-
"""Estaciones de superficie de `meteo.viento3d`: medias horarias de medidas semihorarias y fichero
de estaciones (formato libre que lee `entradas.leer_surf`: cabecera con 8 valores «IBYR IBJUL IBHR
IEYR IEJUL IEHR IBTZ NSTA», sin segundos, y un registro por hora con la fecha de la hora FINAL).
Viene del proyecto de La Galera (2026-10-23). Necesita pandas.

Hora sin temperatura en ninguna estación (la red entera caída: en Meteocat, 1 a 19 h seguidas en
2024-2025, comprobado en su portal el 2026-11-06): el motor no puede seguir sin temperatura ni
presión, así que la temperatura, la humedad y la presión que no tenga ninguna estación salen de la
superficie del modelo (`sfc`: t2m y d2m en °C, sp en hPa), la misma en todas. El viento sigue
ausente: en esa hora manda el del modelo. Sin esas columnas en `sfc`, se escribe ausente como antes."""
from pathlib import Path

import numpy as np
import pandas as pd

from teodors.comun import registro

log = registro.get("viento3d")

FALTA = 9999


def _hr(t_c, td_c):
    """Humedad relativa (%) desde la temperatura y el punto de rocío (°C), con la presión de vapor de
    `pronostico._q_gkg`."""
    def e(x):
        return 6.112 * np.exp(17.67 * x / (x + 243.5))
    return float(np.clip(100.0 * e(td_c) / e(t_c), 0.0, 100.0))


def _del_modelo(s, h):
    """(tk, rh, pr) de la superficie del modelo en la hora h, con FALTA donde no hay dato."""
    def v(col):
        x = float(s.loc[h, col]) if col in s.columns and h in s.index else np.nan
        return x if np.isfinite(x) else np.nan
    t, td, p = v("t2m"), v("d2m"), v("sp")
    tk = t + 273.15 if np.isfinite(t) else FALTA
    rh = int(round(_hr(t, td))) if np.isfinite(t) and np.isfinite(td) else FALTA
    pr = p if np.isfinite(p) else FALTA
    return tk, rh, pr


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
    tabla (time, tcc 0-1) de la que salen nubosidad y techo, que no se miden; si trae t2m, d2m y sp,
    también la temperatura, la humedad y la presión de las horas sin temperatura en ninguna estación
    (ver arriba). Devuelve el número de estaciones."""
    s = sfc.drop_duplicates("time", keep="last").set_index("time")
    tablas = [(i, df.set_index("time")) for i, df in estaciones_obs]
    h0, h1 = horas[0], horas[-1]
    L = [f"{'SURF.DAT':<16}{'2.1':<16}{'Hour Start and End Times with Seconds':<64}",
         "   1",
         comentario,
         "NONE",
         f"{h0.year} {h0.dayofyear} {h0.hour} {h1.year} {h1.dayofyear} {h1.hour} 0 {len(tablas)}"]
    L += [f"{i}" for i, _ in tablas]
    del_modelo = []
    for h in horas:
        L.append(f"{h.year} {h.dayofyear} {h.hour}")
        cc = float(s.loc[h, "tcc"]) if h in s.index else np.nan
        icc = FALTA if np.isnan(cc) else int(round(min(max(cc, 0.0), 1.0) * 10))
        iceil = FALTA if icc == FALTA else (999 if icc < 5 else 30)
        filas = []
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
            filas.append([ws, wd, tk, rh, pr])
        if filas and all(f[2] == FALTA for f in filas):
            # red caída: lo que no tenga ninguna estación, del modelo (la misma en todas)
            m = _del_modelo(s, h)
            if m[0] != FALTA:
                del_modelo.append(h)
                for c, x in zip((2, 3, 4), m):
                    if all(f[c] == FALTA for f in filas):
                        for f in filas:
                            f[c] = x
        for ws, wd, tk, rh, pr in filas:
            L.append(f"{ws:.2f} {wd:.1f} {iceil} {icc} {tk:.2f} {rh} {pr:.1f} 0")
    Path(ruta).write_text("\n".join(L) + "\n")
    if del_modelo:
        log.warning(f"{len(del_modelo)} h sin temperatura en ninguna estación: temperatura, humedad y presión "
                    f"del modelo en {_tramos(del_modelo)}")
    return len(tablas)


def _tramos(horas):
    """«2024-06-03 08h → 2024-06-04 02h (19 h), 2024-06-10 05h» de una lista ordenada de horas."""
    tramos = []
    for h in horas:
        if tramos and h - tramos[-1][1] == pd.Timedelta(hours=1):
            tramos[-1][1] = h
        else:
            tramos.append([h, h])
    return ", ".join(f"{a:%Y-%m-%d %H}h" if a == b else
                     f"{a:%Y-%m-%d %H}h → {b:%Y-%m-%d %H}h ({int((b - a) / pd.Timedelta(hours=1)) + 1} h)"
                     for a, b in tramos)
