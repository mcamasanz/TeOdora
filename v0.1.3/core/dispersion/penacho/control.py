# -*- coding: utf-8 -*-
"""Traducción de AERMOD 26135 (US EPA, dominio público): lectura del fichero de control.

  · setup.f: SETUP, LWRUPR, DEFINE, GETFLD, EXPATH, EXKEY, SETORD, SINDEX, FSPLIT, VARINI e INCLUD.
  · aermod.f: PRESET (pase previo que dimensiona las matrices) con PREINCLUD, SRCSIZ, RECSIZ,
    PRECART, PREGENCAR, PREXYPNTS, PREPOLR, PREPOLDST, PREGENPOL, PRERADRNG y SET_WINDOW;
    ALLSETUP y ALLRESULT (creación de las matrices y memoria estimada).

Peculiaridades del original que se replican a propósito:
  · Columnas FIJAS para la vía (2) y la clave (8), con un desplazamiento de hasta 3 columnas que
    se decide solo cuando DEFINE ve ILINE = 1 (si la línea 1 está en blanco no se decide nunca).
  · PRESET no reinicia ILINE entre sus dos pases ni tras un INCLUDED (los números de línea de
    sus mensajes salen desplazados); SETUP sí lo restaura tras cada INCLUDED.
  · Cuando un número no se puede leer, la variable destino conserva su valor anterior."""
import re

import numpy as np

from .estado import IFMAX, ILEN_FLD, ISTRG, NoTraducido, Parada, P
from .formato import F32, fc, fwrite, fx, nint, stodbl, stonum

PATHWY6 = ("CO", "SO", "RE", "ME", "OU", "**")
PATHWY7 = ("CO", "SO", "RE", "ME", "OU", "**", "EV")
_MAY = str.maketrans("abcdefghijklmnopqrstuvwxyz", "ABCDEFGHIJKLMNOPQRSTUVWXYZ")
_NOBLANCO = re.compile(r"[^ ]+")


# =============================================================================== lectura
def cargar(e, linea):
    """READ (A0512,T1,0512A1) + LWRUPR: RUNST1 conserva mayúsculas/minúsculas; RUNST va en
    mayúsculas (solo a-z) y relleno a 512 columnas."""
    r1 = linea[:ISTRG]
    e.RUNST1 = r1.rstrip(" ")
    e.RUNST = r1.ljust(ISTRG).translate(_MAY)


def define(e):
    """DEFINE: localiza los campos de la línea (las comillas dobles delimitan campos con blancos)."""
    r = e.RUNST
    locb, loce = e.LOCB, e.LOCE
    locb[3:] = 0
    loce[3:] = 0
    e.BLINE = True
    if e.ILINE == 1:
        if r[0] != " ":
            locb[1] = 1
        elif r[1] != " ":
            locb[1] = 2
        elif r[2] != " ":
            locb[1] = 3
        elif r[3] != " ":
            locb[1] = 4
        else:
            locb[1] = 1
        loce[1] = locb[1] + 1
        locb[2] = locb[1] + 3
        loce[2] = locb[1] + 10
    e.IFC = 2
    if not e.RUNST1:
        return
    e.BLINE = False
    ini = int(locb[1]) + 12                     # columna (1..) donde empieza la búsqueda
    if '"' not in r[max(ini - 1, 0):]:
        ifc = 2
        for m in _NOBLANCO.finditer(r, max(ini - 1, 0)):
            ifc += 1
            if ifc > IFMAX:
                e.IFC = ifc
                e.errhdl(e.PPATH, "DEFINE", "E", "109", fwrite("(I8)", IFMAX)[0])
                return
            locb[ifc] = m.start() + 1
            loce[ifc] = m.end()
        e.IFC = ifc
        return
    infld = inquote = False
    ifc = 2
    for i in range(ini, ISTRG + 1):
        c = r[i - 1]
        if not infld and c == '"':
            infld = inquote = True
            ifc += 1
            if ifc > IFMAX:
                e.IFC = ifc
                e.errhdl(e.PPATH, "DEFINE", "E", "109", fwrite("(I8)", IFMAX)[0])
                return
            locb[ifc] = i + 1
        elif not infld and c != " ":
            infld = True
            ifc += 1
            if ifc > IFMAX:
                e.IFC = ifc
                e.errhdl(e.PPATH, "DEFINE", "E", "109", fwrite("(I8)", IFMAX)[0])
                return
            locb[ifc] = i
        elif inquote and c == '"':
            infld = inquote = False
            loce[ifc] = i - 1
        elif not inquote and infld and c == " ":
            infld = False
            loce[ifc] = i - 1
        if infld and i == ISTRG:
            loce[ifc] = ISTRG
    e.IFC = ifc


def getfld(e):
    """GETFLD: contenido de los campos 1..IFC (truncados a ILEN_FLD); los demás quedan en blanco.
    FIELD va en mayúsculas; FIELD1 conserva el texto original (nombres de fichero)."""
    f, f1 = e.FIELD, e.FIELD1
    for i in range(1, IFMAX + 1):
        f[i] = ""
        f1[i] = ""
    r, r1 = e.RUNST, e.RUNST1
    for i in range(1, min(e.IFC, IFMAX) + 1):
        b, fin = int(e.LOCB[i]), int(e.LOCE[i])
        if fin - b <= ILEN_FLD - 1:
            f[i] = r[max(b - 1, 0):fin].rstrip(" ") if fin >= b else ""
            f1[i] = r1[max(b - 1, 0):fin].rstrip(" ") if fin >= b else ""
        else:
            f[i] = r[b - 1:b - 1 + ILEN_FLD].rstrip(" ")
            f1[i] = r1[b - 1:b - 1 + ILEN_FLD].rstrip(" ")


def expath(e, inpfld, pathwy):
    """EXPATH -> nopath."""
    inpfld = inpfld[:2].rstrip(" ")
    if inpfld:
        e.PATH = inpfld
        for i, p in enumerate(pathwy, 1):
            if inpfld == p:
                e.IPNUM = i
                return False
        return True
    e.PATH = e.PPATH
    e.IPNUM = e.IPPNUM
    return False


def exkey(e, inpfld):
    """EXKEY -> nokey."""
    inpfld = inpfld[:8].rstrip(" ")
    if inpfld:
        e.KEYWRD = inpfld
        return inpfld not in _KEYWD
    if e.PKEYWD != "STARTING":
        e.KEYWRD = e.PKEYWD
        return False
    e.KEYWRD = "blank"
    return True


_KEYWD = set(k.rstrip(" ") for k in __import__("teodors.dispersion.penacho.tablas", fromlist=["DATA"]).DATA["KEYWD"])


def setord(e):
    """SETORD: orden de STARTING/FINISHED y de las vías."""
    m = "SETORD"
    k = e.KEYWRD
    if k == "STARTING":
        if e.ISTART or not e.IFINIS:
            e.errhdl(e.PPATH, m, "E", "119", e.PATH)
        elif e.IPNUM != e.IPPNUM + 1:
            e.errhdl(e.PPATH, m, "E", "120", e.PATH)
        e.ISTART = True
        e.IFINIS = False
    elif k == "FINISHED":
        if e.IFINIS or not e.ISTART:
            e.errhdl(e.PPATH, m, "E", "119", e.PATH)
        elif e.ISTART and e.PATH != e.PPATH:
            e.errhdl(e.PPATH, m, "E", "120", e.PATH)
        e.ISTART = False
        e.IFINIS = True
    elif not e.ISTART or e.IFINIS:
        e.errhdl(e.PPATH, m, "E", "119", e.PATH)
    elif e.ISTART and e.PATH != e.PPATH:
        e.errhdl(e.PPATH, m, "E", "120", e.PATH)
    e.PPATH = e.PATH
    e.IPPNUM = e.IPNUM


def sindex(arrin, idim, elem):
    """SINDEX -> (índice, encontrado)."""
    for i in range(1, idim + 1):
        if elem == arrin[i]:
            return i, True
    return 0, False


def fsplit(e, pathin, keyin, inpfld, length, delim):
    """FSPLIT: divide un campo por el delimitador (buscado desde el final).
    Devuelve (lflag, begfld, endfld) en forma canónica."""
    s = inpfld[:length].ljust(length)
    i = length
    idelm = length
    begfld = endfld = ""
    mend = inn = lflag = False
    while not mend and i >= 1:
        c = s[i - 1]
        if c != " ":
            inn = True
            if not lflag and c == delim:
                lflag = True
                idelm = i
                endfld = s[i:length].rstrip(" ")
                if i == 1:
                    e.errhdl(pathin, "FSPLIT", "E", "203", keyin)
                    return lflag, begfld, endfld
            elif lflag and c == delim:
                e.errhdl(pathin, "FSPLIT", "E", "217", keyin)
        elif inn and c == " ":
            mend = True
            begfld = s[:idelm - 1].rstrip(" ") if lflag else s.rstrip(" ")
        i -= 1
    if not mend:
        begfld = s[:idelm - 1].rstrip(" ") if lflag else s.rstrip(" ")
    if not lflag:
        endfld = begfld
    return lflag, begfld, endfld


def dbl(e, i, previo):
    """CALL STODBL(FIELD(i),ILEN_FLD,DNUM,IMIT) -> (valor, imit)."""
    return stodbl(e.FIELD[i], ILEN_FLD, previo)


def num(e, i, previo):
    """CALL STONUM(FIELD(i),ILEN_FLD,FNUM,IMIT) -> (valor, imit)."""
    return stonum(e.FIELD[i], ILEN_FLD, previo)


