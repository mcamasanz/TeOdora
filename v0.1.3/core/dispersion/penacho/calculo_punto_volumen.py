# -*- coding: utf-8 -*-
"""Traducción de AERMOD 26135 (US EPA, dominio público): fuentes puntuales (calc1.f: PCALC,
AERCALC, PRMCALC, GAMCALC, PRM_PCHI, y el agotamiento del penacho de PRIME: PRM_PDEP, PRM_PDEPG,
PRM_F2INT) y de volumen (VCALC, VOLCALC)."""
import math

import numpy as np

from . import depura
from .estado import NoTraducido
from .perfiles import anyavg, gintrp, locate


_MODS = None


def _m():
    global _MODS
    if _MODS is None:
        from . import calculo_area, funciones_dispersion, parametros_efectivos, estela_edificio, resultados, sigmas
        _MODS = (calculo_area, funciones_dispersion, sigmas, parametros_efectivos, estela_edificio, resultados)
    return _MODS




# ---------------------------------------------------------------------------------- PCALC
def pcalc(e):
    """PCALC: cálculo para una fuente puntual (POINT, POINTCAP, POINTHOR)."""
    calculo_area, funciones_dispersion, sigmas, parametros_efectivos, estela_edificio, resultados = _m()
    isrc = e.ISRC
    nt = e.NUMTYP
    e.HRVAL[:] = 0.0
    e.AERVAL[:] = 0.0
    aerplm = np.zeros(nt + 1)
    aerpan = np.zeros(nt + 1)
    e.PRMVAL[:] = 0.0
    if e.allocated("CHI"):
        e.CHI[:, isrc, :] = 0.0
    if e.GRSM:
        e.CHI_TTRAVPLM = 0.0
        e.CHI_TTRAVPAN = 0.0
        e.CHI_TTRAVAER = 0.0
        e.CHI_TTRAVPRM = 0.0
        e.CHI_TTRAVCHM[:, isrc] = 0.0
        e.BLDFAC[:, isrc] = 0.0
        e.PRMVAL_SRC1 = 0.0
    fran = 0.0
    if e.AWMADWDBG:
        depura.awma_pcalc(e)
    calculo_area.setsrc(e)
    funciones_dispersion.emfact(e, e.QS)
    if e.QTK == 0.0:
        return
    calculo_area._met_urbana(e)
    parametros_efectivos.metini(e)
    vseq = calculo_area.fluxes(e)
    if e.OSPLAT[isrc]:
        e.WAKE = False
    else:
        funciones_dispersion.wakflg(e)
    e.CENTER = e.HS
    e.SURFAC = e.CENTER < 0.1 * e.ZI
    t = e.SRCTYP[isrc]
    if t == "POINTCAP":
        e.HSP = sigmas.hsprim(e.US, vseq, e.HS, e.DS)
    elif t == "POINTHOR":
        e.HSP = e.HS
    elif e.NOSTD:
        e.HSP = e.HS
    else:
        e.HSP = sigmas.hsprim(e.US, e.VS, e.HS, e.DS)
    funciones_dispersion.distf(e)
    penfct = calculo_area.penfct
    penfct(e)
    if e.DEBUG:
        depura.pcalc_delh(e)
    gh = e.GRIDHT
    if e.STABLE or (e.UNSTAB and e.HS >= e.ZI):
        kiter = 0
        while True:
            zplm = e.HSP + 0.5 * e.DHFAER
            dhfold = e.DHFAER
            n = locate(gh, 1, e.MXGLVL, zplm)
            svpm = gintrp(gh[n], e.GRIDSV[n], gh[n + 1], e.GRIDSV[n + 1], zplm)
            upm = gintrp(gh[n], e.GRIDWS[n], gh[n + 1], e.GRIDWS[n + 1], zplm)
            svpm = max(svpm, e.SVMIN, e.SVUMIN * upm)
            if e.L_VECTORWS:
                upm = math.sqrt(upm * upm + 2.0 * svpm * svpm)
            upm = max(upm, e.WSMIN)
            e.UP = 0.5 * (e.US + upm)
            tgpm = gintrp(gh[n], e.GRIDTG[n], gh[n + 1], e.GRIDTG[n + 1], zplm)
            ptpm = gintrp(gh[n], e.GRIDPT[n], gh[n + 1], e.GRIDPT[n + 1], zplm)
            e.TGP = 0.5 * (e.TGS + tgpm)
            ptp = 0.5 * (e.PTS + ptpm)
            e.BVF = math.sqrt(e.G * e.TGP / ptp)
            if e.BVF < 1.0e-10:
                e.BVF = 1.0e-10
            e.BVPRIM = 0.7 * e.BVF
            funciones_dispersion.distf(e)
            kiter += 1
            if e.DEBUG:
                depura.opth2_iter(e, kiter, dhfold, e.DHFAER, zplm)
            if abs((dhfold - e.DHFAER) / e.DHFAER) < 0.01:
                break
            if kiter >= 5:
                e.DHFAER = 0.5 * (e.DHFAER + dhfold)
                if e.DEBUG:
                    depura.pcalc_noconv(e)
                break
        # etiqueta 60: UP, TGP y BVF vuelven a los valores de la boca de la chimenea
        e.UP = e.US
        e.TGP = e.TGS
        ptp = e.PTS
        e.BVF = math.sqrt(e.G * e.TGP / ptp)
        if e.BVF < 1.0e-10:
            e.BVF = 1.0e-10
        e.BVPRIM = 0.7 * e.BVF
    e.PRM_FSTREC = True
    if e.EVAL[isrc]:
        raise NoTraducido("EVALFILE")
    e.ZMIDMX = 0.5 * e.ZI
    if e.DEBUG:
        depura.pcalc_zmid(e)
    e.XFINAL = e.XMAX
    e.DHCRIT = e.DHFAER
    e.XMIXED = e.ZI * e.UAVG / e.SWAVG
    if e.UNSTAB and e.HS < e.ZI:
        if e.XMIXED < 1.25 * e.XFINAL:
            e.XFINAL = 0.8 * e.XMIXED
            sigmas.cblprd(e, e.XFINAL)
            e.DHCRIT = e.DHP1
    if e.UNSTAB and e.HS < e.ZI:
        funciones_dispersion.pdf(e)
    calculo_area.deposicion_fuente(e, True)
    zmid = min(4000.0, (e.HS + 0.5 * e.DHFAER))
    n = locate(gh, 1, e.MXGLVL, zmid)
    valabv = e.GRIDWD[n + 1]
    vbelow = e.GRIDWD[n]
    if (valabv - vbelow) < -180.0:
        valabv = valabv + 360.0
    elif (valabv - vbelow) > 180.0:
        valabv = valabv - 360.0
    if vbelow == valabv:
        e.WDIR = vbelow
    else:
        e.WDIR = gintrp(gh[n], vbelow, gh[n + 1], valabv, zmid)
    if e.WDIR > 360.0:
        e.WDIR = e.WDIR - 360.0
    elif e.WDIR <= 0.0:
        e.WDIR = e.WDIR + 360.0
    e.WDSIN = math.sin(e.WDIR * e.DTORAD)
    e.WDCOS = math.cos(e.WDIR * e.DTORAD)
    e.AWDSIN[isrc] = e.WDSIN
    e.AWDCOS[isrc] = e.WDCOS
    e.AFV = e.WDIR - 180.0
    if e.AFV < 0.0:
        e.AFV = e.AFV + 360.0
    e.AAFV[isrc] = e.AFV
    e.IFVSEC = int(e.AFV * 0.10 + 0.4999)
    if e.IFVSEC == 0:
        e.IFVSEC = 36
    if e.WAKE:
        ustack = e.US
        nb = locate(gh, 1, e.MXGLVL, e.DSBH)
        ubldg = gintrp(gh[nb], e.GRIDWS[nb], gh[nb + 1], e.GRIDWS[nb + 1], e.DSBH)
        e.RURAL = True
        estela_edificio.wake_ini(e, e.KURDAT, e.PRIMEDBG, e.PRMDBUNT, e.RURAL, e.DSBH, e.DSBW, e.DSBL,
                       e.XADJ, e.YADJ, ubldg, ustack)
    if e.OSPLAT[isrc]:
        raise NoTraducido("PLATFORM")
    if e.DEBUG:
        depura.pcalc_efectivos(e)

    from . import nucleo
    if nucleo.activo():
        nucleo.pcalc_bucle(e, aerplm, aerpan)
    else:
        _pcalc_bucle(e, aerplm, aerpan)


