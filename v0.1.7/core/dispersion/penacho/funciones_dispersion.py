# -*- coding: utf-8 -*-
"""Traducción de AERMOD 26135 (US EPA, dominio público): rutinas numéricas de calc2.f (de EMFACT a
ERFX): factores de emisión y de fondo, distancia a la sobreelevación final, estela, distancias
fuente-receptor, términos laterales y verticales de la distribución gaussiana, meandro, línea de
corriente divisoria (HCRIT), parámetros de la FDP convectiva, decaimiento y fracción bajo HCRIT.

Las rutinas de salida de resultados (SUMVAL en adelante) están en otro módulo.

Rutinas externas que se llaman (firmas asumidas):
  · ``perfiles.gintrp(htbelo, vbelow, htabov, vabove, reqdht)`` → VALUE (GINTRP de metext.f).
  · ``perfiles.locate(parray, lvlblw, lvlabv, value)`` → NDXBLW (LOCATE).
  · ``sigmas.cblprd(e, xarg)`` → None; fija ``e.DHP1`` (CBLPRD de prise.f). Se importa dentro de
    DISTF para no exigir el módulo al importar este.
  · ``e.errhdl(path, modnam, tipo, codigo, msg)`` (ERRHDL de aermod.f).

En CRITDS, para fuentes RLINE/RLINEXT (fuera de alcance) se leen ``e.RL_GRIDWS`` (MAIN1) e
``e.I_ALPHA`` (módulo RLINE_DATA, que debe existir en `e` si hay fuentes de ese tipo).
"""
import math

from . import depura, perfiles
from .formato import fwrite


# ------------------------------------------------------------------------------------------
# Utilidades IEEE: Intel sin trampas de coma flotante devuelve NaN/Inf donde Python lanzaría
# una excepción. Solo se usan donde el original puede llegar a esos casos (CRITDS).
# ------------------------------------------------------------------------------------------
def _div(a, b):
    """División IEEE: ±Inf o NaN al dividir por cero (en vez de ZeroDivisionError)."""
    if b == 0.0:
        if a == 0.0 or a != a:
            return math.nan
        return math.copysign(math.inf, a) * math.copysign(1.0, b)
    return a / b


def _sqrt(x):
    """DSQRT IEEE: NaN para argumentos negativos (en vez de ValueError)."""
    if x >= 0.0:
        return math.sqrt(x)
    return math.nan


def _ndxvar(e, flag):
    """Índice temporal común a EMFACT, BGVAL, OZONVALS y VARYNOXVALS para los indicadores de
    variación MONTH...MHRDOW7 (None si el indicador no es ninguno de ellos)."""
    if flag == "MONTH":
        return e.IMONTH
    if flag == "HROFDY":
        return e.IHOUR
    if flag == "WSPEED":
        return e.IUCAT
    if flag == "SEASON":
        return e.ISEAS
    if flag == "SEASHR":
        return e.IHOUR + (e.ISEAS - 1) * 24
    if flag == "HRDOW":
        return e.IHOUR + (e.IDAY_OF_WEEK - 1) * 24
    if flag == "HRDOW7":
        return e.IHOUR + (e.IDAY_OF_WEEK7 - 1) * 24
    if flag == "SHRDOW":
        return e.IHOUR + (e.ISEAS - 1) * 24 + (e.IDAY_OF_WEEK - 1) * 96
    if flag == "SHRDOW7":
        return e.IHOUR + (e.ISEAS - 1) * 24 + (e.IDAY_OF_WEEK7 - 1) * 96
    if flag == "MHRDOW":
        return e.IHOUR + (e.IMONTH - 1) * 24 + (e.IDAY_OF_WEEK - 1) * 288
    if flag == "MHRDOW7":
        return e.IHOUR + (e.IMONTH - 1) * 24 + (e.IDAY_OF_WEEK7 - 1) * 288
    return None


# ============================================================================ emisión y fondo
def emfact(e, qarg):
    """EMFACT: aplica el factor de emisión variable según QFLAG(ISRC). Fija ``e.QTK`` (si QFLAG no
    es ninguno de los reconocidos, QTK no se toca, como en el original)."""
    isrc = e.ISRC
    flag = e.QFLAG[isrc]
    if flag == "":
        e.QTK = qarg
    elif flag == "HOURLY":
        e.QTK = qarg
    else:
        n = _ndxvar(e, flag)
        if n is not None:
            e.QTK = qarg * float(e.QFACT[n, isrc])


