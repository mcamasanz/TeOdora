# -*- coding: utf-8 -*-
"""Traducción de AERMOD 26135 (US EPA, dominio público): fuentes de carretera RLINE y RLINEXT.

rline.f (completo): RLCALC, BARRIER_DISPLACEMENT, VEGBARRIERSET, COMPUTE_MET, CREATE_EXP_TABLE,
CREATE_WIND_TABLE, DEPRESSED_DISPLACEMENT, EFFECTIVE_WIND, EXPX, INTERP_COEFFS, MEANDER,
MOST_WIND, NUMERICAL_LINE_SOURCE, PLUME_CONC, POINT_CONC, POLYINTERP, RLEMCONV, SIGMAY, SIGMAZ,
TRANSLATE_ROTATE y VEG_CALC.
soset.f: RLPARM, RLINEBAR_INPUTS (RBARRIER), VBARRIER_INPUTS (VBARRIER), VBARRIER_SETUP,
SBARRIER_INPUTS (SBARRIER), SBARRIER_DCL con WEIGHT_SUM, RLINEDPR_INPUTS (RDEPRESS), más las ramas
de SOCARD de esas claves y de RLEMCONV (``socard``) y la lectura de los extremos de la línea en
SOLOCA (``soloca_rline``).
reset.f: BAREDGEZONE y BARZONE (zonas de borde de las barreras sólidas, opción BAREDGE).
aermod.f (ALLSETUP): reserva de las matrices de RLINE (``reservar``).

Las variables del módulo RLINE_DATA (modules.f) viven en su propio espacio, ``e.RL`` (clase
``RlineDatos``), porque UEFF, SZB y ALPHA coinciden en nombre con variables de MAIN1. Cada rutina
respeta sus USE: un nombre de MAIN1 es ``e.NOMBRE`` y uno de RLINE_DATA es ``e.RL.NOMBRE``.
Excepción: NRLINES, RLMOVESCONV, L_RDEPRESS, L_RBARRIER, FAC_DISPHT e I_ALPHA (que no chocan con
MAIN1) se guardan físicamente en ``e`` porque otras partes ya traducidas los leen o escriben ahí
(SRCSIZ, INPSUM, MODOPT, CRITDS y el núcleo numba); ``e.RL.X`` y ``e.X`` son la misma variable.

Tipos derivados:
  · RLSOURCE(ISRC)%CAMPO → ``e.RL.S_CAMPO[isrc]`` (BARID y BARID2: listas de str).
  · SLDBARR(IB)%X(J) → ``e.RL.SB_X[j, ib]`` (BARID y NUMSEG: ``e.RL.SB_BARID[ib]``,
    ``e.RL.SB_NUMSEG[ib]``).
  · VEGBARR(ISRC)%X(K) → ``e.RL.VB_X[k, isrc]``.

Exactitud: se conserva el orden de las operaciones del Fortran; los literales de precisión
simple (4.47, 2.15, 1.40, 0.02873) se promueven desde float32; las potencias enteras se expanden
en productos; las divisiones, raíces, logaritmos y potencias que pueden recibir argumentos fuera
de dominio usan funciones IEEE (Inf/NaN en lugar de excepciones). Las salidas de depuración
(RLINEDBG, VBRDBG, BARDBG) quedan fuera de alcance (NoTraducido)."""
import math
from decimal import Decimal

import numpy as np

from . import calculo_area, funciones_dispersion, perfiles
from .control import dbl, sindex
from .estado import NoTraducido
from .formato import dsign, fc, fwrite, fx

# ------------------------------------------------------------------------- parámetros
NP = 100                      # puntos de la tabla de viento
MAXSBSEG = 50                 # segmentos máximos de una barrera sólida
ERROR_LIMIT = 5.0e-4          # error de la integración de Romberg
SM_NUM = 1.0e-8
XD_MIN = 1.0
_K = 3                        # orden (2K) de la integración de Romberg
_XINTERP = 0.0
_A = 1.0
_EPS = 1.0e-10                # POLYINTERP

# literales de precisión simple del original (REAL*4 promovidos a doble)
_F4_47 = float(np.float32(4.47))
_F2_15 = float(np.float32(2.15))
_F1_40 = float(np.float32(1.40))
_F0_02873 = float(np.float32(0.02873))

_QFLAG_EMFACT = ("MONTH", "HROFDY", "WSPEED", "SEASON", "SEASHR", "HRDOW", "HRDOW7", "SHRDOW",
                 "SHRDOW7", "MHRDOW", "MHRDOW7")

_CAMPOS_S = ("XSB", "YSB", "ZSB", "XSE", "YSE", "ZSE", "DCL", "INIT_SIGMAZ", "WIDTH", "QEMIS",
             "HTWALL", "DCLWALL", "DEPTH", "WTOP", "WBOTTOM", "HTWALL2", "DCLWALL2")
_CAMPOS_SB = ("XBB", "YBB", "XBE", "YBE", "HT", "Z")
_CAMPOS_VB = ("HT", "WT", "DCL", "LM", "LAI", "WAKE")

# variables de RLINE_DATA guardadas en `e` (ver el docstring del módulo) y su valor inicial
_DELEGADAS = (("NRLINES", 0), ("RLMOVESCONV", False), ("L_RDEPRESS", False),
              ("L_RBARRIER", False), ("FAC_DISPHT", 0.0), ("I_ALPHA", 0))


# ============================================================================ RLINE_DATA
class RlineDatos:
    """Variables del módulo RLINE_DATA con su valor inicial (memoria estática: cero, .FALSE. o
    blanco, salvo RLINEver). Las matrices ALLOCATABLE valen None hasta ``reservar``."""

    def __init__(self, e):
        object.__setattr__(self, "_e", e)
        for n, v in _DELEGADAS:
            if not hasattr(e, n):
                setattr(e, n, v)
        self.RLINEver = "RLINEv1_2"
        self.RLPROCESSED = False
        self.RLFIRSTHR = False
        # RLSOURCE(NSRC)
        self.S_ISRCNUM = None
        for c in _CAMPOS_S:
            setattr(self, "S_" + c, None)
        self.S_BARID = None
        self.S_BARID2 = None
        # SLDBARR(NSBR)
        self.MAXSBSEG = MAXSBSEG
        self.SB_BARID = None
        self.SB_NUMSEG = None
        for c in _CAMPOS_SB:
            setattr(self, "SB_" + c, None)
        self.REEDGE = None
        # VEGBARR(NSRC)
        for c in _CAMPOS_VB:
            setattr(self, "VB_" + c, None)
        self.WRTVDBG = False
        self.RLEMISCONV = None
        # meteorología
        self.SIGMAV = 0.0
        self.DISPHT = 0.0
        self.UEFF = 0.0
        self.THETAW = 0.0
        self.RLWSTAR = 0.0
        self.WSPD_ADJ = 0.0
        self.UMIN = 0.0
        self.SIGZ_Y = 0.0
        self.Z0_A = np.zeros(4)
        self.DH_A = np.zeros(4)
        self.UST_A = np.zeros(4)
        self.LMO_A = np.zeros(4)
        self.ERROR_LIMIT = ERROR_LIMIT
        # fuente
        self.INDQ = 0
        self.SIGMAY0 = 0.0
        self.SIGMAZ0 = 0.0
        self.HRELEASE = 0.0
        self.XSBEGIN = 0.0
        self.YSBEGIN = 0.0
        self.ZSBEGIN = 0.0
        self.XSEND = 0.0
        self.YSEND = 0.0
        self.ZSEND = 0.0
        self.SM_NUM = SM_NUM
        self.XD_MIN = XD_MIN
        self.NP = NP
        # cálculo
        self.XEXP = np.zeros(1001)
        self.AEXP = np.zeros(1001)
        self.BEXP = np.zeros(1001)
        self.DELEXP = 0.0
        self.ZWIND = np.zeros((NP + 1, 4))
        self.AWIND = np.zeros((NP + 1, 4))
        self.BWIND = np.zeros((NP + 1, 4))
        self.DELZ = np.zeros(4)
        self.LOGZMAX = 0.0
        self.LOGZMIN = np.zeros(4)
        self.XRECEP = 0.0
        self.YRECEP = 0.0
        self.ZRECEP = 0.0
        self.XRCP_ROT = None
        self.YRCP_ROT = None
        self.X0 = 0.0
        self.Y0 = 0.0
        self.XR_ROT = 0.0
        self.YR_ROT = 0.0
        self.XSB_ROT = None
        self.YSB_ROT = None
        self.XSE_ROT = None
        self.YSE_ROT = None
        self.BDW_FLAG = None
        self.SHIFT_FLAG = False
        self.SZB = 0.0
        self.XPER = 0.0
        self.THETA_LINE = 0.0
        self.DWU = 0.0
        self.DW_PERU = 0.0
        self.HBU = 0.0
        self.DWD = 0.0
        self.DW_PERD = 0.0
        self.HBD = 0.0
        self.NBARR = 0
        self.UH = 0.0
        self.XSHIFT = 0.0
        self.YSHIFT = 0.0
        self.ALPHA = 0.0
        self.ALPHA_U = 0.0
        self.ALPHA_D = 0.0
        self.FASTRLINE = False
        self.PSY1 = self.PSY2 = self.PSY3 = self.PSY4 = 0.0
        self.PSZ1 = self.PSZ2 = self.PSZ3 = self.PSZ4 = 0.0
        self.PU1 = self.PU2 = self.PU3 = self.PU4 = 0.0
        # barreras vegetales
        self.VDWD = 0.0
        self.VDW_PERD = 0.0
        self.HVBD = 0.0
        self.WVBD = 0.0
        self.LAID = 0.0
        self.LADD = 0.0
        self.WAKED = 0.0
        self.VBARR = 0
        self.VEGBARDW = False
        self.VSZI = 0.0
        self.VUI = 0.0
        self.VU10 = 0.0
        # acumuladores del fichero de depuración
        self.FRAN_SUM = 0.0
        self.SIGMAV_SUM = 0.0
        self.UEFF_SUM = 0.0
        self.VERT_SUM = 0.0
        self.HORZ_SUM = 0.0
        self.CONC_P_SUM = 0.0
        self.CONC_M_SUM = 0.0
        self.POINT_CONC_SUM = 0.0


def _delegada(nombre):
    def _get(self):
        return getattr(self._e, nombre)

    def _set(self, v):
        setattr(self._e, nombre, v)

    return property(_get, _set, doc="RLINE_DATA %s (guardada en e.%s)" % (nombre, nombre))


for _n, _v in _DELEGADAS:
    setattr(RlineDatos, _n, _delegada(_n))


# =========================================================================== ALLSETUP
def reservar(e):
    """Reserva de ALLSETUP (aermod.f) para RLINE: crea ``e.RL`` (si no existe) y sus matrices
    con las dimensiones del original. Devuelve ``e.RL``."""
    rl = getattr(e, "RL", None)
    if rl is None:
        rl = RlineDatos(e)
        e.RL = rl
    nsrc, nrec = e.NSRC, e.NREC
    if e.NRLINES > 0:
        n = nsrc + 1
        # RLSOURCE(NSRC): sin inicialización por defecto en el original (aquí ceros/blancos)
        rl.S_ISRCNUM = np.zeros(n, dtype=np.int64)
        for c in _CAMPOS_S:
            setattr(rl, "S_" + c, np.zeros(n))
        rl.S_BARID = [""] * n
        rl.S_BARID2 = [""] * n
        rl.XSB_ROT = np.zeros(n)
        rl.YSB_ROT = np.zeros(n)
        rl.XSE_ROT = np.zeros(n)
        rl.YSE_ROT = np.zeros(n)
        rl.RLEMISCONV = np.zeros(n)
        rl.BDW_FLAG = np.zeros((n, 3), dtype=np.int64)
        rl.RLMOVESCONV = False
        rl.RLFIRSTHR = True
        rl.XRCP_ROT = np.zeros(nrec + 1)
        rl.YRCP_ROT = np.zeros(nrec + 1)
        if e.NVBR > 0:
            # VEGBARR(NSRC): componentes con inicialización por defecto 0.0
            for c in _CAMPOS_VB:
                setattr(rl, "VB_" + c, np.zeros((3, n)))
    if e.NSBR > 0:
        m = e.NSBR + 1
        rl.SB_BARID = [""] * m
        rl.SB_NUMSEG = np.zeros(m, dtype=np.int64)
        for c in _CAMPOS_SB:
            setattr(rl, "SB_" + c, np.zeros((MAXSBSEG + 1, m)))
    return rl


# ======================================================================= utilidades IEEE
def _div(a, b):
    """División IEEE (±Inf o NaN al dividir por cero)."""
    if b == 0.0:
        if a == 0.0 or a != a:
            return math.nan
        return math.copysign(math.inf, a) * math.copysign(1.0, b)
    return a / b


def _sqrt(x):
    """DSQRT IEEE (NaN para negativos)."""
    return math.sqrt(x) if x >= 0.0 else math.nan


def _log(x):
    """DLOG IEEE (-Inf en 0, NaN para negativos)."""
    if x > 0.0:
        return math.log(x)
    if x == 0.0:
        return -math.inf
    return math.nan


def _exp(x):
    """DEXP IEEE (+Inf si desborda)."""
    try:
        return math.exp(x)
    except OverflowError:
        return math.inf


def _pow(x, y):
    """x**y con exponente real como el Fortran (pow de C): base negativa con exponente no
    entero → NaN; 0**negativo → +Inf; desbordamiento → Inf."""
    if x != x or y != y:
        return 1.0 if (x == 1.0 or y == 0.0) else math.nan
    if x == 0.0 and y < 0.0:
        return math.inf
    if x < 0.0 and y != math.floor(y):
        return math.nan
    try:
        return x ** y
    except OverflowError:
        return math.inf


def _acos(x):
    """DACOS IEEE (NaN fuera de [-1, 1])."""
    if -1.0 <= x <= 1.0:
        return math.acos(x)
    return math.nan


def _modulo(a, p):
    """MODULO real: resto con el signo de P."""
    if not math.isfinite(a):
        return math.nan
    r = math.fmod(a, p)
    if r != 0.0 and ((r < 0.0) != (p < 0.0)):
        r = r + p
    return r


_IND = -2147483648            # entero «indefinido» de x86 (NaN, ±Inf o fuera de rango)


