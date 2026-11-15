# -*- coding: utf-8 -*-
"""Traducción de AERMOD 26135 (US EPA, dominio público): algoritmo PRIME de downwash por
edificios (prime.f). Las variables de sus módulos están en ``e.P``.

Convenciones: las variables de MAIN1 van en ``e`` y las de los módulos PRIME_* y PRM2_WAKEDAT en
``e.P`` (en cada rutina se respeta qué módulos usa el original: los nombres repetidos DS, X, Y, R,
PHI, THIRD, VSIGY, VSIGZ y RGAS son de ``e.P`` en todas las rutinas de PRIME salvo SZSFCLPR, que
solo usa MAIN1 y por tanto lee ``e.THIRD``). Las subrutinas devuelven sus argumentos escalares de
salida; las matrices (numpy o listas, índices 1..N) se modifican en su sitio.

Las matrices locales grandes del original (XT.. de NUMRISE, DIST.. de WAKE_DFSN y WAKE_DFSN2) son
estáticas con Intel Fortran (por omisión solo los escalares locales van a la pila), así que se
guardan en atributos de ``e`` preasignados en NUMPR1 (``e.PRM_*``) y conservan su contenido
entre llamadas, como en el original.

Rutinas externas que se llaman (firma asumida):
  · ``perfiles.locate(parray, lvlblw, lvlabv, value)`` → NDXBLW            (LOCATE, metext.f)
  · ``perfiles.gintrp(htbelo, vbelow, htabov, vabove, reqdht)`` → VALUE    (GINTRP, metext.f)
  · ``perfiles.anyavg(nlvls, hts, parray, zbot, ndxabv, ztop, ndxblw)`` →
    ``(value, zbot, ndxabv, ztop, ndxblw)``                               (ANYAVG, metext.f)
"""

import math

import numpy as np

from . import depura, perfiles
from .estado import NoTraducido, Parada
from .formato import nint

_NAN = float("nan")
_INF = float("inf")


def prime1(e):
    """PRIME1: constantes de la difusión en la estela."""
    p = e.P
    p.AFAC = 1.3
    p.XBYRMAX = 15.0
    p.WIZ0 = 0.06
    if e.L_ORD_TURB:
        p.WIZ0 = 0.07
    p.WIY0 = 0.08
    p.WFZ = 1.7
    p.WFY = 1.7
    p.DUA_UA = 0.7
    p.XDECAY = 2.0 / 3.0
    p.XDECAYI = 1.5


def numpr1(e):
    """NUMPR1: constantes de la sobreelevación numérica y malla meteorológica de PRIME."""
    p = e.P
    p.GRAVI = 9.80616
    p.RGAS = 287.026
    p.ZMIN = 0.001
    p.DS = 1.0
    p.NSTEP = 1
    p.SLAST = 5000.0
    p.RP = 9.1e-11
    p.NENT = 0
    p.ALPHAP[1] = 0.11
    p.BETAP[1] = 0.6 if not e.L_AWMA_ENTRAIN else e.AWMA_BETA_ENTRAINCOEFF
    p.XCAT[1] = -9.0e9
    p.XCAT[2] = 9.0e9
    p.ADIA = 0.00977
    p.PTGRAD0 = 0.0
    p.NZA = 45
    nzap1 = p.NZA + 1
    z = p.ZGPTA
    nn = 1
    z[nn] = 10.0
    for dz, n in ((10.0, 19), (50.0, 6), (100.0, 15), (500.0, 4)):
        for _ in range(n):
            nn += 1
            z[nn] = z[nn - 1] + dz
    f = p.ZFACEA
    f[1] = 0.0
    for i in range(2, p.NZA + 1):
        f[i] = 0.5 * (z[i] + z[i - 1])
    f[nzap1] = z[p.NZA] + 0.5 * (z[p.NZA] - z[p.NZA - 1])
    # estado con SAVE de NUMRISE, WAKE_DFSN, WAKE_DFSN2, WAKE_U_TURB, PRMDELH y PRMCALC
    mxnw, mxntr = p.MXNW, p.MXNTR
    for n in ("PRM_XT", "PRM_YT", "PRM_ZT", "PRM_RT"):
        setattr(e, n, np.zeros(mxnw + 1))
    for pre in ("PRM_DF_", "PRM_D2_"):
        for n in ("DIST", "ASIGZ", "ASIGY", "DSZ", "CSIGZ", "CSIGY"):
            setattr(e, pre + n, np.zeros(mxnw + 1))
    e.PRM_WUT_Z = 0.0
    e.PRM_WUT_ZVEL = 0.0
    e.PRMD_HSEFF = 0.0
    e.PRMD_REFF = 0.0
    for n in ("PRMD_XTR", "PRMD_YTR", "PRMD_ZTR", "PRMD_RTR"):
        setattr(e, n, np.zeros(mxntr + 1))
    e.PRMD_LINW = False
    e.PRMC_LINW = False


# ============================================================================ utilidades
def _rpot0(base, expo):
    """Potencia real ``base**expo`` como el Fortran: base negativa → NaN (Python daría un
    complejo) y 0**negativo → +Inf (Python lanzaría una excepción)."""
    if base < 0.0:
        return _NAN
    if base == 0.0 and expo < 0.0:
        return _INF
    return base ** expo


def _dsqrt(x):
    """DSQRT con argumento posiblemente negativo: NaN como el Fortran (math.sqrt lanzaría)."""
    if x < 0.0:
        return _NAN
    return math.sqrt(x)


