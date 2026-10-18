# -*- coding: utf-8 -*-
"""Efecto edificio PRIME (MBDW = 2): sobreelevación numérica con la estela, tablas de σ de la estela
y de la cavidad, fracción capturada por la cavidad y concentración en la zona de la cavidad.

Fuentes (ver FUENTES.md del laboratorio):
  - [PRIME-JAWMA] Schulman, Strimaitis y Scire (2000), JAWMA 50:378-390: formulación de PRIME
    (escalas de la estela, cavidad, crecimiento de σ en la estela, reparto de masa).
  - [AERMOD-PRIME dominio público] traducción del proyecto de prime.f de AERMOD (EPA, dominio
    público), lagaus/dispersion/penacho/estela_edificio.py: NUMRISE (RATE, LUMP, MARCHING,
    UNLUMP), WAKE_SCALES, POSITION, ZSTREAM, WAKE_U, WAKE_TURB, WAKE_XA, WAKE_DIM, WAKE_SIG,
    WAKE_CAV0, WAKE_DFSN, WAKE_FQC, CAV_SRC, CAVITY_HT, FRGAUSS, ERFDIF, NUMGRAD, WAKE_XSIG. Se
    adaptan a CALPUFF las partes que dependen del modelo anfitrión.
  - Caja negra (salida LDEBUG=T del original, validacion/exp_edificio.py `exp_prime_*`; detalle en
    FUENTES.md del laboratorio): perfil de las capas CALMET (viento lineal desde 0 bajo el primer nivel,
    dθ/dz ≥ 0), σ ambientales de las curvas de dispersión (PG o McElroy-Pooler) en la distancia a la
    chimenea, intensidades de turbulencia ambiental por clase, w/u ≥ 4 en la distancia final del
    chorro, crecimiento ambiental con distancias virtuales (pueden ser negativas), submuestreo de
    las tablas en reales de 4 bytes, filas a barlovento de la entrada en la estela, FQCAV < 10⁻³ → 0,
    CAV_SRC también con FQCAV = 0, zona y exclusión de CAV_CONC, término vertical de CAV_CONC con
    la tapa y la masa penetrada, g = 9,807 m/s² en los flujos.

Las matrices llevan índice 1..N como el original (el elemento 0 no se usa).
"""
import math

import numpy as np

from .sigmas import sigma_dist, x_virtual

# constantes de la difusión en la estela (PRIME1) y de la sobreelevación numérica (NUMPR1)
AFAC = 1.3
XBYRMAX = 15.0
WIZ0 = 0.06
WIY0 = 0.08
WFZ = 1.7
WFY = 1.7
DUA_UA = 0.7
XDECAY = 2.0 / 3.0
XDECAYI = 1.5
GRAVI = 9.807
RGAS = 287.026
ZMIN = 0.001
DS0 = 1.0
NSTEP = 1
SLAST = 5000.0
RP = 9.1e-11
ADIA = 0.0098
MXNTR = 50
MXNW = 5000
THIRD = 1.0 / 3.0

# intensidades de turbulencia ambiental por clase de estabilidad (caja negra: distancias de
# transición de la estela al crecimiento ambiental y tasas de crecimiento de σ sobre el tejado)
AMBIZ_RUR = (0.20, 0.12, 0.08, 0.06, 0.03, 0.016)
AMBIY_RUR = (0.22, 0.16, 0.11, 0.08, 0.06, 0.04)
AMBIZ_URB = (0.24, 0.24, 0.20, 0.14, 0.08, 0.08)
AMBIY_URB = (0.32, 0.32, 0.22, 0.16, 0.11, 0.11)


class Estado:
    """Variables de los módulos de PRIME para una fuente y hora."""

    def __init__(self, hb, wb, lb, xbadj, ybadj, clase, urbano, ub, urh, perfil):
        self.HB, self.WB, self.XLB = hb, wb, lb
        self.XBADJ, self.YBADJ = xbadj, ybadj
        self.clase = min(max(int(clase), 1), 6)
        self.urbano = bool(urbano)
        self.UB, self.URH = ub, urh
        self.perfil = perfil
        k = self.clase - 1
        self.AMBIZ = (AMBIZ_URB if self.urbano else AMBIZ_RUR)[k]
        self.AMBIY = (AMBIY_URB if self.urbano else AMBIY_RUR)[k]
        n = MXNW + 2
        self.XWAK = np.zeros(n)
        self.SZWAK = np.zeros(n)
        self.SYWAK = np.zeros(n)
        self.DRWAK = np.zeros(n)
        self.XCAV = np.zeros(n)
        self.SZCAV = np.zeros(n)
        self.SYCAV = np.zeros(n)
        self.NWAK = 1
        self.NCAV = 1
        self.FQCAV = 0.0
        # distancias virtuales del crecimiento ambiental (estela desde la chimenea; cavidad desde
        # su fuente)
        self.XVZ = 0.0
        self.XVY = 0.0
        self.XVZC = 0.0
        self.XVYC = 0.0
        self.DISTC = 0.0
        self.FINO = None
        self.LWAK = self.LCAV = self.LINWAKE = False
        self.RB = self.HR = self.XLR = self.XLC = 0.0
        wake_scales(self)


# ════════════════════════════════════ σ ambientales y turbulencia ════════════════════════════════
def sigzpr(s, x, z=0.0):
    """σz ambiental a la distancia x de la chimenea (curvas de dispersión de CALPUFF)."""
    return sigma_dist(max(x, 1e-6), s.clase, s.urbano, 1)


def sigypr(s, x, z=0.0):
    """σy ambiental a la distancia x de la chimenea."""
    return sigma_dist(max(x, 1e-6), s.clase, s.urbano, 0)


def _xv(s, sig, eje):
    """Distancia (m) a la que la curva ambiental da `sig` (0 si sig ≤ 0)."""
    if sig <= 0.0:
        return 0.0
    x = x_virtual(sig, s.clase, s.urbano, eje)
    return max(x, 0.0)


def _sucesion(ntot, ntr, agrupada=False):
    """Índices reales rn del submuestreo de paso creciente (más puntos cerca de la fuente), con la
    acumulación en reales de 4 bytes del original (caja negra: rn = 21 exacto queda en 20,999998
    y se toma el índice anterior)."""
    if agrupada:
        # trayectoria de NUMRISE: rn + (1 + (in − 1)·deln) (caja negra)
        deln = np.float32(np.float32(2 * (ntot - ntr)) / np.float32(ntr * (ntr - 1)))
        rn = np.float32(1.0)
        out = [0.0, 1.0]
        for i in range(2, ntr):
            rn = np.float32(rn + np.float32(np.float32(1.0) + np.float32(np.float32(i - 1) * deln)))
            out.append(float(rn))
        return out
    deln = np.float32(2.0) * np.float32(ntot - ntr) / np.float32(ntr * (ntr - 1))
    rn = np.float32(1.0)
    out = [0.0, 1.0]
    for i in range(2, ntr):
        rn = np.float32(np.float32(rn + np.float32(1.0)) + np.float32(np.float32(i - 1) * deln))
        out.append(float(rn))
    return out


def _proximos(ntot, ntr):
    """Índices reales del submuestreo por valores más próximos: in·deln con deln = ntot/ntr en real
    de 4 bytes (caja negra: 10·1,9 queda en 18,9999998 y se toma el índice 18)."""
    deln = float(np.float32(ntot) / np.float32(ntr))
    return [0.0] + [float(i) * deln for i in range(1, ntr)]


def _rpot0(base, expo):
    if base < 0.0:
        return float("nan")
    if base == 0.0 and expo < 0.0:
        return float("inf")
    return base ** expo


# ════════════════════════════════════ escalas y geometría de la estela ═══════════════════════════
def wake_scales(s):
    """WAKE_SCALES: escala R y dimensiones de la cavidad (HR, LR, LC)."""
    if s.HB <= 0.0:
        s.RB = s.HB = s.XLR = s.XLC = 0.0
        return
    rw = s.WB / s.HB
    rl = min(max(s.XLB / s.HB, 0.3), 3.0)
    hh, ww = s.HB, s.WB
    if hh > 8.0 * ww:
        hh = 8.0 * ww
    if ww > 8.0 * hh:
        ww = 8.0 * hh
    s.RB = _rpot0(min(hh, ww), 2.0 * THIRD) * _rpot0(max(hh, ww), THIRD)
    s.XLC = 0.9 * s.RB
    explh = 0.3
    if rw < 1.0:
        explh = max(0.0, 0.3 * (rw - 0.33) / 0.67)
    s.XLR = 1.8 * s.WB / (_rpot0(rl, explh) * (1.0 + 0.24 * rw))
    s.HR = s.HB + 0.22 * s.RB