def _i4(x):
    """INT() de un real a INTEGER*4 (truncamiento, conversión de x86)."""
    if x != x or x >= 2147483648.0 or x <= -2147483649.0:
        return _IND
    return int(x)


def _floor_i4(x):
    """FLOOR() de un real a INTEGER*4."""
    if x != x or x >= 2147483648.0 or x < -2147483648.0:
        return _IND
    return math.floor(x)


def _ceiling_i4(x):
    """CEILING() de un real a INTEGER*4."""
    if x != x or x > 2147483647.0 or x <= -2147483649.0:
        return _IND
    return math.ceil(x)


def _i32(n):
    """Aritmética entera de 32 bits con desbordamiento cíclico."""
    return ((n + 2147483648) % 4294967296) - 2147483648


# trigonometría en grados (DSIND, DCOSD, DTAND de Intel): reducción exacta a [-45, 45] grados y
# paso a radianes en doble-doble para acercarse al redondeo correcto (valores exactos en los
# múltiplos de 90)
_PI180 = Decimal("0.0174532925199432957692369076848861271344287188854172545609719144")
_R_HI = float(_PI180)
_R_LO = float(_PI180 - Decimal(_R_HI))
_SPLIT = 134217729.0          # 2**27 + 1 (separación de Dekker)


def _rad(y):
    """y grados (|y| <= 45) → (a, b) con a + b ≈ y*pi/180."""
    a = y * _R_HI
    t = _SPLIT * y
    yh = t - (t - y)
    yl = y - yh
    t = _SPLIT * _R_HI
    rh = t - (t - _R_HI)
    rlo = _R_HI - rh
    err = ((yh * rh - a) + yh * rlo + yl * rh) + yl * rlo
    return a, err + y * _R_LO


def _sin_r(y):
    a, b = _rad(y)
    return math.sin(a) + math.cos(a) * b


def _cos_r(y):
    a, b = _rad(y)
    return math.cos(a) - math.sin(a) * b


def _reducir(x, periodo):
    r = math.fmod(x, periodo)
    q = int(round(r / 90.0))
    return q, r - 90.0 * q


def _sind(x):
    if not math.isfinite(x):
        return math.nan
    q, y = _reducir(x, 360.0)
    q %= 4
    if q == 0:
        return _sin_r(y)
    if q == 1:
        return _cos_r(y)
    if q == 2:
        return -_sin_r(y)
    return -_cos_r(y)


def _cosd(x):
    if not math.isfinite(x):
        return math.nan
    q, y = _reducir(x, 360.0)
    q %= 4
    if q == 0:
        return _cos_r(y)
    if q == 1:
        return -_sin_r(y)
    if q == 2:
        return -_cos_r(y)
    return _sin_r(y)


def _tand(x):
    if not math.isfinite(x):
        return math.nan
    q, y = _reducir(x, 180.0)
    if q % 2 == 0:
        return _div(_sin_r(y), _cos_r(y))
    if y == 0.0:
        return math.inf if q > 0 else -math.inf
    return _div(-_cos_r(y), _sin_r(y))


def _print(e, *items):
    """PRINT * dirigido por lista (Intel): blanco inicial, elementos seguidos y registro nuevo
    cuando un elemento no cabe en 80 columnas."""
    regs = []
    act = " "
    for it in items:
        if len(act) + len(it) > 80 and len(act) > 1:
            regs.append(act)
            act = " "
        act += it
    regs.append(act)
    e.pantalla.w(regs)


# ============================================================================== RLCALC
def rlcalc(e):
    """RLCALC: concentración de la fuente RLINE/RLINEXT ISRC en todos los receptores (suma a los
    grupos con SUMVAL; con ARM2 la guarda en CHI)."""
    from .resultados import sumval
    rl = e.RL
    isrc = e.ISRC
    e.DISTR = 0.0
    e.HRVAL[:] = 0.0
    edgesave = False
    rl.VSZI = 0.0
    rl.VEGBARDW = False

    # emisión de la hora (QEMIS local)
    qemis = float(rl.S_QEMIS[isrc])
    qflag = e.QFLAG[isrc]
    if qflag == "HOURLY":
        if e.L_HRLYSIG[isrc]:
            rl.S_ZSB[isrc] = e.AHS[isrc]
            rl.S_ZSE[isrc] = e.AHS[isrc]
            rl.S_INIT_SIGMAZ[isrc] = e.ASZINI[isrc]
        if e.SRCTYP[isrc] == "RLINEXT":
            qemis = float(e.AQS[isrc])
        else:
            qemis = float(e.AQS[isrc]) * float(rl.S_WIDTH[isrc])
    elif qflag in _QFLAG_EMFACT:
        funciones_dispersion.emfact(e, 1.0)
        qemis = float(rl.S_QEMIS[isrc]) * e.QTK

    # cálculos de la primera hora
    if rl.RLFIRSTHR:
        create_exp_table(e)
        rlemconv(e)
        rl.RLFIRSTHR = False

    sfcz0_sav = e.SFCZ0
    zi_orig = e.ZI
    mx = e.MXGLVL
    if e.URBSRC[isrc] == "Y":
        for i in range(1, e.NUMURB + 1):
            if e.IURBGRP[isrc, i] == 1:
                e.IURB = i
                break
        iu = e.IURB
        if e.STABLE or e.L_MORNINGTRANS[iu]:
            e.URBSTAB = True
            e.ZI = max(float(e.ZIURB[iu]), e.ZIMECH)
            e.GRIDSV[1:mx + 1] = e.GRDSVU[1:mx + 1, iu]
            e.OBULEN = float(e.URBOBULEN[iu])
            e.USTAR = float(e.URBUSTR[iu])
            rl.RLWSTAR = float(e.URBWSTR[iu])
            e.SFCZ0 = float(e.URBZ0[iu])
        else:
            e.URBSTAB = False
            e.ZI = e.ZIRUR
            e.GRIDSV[1:mx + 1] = e.GRDSVR[1:mx + 1]
            e.OBULEN = e.RUROBULEN
            e.USTAR = e.RURUSTR
            rl.RLWSTAR = e.WSTAR
    elif e.URBAN and e.URBSRC[isrc] == "N":
        e.URBSTAB = False
        e.ZI = e.ZIRUR
        e.GRIDSV[1:mx + 1] = e.GRDSVR[1:mx + 1]
        e.OBULEN = e.RUROBULEN
        e.USTAR = e.RURUSTR
        rl.RLWSTAR = e.WSTAR
    else:
        e.URBSTAB = False
        rl.RLWSTAR = e.WSTAR
    zi_sav = e.ZI

    if not rl.RLPROCESSED:
        translate_rotate(e)

    # fuente trasladada y girada
    rl.SIGMAZ0 = float(rl.S_INIT_SIGMAZ[isrc])
    rl.XSBEGIN = float(rl.XSB_ROT[isrc])
    rl.YSBEGIN = float(rl.YSB_ROT[isrc])
    rl.XSEND = float(rl.XSE_ROT[isrc])
    rl.YSEND = float(rl.YSE_ROT[isrc])
    rl.ZSBEGIN = float(rl.S_ZSB[isrc])
    rl.ZSEND = float(rl.S_ZSE[isrc])

    # el comienzo de la línea es el extremo de menor Y
    if rl.YSEND < rl.YSBEGIN:
        xtemp = rl.XSEND
        ytemp = rl.YSEND
        ztemp = rl.ZSEND
        rl.XSEND = rl.XSBEGIN
        rl.YSEND = rl.YSBEGIN
        rl.ZSEND = rl.ZSBEGIN
        rl.XSBEGIN = xtemp
        rl.YSBEGIN = ytemp
        rl.ZSBEGIN = ztemp
    rl.THETA_LINE = math.atan2(rl.YSEND - rl.YSBEGIN, rl.XSEND - rl.XSBEGIN)

    # desplazamiento vertical por barreras sólidas
    if rl.S_HTWALL[isrc] > 0.0 or rl.S_HTWALL2[isrc] > 0.0:
        barrier_displacement(e)
    else:
        rl.NBARR = 0
        rl.SHIFT_FLAG = False
        rl.XSHIFT = 0.0
        rl.YSHIFT = 0.0
        rl.HBU = 0.0
        rl.HBD = 0.0

    # barreras vegetales (solo sin barreras sólidas)
    if rl.NBARR == 0 and e.VBARSET:
        if rl.VB_HT[1, isrc] > 0.0 or rl.VB_HT[2, isrc] > 0.0:
            vegbarrierset(e)

    # sigma-y inicial a partir del ancho de la vía
    rl.SIGMAY0 = 0.0
    rl.SIGMAY0 = abs(0.5 * float(rl.S_WIDTH[isrc]) * math.cos(rl.THETA_LINE))

    compute_met(e)

    if e.FASTALL:
        interp_coeffs(e)

    e.ZS = float(e.AZS[isrc])

    # sigma-z inicial y viento del caso sin barrera para las ecuaciones de barrera vegetal
    if rl.VEGBARDW:
        rl.I_ALPHA = 1
        effective_wind(e, rl.VDWD, e.ZS, 0.0)
        rl.VUI = rl.UEFF
        rl.VSZI = sigmaz(e, rl.VDWD) * (0.042 * rl.HVBD + 1.118) * \
            (_F0_02873 * rl.LAID + 0.7883)
        rl.VU10 = most_wind(e, 10.0, 1)
        if 3.0 * rl.VSZI > 2.2 * rl.HVBD:
            rl.VEGBARDW = False
            if e.VBRDBG:
                raise NoTraducido("VBRDBG")
        else:
            if e.VBRDBG:
                raise NoTraducido("VBRDBG")

    # bucle de receptores
    nbarr_sav = 0
    shift_flag_sav = False
    xshift_sav = yshift_sav = hbu_sav = hbd_sav = dwu_sav = dwd_sav = 0.0
    dw_peru_sav = dw_perd_sav = alpha_u_sav = alpha_d_sav = 0.0
    for irec in range(1, e.NUMREC + 1):
        e.IREC = irec
        e.ZI = zi_sav
        concd = 0.0
        concentration = 0.0
        if e.RLINEDBG:
            raise NoTraducido("RLINEDBG")
        if e.VBRDBG:
            rl.WRTVDBG = True

        rl.XR_ROT = float(rl.XRCP_ROT[irec])
        rl.YR_ROT = float(rl.YRCP_ROT[irec])
        rl.ZRECEP = float(e.AZFLAG[irec])

        e.ZFLAG = float(e.AZFLAG[irec])
        e.ZELEV = float(e.AZELEV[irec])
        e.ZHILL = float(e.AZHILL[irec])

        # efecto de borde: receptor fuera de la zona de la barrera → valores sin barrera
        if rl.NBARR > 0 and e.BAREDGE:
            if not rl.REEDGE[irec]:
                edgesave = True
                nbarr_sav = rl.NBARR
                shift_flag_sav = rl.SHIFT_FLAG
                xshift_sav = rl.XSHIFT
                yshift_sav = rl.YSHIFT
                hbu_sav = rl.HBU
                hbd_sav = rl.HBD
                dwu_sav = rl.DWU
                dwd_sav = rl.DWD
                dw_peru_sav = rl.DW_PERU
                dw_perd_sav = rl.DW_PERD
                alpha_u_sav = rl.ALPHA_U
                alpha_d_sav = rl.ALPHA_D
                rl.NBARR = 0
                rl.SHIFT_FLAG = False
                rl.XSHIFT = 0.0
                rl.YSHIFT = 0.0
                rl.HBU = 0.0
                rl.HBD = 0.0
                rl.DWU = 0.0
                rl.DWD = 0.0
                rl.DW_PERU = 0.0
                rl.DW_PERD = 0.0
                rl.ALPHA_U = 1.0
                rl.ALPHA_D = 1.0

        concd, _error = numerical_line_source(e)

        # EMIFAC(1): factor de concentración; RLEMISCONV: unidades de MOVES
        concentration = concd * e.EMIFAC[1] * qemis * rl.RLEMISCONV[isrc]
        e.HRVAL[1:] = concentration

        if e.ARM2:
            for ityp in range(1, e.NUMTYP + 1):
                e.ITYP = ityp
                e.CHI[irec, isrc, ityp] = e.HRVAL[ityp]
            e.ITYP = e.NUMTYP + 1
            e.HRVAL[:] = 0.0

        if e.EVONLY:
            raise NoTraducido("EVENT")
        else:
            for igrp in range(1, e.NUMGRP + 1):
                e.IGRP = igrp
                sumval(e)
            e.IGRP = e.NUMGRP + 1

        e.HRVAL[:] = 0.0

        if edgesave:
            edgesave = False
            rl.NBARR = nbarr_sav
            rl.SHIFT_FLAG = shift_flag_sav
            rl.XSHIFT = xshift_sav
            rl.YSHIFT = yshift_sav
            rl.HBU = hbu_sav
            rl.HBD = hbd_sav
            rl.DWU = dwu_sav
            rl.DWD = dwd_sav
            rl.DW_PERU = dw_peru_sav
            rl.DW_PERD = dw_perd_sav
            rl.ALPHA_U = alpha_u_sav
            rl.ALPHA_D = alpha_d_sav
    e.IREC = e.NUMREC + 1

    e.SFCZ0 = sfcz0_sav
    e.ZI = zi_orig


# ================================================================== barreras sólidas
def _alpha_vs(z0, sfcz0):
    """Alfa de Venkatram y Schulte (2018): MAX(1, EXP(0.14*LOG(Z0/SFCZ0)))."""
    return max(1.0, _exp(0.14 * _log(_div(z0, sfcz0))))


