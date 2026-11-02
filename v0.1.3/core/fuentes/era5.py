# -*- coding: utf-8 -*-
"""Meteorología de reanálisis: ERA5 horario en la planta (superficie + perfil vertical).

Trampas del CDS que ya están resueltas aquí:
  · el CDS nuevo entrega a veces un .zip con dos netCDF (instantáneas y acumuladas): se
    detecta la firma «PK» y se unen;
  · límite de coste por petición: superficie MES a MES; el perfil por QUINCENAS (6 niveles ×
    mes completo lo rechaza); 2 peticiones a la vez y reintentos con espera creciente;
  · la cola del CDS puede tardar HORAS por petición (medido el 2026-10-15: de 10 min a 4 h).
    Por eso cada petición se sigue por su identificador: si se corta la red se sigue
    consultando la MISMA (no se reenvía y no se pierde el puesto en la cola), y al arrancar se
    RETOMAN las peticiones idénticas que ya estén en el CDS (en cola o terminadas sin bajar).
    Con cdsapi, un corte de DNS de unos minutos hacía reenviar la petición y perder horas;
  · `sshf` es positivo hacia abajo (teOdors `penacho` lo quiere hacia arriba: H = −sshf, se hará al
    escribir el .sfc); `ssrd` y `sshf` vienen en J/m² acumulados en la hora → ÷ 3600 = W/m².

Caché (reanudable): DATOS/meteo/era5/<lat>_<lon>/
  sfc_AAAAMM.csv  superficie (UTC): u10 v10 t2m d2m tcc ssrd sshf blh zust sp tp wspd wdir
  pfl_AAAAMM.csv  perfil largo: time level height_asl_m wdir wspd temp_c
  punto.json      celda ERA5 usada: lat/lon, máscara tierra-mar, cota del modelo
"""
import calendar
import json
import tempfile
import threading
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path

import numpy as np
import pandas as pd

from teodors import planta as config
from teodors.comun import registro

log = registro.get("meteo")

CDS_URL = "https://cds.climate.copernicus.eu/api"
CDS_ESPERA_MAX_H = 48         # una petición se abandona tras 48 h sin terminar (cola + cortes)
CDS_SONDEO_S = (30, 180)      # sondeo del estado: de 30 s creciendo hasta 3 min
CAJA_GRADOS = 0.15            # semiancho de la petición alrededor del punto (malla de 0,25°)

ERA5_SFC = "reanalysis-era5-single-levels"
ERA5_PL = "reanalysis-era5-pressure-levels"
VARS_SFC = {                                   # nombre CDS -> nombre corto en el netCDF
    "10m_u_component_of_wind": "u10", "10m_v_component_of_wind": "v10",
    "2m_temperature": "t2m", "2m_dewpoint_temperature": "d2m",
    "total_cloud_cover": "tcc", "surface_solar_radiation_downwards": "ssrd",
    "surface_sensible_heat_flux": "sshf", "boundary_layer_height": "blh",
    "friction_velocity": "zust", "surface_pressure": "sp", "total_precipitation": "tp",
}
VARS_PFL = {"u_component_of_wind": "u", "v_component_of_wind": "v",
            "temperature": "t", "geopotential": "z"}
NIVELES_PFL = ["975", "950", "925", "900", "850", "700"]     # hPa (1000 queda bajo el suelo)
G0 = 9.80665


class SinLicencia(Exception):
    """El CDS rechaza por licencia/permisos: no tiene sentido reintentar."""


class DemasiadoGrande(Exception):
    """El CDS rechaza la petición por tamaño/coste: hay que trocearla, no reintentarla."""


class TrabajoFallido(Exception):
    """El CDS dio la petición por fallida: se puede reenviar."""