def wake_dim(x, h, w, r):
    """WAKE_DIM: altura y semianchura de la estela a x de la cara de barlovento."""
    cwkht = 1.2
    xbyr = x / r
    t = h / (cwkht * r)
    dxbyr = xbyr + t * t * t
    hwake = cwkht * r * dxbyr ** THIRD if xbyr > 0.0 else 0.0
    wwake = 0.5 * w + (THIRD * r) * xbyr ** THIRD if xbyr > 0.0 else 0.0
    return hwake, wwake


def cavity_ht(h, w, l, r, lc, lr, hr, x):
    """CAVITY_HT: altura y semianchura de la cavidad a x de la cara de barlovento."""
    zcav = 0.0
    ycav = 0.0
    if x >= (l + lr) or x < 0.0:
        return zcav, ycav
    if x <= r:
        t = x - r
        ycav = (w / 2.0 + r / 3.0) - (t * t) / (3.0 * r)
    else:
        t = (x - r) / (l + lr - r)
        ycav = (w / 2.0 + r / 3.0) * math.sqrt(1.0 - t * t)
    if lc < l:
        if x <= l:
            zcav = h
        else:
            t = (x - l) / lr
            zcav = h * math.sqrt(1.0 - t * t)
    else:
        if x <= 0.5 * r:
            t = x - 0.5 * r
            zcav = hr + 4.0 * (t * t) * (h - hr) / (r * r)
        else:
            t = (x - 0.5 * r) / (l + lr - 0.5 * r)
            zcav = hr * math.sqrt(1.0 - t * t)
    return zcav, ycav


def position(s, x, y, z):
    """POSITION: 1 dentro del edificio, 2 en la cavidad, 3 en la estela lejana, 4 fuera."""
    skin = 0.99998
    if s.HB <= 0.0 or x <= 0.0:
        return 4
    ypos = abs(y)
    rby2 = 0.5 * s.RB
    rby3 = THIRD * s.RB
    wby2 = 0.5 * s.WB
    if x / s.XLB < skin and z / s.HB < skin and ypos / wby2 < skin:
        return 1
    iposy = iposz = 4
    if s.XLC < s.XLB:
        if x < s.XLB:
            if z <= s.HB:
                iposz = 2
        elif x < (s.XLB + s.XLR):
            t = (x - s.XLB) / s.XLR
            if z <= s.HB * math.sqrt(1.0 - t * t):
                iposz = 2
    else:
        if x <= rby2:
            t = x - rby2
            if z <= s.HR + 4.0 * (t * t) * (s.HB - s.HR) / (s.RB * s.RB):
                iposz = 2
        elif x < (s.XLB + s.XLR):
            t = (x - rby2) / (s.XLB + s.XLR - rby2)
            if z <= s.HR * math.sqrt(1.0 - t * t):
                iposz = 2
    if x <= s.RB:
        t = x - s.RB
        if ypos <= (wby2 + rby3) - (t * t) / (3.0 * s.RB):
            iposy = 2
    elif x < (s.XLB + s.XLR):
        t = (x - s.RB) / (s.XLB + s.XLR - s.RB)
        if ypos <= (wby2 + rby3) * math.sqrt(1.0 - t * t):
            iposy = 2
    if iposz == 2 and iposy == 2:
        return 2
    zwake, ywake = wake_dim(x, s.HB, s.WB, s.RB)
    if z <= zwake and ypos <= ywake:
        return 3
    return 4


def zstream(h, w, l, r, lr, hr, x, y, z):
    """ZSTREAM: pendiente media local de las líneas de corriente junto al edificio."""
    if h <= 0.0:
        return 0.0
    dzdx2 = 0.0
    hbyw = h / w
    ypos = abs(y)
    onebyr = 1.0 / r
    wby2 = 0.5 * w
    rby2 = 0.5 * r
    zg = 0.0
    expzg = 0.3
    if hbyw >= 2.0:
        t = 0.5 * hbyw
        expzg = expzg * (t * t)
    if x < -r:
        dzdx2 = 0.0
    elif x < 0.0:
        zslope = 2.0 * (hr - h) * (x + r) * (onebyr * onebyr)
        if z > h:
            t = (z - h + r) * onebyr
            dzdx2 = zslope / (t * t * t)
        elif r <= h and z <= 0.67 * h:
            dzdx2 = 0.0
        elif r <= h and z > 0.67 * h:
            dzdx2 = zslope
        elif r > h and z <= 0.67 * (2.0 * h - r):
            dzdx2 = 0.0
        elif r > h and z > 0.67 * (2.0 * h - r):
            dzdx2 = zslope
    elif x <= rby2:
        zslope = (-(hr - h) * 4.0 * onebyr) * (2.0 * x * onebyr - 1.0)
        if z <= h:
            dzdx2 = zslope
        else:
            t = (z - h + r) * onebyr
            dzdx2 = zslope / (t * t * t)
    elif x <= l + lr:
        t = l - rby2 + lr
        zslope = (hr - h) * (r - 2.0 * x) / (t * t)
        if z > h:
            dzdx2 = zslope / ((z - h + r) * onebyr)
        elif z <= zg:
            dzdx2 = 0.0
        else:
            dzdx2 = zslope * _rpot0((z - zg) / (h - zg), expzg)
    else:
        zslopelr = -2.0 * (hr - h) / (l - rby2 + lr)
        zslope = zslopelr / ((x - (l + lr - r)) * onebyr)
        if z > h:
            dzdx2 = zslope / ((z - h + r) * onebyr)
        elif z <= zg:
            dzdx2 = 0.0
        else:
            dzdx2 = zslope * _rpot0((z - zg) / (h - zg), expzg)
    if ypos > (wby2 + r / 3.0):
        return 0.0
    if ypos <= wby2:
        return dzdx2
    return dzdx2 * (1.0 + (3.0 * onebyr) * (wby2 - ypos))


def wake_u(s, x, y, z):
    """WAKE_U: cociente u(estela)/u(ambiente) y su gradiente vertical."""
    fmin = 0.01
    zcav, ycav = cavity_ht(s.HB, s.WB, s.XLB, s.RB, s.XLC, s.XLR, s.HR, x)
    hwake, wwake = wake_dim(x, s.HB, s.WB, s.RB)
    yabs = abs(y)
    if z >= hwake or yabs >= wwake:
        return 1.0, 0.0
    ymin = max(0.5 * s.WB, wwake - s.RB / 3.0)
    du_ua = DUA_UA
    ydiff = wwake - ymin
    if yabs > ymin and ydiff > 0.0:
        du_ua = DUA_UA * (1.0 - (yabs - ymin) / ydiff)
    xml = max(0.0, x - s.XLB)
    du_ua = du_ua * ((xml + s.RB) / s.RB) ** (-XDECAY)
    if x < s.XLB:
        du_ua = (x / s.XLB) * du_ua
    ucbyua = max(0.0, (1.0 - 2.0 * hwake * du_ua / (hwake + zcav)))
    dufac = 0.0
    if z > zcav:
        dufac = (1.0 - ucbyua) / (hwake - zcav)
    zz = min(z, hwake)
    return max(fmin, (ucbyua + dufac * (zz - zcav))), dufac


def wake_turb(s, xinp, l, rinp):
    """WAKE_TURB: intensidades de turbulencia en la estela a xinp de la cara de barlovento."""
    ambiz, ambiy = s.AMBIZ, s.AMBIY
    fariz = min(WIZ0, ambiz)
    fariy = min(WIY0, ambiy)
    xml = max(0.0, xinp - l)
    xfac = 1.0 / (((xml + rinp) / rinp) ** XDECAY - DUA_UA)
    tiz = fariz * (1.0 + ((WFZ * WIZ0 / fariz - 1.0) + DUA_UA) * xfac)
    tiy = fariy * (1.0 + ((WFY * WIY0 / fariy - 1.0) + DUA_UA) * xfac)
    if xinp < l:
        xfrac = xinp / l
        tiz = ambiz + xfrac * (tiz - ambiz)
        tiy = ambiy + xfrac * (tiy - ambiy)
    return tiz, tiy


def wake_xa(s, l, rinp):
    """WAKE_XA: distancias desde la cara de barlovento a las que la turbulencia de la estela iguala
    la ambiental (limitadas a XBYRMAX escalas R)."""
    ambiz, ambiy = s.AMBIZ, s.AMBIY
    fariz = min(WIZ0, ambiz)
    fariy = min(WIY0, ambiy)
    farizt = max(ambiz, AFAC * fariz)
    fariyt = max(ambiy, AFAC * fariy)
    x0byr = l / rinp - 1.0
    xaz = x0byr + _rpot0(DUA_UA + (WFZ * WIZ0 - fariz * (1.0 - DUA_UA)) / (farizt - fariz), XDECAYI)
    xay = x0byr + _rpot0(DUA_UA + (WFY * WIY0 - fariy * (1.0 - DUA_UA)) / (fariyt - fariy), XDECAYI)
    xbyr = l / rinp + XBYRMAX
    return rinp * min(xbyr, xaz), rinp * min(xbyr, xay)


