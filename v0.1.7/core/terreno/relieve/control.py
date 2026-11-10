# -*- coding: utf-8 -*-
"""Traducción de AERMAP v24142 (US EPA, dominio público): lectura del fichero de control
(aermap.f: PRESET y sus PRE*, SETUP, LWRUPR, DEFINE, GETFLD, EXPATH, EXKEY, SETORD, COCARD,
SOCARD, RECARD, OUCARD, INCLUD y todas las subrutinas de cada clave).

Peculiaridades del original que se replican a propósito:
  · Columnas FIJAS para la vía (2) y la clave (8), con el desplazamiento de hasta 3 columnas
    que se decide SOLO en la línea 1 (DEFINE con ILINE = 1).
  · Los campos que no aparecen en una línea conservan el valor de la línea anterior
    (FIELD es global y solo se reescribe 1..IFC).
  · Cuando un número no se puede leer (STODBL con error), la variable destino conserva su
    valor anterior; varias son locales con SAVE.
  · ILREAL de INCLUD/PREINCLUD/WRITE_INCLUD nunca se reinicia: a partir del segundo fichero
    INCLUDED los números de línea de los mensajes salen desplazados en +1.
  · PRESET comparte estado con SETUP (XINT/YINT, PPATH, LOCB...): sus restos influyen."""
import os

from .estado import ILEN_FLD, ISTRG, KEYWD, fx, feq
from .formato import nint, stodbl, stonum
from .utm import utm_zona

PATHWY = ["CO", "SO", "RE", "OU", "**"]
_MIN = "abcdefghijklmnopqrstuvwxyz"
_MAY = "ABCDEFGHIJKLMNOPQRSTUVWXYZ"
_TABLA = str.maketrans(_MIN, _MAY)


# =============================================================================== lectura
def leer_lineas(ruta):
    """Registros del fichero tal como los lee gfortran: sin el fin de línea (LF o CRLF)."""
    with open(ruta, "rb") as f:
        txt = f.read().decode("latin-1")
    lineas = txt.split("\n")
    if lineas and lineas[-1] == "":
        lineas.pop()
    return [l[:-1] if l.endswith("\r") else l for l in lineas]


def cargar(e, linea):
    """READ (A512,T1,512A1) + LWRUPR: RUNST1 conserva mayúsculas/minúsculas; RUNST va en
    mayúsculas (solo a-z) y relleno a 512 columnas."""
    e.runst1 = linea[:ISTRG]
    e.runst = e.runst1.ljust(ISTRG).translate(_TABLA)


def define(e):
    """DEFINE: localiza los campos de la línea (comillas dobles delimitan campos con blancos)."""
    r = e.runst
    e.bline = True
    infld = inquote = False
    if e.iline == 1:
        if r[0] != " ":
            e.locb[1] = 1
        elif r[1] != " ":
            e.locb[1] = 2
        elif r[2] != " ":
            e.locb[1] = 3
        elif r[3] != " ":
            e.locb[1] = 4
        else:
            e.locb[1] = 1
        e.loce[1] = e.locb[1] + 1
        e.locb[2] = e.locb[1] + 3
        e.loce[2] = e.locb[1] + 10
    e.ifc = 2
    for i in range(e.locb[1], e.loce[2] + 2):
        if r[i - 1] != " ":
            e.bline = False
    for i in range(e.locb[1] + 12, ISTRG + 1):
        c = r[i - 1]
        if not infld and c == '"':
            e.bline = False
            infld = inquote = True
            e.ifc += 1
            e.locb[e.ifc] = i + 1
        elif not infld and c != " ":
            e.bline = False
            infld = True
            e.ifc += 1
            e.locb[e.ifc] = i
        elif inquote and c == '"':
            infld = inquote = False
            e.loce[e.ifc] = i - 1
        elif not inquote and infld and c == " ":
            infld = False
            e.loce[e.ifc] = i - 1
        if infld and i == ISTRG:
            e.loce[e.ifc] = ISTRG


def getfld(e):
    """GETFLD: contenido de los campos 1..IFC (truncados a ILEN_FLD). Los demás conservan
    el valor anterior."""
    for i in range(1, e.ifc + 1):
        b, f = e.locb[i], e.loce[i]
        if f - b <= ILEN_FLD - 1:
            e.field[i] = e.runst[b - 1:f] if f >= b else ""
        else:
            e.field[i] = e.runst[b - 1:b - 1 + ILEN_FLD]


def expath(e, inpfld):
    """EXPATH -> nopath."""
    inpfld = fx(inpfld, 2)
    if inpfld != "  ":
        e.path = inpfld
        for i, p in enumerate(PATHWY, 1):
            if inpfld == p:
                e.ipnum = i
                return False
        return True
    e.path = e.ppath
    e.ipnum = e.ippnum
    return False


def exkey(e, inpfld):
    """EXKEY -> nokey."""
    inpfld = fx(inpfld, 8)
    if inpfld != "        ":
        e.keywrd = inpfld
        return inpfld not in KEYWD
    e.keywrd = e.pkeywd
    return False


def kw(e):
    return e.keywrd.rstrip()


def setord(e):
    """SETORD: orden de STARTING/FINISHED y de las vías."""
    m = "SETORD"
    k = kw(e)
    if k == "STARTING":
        if e.istart or not e.ifinis:
            e.errhdl(e.ppath, m, "E", "115", e.path)
        elif e.ipnum != e.ippnum + 1:
            if e.path == "SO" and e.ppath == "RE":
                e.errhdl(e.ppath, m, "E", "120", e.path)
        e.istart = True
        e.ifinis = False
    elif k == "FINISHED":
        if e.ifinis or not e.istart:
            e.errhdl(e.ppath, m, "E", "115", e.path)
        elif e.istart and e.path != e.ppath:
            e.errhdl(e.ppath, m, "E", "120", e.path)
        e.istart = False
        e.ifinis = True
    elif not e.istart or e.ifinis:
        e.errhdl(e.ppath, m, "E", "115", e.path)
    elif e.istart and e.path != e.ppath:
        e.errhdl(e.ppath, m, "E", "120", e.path)
    e.ppath = e.path
    e.ippnum = e.ipnum


def _dbl(e, i, previo=0.0, length=ILEN_FLD):
    return stodbl(e.field[i], length, previo)


def _num(e, i, previo=0.0):
    return stonum(e.field[i], ILEN_FLD, previo)


def _i8(n):
    return f"{n:8d}"


# =============================================================================== PRESET
def preset(e, lineas):
    """PRESET: primera pasada para dimensionar los vectores."""
    e.iline = 0
    e.ndem = 0
    e.nsrc = 0
    e.ipnum = 0
    e.ippnum = 0
    e.ista = False
    e.iend = False
    e.newid = True
    e.nrec = e.nnet = e.ixm = e.iym = 0       # variables de módulo: valen 0 al empezar
    for linea in lineas:
        e.iline += 1
        cargar(e, linea)
        define(e)
        getfld(e)
        if e.bline:
            continue
        if feq(e.field[1], "NO") and feq(e.field[2], "ECHO"):
            continue
        if expath(e, e.field[1]):
            e.path = e.ppath
            continue
        elif e.path == "**":
            continue
        if exkey(e, e.field[2]):
            e.pkeywd = e.keywrd
            continue
        e.ppath = e.path
        e.ippnum = e.ipnum
        if e.path == "CO" and kw(e) == "DATAFILE":
            e.ndem += 1
        if e.path == "SO":
            _srcsiz(e)
        if e.path == "RE":
            _recsiz(e)
        e.pkeywd = e.keywrd
        if e.path == "OU" and kw(e) == "FINISHED":
            break
    e.iline = 0
    e.pnetid = "        "
    e.nsrc = max(e.nsrc, 1)
    e.nrec = max(e.nrec, 1)
    e.ndem = max(e.ndem, 1)
    e.narc = e.nrec
    e.nnet = max(e.nnet, 1)
    e.ixm = max(e.ixm, 1)
    e.iym = max(e.iym, 1)


def _srcsiz(e):
    k = kw(e)
    if k == "STARTING":
        e.nsrc = 0
    elif k == "LOCATION":
        e.nsrc += 1
    elif k == "INCLUDED":
        _preinclud(e)


def _recsiz(e):
    k = kw(e)
    if k == "STARTING":
        e.nrec = 0
        e.nnet = e.ixm = e.iym = 0
        e.ista = False
    elif k == "GRIDCART":
        _precart(e)
    elif k == "GRIDPOLR":
        _prepolr(e)
    elif k in ("DISCCART", "EVALCART", "DISCPOLR"):
        e.nrec += 1
    elif k == "INCLUDED":
        _preinclud(e)


def _abrir_incluido(e):
    """Nombre del fichero INCLUDED (respeta mayúsculas/minúsculas) o None."""
    if e.loce[3] - e.locb[3] <= ILEN_FLD - 1:
        return e.runst1[e.locb[3] - 1:e.loce[3]]
    return None


def _preinclud(e):
    m = "PREINCLUD"
    e.iline = 1
    if e.ifc == 3:
        nombre = _abrir_incluido(e)
        if nombre is None:
            e.errhdl(e.path, m, "E", "210", _i8(ILEN_FLD))
            return
        try:
            lineas = leer_lineas(nombre)
        except OSError:
            e.errhdl(e.path, m, "E", "500", "INCFILE ")
            return
    else:
        return
    for linea in lineas:
        e.iline += 1
        e.ilreal_pre += 1
        cargar(e, linea)
        define(e)
        if e.ilreal_pre == 1:
            e.iline -= 1
        getfld(e)
        if e.bline:
            continue
        if feq(e.field[1], "NO") and feq(e.field[2], "ECHO"):
            continue
        if expath(e, e.field[1]):
            e.path = e.ppath
            continue
        elif e.path == "**":
            continue
        if exkey(e, e.field[2]):
            e.pkeywd = e.keywrd
            continue
        e.ppath = e.path
        e.ippnum = e.ipnum
        if e.path == "SO":
            if kw(e) == "LOCATION":
                e.nsrc += 1
        elif e.path == "RE":
            k = kw(e)
            if k == "GRIDCART":
                _precart(e)
            elif k == "GRIDPOLR":
                _prepolr(e)
            elif k in ("DISCCART", "EVALCART", "DISCPOLR"):
                e.nrec += 1
        e.pkeywd = e.keywrd
    e.iline += 1                # la lectura que encuentra el fin de fichero también cuenta
    e.ilreal_pre += 1


