# -*- coding: utf-8 -*-
"""UTM <-> geográficas tal como lo hace AERSURFACE v26135 (mod_Geographic.f: UTMGEO,
TMCOF, TMINV, TMFWD; rutinas de origen USGS). Trabaja en SEGUNDOS de arco y con la
longitud POSITIVA AL OESTE por dentro, como el original.

Se traduce en vez de usar pyproj porque las series y los ejes del elipsoide (b = 6356752.31414
para GRS80) son los del original: así la coordenada central sale idéntica."""
import math

EJES = {0: (6378206.4, 6356583.8),          # Clarke 1866 / NAD27
        1: (6378249.1450, 6356514.86955),   # Clarke 1880
        2: (6377397.155, 6356078.96284),    # Bessel
        3: (6378150.0, 6356768.337),        # Mercury modificado 1968
        4: (6378137.0, 6356752.31414)}      # GRS80 / NAD83
SEG_A_RAD = 4.84813681109536e-6
RAD_A_SEG = 206264.8062470964


def _tmcof(A):
    A[10] = (((A[16] * (7.0 / 3.2e1) + (5.0 / 1.6e1)) * A[16] + 0.5) * A[16] + 1.0) * A[16] * 0.25
    A[1] = -(((A[10] * (1.95e2 / 6.4e1) + 3.25) * A[10] + 3.75) * A[10] + 3.0) * A[10]
    A[2] = (((1.455e3 / 3.2e1) * A[10] + (7.0e1 / 3.0)) * A[10] + 7.5) * A[10] ** 2
    A[3] = -((7.0e1 / 3.0) + A[10] * (9.45e2 / 8.0)) * A[10] ** 3
    A[4] = (3.15e2 / 4.0) * A[10] ** 4
    A[11] = (((7.75 - (6.57e2 / 6.4e1) * A[10]) * A[10] - 5.25) * A[10] + 3.0) * A[10]
    A[12] = (((5.045e3 / 3.2e1) * A[10] - (1.51e2 / 3.0)) * A[10] + 10.5) * A[10] ** 2
    A[13] = ((1.51e2 / 3.0) - (3.291e3 / 8.0) * A[10]) * A[10] ** 3
    A[14] = (1.097e3 / 4.0) * A[10] ** 4
    fac = A[10] * A[10]
    A[10] = (((2.25e2 / 6.4e1) * fac + 2.25) * fac + 1.0) * (1.0 - fac) * (1.0 - A[10]) * A[15]


def _parametros(izone, ispher, sur=False):
    A = [0.0] * 17                       # 1-based como el original
    A[5], A[6] = 5.0e5, 0.0
    if sur or izone < 0:
        A[6] = 10.0e6
    A[7], A[8] = 0.0, 0.9996
    A[15], b1 = EJES[ispher]
    A[16] = ((A[15] - b1) / A[15]) * ((A[15] + b1) / A[15])
    _tmcof(A)
    return A


def _tminv(north, east, A):
    B = [0.0] * 13
    B[9] = ((A[5] - east) * 1.0e-6) / A[8]
    B[10] = ((north - A[6]) / A[8] + A[7]) / A[10]
    if abs(B[9]) - 1.0e-7 * A[15] * 2.0 > 0.0 or abs(B[10]) - 1.47 > 0.0:
        return 0.0, 0.0, 1
    sinw, cosw = math.sin(B[10]), math.cos(B[10])
    B[12] = cosw * cosw
    B[11] = (((A[14] * B[12] + A[13]) * B[12] + A[12]) * B[12] + A[11]) * sinw * cosw + B[10]
    sinw, cosw = math.sin(B[11]), math.cos(B[11])
    rn = math.sqrt(1.0 - A[16] * sinw * sinw) * 1.0e6 / A[15]
    t = sinw / cosw
    ts = t * t
    B[12] = cosw * cosw
    etas = A[16] * B[12] / (1.0 - A[16])
    B[1] = rn / cosw
    B[2] = -t * (1.0 + etas) * rn * rn / 2.0
    B[3] = -(1.0 + 2.0 * ts + etas) * B[1] * rn * rn / 6.0
    B[4] = ((((-6.0 - etas * 9.0) * etas + 3.0) * ts + (6.0 - etas * 3.0) * etas + 5.0)
            * t * rn ** 4 / 24.0)
    B[5] = ((ts * 24.0 + etas * 8.0 + 28.0) * ts + etas * 6.0 + 5.0) * B[1] * rn ** 4 / 120.0
    B[6] = ((((etas * 45.0 - 45.0) * ts + etas * 162.0 - 90.0) * ts - etas * 107.0 - 61.0)
            * t * rn ** 6 / 720.0)
    B[7] = -(((ts * 720.0 + 1320.0) * ts + 662.0) * ts + 61.0) * B[1] * rn ** 6 / 5040.0
    B[8] = (((ts * 1575.0 + 4095.0) * ts + 3633.0) * ts + 1385.0) * t * rn ** 8 / 40320.0
    B[10] = B[9] * B[9]
    slat = ((((B[8] * B[10] + B[6]) * B[10] + B[4]) * B[10] + B[2]) * B[10] + B[11]) * RAD_A_SEG
    slon = (((B[7] * B[10] + B[5]) * B[10] + B[3]) * B[10] + B[1]) * B[9] * RAD_A_SEG + A[9]
    return slat, slon, 0


