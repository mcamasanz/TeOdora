# -*- coding: utf-8 -*-
"""Traducción de AERMOD 26135 (US EPA, dominio público): fuentes OPENPIT (canteras y fosos
abiertos).

Rutinas traducidas:
  · calc1.f: OCALC completo (con su bucle de receptores, la aproximación de fuente puntual de
    FASTAREA/FASTALL y las ramas de la química del NO2).
  · pitarea.f: ESCAPE, ADJEMI, AMFRAC, LWIND, PDEPTH, PTFRAC, PITEFF, PITEMI y CTHETA.
  · aermod.f: PNPOLY (punto dentro de un polígono).
  · soset.f: OPARM y la rama OPENPIT de SOPARM (número de campos de SRCPARAM).
  · inpsum.f: la tabla «OPENPIT SOURCE DATA» de PRTSRC y la rama OPENPIT de CHKREC.
  · calc1.f (PVMRM): las ramas OPENPIT de PVMRM_CALC (penacho dominante y moles de NOx),
    MAJOR_CONT y MOLES_NOX, en una copia en Python del bucle de receptores de PVMRM
    (``pvmrm_bucle``) que se usa solo cuando hay fuentes OPENPIT (el núcleo numba de PVMRM no
    las admite).

Lo que ya estaba en la traducción y se reutiliza sin cambios: SETSRC (rama OPENPIT), ARDIST,
AREAIN/PLUMEF/AVERTS (integracion_area.py), METINI/IBLVAL, la selección de la meteorología urbana, EMFACT,
HRQEXT (rama OPENPIT), PLUMESIZES de GRSM, TTRM (rama «otros tipos») y SRCQA (NUMPIT).

Ganchos para integrarlo (la lista exacta, con el código, está en el informe de la traducción):
  · calc1.calc: ``elif t == "OPENPIT": openpit.ocalc(e)``.
  · soset.soloca: quitar OPENPIT de ``_FUENTES_FUERA``; soset.soparm: ``openpit.soparm_pit``.
  · inpsum.prtsrc: ``openpit.prtsrc_pit`` antes de la tabla BUOYLINE; inpsum.chkrec: la rama
    OPENPIT con ``openpit.pnpoly``.
  · no2.pvmrm_calc: ``openpit.pvmrm_bucle`` si NUMPIT > 0.

Rendimiento: el bucle de receptores de OCALC se ejecuta con el núcleo numba del bucle de ACALC
(``nucleo.acalc_bucle``, sin modificarlo; ver ``_bucle_nucleo``); ``_bucle`` es la vía Python de
referencia (AERMOD_NUMBA=0, FASTAREA/FASTALL) y da el mismo resultado bit a bit. La copia del
bucle de PVMRM (``pvmrm_bucle``) es Python puro.

Exactitud: orden de operaciones del Fortran, divisiones/raíces/potencias IEEE y seno y coseno
correctamente redondeados (``seno_coseno``) en OPARM y PITEFF: con math.sin, los receptores sobre
la diagonal de un foso girado 45 grados caían en el borde en lugar de dentro (allsrcs).

Deposición: OCALC llama, igual que el original, a VDP, SCAVRAT, PDEP y PDEPG cuando la corrida las
pide. Se buscan por nombre en calc1 (``calculo_area.vdp(e)``, ``calculo_area.scavrat(e)``, ``calculo_area.pdep(e, x)``,
``calculo_area.pdepg(e, x)``); mientras no existan (o sean los esbozos actuales), paran con NoTraducido.
Las salidas de depuración (AREADBG, DEBUGOPT) y EVENT/EVALFILE también paran con NoTraducido.

Convenciones del paquete: estado ``e`` con los nombres de MAIN1, matrices con índices 1..N."""
import math
from decimal import Decimal, localcontext

import numpy as np

from . import calculo_area, funciones_dispersion, parametros_efectivos, integracion_area, resultados, sigmas
from .estado import NoTraducido
from .formato import fwrite, fx
from .perfiles import gintrp, locate

_EPSLON = 1.0e-05           # PITEFF (PARAMETER)


# ------------------------------------------------------------------------------------------
# Utilidades IEEE (Intel sin trampas devuelve NaN/Inf donde Python lanzaría una excepción)
# ------------------------------------------------------------------------------------------
def _div(a, b):
    """División IEEE (±Inf o NaN al dividir por cero)."""
    if b == 0.0:
        if a == 0.0 or a != a:
            return math.nan
        return math.copysign(math.inf, a) * math.copysign(1.0, b)
    return a / b


def _sqrt(x):
    """DSQRT IEEE: NaN para argumentos negativos (o NaN)."""
    return math.sqrt(x) if x >= 0.0 else math.nan


def _pow(x, y):
    """x**y real IEEE (exponente no entero): NaN si x < 0; +Inf si x = 0 e y < 0."""
    if x != x or y != y:
        return math.nan
    if x < 0.0:
        return math.nan
    if x == 0.0 and y < 0.0:
        return math.inf
    return x ** y


# Seno y coseno correctamente redondeados. La libm de Intel del exe los da correctamente redondeados
# y la de MSVC (math.sin) se equivoca a veces en el último bit: sin(-45*DTORAD) sale
# -0.7071067811865476 en lugar de -0.7071067811865475. En OPARM eso decide si un receptor sobre la
# diagonal de un foso girado 45 grados queda dentro (PNPOLY = 1, no se calcula) o en el borde
# (PNPOLY = 0, sí se calcula): lo vio allsrcs (14 receptores). Se calculan con decimal (80 cifras) y
# se redondean al doble más próximo; las llamadas se guardan en una caché (pocos ángulos distintos).
_PI_DEC = Decimal("3.14159265358979323846264338327950288419716939937510582097494459230781640628620899"
                  "8628034825342117068")
