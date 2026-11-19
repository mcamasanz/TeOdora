# -*- coding: utf-8 -*-
"""Traducción de AERMOD 26135 (US EPA, dominio público): fuentes lineales flotantes BUOYLINE
(algoritmo adaptado del modelo BLP).

Rutinas traducidas:
  · bline.f completo: BL_CALC, BL_DBTSIG, BL_SIGMAY, BL_RISE, BL_ZRISE, BL_INTRSE, BL_GAUSS,
    BL_XVZ, BL_XVY, BL_WSC, BL_LENG, BL_SORT, BL_CUBIC y BL_ROTATE2.
  · El módulo BUOYANT_LINE de modules.f (clase `BuoyantLine`).
  · soset.f: BLPARM (SRCPARAM de una BUOYLINE), BLPGRP (clave BLPGROUP), BL_AVGINP (clave
    BLPINPUT), BL_ROTATE1 y los bloques BUOYLINE de SOCARD (STARTING, BLPINPUT/BLPGROUP,
    FINISHED), SOLOCA, HREMIS y SRCQA.
  · reset.f: BLRECP y su llamada desde RECARD (FINISHED).
  · aermod.f: las reservas de BUOYANT_LINE de ALLSETUP, AAFP de ALLRESULT y las matrices *_SAV
    del programa principal (MAXDCONT); la rama BUOYLINE de HRQEXT; el guardado de AFP para
    MAXDCONT en HRLOOP; las copias de las coordenadas de los receptores de MAXDCONT_LOOP.
  · calc1.f: la rama BUOYLINE de CALC y LTOPG (que la traducción todavía no tenía).
  · metext.f: BLTA = TA de SET_METDATA; output.f: la recuperación de AFP en MAXDCALC.

Estado: las variables del módulo BUOYANT_LINE viven en ``e.BUOY`` (no en ``e.BL``: BL ya es una
variable de MAIN1, la longitud del edificio de SWPOINT, que SETSRC asigna). Las que el resto de la
traducción ya usa como atributos del estado (NBLP, NBLTOTAL, NUMBLGRPS, NUMBLAVGINP,
NBLAVGINPALLOC, L_BLSOURCE, L_BLHOURLY y BLTA) son en ``e.BUOY`` alias de ``e.<NOMBRE>``, de modo
que ambos nombres ven siempre el mismo valor. El tipo derivado BLINEPARMS(L)%CAMPO se guarda como
matrices ``e.BUOY.P_CAMPO[L]`` (SRCID y BLPGRPNAME como listas de cadenas).

Las matrices siguen el convenio del paquete: índices 1..N del Fortran (posición 0 sin usar).
Las salidas de depuración (BLPDBUG, DEBUGOPT) y las opciones EVENT / EVALFILE paran con
NoTraducido."""
import math

import numpy as np

from .control import dbl, fsplit, sindex
from .estado import ILEN_FLD, NoTraducido, crear
from .formato import ErrorEjecucion, dsign, fc, fwrite, fx, nint


# ------------------------------------------------------------------------------------------
# Constantes (PARAMETER y DATA del original; todas en doble salvo donde se indica)
# ------------------------------------------------------------------------------------------
PARALLEL_TOL = 5.0                       # BUOYANT_LINE: Parallel_Tol

# BL_CALC
_BLCRIT = 0.02
_SRT2DP = 0.7978846
_AVFACT = 1.0
_WSPEXP = (None, 0.10, 0.15, 0.20, 0.25, 0.30, 0.30)
_TERAN = (None, 0.5, 0.5, 0.5, 0.5, 0.30, 0.30)
_DTHTA = (None, 0.02, 0.035)
_MAXIT = 14
_NSEGA = (None, 3, 5, 9, 17, 33, 65, 129)

# BL_DBTSIG
_XA = (None, 0.5, 0.4, 0.3, 0.25, 0.2, 0.15, 0.1)
_XB = (None, 0.4, 0.2)
_XD = (None, 30.0, 10.0, 3.0, 1.0, 0.3)
_XE = (None, 40.0, 20.0, 10.0, 4.0, 2.0, 1.0, 0.3, 0.1)
_XF = (None, 60.0, 30.0, 15.0, 7.0, 3.0, 2.0, 1.0, 0.7, 0.2)
_SG_AA = (None, 453.85, 346.75, 258.89, 217.41, 179.52, 170.22, 158.08, 122.8)
_SG_BA = (None, 2.1166, 1.7283, 1.4094, 1.2644, 1.1262, 1.0932, 1.0542, 0.9447)
_SG_AB = (None, 109.30, 98.483, 90.673)
_SG_BB = (None, 1.0971, 0.98332, 0.93198)
_SG_AD = (None, 44.053, 36.650, 33.504, 32.093, 32.093, 34.459)
_SG_BD = (None, 0.51179, 0.56589, 0.60486, 0.64403, 0.81066, 0.86974)
_SG_AE = (None, 47.618, 35.420, 26.970, 24.703, 22.534, 21.628, 21.628, 23.331, 24.26)
_SG_BE = (None, 0.29592, 0.37615, 0.46713, 0.50527, 0.57154, 0.63077, 0.75660, 0.81956, 0.8366)
_SG_AF = (None, 34.219, 27.074, 22.651, 17.836, 16.187, 14.823, 13.953, 13.953, 14.457, 15.209)
_SG_BF = (None, 0.21716, 0.27436, 0.32681, 0.41507, 0.46490, 0.54503, 0.63227, 0.68465, 0.78407,
          0.81558)

# BL_SIGMAY: el 8.3333 de la estabilidad D es un literal REAL*4 (sin D0) en el original
_R4_8P3333 = float(np.float32(8.3333))

# BL_XVZ
_SA = (None, 13.95, 21.40, 29.3, 37.67, 47.44, 71.16, 104.65)
_SB = (None, 20.23, 40.0)
_SD = (None, 12.09, 32.09, 65.12, 134.9, 251.2)
_SE = (None, 3.534, 8.698, 21.628, 33.489, 49.767, 79.07, 109.3, 141.86)
_SF = (None, 4.093, 10.93, 13.953, 21.627, 26.976, 40.0, 54.89, 68.84, 83.25)
_VZ_AA = (None, 122.8, 158.08, 170.22, 179.52, 217.41, 258.89, 346.75, 453.85)
_VZ_AB = (None, 90.673, 98.483, 109.3)
_VZ_AD = (None, 34.459, 32.093, 32.093, 33.504, 36.650, 44.053)
_VZ_AE = (None, 24.26, 23.331, 21.628, 21.628, 22.534, 24.703, 26.97, 35.42, 47.618)
_VZ_AF = (None, 15.209, 14.457, 13.953, 13.953, 14.823, 16.187, 17.836, 22.651, 27.074, 34.219)
_VZ_CA = (None, 1.0585, 0.9486, 0.9147, 0.8879, 0.7909, 0.7095, 0.5786, 0.4725)
_VZ_CB = (None, 1.073, 1.017, 0.9115)
_VZ_CD = (None, 1.1498, 1.2336, 1.5527, 1.6533, 1.7671, 1.9539)
_VZ_CE = (None, 1.1953, 1.2202, 1.3217, 1.5854, 1.7497, 1.9791, 2.1407, 2.6585, 3.3793)
_VZ_CF = (None, 1.2261, 1.2754, 1.4606, 1.5816, 1.8348, 2.151, 2.4092, 3.0599, 3.6448, 4.6049)

# BL_GAUSS (DATA)
_TMIN = 0.0512
_TMAX = 9.21
_EPSIL = 1.0e-30

# BL_LENG (DATA)
_RAD = 0.0174533

# BL_ROTATE2
_TCHK = (None, 90.0, 180.0, 270.0, 360.0)
_ISEG = (None, 1, 129, 129, 1)
_DEG_PER_RAD = 57.29578


# ------------------------------------------------------------------------------------------
# Utilidades IEEE: Intel sin trampas de coma flotante devuelve NaN/Inf donde Python lanzaría
# una excepción (o devolvería un complejo, en x**y con x < 0).
# ------------------------------------------------------------------------------------------
def _div(a, b):
    """División IEEE (±Inf o NaN al dividir por cero)."""
    if b == 0.0:
        if a == 0.0 or a != a:
            return math.nan
        return math.copysign(math.inf, a) * math.copysign(1.0, b)
    return a / b


def _sqrt(x):
    """DSQRT IEEE: NaN para argumentos negativos."""
    return math.sqrt(x) if x >= 0.0 else math.nan


def _pow(x, y):
    """x**y real IEEE (exponentes no enteros): NaN si x < 0; +Inf si x = 0 e y < 0."""
    if x < 0.0:
        return math.nan
    if x == 0.0 and y < 0.0:
        return math.inf
    return x ** y


def _exp(x):
    """EXP IEEE: +Inf si desborda (en vez de OverflowError)."""
    try:
        return math.exp(x)
    except OverflowError:
        return math.inf


def _log(x):
    """DLOG IEEE: -Inf en 0 y NaN para negativos."""
    if x > 0.0:
        return math.log(x)
    if x == 0.0:
        return -math.inf
    return math.nan


def _acos(x):
    """DACOS IEEE: NaN fuera de [-1, 1]."""
    if -1.0 <= x <= 1.0:
        return math.acos(x)
    return math.nan


def _sy_de_th(xy, th):
    """SY = 1000*XY*DSIN(TH)/(2.15*DCOS(TH)) (común a BL_DBTSIG y BL_SIGMAY); NaN si TH no es
    finito (DSIN/DCOS de Inf dan NaN en el original)."""
    if th - th == 0.0:
        return 1000.0 * xy * math.sin(th) / (2.15 * math.cos(th))
    return math.nan


def _mods():
    """Módulos que se importan al usarse (evita importaciones circulares)."""
    from . import calculo_area, funciones_dispersion, resultados
    return calculo_area, funciones_dispersion, resultados


# ------------------------------------------------------------------------------------------
# Módulo BUOYANT_LINE
# ------------------------------------------------------------------------------------------
# variables de BUOYANT_LINE que el resto de la traducción ya guarda en el estado: aquí son alias
_ALIAS_INI = {"NBLP": 0, "NBLTOTAL": 0, "NUMBLGRPS": 0, "NUMBLAVGINP": 0, "NBLAVGINPALLOC": 0,
              "L_BLSOURCE": False, "L_BLHOURLY": False, "BLTA": 0.0}


def _alias(nom):
    def leer(self):
        return getattr(self._e, nom)

    def poner(self, v):
        setattr(self._e, nom, v)

    return property(leer, poner, doc="Alias de e.%s." % nom)


