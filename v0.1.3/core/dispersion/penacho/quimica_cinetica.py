# -*- coding: utf-8 -*-
"""Traducción de AERMOD 26135 (US EPA, dominio público): esquema químico GRS para el NO2
(grsm.f: GRSM_CALC, RXNRATES, GETBGDEQUIL, QuadraticEquil, FindInitDt, DConcsDt, DoGRSMChem,
AdaptiveRK, CashKarpRK y PLUMESIZES).

Las variables del módulo GRSMMOD (velocidades de reacción, fondo en equilibrio, concentraciones
de trabajo y el indicador de hora nocturna) viven como atributos del estado con el mismo nombre.
Las concentraciones de la química van en ppb; CHI, el fondo y los resultados, en µg/m3."""
import math

import numpy as np

from .estado import NoTraducido

_NNO, _NNO2, _NO3 = 1, 2, 3
_CFRAC = 1.0e-2
_MINIMUMCONC = 1.0e-21
_F01 = float(np.float32(0.1))

# coeficientes de Cash-Karp (PARAMETER del original, calculados en doble precisión)
_B21 = 0.2
_B31, _B32 = 3.0 / 40.0, 9.0 / 40.0
_B41, _B42, _B43 = 0.3, -0.9, 1.2
_B51, _B52, _B53, _B54 = -11.0 / 54.0, 2.5, -70.0 / 27.0, 35.0 / 27.0
_B61, _B62, _B63 = 1631.0 / 55296.0, 175.0 / 512.0, 575.0 / 13824.0
_B64, _B65 = 44275.0 / 110592.0, 253.0 / 4096.0
_C1, _C3, _C4, _C6 = 37.0 / 378.0, 250.0 / 621.0, 125.0 / 594.0, 512.0 / 1771.0
_DC1 = _C1 - 2825.0 / 27648.0
_DC3 = _C3 - 18575.0 / 48384.0
_DC4 = _C4 - 13525.0 / 55296.0
_DC5 = -277.0 / 14336.0
_DC6 = _C6 - 0.25


def _div(a, b):
    """División IEEE (±Inf o NaN al dividir por cero)."""
    if b == 0.0:
        if a == 0.0 or a != a:
            return math.nan
        return math.copysign(math.inf, a) * math.copysign(1.0, b)
    return a / b


def _sqrt(x):
    return math.sqrt(x) if x >= 0.0 else math.nan


def _pow(x, y):
    """x**y IEEE para x >= 0 (0**y negativo = +Inf)."""
    if x == 0.0 and y < 0.0:
        return math.inf
    return x ** y


# ------------------------------------------------------------------------------- RXNRATES
def rxnrates(e):
    """RXNRATES: velocidades de NO + O3 -> NO2 (R1) y NO2 + hv -> NO + O3 (R2)."""
    from .perfiles import gintrp, locate
    scrnht = 1.2
    if e.TREFHT == scrnht:
        chemtk = e.TA
    else:
        gh = e.GRIDHT
        n = locate(gh, 1, e.MXGLVL, scrnht)
        chempt = gintrp(gh[n], e.GRIDPT[n], gh[n + 1], e.GRIDPT[n + 1], scrnht)
        chemtk = chempt - e.GOVRCP * (scrnht + e.ZBASE)
    e.R1 = 4.405e-2 * math.exp(-1.370e3 / chemtk)
    e.R1 = max(e.R1, 1.0e-6)
    if e.QSW == 0:
        e.R2 = 0.0
    else:
        e.R2 = 8.0e-4 * math.exp(-10.0 / e.QSW) + 7.4e-6 * e.QSW


def quadratic_equil(e, no2, no, o3):
    """QuadraticEquil: equilibrio fotoestacionario conservando NOx y NO2 + O3."""
    nox = no2 + no
    no2plus_o3 = no2 + o3
    b = -(nox + no2plus_o3 + (e.R2 / e.R1))
    c = nox * no2plus_o3
    no2 = 0.5 * (-b - _sqrt(b * b - 4.0 * c))
    no = nox - no2
    o3 = no2plus_o3 - no2
    return no2, no, o3