def i8(n):
    return fwrite("(I8)", n)[0]


# =============================================================================== SETUP
def setup(e):
    """SETUP: lee y procesa el fichero de control, vía a vía."""
    from . import entrada_control, entrada_meteo, entrada_salidas, entrada_receptores, entrada_fuentes
    m = "SETUP"
    e.PATH = ""
    e.PPATH = ""
    e.EOF = False
    nocommentecho = False
    e.ILINE = 0
    e.IOLINE = 0
    e.IBLINE = 0
    e.INOXLINE = 0
    e.IHR_NDX = 0
    e.IYR_NDX = 0
    e.IBARID = 0
    inp = e.U[e.INUNIT]
    out = e.U[e.IOUNIT]
    while not e.EOF:
        e.ILINE += 1
        linea = inp.leer()
        if linea is None:
            break
        cargar(e, linea)
        if not e.RUNST1:
            out.w(" ")
            continue
        define(e)
        getfld(e)
        if e.ECHO and e.FIELD[1] == "OU" and e.FIELD[2] == "FINISHED":
            lb = int(e.LOCB[1])
            if 1 <= lb <= 4:
                out.w(fx(e.RUNST1, 10 + lb))
        elif e.ECHO:
            out.w(e.RUNST1)
        if e.FIELD[1] == "NO" and e.FIELD[2] == "ECHO":
            e.ECHO = False
            continue
        nopath = expath(e, e.FIELD[1], PATHWY6)
        if nopath:
            e.errhdl(e.PPATH, m, "E", "100", e.PATH)
            e.PATH = e.PPATH
            continue
        elif e.PATH == "RE":
            nocommentecho = True
        elif e.PATH == "ME":
            nocommentecho = False
        elif e.PATH == "OU":
            nocommentecho = True
        if e.PATH == "**":
            continue
        nokey = exkey(e, e.FIELD[2])
        if nokey:
            e.errhdl(e.PATH, m, "E", "105", e.KEYWRD)
            e.PKEYWD = e.KEYWRD
            continue
        setord(e)
        if e.PATH == "CO":
            entrada_control.cocard(e)
        elif e.PATH == "SO":
            entrada_fuentes.socard(e)
        elif e.PATH == "RE":
            entrada_receptores.recard(e)
        elif e.PATH == "ME":
            entrada_meteo.mecard(e)
            s = ""
            for i in range(1, 31):
                if e.MODOPS[i]:
                    s = s + "  " + e.MODOPS[i]
            e.MODOPS_STRING = fc(s, 250)
        elif e.PATH == "OU":
            entrada_salidas.oucard(e)
        e.PKEYWD = e.KEYWRD
        if e.PATH == "OU" and e.KEYWRD == "FINISHED":
            break
    e.EOF = True
    e.ILINE = 0
    if (e.ICSTAT[50] != 1 or e.ISSTAT[50] != 1 or e.IRSTAT[50] != 1 or e.IMSTAT[50] != 1
            or e.IOSTAT[50] != 1):
        ifstat = (int(e.ICSTAT[50]) * 10000 + int(e.ISSTAT[50]) * 1000 + int(e.IRSTAT[50]) * 100
                  + int(e.IMSTAT[50]) * 10 + int(e.IOSTAT[50]))
        e.DUMMY = fwrite("(I5.5)", ifstat)[0]
        e.errhdl(e.PATH, m, "E", "125", e.DUMMY)
        if ifstat == 0:
            txt = fwrite("(/1X,'All AERMOD input pathways missing! ','Processing aborted!!!')")
            out.w(txt)
            e.pantalla.w(txt)
            raise Parada()
    e.MAXDIST = 8.0e04 if (e.FASTALL or e.FASTAREA) else 1.0e20


def includ(e):
    """INCLUD: procesa un fichero INCLUDED (vías SO, RE y EV)."""
    from . import entrada_receptores, entrada_fuentes
    m = "INCLUD"
    e.EOF = False
    e.ILINE = 0
    itempl = 0
    if e.IFC == 3:
        if e.LOCE[3] - e.LOCB[3] <= ILEN_FLD - 1:
            e.INCFIL = fc(e.RUNST1[int(e.LOCB[3]) - 1:int(e.LOCE[3])], 200)
            try:
                inc = e.abrir_entrada(e.INCUNT, e.INCFIL)
            except OSError:
                e.errhdl(e.PATH, m, "E", "500", "INCFILE ")
                return
        else:
            e.DUMMY = i8(ILEN_FLD)
            e.errhdl(e.PATH, m, "E", "291", e.DUMMY)
            return
    elif e.IFC > 4:
        e.errhdl(e.PATH, m, "E", "202", e.KEYWRD)
        return
    else:
        e.errhdl(e.PATH, m, "E", "200", e.KEYWRD)
        return
    while True:
        e.ILINE += 1
        linea = inc.leer()
        if linea is None:
            break
        cargar(e, linea)
        if not e.RUNST1:
            continue
        if e.ILINE == 1:
            e.ILINE = 2
            itempl = 1
        define(e)
        if itempl == 1:
            e.ILINE = 1
            itempl = 0
        getfld(e)
        if e.FIELD[1] == "NO" and e.FIELD[2] == "ECHO":
            continue
        nopath = expath(e, e.FIELD[1], PATHWY7)
        if nopath:
            e.errhdl(e.PPATH, m, "E", "100", e.PATH)
            e.PATH = e.PPATH
            continue
        elif e.PATH == "**":
            continue
        nokey = exkey(e, e.FIELD[2])
        if nokey:
            e.errhdl(e.PATH, m, "E", "105", e.KEYWRD)
            e.PKEYWD = e.KEYWRD
            continue
        if e.KEYWRD != "STARTING" and e.KEYWRD != "FINISHED":
            setord(e)
        if e.KEYWRD == "STARTING":
            e.errhdl(e.PATH, m, "E", "140", e.KEYWRD)
        elif e.KEYWRD == "INCLUDED":
            e.errhdl(e.PATH, m, "E", "135", e.KEYWRD)
        elif e.KEYWRD == "FINISHED":
            e.errhdl(e.PATH, m, "E", "140", e.KEYWRD)
        elif e.PATH == "SO":
            entrada_fuentes.socard(e)
        elif e.PATH == "RE":
            entrada_receptores.recard(e)
        elif e.PATH == "EV":
            raise NoTraducido("EVENT (vía EV)")
        e.PKEYWD = e.KEYWRD
    e.EOF = False
    e.cerrar(e.INCUNT)


# =============================================================================== PRESET
_NCHR1 = ("FIRST", "SECOND", "THIRD", "FOURTH", "FIFTH", "SIXTH", "SEVENTH", "EIGHTH", "NINTH", "TENTH")
_NCHR2 = ("1ST", "2ND", "3RD", "4TH", "5TH", "6TH", "7TH", "8TH", "9TH", "10TH")
_NFAC = {"ANNUAL": 1, "SEASON": 4, "MONTH": 12, "HROFDY": 24, "WSPEED": 6, "SEASHR": 96,
         "HRDOW": 72, "HRDOW7": 168, "SHRDOW": 288, "SHRDOW7": 672, "MHRDOW": 864, "MHRDOW7": 2016}