def _netid_pre(e, claves):
    """Parte común de PRECART/PREPOLR para decidir NETIDT/KTYPE. -> False si inválido."""
    e.netidt = fx(e.field[3], 8)
    if not e.newid and (e.netidt.rstrip() == "" or e.netidt.rstrip() in claves):
        e.netidt = e.pnetid
        e.ktype = fx(e.field[3], 5)
    elif not e.newid and e.netidt == e.pnetid:
        e.ktype = fx(e.field[4], 5)
    elif e.newid and e.netidt.rstrip() != "":
        e.newid = False
        e.ktype = fx(e.field[4], 5)
        e.nnet += 1
    else:
        return False
    return True


def _isc(e, clave):
    for i in range(1, e.ifc + 1):
        if feq(e.field[i], clave):
            e.isc = i + 1


def _precart(e):
    if e.ifc < 3:
        return
    if not _netid_pre(e, ("XYINC", "XPNTS", "YPNTS", "ELEV", "HILL", "FLAG", "END")):
        return
    kt = e.ktype.rstrip()
    if kt == "STA":
        e.ista = True
        e.iend = False
        e.newid = False
        e.recerr = False
        e.icount = e.jcount = 0
    elif kt == "XYINC":
        _pregencar(e)
    elif kt in ("XPNTS", "YPNTS"):
        _prexypnts(e)
    elif kt == "END":
        e.iend = True
        if not e.recerr:
            e.nrec += e.icount * e.jcount
        e.ista = False
        e.newid = True
    elif kt not in ("ELEV", "FLAG", "HILL"):
        e.recerr = True
        return
    e.pnetid = e.netidt


def _pregencar(e):
    _isc(e, "XYINC")
    if e.ifc == e.isc - 1 or e.ifc > e.isc + 5 or e.ifc < e.isc + 5:
        e.recerr = True
        return
    t = [0.0] * 7
    error = False
    for k in range(1, 7):
        v, imit = _dbl(e, e.isc + k - 1, e._pre_tempp[k] if hasattr(e, "_pre_tempp") else 0.0)
        t[k] = v
        if imit == -1:
            error = True
            e.recerr = True
    e._pre_tempp = t
    if error:
        return
    e.xint = t[1]
    e.icount = nint(t[2])
    e.xdelta = t[3]
    e.yint = t[4]
    e.jcount = nint(t[5])
    e.ydelta = t[6]
    e.ixm = max(e.ixm, e.icount)
    e.iym = max(e.iym, e.jcount)


def _prexypnts(e):
    kt = e.ktype.rstrip()
    _isc(e, kt)
    if e.ifc == e.isc - 1:
        e.recerr = True
        return
    n = e.icount if kt == "XPNTS" else e.jcount
    for i in range(e.isc, e.ifc + 1):
        e.fnum, imit = _num(e, i, e.fnum)
        if imit == -1:
            e.recerr = True
        n += 1
        if kt == "XPNTS":
            e.ixm = max(e.ixm, n)
        else:
            e.iym = max(e.iym, n)
    if kt == "XPNTS":
        e.icount = n
    else:
        e.jcount = n


def _prepolr(e):
    if e.ifc < 3:
        return
    if not _netid_pre(e, ("ORIG", "DIST", "DDIR", "ELEV", "HILL", "FLAG", "GDIR", "END")):
        e.recerr = True
        return
    kt = e.ktype.rstrip()
    if kt == "STA":
        e.ista = True
        e.iend = False
        e.newid = False
        e.recerr = False
        e.icount = e.jcount = 0
    elif kt == "DIST":
        _isc(e, "DIST")
        if e.ifc == e.isc - 1:
            e.recerr = True
            return
        n = e.icount
        for i in range(e.isc, e.ifc + 1):
            e.fnum, imit = _num(e, i, e.fnum)
            if imit == -1:
                e.recerr = True
            n += 1
            e.ixm = max(e.ixm, n)
        e.icount = n
    elif kt == "GDIR":
        _isc(e, "GDIR")
        if e.ifc == e.isc - 1 or e.ifc < e.isc + 2 or e.ifc > e.isc + 2:
            e.recerr = True
            return
        t = [0.0] * 4
        error = False
        prev = getattr(e, "_pre_tgp", [0.0] * 4)
        for k in range(1, 4):
            v, imit = _dbl(e, e.isc + k - 1, prev[k])
            t[k] = v
            if imit == -1:
                e.recerr = True
                error = True
        e._pre_tgp = t
        if error:
            return
        e.jcount = nint(t[1])
        e.iym = max(e.iym, e.jcount)
    elif kt == "DDIR":
        _isc(e, "DDIR")
        if e.ifc == e.isc - 1:
            e.recerr = True
            return
        n = e.jcount
        for i in range(e.isc, e.ifc + 1):
            e.fnum, imit = _num(e, i, e.fnum)
            if imit == -1:
                e.recerr = True
            n += 1
            e.iym = max(e.iym, n)
        e.jcount = n
    elif kt == "END":
        e.iend = True
        if not e.recerr:
            e.nrec += e.icount * e.jcount
        e.ista = False
        e.newid = True
    elif kt not in ("ELEV", "FLAG", "HILL", "ORIG"):
        e.recerr = True
        return
    e.pnetid = e.netidt


# =============================================================================== SETUP
def setup(e, lineas):
    """SETUP: lectura del control con eco al fichero de salida."""
    m = "SETUP"
    e.iline = 0
    e.gotdomflg = False
    w = e.out.append
    for linea in lineas:
        e.iline += 1
        cargar(e, linea)
        define(e)
        getfld(e)
        if e.echo and feq(e.field[1], "OU") and feq(e.field[2], "FINISHED"):
            if 1 <= e.locb[1] <= 4:
                w(e.runst1.ljust(ISTRG)[:10 + e.locb[1]])
        elif e.echo:
            w(e.runst1.rstrip(" "))
        if e.bline:
            continue
        if feq(e.field[1], "NO") and feq(e.field[2], "ECHO"):
            e.echo = False
            continue
        if expath(e, e.field[1]):
            e.errhdl(e.ppath, m, "E", "100", e.path)
            e.path = e.ppath
            continue
        elif e.path == "**":
            continue
        if exkey(e, e.field[2]):
            e.errhdl(e.path, m, "E", "105", e.keywrd)
            e.pkeywd = e.keywrd
            continue
        setord(e)
        k = kw(e)
        if e.path == "CO":
            cocard(e)
            if k == "DOMAINLL" or (k == "DOMAINXY" and e.gotdomflg):
                e.domcard = e.runst1[3:min(len(e.runst1.rstrip(" ")), ILEN_FLD + 3)]
            elif k == "ANCHORXY":
                e.anchcrd = e.runst1[3:min(len(e.runst1.rstrip(" ")), ILEN_FLD + 3)]
            elif k == "TERRHGTS":
                e.hgtcard = e.runst1[3:min(len(e.runst1.rstrip(" ")), ILEN_FLD + 3)]
        elif e.path == "SO":
            socard(e)
        elif e.path == "RE":
            recard(e)
        elif e.path == "OU":
            oucard(e)
        e.pkeywd = e.keywrd
        if e.path == "OU" and kw(e) == "FINISHED":
            break
    else:
        e.iline += 1            # la lectura que da fin de fichero también incrementa ILINE
    if e.icstat[20] != 1 or e.iostat[20] != 1:
        ifstat = e.icstat[20] * 1000 + e.isstat[20] * 100 + e.irstat[20] * 10 + e.iostat[20]
        e.errhdl(e.path, m, "E", "125", f"{ifstat:04d}"[-4:])


# =============================================================================== CO
def cocard(e):
    m = "COCARD"
    k = kw(e)
    c = e.icstat

    def unica(i, f):
        c[i] += 1
        if c[i] != 1:
            e.errhdl(e.path, m, "E", "135", e.keywrd)
        else:
            f(e)

    if k == "STARTING":
        e.istart = True
        c[1] += 1
        if c[1] != 1:
            e.errhdl(e.path, m, "E", "135", e.keywrd)
    elif k == "TITLEONE":
        unica(2, _titles)
    elif k == "TITLETWO":
        unica(3, _titles)
    elif k == "DATATYPE":
        unica(4, _dattyp)
    elif k == "DATAFILE":
        c[5] += 1
        _datfil(e)
    elif k in ("DOMAINXY", "DOMAINLL"):
        unica(6, _domain)
    elif k == "ANCHORXY":
        unica(7, _anchor)
    elif k == "TERRHGTS":
        unica(9, _terrht)
    elif k == "FLAGPOLE":
        unica(11, _flagdf)
    elif k == "RUNORNOT":
        unica(12, _runnot)
    elif k == "DEBUGOPT":
        unica(13, _debopt)
    elif k == "NADGRIDS":
        unica(14, _nadgrids)
    elif k == "FINISHED":
        e.ifinis = True
        c[20] += 1
        if c[20] != 1:
            e.errhdl(e.path, m, "E", "135", e.keywrd)
            return
        for i, nom in ((1, "STARTING"), (2, "TITLEONE"), (4, "DATATYPE"), (5, "DATAFILE"),
                       (7, "ANCHORXY"), (12, "RUNORNOT")):
            if c[i] == 0:
                e.errhdl(e.path, m, "E", "130", nom)
        if e.typdat.rstrip() == "DEM":
            for i in range(1, e.numdem + 1):
                if e.l_userelevunits[i]:
                    e.errhdl(e.path, "DATFIL", "E", "203", "DEMCHECK")
        elif e.typdat.rstrip() == "NED":
            for i in range(1, e.numdem + 1):
                if e.l_demcheck[i]:
                    e.errhdl(e.path, "DATFIL", "E", "203", "USERUNIT")
        if c[6] != 0:
            _comprobar_zona_ancla(e)
    else:
        e.errhdl(e.path, m, "E", "110", e.keywrd)