def _pcalc_bucle(e, aerplm, aerpan):
    """Bucle de receptores de PCALC (la parte que se compila con numba en nucleo.py)."""
    calculo_area, funciones_dispersion, sigmas, parametros_efectivos, estela_edificio, resultados = _m()
    fran = 0.0
    # CHIN y CHID son locales de PCALC (solo se usan con TTRM en horas convectivas)
    chin = 0.0
    chid = 0.0
    for irec in range(1, e.NUMREC + 1):
        e.IREC = irec
        if e.EVONLY:
            raise NoTraducido("EVENT")
        funciones_dispersion.xydist(e, irec)
        if e.DISTR < 0.99 or e.DISTR > e.MAXDIST:
            e.HRVAL[:] = 0.0
            aerplm[:] = 0.0
            aerpan[:] = 0.0
            e.PRMVAL[:] = 0.0
            if e.PVMRM or e.OLM or e.ARM2 or e.RUNTTRM or e.GRSM:
                if e.GRSM:
                    e.CHI_TTRAVPLM = 0.0
                    e.CHI_TTRAVPAN = 0.0
                    e.CHI_TTRAVAER = 0.0
                    e.CHI_TTRAVPRM = 0.0
                    e.BLDFAC[irec, e.ISRC] = 0.0
                    e.PRMVAL_SRC1 = 0.0
                calculo_area._cero_chi(e, irec, e.ISRC)
            continue
        l_plume = True
        e.XDIST = e.X
        aercalc(e, e.X, l_plume, aerplm)
        if e.GRSM:
            if e.STABLE or (e.UNSTAB and e.HS >= e.ZI):
                e.UCHM = e.UEFF
            else:
                e.UCHM = e.UEFFD
            if e.UCHM != 0:
                e.CHI_TTRAVPLM = max(0.0, aerplm[1] * e.X / e.UCHM)
            else:
                e.errhdl(e.PATH, "PCALC", "E", "601", "GRSM")
                e.RUNERR = True
                return
        if e.L_EFFSIGY:
            e.AERVAL[:] = aerplm
            aerpan[:] = 0.0
            fran = 0.0
            if e.GRSM:
                e.CHI_TTRAVPAN = 0.0
                e.CHI_TTRAVAER = e.CHI_TTRAVPLM
        else:
            l_plume = False
            e.XDIST = e.DISTR
            aercalc(e, e.DISTR, l_plume, aerpan)
            if e.GRSM:
                if e.STABLE or (e.UNSTAB and e.HS >= e.ZI):
                    e.UCHM = e.UEFF
                else:
                    e.UCHM = e.UEFFD
                if e.UCHM != 0:
                    e.CHI_TTRAVPAN = max(0.0, aerpan[1] * e.XDIST / e.UCHM)
                else:
                    e.errhdl(e.PATH, "PCALC", "E", "601", "GRSM")
                    e.RUNERR = True
                    return
            if e.STABLE or (e.UNSTAB and e.HS >= e.ZI):
                fran = funciones_dispersion.meandr(e, e.UEFF, e.SVEFF)
            elif e.UNSTAB:
                fran = funciones_dispersion.meandr(e, e.UEFFD, e.SVEFFD)
                if e.PPF > 0.0:
                    fran3 = funciones_dispersion.meandr(e, e.UEFF3, e.SVEFF3)
                    fran = e.PPF * fran3 + (1.0 - e.PPF) * fran
            if e.RUNTTRM and e.UNSTAB:
                chid = (e.QTK * e.EMIFAC[1] * (1.0 - e.PPF) / e.UEFFD) * (e.FSUBYD * e.FSUBZD)
                chin = (e.QTK * e.EMIFAC[1] * (1.0 - e.PPF) / e.UEFFN) * (e.FSUBYN * e.FSUBZN)
            if e.RUNTTRM:
                o = e.TTRMOUT
                isrc = e.ISRC
                o[irec, isrc, 12] = e.UEFF
                o[irec, isrc, 13] = e.UEFFD
                o[irec, isrc, 14] = e.UEFF3
                o[irec, isrc, 15] = fran
                o[irec, isrc, 16] = e.PPF
                o[irec, isrc, 18] = chin
                o[irec, isrc, 19] = chid
            e.AERVAL[:] = fran * aerpan + (1.0 - fran) * aerplm
            if e.GRSM:
                e.CHI_TTRAVAER = fran * e.CHI_TTRAVPAN + (1.0 - fran) * e.CHI_TTRAVPLM
        if e.DEBUG:
            depura.aerval_comp(e, aerpan, aerplm, fran, e.AERVAL)
        if e.WAKE and (e.STABLE or e.HS <= e.ZI):
            xbrec = e.X - e.XADJ
            ybrec = e.Y - e.YADJ
            e.XDIST = e.X
            prmcalc(e, xbrec, ybrec)
            if e.RUNERR:
                return
            if e.GRSM:
                if e.UEFF != 0:
                    e.CHI_TTRAVPRM = max(0.0, e.PRMVAL[1] * e.XDIST / e.UEFF)
                else:
                    e.errhdl(e.PATH, "PCALC", "E", "601", "GRSM")
                    e.RUNERR = True
                    return
            gamcalc(e, xbrec, ybrec)
            e.HRVAL[:] = e.GAMFACT * e.PRMVAL + (1.0 - e.GAMFACT) * e.AERVAL
            if e.GRSM:
                e.CHI_TTRAVCHM[irec, e.ISRC] = e.GAMFACT * e.CHI_TTRAVPRM + \
                    (1.0 - e.GAMFACT) * e.CHI_TTRAVAER
                if e.HRVAL[1] > 0.0:
                    e.BLDFAC[irec, e.ISRC] = e.GAMFACT * (e.PRMVAL[1] - e.PRMVAL_SRC1) / e.HRVAL[1]
            if e.PRIMEDBG:
                depura.prime_gamfact(e)
        else:
            e.GAMFACT = 0.0
            e.HRVAL[:] = e.AERVAL
            e.PRMVAL[:] = 0.0
            if e.GRSM:
                e.CHI_TTRAVCHM[irec, e.ISRC] = e.CHI_TTRAVAER
        if e.HBPLUME and e.HBPDBG:
            raise NoTraducido("HBPDBG")
        if e.RUNTTRM:
            o = e.TTRMOUT
            isrc = e.ISRC
            o[irec, isrc, 10] = e.X
            o[irec, isrc, 11] = e.DISTR
            o[irec, isrc, 20] = e.Y
            o[irec, isrc, 17] = e.GAMFACT
            o[irec, isrc, 22] = e.AERVAL[1]
            o[irec, isrc, 23] = e.PRMVAL[1]
        if e.PVMRM or e.OLM or e.RUNTTRM or e.ARM2 or e.GRSM:
            calculo_area._guardar_chi(e, irec, e.ISRC)
            e.HRVAL[:] = 0.0
            e.AERVAL[:] = 0.0
            aerplm[:] = 0.0
            aerpan[:] = 0.0
            e.PRMVAL[:] = 0.0
            continue
        for igrp in range(1, e.NUMGRP + 1):
            e.IGRP = igrp
            resultados.sumval(e)
        e.HRVAL[:] = 0.0
        e.AERVAL[:] = 0.0
        aerplm[:] = 0.0
        aerpan[:] = 0.0
        e.PRMVAL[:] = 0.0