def bgval(e, isect, barg):
    """BGVAL: concentración de fondo variable del sector ISECT, convertida a µg/m3 según POLLUT y
    BACKUNITS. Devuelve BARG (argumento de entrada/salida)."""
    flag = e.BFLAG[isect]
    if flag == "ANNUAL":
        barg = float(e.BACKGRND[1, isect])
    else:
        n = _ndxvar(e, flag)
        if n is not None:
            barg = float(e.BACKGRND[n, isect])

    if e.POLLUT == "NO2":
        if e.BACKUNITS == "PPB":
            barg = barg / e.NO2_PPB
        elif e.BACKUNITS == "PPM":
            barg = barg / e.NO2_PPM
    elif e.POLLUT == "SO2":
        if e.BACKUNITS == "PPB":
            barg = barg / e.SO2_PPB
        elif e.BACKUNITS == "PPM":
            barg = barg / e.SO2_PPM
    elif e.POLLUT == "CO":
        if e.BACKUNITS == "PPB":
            barg = barg * e.CO_PPB
        elif e.BACKUNITS == "PPM":
            barg = barg * e.CO_PPM
    return barg


def ozonvals(e, isect, o3arg):
    """OZONVALS: ozono de fondo variable del sector ISECT en µg/m3. Devuelve O3ARG (entrada/salida)."""
    flag = e.O3FLAG[isect]
    if flag == "ANNUAL":
        o3arg = float(e.O3VARY[1, isect])
    else:
        n = _ndxvar(e, flag)
        if n is not None:
            o3arg = float(e.O3VARY[n, isect])

    if e.OZONEUNITS == "PPB":
        o3arg = o3arg * e.O3_PPB
    elif e.OZONEUNITS == "PPM":
        o3arg = o3arg * e.O3_PPM
    elif e.OZONEUNITS == "UG/M3":
        o3arg = o3arg
    else:
        # unidades por defecto: PPB
        o3arg = o3arg * e.O3_PPB
    return o3arg


def varynoxvals(e, isect, noxarg):
    """VARYNOXVALS: NOx de fondo variable del sector ISECT en µg/m3 (como NO2). Devuelve NOXARG
    (entrada/salida)."""
    flag = e.NOXFLAG[isect]
    if flag == "ANNUAL":
        noxarg = float(e.NOXVARY[1, isect])
    else:
        n = _ndxvar(e, flag)
        if n is not None:
            noxarg = float(e.NOXVARY[n, isect])

    if e.NOXUNITS == "PPB":
        noxarg = noxarg / e.NO2_PPB
    elif e.NOXUNITS == "PPM":
        noxarg = noxarg / e.NO2_PPM
    elif e.NOXUNITS == "UG/M3":
        noxarg = noxarg
    else:
        # unidades por defecto: PPB
        noxarg = noxarg / e.NO2_PPB
    return noxarg