class BuoyantLine:
    """Variables del módulo BUOYANT_LINE (modules.f), con sus valores iniciales: cero, .FALSE. o
    blanco salvo BL_XDIST = 0, DH = 0 y Parallel_Tol = 5. Las ALLOCATABLE valen None hasta
    `reservar`. Los atributos con guion bajo inicial son variables locales del original que deben
    conservar su valor entre llamadas."""

    NBLP = _alias("NBLP")
    NBLTOTAL = _alias("NBLTOTAL")
    NUMBLGRPS = _alias("NUMBLGRPS")
    NUMBLAVGINP = _alias("NUMBLAVGINP")
    NBLAVGINPALLOC = _alias("NBLAVGINPALLOC")
    L_BLSOURCE = _alias("L_BLSOURCE")
    L_BLHOURLY = _alias("L_BLHOURLY")
    BLTA = _alias("BLTA")

    def __init__(self, e):
        self._e = e
        for nom, val in _ALIAS_INI.items():
            if not hasattr(e, nom):
                setattr(e, nom, val)
        self.PARALLEL_TOL = PARALLEL_TOL
        # BLINEPARMS(NBLP)
        self.P_ISRCNUM = None
        self.P_SRCID = None
        self.P_IBLPGRPNUM = None
        self.P_BLPGRPNAME = None
        self.P_XBEG = self.P_YBEG = self.P_XEND = self.P_YEND = None
        self.P_XBEG_TR1 = self.P_YBEG_TR1 = self.P_XEND_TR1 = self.P_YEND_TR1 = None
        self.P_ELEV = self.P_BLQS = self.P_BLHS = None
        # coordenadas de los segmentos
        self.XS_SCS = self.YS_SCS = self.XS_RCS = self.YS_RCS = None
        # por grupo
        self.L_BLURBAN = None
        self.BL_RFLAG = None
        self.NBLINGRP = None
        self.HRLYBLCOUNT = None
        self.BL_NUMURB = None
        # BLPINPUT
        self.BLAVGINP_LLEN = self.BLAVGINP_BHGT = self.BLAVGINP_BWID = None
        self.BLAVGINP_LWID = self.BLAVGINP_BSEP = self.BLAVGINP_FPRM = None
        self.BLAVGINP_GRPID = None
        self.BL_GRPID = None
        # parámetros medios del grupo en curso
        self.BLAVGLLEN = 0.0
        self.BLAVGBHGT = 0.0
        self.BLAVGBWID = 0.0
        self.BLAVGLWID = 0.0
        self.BLAVGBSEP = 0.0
        self.BLAVGFPRM = 0.0
        self.BL_UREF = 0.0
        self.BL_XDIST = np.zeros(8)
        self.DH = np.zeros(8)
        self.DEL = None
        self.BL_XFB = 0.0
        self.LEFF = 0.0
        self.LD = 0.0
        self.R0 = 0.0
        self.BL_XFINAL = 0.0
        self.BL_XFS = 0.0
        self.FPRMXNB = 0.0
        self.XMATCH = 0.0
        self.PARTCH = 0.0
        self.XOR = self.YOR = self.ANGRAD = None
        self.TCOR = self.SINTCOR = self.COSTCOR = None
        self.XR_SCS = self.YR_SCS = None
        self.XR_RCS = self.YR_RCS = None
        self.XR_SCS_SAV = self.YR_SCS_SAV = None
        self.BL_RFLAG_SAV = None
        self.CHIBL = None
        # locales con valor conservado entre llamadas
        self._IGRPNUM = 0                 # BLPGRP: INTEGER, SAVE :: IGRPNUM
        self._NDEX = 7                    # BL_INTRSE: NDEX sin definir si X = BL_XDIST(7)


def reservar(e):
    """ALLSETUP (aermod.f, «Buoyant line allocation», líneas 4273-4331): crea ``e.BUOY`` (siempre:
    las variables del módulo existen aunque no haya fuentes BUOYLINE) y, si NBLP > 0, las matrices
    con los mismos tamaños: BLINEPARMS, XS_SCS, YS_SCS, XS_RCS, YS_RCS, DEL (NBLP); CHIBL,
    XR_RCS, YR_RCS (NREC); XR_SCS, YR_SCS, BL_RFLAG (NREC, NBLGRP); BLAVGINP_* (NBLAVGINPalloc);
    NBLINGRP, ANGRAD, HRLYBLCOUNT, XOR, YOR, TCOR, SINTCOR, COSTCOR, BL_GRPID, L_BLURBAN,
    BL_NUMURB (NBLGRP) e IGRP_BLP (NSRC, NBLGRP; de MAIN1). El original no inicializa estas
    matrices (ALLOCATE); aquí nacen a cero / .FALSE. / blanco."""
    if getattr(e, "BUOY", None) is None:
        e.BUOY = BuoyantLine(e)
    b = e.BUOY
    if b.NBLP > 0:
        nblp, nrec, ngr, nav = b.NBLP, e.NREC, e.NBLGRP, b.NBLAVGINPALLOC
        b.P_ISRCNUM = crear("INTEGER", [nblp])
        b.P_SRCID = crear("CHARACTER", [nblp], 12)
        b.P_IBLPGRPNUM = crear("INTEGER", [nblp])
        b.P_BLPGRPNAME = crear("CHARACTER", [nblp], 8)
        for n in ("P_XBEG", "P_YBEG", "P_XEND", "P_YEND", "P_XBEG_TR1", "P_YBEG_TR1", "P_XEND_TR1",
                  "P_YEND_TR1", "P_ELEV", "P_BLQS", "P_BLHS"):
            setattr(b, n, crear("DOUBLE", [nblp]))
        b.XS_SCS = crear("DOUBLE", [nblp, 129])
        b.YS_SCS = crear("DOUBLE", [nblp])
        b.XS_RCS = crear("DOUBLE", [nblp, 129])
        b.YS_RCS = crear("DOUBLE", [nblp, 129])
        b.DEL = crear("DOUBLE", [nblp])
        b.CHIBL = crear("DOUBLE", [nrec])
        b.XR_SCS = crear("DOUBLE", [nrec, ngr])
        b.YR_SCS = crear("DOUBLE", [nrec, ngr])
        b.XR_RCS = crear("DOUBLE", [nrec])
        b.YR_RCS = crear("DOUBLE", [nrec])
        b.BL_RFLAG = crear("LOGICAL", [nrec, ngr])
        b.BLAVGINP_GRPID = crear("CHARACTER", [nav], 8)
        for n in ("BLAVGINP_LLEN", "BLAVGINP_BWID", "BLAVGINP_BHGT", "BLAVGINP_BSEP",
                  "BLAVGINP_LWID", "BLAVGINP_FPRM"):
            setattr(b, n, crear("DOUBLE", [nav]))
        b.NBLINGRP = crear("INTEGER", [ngr])
        b.ANGRAD = crear("DOUBLE", [ngr])
        b.HRLYBLCOUNT = crear("INTEGER", [ngr])
        for n in ("XOR", "YOR", "TCOR", "SINTCOR", "COSTCOR"):
            setattr(b, n, crear("DOUBLE", [ngr]))
        e.alloc("IGRP_BLP", e.NSRC, ngr)
        b.BL_GRPID = crear("CHARACTER", [ngr], 8)
        b.L_BLURBAN = crear("LOGICAL", [ngr])
        b.BL_NUMURB = crear("INTEGER", [ngr])
    return b


def reservar_resultados_bl(e):
    """ALLRESULT (aermod.f, rama L_MAXDCONT, línea 5052): AAFP(8784, NYEARS, NSRC) si hay
    emisiones horarias y fuentes BUOYLINE (la rama EVONLY, AAFP(NHR,1,NSRC), está fuera de
    alcance)."""
    if e.L_MAXDCONT and not e.EVONLY and e.HOURLY and e.NBLP > 0:
        e.alloc("AAFP", 8784, e.NYEARS, e.NSRC)


def reservar_maxd(e):
    """Programa principal (aermod.f, líneas 614-620), antes de MAXDCONT_LOOP: matrices
    XR_SCS_SAV, YR_SCS_SAV y BL_RFLAG_SAV (NREC, NBLGRP) si hay fuente BUOYLINE."""
    b = e.BUOY
    if b.L_BLSOURCE:
        b.XR_SCS_SAV = crear("DOUBLE", [e.NREC, e.NBLGRP])
        b.YR_SCS_SAV = crear("DOUBLE", [e.NREC, e.NBLGRP])
        b.BL_RFLAG_SAV = crear("LOGICAL", [e.NREC, e.NBLGRP])


# ------------------------------------------------------------------------------------------
# Vía SO (soset.f)
# ------------------------------------------------------------------------------------------
def starting_bl_contadores(e):
    """SOCARD, STARTING (soset.f, líneas 83-91, antes del control de clave repetida):
    NUMBLAVGINP = NUMBLGRPS = 0 y, si existen, NBLINGRP = 0 e IGRP_BLP = 0."""
    b = e.BUOY
    b.NUMBLAVGINP = 0
    b.NUMBLGRPS = 0
    if b.NBLINGRP is not None:
        b.NBLINGRP[:] = 0
    if getattr(e, "IGRP_BLP", None) is not None:
        e.IGRP_BLP[...] = 0


def starting_bl_indicadores(e):
    """SOCARD, STARTING (soset.f, líneas 107-112, tras el control de clave repetida):
    L_BLSOURCE = .FALSE. y, si existen, L_BLURBAN = .FALSE. y BL_NUMURB = 0."""
    b = e.BUOY
    b.L_BLSOURCE = False
    if b.L_BLURBAN is not None:
        b.L_BLURBAN[:] = False
    if b.BL_NUMURB is not None:
        b.BL_NUMURB[:] = 0


def socard_bl(e, k):
    """SOCARD, claves BLPINPUT (ISSTAT(43); BL_AVGINP) y BLPGROUP (ISSTAT(44); BLPGRP), soset.f
    líneas 654-677. Devuelve True si la clave era una de ellas."""
    if k == "BLPINPUT":
        e.ISSTAT[43] += 1
        bl_avginp(e)
        return True
    if k == "BLPGROUP":
        e.ISSTAT[44] += 1
        blpgrp(e)
        return True
    return False


def soloca_bl(e, isrc):
    """SOLOCA (soset.f, líneas 2504-2509), tras NUMSRC = NUMSRC + 1: cuenta las líneas BUOYLINE
    en NBLTOTAL. (La lectura de LOCATION de una BUOYLINE es la de una LINE: AXS1, AYS1, AXS2,
    AYS2 en los campos 5-8 y la cota en el 9.)"""
    if e.SRCTYP[isrc] == "BUOYLINE":
        e.BUOY.NBLTOTAL += 1