# -------------------------------------------------------------------------------- AERCALC
def aercalc(e, xarg, l_plume, aerout):
    """AERCALC: concentración del penacho coherente (L_PLUME) o del meandro (AEROUT en sitio)."""
    calculo_area, funciones_dispersion, sigmas, parametros_efectivos, estela_edificio, resultados = _m()
    nt = e.NUMTYP
    aerout[:] = 0.0
    aertmp = np.zeros(nt + 1)
    fran = 0.0
    if xarg < 1.0:
        aerout[:] = 0.0
        return
    if e.NPD == 0 and (e.LDGAS or e.LWGAS):
        calculo_area.pdepg(e, xarg)
    else:
        e.DQCORG = 1.0
        e.WQCORG = 1.0
    if e.NPD > 0 and (e.LDPART or e.LWPART):
        calculo_area.pdep(e, xarg)
    elif e.NPD > 0:
        e.DQCOR[:] = 1.0
        e.WQCOR[:] = 1.0
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
        e.UEFF3 = e.US
        e.SVEFF3 = e.SVS
        e.SWEFF3 = e.SWS
        e.TGEFF3 = e.TGS
    if e.DEBUG:
        depura.efectivos_ini(e, l_plume)
    calculo_area.centroid(e, xarg)
    sigmas.deltah(e, xarg)
    if e.UNSTAB and e.HS < e.ZI:
        funciones_dispersion.pdf(e)
    calculo_area.heff(e, xarg)
    if e.OSPLAT[e.ISRC] and xarg > 0.0:
        raise NoTraducido("PLATFORM")
    parametros_efectivos.iblval(e, xarg)
    if e.UNSTAB and e.HS < e.ZI:
        funciones_dispersion.pdf(e)
        calculo_area.heff(e, xarg)
    calculo_area.pdis(e, xarg)
    if l_plume:
        if e.L_EFFSIGY:
            if e.STABLE or (e.UNSTAB and e.HS >= e.ZI):
                fran = funciones_dispersion.meandr(e, e.UEFF, e.SVEFF)
            elif e.UNSTAB:
                fran = funciones_dispersion.meandr(e, e.UEFFD, e.SVEFFD)
                if e.PPF > 0.0:
                    fran3 = funciones_dispersion.meandr(e, e.UEFF3, e.SVEFF3)
                    fran = e.PPF * fran3 + (1.0 - e.PPF) * fran
            e.SYEFF = 1.0 / ((fran / (e.SRT2PI * xarg)) + (1.0 - fran) / e.SY)
            if e.L_EFFSIGY:
                if abs(e.Y) > e.NUMSYEFF * e.SYEFF:
                    fyout = 0.0
                else:
                    fyout = funciones_dispersion.fyplm(e, e.SYEFF)
            else:
                if e.X < 1.0 or abs(e.Y) > e.NUMSYEFF * e.SYEFF:
                    fyout = 0.0
                else:
                    fyout = funciones_dispersion.fyplm(e, e.SYEFF)
        else:
            fyout = funciones_dispersion.fyplm(e, e.SY)
    else:
        fyout = funciones_dispersion.fypan(e)
    e.FSUBY = fyout
    e.FSUBYD = e.FSUBY
    e.FSUBYN = e.FSUBYD
    if e.UNSTAB and e.HS < e.ZI and e.PPF > 0.0:
        if l_plume:
            if e.L_EFFSIGY:
                e.SYEFF = 1.0 / ((fran / (e.SRT2PI * xarg)) + (1.0 - fran) / e.SY3)
                if abs(e.Y) > e.NUMSYEFF * e.SYEFF:
                    fyout = 0.0
                else:
                    fyout = funciones_dispersion.fyplm(e, e.SYEFF)
            else:
                fyout = funciones_dispersion.fyplm(e, e.SY3)
        else:
            fyout = funciones_dispersion.fypan(e)
        e.FSUBY3 = fyout
    else:
        e.FSUBY3 = 0.0
    if e.FSUBY == 0.0 and e.FSUBY3 == 0.0:
        aerout[:] = 0.0
        return
    if e.NPD == 0:
        e.HV = 0.0
        adj = e.DQCORG * e.WQCORG
        if e.STABLE or (e.UNSTAB and e.HS >= e.ZI):
            e.HSBL = calculo_area.refl_ht(e, e.HE, xarg, e.SZB, 0.0)
        elif e.UNSTAB:
            e.HSBL = 0.0
        if e.UNSTAB and e.HS < e.ZI and e.PPF > 0.0:
            e.HPEN = calculo_area.refl_ht(e, e.HE3, xarg, e.SZB3, 0.0)
        else:
            e.HPEN = 0.0
        funciones_dispersion.critds(e, e.HE)
        funciones_dispersion.pfract(e, e.HE)
        funciones_dispersion.fterm(e)
        calculo_area.aer_pchi(e, xarg, adj, e.VDEPG, 0, aerout)
    else:
        for j in range(1, e.NPD + 1):
            e.HV = (xarg / e.US) * e.VGRAV[j]
            adj = e.PHI[j] * e.DQCOR[j] * e.WQCOR[j]
            if e.STABLE or (e.UNSTAB and e.HS >= e.ZI):
                e.HESETL = max(0.0, e.HE - e.HV)
                e.HSBL = calculo_area.refl_ht(e, e.HESETL, xarg, e.SZB, 0.0)
            elif e.UNSTAB:
                e.HESETL = max(0.0, 0.5 * (e.HED1 + e.HED2) - e.HV)
                e.HSBL = 0.0
            if e.UNSTAB and e.HS < e.ZI and e.PPF > 0.0:
                e.HE3SETL = max(0.0, e.HE3 - e.HV)
                e.HPEN = calculo_area.refl_ht(e, e.HE3SETL, xarg, e.SZB3, 0.0)
                e.HPEN = max(e.HPEN, e.ZI)
            else:
                e.HPEN = 0.0
            funciones_dispersion.critds(e, e.HESETL)
            funciones_dispersion.pfract(e, e.HESETL)
            funciones_dispersion.fterm(e)
            calculo_area.aer_pchi(e, xarg, adj, e.VDEP[j], j, aertmp)
            aerout[:] = aerout + aertmp


