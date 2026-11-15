# -*- coding: utf-8 -*-
"""Traducción de AERMOD 26135 (US EPA, dominio público): lectura de la meteorología (metext.f)."""
import math

from . import perfiles
from .estado import NoTraducido
from .formato import dsign, fwrite, fx, lread


def pflini(e):
    """PFLINI: inicializa las variables del perfil."""
    e.PATH = "MX"
    e.IFLAG[:] = 0
    for n in ("PFLHT", "PFLWS", "PFLWD", "PFLTA", "PFLSA", "PFLSW", "PFLSV", "PFLTG", "PFLTGZ"):
        getattr(e, n)[:] = -99.0


def pflcnv(e, level):
    """PFLCNV: convierte y controla un nivel del perfil (sigma-v desde sigma-theta, K, mínimos)."""
    m = "PFLCNV"
    e.DUMMY = fwrite("(I10.10)", e.FULLDATE)[0][:12]
    t = e.TURBOPTS
    if e.PFLSA[level] < 99.0 and (t[1] or (t[2] and e.STABLE) or (t[3] and e.UNSTAB) or t[4]
                                  or (t[6] and e.STABLE) or (t[8] and e.UNSTAB)):
        e.PFLSA[level] = 99.0
        if not e.RESET_SA:
            e.RESET_SA = True
    if e.PFLSW[level] < 99.0 and (t[1] or (t[2] and e.STABLE) or (t[3] and e.UNSTAB) or t[5]
                                  or (t[7] and e.STABLE) or (t[9] and e.UNSTAB)):
        e.PFLSW[level] = 99.0
        if not e.RESET_SW:
            e.RESET_SW = True
    if e.PFLWS[level] < 0.0 or e.PFLWS[level] > 90.0:
        e.PFLWS[level] = -99.0
    if 0.0 < e.PFLWS[level] <= 90.0 and e.PFLWD[level] == 0.0:
        e.PFLWD[level] = 360.0
    if e.PFLWD[level] > 900.0 or e.PFLWD[level] < 0.0:
        e.PFLWD[level] = -999.0
    if e.PFLWS[level] == 0.0 and e.PFLWD[level] == 0.0:
        e.PFLWS[level] = -99.0
        e.PFLWD[level] = -999.0
    if e.PFLWS[level] > 0.0 and 0.0 <= e.PFLSA[level] < 99.0:
        sigrad = e.PFLSA[level] * e.DTORAD
        epsil = math.sin(sigrad) * (1.0 - e.GSIGV * sigrad)
        usubv = e.PFLWS[level] * math.sqrt(1.0 - epsil * epsil)
        e.PFLSV[level] = sigrad * usubv
        e.PFLSV[level] = max(e.SVMIN, e.PFLSV[level])
        e.L_GOT_SIGA = True
        e._N_GOT_SIGA = getattr(e, "_N_GOT_SIGA", 0) + 1
    else:
        e.PFLSV[level] = -99.0
    if 0.0 < e.PFLSW[level] < 90.0:
        e.L_GOT_SIGW = True
        e._N_GOT_SIGW = getattr(e, "_N_GOT_SIGW", 0) + 1
    na = getattr(e, "_N_GOT_SIGA", 0)
    nw = getattr(e, "_N_GOT_SIGW", 0)
    ga, gw = e.L_GOT_SIGA, e.L_GOT_SIGW
    if e.L_ADJUSTAR and e.DFAULT:
        if ga and gw:
            if na == 1 and nw == 1:
                e.errhdl(e.PATH, m, "E", "401", "SigA & SigW")
                e.FATAL = True
        elif ga and not gw:
            if na == 1:
                e.errhdl(e.PATH, m, "E", "401", "SigA Data")
                e.FATAL = True
        elif not ga and gw:
            if nw == 1:
                e.errhdl(e.PATH, m, "E", "401", "SigW Data")
                e.FATAL = True
    elif e.L_ADJUSTAR:
        if ga and gw:
            if na == 1 and nw == 1:
                e.errhdl(e.PATH, m, "W", "401", "SigA & SigW")
                e.MODOPS[1] = "NonDFAULT"
                e.MODOPS[26] = "SigA&SigW"
        elif ga and not gw:
            if na == 1:
                e.errhdl(e.PATH, m, "W", "401", "SigA Data")
                e.MODOPS[1] = "NonDFAULT"
                e.MODOPS[26] = "SigA Data"
        elif not ga and gw:
            if nw == 1:
                e.errhdl(e.PATH, m, "W", "401", "SigW Data")
                e.MODOPS[1] = "NonDFAULT"
                e.MODOPS[26] = "SigW Data"
        if not getattr(e, "_L_TURB_WARN", False) and (ga or gw):
            e._L_TURB_WARN = True
            e._N_TURB_WARN = getattr(e, "_N_TURB_WARN", 0) + 1
            if e._N_TURB_WARN == 1:
                e.errhdl(e.PATH, m, "W", "402", "Option")
    else:
        if ga and gw:
            if na == 1 and nw == 1:
                e.errhdl(e.PATH, m, "W", "403", "SigA & SigW")
                e.MODOPS[26] = "SigA&SigW"
        elif ga and not gw:
            if na == 1:
                e.errhdl(e.PATH, m, "W", "403", "SigA Data")
                e.MODOPS[26] = "SigA Data"
        elif not ga and gw:
            if nw == 1:
                e.errhdl(e.PATH, m, "W", "403", "SigW Data")
                e.MODOPS[26] = "SigW Data"
    if -90.0 < e.PFLTA[level] < 90.0:
        e.PFLTA[level] = e.PFLTA[level] + e.DCTODK
    else:
        e.PFLTA[level] = -999.0
    if e.PFLSW[level] < 0.0 or e.PFLSW[level] > 90.0:
        e.PFLSW[level] = -99.0
    else:
        e.PFLSW[level] = max(e.SWMIN, e.PFLSW[level])


# =============================================================================== METEXT
_TIPOS_SFC = ("i", "i", "i", "i", "i", "f", "f", "f", "f", "f", "f", "f", "f", "f", "f", "f", "f", "f", "f",
              "f", "i", "f", "f", "f", "i")
_NOMBRES_SFC = ("IYEAR", "IMONTH", "IDAY", "_IJDAY", "IHOUR", "SFCHF", "USTAR", "WSTAR", "VPTGZI", "ZICONV",
                "ZIMECH", "OBULEN", "SFCZ0", "BOWEN", "ALBEDO", "UREF", "WDREF", "UREFHT", "TA", "TREFHT",
                "IPCODE", "PRATE", "RH", "SFCP", "NCLOUD")
_TIPOS_PFL = ("i", "i", "i", "i", "f", "i", "f", "f", "f", "f", "f")
_BANDERAS = ("NAD", "ADJ", "MIFF-Mod", "MMIF-OS", "PROG-Mod", "PROG-OS")
_IDYMAX = (0, 31, 29, 31, 30, 31, 30, 31, 31, 30, 31, 30, 31)


class FinFichero(Exception):
    pass


class ErrorLecturaMet(Exception):
    pass


def _leer_sfc(e, f):
    """READ(MFUNIT,*) de los 25 valores de una hora del .sfc."""
    previos = [getattr(e, n, 0) for n in _NOMBRES_SFC]
    vals, ios, nr = lread(f.regs[f.ptr:f.ptr + 8], _TIPOS_SFC, previos)
    if ios < 0:
        f.ptr = len(f.regs)
        raise FinFichero()
    f.ptr += nr
    if ios > 0:
        raise ErrorLecturaMet()
    for n, v in zip(_NOMBRES_SFC, vals):
        setattr(e, n, v)