# ── cliente y lectura ────────────────────────────────────────────────────────────────────
def _cliente():
    """Cliente oficial del CDS (ecmwf-datastores). Pocos reintentos internos: los cortes de
    red los gestiona _esperar(), que registra y no pierde la petición."""
    from ecmwf.datastores import Client
    if not config.CDS_CLAVE.is_file():
        raise FileNotFoundError(f"Falta la clave del CDS: {config.CDS_CLAVE}")
    token = config.CDS_CLAVE.read_text(encoding="utf-8").strip().splitlines()[-1].strip()
    return Client(url=CDS_URL, key=token, progress=False, maximum_tries=3, retry_after=20,
                  sleep_max=60, timeout=120)


def _clasificar(e, etiqueta):
    """Convierte un error del CDS en la excepción que decide qué hacer."""
    msg = str(e).lower()
    if any(s in msg for s in ("licence", "license", "not accepted", "forbidden", "403", "401",
                              "unauthor", "required licences")):
        return SinLicencia(f"{etiqueta}: {e}")
    if any(s in msg for s in ("too large", "cost limit", "costlimit", "exceed")):
        return DemasiadoGrande(f"{etiqueta}: {e}")
    return None


def _es_de_red(e):
    """Cortes de red / DNS / tiempo agotado / fallo del servidor (5xx, 429): se espera y se
    vuelve a consultar la MISMA petición.
    ⚠️ En `requests`, HTTPError hereda de OSError: sin mirar el código, un 404 («la petición
    ya no existe en el CDS») pasaba por corte de red y se esperaba 48 h a una petición perdida
    (pasó el 2026-10-16 con dos quincenas de 2022). Un 4xx NO es de red: se reenvía."""
    import requests
    if isinstance(e, requests.exceptions.HTTPError):
        codigo = getattr(getattr(e, "response", None), "status_code", None)
        return codigo is None or codigo >= 500 or codigo == 429
    return isinstance(e, (requests.exceptions.ConnectionError, requests.exceptions.Timeout,
                          ConnectionError, TimeoutError, OSError))


# Peticiones ya existentes en el CDS (en cola, en proceso o terminadas) que se pueden retomar.
_INDICE_CDS = {}
_INDICE_LOCK = threading.Lock()


def _lista(v):
    return sorted(str(x) for x in (v if isinstance(v, (list, tuple)) else [v]))


def _clave(dataset, peticion):
    partes = [dataset]
    for k in sorted(peticion):
        if k in ("data_format", "download_format"):
            continue
        v = peticion[k]
        if k == "area":
            partes.append(f"area={','.join(f'{float(x):.4f}' for x in v)}")
        else:
            partes.append(f"{k}={'|'.join(_lista(v))}")
    return ";".join(partes)


def indexar_cds(limite=200):
    """Lista las peticiones recientes de la cuenta en el CDS que se pueden retomar."""
    try:
        c = _cliente()
        ids = c.get_jobs(limit=limite, sortby="-created",
                         status=["accepted", "running", "successful"]).request_ids
        nuevos = {}
        for rid in ids:
            r = c.get_remote(rid)
            nuevos.setdefault(_clave(r.collection_id, r.request), (rid, r.status))
    except Exception as e:                                          # noqa: BLE001
        log.warning(f"No se pudo listar las peticiones del CDS (se pedirán de nuevo): {e!r}")
        return 0
    with _INDICE_LOCK:
        _INDICE_CDS.clear()
        _INDICE_CDS.update(nuevos)
    estados = {}
    for _, st in nuevos.values():
        estados[st] = estados.get(st, 0) + 1
    log.info(f"CDS: {len(nuevos)} peticiones retomables en la cuenta {estados}")
    return len(nuevos)


def _retomar(dataset, peticion):
    with _INDICE_LOCK:
        hit = _INDICE_CDS.pop(_clave(dataset, peticion), None)
    return hit[0] if hit else None