def barrier_displacement(e):
    """BARRIER_DISPLACEMENT: barreras a barlovento/sotavento de la fuente, distancias a lo largo
    del viento, alfas y desplazamiento de la fuente por la zona de recirculación."""
    rl = e.RL
    isrc = e.ISRC
    sfcz0 = e.SFCZ0
    i = 2
    rl.HBD = 0.0
    rl.DW_PERD = 0.0
    rl.DWD = 0.0
    rl.HBU = 0.0
    rl.DW_PERU = 0.0
    rl.DWU = 0.0
    rl.NBARR = 0
    rl.SHIFT_FLAG = False
    rl.XSHIFT = 0.0
    rl.YSHIFT = 0.0
    recirc_length = 0.0
    rl.ALPHA_U = 1.0
    rl.ALPHA_D = 1.0
    z0 = sfcz0

    if rl.S_HTWALL[isrc] > 0.0 or rl.S_HTWALL2[isrc] > 0.0:
        rl.ZSBEGIN = 0.5 * (rl.ZSBEGIN + rl.ZSEND)
        rl.ZSEND = rl.ZSBEGIN

        dcl = float(rl.S_DCL[isrc])
        hb = [0.0, float(rl.S_HTWALL[isrc]), float(rl.S_HTWALL2[isrc])]
        dw_per = [0.0, abs(float(rl.S_DCLWALL[isrc]) - dcl), abs(float(rl.S_DCLWALL2[isrc]) - dcl)]
        den = abs(math.sin(rl.THETA_LINE)) + SM_NUM
        dw = [0.0, dw_per[1] / den, dw_per[2] / den]

        if hb[1] > 0.0 and hb[2] > 0.0:
            rl.NBARR = 2
        elif hb[1] == 0.0 and hb[2] == 0.0:
            rl.NBARR = 0
        elif hb[1] > 0.0 or hb[2] == 0.0:
            rl.NBARR = 1
        else:
            rl.NBARR = -1

        bdw = rl.BDW_FLAG
        if rl.NBARR == 0:
            rl.DW_PERU = 0.0
            rl.DWU = 0.0
            rl.DW_PERD = 0.0
            rl.DWD = 0.0
        elif rl.NBARR == 1:
            if hb[1] > 0.0:
                i = 1
            if bdw[isrc, i] == 1:
                rl.HBD = hb[i]
                rl.DWD = dw[i]
                rl.DW_PERD = dw_per[i]
                rl.HBU = 0.0
                rl.DWU = 0.0
                rl.DW_PERU = 0.0
                z0 = max(rl.HBD / 9.0, sfcz0)
                rl.ALPHA_D = _alpha_vs(z0, sfcz0)
            else:
                rl.HBD = 0.0
                rl.DWD = 0.0
                rl.DW_PERD = 0.0
                rl.HBU = hb[i]
                rl.DWU = dw[i]
                rl.DW_PERU = dw_per[i]
                z0 = max(rl.HBU / 9.0, sfcz0)
                rl.ALPHA_U = _alpha_vs(z0, sfcz0)
                recirc_length = 6.5 * rl.HBU
        elif rl.NBARR == 2:
            if bdw[isrc, 1] == bdw[isrc, 2]:
                _print(e, "WARNING: Both barriers associated with source ", fx(e.SRCID[isrc], 12),
                       " are on the same side of the source.")
                _print(e, "Barrier closer to source will be used.")
                e.errhdl(e.PATH, "RLINE", "W", "620", e.SRCID[isrc])
                rl.NBARR = 1
                i = 2
                if abs(dw_per[1]) < abs(dw_per[2]):
                    i = 1
                if bdw[isrc, i] == 1:
                    rl.HBD = hb[i]
                    rl.DWD = dw[i]
                    rl.DW_PERD = dw_per[i]
                    rl.HBU = 0.0
                    rl.DWU = 0.0
                    rl.DW_PERU = 0.0
                    z0 = max(rl.HBD / 9.0, sfcz0)
                    rl.ALPHA_D = _alpha_vs(z0, sfcz0)
                else:
                    rl.HBD = 0.0
                    rl.DWD = 0.0
                    rl.DW_PERD = 0.0
                    rl.HBU = hb[i]
                    rl.DWU = dw[i]
                    rl.DW_PERU = dw_per[i]
                    z0 = max(rl.HBU / 9.0, sfcz0)
                    rl.ALPHA_U = _alpha_vs(z0, sfcz0)
                    recirc_length = 6.5 * rl.HBU
            else:
                if bdw[isrc, 1] == 1:
                    rl.HBD = hb[1]
                    rl.DW_PERD = dw_per[1]
                    rl.DWD = dw[1]
                    rl.HBU = hb[2]
                    rl.DW_PERU = dw_per[2]
                    rl.DWU = dw[2]
                    recirc_length = 4.0 * rl.HBU
                else:
                    rl.HBD = hb[2]
                    rl.DW_PERD = dw_per[2]
                    rl.DWD = dw[2]
                    rl.HBU = hb[1]
                    rl.DW_PERU = dw_per[1]
                    rl.DWU = dw[1]
                    recirc_length = 4.0 * rl.HBU
                z0 = max(rl.HBU / 9.0, sfcz0)
                rl.ALPHA_U = _alpha_vs(z0, sfcz0)
                z0 = max(rl.HBD / 9.0, sfcz0)
                rl.ALPHA_D = _alpha_vs(z0, sfcz0)
        else:
            _print(e, "WARNING: Barriers input problem with source ", fwrite("(I12)", isrc)[0])

        # desplazamiento de la fuente si está en la recirculación de la barrera de barlovento
        if rl.HBU > 0.0 and rl.DW_PERU < recirc_length:
            rl.SHIFT_FLAG = True
            rl.XSHIFT = rl.DW_PERU * math.sin(rl.THETA_LINE)
            rl.YSHIFT = -1.0 * rl.DW_PERU * math.cos(rl.THETA_LINE)
            rl.DWD = rl.DWD + rl.XSHIFT
        else:
            rl.SHIFT_FLAG = False
            rl.XSHIFT = 0.0
            rl.YSHIFT = 0.0


def vegbarrierset(e):
    """VEGBARRIERSET: barrera vegetal a sotavento de la fuente (altura, distancias, ancho, LAI,
    densidad foliar y estela)."""
    rl = e.RL
    isrc = e.ISRC
    i = 2
    rl.HVBD = 0.0
    rl.VDW_PERD = 0.0
    rl.VDWD = 0.0
    rl.VBARR = 0
    rl.VEGBARDW = True
    rl.WVBD = 0.0
    rl.LAID = 0.0
    rl.LADD = 0.0
    rl.WAKED = 0.0

    rl.ZSBEGIN = 0.5 * (rl.ZSBEGIN + rl.ZSEND)
    rl.ZSEND = rl.ZSBEGIN

    dcl = float(rl.S_DCL[isrc])
    hb = [0.0, float(rl.VB_HT[1, isrc]), float(rl.VB_HT[2, isrc])]
    dw_per = [0.0, abs(float(rl.VB_DCL[1, isrc]) - dcl), abs(float(rl.VB_DCL[2, isrc]) - dcl)]
    den = abs(math.sin(rl.THETA_LINE)) + SM_NUM
    dw = [0.0, dw_per[1] / den, dw_per[2] / den]

    if hb[1] > 0.0 and hb[2] > 0.0:
        rl.VBARR = 2
    elif hb[1] == 0.0 and hb[2] == 0.0:
        rl.VBARR = 0
    elif hb[1] > 0.0 or hb[2] == 0.0:
        rl.VBARR = 1
    else:
        rl.VBARR = -1

    bdw = rl.BDW_FLAG

    def _sotavento(k):
        rl.HVBD = hb[k]
        rl.VDWD = dw[k]
        rl.VDW_PERD = dw_per[k]
        rl.WVBD = float(rl.VB_WT[k, isrc])
        rl.LAID = float(rl.VB_LAI[k, isrc])
        rl.LADD = float(rl.VB_LM[k, isrc])
        rl.WAKED = float(rl.VB_WAKE[k, isrc])

    def _barlovento():
        rl.HVBD = 0.0
        rl.VDWD = 0.0
        rl.VDW_PERD = 0.0
        rl.VEGBARDW = False

    if rl.VBARR == 0:
        pass
    elif rl.VBARR == 1:
        if hb[1] > 0.0:
            i = 1
        if bdw[isrc, i] == 1:
            _sotavento(i)
        else:
            _barlovento()
    elif rl.VBARR == 2:
        if bdw[isrc, 1] == bdw[isrc, 2]:
            _print(e, "WARNING: Both barriers associated with source", fx(e.SRCID[isrc], 12),
                   " are on the same side of the source.")
            _print(e, "Barrier closer to source will be used.")
            e.errhdl(e.PATH, "RLINE", "W", "620", e.SRCID[isrc])
            rl.VBARR = 1
            i = 2
            if abs(dw_per[1]) < abs(dw_per[2]):
                i = 1
            if bdw[isrc, i] == 1:
                _sotavento(i)
            else:
                _barlovento()
        else:
            if bdw[isrc, 1] == 1:
                _sotavento(1)
            else:
                _sotavento(2)
    else:
        _print(e, "WARNING: Barriers input problem with source ", fwrite("(I12)", isrc)[0])

    if rl.HVBD == 0.0:
        rl.VEGBARDW = False


# ======================================================================= meteorología
def compute_met(e):
    """COMPUTE_MET: sigma-v a la altura de referencia, rugosidades/alfas de los casos sin barrera,
    barrera a sotavento y a barlovento, tabla de viento, viento mínimo, ajuste a UREF, viento a la
    altura de la barrera y viento en la malla para CRITDS (RL_GRIDWS)."""
    rl = e.RL
    rl.UH = 0.0

    gh = e.GRIDHT
    ndx = perfiles.locate(gh, 1, e.MXGLVL, e.UREFHT)
    rl.SIGMAV = perfiles.gintrp(gh[ndx], e.GRIDSV[ndx], gh[ndx + 1], e.GRIDSV[ndx + 1], e.UREFHT)
    rl.SIGMAV = float(max(rl.SIGMAV, e.SVMIN))

    if e.RLINEDBG:
        raise NoTraducido("RLINEDBG")

    sfcz0 = e.SFCZ0
    rl.Z0_A[1] = sfcz0
    rl.Z0_A[2] = max(rl.HBD / 9.0, sfcz0)
    rl.Z0_A[3] = max(rl.HBU / 9.0, sfcz0)
    for ia in range(1, 4):
        rl.DH_A[ia] = rl.FAC_DISPHT * rl.Z0_A[ia]
    rl.DISPHT = float(rl.DH_A[1])
    alphas = (0.0, 1.0, rl.ALPHA_D, rl.ALPHA_U)
    for ia in range(1, 4):
        rl.UST_A[ia] = e.USTAR * alphas[ia]
    for ia in range(1, 4):
        a = alphas[ia]
        rl.LMO_A[ia] = e.OBULEN * (a * a * a)

    create_wind_table(e)

    rl.I_ALPHA = 1
    rl.UMIN = max(_F4_47 * float(rl.UST_A[rl.I_ALPHA]), e.RTOF2 * rl.SIGMAV)
    rl.UMIN = max(rl.UMIN, e.WSMIN)
    rl.WSPD_ADJ = 1.0
    urefcalc = most_wind(e, e.UREFHT, rl.I_ALPHA)
    rl.WSPD_ADJ = _div(e.UREF, urefcalc)

    if rl.HBD > 0.0:
        rl.I_ALPHA = 2
        rl.UH = most_wind(e, rl.HBD, rl.I_ALPHA)

    # viento en la malla para CRITDS (las tres columnas iguales: solo el caso sin barrera)
    e.RL_GRIDWS[:, :] = 0.0
    _zimech_ws = most_wind(e, e.ZI, 1)
    for npt in range(1, e.MXGLVL + 1):
        rl.I_ALPHA = 1
        e.RL_GRIDWS[npt, 1:4] = most_wind(e, float(gh[npt]), rl.I_ALPHA)
        rl.I_ALPHA = 2         # variable del DO al terminar (DO I_ALPHA = 1,1)

    if e.RLINEDBG:
        if not rl.RLPROCESSED:
            raise NoTraducido("RLINEDBG")


def create_exp_table(e):
    """CREATE_EXP_TABLE: tabla de interpolación lineal de la exponencial en [-20, 0]."""
    rl = e.RL
    ext = [0.0] * 1001
    rl.DELEXP = 20.0 / 999.0
    rl.XEXP[1] = -20.0
    ext[1] = math.exp(float(rl.XEXP[1]))
    for ind in range(2, 1001):
        rl.XEXP[ind] = rl.XEXP[ind - 1] + rl.DELEXP
        ext[ind] = math.exp(float(rl.XEXP[ind]))
    for ind in range(1, 1000):
        rl.BEXP[ind] = (ext[ind + 1] - ext[ind]) / (float(rl.XEXP[ind + 1]) - float(rl.XEXP[ind]))
        rl.AEXP[ind] = ext[ind] - float(rl.BEXP[ind]) * float(rl.XEXP[ind])
    rl.BEXP[1000] = rl.BEXP[999]
    rl.AEXP[1000] = rl.AEXP[999]


