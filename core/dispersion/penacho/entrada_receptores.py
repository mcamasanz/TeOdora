# -*- coding: utf-8 -*-
"""Traducción de AERMOD 26135 (US EPA, dominio público): vía RE (reset.f).

RECARD con GRIDCART, GRIDPOLR, DISCCART, DISCPOLR, EVALCART, ELEVUNIT e INCLUDED.

Peculiaridades del original que se replican:
  · IHLSET (redes con alturas HILL) no se reinicia al empezar cada red: el aviso 214 por falta de
    HILL solo puede salir mientras ninguna red anterior las haya dado.
  · Los contadores de opciones de GRIDPOLR (ORIG, DIST, GDIR, DDIR) son locales con SAVE.
  · DISCPOLR con una fuente inexistente sobrescribe NETID, RECTYP e IREF del receptor anterior."""
import math

from . import control
from .control import dbl, sindex
from .estado import NoTraducido
from .formato import fc, fwrite


def recard(e):
    """RECARD: claves de la vía RE."""
    m = "RECARD"
    k = e.KEYWRD
    if k == "STARTING":
        e.IREC = e.INNET = e.NUMREC = e.NUMARC = 0
        e.IRXR = e.IRYR = e.IRZE = e.IRZH = e.IRZF = 0
        e.PXSOID = ""
        e.PESOID = ""
        e.ISTA = False
        e.IRSTAT[1] += 1
        if e.IRSTAT[1] != 1:
            e.errhdl(e.PATH, m, "E", "135", k)
        e.ZETMP1[:] = 0.0
        e.ZETMP2[:] = 0.0
        e.ZFTMP1[:] = 0.0
        e.ZFTMP2[:] = 0.0
    elif k == "GRIDCART":
        e.IRSTAT[2] += 1
        recart(e)
    elif k == "GRIDPOLR":
        e.IRSTAT[3] += 1
        repolr(e)
    elif k == "DISCCART":
        e.IRSTAT[4] += 1
        discar(e)
    elif k == "DISCPOLR":
        e.IRSTAT[5] += 1
        dispol(e)
    elif k == "EVALCART":
        e.IRSTAT[8] += 1
        if e.PSDCREDIT:
            e.errhdl(e.PATH, m, "E", "147", k)
        else:
            evcart(e)
    elif k == "ELEVUNIT":
        e.IRSTAT[9] += 1
        if e.IRSTAT[9] != 1:
            e.errhdl(e.PATH, m, "E", "135", k)
        elif (e.IRSTAT[2] > 0 or e.IRSTAT[3] > 0 or e.IRSTAT[4] > 0 or e.IRSTAT[5] > 0
              or e.IRSTAT[8] > 0):
            e.errhdl(e.PATH, m, "E", "152", "  RE")
        else:
            reelun(e)
    elif k == "INCLUDED":
        e.IRSTAT[11] += 1
        ilsave = e.ILINE
        control.includ(e)
        e.ILINE = ilsave
    elif k == "FINISHED":
        e.IRSTAT[50] += 1
        if e.IRSTAT[50] != 1:
            e.errhdl(e.PATH, m, "E", "135", k)
            return
        if e.IRSTAT[1] == 0:
            e.errhdl(e.PATH, m, "E", "130", "STARTING")
        if e.ISTA:
            e.errhdl(e.PATH, m, "E", "175", e.PNETID)
        e.NUMREC = e.IRXR
        if e.NUMREC == 0:
            e.errhdl(e.PATH, m, "E", "185", "NUMREC=0")
        if not e.FLGPOL:
            e.AZFLAG[1:e.NUMREC + 1] = 0.0
        for irec in range(1, e.NUMREC + 1):
            e.IREC = irec
            if e.AZELEV[irec] < -9998.99 or e.AZHILL[irec] < -9998.99:
                e.DUMMY = fwrite("(I8)", irec)[0]
                e.errhdl(e.PATH, m, "E", "259", e.DUMMY)
            elif e.REELEV == "FEET":
                e.AZELEV[irec] = 0.3048 * e.AZELEV[irec]
                e.AZHILL[irec] = 0.3048 * e.AZHILL[irec]
        e.IREC = e.NUMREC + 1
        from . import fuente_linea_flotante, fuente_carretera
        fuente_linea_flotante.recard_bl(e)
        if e.BAREDGE and e.SBARDCL:
            fuente_carretera.baredgezone(e)
        elif e.BAREDGE and not e.SBARDCL:
            e.errhdl(e.PATH, m, "W", "274", k)
            e.BAREDGE = False
    else:
        e.errhdl(e.PATH, m, "E", "110", k)


