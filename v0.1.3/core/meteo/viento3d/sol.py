# -*- coding: utf-8 -*-
"""Elevación solar en el punto medio de la hora.

[UG] sec. 2.3.1: la elevación solar se calcula en el punto medio de cada hora. Caja negra: la
radiación de la hora que termina en t corresponde al sol en t − 30 min. Se usan las fórmulas
clásicas de almanaque (declinación por la longitud eclíptica aproximada y ecuación del tiempo con
armónicos del día del año), las mismas que publican los preprocesadores meteorológicos de la EPA
(p. ej. AERMET, fase 03 de esta carpeta); con ellas el seno de la elevación coincide con el del
original a ±2e-6.
"""
import math

import numpy as np

D2R = math.pi / 180.0


def seno_elevacion(anio, dia_juliano, hora_utc, lat, lon):
    """sin(elevación) para la hora UTC decimal dada (lat, lon en grados, este positivo)."""
    dayno = (float(dia_juliano) - 1.0) * 0.0172028
    s, c = math.sin(dayno), math.cos(dayno)
    s2, c2 = math.sin(2.0 * dayno), math.cos(2.0 * dayno)
    sigma = 279.9348 + dayno / D2R + 1.914827 * s - 0.079525 * c + 0.019938 * s2 - 0.00162 * c2
    decsin = 0.39785 * math.sin(sigma * D2R)
    deccos = math.sqrt(1.0 - decsin * decsin)
    amm = 12.0 + 0.12357 * s - 0.004289 * c + 0.153809 * s2 + 0.060783 * c2
    hi = (15.0 * (hora_utc - amm) + np.asarray(lon)) * D2R
    la = np.radians(lat)
    return np.sin(la) * decsin + deccos * np.cos(la) * np.cos(hi)