def _comprobar_zona_ancla(e):
    """Final de COCARD: coherencia entre las zonas del dominio y la del ANCHORXY."""
    m = "COCARD"
    zmin, zmax, za = abs(e.zonmin), abs(e.zonmax), abs(e.zaterr)

    def ok(zmin, zmax):
        if zmin == zmax and zmin == za:
            return True
        if zmin == zmax and abs(zmin - za) <= 1:
            return True
        if abs(zmax - zmin) == 1 and (za == zmin or za == zmax):
            return True
        if (zmin == 1 and zmax == 60 and za in (1, 60)) or (zmin == 60 and zmax == 1 and za in (1, 60)):
            return True
        return False

    if ok(zmin, zmax):
        return
    if e.domtyp == "LAT":
        e.zonmax = utm_zona(-1.0 * e.xdmin)
        e.zonmin = utm_zona(-1.0 * e.xdmax)
        zmin, zmax = abs(e.zonmin), abs(e.zonmax)
        bien = ((zmin == zmax and zmin == za)
                or (zmin == zmax and abs(zmax - za) <= 1 and abs(zmin - za) <= 1)
                or (abs(zmax - zmin) == 1 and (za == zmin or za == zmax))
                or (zmin == 1 and zmax == 60 and za in (1, 60))
                or (zmin == 60 and zmax == 1 and za in (1, 60)))
        if not bien:
            e.errhdl(e.path, m, "E", "242", _i8(e.zaterr))
            return
        e.domfix = True
        e.errhdl(e.path, m, "W", "244", "Neg West")
        xtmp = e.xdmin
        e.xdmin = -1.0 * e.xdmax
        e.xdmax = -1.0 * xtmp
        e.out.append("** Adjusted DOMAINLL inputs:")
        # el 1X final del formato no escribe nada en gfortran (no hay dato detrás)
        e.out.append(f"** DOMAINLL  {e.xdmin:13.5f} {e.ydmin:12.5f} {e.xdmax:13.5f} {e.ydmax:12.5f}")
        e.domadj = f"DOMAINLL  {e.xdmin:13.5f} {e.ydmin:12.5f} {e.xdmax:13.5f} {e.ydmax:12.5f} "
    else:
        e.errhdl(e.path, m, "E", "242", _i8(e.zaterr))


def _titles(e):
    m = "TITLES"
    lt = len(e.runst1.rstrip(" "))
    ini = e.loce[2] + 2
    txt = e.runst1[ini - 1:min(lt, ini + ILEN_FLD - 1)]
    if kw(e) == "TITLEONE":
        e.title1 = txt
        if txt.strip(" ") == "":
            e.errhdl(e.path, m, "E", "200", e.keywrd)
    else:
        e.title2 = txt
        if txt.strip(" ") == "":
            e.errhdl(e.path, m, "W", "200", e.keywrd)


def _dattyp(e):
    m = "DATTYP"
    if e.ifc == 2:
        e.errhdl(e.path, m, "E", "200", e.keywrd)
        return
    if e.ifc > 4:
        e.errhdl(e.path, m, "E", "202", e.keywrd)
        return
    if e.field[3][:3] == "DEM":
        e.typdat = "DEM "
    elif feq(e.field[3], "NED"):
        e.typdat = "NED "
    else:
        e.errhdl(e.path, m, "E", "203", " TYPDAT ")
    if e.ifc == 4:
        if feq(e.field[4], "FILLGAPS"):
            e.fillgaps = True
        else:
            e.errhdl(e.path, m, "E", "203", "FILLGAPS")


_UNIDADES = {"FEET": (1, 1.0), "DECI-FEET": (1, 0.1), "DECIFEET": (1, 0.1),
             "DECA-FEET": (1, 10.0), "DECAFEET": (1, 10.0), "METERS": (2, 1.0),
             "DECI-METERS": (2, 0.1), "DECIMETERS": (2, 0.1), "DECA-METERS": (2, 10.0),
             "DECAMETERS": (2, 10.0)}


def _datfil(e):
    m = "DATFIL"
    td = e.typdat.rstrip()
    if e.ifc == 2:
        e.errhdl(e.path, m, "E", "200", e.keywrd)
        return
    if (td == "DEM" and e.ifc > 4) or (td == "NED" and e.ifc > 5):
        e.errhdl(e.path, m, "E", "202", e.keywrd)
        return
    if e.loce[3] - e.locb[3] <= ILEN_FLD - 1:
        e.idem += 1
        e.crecer(e.demfil, e.idem, "")
        for nom, v in (("l_tiffdebug", False), ("l_demcheck", False),
                       ("l_userelevunits", False), ("chr_userelevunits", "           "),
                       ("userelevunits", 0), ("userdci", 0.0), ("l_nedskip", False)):
            e.crecer(getattr(e, nom), e.idem, v)
        e.demfil[e.idem] = e.runst1[e.locb[3] - 1:e.loce[3]]
    else:
        e.errhdl(e.path, m, "E", "210", _i8(ILEN_FLD))
        return
    i = e.idem
    if e.ifc >= 4:
        if td == "DEM" and feq(e.field[4], "CHECK"):
            e.l_demcheck[i] = True
        elif td == "DEM":
            e.errhdl(e.path, m, "E", "203", "CHECK")
            return
        elif td == "NED" and feq(e.field[4], "TIFFDEBUG"):
            e.l_tiffdebug[i] = True
            if e.ifc == 5:
                u = e.field[5].rstrip()
                if u in _UNIDADES:
                    e.l_userelevunits[i] = True
                    e.chr_userelevunits[i] = fx(e.field[5], 11)
                    e.userelevunits[i], e.userdci[i] = _UNIDADES[u]
                else:
                    e.errhdl(e.path, m, "E", "203", "ElevUnit")
        else:
            e.errhdl(e.path, m, "E", "203", " TIFFDBG")
            return
    else:
        e.l_demcheck[i] = False
        e.l_tiffdebug[i] = False
        e.l_userelevunits[i] = False
    # El original compara nombre Y unidad lógica; la unidad siempre difiere, así que un
    # nombre repetido da el error 550 y el fichero no se abre.
    for j in range(1, i):
        if feq(e.demfil[i], e.demfil[j]):
            e.errhdl(e.path, m, "E", "550", f"DEM#{min(i, 9999):4d}")
            return
    if os.path.isfile(e.demfil[i].rstrip()):
        e.numdem += 1
    else:
        e.errhdl(e.path, m, "E", "500", f"DEM#{min(i, 9999):4d}")


def _rango_zonas(e):
    m = "DOMAIN"
    zmin, zmax = abs(e.zonmin), abs(e.zonmax)
    cruce = (zmin == 1 and zmax == 60) or (zmin == 60 and zmax == 1)
    if abs(zmax - zmin) > 1 and not cruce:
        e.errhdl(e.path, m, "E", "232", f"{e.zonmin:3d}  {e.zonmax:3d}")
    elif cruce:
        e.gotdomflg = False
        e.errhdl(e.path, m, "W", "246", e.keywrd)


def _domain(e):
    m = "DOMAIN"
    k = kw(e)
    if k == "DOMAINXY":
        e.domtyp = "UTM"
        if e.ifc == 8:
            for i, nom in ((3, "xdmin"), (4, "ydmin"), (5, "zonmin"), (6, "xdmax"),
                           (7, "ydmax"), (8, "zonmax")):
                if nom.startswith("zon"):
                    arg, idum = _num(e, i, getattr(e, "_domain_arg", 0.0))
                    e._domain_arg = arg
                    setattr(e, nom, nint(arg))
                else:
                    v, idum = _dbl(e, i, getattr(e, nom))
                    setattr(e, nom, v)
                if idum == -1:
                    e.errhdl(e.path, m, "E", "208", e.keywrd)
                    return
        elif e.ifc > 8:
            e.errhdl(e.path, m, "E", "202", e.keywrd)
        else:
            e.errhdl(e.path, m, "E", "200", e.keywrd)
        e.gotdomflg = True
        _rango_zonas(e)
    elif k == "DOMAINLL":
        e.domtyp = "LAT"
        if e.ifc == 6:
            for i, nom in ((3, "xdmin"), (4, "ydmin"), (5, "xdmax"), (6, "ydmax")):
                v, idum = _dbl(e, i, getattr(e, nom))
                setattr(e, nom, v)
                if idum == -1:
                    e.errhdl(e.path, m, "E", "208", e.keywrd)
                    return
        elif e.ifc > 6:
            e.errhdl(e.path, m, "E", "202", e.keywrd)
        else:
            e.errhdl(e.path, m, "E", "200", e.keywrd)
        e.zonmin = utm_zona(e.xdmin)
        if e.ydmin < 0.0:
            e.zonmin = -1 * e.zonmin
        e.zonmax = utm_zona(e.xdmax)
        if e.ydmax < 0.0:
            e.zonmax = -1 * e.zonmax
        e.gotdomflg = True
        _rango_zonas(e)


