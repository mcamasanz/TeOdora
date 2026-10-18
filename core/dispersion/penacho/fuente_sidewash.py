# -*- coding: utf-8 -*-
"""Traducción de AERMOD 26135 (US EPA, dominio público): fuentes SWPOINT (chimenea junto a un
edificio, con arrastre lateral o «sidewash»; opción ALPHA).

Rutinas traducidas:
  · calc1.f: SWCALC (bucle de receptores), PERPEN (viento perpendicular a la fachada) y OBLIQUE
    (viento oblicuo), con las interpolaciones entre 0 y 15 grados y entre 345 y 360 grados.
  · soset.f: SWPARM y la rama SWPOINT de SOPARM (exige ALPHA; 9 campos).

Lo que ya estaba en la traducción y se reutiliza: el recuento NSWP de PRESET (con el error 198 sin
ALPHA), la reserva de ABW/ABL/ABH/ABA y SWXR/SWYR en ALLSETUP, la rama SWPOINT de SETSRC, NUMSWP
de SRCQA y el resumen de fuentes de INPSUM (el original no tiene tabla de datos para SWPOINT).

Como en el original: SWCALC no aplica EMFACT (los factores de emisión variables no afectan a
SWPOINT), no guarda CHI para la química del NO2 (suma directamente con SUMVAL) y escala las
dimensiones con el factor del túnel de viento (150).

Concentraciones no finitas: más allá de unas decenas de alturas de edificio a sotavento, las
regresiones de OBLIQUE dan sigmas negativas (concentración negativa: se anula con el aviso 650) o
|RHO| > 1 (raíz de un negativo: NaN). El exe propaga el NaN como IEEE (``SWCONC .LT. 0`` es falso,
sin aviso, y SUMVAL lo suma), y lo imprime como NaN en las tablas: se reproduce igual.

Exactitud: se conserva el orden de las operaciones del Fortran; las potencias enteras son
productos; divisiones, raíces y exponenciales son IEEE (Inf/NaN sin excepciones); el giro de los
receptores usa seno y coseno correctamente redondeados (``openpit.seno_coseno``, como la libm de
Intel); y se emula el FTZ de /fp:fast (los subnormales valen cero), que se ve en el POSTFILE sin
formato lejos del penacho.

Ganchos para integrarlo (la lista exacta, con el código, está en el informe de la traducción):
  · calc1.calc: ``elif t == "SWPOINT": sidewash.swcalc(e)``.
  · soset.soloca: quitar SWPOINT de ``_FUENTES_FUERA``; soset.soparm: ``sidewash.soparm_sw``.

La depuración (DEBUGOPT SWPOINT, SWDBG) para con NoTraducido.

Convenciones del paquete: estado ``e`` con los nombres de MAIN1, matrices con índices 1..N."""
import math

from . import calculo_area, resultados
from .estado import NoTraducido
from .formato import fwrite
from .fuente_foso import seno_coseno
from .perfiles import gintrp, locate

_WTSF = 150.0               # factor de escala del túnel de viento


# ------------------------------------------------------------------------------------------
# Utilidades IEEE
# ------------------------------------------------------------------------------------------
def _div(a, b):
    """División IEEE (±Inf o NaN al dividir por cero)."""
    if b == 0.0:
        if a == 0.0 or a != a:
            return math.nan
        return math.copysign(math.inf, a) * math.copysign(1.0, b)
    return a / b


def _sqrt(x):
    """SQRT IEEE: NaN para argumentos negativos (o NaN)."""
    return math.sqrt(x) if x >= 0.0 else math.nan


def _exp(x):
    """DEXP IEEE: +Inf si desborda."""
    try:
        return math.exp(x)
    except OverflowError:
        return math.inf


# El exe está compilado con /fp:fast, que activa FTZ/DAZ: todo resultado subnormal (menor que
# DBL_MIN en valor absoluto) vale cero. Se nota en SWPOINT lejos del penacho (exponenciales
# ínfimas): sin emularlo, el POSTFILE sin formato tendría 7e-319 donde el exe escribe 0.
_DBL_MIN = 2.2250738585072014e-308


