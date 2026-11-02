# -*- coding: utf-8 -*-
"""Utilidades para la salida de `meteo.viento3d`: fecha de los registros, recorte de las horas de
arranque e interpolación en un punto.

El viento 3D tiene memoria NOCTURNA: un trozo que arranca en frío a las 00 UTC da otro viento cerca
del suelo (hasta 9 m/s), otra estabilidad y otra temperatura hasta la salida del sol; desde ahí
coincide bit a bit con la corrida continua (medido en La Galera, 2026-10-15). Por eso cada periodo
se calcula desde unas horas antes y luego se recortan (`recortar_arranque` o, al guardar,
`meteo.viento3d.almacen.comprimir(recorte=recorte(...))`).
Viene del proyecto de La Galera (2026-10-23)."""
import struct
from pathlib import Path

import numpy as np


def fecha_registro(ts):
    """AAAAJJJHH (hora FINAL) de un instante (con .year, .dayofyear, .hour)."""
    return ts.year * 100000 + ts.dayofyear * 100 + ts.hour


def recorte(ini, horas):
    """(año, mes, horas, primera fecha AAAAJJJHH) para `almacen.comprimir(recorte=…)`: el periodo
    que empieza en `ini` (el día 1 del mes a las 00) y dura `horas`."""
    return (ini.year, ini.month, horas, fecha_registro(ini))


def recortar_arranque(ruta, ini, horas, nx, ny):
    """Quita del fichero de viento las horas anteriores a `ini` y corrige la cabecera (año, mes,
    día, hora de inicio y número de horas: primeros enteros del registro de 148 B), para que quede
    como una corrida que empieza en `ini` con `horas` horas. Devuelve los registros quitados."""
    ruta = Path(ruta)
    primero = fecha_registro(ini)
    n2d = 12 + 4 * nx * ny
    destino = ruta.with_suffix(".recortado")
    quitados = 0
    with open(ruta, "rb") as fi, open(destino, "wb") as fo:
        while True:
            h = fi.read(4)
            if len(h) < 4:
                break
            n = struct.unpack("<i", h)[0]
            b = fi.read(n)
            fi.read(4)
            if n == 148 and struct.unpack_from("<i", b, 0)[0] > 1900:          # cabecera
                v = list(struct.unpack_from("<10i", b, 0))
                v[0:4] = [ini.year, ini.month, 1, 0]
                v[5] = horas
                b = struct.pack("<10i", *v) + b[40:]
            elif n == n2d:
                fecha = struct.unpack_from("<i", b, 8)[0]
                if fecha and fecha < primero:                                  # arranque
                    quitados += 1
                    continue
            fo.write(h + b + h)
    destino.replace(ruta)
    return quitados


def en_punto(campo, x, y, xs, ys):
    """Interpolación bilineal de un campo (…, ny, nx) en el punto (x, y); xs, ys: centros de las
    columnas y filas de la malla (m)."""
    fx = np.clip((x - xs[0]) / (xs[1] - xs[0]), 0, len(xs) - 1.000001)
    fy = np.clip((y - ys[0]) / (ys[1] - ys[0]), 0, len(ys) - 1.000001)
    i, j = int(fx), int(fy)
    a, b = fx - i, fy - j
    return ((1 - a) * (1 - b) * campo[..., j, i] + a * (1 - b) * campo[..., j, i + 1]
            + (1 - a) * b * campo[..., j + 1, i] + a * b * campo[..., j + 1, i + 1])


def viento_en_punto(u, v, xs, ys, x, y, acimut_norte):
    """Velocidad y dirección GEOGRÁFICA (de donde viene) del viento (u, v respecto a la CUADRÍCULA,
    (…, ny, nx)) en el punto (x, y). `acimut_norte`: hacia dónde apunta el norte geográfico en la
    cuadrícula (`comun.geo.acimut_norte_en_rejilla`)."""
    ue = en_punto(u, x, y, xs, ys)
    ve = en_punto(v, x, y, xs, ys)
    wd_rejilla = (270.0 - np.degrees(np.arctan2(ve, ue))) % 360.0
    return np.hypot(ue, ve), (wd_rejilla - acimut_norte) % 360.0