def wake_sig(x, xd, xold, turbz, turby, szold, syold, h, w, r, zk, yk):
    """WAKE_SIG: σ y dσz/dx en la estela al final de un paso pequeño (zk, yk de entrada/salida)."""
    htwake, hwwake = wake_dim(x, h, w, r)
    fwwake = 2.0 * hwwake
    delx = x - xold
    xstepi = 1.0 / delx
    if x < xd:
        dsz = turbz
        sz = szold + delx * turbz
        sy = syold + delx * turby
    elif xold > xd:
        sz = math.sqrt(szold * szold + delx * zk * turbz * htwake)
        sy = math.sqrt(syold * syold + delx * yk * turby * fwwake)
        dsz = (sz - szold) * xstepi
    else:
        delx = xd - xold
        sigzd = szold + delx * turbz
        sigyd = syold + delx * turby
        zk = 2.0 * sigzd / htwake
        yk = 2.0 * sigyd / fwwake
        delx = x - xd
        sz = math.sqrt(sigzd * sigzd + delx * zk * turbz * htwake)
        sy = math.sqrt(sigyd * sigyd + delx * yk * turby * fwwake)
        dsz = (sz - szold) * xstepi
    return zk, yk, sz, sy, dsz


def wake_cav0(s, sycapt):
    """WAKE_CAV0: σ iniciales de la fuente situada en el suelo de la cavidad."""
    rt2pi = 2.50662827463100
    rt2bypi = 0.797884560802866
    wcapt = min(rt2pi * sycapt, s.WB)
    wscale = min(s.WB, 3.0 * s.HB)
    wscale = max(wscale, THIRD * s.HB)
    wscale = max(wscale, wcapt)
    sycav0 = wscale / rt2pi
    hcav = s.HB if s.XLC < s.XLB else s.HR
    szcav0 = rt2bypi * (s.UB / s.URH) * hcav * THIRD
    return szcav0, sycav0


def numgrad(x, xtr, ztr, ntr):
    """NUMGRAD: interpolación en la tabla de la trayectoria."""
    if x >= xtr[ntr]:
        return float(ztr[ntr])
    for i in range(ntr - 1, 0, -1):
        if x >= xtr[i]:
            ip1 = i + 1
            return float(ztr[ip1] - (ztr[ip1] - ztr[i]) * (xtr[ip1] - x) / (xtr[ip1] - xtr[i]))
    return float(ztr[1])


def wake_drdx(s, x):
    """WAKE_DRDX: ritmo de crecimiento del radio del penacho en la estela."""
    nwak = s.NWAK
    if nwak <= 1 or x > s.XWAK[nwak] or x < s.XWAK[1]:
        return 0.0
    for i in range(nwak - 1, 0, -1):
        if x >= s.XWAK[i]:
            ip1 = i + 1
            return float(s.DRWAK[ip1] - (s.DRWAK[ip1] - s.DRWAK[i]) * (s.XWAK[ip1] - x) /
                         (s.XWAK[ip1] - s.XWAK[i]))
    return float(s.DRWAK[1])


# ════════════════════════════════════ perfil meteorológico (NUMMET / ZMET) ═══════════════════════
class Perfil:
    """Perfil de la celda de la fuente para la sobreelevación numérica (caja negra, NUMMET): niveles
    en los centros de las capas CALMET con su viento y temperatura; gradiente de θ en cada cara
    entre dos centros (las caras extremas copian la vecina); temperatura en el suelo extrapolada de
    las dos primeras capas; viento lineal desde 0 bajo el primer nivel; densidad hidrostática."""

    def __init__(self, zface, ws, tk, plx, rho0=1.1719, ptgrad0=0.0):
        nz = len(ws)
        self.n = nz
        self.z = np.zeros(nz + 1)
        self.u = np.zeros(nz + 1)
        self.t = np.zeros(nz + 1)
        self.r = np.zeros(nz + 1)
        self.zf = np.zeros(nz + 2)
        self.dedz = np.zeros(nz + 2)
        for i in range(nz):
            self.z[i + 1] = 0.5 * (zface[i] + zface[i + 1])
            self.u[i + 1] = ws[i]
            self.t[i + 1] = tk[i]
        for i in range(nz + 1):
            self.zf[i + 1] = zface[i]
        for i in range(2, nz + 1):
            self.dedz[i] = (self.t[i] - self.t[i - 1]) / (self.z[i] - self.z[i - 1]) + ADIA
        self.dedz[1] = self.dedz[2]
        self.dedz[nz + 1] = self.dedz[nz]
        self.t0 = self.t[1] - (self.t[2] - self.t[1]) * self.z[1] / (self.z[2] - self.z[1])
        self.plx = plx
        self.ptgrad0 = ptgrad0
        # densidad: hidrostática con la temperatura media de cada tramo
        p0 = rho0 * RGAS * self.t0
        zp, tp, pp = 0.0, self.t0, p0
        for i in range(1, nz + 1):
            tm = 0.5 * (tp + self.t[i])
            pp = pp * math.exp(-GRAVI * (self.z[i] - zp) / (RGAS * tm))
            zp, tp = self.z[i], self.t[i]
            self.r[i] = pp / (RGAS * self.t[i])
        self.r0 = rho0


def zmet(s, z):
    """ZMET: viento, densidad, temperatura y gradientes a la altura z. Devuelve (ua, ra, ta, dudz,
    dpdz)."""
    f = s.perfil
    n = f.n
    if z <= f.z[1]:
        # bajo el primer nivel, viento lineal desde 0 en el suelo (caja negra)
        zz = max(z, ZMIN)
        ua = f.u[1] * zz / f.z[1]
        dudz = f.u[1] / f.z[1]
        ta = f.t0 + (f.t[1] - f.t0) * z / f.z[1]
        ra = f.r0 + (f.r[1] - f.r0) * z / f.z[1]
        dpdz = f.dedz[1]
    elif z >= f.z[n]:
        ua, ta, ra = f.u[n], f.t[n], f.r[n]
        dudz = (f.u[n] - f.u[n - 1]) / (f.z[n] - f.z[n - 1])
        dpdz = f.dedz[n + 1]
    else:
        i = 1
        while f.z[i + 1] < z:
            i += 1
        w = (z - f.z[i]) / (f.z[i + 1] - f.z[i])
        ua = f.u[i] + w * (f.u[i + 1] - f.u[i])
        ta = f.t[i] + w * (f.t[i + 1] - f.t[i])
        ra = f.r[i] + w * (f.r[i + 1] - f.r[i])
        dudz = (f.u[i + 1] - f.u[i]) / (f.z[i + 1] - f.z[i])
        dpdz = f.dedz[i + 1]
    # gradiente de θ no negativo (caja negra: PTGRAD0 = 0)
    dpdz = max(dpdz, f.ptgrad0)
    return float(ua), float(ra), float(ta), float(dudz), float(dpdz)


# ════════════════════════════════════ sobreelevación numérica (NUMRISE) ══════════════════════════
class _Penacho:
    pass


def _rate(p, ua, dudz, ra, dpdz, ta, drdxa, rhs):
    """RATE: segundos miembros de las ecuaciones del penacho."""
    alpha, beta = 0.11, 0.6
    r = p.R
    rhs[1] = (2.0 * r * ra) * (alpha * abs(p.USC - ua * p.U / p.USC) + beta * abs(ua * math.sin(p.PHI)))
    rhs[1] = max(rhs[1], (2.0 * r * ra) * ua * drdxa)
    tp2 = p.TP * p.TP
    ta2 = ta * ta
    rhs[2] = -(r * r * p.DEN * p.W) * dudz
    rhs[3] = GRAVI * r * r * (ra - p.DEN)
    rhs[4] = -(r * r * p.DEN * p.W) * dpdz - RP * r * (tp2 * tp2 - ta2 * ta2)
    rhs[5] = p.W / p.USC
    rhs[6] = p.U / p.USC
    rhs[7] = p.V / p.USC


def _lump(p, ua, ta, f):
    f[1] = p.DEN * p.USC * p.R * p.R
    f[2] = f[1] * (p.U - ua)
    f[3] = f[1] * p.W
    f[4] = f[1] * (p.TP - ta)
    f[5] = p.Z
    f[6] = p.X
    f[7] = p.Y


