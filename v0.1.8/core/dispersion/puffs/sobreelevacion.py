# -*- coding: utf-8 -*-
"""Sobreelevación de fuentes puntuales: Briggs (flotación y cantidad de movimiento), transición,
efecto punta de chimenea y penetración parcial en la inversión.

Fuentes (ver FUENTES.md del laboratorio):
  - [UG] CALPUFF User's Guide v5 (Scire et al., 2000), sec. 2.4: ecs. 2-116 a 2-126 (Briggs, distancia
    de elevación final, estable, calma, efecto punta, penetración parcial de Manins) y sec. 2.2.2
    (dispersión inducida por la flotación, σ = Δh/3,5, con la convención de ISC3).
  - [ISC3] User's Guide for the ISC3 Dispersion Models, vol. II (EPA-454/B-95-003b), sec. 1.1.4:
    formas de Briggs que usa el original (1,6·F^⅓·x^⅔/u, 21,425·F^¾/u, 38,71·F^⅗/u, 3·D·w/u,
    1,5·(Fm/(u·√s))^⅓, 2,6·(F/(u·s))^⅓, xf = 2,0715·u/√s, chorro estable con sin(x·√s/u)).
  - Caja negra (validacion/cajanegra.py, salida de depuración): se elige el mayor de flotación y
    cantidad de movimiento en cada x, cada uno con su distancia final; F y Fm con la temperatura de
    superficie (TEMPK); s con la temperatura 3D a la altura de la chimenea y el gradiente de θ entre
    hs y hs + 100 m (mínimo 0,005 K/m); viento < 1 m/s: elevación final inmediata con u = 1;
    penetración: salto de θ en los 30 m sobre ZI, zp1 = (1 − 0,33·f)·(ZI − hs), techo de la parte
    penetrada ZI + 2·(1 − f)·(ZI − hs), penetración total con 18,75 en vez de 18,25.
"""
import math
from dataclasses import dataclass

import numba as nb

G = 9.80665              # m/s2 (caja negra: distancias finales y elevación de transición)
GAMMA_AD = 0.0098        # K/m: θ = T + 0,0098·z
DTHDZ_MIN = 0.005        # K/m: gradiente mínimo de θ en estable y en el salto de la inversión
DZ_GRAD = 100.0          # m: capa sobre la chimenea en la que se mide el gradiente estable
DZ_SALTO = 30.0          # m: capa sobre ZI en la que se mide el salto de la inversión
U_MIN = 1.0              # m/s: viento mínimo de la elevación (calma: elevación final inmediata)
FB_MIN = 1.0e-10         # m4/s3: flujo de flotación mínimo en la elevación de calma estable


def t_altura(z, zmid, tcol):
    """Temperatura (K) a la altura z: interpolación lineal entre los centros de capa, y
    extrapolación lineal fuera de ellos (caja negra: chimenea de 5 m con la capa 1 más caliente)."""
    n = len(zmid)
    if z <= zmid[0]:
        a, b = 0, 1
    elif z >= zmid[n - 1]:
        a, b = n - 2, n - 1
    else:
        b = next(k for k in range(1, n) if zmid[k] >= z)
        a = b - 1
    return tcol[a] + (tcol[b] - tcol[a]) * (z - zmid[a]) / (zmid[b] - zmid[a])


def dthdz(z0, dz, zmid, tcol):
    """Gradiente de θ (K/m) entre z0 y z0 + dz, con el mínimo DTHDZ_MIN."""
    g = (t_altura(z0 + dz, zmid, tcol) - t_altura(z0, zmid, tcol)) / dz + GAMMA_AD
    return max(g, DTHDZ_MIN)


@dataclass
class Elevacion:
    hs: float = 0.0          # altura de salida (m) tras el efecto punta
    fb: float = 0.0          # flujo de flotación (m4/s3)
    fm: float = 0.0          # flujo de cantidad de movimiento (m4/s2)
    us: float = 1.0          # viento de la elevación (m/s, ≥ 1)
    bj: float = 1.0          # coeficiente de arrastre del chorro, 1/3 + us/w
    sqs: float = 0.0         # √s (1/s); 0 en neutra/inestable
    xfb: float = 0.0         # distancia final de flotación (m)
    xfm: float = 0.0         # distancia final de cantidad de movimiento (m)
    dhbf: float = 0.0        # elevación final de flotación (m)
    dhmf: float = 0.0        # elevación final de cantidad de movimiento (m)
    dm: float = 0.0          # tope del chorro, 3·D·w/us (m)
    xf: float = 0.0          # distancia a la elevación final (XFINAL); 0 = inmediata
    dhf: float = 0.0         # elevación final efectiva (m), ya recortada por la penetración
    cod: int = 1             # 1 dentro de la capa de mezcla, 5 penetración parcial, 3 por encima
    qfrac: float = 1.0       # fracción de la masa bajo la tapa (QM/Q)
    zimax: float = 0.0       # techo de la parte penetrada (m); 0 = sin tapa propia
    zref: float = 0.0        # tapa de reflexión de la parte de abajo (m)
    zp: float = 0.0          # altura de penetración de Manins sobre hs' (m), solo código 3
    ss: int = 0              # 1: elevación de Schulman-Scire (efecto edificio, edificios.dh_ss)
    r0: float = 0.0          # radio de dilución (m)
    ly: float = 0.0          # longitud de la fuente lineal (m)