def getbgdequil(e):
    """GETBGDEQUIL: fondo de NO2, NO y O3 en equilibrio."""
    if not e.L_NIGHTHOUR:
        if e.L_CALCNOXFROMNO2 or e.NOXMISS:
            if e.O3CONC_BG != 0.0:
                e.NOXCONC_BG = e.NO2CONC_BG / (e.O3CONC_BG) * (e.O3CONC_BG + e.R2 / e.R1)
                e.NOCONC_BG = e.NOXCONC_BG - e.NO2CONC_BG
        else:
            if e.NOXCONC_BG < e.NO2CONC_BG:
                e.errhdl(e.PATH, "GETBGDEQUIL", "W", "613", "GRSM")
                e.NOXCONC_BG = e.NO2CONC_BG
            e.NOCONC_BG = e.NOXCONC_BG - e.NO2CONC_BG
            e.NO2CONC_BG, e.NOCONC_BG, e.O3CONC_BG = quadratic_equil(e, e.NO2CONC_BG, e.NOCONC_BG,
                                                                     e.O3CONC_BG)
    else:
        if e.L_CALCNOXFROMNO2 or e.NOXMISS:
            e.NOXCONC_BG = -999.0
            e.NOCONC_BG = 0.0
        else:
            e.NOCONC_BG = e.NOXCONC_BG - e.NO2CONC_BG


# ------------------------------------------------------------------------------- química
def _dconcsdt(e, c):
    """DConcsDt: derivadas temporales de NO, NO2 y O3."""
    d = [0.0, 0.0, 0.0, 0.0]
    d[_NNO2] = e.R1 * c[_NNO] * c[_NO3] - e.R2 * c[_NNO2]
    d[_NNO] = e.R2 * c[_NNO2] - e.R1 * c[_NNO] * c[_NO3]
    d[_NO3] = e.R2 * c[_NNO2] - e.R1 * c[_NNO] * c[_NO3]
    return d


def _find_init_dt(e, c):
    """FindInitDt: paso inicial (que ninguna concentración cambie más de CFrac)."""
    d = _dconcsdt(e, c)
    ts = 1.0
    for i in range(1, 4):
        if c[i] > 0.0:
            if abs(d[i]) > _CFRAC * c[i]:
                tl = _CFRAC * abs(c[i] / d[i])
                if tl < ts:
                    ts = tl
    return ts


def _cash_karp(e, c, d, dt):
    """CashKarpRK: un paso de Runge-Kutta de Cash-Karp con su error."""
    ct = [0.0] * 4
    for i in range(1, 4):
        ct[i] = c[i] + _B21 * dt * d[i]
        if ct[i] < 0.0:
            ct[i] = 0.0
    ak2 = _dconcsdt(e, ct)
    for i in range(1, 4):
        ct[i] = c[i] + dt * (_B31 * d[i] + _B32 * ak2[i])
        if ct[i] < 0.0:
            ct[i] = 0.0
    ak3 = _dconcsdt(e, ct)
    for i in range(1, 4):
        ct[i] = c[i] + dt * (_B41 * d[i] + _B42 * ak2[i] + _B43 * ak3[i])
        if ct[i] < 0.0:
            ct[i] = 0.0
    ak4 = _dconcsdt(e, ct)
    for i in range(1, 4):
        ct[i] = c[i] + dt * (_B51 * d[i] + _B52 * ak2[i] + _B53 * ak3[i] + _B54 * ak4[i])
        if ct[i] < 0.0:
            ct[i] = 0.0
    ak5 = _dconcsdt(e, ct)
    for i in range(1, 4):
        ct[i] = c[i] + dt * (_B61 * d[i] + _B62 * ak2[i] + _B63 * ak3[i] + _B64 * ak4[i] +
                             _B65 * ak5[i])
        if ct[i] < 0.0:
            ct[i] = 0.0
    ak6 = _dconcsdt(e, ct)
    cout = [0.0] * 4
    cerr = [0.0] * 4
    for i in range(1, 4):
        cout[i] = c[i] + dt * (_C1 * d[i] + _C3 * ak3[i] + _C4 * ak4[i] + _C6 * ak6[i])
    for i in range(1, 4):
        cerr[i] = dt * (_DC1 * d[i] + _DC3 * ak3[i] + _DC4 * ak4[i] + _DC5 * ak5[i] + _DC6 * ak6[i])
    return cout, cerr