def _z(v):
    """FTZ: un subnormal pasa a cero (con su signo)."""
    if v != 0.0 and -_DBL_MIN < v < _DBL_MIN:
        return math.copysign(0.0, v)
    return v


def _m(a, b):
    return _z(a * b)


def _d(a, b):
    return _z(_div(a, b))


def _e(x):
    return _z(_exp(x))


# ------------------------------------------------------------------------------------------
# Vía SO (soset.f): rama SWPOINT de SOPARM y SWPARM
# ------------------------------------------------------------------------------------------
def soparm_sw(e, isdx, temp):
    """Rama SWPOINT de SOPARM: exige la opción ALPHA y 9 campos; después llama a SWPARM."""
    m = "SOPARM"
    if not e.L_ALPHA:
        e.errhdl(e.PATH, m, "E", "198", "SWPOINT")
    elif e.IFC == 3:
        e.errhdl(e.PATH, m, "E", "200", e.KEYWRD)
    elif e.IFC < 9:
        e.errhdl(e.PATH, m, "E", "201", e.KEYWRD)
    elif e.IFC > 9:
        e.errhdl(e.PATH, m, "E", "202", e.KEYWRD)
    else:
        swparm(e, isdx, temp)


def swparm(e, i, temp):
    """SWPARM: emisión, altura de la chimenea y anchura, longitud, altura y ángulo del edificio."""
    m = "SWPARM"
    e.AQS[i] = temp[1]
    e.AHS[i] = temp[2]
    e.ABW[i] = temp[3]
    e.ABL[i] = temp[4]
    e.ABH[i] = temp[5]
    e.ABA[i] = temp[6]
    if e.AQS[i] == 0.0:
        e.errhdl(e.PATH, m, "W", "320", " QS ")
    if e.AHS[i] < 0.0:
        e.errhdl(e.PATH, m, "E", "209", " HS ")
    elif e.AHS[i] > 600.0:
        e.errhdl(e.PATH, m, "W", "320", " HS ")
    elif e.AHS[i] > 3000.0:
        e.errhdl(e.PATH, m, "E", "324", e.SRCID[i])
    # dimensiones nulas o negativas: 1 m
    if e.ABW[i] <= 0.0:
        e.ABW[i] = 1.0
    if e.ABL[i] <= 0.0:
        e.ABL[i] = 1.0
    if e.ABH[i] <= 0.0:
        e.ABH[i] = 1.0
    if e.ABA[i] < 0.0:
        e.ABA[i] = e.ABA[i] + 360.0
    elif e.ABA[i] > 360.0:
        e.ABA[i] = e.ABA[i] - 360.0