_CACHE_SC = {}


def seno_coseno(x):
    """(sin x, cos x) correctamente redondeados para un doble x (radianes)."""
    r = _CACHE_SC.get(x)
    if r is not None:
        return r
    if x != x or x in (math.inf, -math.inf):
        r = (math.nan, math.nan)
    elif x == 0.0:
        r = (x, 1.0)
    else:
        with localcontext() as ctx:
            ctx.prec = 80
            d = Decimal(x)                                  # valor exacto del doble
            dos_pi = 2 * _PI_DEC
            d = d - dos_pi * (d / dos_pi).to_integral_value()
            d2 = d * d
            eps = Decimal(10) ** -75
            s = term = d
            n = 1
            while abs(term) > eps:
                term = -term * d2 / ((n + 1) * (n + 2))
                s += term
                n += 2
            c = term = Decimal(1)
            n = 0
            while abs(term) > eps:
                term = -term * d2 / ((n + 1) * (n + 2))
                c += term
                n += 2
            r = (float(s), float(c))
    if len(_CACHE_SC) > 100000:
        _CACHE_SC.clear()
    _CACHE_SC[x] = r
    return r


def _depos(nombre):
    """Rutina de deposición del original (VDP, SCAVRAT, PDEP, PDEPG) en calc1, si ya existe."""
    f = getattr(calculo_area, nombre, None)
    if f is None:
        raise NoTraducido("depósito (" + nombre.upper() + ")")
    return f


# ------------------------------------------------------------------------------------------
# Vía SO: SRCPARAM de una fuente OPENPIT (soset.f: rama OPENPIT de SOPARM y OPARM)
# ------------------------------------------------------------------------------------------
def soparm_pit(e, isdx, temp):
    """Rama OPENPIT de SOPARM: comprueba el número de campos (8 o 9) y llama a OPARM. TEMP es la
    lista de valores leídos de los campos 4..IFC (TEMP[1] = campo 4)."""
    m = "SOPARM"
    if e.IFC == 3:
        e.errhdl(e.PATH, m, "E", "200", e.KEYWRD)
    elif e.IFC < 8:
        e.errhdl(e.PATH, m, "E", "201", e.KEYWRD)
    elif e.IFC > 9:
        e.errhdl(e.PATH, m, "E", "202", e.KEYWRD)
    else:
        oparm(e, isdx, temp)


def oparm(e, i, temp):
    """OPARM: parámetros de una fuente OPENPIT (emisión por unidad de área, altura de emisión,
    dimensiones X/Y, volumen y orientación), vértices, ángulo del eje largo, profundidad efectiva,
    sigma-z inicial y centro."""
    m = "OPARM"
    e.AQS[i] = temp[1]
    e.AHS[i] = temp[2]
    e.AXINIT[i] = temp[3]
    e.AYINIT[i] = temp[4]
    e.AVOLUM[i] = temp[5]
    e.AANGLE[i] = 0.0
    if e.IFC == 9:
        e.AANGLE[i] = temp[6]

    if e.AQS[i] == 0.0:
        e.errhdl(e.PATH, m, "W", "320", " QS ")
    if e.AHS[i] < 0.0:
        e.errhdl(e.PATH, m, "E", "209", " HS ")
    elif e.AHS[i] > 200.0:
        e.errhdl(e.PATH, m, "W", "320", " HS ")
    elif e.AHS[i] > 3000.0:
        e.errhdl(e.PATH, m, "E", "324", e.SRCID[i])
    for a, txt in ((e.AXINIT, " XINIT "), (e.AYINIT, " YINIT ")):
        if a[i] < 0.0:
            e.errhdl(e.PATH, m, "E", "209", txt)
        elif a[i] < 1.0e-5:
            e.errhdl(e.PATH, m, "W", "320", txt)
            a[i] = 1.0e-5
        elif a[i] > 2000.0:
            e.errhdl(e.PATH, m, "W", "320", txt)
    if abs(e.AANGLE[i]) > 180.0:
        e.errhdl(e.PATH, m, "W", "320", " ANGLE ")
    if e.AVOLUM[i] <= 0.0:
        e.errhdl(e.PATH, m, "E", "209", " AVOLUM ")
    # relación de aspecto (largo/ancho) > 10
    if _div(e.AYINIT[i], e.AXINIT[i]) > 10.0 or _div(e.AXINIT[i], e.AYINIT[i]) > 10.0:
        e.errhdl(e.PATH, m, "W", "392", e.SRCID[i])
    # altura de emisión mayor que la profundidad efectiva
    effdep = _div(e.AVOLUM[i], e.AXINIT[i] * e.AYINIT[i])
    if e.AHS[i] > effdep:
        e.errhdl(e.PATH, m, "E", "322", e.SRCID[i])

    # 4 vértices (el original asigna la variable global NVERT), empezando por el «suroeste» y en
    # sentido horario; el primero se repite al final
    e.NVERT = 4
    xv, yv = e.AXVERT, e.AYVERT
    sa, ca = seno_coseno(e.AANGLE[i] * e.DTORAD)
    xv[1, i] = e.AXS[i]
    yv[1, i] = e.AYS[i]
    xv[2, i] = xv[1, i] + (e.AYINIT[i] * sa)
    yv[2, i] = yv[1, i] + (e.AYINIT[i] * ca)
    xv[3, i] = xv[2, i] + (e.AXINIT[i] * ca)
    yv[3, i] = yv[2, i] - (e.AXINIT[i] * sa)
    xv[4, i] = xv[3, i] - (e.AYINIT[i] * sa)
    yv[4, i] = yv[3, i] - (e.AYINIT[i] * ca)
    xv[5, i] = e.AXS[i]
    yv[5, i] = e.AYS[i]

    # ángulo del lado largo del foso respecto al norte
    if e.AYINIT[i] >= e.AXINIT[i]:
        e.AALPHA[i] = e.AANGLE[i]
    elif e.AXINIT[i] > e.AYINIT[i]:
        e.AALPHA[i] = e.AANGLE[i] + 90.0
    # profundidad efectiva y sigma-z inicial
    e.APDEFF[i] = _div(e.AVOLUM[i], e.AXINIT[i] * e.AYINIT[i])
    e.ASZINI[i] = e.APDEFF[i] / 4.3
    # centro del rectángulo
    e.AXCNTR[i] = 0.0
    e.AYCNTR[i] = 0.0
    for j in range(1, e.NVERT + 1):
        e.AXCNTR[i] = e.AXCNTR[i] + xv[j, i]
        e.AYCNTR[i] = e.AYCNTR[i] + yv[j, i]
    e.AXCNTR[i] = e.AXCNTR[i] / float(e.NVERT)
    e.AYCNTR[i] = e.AYCNTR[i] / float(e.NVERT)


