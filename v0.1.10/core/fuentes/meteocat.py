# -*- coding: utf-8 -*-
"""Estaciones meteorológicas de Meteocat (red XEMA) cerca de la planta.

Datos ABIERTOS y sin clave en el portal de transparencia de la Generalitat (Socrata):
  · inventario de estaciones:  analisi.transparenciacatalunya.cat/resource/yqwd-vj5e
  · lecturas semihorarias:     analisi.transparenciacatalunya.cat/resource/nzvn-apee
Comprobado el 2026-10-15: desde 2009 hasta ~2 h antes de ahora; sirven para validar ERA5 y
para el horizonte «presente». Hora en UTC con la etiqueta de INICIO del intervalo (se comprobó con
el ciclo de la radiación); aquí se guarda tal cual: quien la promedia tiene que saberlo.
⚠️ Medido el 2026-11-01: las lecturas acababan el 26/10 a las 17:30. No siempre llegan a 2 h de ahora.

Caché (reanudable): DATOS/meteo/meteocat/<código>/<año>.csv, una fila cada 30 min:
  time, ws, wd (viento a la altura del anemómetro), t, rh, p, pr, rad + altura_viento_m
"""
import json
import math
import time
import urllib.parse
import urllib.request

import pandas as pd

from teodors import planta as config
from teodors.comun import registro

log = registro.get("estaciones")

URL_INVENTARIO = "https://analisi.transparenciacatalunya.cat/resource/yqwd-vj5e.json"
URL_LECTURAS = "https://analisi.transparenciacatalunya.cat/resource/nzvn-apee.json"
PAGINA = 50000
ESTADO_OPERATIVA = "2"
FUENTE = "las estaciones del Servei Meteorològic de Catalunya (Meteocat, red XEMA), datos abiertos"   # para citarla

# Códigos de variable XEMA -> columna. El viento puede estar a 10, 6 o 2 m según la estación.
VIENTO = {10: ("30", "31"), 6: ("48", "49"), 2: ("46", "47")}     # (velocidad, dirección)
OTRAS = {"32": "t", "33": "rh", "34": "p", "35": "pr", "36": "rad"}


def _get(url, params, intentos=4):
    q = url + "?" + urllib.parse.urlencode(params, safe="(),'$:")
    for k in range(intentos):
        try:
            req = urllib.request.Request(q, headers={"User-Agent": config.bloque("estaciones").get("agente_http", config.AGENTE_HTTP)})
            with urllib.request.urlopen(req, timeout=180) as r:
                return json.loads(r.read().decode("utf-8"))
        except Exception as e:                                      # noqa: BLE001
            if k == intentos - 1:
                raise RuntimeError(f"Meteocat no responde: {e!r}") from e
            log.debug(f"Meteocat: reintento {k + 1} ({e!r})")
            time.sleep(5 * (k + 1))


def dir_meteocat():
    return config.DIR_METEO / "meteocat"


def inventario(forzar=False):
    """Todas las estaciones XEMA (se guarda en caché). Sin la caché, las de la zona que trae la planta con su meteo procesada
    (`planta.DIR_METEO_PLANTA/estaciones.json`, de `operacion.meteo_planta`): no se pide a la red lo que la planta ya trae."""
    f = dir_meteocat() / "estaciones.json"
    if f.is_file() and not forzar:
        return json.loads(f.read_text(encoding="utf-8"))
    de_la_planta = None if forzar else config.meteo_procesada("estaciones.json")
    if de_la_planta:
        return de_la_planta
    datos = _get(URL_INVENTARIO, {"$limit": 5000})
    f.parent.mkdir(parents=True, exist_ok=True)
    f.write_text(json.dumps(datos, ensure_ascii=False, indent=1), encoding="utf-8")
    return datos


def cercanas(lat, lon, radio_km=None, solo_operativas=True):
    """Estaciones a menos de `radio_km` (por defecto, el del bloque `estaciones` de la planta), ordenadas por distancia (con
    distancia y rumbo)."""
    radio_km = config.pide("estaciones", "radio_km") if radio_km is None else radio_km
    from teodors.planta import geo
    salida = []
    for e in inventario():
        try:
            la, lo = float(e["latitud"]), float(e["longitud"])
        except (KeyError, TypeError, ValueError):
            continue
        if solo_operativas and str(e.get("codi_estat_ema")) != ESTADO_OPERATIVA:
            continue
        d, rumbo = geo.distancia_rumbo(lat, lon, la, lo)
        if d <= radio_km * 1000:
            salida.append({"codigo": e["codi_estacio"], "nombre": e["nom_estacio"],
                           "lat": la, "lon": lo, "altitud_m": float(e.get("altitud") or "nan"),
                           "municipio": e.get("nom_municipi"), "dist_m": d, "rumbo": rumbo})
    return sorted(salida, key=lambda s: s["dist_m"])