def _esperar(rid, etiqueta, destino):
    """Sigue la petición `rid` hasta que termina y la descarga en `destino`. Aguanta cortes
    de red de horas sin reenviarla (no se pierde el puesto en la cola)."""
    t0, espera, red_caida = time.time(), CDS_SONDEO_S[0], None
    while time.time() - t0 < CDS_ESPERA_MAX_H * 3600:
        try:
            r = _cliente().get_remote(rid)
            st = r.status
            if red_caida:
                log.info(f"ERA5 {etiqueta}: red recuperada tras {(time.time() - red_caida) / 60:.0f} "
                         f"min; la petición sigue en el CDS ({st})")
                red_caida = None
            if st == "successful":
                r.download(destino)
                return destino
            if st in ("failed", "rejected", "dismissed", "deleted"):
                try:
                    r.get_results()
                    msg = st
                except Exception as e:                              # noqa: BLE001
                    msg = str(e)
                error = _clasificar(Exception(msg), etiqueta)
                raise error or TrabajoFallido(f"{etiqueta}: el CDS la dio por {st}: {msg[:300]}")
        except (SinLicencia, DemasiadoGrande, TrabajoFallido):
            raise
        except Exception as e:                                      # noqa: BLE001
            if not _es_de_red(e):
                error = _clasificar(e, etiqueta)
                if error:
                    raise error from e
                codigo = getattr(getattr(e, "response", None), "status_code", None)
                if codigo == 404:
                    raise TrabajoFallido(f"{etiqueta}: la petición {rid[:8]} ya no existe en el "
                                         f"CDS; se reenvía") from e
                raise
            if red_caida is None:
                red_caida = time.time()
                log.warning(f"ERA5 {etiqueta}: sin red ({type(e).__name__}); se sigue esperando "
                            f"la MISMA petición {rid[:8]}")
        time.sleep(espera)
        espera = min(espera * 1.5, CDS_SONDEO_S[1])
    raise TrabajoFallido(f"{etiqueta}: más de {CDS_ESPERA_MAX_H} h sin terminar")


def _abrir(path):
    """netCDF del CDS: .nc directo o .zip con varios .nc (instantáneas + acumuladas)."""
    import zipfile
    import xarray as xr
    with open(path, "rb") as fh:
        firma = fh.read(2)
    if firma != b"PK":
        return xr.open_dataset(path)
    destino = tempfile.mkdtemp(prefix="cdszip_")
    dss = []
    with zipfile.ZipFile(path) as z:
        for n in z.namelist():
            if n.lower().endswith(".nc"):
                z.extract(n, destino)
                dss.append(xr.open_dataset(Path(destino) / n))
    if not dss:
        raise ValueError("el .zip del CDS no contiene ningún .nc")
    return dss[0] if len(dss) == 1 else xr.merge(dss, compat="override", join="outer")


def _pedir(dataset, peticion, etiqueta, intentos=5):
    """Consigue el fichero de una petición: retoma una idéntica que ya esté en el CDS o la
    envía, y la sigue hasta descargarla. Solo REENVÍA si el CDS la da por fallida."""
    tmp = tempfile.NamedTemporaryFile(suffix=".bin", delete=False)
    tmp.close()
    rid = _retomar(dataset, peticion)
    if rid:
        log.info(f"ERA5 {etiqueta}: se retoma la petición {rid[:8]} que ya estaba en el CDS")
    for k in range(intentos):
        try:
            t0 = time.time()
            if rid is None:
                rid = _cliente().submit(dataset, peticion).request_id
                log.debug(f"ERA5 {etiqueta}: enviada al CDS ({rid[:8]})")
            _esperar(rid, etiqueta, tmp.name)
            log.debug(f"ERA5 {etiqueta}: descargada en {time.time() - t0:.0f} s")
            return tmp.name
        except (SinLicencia, DemasiadoGrande):
            Path(tmp.name).unlink(missing_ok=True)
            raise
        except Exception as e:                                      # noqa: BLE001
            error = _clasificar(e, etiqueta)
            if error:
                Path(tmp.name).unlink(missing_ok=True)
                raise error from e
            if k == intentos - 1:
                Path(tmp.name).unlink(missing_ok=True)
                raise RuntimeError(f"ERA5 {etiqueta}: agotados {intentos} intentos: {e!r}") from e
            espera = 60 * (k + 1)
            log.warning(f"ERA5 {etiqueta}: intento {k + 1}/{intentos} fallido, se reenvía en "
                        f"{espera} s ({e!r})")
            rid = None                                   # solo aquí se reenvía la petición
            time.sleep(espera)


