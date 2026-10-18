# -*- coding: utf-8 -*-
"""Programa principal: CALPUFF.INP + CALMET.DAT -> CONC.DAT (concentraciones horarias).

Alcance (README de la fase 08): fuentes de área (polígonos) y puntuales con sobreelevación (Briggs,
transición, efecto punta, penetración parcial) y efecto edificio (ISC), una especie, sin química ni
deposición, sin slugs ni división de puffs, dispersión MDISP=3 (PG/McElroy-Pooler), ajuste de
terreno MCTADJ=0 o 3, receptores discretos. Lo demás lanza NoImplementado.
"""
import datetime as dt
import math
import sys
import time
from pathlib import Path

import numpy as np

from . import fichero_viento, fichero_conc, deposicion, edificios, emisiones, entrada, nucleo
from . import estela_edificio as prm
from .entrada import NoImplementado
from .sobreelevacion import elevacion

PROGRAMA = "CALPUFF_PY"
VERSION = "1.0"
NIVEL = "261017"

_REQUISITOS = {"MDISP": (2, 3, 4), "MSLUG": (0,), "MSPLIT": (0,), "MCHEM": (0,), "MDRY": (0, 1),
               "MWET": (0, 1), "MCTSG": (0,), "MPDF": (0,), "MSGTIBL": (0,), "MBCON": (0,),
               "MTILT": (0,), "MSOURCE": (0,), "MROUGH": (0,), "MHFTSZ": (0,),
               "METFM": (1,), "NAR2": (0,), "NLINES": (0,), "NLN2": (0,),
               "MCTADJ": (0, 1, 3), "MRESTART": (0,),
               "MTRANS": (0, 1), "MTIP": (0, 1), "MSHEAR": (0,), "MPARTL": (0, 1)}

# código ISTYPE de cada tipo de fuente en el CONC.DAT ([V6] tabla 9-52)
ISTYPE = {1: 1, 3: 3, 2: 7}
# clave del CONC.DAT de cada clase de fuente: (tipo, de fichero de emisiones variables)
CLASES = ((1, False, "NPT1", 1), (1, True, "NPT2", 2), (3, False, "NAR1", 3), (2, False, "NVL1", 7),
          (2, True, "NVL2", 8))


def _fuentes_arb(cfg, carpeta, mbdw):
    """Fuentes de los ficheros de emisiones variables: PTEMARB.DAT (NPT2) y VOLEMARB.DAT (NVL2)."""
    out = []
    if cfg.i("NPT2", 0) > 0:
        a = emisiones.leer_ptemarb((carpeta / cfg.s("PTDAT", "PTEMARB.DAT")).read_text(errors="ignore"), mbdw)
        for d in a.fuentes:
            f = entrada.Fuente(d["cid"], 1, d["x"], d["y"], d["h"], d["zb"], 0.0, d=d["d"], w=1.0, ts=1.0)
            f.bdw, f.fmfac = d["bdw"], d["fmfac"]
            if d["bdw"]:
                f.edif = {k: np.asarray(d["edif"].get(k, [0.0] * 36), float) for k in entrada.EDIF}
            f.arb = (a, d["cid"])
            out.append(f)
    if cfg.i("NVL2", 0) > 0:
        a = emisiones.leer_volemarb((carpeta / cfg.s("VOLDAT", "VOLEMARB.DAT")).read_text(errors="ignore"))
        for d in a.fuentes:
            f = entrada.Fuente(d["cid"], 2, 0.0, 0.0, 0.0, 0.0, 0.0)
            f.arb = (a, d["cid"])
            out.append(f)
    return out


def _actualizar_arb(f, tfin, nombres_emit, x0km, y0km):
    """Parámetros de la hora de una fuente de fichero de emisiones variables."""
    a, cid = f.arb
    d = a.datos(tfin)[cid]
    f.qs = [d["q"][a.especies.index(n)] if n in a.especies else 0.0 for n in nombres_emit]
    f.q = f.qs[0] if f.qs else 0.0
    if f.tipo == 1:
        f.ts, f.w = d["ts"], d["w"]
        f.sy0, f.sz0 = d["sy0"], d["sz0"]
    else:
        f.x, f.y, f.h, f.zbase, f.sy0, f.sz0 = d["x"], d["y"], d["h"], d["zb"], d["sy0"], d["sz0"]
        f._xc = (float(np.float32(f.x)) - x0km) * 1000.0
        f._yc = (float(np.float32(f.y)) - y0km) * 1000.0
# estaciones del perfil IVARY = 3 (primer grupo DIC-ENE-FEB)
_ESTACION = {12: 0, 1: 0, 2: 0, 3: 1, 4: 1, 5: 1, 6: 2, 7: 2, 8: 2, 9: 3, 10: 3, 11: 3}


def _comprobar(cfg):
    for k, ok in _REQUISITOS.items():
        v = cfg.i(k)
        if v is not None and v not in ok:
            raise NoImplementado("%s = %d (solo %s)" % (k, v, ok))
    if cfg.i("IARU", 1) != 1 or cfg.i("IPTU", 1) != 1 or cfg.i("IVLU", 1) != 1:
        raise NoImplementado("unidades de emisión distintas de g/s y g/m2/s")