# ============================================================================ sobreelevación
def distf(e):
    """DISTF: distancia a la sobreelevación final (``e.XMAX``) y sobreelevación final
    (``e.DHFAER``). En capa estable urbana puede fijar también ``e.PSUBS``, ``e.HEDHH`` y
    ``e.PPF``; CBLPRD fija ``e.DHP1``."""
    from . import sigmas

    if e.STABLE or (e.UNSTAB and (e.HS >= e.ZI)):
        # distancia a la sobreelevación final
        e.XMAX = e.UP * math.atan2(e.FM * e.BVPRIM, -e.FB) / e.BVPRIM

        # sobreelevación final estable (Ec. 3-113)
        e.DHFAER = 2.66 * (e.FB / (e.BVF * e.BVF * e.UP)) ** e.THIRD
        xln = e.FB / (e.UP * e.USTAR * e.USTAR)
        delhnn = 1.2 * xln ** 0.6 * (e.HSP + 1.2 * xln) ** 0.4
        e.DHFAER = min(e.DHFAER, delhnn)

        # sobreelevación final neutra/convectiva
        if e.FB <= 0.0:
            xmaxn = 4.0 * e.DS * (e.VS + 3.0 * e.UP) * (e.VS + 3.0 * e.UP) / (e.VS * e.UP)
            e.DHFAER = min(e.DHFAER, 3.0 * e.DS * e.VS / e.UP)
        else:
            if e.FB >= 55.0:
                xmaxn = 119.0 * e.FB ** 0.4
            else:
                xmaxn = 49.0 * e.FB ** 0.625
            sigmas.cblprd(e, xmaxn)
            e.DHFAER = min(e.DHFAER, e.DHP1)

        # límite de calma estable
        e.DHFAER = min(e.DHFAER, 4.0 * e.FB ** 0.25 / (e.BVF * e.BVF) ** 0.375)

        # DHFAER "original" para los casos URBSTAB
        dhfsav = e.DHFAER

        # capa estable urbana: penetración parcial por encima de ZI
        if e.URBSTAB:
            if e.HSP + e.DHFAER >= e.ZI and e.HSP < e.ZI:
                # cuadrado de la frecuencia de Brunt-Vaisala en ZI
                bvzi2 = (e.G / e.PTATZI) * 0.005

                # PsubS, Ec. 26b
                e.PSUBS = e.FB / (e.UP * bvzi2 * (e.ZI - e.HSP) * (e.ZI - e.HSP) * (e.ZI - e.HSP))

                # cociente delta(He)/delta(Hh), Ec. 25 (17.576 = 2.6**3; 0.296296 = (2/3)**3)
                e.HEDHH = (17.576 * e.PSUBS + 0.296296) ** e.THIRD

                # fracción penetrada
                if e.HEDHH < (2.0 * e.THIRD):
                    e.PPF = 0.0
                elif e.HEDHH > 2.0:
                    e.PPF = 1.0
                else:
                    e.PPF = 1.5 - (1.0 / e.HEDHH)

                if e.PPF > 0.0:
                    if e.PPF == 1.0:
                        e.DHFAER = e.HEDHH * (e.ZI - e.HSP)
                    else:
                        e.DHFAER = 0.75 * (e.ZI - e.HSP) * e.HEDHH + 0.5 * (e.ZI - e.HSP)
                else:
                    e.DHFAER = dhfsav

    else:
        # penacho convectivo
        if e.FB <= 0.0:
            e.XMAX = 4.0 * e.DS * (e.VS + 3.0 * e.UP) * (e.VS + 3.0 * e.UP) / (e.VS * e.UP)
            e.DHFAER = 3.0 * e.DS * e.VS / e.UP
        else:
            if e.FB >= 55.0:
                e.XMAX = 119.0 * e.FB ** 0.4
            else:
                e.XMAX = 49.0 * e.FB ** 0.625
            sigmas.cblprd(e, e.XMAX)
            e.DHFAER = e.DHP1


# ============================================================================ estela y distancias
def wakflg(e):
    """WAKFLG: dimensiones del edificio del sector IFVSEC y bandera de estela. Fija ``e.DSBH``,
    ``e.DSBW``, ``e.DSBL``, ``e.XADJ``, ``e.YADJ``, ``e.B_SUBS``, ``e.B_SUBL``, ``e.RSCALE`` (si
    IFVSEC <= NSEC) y ``e.WAKE``."""
    isrc = e.ISRC
    ifv = e.IFVSEC
    if ifv <= e.NSEC:
        e.DSBH = float(e.ADSBH[ifv, isrc])
        e.DSBW = float(e.ADSBW[ifv, isrc])

        # PRIME
        e.DSBL = float(e.ADSBL[ifv, isrc])
        e.XADJ = float(e.ADSXADJ[ifv, isrc])
        e.YADJ = float(e.ADSYADJ[ifv, isrc])
        e.B_SUBS = min(e.DSBH, e.DSBW)
        e.B_SUBL = max(e.DSBH, e.DSBW)
        e.B_SUBL = min(e.B_SUBL, 8.0 * e.B_SUBS)
        e.RSCALE = e.B_SUBS ** (2.0 * e.THIRD) * e.B_SUBL ** e.THIRD

    if e.DSBH <= 1.0e-5 or e.DSBW <= 1.0e-5:
        # sin edificio para esta fuente
        e.WAKE = False
    else:
        # con edificio: PRIME decide si hay downwash (el aviso GEP 305 está suprimido en el original)
        e.WAKE = True


def xydist(e, indx):
    """XYDIST: coordenadas del receptor INDX y distancias a favor (``e.X``) y transversal al viento
    (``e.Y``), radial (``e.DISTR``) y altura del receptor sobre la base de la fuente (``e.ZRT``).
    Fija también ``e.XR``, ``e.YR``, ``e.ZELEV``, ``e.ZHILL`` y ``e.ZFLAG``."""
    e.XR = float(e.AXR[indx])
    e.YR = float(e.AYR[indx])
    e.ZELEV = float(e.AZELEV[indx])
    e.ZHILL = float(e.AZHILL[indx])
    e.ZFLAG = float(e.AZFLAG[indx])

    e.X = -((e.XR - e.XS) * e.WDSIN + (e.YR - e.YS) * e.WDCOS)
    e.Y = (e.XR - e.XS) * e.WDCOS - (e.YR - e.YS) * e.WDSIN

    e.DISTR = math.sqrt(e.X * e.X + e.Y * e.Y)

    if e.L_FLATSRC[e.ISRC]:
        e.ZRT = e.ZFLAG
    else:
        e.ZRT = e.ZELEV - e.ZS + e.ZFLAG

    # modo SCREEN: cálculo sobre el eje del penacho
    if e.SCREEN:
        e.X = e.DISTR
        e.Y = 0.0