def _unlump(p, ua, ta, ra, f):
    p.U = ua + f[2] / f[1]
    p.W = f[3] / f[1]
    p.USC = math.sqrt(p.U * p.U + p.W * p.W)
    p.TP = max(ta + f[4] / f[1], ta - 10.0)
    p.DEN = (ra * ta) / p.TP
    p.R = math.sqrt(f[1] / (p.USC * p.DEN))
    p.PHI = math.atan(p.W / p.U)
    p.Z = f[5]
    p.X = f[6]
    p.Y = f[7]


def _entrada(s, p, h, sz0, sy0):
    """Entrada del eje del penacho en la estela: σ ambientales con la flotación y tablas."""
    xbi = p.X - s.XBADJ
    rise = max(0.0, p.Z - max(h, ZMIN))
    bidsq = (rise / 3.5) ** 2
    if p.X <= 0.0:
        szi = math.sqrt(bidsq + sz0 * sz0)
        syi = math.sqrt(bidsq + sy0 * sy0)
    else:
        szi = math.sqrt(sigzpr(s, p.X) ** 2 + bidsq + sz0 * sz0)
        syi = math.sqrt(sigypr(s, p.X) ** 2 + bidsq + sy0 * sy0)
    s.XENT, s.ZENT, s.RISEENT = p.X, p.Z, rise
    wake_dfsn(s, xbi, szi, syi, p.Z)
    return xbi


def numrise(s, h, reff, texit, wexit, sz0=0.0, sy0=0.0):
    """NUMRISE: sobreelevación numérica con la reducción del viento y la inclinación de las líneas
    de corriente del edificio; al entrar el eje en la estela tabula las σ (WAKE_DFSN). Devuelve las
    tablas de la trayectoria (xtr, ytr, ztr, rtr, htr; índices 1..MXNTR; htr = elevación sin el
    descenso de las líneas de corriente) y fija s.FQCAV."""
    ntr = MXNTR
    xt = np.zeros(MXNW + 2)
    yt = np.zeros(MXNW + 2)
    zt = np.zeros(MXNW + 2)
    rt = np.zeros(MXNW + 2)
    ht = np.zeros(MXNW + 2)
    rhs = [0.0] * 8
    rhstemp = [0.0] * 8
    f = [0.0] * 8
    ftemp = [0.0] * 8
    p = _Penacho()
    nn = 0
    xbi = 0.0
    linwake = False
    p.X = p.Y = p.S = p.V = 0.0
    p.Z = max(h, ZMIN)
    p.R = reff
    p.U = 0.000002
    p.W = wexit
    p.TP = texit
    drdxa = 0.0
    ds = DS0
    zcumul = 0.0
    r15src = s.XBADJ + (s.XLB + 15.0 * s.RB)
    ua0, ra, ta, dudz0, dpdz = zmet(s, p.Z)
    xb = p.X - s.XBADJ
    yb = p.Y - s.YBADJ
    zb = max(p.Z, ZMIN)
    ipositn = position(s, xb, yb, zb)
    ufac, dufac = 1.0, 0.0
    if ipositn < 4:
        ufac, dufac = wake_u(s, xb, yb, zb)
    ua = ufac * ua0
    dudz = ufac * dudz0 + dufac * ua0
    deltat = max(p.TP - ta, 0.0)
    fdum = p.W * p.R * p.R / p.TP
    fb = GRAVI * fdum * deltat
    fm = p.W * fdum * ta
    s.FB, s.FM = fb, fm
    uam = max(ua, 1.0)
    # distancia a la elevación final del chorro con w/u no menor que 4 (caja negra)
    wbyu = max(4.0, p.W / uam)
    t = 1.0 + 3.0 / wbyu
    xmaxm = 8.0 * p.R * wbyu * (t * t)
    if fb <= 0.0:
        xmax = xmaxm
    elif fb < 55.0:
        xmax = max(xmaxm, 49.0 * fb ** 0.625)
    else:
        xmax = 119.0 * fb ** 0.4
    if fb <= 0.0:
        znf = 6.0 * p.R * p.W / uam
    elif fb < 55.0:
        znf = 21.425 * (fb ** 0.75) / uam
    else:
        znf = 38.71 * (fb ** 0.60) / uam
    dmin = 0.5 * max(0.1, znf)
    if ds > dmin:
        ds = dmin
    s.XMAXNUM = xmax
    p.USC = math.sqrt(p.U * p.U + p.W * p.W)
    p.PHI = math.atan(p.W / p.U)
    nnp = 1
    p.DEN = ra * ta / texit
    _lump(p, ua, ta, f)
    zfin = yfin = xfin = rfin = hfin = 0.0
    while True:
        xb = p.X - s.XBADJ
        yb = p.Y - s.YBADJ
        zb = max(p.Z + zcumul, ZMIN)
        dzstrm = 0.0
        ipositn = position(s, xb, yb, zb)
        if ipositn > 2 and p.X <= r15src:
            dzdx = zstream(s.HB, s.WB, s.XLB, s.RB, s.XLR, s.HR, xb, yb, zb)
            dzstrm = dzdx * (p.U / p.USC) * ds
        p.V = 0.0
        _rate(p, ua, dudz, ra, dpdz, ta, drdxa, rhs)
        for i in range(1, 8):
            ftemp[i] = f[i] + rhs[i] * ds
        _unlump(p, ua, ta, ra, ftemp)
        zb = max(p.Z + zcumul + dzstrm, ZMIN)
        ua0, ra, ta, dudz0, dpdz = zmet(s, zb)
        ipositn = position(s, xb, yb, zb)
        ufac, dufac = 1.0, 0.0
        if ipositn < 4:
            ufac, dufac = wake_u(s, xb, yb, zb)
        ua = ufac * ua0
        dudz = ufac * dudz0 + dufac * ua0
        _rate(p, ua, dudz, ra, dpdz, ta, drdxa, rhstemp)
        for i in range(1, 8):
            rhs[i] = 0.5 * (rhstemp[i] - rhs[i])
            f[i] = ftemp[i] + rhs[i] * ds
        _unlump(p, ua, ta, ra, f)
        zcumul = zcumul + dzstrm
        zc = max(p.Z + zcumul, ZMIN)
        xb = p.X - s.XBADJ
        yb = p.Y - s.YBADJ
        zb = zc
        ipositn = position(s, xb, yb, zb)
        if p.X < 0.0:
            p.X = 0.0
            p.S = p.S + ds
            nnp = nnp - 1
        else:
            if p.PHI <= 0.349065850398866 and ipositn < 4:
                if not linwake:
                    linwake = True
                    xbi = _entrada(s, p, h, sz0, sy0)
                drdxa = wake_drdx(s, p.X)
            p.S = p.S + ds
            nn = nnp
            if nn > MXNW:
                raise RuntimeError("PRIME: trayectoria demasiado larga")
            xt[nn], yt[nn], zt[nn], rt[nn], ht[nn] = p.X, p.Y, zc, p.R, p.Z - h
            if p.X >= xmax:
                zfin, yfin, xfin, rfin, hfin = zc, p.Y, p.X, p.R, p.Z - h
                break
        ua0, ra, ta, dudz0, dpdz = zmet(s, zb)
        ufac, dufac = 1.0, 0.0
        if ipositn < 4:
            ufac, dufac = wake_u(s, xb, yb, zb)
        ua = ufac * ua0
        dudz = ufac * dudz0 + dufac * ua0
        nnp = nnp + 1
        if p.W < 0.0:
            zfin, yfin, xfin, rfin, hfin = zc, p.Y, p.X, p.R, p.Z - h
            break
        if ds < DS0:
            ds = min(DS0, 2.0 * ds)
        if p.S < SLAST:
            continue
        zfin, yfin, xfin, rfin, hfin = zc, p.Y, p.X, p.R, p.Z - h
        break
    s.XFINRISE = xfin
    s.ZFINRISE = zfin
    # trayectoria hasta 15R con solo la pendiente de las líneas de corriente
    x15r = r15src - xfin
    if x15r > 0.0:
        dsfin = float(NSTEP) * ds
        dx15r = max(dsfin, x15r / float(MXNW - nn)) if MXNW > nn else float("inf")
        # el original redondea al entero más próximo (caja negra: 139,99 m -> 140 pasos)
        n15r = min(int(math.floor(x15r / dx15r + 0.5)), MXNW - nn)
        nbeg = nn + 1
        nend = nn + n15r
        for in_ in range(nbeg, nend + 1):
            xbb = xt[in_ - 1] - s.XBADJ
            xbe = xbb + dx15r
            yb = yt[in_ - 1] - s.YBADJ
            zb = zt[in_ - 1]
            dzdx = 0.0
            ipos = position(s, xbb, yb, zb)
            if ipos > 2:
                dzdx = 0.5 * (zstream(s.HB, s.WB, s.XLB, s.RB, s.XLR, s.HR, xbb, yb, zb) +
                              zstream(s.HB, s.WB, s.XLB, s.RB, s.XLR, s.HR, xbe, yb, zb))
            xt[in_] = xt[in_ - 1] + dx15r
            yt[in_] = yfin
            zt[in_] = max(ZMIN, zt[in_ - 1] + dzdx * dx15r)
            rt[in_] = rfin
            ht[in_] = hfin
            zcumul = zcumul + dzdx * dx15r
            if not linwake and ipos < 4:
                linwake = True
                p.X = xt[in_]
                p.Z = zt[in_] - zcumul
                xbi = _entrada(s, p, h, sz0, sy0)
            if linwake:
                drdxa = wake_drdx(s, p.X)
        nn = nend
        xfin = xt[nn]
        zfin = zt[nn]
    s.ZCUMUL = zcumul
    s.NN = nn
    xtr = np.zeros(ntr + 1)
    ytr = np.zeros(ntr + 1)
    ztr = np.zeros(ntr + 1)
    rtr = np.zeros(ntr + 1)
    htr = np.zeros(ntr + 1)

    def copia(i, j):
        xtr[i], ytr[i], ztr[i], rtr[i], htr[i] = xt[j], yt[j], zt[j], rt[j], ht[j]

    if nn > ntr:
        copia(ntr, nn)
        rns = _proximos(nn, ntr) if nn <= 2 * ntr else _sucesion(nn, ntr, True)
        for in_ in range(1, ntr):
            copia(in_, int(rns[in_]))
    else:
        for in_ in range(1, nn + 1):
            copia(in_, in_)
        for it in range(nn + 1, ntr + 1):
            copia(it, nn)
    s.LINWAKE = linwake
    s.FQCAV = 0.0
    if linwake:
        _addbid(s, xtr, htr, ntr)
        if xbi < (s.XLB + s.XLR):
            wake_fqc(s, xbi, xtr, ztr, ntr)
    return xtr, ytr, ztr, rtr, htr