def _factor_emision(f, nombre, hora, mes, ws, clase, tk, wscat):
    """Factor de variación de la emisión (subgrupos 13d, 14d y 16c; [V6] tabla 9-3): IVARY 1 (24
    horas), 2 (12 meses), 3 (4 estaciones × 24 horas, la primera DIC-ENE-FEB), 4 (6 clases de
    estabilidad × 6 clases de viento con los límites WSCAT) y 5 (12 clases de temperatura con
    límites superiores de 0 a 50 °C)."""
    var = f.variacion.get(nombre, f.variacion.get(None))
    if var is None:
        return 1.0
    iv, fac = var
    if iv == 0:
        return 1.0
    if iv == 1:
        return fac[hora - 1]
    if iv == 2:
        return fac[mes - 1]
    if iv == 3:
        return fac[_ESTACION[mes] * 24 + hora - 1]
    if iv == 4:
        kw = sum(1 for lim in wscat if ws > lim)
        return fac[(min(max(clase, 1), 6) - 1) * 6 + kw]
    if iv == 5:
        tc = tk - 273.15
        kt = sum(1 for lim in range(0, 55, 5) if tc > lim)
        return fac[min(kt, 11)]
    raise NoImplementado("IVARY = %d" % iv)


def _f32(x):
    return np.asarray(x, np.float32).astype(np.float64)


def _area_poligono(vx, vy):
    n = len(vx)
    return 0.5 * abs(sum(vx[i] * vy[(i + 1) % n] - vx[(i + 1) % n] * vy[i] for i in range(n)))


def _fila_estela(fila, est, symin, szmin):
    """Efecto edificio ISC en el puff nuevo: σ iniciales (crecimiento virtual desde 10·esc), datos
    de las σ del campo cercano y, con Schulman-Scire, la elevación reducida."""
    fila[nucleo.PSY] = est.sy0
    fila[nucleo.PSZ] = est.sz0
    # el mínimo de las σ en los receptores sigue siendo SYMIN/SZMIN (caja negra)
    fila[nucleo.PSYI] = symin
    fila[nucleo.PSZI] = szmin
    fila[nucleo.PDW] = est.idw
    fila[nucleo.PDWESC] = est.esc
    fila[nucleo.PDWA] = est.a
    fila[nucleo.PDWSYC] = est.syc
    fila[nucleo.PDWK] = est.clase
    fila[nucleo.PDWURB] = 1.0 if est.urbano else 0.0
    if est.idw == 2:
        fila[nucleo.PSS] = 1.0
        fila[nucleo.PR0] = est.r0
        fila[nucleo.PLY] = est.ly


def _prime(f, u32, v32, us, U, V, T3, ix, iy, zface, clase, ilu, par, plx0):
    """Efecto edificio PRIME de una fuente para la hora: sobreelevación numérica, tablas y fracción
    en la cavidad. Devuelve (Estado, trayectoria, Ub, ux, uy) o None si no hay edificio en el
    sector o el viento en la chimenea es de calma."""
    ks = edificios.sector(float(u32), float(v32))
    e = f.edif
    hb, wb = e["HEIGHT"][ks - 1], e["WIDTH"][ks - 1]
    if hb <= 0.0 or wb <= 0.0 or us < 1.0:
        return None
    lb, xb, yb = e["LENGTH"][ks - 1], e["XBADJ"][ks - 1], e["YBADJ"][ks - 1]
    u32c = U[:, iy, ix].astype(np.float32)
    v32c = V[:, iy, ix].astype(np.float32)
    wsc = np.sqrt(u32c * u32c + v32c * v32c).astype(float)
    nz = len(wsc)
    kb = min(max(int(np.searchsorted(zface, hb, side="right") - 1), 0), nz - 1)
    ub = float(wsc[kb])
    lu = abs(ilu)
    urb = par[nucleo.C_IURB1] <= lu <= par[nucleo.C_IURB2]
    per = prm.Perfil(zface, wsc, T3[:, iy, ix], plx0[min(max(clase, 1), 6) - 1])
    st = prm.Estado(hb, wb, lb, xb, yb, clase, urb, ub, ub, per)
    tr = prm.numrise(st, f.h, 0.5 * f.d, f.ts, f.w)
    return st, tr, ub, float(u32) / us, float(v32) / us


def _elevacion_prime(f, pri, us, tempk, clase, zi, zmid, tcol):
    """Elevación de un puff PRIME: altura de salida hs, final ZFIN de la trayectoria y distancia
    XFIN (la altura de transición sale de la tabla de la trayectoria); el código del puff y el
    reparto de la masa por la penetración en la inversión, con el flujo de flotación de Briggs y sin
    recortar la elevación (caja negra)."""
    from .sobreelevacion import Elevacion, G, penetracion
    tr = pri[1]
    e = Elevacion()
    e.hs = f.h
    e.dhf = tr[2][prm.MXNTR] - f.h
    e.xf = tr[0][prm.MXNTR]
    e.us = max(us, 1.0)
    r = 0.5 * f.d
    e.fb = max(G * f.w * r * r * (f.ts - tempk) / f.ts, 0.0)
    e.ss = 1
    estable = clase >= 5
    return penetracion(e, estable, (not estable) and e.hs >= zi, zi, zmid, tcol, tempk)


def _fuente_cavidad(f, st, ux, uy):
    """Posición (m) de la fuente de la cavidad: DISTC aguas abajo de la chimenea, sobre el eje lateral
    de la chimenea limitado a la anchura del edificio (como el eje del penacho de la cavidad en
    CAV_SRC)."""
    rt2pi = 2.50662827463100
    ybmax = 0.5 * (st.WB - st.SYCAV[1] * rt2pi)
    ysb = -st.YBADJ
    if ybmax <= 0.0:
        ycav = st.YBADJ
    else:
        ycav = st.YBADJ + (max(ysb, -ybmax) if ysb < 0.0 else min(ysb, ybmax))
    return f._xc + st.DISTC * ux - ycav * uy, f._yc + st.DISTC * uy + ycav * ux


