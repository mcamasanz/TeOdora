# -*- coding: utf-8 -*-
"""Traducción de AERMOD 26135 (US EPA, dominio público): perfiles meteorológicos en la malla de
alturas GRIDHT (windgrid.f, tempgrid.f, siggrid.f y las utilidades GINTRP y ZIAVER de metext.f)."""
import math


def gintrp(htbelo, vbelow, htabov, vabove, reqdht):
    """GINTRP: interpolación lineal."""
    return vbelow + ((reqdht - htbelo) / (htabov - htbelo)) * (vabove - vbelow)


def locate(parray, lvlblw, lvlabv, value):
    """LOCATE: índice del nivel inmediatamente inferior (búsqueda binaria)."""
    jl = lvlblw - 1
    ju = lvlabv + 1
    while ju - jl > 1:
        jm = (ju + jl) // 2
        if value >= parray[jm]:
            jl = jm
        else:
            ju = jm
    return min(jl, lvlabv - 1)


def ziaver(nlvls, hts, parray, zi, ndxblw, valzi):
    """ZIAVER: promedio de un perfil entre el suelo y ZI."""
    s = 0.0
    for i in range(2, ndxblw + 1):
        s = s + (hts[i] - hts[i - 1]) * 0.5 * (parray[i] + parray[i - 1])
    if ndxblw < nlvls:
        s = s + (zi - hts[ndxblw]) * 0.5 * (valzi + parray[ndxblw])
    else:
        s = s + (zi - hts[nlvls]) * parray[nlvls]
    return s / zi


def anyavg(nlvls, hts, parray, zbot, ndxabv, ztop, ndxblw):
    """ANYAVG: promedio de un perfil entre ZBOT y ZTOP. Devuelve (promedio, zbot, ndxabv, ztop,
    ndxblw): el original modifica sus argumentos."""
    s = 0.0
    if zbot < 0.5:
        zbot = 0.5
        ndxabv = 2
    if ztop < 0.51:
        ztop = 0.51
        ndxblw = 2
    if ndxblw < ndxabv:
        v = gintrp(hts[ndxabv - 1], parray[ndxabv - 1], hts[ndxabv], parray[ndxabv], 0.5 * (zbot + ztop))
        return v, zbot, ndxabv, ztop, ndxblw
    if ndxblw != ndxabv:
        for i in range(ndxabv + 1, ndxblw + 1):
            s = s + (hts[i] - hts[i - 1]) * 0.5 * (parray[i] + parray[i - 1])
    if ndxabv > 1:
        valbot = gintrp(hts[ndxabv - 1], parray[ndxabv - 1], hts[ndxabv], parray[ndxabv], zbot)
        s = s + (hts[ndxabv] - zbot) * 0.5 * (valbot + parray[ndxabv])
    else:
        s = s + (hts[1] - zbot) * parray[1]
    if ndxblw < nlvls:
        valtop = gintrp(hts[ndxblw], parray[ndxblw], hts[ndxblw + 1], parray[ndxblw + 1], ztop)
        s = s + (ztop - hts[ndxblw]) * 0.5 * (valtop + parray[ndxblw])
    else:
        s = s + (ztop - hts[nlvls]) * parray[nlvls]
    return s / (ztop - zbot), zbot, ndxabv, ztop, ndxblw


# ============================================================================ temperatura
def comptg(e):
    """COMPTG: gradientes de temperatura potencial a partir del perfil observado."""
    e.PATH = "MX"
    ndxblw, ndxabv = 1, 2
    e.NTGLVL = 0
    ta, ht, tg, tgz = e.PFLTA, e.PFLHT, e.PFLTG, e.PFLTGZ
    while ndxabv <= e.NPLVLS:
        if ta[ndxblw] > 0.0:
            if ta[ndxabv] > 0.0:
                e.NTGLVL += 1
                n = e.NTGLVL
                tg[n] = (ta[ndxabv] - ta[ndxblw]) / (ht[ndxabv] - ht[ndxblw]) + e.GOVRCP
                tgz[n] = (ht[ndxabv] + ht[ndxblw]) / 2.0
                ndxblw = ndxabv
                ndxabv = ndxabv + 1
            else:
                ndxabv += 1
        else:
            ndxabv += 1
            ndxblw += 1
    if e.STABLE:
        for n in range(1, e.NTGLVL + 1):
            tg[n] = max(e.SPTGMN, tg[n])
    if e.NTGLVL == 0:
        e.NTGLVL = 1