def _adaptive_rk(e, c, d, tlocal, dttry, cscal):
    """AdaptiveRK: paso de Runge-Kutta reduciendo dt hasta que el error sea aceptable. Actualiza
    C y devuelve (tLocal, dtnext)."""
    safety, p_shrink, p_grow, maxgrow = 0.9, -0.25, -0.2, 5.0
    dt = dttry
    while True:
        ctemp, cerr = _cash_karp(e, c, d, dt)
        errmax = 0.0
        for i in range(1, 4):
            if cscal[i] > _MINIMUMCONC:
                errmax = max(errmax, abs(cerr[i] / cscal[i]))
        errmax = errmax / _CFRAC
        if errmax > 1.0:
            ttemp = safety * dt * _pow(errmax, p_shrink)
            dt = max(ttemp, _F01 * dt)
            continue
        growth = safety * _pow(errmax, p_grow)
        if growth > maxgrow:
            dtnext = maxgrow * dt
        else:
            dtnext = growth * dt
        tlocal = tlocal + dt
        for i in range(1, 4):
            c[i] = ctemp[i]
        return tlocal, dtnext


def _do_grsm_chem(e, c, ttrav):
    """DoGRSMChem: integra la química durante el tiempo de viaje TTRAV (modifica C)."""
    maxstp, dtmin = 1000000, 1.0e-6
    tlocal = 0.0
    for i in range(1, 4):
        if c[i] < _MINIMUMCONC:
            c[i] = 0.0
    dt = _find_init_dt(e, c)
    for _n in range(maxstp):
        d = _dconcsdt(e, c)
        for i in range(1, 4):
            if c[i] < _MINIMUMCONC and d[i] < 0.0:
                c[i] = 0.0
                d[i] = 0.0
        cscal = [0.0] * 4
        for i in range(1, 4):
            cscal[i] = c[i] + abs(dt * d[i])
        if tlocal + dt > ttrav:
            dt = ttrav - tlocal
        tlocal, dtnext = _adaptive_rk(e, c, d, tlocal, dt, cscal)
        for i in range(1, 4):
            if c[i] < 0.0:
                c[i] = 0.0
        if tlocal >= ttrav:
            return
        if dtnext < dtmin:
            dtnext = dtmin
        dt = dtnext


