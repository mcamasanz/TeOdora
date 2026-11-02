# -*- coding: utf-8 -*-
"""Traducción de AERMOD 26135 (US EPA, dominio público): integración numérica de las fuentes de
área (pitarea.f): AVERTS, AREAIN, PLUMEF, PSIDE, XWIDTH, PWIDTH, ZBRENT, PSIDE2, HPSORT, QATR3 y
QG2. Las rutinas de OPENPIT (ESCAPE, ADJEMI, AMFRAC, LWIND, PDEPTH, PTFRAC, PITEFF, PITEMI,
CTHETA) y las variantes FASTAREA (PSIDE_TOX, PSIDE2_TOX) quedan fuera de este módulo.

Rutinas externas que se llaman (misma convención: primer argumento `e`, los escalares de salida
se devuelven):
  · calculo_area.centroid(e, xarg), calculo_area.heff(e, xarg), calculo_area.adisy(e, xarg), calculo_area.adisz(e, xarg)
  · herefl = calculo_area.refl_ht(e, hearg, xarg, szbarg, vsigzarg)
  · pout = calculo_area.aer_achi(e, xarg, adj, vdinp, jin, fyarg)
  · calculo_area.debout(e)
  · calculo_area.pdep(e, xarg), calculo_area.pdepg(e, xarg)          (PDEP(XARG), PDEPG(XARG): fijan globales)
  · funciones_dispersion.pdf(e), funciones_dispersion.critds(e, hearg), funciones_dispersion.pfract(e, hearg), funciones_dispersion.fterm(e)
  · parametros_efectivos.iblval(e, xarg)
  · arise.afluxes(e), arise.adeltah(e, xarg)          (AFLUXES, ADELTAH(XARG) de arise.f)
  · dval = pside_tox(e, u1, u2), dval = pside2_tox(e) (FASTAREA; se buscan en este módulo al
    llamarlas y, si aún no existen, se lanza NoTraducido)

Los módulos hermanos se importan en el primer uso (`_Perezoso`): algunos aún no existen y calc1
importa a su vez este módulo. Las matrices de trabajo locales (AUX, ULIST, USEG...) son listas de
Python con índices 1..N (posición 0 sin usar); las globales de MAIN1 son las de `e`.
"""
import importlib
import math

from .formato import dsign


class _Perezoso:
    """Módulo hermano importado en el primer acceso; después se sustituye a sí mismo en los
    globales de este módulo por el módulo real (sin coste en las llamadas siguientes)."""

    __slots__ = ("_nombre",)

    def __init__(self, nombre):
        self._nombre = nombre

    def __getattr__(self, atr):
        mod = importlib.import_module("." + self._nombre, __package__)
        globals()[self._nombre] = mod
        return getattr(mod, atr)


calculo_area = _Perezoso("calculo_area")
funciones_dispersion = _Perezoso("funciones_dispersion")
parametros_efectivos = _Perezoso("parametros_efectivos")
arise = _Perezoso("arise")


def _rutina_tox(nombre):
    """PSIDE_TOX / PSIDE2_TOX (opción FASTAREA): fuera del alcance de este módulo."""
    f = globals().get(nombre)
    if f is None:
        from .estado import NoTraducido
        raise NoTraducido(nombre.upper() + " (opción FASTAREA)")
    return f


# Convergencia de QATR3 en PSIDE y PSIDE2 (PARAMETER locales)
_NDIM = 12
_IMIN = 5
_EPSR = 1.0e-2
_EPST = 1.0e-5

# Tabla GA de PWIDTH: distribución normal acumulada en pasos de 0.1 sigma (literales D0), 1..79
_GA = (0.0,
       0.0, .0001, .0001, .0002, .0002, .0003, .0005,
       .0007, .0010, .0013, .0019, .0026, .0035, .0047, .0062,
       .0082, .0107, .0139, .0179, .0227, .0287, .0359, .0446,
       .0548, .0668, .0808, .0968, .1151, .1357, .1587, .1841,
       .2119, .2420, .2742, .3085, .3445, .3821, .4207, .4602,
       .5000, .5398, .5793, .6179, .6555, .6915, .7258, .7580,
       .7881, .8159, .8413, .8643, .8849, .9032, .9192, .9332,
       .9452, .9554, .9641, .9713, .9773, .9821, .9861, .9893,
       .9918, .9938, .9953, .9965, .9974, .9981, .9987, .9990,
       .9993, .9995, .9997, .9998, .9998, .9999, .9999, 1.000)