def _caja(lat, lon):
    d = CAJA_GRADOS
    return [lat + d, lon - d, lat - d, lon + d]                     # N, O, S, E


def dir_era5(lat, lon):
    return config.DIR_METEO / "era5" / f"{lat:.3f}_{lon:.3f}"


# ── invariantes: qué celda de ERA5 representa a la planta ────────────────────────────────
def punto_era5(lat, lon):
    """Celda ERA5 más cercana: su lat/lon, máscara tierra-mar y cota del modelo. Se guarda en
    punto.json. En la costa la celda puede ser mar (guía 02, arranque §2.2): se avisa."""
    f = dir_era5(lat, lon) / "punto.json"
    if f.is_file():
        return json.loads(f.read_text(encoding="utf-8"))
    pet = {"product_type": ["reanalysis"], "variable": ["land_sea_mask", "geopotential"],
           "year": "2021", "month": "01", "day": "01", "time": "00:00",
           "area": _caja(lat, lon), "data_format": "netcdf", "download_format": "unarchived"}
    ruta = _pedir(ERA5_SFC, pet, "invariantes")
    try:
        ds = _abrir(ruta)
        latc = "latitude" if "latitude" in ds.coords else "lat"
        lonc = "longitude" if "longitude" in ds.coords else "lon"
        pt = ds.sel({latc: lat, lonc: lon}, method="nearest").squeeze()
        from teodors.planta import geo
        la, lo = float(pt[latc]), float(pt[lonc])
        d, rumbo = geo.distancia_rumbo(lat, lon, la, lo)
        info = {"lat": la, "lon": lo, "lsm": float(pt["lsm"]), "cota_modelo_m": float(pt["z"]) / G0,
                "dist_planta_m": d, "rumbo_desde_planta": rumbo,
                "celdas_en_peticion": {latc: [float(v) for v in np.atleast_1d(ds[latc].values)],
                                       lonc: [float(v) for v in np.atleast_1d(ds[lonc].values)]}}
        ds.close()
    finally:
        Path(ruta).unlink(missing_ok=True)
    f.parent.mkdir(parents=True, exist_ok=True)
    f.write_text(json.dumps(info, ensure_ascii=False, indent=2), encoding="utf-8")
    return info


# ── superficie (mes a mes) ───────────────────────────────────────────────────────────────
def _convertir_sfc(df):
    df = df.copy()
    for k in ("t2m", "d2m"):
        df[k] = df[k] - 273.15                                     # K → °C
    df["sp"] = df["sp"] / 100.0                                    # Pa → hPa
    df["tp"] = df["tp"] * 1000.0                                   # m → mm/h
    for k in ("ssrd", "sshf"):
        df[k] = df[k] / 3600.0                                     # J/m² (1 h) → W/m²
    df["wspd"] = np.hypot(df["u10"], df["v10"])
    df["wdir"] = (270.0 - np.degrees(np.arctan2(df["v10"], df["u10"]))) % 360.0
    return df