def create_wind_table(e):
    """CREATE_WIND_TABLE: tabla del perfil de viento de Monin-Obukhov (alturas espaciadas en
    logaritmo) para los tres casos de barrera; pendientes y ordenadas para MOST_WIND."""
    rl = e.RL
    npt = NP
    z0a, dha, usta, lmoa = rl.Z0_A, rl.DH_A, rl.UST_A, rl.LMO_A
    zw = rl.ZWIND
    for ia in range(1, 4):
        rl.LOGZMAX = max(math.log(500.0), _log(e.ZI))
        rl.LOGZMIN[ia] = _log(float(z0a[ia]) + float(dha[ia]))
        rl.DELZ[ia] = (rl.LOGZMAX - float(rl.LOGZMIN[ia])) / float(npt - 1)
        expdelz = _exp(float(rl.DELZ[ia]))
        zw[1, ia] = z0a[ia] + dha[ia]
        for iz in range(2, npt + 1):
            zw[iz, ia] = float(zw[iz - 1, ia]) * expdelz

    psi1 = [[0.0] * 4 for _ in range(npt + 1)]
    psi2 = [0.0] * 4
    if e.STABLE:
        for ia in range(1, 4):
            lmoa[ia] = abs(float(lmoa[ia]))
        for ia in range(1, 4):
            dh = float(dha[ia])
            lmo = float(lmoa[ia])
            for iz in range(1, npt + 1):
                psi1[iz][ia] = -17.0 * (1.0 - _exp(_div(-0.29 * (float(zw[iz, ia]) - dh), lmo)))
            psi2[ia] = -17.0 * (1.0 - _exp(_div(-0.29 * float(z0a[ia]), lmo)))
    else:
        for ia in range(1, 4):
            lmoa[ia] = -1.0 * abs(float(lmoa[ia]))
        pi = e.PI
        for ia in range(1, 4):
            dh = float(dha[ia])
            lmo = float(lmoa[ia])
            x1 = [0.0] * (npt + 1)
            for iz in range(1, npt + 1):
                x1[iz] = _sqrt(_sqrt(1.0 - _div(16.0 * (float(zw[iz, ia]) - dh), lmo)))
            x2 = _sqrt(_sqrt(1.0 - _div(16.0 * float(z0a[ia]), lmo)))
            for iz in range(1, npt + 1):
                x = x1[iz]
                psi1[iz][ia] = 2.0 * _log((1.0 + x) / 2.0) + _log((1.0 + x * x) / 2.0) - \
                    2.0 * math.atan(x) + pi / 2.0
            psi2[ia] = 2.0 * _log((1.0 + x2) / 2.0) + _log((1.0 + x2 * x2) / 2.0) - \
                2.0 * math.atan(x2) + pi / 2.0

    vonkar = e.VONKAR
    utbl = [[0.0] * 4 for _ in range(npt + 1)]
    for ia in range(1, 4):
        ust = float(usta[ia])
        dh = float(dha[ia])
        z0 = float(z0a[ia])
        for iz in range(1, npt + 1):
            utbl[iz][ia] = ust * (_log(_div(float(zw[iz, ia]) - dh, z0)) - psi1[iz][ia] +
                                  psi2[ia]) / vonkar

    # sin velocidades negativas por redondeo (WHERE)
    for iz in range(1, npt + 1):
        for ia in range(1, 4):
            if utbl[iz][ia] < 0.0:
                utbl[iz][ia] = 0.0

    aw, bw = rl.AWIND, rl.BWIND
    for ia in range(1, 4):
        for iz in range(1, npt):
            bw[iz, ia] = _div(utbl[iz + 1][ia] - utbl[iz][ia], float(zw[iz + 1, ia]) - float(zw[iz, ia]))
        bw[npt, ia] = bw[npt - 1, ia]
        for iz in range(1, npt + 1):
            aw[iz, ia] = utbl[iz][ia] - float(bw[iz, ia]) * float(zw[iz, ia])
        aw[npt, ia] = aw[npt - 1, ia]


def most_wind(e, z, ia):
    """MOST_WIND (FUNCTION): velocidad del viento a la altura Z (caso de barrera IA) por la tabla
    de CREATE_WIND_TABLE, con el ajuste WSPD_ADJ y el mínimo UMIN."""
    rl = e.RL
    zd = max(float(rl.ZWIND[1, ia]), z)
    p = _i4(_div(_log(zd) - float(rl.LOGZMIN[ia]), float(rl.DELZ[ia]))) + 1
    p = min(p, NP)
    if p < 1:
        raise NoTraducido("MOST_WIND: índice %d fuera de la tabla de viento (lectura fuera de "
                          "límites en el original)" % p)
    umost = float(rl.AWIND[p, ia]) + float(rl.BWIND[p, ia]) * zd
    umost = max(umost, rl.UMIN)
    return max(umost * rl.WSPD_ADJ, rl.UMIN)


def expx(e, xp):
    """EXPX (FUNCTION): exponencial por la tabla de CREATE_EXP_TABLE."""
    rl = e.RL
    xpd = xp
    xpd = max(float(rl.XEXP[1]), xpd)
    p = _i4(_floor_i4(_div(xpd + 20.0, rl.DELEXP)) + 1.0)
    if p < 1 or p > 1000:
        raise NoTraducido("EXPX: índice %d fuera de la tabla (lectura fuera de límites en el "
                          "original)" % p)
    return float(rl.AEXP[p]) + float(rl.BEXP[p]) * xpd


def interp_coeffs(e):
    """INTERP_COEFFS: coeficientes de interpolación de UEFF, SIGMAY y SIGMAZ (opción FASTALL) a
    partir de sus valores en x = 1, 10 y 500 m."""
    rl = e.RL
    rl.FASTRLINE = False
    rl.ALPHA = 1.0
    rl.I_ALPHA = 1
    hshift = 0.0
    x1 = 1.0
    x2 = 10.0
    x3 = 500.0
    lnx1 = 0.0
    lnx2 = math.log(x2)
    lnx3 = math.log(x3)
    zs = 0.5 * (rl.ZSBEGIN + rl.ZSEND)

    effective_wind(e, x1, zs, hshift)
    u1 = rl.UEFF
    sz1 = sigmaz(e, x1)
    lnsz1 = _log(sz1)
    sy1 = sigmay(e, x1)
    lnsy1 = _log(sy1)

    effective_wind(e, x2, zs, hshift)
    u2 = rl.UEFF
    sz2 = sigmaz(e, x2)
    lnsz2 = _log(sz2)
    sy2 = sigmay(e, x2)
    lnsy2 = _log(sy2)

    effective_wind(e, x3, zs, hshift)
    u3 = rl.UEFF
    sz3 = sigmaz(e, x3)
    lnsz3 = _log(sz3)
    sy3 = sigmay(e, x3)
    lnsy3 = _log(sy3)

    rl.PU2 = (u2 - u1) / (lnx2 - lnx1)
    rl.PU1 = u2 - rl.PU2 * lnx2
    rl.PU4 = (u3 - u2) / (lnx3 - lnx2)
    rl.PU3 = u2 - rl.PU4 * lnx2

    rl.PSY2 = (lnsy2 - lnsy1) / (lnx2 - lnx1)
    rl.PSY1 = _exp(0.5 * (lnsy1 + lnsy2 - rl.PSY2 * (lnx1 + lnx2)))
    rl.PSY4 = (lnsy3 - lnsy2) / (lnx3 - lnx2)
    rl.PSY3 = _exp(0.5 * (lnsy2 + lnsy3 - rl.PSY4 * (lnx2 + lnx3)))

    rl.PSZ2 = (lnsz2 - lnsz1) / (lnx2 - lnx1)
    rl.PSZ1 = _exp(0.5 * (lnsz1 + lnsz2 - rl.PSZ2 * (lnx1 + lnx2)))
    rl.PSZ4 = (lnsz3 - lnsz2) / (lnx3 - lnx2)
    rl.PSZ3 = _exp(0.5 * (lnsz2 + lnsz3 - rl.PSZ4 * (lnx2 + lnx3)))

    rl.FASTRLINE = True


def effective_wind(e, xd, heff, hshift):
    """EFFECTIVE_WIND: viento efectivo a la altura media del penacho (iterativo). Fija
    ``e.RL.UEFF``."""
    rl = e.RL
    if rl.FASTRLINE:
        if xd <= 10:
            rl.UEFF = rl.PU1 + rl.PU2 * _log(abs(xd))
        else:
            rl.UEFF = rl.PU3 + rl.PU4 * _log(abs(xd))
        return

    zbar = 0.0
    err = 10.0
    it = 1
    rl.UEFF = most_wind(e, heff, rl.I_ALPHA)
    sz = sigmaz(e, xd)
    while err > 1.0e-02 and it < 20:
        t = _div(heff, sz)
        zbar = e.RT2BYPI * sz * expx(e, -0.5 * (t * t)) + \
            heff * math.erf(_div(heff, e.RTOF2 * sz)) + hshift
        rl.UEFF = most_wind(e, max(zbar, heff), rl.I_ALPHA)
        sz_new = sigmaz(e, xd)
        err = abs(_div(sz_new - sz, sz))
        sz = sz_new
        it = it + 1
    if e.RLINEDBG:
        raise NoTraducido("RLINEDBG")


# ======================================================================== dispersión
def sigmay(e, xd):
    """SIGMAY (FUNCTION): dispersión horizontal (usa SIGZ_Y de la última llamada a SIGMAZ)."""
    rl = e.RL
    if rl.FASTRLINE:
        if xd <= 10:
            return rl.PSY1 * _pow(xd, rl.PSY2)
        return rl.PSY3 * _pow(xd, rl.PSY4)
    sz = rl.SIGZ_Y
    if e.STABLE:
        s = _div(1.4 * rl.SIGMAV, e.USTAR) * sz * (1.0 + _div(1.5 * sz, abs(e.OBULEN)))
    else:
        s = _div(_div(_F1_40 * rl.SIGMAV, e.USTAR) * sz,
                 _sqrt(1.0 + _div(2.5 * sz, abs(e.OBULEN))))
    return _sqrt(s * s + rl.SIGMAY0 * rl.SIGMAY0)


def sigmaz(e, xd):
    """SIGMAZ (FUNCTION): dispersión vertical con los efectos de la configuración de la fuente
    (sigma-z inicial, depresión y barrera). Fija ``e.RL.SIGZ_Y``."""
    rl = e.RL
    if rl.FASTRLINE:
        if xd <= 10:
            sigz = rl.PSZ1 * _pow(xd, rl.PSZ2)
        else:
            sigz = rl.PSZ3 * _pow(xd, rl.PSZ4)
        return sigz

    ia = rl.I_ALPHA
    xbar = abs(_div(xd, float(rl.LMO_A[ia])))
    xdabs = abs(xd)
    sigmazd = 0.0
    sigmazb = 0.0
    uratio = _div(float(rl.UST_A[ia]), rl.UEFF)

    if e.STABLE:
        sigz = _div(0.70 * (uratio * xdabs),
                    (1.0 + 1.5 * uratio * (_exp(e.TWOTHIRDS * _log(xbar)))))
    else:
        sigz = 0.70 * (uratio * xdabs) * (1.0 + 1.0 * (uratio * xbar))

    depth = float(rl.S_DEPTH[e.ISRC])
    if depth < 0.0:
        sigmazd = -1.0 * depth / 2.15

    if rl.NBARR > 0:
        sigmazb = rl.SZB

    rl.SIGZ_Y = sigz
    sigz = _sqrt(sigz * sigz + rl.SIGMAZ0 * rl.SIGMAZ0 + sigmazd * sigmazd + sigmazb * sigmazb)
    return sigz


def depressed_displacement(e, theta_line, ind):
    """DEPRESSED_DISPLACEMENT (FUNCTION): desplazamiento de la línea en una vía deprimida."""
    rl = e.RL
    depth = float(rl.S_DEPTH[ind])
    wbottom = float(rl.S_WBOTTOM[ind])
    wtop = float(rl.S_WTOP[ind])
    dcl = float(rl.S_DCL[ind])

    theta_rel = theta_line - rl.THETAW

    effd = _div(wbottom * abs(depth) + ((wtop - wbottom) / 2.0 * abs(depth)), wtop)
    reld = _div(effd, wbottom)

    if reld >= 0.0483:
        fracw = 1.0
    else:
        fracw = -0.0776 + _sqrt(1.506 - 7.143 * reld)

    c = math.cos(abs(theta_rel))
    effw = _pow(fracw, 1.0 - (c * c)) * wbottom
    dcrit = _div(0.2064 * wtop * wbottom, 0.5 * (wtop + wbottom))
    f = min(1.0, _div(wbottom, wtop) * (1.0 + _div(abs(depth), dcrit)))

    s = math.sin(theta_rel)
    return ((wtop * f - effw) / 2.0) * (s * s) * dsign(1.0, s) - \
        (_div(effw, wbottom) * dcl) * dsign(1.0, math.sin(theta_line))


def meander(e, x, y, z, hshift):
    """MEANDER (FUNCTION): contribución del punto (X, Y, Z) suponiendo dispersión radial."""
    rl = e.RL
    dx = rl.XR_ROT - x
    dy = rl.YR_ROT - y
    r = _sqrt(dx * dx + dy * dy)
    r = max(r, XD_MIN)
    heff = max(z, 0.75 * max(rl.HBU, rl.HBD))

    effective_wind(e, r, heff, hshift)

    sz = sigmaz(e, r)
    t1 = _div(heff - rl.ZRECEP, sz)
    t2 = _div(heff + rl.ZRECEP, sz)
    vert = _div(e.RT2BYPI * (expx(e, -0.5 * (t1 * t1)) + expx(e, -0.5 * (t2 * t2))),
                2.0 * sz * rl.UEFF)
    horz = 1.0 / (2.0 * e.PI * r)
    return vert * horz


def veg_calc(e, xd):
    """VEG_CALC: sigma-z y viento efectivo tras una barrera vegetal a sotavento (Hashad et al.
    2024). Devuelve (VSZ, VUEFF)."""
    rl = e.RL
    vsz = 0.0
    vueff = 0.0
    region = 0
    hvbd, wvbd, laid, ladd = rl.HVBD, rl.WVBD, rl.LAID, rl.LADD
    waked, vszi, vui, vu10, vdwd = rl.WAKED, rl.VSZI, rl.VUI, rl.VU10, rl.VDWD

    if xd >= vdwd and xd <= wvbd + vdwd:
        region = 1
        vsz = vszi + (xd - vdwd) * (-0.037 * _pow(hvbd, -1.505) + 0.07)
        vueff = vui + (xd - vdwd) * (0.02233 * _pow(ladd, -1.231) - 0.0149)

    if xd > wvbd + vdwd and xd <= wvbd + vdwd + waked:
        region = 2
        vsz = vszi + wvbd * (-0.037 * _pow(hvbd, -1.505) + 0.07) + (xd - wvbd - vdwd) * 0.013
        vueff = vui + wvbd * (0.02233 * _pow(ladd, -1.231) - 0.0149) + \
            (xd - wvbd - vdwd) * (0.08912 * ladd + 0.7987) * (-0.002252 * vu10)

    if xd > wvbd + vdwd + waked and xd <= wvbd + vdwd + waked + 3.0 * hvbd:
        region = 3
        vsz = vszi + wvbd * (-0.037 * _pow(hvbd, -1.505) + 0.07) + waked * 0.013 + \
            (xd - wvbd - waked - vdwd) * (0.000695) * hvbd * laid
        vueff = vui + wvbd * (0.02233 * _pow(ladd, -1.231) - 0.0149) + \
            waked * (0.08912 * ladd + 0.7987) * (-0.002252 * vu10) + \
            (xd - wvbd - waked - vdwd) * (0.003063 * laid - 0.008317) * (0.4378 * vu10 - 0.3306)

    if xd > wvbd + vdwd + waked + 3.0 * hvbd:
        region = 4
        base = xd - (vdwd + wvbd + waked + 3.0 * hvbd)
        vsz = vszi + wvbd * (-0.037 * _pow(hvbd, -1.505) + 0.07) + waked * 0.013 + \
            (3.0 * hvbd) * (0.000695) * hvbd * laid + base * (0.000695) * hvbd * laid
        u = max(vu10, 1.0)
        c = ((0.1285 * _pow(ladd, -2.105) + 0.4923) * (0.3592 * _pow(u, -18.68) + 0.9558))
        vueff = vui + wvbd * (0.02233 * _pow(ladd, -1.231) - 0.0149) + \
            waked * (0.08912 * ladd + 0.7987) * (-0.002252 * vu10) + \
            (3.0 * hvbd) * (0.003063 * laid - 0.008317) * (0.4378 * vu10 - 0.3306) + \
            (-0.4371 * _pow(ladd, -1.822) + 1.192) * (0.05351 * vu10 - 0.01589) * \
            (_pow(base, c))

    if e.VBRDBG and rl.WRTVDBG:
        rl.WRTVDBG = False
        raise NoTraducido("VBRDBG (región %d)" % region)

    return vsz, vueff