def blparm(e, isdx, temp):
    """BLPARM: SRCPARAM de una fuente BUOYLINE (emisión y altura medias de emisión)."""
    m = "BLPARM"
    e.AQS[isdx] = temp[1]
    e.AHS[isdx] = temp[2]
    if e.AQS[isdx] == 0.0:
        e.errhdl(e.PATH, m, "W", "320", " QS ")
    if e.AHS[isdx] < 0.0:
        e.errhdl(e.PATH, m, "E", "209", " HS ")
    elif e.AHS[isdx] > 100.0:
        e.errhdl(e.PATH, m, "W", "320", " HS ")
    elif e.AHS[isdx] > 3000.0:
        # inalcanzable (ya es > 100), como en el original
        e.errhdl(e.PATH, m, "E", "324", e.SRCID[isdx])
    e.AXS[isdx] = (e.AXS1[isdx] + e.AXS2[isdx]) * 0.5
    e.AYS[isdx] = (e.AYS1[isdx] + e.AYS2[isdx]) * 0.5


def bl_avginp(e):
    """BL_AVGINP: clave BLPINPUT (parámetros medios de la sobreelevación de un grupo: longitud de
    línea, altura, anchura y separación de edificios, anchura de línea y flotabilidad F')."""
    m = "BL_AVGINP"
    b = e.BUOY
    ifc = e.IFC
    if ifc <= 2:
        e.errhdl(e.PATH, m, "E", "200", e.KEYWRD)
        return
    elif ifc < 8:
        e.errhdl(e.PATH, m, "E", "201", e.KEYWRD)
        return
    elif ifc > 9:
        e.errhdl(e.PATH, m, "E", "202", e.KEYWRD)
        return
    if ifc == 8:
        if b.NUMBLAVGINP >= 1:
            e.errhdl(e.PATH, m, "E", "201", e.KEYWRD)
            return
        if b.NBLP == 0:
            e.errhdl(e.PATH, m, "E", "508", "  ")
            return
        b.NUMBLAVGINP = 1
        b.BLAVGINP_GRPID[b.NUMBLAVGINP] = "ALL"
        campos = (3, 4, 5, 6, 7, 8)
    else:
        tempid = fc(e.FIELD[3], 12)
        if b.BLAVGINP_GRPID is None:
            raise NoTraducido("BLPINPUT con identificador de grupo y sin fuentes BUOYLINE (el "
                              "original escribe en BLAVGINP_GRPID sin reservar)")
        if b.NUMBLAVGINP > 0:
            for _kk in range(1, b.NUMBLAVGINP + 1):
                _isdx, found = sindex(b.BLAVGINP_GRPID, b.NUMBLAVGINP, tempid)
                if found:
                    e.errhdl(e.PATH, m, "E", "504", tempid)
                    return
                b.NUMBLAVGINP += 1
                b.BLAVGINP_GRPID[b.NUMBLAVGINP] = fc(tempid, 8)
                break
        else:
            b.NUMBLAVGINP += 1
            b.BLAVGINP_GRPID[b.NUMBLAVGINP] = fc(tempid, 8)
        campos = (4, 5, 6, 7, 8, 9)
    n = b.NUMBLAVGINP
    for k, dest in zip(campos, (b.BLAVGINP_LLEN, b.BLAVGINP_BHGT, b.BLAVGINP_BWID,
                                b.BLAVGINP_LWID, b.BLAVGINP_BSEP, b.BLAVGINP_FPRM)):
        e.DNUM, imit = dbl(e, k, e.DNUM)
        e.IMIT = imit
        if imit != 1:
            e.errhdl(e.PATH, m, "E", "208", e.KEYWRD)
            return
        dest[n] = e.DNUM
    b.L_BLSOURCE = True


def blpgrp(e):
    """BLPGRP: clave BLPGROUP (líneas que forman cada grupo/fuente BUOYLINE). El número de grupo
    de una tarjeta de continuación es el guardado (SAVE) de la tarjeta anterior."""
    from .entrada_fuentes import asngrp, setidg
    m = "BLPGRP"
    b = e.BUOY
    f = e.FIELD
    cont = False
    blpavggrp_found = False
    if e.IFC <= 2:
        e.errhdl(e.PATH, m, "E", "200", e.KEYWRD)
        return
    elif e.IFC <= 3 and f[3] != "ALL":
        e.errhdl(e.PATH, m, "E", "201", e.KEYWRD)
        return
    if e.LOCE[3] - e.LOCB[3] <= 7:
        tempid = fc(f[3], 12)
        for i in range(1, b.NUMBLGRPS + 1):
            if tempid == b.BL_GRPID[i]:
                blpavggrp_found = True
                cont = True
                break
    else:
        e.errhdl(e.PATH, m, "E", "245", f[3][:12])
        return
    if not cont:
        for kk in range(1, b.NUMBLAVGINP + 1):
            if tempid == b.BLAVGINP_GRPID[kk]:
                b._IGRPNUM = kk
                blpavggrp_found = True
                b.NUMBLGRPS += 1
                b.BL_GRPID[b._IGRPNUM] = fc(tempid, 8)
                break
    igrpnum = b._IGRPNUM
    if blpavggrp_found:
        if b.BL_GRPID[igrpnum] == "ALL" and not cont:
            for kk in range(1, e.NUMSRC + 1):
                if e.SRCTYP[kk] == "BUOYLINE":
                    e.IGRP_BLP[kk, igrpnum] = 1
        else:
            for jj in range(4, e.IFC + 1):
                if "-" not in f[jj]:
                    found = False
                    for kk in range(1, e.NUMSRC + 1):
                        if f[jj] == e.SRCID[kk]:
                            if e.SRCTYP[kk] == "BUOYLINE":
                                found = True
                                e.IGRP_BLP[kk, igrpnum] = 1
                                break
                            else:
                                e.errhdl(e.PATH, m, "E", "255", f[jj][:12])
                    if not found:
                        e.errhdl(e.PATH, m, "E", "254", f[jj][:12])
                else:
                    _r, lowid, higid = fsplit(e, e.PATH, e.KEYWRD, f[jj], ILEN_FLD, "-")
                    lowid, higid = fc(lowid, 12), fc(higid, 12)
                    lid1, il, lid2 = setidg(lowid)
                    hid1, ih, hid2 = setidg(higid)
                    if hid1 < lid1 or ih < il or hid2 < lid2:
                        e.errhdl(e.PATH, m, "E", "203", "SRCRANGE")
                        continue
                    for kk in range(1, e.NUMSRC + 1):
                        if e.SRCTYP[kk] == "BUOYLINE":
                            if asngrp(e.SRCID[kk], lowid, higid):
                                e.IGRP_BLP[kk, igrpnum] = 1
    else:
        e.DUMMY = fc(fwrite("(A12)", fx(tempid, 12))[0], 12)
        e.errhdl(e.PATH, m, "E", "502", e.DUMMY)


def hremis_bl(e, k):
    """HREMIS (soset.f, líneas 6487-6489 y 6536-6539): para cada fuente K a la que se asigna
    QFLAG = 'HOURLY', activa L_BLHOURLY si es una BUOYLINE."""
    if e.SRCTYP[k] == "BUOYLINE" and not e.L_BLHOURLY:
        e.L_BLHOURLY = True


def finished_bl(e):
    """SOCARD, FINISHED (soset.f, líneas 864-952; con NUMSRC > 0, tras los errores 244 y antes
    de SRCQA): MODOPS(25), grupo 'ALL' para ficheros antiguos sin BLPGROUP, relleno de
    BLINEPARMS y NBLINGRP y primera traslación/rotación de cada grupo (BL_ROTATE1)."""
    b = e.BUOY
    lnum = 0
    if b.NBLTOTAL > 0:
        e.MODOPS[25] = "BUOYLINE"
        b.L_BLSOURCE = True
        if b.NUMBLGRPS == 0 and b.NUMBLAVGINP > 0:
            b.NUMBLGRPS = 1
            for i in range(1, e.NUMSRC + 1):
                if e.SRCTYP[i] == "BUOYLINE":
                    e.IGRP_BLP[i, 1] = 1
            b.BL_GRPID[1] = "ALL"
        for i in range(1, e.NUMSRC + 1):
            if e.SRCTYP[i] == "BUOYLINE":
                lnum += 1
                b.P_ISRCNUM[lnum] = i
                b.P_SRCID[lnum] = e.SRCID[i]
                b.P_XBEG[lnum] = e.AXS1[i]
                b.P_YBEG[lnum] = e.AYS1[i]
                b.P_XEND[lnum] = e.AXS2[i]
                b.P_YEND[lnum] = e.AYS2[i]
                b.P_ELEV[lnum] = e.AZS[i]
                b.P_BLQS[lnum] = e.AQS[i]
                b.P_BLHS[lnum] = e.AHS[i]
                for j in range(1, b.NUMBLGRPS + 1):
                    if e.IGRP_BLP[i, j] == 1:
                        b.P_IBLPGRPNUM[lnum] = j
                        b.P_BLPGRPNAME[lnum] = b.BL_GRPID[j]
                        b.NBLINGRP[j] += 1
                        break
        for kk in range(1, b.NUMBLGRPS + 1):
            bl_rotate1(e, kk)


def srcqa_bl(e, modnam):
    """SRCQA (soset.f, líneas 1489-1708; tras los controles de zonas urbanas y de aeronaves y
    antes del de OLMGROUP): altura mínima de 2 m, orden oeste-este de los extremos, coherencia de
    BLPINPUT/BLPGROUP/HOUREMIS, grupos urbanos completos, cada línea en un único grupo y orden de
    las líneas por grupo. Como en el original, los bucles ``DO ILINE = ...`` usan ILINE de MAIN1
    como índice y lo dejan modificado."""
    b = e.BUOY
    nbt = b.NBLTOTAL
    ngr = b.NUMBLGRPS
    nerrcount = 0
    if b.L_BLSOURCE:
        for lnum in range(1, nbt + 1):
            if b.P_BLHS[lnum] < 2.0:
                b.P_BLHS[lnum] = 2.0
                e.DUMMY = fc(fwrite("('line #',I2)", lnum)[0], 12)
                e.errhdl(e.PATH, modnam, "W", "472", e.DUMMY)
        for iline in range(1, nbt + 1):
            e.ILINE = iline
            blxbeg = float(b.P_XBEG[iline])
            blxend = float(b.P_XEND[iline])
            if blxbeg > blxend:
                nerrcount += 1
        e.ILINE = nbt + 1
        if nerrcount > 0:
            e.errhdl(e.PATH, modnam, "E", "388", "BUOYLINE")
        if b.NUMBLAVGINP == 0 and nbt > 0:
            e.errhdl(e.PATH, modnam, "E", "507", "  ")
        if ngr != e.NBLGRP:
            e.errhdl(e.PATH, modnam, "E", "509", "  ")
        if ngr != b.NUMBLAVGINP:
            e.errhdl(e.PATH, modnam, "E", "503", "  ")
        if ngr > 0:
            b.HRLYBLCOUNT[1:ngr + 1] = 0
        if b.L_BLHOURLY:
            for lnum in range(1, nbt + 1):
                if e.QFLAG[int(b.P_ISRCNUM[lnum])] == "HOURLY":
                    for kk in range(1, ngr + 1):
                        if b.P_IBLPGRPNUM[lnum] == kk:
                            b.HRLYBLCOUNT[kk] += 1
            for kk in range(1, ngr + 1):
                if b.HRLYBLCOUNT[kk] > 0 and b.NBLINGRP[kk] > 0:
                    if b.HRLYBLCOUNT[kk] != b.NBLINGRP[kk]:
                        e.errhdl(e.PATH, modnam, "E", "383", b.BL_GRPID[kk])
        lcount = 0
        for kk in range(1, ngr + 1):
            nl = int(b.NBLINGRP[kk])
            for iline in range(1, nl + 1):
                e.ILINE = iline
                lcount += 1
                if e.URBSRC[int(b.P_ISRCNUM[lcount])] == "Y":
                    if not b.L_BLURBAN[kk]:
                        b.L_BLURBAN[kk] = True
                    b.BL_NUMURB[kk] += 1
            e.ILINE = nl + 1
            if b.L_BLURBAN[kk] and b.BL_NUMURB[kk] != nl:
                e.errhdl(e.PATH, modnam, "E", "393", b.BL_GRPID[kk])
        if ngr > 0:
            for i in range(1, e.NUMSRC + 1):
                itotgrp = 0
                if e.SRCTYP[i] == "BUOYLINE":
                    for j in range(1, ngr + 1):
                        if e.IGRP_BLP[i, j] == 1:
                            itotgrp += 1
                    if itotgrp > 1:
                        e.errhdl(e.PATH, modnam, "E", "257", e.SRCID[i])
                    if itotgrp == 0:
                        e.errhdl(e.PATH, modnam, "E", "258", e.SRCID[i])
    if ngr > 1:
        for lnum in range(2, nbt + 1):
            if b.P_IBLPGRPNUM[lnum] - b.P_IBLPGRPNUM[lnum - 1] < 0:
                e.DUMMY = fc(fwrite("(I2,' and',I2)", int(b.P_IBLPGRPNUM[lnum - 1]),
                                    int(b.P_IBLPGRPNUM[lnum]))[0], 12)
                e.errhdl(e.PATH, modnam, "E", "505", e.DUMMY)


