# -*- coding: utf-8 -*-
"""El MOS entrenado (`mos.entrenar`), aplicado a una ejecución NUEVA de GFS: el viento corregido en cada estación, para la
predicción (`operacion.prevision`, `operacion.viento_periodo --prediccion`).

Las entradas salen de las mismas funciones que en el entrenamiento (`tabla.entradas_gfs` y `entrenar.preparar`). El GFS de NOAA
que baja la predicción (`fuentes.gfs_noaa.ejecucion(…, extra=True)`) da lo mismo que el archivo con el que se entrenó
(`fuentes.gfs_dynamical`), salvo su redondeo: comprobado el 2026-11-18 (ver `gfs_noaa.EXTRA`). Del modelo se usa el gradient
boosting («gb»), como en las métricas de `entrenar`: la velocidad, de su propio modelo y nunca negativa, y la dirección, de u y v.

Los modelos son los de la planta (`meteo/mos/`, que viajan con ella) o, si no están, los de DATOS/mos/modelos. Los de la planta
piloto se entrenaron con scikit-learn 1.9.0 y con la 1.9.1 dan exactamente lo mismo en sus 330.705 filas de validación
(comprobado el 2026-11-18).
"""
import numpy as np
import pandas as pd

from teodors.mos.entrenar import ENTRADAS, preparar
from teodors.mos.tabla import entradas_gfs
from teodors.planta.geo import direccion

VARIABLES = ["wind_u_10m", "wind_v_10m", "wind_u_100m", "wind_v_100m", "temperature_2m", "relative_humidity_2m",
             "total_cloud_cover_atmosphere", "downward_short_wave_radiation_flux_surface", "pressure_reduced_to_mean_sea_level"]
OBJETIVOS = ("u", "v", "ws")
COLUMNAS = ["codigo", "valid_time", "plazo_h", "u", "v", "ws", "wd", "gfs_ws10", "gfs_wd10"]


def entradas(ds):
    """De una ejecución de `gfs_noaa.ejecucion(…, extra=True)` (plazo_h × latitude × longitude, con `init_time` escalar y la presión
    en hPa) a la forma del archivo del entrenamiento: init_time × lead_time_h × latitude × longitude, con sus nombres y sus
    unidades (la presión al nivel del mar, en Pa)."""
    ini = pd.Timestamp(np.asarray(ds["init_time"].values).reshape(-1)[0])
    g = ds.rename({"plazo_h": "lead_time_h"})
    if "pressure_msl" in g:
        g["pressure_reduced_to_mean_sea_level"] = g["pressure_msl"] * 100.0
    falta = [v for v in VARIABLES if v not in g]
    if falta:
        raise ValueError(f"Al GFS le faltan las entradas del MOS {falta}: hay que bajarlo con `gfs_noaa.ejecucion(…, extra=True)`")
    g = g[VARIABLES]
    if "init_time" in g.coords:
        g = g.drop_vars("init_time")
    return g.expand_dims(init_time=[ini]).transpose("init_time", "lead_time_h", "latitude", "longitude")


def carpeta_modelos():
    """La carpeta de los modelos: la de la planta (`meteo/mos/`, viaja con ella) o, si no, DATOS/mos/modelos. None si no hay."""
    from teodors import planta as config
    for d in (config.DIR_METEO_PLANTA / "mos", config.DATOS / "mos" / "modelos"):
        if d.is_dir() and any(d.glob("*_ws.joblib")):
            return d
    return None


def cargar(codigos, carpeta=None):
    """{código: {"u", "v", "ws": modelo gb}} de las estaciones que tienen sus tres modelos; las demás no salen. Un modelo que pida
    otras entradas que `entrenar.ENTRADAS` es un error."""
    import warnings

    import joblib
    carpeta = carpeta or carpeta_modelos()
    if carpeta is None:
        return {}
    salen = {}
    for c in codigos:
        fs = {k: carpeta / f"{c}_{k}.joblib" for k in OBJETIVOS}
        if not all(f.is_file() for f in fs.values()):
            continue
        with warnings.catch_warnings():
            warnings.filterwarnings("ignore", message="Trying to unpickle estimator")        # otra versión menor de scikit-learn (ver arriba)
            m = {k: joblib.load(f) for k, f in fs.items()}
        if any(list(x["entradas"]) != ENTRADAS for x in m.values()):
            raise ValueError(f"Los modelos de {c} piden otras entradas que `mos.entrenar.ENTRADAS`")
        salen[c] = {k: x["gb"] for k, x in m.items()}
    return salen


def corregir(ds, estaciones, modelos):
    """El viento corregido en cada estación, en los plazos de la ejecución `ds` (`gfs_noaa.ejecucion(…, extra=True)`).
    estaciones: [{"codigo", "lat", "lon"}]; las que no tienen modelos no salen. Devuelve una tabla con `COLUMNAS`."""
    g = entradas(ds)
    salen = []
    for e in estaciones:
        m = modelos.get(e["codigo"])
        if m is None:
            continue
        t = preparar(entradas_gfs(g, e["lat"], e["lon"]))
        X = t[ENTRADAS].to_numpy(np.float32)
        u, v = m["u"].predict(X), m["v"].predict(X)
        ws = np.maximum(m["ws"].predict(X), 0.0)
        salen.append(pd.DataFrame({"codigo": e["codigo"], "valid_time": t.valid_time.to_numpy(), "plazo_h": t.plazo_h.to_numpy(),
                                   "u": u, "v": v, "ws": ws, "wd": direccion(u, v), "gfs_ws10": t.gfs_ws10.to_numpy(),
                                   "gfs_wd10": t.gfs_wd10.to_numpy()}))
    return pd.concat(salen, ignore_index=True) if salen else pd.DataFrame(columns=COLUMNAS)


def horaria(t, horas):
    """De los plazos de `corregir` (cada 3 h en la predicción) a cada hora de `horas`, por estación: u, v y la velocidad, lineales
    en el tiempo, y la dirección, de u y v. Fuera del primer y el último plazo, NaN. Devuelve {código: tabla (time, ws, wd)}."""
    horas = pd.DatetimeIndex(horas)
    salen = {}
    for c, d in t.groupby("codigo"):
        d = d.set_index(pd.DatetimeIndex(d["valid_time"])).sort_index()[["u", "v", "ws"]].astype(float)
        x = d.reindex(d.index.union(horas)).interpolate(method="time", limit_area="inside").reindex(horas)
        salen[c] = pd.DataFrame({"time": horas, "ws": x["ws"].to_numpy(), "wd": direccion(x["u"].to_numpy(), x["v"].to_numpy())})
    return salen