def mes_sfc(lat, lon, anio, mes):
    """Un mes de superficie ya convertido (CSV en caché; si existe, no consulta el CDS)."""
    f = dir_era5(lat, lon) / f"sfc_{anio}{mes:02d}.csv"
    if f.is_file():
        return f
    pet = {"product_type": ["reanalysis"], "variable": list(VARS_SFC),
           "year": str(anio), "month": f"{mes:02d}",
           "day": [f"{d:02d}" for d in range(1, calendar.monthrange(anio, mes)[1] + 1)],
           "time": [f"{h:02d}:00" for h in range(24)], "area": _caja(lat, lon),
           "data_format": "netcdf", "download_format": "unarchived"}
    ruta = _pedir(ERA5_SFC, pet, f"superficie {anio}-{mes:02d}")
    try:
        ds = _abrir(ruta)
        latc = "latitude" if "latitude" in ds.coords else "lat"
        lonc = "longitude" if "longitude" in ds.coords else "lon"
        pt = ds.sel({latc: lat, lonc: lon}, method="nearest").squeeze()
        tc = "valid_time" if "valid_time" in pt.coords else "time"
        datos = {"time": pd.to_datetime(np.asarray(pt[tc].values).ravel())}
        faltan = [c for c in VARS_SFC.values() if c not in pt]
        if faltan:
            raise ValueError(f"faltan variables en el netCDF: {faltan}")
        for c in VARS_SFC.values():
            datos[c] = np.asarray(pt[c].values, dtype="float64").ravel()
        ds.close()
    finally:
        Path(ruta).unlink(missing_ok=True)
    df = _convertir_sfc(pd.DataFrame(datos)).sort_values("time")
    n_esp = calendar.monthrange(anio, mes)[1] * 24
    if len(df) != n_esp:
        log.warning(f"ERA5 superficie {anio}-{mes:02d}: {len(df)} horas de {n_esp}")
    tmp = f.with_suffix(".tmp")
    df.to_csv(tmp, index=False)
    tmp.replace(f)
    return f


# ── superficie por SERIE TEMPORAL (rápida) + u* por años ────────────────────────────────
# Medido el 2026-10-15: el dataset «ERA5 time-series» de un punto entrega los 5 años de
# superficie (43 824 h) en ~80 s, frente a 10 min-4 h POR MES en la cola normal, y sus valores
# coinciden con los mensuales (|Δ| ≤ 0,0003 °C). No trae u* (friction_velocity): se pide aparte
# por años en el dataset normal. Su perfil, en cambio, es 6-horario y sin 975/950/900 hPa: el
# perfil sigue saliendo de la cola por quincenas.
ERA5_SFC_SERIE = "reanalysis-era5-single-levels-timeseries"
VARS_SFC_SERIE = [v for v in VARS_SFC if v != "friction_velocity"]


def serie_sfc(lat, lon, anios):
    """Superficie de todos los años en UNA petición (unidades originales, sin u*)."""
    f = dir_era5(lat, lon) / f"serie_sfc_{anios[0]}_{anios[-1]}.csv"
    if f.is_file():
        return pd.read_csv(f, parse_dates=["time"])
    celda = punto_era5(lat, lon)
    caja = [celda["lat"] + 0.1, celda["lon"] - 0.1, celda["lat"] - 0.1, celda["lon"] + 0.1]
    pet = {"variable": VARS_SFC_SERIE, "area": caja, "data_format": "netcdf",
           "date": f"{anios[0]}-01-01/{anios[-1]}-12-31"}
    ruta = _pedir(ERA5_SFC_SERIE, pet, f"serie de superficie {anios[0]}-{anios[-1]}")
    try:
        ds = _abrir(ruta)
        tc = "valid_time" if "valid_time" in ds.coords else "time"
        pt = ds.sel(latitude=celda["lat"], longitude=celda["lon"], method="nearest") \
            if "latitude" in ds.dims else ds
        datos = {"time": pd.to_datetime(np.asarray(pt[tc].values).ravel())}
        for c in (VARS_SFC[v] for v in VARS_SFC_SERIE):
            datos[c] = np.asarray(pt[c].values, dtype="float64").ravel()
        ds.close()
    finally:
        Path(ruta).unlink(missing_ok=True)
    df = pd.DataFrame(datos).sort_values("time")
    tmp = f.with_suffix(".tmp")
    df.to_csv(tmp, index=False)
    tmp.replace(f)
    return df