def plume_conc(e, xd, yd, z, dwdt, heff, hshift, hbdeff, hbmax):
    """PLUME_CONC: penacho directo de un punto (gaussiano o de estela mezclada tras una barrera).
    XD, HEFF y HSHIFT son de entrada y salida (XD no tiene INTENT en el original y se modifica
    con MAX(XD, XD_MIN)). Devuelve (XD, HEFF, HSHIFT, CONC_PLUME)."""
    rl = e.RL
    direct_flag = False
    gaussian_flag = False
    rl.SZB = 0.0
    sy = 0.0
    sz = 0.0
    vert = 0.0
    horz = 0.0
    rl.ALPHA = 1.0
    rl.I_ALPHA = 1
    ia_max = 2
    sigmaz0_orig = rl.SIGMAZ0
    f_ueff = 1.0
    zieff = 0.0

    # penacho directo / solo meandro y modo gaussiano / estela mezclada
    if xd < 0.0001:
        direct_flag = False
    else:
        xd = max(xd, XD_MIN)
        direct_flag = True
        gaussian_flag = True
        if rl.HBD > 0.0 and xd > dwdt:
            gaussian_flag = False

    # HEFF, SZB, I_ALPHA, ALPHA (y F_UEFF con barrera a barlovento)
    if direct_flag:
        if rl.SHIFT_FLAG:
            heff = max(z, 0.75 * rl.HBU)
            rl.SZB = 0.0
            rl.I_ALPHA = 3
            rl.ALPHA = rl.ALPHA_U
            f_ueff = 1.0 - 1.0 * expx(e, _div(-1.0 * xd, 8.0 * rl.HBU))
        else:
            heff = z
            rl.SZB = 0.0
            rl.I_ALPHA = 1
            rl.ALPHA = 1.0
    else:
        if rl.NBARR > 0:
            rl.SZB = 0.25 * hbmax
            if rl.HBU > rl.HBD:
                ia_max = 3
            rl.I_ALPHA = ia_max
            rl.ALPHA = max(rl.ALPHA_D, rl.ALPHA_U)
        else:
            rl.I_ALPHA = 1
            rl.ALPHA = 1.0

    if direct_flag and gaussian_flag:
        hshift = 0.0
        if rl.VEGBARDW and xd > rl.VDWD:
            sz, rl.UEFF = veg_calc(e, xd)
        else:
            effective_wind(e, xd, z, hshift)
            sz = sigmaz(e, xd)
        sy = sigmay(e, xd)
        ueff_bu = f_ueff * rl.UEFF
        e.ZR = rl.ZRECEP
        zieff = max(e.ZI, heff + _F2_15 * sz)
        funciones_dispersion.vrtsbl(e, sz, heff, zieff)
        vert = _div(e.FSUBZ, ueff_bu)
        t = _div(yd, sy)
        horz = _div(1.0, e.SRT2PI * sy) * expx(e, -0.5 * (t * t))

    elif direct_flag and not gaussian_flag:
        # paso 1: dispersión entre la fuente y la barrera de sotavento
        hshift = rl.HBD
        effective_wind(e, dwdt, heff, hshift)
        rl.SZB = sigmaz(e, dwdt) + 0.1 * rl.HBD
        rl.SIGMAZ0 = 0.0
        # paso 2: dispersión más allá de la barrera
        rl.I_ALPHA = 2
        rl.ALPHA = rl.ALPHA_D
        effective_wind(e, xd - dwdt, heff, hshift)
        sz = sigmaz(e, xd - dwdt)
        sy = sigmay(e, xd - dwdt)
        rl.SIGMAZ0 = sigmaz0_orig

        t = _div(heff, sz)
        cq = (_div(1.0, e.SRT2PI * sz * rl.UEFF)) * 2.0 * expx(e, -0.5 * (t * t))
        hmax = max(rl.HBD, 12.0)
        a = (1.0 - (0.75 * rl.HBD) / hmax)
        f_uh = 1.0 - a * expx(e, _div(-(xd - dwdt), 9.0 * rl.HBD))
        fq = _div(1.0, 1.0 + f_uh * 0.5 * rl.UH * cq * hbdeff)
        if rl.ZRECEP > hbdeff:
            t1 = _div(rl.ZRECEP - hbdeff - heff, sz)
            t2 = _div(rl.ZRECEP - hbdeff + heff, sz)
            vert = fq * (_div(1.0, e.SRT2PI * sz * rl.UEFF)) * \
                (expx(e, -0.5 * (t1 * t1)) + expx(e, -0.5 * (t2 * t2)))
        else:
            vert = fq * cq
        t = _div(yd, sy)
        horz = _div(1.0, e.SRT2PI * sy) * expx(e, -0.5 * (t * t))

    else:
        # solo meandro
        hshift = 0.0
        vert = 0.0
        horz = 0.0

    conc_plume = vert * horz

    if e.RLINEDBG:
        raise NoTraducido("RLINEDBG")
    return xd, heff, hshift, conc_plume


def point_conc(e, x, y, z):
    """POINT_CONC (FUNCTION): concentración de un punto de la línea en el receptor: penacho
    directo y meandro, cada uno ponderado entre el estado horizontal (CWRAP) y el que sigue al
    terreno (CLIFT) con FOPT, y combinados con la fracción de meandro FRAN."""
    rl = e.RL
    conc_p = 0.0
    conc_m = 0.0
    fran = 0.0
    xmax = 0.0
    dwdt = 0.0
    heff = z
    hbdeff = 0.0
    hshift = 0.0
    hbmax = 0.0                # sin inicializar en el original: solo se usa con NBARR > 0
    vert = 0.0                 # VERT y HORZ: sin asignar en el original (solo depuración)
    horz = 0.0
    cwrap_p = 0.0
    cwrap_m = 0.0
    clift_p = 0.0
    clift_m = 0.0

    # distancias fuente-receptor (con el desplazamiento por la barrera de barlovento)
    xd = rl.XR_ROT - (x - rl.XSHIFT)
    yd = rl.YR_ROT - (y - rl.YSHIFT)

    if rl.NBARR > 0:
        hbmax = max(rl.HBU, rl.HBD)
        hbdeff = rl.HBD * 1.25
        xmax = max(abs(rl.XR_ROT - (rl.XSBEGIN - rl.XSHIFT)),
                   abs(rl.XR_ROT - (rl.XSEND - rl.XSHIFT)))
        if xmax < rl.DW_PERD:
            dwdt = rl.DWD
        if xmax >= rl.DW_PERD:
            dwdt = min(xmax, rl.DWD)

    # altura del receptor sobre la base de la fuente
    if e.L_FLATSRC[e.ISRC]:
        e.ZRT = e.ZFLAG
    else:
        e.ZRT = e.ZELEV - e.ZS + e.ZFLAG

    rl.I_ALPHA = 1

    # D234: UEFF sin calcular o nulo antes de llamar a SIGMAZ
    if rl.UEFF <= 0.0:
        effective_wind(e, xd, heff, hshift)

    # superficie reflectora efectiva
    if e.STABLE or (e.UNSTAB and (e.ZS >= e.ZI)):
        e.SZ = sigmaz(e, xd)
        e.HSBL = calculo_area.refl_ht(e, heff, abs(xd), 0.0, e.SZ)
    elif e.UNSTAB:
        e.HSBL = 0.0

    funciones_dispersion.critds(e, heff)
    funciones_dispersion.pfract(e, heff)
    funciones_dispersion.fterm(e)

    # penacho horizontal, CWRAP
    if e.FOPT == 0.0:
        cwrap_p = 0.0
        cwrap_m = 0.0
    else:
        rl.ZRECEP = e.ZRT
        xd, heff, hshift, cwrap_p = plume_conc(e, xd, yd, z, dwdt, heff, hshift, hbdeff, hbmax)
        cwrap_m = meander(e, x, y, z, hshift)

    # penacho que sigue al terreno, CLIFT
    if e.ZRT == e.ZFLAG:
        clift_p = cwrap_p
        clift_m = cwrap_m
    elif e.FOPT == 1.0:
        clift_p = 0.0
        clift_m = 0.0
    else:
        rl.ZRECEP = e.ZFLAG
        xd, heff, hshift, clift_p = plume_conc(e, xd, yd, z, dwdt, heff, hshift, hbdeff, hbmax)
        clift_m = meander(e, x, y, z, hshift)

    # nuevo FOPT si PLUME_CONC ha cambiado I_ALPHA o HEFF (barreras)
    if rl.I_ALPHA != 1 or heff != z:
        if e.STABLE or (e.UNSTAB and (e.ZS >= e.ZI)):
            e.SZ = sigmaz(e, xd)
            e.HSBL = calculo_area.refl_ht(e, heff, abs(xd), e.SZ, 0.0)
        elif e.UNSTAB:
            e.HSBL = 0.0
        funciones_dispersion.critds(e, heff)
        funciones_dispersion.pfract(e, heff)
        funciones_dispersion.fterm(e)

    fopt = e.FOPT
    conc_p = fopt * cwrap_p + ((1.0 - fopt) * clift_p)
    conc_m = fopt * cwrap_m + ((1.0 - fopt) * clift_m)

    fran = funciones_dispersion.meandr(e, rl.UEFF, rl.SIGMAV)

    point = conc_p * (1.0 - fran) + conc_m * fran

    if e.RLINEDBG:
        raise NoTraducido("RLINEDBG")

    rl.FRAN_SUM = rl.FRAN_SUM + fran
    rl.SIGMAV_SUM = rl.SIGMAV_SUM + rl.SIGMAV
    rl.UEFF_SUM = rl.UEFF_SUM + rl.UEFF
    rl.VERT_SUM = rl.VERT_SUM + vert
    rl.HORZ_SUM = rl.HORZ_SUM + horz
    rl.CONC_P_SUM = rl.CONC_P_SUM + conc_p
    rl.CONC_M_SUM = rl.CONC_M_SUM + conc_m
    rl.POINT_CONC_SUM = rl.POINT_CONC_SUM + point
    return point


# ======================================================================== integración
def polyinterp(xa, ya, x, n):
    """POLYINTERP: interpolación polinómica de Neville (Numerical Recipes) en X de la tabla
    (XA, YA) de N puntos (listas con índices 1..N). Devuelve (Y, ERR)."""
    deltay = 0.0
    ns = 1
    dif = abs(x - xa[1])
    c = [0.0] * (n + 1)
    d = [0.0] * (n + 1)
    for i in range(1, n + 1):
        dift = abs(x - xa[i])
        if dift < dif:
            ns = i
            dif = dift
        c[i] = ya[i]
        d[i] = ya[i]
    y = ya[ns]
    ns = ns - 1
    for m in range(1, n):
        for i in range(1, n - m + 1):
            ho = xa[i] - x
            hp = xa[i + m] - x
            w = c[i + 1] - d[i]
            den = ho - hp
            d[i] = _div(w * hp, den)
            c[i] = _div(w * ho, den)
        if 2 * ns < (n - m):
            deltay = c[ns + 1]
        else:
            deltay = d[ns]
            ns = ns - 1
        y = y + deltay
    err = abs(_div(deltay, y + _EPS))
    return y, err


def numerical_line_source(e):
    """NUMERICAL_LINE_SOURCE: integral de la línea en el receptor (trapecios sucesivos con
    extrapolación de Romberg). Devuelve (CONC_NUM, ERR)."""
    rl = e.RL
    conc_num = 0.0
    err = 2.0 * ERROR_LIMIT

    xsb, ysb, zsb = rl.XSBEGIN, rl.YSBEGIN, rl.ZSBEGIN
    xse, yse, zse = rl.XSEND, rl.YSEND, rl.ZSEND
    xr, yr = rl.XR_ROT, rl.YR_ROT

    xdif = xse - xsb
    ydif = yse - ysb
    zdif = zse - zsb

    tmax = math.sqrt(xdif * xdif + ydif * ydif + zdif * zdif)
    phi = math.asin(zdif / (tmax + SM_NUM))
    sinp = math.sin(phi)
    cosp = math.cos(phi)
    cost = math.cos(rl.THETA_LINE)
    sint = math.sin(rl.THETA_LINE)

    # punto de la línea directamente a barlovento del receptor
    xrec = (xse - _div((yse - yr) * (xse - xsb), (yse - ysb)))
    dr = abs(xr - xrec)

    # receptor sobre la fuente
    dr = max(XD_MIN, dr)
    rl.XPER = _div(dsign(_A, xr - xrec) * abs(-1.0 * ydif * (xr - xsb) + xdif * (yr - ysb)),
                   _sqrt(xdif * xdif + ydif * ydif))

    # mínimo de iteraciones
    if (yr > ysb - tmax / 2.0 * abs(cost)) and (yr < yse + tmax / 2.0 * abs(cost)):
        v = _div(_log(_div(2.0 * tmax, (max(XD_MIN, dr * abs(sint)))) - 2.0), math.log(2.0))
        minj = _i4(_ceiling_i4(v) + 2.0)
    else:
        minj = 0

    # receptor a barlovento de la línea
    if (xr < xsb) and (xr < xse):
        minj = 0

    it_lim = max(10, _i32(2 * minj))

    conc = [0.0] * (it_lim + 1)
    h = [0.0] * (it_lim + 1)

    tot_no_points = 0
    rl.FRAN_SUM = 0.0
    rl.SIGMAV_SUM = 0.0
    rl.UEFF_SUM = 0.0
    rl.VERT_SUM = 0.0
    rl.HORZ_SUM = 0.0
    rl.CONC_P_SUM = 0.0
    rl.CONC_M_SUM = 0.0
    rl.POINT_CONC_SUM = 0.0

    disp = (point_conc(e, xsb, ysb, zsb) + point_conc(e, xse, yse, zse)) * 0.5

    if e.RLINEDBG:
        raise NoTraducido("RLINEDBG")

    # primera aproximación
    conc[1] = disp * tmax
    h[1] = 1.0
    for j in range(2, it_lim + 1):
        no_points = _i32(1 << (j - 2))
        delt = _div(tmax, float(no_points))
        t = delt / 2.0
        disp = 0.0
        for _is in range(1, no_points + 1):
            x = t * cost * cosp + xsb
            y = t * sint * cosp + ysb
            z = t * sinp + zsb
            disp = disp + point_conc(e, x, y, z)
            t = t + delt
        conc[j] = (disp * delt + conc[j - 1]) / 2.0
        h[j] = 0.25 * h[j - 1]

        tot_no_points = tot_no_points + no_points

        # Romberg a partir de J >= K
        if j >= _K:
            st = j - _K + 1
            fi = st + _K - 1
            hdum = [0.0] + h[st:fi + 1]
            concdum = [0.0] + conc[st:fi + 1]
            conc_int, err = polyinterp(hdum, concdum, _XINTERP, _K)
            conc_num = abs(conc_int)
            if (abs(err) < ERROR_LIMIT) and (j > minj):
                if e.RLINEDBG:
                    raise NoTraducido("RLINEDBG")
                return conc_num, err

        conc_num = abs(conc[j])

        if e.RLINEDBG:
            raise NoTraducido("RLINEDBG")

    return conc_num, err