# ------------------------------------------------------------------------------------------
# pitarea.f: rutinas del algoritmo de fosos abiertos
# ------------------------------------------------------------------------------------------
def escape(e, icat):
    """ESCAPE: fracción de escape de la categoría de tamaño ICAT."""
    e.EFRAC[icat] = 1.0 / (1.0 + _div(e.VGRAV[icat], e.ALPHA * e.UREF10))


def adjemi(e, icat, qptot):
    """ADJEMI: emisión ajustada de la categoría ICAT. Devuelve QPTOT acumulado."""
    e.QPART[icat] = e.EFRAC[icat] * e.PHI[icat] * e.QS
    return qptot + e.QPART[icat]


def amfrac(e, qptot):
    """AMFRAC: fracciones másicas ajustadas de todas las categorías."""
    for icat in range(1, e.NPD + 1):
        e.PHI[icat] = _div(e.QPART[icat], qptot)


def ctheta(afvin, alfin):
    """CTHETA: ángulo entre la dirección del viento y el eje largo del foso (0..90 grados)."""
    thout = 0.0
    if abs(afvin - alfin) <= 90.0:
        thout = abs(afvin - alfin)
    elif afvin > alfin:
        theta = afvin - alfin
        if theta > 90.0:
            theta = afvin - 180.0 - alfin
        if theta > 90.0:
            theta = afvin - 360.0 - alfin
        if theta > 90.0:
            theta = afvin - 540.0 - alfin
        thout = abs(theta)
    elif afvin < alfin:
        theta = afvin - alfin
        if theta < -90.0:
            theta = afvin + 180.0 - alfin
        if theta < -90.0:
            theta = afvin + 360.0 - alfin
        if theta < -90.0:
            theta = afvin + 540.0 - alfin
        thout = abs(theta)
    return thout


def lwind(e):
    """LWIND: longitud del foso en la dirección del viento (PITL); fija THETA."""
    e.THETA = ctheta(e.AFV, e.PALPHA)
    e.PITL = e.PITLEN * (1.0 - e.THETA / 90.0) + e.PITWID * (e.THETA / 90.0)


def pdepth(e):
    """PDEPTH: profundidad relativa del foso (PDREL)."""
    e.PDREL = _div(e.PDEFF - e.EMIHGT, e.PITL)


def ptfrac(e):
    """PTFRAC: fracción del área del foso que ocupa el área efectiva (PITFRA)."""
    if e.PDREL >= 0.2:
        e.PITFRA = 0.08
    else:
        e.PITFRA = _sqrt(1.0 - 1.7 * _pow(e.PDREL, e.THIRD))