# -------------------------------------------------------------------------------- PRMCALC
def prmcalc(e, xbrec, ybrec):
    """PRMCALC: concentración con el algoritmo PRIME (downwash por edificios)."""
    calculo_area, funciones_dispersion, sigmas, parametros_efectivos, estela_edificio, resultados = _m()
    p = e.P
    e.PRMVAL[:] = 0.0
    if e.GRSM:
        e.PRMVAL_SRC1 = 0.0
    e.P.UEFF_SAVE = 0.0
    e.P.SWEFF_SAVE = 0.0
    e.P.SVEFF_SAVE = 0.0
    ipositn = estela_edificio.position(e, xbrec, ybrec, e.ZFLAG)
    if ipositn == 4 and e.X <= 0.0:
        e.PRMVAL[:] = e.AERVAL
        if e.GRSM:
            e.PRMVAL_SRC1 = e.AERVAL[1]
        return
    elif ipositn != 2 and e.DISTR < 0.99:
        e.PRMVAL[:] = e.AERVAL
        if e.GRSM:
            e.PRMVAL_SRC1 = e.AERVAL[1]
        return
    elif not e.WAKE:
        e.PRMVAL[:] = e.AERVAL
        if e.GRSM:
            e.PRMVAL_SRC1 = e.AERVAL[1]
        return
    zhi = 1.2 * e.RSCALE * (15.0 + (e.DSBH / (1.2 * e.RSCALE)) ** 3) ** e.THIRD
    if e.UNSTAB:
        zhi = min(zhi, e.ZI)
    zlo = 0.0
    if e.L_AWMA_UTURB or e.L_AWMA_UTURBHX:
        raise NoTraducido("AWMAUTURB")
    gh = e.GRIDHT
    mx = e.MXGLVL
    ndxbhi = locate(gh, 1, mx, zhi)
    ndxblo = locate(gh, 1, mx, zlo)
    ndxalo = ndxblo + 1
    e.UEFF, zlo, ndxalo, zhi, ndxbhi = anyavg(mx, gh, e.GRIDWS, zlo, ndxalo, zhi, ndxbhi)
    e.SVEFF, zlo, ndxalo, zhi, ndxbhi = anyavg(mx, gh, e.GRIDSV, zlo, ndxalo, zhi, ndxbhi)
    e.SWEFF, zlo, ndxalo, zhi, ndxbhi = anyavg(mx, gh, e.GRIDSW, zlo, ndxalo, zhi, ndxbhi)
    e.TGEFF, zlo, ndxalo, zhi, ndxbhi = anyavg(mx, gh, e.GRIDTG, zlo, ndxalo, zhi, ndxbhi)
    e.SWEFF = max(e.SWEFF, e.SWMIN)
    e.SVEFF = max(e.SVEFF, e.SVMIN, e.SVUMIN * e.UEFF)
    if e.L_VECTORWS:
        e.UEFF = math.sqrt(e.UEFF * e.UEFF + 2.0 * e.SVEFF * e.SVEFF)
    e.UEFF = max(e.UEFF, e.WSMIN)
    if e.PRIMEDBG:
        depura.prmcalc_efectivos(e, zlo, zhi)
    l_inwake = e.PRMC_LINW
    l_inwake = sigmas.prmdelh(e, e.X, l_inwake)
    e.PRMC_LINW = l_inwake
    if e.RUNERR:
        return
    if not l_inwake:
        e.PRMVAL[:] = e.AERVAL
        if e.GRSM:
            e.PRMVAL_SRC1 = e.AERVAL[1]
        return
    calculo_area.prmheff(e)
    if e.UNSTAB and e.HE >= e.ZI:
        e.PRMVAL[:] = e.AERVAL
        if e.GRSM:
            e.PRMVAL_SRC1 = e.AERVAL[1]
        return
    dhpout = e.DHP
    szout, syout, szcav, sycav = estela_edificio.wake_xsig(e, e.X, e.HS, dhpout, e.NOBID)
    e.SY = syout
    e.SZ = szout
    qtksav = e.QTK
    ppfsav = e.PPF
    q2 = [0.0, e.QTK, 0.0, 0.0]
    y2 = [0.0, e.Y, 0.0, 0.0]
    sy2 = [0.0, e.SY, 0.0, 0.0]
    z2 = [0.0, e.ZFLAG, 0.0, 0.0]
    h2 = [0.0, e.HE, 0.0, 0.0]
    sz2 = [0.0, e.SZ, 0.0, 0.0]
    qc2 = [0.0, 0.0, 0.0, 0.0]
    n1 = 1
    n2 = 1
    if e.WAKE:
        fqcav, n1, n2 = estela_edificio.cav_src(e, e.X, e.Y, e.ZFLAG, qc2, h2, y2, z2, sz2, sy2)
        if e.SCREEN:
            y2[:] = [0.0] * 4
        if fqcav > 0.0:
            q2[1] = e.QTK * (1.0 - fqcav)
            q2[2] = e.QTK * fqcav * qc2[2]
            q2[3] = e.QTK * fqcav * qc2[3]
    e.PRMVAL[:] = 0.0
    if e.GRSM:
        e.PRMVAL_SRC1 = 0.0
    for is_ in range(n1, n2 + 1):
        if q2[is_] == 0.0:
            continue
        e.QTK = q2[is_]
        e.Y = y2[is_]
        e.SY = sy2[is_]
        e.SZ = sz2[is_]
        e.HE = h2[is_]
        e.ZFLAG = z2[is_]
        fyout = funciones_dispersion.fyplm(e, e.SY)
        e.FSUBY = fyout
        if e.FSUBY == 0.0:
            e.PRMVAL[:] = 0.0
            if e.GRSM:
                e.PRMVAL_SRC1 = 0.0
        else:
            e.FOPT = 0.5
            if e.NPD == 0:
                if (e.LDGAS or e.LWGAS) and is_ != 3 and e.X > 1.0:
                    # (sin agotamiento para la fuente dentro de la cavidad, IS = 3)
                    prm_pdepg(e, e.X)
                    # altura y sigmas del penacho, que la integración puede haber cambiado
                    e.SY = sy2[is_]
                    e.SZ = sz2[is_]
                    e.HE = h2[is_]
                else:
                    e.DQCORG = 1.0
                    e.WQCORG = 1.0
                adj = e.DQCORG * e.WQCORG
                prm_pchi(e, adj, e.VDEPG, 0, is_)
            else:
                if (e.LDPART or e.LWPART) and is_ != 3 and e.X > 1.0:
                    prm_pdep(e, e.X)
                    e.SY = sy2[is_]
                    e.SZ = sz2[is_]
                    e.HE = h2[is_]
                else:
                    e.DQCOR[:] = 1.0
                    e.WQCOR[:] = 1.0
                for j in range(1, e.NPD + 1):
                    adj = e.PHI[j] * e.DQCOR[j] * e.WQCOR[j]
                    e.HV = (e.X / e.US) * e.VGRAV[j]
                    # (la altura se va reduciendo de una categoría a la siguiente, como en el original)
                    e.HE = max(0.0, e.HE - e.HV)
                    prm_pchi(e, adj, e.VDEP[j], j, is_)
            if e.GRSM and is_ == 1:
                e.PRMVAL_SRC1 = e.PRMVAL[1]
    e.QTK = qtksav
    e.PPF = ppfsav
    e.Y = y2[1]
    e.SY = sy2[1]
    e.SZ = sz2[1]
    e.HE = h2[1]
    e.ZFLAG = z2[1]