def fterm(e):
    """FTERM: término F ligado a la fracción de penacho bajo HCRIT. Fija ``e.FOPT``."""
    e.FOPT = 0.5 * (1.0 + e.PHEE)


def fyplm(e, syarg):
    """FYPLM: término lateral gaussiano del penacho coherente (usa ``e.Y``). Devuelve FYOUT."""
    exparg = -(e.Y * e.Y / (2.0 * syarg * syarg))
    if exparg > e.EXPLIM:
        fyout = math.exp(exparg) / (e.SRT2PI * syarg)
    else:
        fyout = 0.0
    return fyout


def fypan(e):
    """FYPAN: término lateral de la componente aleatoria ("pancake"). Devuelve FYOUT."""
    return 1.0 / (e.TWOPI * e.DISTR)


def meandr(e, uef, svef):
    """MEANDR: fracción del penacho en la distribución lateral aleatoria (meandro). Devuelve FRAN.
    Puede emitir los mensajes informativos 494 y 424 (fija ``e.DUMMY``)."""
    # escala de tiempo de la dispersión aleatoria (BIGT en horas)
    tran = e.BIGT * 3600.0

    # se quita la componente SVeff de UEF
    sqrtarg = uef * uef - 2.0 * svef * svef
    if sqrtarg >= 0.01:
        umean = math.sqrt(sqrtarg)
    else:
        umean = 0.1
    totkin = uef * uef
    ttrav = e.DISTR / uef
    sigran = 2.0 * svef * svef + umean * umean * (1.0 - math.exp(-ttrav / tran))
    fran = sigran / totkin

    if e.L_PBAL:
        fran = math.sqrt(fran)

    if e.L_USERFRANMAX and (fran > e.FRANMAX):
        e.DUMMY = fwrite("(I2.2,1X,I2.2,1X,I2.2,1X,I3)", e.IMONTH, e.IDAY, e.IHOUR,
                         min(e.ISRC, 999))[0]
        e.errhdl(e.PATH, "MEANDR", "I", "494", e.DUMMY)

    if e.L_USERFRANMIN and (fran < e.FRANMIN):
        e.DUMMY = fwrite("(I2.2,1X,I2.2,1X,I2.2,1X,I3)", e.IMONTH, e.IDAY, e.IHOUR,
                         min(e.ISRC, 999))[0]
        e.errhdl(e.PATH, "MEANDR", "I", "424", e.DUMMY)

    fran = min(fran, e.FRANMAX)
    fran = max(fran, e.FRANMIN)

    if e.DEBUG:
        depura.meandr(e, svef, uef, umean, ttrav, tran, totkin, sigran, fran)
    return fran


