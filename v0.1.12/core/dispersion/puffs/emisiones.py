# -*- coding: utf-8 -*-
"""Ficheros de emisión con parámetros variables: PTEMARB.DAT (fuentes puntuales) y VOLEMARB.DAT
(fuentes de volumen).

Fuentes (ver FUENTES.md del laboratorio):
  - [UG] sec. 4.3, tablas 4-16 a 4-19: PTEMARB.DAT de la versión 5, ASCII de formato libre (lectura
    dirigida por lista): cabecera FNAME, NSRC, NSE, IUTMZ, IBDAT, IBTIM, IEDAT, IETIM, VRS, LABEL;
    especies; pesos moleculares; por fuente CID, X, Y (km), altura, diámetro, cota, indicador de
    efecto edificio, código del usuario (y 36 alturas y 36 anchuras del edificio si lo hay); por
    periodo IBDAT, IBTIM, IEDAT, IETIM (fecha YYYYJJJ y hora de final de periodo) y por fuente CID,
    temperatura, velocidad de salida y emisiones. Es el formato que acepta calpuff.exe 5.8.5 (caja
    negra: VRS = '5'; rechaza la versión 2.1 de la guía V6).
  - [V6] secs. 9.3 y 9.6, tablas 9-16 a 9-19 y 9-28 a 9-31: versión 2.1 (comentarios, proyección,
    zona horaria, fechas con segundos; PTEMARB con FMFAC y σy, σz iniciales por periodo; VOLEMARB con
    posición, altura efectiva, cota y σ iniciales por periodo). calpuff.exe 5.8.5 no la acepta (exige
    VOLEMARB de una versión ≥ 5.4 sin documentar), así que se valida por equivalencia con las fuentes
    del fichero de control.
"""
import datetime as dt
import re

_TOKEN = re.compile(r"'([^']*)'|\"([^\"]*)\"|([^\s,']+)")


def _tokens(texto):
    """Elementos de una lectura dirigida por lista (cadenas entre comillas o valores)."""
    out = []
    for m in _TOKEN.finditer(texto):
        if m.group(1) is not None:
            out.append(m.group(1))
        elif m.group(2) is not None:
            out.append(m.group(2))
        else:
            out.append(m.group(3))
    return out


def _fecha_v5(ymd, hh):
    """YYYYJJJ (o YYJJJ) y hora de final de periodo -> datetime del final del periodo."""
    ymd = int(ymd)
    y, j = divmod(ymd, 1000)
    if y < 100:
        y += 1900 if y >= 50 else 2000
    return dt.datetime(y, 1, 1) + dt.timedelta(days=j - 1, hours=int(hh))


def _fecha_v21(y, j, h, s):
    """Año, día juliano, hora y segundo (versión 2.1) -> datetime."""
    return dt.datetime(int(y), 1, 1) + dt.timedelta(days=int(j) - 1, hours=int(h), seconds=int(s))


class Arb:
    """Fichero de emisión variable leído: fuentes fijas y periodos con los datos por fuente."""

    def __init__(self):
        self.especies = []
        self.fuentes = []         # dicts con los datos fijos
        self.periodos = []        # (t0, t1, {cid: datos}); el periodo que acaba en t vale si t0 < t ≤ t1
        self.v21 = False

    def datos(self, tfin):
        """Datos por fuente del periodo que termina en tfin."""
        for t0, t1, d in self.periodos:
            if t0 < tfin <= t1:
                return d
        raise ValueError("el fichero de emisiones no cubre el periodo que termina en %s" % tfin)


def leer_ptemarb(texto, mbdw=1):
    """PTEMARB.DAT (versión 5 o 2.1)."""
    a = Arb()
    lin = texto.replace("\r", "").split("\n")
    if lin[0][:16].strip().upper().startswith("PTEMARB.DAT"):
        return _leer_ptemarb21(lin, a)
    tk = _tokens(texto)
    p = 0
    fname, nsrc, nse = tk[0], int(tk[1]), int(tk[2])
    p = 10
    a.especies = [t.strip().upper() for t in tk[p:p + nse]]
    p += 2 * nse
    for _ in range(nsrc):
        cid = tk[p].strip()
        x, y, hs, d, zb, bdw = [float(v) for v in tk[p + 1:p + 7]]
        p += 8
        f = dict(cid=cid, x=x, y=y, h=hs, d=d, zb=zb, bdw=bdw, fmfac=1.0, edif=None)
        if bdw:
            narr = 5 if mbdw == 2 else 2
            arr = [float(v) for v in tk[p:p + 36 * narr]]
            p += 36 * narr
            f["edif"] = {k: arr[36 * i:36 * (i + 1)] for i, k in enumerate(("HEIGHT", "WIDTH", "LENGTH", "XBADJ",
                                                                           "YBADJ")[:narr])}
        a.fuentes.append(f)
    while p + 4 <= len(tk):
        t0 = _fecha_v5(tk[p], tk[p + 1]) - dt.timedelta(hours=1)
        t1 = _fecha_v5(tk[p + 2], tk[p + 3])
        p += 4
        d = {}
        for _ in range(nsrc):
            cid = tk[p].strip()
            ts, w = float(tk[p + 1]), float(tk[p + 2])
            q = [float(v) for v in tk[p + 3:p + 3 + nse]]
            p += 3 + nse
            d[cid] = dict(ts=ts, w=w, q=q, sy0=0.0, sz0=0.0)
        a.periodos.append((t0, t1, d))
    return a