# ════════════════════════════════════ tablas de σ de la estela (WAKE_DFSN) ═══════════════════════
def wake_dfsn(s, xi, szi, syi, z):
    """WAKE_DFSN: tablas de σ del penacho en la estela y de la fuente de la cavidad. Como el
    original de dominio público salvo el crecimiento ambiental, que en CALPUFF sigue la curva desde
    una distancia virtual (en la estela, contada desde la chimenea; en la cavidad, desde su
    fuente), y las filas a barlovento de la entrada en la estela (caja negra)."""
    hb, wb, rb, xbadj = s.HB, s.WB, s.RB, s.XBADJ
    n = MXNW + 2
    dist = np.zeros(n)
    asigz = np.zeros(n)
    asigy = np.zeros(n)
    dsz = np.zeros(n)
    csigz = np.zeros(n)
    csigy = np.zeros(n)
    xaz, xay = wake_xa(s, s.XLB, s.RB)
    s.XAZ, s.XAY = xaz, xay
    xamx = max(xaz, xay)
    xamn = min(xaz, xay)
    zk = yk = zkc = ykc = 0.0
    xcave = s.XLB + s.XLR
    xbc = min(max(xi, s.XLB), xcave)
    xdc = xbc + s.XLR
    szcav0, sycav0 = wake_cav0(s, syi)
    lrevcav = xi < s.XLB
    distc = xbc + xbadj
    s.DISTC = distc
    # distancias virtuales: entrada en la estela y fuente de la cavidad (en la transición al
    # crecimiento ambiental pueden ser negativas, caja negra)
    xve_z = max(_xv(s, szi, 1) - (xi + xbadj), 0.0)
    xve_y = max(_xv(s, syi, 0) - (xi + xbadj), 0.0)
    s.XVZ = s.XVY = 0.0
    trz = try_ = False          # ¿se ha pasado ya por la transición de σz / σy?
    s.XVZC = _xv(s, szcav0, 1)
    s.XVYC = _xv(s, sycav0, 0)
    s.NCAV = 1
    s.XCAV[1] = distc
    s.SZCAV[1] = szcav0
    s.SYCAV[1] = sycav0
    lcav = xi < xcave
    if not lcav:
        lrevcav = False
    s.NWAK = 1
    s.XWAK[1] = xi + xbadj
    s.SZWAK[1] = szi
    s.SYWAK[1] = syi
    s.DRWAK[1] = 0.0
    lwak = xi < xamx
    s.LWAK, s.LCAV = lwak, lcav
    if not lwak and not lcav:
        return
    xd = xi + s.XLR
    dx = 2.0
    xlow = xi
    xhi = xamx
    if lcav:
        xlow = min(xi, xbc)
        xhi = max(xamx, xcave)
    xrange_ = xhi - xlow + dx
    np_ = int(math.floor(xrange_ / dx + 0.5)) + 1
    np_ = min(np_, MXNW - 1)
    dx = xrange_ / (float(np_) - 1.0)
    dxi = 1.0 / dx
    nws = ncs = 0
    dist[1] = xlow + xbadj
    if lwak:
        asigz[1], asigy[1], dsz[1] = szi, syi, 0.0
    if lcav:
        csigz[1], csigy[1] = szcav0, sycav0
    x = xlow
    for n_ in range(2, np_ + 1):
        xold = x
        x = x + dx
        dist[n_] = dist[n_ - 1] + dx
        if lrevcav and xold >= s.XLB:
            szcav0, sycav0r = wake_cav0(s, asigy[n_ - 1])
            if sycav0r > sycav0:
                sycav0 = sycav0r
                s.SYCAV[1] = sycav0
                s.XVYC = max(s.XVYC, _xv(s, sycav0, 0))
                for ir in range(1, n_):
                    csigy[ir] = max(csigy[ir], sycav0)
            lrevcav = False
        if lwak and xi >= x:
            asigz[n_], asigy[n_], dsz[n_] = asigz[n_ - 1], asigy[n_ - 1], dsz[n_ - 1]
            nws = n_
        if lcav and xbc >= x:
            csigz[n_], csigy[n_] = szcav0, sycav0
            ncs = n_
        dc = dist[n_] - distc
        if xold > xamx:
            if lwak and xi < x:
                s.XVZ = s.XVZ if trz else xve_z
                s.XVY = s.XVY if try_ else xve_y
                asigz[n_] = sigzpr(s, dist[n_] + s.XVZ)
                asigy[n_] = sigypr(s, dist[n_] + s.XVY)
                dsz[n_] = (asigz[n_] - asigz[n_ - 1]) * dxi
            if lcav and xbc < x:
                csigz[n_] = sigzpr(s, dc + s.XVZC)
                csigy[n_] = sigypr(s, dc + s.XVYC)
        elif x < xamn:
            wakiz, wakiy = wake_turb(s, 0.5 * (x + xold), s.XLB, s.RB)
            if lwak and xi <= x:
                zk, yk, asigz[n_], asigy[n_], dsz[n_] = wake_sig(
                    x, xd, xold, wakiz, wakiy, asigz[n_ - 1], asigy[n_ - 1], hb, wb, rb, zk, yk)
            if lcav and xbc <= x:
                zkc, ykc, csigz[n_], csigy[n_], _d = wake_sig(
                    x, xdc, xold, wakiz, wakiy, csigz[n_ - 1], csigy[n_ - 1], hb, wb, rb, zkc, ykc)
                csigz[n_] = max(csigz[n_], szcav0)
        else:
            # σz
            if xold >= xaz:
                if lwak and xi <= x:
                    s.XVZ = s.XVZ if trz else xve_z
                    asigz[n_] = sigzpr(s, dist[n_] + s.XVZ)
                    dsz[n_] = (asigz[n_] - asigz[n_ - 1]) * dxi
                if lcav and xbc <= x:
                    csigz[n_] = max(sigzpr(s, dc + s.XVZC), szcav0)
            elif x >= xaz:
                xnew = xaz
                wakiz, wakiy = wake_turb(s, 0.5 * (xnew + xold), s.XLB, s.RB)
                if lwak and xi <= xnew:
                    zk, _yd, sigzxa, _sd, _d = wake_sig(
                        xnew, xd, xold, wakiz, wakiy, asigz[n_ - 1], asigy[n_ - 1], hb, wb, rb, zk, 0.0)
                    s.XVZ = _xv(s, sigzxa, 1) - (xaz + xbadj)
                    trz = True
                    asigz[n_] = sigzpr(s, dist[n_] + s.XVZ)
                    dsz[n_] = (asigz[n_] - asigz[n_ - 1]) * dxi
                if lcav and xbc <= xnew:
                    zkc, _yd, sigzxa, _sd, _d = wake_sig(
                        xnew, xdc, xold, wakiz, wakiy, csigz[n_ - 1], csigy[n_ - 1], hb, wb, rb, zkc, 0.0)
                    s.XVZC = max(_xv(s, sigzxa, 1) - (xaz + xbadj - distc), _xv(s, szcav0, 1))
                    csigz[n_] = sigzpr(s, dc + s.XVZC)
            else:
                wakiz, wakiy = wake_turb(s, 0.5 * (x + xold), s.XLB, s.RB)
                if lwak and xi <= x:
                    zk, _yd, asigz[n_], _sd, dsz[n_] = wake_sig(
                        x, xd, xold, wakiz, wakiy, asigz[n_ - 1], asigy[n_ - 1], hb, wb, rb, zk, 0.0)
                if lcav and xbc <= x:
                    zkc, _yd, csigz[n_], _sd, _d = wake_sig(
                        x, xdc, xold, wakiz, wakiy, csigz[n_ - 1], csigy[n_ - 1], hb, wb, rb, zkc, 0.0)
                    csigz[n_] = max(csigz[n_], szcav0)
            # σy
            if xold >= xay:
                if lwak and xi <= x:
                    s.XVY = s.XVY if try_ else xve_y
                    asigy[n_] = sigypr(s, dist[n_] + s.XVY)
                if lcav and xbc <= x:
                    s.XVYC = max(s.XVYC, _xv(s, sycav0, 0))
                    csigy[n_] = sigypr(s, dc + s.XVYC)
            elif x >= xay:
                xnew = xay
                wakiz, wakiy = wake_turb(s, 0.5 * (xnew + xold), s.XLB, s.RB)
                if lwak and xi <= xnew:
                    _zd, yk, _sd, sigyxa, _d = wake_sig(
                        xnew, xd, xold, wakiz, wakiy, asigz[n_ - 1], asigy[n_ - 1], hb, wb, rb, 0.0, yk)
                    s.XVY = _xv(s, sigyxa, 0) - (xay + xbadj)
                    try_ = True
                    asigy[n_] = sigypr(s, dist[n_] + s.XVY)
                if lcav and xbc <= xnew:
                    _zd, ykc, _sd, sigyxa, _d = wake_sig(
                        xnew, xdc, xold, wakiz, wakiy, csigz[n_ - 1], csigy[n_ - 1], hb, wb, rb, 0.0, ykc)
                    s.XVYC = _xv(s, sigyxa, 0) - (xay + xbadj - distc)
                    csigy[n_] = sigypr(s, dc + s.XVYC)
            else:
                wakiz, wakiy = wake_turb(s, 0.5 * (x + xold), s.XLB, s.RB)
                if lwak and xi <= x:
                    _zd, yk, _sd, asigy[n_], _d = wake_sig(
                        x, xd, xold, wakiz, wakiy, asigz[n_ - 1], asigy[n_ - 1], hb, wb, rb, 0.0, yk)
                if lcav and xbc <= x:
                    _zd, ykc, _sd, csigy[n_], _d = wake_sig(
                        x, xdc, xold, wakiz, wakiy, csigz[n_ - 1], csigy[n_ - 1], hb, wb, rb, 0.0, ykc)
    s.DXW = dx
    _tablas(s, lwak, lcav, np_, nws, ncs, xi, szi, syi, xbc, szcav0, sycav0, dx,
            dist, asigz, asigy, dsz, csigz, csigy)


