# -*- coding: utf-8 -*-
"""Lectura y escritura del fichero de concentraciones CONC.DAT (versión de dataset 2.1).

Formato: fichero Fortran secuencial sin formato (cada registro entre dos marcas de 4 bytes con su
longitud), little-endian, reales de 4 bytes. Fuentes:
  - [V6] CALPUFF Version 6 User Instructions (2011), sec. 9.15.3, tabla 9-52: registros de
    cabecera (declaración, comentarios, registro general, título, especies, receptores y nombres
    de fuentes) y registros de datos por periodo (fechas de inicio y fin, fuente, especie).
  - Observación de los CONC.DAT de calpuff.exe 5.8.5 (caja negra): con LCOMPR=T cada campo va
    precedido de un registro con el número de palabras; dentro del campo un valor negativo -n
    sustituye a n ceros seguidos, escrito como -(n + 0,0001) en real de 4 bytes.
"""
import struct
from dataclasses import dataclass, field

import numpy as np

TIPOS_FUENTE = ("NPT1", "NPT2", "NAR1", "NAR2", "NLN1", "NLN2", "NVL1", "NVL2")


def _c(s, n):
    return str(s).encode("latin-1")[:n].ljust(n)


def _s(b):
    return b.decode("latin-1").rstrip()


def _registros(b):
    p = 0
    while p < len(b):
        n = struct.unpack_from("<i", b, p)[0]
        yield b[p + 4:p + 4 + n]
        p += 8 + n


@dataclass
class Cabecera:
    dataset: str = "CONC.DAT"
    dataver: str = "2.1"
    datamod: str = "No-Obs file structure with embedded control file"
    comentarios: list = field(default_factory=list)
    modelo: str = "CALPUFF"
    version: str = ""
    nivel: str = ""
    ibyr: int = 0
    ibjul: int = 0
    ibhr: int = 0
    ibsec: int = 0
    xbtz: float = 0.0
    irlg: int = 0
    iavg: int = 1
    nsecdt: int = 3600
    nx: int = 0
    ny: int = 0
    dxkm: float = 0.0
    dykm: float = 0.0
    ione: int = 1
    xorigkm: float = 0.0
    yorigkm: float = 0.0
    nssta: int = 0
    comp: tuple = (1, 1, 1, 1)          # IBCOMP, IECOMP, JBCOMP, JECOMP
    samp: tuple = (1, 1, 1, 1)          # IBSAMP, JBSAMP, IESAMP, JESAMP
    meshdn: int = 1
    nfuentes: dict = field(default_factory=lambda: dict.fromkeys(TIPOS_FUENTE, 0))
    msource: int = 0
    nctrec: int = 0
    lsamp: bool = False
    lcompr: bool = True
    i2dmet: int = 1
    iutmzn: int = 0
    feast: float = 0.0
    fnorth: float = 0.0
    rnlat0: float = 0.0
    relon0: float = 0.0
    xlat1: float = 0.0
    xlat2: float = 0.0
    pmap: str = "UTM"
    utmhem: str = "N"
    datum: str = "WGS-84"
    daten: str = "02-21-2003"
    clat: tuple = ("", "", "", "")
    titulo: list = field(default_factory=lambda: ["", "", ""])
    especies: list = field(default_factory=list)     # CSOUT, C*15 (nombre + nivel)
    xrec: np.ndarray = None                          # km
    yrec: np.ndarray = None
    zrec: np.ndarray = None                          # m
    nombres: dict = field(default_factory=dict)      # tipo -> (istype, [nombres])
    fuente_total: tuple = (0, 1, "TOTAL", 0.0, 0.0)  # registro de fuente de los datos


@dataclass
class Periodo:
    inicio: tuple       # (año, día juliano, hora, segundo)
    fin: tuple
    campos: dict        # especie (C*15) -> array (nrec discretos [+ malla])


def _comprimir(a):
    out = []
    n0 = 0
    for v in np.asarray(a, "<f4"):
        if v == 0.0:
            n0 += 1
            continue
        if n0:
            out.append(-(n0 + 1e-4))
            n0 = 0
        out.append(float(v))
    if n0:
        out.append(-(n0 + 1e-4))
    return np.asarray(out, "<f4")