def srcqa_depos_bl(e, modnam):
    """SRCQA (soset.f, líneas 1725-1734; tras el control de OLMGROUP): deposición incompatible con
    BUOYLINE o, si no hay BUOYLINE, con RLINE/RLINEXT (es un IF / ELSE IF)."""
    if e.DEPOS or e.DDEP or e.WDEP:
        if e.NBLTOTAL > 0:
            e.errhdl(e.PATH, modnam, "E", "251", "BUOYLINE")
        elif e.NRLINES > 0:
            e.errhdl(e.PATH, modnam, "E", "251", "RLINE/RLINEXT")


def srcqa_screen_bl(e, modnam):
    """SRCQA (soset.f, líneas 1740-1746): aviso 731 de SCREEN con BUOYLINE (el primero del
    bloque IF (SCREEN), antes de RLINE, SWPOINT, AREA...)."""
    if e.SCREEN and e.NBLTOTAL > 0:
        e.errhdl(e.PATH, modnam, "W", "731", "BUOYLINE")


def bl_rotate1(e, kk):
    """BL_ROTATE1: traslada el grupo KK al origen de su primera línea y lo gira para alinear el
    eje x con las líneas; comprueba el orden de las líneas en y (389) y que sean paralelas a la
    primera dentro de Parallel_Tol grados (506)."""
    m = "BL_ROTATE1"
    b = e.BUOY
    nbt = b.NBLTOTAL
    grp = b.P_IBLPGRPNUM
    bl_ycoord_chk = False
    # (IPLSTART queda sin definir en el original si el grupo no tiene líneas; el bucle del
    # paralelismo no encontraría entonces ninguna línea del grupo)
    iplstart = nbt + 1
    for il in range(1, nbt + 1):
        if grp[il] == kk:
            iplstart = il + 1
            b.XOR[kk] = b.P_XBEG[il]
            b.YOR[kk] = b.P_YBEG[il]
            ddx = float(b.P_XEND[il]) - float(b.XOR[kk])
            ddy = float(b.P_YEND[il]) - float(b.YOR[kk])
            ang = math.atan2(ddy, ddx)
            b.ANGRAD[kk] = ang
            b.TCOR[kk] = 90.0 + ang * e.RTODEG
            b.SINTCOR[kk] = math.sin(ang)
            b.COSTCOR[kk] = math.cos(ang)
            if abs(b.COSTCOR[kk]) < 1.0e-10:
                b.COSTCOR[kk] = 1.0e-05
            break
    xo, yo = float(b.XOR[kk]), float(b.YOR[kk])
    s, c = float(b.SINTCOR[kk]), float(b.COSTCOR[kk])
    for il in range(1, nbt + 1):
        if grp[il] == kk:
            xb1 = float(b.P_XBEG[il]) - xo
            xe1 = float(b.P_XEND[il]) - xo
            yb1 = float(b.P_YBEG[il]) - yo
            ye1 = float(b.P_YEND[il]) - yo
            yb1 = -xb1 * s + yb1 * c
            b.P_YBEG_TR1[il] = yb1
            xb1 = _div(xb1 + yb1 * s, c)
            b.P_XBEG_TR1[il] = xb1
            ye1 = -xe1 * s + ye1 * c
            b.YS_SCS[il] = ye1
            b.P_YEND_TR1[il] = ye1
            xe1 = _div(xe1 + ye1 * s, c)
            b.P_XEND_TR1[il] = xe1
    ylbsav = ylesav = 0.0
    for il in range(1, nbt + 1):
        if grp[il] == kk:
            if not bl_ycoord_chk:
                ylbsav = float(b.P_YBEG_TR1[il])
                ylesav = float(b.P_YEND_TR1[il])
                bl_ycoord_chk = True
            else:
                if b.P_YBEG_TR1[il] > ylbsav and b.P_YEND_TR1[il] > ylesav:
                    ylbsav = float(b.P_YBEG_TR1[il])
                    ylesav = float(b.P_YEND_TR1[il])
                else:
                    e.errhdl(e.PATH, m, "E", "389", b.P_SRCID[il])
    grados = 180.0 / (4.0 * math.atan(1.0))
    for ilp in range(iplstart, nbt + 1):
        if grp[ilp] == kk:
            xor2 = float(b.P_XBEG[ilp])
            yor2 = float(b.P_YBEG[ilp])
            ddx2 = float(b.P_XEND[ilp]) - xor2
            ddy2 = float(b.P_YEND[ilp]) - yor2
            angrad2 = math.atan2(ddy2, ddx2)
            angdiff = abs(float(b.ANGRAD[kk]) - angrad2) * grados
            if angdiff > PARALLEL_TOL:
                e.errhdl(e.PATH, m, "W", "506", b.P_SRCID[ilp])


# ------------------------------------------------------------------------------------------
# Vía RE (reset.f)
# ------------------------------------------------------------------------------------------
def recard_bl(e):
    """RECARD, FINISHED (reset.f, líneas 183-188; tras convertir las cotas de los receptores y
    antes de BAREDGE): si hay líneas BUOYLINE, BL_RFLAG = .FALSE. y BLRECP para cada grupo."""
    b = e.BUOY
    if b.NBLTOTAL >= 1:
        b.BL_RFLAG[...] = False
        for kk in range(1, b.NUMBLGRPS + 1):
            blrecp(e, kk)


def blrecp(e, kk):
    """BLRECP: primera traslación/rotación de los receptores para el grupo KK (la de sus líneas)
    y marca BL_RFLAG de los receptores dentro del rectángulo que ocupan las líneas (aviso 476
    con su número)."""
    m = "BLRECEP"
    b = e.BUOY
    n = e.NUMREC
    xo, yo = float(b.XOR[kk]), float(b.YOR[kk])
    s, c = float(b.SINTCOR[kk]), float(b.COSTCOR[kk])
    with np.errstate(all="ignore"):
        ex = e.AXR[1:n + 1] - xo
        ey = e.AYR[1:n + 1] - yo
        ey = -ex * s + ey * c
        b.YR_SCS[1:n + 1, kk] = ey
        ex = (ex + ey * s) / c
        b.XR_SCS[1:n + 1, kk] = ex
    nbt = b.NBLTOTAL
    grp = b.P_IBLPGRPNUM
    # (sin definir en el original si el grupo no tiene líneas)
    ylmax = xlmax = xlmin = ylmin = 0.0
    for lnum in range(1, nbt + 1):
        if grp[lnum] == kk:
            ylmax = float(b.YS_SCS[lnum])
            xlmax = float(b.P_XEND_TR1[lnum])
            xlmin = float(b.P_XBEG_TR1[lnum])
            break
    for lnum in range(nbt, 0, -1):
        if grp[lnum] == kk:
            ylmin = float(b.YS_SCS[lnum])
            break
    for lnum in range(1, nbt + 1):
        if grp[lnum] == kk:
            xlmin = min(xlmin, float(b.P_XBEG_TR1[lnum]))
            xlmax = max(xlmax, float(b.P_XEND_TR1[lnum]))
            ylmin = min(ylmin, float(b.YS_SCS[lnum]))
            ylmax = max(ylmax, float(b.YS_SCS[lnum]))
    yr = b.YR_SCS[1:n + 1, kk]
    xr = b.XR_SCS[1:n + 1, kk]
    dentro = ((yr <= (ylmax + 0.1)) & (yr >= (ylmin - 0.1)) &
              (xr <= (xlmax + 0.1)) & (xr >= (xlmin - 0.1)))
    nrecin = int(dentro.sum())
    col = b.BL_RFLAG[1:n + 1, kk]
    col[dentro] = True
    e.DUMMY = fc(fwrite('(I3," (",A6,")")', nrecin, fx(b.BL_GRPID[kk], 8))[0], 12)
    e.errhdl(e.PATH, m, "W", "476", e.DUMMY)


# ------------------------------------------------------------------------------------------
# Bucle horario: emisiones, meteorología y MAXDCONT
# ------------------------------------------------------------------------------------------
def hrqext_bl(e, i):
    """HRQEXT (aermod.f, líneas 2293-2294 y 2332-2333): parámetro de flotabilidad de la hora
    (AFP) de una fuente BUOYLINE con emisiones horarias."""
    if e.EVONLY:
        raise NoTraducido("EVENT")
    e.AFP[i] = e.HRFP


def hrqext_bl_qa(e, i):
    """HRQEXT (aermod.f, líneas 2489-2493): control de calidad de AFP de una BUOYLINE (rama
    del IF de QA tras POINT, VOLUME y AREA/LINE/RLINE)."""
    if e.AFP[i] < 0.0:
        e.errhdl(e.PATH, "HRQEXT", "E", "209", "HRFP")