def _tablas(s, lwak, lcav, np_, nws, ncs, xi, szi, syi, xbc, szcav0, sycav0, dx,
            dist, asigz, asigy, dsz, csigz, csigy):
    """Tablas de la estela (con la chimenea en x = 0 y filas a barlovento de la entrada en x =
    rn·dx, caja negra) y de la cavidad, submuestreadas a MXNTR puntos como el original."""
    ntr = MXNTR
    s.NUP = 0
    # se guardan las matrices finas para la tabla definitiva (con las filas a barlovento), que se
    # construye al terminar NUMRISE; durante la sobreelevación se usa la de los puntos de la estela
    s.FINO = (lwak, np_, nws, xi, szi, syi, dx, dist.copy(), asigz.copy(), asigy.copy(), dsz.copy())
    if lwak:
        _tabla_estela(s, np_, nws, xi, szi, syi, dx, dist, asigz, asigy, dsz, False)
    if lcav:
        npc = np_ - ncs
        s.XCAV[1] = xbc + s.XBADJ
        s.SZCAV[1] = szcav0
        s.SYCAV[1] = sycav0
        if npc >= ntr:
            s.NCAV = ntr
            s.XCAV[ntr] = dist[np_]
            s.SZCAV[ntr] = csigz[np_]
            s.SYCAV[ntr] = csigy[np_]
            rns = _proximos(npc, ntr) if npc <= 2 * ntr else _sucesion(npc, ntr)
            for in_ in range(2, ntr):
                jn = int(rns[in_]) + ncs
                s.XCAV[in_], s.SZCAV[in_], s.SYCAV[in_] = dist[jn], csigz[jn], csigy[jn]
        else:
            s.NCAV = npc
            for in_ in range(2, npc + 1):
                inp = in_ + ncs
                s.XCAV[in_], s.SZCAV[in_], s.SYCAV[in_] = dist[inp], csigz[inp], csigy[inp]


def _tabla_estela(s, np_, nws, xi, szi, syi, dx, dist, asigz, asigy, dsz, barlovento):
    """Tabla de la estela submuestreada a MXNTR puntos. Sin `barlovento` (durante NUMRISE): primer
    elemento en la entrada y los npw puntos de la estela. Con `barlovento` (tabla definitiva): la
    chimenea en x = 0 y las filas a barlovento de la entrada en x = rn·dx con la σ ambiental (la
    flotación se añade en WAKE_ADDBID), seguidas de los puntos de la estela (caja negra)."""
    rtpiby2 = 1.25331413731550
    ntr = MXNTR
    npw = np_ - nws
    xent = xi + s.XBADJ
    npup = (max(1, int(xent / dx)) if xent > 0.0 else 0) if barlovento else 0
    nptot = npw + npup
    s.NUP = npup

    def fila(in_, rn):
        j = int(rn)
        if barlovento and j <= npup:
            if in_ == 1:
                s.XWAK[in_] = 0.0
                s.SZWAK[in_] = s.SYWAK[in_] = s.DRWAK[in_] = 0.0
            else:
                x = rn * dx
                s.XWAK[in_] = x
                s.SZWAK[in_] = -sigzpr(s, x)
                s.SYWAK[in_] = -sigypr(s, x)
                s.DRWAK[in_] = 0.0
        elif in_ == 1:
            s.XWAK[1] = xent
            s.SZWAK[1] = szi
            s.SYWAK[1] = syi
            s.DRWAK[1] = 0.0
        else:
            k = j - npup + nws
            s.XWAK[in_] = dist[k]
            s.SZWAK[in_] = asigz[k]
            s.SYWAK[in_] = asigy[k]
            s.DRWAK[in_] = rtpiby2 * dsz[k]

    if nptot >= ntr:
        s.NWAK = ntr
        if nptot <= 2 * ntr:
            rns = _proximos(nptot, ntr)
            if barlovento:
                # con filas a barlovento, por valores próximos: índice int((in − 1)·deln) y las
                # filas a barlovento en ese índice entero por dx (caja negra)
                rns = [0.0, 0.0] + [float(int(r)) for r in rns[1:-1]]
        else:
            rns = _sucesion(nptot, ntr)
        for in_ in range(1, ntr):
            fila(in_, rns[in_])
        s.XWAK[ntr] = dist[np_]
        s.SZWAK[ntr] = asigz[np_]
        s.SYWAK[ntr] = asigy[np_]
        s.DRWAK[ntr] = rtpiby2 * dsz[np_]
    else:
        # sin submuestreo: las filas a barlovento reparten la distancia hasta la entrada en npup
        # tramos iguales (caja negra)
        s.NWAK = nptot
        for in_ in range(1, nptot + 1):
            if barlovento and in_ <= npup:
                x = (in_ - 1) * xent / npup
                s.XWAK[in_] = x
                s.SZWAK[in_] = -sigzpr(s, x) if in_ > 1 else 0.0
                s.SYWAK[in_] = -sigypr(s, x) if in_ > 1 else 0.0
                s.DRWAK[in_] = 0.0
            else:
                fila(in_, float(in_))


