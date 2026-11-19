# -*- coding: utf-8 -*-
"""Escalas de color del viento y de las concentraciones. Necesita matplotlib (extra `teodors[mapas]`).

Las imágenes de concentración se pueden guardar en grises y dejar que el color lo ponga el navegador
con un filtro (`para_mapa`): cambiar de escala no rehace ninguna imagen."""
from functools import lru_cache

import numpy as np

# Clases de velocidad de las rosas de los vientos, de lento a rápido: azul, verde, amarillo, naranja y rojo
COLORES_VEL = ("#2b7bba", "#2ca25f", "#f2cc0c", "#f28e1c", "#d7301f")

# clave: (nombre que se enseña, escala de matplotlib o sus colores)
ESCALAS = {"turbo": ("Turbo", "turbo"),
           "viridis": ("Viridis", "viridis"),
           "plasma": ("Plasma", "plasma"),
           "inferno": ("Inferno", "inferno"),
           "cividis": ("Cividis", "cividis"),
           "amarillo_rojo": ("Amarillo a rojo", "YlOrRd"),
           "verde_rojo": ("Verde a rojo", "RdYlGn_r"),
           "azul_rojo": ("Azul a rojo", COLORES_VEL)}


@lru_cache(maxsize=None)
def lut(clave):
    """Los 256 colores de la escala, RGB de 0 a 1."""
    from matplotlib import colormaps
    from matplotlib.colors import LinearSegmentedColormap
    origen = ESCALAS[clave][1]
    cm = (colormaps[origen].resampled(256) if isinstance(origen, str)
          else LinearSegmentedColormap.from_list(clave, origen, 256))
    return cm(np.arange(256))[:, :3]


def colores(clave, n):
    """n colores repartidos de un extremo al otro de la escala, en #rrggbb."""
    origen = ESCALAS[clave][1]
    if not isinstance(origen, str) and len(origen) == n:
        return list(origen)
    t = (lut(clave)[np.linspace(0, 255, n).round().astype(int)] * 255).round().astype(int)
    return ["#%02x%02x%02x" % tuple(f) for f in t]


def para_mapa(clave):
    """Lo que necesita una página de mapa: el degradado de la leyenda y las tablas del filtro."""
    t = lut(clave)
    return {"gradiente": "linear-gradient(90deg," + ",".join(colores(clave, 17)) + ")",
            **{c: " ".join(f"{v:.4f}" for v in t[:, k]) for k, c in enumerate("rgb")}}