def preset(e):
    """PRESET: primer pase por el fichero de control para dimensionar las matrices."""
    m = "PRESET"
    e.PREVSRCID = ""
    e.PREVGRPID = ""
    e.PATH = ""
    e.PPATH = ""
    e.EOF = False
    e.NSEC = e.NPDMAX = e.NQF = e.NBF = e.NURB = e.NVMAX = 0
    e.ILINE = 0
    e.NAFT = 0
    e.IPNUM = e.IPPNUM = 0
    e.IREC = 0
    e.ISTA = False
    e.IEND = False
    e.NEWID = True
    e.L_PRESET_URBAN = False
    e.L_MULTURB = False
    e.L_URBAN_ALL = False
    e.L_PRESET_ARCFT = False
    e.L_ARCFT_ALL = False
    e.L_HBP_ALL = False
    e.L_O3SECTOR = False
    l_o3data = False
    e.L_BGSECTOR = False
    e.L_BACKGRND = False
    e.L_NOXSECTOR = False
    l_noxdata = False
    e.L_BLSOURCE = False
    e.FILE_FORMAT = "FIX"
    e.ARM2 = e.OLM = e.PVMRM = e.GRSM = False
    e.MODOPS_STRING = ""
    for i in range(1, IFMAX + 1):
        e.DEBUG_FLS[i] = ""
        e.DEBUG_FLS1[i] = ""
    inp = e.U[e.INUNIT]
    # ---- primer pase: opciones que condicionan el segundo
    while True:
        e.ILINE += 1
        linea = inp.leer()
        if linea is None:
            break
        cargar(e, linea)
        if not e.RUNST1:
            continue
        define(e)
        getfld(e)
        if e.BLINE:
            continue
        if e.FIELD[1] == "NO" and e.FIELD[2] == "ECHO":
            continue
        if expath(e, e.FIELD[1], PATHWY7):
            e.PATH = e.PPATH
            continue
        elif e.PATH == "**":
            continue
        if exkey(e, e.FIELD[2]):
            e.PKEYWD = e.KEYWRD
            continue
        e.PPATH = e.PATH
        e.IPPNUM = e.IPNUM
        k = e.KEYWRD
        if e.PATH == "CO":
            if k == "O3SECTOR":
                e.L_O3SECTOR = True
                continue
            elif k in ("OZONEFIL", "O3VALUES", "OZONEVAL"):
                l_o3data = True
                continue
            elif k == "EVENTFIL":
                continue
            elif k == "LOW_WIND":
                e.LOW_WIND = True
            elif k == "NOXSECTR":
                e.L_NOXSECTOR = True
                continue
            elif k in ("NOX_FILE", "NOX_VALS", "NOXVALUE"):
                l_noxdata = True
                continue
        elif e.PATH == "SO":
            if k == "BGSECTOR":
                e.L_BGSECTOR = True
                continue
            elif k == "BACKGRND":
                e.L_BACKGRND = True
                continue
            elif k == "INCLUDED" and (not e.L_BGSECTOR or not e.L_BACKGRND):
                preinclud(e)
                continue
            elif k == "URBANSRC":
                e.L_URBAN = True
                if e.FIELD[3] == "ALL":
                    e.L_RURAL = False
                continue
            elif k == "ARCFTSRC":
                e.L_ARCFT = True
                continue
            elif k in ("BLPINPUT", "BLPGROUP"):
                e.L_BLSOURCE = True
                continue
            if e.L_BGSECTOR and e.L_BACKGRND:
                break
        elif e.PATH == "RE":
            break
    if e.L_O3SECTOR and not l_o3data:
        e.errhdl(e.PATH, m, "W", "166", "O3SECTOR")
    if e.L_BGSECTOR and not e.L_BACKGRND:
        e.errhdl(e.PATH, m, "W", "166", "BGSECTOR")
    if e.L_NOXSECTOR and not l_noxdata:
        e.errhdl(e.PATH, m, "W", "166", "NOXSECTR")
    # ---- segundo pase: tamaños
    inp.rewind()
    e.PATH = ""
    e.PPATH = ""
    e.IPNUM = e.IPPNUM = 0
    e.EOF = False
    while True:
        e.ILINE += 1
        linea = inp.leer()
        if linea is None:
            break
        cargar(e, linea)
        if not e.RUNST1:
            continue
        define(e)
        getfld(e)
        if e.FIELD[1] == "NO" and e.FIELD[2] == "ECHO":
            continue
        if expath(e, e.FIELD[1], PATHWY7):
            e.PATH = e.PPATH
            continue
        elif e.PATH == "**":
            continue
        if exkey(e, e.FIELD[2]):
            e.PKEYWD = e.KEYWRD
            continue
        e.PPATH = e.PATH
        e.IPPNUM = e.IPNUM
        k = e.KEYWRD
        f = e.FIELD
        if e.PATH == "CO":
            if k == "DEBUGOPT":
                e.DEBUG_COUNT += 1
            if k == "MODELOPT":
                for i in range(3, e.IFC + 1):
                    fi = f[i] if i <= IFMAX else ""
                    if fi in ("CONC", "DEPOS", "DDEP", "WDEP"):
                        e.NTYP += 1
                    if fi == "PVMRM":
                        e.PVMRM = True
                    elif fi == "PSDCREDIT":
                        e.PSDCREDIT = True
                    elif fi == "OLM":
                        e.OLM = True
                    elif fi == "ARM2":
                        e.ARM2 = True
                    elif fi == "GRSM":
                        e.GRSM = True
                    elif fi == "TTRM":
                        e.RUNTTRM = True
                    elif fi == "TTRM2":
                        e.RUNTTRM = True
                        e.RUNTTRM2 = True
                    if fi == "ALPHA":
                        e.L_ALPHA = True
                    elif fi == "BETA":
                        e.BETA = True
            elif k == "AVERTIME":
                for i in range(3, e.IFC + 1):
                    if f[i] != "PERIOD" and f[i] != "ANNUAL":
                        e.NAVE += 1
            elif k == "URBANOPT":
                e.NURB += 1
                e.L_PRESET_URBAN = True
                if e.NURB > 1:
                    e.L_MULTURB = True
            elif k == "ARCFTOPT":
                e.NAFT += 1
                e.L_PRESET_ARCFT = True
            elif k == "O3SECTOR":
                e.L_O3SECTOR = True
                e.NUMO3SECTS = e.IFC - 2
            elif k == "O3VALUES":
                kk = 4 if e.L_O3SECTOR else 3
                if f[kk] in _NFAC:
                    e.NO3F = max(e.NO3F, _NFAC[f[kk]])
            elif k == "NOXSECTR":
                e.L_NOXSECTOR = True
                e.NUMNOXSECTS = e.IFC - 2
            elif k == "NOX_VALS":
                kk = 4 if e.L_NOXSECTOR else 3
                if f[kk] in _NFAC:
                    e.NNOXF = max(e.NNOXF, _NFAC[f[kk]])
            elif k == "LOW_WIND":
                n = e.IFC
                if 3 <= n <= 9:
                    e.L_USERSVMIN = True
                if 4 <= n <= 9:
                    e.L_USERWSMIN = True
                if 5 <= n <= 9:
                    e.L_USERFRANMAX = True
                if 6 <= n <= 9:
                    e.L_USERSWMIN = True
                if 7 <= n <= 9:
                    e.L_USERBIGT = True
                if 8 <= n <= 9:
                    e.L_USERFRANMIN = True
                if n == 9 and f[n] in ("PBAL", "PBALANCE"):
                    e.L_PBAL = True
                e.MODOPS[22] = "LOW_WIND"
        elif e.PATH == "SO":
            srcsiz(e)
        elif e.PATH == "RE":
            e.EVONLY = False
            recsiz(e)
        elif e.PATH == "EV":
            e.EVONLY = True
            if k == "EVENTPER":
                e.NEVE += 1
            elif k == "INCLUDED":
                preinclud(e)
        elif e.PATH == "ME" and k == "SURFDATA":
            set_window(e)
        elif e.PATH == "ME" and k == "NUMYEARS":
            if e.IFC == 3:
                e.FNUM, imit = num(e, 3, e.FNUM)
                e.IMIT = imit
                if imit == 1:
                    e.NYEARS = nint(e.FNUM)
        elif e.PATH == "OU":
            if k == "RECTABLE":
                for i in range(4, e.IFC + 1):
                    if i > IFMAX:
                        break
                    _rmark, lprd, hprd = fsplit(e, e.PATH, k, f[i], ILEN_FLD, "-")
                    lprd = lprd[:8].rstrip(" ")
                    hprd = hprd[:8].rstrip(" ")
                    isprd = ieprd = 0
                    e.FNUM, imit = stonum(lprd, ILEN_FLD, e.FNUM)
                    if imit == 1:
                        isprd = int(e.FNUM)
                    e.FNUM, imit = stonum(hprd, ILEN_FLD, e.FNUM)
                    e.IMIT = imit
                    if imit == 1:
                        ieprd = int(e.FNUM)
                    for j in range(10):
                        if lprd == _NCHR1[j] or lprd == _NCHR2[j][:5]:
                            isprd = j + 1
                        if hprd == _NCHR1[j] or hprd == _NCHR2[j][:5]:
                            ieprd = j + 1
                    if isprd > 999 or ieprd > 999:
                        e.errhdl(e.PATH, m, "E", "203", "HIVALU")
                        continue
                    if isprd > e.NVAL:
                        e.NVAL = isprd
                    if ieprd > e.NVAL:
                        e.NVAL = ieprd
            elif k in ("MAXTABLE", "RANKFILE"):
                e.FNUM, imit = num(e, 4, e.FNUM)
                e.IMIT = imit
                if imit != 1:
                    break
                e.INUM = nint(e.FNUM)
                if e.INUM > e.NMXVAL:
                    e.NMXVAL = e.INUM
            elif k == "SEASONHR":
                e.SEASONHR = True
            elif k == "MAXDCONT":
                e.L_MAXDCONT = True
            elif k == "FILEFORM" and f[3][:3] == "EXP":
                e.FILE_FORMAT = "EXP"
            elif k == "NOHEADER":
                for i in range(3, e.IFC + 1):
                    fi = f[i]
                    if fi == "ALL":
                        e.L_NOHEADER[:] = True
                        break
                    j = ("MAXIFILE", "POSTFILE", "PLOTFILE", "SEASONHR", "RANKFILE", "MAXDAILY",
                         "MXDYBYYR", "MAXDCONT")
                    if fi in j:
                        e.L_NOHEADER[j.index(fi) + 1] = True
            elif k == "FINISHED":
                break
        e.PKEYWD = e.KEYWRD
    if e.PSDCREDIT:
        e.NGRP = 2
    if e.NAREA == 0 and e.NLINE == 0 and e.NPIT == 0:
        e.NVMAX = 0
    else:
        if e.NPOLY == 0 and e.NCIRC == 0:
            e.NVMAX = 8
        else:
            e.NVMAX = max(e.NVMAX, 8)
    e.NVMAX2 = e.NVMAX * 2
    inp.rewind()
    e.ILINE = 0
    e.PNETID = ""
    e.NSRC = max(e.NSRC, 1)
    e.NGRP = max(e.NGRP, 1)
    e.NREC = max(e.NREC, 1)
    e.NARC = e.NREC
    e.NAVE = max(e.NAVE, 1)
    e.NTYP = max(e.NTYP, 1)
    e.NNET = max(e.NNET, 1)
    e.IXM = max(e.IXM, 1)
    e.IYM = max(e.IYM, 1)
    maxfiles = e.NGRP * e.NAVE * 10 + 100
    e.FUNITIND = 1
    e.FUNITINX = 100
    e.alloc("FUNITARRAY", maxfiles)
    e.alloc("FNAMEARRAY", maxfiles)
    e.alloc("FTYPARRAY", maxfiles)
    e.FUNITARRAY[1], e.FNAMEARRAY[1], e.FTYPARRAY[1] = e.INUNIT, e.INPFIL, "INPUT"
    e.FUNITARRAY[2], e.FNAMEARRAY[2], e.FTYPARRAY[2] = e.IOUNIT, e.OUTFIL, "OUTPUT"
    e.FUNITIND = 3
    e.alloc("HOUREMISARRAY", e.NSRC)
    e.alloc("HOUREMISNAMEARRAY", e.NSRC)
    e.alloc("HRSRCIDS", e.NSRC)
    e.alloc("IQLINE", e.NSRC)


