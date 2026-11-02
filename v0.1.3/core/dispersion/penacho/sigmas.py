# -*- coding: utf-8 -*-
"""Traducción de AERMOD 26135 (US EPA, dominio público): coeficientes de dispersión (sigmas.f:
SIGY, SIGZ, BID, SZSFCL, RMSSIG) y sobreelevación del penacho (prise.f: DELTAH, PRMDELH, HSPRIM,
SBLRIS, CBLPRD, CBLPRN, CBLPR3).

Las variables de MAIN1 se leen y escriben en ``e`` con su nombre Fortran; las de los módulos de
PRIME, en ``e.P``. Las subrutinas devuelven sus argumentos escalares de salida.

Rutinas externas que se llaman (firma asumida):
  · ``perfiles.locate(parray, lvlblw, lvlabv, value)`` → NDXBLW            (LOCATE, metext.f)
  · ``perfiles.gintrp(htbelo, vbelow, htabov, vabove, reqdht)`` → VALUE    (GINTRP, metext.f)
  · ``prime.numrise(e, ldbhr, h, reff, texit, wexit, ntr, capped, horiz, capfact,
    xtr, ytr, ztr, rtr, dbgunt)`` → ``(linwake, numwake, ierr)``          (NUMRISE, prime.f)
    rellena en su sitio las matrices xtr, ytr, ztr, rtr (numpy, índices 1..ntr). ``numwake`` solo
    lo asigna el original cuando el penacho entra en la estela (linwake verdadero); en otro caso
    se devuelve -1 (cuenta como ≤ 1).
  · ``prime.numgrad(x, xtr, ztr, ntr)`` → ZEFF                             (NUMGRAD, prime.f)
"""
import math

import numpy as np

from . import depura, perfiles
from . import estela_edificio
from .formato import sngl


def _rpot(base, expo):
    """Potencia real ``base**expo`` como el Fortran: base negativa → NaN (Python daría un
    complejo). Solo se usa donde la base podría ser negativa (distancias negativas)."""
    if base < 0.0:
        return float("nan")
    return base ** expo


# ============================================================================ sigmas.f
def sigy(e, xarg):
    """SIGY: sigma-y ambiental (SYAMB; en convectivo también SYAN y SYA3)."""
    if e.STABLE or (e.UNSTAB and (e.HS >= e.ZI)):
        # estable o emisión por encima de la capa de mezcla convectiva
        svovru = max(e.SVUMIN, e.SVEFF / e.UEFF)
        tyeff = (e.ZIMECH / (156.0 * e.SVEFF)) * (max(e.HE, 0.46) / 0.46)
        e.SYAMB = (svovru * xarg) / (1.0 + xarg / (2.0 * e.UEFF * tyeff)) ** 0.3

    elif e.UNSTAB:
        # convectivo con emisión por debajo de ZI
        svovru = max(e.SVUMIN, e.SVEFFD / e.UEFFD)
        xnodim = svovru * xarg / e.ZI
        denomi = max(e.HS, 0.46)
        # EXPON = 1: el original lo recodifica sin el exponente
        betalph = max(78.0 * (0.46 / denomi), 0.7)
        e.SYAMB = (svovru * xarg) / (1.0 + betalph * xnodim) ** 0.3

        # fuente indirecta = fuente directa
        e.SYAN = e.SYAMB

        # penacho que penetra la capa de mezcla, SYA3
        if e.PPF > 0.0:
            svovru = max(e.SVUMIN, e.SVEFF3 / e.UEFF3)
            tyeff3 = (e.ZIMECH / (156.0 * e.SVEFF3)) * (max(e.HE3, 0.46) / 0.46)
            e.SYA3 = (svovru * xarg) / (1.0 + xarg / (2.0 * e.UEFF3 * tyeff3)) ** 0.3
        else:
            e.SYA3 = 0.0