def _fila_prime(fila, pri, kt, symin, szmin, tipo):
    """Puff PRIME (1 penacho principal, 2 fuente de la cavidad): tabla, σ iniciales (curva ambiental
    en la distancia virtual de la estela) y, en la cavidad, emisión en el suelo sin elevación."""
    st = pri[0]
    fila[nucleo.PPRI] = tipo
    fila[nucleo.PTAB] = kt
    lwak = st.LINWAKE and st.LWAK
    if tipo == 1:
        if lwak:
            fila[nucleo.PSY] = max(prm.sigypr(st, st.XVY), symin)
            fila[nucleo.PSZ] = max(prm.sigzpr(st, st.XVZ), szmin)
        else:
            # sin entrada en la estela: crecimiento normal desde σ0 = flotación del primer punto de
            # la trayectoria; la σ guardada al final de cada paso no baja de SYMIN/SZMIN (caja negra)
            b0 = pri[1][4][1] / 3.5
            fila[nucleo.PSY] = fila[nucleo.PSZ] = b0
            fila[nucleo.PSYI] = symin
            fila[nucleo.PSZI] = szmin
            return
    else:
        fila[nucleo.PH] = 0.0
        fila[nucleo.PHS] = 0.0
        fila[nucleo.PXF] = 0.0
        fila[nucleo.PSY] = max(prm.sigypr(st, st.XVYC), symin)
        fila[nucleo.PSZ] = max(prm.sigzpr(st, st.XVZC), szmin)
    fila[nucleo.PSYI] = symin
    fila[nucleo.PSZI] = szmin


def _malla_muestreo(cfg, cab, dg, nx, ny):
    """Receptores de la malla de muestreo: (x, y) en m desde el origen y cota (m)."""
    ib, jb = cfg.i("IBSAMP", 1), cfg.i("JBSAMP", 1)
    ie, je = cfg.i("IESAMP", nx), cfg.i("JESAMP", ny)
    m = max(cfg.i("MESHDN", 1), 1)
    xs = (ib - 0.5) * dg + np.arange((ie - ib) * m + 1) * dg / m
    ys = (jb - 0.5) * dg + np.arange((je - jb) * m + 1) * dg / m
    X, Y = np.meshgrid(xs, ys)
    el = np.asarray(cab.elev, float)
    fx = np.clip(X / dg - 0.5, 0.0, nx - 1.0)
    fy = np.clip(Y / dg - 0.5, 0.0, ny - 1.0)
    i0 = np.minimum(np.floor(fx).astype(int), nx - 2) if nx > 1 else np.zeros_like(fx, int)
    j0 = np.minimum(np.floor(fy).astype(int), ny - 2) if ny > 1 else np.zeros_like(fy, int)
    ax, ay = fx - i0, fy - j0
    i1, j1 = np.minimum(i0 + 1, nx - 1), np.minimum(j0 + 1, ny - 1)
    z = (el[j0, i0] * (1 - ax) * (1 - ay) + el[j0, i1] * ax * (1 - ay) + el[j1, i0] * (1 - ax) * ay
         + el[j1, i1] * ax * ay)
    return X.ravel(), Y.ravel(), z.ravel()


def _fila_masas(fila, masas, qfrac):
    """Masa de cada especie del puff nuevo: la fracción qfrac bajo la tapa (QM) y el resto por encima
    (QU, penetración en la inversión)."""
    for k, m in enumerate(masas):
        fila[nucleo.PM0 + 2 * k] = m * qfrac
        fila[nucleo.PM0 + 2 * k + 1] = m - m * qfrac


def _fila_elevacion(fila, e):
    """Copia la sobreelevación de la fuente en el estado del puff nuevo."""
    for col, val in ((nucleo.PHS, e.hs), (nucleo.PFB, e.fb), (nucleo.PFM, e.fm), (nucleo.PUS, e.us),
                     (nucleo.PBJ, e.bj), (nucleo.PSQS, e.sqs), (nucleo.PXFB, e.xfb),
                     (nucleo.PXFM, e.xfm), (nucleo.PDHBF, e.dhbf), (nucleo.PDHMF, e.dhmf),
                     (nucleo.PDM, e.dm), (nucleo.PDHF, e.dhf), (nucleo.PXF, e.xf),
                     (nucleo.PCOD, e.cod), (nucleo.PQFRAC, e.qfrac)):
        fila[col] = val
    if e.cod != 1:
        # penetración parcial (5) o total (3): techo de la parte penetrada y tapa de la de abajo
        fila[nucleo.PZIMAX] = e.zimax
        fila[nucleo.PZREF] = e.zref


