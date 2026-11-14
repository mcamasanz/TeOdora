# -*- coding: utf-8 -*-
"""Traducción de AERMOD 26135 (US EPA, dominio público): química del NO2 en el cálculo horario.

aermod.f: O3EXT, NOXEXT y el paso de HRLOOP que fija el ozono y el NOx de fondo de la hora.
calc1.f: OLM_CALC, ARM2_CALC, PVMRM_CALC, MAJOR_CONT, MOLES_NOX, PLUME_VOL, RELDISP y AERMAX.
calc2.f: SUMBACK_NO2 y SUMVALPSD.

Las concentraciones de cada fuente en cada receptor (CHI, y para PVMRM la altura del penacho,
el viento efectivo, la disipación, la fracción penetrada y FOPT) las guardan los bucles de
receptores de calc1/calc1_pv; aquí se aplica la conversión NO -> NO2 y se suman a los grupos."""
import math

import numpy as np

from . import calculo_area, funciones_dispersion, parametros_efectivos, perfiles, resultados, sigmas
from .estado import NoTraducido
from .formato import fread, fwrite, lread
from .meteo_horaria import cent_date2

_NTAB = 59
_XTABLE = (0.0, 10.0, 20.0, 30.0, 40.0, 50.0, 60.0, 70.0, 80.0, 90.0, 100.0,
           120.0, 140.0, 160.0, 180.0, 200.0,
           250.0, 300.0, 350.0, 400.0, 450.0, 500.0,
           600.0, 700.0, 800.0, 900.0, 1000.0,
           1200.0, 1400.0, 1600.0, 1800.0, 2000.0,
           2500.0, 3000.0, 3500.0, 4000.0, 4500.0, 5000.0,
           6000.0, 7000.0, 8000.0, 9000.0, 10000.0,
           12000.0, 14000.0, 16000.0, 18000.0, 20000.0,
           25000.0, 30000.0, 35000.0, 40000.0, 45000.0, 50000.0,
           60000.0, 70000.0, 80000.0, 90000.0, 100000.0,
           500000.0)
_ARM2_COEF = (0.0, -1.1723e-17, 4.2795e-14, 5.8345e-11, 3.4555e-08, 5.6062e-06, 2.7383e-03,
              1.2441e+00)


def _quimica(e):
    return e.PVMRM or e.OLM or e.ARM2 or e.RUNTTRM or e.GRSM


# ========================================================================= fondo de la hora
def _leer(e, unidad, forma, previos):
    """READ(u,*) o READ(u,forma) de (año, mes, día, hora, valor). Devuelve (valores, iostat)."""
    u = e.U[int(unidad)]
    if u.ptr >= len(u.regs):
        return None, -1
    regs = u.regs[u.ptr:u.ptr + 20]
    tipos = ("i", "i", "i", "i", "f")
    if forma == "FREE":
        vals, ios, nr = lread(regs, tipos, previos)
    else:
        vals, ios, nr = fread(forma, regs, tipos)
    u.ptr += nr
    if ios == 0:
        previos[:] = vals
    return vals, ios


def o3ext(e):
    """O3EXT: ozono de fondo de la hora desde el fichero horario del sector en curso (los de los
    demás sectores se leen para mantenerlos sincronizados), con el mínimo de las horas estables y
    la sustitución de los valores ausentes. Devuelve (L_ReadErr, ReadErr, EndErr)."""
    m = "O3EXT"
    readerr = enderr = ""
    full = [0] * 7
    e.O3MISS = False
    e.ILINE = e.IOLINE
    e.O3CONC = 0.0
    o3sub = [-99.0] * 7
    o3min = -99.0
    prev = getattr(e, "_O3_PREVIOS", None)
    if prev is None:
        prev = e._O3_PREVIOS = [0, 0, 0, 0, 0.0]
    from .funciones_dispersion import ozonvals
    for i in range(1, e.NUMO3SECTS + 1):
        o3sub[i] = -99.0
        if e.L_O3VALUES[i]:
            o3sub[i] = ozonvals(e, i, o3sub[i])
        elif e.L_O3VAL[i]:
            o3sub[i] = e.O3BACK[i]
        else:
            o3sub[i] = 0.0
        if not e.L_O3FILE[i]:
            continue
        readerr = fwrite("('SECT',I1)", i)[0]
        vals, ios = _leer(e, e.IO3UNT[i], e.O3FORM[i], prev)
        if ios < 0:
            e.EOF = True
            enderr = fwrite("('SECT',I1)", i)[0]
            continue
        if ios > 0:
            e.errhdl(e.PATH, m, "E", "510", readerr)
            e.RUNERR = True
            return True, readerr, enderr
        iyr, imn, idy, ihr, val = vals
        if iyr <= 99:
            _d, iyr = cent_date2(e, 0, iyr)
        full[i] = iyr * 1000000 + imn * 10000 + idy * 100 + ihr
        if i == e.IO3SECT:
            e.O3CONC = val
            if 0.0 <= e.O3CONC < 900.0:
                if e.O3FILUNITS == "PPB":
                    e.O3CONC = e.O3CONC * e.O3_PPB
                elif e.O3FILUNITS == "PPM":
                    e.O3CONC = e.O3CONC * e.O3_PPM
                if not e.NOMINO3:
                    if e.STABLE:
                        o3max24 = min(78.40, float(e.O3_MAX24HR[1:, e.IO3SECT].max()))
                        if 0.0 < e.OBULEN <= 50.0:
                            o3min = o3max24
                        elif e.OBULEN > 250.0:
                            o3min = 0.0
                        else:
                            o3min = o3max24 * (250.0 - e.OBULEN) / 200.0
                    else:
                        o3min = -9.0
                    e.O3_MAX24HR[ihr, e.IO3SECT] = e.O3CONC
                    e.O3CONC = max(e.O3CONC, o3min)
            elif e.L_O3VALUES[e.IO3SECT] or e.L_O3VAL[e.IO3SECT]:
                e.O3CONC = o3sub[e.IO3SECT]
                e.O3_MAX24HR[ihr, e.IO3SECT] = 0.0
            else:
                e.O3MISS = True
                e.O3_MAX24HR[ihr, e.IO3SECT] = 0.0
        else:
            o3temp = val
            if 0.0 <= o3temp < 900.0:
                if e.O3FILUNITS == "PPB":
                    o3temp = o3temp * e.O3_PPB
                elif e.O3FILUNITS == "PPM":
                    o3temp = o3temp * e.O3_PPM
                e.O3_MAX24HR[ihr, i] = o3temp
            else:
                e.O3_MAX24HR[ihr, i] = 0.0
    if e.O3MISS:
        e.O3CONC = 0.0
        if not e.L_SKIPMESSAGES:
            e.errhdl(e.PATH, m, "I", "459", fwrite("(I10.10)", e.FULLDATE)[0])
    for i in range(1, e.NUMO3SECTS + 1):
        if e.L_O3FILE[i] and e.FULLDATE != full[i]:
            e.errhdl(e.PATH, m, "E", "457", fwrite("(I10.10,'S',I1)", e.FULLDATE, i)[0])
            e.RUNERR = True
            break
    return False, readerr, enderr