def _descomprimir(c, n):
    out = np.zeros(n, "<f4")
    p = 0
    for v in c:
        if v < 0:
            p += int(round(-v))
        else:
            out[p] = v
            p += 1
    return out


def leer(ruta):
    """Lee un CONC.DAT 2.1 -> (Cabecera, [Periodo, ...])."""
    b = open(ruta, "rb").read()
    it = _registros(b)
    cab = Cabecera()
    r = next(it)
    cab.dataset, cab.dataver, cab.datamod = _s(r[:16]), _s(r[16:32]), _s(r[32:96])
    ncom = struct.unpack("<i", next(it))[0]
    cab.comentarios = [_s(next(it)) for _ in range(ncom)]
    r = next(it)
    cab.modelo, cab.version, cab.nivel = _s(r[0:12]), _s(r[12:24]), _s(r[24:36])
    cab.ibyr, cab.ibjul, cab.ibhr, cab.ibsec = struct.unpack_from("<4i", r, 36)
    cab.xbtz, = struct.unpack_from("<f", r, 52)
    cab.irlg, cab.iavg, cab.nsecdt, cab.nx, cab.ny = struct.unpack_from("<5i", r, 56)
    cab.dxkm, cab.dykm = struct.unpack_from("<2f", r, 76)
    cab.ione, = struct.unpack_from("<i", r, 84)
    cab.xorigkm, cab.yorigkm = struct.unpack_from("<2f", r, 88)
    v = struct.unpack_from("<21i", r, 96)
    cab.nssta = v[0]
    cab.comp = v[1:5]
    cab.samp = v[5:9]
    cab.meshdn = v[9]
    cab.nfuentes = dict(zip(TIPOS_FUENTE, v[10:18]))
    cab.msource, nrec, cab.nctrec = v[18], v[19], v[20]
    lsamp, nspout, lcompr, cab.i2dmet, cab.iutmzn = struct.unpack_from("<5i", r, 180)
    cab.lsamp, cab.lcompr = lsamp != 0, lcompr != 0
    cab.feast, cab.fnorth, cab.rnlat0, cab.relon0, cab.xlat1, cab.xlat2 = struct.unpack_from("<6f", r, 200)
    cab.pmap, cab.utmhem, cab.datum, cab.daten = _s(r[224:232]), _s(r[232:236]), _s(r[236:244]), _s(r[244:256])
    cab.clat = tuple(_s(r[256 + 16 * k:272 + 16 * k]) for k in range(4))
    r = next(it)
    cab.titulo = [_s(r[80 * k:80 * (k + 1)]) for k in range(3)]
    r = next(it)
    cab.especies = [r[15 * k:15 * (k + 1)].decode("latin-1") for k in range(nspout)]
    if nrec > 0:
        a = np.frombuffer(next(it), "<f4")
        cab.xrec, cab.yrec, cab.zrec = a[:nrec].copy(), a[nrec:2 * nrec].copy(), a[2 * nrec:].copy()
    if cab.nctrec > 0:
        next(it)
    for t in TIPOS_FUENTE:
        if cab.nfuentes[t] > 0:
            r = next(it)
            istype = struct.unpack_from("<i", r, 0)[0]
            cab.nombres[t] = (istype, [_s(r[4 + 16 * k:20 + 16 * k]) for k in range(cab.nfuentes[t])])
    nmalla = 0
    if cab.lsamp:
        ib, jb, ie, je = cab.samp
        nmalla = ((ie - ib) * cab.meshdn + 1) * ((je - jb) * cab.meshdn + 1)
    ntot = nmalla + nrec + cab.nctrec
    periodos = []
    for r in it:
        f = struct.unpack("<8i", r)
        r = next(it)
        istype, isnum = struct.unpack_from("<2i", r, 0)
        cab.fuente_total = (istype, isnum, _s(r[8:24])) + struct.unpack_from("<2f", r, 24)
        campos = {}
        for _ in cab.especies:
            # con malla de muestreo (LSAMP) cada especie lleva dos campos: la malla y los discretos
            # (caja negra: dos parejas de registros)
            partes = []
            for nv in ((nmalla, nrec + cab.nctrec) if cab.lsamp else (ntot,)):
                if cab.lcompr:
                    next(it)
                    r = next(it)
                    esp = r[:15].decode("latin-1")
                    partes.append(_descomprimir(np.frombuffer(r, "<f4", offset=15), nv))
                else:
                    r = next(it)
                    esp = r[:15].decode("latin-1")
                    partes.append(np.frombuffer(r, "<f4", offset=15).copy())
            campos[esp] = np.concatenate(partes)
        periodos.append(Periodo(f[:4], f[4:], campos))
    return cab, periodos