def sigz(e, xarg):
    """SIGZ: sigma-z ambiental (SZAMB/SZAS en estable; SZAD1, SZAD2, SZAN1, SZAN2 y SZA3 en
    convectivo)."""
    if e.STABLE or (e.UNSTAB and e.HS >= e.ZI):
        # estable o emisión por encima de ZI (Venkatram, ec. 1)
        ttravl = xarg / e.UEFF

        # formulación de CTDMPLUS: temperatura potencial a la altura HE
        ndxzhe = perfiles.locate(e.GRIDHT, 1, e.MXGLVL, e.HE)
        ptp = float(perfiles.gintrp(e.GRIDHT[ndxzhe], e.GRIDPT[ndxzhe],
                                    e.GRIDHT[ndxzhe + 1], e.GRIDPT[ndxzhe + 1], e.HE))

        if e.TGEFF > 0.0:
            bvfrq = math.sqrt(e.G * e.TGEFF / ptp)
        else:
            bvfrq = 1.0e-10

        if bvfrq < 1.0e-10:
            bvfrq = 1.0e-10

        # altura para sigma-z
        ztmp = max(e.HS, e.HE, 1.0e-4)

        if e.URBSTAB:
            # capa estable urbana: sin el término de Brunt-Vaisala
            e.SZAMB = e.SWEFF * ttravl / math.sqrt(1.0 + e.SWEFF * ttravl *
                                                   (1.0 / (0.72 * ztmp)))
        else:
            e.SZAMB = e.SWEFF * ttravl / math.sqrt(1.0 + e.SWEFF * ttravl *
                                                   (1.0 / (0.72 * ztmp) + bvfrq / (0.54 * e.SWEFF)))

        if e.HE < e.ZI:
            szsfcl(e, xarg)

            sigf = min(e.HE / e.ZI, 1.0)
            e.SZAS = (1.0 - sigf) * e.SZSURF + sigf * e.SZAMB
        else:
            e.SZAS = e.SZAMB

    elif e.UNSTAB:
        # convectivo con emisión por debajo de ZI (Weil, ecs. 5c y 24a)
        if e.PPF < 1.0:
            if not e.SURFAC:
                alphab = 1.0
            else:
                alphab = 0.6 + 0.4 * (e.CENTER / (0.1 * e.ZI))

            e.SZAD1 = alphab * e.BSUB1 * e.WSTAR * xarg / e.UEFFD
            e.SZAD2 = alphab * e.BSUB2 * e.WSTAR * xarg / e.UEFFD

            szsfcl(e, xarg)

            e.SZAD1 = math.sqrt(e.SZAD1 * e.SZAD1 + e.SZSURF * e.SZSURF)
            e.SZAD2 = math.sqrt(e.SZAD2 * e.SZAD2 + e.SZSURF * e.SZSURF)

        else:
            e.SZAD1 = 1.0
            e.SZAD2 = 1.0

        e.SZAN1 = e.SZAD1
        e.SZAN2 = e.SZAD2

        # penacho que penetra: CTDMPLUS sin término de Brunt-Vaisala
        if e.PPF > 0.0:
            ttravl = xarg / e.UEFF3
            e.SZA3 = e.SWEFF3 * ttravl / math.sqrt(1.0 + e.SWEFF3 * ttravl *
                                                   (1.0 / (0.72 * e.HE3)))
        else:
            e.SZA3 = 0.0


def bid(e):
    """BID: dispersión inducida por la flotabilidad (SYB, SZB, SZBD, SZBN, SYB3, SZB3)."""
    if e.STABLE or (e.UNSTAB and (e.HS >= e.ZI)):
        if e.AFTSRC[e.ISRC] == "Y":
            # fuentes de aeronave: PLUME_SPREAD calculado en PLUME_TRAJ
            e.SZB = e.PLUME_SPREAD / 5.93
            e.SYB = e.PLUME_SPREAD / 2.28
            e.SZBD = 0.0
            e.SZBN = 0.0
            e.SYB3 = 0.0
            e.SZB3 = 0.0
        else:
            e.SZB = e.BETA2 * e.DHP / e.RTOF2

            e.SYB = e.SZB
            e.SZBD = 0.0
            e.SZBN = 0.0
            e.SYB3 = 0.0
            e.SZB3 = 0.0
    elif e.UNSTAB:
        if e.AFTSRC[e.ISRC] == "Y":
            e.SZBD = e.PLUME_SPREAD / 5.93
            e.SZBN = e.SZBD
        else:
            # contribución de la fuente directa
            e.SZBD = e.BETA2 * e.DHP1 / e.RTOF2
            e.SZBN = e.SZBD
        # contribución del penacho que penetra
        if e.PPF > 0.0:
            e.SZB3 = e.BETA2 * e.PPF * e.DHP3 / e.RTOF2
        else:
            e.SZB3 = 0.0

        if e.AFTSRC[e.ISRC] == "Y":
            e.SYB = sngl(2.6) * e.SZBD       # literal de precisión simple en el original
            e.SYB3 = e.SZB3
        else:
            e.SYB = e.SZBD
            e.SYB3 = e.SZB3