def _anchor(e):
    m = "ANCHOR"
    if e.ifc == 8:
        for i, nom in ((3, "xauser"), (4, "yauser"), (5, "xaterr"), (6, "yaterr")):
            v, idum = _dbl(e, i, getattr(e, nom))
            setattr(e, nom, v)
            if idum == -1:
                e.errhdl(e.path, m, "E", "208", e.keywrd)
                return
        for i, nom in ((7, "zaterr"), (8, "nada")):
            arg, idum = _num(e, i, getattr(e, "_anchor_arg", 0.0))
            e._anchor_arg = arg
            setattr(e, nom, nint(arg))
            if idum == -1:
                e.errhdl(e.path, m, "E", "208", e.keywrd)
                return
    elif e.ifc > 9:
        e.errhdl(e.path, m, "E", "202", e.keywrd)
    else:
        e.errhdl(e.path, m, "E", "200", e.keywrd)


def _terrht(e):
    m = "TERRHT"
    if e.ifc == 3:
        if feq(e.field[3], "EXTRACT"):
            e.extract = True
        elif feq(e.field[3], "PROVIDED"):
            e.extract = False
        else:
            e.errhdl(e.path, m, "E", "203", e.keywrd)
    elif e.ifc > 3:
        e.errhdl(e.path, m, "E", "202", e.keywrd)
    else:
        e.errhdl(e.path, m, "E", "200", e.keywrd)


def _flagdf(e):
    m = "FLAGDF"
    e.flgpol = True
    e.l_flgdf = False
    if e.ifc == 3:
        e.zflg, idum = _dbl(e, 3, e.zflg)
        if idum == -1:
            e.errhdl(e.path, m, "E", "208", e.keywrd)
        if e.zflg >= 0.0 and idum == 1:
            e.l_flgdf = True
            for i in range(1, e.nrec + 1):
                e.azflag[i] = e.zflg
        elif e.zflg < 0.0:
            e.errhdl(e.path, m, "E", "209", "ZFLAG")
        elif idum != 1:
            e.errhdl(e.path, m, "E", "208", e.keywrd)
        else:
            e.errhdl(e.path, m, "E", "203", e.keywrd)
    elif e.ifc > 3:
        e.errhdl(e.path, m, "E", "202", e.keywrd)
    else:
        e.errhdl(e.path, m, "W", "205", "ZFLAG=0.")


def _runnot(e):
    m = "RUNNOT"
    if e.ifc == 3:
        if feq(e.field[3], "RUN"):
            e.run = True
        elif feq(e.field[3], "NOT"):
            e.run = False
        else:
            e.errhdl(e.path, m, "E", "203", e.keywrd)
    elif e.ifc > 3:
        e.errhdl(e.path, m, "E", "202", e.keywrd)
    else:
        e.errhdl(e.path, m, "E", "200", e.keywrd)


def _debopt(e):
    m = "DEBOPT"
    if e.ifc < 3:
        e.errhdl(e.path, m, "E", "200", e.keywrd)
        return
    if e.ifc > 5:
        e.errhdl(e.path, m, "E", "202", e.keywrd)
        return
    for i in range(3, e.ifc + 1):
        kopt = fx(e.field[i], 8).rstrip()
        if kopt == "HILL":
            e.hilldbg = True
        elif kopt == "RECEPTOR":
            e.recdbg = True
        elif kopt == "SOURCE":
            e.srcdbg = True
        elif kopt == "ALL":
            e.hilldbg = e.recdbg = e.srcdbg = True
        else:
            e.errhdl(e.path, m, "E", "203", e.keywrd)


def _nadgrids(e):
    m = "NADGRIDS"
    if e.ifc < 3:
        e.errhdl(e.path, m, "E", "200", e.keywrd)
        return
    if e.ifc > 4:
        e.errhdl(e.path, m, "E", "202", e.keywrd)
        return
    if e.loce[3] - e.locb[3] <= ILEN_FLD - 1:
        e.nadgrid_path = e.runst1[e.locb[3] - 1:e.loce[3]]
        e.nadpath = True
    else:
        e.errhdl(e.path, m, "E", "210", _i8(ILEN_FLD))


# =============================================================================== SO
def socard(e):
    m = "SOCARD"
    k = kw(e)
    s = e.isstat
    if k == "STARTING":
        e.numsrc = 0
        s[1] += 1
        if s[1] != 1:
            e.errhdl(e.path, m, "E", "135", e.keywrd)
    elif k == "LOCATION":
        s[2] += 1
        _soloca(e)
    elif k == "SRCPARAM":
        e.errhdl(e.path, m, "W", "112", "ignored ")
    elif k == "ELEVUNIT":
        s[15] += 1
        if s[15] != 1:
            e.errhdl(e.path, m, "E", "135", e.keywrd)
        elif e.numsrc > 0:
            e.errhdl(e.path, m, "E", "152", e.path)
        else:
            if e.ifc == 3:
                if feq(e.field[3], "METERS"):
                    e.soelev = "METERS"
                elif feq(e.field[3], "FEET"):
                    e.soelev = "FEET"
                else:
                    e.errhdl(e.path, "SOELUN", "E", "203", " SO_ELEV")
            elif e.ifc > 3:
                e.errhdl(e.path, "SOELUN", "E", "202", e.keywrd)
            else:
                e.errhdl(e.path, "SOELUN", "E", "200", "ElevUnit")
    elif k == "INCLUDED":
        s[18] += 1
        e.ilsave = e.iline
        includ(e)
        e.iline = e.ilsave
    elif k == "FINISHED":
        s[20] += 1
        if s[20] != 1:
            e.errhdl(e.path, m, "E", "135", e.keywrd)
        if s[1] == 0:
            e.errhdl(e.path, m, "E", "130", "STARTING")
        if s[2] == 0:
            e.errhdl(e.path, m, "E", "130", "LOCATION")
    else:
        e.errhdl(e.path, m, "E", "110", e.keywrd)


def sindex(arr, n, elem):
    for i in range(1, n + 1):
        if feq(elem, arr[i]):
            return i, True
    return 0, False


def _soloca(e):
    m = "SOLOCA"
    if e.ifc <= 2:
        e.errhdl(e.path, m, "E", "200", e.keywrd)
        return
    if e.ifc < 6:
        e.errhdl(e.path, m, "E", "201", e.keywrd)
        return
    if e.ifc > 10:
        e.errhdl(e.path, m, "E", "202", e.keywrd)
        return
    if e.loce[3] - e.locb[3] <= 11:
        soid = fx(e.field[3], 12)
    else:
        e.errhdl(e.path, m, "E", "206", e.field[3][:12])
        return
    _, found = sindex(e.srcid, e.nsrc, soid)
    if found:
        e.errhdl(e.path, m, "E", "377", soid)
        return
    e.isrc_soloca += 1
    i = e.isrc_soloca
    if i > e.nsrc:
        e.errhdl(e.path, m, "E", "217", _i8(e.nsrc))
        return
    e.srcid[i] = fx(e.field[3], 12)
    e.srctyp[i] = fx(e.field[4], 8)
    st = e.srctyp[i].rstrip()
    if st in ("OPENPIT", "OPEN_PIT", "OPEN-PIT"):
        e.srctyp[i] = fx("OPENPIT", 8)
        st = "OPENPIT"
    if st in ("RLINE", "BUOYLINE"):
        if e.ifc > 9:
            e.errhdl(e.path, m, "E", "202", e.keywrd)
            return
        elif e.ifc < 8:
            e.errhdl(e.path, m, "E", "201", e.keywrd)
            return
    elif st == "LINE":
        if e.ifc > 10:
            e.errhdl(e.path, m, "E", "202", e.keywrd)
            return
        elif e.ifc < 9:
            e.errhdl(e.path, m, "E", "201", e.keywrd)
            return
    elif e.ifc > 7:
        e.errhdl(e.path, m, "E", "202", e.keywrd)
        return

    def dbl(j, previo):
        return stodbl(e.field[j], 40, previo)

    def elev_fuente(j):
        if e.ifc == j:
            e.azs[i], imit = dbl(j, e.azs[i])
            if imit != 1:
                e.errhdl(e.path, m, "E", "208", e.keywrd)
            if e.soelev == "FEET":
                e.azs[i] = e.azs[i] * 0.3048
        else:
            e.azs[i] = 0.0
            if not e.extract:
                e.errhdl(e.path, m, "W", "205", "ZS = 0.0")

    if st in ("POINT", "POINTCAP", "POINTHOR", "VOLUME", "AREA", "AREAPOLY", "AREACIRC", "OPENPIT"):
        e.axs[i], imit = dbl(5, e.axs[i])
        if imit != 1:
            e.errhdl(e.path, m, "E", "208", e.keywrd)
        e.ays[i], imit = dbl(6, e.ays[i])
        if imit != 1:
            e.errhdl(e.path, m, "E", "208", e.keywrd)
        elev_fuente(7)
    elif st in ("RLINE", "BUOYLINE"):
        e.ax1s[i], imit = dbl(5, e.ax1s[i])
        e.ax2s[i], imit = dbl(7, e.ax2s[i])
        if imit != 1:
            e.errhdl(e.path, m, "E", "208", e.keywrd)
        e.ay1s[i], imit = dbl(6, e.ay1s[i])
        e.ay2s[i], imit = dbl(8, e.ay2s[i])
        if imit != 1:
            e.errhdl(e.path, m, "E", "208", e.keywrd)
        e.axs[i] = (e.ax1s[i] + e.ax2s[i]) / 2
        e.ays[i] = (e.ay1s[i] + e.ay2s[i]) / 2
        elev_fuente(9)
    elif st == "LINE":
        import math
        e.ax1s[i], imit = dbl(5, e.ax1s[i])
        e.ax2s[i], imit = dbl(7, e.ax2s[i])
        if imit != 1:
            e.errhdl(e.path, m, "E", "208", e.keywrd)
        e.ay1s[i], imit = dbl(6, e.ay1s[i])
        e.ay2s[i], imit = dbl(8, e.ay2s[i])
        if e.ifc >= 9:
            e.aws[i], imit = dbl(9, e.aws[i])
            if imit != 1:
                e.errhdl(e.path, m, "E", "208", e.keywrd)
            ldx = e.ax2s[i] - e.ax1s[i]
            ldy = e.ay2s[i] - e.ay1s[i]
            e.axs[i] = (e.ax1s[i] + e.ax2s[i]) * 0.5
            e.ays[i] = (e.ay1s[i] + e.ay2s[i]) * 0.5
            lxinit = e.aws[i]
            langle = math.atan2(ldx, ldy) * e.rtodeg
            lx1 = e.ax1s[i] - (lxinit / 2.0) * math.cos(langle * e.dtorad)
            ly1 = e.ay1s[i] + (lxinit / 2.0) * math.sin(langle * e.dtorad)
            e.axs[i] = lx1
            e.ays[i] = ly1
        elev_fuente(10)
    else:
        e.errhdl(e.path, m, "E", "203", " SRCTYP ")
        return
    e.numsrc += 1


