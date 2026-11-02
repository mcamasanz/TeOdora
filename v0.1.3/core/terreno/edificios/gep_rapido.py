# -*- coding: utf-8 -*-
"""Bucles GEP de BPIPPRM 04274 (1.440 direcciones de cuarto de grado) compilados con numba.

Es el mismo código que nucleo.py (etiquetas 100-106 y 110-136 del original, con WIDTH, DISLIN,
CNRLIN y GPC), con la misma aritmética: cada expresión en doble y redondeo a simple (``_r4``)
en cada asignación a una variable REAL. Los senos y cosenos de cada dirección se calculan fuera,
con ``math`` (los mismos valores que la versión escalar). Matrices numpy con índices 1-based.

Si numba no está disponible, nucleo.py usa su versión escalar (mismo resultado, más lenta)."""
import numpy as np

try:
    from numba import njit
    HAY_NUMBA = True
except ImportError:  # pragma: no cover
    HAY_NUMBA = False

    def njit(*a, **k):
        def deco(f):
            return f
        return deco(a[0]) if a and callable(a[0]) else deco


@njit(cache=True)
def _r4(x):
    return np.float64(np.float32(x))


R4_M0001 = np.float64(np.float32(-0.001))


@njit(cache=True)
def _width(X, Y, ND, XC, YC, XMAX, XMIN, YMAX, YMIN, csaw, snaw, i, j, c):
    for k in range(1, ND[i, j] + 1):
        XC[c, k] = _r4(X[i, j, k] * csaw + Y[i, j, k] * snaw)
        YC[c, k] = _r4(Y[i, j, k] * csaw - X[i, j, k] * snaw)
        if k == 1:
            YMIN[c] = YC[c, 1]
            YMAX[c] = YC[c, 1]
            XMIN[c] = XC[c, 1]
            XMAX[c] = XC[c, 1]
        if YC[c, k] <= YMIN[c]:
            YMIN[c] = YC[c, k]
        if YC[c, k] >= YMAX[c]:
            YMAX[c] = YC[c, k]
        if XC[c, k] <= XMIN[c]:
            XMIN[c] = XC[c, k]
        if XC[c, k] >= XMAX[c]:
            XMAX[c] = XC[c, k]
    return _r4(XMAX[c] - XMIN[c])


@njit(cache=True)
def _dislin(x1, y1, x2, y2, l5, xsp, ysp):
    ibet = 0
    dx1 = min(x1, x2)
    dx2 = max(x1, x2)
    if xsp < dx1 or xsp > dx2:
        return ibet
    if y1 == y2:
        dist = _r4(ysp - y1)
        if dist >= 0.0 and dist <= l5:
            ibet = 1
    if x1 == x2:
        if xsp == x1:
            d1 = _r4(ysp - y1)
            if d1 <= l5 and d1 >= 0.0:
                ibet = 1
            d2 = _r4(ysp - y2)
            if d2 <= l5 and d2 >= 0.0:
                ibet = 1
    else:
        yi = _r4(y2 + (xsp - x2) * (y1 - y2) / (x1 - x2))
        dist = _r4(ysp - yi)
        if dist >= 0.0 and dist <= l5:
            ibet = 1
    return ibet


@njit(cache=True)
def _cnrlin(x1, y1, x2, y2, xkp, ykp):
    if x1 != x2 and y1 != y2:
        sm = _r4((y2 - y1) / (x2 - x1))
        xi = _r4((ykp + xkp / sm - y1 + x1 * sm) / (sm + 1.0 / sm))
        yi = _r4(y1 + (xi - x1) * sm)
    else:
        if y2 == y1:
            xi = xkp
            yi = y1
        else:
            xi = x1
            yi = ykp
    dist = _r4(np.sqrt((yi - ykp) * (yi - ykp) + (xi - xkp) * (xi - xkp)))
    a1 = _r4((x1 - xi) * (x1 - xi) + (y1 - yi) * (y1 - yi) + (x2 - xi) * (x2 - xi) + (y2 - yi) * (y2 - yi))
    a2 = _r4((x1 - x2) * (x1 - x2) + (y1 - y2) * (y1 - y2))
    return xi, yi, _r4(a2 - a1), dist


