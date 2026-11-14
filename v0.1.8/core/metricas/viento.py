# -*- coding: utf-8 -*-
"""Validación de la meteorología modelizada (ERA5 u otro modelo) contra las estaciones.

Métricas y umbrales habituales de validación de modelos meteorológicos para dispersión
(Emery, Tai y Yarwood, 2001):
  viento   RMSE ≤ 2 m/s · sesgo ≤ ±0,5 m/s · índice de concordancia (IOA) ≥ 0,6
  dirección error bruto ≤ 30° · sesgo ≤ ±10°   (solo horas con viento ≥ 1 m/s en ambos)
  temperatura error bruto ≤ 2 K · sesgo ≤ ±0,5 K
Además, la frecuencia de CALMAS (< 0,5 m/s), clave en olores: teOdors `penacho` las descarta y una
fuente de 31 km como ERA5 las subestima.

Comparación HORARIA: ERA5 da u10, v10 y t2m instantáneos en la hora H; de la estación se
toman las dos medias semihorarias que rodean H (viento promediado como vector).
"""
import json
import math

import numpy as np
import pandas as pd

from teodors import planta as config
from teodors.comun import registro
from teodors.fuentes import era5 as meteo
from teodors.fuentes import meteocat as estaciones
from teodors.planta import geo

log = registro.get("validacion")

UMBRALES = {"ws_rmse": 2.0, "ws_sesgo": 0.5, "ws_ioa": 0.6,
            "wd_error": 30.0, "wd_sesgo": 10.0, "t_error": 2.0, "t_sesgo": 0.5}
CALMA = 0.5                 # m/s
VIENTO_MIN_DIR = 1.0        # m/s: por debajo la dirección no está bien definida
GRADIENTE_T = -0.0065       # K/m (atmósfera estándar) para corregir la diferencia de cota
SECTORES = 16


def dir_validacion():
    return config.DIR_METEO / "validacion"


# ── ERA5 ─────────────────────────────────────────────────────────────────────────────────
def era5_horario(lat, lon, anios=None):
    """Serie ERA5 de superficie en unidades útiles (de la serie temporal ya descargada)."""
    anios = config.REANALISIS_ANIOS if anios is None else anios
    s = meteo.serie_sfc(lat, lon, anios).copy()
    s["ws"] = np.hypot(s.u10, s.v10)
    s["wd"] = (270.0 - np.degrees(np.arctan2(s.v10, s.u10))) % 360.0
    s["t"] = s.t2m - 273.15
    s["rad"] = s.ssrd / 3600.0                    # media de la hora que ACABA en H (W/m²)
    return s[["time", "ws", "wd", "t", "rad"]]


# ── hora de las estaciones ───────────────────────────────────────────────────────────────
def centroide_radiacion(df):
    """Hora media (UTC, en horas) del ciclo diario de radiación según las etiquetas de la
    estación. Si las medias de 30 min se etiquetan con su INICIO sale ≈ 15 min antes del mediodía
    solar; con su FINAL, ≈ 15 min después; en hora local, 1-2 h más."""
    r = df.dropna(subset=["rad"])
    r = r[r.rad > 0]
    h = r.time.dt.hour + r.time.dt.minute / 60.0
    perfil = r.groupby(h)["rad"].mean()
    return float((perfil.index * perfil).sum() / perfil.sum())


def mediodia_solar(lon):
    """Hora UTC del mediodía solar medio en esa longitud (a lo largo del año, la ecuación del tiempo se compensa)."""
    return 12.0 - lon / 15.0


def convencion(df, mediodia_h=None):
    """¿La hora de una estación es la del INICIO o la del FINAL de su media? Se mira a qué lado del mediodía cae el centroide de la
    radiación, en una ventana de ±0,6 h. `mediodia_h`, hora UTC: por defecto, `estaciones.mediodia_utc_h` de la planta y, si no lo
    tiene, el mediodía solar en su longitud. ⚠️ El centroide no es circular: no vale donde el día cruza las 00 UTC. Con pocos días
    tampoco es fiable: si se sabe la convención, mejor darla."""
    if mediodia_h is None:
        mediodia_h = config.bloque("estaciones").get("mediodia_utc_h")
    if mediodia_h is None:
        mediodia_h = mediodia_solar(config.cargar_emplazamiento()["lon"])
    c = centroide_radiacion(df)
    if mediodia_h - 0.6 <= c < mediodia_h:
        return "inicio", c
    if mediodia_h <= c < mediodia_h + 0.6:
        return "fin", c
    raise ValueError(f"Centroide de radiación a las {c:.2f} h: la hora de la estación no "
                     f"parece UTC; revisar antes de comparar.")