# =============================================================================== RE
def recard(e):
    m = "RECARD"
    k = kw(e)
    r = e.irstat
    if k == "STARTING":
        e.innet = 0
        e.numrec = 0
        e.numarc = 0
        e.irxr = e.iryr = e.irze = e.irhz = e.irzf = 0
        e.ista = False
        r[1] += 1
        if r[1] != 1:
            e.errhdl(e.path, m, "E", "135", e.keywrd)
        for v in (e.zetmp1, e.zetmp2, e.zftmp1, e.zftmp2):
            v[:] = [0.0] * len(v)
    elif k == "GRIDCART":
        r[2] += 1
        recart(e)
    elif k == "GRIDPOLR":
        r[3] += 1
        repolr(e)
    elif k == "DISCCART":
        r[4] += 1
        discar(e)
    elif k == "DISCPOLR":
        r[5] += 1
        dispol(e)
    elif k == "EVALCART":
        r[8] += 1
        evcart(e)
    elif k == "ELEVUNIT":
        r[9] += 1
        if r[9] != 1:
            e.errhdl(e.path, m, "E", "135", e.keywrd)
        elif r[2] > 0 or r[3] > 0 or r[4] > 0 or r[5] > 0 or r[8] > 0:
            e.errhdl(e.path, m, "E", "152", e.path)
        else:
            if e.ifc == 3:
                if feq(e.field[3], "METERS"):
                    e.reelev = "METERS"
                elif feq(e.field[3], "FEET"):
                    e.reelev = "FEET"
                else:
                    e.errhdl(e.path, "REELUN", "E", "203", "RE_ELEV")
            elif e.ifc > 3:
                e.errhdl(e.path, "REELUN", "E", "202", e.keywrd)
            else:
                e.errhdl(e.path, "REELUN", "E", "200", "ElevUnit")
    elif k == "INCLUDED":
        r[12] += 1
        e.ilsave = e.iline
        includ(e)
        e.iline = e.ilsave
    elif k == "FINISHED":
        r[20] += 1
        if r[20] != 1:
            e.errhdl(e.path, m, "E", "135", e.keywrd)
            return
        if r[1] == 0:
            e.errhdl(e.path, m, "E", "130", "STARTING")
        if r[2] == 0 and r[3] == 0 and r[4] == 0 and r[5] == 0 and r[8] == 0:
            e.errhdl(e.path, m, "E", "185", "NUMREC=0")
        if e.ista:
            e.errhdl(e.path, m, "E", "175", e.pnetid)
        e.numrec = e.irxr
        if e.numrec == 0:
            e.errhdl(e.path, m, "E", "227", "NUMREC=0")
        if not e.flgpol:
            for i in range(1, e.numrec + 1):
                e.azflag[i] = 0.0
    else:
        e.errhdl(e.path, m, "E", "110", e.keywrd)


def includ(e):
    """INCLUD: procesa un fichero INCLUDED (solo vías SO y RE)."""
    m = "INCLUD"
    e.iline = 1
    lineas = []
    if e.ifc == 3:
        nombre = _abrir_incluido(e)
        if nombre is None:
            e.errhdl(e.path, m, "E", "210", _i8(ILEN_FLD))
            return
        try:
            lineas = leer_lineas(nombre)
        except OSError:
            e.errhdl(e.path, m, "E", "500", "INCFILE ")
            return
    elif e.ifc > 4:
        e.errhdl(e.path, m, "E", "202", e.keywrd)
    else:
        e.errhdl(e.path, m, "E", "200", e.keywrd)
    for linea in lineas:
        e.iline += 1
        e.ilreal_inc += 1
        cargar(e, linea)
        define(e)
        if e.ilreal_inc == 1:
            e.iline -= 1
        getfld(e)
        if e.bline:
            continue
        if feq(e.field[1], "NO") and feq(e.field[2], "ECHO"):
            continue
        if expath(e, e.field[1]):
            e.errhdl(e.ppath, m, "E", "100", e.path)
            e.path = e.ppath
            continue
        elif e.path == "**":
            continue
        if exkey(e, e.field[2]):
            e.errhdl(e.path, m, "E", "105", e.keywrd)
            e.pkeywd = e.keywrd
            continue
        k = kw(e)
        if k not in ("STARTING", "FINISHED"):
            setord(e)
        if k == "STARTING":
            e.errhdl(e.path, m, "E", "140", e.keywrd)
        elif k == "INCLUDED":
            e.errhdl(e.path, m, "E", "135", e.keywrd)
        elif k == "FINISHED":
            e.errhdl(e.path, m, "E", "140", e.keywrd)
        elif e.path == "SO":
            socard(e)
        elif e.path == "RE":
            recard(e)
        e.pkeywd = e.keywrd
    e.iline += 1
    e.ilreal_inc += 1


def _netid(e, claves, m):
    """Cabecera común de RECART/REPOLR. Devuelve False si hay que salir."""
    e.netidt = fx(e.field[3], 8)
    if not e.newid and (e.netidt.rstrip() == "" or e.netidt.rstrip() in claves):
        e.netidt = e.pnetid
        e.ktype = fx(e.field[3], 5)
    elif not e.newid and e.netidt == e.pnetid:
        e.ktype = fx(e.field[4], 5)
    elif e.newid and e.netidt.rstrip() != "":
        e.newid = False
        e.ktype = fx(e.field[4], 5)
        e.innet += 1
        if e.innet > e.nnet:
            e.errhdl(e.path, m, "E", "224", _i8(e.nnet))
            e.recerr = True
            return False
        return "nueva"
    else:
        e.errhdl(e.path, m, "E", "170", e.pnetid)
        e.recerr = True
        return False
    return True


def _fin_red(e, m):
    """Comprobaciones comunes al END de una red (RECART/REPOLR, tras SETCAR/SETPOL)."""
    if not e.extract and e.ievset == 0:
        e.errhdl(e.path, m, "W", "214", e.netidt)
        e.irze = e.irxr
        e.irhz = e.irze
    if e.flgpol and not e.l_flgdf and e.ifgset == 0:
        e.errhdl(e.path, m, "W", "216", e.netidt)
        e.irzf = e.irxr
    elif not e.flgpol and e.ifgset != 0:
        e.errhdl(e.path, m, "W", "215", e.netidt)
        e.irzf = e.irxr
    else:
        e.irzf = e.irxr
    if not e.extract and e.ievset != 0:
        if e.icount * e.jcount != e.ize:
            e.errhdl(e.path, m, "E", "218", "ELEV")
    if e.flgpol and e.ifgset != 0:
        if e.icount * e.jcount != e.izf:
            e.errhdl(e.path, m, "E", "218", "FLAG")
    if e.extract and e.ievset != 0:
        e.errhdl(e.path, m, "W", "214", e.netidt)


def _sta(e, m):
    e.ista = True
    e.iend = False
    e.newid = False
    e.recerr = False
    e.icount = e.jcount = 0
    e.ize = e.izf = 0
    e.idc1 = e.irxr
    for i in range(1, e.innet):
        if feq(e.field[3], e.ntid[i]):
            e.errhdl(e.path, m, "W", "252", e.ntid[i])


def recart(e):
    m = "RECART"
    if e.ifc < 3:
        e.errhdl(e.path, m, "E", "200", e.keywrd)
        return
    r = _netid(e, ("XYINC", "XPNTS", "YPNTS", "ELEV", "FLAG", "END"), m)
    if r is False:
        return
    if r == "nueva":
        e.incset = e.ixyset = e.ievset = e.ifgset = 0
    kt = e.ktype.rstrip()
    if kt == "STA":
        _sta(e, m)
    elif kt == "XYINC":
        if not e.ista:
            e.errhdl(e.path, m, "E", "200", "  STA   ")
        if e.ixyset != 0:
            e.errhdl(e.path, m, "E", "180", e.netidt)
        _gencar(e)
        e.incset += 1
    elif kt in ("XPNTS", "YPNTS"):
        if not e.ista:
            e.errhdl(e.path, m, "E", "200", "  STA   ")
        if e.incset != 0:
            e.errhdl(e.path, m, "E", "180", e.netidt)
        _xypnts(e)
        e.ixyset += 1
    elif kt == "ELEV":
        if not e.ista:
            e.errhdl(e.path, m, "E", "200", "  STA   ")
        _terhgt(e)
        e.ievset += 1
    elif kt == "FLAG":
        if not e.ista:
            e.errhdl(e.path, m, "E", "200", "  STA   ")
        if e.flgpol:
            _flghgt(e)
            e.ifgset += 1
    elif kt == "END":
        e.iend = True
        if not e.ista:
            e.errhdl(e.path, m, "E", "200", "  STA   ")
        elif not e.recerr:
            _setred(e, "GC")
        e.ista = False
        e.newid = True
        if e.ixyset == 0 and e.incset == 0:
            e.errhdl(e.path, m, "E", "212", e.netidt)
        _fin_red(e, m)
    else:
        e.errhdl(e.path, m, "E", "170", e.netidt)
        e.recerr = True
        return
    e.pnetid = e.netidt


