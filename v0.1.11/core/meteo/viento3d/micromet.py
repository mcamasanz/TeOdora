# -*- coding: utf-8 -*-
"""Micrometeorología sobre tierra: radiación, flujos, u*, L, alturas de mezcla, w* y clase PGT.

Fuentes ([UG] sec. 2.3.1 y caja negra; ver FUENTES.md del laboratorio):
  - Radiación solar (ec. 2-47) y neta (ec. 2-46) de Holtslag y van Ulden con las constantes de
    la tabla 2-2; flujo sensible diurno del balance de energía (ec. 2-48).
  - Día (Qh > 0): u* y L por iteración (ec. 2-49, 2-50, ψm de Dyer y Hicks), 5 iteraciones
    desde neutro.
  - Noche: método de Venkatram / Weil y Brower (ec. 2-51 a 2-57), θ* = mín(θ1, θ2); u* ≥ 0,05.
  - Altura de mezcla convectiva de Maul-Carson (ec. 2-58, 2-59) con flujo efectivo
    Qh − THRESHL·h y ψ1 medido en la columna de la hora; mecánica (ec. 2-60) con la misma ψ1;
    estable mín(ec. 2-63, 2-64); acotada a [ZIMIN, ZIMAX].
  - Clase PGT por el método de Turner (viento a 10 m en nudos e índice de radiación neta).
  - Agua sin estaciones sobre el agua: neutro con la z0 de Hosker; con ellas, ver mar.py y la
    altura convectiva sobre el agua de crece_agua.
  - IMIXH = ±2: crecimiento convectivo de Batchvarova y Gryning (crece_bg) [M12].
"""
import math

import numpy as np

try:
    from numba import njit
except ImportError:                     # pragma: no cover
    def njit(*a, **k):
        return (lambda f: f) if not a or not callable(a[0]) else a[0]

K = 0.4
G = 9.81
CP = 996.0
SIG = 5.67e-8
C1, C2, C3 = 5.31e-13, 60.0, 0.12
A1, A2, B1, B2 = 990.0, -30.0, -0.75, 3.4
GAMMA_V = 4.7
USTAR_MIN = 0.05
U_MIN_ESTABLE = 0.5       # m/s, velocidad mínima en el método estable [caja negra]
THETA_USTAR_MAX = 0.05    # K m/s, tope de u*·θ* en el método estable [caja negra]
ZM = 10.0

# Turner: filas por viento en nudos (0-1, 2-3, 4-5, 6, 7, 8-9, 10, 11, >=12), columnas por NRI
TURNER = {-2: [6, 6, 6, 6, 5, 5, 5, 4, 4], -1: [6, 6, 5, 5, 4, 4, 4, 4, 4], 0: [4] * 9,
          1: [3, 3, 4, 4, 4, 4, 4, 4, 4], 2: [2, 2, 3, 3, 3, 3, 4, 4, 4],
          3: [1, 2, 2, 2, 2, 3, 3, 3, 4], 4: [1, 1, 1, 2, 2, 2, 3, 3, 3]}


def radiacion_solar(sinphi, nubes):
    q = (A1 * sinphi + A2) * (1.0 + B1 * np.power(np.clip(nubes, 0, 1), B2))
    return np.maximum(q, 0.0)


def flujo_sensible_diurno(qsw, t, nubes, albedo, bowen, hcg, qf):
    qnet = ((1.0 - albedo) * qsw + C1 * t ** 6 - SIG * t ** 4 + C2 * nubes) / (1.0 + C3)
    return bowen / (1.0 + bowen) * (qnet * (1.0 - hcg) + qf)


def _psim(zl):
    x = np.power(np.maximum(1.0 - 16.0 * zl, 1.0), 0.25)
    return 2 * np.log((1 + x) / 2) + np.log((1 + x * x) / 2) - 2 * np.arctan(x) + np.pi / 2


def ustar_l_diurno(u, z0, qh, t, rho, nit=5):
    u = np.maximum(u, 1e-3)
    lz = np.log(ZM / z0)
    ust = K * u / lz
    el = np.full_like(ust, -1e9)
    for _ in range(nit):
        el = -rho * CP * t * ust ** 3 / (K * G * qh)
        ust = K * u / (lz - _psim(ZM / el) + _psim(z0 / el))
    return ust, el