def preinclud(e):
    """PREINCLUD: pase previo de un fichero INCLUDED (no restaura ILINE al volver)."""
    m = "PREINCLUD"
    e.EOF = False
    e.ILINE = 0
    itempl = 0
    e.L_PREINC = True
    if e.IFC == 3:
        if e.LOCE[3] - e.LOCB[3] <= ILEN_FLD - 1:
            e.INCFIL = fc(e.RUNST1[int(e.LOCB[3]) - 1:int(e.LOCE[3])], 200)
            try:
                inc = e.abrir_entrada(e.INCUNT, e.INCFIL)
            except OSError:
                e.errhdl(e.PATH, m, "E", "500", "INCFILE ")
                return
        else:
            e.DUMMY = i8(ILEN_FLD)
            e.errhdl(e.PATH, m, "E", "291", e.DUMMY)
            return
    else:
        return
    while True:
        e.ILINE += 1
        linea = inc.leer()
        if linea is None:
            break
        cargar(e, linea)
        if e.ILINE == 1:
            e.ILINE = 2
            itempl = 1
        if not e.RUNST1:
            continue
        define(e)
        if itempl == 1:
            e.ILINE = 1
            itempl = 0
        getfld(e)
        if e.FIELD[1] == "NO" and e.FIELD[2] == "ECHO":
            continue
        if expath(e, e.FIELD[1], PATHWY7):
            e.PATH = e.PPATH
            continue
        elif e.PATH == "**":
            continue
        if exkey(e, e.FIELD[2]):
            e.PKEYWD = e.KEYWRD
            continue
        e.PPATH = e.PATH
        e.IPPNUM = e.IPNUM
        if e.PATH == "SO":
            srcsiz(e)
        elif e.PATH == "RE":
            recsiz(e)
        elif e.PATH == "EV":
            if e.KEYWRD == "EVENTPER":
                e.NEVE += 1
        e.PKEYWD = e.KEYWRD
    e.EOF = False
    e.cerrar(e.INCUNT)
    e.L_PREINC = False


_AVISOS_QUIMICA = (("PVMRM", "722"), ("OLM", "725"), ("GRSM", "724"))


def _avisos_fuente(e, arm2=True):
    m = "SRCSIZ"
    if e.PVMRM:
        e.errhdl(e.PATH, m, "W", "722", e.FIELD[4])
    if e.RUNTTRM2:
        e.errhdl(e.PATH, m, "W", "723", e.FIELD[4])
    elif e.RUNTTRM:
        e.errhdl(e.PATH, m, "W", "710", e.FIELD[4])
    if e.OLM:
        e.errhdl(e.PATH, m, "W", "725", e.FIELD[4])
    if e.GRSM:
        e.errhdl(e.PATH, m, "W", "724", e.FIELD[4])
    if arm2 and e.ARM2:
        e.errhdl(e.PATH, m, "W", "726", e.FIELD[4])


def srcsiz(e):
    """SRCSIZ: cuenta fuentes, grupos, vértices... (vía SO del pase previo)."""
    m = "SRCSIZ"
    k = e.KEYWRD
    f = e.FIELD
    if k == "STARTING":
        for n in ("NSRC", "NGRP", "NOLM", "NPSD", "NBLGRP", "NQF", "NBF", "NSEC", "NPIT", "NPNT",
                  "NVOL", "NAREA", "NPOLY", "NCIRC", "NLINE", "NRLINES", "NBLP", "NURBSRC", "NSWP",
                  "NAFTSRC", "NHBP", "NVMAX", "NVTEMP", "NPTEMP", "NPDMAX", "NSBR", "NVBR"):
            setattr(e, n, 0)
        e.PREVSRCID = ""
        e.PREVGRPID = ""
        e._srcsiz_tmp = []
    elif k == "LOCATION":
        e.NSRC += 1
        f4 = f[4]
        if f4[:5] == "POINT":
            e.NPNT += 1
        elif f4 == "VOLUME":
            e.NVOL += 1
        elif f4 == "LINE":
            e.NLINE += 1
        elif f4 == "SWPOINT":
            if e.L_ALPHA or e.L_PREINC:
                e.NSWP += 1
            else:
                e.errhdl(e.PATH, m, "E", "198", " SWPOINT")
            _avisos_fuente(e)
        elif f4 == "RLINE":
            e.NRLINES += 1
            _avisos_fuente(e, arm2=False)
        elif f4 == "RLINEXT":
            if e.L_ALPHA or e.L_PREINC:
                e.NRLINES += 1
            else:
                e.errhdl(e.PATH, m, "E", "198", " RLINEXT")
            _avisos_fuente(e, arm2=False)
        elif f4 == "BUOYLINE":
            e.NBLP += 1
            _avisos_fuente(e, arm2=False)
        elif f4[:4] == "AREA":
            e.NAREA += 1
            e.NVMAX = max(e.NVMAX, 8)
            if f4 == "AREAPOLY":
                e.NPOLY += 1
                e.NVMAX = max(e.NVMAX, 8)
            elif f4 == "AREACIRC":
                e.NCIRC += 1
                tmp = getattr(e, "_srcsiz_tmp", [])
                tmp = tmp + [""] * (e.NSRC - len(tmp))
                tmp[e.NSRC - 1] = fc(f[3], 12)
                e._srcsiz_tmp = tmp
        elif f4 == "OPENPIT":
            e.NPIT += 1
        else:
            e.errhdl(e.PATH, m, "E", "640", f4)
    elif k == "SRCPARAM":
        tmp = getattr(e, "_srcsiz_tmp", [])
        for i in range(1, e.NSRC + 1):
            if len(tmp) < i:
                break
            if f[3] == tmp[i - 1]:
                if e.IFC >= 7:
                    e.DNUM, imit = dbl(e, 7, e.DNUM)
                    e.IMIT = imit
                    if imit != 1:
                        e.errhdl(e.PATH, m, "E", "208", k)
                    else:
                        e.NVMAX = max(e.NVMAX, nint(e.DNUM) + 4)
                else:
                    e.NVMAX = max(e.NVMAX, 24)
                break
    elif k == "AREAVERT":
        if f[3] == e.PREVSRCID:
            e.NVTEMP = e.NVTEMP + e.IFC - 3
        else:
            e.NVTEMP = e.IFC - 3
            e.PREVSRCID = fc(f[3], 12)
        e.NVMAX = max(e.NVMAX, e.NVPOLY + nint(float(int(e.NVTEMP / 2))))
    elif k == "PARTDIAM":
        if f[3] == e.PREVSRCID:
            e.NPTEMP = e.NPTEMP + e.IFC - 3
        else:
            e.NPTEMP = e.IFC - 3
            e.PREVSRCID = fc(f[3], 12)
        e.NPDMAX = max(e.NPDMAX, e.NPTEMP)
    elif k in ("BUILDHGT", "BUILDWID", "BUILDLEN"):
        e.NSEC = 36
    elif k == "METHOD_2":
        e.NPDMAX = max(e.NPDMAX, 1)
    elif k == "EMISFACT":
        if f[4] in _NFAC and f[4] != "ANNUAL":
            e.NQF = max(e.NQF, _NFAC[f[4]])
    elif k == "BGSECTOR":
        e.L_BGSECTOR = True
        e.NUMBGSECTS = e.IFC - 2
    elif k == "BACKGRND":
        e.L_BACKGRND = True
        kk = 4 if e.L_BGSECTOR else 3
        if f[kk] in _NFAC:
            e.NBF = max(e.NBF, _NFAC[f[kk]])
    elif k == "URBANSRC" and e.IFC == 3 and f[3] == "ALL" and e.L_PRESET_URBAN:
        if not e.L_MULTURB:
            e.L_URBAN_ALL = True
            e.NURBSRC = e.NSRC
        else:
            e.errhdl(e.PATH, m, "E", "279", "URBANSRC ALL")
    elif k == "URBANSRC" and not e.L_MULTURB:
        e.NURBSRC = e.NURBSRC + e.IFC - 2
    elif k == "URBANSRC" and e.L_MULTURB:
        e.NURBSRC = e.NURBSRC + e.IFC - 3
    elif k == "ARCFTSRC" and e.IFC == 3 and f[3] == "ALL" and e.L_PRESET_ARCFT:
        e.L_ARCFT_ALL = True
        e.NAFTSRC = e.NSRC
    elif k == "ARCFTSRC":
        e.NAFTSRC = e.NAFTSRC + e.IFC - 2
    elif k == "HBPSRCID" and e.IFC == 3 and f[3] == "ALL":
        e.L_HBP_ALL = True
    elif k in ("OLMGROUP", "PSDGROUP", "BLPGROUP", "SRCGROUP"):
        cont = {"OLMGROUP": "NOLM", "PSDGROUP": "NPSD", "BLPGROUP": "NBLGRP", "SRCGROUP": "NGRP"}[k]
        if getattr(e, cont) == 0:
            e.PREVGRPID = ""
        if f[3] != e.PREVGRPID:
            setattr(e, cont, getattr(e, cont) + 1)
            e.PREVGRPID = fc(f[3], 8)
    elif k == "BLPINPUT":
        e.NBLAVGINPALLOC += 1
    elif k == "SBARRIER":
        if e.NSBR == 0:
            e.SBARID = ""
        if f[3] != e.SBARID:
            e.NSBR += 1
            e.SBARID = fc(f[3], 12)
    elif k == "VBARRIER":
        e.NVBR += 1
    elif k == "INCLUDED":
        preinclud(e)
    elif k == "FINISHED":
        if e.NBLP > 0 and e.NBLGRP == 0:
            e.NBLGRP = 1


