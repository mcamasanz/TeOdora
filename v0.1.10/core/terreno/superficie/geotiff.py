# -*- coding: utf-8 -*-
"""Lectura de los GeoTIFF de NLCD con la semántica de AERSURFACE (mod_TiffParams.f,
mod_GetData.f: GetGridVars + Read_TiffData), usando rasterio en lugar de su lector propio
de TIFF (≈3.000 líneas: OPTIMIZACIÓN, y además admite TIFF comprimidos).

Semántica que se conserva a propósito:
  · tiffULX/ULY = IDNINT(punto de anclaje + ½ píxel) -> ENTEROS (centro del píxel NW).
  · El falso este/norte de la proyección se SUMA al anclaje (así lo hace el original).
  · Muestras de 1 byte leídas como entero CON SIGNO (255 -> -1).
  · Ficheros por TESELAS: los valores negativos pasan a 0. Por BANDAS (strips): no.
  · Fuera del fichero, la rejilla conserva su valor inicial (0 en uso del suelo, 127 en
    impermeable/arbolado)."""
import re
from dataclasses import dataclass

import numpy as np
import rasterio
from rasterio.windows import Window

from .formato import nint


@dataclass
class TiffVars:
    path: str
    cols: int
    rows: int
    pxl_x: float
    pxl_y: float
    cell_res: float
    tie_x: float                # anclaje ajustado al centro del píxel NW (+ falso este)
    tie_y: float
    ul_x: int
    ul_y: int
    lr_x: int
    lr_y: int
    hdatum: str
    tipo: str                   # "strip" o "tile"
    bytes_muestra: int
    std1: float
    std2: float
    origen_lat: float
    meridiano: float


def leer_tags(path):
    with rasterio.open(path) as src:
        tr = src.transform
        if src.tags().get("AREA_OR_POINT", "Area").lower() != "area":
            raise ValueError(f"{path}: solo se admite GTRasterType = PixelIsArea (como el original)")
        crs = src.crs.to_dict() if src.crs else {}
        if crs.get("proj") != "aea":
            raise ValueError(f"{path}: la proyección debe ser Albers (aea), es {crs.get('proj')}")
        wkt = src.crs.to_wkt().upper()
        if "1927" in wkt or "NAD27" in wkt:
            hd = "NAD27"
        elif "WGS_1984" in wkt or "WGS 84" in wkt or "WGS84" in wkt:
            hd = "WGS84"
        elif "1972" in wkt:
            hd = "WGS72"
        else:
            hd = "NAD83"                  # NAD83 o sin datum: el original asume NAD83/WGS84
        tiled = bool(src.profile.get("tiled", False))
        nbytes = np.dtype(src.dtypes[0]).itemsize
        pxl_x, pxl_y = abs(tr.a), abs(tr.e)
        fe, fn = float(crs.get("x_0", 0.0)), float(crs.get("y_0", 0.0))
        # GDAL ya da la esquina NW del píxel NW (el anclaje con su offset de ráster aplicado)
        tie_x = tr.c + 0.5 * pxl_x
        tie_y = tr.f - 0.5 * pxl_y
        ul_x, ul_y = nint(tie_x), nint(tie_y)
        lr_x = ul_x + (src.width - 1) * nint(pxl_x)
        lr_y = ul_y - (src.height - 1) * nint(pxl_x)
        if fe != 0.0:
            tie_x += fe
            ul_x += nint(fe)
            lr_x += nint(fe)
        if fn != 0.0:
            tie_y += fn
            ul_y += nint(fn)
            lr_y += nint(fn)
        return TiffVars(str(path), src.width, src.height, pxl_x, pxl_y, pxl_x, tie_x, tie_y,
                        ul_x, ul_y, lr_x, lr_y, hd, "tile" if tiled else "strip", nbytes,
                        float(crs.get("lat_1")), float(crs.get("lat_2")),
                        float(crs.get("lat_0")), float(crs.get("lon_0")))


def leer_ventana(v, fila0, filas, col0, cols, inicial, es_uso=False):
    """Rejilla [filas, cols] desde la fila/columna `fila0`/`col0` (1-based, del fichero).
    `inicial`: valor de las celdas fuera del fichero. Devuelve (datos, leido) donde `leido`
    marca las celdas que sí estaban dentro del fichero."""
    out = np.full((filas, cols), inicial, dtype=np.int64)
    leido = np.zeros((filas, cols), bool)
    r0, c0 = fila0 - 1, col0 - 1                       # a 0-based
    rr0, cc0 = max(r0, 0), max(c0, 0)
    rr1, cc1 = min(r0 + filas, v.rows), min(c0 + cols, v.cols)
    if rr1 <= rr0 or cc1 <= cc0:
        return out, leido
    with rasterio.open(v.path) as src:
        a = src.read(1, window=Window(cc0, rr0, cc1 - cc0, rr1 - rr0))
    if a.dtype.itemsize == 1:
        a = a.view(np.int8)                            # INTEGER(KIND=1): con signo
    elif a.dtype.itemsize == 2:
        a = a.view(np.int16)
    elif a.dtype.itemsize == 4:
        a = a.view(np.int32)
    a = a.astype(np.int64)
    out[rr0 - r0:rr1 - r0, cc0 - c0:cc1 - c0] = a
    leido[rr0 - r0:rr1 - r0, cc0 - c0:cc1 - c0] = True
    return out, leido