def noxext(e):
    """NOXEXT: NOx de fondo de la hora desde el fichero horario del sector en curso (GRSM).
    Devuelve (L_ReadErr, ReadErr, EndErr)."""
    m = "NOXEXT"
    readerr = enderr = ""
    full = [0] * 7
    e.NOXMISS = False
    e.ILINE = e.INOXLINE
    e.NOXBGCONC = 0.0
    noxsub = [-99.0] * 7
    prev = getattr(e, "_NOX_PREVIOS", None)
    if prev is None:
        prev = e._NOX_PREVIOS = [0, 0, 0, 0, 0.0]
    from .funciones_dispersion import varynoxvals
    for i in range(1, e.NUMNOXSECTS + 1):
        noxsub[i] = -99.0
        if e.L_NOX_VALS[i]:
            noxsub[i] = varynoxvals(e, i, noxsub[i])
        elif e.L_NOXVALUE[i]:
            noxsub[i] = e.NOXBACK[i]
        else:
            noxsub[i] = 0.0
        if not e.L_NOXFILE[i]:
            continue
        readerr = fwrite("('SECT',I1)", i)[0]
        vals, ios = _leer(e, e.INOXUNT[i], e.NOXFORM[i], prev)
        if ios < 0:
            e.EOF = True
            enderr = fwrite("('SECT',I1)", i)[0]
            continue
        if ios > 0:
            e.errhdl(e.PATH, m, "E", "510", readerr)
            e.RUNERR = True
            return True, readerr, enderr
        iyr, imn, idy, ihr, val = vals
        if iyr <= 99:
            _d, iyr = cent_date2(e, 0, iyr)
        full[i] = iyr * 1000000 + imn * 10000 + idy * 100 + ihr
        if i == e.INOXSECT:
            e.NOXBGCONC = val
            if e.NOXBGCONC >= 0.0:
                if e.NOXFILUNITS == "PPB":
                    e.NOXBGCONC = e.NOXBGCONC / e.NO2_PPB
                elif e.NOXFILUNITS == "PPM":
                    e.NOXBGCONC = e.NOXBGCONC / e.NO2_PPM
                e.NOXBGCONC = max(e.NOXBGCONC, 0.0)
            elif e.L_NOX_VALS[e.INOXSECT] or e.L_NOXVALUE[e.INOXSECT]:
                e.NOXBGCONC = noxsub[e.INOXSECT]
            else:
                e.NOXMISS = True
    if e.NOXMISS:
        e.NOXBGCONC = 0.0
        if not e.L_SKIPMESSAGES:
            e.errhdl(e.PATH, m, "I", "609", fwrite("(I10.10)", e.FULLDATE)[0])
    for i in range(1, e.NUMNOXSECTS + 1):
        if e.L_NOXFILE[i] and e.FULLDATE != full[i]:
            e.errhdl(e.PATH, m, "E", "608", fwrite("(I10.10,'S',I1)", e.FULLDATE, i)[0])
            e.RUNERR = True
            break
    return False, readerr, enderr


def fondo_hora(e):
    """Paso de HRLOOP con química del NO2: ozono (OLM/PVMRM/TTRM/GRSM) y NOx (GRSM) de fondo de la
    hora, desde fichero horario o desde los valores fijos o variables por sector."""
    from .funciones_dispersion import ozonvals, varynoxvals
    m = "HRLOOP"
    if e.RUNTTRM2:
        raise NoTraducido("TTRM2")
    if e.PVMRM or e.OLM or e.RUNTTRM or e.GRSM:
        if e.L_O3HOURLY:
            e.IOLINE += 1
            if not e.EOF:
                l_err, e._O3_READERR, e._O3_ENDERR = o3ext(e)
            else:
                l_err = False
            if e.EOF:
                e.errhdl(e.PATH, m, "E", "580",
                         fwrite("('O3FILE ',A5)", getattr(e, "_O3_ENDERR", ""))[0])
                e.RUNERR = True
            elif l_err:
                e.errhdl(e.PATH, m, "E", "510", fwrite("('O3FILE ',A5)", e._O3_READERR)[0])
                e.RUNERR = True
        elif e.IO3SECT > 0:
            if e.L_O3VALUES[e.IO3SECT]:
                e.O3CONC = ozonvals(e, e.IO3SECT, e.O3CONC)
            elif e.L_O3VAL[e.IO3SECT]:
                e.O3CONC = e.O3BACK[e.IO3SECT]
            else:
                e.O3CONC = 0.0
        else:
            e.O3CONC = 0.0
        if not e.RSTINP and e.L_MAXDCONT and e.FULLDATE >= e.ISDATE:
            e.AO3CONC[e.IHR_NDX, e.IYR_NDX] = -9.0 if e.O3MISS else e.O3CONC
    if e.GRSM:
        if e.L_NOXHOURLY:
            e.INOXLINE += 1
            if not e.EOF:
                l_err, e._NOX_READERR, e._NOX_ENDERR = noxext(e)
            else:
                l_err = False
            if e.EOF:
                e.errhdl(e.PATH, m, "E", "580",
                         fwrite("('NOXFIL ',A5)", getattr(e, "_NOX_ENDERR", ""))[0])
                e.RUNERR = True
            elif l_err:
                e.errhdl(e.PATH, m, "E", "510", fwrite("('NOXFIL ',A5)", e._NOX_READERR)[0])
                e.RUNERR = True
        elif e.INOXSECT > 0:
            if e.L_NOX_VALS[e.INOXSECT]:
                e.NOXBGCONC = varynoxvals(e, e.INOXSECT, e.NOXBGCONC)
            elif e.L_NOXVALUE[e.INOXSECT]:
                e.NOXBGCONC = e.NOXBACK[e.INOXSECT]
            else:
                e.NOXBGCONC = 0.0
        else:
            e.NOXBGCONC = 0.0
        if not e.RSTINP and e.L_MAXDCONT and e.FULLDATE >= e.ISDATE:
            e.ANOXBGCONC[e.IHR_NDX, e.IYR_NDX] = e.NOXBGCONC


def conversion(e):
    """HRLOOP, horas que no son de calma ni ausentes: aplica la opción de NO2."""
    if e.PVMRM and not e.PSDCREDIT:
        pvmrm_calc(e, "ALLSRCS")
    elif e.PVMRM and e.PSDCREDIT:
        pvmrm_calc(e, "NAAQSRC")
        pvmrm_calc(e, "ALLBASE")
    elif e.OLM:
        olm_calc(e)
    elif e.ARM2:
        arm2_calc(e)
    elif e.GRSM:
        from .quimica_cinetica import grsm_calc
        grsm_calc(e)
    elif e.RUNTTRM:
        ttrm_calc(e)


def vaciar(e):
    """Final de la hora en HRLOOP: pone a cero CHI (y ABVAL/BCVAL con PSDCREDIT)."""
    e.CHI[...] = 0.0
    if e.GRSM:
        e.CHI_TTRAVPLM = 0.0
        e.CHI_TTRAVPAN = 0.0
        e.CHI_TTRAVAER = 0.0
        e.CHI_TTRAVPRM = 0.0
        e.CHI_TTRAVCHM[...] = 0.0
        e.BLDFAC[...] = 0.0
        e.PRMVAL_SRC1 = 0.0
    if e.PSDCREDIT:
        e.ABVAL[...] = 0.0
        e.BCVAL[...] = 0.0


# ================================================================================ SUMBACK
def sumback_no2(e):
    """SUMBACK_NO2: suma el fondo de la hora al receptor IREC del grupo IGRP (si es positivo)."""
    igrp, irec = e.IGRP, e.IREC
    e.ITYP = 1
    if e.GRP_BACK[igrp] and e.BGCONC > 0.0:
        e.BACKAVE[igrp] = e.BACKAVE[igrp] + e.BGCONC * e.EMIFAC[1] / 1.0e6
        if e.PERIOD or e.ANNUAL:
            e.BACKANN[igrp] = e.BACKANN[igrp] + e.BGCONC * e.EMIFAC[1] / 1.0e6
        if e.ISEAHR[igrp] == 1:
            e.BACKSEASHR[igrp, e.ISEAS, e.IHOUR] = e.BACKSEASHR[igrp, e.ISEAS, e.IHOUR] + \
                e.BGCONC * e.EMIFAC[1] / 1.0e6
        for iave in range(1, e.NUMAVE + 1):
            e.AVEVAL[irec, igrp, iave, 1] = e.BGCONC * e.EMIFAC[1] / 1.0e6 + e.AVEVAL[irec, igrp, iave, 1]
        e.IAVE = e.NUMAVE + 1
        if e.PERIOD or e.ANNUAL:
            e.ANNVAL[irec, igrp, 1] = e.BGCONC * e.EMIFAC[1] / 1.0e6 + e.ANNVAL[irec, igrp, 1]
        if e.ISEAHR[igrp] == 1:
            e.SHVALS[irec, igrp, e.ISEAS, e.IHOUR, 1] = e.BGCONC * e.EMIFAC[1] / 1.0e6 + \
                e.SHVALS[irec, igrp, e.ISEAS, e.IHOUR, 1]


