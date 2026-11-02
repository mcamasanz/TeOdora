# -*- coding: utf-8 -*-
"""Predicciones ANTIGUAS de GFS 0,25° en la caja de la planta (`pronostico.caja_gfs` de planta.json), para entrenar el MOS.

Fuente: archivo de dynamical.org («NOAA GFS forecast», Icechunk/Zarr en AWS, CC BY 4.0; cita:
«NOAA GFS from dynamical.org»): todas las ejecuciones desde 2021-05-01, plazos de 0 a 384 h
(horarios hasta 120 h). Se guarda solo la caja, para la ejecución de las 00 UTC y los plazos de 0 a
120 h. Un fichero por mes en DATOS/meteo/gfs/: se puede cortar y reanudar.

Medido el 2026-10-20, con una caja de 5 × 5 puntos: ~3,3 MB de tráfico por ejecución y variable (se lee el bloque de 121 × 121
puntos que contiene la caja) → 9 variables × ~2 000 ejecuciones ≈ 60 GB y ~1 h con 16 hilos;
en disco, ~100 MB.

⚠️ Necesita Python ≥ 3.12 (icechunk 2), en un entorno aislado: extra `teodors[gfs_historico]`, o
`uv pip install "icechunk>=2" xarray zarr numpy pandas netCDF4`. Al importarlo solo carga numpy y pandas; de teOdors,
`teodors.planta` (biblioteca estándar): no hace falta el resto del paquete.

    python -m teodors.fuentes.gfs_dynamical [--desde 2021-05] [--hasta 2026-09] [--hilos 16]
"""
import argparse
import json
import sys
import time
import urllib.request
from concurrent.futures import ThreadPoolExecutor

import numpy as np
import pandas as pd

from teodors import planta as config

STAC = "https://stac.dynamical.org/catalog.json"
COLECCION = "noaa-gfs-forecast"
CICLO_H = 0
PLAZO_MAX_H = 120
VARIABLES = ["wind_u_10m", "wind_v_10m", "wind_u_100m", "wind_v_100m", "temperature_2m",
             "relative_humidity_2m", "total_cloud_cover_atmosphere",
             "downward_short_wave_radiation_flux_surface", "pressure_reduced_to_mean_sea_level"]
REINTENTOS = 6


def abrir():
    """Repositorio Icechunk de la colección (la versión vigente se lee del catálogo STAC)."""
    import icechunk
    import xarray as xr
    import zarr
    cat = json.load(urllib.request.urlopen(STAC, timeout=60))
    ref = next(l["href"] for l in cat["links"]
               if l.get("rel") == "child" and COLECCION in l["href"])
    ref = ref if ref.startswith("http") else STAC.rsplit("/", 1)[0] + "/" + ref.lstrip("./")
    s3 = json.load(urllib.request.urlopen(ref, timeout=60))["assets"]["icechunk"]["href"]
    cubo, prefijo = s3.removeprefix("s3://").split("/", 1)
    repo = icechunk.Repository.open(icechunk.s3_storage(
        bucket=cubo, prefix=prefijo.rstrip("/"), region="us-west-2", anonymous=True))
    store = repo.readonly_session("main").store
    return xr.open_zarr(store, chunks=None), zarr.open_group(store, mode="r"), s3


def leer(g, v, n, k, j, i):
    for intento in range(REINTENTOS):
        try:
            return np.asarray(g[v][n, k, j[0]:j[-1] + 1, i[0]:i[-1] + 1], dtype=np.float32)
        except Exception as e:                       # cortes de red: esperar y repetir
            if intento == REINTENTOS - 1:
                raise
            print(f"   reintento {intento + 1} ({v}, {n}): {type(e).__name__}: {e}", flush=True)
            time.sleep(10 * 2 ** intento)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--desde", default="2021-05")
    ap.add_argument("--hasta", default=None, help="último mes (por defecto, el anterior al actual)")
    ap.add_argument("--hilos", type=int, default=16)
    a = ap.parse_args()
    import xarray as xr
    salida, caja = config.DATOS / "meteo" / "gfs", config.pide("pronostico", "caja_gfs")
    salida.mkdir(parents=True, exist_ok=True)
    ds, g, origen = abrir()
    lat, lon = ds.latitude.values, ds.longitude.values
    j = np.where((lat >= caja["lat"][0]) & (lat <= caja["lat"][1]))[0]
    i = np.where((lon >= caja["lon"][0]) & (lon <= caja["lon"][1]))[0]
    plazos = ds.lead_time.values.astype("timedelta64[h]").astype(int)
    kk = np.where(plazos <= PLAZO_MAX_H)[0]
    k = slice(int(kk[0]), int(kk[-1]) + 1)
    inits = pd.DatetimeIndex(ds.init_time.values)
    hasta = pd.Period(a.hasta, "M") if a.hasta else pd.Timestamp.now("UTC").tz_localize(None).to_period("M") - 1
    meses = pd.period_range(pd.Period(a.desde, "M"), hasta, freq="M")
    (salida / "origen.json").write_text(json.dumps({
        "fuente": "NOAA GFS forecast (dynamical.org)", "licencia": "CC BY 4.0",
        "cita": "NOAA GFS from dynamical.org", "almacen": origen, "ciclo_utc": CICLO_H,
        "plazos_h": [0, PLAZO_MAX_H], "caja": caja, "variables": VARIABLES,
        "descargado": pd.Timestamp.now().isoformat(timespec="seconds")}, indent=1),
        encoding="utf-8")
    print(f"GFS {COLECCION}: {origen}\n{len(meses)} meses · caja {lat[j].tolist()} × "
          f"{lon[i].tolist()} · {len(VARIABLES)} variables · plazos 0-{PLAZO_MAX_H} h", flush=True)
    t_ini = time.time()
    for m, mes in enumerate(meses):
        fichero = salida / f"gfs{CICLO_H:02d}_{mes.strftime('%Y%m')}.nc"
        if fichero.exists():
            continue
        sel = np.where((inits.to_period("M") == mes) & (inits.hour == CICLO_H))[0]
        if not len(sel):
            print(f"{mes}: sin ejecuciones en el archivo", flush=True)
            continue
        t0 = time.time()
        tareas = [(v, int(n)) for n in sel for v in VARIABLES]
        with ThreadPoolExecutor(a.hilos) as ex:
            datos = list(ex.map(lambda t: leer(g, t[0], t[1], k, j, i), tareas))
        cubo = {v: np.stack([d for (vv, _), d in zip(tareas, datos) if vv == v]) for v in VARIABLES}
        out = xr.Dataset({v: (("init_time", "lead_time_h", "latitude", "longitude"), x)
                          for v, x in cubo.items()},
                         coords={"init_time": inits[sel], "lead_time_h": plazos[kk],
                                 "latitude": lat[j], "longitude": lon[i]},
                         attrs={"fuente": "NOAA GFS from dynamical.org (CC BY 4.0)"})
        tmp = fichero.with_suffix(".tmp")
        out.to_netcdf(tmp, encoding={v: {"zlib": True, "complevel": 4} for v in VARIABLES})
        tmp.replace(fichero)
        resto = (time.time() - t_ini) / (m + 1) * (len(meses) - m - 1) / 60
        print(f"{mes}: {len(sel)} ejecuciones en {time.time() - t0:.0f} s · "
              f"{fichero.stat().st_size / 1e6:.1f} MB · quedan ~{resto:.0f} min", flush=True)
    print(f"terminado en {(time.time() - t_ini) / 60:.0f} min", flush=True)


if __name__ == "__main__":
    sys.stdout.reconfigure(encoding="utf-8")
    main()
