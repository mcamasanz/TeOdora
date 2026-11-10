# -*- coding: utf-8 -*-
"""Estaciones sobre el agua (SEAn.DAT, NOWSTA > 0) y capa límite marina sobre las celdas de agua.

Reglas (procedencia en FUENTES.md del laboratorio, claves W*):
  - Sin dato de ΔT aire-mar (sin SEA.DAT, o ΔT ausente): neutro, u* = kU/ln(10/z0) con la z0 de
    Hosker ([UG] ec. 2-69: z0 = 2e-6·U^2,5, con U ≥ 1 m/s) y U el viento final de la capa 1;
    L = 9,9e9 [W1].
  - ICOARE = 0 (método OCD «ΔT»): perfil con la misma z0 de Hosker para el viento y la
    temperatura, funciones de Businger-Dyer (Kansas 15/9, estable 4,7, Prandtl 0,74), ΔθV entre
    el aire (θ = Ta + 0,0098·ZOWSTA) y el agua (saturada a SST = Ta − ΔT) con la razón de
    mezcla de Goff-Gratch a 1000 hPa; |L| ≥ 5 [W2].
  - ICOARE = 10 (COARE con Charnock): algoritmo COARE 3.0 (Fairall et al. 2003) con UNA sola
    iteración, viento de la capa 1 a 10 m, T y humedad a ZOWSTA, presión fija de 1013 hPa,
    zi = 600 m, β = 1,2, sin piel fría ni capa cálida; la L es la del principio de la iteración
    y u* la del final; |L| ≥ 5; SST ≥ 270,15 K [W3].
  - Parámetros de cada celda de agua: cada uno, el de la estación sobre el agua más cercana que
    lo tiene [W4]; sin ninguna, por defecto (ΔT: neutro; Ta 288,7 K, HR 100 %, gradientes
    TGDEFB/TGDEFA) [W5].
  - Clase PGT sobre el agua por L: B (−10 < L < 0), C (−25 < L ≤ −10), D (|L| ≥ 25),
    E (10 ≤ L < 25), F (0 < L < 10) [W6].
  - ICOARE = 11 y 12: rugosidad con oleaje de Oost et al. o de Taylor y Yelland con el oleaje por
    defecto de COARE 3.0, calculado con el viento de la primera hora [W13].
  - ICOOL = 1 (piel fría de COARE 3.0, Fairall et al. 1996b): con una sola iteración, la del valor
    inicial del algoritmo, ΔT_piel = 0,3 K y Δq = s·ΔT_piel (Clausius-Clapeyron), en todo el
    cálculo [W17].
"""
import math

import numpy as np

K = 0.4
G = 9.81
EL_NEUTRO = 9.9e9
L_MIN = 5.0
TA_DEF, RH_DEF = 288.7, 100.0       # [V6] tabla 8-14: valores por defecto de los ausentes


# ───────────────────────────── neutro (Hosker) ─────────────────────────────
def z0_hosker(u):
    """[UG] ec. 2-69 con U ≥ 1 m/s [caja negra: dominio de agua con viento de 0,3 a 15 m/s]."""
    return 2.0e-6 * np.maximum(u, 1.0) ** 2.5


def ustar_neutro(u):
    return K * u / np.log(10.0 / z0_hosker(u))


# ───────────────────────────── humedad ─────────────────────────────
def es_goff_gratch(t):
    """Presión de vapor de saturación sobre agua (hPa), Goff-Gratch; t en K."""
    ts = 373.16
    x = (-7.90298 * (ts / t - 1) + 5.02808 * np.log10(ts / t)
         - 1.3816e-7 * (10.0 ** (11.344 * (1 - t / ts)) - 1)
         + 8.1328e-3 * (10.0 ** (-3.49149 * (ts / t - 1)) - 1) + math.log10(1013.246))
    return 10.0 ** x


def rsat(t, p=1000.0):
    e = es_goff_gratch(t)
    return 0.622 * e / (p - e)


# ───────────────────────────── OCD (ICOARE = 0) ─────────────────────────────
def _psi_bd(zl):
    """Businger-Dyer (Kansas): (ψm, ψh) con 15 y 9 inestable, 4,7 estable y Prandtl 0,74."""
    zn = np.minimum(zl, 0.0)
    x = (1 - 15.0 * zn) ** 0.25
    y = (1 - 9.0 * zn) ** 0.5
    pm_i = 2 * np.log((1 + x) / 2) + np.log((1 + x * x) / 2) - 2 * np.arctan(x) + np.pi / 2
    ph_i = 2 * np.log((1 + y) / 2)
    zp = np.maximum(zl, 0.0)
    return np.where(zl < 0, pm_i, -4.7 * zp), np.where(zl < 0, ph_i, -4.7 / 0.74 * zp)