# ===================================================================================== OLM
def olm_calc(e):
    """OLM_CALC: método de limitación por ozono, fuente a fuente o por OLMGROUP."""
    from .resultados import sumval
    nt, ns, numolm = e.NUMTYP, e.NUMSRC, e.NUMOLM
    chi, ratio = e.CHI, e.ANO2_RATIO
    eq = e.NO2EQUIL
    e.HRVAL[:] = 0.0
    if numolm >= 1:
        olmval = np.zeros((numolm + 1, nt + 1))
        no2val = np.zeros(numolm + 1)
        no_val = np.zeros(numolm + 1)
        pct_g = np.zeros(numolm + 1)
    e.IOLM = 0
    if e.EVONLY:
        raise NoTraducido("EVENT")
    for irec in range(1, e.NUMREC + 1):
        e.IREC = irec
        if numolm >= 1:
            olmval[:] = 0.0
            no2val[:] = 0.0
            no_val[:] = 0.0
            pct_g[:] = 0.0
            for iolm in range(1, numolm + 1):
                e.IOLM = iolm
                for isrc in range(1, ns + 1):
                    if e.L_OLMGRP[isrc] and e.IGRP_OLM[isrc, iolm] == 1:
                        no2val[iolm] = no2val[iolm] + ratio[isrc] * chi[irec, isrc, 1]
                        no_val[iolm] = no_val[iolm] + (1.0 - ratio[isrc]) * chi[irec, isrc, 1] * \
                            (30.0 / 46.0)
                        for ityp in range(1, nt + 1):
                            olmval[iolm, ityp] = olmval[iolm, ityp] + chi[irec, isrc, ityp]
                if not e.O3MISS and (e.O3CONC / 48.0) < (no_val[iolm] / 30.0):
                    olmtemp = no2val[iolm] + (e.O3CONC * (46.0 / 48.0))
                    if olmval[iolm, 1] > 0.0:
                        pct_g[iolm] = olmtemp / olmval[iolm, 1]
                    else:
                        pct_g[iolm] = eq
                else:
                    pct_g[iolm] = 1.0
                pct_g[iolm] = min(pct_g[iolm], 1.0)
                if pct_g[iolm] > eq:
                    pct_g[iolm] = eq
            e.ISRC = ns + 1
            e.IOLM = numolm + 1
        for igrp in range(1, e.NUMGRP + 1):
            e.IGRP = igrp
            for isrc in range(1, ns + 1):
                e.ISRC = isrc
                if e.IGROUP[isrc, igrp] != 1:
                    continue
                if e.L_OLMGRP is not None and e.L_OLMGRP[isrc]:
                    for iolm in range(1, numolm + 1):
                        e.IOLM = iolm
                        if e.IGRP_OLM[isrc, iolm] == 1:
                            for ityp in range(1, nt + 1):
                                e.HRVAL[ityp] = pct_g[iolm] * chi[irec, isrc, ityp]
                            break
                    else:
                        e.IOLM = numolm + 1
                    sumval(e)
                else:
                    c1 = chi[irec, isrc, 1]
                    no2 = ratio[isrc] * c1
                    no = (1.0 - ratio[isrc]) * c1 * (30.0 / 46.0)
                    if not e.O3MISS and (e.O3CONC / 48.0) < (no / 30.0):
                        e.HRVAL[1] = no2 + (e.O3CONC * (46.0 / 48.0))
                    else:
                        e.HRVAL[1] = c1
                    if c1 > 0.0:
                        pct = e.HRVAL[1] / c1
                    else:
                        pct = eq
                    pct = min(pct, 1.0)
                    if pct > eq:
                        pct = eq
                    for ityp in range(1, nt + 1):
                        e.HRVAL[ityp] = pct * chi[irec, isrc, ityp]
                    sumval(e)
                    e.IOLM = 0
                if e.EVAL[isrc]:
                    raise NoTraducido("EVALFILE")
            e.ISRC = ns + 1
            if e.GRP_BACK[igrp]:
                sumback_no2(e)
        e.IGRP = e.NUMGRP + 1
        e.HRVAL[:] = 0.0
    e.IREC = e.NUMREC + 1


# ==================================================================================== TTRM
def _cociente(a, b):
    """DABS(a/b) si b > 0; 0 si no (tiempo de viaje de TTRM_STEP)."""
    if b > 0.0:
        return abs(a / b)
    return 0.0


def _ttrm_step(e):
    """TTRM_STEP: tiempo de viaje de la fuente ISRC al receptor IREC según el tipo de fuente, la
    componente dominante del penacho (serpenteo o coherente, directa, indirecta o penetrada) y la
    estabilidad, con los valores guardados en TTRMOUT por los bucles de receptores."""
    t = e.SRCTYP[e.ISRC]
    o = e.TTRMOUT[e.IREC, e.ISRC]
    if t[:5] == "POINT":
        if e.WAKE and (e.STABLE or e.HS <= e.ZI):
            e.TTRMTIME_PRM = _cociente(o[10], o[24])
            o[25] = e.TTRMTIME_PRM
        if o[15] >= 0.5:
            # serpenteo dominante: distancia radial
            d = o[11]
        elif o[10] >= 0.0:
            # penacho coherente a sotavento: distancia a favor del viento
            d = o[10]
        else:
            d = o[11]
        if e.STABLE:
            e.TTRMTIME = _cociente(d, o[12])
        elif o[16] >= 0.5:
            e.TTRMTIME = _cociente(d, o[14])
        elif o[19] >= o[18]:
            e.TTRMTIME = _cociente(d, o[13])
        else:
            e.TTRMTIME = _cociente(d, o[12])
    elif t == "VOLUME":
        if o[15] >= 0.5:
            d = o[11]
        elif o[10] >= 0.0:
            d = o[10]
        else:
            d = o[11]
        if e.STABLE:
            e.TTRMTIME = _cociente(d, o[12])
        elif o[13] > o[12]:
            e.TTRMTIME = _cociente(d, o[13])
        else:
            e.TTRMTIME = _cociente(d, o[12])
    elif t[:4] == "AREA":
        if e.STABLE:
            e.TTRMTIME = _cociente(o[11], o[12])
        elif o[13] > o[12]:
            e.TTRMTIME = _cociente(o[11], o[13])
        else:
            e.TTRMTIME = _cociente(o[11], o[12])


