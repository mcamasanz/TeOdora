# -*- coding: utf-8 -*-
"""Traducción de AERMOD 26135 (US EPA, dominio público): parámetros meteorológicos efectivos del
penacho (iblval.f: IBLVAL y METINI; LOCATE y ANYAVG están en perfiles.py)."""
import math

from . import depura
from .perfiles import anyavg, gintrp, locate

_calc1 = None


def iblval(e, xarg):
    """IBLVAL: parámetros efectivos (Ueff, sigma-v, sigma-w, gradiente) promediados sobre la capa
    que ocupa el penacho, para el penacho estable, directo y penetrado."""
    global _calc1
    if _calc1 is None:
        from . import calculo_area as _c
        _calc1 = _c
    calculo_area = _calc1
    gh = e.GRIDHT
    mx = e.MXGLVL
    if e.HBPLUME:
        e.PPFN = 1.0
    if e.STABLE or (e.UNSTAB and e.HS >= e.ZI):
        e.HTEFF = e.HE
        n = locate(gh, 1, mx, e.HTEFF)
        e.UEFF = gintrp(gh[n], e.GRIDWS[n], gh[n + 1], e.GRIDWS[n + 1], e.HTEFF)
        e.SVEFF = gintrp(gh[n], e.GRIDSV[n], gh[n + 1], e.GRIDSV[n + 1], e.HTEFF)
        e.SWEFF = gintrp(gh[n], e.GRIDSW[n], gh[n + 1], e.GRIDSW[n + 1], e.HTEFF)
        e.TGEFF = gintrp(gh[n], e.GRIDTG[n], gh[n + 1], e.GRIDTG[n + 1], e.HTEFF)
        if e.PVMRM or e.GRSM:
            e.EPSEFF = gintrp(gh[n], e.GRIDEPS[n], gh[n + 1], e.GRIDEPS[n + 1], e.HTEFF)
        e.SWEFF = max(e.SWEFF, e.SWMIN)
        e.SVEFF = max(e.SVEFF, e.SVMIN, e.SVUMIN * e.UEFF)
        if e.L_VECTORWS:
            e.UEFF = math.sqrt(e.UEFF * e.UEFF + 2.0 * e.SVEFF * e.SVEFF)
        e.UEFF = max(e.UEFF, e.WSMIN)
        if e.DEBUG:
            depura.ibl_ini(e, "S")
    elif e.UNSTAB and e.HS < e.ZI:
        if e.PPF < 1.0:
            e.HTEFF = e.CENTER
            n = locate(gh, 1, mx, e.HTEFF)
            e.UEFFD = gintrp(gh[n], e.GRIDWS[n], gh[n + 1], e.GRIDWS[n + 1], e.HTEFF)
            e.SVEFFD = gintrp(gh[n], e.GRIDSV[n], gh[n + 1], e.GRIDSV[n + 1], e.HTEFF)
            e.SWEFFD = gintrp(gh[n], e.GRIDSW[n], gh[n + 1], e.GRIDSW[n + 1], e.HTEFF)
            if e.PVMRM or e.GRSM:
                e.EPSEFFD = gintrp(gh[n], e.GRIDEPS[n], gh[n + 1], e.GRIDEPS[n + 1], e.HTEFF)
            e.SWEFFD = max(e.SWEFFD, e.SWMIN)
            e.SVEFFD = max(e.SVEFFD, e.SVMIN, e.SVUMIN * e.UEFFD)
            if e.L_VECTORWS:
                e.UEFFD = math.sqrt(e.UEFFD * e.UEFFD + 2.0 * e.SVEFFD * e.SVEFFD)
            e.UEFFD = max(e.UEFFD, e.WSMIN)
            if e.DEBUG:
                depura.ibl_ini(e, "D")
        if e.PPF > 0.0:
            if e.HBPLUME:
                if e.ZICONVN > 0.0 and e.ZIMECHN > 0.0:
                    e.ZIN = max(e.ZICONVN, e.ZIMECHN)
                elif e.ZICONVN < 0.0 and e.ZIMECHN > 0.0:
                    e.ZIN = e.ZIMECHN
                elif e.ZICONVN > 0.0 and e.ZIMECHN < 0.0:
                    e.ZIN = e.ZICONVN
                else:
                    e.ZIN = e.ZI
                e.ZIAVG = (e.ZI + e.ZIN) / 2.0
                if e.DEBUG:
                    depura.ibl_hbp(e)
            e.HTEFF = e.HE3
            n = locate(gh, 1, mx, e.HTEFF)
            e.UEFF3 = gintrp(gh[n], e.GRIDWS[n], gh[n + 1], e.GRIDWS[n + 1], e.HTEFF)
            e.SVEFF3 = gintrp(gh[n], e.GRIDSV[n], gh[n + 1], e.GRIDSV[n + 1], e.HTEFF)
            e.SWEFF3 = gintrp(gh[n], e.GRIDSW[n], gh[n + 1], e.GRIDSW[n + 1], e.HTEFF)
            e.TGEFF3 = gintrp(gh[n], e.GRIDTG[n], gh[n + 1], e.GRIDTG[n + 1], e.HTEFF)
            if e.PVMRM or e.GRSM:
                e.EPSEFF3 = gintrp(gh[n], e.GRIDEPS[n], gh[n + 1], e.GRIDEPS[n + 1], e.HTEFF)
            e.SWEFF3 = max(e.SWEFF3, e.SWMIN)
            e.SVEFF3 = max(e.SVEFF3, e.SVMIN, e.SVUMIN * e.UEFF3)
            if e.L_VECTORWS:
                e.UEFF3 = math.sqrt(e.UEFF3 * e.UEFF3 + 2.0 * e.SVEFF3 * e.SVEFF3)
            e.UEFF3 = max(e.UEFF3, e.WSMIN)
            if e.DEBUG:
                depura.ibl_ini(e, "P")
    t = e.SRCTYP[e.ISRC]
    if t[:5] == "POINT":
        calculo_area.pdis(e, xarg)
    elif t == "VOLUME":
        calculo_area.vdis(e, xarg)
    elif t in ("AREA", "AREAPOLY", "AREACIRC", "LINE", "OPENPIT"):
        calculo_area.adisz(e, xarg)
    if e.STABLE or (e.UNSTAB and e.HS >= e.ZI):
        sznew = e.SZ
        e.CENTER = e.HE
        if e.CENTER <= 5.0 and e.ZRT <= 5.0:
            zhi = min(5.0, e.ZI)
            zlo = 0.0
        elif e.CENTER > e.ZRT:
            zhi = e.CENTER
            zlo = max(e.CENTER - e.SZCOEF * sznew, e.ZRT)
        else:
            zhi = min(e.CENTER + e.SZCOEF * sznew, e.ZRT)
            zlo = e.CENTER
        if e.DEBUG:
            depura.ibl_capa(e, "Stable", e.CENTER, sznew, zlo, zhi)
        nbhi = locate(gh, 1, mx, zhi)
        nblo = locate(gh, 1, mx, zlo)
        nalo = nblo + 1
        e.UEFF, zlo, nalo, zhi, nbhi = anyavg(mx, gh, e.GRIDWS, zlo, nalo, zhi, nbhi)
        e.SVEFF, zlo, nalo, zhi, nbhi = anyavg(mx, gh, e.GRIDSV, zlo, nalo, zhi, nbhi)
        e.SWEFF, zlo, nalo, zhi, nbhi = anyavg(mx, gh, e.GRIDSW, zlo, nalo, zhi, nbhi)
        e.TGEFF, zlo, nalo, zhi, nbhi = anyavg(mx, gh, e.GRIDTG, zlo, nalo, zhi, nbhi)
        if e.PVMRM or e.GRSM:
            e.EPSEFF, zlo, nalo, zhi, nbhi = anyavg(mx, gh, e.GRIDEPS, zlo, nalo, zhi, nbhi)
        e.SWEFF = max(e.SWEFF, e.SWMIN)
        e.SVEFF = max(e.SVEFF, e.SVMIN, e.SVUMIN * e.UEFF)
        if e.L_VECTORWS:
            e.UEFF = math.sqrt(e.UEFF * e.UEFF + 2.0 * e.SVEFF * e.SVEFF)
        e.UEFF = max(e.UEFF, e.WSMIN)
        if e.DEBUG:
            depura.ibl_fin(e, "S")
    elif e.UNSTAB and e.HS < e.ZI:
        if e.PPF > 0.0:
            if e.HBPLUME:
                hhtop = e.HE3 + 2.15 * e.SZ3
                hhbot = max(e.HE3 - 2.15 * e.SZ3, e.ZRT)
                ppwid = hhtop - hhbot
                htopdif = hhtop - e.ZIAVG
                if htopdif > 0.0:
                    if htopdif < ppwid:
                        if e.ZIAVG <= e.HE3:
                            e.PPFN = 0.5 * math.erf((e.ZIAVG - hhbot) / e.SZ3 / math.sqrt(2.0))
                        else:
                            e.PPFN = 0.5 * (1.0 + math.erf((e.ZIAVG - e.HE3) / e.SZ3 / math.sqrt(2.0)))
                    else:
                        e.PPFN = 0.0
                else:
                    e.PPFN = 1.0
                e.SZ3DBG = e.SZ3
            sz3new = e.SZ3
            if e.HE3 > e.ZRT:
                zhi = e.HE3
                zlo = max(e.HE3 - e.SZCOEF * sz3new, e.ZRT)
            else:
                zhi = min(e.HE3 + e.SZCOEF * sz3new, e.ZRT)
                zlo = e.HE3
            if e.DEBUG:
                depura.ibl_capa(e, "Penetrated", e.HE3, sz3new, zlo, zhi)
            nbhi = locate(gh, 1, mx, zhi)
            nblo = locate(gh, 1, mx, zlo)
            nalo = nblo + 1
            e.UEFF3, zlo, nalo, zhi, nbhi = anyavg(mx, gh, e.GRIDWS, zlo, nalo, zhi, nbhi)
            e.SVEFF3, zlo, nalo, zhi, nbhi = anyavg(mx, gh, e.GRIDSV, zlo, nalo, zhi, nbhi)
            e.SWEFF3, zlo, nalo, zhi, nbhi = anyavg(mx, gh, e.GRIDSW, zlo, nalo, zhi, nbhi)
            e.TGEFF3, zlo, nalo, zhi, nbhi = anyavg(mx, gh, e.GRIDTG, zlo, nalo, zhi, nbhi)
            if e.PVMRM or e.GRSM:
                e.EPSEFF3, zlo, nalo, zhi, nbhi = anyavg(mx, gh, e.GRIDEPS, zlo, nalo, zhi, nbhi)
            e.SWEFF3 = max(e.SWEFF3, e.SWMIN)
            e.SVEFF3 = max(e.SVEFF3, e.SVMIN, e.SVUMIN * e.UEFF3)
            if e.L_VECTORWS:
                e.UEFF3 = math.sqrt(e.UEFF3 * e.UEFF3 + 2.0 * e.SVEFF3 * e.SVEFF3)
            e.UEFF3 = max(e.UEFF3, e.WSMIN)
            if e.DEBUG:
                depura.ibl_fin(e, "P")
        if e.PPF < 1.0:
            szdavg = 0.5 * (e.SZD1 + e.SZD2)
            szdnew = szdavg
            if e.CENTER <= 5.0 and e.ZRT <= 5.0:
                zhi = min(5.0, e.ZI)
                zhi = min(zhi, e.ZI)
                zlo = 0.0
            elif e.CENTER > e.ZRT:
                zhi = min(e.CENTER, e.ZI)
                zlo = max(e.CENTER - e.SZCOEF * szdnew, e.ZRT)
            else:
                zhi = min(e.CENTER + e.SZCOEF * szdnew, e.ZRT)
                zhi = min(zhi, e.ZI)
                zlo = e.CENTER
            if e.DEBUG:
                depura.ibl_capa(e, "Direct", e.CENTER, szdnew, zlo, zhi)
            if zhi > zlo:
                nbhi = locate(gh, 1, mx, zhi)
                nblo = locate(gh, 1, mx, zlo)
                nalo = nblo + 1
                e.UEFFD, zlo, nalo, zhi, nbhi = anyavg(mx, gh, e.GRIDWS, zlo, nalo, zhi, nbhi)
                e.SVEFFD, zlo, nalo, zhi, nbhi = anyavg(mx, gh, e.GRIDSV, zlo, nalo, zhi, nbhi)
                e.SWEFFD, zlo, nalo, zhi, nbhi = anyavg(mx, gh, e.GRIDSW, zlo, nalo, zhi, nbhi)
                if e.PVMRM or e.GRSM:
                    e.EPSEFFD, zlo, nalo, zhi, nbhi = anyavg(mx, gh, e.GRIDEPS, zlo, nalo, zhi, nbhi)
            else:
                e.HTEFF = e.ZI
                n = locate(gh, 1, mx, e.HTEFF)
                e.UEFFD = gintrp(gh[n], e.GRIDWS[n], gh[n + 1], e.GRIDWS[n + 1], e.HTEFF)
                e.SVEFFD = gintrp(gh[n], e.GRIDSV[n], gh[n + 1], e.GRIDSV[n + 1], e.HTEFF)
                e.SWEFFD = gintrp(gh[n], e.GRIDSW[n], gh[n + 1], e.GRIDSW[n + 1], e.HTEFF)
                if e.PVMRM or e.GRSM:
                    e.EPSEFFD = gintrp(gh[n], e.GRIDEPS[n], gh[n + 1], e.GRIDEPS[n + 1], e.HTEFF)
            e.SWEFFD = max(e.SWEFFD, e.SWMIN)
            e.SVEFFD = max(e.SVEFFD, e.SVMIN, e.SVUMIN * e.UEFFD)
            if e.L_VECTORWS:
                e.UEFFD = math.sqrt(e.UEFFD * e.UEFFD + 2.0 * e.SVEFFD * e.SVEFFD)
            e.UEFFD = max(e.UEFFD, e.WSMIN)
            if e.DEBUG:
                depura.ibl_fin(e, "D")
    if e.UNSTAB and e.HS < e.ZI:
        e.UEFFN = e.UEFFD
        e.SVEFFN = e.SVEFFD
        e.SWEFFN = e.SWEFFD