def piteff(e):
    """PITEFF: vértices del área efectiva del foso (XVERT, YVERT, en coordenadas del usuario),
    sus dimensiones XEFF, YEFF y su centro XCNTR, YCNTR."""
    nv = e.NVERT
    xtemp = [0.0] * (max(e.NVMAX, nv + 1) + 1)
    ytemp = [0.0] * len(xtemp)
    # vértices del foso real en el sistema de la dirección del viento
    integracion_area.averts(e, e.XVERT, e.YVERT, xtemp, ytemp, nv + 1)
    # vértice de barlovento (el de menor X)
    spamin = 1.0e20
    iupwnd = 0
    for iv in range(1, nv + 1):
        if xtemp[iv] < spamin:
            iupwnd = iv
            spamin = xtemp[iv] - _EPSLON
    e.IVERT = nv + 1                     # índice del DO (variable global en el original)
    if e.AREADBG or e.DEBUG:
        raise NoTraducido("AREADBG/DEBUGOPT (PITEFF)")

    # ángulo del área efectiva respecto al norte y sus dimensiones
    effang = e.ANGLE + (90.0 * float(iupwnd - 1))
    ct = seno_coseno(e.THETA * e.DTORAD)[1]
    effwid = _pow(e.PITFRA, 1.0 - ct * ct) * e.PITWID
    efflen = _pow(e.PITFRA, ct * ct) * e.PITLEN

    # dimensiones 'x' e 'y' del área efectiva según la orientación y el vértice de barlovento
    if e.XINIT <= e.YINIT and (iupwnd == 1 or iupwnd == 3):
        e.XEFF = effwid
        e.YEFF = efflen
    elif e.XINIT <= e.YINIT and (iupwnd == 2 or iupwnd == 4):
        e.XEFF = efflen
        e.YEFF = effwid
    elif e.XINIT > e.YINIT and (iupwnd == 1 or iupwnd == 3):
        e.XEFF = efflen
        e.YEFF = effwid
    elif e.XINIT > e.YINIT and (iupwnd == 2 or iupwnd == 4):
        e.XEFF = effwid
        e.YEFF = efflen

    sa, ca = seno_coseno(effang * e.DTORAD)
    xtemp[1] = e.XVERT[iupwnd]
    ytemp[1] = e.YVERT[iupwnd]
    xtemp[2] = xtemp[1] + (e.YEFF * sa)
    ytemp[2] = ytemp[1] + (e.YEFF * ca)
    xtemp[3] = xtemp[2] + (e.XEFF * ca)
    ytemp[3] = ytemp[2] - (e.XEFF * sa)
    xtemp[4] = xtemp[3] - (e.YEFF * sa)
    ytemp[4] = ytemp[3] - (e.YEFF * ca)
    xtemp[5] = e.XVERT[iupwnd]
    ytemp[5] = e.YVERT[iupwnd]

    # (el original pasa el área efectiva al sistema del viento para la depuración, sobre
    # XVERT/YVERT, y a continuación los sobrescribe)
    integracion_area.averts(e, xtemp, ytemp, e.XVERT, e.YVERT, nv + 1)
    for i in range(1, 6):
        e.XVERT[i] = xtemp[i]
        e.YVERT[i] = ytemp[i]

    # centro del área efectiva (antes en ARDIST)
    xc = 0.0
    yc = 0.0
    for i in range(1, nv + 1):
        xc = xc + e.XVERT[i]
        yc = yc + e.YVERT[i]
    e.XCNTR = xc / float(nv)
    e.YCNTR = yc / float(nv)


def pitemi(e, qptot):
    """PITEMI: emisión por unidad de área del área efectiva (QEFF)."""
    e.QEFF = _div(qptot, e.PITFRA)


def geometria(e):
    """LWIND, PDEPTH, PTFRAC y PITEFF (la secuencia que repiten OCALC y las rutinas de PVMRM)."""
    lwind(e)
    pdepth(e)
    ptfrac(e)
    piteff(e)


def pnpoly(px, py, x, y, n):
    """PNPOLY (aermod.f): -1 si (PX,PY) está fuera del polígono de N vértices X(1..N), Y(1..N);
    0 si está en un lado o en un vértice; 1 si está dentro."""
    inout = -1
    for i in range(1, n + 1):
        xi = x[i] - px
        yi = y[i] - py
        # ¿en este vértice?
        if xi == 0.0 and yi == 0.0:
            inout = 0
            break
        j = 1 + (i % n)
        xj = x[j] - px
        yj = y[j] - py
        # lado de longitud nula
        if xi == xj and yi == yj:
            continue
        ix = xi >= 0.0
        iy = yi >= 0.0
        jx = xj >= 0.0
        jy = yj >= 0.0
        # ¿en un lado vertical?
        if xi == 0.0 and xj == 0.0 and (iy != jy):
            inout = 0
            break
        # ¿en un lado horizontal?
        if yi == 0.0 and yj == 0.0 and (ix != jx):
            inout = 0
            break
        # los dos extremos a la derecha, a la izquierda o por debajo del punto
        if not ((iy or jy) and (ix != jx)):
            continue
        # ¿el lado cruza claramente la vertical que sube desde el punto?
        if not (iy and jy and (ix != jx)):
            t = _div(yi * xj - xi * yj, xj - xi)
            if t < 0.0:
                continue
            elif t == 0.0:
                inout = 0
                break
            else:
                inout = -inout
        else:
            inout = -inout
    return inout


# ------------------------------------------------------------------------------------------
# OCALC (calc1.f)
# ------------------------------------------------------------------------------------------
def ocalc(e):
    """OCALC: concentración horaria de una fuente OPENPIT en todos los receptores."""
    m = "OCALC"
    isrc = e.ISRC
    numtyp = e.NUMTYP
    e.WAKE = False
    e.L_APLUME = True
    e.HRVAL[:] = 0.0
    e.AERVAL[:] = 0.0
    aerout = np.zeros(numtyp + 1)
    e.PRMVAL[:] = 0.0
    if e.allocated("CHI"):
        e.CHI[:, isrc, :] = 0.0
    if e.GRSM:
        e.CHI_TTRAVCHM[:, isrc] = 0.0

    # viento de referencia a 10 m
    gh = e.GRIDHT
    ndxr = locate(gh, 1, e.MXGLVL, 10.0)
    e.UREF10 = gintrp(gh[ndxr], e.GRIDWS[ndxr], gh[ndxr + 1], e.GRIDWS[ndxr + 1], 10.0)

    # meteorología urbana o rural de la fuente (en OCALC, antes de SETSRC)
    calculo_area._met_urbana(e)
    calculo_area.setsrc(e)
    parametros_efectivos.metini(e)
    e.AWDSIN[isrc] = e.WDSIN
    e.AWDCOS[isrc] = e.WDCOS
    e.AAFV[isrc] = e.AFV

    # emisión total ajustada (gases: QS; partículas: fracciones de escape)
    qptot = 0.0
    if e.NPD == 0:
        qptot = e.QS
    else:
        for icat in range(1, e.NPD + 1):
            escape(e, icat)
            qptot = adjemi(e, icat, qptot)
    if qptot == 0.0:
        return
    if e.NPD > 0:
        amfrac(e, qptot)

    lwind(e)
    pdepth(e)
    ptfrac(e)
    if e.AREADBG or e.DEBUG:
        raise NoTraducido("AREADBG/DEBUGOPT (OCALC)")
    piteff(e)
    pitemi(e, qptot)

    funciones_dispersion.emfact(e, e.QEFF)
    if e.EVAL[isrc]:
        raise NoTraducido("EVALFILE")

    if e.QEFF != 0.0 and (e.STABLE or e.HS <= e.ZI):
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
        # emisión original, por si se usa la aproximación de fuente puntual
        qtksav = e.QTK
        if e.UNSTAB and e.HS < e.ZI:
            funciones_dispersion.pdf(e)
        _deposicion_fuente(e)
        from . import nucleo
        if nucleo.activo() and not e.FASTAREA and not e.FASTALL:
            _bucle_nucleo(e, qtksav, aerout)
        else:
            _bucle(e, m, qtksav, aerout)