def ttrm_calc(e):
    """TTRM_CALC: método de reacción según el tiempo de viaje (conversión NO -> NO2 por el ozono
    durante el transporte de cada fuente a cada receptor)."""
    from .resultados import sumval
    if e.EVONLY:
        raise NoTraducido("EVENT")
    if e.TTRMDBG:
        raise NoTraducido("TTRMDEBUG")
    nt, ns = e.NUMTYP, e.NUMSRC
    chi, ratio = e.CHI, e.ANO2_RATIO
    eq = e.NO2EQUIL
    c1533 = float(np.float32(15.33))
    e.HRVAL[:] = 0.0
    e.ITTRM = 0
    e.TTRMTIME = 0.0
    e.TTRMTIME_PRM = 0.0
    e.GAMF = 0.0
    for n in ("TTRMINST", "TTRMFRAC", "TTRMFRAC_PRM", "TTRMFRAC_AER", "TTRMNO2", "TTRMSUB"):
        getattr(e, n)[:] = 0.0
    frac, frac_prm, frac_aer = e.TTRMFRAC, e.TTRMFRAC_PRM, e.TTRMFRAC_AER
    tno2, tsub = e.TTRMNO2, e.TTRMSUB
    for irec in range(1, e.NUMREC + 1):
        e.IREC = irec
        e.TTRMTIME = 0.0
        e.TTRMTIME_PRM = 0.0
        for igrp in range(1, e.NUMGRP + 1):
            e.IGRP = igrp
            for isrc in range(1, ns + 1):
                e.ISRC = isrc
                if e.IGROUP[isrc, igrp] != 1:
                    continue
                e.K1 = (c1533 / e.TA) * math.exp(-1450.0 / e.TA)
                o3ppb = e.O3CONC / e.O3_PPB
                ko3 = -1.0 * e.K1 * o3ppb
                no2 = ratio[isrc] * chi[irec, isrc, 1]
                nox = (1.0 - ratio[isrc]) * chi[irec, isrc, 1]
                t = e.SRCTYP[isrc]
                if t[:5] == "POINT" or t == "VOLUME" or t[:4] == "AREA":
                    _ttrm_step(e)
                    e.GAMF = e.TTRMOUT[irec, isrc, 17]
                    if not e.O3MISS:
                        for ityp in range(1, nt + 1):
                            if e.TTRMTIME > 0.0:
                                frac[ityp] = 1.0 - math.exp(ko3 * e.TTRMTIME)
                            else:
                                frac[ityp] = 0.0
                            if frac[ityp] >= eq:
                                frac[ityp] = eq
                                e.HRVAL[ityp] = eq * chi[irec, isrc, ityp]
                                no2 = 0.0
                                nox = chi[irec, isrc, ityp]
                                tsub[ityp] = e.HRVAL[ityp]
                            else:
                                tno2[ityp] = frac[ityp] * nox
                                e.HRVAL[ityp] = tno2[ityp] + no2
                                tsub[ityp] = e.HRVAL[ityp]
                            if e.WAKE and (e.STABLE or e.HS <= e.ZI):
                                frac_aer[ityp] = frac[ityp]
                                if e.TTRMTIME_PRM > 0.0:
                                    frac_prm[ityp] = 1.0 - math.exp(ko3 * e.TTRMTIME_PRM)
                                    if frac_prm[ityp] >= eq:
                                        frac_prm[ityp] = eq
                                else:
                                    frac_prm[ityp] = 0.0
                                frac[ityp] = e.GAMF * frac_prm[ityp] + (1.0 - e.GAMF) * frac_aer[ityp]
                                tno2[ityp] = frac[ityp] * nox
                                e.HRVAL[ityp] = tno2[ityp] + no2
                                tsub[ityp] = e.HRVAL[ityp]
                    else:
                        for ityp in range(1, nt + 1):
                            e.HRVAL[ityp] = eq * chi[irec, isrc, ityp]
                            tsub[ityp] = e.HRVAL[ityp]
                else:
                    for ityp in range(1, nt + 1):
                        e.HRVAL[ityp] = eq * chi[irec, isrc, ityp]
                        tsub[ityp] = e.HRVAL[ityp]
                        if not e.L_TTRMSRCTYP[isrc]:
                            e.errhdl(e.PATH, "TTRM_CALC", "W", "710", e.SRCID[isrc])
                            e.L_TTRMSRCTYP[isrc] = True
                sumval(e)
                if e.EVAL[isrc]:
                    raise NoTraducido("EVALFILE")
            e.ISRC = ns + 1
            if e.GRP_BACK[igrp]:
                sumback_no2(e)
        e.IGRP = e.NUMGRP + 1
        e.HRVAL[:] = 0.0
    e.IREC = e.NUMREC + 1


# ==================================================================================== ARM2
def _arm2_razon(x):
    """Polinomio de ARM2 con las potencias enteras desarrolladas en productos, como el original."""
    c = _ARM2_COEF
    x2 = x * x
    x3 = x2 * x
    x4 = x2 * x2
    x5 = x4 * x
    x6 = x3 * x3
    return (c[1] * x6) + (c[2] * x5) - (c[3] * x4) + (c[4] * x3) - (c[5] * x2) - c[6] * x + c[7]


def arm2_calc(e):
    """ARM2_CALC: método de la razón ambiental (versión 2) con el NOx total en cada receptor."""
    from .resultados import sumval
    nt, ns, nsrc = e.NUMTYP, e.NUMSRC, e.NSRC
    chi = e.CHI
    e.HRVAL[:] = 0.0
    e.RATIOARM2 = 0.0
    if e.EVONLY:
        raise NoTraducido("EVENT")
    # SUM(CHI, DIM=2): todas las fuentes reservadas, en orden
    noxconc = chi[:, 1, :].copy()
    for k in range(2, nsrc + 1):
        noxconc = noxconc + chi[:, k, :]
    for irec in range(1, e.NUMREC + 1):
        e.IREC = irec
        r = _arm2_razon(noxconc[irec, 1])
        if r > e.ARM2_MAX:
            r = e.ARM2_MAX
        elif r < e.ARM2_MIN:
            r = e.ARM2_MIN
        e.RATIOARM2 = r
        for igrp in range(1, e.NUMGRP + 1):
            e.IGRP = igrp
            for isrc in range(1, ns + 1):
                e.ISRC = isrc
                for ityp in range(1, nt + 1):
                    e.HRVAL[ityp] = chi[irec, isrc, ityp] * r
                sumval(e)
            e.ISRC = ns + 1
            if e.GRP_BACK[igrp]:
                sumback_no2(e)
        e.IGRP = e.NUMGRP + 1
    e.IREC = e.NUMREC + 1


# =================================================================================== PVMRM
# Conjuntos de fuentes de PVMRM_CALC (SRCS2USE): todas, las de consumo de incremento y las de
# base (PSDCREDIT). Tipos de fuente PSD en e.PSDC: 1 = IC, 2 = NB, 3 = RB.
_ALLSRCS, _NAAQSRC, _ALLBASE = 0, 1, 2
_CODIGO_SRCS = {"ALLSRCS": _ALLSRCS, "NAAQSRC": _NAAQSRC, "ALLBASE": _ALLBASE}
_CODIGO_PSD = {"IC": 1, "NB": 2, "RB": 3}


def sumvalpsd(e, srcs):
    """SUMVALPSD: suma ABVAL (NAAQS) o ABVAL-BCVAL (incremento PSD) al receptor IREC."""
    irec = e.IREC
    for ityp in range(1, e.NUMTYP + 1):
        for iave in range(1, e.NUMAVE + 1):
            if srcs == 1:
                e.AVEVAL[irec, 1, iave, ityp] = e.ABVAL[irec, ityp] + e.AVEVAL[irec, 1, iave, ityp]
            elif srcs == 2:
                e.AVEVAL[irec, 2, iave, ityp] = (e.ABVAL[irec, ityp] - e.BCVAL[irec, ityp]) + \
                    e.AVEVAL[irec, 2, iave, ityp]
        e.IAVE = e.NUMAVE + 1
        if e.PERIOD or e.ANNUAL:
            if srcs == 1:
                e.ANNVAL[irec, 1, ityp] = e.ABVAL[irec, ityp] + e.ANNVAL[irec, 1, ityp]
            elif srcs == 2:
                e.ANNVAL[irec, 2, ityp] = (e.ABVAL[irec, ityp] - e.BCVAL[irec, ityp]) + \
                    e.ANNVAL[irec, 2, ityp]
    e.ITYP = e.NUMTYP + 1