def prm_pdep(e, xarg):
    """PRM_PDEP: factores de agotamiento de las partículas para el penacho de PRIME."""
    calculo_area = _m()[0]
    for i in range(1, e.NPD + 1):
        e.DQCOR[i] = 1.0
        e.WQCOR[i] = 1.0
        if e.DDPLETE:
            e.VSETL = e.VGRAV[i]
            e.DQCOR[i] = calculo_area.deplete(e, e.VDEP[i], xarg, e.ROMBERG, 2)
        if e.WDPLETE and e.PSCVRT[i] > 0.0:
            e.WQCOR[i] = math.exp(-e.PSCVRT[i] * xarg / e.US)


def prm_pdepg(e, xarg):
    """PRM_PDEPG: factores de agotamiento de los gases para el penacho de PRIME."""
    calculo_area = _m()[0]
    e.DQCORG = 1.0
    e.WQCORG = 1.0
    if e.DDPLETE:
        e.DQCORG = calculo_area.deplete(e, e.VDEPG, xarg, e.ROMBERG, 2)
    if e.WDPLETE and e.GSCVRT > 0.0:
        e.WQCORG = math.exp(-e.GSCVRT * xarg / e.US)


def prm_f2int(e, xi):
    """PRM_F2INT: integrando de PRM_DEPLETE (penacho de PRIME) a la distancia XI: sobreelevación y
    sigmas de la estela a esa distancia, inclinación por sedimentación y término vertical a la
    altura de referencia de la deposición (FOPT = 0,5)."""
    calculo_area, funciones_dispersion, sigmas, parametros_efectivos, estela_edificio, resultados = _m()
    zetmp = e.ZELEV
    e.ZELEV = e.ZS + (zetmp - e.ZS) * xi / e.X
    zhtmp = e.ZHILL
    e.ZHILL = e.HS + (zhtmp - e.HS) * xi / e.X
    # (L_INWAKE es una variable local sin valor inicial: PRMDELH no la lee tras el primer receptor)
    l_inwake = sigmas.prmdelh(e, xi, False)
    calculo_area.prmheff(e)
    dhpout = e.DHP
    szout, syout, szcav, sycav = estela_edificio.wake_xsig(e, xi, e.HS, dhpout, e.NOBID)
    e.SY = syout
    e.SZ = szout
    e.HV = (xi / e.US) * e.VSETL
    e.HE = max(0.0, e.HE - e.HV)
    e.FOPT = 0.5
    e.ZR = e.ZRT + e.ZRDEP
    if e.STABLE:
        funciones_dispersion.vrtsbn(e, e.SZ, e.HE)
    elif e.UNSTAB and e.HE <= e.ZI:
        funciones_dispersion.vrtsbl(e, e.SZ, e.HE, e.ZI)
    else:
        e.FSUBZ = 0.0
    vwrap = e.FSUBZ / e.UEFF
    if e.ZRT == 0.0:
        vlift = vwrap
    elif e.FOPT == 1.0:
        vlift = 0.0
    else:
        e.ZR = e.ZRDEP
        if e.STABLE:
            funciones_dispersion.vrtsbn(e, e.SZ, e.HE)
        elif e.UNSTAB and e.HE <= e.ZI:
            funciones_dispersion.vrtsbl(e, e.SZ, e.HE, e.ZI)
        else:
            e.FSUBZ = 0.0
        vlift = e.FSUBZ / e.UEFF
    res = e.FOPT * vwrap + (1.0 - e.FOPT) * vlift
    e.ZELEV = zetmp
    e.ZHILL = zhtmp
    return res


