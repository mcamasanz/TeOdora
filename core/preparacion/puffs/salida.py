# -*- coding: utf-8 -*-
"""Lectura cómoda del fichero de concentraciones de `dispersion.puffs` (`fichero_conc.leer`):
fin de cada periodo como fecha y concentraciones de una especie como matriz.
Viene del proyecto de La Galera (2026-10-23)."""
from datetime import datetime, timedelta

import numpy as np


def fecha(t):
    """(año, día juliano, hora, segundos) de un registro -> datetime."""
    a, j, h, s = (int(x) for x in t)
    return datetime(a, 1, 1) + timedelta(days=j - 1, hours=h, seconds=s)


def concentraciones(ruta, especie=0):
    """(fines, conc): datetime del FIN de cada periodo y concentraciones (periodos, receptores)
    de la especie `especie` (posición o nombre), en g/m³."""
    from teodors.dispersion.puffs import fichero_conc
    _, periodos = fichero_conc.leer(ruta)
    fines = [fecha(p.fin) for p in periodos]
    if not periodos:
        return fines, np.zeros((0, 0))
    claves = list(periodos[0].campos)               # «NOMBRE» (12 caracteres) + nivel (3)
    if isinstance(especie, int):
        clave = claves[especie]
    else:
        clave = next((k for k in claves if k[:12].strip().upper() == especie.strip().upper()), None)
        if clave is None:
            raise KeyError("no hay la especie %s en %s (hay: %s)" % (especie, ruta, claves))
    conc = np.array([np.asarray(p.campos[clave], float).ravel() for p in periodos])
    return fines, conc