def reelun(e):
    """REELUN: unidades de la cota de los receptores."""
    m = "REELUN"
    if e.IFC == 3:
        if e.FIELD[3] == "METERS":
            e.REELEV = "METERS"
        elif e.FIELD[3] == "FEET":
            e.REELEV = "FEET"
        else:
            e.errhdl(e.PATH, m, "E", "203", "RE_ELEV")
    elif e.IFC > 3:
        e.errhdl(e.PATH, m, "E", "202", e.KEYWRD)
    else:
        e.errhdl(e.PATH, m, "E", "200", "ElevUnit")


def _id_red(e, m, claves):
    """Identificador de red y tipo de línea (común a RECART y REPOLR). False si hay error."""
    if e.IFC < 3:
        e.errhdl(e.PATH, m, "E", "200", e.KEYWRD)
        return False
    netidt = fc(e.FIELD[3], 8)
    if not e.NEWID and netidt in claves:
        netidt = e.PNETID
        e.KTYPE = fc(e.FIELD[3], 5)
    elif not e.NEWID and netidt == e.PNETID:
        e.KTYPE = fc(e.FIELD[4], 5)
    elif e.NEWID and netidt != "":
        e.NEWID = False
        e.KTYPE = fc(e.FIELD[4], 5)
        e.INNET += 1
        if e.INNET > e.NNET:
            e.NETIDT = netidt
            e.DUMMY = fwrite("('NNET=',I7)", e.NNET)[0]
            e.errhdl(e.PATH, m, "E", "290", e.DUMMY)
            e.RECERR = True
            return False
        e.NETIDT = netidt
        return "nueva"
    else:
        e.NETIDT = netidt
        e.errhdl(e.PATH, m, "E", "170", e.PNETID)
        e.RECERR = True
        return False
    e.NETIDT = netidt
    return True


def _sta(e, m):
    e.ISTA = True
    e.IEND = False
    e.NEWID = False
    e.RECERR = False
    e.ICOUNT = e.JCOUNT = 0
    e.IZE = e.IZH = e.IZF = 0
    e.IDC1 = e.IRXR
    for i in range(1, e.INNET):
        if e.FIELD[3] == e.NTID[i]:
            e.errhdl(e.PATH, m, "W", "252", e.NTID[i])


def _fin_red(e, m):
    """Comprobaciones comunes al END de una red (cotas, alturas de colina y de receptor)."""
    if e.ELEV and (e.IEVSET == 0 or e.IHLSET == 0):
        e.errhdl(e.PATH, m, "W", "214", e.NETIDT)
        e.IRZE = e.IRXR
        e.IRZH = e.IRZE
    elif e.FLAT and e.IEVSET != 0:
        e.errhdl(e.PATH, m, "W", "213", e.NETIDT)
        e.IRZE = e.IRXR
        e.IRZH = e.IRZE
    elif e.FLAT and e.IEVSET == 0:
        e.IRZE = e.IRXR
        e.IRZH = e.IRZE
    if e.FLGPOL and e.IFGSET == 0:
        e.errhdl(e.PATH, m, "W", "216", e.NETIDT)
        e.IRZF = e.IRXR
    elif not e.FLGPOL and e.IFGSET != 0:
        e.errhdl(e.PATH, m, "W", "215", e.NETIDT)
        e.IRZF = e.IRXR
    elif not e.FLGPOL and e.IFGSET == 0:
        e.IRZF = e.IRXR
    n = e.ICOUNT * e.JCOUNT
    if e.ELEV and e.IEVSET != 0:
        if n != e.IZE:
            e.errhdl(e.PATH, m, "E", "218", "ELEV")
        if n != e.IZH:
            e.errhdl(e.PATH, m, "E", "218", "ZHILL")
    if e.FLGPOL and e.IFGSET != 0:
        if n != e.IZF:
            e.errhdl(e.PATH, m, "E", "218", "FLAG")


