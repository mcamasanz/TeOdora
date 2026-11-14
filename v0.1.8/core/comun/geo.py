# -*- coding: utf-8 -*-
"""Coordenadas UTM, convergencia de meridianos y dominios cuadrados.

En la proyección UTM el norte de la cuadrícula no coincide con el norte geográfico salvo en el
meridiano central del huso: el giro entre los dos es la **convergencia de meridianos γ**. Un viento
dado desde el norte geográfico (observaciones, reanálisis) hay que girarlo γ para usarlo con
receptores y fuentes en UTM, y el penacho se desvía lateralmente d · sen γ a una distancia d (con
γ = −1,65°, unos 200 m a 7 km).

`epsg`: el sistema UTM de trabajo («EPSG:25831»…). Si no se da, el del huso de la longitud con datum
ETRS89 (husos 28 a 38) o WGS-84. ⚠️ En un dominio, TODOS los puntos tienen que usar el mismo: el
proyecto lo fija una vez y lo pasa siempre (si no, dos puntos a lados de un límite de huso caerían en
husos distintos).
"""
import math
from functools import lru_cache

import numpy as np
from pyproj import Transformer

CRS_GEO = "EPSG:4326"
_RUMBOS = ("N", "NE", "E", "SE", "S", "SO", "O", "NO")


@lru_cache(maxsize=16)
def _tr(origen, destino):
    return Transformer.from_crs(origen, destino, always_xy=True)


def huso_utm(lon):
    """Huso UTM estándar de una longitud (España peninsular: 29, 30 o 31)."""
    return int((lon + 180.0) // 6.0) + 1


def epsg_utm(lon, datum="ETRS89", norte=True):
    """Código EPSG del UTM del huso de `lon`: ETRS89 (258zz, husos 28 a 38) o WGS-84 (326zz al
    norte, 327zz al sur)."""
    z = huso_utm(lon)
    if datum.upper() == "ETRS89" and norte and 28 <= z <= 38:
        return "EPSG:%d" % (25800 + z)
    return "EPSG:%d" % ((32600 if norte else 32700) + z)


def _epsg(epsg, lon):
    return epsg or epsg_utm(lon)


def a_utm(lat, lon, epsg=None):
    """(lat, lon) -> (x, y) en metros."""
    return _tr(CRS_GEO, _epsg(epsg, lon)).transform(lon, lat)


def a_geo(x, y, epsg):
    """(x, y) UTM de `epsg` -> (lat, lon)."""
    lon, lat = _tr(epsg, CRS_GEO).transform(x, y)
    return lat, lon


def acimut_norte_en_rejilla(lat, lon, epsg=None):
    """Hacia dónde apunta el NORTE GEOGRÁFICO medido en la cuadrícula UTM (grados, horario). Se
    calcula proyectando un paso hacia el norte: sin ambigüedades de signo."""
    epsg = _epsg(epsg, lon)
    x0, y0 = a_utm(lat, lon, epsg)
    x1, y1 = a_utm(lat + 0.01, lon, epsg)
    return math.degrees(math.atan2(x1 - x0, y1 - y0))


def convergencia_deg(lat, lon, epsg=None):
    """Convergencia de meridianos γ: giro entre el norte geográfico y el de la cuadrícula.
    Positiva al este del meridiano central del huso."""
    return -acimut_norte_en_rejilla(lat, lon, epsg)


def dir_geo_a_rejilla(wd_geo, lat, lon, epsg=None):
    """Dirección del viento (de donde viene, desde el norte GEOGRÁFICO) -> desde el norte de la
    CUADRÍCULA, que es como la interpreta el penacho (`dispersion.penacho`) respecto a sus
    receptores UTM."""
    return (wd_geo + acimut_norte_en_rejilla(lat, lon, epsg)) % 360.0


def distancia_rumbo(lat0, lon0, lat, lon, epsg=None):
    """Distancia (m) y rumbo GEOGRÁFICO en 8 puntos («NE», «SO»…) de (lat, lon) visto desde
    (lat0, lon0). El rumbo se corrige de cuadrícula a norte geográfico."""
    epsg = _epsg(epsg, lon0)
    x0, y0 = a_utm(lat0, lon0, epsg)
    x, y = a_utm(lat, lon, epsg)
    dx, dy = x - x0, y - y0
    acimut = (math.degrees(math.atan2(dx, dy)) - acimut_norte_en_rejilla(lat0, lon0, epsg)) % 360
    return math.hypot(dx, dy), _RUMBOS[int((acimut + 22.5) // 45) % 8]


def desvio_lateral_m(distancia_m, gamma_deg):
    """Desplazamiento lateral del penacho a `distancia_m` si su dirección está girada γ."""
    return distancia_m * math.sin(math.radians(abs(gamma_deg)))


def cuadrado_utm(lat, lon, lado_km, epsg=None, puntos_por_lado=8):
    """Cuadrado de LADO `lado_km` alineado con la cuadrícula UTM y centrado en (lat, lon). Devuelve
    (vértices [(lat, lon), …] para pintar, extensión UTM (xmin, xmax, ymin, ymax)). Los lados se
    densifican porque una recta UTM no es recta en un mapa web."""
    epsg = _epsg(epsg, lon)
    cx, cy = a_utm(lat, lon, epsg)
    h = lado_km * 500.0
    ext = (cx - h, cx + h, cy - h, cy + h)
    esquinas = [(cx - h, cy - h), (cx + h, cy - h), (cx + h, cy + h), (cx - h, cy + h)]
    xs, ys = [], []
    for (xa, ya), (xb, yb) in zip(esquinas, esquinas[1:] + esquinas[:1]):
        for i in range(puntos_por_lado):
            t = i / puntos_por_lado
            xs.append(xa + (xb - xa) * t)
            ys.append(ya + (yb - ya) * t)
    lons, lats = _tr(epsg, CRS_GEO).transform(xs, ys)
    return [(la, lo) for la, lo in zip(lats, lons)], ext


def direccion(u, v):
    """Dirección de la que viene el viento (grados, 0-360), en los mismos ejes que sus componentes u, v."""
    return (np.degrees(np.arctan2(-u, -v)) + 360.0) % 360.0


def elevacion_solar(t, lat, lon):
    """Elevación del sol (grados) en instantes UTC (serie de pandas; fórmula aproximada de la NOAA)."""
    dia = t.dt.dayofyear.to_numpy()
    h = t.dt.hour.to_numpy() + t.dt.minute.to_numpy() / 60.0
    g = 2 * np.pi / 365 * (dia - 1 + (h - 12) / 24)
    decl = (0.006918 - 0.399912 * np.cos(g) + 0.070257 * np.sin(g) - 0.006758 * np.cos(2 * g)
            + 0.000907 * np.sin(2 * g) - 0.002697 * np.cos(3 * g) + 0.00148 * np.sin(3 * g))
    eq = 229.18 * (0.000075 + 0.001868 * np.cos(g) - 0.032077 * np.sin(g)
                   - 0.014615 * np.cos(2 * g) - 0.040849 * np.sin(2 * g))
    ang = np.radians(((h * 60 + eq + 4 * lon) / 4) - 180)
    la = np.radians(lat)
    sen = np.sin(la) * np.sin(decl) + np.cos(la) * np.cos(decl) * np.cos(ang)
    return np.degrees(np.arcsin(np.clip(sen, -1, 1)))