def tginit(e):
    """TGINIT: escala de temperatura THSTAR y gradientes de referencia para la capa estable."""
    e.PATH = "MX"
    if e.STABLE:
        reflvl = -99.0
        lvl = 1
        while reflvl < 0.0 and lvl <= e.NTGLVL:
            if e.PFLTGZ[lvl] > e.SFCZ0:
                reflvl = e.PFLTGZ[lvl]
            else:
                lvl += 1
        if 0.0 < reflvl <= 100.0:
            e.THSTAR = e.PFLTG[lvl] * e.VONKAR * e.PFLTGZ[lvl] / (1.0 + 5.0 * e.PFLTGZ[lvl] / e.OBULEN)
        else:
            e.THSTAR = e.USTAR ** 2 / (e.G * e.VONKAR * e.OBULEN / e.TA)
        if e.L_ADJUSTAR and e.L_BULKRN and reflvl < 0.0:
            ustarmax = 0.6 * (e.UREFHT / math.log((e.UREFHT - 5. * e.SFCZ0) / e.SFCZ0)) ** 0.333333
            ncloud8 = float(round_half_away(float(e.NCLOUD) * 0.8))
            thstar0 = 1.4 * (0.005 / (math.tan(0.17 * (2.0 * ncloud8 + 1.0))) + 0.05)
            e.THSTAR = thstar0 * (1.0 - ((2.0 * e.USTAR / ustarmax) - 1.0) ** 2.)
        elif e.L_ADJUSTAR and not e.L_BULKRN and reflvl < 0.0:
            e.THSTAR = 0.08
        elif reflvl < 0.0:
            e.THSTAR = e.USTAR ** 2 / (e.G * e.VONKAR * e.OBULEN / e.TA)
        if e.L_ADJUSTAR:
            e.TG4PFL = (e.THSTAR / (e.VONKAR * 2.0)) * (0.74 + 4.7 * 2.0 / e.OBULEN)
            e.TG4XTR = (e.THSTAR / (e.VONKAR * 100.0)) * (0.74 + 4.7 * 100.0 / e.OBULEN)
        else:
            e.TG4PFL = (e.THSTAR / (e.VONKAR * 2.0)) * (1.0 + 5.0 * 2.0 / e.OBULEN)
            e.TG4XTR = (e.THSTAR / (e.VONKAR * 100.0)) * (1.0 + 5.0 * 100.0 / e.OBULEN)
        if e.TG4PFL > 0.5:
            e.errhdl(e.PATH, "TGINIT", "W", "479", _tg4pfl(e))
    else:
        e.THSTAR = -9.0
        e.TG4PFL = e.XVAL


def _tg4pfl(e):
    from .formato import fwrite
    return fwrite('("TG4PFL=",F5.3)', e.TG4PFL)[0]


def round_half_away(x):
    return int(math.floor(x + 0.5)) if x >= 0 else -int(math.floor(-x + 0.5))


def refptg(e, height):
    """REFPTG: gradiente de temperatura potencial teórico a una altura."""
    if e.UNSTAB:
        if height <= e.ZI:
            return e.XVAL
        elif height <= e.ZI + 500.0:
            return e.VPTGZI
        return 0.005
    if height <= 2.0:
        value = e.TG4PFL
    elif height <= 100.0:
        if e.L_ADJUSTAR:
            value = (e.THSTAR / (e.VONKAR * height)) * (0.74 + 4.7 * height / e.OBULEN)
        else:
            value = (e.THSTAR / (e.VONKAR * height)) * (1.00 + 5.0 * height / e.OBULEN)
    else:
        exparg = -1.0 * (height - 100.0) / (e.EFOLDH * max(100.0, e.ZI))
        if exparg > e.EXPLIM:
            value = e.TG4XTR * math.exp(exparg)
        else:
            value = 0.0
    return max(value, e.SPTGMN)