def szsfcl(e, xarg):
    """SZSFCL: término de capa superficial de sigma-z (SZSURF)."""
    if e.UNSTAB and e.SURFAC:
        e.SZSURF = (e.BSUBC * (1.0 - 10.0 * (e.CENTER / e.ZI)) *
                    (e.USTAR / e.UEFFD) * (e.USTAR / e.UEFFD) *
                    (xarg * xarg / abs(e.OBULEN)))

    elif e.STABLE:
        # en estable se aplica siempre
        e.SZSURF = ((e.RTOF2 / e.RTOFPI) * e.USTAR * (xarg / e.UEFF) *
                    (1.0 + 0.7 * xarg / e.OBULEN) ** (-1.0 * e.THIRD))

    else:
        e.SZSURF = 0.0


def rmssig(e):
    """RMSSIG: sigma-y y sigma-z totales como raíz de la suma de cuadrados (incluye los términos
    de downwash de plataformas)."""
    if e.STABLE or (e.UNSTAB and (e.HS >= e.ZI)):
        e.SY = math.sqrt(e.SYB * e.SYB + e.SYAMB * e.SYAMB + e.VSIGY * e.VSIGY
                         + e.PLATSY * e.PLATSY)

        e.SZ = math.sqrt(e.SZB * e.SZB + e.SZAS * e.SZAS + e.VSIGZ * e.VSIGZ
                         + e.PLATSZ * e.PLATSZ)

        e.SYN = 0.0
        e.SZD1 = 0.0
        e.SZD2 = 0.0
        e.SZN1 = 0.0
        e.SZN2 = 0.0

        e.SY3 = 0.0
        e.SZ3 = 0.0

        # (depuración omitida: PLATFMDBG)

    elif e.UNSTAB:
        e.SY = math.sqrt(e.SYB * e.SYB + e.SYAMB * e.SYAMB + e.VSIGY * e.VSIGY
                         + max(e.PLATSYD1, e.PLATSYD2) * max(e.PLATSYD1, e.PLATSYD2))
        e.SYN = math.sqrt(e.SYB * e.SYB + e.SYAN * e.SYAN + e.VSYN * e.VSYN
                          + max(e.PLATSYN1, e.PLATSYN2) * max(e.PLATSYN1, e.PLATSYN2))
        e.SZD1 = math.sqrt(e.SZBD * e.SZBD + e.SZAD1 * e.SZAD1 + e.VSZD1 * e.VSZD1
                           + e.PLATSZD1 * e.PLATSZD1)
        e.SZD2 = math.sqrt(e.SZBD * e.SZBD + e.SZAD2 * e.SZAD2 + e.VSZD2 * e.VSZD2
                           + e.PLATSZD2 * e.PLATSZD2)
        e.SZN1 = math.sqrt(e.SZBN * e.SZBN + e.SZAN1 * e.SZAN1 + e.VSZN1 * e.VSZN1
                           + e.PLATSZN1 * e.PLATSZN1)
        e.SZN2 = math.sqrt(e.SZBN * e.SZBN + e.SZAN2 * e.SZAN2 + e.VSZN2 * e.VSZN2
                           + e.PLATSZN2 * e.PLATSZN2)

        if e.PPF > 0.0:
            e.SY3 = math.sqrt(e.SYB3 * e.SYB3 + e.SYA3 * e.SYA3
                              + e.PLATSYP * e.PLATSYP)
            e.SZ3 = math.sqrt(e.SZB3 * e.SZB3 + e.SZA3 * e.SZA3
                              + e.PLATSZP * e.PLATSZP)
        else:
            e.SY3 = 0.0
            e.SZ3 = 0.0

        # (depuración omitida: PLATFMDBG)