def ocd(u, ta, dt, rh, zt):
    """Método OCD: (u*, L, flujo de flotabilidad cinemático w'θv' (K m/s), z0) [W2]."""
    u = np.asarray(u, float)
    ts = ta - dt
    ra = rh / 100.0 * rsat(ta)
    rs = rsat(ts)
    tha = ta + 0.0098 * zt
    d = tha * (1 + 0.61 * ra) - ts * (1 + 0.61 * rs)
    z0 = z0_hosker(u)
    lu = np.log(10.0 / z0)
    lt = np.log(zt / z0)
    ds = np.where(d == 0, 1e-12, d)
    el = 0.74 * ta * u * u * lt / (G * ds * lu * lu)
    for _ in range(200):
        pm, _ = _psi_bd(10.0 / el)
        _, ph = _psi_bd(zt / el)
        nuevo = 0.74 * ta * u * u * (lt - ph) / (G * ds * (lu - pm) ** 2)
        if np.all(np.abs(nuevo - el) <= 1e-9 * np.abs(el)):
            el = nuevo
            break
        el = 0.5 * el + 0.5 * nuevo
    el = np.where(np.abs(el) < L_MIN, np.copysign(L_MIN, el), el)
    pm, _ = _psi_bd(10.0 / el)
    ust = K * u / (lu - pm)
    flujo = -ta * ust ** 3 / (K * G * el)
    el = np.where((d == 0) | (np.abs(el) > 1.0e4), EL_NEUTRO, el)
    return ust, el, flujo, z0


# ───────────────────────────── COARE (ICOARE = 10) ─────────────────────────────
def _psiu(zet):
    zn = np.minimum(zet, 0.0)
    x = (1 - 16.0 * zn) ** 0.25
    psik = 2 * np.log((1 + x) / 2) + np.log((1 + x * x) / 2) - 2 * np.arctan(x) + 2 * np.arctan(1.0)
    y = (1 - 10.15 * zn) ** (1 / 3)
    psic = (1.5 * np.log((1 + y + y * y) / 3) - math.sqrt(3) * np.arctan((1 + 2 * y) / math.sqrt(3))
            + 4 * np.arctan(1.0) / math.sqrt(3))
    f = zn * zn / (1 + zn * zn)
    zp = np.maximum(zet, 0.0)
    c = np.minimum(50.0, 0.35 * zp)
    est = -((1 + zp) + 0.6667 * (zp - 14.28) / np.exp(c) + 8.525)
    return np.where(zet < 0, (1 - f) * psik + f * psic, est)


def _psit(zet):
    zn = np.minimum(zet, 0.0)
    x = (1 - 16.0 * zn) ** 0.5
    psik = 2 * np.log((1 + x) / 2)
    y = (1 - 34.15 * zn) ** (1 / 3)
    psic = (1.5 * np.log((1 + y + y * y) / 3) - math.sqrt(3) * np.arctan((1 + 2 * y) / math.sqrt(3))
            + 4 * np.arctan(1.0) / math.sqrt(3))
    f = zn * zn / (1 + zn * zn)
    zp = np.maximum(zet, 0.0)
    c = np.minimum(50.0, 0.35 * zp)
    est = -((1 + 2.0 / 3.0 * zp) ** 1.5 + 0.6667 * (zp - 14.28) / np.exp(c) + 8.525)
    return np.where(zet < 0, (1 - f) * psik + f * psic, est)


def _qsat_coare(t, p):
    es = 6.112 * np.exp(17.502 * t / (t + 240.97)) * (1.0007 + 3.46e-6 * p)
    return es * 0.622 / (p - 0.378 * es)


SST_MIN = 270.15
P_COARE, ZI_COARE, BETA_COARE = 1013.0, 600.0, 1.2


def _z0_olas(jwave, usr, ut, visa, hwave=None, twave=None):
    """Rugosidad con oleaje de COARE 3.0 (Fairall et al., 2003): jwave = 1 Oost et al. (2002),
    z0 = 50/(2π)·Lp·(u*/cp)^4,5; jwave = 2 Taylor y Yelland (2001), z0 = 1200·Hs·(Hs/Lp)^4,5; más
    0,11 ν/u* en los dos. Olas por defecto: Tp = 0,729 U y Hs = 0,018 U² (1 + 0,015 U) [W13]."""
    if twave is None or hwave is None:
        hwave, twave = olas_por_defecto(ut)
    cwave = G * twave / (2.0 * math.pi)
    lwave = cwave * twave
    if jwave == 1:
        return 50.0 / (2.0 * math.pi) * lwave * (usr / cwave) ** 4.5 + 0.11 * visa / usr
    return 1200.0 * hwave * (hwave / lwave) ** 4.5 + 0.11 * visa / usr