def recart(e):
    """RECART: red cartesiana (GRIDCART)."""
    m = "RECART"
    r = _id_red(e, m, ("", "XYINC", "XPNTS", "YPNTS", "ELEV", "HILL", "FLAG", "END"))
    if not r:
        return
    if r == "nueva":
        e.INCSET = e.IXYSET = e.IEVSET = e.IFGSET = 0
    kt = e.KTYPE
    if kt == "STA":
        _sta(e, m)
    elif kt == "XYINC":
        if not e.ISTA:
            e.errhdl(e.PATH, m, "E", "200", "  STA   ")
        if e.IXYSET != 0:
            e.errhdl(e.PATH, m, "E", "180", e.NETIDT)
        gencar(e)
        e.INCSET += 1
    elif kt in ("XPNTS", "YPNTS"):
        if not e.ISTA:
            e.errhdl(e.PATH, m, "E", "200", "  STA   ")
        if e.INCSET != 0:
            e.errhdl(e.PATH, m, "E", "180", e.NETIDT)
        xypnts(e)
        e.IXYSET += 1
    elif kt == "ELEV":
        if not e.ISTA:
            e.errhdl(e.PATH, m, "E", "200", "  STA   ")
        _hgt(e, "ELEV", "TERHGT")
        e.IEVSET += 1
    elif kt == "HILL":
        if not e.ISTA:
            e.errhdl(e.PATH, m, "E", "200", "  STA   ")
        _hgt(e, "HILL", "HILHGT")
        e.IHLSET += 1
    elif kt == "FLAG":
        if not e.ISTA:
            e.errhdl(e.PATH, m, "E", "200", "  STA   ")
        _hgt(e, "FLAG", "FLGHGT")
        e.IFGSET += 1
    elif kt == "END":
        e.IEND = True
        if not e.ISTA:
            e.errhdl(e.PATH, m, "E", "200", "  STA   ")
        elif not e.RECERR:
            setcar(e)
        e.ISTA = False
        e.NEWID = True
        if e.IXYSET == 0 and e.INCSET == 0:
            e.errhdl(e.PATH, m, "E", "212", e.NETIDT)
        _fin_red(e, m)
    else:
        e.errhdl(e.PATH, m, "E", "170", e.NETIDT)
        e.RECERR = True
        return
    e.PNETID = e.NETIDT


def _isc(e, clave):
    for i in range(1, e.IFC + 1):
        if e.FIELD[i] == clave:
            e.ISC = i + 1


def gencar(e):
    """GENCAR: red cartesiana a partir de origen, número de puntos e incremento."""
    m = "GENCAR"
    _isc(e, "XYINC")
    isc = e.ISC
    if e.IFC == isc - 1:
        e.errhdl(e.PATH, m, "E", "200", e.KEYWRD)
        e.RECERR = True
        return
    elif e.IFC > isc + 5:
        e.errhdl(e.PATH, m, "E", "202", e.KTYPE)
        e.RECERR = True
        return
    elif e.IFC < isc + 5:
        e.errhdl(e.PATH, m, "E", "201", e.KTYPE)
        e.RECERR = True
        return
    tempp = [0.0] * 7
    error = False
    for k in range(1, 7):
        tempp[k], imit = dbl(e, isc + k - 1, tempp[k])
        e.IMIT = imit
        if imit != 1:
            e.errhdl(e.PATH, m, "E", "208", e.KEYWRD)
            error = True
            e.RECERR = True
    if error:
        return
    from .formato import nint
    e.XINT = tempp[1]
    e.ICOUNT = nint(tempp[2])
    xdelta = tempp[3]
    e.YINT = tempp[4]
    e.JCOUNT = nint(tempp[5])
    ydelta = tempp[6]
    if e.ICOUNT <= e.IXM:
        for i in range(1, e.ICOUNT + 1):
            e.XCOORD[i, e.INNET] = e.XINT + xdelta * float(i - 1)
    else:
        e.DUMMY = fwrite("('IXM =',I7)", e.IXM)[0]
        e.errhdl(e.PATH, m, "E", "290", e.DUMMY)
    if e.JCOUNT <= e.IYM:
        for j in range(1, e.JCOUNT + 1):
            e.YCOORD[j, e.INNET] = e.YINT + ydelta * float(j - 1)
    else:
        e.DUMMY = fwrite("('IYM =',I7)", e.IYM)[0]
        e.errhdl(e.PATH, m, "E", "290", e.DUMMY)