# ============================================================================ prise.f
def deltah(e, xarg):
    """DELTAH: sobreelevación del penacho a la distancia XARG (DHP; en convectivo DHP1, DHP2 y
    DHP3)."""
    if (e.STABLE or (e.UNSTAB and (e.HS >= e.ZI))) and (xarg >= e.XMAX):
        # sobreelevación final estable calculada en DISTF
        e.DHP = e.DHFAER

    elif (e.STABLE or (e.UNSTAB and (e.HS >= e.ZI))) and (xarg < e.XMAX):
        # sobreelevación estable a la distancia XARG, iterativa; no se pasa a SBLRIS una distancia
        # mayor que la de sobreelevación final con los valores actuales de UP y BVPRIM
        xmaxtmp = e.UP * math.atan2(e.FM * e.BVPRIM, -e.FB) / e.BVPRIM
        xrise = min(xarg, xmaxtmp)
        sblris(e, xrise)
        kiter = 0

        gh = e.GRIDHT
        while True:
            # etiqueta 50
            zplm = e.HSP + 0.5 * e.DHP
            dhpold = e.DHP

            # índice del nivel inferior a ZPLM
            ndxzpl = perfiles.locate(gh, 1, e.MXGLVL, zplm)

            # viento y sigma-v a ZPLM
            svpm = float(perfiles.gintrp(gh[ndxzpl], e.GRIDSV[ndxzpl],
                                         gh[ndxzpl + 1], e.GRIDSV[ndxzpl + 1], zplm))
            upm = float(perfiles.gintrp(gh[ndxzpl], e.GRIDWS[ndxzpl],
                                        gh[ndxzpl + 1], e.GRIDWS[ndxzpl + 1], zplm))

            svpm = max(svpm, e.SVMIN, e.SVUMIN * upm)
            if e.L_VECTORWS:
                upm = math.sqrt(upm * upm + 2.0 * svpm * svpm)
            upm = max(upm, e.WSMIN)

            # promedio de los valores en la boca y en el punto medio
            e.UP = 0.5 * (e.US + upm)

            tgpm = float(perfiles.gintrp(gh[ndxzpl], e.GRIDTG[ndxzpl],
                                         gh[ndxzpl + 1], e.GRIDTG[ndxzpl + 1], zplm))
            ptpm = float(perfiles.gintrp(gh[ndxzpl], e.GRIDPT[ndxzpl],
                                         gh[ndxzpl + 1], e.GRIDPT[ndxzpl + 1], zplm))
            e.TGP = 0.5 * (e.TGS + tgpm)
            ptp = 0.5 * (e.PTS + ptpm)
            e.BVF = math.sqrt(e.G * e.TGP / ptp)
            if e.BVF < 1.0e-10:
                e.BVF = 1.0e-10
            e.BVPRIM = 0.7 * e.BVF

            # distancia de sobreelevación final con los nuevos UP y BVPRIM
            xmaxtmp = e.UP * math.atan2(e.FM * e.BVPRIM, -e.FB) / e.BVPRIM
            xrise = min(xarg, xmaxtmp)
            sblris(e, xrise)

            kiter = kiter + 1

            if e.DEBUG:
                depura.opth2_iter(e, kiter, dhpold, e.DHP, zplm)

            # convergencia (el "and" de Python evita dividir por DHP <= 0; el resultado lógico
            # es el mismo)
            if e.DHP > 0.0 and abs((dhpold - e.DHP) / e.DHP) < 0.001 and kiter >= 5:
                if e.DHP <= 1.0e-5:
                    e.DHP = 1.0e-5
                break
            elif kiter < 10:
                continue

            if kiter >= 5:
                e.DHP = 0.5 * (e.DHP + dhpold)
                if e.DEBUG:
                    depura.deltah_noconv(e)
                break
            # (rama GO TO 50 inalcanzable: aquí KITER >= 10)

        # etiqueta 60: se restauran UP, TGP y BVF de la boca de la chimenea
        e.UP = e.US
        e.TGP = e.TGS
        ptp = e.PTS
        e.BVF = math.sqrt(e.G * e.TGP / ptp)
        if e.BVF < 1.0e-10:
            e.BVF = 1.0e-10
        e.BVPRIM = 0.7 * e.BVF
        # la sobreelevación estable no puede superar la convectiva
        cblprd(e, xarg)
        e.DHP = min(e.DHP, e.DHP1)
        e.DHP = min(e.DHP, e.DHFAER)

    elif e.UNSTAB:
        # convectivo con HS < ZI
        cblprd(e, xarg)          # penacho directo
        cblprn(e, xarg)          # penacho indirecto

        if e.PPF > 0.0:
            cblpr3(e)            # penacho que penetra
        else:
            e.DHP3 = 0.0