def _gencar(e):
    m = "GENCAR"
    _isc(e, "XYINC")
    if e.ifc == e.isc - 1:
        e.errhdl(e.path, m, "E", "200", e.keywrd)
        e.recerr = True
        return
    if e.ifc > e.isc + 5:
        e.errhdl(e.path, m, "E", "202", e.ktype)
        e.recerr = True
        return
    if e.ifc < e.isc + 5:
        e.errhdl(e.path, m, "E", "201", e.ktype)
        e.recerr = True
        return
    prev = getattr(e, "_gencar_t", [0.0] * 7)
    t = list(prev)
    error = False
    for k in range(1, 7):
        t[k], e.mitl = _dbl(e, e.isc + k - 1, prev[k])
        if e.mitl == -1:
            e.errhdl(e.path, m, "E", "208", e.keywrd)
            error = True
            e.recerr = True
    e._gencar_t = t
    if error:
        return
    e.xint = t[1]
    e.icount = nint(t[2])
    e.xdelta = t[3]
    e.yint = t[4]
    e.jcount = nint(t[5])
    e.ydelta = t[6]
    if e.icount <= e.ixm:
        for i in range(1, e.icount + 1):
            e.xcoord[e.innet][i] = e.xint + e.xdelta * float(i - 1)
    else:
        e.errhdl(e.path, m, "E", "225", _i8(e.ixm))
        e.recerr = True
    if e.jcount <= e.iym:
        for j in range(1, e.jcount + 1):
            e.ycoord[e.innet][j] = e.yint + e.ydelta * float(j - 1)
    else:
        e.errhdl(e.path, m, "E", "226", _i8(e.iym))
        e.recerr = True


def _xypnts(e):
    m = "XYPNTS"
    kt = e.ktype.rstrip()
    _isc(e, kt)
    if e.ifc == e.isc - 1:
        e.errhdl(e.path, m, "E", "200", e.keywrd)
        e.recerr = True
        return
    xs = kt == "XPNTS"
    n = e.icount if xs else e.jcount
    lim = e.ixm if xs else e.iym
    coord = e.xcoord[e.innet] if xs else e.ycoord[e.innet]
    for i in range(e.isc, e.ifc + 1):
        e.dnum, imit = _dbl(e, i, e.dnum)
        if imit == -1:
            e.errhdl(e.path, m, "E", "208", e.keywrd)
            e.recerr = True
        n += 1
        if n <= lim:
            coord[n] = e.dnum
            for j in range(1, n):
                if e.dnum == coord[j]:
                    e.errhdl(e.path, m, "W", "250", e.netidt)
        else:
            e.errhdl(e.path, m, "E", "225" if xs else "226", _i8(lim))
            e.recerr = True
    if xs:
        e.icount = n
    else:
        e.jcount = n


def _sbyval(a1, a2, inx):
    """SBYVAL: ordenación por selección (estable como el original) de a1, arrastrando a2."""
    jc = 1
    while jc <= inx:
        vmin = a1[jc]
        imin = jc
        for i in range(jc, inx + 1):
            if a1[i] < vmin:
                imin = i
                vmin = a1[i]
        a1[jc], a1[imin] = a1[imin], a1[jc]
        a2[jc], a2[imin] = a2[imin], a2[jc]
        jc += 1


def _setred(e, tipo):
    """SETCAR (tipo 'GC') / SETPOL (tipo 'GP')."""
    import math
    m = "SETCAR" if tipo == "GC" else "SETPOL"
    if e.icount != 0 and e.jcount != 0:
        e.netsta[e.innet] = e.irxr + 1
        iset, jset = e.irxr, e.iryr
        for j in range(1, e.jcount + 1):
            for i in range(1, e.icount + 1):
                iset += 1
                jset += 1
                if iset > e.nrec:
                    e.errhdl(e.path, m, "E", "219", _i8(e.nrec))
                    return
                if e.icount > e.ixm:
                    e.errhdl(e.path, m, "E", "225", _i8(e.ixm))
                    return
                if e.jcount > e.iym:
                    e.errhdl(e.path, m, "E", "226", _i8(e.iym))
                    return
                if tipo == "GC":
                    e.axr[iset] = e.xcoord[e.innet][i]
                    e.ayr[jset] = e.ycoord[e.innet][j]
                else:
                    ytemp = e.ycoord[e.innet][j] * e.dtorad
                    e.axr[iset] = e.xint + e.xcoord[e.innet][i] * math.sin(ytemp)
                    e.ayr[jset] = e.yint + e.xcoord[e.innet][i] * math.cos(ytemp)
        e.irxr = iset
        e.iryr = jset
        if tipo == "GP":
            e.xorig[e.innet] = e.xint
            e.yorig[e.innet] = e.yint
        e.netend[e.innet] = e.irxr
        e.numxpt[e.innet] = e.icount
        e.numypt[e.innet] = e.jcount
        e.ntid[e.innet] = e.netidt
        e.nttyp[e.innet] = "GRIDCART" if tipo == "GC" else "GRIDPOLR"
    _sbyval(e.zetmp1, e.zetmp2, e.ize)
    iset = e.irze
    for i in range(1, e.ize + 1):
        iset += 1
        if iset > e.nrec:
            e.errhdl(e.path, m, "E", "219", _i8(e.nrec))
            return
        e.azelev[iset] = e.zetmp2[i]
    e.irze = iset
    e.irhz = e.irze
    _sbyval(e.zftmp1, e.zftmp2, e.izf)
    iset = e.irzf
    for i in range(1, e.izf + 1):
        iset += 1
        if iset > e.nrec:
            e.errhdl(e.path, m, "E", "219", _i8(e.nrec))
            return
        e.azflag[iset] = e.zftmp2[i]
    e.irzf = iset
    for i in range(e.idc1 + 1, e.irxr + 1):
        e.netid[i] = e.netidt
        e.rectyp[i] = tipo


def repolr(e):
    m = "REPOLR"
    if e.ifc < 3:
        e.errhdl(e.path, m, "E", "200", e.keywrd)
        return
    r = _netid(e, ("ORIG", "DIST", "DDIR", "ELEV", "FLAG", "GDIR", "END"), m)
    if r is False:
        return
    if r == "nueva":
        e.iorset = e.ixrset = e.idrset = e.igrset = e.ievset = e.ifgset = 0
    kt = e.ktype.rstrip()
    if kt == "STA":
        _sta(e, m)
    elif kt == "ORIG":
        if not e.ista:
            e.errhdl(e.path, m, "E", "200", "  STA   ")
        if e.iorset != 0:
            e.errhdl(e.path, m, "E", "160", e.netidt)
        _polorg(e)
        e.iorset += 1
    elif kt == "DIST":
        if not e.ista:
            e.errhdl(e.path, m, "E", "200", "  STA   ")
        _poldst(e)
        e.ixrset += 1
    elif kt == "GDIR":
        if not e.ista:
            e.errhdl(e.path, m, "E", "200", "  STA   ")
        if e.idrset != 0:
            e.errhdl(e.path, m, "E", "180", e.netidt)
        _genpol(e)
        e.igrset += 1
    elif kt == "DDIR":
        if not e.ista:
            e.errhdl(e.path, m, "E", "200", "  STA   ")
        if e.igrset != 0:
            e.errhdl(e.path, m, "E", "180", e.netidt)
        _radrng(e)
        e.idrset += 1
    elif kt == "ELEV":
        if not e.ista:
            e.errhdl(e.path, m, "E", "200", "  STA   ")
        _terhgt(e)
        e.ievset += 1
    elif kt == "FLAG":
        if not e.ista:
            e.errhdl(e.path, m, "E", "200", "  STA   ")
        if e.flgpol:
            _flghgt(e)
            e.ifgset += 1
    elif kt == "END":
        e.iend = True
        if not e.ista:
            e.errhdl(e.path, m, "E", "200", "  STA   ")
        elif not e.recerr:
            _setred(e, "GP")
        e.ista = False
        e.newid = True
        if e.iorset == 0:
            e.errhdl(e.path, m, "W", "220", e.netidt)
            e.xint = 0.0
            e.yint = 0.0
        if e.ixrset == 0:
            e.errhdl(e.path, m, "E", "221", e.netidt)
        if e.igrset == 0 and e.idrset == 0:
            e.errhdl(e.path, m, "E", "222", e.netidt)
        _fin_red(e, m)
    else:
        e.errhdl(e.path, m, "E", "170", e.netidt)
        e.recerr = True
        return
    e.pnetid = e.netidt


def _polorg(e):
    m = "POLORG"
    _isc(e, "ORIG")
    if e.ifc == e.isc - 1:
        e.errhdl(e.path, m, "E", "200", e.keywrd)
        e.recerr = True
        return
    if e.ifc > e.isc + 1:
        e.errhdl(e.path, m, "E", "202", e.ktype)
        e.recerr = True
        return
    if e.ifc == e.isc:
        if e.loce[e.isc] - e.locb[e.isc] <= 11:
            soid = fx(e.field[e.isc], 12)
        else:
            e.errhdl(e.path, m, "E", "206", e.field[e.isc][:12])
            e.recerr = True
            return
        isdx, found = sindex(e.srcid, e.nsrc, soid)
        if not found:
            e.errhdl(e.path, m, "E", "375", e.keywrd)
            e.recerr = True
        else:
            e.xint = e.axs[isdx]
            e.yint = e.ays[isdx]
    else:
        e.xint, imut = _dbl(e, e.isc, e.xint)
        if imut == -1:
            e.errhdl(e.path, m, "E", "208", e.keywrd)
            e.recerr = True
        e.yint, imut = _dbl(e, e.isc + 1, e.yint)
        if imut == -1:
            e.errhdl(e.path, m, "E", "208", e.keywrd)
            e.recerr = True


