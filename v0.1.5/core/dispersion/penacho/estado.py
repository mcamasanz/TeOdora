# -*- coding: utf-8 -*-
"""Traducción de AERMOD 26135 (US EPA, dominio público): estado global y servicios comunes.

El original guarda casi todo en el módulo MAIN1 (modules.f) con variables globales que las
subrutinas leen y modifican. La traducción conserva ese diseño: un objeto `Estado` con los MISMOS
nombres (en mayúsculas) creado a partir de las declaraciones de modules.f (`tablas.DECL`) y de sus
valores iniciales (`tablas.DATA`). Así cada efecto lateral del Fortran tiene su equivalente exacto.

Representación:
  · INTEGER → int; DOUBLE PRECISION → float; REAL → float redondeado a simple donde importa.
  · CHARACTER → str en forma canónica (truncada a su longitud y sin blancos finales, ver
    `fortran.fc`).
  · Vectores y matrices numéricos y lógicos → numpy con UNA POSICIÓN EXTRA por dimensión, para
    usar directamente los índices 1..N del Fortran; vectores CHARACTER → listas (posición 0 sin
    usar); matrices CHARACTER → numpy de objetos.
  · Las variables ALLOCATABLE valen None hasta que ALLSETUP/ALLRESULT las crean (`alloc`).

También están aquí los servicios de aermod.f que usa todo el programa: ERRHDL, TERRST, SUMTBL,
MSGWRT, HEADER, DATIME, JULIAN y GREGOR, y la gestión de unidades de E/S."""
import datetime
import os
import sys

import numpy as np

from . import tablas as T
from .formato import fc, fwrite, fx, lw, stodbl, stonum, nint

P = T.PARAM
ISTRG = P["ISTRG"]
ILEN_FLD = P["ILEN_FLD"]
IFMAX = P["IFMAX"]

_ERR_IDX = {}
for _c, _t in T.ERRORES:
    _ERR_IDX.setdefault(_c, _t)


class Parada(Exception):
    """STOP del original: el programa termina sin pasar por el final normal."""


class NoTraducido(Exception):
    """Opción del original fuera del alcance de la traducción."""


def _dim(d):
    d = d.strip()
    if ":" in d:
        lo, hi = d.split(":")
        assert _dim(lo) in (0, 1), d
        return _dim(hi)
    if d.isdigit():
        return int(d)
    return int(eval(d.upper(), {"__builtins__": {}}, dict(P)))


def crear(tipo, dims, lon=1, val=None):
    """Matriz de un tipo Fortran con índices 1..dims (posición 0 sin usar en cada dimensión)."""
    forma = tuple(int(n) + 1 for n in dims)
    if tipo == "CHARACTER":
        v = "" if val is None else val
        if len(forma) == 1:
            return [v] * forma[0]
        a = np.empty(forma, dtype=object)
        a.fill(v)
        return a
    if tipo == "LOGICAL":
        return np.full(forma, bool(val) if val is not None else False, dtype=bool)
    if tipo == "INTEGER":
        return np.full(forma, 0 if val is None else val, dtype=np.int64)
    if tipo == "REAL":
        return np.full(forma, 0.0 if val is None else val, dtype=np.float32)
    return np.full(forma, 0.0 if val is None else val, dtype=np.float64)


class Salida:
    """Fichero formateado de salida (Intel en Windows: registros terminados en CRLF) escrito
    según se produce, para no acumular ficheros grandes en memoria."""

    def __init__(self, nombre):
        self.nombre = nombre
        self.fh = open(nombre, "w", encoding="latin-1", newline="", errors="replace")

    def w(self, lineas):
        if isinstance(lineas, str):
            self.fh.write(lineas + "\r\n")
        else:
            self.fh.write("".join(l + "\r\n" for l in lineas))

    def cerrar(self):
        if self.fh is not None:
            self.fh.close()
            self.fh = None