def averts(e, xvin, yvin, xwd, ywd, numv):
    """AVERTS: vértices en el sistema de coordenadas de la dirección del viento (OPENPIT).
    Escribe xwd, ywd en sitio (índices 1..numv)."""
    for nsp in range(1, numv + 1):
        xwd[nsp] = -(xvin[nsp] * e.WDSIN + yvin[nsp] * e.WDCOS)
        ywd[nsp] = xvin[nsp] * e.WDCOS - yvin[nsp] * e.WDSIN


def areain(e):
    """AREAIN: concentración horaria de una fuente de área por integración numérica.
    Fija UVERT, VVERT, VNVERT, WVERT, IVERT, NSEGS, UASEGS, UBSEGS, LSEG y HRVAL(ITYP)
    (o RUNERR y el mensaje 406 si el número de lados supera NVMAX)."""
    modnam = "AREAIN"
    ucrit = 1.01
    val = 0.0
    e.UVERT[:] = 0.0
    e.VVERT[:] = 0.0
    kside = 0
    spa = e.SPA
    uvert = e.UVERT
    vvert = e.VVERT
    vnvert = e.VNVERT
    wvert = e.WVERT
    nvmax1 = e.NVMAX + 1

    for ncp in range(1, e.NVERT + 1):
        ua = spa[ncp, 1]
        ub = spa[ncp + 1, 1]
        va = spa[ncp, 2]
        vb = spa[ncp + 1, 2]
        if ua >= ucrit:
            kside = kside + 1
            if kside <= nvmax1:
                uvert[kside] = ua
                vvert[kside] = va
            else:
                e.errhdl(e.PATH, modnam, "E", "406", e.SRCID[e.ISRC])
                e.RUNERR = True
                return
        if (ua >= ucrit and ub < ucrit) or (ua < ucrit and ub >= ucrit):
            kside = kside + 1
            if kside <= nvmax1:
                uvert[kside] = ucrit
                vvert[kside] = va + (ucrit - ua) * (vb - va) / (ub - ua)
            else:
                e.errhdl(e.PATH, modnam, "E", "406", e.SRCID[e.ISRC])
                e.RUNERR = True
                return

    # (depuración omitida)

    qgo = False
    if kside > 2:
        qgo = True
        vnmin = 3.9
        vnmax = -3.9
        for ncp in range(1, kside + 1):
            ua = uvert[ncp]
            va = vvert[ncp]
            vnorm, wa = pwidth(e, ua, va)
            vnvert[ncp] = vnorm
            wvert[ncp] = wa
            vnmax = max(vnorm, vnmax)
            vnmin = min(vnorm, vnmin)
        if vnmin >= 3.9 or vnmax <= -3.9:
            qgo = False
        # (depuración omitida)

    # integración entre vértices u(1),u(2); u(2),u(3); etc.
    if qgo:
        # el primer punto se repite al final
        ksp = kside + 1
        if ksp <= nvmax1:
            uvert[ksp] = uvert[1]
            vvert[ksp] = vvert[1]
            vnvert[ksp] = vnvert[1]
            wvert[ksp] = wvert[1]
        else:
            e.errhdl(e.PATH, modnam, "E", "406", e.SRCID[e.ISRC])
            e.RUNERR = True
            return
        e.NSEGS = 0
        e.LSEG = False
        for ks in range(1, kside + 1):
            qgo = True
            e.IVERT = ks
            ua = uvert[ks]
            ub = uvert[ks + 1]
            dval = 0.0
            if abs(ua - ub) < 0.01:
                qgo = False
            if qgo and e.FASTAREA:
                dval = _rutina_tox("pside_tox")(e, ua, ub)
            elif qgo:
                dval = pside(e, ua, ub)
            val = val + dval
        if e.NSEGS > 0:
            e.LSEG = True
            if e.FASTAREA:
                dval = _rutina_tox("pside2_tox")(e)
            else:
                dval = pside2(e)
            val = val + dval

        # valor horario (el término 1/U ya está en VAL); 1/(2pi) para el penacho meandro
        if e.L_APLUME:
            e.HRVAL[e.ITYP] = abs(val) * e.QTK * e.EMIFAC[e.ITYP]
        else:
            e.HRVAL[e.ITYP] = abs(val) * e.QTK * e.EMIFAC[e.ITYP] * (1.0 / e.TWOPI)
    else:
        e.HRVAL[e.ITYP] = 0.0

    if e.DEBUG:
        calculo_area.debout(e)