@njit(cache=True)
def _gpc(G, GI, BELEV, SB, TNUM2, TLIST2, GEPIN, mxtrs, d, i, c, s, tw, ws, hta, ch, ig):
    """G[:, 0..3] = GEP, GEPBH, GEPBW, GDIRS; GI[:, 0..2] = GTNUM, MI(.,1), MJ(.,1);
    GI[:, 3:] = GTLIST."""
    hwe = _r4(hta + BELEV[i] - SB[s] + 1.5 * ws)
    GEPIN[s, c, ch, ig] = 1
    for vez in range(2):
        if (vez == 0 and hwe > G[s, 0]) or (vez == 1 and hwe == G[s, 0] and tw < G[s, 2]):
            G[s, 0] = hwe
            G[s, 1] = hta
            G[s, 2] = tw
            GI[s, 0] = TNUM2[c]
            GI[s, 1] = i
            GI[s, 2] = c - (i - 1) * mxtrs
            G[s, 3] = _r4(np.float64(d) / 4)
            for m in range(1, GI[s, 0] + 1):
                GI[s, 2 + m] = TLIST2[c, m]


@njit(cache=True)
def gep_niveles(X, Y, ND, NTRS, TH, BELEV, SB, XS, YS, LFLAT, mxtrs, nb, ns,
                csa32, sna32, csaw, snaw, XC, YC, XMAX, XMIN, YMAX, YMIN, W, TNUM2, TLIST2,
                GEPIN, G, GI):
    """Etiquetas 100-106: cada nivel por separado."""
    for d in range(1, 1441):
        csa = csa32[d]
        sna = sna32[d]
        for i in range(1, nb + 1):
            for j in range(1, NTRS[i] + 1):
                c = (i - 1) * mxtrs + j
                TNUM2[c] = 0
                tw = _width(X, Y, ND, XC, YC, XMAX, XMIN, YMAX, YMIN, csaw[d], snaw[d], i, j, c)
                W[c] = tw
                ws = tw
                hta = TH[i, j]
                if hta < tw:
                    ws = hta
                l5 = _r4(ws * 5)
                cxmn = XMIN[c]
                cxmx = XMAX[c]
                cymn = YMIN[c]
                for s in range(1, ns + 1):
                    xpstk = _r4(XS[s] * csa + YS[s] * sna)
                    ypstk = _r4(YS[s] * csa - XS[s] * sna)
                    if xpstk >= cxmn and xpstk <= cxmx and ypstk >= cymn:
                        for k in range(1, ND[i, j] + 1):
                            l_ = k + 1
                            if l_ > ND[i, j]:
                                l_ = 1
                            ibet = _dislin(XC[c, k], YC[c, k], XC[c, l_], YC[c, l_], l5, xpstk, ypstk)
                            if LFLAT[s, c] == 1:
                                ibet = 1
                            if ibet == 1:
                                TNUM2[c] = 1
                                TLIST2[c, 1] = c
                                _gpc(G, GI, BELEV, SB, TNUM2, TLIST2, GEPIN, mxtrs, d, i, c, s, tw, ws, hta, c, 1)


@njit(cache=True)
def _gep_grupo(XC, YC, ND, TNUM2, TLIST2, LFLAT, mxtrs, i, j, c1, s, ws, l5, xpstk, ypstk):
    """Etiquetas 131-135: True si hay que llamar a GPC."""
    for k in range(1, ND[i, j] + 1):
        l_ = k + 1
        if l_ > ND[i, j]:
            l_ = 1
        ibet = _dislin(XC[c1, k], YC[c1, k], XC[c1, l_], YC[c1, l_], l5, xpstk, ypstk)
        if LFLAT[s, c1] == 1:
            ibet = 1
        if ibet == 1:
            return True
    for m in range(2, TNUM2[c1] + 1):
        c2 = TLIST2[c1, m]
        ii = (c2 - 1) // mxtrs + 1
        jj = c2 - (ii - 1) * mxtrs
        for k in range(1, ND[ii, jj] + 1):
            l_ = k + 1
            if l_ > ND[ii, jj]:
                l_ = 1
            ibet = _dislin(XC[c2, k], YC[c2, k], XC[c2, l_], YC[c2, l_], l5, xpstk, ypstk)
            if LFLAT[s, c2] == 1:
                ibet = 1
            if ibet == 1:
                return True
        for k in range(1, ND[i, j] + 1):
            x11 = XC[c1, k]
            y11 = YC[c1, k]
            k1 = k + 1
            if k1 > ND[i, j]:
                k1 = 1
            x12 = XC[c1, k1]
            y12 = YC[c1, k1]
            for l_ in range(1, ND[ii, jj] + 1):
                x21 = XC[c2, l_]
                y21 = YC[c2, l_]
                k2 = l_ + 1
                if k2 > ND[ii, jj]:
                    k2 = 1
                x22 = XC[c2, k2]
                y22 = YC[c2, k2]
                dist = _r4(np.sqrt((x11 - x21) * (x11 - x21) + (y11 - y21) * (y11 - y21)))
                if dist <= ws:
                    ibet = _dislin(x11, y11, x21, y21, l5, xpstk, ypstk)
                    if dist <= l5 and ibet == 1:
                        return True
                xi, yi, bet, dist = _cnrlin(x11, y11, x12, y12, x21, y21)
                if dist <= ws and bet > R4_M0001:
                    ibet = _dislin(x21, y21, xi, yi, l5, xpstk, ypstk)
                    if dist <= l5 and ibet == 1:
                        return True
                xi, yi, bet, dist = _cnrlin(x21, y21, x22, y22, x11, y11)
                if dist <= ws and bet > R4_M0001:
                    ibet = _dislin(x11, y11, xi, yi, l5, xpstk, ypstk)
                    if dist <= l5 and ibet == 1:
                        return True
    return False