def _lista_coord(e, m, clave, cuenta, coord, lim, nomlim, polar=False):
    """XPNTS/YPNTS/DIST/DDIR: lista de coordenadas que se añade a la red."""
    _isc(e, clave)
    if e.IFC == e.ISC - 1:
        e.errhdl(e.PATH, m, "E", "200", e.KEYWRD)
        e.RECERR = True
        return cuenta
    iset = cuenta
    for i in range(e.ISC, e.IFC + 1):
        e.DNUM, imit = dbl(e, i, e.DNUM)
        e.IMIT = imit
        if imit != 1:
            e.errhdl(e.PATH, m, "E", "208", e.KEYWRD)
            e.RECERR = True
        iset += 1
        if iset <= lim:
            coord[iset, e.INNET] = e.DNUM
            if polar:
                if coord[iset, e.INNET] > 360.0:
                    coord[iset, e.INNET] = coord[iset, e.INNET] - 360.0
                elif coord[iset, e.INNET] <= 0.0:
                    coord[iset, e.INNET] = coord[iset, e.INNET] + 360.0
            for j in range(1, iset):
                if e.DNUM == coord[j, e.INNET]:
                    e.errhdl(e.PATH, m, "W", "250", e.NETIDT)
        else:
            e.DUMMY = fwrite("('" + nomlim + " =',I7)", lim)[0]
            e.errhdl(e.PATH, m, "E", "290", e.DUMMY)
            e.RECERR = True
    e.ISET = iset
    return iset


def xypnts(e):
    """XYPNTS: red cartesiana a partir de listas de X e Y."""
    m = "XYPNTS"
    if e.KTYPE == "XPNTS":
        e.ICOUNT = _lista_coord(e, m, "XPNTS", e.ICOUNT, e.XCOORD, e.IXM, "IXM")
    elif e.KTYPE == "YPNTS":
        e.JCOUNT = _lista_coord(e, m, "YPNTS", e.JCOUNT, e.YCOORD, e.IYM, "IYM")


def _volcar_z(e, m, tmp1, tmp2, n, irz, dest, cod="290"):
    """SBYVAL + copia de las cotas/alturas ordenadas por fila (parte común de SETCAR y SETPOL)."""
    sbyval(tmp1, tmp2, n)
    iset = irz
    for i in range(1, n + 1):
        iset += 1
        if iset > e.NREC:
            e.DUMMY = fwrite("('NREC=',I7)", e.NREC)[0]
            e.errhdl(e.PATH, m, "E", cod, e.DUMMY)
            return None
        dest[iset] = tmp2[i]
    return iset


def _malla(e, m, polar):
    if e.ICOUNT != 0 and e.JCOUNT != 0:
        innet = e.INNET
        e.NETSTA[innet] = e.IRXR + 1
        iset = e.IRXR
        jset = e.IRYR
        for j in range(1, e.JCOUNT + 1):
            for i in range(1, e.ICOUNT + 1):
                iset += 1
                jset += 1
                if iset > e.NREC:
                    e.DUMMY = fwrite("('NREC=',I7)", e.NREC)[0]
                    e.errhdl(e.PATH, m, "E", "290", e.DUMMY)
                    return False
                if e.ICOUNT > e.IXM:
                    e.DUMMY = fwrite("('IXM =',I7)", e.IXM)[0]
                    e.errhdl(e.PATH, m, "E", "290", e.DUMMY)
                    if not polar:
                        return False
                    e.RECERR = True
                if e.JCOUNT > e.IYM:
                    e.DUMMY = fwrite("('IYM =',I7)", e.IYM)[0]
                    e.errhdl(e.PATH, m, "E", "290", e.DUMMY)
                    if not polar:
                        return False
                    e.RECERR = True
                if polar:
                    ytemp = e.YCOORD[j, innet] * e.DTORAD
                    e.AXR[iset] = e.XINT + e.XCOORD[i, innet] * math.sin(ytemp)
                    e.AYR[jset] = e.YINT + e.XCOORD[i, innet] * math.cos(ytemp)
                else:
                    e.AXR[iset] = e.XCOORD[i, innet]
                    e.AYR[jset] = e.YCOORD[j, innet]
        e.IRXR = iset
        e.IRYR = jset
        if polar:
            e.XORIG[innet] = e.XINT
            e.YORIG[innet] = e.YINT
        e.NETEND[innet] = e.IRXR
        e.NUMXPT[innet] = e.ICOUNT
        e.NUMYPT[innet] = e.JCOUNT
        e.NTID[innet] = e.NETIDT
        e.NTTYP[innet] = "GRIDPOLR" if polar else "GRIDCART"
        if e.ITAB < 0:
            e.ITAB = 1 if polar else 2
            e.NXTOX = e.ICOUNT
            e.NYTOX = e.JCOUNT
        else:
            e.ITAB = 0
    r = _volcar_z(e, m, e.ZETMP1, e.ZETMP2, e.IZE, e.IRZE, e.AZELEV)
    if r is None:
        return False
    e.IRZE = r
    r = _volcar_z(e, m, e.ZHTMP1, e.ZHTMP2, e.IZH, e.IRZH, e.AZHILL, "210" if polar else "290")
    if r is None:
        return False
    e.IRZH = r
    r = _volcar_z(e, m, e.ZFTMP1, e.ZFTMP2, e.IZF, e.IRZF, e.AZFLAG)
    if r is None:
        return False
    e.IRZF = r
    for i in range(e.IDC1 + 1, e.IRXR + 1):
        e.NETID[i] = e.NETIDT
        e.RECTYP[i] = "GP" if polar else "GC"
    return True


