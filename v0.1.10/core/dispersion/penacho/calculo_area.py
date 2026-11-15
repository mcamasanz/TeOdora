# -*- coding: utf-8 -*-
"""Traducción de AERMOD 26135 (US EPA, dominio público): cálculo horario por fuente y receptor
(calc1.f: CALC, ACALC, ARDIST, SETSRC, FLUXES, HEFF, PRMHEFF, PDIS, VDIS, ADISY, ADISZ, CENTROID,
REFL_HT, PENFCT, CPLUME, PRM_PLUME, ACPLUME, AER_PCHI, AER_ACHI) y la deposición (VDP, SCAVRAT,
PDEP, PDEPG, DEPLETE, F2INT, QATR2, QG2D2).

Las fuentes puntuales (PCALC, AERCALC, PRMCALC) y de volumen (VCALC, VOLCALC) están en
calculo_punto_volumen.py. Rutinas externas: calc2 (EMFACT, CRITDS, PDF, PFRACT, FTERM, FYPLM, MEANDR, DECAY,
VRTSBL, VRTSBN, VRTCBL), sigmas (SIGY, SIGZ, BID, RMSSIG, CBLPRD), iblval (IBLVAL, METINI),
pitarea (AREAIN), resultados (SUMVAL)."""
import math

import numpy as np

from . import depura
from .estado import NoTraducido
from .perfiles import gintrp, locate


_MODS = None


def _m():
    global _MODS
    if _MODS is None:
        from . import funciones_dispersion, parametros_efectivos, integracion_area, resultados, sigmas
        _MODS = (funciones_dispersion, sigmas, parametros_efectivos, integracion_area, resultados)
    return _MODS


# ---------------------------------------------------------------------------------------- CALC
def calc(e):
    """CALC: recorre las fuentes para la hora en curso."""
    e.PATH = "CN"
    if e.RUNTTRM:
        e.TTRMOUT[...] = 0.0
    # BUOYLINE: todas las líneas se calculan juntas en la primera; RLINE: los receptores solo se
    # giran con la primera fuente RLINE de la hora
    blprocessed = False
    if e.NRLINES > 0:
        e.RL.RLPROCESSED = False
    e.METHDR = True
    for isrc in range(1, e.NUMSRC + 1):
        e.ISRC = isrc
        t = e.SRCTYP[isrc]
        if t[:5] == "POINT":
            from . import calculo_punto_volumen
            calculo_punto_volumen.pcalc(e)
        elif t == "VOLUME":
            from . import calculo_punto_volumen
            calculo_punto_volumen.vcalc(e)
        elif t[:4] == "AREA" or t == "LINE":
            acalc(e)
        elif t == "RLINE" or t == "RLINEXT":
            from . import fuente_carretera
            fuente_carretera.rlcalc(e)
            e.RL.RLPROCESSED = True
        elif t == "BUOYLINE":
            if not blprocessed:
                from . import fuente_linea_flotante
                fuente_linea_flotante.calc_bl(e)
                blprocessed = True
        elif t == "OPENPIT":
            from . import fuente_foso
            fuente_foso.ocalc(e)
        elif t == "SWPOINT":
            from . import fuente_sidewash
            fuente_sidewash.swcalc(e)
        else:
            raise NoTraducido("tipo de fuente " + t)
        if e.RUNERR:
            break
    if e.L_BACKGRND and not e.ARM2 and not e.OLM and not e.GRSM and not e.RUNTTRM \
            and not e.PVMRM:
        resultados = _m()[4]
        for igrp in range(1, e.NUMGRP + 1):
            e.IGRP = igrp
            resultados.sumback(e)
        e.IGRP = e.NUMGRP + 1


# ---------------------------------------------------------------------------------- SETSRC
def _setsrc_aft(e, i):
    """SETSRC: parámetros de aeronave de la fuente I (o cero si no lo es)."""
    if e.AFTSRC[i] == "Y":
        e.MFUEL = e.AMFUEL[i]
        e.THRUST = e.ATHRUST[i]
        e.VAA = e.AVAA[i]
        e.AFR = e.AAFR[i]
        e.BYPR = e.ABYPR[i]
        e.RPWR = e.ARPWR[i]
        e.SRCANGLE = e.ASRCANGLE[i]
    else:
        e.MFUEL = 0.0
        e.THRUST = 0.0
        e.VAA = 0.0
        e.AFR = 0.0
        e.BYPR = 0.0
        e.RPWR = 0.0
        e.SRCANGLE = 0.0


def _setsrc_vert(e, i, n):
    """SETSRC: vértices de la fuente I (los N más el primero repetido)."""
    e.XVERT[1:n + 2] = e.AXVERT[1:n + 2, i]
    e.YVERT[1:n + 2] = e.AYVERT[1:n + 2, i]


def setsrc(e):
    """SETSRC: copia los parámetros de la fuente ISRC a las variables de trabajo."""
    i = e.ISRC
    e.XINIT = 0.0
    e.YINIT = 0.0
    e.SYINIT = 0.0
    e.SZINIT = 0.0
    e.ANGLE = 0.0
    e.PALPHA = 0.0
    e.PDEFF = 0.0
    e.PITLEN = 0.0
    e.PITWID = 0.0
    t = e.SRCTYP[i]
    if t[:5] == "POINT":
        e.XS = e.AXS[i]
        e.YS = e.AYS[i]
        e.ZS = e.AZS[i]
        e.QS = e.AQS[i]
        e.HS = e.AHS[i]
        e.DS = e.ADS[i]
        e.VS = e.AVS[i]
        e.TS = e.ATS[i]
        if t == "POINTCAP":
            e.DSFACT = e.ADSFACT[i]
        else:
            e.DSFACT = 1.0
    elif t == "VOLUME":
        e.XS = e.AXS[i]
        e.YS = e.AYS[i]
        e.ZS = e.AZS[i]
        e.QS = e.AQS[i]
        e.HS = e.AHS[i]
        e.SYINIT = e.ASYINI[i]
        e.SZINIT = e.ASZINI[i]
        _setsrc_aft(e, i)
    elif t == "AREA" or t == "LINE":
        e.XS = e.AXS[i]
        e.YS = e.AYS[i]
        e.ZS = e.AZS[i]
        e.QS = e.AQS[i]
        e.HS = e.AHS[i]
        e.XINIT = e.AXINIT[i]
        e.YINIT = e.AYINIT[i]
        e.ANGLE = e.AANGLE[i]
        e.SZINIT = e.ASZINI[i]
        e.NVERT = 4
        _setsrc_vert(e, i, e.NVERT)
        e.IVERT = e.NVERT + 2
        e.XCNTR = e.AXCNTR[i]
        e.YCNTR = e.AYCNTR[i]
        if t == "AREA" and e.AFTSRC[i] == "Y":
            _setsrc_aft(e, i)
        else:
            e.MFUEL = 0.0
            e.THRUST = 0.0
            e.VAA = 0.0
            e.AFR = 0.0
            e.BYPR = 0.0
            e.RPWR = 0.0
            e.SRCANGLE = 0.0
    elif t == "AREAPOLY" or t == "AREACIRC":
        e.XS = e.AXS[i]
        e.YS = e.AYS[i]
        e.ZS = e.AZS[i]
        e.QS = e.AQS[i]
        e.HS = e.AHS[i]
        e.SZINIT = e.ASZINI[i]
        e.NVERT = int(e.NVERTS[i])
        _setsrc_vert(e, i, e.NVERT)
        e.IVERT = e.NVERT + 2
        e.XINIT = e.AXINIT[i]
        e.YINIT = e.AYINIT[i]
        e.XCNTR = e.AXCNTR[i]
        e.YCNTR = e.AYCNTR[i]
        _setsrc_aft(e, i)
    elif t == "OPENPIT":
        e.XS = e.AXS[i]
        e.YS = e.AYS[i]
        e.ZS = e.AZS[i]
        e.QS = e.AQS[i]
        e.HS = 0.0
        e.EMIHGT = e.AHS[i]
        e.NVERT = 4
        e.XINIT = e.AXINIT[i]
        e.YINIT = e.AYINIT[i]
        e.ANGLE = e.AANGLE[i]
        e.PALPHA = e.AALPHA[i]
        e.PDEFF = e.APDEFF[i]
        e.SZINIT = e.ASZINI[i]
        e.PITLEN = max(e.XINIT, e.YINIT)
        e.PITWID = min(e.XINIT, e.YINIT)
        _setsrc_vert(e, i, e.NVERT)
        e.IVERT = e.NVERT + 2
        e.XCNTR = e.AXCNTR[i]
        e.YCNTR = e.AYCNTR[i]
    elif t == "BUOYLINE":
        e.QS = e.AQS[i]
    elif t == "SWPOINT":
        e.XS = e.AXS[i]
        e.YS = e.AYS[i]
        e.ZS = e.AZS[i]
        e.QS = e.AQS[i]
        e.HS = e.AHS[i]
        e.BW = e.ABW[i]
        e.BL = e.ABL[i]
        e.BH = e.ABH[i]
        e.BA = e.ABA[i]
    e.NPD = int(e.INPD[i])
    if e.NPD > 0:
        for j in range(1, e.NPD + 1):
            e.PDIAM[j] = e.APDIAM[j, i]
            e.PHI[j] = e.APHI[j, i]
            e.PDENS[j] = e.APDENS[j, i]
            e.VGRAV[j] = e.AVGRAV[j, i]
            e.TSTOP[j] = e.ATSTOP[j, i]
    e.SURFAC = e.HS < 0.1 * e.ZI


def fluxes(e):
    """FLUXES: flujos de flotabilidad y cantidad de movimiento. Devuelve VSEQ."""
    if e.TS < 0.0:
        e.TS = e.TA + abs(e.TS)
    if e.TS < e.TA:
        e.TS = e.TA
    e.FB = (0.25 / e.TS) * (e.VS * e.DS * e.DS) * e.G * (e.TS - e.TA)
    e.FM = (0.25 / e.TS) * (e.VS * e.DS * e.DS) * e.VS * e.TA
    t = e.SRCTYP[e.ISRC]
    if t == "POINTCAP" or t == "POINTHOR":
        vseq = 0.001
        dseq = e.DS * math.sqrt(e.VS / vseq)
        tseq = e.TS
        e.FM = (0.25 / tseq) * (vseq * dseq * dseq) * vseq * e.TA
    else:
        vseq = e.VS
    if e.FB < 1.0e-10:
        e.FB = 1.0e-10
    if e.FM < 1.0e-10:
        e.FM = 1.0e-10
    return vseq


