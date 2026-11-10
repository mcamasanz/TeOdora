# -*- coding: utf-8 -*-
"""Traducción de AERMAP v24142 (US EPA, dominio público): lector de GeoTIFF
(sub_read_tifftags.f y la parte de lectura de datos de sub_initer_ned.f).

Se lee el TIFF a mano, como el original, y NO con GDAL/rasterio: los avisos y errores que
AERMAP escribe dependen de qué etiquetas trae el fichero y de cómo las interpreta. Se
conservan sus peculiaridades:
  · las etiquetas de tipo FLOAT (11) se leen como ENTEROS de 4 bytes convertidos a doble;
  · un tipo de dato desconocido (incluido UNDEFINED = 7) marca la etiqueta como problemática
    y activa el aviso de lectura (W480);
  · de una GeoKey con el valor «en línea» solo se lee el primer valor;
  · los datos enteros SIN signo se leen en la práctica como CON signo (la suma de 2**n se
    hace en un entero más ancho y al guardarla en la variable corta vuelve a «dar la vuelta»);
  · los valores menores que -9999 se fijan a -9999 (dato ausente)."""
import struct

import numpy as np

TIPO_LONG = {1: 1, 2: 1, 3: 2, 4: 4, 5: 8, 6: 1, 7: 1, 8: 2, 9: 4, 10: 8, 11: 4, 12: 8}


class Etiqueta:
    __slots__ = ("id", "fldtype", "cnt", "offset", "prob", "intval", "dblval", "chrval",
                 "ratval")

    def __init__(self):
        self.id = self.fldtype = self.cnt = self.offset = 0
        self.prob = False
        self.intval, self.dblval, self.chrval, self.ratval = [], [], [], []


class LecturaTiff:
    """Resultado de read_tifftags."""

    def __init__(self):
        self.ttags, self.gkeys = [], []
        self.swapbytes = False
        self.tifferr = self.tiffwrn = self.allerr = False


class _Fichero:
    """Acceso por bytes (registros de 1 byte del original). Lanza EOFError si se lee más
    allá del final, como el ERR=9010 del Fortran."""

    def __init__(self, ruta):
        with open(ruta, "rb") as f:
            self.b = f.read()

    def bytes(self, pos, n):
        if pos < 0 or pos + n > len(self.b):
            raise EOFError
        return self.b[pos:pos + n]