def aermax(e, srcs):
    """AERMAX: concentración máxima y fuente dominante en cada receptor entre las fuentes del
    grupo PSD indicado (1: IC y NB; 2: NB y RB)."""
    nr, nt = e.NUMREC, e.NUMTYP
    maxarg = np.zeros((nr + 1, nt + 1))
    domarg = np.zeros((nr + 1, nt + 1), dtype=np.int64)
    for i in range(1, nt + 1):
        for j in range(1, nr + 1):
            for k in range(1, e.NUMSRC + 1):
                c = e.PSDC[k]
                if (srcs == 1 and (c == 1 or c == 2)) or (srcs == 2 and (c == 2 or c == 3)):
                    if e.CHI[j, k, i] > maxarg[j, i]:
                        maxarg[j, i] = e.CHI[j, k, i]
                        domarg[j, i] = k
    return maxarg, domarg


def _maxloc_fuentes(e):
    """MAXVAL(CHI, DIM=2) y MAXLOC(CHI, DIM=2) sobre todas las fuentes reservadas (primera en caso
    de empate)."""
    c = e.CHI[:, 1:e.NSRC + 1, :]
    idx = np.argmax(c, axis=1) + 1
    return c.max(axis=1), idx.astype(np.int64)


def _major_cont(e, maxconc, idom):
    """MAJOR_CONT: extensión transversal y longitudinal y alturas de las fuentes que aportan al
    menos la mitad de la concentración máxima en el receptor."""
    isrc, irec = e.ISRC, e.IREC
    if not (e.CHI[irec, isrc, 1] >= 0.5 * maxconc):
        return
    t = e.SRCTYP[isrc]
    if t[:4] == "AREA" or t == "LINE":
        calculo_area.setsrc(e)
        calculo_area.ardist(e, irec)
        if e.DISTR > e.MAXDIST:
            return
        _contar(e, False)
    elif t == "OPENPIT":
        raise NoTraducido("OPENPIT")
    else:
        calculo_area.setsrc(e)
        funciones_dispersion.xydist(e, irec)
        if e.DISTR > e.MAXDIST:
            return
        _contar(e, e.PPFACT[irec, isrc] > 0.0)
    if e.L_FLATSRC[idom]:
        e.ZRT = e.ZFLAG
    else:
        e.ZRT = e.ZELEV - e.AZS[idom] + e.ZFLAG
    h = e.HECNTR[irec, isrc]
    if h < e.HMNT:
        e.HMNT = h
    if h > e.HMXT:
        e.HMXT = h
    if (h - e.ZRT) < e.HMNH:
        e.HMNH = h - e.ZRT
    if (h - e.ZRT) > e.HMXH:
        e.HMXH = h - e.ZRT
    if e.PPFACT[irec, isrc] > 0.0:
        h3 = e.HECNTR3[irec, isrc]
        if h3 < e.HMNT3:
            e.HMNT3 = h3
        if h3 > e.HMXT3:
            e.HMXT3 = h3
        if (h3 - e.ZRT) < e.HMNH3:
            e.HMNH3 = h3 - e.ZRT
        if (h3 - e.ZRT) > e.HMXH3:
            e.HMXH3 = h3 - e.ZRT


def _fmax(a, b):
    if a >= b:
        return a
    return b


def _fmin(a, b):
    if a <= b:
        return a
    return b


def _contar(e, tercera):
    e.NUMCONT += 1
    e.CWMAX = _fmax(e.CWMAX, e.Y)
    e.CWMIN = _fmin(e.CWMIN, e.Y)
    e.DWMAX = _fmax(e.DWMAX, e.X)
    e.DWMIN = _fmin(e.DWMIN, e.X)
    if e.DWMAX < 1.0:
        e.DWMAX = 1.0
    if e.DWMIN < 1.0:
        e.DWMIN = 1.0
    if tercera:
        e.CWMAX3 = _fmax(e.CWMAX3, e.Y)
        e.CWMIN3 = _fmin(e.CWMIN3, e.Y)
        e.DWMAX3 = _fmax(e.DWMAX3, e.X)
        e.DWMIN3 = _fmin(e.DWMIN3, e.X)
        if e.DWMAX3 < 1.0:
            e.DWMAX3 = 1.0
        if e.DWMIN3 < 1.0:
            e.DWMIN3 = 1.0


def _moles_nox(e, idom):
    """MOLES_NOX: emisión de NOx de las fuentes que caen dentro del volumen combinado. QTK de cada
    fuente es el de EMFACT de la hora (precalculado en e.QTKSRC)."""
    eps = 1.0e-5
    isrc, irec = e.ISRC, e.IREC
    t = e.SRCTYP[isrc]
    calculo_area.setsrc(e)
    e.QTK = e.QTKSRC[isrc]
    if t[:4] == "AREA" or t == "LINE":
        calculo_area.ardist(e, irec)
    elif t == "OPENPIT":
        raise NoTraducido("OPENPIT")
    else:
        funciones_dispersion.xydist(e, irec)
    cwdist = e.Y
    dwdist = max(e.X, 1.0)
    fdom = e.FOPTS[irec, idom]
    h = e.HECNTR[irec, isrc]
    r = e.ANO2_RATIO[isrc]
    area = t == "AREA" or t == "AREAPOLY" or t == "LINE"
    circ = t == "AREACIRC"
    if (e.CWMIN - eps <= cwdist <= e.CWMAX + eps) and (e.DWMIN - eps <= dwdist <= e.DWMAX + eps):
        if e.HMNT - eps <= h <= e.HMXT + eps:
            if area:
                qarea = e.QTK * e.XINIT * e.YINIT
                e.QSUM = e.QSUM + qarea * (1.0 - fdom)
                e.SUM_NO2RAT = e.SUM_NO2RAT + r * qarea * (1.0 - fdom)
            elif circ:
                qarea = e.QTK * e.PI * e.RADIUS[isrc] * e.RADIUS[isrc]
                e.QSUM = e.QSUM + qarea * (1.0 - fdom)
                e.SUM_NO2RAT = e.SUM_NO2RAT + r * qarea * (1.0 - fdom)
            else:
                pp = e.PPFACT[irec, isrc]
                e.QSUM = e.QSUM + e.QTK * (1.0 - pp) * (1.0 - fdom)
                e.SUM_NO2RAT = e.SUM_NO2RAT + r * e.QTK * (1.0 - pp) * (1.0 - fdom)
        if e.HMNH - eps <= (h - e.ZRT) <= e.HMXH + eps:
            if area:
                qarea = e.QTK * e.XINIT * e.YINIT
                e.QSUM = e.QSUM + qarea * fdom
                e.SUM_NO2RAT = e.SUM_NO2RAT + r * qarea * fdom
            elif circ:
                qarea = e.QTK * e.PI * e.RADIUS[isrc] * e.RADIUS[isrc]
                e.QSUM = e.QSUM + qarea * fdom
                e.SUM_NO2RAT = e.SUM_NO2RAT + r * qarea * fdom
            else:
                pp = e.PPFACT[irec, isrc]
                e.QSUM = e.QSUM + e.QTK * (1.0 - pp) * fdom
                e.SUM_NO2RAT = e.SUM_NO2RAT + r * e.QTK * (1.0 - pp) * fdom
    if (e.CWMIN3 - eps <= cwdist <= e.CWMAX3 + eps) and (e.DWMIN3 - eps <= dwdist <= e.DWMAX3 + eps):
        h3 = e.HECNTR3[irec, isrc]
        pp = e.PPFACT[irec, isrc]
        if e.HMNT3 - eps <= h3 <= e.HMXT3 + eps:
            if t[:5] == "POINT":
                e.QSUM3 = e.QSUM3 + e.QTK * pp * (1.0 - fdom)
                e.SUM3_NO2RAT = e.SUM3_NO2RAT + r * e.QTK * pp * (1.0 - fdom)
        if e.HMNH3 - eps <= (h3 - e.ZRT) <= e.HMXH3 + eps:
            if t[:5] == "POINT":
                e.QSUM3 = e.QSUM3 + e.QTK * pp * fdom
                e.SUM3_NO2RAT = e.SUM3_NO2RAT + r * e.QTK * pp * fdom