def heff(e, xarg):
    """HEFF: altura efectiva del penacho a la distancia XARG."""
    e.DHP3PLAT = 0.0
    if e.STABLE or (e.UNSTAB and e.HS >= e.ZI):
        e.HE = e.HSP + e.DHP
        e.HE = max(0.0, e.HE)
        e.HED1 = 0.0
        e.HED2 = 0.0
        e.HEN1 = 0.0
        e.HEN2 = 0.0
        e.HE3 = 0.0
    elif e.UNSTAB:
        e.HE = 0.0
        e.HED1 = e.HSP + e.DHP1 + (e.ASUB1 * e.WSTAR * xarg / e.UEFFD)
        e.HED2 = e.HSP + e.DHP1 + (e.ASUB2 * e.WSTAR * xarg / e.UEFFD)
        e.HEN1 = e.HSP + e.DHP1 - e.DHP2 + (e.ASUB1 * e.WSTAR * xarg / e.UEFFN)
        e.HEN2 = e.HSP + e.DHP1 - e.DHP2 + (e.ASUB2 * e.WSTAR * xarg / e.UEFFN)
        if e.PPF > 0.0:
            if e.PPF == 1.0:
                e.DHP3 = e.HEDHH * (e.ZI - e.HSP)
            else:
                e.DHP3 = 0.75 * (e.ZI - e.HSP) * e.HEDHH + 0.5 * (e.ZI - e.HSP)
            if e.OSPLAT[e.ISRC]:
                e.HE3 = e.HSP + e.DHP3 - e.DHP3PLAT
            else:
                e.HE3 = e.HSP + e.DHP3
        else:
            e.DHP3 = 0.0
            e.HE3 = 0.0


def prmheff(e):
    """PRMHEFF: altura efectiva para el penacho de PRIME."""
    if e.STABLE:
        e.HE = e.HS + e.DHP
        e.HE = max(0.0, e.HE)
    elif e.UNSTAB:
        e.HE = e.HS + e.DHP
        e.HE = max(0.0, e.HE)


# ----------------------------------------------------------------------------- dispersión
def pdis(e, xarg):
    """PDIS: sigmas de una fuente puntual."""
    funciones_dispersion, sigmas, _i, _p, _r = _m()
    sigmas.sigz(e, xarg)
    sigmas.sigy(e, xarg)
    e.VSIGY = 0.0
    e.VSYN = 0.0
    e.VSIGZ = 0.0
    e.VSZD1 = 0.0
    e.VSZD2 = 0.0
    e.VSZN1 = 0.0
    e.VSZN2 = 0.0
    e.VSZ3 = 0.0
    e.VSY3 = 0.0
    if e.NOBID:
        if e.STABLE or (e.UNSTAB and e.HS >= e.ZI):
            e.SYB = 0.0
            e.SZB = 0.0
        elif e.UNSTAB:
            e.SYB = 0.0
            e.SZBD = 0.0
            e.SZBN = 0.0
            e.SYB3 = 0.0
            e.SZB3 = 0.0
    else:
        sigmas.bid(e)
    for n in ("PLATSZ", "PLATSY", "PLATSZD1", "PLATSYD1", "PLATSZD2", "PLATSYD2", "PLATSZN1",
              "PLATSYN1", "PLATSZN2", "PLATSYN2", "PLATSZP", "PLATSYP"):
        setattr(e, n, 0.0)
    if e.OSPLAT[e.ISRC]:
        raise NoTraducido("PLATFORM")
    sigmas.rmssig(e)


def vdis(e, xarg):
    """VDIS: sigmas de una fuente de volumen."""
    funciones_dispersion, sigmas, _i, _p, _r = _m()
    sigmas.sigy(e, xarg)
    sigmas.sigz(e, xarg)
    e.VSIGY = e.SYINIT
    e.VSYN = e.SYINIT
    e.VSIGZ = e.SZINIT
    e.VSZD1 = e.SZINIT
    e.VSZD2 = e.SZINIT
    e.VSZN1 = e.SZINIT
    e.VSZN2 = e.SZINIT
    e.VSZ3 = 0.0
    e.VSY3 = 0.0
    if e.AFTSRC[e.ISRC] == "Y":
        sigmas.bid(e)
    else:
        e.SYB = 0.0
        e.SZB = 0.0
        e.SZBD = 0.0
        e.SZBN = 0.0
        e.SYB3 = 0.0
        e.SZB3 = 0.0
    sigmas.rmssig(e)


def adisy(e, xarg):
    """ADISY: sigma-y de una fuente de área."""
    funciones_dispersion, sigmas, _i, _p, _r = _m()
    sigmas.sigy(e, xarg)
    e.VSIGY = 0.0
    e.VSY3 = 0.0
    if e.AFTSRC[e.ISRC] == "Y":
        sigmas.bid(e)
        e.SY = math.sqrt(e.SYB * e.SYB + e.SYAMB * e.SYAMB + e.VSIGY * e.VSIGY)
    else:
        e.SYB = 0.0
        e.SYB3 = 0.0
        e.SY = e.SYAMB


def adisz(e, xarg):
    """ADISZ: sigma-z de una fuente de área."""
    funciones_dispersion, sigmas, _i, _p, _r = _m()
    sigmas.sigz(e, xarg)
    e.VSIGZ = e.SZINIT
    e.VSZD1 = e.SZINIT
    e.VSZD2 = e.SZINIT
    e.VSZN1 = e.SZINIT
    e.VSZN2 = e.SZINIT
    e.VSZ3 = 0.0
    if e.AFTSRC[e.ISRC] == "Y":
        sigmas.bid(e)
    else:
        e.SZB = 0.0
        e.SZBD = 0.0
        e.SZBN = 0.0
        e.SZB3 = 0.0
    sigmas.rmssig(e)


def centroid(e, xarg):
    """CENTROID: altura del centroide del penacho en convectiva."""
    funciones_dispersion, sigmas, _i, _p, _r = _m()
    xtmp = max(xarg, 1.0)
    t = e.SRCTYP[e.ISRC]
    if e.UNSTAB and e.HS < e.ZI:
        if t[:5] == "POINT":
            sigmas.cblprd(e, xtmp)
            e.HTEFF = min(e.HSP + e.DHP1, e.ZI)
        elif (t == "VOLUME" or t[:4] == "AREA") and e.AFTSRC[e.ISRC] == "Y":
            raise NoTraducido("AIRCRAFT (PLUME_TRAJ)")
        else:
            e.HTEFF = e.HSP
            e.DHCRIT = 0.0
            e.XFINAL = 0.0
        if xtmp < e.XFINAL:
            e.CENTER = e.HTEFF
        elif xtmp >= e.XMIXED:
            e.CENTER = e.ZMIDMX
        else:
            delx = e.XMIXED - e.XFINAL
            delz = e.ZMIDMX - min(e.HSP + e.DHCRIT, e.ZI)
            frac = (xtmp - e.XFINAL) / delx
            e.CENTER = min(e.HSP + e.DHCRIT, e.ZI) + frac * delz
        e.SURFAC = e.CENTER < 0.1 * e.ZI
    elif e.UNSTAB and e.HS >= e.ZI:
        e.SURFAC = False
        e.CENTER = e.HSP
        e.SURFAC = e.CENTER < 0.1 * e.ZI
    else:
        e.CENTER = e.HSP
        e.SURFAC = e.CENTER < 0.1 * e.ZI


def refl_ht(e, hearg, xarg, szbarg, vsigzarg):
    """REFL_HT: altura de la superficie reflectora en estable. Devuelve HEREFL."""
    gh = e.GRIDHT
    ndxhe = locate(gh, 1, e.MXGLVL, hearg)
    if ndxhe >= 1:
        svrefl = gintrp(gh[ndxhe], e.GRIDSV[ndxhe], gh[ndxhe + 1], e.GRIDSV[ndxhe + 1], hearg)
        swrefl = gintrp(gh[ndxhe], e.GRIDSW[ndxhe], gh[ndxhe + 1], e.GRIDSW[ndxhe + 1], hearg)
        urefl = gintrp(gh[ndxhe], e.GRIDWS[ndxhe], gh[ndxhe + 1], e.GRIDWS[ndxhe + 1], hearg)
        tgrefl = gintrp(gh[ndxhe], e.GRIDTG[ndxhe], gh[ndxhe + 1], e.GRIDTG[ndxhe + 1], hearg)
        ptrefl = gintrp(gh[ndxhe], e.GRIDPT[ndxhe], gh[ndxhe + 1], e.GRIDPT[ndxhe + 1], hearg)
    else:
        svrefl = e.GRIDSV[1]
        swrefl = e.GRIDSW[1]
        urefl = e.GRIDWS[1]
        tgrefl = e.GRIDTG[1]
        ptrefl = e.GRIDPT[1]
    swrefl = max(swrefl, e.SWMIN)
    svrefl = max(svrefl, e.SVMIN, e.SVUMIN * urefl)
    if e.L_VECTORWS:
        urefl = math.sqrt(urefl * urefl + 2.0 * svrefl * svrefl)
    urefl = max(urefl, e.WSMIN)
    if e.STABLE:
        e.SZSURF = (e.RTOF2 / e.RTOFPI) * e.USTAR * (xarg / urefl) * \
            (1.0 + 0.7 * xarg / e.OBULEN) ** (-1.0 * e.THIRD)
    else:
        e.SZSURF = 0.0
    ttravl = xarg / urefl
    bvfrq = math.sqrt(e.G * tgrefl / ptrefl)
    if bvfrq < 1.0e-10:
        bvfrq = 1.0e-10
    ztmp = max(e.HS, hearg, 1.0e-4)
    szrefl = swrefl * ttravl / \
        math.sqrt(1.0 + swrefl * ttravl * (1.0 / (0.72 * ztmp) + bvfrq / (0.54 * swrefl)))
    if hearg >= e.ZI:
        szrf = szrefl
    else:
        sigf = min(hearg / e.ZI, 1.0)
        szrf = (1.0 - sigf) * e.SZSURF + sigf * szrefl
    szhsbl = math.sqrt(szbarg * szbarg + szrf * szrf + vsigzarg * vsigzarg)
    return max(e.ZI, hearg + 2.15 * szhsbl)