def leer_etiquetas(e, ruta):
    """read_tifftags. `e` es el Estado (para ERRHDL)."""
    r = LecturaTiff()
    try:
        f = _Fichero(ruta)
    except OSError:
        e.errhdl("RN", "TIFFTAGS", "E", "500", "TIF File")
        r.tifferr = True
        return r
    try:
        cab = f.bytes(0, 8)
        if cab[:2] == b"II":
            fin = "<"
        elif cab[:2] == b"MM":
            fin = ">"
        else:
            r.tifferr = True
            return r
        r.swapbytes = fin == ">"            # CPU little-endian
        tiffid = struct.unpack(fin + "h", cab[2:4])[0]
        ifd = struct.unpack(fin + "i", cab[4:8])[0]
        if ifd < 0:
            ifd += 2 ** 32
        if tiffid != 42:
            r.tifferr = True
            return r
        n = struct.unpack(fin + "h", f.bytes(ifd, 2))[0]
        if n < 0:
            n += 65536
        thisrec = ifd + 2
        geodir = geodbls = geoasc = False
        geodirref = geodblsref = geoascref = 0
        for _ in range(n):
            t = Etiqueta()
            ent = f.bytes(thisrec, 12)
            t.id = struct.unpack(fin + "h", ent[0:2])[0]
            t.fldtype = struct.unpack(fin + "h", ent[2:4])[0]
            t.cnt = struct.unpack(fin + "i", ent[4:8])[0]
            if t.id < 0:
                t.id += 65536
            if t.cnt < 0:
                t.cnt += 2 ** 32
            r.ttags.append(t)
            if t.fldtype not in TIPO_LONG or t.fldtype == 7:
                r.tiffwrn = True
                t.prob = True
                thisrec += 12
                continue
            if t.cnt * TIPO_LONG[t.fldtype] <= 4:
                temprec = thisrec + 8
            else:
                off = struct.unpack(fin + "i", ent[8:12])[0]
                if off < 0:
                    off += 2 ** 32
                t.offset = off
                temprec = off
            ft = t.fldtype
            for _j in range(t.cnt):
                if ft in (1, 6):
                    v = struct.unpack("b", f.bytes(temprec, 1))[0]
                    if ft == 1 and v < 0:
                        v += 256
                    t.intval.append(v)
                    temprec += 1
                elif ft == 2:
                    c = f.bytes(temprec, 1).decode("latin-1")
                    t.chrval.append("|" if c == "\0" else (" " if c == "\n" else c))
                    temprec += 1
                elif ft in (3, 8):
                    v = struct.unpack(fin + "h", f.bytes(temprec, 2))[0]
                    if ft == 3 and v < 0:
                        v += 65536
                    t.intval.append(v)
                    temprec += 2
                elif ft in (4, 9):
                    v = struct.unpack(fin + "i", f.bytes(temprec, 4))[0]
                    if ft == 4 and v < 0:
                        v += 2 ** 32
                    t.intval.append(v)
                    temprec += 4
                elif ft in (5, 10):
                    a, b = struct.unpack(fin + "ii", f.bytes(temprec, 8))
                    if ft == 5:
                        a += 2 ** 32 if a < 0 else 0
                        b += 2 ** 32 if b < 0 else 0
                    t.ratval.append((a, b))
                    temprec += 8
                elif ft == 11:
                    # (sic) el original convierte el ENTERO de 4 bytes, no el REAL
                    t.dblval.append(float(struct.unpack(fin + "i", f.bytes(temprec, 4))[0]))
                    temprec += 4
                elif ft == 12:
                    t.dblval.append(struct.unpack(fin + "d", f.bytes(temprec, 8))[0])
                    temprec += 8
                if t.id == 34735:
                    geodir, geodirref = True, t.offset
                elif t.id == 34736:
                    geodbls, geodblsref = True, t.offset
                elif t.id == 34737:
                    geoasc, geoascref = True, t.offset
            thisrec += 12
        if not geodir:
            r.tifferr = True
            return r
        cab = f.bytes(geodirref, 8)
        ngk = struct.unpack(fin + "h", cab[6:8])[0]
        if ngk < 0:
            ngk += 65536
        thisrec = geodirref + 8
        for _ in range(ngk):
            g = Etiqueta()
            ent = f.bytes(thisrec, 6)
            g.id, g.fldtype, g.cnt = struct.unpack(fin + "hhh", ent)
            g.id += 65536 if g.id < 0 else 0
            g.fldtype += 65536 if g.fldtype < 0 else 0
            g.cnt += 65536 if g.cnt < 0 else 0
            r.gkeys.append(g)
            if g.fldtype not in (0, 34736, 34737):
                r.tiffwrn = True
                g.prob = True
                thisrec += 8
                continue
            if g.fldtype == 0:
                temprec = thisrec + 6
            else:
                off = struct.unpack(fin + "h", f.bytes(thisrec + 6, 2))[0]
                off += 65536 if off < 0 else 0
                g.offset = off
                if g.fldtype == 34736:
                    if not geodbls:
                        r.tifferr = True
                        return r
                    temprec = geodblsref + off * 8
                else:
                    if not geoasc:
                        r.tifferr = True
                        return r
                    temprec = geoascref + off
            for _j in range(g.cnt):
                if g.fldtype == 0:
                    v = struct.unpack(fin + "h", f.bytes(temprec, 2))[0]
                    g.intval.append(v + 65536 if v < 0 else v)
                    if g.cnt != 1:
                        r.tiffwrn = True
                    break                       # «go to 992»: solo el primer valor
                elif g.fldtype == 34736:
                    g.dblval.append(struct.unpack(fin + "d", f.bytes(temprec, 8))[0])
                    temprec += 8
                else:
                    c = f.bytes(temprec, 1).decode("latin-1")
                    g.chrval.append("|" if c == "\0" else (" " if c == "\n" else c))
                    temprec += 1
            thisrec += 8
    except EOFError:
        e.errhdl("RN", "TIFFTAGS", "E", "510", "TIF File")
        r.tifferr = True
    return r


def leer_elevaciones(ruta, d):
    """Lectura de los datos de INITER_NED. `d` describe el fichero (atributos de NEDCHK).
    Devuelve z[fila desde el SUR, columna] (float64) o lanza EOFError."""
    ncols, nrows, bps = d.ncols, d.nrows, d.bps
    fin = ">" if d.swap else "<"
    if bps == 1:
        tipo = np.dtype("i1")
    elif bps == 2:
        tipo = np.dtype(fin + "i2")
    elif bps == 4:
        tipo = np.dtype(fin + ("f4" if d.sampleformat == 3 else "i4"))
    else:
        tipo = np.dtype(fin + "f8")
    raw = np.memmap(ruta, dtype=np.uint8, mode="r")
    z = np.zeros((nrows, ncols), dtype=np.float64)

    def bloque(pos, n):
        if pos < 0 or pos + n * bps > raw.size:
            raise EOFError
        return np.frombuffer(raw[pos:pos + n * bps].tobytes(), dtype=tipo)

    if d.tifftype == "strip":
        fila = 0                                   # fila desde el NORTE (0 = arriba)
        for off in d.dataos:
            nf = min(d.rowsperstrip, nrows - fila)
            if nf <= 0:
                break
            v = bloque(off, nf * ncols).reshape(nf, ncols)
            z[nrows - fila - nf:nrows - fila, :] = v[::-1, :]
            fila += d.rowsperstrip
    else:
        tw, tl = d.tilewid, d.tilelen
        across = (ncols + tw - 1) // tw
        for j, off in enumerate(d.dataos):
            trow, tcol = j // across, j % across
            r0, c0 = trow * tl, tcol * tw
            nf = min(tl, nrows - r0)
            nc = min(tw, ncols - c0)
            if nf <= 0 or nc <= 0:
                continue
            # el original lee fila a fila dentro de la tesela; se lee la tesela entera
            # (hasta la última fila útil) y se recorta
            v = bloque(off, (nf - 1) * tw + nc)
            v = np.concatenate([v, np.zeros(nf * tw - v.size, dtype=tipo)]).reshape(nf, tw)
            z[nrows - r0 - nf:nrows - r0, c0:c0 + nc] = v[::-1, :nc]
    return np.fmax(-9999.0, z)