def _tmfwd(slat, slon, A):
    B = [0.0] * 13
    B[10] = (A[9] - slon) * SEG_A_RAD
    if abs(slat) - 302400.0 > 0.0 or abs(B[10]) - 0.16 > 0.0:
        return 0.0, 0.0, 1
    B[9] = slat * SEG_A_RAD
    sinp, cosp = math.sin(B[9]), math.cos(B[9])
    rn = A[15] / math.sqrt(1.0 - A[16] * sinp * sinp)
    t = sinp / cosp
    ts = t * t
    B[11] = cosp * cosp
    etas = A[16] * B[11] / (1.0 - A[16])
    B[1] = rn * cosp
    B[3] = (1.0 - ts + etas) * B[1] * B[11] / 6.0
    B[5] = ((ts - 18.0) * ts + 5.0 + (14.0 - 58.0 * ts) * etas) * B[1] * B[11] * B[11] / 120.0
    B[7] = (((179.0 - ts) * ts - 479.0) * ts + 61.0) * B[1] * B[11] ** 3 / 5040.0
    B[12] = B[10] * B[10]
    east = (((B[7] * B[12] + B[5]) * B[12] + B[3]) * B[12] + B[1]) * B[10] * A[8] + A[5]
    B[2] = rn * B[11] * t / 2.0
    B[4] = (etas * (9.0 + 4.0 * etas) + 5.0 - ts) * B[2] * B[11] / 12.0
    B[6] = ((ts - 58.0) * ts + 61.0 + (270.0 - 330.0 * ts) * etas) * B[2] * B[11] * B[11] / 360.0
    B[8] = (((543.0 - ts) * ts - 3111.0) * ts + 1385.0) * B[2] * B[11] ** 3 / 20160.0
    north = ((((B[8] * B[12] + B[6]) * B[12] + B[4]) * B[12] + B[2]) * B[12]
             + ((((A[4] * B[11] + A[3]) * B[11] + A[2]) * B[11] + A[1]) * sinp * cosp + B[9])
             * A[10])
    north = (north - A[7]) * A[8] + A[6]
    return north, east, 0


def utm_a_geo(east, north, zona, ispher=4):
    """UTMGEO(KOD=333): -> (lat, lon) en grados decimales (oeste negativo), como hace
    GetGridVars al dividir entre 3600."""
    A = _parametros(zona, ispher)
    utz = 30.0 - float(abs(zona))
    A[9] = ((utz * 6.0) + 3.0) * 3600.0
    slat, slon, ierr = _tminv(north, east, A)
    if slon < -180.0 * 3600.0:
        slon = 360.0 * 3600.0 + slon
    elif slon > 180.0 * 3600.0:
        slon = -1.0 * (360.0 * 3600.0 - slon)
    slon = -1.0 * slon
    return slat / 3600.0, slon / 3600.0


def geo_a_utm(lat, lon, zona, ispher=4):
    """UTMGEO(KOD=555) con zona forzada: (lat, lon) grados -> (este, norte). Para generar
    casos de prueba con la misma aritmética del original."""
    slat, slon = lat * 3600.0, -lon * 3600.0
    A = _parametros(zona, ispher, sur=slat < 0)
    if abs(zona) <= 30:
        utz = 30.0 - float(abs(zona))
        A[9] = ((utz * 6.0) + 3.0) * 3600.0
    else:
        utz = float(abs(zona)) - 30.0
        A[9] = ((utz * 6.0) - 3.0) * (-3600.0)
    north, east, ierr = _tmfwd(slat, slon, A)
    return east, north