def penfct(e):
    """PENFCT: fracción de penacho que penetra la inversión."""
    if e.STABLE:
        e.PPF = 0.0
    elif e.UNSTAB and e.HS >= e.ZI:
        e.PPF = 1.0
    else:
        bvzi2 = (e.G / e.PTATZI) * e.VPTGZI
        if e.AFTSRC[e.ISRC] == "Y":
            e.PSUBS = e.FB / (bvzi2 * (e.ZI - e.HSP) * (e.ZI - e.HSP) * (e.ZI - e.HSP))
        else:
            e.PSUBS = e.FB / (e.UP * bvzi2 * (e.ZI - e.HSP) * (e.ZI - e.HSP) * (e.ZI - e.HSP))
        e.HEDHH = (17.576 * e.PSUBS + 0.296296) ** e.THIRD
        if e.HEDHH < (2.0 * e.THIRD):
            e.PPF = 0.0
        elif e.HEDHH > 2.0:
            e.PPF = 1.0
        else:
            e.PPF = 1.5 - (1.0 / e.HEDHH)


# ------------------------------------------------------------------------------ penachos
def cplume(e, zarg):
    """CPLUME: concentración del penacho (puntual/volumen) a la altura ZARG. Devuelve COUT."""
    funciones_dispersion = _m()[0]
    e.ZR = zarg
    if e.STABLE or (e.UNSTAB and e.HS >= e.ZI):
        if e.ZR <= e.HSBL:
            funciones_dispersion.vrtsbl(e, e.SZ, max(0.0, e.HE - e.HV), e.HSBL)
        else:
            funciones_dispersion.vrtsbn(e, e.SZ, max(0.0, e.HE - e.HV))
        return (e.QTK / e.UEFF) * (e.FSUBY * e.FSUBZ)
    if not e.UNSTAB:
        return None
    if e.PPF < 1.0:
        if e.ZR <= e.ZI:
            funciones_dispersion.vrtcbl(e, e.HED1 - e.HV, e.HED2 - e.HV, e.SZD1, e.SZD2, 1.0)
            e.FSUBZD = e.FSUBZ
        else:
            e.FSUBZD = 0.0
        if e.ZR <= e.ZI:
            funciones_dispersion.vrtcbl(e, e.HEN1 - e.HV, e.HEN2 - e.HV, e.SZN1, e.SZN2, -1.0)
            e.FSUBZN = e.FSUBZ
        else:
            e.FSUBZN = 0.0
    else:
        e.FSUBZD = 0.0
        e.FSUBZN = 0.0
    if e.PPF > 0.0:
        if e.ZR <= e.HPEN:
            funciones_dispersion.vrtsbl(e, e.SZ3, max(0.0, e.HE3 - e.HV), e.HPEN)
        else:
            funciones_dispersion.vrtsbn(e, e.SZ3, max(0.0, e.HE3 - e.HV))
        e.FSUBZ3 = e.FSUBZ
        q = e.QTK
        if e.HBPLUME and e.HBPSRC[e.ISRC] == "Y":
            if e.PPF < 1.0:
                return (q * (1.0 - e.PPF) / e.UEFFD) * (e.FSUBYD * e.FSUBZD) + \
                    (q * (1.0 - e.PPF) / e.UEFFN) * (e.FSUBYN * e.FSUBZN) + \
                    (q * e.PPF * e.PPFN / e.UEFF3) * (e.FSUBY3 * e.FSUBZ3)
            return (q * e.PPF * e.PPFN / e.UEFF3) * (e.FSUBY3 * e.FSUBZ3)
        if e.PPF < 1.0:
            return (q * (1.0 - e.PPF) / e.UEFFD) * (e.FSUBYD * e.FSUBZD) + \
                (q * (1.0 - e.PPF) / e.UEFFN) * (e.FSUBYN * e.FSUBZN) + \
                (q * e.PPF / e.UEFF3) * (e.FSUBY3 * e.FSUBZ3)
        return (q * e.PPF / e.UEFF3) * (e.FSUBY3 * e.FSUBZ3)
    e.FSUBZ3 = 0.0
    e.HPEN = 0.0
    return (e.QTK / e.UEFFD) * (e.FSUBYD * e.FSUBZD) + \
        (e.QTK / e.UEFFN) * (e.FSUBYN * e.FSUBZN)


def prm_plume(e, zarg, ueffph):
    """PRM_PLUME: concentración del penacho de PRIME. Devuelve COUT."""
    funciones_dispersion = _m()[0]
    e.ZR = zarg
    if e.STABLE:
        funciones_dispersion.vrtsbn(e, e.SZ, e.HE)
    elif e.UNSTAB and e.HE <= e.ZI:
        funciones_dispersion.vrtsbl(e, e.SZ, e.HE, e.ZI)
    else:
        e.FSUBZ = 0.0
    return (e.QTK / ueffph) * (e.FSUBY * e.FSUBZ)


def acplume(e, zarg, fyarg):
    """ACPLUME: concentración por unidad de emisión de un elemento de área. Devuelve COUT."""
    funciones_dispersion = _m()[0]
    e.ZR = zarg
    e.FSUBY = fyarg
    if e.STABLE or (e.UNSTAB and e.HS >= e.ZI):
        if e.ZR <= e.HSBL:
            funciones_dispersion.vrtsbl(e, e.SZ, max(0.0, e.HE - e.HV), e.HSBL)
        else:
            funciones_dispersion.vrtsbn(e, e.SZ, max(0.0, e.HE - e.HV))
        return (1.0 / e.UEFF) * (e.FSUBY * e.FSUBZ)
    if not e.UNSTAB:
        return None
    if e.ZR <= e.ZI:
        funciones_dispersion.vrtcbl(e, e.HED1 - e.HV, e.HED2 - e.HV, e.SZD1, e.SZD2, 1.0)
        e.FSUBZD = e.FSUBZ
    else:
        e.FSUBZD = 0.0
    if e.ZR <= e.ZI:
        funciones_dispersion.vrtcbl(e, e.HEN1 - e.HV, e.HEN2 - e.HV, e.SZN1, e.SZN2, -1.0)
        e.FSUBZN = e.FSUBZ
    else:
        e.FSUBZN = 0.0
    e.FSUBZ3 = 0.0
    e.HPEN = 0.0
    return (1.0 / e.UEFFD) * (e.FSUBY * e.FSUBZD) + (1.0 / e.UEFFN) * (e.FSUBY * e.FSUBZN)


def _humedo(e, adj, jin):
    if e.PRATE > 0.0:
        if e.NPD == 0:
            return (adj * e.FRACSAT * e.PRATE * 1.0e6 * e.RGAS * e.TA) / \
                (e.ZSUBP * e.HENRY[e.ISRC] * 1.0e9 * e.DENOM * 3600.0)
        return 1.0e-3 * adj * e.WASHOUT[jin] * e.PRATE / (e.ZSUBP * 3600.0)
    return 0.0


def aer_pchi(e, xarg, adj, vdinp, jin, aerout):
    """AER_PCHI: concentración/depósito de AERMOD para puntual y volumen (AEROUT en sitio)."""
    funciones_dispersion = _m()[0]
    dryflux = 0.0
    wetflux = 0.0
    if e.FOPT == 0.0:
        e.CWRAP = 0.0
    else:
        e.CWRAP = cplume(e, e.ZRT)
    if e.ZRT == e.ZFLAG:
        e.CLIFT = e.CWRAP
    elif e.FOPT == 1.0:
        e.CLIFT = 0.0
    else:
        e.CLIFT = cplume(e, e.ZFLAG)
    funciones_dispersion.decay(e, xarg)
    ityp = 0
    if e.CONC:
        ityp = 1
        aerout[ityp] = adj * e.EMIFAC[ityp] * \
            (e.FOPT * e.CWRAP + (1.0 - e.FOPT) * e.CLIFT) * e.D
        if e.DEBUG:
            depura.aer_pchi_conc(e, ityp, adj, aerout[ityp])
    if e.DEPOS or e.DDEP:
        if e.FOPT == 0.0:
            e.CWRAP = 0.0
        else:
            e.CWRAP = cplume(e, e.ZRT - e.ZFLAG + e.ZRDEP)
        if e.ZRT == e.ZFLAG:
            e.CLIFT = e.CWRAP
        elif e.FOPT == 1.0:
            e.CLIFT = 0.0
        else:
            e.CLIFT = cplume(e, e.ZRDEP)
        dryflux = (e.FOPT * e.CWRAP + (1.0 - e.FOPT) * e.CLIFT) * e.D
    if e.DEPOS or e.WDEP:
        wetflux = _humedo(e, adj, jin)
    if e.DEPOS:
        ityp += 1
        if e.STABLE or (e.UNSTAB and e.HS >= e.ZI):
            aerout[ityp] = adj * vdinp * e.EMIFAC[ityp] * dryflux + \
                e.QTK * wetflux * e.EMIFAC[ityp] * e.FSUBY / e.UEFF
        elif e.UNSTAB:
            aerout[ityp] = adj * vdinp * e.EMIFAC[ityp] * dryflux + \
                e.QTK * wetflux * e.EMIFAC[ityp] * \
                (e.PPF * e.FSUBY3 / e.UEFF3 + (1.0 - e.PPF) * e.FSUBY / e.UEFFD)
        if e.DEBUG:
            depura.aer_pchi_dep(e, "DEPOS", ityp, adj, vdinp, dryflux, wetflux, aerout[ityp])
    if e.DDEP:
        ityp += 1
        aerout[ityp] = adj * vdinp * e.EMIFAC[ityp] * dryflux
        if e.DEBUG:
            depura.aer_pchi_dep(e, "DDEP", ityp, adj, vdinp, dryflux, 0.0, aerout[ityp])
    if e.WDEP:
        ityp += 1
        if e.STABLE or (e.UNSTAB and e.HS >= e.ZI):
            aerout[ityp] = e.QTK * wetflux * e.EMIFAC[ityp] * e.FSUBY / e.UEFF
        elif e.UNSTAB:
            aerout[ityp] = e.QTK * wetflux * e.EMIFAC[ityp] * \
                (e.PPF * e.FSUBY3 / e.UEFF3 + (1.0 - e.PPF) * e.FSUBY / e.UEFFD)
        if e.DEBUG:
            depura.aer_pchi_dep(e, "WDEP", ityp, adj, e.ZSUBP, e.PRATE, wetflux, aerout[ityp])
    e.ITYP = ityp
    if e.METEORDBG:
        depura.metdeb(e)
    if e.DEBUG:
        debout(e)