def hrloop_maxd_bl(e, isrc):
    """HRLOOP (aermod.f, líneas 959-960): guarda AFP de la hora para MAXDCONT (rama BUOYLINE del
    IF que guarda AAQS, AATS...)."""
    if e.SRCTYP[isrc] == "BUOYLINE":
        e.AAFP[e.IHR_NDX, e.IYR_NDX, isrc] = e.AFP[isrc]


def maxdcalc_bl(e, isrc):
    """MAXDCALC (output.f, líneas 3397-3398): recupera AFP de la hora guardada (rama BUOYLINE)."""
    if e.SRCTYP[isrc] == "BUOYLINE":
        e.AFP[isrc] = e.AAFP[e.IHR_NDX, e.IYR_NDX, isrc]


def set_metdata_bl(e):
    """SET_METDATA (metext.f, líneas 1057-1059; tras el ajuste ROTANG y antes de URBSTAB =
    .FALSE.): guarda la temperatura del fichero de superficie para las BUOYLINE."""
    if e.L_BLSOURCE:
        e.BLTA = e.TA


def ltopg(e):
    """LTOPG (calc1.f): clase de estabilidad de Pasquill-Gifford a partir de OBULEN y SFCZ0
    (función LSTAB de CTDMPLUS, Golder 1972). Devuelve LSTAB."""
    el = e.OBULEN
    zr0 = e.SFCZ0
    z0 = zr0
    if z0 > 0.5:
        z0 = 0.5
    if z0 < 0.01:
        z0 = 0.01

    def xl(yy, xm, bb):
        return xm / (math.log(yy) - bb)

    if el < 0.0:
        xel = -el
        if xel <= xl(z0, -70.0, 4.35):
            lstab = 1
        elif xel <= xl(z0, -85.2, 0.502):
            lstab = 2
        elif xel <= xl(z0, -245.0, 0.050):
            lstab = 3
        else:
            lstab = 4
    else:
        if el >= xl(z0, -327.0, 0.627):
            lstab = 4
        elif el >= xl(z0, -70.0, 0.295):
            lstab = 5
        else:
            lstab = 6
    return lstab


def maxd_guardar_bl(e):
    """MAXDCONT_LOOP (aermod.f, líneas 7931-7935): guarda la primera rotación de los receptores
    y BL_RFLAG."""
    b = e.BUOY
    if b.L_BLSOURCE:
        b.XR_SCS_SAV[...] = b.XR_SCS
        b.YR_SCS_SAV[...] = b.YR_SCS
        b.BL_RFLAG_SAV[...] = b.BL_RFLAG


def maxd_receptor_bl(e, ir):
    """MAXDCONT_LOOP (aermod.f, líneas 7985-7990): pasa el receptor IR guardado a la posición 1
    para todos los grupos."""
    b = e.BUOY
    if b.L_BLSOURCE:
        n = b.NUMBLGRPS
        b.XR_SCS[1, 1:n + 1] = b.XR_SCS_SAV[ir, 1:n + 1]
        b.YR_SCS[1, 1:n + 1] = b.YR_SCS_SAV[ir, 1:n + 1]
        b.BL_RFLAG[1, 1:n + 1] = b.BL_RFLAG_SAV[ir, 1:n + 1]


def maxd_restaurar_bl(e):
    """MAXDCONT_LOOP (aermod.f, líneas 8195-8199): restaura las coordenadas de los receptores y
    BL_RFLAG."""
    b = e.BUOY
    if b.L_BLSOURCE:
        b.XR_SCS[...] = b.XR_SCS_SAV
        b.YR_SCS[...] = b.YR_SCS_SAV
        b.BL_RFLAG[...] = b.BL_RFLAG_SAV


def calc_bl(e):
    """Rama BUOYLINE de CALC (calc1.f, líneas 104-131), que se ejecuta una sola vez por hora
    (BLPROCESSED lo lleva quien llama): viento de referencia BL_UREF >= 1 m/s (aviso 471) y
    BL_CALC de cada grupo."""
    b = e.BUOY
    if e.UREF >= 1.0:
        b.BL_UREF = e.UREF
    else:
        b.BL_UREF = 1.0
        e.DUMMY = fc(fwrite("('on ',I8.8)", e.KURDAT)[0], 12)
        e.errhdl(e.PATH, "CALC", "W", "471", e.DUMMY)
    for kk in range(1, b.NUMBLGRPS + 1):
        bl_calc(e, kk)