# ============================================================================ HCRIT
def critds(e, hearg):
    """CRITDS: altura de la línea de corriente divisoria para el receptor actual. Fija
    ``e.HCRIT``."""
    isrc = e.ISRC
    zmid = 0.0
    topht = 0.0
    tghc = 0.0
    pthc = 0.0

    # límite superior de la integración: mínimo entre la altura del penacho sobre el receptor y
    # la escala de altura de la colina de AERMAP
    if e.L_FLATSRC[isrc]:
        # fuente en terreno llano
        hhill = 0.0
        e.HCRIT = 0.0
        return
    else:
        hhill = min(e.ZHILL - e.ZS, e.ZELEV - e.ZS + hearg)

    if e.STABLE and e.ELEV and hhill > 0.0:
        ht = e.GRIDHT
        ws = e.GRIDWS
        pt = e.GRIDPT
        tg = e.GRIDTG
        rline = (e.SRCTYP[isrc] == "RLINE") or (e.SRCTYP[isrc] == "RLINEXT")
        if rline:
            rlws = e.RL_GRIDWS
            ia = e.I_ALPHA

        # nivel de la malla inmediatamente inferior a la colina y número de niveles
        ndx4hc = perfiles.locate(ht, 1, e.MXGLVL, hhill)
        nlev = ndx4hc + 1

        # valores en la cima
        if rline:
            uathh = perfiles.gintrp(ht[ndx4hc], rlws[ndx4hc, ia], ht[ndx4hc + 1],
                                    rlws[ndx4hc + 1, ia], hhill)
        else:
            uathh = perfiles.gintrp(ht[ndx4hc], ws[ndx4hc], ht[ndx4hc + 1], ws[ndx4hc + 1], hhill)
        ptathh = perfiles.gintrp(ht[ndx4hc], pt[ndx4hc], ht[ndx4hc + 1], pt[ndx4hc + 1], hhill)
        tgathh = perfiles.gintrp(ht[ndx4hc], tg[ndx4hc], ht[ndx4hc + 1], tg[ndx4hc + 1], hhill)

        ls = [0.0] * (nlev + 1)
        rs = [0.0] * (nlev + 1)
        xn2 = [0.0] * (nlev + 1)

        # lado izquierdo de la Ec. 32 de CTDMPLUS en los niveles de la malla
        for nl in range(1, nlev):
            if rline:
                ls[nl] = 0.5 * rlws[nl, ia] * rlws[nl, ia]
            else:
                ls[nl] = 0.5 * ws[nl] * ws[nl]

        # LS en la cima
        ls[nlev] = 0.5 * uathh * uathh

        # lado derecho de la Ec. 32 con el punto medio de cada capa
        rs[nlev] = 0.0
        for nl in range(nlev - 1, 0, -1):
            if nl < nlev - 1:
                zmid = 0.5 * (ht[nl + 1] + ht[nl])
                pthc = 0.5 * (pt[nl + 1] + pt[nl])
                tghc = 0.5 * (tg[nl + 1] + tg[nl])
                topht = ht[nl + 1]
            elif nl == nlev - 1:
                zmid = 0.5 * (hhill + ht[nl])
                pthc = 0.5 * (ptathh + pt[nl])
                tghc = 0.5 * (tgathh + tg[nl])
                topht = hhill

            # frecuencia de Brunt-Vaisala y lado derecho de la Ec. 32
            xn2[nl] = (e.G / pthc) * tghc
            rs[nl] = rs[nl + 1] + xn2[nl] * ((hhill - zmid) * (topht - ht[nl]))

        # capa más baja en que se cumple la Ec. 32
        it = 1
        for nl in range(nlev, 0, -1):
            if ls[nl] >= rs[nl]:
                it = nl

        # interpolación lineal en la capa: ecuación de segundo grado en HC
        if it > 1:
            if it == nlev:
                wstop = uathh
                htop = hhill
            else:
                if rline:
                    wstop = rlws[it, ia]
                    htop = ht[it]
                else:
                    wstop = ws[it]
                    htop = ht[it]

            ib = it - 1
            hbot = ht[ib]
            if rline:
                dws = (wstop - rlws[ib, ia]) / (htop - hbot)
            else:
                dws = (wstop - ws[ib]) / (htop - hbot)

            dws2 = dws * dws
            n2 = xn2[ib]

            a = 0.5 * (n2 - dws2)
            b = (htop * dws2 - wstop * dws - n2 * hhill)
            c = (n2 * hhill * htop) - 0.5 * (n2 * htop * htop) - \
                0.5 * (dws2 * htop * htop) + wstop * dws * htop - \
                (ls[it] - rs[it])
            b2 = b * b
            ac4 = 4.0 * a * c
            # se evita la raíz de un negativo cuando está cerca de cero
            if _div(b2 - ac4, b2) < 0.0 and _div(b2 - ac4, b2) > -0.001:
                ac4 = b2
            deter = _sqrt(b2 - ac4)
            e.HCRIT = float(_div(-b - deter, 2.0 * a))
        else:
            e.HCRIT = 0.0

    else:
        # colina por debajo de la base de la fuente
        e.HCRIT = 0.0


# ============================================================================ FDP convectiva
def pdf(e):
    """PDF: parámetros de la función de densidad de probabilidad de la capa convectiva."""
    skcalc(e)
    crcalc(e)
    alcalc(e)
    becalc(e)
    aacalc(e)
    bbcalc(e)
    llcalc(e)


def skcalc(e):
    """SKCALC: asimetría de la velocidad vertical. Fija ``e.SKEW``."""
    if e.SURFAC:
        # emisión en la capa superficial
        wbar3 = 1.25 * (e.WSTAR * e.WSTAR * e.WSTAR) * (e.CENTER / e.ZI)
    else:
        wbar3 = 0.125 * (e.WSTAR * e.WSTAR * e.WSTAR)

    e.SKEW = wbar3 / (e.SWEFFD * e.SWEFFD * e.SWEFFD)