# ===================================================================== geometría y emisión
def rlemconv(e):
    """RLEMCONV: factores de conversión de las unidades de MOVES (g/h/tramo) a las de RLINE
    (g/m/s) de las fuentes RLINE desde ISRC (1 si no hay RLEMCONV)."""
    rl = e.RL
    rl.RLEMISCONV[:] = 1.0
    if rl.RLMOVESCONV:
        for index in range(e.ISRC, e.NUMSRC + 1):
            if e.SRCTYP[index] == "RLINE":
                dx = float(rl.S_XSB[index]) - float(rl.S_XSE[index])
                dy = float(rl.S_YSB[index]) - float(rl.S_YSE[index])
                length = math.sqrt(dx * dx + dy * dy)
                rl.RLEMISCONV[index] = _div(1.0, length) / 3600.0


def translate_rotate(e):
    """TRANSLATE_ROTATE: traslada el origen al comienzo de la fuente ISRC y gira las fuentes RLINE
    (desde ISRC) y los receptores para que el eje x siga al viento; aplica el desplazamiento DCL y
    el de la vía deprimida y marca las barreras situadas a sotavento (BDW_FLAG)."""
    rl = e.RL
    isrc = e.ISRC
    rl.BDW_FLAG[:, :] = 0

    angle = 270.0 - e.WDREF
    if angle > 180.0:
        angle = angle - 360.0
    rl.THETAW = angle * e.PI / 180.0
    ctw = math.cos(rl.THETAW)
    stw = math.sin(rl.THETAW)

    rl.X0 = float(rl.S_XSB[isrc])
    rl.Y0 = float(rl.S_YSB[isrc])
    x0, y0 = rl.X0, rl.Y0

    # DCLWALL_LOC: local sin inicializar en el original; conserva el valor entre fuentes
    dclwall_loc = [0.0, 0.0, 0.0]
    for index in range(isrc, e.NUMSRC + 1):
        if e.SRCTYP[index] == "RLINE" or e.SRCTYP[index] == "RLINEXT":
            dcl_loc = float(rl.S_DCL[index])
            if rl.S_HTWALL[index] > 0.0 or rl.S_HTWALL2[index] > 0.0:
                dclwall_loc[1] = float(rl.S_DCLWALL[index])
                dclwall_loc[2] = float(rl.S_DCLWALL2[index])
            elif e.VBARSET:
                if rl.VB_HT[1, index] > 0.0 or rl.VB_HT[2, index] > 0.0:
                    dclwall_loc[1] = float(rl.VB_DCL[1, index])
                    dclwall_loc[2] = float(rl.VB_DCL[2, index])

            xsb_tran = float(rl.S_XSB[index]) - x0
            ysb_tran = float(rl.S_YSB[index]) - y0
            xse_tran = float(rl.S_XSE[index]) - x0
            yse_tran = float(rl.S_YSE[index]) - y0
            rl.THETA_LINE = math.atan2(yse_tran - ysb_tran, xse_tran - xsb_tran)

            # líneas Oeste-Este
            if math.sin(rl.THETA_LINE) == 0.0:
                dcl_loc = -1.0 * dcl_loc
                dclwall_loc[1] = -1.0 * dclwall_loc[1]
                dclwall_loc[2] = -1.0 * dclwall_loc[2]

            # línea dada por el eje y la distancia al eje (sin depresión)
            depth = float(rl.S_DEPTH[index])
            if dcl_loc != 0.0 and depth == 0.0:
                s = math.sin(rl.THETA_LINE)
                c = math.cos(rl.THETA_LINE)
                sg = dsign(1.0, s)
                xse_tran = xse_tran + dcl_loc * s * sg
                yse_tran = yse_tran - dcl_loc * c * sg
                xsb_tran = xsb_tran + dcl_loc * s * sg
                ysb_tran = ysb_tran - dcl_loc * c * sg

            # vía deprimida
            if depth < 0.0:
                s = math.sin(rl.THETA_LINE)
                c = math.cos(rl.THETA_LINE)
                xse_tran = xse_tran - depressed_displacement(e, rl.THETA_LINE, index) * s
                yse_tran = yse_tran + depressed_displacement(e, rl.THETA_LINE, index) * c
                xsb_tran = xsb_tran - depressed_displacement(e, rl.THETA_LINE, index) * s
                ysb_tran = ysb_tran + depressed_displacement(e, rl.THETA_LINE, index) * c

            rl.XSB_ROT[index] = xsb_tran * ctw + ysb_tran * stw
            rl.YSB_ROT[index] = -1.0 * xsb_tran * stw + ysb_tran * ctw
            rl.XSE_ROT[index] = xse_tran * ctw + yse_tran * stw
            rl.YSE_ROT[index] = -1.0 * xse_tran * stw + yse_tran * ctw

            # comienzo de cada barrera y si queda a sotavento de la vía
            if rl.THETA_LINE == rl.THETAW:
                rl.THETA_LINE = rl.THETA_LINE + 0.001
            s = math.sin(rl.THETA_LINE)
            c = math.cos(rl.THETA_LINE)
            sg = dsign(1.0, s)
            xsb_rot = float(rl.XSB_ROT[index])
            for i in (1, 2):
                xbb = xsb_tran + (dclwall_loc[i] - dcl_loc) * s * sg
                ybb = ysb_tran - (dclwall_loc[i] - dcl_loc) * c * sg
                xbb_rot = xbb * ctw + ybb * stw
                if xbb_rot > xsb_rot:
                    rl.BDW_FLAG[index, i] = 1

    for index in range(1, e.NUMREC + 1):
        xr_tran = float(e.AXR[index]) - x0
        yr_tran = float(e.AYR[index]) - y0
        rl.XRCP_ROT[index] = xr_tran * ctw + yr_tran * stw
        rl.YRCP_ROT[index] = -1.0 * xr_tran * stw + yr_tran * ctw


# ======================================================================= entrada (vía SO)
def _orden_grupo(e, m):
    if not e.PSDCREDIT and e.ISSTAT[24] != 0:
        e.errhdl(e.PATH, m, "E", "140", "SRCGROUP")
    elif e.PSDCREDIT and e.ISSTAT[34] != 0:
        e.errhdl(e.PATH, m, "E", "140", "PSDGROUP")


def socard(e, k):
    """Ramas de SOCARD de RLEMCONV, RBARRIER, SBARRIER, VBARRIER y RDEPRESS. Devuelve False si la
    clave no es de las suyas."""
    m = "SOCARD"
    rl = e.RL
    if k == "RLEMCONV":
        e.ISSTAT[12] += 1
        _orden_grupo(e, m)
        if e.ISSTAT[12] != 1:
            e.errhdl(e.PATH, m, "E", "135", e.KEYWRD)
        elif e.IFC > 2:
            e.errhdl(e.PATH, m, "E", "202", e.KEYWRD)
        else:
            rl.RLMOVESCONV = True
    elif k == "RBARRIER":
        if e.L_ALPHA and e.FLAT:
            rl.L_RBARRIER = True
            rlinebar_inputs(e)
        else:
            if not e.FLAT:
                e.errhdl(e.PATH, m, "E", "713", "")
            if not e.L_ALPHA:
                e.errhdl(e.PATH, m, "E", "198", " RBARRIER ")
    elif k == "SBARRIER":
        if e.L_ALPHA and e.FLAT:
            e.SBARDCL = True
            sbarrier_inputs(e)
        else:
            if not e.FLAT:
                e.errhdl(e.PATH, m, "E", "713", "")
            if not e.L_ALPHA:
                e.errhdl(e.PATH, m, "E", "198", " RBARRIER ")
    elif k == "VBARRIER":
        if e.L_ALPHA and e.FLAT:
            vbarrier_inputs(e)
            e.VBARSET = True
        else:
            if not e.FLAT:
                e.errhdl(e.PATH, m, "E", "713", "")
            if not e.L_ALPHA:
                e.errhdl(e.PATH, m, "E", "198", " RBARRIER ")
    elif k == "RDEPRESS":
        if e.L_ALPHA and e.FLAT:
            rl.L_RDEPRESS = True
            rlinedpr_inputs(e)
        else:
            if not e.FLAT:
                e.errhdl(e.PATH, m, "E", "713", "")
            if not e.L_ALPHA:
                e.errhdl(e.PATH, m, "E", "198", " RDEPRESS ")
    else:
        return False
    return True


def soloca_rline(e, m, isrc):
    """Rama de SOLOCA de RLINE (campos 5-8: XSB, YSB, XSE, YSE) y RLINEXT (campos 5-10: XSB, YSB,
    ZSB, XSE, YSE, ZSE). La cota de la base (campo 9 u 11) se lee aparte, como en el resto de
    fuentes lineales."""
    rl = e.RL
    if e.SRCTYP[isrc] == "RLINE":
        campos = ((5, rl.S_XSB), (6, rl.S_YSB), (7, rl.S_XSE), (8, rl.S_YSE))
    else:
        campos = ((5, rl.S_XSB), (6, rl.S_YSB), (7, rl.S_ZSB), (8, rl.S_XSE), (9, rl.S_YSE),
                  (10, rl.S_ZSE))
    for k, a in campos:
        v, imit = dbl(e, k, a[isrc])
        e.IMIT = imit
        a[isrc] = v
        if imit != 1:
            e.errhdl(e.PATH, m, "E", "208", e.KEYWRD)


def rlparm(e, isdx, temp):
    """RLPARM: parámetros de SRCPARAM de las fuentes RLINE (Lnemis, HS, WIDTH[, SZINIT]) y
    RLINEXT (QEMIS, DCL, WIDTH, SZINIT). TEMP con índices 1.. (TEMP(1) = FIELD(4))."""
    m = "RLPARM"
    rl = e.RL
    t = e.SRCTYP[isdx]
    if t == "RLINE":
        rl.S_QEMIS[isdx] = temp[1] * temp[3]
        rl.S_DCL[isdx] = 0.0
        rl.S_ZSB[isdx] = temp[2]
        rl.S_ZSE[isdx] = temp[2]
        if e.IFC == 7:
            rl.S_INIT_SIGMAZ[isdx] = temp[4]
        else:
            rl.S_INIT_SIGMAZ[isdx] = 0.0
        rl.S_WIDTH[isdx] = temp[3]
        rl.S_HTWALL[isdx] = 0.0
        rl.S_DCLWALL[isdx] = 0.0
        rl.S_HTWALL2[isdx] = 0.0
        rl.S_DCLWALL2[isdx] = 0.0
        rl.S_DEPTH[isdx] = 0.0
        rl.S_WTOP[isdx] = 0.0
        rl.S_WBOTTOM[isdx] = 0.0

    if t == "RLINEXT":
        rl.S_QEMIS[isdx] = temp[1]
        rl.S_DCL[isdx] = temp[2]
        rl.S_WIDTH[isdx] = temp[3]
        rl.S_INIT_SIGMAZ[isdx] = temp[4]
        rl.S_HTWALL[isdx] = 0.0
        rl.S_DCLWALL[isdx] = 0.0
        rl.S_HTWALL2[isdx] = 0.0
        rl.S_DCLWALL2[isdx] = 0.0
        rl.S_DEPTH[isdx] = 0.0
        rl.S_WTOP[isdx] = 0.0
        rl.S_WBOTTOM[isdx] = 0.0

    if rl.S_QEMIS[isdx] < 0.0:
        e.errhdl(e.PATH, m, "E", "209", " QS ")
    elif rl.S_QEMIS[isdx] == 0.0:
        e.errhdl(e.PATH, m, "W", "320", " QS ")

    if rl.S_INIT_SIGMAZ[isdx] < 0.0:
        e.errhdl(e.PATH, m, "E", "209", " INIT_SIGMAZ ")
    elif rl.S_INIT_SIGMAZ[isdx] > 42.0:
        e.errhdl(e.PATH, m, "E", "320", " INIT_SIGMAZ ")

    if rl.S_WIDTH[isdx] < 0.0:
        e.errhdl(e.PATH, m, "E", "209", " WIDTH ")
    elif rl.S_WIDTH[isdx] == 0.0:
        e.errhdl(e.PATH, m, "W", "320", " WIDTH ")
    elif rl.S_WIDTH[isdx] > 30.0:
        e.errhdl(e.PATH, m, "W", "320", " WIDTH ")