def plumef(e, xarg):
    """PLUMEF: integrando de la fuente de área a la distancia xarg (m). Devuelve POUT.
    Fija XDIST, DQCORG/WQCORG o DQCOR/WQCOR, HV, HESETL, HSBL y lo que fijan las rutinas
    llamadas (CENTROID, PDF, HEFF, IBLVAL, ADISZ, ADISY, CRITDS, PFRACT, FTERM...)."""
    ptmp = 0.0
    pout = 0.0

    # XDIST para el agotamiento seco (F2INT)
    e.XDIST = xarg

    # factores de corrección por deposición
    if e.NPD == 0 and not e.ARDPLETE and (e.LDGAS or e.LWGAS):
        calculo_area.pdepg(e, xarg)
    elif not e.ARDPLETE:
        e.DQCORG = 1.0
        e.WQCORG = 1.0
    if not e.ARDPLETE and (e.LDPART or e.LWPART):
        calculo_area.pdep(e, xarg)
    elif not e.ARDPLETE and e.NPD > 0:
        e.DQCOR[:] = 1.0
        e.WQCOR[:] = 1.0

    # altura del centroide del penacho
    calculo_area.centroid(e, xarg)

    # coeficientes de la PDF convectiva
    if e.UNSTAB and (e.HS < e.ZI):
        funciones_dispersion.pdf(e)

    # altura efectiva (sobreelevación de aeronaves si AFTSRC = 'Y')
    if e.AFTSRC[e.ISRC] == "Y":
        arise.afluxes(e)
        arise.adeltah(e, xarg)
        calculo_area.heff(e, xarg)
    else:
        calculo_area.heff(e, xarg)

    # promedio en la capa de sobreelevación
    parametros_efectivos.iblval(e, xarg)

    # PDF y HEFF de nuevo para las alturas finales convectivas
    if e.UNSTAB and (e.HS < e.ZI):
        funciones_dispersion.pdf(e)
        if e.AFTSRC[e.ISRC] == "Y":
            arise.afluxes(e)
            arise.adeltah(e, xarg)
            calculo_area.heff(e, xarg)
        else:
            calculo_area.heff(e, xarg)

    # término lateral VAL (LSEG: VAL = 1, no hace falta sigma-y)
    if e.LSEG:
        calculo_area.adisz(e, xarg)
        val = 1.0
    else:
        vt = xwidth(e, xarg)
        vn, val = pwidth(e, xarg, vt)
        calculo_area.adisz(e, xarg)

    if e.NPD == 0:
        # gases: sin inclinación del penacho
        e.HV = 0.0
        adj = e.DQCORG * e.WQCORG

        if e.STABLE or (e.UNSTAB and (e.HS >= e.ZI)):
            # altura de la "superficie reflectora efectiva"
            if e.AFTSRC[e.ISRC] == "Y":
                e.HSBL = calculo_area.refl_ht(e, e.HE, xarg, e.SZB, e.VSIGZ)
            else:
                e.HSBL = calculo_area.refl_ht(e, e.HE, xarg, 0.0, e.VSIGZ)
        elif e.UNSTAB:
            e.HSBL = 0.0

        funciones_dispersion.critds(e, e.HE)
        funciones_dispersion.pfract(e, e.HE)
        funciones_dispersion.fterm(e)

        pout = calculo_area.aer_achi(e, xarg, adj, e.VDEPG, 0, val)

    else:
        # partículas: bucle en los tamaños
        for j in range(1, e.NPD + 1):
            # inclinación del penacho por sedimentación
            e.HV = (xarg / e.US) * e.VGRAV[j]

            # fracción másica y agotamiento en la fuente
            adj = e.PHI[j] * e.DQCOR[j] * e.WQCOR[j]

            if e.STABLE or (e.UNSTAB and (e.HS >= e.ZI)):
                e.HESETL = max(0.0, e.HE - e.HV)
                if e.AFTSRC[e.ISRC] == "Y":
                    e.HSBL = calculo_area.refl_ht(e, e.HESETL, xarg, e.SZB, e.VSIGZ)
                else:
                    e.HSBL = calculo_area.refl_ht(e, e.HESETL, xarg, 0.0, e.VSIGZ)
            elif e.UNSTAB:
                e.HESETL = max(0.0, 0.5 * (e.HED1 + e.HED2) - e.HV)
                e.HSBL = 0.0

            funciones_dispersion.critds(e, e.HESETL)
            funciones_dispersion.pfract(e, e.HESETL)
            funciones_dispersion.fterm(e)

            ptmp = calculo_area.aer_achi(e, xarg, adj, e.VDEP[j], j, val)
            pout = pout + ptmp

    return pout