def ustar_l_estable(u, z0, t, nubes):
    u = np.maximum(u, U_MIN_ESTABLE)
    cdn = K / np.log(ZM / z0)
    th1 = 0.09 * (1.0 - 0.5 * nubes ** 2)
    th2 = t * cdn * u ** 2 / (4.0 * GAMMA_V * ZM * G)
    ths = np.minimum(th1, th2)

    def _ust(ths):
        u02 = GAMMA_V * ZM * G * ths / t
        c = 1.0 - 4.0 * u02 / np.maximum(cdn * u ** 2, 1e-12)
        return cdn * u / 2.0 * (1.0 + np.sqrt(np.maximum(c, 0.0)))
    ust = _ust(ths)
    # tope del flujo de calor con viento fuerte: si u*·θ* > 0,05 K m/s, θ* = 0,05/u* y u* se
    # recalcula una vez con ese θ* [caja negra: viento a 10 m de 3 a 12 m/s y nubosidad 0-1]
    tope = ust * ths > THETA_USTAR_MAX
    if np.any(tope):
        ths = np.where(tope, THETA_USTAR_MAX / np.maximum(ust, 1e-12), ths)
        ust = np.where(tope, _ust(ths), ust)
    ust = np.maximum(ust, USTAR_MIN)
    el = t * ust ** 2 / (K * G * np.maximum(ths, 1e-12))
    return ust, el, ths


def psi1_niveles(zl, tl, h, dzzi, dptmin):
    """Gradiente de θ (= T + 0,0098 z) entre h y h + DZZI en los niveles del pronóstico de la hora
    anterior interpolados a cada celda (zl, tl: (nzp, ny, nx), z sobre el suelo); por debajo del
    primer nivel, θ del primer nivel [caja negra: corridas sintéticas y Lleida]."""
    th = tl + 0.0098 * zl
    a = _interp_niv(zl, th, h)
    b = _interp_niv(zl, th, h + dzzi)
    return np.maximum((b - a) / dzzi, dptmin)


def _interp_niv(zl, th, zq):
    """Interpolación lineal en z por columna (niveles crecientes; extremos constantes)."""
    nz = zl.shape[0]
    k = (zl <= zq[None]).sum(axis=0) - 1
    k = np.clip(k, 0, nz - 2)
    z0 = np.take_along_axis(zl, k[None], 0)[0]
    z1 = np.take_along_axis(zl, (k + 1)[None], 0)[0]
    t0 = np.take_along_axis(th, k[None], 0)[0]
    t1 = np.take_along_axis(th, (k + 1)[None], 0)[0]
    f = np.clip((zq - z0) / (z1 - z0), 0.0, 1.0)
    return t0 + f * (t1 - t0)


def turner(ws10, sin_elev, nubes, techo=None):
    """Clase PGT por Turner. techo: altura de nubes en cientos de pies (ICLOUD=0, estaciones);
    sin ella se comporta como un techo bajo (< 7000 pies) [M7, O15]."""
    kt = np.floor(ws10 * 1.94384 + 0.5).astype(int)
    fila = np.select([kt <= 1, kt <= 3, kt <= 5, kt == 6, kt == 7, kt <= 9, kt == 10, kt == 11],
                     [0, 1, 2, 3, 4, 5, 6, 7], 8)
    dec = np.rint(nubes * 10.0).astype(int)
    el = np.degrees(np.arcsin(np.clip(sin_elev, -1, 1)))
    ic = np.select([el > 60, el > 35, el > 15], [4, 3, 2], 1)
    techo = np.zeros_like(dec) if techo is None else np.asarray(techo)
    rebaja = np.select([techo < 70, techo < 160], [2, 1], 0)
    rebaja = np.where(dec >= 10, np.maximum(rebaja, 1), rebaja)
    nri = np.where(el > 0, np.where(dec <= 5, ic, np.maximum(1, ic - rebaja)),
                   np.where(dec <= 4, -2, -1))
    nri = np.where((dec >= 10) & (techo < 70), 0, nri)
    out = np.zeros_like(kt)
    for n, tab in TURNER.items():
        m = nri == n
        out[m] = np.asarray(tab)[fila[m]]
    return out