# ------------------------------------------------------------------------------------------
# SWCALC, PERPEN y OBLIQUE (calc1.f)
# ------------------------------------------------------------------------------------------
def swcalc(e):
    """SWCALC: concentración horaria de una fuente SWPOINT en todos los receptores."""
    m = "SWCALC"
    isrc = e.ISRC
    calculo_area.setsrc(e)
    if e.SWDBG:
        raise NoTraducido("DEBUGOPT SWPOINT")
    wtsf = _WTSF
    e.BHS = e.BH / wtsf
    e.BWS = e.BW / wtsf
    e.BLS = e.BL / wtsf
    e.HSS = e.HS / wtsf
    # (EMFACT no se aplica: «Not yet implemented» en el original)

    # dirección del viento a la altura de la chimenea y velocidad a la altura del edificio
    gh = e.GRIDHT
    n = locate(gh, 1, e.MXGLVL, e.HS)
    stkwd = gintrp(gh[n], e.GRIDWD[n], gh[n + 1], e.GRIDWD[n + 1], e.HS)
    n = locate(gh, 1, e.MXGLVL, e.BH)
    stkws = gintrp(gh[n], e.GRIDWS[n], gh[n + 1], e.GRIDWS[n + 1], e.BH)
    e.U_AMB = stkws
    if stkwd > 360.0:
        stkwd = stkwd - 360.0
    elif stkwd <= 0.0:
        stkwd = stkwd + 360.0

    # ángulo del viento sobre la fachada
    e.SWTHETA = e.BA - (90.0 - (360.0 - stkwd))
    if e.SWTHETA >= 359.9:
        e.SWTHETA = e.SWTHETA - 360.0
    elif e.SWTHETA < 0.0:
        e.SWTHETA = e.SWTHETA + 360.0

    numtyp = e.NUMTYP
    # giro (270 - STKWD): seno y coseno correctamente redondeados, como la libm de Intel
    sr, cr = seno_coseno((270.0 - stkwd) * e.DTORAD)
    for irec in range(1, e.NUMREC + 1):
        e.IREC = irec
        # receptor trasladado a la chimenea y girado con el viento (eje X a sotavento)
        swxt = e.AXR[irec] - e.AXS[isrc]
        swyt = e.AYR[irec] - e.AYS[isrc]
        e.SWXR[irec] = swxt * cr + swyt * sr
        e.SWYR[irec] = swyt * cr - swxt * sr

        e.SX1 = e.SWXR[irec] / e.BH
        if e.SX1 == 0.0:
            e.SX1 = 1.0e-08
        e.SY1 = e.SWYR[irec] / wtsf
        e.SWZ = e.AZELEV[irec] / wtsf

        e.SWCONC = 0.0
        chisw = 0.0

        th = e.SWTHETA
        if th == 0.0 or th == 360.0:
            perpen(e)
        elif 15.0 <= th <= 60.0:
            oblique(e)
        elif 0.0 < th < 15.0:
            tmptheta = e.SWTHETA
            e.CONC_P = 0.0
            e.CONC_SW = 0.0
            e.THETA_P = 0.0
            e.THETA_SW = 15.0
            swepsilon = 1.0 - ((tmptheta - e.THETA_P) / (e.THETA_SW - e.THETA_P))
            e.SWTHETA = e.THETA_P
            perpen(e)
            e.CONC_P = e.SWCONC
            e.SWCONC = 0.0
            e.SWTHETA = e.THETA_SW
            oblique(e)
            e.CONC_SW = e.SWCONC
            e.SWTHETA = tmptheta
            e.SWCONC = e.CONC_P * swepsilon + e.CONC_SW * (1.0 - swepsilon)
        elif 300.0 <= th <= 345.0:
            e.SY1 = -1.0 * e.SY1
            tmptheta = e.SWTHETA
            e.SWTHETA = 360.0 - e.SWTHETA
            oblique(e)
            e.SWTHETA = tmptheta
        elif 345.0 < th < 360.0:
            e.SY1 = -1.0 * e.SY1
            tmptheta = e.SWTHETA
            e.CONC_P = 0.0
            e.CONC_SW = 0.0
            e.THETA_P = 360.0
            e.THETA_SW = 345.0
            swepsilon = 1.0 - ((tmptheta - e.THETA_P) / (e.THETA_SW - e.THETA_P))
            e.SWTHETA = e.THETA_P
            perpen(e)
            e.CONC_P = e.SWCONC
            e.SWCONC = 0.0
            e.SWTHETA = 360.0 - e.THETA_SW
            oblique(e)
            e.CONC_SW = e.SWCONC
            e.SWTHETA = tmptheta
            e.SWCONC = e.CONC_P * swepsilon + e.CONC_SW * (1.0 - swepsilon)
        else:
            # ángulos de más de 60 grados
            e.SWCONC = 0.0

        # concentración normalizada (escala del túnel) y en microgramos/m3
        chisw = _d(_m(_m(e.SWCONC, e.U_AMB), _m(e.BHS, e.BHS)), e.QS)
        hrval = _d(_m(_m(1.0e06, chisw), e.QS), _m(e.U_AMB, _m(e.BH, e.BH)))
        e.HRVAL[1:numtyp + 1] = hrval

        # concentración negativa: se anula con un aviso
        if e.SWCONC < 0.0:
            e.DUMMY = fwrite("(I12)", e.KURDAT)[0]
            e.errhdl(e.PATH, m, "W", "650", e.DUMMY)
            e.HRVAL[:] = 0.0

        for igrp in range(1, e.NUMGRP + 1):
            e.IGRP = igrp
            resultados.sumval(e)
        e.HRVAL[:] = 0.0
    e.IREC = e.NUMREC + 1


