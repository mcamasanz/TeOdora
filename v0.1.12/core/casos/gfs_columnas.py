# -*- coding: utf-8 -*-
"""Columnas de GFS (niveles de presión de DATOS/meteo/gfs_niveles) para el pronóstico 3D de `meteo.viento3d`:
predicción a 1 día de cada hora (ejecución de las 00 UTC de H − 1 h, interpolada entre plazos) o, en la
predicción, la de la ejecución `ciclo` desde que empieza, en n_col × n_col columnas cada paso_col_m (bloque `pronostico` de
planta.json) centradas en la planta.
"""
import numpy as np
import pandas as pd
import xarray as xr

from teodors import planta as config
from teodors.fuentes.gfs_noaa import NIVELES
from teodors.planta import geo
from teodors.preparacion.viento3d import pronostico


def dia1(h):
    """Ejecución (00 UTC) y plazo de la predicción a 1 día de la hora h."""
    d = (h - pd.Timedelta(hours=1)).normalize()
    return d, int((h - d) / pd.Timedelta(hours=1))


def niveles(dias, ficheros=(), raiz=None):
    base = raiz or (config.DATOS / "meteo" / "gfs_niveles")       # el episodio lo tiene en tmp; el reanálisis/predicción, en DATOS
    fs = [base / f"gfs00_{d:%Y%m%d}.nc" for d in dias] + list(ficheros)
    ds = xr.concat([xr.open_dataset(f).load() for f in fs], dim="init_time")
    cc = ds.cloud_cover.transpose("init_time", "plazo_h", ...).values.copy()
    cc[:, 0] = np.where(np.isnan(cc[:, 0]), cc[:, 1], cc[:, 0])     # no existe en el plazo 0
    ds["cloud_cover"] = (("init_time", "plazo_h", "latitude", "longitude"), cc)
    return ds


def columnas(ds, horas, ciclo=None):
    """Filas (time, i, j) con los nombres de columna que espera teOdors
    (`preparacion.viento3d.pronostico.escribir_columnas`), y los centros xs, ys de las columnas."""
    emp = config.cargar_emplazamiento()
    pts, (xs, ys) = pronostico.rejilla_puntos(geo.a_utm(emp["lat"], emp["lon"]), config.pide("pronostico", "n_col"),
                                              config.pide("pronostico", "paso_col_m"), config.EPSG_UTM)
    la = xr.DataArray([p[2] for p in pts], dims="p")
    lo = xr.DataArray([p[3] for p in pts], dims="p")
    filas = []
    for h in horas:
        d, L = (ciclo, int((h - ciclo) / pd.Timedelta(hours=1))) if ciclo is not None and h > ciclo else dia1(h)
        x = ds.sel(init_time=d).interp(plazo_h=L).interp(latitude=la, longitude=lo)
        f = pd.DataFrame({"time": h, "i": [p[0] for p in pts], "j": [p[1] for p in pts]})
        t2, rh = x.temperature_2m.values, np.clip(x.relative_humidity_2m.values, 1, 100)
        gam = np.log(rh / 100) + 17.67 * t2 / (t2 + 243.5)
        f["surface_pressure"] = x.surface_pressure.values
        f["pressure_msl"] = x.pressure_msl.values
        f["temperature_2m"], f["dew_point_2m"] = t2, 243.5 * gam / (17.67 - gam)
        f["precipitation"] = 0.0
        f["shortwave_radiation"] = 0.0
        f["wind_speed_10m"] = np.hypot(x.wind_u_10m.values, x.wind_v_10m.values)
        f["wind_direction_10m"] = geo.direccion(x.wind_u_10m.values, x.wind_v_10m.values)
        f["cloud_cover"] = x.cloud_cover.values
        for p in NIVELES:
            u, v = x[f"wind_u_{p}hPa"].values, x[f"wind_v_{p}hPa"].values
            f[f"geopotential_height_{p}hPa"] = x[f"geopotential_height_{p}hPa"].values
            f[f"temperature_{p}hPa"] = x[f"temperature_{p}hPa"].values
            f[f"wind_speed_{p}hPa"], f[f"wind_direction_{p}hPa"] = np.hypot(u, v), geo.direccion(u, v)
        filas.append(f)
    return pd.concat(filas, ignore_index=True), xs, ys