def metini(e):
    """METINI: parámetros meteorológicos a la altura de la chimenea (o de emisión) de la fuente."""
    gh = e.GRIDHT
    n = int(e.NDXSTK[e.ISRC])
    if n >= 1:
        e.SVS = gintrp(gh[n], e.GRIDSV[n], gh[n + 1], e.GRIDSV[n + 1], e.HS)
        e.SWS = gintrp(gh[n], e.GRIDSW[n], gh[n + 1], e.GRIDSW[n + 1], e.HS)
        e.US = gintrp(gh[n], e.GRIDWS[n], gh[n + 1], e.GRIDWS[n + 1], e.HS)
        valabv = e.GRIDWD[n + 1]
        vbelow = e.GRIDWD[n]
        if (valabv - vbelow) < -180.0:
            valabv = valabv + 360.0
        elif (valabv - vbelow) > 180.0:
            valabv = valabv - 360.0
        if vbelow == valabv:
            e.WDIR = vbelow
        else:
            e.WDIR = gintrp(gh[n], vbelow, gh[n + 1], valabv, e.HS)
        if e.WDIR > 360.0:
            e.WDIR = e.WDIR - 360.0
        elif e.WDIR <= 0.0:
            e.WDIR = e.WDIR + 360.0
        e.TGS = gintrp(gh[n], e.GRIDTG[n], gh[n + 1], e.GRIDTG[n + 1], e.HS)
        e.PTS = gintrp(gh[n], e.GRIDPT[n], gh[n + 1], e.GRIDPT[n + 1], e.HS)
    else:
        e.SVS = e.GRIDSV[1]
        e.SWS = e.GRIDSW[1]
        e.US = e.GRIDWS[1]
        e.WDIR = e.GRIDWD[1]
        e.TGS = e.GRIDTG[1]
        e.PTS = e.GRIDPT[1]
    e.SWS = max(e.SWS, e.SWMIN)
    e.SVS = max(e.SVS, e.SVMIN, e.SVUMIN * e.US)
    if e.L_VECTORWS:
        e.US = math.sqrt(e.US * e.US + 2.0 * e.SVS * e.SVS)
    e.US = max(e.US, e.WSMIN)
    if not e.CLMHR and not e.MSGHR:
        e.WDSIN = math.sin(e.WDIR * e.DTORAD)
        e.WDCOS = math.cos(e.WDIR * e.DTORAD)
        e.AFV = e.WDIR - 180.0
        if e.AFV < 0.0:
            e.AFV = e.AFV + 360.0
        e.IFVSEC = int(e.AFV * 0.10 + 0.4999)
        if e.IFVSEC == 0:
            e.IFVSEC = 36
    e.TGP = e.TGS
    e.TA = e.PTS - e.GOVRCP * (e.HS + e.ZBASE)
    e.UP = e.US
    e.SVP = e.SVS
    e.SWP = e.SWS
    if e.TGS > 0.0 and (e.STABLE or (e.UNSTAB and e.HS >= e.ZI)):
        e.BVF = math.sqrt(e.G * e.TGS / e.PTS)
    else:
        e.BVF = 1.0e-10
    if e.BVF < 1.0e-10:
        e.BVF = 1.0e-10
    e.BVPRIM = 0.7 * e.BVF
    e.UEFF = e.US
    e.SVEFF = e.SVS
    e.SWEFF = e.SWS
    e.TGEFF = e.TGS
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
    e.CENTER = e.HS
    e.SURFAC = e.CENTER < 0.1 * e.ZI