def _deposicion_fuente(e):
    """Velocidades de deposición y razones de lavado de la fuente (bloque de OCALC antes del
    bucle de receptores)."""
    if e.LUSERVD and e.LDGAS and e.NPD == 0:
        e.VDEPG = e.USERVD
    elif e.LDPART or (not e.LUSERVD and e.LDGAS and e.NPD == 0):
        _depos("vdp")(e)
    if e.LWPART or e.LWGAS:
        # ZSUBP = MAX(ZI, cima del penacho a 20 km), entre 500 y 10000 m
        calculo_area.heff(e, 20000.0)
        if e.STABLE or (e.UNSTAB and e.HS >= e.ZI):
            sigmas.sigz(e, 20000.0)
            e.ZSUBP = max(500.0, e.ZI, e.HS + e.SZCOEF * e.SZAS)
        elif e.UNSTAB:
            sigmas.sigz(e, 20000.0)
            e.ZSUBP = max(500.0, e.ZI, e.HS + e.SZCOEF * (e.SZAD1 + e.SZAD2) / 2.0)
        e.ZSUBP = min(10000.0, e.ZSUBP)
        _depos("scavrat")(e)


def _anular(e, aerout, qtksav, ttrm):
    """Ramas CYCLE RECEPTOR_LOOP de OCALC: contribución nula del receptor (y de los datos del
    penacho para la química del NO2); TTRM indica si la condición incluye RUNTTRM."""
    if e.PVMRM or e.OLM or e.ARM2 or e.GRSM or (ttrm and e.RUNTTRM):
        calculo_area._cero_chi(e, e.IREC, e.ISRC)
    e.HRVAL[:] = 0.0
    e.AERVAL[:] = 0.0
    aerout[:] = 0.0
    e.QTK = qtksav


def _bucle(e, m, qtksav, aerout):
    """Bucle de receptores de OCALC."""
    isrc = e.ISRC
    numtyp = e.NUMTYP
    nv = e.NVERT
    xvm = [0.0] * 6
    yvm = [0.0] * 6
    for irec in range(1, e.NUMREC + 1):
        e.IREC = irec
        # receptor dentro del foso real: no se calcula
        for i in range(1, nv + 2):
            xvm[i] = e.AXVERT[i, isrc]
            yvm[i] = e.AYVERT[i, isrc]
        e.XR = e.AXR[irec]
        e.YR = e.AYR[irec]
        if pnpoly(e.XR, e.YR, xvm, yvm, 4) > 0:
            _anular(e, aerout, qtksav, False)
            continue

        if e.EVONLY:
            raise NoTraducido("EVENT")
        xdep, width, length, xminr, xmaxr = calculo_area.ardist(e, irec)

        # receptor a barlovento o más allá de MAXDIST
        if xmaxr < 1.0 or e.DISTR > e.MAXDIST:
            _anular(e, aerout, qtksav, True)
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

        # receptor fuera del borde lateral del penacho
        if (abs(e.Y) - 0.5 * width) > 0.0:
            calculo_area.adisy(e, xmaxr)
            if (abs(e.Y) - 0.5 * width) >= 5.0 * e.SY:
                _anular(e, aerout, qtksav, True)
                continue

        funciones_dispersion.critds(e, e.HE)
        if e.URBSTAB:
            e.VP_FACT = e.VIRTPNT_URB[e.KST]
        else:
            e.VP_FACT = e.VIRTPNT_RUR[e.KST]
        xpoint = 1.5 * length + e.VP_FACT * width
        if (not e.FASTAREA and not e.FASTALL) or \
                ((e.FASTAREA or e.FASTALL) and e.X < xpoint):
            if e.ARDPLETE:
                if e.NPD == 0 and (e.LDGAS or e.LWGAS):
                    _depos("pdepg")(e, xdep)
                else:
                    e.DQCORG = 1.0
                    e.WQCORG = 1.0
                if e.NPD > 0 and (e.LDPART or e.LWPART):
                    _depos("pdep")(e, xdep)
                elif e.NPD > 0:
                    e.DQCOR[:] = 1.0
                    e.WQCOR[:] = 1.0
            for ityp in range(1, numtyp + 1):
                e.ITYP = ityp
                e.L_APLUME = True
                integracion_area.areain(e)
            e.ITYP = numtyp + 1
        else:
            if _punto_virtual(e, aerout, qtksav):
                continue

        if e.PVMRM or e.OLM or e.RUNTTRM or e.ARM2 or e.GRSM:
            # la suma a los grupos la hace después la rutina de la química del NO2
            if e.GRSM:
                if e.STABLE or (e.UNSTAB and e.HS >= e.ZI):
                    e.UCHM = e.UEFF
                else:
                    e.UCHM = e.UEFFD
                if e.UCHM != 0:
                    e.CHI_TTRAVCHM[irec, isrc] = max(0.0, e.HRVAL[1] * e.X / e.UCHM)
                else:
                    e.errhdl(e.PATH, m, "E", "601", "GRSM")
                    e.RUNERR = True
                    return
            calculo_area._guardar_chi(e, irec, isrc)
            e.HRVAL[:] = 0.0
            e.AERVAL[:] = 0.0
            aerout[:] = 0.0
            continue

        for igrp in range(1, e.NUMGRP + 1):
            e.IGRP = igrp
            resultados.sumval(e)
        e.HRVAL[:] = 0.0
        e.AERVAL[:] = 0.0
        aerout[:] = 0.0
    e.IREC = e.NUMREC + 1