def a_horario(df, conv):
    """Medias horarias centradas en cada hora H (las dos medias semihorarias que la rodean).
    'inicio': etiquetas H-30 y H; 'fin': H y H+30. ⚠️ Solo valen las horas con las DOS medias:
    `preparacion.viento3d.estaciones.medias_horarias` se conforma con una. No fundirlas sin medir."""
    d = df.copy()
    rad = np.radians(d["wd"])
    d["u"], d["v"] = -d["ws"] * np.sin(rad), -d["ws"] * np.cos(rad)
    desfase = pd.Timedelta(minutes=30) if conv == "inicio" else pd.Timedelta(0)
    d["hora"] = (d["time"] + desfase).dt.floor("h")
    g = d.groupby("hora").agg(ws=("ws", "mean"), u=("u", "mean"), v=("v", "mean"),
                              t=("t", "mean"), n=("time", "size"))
    g = g[g["n"] == 2]                             # solo horas con las dos medias
    g["wd"] = geo.direccion(g["u"], g["v"])
    return g.reset_index().rename(columns={"hora": "time"})[["time", "ws", "wd", "t"]]


# ── métricas ─────────────────────────────────────────────────────────────────────────────
def ioa(mod, obs):
    """Índice de concordancia de Willmott (1 = perfecto)."""
    om = obs.mean()
    den = ((np.abs(mod - om) + np.abs(obs - om)) ** 2).sum()
    return float(1 - ((mod - obs) ** 2).sum() / den) if den > 0 else float("nan")