def aer_achi(e, xarg, adj, vdinp, jin, fyarg):
    """AER_ACHI: concentración/depósito de un elemento de área para el tipo ITYP. Devuelve POUT."""
    funciones_dispersion = _m()[0]
    dryflux = 0.0
    wetflux = 0.0
    o = e.OUTTYP[e.ITYP]
    sconc = o == "CONC"
    sdepos = o == "DEPOS"
    sddep = o == "DDEP"
    swdep = o == "WDEP"
    if not (sconc or sdepos or sddep or swdep):
        return None
    pout = 0.0
    funciones_dispersion.decay(e, xarg)
    if sconc:
        if e.FOPT == 0.0:
            e.CWRAP = 0.0
        else:
            e.CWRAP = acplume(e, e.ZRT, fyarg)
        if e.ZRT == e.ZFLAG:
            e.CLIFT = e.CWRAP
        elif e.FOPT == 1.0:
            e.CLIFT = 0.0
        else:
            e.CLIFT = acplume(e, e.ZFLAG, fyarg)
        pout = adj * (e.FOPT * e.CWRAP + (1.0 - e.FOPT) * e.CLIFT) * e.D
    if sdepos or sddep:
        if e.FOPT == 0.0:
            e.CWRAP = 0.0
        else:
            e.CWRAP = acplume(e, e.ZRT - e.ZFLAG + e.ZRDEP, fyarg)
        if e.ZRT == e.ZFLAG:
            e.CLIFT = e.CWRAP
        elif e.FOPT == 1.0:
            e.CLIFT = 0.0
        else:
            e.CLIFT = acplume(e, e.ZRDEP, fyarg)
        dryflux = adj * (e.FOPT * e.CWRAP + (1.0 - e.FOPT) * e.CLIFT) * e.D
    if sdepos or swdep:
        wetflux = _humedo(e, adj, jin)
    if sdepos:
        if e.STABLE or (e.UNSTAB and e.HS >= e.ZI):
            pout = vdinp * dryflux + wetflux * fyarg / e.UEFF
        elif e.UNSTAB:
            pout = vdinp * dryflux + wetflux * fyarg / e.UEFFD
    if sddep:
        pout = vdinp * dryflux
    if swdep:
        if e.STABLE or (e.UNSTAB and e.HS >= e.ZI):
            pout = wetflux * fyarg / e.UEFF
        elif e.UNSTAB:
            pout = wetflux * fyarg / e.UEFFD
    if e.METEORDBG:
        depura.metdeb(e)
    if e.DEBUG:
        debout(e)
    return pout


def debout(e):
    """DEBOUT: componentes del penacho en el receptor (fichero MODEL de DEBUGOPT)."""
    depura.debout(e)


# ------------------------------------------------------------------------------ deposición
# VDP: factor de estabilidad por uso del suelo (Stab) y tabla de resistencias (Restab) por uso del
# suelo (1-9), tipo de resistencia (1 Ri, 2 Rcs, 3 Rco, 4 Raci, 5 Rgs, 6 Rgo) y estación de Wesely
# (1-5); filas en el orden de las sentencias DATA (estación, después tipo)
_STAB = (0.0, 1.0e-5, 6.0, 5.0, 7.0, 3.0, 4.0, 1.0e-5, 1.0e-5, 3.0)
_RESTAB_FILAS = (
    (1.e07, 60., 120., 100., 200., 150., 1.e07, 1.e07, 80.),
    (1.e07, 2000., 2000., 2000., 2000., 2000., 1.e07, 1.e07, 2.5e3),
    (1.e07, 1000., 1000., 1000., 2000., 2000., 1.e07, 1.e07, 1.e3),
    (100., 200., 100., 2000., 100., 1500., 0., 0., 300.),
    (400., 150., 350., 300., 500., 450., 0., 1000., 0.),
    (300., 150., 200., 200., 300., 300., 2.e3, 400., 1.e3),
    (1.e07, 1.e07, 1.e07, 350., 1.e07, 700., 1.e07, 1.e07, 1.e07),
    (1.e07, 6500., 6500., 3000., 2000., 2000., 1.e07, 1.e07, 6.5e3),
    (1.e07, 400., 300., 500., 600., 1000., 1.e07, 1.e07, 300.),
    (100., 150., 100., 1700., 100., 1200., 0., 0., 200.),
    (400., 200., 350., 300., 500., 450., 0., 1.e3, 0.),
    (300., 150., 200., 200., 300., 300., 2.0e3, 400., 8.e2),
    (1.e07, 1.e07, 1.e07, 500., 1.e07, 1000., 1.e07, 1.e07, 1.e07),
    (1.e07, 1.e07, 9000., 6000., 2000., 2000., 1.e07, 1.e07, 9.e3),
    (1.e07, 1.e07, 400., 600., 800., 1600., 1.e07, 1.e07, 8.e2),
    (100., 0., 100., 1500., 100., 1000., 0., 0., 1.e2),
    (400., 150., 350., 300., 500., 450., 0., 0., 1.e3),
    (300., 150., 200., 200., 300., 300., 2.e3, 400., 1.e3),
    (1.e07, 1.e07, 1.e07, 800., 1.e07, 1600., 1.e07, 1.e07, 1.e07),
    (1.e07, 1.e07, 1.e07, 400., 1.e07, 800., 1.e07, 1.e07, 9.e3),
    (1.e07, 2000., 1000., 600., 2000., 1200., 1.e07, 1.e07, 8.e2),
    (100., 0., 10., 1500., 100., 1000., 0., 0., 50.),
    (100., 100., 100., 100., 200., 200., 0., 1.e3, 100.),
    (600., 3500., 3500., 3500., 500., 500., 2.e3, 400., 3.5e3),
    (1.e07, 100., 120., 100., 200., 150., 1.e07, 1.e07, 80.),
    (1.e07, 2000., 2000., 1500., 2000., 2000., 1.e07, 1.e07, 2.e3),
    (1.e07, 1000., 250., 350., 500., 700., 1.e07, 1.e07, 300.),
    (100., 50., 80., 1500., 100., 1000., 0., 0., 200.),
    (500., 150., 350., 300., 500., 450., 0., 1.e3, 0.),
    (300., 150., 200., 200., 300., 300., 2.e3, 400., 1.e3))


def _restab(lanuse, j, isea5):
    return _RESTAB_FILAS[(isea5 - 1) * 6 + (j - 1)][lanuse - 1]


def deposicion_fuente(e, puntual):
    """Variables de deposición de la fuente ISRC para la hora (bloque común de PCALC, VCALC y
    ACALC antes del bucle de receptores): velocidad de deposición seca (GASDEPVD o VDP), altura
    ZSUBP (cima del penacho a 20 km, entre 500 y 10000 m) y coeficientes de lavado (SCAVRAT).
    `puntual`: fuente puntual (la altura del penacho a 20 km incluye la sobreelevación)."""
    funciones_dispersion, sigmas, parametros_efectivos, integracion_area, resultados = _m()
    if e.LUSERVD and e.LDGAS and e.NPD == 0:
        e.VDEPG = e.USERVD
    elif e.LDPART or (not e.LUSERVD and e.LDGAS and e.NPD == 0):
        vdp(e)
    if e.LWPART or e.LWGAS:
        heff(e, 20000.0)
        if e.STABLE or (e.UNSTAB and e.HS >= e.ZI):
            if puntual:
                e.HE = e.HSP + e.DHCRIT
                sigmas.sigz(e, 20000.0)
                e.ZSUBP = max(500.0, e.ZI, e.HE + e.SZCOEF * e.SZAS)
            else:
                sigmas.sigz(e, 20000.0)
                e.ZSUBP = max(500.0, e.ZI, e.HS + e.SZCOEF * e.SZAS)
        elif e.UNSTAB:
            if puntual:
                e.HED1 = e.HSP + e.DHCRIT
                if e.PPF > 0.0:
                    sigmas.cblpr3(e)
                sigmas.sigz(e, 20000.0)
                if e.PPF == 0.0:
                    e.ZSUBP = max(500.0, e.ZI, e.HED1 + e.SZCOEF * (e.SZAD1 + e.SZAD2) / 2.0)
                elif e.PPF == 1.0:
                    e.ZSUBP = max(500.0, e.ZI, e.HE3 + e.SZCOEF * e.SZA3)
                else:
                    e.ZSUBP = max(500.0, e.ZI, e.PPF * (e.HE3 + e.SZCOEF * e.SZA3) +
                                  (1.0 - e.PPF) * (e.HED1 + e.SZCOEF * (e.SZAD1 + e.SZAD2) / 2.0))
            else:
                sigmas.sigz(e, 20000.0)
                e.ZSUBP = max(500.0, e.ZI, e.HS + e.SZCOEF * (e.SZAD1 + e.SZAD2) / 2.0)
        e.ZSUBP = min(10000.0, e.ZSUBP)
        scavrat(e)