def anio_zust(lat, lon, anio, trozos=1):
    """u* (friction_velocity) de un año en el dataset normal. Si el CDS lo rechaza por
    tamaño, se trocea en 2, 4 y 12 partes."""
    f = dir_era5(lat, lon) / f"zust_{anio}.csv"
    if f.is_file():
        return f
    try:
        partes = []
        for meses in np.array_split(np.arange(1, 13), trozos):
            pet = {"product_type": ["reanalysis"], "variable": ["friction_velocity"],
                   "year": str(anio), "month": [f"{m:02d}" for m in meses],
                   "day": [f"{d:02d}" for d in range(1, 32)],
                   "time": [f"{h:02d}:00" for h in range(24)], "area": _caja(lat, lon),
                   "data_format": "netcdf", "download_format": "unarchived"}
            ruta = _pedir(ERA5_SFC, pet, f"u* {anio} meses {meses[0]}-{meses[-1]}")
            try:
                ds = _abrir(ruta)
                latc = "latitude" if "latitude" in ds.coords else "lat"
                lonc = "longitude" if "longitude" in ds.coords else "lon"
                pt = ds.sel({latc: lat, lonc: lon}, method="nearest").squeeze()
                tc = "valid_time" if "valid_time" in pt.coords else "time"
                partes.append(pd.DataFrame({
                    "time": pd.to_datetime(np.asarray(pt[tc].values).ravel()),
                    "zust": np.asarray(pt["zust"].values, dtype="float64").ravel()}))
                ds.close()
            finally:
                Path(ruta).unlink(missing_ok=True)
    except DemasiadoGrande:
        siguiente = {1: 2, 2: 4, 4: 12}.get(trozos)
        if siguiente is None:
            raise
        log.warning(f"ERA5 u* {anio}: el CDS lo rechaza por tamaño; se pide en {siguiente} partes")
        return anio_zust(lat, lon, anio, siguiente)
    df = pd.concat(partes, ignore_index=True).dropna().sort_values("time")
    n_esp = (366 if calendar.isleap(anio) else 365) * 24
    if len(df) != n_esp:
        log.warning(f"ERA5 u* {anio}: {len(df)} horas de {n_esp}")
    tmp = f.with_suffix(".tmp")
    df.to_csv(tmp, index=False)
    tmp.replace(f)
    return f


def construir_sfc_anio(lat, lon, anio, serie):
    """Escribe los sfc_AAAAMM.csv que falten del año uniendo la serie y u*."""
    zust = pd.read_csv(dir_era5(lat, lon) / f"zust_{anio}.csv", parse_dates=["time"])
    df = serie[serie.time.dt.year == anio].merge(zust, on="time", how="left")
    if df["zust"].isna().any():
        log.warning(f"ERA5 {anio}: {int(df['zust'].isna().sum())} horas sin u*")
    df = _convertir_sfc(df)[["time", *VARS_SFC.values(), "wspd", "wdir"]]
    for mes, grupo in df.groupby(df.time.dt.month):
        f = dir_era5(lat, lon) / f"sfc_{anio}{mes:02d}.csv"
        if not f.is_file():
            tmp = f.with_suffix(".tmp")
            grupo.to_csv(tmp, index=False)
            tmp.replace(f)