def gamcalc(e, xarg, yarg):
    """GAMCALC: factor de mezcla GAMFACT entre PRIME y AERMOD."""
    from . import estela_edificio
    if xarg <= 0.0 or not e.WAKE:
        e.GAMFACT = 0.0
        return
    rs = e.RSCALE
    wake_hgt = 1.2 * rs * (xarg / rs + (e.DSBH / (1.2 * rs)) ** 3) ** e.THIRD
    wake_wid = 0.5 * e.DSBW + (rs / 3.0) * (xarg / rs) ** e.THIRD
    xaz, xay = estela_edificio.wake_xa2(e, e.DSBL, rs)
    xamx = max(xaz, xay)
    wake_len = max(15.0 * rs, xamx)
    sigma_xg = wake_len
    sigma_yg = wake_wid
    sigma_zg = wake_hgt
    if xarg <= sigma_xg:
        exparg_xg = 0.0
    else:
        exparg_xg = -((xarg - sigma_xg) * (xarg - sigma_xg) / (2.0 * (sigma_xg * sigma_xg)))
    if abs(yarg) <= sigma_yg:
        exparg_yg = 0.0
    else:
        exparg_yg = -((abs(yarg) - sigma_yg) * (abs(yarg) - sigma_yg) /
                      (2.0 * (sigma_yg * sigma_yg)))
    if e.ZRT <= sigma_zg:
        exparg_zg = 0.0
    else:
        exparg_zg = -((e.ZRT - sigma_zg) * (e.ZRT - sigma_zg) / (2.0 * (sigma_zg * sigma_zg)))
    if exparg_xg > e.EXPLIM and exparg_yg > e.EXPLIM and exparg_zg > e.EXPLIM:
        e.GAMFACT = math.exp(exparg_xg) * math.exp(exparg_yg) * math.exp(exparg_zg)
    else:
        e.GAMFACT = 0.0