def perpen(e):
    """PERPEN: concentración con el viento perpendicular a la fachada (SWCONC)."""
    if e.SX1 < 0.0:
        e.SWCONC = 0.0
        return
    wh = e.BWS / e.BHS
    beta_b_u_c1 = (-0.0555 * wh)
    beta_b_u_c2 = 0.975993
    beta_b_sig_y1_c1 = 0.0141 + 0.0006 * wh
    beta_b_sig_z1 = 1.5 * (0.0172 + (0.0003 * wh))
    beta_b_mu_z1_c1 = -0.0217 + (0.0016 * wh)

    u = beta_b_u_c1 + beta_b_u_c2 * e.U_AMB
    e.LAMBDA = 1.0
    sig_y1 = beta_b_sig_y1_c1 * e.SX1
    sig_z1 = beta_b_sig_z1 * e.SX1
    sig_y2 = 1.0
    sig_z2 = 1.0
    e.MU_Y1 = 0.0
    e.MU_Z1 = e.HSS + beta_b_mu_z1_c1 * e.SX1
    e.MU_Y2 = 0.0
    e.MU_Z2 = 0.0
    rho = 0.0
    e.SWCONC = _terminos(e, u, sig_y1, sig_z1, sig_y2, sig_z2, rho)


def oblique(e):
    """OBLIQUE: concentración con el viento oblicuo a la fachada (15 a 60 grados) (SWCONC)."""
    if e.SX1 < 0.0:
        e.SWCONC = 0.0
        return
    th = e.SWTHETA
    wh = e.BWS / e.BHS
    beta_b_u_c1 = (-0.0555 * wh)
    beta_b_u_c2 = 0.975993
    beta_b_lambda = -0.416614 + (0.003644 * th) + (-0.012852 * wh)
    beta_b_sig_y1_c1 = 0.026233
    beta_b_sig_y1_c2 = -0.00117
    beta_b_sig_z1 = 1.83e-02 + (-3.83e-05 * th) + (-5.81e-04 * wh)
    beta_b_sig_y2 = 2.67e-02 + (-8.50e-05 * th) + (4.93e-04 * wh)
    beta_b_sig_z2_c1 = 0.0385 + (-0.000171 * th) + (-0.0014 * wh)
    beta_b_sig_z2_c2 = -0.00191 + (0.0000108 * th) + (0.000118 * wh)
    beta_b_mu_y1_c1 = 0.015081 + (0.000243 * th) + (-0.0031 * wh)
    beta_b_mu_y1_c2 = -0.00175 + (-0.0000178 * th) + (0.000331 * wh)
    beta_b_mu_z1_c1 = -0.03578 + (-0.00029 * th) + (0.00224 * wh)
    beta_b_mu_z1_c2 = 0.00186 + (0.00000833 * th) + (-0.000116 * wh)
    beta_b_mu_y2 = 2.21e-02 + (-1.82e-04 * th) + (9.71e-04 * wh)
    beta_b_mu_z2 = -0.357069 + (0.002894 * th) + (0.002252 * wh)
    beta_b_rho_c1 = 0.012006
    beta_b_rho_c2 = -0.00039

    sx1 = e.SX1
    sx2 = sx1 * sx1
    u = beta_b_u_c1 + beta_b_u_c2 * e.U_AMB
    e.LAMBDA = _e(_m(beta_b_lambda, sx1))
    sig_y1 = beta_b_sig_y1_c1 * sx1 + beta_b_sig_y1_c2 * sx2
    sig_z1 = beta_b_sig_z1 * sx1
    sig_y2 = beta_b_sig_y2 * sx1
    sig_z2 = beta_b_sig_z2_c1 * sx1 + beta_b_sig_z2_c2 * sx2
    e.MU_Y1 = beta_b_mu_y1_c1 * sx1 + beta_b_mu_y1_c2 * sx2
    e.MU_Z1 = e.HSS + beta_b_mu_z1_c1 * sx1 + beta_b_mu_z1_c2 * sx2
    e.MU_Y2 = beta_b_mu_y2 * sx1
    e.MU_Z2 = _m(e.BHS, _e(_m(beta_b_mu_z2, sx1)))
    rho = beta_b_rho_c1 * sx1 + beta_b_rho_c2 * sx2
    e.SWCONC = _terminos(e, u, sig_y1, sig_z1, sig_y2, sig_z2, rho)