def _poldst(e):
    m = "POLDST"
    _isc(e, "DIST")
    if e.ifc == e.isc - 1:
        e.errhdl(e.path, m, "E", "200", e.keywrd)
        e.recerr = True
        return
    n = e.icount
    coord = e.xcoord[e.innet]
    for i in range(e.isc, e.ifc + 1):
        e.dnum, imit = _dbl(e, i, e.dnum)
        if imit == -1:
            e.errhdl(e.path, m, "E", "208", e.keywrd)
            e.recerr = True
        n += 1
        if n <= e.ixm:
            coord[n] = e.dnum
            for j in range(1, n):
                if e.dnum == coord[j]:
                    e.errhdl(e.path, m, "W", "250", e.netidt)
        else:
            e.errhdl(e.path, m, "E", "225", _i8(e.ixm))
            e.recerr = True
    e.icount = n


def _genpol(e):
    m = "GENPOL"
    _isc(e, "GDIR")
    if e.ifc == e.isc - 1:
        e.errhdl(e.path, m, "E", "200", e.keywrd)
        e.recerr = True
        return
    if e.ifc < e.isc + 2:
        e.errhdl(e.path, m, "E", "201", e.ktype)
        e.recerr = True
        return
    if e.ifc > e.isc + 2:
        e.errhdl(e.path, m, "E", "202", e.ktype)
        e.recerr = True
        return
    prev = getattr(e, "_genpol_t", [0.0] * 4)
    t = list(prev)
    error = False
    for k in range(1, 4):
        t[k], e.mitl = _dbl(e, e.isc + k - 1, prev[k])
        if e.mitl == -1:
            e.errhdl(e.path, m, "E", "208", e.keywrd)
            e.recerr = True
            error = True
    e._genpol_t = t
    if error:
        return
    e.jcount = nint(t[1])
    dirini, dirinc = t[2], t[3]
    if e.jcount <= e.iym:
        for j in range(1, e.jcount + 1):
            y = dirini + dirinc * float(j - 1)
            if y > 360.0:
                y = y - 360.0
            elif y <= 0.0:
                y = y + 360.0
            e.ycoord[e.innet][j] = y
    else:
        e.errhdl(e.path, m, "E", "226", _i8(e.iym))
        e.recerr = True


def _radrng(e):
    m = "RADRNG"
    _isc(e, "DDIR")
    if e.ifc == e.isc - 1:
        e.errhdl(e.path, m, "E", "200", e.keywrd)
        e.recerr = True
        return
    n = e.jcount
    coord = e.ycoord[e.innet]
    for i in range(e.isc, e.ifc + 1):
        e.dnum, imit = _dbl(e, i, e.dnum)
        if imit == -1:
            e.errhdl(e.path, m, "E", "208", e.keywrd)
            e.recerr = True
        n += 1
        if n <= e.iym:
            v = e.dnum
            if v > 360.0:
                v = v - 360.0
            elif v <= 0.0:
                v = v + 360.0
            coord[n] = v
            for j in range(1, n):
                if e.dnum == coord[j]:
                    e.errhdl(e.path, m, "W", "250", e.netidt)
        else:
            e.errhdl(e.path, m, "E", "226", _i8(e.iym))
            e.recerr = True
    e.jcount = n


def _terhgt(e):
    m = "TERHGT"
    ize1 = e.ize + 1
    _isc(e, "ELEV")
    if e.ifc == e.isc - 1:
        e.errhdl(e.path, m, "E", "223", e.ktype)
        e.recerr = True
        return
    if e.ifc == e.isc:
        e.errhdl(e.path, m, "E", "200", e.keywrd)
        e.recerr = True
        return
    e.dnum, imit = _dbl(e, e.isc, e.dnum)
    if imit == -1:
        e.errhdl(e.path, m, "E", "208", e.keywrd)
        e.recerr = True
    row = e.dnum
    iset = e.ize
    for i in range(e.isc + 1, e.ifc + 1):
        e.dnum, imit = _dbl(e, i, e.dnum)
        if imit == -1:
            e.errhdl(e.path, m, "E", "208", e.keywrd)
            e.recerr = True
        for _ in range(imit):
            iset += 1
            e.crecer(e.zetmp1, iset)
            e.crecer(e.zetmp2, iset)
            e.zetmp1[iset] = row
            e.zetmp2[iset] = e.dnum
    e.ize = iset
    if e.reelev == "FEET":
        for i in range(ize1, e.ize + 1):
            e.zetmp2[i] = 0.3048 * e.zetmp2[i]


def _flghgt(e):
    import numpy as np
    m = "FLGHGT"
    _isc(e, "FLAG")
    if e.ifc == e.isc - 1:
        e.errhdl(e.path, m, "E", "223", e.ktype)
        e.recerr = True
        return
    if e.ifc == e.isc:
        e.errhdl(e.path, m, "E", "200", e.keywrd)
        e.recerr = True
        return
    e.dnum, imit = _dbl(e, e.isc, e.dnum)
    if imit == -1:
        e.errhdl(e.path, m, "E", "208", e.keywrd)
        e.recerr = True
    row = float(np.float32(e.dnum))          # ROW es REAL en FLGHGT
    iset = e.izf
    for i in range(e.isc + 1, e.ifc + 1):
        e.dnum, imit = _dbl(e, i, e.dnum)
        if imit == -1:
            e.errhdl(e.path, m, "E", "208", e.keywrd)
            e.recerr = True
        for _ in range(imit):
            iset += 1
            e.crecer(e.zftmp1, iset)
            e.crecer(e.zftmp2, iset)
            e.zftmp1[iset] = row
            e.zftmp2[iset] = e.dnum
    e.izf = iset


def _lleno(e, m):
    i1, i2, i3, i4, i5 = e.irxr, e.iryr, e.irze, e.irzf, e.irhz
    if e.nrec in (i1, i2, i3, i4, i5):
        e.errhdl(e.path, m, "E", "219", _i8(e.nrec))
        return None
    return i1, i2, i3, i4, i5


def _avanzar(e, i1, i2, i3, i4, i5):
    e.irxr, e.iryr, e.irze, e.irzf, e.irhz = i1 + 1, i2 + 1, i3 + 1, i4 + 1, i5 + 1


def discar(e):
    m = "DISCAR"
    ex, fp, ifc = e.extract, e.flgpol, e.ifc
    if ifc < 4:
        e.errhdl(e.path, m, "E", "200", e.keywrd)
        return
    if ifc > 6:
        e.errhdl(e.path, m, "E", "202", e.keywrd)
        return
    if not ex and fp and ifc < 6:
        e.errhdl(e.path, m, "W", "228", e.keywrd)
    elif (not ex or fp) and ifc < 5:
        e.errhdl(e.path, m, "W", "228", e.keywrd)
    elif not ex and not fp and ifc > 5:
        e.errhdl(e.path, m, "W", "229", e.keywrd)
    elif fp and ex and ifc > 5:
        e.errhdl(e.path, m, "W", "229", e.keywrd)
    elif ex and not fp and ifc > 4:
        e.errhdl(e.path, m, "W", "229", e.keywrd)
    idx = _lleno(e, m)
    if idx is None:
        return
    i1, i2, i3, i4, i5 = idx
    e.axr[i1 + 1], inum = _dbl(e, 3, e.axr[i1 + 1])
    if inum == -1:
        e.errhdl(e.path, m, "E", "208", e.keywrd)
    e.ayr[i2 + 1], inum = _dbl(e, 4, e.ayr[i2 + 1])
    if inum == -1:
        e.errhdl(e.path, m, "E", "208", e.keywrd)
    if not ex and fp:
        if ifc >= 5:
            e.dnum, inum = _dbl(e, 5, e.dnum)
            if inum == -1:
                e.errhdl(e.path, m, "E", "208", e.keywrd)
            else:
                e.azelev[i3 + 1] = e.dnum
            if ifc >= 6:
                e.dnum, inum = _dbl(e, 6, e.dnum)
                if inum == -1:
                    e.errhdl(e.path, m, "E", "208", e.keywrd)
                else:
                    e.azflag[i3 + 1] = e.dnum          # (sic) índice I3 en el original
        if ifc == 5:
            e.azflag[i4 + 1] = e.zflg
        elif ifc < 5:
            e.azelev[i3 + 1] = 0.0
            e.azflag[i4 + 1] = e.zflg
    elif not ex and not fp:
        if ifc >= 5:
            e.dnum, inum = _dbl(e, 5, e.dnum)
            if inum == -1:
                e.errhdl(e.path, m, "E", "208", e.keywrd)
            else:
                e.azelev[i3 + 1] = e.dnum
        elif ifc < 5:
            e.azelev[i3 + 1] = 0.0
    elif fp and ex:
        if ifc == 5:
            e.dnum, inum = _dbl(e, 5, e.dnum)
            if inum == -1:
                e.errhdl(e.path, m, "E", "208", e.keywrd)
            else:
                e.azflag[i4 + 1] = e.dnum
        elif ifc > 5:
            e.dnum, inum = _dbl(e, 6, e.dnum)
            if inum == -1:
                e.errhdl(e.path, m, "E", "208", e.keywrd)
            else:
                e.azflag[i4 + 1] = e.dnum
        else:
            e.azflag[i4 + 1] = e.zflg if e.l_flgdf else 0.0
    if e.reelev == "FEET":
        e.azelev[i3 + 1] = 0.3048 * e.azelev[i3 + 1]
    _avanzar(e, i1, i2, i3, i4, i5)
    e.netid[e.irxr] = "        "
    e.rectyp[e.irxr] = "DC"