class SalidaBin:
    """Fichero secuencial SIN FORMATO de Intel: cada registro va entre dos marcas de 4 bytes con
    su longitud (enteros little endian)."""

    def __init__(self, nombre):
        self.nombre = nombre
        self.fh = open(nombre, "wb")

    def reg(self, datos):
        n = len(datos).to_bytes(4, "little")
        self.fh.write(n + datos + n)

    def w(self, lineas):
        raise TypeError("escritura formateada en un fichero sin formato")

    def cerrar(self):
        if self.fh is not None:
            self.fh.close()
            self.fh = None


class SalidaReanudada(Salida):
    """Fichero formateado existente posicionado tras sus primeros `nbytes` (BACKSPACE tras leerlo
    en un re-arranque): el primer WRITE trunca lo que quede detrás."""

    def __init__(self, nombre, nbytes):
        self.nombre = nombre
        self.fh = open(nombre, "r+b")
        self.fh.seek(nbytes)
        self.pendiente = True

    def w(self, lineas):
        if self.pendiente:
            self.fh.truncate()
            self.pendiente = False
        if isinstance(lineas, str):
            lineas = [lineas]
        self.fh.write("".join(l + "\r\n" for l in lineas).encode("latin-1", errors="replace"))


class SalidaBinReanudada(SalidaBin):
    """Fichero sin formato existente posicionado tras sus primeros `nbytes` (ver SalidaReanudada)."""

    def __init__(self, nombre, nbytes):
        self.nombre = nombre
        self.fh = open(nombre, "r+b")
        self.fh.seek(nbytes)
        self.pendiente = True

    def reg(self, datos):
        if self.pendiente:
            self.fh.truncate()
            self.pendiente = False
        SalidaBin.reg(self, datos)


class EntradaBin:
    """Fichero secuencial SIN FORMATO de entrada (registros de Intel entre marcas de longitud),
    con REWIND. `leer()` devuelve los bytes del registro siguiente o None al final del fichero
    (END=); un registro mal formado se trata como el final de los datos legibles."""

    def __init__(self, nombre):
        self.nombre = nombre
        with open(nombre, "rb") as f:
            datos = f.read()
        self.regs = []
        i = 0
        while i + 4 <= len(datos):
            n = int.from_bytes(datos[i:i + 4], "little", signed=True)
            if n < 0 or i + 8 + n > len(datos):
                self.regs.append(None)          # registro corrupto: ERR= al leerlo
                break
            self.regs.append(datos[i + 4:i + 4 + n])
            i += 8 + n
        self.ptr = 0

    def leer(self):
        if self.ptr >= len(self.regs):
            return None
        r = self.regs[self.ptr]
        self.ptr += 1
        if r is None:
            raise ValueError("registro sin formato corrupto")
        return r

    def rewind(self):
        self.ptr = 0

    def cerrar(self):
        pass


class Pantalla:
    """Unidad * (pantalla)."""

    def __init__(self):
        self.lineas = []

    def w(self, lineas):
        if isinstance(lineas, str):
            lineas = [lineas]
        for l in lineas:
            self.lineas.append(l)
            sys.stdout.write(l + "\n")
        sys.stdout.flush()

    def cerrar(self):
        pass


class Entrada:
    """Fichero formateado de entrada: registros en memoria (como los lee Intel: sin el fin de
    línea) con puntero, REWIND y BACKSPACE."""

    def __init__(self, nombre):
        self.nombre = nombre
        with open(nombre, "rb") as f:
            txt = f.read().decode("latin-1")
        regs = txt.split("\n")
        if regs and regs[-1] == "":
            regs.pop()
        self.regs = [r[:-1] if r.endswith("\r") else r for r in regs]
        self.ptr = 0

    def leer(self):
        if self.ptr >= len(self.regs):
            return None
        r = self.regs[self.ptr]
        self.ptr += 1
        return r

    def rewind(self):
        self.ptr = 0

    def cerrar(self):
        pass