def _cabecera21(lin, a):
    """Cabecera de la versión 2.1: devuelve el índice de la línea de los periodos."""
    a.v21 = True
    ncom = int(lin[1].split()[0])
    k = 2 + ncom
    pmap = lin[k].split()[0].upper()
    k += 1
    if pmap == "UTM":
        k += 1
    elif pmap in ("LCC", "PS", "EM", "LAZA", "TTM"):
        k += 1
        if pmap in ("TTM", "LCC", "LAZA"):
            k += 1
    k += 1          # DATUM y fecha
    k += 1          # unidades
    k += 1          # zona horaria
    return k


def _leer_ptemarb21(lin, a):
    k = _cabecera21(lin, a)
    resto = "\n".join(lin[k + 1:])
    tk = _tokens(resto)
    nsrc, nse = int(tk[0]), int(tk[1])
    p = 2
    a.especies = [t.strip().upper() for t in tk[p:p + nse]]
    p += 2 * nse
    for _ in range(nsrc):
        cid = tk[p].strip()
        x, y, hs, d, zb, bdw, fmfac = [float(v) for v in tk[p + 1:p + 8]]
        p += 9
        f = dict(cid=cid, x=x, y=y, h=hs, d=d, zb=zb, bdw=bdw, fmfac=fmfac, edif=None)
        if bdw:
            arr = [float(v) for v in tk[p:p + 180]]
            p += 180
            f["edif"] = {kk: arr[36 * i:36 * (i + 1)] for i, kk in enumerate(("HEIGHT", "WIDTH", "LENGTH",
                                                                            "XBADJ", "YBADJ"))}
        a.fuentes.append(f)
    while p + 8 <= len(tk):
        t0 = _fecha_v21(*tk[p:p + 4])
        t1 = _fecha_v21(*tk[p + 4:p + 8])
        p += 8
        d = {}
        for _ in range(nsrc):
            cid = tk[p].strip()
            ts, w, sy, sz = [float(v) for v in tk[p + 1:p + 5]]
            q = [float(v) for v in tk[p + 5:p + 5 + nse]]
            p += 5 + nse
            d[cid] = dict(ts=ts, w=w, q=q, sy0=sy, sz0=sz)
        a.periodos.append((t0, t1, d))
    return a


def leer_volemarb(texto):
    """VOLEMARB.DAT (versión 2.1 de la guía V6)."""
    a = Arb()
    lin = texto.replace("\r", "").split("\n")
    if not lin[0][:16].strip().upper().startswith("VOLEMARB.DAT"):
        raise ValueError("VOLEMARB.DAT: solo se admite la versión 2.1 de la guía V6")
    k = _cabecera21(lin, a)
    tk = _tokens("\n".join(lin[k + 1:]))
    nsrc, nse = int(tk[0]), int(tk[1])
    p = 2
    a.especies = [t.strip().upper() for t in tk[p:p + nse]]
    p += 2 * nse
    for _ in range(nsrc):
        a.fuentes.append(dict(cid=tk[p].strip()))
        p += 2
    while p + 8 <= len(tk):
        t0 = _fecha_v21(*tk[p:p + 4])
        t1 = _fecha_v21(*tk[p + 4:p + 8])
        p += 8
        d = {}
        for _ in range(nsrc):
            cid = tk[p].strip()
            x, y, h, zb, sy, sz = [float(v) for v in tk[p + 1:p + 7]]
            q = [float(v) for v in tk[p + 7:p + 7 + nse]]
            p += 7 + nse
            d[cid] = dict(x=x, y=y, h=h, zb=zb, sy0=sy, sz0=sz, q=q)
        a.periodos.append((t0, t1, d))
    return a