def dentro_pit(e, isrc):
    """Receptores (índices 1..NUMREC) dentro del foso real de la fuente ISRC (PNPOLY > 0)."""
    xvm, yvm = vertices_pit(e, isrc)
    return [irec for irec in range(1, e.NUMREC + 1)
            if pnpoly(e.AXR[irec], e.AYR[irec], xvm, yvm, 4) > 0]


def _bucle_nucleo(e, qtksav, aerout):
    """Bucle de receptores de OCALC con el núcleo compilado del bucle de ACALC (nucleo.py), sin
    tocarlo. Para fosos, el bucle de OCALC es el de ACALC salvo en tres cosas, que aquí se
    resuelven fuera del núcleo:
      · los receptores dentro del foso real no se calculan: durante la llamada se llevan muy a
        barlovento del área efectiva (XMAXREC < 1, la rama que los anula) y se restauran después;
        los que quedan detrás del último receptor exterior no se pasan al núcleo (NUMREC menor) y
        se anulan aquí, para que el estado final (XR, X, DISTR...) sea el del original;
      · OCALC no aplica el serpenteo de las áreas (AREAMNDR): se desactiva durante la llamada;
      · la aproximación de fuente puntual de FASTAREA/FASTALL usa XEFF*YEFF: esas corridas van
        por ``_bucle`` (el núcleo tampoco admite FASTAREA).
    Diferencias inocuas: el núcleo escribe TTRMOUT(IREC,ISRC,11..13) con TTRM, que TTRM_CALC no
    lee para OPENPIT, y el mensaje 601 de GRSM (UEFF nulo, imposible) saldría con «ACALC»."""
    from . import nucleo
    isrc = e.ISRC
    numrec = e.NUMREC
    dentro = dentro_pit(e, isrc)
    sd = set(dentro)
    ult = numrec
    while ult >= 1 and ult in sd:
        ult -= 1
    axr, ayr = e.AXR, e.AYR
    guardados = [(irec, axr[irec], ayr[irec]) for irec in dentro if irec <= ult]
    # a 1e7 m a barlovento del centro del área efectiva: X = -1e7 en todos los vértices
    xlej = e.XCNTR + 1.0e7 * e.WDSIN
    ylej = e.YCNTR + 1.0e7 * e.WDCOS
    mndr = e.L_AREAMNDR
    try:
        for irec, _x, _y in guardados:
            axr[irec] = xlej
            ayr[irec] = ylej
        e.L_AREAMNDR = False
        e.NUMREC = ult
        if ult >= 1:
            nucleo.acalc_bucle(e, qtksav, aerout)
    finally:
        e.NUMREC = numrec
        e.L_AREAMNDR = mndr
        for irec, x, y in guardados:
            axr[irec] = x
            ayr[irec] = y
    # receptores interiores al final de la lista (rama PNPOLY del original)
    for irec in range(ult + 1, numrec + 1):
        e.IREC = irec
        e.XR = axr[irec]
        e.YR = ayr[irec]
        _anular(e, aerout, qtksav, False)
    e.IREC = numrec + 1