def ejecutar(ruta_inp, carpeta=None, salida=None, verbose=True, traza_ids=(), receptor_dbg=-1,
             al_periodo=None):
    """Corre el modelo con el fichero de control `ruta_inp`. Devuelve (cabecera, periodos).
    `al_periodo(fin, conc)`: se llama al acabar cada hora con la fecha final (año, día juliano,
    hora, segundo) y las concentraciones por receptor (g/m3), p. ej. para una vista previa."""
    t0 = time.time()
    ruta_inp = Path(ruta_inp)
    carpeta = Path(carpeta or ruta_inp.parent)
    texto = ruta_inp.read_text(errors="ignore")
    cfg = entrada.leer(texto)
    _comprobar(cfg)
    metdat = carpeta / cfg.s("METDAT", "CALMET.DAT")
    if not metdat.exists():
        metdat = carpeta / metdat.name.lower()
    cab, horas = fichero_viento.leer(metdat)
    nx, ny, nz = cab.nx, cab.ny, cab.nz
    if (cfg.i("NX"), cfg.i("NY")) != (nx, ny):
        raise ValueError("la malla de CALPUFF.INP no coincide con la del CALMET.DAT")
    dg = cab.dgrid
    x0km, y0km = float(np.float32(cfg.r("XORIGKM"))), float(np.float32(cfg.r("YORIGKM")))
    zface = np.asarray(cab.zface, float)
    ilu = np.asarray(cab.ilandu, np.int64)
    # parámetros
    sv = np.array(cfg.lista("SVMIN") or [0.5] * 6 + [0.37] * 6, float)
    sw = np.array(cfg.lista("SWMIN") or [.2, .12, .08, .06, .03, .016] * 2, float)
    ppc = np.array(cfg.lista("PPC") or [.5, .5, .5, .5, .35, .35], float)
    par = np.zeros(nucleo.NPAR)
    par[nucleo.C_DG] = dg
    par[nucleo.C_NX] = nx
    par[nucleo.C_NY] = ny
    par[nucleo.C_IB] = cfg.i("IBCOMP", 1) - 1
    par[nucleo.C_IE] = cfg.i("IECOMP", nx)
    par[nucleo.C_JB] = cfg.i("JBCOMP", 1) - 1
    par[nucleo.C_JE] = cfg.i("JECOMP", ny)
    par[nucleo.C_XSAMLEN] = cfg.r("XSAMLEN", 1.0)
    par[nucleo.C_MXSAM] = cfg.i("MXSAM", 99)
    par[nucleo.C_WSCALM] = cfg.r("WSCALM", 0.5)
    par[nucleo.C_SYTDEP] = cfg.r("SYTDEP", 550.0)
    par[nucleo.C_XMINZI] = cfg.r("XMINZI", 50.0)
    par[nucleo.C_XMAXZI] = cfg.r("XMAXZI", 3000.0)
    par[nucleo.C_IURB1] = cfg.i("IURB1", 10)
    par[nucleo.C_IURB2] = cfg.i("IURB2", 19)
    par[nucleo.C_IWAT1] = cab.iwat1 or 50
    par[nucleo.C_IWAT2] = cab.iwat2 or 55
    par[nucleo.C_MCTADJ] = cfg.i("MCTADJ", 3)
    par[nucleo.C_NZ] = nz
    cdiv = cfg.lista("CDIV") or [0.0, 0.0]
    par[nucleo.C_CDIV1], par[nucleo.C_CDIV2] = cdiv[0], cdiv[1]
    par[nucleo.C_NCOUNT] = cfg.i("NCOUNT", 2)
    par[nucleo.C_JSUP] = cfg.i("JSUP", 5)
    par[nucleo.C_MXNEW] = cfg.i("MXNEW", 99)
    par[nucleo.C_CONK1] = cfg.r("CONK1", 0.01)
    par[nucleo.C_CONK2] = cfg.r("CONK2", 0.1)
    par[nucleo.C_MDISP] = cfg.i("MDISP", 3)
    par[nucleo.C_MTRANS] = cfg.i("MTRANS", 1)
    par[nucleo.C_FAV] = (cfg.r("AVET", 60.0) / cfg.r("PGTIME", 60.0)) ** 0.2 if cfg.i("MDISP", 3) in (3, 4) else 1.0
    if cfg.i("MDISP", 3) == 2 and any(f.bdw for f in cfg.fuentes):
        raise NoImplementado("efecto edificio con MDISP = 2")
    mtip = cfg.i("MTIP", 1)
    mbdw = cfg.i("MBDW", 1)
    tbd = cfg.r("TBD", 0.5)
    if mbdw not in (1, 2):
        raise NoImplementado("MBDW = %d" % mbdw)
    plx0 = cfg.lista("PLX0") or [0.07, 0.07, 0.10, 0.15, 0.35, 0.55]
    zmid = 0.5 * (zface[:-1] + zface[1:])
    xmxlen = cfg.r("XMXLEN", 1.0)
    mxnew = cfg.i("MXNEW", 99)
    symin, szmin = cfg.r("SYMIN", 1.0), cfg.r("SZMIN", 1.0)
    # receptores (coordenadas en km de 4 bytes, como el original)
    rec = cfg.receptores
    xr = (_f32(rec[:, 0]) - x0km) * 1000.0
    yr = (_f32(rec[:, 1]) - y0km) * 1000.0
    zr = rec[:, 2].astype(float)
    zp = rec[:, 3].astype(float)
    # malla de muestreo (LSAMP = T): receptores en los centros de las celdas IBSAMP..IESAMP,
    # JBSAMP..JESAMP con paso DGRIDKM/MESHDN, en el suelo, con la cota interpolada linealmente entre
    # los centros de celda del CALMET.DAT; van antes que los discretos en el CONC.DAT (caja negra:
    # qarecg.dat y registros del CONC.DAT)
    lsamp = cfg.s("LSAMP", "F").upper().startswith("T")
    if lsamp:
        xg, yg, zg = _malla_muestreo(cfg, cab, dg, nx, ny)
        xr = np.concatenate([xg, xr])
        yr = np.concatenate([yg, yr])
        zr = np.concatenate([zg, zr])
        zp = np.concatenate([np.zeros(len(xg)), zp])
    # fuentes: las del fichero de control y las de los ficheros de emisiones variables
    fuentes = list(cfg.fuentes) + _fuentes_arb(cfg, carpeta, cfg.i("MBDW", 1))
    # especies: masa de cada especie modelada en el puff (QM, QU); las emitidas llevan su emisión en
    # los datos de las fuentes en el orden del grupo 3a
    especies = cfg.especies
    nesp = len(especies)
    nombres = [e.nombre for e in especies]
    i_emit = [k for k, e in enumerate(especies) if e.emitida]
    ncolp = nucleo.ncol(nesp)
    # deposición seca (MDRY) y húmeda (MWET)
    mdry = cfg.i("MDRY", 0) == 1
    mwet = cfg.i("MWET", 0) == 1
    g9 = {"RCUTR": cfg.r("RCUTR", 30.0), "RGR": cfg.r("RGR", 10.0), "REACTR": cfg.r("REACTR", 8.0),
          "IVEG": cfg.i("IVEG", 1)}
    nint = cfg.i("NINT", 9)
    vd_usr = {}
    if mdry and any(e.seca == 3 for e in especies):
        vd_usr = deposicion.leer_vd((carpeta / cfg.s("VDDAT", "VD.DAT")).read_text(errors="ignore"))
    hay_dep = (mdry and any(e.seca for e in especies)) or (mwet and any(max(e.lavado) > 0 for e in especies))
    agua = (ilu >= (cab.iwat1 or 50)) & (ilu <= (cab.iwat2 or 55))
    z0m = np.asarray(cab.z0, float)
    laim = np.asarray(cab.xlai, float)
    wscat = cfg.lista("WSCAT") or [1.54, 3.09, 5.14, 8.23, 10.8]
    for f in fuentes:
        if f.tipo == 1 and (f.w <= 0.0 or f.ts <= 0.0):
            # el original no admite velocidad de salida ni temperatura nulas
            raise ValueError("fuente puntual %s: velocidad y temperatura de salida deben ser > 0" % f.nombre)
        if f.tipo == 3:
            vx = (_f32(f.vx) - x0km) * 1000.0
            vy = (_f32(f.vy) - y0km) * 1000.0
            f._vx, f._vy = vx, vy
            f._area = _area_poligono(vx, vy)
            f._xc, f._yc = float(vx.mean()), float(vy.mean())
        else:
            f._xc = (float(np.float32(f.x)) - x0km) * 1000.0
            f._yc = (float(np.float32(f.y)) - y0km) * 1000.0
    # tiempos: IBHR es la hora final del primer periodo (convención de hora final)
    ini = dt.datetime(cfg.i("IBYR"), cfg.i("IBMO"), cfg.i("IBDY")) + dt.timedelta(hours=cfg.i("IBHR"))
    irlg = cfg.i("IRLG")
    por_fecha = {h.ndathr: h for h in horas}
    P = np.zeros((0, ncolp))
    tablas = []          # PRIME: una fila por fuente y hora (prime.fila_tabla)
    tabla_fuente = []    # fuente de cada fila de `tablas`
    periodos = []
    per_dry, per_wet = [], []
    # especies de cada fichero de salida (grupo 5: concentración, flujo seco y húmedo guardados)
    s_conc = [k for k, e in enumerate(especies) if e.salida[1]]
    s_dry = [k for k, e in enumerate(especies) if len(e.salida) > 3 and e.salida[3]]
    s_wet = [k for k, e in enumerate(especies) if len(e.salida) > 5 and e.salida[5]]
    ids = np.asarray(traza_ids, float)
    traza = np.zeros((200000 if len(ids) else 0, nucleo.NTRAZA))
    ntr = np.zeros(1, np.int64)
    trazas = []
    nid = 0
    cdbg = np.zeros(200000)
    contrib = []
    nrec = len(xr)
    for kh in range(irlg):
        tfin = ini + dt.timedelta(hours=kh)
        nd = tfin.year * 100000 + tfin.timetuple().tm_yday * 100 + tfin.hour
        if nd not in por_fecha:
            raise ValueError("no hay meteorología para %d" % nd)
        h = por_fecha[nd]
        U = np.asarray(h.u, float)
        V = np.asarray(h.v, float)
        W = np.asarray(h.w, float) if h.w is not None else np.zeros_like(U)
        IPGT = np.asarray(h.d2["IPGT"], np.int64)
        ZI = np.asarray(h.d2["ZI"], float)
        EL = np.asarray(h.d2["EL"], float)
        TK = np.asarray(h.d2["TEMPK"], float)
        T3 = np.asarray(h.t, float) if h.t is not None else None
        nuevos, nnew = [], []
        hora_reloj = tfin.hour if tfin.hour > 0 else 24
        for f in fuentes:
            if getattr(f, "arb", None) is not None:
                _actualizar_arb(f, tfin, [especies[k].nombre for k in i_emit], x0km, y0km)
        tini_h = tfin - dt.timedelta(hours=1)
        # deposición: velocidad seca y tasa de lavado de cada especie por celda, u* y w*
        if hay_dep:
            US2 = np.asarray(h.d2["USTAR"], float)
            DEP = np.zeros((2 * nesp + 2, ny, nx))
            DEP[2 * nesp] = US2
            DEP[2 * nesp + 1] = np.asarray(h.d2["WSTAR"], float)
            ws10 = np.hypot(U[0], V[0])
            for k, e in enumerate(especies):
                if mdry and e.seca == 1:
                    DEP[k] = deposicion.vd_gas(e.gas, g9, US2, EL, z0m, laim, np.asarray(h.d2["QSW"], float),
                                               TK, ilu, agua, ws10)
                elif mdry and e.seca == 2:
                    DEP[k] = deposicion.vd_particula(e.part, nint, US2, EL, z0m, agua, ws10)
                elif mdry and e.seca == 3:
                    DEP[k] = vd_usr[e.nombre][hora_reloj - 1]
                if mwet and max(e.lavado) > 0.0:
                    DEP[nesp + k] = deposicion.lavado(e.lavado, np.asarray(h.d2["RMM"], float),
                                                      np.asarray(h.d2["IPCODE"], np.int64))
        else:
            DEP = np.zeros((1, 1, 1))
        M2 = np.stack([np.asarray(h.d2["USTAR"], float), np.asarray(h.d2["WSTAR"], float),
                       np.asarray(cab.elev, float)])
        # PRIME: la zona de exclusión de receptores (zona de la cavidad) es la de la hora actual de cada
        # fuente y vale para todos sus puffs (de esta hora y de las anteriores); sin efecto PRIME en
        # la hora (calma, sector sin edificio) no hay exclusión (caja negra)
        for fl in tablas:
            fl[prm.T_EXC] = -1.0
        exc = []
        conc_cav = np.zeros((nrec, nesp))
        for js, f in enumerate(fuentes):
            ix, iy = nucleo.celda(f._xc / dg, f._yc / dg, nx, ny)
            hem = f.h
            ele = None
            est = None
            pri = None
            if f.tipo == 1:
                # sobreelevación con el viento de la capa que contiene la chimenea y la meteorología
                # de la celda de la fuente; los puffs se cuentan con el viento de la altura final
                kz = min(max(int(np.searchsorted(zface, f.h, side="right") - 1), 0), nz - 1)
                # en reales de 4 bytes, como el original (umbral de 1 m/s con vientos de 1,0 exacto)
                u32, v32 = np.float32(U[kz, iy, ix]), np.float32(V[kz, iy, ix])
                us = float(np.sqrt(u32 * u32 + v32 * v32))
                zis = min(max(ZI[iy, ix], par[nucleo.C_XMINZI]), par[nucleo.C_XMAXZI])
                if T3 is None:
                    raise NoImplementado("sobreelevación sin temperaturas 3D en el CALMET.DAT")
                if f.bdw and mbdw == 2:
                    pri = _prime(f, u32, v32, us, U, V, T3, ix, iy, zface, int(IPGT[iy, ix]),
                                 int(ilu[iy, ix]), par, plx0)
                elif f.bdw:
                    # efecto edificio ISC: dimensiones del sector del vector de flujo de la capa de
                    # la chimenea
                    ks = edificios.sector(float(u32), float(v32))
                    lu = abs(int(ilu[iy, ix]))
                    est = edificios.isc(f.h, f.d, f.w, f.ts, TK[iy, ix], us, int(IPGT[iy, ix]),
                                        f.edif["HEIGHT"][ks - 1], f.edif["WIDTH"][ks - 1], tbd,
                                        zmid, T3[:, iy, ix],
                                        par[nucleo.C_IURB1] <= lu <= par[nucleo.C_IURB2],
                                        max(symin, f.sy0), max(szmin, f.sz0))
                    if est.idw == 0:
                        est = None
                ss = est is not None and est.idw == 2
                if pri is not None:
                    # PRIME: altura final y distancia de la trayectoria numérica; código y reparto de
                    # la masa por la penetración sin recortar la elevación (caja negra)
                    ele = _elevacion_prime(f, pri, us, TK[iy, ix], int(IPGT[iy, ix]), zis, zmid,
                                           T3[:, iy, ix])
                else:
                    # con Schulman-Scire no hay efecto punta de chimenea (caja negra: TIPDW = 0)
                    ele = elevacion(f.h, f.d, f.w, f.ts, TK[iy, ix], us, int(IPGT[iy, ix]), zis,
                                    zmid, T3[:, iy, ix], 0 if ss else mtip, mpartl=cfg.i("MPARTL", 1),
                                    ss=(est.r0, est.ly) if ss else None, fmfac=f.fmfac)
                hem = ele.hs + ele.dhf
            kz = int(np.searchsorted(zface, hem, side="right") - 1)
            kz = min(max(kz, 0), nz - 1)
            u0, v0 = U[kz, iy, ix], V[kz, iy, ix]
            ws0 = math.hypot(u0, v0)
            # módulo en reales de 4 bytes, como el original (n exacto con vientos de valor redondo)
            u32, v32 = np.float32(u0), np.float32(v0)
            xx = np.sqrt(u32 * u32 + v32 * v32) * np.float32(3600.0) / np.float32(xmxlen * dg)
            n = min(int(math.floor(xx)) + 1, mxnew)
            # emisión de cada especie (g/s) con su factor de variación
            qesp = np.zeros(nesp)
            for j, k in enumerate(i_emit):
                if j < len(f.qs):
                    qesp[k] = f.qs[j] * (f._area if f.tipo == 3 else 1.0) * _factor_emision(
                        f, nombres[k], hora_reloj, tini_h.month, ws0, int(IPGT[iy, ix]), TK[iy, ix], wscat)
            qtot = qesp[0] if nesp else 0.0
            masa = qtot * 3600.0 / n
            masas = qesp * 3600.0 / n
            if pri is not None:
                st, tr, ub, ux, uy = pri
                # tapa y techo de la parte penetrada para CAV_CONC (caja negra): ZI en A-D; el techo
                # es el ZIMAX de la penetración parcial o, con toda la masa por encima (código 3),
                # 2·(hs + zp) − ZI, simétrico respecto a la altura de penetración de Manins
                tapa_cav = zis if int(IPGT[iy, ix]) <= 4 else None
                if ele.cod == 5:
                    zsup_cav = ele.zimax
                elif ele.cod == 3:
                    zsup_cav = 2.0 * (ele.hs + ele.zp) - zis
                else:
                    zsup_cav = 0.0
                fl = prm.fila_tabla(st, tr)
                kt = len(tablas)
                # concentración de la zona de la cavidad (CAV_CONC) y receptores excluidos de los
                # puffs de esta fuente: en la fila, el final de la zona desde la chimenea (−1 fuera)
                mask = np.full(nrec, -1.0)
                x115 = st.XBADJ + st.XLB + 1.15 * st.XLR
                for r in range(nrec):
                    dx, dy = xr[r] - f._xc, yr[r] - f._yc
                    xf, yf = dx * ux + dy * uy, -dx * uy + dy * ux
                    if prm.zona_exclusion(st, xf, yf):
                        mask[r] = x115
                        if prm.region_cavidad(st, xf, yf):
                            conc_cav[r] += qesp * prm.cav_conc(st, tr, xf, yf, zp[r], us, ub,
                                                               tapa_cav, zsup_cav)
                tablas.append(fl)
                tabla_fuente.append(js)
                if (mask >= 0.0).any():
                    for kk, jf in enumerate(tabla_fuente):
                        if jf == js:
                            tablas[kk][prm.T_EXC] = len(exc)
                    exc.append(mask)
            sy0sq, lc2 = 0.0, 0.0
            if f.tipo == 3:
                # anchura transversal al viento del polígono
                ang = math.atan2(v0, u0) if ws0 > 0.0 else 0.0
                cr = -np.sin(ang) * f._vx + np.cos(ang) * f._vy
                lc = float(cr.max() - cr.min())
                sy0sq = (lc / math.sqrt(2.0 * math.pi)) ** 2
                lc2 = 0.5 * lc
            for k in range(n):
                fila = np.zeros(ncolp)
                fila[nucleo.PX] = f._xc / dg
                fila[nucleo.PY] = f._yc / dg
                fila[nucleo.PH] = hem
                fila[nucleo.PHS] = hem
                fila[nucleo.PZB] = f.zbase
                fila[nucleo.PHFIS] = f.h
                fila[nucleo.PQ] = masa
                fila[nucleo.PSY] = max(symin, f.sy0)
                fila[nucleo.PSZ] = max(szmin, f.sz0)
                fila[nucleo.PSYI] = fila[nucleo.PSY]
                fila[nucleo.PSZI] = fila[nucleo.PSZ]
                fila[nucleo.PSY0] = sy0sq
                fila[nucleo.PLC2] = lc2
                fila[nucleo.PZIMAX] = nucleo.SIN_TAPA
                fila[nucleo.PVIVO] = 1.0
                fila[nucleo.PQFRAC] = 1.0
                fila[nucleo.PFUENTE] = js
                fila[nucleo.PTIPO] = f.tipo
                nid += 1
                fila[nucleo.PID] = nid
                fila[nucleo.PCOD] = 1.0
                fila[nucleo.PZREF] = nucleo.SIN_TAPA
                if ele is not None:
                    _fila_elevacion(fila, ele)
                if est is not None:
                    _fila_estela(fila, est, max(symin, f.sy0), max(szmin, f.sz0))
                fm = 1.0
                if pri is not None:
                    _fila_prime(fila, pri, kt, symin, szmin, 1)
                    fm = 1.0 - prm.fqcav_ef(st)
                    fila[nucleo.PQ] = masa * fm
                _fila_masas(fila, masas * fm, fila[nucleo.PQFRAC])
                nuevos.append(fila)
                nnew.append((n, k))
            if pri is not None and prm.fqcav_ef(st) > 0.0:
                # puffs de la fuente de la cavidad: en el suelo, DISTC aguas abajo de la chimenea
                xc, yc = _fuente_cavidad(f, st, ux, uy)
                for k in range(n):
                    fila = np.zeros(ncolp)
                    fila[nucleo.PX] = xc / dg
                    fila[nucleo.PY] = yc / dg
                    fila[nucleo.PZB] = f.zbase
                    fila[nucleo.PQ] = masa * prm.fqcav_ef(st)
                    fila[nucleo.PZIMAX] = nucleo.SIN_TAPA
                    fila[nucleo.PVIVO] = 1.0
                    fila[nucleo.PQFRAC] = 1.0
                    fila[nucleo.PFUENTE] = js
                    fila[nucleo.PTIPO] = f.tipo
                    nid += 1
                    fila[nucleo.PID] = nid
                    fila[nucleo.PCOD] = 1.0
                    fila[nucleo.PZREF] = nucleo.SIN_TAPA
                    _fila_prime(fila, pri, kt, symin, szmin, 2)
                    _fila_masas(fila, masas * prm.fqcav_ef(st), 1.0)
                    nuevos.append(fila)
                    nnew.append((n, k))
        nuevos = np.array(nuevos).reshape(-1, ncolp)
        nnew = np.array(nnew, np.int64).reshape(-1, 2)
        conc = np.zeros((nrec, nesp))
        dflx = np.zeros((nrec, nesp))
        wflx = np.zeros((nrec, nesp))
        ntr[0] = 0
        TB = np.array(tablas) if tablas else np.zeros((1, prm.NTCOL))
        EXC = np.array(exc) if exc else np.full((1, max(nrec, 1)), -1.0)
        nucleo.hora(P, P.shape[0], nuevos, nnew, U, V, W, zface, IPGT, ZI, EL, ilu, sv, sw, ppc, par,
                    xr, yr, zr, zp, conc, ids, traza, ntr, receptor_dbg, cdbg, TB, EXC, DEP, M2, dflx, wflx)
        conc += conc_cav
        if receptor_dbg >= 0:
            nzc = np.nonzero(cdbg)[0]
            contrib.append({int(j): float(cdbg[j]) for j in nzc})
            cdbg[:] = 0.0
        if len(ids):
            trazas += [(nd,) + tuple(fila) for fila in traza[:ntr[0]]]
        P = np.vstack([P[P[:, nucleo.PVIVO] > 0.5], nuevos[nuevos[:, nucleo.PVIVO] > 0.5]])
        if tablas:
            # PRIME: se guardan solo las tablas que usan los puffs vivos, renumeradas
            pri_ = P[:, nucleo.PPRI] > 0.5
            usadas = np.unique(P[pri_, nucleo.PTAB].astype(np.int64))
            tablas = [tablas[k] for k in usadas]
            tabla_fuente = [tabla_fuente[k] for k in usadas]
            P[pri_, nucleo.PTAB] = np.searchsorted(usadas, P[pri_, nucleo.PTAB].astype(np.int64))
        tini = tfin - dt.timedelta(hours=1)
        ti = (tini.year, tini.timetuple().tm_yday, tini.hour, 0)
        tf = (tfin.year, tfin.timetuple().tm_yday, tfin.hour, 0)
        periodos.append(fichero_conc.Periodo(ti, tf, {"%-12s%3s" % (nombres[k], "1"): conc[:, k].astype(np.float32)
                                                  for k in s_conc}))
        per_dry.append(fichero_conc.Periodo(ti, tf, {"%-12s%3s" % (nombres[k], "DF"): dflx[:, k].astype(np.float32)
                                                for k in s_dry}))
        per_wet.append(fichero_conc.Periodo(ti, tf, {"%-12s%3s" % (nombres[k], "WF"): wflx[:, k].astype(np.float32)
                                                for k in s_wet}))
        if al_periodo is not None:
            al_periodo(periodos[-1].fin, conc[:, 0])
        if verbose:
            print("   %d %8d puffs  (%.1f s)" % (nd, P.shape[0], time.time() - t0), flush=True)
    # cabecera del CONC.DAT
    c = fichero_conc.Cabecera()
    c.comentarios = ["Produced by %s Version: %s  Level: %s" % (PROGRAMA, VERSION, NIVEL)] + \
        texto.replace("\r", "").split("\n")
    c.modelo, c.version, c.nivel = PROGRAMA, VERSION, NIVEL
    t1 = ini - dt.timedelta(hours=1)
    c.ibyr, c.ibjul, c.ibhr, c.ibsec = t1.year, t1.timetuple().tm_yday, t1.hour, 0
    c.xbtz = cfg.r("XBTZ", 0.0)
    c.irlg, c.iavg, c.nsecdt = irlg, 1, 3600
    c.nx, c.ny, c.dxkm, c.dykm = nx, ny, dg / 1000.0, dg / 1000.0
    c.xorigkm, c.yorigkm = x0km, y0km
    c.comp = (cfg.i("IBCOMP", 1), cfg.i("IECOMP", nx), cfg.i("JBCOMP", 1), cfg.i("JECOMP", ny))
    c.samp = (cfg.i("IBSAMP", 1), cfg.i("JBSAMP", 1), cfg.i("IESAMP", nx), cfg.i("JESAMP", ny))
    c.meshdn = cfg.i("MESHDN", 1)
    c.nfuentes = dict.fromkeys(fichero_conc.TIPOS_FUENTE, 0)
    for tipo, arb, clave, ist in CLASES:
        sel = [f.nombre for f in fuentes if f.tipo == tipo and (getattr(f, "arb", None) is not None) == arb]
        c.nfuentes[clave] = len(sel)
        if sel:
            c.nombres[clave] = (ist, sel)
    c.lsamp, c.lcompr = lsamp, cfg.s("LCOMPRS", "T").upper().startswith("T")
    c.iutmzn = cfg.i("IUTMZN", cab.iutmzn)
    c.utmhem = cfg.s("UTMHEM", "N")
    c.datum = cfg.s("DATUM", "WGS-84")
    c.pmap = cfg.s("PMAP", "UTM")
    c.titulo = [texto.replace("\r", "").split("\n")[0], "", ""]
    c.especies = ["%-12s%3s" % (nombres[k], "1") for k in s_conc]
    c.xrec, c.yrec, c.zrec = rec[:, 0].astype(np.float32), rec[:, 1].astype(np.float32), \
        rec[:, 2].astype(np.float32)
    c.fuente_total = (0, 1, "TOTAL", x0km, y0km)
    ejecutar.trazas = trazas
    ejecutar.contrib = contrib
    if salida is not False:
        fichero_conc.escribir(salida or (carpeta / cfg.s("CONDAT", "CONC.DAT")), c, periodos)
        # flujos de deposición seca (DFLX.DAT) y húmeda (WFLX.DAT): misma estructura que el CONC.DAT
        # ([UG] secs. 4.14.4 y 4.14.5) con el nombre de la especie seguido de «DF» o «WF»
        import copy
        for flag, nom, def_, lista, per, suf in (("IDRY", "DFDAT", "DFLX.DAT", s_dry, per_dry, "DF"),
                                                 ("IWET", "WFDAT", "WFLX.DAT", s_wet, per_wet, "WF")):
            if cfg.i(flag, 0) == 1 and lista:
                cf = copy.copy(c)
                cf.dataset = def_
                cf.especies = ["%-12s%3s" % (nombres[k], suf) for k in lista]
                ruta = Path(salida).parent / (Path(salida).stem + "_" + suf + ".DAT") if salida else \
                    carpeta / cfg.s(nom, def_)
                fichero_conc.escribir(ruta, cf, per)
    ejecutar.flujos = (per_dry, per_wet)
    if verbose:
        print("%s: %d periodos, %d receptores, %.1f s" % (PROGRAMA, irlg, nrec, time.time() - t0))
    return c, periodos


if __name__ == "__main__":
    ejecutar(sys.argv[1] if len(sys.argv) > 1 else "CALPUFF.INP")