def _iniciar(obj, decl, data, params):
    """Crea las variables de un módulo Fortran (declaraciones y valores iniciales) en `obj`."""
    for nom, (tipo, dims, lon, alloc, _mod) in decl.items():
        if nom in params:
            continue
        if alloc:
            v = None
        elif dims:
            v = crear(tipo, [_dim(d) for d in dims], lon)
        elif tipo == "CHARACTER":
            v = ""
        elif tipo == "LOGICAL":
            v = False
        elif tipo == "INTEGER":
            v = 0
        else:
            v = 0.0
        setattr(obj, nom, v)
    for nom, val in data.items():
        tipo, dims, lon = decl[nom][:3]
        if dims and isinstance(val, list):
            a = getattr(obj, nom)
            if len(dims) > 1:
                # orden de Fortran: el primer índice varía más rápido
                forma = tuple(_dim(d) for d in dims)
                a[tuple(slice(1, None) for _ in forma)] = np.array(val).reshape(forma, order="F")
                continue
            for i, x in enumerate(val, 1):
                a[i] = fc(x, lon) if tipo == "CHARACTER" else x
        elif tipo == "CHARACTER":
            setattr(obj, nom, fc(val, lon))
        else:
            setattr(obj, nom, val)
    for k, v in params.items():
        setattr(obj, k, v)


class Prime:
    """Variables de los módulos de PRIME (PRIME_PARAMS, NUMPARM, DFSN, WAKEDAT, AMBIENT, PLU y
    PRM2_WAKEDAT), en su propio espacio porque varias coinciden en nombre con las de MAIN1."""