def vdp(e):
    """VDP: velocidades de deposición seca de partículas (VDEP, por categoría de tamaño; método 1
    o método 2) y de gases (VDEPG) según Wesely et al. (2001). Fija también ZRDEP, XNU, SCHMIDT,
    RCUT, RM y acota la humedad relativa RH (global) entre 5 y 100."""
    isrc = e.ISRC
    npd = e.NPD
    sfact = 0.0
    rlai = 0.0
    ri = rgs = rgo = rcs = rco = raci = 0.0
    gr = 0.0
    dv = 0.219e-04
    po = 101.3
    to = 273.16
    alfa = 0.1
    pressure = e.SFCP / 10.0
    if pressure < 10.0:
        pressure = 100.0
    isea5 = 0
    rb = rc = rp = 0.0
    rds = [0.0] * (npd + 1)
    if npd == 0 and e.LDGAS and not e.LUSERVD:
        # uso del suelo del sector de la dirección del flujo (como IFVSEC) y estación del mes
        iland = int(e.AFV * 0.10 + 0.4999)
        if iland == 0:
            iland = 36
        lanuse = int(e.ILAND_GD[iland])
        isea5 = int(e.ISEAS_GD[e.IMONTH])
        if lanuse < 1 or isea5 < 1:
            # GDLANUSE con menos de 36 sectores o GDSEASON con menos de 12 meses
            raise NoTraducido("VDP: uso del suelo o estación sin definir (lectura fuera de límites en el "
                              "original)")
        sfact = _STAB[lanuse]
        ri = _restab(lanuse, 1, isea5)
        rcs = _restab(lanuse, 2, isea5)
        rco = _restab(lanuse, 3, isea5)
        raci = _restab(lanuse, 4, isea5)
        rgs = _restab(lanuse, 5, isea5)
        rgo = _restab(lanuse, 6, isea5)
        f = 0.0
        if isea5 == 1 or isea5 == 3 or isea5 == 4:
            f = 1.0
        elif isea5 == 2:
            f = e.FSEAS2
        elif isea5 == 5:
            f = e.FSEAS5
        if lanuse == 4 or lanuse == 6:
            rlai = f
            gr = 30.0
        else:
            rlai = math.sqrt(f)
            gr = 100.0
    elif npd == 0 and e.LDGAS and e.LUSERVD:
        return
    e.ZRDEP = e.SFCZ0 + 1.0
    if e.RH > 100.0:
        e.RH = 100.0
    if e.RH < 5.0:
        e.RH = 5.0
    de = ((100.0 - e.RH) / 100.0) * e.ESTA
    if de < 0.0:
        de = 0.0
    qsat = 1.0e03 * 0.622 * e.ESTA / (pressure - 0.378 * e.ESTA)
    vp = (e.RH / 100.0) * e.ESTA
    q = 1.0e03 * 0.622 * vp / (pressure - 0.378 * vp)
    dq = qsat - q
    if dq <= 0.0:
        dq = 0.001
    ustar, obulen, z0, zr = e.USTAR, e.OBULEN, e.SFCZ0, e.ZRDEP
    if obulen >= 0.0:
        ra = (1.0 / (e.VONKAR * ustar)) * (math.log(zr / z0) + 5.0 * zr / obulen)
    else:
        sr = math.sqrt(1.0 - 16.0 * zr / obulen)
        s0 = math.sqrt(1.0 - 16.0 * z0 / obulen)
        ra = (1.0 / (e.VONKAR * ustar)) * math.log(((sr - 1.0) * (s0 + 1.0)) / ((sr + 1.0) * (s0 - 1.0)))
    e.XNU = 0.1505 * 1.0e-4 * ((e.TA / to) ** 1.772) * (pressure / po) * (1.0 + 0.0132 * (pressure - po))
    if npd == 0 and e.LDGAS:
        # velocidad de deposición de gases
        f1 = ((e.QSW / gr) + 0.01) / ((e.QSW / gr) + 1.0)
        if f1 <= 0.01:
            f1 = 0.01
        if f1 > 1.0:
            f1 = 1.0
        if ri == 1.0e07:
            f1 = 0.01
        f3 = 1.0 / (1.0 + alfa * de)
        if f3 <= 0.01:
            f3 = 0.01
        d = 298.2 - e.TA
        f4 = 1.0 - 0.0016 * (d * d)
        if f4 <= 0.01:
            f4 = 0.01
        # superficie mojada (rocío o lluvia en la hora o en las dos anteriores)
        ppp = e.PRATE + e.PREC1 + e.PREC2
        a = 0.30
        if e.NCLOUD <= 2:
            a = 0.45
        if e.NCLOUD >= 8:
            a = 0.15
        if isea5 == 4 and e.IPCODE > 18 and e.TA < to:
            # superficie cubierta de nieve: sin ajuste por superficie mojada
            rcox = rco
        elif (ustar < (a / dq) and (e.IHOUR < 8 or e.IHOUR > 19)) or ppp > 0.0:
            rcs = 50.0
            rcox = 0.75 * rco
            rgs = 50.0
            if ustar < (a / dq) and (e.IHOUR < 8 or e.IHOUR > 19):
                if ra < 1000.0:
                    ra = 1000.0
        else:
            rcox = rco
        # heladas fuertes
        rx = 1.0e03 * math.exp(-(e.TA - 269.2))
        rcs = rcs + rx
        rgs = rgs + rx
        rgo = rgo + rx
        rcox = rcox + rx
        rac = 0.3 * raci / ustar
        d_suba = e.PDIFF[isrc]
        henry = e.HENRY[isrc]
        fo = e.FO
        rb = 2.2 * ((e.XNU / d_suba) ** (2.0 * e.THIRD)) / (e.VONKAR * ustar)
        rs = ri * (dv / d_suba) / (f1 * e.F2 * f3 * f4)
        if rs > 1.0e07:
            rs = 1.0e07
        e.RM = 1.0 / ((0.034 / henry) + 100.0 * fo)
        if e.RM > 1.0e07:
            e.RM = 1.0e07
        rcl = e.RCLI[isrc] / (rlai * sfact)
        rcl = rcl + rx
        if rcl < 100.0:
            rcl = 100.0
        e.RCUT = 1.0 / ((1.0e-3 / (henry * rcs)) + ((fo + fo * fo / henry) / rcox) + (1.0 / rcl))
        rg = 1.0 / ((1.0e-3 / (henry * rgs)) + ((fo + (0.1 * fo * fo)) / rgo))
        if rg > 1.0e07:
            rg = 1.0e07
        rc = 1.0 / ((rlai / (rs + e.RM)) + (rlai / e.RCUT) + (1.0 / (rac + rg)))
        e.VDEPG = 1.0 / (ra + rb + rc)
    elif npd > 0:
        if not e.L_METHOD2[isrc]:
            # método 1 (ISCST3 con la Rb modificada, ec. 21)
            t1 = ustar * ustar / e.XNU
            for i in range(1, npd + 1):
                st = e.TSTOP[i] * t1
                xinert = 10.0 ** (-3.0 / st)
                d_sub_b = 8.09e-14 * (e.TA * e.SCF[i] / e.PDIAM[i])
                e.SCHMIDT[i] = e.XNU / d_sub_b
                if e.WSTAR <= 0.0:
                    gust_adj = 1.0
                else:
                    gust_adj = 1.0 + 0.24 * e.WSTAR * e.WSTAR / (ustar * ustar)
                rd = 1.0 / (gust_adj * ustar * (e.SCHMIDT[i] ** (-2.0 * e.THIRD) + xinert))
                rds[i] = rd
                e.VDEP[i] = 1.0 / (ra + rd + ra * rd * e.VGRAV[i]) + e.VGRAV[i] + e.VDPHOR
            if e.DEBUG or e.DEPOSDBG:
                depura.vdp_part(e, ra, rds)
        else:
            # método 2: partículas finas y gruesas
            if obulen >= 0.0:
                rp = 500.0 / ustar
            else:
                rp = 500.0 / (ustar * (1.0 - (300.0 / obulen)))
            d_sub_b = 8.09e-14 * (e.TA * e.SCF[1] / e.PDIAM[1])
            e.SCHMIDT[1] = e.XNU / d_sub_b
            vd1 = 1.0 / (ra + rp)
            vd2 = 0.002 + (1.0 / (ra + rp + 0.002 * ra * rp))
            fm = e.FINEMASS[isrc]
            e.VDEP[1] = fm * vd1 + (1.0 - fm) * vd2
    if e.DEBUG or e.DEPOSDBG:
        depura.vdp_fin(e, ra, rb, rc, rds, rp)


