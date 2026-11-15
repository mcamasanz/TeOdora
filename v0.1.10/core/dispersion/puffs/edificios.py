# -*- coding: utf-8 -*-
"""Efecto edificio sobre las chimeneas (building downwash), método ISC (MBDW = 1).

Fuentes (ver FUENTES.md del laboratorio):
  - [UG] CALPUFF User's Guide v5 (Scire et al., 2000), sec. 2.3 (Huber-Snyder y Schulman-Scire,
    ecs. 2-108 a 2-115, umbral TBD), sec. 2.4.4 (sobreelevación con radio de dilución y fuente
    lineal, ecs. 2-127 a 2-130) y sec. 2.2.2 (sin dispersión por flotación con Schulman-Scire).
  - [V6] CALPUFF V6 User Instructions (2011), tabla 9-3: datos del subgrupo 13c (36 direcciones del
    vector de flujo, de 10° a 360°).
  - [ISC3] ISC3 User's Guide, vol. II (EPA-454/B-95-003b), secs. 1.1.4.10.1 (altura del chorro a
    dos alturas de edificio, sin efecto punta), 1.1.4.11 (cúbica de Schulman-Scire, β = 0,6, R0 y
    Ly en x = 3·LB) y 1.1.5.3 (criterio GEP hb + 1,5·LB, ecs. 1-37 a 1-47: σ aumentadas, naves
    achatadas o altas, hw/hb > 5 con la ec. 1-43, distancias virtuales en 10·hb no negativas).
  - Caja negra (validacion/cajanegra.py, `exp_edificio_*`): sector int((vector + 4,5)/10); viento y
    dirección de la capa CALMET de la chimenea; la reducción de la sobreelevación (Schulman-Scire,
    sin dispersión por flotación) se decide con hs < hb + 0,5·LB y TBD solo decide el factor A de
    σz; el aumento de σy con HEFF2 ≤ 1,2·hb; en el muestreo, con el receptor a menos de 10·esc del
    origen, σ = máx(σ del edificio, σ ambiental) en la distancia real (como mínimo 3·esc, y el
    tamaño mínimo SYMIN/SZMIN por debajo de 0,99·3·esc); más allá, el crecimiento normal del puff
    desde σ0 = σ(x virtual), con el x virtual que da en 10·esc la σ del edificio.
"""
import math
from dataclasses import dataclass

import numba as nb

from .sigmas import sigma_dist, x_virtual
from .sobreelevacion import G, DZ_GRAD, dthdz, t_altura

BETA = 0.6               # arrastre de Schulman-Scire ([ISC3] 1.1.4.11)
RAIZ2 = math.sqrt(2.0)
RAIZ2PI = math.sqrt(2.0 * math.pi)
U_MIN = 1.0              # m/s, viento mínimo de la sobreelevación


def sector(u, v):
    """Sector 1..36 del vector de flujo (dirección hacia la que sopla el viento) para buscar las
    dimensiones del edificio: int((vector + 4,5)/10), 0 -> 36 (caja negra)."""
    fv = math.degrees(math.atan2(u, v)) % 360.0
    k = int((fv + 4.5) / 10.0)
    return 36 if k == 0 else min(k, 36)


@dataclass
class Estela:
    """Efecto edificio ISC de una fuente para la hora (vector de flujo de la capa de la chimenea)."""
    idw: int = 0             # 0 sin efecto, 1 Huber-Snyder, 2 Schulman-Scire (sobreelevación reducida)
    hb: float = 0.0
    hw: float = 0.0
    esc: float = 0.0         # escala de las σ: hb (nave achatada, hw ≥ hb) o hw (alta)
    heff2: float = 0.0       # altura del chorro a 2·hb (sin efecto punta)
    a: float = 1.0           # factor de decaimiento de σz (1 si hs ≥ hb + TBD·LB)
    syc: float = 0.0         # término constante de σy' (0: σy sin aumento)
    r0: float = 0.0          # radio de dilución (m), solo Schulman-Scire
    ly: float = 0.0          # longitud de la fuente lineal equivalente (m)
    sy0: float = 0.0         # σ iniciales del puff (crecimiento virtual desde 10·esc); 0 = mínimo
    sz0: float = 0.0
    clase: int = 4           # clase de estabilidad y uso urbano de la emisión (σ del campo cercano)
    urbano: bool = False


def _dh_chorro_2hb(hs, d, w, ts, tempk, us, clase, hb, zmid, tcol):
    """Elevación del chorro a x = 2·hb ([ISC3] 1.1.4.10.1, ecs. 1-23 a 1-27), sin efecto punta."""
    r = 0.5 * d
    fm = w * w * r * r * tempk / ts
    u = max(us, U_MIN)
    bj = 1.0 / 3.0 + u / w
    x = 2.0 * hb
    dm = 3.0 * d * w / u
    if clase <= 4:
        xm = 4.0 * d * (w + 3.0 * u) ** 2 / (w * u)
        return min((3.0 * fm * min(x, xm) / (bj * bj * u * u)) ** (1.0 / 3.0), dm)
    s = G / t_altura(hs, zmid, tcol) * dthdz(hs, DZ_GRAD, zmid, tcol)
    sq = math.sqrt(s)
    xm = 0.5 * math.pi * u / sq
    dh = (3.0 * fm * math.sin(min(x, xm) * sq / u) / (bj * bj * u * sq)) ** (1.0 / 3.0)
    return min(dh, dm)