def _terminos(e, u, sig_y1, sig_z1, sig_y2, sig_z2, rho):
    """Ecuación gaussiana de doble penacho común a PERPEN y OBLIQUE (TERM1..TERM5): penacho
    principal con correlación RHO y reflexión en el suelo, más el penacho de la estela. Cada
    operación pasa por ``_z`` (los subnormales a cero, como el exe)."""
    qs = e.QS
    lam = e.LAMBDA
    sy1, swz = e.SY1, e.SWZ
    mu_y1, mu_z1, mu_y2, mu_z2 = e.MU_Y1, e.MU_Z1, e.MU_Y2, e.MU_Z2
    dos_pi = 2.0 * e.PI
    rho2 = _m(rho, rho)
    term1 = _d(_m(lam, qs), _m(_m(_m(_m(dos_pi, u), sig_y1), sig_z1), _sqrt(1.0 - rho2)))
    # segundo término
    term2a = _d(-1.0, _m(2.0, 1.0 - rho2))
    dy = _z(sy1 - mu_y1)
    dz = _z(swz - mu_z1)
    term2b = _d(_m(dy, dy), _m(sig_y1, sig_y1))
    term2c = _d(_m(dz, dz), _m(sig_z1, sig_z1))
    term2d = _d(_m(_m(_m(2.0, rho), dy), dz), _m(sig_y1, sig_z1))
    term2 = _e(_m(term2a, _z(_z(term2b + term2c) - term2d)))
    # tercer término (reflexión)
    term2a = _d(-1.0, _m(2.0, 1.0 - rho2))
    dz3 = _z(swz + mu_z1)
    term3b = _d(_m(dy, dy), _m(sig_y1, sig_y1))
    term3c = _d(_m(dz3, dz3), _m(sig_z1, sig_z1))
    term3d = _d(_m(_m(_m(2.0, rho), dy), dz3), _m(sig_y1, sig_z1))
    term3 = _e(_m(term2a, _z(_z(term3b + term3c) - term3d)))
    # cuarto término
    term4 = _d(_m(1.0 - lam, qs), _m(_m(_m(dos_pi, u), sig_y2), sig_z2))
    # quinto término
    dy5 = _z(sy1 - mu_y2)
    dz5 = _z(swz - mu_z2)
    dz5r = _z(swz + mu_z2)
    term5a = _d(_m(dy5, dy5), _m(sig_y2, sig_y2))
    term5b = _d(_m(dz5, dz5), _m(sig_z2, sig_z2))
    term5c = _d(_m(dz5r, dz5r), _m(sig_z2, sig_z2))
    term51 = _e(_m(-0.5, _z(term5a + term5b)))
    term52 = _e(_m(-0.5, _z(term5a + term5c)))
    term5 = _z(term51 + term52)
    return _z(_m(term1, _z(term2 + term3)) + _m(term4, term5))