def _leer_pfl(e, f, level, jflag):
    previos = [e.KYEAR, e.KMONTH, e.KDAY, e.KHOUR, e.PFLHT[level], jflag, e.PFLWD[level], e.PFLWS[level],
               e.PFLTA[level], e.PFLSA[level], e.PFLSW[level]]
    vals, ios, nr = lread(f.regs[f.ptr:f.ptr + 8], _TIPOS_PFL, previos)
    if ios < 0:
        f.ptr = len(f.regs)
        raise FinFichero()
    f.ptr += nr
    if ios > 0:
        raise ErrorLecturaMet()
    (e.KYEAR, e.KMONTH, e.KDAY, e.KHOUR, e.PFLHT[level], jflag, e.PFLWD[level], e.PFLWS[level],
     e.PFLTA[level], e.PFLSA[level], e.PFLSW[level]) = vals
    return jflag


def _qsw(e):
    """Radiación solar QSW a partir del flujo de calor, la razón de Bowen, el albedo y la
    nubosidad (rama de deposición de METEXT, que también usa GRSM)."""
    c1, c2, c3, stefb = 5.31e-13, 60.0, 1.12, 5.67e-08
    if e.OBULEN > 0.0 or e.OBULEN < -99990.0 or e.TA < 0.0 or e.ALBEDO == 1.0 or e.BOWEN == 0.0:
        e.QSW = 0.0
    else:
        rn = (1.0 + 1.0 / e.BOWEN) * e.SFCHF / 0.9
        # TA**6 y TA**4 enteros: desarrollados en productos
        ta2 = e.TA * e.TA
        ta3 = ta2 * e.TA
        ta6 = ta3 * ta3
        ta4 = ta2 * ta2
        e.QSW = (rn * (1.0 + c3) - c1 * ta6 + stefb * ta4 - c2 * 0.1 * float(e.NCLOUD)) / \
            (1.0 - e.ALBEDO)


def _agua_suelo(e):
    """Variables de la deposición seca (METEXT): presión de vapor de saturación (fórmula de CMAQ),
    agua disponible en la zona de raíces y factor f2 de la resistencia estomática."""
    if e.TA < 0.0 or e.PRATE < 0.0:
        e.WNEW = e.WOLD
    else:
        e.ESTA = 0.6112 * math.exp(19.83 - 5417.4 / e.TA)
        es25 = 3.167
        e.WNEW = e.WOLD + e.PREC1 - 0.5 * e.F2 * e.ESTA / es25
        e.WOLD = e.WNEW
        e.F2 = e.WNEW / 200.0
        if e.F2 <= 0.01:
            e.F2 = 0.01
        if e.F2 > 1.0:
            e.F2 = 1.0