def pside(e, u1, u2):
    """PSIDE: integra el lado IVERT del polígono entre u1 y u2 según los casos de anchura
    normalizada fuera de [-3.9, 3.9]. Devuelve DVAL. Fija NSEGS, UASEGS, UBSEGS."""
    aux = [0.0] * (_NDIM + 1)

    dval = 0.0
    u = [0.0, 0.0, 0.0]
    vn = [0.0, 0.0, 0.0]
    for i in (1, 2):
        ks = e.IVERT + i - 1
        u[i] = e.UVERT[ks]
        vn[i] = e.VNVERT[ks]

    iminus = 0
    iplus = 0
    uminus = -1.0
    uplus = -1.0
    for i in (1, 2):
        if vn[i] < -3.9:
            iminus = i + iminus
        if vn[i] > 3.9:
            iplus = i + iplus

    if iplus == 1 or iplus == 2:
        uplus = zbrent(e, 1, u[1], u[2], vn[1], vn[2], 1.0e-3, uplus)
    if iminus == 1 or iminus == 2:
        uminus = zbrent(e, -1, u[1], u[2], vn[1], vn[2], 1.0e-3, uminus)

    # (depuración omitida)

    # el caso depende de iplus, iminus
    if iplus == 0:
        if iminus == 0:
            # caso 1
            dval, icon, nout = qatr3(e, u1, u2, _EPSR, _EPST, _NDIM, _IMIN, aux)
        elif iminus == 3:
            # caso 2
            dval = 0.0
        elif iminus == 1:
            # caso 4
            dval, icon, nout = qatr3(e, uminus, u2, _EPSR, _EPST, _NDIM, _IMIN, aux)
        else:
            # caso 5
            dval, icon, nout = qatr3(e, u1, uminus, _EPSR, _EPST, _NDIM, _IMIN, aux)

    elif iplus == 1:
        e.NSEGS = e.NSEGS + 1
        e.UASEGS[e.NSEGS] = u1
        e.UBSEGS[e.NSEGS] = uplus
        if iminus == 0:
            # caso 7
            dval, icon, nout = qatr3(e, uplus, u2, _EPSR, _EPST, _NDIM, _IMIN, aux)
        else:
            # caso 9
            dval, icon, nout = qatr3(e, uplus, uminus, _EPSR, _EPST, _NDIM, _IMIN, aux)

    elif iplus == 2:
        e.NSEGS = e.NSEGS + 1
        e.UASEGS[e.NSEGS] = uplus
        e.UBSEGS[e.NSEGS] = u2
        if iminus == 0:
            # caso 6
            dval, icon, nout = qatr3(e, u1, uplus, _EPSR, _EPST, _NDIM, _IMIN, aux)
        else:
            # caso 8
            dval, icon, nout = qatr3(e, uminus, uplus, _EPSR, _EPST, _NDIM, _IMIN, aux)

    else:
        # caso 3
        e.NSEGS = e.NSEGS + 1
        e.UASEGS[e.NSEGS] = u1
        e.UBSEGS[e.NSEGS] = u2

    # (depuración omitida)

    return dval


