# -*- coding: utf-8 -*-
"""Coeficientes de dispersión σy, σz y sus inversas (distancia o tiempo virtual).

Fuentes (ver FUENTES.md del laboratorio):
  - [UG] CALPUFF User's Guide v5 (Scire et al., 2000), sec. 2.2.1: tablas 2-4 y 2-5 (Pasquill-Gifford,
    curvas rurales de ISC), 2-6 y 2-7 (McElroy-Pooler urbanas), ecs. 2-65 a 2-67 (funciones de Draxler)
    y transición a Heffter (σy ∝ t) por SYTDEP.
  - Caja negra (validacion/cajanegra.py, salida de depuración): crecimiento por fuente virtual desde
    σ0 = SYMIN/SZMIN; en calma, σ = σv·t·fy(t) y σz = σw·t·fz(t) con σv = SVMIN y σw = SWMIN de la
    clase; fz según el signo de L; Heffter σy = 0,5·t (t en s).
"""
import math

import numba as nb
import numpy as np

# Tabla 2-4: σy = 465.11628·x·tan(0.017453293·(c − d·ln x)), x en km
PGY = np.array([[24.1670, 2.5334], [18.3330, 1.8096], [12.5000, 1.0857], [8.3330, 0.72382],
                [6.2500, 0.54287], [4.1667, 0.36191]])
# Tabla 2-5: σz = a·x^b por tramos (límite superior del tramo en km, a, b); A > 3.11 km -> 5000 m
_Z = [
    [(0.10, 122.800, 0.94470), (0.15, 158.080, 1.05420), (0.20, 170.220, 1.09320),
     (0.25, 179.520, 1.12620), (0.30, 217.410, 1.26440), (0.40, 258.890, 1.40940),
     (0.50, 346.750, 1.72830), (3.11, 453.850, 2.11660)],
    [(0.20, 90.673, 0.93198), (0.40, 98.483, 0.98332), (1e30, 109.300, 1.09710)],
    [(1e30, 61.141, 0.91465)],
    [(0.30, 34.459, 0.86974), (1.00, 32.093, 0.81066), (3.00, 32.093, 0.64403),
     (10.0, 33.504, 0.60486), (30.0, 36.650, 0.56589), (1e30, 44.053, 0.51179)],
    [(0.10, 24.260, 0.83660), (0.30, 23.331, 0.81956), (1.00, 21.628, 0.75660),
     (2.00, 21.628, 0.63077), (4.00, 22.534, 0.57154), (10.0, 24.703, 0.50527),
     (20.0, 26.970, 0.46713), (40.0, 35.420, 0.37615), (1e30, 47.618, 0.29592)],
    [(0.20, 15.209, 0.81558), (0.70, 14.457, 0.78407), (1.00, 13.953, 0.68465),
     (2.00, 13.953, 0.63227), (3.00, 14.823, 0.54503), (7.00, 16.187, 0.46490),
     (15.0, 17.836, 0.41507), (30.0, 22.651, 0.32681), (60.0, 27.074, 0.27436),
     (1e30, 34.219, 0.21716)]]
NZT = max(len(t) for t in _Z)
PGZ = np.full((6, NZT, 3), np.nan)
PGZN = np.zeros(6, np.int64)
for _k, _t in enumerate(_Z):
    PGZN[_k] = len(_t)
    for _i, _r in enumerate(_t):
        PGZ[_k, _i] = _r
SZ_MAX = 5000.0
# Tablas 2-6 y 2-7 (x en m): σ = a·x·(1 + b·x)^e
MPY = np.array([[0.32, 0.0004, -0.5], [0.32, 0.0004, -0.5], [0.22, 0.0004, -0.5],
                [0.16, 0.0004, -0.5], [0.11, 0.0004, -0.5], [0.11, 0.0004, -0.5]])
MPZ = np.array([[0.24, 0.001, 0.5], [0.24, 0.001, 0.5], [0.20, 0.0, 0.0],
                [0.14, 0.0003, -0.5], [0.08, 0.0015, -0.5], [0.08, 0.0015, -0.5]])
HEFFTER_Y = 0.5     # m/s: σy = 0,5·t (caja negra)
# MDISP = 4: curvas PG de MESOPUFF II, σy = ay·x^by, σz = az·x^bz con x en m ([UG] tabla 2-8, ecs.
# 2-70 y 2-71); se seleccionan con las clases 7 a 12 en sigma_dist
MPII = np.array([[0.36, 0.9, 0.00023, 2.10], [0.25, 0.9, 0.058, 1.09], [0.19, 0.9, 0.11, 0.91],
                 [0.13, 0.9, 0.57, 0.58], [0.096, 0.9, 0.85, 0.47], [0.063, 0.9, 0.77, 0.42]])


@nb.njit(cache=True)
def sy_pg(x, k):
    """σy rural (m) a la distancia x (m), clase k = 1..6."""
    if x <= 0.0:
        return 0.0
    xk = x / 1000.0
    th = 0.017453293 * (PGY[k - 1, 0] - PGY[k - 1, 1] * math.log(xk))
    return 465.11628 * xk * math.tan(th)


@nb.njit(cache=True)
def sz_pg(x, k):
    """σz rural (m) a la distancia x (m)."""
    if x <= 0.0:
        return 0.0
    xk = x / 1000.0
    for i in range(PGZN[k - 1]):
        if xk <= PGZ[k - 1, i, 0]:
            return min(PGZ[k - 1, i, 1] * xk ** PGZ[k - 1, i, 2], SZ_MAX)
    return SZ_MAX     # clase A más allá de 3,11 km