def _addbid(s, xtr, htr, ntr):
    """WAKE_ADDBID: σ de las filas a barlovento de la entrada con la flotación de la elevación de
    la trayectoria (sin el descenso de las líneas de corriente)."""
    if s.FINO is None:
        return
    lwak, np_, nws, xi, szi, syi, dx, dist, asigz, asigy, dsz = s.FINO
    if lwak:
        _tabla_estela(s, np_, nws, xi, szi, syi, dx, dist, asigz, asigy, dsz, True)
    for i in range(1, s.NWAK + 1):
        if s.SZWAK[i] < 0.0 or s.SYWAK[i] < 0.0:
            x = s.XWAK[i]
            bid2 = (numgrad(x, xtr, htr, ntr) / 3.5) ** 2
            s.SZWAK[i] = math.sqrt(s.SZWAK[i] ** 2 + bid2)
            s.SYWAK[i] = math.sqrt(s.SYWAK[i] ** 2 + bid2)


# ════════════════════════════════════ fracción en la cavidad (WAKE_FQC) ══════════════════════════
def wake_fqc(s, xbi, xtr, ztr, ntr):
    """WAKE_FQC: fracción máxima de la masa capturada por la cavidad."""
    s.FQCAV = 0.0
    xbstart = max(xbi, s.XLB)
    xbend = s.XLB + s.XLR
    xrange_ = 0.99 * (xbend - xbstart)
    yba = abs(s.YBADJ)
    xend = xbend + s.XBADJ
    nstep = max(5, int(1.0 + xrange_ / 10.0))
    xstep = xrange_ / float(nstep)
    zplm = numgrad(xend, xtr, ztr, ntr)
    sz, sy, szc, syc = wake_xsig(s, xend, s.HB, 0.0, True)
    fractz0 = frgauss(zplm, sz, s.HB, -s.HB)
    for is_ in range(0, nstep + 1):
        xb = xbstart + float(is_) * xstep
        x = xb + s.XBADJ
        zplm = numgrad(x, xtr, ztr, ntr)
        zcav, ycav = cavity_ht(s.HB, s.WB, s.XLB, s.RB, s.XLC, s.XLR, s.HR, xb)
        sz, sy, szc, syc = wake_xsig(s, x, zplm, 0.0, True)
        fract = min(frgauss(zplm, sz, zcav, -zcav), fractz0) * frgauss(yba, sy, ycav, -ycav)
        if fract > s.FQCAV:
            s.FQCAV = float(fract)
    xb85 = s.XLB + 0.85 * s.XLR
    if xbstart > xb85:
        s.FQCAV = min(s.FQCAV, max(0.0, 1.0 - (xbstart - xb85) / (xbend - xb85)))


FQCAV_MIN = 0.001


def fqcav_ef(s):
    """Fracción en la cavidad que se usa de verdad: por debajo de FQCAV_MIN no hay fuente de la
    cavidad y toda la masa va al penacho principal (caja negra: 7,8·10⁻⁴ → 0; 1,6·10⁻³ se usa)."""
    return s.FQCAV if s.FQCAV >= FQCAV_MIN else 0.0


_A_ERF = (0.0, 0.0000430638, 0.0002765672, 0.0001520143, 0.0092705272, 0.0422820123, 0.0705230784)


def fnerf(xx):
    a = _A_ERF
    x = abs(xx)
    if x > 3.919206:
        t16 = 0.0
    else:
        t = (((((((((a[1] * x + a[2]) * x) + a[3]) * x) + a[4]) * x) + a[5]) * x) + a[6]) * x
        t = 1.0 / (t + 1.0)
        t16 = t * t * t * t
        t16 = t16 * t16 * t16 * t16
    return 1.0 - t16 if xx > 0.0 else t16 - 1.0


def fnerfc(xx):
    a = _A_ERF
    if xx > 13.306:
        return 0.0
    if xx < -3.919206:
        return 2.0
    if xx > 2.79:
        z = 1.0 / abs(xx)
        return 0.564189583547756 * z * math.exp(-xx * xx) * (1.0 - 0.5 * z * z * (1.0 - 1.5 * z * z))
    x = abs(xx)
    t = (((((((((a[1] * x + a[2]) * x) + a[3]) * x) + a[4]) * x) + a[5]) * x) + a[6]) * x
    t = 1.0 / (t + 1.0)
    t16 = t * t * t * t
    t16 = t16 * t16 * t16 * t16
    return t16 if xx > 0.0 else 2.0 - t16


def erfdif(x1, x2):
    if x1 == x2:
        return 0.0
    if x1 * x2 <= 0.0:
        return fnerf(x1) - fnerf(x2)
    xtest = min(abs(x1), abs(x2))
    if xtest >= 9.15:
        return 0.0
    if xtest < 0.47:
        return fnerf(x1) - fnerf(x2)
    isign = 1
    xx1, xx2 = x1, x2
    if not x1 > 0.0:
        isign = -1
        xx1, xx2 = -xx1, -xx2
    e1 = fnerfc(xx1) if xx1 < 9.15 else 0.0
    e2 = fnerfc(xx2) if xx2 < 9.15 else 0.0
    return 0.0 if e1 == e2 else float(isign) * (e2 - e1)


def frgauss(hcntr, sigma, h1, h2):
    """FRGAUSS: fracción de una gaussiana entre h1 y h2."""
    sg = 1.41421356237310 * max(sigma, 1.0e-5)
    return 0.5 * abs(erfdif((h1 - hcntr) / sg, (h2 - hcntr) / sg))


# ════════════════════════════════════ σ en un punto (WAKE_XSIG) ══════════════════════════════════
def _interp(xt, yt, n, x):
    for i in range(n - 1, 0, -1):
        if x >= xt[i]:
            ip1 = i + 1
            return float(yt[ip1] - (yt[ip1] - yt[i]) * (xt[ip1] - x) / (xt[ip1] - xt[i]))
    return float(yt[1])


def wake_xsig(s, x, hstk, rise, nobid):
    """WAKE_XSIG: σ del penacho principal y de la fuente de la cavidad a la distancia x de la
    chimenea: interpolación en las tablas; fuera de ellas, curva ambiental (con flotación) antes y
    crecimiento desde la distancia virtual después."""
    if x <= 0.0:
        sz = sy = 0.0
    elif s.NWAK <= 1 or x < s.XWAK[1]:
        sz = sigzpr(s, x)
        sy = sigypr(s, x)
        if not nobid:
            b2 = (rise / 3.5) ** 2
            sz = math.sqrt(sz * sz + b2)
            sy = math.sqrt(sy * sy + b2)
    elif x > s.XWAK[s.NWAK]:
        sz = sigzpr(s, x + s.XVZ)
        sy = sigypr(s, x + s.XVY)
    else:
        sz = _interp(s.XWAK, s.SZWAK, s.NWAK, x)
        sy = _interp(s.XWAK, s.SYWAK, s.NWAK, x)
    if s.NCAV <= 1 or x < s.XCAV[1]:
        szc, syc = s.SZCAV[1], s.SYCAV[1]
    elif x > s.XCAV[s.NCAV]:
        szc = sigzpr(s, x - s.DISTC + s.XVZC)
        syc = sigypr(s, x - s.DISTC + s.XVYC)
    else:
        szc = _interp(s.XCAV, s.SZCAV, s.NCAV, x)
        syc = _interp(s.XCAV, s.SYCAV, s.NCAV, x)
    return float(sz), float(sy), float(szc), float(syc)