@njit(cache=True)
def _promedio(campos, u, v, dx, dt, mnmdav, hafang):
    """Promedio espacial a barlovento ([UG] ec. 2-61, 2-62): cono de semiángulo HAFANG con el
    vértice en la celda y la base centrada a la distancia de Courant eps = |V|·dt/dx (en celdas),
    más un cuadrado de semilado MNMDAV; peso 1/[du² + (1 + dc)²] con du = eps − du a sotavento."""
    nc, ny, nx = campos.shape
    out = np.empty_like(campos)
    tg = math.tan(math.radians(hafang))
    for j in range(ny):
        for i in range(nx):
            s = math.sqrt(u[j, i] ** 2 + v[j, i] ** 2)
            if s > 0:
                ex = u[j, i] / s
                ey = v[j, i] / s
            else:
                ex = 1.0
                ey = 0.0
            eps = s * dt / dx
            r = max(mnmdav, int(math.ceil(eps / math.cos(math.atan(tg)))) + 1)
            sw = 0.0
            acc = np.zeros(nc)
            for dj in range(-r, r + 1):
                jj = j + dj
                if jj < 0 or jj >= ny:
                    continue
                for di in range(-r, r + 1):
                    ii = i + di
                    if ii < 0 or ii >= nx:
                        continue
                    du = -(di * ex + dj * ey)
                    dc = abs(di * ey - dj * ex)
                    tri = (du >= 0.0) and (du <= eps + 1e-9) and (dc <= du * tg + 1e-9)
                    caja = abs(di) <= mnmdav and abs(dj) <= mnmdav
                    if not (tri or caja):
                        continue
                    due = du if du >= 0.0 else eps - du
                    w = 1.0 / (due * due + (1.0 + dc) ** 2)
                    sw += w
                    for c in range(nc):
                        acc[c] += w * campos[c, jj, ii]
            for c in range(nc):
                out[c, j, i] = acc[c] / sw
    return out


class AlturaMezcla:
    """Estado de la altura de mezcla convectiva entre horas (por celda)."""

    def __init__(self, shape, p):
        self.h = np.zeros(shape)
        self.dth = np.zeros(shape)
        self.p = p

    def convectiva(self, qh, t, rho, theta_prev, agua, u_av=None, v_av=None, dx=1.0, dt=3600.0,
                   bg=None):
        """Altura de mezcla convectiva de la hora (antes del módulo de viento). Devuelve
        (h sin promediar, h promediada, ψ1). La promediada se guarda para la hora siguiente.
        bg = (u*, L): crecimiento de Batchvarova y Gryning (IMIXH = ±2) en vez de Maul-Carson."""
        p = self.p
        dia = (qh > 0) & ~agua
        psi = np.maximum((theta_prev(self.h + p["DZZI"]) - theta_prev(self.h)) / p["DZZI"], p["DPTMIN"])
        psi_mec = psi
        if bg is not None:
            # con Batchvarova y Gryning, la ψ1 de la altura mecánica se evalúa desde máx(h, ZIMIN)
            # [caja negra: altura mecánica de la primera hora convectiva] [M12]
            hm = np.maximum(self.h, p["ZIMIN"])
            psi_mec = np.maximum((theta_prev(hm + p["DZZI"]) - theta_prev(hm)) / p["DZZI"], p["DPTMIN"])
        qef = qh - p["THRESHL"] * self.h
        crece = dia & (qef > 0)
        rc = rho * CP
        qe = np.where(crece, qef, 0.0)
        dn = np.sqrt(2.0 * psi * p["CONSTE"] * qe * dt / rc)
        if bg is not None:
            hn = crece_bg(self.h, qh, psi, bg[0], bg[1], t, rho, p["THRESHL"], dt)
        else:
            a = self.h ** 2 + 2.0 * qe * (1.0 + p["CONSTE"]) * dt / (psi * rc) - 2.0 * self.dth * self.h / psi
            hn = np.sqrt(np.maximum(a, 0.0)) + dn / psi
        hraw = np.where(crece, hn, 0.0)
        hraw = np.where(agua, self.h, hraw)            # sobre agua se arrastra la de la hora anterior
        self.dth = np.where(crece, dn, np.where(agua, self.dth, 0.0))
        hav = hraw
        if p.get("IAVEZI", 0) and u_av is not None:
            hav = _promedio(hraw[None], u_av.astype(float), v_av.astype(float), dx, dt,
                            int(p["MNMDAV"]), float(p["HAFANG"]))[0]
        self.h = hav
        return hraw, hav, psi_mec

    def efectiva(self, qh, ust, el, t, hraw, psi, agua, ust_agua, u_av=None, v_av=None, dx=1.0,
                 dt=3600.0, zi_agua=None):
        """Altura de mezcla que se escribe: de día máx(convectiva, mecánica), de noche la estable,
        sobre agua CONSTW·u*/f (o la que se dé en zi_agua); con el promedio espacial a
        barlovento."""
        p = self.p
        dia = (qh > 0) & ~agua
        nb = np.sqrt(G / t * psi)
        hmec = p["CONSTB"] * ust / np.sqrt(p["FCORIOL"] * nb)
        h1 = p["CONSTN"] * ust ** 1.5
        h2 = 0.4 * np.sqrt(ust * np.abs(el) / p["FCORIOL"])
        zi = np.where(dia, np.maximum(hraw, hmec), np.minimum(h1, h2))
        zi = np.clip(zi, p["ZIMIN"], p["ZIMAX"])
        if zi_agua is None:
            zi_agua = np.clip(p["CONSTW"] / p["FCORIOL"] * ust_agua, p["ZIMINW"], p["ZIMAXW"])
        zi = np.where(agua, zi_agua, zi)
        if p.get("IAVEZI", 0) and u_av is not None:
            zi = _promedio(zi[None], u_av.astype(float), v_av.astype(float), dx, dt,
                           int(p["MNMDAV"]), float(p["HAFANG"]))[0]
        return zi


