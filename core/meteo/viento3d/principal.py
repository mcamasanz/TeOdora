# -*- coding: utf-8 -*-
"""Programa principal: fichero de control -> CALMET.DAT 2.0 (o PACOUT.DAT con IFORMO=2).

Alcance (ver ../../README.md): IPROG=14 (pronóstico como campo inicial, uno o varios 3D.DAT),
NOOBS=2 (sin observaciones), NOOBS=1 (estaciones de superficie del SURF.DAT + pronóstico en
altura) o NOOBS=0 (además, sondeos UPn.DAT), ITPROG=2, 1 (temperatura de superficie de las
estaciones) o 0 (temperatura 3D de los sondeos), ICLOUD=2 o 0, efectos cinemáticos (IKINE),
O'Brien (IOBR) y minimización de la divergencia, barreras (NBAR), extrapolación IEXTRP ±1 a ±4,
estaciones sobre el agua (SEAn.DAT) con OCD (ICOARE=0) o COARE (ICOARE=10, 11, 12), IMIXH ±1 y ±2,
ITWPROG=0 y 1, regiones de brisa (LLBREZE), pluviómetros (PRECIP.DAT), proyecciones UTM, LCC y TTM.
Lo que no está implementado se rechaza con NoImplementado; las configuraciones con las que el
original se detiene, con ErrorOriginal.
"""
import datetime as dt
import math
import sys
import time
from pathlib import Path

import numpy as np

from . import fichero_viento, entradas, lluvia, mar, micromet, observaciones, prognostico, proyeccion, sol, viento
from .control import Control
from .malla import Malla

PROGRAMA = "CALMET_PY (CIRCE)"
MODO_PSI_W = "anterior"
PRUEBA_T2 = 0
AV_INICIAL = False    # promedio de la altura convectiva con el viento final (True: con el inicial)
VERSION = "0.1"
NIVEL = "261018"
IRH_SIN_DATO = 80     # humedad relativa (%) con NOOBS=1 e ITPROG=2 [caja negra: fija, no depende
                      # de las estaciones ni del 3D.DAT]


class NoImplementado(Exception):
    pass


class ErrorOriginal(Exception):
    """Configuración con la que el original se detiene: el motor propio se detiene igual."""


def _reales(c, nombre):
    v = c.lista(nombre)
    return [float(x) for x in v[-1]] if v else []


def _extrapolacion_semejanza(obs, dat, malla, p, z0, t1, t1p, nub, qh_dia, rho, hraw, psi, agua,
                             hem):
    """IEXTRP=±4: L y altura de mezcla de cada estación con su viento observado y los campos de
    su celda (balance de energía de día, Venkatram de noche, como en la malla) y función
    (k, ws, wd, usar) -> (ws_k, wd_k, usar_k) con el perfil de semejanza y el giro de van Ulden y
    Holtslag ([UG] ec. 2-21, 2-22, tabla 2-1) en las capas cuya cara superior no pasa de la
    altura de mezcla de la estación [caja negra] [O7]."""
    j, i = obs.jc, obs.ic
    ws = np.maximum(dat[:, 0], 0.0)
    z0s = z0[j, i]
    ts, rs, ns = t1[j, i], rho[j, i], nub[j, i]
    qd = qh_dia[j, i]
    ud, ld = micromet.ustar_l_diurno(ws, z0s, np.maximum(qd, 1e-6), ts, rs)
    un, ln_, _ = micromet.ustar_l_estable(ws, z0s, ts, ns)
    dia = qd > 0
    ust = np.where(dia, ud, un)
    el = np.where(dia, ld, ln_)
    nb = np.sqrt(micromet.G / t1p[j, i] * psi[j, i])
    hmec = p["CONSTB"] * ust / np.sqrt(p["FCORIOL"] * nb)
    hest = np.minimum(p["CONSTN"] * ust ** 1.5, 0.4 * np.sqrt(ust * np.abs(el) / p["FCORIOL"]))
    zi = np.clip(np.where(dia, np.maximum(hraw[j, i], hmec), hest), p["ZIMIN"], p["ZIMAX"])
    w = agua[j, i]
    if w.any():
        uw = micromet.ustar_agua(ws)
        el = np.where(w, micromet.EL_NEUTRO, el)
        zi = np.where(w, np.clip(p["CONSTW"] / p["FCORIOL"] * uw, p["ZIMINW"], p["ZIMAXW"]), zi)
    za = np.array([e["zanem"] for e in obs.est])
    dh = observaciones.giro_200(el)
    signo = 1.0 if hem == "N" else -1.0

    def extra(k, ws_, wd_, usar):
        zk = malla.zc[k]
        r = observaciones.perfil_semejanza(1.0, za, zk, z0s, el)
        giro = signo * (observaciones.giro(zk, dh) - observaciones.giro(za, dh))
        return ws_ * r, wd_ + giro, usar & (malla.zface[k + 1] <= zi)
    return extra


def _adiabatica(tk, ts, h, adiab, malla, caras=None):
    """Temperatura adiabática bajo la altura de mezcla convectiva h.

    Con el pronóstico (ITPROG=1, 2): T = T₁ − 0,0098 (z − z₁) en las capas con el centro por
    debajo de h [T4]. Con los sondeos (ITPROG=0, caras = temperatura de las caras): T = T₁ −
    0,0098 z en las capas que quedan enteras por debajo de h y, en la que contiene h, la media
    ponderada por espesores de los tres puntos (cara inferior y h adiabáticas, cara superior del
    sondeo) ([UG] sec. 2.3.2, paso 6; caja negra) [T7]."""
    tk = tk.copy()
    zc, zf = malla.zc, malla.zface
    if caras is None:
        for kk in range(len(zc)):
            tk[kk] = np.where(adiab[kk], ts - 0.0098 * (zc[kk] - zc[0]), tk[kk])
        return tk
    for kk in range(1, len(zc)):
        lleno = zf[kk + 1] <= h
        tapa = (zf[kk] < h) & ~lleno
        tb = ts - 0.0098 * zf[kk]
        th = ts - 0.0098 * h
        mezcla = ((tb + th) * (h - zf[kk]) + (th + caras[kk + 1]) * (zf[kk + 1] - h)) / (
            2.0 * (zf[kk + 1] - zf[kk]))
        tk[kk] = np.where(lleno, ts - 0.0098 * zc[kk], np.where(tapa, mezcla, tk[kk]))
    return tk