def _punto_virtual(e, aerout, qtksav):
    """Aproximación de fuente puntual de FASTAREA/FASTALL con el área efectiva del foso
    (QTK * XEFF * YEFF). Devuelve True si el receptor se salta (CYCLE RECEPTOR_LOOP)."""
    e.QTK = e.QTK * e.XEFF * e.YEFF
    e.SYINIT = 0.0
    if e.NPD == 0 and (e.LDGAS or e.LWGAS):
        _depos("pdepg")(e, e.X)
    else:
        e.DQCORG = 1.0
        e.WQCORG = 1.0
    if e.NPD > 0 and (e.LDPART or e.LWPART):
        _depos("pdep")(e, e.X)
    elif e.NPD > 0:
        e.DQCOR[:] = 1.0
        e.WQCOR[:] = 1.0
    calculo_area.centroid(e, e.X)
    if e.UNSTAB and e.HS < e.ZI:
        funciones_dispersion.pdf(e)
    calculo_area.heff(e, e.X)
    parametros_efectivos.iblval(e, e.X)
    if e.UNSTAB and e.HS < e.ZI:
        funciones_dispersion.pdf(e)
        calculo_area.heff(e, e.X)
    calculo_area.vdis(e, e.X)
    fyout = funciones_dispersion.fyplm(e, e.SY)
    e.FSUBY = fyout
    e.FSUBYD = e.FSUBY
    e.FSUBYN = e.FSUBYD
    e.FSUBY3 = 0.0
    if e.FSUBY == 0.0 and e.FSUBY3 == 0.0:
        if e.PVMRM or e.OLM or e.ARM2 or e.GRSM:
            calculo_area._cero_chi(e, e.IREC, e.ISRC)
        e.HRVAL[:] = 0.0
        e.AERVAL[:] = 0.0
        aerout[:] = 0.0
        e.QTK = qtksav
        return True
    if e.NPD == 0:
        adj = e.DQCORG * e.WQCORG
        if e.STABLE or (e.UNSTAB and e.HS >= e.ZI):
            e.HSBL = calculo_area.refl_ht(e, e.HE, e.X, 0.0, e.VSIGZ)
        elif e.UNSTAB:
            e.HSBL = 0.0
        funciones_dispersion.critds(e, e.HE)
        funciones_dispersion.pfract(e, e.HE)
        funciones_dispersion.fterm(e)
        calculo_area.aer_pchi(e, e.X, adj, e.VDEPG, 0, aerout)
        e.HRVAL[1:] = aerout[1:]
    else:
        for j in range(1, e.NPD + 1):
            e.HV = (e.X / e.US) * e.VGRAV[j]
            adj = e.PHI[j] * e.DQCOR[j] * e.WQCOR[j]
            if e.STABLE or (e.UNSTAB and e.HS >= e.ZI):
                e.HESETL = max(0.0, e.HE - e.HV)
                e.HSBL = calculo_area.refl_ht(e, e.HESETL, e.X, 0.0, e.VSIGZ)
            elif e.UNSTAB:
                e.HESETL = max(0.0, 0.5 * (e.HED1 + e.HED2) - e.HV)
                e.HSBL = 0.0
            funciones_dispersion.critds(e, e.HESETL)
            funciones_dispersion.pfract(e, e.HESETL)
            funciones_dispersion.fterm(e)
            calculo_area.aer_pchi(e, e.X, adj, e.VDEP[j], j, aerout)
            e.HRVAL[1:] = e.HRVAL[1:] + aerout[1:]
    e.QTK = qtksav
    return False


# ------------------------------------------------------------------------------------------
# inpsum.f: tabla de datos de las fuentes OPENPIT (PRTSRC) y receptores dentro del foso (CHKREC)
# ------------------------------------------------------------------------------------------
_F9082 = ("(//50X,'*** OPENPIT SOURCE DATA ***'//15X,'NUMBER EMISSION RATE',2X,'COORD (SW CORNER)',2X,"
          "'BASE     RELEASE  X-DIM     Y-DIM    ORIENT.',4X,'VOLUME',3X,'URBAN  EMISSION RATE',/3X,"
          "'SOURCE',7X,'PART. ',A11,7X,'X',8X,'Y',6X,'ELEV.    ','HEIGHT  OF PIT    OF PIT    OF PIT     OF PIT"
          "   ','SOURCE  SCALAR VARY',/4X,' ID         CATS.   /METER**2)  ',1X,2('(METERS) (METERS) '),"
          "2('(METERS)',2X),' (DEG.) ',3X,'(M**3)               BY'/66(' -')/)")
_F9083 = "(1X,A12,2X,A5,2X,E11.5,2F10.1,A8,F9.2,3(1X,F9.2),3X,E10.5,2X,A3,3X,A7)"
F9004 = "(29X,A12,3X,F13.1,1X,F13.1,5X,'     OPENPIT')"


def prtsrc_pit(e, o, cabecera, iqun):
    """Tabla «OPENPIT SOURCE DATA» de PRTSRC (va entre la de trincheras RLINE y la de BUOYLINE).
    O es la lista de líneas pendientes de PRTSRC, CABECERA su función de cambio de página
    (HEADER + formato) e IQUN el texto de las unidades de emisión."""
    indc = 0
    for i in range(1, e.NUMSRC + 1):
        if e.SRCTYP[i] != "OPENPIT":
            continue
        indc += 1
        urb = "YES" if e.URBSRC[i] == "Y" else "NO"
        cnpd = "METH2" if e.L_METHOD2[i] else fx(fwrite("(I4,1X)", int(e.INPD[i]))[0], 5)
        cazs = "    FLAT" if e.L_FLATSRC[i] else fwrite("(F8.1)", e.AZS[i])[0]
        if (indc - 1) % 40 == 0:
            cabecera(_F9082, iqun)
        o.extend(fwrite(_F9083, fx(e.SRCID[i], 12), cnpd, e.AQS[i], e.AXS[i], e.AYS[i], cazs, e.AHS[i],
                        e.AXINIT[i], e.AYINIT[i], e.AANGLE[i], e.AVOLUM[i], fx(urb, 3), fx(e.QFLAG[i], 7)))


def vertices_pit(e, isrc):
    """XVM, YVM de CHKREC/OCALC: los 5 vértices del foso real (índices 1..5)."""
    return ([0.0] + [e.AXVERT[k, isrc] for k in range(1, 6)],
            [0.0] + [e.AYVERT[k, isrc] for k in range(1, 6)])


# ------------------------------------------------------------------------------------------
# PVMRM con fuentes OPENPIT (calc1.f: PVMRM_CALC, MAJOR_CONT, MOLES_NOX)
# ------------------------------------------------------------------------------------------
def _major_cont(e, maxconc, idom):
    """MAJOR_CONT con la rama OPENPIT (el resto, como no2._major_cont)."""
    from . import quimica_no2
    isrc, irec = e.ISRC, e.IREC
    if e.SRCTYP[isrc] != "OPENPIT":
        quimica_no2._major_cont(e, maxconc, idom)
        return
    if not (e.CHI[irec, isrc, 1] >= 0.5 * maxconc):
        return
    calculo_area.setsrc(e)
    geometria(e)
    if e.EVONLY:
        raise NoTraducido("EVENT")
    calculo_area.ardist(e, irec)
    if e.DISTR > e.MAXDIST:
        return
    quimica_no2._contar(e, False)
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