DTER0 = 0.3      # K, valor inicial del salto de la piel fría en COARE 3.0 [W17]


def coare(u, ta, dt, rh, zt, zu=10.0, jwave=0, hwave=None, twave=None, jcool=0):
    """COARE 3.0 con una iteración [W3]. Devuelve (u*, L, w'θv' (K m/s), z0). jwave: 0 Charnock,
    1 Oost et al., 2 Taylor y Yelland (ICOARE = 10, ±11, ±12) [W13]. jcool = 1 (ICOOL): piel fría
    con el valor inicial de COARE 3.0, que con una sola iteración no llega a actualizarse: la
    temperatura de la superficie baja 0,3 K y su humedad wetc·0,3 (Fairall et al. 1996b, ec. 12;
    caja negra: boya con U de 1 a 20 m/s y ΔT de −3 a 2 K, también de noche, mismo error que sin
    piel fría) [W17]."""
    u = np.asarray(u, float)
    t = ta - 273.15
    tsk = np.maximum(ta - dt, SST_MIN)
    ts = tsk - 273.15
    zq = zt
    von, tdk, p = 0.4, 273.16, P_COARE
    q = rh / 100.0 * _qsat_coare(t, p)
    qs = 0.98 * _qsat_coare(ts, p)
    visa = 1.326e-5 * (1 + 6.542e-3 * t + 8.301e-6 * t * t - 4.84e-9 * t ** 3)
    ddt = ts - t - 0.0098 * zt
    dq = qs - q
    if jcool:
        # piel fría: dter = 0,3 K y dqer = wetc·dter, wetc = 0,622·Le·qs/(R·Ts²) [W17]
        le = (2.501 - 0.00237 * ts) * 1e6
        wetc = 0.622 * le * qs / (287.1 * (ts + tdk) ** 2)
        ddt = ddt - DTER0
        dq = dq - wetc * DTER0
    tak = t + tdk
    ug = 0.5
    ut = np.sqrt(u * u + ug * ug)
    u10 = ut * math.log(10 / 1e-4) / np.log(zu / 1e-4)
    usr = 0.035 * u10
    zo10 = 0.011 * usr * usr / G + 0.11 * visa / usr
    cd10 = (von / np.log(10 / zo10)) ** 2
    ct10 = 0.00115 / np.sqrt(cd10)
    zot10 = 10 / np.exp(von / ct10)
    cd = (von / np.log(zu / zo10)) ** 2
    ct = von / np.log(zt / zot10)
    cc = von * ct / cd
    ribcu = -zu / ZI_COARE / 0.004 / BETA_COARE ** 3
    ribu = -G * zu / tak * (ddt + 0.61 * tak * dq) / ut ** 2
    zetu = np.where(ribu < 0, cc * ribu / (1 + ribu / ribcu), cc * ribu * (1 + 27 / 9 * ribu / cc))
    l10 = zu / zetu
    usr = ut * von / (np.log(zu / zo10) - _psiu(zu / l10))
    tsr = -ddt * von / (np.log(zt / zot10) - _psit(zt / l10))
    qsr = -dq * von / (np.log(zq / zot10) - _psit(zq / l10))
    charn = np.clip(0.011 + (ut - 10) / 8 * 0.007, 0.011, 0.018)
    # una sola iteración [caja negra: barrido casi neutro de 0,5 a 25 m/s]
    zet = von * G * zu / tak * (tsr * (1 + 0.61 * q) + 0.61 * tak * qsr) / (usr * usr) / (1 + 0.61 * q)
    if jwave == 0:
        zo = charn * usr * usr / G + 0.11 * visa / usr
    else:
        zo = _z0_olas(jwave, usr, ut, visa, hwave, twave)
    rr = zo * usr / visa
    el = zu / zet
    zoq = np.minimum(1.15e-4, 5.5e-5 / rr ** 0.6)
    usr = ut * von / (np.log(zu / zo) - _psiu(zu / el))
    tsr = -ddt * von / (np.log(zt / zoq) - _psit(zt / el))
    qsr = -dq * von / (np.log(zq / zoq) - _psit(zq / el))
    flujo = -usr * (tsr + 0.61 * tak * qsr)
    el = np.where(np.abs(el) < L_MIN, np.copysign(L_MIN, el), el)
    el = np.where(np.abs(el) > 1.0e5, 1.0e4, el)
    return usr, el, flujo, zo


