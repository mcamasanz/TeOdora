# -*- coding: utf-8 -*-
"""Niveles de presión de GFS 0,25° (campo inicial de teOdors viento3d en predicción) en la caja de
la planta (`pronostico.caja_gfs` de planta.json).

Fuente: ficheros GRIB2 originales del archivo de NOAA en AWS (`s3://noaa-gfs-bdp-pds`, datos
públicos de NOAA). Cada mensaje es un campo GLOBAL (~0,9 MB): con el índice .idx de cada fichero
se piden solo los mensajes necesarios (lecturas por rangos) y se recorta la caja.

Por ejecución de las 00 UTC: plazos 0, 3, …, 24 h (la predicción a 1 día; se interpola a horas
al preparar el caso), 7 niveles (1000-700 hPa) × altura, T, u, v, y en superficie presión, cota
del modelo, T y HR a 2 m, viento a 10 m, nubosidad y presión al nivel del mar.
Medido el 2026-10-20: ~31 MB de tráfico por plazo → ~2,5 GB por semana (9 ejecuciones con la del
arranque).

    python -m teodors.fuentes.gfs_noaa [--semanas aaaa-mm-dd …] [--hilos 9] [--paralelo 2]
Sin --semanas, las de `pronostico.semanas_mos` de planta.json. Con la carpeta de la planta en TEODORS_PLANTA.
Salida: DATOS/meteo/gfs_niveles/gfs00_AAAAMMDD.nc (una ejecución por fichero; reanudable)
"""
import argparse
import sys
import time
import urllib.request
from concurrent.futures import ThreadPoolExecutor

import numpy as np
import pandas as pd

from teodors import planta as config

URL = "https://noaa-gfs-bdp-pds.s3.amazonaws.com/gfs.{d:%Y%m%d}/00/atmos/gfs.t00z.pgrb2.0p25.f{p:03d}"
PLAZOS = list(range(0, 25, 3))
NIVELES = (1000, 975, 950, 925, 900, 850, 700)
SUPERFICIE = {"PRES:surface": "surface_pressure", "HGT:surface": "surface_height",
              "TMP:2 m above ground": "temperature_2m", "RH:2 m above ground": "relative_humidity_2m",
              "UGRD:10 m above ground": "wind_u_10m", "VGRD:10 m above ground": "wind_v_10m",
              "TCDC:entire atmosphere": "cloud_cover", "PRMSL:mean sea level": "pressure_msl"}
NIVEL_VAR = {"HGT": "geopotential_height", "TMP": "temperature", "UGRD": "wind_u", "VGRD": "wind_v"}
HUECO = 2_000_000              # se juntan rangos separados menos de 2 MB


def indices_caja(caja=None):
    """Filas y columnas de una caja {"lat": [sur, norte], "lon": [oeste, este]} en la malla global de GFS 0,25°, que va de 90 a −90 en
    latitud y de 0 a 360 en longitud. Al oeste de Greenwich la caja cae al final de cada fila y, si cruza el meridiano 0, da la
    vuelta: por eso I es una lista de columnas y no un tramo. Por defecto, la de la planta activa."""
    caja = config.pide("pronostico", "caja_gfs") if caja is None else caja
    j0, j1 = int(round((90.0 - caja["lat"][1]) / 0.25)), int(round((90.0 - caja["lat"][0]) / 0.25))
    i0, i1 = int(round(caja["lon"][0] / 0.25)), int(round(caja["lon"][1] / 0.25))
    return slice(j0, j1 + 1), np.arange(i0, i1 + 1) % 1440


def _get(url, rango=None, reintentos=6):
    for k in range(reintentos):
        try:
            req = urllib.request.Request(url, headers={"Range": f"bytes={rango[0]}-{rango[1]}"}
                                         if rango else {})
            return urllib.request.urlopen(req, timeout=120).read()
        except Exception as e:
            if k == reintentos - 1:
                raise
            print(f"   reintento {k + 1}: {url[-40:]} {type(e).__name__}", flush=True)
            time.sleep(5 * 2 ** k)