def _reldisp(e, xarg):
    """RELDISP: dispersión relativa del penacho (Weil). Devuelve (SROUT, SROUT3)."""
    a1 = 0.57
    a2 = 0.62 * a1
    ar1 = 0.46
    if e.SZINIT >= 1.0e-8:
        if e.SYINIT >= 1.0e-8:
            vsigr = math.sqrt(e.SYINIT * e.SZINIT)
        else:
            vsigr = e.SZINIT
    elif e.SZINIT < 1.0e-8:
        if e.SYINIT >= 1.0e-8:
            vsigr = e.SYINIT
        else:
            vsigr = 0.0
    else:
        vsigr = 0.0
    v3 = vsigr * vsigr * vsigr
    srout = 0.0
    srout3 = 0.0
    if e.STABLE or (e.UNSTAB and e.HS >= e.ZI):
        tlr = ar1 * e.ZI / e.SWEFF
        sramb = (a1 * math.sqrt(e.EPSEFF) * (xarg / e.UEFF) ** 1.5) / (1.0 + a2 * xarg / (e.UEFF * tlr))
        srout = (sramb * sramb * sramb + e.SZB * e.SZB * e.SZB + v3) ** e.THIRD
    elif e.UNSTAB:
        tlr = ar1 * e.ZI / e.SWEFFD
        sramb = (a1 * math.sqrt(e.EPSEFFD) * (xarg / e.UEFFD) ** 1.5) / (1.0 + a2 * xarg / (e.UEFFD * tlr))
        srout = (sramb * sramb * sramb + e.SZBD * e.SZBD * e.SZBD + v3) ** e.THIRD
        if e.PPFACT[e.IREC, e.ISRC] > 0.0:
            tlr = ar1 * e.ZI / e.SWEFF3
            sramb3 = (a1 * math.sqrt(e.EPSEFF3) * (xarg / e.UEFF3) ** 1.5) / \
                (1.0 + a2 * xarg / (e.UEFF3 * tlr))
            srout3 = (sramb3 * sramb3 * sramb3 + e.SZB3 * e.SZB3 * e.SZB3 + v3) ** e.THIRD
    return srout, srout3


def _plume_vol(e, xarg, irdx, isdx, bvarg, bvarg3, bharg, bharg3):
    """PLUME_VOL: volumen del penacho de la fuente ISDX hasta la distancia XARG (integrado por
    tramos de la tabla de distancias), ampliado con las extensiones BV/BH de las fuentes que
    aportan. Devuelve VOLOUT."""
    nsubzs = 1.282
    srmins = 15.0
    nsubzu = 2.58
    srminu = 9.0
    e.ISRC = isdx
    e.IREC = irdx
    isrc = isdx
    irec = irdx
    suma = 0.0
    suma3 = 0.0
    sr = np.zeros(_NTAB + 1)
    sr3 = np.zeros(_NTAB + 1)
    sigr = 0.0
    sigr3 = 0.0
    srmin3 = 0.0
    if e.STABLE or (e.UNSTAB and e.AHS[isdx] >= e.ZI):
        srmin = srmins
        nsubz = nsubzs
    else:
        srmin = srminu
        nsubz = nsubzu
    if e.PVMRMDBG and e.DEBUG:
        raise NoTraducido("PVMRMDBG")
    calculo_area._met_urbana(e)
    calculo_area.setsrc(e)
    parametros_efectivos.metini(e)
    t = e.SRCTYP[isrc]
    aft_y = e.AFTSRC[isrc] == "Y"
    puntual = t[:5] == "POINT"
    if (t == "VOLUME" and not aft_y) or t == "LINE" or (t[:4] == "AREA" and not aft_y) or \
            t == "OPENPIT":
        e.FB = 0.0
        e.FM = 0.0
        e.PPF = 0.0
        e.HSP = e.HS
        e.DHP = 0.0
        e.DHP1 = 0.0
        e.DHP2 = 0.0
        e.DHP3 = 0.0
        e.DHCRIT = 0.0
        e.XFINAL = 0.0
        e.XMIXED = e.ZI * e.UAVG / e.SWAVG
        if e.XMIXED < e.XFINAL:
            e.XMIXED = e.XFINAL
        e.ZMIDMX = 0.5 * e.ZI
        e.CENTER = e.HECNTR[irec, isrc]
        e.SURFAC = e.CENTER < 0.1 * e.ZI
    elif t == "VOLUME" or (t == "AREA" and aft_y):
        raise NoTraducido("AIRCRAFT")
    elif puntual:
        vseq = calculo_area.fluxes(e)
        e.WAKE = False
        e.CENTER = e.HECNTR[irec, isrc]
        e.SURFAC = e.CENTER < 0.1 * e.ZI
        if t == "POINTCAP":
            e.HSP = sigmas.hsprim(e.US, vseq, e.HS, e.DS)
        elif t == "POINTHOR":
            e.HSP = e.HS
        elif e.NOSTD:
            e.HSP = e.HS
        else:
            e.HSP = sigmas.hsprim(e.US, e.VS, e.HS, e.DS)
        funciones_dispersion.distf(e)
        calculo_area.penfct(e)
        gh = e.GRIDHT
        if e.STABLE or (e.UNSTAB and e.HS >= e.ZI):
            kiter = 0
            while True:
                zplm = e.HSP + 0.5 * e.DHFAER
                dhfold = e.DHFAER
                n = perfiles.locate(gh, 1, e.MXGLVL, zplm)
                svpm = perfiles.gintrp(gh[n], e.GRIDSV[n], gh[n + 1], e.GRIDSV[n + 1], zplm)
                upm = perfiles.gintrp(gh[n], e.GRIDWS[n], gh[n + 1], e.GRIDWS[n + 1], zplm)
                svpm = max(svpm, e.SVMIN, e.SVUMIN * upm)
                if e.L_VECTORWS:
                    upm = math.sqrt(upm * upm + 2.0 * svpm * svpm)
                upm = max(upm, e.WSMIN)
                e.UP = 0.5 * (e.US + upm)
                tgpm = perfiles.gintrp(gh[n], e.GRIDTG[n], gh[n + 1], e.GRIDTG[n + 1], zplm)
                ptpm = perfiles.gintrp(gh[n], e.GRIDPT[n], gh[n + 1], e.GRIDPT[n + 1], zplm)
                e.TGP = 0.5 * (e.TGS + tgpm)
                ptp = 0.5 * (e.PTS + ptpm)
                e.BVF = math.sqrt(e.G * e.TGP / ptp)
                if e.BVF < 1.0e-10:
                    e.BVF = 1.0e-10
                e.BVPRIM = 0.7 * e.BVF
                funciones_dispersion.distf(e)
                kiter += 1
                if abs((dhfold - e.DHFAER) / e.DHFAER) < 0.01:
                    break
                if kiter >= 5:
                    e.DHFAER = 0.5 * (e.DHFAER + dhfold)
                    break
            e.UP = e.US
            e.TGP = e.TGS
            ptp = e.PTS
            e.BVF = math.sqrt(e.G * e.TGP / ptp)
            if e.BVF < 1.0e-10:
                e.BVF = 1.0e-10
            e.BVPRIM = 0.7 * e.BVF
        e.PRM_FSTREC = True
        e.ZMIDMX = 0.5 * e.ZI
        e.XFINAL = e.XMAX
        e.DHCRIT = e.DHFAER
        e.XMIXED = e.ZI * e.UAVG / e.SWAVG
        if e.UNSTAB and e.HS < e.ZI:
            if e.XMIXED < 1.25 * e.XFINAL:
                e.XFINAL = 0.8 * e.XMIXED
                sigmas.cblprd(e, e.XFINAL)
                e.DHCRIT = e.DHP1
    pp = e.PPFACT[irec, isrc]
    for i in range(1, _NTAB + 1):
        xtab = _XTABLE[i]
        if xarg > xtab:
            xinp = xtab
            if i > 1:
                deltax = _XTABLE[i] - _XTABLE[i - 1]
            else:
                deltax = _XTABLE[1]
        else:
            xinp = xarg
            if i > 1:
                deltax = xarg - _XTABLE[i - 1]
            else:
                deltax = xarg
        calculo_area.centroid(e, xinp)
        if puntual:
            sigmas.deltah(e, xinp)
        elif (t == "VOLUME" or t[:4] == "AREA") and aft_y:
            raise NoTraducido("AIRCRAFT")
        else:
            e.DHP = 0.0
            e.DHP1 = 0.0
            e.DHP2 = 0.0
            e.DHP3 = 0.0
        if e.UNSTAB and e.HS < e.ZI:
            funciones_dispersion.pdf(e)
        calculo_area.heff(e, xinp)
        parametros_efectivos.iblval(e, xinp)
        if e.UNSTAB and e.HS < e.ZI:
            funciones_dispersion.pdf(e)
            calculo_area.heff(e, xinp)
        if puntual and not e.NOBID:
            sigmas.bid(e)
        else:
            if e.STABLE or (e.UNSTAB and e.HS >= e.ZI):
                e.SYB = 0.0
                e.SZB = 0.0
            elif e.UNSTAB:
                e.SYB = 0.0
                e.SZBD = 0.0
                e.SZBN = 0.0
                e.SYB3 = 0.0
                e.SZB3 = 0.0
        if e.STABLE or (e.UNSTAB and e.HS >= e.ZI):
            if puntual:
                calculo_area.pdis(e, xinp)
                sr[i] = math.sqrt(e.SZ * e.SY)
                sr3[i] = 0.0
            elif t == "VOLUME":
                calculo_area.vdis(e, xinp)
                sr[i] = math.sqrt(e.SY * e.SZ)
                sr3[i] = 0.0
            elif t[:4] == "AREA" or t == "OPENPIT":
                calculo_area.adisy(e, xinp)
                calculo_area.adisz(e, xinp)
                sr[i] = math.sqrt(e.SY * e.SZ)
                sr3[i] = 0.0
            fran = funciones_dispersion.meandr(e, e.UEFF, e.SVEFF)
            e.SYEFF = 1.0 / ((fran / (e.SRT2PI * xinp)) + (1.0 - fran) / e.SY)
            nsubz = min(2.15, nsubzs * (e.SYEFF / e.SY))
            srmin = srmins * (1.282 / nsubz)
            if i > 1:
                sigr = max(srmin, 0.5 * (sr[i] + sr[i - 1]))
            else:
                sigr = max(srmin, 0.5 * sr[i])
        else:
            s1, s3 = _reldisp(e, xinp)
            sr[i] = s1
            sr3[i] = s3
            if i > 1:
                sigr = max(srmin, 0.5 * (sr[i] + sr[i - 1]))
            else:
                sigr = max(srmin, 0.5 * sr[i])
            if pp > 0.0:
                e.PPF = pp
                srmin3 = e.PPF * srmins + (1.0 - e.PPF) * srminu
            if pp > 0.0:
                if i > 1:
                    sigr3 = max(srmin3, (0.5 * (sr3[i] + sr3[i - 1])))
                else:
                    sigr3 = max(srmin3, (0.5 * sr3[i]))
            else:
                sigr3 = 0.0
        vert = bvarg + 2.0 * nsubz * sigr
        if e.UNSTAB and vert > e.ZI:
            vert = e.ZI
            bvtmp = max(0.0, e.ZI - 2.0 * nsubz * sigr)
            if 2.0 * nsubz * sigr > e.ZI:
                sigrztmp = e.ZI / (2.0 * nsubz)
            else:
                sigrztmp = sigr
        else:
            bvtmp = bvarg
            sigrztmp = sigr
        suma = suma + (e.PI * (nsubz * sigr) * (nsubz * sigrztmp) + vert * bharg +
                       2.0 * nsubz * sigr * bvtmp) * deltax
        if e.UNSTAB and pp > 0.0:
            nsubz = e.PPF * nsubzs + (1.0 - e.PPF) * nsubzu
            vert3 = bvarg3 + 2.0 * nsubz * sigr3
            suma3 = suma3 + (e.PI * (nsubz * sigr3) * (nsubz * sigr3) + vert3 * bharg3 +
                             2.0 * nsubz * sigr3 * bvarg3) * deltax
        else:
            suma3 = 0.0
        if xarg <= xtab:
            break
    return suma * (1.0 - pp) + suma3 * pp


