# -*- coding: utf-8 -*-
"""Malla de receptores de cálculo de una planta y lo que necesita su capa del mapa (la rejilla anidada la hace
`preparacion.receptores.malla_anidada`).

Niveles y estilos, del bloque `receptores` de planta.json; el dominio de cálculo es config.RADIO_CALCULO_KM. Además de los niveles,
receptores discretos: los núcleos de CORINE, las VIVIENDAS del Catastro y los receptores CON NOMBRE de receptores.json.
"""
import json

import numpy as np

from teodors import planta as config
from teodors.planta import geo
from teodors.preparacion import receptores as rec

resumen = rec.resumen


def niveles():
    """Los niveles de la malla, de dentro afuera: [(clase, paso_m, semilado_m o None = todo el dominio)]."""
    return [tuple(n) for n in config.pide("receptores", "niveles")]


def estilos():
    """Cómo se pinta cada clase en el mapa, en el orden de planta.json: {clase: (color, radio en píxeles, texto)}."""
    return {c: tuple(e) for c, e in config.pide("receptores", "estilos").items()}


def con_nombre():
    """Receptores con nombre de receptores.json de la planta: [{id, nombre, x, y, …}] en config.EPSG_UTM."""
    if not config.RECEPTORES_JSON.is_file():
        return []
    d = json.loads(config.RECEPTORES_JSON.read_text(encoding="utf-8"))
    if d["epsg"] != config.EPSG_UTM:
        raise ValueError(f"{config.RECEPTORES_JSON.name} está en {d['epsg']}, no en {config.EPSG_UTM}")
    return d["receptores"]


def malla(nucleos=(), edificios=None):
    """Receptores [(x, y, clase)] en config.EPSG_UTM. nucleos: lista de `fuentes.terreno.resumen()`
    ['nucleos'] (con x, y); edificios: GeoDataFrame de `fuentes.catastro.cargar()` (EPSG_UTM)."""
    emp = config.cargar_emplazamiento()
    discretos = [(n["x"], n["y"], "nucleo") for n in nucleos]
    if edificios is not None and len(edificios):
        viv = edificios[edificios["uso"] == "Residencial"]
        discretos += [(c.x, c.y, "vivienda") for c in viv.geometry.centroid]
    discretos += [(r["x"], r["y"], "nombrado") for r in con_nombre()]
    return rec.malla_anidada(geo.a_utm(emp["lat"], emp["lon"]), config.RADIO_CALCULO_KM * 1000.0,
                             niveles(), discretos)


def a_geo(recs):
    """[(lat, lon, clase)]"""
    from pyproj import Transformer
    tr = Transformer.from_crs(config.EPSG_UTM, config.CRS_GEO, always_xy=True)
    x = np.array([r[0] for r in recs])
    y = np.array([r[1] for r in recs])
    lon, lat = tr.transform(x, y)
    return [(float(la), float(lo), r[2]) for la, lo, r in zip(lat, lon, recs)]