def xwidth(e, u):
    """XWIDTH: coordenada transversal del lado IVERT para la coordenada u. Devuelve XOUT."""
    iv = e.IVERT
    u1 = e.UVERT[iv]
    u2 = e.UVERT[iv + 1]
    v1 = e.VVERT[iv]
    v2 = e.VVERT[iv + 1]
    return v1 + (u - u1) * (v2 - v1) / (u2 - u1)


def pwidth(e, xarg, v1):
    """PWIDTH: anchura normalizada VN = v1/SY y fracción del penacho WIDTH (tabla GA).
    Devuelve (VN, WIDTH). Fija SY (y lo que fijan CENTROID, PDF, HEFF, IBLVAL, ADISY).
    Sin L_APLUME (penacho meandro) devuelve VN = 0 y WIDTH = ln(v1 + sqrt(x² + v1²))."""
    width = 0.0
    vn = 0.0

    if xarg == 0.0:
        e.SY = 1.0
        vn = v1
        width = vn
        return vn, width

    # sigma-y del penacho meandro
    if not e.L_APLUME:
        s = v1 + math.sqrt(xarg * xarg + v1 * v1)
        width = math.log(s) if s > 0.0 else (-math.inf if s == 0.0 else math.nan)
        return vn, width

    # altura del centroide del penacho
    calculo_area.centroid(e, xarg)

    # coeficientes de la PDF convectiva
    if e.UNSTAB and (e.HS < e.ZI):
        funciones_dispersion.pdf(e)

    # altura efectiva (sobreelevación de aeronaves si AFTSRC = 'Y')
    if e.AFTSRC[e.ISRC] == "Y":
        arise.afluxes(e)
        arise.adeltah(e, xarg)
        calculo_area.heff(e, xarg)
    else:
        calculo_area.heff(e, xarg)

    # promedio en la capa de sobreelevación
    parametros_efectivos.iblval(e, xarg)

    # sigma-y
    calculo_area.adisy(e, xarg)

    vn = v1 / e.SY
    temp = 10.0 * vn + 40.0
    # IDINT a INTEGER*4: fuera de rango (o NaN) Intel da -2147483648
    itemp = int(temp) if -2147483649.0 < temp < 2147483648.0 else -2147483648
    width = 0.0

    if itemp > 78:
        width = 1.0000
    else:
        if itemp >= 1:
            width = _GA[itemp] + (temp - float(itemp)) * (_GA[itemp + 1] - _GA[itemp])

    return vn, width