def _psd_incluida(e, isrc, srcs):
    """¿Entra la fuente en el cálculo según PSDCREDIT y el conjunto de fuentes?"""
    if not e.PSDCREDIT:
        return True
    c = e.PSDC[isrc]
    if srcs == 1:
        return c == 1 or c == 2
    if srcs == 2:
        return c == 2 or c == 3
    return False


def _aviso_411(e, irec):
    """Aviso 411 de PVMRM_CALC (no hay emisión de NOx en el volumen combinado)."""
    if irec <= 999:
        d = fwrite("(I3.3,1X,I8.8)", irec, e.KURDAT)[0]
    elif irec <= 9999:
        d = fwrite("(I4.4,I8.8)", irec, e.KURDAT)[0]
    else:
        d = fwrite("('000',1X,I8.8)", e.KURDAT)[0]
    e.errhdl(e.PATH, "PVMRM_CALC", "W", "411", d)


def pvmrm_calc(e, srcs2use):
    """PVMRM_CALC: método de la razón molar en el volumen del penacho."""
    if e.EVONLY:
        raise NoTraducido("EVENT")
    srcs = _CODIGO_SRCS[srcs2use]
    if e.PSDCREDIT:
        for k in range(1, e.NUMSRC + 1):
            e.PSDC[k] = _CODIGO_PSD.get(e.PSDSRCTYP[k], 0)
    # QTK de EMFACT de cada fuente para la hora (constante en el bucle de receptores)
    isrc0, qtk0 = e.ISRC, e.QTK
    for k in range(1, e.NUMSRC + 1):
        e.ISRC = k
        funciones_dispersion.emfact(e, e.AQS[k])
        e.QTKSRC[k] = e.QTK
    e.ISRC, e.QTK = isrc0, qtk0
    if srcs == _ALLSRCS:
        maxchi, domidx = _maxloc_fuentes(e)
    else:
        maxchi, domidx = aermax(e, srcs)
    from . import nucleo
    if e.NUMPIT > 0:
        from . import fuente_foso
        fuente_foso.pvmrm_bucle(e, srcs, maxchi, domidx)
    elif nucleo.activo():
        nucleo.pvmrm_bucle(e, srcs, maxchi, domidx)
    else:
        _pvmrm_bucle(e, srcs, maxchi, domidx)