def escribir(ruta, cab, periodos):
    """Escribe un CONC.DAT 2.1 con la estructura de [V6] tabla 9-52."""
    nrec = 0 if cab.xrec is None else len(cab.xrec)
    with open(ruta, "wb") as f:
        def reg(d):
            f.write(struct.pack("<i", len(d)) + d + struct.pack("<i", len(d)))
        reg(_c(cab.dataset, 16) + _c(cab.dataver, 16) + _c(cab.datamod, 64))
        reg(struct.pack("<i", len(cab.comentarios)))
        for c in cab.comentarios:
            reg(_c(c, 132))
        nf = [cab.nfuentes.get(t, 0) for t in TIPOS_FUENTE]
        reg(_c(cab.modelo, 12) + _c(cab.version, 12) + _c(cab.nivel, 12)
            + struct.pack("<4i", cab.ibyr, cab.ibjul, cab.ibhr, cab.ibsec)
            + struct.pack("<f", cab.xbtz)
            + struct.pack("<5i", cab.irlg, cab.iavg, cab.nsecdt, cab.nx, cab.ny)
            + struct.pack("<2f", cab.dxkm, cab.dykm) + struct.pack("<i", cab.ione)
            + struct.pack("<2f", cab.xorigkm, cab.yorigkm)
            + struct.pack("<21i", cab.nssta, *cab.comp, *cab.samp, cab.meshdn, *nf,
                          cab.msource, nrec, cab.nctrec)
            + struct.pack("<5i", 1 if cab.lsamp else 0, len(cab.especies), 1 if cab.lcompr else 0,
                          cab.i2dmet, cab.iutmzn)
            + struct.pack("<6f", cab.feast, cab.fnorth, cab.rnlat0, cab.relon0, cab.xlat1, cab.xlat2)
            + _c(cab.pmap, 8) + _c(cab.utmhem, 4) + _c(cab.datum, 8) + _c(cab.daten, 12)
            + b"".join(_c(x, 16) for x in cab.clat))
        reg(b"".join(_c(x, 80) for x in cab.titulo))
        reg(b"".join(_c(x, 15) for x in cab.especies))
        if nrec:
            reg(np.concatenate([cab.xrec, cab.yrec, cab.zrec]).astype("<f4").tobytes())
        for t in TIPOS_FUENTE:
            if t in cab.nombres and cab.nfuentes.get(t, 0) > 0:
                istype, nombres = cab.nombres[t]
                reg(struct.pack("<i", istype) + b"".join(_c(n, 16) for n in nombres))
        ft = cab.fuente_total
        for p in periodos:
            reg(struct.pack("<8i", *p.inicio, *p.fin))
            reg(struct.pack("<2i", ft[0], ft[1]) + _c(ft[2], 16) + struct.pack("<2f", ft[3], ft[4]))
            for esp in cab.especies:
                vals = np.asarray(p.campos[esp], "<f4")
                trozos = (vals[:len(vals) - nrec], vals[len(vals) - nrec:]) if cab.lsamp else (vals,)
                for v in trozos:
                    if cab.lcompr:
                        c = _comprimir(v)
                        reg(struct.pack("<i", len(c)))
                        reg(_c(esp, 15) + c.tobytes())
                    else:
                        reg(_c(esp, 15) + v.tobytes())