def zbrent(e, ifd, x1, x2, vn1, vn2, tol, outval):
    """ZBRENT: método de Brent para la u en la que VN = ifd*3.9 entre x1 y x2.
    Devuelve OUTVAL (entrada/salida: si VN-ifd*3.9 no cambia de signo en el intervalo, el
    original no lo asigna y se devuelve el valor de entrada). No usa MAIN1 directamente, pero
    llama a XWIDTH y PWIDTH, que sí."""
    itmax = 10
    epsz = 1.0e-3

    e1 = 0.0
    c1 = 0.0
    d1 = 0.0          # sin inicializar en el original; nunca se lee antes de asignarse

    a1 = x1
    b1 = x2
    fa = vn1 - float(ifd) * 3.9
    fb = vn2 - float(ifd) * 3.9

    if fb * fa <= 0.0:
        fc = fb
        for _it in range(1, itmax + 1):
            if fb * fc > 0.0:
                c1 = a1
                fc = fa
                d1 = b1 - a1
                e1 = d1
            if abs(fc) < abs(fb):
                a1 = b1
                b1 = c1
                c1 = a1
                fa = fb
                fb = fc
                fc = fa
            tol1 = 2.0 * epsz * abs(b1) + 0.5 * tol
            xm = 0.5 * (c1 - b1)
            if abs(xm) <= tol1 or fb == 0.0:
                outval = b1
                return outval
            if abs(e1) >= tol1 and abs(fa) > abs(fb):
                s1 = fb / fa
                if a1 == c1:
                    p1 = 2.0 * xm * s1
                    q1 = 1.0 - s1
                else:
                    q1 = fa / fc
                    r1 = fb / fc
                    p1 = s1 * (2.0 * xm * q1 * (q1 - r1) - (b1 - a1) * (r1 - 1.0))
                    q1 = (q1 - 1.0) * (r1 - 1.0) * (s1 - 1.0)
                if p1 > 0.0:
                    q1 = -q1
                p1 = abs(p1)
                if 2.0 * p1 < min(3.0 * xm * q1 - abs(tol1 * q1), abs(e1 - q1)):
                    e1 = d1
                    d1 = p1 / q1
                else:
                    d1 = xm
                    e1 = d1
            else:
                d1 = xm
                e1 = d1
            a1 = b1
            fa = fb
            if abs(d1) > tol1:
                b1 = b1 + d1
            else:
                b1 = b1 + dsign(tol1, xm)
            v1 = xwidth(e, b1)
            vn, w1 = pwidth(e, b1, v1)
            fb = vn - float(ifd) * 3.9
        outval = b1

    return outval


def pside2(e):
    """PSIDE2: integra los segmentos con |VN| > 3.9 eliminando solapes. Devuelve DVAL.
    Modifica UASEGS/UBSEGS (los ordena en cada segmento) y fija NSEGS."""
    aux = [0.0] * (_NDIM + 1)

    nsegs = e.NSEGS
    uasegs = e.UASEGS
    ubsegs = e.UBSEGS
    nvmax = e.NVMAX
    nvmax2 = e.NVMAX2
    # matrices locales ULIST(NVMAX2), USEG(NVMAX,2), USIGN(NVMAX), USEGF(NVMAX); se dimensionan
    # con holgura para no fallar donde el original escribiría fuera de rango
    n1 = max(nvmax2, 2 * nsegs) + 1
    ulist = [0.0] * n1
    useg1 = [0.0] * n1
    useg2 = [0.0] * n1
    usign = [0] * (max(nvmax, nsegs) + 1)
    usegf = [0] * n1

    j = 1
    for i in range(1, nsegs + 1):
        ulist[j] = uasegs[i]
        j = j + 1
        ulist[j] = ubsegs[i]
        j = j + 1
    npts = 2 * nsegs

    hpsort(npts, ulist, nvmax2)

    for i in range(1, nsegs + 1):
        usign[i] = 1
        if uasegs[i] > ubsegs[i]:
            usign[i] = -1
            temp = uasegs[i]
            uasegs[i] = ubsegs[i]
            ubsegs[i] = temp
        if uasegs[i] == ubsegs[i]:
            usign[i] = 0
    iseg = 0

    for i in range(2, npts + 1):
        u1 = ulist[i - 1]
        u2 = ulist[i]
        ufac = 0
        # compara el segmento [u1,u2] con cada ua,ub
        if u1 != u2:
            for j in range(1, nsegs + 1):
                if u1 >= uasegs[j] and u2 <= ubsegs[j]:
                    ufac = ufac + usign[j]
            # tabla de segmentos y factores
            if ufac != 0:
                iseg = iseg + 1
                useg1[iseg] = u1
                useg2[iseg] = u2
                usegf[iseg] = ufac

    # consolida segmentos si iseg > 1
    e.NSEGS = iseg
    nsegs = iseg
    if nsegs > 1:
        for iseg in range(2, nsegs + 1):
            ltest1 = useg1[iseg] == useg2[iseg - 1]
            ltest2 = usegf[iseg] * usegf[iseg - 1] > 0
            if ltest1 and ltest2:
                usegf[iseg - 1] = 0
                useg1[iseg] = useg1[iseg - 1]
    dval = 0.0
    if nsegs > 0:
        for iseg in range(1, nsegs + 1):
            if usegf[iseg] != 0:
                uav = useg1[iseg]
                ubv = useg2[iseg]
                ufac = usegf[iseg]
                tmpval, icon, nout = qatr3(e, uav, ubv, _EPSR, _EPST, _NDIM, _IMIN, aux)
                dval = dval + float(ufac) * tmpval

    # (depuración omitida)

    return dval


