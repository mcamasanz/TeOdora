# -*- coding: utf-8 -*-
"""La previsión en las estaciones, para la predicción (`viento_periodo --prediccion`; usuario, 2026-11-18: «Previsión corregida»).

En cada estación y hora: el viento de GFS corregido con el MOS de esa estación (`mos.aplicar`), y la temperatura, la humedad y la
presión en superficie de GFS. Donde hay medida (la víspera y lo que va de hoy), manda lo medido y la previsión rellena el resto
(`completar`). Así va al motor del viento 3D, como si fueran las estaciones (NOOBS = 1), y se guarda con la serie
(`prevision_estaciones.csv`, `guardar`/`leer`) para las rosas y el informe.

⚠️ La mejora de dirección del MOS es LOCAL a cada estación (ver `mos/README.md`): lejos de ellas, el viento 3D tiene la dirección
de GFS; la velocidad, en cambio, sí mejora en todo el dominio.
"""
import numpy as np
import pandas as pd

FICHERO = "prevision_estaciones.csv"
COLUMNAS = ["ws", "wd", "t", "rh", "p"]


def en_estaciones(ds, viento, estaciones, horas):
    """{código: tabla horaria (time, ws, wd, t, rh, p)} de la previsión: el viento del MOS, ya por horas (`aplicar.horaria`, en
    `viento`), y la temperatura (°C), la humedad (%) y la presión en superficie (hPa) de la ejecución `ds` de GFS
    (`gfs_noaa.ejecucion`), interpoladas a la estación y a cada hora. Fuera de los plazos de `ds`, NaN. Las estaciones sin viento del
    MOS no salen."""
    import xarray as xr
    horas = pd.DatetimeIndex(horas)
    ini = pd.Timestamp(np.asarray(ds["init_time"].values).reshape(-1)[0])
    plazos = xr.DataArray(((horas - ini) / pd.Timedelta(hours=1)).to_numpy(float), dims="hora")
    salen = {}
    for e in estaciones:
        c = e["codigo"]
        if c not in viento:
            continue
        x = ds[["temperature_2m", "relative_humidity_2m", "surface_pressure"]].interp(latitude=e["lat"], longitude=e["lon"])
        x = x.interp(plazo_h=plazos)
        t = viento[c].set_index("time").reindex(horas)
        salen[c] = pd.DataFrame({"time": horas, "ws": t["ws"].to_numpy(), "wd": t["wd"].to_numpy(),
                                 "t": x.temperature_2m.to_numpy(), "rh": np.clip(x.relative_humidity_2m.to_numpy(), 0.0, 100.0),
                                 "p": x.surface_pressure.to_numpy()})
    return salen


def completar(medido, prevista, horas):
    """Lo medido de una estación (tabla horaria de `casos.viento3d.obs_horarias`; None o vacía si no hay) completado con su previsión
    (`en_estaciones`; None si no hay) en las horas sin medida. El viento va por parejas: donde falta la velocidad medida, la velocidad
    y la dirección son las previstas (una calma medida, sin dirección, se queda como está); la temperatura, la humedad y la presión,
    cada una donde falte. Devuelve (time, ws, wd, t, rh, p, previsto), con `previsto` True en las horas con el viento previsto."""
    horas = pd.DatetimeIndex(horas)
    if medido is not None and len(medido):
        m = medido.drop_duplicates("time").set_index("time")[COLUMNAS].reindex(horas).astype(float)
    else:
        m = pd.DataFrame(np.nan, index=horas, columns=COLUMNAS)
    previsto = np.zeros(len(horas), bool)
    if prevista is not None and len(prevista):
        f = prevista.drop_duplicates("time").set_index("time")[COLUMNAS].reindex(horas).astype(float)
        previsto = (m["ws"].isna() & f["ws"].notna()).to_numpy()
        m.loc[previsto, ["ws", "wd"]] = f.loc[previsto, ["ws", "wd"]].to_numpy()
        for c in ("t", "rh", "p"):
            m[c] = m[c].fillna(f[c])
    m["previsto"] = previsto
    return m.rename_axis("time").reset_index()


def guardar(tablas, carpeta):
    """Las tablas de `completar` ({código: tabla}) en `carpeta/prevision_estaciones.csv`, con la columna `codigo`."""
    filas = [t.assign(codigo=c) for c, t in tablas.items()]
    if not filas:
        return None
    f = carpeta / FICHERO
    pd.concat(filas, ignore_index=True)[["codigo", "time", *COLUMNAS, "previsto"]].to_csv(f, index=False, float_format="%.3f")
    return f


def leer(serie, ini):
    """La previsión en las estaciones guardada con la serie de una predicción (la de su mes de inicio), o None si no está."""
    from teodors.casos import viento3d as vc
    f = vc.dir_serie(serie) / f"{pd.Timestamp(ini):%Y%m}" / FICHERO
    return pd.read_csv(f, parse_dates=["time"]) if f.is_file() else None