def setcar(e):
    """SETCAR: receptores de una red cartesiana."""
    _malla(e, "SETCAR", False)


def setpol(e):
    """SETPOL: receptores de una red polar."""
    _malla(e, "SETPOL", True)


def repolr(e):
    """REPOLR: red polar (GRIDPOLR)."""
    m = "REPOLR"
    r = _id_red(e, m, ("", "ORIG", "DIST", "DDIR", "ELEV", "HILL", "FLAG", "GDIR", "END"))
    if not r:
        return
    if r == "nueva":
        e._IORSET = e._IXRSET = e._IDRSET = e._IGRSET = 0
        e.IEVSET = e.IFGSET = 0
    kt = e.KTYPE
    if kt == "STA":
        _sta(e, m)
    elif kt == "ORIG":
        if not e.ISTA:
            e.errhdl(e.PATH, m, "E", "200", "  STA   ")
        if e._IORSET != 0:
            e.errhdl(e.PATH, m, "E", "160", e.NETIDT)
        polorg(e)
        e._IORSET += 1
    elif kt == "DIST":
        if not e.ISTA:
            e.errhdl(e.PATH, m, "E", "200", "  STA   ")
        e.ICOUNT = _lista_coord(e, "POLDST", "DIST", e.ICOUNT, e.XCOORD, e.IXM, "IXM")
        e._IXRSET += 1
    elif kt == "GDIR":
        if not e.ISTA:
            e.errhdl(e.PATH, m, "E", "200", "  STA   ")
        if e._IDRSET != 0:
            e.errhdl(e.PATH, m, "E", "180", e.NETIDT)
        genpol(e)
        e._IGRSET += 1
    elif kt == "DDIR":
        if not e.ISTA:
            e.errhdl(e.PATH, m, "E", "200", "  STA   ")
        if e._IGRSET != 0:
            e.errhdl(e.PATH, m, "E", "180", e.NETIDT)
        e.JCOUNT = _lista_coord(e, "RADRNG", "DDIR", e.JCOUNT, e.YCOORD, e.IYM, "IYM", polar=True)
        e._IDRSET += 1
    elif kt == "ELEV":
        if not e.ISTA:
            e.errhdl(e.PATH, m, "E", "200", "  STA   ")
        _hgt(e, "ELEV", "TERHGT")
        e.IEVSET += 1
    elif kt == "HILL":
        if not e.ISTA:
            e.errhdl(e.PATH, m, "E", "200", "  STA   ")
        _hgt(e, "HILL", "HILHGT")
        e.IHLSET += 1
    elif kt == "FLAG":
        if not e.ISTA:
            e.errhdl(e.PATH, m, "E", "200", "  STA   ")
        _hgt(e, "FLAG", "FLGHGT")
        e.IFGSET += 1
    elif kt == "END":
        e.IEND = True
        if not e.ISTA:
            e.errhdl(e.PATH, m, "E", "200", "  STA   ")
        elif not e.RECERR:
            setpol(e)
        e.ISTA = False
        e.NEWID = True
        if e._IORSET == 0:
            e.errhdl(e.PATH, m, "W", "220", e.NETIDT)
            e.XINT = 0.0
            e.YINT = 0.0
        if e._IXRSET == 0:
            e.errhdl(e.PATH, m, "E", "221", e.NETIDT)
        if e._IGRSET == 0 and e._IDRSET == 0:
            e.errhdl(e.PATH, m, "E", "221", e.NETIDT)
        _fin_red(e, m)
    else:
        e.errhdl(e.PATH, m, "E", "170", e.NETIDT)
        e.RECERR = True
        return
    e.PNETID = e.NETIDT