# ── perfil vertical (por quincenas) ──────────────────────────────────────────────────────
def _quincena_pfl(lat, lon, anio, mes, dias):
    pet = {"product_type": ["reanalysis"], "variable": list(VARS_PFL),
           "pressure_level": NIVELES_PFL, "year": str(anio), "month": f"{mes:02d}",
           "day": [f"{d:02d}" for d in dias], "time": [f"{h:02d}:00" for h in range(24)],
           "area": _caja(lat, lon), "data_format": "netcdf", "download_format": "unarchived"}
    ruta = _pedir(ERA5_PL, pet, f"perfil {anio}-{mes:02d} d{dias[0]:02d}-{dias[-1]:02d}")
    try:
        ds = _abrir(ruta)
        latc = "latitude" if "latitude" in ds.coords else "lat"
        lonc = "longitude" if "longitude" in ds.coords else "lon"
        pt = ds.sel({latc: lat, lonc: lon}, method="nearest")
        tc = "valid_time" if "valid_time" in pt.coords else "time"
        nc = "pressure_level" if "pressure_level" in pt.coords else "level"
        df = (pt[list(VARS_PFL.values())].to_dataframe().reset_index()
              .rename(columns={tc: "time", nc: "level"}))
        ds.close()
    finally:
        Path(ruta).unlink(missing_ok=True)
    df["height_asl_m"] = df["z"] / G0
    df["temp_c"] = df["t"] - 273.15
    df["wspd"] = np.hypot(df["u"], df["v"])
    from teodors.planta import geo
    df["wdir"] = geo.direccion(df["u"], df["v"])
    return df[["time", "level", "height_asl_m", "wdir", "wspd", "temp_c"]]


def quincena_pfl(lat, lon, anio, mes, q):
    """Media mes de perfil (q = 1: días 1-15; q = 2: del 16 al final). Cada quincena es una
    tarea y un CSV propio: así las dos peticiones en paralelo nunca esperan la una a la otra."""
    f = dir_era5(lat, lon) / f"pfl_{anio}{mes:02d}_{q}.csv"
    if f.is_file():
        return f
    ultimo = calendar.monthrange(anio, mes)[1]
    dias = list(range(1, 16)) if q == 1 else list(range(16, ultimo + 1))
    df = _quincena_pfl(lat, lon, anio, mes, dias).sort_values(["time", "level"],
                                                               ascending=[True, False])
    n_esp = len(dias) * 24 * len(NIVELES_PFL)
    if len(df) != n_esp:
        log.warning(f"ERA5 perfil {anio}-{mes:02d} q{q}: {len(df)} filas de {n_esp}")
    tmp = f.with_suffix(".tmp")
    df.to_csv(tmp, index=False)
    tmp.replace(f)
    return f