def recsiz(e):
    """RECSIZ: cuenta receptores y redes (vía RE del pase previo)."""
    k = e.KEYWRD
    if k == "STARTING":
        e.NREC = e.NNET = e.IXM = e.IYM = 0
        e.PXSOID = ""
        e.ISTA = False
    elif k == "GRIDCART":
        precart(e)
    elif k == "GRIDPOLR":
        prepolr(e)
    elif k in ("DISCCART", "EVALCART", "DISCPOLR"):
        e.NREC += 1
    elif k == "INCLUDED":
        preinclud(e)


def _red_pre(e, claves):
    if e.IFC < 3:
        return None
    netidt = fc(e.FIELD[3], 8)
    if not e.NEWID and (netidt in claves):
        netidt = e.PNETID
        e.KTYPE = fc(e.FIELD[3], 5)
    elif not e.NEWID and netidt == e.PNETID:
        e.KTYPE = fc(e.FIELD[4], 5)
    elif e.NEWID and netidt != "":
        e.NEWID = False
        e.KTYPE = fc(e.FIELD[4], 5)
        e.NNET += 1
    else:
        return False
    e.NETIDT = netidt
    return True


def precart(e):
    """PRECART: tamaño de una red GRIDCART."""
    r = _red_pre(e, ("", "XYINC", "XPNTS", "YPNTS", "ELEV", "HILL", "FLAG", "END"))
    if not r:
        return
    kt = e.KTYPE
    if kt == "STA":
        e.ISTA = True
        e.IEND = False
        e.NEWID = False
        e.RECERR = False
        e.ICOUNT = 0
        e.JCOUNT = 0
    elif kt == "XYINC":
        pregencar(e)
    elif kt in ("XPNTS", "YPNTS"):
        prexypnts(e)
    elif kt == "END":
        e.IEND = True
        if not e.RECERR:
            e.NREC = e.NREC + e.ICOUNT * e.JCOUNT
        e.ISTA = False
        e.NEWID = True
    elif kt not in ("ELEV", "FLAG", "HILL"):
        e.RECERR = True
        return
    e.PNETID = e.NETIDT


def _isc(e, clave):
    for i in range(1, e.IFC + 1):
        if e.FIELD[i] == clave:
            e.ISC = i + 1


def pregencar(e):
    _isc(e, "XYINC")
    if e.IFC == e.ISC - 1 or e.IFC > e.ISC + 5 or e.IFC < e.ISC + 5:
        e.RECERR = True
        return
    tempr = [0.0] * 7
    tempd = [0.0] * 7
    error = False
    for k in range(1, 7):
        if k in (2, 5):
            tempr[k], imit = stonum(e.FIELD[e.ISC + k - 1], ILEN_FLD, tempr[k])
        else:
            tempd[k], imit = stodbl(e.FIELD[e.ISC + k - 1], ILEN_FLD, tempd[k])
        e.IMIT = imit
        if imit == -1:
            error = True
            e.RECERR = True
    if error:
        return
    e.XINT = tempd[1]
    e.ICOUNT = nint(tempr[2])
    e.YINT = tempd[4]
    e.JCOUNT = nint(tempr[5])
    if e.ICOUNT > e.IXM:
        e.IXM = e.ICOUNT
    if e.JCOUNT > e.IYM:
        e.IYM = e.JCOUNT


def prexypnts(e):
    if e.KTYPE == "XPNTS":
        _isc(e, "XPNTS")
        if e.IFC == e.ISC - 1:
            e.RECERR = True
            return
        iset = e.ICOUNT
        for i in range(e.ISC, e.IFC + 1):
            e.FNUM, imit = num(e, i, e.FNUM)
            e.IMIT = imit
            if imit == -1:
                e.RECERR = True
            iset += 1
            if iset > e.IXM:
                e.IXM = iset
        e.ISET = iset
        e.ICOUNT = iset
    elif e.KTYPE == "YPNTS":
        _isc(e, "YPNTS")
        if e.IFC == e.ISC - 1:
            e.RECERR = True
            return
        jset = e.JCOUNT
        for i in range(e.ISC, e.IFC + 1):
            e.FNUM, imit = num(e, i, e.FNUM)
            e.IMIT = imit
            if imit == -1:
                e.RECERR = True
            jset += 1
            if jset > e.IYM:
                e.IYM = jset
        e.JCOUNT = jset


def prepolr(e):
    """PREPOLR: tamaño de una red GRIDPOLR."""
    r = _red_pre(e, ("", "ORIG", "DIST", "DDIR", "ELEV", "HILL", "FLAG", "GDIR", "END"))
    if r is None:
        return
    if not r:
        e.RECERR = True
        return
    kt = e.KTYPE
    if kt == "STA":
        e.ISTA = True
        e.IEND = False
        e.NEWID = False
        e.RECERR = False
        e.ICOUNT = 0
        e.JCOUNT = 0
    elif kt == "DIST":
        _isc(e, "DIST")
        if e.IFC == e.ISC - 1:
            e.RECERR = True
        else:
            iset = e.ICOUNT
            for i in range(e.ISC, e.IFC + 1):
                e.FNUM, imit = num(e, i, e.FNUM)
                e.IMIT = imit
                if imit == -1:
                    e.RECERR = True
                iset += 1
                if iset > e.IXM:
                    e.IXM = iset
            e.ISET = iset
            e.ICOUNT = iset
    elif kt == "GDIR":
        _isc(e, "GDIR")
        if e.IFC == e.ISC - 1 or e.IFC < e.ISC + 2 or e.IFC > e.ISC + 2:
            e.RECERR = True
        else:
            tempp = [0.0] * 4
            error = False
            for k in range(1, 4):
                tempp[k], imit = stodbl(e.FIELD[e.ISC + k - 1], ILEN_FLD, tempp[k])
                e.IMIT = imit
                if imit == -1:
                    e.RECERR = True
                    error = True
            if not error:
                e.JCOUNT = nint(tempp[1])
                if e.JCOUNT > e.IYM:
                    e.IYM = e.JCOUNT
    elif kt == "DDIR":
        _isc(e, "DDIR")
        if e.IFC == e.ISC - 1:
            e.RECERR = True
        else:
            iset = e.JCOUNT
            for i in range(e.ISC, e.IFC + 1):
                e.FNUM, imit = num(e, i, e.FNUM)
                e.IMIT = imit
                if imit == -1:
                    e.RECERR = True
                iset += 1
                if iset > e.IYM:
                    e.IYM = iset
            e.ISET = iset
            e.JCOUNT = iset
    elif kt == "END":
        e.IEND = True
        if not e.RECERR:
            e.NREC = e.NREC + e.ICOUNT * e.JCOUNT
        e.ISTA = False
        e.NEWID = True
    elif kt not in ("ELEV", "FLAG", "HILL", "ORIG"):
        e.RECERR = True
        return
    e.PNETID = e.NETIDT


def set_window(e):
    """SET_WINDOW: ventana de siglo para los años de 2 cifras (ME SURFDATA)."""
    m = "SET_WINDOW"
    ok = False
    if 4 <= e.IFC <= 7:
        e.FNUM, imit = num(e, 4, e.FNUM)
        e.IMIT = imit
        if imit == 1:
            ok = True
    if not ok:
        e.ISTRT_CENT = 19
        e.ISTRT_WIND = 50
        return
    e.ISYEAR = nint(e.FNUM)
    if 50 <= e.ISYEAR < 100:
        if not e.L_SKIPMESSAGES:
            e.errhdl(e.PATH, m, "W", "360", e.KEYWRD)
        e.ISTRT_CENT = 19
        e.ISTRT_WIND = 50
    elif e.ISYEAR < 50:
        if not e.L_SKIPMESSAGES:
            e.errhdl(e.PATH, m, "W", "360", e.KEYWRD)
        e.ISTRT_CENT = 20
        e.ISTRT_WIND = 0
    else:
        e.ISTRT_CENT = e.ISYEAR // 100
        e.ISTRT_WIND = e.ISYEAR - e.ISTRT_CENT * 100
        e.ISTRT_WIND = e.ISTRT_WIND - 1
        if e.ISTRT_WIND < 0:
            e.ISTRT_WIND = 0
        if e.ISTRT_CENT >= 21 and e.ISTRT_WIND >= 48:
            e.errhdl(e.PATH, m, "E", "365", e.KEYWRD)
            e.ISTRT_CENT = 21
            e.ISTRT_WIND = 47