def _lecturas(codigo, desde, hasta, variables):
    """Lecturas crudas (largas) de una estación entre dos fechas ISO, paginando."""
    filas, desplaz = [], 0
    lista = ",".join(f"'{v}'" for v in variables)
    while True:
        pagina = _get(URL_LECTURAS, {
            "$select": "data_lectura,codi_variable,valor_lectura",
            "$where": (f"codi_estacio='{codigo}' and codi_variable in({lista}) and "
                       f"data_lectura between '{desde}' and '{hasta}'"),
            "$order": "data_lectura,codi_variable", "$limit": PAGINA, "$offset": desplaz})
        filas += pagina
        if len(pagina) < PAGINA:
            return filas
        desplaz += PAGINA


def altura_viento(codigo):
    """Altura del anemómetro (10, 6 o 2 m) mirando qué variable de viento publica."""
    for h, (vel, _) in VIENTO.items():
        hay = _get(URL_LECTURAS, {"$select": "count(valor_lectura) as n",
                                  "$where": f"codi_estacio='{codigo}' and codi_variable='{vel}' "
                                            f"and data_lectura > '{config.REANALISIS_ANIOS[0]}-01-01T00:00:00'"})
        if hay and int(hay[0].get("n", 0)) > 0:
            return h
    return None


def anio_estacion(codigo, anio):
    """Un año de una estación en la caché (si existe, no consulta)."""
    f = dir_meteocat() / codigo / f"{anio}.csv"
    if f.is_file():
        return f
    h = altura_viento(codigo)
    variables = list(OTRAS) + (list(VIENTO[h]) if h else [])
    # Mes a mes: la consulta de un año entero (~120 mil lecturas) agotaba el tiempo de
    # respuesta del portal (medido el 2026-10-15).
    crudo = []
    for mes in range(1, 13):
        fin = pd.Timestamp(anio, mes, 1) + pd.offsets.MonthEnd(1)
        crudo += _lecturas(codigo, f"{anio}-{mes:02d}-01T00:00:00",
                           f"{fin:%Y-%m-%d}T23:59:59", variables)
    if not crudo:
        log.warning(f"Meteocat {codigo} {anio}: sin lecturas")
        return None
    df = pd.DataFrame(crudo)
    df["time"] = pd.to_datetime(df["data_lectura"])
    df["valor"] = pd.to_numeric(df["valor_lectura"], errors="coerce")
    nombres = dict(OTRAS)
    if h:
        nombres.update({VIENTO[h][0]: "ws", VIENTO[h][1]: "wd"})
    df["col"] = df["codi_variable"].map(nombres)
    ancho = df.pivot_table(index="time", columns="col", values="valor", aggfunc="first")
    ancho = ancho.reindex(columns=["ws", "wd", "t", "rh", "p", "pr", "rad"]).reset_index()
    ancho["altura_viento_m"] = h
    f.parent.mkdir(parents=True, exist_ok=True)
    tmp = f.with_suffix(".tmp")
    ancho.to_csv(tmp, index=False)
    tmp.replace(f)
    return f


def estaciones_dias(est, ini, fin):
    """Medidas semihorarias de [ini, fin] de cada estación → DIR_METEO/meteocat/<cod>/<año>.csv (mismo formato que
    anio_estacion), SUMADAS a lo que ya hubiera: en DATOS está el año entero. Devuelve {código: altura}."""
    alturas = {}
    for e in est:
        h = altura_viento(e["codigo"])
        variables = list(OTRAS) + (list(VIENTO[h]) if h else [])
        crudo = _lecturas(e["codigo"], f"{ini:%Y-%m-%dT%H:%M:%S}",
                                     f"{fin:%Y-%m-%dT%H:%M:%S}", variables)
        df = pd.DataFrame(crudo)
        df["time"] = pd.to_datetime(df["data_lectura"])
        df["valor"] = pd.to_numeric(df["valor_lectura"], errors="coerce")
        nombres = dict(OTRAS)
        if h:
            nombres.update({VIENTO[h][0]: "ws", VIENTO[h][1]: "wd"})
        df["col"] = df["codi_variable"].map(nombres)
        ancho = df.pivot_table(index="time", columns="col", values="valor", aggfunc="first")
        ancho = ancho.reindex(columns=["ws", "wd", "t", "rh", "p", "pr", "rad"]).reset_index()
        ancho["altura_viento_m"] = h
        for anio, g in ancho.groupby(ancho["time"].dt.year):
            f = dir_meteocat() / e["codigo"] / f"{anio}.csv"
            f.parent.mkdir(parents=True, exist_ok=True)
            if f.is_file():
                g = pd.concat([pd.read_csv(f, parse_dates=["time"]), g]).drop_duplicates("time", keep="last").sort_values("time")
            g.to_csv(f, index=False)
        alturas[e["codigo"]] = float(h or 10.0)
        print(f"   {e['codigo']} {e['nombre']}: {len(ancho)} medidas · anemómetro {h} m", flush=True)
    return alturas


