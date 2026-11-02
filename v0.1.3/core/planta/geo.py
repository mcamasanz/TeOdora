# -*- coding: utf-8 -*-
"""Las cuentas de `teodors.comun.geo` en el huso de la planta activa: todos los puntos del dominio en
el mismo sistema, sin tener que pasarlo cada vez. Con `epsg`, el que se pida."""
from teodors.comun import geo as _geo
from teodors.comun.geo import desvio_lateral_m, direccion, elevacion_solar, huso_utm  # noqa: F401  (no dependen del huso)

from . import actual


def _epsg(epsg):
    return epsg or actual().EPSG_UTM


def a_utm(lat, lon, epsg=None):
    """(lat, lon) -> (x, y) en metros."""
    return _geo.a_utm(lat, lon, _epsg(epsg))


def a_geo(x, y, epsg=None):
    """(x, y) UTM -> (lat, lon)."""
    return _geo.a_geo(x, y, _epsg(epsg))


def acimut_norte_en_rejilla(lat, lon, epsg=None):
    """Hacia dónde apunta el norte geográfico en la cuadrícula UTM (grados, horario)."""
    return _geo.acimut_norte_en_rejilla(lat, lon, _epsg(epsg))


def convergencia_deg(lat, lon, epsg=None):
    """Convergencia de meridianos γ (positiva al este del meridiano central del huso)."""
    return _geo.convergencia_deg(lat, lon, _epsg(epsg))


def dir_geo_a_rejilla(wd_geo, lat, lon, epsg=None):
    """Dirección del viento desde el norte geográfico -> desde el norte de la cuadrícula."""
    return _geo.dir_geo_a_rejilla(wd_geo, lat, lon, _epsg(epsg))


def distancia_rumbo(lat0, lon0, lat, lon, epsg=None):
    """Distancia (m) y rumbo geográfico en 8 puntos de (lat, lon) visto desde (lat0, lon0)."""
    return _geo.distancia_rumbo(lat0, lon0, lat, lon, _epsg(epsg))


def cuadrado_utm(lat, lon, lado_km, epsg=None, puntos_por_lado=8):
    """Cuadrado de LADO `lado_km` alineado con la cuadrícula UTM y centrado en (lat, lon)."""
    return _geo.cuadrado_utm(lat, lon, lado_km, _epsg(epsg), puntos_por_lado)
