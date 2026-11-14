# -*- coding: utf-8 -*-
"""Lectura y escritura del fichero de salida CALMET.DAT (versión de dataset 2.0).

Formato: fichero Fortran secuencial sin formato (cada registro va entre dos marcas de 4 bytes con
su longitud), little-endian, reales de 4 bytes. Fuentes:
  - [UG] CALMET User's Guide (2000), sec. 4.3.11.1, tablas 4-65 y 4-66: registros de datos
    «CLAB, NDATHR, campo» (una sola marca de fecha) y cabecera con IDUM tras cada etiqueta.
  - [V6] CALPUFF Version 6 User Instructions (2011), sec. 8.11.1, tabla 8-26: registro de
    declaración (DATASET, DATAVER, DATAMOD), número de comentarios y comentarios, y registro de
    control con proyección y datum.
  - Observación de los CALMET.DAT que escribe calmet.exe 5.8.5 (caja negra): la versión 2.0
    combina la cabecera de [V6] SIN los segundos (IBSEC/IESEC) con los registros de datos de [UG];
    sin estaciones de superficie, TEMPK, RHO, QSW, IRH e IPCODE son campos de malla (NX·NY).
"""
import struct
from dataclasses import dataclass, field

import numpy as np

CAMPOS_2D = ("IPGT", "USTAR", "ZI", "EL", "WSTAR", "RMM", "TEMPK", "RHO", "QSW", "IRH", "IPCODE")
ENTEROS_2D = ("IPGT", "IRH", "IPCODE")


@dataclass
class Cabecera:
    dataset: str = "CALMET.DAT"
    dataver: str = "2.0"
    datamod: str = "No-Obs file structure with embedded control file"
    comentarios: list = field(default_factory=list)
    ibyr: int = 0
    ibmo: int = 0
    ibdy: int = 0
    ibhr: int = 0
    ibtz: int = 0
    irlg: int = 0
    irtype: int = 1
    nx: int = 0
    ny: int = 0
    nz: int = 0
    dgrid: float = 0.0          # m
    xorig: float = 0.0          # m
    yorig: float = 0.0          # m
    iwfcod: int = 1
    nssta: int = 0
    nusta: int = 0
    npsta: int = 0
    nowsta: int = 0
    nlu: int = 0
    iwat1: int = 0
    iwat2: int = 0
    lcalgrd: bool = True
    pmap: str = "UTM"
    datum: str = "WGS-84"
    daten: str = "02-21-2003"
    feast: float = 0.0
    fnorth: float = 0.0
    utmhem: str = "N"
    iutmzn: int = 0
    rnlat0: float = 0.0
    relon0: float = 0.0
    xlat1: float = 0.0
    xlat2: float = 0.0
    zface: np.ndarray = None    # (nz+1,)
    z0: np.ndarray = None       # (ny, nx)
    ilandu: np.ndarray = None
    elev: np.ndarray = None
    xlai: np.ndarray = None
    estaciones: dict = field(default_factory=dict)   # 'XSSTA', ... si las hay
    nears: np.ndarray = None


@dataclass
class Hora:
    ndathr: int
    u: np.ndarray               # (nz, ny, nx)
    v: np.ndarray
    w: np.ndarray = None        # (nz, ny, nx): velocidad en la cara superior de cada capa
    t: np.ndarray = None        # (nz, ny, nx)
    d2: dict = field(default_factory=dict)            # CAMPOS_2D -> (ny, nx)


def _c(s, n):
    return s.encode("latin-1")[:n].ljust(n)


def _s(b):
    return b.decode("latin-1").rstrip()


class _Escritor:
    def __init__(self, f):
        self.f = f

    def reg(self, datos):
        n = struct.pack("<i", len(datos))
        self.f.write(n + datos + n)


def _malla(a, tipo):
    """(ny, nx) -> bytes en el orden Fortran ((a(i,j), i=1,nx), j=1,ny), fila 1 = sur."""
    return np.ascontiguousarray(a, dtype=tipo).tobytes()