def hpsort(nvar, uvar, idim):
    """HPSORT: ordenación por montículo (heapsort) de uvar[1..nvar], en sitio. Rutina pura (no
    usa globales): no lleva `e`. idim (dimensión declarada) no se usa."""
    ilmid = nvar // 2 + 1
    ir = nvar

    while True:
        if ilmid > 1:
            ilmid = ilmid - 1
            ru = uvar[ilmid]
        else:
            ru = uvar[ir]
            uvar[ir] = uvar[1]
            ir = ir - 1
            if ir == 1:
                uvar[1] = ru
                # terminado
                return

        i = ilmid
        j = ilmid + ilmid

        while j <= ir:
            if j < ir:
                if uvar[j] < uvar[j + 1]:
                    j = j + 1
            if ru < uvar[j]:
                uvar[i] = uvar[j]
                i = j
                j = 2 * j
            else:
                j = ir + 1

        uvar[i] = ru


def qatr3(e, xl, xu, eps, epst, ndim, imin, aux):
    """QATR3: integral de PLUMEF entre xl y xu por Romberg (adaptación de DQATR de IBM SSP).
    aux (índices 1..ndim) es la matriz de trabajo, modificada en sitio.
    Devuelve (Y, IER, I): integral, estado (0 convergió, 2 no convergió en ndim pasos) y número
    de pasos. En la salida temprana (h = 0 o integrando nulo) el original no asigna I: se
    devuelve None (los llamantes no lo usan)."""
    # AUX(:) = 0
    for k in range(1, ndim + 1):
        aux[k] = 0.0

    # preparación del bucle de Romberg
    p1 = plumef(e, xl)
    p2 = plumef(e, xu)
    aux[1] = 0.5 * (p1 + p2)
    h = xu - xl

    if h == 0.0 or aux[1] == 0.0:
        ier = 0
        y = 0.0
        return y, ier, None

    hh = h
    delt2 = 0.0
    p = 1.0
    jj = 1

    for i in range(2, ndim + 1):
        y = aux[1]
        hd = hh
        hh = 0.5 * hh
        p = 0.5 * p
        x = xl + hh
        sm = 0.0

        for _j in range(1, jj + 1):
            p1 = plumef(e, x)
            sm = sm + p1
            x = x + hd

        # nueva aproximación por la regla de los trapecios
        aux[i] = 0.5 * aux[i - 1] + p * sm

        # extrapolación de Romberg
        q = 1.0
        ji = i - 1
        for j in range(1, ji + 1):
            ii = i - j
            q = q + q
            q = q + q
            aux[ii] = aux[ii + 1] + (aux[ii + 1] - aux[ii]) / (q - 1.0)

        # error absoluto
        delt2 = abs(y - aux[1])

        if i >= imin:
            # criterios de convergencia
            if abs(aux[1]) < epst:
                # umbral inferior
                ier = 0
                y = h * aux[1]
                return y, ier, i
            elif delt2 <= eps * abs(aux[1]):
                # error relativo
                ier = 0
                y = h * aux[1]
                return y, ier, i
            elif abs(hh) < 1.0:
                # paso mínimo < 1 m
                ier = 0
                y = h * aux[1]
                return y, ier, i

        jj = jj + jj

    # sin convergencia en el número máximo de pasos (I = NDIM+1 al salir del DO)
    ier = 2
    y = h * aux[1]
    return y, ier, ndim + 1


def qg2(e, xl, xu):
    """QG2: integral de PLUMEF entre xl y xu por cuadratura de Gauss de 2 puntos. Devuelve Y."""
    a = 0.5 * (xu + xl)
    b = xu - xl
    y = 0.2886751 * b
    p1 = plumef(e, a + y)
    p2 = plumef(e, a - y)
    y = 0.5 * b * (p1 + p2)
    return y