def scavrat(e):
    """SCAVRAT: coeficientes de lavado húmedo (Walcek) de partículas (PSCVRT, WASHOUT, ECOLL; la
    eficiencia de colisión según Slinn y Seinfeld-Pandis) o de gases (GSCVRT); fija también
    LIQCONT, DENOM y FRACSAT."""
    rhow = 1.0e6
    npd = e.NPD
    prate = e.PRATE
    if e.DEBUG or e.DEPOSDBG:
        depura.scavrat_ent(e)
    if prate == 0.0:
        if npd > 0:
            e.PSCVRT[:] = 0.0
            e.WASHOUT[:] = 0.0
            e.ECOLL[:] = 0.0
        else:
            e.GSCVRT = 0.0
    elif npd > 0:
        vfall = 3.75 * prate ** 0.111
        rdrop = (prate ** 0.232) / 18.11
        isrc = e.ISRC
        for i in range(1, npd + 1):
            if not e.L_METHOD2[isrc]:
                reynold = rdrop * 0.01 * vfall / e.XNU
                sch = e.SCHMIDT[i]
                term1 = (4.0 / (reynold * sch)) * (1.0 + 0.4 * math.sqrt(reynold) * sch ** e.THIRD +
                                                   0.16 * math.sqrt(reynold * sch))
                kappa = (e.PDIAM[i] * 1.0e-6) / (rdrop * 0.02)
                term2 = 4.0 * kappa * (1.81e-2 + kappa * (1.0 + 2.0 * math.sqrt(reynold)))
                stoke = e.TSTOP[i] * (vfall - e.VGRAV[i]) / (rdrop * 0.01)
                sstar = (1.2 + math.log(1.0 + reynold) / 12.0) / (1.0 + math.log(1.0 + reynold))
                sstar = min(sstar, stoke)
                term3 = ((stoke - sstar) / (stoke - sstar + 2.0 * e.THIRD)) ** 1.5
                term3 = term3 * math.sqrt(1.0 / e.PDENS[i])
                e.ECOLL[i] = min(1.0, term1 + term2 + term3)
                e.WASHOUT[i] = 1.5 * (e.ZSUBP * e.ECOLL[i]) / (2.0 * rdrop * 0.01)
            else:
                # método 2: lavado de Wesely et al. (2001) con las fracciones fina y gruesa
                fm = e.FINEMASS[isrc]
                e.WASHOUT[i] = 1.0e5 * e.PDIAM[i] * fm + 1.0e5 * 6.0 * (1 - fm)
                e.ECOLL[i] = ((2.0 * rdrop * 0.01) * e.WASHOUT[i]) / (1.5 * e.ZSUBP)
                e.ECOLL[i] = min(1.0, e.ECOLL[i])
            if prate > 0.0:
                e.PSCVRT[i] = 1.5 * e.ECOLL[i] * prate / (2.0 * rdrop * 3.6e4)
            else:
                e.PSCVRT[i] = 0.0
    else:
        vfall = 3.75 * prate ** 0.111
        rdrop = (prate ** 0.232) / 18.11
        e.LIQCONT = (prate ** 0.889) / 13.28
        fsubg = 80.0 * rdrop + 1.0
        if rdrop < 0.01:
            fsubl = 1.0
        elif rdrop <= 0.05:
            fsubl = 2.6
        else:
            fsubl = 20.0
        isrc = e.ISRC
        henry = e.HENRY[isrc]
        rgas, ta = e.RGAS, e.TA
        r2 = rdrop * rdrop
        e.DENOM = (1.0 + (e.LIQCONT * rgas * ta) / (henry * rhow))
        tabs = (r2 * rgas * ta / (henry * 3.0 * e.PDIFF[isrc] * 1.0e4 * fsubg) +
                (4.0 * rdrop * rgas * ta) / (henry * 3.0 * 50000.0 * 0.01) +
                (r2 * 0.17) / (3.0 * e.PDIFFW[isrc] * 1.0e4 * fsubl)) / e.DENOM
        tres = e.ZSUBP / vfall
        e.FRACSAT = min(1.0, tres / tabs)
        e.GSCVRT = (e.FRACSAT * rgas * ta * prate) / (3600.0 * e.ZSUBP * henry * 1.0e3 * e.DENOM)
    if e.DEBUG or e.DEPOSDBG:
        depura.scavrat_res(e)


def pdep(e, xarg):
    """PDEP: factores de agotamiento del penacho de partículas a la distancia XARG, por
    sedimentación y deposición seca (DQCOR, integrando con DEPLETE) y por lavado (WQCOR)."""
    for i in range(1, e.NPD + 1):
        e.DQCOR[i] = 1.0
        e.WQCOR[i] = 1.0
        if e.DDPLETE:
            e.VSETL = e.VGRAV[i]
            e.DQCOR[i] = deplete(e, e.VDEP[i], xarg, e.ROMBERG, 1)
        if e.WDPLETE and e.PSCVRT[i] > 0.0:
            e.WQCOR[i] = math.exp(-e.PSCVRT[i] * xarg / e.US)


def pdepg(e, xarg):
    """PDEPG: factores de agotamiento del penacho de gases (DQCORG seco, WQCORG húmedo)."""
    e.DQCORG = 1.0
    e.WQCORG = 1.0
    if e.DDPLETE:
        e.DQCORG = deplete(e, e.VDEPG, xarg, e.ROMBERG, 1)
    if e.WDPLETE and e.GSCVRT > 0.0:
        e.WQCORG = math.exp(-e.GSCVRT * xarg / e.US)


def deplete(e, vdi, xri, lromb, ifct):
    """DEPLETE (y PRM_DEPLETE con ifct = 2): integral del término vertical a lo largo de la
    trayectoria entre 1 m y XRI, por Romberg (QATR2, si ROMBERG) o por Gauss de 2 puntos (QG2D2).
    Devuelve QCOR, la fracción de la emisión que queda en el penacho."""
    if lromb:
        eps = 0.050
        value = qatr2(e, 1.0, xri, eps, 12, ifct)
    else:
        value = qg2d2(e, 1.0, xri, ifct)
    if vdi * value > 50.0:
        value = 50.0 / vdi
    elif vdi * value < -50.0:
        value = -50.0 / vdi
    return math.exp(-vdi * value)


def _fct_dep(e, ifct, x):
    """Integrando de DEPLETE: F2INT (ifct = 1) o PRM_F2INT (ifct = 2)."""
    if ifct == 1:
        return f2int(e, x)
    from . import calculo_punto_volumen
    return calculo_punto_volumen.prm_f2int(e, x)


def qatr2(e, xl, xu, eps, ndim, ifct):
    """QATR2: integración de Romberg (DQATR de IBM SSP) del integrando de DEPLETE, con el
    criterio de convergencia de AERMOD (integral < 1e-10, error relativo EPS o paso < 1 m).
    Devuelve la integral (el estado IER y el número de pasos no se usan)."""
    aux = np.zeros(ndim + 1)
    half = 0.5
    aux[1] = half * (_fct_dep(e, ifct, xl) + _fct_dep(e, ifct, xu))
    h = xu - xl
    if h == 0.0 or aux[1] == 0.0:
        return 0.0
    hh = h
    p = 1.0
    jj = 1
    for i in range(2, ndim + 1):
        y = aux[1]
        hd = hh
        hh = half * hh
        p = half * p
        x = xl + hh
        sm = 0.0
        for _j in range(1, jj + 1):
            sm = sm + _fct_dep(e, ifct, x)
            x = x + hd
        aux[i] = half * aux[i - 1] + p * sm
        q = 1.0
        for j in range(1, i):
            ii = i - j
            q = q + q
            q = q + q
            aux[ii] = aux[ii + 1] + (aux[ii + 1] - aux[ii]) / (q - 1.0)
        delt2 = abs(y - aux[1])
        if i >= 3:
            if aux[1] < 1.0e-10:
                return h * aux[1]
            elif delt2 <= eps * abs(aux[1]):
                return h * aux[1]
            elif hh < 1.0:
                return h * aux[1]
        jj = jj + jj
    return h * aux[1]


def qg2d2(e, xl, xu, ifct):
    """QG2D2: integral por cuadratura de Gauss de 2 puntos del integrando de DEPLETE (los dos
    puntos se evalúan en el orden del original: A+Y y después A-Y)."""
    a = 0.5 * (xu + xl)
    b = xu - xl
    y = 0.2886751 * b
    f1 = _fct_dep(e, ifct, a + y)
    f2 = _fct_dep(e, ifct, a - y)
    return 0.5 * b * (f1 + f2)


def f2int(e, xi):
    """F2INT: integrando de DEPLETE a la distancia XI (término vertical a la altura de referencia
    de la deposición, mezcla de los penachos horizontal y que sigue el terreno). Recalcula el
    penacho a esa distancia (las cotas del receptor se interpolan linealmente entre la fuente y el
    receptor) con la inclinación por sedimentación VSETL; para todas las fuentes usa las sigmas de
    PDIS (como el original)."""
    funciones_dispersion, sigmas, parametros_efectivos, integracion_area, resultados = _m()
    e.UEFF = e.US
    e.SVEFF = e.SVS
    e.SWEFF = e.SWS
    e.TGEFF = e.TGS
    if e.UNSTAB and (e.HS < e.ZI):
        e.UEFFD = e.US
        e.SVEFFD = e.SVS
        e.SWEFFD = e.SWS
        e.UEFFN = e.US
        e.SVEFFN = e.SVS
        e.SWEFFN = e.SWS
        e.UEFF3 = e.US
        e.SVEFF3 = e.SVS
        e.SWEFF3 = e.SWS
        e.TGEFF3 = e.TGS
    zetmp = e.ZELEV
    e.ZELEV = e.ZS + (zetmp - e.ZS) * xi / e.XDIST
    zhtmp = e.ZHILL
    e.ZHILL = e.HS + (zhtmp - e.HS) * xi / e.XDIST
    centroid(e, xi)
    centroid(e, xi)
    t = e.SRCTYP[e.ISRC]
    if t[:5] == "POINT":
        sigmas.deltah(e, xi)
    if (t == "VOLUME" or t[:4] == "AREA") and e.AFTSRC[e.ISRC] == "Y":
        raise NoTraducido("AIRCRAFT (ADELTAH)")
    if e.UNSTAB and (e.HS < e.ZI):
        funciones_dispersion.pdf(e)
    heff(e, xi)
    parametros_efectivos.iblval(e, xi)
    if e.UNSTAB and (e.HS < e.ZI):
        funciones_dispersion.pdf(e)
        heff(e, xi)
    pdis(e, xi)
    if e.AFTSRC[e.ISRC] == "Y":
        if t == "VOLUME":
            vdis(e, xi)
        elif t[:4] == "AREA":
            adisy(e, xi)
            adisz(e, xi)
    e.HV = (xi / e.US) * e.VSETL
    if e.STABLE or (e.UNSTAB and (e.HS >= e.ZI)):
        e.HESETL = max(0.0, e.HE - e.HV)
        e.HSBL = refl_ht(e, e.HESETL, xi, e.SZB, 0.0)
    elif e.UNSTAB:
        e.HESETL = max(0.0, 0.5 * (e.HED1 + e.HED2) - e.HV)
        e.HSBL = 0.0
    if e.UNSTAB and (e.HS < e.ZI) and (e.PPF > 0.0):
        e.HE3SETL = max(0.0, e.HE3 - e.HV)
        e.HPEN = refl_ht(e, e.HE3SETL, xi, e.SZB3, 0.0)
        e.HPEN = max(e.HPEN, e.ZI)
    else:
        e.HPEN = 0.0
    funciones_dispersion.critds(e, e.HESETL)
    funciones_dispersion.pfract(e, e.HESETL)
    funciones_dispersion.fterm(e)
    vwrap = 0.0
    if e.FOPT == 0.0:
        vwrap = 0.0
    else:
        e.ZR = e.ZRT + e.ZRDEP
        vwrap = _f2int_vertical(e)
    if e.ZRT == 0.0:
        vlift = vwrap
    elif e.FOPT == 1.0:
        vlift = 0.0
    else:
        e.ZR = e.ZRDEP
        vlift = _f2int_vertical(e)
    res = e.FOPT * vwrap + (1.0 - e.FOPT) * vlift
    e.ZELEV = zetmp
    e.ZHILL = zhtmp
    return res