def prmdelh(e, xarg, l_inwake):
    """PRMDELH: sobreelevación para el cálculo PRIME (DHP). Devuelve L_INWAKE (argumento de
    entrada/salida del original)."""
    p = e.P
    mxntr = p.MXNTR
    # variables locales con SAVE
    xtr = e.PRMD_XTR
    ytr = e.PRMD_YTR
    ztr = e.PRMD_ZTR
    rtr = e.PRMD_RTR

    capped = False
    horiz = False

    if e.WAKE:
        # sobreelevación final y tabla de transición solo para el primer receptor
        if e.PRM_FSTREC:
            e.PRM_FSTREC = False
            l_inwake = False
            p.DFSN2CALL = False
            e.PRMD_HSEFF = e.HS
            # radio a partir del diámetro
            e.PRMD_REFF = 0.5 * e.DS
            if e.SRCTYP[e.ISRC] == "POINTCAP":
                capped = True
            else:
                capped = False
            if e.SRCTYP[e.ISRC] == "POINTHOR":
                horiz = True
            else:
                horiz = False
            # sobreelevación de transición y final (NUMRISE)
            l_inwake, numwake, ierr = estela_edificio.numrise(
                e, e.PRIMEDBG, e.PRMD_HSEFF, e.PRMD_REFF, e.TS, e.VS, mxntr, capped,
                horiz, e.DSFACT, xtr, ytr, ztr, rtr, e.PRMDBUNT)
            if ierr == 1:
                # error en la sobreelevación numérica de PRIME
                e.errhdl(e.PATH, "PRMDELH", "E", "499", e.SRCID[e.ISRC])
                e.RUNERR = True
                return l_inwake
            # NUMWAKE sin asignar solo si el penacho no entró en la estela (L_INWAKE ya falso)
            if numwake <= 1:
                l_inwake = False
            # ZTR es la altura efectiva: sobreelevación final
            e.DHF = float(ztr[mxntr]) - e.PRMD_HSEFF
            if e.PRIMEDBG:
                depura.wake_dbg(e, e.PRMDBUNT, mxntr, xtr, ytr, ztr, rtr, e.NOBID, e.PRMD_HSEFF)
            e.PRMD_LINW = l_inwake
        else:
            l_inwake = e.PRMD_LINW

        # sobreelevación para el receptor actual
        if xarg < xtr[mxntr]:
            # interpolación en la tabla de sobreelevación gradual (NUMGRAD)
            e.ZEFF = float(estela_edificio.numgrad(xarg, xtr, ztr, mxntr))
            e.DHP = e.ZEFF - e.PRMD_HSEFF
        else:
            e.DHP = float(ztr[mxntr]) - e.PRMD_HSEFF

    return l_inwake


def hsprim(us, vs, hs, ds):
    """HSPRIM (FUNCTION): altura de chimenea corregida por el downwash de la boca (HS')."""
    if vs < 1.5 * us:
        hsprim_ = hs - 2.0 * ds * (1.5 - vs / us)
    else:
        hsprim_ = hs

    if hsprim_ < 0.0:
        hsprim_ = 0.0

    return hsprim_


def sblris(e, xarg):
    """SBLRIS: sobreelevación en la capa estable o por encima de la capa convectiva (DHP)."""
    # FB, BVF y UP ya se han comprobado positivos
    terma = e.FB / (e.BVF * e.BVF * e.UP)
    termb = e.BVPRIM * e.FM / e.FB
    termc = math.sin(e.BVPRIM * xarg / e.UP)
    termd = math.cos(e.BVPRIM * xarg / e.UP)

    # TERME evita un argumento negativo
    terme = (termb * termc + 1.0 - termd)

    if terme > 0.0:
        e.DHP = 2.66 * (terma * (termb * termc + 1.0 - termd)) ** e.THIRD
    else:
        e.DHP = 2.66 * _rpot(terma * termb * termc, e.THIRD)

    # límite inferior (ec. 98 del MFD)
    xln = e.FB / (e.UP * e.USTAR * e.USTAR)
    delhnn = 1.2 * xln ** 0.6 * (e.HSP + 1.2 * xln) ** 0.4

    e.DHP = min(e.DHP, e.DHFAER, delhnn)


def cblprd(e, xarg):
    """CBLPRD: sobreelevación del penacho directo en la capa convectiva (DHP1)."""
    e.DHP1 = _rpot(3.0 * e.FM * xarg / (e.BETA1 * e.BETA1 * e.UP * e.UP) +
                   3.0 * e.FB * xarg * xarg /
                   (2.0 * e.BETA1 * e.BETA1 * e.UP * e.UP * e.UP), e.THIRD)


def cblprn(e, xarg):
    """CBLPRN: sobreelevación del penacho indirecto en la capa convectiva (DHP2)."""
    rsubh = e.BETA2 * (e.ZI - e.HSP)
    ryrz = (rsubh * rsubh + 0.25 * e.ASUBE * (e.LAMDAY ** 1.5) *
            e.WSTAR * e.WSTAR * xarg * xarg / (e.UP * e.UP))
    delhi = math.sqrt((2.0 * e.FB * e.ZI) / (e.ALPHAR * e.UP * ryrz)) * (xarg / e.UP)
    e.DHP2 = delhi


def cblpr3(e):
    """CBLPR3: sobreelevación del penacho que penetra la capa convectiva (DHP3)."""
    if e.PPF == 1.0:
        e.DHP3 = e.HEDHH * (e.ZI - e.HSP)
    else:
        e.DHP3 = 0.75 * (e.ZI - e.HSP) * e.HEDHH + 0.5 * (e.ZI - e.HSP)