def ntrptg(e, htbelo, vbelow, htabov, vabove, reqdht):
    refblw = refptg(e, htbelo)
    refabv = refptg(e, htabov)
    refreq = refptg(e, reqdht)
    if abs(refabv - refblw) > 0.0001:
        valint = gintrp(htbelo, vbelow, htabov, vabove, reqdht)
        refint = gintrp(htbelo, refblw, htabov, refabv, reqdht)
        return (refreq / refint) * valint
    return gintrp(htbelo, vbelow, htabov, vabove, reqdht)


def xtrptg(e, pflz, pflval, grdz):
    valobs = refptg(e, pflz)
    valgrd = refptg(e, grdz)
    ratio = 1.0 if abs(valobs) < 0.0001 else valgrd / valobs
    if pflz <= 100.0:
        return ratio * pflval
    return pflval * math.exp(-(grdz - pflz) / (e.EFOLDH * max(100.0, e.ZI)))


def xtrpdn(e, grdz):
    if e.UNSTAB:
        if grdz <= e.ZI:
            return e.XVAL
        elif grdz <= e.ZI + 500.0:
            return e.VPTGZI
        return 0.005
    if grdz < 2.0:
        return e.TG4PFL
    if e.L_ADJUSTAR:
        return (e.THSTAR / (e.VONKAR * grdz)) * (0.74 + 4.7 * grdz / e.OBULEN)
    return (e.THSTAR / (e.VONKAR * grdz)) * (1.0 + 5.0 * grdz / e.OBULEN)


def grdptg(e):
    """GRDPTG: gradiente de temperatura potencial en la malla."""
    gh, gt = e.GRIDHT, e.GRIDTG
    tg, tgz = e.PFLTG, e.PFLTGZ
    ntg = e.NTGLVL
    mx = e.MXGLVL
    gindex = 1
    pindex = 1
    vbelow = -999.0
    htbelo = 0.0
    while gindex <= mx:
        if e.STABLE:
            while gt[gindex] < -90.0 and pindex <= ntg:
                if tg[pindex] >= -50.0:
                    if abs(tgz[pindex] - gh[gindex]) <= 0.1:
                        gt[gindex] = tg[pindex]
                    elif gh[gindex] > tgz[pindex]:
                        if pindex < ntg:
                            vbelow = tg[pindex]
                            htbelo = tgz[pindex]
                        else:
                            gt[gindex] = xtrptg(e, tgz[pindex], tg[pindex], gh[gindex])
                    elif gh[gindex] < tgz[pindex]:
                        if vbelow >= -50.0:
                            gt[gindex] = ntrptg(e, htbelo, vbelow, tgz[pindex], tg[pindex], gh[gindex])
                        else:
                            gt[gindex] = xtrpdn(e, gh[gindex])
                else:
                    if pindex == ntg:
                        if vbelow >= -50.0:
                            gt[gindex] = xtrptg(e, tgz[pindex], tg[pindex], gh[gindex])
                        else:
                            gt[gindex] = refptg(e, gh[gindex])
                if gt[gindex] < -50.0 and pindex < ntg:
                    pindex += 1
        elif e.UNSTAB:
            gt[gindex] = refptg(e, gh[gindex])
        gindex += 1
    for n in range(1, mx + 1):
        if e.STABLE or (e.UNSTAB and gh[n] > e.ZI):
            gt[n] = max(e.SPTGMN, gt[n])


