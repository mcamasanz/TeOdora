# -*- coding: utf-8 -*-
"""Traducción de AERMOD 26135 (US EPA, dominio público): re-arranque de corridas y corridas de
varios años encadenados (SAVEFILE, INITFILE y MULTYEAR).

- RSDUMP (calc2.f): vuelca las matrices de resultados a un fichero sin formato de Intel.
- RSINIT (inpsum.f): las recupera al empezar la corrida siguiente.
- La reanudación de los ficheros de salida (MAXIFILE, POSTFILE, MAXDAILY, MXDYBYYR) de ouset.f:
  el original los abre, los lee hasta la fecha del re-arranque, hace BACKSPACE y sigue escribiendo.

Los registros siguen el orden de los bucles implícitos del original (el primer índice varía más
rápido): `_f` aplana en orden de Fortran la parte 1..n de cada dimensión."""
import os
import struct

import numpy as np

from .formato import fwrite, nint


def _f(a, *dims):
    """Bloque a(1:d1, 1:d2, ...) aplanado en el orden de Fortran."""
    return a[tuple(slice(1, d + 1) for d in dims)].ravel(order="F")


def _d(a, *dims):
    return _f(a, *dims).astype("<f8").tobytes()


def _i(a, *dims):
    return _f(a, *dims).astype("<i4").tobytes()


def _c(a, *dims):
    return "".join((x or " ")[:1] for x in _f(a, *dims)).encode("latin-1")


def _ints(*v):
    return struct.pack("<%di" % len(v), *[int(x) for x in v])


# ------------------------------------------------------------------------------------- RSDUMP
def rsdump(e):
    """RSDUMP: resultados intermedios al SAVEFILE (alterna SAVFIL y SAVFL2 si son distintos)."""
    m = "RSDUMP"
    e.NDUMP += 1
    if e.MONTH and not e.ENDMON:
        return
    nom = e.SAVFIL if (e.SAVFIL == e.SAVFL2 or e.NDUMP % 2 != 0) else e.SAVFL2
    nr, ng, na, nt = e.NUMREC, e.NUMGRP, e.NUMAVE, e.NUMTYP
    nh, nm = e.NHIVAL, e.NMXVAL
    regs = [_ints(e.FULLDATE, e.NTOTHRS), _ints(nh, nm, nr, ng, na, nt)]
    if nh > 0:
        regs.append(_d(e.HIVALU, nr, nh, ng, na, nt))
        regs.append(_i(e.NHIDAT, nr, nh, ng, na, nt))
        regs.append(_c(e.HCLMSG, nr, nh, ng, na, nt))
        if e.PM25AVE or e.NO2AVE or e.SO2AVE:
            ny = e.NUMYRS
            regs.append(_ints(ny))
            regs.append(_d(e.SUMHNH, nr, ng, nh))
            regs.append(_d(e.HIMXDLY, nr, ng, nh))
            regs.append(_i(e.NHIDATMXD, nr, ng, nh))
            regs.append(_d(e.HIMXDLY_BYYR, nr, ng, nh, ny))
            regs.append(_i(e.NHIDATMXD_BYYR, nr, ng, nh, ny))
    if nm > 0:
        regs.append(_d(e.RMXVAL, nm, ng, na, nt))
        regs.append(_i(e.MXDATE, nm, ng, na, nt))
        regs.append(_i(e.MXLOCA, nm, ng, na, nt))
        regs.append(_c(e.MCLMSG, nm, ng, na, nt))
    if e.SEASONHR:
        regs.append(_d(e.SHVALS, nr, ng, 4, 24, nt))
        regs.append(_i(e.NSEAHR, 4, 24))
        regs.append(_i(e.NSEACM, 4, 24))
    if e.PERIOD:
        regs.append(_ints(e.IANHRS, e.IANCLM, e.IANMSG, e.NUMYRS))
        regs.append(_d(e.ANNVAL, nr, ng, nt))
        if e.MULTYR:
            nha = e.NHIANN
            regs.append(_d(e.AMXVAL, nha, ng, nt))
            regs.append(_i(e.IMXLOC, nha, ng, nt))
    elif e.ANNUAL:
        regs.append(_ints(e.IANHRS, e.IANCLM, e.IANMSG, e.NUMYRS))
        regs.append(_d(e.ANNVAL, nr, ng, nt))
        regs.append(_d(e.SUMANN, nr, ng, nt))
    try:
        with open(nom, "wb") as fh:
            for r in regs:
                n = len(r).to_bytes(4, "little")
                fh.write(n + r + n)
    except OSError:
        e.errhdl(e.PATH, m, "E", "500", "SAVEFILE")
        e.RUNERR = True


# ------------------------------------------------------------------------------------- RSINIT
class _FinDatos(Exception):
    pass