def escribir(ruta, cab, horas):
    """Escribe un CALMET.DAT 2.0. `horas` es un iterable de Hora."""
    nxy = cab.nx * cab.ny
    with open(ruta, "wb") as f:
        e = _Escritor(f)
        e.reg(_c(cab.dataset, 16) + _c(cab.dataver, 16) + _c(cab.datamod, 64))
        e.reg(struct.pack("<i", len(cab.comentarios)))
        for c in cab.comentarios:
            e.reg(_c(c, 132))
        e.reg(struct.pack("<10i", cab.ibyr, cab.ibmo, cab.ibdy, cab.ibhr, cab.ibtz, cab.irlg,
                          cab.irtype, cab.nx, cab.ny, cab.nz)
              + struct.pack("<3f", cab.dgrid, cab.xorig, cab.yorig)
              + struct.pack("<9i", cab.iwfcod, cab.nssta, cab.nusta, cab.npsta, cab.nowsta,
                            cab.nlu, cab.iwat1, cab.iwat2, 1 if cab.lcalgrd else 0)
              + _c(cab.pmap, 8) + _c(cab.datum, 8) + _c(cab.daten, 12)
              + struct.pack("<2f", cab.feast, cab.fnorth) + _c(cab.utmhem, 4)
              + struct.pack("<i4f", cab.iutmzn, cab.rnlat0, cab.relon0, cab.xlat1, cab.xlat2))
        e.reg(_c("ZFACE", 8) + struct.pack("<i", 0) + np.asarray(cab.zface, "<f4").tobytes())
        for par in (("XSSTA", "YSSTA"), ("XUSTA", "YUSTA"), ("XPSTA", "YPSTA")):
            for k in par:
                if k in cab.estaciones:
                    e.reg(_c(k, 8) + struct.pack("<i", 0)
                          + np.asarray(cab.estaciones[k], "<f4").tobytes())
        e.reg(_c("Z0", 8) + struct.pack("<i", 0) + _malla(cab.z0, "<f4"))
        e.reg(_c("ILANDU", 8) + struct.pack("<i", 0) + _malla(cab.ilandu, "<i4"))
        e.reg(_c("ELEV", 8) + struct.pack("<i", 0) + _malla(cab.elev, "<f4"))
        e.reg(_c("XLAI", 8) + struct.pack("<i", 0) + _malla(cab.xlai, "<f4"))
        if cab.nssta >= 1 and cab.nears is not None:
            e.reg(_c("NEARS", 8) + struct.pack("<i", 0) + _malla(cab.nears, "<i4"))
        for h in horas:
            fh = struct.pack("<i", h.ndathr)
            for k in range(cab.nz):
                e.reg(_c("U-LEV%3d" % (k + 1), 8) + fh + _malla(h.u[k], "<f4"))
                e.reg(_c("V-LEV%3d" % (k + 1), 8) + fh + _malla(h.v[k], "<f4"))
                if cab.lcalgrd:
                    e.reg(_c("WFACE%3d" % (k + 1), 8) + fh + _malla(h.w[k], "<f4"))
            if cab.lcalgrd and cab.irtype == 1:
                for k in range(cab.nz):
                    e.reg(_c("T-LEV%3d" % (k + 1), 8) + fh + _malla(h.t[k], "<f4"))
            if cab.irtype == 1:
                for nombre in CAMPOS_2D:
                    tipo = "<i4" if nombre in ENTEROS_2D else "<f4"
                    e.reg(_c(nombre, 8) + fh + _malla(h.d2[nombre], tipo))
    return nxy


def _registros(ruta):
    with open(ruta, "rb") as f:
        b = f.read()
    p = 0
    while p < len(b):
        n = struct.unpack_from("<i", b, p)[0]
        yield b[p + 4:p + 4 + n]
        p += 8 + n


def leer(ruta, horas=True):
    """Lee un CALMET.DAT 2.0 -> (Cabecera, [Hora, ...]). Con horas=False solo la cabecera."""
    it = _registros(ruta)
    cab = Cabecera()
    r = next(it)
    cab.dataset, cab.dataver, cab.datamod = _s(r[:16]), _s(r[16:32]), _s(r[32:96])
    ncom = struct.unpack("<i", next(it))[0]
    cab.comentarios = [_s(next(it)) for _ in range(ncom)]
    r = next(it)
    (cab.ibyr, cab.ibmo, cab.ibdy, cab.ibhr, cab.ibtz, cab.irlg, cab.irtype, cab.nx, cab.ny,
     cab.nz) = struct.unpack_from("<10i", r, 0)
    cab.dgrid, cab.xorig, cab.yorig = struct.unpack_from("<3f", r, 40)
    (cab.iwfcod, cab.nssta, cab.nusta, cab.npsta, cab.nowsta, cab.nlu, cab.iwat1, cab.iwat2,
     lc) = struct.unpack_from("<9i", r, 52)
    cab.lcalgrd = lc != 0
    cab.pmap, cab.datum, cab.daten = _s(r[88:96]), _s(r[96:104]), _s(r[104:116])
    cab.feast, cab.fnorth = struct.unpack_from("<2f", r, 116)
    cab.utmhem = _s(r[124:128])
    cab.iutmzn, cab.rnlat0, cab.relon0, cab.xlat1, cab.xlat2 = struct.unpack_from("<i4f", r, 128)
    nx, ny, nz = cab.nx, cab.ny, cab.nz

    def campo(r, tipo):
        return np.frombuffer(r, tipo, offset=12).reshape(ny, nx).copy()

    salida = []
    hora = None
    for r in it:
        lab = _s(r[:8])
        if lab == "ZFACE":
            cab.zface = np.frombuffer(r, "<f4", offset=12).copy()
        elif lab in ("XSSTA", "YSSTA", "XUSTA", "YUSTA", "XPSTA", "YPSTA"):
            cab.estaciones[lab] = np.frombuffer(r, "<f4", offset=12).copy()
        elif lab == "Z0":
            cab.z0 = campo(r, "<f4")
        elif lab == "ILANDU":
            cab.ilandu = campo(r, "<i4")
        elif lab == "ELEV":
            cab.elev = campo(r, "<f4")
        elif lab == "XLAI":
            cab.xlai = campo(r, "<f4")
        elif lab == "NEARS":
            cab.nears = campo(r, "<i4")
        else:
            if not horas:
                break
            nd = struct.unpack_from("<i", r, 8)[0]
            if hora is None or hora.ndathr != nd:
                hora = Hora(nd, np.zeros((nz, ny, nx), "f4"), np.zeros((nz, ny, nx), "f4"))
                if cab.lcalgrd:
                    hora.w = np.zeros((nz, ny, nx), "f4")
                    hora.t = np.zeros((nz, ny, nx), "f4")
                salida.append(hora)
            pref = lab[:5]
            if pref in ("U-LEV", "V-LEV", "WFACE", "T-LEV"):
                k = int(lab[5:]) - 1
                destino = {"U-LEV": hora.u, "V-LEV": hora.v, "WFACE": hora.w, "T-LEV": hora.t}[pref]
                destino[k] = campo(r, "<f4")
            else:
                hora.d2[lab] = campo(r, "<i4" if lab in ENTEROS_2D else "<f4")
    return cab, salida
