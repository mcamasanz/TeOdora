# -*- coding: utf-8 -*-
"""Viento en superficie de una serie de viento 3D (nivel 1 de `meteo.viento3d`) preparado para la capa animada del mapa (partículas, líneas o flechas).

Se lee directamente del .cmz del mes (solo «U-LEV  1» y «V-LEV  1»), sin
reconstruir el fichero de viento. u y v van respecto a la CUADRÍCULA UTM (i = este, j = norte): la capa
del mapa los coloca con la geometría real de la rejilla en pantalla, así que no hace falta girar
por la convergencia de meridianos.

Las series son de la planta (`series` de planta.json): `era5`, `preferidas` y `titulos`.
"""
import base64
import json
from functools import lru_cache
from pathlib import Path

import numpy as np
import pandas as pd
from pyproj import Transformer

from teodors import planta as config
from teodors.comun import registro
from teodors.meteo.viento3d import almacen

log = registro.get("viento_mapa")

# Forma, color, escala y cantidad: se eligen en la configuración; las añade la interfaz.


def serie_defecto():
    """La serie de los años del reanálisis (`series.era5`)."""
    return config.pide("series", "era5")


def titulos():
    """{serie: su título en la leyenda} (`series.titulos`)."""
    return config.bloque("series").get("titulos", {})


def preferidas():
    """Las series en orden de preferencia: la app usa la primera que exista (`series.preferidas`)."""
    return tuple(config.bloque("series").get("preferidas", ()))


def _dir_serie(nombre):
    """Carpeta de una serie de viento 3D (config.DIR_VIENTO3D / nombre)."""
    return config.DIR_VIENTO3D / nombre


def serie_disponible():
    """La primera serie de `preferidas` con algún mes calculado (o None)."""
    return next((s for s in preferidas() if meses(s)), None)


def dia_inicial(serie):
    """Día con el que abrir el calendario: el que marque el caso.json del último mes
    («dias_completos», p. ej. en un caso de un solo día) o el 15 del primer mes."""
    m = meses(serie)
    if not m:
        return None
    a, mm = m[-1]
    f = _dir_serie(serie) / f"{a}{mm:02d}" / "caso.json"
    if f.is_file():
        dias = json.loads(f.read_text(encoding="utf-8")).get("dias_completos")
        if dias:
            return pd.Timestamp(dias[-1])
    return pd.Timestamp(m[0][0], m[0][1], 15)


def rango_dias(serie):
    """Primer y último día con viento (o None): de los meses con .cmz y, si su caso.json lo dice, de «dias_completos»."""
    m = meses(serie)
    if not m:
        return None

    def extremos(anio, mes):
        f = _dir_serie(serie) / f"{anio}{mes:02d}" / "caso.json"
        dias = json.loads(f.read_text(encoding="utf-8")).get("dias_completos") if f.is_file() else None
        if dias:
            return pd.Timestamp(dias[0]), pd.Timestamp(dias[-1])
        return pd.Timestamp(anio, mes, 1), pd.Timestamp(anio, mes, 1) + pd.offsets.MonthEnd(0)
    return extremos(*m[0])[0], extremos(*m[-1])[1]


VMAX = 8.0                 # m/s: tope de la escala de color
BIBLIOTECA = None          # otra biblioteca en vez de la de la planta, si se pone


def biblioteca():
    """Ruta de la biblioteca del viento local de la planta (`viento_local.biblioteca`, relativa a su carpeta); None si no tiene."""
    if BIBLIOTECA is not None:
        return Path(BIBLIOTECA)
    b = config.bloque("viento_local").get("biblioteca")
    return config.PLANTA / b if b else None


def meses(serie=None):
    """[(año, mes)] con .cmz en DATOS/viento3d/<serie>/cmz; por defecto, la serie del reanálisis."""
    serie = serie_defecto() if serie is None else serie
    d = _dir_serie(serie) / "cmz"
    return sorted((int(f.stem[:4]), int(f.stem[4:])) for f in d.glob("??????.cmz")) if d.is_dir() else []