# Sobre agua sin SEA.DAT (diferencia aire-agua desconocida): neutro, u* = kU/ln(10/z0) con la z0 de
# Hosker ([UG] ec. 2-69, U ≥ 1 m/s) [caja negra: el cociente u*/U medido de 0,3 a 15 m/s es
# exactamente el de esta fórmula; la capa 1 debe tener su centro a unos 10 m] [W1].
EL_NEUTRO = 9.9e9


def ustar_agua(u):
    from .mar import ustar_neutro
    return ustar_neutro(u)


def crece_agua(q, h_ant, psi, p, rho, dt=3600.0):
    """Altura convectiva sobre el agua (Maul-Carson, [UG] ec. 2-58, 2-59) con el flujo de
    flotabilidad q (W/m²) de la estación sobre el agua: parte de máx(h anterior, ZIMINW), flujo
    efectivo q − THRESHW·h y el salto de θ de la PROPIA hora; si no crece, 0 (y la hora
    siguiente vuelve a partir de ZIMINW) [caja negra: dominio de agua con ΔT = −3 K durante 12 h,
    THRESHW = 0 y 0,05, gradientes de 0,0008 a 0,0078 K/m (error ≤ 0,2 %)] [W8]."""
    hp = np.maximum(h_ant, p["ZIMINW"])
    rc = rho * CP
    qe = q - p["THRESHW"] * hp
    crece = qe > 0
    qe = np.where(crece, qe, 0.0)
    dn = np.sqrt(2.0 * psi * p["CONSTE"] * qe * dt / rc)
    a = hp ** 2 + 2.0 * qe * (1.0 + p["CONSTE"]) * dt / (psi * rc) - 2.0 * dn * hp / psi
    hn = np.sqrt(np.maximum(a, 0.0)) + dn / psi
    return np.where(crece, hn, 0.0)


BG_A, BG_B, BG_C = 0.2, 2.5, 8.0      # Batchvarova y Gryning (1991)


def crece_bg(h0, q, gam, ust, el, t, rho, thresh, dt=3600.0, npasos=2):
    """Altura convectiva de Batchvarova y Gryning (1991, 1994):
    dh/dt = (w'θ')/γ / {h²/[(1+2A)h − 2BκL] + C u*² T/(γ g [(1+A)h − BκL])}, A = 0,2, B = 2,5, C = 8,
    con el flujo efectivo q − THRESH·h₀ (h₀ la altura al empezar la hora), integrada con dos
    pasos de Euler de media hora desde la altura de la hora anterior ([V6] sec. 1.4.1; caja
    negra: llano con gradiente constante y THRESHL = 0 y 0,05, errores ≤ 2 %) [M12]."""
    h = np.maximum(np.asarray(h0, float), 0.0)
    el = np.minimum(np.asarray(el, float), -1e-6)
    qk = np.maximum(q - thresh * h, 0.0) / (rho * CP)
    for _ in range(npasos):
        den = (h * h / ((1 + 2 * BG_A) * h - 2 * BG_B * K * el)
               + BG_C * ust * ust * t / (gam * G * ((1 + BG_A) * h - BG_B * K * el)))
        h = h + dt / npasos * qk / gam / den
    return h


def wstar(qh, hconv, t, rho):
    v = G * np.maximum(qh, 0.0) * hconv / (t * rho * CP)
    return np.where((qh > 0) & (hconv > 0), np.cbrt(v), 0.0)