def prm_pchi(e, adj, vdinp, jin, insrc):
    """PRM_PCHI: concentración/depósito del penacho de PRIME (acumula en PRMVAL)."""
    calculo_area, funciones_dispersion, sigmas, parametros_efectivos, estela_edificio, resultados = _m()
    dryflux = 0.0
    wetflux = 0.0
    funciones_dispersion.decay(e, e.X)
    if e.L_ORD_UEFF or e.L_AWMA_UEFF:
        raise NoTraducido("ORD_UEFF / AWMAUEFF")
    ueffe = e.US
    if e.RUNTTRM:
        e.TTRMOUT[e.IREC, e.ISRC, 24] = ueffe
    ityp = 0
    if e.CONC:
        ityp = 1
        if e.FOPT == 0.0:
            e.CWRAP = 0.0
        else:
            e.CWRAP = calculo_area.prm_plume(e, e.ZRT, ueffe)
        if e.ZRT == e.ZFLAG:
            e.CLIFT = e.CWRAP
        elif e.FOPT == 1.0:
            e.CLIFT = 0.0
        else:
            e.CLIFT = calculo_area.prm_plume(e, e.ZFLAG, ueffe)
        e.PRMVAL[ityp] = e.PRMVAL[ityp] + adj * e.EMIFAC[ityp] * \
            (e.FOPT * e.CWRAP + (1.0 - e.FOPT) * e.CLIFT) * e.D
    if e.DEPOS or e.DDEP:
        if e.FOPT == 0.0:
            e.CWRAP = 0.0
        else:
            e.CWRAP = calculo_area.prm_plume(e, e.ZRT - e.ZFLAG + e.ZRDEP, ueffe)
        if e.ZRT == e.ZFLAG:
            e.CLIFT = e.CWRAP
        elif e.FOPT == 1.0:
            e.CLIFT = 0.0
        else:
            e.CLIFT = calculo_area.prm_plume(e, e.ZRDEP, ueffe)
        dryflux = (e.FOPT * e.CWRAP + (1.0 - e.FOPT) * e.CLIFT) * e.D
    if e.DEPOS or e.WDEP:
        wetflux = calculo_area._humedo(e, adj, jin)
    if e.DEPOS:
        ityp += 1
        e.PRMVAL[ityp] = e.PRMVAL[ityp] + adj * vdinp * e.EMIFAC[ityp] * dryflux + \
            e.QTK * wetflux * e.EMIFAC[ityp] * e.FSUBY / e.UEFF
    if e.DDEP:
        ityp += 1
        e.PRMVAL[ityp] = e.PRMVAL[ityp] + adj * vdinp * e.EMIFAC[ityp] * dryflux
    if e.WDEP:
        ityp += 1
        e.PRMVAL[ityp] = e.PRMVAL[ityp] + e.QTK * wetflux * e.EMIFAC[ityp] * e.FSUBY / e.UEFF
    e.ITYP = ityp
    if e.DEBUG:
        calculo_area.debout(e)


# --------------------------------------------------------------------------------- VCALC
def vcalc(e):
    """VCALC: cálculo para una fuente de volumen."""
    calculo_area, funciones_dispersion, sigmas, parametros_efectivos, estela_edificio, resultados = _m()
    isrc = e.ISRC
    nt = e.NUMTYP
    e.WAKE = False
    e.HRVAL[:] = 0.0
    e.AERVAL[:] = 0.0
    aerplm = np.zeros(nt + 1)
    aerpan = np.zeros(nt + 1)
    e.PRMVAL[:] = 0.0
    fran = 0.0
    if e.allocated("CHI"):
        e.CHI[:, isrc, :] = 0.0
    if e.GRSM:
        e.CHI_TTRAVPLM = 0.0
        e.CHI_TTRAVPAN = 0.0
        e.CHI_TTRAVAER = 0.0
        e.CHI_TTRAVCHM[:, isrc] = 0.0
    calculo_area.setsrc(e)
    funciones_dispersion.emfact(e, e.QS)
    if e.EVAL[isrc]:
        raise NoTraducido("EVALFILE")
    if e.QTK == 0.0:
        return
    calculo_area._met_urbana(e)
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
    e.XRAD = 2.15 * e.SYINIT
    if e.UNSTAB and e.HS < e.ZI:
        funciones_dispersion.pdf(e)
    calculo_area.deposicion_fuente(e, False)
    from . import nucleo
    if nucleo.activo():
        nucleo.vcalc_bucle(e, aerplm, aerpan)
    else:
        _vcalc_bucle(e, aerplm, aerpan)


def _vcalc_bucle(e, aerplm, aerpan):
    """Bucle de receptores de VCALC (la parte que se compila con numba en nucleo.py)."""
    calculo_area, funciones_dispersion, sigmas, parametros_efectivos, estela_edificio, resultados = _m()
    fran = 0.0
    for irec in range(1, e.NUMREC + 1):
        e.IREC = irec
        if e.EVONLY:
            raise NoTraducido("EVENT")
        funciones_dispersion.xydist(e, irec)
        if e.DISTR < (e.XRAD + 0.99) or (e.DISTR > e.MAXDIST):
            e.HRVAL[:] = 0.0
            aerplm[:] = 0.0
            aerpan[:] = 0.0
            if e.PVMRM or e.OLM or e.ARM2 or e.RUNTTRM or e.GRSM:
                if e.GRSM:
                    e.CHI_TTRAVPLM = 0.0
                    e.CHI_TTRAVPAN = 0.0
                    e.CHI_TTRAVAER = 0.0
                calculo_area._cero_chi(e, irec, e.ISRC)
            continue
        l_plume = True
        e.XDIST = e.X
        if e.X < 1.0:
            aerplm[:] = 0.0
            if e.GRSM:
                e.CHI_TTRAVPLM = 0.0
        else:
            volcalc(e, e.X, l_plume, aerplm)
            if e.GRSM:
                if e.STABLE or (e.UNSTAB and e.HS >= e.ZI):
                    e.UCHM = e.UEFF
                else:
                    e.UCHM = e.UEFFD
                if e.UCHM != 0:
                    e.CHI_TTRAVPLM = max(0.0, aerplm[1] * e.X / e.UCHM)
                else:
                    e.errhdl(e.PATH, "VCALC", "E", "601", "GRSM")
                    e.RUNERR = True
                    return
        if e.L_EFFSIGY:
            e.HRVAL[:] = aerplm
            aerpan[:] = 0.0
            fran = 0.0
            if e.GRSM:
                e.CHI_TTRAVPAN = 0.0
        else:
            l_plume = False
            e.XDIST = e.DISTR
            volcalc(e, e.DISTR, l_plume, aerpan)
            if e.GRSM:
                if e.STABLE or (e.UNSTAB and e.HS >= e.ZI):
                    e.UCHM = e.UEFF
                else:
                    e.UCHM = e.UEFFD
                if e.UCHM != 0:
                    e.CHI_TTRAVPAN = max(0.0, aerpan[1] * e.XDIST / e.UCHM)
                else:
                    e.errhdl(e.PATH, "VCALC", "E", "601", "GRSM")
                    e.RUNERR = True
                    return
            if e.STABLE or (e.UNSTAB and e.HS >= e.ZI):
                fran = funciones_dispersion.meandr(e, e.UEFF, e.SVEFF)
            elif e.UNSTAB:
                fran = funciones_dispersion.meandr(e, e.UEFFD, e.SVEFFD)
            e.HRVAL[:] = fran * aerpan + (1.0 - fran) * aerplm
            if e.GRSM:
                e.CHI_TTRAVCHM[irec, e.ISRC] = fran * e.CHI_TTRAVPAN + (1.0 - fran) * e.CHI_TTRAVPLM
        if e.DEBUG:
            depura.aerval_comp(e, aerpan, aerplm, fran, e.HRVAL, "HRVAL")
        if e.RUNTTRM:
            o = e.TTRMOUT
            isrc = e.ISRC
            o[irec, isrc, 12] = e.UEFF
            o[irec, isrc, 13] = e.UEFFD
            o[irec, isrc, 15] = fran
            o[irec, isrc, 10] = e.X
            o[irec, isrc, 11] = e.DISTR
            o[irec, isrc, 20] = e.Y
        if e.PVMRM or e.OLM or e.RUNTTRM or e.ARM2 or e.GRSM:
            calculo_area._guardar_chi(e, irec, e.ISRC)
            e.HRVAL[:] = 0.0
            e.AERVAL[:] = 0.0
            aerplm[:] = 0.0
            aerpan[:] = 0.0
            e.PRMVAL[:] = 0.0
            continue
        for igrp in range(1, e.NUMGRP + 1):
            e.IGRP = igrp
            resultados.sumval(e)