# ------------------------------------------------------------------------------ PLUMESIZES
def plumesizes(e, xarg):
    """PLUMESIZES: tamaño (sigma-y * sigma-z) del penacho instantáneo y del promediado (con
    serpenteo) de la fuente ISRC a la distancia XARG. Devuelve (SIGYSIGZ_I, SIGYSIGZ_E)."""
    from . import calculo_area, funciones_dispersion, parametros_efectivos, sigmas
    from .perfiles import gintrp, locate
    m = "PLUMESIZES"
    a0 = 0.2
    isrc, irec = e.ISRC, e.IREC
    calculo_area._met_urbana(e)
    calculo_area.setsrc(e)
    parametros_efectivos.metini(e)
    t = e.SRCTYP[isrc]
    aft = e.AFTSRC[isrc]
    if (t == "VOLUME" and aft == "N") or t == "LINE" or (t[:4] == "AREA" and aft == "N") or \
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
    elif (t == "VOLUME" or t[:4] == "AREA") and aft == "Y":
        raise NoTraducido("AIRCRAFT")
    elif t[:5] == "POINT":
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
    calculo_area.centroid(e, xarg)
    if t[:5] == "POINT":
        sigmas.deltah(e, xarg)
    else:
        e.DHP = 0.0
        e.DHP1 = 0.0
        e.DHP2 = 0.0
        e.DHP3 = 0.0
    if e.UNSTAB and e.HS < e.ZI:
        funciones_dispersion.pdf(e)
    calculo_area.heff(e, xarg)
    parametros_efectivos.iblval(e, xarg)
    if e.UNSTAB and e.HS < e.ZI:
        funciones_dispersion.pdf(e)
        calculo_area.heff(e, xarg)
    estable = e.STABLE or (e.UNSTAB and e.HS >= e.ZI)
    puntual = t in ("POINT", "POINTHOR", "POINTCAP")
    area = t in ("LINE", "BUOYLINE", "AREA", "AREAPOLY", "AREACIRC", "OPENPIT")
    sigy_nt = 0.0
    if puntual:
        calculo_area.pdis(e, 0.0)
        sigy_nt = math.sqrt(e.SY ** 2.0 + (e.DS / 2.0) ** 2.0)
    elif area:
        calculo_area.adisy(e, 0.0)
        calculo_area.adisz(e, 0.0)
        sigy_nt = math.sqrt(e.SY ** 2.0 + (e.YINIT / 2.0) ** 2.0)
    elif t == "VOLUME":
        calculo_area.vdis(e, 0.0)
        sigy_nt = e.SY
    else:
        e.errhdl(e.PATH, m, "E", "614", "")
    sigz_nt = e.SZ if estable else 0.5 * (e.SZD1 + e.SZD2)
    sigy = 0.0
    if puntual:
        calculo_area.pdis(e, xarg)
        sigy = math.sqrt(e.SY ** 2.0 + (e.DS / 2.0) ** 2.0)
    elif area:
        calculo_area.adisy(e, xarg)
        calculo_area.adisz(e, xarg)
        sigy = math.sqrt(e.SY ** 2.0 + (e.YINIT / 2.0) ** 2.0)
    elif t == "VOLUME":
        calculo_area.vdis(e, xarg)
        sigy = e.SY
    else:
        e.errhdl(e.PATH, m, "E", "614", "")
    sigz = e.SZ if estable else 0.5 * (e.SZD1 + e.SZD2)
    sigy = max(sigy, 0.01)
    sigy_nt = max(sigy_nt, 0.01)
    sigz = max(sigz, 0.01)
    sigz_nt = max(sigz_nt, 0.01)
    u3 = e.USTAR * e.USTAR * e.USTAR
    if e.ZI / e.OBULEN <= 0.0:
        w3 = e.WSTAR * e.WSTAR * e.WSTAR
        eps = (2.5 / max(e.CENTER, e.SFCZ0, 0.0001) + 2.0 / e.ZI) * u3 + 0.4 * (w3) / e.ZI
    else:
        eps = (2.5 / max(e.CENTER, e.SFCZ0, 0.0001) + 4.0 / e.ZI) * u3
    e.UCHM = e.UEFF if estable else e.UEFFD
    if e.UCHM != 0:
        tiempo = max(0.0, xarg / e.UCHM)
        e._GRSM_TIME = tiempo
    else:
        e.errhdl(e.PATH, m, "E", "601", "GRSM")
        tiempo = getattr(e, "_GRSM_TIME", 0.0)
    sigr2 = eps * tiempo ** 3.0 / 3.0
    sigy_t2 = sigy ** 2.0 - sigy_nt ** 2.0
    if sigy_t2 <= 0.01:
        sigy_i = sigy
    else:
        sigy_d2 = sigy_t2 * sigr2 / (sigy_t2 + a0 * math.sqrt(sigy_t2) * math.sqrt(sigr2) + sigr2)
        sigy_i = math.sqrt(sigy_d2 + sigy_nt ** 2.0)
    sigz_t2 = sigz ** 2.0 - sigz_nt ** 2.0
    if sigz_t2 <= 0.01:
        sigz_i = sigz
    else:
        sigz_d2 = sigz_t2 * sigr2 / (sigz_t2 + a0 * math.sqrt(sigz_t2) * math.sqrt(sigr2) + sigr2)
        sigz_i = math.sqrt(sigz_d2 + sigz_nt ** 2.0)
    if estable:
        fran = funciones_dispersion.meandr(e, e.UEFF, e.SVEFF)
    else:
        fran = funciones_dispersion.meandr(e, e.UEFFD, e.SVEFFD)
    if xarg != 0.0:
        sigy_e = 1.0 / ((fran / (e.SRT2PI * xarg)) + (1.0 - fran) / sigy)
    else:
        sigy_e = 0.0
    sigz_e = sigz
    return sigy_i * sigz_i, sigy_e * sigz_e