@njit(cache=True)
def gep_grupos(X, Y, ND, NTRS, TH, BELEV, SB, XS, YS, LFLAT, DISTMN, mxtrs, nb, ns,
               csa32, sna32, csaw, snaw, XC, YC, XMAX, XMIN, YMAX, YMIN, W, HT, TNUM, TLIST,
               TNUM2, TLIST2, GEPIN, G, GI):
    """Etiquetas 110-136: grupos de niveles de edificios distintos que se pueden combinar."""
    for d in range(1, 1441):
        csa = csa32[d]
        sna = sna32[d]
        for i in range(1, nb + 1):
            for j in range(1, NTRS[i] + 1):
                c1 = (i - 1) * mxtrs + j
                tw = _width(X, Y, ND, XC, YC, XMAX, XMIN, YMAX, YMIN, csaw[d], snaw[d], i, j, c1)
                W[c1] = tw
                HT[c1] = TH[i, j]
                TNUM[c1] = 1
                TLIST[c1, 1] = c1
                for ii in range(1, nb + 1):
                    if i != ii:
                        for jj in range(1, NTRS[ii] + 1):
                            c2 = (ii - 1) * mxtrs + jj
                            tw = _width(X, Y, ND, XC, YC, XMAX, XMIN, YMAX, YMIN, csaw[d], snaw[d], ii, jj, c2)
                            W[c2] = tw
                            HT[c2] = TH[ii, jj]
                            r = min(W[c1], HT[c1])
                            if DISTMN[c1, c2] < r:
                                TNUM[c1] += 1
                                TLIST[c1, TNUM[c1]] = c2
                            else:
                                r = min(W[c2], HT[c2])
                                if DISTMN[c1, c2] < r:
                                    TNUM[c1] += 1
                                    TLIST[c1, TNUM[c1]] = c2
        for i in range(1, nb + 1):
            for j in range(1, NTRS[i] + 1):
                c1 = (i - 1) * mxtrs + j
                if TNUM[c1] <= 1:
                    continue
                tn1 = TNUM[c1]
                htc = HT[TLIST[c1, 1]]
                for t1 in range(1, tn1 + 1):
                    tl1 = TLIST[c1, t1]
                    hta = HT[TLIST[c1, t1]]
                    if not (hta < htc or c1 == tl1):
                        continue
                    TNUM2[c1] = 1
                    TLIST2[c1, 1] = c1
                    xmn = XMIN[c1]
                    ymn = YMIN[c1]
                    xmx = XMAX[c1]
                    ymx = YMAX[c1]
                    for t2 in range(1, tn1 + 1):
                        tl2 = TLIST[c1, t2]
                        if c1 != tl2 and HT[tl2] >= hta:
                            ltn1 = min(hta, W[c1])
                            ltn2 = min(hta, W[tl2])
                            ltn = max(ltn1, ltn2)
                            if DISTMN[c1, tl2] < ltn:
                                TNUM2[c1] += 1
                                TLIST2[c1, TNUM2[c1]] = tl2
                                if XMIN[tl2] < xmn:
                                    xmn = XMIN[tl2]
                                if XMAX[tl2] > xmx:
                                    xmx = XMAX[tl2]
                                if YMIN[tl2] < ymn:
                                    ymn = YMIN[tl2]
                                if YMAX[tl2] > ymx:
                                    ymx = YMAX[tl2]
                    tw = _r4(xmx - xmn)
                    ws = tw
                    if hta < tw:
                        ws = hta
                    l5 = _r4(ws * 5)
                    if TNUM2[c1] > 1:
                        for s in range(1, ns + 1):
                            xpstk = _r4(XS[s] * csa + YS[s] * sna)
                            ypstk = _r4(YS[s] * csa - XS[s] * sna)
                            if xpstk >= xmn and xpstk <= xmx and ypstk >= ymn:
                                if _gep_grupo(XC, YC, ND, TNUM2, TLIST2, LFLAT, mxtrs, i, j, c1, s, ws, l5,
                                              xpstk, ypstk):
                                    _gpc(G, GI, BELEV, SB, TNUM2, TLIST2, GEPIN, mxtrs, d, i, c1, s, tw, ws,
                                         hta, tl1, 2)