def grdpt(e):
    """GRDPT: temperatura potencial en la malla integrando el gradiente desde TREFHT."""
    gh, gt, gp = e.GRIDHT, e.GRIDTG, e.GRIDPT
    nbelow = locate(gh, 1, e.MXGLVL, e.TREFHT)
    ptref = e.TA + e.GOVRCP * (e.TREFHT + e.ZBASE)
    gp[nbelow] = ptref - 0.5 * (gt[nbelow + 1] + gt[nbelow]) * (e.TREFHT - gh[nbelow])
    for l in range(nbelow - 1, 0, -1):
        gp[l] = gp[l + 1] - 0.5 * (gt[l + 1] + gt[l]) * (gh[l + 1] - gh[l])
    for l in range(nbelow + 1, e.MXGLVL + 1):
        gp[l] = gp[l - 1] + 0.5 * (gt[l] + gt[l - 1]) * (gh[l] - gh[l - 1])


def grdden(e):
    """GRDDEN: densidad del aire en la malla."""
    tamb0 = e.TA
    ramb0 = 1.2
    rgasm = 287.026
    gh, gp, rho = e.GRIDHT, e.GRIDPT, e.GRIDRHO
    for i in range(1, e.MXGLVL + 1):
        tamb = gp[i] - e.GOVRCP * (gh[i] + e.ZBASE)
        tbar = 0.5 * (tamb + tamb0)
        rho[i] = ramb0 * (tamb0 / tamb) * math.exp(-e.G * gh[i] / (rgasm * tbar))


# ============================================================================ viento
def unstu(ustr, z, oblen, z0, valpi, valk):
    x0 = (1.0 - 16.0 * z / oblen) ** 0.25
    xz0 = (1.0 - 16.0 * z0 / oblen) ** 0.25
    psim = 2.0 * math.log((1.0 + x0) / 2.0) + math.log((1.0 + x0 * x0) / 2.0) - 2.0 * math.atan(x0) + valpi / 2.0
    psimz0 = (2.0 * math.log((1.0 + xz0) / 2.0) + math.log((1.0 + xz0 * xz0) / 2.0) - 2.0 * math.atan(xz0)
              + valpi / 2.0)
    return (ustr / valk) * (math.log(z / z0) - psim + psimz0)


def stblu(ustr, z, oblen, z0, valk):
    psim = -17.0 * (1.0 - math.exp(-0.29 * z / oblen))
    psimz0 = -17.0 * (1.0 - math.exp(-0.29 * z0 / oblen))
    return (ustr / valk) * (math.log(z / z0) - psim + psimz0)


def refws(e, prflht):
    """REFWS: velocidad del viento teórica (perfil de semejanza)."""
    vldlb = 7.0 * e.SFCZ0
    zi = e.ZI
    # UTHEOR conserva el valor de la llamada anterior si ninguna rama lo asigna
    uth = e.PRF_UTHEOR
    if vldlb < e.UREFHT <= zi:
        if vldlb < prflht <= zi:
            uth = _perfil_u(e, prflht)
        elif prflht <= vldlb:
            uth = _perfil_u(e, vldlb) * (prflht / vldlb)
        elif prflht > zi:
            uth = _perfil_u(e, zi)
    elif e.UREFHT > zi:
        if vldlb < prflht <= zi:
            uth = _perfil_u(e, prflht)
        elif prflht < vldlb:
            uth = _perfil_u(e, vldlb)
        elif prflht > zi:
            uth = e.UREF
    elif e.UREFHT <= vldlb:
        ufact2 = e.UREFHT / vldlb
        if vldlb < prflht <= zi:
            uth = _perfil_u(e, prflht)
        elif prflht <= vldlb:
            uth = e.UREF * (prflht / vldlb) / ufact2
        elif prflht > zi:
            uth = _perfil_u(e, zi)
    e.PRF_UTHEOR = uth
    return uth


def _perfil_u(e, z):
    if e.OBULEN < 0.0:
        return unstu(e.USTAR, z, e.OBULEN, e.SFCZ0, e.PI, e.VONKAR)
    return stblu(e.USTAR, z, e.OBULEN, e.SFCZ0, e.VONKAR)