# ============================================================================ NUMRISE
def numrise(e, ldbhr, h, reff, texit, wexit, ntr, capped, horiz, capfact,
            xtr, ytr, ztr, rtr, dbgunt):
    """NUMRISE: sobreelevación numérica (ecuaciones no Boussinesq) con difusión en la estela y
    fracción capturada por la cavidad.

    Rellena en su sitio xtr, ytr, ztr, rtr (índices 1..ntr). Devuelve ``(linwake, numwake, ierr)``;
    ``numwake`` vale -1 si el original no lo asigna (el penacho no entra en la estela) y
    ``ierr`` = 1 si NN > MXNW (en ese caso el original sale sin restaurar DS, igual aquí).
    Globales: variables de PRIME_PLU (X, Y, Z, S, R, U, V, W, USC, PHI, DEN, TP), DS (temporal),
    FQCAV, DFSN2CALL, XTR_SAV, ZTR_SAV y, a través de WAKE_DFSN/WAKE_DFSN2, las tablas de la
    estela."""
    p = e.P
    mxnw = p.MXNW
    xt, yt, zt, rt = e.PRM_XT, e.PRM_YT, e.PRM_ZT, e.PRM_RT
    rhs = [0.0] * 8
    rhstemp = [0.0] * 8
    f = [0.0] * 8
    ftemp = [0.0] * 8

    ldb = ldbhr
    ldbu = False

    ierr = 0
    nn = 0
    numwake = -1
    # xbi, szi, syi solo se usan si linwake (siempre asignados antes)
    xbi = 0.0
    szi = 0.0
    syi = 0.0

    linwake = False
    p.X = 0.0
    p.Y = 0.0
    p.Z = max(h, p.ZMIN)
    p.S = 0.0
    p.R = reff
    p.U = 0.000002
    p.W = wexit
    p.TP = texit
    drdxa = 0.0
    ipositn = 4

    # paso inicial
    ds0 = p.DS

    # ZCUMUL: cambio acumulado de la altura por la inclinación de las líneas de corriente
    zcumul = 0.0
    r15src = p.XBADJ + (p.XLB + 15.0 * p.RB)

    # meteorología a la altura de emisión
    ua0, ra, ta, dudz0, dpdz = zmet(e, p.Z)

    # reducción del viento en la estela
    xb = p.X - p.XBADJ
    yb = p.Y - p.YBADJ
    zb = max(p.Z, p.ZMIN)
    ipositn = position(e, xb, yb, zb)
    ufac = 1.0
    dufac = 0.0

    if ipositn < 4:
        ufac, dufac = wake_u(e, False, xb, yb, zb, dbgunt)
    ua = ufac * ua0
    dudz = ufac * dudz0 + dufac * ua0

    # flujos de flotabilidad y de cantidad de movimiento (estimación de Briggs)
    deltat = max(p.TP - ta, 0.0)
    fdum = p.W * p.R * p.R / p.TP
    fb = p.GRAVI * fdum * deltat
    fm = p.W * fdum * ta

    if capped:
        # chimenea con sombrerete
        p.R = capfact * reff
        p.U = wexit / (capfact * capfact)
        p.W = 0.001
        fm = p.W * p.W * p.R * p.R * ta / p.TP
    elif horiz:
        # emisión horizontal
        p.U = wexit
        p.W = 0.001
        fm = p.W * p.W * p.R * p.R * ta / p.TP

    # distancia a la sobreelevación final neutra
    uam = max(ua, 1.0)
    wbyu = max(1.0, p.W / uam)
    t = 1.0 + 3.0 / wbyu
    xmaxm = 8.0 * p.R * wbyu * (t * t)
    if fb <= 0.0:
        xmax = xmaxm
    elif fb < 55.0:
        xmaxb = 49.0 * fb ** 0.625
        xmax = max(xmaxm, xmaxb)
    else:
        xmax = 119.0 * fb ** 0.4

    # sobreelevación final neutra de Briggs
    if fb <= 0.0:
        znf = 6.0 * p.R * p.W / uam
    elif fb < 55.0:
        znf = 21.425 * (fb ** 0.75) / uam
    else:
        znf = 38.71 * (fb ** 0.60) / uam
    znf0 = max(0.1, znf)

    # el paso no debe superar la mitad de la sobreelevación probable
    dmin = 0.5 * znf0
    if p.DS > dmin:
        p.DS = dmin
        if ldb:
            depura.numrise_paso(e, dbgunt, znf, ds0)

    p.USC = math.sqrt(p.U * p.U + p.W * p.W)
    p.PHI = math.atan(p.W / p.U)
    np_ = p.NSTEP
    xnp = float(np_)
    nnp = 1

    # bucle de avance
    p.DEN = ra * ta / texit
    lump(e, ua, ta, f)

    while True:                                                    # 999
        if nnp < 150:
            ldbnn = ldb
        else:
            ldbnn = False
        xb = p.X - p.XBADJ
        yb = p.Y - p.YBADJ
        zb = max(p.Z + zcumul, p.ZMIN)
        # pendiente media de las líneas de corriente (a menos de 15R del edificio)
        dxds = 0.0
        dzds = 0.0
        dzdx = 0.0
        dzstrm = 0.0
        ipositn = position(e, xb, yb, zb)
        if ipositn > 2 and p.X <= r15src:
            dzdx = zstream(p.HB, p.WB, p.XLB, p.RB, p.XLR, p.HR, xb, yb, zb)
            dxds = p.U / p.USC
            dzds = dzdx * dxds
            dzstrm = dzds * p.DS
        p.V = 0.0

        drdxa = rate(e, ua, dudz, ra, dpdz, ta, drdxa, rhs)

        # predictor
        marching(f, ftemp, rhs, p.DS)
        unlump(e, ua, ta, ra, ftemp)

        zb = max(p.Z + zcumul + dzstrm, p.ZMIN)
        ua0, ra, ta, dudz0, dpdz = zmet(e, zb)
        ipositn = position(e, xb, yb, zb)
        ufac = 1.0
        dufac = 0.0

        if ipositn < 4:
            ufac, dufac = wake_u(e, ldbu, xb, yb, zb, dbgunt)
        ua = ufac * ua0
        dudz = ufac * dudz0 + dufac * ua0
        drdxa = rate(e, ua, dudz, ra, dpdz, ta, drdxa, rhstemp)

        # corrector
        for i in range(1, 8):
            rhs[i] = 0.5 * (rhstemp[i] - rhs[i])
        marching(ftemp, f, rhs, p.DS)
        unlump(e, ua, ta, ra, f)

        zcumul = zcumul + dzstrm
        zc = max(p.Z + zcumul, p.ZMIN)
        xb = p.X - p.XBADJ
        yb = p.Y - p.YBADJ
        zb = zc
        ipositn = position(e, xb, yb, zb)

        if p.X < 0.0:
            # pequeña distancia negativa por la precisión: a cero y al paso siguiente (GOTO 96)
            p.X = 0.0
            p.S = p.S + p.DS
            nnp = nnp - 1
        else:
            if ldbnn:
                depura.numrise_traza(e, dbgunt, nnp, zc, ua, ra, ta, dudz, dpdz, dzds, ipositn, h)

            # inclinación por debajo de 20 grados: influencia de la estela
            if p.PHI <= 0.349065850398866 and ipositn < 4:
                if not linwake:
                    # el eje del penacho acaba de entrar en la estela
                    linwake = True
                    xbi = xb
                    base = max(h, p.ZMIN)
                    rise = max(0.0, p.Z - base)
                    t = rise / 3.5
                    bidsq = t * t
                    if p.X <= 0.0:
                        szi = math.sqrt(bidsq)
                        syi = szi
                    else:
                        szi = sigzpr(e, p.X, p.Z)
                        szi = math.sqrt(szi * szi + bidsq)
                        syi = sigypr(e, p.X, p.Z)
                        syi = math.sqrt(syi * syi + bidsq)

                    if ldbhr:
                        depura.numrise_dfsn_a(e, dbgunt, zc, xb, szi, syi)

                    # tabla de sigmas y crecimiento en la estela
                    wake_dfsn(e, ldb, xbi, szi, syi, p.Z, dbgunt)
                    numwake = p.NWAK
                # ritmo de crecimiento del radio en este punto
                drdxa = wake_drdx(e, p.X)

            # nueva posición
            p.S = p.S + p.DS
            if float(nnp // np_) == float(nnp) / xnp:
                nn = nnp // np_
                if nn > mxnw:
                    # mensaje al fichero de depuración de PRIME (se escribe siempre)
                    depura.numrise_error(e, dbgunt, nn, mxnw)
                    ierr = 1
                    return linwake, numwake, ierr
                xt[nn] = p.X
                yt[nn] = p.Y
                zt[nn] = zc
                rt[nn] = p.R
                # altura de equilibrio
                if p.X >= xmax:
                    zfin = zc
                    yfin = p.Y
                    xfin = p.X
                    rfin = p.R
                    break                                          # GOTO 97

        # 96: meteorología y reducción del viento en la estela
        ua0, ra, ta, dudz0, dpdz = zmet(e, zb)
        ufac = 1.0
        dufac = 0.0

        if ipositn < 4:
            ufac, dufac = wake_u(e, False, xb, yb, zb, dbgunt)
        ua = ufac * ua0
        dudz = ufac * dudz0 + dufac * ua0

        nnp = nnp + 1
        # máximo local de la sobreelevación
        if p.W < 0.0:
            zfin = zc
            yfin = p.Y
            xfin = p.X
            rfin = p.R
            break                                                  # GOTO 97

        # el paso vuelve hacia DS0
        if p.DS < ds0:
            p.DS = min(ds0, 2.0 * p.DS)

        if p.S < p.SLAST:
            continue
        zfin = zc
        yfin = p.Y
        xfin = p.X
        rfin = p.R
        break

    # 97: trayectoria hasta "15R" (solo la pendiente vertical de las líneas de corriente)
    xfin0 = xfin
    x15r = r15src - xfin0
    if x15r > 0.0:
        dsfin = float(p.NSTEP) * p.DS
        if mxnw - nn == 0:
            dx15r = _INF                       # división por cero del original (x15r > 0)
        else:
            dx15r = x15r / float(mxnw - nn)
        dx15r = max(dsfin, dx15r)
        n15r = min(int(x15r / dx15r), mxnw - nn)
        nbeg = nn + 1
        nend = nn + n15r
        for in_ in range(nbeg, nend + 1):
            xbb = xt[in_ - 1] - p.XBADJ
            xbe = xbb + dx15r
            yb = yt[in_ - 1] - p.YBADJ
            zb = zt[in_ - 1]
            dzdx = 0.0
            ipos = position(e, xbb, yb, zb)
            if ipos > 2:
                dzdxb = zstream(p.HB, p.WB, p.XLB, p.RB, p.XLR, p.HR, xbb, yb, zb)
                dzdxe = zstream(p.HB, p.WB, p.XLB, p.RB, p.XLR, p.HR, xbe, yb, zb)
                dzdx = 0.5 * (dzdxb + dzdxe)
            xt[in_] = xt[in_ - 1] + dx15r
            yt[in_] = yfin
            zt[in_] = max(p.ZMIN, zt[in_ - 1] + dzdx * dx15r)
            rt[in_] = rfin
            zcumul = zcumul + dzdx * dx15r

            # entrada en la estela si no ha ocurrido todavía
            if not linwake:
                if ipos < 4:
                    linwake = True
                    p.X = xt[in_]
                    p.Z = zt[in_] - zcumul
                    xbi = p.X - p.XBADJ
                    base = max(h, p.ZMIN)
                    rise = max(0.0, p.Z - base)
                    t = rise / 3.5
                    bidsq = t * t
                    szi = sigzpr(e, p.X, p.Z)
                    szi = math.sqrt(szi * szi + bidsq)
                    syi = sigypr(e, p.X, p.Z)
                    syi = math.sqrt(syi * syi + bidsq)

                    if ldbhr:
                        depura.numrise_dfsn_b(e, dbgunt, yfin, zt[in_], xbi, szi, syi)

                    wake_dfsn(e, ldb, xbi, szi, syi, p.Z, dbgunt)
                    numwake = p.NWAK
                drdxa = wake_drdx(e, p.X)

        nn = nend
        xfin = xt[nn]
        zfin = zt[nn]

    # matrices de la trayectoria para el programa que llama
    if nn > ntr:
        # submuestreo de los nn puntos
        xtr[ntr] = xfin
        ytr[ntr] = yfin
        ztr[ntr] = zfin
        rtr[ntr] = rfin
        if nn <= 2 * ntr:
            deln = float(nn) / float(ntr)
            for in_ in range(1, ntr):
                # el ejecutable (Intel, /fp:fast) evalúa DBLE(in)*deln, con deln = a/b, reasociado
                # como (in*a)/b; cambia JN cuando in*a/b es entero (comprobado con WAKE_DBG)
                jn = int(float(in_) * float(nn) / float(ntr))
                xtr[in_] = xt[jn]
                ytr[in_] = yt[jn]
                ztr[in_] = zt[jn]
                rtr[in_] = rt[jn]
        else:
            # paso creciente: más puntos en el campo cercano
            deln = 2.0 * float(nn - ntr) / float(ntr * (ntr - 1))
            rn = 0.0
            for in_ in range(1, ntr):
                # el ejecutable (/fp:fast) evalúa (in-1)*deln, con deln = a/b, como ((in-1)*a)/b
                # (comprobado con WAKE_DBG: trayectoria idéntica)
                rn = rn + 1.0 + float(in_ - 1) * (2.0 * float(nn - ntr)) / float(ntr * (ntr - 1))
                jn = int(rn)
                xtr[in_] = xt[jn]
                ytr[in_] = yt[jn]
                ztr[in_] = zt[jn]
                rtr[in_] = rt[jn]
    else:
        for in_ in range(1, nn + 1):
            xtr[in_] = xt[in_]
            ytr[in_] = yt[in_]
            ztr[in_] = zt[in_]
            rtr[in_] = rt[in_]
        for it in range(nn + 1, ntr + 1):
            xtr[it] = xfin
            ytr[it] = yfin
            ztr[it] = zfin
            rtr[it] = rfin

    # restaura el paso
    p.DS = ds0

    if linwake:
        # fracción máxima del penacho capturada en la cavidad
        if xbi < (p.XLB + p.XLR):
            wake_fqc(e, ldb, xbi, xtr, ztr, p.MXNTR, dbgunt)
        else:
            p.FQCAV = 0.0
    else:
        p.FQCAV = 0.0

    if ldbhr:
        depura.numrise_fin(e, dbgunt, texit, fb, fm, xmax, xfin0, x15r, xfin, yfin, zfin, h, rfin, zcumul)
    if ldb:
        depura.numrise_tray(e, dbgunt, False, xtr, ytr, ztr, rtr, ntr)

    # AWMA: copia de las trayectorias para WAKE_DFSN2 / WAKE_TURB (XTR_SAV = XTR)
    if e.L_AWMA_UTURB or e.L_AWMA_UTURBHX:
        for i in range(1, p.P2MXNTR + 1):
            p.XTR_SAV[i] = xtr[i]
            p.ZTR_SAV[i] = ztr[i]

    # nueva tabla de sigmas con la trayectoria completa y sigmas de las fuentes virtuales
    if linwake:
        p.DFSN2CALL = True
        wake_dfsn2(e, ldb, xbi, szi, syi, xtr, ztr, ntr, dbgunt)

    if ldb:
        depura.numrise_tray(e, dbgunt, True, xtr, ytr, ztr, rtr, ntr)

    return linwake, numwake, ierr


def rate(e, ua, dudz, ra, dpdz, ta, drdxa, rhs):
    """RATE: segundos miembros de las ecuaciones (rhs[1..7], en su sitio). Devuelve DRDXA (el
    original lo anula si hay coeficientes de arrastre perturbados y X queda fuera de XCAT)."""
    p = e.P
    # coeficientes de arrastre por omisión (DATA)
    alpha0 = 0.11
    beta0 = 0.6
    alpha = alpha0

    # AWMA: coeficiente de arrastre 0.35 con AWMAENTRAIN
    if not e.L_AWMA_ENTRAIN:
        beta = beta0
    else:
        beta = e.AWMA_BETA_ENTRAINCOEFF

    if p.NENT > 0:
        # zona de coeficientes perturbados
        if not (p.X < p.XCAT[1]):
            nentp1 = p.NENT + 1
            hallado = False
            for i in range(2, nentp1 + 1):
                if p.X <= p.XCAT[i]:
                    alpha = p.ALPHAP[i - 1]
                    beta = p.BETAP[i - 1]
                    hallado = True
                    break
            if not hallado:
                # anula el crecimiento ambiental
                drdxa = 0.0
    # 99
    r = p.R
    rhs[1] = (2.0 * r * ra) * (alpha * abs(p.USC - ua * p.U / p.USC) +
                               beta * abs(ua * math.sin(p.PHI)))

    # arrastre no menor que el crecimiento por la turbulencia ambiental
    rhs1a = (2.0 * r * ra) * ua * drdxa
    rhs[1] = max(rhs[1], rhs1a)

    tp = p.TP
    # X**4 entero: Intel lo desarrolla como (x*x)*(x*x)
    tp2 = tp * tp
    ta2 = ta * ta
    rhs[2] = -(r * r * p.DEN * p.W) * dudz
    rhs[3] = p.GRAVI * r * r * (ra - p.DEN)
    rhs[4] = -(r * r * p.DEN * p.W) * dpdz - p.RP * r * (tp2 * tp2 - ta2 * ta2)
    rhs[5] = p.W / p.USC
    rhs[6] = p.U / p.USC
    rhs[7] = p.V / p.USC
    return drdxa


def lump(e, ua, ta, f):
    """LUMP: variables agrupadas f[1..7] (en su sitio)."""
    p = e.P
    f[1] = p.DEN * p.USC * p.R * p.R
    f[2] = f[1] * (p.U - ua)
    f[3] = f[1] * p.W
    f[4] = f[1] * (p.TP - ta)
    f[5] = p.Z
    f[6] = p.X
    f[7] = p.Y


def marching(fold, fnew, rhs, ds):
    """MARCHING: un paso en S (predictor o corrector); fnew en su sitio. Sin globales."""
    for i in range(1, 8):
        fnew[i] = fold[i] + rhs[i] * ds


def unlump(e, ua, ta, ra, f):
    """UNLUMP: variables físicas de PRIME_PLU a partir de las agrupadas."""
    p = e.P
    p.U = ua + f[2] / f[1]
    p.W = f[3] / f[1]
    p.USC = math.sqrt(p.U * p.U + p.W * p.W)
    p.TP = ta + f[4] / f[1]
    # TP no menor que TA - 10 K
    p.TP = max(p.TP, ta - 10.0)
    p.DEN = (ra * ta) / p.TP
    p.R = math.sqrt(f[1] / (p.USC * p.DEN))
    p.PHI = math.atan(p.W / p.U)
    p.Z = f[5]
    p.X = f[6]
    p.Y = f[7]


def zmet(e, z):
    """ZMET: meteorología a la altura z a partir de los perfiles de AERMOD.
    Devuelve ``(ua, ra, tap, dudz, dpdz)``."""
    g = e.GRIDHT
    ndxblz = perfiles.locate(g, 1, e.MXGLVL, z)

    if ndxblz >= 1:
        n = ndxblz
        n1 = n + 1
        svatz = perfiles.gintrp(g[n], e.GRIDSV[n], g[n1], e.GRIDSV[n1], z)
        swatz = perfiles.gintrp(g[n], e.GRIDSW[n], g[n1], e.GRIDSW[n1], z)
        uatz = perfiles.gintrp(g[n], e.GRIDWS[n], g[n1], e.GRIDWS[n1], z)
        dpdz = perfiles.gintrp(g[n], e.GRIDTG[n], g[n1], e.GRIDTG[n1], z)
        ptz = perfiles.gintrp(g[n], e.GRIDPT[n], g[n1], e.GRIDPT[n1], z)
        ra = perfiles.gintrp(g[n], e.GRIDRHO[n], g[n1], e.GRIDRHO[n1], z)
        # gradiente del viento
        delz = (g[n1] - g[n])
        dudz = (e.GRIDWS[n1] - e.GRIDWS[n]) / delz
    else:
        # valores del nivel más bajo
        svatz = e.GRIDSV[1]
        swatz = e.GRIDSW[1]
        uatz = e.GRIDWS[1]
        dpdz = e.GRIDTG[1]
        ptz = e.GRIDPT[1]
        ra = e.GRIDRHO[1]
        dudz = e.GRIDWS[1] / g[1]

    # temperatura ambiente a partir de la potencial
    tap = ptz - e.P.ADIA * (z + e.ZBASE)

    # vientos y turbulencias mínimos
    swatz = max(swatz, e.SWMIN)
    svatz = max(svatz, e.SVMIN, e.SVUMIN * uatz)
    if e.L_VECTORWS:
        ua = math.sqrt(uatz * uatz + 2.0 * svatz * svatz)
    # (el original sobrescribe aquí el valor vectorial)
    ua = max(uatz, e.WSMIN)

    return float(ua), float(ra), float(tap), float(dudz), float(dpdz)


def zstream(h, w, l, r, lr, hr, x, y, z):
    """ZSTREAM: pendiente media local de las líneas de corriente junto al edificio (DZDX).
    Sin globales."""
    # sin edificio
    if h <= 0.0:
        return 0.0

    dzdx2 = 0.0

    hbyw = h / w
    ypos = abs(y)
    onebyr = 1.0 / r
    wby2 = 0.5 * w
    rby2 = 0.5 * r

    # exponente de la pendiente hacia el suelo (modificado para edificios altos y estrechos)
    zg = 0.0
    expzg = 0.3
    if hbyw >= 2.0:
        t = 0.5 * hbyw
        expzg = expzg * (t * t)

    if x < -r:
        # a barlovento de la influencia del edificio
        dzdx2 = 0.0

    elif x < 0.0:
        # ascenso a barlovento del edificio
        zslope = 2.0 * (hr - h) * (x + r) * (onebyr * onebyr)
        if z > h:
            t = (z - h + r) * onebyr
            dzdx2 = zslope / (t * t * t)
        elif r <= h and z <= 0.67 * h:
            dzdx2 = 0.0
        elif r <= h and z > 0.67 * h:
            dzdx2 = zslope
        elif r > h and z <= 0.67 * (2.0 * h - r):
            dzdx2 = 0.0
        elif r > h and z > 0.67 * (2.0 * h - r):
            dzdx2 = zslope
        else:
            # (solo con NaN; el original escribe 'z out of bounds' en pantalla)
            pass

    elif x <= rby2:
        # ascenso sobre el edificio
        zslope = (-(hr - h) * 4.0 * onebyr) * (2.0 * x * onebyr - 1.0)
        if z <= h:
            dzdx2 = zslope
        else:
            t = (z - h + r) * onebyr
            dzdx2 = zslope / (t * t * t)

    elif x <= l + lr:
        # descenso sobre el edificio hasta el final de la estela cercana
        t = l - rby2 + lr
        zslope = (hr - h) * (r - 2.0 * x) / (t * t)
        if z > h:
            dzdx2 = zslope / ((z - h + r) * onebyr)
        elif z <= zg:
            dzdx2 = 0.0
        else:
            dzdx2 = zslope * _rpot0((z - zg) / (h - zg), expzg)

    else:
        # descenso más allá de la estela cercana (estela lejana)
        zslopelr = -2.0 * (hr - h) / (l - rby2 + lr)
        zslope = zslopelr / ((x - (l + lr - r)) * onebyr)
        if z > h:
            dzdx2 = zslope / ((z - h + r) * onebyr)
        elif z <= zg:
            dzdx2 = 0.0
        else:
            dzdx2 = zslope * _rpot0((z - zg) / (h - zg), expzg)

    # pendiente tridimensional a partir de la del plano central
    if ypos > (wby2 + r / 3.0):
        dzdx = 0.0
    elif ypos <= wby2:
        dzdx = dzdx2
    else:
        yscale = 1.0 + (3.0 * onebyr) * (wby2 - ypos)
        dzdx = dzdx2 * yscale

    return dzdx


def position(e, x, y, z):
    """POSITION: 1 dentro del edificio, 2 en la estela cercana, 3 en la lejana, 4 fuera.
    Devuelve IPOSITN."""
    p = e.P
    skin = 0.99998

    iposy = 4
    iposz = 4
    ipositn = 4

    # sin edificio
    if p.HB <= 0.0:
        return ipositn

    # a barlovento del edificio (y en la cara de barlovento)
    if x <= 0.0:
        return ipositn

    ypos = abs(y)

    rby2 = 0.5 * p.RB
    rby3 = p.THIRD * p.RB
    wby2 = 0.5 * p.WB

    # dentro del edificio
    xtest = x / p.XLB
    ytest = ypos / wby2
    ztest = z / p.HB
    if xtest < skin and ztest < skin and ytest < skin:
        ipositn = 1
        return ipositn

    # por debajo de la frontera de la estela cercana
    if p.XLC < p.XLB:
        # readherencia
        if x < p.XLB:
            zcav = p.HB
            if z <= zcav:
                iposz = 2
        elif x < (p.XLB + p.XLR):
            t = (x - p.XLB) / p.XLR
            zcav = p.HB * math.sqrt(1.0 - t * t)
            if z <= zcav:
                iposz = 2
    else:
        # sin readherencia
        if x <= rby2:
            t = x - rby2
            zcav = p.HR + 4.0 * (t * t) * (p.HB - p.HR) / (p.RB * p.RB)
            if z <= zcav:
                iposz = 2
        elif x < (p.XLB + p.XLR):
            t = (x - rby2) / (p.XLB + p.XLR - rby2)
            zcav = p.HR * math.sqrt(1.0 - t * t)
            if z <= zcav:
                iposz = 2

    # frontera x-y de la estela cercana
    if x <= p.RB:
        t = x - p.RB
        ycav = (wby2 + rby3) - (t * t) / (3.0 * p.RB)
        if ypos <= ycav:
            iposy = 2
    elif x < (p.XLB + p.XLR):
        t = (x - p.RB) / (p.XLB + p.XLR - p.RB)
        ycav = (wby2 + rby3) * math.sqrt(1.0 - t * t)
        if ypos <= ycav:
            iposy = 2

    if iposz == 2 and iposy == 2:
        ipositn = 2

    # estela lejana
    if ipositn == 4:
        zwake, ywake = wake_dim(x, p.HB, p.WB, p.RB)
        if z <= zwake and ypos <= ywake:
            ipositn = 3

    return ipositn


def numgrad(x, xtr, ztr, ntr):
    """NUMGRAD: altura efectiva gradual por interpolación en la tabla (ZEFF). Sin globales."""
    if x >= xtr[ntr]:
        zeff = ztr[ntr]
    else:
        ntrm1 = ntr - 1
        zeff = ztr[1]
        for i in range(ntrm1, 0, -1):
            if x >= xtr[i]:
                ip1 = i + 1
                zeff = ztr[ip1] - (ztr[ip1] - ztr[i]) * (xtr[ip1] - x) / (xtr[ip1] - xtr[i])
                return float(zeff)
    return float(zeff)


def wake_drdx(e, x):
    """WAKE_DRDX: ritmo de crecimiento del radio del penacho en la estela (DRDX)."""
    p = e.P
    nwak = p.NWAK
    xwak = p.XWAK
    drwak = p.DRWAK
    # cero fuera de la zona de interpolación
    if x > xwak[nwak] or x < xwak[1]:
        drdx = 0.0
    elif nwak <= 1:
        # la turbulencia de la estela no altera este penacho
        drdx = 0.0
    else:
        nwkm1 = nwak - 1
        drdx = drwak[1]
        for i in range(nwkm1, 0, -1):
            if x >= xwak[i]:
                ip1 = i + 1
                drdx = drwak[ip1] - (drwak[ip1] - drwak[i]) * (xwak[ip1] - x) / (
                    xwak[ip1] - xwak[i])
                return float(drdx)
    return float(drdx)


# ============================================================================ estela
def wake_ini(e, kurdat, ldbhr, dbgunt, rural, dsbh, dsbw, dsbl, xadj, yadj, ubldg, ustack):
    """WAKE_INI: refresca las variables de PRIME_WAKEDAT (edificio, escalas de la estela y
    tablas reiniciadas). Fija THIRD, LRURL, HB, WB, XLB, XBADJ, YBADJ, UB, URH, RB, HR, XLR, XLC,
    NWAK y el primer elemento de XWAK, SZWAK, SYWAK, DRWAK."""
    p = e.P
    # constante global 1/3
    p.THIRD = 1.0 / 3.0

    p.LRURL = rural
    p.HB = dsbh
    p.WB = dsbw
    p.XLB = dsbl
    p.XBADJ = xadj
    p.YBADJ = yadj
    p.UB = ubldg
    p.URH = ustack

    # dimensiones de la estela
    wake_scales(e, kurdat, ldbhr, dbgunt)

    # reinicia las tablas de sigmas de la estela
    p.NWAK = 1
    p.XWAK[1] = 0.0
    p.SZWAK[1] = 0.0
    p.SYWAK[1] = 0.0
    p.DRWAK[1] = 0.0


def wake_scales(e, kurdat, ldbhr, dbgunt):
    """WAKE_SCALES: escala de longitud RB y dimensiones de la cavidad (HR, XLR, XLC). Sin
    edificio (HB <= 0) anula RB, HB, XLR y XLC y deja HR como estaba (igual que el original)."""
    p = e.P
    twoby3 = 2.0 * p.THIRD

    if p.HB <= 0.0:
        # sin edificio
        p.RB = 0.0
        p.HB = 0.0
        p.XLR = 0.0
        p.XLC = 0.0
    else:
        rw = p.WB / p.HB
        rl = p.XLB / p.HB
        # límites de Fackrell de L/H
        if rl < 0.3:
            rl = 0.3
        if rl > 3.0:
            rl = 3.0

        # escala R de Wilson (H/W y W/H no mayores que 8)
        hh = p.HB
        ww = p.WB
        if hh > 8.0 * ww:
            hh = 8.0 * ww
        if ww > 8.0 * hh:
            ww = 8.0 * hh
        p.RB = (_rpot0(min(hh, ww), twoby3)) * (_rpot0(max(hh, ww), p.THIRD))

        # readherencia para LC < L
        p.XLC = 0.9 * p.RB

        # longitud de la cavidad de recirculación (Fackrell modificada)
        explh = 0.3
        if rw < 1.0:
            explh = max(0.0, 0.3 * (rw - 0.33) / 0.67)
        p.XLR = 1.8 * p.WB / (_rpot0(rl, explh) * (1.0 + 0.24 * rw))

        # altura máxima de la cavidad (Wilson, ASHRAE)
        p.HR = p.HB + 0.22 * p.RB

    if ldbhr:
        depura.wake_scales(e, dbgunt, kurdat)


def _tablas_estela(e, lwak, lcav, np_, nws, ncs, xi, szi, syi, xbc, szcav0, sycav0,
                   dist, asigz, asigy, dsz, csigz, csigy):
    """Construcción de las tablas de PRIME_WAKEDAT (bloque idéntico al final de WAKE_DFSN y de
    WAKE_DFSN2): NWAK, XWAK, SZWAK, SYWAK, DRWAK y NCAV, XCAV, SZCAV, SYCAV."""
    p = e.P
    mxntr = p.MXNTR
    rtpiby2 = 1.25331413731550

    if lwak:
        # tablas WAK
        npw = np_ - nws

        # primer elemento: valores iniciales
        p.XWAK[1] = xi + p.XBADJ
        p.SZWAK[1] = szi
        p.SYWAK[1] = syi
        p.DRWAK[1] = 0.0
        if npw >= mxntr:
            # submuestreo de los npw puntos
            p.NWAK = mxntr
            nwak = p.NWAK
            p.XWAK[nwak] = dist[np_]
            p.SZWAK[nwak] = asigz[np_]
            p.SYWAK[nwak] = asigy[np_]
            p.DRWAK[nwak] = rtpiby2 * dsz[np_]
            if npw <= 2 * mxntr:
                # valores más próximos
                deln = float(npw) / float(nwak)
                for in_ in range(2, nwak):
                    jn = int(float(in_) * float(npw) / float(nwak)) + nws  # reasociado (/fp:fast)
                    p.XWAK[in_] = dist[jn]
                    p.SZWAK[in_] = asigz[jn]
                    p.SYWAK[in_] = asigy[jn]
                    p.DRWAK[in_] = rtpiby2 * dsz[jn]
            else:
                # paso creciente: más puntos en el campo cercano
                deln = 2.0 * float(npw - mxntr) / float(mxntr * (mxntr - 1))
                rn = 1.0
                for in_ in range(2, nwak):
                    # ((in-1)*a)/b como en NUMRISE (la forma agrupada de la cavidad empeora
                    # testpm10: cada bucle se optimizó de forma distinta)
                    rn = rn + 1.0 + float(in_ - 1) * (2.0 * float(npw - mxntr)) / \
                        float(mxntr * (mxntr - 1))
                    jn = int(rn) + nws
                    p.XWAK[in_] = dist[jn]
                    p.SZWAK[in_] = asigz[jn]
                    p.SYWAK[in_] = asigy[jn]
                    p.DRWAK[in_] = rtpiby2 * dsz[jn]
        else:
            # solo los elementos usados
            p.NWAK = npw
            for in_ in range(2, npw + 1):
                inp = in_ + nws
                p.XWAK[in_] = dist[inp]
                p.SZWAK[in_] = asigz[inp]
                p.SYWAK[in_] = asigy[inp]
                p.DRWAK[in_] = rtpiby2 * dsz[inp]

    if lcav:
        # tablas CAV
        npc = np_ - ncs

        p.XCAV[1] = xbc + p.XBADJ
        p.SZCAV[1] = szcav0
        p.SYCAV[1] = sycav0
        if npc >= mxntr:
            p.NCAV = mxntr
            ncav = p.NCAV
            p.XCAV[ncav] = dist[np_]
            p.SZCAV[ncav] = csigz[np_]
            p.SYCAV[ncav] = csigy[np_]
            if npc <= 2 * mxntr:
                deln = float(npc) / float(ncav)
                for in_ in range(2, ncav):
                    jn = int(float(in_) * float(npc) / float(ncav)) + ncs  # reasociado (/fp:fast)
                    p.XCAV[in_] = dist[jn]
                    p.SZCAV[in_] = csigz[jn]
                    p.SYCAV[in_] = csigy[jn]
            else:
                deln = 2.0 * float(npc - mxntr) / float(mxntr * (mxntr - 1))
                rn = 1.0
                for in_ in range(2, ncav):
                    # aquí el ejecutable agrupa además la suma: rn + (1 + ((in-1)*a)/b)
                    # (deducido índice a índice en dos horas de testpm10 y capped)
                    rn = rn + (1.0 + float(in_ - 1) * (2.0 * float(npc - mxntr)) /
                               float(mxntr * (mxntr - 1)))
                    jn = int(rn) + ncs
                    p.XCAV[in_] = dist[jn]
                    p.SZCAV[in_] = csigz[jn]
                    p.SYCAV[in_] = csigy[jn]
        else:
            p.NCAV = npc
            for in_ in range(2, npc + 1):
                inp = in_ + ncs
                p.XCAV[in_] = dist[inp]
                p.SZCAV[in_] = csigz[inp]
                p.SYCAV[in_] = csigy[inp]


def wake_dfsn(e, ldbhr, xi, szi, syi, z, dbgunt):
    """WAKE_DFSN: tabula sigmas y crecimiento del penacho en la estela (Weil 1996 modificado)
    para la fuente principal y la de la cavidad. xi: distancia desde la cara de barlovento al
    punto de entrada en la estela; szi, syi: sigmas en xi; z: altura del penacho en xi.
    Globales: VSIGY, VSIGZ, VSIGYC, VSIGZC y las tablas WAK y CAV de PRIME_WAKEDAT."""
    p = e.P
    mxnw = p.MXNW
    dist, asigz, asigy, dsz, csigz, csigy = (e.PRM_DF_DIST, e.PRM_DF_ASIGZ, e.PRM_DF_ASIGY,
                                             e.PRM_DF_DSZ, e.PRM_DF_CSIGZ, e.PRM_DF_CSIGY)
    hb = p.HB
    wb = p.WB
    rb = p.RB
    xbadj = p.XBADJ

    # xa: transición del crecimiento turbulento de la estela al ambiental
    xaz, xay = wake_xa(e, p.XLB, p.RB)
    xamx = max(xaz, xay)
    xamn = min(xaz, xay)

    # sigmas de las fuentes virtuales
    p.VSIGY = 0.0
    p.VSIGZ = 0.0
    p.VSIGYC = 0.0
    p.VSIGZC = 0.0

    zkdum = 0.0
    ykdum = 0.0
    # ZK, YK, ZKC, YKC: sin inicializar en el original; WAKE_SIG siempre los fija (rama de
    # transición) antes de leerlos
    zk = 0.0
    yk = 0.0
    zkc = 0.0
    ykc = 0.0

    # parámetros de la CAVIDAD
    xcave = p.XLB + p.XLR
    # (distc = XLB + XBADJ: solo depuración)
    xbc = max(xi, p.XLB)
    xbc = min(xbc, xcave)
    xdc = xbc + p.XLR
    szcav0, sycav0 = wake_cav0(e, syi)
    if xi < p.XLB:
        lrevcav = True
    else:
        lrevcav = False

    # ¿material en la cavidad?
    p.NCAV = 1
    p.XCAV[1] = xbc + xbadj
    p.SZCAV[1] = szcav0
    p.SYCAV[1] = sycav0
    if xi >= xcave:
        lcav = False
        lrevcav = False
    else:
        lcav = True

    # ¿afecta la turbulencia de la estela al penacho?
    p.NWAK = 1
    p.XWAK[1] = xi + xbadj
    p.SZWAK[1] = szi
    p.SYWAK[1] = syi
    p.DRWAK[1] = 0.0
    if xi >= xamx:
        lwak = False
        if ldbhr:
            depura.wake_dfsn_ambiente(e, dbgunt, False, xaz, xay, xi)
        if e.AWMADWDBG:
            depura.wake_dfsn_ambiente(e, e.AWMADWDBUNT, False, xaz, xay, xi)
    else:
        lwak = True

    if not lwak and not lcav:
        return

    # borde de la región FDP desde xi
    xd = xi + p.XLR

    # pasos
    dx = 2.0
    xlow = xi
    xhi = xamx
    if lcav:
        xlow = min(xi, xbc)
        xhi = max(xamx, xcave)
    xrange_ = xhi - xlow + dx
    np_ = nint(xrange_ / dx) + 1
    np_ = min(np_, mxnw - 1)
    dx = xrange_ / (float(np_) - 1.0)
    dxi = 1.0 / dx
    nws = 0
    ncs = 0

    # primer elemento en xlow
    dist[1] = xlow + xbadj
    if lwak:
        asigz[1] = szi
        asigy[1] = syi
        dsz[1] = 0.0
    if lcav:
        csigz[1] = szcav0
        csigy[1] = sycav0

    x = xlow

    for n in range(2, np_ + 1):
        xold = x
        x = x + dx
        dist[n] = dist[n - 1] + dx

        # revisión de la cavidad con los datos del paso anterior
        if lrevcav and xold >= p.XLB:
            szcav0, sycav0r = wake_cav0(e, asigy[n - 1])
            if sycav0r > sycav0:
                sycav0 = sycav0r
                p.SYCAV[1] = sycav0
                for ir in range(1, n):
                    csigy[ir] = max(csigy[ir], sycav0)
            lrevcav = False

        # valores iniciales persistentes a barlovento del punto de partida
        if lwak and (xi >= x):
            asigz[n] = asigz[n - 1]
            asigy[n] = asigy[n - 1]
            dsz[n] = dsz[n - 1]
            nws = n
        if lcav and (xbc >= x):
            csigz[n] = szcav0
            csigy[n] = sycav0
            ncs = n

        if xold > xamx:
            # crecimiento ambiental: fuentes virtuales
            if lwak and (xi < x):
                p.VSIGZ = max(p.VSIGZ, szi)
                p.VSIGY = max(p.VSIGY, syi)
                asigz[n] = sigzpr(e, dist[n], z)
                asigy[n] = sigypr(e, dist[n], z)
                asigz[n] = math.sqrt(asigz[n] * asigz[n] + p.VSIGZ * p.VSIGZ)
                asigy[n] = math.sqrt(asigy[n] * asigy[n] + p.VSIGY * p.VSIGY)
                dsz[n] = (asigz[n] - asigz[n - 1]) * dxi
            # fuente de la cavidad
            if lcav and (xbc < x):
                p.VSIGZC = max(p.VSIGZC, szcav0)
                p.VSIGYC = max(p.VSIGYC, sycav0)
                csigz[n] = sigzpr(e, dist[n], 0.0)
                csigy[n] = sigypr(e, dist[n], 0.0)
                csigz[n] = math.sqrt(csigz[n] * csigz[n] + p.VSIGZC * p.VSIGZC)
                csigy[n] = math.sqrt(csigy[n] * csigy[n] + p.VSIGYC * p.VSIGYC)
        else:
            if x < xamn:
                # crecimiento en la estela de sigz y sigy (intensidades en el punto medio)
                xmid = 0.5 * (x + xold)
                wakiz, wakiy = wake_turb(e, xmid, p.XLB, p.RB)
                if lwak and (xi <= x):
                    zk, yk, asigz[n], asigy[n], dsz[n] = wake_sig(
                        x, xd, xold, wakiz, wakiy, asigz[n - 1], asigy[n - 1], hb, wb, rb,
                        zk, yk)
                if lcav and (xbc <= x):
                    zkc, ykc, csigz[n], csigy[n], dzrate = wake_sig(
                        x, xdc, xold, wakiz, wakiy, csigz[n - 1], csigy[n - 1], hb, wb, rb,
                        zkc, ykc)
                    csigz[n] = max(csigz[n], szcav0)
            else:
                # al menos una de las sigmas alcanza el crecimiento ambiental
                # --- SIGMA-Z
                if xold >= xaz:
                    if lwak and (xi <= x):
                        asigz[n] = sigzpr(e, dist[n], z)
                        p.VSIGZ = max(p.VSIGZ, szi)
                        asigz[n] = math.sqrt(asigz[n] * asigz[n] + p.VSIGZ * p.VSIGZ)
                        dsz[n] = (asigz[n] - asigz[n - 1]) * dxi
                    if lcav and (xbc <= x):
                        csigz[n] = sigzpr(e, dist[n], 0.0)
                        csigz[n] = math.sqrt(csigz[n] * csigz[n] + p.VSIGZC * p.VSIGZC)
                        csigz[n] = max(csigz[n], szcav0)
                elif x >= xaz:
                    # transición de la estela al ambiente
                    xnew = xaz
                    xmid = 0.5 * (xnew + xold)
                    wakiz, wakiy = wake_turb(e, xmid, p.XLB, p.RB)
                    if lwak and (xi <= xnew):
                        zk, ykdum, sigzxa, sydum, dzrate = wake_sig(
                            xnew, xd, xold, wakiz, wakiy, asigz[n - 1], asigy[n - 1], hb, wb,
                            rb, zk, ykdum)
                        # fuente virtual: diferencia en cuadratura en la transición
                        sz = sigzpr(e, xaz + xbadj, z)
                        if sigzxa > sz:
                            p.VSIGZ = math.sqrt(sigzxa * sigzxa - sz * sz)
                        else:
                            p.VSIGZ = 0.0
                        asigz[n] = sigzpr(e, dist[n], z)
                        asigz[n] = math.sqrt(asigz[n] * asigz[n] + p.VSIGZ * p.VSIGZ)
                        dsz[n] = (asigz[n] - asigz[n - 1]) * dxi
                    if lcav and (xbc <= xnew):
                        zkc, ykdum, sigzxa, sydum, dzrate = wake_sig(
                            xnew, xdc, xold, wakiz, wakiy, csigz[n - 1], csigy[n - 1], hb, wb,
                            rb, zkc, ykdum)
                        sz = sigzpr(e, xaz + xbadj, 0.0)
                        if sigzxa > sz:
                            p.VSIGZC = math.sqrt(sigzxa * sigzxa - sz * sz)
                        else:
                            p.VSIGZC = 0.0
                        p.VSIGZC = max(p.VSIGZC, szcav0)
                        csigz[n] = sigzpr(e, dist[n], 0.0)
                        csigz[n] = math.sqrt(csigz[n] * csigz[n] + p.VSIGZC * p.VSIGZC)
                else:
                    # crecimiento en la estela de sigz
                    xmid = 0.5 * (x + xold)
                    wakiz, wakiy = wake_turb(e, xmid, p.XLB, p.RB)
                    if lwak and (xi <= x):
                        zk, ykdum, asigz[n], sydum, dsz[n] = wake_sig(
                            x, xd, xold, wakiz, wakiy, asigz[n - 1], asigy[n - 1], hb, wb, rb,
                            zk, ykdum)
                    if lcav and (xbc <= x):
                        zkc, ykdum, csigz[n], sydum, dzrate = wake_sig(
                            x, xdc, xold, wakiz, wakiy, csigz[n - 1], csigy[n - 1], hb, wb, rb,
                            zkc, ykdum)
                        csigz[n] = max(csigz[n], szcav0)
                # --- SIGMA-Y
                if xold >= xay:
                    if lwak and (xi <= x):
                        asigy[n] = sigypr(e, dist[n], z)
                        p.VSIGY = max(p.VSIGY, syi)
                        asigy[n] = math.sqrt(asigy[n] * asigy[n] + p.VSIGY * p.VSIGY)
                    if lcav and (xbc <= x):
                        csigy[n] = sigypr(e, dist[n], 0.0)
                        p.VSIGYC = max(p.VSIGYC, sycav0)
                        csigy[n] = math.sqrt(csigy[n] * csigy[n] + p.VSIGYC * p.VSIGYC)
                elif x >= xay:
                    # transición de la estela al ambiente
                    xnew = xay
                    xmid = 0.5 * (xnew + xold)
                    wakiz, wakiy = wake_turb(e, xmid, p.XLB, p.RB)
                    if lwak and (xi <= xnew):
                        zkdum, yk, szdum, sigyxa, dzrate = wake_sig(
                            xnew, xd, xold, wakiz, wakiy, asigz[n - 1], asigy[n - 1], hb, wb,
                            rb, zkdum, yk)
                        sy = sigypr(e, xay + xbadj, z)
                        if sigyxa > sy:
                            p.VSIGY = math.sqrt(sigyxa * sigyxa - sy * sy)
                        else:
                            p.VSIGY = 0.0
                        asigy[n] = sigypr(e, dist[n], z)
                        asigy[n] = math.sqrt(asigy[n] * asigy[n] + p.VSIGY * p.VSIGY)
                    if lcav and (xbc <= xnew):
                        zkdum, ykc, szdum, sigyxa, dzrate = wake_sig(
                            xnew, xdc, xold, wakiz, wakiy, csigz[n - 1], csigy[n - 1], hb, wb,
                            rb, zkdum, ykc)
                        sy = sigypr(e, xay + xbadj, 0.0)
                        if sigyxa > sy:
                            p.VSIGYC = math.sqrt(sigyxa * sigyxa - sy * sy)
                        else:
                            p.VSIGYC = 0.0
                        csigy[n] = sigypr(e, dist[n], 0.0)
                        csigy[n] = math.sqrt(csigy[n] * csigy[n] + p.VSIGYC * p.VSIGYC)
                else:
                    # crecimiento en la estela de sigy
                    xmid = 0.5 * (x + xold)
                    wakiz, wakiy = wake_turb(e, xmid, p.XLB, p.RB)
                    if lwak and (xi <= x):
                        zkdum, yk, szdum, asigy[n], dzrate = wake_sig(
                            x, xd, xold, wakiz, wakiy, asigz[n - 1], asigy[n - 1], hb, wb, rb,
                            zkdum, yk)
                    if lcav and (xbc <= x):
                        zkdum, ykc, szdum, csigy[n], dzrate = wake_sig(
                            x, xdc, xold, wakiz, wakiy, csigz[n - 1], csigy[n - 1], hb, wb, rb,
                            zkdum, ykc)

    # tablas de PRIME_WAKEDAT
    _tablas_estela(e, lwak, lcav, np_, nws, ncs, xi, szi, syi, xbc, szcav0, sycav0,
                   dist, asigz, asigy, dsz, csigz, csigy)

    if ldbhr or e.AWMADWDBG:
        depura.wake_dfsn_fin(e, dbgunt, ldbhr, xaz, xay, xi, xbc, xdc, lwak, lcav, np_, nws, ncs)


def wake_dfsn2(e, ldbhr, xi, szi, syi, xtr, ztr, ntr, dbgunt):
    """WAKE_DFSN2: como WAKE_DFSN pero con la trayectoria completa (xtr, ztr; índices 1..ntr)
    para las alturas de SIGYPR/SIGZPR y las sigmas de las fuentes virtuales; incluye la opción
    ORD de la cavidad (L_ORD_CAV). Globales: VSIGY, VSIGZ, VSIGYC, VSIGZC y las tablas WAK y CAV
    de PRIME_WAKEDAT."""
    p = e.P
    mxnw = p.MXNW
    dist, asigz, asigy, dsz, csigz, csigy = (e.PRM_D2_DIST, e.PRM_D2_ASIGZ, e.PRM_D2_ASIGY,
                                             e.PRM_D2_DSZ, e.PRM_D2_CSIGZ, e.PRM_D2_CSIGY)
    hb = p.HB
    wb = p.WB
    rb = p.RB
    xbadj = p.XBADJ
    l_ord_cav = e.L_ORD_CAV

    xaz, xay = wake_xa(e, p.XLB, p.RB)
    xamx = max(xaz, xay)
    xamn = min(xaz, xay)

    # altura del penacho en los puntos de transición
    zxay = numgrad(xay + xbadj, xtr, ztr, ntr)
    zxaz = numgrad(xaz + xbadj, xtr, ztr, ntr)

    p.VSIGY = 0.0
    p.VSIGZ = 0.0
    p.VSIGYC = 0.0
    p.VSIGZC = 0.0

    zkdum = 0.0
    ykdum = 0.0
    # ZK, YK, ZKC, YKC: sin inicializar en el original (ver WAKE_DFSN)
    zk = 0.0
    yk = 0.0
    zkc = 0.0
    ykc = 0.0

    # parámetros de la CAVIDAD
    xcave = p.XLB + p.XLR
    xbc = max(xi, p.XLB)
    xbc = min(xbc, xcave)
    xdc = xbc + p.XLR
    szcav0, sycav0 = wake_cav0(e, syi)
    if xi < p.XLB:
        lrevcav = True
    else:
        lrevcav = False

    p.NCAV = 1
    p.XCAV[1] = xbc + xbadj
    p.SZCAV[1] = szcav0
    p.SYCAV[1] = sycav0
    if xi >= xcave:
        lcav = False
        lrevcav = False
    else:
        lcav = True

    p.NWAK = 1
    p.XWAK[1] = xi + xbadj
    p.SZWAK[1] = szi
    p.SYWAK[1] = syi
    p.DRWAK[1] = 0.0
    if xi >= xamx:
        lwak = False
        if ldbhr:
            depura.wake_dfsn_ambiente(e, dbgunt, True, xaz, xay, xi)
        if e.AWMADWDBG:
            depura.wake_dfsn2_ambiente_awma(e, xaz, xay, xi)
    else:
        lwak = True

    if not lwak and not lcav:
        return

    xd = xi + p.XLR

    dx = 2.0
    xlow = xi
    xhi = xamx
    if lcav:
        xlow = min(xi, xbc)
        xhi = max(xamx, xcave)
    xrange_ = xhi - xlow + dx
    np_ = nint(xrange_ / dx) + 1
    np_ = min(np_, mxnw - 1)
    dx = xrange_ / (float(np_) - 1.0)
    dxi = 1.0 / dx
    nws = 0
    ncs = 0

    dist[1] = xlow + xbadj
    if lwak:
        asigz[1] = szi
        asigy[1] = syi
        dsz[1] = 0.0
    if lcav:
        csigz[1] = szcav0
        csigy[1] = sycav0

    x = xlow

    if e.AWMADWDBG:
        depura.wake_dfsn2_awma_ini(e)

    for n in range(2, np_ + 1):
        xold = x
        x = x + dx
        dist[n] = dist[n - 1] + dx

        if lrevcav and xold >= p.XLB:
            szcav0, sycav0r = wake_cav0(e, asigy[n - 1])
            if sycav0r > sycav0:
                sycav0 = sycav0r
                p.SYCAV[1] = sycav0
                for ir in range(1, n):
                    csigy[ir] = max(csigy[ir], sycav0)
            lrevcav = False

        if lwak and (xi >= x):
            asigz[n] = asigz[n - 1]
            asigy[n] = asigy[n - 1]
            dsz[n] = dsz[n - 1]
            nws = n
        if lcav and (xbc >= x):
            csigz[n] = szcav0
            csigy[n] = sycav0
            ncs = n

        if xold > xamx:
            # crecimiento ambiental: fuentes virtuales
            if lwak and (xi < x):
                p.VSIGZ = max(p.VSIGZ, szi)
                p.VSIGY = max(p.VSIGY, syi)
                zdist = numgrad(dist[n], xtr, ztr, ntr)
                asigz[n] = sigzpr(e, dist[n], zdist)
                asigy[n] = sigypr(e, dist[n], zdist)
                asigz[n] = math.sqrt(asigz[n] * asigz[n] + p.VSIGZ * p.VSIGZ)
                asigy[n] = math.sqrt(asigy[n] * asigy[n] + p.VSIGY * p.VSIGY)
                dsz[n] = (asigz[n] - asigz[n - 1]) * dxi
            if lcav and (xbc < x):
                p.VSIGZC = max(p.VSIGZC, szcav0)
                p.VSIGYC = max(p.VSIGYC, sycav0)
                csigz[n] = sigzpr(e, dist[n], 0.0)
                csigy[n] = sigypr(e, dist[n], 0.0)
                csigz[n] = math.sqrt(csigz[n] * csigz[n] + p.VSIGZC * p.VSIGZC)
                csigy[n] = math.sqrt(csigy[n] * csigy[n] + p.VSIGYC * p.VSIGYC)
        else:
            if x < xamn:
                # crecimiento en la estela de sigz y sigy
                xmid = 0.5 * (x + xold)
                wakiz, wakiy = wake_turb(e, xmid, p.XLB, p.RB)
                if lwak and (xi <= x):
                    zk, yk, asigz[n], asigy[n], dsz[n] = wake_sig(
                        x, xd, xold, wakiz, wakiy, asigz[n - 1], asigy[n - 1], hb, wb, rb,
                        zk, yk)

                # fuente de la cavidad
                if l_ord_cav:
                    # modificación ORD del downwash
                    if lcav and (xbc <= x) and (x >= xcave):
                        zkc, ykc, csigz[n], csigy[n], dzrate = wake_sig(
                            x, xdc, xold, wakiz, wakiy, csigz[n - 1], csigy[n - 1], hb, wb,
                            rb, zkc, ykc)
                        csigz[n] = max(csigz[n], szcav0)
                    elif lcav and (xbc <= x) and (x < xcave):
                        zkc, ykc, csigz[n], csigy[n], dzrate = wake_sig(
                            x, xdc, xold, wakiz, wakiy, csigz[n - 1], csigy[n - 1], hb, wb,
                            rb, zkc, ykc)
                        csigz[n] = 1.0 * csigz[1]
                        csigy[n] = 1.0 * csigy[1]
                else:
                    # código reglamentario
                    if lcav and (xbc <= x):
                        zkc, ykc, csigz[n], csigy[n], dzrate = wake_sig(
                            x, xdc, xold, wakiz, wakiy, csigz[n - 1], csigy[n - 1], hb, wb,
                            rb, zkc, ykc)
                        csigz[n] = max(csigz[n], szcav0)
            else:
                # --- SIGMA-Z
                if xold >= xaz:
                    if lwak and (xi <= x):
                        zdist = numgrad(dist[n], xtr, ztr, ntr)
                        asigz[n] = sigzpr(e, dist[n], zdist)
                        p.VSIGZ = max(p.VSIGZ, szi)
                        asigz[n] = math.sqrt(asigz[n] * asigz[n] + p.VSIGZ * p.VSIGZ)
                        dsz[n] = (asigz[n] - asigz[n - 1]) * dxi
                    if lcav and (xbc <= x):
                        p.VSIGZC = max(p.VSIGZC, szcav0)
                        csigz[n] = sigzpr(e, dist[n], 0.0)
                        csigz[n] = math.sqrt(csigz[n] * csigz[n] + p.VSIGZC * p.VSIGZC)
                elif x >= xaz:
                    # transición de la estela al ambiente
                    xnew = xaz
                    xmid = 0.5 * (xnew + xold)
                    wakiz, wakiy = wake_turb(e, xmid, p.XLB, p.RB)
                    if lwak and (xi <= xnew):
                        zk, ykdum, sigzxa, sydum, dzrate = wake_sig(
                            xnew, xd, xold, wakiz, wakiy, asigz[n - 1], asigy[n - 1], hb, wb,
                            rb, zk, ykdum)
                        sz = sigzpr(e, xaz + xbadj, zxaz)
                        if sigzxa > sz:
                            p.VSIGZ = math.sqrt(sigzxa * sigzxa - sz * sz)
                        else:
                            p.VSIGZ = 0.0
                        zdist = numgrad(dist[n], xtr, ztr, ntr)
                        asigz[n] = sigzpr(e, dist[n], zdist)
                        asigz[n] = math.sqrt(asigz[n] * asigz[n] + p.VSIGZ * p.VSIGZ)
                        dsz[n] = (asigz[n] - asigz[n - 1]) * dxi
                    if lcav and (xbc <= xnew):
                        zkc, ykdum, sigzxa, sydum, dzrate = wake_sig(
                            xnew, xdc, xold, wakiz, wakiy, csigz[n - 1], csigy[n - 1], hb, wb,
                            rb, zkc, ykdum)
                        sz = sigzpr(e, xaz + xbadj, 0.0)
                        if sigzxa > sz:
                            p.VSIGZC = math.sqrt(sigzxa * sigzxa - sz * sz)
                        else:
                            p.VSIGZC = 0.0
                        p.VSIGZC = max(p.VSIGZC, szcav0)
                        csigz[n] = sigzpr(e, dist[n], 0.0)
                        csigz[n] = math.sqrt(csigz[n] * csigz[n] + p.VSIGZC * p.VSIGZC)
                else:
                    # crecimiento en la estela de sigz
                    xmid = 0.5 * (x + xold)
                    wakiz, wakiy = wake_turb(e, xmid, p.XLB, p.RB)
                    if lwak and (xi <= x):
                        zk, ykdum, asigz[n], sydum, dsz[n] = wake_sig(
                            x, xd, xold, wakiz, wakiy, asigz[n - 1], asigy[n - 1], hb, wb, rb,
                            zk, ykdum)
                    if lcav and (xbc <= x):
                        zkc, ykdum, csigz[n], sydum, dzrate = wake_sig(
                            x, xdc, xold, wakiz, wakiy, csigz[n - 1], csigy[n - 1], hb, wb, rb,
                            zkc, ykdum)
                        csigz[n] = max(csigz[n], szcav0)
                # --- SIGMA-Y
                if xold >= xay:
                    if lwak and (xi <= x):
                        zdist = numgrad(dist[n], xtr, ztr, ntr)
                        asigy[n] = sigypr(e, dist[n], zdist)
                        p.VSIGY = max(p.VSIGY, syi)
                        asigy[n] = math.sqrt(asigy[n] * asigy[n] + p.VSIGY * p.VSIGY)

                    # fuente de la cavidad
                    if l_ord_cav:
                        # modificaciones AWMADWNW / ORD
                        if lcav and (x >= xcave) and (xbc <= x):
                            csigy[n] = sigypr(e, dist[n], 0.0)
                            p.VSIGYC = max(p.VSIGYC, sycav0)
                            csigy[n] = math.sqrt(csigy[n] * csigy[n] + p.VSIGYC * p.VSIGYC)
                        elif lcav and (x < xcave) and (xbc <= x):
                            # (SIGYPR se llama por su efecto en SYAMB; el valor se sobrescribe)
                            csigy[n] = sigypr(e, dist[n], 0.0)
                            p.VSIGYC = max(p.VSIGYC, sycav0)
                            csigy[n] = 1.0 * csigy[1]
                    else:
                        # código reglamentario
                        if lcav and (xbc <= x):
                            csigy[n] = sigypr(e, dist[n], 0.0)
                            p.VSIGYC = max(p.VSIGYC, sycav0)
                            csigy[n] = math.sqrt(csigy[n] * csigy[n] + p.VSIGYC * p.VSIGYC)

                elif x >= xay:
                    # transición de la estela al ambiente
                    xnew = xay
                    xmid = 0.5 * (xnew + xold)
                    wakiz, wakiy = wake_turb(e, xmid, p.XLB, p.RB)
                    if lwak and (xi <= xnew):
                        zkdum, yk, szdum, sigyxa, dzrate = wake_sig(
                            xnew, xd, xold, wakiz, wakiy, asigz[n - 1], asigy[n - 1], hb, wb,
                            rb, zkdum, yk)
                        sy = sigypr(e, xay + xbadj, zxay)
                        if sigyxa > sy:
                            p.VSIGY = math.sqrt(sigyxa * sigyxa - sy * sy)
                        else:
                            p.VSIGY = 0.0
                        zdist = numgrad(dist[n], xtr, ztr, ntr)
                        asigy[n] = sigypr(e, dist[n], zdist)
                        asigy[n] = math.sqrt(asigy[n] * asigy[n] + p.VSIGY * p.VSIGY)
                    if lcav and (xbc <= xnew):
                        zkdum, ykc, szdum, sigyxa, dzrate = wake_sig(
                            xnew, xdc, xold, wakiz, wakiy, csigz[n - 1], csigy[n - 1], hb, wb,
                            rb, zkdum, ykc)
                        sy = sigypr(e, xay + xbadj, 0.0)
                        if sigyxa > sy:
                            p.VSIGYC = math.sqrt(sigyxa * sigyxa - sy * sy)
                        else:
                            p.VSIGYC = 0.0
                        csigy[n] = sigypr(e, dist[n], 0.0)
                        csigy[n] = math.sqrt(csigy[n] * csigy[n] + p.VSIGYC * p.VSIGYC)
                else:
                    # crecimiento en la estela de sigy
                    xmid = 0.5 * (x + xold)
                    wakiz, wakiy = wake_turb(e, xmid, p.XLB, p.RB)
                    if lwak and (xi <= x):
                        zkdum, yk, szdum, asigy[n], dzrate = wake_sig(
                            x, xd, xold, wakiz, wakiy, asigz[n - 1], asigy[n - 1], hb, wb, rb,
                            zkdum, yk)
                    if lcav and (xbc <= x):
                        zkdum, ykc, szdum, csigy[n], dzrate = wake_sig(
                            x, xdc, xold, wakiz, wakiy, csigz[n - 1], csigy[n - 1], hb, wb, rb,
                            zkdum, ykc)

    _tablas_estela(e, lwak, lcav, np_, nws, ncs, xi, szi, syi, xbc, szcav0, sycav0,
                   dist, asigz, asigy, dsz, csigz, csigy)

    if ldbhr or e.AWMADWDBG:
        depura.wake_dfsn2_fin(e, dbgunt, ldbhr)


def wake_turb(e, xinp, l, rinp):
    """WAKE_TURB: intensidades de turbulencia en la estela a la distancia xinp desde la cara de
    barlovento (l: distancia a la cara de sotavento; rinp: escala R). Devuelve ``(tiz, tiy)``.
    Con AWMAUTURBHX y DFSN2CALL recalcula (y luego restaura) UEFF, SVEFF, SWEFF y TGEFF de
    MAIN1 y fija ZEFF_PRM2."""
    p = e.P
    # intensidades ambientales a partir de los parámetros efectivos de AERMOD
    ambiz = e.SWEFF / e.UEFF
    ambiy = e.SVEFF / e.UEFF

    # intensidad asintótica en la estela lejana
    fariz = min(p.WIZ0, ambiz)
    fariy = min(p.WIY0, ambiy)

    # AWMA: con AWMAUTURBHX y la llamada desde WAKE_DFSN2, parámetros efectivos recalculados
    if e.L_AWMA_UTURBHX and p.DFSN2CALL:
        # altura del penacho en xinp
        if xinp < p.XTR_SAV[p.P2MXNTR]:
            p.ZEFF_PRM2 = numgrad(xinp, p.XTR_SAV, p.ZTR_SAV, p.P2MXNTR)
        else:
            p.ZEFF_PRM2 = p.ZTR_SAV[p.P2MXNTR]

        zhi = p.ZEFF_PRM2 + 5.0
        zlo = p.ZEFF_PRM2 - 5.0

        # promedios entre ZLO y ZHI (ANYAVG modifica sus argumentos)
        ndxbhi = perfiles.locate(e.GRIDHT, 1, e.MXGLVL, zhi)
        ndxblo = perfiles.locate(e.GRIDHT, 1, e.MXGLVL, zlo)

        ndxalo = ndxblo + 1
        e.UEFF, zlo, ndxalo, zhi, ndxbhi = perfiles.anyavg(
            e.MXGLVL, e.GRIDHT, e.GRIDWS, zlo, ndxalo, zhi, ndxbhi)
        e.SVEFF, zlo, ndxalo, zhi, ndxbhi = perfiles.anyavg(
            e.MXGLVL, e.GRIDHT, e.GRIDSV, zlo, ndxalo, zhi, ndxbhi)
        e.SWEFF, zlo, ndxalo, zhi, ndxbhi = perfiles.anyavg(
            e.MXGLVL, e.GRIDHT, e.GRIDSW, zlo, ndxalo, zhi, ndxbhi)
        e.TGEFF, zlo, ndxalo, zhi, ndxbhi = perfiles.anyavg(
            e.MXGLVL, e.GRIDHT, e.GRIDTG, zlo, ndxalo, zhi, ndxbhi)

        ambiz = e.SWEFF / e.UEFF
        ambiy = e.SVEFF / e.UEFF

    if e.L_AWMA_UTURB or e.L_AWMA_UTURBHX:
        # AWMADWNW: zdum < 0 obliga a usar la z previa de WAKE_U
        zdum = -1.0
        _dum, tiz, tiy = wake_u_turb(e, "turb", xinp, zdum, ambiz, ambiy)
    else:
        # código original de AERMOD
        xml = max(0.0, xinp - l)
        xfac = 1.0 / (((xml + rinp) / rinp) ** p.XDECAY - p.DUA_UA)
        tiz = fariz * (1.0 + ((p.WFZ * p.WIZ0 / fariz - 1.0) + p.DUA_UA) * xfac)
        tiy = fariy * (1.0 + ((p.WFY * p.WIY0 / fariy - 1.0) + p.DUA_UA) * xfac)

    # interpolación sobre el tejado
    if xinp < l:
        xfrac = xinp / l
        tiz = ambiz + xfrac * (tiz - ambiz)
        tiy = ambiy + xfrac * (tiy - ambiy)

    # restaura los parámetros efectivos de PRMCALC
    if e.L_AWMA_UTURBHX:
        e.UEFF = p.UEFF_SAVE
        e.SWEFF = p.SWEFF_SAVE
        e.SVEFF = p.SVEFF_SAVE

    return tiz, tiy


def wake_u(e, ldb, x, y, z, dbgunt):
    """WAKE_U: cociente de velocidades u(estela)/u(ambiente) en (x, y, z) relativos a la cara de
    barlovento. Devuelve ``(ubyua, dufac)``."""
    p = e.P
    fmin = 0.01

    # altura y anchura de la cavidad
    zcav, ycav = cavity_ht(p.HB, p.WB, p.XLB, p.RB, p.XLC, p.XLR, p.HR, x)

    # altura y anchura de la estela lejana
    hwake, wwake = wake_dim(x, p.HB, p.WB, p.RB)

    # valores nulos fuera de la estela
    yabs = abs(y)
    ubyua = 1.0
    dufac = 0.0
    if z >= hwake or yabs >= wwake:
        return ubyua, dufac

    if e.L_AWMA_UTURB or e.L_AWMA_UTURBHX:
        # AWMADWNW: nuevo déficit de velocidad (los argumentos 'dum' no se usan con 'vel')
        du_ua, _dum1, _dum2 = wake_u_turb(e, "vel", x, z, 0.0, 0.0)

        # ajuste fuera de la proyección del edificio pero dentro de la estela
        ymin = max(0.5 * p.WB, wwake - p.RB / 3.0)
        ydiff = wwake - ymin
        if yabs > ymin and ydiff > 0.0:
            du_ua = du_ua * (1.0 - (yabs - ymin) / ydiff)

    else:
        # AERMOD reglamentario
        ymin = max(0.5 * p.WB, wwake - p.RB / 3.0)
        du_ua = p.DUA_UA
        ydiff = wwake - ymin
        if yabs > ymin and ydiff > 0.0:
            du_ua = p.DUA_UA * (1.0 - (yabs - ymin) / ydiff)

        # déficit a la distancia x de la cara del edificio
        xml = max(0.0, x - p.XLB)
        du_ua = du_ua * ((xml + p.RB) / p.RB) ** (-p.XDECAY)

    # interpolación lineal sobre el tejado
    if x < p.XLB:
        xfrac = x / p.XLB
        du_ua = xfrac * du_ua

    # factor de velocidad en lo alto de la cavidad
    ucbyua = max(0.0, (1.0 - 2.0 * hwake * du_ua / (hwake + zcav)))

    # gradiente del factor (cero bajo ZCAV)
    dufac = 0.0
    if z > zcav:
        dufac = (1.0 - ucbyua) / (hwake - zcav)

    # factor de velocidad a la altura z (con FMIN como mínimo)
    zz = min(z, hwake)
    ubyua = max(fmin, (ucbyua + dufac * (zz - zcav)))

    # (depuración omitida)

    return ubyua, dufac


def wake_u_turb(e, scope, xinp, znew, ambiz, ambiy):
    """WAKE_U_TURB (AWMADWNW): déficit de velocidad y, con scope 'turb', intensidades de
    turbulencia en la estela. Devuelve ``(du_ua, tiz, tiy)``; con scope 'vel' tiz y tiy son None
    (el original no los asigna). Variables con SAVE (z, zvel_sav) en ``e.PRM_WUT_Z`` y ``e.PRM_WUT_ZVEL``."""
    p = e.P
    hb = p.HB
    wb = p.WB
    hr = p.HR
    xlb = p.XLB

    # constantes según el tipo de edificio
    if e.L_RECT_BLDG:
        # edificios rectangulares
        vufac = 0.294
        svfac = 0.320
        swfac = 0.290
        au = 0.500
        asv = 0.700
        asw = 0.650
        nu = 0.000
        nsv = 0.356
        nsw = 0.336
        bu = 3.494
        ru = 1.667
        lrudfac = 1.135
        lrsvfac = 1.349
        lrswfac = 1.794
        hwminu = 0.449
        hwminsv = 0.200
        hwminsw = 0.375
        hlminu = 0.753
        hlminsv = 0.321
        hlminsw = 0.308
        hwmaxu = 3.00
        hwmaxsv = 3.00
        hwmaxsw = 3.00
        hlmaxu = 3.00
        hlmaxsv = 3.00
        hlmaxsw = 3.00
    elif e.L_STRMLN_BLDG:
        # edificios aerodinámicos
        vufac = 0.294
        svfac = 0.225
        swfac = 0.225
        au = 0.400
        asv = 0.550
        asw = 0.450
        nu = 0.631
        nsv = 0.477
        nsw = 0.570
        bu = 2.113
        ru = 1.796
        lrudfac = 0.563
        lrsvfac = 0.971
        lrswfac = 0.640
        hwminu = 0.449
        hwminsv = 0.375
        hwminsw = 0.375
        hlminu = 0.753
        hlminsv = 0.308
        hlminsw = 0.308
        hwmaxu = 3.00
        hwmaxsv = 3.00
        hwmaxsw = 3.00
        hlmaxu = 3.00
        hlmaxsv = 3.00
        hlmaxsw = 3.00
    else:
        # el original dejaría las constantes sin definir
        raise NoTraducido("WAKE_U_TURB sin L_RECT_BLDG ni L_STRMLN_BLDG")

    # constantes adicionales Bsv, Bsw, rsv, rsw
    if e.L_RECT_BLDG:
        absv = 0.018571
        bbsv = -1.10574
        cbsv = 18.30949
        absw = 0.045142
        bbsw = -2.1585
        cbsw = 29.33697
        arsv = -0.00124
        brsv = 0.033975
        crsv = 1.431187
        arsw = 0.000155
        brsw = -0.00626
        crsw = 1.562781
        iy0 = p.SV30 / p.U30 * 100.0
        if iy0 > 29.2:
            iy0 = 29.2
        if iy0 < 5.0:
            iy0 = 5.0
        iz0 = p.SW30 / p.U30 * 100.0
        if iz0 > 18.6:
            iz0 = 18.6
        if iz0 < 2.0:
            iz0 = 2.0
        bsv = absv * (iy0 * iy0) + bbsv * iy0 + cbsv
        bsw = absw * (iz0 * iz0) + bbsw * iz0 + cbsw
        rsv = arsv * (iy0 * iy0) + brsv * iy0 + crsv
        rsw = arsw * (iz0 * iz0) + brsw * iz0 + crsw
    else:
        absv = 0.008223
        bbsv = -0.42265
        cbsv = 9.330299
        absw = 0.092864
        bbsw = -3.68931
        cbsw = 39.21321
        arsv = 0.000861
        brsv = 0.004194
        crsv = 1.385942
        arsw = 0.004627
        brsw = -0.15270
        crsw = 2.939305
        iy0 = p.SV30 / p.U30 * 100.0
        iz0 = p.SW30 / p.U30 * 100.0
        bsv = absv * (iy0 * iy0) + bbsv * iy0 + cbsv
        bsw = absw * (iz0 * iz0) + bbsw * iz0 + cbsw
        rsv = arsv * (iy0 * iy0) + brsv * iy0 + crsv
        rsw = arsw * (iz0 * iz0) + brsw * iz0 + crsw

    # valor de z: con 'vel' el de entrada; con 'turb' el previo o ZEFF_PRM2 (SAVE)
    if scope == "vel":
        z = znew
        e.PRM_WUT_Z = z
        e.PRM_WUT_ZVEL = znew
    elif scope == "turb":
        z = min(e.PRM_WUT_ZVEL, p.ZEFF_PRM2)

        # AWMA: con la llamada desde WAKE_DFSN2, altura del penacho en xinp
        if e.L_AWMA_UTURBHX and p.DFSN2CALL:
            if xinp < p.XTR_SAV[p.P2MXNTR]:
                zplm = numgrad(xinp, p.XTR_SAV, p.ZTR_SAV, p.P2MXNTR)
                z = zplm
            else:
                zplm = p.ZTR_SAV[p.P2MXNTR]
                z = zplm
        e.PRM_WUT_Z = z
    else:
        # error de programación (el original escribe en pantalla con PRINT * y para)
        e.pantalla.w(["  Improper u/turb scope in wake_u_turb",
                      '   - must be "vel" or "turb" (lower case)'])
        raise Parada()

    # du_ua para wake_u y wake_turb
    # Ec. (11)
    xml = max(0.0, xinp - xlb)
    eps = xml + hb

    # Ec. (8a)
    hwlimu = hb / wb
    if hwlimu < hwminu:
        hwlimu = hwminu
    if hwlimu > hwmaxu:
        hwlimu = hwmaxu
    # Ec. (8b)
    hllimu = hb / xlb
    if hllimu < hlminu:
        hllimu = hlminu
    if hllimu > hlmaxu:
        hllimu = hlmaxu

    # Ec. (7a)
    a1 = 1.0 / hwlimu
    a2 = (1.0 / hllimu ** 0.3) * (1.0 + 0.24 / hwlimu)
    xlrud = 1.8 * a1 / a2

    # Ec. (10a)
    xiud_hb = max((lrudfac * xlrud + 1.0), eps / hb)

    # Ec. (5)
    a1 = xiud_hb * hwlimu ** (2.0 / 3.0)
    a2 = hllimu ** (-nu)
    udmax = bu * (a1 * a2) ** (-ru)

    # Ec. (4a)
    zudmax_hb = au * (hr / hb) ** 1.5

    # Ec. (2)
    if z / hb >= zudmax_hb:
        t = zudmax_hb - z / hb
        a1 = t * t
        a2 = (vufac * vufac) * xiud_hb
        du_ua = udmax * math.exp(-a1 / a2)
    else:
        du_ua = udmax
    # (depuración omitida)

    # con 'vel' se sale aquí
    if scope == "vel":
        return du_ua, 0.0, 0.0

    # Ec. (9a1)
    hwlimsw = hb / wb
    if hwlimsw < hwminsw:
        hwlimsw = hwminsw
    if hwlimsw > hwmaxsw:
        hwlimsw = hwmaxsw
    # Ec. (9a2)
    hllimsw = hb / xlb
    if hllimsw < hlminsw:
        hllimsw = hlminsw
    if hllimsw > hlmaxsw:
        hllimsw = hlmaxsw

    # Ec. (9b1)
    hwlimsv = hb / wb
    if hwlimsv < hwminsv:
        hwlimsv = hwminsv
    if hwlimsv > hwmaxsv:
        hwlimsv = hwmaxsv
    # Ec. (9b2) (el original compara con los límites de SW: se conserva)
    hllimsv = hb / xlb
    if hllimsv < hlminsw:
        hllimsv = hlminsv
    if hllimsv > hlmaxsw:
        hllimsv = hlmaxsv

    # Ec. (7b)
    a1 = 1.0 / hwlimsw
    a2 = (1.0 / hllimsw ** 0.3) * (1.0 + 0.24 / hwlimsw)
    xlrsw = 1.8 * a1 / a2
    # Ec. (7c)
    a1 = 1.0 / hwlimsv
    a2 = (1.0 / hllimsv ** 0.3) * (1.0 + 0.24 / hwlimsv)
    xlrsv = 1.8 * a1 / a2

    # Ec. (10b)
    xisw_hb = max((lrswfac * xlrsw + 1.0), eps / hb)
    # Ec. (10c)
    xisv_hb = max((lrsvfac * xlrsv + 1.0), eps / hb)

    # Ec. (6a)
    a1 = xisw_hb * hwlimsw ** (2.0 / 3.0)
    a2 = hllimsw ** (-nsw)
    swmaxx = bsw * (a1 * a2) ** (-rsw)
    # Ec. (6b)
    a1 = xisv_hb * hwlimsv ** (2.0 / 3.0)
    a2 = hllimsv ** (-nsv)
    svmaxx = bsv * (a1 * a2) ** (-rsv)

    # Ec. (4b)
    zsw_hb = asw * (hr / hb) ** 1.5
    zsv_hb = asv * (hr / hb) ** 1.5

    # Ec. (3a)
    t = zsw_hb - z / hb
    a1 = t * t
    a2 = (swfac * swfac) * xisw_hb
    if z / hb >= zsw_hb:
        sw = swmaxx * math.exp(-a1 / a2)
    else:
        sw = swmaxx
    # Ec. (3b)
    t = zsv_hb - z / hb
    a1 = t * t
    a2 = (svfac * svfac) * xisv_hb
    if z / hb >= zsv_hb:
        sv = svmaxx * math.exp(-a1 / a2)
    else:
        sv = svmaxx

    # límites de la mejora de turbulencia (D116)
    du_ua = min(du_ua, 0.9)
    # Ec. (1a)
    a1 = (1.0 + sw) / (1.0 - du_ua)
    tiz = ambiz * min(18.0, a1)
    tiz = min(0.9, tiz)
    # Ec. (1b)
    a1 = (1.0 + sv) / (1.0 - du_ua)
    tiy = ambiy * min(6.0, a1)
    tiy = min(0.9, tiy)

    # (depuración omitida)

    return du_ua, tiz, tiy


def wake_xa(e, l, rinp):
    """WAKE_XA: distancias desde la cara de barlovento a las que la turbulencia de la estela
    iguala la ambiental, limitadas a XBYRMAX escalas R. Devuelve ``(xaz, xay)``."""
    p = e.P
    ambiz = e.SWEFF / e.UEFF
    ambiy = e.SVEFF / e.UEFF

    fariz = min(p.WIZ0, ambiz)
    fariy = min(p.WIY0, ambiy)

    # intensidad en el punto de transición
    farizt = max(ambiz, p.AFAC * fariz)
    fariyt = max(ambiy, p.AFAC * fariy)

    x0byr = l / rinp - 1.0

    xaz = x0byr + _rpot0(p.DUA_UA + (p.WFZ * p.WIZ0 - fariz * (1.0 - p.DUA_UA)) /
                        (farizt - fariz), p.XDECAYI)

    xay = x0byr + _rpot0(p.DUA_UA + (p.WFY * p.WIY0 - fariy * (1.0 - p.DUA_UA)) /
                        (fariyt - fariy), p.XDECAYI)

    # límite de las distancias
    xbyr = l / rinp + p.XBYRMAX
    xaz = rinp * min(xbyr, xaz)
    xay = rinp * min(xbyr, xay)

    if e.PRIMEDBG:
        depura.wake_xa(e, ambiz, ambiy, farizt, fariyt, xaz, xay)

    return xaz, xay


def wake_xa2(e, l, rinp):
    """WAKE_XA2: como WAKE_XA pero sin limitar a XBYRMAX escalas R. Devuelve ``(xaz, xay)``."""
    p = e.P
    ambiz = e.SWEFF / e.UEFF
    ambiy = e.SVEFF / e.UEFF

    fariz = min(p.WIZ0, ambiz)
    fariy = min(p.WIY0, ambiy)

    farizt = max(ambiz, p.AFAC * fariz)
    fariyt = max(ambiy, p.AFAC * fariy)

    x0byr = l / rinp - 1.0

    xaz = x0byr + _rpot0(p.DUA_UA + (p.WFZ * p.WIZ0 - fariz * (1.0 - p.DUA_UA)) /
                        (farizt - fariz), p.XDECAYI)

    xay = x0byr + _rpot0(p.DUA_UA + (p.WFY * p.WIY0 - fariy * (1.0 - p.DUA_UA)) /
                        (fariyt - fariy), p.XDECAYI)

    xaz = rinp * xaz
    xay = rinp * xay

    return xaz, xay


def wake_dim(x, h, w, r):
    """WAKE_DIM: altura y semianchura de la estela a la distancia x de la cara de barlovento.
    Devuelve ``(hwake, wwake)``. Sin globales (THIRD es local)."""
    cwkht = 1.2
    third = 1.0 / 3.0

    xbyr = x / r
    # (x < 0 da NaN en el original; solo se usa si xbyr > 0)
    xbyr3rd = _rpot0(xbyr, third)

    # ajuste a la altura del edificio en x = 0
    t = h / (cwkht * r)
    xpbyr = -(t * t * t)
    dxbyr = xbyr - xpbyr

    hwake = 0.0
    if xbyr > 0.0:
        hwake = cwkht * r * dxbyr ** third

    # semianchura (ajuste empírico a los datos de túnel de Snyder)
    wwake = 0.0
    if xbyr > 0.0:
        wwake = 0.5 * w + (third * r) * xbyr3rd

    return hwake, wwake


def wake_sig(x, xd, xold, turbz, turby, szold, syold, h, w, r, zk, yk):
    """WAKE_SIG: sigmas y d(sigma)/dx en la estela al final de un paso pequeño. zk, yk son de
    entrada/salida (constantes de la transición FDP → difusividad). Devuelve
    ``(zk, yk, sz, sy, dsz)``. Sin globales."""
    htwake, hwwake = wake_dim(x, h, w, r)

    # anchura total de la estela para la difusividad lateral
    fwwake = 2.0 * hwwake

    delx = x - xold
    xstepi = 1.0 / delx
    if x < xd:
        # forma FDP pura
        dsz = turbz
        sz = szold + delx * turbz
        sy = syold + delx * turby
    elif xold > xd:
        # difusividad de la estela pura
        dsz2 = zk * turbz * htwake
        dsy2 = yk * turby * fwwake
        sz = math.sqrt(szold * szold + delx * dsz2)
        sy = math.sqrt(syold * syold + delx * dsy2)
        dsz = (sz - szold) * xstepi
    else:
        # transición de FDP a difusividad: hasta el final de la FDP
        delx = xd - xold
        sigzd = szold + delx * turbz
        sigyd = syold + delx * turby
        zk = 2.0 * sigzd / htwake
        yk = 2.0 * sigyd / fwwake
        # más allá del final de la FDP
        delx = x - xd
        dsz2 = zk * turbz * htwake
        dsy2 = yk * turby * fwwake
        sz = math.sqrt(sigzd * sigzd + delx * dsz2)
        sy = math.sqrt(sigyd * sigyd + delx * dsy2)
        dsz = (sz - szold) * xstepi

    return zk, yk, sz, sy, dsz


def wake_dbg(e, io, ntr, xtr, ytr, ztr, rtr, nobid, hstack):
    """WAKE_DBG: informe de depuración de PRIME (DEBUGOPT PRIME) a la unidad io. Además de las
    escrituras tiene efectos laterales (WAKE_XSIG → SIGYPR/SIGZPR fijan SYAMB, SZAMB, SZAS,
    SZSURF; WAKE_U → variables con SAVE de WAKE_U_TURB). Solo se llama desde Python (depura)."""
    from .formato import fwrite, lwrite
    p = e.P
    ldb = False
    rt2bypi = 0.797884560802866
    f101 = "(1x,7f7.1,2f7.3,f7.1,f7.3,i4,2f7.1)"
    out = []

    def lw(*it):
        out.extend(lwrite(*it))

    lw()
    lw("------------------------------------------------")
    lw("PRIME Module Results for Current Source and Hour")
    lw("          (all lengths in meters)")
    lw("------------------------------------------------")
    lw()
    out.extend(fwrite("('     XB      X      Z   Hwake   Hcav    Sz     S','y    Ufac  dUfac  R->Sz  dRdx  Pos  "
                      "Szcav  Sycav')"))
    lw()
    # DBDUW sin asignar en el original si XB < 0 (valor de la llamada anterior)
    dbduw = getattr(e, "_prm_dbduw", 0.0)

    # inicio de la cavidad a barlovento de la fuente
    if p.XCAV[1] < 0.0:
        dbx = p.XCAV[1]
        dby = ytr[1]
        dbz = 0.0
        dbsz = dbsy = dbhw = dbhc = dbrsz = 0.0
        dbuw = 1.0
        ipositn = 4
        xb = dbx - p.XBADJ
        yb = dby - p.YBADJ
        zb = dbz
        dbxb = xb
        dbszc = p.SZCAV[1]
        dbsyc = p.SYCAV[1]
        dbdrdx = 0.0
        if xb >= 0.0:
            dbhw, _dbww = wake_dim(xb, p.HB, p.WB, p.RB)
            dbhc, _dbwc = cavity_ht(p.HB, p.WB, p.XLB, p.RB, p.XLC, p.XLR, p.HR, xb)
            ipositn = position(e, xb, yb, zb)
            dbuw = 1.0
            if ipositn < 4:
                dbuw, dbduw = wake_u(e, ldb, xb, yb, zb, io)
            else:
                dbduw = 0.0
        out.extend(fwrite(f101, dbxb, dbx, dbz, dbhw, dbhc, dbsz, dbsy, dbuw, dbduw, dbrsz, dbdrdx, ipositn,
                          dbszc, dbsyc))

    # punto de la fuente
    dbx = 0.0
    dby = ytr[1]
    dbz = hstack
    dbhw = dbhc = dbrsz = 0.0
    dbuw = 1.0
    ipositn = 4
    rise = dbz - hstack
    xb = dbx - p.XBADJ
    yb = dby - p.YBADJ
    zb = dbz
    dbxb = xb
    xzero = 0.001
    dbsz, dbsy, dbszc, dbsyc = wake_xsig(e, xzero, hstack, rise, nobid)
    dbdrdx = wake_drdx(e, dbx)
    if xb >= 0.0:
        dbhw, _dbww = wake_dim(xb, p.HB, p.WB, p.RB)
        dbhc, _dbwc = cavity_ht(p.HB, p.WB, p.XLB, p.RB, p.XLC, p.XLR, p.HR, xb)
        ipositn = position(e, xb, yb, zb)
        dbuw = 1.0
        if ipositn < 4:
            dbuw, dbduw = wake_u(e, ldb, xb, yb, zb, io)
        else:
            dbduw = 0.0
    else:
        dbduw = 0.0
    out.extend(fwrite(f101, dbxb, dbx, dbz, dbhw, dbhc, dbsz, dbsy, dbuw, dbduw, dbrsz, dbdrdx, ipositn,
                      dbszc, dbsyc))

    # puntos de la trayectoria
    for it in range(1, ntr + 1):
        dbx = xtr[it]
        dby = ytr[it]
        dbz = ztr[it]
        dbrsz = rtr[it] * rt2bypi
        dbhw = dbhc = 0.0
        dbuw = 1.0
        ipositn = 4
        rise = dbz - hstack
        xb = dbx - p.XBADJ
        yb = dby - p.YBADJ
        zb = dbz
        dbxb = xb
        dbsz, dbsy, dbszc, dbsyc = wake_xsig(e, dbx, hstack, rise, nobid)
        dbdrdx = wake_drdx(e, dbx)
        if xb >= 0.0:
            dbhw, _dbww = wake_dim(xb, p.HB, p.WB, p.RB)
            dbhc, _dbwc = cavity_ht(p.HB, p.WB, p.XLB, p.RB, p.XLC, p.XLR, p.HR, xb)
            ipositn = position(e, xb, yb, zb)
            dbuw = 1.0
            if ipositn < 4:
                dbuw, dbduw = wake_u(e, ldb, xb, yb, zb, io)
            else:
                dbduw = 0.0
        else:
            dbduw = 0.0
        out.extend(fwrite(f101, dbxb, dbx, dbz, dbhw, dbhc, dbsz, dbsy, dbuw, dbduw, dbrsz, dbdrdx, ipositn,
                          dbszc, dbsyc))
    lw()
    e._prm_dbduw = dbduw
    if io not in e.U:
        e.abrir_salida(io, "fort.%d" % io)
    e.U[io].w(out)


def wake_cav0(e, sycapt):
    """WAKE_CAV0: sigmas iniciales de la fuente situada en el suelo de la cavidad. sycapt:
    sigma-y del penacho donde la cavidad captura la masa. Devuelve ``(szcav0, sycav0)``."""
    p = e.P
    rt2pi = 2.50662827463100
    rt2bypi = 0.797884560802866

    # anchura equivalente de sombrero de copa, limitada a la del edificio
    wcapt = min(rt2pi * sycapt, p.WB)

    # escala de anchura de la distribución lateral en la cavidad
    wscale = min(p.WB, 3.0 * p.HB)
    wscale = max(wscale, p.THIRD * p.HB)
    wscale = max(wscale, wcapt)

    sycav0 = wscale / rt2pi

    # altura de la cavidad tras el edificio
    if p.XLC < p.XLB:
        # readherencia
        hcav = p.HB
    else:
        hcav = p.HR

    # sigma-z que da en el eje la concentración de la cavidad (Wilson y Britter 1982)
    uratio = p.UB / p.URH
    szcav0 = rt2bypi * uratio * hcav * p.THIRD

    return szcav0, sycav0


def cav_src(e, xr, yr, zr, qc, hc, yrc, zrc, szc, syc):
    """CAV_SRC: datos de las fuentes de la cavidad para un receptor (xr, yr, zr relativos a la
    chimenea). Rellena en su sitio qc, hc, yrc, zrc, szc, syc (índices 1..3; el 1 es de la
    fuente principal y no se toca). Devuelve ``(fqcav0, n1, n2)``."""
    p = e.P
    rt2pi = 2.50662827463100

    # sigmas de la cavidad: primer elemento de las tablas
    szcav0 = p.SZCAV[1]
    sycav0 = p.SYCAV[1]

    fqcav0 = float(p.FQCAV)

    hc[2] = 0.0
    hc[3] = 0.0

    # modo (0: ninguna, 1: "exterior", 2: "interior", 3: ambas)
    mode = 0
    n1 = 0
    n2 = 0

    if p.FQCAV <= 0.0:
        # sin masa en la cavidad
        n1 = 1
        n2 = 1
        for i in range(2, 4):
            qc[i] = 0.0
            yrc[i] = yr
            zrc[i] = zr
            szc[i] = szcav0
            syc[i] = sycav0
    else:
        # receptor relativo al centro de la cara de barlovento
        xrb = xr - p.XBADJ
        yrb = yr - p.YBADJ
        zrb = zr
        ipositn = position(e, xrb, yrb, zrb)

        # zona de transición al final de la cavidad
        x115b = p.XLB + 1.15 * p.XLR
        x85b = p.XLB + 0.85 * p.XLR
        if xrb >= x115b:
            # receptor claramente fuera: solo la fuente "exterior"
            qc[2] = 1.0
            qc[3] = 0.0
            mode = 1
        elif xrb > x85b:
            # mezcla: contribuciones iguales al final de la cavidad
            qc[2] = (xrb - x85b) / (x115b - x85b)
            qc[3] = 1.0 - qc[2]
            mode = 3
        elif xrb > p.XLB:
            # receptor dentro de la cavidad: solo la "interior"
            qc[2] = 0.0
            qc[3] = 1.0
            mode = 2
        else:
            # a barlovento del borde de sotavento: "interior" con masa decreciente
            qc[2] = 0.0
            qc[3] = max(0.0, xrb / p.XLB)
            mode = 2

        if ipositn == 4:
            # fuera de la estela: sin contribución de la cavidad
            mode = 0
            n1 = 1
            n2 = 1
            for i in range(2, 4):
                qc[i] = 0.0
                yrc[i] = yr
                zrc[i] = zr
                szc[i] = szcav0
                syc[i] = sycav0
        else:
            # desplazamiento del receptor respecto al eje del penacho de la cavidad
            wtop = sycav0 * rt2pi
            ybmax = 0.5 * (p.WB - wtop)
            if ybmax <= 0.0:
                # penacho más ancho que el edificio: centrado en él
                yrc[2] = yrb
            else:
                ysb = -p.YBADJ
                if ysb < 0.0:
                    yrc[2] = yrb - max(ysb, -ybmax)
                else:
                    yrc[2] = yrb - min(ysb, ybmax)
            yrc[3] = yrc[2]

            if ipositn <= 2:
                # dentro de la cavidad/edificio: sin fuente principal, receptor en el suelo
                if mode == 3:
                    n1 = 2
                    n2 = 3
                elif mode == 2:
                    n1 = 3
                    n2 = 3
                elif mode == 1:
                    n1 = 2
                    n2 = 2
                for i in range(n1, n2 + 1):
                    zrc[i] = 0.0
                    szc[i] = szcav0
                    syc[i] = sycav0
                if (mode == 1 or mode == 3) and xr > 0.0:
                    _dumz, _dumy, szc[2], syc[2] = wake_xsig(e, xr, hc[2], 0.0, True)
            else:
                # principal y posiblemente las dos de la cavidad
                n1 = 1
                n2 = 3
                # altura del receptor sobre la frontera de la cavidad
                if xrb >= (p.XLB + p.XLR):
                    zrc[2] = zr
                else:
                    zcav, wcav = cavity_ht(p.HB, p.WB, p.XLB, p.RB, p.XLC, p.XLR, p.HR, xrb)
                    zrc[2] = max(0.0, zr - zcav)
                zrc[3] = zrc[2]
                if mode == 2:
                    # sin la fuente "exterior": emisión nula en su casilla
                    qc[2] = 0.0
                    szc[2] = szcav0
                    syc[2] = sycav0
                    szc[3] = szcav0
                    syc[3] = sycav0
                    n2 = 3
                elif mode == 1:
                    # sin la "interior"
                    _dumz, _dumy, szc[2], syc[2] = wake_xsig(e, xr, hc[2], 0.0, True)
                    n2 = 2
                else:
                    # las dos fuentes de la cavidad
                    szc[2] = szcav0
                    syc[2] = sycav0
                    szc[3] = szcav0
                    syc[3] = sycav0
                    if xr >= 0.0:
                        _dumz, _dumy, szc[2], syc[2] = wake_xsig(e, xr, hc[2], 0.0, True)

    # receptor a barlovento de la fuente o toda la masa en la cavidad: sin fuente principal
    if n1 == 1 and (xr <= 0.0 or p.FQCAV == 1.0):
        n1 = 2

    return fqcav0, n1, n2


def wake_fqc(e, ldb, xbi, xtr, ztr, ntr, dbgunt):
    """WAKE_FQC: fracción máxima de la masa del penacho capturada por la cavidad (FQCAV).
    xbi: distancia desde la cara de barlovento a la entrada en la estela; xtr, ztr: trayectoria
    (índices 1..ntr)."""
    p = e.P
    p.FQCAV = 0.0

    # distancias desde la cara de barlovento a evaluar
    xbstart = max(xbi, p.XLB)
    xbend = p.XLB + p.XLR
    xrange_ = 0.99 * (xbend - xbstart)
    yba = abs(p.YBADJ)
    # distancia de la fuente al final de la cavidad
    xend = xbend + p.XBADJ

    # al menos 5 pasos, de 10 m como mucho
    nstep = max(5, int(1.0 + xrange_ / 10.0))
    xstep = xrange_ / float(nstep)

    # fracción bajo HB al final de la cavidad: límite de fractz
    zplm = numgrad(xend, xtr, ztr, ntr)
    sz, sy, szc, syc = wake_xsig(e, xend, p.HB, 0.0, True)
    fractz0 = frgauss(zplm, sz, p.HB, -p.HB)
    xmax = 0.0
    fzmax = 0.0

    for is_ in range(0, nstep + 1):
        xb = xbstart + float(is_) * xstep
        x = xb + p.XBADJ
        zplm = numgrad(x, xtr, ztr, ntr)
        zcav, ycav = cavity_ht(p.HB, p.WB, p.XLB, p.RB, p.XLC, p.XLR, p.HR, xb)
        sz, sy, szc, syc = wake_xsig(e, x, zplm, 0.0, True)
        fractz = frgauss(zplm, sz, zcav, -zcav)
        fracty = frgauss(yba, sy, ycav, -ycav)
        fz = min(fractz, fractz0)
        fract = fz * fracty
        if fract > p.FQCAV:
            p.FQCAV = float(fract)
            xmax = x
            fzmax = fz

    # fracción máxima que cae linealmente de 1 (85 % de la cavidad) a 0 (final)
    xb85 = p.XLB + 0.85 * p.XLR
    if xbstart > xb85:
        fq85 = max(0.0, 1.0 - (xbstart - xb85) / (xbend - xb85))
        p.FQCAV = min(p.FQCAV, fq85)

    if ldb:
        depura.wake_fqc(e, dbgunt, xbi, xbstart, xbend, xstep, nstep, fractz0, xb85, xmax, fzmax)


def frgauss(hcntr, sigma, h1, h2):
    """FRGAUSS: fracción de una distribución gaussiana entre h1 y h2 (FRACT). Sin globales."""
    sqrt2 = 1.41421356237310
    small = 1.0e-5
    # evita problemas con sigmas muy pequeñas
    s = sqrt2 * max(sigma, small)

    z1 = (h1 - hcntr) / s
    z2 = (h2 - hcntr) / s

    fract = 0.5 * abs(erfdif(z1, z2))
    return fract


def erfdif(x1, x2):
    """ERFDIF (FUNCTION): erf(x1) - erf(x2) evitando errores de redondeo. Sin globales."""
    erfdif_ = 0.0
    if x1 == x2:
        return erfdif_                                             # 40
    if (x1 * x2) <= 0.0:
        return fnerf(x1) - fnerf(x2)                               # 50
    xtest = abs(x2)
    if abs(x1) < xtest:
        xtest = abs(x1)
    if xtest >= 9.15:
        return erfdif_                                             # 40
    if xtest < 0.47:
        return fnerf(x1) - fnerf(x2)                               # 50
    # solo se llega con x1 y x2 del mismo signo
    isign = 1
    xx1 = x1
    xx2 = x2
    if not (x1 > 0.0):
        isign = -1
        xx1 = -xx1
        xx2 = -xx2
    # 30
    erfcx1 = 0.0
    erfcx2 = 0.0
    if xx1 < 9.15:
        erfcx1 = fnerfc(xx1)
    if xx2 < 9.15:
        erfcx2 = fnerfc(xx2)
    erfdif_ = float(isign) * (erfcx2 - erfcx1)
    if erfcx2 == erfcx1:
        erfdif_ = 0.0
    return erfdif_


_A_ERF = (0.0, 0.0000430638, 0.0002765672, 0.0001520143,
          0.0092705272, 0.0422820123, 0.0705230784)


def fnerf(xx):
    """FNERF (FUNCTION): función de error, aproximación de Hastings. Sin globales."""
    a = _A_ERF
    xcut = 3.919206

    x = abs(xx)
    if x > xcut:
        t16 = 0.0
    else:
        t = (((((((((a[1] * x + a[2]) * x) + a[3]) * x) + a[4]) *
                x) + a[5]) * x) + a[6]) * x

        t = 1.0 / (t + 1.0)

        t16 = t * t * t * t
        t16 = t16 * t16 * t16 * t16

    if xx > 0.0:
        return 1.0 - t16
    else:
        return t16 - 1.0


def fnerfc(xx):
    """FNERFC (FUNCTION): función de error complementaria (Hastings, con la expresión
    asintótica para x grande). Sin globales."""
    a = _A_ERF
    xcutl = -3.919206
    xcuth = 13.306
    rtpii = 0.564189583547756

    if xx > xcuth:
        return 0.0

    elif xx < xcutl:
        return 2.0

    elif xx > 2.79:
        x = abs(xx)
        z = 1.0 / x
        return rtpii * z * math.exp(-x * x) * (1.0 - 0.5 * z * z * (1.0 - 1.5 * z * z))

    else:
        x = abs(xx)
        t = (((((((((a[1] * x + a[2]) * x) + a[3]) * x) + a[4]) *
                x) + a[5]) * x) + a[6]) * x

        t = 1.0 / (t + 1.0)

        # t**16 para x > 0
        t16 = t * t * t * t
        t16 = t16 * t16 * t16 * t16

        if xx > 0.0:
            return t16
        else:
            return 2.0 - t16


def wake_xsig(e, x, hstk, rise, nobid):
    """WAKE_XSIG: sigmas en la estela por interpolación en las tablas, o con las curvas
    ambientales (BID o fuente virtual) fuera de ellas. x: distancia desde la fuente; hstk:
    altura física; rise: sobreelevación gradual; nobid: sin BID. Devuelve ``(sz, sy, szc, syc)``
    (principal y cavidad)."""
    p = e.P
    nwak = p.NWAK
    xwak = p.XWAK

    # fuente principal
    if x <= 0.0:
        # valores nulos (no deberían usarse)
        sz = 0.0
        sy = 0.0
    elif nwak <= 1:
        # penacho no alterado por la estela: curvas ambientales
        sz = sigzpr(e, x, hstk + rise)
        sy = sigypr(e, x, hstk + rise)
        if not nobid:
            t = rise / 3.5
            bidsq = t * t
            sz = math.sqrt(sz * sz + bidsq)
            sy = math.sqrt(sy * sy + bidsq)
    elif x < xwak[1]:
        # a barlovento de la región de la estela: curvas ambientales
        sz = sigzpr(e, x, hstk + rise)
        sy = sigypr(e, x, hstk + rise)
        if not nobid:
            t = rise / 3.5
            bidsq = t * t
            sz = math.sqrt(sz * sz + bidsq)
            sy = math.sqrt(sy * sy + bidsq)
    elif x > xwak[nwak]:
        # más allá de la transición al crecimiento ambiental: fuente virtual
        sz = sigzpr(e, x, hstk + rise)
        sy = sigypr(e, x, hstk + rise)
        sz = math.sqrt(sz * sz + p.VSIGZ * p.VSIGZ)
        sy = math.sqrt(sy * sy + p.VSIGY * p.VSIGY)
    else:
        # dentro de la tabla
        nwkm1 = nwak - 1
        sz = p.SZWAK[1]
        sy = p.SYWAK[1]
        for i in range(nwkm1, 0, -1):
            if x >= xwak[i]:
                ip1 = i + 1
                fac = (xwak[ip1] - x) / (xwak[ip1] - xwak[i])
                sz = p.SZWAK[ip1] - (p.SZWAK[ip1] - p.SZWAK[i]) * fac
                sy = p.SYWAK[ip1] - (p.SYWAK[ip1] - p.SYWAK[i]) * fac
                break                                              # GOTO 50

    # 50: fuente de la cavidad
    ncav = p.NCAV
    xcav = p.XCAV
    if ncav <= 1:
        # sin contribución de la cavidad (valores iniciales)
        szc = p.SZCAV[1]
        syc = p.SYCAV[1]
    elif x < xcav[1]:
        # a barlovento de la región de la cavidad (valores iniciales)
        szc = p.SZCAV[1]
        syc = p.SYCAV[1]
    elif x > xcav[ncav]:
        # más allá de la transición: curvas ambientales con fuente virtual
        szc = sigzpr(e, x, 0.0)
        syc = sigypr(e, x, 0.0)
        szc = math.sqrt(szc * szc + p.VSIGZC * p.VSIGZC)
        syc = math.sqrt(syc * syc + p.VSIGYC * p.VSIGYC)
    else:
        # dentro de la tabla
        ncvm1 = ncav - 1
        szc = p.SZCAV[1]
        syc = p.SYCAV[1]
        for i in range(ncvm1, 0, -1):
            if x >= xcav[i]:
                ip1 = i + 1
                fac = (xcav[ip1] - x) / (xcav[ip1] - xcav[i])
                szc = p.SZCAV[ip1] - (p.SZCAV[ip1] - p.SZCAV[i]) * fac
                syc = p.SYCAV[ip1] - (p.SYCAV[ip1] - p.SYCAV[i]) * fac
                break

    return float(sz), float(sy), float(szc), float(syc)


def cavity_ht(h, w, l, r, lc, lr, hr, x):
    """CAVITY_HT: altura y semianchura de la envolvente de la cavidad en x. Devuelve
    ``(zcav, ycav)``. Sin globales."""
    zcav = 0.0
    ycav = 0.0

    # sin cavidad a barlovento del edificio ni en L+LR o más allá
    if x >= (l + lr):
        return zcav, ycav
    elif x < 0.0:
        return zcav, ycav

    # frontera x-y de la estela cercana
    if x >= 0.0 and x <= r:
        t = x - r
        ycav = (w / 2.0 + r / 3.0) - (t * t) / (3.0 * r)
    elif x > r and x <= (l + lr):
        t = (x - r) / (l + lr - r)
        ycav = (w / 2.0 + r / 3.0) * math.sqrt(1.0 - t * t)

    # frontera x-z de la estela cercana
    if lc < l:
        # readherencia
        if x >= 0.0 and x <= l:
            zcav = h
        elif x >= l and x <= (l + lr):
            t = (x - l) / lr
            zcav = h * math.sqrt(1.0 - t * t)
    else:
        # sin readherencia
        if x >= 0.0 and x <= 0.5 * r:
            t = x - 0.5 * r
            zcav = hr + 4.0 * (t * t) * (h - hr) / (r * r)
        elif x > 0.5 * r and x <= (l + lr):
            t = (x - 0.5 * r) / (l + lr - 0.5 * r)
            zcav = hr * math.sqrt(1.0 - t * t)

    return zcav, ycav


# ============================================================================ sigmas de PRIME
def sigypr(e, xarg, zarg):
    """SIGYPR: sigma-y ambiental para PRIME. Fija e.SYAMB y devuelve SYOUT (= SYAMB; si no es
    ni estable ni inestable, el SYAMB previo, como el original)."""
    if e.STABLE:
        # estable o emisión por encima de la capa de mezcla convectiva
        svovru = max(e.SVUMIN, e.SVEFF / e.UEFF)
        tyeff = (e.ZIMECH / (156.0 * e.SVEFF)) * (max(zarg, 0.46) / 0.46)
        e.SYAMB = (svovru * xarg) / _rpot0(1.0 + xarg / (2.0 * e.UEFF * tyeff), 0.3)

    elif e.UNSTAB:
        # inestable con la emisión bajo la altura de mezcla
        svovru = max(e.SVUMIN, e.SVEFF / e.UEFF)
        xnodim = svovru * xarg / e.ZI
        denomi = max(zarg, 0.46)
        betalph = max(78.0 * (0.46 / denomi), 0.7)
        e.SYAMB = (svovru * xarg) / _rpot0(1.0 + betalph * xnodim, 0.3)

    return e.SYAMB


def sigzpr(e, xarg, zarg, szout=0.0):
    """SIGZPR: sigma-z ambiental para PRIME. Devuelve SZOUT. En estable fija e.SZAMB, e.SZAS (y
    e.SZSURF vía SZSFCLPR); en inestable, e.SZSURF. Si no es ni estable ni inestable el original
    no asigna SZOUT: se devuelve el argumento opcional ``szout`` (valor previo)."""
    if e.STABLE:
        # tiempo de viaje
        ttravl = xarg / e.UEFF

        # sigma-z de CTDMPLUS: temperatura potencial a la altura ZARG
        ndxzhe = perfiles.locate(e.GRIDHT, 1, e.MXGLVL, zarg)

        if ndxzhe >= 1:
            ptp = perfiles.gintrp(e.GRIDHT[ndxzhe], e.GRIDPT[ndxzhe],
                                  e.GRIDHT[ndxzhe + 1], e.GRIDPT[ndxzhe + 1], zarg)
        else:
            ptp = e.GRIDPT[1]

        bvfrq = _dsqrt(e.G * e.TGEFF / ptp)
        if bvfrq < 1.0e-10:
            bvfrq = 1.0e-10

        # altura para sigma-z
        ztmp = max(zarg, 1.0e-4)

        if e.URBSTAB:
            # término de Brunt-Vaisala nulo en la capa estable urbana
            e.SZAMB = e.SWEFF * ttravl / math.sqrt(1.0 + e.SWEFF * ttravl *
                                                   (1.0 / (0.72 * ztmp)))

        else:
            e.SZAMB = e.SWEFF * ttravl / math.sqrt(1.0 + e.SWEFF * ttravl *
                                                   (1.0 / (0.72 * ztmp) +
                                                    bvfrq / (0.54 * e.SWEFF)))

        if zarg < e.ZI:
            szsfclpr(e, xarg, zarg)

            sigf = min(zarg / e.ZI, 1.0)
            e.SZAS = (1.0 - sigf) * e.SZSURF + sigf * e.SZAMB
        else:
            e.SZAS = e.SZAMB

        szout = e.SZAS

    elif e.UNSTAB:

        if zarg >= 0.1 * e.ZI:
            alphab = 1.0
        else:
            alphab = 0.6 + 0.4 * (zarg / (0.1 * e.ZI))

        szad = alphab * e.SWEFF * xarg / e.UEFF

        szsfclpr(e, xarg, zarg)

        szout = math.sqrt(szad * szad + e.SZSURF * e.SZSURF)

    return float(szout)


def szsfclpr(e, xarg, zarg):
    """SZSFCLPR: término de capa superficial de sigma-z para PRIME (fija e.SZSURF). Solo usa
    MAIN1: THIRD es e.THIRD."""
    if e.UNSTAB and zarg < 0.1 * e.ZI:
        e.SZSURF = (e.BSUBC * (1.0 - 10.0 * (zarg / e.ZI)) *
                    (e.USTAR / e.UEFF) * (e.USTAR / e.UEFF) *
                    (xarg * xarg / abs(e.OBULEN)))

    elif e.STABLE:
        e.SZSURF = ((e.RTOF2 / e.RTOFPI) * e.USTAR * (xarg / e.UEFF) *
                    _rpot0(1.0 + 0.7 * xarg / e.OBULEN, -e.THIRD))

    else:
        e.SZSURF = 0.0