def _moles_nox(e, idom):
    """MOLES_NOX con la rama OPENPIT (el resto, como no2._moles_nox). En la rama OPENPIT el
    original suma QEFF*XINIT*YINIT (no QTK: los factores de emisión variables no cuentan)."""
    from . import quimica_no2
    eps = 1.0e-5
    isrc, irec = e.ISRC, e.IREC
    if e.SRCTYP[isrc] != "OPENPIT":
        quimica_no2._moles_nox(e, idom)
        return
    calculo_area.setsrc(e)
    geometria(e)
    pitemi(e, e.QS)
    funciones_dispersion.emfact(e, e.QEFF)
    if e.EVONLY:
        raise NoTraducido("EVENT")
    calculo_area.ardist(e, irec)
    cwdist = e.Y
    dwdist = max(e.X, 1.0)
    fdom = e.FOPTS[irec, idom]
    h = e.HECNTR[irec, isrc]
    r = e.ANO2_RATIO[isrc]
    if (e.CWMIN - eps <= cwdist <= e.CWMAX + eps) and (e.DWMIN - eps <= dwdist <= e.DWMAX + eps):
        if e.HMNT - eps <= h <= e.HMXT + eps:
            qarea = e.QEFF * e.XINIT * e.YINIT
            e.QSUM = e.QSUM + qarea * (1.0 - fdom)
            e.SUM_NO2RAT = e.SUM_NO2RAT + r * qarea * (1.0 - fdom)
        if e.HMNH - eps <= (h - e.ZRT) <= e.HMXH + eps:
            qarea = e.QEFF * e.XINIT * e.YINIT
            e.QSUM = e.QSUM + qarea * fdom
            e.SUM_NO2RAT = e.SUM_NO2RAT + r * qarea * fdom
    # (la tercera fuente, penetrada, solo suma fuentes POINT)


def pvmrm_bucle(e, srcs, maxchi, domidx):
    """Bucle de receptores de PVMRM_CALC (copia en Python de no2._pvmrm_bucle) con las ramas
    OPENPIT del penacho dominante, MAJOR_CONT y MOLES_NOX. Se usa en lugar del núcleo numba y de
    no2._pvmrm_bucle cuando la corrida tiene fuentes OPENPIT."""
    from . import quimica_no2, perfiles
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
            if quimica_no2._psd_incluida(e, isrc, srcs):
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
            voldom = quimica_no2._plume_vol(e, distdom, irec, idom, 0.0, 0.0, width, 0.0)
        elif t == "OPENPIT":
            calculo_area.setsrc(e)
            geometria(e)
            pitemi(e, e.QS)
            funciones_dispersion.emfact(e, e.QEFF)
            if e.EVONLY:
                raise NoTraducido("EVENT")
            xdep, width, length, xminr, xmaxr = calculo_area.ardist(e, irec)
            distdom = max(e.X, 1.0)
            if e.PVMRM:
                calculo_area.adisy(e, distdom)
                if 4.3 * e.SY < width:
                    width = 4.3 * e.SY
            voldom = quimica_no2._plume_vol(e, distdom, irec, idom, 0.0, 0.0, width, 0.0)
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
            voldom = quimica_no2._plume_vol(e, distdom, irec, idom, 0.0, 0.0, width, 0.0)
        if e.UNSTAB and distdom >= e.XMIXED:
            bvert = 0.0
        else:
            bvert = fdom * (e.HMXH - e.HMNH) + (1.0 - fdom) * (e.HMXT - e.HMNT)
        if bvert > 0.0 or bvert3 > 0.0 or bhoriz > 0.0 or bhoriz3 > 0.0:
            volsum = quimica_no2._plume_vol(e, distdom, irec, idom, bvert, bvert3, bhoriz, bhoriz3)
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
        elif t == "OPENPIT":
            domnox = e.QEFF * e.XINIT * e.YINIT * (1.0 - rdom) * distdom / (udom * 46.0)
        else:
            domnox = e.QTK * (1.0 - rdom) * distdom / (udom * 46.0)
        e.QSUM = 0.0
        e.QSUM3 = 0.0
        e.SUM_NO2RAT = 0.0
        e.SUM3_NO2RAT = 0.0
        for isrc in range(1, ns + 1):
            e.ISRC = isrc
            if quimica_no2._psd_incluida(e, isrc, srcs):
                _moles_nox(e, idom)
        if e.QSUM == 0.0 and e.QSUM3 == 0.0:
            quimica_no2._aviso_411(e, irec)
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
                    quimica_no2.sumback_no2(e)
            e.IGRP = e.NUMGRP + 1
        elif srcs == 1:
            for isrc in range(1, ns + 1):
                for ityp in range(1, nt + 1):
                    c = e.PSDC[isrc]
                    if c == 1 or c == 2:
                        e.ABVAL[irec, ityp] = e.ABVAL[irec, ityp] + chi[irec, isrc, ityp] * pct
            e.ISRC = ns + 1
            quimica_no2.sumvalpsd(e, srcs)
        elif srcs == 2:
            for isrc in range(1, ns + 1):
                for ityp in range(1, nt + 1):
                    c = e.PSDC[isrc]
                    if c == 2 or c == 3:
                        e.BCVAL[irec, ityp] = e.BCVAL[irec, ityp] + chi[irec, isrc, ityp] * pct
            e.ISRC = ns + 1
            quimica_no2.sumvalpsd(e, srcs)
        e.HRVAL[:] = 0.0
        e.AERVAL[:] = 0.0
    e.IREC = e.NUMREC + 1