@nb.njit(cache=True)
def sy_mp(x, k):
    if x <= 0.0:
        return 0.0
    return MPY[k - 1, 0] * x * (1.0 + MPY[k - 1, 1] * x) ** MPY[k - 1, 2]


@nb.njit(cache=True)
def sz_mp(x, k):
    if x <= 0.0:
        return 0.0
    return MPZ[k - 1, 0] * x * (1.0 + MPZ[k - 1, 1] * x) ** MPZ[k - 1, 2]


@nb.njit(cache=True)
def sigma_dist(x, k, urbano, eje):
    """σ (m) a la distancia x (m): eje 0 = y, 1 = z; urbano -> McElroy-Pooler; clases 7 a 12: curvas
    rurales de MESOPUFF II (MDISP = 4)."""
    if k > 6:
        if urbano:
            k -= 6
        elif x <= 0.0:
            return 0.0
        else:
            c = MPII[k - 7]
            return c[0] * x ** c[1] if eje == 0 else min(c[2] * x ** c[3], SZ_MAX)
    if urbano:
        return sy_mp(x, k) if eje == 0 else sz_mp(x, k)
    return sy_pg(x, k) if eje == 0 else sz_pg(x, k)


@nb.njit(cache=True)
def x_virtual(sig, k, urbano, eje):
    """Distancia virtual (m) a la que la curva da `sig` (bisección en ln x; las curvas son
    crecientes salvo los saltos entre tramos de σz, donde se toma el borde). Devuelve −1 si la
    curva no llega a `sig` (σz de clases estables a distancias enormes): el puff no crece."""
    if sig <= 0.0:
        return 0.0
    # la curva de σy de PG decae más allá de ~1e5 km; la de σz sigue creciendo muy despacio
    a, b = math.log(1e-4), math.log(1e6 if eje == 0 else 1e15)
    if sigma_dist(math.exp(b), k, urbano, eje) < sig:
        return -1.0
    for _ in range(100):
        m = 0.5 * (a + b)
        if sigma_dist(math.exp(m), k, urbano, eje) < sig:
            a = m
        else:
            b = m
    return math.exp(0.5 * (a + b))


# ── crecimiento con el tiempo (calmas): σ = σt·t·f(t), funciones de Draxler (ecs. 2-65 a 2-67) ──
@nb.njit(cache=True)
def f_draxler(t, eje, estable):
    if eje == 0:
        return 1.0 / (1.0 + 0.9 * math.sqrt(t / 1000.0))
    if estable:
        return 1.0 / (1.0 + 0.945 * (t / 100.0) ** 0.806)
    return 1.0 / (1.0 + 0.9 * math.sqrt(t / 500.0))


@nb.njit(cache=True)
def sigma_tiempo(t, sv, eje, estable):
    if t <= 0.0:
        return 0.0
    return sv * t * f_draxler(t, eje, estable)


@nb.njit(cache=True)
def t_virtual(sig, sv, eje, estable):
    """Tiempo virtual (s) al que σ(t) = sig."""
    if sig <= 0.0:
        return 0.0
    if eje == 0 or not estable:
        # σ(1 + 0.9·√(t/T)) = σv·t  ->  cuadrática en s = √t
        T = 1000.0 if eje == 0 else 500.0
        bb = 0.9 * sig / math.sqrt(T)
        s = (bb + math.sqrt(bb * bb + 4.0 * sv * sig)) / (2.0 * sv)
        return s * s
    a, b = math.log(1e-6), math.log(1e15)
    if sigma_tiempo(math.exp(b), sv, eje, estable) < sig:
        return -1.0     # inalcanzable: el puff no crece
    for _ in range(90):
        m = 0.5 * (a + b)
        if sigma_tiempo(math.exp(m), sv, eje, estable) < sig:
            a = m
        else:
            b = m
    return math.exp(0.5 * (a + b))


# ── MDISP = 2: σv y σw de la micrometeorología ([UG] ecs. 2-52 a 2-64) ──
@nb.njit(cache=True)
def sigvw(z, h, us, ws, el):
    """σv, σw (m/s) a la altura z con la capa de mezcla h, u*, w* y L. Inestable: capa superficial
    (z ≤ 0,1·h), de mezcla (hasta 0,8·h) y de arrastre (hasta 1,2·h, con el factor ac elevado al
    cuadrado; caja negra); estable/neutra con Cs = (1 − z/h)^¾ (0 por encima de h); por encima de
    1,2·h, 0 (se aplican después los mínimos SVMIN/SWMIN)."""
    if h <= 0.0 or z > 1.2 * h:
        return 0.0, 0.0
    zh = z / h
    an = math.exp(-0.9 * zh)
    u2a = us * us * an * an
    if el < 0.0:
        sv = math.sqrt(4.0 * u2a + 0.35 * ws * ws)
        if zh <= 0.1:
            sw = math.sqrt(1.6 * u2a + 2.9 * us * us * (-z / el) ** (2.0 / 3.0))
        elif zh <= 0.8:
            sw = math.sqrt(1.15 * u2a + 0.35 * ws * ws)
        elif zh <= 1.0:
            ac = 0.5 + (h - z) / (0.4 * h)
            sw = math.sqrt(1.15 * u2a + ac * ac * 0.35 * ws * ws)
        else:
            ac = 1.0 / 3.0 + (1.2 * h - z) / (1.2 * h)
            sw = math.sqrt(1.15 * u2a + ac * ac * 0.35 * ws * ws)
        return sv, sw
    cs = max(1.0 - zh, 0.0) ** 0.75
    zl = z / el
    sv = us * (1.6 * cs * zl + 1.8 * an) / (1.0 + zl)
    sw = 1.3 * us * (cs * zl + an) / (1.0 + zl)
    return sv, sw