def _f2int_vertical(e):
    """F2INT: término vertical dividido por el viento efectivo a la altura ZR (VWRAP o VLIFT)."""
    funciones_dispersion = _m()[0]
    v = 0.0
    if e.STABLE or (e.UNSTAB and (e.HS >= e.ZI)):
        if e.ZR <= e.HSBL:
            funciones_dispersion.vrtsbl(e, e.SZ, max(0.0, e.HE - e.HV), e.HSBL)
        else:
            funciones_dispersion.vrtsbn(e, e.SZ, max(0.0, e.HE - e.HV))
        v = e.FSUBZ / e.UEFF
    elif e.UNSTAB:
        if e.PPF < 1.0:
            if e.ZR <= e.ZI:
                funciones_dispersion.vrtcbl(e, e.HED1 - e.HV, e.HED2 - e.HV, e.SZD1, e.SZD2, 1.0)
                e.FSUBZD = e.FSUBZ
            else:
                e.FSUBZD = 0.0
            if e.ZR <= e.ZI:
                funciones_dispersion.vrtcbl(e, e.HEN1 - e.HV, e.HEN2 - e.HV, e.SZN1, e.SZN2, -1.0)
                e.FSUBZN = e.FSUBZ
            else:
                e.FSUBZN = 0.0
        else:
            e.FSUBZD = 0.0
            e.FSUBZN = 0.0
        if e.PPF > 0.0:
            if e.ZR <= e.HPEN:
                funciones_dispersion.vrtsbl(e, e.SZ3, max(0.0, e.HE3 - e.HV), e.HPEN)
            else:
                funciones_dispersion.vrtsbn(e, e.SZ3, max(0.0, e.HE3 - e.HV))
            e.FSUBZ3 = e.FSUBZ
            if e.PPF < 1.0:
                v = (1.0 - e.PPF) * e.FSUBZD / e.UEFFD + (1.0 - e.PPF) * e.FSUBZN / e.UEFFN + \
                    e.PPF * e.FSUBZ3 / e.UEFF3
            else:
                v = e.PPF * e.FSUBZ3 / e.UEFF3
        else:
            e.FSUBZ3 = 0.0
            e.HPEN = 0.0
            v = e.FSUBZD / e.UEFFD + e.FSUBZN / e.UEFFN
    return v


# ------------------------------------------------------------------------- química del NO2
def _cero_chi(e, irec, isrc):
    """Pone a cero CHI y, con PVMRM/GRSM, los datos del penacho de la fuente en el receptor (para
    que no persista el valor de la hora anterior)."""
    e.CHI[irec, isrc, :] = 0.0
    if e.GRSM:
        e.CHI_TTRAVCHM[irec, isrc] = 0.0
    if e.PVMRM or e.GRSM:
        e.HECNTR[irec, isrc] = 0.0
        e.UEFFS[irec, isrc] = 0.0
        e.EPSEF[irec, isrc] = 0.0
        e.PPFACT[irec, isrc] = 0.0
        e.HECNTR3[irec, isrc] = 0.0
        e.UEFF3S[irec, isrc] = 0.0
        e.EPSEF3[irec, isrc] = 0.0
        e.FOPTS[irec, isrc] = 0.0


def _guardar_chi(e, irec, isrc):
    """Guarda HRVAL de la fuente en el receptor (CHI) y, con PVMRM/GRSM, la altura del penacho,
    el viento efectivo, la disipación, la fracción penetrada y FOPT; la suma a los grupos la hace
    después la rutina de la opción de NO2."""
    for ityp in range(1, e.NUMTYP + 1):
        e.CHI[irec, isrc, ityp] = e.HRVAL[ityp]
    if e.PVMRM or e.GRSM:
        if e.STABLE or (e.UNSTAB and e.HS >= e.ZI):
            e.HECNTR[irec, isrc] = e.HE
            e.UEFFS[irec, isrc] = e.UEFF
            e.EPSEF[irec, isrc] = e.EPSEFF
        else:
            e.HECNTR[irec, isrc] = e.CENTER
            e.UEFFS[irec, isrc] = e.UEFFD
            e.EPSEF[irec, isrc] = e.EPSEFFD
        if e.PPF > 0.0:
            e.PPFACT[irec, isrc] = e.PPF
            e.HECNTR3[irec, isrc] = e.HE3
            e.UEFF3S[irec, isrc] = e.UEFF3
            e.EPSEF3[irec, isrc] = e.EPSEFF3
        else:
            e.PPFACT[irec, isrc] = 0.0
            e.HECNTR3[irec, isrc] = 0.0
            e.UEFF3S[irec, isrc] = 0.0
            e.EPSEF3[irec, isrc] = 0.0
        e.FOPTS[irec, isrc] = e.FOPT


# ----------------------------------------------------------------------------------- ACALC
def _cero_receptor(e, aerout):
    """Pone a cero la contribución del receptor (ramas CYCLE RECEPTOR_LOOP de ACALC)."""
    if e.RUNTTRM:
        e.TTRMOUT[e.IREC, e.ISRC, 11] = 0.0
    if e.PVMRM or e.OLM or e.ARM2 or e.RUNTTRM or e.GRSM:
        _cero_chi(e, e.IREC, e.ISRC)
    e.HRVAL[:] = 0.0
    e.AERVAL[:] = 0.0
    aerout[:] = 0.0


def ardist(e, indx):
    """ARDIST: distancias receptor-vértices de un área. Devuelve (XDEP, WIDTH, LENGTH, XMINREC,
    XMAXREC); fija XR, YR, ZELEV, ZHILL, ZFLAG, X, Y, DISTR, ZRT y SPA."""
    e.XR = e.AXR[indx]
    e.YR = e.AYR[indx]
    e.ZELEV = e.AZELEV[indx]
    e.ZHILL = e.AZHILL[indx]
    e.ZFLAG = e.AZFLAG[indx]
    xminrec = 9.0e10
    xmaxrec = -9.0e10
    yminrec = 9.0e10
    ymaxrec = -9.0e10
    spa = e.SPA
    spa[:, :] = 0.0
    xr, yr = e.XR, e.YR
    wdsin, wdcos = e.WDSIN, e.WDCOS
    xv, yv = e.XVERT, e.YVERT
    for i in range(1, e.NVERT + 2):
        xsrc = xv[i]
        ysrc = yv[i]
        s1 = -((xr - xsrc) * wdsin + (yr - ysrc) * wdcos)
        s2 = (xr - xsrc) * wdcos - (yr - ysrc) * wdsin
        spa[i, 1] = s1
        spa[i, 2] = s2
        xminrec = min(xminrec, s1)
        xmaxrec = max(xmaxrec, s1)
        yminrec = min(yminrec, s2)
        ymaxrec = max(ymaxrec, s2)
    width = ymaxrec - yminrec
    length = xmaxrec - xminrec
    if e.AREADBG:
        raise NoTraducido("AREADBG")
    if xminrec >= 0.0:
        xdep = xminrec + length / 3.0
    else:
        xdep = xmaxrec / 3.0
    xdep = max(1.0, xdep)
    e.X = -((xr - e.XCNTR) * wdsin + (yr - e.YCNTR) * wdcos)
    e.Y = (xr - e.XCNTR) * wdcos - (yr - e.YCNTR) * wdsin
    e.DISTR = math.sqrt(e.X * e.X + e.Y * e.Y)
    if e.L_FLATSRC[e.ISRC]:
        e.ZRT = e.ZFLAG
    else:
        e.ZRT = e.ZELEV - e.ZS + e.ZFLAG
    return xdep, width, length, xminrec, xmaxrec


def _met_urbana(e):
    """Selección de la meteorología urbana/rural de la fuente (común a ACALC, PCALC, VCALC)."""
    isrc = e.ISRC
    mx = e.MXGLVL
    if e.URBSRC[isrc] == "Y":
        for i in range(1, e.NUMURB + 1):
            if e.IURBGRP[isrc, i] == 1:
                e.IURB = i
                break
        iu = e.IURB
        if e.STABLE or e.L_MORNINGTRANS[iu]:
            e.URBSTAB = True
            e.ZI = max(e.ZIURB[iu], e.ZIMECH)
            e.GRIDSV[1:mx + 1] = e.GRDSVU[1:mx + 1, iu]
            e.GRIDSW[1:mx + 1] = e.GRDSWU[1:mx + 1, iu]
            e.GRIDTG[1:mx + 1] = e.GRDTGU[1:mx + 1, iu]
            e.GRIDPT[1:mx + 1] = e.GRDPTU[1:mx + 1, iu]
            e.OBULEN = e.URBOBULEN[iu]
            e.USTAR = e.URBUSTR[iu]
        else:
            _met_rural(e)
    elif e.URBAN and e.URBSRC[isrc] == "N":
        _met_rural(e)
    else:
        e.URBSTAB = False


def _met_rural(e):
    mx = e.MXGLVL
    e.URBSTAB = False
    e.ZI = e.ZIRUR
    e.GRIDSV[1:mx + 1] = e.GRDSVR[1:mx + 1]
    e.GRIDSW[1:mx + 1] = e.GRDSWR[1:mx + 1]
    e.GRIDTG[1:mx + 1] = e.GRDTGR[1:mx + 1]
    e.GRIDPT[1:mx + 1] = e.GRDPTR[1:mx + 1]
    e.OBULEN = e.RUROBULEN
    e.USTAR = e.RURUSTR