def crcalc(e):
    """CRCALC: coeficiente de correlación lagrangiano. Fija ``e.R`` = 2."""
    e.R = 2.0


def alcalc(e):
    """ALCALC: coeficiente ALPHPD de la FDP. Fija ``e.ALPHPD``."""
    e.ALPHPD = (1.0 + e.R * e.R) / (1.0 + 3.0 * e.R * e.R)


def becalc(e):
    """BECALC: coeficiente BETAPD de la FDP. Fija ``e.BETAPD``."""
    e.BETAPD = 1.0 + e.R * e.R


def aacalc(e):
    """AACALC: cocientes de las velocidades medias de corrientes ascendentes y descendentes a
    sigma-w. Fija ``e.ASUB1`` y ``e.ASUB2``."""
    determ = (e.ALPHPD * e.ALPHPD) * (e.SKEW * e.SKEW) + (4.0 / e.BETAPD)

    # raíz de sigma-wc^2/wstar^2
    swratio = e.SWEFFD / e.WSTAR

    e.ASUB1 = swratio * (0.5 * e.ALPHPD * e.SKEW + 0.5 * math.sqrt(determ))
    e.ASUB2 = swratio * (0.5 * e.ALPHPD * e.SKEW - 0.5 * math.sqrt(determ))


def bbcalc(e):
    """BBCALC: cocientes de la energía turbulenta de ascendentes y descendentes. Fija ``e.BSUB1``
    y ``e.BSUB2``."""
    e.BSUB1 = e.R * e.ASUB1
    e.BSUB2 = -(e.R * e.ASUB2)


def llcalc(e):
    """LLCALC: frecuencias relativas de ascendentes y descendentes. Fija ``e.LAMDA1`` y
    ``e.LAMDA2``."""
    e.LAMDA1 = e.ASUB2 / (e.ASUB2 - e.ASUB1)
    e.LAMDA2 = 1.0 - e.LAMDA1


# ============================================================================ decaimiento
def decay(e, xarg):
    """DECAY: término de decaimiento. Fija ``e.D``; DECOEF se modifica temporalmente y se repone."""
    e.D = 1.0
    dc1 = e.DECOEF  # copia temporal de DECOEF

    if e.URBAN and e.POLLUT == "SO2" and e.URBSRC[e.ISRC] == "Y" and \
            ((e.ICSTAT[7] == 0 and e.ICSTAT[8] == 0) or e.DFAULT):
        # fuente urbana de SO2: semivida de 4 horas
        e.DECOEF = 4.81e-5
    elif (e.POLLUT == "SO2" and e.URBSRC[e.ISRC] == "N") or e.DFAULT:
        # fuente rural de SO2 u opción por defecto
        e.DECOEF = 0.0

    if e.DECOEF > 0.0:
        if e.STABLE or (e.UNSTAB and e.HS >= e.ZI):
            e.D = math.exp(max(e.EXPLIM, -(e.DECOEF * xarg / e.UEFF)))
        else:
            e.D = math.exp(max(e.EXPLIM, -(e.DECOEF * xarg / e.UEFFD)))
    e.DECOEF = dc1  # se repone el valor original