def _estable(e, hs, d, w, zmid, tcol, calma):
    """Elevaciones finales en estable (clases E-F, o chimenea por encima de ZI)."""
    s = G / t_altura(hs, zmid, tcol) * dthdz(hs, DZ_GRAD, zmid, tcol)
    e.sqs = math.sqrt(s)
    u = e.us
    calm_b = 4.0 * e.fb ** 0.25 * s ** -0.375 if e.fb > 0.0 else 0.0
    if calma:
        # en calma el flujo de flotación no baja de FB_MIN = 1e-10 m4/s3 (caja negra: chimenea sin
        # flotación, Ts = Ta, con elevación de 0,33 m = 4·FB_MIN^¼·s^−⅜ en clase F)
        e.dhbf, e.xfb = 4.0 * max(e.fb, FB_MIN) ** 0.25 * s ** -0.375, 0.0
    else:
        e.dhbf = min(2.6 * (e.fb / (u * s)) ** (1.0 / 3.0), calm_b) if e.fb > 0.0 else 0.0
        e.xfb = 2.0715 * u / e.sqs
    e.dm = 3.0 * d * w / u
    e.dhmf = min(1.5 * (e.fm / (u * e.sqs)) ** (1.0 / 3.0), e.dm)
    e.xfm = 0.5 * math.pi * u / e.sqs


def _neutra(e, d, w):
    """Elevaciones finales en neutra/inestable (clases A-D)."""
    u = e.us
    if e.fb > 0.0:
        xs = 14.0 * e.fb ** 0.625 if e.fb <= 55.0 else 34.0 * e.fb ** 0.4
        e.xfb = 3.5 * xs
        e.dhbf = 1.6 * e.fb ** (1.0 / 3.0) * e.xfb ** (2.0 / 3.0) / u
    e.dm = 3.0 * d * w / u
    e.dhmf = e.dm
    e.xfm = 4.0 * d * (w + 3.0 * u) ** 2 / (w * u) if w > 0.0 else 0.0


def elevacion(hs, d, w, ts, tempk, us, clase, zi, zmid, tcol, mtip=1, mpartl=1, ss=None, fmfac=1.0):
    """Sobreelevación de una fuente puntual para la hora: devuelve Elevacion.
    us: viento de la capa CALMET que contiene hs; clase: PGT de la celda de la fuente; zi: altura de
    mezcla ya acotada; zmid, tcol: centros de capa y temperaturas 3D de la celda; ss: (R0, Ly) si la
    chimenea está en la estela con Schulman-Scire (elevación reducida por la dilución inicial, con
    las mismas distancias finales; edificios.py)."""
    e = Elevacion()
    # efecto punta de chimenea ([UG] ec. 2-121)
    e.hs = hs
    # con FMFAC la velocidad de salida efectiva del efecto punta es w·FMFAC (caja negra: TIPDW = 3 m
    # con FMFAC = 0 y D = 1 m)
    we = w * fmfac
    if mtip and us > 0.0 and we / us < 1.5:
        e.hs = max(hs + 2.0 * d * (we / us - 1.5), 0.0)
    r = 0.5 * d
    e.fb = max(G * w * r * r * (ts - tempk) / ts, 0.0)
    # FMFAC (0 o 1) reduce el flujo de cantidad de movimiento (sombreretes; [V6] tabla 9-3)
    e.fm = w * w * r * r * tempk / ts * fmfac
    calma = us < U_MIN
    e.us = max(us, U_MIN)
    e.bj = 1.0 / 3.0 + e.us / w
    estable = clase >= 5
    # sin penetración parcial (MPARTL = 0) no hay tratamiento de chimenea por encima de ZI (caja negra)
    encima = (not estable) and e.hs >= zi and mpartl
    if estable or encima:
        # la chimenea por encima de ZI se trata con las fórmulas estables (caja negra)
        _estable(e, hs, d, we, zmid, tcol, calma)
    else:
        _neutra(e, d, we)
    if ss is not None:
        from .edificios import dh_ss
        e.ss = 1
        e.r0, e.ly = ss
        if calma and e.sqs > 0.0:
            e.xfb = 2.0715 * e.us / e.sqs
        e.dhbf = dh_ss(1e30, e.fb, 0.0, e.us, e.bj, e.sqs, e.xfb, e.xfm, e.r0, e.ly)
        e.dhmf = dh_ss(1e30, 0.0, e.fm, e.us, e.bj, e.sqs, e.xfb, e.xfm, e.r0, e.ly)
    e.dhf = max(e.dhbf, e.dhmf)
    e.xf = 0.0 if calma else max(e.xfb, e.xfm)
    return penetracion(e, estable, encima, zi, zmid, tcol, tempk, mpartl)