# ------------------------------------------------------------------------------------------
# bline.f
# ------------------------------------------------------------------------------------------
def bl_calc(e, kk):
    """BL_CALC(KK): concentraciones horarias del grupo BUOYLINE KK en todos los receptores
    (integración adaptativa a lo largo de cada línea, sobreelevación de BLP y sigmas de
    Briggs/PG). Suma cada contribución con SUMVAL (o la guarda en CHI con ARM2)."""
    b = e.BUOY
    calculo_area, funciones_dispersion, resultados = _mods()
    iwpbl = 0
    ter1 = 0.0
    fbrg = 0.0
    isrc_sav = e.ISRC
    kst_sav = e.KST
    sfcz0_sav = e.SFCZ0
    jitct = 0

    b.CHIBL[:] = 0.0
    b.PARTCH = 0.0
    b.BLAVGLLEN = float(b.BLAVGINP_LLEN[kk])
    b.BLAVGBHGT = float(b.BLAVGINP_BHGT[kk])
    b.BLAVGBWID = float(b.BLAVGINP_BWID[kk])
    b.BLAVGLWID = float(b.BLAVGINP_LWID[kk])
    b.BLAVGBSEP = float(b.BLAVGINP_BSEP[kk])
    b.BLAVGFPRM = float(b.BLAVGINP_FPRM[kk])
    nblines = int(b.NBLINGRP[kk])

    # ---- opción urbana (todas las líneas del grupo son urbanas o ninguna)
    if b.L_BLURBAN[kk]:
        lnum = 0
        ksrc = 0
        if kk == 1:
            ksrc = e.ISRC
        elif kk >= 2:
            for i in range(1, e.NUMSRC + 1):
                if e.SRCTYP[i] == "BUOYLINE":
                    lnum += 1
                    if b.P_IBLPGRPNUM[lnum] == kk:
                        ksrc = i
                        break
        for i in range(1, e.NUMURB + 1):
            if e.IURBGRP[ksrc, i] == 1:
                e.IURB = i
                break
        iurb = e.IURB
        if e.STABLE or e.L_MORNINGTRANS[iurb]:
            e.URBSTAB = True
            e.ZI = max(float(e.ZIURB[iurb]), e.ZIMECH)
            e.SFCZ0 = float(e.URBZ0[iurb])
            if e.L_MORNINGTRANS[iurb]:
                e.OBULEN = float(e.URBOBULEN[iurb])
                bl_urbkst = ltopg(e)
                e.KST = bl_urbkst
            else:
                e.OBULEN = abs(float(e.URBOBULEN[iurb]))
                e.KST = 4
        else:
            e.URBSTAB = False
            e.ZI = e.ZIRUR
            e.OBULEN = e.RUROBULEN
    elif e.URBAN and not b.L_BLURBAN[kk]:
        e.URBSTAB = False
        e.ZI = e.ZIRUR
        e.OBULEN = e.RUROBULEN
    else:
        e.URBSTAB = False

    # ---- decaimiento
    if e.URBAN and e.POLLUT == "SO2" and b.L_BLURBAN[kk] and \
            ((e.ICSTAT[7] == 0 and e.ICSTAT[8] == 0) or e.DFAULT):
        decfac = e.DECOEF
    elif (e.POLLUT == "SO2" and b.L_BLURBAN[kk]) or e.DFAULT:
        decfac = 0.0
    else:
        decfac = e.DECOEF

    # ---- F' medio de las emisiones horarias (DO ISRC = 1, NUMSRC con ISRC de MAIN1)
    if b.HRLYBLCOUNT[kk] > 0:
        lnum = 0
        sumfprm = 0.0
        for isrc in range(1, e.NUMSRC + 1):
            e.ISRC = isrc
            if e.SRCTYP[isrc] == "BUOYLINE":
                lnum += 1
                lsrc = int(b.P_ISRCNUM[lnum])
                if e.QFLAG[lsrc] == "HOURLY" and b.P_IBLPGRPNUM[lnum] == kk:
                    sumfprm = sumfprm + float(e.AFP[lsrc])
        e.ISRC = e.NUMSRC + 1
        b.BLAVGFPRM = sumfprm / float(b.HRLYBLCOUNT[kk])

    # ---- distancia a la sobreelevación final neutra
    fbrg = float(nblines) * b.BLAVGFPRM / e.PI
    if fbrg <= 55.0:
        b.BL_XFINAL = 49.0 * _pow(fbrg, 0.625)
    else:
        b.BL_XFINAL = 120.72 * _pow(fbrg, 0.4)
    b.XMATCH = b.BL_XFINAL

    grp = b.P_IBLPGRPNUM
    nbt = b.NBLTOTAL
    for lnum in range(1, nbt + 1):
        if grp[lnum] == kk:
            b.DEL[lnum] = b.P_XEND_TR1[lnum] - b.P_XBEG_TR1[lnum]

    bl_theta, itheta = bl_rotate2(e, e.WDREF, e.NUMREC, nbt, kk)

    kst = int(e.KST)
    p = _WSPEXP[kst]
    wsst = b.BL_UREF * _pow(b.BLAVGBHGT / e.UREFHT, p)
    # (S sin definir en el original con KST <= 4; entonces no se usa)
    s = 0.0
    if kst > 4:
        s = 9.80616 * _DTHTA[kst - 4] / b.BLTA

    bl_ueff = bl_wsc(e, kst, wsst, s, p, nblines)
    bl_leng(e, bl_theta, bl_ueff, _AVFACT, nblines)

    if kst <= 4:
        b.BL_XFS = b.BL_XFB + b.BL_XFINAL
        for idist in range(2, 8):
            ri = float(idist)
            b.BL_XDIST[idist] = b.BL_XFS - (b.BL_XFS - b.BL_XFB) * (7.0 - ri) / 5.0
    else:
        unsrt = (16.0 * bl_ueff * bl_ueff / s) - (b.BL_XFB * b.BL_XFB / 3.0)
        if unsrt <= 0.0:
            b.BL_XFS = _pow(12.0 * b.BL_XFB * bl_ueff * bl_ueff / s, 0.333333)
        else:
            b.BL_XFS = 0.5 * (b.BL_XFB + _sqrt(unsrt))
        xfsxx = bl_ueff * e.PI / _sqrt(s)
        b.BL_XFS = min(b.BL_XFS, xfsxx)
        if b.BL_XFS <= b.BL_XFB:
            for idist in range(2, 8):
                b.BL_XDIST[idist] = b.BL_XFS
        else:
            for idist in range(2, 8):
                ri = float(idist)
                b.BL_XDIST[idist] = b.BL_XFS - (b.BL_XFS - b.BL_XFB) * (7.0 - ri) / 5.0

    bl_rise(e, bl_ueff, kst, s)

    # ---- concentraciones: bucle de líneas y receptores
    numrec = e.NUMREC
    numgrp = e.NUMGRP
    numtyp = e.NUMTYP
    zi = e.ZI
    emifac1 = float(e.EMIFAC[1])
    xr = b.XR_RCS.tolist()
    yr = b.YR_RCS.tolist()
    rflag = b.BL_RFLAG[:, kk].tolist()
    azflag = e.AZFLAG.tolist()
    azelev = e.AZELEV.tolist()
    bl_xfb = b.BL_XFB
    dh2 = float(b.DH[2])
    ter_kst = 1.0 - _TERAN[kst]
    ftsave = [0.0] * 130
    ibmin = ibmax = 0
    nsegm1 = 0
    indlsv = 0
    sum2 = 0.0
    ibmax1 = ih = igmax = 0

    for lnum in range(1, nbt + 1):
        if grp[lnum] != kk:
            continue
        isrc = int(b.P_ISRCNUM[lnum])
        e.ISRC = isrc
        dlmin = float(b.DEL[lnum]) / 128.0
        zlinebase = float(b.P_ELEV[lnum])
        zlinehs = float(b.P_BLHS[lnum])
        if e.BLPDBUG:
            from . import depura
            fplmht = zlinehs + float(b.DH[7])
            depura.wf(e, e.BLPUNT, "(1X,A12,4(2X,I2),14(F8.2),2X,2(F8.2),4X,I1,4(1X,F8.2))",
                      fx(e.SRCID[isrc], 12), e.IYEAR, e.IMONTH, e.IDAY, e.IHOUR, *[float(b.DH[k]) for k in range(1, 8)],
                      *[float(b.BL_XDIST[k]) for k in range(1, 8)], b.BL_XFB, b.BL_XFS, e.KST,
                      *[float(e.URBOBULEN[k]) for k in range(1, len(e.URBOBULEN))], e.OBULEN, zlinehs, fplmht)
        wsst = b.BL_UREF * _pow(zlinehs / e.UREFHT, p)
        calculo_area.setsrc(e)
        funciones_dispersion.emfact(e, e.QS)
        cuq = e.QTK * emifac1 / (float(_NSEGA[1] - 1) * wsst)
        sz0 = b.R0 * _SRT2DP
        zv = 1000.0 * bl_xvz(e, sz0, kst)
        sy0 = sz0 / 2.0
        yv = 1000.0 * bl_xvy(e, sy0, kst)
        xs = b.XS_RCS[lnum].tolist()
        ys = b.YS_RCS[lnum].tolist()
        xb = xs[1]
        yb = ys[1]
        xe = xs[129]
        ye = ys[129]
        xmaxl = max(xb, xe)
        xminl = min(xb, xe)
        ymaxl = max(yb, ye)
        yminl = min(yb, ye)
        dxel = xe - xb
        dyel = ye - yb
        flat = bool(e.L_FLATSRC[isrc])

        for irec in range(1, numrec + 1):
            e.IREC = irec
            summ = 0.0
            b.PARTCH = 0.0
            nseg = 0
            ncontrib = 0
            xrecep = xr[irec]
            zflag = azflag[irec]
            e.ZFLAG = zflag
            if flat:
                tht = zflag
            else:
                tht = azelev[irec] - zlinebase + zflag
            # receptor a barlovento de la línea
            if xrecep <= xminl:
                continue
            # receptor dentro del rectángulo de las líneas
            if rflag[irec]:
                continue
            yrecep = yr[irec]
            iwosig = 0
            xrmxkm = (xrecep - xminl) / 1000.0
            syc = bl_sigmay(e, xrmxkm, kst)
            ylow = yminl - 4.0 * syc
            yhigh = ymaxl + 4.0 * syc
            if yrecep < ylow or yrecep > yhigh:
                continue
            ylow = ylow + dlmin
            yhigh = yhigh - dlmin
            if yrecep < ylow or yrecep > yhigh:
                continue
            idw = 1
            if yrecep < yminl or yrecep > ymaxl:
                idw = 0
            if xrecep < xmaxl:
                if itheta % 90 != 0:
                    em = _div(dyel, dxel)
                    bb = ye - em * xe
                    if xrecep < _div(yrecep - bb, em):
                        ncontrib = 999
            nseg0 = _NSEGA[1]
            nnew = nseg0
            iter_ = 0
            indl = 1
            idelta = 128 // (nseg0 - 1)
            z2 = None                # BL_INTRSE(XR_RCS(IREC)): solo depende del receptor
            sumar = False
            lab = 498
            while True:
                if lab == 498:
                    nseg = nseg + nnew
                    for _iseg in range(nnew):
                        ftsave[indl] = 0.0
                        xsi = xs[indl]
                        if not (xsi >= xrecep):
                            downx = xrecep - xsi
                            crossy = yrecep - ys[indl]
                            virtxz = downx + zv
                            virtxy = downx + yv
                            vxykm = virtxy / 1000.0
                            vxzkm = virtxz / 1000.0
                            if not (vxykm < 0.0 or vxzkm < 0.0):
                                sigy, sigz = bl_dbtsig(e, vxzkm, vxykm, kst)
                                if not (4.0 * sigy < abs(crossy)):
                                    if abs(crossy) < sigy:
                                        iwosig = 1
                                    # BL_ZRISE(LNUM, INDL, IREC, Z)
                                    xi = bl_xfb - xsi
                                    xi = max(xi, 0.0)
                                    xi = min(xi, bl_xfb)
                                    zxfb = dh2 * (1.0 - _div(bl_xfb - xi, bl_xfb))
                                    if z2 is None:
                                        z2 = bl_intrse(e, xrecep)
                                    z = zxfb + z2 - dh2
                                    ter1 = ter_kst
                                    hnt = z + zlinehs
                                    terran = ter1 * min(hnt, tht)
                                    h = hnt - terran
                                    if not (h > zi and kst <= 4):
                                        ft = bl_gauss(e, kst, zi, crossy, sigy, sigz, h)
                                        deltat = downx / wsst
                                        ftsave[indl] = ft * (1.0 - deltat * decfac)
                                        ncontrib += 1
                        indl = indl + idelta
                    if nnew != nseg0:
                        lab = 714
                        continue
                    # primera estimación
                    indl = 1
                    nsegm1 = nseg0 - 1
                    summ = (ftsave[1] + ftsave[129]) / 2.0
                    for _iseg2 in range(2, nsegm1 + 1):
                        indl = indl + idelta
                        summ = summ + ftsave[indl]
                    if summ <= 0.0 and idw != 1:
                        break
                    lab = 713
                elif lab == 713:
                    iter_ += 1
                    if iter_ >= 31:
                        raise ErrorEjecucion("BL_CALC: NSEGM1**ITER desborda el entero (ITER = %d)"
                                             % iter_)
                    idiv = min(iter_, 2)
                    idelta = idelta // idiv
                    indl = 1 + idelta // 2
                    indlsv = indl
                    nnew = int(float(nsegm1 ** iter_) + 0.1)
                    lab = 759 if nnew > 64 else 498
                elif lab == 714:
                    indlln = 129 - idelta // 2
                    sum2 = ftsave[indlsv] + ftsave[indlln]
                    if nnew > 2:
                        indl = indlsv
                        i2 = nnew - 1
                        for _iseg3 in range(2, i2 + 1):
                            indl = indl + idelta
                            sum2 = sum2 + ftsave[indl]
                    sum2 = summ / 2.0 + sum2 / (2.0 ** iter_)
                    if idw == 1 and iwosig != 1:
                        lab = 758
                        continue
                    diff = abs(sum2 - summ)
                    if _div(diff * cuq * 1.0e6, emifac1) < 0.1:
                        lab = 720
                        continue
                    corr = _div(diff, sum2)
                    if corr < _BLCRIT:
                        lab = 720
                        continue
                    lab = 758
                elif lab == 758:
                    summ = sum2
                    lab = 713
                elif lab == 759:
                    ibmin, ibmax, iwpbl = bl_sort(e, ftsave, ibmin, ibmax, iwpbl)
                    if iwpbl != 999:
                        lab = 4949
                        continue
                    iwpbl = 0
                    b.PARTCH = 0.0
                    break
                elif lab == 4949:
                    ibmax1 = ibmax - 1
                    ih = 0
                    igmax = 1
                    lab = 939
                elif lab == 939:
                    sum2 = 0.0
                    igmax1 = igmax + 1
                    for ig in range(ibmin, ibmax1 + 1):
                        xseg1 = xs[ig]
                        xdiff = xs[ig + 1] - xseg1
                        yseg1 = ys[ig]
                        ydiff = ys[ig + 1] - yseg1
                        for igsub in range(1, igmax + 1):
                            weight = float(igsub) / float(igmax1)
                            xcln = xseg1 + weight * xdiff
                            ycln = yseg1 + weight * ydiff
                            downx = xrecep - xcln
                            crossy = yrecep - ycln
                            virtxz = downx + zv
                            virtxy = downx + yv
                            vxykm = virtxy / 1000.0
                            vxzkm = virtxz / 1000.0
                            if vxykm < 0.0 or vxzkm < 0.0:
                                continue
                            sigy, sigz = bl_dbtsig(e, vxzkm, vxykm, kst)
                            # BL_ZRISE(LNUM, IG, IREC, Z)
                            xi = bl_xfb - xseg1
                            xi = max(xi, 0.0)
                            xi = min(xi, bl_xfb)
                            zxfb = dh2 * (1.0 - _div(bl_xfb - xi, bl_xfb))
                            if z2 is None:
                                z2 = bl_intrse(e, xrecep)
                            z = zxfb + z2 - dh2
                            hnt = z + zlinehs
                            terran = ter1 * min(hnt, tht)
                            h = hnt - terran
                            ft = bl_gauss(e, kst, zi, crossy, sigy, sigz, h)
                            deltat = downx / wsst
                            ft = ft * (1.0 - deltat * decfac)
                            sum2 = sum2 + ft
                            ncontrib += 1
                    sum2 = summ / 2.0 + sum2 / (2.0 ** iter_)
                    diff = abs(sum2 - summ)
                    if _div(diff * cuq * 1.0e6, emifac1) < 0.1:
                        lab = 720
                        continue
                    corr = _div(diff, sum2)
                    if corr < _BLCRIT:
                        lab = 720
                        continue
                    summ = sum2
                    iter_ += 1
                    if iter_ >= _MAXIT:
                        # sin convergencia: solo se acumula en CHIBL (no pasa por SUMVAL)
                        summ = sum2
                        b.PARTCH = cuq * summ
                        b.CHIBL[irec] = b.CHIBL[irec] + b.PARTCH
                        if e.DEBUG:
                            from . import depura
                            depura.wf(e, e.DBGUNT, "(/,5X,'Buoyant Line iteration fails to ',' converge for "
                                      "receptor',I6,', conc. =',F13.6)", irec, float(b.CHIBL[irec]))
                            jitct += 1
                            if jitct % 100 == 0:
                                depura.wf(e, e.DBGUNT, "(/,5X,'Buoyant Line iterations for',' all receptors "
                                          "fails for ',I8,'th time' )", jitct)
                        break
                    ih += 1
                    igmax = 2 ** ih
                    lab = 939
                elif lab == 720:
                    summ = sum2
                    if ncontrib < 2:
                        lab = 713
                        continue
                    sumar = True
                    break
            if not sumar:
                continue

            partch = cuq * summ
            b.PARTCH = partch
            b.CHIBL[irec] = b.CHIBL[irec] + partch
            e.HRVAL[1:numtyp + 1] = partch
            if e.ARM2:
                for ityp in range(1, numtyp + 1):
                    e.CHI[irec, isrc, ityp] = e.HRVAL[ityp]
                e.ITYP = numtyp + 1
                e.HRVAL[:] = 0.0
            if e.EVONLY:
                raise NoTraducido("EVENT")
            for igrp in range(1, numgrp + 1):
                e.IGRP = igrp
                resultados.sumval(e)
            e.IGRP = numgrp + 1
            if e.EVAL[isrc]:
                raise NoTraducido("EVALFILE")
            e.HRVAL[:] = 0.0
        e.IREC = numrec + 1

    # ---- se restauran ISRC, KST, SFCZ0 (y ZI, OBULEN si el grupo era urbano estable)
    if e.URBSTAB:
        e.ISRC = isrc_sav
        e.KST = kst_sav
        e.ZI = e.ZIRUR
        e.SFCZ0 = sfcz0_sav
        e.OBULEN = e.RUROBULEN
    else:
        e.ISRC = isrc_sav
        e.KST = kst_sav
        e.SFCZ0 = sfcz0_sav