def volcalc(e, xarg, l_plume, aerout):
    """VOLCALC: concentración del penacho coherente o del meandro de una fuente de volumen."""
    calculo_area, funciones_dispersion, sigmas, parametros_efectivos, estela_edificio, resultados = _m()
    nt = e.NUMTYP
    fran = 0.0
    aerout[:] = 0.0
    aertmp = np.zeros(nt + 1)
    if e.NPD == 0 and (e.LDGAS or e.LWGAS):
        calculo_area.pdepg(e, xarg)
    else:
        e.DQCORG = 1.0
        e.WQCORG = 1.0
    if e.NPD > 0 and (e.LDPART or e.LWPART):
        calculo_area.pdep(e, xarg)
    elif e.NPD > 0:
        e.DQCOR[:] = 1.0
        e.WQCOR[:] = 1.0
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
    if e.DEBUG:
        depura.efectivos_ini(e, l_plume)
    calculo_area.centroid(e, xarg)
    if e.UNSTAB and e.HS < e.ZI:
        funciones_dispersion.pdf(e)
    calculo_area.heff(e, xarg)
    parametros_efectivos.iblval(e, xarg)
    if e.UNSTAB and e.HS < e.ZI:
        funciones_dispersion.pdf(e)
        calculo_area.heff(e, xarg)
    calculo_area.vdis(e, xarg)
    if l_plume:
        if e.L_EFFSIGY:
            if e.STABLE or (e.UNSTAB and e.HS >= e.ZI):
                fran = funciones_dispersion.meandr(e, e.UEFF, e.SVEFF)
            elif e.UNSTAB:
                fran = funciones_dispersion.meandr(e, e.UEFFD, e.SVEFFD)
            e.SYEFF = 1.0 / ((fran / (e.SRT2PI * xarg)) + (1.0 - fran) / e.SY)
            if abs(e.Y) > e.NUMSYEFF * e.SYEFF:
                fyout = 0.0
            else:
                fyout = funciones_dispersion.fyplm(e, e.SYEFF)
        else:
            fyout = funciones_dispersion.fyplm(e, e.SY)
    else:
        fyout = funciones_dispersion.fypan(e)
    e.FSUBY = fyout
    e.FSUBYD = e.FSUBY
    e.FSUBYN = e.FSUBYD
    e.FSUBY3 = 0.0
    if e.FSUBY == 0.0 and e.FSUBY3 == 0.0:
        aerout[:] = 0.0
        return
    if e.NPD == 0:
        adj = e.DQCORG * e.WQCORG
        if e.STABLE or (e.UNSTAB and e.HS >= e.ZI):
            e.HSBL = calculo_area.refl_ht(e, e.HE, xarg, 0.0, e.VSIGZ)
        elif e.UNSTAB:
            e.HSBL = 0.0
        funciones_dispersion.critds(e, e.HE)
        funciones_dispersion.pfract(e, e.HE)
        funciones_dispersion.fterm(e)
        calculo_area.aer_pchi(e, xarg, adj, e.VDEPG, 0, aerout)
    else:
        for j in range(1, e.NPD + 1):
            e.HV = (xarg / e.US) * e.VGRAV[j]
            adj = e.PHI[j] * e.DQCOR[j] * e.WQCOR[j]
            if e.STABLE or (e.UNSTAB and e.HS >= e.ZI):
                e.HESETL = max(0.0, e.HE - e.HV)
                e.HSBL = calculo_area.refl_ht(e, e.HESETL, xarg, 0.0, e.VSIGZ)
            elif e.UNSTAB:
                e.HESETL = max(0.0, 0.5 * (e.HED1 + e.HED2) - e.HV)
                e.HSBL = 0.0
            funciones_dispersion.critds(e, e.HESETL)
            funciones_dispersion.pfract(e, e.HESETL)
            funciones_dispersion.fterm(e)
            calculo_area.aer_pchi(e, xarg, adj, e.VDEP[j], j, aertmp)
            aerout[:] = aerout + aertmp