def dispol(e):
    import math
    m = "DISPOL"
    ex, fp, ifc = e.extract, e.flgpol, e.ifc
    if ifc < 5:
        e.errhdl(e.path, m, "E", "200", e.keywrd)
        return
    if ifc > 7:
        e.errhdl(e.path, m, "E", "202", e.keywrd)
        return
    if not ex and fp and ifc < 7:
        e.errhdl(e.path, m, "W", "228", e.keywrd)
    elif (not ex or fp) and ifc < 6:
        e.errhdl(e.path, m, "W", "228", e.keywrd)
    elif not ex and not fp and ifc > 6:
        e.errhdl(e.path, m, "W", "229", e.keywrd)
    elif fp and ex and ifc > 6:
        e.errhdl(e.path, m, "W", "229", e.keywrd)
    elif ex and not fp and ifc > 5:
        e.errhdl(e.path, m, "W", "229", e.keywrd)
    idx = _lleno(e, m)
    if idx is None:
        return
    i1, i2, i3, i4, i5 = idx
    if e.loce[3] - e.locb[3] <= 11:
        soid = fx(e.field[3], 12)
    else:
        e.errhdl(e.path, m, "E", "206", e.field[3][:12])
        e.recerr = True
        return
    rng, imit = _dbl(e, 4, getattr(e, "_dispol_range", 0.0))
    e._dispol_range = rng
    if imit == -1:
        e.errhdl(e.path, m, "E", "208", e.keywrd)
    direct, imit = _dbl(e, 5, getattr(e, "_dispol_direct", 0.0))
    if imit == -1:
        e.errhdl(e.path, m, "E", "208", e.keywrd)
    elif direct > 360.0:
        direct = direct - 360.0
    elif direct <= 0.0:
        direct = direct + 360.0
    e._dispol_direct = direct
    if not ex and fp:
        if ifc >= 6:
            e.dnum, inum = _dbl(e, 6, e.dnum)
            if inum == -1:
                e.errhdl(e.path, m, "E", "208", e.keywrd)
            else:
                e.azelev[i3 + 1] = e.dnum
        if ifc == 7:
            e.dnum, inum = _dbl(e, 7, e.dnum)
            if inum == -1:
                e.errhdl(e.path, m, "E", "208", e.keywrd)
            else:
                e.azflag[i4 + 1] = e.dnum
    elif not ex and not fp:
        if ifc >= 6:
            e.dnum, inum = _dbl(e, 6, e.dnum)
            if inum == -1:
                e.errhdl(e.path, m, "E", "208", e.keywrd)
            else:
                e.azelev[i3 + 1] = e.dnum
    elif fp and ex:
        if ifc in (6, 7):
            e.dnum, inum = _dbl(e, ifc, e.dnum)
            if inum == -1:
                e.errhdl(e.path, m, "E", "208", e.keywrd)
            else:
                e.azflag[i4 + 1] = e.dnum
    isdx, found = sindex(e.srcid, e.nsrc, soid)
    if not found:
        e.errhdl(e.path, m, "E", "375", e.keywrd)
    else:
        darg = direct * e.dtorad
        e.axr[i1 + 1] = e.axs[isdx] + rng * math.sin(darg)
        e.ayr[i2 + 1] = e.ays[isdx] + rng * math.cos(darg)
        if e.reelev == "FEET":
            e.azelev[i3 + 1] = 0.3048 * e.azelev[i3 + 1]
        _avanzar(e, i1, i2, i3, i4, i5)
        e.netid[e.irxr] = "        "
        e.rectyp[e.irxr] = "DP"
        e.iref[e.irxr] = isdx


def evcart(e):
    m = "EVCART"
    if e.ifc < 7:
        e.errhdl(e.path, m, "E", "201", e.keywrd)
        return
    if e.ifc > 8:
        e.errhdl(e.path, m, "E", "202", e.keywrd)
        return
    idx = _lleno(e, m)
    if idx is None:
        return
    i1, i2, i3, i4, i5 = idx
    e.axr[i1 + 1], inum = _dbl(e, 3, e.axr[i1 + 1])
    if inum == -1:
        e.errhdl(e.path, m, "E", "208", e.keywrd)
    e.ayr[i2 + 1], inum = _dbl(e, 4, e.ayr[i2 + 1])
    if inum == -1:
        e.errhdl(e.path, m, "E", "208", e.keywrd)
    e.dnum, inum = _dbl(e, 5, e.dnum)
    if inum == -1:
        e.errhdl(e.path, m, "E", "208", e.keywrd)
    else:
        e.azelev[i3 + 1] = e.dnum
    e.dnum, inum = _dbl(e, 6, e.dnum)
    if inum == -1:
        e.errhdl(e.path, m, "E", "208", e.keywrd)
    else:
        e.azflag[i4 + 1] = e.dnum
    if not e.flgpol:
        e.errhdl(e.path, m, "W", "216", "ZFLAG=0.")
    found = False
    for j in range(1, e.numarc + 1):
        if feq(e.field[7], e.arcid[j]):
            found = True
            e.ndxarc[i1 + 1] = j
            break
    if not found:
        e.numarc += 1
        if e.numarc > e.narc:
            e.errhdl(e.path, m, "E", "254", _i8(e.narc))
            return
        e.arcid[e.numarc] = fx(e.field[7], 8)
        e.ndxarc[i1 + 1] = e.numarc
    e.recnam[i1 + 1] = fx(e.field[8], 8) if e.ifc == 8 else "        "
    if e.reelev == "FEET":
        e.azelev[i3 + 1] = 0.3048 * e.azelev[i3 + 1]
    _avanzar(e, i1, i2, i3, i4, i5)
    e.netid[e.irxr] = "        "
    e.rectyp[e.irxr] = "DC"


# =============================================================================== OU
def oucard(e):
    m = "OUCARD"
    k = kw(e)
    o = e.iostat
    if k == "STARTING":
        o[1] += 1
    elif k == "RECEPTOR":
        o[2] += 1
        if o[2] != 1:
            e.errhdl(e.path, m, "E", "135", e.keywrd)
        elif e.numrec == 0:
            e.errhdl(e.path, m, "E", "192", "        ")
        else:
            _oufich(e, "OURECF", "recfil", "RECOUT  ")
    elif k == "SOURCLOC":
        o[3] += 1
        if o[3] != 1:
            e.errhdl(e.path, m, "E", "135", e.keywrd)
        elif e.numsrc == 0:
            e.errhdl(e.path, m, "E", "190", "        ")
        else:
            _oufich(e, "OUSRCF", "srcfil", "SRCOUT  ")
    elif k == "DEBUGHIL":
        o[4] += 1
        if o[4] != 1:
            e.errhdl(e.path, m, "E", "135", e.keywrd)
        elif not e.hilldbg:
            e.errhdl(e.path, m, "E", "150", e.keywrd)
        else:
            _oudeb(e, "OUHILDB", ("calchc_file",))
    elif k == "DEBUGREC":
        o[5] += 1
        if o[5] != 1:
            e.errhdl(e.path, m, "E", "135", e.keywrd)
        elif not e.recdbg:
            e.errhdl(e.path, m, "E", "150", e.keywrd)
        else:
            _oudeb(e, "OURECDB", ("recdet_file", "recndem_file", "recelv_file"))
    elif k == "DEBUGSRC":
        o[6] += 1
        if o[6] != 1:
            e.errhdl(e.path, m, "E", "135", e.keywrd)
        elif not e.srcdbg:
            e.errhdl(e.path, m, "E", "150", e.keywrd)
        else:
            _oudeb(e, "OUSRCDB", ("srcdet_file", "srcndem_file", "srcelv_file"))
    elif k == "FINISHED":
        o[20] += 1
        if o[1] == 0:
            e.errhdl(e.path, m, "E", "130", "STARTING")
        if o[2] == 0 and e.numrec > 0 and e.extract:
            e.errhdl(e.path, m, "W", "193", _i8(e.numrec))
        if o[3] == 0 and e.numsrc > 0 and e.extract:
            e.errhdl(e.path, m, "W", "191", _i8(e.numsrc))
        if o[2] == 0 and o[3] == 0 and e.extract:
            e.errhdl(e.path, m, "E", "194", _i8(e.numsrc))
    else:
        e.errhdl(e.path, m, "E", "110", e.keywrd)


def _oufich(e, m, atributo, txt_err):
    if e.ifc == 3:
        if e.loce[3] - e.locb[3] <= ILEN_FLD - 1:
            nombre = e.runst1[e.locb[3] - 1:e.loce[3]]
            if _abierto(e, nombre):
                e.errhdl(e.path, m, "E", "505", nombre)
            else:
                try:                               # OPEN(..., STATUS='REPLACE')
                    open(nombre.rstrip(), "w").close()
                    setattr(e, atributo, nombre)
                except OSError:
                    e.errhdl(e.path, m, "E", "500", txt_err)
        else:
            e.errhdl(e.path, m, "E", "210", _i8(ILEN_FLD))
    elif e.ifc > 3:
        e.errhdl(e.path, m, "E", "202", e.keywrd)
    else:
        e.errhdl(e.path, m, "W", "207", e.keywrd)


def _abierto(e, nombre):
    """INQUIRE(FILE=..., OPENED=...): en ese momento están abiertos el control, la salida
    principal y los ficheros RECEPTOR/SOURCLOC ya aceptados."""
    def norm(r):
        return os.path.normcase(os.path.abspath(r.rstrip())) if r and r.strip() else None
    n = norm(nombre)
    return n is not None and n in {norm(x) for x in (e.inpfil, e.outfil, e.recfil, e.srcfil)}


def _oudeb(e, m, atributos):
    n = 2 + len(atributos)
    if e.ifc == n:
        for j, a in enumerate(atributos, 3):
            if e.loce[j] - e.locb[j] <= ILEN_FLD - 1:
                setattr(e, a, e.runst1[e.locb[j] - 1:e.loce[j]])
            else:
                e.errhdl(e.path, m, "E", "210", _i8(ILEN_FLD))
    elif e.ifc > n:
        e.errhdl(e.path, m, "E", "202", e.keywrd)
    else:
        e.errhdl(e.path, m, "W", "207", e.keywrd)