def _media_dos_tramos(t0, g1, g2, h, za, zb):
    """Media en [za, zb] del perfil T(z) = t0 + g1·z bajo h y T(h) + g2·(z − h) encima."""
    def prim(z):
        # integral de 0 a z del perfil
        bajo = np.minimum(z, h)
        sobre = np.maximum(z - h, 0.0)
        return t0 * z + 0.5 * g1 * bajo ** 2 + g1 * h * sobre + 0.5 * g2 * sobre ** 2
    return (prim(zb) - prim(za)) / (zb - za)


ZI_T_AGUA = lambda zi, zi_agua: zi


def _vientos_mar(dm, dmar, po, malla, p, icoare, hem, alto=None, h_agua=None, agua=None,
                 olas_boya=None, icool=0):
    """Vientos por capa de las estaciones sobre el agua para el paso 2: el observado en la capa 1
    y, según IEXTRP, extrapolado como el de las estaciones de superficie (±3: × FEXTR2; ±4: perfil
    de semejanza con la L y la z0 de la propia estación —OCD o COARE con su viento— y el giro de
    la tabla 2-1, hasta su altura de mezcla) [caja negra: boya con R2 = 1000 km] [W7]."""
    n, nz = len(dm["ws"]), malla.nz
    ws, wd = dm["ws"], dm["wd"]
    validas = ~np.isnan(ws) & ~np.isnan(wd)
    validas &= np.where(validas, ws, 0.0) >= 0
    wsv = np.where(validas, ws, 0.0)
    wdv = np.where(validas, wd, 0.0)
    U = np.zeros((n, nz))
    V = np.zeros((n, nz))
    OK = np.zeros((n, nz), bool)
    U[:, 0], V[:, 0] = observaciones._uv(wsv, wdv)
    OK[:, 0] = validas
    iextrp = abs(int(po["IEXTRP"]))
    extrapola = validas & ((wsv > 0) | bool(po["ICALM"]))
    if alto is not None and po.get("RMIN2", -1.0) > 0:
        dsu = np.hypot(dm["x"][:, None] - alto["x"][None], dm["y"][:, None] - alto["y"][None]) / 1000.0
        extrapola &= ~(dsu < po["RMIN2"] * malla.dx / 1000.0).any(axis=1)     # [O20]
    if iextrp == 2:
        # potencial con el exponente del uso del suelo de la celda de la estación (anemómetro a
        # 10 m) ([UG] ec. 2-19) [O19]
        ic = np.clip(((dm["x"] - malla.x0) // malla.dx).astype(int), 0, malla.nx - 1)
        jc = np.clip(((dm["y"] - malla.y0) // malla.dx).astype(int), 0, malla.ny - 1)
        pot = np.where(agua[jc, ic], 0.286, 0.143) if agua is not None else 0.286
        U[:, 0], V[:, 0] = observaciones._uv(wsv * (malla.zc[0] / 10.0) ** pot, wdv)
        for k in range(1, nz):
            U[:, k], V[:, k] = observaciones._uv(wsv * (malla.zc[k] / 10.0) ** pot, wdv)
            OK[:, k] = extrapola
    elif iextrp == 3:
        for k in range(1, nz):
            f = po["FEXTR2"][min(k, len(po["FEXTR2"]) - 1)]
            U[:, k], V[:, k] = observaciones._uv(wsv * f, wdv)
            OK[:, k] = extrapola
    elif iextrp == 4:
        zow = np.where(np.isnan(dm["z"]), 10.0, dm["z"])
        ust, el, _, z0 = mar.flujos(icoare, np.maximum(wsv, 1e-3), dm["Ta_def"], dm["dT"],
                                    dm["rh_def"], zow, olas_boya, icool)
        zi = p["CONSTW"] / p["FCORIOL"] * ust
        if h_agua is not None:
            # con la convectiva sobre el agua de la hora anterior en la celda de la estación
            ic = np.clip(((dm["x"] - malla.x0) // malla.dx).astype(int), 0, malla.nx - 1)
            jc = np.clip(((dm["y"] - malla.y0) // malla.dx).astype(int), 0, malla.ny - 1)
            zi = np.maximum(zi, h_agua[jc, ic])
        zi = np.clip(zi, p["ZIMINW"], p["ZIMAXW"])
        zi = np.where(np.isnan(dm["zi"]), zi, dm["zi"])
        dh = observaciones.giro_200(el)
        # el giro de las estaciones sobre el agua va al revés que el de las de tierra (en el
        # hemisferio norte se resta) [caja negra: boya a 180° con L = −34 m: 178,3°/176,1°/172,6°]
        signo = -1.0 if hem == "N" else 1.0
        for k in range(1, nz):
            zk = malla.zc[k]
            r = observaciones.perfil_semejanza(1.0, 10.0, zk, z0, el)
            giro = signo * (observaciones.giro(zk, dh) - observaciones.giro(10.0, dh))
            U[:, k], V[:, k] = observaciones._uv(wsv * r, wdv + giro)
            OK[:, k] = extrapola & (malla.zface[k + 1] <= zi)
    return {"d": dmar, "u": U, "v": V, "ok": OK, "x": dm["x"], "y": dm["y"]}


def ejecutar(argv=None, carpeta=None):
    argv = list(sys.argv[1:] if argv is None else argv)
    carpeta = Path(carpeta or ".")
    ctl_path = carpeta / (argv[0] if argv else "CALMET.INP")
    texto = ctl_path.read_text(errors="ignore")
    c = Control(texto)
    lc = c.logico("LCFILES", True)
    nombre = lambda n, d: (c.cadena(n, d) or d).strip()
    fmin = (lambda s: s.lower()) if lc else (lambda s: s.upper())
    f_geo = carpeta / fmin(nombre("GEODAT", "GEO.DAT"))
    f_3d = carpeta / fmin(nombre("M3DDAT", "3D.DAT"))
    f_cld = carpeta / fmin(nombre("CLDDAT", "CLOUD.DAT"))
    f_out = carpeta / fmin(nombre("METDAT", "CALMET.DAT"))

    noobs, itprog = c.entero("NOOBS", 0), c.entero("ITPROG", 0)
    if noobs not in (0, 1, 2):
        raise NoImplementado("NOOBS=%d" % noobs)
    if itprog not in (0, 1, 2) or (itprog == 1 and noobs == 2) or (itprog == 0 and noobs != 0):
        raise NoImplementado("ITPROG=%d con NOOBS=%d (ITPROG=0 solo con sondeos, NOOBS=0; "
                             "ITPROG=1 con NOOBS=0 o 1)" % (itprog, noobs))
    if c.entero("IPROG", 14) != 14:
        raise NoImplementado("solo IPROG=14")
    if c.entero("IWFCOD", 1) == 0:
        raise ErrorOriginal("IWFCOD=0 con IPROG=14: calmet.exe 5.8.5 se detiene («The Diagnostic "
                            "Wind module must be selected if MM5 model results are used as the "
                            "Initial Guess Field»)")
    icloud = c.entero("ICLOUD", 0)
    if not (icloud == 2 or (icloud == 0 and noobs < 2)):
        raise NoImplementado("solo ICLOUD=2, o ICLOUD=0 con estaciones")
    if any(c.entero("IDIOPT%d" % n, 0) for n in range(1, 6)):
        raise NoImplementado("IDIOPT1-5 (datos preprocesados de DIAG.DAT)")
    ikine, iobr = c.entero("IKINE", 0), c.entero("IOBR", 0)
    alpha_kin = c.real("ALPHA", 0.1)
    nssta = c.entero("NSSTA", 0) if noobs < 2 else 0
    nusta = c.entero("NUSTA", 0) if noobs == 0 else 0
    npsta = c.entero("NPSTA", -1)
    sin_formato = ("el formato de registros del fichero sin formato de SMERGE/PMERGE no está "
                   "publicado y no se ha podido reconstruir por caja negra")
    if npsta > 0 and c.entero("IFORMP", 2) != 2:
        raise NoImplementado("PRECIP.DAT sin formato (IFORMP=%d): %s" % (c.entero("IFORMP", 2),
                                                                         sin_formato))
    if icloud == 2 and c.entero("IFORMC", 2) != 2:
        raise NoImplementado("CLOUD.DAT sin formato (IFORMC=%d)" % c.entero("IFORMC", 2))
    nowsta = c.entero("NOWSTA", 0) if noobs < 2 else 0
    icoare = c.entero("ICOARE", 10)
    if icoare in (-11, -12):
        raise NoImplementado("ICOARE=%d (oleaje observado: exige un SEA.DAT de versión > 2.0 cuyo "
                             "formato no está publicado)" % icoare)
    if icoare not in (0, 10, 11, 12):
        raise NoImplementado("ICOARE=%d" % icoare)
    imixh = c.entero("IMIXH", 1)
    if imixh not in (1, -1, 2, -2):
        raise NoImplementado("IMIXH=%d" % imixh)
    itwprog = c.entero("ITWPROG", 0)
    if itwprog not in (0, 1, 2):
        raise NoImplementado("ITWPROG=%d" % itwprog)
    if itwprog == 2 and nowsta > 0:
        raise NoImplementado("ITWPROG=2 con estaciones sobre el agua (SEA.DAT)")
    # piel fría de COARE (ICOOL) [W17]; la capa cálida (IWARM) no se ha reproducido [W15]
    icool = c.entero("ICOOL", 0) if icoare != 0 else 0
    if c.entero("IWARM", 0) and icoare != 0 and (nowsta > 0 or itwprog == 2):
        raise NoImplementado("IWARM (capa cálida de COARE): el original cambia u*, L y la altura de "
                             "mezcla sobre el agua de día y no se ha reproducido")
    if noobs < 2:
        if nssta < 1:
            raise NoImplementado("NOOBS<2 sin estaciones de superficie")
        if noobs == 0 and nusta < 1:
            raise NoImplementado("NOOBS=0 sin sondeos")
        if c.entero("IFORMS", 2) != 2:
            raise NoImplementado("SURF.DAT sin formato (IFORMS=%d): %s" % (c.entero("IFORMS", 2),
                                                                          sin_formato))
        if abs(c.entero("IEXTRP", -4)) == 2 and noobs == 1:
            raise ErrorOriginal("IEXTRP=±2 sin sondeos (NOOBS=1): calmet.exe 5.8.5 se detiene en la "
                                "primera hora con una excepción de división en coma flotante "
                                "(«A floating division exception was detected ... _diagno_»); "
                                "el motor propio también se detiene, sin inventar un resultado")

    nx, ny, nz = c.entero("NX"), c.entero("NY"), c.entero("NZ")
    dx = c.real("DGRIDKM") * 1000.0
    x0, y0 = c.real("XORIGKM") * 1000.0, c.real("YORIGKM") * 1000.0
    zface = np.array(_reales(c, "ZFACE")[: nz + 1])
    proy = proyeccion.Proyeccion(c)
    if proy.pmap not in proyeccion.PROYECCIONES:
        raise ErrorOriginal("PMAP=%s: calmet.exe 5.8.5 se detiene («Unacceptable PMAP ... PMAP must "
                            "be UTM,LCC,TTM»)" % proy.pmap)
    zona, hem = proy.zona, proy.hem_giro

    geo = entradas.leer_geo(f_geo)
    malla = Malla(nx, ny, dx, x0, y0, zface, geo["elev"].astype(np.float32).astype(float))
    # varios 3D.DAT seguidos o solapados (NM3D > 1): se unen por fechas, la primera aparición de
    # cada hora [V6] grupo 0 (d); caja negra: el mismo resultado que con un solo fichero [D12]
    f_3ds = [carpeta / fmin(x.strip()) for x in c.v.get("M3DDAT", [])][:max(c.entero("NM3D", 1), 1)]
    d3 = entradas.leer_3d(f_3ds[0] if f_3ds else f_3d)
    vistas = {h["fecha"] for h in d3["horas"]}
    for f in f_3ds[1:]:
        for h in entradas.leer_3d(f)["horas"]:
            if h["fecha"] not in vistas:
                d3["horas"].append(h)
                vistas.add(h["fecha"])
    d3["horas"].sort(key=lambda h: h["fecha"])
    nubes = entradas.leer_nubes(f_cld, nx, ny) if icloud == 2 else None
    try:
        prog = prognostico.Pronostico(d3, malla, zona, hem, proj=proy.proj,
                                      iluoc3d=c.entero("ILUOC3D", 16), itwprog=itwprog)
    except ValueError as e:
        if "mar adentro" in str(e):
            raise ErrorOriginal(str(e))
        raise

    ini = dt.datetime(c.entero("IBYR"), c.entero("IBMO"), c.entero("IBDY"), c.entero("IBHR"))
    irlg = c.entero("IRLG")
    nsmth = [int(float(x)) for x in c.lista("NSMTH")[-1]]
    p = {k: c.real(k, d) for k, d in (("CONSTB", 1.41), ("CONSTE", 0.15), ("CONSTN", 2400.0),
                                       ("FCORIOL", 1e-4), ("DPTMIN", 0.001), ("DZZI", 200.0),
                                       ("ZIMAX", 3000.0), ("ZIMIN", 50.0), ("THRESHL", 0.05),
                                       ("CONSTW", 0.16), ("ZIMAXW", 3000.0), ("ZIMINW", 50.0),
                                       ("IAVEZI", 1), ("MNMDAV", 1), ("HAFANG", 30.0),
                                       ("ILEVZI", 1), ("THRESHW", 0.05), ("TGDEFA", -0.0045),
                                       ("TGDEFB", -0.0098))}
    terrad = c.real("TERRAD", 10.0) * 1000.0
    critfn = c.real("CRITFN", 1.0)
    divlim, niter_div = c.real("DIVLIM", 5e-6), c.entero("NITER", 50)
    zupt = c.real("ZUPT", 200.0)
    iupt = max(c.entero("IUPT", 1), 1) - 1
    isurft = max(c.entero("ISURFT", 1), 1) - 1
    ifradj, islope = c.entero("IFRADJ", 1), c.entero("ISLOPE", 1)
    lcalgrd = c.logico("LCALGRD", True)
    cutp = c.real("CUTP", 0.01)

    tr = proy.a_lonlat()
    XX, YY = np.meshgrid(malla.xc, malla.yc)
    lon, lat = tr.transform(XX, YY)
    iformo = c.entero("IFORMO", 1)
    if iformo not in (1, 2):
        raise NoImplementado("IFORMO=%d" % iformo)
    gx, gy = malla.gradiente()
    hmax = viento.h_max_radio(malla.elev, dx, terrad)
    crestas = viento._crestas(malla.elev.astype(float), dx, terrad)
    z0 = geo["z0"]
    agua = (geo["lu"] >= geo["iwat1"]) & (geo["lu"] <= geo["iwat2"])
    zm = micromet.AlturaMezcla((ny, nx), p)

    obs = None
    mar_est = None
    if nowsta > 0:
        f_sea = [carpeta / fmin(x.strip()) for x in c.v.get("SEADAT", [])][:nowsta]
        if len(f_sea) < nowsta:
            raise ValueError("faltan ficheros SEADAT para las %d estaciones sobre el agua" % nowsta)
        mar_est = mar.EstacionesMar([entradas.leer_sea(f) for f in f_sea], p)
    jwat = np.zeros_like(agua)
    if itprog in (0, 1):
        # celdas cuya temperatura de superficie sale solo de las estaciones sobre el agua
        # ([UG] sec. 2.3.2.1); sin ellas el original se detiene [O17]
        jw1, jw2 = c.entero("JWAT1", 55), c.entero("JWAT2", 55)
        jwat = (geo["lu"] >= jw1) & (geo["lu"] <= jw2)
        if jwat.any() and mar_est is None:
            raise ValueError("celdas de agua entre JWAT1 y JWAT2 sin estaciones sobre el agua "
                             "(SEA.DAT): el original se detiene («has no valid sites for "
                             "interpolation»)")
    sond = None
    if noobs < 2:
        po = {k: c.real(k, d) for k, d in (("R1", None), ("R2", None), ("RMAX1", None),
                                            ("RMAX2", None), ("RMAX3", None), ("RMIN", 0.1),
                                            ("RMIN2", 4.0),
                                            ("IEXTRP", -4), ("ICALM", 0), ("IRAD", 1),
                                            ("TRADKM", 500.0), ("NUMTS", 5), ("IAVET", 1))}
        po["LVARY"] = c.logico("LVARY", False)
        po["NINTR2"] = _reales(c, "NINTR2") or [99.0]
        po["FEXTR2"] = _reales(c, "FEXTR2") or [0.0]
        f_srf = carpeta / fmin(nombre("SRFDAT", "SURF.DAT"))
        obs = observaciones.Observaciones(observaciones.leer_estaciones(c, nssta), entradas.leer_surf(f_srf),
                                   malla, agua, po)
        if noobs == 0:
            f_up = [carpeta / fmin(x.strip()) for x in c.v.get("UPDAT", [])][:nusta]
            if len(f_up) < nusta:
                raise ValueError("faltan ficheros UPDAT para las %d estaciones de altura" % nusta)
            sond = observaciones.Sondeos(observaciones.leer_estaciones_altura(c, nusta),
                                  [entradas.leer_up(f) for f in f_up], malla,
                                  [e["nombre"] for e in obs.est])
            # pesos de los sondeos en la temperatura 3D (ITPROG=0): mín(1, 1/r^IRAD) con r en
            # celdas de malla, todos los sondeos (sin TRADKM ni NUMTS) [caja negra] [T7]
            rc = np.maximum(sond.d * 1000.0 / dx, 1e-6)
            w_sond = np.minimum(1.0, 1.0 / rc ** int(po["IRAD"]))
            grad_sond = observaciones.GradienteSondeo(sond.son[iupt], zupt)

    cab = fichero_viento.Cabecera(
        comentarios=["Produced by %s Version: %s  Level: %s" % (PROGRAMA, VERSION, NIVEL)]
        + texto.replace("\r", "").split("\n"),
        ibyr=ini.year, ibmo=ini.month, ibdy=ini.day, ibhr=ini.hour, ibtz=c.entero("IBTZ", 0),
        irlg=irlg, irtype=c.entero("IRTYPE", 1), nx=nx, ny=ny, nz=nz, dgrid=dx, xorig=x0, yorig=y0,
        iwfcod=c.entero("IWFCOD", 1), nssta=nssta, nusta=nusta, npsta=npsta, nowsta=nowsta,
        nlu=geo["nlu"], iwat1=geo["iwat1"], iwat2=geo["iwat2"], lcalgrd=lcalgrd, pmap=proy.pmap,
        datum=(c.cadena("DATUM", "WGS-84") or "WGS-84").strip(), daten=geo.get("daten", ""),
        # el original escribe los parámetros del grupo 2 tal como están en el control, también
        # los que no usa su proyección [caja negra]
        utmhem=proy.hem, iutmzn=zona, rnlat0=proy.lat0, relon0=proy.lon0, xlat1=proy.lat1,
        xlat2=proy.lat2, feast=proy.feast, fnorth=proy.fnorth,
        zface=zface.astype(np.float32), z0=z0, ilandu=geo["lu"], elev=malla.elev, xlai=geo["lai"])
    if obs is not None:
        # posiciones de las estaciones en m respecto al origen de la malla y estación más
        # cercana a cada celda [V6] tabla 8-26; caja negra
        cab.estaciones = {"XSSTA": obs.xs - x0, "YSSTA": obs.ys - y0}
        cab.nears = obs.nears
    if sond is not None:
        cab.estaciones.update(XUSTA=sond.x - x0, YUSTA=sond.y - y0)
    lon_st = lat_st = None
    if obs is not None:
        lon_st, lat_st = tr.transform(obs.xs, obs.ys)
    barreras = observaciones.Barreras(c, malla) if (obs is not None and c.entero("NBAR", 0) > 0) else None
    brisa = None
    if c.logico("LLBREZE", False) and c.entero("NBOX", 0) > 0:
        if obs is not None:
            brisa = observaciones.Brisa(c, obs, malla, sond)
    pluv = None
    if npsta > 0:
        f_prc = carpeta / fmin(nombre("PRCDAT", "PRECIP.DAT"))
        pp = {k: c.real(k, d) for k, d in (("NFLAGP", 2), ("SIGMAP", 100.0), ("CUTP", 0.01))}
        pluv = lluvia.Pluviometros(lluvia.leer_pluviometros(c, npsta), entradas.leer_precip(f_prc),
                                   malla, pp)
        # posiciones de los pluviómetros en el CALMET.DAT [V6] tabla 8-26; caja negra
        cab.estaciones.update(XPSTA=pluv.x - x0, YPSTA=pluv.y - y0)

    indice = {f: i for i, f in enumerate(prog.fechas)}
    previo = {"hw": np.zeros((ny, nx)), "hw_crudo": np.zeros((ny, nx))}

    def olas_boya(dm):
        # oleaje por defecto de cada boya, con su viento de la primera hora [W13]
        if icoare not in (11, 12):
            return None
        if "olas_boya" not in previo:
            previo["olas_boya"] = mar.olas_por_defecto(np.nan_to_num(dm["ws"], nan=0.0))
        return previo["olas_boya"]

    def horas():
        for k in range(irlg):
            t = ini + dt.timedelta(hours=k)
            ki = indice[(t.year, t.month, t.day, t.hour)]
            jd = t.timetuple().tm_yday
            ndathr = t.year * 100000 + jd * 100 + t.hour
            tm = t - dt.timedelta(minutes=30)
            sinf = sol.seno_elevacion(tm.year, tm.timetuple().tm_yday,
                                      tm.hour + tm.minute / 60.0, lat, lon)
            techo = None
            if obs is not None:
                # con estaciones, el techo de nubes de la más cercana entra en la clase PGT
                # también con ICLOUD=2 [O15]
                dat = obs.datos(t)
                techo = dat[obs.nears - 1, 2]
            if icloud == 2:
                nub = nubes[ndathr]
            else:
                # ICLOUD=0: nubosidad (décimas) de la estación más cercana [O15]
                if (dat[:, 3] >= entradas.AUSENTE * 0.999).all():
                    raise ValueError("ICLOUD=0 sin nubosidad en ninguna estación a %s" % t)
                nub = dat[obs.nears - 1, 3] / 10.0
            qsw = micromet.radiacion_solar(sinf, nub)
            dia = bool(float(np.mean(sinf)) > -micromet.A2 / micromet.A1)
            ph = prog.hora(ki, dia)
            u, v, tk = ph["u"], ph["v"], ph["t"]
            rho = ph["rho"]
            irh = np.zeros((ny, nx), int)
            if obs is None and "rh" in ph:
                # sin observaciones, la humedad del pronóstico si el 3D.DAT la trae (IOUTQ=1),
                # del primer nivel e interpolada como el resto [caja negra] [W11]
                irh = np.floor(ph["rh"] + 1e-6).astype(int)
            dm = dmar = None
            if mar_est is not None:
                # estaciones sobre el agua de la hora y sus distancias a las celdas (km)
                dm = mar_est.hora(t)
                dmar = np.hypot(XX[None] - dm["x"][:, None, None],
                                YY[None] - dm["y"][:, None, None]) / 1000.0
            caras = None
            if itprog == 0:
                # temperatura 3D de los sondeos: en las caras de las capas (alturas sobre el
                # primer nivel de cada sondeo), lineal entre niveles y en el tiempo, media
                # ponderada de los sondeos y media de las dos caras en cada capa ([UG] sec. 2.3.2,
                # pasos 1-4; caja negra) [T7]
                tf, okt = sond.temperatura(t, malla.zface)
                if not okt.any():
                    raise ValueError("ningún sondeo con temperatura a %s" % t)
                ww = w_sond[okt]
                caras = np.einsum("nz,nyx->zyx", tf[okt], ww) / ww.sum(0)
                tk = 0.5 * (caras[:-1] + caras[1:])
            if obs is not None:
                if itprog in (0, 1):
                    # temperatura de la capa 1, humedad y presión desde las estaciones; RHO con
                    # la presión de la estación más cercana [O9-O11]
                    ts, irh, pc = obs.superficie(dat)
                    if jwat.any():
                        # sobre el agua (JWAT1-JWAT2), solo las estaciones sobre el agua, con los
                        # mismos pesos [UG] sec. 2.3.2.1; caja negra [W9]
                        ok_t = ~np.isnan(dm["Ta"])
                        if not ok_t.any():
                            raise ValueError("ninguna estación sobre el agua con temperatura a "
                                             "%s (el original se detiene)" % t)
                        idw, ww = observaciones.pesos_t(dmar, ok_t, dx, obs.p)
                        tw = (ww * dm["Ta"][idw][:, None, None]).sum(0) / ww.sum(0)
                        ts = np.where(jwat, tw, ts)
                        ok_h = ~np.isnan(dm["rh"])
                        if ok_h.any():
                            idh, wh = observaciones.pesos_t(dmar, ok_h, dx, obs.p)
                            # HR de las boyas truncada a entero antes de interpolar [caja negra]
                            rw = (wh * np.floor(dm["rh"][idh])[:, None, None]).sum(0) / wh.sum(0)
                            irh = np.where(jwat, np.floor(rw + 1e-6).astype(int), irh)
                    tk = tk.copy()
                    tk[0] = ts
                    rho = pc * 100.0 / (287.0 * ts)
                elif icoare != 0:
                    irh = np.full((ny, nx), IRH_SIN_DATO, int)
                else:
                    # con ICOARE=0 e ITPROG=2, la humedad de la estación más cercana (NEARS)
                    # [caja negra] [W10]
                    irh = dat[obs.nears - 1, 5].astype(int)
            t1 = tk[0]
            # flujo sensible: balance de energía de día, Venkatram de noche (con el viento inicial)
            qh_dia = micromet.flujo_sensible_diurno(qsw, t1, nub, geo["albedo"], geo["bowen"],
                                                    geo["hcg"], geo["qf"])
            ws0 = np.hypot(u[0], v[0])
            ust0, el0, ths0 = micromet.ustar_l_estable(ws0, z0, t1, nub)
            qh0 = np.where(qh_dia > 0, qh_dia, -rho * micromet.CP * ust0 * ths0)
            qh0 = np.where(agua, 0.0, qh0)
            # altura de mezcla convectiva y temperatura final antes del viento: el N del bloqueo
            # usa la temperatura ya ajustada [caja negra: caso del Prepirineo, N medido por horas]
            zp_p, tp_p = previo.get("niv", (ph["zp"], ph["tp"]))
            th_prev = lambda zq: prog.theta_niveles(zp_p, tp_p, zq)
            if itprog == 0:
                # gradiente sobre la capa de mezcla del último sondeo de la estación IUPT
                # [UG] sec. 2.3.1; caja negra [T8]
                th_prev = lambda zq: sond.theta(t, zq, iupt)
            kz = int(p["ILEVZI"]) - 1
            h_ant = zm.h.copy()
            bg = None
            if abs(imixh) == 2:
                # Batchvarova y Gryning con u* y L del viento inicial [M12]
                bg = micromet.ustar_l_diurno(ws0, z0, np.maximum(qh_dia, 1e-6), t1, rho)
            hraw, hconv, psi = zm.convectiva(qh0, t1, rho, th_prev, agua,
                                             u[kz] if AV_INICIAL else None,
                                             v[kz] if AV_INICIAL else None, dx, bg=bg)
            th_psi_w = th_prev if MODO_PSI_W == "anterior" else (
                lambda zq: prog.theta_niveles(ph["zp"], ph["tp"], zq))
            previo["niv"] = (ph["zp"], ph["tp"])
            adiab = [hconv > malla.zc[kk] for kk in range(nz)]
            tk = _adiabatica(tk, t1, hconv, adiab, malla, caras)
            # paso 1
            if ikine and not ifradj:
                tkn = ph["t"].copy() if itprog == 1 else tk
                if itprog == 1:
                    for kk in range(nz):
                        tkn[kk] = np.where(adiab[kk], tkn[0] - 0.0098 * (malla.zc[kk] - malla.zc[0]),
                                           tkn[kk])
                if itprog == 0:
                    gam = grad_sond.hora(t, float(h_ant[sond.jc[iupt], sond.ic[iupt]]))
                    n2 = viento.G_FR / dat[isurft, 4] * (gam + 0.01)
                    nbv = math.sqrt(n2) if n2 > 0 else 0.0
                else:
                    nbv = viento.brunt_vaisala(tkn, malla.zc, zupt)
            if ifradj:
                # N con la temperatura del pronóstico (también con ITPROG=1: las estaciones no
                # entran en el bloqueo) [O14]
                tkn = tk
                if itprog == 1:
                    tkn = ph["t"].copy()
                    for kk in range(nz):
                        tkn[kk] = np.where(adiab[kk], tkn[0] - 0.0098 * (malla.zc[kk] - malla.zc[0]),
                                           tkn[kk])
                if itprog == 0:
                    # con los sondeos (ITPROG=0), N del gradiente del sondeo IUPT entre su primer
                    # nivel y ZUPT y la temperatura de la estación de superficie ISURFT [T9]
                    gam = grad_sond.hora(t, float(h_ant[sond.jc[iupt], sond.ic[iupt]]))
                    n2 = viento.G_FR / dat[isurft, 4] * (gam + 0.01)
                    nbv = math.sqrt(n2) if n2 > 0 else 0.0
                else:
                    nbv = viento.brunt_vaisala(tkn, malla.zc, zupt)
                if ikine:
                    # efectos cinemáticos antes del bloqueo, con la misma N ([UG] fig. 3-4) [V15]
                    u, v = viento.cinematico(u, v, malla, gx, gy, nbv, alpha_kin, divlim, niter_div)
                u, v = viento.froude(u, v, malla.elev, gx, gy, malla.zc, hmax, nbv, critfn)
            elif ikine:
                u, v = viento.cinematico(u, v, malla, gx, gy, nbv, alpha_kin, divlim, niter_div)
            if islope:
                u, v = viento.ladera(u, v, malla, gx, gy, qh0, t1, terrad, crestas)
            # paso 2: análisis objetivo con las observaciones, suavizado y velocidad vertical
            if obs is not None:
                extra = None
                if abs(int(obs.p["IEXTRP"])) == 4:
                    extra = _extrapolacion_semejanza(obs, dat, malla, p, z0, t1, ph["t"][0], nub,
                                                     qh_dia, rho, hraw, psi, agua, hem)
                alto = sond.hora(t) if sond is not None else None
                u, v = obs.viento(u, v, dat, malla.zc, extra, alto,
                                  _vientos_mar(dm, dmar, obs.p, malla, p, icoare, hem, alto,
                                               previo["hw_crudo"], agua, olas_boya(dm), icool)
                                  if dm is not None else None, barreras)
            fijas = None
            if brisa is not None:
                # regiones de brisa: capa 1 sustituida antes del suavizado, que no la toca (sus
                # vecinas sí la usan) y que también es la de los bordes en la velocidad vertical
                # [caja negra: región parcial con NSMTH = 2] [B1-B3]
                u, v = brisa.aplicar(u, v, dat, alto, int(obs.p["IEXTRP"]))
                fijas = brisa.mascara
            u1, v1 = u, v
            u, v = viento.suavizar(u, v, nsmth, fijas)
            w = viento.vertical(u, v, malla, u1, v1)
            if iobr:
                # O'Brien: W nula en la cima y minimización de la divergencia con W fija ([UG]
                # ec. 2-28 a 2-36; caja negra) [V13, V14]
                w = viento.obrien(w, malla.zface)
                u, v = viento.minimizar(u, v, w, malla, divlim, niter_div)
                u, v = u.astype(np.float32), v.astype(np.float32)
            if obs is not None and itprog in (0, 1) and int(obs.p["IAVET"]):
                # promedio espacial de la temperatura de superficie a barlovento con el viento
                # final (el de la altura de mezcla) [O12]; RHO con la temperatura promediada
                t1 = micromet._promedio(t1[None].astype(float), u[kz].astype(float),
                                        v[kz].astype(float), dx, 3600.0, int(p["MNMDAV"]),
                                        float(p["HAFANG"]))[0]
                tk = _adiabatica(tk, t1, hconv, adiab, malla, caras)
                tk[0] = t1
                rho = pc * 100.0 / (287.0 * t1)
            elif itwprog == 2 and PRUEBA_T2 and c.entero("IAVET", 1):
                t1 = micromet._promedio(t1[None].astype(float), u[kz].astype(float),
                                        v[kz].astype(float), dx, 3600.0, int(p["MNMDAV"]),
                                        float(p["HAFANG"]))[0]
                if PRUEBA_T2 == 2:
                    t1 = np.where(agua, t1, tk[0])
                tk = tk.copy()
                tk[0] = t1
            # micrometeorología con el viento final
            ws = np.hypot(u[0], v[0]).astype(float)
            ust_s, el_s, ths = micromet.ustar_l_estable(ws, z0, t1, nub)
            qhp = np.maximum(qh_dia, 1e-6)
            ust_d, el_d = micromet.ustar_l_diurno(ws, z0, qhp, t1, rho)
            dmask = qh_dia > 0
            ust = np.where(dmask, ust_d, ust_s)
            el = np.where(dmask, el_d, el_s)
            qh = np.where(dmask, qh_dia, -rho * micromet.CP * ust_s * ths)
            zi_agua = None
            con_mar = dm is not None or itwprog == 2
            if not con_mar:
                # agua sin estaciones sobre el agua: neutro con la z0 de Hosker [W1, M10]
                ust_w = micromet.ustar_agua(ws)
                el_w = np.full(ws.shape, micromet.EL_NEUTRO)
                q_w = np.zeros(ws.shape)
            else:
                if dm is not None:
                    # capa límite marina con los datos de la estación sobre el agua más cercana y
                    # el viento final de la capa 1 (OCD o COARE) [W1-W5]
                    # cada dato, de la estación más cercana que lo tiene; sin ninguna, el valor por
                    # defecto (ΔT ausente: neutro) [W4, W5]
                    ta_c = mar.mas_cercana(dmar, dm["Ta"], mar.TA_DEF)
                    dt_c = mar.mas_cercana(dmar, dm["dT"])
                    rh_c = mar.mas_cercana(dmar, dm["rh"], mar.RH_DEF)
                    z_c = mar.mas_cercana(dmar, dm["z"], 10.0)
                    tga_c = mar.mas_cercana(dmar, dm["tga"], p["TGDEFA"])
                    zi_obs = dm["zi"]
                else:
                    # ITWPROG=2 sin estaciones sobre el agua: del punto del 3D.DAT de mar adentro
                    # más cercano, ΔT = T₁ − SST con la T del primer nivel a su altura y su
                    # humedad (0 sin ella en el 3D.DAT) [caja negra: SST de 284 a 298 K, primer
                    # nivel de 10 a 120 m, viento 5 y 10 m/s; u* ± 0,15 %, L ± 0,6 %] [W16]
                    pm = ph["mar"]
                    ta_c, z_c, rh_c = pm["ta"], pm["z"], pm["rh"]
                    dt_c = pm["ta"] - pm["sst"]
                    tga_c = np.full((ny, nx), p["TGDEFA"])
                    zi_obs = np.array([np.nan])
                if icoare in (11, 12) and "olas" not in previo:
                    previo["olas"] = mar.olas_por_defecto(ws)      # primera hora [W13]
                ust_w, el_w, fl_w, _ = mar.flujos(icoare, ws, ta_c, dt_c, rh_c, z_c,
                                                  previo.get("olas"), icool)
                q_w = rho * micromet.CP * fl_w
                # altura convectiva sobre el agua (Maul-Carson con THRESHW y el gradiente sobre
                # la capa de mezcla de la estación, TGRADA o TGDEFA) [W8]
                okz = ~np.isnan(zi_obs)
                if okz.any():
                    # altura de mezcla observada sobre el agua: 1/r² de todas las que la dan
                    # ([UG] sec. 2.3.1); esa hora la convectiva no crece, w* usa la anterior y
                    # la siguiente parte de mín(anterior, observada) [caja negra] [W8]
                    wz = 1.0 / np.maximum(dmar[okz], 1e-6) ** 2
                    zi_agua = (wz * dm["zi"][okz][:, None, None]).sum(0) / wz.sum(0)
                    hw_w = previo["hw"]
                    hw = np.minimum(previo["hw"], zi_agua)
                else:
                    psi_w = np.maximum(0.0098 + tga_c, p["DPTMIN"])
                    if itwprog >= 1:
                        # ITWPROG=1: gradiente sobre la capa de mezcla del pronóstico, como en
                        # tierra (niveles de la hora anterior) ([V6] tabla 8-4) [W12]
                        hp = np.maximum(previo["hw"], p["ZIMINW"])
                        psi_w = np.maximum((th_psi_w(hp + p["DZZI"]) - th_psi_w(hp)) / p["DZZI"],
                                           p["DPTMIN"])
                    if imixh < 0:
                        # IMIXH < 0: sobre el agua solo la altura mecánica de OCD, CONSTW·u*/f
                        # ([UG] ec. 2-70; [V6] tabla 8-4); w* con esa altura [caja negra] [W14]
                        hw = np.zeros((ny, nx))
                        zi_agua = np.clip(p["CONSTW"] / p["FCORIOL"] * ust_w, p["ZIMINW"],
                                          p["ZIMAXW"])
                        hw_w = zi_agua
                    elif imixh == 2:
                        # Batchvarova y Gryning también sobre el agua, desde la altura de la hora
                        # anterior (sin el mínimo ZIMINW de Maul-Carson) y con THRESHW
                        # [caja negra: dominio todo agua, 1,3 %] [W14]
                        hp = previo["hw"]
                        hw = hw_w = np.where(q_w - p["THRESHW"] * hp > 0, micromet.crece_bg(
                            hp, q_w, psi_w, ust_w, el_w, t1, rho, p["THRESHW"]), 0.0)
                        zi_agua = np.clip(np.maximum(hw, p["CONSTW"] / p["FCORIOL"] * ust_w),
                                          p["ZIMINW"], p["ZIMAXW"])
                    else:
                        hw = hw_w = micromet.crece_agua(q_w, previo["hw"], psi_w, p, rho)
                        zi_agua = np.clip(np.maximum(hw, p["CONSTW"] / p["FCORIOL"] * ust_w),
                                          p["ZIMINW"], p["ZIMAXW"])
                # la convectiva sobre el agua es un estado aparte: no entra en el campo de la de
                # tierra (que pasa a la hora siguiente y ajusta la temperatura), pero la de la hora
                # siguiente parte de su promedio a barlovento junto con la de tierra; la extrapolación
                # vertical de las boyas usa la de la celda sin promediar [caja negra: casos C y
                # R_tarragona, con ITPROG=1 y JWAT] [W8]
                previo["hw"] = previo["hw_crudo"] = hw
                if p.get("IAVEZI", 0):
                    previo["hw"] = micromet._promedio(np.where(agua, hw, hraw)[None],
                                                      u[kz].astype(float), v[kz].astype(float), dx,
                                                      3600.0, int(p["MNMDAV"]), float(p["HAFANG"]))[0]
            ust = np.where(agua, ust_w, ust)
            el = np.where(agua, el_w, el)
            qh = np.where(agua, q_w, qh)
            if not AV_INICIAL and p.get("IAVEZI", 0):
                # promedio de la convectiva con el viento final (se guarda para la hora siguiente)
                hconv = micromet._promedio(hraw[None], u[kz].astype(float), v[kz].astype(float),
                                           dx, 3600.0, int(p["MNMDAV"]), float(p["HAFANG"]))[0]
                zm.h = hconv
            elif con_mar:
                hconv = hraw
                zm.h = hconv
            # la N de la altura mecánica usa la temperatura del pronóstico en la capa 1 (también
            # con ITPROG=1) [O13]
            zi = zm.efectiva(qh, ust, el, ph["t"][0], hraw, psi, agua, ust_w, u[kz], v[kz], dx,
                             zi_agua=zi_agua)
            if itprog == 0 and jwat.any():
                # temperatura sobre el agua (JWAT1-JWAT2) con los sondeos: desde la de la capa 1
                # (de las estaciones sobre el agua), con el gradiente TGRADB del SEA.DAT bajo la
                # altura de mezcla y TGRADA encima (o TGDEFB, TGDEFA), media de cada capa
                # ([UG] sec. 2.3.2.1; caja negra) [T10]
                tgb_c = mar.mas_cercana(dmar, dm["tgb"], p["TGDEFB"])
                tga_c = mar.mas_cercana(dmar, dm["tga"], p["TGDEFA"])
                tk = tk.copy()
                for kk in range(1, nz):
                    tw = _media_dos_tramos(t1, tgb_c, tga_c, ZI_T_AGUA(zi, zi_agua), malla.zface[kk],
                                           malla.zface[kk + 1])
                    tk[kk] = np.where(jwat, tw, tk[kk])
            # w* sobre el agua con la convectiva de la celda SIN promediar [caja negra] [W8]
            wst = micromet.wstar(qh, np.where(agua, hw_w, hconv) if con_mar else hconv,
                                 t1, rho)
            ipgt = np.where(agua, mar.pgt_agua(el_w), micromet.turner(ws, sinf, nub, techo))
            # precipitación del pronóstico (NPSTA=-1): cm/h -> mm/h, nula por debajo de CUTP;
            # código 10 (líquida) o 20 (sólida) según TEMPK [caja negra]
            if pluv is not None:
                # pluviómetros: lluvia interpolada (NFLAGP, SIGMAP, CUTP) y código de la estación
                # de superficie más cercana [P1-P3]
                rmm = pluv.hora(t)
                # sin estaciones de superficie (NOOBS=2) el código de precipitación es 0 en toda
                # la malla, también donde llueve [caja negra] [P4]
                ipcode = (dat[obs.nears - 1, 7].astype(int) if obs is not None
                          else np.zeros((ny, nx), int))
            else:
                rmm = prog.a_malla(ph["rain_puntos"])
                rmm = np.where(rmm >= cutp, rmm, 0.0)
                ipcode = np.where(rmm > 0, np.where(t1 > 273.15, 10, 20), 0)
            d2 = {"IPGT": ipgt, "USTAR": ust, "ZI": zi, "EL": el, "WSTAR": wst, "RMM": rmm,
                  "TEMPK": t1, "RHO": rho, "QSW": qsw, "IRH": irh, "IPCODE": ipcode}
            hora = fichero_viento.Hora(ndathr, u, v, w, tk, d2)
            if iformo == 2 and obs is not None:
                # valores en las estaciones para el PACOUT.DAT: los del SURF.DAT y la radiación
                # solar con la elevación y la nubosidad de cada estación [D11]
                sin_st = sol.seno_elevacion(tm.year, tm.timetuple().tm_yday,
                                            tm.hour + tm.minute / 60.0, lat_st, lon_st)
                nub_st = nub[obs.jc, obs.ic] if icloud == 2 else dat[:, 3] / 10.0
                hora.sup = {"tempk": dat[:, 4], "srad": micromet.radiacion_solar(sin_st, nub_st),
                            "irh": dat[:, 5].astype(int), "ipcode": dat[:, 7].astype(int)}
            yield hora

    t0 = time.time()
    if not c.logico("LSAVE", True):
        # LSAVE = F: el original no escribe el fichero de salida [V6] tabla 8-3; caja negra
        for _ in horas():
            pass
        return {"salida": None, "segundos": time.time() - t0}
    if iformo == 2:
        # salida en el formato de MESOPUFF II (PACOUT.DAT) [UG] sec. 4.3.11.2 [D11]
        f_out = carpeta / fmin(nombre("PACDAT", "PACOUT.DAT"))
        g = lambda a, o: (np.asarray(a, float) - o) / dx + 0.5
        fichero_viento.escribir_pacout(
            f_out, cab, horas(), ini.timetuple().tm_yday,
            *((g(obs.xs, x0), g(obs.ys, y0)) if obs is not None else ((), ())),
            *((g(sond.x, x0), g(sond.y, y0)) if sond is not None else ((), ())))
    else:
        fichero_viento.escribir(f_out, cab, horas())
    return {"salida": str(f_out), "segundos": time.time() - t0}


if __name__ == "__main__":
    print(ejecutar())