def plazo(dia, p):
    import pygrib                       # solo aquí: quien solo quiere NIVELES no lo necesita
    J, I = indices_caja()
    url = URL.format(d=dia, p=p)
    idx = _get(url + ".idx").decode().splitlines()
    ofs = [int(l.split(":")[1]) for l in idx]
    quiero = {}
    for k, l in enumerate(idx):
        c = l.split(":")
        clave = f"{c[3]}:{c[4]}"
        nombre = SUPERFICIE.get(clave)
        if nombre is None and c[3] in NIVEL_VAR and c[4].endswith(" mb") \
                and float(c[4].split()[0]) in NIVELES:
            nombre = f"{NIVEL_VAR[c[3]]}_{int(float(c[4].split()[0]))}hPa"
        if nombre and nombre not in quiero:                     # el primero (p. ej. TCDC)
            quiero[nombre] = (ofs[k], ofs[k + 1] - 1)
    tramos = []
    for ini, fin in sorted(quiero.values()):
        if tramos and ini - tramos[-1][1] < HUECO:
            tramos[-1][1] = max(tramos[-1][1], fin)
        else:
            tramos.append([ini, fin])
    blobs = [(a, _get(url, (a, b))) for a, b in tramos]
    out = {}
    for nombre, (ini, fin) in quiero.items():
        a, blob = next((a, bl) for a, bl in blobs if a <= ini and fin < a + len(bl))
        m = pygrib.fromstring(blob[ini - a:fin - a + 1])
        out[nombre] = np.asarray(m.values, dtype=np.float32)[J, I]
    return out


def ejecucion(dia, hilos, plazos=PLAZOS):
    import xarray as xr
    plazos = list(plazos)
    with ThreadPoolExecutor(hilos) as ex:
        campos = list(ex.map(lambda p: plazo(dia, p), plazos))
    nombres = sorted(set().union(*campos))
    J, I = indices_caja()
    lat = 90.0 - 0.25 * np.arange(721)[J]
    lon = (0.25 * np.arange(1440)[I] + 180.0) % 360.0 - 180.0        # de −180 a 180, y creciente: se interpola en ella
    datos = {}
    for n in nombres:
        x = np.stack([c.get(n, np.full((len(lat), len(lon)), np.nan, np.float32)) for c in campos])
        if n.startswith("temperature"):
            x = x - 273.15                                           # °C
        if n in ("surface_pressure", "pressure_msl"):
            x = x / 100.0                                            # hPa
        datos[n] = (("plazo_h", "latitude", "longitude"), x)
    return xr.Dataset(datos, coords={"plazo_h": plazos, "latitude": lat, "longitude": lon,
                                     "init_time": pd.Timestamp(dia)},
                      attrs={"fuente": "NOAA GFS 0.25 (s3://noaa-gfs-bdp-pds), dominio público"})


def main():
    sys.stdout.reconfigure(encoding="utf-8")
    ap = argparse.ArgumentParser()
    ap.add_argument("--semanas", nargs="*", default=None)
    ap.add_argument("--hilos", type=int, default=9)
    ap.add_argument("--paralelo", type=int, default=2, help="ejecuciones a la vez")
    a = ap.parse_args()
    if a.semanas is None:
        a.semanas = config.pide("pronostico", "semanas_mos")
    salida = config.DATOS / "meteo" / "gfs_niveles"
    salida.mkdir(parents=True, exist_ok=True)
    dias = sorted({d for s in a.semanas
                   for d in pd.date_range(pd.Timestamp(s) - pd.Timedelta(days=2), periods=9)})
    pend = [d for d in dias if not (salida / f"gfs00_{d:%Y%m%d}.nc").exists()]
    print(f"{len(a.semanas)} semanas · {len(dias)} ejecuciones ({len(pend)} pendientes) · plazos "
          f"{PLAZOS} · {len(NIVELES)} niveles", flush=True)
    t0 = time.time()

    def una(d):
        t1 = time.time()
        ds = ejecucion(d, a.hilos)
        f = salida / f"gfs00_{d:%Y%m%d}.nc"
        ds.to_netcdf(f.with_suffix(".tmp"))
        f.with_suffix(".tmp").replace(f)
        return d, time.time() - t1, len(ds.data_vars)

    with ThreadPoolExecutor(a.paralelo) as ex:
        for k, (d, dt, nv) in enumerate(ex.map(una, pend), 1):
            resto = (time.time() - t0) / k * (len(pend) - k) / 60
            print(f"{d:%Y-%m-%d}: {nv} variables en {dt:.0f} s · quedan ~{resto:.0f} min", flush=True)
    print(f"terminado en {(time.time() - t0) / 60:.0f} min", flush=True)


if __name__ == "__main__":
    main()