def descargar(lat, lon, anios=None, radio_km=None):
    """Descarga (o completa) los años pedidos de todas las estaciones operativas cercanas."""
    anios = config.REANALISIS_ANIOS if anios is None else anios
    radio_km = config.pide("estaciones", "radio_km") if radio_km is None else radio_km
    est = cercanas(lat, lon, radio_km)
    log.info(f"Meteocat: {len(est)} estaciones operativas a menos de {radio_km:g} km: "
             + ", ".join(f"{e['nombre']} ({e['dist_m'] / 1000:.1f} km)" for e in est))
    fallidos = []
    for e in est:
        for a in anios:
            t0 = time.time()
            try:
                f = anio_estacion(e["codigo"], a)
            except Exception as ex:                                 # noqa: BLE001
                fallidos.append((e["codigo"], a))
                log.error(f"Meteocat {e['codigo']} {e['nombre']} {a}: {ex} (se sigue; "
                          f"relanzar para completarlo)")
                continue
            if f is not None:
                log.info(f"Meteocat {e['codigo']} {e['nombre']} {a}: listo "
                         f"({time.time() - t0:.0f} s)")
    if fallidos:
        log.warning(f"Meteocat: quedan por bajar {fallidos}")
    return est


def cargar(codigo, anios=None):
    anios = config.REANALISIS_ANIOS if anios is None else anios
    fs = [dir_meteocat() / codigo / f"{a}.csv" for a in anios]
    fs = [f for f in fs if f.is_file()]
    if not fs:
        return pd.DataFrame()
    return pd.concat((pd.read_csv(f, parse_dates=["time"]) for f in fs), ignore_index=True)


def a_10m(ws, altura_m, z0_m=0.1):
    """Velocidad llevada a 10 m con la ley logarítmica neutra (aproximación: z0 típico de
    cultivos y frutales; no corrige la estabilidad)."""
    if altura_m is None or altura_m >= 10:
        return ws
    return ws * math.log(10.0 / z0_m) / math.log(altura_m / z0_m)


def para_mapa(lat, lon, radio_km=None):
    """Estaciones cercanas con lo que se sabe de ellas SIN consultar la red (inventario y
    lecturas de la caché, validación de ERA5 si ya se hizo). Lista vacía si aún no hay
    inventario en la caché (la app no debe colgarse al arrancar sin conexión)."""
    if not (dir_meteocat() / "estaciones.json").is_file() and not (config.DIR_METEO_PLANTA / "estaciones.json").is_file():
        return []
    val = {}
    f_val = config.DIR_METEO / "validacion" / "era5_vs_meteocat.json"
    if f_val.is_file():
        try:
            val = {e["codigo"]: e for e in
                   json.loads(f_val.read_text(encoding="utf-8"))["estaciones"]}
        except (ValueError, KeyError):
            log.warning(f"Validación ERA5 ilegible: {f_val}")
    salida = []
    for e in cercanas(lat, lon, radio_km):
        d = dir_meteocat() / e["codigo"]
        anios = sorted(int(f.stem) for f in d.glob("*.csv") if f.stem.isdigit())
        altura = None
        if anios:
            h = pd.read_csv(d / f"{anios[-1]}.csv", usecols=["altura_viento_m"], nrows=1)
            if len(h) and pd.notna(h.iloc[0, 0]):
                altura = float(h.iloc[0, 0])
        v = val.get(e["codigo"], {})
        salida.append(e | {"altura_viento_m": altura, "anios": anios,
                           "era5_wd_error": v.get("wd_error"), "era5_ws_ioa": v.get("ws_ioa"),
                           "era5_t_error": v.get("t_error")})
    return salida