# ============================================================================ términos verticales
def vrtsbl(e, szarg, hearg, ziarg):
    """VRTSBL: término vertical estable con reflexiones múltiples en ZIARG (= max(HE, ZI)).
    Fija ``e.FSUBZ``."""
    zr = e.ZR
    explim = e.EXPLIM
    v = 0.0

    if zr == 0.0:
        # terreno llano sin receptor elevado (ZR = 0)
        a1 = (-0.5 / (szarg * szarg)) * hearg * hearg
        if a1 > explim:
            v = math.exp(a1)
        sum_ = 0.0
        for i in range(1, 101):
            t = 0.0
            twoizi = 2.0 * float(i) * ziarg
            a2 = (-0.5 / (szarg * szarg)) * (twoizi - hearg) * \
                 (twoizi - hearg)
            a3 = (-0.5 / (szarg * szarg)) * (twoizi + hearg) * \
                 (twoizi + hearg)
            if a2 > explim:
                t = math.exp(a2)
            if a3 > explim:
                t = t + math.exp(a3)
            sum_ = sum_ + t

            # convergencia relativa
            if abs(t) <= 5.0e-7 * abs(sum_):
                break
        v = 2.0 * (v + sum_)

    elif zr <= ziarg:
        # ZR distinto de 0: con ZR < 0 se mantienen HE y ZI horizontales
        hetmp = max(hearg, hearg - zr)
        zitmp = max(ziarg, ziarg - zr)

        a1 = (-0.5 / (szarg * szarg)) * (zr - hetmp) * (zr - hetmp)
        a2 = (-0.5 / (szarg * szarg)) * (zr + hetmp) * (zr + hetmp)
        if a1 > explim:
            v = math.exp(a1)
        if a2 > explim:
            v = v + math.exp(a2)
        sum_ = 0.0
        for i in range(1, 101):
            t = 0.0
            twoizi = 2.0 * float(i) * zitmp
            a3 = (-0.5 / (szarg * szarg)) * (zr - (twoizi - hetmp)) * \
                 (zr - (twoizi - hetmp))
            a4 = (-0.5 / (szarg * szarg)) * (zr + (twoizi - hetmp)) * \
                 (zr + (twoizi - hetmp))
            a5 = (-0.5 / (szarg * szarg)) * (zr - (twoizi + hetmp)) * \
                 (zr - (twoizi + hetmp))
            a6 = (-0.5 / (szarg * szarg)) * (zr + (twoizi + hetmp)) * \
                 (zr + (twoizi + hetmp))
            if a3 > explim:
                t = t + math.exp(a3)
            if a4 > explim:
                t = t + math.exp(a4)
            if a5 > explim:
                t = t + math.exp(a5)
            if a6 > explim:
                t = t + math.exp(a6)
            sum_ = sum_ + t

            # convergencia relativa
            if abs(t) <= 1.0e-6 * abs(sum_):
                break
        v = v + sum_

    else:
        # receptor por encima de HSBL
        v = 0.0

    # FSUBZ = V / (SQRT(2*PI) * SZARG)
    e.FSUBZ = v / (e.SRT2PI * szarg)


def vrtsbn(e, szarg, hearg):
    """VRTSBN: término vertical estable SIN tapa de mezcla (penachos por encima de la capa
    convectiva). Fija ``e.FSUBZ``."""
    zr = e.ZR
    v = 0.0

    if zr == 0.0:
        # terreno llano sin receptor elevado (ZR = 0)
        a1 = (-0.5 / (szarg * szarg)) * hearg * hearg
        if a1 > e.EXPLIM:
            v = math.exp(a1)
        v = 2.0 * v
    else:
        # ZR distinto de 0: con ZR < 0 se mantiene HE horizontal
        hetmp = max(hearg, hearg - zr)

        a1 = (-0.5 / (szarg * szarg)) * (zr - hetmp) * (zr - hetmp)
        a2 = (-0.5 / (szarg * szarg)) * (zr + hetmp) * (zr + hetmp)
        if a1 > e.EXPLIM:
            v = math.exp(a1)
        if a2 > e.EXPLIM:
            v = v + math.exp(a2)

    # FSUBZ = V / (SQRT(2*PI) * SZ)
    e.FSUBZ = v / (e.SRT2PI * szarg)


def vrtcbl(e, he1, he2, sz1, sz2, fact):
    """VRTCBL: término vertical bi-gaussiano convectivo (FACT = 1 penacho directo, -1 indirecto).
    Fija ``e.FSUBZ`` (el factor 1/SZ va dentro de V)."""
    zr = e.ZR
    zi = e.ZI
    explim = e.EXPLIM
    lamda1 = e.LAMDA1
    lamda2 = e.LAMDA2
    v = 0.0

    if abs(zr - 0.0) < 1.0e-10:
        # terreno llano sin receptor elevado (ZR = 0)
        sum_ = 0.0

        for i in range(0, 1001):
            t1 = 0.0
            t2 = 0.0
            twoizi = 2.0 * float(i) * zi * fact
            # con FACT < 0 se salta el primer término
            if fact < 0.0 and i == 0:
                continue

            hearg1 = twoizi + he1
            hearg2 = twoizi + he2
            a1 = (-0.5 / (sz1 * sz1)) * (hearg1) * (hearg1)
            if a1 > explim:
                t1 = math.exp(a1)
            a2 = (-0.5 / (sz2 * sz2)) * (hearg2) * (hearg2)
            if a2 > explim:
                t2 = math.exp(a2)

            # suma de las partes de los penachos 1 y 2
            term = (lamda1 / sz1) * t1 + (lamda2 / sz2) * t2
            sum_ = sum_ + term

            # convergencia
            if abs(term) <= 5.0e-7 * abs(sum_):
                break

        v = 2.0 * sum_

    elif zr <= zi:
        # ZR distinto de 0: con ZR < 0 se mantienen HE y ZI horizontales
        he1tmp = max(he1, he1 - zr)
        he2tmp = max(he2, he2 - zr)
        zitmp = max(zi, zi - zr)

        sum_ = 0.0

        for i in range(0, 1001):
            t1 = 0.0
            t2 = 0.0
            twoizi = 2.0 * float(i) * zitmp * fact
            # con FACT < 0 se salta el primer término
            if fact < 0.0 and i == 0:
                continue

            # vale también para el penacho indirecto (su HE ya contiene ZI)
            hearg1 = twoizi + he1tmp
            hearg2 = twoizi + he2tmp
            a1 = (-0.5 / (sz1 * sz1)) * (zr - (hearg1)) * \
                 (zr - (hearg1))
            a2 = (-0.5 / (sz1 * sz1)) * (zr + (hearg1)) * \
                 (zr + (hearg1))
            if a1 > explim:
                t1 = math.exp(a1)
            if a2 > explim:
                t1 = t1 + math.exp(a2)
            a3 = (-0.5 / (sz2 * sz2)) * (zr - (hearg2)) * \
                 (zr - (hearg2))
            a4 = (-0.5 / (sz2 * sz2)) * (zr + (hearg2)) * \
                 (zr + (hearg2))
            if a3 > explim:
                t2 = math.exp(a3)
            if a4 > explim:
                t2 = t2 + math.exp(a4)

            # suma de las partes de los penachos 1 y 2
            term = (lamda1 / sz1) * t1 + (lamda2 / sz2) * t2
            sum_ = sum_ + term

            # convergencia
            if abs(term) <= 1.0e-6 * abs(sum_):
                break

        v = sum_

    else:
        # receptor por encima de la altura de mezcla
        v = 0.0

    # FSUBZ = V / SQRT(2*PI)
    e.FSUBZ = v / e.SRT2PI