def _fecha(f):
    """AAAAJJJHH (convención de viento3d: hora FINAL) → Timestamp UTC sin zona."""
    f = int(f)
    return (pd.Timestamp(f // 100000, 1, 1) + pd.Timedelta(days=(f // 100) % 1000 - 1)
            + pd.Timedelta(hours=f % 100))


@lru_cache(maxsize=2)
def _mes(serie, anio, mes):
    cmz = _dir_serie(serie) / "cmz" / f"{anio}{mes:02d}.cmz"
    fz, u = almacen.leer_campo(cmz, "U-LEV  1")
    _, v = almacen.leer_campo(cmz, "V-LEV  1")
    info = json.loads((_dir_serie(serie) / f"{anio}{mes:02d}" / "caso.json")
                      .read_text(encoding="utf-8"))
    horas = pd.DatetimeIndex([_fecha(x) for x in fz])
    return horas, u, v, info


@lru_cache(maxsize=1)
def _rejilla(nx, ny, x0, y0, dg):
    xs = x0 + (np.arange(nx) + 0.5) * dg
    ys = y0 + (np.arange(ny) + 0.5) * dg
    X, Y = np.meshgrid(xs, ys)                                 # fila j = norte, columna i = este
    lon, lat = Transformer.from_crs(config.EPSG_UTM, "EPSG:4326", always_xy=True).transform(X, Y)
    return lat.ravel(), lon.ravel()


def datos_dia(fecha, serie=None, cada=1, dias=1):
    """Viento del nivel 1 desde el día `fecha`, `dias` días (00 a 23 UTC y, si existe, las 00 del día siguiente
    para interpolar la última hora) en el formato de la capa del mapa. `cada` aclara la malla
    (1 = todas las celdas). Por defecto, la serie del reanálisis."""
    serie = serie_defecto() if serie is None else serie
    fecha = pd.Timestamp(fecha).normalize()
    horas, u, v, info = _mes(serie, fecha.year, fecha.month)
    sel = np.where((horas >= fecha) & (horas <= fecha + pd.Timedelta(hours=24 * dias)))[0]
    if not len(sel):
        raise ValueError(f"sin datos de {serie} el {fecha:%Y-%m-%d}")
    uu, vv = u[sel][:, ::cada, ::cada], v[sel][:, ::cada, ::cada]
    ny, nx = uu.shape[1:]
    dg = info["celda_m"] * cada
    x0 = info["ext"][0] + (cada - 1) * info["celda_m"] / 2
    y0 = info["ext"][2] + (cada - 1) * info["celda_m"] / 2
    lat, lon = _rejilla(nx, ny, x0, y0, dg)
    vel = np.hypot(uu, vv)
    # la capa solo necesita tres esquinas para colocar la rejilla en pantalla, y el viento va
    # en centésimas de m/s como int16 en base64 (~2 MB por día en vez de ~16 MB en texto)
    esq = {"c00": [lat[0], lon[0]], "c10": [lat[nx - 1], lon[nx - 1]],
           "c01": [lat[(ny - 1) * nx], lon[(ny - 1) * nx]]}
    b64 = lambda a: base64.b64encode(np.round(a.ravel() * 100).astype("<i2").tobytes()).decode()
    return {"nx": int(nx), "ny": int(ny), "dg": float(dg),
            "esquinas": {k: [round(float(a), 6), round(float(b), 6)] for k, (a, b) in esq.items()},
            "u": [b64(a) for a in uu], "v": [b64(a) for a in vv], "escala": 0.01,
            "pos": list(range(len(sel))), "clip": [0, nx - 1, 0, ny - 1], "vmax": VMAX,
            "horas": [f"{h:%Y-%m-%d %H:%M}" for h in horas[sel]],
            "media": [round(float(x), 2) for x in vel.mean(axis=(1, 2))],
            "maxima": [round(float(x), 1) for x in vel.max(axis=(1, 2))],
            "serie": serie, "titulo": titulos().get(serie, serie), "origen": [float(x0 + dg / 2), float(y0 + dg / 2)]}


@lru_cache(maxsize=1)
def datos_local():
    """La biblioteca del viento local de la planta (`meteo.viento_local.biblioteca`), para el mapa; None si no está."""
    ruta = biblioteca()
    if ruta is None or not ruta.is_file():
        return None
    with np.load(ruta) as z:
        b64 = lambda a: base64.b64encode(a.astype("<i2").tobytes()).decode()
        ny, nx, dx, x0, y0 = int(z["u"].shape[1]), int(z["u"].shape[2]), float(z["dx"]), float(z["x0"]), float(z["y0"])
        a_geo = Transformer.from_crs(config.EPSG_UTM, "EPSG:4326", always_xy=True).transform
        esq = {k: a_geo(x, y)[::-1] for k, (x, y) in {"c00": (x0, y0), "c10": (x0 + (nx - 1) * dx, y0),
                                                      "c01": (x0, y0 + (ny - 1) * dx)}.items()}
        return {"nx": nx, "ny": ny, "dx": dx, "x0": x0, "y0": y0, "esquinas": esq,
                "cx": float(z["cx"]), "cy": float(z["cy"]), "cx2": float(z["cx2"]), "cy2": float(z["cy2"]), "radio": float(z["radio"]),
                "radio_borde": float(z["radio_borde"]), "paso": float(z["paso"]), "escala": float(z["escala"]),
                "solido": int(z["solido"]), "u": [b64(a) for a in z["u"]], "v": [b64(a) for a in z["v"]]}