def polorg(e):
    """POLORG: origen de una red polar (coordenadas o identificador de fuente)."""
    m = "POLORG"
    _isc(e, "ORIG")
    isc = e.ISC
    if e.IFC == isc - 1:
        e.errhdl(e.PATH, m, "E", "200", e.KEYWRD)
        e.RECERR = True
        return
    elif e.IFC > isc + 1:
        e.errhdl(e.PATH, m, "E", "202", e.KTYPE)
        e.RECERR = True
        return
    if e.IFC == isc:
        if e.LOCE[isc] - e.LOCB[isc] <= 11:
            soid = fc(e.FIELD[isc], 12)
        else:
            e.errhdl(e.PATH, m, "E", "230", e.FIELD[isc][:12])
            e.RECERR = True
            return
        isdx, found = sindex(e.SRCID, e.NSRC, soid)
        if not found:
            e.errhdl(e.PATH, m, "E", "300", e.KEYWRD)
            e.RECERR = True
        else:
            e.XINT = e.AXS[isdx]
            e.YINT = e.AYS[isdx]
    else:
        e.XINT, imit = dbl(e, isc, e.XINT)
        if imit != 1:
            e.errhdl(e.PATH, m, "E", "208", e.KEYWRD)
            e.RECERR = True
        e.YINT, imit = dbl(e, isc + 1, e.YINT)
        e.IMIT = imit
        if imit != 1:
            e.errhdl(e.PATH, m, "E", "208", e.KEYWRD)
            e.RECERR = True


def genpol(e):
    """GENPOL: direcciones de una red polar a partir de inicial e incremento."""
    m = "GENPOL"
    _isc(e, "GDIR")
    isc = e.ISC
    if e.IFC == isc - 1:
        e.errhdl(e.PATH, m, "E", "200", e.KEYWRD)
        e.RECERR = True
        return
    elif e.IFC < isc + 2:
        e.errhdl(e.PATH, m, "E", "201", e.KTYPE)
        e.RECERR = True
        return
    elif e.IFC > isc + 2:
        e.errhdl(e.PATH, m, "E", "202", e.KTYPE)
        e.RECERR = True
        return
    tempp = [0.0] * 4
    error = False
    for k in range(1, 4):
        tempp[k], imit = dbl(e, isc + k - 1, tempp[k])
        e.IMIT = imit
        if imit != 1:
            e.errhdl(e.PATH, m, "E", "208", e.KEYWRD)
            e.RECERR = True
            error = True
    if error:
        return
    from .formato import nint
    e.JCOUNT = nint(tempp[1])
    dirini, dirinc = tempp[2], tempp[3]
    if e.JCOUNT <= e.IYM:
        for j in range(1, e.JCOUNT + 1):
            y = dirini + dirinc * float(j - 1)
            if y > 360.0:
                y = y - 360.0
            elif y <= 0.0:
                y = y + 360.0
            e.YCOORD[j, e.INNET] = y
    else:
        e.DUMMY = fwrite("('IYM =',I7)", e.IYM)[0]
        e.errhdl(e.PATH, m, "E", "290", e.DUMMY)
        e.RECERR = True


_HGT = {"ELEV": ("ZETMP1", "ZETMP2", "IZE"), "HILL": ("ZHTMP1", "ZHTMP2", "IZH"),
        "FLAG": ("ZFTMP1", "ZFTMP2", "IZF")}


def _hgt(e, clave, m):
    """TERHGT/HILHGT/FLGHGT: cotas, alturas de colina o de receptor de una fila de la red."""
    t1n, t2n, cn = _HGT[clave]
    t1, t2 = getattr(e, t1n), getattr(e, t2n)
    _isc(e, clave)
    isc = e.ISC
    if e.IFC == isc - 1:
        e.errhdl(e.PATH, m, "E", "223", e.KTYPE)
        e.RECERR = True
        return
    elif e.IFC == isc:
        e.errhdl(e.PATH, m, "E", "200", e.KEYWRD)
        e.RECERR = True
        return
    e.DNUM, imit = dbl(e, isc, e.DNUM)
    e.IMIT = imit
    if imit != 1:
        e.errhdl(e.PATH, m, "E", "208", e.KEYWRD)
        e.RECERR = True
    row = e.DNUM
    iset = getattr(e, cn)
    for i in range(isc + 1, e.IFC + 1):
        e.DNUM, imit = dbl(e, i, e.DNUM)
        e.IMIT = imit
        if imit == -1:
            e.errhdl(e.PATH, m, "E", "208", e.KEYWRD)
            e.RECERR = True
        for _j in range(imit):
            iset += 1
            if iset <= e.NREC:
                t1[iset] = row
                t2[iset] = e.DNUM
    e.ISET = iset
    setattr(e, cn, iset)


