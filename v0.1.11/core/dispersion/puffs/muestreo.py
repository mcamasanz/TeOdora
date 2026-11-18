# -*- coding: utf-8 -*-
"""Función de muestreo integrada de un puff a lo largo de su tramo y término vertical.

Fuentes (ver FUENTES.md del laboratorio):
  - [UG] sec. 2.1.1, ecs. 2-1 a 2-13: integral de la contribución gaussiana a lo largo de un tramo
    recto con σ constante (I1, ecs. 2-9, 2-11 a 2-13) y término vertical g con reflexiones en el
    suelo y la tapa (ec. 2-2), mezcla uniforme 1/h para σz > 1,6·h.
  - [UG] sec. 2.11, ec. 2-274: factor de corrección Fr de los puffs de fuentes de área.
  - Caja negra: σ en el receptor en la posición a lo largo del tramo recortada a
    [−σy_ini, L + σy_fin]; solo receptores a menos de 3σy de la trayectoria.
"""
import math

import numba as nb

SQ2 = math.sqrt(2.0)
SQ2PI = math.sqrt(2.0 * math.pi)
N_CORTE = 3.0          # receptores a más de 3σy del tramo no se muestrean (caja negra)


@nb.njit(cache=True)
def integral_tramo(a, b, c):
    """∫_0^1 exp(−(a·p² + 2·b·p + c)/2) dp (ecs. 2-9 y 2-11 a 2-13 con Q constante)."""
    if a < 1e-10:
        # tramo casi nulo: el integrando apenas varía
        return math.exp(-0.5 * (c + b + a / 3.0))
    sa = math.sqrt(2.0 * a)
    arg = b * b / (2.0 * a) - 0.5 * c
    return math.sqrt(math.pi / (2.0 * a)) * math.exp(arg) * (math.erf((a + b) / sa) - math.erf(b / sa))


@nb.njit(cache=True)
def integral_tramo_p(a, b, c, i1):
    """∫_0^1 p·exp(−(a·p² + 2·b·p + c)/2) dp ([UG] ec. 2-10): término de la masa que varía
    linealmente a lo largo del tramo (eliminación y transformación)."""
    if a < 1e-4:
        # tramo corto: cuadratura de Gauss-Legendre de 4 puntos (sin cancelación)
        s = 0.0
        for xg, wg in ((0.0694318442029737, 0.1739274225687269), (0.3300094782075719, 0.3260725774312731),
                       (0.6699905217924281, 0.3260725774312731), (0.9305681557970263, 0.1739274225687269)):
            s += wg * xg * math.exp(-0.5 * (a * xg * xg + 2.0 * b * xg + c))
        return s
    return (math.exp(-0.5 * c) - math.exp(-0.5 * (a + 2.0 * b + c))) / a - b / a * i1


@nb.njit(cache=True)
def g_vertical(he, zr, sz, lid):
    """Término vertical g (1/m) para un puff a altura he, receptor a altura zr, con reflexión en el
    suelo y, si lid < 1e4, en la tapa (ec. 2-2 generalizada a receptor elevado)."""
    if sz <= 0.0:
        return 0.0
    sin_tapa = lid >= 9999.0
    if not sin_tapa and sz > 1.6 * lid:
        return 1.0 / lid
    f = 1.0 / (SQ2PI * sz)
    s2 = 2.0 * sz * sz
    tot = math.exp(-(he - zr) ** 2 / s2) + math.exp(-(he + zr) ** 2 / s2)
    if sin_tapa:
        return f * tot
    for n in range(1, 60):
        d = 2.0 * n * lid
        t = (math.exp(-(he - zr + d) ** 2 / s2) + math.exp(-(he + zr + d) ** 2 / s2)
             + math.exp(-(he - zr - d) ** 2 / s2) + math.exp(-(he + zr - d) ** 2 / s2))
        tot += t
        if t < 1e-12 * tot:
            break
    return f * tot


@nb.njit(cache=True)
def fr_area(yr, syr, sys, lc2):
    """Factor de corrección de los puffs de fuentes de área (ec. 2-274): distribución transversal de
    una línea de anchura 2·lc2 frente a la gaussiana de σ = syr."""
    sya2 = syr * syr - sys * sys
    if sys <= 0.0 or sya2 <= 1e-12:
        return 1.0
    sya = math.sqrt(sya2)
    num = math.erf((yr + lc2) / (SQ2 * sya)) - math.erf((yr - lc2) / (SQ2 * sya))
    den = 2.0 * math.exp(-yr * yr / (2.0 * syr * syr))
    if den <= 1e-300:
        return 1.0
    return syr / sys * num / den