def ntrpws(e, htbelo, vbelow, htabov, vabove, reqdht):
    refblw = refws(e, htbelo)
    refabv = refws(e, htabov)
    refreq = refws(e, reqdht)
    valint = gintrp(htbelo, vbelow, htabov, vabove, reqdht)
    refint = gintrp(htbelo, refblw, htabov, refabv, reqdht)
    return (refreq / refint) * valint


def xtrpws(e, pflz, pflval, grdz):
    valobs = refws(e, pflz)
    valgrd = refws(e, grdz)
    return (valgrd / valobs) * pflval


def grdws(e):
    """GRDWS: velocidad del viento en la malla."""
    e.PATH = "MX"
    gh, gw = e.GRIDHT, e.GRIDWS
    ws, ht = e.PFLWS, e.PFLHT
    npl = e.NPLVLS
    gindex = pindex = 1
    vbelow = -999.0
    htbelo = 0.0
    while gindex <= e.MXGLVL:
        while gw[gindex] < -90.0 and pindex <= npl:
            if ws[pindex] >= 0.0:
                if abs(ht[pindex] - gh[gindex]) <= 0.1:
                    gw[gindex] = ws[pindex]
                elif gh[gindex] > ht[pindex]:
                    if pindex < npl:
                        vbelow = ws[pindex]
                        htbelo = ht[pindex]
                    else:
                        gw[gindex] = xtrpws(e, ht[pindex], ws[pindex], gh[gindex])
                elif gh[gindex] < ht[pindex]:
                    if vbelow >= 0.0:
                        gw[gindex] = ntrpws(e, htbelo, vbelow, ht[pindex], ws[pindex], gh[gindex])
                    else:
                        gw[gindex] = xtrpws(e, ht[pindex], ws[pindex], gh[gindex])
            else:
                if pindex == npl:
                    if vbelow >= 0.0:
                        gw[gindex] = xtrpws(e, htbelo, vbelow, gh[gindex])
                    else:
                        gw[gindex] = xtrpws(e, e.UREFHT, e.UREF, gh[gindex])
            if gw[gindex] < 0.0 and pindex < npl:
                pindex += 1
        gw[gindex] = max(e.UMINGR, gw[gindex])
        gindex += 1


def _ntrpwd(e, htbelo, vbelow, htabov, vabove, reqdht):
    valabv = vabove
    refblw = refabv = refreq = e.WDREF
    if (valabv - vbelow) < -180.0:
        valabv = valabv + 360.0
    elif (valabv - vbelow) > 180.0:
        valabv = valabv - 360.0
    valint = gintrp(htbelo, vbelow, htabov, valabv, reqdht)
    refint = gintrp(htbelo, refblw, htabov, refabv, reqdht)
    v = (refreq / refint) * valint
    if v > 360.0:
        v = v - 360.0
    elif v <= 0.0:
        v = v + 360.0
    return v


def _xtrpwd(e, pflval):
    valobs = valgrd = e.WDREF
    v = (valgrd / valobs) * pflval
    if v > 360.0:
        v = v - 360.0
    elif v <= 0.0:
        v = v + 360.0
    return v


def grdwd(e):
    """GRDWD: dirección del viento en la malla."""
    gh, gd = e.GRIDHT, e.GRIDWD
    wd, ht = e.PFLWD, e.PFLHT
    npl = e.NPLVLS
    gindex = pindex = 1
    vbelow = -999.0
    htbelo = 0.0
    while gindex <= e.MXGLVL:
        while gd[gindex] < -90.0 and pindex <= npl:
            if wd[pindex] >= 0.0:
                if abs(ht[pindex] - gh[gindex]) <= 0.1:
                    if wd[pindex] > 360.0:
                        wd[pindex] = wd[pindex] - 360.0
                    elif wd[pindex] <= 0.0:
                        wd[pindex] = wd[pindex] + 360.0
                    gd[gindex] = wd[pindex]
                elif gh[gindex] > ht[pindex]:
                    if pindex < npl:
                        vbelow = wd[pindex]
                        htbelo = ht[pindex]
                    else:
                        gd[gindex] = _xtrpwd(e, wd[pindex])
                elif gh[gindex] < ht[pindex]:
                    if vbelow >= 0.0:
                        gd[gindex] = _ntrpwd(e, htbelo, vbelow, ht[pindex], wd[pindex], gh[gindex])
                    else:
                        gd[gindex] = _xtrpwd(e, wd[pindex])
            else:
                if pindex == npl:
                    if vbelow >= 0.0:
                        gd[gindex] = _xtrpwd(e, vbelow)
                    else:
                        gd[gindex] = _xtrpwd(e, e.WDREF)
            if gd[gindex] < 0.0 and pindex < npl:
                pindex += 1
        gindex += 1