def _avisos_disc(e, m, base):
    """Avisos por número de campos de DISCCART (base=4) y DISCPOLR (base=5)."""
    ifc = e.IFC
    if ifc < base:
        e.errhdl(e.PATH, m, "E", "200", e.KEYWRD)
        return False
    elif ifc > base + 3:
        e.errhdl(e.PATH, m, "E", "202", e.KEYWRD)
        return False
    elif e.ELEV and e.FLGPOL and ifc < base + 3:
        e.errhdl(e.PATH, m, "W", "228", e.KEYWRD)
    elif e.ELEV and not e.FLGPOL and ifc < base + 2:
        e.errhdl(e.PATH, m, "W", "228", e.KEYWRD)
    elif e.ELEV and not e.FLGPOL and ifc > base + 2:
        e.errhdl(e.PATH, m, "W", "229", e.KEYWRD if base == 4 else " ZFLAG ")
    elif e.FLGPOL and not e.ELEV and ifc > base + 1:
        e.errhdl(e.PATH, m, "W", "229", e.KEYWRD)
    elif not e.ELEV and not e.FLGPOL and ifc > base:
        e.errhdl(e.PATH, m, "W", "229", e.KEYWRD)
    return True


def _cotas_disc(e, m, base, i3, i4, i5):
    """Cota, colina y altura de receptor opcionales de DISCCART/DISCPOLR."""
    ifc = e.IFC
    destinos = []
    if e.ELEV and e.FLGPOL:
        if ifc >= base + 1:
            destinos.append((base + 1, e.AZELEV, i3))
        if ifc >= base + 2:
            destinos.append((base + 2, e.AZHILL, i5))
        if ifc == base + 3:
            destinos.append((base + 3, e.AZFLAG, i4))
    elif e.ELEV and not e.FLGPOL:
        if ifc >= base + 1:
            destinos.append((base + 1, e.AZELEV, i3))
        if ifc >= base + 2:
            destinos.append((base + 2, e.AZHILL, i5))
    elif e.FLGPOL and not e.ELEV:
        if ifc == base + 1:
            destinos.append((base + 1, e.AZFLAG, i4))
        elif ifc == base + 3:
            destinos.append((base + 3, e.AZFLAG, i4))
    for k, a, ii in destinos:
        e.DNUM, imit = dbl(e, k, e.DNUM)
        e.IMIT = imit
        if imit != 1:
            e.errhdl(e.PATH, m, "E", "208", e.KEYWRD)
        else:
            a[ii + 1] = e.DNUM


def _lleno(e, m, i1, i2, i3, i4, i5):
    n = e.NREC
    if n in (i1, i2, i3, i4, i5):
        e.DUMMY = fwrite("('NREC=',I7)", e.NREC)[0]
        e.errhdl(e.PATH, m, "E", "290", e.DUMMY)
        return True
    return False


def discar(e):
    """DISCAR: receptor cartesiano discreto (DISCCART)."""
    m = "DISCAR"
    i1, i2, i3, i4, i5 = e.IRXR, e.IRYR, e.IRZE, e.IRZF, e.IRZH
    if not _avisos_disc(e, m, 4):
        return
    if _lleno(e, m, i1, i2, i3, i4, i5):
        return
    e.DNUM, imit = dbl(e, 3, e.DNUM)
    if imit != 1:
        e.errhdl(e.PATH, m, "E", "208", e.KEYWRD)
    else:
        e.AXR[i1 + 1] = e.DNUM
    e.DNUM, imit = dbl(e, 4, e.DNUM)
    e.IMIT = imit
    if imit != 1:
        e.errhdl(e.PATH, m, "E", "208", e.KEYWRD)
    else:
        e.AYR[i2 + 1] = e.DNUM
    _cotas_disc(e, m, 4, i3, i4, i5)
    e.IRXR, e.IRYR, e.IRZE, e.IRZF, e.IRZH = i1 + 1, i2 + 1, i3 + 1, i4 + 1, i5 + 1
    e.NETID[e.IRXR] = ""
    e.RECTYP[e.IRXR] = "DC"
    e.ITAB = 0