def _leer_campo(e, m, k, a, idx):
    """CALL STODBL(FIELD(k), ILEN_FLD, A(idx), IMIT) con el mensaje 208 si no es numérico (A es
    una matriz numpy y IDX un índice o una tupla de índices)."""
    v, imit = dbl(e, k, a[idx])
    e.IMIT = imit
    a[idx] = v
    if imit != 1:
        e.errhdl(e.PATH, m, "E", "208", e.KEYWRD)


def rlinebar_inputs(e):
    """RLINEBAR_INPUTS: barreras sólidas de una fuente RLINEXT (RBARRIER): altura y distancia al
    eje de una o dos barreras."""
    m = "RLBAR_INP"
    rl = e.RL
    if e.IFC <= 2:
        e.errhdl(e.PATH, m, "E", "200", e.KEYWRD)
        return
    elif e.IFC < 5:
        e.errhdl(e.PATH, m, "E", "201", e.KEYWRD)
        return
    elif e.IFC == 6:
        e.errhdl(e.PATH, m, "E", "203", e.KEYWRD)
        return
    elif e.IFC > 7:
        e.errhdl(e.PATH, m, "E", "202", e.KEYWRD)
        return

    soid = fc(e.FIELD[3], 12)
    indexs, found = sindex(e.SRCID, e.NSRC, soid)
    if found:
        if e.SRCTYP[indexs] == "RLINEXT":
            _leer_campo(e, m, 4, rl.S_HTWALL, indexs)
            _leer_campo(e, m, 5, rl.S_DCLWALL, indexs)
            if e.IFC == 7:
                _leer_campo(e, m, 6, rl.S_HTWALL2, indexs)
                _leer_campo(e, m, 7, rl.S_DCLWALL2, indexs)
        else:
            e.errhdl(e.PATH, m, "E", "278", e.KEYWRD)
    else:
        e.errhdl(e.PATH, m, "E", "300", e.KEYWRD)

    # sin encontrar, INDEXS = 0: el original lee RLSOURCE(0) (fuera de límites); aquí la
    # posición 0 sin usar (ceros)
    if rl.S_HTWALL is None:
        raise NoTraducido("RBARRIER sin RLSOURCE reservada (sin fuentes RLINE: acceso a una "
                          "matriz no reservada en el original)")
    if rl.S_HTWALL[indexs] < 0.0 or rl.S_HTWALL2[indexs] < 0.0:
        e.errhdl(e.PATH, m, "E", "209", " HTWALL ")


def vbarrier_inputs(e):
    """VBARRIER_INPUTS: barreras vegetales de una fuente RLINEXT (VBARRIER): altura, ancho,
    distancia al eje, LAI y densidad foliar máxima de una o dos barreras."""
    m = "VBAR_INP"
    rl = e.RL
    if e.IFC < 8:
        e.errhdl(e.PATH, m, "E", "201", e.KEYWRD)
        return
    elif e.IFC > 13:
        e.errhdl(e.PATH, m, "E", "202", e.KEYWRD)
        return
    elif e.IFC > 8 and e.IFC < 13:
        e.errhdl(e.PATH, m, "E", "201", e.KEYWRD)
        return

    soid = fc(e.FIELD[3], 12)
    indexs, found = sindex(e.SRCID, e.NSRC, soid)
    if found:
        if e.SRCTYP[indexs] == "RLINEXT":
            for k, base in ((1, 4), (2, 9)):
                if k == 2 and e.IFC != 13:
                    break
                _leer_campo(e, m, base, rl.VB_HT, (k, indexs))
                if rl.VB_HT[k, indexs] < 2.0 or rl.VB_HT[k, indexs] > 10.0:
                    e.errhdl(e.PATH, m, "E", "371", e.KEYWRD)
                _leer_campo(e, m, base + 1, rl.VB_WT, (k, indexs))
                if rl.VB_WT[k, indexs] < 2.5 or rl.VB_WT[k, indexs] > 13.0:
                    e.errhdl(e.PATH, m, "E", "372", e.KEYWRD)
                _leer_campo(e, m, base + 2, rl.VB_DCL, (k, indexs))
                _leer_campo(e, m, base + 3, rl.VB_LAI, (k, indexs))
                if rl.VB_LAI[k, indexs] < 4.0 or rl.VB_LAI[k, indexs] > 10.92:
                    e.errhdl(e.PATH, m, "E", "373", e.KEYWRD)
                _leer_campo(e, m, base + 4, rl.VB_LM, (k, indexs))
                if rl.VB_LM[k, indexs] < 0.55 or rl.VB_LM[k, indexs] > 3.75:
                    e.errhdl(e.PATH, m, "E", "374", e.KEYWRD)
        else:
            e.errhdl(e.PATH, m, "E", "278", e.KEYWRD)
    else:
        e.errhdl(e.PATH, m, "E", "300", e.KEYWRD)

    # sentido de las distancias al eje (INDEXS = 0 si no se encontró: ver RLINEBAR_INPUTS)
    if rl.VB_HT is None:
        raise NoTraducido("VBARRIER sin VEGBARR reservada (sin fuentes RLINE: acceso a una "
                          "matriz no reservada en el original)")
    d1 = rl.VB_DCL[1, indexs]
    d2 = rl.VB_DCL[2, indexs]
    if (d1 < 0.0 and d2 < 0.0) or (d1 > 0.0 and d2 > 0.0):
        # se anula la barrera más lejana
        if abs(d1) < abs(d2):
            e.errhdl(e.PATH, m, "W", "375", "VBARRIER 1")
            k = 2
        elif abs(d2) < abs(d1):
            e.errhdl(e.PATH, m, "W", "375", "VBARRIER 2")
            k = 1
        else:
            k = 0
        if k:
            rl.VB_HT[k, indexs] = 0.0
            rl.VB_WT[k, indexs] = 0.0
            rl.VB_DCL[k, indexs] = 0.0
            rl.VB_LAI[k, indexs] = 0.0
            rl.VB_LM[k, indexs] = 0.0


def vbarrier_setup(e):
    """VBARRIER_SETUP: estela de las barreras vegetales (se anulan si la fuente tiene barreras
    sólidas)."""
    m = "VBAR_SETUP"
    rl = e.RL
    for is_ in range(1, e.NSRC + 1):
        if e.SRCTYP[is_] == "RLINEXT":
            if rl.S_HTWALL[is_] > 0.0 or rl.S_HTWALL2[is_] > 0.0:
                e.errhdl(e.PATH, m, "W", "376", e.SRCID[is_])
                rl.VB_HT[1, is_] = 0.0
                rl.VB_HT[2, is_] = 0.0
            else:
                for k in (1, 2):
                    if rl.VB_HT[k, is_] > 0.0:
                        rl.VB_WAKE[k, is_] = float(rl.VB_HT[k, is_]) * \
                            (3.03 * (_pow(float(rl.VB_WT[k, is_]), -2.086)) + 0.1042) * \
                            (39.0053 * (_pow(float(rl.VB_LM[k, is_]), -0.7284)))


def sbarrier_inputs(e):
    """SBARRIER_INPUTS: barreras sólidas por segmentos (SBARRIER): registro STA (identificador y
    número de segmentos), registros de segmento (extremos, altura y cota) y registro END."""
    m = "SBAR_INP"
    rl = e.RL
    if e.IFC <= 3:
        e.errhdl(e.PATH, m, "E", "201", e.KEYWRD)
        return
    elif e.IFC > 9:
        e.errhdl(e.PATH, m, "E", "202", e.KEYWRD)
        return

    inbar = fc(e.FIELD[4], 12)
    if inbar == "STA":
        e.IBARID = e.IBARID + 1
        ib = e.IBARID
        if ib < 1 or ib > e.NSBR:
            raise NoTraducido("SBARRIER: barrera %d fuera de SLDBARR (escritura fuera de límites "
                              "en el original)" % ib)
        rl.SB_BARID[ib] = fc(e.FIELD[3], 12)
        # DPNUMSEG: local sin inicializar en el original (aquí 0 si el campo no es numérico)
        dpnumseg, imit = dbl(e, 5, 0.0)
        e.IMIT = imit
        rl.SB_NUMSEG[ib] = _i4(dpnumseg)
        if imit != 1:
            e.errhdl(e.PATH, m, "E", "208", e.KEYWRD)
        if rl.SB_NUMSEG[ib] < 1 or rl.SB_NUMSEG[ib] > 50:
            e.errhdl(e.PATH, m, "E", "320", rl.SB_BARID[ib])
        e.INUMSEG = 1

    elif inbar == "END":
        ib = e.IBARID
        if ib < 1 or ib > e.NSBR:
            raise NoTraducido("SBARRIER END sin STA (lectura fuera de límites en el original)")
        if rl.SB_NUMSEG[ib] != e.INUMSEG - 1:
            e.errhdl(e.PATH, m, "E", "306", rl.SB_BARID[ib])
        return

    else:
        ib = e.IBARID
        j = e.INUMSEG
        if ib < 1 or ib > e.NSBR or j < 1 or j > MAXSBSEG:
            raise NoTraducido("SBARRIER: segmento %d de la barrera %d fuera de SLDBARR (escritura "
                              "fuera de límites en el original)" % (j, ib))
        _leer_campo(e, m, 4, rl.SB_XBB, (j, ib))
        _leer_campo(e, m, 5, rl.SB_YBB, (j, ib))
        _leer_campo(e, m, 6, rl.SB_XBE, (j, ib))
        _leer_campo(e, m, 7, rl.SB_YBE, (j, ib))

        # extremos de Oeste a Este (o de Norte a Sur)
        if rl.SB_XBB[j, ib] > rl.SB_XBE[j, ib]:
            xtemp = rl.SB_XBB[j, ib]
            ytemp = rl.SB_YBB[j, ib]
            rl.SB_XBB[j, ib] = rl.SB_XBE[j, ib]
            rl.SB_XBE[j, ib] = xtemp
            rl.SB_YBB[j, ib] = rl.SB_YBE[j, ib]
            rl.SB_YBE[j, ib] = ytemp
        elif (rl.SB_XBB[j, ib] == rl.SB_XBE[j, ib]) and (rl.SB_YBB[j, ib] < rl.SB_YBE[j, ib]):
            xtemp = rl.SB_XBB[j, ib]
            ytemp = rl.SB_YBB[j, ib]
            rl.SB_XBB[j, ib] = rl.SB_XBE[j, ib]
            rl.SB_XBE[j, ib] = xtemp
            rl.SB_YBB[j, ib] = rl.SB_YBE[j, ib]
            rl.SB_YBE[j, ib] = ytemp

        _leer_campo(e, m, 8, rl.SB_HT, (j, ib))
        if rl.SB_HT[j, ib] <= 2.0 or rl.SB_HT[j, ib] > 12.0:
            e.errhdl(e.PATH, m, "E", "320", rl.SB_BARID[ib])
        _leer_campo(e, m, 9, rl.SB_Z, (j, ib))
        if rl.SB_Z[j, ib] > 0.0 or rl.SB_Z[j, ib] < 0.0:
            e.errhdl(e.PATH, m, "W", "326", e.KEYWRD)
        e.INUMSEG = e.INUMSEG + 1


def weight_sum(nseg, weights, var):
    """WEIGHT_SUM (FUNCTION): media ponderada de los NSEG segmentos (listas con índices 1..)."""
    wnorm = 0.0
    wsum = 0.0
    for i in range(1, nseg + 1):
        wsum = wsum + (weights[i] * var[i])
        wnorm = wnorm + weights[i]
    wsum = _div(wsum, wnorm)
    return wsum