# ============================================================================ sigma-v y sigma-w
def refsvc(e, height):
    zdcrs = e.AT1PT2 * e.ZICONV
    sv2 = 0.35 * e.WSTAR ** 2
    if height <= e.ZICONV:
        return math.sqrt(sv2)
    elif e.ZICONV < height <= zdcrs:
        sv2dcr = min(sv2, 0.25)
        return math.sqrt(gintrp(e.ZICONV, sv2, zdcrs, sv2dcr, height))
    return min(math.sqrt(sv2), 0.5)


def refsvm(e, height):
    sv02 = 3.6 * e.USTAR ** 2
    sv2zi = min(sv02, 0.25)
    if height <= e.ZIMECH:
        return math.sqrt(gintrp(0.0, sv02, e.ZIMECH, sv2zi, height))
    return math.sqrt(sv2zi)


def refsv(e, height):
    if e.UNSTAB:
        svc = refsvc(e, height)
        svm = refsvm(e, height)
        return math.sqrt(svc * svc + svm * svm)
    elif e.STABLE:
        return refsvm(e, height)
    return 0.0


def refswc(e, height):
    zc = e.ZICONV
    if height <= 0.1 * zc:
        sw2 = 1.6 * (height / zc) ** (2.0 * e.THIRD) * e.WSTAR ** 2
        return math.sqrt(sw2)
    elif 0.1 * zc < height <= zc:
        return math.sqrt(0.35 * e.WSTAR ** 2)
    elif height > zc:
        exparg = -6.0 * (height - zc) / zc
        if exparg > e.EXPLIM:
            sw2 = 0.35 * e.WSTAR ** 2 * math.exp(exparg)
            return math.sqrt(sw2)
        return 0.0
    return 0.0


def refswm(e, height):
    swr = e.SWRMAX * min(1.0, height / e.ZI)
    if height < e.ZI:
        swbl = 1.3 * e.USTAR * math.sqrt(1.0 - height / e.ZI)
    else:
        swbl = 0.0
    return math.sqrt(swr * swr + swbl * swbl)


def refsw(e, height):
    if e.UNSTAB:
        swc = max(refswc(e, height), 0.0001)
        swm = max(refswm(e, height), 0.0001)
        return math.sqrt(swc * swc + swm * swm)
    elif e.STABLE:
        return max(refswm(e, height), 0.0001)
    return 0.0


def _ref(e, cual, height):
    return refsv(e, height) if cual == 1 else refsw(e, height)