def bl_dbtsig(e, xz, xy, istab):
    """BL_DBTSIG: sigma-y y sigma-z (m) de Briggs/PG a las distancias virtuales XZ y XY (km).
    Devuelve (SY, SZ)."""
    th = 0.0
    sz = 0.0
    if istab == 1:
        th = (24.167 - 2.5334 * _log(xy)) / 57.2958
        if xz > 3.11:
            sz = 5000.0
        else:
            idx = 8
            for i in range(1, 8):
                if xz >= _XA[i]:
                    idx = i
                    break
            sz = _SG_AA[idx] * xz ** _SG_BA[idx]
    elif istab == 2:
        th = (18.333 - 1.8096 * _log(xy)) / 57.2958
        if xz > 35.0:
            sz = 5000.0
        else:
            idx = 3
            for i in range(1, 3):
                if xz >= _XB[i]:
                    idx = i
                    break
            sz = _SG_AB[idx] * xz ** _SG_BB[idx]
            if sz > 5000.0:
                sz = 5000.0
    elif istab == 3:
        th = (12.5 - 1.0857 * _log(xy)) / 57.2958
        sz = 61.141 * xz ** 0.91465
        if sz > 5000.0:
            sz = 5000.0
    elif istab == 4:
        th = (8.3333 - 0.72382 * _log(xy)) / 57.2958
        idx = 6
        for i in range(1, 6):
            if xz >= _XD[i]:
                idx = i
                break
        sz = _SG_AD[idx] * xz ** _SG_BD[idx]
        if sz > 5000.0:
            sz = 5000.0
    elif istab == 5:
        th = (6.25 - 0.54287 * _log(xy)) / 57.2958
        idx = 9
        for i in range(1, 9):
            if xz >= _XE[i]:
                idx = i
                break
        sz = _SG_AE[idx] * xz ** _SG_BE[idx]
        if sz > 5000.0:
            sz = 5000.0
    elif istab == 6:
        th = (4.1667 - 0.36191 * _log(xy)) / 57.2958
        idx = 10
        for i in range(1, 10):
            if xz >= _XF[i]:
                idx = i
                break
        sz = _SG_AF[idx] * xz ** _SG_BF[idx]
        if sz > 5000.0:
            sz = 5000.0
    sy = _sy_de_th(xy, th)
    return sy, sz


def bl_sigmay(e, xkm, istab):
    """BL_SIGMAY: sigma-y (m) a XKM km. (En la estabilidad D el original usa 8.3333 en simple
    precisión y 0.72385, no 0.72382 como BL_DBTSIG.)"""
    th = 0.0
    if istab == 1:
        th = (24.167 - 2.5334 * _log(xkm)) / 57.2958
    elif istab == 2:
        th = (18.333 - 1.8096 * _log(xkm)) / 57.2958
    elif istab == 3:
        th = (12.5 - 1.0857 * _log(xkm)) / 57.2958
    elif istab == 4:
        th = (_R4_8P3333 - 0.72385 * _log(xkm)) / 57.2958
    elif istab == 5:
        th = (6.25 - 0.54287 * _log(xkm)) / 57.2958
    elif istab == 6:
        th = (4.1667 - 0.36191 * _log(xkm)) / 57.2958
    return _sy_de_th(xkm, th)


def bl_rise(e, u, istab, s):
    """BL_RISE: sobreelevación de la línea (DH(2..7)) en las distancias BL_XDIST(2..7), con el
    viento efectivo U y, en estable, el parámetro S."""
    b = e.BUOY
    leff, r0, ld = b.LEFF, b.R0, b.LD
    fprmxnb, xfb, xfs = b.FPRMXNB, b.BL_XFB, b.BL_XFS
    a = 1.5915494 * leff + 5.0 * r0
    bb = r0 * (5.3051648 * ld + 8.333333 * r0)
    for idist in range(2, 8):
        x = float(b.BL_XDIST[idist])
        if istab <= 4 or x < xfs:
            if abs(x - xfb) < 1.0e-10:
                t = x / u
                c = -0.4420971 * _div(fprmxnb, xfb) * (t * t * t)
                z = bl_cubic(e, a, bb, c)
                b.DH[idist] = z
            else:
                c = -1.3262912 * fprmxnb * (xfb * xfb / 3.0 + x * x - xfb * x) / (u * u * u)
                z = bl_cubic(e, a, bb, c)
                b.DH[idist] = z
        else:
            c = -5.3051648 * fprmxnb / (u * s)
            z = bl_cubic(e, a, bb, c)
            b.DH[idist] = z


def bl_zrise(e, il, is_, ir):
    """BL_ZRISE(IL, IS, IR): altura del penacho del segmento IS de la línea IL en el receptor IR.
    (BL_CALC hace el mismo cálculo en línea, con BL_INTRSE evaluado una vez por receptor.)"""
    b = e.BUOY
    z1 = float(b.DH[2])
    xi = b.BL_XFB - float(b.XS_RCS[il, is_])
    xi = max(xi, 0.0)
    xi = min(xi, b.BL_XFB)
    zxfb = z1 * (1.0 - _div(b.BL_XFB - xi, b.BL_XFB))
    z2 = bl_intrse(e, float(b.XR_RCS[ir]))
    return zxfb + z2 - z1


def bl_intrse(e, x):
    """BL_INTRSE: interpola la sobreelevación del elemento más alto a la distancia X entre los
    puntos BL_XDIST(1..7) (DH(1) = BL_XDIST(1) = 0, nunca se asignan). Si X = BL_XDIST(7) el
    índice queda sin definir en el original: se usa el de la llamada anterior."""
    b = e.BUOY
    xd, dh = b.BL_XDIST, b.DH
    if x > xd[7]:
        return float(dh[7])
    ndex = 0
    for idist in range(2, 8):
        if x < xd[idist]:
            ndex = idist
            break
    if ndex == 0:
        ndex = b._NDEX
    else:
        b._NDEX = ndex
    ndex1 = ndex - 1
    dn, dn1 = float(dh[ndex]), float(dh[ndex1])
    xn, xn1 = float(xd[ndex]), float(xd[ndex1])
    return dn - _div((dn - dn1) * (xn - x), xn - xn1)


def bl_gauss(e, istab, dpbl, crossy, sigy, sigz, h):
    """BL_GAUSS: término gaussiano del segmento (con reflexiones en la capa de mezcla por serie
    de Fourier, o distribución vertical uniforme). Devuelve FT."""
    td1 = 3.1415927 * sigy * sigz
    ypsig = _div(crossy, sigy)
    expyp = 0.5 * ypsig * ypsig
    if expyp > 50.0:
        return 0.0
    f = math.exp(-expyp)
    if istab >= 5 or dpbl > 5000.0:
        # 451: sin términos de reflexión
        hpsig = _div(h, sigz)
        exphp = 0.5 * hpsig * hpsig
        if exphp > 50.0:
            f1 = 0.0
        else:
            f1 = math.exp(-exphp)
        return _div(f * f1, td1)
    if sigz > 1.6 * dpbl:
        # 460: distribución vertical uniforme
        return _div(f, 2.5066283 * sigy * dpbl)
    f1 = 1.0
    t = _div(sigz, dpbl)
    t = t * t
    h2 = _div(h, dpbl)
    if t < 0.6:
        arg = _div(2.0 * (1.0 - h2), t)
        if arg < _TMAX:
            if arg < _TMIN:
                f1 = f1 + 1.0 - arg
            if arg >= _TMIN:
                f1 = f1 + _exp(-arg)
            arg = _div(2.0 * (1.0 + h2), t)
            if arg < _TMAX:
                f1 = f1 + _exp(-arg)
                arg = _div(4.0 * (2.0 - h2), t)
                if arg < _TMAX:
                    f1 = f1 + _exp(-arg)
                    arg = _div(4.0 * (2.0 + h2), t)
                    if arg < _TMAX:
                        f1 = f1 + _exp(-arg)
        arg = _div(-0.5 * h2 * h2, t)
        if arg < -90.0:
            f1 = 0.0
        if arg >= -90.0:
            f1 = _div(0.797885 * f1 * math.exp(arg), sigz)
        if f1 < _EPSIL:
            f1 = 0.0
    else:
        arg = 4.934802 * t
        if arg < _TMAX:
            f1 = f1 + 2.0 * math.exp(-arg) * math.cos(3.141593 * h2)
            arg = 19.739209 * t
            if arg < _TMAX:
                f1 = f1 + 2.0 * math.exp(-arg) * math.cos(6.283185 * h2)
        f1 = _div(f1, dpbl)
        if f1 < _EPSIL:
            f1 = 0.0
    f1 = 1.25331414 * sigz * f1
    # 445
    return _div(f * f1, td1)