def dispol(e):
    """DISPOL: receptor polar discreto (DISCPOLR) respecto a una fuente."""
    m = "DISPOL"
    i1, i2, i3, i4, i5 = e.IRXR, e.IRYR, e.IRZE, e.IRZF, e.IRZH
    if not _avisos_disc(e, m, 5):
        return
    if _lleno(e, m, i1, i2, i3, i4, i5):
        return
    if e.LOCE[3] - e.LOCB[3] <= 11:
        soid = fc(e.FIELD[3], 12)
    else:
        e.errhdl(e.PATH, m, "E", "230", e.FIELD[3][:12])
        e.RECERR = True
        return
    e._RANGE, imit = dbl(e, 4, getattr(e, "_RANGE", 0.0))
    if imit != 1:
        e.errhdl(e.PATH, m, "E", "208", e.KEYWRD)
    direct, imit = dbl(e, 5, getattr(e, "_DIRECT", 0.0))
    e.IMIT = imit
    if imit != 1:
        e.errhdl(e.PATH, m, "E", "208", e.KEYWRD)
    elif direct > 360.0:
        direct = direct - 360.0
    elif direct <= 0.0:
        direct = direct + 360.0
    e._DIRECT = direct
    _cotas_disc(e, m, 5, i3, i4, i5)
    isdx, found = sindex(e.SRCID, e.NSRC, soid)
    if not found:
        e.errhdl(e.PATH, m, "E", "300", e.KEYWRD)
    else:
        e.AXR[i1 + 1] = e.AXS[isdx] + e._RANGE * math.sin(direct * e.DTORAD)
        e.AYR[i2 + 1] = e.AYS[isdx] + e._RANGE * math.cos(direct * e.DTORAD)
        e.IRXR, e.IRYR, e.IRZE, e.IRZF, e.IRZH = i1 + 1, i2 + 1, i3 + 1, i4 + 1, i5 + 1
        e.ITAB = 0
    e.NETID[e.IRXR] = ""
    e.RECTYP[e.IRXR] = "DP"
    e.IREF[e.IRXR] = isdx


def sbyval(a1, a2, inx):
    """SBYVAL: ordena (por selección) a1 y arrastra a2, de 1 a inx."""
    jc = 1
    while jc <= inx:
        rmin = a1[jc]
        imin = jc
        for i in range(jc, inx + 1):
            if a1[i] < rmin:
                imin = i
                rmin = a1[i]
        t1, t2 = a1[jc], a2[jc]
        a1[jc], a2[jc] = a1[imin], a2[imin]
        a1[imin], a2[imin] = t1, t2
        jc += 1


def evcart(e):
    """EVCART: receptor discreto de evaluación (EVALCART)."""
    m = "EVCART"
    i1, i2, i3, i4, i5 = e.IRXR, e.IRYR, e.IRZE, e.IRZF, e.IRZH
    if e.IFC < 8:
        e.errhdl(e.PATH, m, "E", "201", e.KEYWRD)
        return
    elif e.IFC > 9:
        e.errhdl(e.PATH, m, "E", "202", e.KEYWRD)
        return
    if _lleno(e, m, i1, i2, i3, i4, i5):
        return
    for k, a, ii in ((3, e.AXR, i1), (4, e.AYR, i2), (5, e.AZELEV, i3), (6, e.AZHILL, i5), (7, e.AZFLAG, i4)):
        e.DNUM, imit = dbl(e, k, e.DNUM)
        e.IMIT = imit
        if imit != 1:
            e.errhdl(e.PATH, m, "E", "208", e.KEYWRD)
        else:
            a[ii + 1] = e.DNUM
    found = False
    j = 1
    while not found and j <= e.NUMARC:
        if e.FIELD[8] == e.ARCID[j]:
            found = True
            e.NDXARC[i1 + 1] = j
        j += 1
    if not found:
        e.NUMARC += 1
        if e.NUMARC > e.NARC:
            e.DUMMY = fwrite("('NARC =',I6)", e.NARC)[0]
            e.errhdl(e.PATH, m, "E", "290", e.DUMMY)
            return
        e.ARCID[e.NUMARC] = fc(e.FIELD[8], 8)
        e.NDXARC[i1 + 1] = e.NUMARC
    e.IRXR, e.IRYR, e.IRZE, e.IRZF, e.IRZH = i1 + 1, i2 + 1, i3 + 1, i4 + 1, i5 + 1
    e.NETID[e.IRXR] = ""
    e.RECTYP[e.IRXR] = "DC"
    e.ITAB = 0