class Estado:
    def __init__(self):
        _iniciar(self, T.DECL, T.DATA, P)
        prime_params = {k: v for k, v in P.items() if k in T.DECL_PRIME or k not in T.DECL}
        self.P = Prime()
        _iniciar(self.P, T.DECL_PRIME, T.DATA_PRIME, prime_params)
        # variables de los módulos RLINE_DATA y BUOYANT_LINE (fuentes fuera de alcance) que leen
        # partes comunes del programa
        self.NBLTOTAL = 0
        self.NRLINES = 0
        self.NUMBLGRPS = 0
        self.NBLAVGINPALLOC = 0
        # UTHEOR de REFWS (conserva el valor entre llamadas)
        self.PRF_UTHEOR = 0.0
        self.L_BLHOURLY = False
        self.L_RDEPRESS = False
        self.L_RBARRIER = False
        self.RLMOVESCONV = False
        self.U = {}                    # unidades abiertas: número -> Salida/Entrada
        self.pantalla = Pantalla()
        self.U[6] = self.pantalla
        self.ERRTMP = []               # fichero temporal de mensajes (IERUNT)

    # ------------------------------------------------------------------ memoria
    def alloc(self, nom, *dims, val=None):
        tipo, _d, lon = T.DECL[nom][:3]
        setattr(self, nom, crear(tipo, dims, lon, val))

    def allocated(self, nom):
        return getattr(self, nom) is not None

    # ------------------------------------------------------------------ unidades
    def abrir_salida(self, unidad, nombre):
        viejo = self.U.get(unidad)
        if viejo is not None:
            viejo.cerrar()
        f = Salida(nombre)
        self.U[unidad] = f
        return f

    def abrir_bin(self, unidad, nombre):
        viejo = self.U.get(unidad)
        if viejo is not None:
            viejo.cerrar()
        f = SalidaBin(nombre)
        self.U[unidad] = f
        return f

    def abrir_entrada(self, unidad, nombre):
        f = Entrada(nombre)
        self.U[unidad] = f
        return f

    def abrir_entrada_bin(self, unidad, nombre):
        f = EntradaBin(nombre)
        self.U[unidad] = f
        return f

    def abrir_reanudada(self, unidad, nombre, nbytes, binario=False):
        """Fichero de salida existente que se reanuda (re-arranque con INITFILE/MULTYEAR): el
        original lo lee hasta la fecha del re-arranque, hace BACKSPACE y sigue escribiendo, con lo
        que lo que hubiera detrás de esos `nbytes` desaparece con el primer WRITE."""
        viejo = self.U.get(unidad)
        if viejo is not None:
            viejo.cerrar()
        f = (SalidaBinReanudada if binario else SalidaReanudada)(nombre, nbytes)
        self.U[unidad] = f
        return f

    def volcar(self, unidad):
        """CLOSE y OPEN con POSITION='APPEND' (SAVEFILE): el fichero queda escrito en disco."""
        f = self.U.get(unidad)
        if f is not None and getattr(f, "fh", None) is not None:
            f.fh.flush()

    def w(self, unidad, lineas):
        self.U[unidad].w(lineas)

    def wf(self, unidad, fmt, *items):
        self.U[unidad].w(fwrite(fmt, *items))

    def cerrar(self, unidad):
        f = self.U.pop(unidad, None)
        if f is not None:
            f.cerrar()

    def cerrar_todo(self):
        for u in list(self.U):
            if u != 6:
                self.cerrar(u)

    # ------------------------------------------------------------------ mensajes
    def errhdl(self, pathwy, modnam, inertp, inercd, inpmsg):
        """ERRHDL: registro en el fichero temporal de mensajes."""
        self.IERROR += 1
        if inertp == "E":
            self.FATAL = True
            self.NFATAL += 1
            if self.NFATAL == 999:
                self.ERRTMP.append(fwrite("(A2,1X,A1,A3,I8,1X,A12,': ',A50,1X,A12)",
                                          fx(pathwy, 2), inertp, "999", min(self.ILINE, 99999999),
                                          "ERRHDL", fx("Number of Fatal Errors Has Reached Limit of 999", 50),
                                          " " * 12)[0])
                return
            if self.NFATAL > 999:
                return
        errmg1 = _ERR_IDX.get(fx(inercd, 3))
        if errmg1 is None:
            errmg1 = fx("SYSTEM ERROR: MESSAGE NOT FOUND FOR THIS NUMBER!", 50)
        m = modnam.rstrip(" ")[:12]
        t = inpmsg.rstrip(" ")[:12]
        self.ERRTMP.append(fwrite("(A2,1X,A1,A3,I8,1X,A12,': ',A50,1X,A12)", fx(pathwy, 2),
                                  inertp, fx(inercd, 3), min(self.ILINE, 99999999), m, errmg1, t)[0])

    @staticmethod
    def _campos_msg(r):
        """READ(IERUNT,1116): PATH, ERRTP, ERRCD, IERRLN, MODNAM, ERRMG1, ERRMG2."""
        r = r.ljust(93)
        return r[0:2], r[3], r[4:7], int(r[7:15]), r[16:28], r[30:80], r[81:93]

    def terrst(self):
        """TERRST: totales de mensajes, horas de calma y horas ausentes."""
        self.IFTL = self.IWRN = self.INFO = self.ICLM = self.IMSG = 0
        self.DNUM = 0.0
        for r in self.ERRTMP:
            path, errtp, errcd, _ln, _mod, _m1, errmg2 = self._campos_msg(r)
            self.PATH = fc(path, 2)
            fnum, _imit = stonum(errcd, 3, self.FNUM)
            self.FNUM = fnum
            if errtp == "E":
                self.IFTL += 1
            elif errtp == "W":
                self.IWRN += 1
            elif errtp == "I":
                self.INFO += 1
                n = nint(fnum)
                if n in (440, 460):
                    self.DNUM, _ = stodbl(errmg2, 12, self.DNUM)
                    icdat = nint(self.DNUM)
                    icyr = icdat // 1000000
                    if self.RSTINP or self.IMSTAT[6] == 0 or self.ISDATE <= icdat <= self.IEDATE:
                        icmn = icdat // 10000 - (icdat // 1000000) * 100
                        icdy = icdat // 100 - (icdat // 10000) * 100
                        if icmn > 0 and icdy > 0:
                            icjdy = self.julian(icyr, icmn, icdy)
                        else:
                            continue
                        if self.IPROC[icjdy] == 1:
                            if n == 440:
                                self.ICLM += 1
                            else:
                                self.IMSG += 1
        self.EOF = True

    def sumtbl(self, u):
        """SUMTBL: resumen de mensajes."""
        out = [lw(" --------- Summary of Total Messages --------"), lw(" "),
               fwrite("(' A Total of   ',I10,' Fatal Error Message(s)')", self.IFTL)[0],
               fwrite("(' A Total of   ',I10,' Warning Message(s)')", self.IWRN)[0],
               fwrite("(' A Total of   ',I10,' Informational Message(s)')", self.INFO)[0]]
        if self.NTOTHRS > 0:
            out += fwrite("(/,' A Total of   ',I10,' Hours Were Processed')", self.NTOTHRS)
            out += fwrite("(/,' A Total of   ',I10,' Calm Hours Identified')", self.ICLM)
            percent = np.float32(100.0) * (np.float32(self.IMSG) / np.float32(self.NTOTHRS))
            out += fwrite("(/,' A Total of   ',I10,' Missing Hours Identified (',F6.2,' Percent)')",
                          self.IMSG, float(percent))
            if self.NSUBBGHOUR > 0:
                out += fwrite("(/,' A Total of   ',I10,' Missing Hourly BACKGRND ','Values Substituted')",
                              self.NSUBBGHOUR)
            if percent > 10.0:
                out += fwrite("(/,' CAUTION!:  Number of Missing Hours Exceeds 10 ','Percent of Total!',/,"
                              "12X,'Data May Not Be ','Acceptable for Regulatory Applications.',/,12X,"
                              "'See Section 5.3.2 of \"Meteorological Monitoring ','Guidance',/,12X,"
                              "'for Regulatory Modeling ','Applications\" (EPA-454/R-99-005).')")
            if self.WDPLETE or self.DEPOS or self.WDEP:
                out += fwrite("(/,' Met Data File Includes ',F10.2,' Millimeters (',F10.3,"
                              "' Inches) of Precipitation')", self.TOTAL_PRECIP, self.TOTAL_PRECIP / 25.4)
        out += [lw(" "), lw(" "), lw("   ******** FATAL ERROR MESSAGES ******** ")]
        j = 0
        for r in self.ERRTMP:
            if r[3:4] == "E":
                j += 1
                out.append(" " + r.ljust(93))
        if j == 0:
            out += [lw("              ***  NONE  ***         "), lw(" ")]
        out += [lw(" "), lw("   ********   WARNING MESSAGES   ******** ")]
        j = 0
        for r in self.ERRTMP:
            if r[3:4] == "W":
                j += 1
                if not self.NOWARN:
                    if j <= 999:
                        out.append(" " + r.ljust(93))
                    if j == 999:
                        out.append(lw("More Than 999 Warning Messages ", "Found.  See ERRORFIL Output for",
                                      " the Remainder."))
        if j == 0:
            out += [lw("              ***  NONE  ***        "), lw(" ")]
        elif self.NOWARN:
            out += [lw(" ** WARNINGS SUPPRESSED BY NOWARN OPTION **"), lw(" ")]
        self.w(u, out)

    def msgwrt(self):
        """MSGWRT: fichero de mensajes detallado (ERRORFIL)."""
        out = [lw(" "), lw("   ************ Error Message List *************"), lw(" "),
               lw("   PW     --- Pathway                           "),
               lw("   Code   --- Error Type + Error Code           "),
               lw("   L#     --- The Line Number Where Error Occurs"),
               lw("   ModNam --- Module Name In Which Error Occurs "),
               lw("   Hints  --- Hints For The Possible Solution   "),
               lw("   *********************************************"), lw(" "),
               "PW CODE    L#      MODNAM     " + " " * 18 + "ERROR MESSAGES" + " " * 22 + "HINTS",
               "-- ---- ------- ------------- " + "-" * 50 + " ------------", lw(" ")]
        out += [r.ljust(93) for r in self.ERRTMP]
        self.w(self.IERWRT, out)

    def header(self, u):
        """HEADER: cabecera de página (con salto de página)."""
        if u == self.IOUNIT:
            self.IPAGE += 1
            pag = self.IPAGE
        elif u == self.ISUMUNT:
            self.IPGSUM += 1
            pag = self.IPGSUM
        out = fwrite("(A1,1X,'*** AERMOD - VERSION ',A6,' ***',3X,'*** ',A68,' ***',8X,A8)", "\x0c",
                     fx(self.VERSN, 6), fx(self.TITLE1, 68), fx(self.RUNDAT, 8))
        f9029 = "(1X,'*** AERMET - VERSION ',A6,' ***',3X,'*** ',A68,' ***',8X,A8,/T120,'PAGE',I4)"
        if u == self.IOUNIT:
            if pag <= 999:
                fmt = f9029
            elif pag <= 99999:
                fmt = "(1X,'*** AERMET - VERSION ',A6,' ***',3X,'*** ',A68,' ***',8X,A8,/T118,'PAGE',I6)"
            else:
                fmt = "(1X,'*** AERMET - VERSION ',A6,' ***',3X,'*** ',A68,' ***',8X,A8,/T116,'PAGE',I8)"
                pag = min(pag, 99999999)
        else:
            fmt = f9029
        out += fwrite(fmt, fx(self.C_METVER, 6), fx(self.TITLE2, 68), fx(self.RUNTIM, 8), pag)
        s = self.MODOPS_STRING
        out += fwrite("(1X,'*** MODELOPTs: ',1X,A:)", s)
        if len(s) > 110:
            out += fwrite("(4X,A:)", " " * (250 - len(s)))
        self.w(u, out)

    def datime(self):
        """DATIME: fecha (mm/dd/aa) y hora (hh:mm:ss) de la corrida."""
        t = datetime.datetime.now()
        return "%02d/%02d/%02d" % (t.month, t.day, t.year % 100), "%02d:%02d:%02d" % (t.hour, t.minute, t.second)

    # ------------------------------------------------------------------ fechas
    _NDAY = (0, 0, 31, 59, 90, 120, 151, 181, 212, 243, 273, 304, 334)
    _IDYMAX = (0, 31, 29, 31, 30, 31, 30, 31, 31, 30, 31, 30, 31)

    def julian(self, inyr, inmn, indy):
        """JULIAN: día juliano (1..366)."""
        if inmn < 1 or inmn > 12:
            self.errhdl(self.PATH, "JULIAN", "E", "203", fwrite("('MONTH = ',I2)", inmn)[0])
            self.RUNERR = True
            return 0
        if indy > self._IDYMAX[inmn]:
            self.errhdl(self.PATH, "JULIAN", "E", "203", fwrite("('DAY=',I2,' MO=',I2)", indy, inmn)[0])
            self.RUNERR = True
            return 0
        if inyr % 4 != 0 or (inyr % 100 == 0 and inyr % 400 != 0):
            if inmn != 2 or indy <= 28:
                return indy + self._NDAY[inmn]
            self.errhdl(self.PATH, "JULIAN", "E", "370", fwrite("('YR= ',I4)", inyr)[0])
            self.RUNERR = True
            return 60
        jdy = indy + self._NDAY[inmn]
        if inmn > 2:
            jdy += 1
        return jdy

    def gregor(self, inyr, inmn, jdy, idy_previo=0):
        """GREGOR: día del mes a partir del juliano y el mes."""
        if inmn < 1 or inmn > 12:
            self.errhdl(self.PATH, "GREGOR", "E", "203", "MONTH")
            return idy_previo
        if jdy < 1 or jdy > 366:
            self.errhdl(self.PATH, "GREGOR", "E", "203", "Juli Day")
            return idy_previo
        idy = jdy - self._NDAY[inmn]
        if not (inyr % 4 != 0 or (inyr % 100 == 0 and inyr % 400 != 0)) and inmn > 2:
            idy -= 1
        return idy


def fmod_fortran(a, b):
    """MOD de enteros de Fortran: el resto lleva el signo del dividendo."""
    r = abs(a) % abs(b)
    return -r if a < 0 else r


def idiv(a, b):
    """División entera de Fortran (trunca hacia cero)."""
    q = abs(a) // abs(b)
    return q if (a >= 0) == (b >= 0) else -q