# =============================================================================== ALLSETUP
def allsetup(e):
    """ALLSETUP: crea las matrices de entrada (las de opciones fuera de alcance no se crean)."""
    a = e.alloc
    if e.NUMBGSECTS < 1:
        e.NUMBGSECTS = 1
    if e.NUMO3SECTS < 1:
        e.NUMO3SECTS = 1
    if e.NUMNOXSECTS < 1:
        e.NUMNOXSECTS = 1
    nsrc, ngrp, nrec, nave, ntyp = e.NSRC, e.NGRP, e.NREC, e.NAVE, e.NTYP
    a("KAVE", nave)
    a("CHRAVE", nave)
    a("CHIDEP", 6, ntyp)
    a("OUTTYP", ntyp)
    for n in ("AXS", "AYS", "AZS", "AQS", "AHS", "ATS", "AVS", "ADS", "PLATELV", "PLATHB", "PLATWB",
              "OSPLAT", "SOPLAT", "ASYINI", "ASZINI", "AFP", "AXS1", "AYS1", "AXS2", "AYS2", "AWIDTH",
              "ADSFACT", "NDXSTK", "AWDSIN", "AWDCOS", "AAFV", "INPD", "EVAL", "URBSRC", "L_HRLYSIG",
              "L_FLATSRC", "L_METHOD2", "L_WAKEMESSAGE", "SRCID", "SRCTYP", "SOPCRD", "SOGAS", "QFLAG",
              "HBPSRC", "AFTSRC", "AMFUEL", "ATHRUST", "AVAA", "AAFR", "ABYPR", "ARPWR", "ASRCANGLE",
              "ABW", "ABL", "ABH", "ABA", "SWXS", "SWYS", "PDIFF", "PDIFFW", "RMOLWT", "ALPHAS",
              "REACT", "HENRY", "RCLI", "IELUNT", "EVLFIL"):
        a(n, nsrc)
    a("IGROUP", nsrc, ngrp)
    a("O3VARY", e.NO3F, e.NUMO3SECTS)
    for n in ("GRPID", "GRP_BACK", "IANPST", "IANPLT", "IAPUNT", "IANFRM", "IPPUNT", "ANNPST",
              "ANNPLT", "ISEAHR", "SEAHRS", "ISHUNT", "IMXDLY", "IMDUNT", "MAXDLY", "IMXDLY_BYYR",
              "IMDUNT_BYYR", "MAXDLY_BYYR", "MAXDCONT", "IMXDCUNT", "MAXDCONT_FILE", "MAXD_THRESH"):
        a(n, ngrp)
    for n in ("EMILBL", "OUTLBL", "PERLBL", "EMIFAC"):
        a(n, ntyp)
    a("BACKGRND", e.NBF, e.NUMBGSECTS)
    a("NOXVARY", e.NNOXF, e.NUMNOXSECTS)
    if e.NSEC > 0:
        for n in ("ADSBH", "ADSBW", "ADSBL", "ADSXADJ", "ADSYADJ"):
            a(n, e.NSEC, nsrc)
    if e.NQF > 0:
        a("QFACT", e.NQF, nsrc)
    if e.NPDMAX > 0:
        for n in ("APDIAM", "APHI", "APDENS", "AVGRAV", "ATSTOP"):
            a(n, e.NPDMAX, nsrc)
        for n in ("EFRAC", "QPART", "PDIAM", "PHI", "PDENS", "VGRAV", "TSTOP", "SCHMIDT", "VDEP",
                  "SCF", "WQCOR", "DQCOR", "PSCVRT", "WASHOUT", "ECOLL"):
            a(n, e.NPDMAX)
        a("FINEMASS", nsrc)
    if e.NVMAX > 0:
        for n in ("AXINIT", "AYINIT", "AANGLE", "AALPHA", "APDEFF", "AVOLUM", "RADIUS", "NVERTS",
                  "AXCNTR", "AYCNTR"):
            a(n, nsrc)
        a("AXVERT", e.NVMAX + 1, nsrc)
        a("AYVERT", e.NVMAX + 1, nsrc)
        for n in ("UVERT", "VVERT", "VNVERT", "WVERT", "UASEGS", "UBSEGS", "XVERT", "YVERT"):
            a(n, e.NVMAX + 1)
        a("SPA", e.NVMAX + 1, 2)
    # módulos RLINE_DATA y BUOYANT_LINE (sus variables existen siempre; las matrices, si hay fuentes)
    from . import fuente_linea_flotante, fuente_carretera
    fuente_carretera.reservar(e)
    fuente_linea_flotante.reservar(e)
    if e.NURB > 0:
        a("IURBGRP", nsrc, e.NURB)
        for n in ("URBID", "URBNAM", "URBPOP", "URBZ0", "ZIURB", "URBWSTR", "URBUSTR", "URBOBULEN",
                  "L_MORNINGTRANS"):
            a(n, e.NURB)
        for n in ("GRDSWU", "GRDSVU", "GRDTGU", "GRDPTU"):
            a(n, P["MXGLVL"], e.NURB)
    if e.NAFT > 0:
        a("AFTID", e.NAFT)
    if e.EVONLY:
        raise NoTraducido("EVENT (vía EV)")
    for n in ("AXR", "AYR", "AZELEV", "AZFLAG", "AZHILL", "IREF", "NETID", "RECTYP", "NDXARC",
              "SWXR", "SWYR"):
        a(n, nrec)
    a("ARCID", e.NARC)
    for n in ("NTID", "NTTYP", "XORIG", "YORIG", "NETSTA", "NETEND", "NUMXPT", "NUMYPT"):
        a(n, e.NNET)
    a("XCOORD", e.IXM, e.NNET)
    a("YCOORD", e.IYM, e.NNET)
    nval = e.NVAL
    a("NHIAVE", nval, nave)
    for n in ("MAXAVE", "IMXVAL", "IDYTAB", "INHI", "ITOXFL", "IRNKFL", "IRKVAL", "TOXTHR", "ITXUNT",
              "IRKUNT", "TOXFIL", "RNKFIL"):
        a(n, nave)
    for n in ("MAXFLE", "IPSTFL", "THRESH", "IMXUNT", "IPSUNT", "IPSFRM", "THRFIL", "PSTFIL"):
        a(n, ngrp, nave)
    for n in ("IPLTFL", "IPLUNT", "PLTFIL"):
        a(n, nval, ngrp, nave)
    a("MXD_RANK", ngrp, 2)
    a("IDCONC", nave, P["NPAIR"])
    a("TXCONC", nave, P["NPAIR"])
    a("WORKID", nsrc + 1)
    a("IWRK2", nsrc, 13)
    for n in ("ZETMP1", "ZETMP2", "ZHTMP1", "ZHTMP2", "ZFTMP1", "ZFTMP2"):
        a(n, nrec)
    # auxiliares de la traducción para el núcleo compilado de PVMRM (tipo PSD y QTK por fuente)
    e.PSDC = np.zeros(nsrc + 1, dtype=np.int64)
    e.QTKSRC = np.zeros(nsrc + 1)
    if e.PVMRM or e.OLM or e.ARM2 or e.RUNTTRM or e.GRSM:
        _allsetup_no2(e, a, nsrc, nrec, ntyp, ngrp)


def _allsetup_no2(e, a, nsrc, nrec, ntyp, ngrp):
    """Matrices de la química del NO2 (ALLSETUP) con los valores iniciales de VARINI."""
    a("ANO2_RATIO", nsrc)
    a("CHI", nrec, nsrc, ntyp)
    if e.PVMRM or e.GRSM:
        for n in ("HECNTR", "HECNTR3", "UEFFS", "UEFF3S", "EPSEF", "EPSEF3", "FOPTS", "PPFACT"):
            a(n, nrec, nsrc)
    if e.OLM:
        a("OLMID", e.NOLM)
        a("L_OLMGRP", nsrc)
        a("IGRP_OLM", nsrc, e.NOLM)
    if e.RUNTTRM:
        a("TTRMOUT", nrec, nsrc, 25)
        a("TTRMSRC", nrec, nsrc)
        for n in ("TTRMINST", "TTRMFRAC", "TTRMSUB", "TTRMNO2", "TTRMFRAC_PRM", "TTRMFRAC_AER"):
            a(n, ntyp)
        a("L_TTRMSRCTYP", nsrc)
        a("TTRMCOMPARE", ngrp, nsrc, nrec, ntyp)
    if e.PSDCREDIT:
        a("PSDSRCTYP", nsrc)
        a("PSDID", e.NPSD)
        a("L_PSDGRP", nsrc)
        a("IGRP_PSD", nsrc, e.NPSD)
        a("ABVAL", nrec, ntyp)
        a("BCVAL", nrec, ntyp)
    if e.GRSM:
        a("CHI_TTRAVCHM", nrec, nsrc)
        a("BLDFAC", nrec, nsrc)
        a("TTRAVCHM", nrec)
    if e.PVMRM or e.OLM or e.GRSM:
        e.ANO2_RATIO[:] = -9.0