def metext(e):
    """METEXT: lee una hora de meteorología (.sfc y perfil .pfl) y prepara los perfiles."""
    m = "METEXT"
    e.PATH = "MX"
    e.IPDATE = e.KURDAT
    e.IPYEAR = e.IYR
    e.IPHOUR = e.IHOUR
    e.USTAR = e.OBULEN = e.SFCZ0 = 0.0
    e.QSW = 0.0
    e.IPCODE = 0
    e.PRATE = 0.0
    e.RESET_SA = e.RESET_SW = False
    e.ILINE += 1
    e.DUMMY = "SURFFILE"
    sfc = e.U[e.MFUNIT]
    try:
        if e.IMONTH == 12 and e.IDAY == 31 and e.IHOUR == 24:
            buf = sfc.leer()
            if buf is None:
                raise FinFichero()
            buf = buf[:256].ljust(256)
            if ":" not in buf:
                sfc.ptr -= 1
            else:
                raise NoTraducido("cabeceras intermedias en el .sfc (varios años concatenados)")
        # la deposición (y GRSM, para calcular QSW) lee el .sfc por la rama de las variables de
        # deposición
        dep = e.LDPART or e.LWPART or e.LDGAS or e.LWGAS or e.GRSM
        buf = sfc.leer()
        if buf is None:
            raise FinFichero()
        buf = buf[:256].ljust(256)
        banderas = any(b in buf for b in _BANDERAS)
        if e.ILINE == 1:
            if banderas:
                e.L_NAD_ADJ_FLAGS = True
            nfld = 0
            infld = False
            for c in buf.rstrip(" "):
                if not infld and c != " " and c != ",":
                    infld = True
                    nfld += 1
                elif infld and (c == " " or c == ","):
                    infld = False
            if dep:
                if nfld < 25:
                    e.errhdl(e.PATH, m, "E", "495", "with DEP")
                    e.RUNERR = True
                    e.EOF = True
                    raise ErrorLecturaMet()
            elif nfld < 20:
                e.errhdl(e.PATH, m, "E", "495", "Non-DEP ")
                e.RUNERR = True
                e.EOF = True
                raise ErrorLecturaMet()
            sfc.ptr -= 1
        else:
            e.L_NAD_ADJ_FLAGS = banderas
            sfc.ptr -= 1
        _leer_sfc(e, sfc)
        if dep:
            _qsw(e)
            if e.LDPART or e.LDGAS:
                _agua_suelo(e)
        if e.HBPLUME:
            raise NoTraducido("HBP")
    except FinFichero:
        return _fin(e)
    except ErrorLecturaMet:
        e.errhdl(e.PATH, m, "E", "510", "SURFFILE")
        e.RUNERR = True
        return
    if not e.L_OLDMETVER and not e.SCREEN and e.IMETMSG == 0 and not e.L_NAD_ADJ_FLAGS:
        e.L_OLDMETVER = True
        e.errhdl(e.PATH, m, "W", "394", "No NAD/ADJ")
        e.IMETMSG += 1
    if e.OBULEN > 0.0:
        e.UNSTAB, e.STABLE = False, True
    else:
        e.UNSTAB, e.STABLE = True, False
    pflini(e)
    level = 1
    jflag = 0
    e.DUMMY = "PROFFILE"
    e.L_TURBDATA = False
    pfl = e.U[e.MPUNIT]
    try:
        while jflag == 0:
            jflag = _leer_pfl(e, pfl, level, jflag)
            pflcnv(e, level)
            if (0.0 < e.PFLSA[level] < 99.0) or (0.0 < e.PFLSW[level] < 99.0):
                e.L_TURBDATA = True
            e.NPLVLS = level
            e.IFLAG[level] = jflag
            if jflag == 0:
                level += 1
                if level > e.MXPLVL:
                    if not e.PFLERR:
                        e.DUMMY = fwrite("(I8)", e.MXPLVL)[0]
                        e.errhdl(e.PATH, m, "E", "465", e.DUMMY)
                        e.PFLERR = True
                        e.RUNERR = True
                    level = e.MXPLVL
            if 0.0 < e.PFLSA[level] < 99.0:
                e.L_TURBDATA = True
                e.L_GOT_SIGA = True
            if 0.0 < e.PFLSW[level] < 99.0:
                e.L_TURBDATA = True
                e.L_GOT_SIGW = True
    except FinFichero:
        return _fin(e)
    except ErrorLecturaMet:
        e.errhdl(e.PATH, m, "E", "510", "PROFFILE")
        e.RUNERR = True
        return
    if e.DFAULT and e.L_TURBDATA and e.L_ADJUSTAR:
        if e.L_GOT_SIGA and e.L_GOT_SIGW:
            e.DUMMY = "SigA & SigW"
        elif e.L_GOT_SIGA:
            e.DUMMY = "SigA"
        elif e.L_GOT_SIGW:
            e.DUMMY = "SigW"
        e.errhdl(e.PATH, m, "E", "401", e.DUMMY)
        e.RUNERR = True
    if e.L_TURBDATA:
        if e.L_GOT_SIGA and e.L_GOT_SIGW:
            e.DUMMY = "SigA & SigW"
        elif e.L_GOT_SIGA:
            e.DUMMY = "SigA"
        elif e.L_GOT_SIGW:
            e.DUMMY = "SigW"
        if e.L_ADJUSTAR and e.DFAULT:
            e.errhdl(e.PATH, m, "E", "401", e.DUMMY)
            e.RUNERR = True
    if not e.RUNERR:
        e.NTGLVL = 0
        perfiles.comptg(e)
    if e.ILINE == 1:
        e.JDAY = e._IJDAY
        if not e.L_SKIPMESSAGES:
            metdat(e, e.IOUNIT)
        if e.SUMMFILE and not e.L_SKIPMESSAGES:
            metdat(e, e.ISUMUNT)
    set_metdata(e)
    if e.ILINE == 1:
        if e.IHOUR > 1 and (e.PM25AVE or e.NO2AVE or e.SO2AVE):
            if e.L_MAXDCONT:
                e.DUMMY = fwrite("('First Hr= ',I2.2)", e.IHOUR)[0]
                e.errhdl(e.PATH, m, "E", "491", e.DUMMY)
                e.RUNERR = True
            elif e.NO2AVE or e.SO2AVE:
                e.DUMMY = fwrite("('First Hr= ',I2.2)", e.IHOUR)[0]
                e.errhdl(e.PATH, m, "W", "488", e.DUMMY)
            elif e.PM25AVE:
                e.errhdl(e.PATH, m, "W", "488", "for 1st Day")
        elif e.IHOUR > 1 and (e.NUMAVE > 1 or (e.NUMAVE == 1 and e.KAVE[1] != 1)):
            e.errhdl(e.PATH, m, "W", "488", "for 1st Day")
        if e.IYR != e.ISYEAR and e.IMSTAT[7] == 0:
            e.DUMMY = fwrite("('StartYR ',I4)", e.IYR)[0]
            e.errhdl(e.PATH, m, "W", "492", e.DUMMY)
            e.ISYEAR = e.IYR
        elif e.IYR != e.ISYEAR and e.IMSTAT[7] > 0:
            e.DUMMY = fwrite("('StartYR ',I4)", e.IYR)[0]
            e.errhdl(e.PATH, m, "E", "493", e.DUMMY)
            e.ISYEAR = e.IYR
            e.RUNERR = True
        if e.PM25AVE or e.NO2AVE or e.SO2AVE or e.ANNUAL or e.MULTYR:
            if e.IMSTAT[6] == 0:
                e.ISYR = e.IYEAR
                e.ISHR = e.IHOUR
                e.ISDY = e.IDAY
                e.ISMN = e.IMONTH
                e.IYEAR, e.ISYR = cent_date2(e, e.IYEAR, e.ISYR)
                e.ISJDAY = e.julian(e.ISYR, e.ISMN, e.ISDY)
                if e.IHOUR > 1:
                    e.IENDHOUR = e.IHOUR - 1
                    e.IENDDY = e.IDAY
                    e.IENDMN = e.IMONTH
                else:
                    e.IENDHOUR = 24
                    if e.IDAY > 1:
                        e.IENDDY = e.IDAY - 1
                        e.IENDMN = e.IMONTH
                    else:
                        e.IENDMN = e.IMONTH - 1
                        if e.IENDMN == 0:
                            e.IENDMN = 12
                        e.IENDDY = _IDYMAX[e.IENDMN]
                if not e.RSTINP:
                    e.ISDATE = e.FULLDATE
        if not e.MULTYR and e.IMSTAT[6] == 1 and e.FULLDATE > e.ISDATE:
            e.DUMMY = fwrite("(I10.10)", e.FULLDATE)[0]
            e.errhdl(e.PATH, m, "E", "483", e.DUMMY)
            e.RUNERR = True
        elif e.RSTINP and (e.FULLDATE > e.ISDATE or (e.MULTYR and e.IMSTAT[6] == 0 and
                                                       e.FULLDATE < e.ISDATE)):
            # re-arranque (INITFILE / MULTYEAR): fechas del fichero meteorológico y del SAVEFILE
            e.DUMMY = fwrite("(I10.10)", e.ISDATE - (e.ISDATE // 100000000) * 100000000)[0]
            if not e.MULTYR:
                e.errhdl(e.PATH, m, "E", "484", e.DUMMY)
                e.RUNERR = True
            elif e.FULLDATE > e.ISDATE:
                e.errhdl(e.PATH, m, "W", "485", e.DUMMY)
            else:
                e.errhdl(e.PATH, m, "E", "487", e.DUMMY)
                e.RUNERR = True
    if e.FULLDATE >= e.ISDATE and e.L_MAXDCONT:
        e.IHR_NDX += 1
        e.IYR_NDX = e.NUMYRS + 1
        if e.IYR_NDX > e.NYEARS:
            e.DUMMY = fwrite("('NYEARS=',I4)", e.NYEARS)[0]
            e.errhdl(e.PATH, m, "E", "482", e.DUMMY)
            e.RUNERR = True
            return
        if not e.RSTINP:
            _guardar_maxd(e)


# variables de la hora que MAXDCONT guarda (MAXD_METEXT las recupera)
MAXD_ESCALARES = (("ASFCHF", "SFCHF"), ("AUREF", "UREF"), ("AUREFHT", "UREFHT"), ("ATA", "TA"),
                  ("ATREFHT", "TREFHT"), ("AWDREF", "WDREF"), ("AUSTAR", "USTAR"), ("AWSTAR", "WSTAR"),
                  ("AZICONV", "ZICONV"), ("AZIMECH", "ZIMECH"), ("AOBULEN", "OBULEN"), ("AVPTGZI", "VPTGZI"),
                  ("ASFCZ0", "SFCZ0"))
MAXD_ESCALARES2 = (("ARURUSTR", "RURUSTR"), ("ARUROBULEN", "RUROBULEN"), ("ACLMHR", "CLMHR"),
                   ("AMSGHR", "MSGHR"), ("AUNSTAB", "UNSTAB"), ("ASTABLE", "STABLE"), ("AURBSTAB", "URBSTAB"),
                   ("ANDX4ZI", "NDX4ZI"), ("AUATZI", "UATZI"), ("ASVATZI", "SVATZI"), ("ASWATZI", "SWATZI"),
                   ("AUAVG", "UAVG"), ("ASVAVG", "SVAVG"), ("ASWAVG", "SWAVG"), ("APTATZI", "PTATZI"))
MAXD_PERFILES = (("AGRIDWD", "GRIDWD"), ("AGRIDWS", "GRIDWS"), ("AGRIDSW", "GRIDSW"), ("AGRIDSV", "GRIDSV"),
                 ("AGRIDTG", "GRIDTG"), ("AGRIDPT", "GRIDPT"))


def _sector_flujo(fvref, sector_on, sect, n, previo):
    """Sector de un fondo que varía con la dirección (O3SECTOR, NOXSECTR). Si el vector de
    flujo no cae en ningún intervalo, el índice conserva su valor (como en el original)."""
    if not sector_on:
        return 1
    if fvref < sect[1] or fvref >= sect[n]:
        return n
    for i in range(1, n):
        if sect[i] <= fvref < sect[i + 1]:
            return i
    return previo


def grdeps(e):
    """GRDEPS: perfil de la tasa de disipación de la turbulencia (épsilon) para PVMRM y GRSM."""
    ar1 = 0.46
    for i in range(1, e.MXGLVL + 1):
        tsublr = ar1 * e.ZI / e.GRIDSW[i]
        e.GRIDEPS[i] = 0.78 * e.GRIDSW[i] * e.GRIDSW[i] / tsublr


def _guardar_maxd(e):
    """Final de METEXT con MAXDCONT: guarda la meteorología de la hora (IHR_NDX, IYR_NDX)."""
    h, y = e.IHR_NDX, e.IYR_NDX
    for a, v in MAXD_ESCALARES:
        getattr(e, a)[h, y] = getattr(e, v)
    e.AKST[h, y] = e.KST
    if e.HBPLUME:
        e.AZICONVN[h, y] = e.ZICONVN
        e.AZIMECHN[h, y] = e.ZIMECHN
    if e.LDGAS or e.LDPART or e.LWPART or e.LWGAS or e.GRSM:
        e.ABOWEN[h, y] = e.BOWEN
        e.AALBEDO[h, y] = e.ALBEDO
        e.IAPCODE[h, y] = e.IPCODE
        e.APRATE[h, y] = e.PRATE
        e.ARH[h, y] = e.RH
        e.ASFCP[h, y] = e.SFCP
        e.NACLOUD[h, y] = e.NCLOUD
        e.AQSW[h, y] = e.QSW
        e.AWNEW[h, y] = e.WNEW
        e.AF2[h, y] = e.F2
        e.AESTA[h, y] = e.ESTA
        e.APREC1[h, y] = e.PREC1
        e.APREC2[h, y] = e.PREC2
    if e.L_BLSOURCE:
        e.ABLTA[h, y] = e.TA
    for a, v in MAXD_ESCALARES2:
        getattr(e, a)[h, y] = getattr(e, v)
    mx = e.MXGLVL
    for a, v in MAXD_PERFILES:
        getattr(e, a)[h, 1:mx + 1, y] = getattr(e, v)[1:mx + 1]
    if e.NSEC > 0:
        e.AGRIDRHO[h, 1:mx + 1, y] = e.GRIDRHO[1:mx + 1]
    if e.PVMRM or e.GRSM:
        e.AGRIDEPS[h, 1:mx + 1, y] = e.GRIDEPS[1:mx + 1]
    if e.NURB > 0:
        e.AGRDSWR[h, 1:mx + 1, y] = e.GRDSWR[1:mx + 1]
        e.AGRDSVR[h, 1:mx + 1, y] = e.GRDSVR[1:mx + 1]
        e.AGRDTGR[h, 1:mx + 1, y] = e.GRDTGR[1:mx + 1]
        e.AGRDPTR[h, 1:mx + 1, y] = e.GRDPTR[1:mx + 1]
        for i in range(1, e.NURB + 1):
            e.AGRDSWU[h, 1:mx + 1, y, i] = e.GRDSWU[1:mx + 1, i]
            e.AGRDSVU[h, 1:mx + 1, y, i] = e.GRDSVU[1:mx + 1, i]
            e.AGRDTGU[h, 1:mx + 1, y, i] = e.GRDTGU[1:mx + 1, i]
            e.AGRDPTU[h, 1:mx + 1, y, i] = e.GRDPTU[1:mx + 1, i]
            e.AZIURB[h, y, i] = e.ZIURB[i]
            e.AURBWSTR[h, y, i] = e.URBWSTR[i]
            e.AURBUSTR[h, y, i] = e.URBUSTR[i]
            e.AURBOBULEN[h, y, i] = e.URBOBULEN[i]
            e.AL_MORNINGTRANS[h, y, i] = e.L_MORNINGTRANS[i]


def _fin(e):
    """Fin de fichero meteorológico (etiqueta 1000 de METEXT)."""
    e.EOF = True
    if e.ILINE == 1:
        e.errhdl(e.PATH, "METEXT", "E", "580", e.DUMMY)
        e.RUNERR = True


def cent_date2(e, two, four):
    """CENT_DATE(TwoDigitYear, FourDigitYear) con dos variables distintas. Devuelve (two, four)."""
    if four <= 99 and four != 0:
        two = four
    if two != e.ISTRT_WIND:
        e.ISTRT_WIND = two
        if 50 <= two < 100:
            e.ISTRT_CENT = 19
        elif two < 50:
            e.ISTRT_CENT = 20
    if e.ISTRT_WIND <= two <= 99:
        four = e.ISTRT_CENT * 100 + two
    elif two > 99:
        four = two
        two = four - 100 * (four // 100)
    return two, four


_NDAY = (0, 31, 59, 90, 120, 151, 181, 212, 243, 273, 304, 334, 365)
_ISEA_NDX = (0, 1, 1, 2, 2, 2, 3, 3, 3, 4, 4, 4, 1)


def set_dates(e):
    """SET_DATES: año de 4 cifras, día juliano, KURDAT, FULLDATE, estación y día de la semana."""
    if not e.L_SKIPMESSAGES:
        e.IYEAR, e.IYR = cent_date2(e, e.IYEAR, e.IYR)
        y = e.IYR
        e.L_LEAPYEAR = not (y % 4 != 0 or (y % 100 == 0 and y % 400 != 0))
        e.JDAY_PREV = e.JDAY if e.JDAY >= 1 else 0
        e.JDAY = e.julian(e.IYR, e.IMONTH, e.IDAY)
        e.KURDAT = e.IYEAR * 1000000 + e.IMONTH * 10000 + e.IDAY * 100 + e.IHOUR
        if e.IYR >= 2148:
            e.DUMMY = fwrite('("YR= ",I4)', e.IYR)[0]
            e.errhdl(e.PATH, "SET_DATES", "E", "365", e.DUMMY)
            e.RUNERR = True
            e.FULLDATE = 2147123124
        else:
            e.FULLDATE = e.IYR * 1000000 + e.IMONTH * 10000 + e.IDAY * 100 + e.IHOUR
        if e.KYEAR >= 100:
            e.KYEAR = e.KYEAR - 100 * (e.KYEAR // 100)
        e.KURPFL = e.KYEAR * 1000000 + e.KMONTH * 10000 + e.KDAY * 100 + e.KHOUR
    e.ISEAS = _ISEA_NDX[e.IMONTH]
    if e.L_DAYOFWEEKOPTS:
        ia = (14 - e.IMONTH) // 12
        iy = e.IYR - ia
        im = e.IMONTH + 12 * ia - 2
        idd = (e.IDAY + iy + iy // 4 - iy // 100 + iy // 400 + (31 * im) // 12) % 7
        if 1 <= idd <= 5:
            e.IDAY_OF_WEEK = 1
        elif idd == 6:
            e.IDAY_OF_WEEK = 2
        elif idd == 0:
            e.IDAY_OF_WEEK = 3
        e.IDAY_OF_WEEK7 = 7 if idd == 0 else idd
    else:
        e.IDAY_OF_WEEK = 1
        e.IDAY_OF_WEEK7 = 1


def set_metdata(e):
    """SET_METDATA: controles de la hora, ZI, rotación del viento y perfiles en la malla."""
    m = "SET_METDATA"
    if 0.0 <= e.ZICONV < 1.0:
        e.ZICONV = 1.0
    if 0.0 <= e.ZIMECH < 1.0:
        e.ZIMECH = 1.0
    set_dates(e)
    if e.MONTH and e.IHOUR == 24:
        if e.IMONTH == 1 or e.IYR % 4 != 0 or (e.IYR % 100 == 0 and e.IYR % 400 != 0):
            if e.JDAY == _NDAY[e.IMONTH]:
                e.ENDMON = True
        elif e.JDAY == _NDAY[e.IMONTH] + 1:
            e.ENDMON = True
    if not e.L_SKIPMESSAGES:
        metchk(e)
    if e.ZICONV > 4000.0:
        e.ZICONV = 4000.0
    if e.ZIMECH > 4000.0:
        e.ZIMECH = 4000.0
    if not e.MSGHR and not e.CLMHR and e.OBULEN < 0.0:
        e.ZI = max(e.ZICONV, e.ZIMECH)
    elif not e.MSGHR and not e.CLMHR:
        e.ZI = e.ZIMECH
    else:
        e.ZI = -999.0
    if 0.0 <= e.ZI < 1.0:
        e.ZI = 1.0
    if e.URBAN:
        e.ZIRUR = e.ZI
    if abs(e.ROTANG) > 0.0000001:
        e.WDREF = e.WDREF - e.ROTANG
        if e.WDREF <= 0.0:
            e.WDREF = e.WDREF + 360.0
        for nl in range(1, e.NPLVLS + 1):
            if e.PFLWD[nl] > 0.0:
                e.PFLWD[nl] = e.PFLWD[nl] - e.ROTANG
                if e.PFLWD[nl] <= 0.0:
                    e.PFLWD[nl] = e.PFLWD[nl] + 360.0
    if e.L_BLSOURCE:
        e.BLTA = e.TA
    if not e.L_SKIPMESSAGES:
        e.URBSTAB = False
    if not e.RUNERR and not e.L_SKIPMESSAGES:
        if not e.CLMHR and not e.MSGHR:
            if e.OBULEN > 0.0:
                e.UNSTAB, e.STABLE = False, True
            else:
                e.UNSTAB, e.STABLE = True, False
            proc = e.IPROCL[e.JDAY] if e.L_LEAPYEAR else e.IPROC[e.JDAY]
            if e.FULLDATE >= e.ISDATE and proc == 1:
                if e.URBAN:
                    for n in ("GRDSVR", "GRDSVU", "GRDSWR", "GRDSWU", "GRDTGR", "GRDTGU", "GRDPTR", "GRDPTU"):
                        getattr(e, n)[...] = -99.0
                e.PATH = "MX"
                from . import nucleo
                if nucleo.activo():
                    nucleo.perfiles_hora(e)
                else:
                    perfiles.perfiles_hora(e)
                if e.PVMRM or e.GRSM:
                    grdeps(e)
                if e.URBAN:
                    urbcalc(e)
                    grdurban(e)
        e.DUMMY = fwrite("(I10.10)", e.FULLDATE)[0]
    if e.WDREF <= 0.0 or e.WDREF > 360.0:
        e.IO3SECT = 0
        e.INOXSECT = 0
    else:
        # sector del ozono y del NOx de fondo según el vector de flujo (hacia donde sopla)
        fvref = e.WDREF + 180.0
        if fvref > 360.0:
            fvref = fvref - 360.0
        e.IO3SECT = _sector_flujo(fvref, e.L_O3SECTOR, e.O3SECT, e.NUMO3SECTS, e.IO3SECT)
        e.INOXSECT = _sector_flujo(fvref, e.L_NOXSECTOR, e.NOXSECT, e.NUMNOXSECTS, e.INOXSECT)
    if e.WDREF <= 0.0 or e.WDREF > 360.0:
        e.IBGSECT = 0
    else:
        # sector del fondo según el vector de flujo (hacia donde sopla)
        fvref = e.WDREF + 180.0
        if fvref > 360.0:
            fvref = fvref - 360.0
        if e.L_BGSECTOR:
            bs, nb = e.BGSECT, e.NUMBGSECTS
            if fvref < bs[1] or fvref >= bs[nb]:
                e.IBGSECT = nb
            else:
                for i in range(1, nb):
                    if bs[i] <= fvref < bs[i + 1]:
                        e.IBGSECT = i
                        break
        else:
            e.IBGSECT = 1
    u = e.UREF
    if u <= e.UCAT[1]:
        e.IUCAT = 1
    elif u <= e.UCAT[2]:
        e.IUCAT = 2
    elif u <= e.UCAT[3]:
        e.IUCAT = 3
    elif u <= e.UCAT[4]:
        e.IUCAT = 4
    elif u <= e.UCAT[5]:
        e.IUCAT = 5
    else:
        e.IUCAT = 6
    if e.FASTAREA or e.L_BLSOURCE:
        from . import fuente_linea_flotante
        e.KST = fuente_linea_flotante.ltopg(e)
    else:
        e.KST = 4
    if e.MSGHR and not e.L_SKIPMESSAGES:
        e.DUMMY = fwrite("(I10.10)", e.FULLDATE)[0]
        if not e.MSGPRO:
            e.RUNERR = True
            e.errhdl(e.PATH, m, "E", "460", e.DUMMY)
        else:
            e.errhdl(e.PATH, m, "I", "460", e.DUMMY)


def metchk(e):
    """METCHK: controles de la hora meteorológica."""
    e.CLMHR = False
    e.MSGHR = False
    if not e.NOCHKD and not e.EVONLY:
        chkdat(e)
    cmpdat(e)
    chkclm(e)
    if not e.CLMHR:
        chkmsg(e)
    metqa(e)


def _aviso450(e, txt, error_cuenta=True):
    """Mensaje 450 de CHKDAT: error (y RUNERR) o aviso si WARNCHKD."""
    e.DUMMY = txt
    if not e.L_WARNCHKD:
        e.errhdl(e.PATH, "CHKDAT", "E", "450", e.DUMMY)
        if error_cuenta:
            e.RUNERR = True
    elif e.L_WARNCHKD and not e.L_SKIPMESSAGES:
        e.errhdl(e.PATH, "CHKDAT", "W", "450", e.DUMMY)


def chkdat(e):
    """CHKDAT: secuencia de fechas del fichero meteorológico."""
    k8 = fwrite("(I8.8)", e.KURDAT)[0]
    if e.IPDATE <= 0:
        return
    if e.KURDAT <= e.IPDATE:
        if e.KURDAT != 10101 or e.IPDATE != 99123124:
            _aviso450(e, k8)
    elif e.IHOUR > 1:
        d = e.KURDAT - e.IPDATE
        if d == 1:
            pass
        elif d < 23:
            _aviso450(e, k8)
            _aviso450(e, fwrite("(I3,' hour gap')", d - 1)[0])
        else:
            _aviso450(e, k8)
    elif e.IHOUR == 1 and e.IPHOUR == 24:
        jd, jp = e.JDAY, e.JDAY_PREV
        if jd > 1 and jd - jp == 1 and e.IYR == e.IPYEAR:
            pass
        elif jd > 1 and jd - jp > 1 and e.IYR == e.IPYEAR:
            _aviso450(e, k8)
            _aviso450(e, fwrite("(I3,' day gap')", jd - jp - 1)[0], False)
        elif jd > 1 and jd - jp > 1 and e.IYR > e.IPYEAR:
            _aviso450(e, k8)
            _aviso450(e, fwrite("(I2,' yr;',I3,' dy')", e.IYR - e.IPYEAR, jd - jp - 1)[0], False)
        elif jd > 1 and jp >= jd and e.IYR > e.IPYEAR:
            _aviso450(e, k8)
            _aviso450(e, fwrite("(I2,' yr;',I3,' dy')", e.IYR - e.IPYEAR - 1, (365 - jp) + jd - 1)[0], False)
        elif jd == 1 and jp >= 1 and e.IYR - e.IPYEAR == 1:
            py = e.IPYEAR
            if py % 4 != 0 or (py % 100 == 0 and py % 400 != 0):
                if jp < 365:
                    _aviso450(e, k8)
                    _aviso450(e, fwrite("(I3,' day gap')", 365 - jp)[0], False)
            elif jp < 366:
                _aviso450(e, k8)
                _aviso450(e, fwrite("(I3,' day gap')", 366 - jp)[0], False)
        elif e.IHOUR == 1 and jd == 1 and jp >= 1 and (e.IYR - e.IPYEAR) > 1:
            py = e.IPYEAR
            if py % 4 != 0 or (py % 100 == 0 and py % 400 != 0):
                if jp < 365:
                    _aviso450(e, k8)
                    _aviso450(e, fwrite("(I3,' day gap')", 365 - jp)[0], False)
            elif jp < 366:
                _aviso450(e, k8)
                _aviso450(e, fwrite("(I3,' day gap')", 366 - jp)[0], False)
            e.DUMMY = k8
            if not e.L_WARNCHKD or not e.L_SKIPMESSAGES:
                e.errhdl(e.PATH, "CHKDAT", "W", "450", e.DUMMY)
            e.DUMMY = fwrite("(I3,' year gap')", e.IYR - e.IPYEAR - 1)[0]
            if not e.L_WARNCHKD or not e.L_SKIPMESSAGES:
                e.errhdl(e.PATH, "CHKDAT", "W", "450", e.DUMMY)
    elif e.IHOUR == 1 and e.IPHOUR != 24:
        _aviso450(e, k8)
        jd, jp = e.JDAY, e.JDAY_PREV
        if jd > 1 and jd - jp > 1 and e.IYR == e.IPYEAR:
            _aviso450(e, fwrite("(I2,'hr & ',I3,'dy')", 24 - e.IPHOUR, jd - jp - 1)[0], False)
        elif jd == 1 and jp >= 1 and e.IYR - e.IPYEAR == 1:
            _aviso450(e, k8)
            _aviso450(e, fwrite("(I3,' day gap')", jd - jp - 1)[0], False)


def cmpdat(e):
    """CMPDAT: la fecha del .sfc y la del .pfl deben coincidir."""
    if e.KURDAT != e.KURPFL:
        e.DUMMY = fwrite("(I8.8)", e.KURDAT)[0]
        e.errhdl(e.PATH, "CMPDAT", "E", "456", e.DUMMY)
        e.RUNERR = True


def chkclm(e):
    """CHKCLM: hora de calma (UREF = 0)."""
    if e.UREF == 0.0:
        e.CLMHR = True
        if not e.L_SKIPMESSAGES:
            e.DUMMY = fwrite("(I10.10)", e.FULLDATE)[0]
            e.errhdl(e.PATH, "CHKCLM", "I", "440", e.DUMMY)


def chkmsg(e):
    """CHKMSG: hora con datos ausentes."""
    if e.UREF >= 90.0 or e.UREF < 0.0:
        e.MSGHR = True
    elif e.WDREF > 900.0 or e.WDREF <= -9.0:
        e.MSGHR = True
    elif e.TA > 900.0 or e.TA <= 0.0:
        e.MSGHR = True
    elif e.OBULEN < -99990.0:
        e.MSGHR = True
    elif e.OBULEN < 0.0 and (e.ZICONV > 90000.0 or e.ZICONV < 0.0):
        e.MSGHR = True
    elif e.ZIMECH > 90000.0 or e.ZIMECH < 0.0:
        e.MSGHR = True
    elif e.USTAR < 0.0 or e.USTAR >= 9.0:
        e.MSGHR = True
    elif e.WSTAR < 0.0 and (e.OBULEN < 0.0 and e.OBULEN > -99990.0):
        e.MSGHR = True


def metqa(e):
    """METQA: control de calidad de la hora (y ajustes de WSTAR, OBULEN, VPTGZI, Z0, PRATE)."""
    m = "METQA"
    k8 = fwrite("(I8.8)", e.KURDAT)[0]
    if e.WDREF == 0.0:
        e.WDREF = 360.0
    for nl in range(1, e.NPLVLS + 1):
        if e.PFLWD[nl] == 0.0:
            e.PFLWD[nl] = 360.0
    if not e.L_SKIPMESSAGES:
        if (-9.0 < e.WDREF < 0.0) or (360.0 < e.WDREF < 900.0):
            e.DUMMY = k8
            e.errhdl(e.PATH, m, "W", "410", e.DUMMY)
        if -9.0 < e.UREF < 0.0:
            e.DUMMY = k8
            e.errhdl(e.PATH, m, "W", "420", e.DUMMY)
        if 30.0 < e.UREF < 90.0:
            e.DUMMY = k8
            e.errhdl(e.PATH, m, "W", "420", e.DUMMY)
        if e.UREFHT > 100.0:
            e.DUMMY = k8
            e.errhdl(e.PATH, m, "W", "475", e.DUMMY)
        elif e.UREFHT < 0.001 and not e.CLMHR and not e.MSGHR:
            e.DUMMY = k8
            e.errhdl(e.PATH, m, "E", "474", e.DUMMY)
            e.RUNERR = True
        if (0.0 < e.TA < 220.0) or (330.0 < e.TA < 900.0):
            e.DUMMY = k8
            e.errhdl(e.PATH, m, "W", "430", e.DUMMY)
        if e.USTAR > 4.0:
            e.DUMMY = k8
            e.errhdl(e.PATH, m, "W", "432", e.DUMMY)
    if e.WSTAR > 4.00:
        if not e.L_SKIPMESSAGES:
            e.DUMMY = k8
            e.errhdl(e.PATH, m, "W", "438", e.DUMMY)
    elif e.WSTAR == 0.0:
        if not e.L_SKIPMESSAGES:
            e.DUMMY = k8
            e.errhdl(e.PATH, m, "W", "438", e.DUMMY)
        e.WSTAR = 0.001
    if abs(e.OBULEN) < 1.00:
        if not e.L_SKIPMESSAGES:
            e.DUMMY = k8
            e.errhdl(e.PATH, m, "W", "439", e.DUMMY)
        if e.OBULEN < 0.0:
            e.OBULEN = -1.0
        elif e.OBULEN > 0.0:
            e.OBULEN = 1.0
        else:
            e.OBULEN = -1.0 * dsign(1.0, e.SFCHF)
    if e.ZICONV > 0.0 and -99990.0 < e.OBULEN < 0.0 and e.VPTGZI < 0.005:
        if not e.L_SKIPMESSAGES:
            e.DUMMY = k8
            e.errhdl(e.PATH, m, "W", "441", e.DUMMY)
        e.VPTGZI = 0.005
    elif e.ZICONV > 0.0 and -99990.0 < e.OBULEN < 0.0 and e.VPTGZI > 0.10:
        if not e.L_SKIPMESSAGES:
            e.DUMMY = k8
            e.errhdl(e.PATH, m, "W", "442", e.DUMMY)
    if e.SFCZ0 < 0.0001:
        if not e.MSGHR and not e.CLMHR:
            if not e.L_SKIPMESSAGES:
                e.DUMMY = k8
                e.errhdl(e.PATH, m, "W", "435", e.DUMMY)
        e.SFCZ0 = 0.0001
    if e.PRATE < 0.0 or e.PRATE > 900.0:
        e.PRATE = 0.0
    else:
        e.TOTAL_PRECIP = e.TOTAL_PRECIP + e.PRATE


def metdat(e, u):
    """METDAT: primeras 24 horas de datos de superficie y primer perfil."""
    out = []
    e.header(u)
    out += fwrite("(/36X,'*** UP TO THE FIRST 24 HOURS OF ','METEOROLOGICAL DATA ***'/)")
    out += fwrite("(3X,'Surface file:   ',A80,3X,'Met Version: ',A6,/,3X,'Profile file:   ',A80,/,3X,"
                  "'Surface format: ',A105,/,3X,'Profile format: ',A105 )", fx(e.METINP, 80), fx(e.C_METVER, 6),
                  fx(e.PROINP, 80), fx(e.METFRM, 105), fx(e.PROFRM, 105))
    out += fwrite("(3X,'Surface station no.: ',I8,18X,'Upper air station no.: ',I8/18X,'Name: ',A40,3X,'Name: ',"
                  "A40/18X,'Year: ',I6,37X,'Year: ',I6)", e.IDSURF, e.IDUAIR, fx(e.SFNAME, 40), fx(e.UANAME, 40),
                  e.ISYEAR, e.IUYEAR)
    out += fwrite("(/' First 24 hours of scalar data')")
    dep = e.LDPART or e.LDGAS or e.LWPART or e.LWGAS or e.GRSM
    if dep:
        out += fwrite("(' YR',' MO', ' DY', ' HR', '     H0','     U*', '     W*', '  DT/DZ', ' ZICNV', "
                      "' ZIMCH','  M-O LEN', '  Z0 ', 'BOWEN', '  ALB','  REF WS', '   WD', '   HT', "
                      "'  REF TA', '  HT',' IPCOD',' PRATE','  RH',' SFCP',' CCVR'/66('- '))")
    else:
        out += fwrite("(' YR',' MO', ' DY', ' JDY', ' HR', '     H0','     U*', '     W*', '  DT/DZ', ' ZICNV', "
                      "' ZIMCH','  M-O LEN', '    Z0', '  BOWEN', ' ALBEDO','  REF WS', '   WD', '     HT', "
                      "'  REF TA', '     HT',/61('- '))")
    f9026 = ("( 1X,3(I2.2,1X),I3,1X,I2.2,1X,F6.1,1X,3(F6.3,1X),2(F5.0,1X),F8.1,1X,F5.2,1X,2(F6.2,1X),F7.2,1X,"
             "F5.0,3(1X,F6.1) )")
    f99026 = ("( 1X,3(I2.2,1X),I2.2,1X,F6.1,1X,3(F6.3,1X),2(F5.0,1X),F8.1,3F5.2,1X,F7.2,1X,F5.0,1X,F4.0,1X,"
              "F6.1,1X,F4.0,I3,F7.2,F6.0,F6.0,I3)")
    sfc = e.U[e.MFUNIT]
    for i in range(1, 25):
        if i > 1 and e.IYEAR >= 100:
            e.IYEAR = e.IYEAR - 100 * (e.IYEAR // 100)
        if dep:
            out += fwrite(f99026, e.IYEAR, e.IMONTH, e.IDAY, e.IHOUR, e.SFCHF, e.USTAR, e.WSTAR,
                          e.VPTGZI, e.ZICONV, e.ZIMECH, e.OBULEN, e.SFCZ0, e.BOWEN, e.ALBEDO, e.UREF, e.WDREF,
                          e.UREFHT, e.TA, e.TREFHT, e.IPCODE, e.PRATE, e.RH, e.SFCP, e.NCLOUD)
        elif i == 1:
            out += fwrite(f9026, e.IYEAR, e.IMONTH, e.IDAY, e.JDAY, e.IHOUR, e.SFCHF, e.USTAR, e.WSTAR,
                          e.VPTGZI, e.ZICONV, e.ZIMECH, e.OBULEN, e.SFCZ0, e.BOWEN, e.ALBEDO, e.UREF, e.WDREF,
                          e.UREFHT, e.TA, e.TREFHT)
        else:
            out += fwrite(f9026, e.IYEAR, e.IMONTH, e.IDAY, e._IJDAY, e.IHOUR, e.SFCHF, e.USTAR, e.WSTAR,
                          e.VPTGZI, e.ZICONV, e.ZIMECH, e.OBULEN, e.SFCZ0, e.BOWEN, e.ALBEDO, e.UREF, e.WDREF,
                          e.UREFHT, e.TA, e.TREFHT)
        try:
            _leer_sfc(e, sfc)
        except FinFichero:
            break
        except ErrorLecturaMet:
            e.errhdl(e.PATH, "METDAT", "E", "510", "SURFFILE")
            e.RUNERR = True
            e.w(u, out)
            return
    sfc.rewind()
    sfc.leer()
    try:
        _leer_sfc(e, sfc)
    except FinFichero:
        pass
    except ErrorLecturaMet:
        e.errhdl(e.PATH, "METDAT", "E", "510", "SURFFILE")
        e.RUNERR = True
        e.w(u, out)
        return
    e.w(u, out)
    out = []
    if e.NPLVLS > 10:
        e.header(u)
    out += fwrite("(//,' First hour of profile data')")
    out += fwrite("( ' YR', ' MO', ' DY', ' HR', ' HEIGHT', ' F', '  WDIR','    WSPD',' AMB_TMP', ' sigmaA', "
                  "'  sigmaW','  sigmaV' )")
    for i in range(1, e.NPLVLS + 1):
        out += fwrite("(1X, 4(I2.2,1X),F6.1,1X,I1,1X,F5.0,1X,F7.2,1X,F7.1,1X,F6.1,1X,F7.2,1X,F7.2)", e.KYEAR,
                      e.KMONTH, e.KDAY, e.KHOUR, e.PFLHT[i], int(e.IFLAG[i]), e.PFLWD[i], e.PFLWS[i], e.PFLTA[i],
                      e.PFLSA[i], e.PFLSW[i], e.PFLSV[i])
    out += fwrite("(/ ' F indicates top of profile (=1) or below (=0)')")
    e.w(u, out)


# ------------------------------------------------------------------------------------- urbano
def urbcalc(e):
    """URBCALC: capa límite urbana nocturna (o de la transición matinal) de cada zona urbana:
    altura de mezcla, velocidades convectiva y de fricción y longitud de Monin-Obukhov."""
    refzi, cp = 400.0, 1004.0
    e.RURUSTR = e.USTAR
    e.RUROBULEN = e.OBULEN
    for iu in range(1, e.NUMURB + 1):
        e.IURB = iu
        deltur = e.DELTRUR * (0.1 * math.log(e.URBPOP[iu] / e.REFPOP) + 1.0)
        if e.STABLE:
            e.ZIURB[iu] = refzi * (e.URBPOP[iu] / e.REFPOP) ** 0.25
            e.L_MORNINGTRANS[iu] = False
        elif e.L_URBANTRANSITION:
            e.ZIURB[iu] = refzi * (e.URBPOP[iu] / e.REFPOP) ** 0.25
            if e.ZICONV > e.ZIURB[iu]:
                e.L_MORNINGTRANS[iu] = False
                continue
            e.L_MORNINGTRANS[iu] = True
        else:
            e.L_MORNINGTRANS[iu] = False
            continue
        rho = 101325.0 / (287.04 * e.TA)
        urbhf = 0.03 * deltur * e.USTAR * rho * cp
        e.URBWSTR[iu] = ((e.G / e.TA / rho / cp) * urbhf * e.ZIURB[iu]) ** e.THIRD
        ht7z0 = 7.0 * max(e.URBZ0[iu], e.SFCZ0)
        zu = e.ZIURB[iu]
        urbustrsav = e.URBWSTR[iu] * math.sqrt(1.6 * (ht7z0 / zu) ** (2.0 * e.THIRD)) / \
            (1.3 * math.sqrt(1.0 - ht7z0 / max(zu, e.ZIMECH)))
        e.URBUSTR[iu] = max(e.USTAR, urbustrsav)
        e.URBOBULEN[iu] = -((rho * cp * e.TA * e.URBUSTR[iu] ** 3) / (0.4 * e.G * urbhf))
        urboblsav = e.URBOBULEN[iu]
        if e.L_MORNINGTRANS[iu]:
            e.URBOBULEN[iu] = max(e.URBOBULEN[iu], e.RUROBULEN)
        else:
            e.URBOBULEN[iu] = max(abs(e.URBOBULEN[iu]), e.RUROBULEN)
        if e.URBDBUG:
            from . import depura
            depura.wf(e, e.URBUNT, "(1X,5(2X,I2),17(F12.2),(7X,L2),(9X,L2))", iu, e.IYEAR, e.IMONTH, e.IDAY,
                      e.IHOUR, e.URBOBULEN[iu], urboblsav, e.RUROBULEN, e.URBUSTR[iu], urbustrsav, e.USTAR,
                      deltur, e.ZIURB[iu], e.ZIMECH, e.ZICONV, e.URBPOP[iu], urbhf, e.URBWSTR[iu], e.WSTAR,
                      e.TA, e.UREF, e.BOWEN, bool(e.STABLE), bool(e.L_MORNINGTRANS[iu]))
    e.IURB = e.NUMURB + 1


def grdurban(e):
    """GRDURBAN: perfiles de sigma-v, sigma-w y gradiente de temperatura potencial con la
    turbulencia convectiva urbana añadida (y copia de los rurales)."""
    mx = e.MXGLVL
    gh = e.GRIDHT
    e.GRDSVR[:] = e.GRIDSV
    e.GRDSWR[:] = e.GRIDSW
    e.GRDTGR[:] = e.GRIDTG
    e.GRDPTR[:] = e.GRIDPT
    for iu in range(1, e.NUMURB + 1):
        e.IURB = iu
        if not e.STABLE and not e.L_MORNINGTRANS[iu]:
            continue
        zu = e.ZIURB[iu]
        ws = e.URBWSTR[iu]
        zdcrs = e.AT1PT2 * zu
        for i in range(1, mx + 1):
            z = gh[i]
            sv2 = 0.35 * ws ** 2
            if z <= zu:
                svurb = math.sqrt(sv2)
            elif zu < z <= zdcrs:
                sv2dcr = min(sv2, 0.25)
                val2 = perfiles.gintrp(zu, sv2, zdcrs, sv2dcr, z)
                svurb = math.sqrt(val2)
            else:
                atzi = math.sqrt(sv2)
                svurb = min(atzi, 0.5)
            if z <= 0.1 * zu:
                sw2 = 1.6 * (z / zu) ** (2.0 * e.THIRD) * ws ** 2
                swurb = math.sqrt(sw2)
            elif 0.1 * zu < z <= zu:
                swurb = math.sqrt(0.35 * ws ** 2)
            else:
                sw2 = 0.35 * ws ** 2 * math.exp(-(6.0 * (z - zu) / zu))
                swurb = math.sqrt(sw2)
            e.GRDSVU[i, iu] = math.sqrt(e.GRIDSV[i] ** 2 + svurb ** 2)
            e.GRDSWU[i, iu] = math.sqrt(e.GRIDSW[i] ** 2 + swurb ** 2)
            e.GRDTGU[i, iu] = 1.0e-5 if z <= zu else e.GRIDTG[i]
            if e.URBDBUG and i < 17:
                from . import depura
                depura.wf(e, e.URBUNT1, "(1X,6(2X,I2),9(F10.2))", iu, e.IYEAR, e.IMONTH, e.IDAY, e.IHOUR, i,
                          gh[i], e.GRIDSV[i], svurb, e.GRDSVU[i, iu], e.GRIDSW[i], swurb, e.GRDSWU[i, iu])
    e.IURB = e.NUMURB + 1
    grdpturb(e)


def grdpturb(e):
    """GRDPTURB: perfil de temperatura potencial urbano a partir de su gradiente."""
    mx = e.MXGLVL
    gh = e.GRIDHT
    nbelow = perfiles.locate(gh, 1, mx, e.TREFHT)
    ptref = e.TA + e.GOVRCP * (e.TREFHT + e.ZBASE)
    for iu in range(1, e.NUMURB + 1):
        e.IURB = iu
        if not e.STABLE and not e.L_MORNINGTRANS[iu]:
            continue
        tg, pt = e.GRDTGU, e.GRDPTU
        pt[nbelow, iu] = ptref - 0.5 * (tg[nbelow + 1, iu] + tg[nbelow, iu]) * (e.TREFHT - gh[nbelow])
        for lv in range(nbelow - 1, 0, -1):
            pt[lv, iu] = pt[lv + 1, iu] - 0.5 * (tg[lv + 1, iu] + tg[lv, iu]) * (gh[lv + 1] - gh[lv])
        for lv in range(nbelow + 1, mx + 1):
            pt[lv, iu] = pt[lv - 1, iu] + 0.5 * (tg[lv, iu] + tg[lv - 1, iu]) * (gh[lv] - gh[lv - 1])
        if e.URBDBUG:
            from . import depura
            for i in range(1, mx + 1):
                depura.wf(e, e.URBUNT2, "(1X,6(2X,I2),1(5X,I2),1(F10.2),2(E10.3),2(F10.4))", iu, e.IYEAR,
                          e.IMONTH, e.IDAY, e.IHOUR, i, nbelow, gh[i], e.GRIDTG[i], tg[i, iu], e.GRIDPT[i],
                          pt[i, iu])
    e.IURB = e.NUMURB + 1