# ── cola completa ────────────────────────────────────────────────────────────────────────
def descargar_reanalisis(lat, lon, anios=None, hilos=2, progreso=None):
    """Descarga (o completa) superficie y perfil de los años pedidos. Reanudable: lo que ya
    está en caché no se vuelve a pedir. Devuelve un resumen {hechos, fallidos}."""
    anios = config.REANALISIS_ANIOS if anios is None else anios
    info = punto_era5(lat, lon)
    log.info(f"ERA5: celda {info['lat']:.2f} N, {info['lon']:.2f} E · tierra-mar "
             f"{info['lsm']:.2f} · cota del modelo {info['cota_modelo_m']:.0f} m · a "
             f"{info['dist_planta_m'] / 1000:.1f} km al {info['rumbo_desde_planta']} de la planta")
    if info["lsm"] < 0.5:
        log.warning("La celda ERA5 más cercana es MAR: revisar (guía 02 y arranque §2.2).")
    d = dir_era5(lat, lon)
    indexar_cds()               # retomar lo que ya esté en la cola del CDS o terminado sin bajar

    # 1) Superficie: serie temporal (todos los años en una petición). Si falla, mes a mes.
    serie = None
    falta_sfc = [(a, m) for a in anios for m in range(1, 13)
                 if not (d / f"sfc_{a}{m:02d}.csv").is_file()]
    if falta_sfc:
        try:
            t0 = time.time()
            serie = serie_sfc(lat, lon, anios)
            log.info(f"ERA5 superficie {anios[0]}–{anios[-1]} por serie temporal: "
                     f"{len(serie)} horas en {time.time() - t0:.0f} s (falta u*, va por años)")
        except SinLicencia:
            raise
        except Exception as e:                                      # noqa: BLE001
            log.warning(f"La serie temporal falló ({e}); la superficie irá mes a mes.")

    # 2) Cola: u* por años (o superficie por meses si no hubo serie) y perfil por quincenas
    tareas = []
    for a in anios:
        if serie is not None:
            if any(fa == a for fa, _ in falta_sfc):
                tareas.append(("zust", a, 0, 0))
        else:
            tareas += [("sfc", a, m, 0) for fa, m in falta_sfc if fa == a]
        tareas += [("pfl", a, m, q) for m in range(1, 13) for q in (1, 2)
                   if not (d / f"pfl_{a}{m:02d}_{q}.csv").is_file()]

    def lanzar(t, a, m, q):
        if t == "zust":
            anio_zust(lat, lon, a)
            construir_sfc_anio(lat, lon, a, serie)
        elif t == "sfc":
            mes_sfc(lat, lon, a, m)
        else:
            quincena_pfl(lat, lon, a, m, q)

    def nombre(t, a, m, q):
        return {"zust": f"u* y superficie {a}", "sfc": f"superficie {a}-{m:02d}",
                "pfl": f"perfil {a}-{m:02d} q{q}"}[t]

    log.info(f"ERA5 cola: {len(tareas)} peticiones pendientes "
             f"({sum(t[0] == 'zust' for t in tareas)} de u* por año, "
             f"{sum(t[0] == 'sfc' for t in tareas)} de superficie por mes, "
             f"{sum(t[0] == 'pfl' for t in tareas)} de perfil por quincena) · {hilos} a la vez")
    pendientes = sorted(tareas, key=lambda t: t[0] != "zust")      # u* primero
    hechos, fallidos, t0 = 0, [], time.time()
    with ThreadPoolExecutor(max_workers=hilos) as ex:
        futuros = {ex.submit(lanzar, *t): t for t in pendientes}
        for fu in as_completed(futuros):
            tipo, a, m, q = futuros[fu]
            try:
                fu.result()
                hechos += 1
                resto = (len(tareas) - hechos) * (time.time() - t0) / hechos / 3600
                log.info(f"ERA5 {nombre(tipo, a, m, q)} listo · {hechos}/{len(tareas)} · "
                         f"quedan ≈ {resto:.1f} h")
            except SinLicencia as e:
                log.error(f"El CDS rechaza la petición por licencia/permisos: {e}. Acepta la "
                          f"licencia de «ERA5 single levels» y «ERA5 pressure levels» en la "
                          f"web del CDS con esta cuenta.")
                for f in futuros:
                    f.cancel()
                raise
            except Exception as e:                                  # noqa: BLE001
                fallidos.append((tipo, a, m, q))
                log.error(f"ERA5 {nombre(tipo, a, m, q)}: {e}")
            if progreso:
                progreso(hechos, len(tareas))
    log.info(f"ERA5: {hechos}/{len(tareas)} peticiones completas"
             + (f" · fallidas: {fallidos} (relanzar para completarlas)" if fallidos else ""))
    return {"hechos": hechos, "total": len(tareas), "fallidos": fallidos}


def cargar_sfc(lat, lon, anios=None):
    """Serie horaria de superficie de los años pedidos (solo los meses ya descargados)."""
    anios = config.REANALISIS_ANIOS if anios is None else anios
    fs = sorted(f for a in anios for f in dir_era5(lat, lon).glob(f"sfc_{a}??.csv"))
    if not fs:
        return pd.DataFrame()
    return pd.concat((pd.read_csv(f, parse_dates=["time"]) for f in fs), ignore_index=True)


def cargar_pfl(lat, lon, anios=None):
    anios = config.REANALISIS_ANIOS if anios is None else anios
    fs = sorted(f for a in anios for f in dir_era5(lat, lon).glob(f"pfl_{a}??_?.csv"))
    if not fs:
        return pd.DataFrame()
    return (pd.concat((pd.read_csv(f, parse_dates=["time"]) for f in fs), ignore_index=True)
            .sort_values(["time", "level"], ascending=[True, False]).reset_index(drop=True))