def cav_src(s, xr, yr, zr):
    """CAV_SRC: fuentes de la cavidad para un receptor (xr, yr, zr relativos a la chimenea, eje x
    con el flujo). Devuelve (n1, n2, qc, yrc, zrc, szc, syc) con índices 1..3 (1 = principal)."""
    rt2pi = 2.50662827463100
    szcav0, sycav0 = s.SZCAV[1], s.SYCAV[1]
    qc = [0.0] * 4
    yrc = [0.0] * 4
    zrc = [0.0] * 4
    szc = [0.0] * 4
    syc = [0.0] * 4
    mode = 0
    n1 = n2 = 0
    # a diferencia de AERMOD, el reparto se calcula también con FQCAV = 0: dentro de la cavidad el
    # penacho principal no cuenta (caja negra)
    if True:
        xrb = xr - s.XBADJ
        yrb = yr - s.YBADJ
        ipositn = position(s, xrb, yrb, zr)
        x115b = s.XLB + 1.15 * s.XLR
        x85b = s.XLB + 0.85 * s.XLR
        if xrb >= x115b:
            qc[2], qc[3], mode = 1.0, 0.0, 1
        elif xrb > x85b:
            qc[2] = (xrb - x85b) / (x115b - x85b)
            qc[3] = 1.0 - qc[2]
            mode = 3
        elif xrb > s.XLB:
            qc[2], qc[3], mode = 0.0, 1.0, 2
        else:
            qc[2], qc[3], mode = 0.0, max(0.0, xrb / s.XLB), 2
        if ipositn == 4:
            mode = 0
            n1 = n2 = 1
            for i in (2, 3):
                qc[i] = 0.0
                yrc[i], zrc[i], szc[i], syc[i] = yr, zr, szcav0, sycav0
        else:
            wtop = sycav0 * rt2pi
            ybmax = 0.5 * (s.WB - wtop)
            if ybmax <= 0.0:
                yrc[2] = yrb
            else:
                ysb = -s.YBADJ
                yrc[2] = yrb - (max(ysb, -ybmax) if ysb < 0.0 else min(ysb, ybmax))
            yrc[3] = yrc[2]
            if ipositn <= 2:
                n1, n2 = {3: (2, 3), 2: (3, 3), 1: (2, 2)}[mode]
                for i in range(n1, n2 + 1):
                    zrc[i], szc[i], syc[i] = 0.0, szcav0, sycav0
                if (mode == 1 or mode == 3) and xr > 0.0:
                    _z, _y, szc[2], syc[2] = wake_xsig(s, xr, 0.0, 0.0, True)
            else:
                n1, n2 = 1, 3
                if xrb >= (s.XLB + s.XLR):
                    zrc[2] = zr
                else:
                    zcav, wcav = cavity_ht(s.HB, s.WB, s.XLB, s.RB, s.XLC, s.XLR, s.HR, xrb)
                    zrc[2] = max(0.0, zr - zcav)
                zrc[3] = zrc[2]
                if mode == 2:
                    qc[2] = 0.0
                    szc[2], syc[2], szc[3], syc[3] = szcav0, sycav0, szcav0, sycav0
                elif mode == 1:
                    _z, _y, szc[2], syc[2] = wake_xsig(s, xr, 0.0, 0.0, True)
                    n2 = 2
                else:
                    szc[2], syc[2], szc[3], syc[3] = szcav0, sycav0, szcav0, sycav0
                    if xr >= 0.0:
                        _z, _y, szc[2], syc[2] = wake_xsig(s, xr, 0.0, 0.0, True)
    if n1 == 1 and (xr <= 0.0 or s.FQCAV == 1.0):
        n1 = 2
    return n1, n2, qc, yrc, zrc, szc, syc


# ════════════════════════════════════ resultado para el modelo de puffs ══════════════════════════
# fila de la tabla compacta de una fuente y hora (la usa el núcleo numba)
(T_NWAK, T_NCAV, T_XVY, T_XVZ, T_XVYC, T_XVZC, T_DISTC, T_XFIN, T_ZFIN, T_CLASE, T_URB, T_LWAK,
 T_EXC, T_X115) = range(14)
T_XW = 14
T_SYW = T_XW + MXNTR
T_SZW = T_SYW + MXNTR
T_XC = T_SZW + MXNTR
T_SYC = T_XC + MXNTR
T_SZC = T_SYC + MXNTR
T_XT = T_SZC + MXNTR
T_ZT = T_XT + MXNTR
T_HT = T_ZT + MXNTR
NTCOL = T_HT + MXNTR


def fila_tabla(s, tr):
    """Tabla compacta (vector de NTCOL) con lo que necesitan los puffs de una fuente y hora."""
    f = np.zeros(NTCOL)
    f[T_NWAK] = s.NWAK if s.LINWAKE and s.LWAK else 0
    f[T_NCAV] = s.NCAV if s.LINWAKE and s.LCAV else 0
    f[T_XVY], f[T_XVZ], f[T_XVYC], f[T_XVZC] = s.XVY, s.XVZ, s.XVYC, s.XVZC
    f[T_DISTC] = s.DISTC
    f[T_XFIN] = tr[0][MXNTR]
    f[T_ZFIN] = tr[2][MXNTR]
    f[T_CLASE] = s.clase
    f[T_URB] = 1.0 if s.urbano else 0.0
    f[T_LWAK] = 1.0 if (s.LINWAKE and s.LWAK) else 0.0
    f[T_EXC] = -1.0
    # fin de la zona de la cavidad (CAV_CONC) desde la chimenea
    f[T_X115] = s.XBADJ + s.XLB + 1.15 * s.XLR
    n = MXNTR
    f[T_XW:T_XW + n] = s.XWAK[1:n + 1]
    f[T_SYW:T_SYW + n] = s.SYWAK[1:n + 1]
    f[T_SZW:T_SZW + n] = s.SZWAK[1:n + 1]
    f[T_XC:T_XC + n] = s.XCAV[1:n + 1]
    f[T_SYC:T_SYC + n] = s.SYCAV[1:n + 1]
    f[T_SZC:T_SZC + n] = s.SZCAV[1:n + 1]
    f[T_XT:T_XT + n] = tr[0][1:n + 1]
    f[T_ZT:T_ZT + n] = tr[2][1:n + 1]
    f[T_HT:T_HT + n] = tr[4][1:n + 1]
    return f


def zona_exclusion(s, xr, yr):
    """¿Está el receptor (relativo a la chimenea, eje x con el flujo de la hora) antes del final de
    la zona de la cavidad, xb < LB + 1,15·LR? Ahí los puffs de la fuente no cuentan mientras su punto
    de evaluación no haya salido de la zona (caja negra; sin límite lateral ni a barlovento)."""
    return xr - s.XBADJ < s.XLB + 1.15 * s.XLR


def region_cavidad(s, xr, yr):
    """¿Recibe el receptor la concentración de la zona de la cavidad (CAV_CONC)? Desde la chimenea o
    desde la cara de barlovento (la que esté antes) hasta el final de la zona (caja negra)."""
    xrb = xr - s.XBADJ
    return (xr > 0.0 or xrb >= 0.0) and zona_exclusion(s, xr, yr)


def _vertical_cav(h, z, sz, tapa, zsup):
    """Término vertical (×√(2π)·σz) de CAV_CONC (caja negra): sin tapa (estable) o con el penacho
    por encima de ella, gaussiana con reflexión en el suelo; con el penacho bajo la tapa, reflexiones
    entre el suelo y la tapa para los receptores bajo ella y, por encima, mezcla uniforme de toda la
    masa entre la tapa y zsup (el techo de la parte penetrada; nada si zsup ≤ tapa)."""
    def g(d):
        return math.exp(-0.5 * (d / sz) ** 2)

    if tapa is None or h > tapa:
        return g(z - h) + g(z + h)
    if z <= tapa:
        tot = g(z - h) + g(z + h)
        for n in range(1, 60):
            d = 2.0 * n * tapa
            t = g(z - h + d) + g(z + h + d) + g(z - h - d) + g(z + h - d)
            tot += t
            if t < 1e-12 * tot:
                break
        return tot
    if zsup > tapa and z <= zsup:
        return math.sqrt(2.0 * math.pi) * sz / (zsup - tapa)
    return 0.0


def cav_conc(s, tr, xr, yr, zr, us, ub, tapa=None, zsup=0.0):
    """CAV_CONC: concentración por unidad de emisión (s/m³) en un receptor de la zona de la cavidad:
    penacho principal (masa 1 − FQCAV, viento de la chimenea, altura de la trayectoria, σ de la
    tabla de la estela) más las fuentes de la cavidad exterior e interior (masa FQCAV con los pesos
    de CAV_SRC, viento a la altura del edificio, en el suelo). tapa: ZI en las clases A-D (None en
    estable); zsup: techo de la parte penetrada en la inversión (_vertical_cav)."""
    n1, n2, qc, yrc, zrc, szc, syc = cav_src(s, xr, yr, zr)

    def gq(sy, sz, y, z, h, u):
        if sy <= 0.0 or sz <= 0.0:
            return 0.0
        return (math.exp(-0.5 * (y / sy) ** 2) / (2.0 * math.pi * u * sy * sz) *
                _vertical_cav(h, z, sz, tapa, zsup))

    c0 = 0.0
    if n1 == 1:
        # fuera de la tabla de la estela (antes de la entrada o sin ella), σ ambiental con la
        # flotación de la elevación de la trayectoria en xr (caja negra)
        rise = numgrad(xr, tr[0], tr[4], MXNTR)
        sz1, sy1, _a, _b = wake_xsig(s, xr, 0.0, rise, False)
        h = numgrad(xr, tr[0], tr[2], MXNTR)
        c0 = gq(sy1, sz1, yr, zr, h, us)
    cc = 0.0
    for i in (2, 3):
        if n1 <= i <= n2 and qc[i] > 0.0:
            cc += qc[i] * gq(syc[i], szc[i], yrc[i], zrc[i], 0.0, ub)
    fq = fqcav_ef(s)
    return (1.0 - fq) * c0 + fq * cc