def _leer(u, fmt_items):
    """READ(IRSUNT) de un registro: lista de (tipo, n) con tipo 'i', 'd' o 'c'. Devuelve las
    piezas como matrices numpy (o cadenas). Error de lectura si el registro es más corto."""
    r = u.leer()
    if r is None:
        raise _FinDatos()
    out, pos = [], 0
    for t, n in fmt_items:
        tam = {"i": 4, "d": 8, "c": 1}[t] * n
        if pos + tam > len(r):
            raise ValueError("registro corto")
        trozo = r[pos:pos + tam]
        if t == "i":
            out.append(np.frombuffer(trozo, dtype="<i4").astype(np.int64))
        elif t == "d":
            out.append(np.frombuffer(trozo, dtype="<f8").astype(np.float64))
        else:
            out.append(trozo.decode("latin-1"))
        pos += tam
    return out


def _poner(a, v, *dims):
    """a(1:d1, ...) = v (aplanado en orden de Fortran)."""
    blk = tuple(slice(1, d + 1) for d in dims)
    a[blk] = np.asarray(v).reshape(dims, order="F")


def _poner_c(a, s, *dims):
    blk = tuple(slice(1, d + 1) for d in dims)
    v = np.array([" " if c == " " else c for c in s], dtype=object)
    v = np.where(v == " ", "", v)
    a[blk] = v.reshape(dims, order="F")