def penetracion(e, estable, encima, zi, zmid, tcol, tempk, mpartl=1):
    """Código del puff y reparto de la masa por la penetración en la inversión ([UG] sec. 2.4.3;
    caja negra). Con e.ss (Schulman-Scire o PRIME) se fijan el código y la fracción, pero la
    elevación e.dhf no se recorta."""
    if estable:
        return e
    if encima:
        e.cod, e.qfrac, e.zimax, e.zref = 3, 0.0, zi, zi
        return e
    # penetración parcial en la inversión ([UG] sec. 2.4.3; caja negra)
    if not mpartl:
        # MPARTL = 0: elevación completa; si acaba por encima de ZI, toda la masa por encima (código 3)
        # (caja negra)
        if e.hs + e.dhf > zi:
            e.cod, e.qfrac, e.zimax, e.zref = 3, 0.0, zi, zi
        return e
    dz = zi - e.hs
    if e.fb <= 0.0:
        # sin flotación no hay penetración parcial: o toda dentro o toda por encima
        if e.hs + e.dhf > zi:
            e.cod, e.qfrac, e.zimax, e.zref = 3, 0.0, zi, zi
        return e
    salto = dthdz(zi, DZ_SALTO, zmid, tcol) * DZ_SALTO
    bi = G * salto / tempk
    p = e.fb / (e.us * bi * dz * dz)
    if p < 0.08:
        f = 1.0
    elif p <= 0.3:
        f = 0.08 / p - p + 0.08
    else:
        f = 0.0
    # con Schulman-Scire (efecto edificio) se fijan el código y la fracción, pero la elevación no
    # se recorta (caja negra)
    if f > 0.0:
        if not e.ss:
            e.dhf = min(e.dhf, (1.0 - 0.33 * f) * dz)
        if f < 1.0:
            e.cod, e.qfrac = 5, f
            e.zimax, e.zref = zi + 2.0 * (1.0 - f) * dz, zi
    else:
        sp = G / tempk * salto / DZ_SALTO
        zp = (1.8 * dz ** 3 + 18.75 * e.fb / (e.us * sp)) ** (1.0 / 3.0)
        e.zp = zp
        if not e.ss:
            e.dhf = min(e.dhf, zp)
        e.cod, e.qfrac, e.zimax, e.zref = 3, 0.0, zi, zi
    return e


@nb.njit(cache=True)
def dh_trans(x, fb, fm, us, bj, sqs, xfb, xfm, dhbf, dhmf, dm, dhf):
    """Elevación de transición (m) a la distancia x: la mayor de la de flotación (1,6·F^⅓·x^⅔/u
    hasta xfb) y la del chorro (neutra: (3·Fm·x/(βj²·u²))^⅓; estable: con sin(x·√s/u); hasta xfm,
    con el tope 3·D·w/u), recortada a la elevación final efectiva dhf (caja negra)."""
    if x <= 0.0:
        return 0.0
    if x < xfb:
        b = 1.6 * fb ** (1.0 / 3.0) * x ** (2.0 / 3.0) / us
        b = min(b, dhbf)
    else:
        b = dhbf
    if x < xfm:
        if sqs > 0.0:
            m = (3.0 * fm * math.sin(x * sqs / us) / (bj * bj * us * sqs)) ** (1.0 / 3.0)
        else:
            m = (3.0 * fm * x / (bj * bj * us * us)) ** (1.0 / 3.0)
        m = min(m, dm)
    else:
        m = dhmf
    return min(max(b, m), dhf)