def acalc(e):
    """ACALC: cálculo para una fuente de área (AREA, AREAPOLY, AREACIRC, LINE)."""
    funciones_dispersion, sigmas, parametros_efectivos, integracion_area, resultados = _m()
    isrc = e.ISRC
    numtyp = e.NUMTYP
    e.WAKE = False
    e.L_APLUME = True
    fran = 0.0
    e.HRVAL[:] = 0.0
    e.AERVAL[:] = 0.0
    aerout = np.zeros(numtyp + 1)
    e.PRMVAL[:] = 0.0
    if e.allocated("CHI"):
        e.CHI[:, isrc, :] = 0.0
    if e.GRSM:
        e.CHI_TTRAVCHM[:, isrc] = 0.0
    setsrc(e)
    funciones_dispersion.emfact(e, e.QS)
    if e.EVAL[isrc]:
        raise NoTraducido("EVALFILE")
    if e.AREADBG:
        raise NoTraducido("AREADBG")
    if e.QTK == 0.0:
        return
    qtksav = e.QTK
    _met_urbana(e)
    parametros_efectivos.metini(e)
    e.AWDSIN[isrc] = e.WDSIN
    e.AWDCOS[isrc] = e.WDCOS
    e.AAFV[isrc] = e.AFV
    if e.AFTSRC[isrc] == "Y":
        raise NoTraducido("AIRCRAFT")
    e.FB = 0.0
    e.FM = 0.0
    e.PPF = 0.0
    e.HSP = e.HS
    e.HE = e.HS
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
    if e.UNSTAB and e.HS < e.ZI:
        funciones_dispersion.pdf(e)
    deposicion_fuente(e, False)
    e.AWDSIN[isrc] = e.WDSIN
    e.AWDCOS[isrc] = e.WDCOS
    from . import nucleo
    if nucleo.activo():
        nucleo.acalc_bucle(e, qtksav, aerout)
    else:
        _acalc_bucle(e, qtksav, aerout)


def _acalc_bucle(e, qtksav, aerout):
    """Bucle de receptores de ACALC (la parte que se compila con numba en nucleo.py)."""
    funciones_dispersion, sigmas, parametros_efectivos, integracion_area, resultados = _m()
    numtyp = e.NUMTYP
    fran = 0.0
    for irec in range(1, e.NUMREC + 1):
        e.IREC = irec
        if e.RUNTTRM:
            # valores de DISTR, UEFF y UEFFD que quedan del receptor anterior (como en el original)
            e.TTRMOUT[irec, e.ISRC, 11] = e.DISTR
            e.TTRMOUT[irec, e.ISRC, 12] = e.UEFF
            e.TTRMOUT[irec, e.ISRC, 13] = e.UEFFD
        if e.EVONLY:
            raise NoTraducido("EVENT")
        xdep, width, length, xminr, xmaxr = ardist(e, irec)
        if xmaxr < 1.0 or e.DISTR > e.MAXDIST:
            _cero_receptor(e, aerout)
            e.QTK = qtksav
            continue
        e.HE = e.HS
        e.UEFF = e.US
        e.SVEFF = e.SVS
        e.SWEFF = e.SWS
        e.TGEFF = e.TGS
        if e.UNSTAB and e.HS < e.ZI:
            e.UEFFD = e.US
            e.SVEFFD = e.SVS
            e.SWEFFD = e.SWS
            e.UEFFN = e.US
            e.SVEFFN = e.SVS
            e.SWEFFN = e.SWS
        if not e.L_AREAMNDR:
            if (abs(e.Y) - 0.5 * width) > 0.0:
                adisy(e, xmaxr)
                if (abs(e.Y) - 0.5 * width) >= 5.0 * e.SY:
                    _cero_receptor(e, aerout)
                    e.QTK = qtksav
                    continue
        if e.DEBUG:
            depura.area_efectivos_ini(e)
        funciones_dispersion.critds(e, e.HE)
        if e.URBSTAB:
            vp_fact = e.VIRTPNT_URB[e.KST]
        else:
            vp_fact = e.VIRTPNT_RUR[e.KST]
        xpoint = 1.5 * length + vp_fact * width
        e.XDIST = e.X
        if (not e.FASTAREA and not e.FASTALL) or \
                ((e.FASTAREA or e.FASTALL) and e.X < xpoint):
            if e.ARDPLETE:
                # agotamiento del área calculado una sola vez, a la distancia XDEP
                if e.NPD == 0 and (e.LDGAS or e.LWGAS):
                    pdepg(e, xdep)
                else:
                    e.DQCORG = 1.0
                    e.WQCORG = 1.0
                if e.NPD > 0 and (e.LDPART or e.LWPART):
                    pdep(e, xdep)
                elif e.NPD > 0:
                    e.DQCOR[:] = 1.0
                    e.WQCOR[:] = 1.0
            for ityp in range(1, numtyp + 1):
                e.ITYP = ityp
                e.L_APLUME = True
                integracion_area.areain(e)
                aerout_plm = e.HRVAL[ityp]
                if e.L_AREAMNDR:
                    e.L_APLUME = False
                    integracion_area.areain(e)
                    aerout_pan = e.HRVAL[ityp]
                    if e.STABLE or (e.UNSTAB and e.HS >= e.ZI):
                        fran = funciones_dispersion.meandr(e, e.UEFF, e.SVEFF)
                    elif e.UNSTAB:
                        fran = funciones_dispersion.meandr(e, e.UEFFD, e.SVEFFD)
                    e.HRVAL[ityp] = fran * aerout_pan + (1.0 - fran) * aerout_plm
                else:
                    e.HRVAL[ityp] = aerout_plm
            e.ITYP = numtyp + 1
        else:
            if _acalc_rapido(e, aerout, qtksav):
                continue
        if e.PVMRM or e.OLM or e.RUNTTRM or e.ARM2 or e.GRSM:
            if e.GRSM:
                if e.STABLE or (e.UNSTAB and e.HS >= e.ZI):
                    e.UCHM = e.UEFF
                else:
                    e.UCHM = e.UEFFD
                if e.UCHM != 0:
                    e.CHI_TTRAVCHM[irec, e.ISRC] = max(0.0, e.HRVAL[1] * e.X / e.UCHM)
                else:
                    e.errhdl(e.PATH, "ACALC", "E", "601", "GRSM")
                    e.RUNERR = True
                    return
            _guardar_chi(e, irec, e.ISRC)
            e.HRVAL[:] = 0.0
            e.AERVAL[:] = 0.0
            aerout[:] = 0.0
            continue
        if e.EVONLY:
            raise NoTraducido("EVENT")
        for igrp in range(1, e.NUMGRP + 1):
            e.IGRP = igrp
            resultados.sumval(e)
        e.HRVAL[:] = 0.0
        e.AERVAL[:] = 0.0
        aerout[:] = 0.0


def _acalc_rapido(e, aerout, qtksav):
    """Rama FASTAREA/FASTALL de ACALC: el área se trata como fuente puntual virtual. Devuelve
    True si el receptor se salta (CYCLE RECEPTOR_LOOP)."""
    funciones_dispersion, sigmas, parametros_efectivos, integracion_area, resultados = _m()
    t = e.SRCTYP[e.ISRC]
    if t in ("AREA", "LINE", "AREAPOLY"):
        e.QTK = e.QTK * e.XINIT * e.YINIT
    elif t == "AREACIRC":
        e.QTK = e.QTK * e.PI * e.RADIUS[e.ISRC] * e.RADIUS[e.ISRC]
    e.SYINIT = 0.0
    if e.NPD == 0 and (e.LDGAS or e.LWGAS):
        pdepg(e, e.X)
    else:
        e.DQCORG = 1.0
        e.WQCORG = 1.0
    if e.NPD > 0 and (e.LDPART or e.LWPART):
        pdep(e, e.X)
    elif e.NPD > 0:
        e.DQCOR[:] = 1.0
        e.WQCOR[:] = 1.0
    centroid(e, e.X)
    if e.UNSTAB and e.HS < e.ZI:
        funciones_dispersion.pdf(e)
    heff(e, e.X)
    parametros_efectivos.iblval(e, e.X)
    if e.UNSTAB and e.HS < e.ZI:
        funciones_dispersion.pdf(e)
        heff(e, e.X)
    vdis(e, e.X)
    fyout = funciones_dispersion.fyplm(e, e.SY)
    e.FSUBY = fyout
    e.FSUBYD = e.FSUBY
    e.FSUBYN = e.FSUBYD
    e.FSUBY3 = 0.0
    if e.FSUBY == 0.0 and e.FSUBY3 == 0.0:
        _cero_receptor(e, aerout)
        e.QTK = qtksav
        return True
    if e.NPD == 0:
        adj = e.DQCORG * e.WQCORG
        if e.STABLE or (e.UNSTAB and e.HS >= e.ZI):
            e.HSBL = refl_ht(e, e.HE, e.X, 0.0, e.VSIGZ)
        elif e.UNSTAB:
            e.HSBL = 0.0
        funciones_dispersion.critds(e, e.HE)
        funciones_dispersion.pfract(e, e.HE)
        funciones_dispersion.fterm(e)
        aer_pchi(e, e.X, adj, e.VDEPG, 0, aerout)
        e.HRVAL[:] = aerout
    else:
        for j in range(1, e.NPD + 1):
            e.HV = (e.X / e.US) * e.VGRAV[j]
            adj = e.PHI[j] * e.DQCOR[j] * e.WQCOR[j]
            if e.STABLE or (e.UNSTAB and e.HS >= e.ZI):
                hesetl = max(0.0, e.HE - e.HV)
                e.HSBL = refl_ht(e, hesetl, e.X, 0.0, e.VSIGZ)
            elif e.UNSTAB:
                hesetl = max(0.0, 0.5 * (e.HED1 + e.HED2) - e.HV)
                e.HSBL = 0.0
            funciones_dispersion.critds(e, hesetl)
            funciones_dispersion.pfract(e, hesetl)
            funciones_dispersion.fterm(e)
            aer_pchi(e, e.X, adj, e.VDEP[j], j, aerout)
            e.HRVAL[:] = e.HRVAL + aerout
    e.QTK = qtksav
    return False