def rsinit(e):
    """RSINIT: inicializa los resultados desde el fichero de re-arranque (INITFILE o el SAVEFILE
    del año anterior con MULTYEAR)."""
    m = "RSINIT"
    u = e.U[e.IRSUNT]
    irsdate = 0
    try:
        irsdate, ntot = (int(x) for x in _leer(u, [("i", 2)])[0])
        e.NTOTHRS = ntot
        if not e.MULTYR and e.IMSTAT[6] == 1 and irsdate < e.ISDATE:
            e.errhdl(e.PATH, m, "E", "484", "STARTEND")
            e.RUNERR = True
            return
        elif e.MULTYR and e.IMSTAT[6] == 1 and irsdate < e.ISDATE:
            e.errhdl(e.PATH, m, "W", "485", "STARTEND")
        elif e.MULTYR and e.IMSTAT[6] == 1 and irsdate > e.ISDATE:
            e.DUMMY = fwrite("(I10.10)", irsdate - (irsdate // 100000000) * 100000000)[0]
            e.errhdl(e.PATH, m, "E", "486", e.DUMMY)
            e.RUNERR = True
            return
        else:
            e.ISDATE = irsdate
        v = _leer(u, [("i", 6)])[0]
        e.NHIVAL, e.NMXVAL, e.NUMREC, e.NUMGRP, e.NUMAVE, e.NUMTYP = (int(x) for x in v)
        nr, ng, na, nt = e.NUMREC, e.NUMGRP, e.NUMAVE, e.NUMTYP
        nh, nm = e.NHIVAL, e.NMXVAL
        if nh > 0:
            n5 = nr * nh * ng * na * nt
            _poner(e.HIVALU, _leer(u, [("d", n5)])[0], nr, nh, ng, na, nt)
            _poner(e.NHIDAT, _leer(u, [("i", n5)])[0], nr, nh, ng, na, nt)
            _poner_c(e.HCLMSG, _leer(u, [("c", n5)])[0], nr, nh, ng, na, nt)
            if e.PM25AVE or e.NO2AVE or e.SO2AVE:
                e.NUMYRS = int(_leer(u, [("i", 1)])[0][0])
                ny = e.NUMYRS
                n3 = nr * ng * nh
                _poner(e.SUMHNH, _leer(u, [("d", n3)])[0], nr, ng, nh)
                _poner(e.HIMXDLY, _leer(u, [("d", n3)])[0], nr, ng, nh)
                _poner(e.NHIDATMXD, _leer(u, [("i", n3)])[0], nr, ng, nh)
                _poner(e.HIMXDLY_BYYR, _leer(u, [("d", n3 * ny)])[0], nr, ng, nh, ny)
                _poner(e.NHIDATMXD_BYYR, _leer(u, [("i", n3 * ny)])[0], nr, ng, nh, ny)
        if nm > 0:
            n4 = nm * ng * na * nt
            _poner(e.RMXVAL, _leer(u, [("d", n4)])[0], nm, ng, na, nt)
            _poner(e.MXDATE, _leer(u, [("i", n4)])[0], nm, ng, na, nt)
            _poner(e.MXLOCA, _leer(u, [("i", n4)])[0], nm, ng, na, nt)
            _poner_c(e.MCLMSG, _leer(u, [("c", n4)])[0], nm, ng, na, nt)
        if e.SEASONHR:
            _poner(e.SHVALS, _leer(u, [("d", nr * ng * 4 * 24 * nt)])[0], nr, ng, 4, 24, nt)
            _poner(e.NSEAHR, _leer(u, [("i", 96)])[0], 4, 24)
            _poner(e.NSEACM, _leer(u, [("i", 96)])[0], 4, 24)
        if e.PERIOD or e.ANNUAL:
            v = _leer(u, [("i", 4)])[0]
            e.IANHRS, e.IANCLM, e.IANMSG, e.NUMYRS = (int(x) for x in v)
            _poner(e.ANNVAL, _leer(u, [("d", nr * ng * nt)])[0], nr, ng, nt)
            if e.PERIOD and e.MULTYR:
                e.ANNVAL[...] = 0.0
                e.IANHRS = 0
                e.IANCLM = 0
                e.IANMSG = 0
                nha = e.NHIANN
                _poner(e.AMXVAL, _leer(u, [("d", nha * ng * nt)])[0], nha, ng, nt)
                _poner(e.IMXLOC, _leer(u, [("i", nha * ng * nt)])[0], nha, ng, nt)
            elif not e.PERIOD:
                _poner(e.SUMANN, _leer(u, [("d", nr * ng * nt)])[0], nr, ng, nt)
    except _FinDatos:
        e.DUMMY = "INITFILE"
        e.errhdl(e.PATH, m, "E", "580", e.DUMMY)
        e.RUNERR = True
    except (ValueError, IndexError):
        e.DUMMY = "INITFILE"
        e.errhdl(e.PATH, m, "E", "510", e.DUMMY)
        e.RUNERR = True


# ------------------------------------------------------------- reanudación de ficheros (ouset.f)
def fecha_reinicio(e):
    """READ(IRSUNT) IRSDATE + REWIND. Devuelve None si no se puede leer (error 919 del llamador)."""
    u = e.U.get(e.IRSUNT)
    if u is None:
        return None
    try:
        r = u.leer()
    except ValueError:
        r = None
    u.rewind()
    if r is None or len(r) < 4:
        return None
    return struct.unpack("<i", r[:4])[0]


def _long_date(e, idat8, previo):
    """LONG_DATE: fecha de 8 cifras (año de 2) a 10 cifras con el siglo ISTRT_CENT (si el año no
    cabe en 2 cifras, IDAT conserva el valor anterior)."""
    if idat8 // 1000000 <= 99:
        return e.ISTRT_CENT * 100000000 + idat8
    return previo


def reanudar_texto(e, m, unidad, nombre, col, irsdate, cod_multyr, ajustar_hora=False):
    """Posiciona un fichero formateado de resultados (MAXIFILE, POSTFILE PLOT, MAXDAILY...) tras su
    último registro con fecha <= IRSDATE. `col` = (inicio, fin) de la fecha I8 en el registro (1..n).
    Devuelve False si hay error de lectura (919 del original)."""
    try:
        with open(nombre, "rb") as fh:
            datos = fh.read()
    except OSError:
        return False
    pos, n = 0, len(datos)
    corte = n
    idat = 0
    while pos < n:
        fin = datos.find(b"\n", pos)
        sig = n if fin < 0 else fin + 1
        reg = datos[pos:sig].rstrip(b"\n").rstrip(b"\r").decode("latin-1")
        if not reg.startswith("*"):
            campo = reg[col[0] - 1:col[1]].replace(" ", "")
            try:
                idat8 = int(campo) if campo else 0
            except ValueError:
                # error de lectura (919): el fichero queda tras el registro leído
                e.abrir_reanudada(unidad, nombre, sig)
                return False
            if ajustar_hora:
                idat8 = 100 * (idat8 // 100)
            idat = _long_date(e, idat8, idat)
            if idat > irsdate:
                if e.MULTYR:
                    e.DUMMY = fwrite("(I8.8)", idat8)[0]
                    e.errhdl(e.PATH, m, "E", cod_multyr, e.DUMMY)
                corte = pos
                break
        pos = sig
    e.abrir_reanudada(unidad, nombre, corte)
    return True


def reanudar_bin(e, m, unidad, nombre, irsdate):
    """POSTFILE sin formato: igual que `reanudar_texto` leyendo la fecha (primer entero) de cada
    registro."""
    try:
        with open(nombre, "rb") as fh:
            datos = fh.read()
    except OSError:
        return False
    pos, n = 0, len(datos)
    corte = n
    idat = 0
    while pos + 4 <= n:
        lon = int.from_bytes(datos[pos:pos + 4], "little", signed=True)
        if lon < 4 or pos + 8 + lon > n:
            e.abrir_reanudada(unidad, nombre, pos, binario=True)
            return False
        idat8 = struct.unpack("<i", datos[pos + 4:pos + 8])[0]
        idat = _long_date(e, idat8, idat)
        if idat > irsdate:
            if e.MULTYR:
                e.DUMMY = fwrite("(I8.8)", idat8)[0]
                e.errhdl(e.PATH, m, "E", "593", e.DUMMY)
            corte = pos
            break
        pos += 8 + lon
    e.abrir_reanudada(unidad, nombre, corte, binario=True)
    return True


def existe(nombre):
    return os.path.isfile(nombre)