def isc(hs, d, w, ts, tempk, us, clase, hb, hw, tbd, zmid, tcol, urbano, symin, szmin):
    """Efecto edificio ISC para la hora: devuelve Estela (idw = 0 si no hay efecto)."""
    e = Estela(hb=hb, hw=hw, clase=min(max(clase, 1), 6), urbano=urbano)
    if hb <= 0.0 or hw <= 0.0 or us < U_MIN:
        # sin edificio en el sector, o viento de calma en la chimenea (elevación final inmediata):
        # sin efecto edificio (caja negra: IDW = 0 con us < 1 m/s)
        return e
    lb = min(hb, hw)
    e.heff2 = hs + _dh_chorro_2hb(hs, d, w, ts, tempk, us, clase, hb, zmid, tcol)
    if e.heff2 > hb + 1.5 * lb:
        # por encima de la altura GEP: sin efecto edificio
        return e
    e.idw = 2 if hs < hb + 0.5 * lb else 1
    if hs < hb + tbd * lb:
        if e.heff2 <= hb:
            e.a = 1.0
        elif e.heff2 <= hb + 2.0 * lb:
            e.a = (hb - e.heff2) / (2.0 * lb) + 1.0
        else:
            e.a = 0.0
    e.esc = hb if hw >= hb else hw
    if e.heff2 <= 1.2 * hb:
        e.syc = 0.35 * (hb if (hw >= hb and hw > 5.0 * hb) else hw)
    k = min(max(clase, 1), 6)
    esc = e.esc
    if e.idw == 2:
        # radio de dilución y fuente lineal en x = 3·LB ([ISC3] ecs. 1-28 y 1-29)
        x3 = 3.0 * esc
        sz3 = max(e.a * 0.7 * esc, sigma_dist(x3, k, urbano, 1))
        sy3 = sigma_dist(x3, k, urbano, 0)
        if e.syc > 0.0:
            sy3 = max(sy3, e.syc)
        e.r0 = RAIZ2 * sz3
        # fuente lineal solo si σy está aumentada por el edificio y supera a σz
        e.ly = RAIZ2PI * (sy3 - sz3) if (e.syc > 0.0 and sy3 > sz3) else 0.0
    # σ iniciales: distancia virtual que da en 10·esc la σ del edificio ([ISC3] ecs. 1-39 a 1-41)
    x10 = 10.0 * esc
    szb = e.a * (0.7 * esc + 0.067 * 7.0 * esc)
    xv = x_virtual(szb, k, urbano, 1) - x10
    e.sz0 = sigma_dist(xv, k, urbano, 1) if xv > 0.0 else 0.0
    if e.syc > 0.0:
        xv = x_virtual(e.syc + 0.067 * 7.0 * esc, k, urbano, 0) - x10
        e.sy0 = sigma_dist(xv, k, urbano, 0) if xv > 0.0 else 0.0
    e.sz0 = max(e.sz0, szmin)
    e.sy0 = max(e.sy0, symin)
    return e


@nb.njit(cache=True)
def dwsigs(x, esc, a, syc, k, urb):
    """σy, σz del efecto edificio a la distancia x del origen ([ISC3] ecs. 1-37 a 1-46): la mayor de la
    del edificio y la ambiental, en x ≥ 3·esc; (0, 0) por debajo de 0,99·3·esc (caja negra)."""
    x3 = 3.0 * esc
    if x < 0.99 * x3:
        return 0.0, 0.0
    xx = max(x, x3)
    sz = max(a * (0.7 * esc + 0.067 * (xx - x3)), sigma_dist(xx, k, urb, 1))
    sy = sigma_dist(xx, k, urb, 0)
    if syc > 0.0:
        sy = max(sy, syc + 0.067 * (xx - x3))
    return sy, sz


@nb.njit(cache=True)
def cubica(b, c, rhs):
    """Raíz no negativa de Z³ + b·Z² + c·Z = rhs (b, c ≥ 0), por Newton."""
    if rhs <= 0.0:
        return 0.0
    z = rhs ** (1.0 / 3.0)
    for _ in range(60):
        f = ((z + b) * z + c) * z - rhs
        df = (3.0 * z + 2.0 * b) * z + c
        dz = f / df
        z -= dz
        if z < 0.0:
            z = 0.0
        if abs(dz) <= 1e-12 * max(z, 1e-12):
            break
    return z


@nb.njit(cache=True)
def dh_ss(x, fb, fm, us, bj, sqs, xfb, xfm, r0, ly):
    """Elevación de Schulman-Scire a la distancia x ([ISC3] ecs. 1-30 y 1-31; [UG] ecs. 2-127 a
    2-130): la mayor de la de flotación y la del chorro, cada una con su cúbica."""
    b = 3.0 * ly / (math.pi * BETA) + 3.0 * r0 / BETA
    c = 6.0 * r0 * ly / (math.pi * BETA * BETA) + 3.0 * r0 * r0 / (BETA * BETA)
    zb = 0.0
    if fb > 0.0:
        xb = min(x, xfb)
        rhs = 3.0 * fb * xb * xb / (2.0 * BETA * BETA * us * us * us)
        if sqs > 0.0:
            rhs = min(rhs, 6.0 * fb / (BETA * BETA * us * sqs * sqs))
        zb = cubica(b, c, rhs)
    xm = min(x, xfm)
    if sqs > 0.0:
        rhs = 3.0 * fm * math.sin(xm * sqs / us) / (bj * bj * us * sqs)
    else:
        rhs = 3.0 * fm * xm / (bj * bj * us * us)
    zm = cubica(b, c, rhs)
    return max(zb, zm)