# ------------------------------------------------------------------------------ GRSM_CALC
def grsm_calc(e):
    """GRSM_CALC: conversión NO -> NO2 con el esquema químico GRS (dilución y arrastre del
    fondo según el tamaño del penacho instantáneo, química durante el tiempo de viaje)."""
    from . import calculo_area, funciones_dispersion
    from .quimica_no2 import sumback_no2
    from .resultados import sumval
    m = "GRSM_CALC"
    if e.EVONLY:
        raise NoTraducido("EVENT")
    if e.GRSMDEBUG:
        raise NoTraducido("GRSMDEBUG")
    f_down = 0.1
    f_bldmin, f_bldmax = 0.0, 0.5
    f_multmin, f_multmax = 0.25, 0.75
    f_bld_rango = f_bldmax - f_bldmin
    f_mult_rango = f_multmax - f_multmin
    ns, nt, ng = e.NUMSRC, e.NUMTYP, e.NUMGRP
    chi, ratio = e.CHI, e.ANO2_RATIO
    l_fullconv = False
    e.HRVAL[:] = 0.0
    sig_i0 = 0.0
    plumebkgno2 = [0.0] * (ns + 1)
    plumebkgno = [0.0] * (ns + 1)
    plumebkgo3 = [0.0] * (ns + 1)
    noxpersource = [0.0] * (ns + 1)
    no2frac = [0.0] * (ng + 1)
    # locales del original que conservan su valor entre receptores (y entre llamadas)
    st = getattr(e, "_GRSM_LOCALES", None)
    if st is None:
        st = e._GRSM_LOCALES = {"L_GRPBACK": False, "NO2FRACMDC": 0.0}
    rxnrates(e)
    e.L_NIGHTHOUR = not (e.QSW > 0.0)
    bgconc_in = e.BGCONC
    e.NO2CONC_BG = bgconc_in * e.NO2_PPB
    if not (e.NOXMISS or e.L_CALCNOXFROMNO2):
        e.NOXCONC_BG = e.NOXBGCONC * e.NO2_PPB
    if not e.O3MISS:
        e.O3CONC_BG = e.O3CONC / e.O3_PPB
        getbgdequil(e)
    else:
        e.O3CONC_BG = -999.0
        l_fullconv = True
    con_fondo = e.L_BACKGRND and not e.L_NIGHTHOUR
    bgconc_out = bgconc_in
    for irec in range(1, e.NUMREC + 1):
        e.IREC = irec
        if not l_fullconv:
            instno2 = instno = instnox = concmaxnox = 0.0
            sig_ix = [0.0] * (ns + 1)
            sig_ex = [0.0] * (ns + 1)
            maxnox = 0.0
            totalnox = 0.0
            for isrc in range(1, ns + 1):
                c = chi[irec, isrc, 1]
                totalnox = totalnox + c
                if c > maxnox:
                    maxnox = c
            fmult = 1.0 - maxnox / totalnox if totalnox > 0.0 else 0.0
            for isrc in range(1, ns + 1):
                e.ISRC = isrc
                noxpersource[isrc] = 0.0
                if chi[irec, isrc, 1] == 0.0:
                    continue
                cno2 = ratio[isrc] * chi[irec, isrc, 1] * e.NO2_PPB
                cno = (1.0 - ratio[isrc]) * chi[irec, isrc, 1] * e.NO2_PPB
                calculo_area.setsrc(e)
                e.WDSIN = e.AWDSIN[isrc]
                e.WDCOS = e.AWDCOS[isrc]
                funciones_dispersion.xydist(e, irec)
                if e.X > f_down:
                    sig_i0, _fdum = plumesizes(e, 0.0)
                    sig_ix[isrc], sig_ex[isrc] = plumesizes(e, e.X)
                    if sig_ix[isrc] > sig_ex[isrc]:
                        sig_ix[isrc] = sig_ex[isrc]
                    if sig_i0 > sig_ix[isrc]:
                        sig_i0 = sig_ix[isrc]
                    bf = e.BLDFAC[irec, isrc]
                    if bf <= f_bldmin:
                        pass
                    elif bf >= f_bldmax:
                        sig_ix[isrc] = sig_ex[isrc]
                    else:
                        sig_ix[isrc] = sig_ix[isrc] + (sig_ex[isrc] - sig_ix[isrc]) * \
                            (bf - f_bldmin) / f_bld_rango
                    if fmult <= f_multmin:
                        pass
                    elif fmult >= f_multmax:
                        sig_ix[isrc] = sig_ex[isrc]
                    else:
                        sig_ix[isrc] = sig_ix[isrc] + (sig_ex[isrc] - sig_ix[isrc]) * \
                            (fmult - f_multmin) / f_mult_rango
                    cno2 = cno2 * sig_ex[isrc] / (sig_ix[isrc])
                    cno = cno * sig_ex[isrc] / (sig_ix[isrc])
                    if con_fondo:
                        plumebkgno2[isrc] = (1.0 - sig_i0 / sig_ix[isrc]) * e.NO2CONC_BG
                        plumebkgno[isrc] = (1.0 - sig_i0 / sig_ix[isrc]) * e.NOCONC_BG
                    else:
                        plumebkgno2[isrc] = 0.0
                        plumebkgno[isrc] = 0.0
                    plumebkgo3[isrc] = (1.0 - sig_i0 / sig_ix[isrc]) * e.O3CONC_BG
                else:
                    if con_fondo:
                        plumebkgno2[isrc] = e.NO2CONC_BG
                        plumebkgno[isrc] = e.NOCONC_BG
                    else:
                        plumebkgno2[isrc] = 0.0
                        plumebkgno[isrc] = 0.0
                    plumebkgo3[isrc] = e.O3CONC_BG
                instno2 = instno2 + cno2
                instno = instno + cno
                noxpersource[isrc] = cno2 + cno
                instnox = instnox + noxpersource[isrc]
                if noxpersource[isrc] > concmaxnox:
                    concmaxnox = noxpersource[isrc]
            e.ISRC = ns + 1
            if con_fondo:
                minbkgno2 = e.NO2CONC_BG
                minbkgno = e.NOCONC_BG
            else:
                minbkgno2 = 0.0
                minbkgno = 0.0
            minbkgo3 = e.O3CONC_BG
            for isrc in range(1, ns + 1):
                if noxpersource[isrc] <= 0.5 * concmaxnox:
                    continue
                if minbkgo3 > plumebkgo3[isrc]:
                    minbkgno2 = plumebkgno2[isrc]
                    minbkgno = plumebkgno[isrc]
                    minbkgo3 = plumebkgo3[isrc]
            if con_fondo:
                minbkgno2, minbkgno, minbkgo3 = quadratic_equil(e, minbkgno2, minbkgno, minbkgo3)
            instno2 = instno2 + minbkgno2
            instno = instno + minbkgno
            # SUM sobre todas las fuentes reservadas
            schi = 0.0
            stt = 0.0
            for k in range(1, e.NSRC + 1):
                schi = schi + chi[irec, k, 1]
            if schi != 0.0:
                for k in range(1, e.NSRC + 1):
                    stt = stt + e.CHI_TTRAVCHM[irec, k]
                e.TTRAVCHM[irec] = stt / schi
            else:
                e.TTRAVCHM[irec] = 0.0
            e.TTRAVCHM[irec] = min(e.TTRAVCHM[irec], 3600.0)
            conc = [0.0, instno, instno2, minbkgo3]
            _do_grsm_chem(e, conc, e.TTRAVCHM[irec])
            e.CONCTEMP = conc
            instno = conc[_NNO] - minbkgno
            instno2 = conc[_NNO2] - minbkgno2
            ensno = 0.0
            ensno2 = 0.0
            for isrc in range(1, ns + 1):
                e.ISRC = isrc
                if instnox == 0 or noxpersource[isrc] == 0:
                    cno2 = 0.0
                    cno = 0.0
                else:
                    cno2 = instno2 * noxpersource[isrc] / instnox
                    cno = instno * noxpersource[isrc] / instnox
                    calculo_area.setsrc(e)
                    e.WDSIN = e.AWDSIN[isrc]
                    e.WDCOS = e.AWDCOS[isrc]
                    funciones_dispersion.xydist(e, irec)
                    if e.X > f_down:
                        cno2 = cno2 * sig_ix[isrc] / (sig_ex[isrc])
                        cno = cno * sig_ix[isrc] / (sig_ex[isrc])
                ensno2 = ensno2 + cno2
                ensno = ensno + cno
            e.ISRC = ns + 1
            indx_grpall = 0
            for i in range(1, ng + 1):
                if e.GRPID[i] == "ALL":
                    indx_grpall = i
                    break
            if indx_grpall == 0:
                e.errhdl(e.PATH, m, "W", "299", "GRSM Option")
            grpbackno2 = 0.0
            grpbackno = 0.0
            st["L_GRPBACK"] = False
            for igrp in range(1, ng + 1):
                if igrp == indx_grpall and e.GRP_BACK[igrp] and not e.L_NIGHTHOUR:
                    grpbackno2 = ensno2 + e.NO2CONC_BG
                    grpbackno = ensno + e.NOCONC_BG
                    st["L_GRPBACK"] = True
                if st["L_GRPBACK"] and (grpbackno2 + grpbackno) >= 0.0:
                    f = _div(grpbackno2, grpbackno2 + grpbackno)
                    f = min(1.0, f) if f >= 0.0 else 1.0
                    no2frac[igrp] = f
                    st["NO2FRACMDC"] = f
                elif not st["L_GRPBACK"] and (ensno2 + ensno) >= 0.0:
                    f = _div(ensno2, ensno2 + ensno)
                    no2frac[igrp] = min(1.0, f) if f >= 0.0 else 1.0
                else:
                    no2frac[igrp] = 0.0
                if e.L_NIGHTHOUR:
                    bgconc_out = e.NO2CONC_BG / e.NO2_PPB
                elif st["L_GRPBACK"]:
                    bgconc_out = no2frac[igrp] * e.NOXCONC_BG / e.NO2_PPB
                else:
                    bgconc_out = bgconc_in
        else:
            for igrp in range(1, ng + 1):
                no2frac[igrp] = 1.0
            bgconc_out = bgconc_in
        for igrp in range(1, ng + 1):
            e.IGRP = igrp
            for isrc in range(1, ns + 1):
                e.ISRC = isrc
                f = st["NO2FRACMDC"] if st["L_GRPBACK"] else no2frac[igrp]
                for ityp in range(1, nt + 1):
                    e.HRVAL[ityp] = f * chi[irec, isrc, ityp]
                sumval(e)
                if e.EVAL[isrc]:
                    raise NoTraducido("EVALFILE")
                e.HRVAL[:] = 0.0
            e.ISRC = ns + 1
            if e.GRP_BACK[igrp]:
                e.BGCONC = bgconc_out
                sumback_no2(e)
        e.IGRP = ng + 1
    e.IREC = e.NUMREC + 1