def _pvmrm_bucle(e, srcs, maxchi, domidx):
    """Bucle de receptores de PVMRM_CALC (la parte que se compila con numba en nucleo.py)."""
    nt = e.NUMTYP
    ns = e.NUMSRC
    chi = e.CHI
    width = 0.0
    for irec in range(1, e.NUMREC + 1):
        e.IREC = irec
        maxconc = maxchi[irec, 1]
        idom = domidx[irec, 1]
        if maxconc == 0.0:
            e.HRVAL[:] = 0.0
            e.AERVAL[:] = 0.0
            continue
        udom = e.UEFFS[irec, idom]
        fdom = e.FOPTS[irec, idom]
        e.WDSIN = e.AWDSIN[idom]
        e.WDCOS = e.AWDCOS[idom]
        e.AFV = e.AAFV[idom]
        e.HMNT = 1.0e10
        e.HMXT = -1.0e10
        e.HMNH = 1.0e10
        e.HMXH = -1.0e10
        e.HMNT3 = 1.0e10
        e.HMXT3 = -1.0e10
        e.HMNH3 = 1.0e10
        e.HMXH3 = -1.0e10
        e.CWMIN = 1.0e20
        e.CWMAX = -1.0e20
        e.CWMIN3 = 1.0e20
        e.CWMAX3 = -1.0e20
        e.DWMIN = 1.0e20
        e.DWMAX = -1.0e20
        e.DWMIN3 = 1.0e20
        e.DWMAX3 = -1.0e20
        width = 0.0
        e.NUMCONT = 0
        for isrc in range(1, ns + 1):
            e.ISRC = isrc
            if _psd_incluida(e, isrc, srcs):
                _major_cont(e, maxconc, idom)
        bvert = fdom * (e.HMXH - e.HMNH) + (1.0 - fdom) * (e.HMXT - e.HMNT)
        if e.UNSTAB and e.PPFACT[irec, idom] > 0.0:
            bvert3 = fdom * (e.HMXH3 - e.HMNH3) + (1.0 - fdom) * (e.HMXT3 - e.HMNT3)
        else:
            bvert3 = 0.0
        if e.CWMAX > e.CWMIN:
            bhoriz = e.CWMAX - e.CWMIN
        else:
            bhoriz = 0.0
        if e.CWMAX3 > e.CWMIN3:
            bhoriz3 = e.CWMAX3 - e.CWMIN3
        else:
            bhoriz3 = 0.0
        e.ISRC = idom
        t = e.SRCTYP[idom]
        if t[:4] == "AREA" or t == "LINE":
            calculo_area.setsrc(e)
            e.QTK = e.QTKSRC[idom]
            xdep, width, length, xminr, xmaxr = calculo_area.ardist(e, irec)
            distdom = max(e.X, 1.0)
            if e.PVMRM:
                calculo_area.adisy(e, distdom)
                if 4.3 * e.SY < width:
                    width = 4.3 * e.SY
            voldom = _plume_vol(e, distdom, irec, idom, 0.0, 0.0, width, 0.0)
        elif t == "OPENPIT":
            raise NoTraducido("OPENPIT")
        else:
            calculo_area.setsrc(e)
            e.QTK = e.QTKSRC[idom]
            funciones_dispersion.xydist(e, irec)
            if t == "VOLUME":
                xdom = max(e.X, 1.0)
                width = 4.3 * e.ASYINI[idom]
            else:
                xdom = max(e.X, 1.0)
                width = 0.0
            distdom = max(xdom, 1.0)
            voldom = _plume_vol(e, distdom, irec, idom, 0.0, 0.0, width, 0.0)
        if e.UNSTAB and distdom >= e.XMIXED:
            bvert = 0.0
        else:
            bvert = fdom * (e.HMXH - e.HMNH) + (1.0 - fdom) * (e.HMXT - e.HMNT)
        if bvert > 0.0 or bvert3 > 0.0 or bhoriz > 0.0 or bhoriz3 > 0.0:
            volsum = _plume_vol(e, distdom, irec, idom, bvert, bvert3, bhoriz, bhoriz3)
        else:
            volsum = voldom
        e.WDSIN = e.AWDSIN[idom]
        e.WDCOS = e.AWDCOS[idom]
        e.AFV = e.AAFV[idom]
        zcorr = e.AZS[idom] + e.HECNTR[irec, idom]
        gh = e.GRIDHT
        n = perfiles.locate(gh, 1, e.MXGLVL, zcorr)
        if n >= 1:
            ptz = perfiles.gintrp(gh[n], e.GRIDPT[n], gh[n + 1], e.GRIDPT[n + 1], zcorr)
        else:
            ptz = e.GRIDPT[1]
        tap = ptz - e.GOVRCP * zcorr
        pcorr = math.exp(-e.G * 0.028966 * zcorr / (e.RGAS * tap))
        tcorr = 273.15 / tap
        voldom = voldom * pcorr * tcorr
        volsum = volsum * pcorr * tcorr
        if not e.O3MISS:
            domo3 = voldom * e.O3CONC / (1.0e6 * 48.0)
            sumo3 = volsum * e.O3CONC / (1.0e6 * 48.0)
        else:
            domo3 = 0.0
            sumo3 = 0.0
        rdom = e.ANO2_RATIO[idom]
        t = e.SRCTYP[idom]
        if t == "AREA" or t == "AREAPOLY" or t == "LINE":
            domnox = e.QTK * e.XINIT * e.YINIT * (1.0 - rdom) * distdom / (udom * 46.0)
        elif t == "AREACIRC":
            domnox = e.QTK * e.PI * e.RADIUS[idom] * e.RADIUS[idom] * (1.0 - rdom) * distdom / \
                (udom * 46.0)
        else:
            domnox = e.QTK * (1.0 - rdom) * distdom / (udom * 46.0)
        e.QSUM = 0.0
        e.QSUM3 = 0.0
        e.SUM_NO2RAT = 0.0
        e.SUM3_NO2RAT = 0.0
        for isrc in range(1, ns + 1):
            e.ISRC = isrc
            if _psd_incluida(e, isrc, srcs):
                _moles_nox(e, idom)
        if e.QSUM == 0.0 and e.QSUM3 == 0.0:
            _aviso_411(e, irec)
            e.HRVAL[:] = 0.0
            e.AERVAL[:] = 0.0
            continue
        if e.QSUM > 0.0:
            ave = e.SUM_NO2RAT / e.QSUM
        else:
            ave = 0.0
        if e.QSUM3 > 0.0:
            ave3 = e.SUM3_NO2RAT / e.QSUM3
        else:
            ave3 = 0.0
        sumnox = e.QSUM * (1.0 - ave) * distdom / (udom * 46.0) + \
            e.QSUM3 * (1.0 - ave3) * distdom / (udom * 46.0)
        if domnox > 0.0:
            domconv = min(domo3 / domnox, 1.0)
        else:
            domconv = 0.0
        if sumnox > 0.0:
            sumconv = min(sumo3 / sumnox, 1.0)
        else:
            sumconv = 0.0
        if e.O3MISS:
            pct = 1.0
        elif (domconv + rdom) <= (sumconv + ave):
            pct = domconv + rdom
        else:
            pct = sumconv + ave
        if pct > e.NO2EQUIL:
            pct = e.NO2EQUIL
        if not e.PSDCREDIT:
            for igrp in range(1, e.NUMGRP + 1):
                e.IGRP = igrp
                for isrc in range(1, ns + 1):
                    e.ISRC = isrc
                    for ityp in range(1, nt + 1):
                        e.HRVAL[ityp] = chi[irec, isrc, ityp] * pct
                    if e.IGROUP[isrc, igrp] == 1:
                        resultados.sumval(e)
                    if e.EVAL[isrc]:
                        raise NoTraducido("EVALFILE")
                e.ISRC = ns + 1
                if e.GRP_BACK[igrp]:
                    sumback_no2(e)
            e.IGRP = e.NUMGRP + 1
        elif srcs == 1:
            for isrc in range(1, ns + 1):
                for ityp in range(1, nt + 1):
                    c = e.PSDC[isrc]
                    if c == 1 or c == 2:
                        e.ABVAL[irec, ityp] = e.ABVAL[irec, ityp] + chi[irec, isrc, ityp] * pct
            e.ISRC = ns + 1
            sumvalpsd(e, srcs)
        elif srcs == 2:
            for isrc in range(1, ns + 1):
                for ityp in range(1, nt + 1):
                    c = e.PSDC[isrc]
                    if c == 2 or c == 3:
                        e.BCVAL[irec, ityp] = e.BCVAL[irec, ityp] + chi[irec, isrc, ityp] * pct
            e.ISRC = ns + 1
            sumvalpsd(e, srcs)
        e.HRVAL[:] = 0.0
        e.AERVAL[:] = 0.0
    e.IREC = e.NUMREC + 1