def rosa(ws, wd, sectores=SECTORES):
    """Frecuencia (%) por sector de las horas NO calmas y % de calmas."""
    ancho = 360.0 / sectores
    no_calma = ws >= CALMA
    idx = (((wd[no_calma] + ancho / 2) % 360) // ancho).astype(int)
    f = np.bincount(idx, minlength=sectores) / len(ws) * 100
    return f, float((~no_calma).mean() * 100)


def metricas(est_h, era, altitud_est, cota_era5, altura_viento):
    m = est_h.merge(era, on="time", suffixes=("_obs", "_mod")).dropna()
    obs_ws = m.ws_obs * (estaciones.a_10m(1.0, altura_viento) if altura_viento else 1.0)
    mod_ws = m.ws_mod
    con_dir = (obs_ws >= VIENTO_MIN_DIR) & (mod_ws >= VIENTO_MIN_DIR)
    dd = ((m.wd_mod[con_dir] - m.wd_obs[con_dir] + 180.0) % 360.0) - 180.0
    t_mod = m.t_mod + GRADIENTE_T * (altitud_est - cota_era5)
    res = {"horas": int(len(m)),
           "ws_obs": float(obs_ws.mean()), "ws_mod": float(mod_ws.mean()),
           "ws_sesgo": float((mod_ws - obs_ws).mean()),
           "ws_rmse": float(np.sqrt(((mod_ws - obs_ws) ** 2).mean())),
           "ws_ioa": ioa(mod_ws, obs_ws), "ws_r": float(np.corrcoef(mod_ws, obs_ws)[0, 1]),
           "wd_horas": int(con_dir.sum()),
           "wd_sesgo": float(dd.mean()), "wd_error": float(dd.abs().mean()),
           "calmas_obs": float((obs_ws < CALMA).mean() * 100),      # a 10 m, como ERA5
           "calmas_mod": float((m.ws_mod < CALMA).mean() * 100),
           "t_sesgo": float((t_mod - m.t_obs).mean()),
           "t_error": float((t_mod - m.t_obs).abs().mean())}
    res["cumple"] = {
        "ws_rmse": res["ws_rmse"] <= UMBRALES["ws_rmse"],
        "ws_sesgo": abs(res["ws_sesgo"]) <= UMBRALES["ws_sesgo"],
        "ws_ioa": res["ws_ioa"] >= UMBRALES["ws_ioa"],
        "wd_error": res["wd_error"] <= UMBRALES["wd_error"],
        "wd_sesgo": abs(res["wd_sesgo"]) <= UMBRALES["wd_sesgo"],
        "t_error": res["t_error"] <= UMBRALES["t_error"],
        "t_sesgo": abs(res["t_sesgo"]) <= UMBRALES["t_sesgo"]}
    return res


# ── figura de rosas ──────────────────────────────────────────────────────────────────────
def figura_rosas(rosas, ruta, titulo="ERA5 frente a Meteocat"):
    """Rosas de vientos de ERA5 y de cada estación, misma escala radial."""
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt
    n = len(rosas)
    cols = 3
    filas = math.ceil(n / cols)
    fig, ejes = plt.subplots(filas, cols, subplot_kw={"projection": "polar"},
                             figsize=(4.2 * cols, 4.0 * filas))
    ejes = np.atleast_1d(ejes).ravel()
    tope = max(f.max() for f, _ in rosas.values()) * 1.1
    ang = np.radians(np.arange(SECTORES) * 360.0 / SECTORES)
    for ax, (nombre, (f, calmas)) in zip(ejes, rosas.items()):
        color = ("#c0392b" if nombre.startswith("ERA5")
                 else "#2e8b57" if "Modelo" in nombre else "#1f6feb")
        ax.bar(ang, f, width=np.radians(360.0 / SECTORES) * 0.9, color=color, alpha=0.75,
               edgecolor="white")
        ax.set_theta_zero_location("N")
        ax.set_theta_direction(-1)
        ax.set_ylim(0, tope)
        ax.set_xticks(np.radians(np.arange(0, 360, 45)))
        ax.set_xticklabels(["N", "NE", "E", "SE", "S", "SO", "O", "NO"], fontsize=8)
        ax.tick_params(axis="y", labelsize=7)
        ax.set_title(f"{nombre}\ncalmas (< 0,5 m/s): {calmas:.1f} %".replace(".", ","),
                     fontsize=9)
    for ax in ejes[n:]:
        ax.set_visible(False)
    fig.suptitle(f"Procedencia del viento (% de horas) · {titulo}", fontsize=11)
    fig.tight_layout()
    fig.savefig(ruta, dpi=110)
    plt.close(fig)


# ── rosas de los vientos por estación (para el tooltip del mapa) ─────────────────────────
CLASES_VEL = (CALMA, 2.0, 4.0, 6.0, 8.0)          # m/s: 0,5-2 · 2-4 · 4-6 · 6-8 · ≥ 8


def _rosa_clases(ws, wd, sectores=SECTORES, clases=CLASES_VEL):
    """Frecuencias (% de TODAS las horas) por sector y clase de velocidad, y % de calmas."""
    ws, wd = np.asarray(ws, float), np.asarray(wd, float)
    n = len(ws)
    ancho = 360.0 / sectores
    sec = (((wd + ancho / 2) % 360) // ancho).astype(int)
    cls = np.digitize(ws, clases) - 1                 # -1 = calma
    tabla = np.zeros((sectores, len(clases)))
    ok = cls >= 0
    np.add.at(tabla, (sec[ok], cls[ok]), 1)
    return (tabla / n * 100).round(3).tolist(), float((~ok).mean() * 100)


def rosas_estaciones(lat, lon, anios=None, progreso=None):
    """Rosa de cada estación (viento a SU altura de medida) y la de ERA5 (10 m) en las MISMAS
    horas, para el periodo de reanálisis. Se guarda en caché y solo se recalcula si cambian
    los datos. Devuelve {"clases": [...], "estaciones": {código: {...}}}."""
    anios = config.REANALISIS_ANIOS if anios is None else anios
    from pathlib import Path
    ficheros = sorted([f for e in estaciones.cercanas(lat, lon)
                       for f in (estaciones.dir_meteocat() / e["codigo"]).glob("*.csv")
                       if f.stem.isdigit() and int(f.stem) in anios]
                      + list(meteo.dir_era5(lat, lon).glob("serie_sfc_*.csv")))
    firma = [[f.name, int(f.stat().st_mtime)] for f in ficheros]
    cache = dir_validacion() / "rosas_estaciones.json"
    if cache.is_file():
        try:
            d = json.loads(cache.read_text(encoding="utf-8"))
            if d.get("firma") == firma and d.get("anios") == list(anios):
                return d
        except ValueError:
            pass
    era = era5_horario(lat, lon, anios)
    res = {"clases": list(CLASES_VEL), "anios": list(anios), "firma": firma, "estaciones": {}}
    lista = estaciones.cercanas(lat, lon)
    for k, e in enumerate(lista):
        if progreso:
            progreso(int(100 * k / len(lista)), e["nombre"])
        df = estaciones.cargar(e["codigo"], anios)
        if df.empty:
            continue
        conv, _ = convencion(df)
        h = df["altura_viento_m"].dropna()
        hor = a_horario(df, conv).dropna(subset=["ws", "wd"])
        m = hor.merge(era[["time", "ws", "wd"]], on="time", suffixes=("", "_era5")).dropna()
        obs, calmas = _rosa_clases(m.ws, m.wd)
        mod, calmas_mod = _rosa_clases(m.ws_era5, m.wd_era5)
        res["estaciones"][e["codigo"]] = {
            "altura_m": float(h.iloc[0]) if len(h) else None, "horas": int(len(m)),
            "desde": f"{m.time.min():%Y}", "hasta": f"{m.time.max():%Y}",
            "obs": obs, "calmas": calmas,
            "era5": [round(sum(f), 3) for f in mod], "calmas_era5": calmas_mod}
    dir_validacion().mkdir(parents=True, exist_ok=True)
    cache.write_text(json.dumps(res, ensure_ascii=False), encoding="utf-8")
    return res


def rosas_periodo(lat, lon, ini, fin):
    """Rosa de lo MEDIDO en cada estación entre `ini` y `fin` (ambos incluidos; medias horarias UTC a la altura del anemómetro, Meteocat
    etiqueta el INICIO del intervalo), para los días que se ven en Episodio/Predicción. Devuelve {"clases", "ini", "fin", "dias",
    "estaciones": {código: {obs, calmas, horas, altura_m}}}."""
    d0 = pd.Timestamp(ini).normalize()
    d1 = pd.Timestamp(fin).normalize() + pd.Timedelta(days=1)
    anios = sorted({d0.year, (d1 - pd.Timedelta(days=1)).year})
    res = {"clases": list(CLASES_VEL), "ini": f"{d0:%Y-%m-%d}", "fin": f"{d1 - pd.Timedelta(days=1):%Y-%m-%d}",
           "dias": (d1 - d0).days, "estaciones": {}}
    for e in estaciones.cercanas(lat, lon):
        df = estaciones.cargar(e["codigo"], anios)
        if df.empty:
            continue
        hor = a_horario(df, "inicio").dropna(subset=["ws", "wd"])
        hor = hor[(hor.time >= d0) & (hor.time < d1)]
        if hor.empty:
            continue
        h = df["altura_viento_m"].dropna()
        obs, calmas = _rosa_clases(hor.ws, hor.wd)
        res["estaciones"][e["codigo"]] = {"obs": obs, "calmas": calmas, "horas": int(len(hor)),
                                          "altura_m": float(h.iloc[0]) if len(h) else None}
    return res


def rosas_dia(lat, lon, dia):
    """Rosa de lo MEDIDO en cada estación el día `dia` (medias horarias UTC a la altura del
    anemómetro; Meteocat etiqueta el INICIO del intervalo), para el día que se ve en Reanálisis.
    Devuelve {"clases", "dia", "estaciones": {código: {obs, calmas, horas, altura_m}}}."""
    d0 = pd.Timestamp(dia).normalize()
    d1 = d0 + pd.Timedelta(days=1)
    res = {"clases": list(CLASES_VEL), "dia": f"{d0:%Y-%m-%d}", "estaciones": {}}
    for e in estaciones.cercanas(lat, lon):
        df = estaciones.cargar(e["codigo"], [d0.year])
        if df.empty:
            continue
        hor = a_horario(df, "inicio").dropna(subset=["ws", "wd"])
        hor = hor[(hor.time >= d0) & (hor.time < d1)]
        if hor.empty:
            continue
        h = df["altura_viento_m"].dropna()
        obs, calmas = _rosa_clases(hor.ws, hor.wd)
        res["estaciones"][e["codigo"]] = {"obs": obs, "calmas": calmas, "horas": int(len(hor)),
                                          "altura_m": float(h.iloc[0]) if len(h) else None}
    return res


# ── estaciones del año ───────────────────────────────────────────────────────────────
ESTACIONES_ANIO = {"invierno": (12, 1, 2), "primavera": (3, 4, 5), "verano": (6, 7, 8),
                   "otoño": (9, 10, 11)}