def bl_xvz(e, szo, istab):
    """BL_XVZ: distancia virtual (km) que da el sigma-z inicial SZO."""
    v = 0.0
    if istab == 1:
        idx = 8
        for i in range(1, 8):
            if szo <= _SA[i]:
                idx = i
                break
        v = _pow(szo / _VZ_AA[idx], _VZ_CA[idx])
    elif istab == 2:
        idx = 3
        for i in range(1, 3):
            if szo <= _SB[i]:
                idx = i
                break
        v = _pow(szo / _VZ_AB[idx], _VZ_CB[idx])
    elif istab == 3:
        v = _pow(szo / 61.141, 1.0933)
    elif istab == 4:
        idx = 6
        for i in range(1, 6):
            if szo <= _SD[i]:
                idx = i
                break
        v = _pow(szo / _VZ_AD[idx], _VZ_CD[idx])
    elif istab == 5:
        idx = 9
        for i in range(1, 9):
            if szo <= _SE[i]:
                idx = i
                break
        v = _pow(szo / _VZ_AE[idx], _VZ_CE[idx])
    elif istab == 6:
        idx = 10
        for i in range(1, 10):
            if szo <= _SF[i]:
                idx = i
                break
        v = _pow(szo / _VZ_AF[idx], _VZ_CF[idx])
    return v


def bl_xvy(e, syo, istab):
    """BL_XVY: distancia virtual (km) que da el sigma-y inicial SYO."""
    v = 0.0
    if istab == 1:
        v = _pow(syo / 213.0, 1.1148)
    elif istab == 2:
        v = _pow(syo / 155.0, 1.097)
    elif istab == 3:
        v = _pow(syo / 103.0, 1.092)
    elif istab == 4:
        v = _pow(syo / 68.0, 1.076)
    elif istab == 5:
        v = _pow(syo / 50.0, 1.086)
    elif istab == 6:
        v = _pow(syo / 33.5, 1.083)
    return v


def bl_wsc(e, istab, um, s, p, nbl):
    """BL_WSC: viento efectivo U de la ecuación de sobreelevación de la línea, ajustada en la
    distancia final XMATCH (UM = viento a la altura de los edificios). Devuelve U."""
    b = e.BUOY
    if istab <= 4:
        p3 = 3.0 * p
        ep = 2.0 + p3
        epi = 1.0 / ep
        t1 = _pow(_div(ep * ep * float(nbl) * b.BLAVGFPRM * _pow(b.BLAVGBHGT, p3),
                       2.4 * (2.0 + p) * b.BLAVGLLEN * (um * um * um)), epi)
        z = t1 * _pow(b.XMATCH, 2.0 * epi)
        u = _pow(_div(float(nbl) * b.BLAVGFPRM, 1.2 * b.BLAVGLLEN) * _div(b.XMATCH, z) *
                 _div(b.XMATCH, z), 0.333333)
        u = max(u, um)
    else:
        p2 = 2.0 + p
        z = _pow(_div(p2 * _pow(b.BLAVGBHGT, p) * float(nbl) * b.BLAVGFPRM,
                      0.6 * b.BLAVGLLEN * um * s), 1.0 / p2)
        u = _div(3.3333333 * float(nbl) * b.BLAVGFPRM, b.BLAVGLLEN * s * z * z)
        u = max(u, um)
    return u


def bl_leng(e, theta, u, avfactor, nbl):
    """BL_LENG: distancia de flotabilidad plena BL_XFB, longitud efectiva LEFF, longitud de
    estela LD y radio de borde R0 (variables del módulo) para el ángulo THETA del flujo."""
    b = e.BUOY
    b.FPRMXNB = float(nbl) * b.BLAVGFPRM
    thrad = theta * _RAD
    sint = abs(math.sin(thrad))
    cost = abs(math.cos(thrad))
    dxm = b.BLAVGBSEP + b.BLAVGBWID
    b.BL_XFB = b.BLAVGLLEN * cost + float(nbl - 1) * dxm * sint
    leff1 = b.BLAVGLLEN * sint
    if nbl == 1:
        leffv = b.BLAVGLWID
        b.FPRMXNB = b.BLAVGFPRM
        b.BL_XFB = b.BL_XFB + b.BLAVGLWID * sint
    else:
        dxm833 = 0.8333333 * dxm
        t1 = _div(2.2619467 * (u * u * u), b.BLAVGFPRM) * dxm833 * dxm833 * \
            (dxm833 + 1.5915494 * b.BLAVGLWID)
        xi = _pow(t1 * b.BLAVGLLEN, 0.333333)
        if xi > b.BLAVGLLEN:
            xi = b.BLAVGLLEN / 2.0 + _sqrt(12.0 * t1 - 3.0 * b.BLAVGLLEN * b.BLAVGLLEN) / 6.0
            leffv = _div(b.FPRMXNB * (b.BLAVGLLEN * b.BLAVGLLEN / 3.0 + xi * (xi - b.BLAVGLLEN)),
                         1.2 * (u * u * u) * dxm833 * dxm833) - 0.6283185 * dxm833
        else:
            t = xi / u
            leffv = _div(b.FPRMXNB, 3.6 * b.BLAVGLLEN * dxm833 * dxm833) * (t * t * t) - \
                0.6283185 * dxm833
    b.LEFF = leff1 + leffv * cost
    b.LD = b.LEFF * sint
    b.R0 = min(b.BLAVGBHGT, b.LD) / avfactor


def bl_sort(e, ftsave, ibmin, ibmax, iwpbl):
    """BL_SORT: tramo de segmentos que contribuye (FTSAVE no nulo) alrededor del primero que se
    encuentra. Devuelve (IBMIN, IBMAX, IWPBL); IWPBL = 999 si ningún segmento contribuye (y
    entonces IBMIN/IBMAX no cambian)."""
    isafe = 0
    ib = 0
    if ftsave[129] != 0.0:
        ib = 129
    if ftsave[1] != 0.0:
        ib = 1
    if ib == 0:
        hallado = False
        for ilevel in range(1, 8):
            neachl = 2 ** (ilevel - 1)
            incr = 2 ** (8 - ilevel)
            indexi = 1 + incr // 2
            for _nc in range(neachl):
                if not (ftsave[indexi] == 0.0):
                    ib = indexi
                    hallado = True
                    break
                indexi = indexi + incr
            if hallado:
                break
        if ib == 0:
            return ibmin, ibmax, 999
    ibmin = ib - 1
    ibmax = ib + 1
    ibmin = max(ibmin, 1)
    ibmax = min(ibmax, 129)
    while True:
        incrm = 0
        incrp = 0
        if ftsave[ibmin] != 0.0:
            incrm = 1
        if ibmin == 1:
            incrm = 0
        if ftsave[ibmax] != 0.0:
            incrp = 1
        if ibmax == 129:
            incrp = 0
        ibmin = ibmin - incrm
        ibmax = ibmax + incrp
        if incrm == 0 and incrp == 0:
            break
        isafe += 1
        if isafe > 129:
            break
    return ibmin, ibmax, iwpbl


def bl_cubic(e, a, b, c):
    """BL_CUBIC: una raíz de Z**3 + A*Z**2 + B*Z + C = 0 (exponentes 0.333333, como el
    original). Devuelve Z."""
    one = 1.0
    a3 = a / 3.0
    ap = b - a * a3
    bp = 2.0 * (a3 * a3 * a3) - a3 * b + c
    ap3 = ap / 3.0
    bp2 = bp / 2.0
    troot = bp2 * bp2 + ap3 * ap3 * ap3
    if troot > 0.0:
        tr = math.sqrt(troot)
        app = _pow(-bp2 + tr, 0.333333)
        bsv = -bp2 - tr
        if bsv == 0.0:
            z = app - a3
        else:
            sgn = dsign(one, bsv)
            bpp = sgn * _pow(abs(bsv), 0.333333)
            z = app + bpp - a3
    else:
        cm = 2.0 * _sqrt(-ap3)
        alpha = _acos(_div(bp, ap3 * cm)) / 3.0
        z = cm * math.cos(alpha) - a3
    return z


def bl_rotate2(e, wd1, nrecep, nbl, kk):
    """BL_ROTATE2: segmentos de las líneas del grupo KK y receptores, trasladados y girados para
    que el eje y quede paralelo al viento de la hora (WD1). Devuelve (THETA, ITHETA)."""
    b = e.BUOY
    yn = 0.0
    xn = 0.0
    theta = 360.0 - (wd1 + float(b.TCOR[kk]))
    if theta < 0.0:
        theta = 360.0 + theta
    theta = math.fmod(theta, 360.0)
    itheta = nint(theta)
    costheta = math.cos(theta / _DEG_PER_RAD)
    sintheta = math.sin(theta / _DEG_PER_RAD)
    grp = b.P_IBLPGRPNUM
    for lnum in range(1, nbl + 1):
        if grp[lnum] == kk:
            dxx = float(b.DEL[lnum]) / 128.0
            v = float(b.P_XBEG_TR1[lnum])
            fila = [0.0, v]
            for _j in range(2, 130):
                v = v + dxx
                fila.append(v)
            b.XS_SCS[lnum, :] = fila
    # IL: primera y última línea del grupo KK (las líneas van ordenadas por grupo)
    if kk == 1:
        il = (None, 1, 1, int(b.NBLINGRP[kk]), int(b.NBLINGRP[kk]))
    else:
        il12 = 1
        il34 = int(b.NBLINGRP[1])
        for j in range(2, kk + 1):
            il12 = il12 + int(b.NBLINGRP[j - 1])
            il34 = il34 + int(b.NBLINGRP[j])
        il = (None, il12, il12, il34, il34)
    hallado = False
    for lnum in range(1, nbl + 1):
        if grp[lnum] == kk:
            for i in range(1, 5):
                if theta >= _TCHK[i]:
                    continue
                iline = il[i]
                isegn = _ISEG[i]
                xn = float(b.XS_SCS[iline, isegn])
                yn = float(b.YS_SCS[iline])
                hallado = True
                break
            if hallado:
                break
    for lnum in range(1, nbl + 1):
        if grp[lnum] == kk:
            b.XS_RCS[lnum, 1:130] = b.XS_SCS[lnum, 1:130] - xn
            b.YS_RCS[lnum, 1:130] = float(b.YS_SCS[lnum]) - yn
    n = nrecep
    b.XR_RCS[1:n + 1] = b.XR_SCS[1:n + 1, kk] - xn
    b.YR_RCS[1:n + 1] = b.YR_SCS[1:n + 1, kk] - yn
    for lnum in range(1, nbl + 1):
        if grp[lnum] == kk:
            xsave = b.XS_RCS[lnum, 1:130].copy()
            ysave = b.YS_RCS[lnum, 1:130].copy()
            b.XS_RCS[lnum, 1:130] = xsave * costheta + ysave * sintheta
            b.YS_RCS[lnum, 1:130] = ysave * costheta - xsave * sintheta
    xsave = b.XR_RCS[1:n + 1].copy()
    ysave = b.YR_RCS[1:n + 1].copy()
    b.XR_RCS[1:n + 1] = xsave * costheta + ysave * sintheta
    b.YR_RCS[1:n + 1] = ysave * costheta - xsave * sintheta
    return theta, itheta