def sbarrier_dcl(e):
    """SBARRIER_DCL: altura y distancia al eje (con signo) efectivas de cada barrera SBARRIER para
    cada fuente RLINEXT (giro de los segmentos no paralelos, solape con la fuente, huecos) y
    asignación a HTWALL/DCLWALL y HTWALL2/DCLWALL2 de las más cercanas a cada lado."""
    m = "SBAR_DCL"
    rl = e.RL
    rtodeg = e.RTODEG
    leftext = False
    rightext = False
    dclpos = True
    gap = False
    par = False
    fsbovrlp = 0.0
    infl = True
    glength = 0.0              # sin inicializar en el original (ver el control de huecos)
    blength = 0.0

    if e.BARDBG and e.NSBR * e.NRLINES >= 50:
        e.errhdl(e.PATH, m, "W", "312", "SBAR DEBUG")
    if e.BARDBG:
        raise NoTraducido("BARDBG")

    for is_ in range(1, e.NSRC + 1):
        if e.SRCTYP[is_] != "RLINEXT":
            continue
        sxb0, sxe0 = float(rl.S_XSB[is_]), float(rl.S_XSE[is_])
        syb0, sye0 = float(rl.S_YSB[is_]), float(rl.S_YSE[is_])
        # extremos de Oeste a Este (o de Norte a Sur), solo localmente
        if sxb0 > sxe0:
            xsb, xse, ysb, yse = sxe0, sxb0, sye0, syb0
        elif (sxb0 == sxe0) and (syb0 < sye0):
            xsb, xse, ysb, yse = sxe0, sxb0, sye0, syb0
        else:
            xsb, xse, ysb, yse = sxb0, sxe0, syb0, sye0

        slength = math.sqrt((xsb - xse) * (xsb - xse) + (ysb - yse) * (ysb - yse))
        if slength <= 0.0:
            e.errhdl(e.PATH, m, "E", "309", e.SRCID[is_])
        sang = _modulo(math.atan2((yse - ysb), (xse - xsb)) * rtodeg, 360.0)

        rl.S_BARID[is_] = "NOBARID"
        rl.S_BARID2[is_] = "NOBARID"

        for ib in range(1, e.NSBR + 1):
            nseg = int(rl.SB_NUMSEG[ib])
            if nseg > MAXSBSEG:
                raise NoTraducido("SBARRIER_DCL: NUMSEG > %d (lectura fuera de límites en el "
                                  "original)" % MAXSBSEG)
            nn = max(nseg, 0) + 1
            bsdcl = [0.0] * nn
            bsovrlap = [0.0] * nn
            bsrlht = [0.0] * nn
            sovrlp = [0.0] * nn
            xbb = rl.SB_XBB[:, ib]
            ybb = rl.SB_YBB[:, ib]
            xbe = rl.SB_XBE[:, ib]
            ybe = rl.SB_YBE[:, ib]

            for ibs in range(1, nseg + 1):
                bsrlht[ibs] = float(rl.SB_HT[ibs, ib])

                # huecos entre segmentos
                if ibs > 1 and not (xbe[ibs - 1] == xbb[ibs] and ybe[ibs - 1] == ybb[ibs]):
                    ang_ant = math.atan2((float(ybb[ibs - 1]) - float(ybe[ibs - 1])),
                                         (float(xbb[ibs - 1]) - float(xbe[ibs - 1]))) * rtodeg
                    stheta = _modulo((math.atan2((float(ybe[ibs - 1]) - float(ybb[ibs])),
                                                 (float(xbe[ibs - 1]) - float(xbb[ibs]))) * rtodeg)
                                     - ang_ant, 360.0)
                    dx = float(xbb[ibs]) - float(xbe[ibs - 1])
                    dy = float(ybb[ibs]) - float(ybe[ibs - 1])
                    sslgth = math.sqrt(dx * dx + dy * dy)

                    if stheta <= 90.0 or stheta >= 270.0:
                        glength = sslgth
                    elif stheta > 90.0 and stheta < 270.0:
                        thetai = _modulo(math.atan2((float(ybb[ibs]) - float(ybe[ibs])),
                                                    (float(xbb[ibs]) - float(xbe[ibs]))) * rtodeg,
                                         180.0)
                        thetadif = _modulo(thetai - ang_ant, 180.0)
                        if thetadif > 90.0:
                            ali = _modulo(stheta - 90.0, 180.0)
                            schi = _modulo(stheta - thetai, 180.0)
                            bei = _modulo(180 - ali - schi, 180.0)
                            glength = sslgth * (_div(_sind(schi), _sind(bei)))
                            sovrlp[ibs] = _div(glength * _tand(ali), blength)
                        else:
                            ali = 180.0 - stheta
                            glength = sslgth * _sind(ali)
                            sovrlp[ibs] = _div(sslgth * _cosd(ali), blength)
                    else:
                        pass       # error en el orden de los extremos: GLENGTH sin cambiar

                    if not gap and abs(glength) > 1.0:
                        gap = True

                # paralelismo con la fuente (a menos de 3 grados)
                xb, yb = float(xbb[ibs]), float(ybb[ibs])
                xe, ye = float(xbe[ibs]), float(ybe[ibs])
                bsang = _modulo(math.atan2((ye - yb), (xe - xb)) * rtodeg, 360.0)
                partheta = _modulo(sang - bsang, 180.0)
                if partheta == 90.0:
                    par = True
                    sxbb, sxbe, sybb, sybe = xb, xe, yb, ye
                elif partheta > 3.0:
                    par = True
                    # giro hasta ser paralelo a la fuente alrededor del punto medio
                    xmp = (xb + xe) / 2
                    ymp = (yb + ye) / 2
                    ang = _modulo(abs(sang - bsang), 180.0)
                    rxbe = ((xe - xmp) * _cosd(ang) + (ye - ymp) * _sind(ang)) + xmp
                    rybe = ((ye - ymp) * _cosd(ang) - (xe - xmp) * _sind(ang)) + ymp
                    slope = _div(rybe - ymp, rxbe - xmp)
                    b = ymp - (slope * xmp)
                    bsdist = ((math.sqrt((xb - xe) * (xb - xe) + (yb - ye) * (yb - ye))) / 2) * \
                        _cosd(_modulo(abs(bsang - sang), 90.0))
                    q = _sqrt(bsdist * bsdist / (1 + slope * slope))
                    sxbb = xmp - q
                    sxbe = xmp + q
                    sybb = (slope * sxbb) + b
                    sybe = (slope * sxbe) + b
                else:
                    sxbb, sxbe, sybb, sybe = xb, xe, yb, ye

                blength = math.sqrt((sxbb - sxbe) * (sxbb - sxbe) + (sybb - sybe) * (sybb - sybe))

                # triángulos con los extremos de la fuente
                sba = _sqrt((sxbb - xsb) * (sxbb - xsb) + (sybb - ysb) * (sybb - ysb))
                sbb = _sqrt((sxbe - xsb) * (sxbe - xsb) + (sybe - ysb) * (sybe - ysb))
                sea = _sqrt((sxbb - xse) * (sxbb - xse) + (sybb - yse) * (sybb - yse))
                seb = _sqrt((sxbe - xse) * (sxbe - xse) + (sybe - yse) * (sybe - yse))

                sbal = _acos(_div(sbb * sbb + blength * blength - sba * sba, 2.0 * sbb * blength))
                sbbe = _acos(_div(sba * sba + blength * blength - sbb * sbb, 2.0 * sba * blength))
                sbch = _acos(_div(sba * sba + sbb * sbb - blength * blength, 2.0 * sba * sbb))
                seal = _acos(_div(seb * seb + blength * blength - sea * sea, 2.0 * seb * blength))
                sebe = _acos(_div(sea * sea + blength * blength - seb * seb, 2.0 * sea * blength))
                sech = _acos(_div(sea * sea + seb * seb - blength * blength, 2.0 * sea * seb))

                dclsb = sbb * (math.sin(sbal))
                dclse = seb * (math.sin(seal))

                # solape y DCL ponderada
                if (sbal * rtodeg > 90 and seal * rtodeg > 90) or \
                        (sbbe * rtodeg > 90 and sebe * rtodeg > 90) or \
                        (sbch * rtodeg > 90 and sech * rtodeg > 90):
                    pass       # sin solape
                elif sbal * rtodeg <= 90 and seal * rtodeg <= 90 and \
                        sbbe * rtodeg <= 90 and sebe * rtodeg <= 90:
                    bsovrlap[ibs] = _div(blength, slength)
                    bsdcl[ibs] = (dclsb + dclse) / 2
                else:
                    if sbbe * rtodeg > 90 and sebe * rtodeg <= 90:
                        leftext = True
                    if sbal * rtodeg < 90 and seal * rtodeg > 90:
                        rightext = True
                    if leftext and rightext:
                        bsovrlap[ibs] = _div(blength, slength)
                        bsdcl[ibs] = (dclsb + dclse) / 2
                    elif leftext:
                        bsovrlap[ibs] = abs(_div(sea * math.cos(sebe), slength))
                        bsdcl[ibs] = ((1 - bsovrlap[ibs]) * dclsb) + (bsovrlap[ibs] * dclse)
                    elif rightext:
                        bsovrlap[ibs] = abs(_div(sbb * math.cos(sbal), slength))
                        bsdcl[ibs] = (bsovrlap[ibs] * dclsb) + ((1 - bsovrlap[ibs]) * dclse)

                # signo de la DCL: dirección del punto medio de la fuente al del segmento
                mpang = _modulo(math.atan2(((yb + ye) / 2 - (ysb + yse) / 2),
                                           ((xb + xe) / 2 - (xsb + xse) / 2)) * rtodeg, 360.0)
                if sang == 0 or sang == 180:
                    if mpang > 180:
                        dclpos = False
                else:
                    if mpang > 90 and mpang <= 270:
                        dclpos = False
                if not dclpos:
                    bsdcl[ibs] = -bsdcl[ibs]
                    dclpos = True

                leftext = False
                rightext = False

            if gap:
                e.errhdl(e.PATH, m, "W", "304", rl.SB_BARID[ib])
                gap = False
            if par:
                e.errhdl(e.PATH, m, "W", "307", rl.SB_BARID[ib])
                par = False

            # una altura y una DCL por barrera
            dcl = weight_sum(nseg, bsovrlap, bsdcl)
            ht = weight_sum(nseg, bsovrlap, bsrlht)

            # solape descontando el solape entre segmentos
            for i in range(1, nseg + 1):
                fsbovrlp = fsbovrlp + abs(bsovrlap[i] * (1 - sovrlp[i]))

            if fsbovrlp < 0.9:
                e.errhdl("SO", "SBAR_DCL", "W", "308", rl.SB_BARID[ib])
                infl = False

            if dcl > 10.0 * ht:
                e.errhdl(e.PATH, m, "W", "311", rl.SB_BARID[ib])
                infl = False

            if not infl:
                dcl = 0.0
                ht = 0.0
                infl = True

            # la barrera más cercana a cada lado de la fuente
            if dcl == 0.0 or ht == 0.0:
                pass
            else:
                if rl.S_DCLWALL[is_] == 0.0:
                    rl.S_DCLWALL[is_] = dcl
                    rl.S_HTWALL[is_] = ht
                    rl.S_BARID[is_] = rl.SB_BARID[ib]
                elif (rl.S_DCLWALL[is_] < 0.0 and dcl < 0.0) or \
                        (rl.S_DCLWALL[is_] > 0.0 and dcl > 0.0):
                    if abs(dcl) < abs(rl.S_DCLWALL[is_]):
                        rl.S_DCLWALL[is_] = dcl
                        rl.S_HTWALL[is_] = ht
                        rl.S_BARID[is_] = rl.SB_BARID[ib]
                else:
                    if rl.S_DCLWALL2[is_] == 0.0 or (abs(dcl) < abs(rl.S_DCLWALL2[is_])):
                        rl.S_DCLWALL2[is_] = dcl
                        rl.S_HTWALL2[is_] = ht
                        rl.S_BARID2[is_] = rl.SB_BARID[ib]

            fsbovrlp = 0.0


def rlinedpr_inputs(e):
    """RLINEDPR_INPUTS: vía deprimida de una fuente RLINEXT (RDEPRESS): profundidad y anchos
    superior e inferior."""
    m = "RLDPR_INP"
    rl = e.RL
    if e.IFC <= 2:
        e.errhdl(e.PATH, m, "E", "200", e.KEYWRD)
        return
    elif e.IFC < 6:
        e.errhdl(e.PATH, m, "E", "201", e.KEYWRD)
        return
    elif e.IFC > 6:
        e.errhdl(e.PATH, m, "E", "202", e.KEYWRD)
        return

    soid = fc(e.FIELD[3], 12)
    indexs, found = sindex(e.SRCID, e.NSRC, soid)
    if found:
        if e.SRCTYP[indexs] == "RLINEXT":
            _leer_campo(e, m, 4, rl.S_DEPTH, indexs)
            _leer_campo(e, m, 5, rl.S_WTOP, indexs)
            _leer_campo(e, m, 6, rl.S_WBOTTOM, indexs)
        else:
            e.errhdl(e.PATH, m, "E", "278", e.KEYWRD)
    else:
        e.errhdl(e.PATH, m, "E", "300", e.KEYWRD)

    # INDEXS = 0 si no se encontró (ver RLINEBAR_INPUTS)
    if rl.S_DEPTH is None:
        raise NoTraducido("RDEPRESS sin RLSOURCE reservada (sin fuentes RLINE: acceso a una "
                          "matriz no reservada en el original)")
    if rl.S_DEPTH[indexs] > 0.0:
        e.errhdl(e.PATH, m, "E", "320", " DEPTH ")
    if rl.S_WTOP[indexs] < 0.0:
        e.errhdl(e.PATH, m, "E", "320", " WTOP ")
    if rl.S_WBOTTOM[indexs] < 0.0 or rl.S_WBOTTOM[indexs] > rl.S_WTOP[indexs]:
        e.errhdl(e.PATH, m, "E", "320", " WBOTTOM ")


# ========================================================= zonas de borde (reset.f, BAREDGE)
def barzone(e, bxs, bys, bht, rezone):
    """BARZONE (FUNCTION): gira la barrera (extremos BXS, BYS con índices 1..2) al eje x y marca
    los receptores dentro de su zona de influencia. Devuelve la nueva matriz de zonas."""
    zona = rezone.copy()
    bangle = abs(math.atan2((bys[2] - bys[1]), (bxs[2] - bxs[1])))
    c = math.cos(bangle)
    s = math.sin(bangle)
    bxr1 = bxs[1] * c + bys[1] * s
    bxr2 = bxs[2] * c + bys[2] * s
    byr = -bxs[1] * s + bys[1] * c
    for ir in range(1, e.NREC + 1):
        if not rezone[ir]:
            axr = float(e.AXR[ir])
            ayr = float(e.AYR[ir])
            rxr = axr * c + ayr * s
            ryr = -axr * s + ayr * c
            if rxr >= (bxr1 + (6.5 * bht)) and rxr <= (bxr2 - (6.5 * bht)) and \
                    ryr >= (byr - (40.0 * bht)) and ryr <= (byr + (40.0 * bht)):
                zona[ir] = True
    return zona


def baredgezone(e):
    """BAREDGEZONE (reset.f): receptores dentro de la zona de influencia de las barreras SBARRIER
    asociadas a fuentes RLINEXT (REEDGE); avisa si una barrera es demasiado corta."""
    m = "BAREDGEZONE"
    rl = e.RL
    idcheck = [False] * (e.NSBR + 1)
    blength = 0.0

    if rl.REEDGE is None:
        rl.REEDGE = np.zeros(e.NREC + 1, dtype=bool)
    rl.REEDGE[:] = False

    def _findloc(barid):
        for ib in range(1, e.NSBR + 1):
            if rl.SB_BARID[ib] == barid:
                return ib
        return 0

    for is_ in range(1, e.NSRC + 1):
        if e.SRCTYP[is_] != "RLINEXT":
            continue
        for ht_arr, id_arr in ((rl.S_HTWALL, rl.S_BARID), (rl.S_HTWALL2, rl.S_BARID2)):
            ht = float(ht_arr[is_])
            if ht > 0.0:
                idloc = _findloc(id_arr[is_])
                if idloc == 0:
                    raise NoTraducido("BAREDGEZONE: barrera %r no encontrada (FINDLOC = 0; acceso "
                                      "fuera de límites en el original)" % id_arr[is_])
                if not idcheck[idloc]:
                    idcheck[idloc] = True
                    nseg = int(rl.SB_NUMSEG[idloc])
                    bxs = [0.0, float(rl.SB_XBB[1, idloc]), float(rl.SB_XBE[nseg, idloc])]
                    bys = [0.0, float(rl.SB_YBB[1, idloc]), float(rl.SB_YBE[nseg, idloc])]
                    dx = bxs[1] - bxs[2]
                    dy = bys[1] - bys[2]
                    blength = math.sqrt(dx * dx + dy * dy)
                    if blength <= (2.0 * 6.5 * ht):
                        e.errhdl(e.PATH, m, "W", "275", "REEDGE")
                        e.BAREDGE = False
                    rl.REEDGE = barzone(e, bxs, bys, ht, rl.REEDGE)