def pgt_agua(el):
    """Clase PGT sobre el agua por la longitud de Monin-Obukhov [W6]."""
    return np.select([(el < 0) & (el > -10.0), (el < 0) & (el > -25.0), (el > 0) & (el < 10.0),
                      (el > 0) & (el < 25.0)], [2, 3, 6, 5], 4)


# ───────────────────────────── estaciones ─────────────────────────────
CAMPOS = ("x", "y", "lon", "z", "dT", "Ta", "rh", "zi", "tgb", "tga", "ws", "wd")


class EstacionesMar:
    """Datos de las estaciones sobre el agua de cada hora: el registro cuyo periodo contiene la
    hora (si falta, el original se detiene) [V6] sec. 8.5; caja negra."""

    def __init__(self, ficheros, p):
        self.est = ficheros
        self.p = p
        self.n = len(ficheros)
        self.ids = [f["id"] for f in ficheros]
        self.nombres = [f["nombre"] for f in ficheros]

    def hora(self, t):
        a = np.full((self.n, len(CAMPOS)), np.nan)
        for q, f in enumerate(self.est):
            reg = [r for r in f["registros"] if r[0] <= t <= r[1]]
            if not reg:
                raise ValueError("SEA.DAT de la estación %d sin datos para %s (el original se "
                                 "detiene: «required date/hour not found»)" % (f["id"], t))
            a[q] = reg[-1][2]
        d = {c: a[:, i] for i, c in enumerate(CAMPOS)}
        d["Ta_def"] = np.where(np.isnan(d["Ta"]), TA_DEF, d["Ta"])
        d["rh_def"] = np.where(np.isnan(d["rh"]), RH_DEF, d["rh"])
        d["tga_def"] = np.where(np.isnan(d["tga"]), self.p.get("TGDEFA", -0.0045), d["tga"])
        d["tgb_def"] = np.where(np.isnan(d["tgb"]), self.p.get("TGDEFB", -0.0098), d["tgb"])
        return d


def mas_cercana(dist, valor, defecto=np.nan):
    """Valor en cada celda de la estación sobre el agua más cercana que lo tiene (dist: (n, ny,
    nx)); sin ninguna, `defecto` [caja negra: ΔT ausente en la boya más cercana -> la siguiente]
    [W4, W5]."""
    ok = ~np.isnan(valor)
    if not ok.any():
        return np.full(dist.shape[1:], defecto)
    d = np.where(ok[:, None, None], dist, np.inf)
    return valor[np.argmin(d, axis=0)]


def olas_por_defecto(u):
    """Oleaje por defecto de COARE 3.0 (Tp = 0,729 U, Hs = 0,018 U² (1 + 0,015 U)) con U el
    viento de la capa 1 (sin la ráfaga de COARE); el original lo calcula con el viento de la
    PRIMERA hora y lo conserva toda la corrida [caja negra: el periodo deducido de u* con viento
    de 2 a 20 m/s es constante e igual a 0,729 × el viento de la primera hora] [W13]."""
    ut = np.asarray(u, float)
    return 0.018 * ut * ut * (1.0 + 0.015 * ut), 0.729 * ut


def flujos(icoare, u, ta, dt, rh, zt, olas=None, icool=0):
    """u*, L, w'θv' y z0 sobre el agua; donde falta ΔT, neutro de Hosker [W1-W3]. icoare 11 y
    12: COARE con el oleaje (Hs, Tp) de `olas` [W13]; icool: piel fría de COARE [W17]."""
    u = np.asarray(u, float)
    neutro = np.isnan(dt)
    dts = np.where(neutro, 0.0, dt)
    if icoare == 0:
        ust, el, fl, z0 = ocd(u, ta, dts, rh, zt)
    elif abs(icoare) in (11, 12):
        hw, tw = olas if olas is not None else olas_por_defecto(u)
        ust, el, fl, z0 = coare(u, ta, dts, rh, zt, jwave=abs(icoare) - 10, hwave=hw, twave=tw,
                                jcool=icool)
    else:
        ust, el, fl, z0 = coare(u, ta, dts, rh, zt, jcool=icool)
    ust = np.where(neutro, ustar_neutro(u), ust)
    el = np.where(neutro, EL_NEUTRO, el)
    fl = np.where(neutro, 0.0, fl)
    z0 = np.where(neutro, z0_hosker(u), z0)
    return ust, el, fl, z0