# =============================================================================== ALLRESULT
def allresult(e):
    """ALLRESULT: memoria estimada (STORE, en precisión simple) y matrices de resultados."""
    f = F32
    e.NARC = e.NUMARC
    e.NMXVAL = max(int(e.IRKVAL[1:].max()), int(e.IMXVAL[1:].max()))
    rsrc, rsec, rgrp, rrec = f(e.NSRC), f(e.NSEC), f(e.NGRP), f(e.NREC)
    rurb, rarc, rave, rhival = f(e.NURB), f(e.NARC), f(e.NAVE), f(e.NHIVAL)
    rtyp, rmaxval, rnet, rxm, rym = f(e.NTYP), f(e.NMXVAL), f(e.NNET), f(e.IXM), f(e.IYM)
    rolm, rpsd, rqf, rpdmax, rvmax = f(e.NOLM), f(e.NPSD), f(e.NQF), f(e.NPDMAX), f(e.NVMAX)
    if e.RUNTTRM:
        rolm = f(1.0)
    rpair, rhiann, ryears, rhimxdly, raft = f(P["NPAIR"]), f(P["NHIANN"]), f(e.NYEARS), f(e.NHIMXDLY), f(e.NAFT)
    store = f(0.0)
    if not e.EVONLY:
        store = (rsrc * (f(54.) + rqf + f(5.) * rsec + f(5.) * rpdmax + f(2.) * rvmax
                         + f(0.5) * (rgrp + rurb + raft))
                 + rpdmax * f(14.)
                 + rrec * (f(9.) + rhival * rgrp * rave * rtyp * f(1.75) + rgrp * rave * rtyp
                           + f(2.) * rgrp * rtyp + rgrp)
                 + rarc * f(20.) + rnet * (f(9.) + rxm + rym)
                 + rhival * (rgrp * rave * rtyp * f(3.))
                 + rmaxval * (rgrp * rave * rtyp * f(2.25))
                 + rhiann * f(1.5) * rgrp * rtyp
                 + rave * (f(12.) + f(2.) * rpair + f(3.) * rhival * rgrp + f(8.) * rgrp)
                 + rgrp * f(11.) + rtyp * f(38.) + rvmax * f(20.))
        if e.SEASONHR:
            store = store + (f(4.) * f(24.) * rrec * rgrp * rtyp)
        if e.PVMRM or e.OLM or e.RUNTTRM or e.GRSM or e.RUNTTRM2:
            # ARM2 no entra en esta estimación en el original
            store = store + (rsrc + rsrc * rrec * rtyp)
            if e.PVMRM:
                store = store + (f(8.) * rsrc * rrec)
                if e.PSDCREDIT:
                    store = store + (rsrc * (f(2.) + rpsd) + rrec * f(2.) * rtyp)
            elif e.OLM or e.RUNTTRM:
                store = store + (f(0.5) * rolm * rsrc + rolm + rsrc)
            elif e.GRSM:
                store = store + (f(8.) * rsrc * rrec)
                store = store + rrec + (f(2.) * rrec * rsrc)
                store = store + (f(6.) * rsrc)
        if e.PM25AVE or e.NO2AVE or e.SO2AVE:
            store = store + rrec * rgrp * (f(1.5) + f(1.5) * rhimxdly + f(1.5) * rhimxdly * ryears)
        if e.L_MAXDCONT:
            h = f(8784.)
            mxg = f(P["MXGLVL"])
            store = store + ryears * (f(19.) * h + f(10.) * h + f(7.) * h * mxg)
            if e.LDGAS or e.LDPART or e.LWGAS or e.LWPART or e.GRSM:
                store = store + ryears * f(14.) * h
            if e.NSEC > 0:
                store = store + ryears * h * mxg
            if e.PVMRM or e.GRSM:
                store = store + ryears * h * mxg
            if e.PVMRM or e.OLM or e.RUNTTRM or e.GRSM:
                store = store + ryears * h
            if e.GRSM:
                store = store + ryears * h
            if e.L_BACKGRND:
                store = store + ryears * h
            if e.HOURLY:
                store = store + ryears * f(2 * 8784) * rsrc
                if e.NPNT > 0:
                    store = store + ryears * f(2 * 8784) * rsrc
                if e.NVOL > 0 or e.NVMAX > 0:
                    store = store + ryears * f(2 * 8784) * rsrc
            if e.NURB > 0:
                store = store + f(4 * 8784 * P["MXGLVL"] * e.NYEARS * e.NURB) + f(4 * 8784 * P["MXGLVL"] * e.NYEARS) \
                    + f(5 * 8784 * e.NYEARS * e.NURB)
        store = store * f(8.) / f(1.048576e6) + f(3.5)
    e.STORE = float(store)
    a = e.alloc
    nt, ng, na, nr, nh = e.NUMTYP, e.NUMGRP, e.NUMAVE, e.NUMREC, e.NHIVAL
    for n in ("HRVAL", "AERVAL", "PRMVAL"):
        a(n, nt)
    a("BACKAVE", ng)
    a("BACKANN", ng)
    if e.NARC > 0:
        for n in ("ARCMAX", "QMAX", "DXMAX", "UMAX", "SVMAX", "SWMAX", "SYMAX", "SY3MX", "U3MAX",
                  "HEMAX", "ARCCL", "SZMAX", "CHIDMW", "CHINMW", "CHI3MW", "CHIDML", "CHINML",
                  "CHI3ML", "HSBLMX"):
            a(n, e.NARC)
    a("AVEVAL", nr, ng, na, nt)
    a("HIVALU", nr, nh, ng, na, nt)
    for n in ("HMAX", "HMLOC", "HMDATE"):
        a(n, nh, ng, na, nt)
    a("NHIDAT", nr, nh, ng, na, nt)
    if e.PERIOD or e.ANNUAL:
        a("ANNVAL", nr, ng, nt)
        a("AMXVAL", P["NHIANN"], ng, nt)
        a("IMXLOC", P["NHIANN"], ng, nt)
    for n in ("RMXVAL", "MXDATE", "MXLOCA"):
        a(n, e.NMXVAL, ng, na, nt)
    for n in ("NUMHRS", "NUMCLM", "NUMMSG"):
        a(n, na)
    if e.SEASONHR:
        a("SHVALS", nr, ng, 4, 24, nt)
        if e.L_BACKGRND:
            a("BACKSEASHR", ng, 4, 24)
    if e.PM25AVE or e.NO2AVE or e.SO2AVE:
        e.NHIMXDLY = max(e.NHIMXDLY, nh)
        a("MXDVAL", nr, ng)
        a("HIMXDLY", nr, ng, e.NHIMXDLY)
        a("HIMXDLY_BYYR", nr, ng, e.NHIMXDLY, e.NYEARS)
        a("IMXDHR", nr, ng)
        a("NHIDATMXD", nr, ng, e.NHIMXDLY)
        a("NHIDATMXD_BYYR", nr, ng, e.NHIMXDLY, e.NYEARS)
    a("HCLMSG", nr, nh, ng, na, nt)
    a("MCLMSG", e.NMXVAL, ng, na, nt)
    a("HMCLM", nh, ng, na, nt)
    if e.ANNUAL:
        a("SUMANN", nr, ng, nt)
    if e.PM25AVE or e.NO2AVE or e.SO2AVE:
        a("SUMHNH", nr, ng, nh)
        a("MXPMVAL", P["NMXPM"], ng, nh)
        a("MXPMLOC", P["NMXPM"], ng, nh)
    if e.L_MAXDCONT and not e.EVONLY:
        # meteorología, fondo y emisiones horarias guardadas para recalcular los días de MAXDCONT
        ny, mx = e.NYEARS, P["MXGLVL"]
        for n in ("ASFCHF", "AUREF", "AUREFHT", "ATA", "ATREFHT", "AWDREF", "AUSTAR", "AWSTAR", "AZICONV",
                  "AZIMECH", "AOBULEN", "AVPTGZI", "ASFCZ0", "AKST", "ABLTA", "ACLMHR", "AMSGHR", "AUNSTAB",
                  "ASTABLE", "AURBSTAB", "ANTGLVL", "AUATZI", "ASVATZI", "ASWATZI", "AUAVG", "ASVAVG", "ASWAVG",
                  "APTATZI", "ANDX4ZI", "ARURUSTR", "ARUROBULEN"):
            a(n, 8784, ny)
        for n in ("AGRIDHT", "AGRIDWD", "AGRIDWS", "AGRIDSW", "AGRIDSV", "AGRIDTG", "AGRIDPT"):
            a(n, 8784, mx, ny)
        if e.HBPLUME:
            a("AZICONVN", 8784, ny)
            a("AZIMECHN", 8784, ny)
        if e.PVMRM or e.GRSM:
            a("AGRIDEPS", 8784, mx, ny)
        if e.PVMRM or e.GRSM or e.OLM or e.RUNTTRM:
            a("AO3CONC", 8784, ny)
        if e.GRSM:
            a("ANOXBGCONC", 8784, ny)
        if e.L_BACKGRND:
            a("ABGCONC", 8784, ny)
        if e.NSEC > 0:
            a("AGRIDRHO", 8784, mx, ny)
        if e.LDGAS or e.LDPART or e.LWPART or e.LWGAS or e.GRSM:
            for n in ("ABOWEN", "AALBEDO", "AWNEW", "AWOLD", "AESTA", "AF2", "APREC1", "APREC2", "APRATE",
                      "ARH", "ASFCP", "AQSW", "IAPCODE", "NACLOUD"):
                a(n, 8784, ny)
        if e.HOURLY:
            a("AAQS", 8784, ny, e.NSRC)
            a("AAHS", 8784, ny, e.NSRC)
            if e.NPNT > 0:
                a("AAVS", 8784, ny, e.NSRC)
                a("AATS", 8784, ny, e.NSRC)
            if e.NVOL > 0 or e.NVMAX > 0:
                a("AASYINI", 8784, ny, e.NSRC)
                a("AASZINI", 8784, ny, e.NSRC)
            from . import fuente_linea_flotante
            fuente_linea_flotante.reservar_resultados_bl(e)
        if e.NURB > 0:
            for n in ("AGRDSWR", "AGRDSVR", "AGRDTGR", "AGRDPTR"):
                a(n, 8784, mx, ny)
            for n in ("AGRDSWU", "AGRDSVU", "AGRDTGU", "AGRDPTU"):
                a(n, 8784, mx, ny, e.NURB)
            for n in ("AZIURB", "AURBWSTR", "AURBUSTR", "AURBOBULEN", "AL_MORNINGTRANS"):
                a(n, 8784, ny, e.NURB)