def _grdsig(e, pfl, grid, cual):
    """GRDSV/GRDSW: interpolación de sigma-v (cual = 1) o sigma-w (2) a la malla."""
    gh, ht = e.GRIDHT, e.PFLHT
    npl = e.NPLVLS
    gindex = pindex = 1
    vbelow = -999.0
    htbelo = 0.0
    while gindex <= e.MXGLVL:
        while grid[gindex] < -90.0 and pindex <= npl:
            if pfl[pindex] >= 0.0:
                if abs(ht[pindex] - gh[gindex]) <= 0.1:
                    grid[gindex] = pfl[pindex]
                elif gh[gindex] > ht[pindex]:
                    if pindex < npl:
                        vbelow = pfl[pindex]
                        htbelo = ht[pindex]
                    else:
                        grid[gindex] = (_ref(e, cual, gh[gindex]) / _ref(e, cual, ht[pindex])) * pfl[pindex]
                elif gh[gindex] < ht[pindex]:
                    if vbelow >= 0.0:
                        refblw = _ref(e, cual, htbelo)
                        refabv = _ref(e, cual, ht[pindex])
                        refreq = _ref(e, cual, gh[gindex])
                        valint = gintrp(htbelo, vbelow, ht[pindex], pfl[pindex], gh[gindex])
                        refint = gintrp(htbelo, refblw, ht[pindex], refabv, gh[gindex])
                        grid[gindex] = (refreq / refint) * valint
                    else:
                        grid[gindex] = (_ref(e, cual, gh[gindex]) / _ref(e, cual, ht[pindex])) * pfl[pindex]
            else:
                if pindex == npl:
                    if vbelow >= 0.0:
                        grid[gindex] = (_ref(e, cual, gh[gindex]) / _ref(e, cual, htbelo)) * vbelow
                    else:
                        grid[gindex] = _ref(e, cual, gh[gindex])
            if grid[gindex] < 0.0 and pindex < npl:
                pindex += 1
        gindex += 1


def grdsv(e):
    """GRDSV: sigma-v en la malla."""
    _grdsig(e, e.PFLSV, e.GRIDSV, 1)


def grdsw(e):
    """GRDSW: sigma-w en la malla."""
    _grdsig(e, e.PFLSW, e.GRIDSW, 2)


def perfiles_hora(e):
    """Perfiles de la hora en la malla (bloque de SET_METDATA): viento, dirección, gradiente y
    temperatura potencial, densidad, sigma-v y sigma-w, y sus valores en ZI y promedios."""
    e.GRIDSV[:] = -99.0
    e.GRIDSW[:] = -99.0
    e.GRIDWS[:] = -99.0
    e.GRIDWD[:] = -99.0
    e.GRIDTG[:] = -99.0
    e.GRIDPT[:] = -99.0
    gh = e.GRIDHT
    mx = e.MXGLVL
    e.NDX4ZI = locate(gh, 1, mx, e.ZI)
    tginit(e)
    grdws(e)
    grdwd(e)
    grdptg(e)
    grdpt(e)
    grdden(e)
    n4 = e.NDX4ZI
    if n4 < mx:
        e.UATZI = gintrp(gh[n4], e.GRIDWS[n4], gh[n4 + 1], e.GRIDWS[n4 + 1], e.ZI)
        e.PTATZI = gintrp(gh[n4], e.GRIDPT[n4], gh[n4 + 1], e.GRIDPT[n4 + 1], e.ZI)
    else:
        e.UATZI = e.GRIDWS[mx]
        e.PTATZI = e.GRIDPT[mx]
    grdsv(e)
    numsw = 0
    sumsw = 0.0
    for i in range(1, e.NPLVLS + 1):
        if e.PFLHT[i] >= e.ZI and e.PFLSW[i] >= 0.0:
            numsw += 1
            sumsw = sumsw + e.PFLSW[i]
    e.SWRMAX = sumsw / float(numsw) if numsw > 0 else 0.02 * e.UATZI
    grdsw(e)
    if n4 < mx:
        e.SVATZI = gintrp(gh[n4], e.GRIDSV[n4], gh[n4 + 1], e.GRIDSV[n4 + 1], e.ZI)
        e.SWATZI = gintrp(gh[n4], e.GRIDSW[n4], gh[n4 + 1], e.GRIDSW[n4 + 1], e.ZI)
    else:
        e.SVATZI = e.GRIDSV[mx]
        e.SWATZI = e.GRIDSW[mx]
    e.SVAVG = ziaver(mx, gh, e.GRIDSV, e.ZI, n4, e.SVATZI)
    e.SWAVG = ziaver(mx, gh, e.GRIDSW, e.ZI, n4, e.SWATZI)
    e.UAVG = ziaver(mx, gh, e.GRIDWS, e.ZI, n4, e.UATZI)