# ============================================================================ fracción bajo HCRIT
def pfract(e, hearg):
    """PFRACT: fracción del penacho por debajo de HCRIT. Fija ``e.PHEE``; si pasa de 1.01 (y no
    se omiten los mensajes) emite el mensaje 405 (fija ``e.DUMMY``) y la limita a 1."""
    e.PHEE = 0.0

    if e.STABLE and (e.HCRIT > 0.0):
        sz = e.SZ
        rtof2 = e.RTOF2
        hsbl = e.HSBL

        # límite de la integral: HCINT = MIN(HSBL, HCRIT), con HSBL = MAX(HE, ZI)
        hcint = min(hsbl, e.HCRIT)

        # términos de n = 0
        a1 = (hcint - hearg) / (rtof2 * sz)
        a2 = (hcint + hearg) / (rtof2 * sz)
        b1 = erfx(a1)
        b2 = erfx(a2)

        # sumatorio
        sum_ = 0.0
        for i in range(1, 101):
            t = 0.0
            twoizi = 2.0 * float(i) * hsbl
            a3 = (hcint - hearg + twoizi) / (rtof2 * sz)
            a4 = (hcint + hearg + twoizi) / (rtof2 * sz)
            a5 = (hcint - hearg - twoizi) / (rtof2 * sz)
            a6 = (hcint + hearg - twoizi) / (rtof2 * sz)
            b3 = erfx(a3)
            b4 = erfx(a4)
            b5 = erfx(a5)
            b6 = erfx(a6)

            t = b3 + b4 + b5 + b6
            sum_ = sum_ + t

            # convergencia, con un mínimo de 5 iteraciones
            if abs(t) <= 1.0e-6 * abs(sum_):
                if i >= 5:
                    break

        e.PHEE = 0.5 * (b1 + b2 + sum_)

        # PHEE > 1.01: se limita a 1 (solo si no se omiten los mensajes)
        if e.PHEE > 1.01 and not e.L_SKIPMESSAGES:
            e.DUMMY = fwrite("(I8.8)", e.KURDAT)[0]
            e.errhdl(e.PATH, "PFRACT", "I", "405", e.DUMMY)
            e.PHEE = 1.0


def erfx(arg):
    """ERFX (FUNCTION): función de error por la aproximación de Hastings (1955). No usa el estado
    global, por eso no recibe `e`."""
    if arg > 4.0:
        return 1.0
    elif arg < -4.0:
        return -1.0
    elif abs(arg) < 1.0e-10:
        return 0.0
    else:
        x = abs(arg)
        r = 1.0 - 1.0 / (1.0 + x * (0.705230784e-1 + x * (0.422820123e-1 + x *
                         (0.92705272e-2 + x * (0.1520143e-3 + x * (0.2765672e-3 + x *
                          0.430638e-4)))))) ** 16.0
        if arg < 0.0:
            r = -r
        return r