# =============================================================================== VARINI
def varini(e):
    """VARINI: valores iniciales de las variables (tras ALLSETUP)."""
    import math
    e.PI = 4.0 * math.atan(1.0)
    e.TWOPI = 2.0 * e.PI
    e.RTOFPI = math.sqrt(e.PI)
    e.SRT2PI = math.sqrt(e.TWOPI)
    e.RTOF2 = math.sqrt(2.0)
    e.RTPIBY2 = math.sqrt(e.PI / 2.0)
    e.RT2BYPI = math.sqrt(2.0 / e.PI)
    e.DTORAD = e.PI / 180.0
    e.RTODEG = 180.0 / e.PI
    e.THIRD = 1.0 / 3.0
    e.TWOTHIRDS = 2.0 / 3.0
    e.IPNUM = e.IPPNUM = e.NDUMP = e.IMETMSG = 0
    e.POLLUT = "undefine"
    for n in ("ISTART", "ERRLST", "DFAULT", "CONC", "DEPOS", "DDEP", "WDEP", "RURAL", "URBAN",
              "GRDRIS", "NOSTD", "NOBID", "NOWARN", "PERIOD", "ANNUAL", "MONTH", "FLAT", "FLGPOL",
              "RUN", "EVENTS", "RSTSAV", "RSTINP", "MULTYR", "DAYTAB", "MXFILE", "PPFILE", "PLFILE",
              "SUMMFILE", "ARCFT", "TXFILE", "RKFILE", "ANPOST", "ANPLOT", "RECERR", "PFLERR",
              "ENDMON", "CALCS", "SURFAC", "DEBUG", "METEORDBG", "AREADBG", "PRIMEDBG", "OLMDEBUG",
              "ARM2DEBUG", "PVMRMDBG", "GRSMDEBUG", "DEPOSDBG", "PLATFMDBG", "BARDBG", "EDGEDBG",
              "VBRDBG", "WAKE", "SCREEN", "HOURLY", "ARCFTDEBUG", "L_BLHOURLY", "POLLCRIT",
              "AWMADWDBG", "LDPART", "LWPART", "LWGAS", "LDGAS", "DDPLETE", "WDPLETE", "ARDPLETE",
              "WETDPLT", "DRYDPLT", "NOWETDPLT", "NODRYDPLT", "SOCONT", "DETAIL", "L_VECTORWS",
              "L_USERSVMIN", "L_USERWSMIN", "L_USERFRANMAX", "L_USERSWMIN", "L_USERBIGT",
              "L_USERFRANMIN", "L_PBAL", "RUNTTRM", "TTRMDBG", "RUNTTRM2", "TTRM2DBG", "HBPLUME",
              "HBPDBG", "URBDBUG", "BLPDBUG", "L_ADJUSTAR", "L_BULKRN", "L_MMIF_DATA",
              "L_MMIF_PROFILE", "L_TURBDATA", "L_COARE", "LUSERVD", "SCIM", "SCIMOUT", "SCIMHR",
              "SEASONHR", "BETA", "PM25AVE", "NO2AVE", "SO2AVE", "L_NO_PM25AVE", "L_NO_NO2AVE",
              "L_NO_SO2AVE", "L_O3HOURLY", "L_BACKGRND", "L_BGHOURLY", "L_NOXHOURLY",
              "L_CALCNOXFROMNO2", "L_DAYOFWEEKOPTS", "MXDAILY", "L_MAXDCONT", "MXDAILY_BYYR",
              "L_SKIPMESSAGES", "L_NAD_ADJ_FLAGS", "L_OLDMETVER", "FASTAREA", "FASTALL",
              "L_EFFSIGY", "L_NONDFAULT", "NOCHKD", "L_WARNCHKD", "L_EVENT_ORIGCONC_WARNING",
              "L_MAXDCONT_ORIGCONC_WARNING"):
        setattr(e, n, False)
    e.IFINIS = True
    e.MSGPRO = True
    e.CLMPRO = True
    e.ELEV = True
    e.ECHO = True
    e.L_URBANTRANSITION = True
    if e.L_MORNINGTRANS is not None:
        e.L_MORNINGTRANS[:] = False
    e.TURBOPTS[:] = False
    for n in ("L_O3FILE", "L_O3VAL", "L_O3VALUES", "L_BGFILE", "L_BGVALUES", "L_NOXVALUE",
              "L_NOX_VALS", "L_NOXFILE"):
        getattr(e, n)[:] = False
    e.IBKGRD[:] = 0
    if e.FILE_FORMAT != "EXP":
        e.FILE_FORMAT = "FIX"
    e.REELEV = "METERS"
    e.SOELEV = "METERS"
    e.DECOEF = 0.0
    e.PREC1 = e.PREC2 = 0.0
    e.TOTAL_PRECIP = 0.0
    e.WOLD = 180.0
    e.F2 = e.WOLD / 200.0
    e.FO = 0.0
    e.FSEAS2 = 0.5
    e.FSEAS5 = 0.25
    e.ISRC = 0
    for n in ("SOPCRD", "SOGAS", "URBSRC", "AFTSRC"):
        l = getattr(e, n)
        for i in range(1, len(l)):
            l[i] = "N"
    if e.O3VARY is not None:
        e.O3VARY[:] = -99.0
    if e.NOXVARY is not None:
        e.NOXVARY[:] = -99.0
    for n in ("O3FLAG", "BFLAG", "NOXFLAG"):
        l = getattr(e, n)
        for i in range(1, len(l)):
            l[i] = ""
    if not e.L_O3SECTOR:
        e.NUMO3SECTS = 1
    if not e.L_BGSECTOR:
        e.NUMBGSECTS = 1
    if not e.L_NOXSECTOR:
        e.NUMNOXSECTS = 1
    e.NSUBBGHOUR = 0
    e.DQCORG = 1.0
    e.WQCORG = 1.0
    if e.WQCOR is not None:
        e.WQCOR[:] = 1.0
    if e.DQCOR is not None:
        e.DQCOR[:] = 1.0
    e.IREC = 0
    e.ISTA = e.IEND = False
    e.IRXR = e.IRYR = e.IRZE = e.IRZH = e.IRZF = 0
    e.NEWID = True
    e.ITAB = -9
    e.NXTOX = e.NYTOX = 0
    e.ISJDAY = 0
    e.IEJDAY = 366
    e.ISDATE = 0
    e.IEDATE = 2147123124
    e.ISYR = e.ISMN = e.ISDY = e.ISHR = 0
    e.IEYR = 9999
    e.IEMN = 99
    e.IEDY = 99
    e.IEHR = 24
    e.IPDATE = e.IPHOUR = e.IMONTH = e.IDAY = e.IHOUR = e.IYEAR = 0
    e.NUMYRS = e.NREMAIN = e.IHR_NDX = e.IYR_NDX = 0
    e.INCRST = 1
    e.SFX = e.SFY = e.UAX = e.UAY = e.ROTANG = 0.0
    e.O3MISS = False
    e.O3BACK[:] = -999.0
    e.O3CONC = -999.0
    e.NO2EQUIL = 0.90
    e.NO2STACK = -9.0
    e.IOLM = 0
    e.NOXMISS = False
    e.NOXBACK[:] = -999.0
    e.NOXBGCONC = -999.0
    e.ITTRM = 0
    e.METINP = ""
    e.PROINP = ""
    e.METFRM = "FREE"
    e.PROFRM = "FREE"
    e.XINT = 0.0
    e.YINT = 0.0
    e.TITLE1 = ""
    e.TITLE2 = ""
    e.IPAGE = e.IPGSUM = e.NHIVAL = e.NMXVAL = 0
    e.THRFRM = "(1X,I3,1X,A8,1X,I8.8,2(1X,F13.5),3(1X,F7.2),1X,F13.5)"
    e.PSTFRM = "(3(1X,F13.5),3(1X,F8.2),2X,A6,2X,A8,2X,I8.8,2X,A8)"
    e.PLTFRM = "(3(1X,F13.5),3(1X,F8.2),3X,A5,2X,A8,2X,A5,5X,A8,2X,I8)"
    e.RNKFRM = "(1X,I6,1X,F13.5,1X,I8.8,2(1X,F13.5),3(1X,F7.2),2X,A8)"
    e.MXDFRM = "(3(1X,F13.5),3(1X,F8.2),2X,A6,2X,A8,2X,I4,2X,I3,2X,I8.8,2X,A8)"
    e.SAVFIL = e.MSGFIL = e.EVFILE = e.SUMFIL = ""
    for n in ("BKGRND_FILE", "OZONFL", "NOXFL"):
        l = getattr(e, n)
        for i in range(1, len(l)):
            l[i] = ""
    e.IERROR = e.NFATAL = e.NWARN = 0
