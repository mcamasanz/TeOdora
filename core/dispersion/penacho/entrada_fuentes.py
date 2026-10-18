# -*- coding: utf-8 -*-
"""Traducción de AERMOD 26135 (US EPA, dominio público): vía SO (soset.f).

SOCARD con las claves del alcance: LOCATION, SRCPARAM (POINT, POINTCAP, POINTHOR, VOLUME, AREA,
AREAPOLY, AREACIRC), BUILDHGT/BUILDWID/BUILDLEN/XBADJ/YBADJ, EMISFACT, EMISUNIT, CONCUNIT,
ELEVUNIT, AREAVERT, INCLUDED, HOUREMIS, BACKGRND, BACKUNIT, BGSECTOR, SRCGROUP y las de la
química del NO2 (NO2RATIO, OLMGROUP y PSDGROUP, en entrada_no2.py), las de la deposición (PARTDIAM,
MASSFRAX, PARTDENS, METHOD_2, GASDEPOS, DEPOUNIT y VDP1) y el control de calidad final (SRCQA).
Las fuentes y claves fuera de alcance (OPENPIT, SWPOINT, PLATFORM, aeronaves...) paran con
NoTraducido."""
import math

import numpy as np

from . import fuente_linea_flotante, control, emisiones, entrada_no2, fuente_carretera
from .control import dbl, fsplit, i8, sindex
from .estado import ILEN_FLD, NoTraducido
from .formato import fc, fwrite, nint, stodbl

_FUERA = {"PLATFORM": "PLATFORM", "ARCFTSRC": "fuentes de aeronaves", "HBPSRCID": "HBP"}

_FUENTES_FUERA = ()


def _orden_grupo(e, m):
    if not e.PSDCREDIT and e.ISSTAT[24] != 0:
        e.errhdl(e.PATH, m, "E", "140", "SRCGROUP")
    elif e.PSDCREDIT and e.ISSTAT[34] != 0:
        e.errhdl(e.PATH, m, "E", "140", "PSDGROUP")


def socard(e):
    """SOCARD: claves de la vía SO."""
    m = "SOCARD"
    k = e.KEYWRD
    if k == "STARTING":
        e.ISRC = e.IGRP = e.NUMSRC = e.NUMGRP = e.NUMOLM = e.NUMPSD = 0
        fuente_linea_flotante.starting_bl_contadores(e)
        e.NUMCAP = e.NUMHOR = e.NURBSRC = e.NAFTSRC = e.NUMFLAT = 0
        e.ISSTAT[1] += 1
        if e.ISSTAT[1] != 1:
            e.errhdl(e.PATH, m, "E", "135", k)
            return
        fuente_linea_flotante.starting_bl_indicadores(e)
        e.L_RDEPRESS = False
        e.L_RBARRIER = False
        e.IWRK2[:] = 0
    elif k == "LOCATION":
        e.ISSTAT[2] += 1
        _orden_grupo(e, m)
        soloca(e)
    elif k == "SRCPARAM":
        e.ISSTAT[3] += 1
        _orden_grupo(e, m)
        soparm(e)
    elif k in ("BUILDHGT", "BUILDWID", "BUILDLEN", "XBADJ", "YBADJ"):
        _orden_grupo(e, m)
        n = {"BUILDHGT": 4, "BUILDWID": 5, "BUILDLEN": 21, "XBADJ": 22, "YBADJ": 23}[k]
        e.ISSTAT[n] += 1
        dsbldg(e)
    elif k == "EMISFACT":
        e.ISSTAT[7] += 1
        _orden_grupo(e, m)
        emvary(e)
    elif k == "EMISUNIT":
        e.ISSTAT[8] += 1
        _orden_grupo(e, m)
        if e.ISSTAT[8] != 1:
            e.errhdl(e.PATH, m, "E", "135", k)
        elif e.NUMTYP == 1:
            emunit(e)
        else:
            e.errhdl(e.PATH, m, "E", "158", " ")
    elif k == "ELEVUNIT":
        e.ISSTAT[15] += 1
        _orden_grupo(e, m)
        if e.ISSTAT[15] != 1:
            e.errhdl(e.PATH, m, "E", "135", k)
        elif e.NUMSRC > 0:
            e.errhdl(e.PATH, m, "E", "152", "  SO")
        else:
            soelun(e)
    elif k == "CONCUNIT":
        e.ISSTAT[17] += 1
        _orden_grupo(e, m)
        if e.ISSTAT[17] != 1:
            e.errhdl(e.PATH, m, "E", "135", k)
        if e.ISSTAT[8] != 0:
            e.errhdl(e.PATH, m, "E", "159", k)
        else:
            counit(e)
    elif k == "HOUREMIS":
        e.ISSTAT[16] += 1
        _orden_grupo(e, m)
        e.HOURLY = True
        hremis(e)
    elif k == "URBANSRC":
        e.ISSTAT[28] += 1
        _orden_grupo(e, m)
        if e.URBAN:
            urbans(e)
        else:
            e.errhdl(e.PATH, m, "E", "130", "URBANOPT")
    elif k == "BACKGRND":
        e.ISSTAT[40] += 1
        _orden_grupo(e, m)
        back_grnd(e)
    elif k == "BACKUNIT":
        e.ISSTAT[41] += 1
        _orden_grupo(e, m)
        if e.ISSTAT[41] != 1:
            e.errhdl(e.PATH, m, "E", "135", k)
        else:
            back_unit(e)
    elif k == "BGSECTOR":
        e.ISSTAT[42] += 1
        if e.ISSTAT[42] != 1:
            e.errhdl(e.PATH, m, "E", "135", k)
        else:
            bgsector(e)
    elif k == "AREAVERT":
        e.ISSTAT[19] += 1
        _orden_grupo(e, m)
        arvert(e)
    elif k in ("PARTDIAM", "MASSFRAX", "PARTDENS"):
        e.ISSTAT[{"PARTDIAM": 9, "MASSFRAX": 10, "PARTDENS": 11}[k]] += 1
        _orden_grupo(e, m)
        partdep(e)
    elif k == "DEPOUNIT":
        e.ISSTAT[18] += 1
        _orden_grupo(e, m)
        if e.ISSTAT[18] != 1:
            e.errhdl(e.PATH, m, "E", "135", k)
        if e.ISSTAT[8] != 0:
            e.errhdl(e.PATH, m, "E", "159", k)
        else:
            dpunit(e)
    elif k == "GASDEPOS":
        # deposición de gases: opción ALPHA desde la versión 19191
        if e.L_ALPHA:
            e.ISSTAT[26] += 1
            _orden_grupo(e, m)
            if not e.LUSERVD:
                gasdep(e)
            else:
                e.errhdl(e.PATH, m, "E", "195", k)
        else:
            e.errhdl(e.PATH, m, "E", "198", "GASDEPOS")
    elif k == "METHOD_2":
        if e.L_ALPHA:
            e.ISSTAT[27] += 1
            if e.DFAULT:
                e.errhdl(e.PATH, m, "E", "197", "METHOD_2")
            else:
                e.L_NONDFAULT = True
                _orden_grupo(e, m)
                meth_2(e)
        else:
            e.errhdl(e.PATH, m, "E", "198", "METHOD_2")
    elif k == "INCLUDED":
        e.ISSTAT[20] += 1
        ilsave = e.ILINE
        control.includ(e)
        e.ILINE = ilsave
    elif k == "SRCGROUP":
        e.ISSTAT[24] += 1
        if not e.PSDCREDIT:
            sogrp(e)
        else:
            e.errhdl(e.PATH, m, "E", "105", k)
    elif entrada_no2.socard(e, k, _orden_grupo):
        pass
    elif fuente_carretera.socard(e, k):
        pass
    elif fuente_linea_flotante.socard_bl(e, k):
        pass
    elif k in _FUERA:
        raise NoTraducido("SO " + k + " (" + _FUERA[k] + ")")
    elif k == "FINISHED":
        _finished(e)
    else:
        e.errhdl(e.PATH, m, "E", "110", k)


def urbans(e):
    """URBANS: tarjeta URBANSRC (fuentes urbanas y zona urbana a la que pertenecen)."""
    m = "URBANS"
    f = e.FIELD
    if e.IFC <= 2:
        e.errhdl(e.PATH, m, "E", "200", e.KEYWRD)
        return
    if e.L_URBAN_ALL:
        if e.IFC == 3 and f[3] == "ALL":
            for k in range(1, len(e.URBSRC)):
                e.URBSRC[k] = "Y"
            e.IURBGRP[...] = 1
        else:
            e.errhdl(e.PATH, m, "E", "279", "URBANSRC ALL")
        return
    if e.L_MULTURB:
        tempid = fc(f[3], 12)
        found = False
        for i in range(1, e.NUMURB + 1):
            if tempid == e.URBID[i]:
                found = True
                e.IURB = i
        if not found:
            e.errhdl(e.PATH, m, "E", "301", tempid)
            return
        istr = 4
    else:
        e.IURB = 1
        istr = 3
    iu = e.IURB
    for i in range(istr, e.IFC + 1):
        if "-" not in f[i]:
            found = False
            for k in range(1, e.NUMSRC + 1):
                if e.SRCID[k] == f[i]:
                    found = True
                    e.URBSRC[k] = "Y"
                    e.IURBGRP[k, iu] = 1
            if not found:
                e.errhdl(e.PATH, m, "E", "300", e.KEYWRD)
        else:
            _r, lowid, higid = fsplit(e, e.PATH, e.KEYWRD, f[i], ILEN_FLD, "-")
            lowid, higid = fc(lowid, 12), fc(higid, 12)
            l1, il, l2 = setidg(lowid)
            h1, ih, h2 = setidg(higid)
            if h1 < l1 or ih < il or h2 < l2:
                e.errhdl(e.PATH, m, "E", "203", "SRCRANGE")
                continue
            for k in range(1, e.NUMSRC + 1):
                if asngrp(e.SRCID[k], lowid, higid):
                    e.URBSRC[k] = "Y"
                    e.IURBGRP[k, iu] = 1


def hremis(e):
    """HREMIS: tarjeta HOUREMIS (fichero de emisiones horarias y fuentes que lo usan). Un fichero
    ya declarado reutiliza su unidad; uno nuevo toma la siguiente unidad dinámica (FUNITINX)."""
    from .entrada_meteo import _abierto
    m = "HREMIS"
    if e.IFC < 4:
        e.errhdl(e.PATH, m, "E", "201", e.KEYWRD)
        return
    if e.LOCE[3] - e.LOCB[3] > ILEN_FLD - 1:
        e.errhdl(e.PATH, m, "E", "291", i8(ILEN_FLD))
        return
    e.HRFILE = fc(e.RUNST1[int(e.LOCB[3]) - 1:int(e.LOCE[3])], 200)
    hallado = False
    for j in range(1, e.NUMSRC + 1):
        nom = e.HOUREMISNAMEARRAY[j]
        if nom != "" and nom != e.HRFILE and e.HRSRCIDS[j] != e.SRCID[j]:
            e.errhdl(e.PATH, m, "E", "835", "HOUREMIS")
        if nom == e.HRFILE:
            hallado = True
            e.IHREMI = int(e.HOUREMISARRAY[j])
            break
    if not hallado:
        e.IHREMI = e.FUNITINX
        e.FUNITINX += 1
    if not _abierto(e, e.HRFILE) and e.IHREMI not in e.U:
        try:
            e.abrir_entrada(e.IHREMI, e.HRFILE)
        except OSError:
            e.errhdl(e.PATH, m, "E", "500", e.KEYWRD)
            return
        e.FUNITARRAY[e.FUNITIND] = e.IHREMI
        e.FNAMEARRAY[e.FUNITIND] = e.HRFILE
        e.FTYPARRAY[e.FUNITIND] = "HOUREMIS"
        e.FUNITIND += 1
    if fc(e.FIELD[4], 12) == "ALL":
        for k in range(1, e.NUMSRC + 1):
            e.QFLAG[k] = "HOURLY"
            fuente_linea_flotante.hremis_bl(e, k)
            e.HOUREMISARRAY[k] = e.IHREMI
            e.HOUREMISNAMEARRAY[k] = e.HRFILE
            e.HRSRCIDS[k] = e.SRCID[k]
    else:
        for i in range(4, e.IFC + 1):
            _r, lowid, higid = fsplit(e, e.PATH, e.KEYWRD, e.FIELD[i], ILEN_FLD, "-")
            lowid, higid = fc(lowid, 12), fc(higid, 12)
            l1, il, l2 = setidg(lowid)
            h1, ih, h2 = setidg(higid)
            if h1 < l1 or ih < il or h2 < l2:
                e.errhdl(e.PATH, m, "E", "203", "SRCRANGE")
                continue
            for k in range(1, e.NUMSRC + 1):
                if not asngrp(e.SRCID[k], lowid, higid):
                    continue
                e.QFLAG[k] = "HOURLY"
                fuente_linea_flotante.hremis_bl(e, k)
                if e.HOUREMISARRAY[k] == 0:
                    e.HOUREMISARRAY[k] = e.IHREMI
                elif e.HOUREMISARRAY[k] != e.IHREMI:
                    e.errhdl(e.PATH, m, "E", "565", "HOUREMIS")
                if e.HOUREMISNAMEARRAY[k] == "":
                    e.HOUREMISNAMEARRAY[k] = e.HRFILE
                elif e.HOUREMISNAMEARRAY[k] != e.HRFILE:
                    e.errhdl(e.PATH, m, "E", "835", "HOUREMIS")
                if e.HRSRCIDS[k] == "":
                    e.HRSRCIDS[k] = e.SRCID[k]
                elif e.HRSRCIDS[k] != e.SRCID[k]:
                    e.errhdl(e.PATH, m, "E", "834", e.SRCID[k])
    e.HOUREMISIND += 1


def _finished(e):
    m = "SOCARD"
    e.ISSTAT[50] += 1
    if e.ISSTAT[50] != 1:
        e.errhdl(e.PATH, m, "E", "135", e.KEYWRD)
    if e.PKEYWD != "SRCGROUP" and not e.PSDCREDIT:
        e.errhdl(e.PATH, m, "E", "140", "SRCGROUP")
    if e.PKEYWD != "PSDGROUP" and e.PSDCREDIT:
        e.errhdl(e.PATH, m, "E", "140", "SRCGROUP")
    if e.ISSTAT[1] == 0:
        e.errhdl(e.PATH, m, "E", "130", "STARTING")
    if e.ISSTAT[2] == 0:
        e.errhdl(e.PATH, m, "E", "130", "LOCATION")
    if e.ISSTAT[3] == 0:
        e.errhdl(e.PATH, m, "E", "130", "SRCPARAM")
    if e.ISSTAT[24] == 0 and not e.PSDCREDIT:
        e.errhdl(e.PATH, m, "E", "130", "SRCGROUP")
    if e.ISSTAT[34] == 0 and e.PSDCREDIT:
        e.errhdl(e.PATH, m, "E", "130", "PSDGROUP")
    if e.ISSTAT[3] < e.ISSTAT[2]:
        e.errhdl(e.PATH, m, "E", "130", "SRCPARAM")
    if e.ISSTAT[40] == 0 and e.ISSTAT[41] > 0:
        e.errhdl(e.PATH, m, "E", "193", "SO BACKGRND")
    if e.NUMSRC == 0:
        e.errhdl(e.PATH, m, "E", "185", "NUMSRC=0")
        return
    if e.DFAULT and e.ISSTAT[26] > 0:
        e.errhdl(e.PATH, m, "E", "196", "GASDEPOS")
    elif e.ISSTAT[26] > 0:
        e.L_NONDFAULT = True
    # opciones de deposición según las entradas dadas: seca de gases con GASDEPVD o con GDSEASON,
    # GDLANUSE y GASDEPOS; húmeda de gases con GASDEPOS; partículas con PARTDIAM, MASSFRAX y
    # PARTDENS o con METHOD_2
    if e.LUSERVD or (e.ICSTAT[18] > 0 and e.ICSTAT[20] > 0 and e.ISSTAT[26] > 0):
        e.LDGAS = True
    if e.ISSTAT[26] > 0:
        e.LWGAS = True
    if (e.ISSTAT[9] > 0 and e.ISSTAT[10] > 0 and e.ISSTAT[11] > 0) or e.ISSTAT[27] > 0:
        e.LDPART = True
        e.LWPART = True
    if e.DRYDPLT or (not e.NODRYDPLT and (e.LDGAS or e.LDPART)):
        e.DDPLETE = True
    if e.WETDPLT or (not e.NOWETDPLT and (e.LWGAS or e.LWPART)):
        e.WDPLETE = True
    if e.LUSERVD and e.WDPLETE:
        e.errhdl(e.PATH, m, "E", "243", "GASDEPVD")
    if e.DDPLETE:
        e.MODOPS[14] = "AREADPLT" if e.ARDPLETE else ("ROMBERG" if e.ROMBERG else "DRYDPLT")
    elif e.NODRYDPLT:
        e.MODOPS[14] = "NODRYDPLT"
    else:
        e.MODOPS[14] = ""
    if e.WDPLETE:
        e.MODOPS[15] = "WETDPLT"
    elif e.NODRYDPLT:
        e.MODOPS[15] = "NOWETDPLT"
    else:
        e.MODOPS[15] = ""
    if (e.DDPLETE or e.DEPOS or e.DDEP) and (not e.LDGAS and not e.LDPART):
        e.errhdl("SO", m, "E", "244", "DRYDEP")
    if (e.WDPLETE or e.DEPOS or e.WDEP) and (not e.LWGAS and not e.LWPART):
        e.errhdl("SO", m, "E", "244", "WETDEP")
    fuente_linea_flotante.finished_bl(e)
    srcqa(e)
    if e.SBARDCL:
        fuente_carretera.sbarrier_dcl(e)
    if e.VBARSET:
        fuente_carretera.vbarrier_setup(e)
    if not e.LUSERVD and e.LDGAS and e.ICSTAT[18] == 0:
        e.errhdl("CO", m, "E", "130", "GDSEASON")
    if not e.LUSERVD and e.LDGAS and e.ICSTAT[20] == 0:
        e.errhdl("CO", m, "E", "130", "GDLANUSE")
    if not e.LUSERVD and e.LDGAS and e.ISSTAT[26] == 0:
        e.errhdl("SO", m, "E", "130", "GASDEPOS")
    e.MODOPS[1] = "RegDFAULT" if e.DFAULT else ("NonDFAULT" if e.L_NONDFAULT else "")


def soelun(e):
    """SOELUN: unidades de la cota de las fuentes."""
    m = "SOELUN"
    if e.IFC == 3:
        if e.FIELD[3] == "METERS":
            e.SOELEV = "METERS"
        elif e.FIELD[3] == "FEET":
            e.SOELEV = "FEET"
        else:
            e.errhdl(e.PATH, m, "E", "203", "SO_ELEV")
    elif e.IFC > 3:
        e.errhdl(e.PATH, m, "E", "202", e.KEYWRD)
    else:
        e.errhdl(e.PATH, m, "E", "200", "ElevUnit")


_TIPOS = ("POINT", "POINTCAP", "POINTHOR", "VOLUME", "AREA", "AREAPOLY", "AREACIRC", "LINE", "RLINE",
          "RLINEXT", "BUOYLINE", "OPENPIT", "SWPOINT")


def soloca(e):
    """SOLOCA: LOCATION (identificador, tipo y coordenadas de la fuente)."""
    m = "SOLOCA"
    f = e.FIELD
    ifc = e.IFC
    if f[4] in ("LINE", "BUOYLINE", "RLINE"):
        lim = (8, 9)
    elif f[4] == "RLINEXT":
        lim = (10, 11)
    else:
        lim = (6, 7)
    if ifc <= 2:
        e.errhdl(e.PATH, m, "E", "200", e.KEYWRD)
        return
    elif ifc < lim[0]:
        e.errhdl(e.PATH, m, "E", "201", e.KEYWRD)
        return
    elif ifc > lim[1]:
        e.errhdl(e.PATH, m, "E", "202", e.KEYWRD)
        return
    if e.LOCE[3] - e.LOCB[3] <= 11:
        soid = fc(f[3], 12)
        if soid in ("BACKGROUND", "BACKGRND"):
            e.errhdl(e.PATH, m, "E", "285", f[3][:12])
            return
    else:
        e.errhdl(e.PATH, m, "E", "230", f[3][:12])
        return
    _isdx, found = sindex(e.SRCID, e.NSRC, soid)
    if found:
        e.errhdl(e.PATH, m, "E", "310", soid)
        return
    e.ISRC += 1
    isrc = e.ISRC
    if isrc > e.NSRC:
        e.DUMMY = fwrite("('NSRC=',I7)", e.NSRC)[0]
        e.errhdl(e.PATH, m, "E", "290", e.DUMMY)
        return
    e.SRCID[isrc] = fc(f[3], 12)
    tipo = fc(f[4], 8)
    if tipo in ("OPENPIT", "OPEN_PIT", "OPEN-PIT"):
        tipo = "OPENPIT"
    e.SRCTYP[isrc] = tipo
    if tipo not in _TIPOS:
        e.errhdl(e.PATH, m, "E", "203", "SRCTYP")
        return
    if tipo in _FUENTES_FUERA:
        raise NoTraducido("fuente " + tipo)
    if tipo in ("LINE", "BUOYLINE", "RLINE", "RLINEXT"):
        if tipo in ("LINE", "BUOYLINE"):
            # extremos de la línea; el campo de cota es el 9
            for k, a in ((5, e.AXS1), (6, e.AYS1), (7, e.AXS2), (8, e.AYS2)):
                v, imit = dbl(e, k, a[isrc])
                e.IMIT = imit
                a[isrc] = v
                if imit != 1:
                    e.errhdl(e.PATH, m, "E", "208", e.KEYWRD)
            _cota(e, m, isrc, soid, 9)
        else:
            fuente_carretera.soloca_rline(e, m, isrc)
            _cota(e, m, isrc, soid, 9 if tipo == "RLINE" else 11)
        e.ISET = isrc
        e.NUMSRC += 1
        fuente_linea_flotante.soloca_bl(e, isrc)
        return
    for k, a in ((5, e.AXS), (6, e.AYS)):
        v, imit = dbl(e, k, a[isrc])
        e.IMIT = imit
        a[isrc] = v
        if imit != 1:
            e.errhdl(e.PATH, m, "E", "208", e.KEYWRD)
    if ifc == 7 and e.FLATSRCS and f[7] == "FLAT":
        e.L_FLATSRC[isrc] = True
        e.NUMFLAT += 1
        e.errhdl(e.PATH, m, "W", "752", soid)
    elif ifc == 7:
        v, imit = dbl(e, 7, e.AZS[isrc])
        e.IMIT = imit
        e.AZS[isrc] = v
        if imit != 1:
            e.errhdl(e.PATH, m, "E", "208", e.KEYWRD)
        if e.AZS[isrc] < -9998.99:
            e.errhdl(e.PATH, m, "E", "249", soid)
        elif e.SOELEV == "FEET":
            e.AZS[isrc] = e.AZS[isrc] * 0.3048
    else:
        e.AZS[isrc] = 0.0
        if e.ELEV:
            e.errhdl(e.PATH, m, "W", "205", "ZS = 0.0")
    e.ISET = isrc
    e.NUMSRC += 1


def _cota(e, m, isrc, soid, k):
    """Cota de la base de la fuente en el campo K de LOCATION (LINE, BUOYLINE, RLINE: K = 9;
    RLINEXT: K = 11): sin campo, 0 (aviso con ELEV); 'FLAT' con FLATSRCS; o el valor leído."""
    f = e.FIELD
    if e.IFC == k - 1:
        e.AZS[isrc] = 0.0
        if e.ELEV:
            e.errhdl(e.PATH, m, "W", "205", "ZS = 0.0")
    elif e.IFC == k and e.FLATSRCS and f[k] == "FLAT":
        e.L_FLATSRC[isrc] = True
        e.NUMFLAT += 1
        if k == 11:
            e.AZS[isrc] = 0.0
        e.errhdl(e.PATH, m, "W", "752", soid)
    elif e.IFC == k:
        v, imit = dbl(e, k, e.AZS[isrc])
        e.IMIT = imit
        e.AZS[isrc] = v
        if imit != 1:
            e.errhdl(e.PATH, m, "E", "208", e.KEYWRD)
        if e.AZS[isrc] < -9998.99:
            e.errhdl(e.PATH, m, "E", "249", soid)
        elif e.SOELEV == "FEET":
            e.AZS[isrc] = e.AZS[isrc] * 0.3048


def soparm(e):
    """SOPARM: SRCPARAM (parámetros de la fuente según su tipo)."""
    m = "SOPARM"
    f = e.FIELD
    ifc = e.IFC
    temp = [0.0] * (ifc + 2)
    if ifc <= 2:
        e.errhdl(e.PATH, m, "E", "200", e.KEYWRD)
        return
    elif ifc == 3:
        e.errhdl(e.PATH, m, "E", "201", e.KEYWRD)
        return
    isdx, found = sindex(e.SRCID, e.NSRC, f[3])
    if not found:
        e.errhdl(e.PATH, m, "E", "300", e.KEYWRD)
        return
    if e.SOPCRD[isdx] == "Y":
        e.errhdl(e.PATH, m, "E", "315", e.SRCID[isdx])
        return
    e.SOPCRD[isdx] = "Y"
    for i in range(4, ifc + 1):
        temp[i - 3], imit = dbl(e, i, temp[i - 3])
        e.IMIT = imit
        if imit != 1:
            e.errhdl(e.PATH, m, "E", "208", e.KEYWRD)
    t = e.SRCTYP[isdx]
    if t == "OPENPIT":
        from . import fuente_foso
        fuente_foso.soparm_pit(e, isdx, temp)
        return
    if t == "SWPOINT":
        from . import fuente_sidewash
        fuente_sidewash.soparm_sw(e, isdx, temp)
        return
    lims = {"POINT": (8, 8, pparm), "POINTCAP": (8, 8, pparm), "POINTHOR": (8, 8, pparm),
            "VOLUME": (7, 7, vparm), "AREA": (6, 9, aparm), "AREAPOLY": (6, 7, apparm),
            "AREACIRC": (6, 8, acparm), "LINE": (6, 7, lparm), "RLINE": (6, 7, fuente_carretera.rlparm),
            "RLINEXT": (7, 7, fuente_carretera.rlparm), "BUOYLINE": (5, 5, fuente_linea_flotante.blparm)}
    if t not in lims:
        return
    lo, hi, fn = lims[t]
    if ifc < lo:
        e.errhdl(e.PATH, m, "E", "201", e.KEYWRD)
        return
    if ifc > hi:
        e.errhdl(e.PATH, m, "E", "202", e.KEYWRD)
        return
    fn(e, isdx, temp)


def pparm(e, i, temp):
    """PPARM: fuentes puntuales."""
    m = "PPARM"
    e.AQS[i], e.AHS[i], e.ATS[i], e.AVS[i], e.ADS[i] = temp[1], temp[2], temp[3], temp[4], temp[5]
    if e.AQS[i] == 0.0:
        e.errhdl(e.PATH, m, "W", "320", " QS ")
    if e.AHS[i] < 0.0:
        e.errhdl(e.PATH, m, "E", "209", " HS ")
    elif e.AHS[i] > 600.0:
        e.errhdl(e.PATH, m, "W", "320", " HS ")
    if e.ATS[i] == 0.0:
        e.ATS[i] = -1.0e-5
    elif e.ATS[i] > 2000.0:
        e.errhdl(e.PATH, m, "W", "320", " TS ")
    elif 0.0 < e.ATS[i] < 200.0:
        e.errhdl(e.PATH, m, "E", "320", " TS ")
        e.RUNERR = True
    if e.AVS[i] < 0.0:
        e.errhdl(e.PATH, m, "W", "325", e.SRCID[i])
        e.AVS[i] = 1.0e-5
    elif e.AVS[i] < 1.0e-5:
        e.AVS[i] = 1.0e-5
    elif e.AVS[i] > 50.0:
        e.errhdl(e.PATH, m, "W", "320", " VS ")
    if e.ADS[i] < 0.0:
        e.errhdl(e.PATH, m, "E", "209", " DS ")
    elif e.ADS[i] < 1.0e-5:
        e.ADS[i] = 1.0e-5
    elif e.ADS[i] > 20.0:
        e.errhdl(e.PATH, m, "W", "320", " DS ")
    e.ADSFACT[i] = 2.0 if e.SRCTYP[i] == "POINTCAP" else 1.0


def vparm(e, i, temp):
    """VPARM: fuentes de volumen."""
    m = "VPARM"
    e.AQS[i], e.AHS[i], e.ASYINI[i], e.ASZINI[i] = temp[1], temp[2], temp[3], temp[4]
    if e.AQS[i] == 0.0:
        e.errhdl(e.PATH, m, "W", "320", " QS ")
    if e.AHS[i] < 0.0:
        e.errhdl(e.PATH, m, "E", "209", " HS ")
    elif e.AHS[i] > 100.0 and not e.ARCFT:
        e.errhdl(e.PATH, m, "W", "320", " HS ")
    elif e.AHS[i] > 3000.0:
        e.errhdl(e.PATH, m, "E", "324", e.SRCID[i])
    for a, txt in ((e.ASYINI, " SYINIT "), (e.ASZINI, " SZINIT ")):
        if a[i] < 0.0:
            e.errhdl(e.PATH, m, "E", "209", txt)
        elif a[i] < 1.0e-5:
            e.errhdl(e.PATH, m, "W", "320", txt)
            a[i] = 1.0e-5
        elif a[i] > 200.0:
            e.errhdl(e.PATH, m, "W", "320", txt)


def _qs_hs_area(e, m, i):
    if e.AQS[i] == 0.0:
        e.errhdl(e.PATH, m, "W", "320", " QS ")
    if e.AHS[i] < 0.0:
        e.errhdl(e.PATH, m, "E", "209", " HS ")
    elif e.AHS[i] > 100.0 and (m != "APARM" or not e.ARCFT):
        e.errhdl(e.PATH, m, "W", "320", " HS ")
    elif e.AHS[i] > 3000.0:
        e.errhdl(e.PATH, m, "E", "324", e.SRCID[i])


def _szini_area(e, m, i):
    if e.ASZINI[i] < 0.0:
        e.errhdl(e.PATH, m, "E", "209", " SZINIT ")
    elif e.ASZINI[i] < 1.0e-5:
        e.ASZINI[i] = 1.0e-5
    elif e.ASZINI[i] > 200.0:
        e.errhdl(e.PATH, m, "W", "320", " SZINIT ")


def aparm(e, i, temp):
    """APARM: fuentes de área rectangulares."""
    m = "APARM"
    e.AQS[i], e.AHS[i] = temp[1], temp[2]
    ifc = e.IFC
    if ifc == 6:
        e.AXINIT[i] = temp[3]
        e.AYINIT[i] = e.AXINIT[i]
        e.AANGLE[i] = 0.0
        e.ASZINI[i] = 0.0
    elif ifc == 7:
        e.AXINIT[i], e.AYINIT[i], e.AANGLE[i], e.ASZINI[i] = temp[3], temp[4], 0.0, 0.0
    elif ifc == 8:
        e.AXINIT[i], e.AYINIT[i], e.AANGLE[i], e.ASZINI[i] = temp[3], temp[4], temp[5], 0.0
    elif ifc == 9:
        e.AXINIT[i], e.AYINIT[i], e.AANGLE[i], e.ASZINI[i] = temp[3], temp[4], temp[5], temp[6]
    _qs_hs_area(e, m, i)
    for a, txt in ((e.AXINIT, " XINIT "), (e.AYINIT, " YINIT ")):
        if a[i] < 0.0:
            e.errhdl(e.PATH, m, "E", "209", txt)
        elif a[i] < 1.0e-5:
            e.errhdl(e.PATH, m, "W", "320", txt)
            a[i] = 1.0e-5
        elif a[i] > 2000.0:
            e.errhdl(e.PATH, m, "W", "320", txt)
    if abs(e.AANGLE[i]) > 180.0:
        e.errhdl(e.PATH, m, "W", "320", " ANGLE ")
    _szini_area(e, m, i)
    if e.AYINIT[i] / e.AXINIT[i] > 100.00001 or e.AXINIT[i] / e.AYINIT[i] > 100.00001:
        e.errhdl(e.PATH, m, "W", "391", e.SRCID[i])
    e.NVERTS[i] = 4
    xv, yv = e.AXVERT, e.AYVERT
    ang = e.AANGLE[i] * e.DTORAD
    s, c = math.sin(ang), math.cos(ang)
    xv[1, i] = e.AXS[i]
    yv[1, i] = e.AYS[i]
    xv[2, i] = xv[1, i] + (e.AYINIT[i] * s)
    yv[2, i] = yv[1, i] + (e.AYINIT[i] * c)
    xv[3, i] = xv[2, i] + (e.AXINIT[i] * c)
    yv[3, i] = yv[2, i] - (e.AXINIT[i] * s)
    xv[4, i] = xv[3, i] - (e.AYINIT[i] * s)
    yv[4, i] = yv[3, i] - (e.AYINIT[i] * c)
    xv[5, i] = e.AXS[i]
    yv[5, i] = e.AYS[i]
    sx = sy = 0.0
    for j in range(1, 5):
        sx = sx + xv[j, i]
        sy = sy + yv[j, i]
    e.AXCNTR[i] = sx / 4.0
    e.AYCNTR[i] = sy / 4.0


_1EM5_R4 = float(np.float32(1.0e-5))


def lparm(e, i, temp):
    """LPARM: fuentes LINE (se tratan como un área rectangular girada entre los dos extremos)."""
    m = "LPARM"
    e.AQS[i] = temp[1]
    e.AHS[i] = temp[2]
    e.AWIDTH[i] = temp[3]
    if e.IFC == 7:
        e.ASZINI[i] = temp[4]
    else:
        e.ASZINI[i] = 0.0
    if e.AQS[i] == 0.0:
        e.errhdl(e.PATH, m, "W", "320", " QS ")
    if e.AHS[i] < 0.0:
        e.errhdl(e.PATH, m, "E", "209", " HS ")
    elif e.AHS[i] > 100.0:
        e.errhdl(e.PATH, m, "W", "320", " HS ")
    if e.ASZINI[i] < 0.0:
        e.errhdl(e.PATH, m, "E", "209", " SZINIT ")
    elif e.ASZINI[i] < _1EM5_R4:
        e.ASZINI[i] = 1.0e-5
    elif e.ASZINI[i] > 200.0:
        e.errhdl(e.PATH, m, "W", "320", " SZINIT ")
    if e.AWIDTH[i] < 1.0:
        e.errhdl(e.PATH, m, "E", "320", " WIDTH ")
    xlen = e.AXS2[i] - e.AXS1[i]
    ylen = e.AYS2[i] - e.AYS1[i]
    e.AXS[i] = (e.AXS1[i] + e.AXS2[i]) * 0.5
    e.AYS[i] = (e.AYS1[i] + e.AYS2[i]) * 0.5
    e.AXINIT[i] = e.AWIDTH[i]
    e.AYINIT[i] = math.sqrt(xlen * xlen + ylen * ylen)
    e.AANGLE[i] = math.atan2(xlen, ylen) * e.RTODEG
    if e.AYINIT[i] / e.AXINIT[i] > 100.00001 or e.AXINIT[i] / e.AYINIT[i] > 100.00001:
        e.errhdl(e.PATH, m, "W", "390", e.SRCID[i])
    e.NVERTS[i] = 4
    xv, yv = e.AXVERT, e.AYVERT
    ang = e.AANGLE[i] * e.DTORAD
    xv[1, i] = e.AXS1[i] - (e.AXINIT[i] / 2.0) * math.cos(ang)
    yv[1, i] = e.AYS1[i] + (e.AXINIT[i] / 2.0) * math.sin(ang)
    xv[2, i] = xv[1, i] + (e.AYINIT[i] * math.sin(ang))
    yv[2, i] = yv[1, i] + (e.AYINIT[i] * math.cos(ang))
    xv[3, i] = xv[2, i] + (e.AXINIT[i] * math.cos(ang))
    yv[3, i] = yv[2, i] - (e.AXINIT[i] * math.sin(ang))
    xv[4, i] = xv[3, i] - (e.AYINIT[i] * math.sin(ang))
    yv[4, i] = yv[3, i] - (e.AYINIT[i] * math.cos(ang))
    xv[5, i] = xv[1, i]
    yv[5, i] = yv[1, i]
    sx = sy = 0.0
    for j in range(1, 5):
        sx = sx + xv[j, i]
        sy = sy + yv[j, i]
    e.AXCNTR[i] = sx / float(4)
    e.AYCNTR[i] = sy / float(4)


def apparm(e, i, temp):
    """APPARM: fuentes de área poligonales (los vértices llegan con AREAVERT)."""
    m = "APPARM"
    e.AQS[i], e.AHS[i] = temp[1], temp[2]
    e.NVERTS[i] = nint(temp[3])
    e.ASZINI[i] = temp[4] if e.IFC == 7 else 0.0
    _qs_hs_area(e, m, i)
    _szini_area(e, m, i)
    if e.NVERTS[i] < 3:
        e.errhdl(e.PATH, m, "E", "380", " NVERT ")
    elif e.NVERTS[i] > e.NVMAX - 8:
        e.errhdl(e.PATH, m, "W", "406", e.SRCID[i])


def arvert(e):
    """ARVERT: vértices de una fuente AREAPOLY."""
    m = "ARVERT"
    f = e.FIELD
    if e.LOCE[3] - e.LOCB[3] <= 11:
        soid = fc(f[3], 12)
    else:
        e.errhdl(e.PATH, m, "E", "230", f[3][:12])
        return
    isdx, found = sindex(e.SRCID, e.NSRC, soid)
    if not found:
        e.errhdl(e.PATH, m, "E", "300", e.KEYWRD)
        return
    iset = int(e.IWRK2[isdx, 10])
    dx = dy = 0.0
    for k in range(4, e.IFC, 2):
        dx, imit = dbl(e, k, dx)
        e.IMIT = imit
        if imit != 1:
            e.errhdl(e.PATH, m, "E", "208", e.KEYWRD)
            continue
        dy, imit = dbl(e, k + 1, dy)
        e.IMIT = imit
        if imit != 1:
            e.errhdl(e.PATH, m, "E", "208", e.KEYWRD)
            continue
        iset += 1
        if iset == 1:
            if dx != e.AXS[isdx]:
                e.errhdl(e.PATH, m, "E", "262", e.SRCID[isdx])
            if dy != e.AYS[isdx]:
                e.errhdl(e.PATH, m, "E", "262", e.SRCID[isdx])
        if iset <= e.NVERTS[isdx] + 1:
            e.AXVERT[iset, isdx] = dx
            e.AYVERT[iset, isdx] = dy
        else:
            e.errhdl(e.PATH, m, "E", "264", e.SRCID[isdx])
    e.ISET = iset
    e.IWRK2[isdx, 10] = iset


def acparm(e, i, temp):
    """ACPARM: fuentes de área circulares."""
    m = "ACPARM"
    e.AQS[i], e.AHS[i], e.RADIUS[i] = temp[1], temp[2], temp[3]
    e.NVERTS[i] = nint(temp[4]) if e.IFC >= 7 else 20
    e.ASZINI[i] = temp[5] if e.IFC == 8 else 0.0
    _qs_hs_area(e, m, i)
    if e.RADIUS[i] < 0.0:
        e.errhdl(e.PATH, m, "E", "209", " RADIUS ")
    elif e.RADIUS[i] <= 0.5:
        e.errhdl(e.PATH, m, "E", "203", " RADIUS ")
    elif e.RADIUS[i] > 10000.0:
        e.errhdl(e.PATH, m, "W", "320", " RADIUS ")
    _szini_area(e, m, i)
    if e.NVERTS[i] < 3:
        e.errhdl(e.PATH, m, "E", "380", " NVERT ")
        return
    elif e.NVERTS[i] > e.NVMAX + 1:
        e.NVMAX = int(e.NVERTS[i]) + 1
    gencir(e, i)
    e.AXCNTR[i] = e.AXS[i]
    e.AYCNTR[i] = e.AYS[i]


def gencir(e, i):
    """GENCIR: polígono equivalente (misma área) a un círculo."""
    nsides = int(e.NVERTS[i])
    anginc = 360.0 / float(nsides)
    ang = 0.0
    area = e.PI * e.RADIUS[i] * e.RADIUS[i]
    triarea = area / float(nsides)
    opp = math.sqrt(triarea * math.tan(anginc / (2.0 * e.RTODEG)))
    newrad = opp / (math.sin(anginc / (2.0 * e.RTODEG)))
    for j in range(1, nsides + 1):
        if j != 1:
            ang = ang + anginc
        e.AXVERT[j, i] = (newrad * math.sin(ang / e.RTODEG)) + e.AXS[i]
        e.AYVERT[j, i] = (newrad * math.cos(ang / e.RTODEG)) + e.AYS[i]
    e.AXVERT[nsides + 1, i] = e.AXVERT[1, i]
    e.AYVERT[nsides + 1, i] = e.AYVERT[1, i]
    e.AXINIT[i] = math.sqrt(area)
    e.AYINIT[i] = math.sqrt(area)


def _rango(e, m, soid):
    """Identificadores LID-HID de un campo con rango (FSPLIT + SETIDG). None si es un solo ID."""
    _r, lid, hid = fsplit(e, e.PATH, e.KEYWRD, soid, ILEN_FLD, "-")
    lid, hid = fc(lid, 12), fc(hid, 12)
    if lid == hid:
        return None
    l1, il, l2 = setidg(lid)
    h1, ih, h2 = setidg(hid)
    if h1 < l1 or ih < il or h2 < l2:
        e.errhdl(e.PATH, m, "E", "203", "SRCRANGE")
        return False
    return lid, hid


def dsbldg(e):
    """DSBLDG: dimensiones de edificios por sector (BUILDHGT/WID/LEN, XBADJ, YBADJ)."""
    m = "DSBLDG"
    if e.IFC <= 2:
        e.errhdl(e.PATH, m, "E", "200", e.KEYWRD)
        return
    elif e.IFC == 3:
        e.errhdl(e.PATH, m, "E", "201", e.KEYWRD)
        return
    soid = e.FIELD[3]
    r = _rango(e, m, soid)
    if r is None:
        isdx, found = sindex(e.SRCID, e.NSRC, soid)
        if found:
            if e.SRCTYP[isdx][:5] == "POINT":
                dsfill(e, isdx)
            else:
                e.errhdl(e.PATH, m, "W", "233", e.SRCID[isdx])
        else:
            e.errhdl(e.PATH, m, "E", "300", e.KEYWRD)
    elif r:
        lid, hid = r
        for i in range(1, e.NUMSRC + 1):
            if asngrp(e.SRCID[i], lid, hid) and e.SRCTYP[i][:5] == "POINT":
                dsfill(e, i)


_DS = {"BUILDHGT": (1, "ADSBH", True), "BUILDWID": (2, "ADSBW", True), "BUILDLEN": (11, "ADSBL", True),
       "XBADJ": (12, "ADSXADJ", False), "YBADJ": (13, "ADSYADJ", False)}


def dsfill(e, isdx):
    """DSFILL: rellena los valores por sector de una fuente."""
    m = "DSFILL"
    col, nom, positivo = _DS[e.KEYWRD]
    a = getattr(e, nom)
    iset = int(e.IWRK2[isdx, col])
    for k in range(4, e.IFC + 1):
        e.DNUM, imit = dbl(e, k, e.DNUM)
        e.IMIT = imit
        if imit == -1:
            e.errhdl(e.PATH, m, "E", "208", e.KEYWRD)
            continue
        for _j in range(imit):
            iset += 1
            if iset <= e.NSEC:
                a[iset, isdx] = e.DNUM
                if positivo and e.DNUM < 0.0:
                    e.errhdl(e.PATH, m, "E", "209", e.KEYWRD)
            else:
                e.errhdl(e.PATH, m, "E", "234", e.KEYWRD)
    e.ISET = iset
    e.IWRK2[isdx, col] = iset


_IQMAX = {"SEASON": 4, "MONTH": 12, "HROFDY": 24, "WSPEED": 6, "SEASHR": 96, "HRDOW": 72, "HRDOW7": 168,
          "SHRDOW": 288, "SHRDOW7": 672, "MHRDOW": 864, "MHRDOW7": 2016}


def emvary(e):
    """EMVARY: factores de emisión variables (EMISFACT)."""
    m = "EMVARY"
    if e.IFC <= 2:
        e.errhdl(e.PATH, m, "E", "200", e.KEYWRD)
        return
    elif e.IFC < 5:
        e.errhdl(e.PATH, m, "E", "201", e.KEYWRD)
        return
    soid = e.FIELD[3]

    def una(isdx):
        e.QFLAG[isdx] = fc(e.FIELD[4], 8)
        q = e.QFLAG[isdx]
        if q in _IQMAX:
            e._IQMAX = _IQMAX[q]
            if q.startswith(("HRDOW", "SHRDOW", "MHRDOW")):
                e.L_DAYOFWEEKOPTS = True
        else:
            e.errhdl(e.PATH, m, "E", "203", "QFLAG")
        iqmax = getattr(e, "_IQMAX", 0)
        if iqmax <= e.NQF:
            effill(e, isdx, iqmax)
        else:
            e.DUMMY = fwrite("('NQF =',I6)", e.NQF)[0]
            e.errhdl(e.PATH, m, "E", "260", e.DUMMY)

    r = _rango(e, m, soid)
    if r is None:
        isdx, found = sindex(e.SRCID, e.NSRC, soid)
        if found:
            una(isdx)
        else:
            e.errhdl(e.PATH, m, "E", "300", e.KEYWRD)
    elif r:
        lid, hid = r
        for i in range(1, e.NUMSRC + 1):
            if asngrp(e.SRCID[i], lid, hid):
                una(i)


def effill(e, isdx, iqmax):
    """EFFILL: valores de los factores de emisión."""
    m = "EFFILL"
    iset = int(e.IWRK2[isdx, 4])
    for k in range(5, e.IFC + 1):
        e.DNUM, imit = dbl(e, k, e.DNUM)
        e.IMIT = imit
        if imit == -1:
            e.errhdl(e.PATH, m, "E", "208", e.KEYWRD)
            continue
        for _j in range(imit):
            iset += 1
            if iset <= iqmax:
                e.QFACT[iset, isdx] = e.DNUM
                if e.DNUM < 0.0:
                    e.errhdl(e.PATH, m, "E", "209", e.KEYWRD)
            else:
                if isdx <= 999:
                    e.DUMMY = fwrite("('QFACT Src',I3.3)", isdx)[0]
                elif isdx <= 99999:
                    e.DUMMY = fwrite("('QF Src',I5.5)", isdx)[0]
                else:
                    e.DUMMY = "QF Src>99999"
                e.errhdl(e.PATH, m, "E", "231", e.DUMMY)
    e.ISET = iset
    e.IWRK2[isdx, 4] = iset


_IBGMAX = {"ANNUAL": 1, "SEASON": 4, "MONTH": 12, "HROFDY": 24, "WSPEED": 6, "SEASHR": 96,
           "HRDOW": 72, "HRDOW7": 168, "SHRDOW": 288, "SHRDOW7": 672, "MHRDOW": 864, "MHRDOW7": 2016}


def back_grnd(e):
    """BACK_GRND: tarjeta BACKGRND (valores de fondo que varían en el tiempo, o fichero horario
    con HOURLY), por sector si hay BGSECTOR."""
    from .entrada_meteo import _abierto
    m = "BACK_GRND"
    e.L_BACKGRND = True
    f = e.FIELD
    num_int = num_real = 0
    if not e.L_BGSECTOR:
        if e.IFC <= 2:
            e.errhdl(e.PATH, m, "E", "200", e.KEYWRD)
            return
        if e.IFC < 4:
            e.errhdl(e.PATH, m, "E", "201", e.KEYWRD)
            return
        if f[3][:4] == "SECT":
            e.errhdl(e.PATH, m, "E", "171", e.KEYWRD)
            return
        e.IBGSECT = 1
        i = 3
    else:
        if e.IFC <= 2:
            e.errhdl(e.PATH, m, "E", "200", e.KEYWRD)
            return
        if e.IFC == 4:
            if f[3][:4] != "SECT":
                e.errhdl(e.PATH, m, "E", "203", "BGSECTOR ID")
            else:
                e.errhdl(e.PATH, m, "E", "201", e.KEYWRD)
            return
        if e.IFC < 5:
            e.errhdl(e.PATH, m, "E", "201", e.KEYWRD)
            return
        nb = e.NUMBGSECTS
        if f[3] == "SECT1":
            e.IBGSECT = 1
        elif f[3] in ("SECT2", "SECT3", "SECT4", "SECT5") and nb >= int(f[3][4]):
            e.IBGSECT = int(f[3][4])
        elif f[3] == "SECT6" and nb == 6:
            e.IBGSECT = 6
        else:
            e.errhdl(e.PATH, m, "E", "203", "BGSECTOR ID")
            return
        i = 4
    ib = e.IBGSECT
    if e.IBGMAX[ib] >= 1 and e.BFLAG[ib] != f[i] and f[i] != "HOURLY":
        if not e.L_BGSECTOR:
            e.errhdl(e.PATH, m, "E", "165", f[i])
        elif len(f[i]) > 6:
            e.errhdl(e.PATH, m, "E", "165", fwrite("('SEC',I1,1X,A)", ib, f[i])[0])
        else:
            e.errhdl(e.PATH, m, "E", "165", fwrite("('SECT',I1,1X,A)", ib, f[i])[0])
    elif f[i] != "HOURLY":
        e.BFLAG[ib] = fc(f[i], 8)
        e.L_BGVALUES[ib] = True
    elif e.L_BGFILE[ib]:
        e.errhdl(e.PATH, m, "E", "168", fwrite("('BGSECT',I1)", ib)[0])
    else:
        e.L_BGHOURLY = True
        e.L_BGFILE[ib] = True
    if e.L_BGFILE[ib] and f[i] == "HOURLY":
        if e.LOCE[i + 1] - e.LOCB[i + 1] > ILEN_FLD - 1:
            e.errhdl(e.PATH, m, "E", "291", i8(ILEN_FLD))
            return
        e.BKGRND_FILE[ib] = fc(e.RUNST1[int(e.LOCB[i + 1]) - 1:int(e.LOCE[i + 1])], 200)
        e.IBGUNT[ib] = 2000 + ib
        if _abierto(e, e.BKGRND_FILE[ib]) or e.IBGUNT[ib] in e.U:
            e.errhdl(e.PATH, m, "E", "501", e.KEYWRD)
            return
        try:
            e.abrir_entrada(int(e.IBGUNT[ib]), e.BKGRND_FILE[ib])
        except OSError:
            if not e.L_BGSECTOR:
                e.errhdl(e.PATH, m, "E", "500", "BG File")
            else:
                e.errhdl(e.PATH, m, "E", "500", fwrite("('BGFILE SECT',I1)", ib)[0])
            return
        e.FUNITARRAY[e.FUNITIND] = int(e.IBGUNT[ib])
        e.FNAMEARRAY[e.FUNITIND] = e.BKGRND_FILE[ib]
        e.FTYPARRAY[e.FUNITIND] = "BACKGROUND"
        e.FUNITIND += 1
        if e.IFC == i + 2:
            if e.LOCE[i + 2] - e.LOCB[i + 2] <= ILEN_FLD - 1:
                form = fc(e.RUNST1[int(e.LOCB[i + 2]) - 1:int(e.LOCE[i + 2])], 200)
                e.BGFORM[ib] = form
                if f[i + 2] == "FREE":
                    e.BGFORM[ib] = "FREE"
                else:
                    for c in form:
                        if c in "Ii":
                            num_int += 1
                        elif c in "FfEeDd":
                            num_real += 1
                        elif c in "'\"-;":
                            e.errhdl(e.PATH, m, "W", "292", fwrite("('InvalidChr ',A)", c)[0])
                    if num_int < 1 or num_int > 4:
                        e.errhdl(e.PATH, m, "W", "292", fwrite("('NumInts= ',I3)", num_int)[0])
                    if num_real != 1:
                        e.errhdl(e.PATH, m, "W", "292", fwrite("('NumReal= ',I3)", num_real)[0])
            else:
                e.errhdl(e.PATH, m, "E", "292",
                         fwrite("('LEN=',I6)", int(e.LOCE[i + 2] - e.LOCB[i + 2]))[0])
        elif e.IFC == i + 1:
            e.BGFORM[ib] = "FREE"
        elif e.IFC > i + 2:
            e.errhdl(e.PATH, m, "E", "202", e.KEYWRD)
            return
    else:
        n = _IBGMAX.get(e.BFLAG[ib])
        if n is None:
            e.errhdl(e.PATH, m, "E", "203", "BFLAG")
            return
        e.IBGMAX[ib] = n
        if e.BFLAG[ib] in ("HRDOW", "HRDOW7", "SHRDOW", "SHRDOW7", "MHRDOW", "MHRDOW7"):
            e.L_DAYOFWEEKOPTS = True
        bgfill(e)


def bgfill(e):
    """BGFILL: guarda los valores de fondo de la tarjeta en BACKGRND(:, IBGSECT)."""
    m = "BGFILL"
    ib = e.IBGSECT
    iset = int(e.IBKGRD[ib])
    for k in range(5 if e.L_BGSECTOR else 4, e.IFC + 1):
        e.DNUM, imit = dbl(e, k, e.DNUM)
        if imit == -1:
            e.errhdl(e.PATH, m, "E", "208", e.KEYWRD)
            continue
        fin = False
        for _j in range(imit):
            iset += 1
            if iset <= e.IBGMAX[ib]:
                e.BACKGRND[iset, ib] = e.DNUM
                if e.DNUM < 0.0:
                    e.errhdl(e.PATH, m, "E", "209", e.KEYWRD)
            else:
                d = fwrite("('BCKGRD SECT',I1)", ib)[0] if e.L_BGSECTOR else "BACKGRND"
                e.errhdl(e.PATH, m, "E", "231", d)
                fin = True
                break
        if fin:
            break
    e.IBKGRD[ib] = iset


def back_unit(e):
    """BACK_UNIT: unidades de los valores de fondo."""
    m = "BACK_UNIT"
    if e.IFC <= 2:
        e.errhdl(e.PATH, m, "E", "200", e.KEYWRD)
        return
    if e.IFC > 3:
        e.errhdl(e.PATH, m, "E", "202", e.KEYWRD)
        return
    u = e.FIELD[3]
    if u == "UG/M3":
        e.BACKUNITS = u
    elif u in ("PPM", "PPB"):
        if e.POLLUT in ("NO2", "SO2", "CO"):
            e.BACKUNITS = u
        else:
            e.errhdl(e.PATH, m, "E", "203", "BackUnits")


def bgsector(e):
    """BGSECTOR: límites de los sectores (hacia donde sopla el viento) del fondo variable."""
    m = "BGSECTOR"
    if e.IFC <= 2:
        e.errhdl(e.PATH, m, "E", "200", e.KEYWRD)
        return
    if e.IFC < 4:
        e.errhdl(e.PATH, m, "E", "201", e.KEYWRD)
        return
    if e.IFC > 8:
        e.errhdl(e.PATH, m, "E", "202", e.KEYWRD)
        return
    e.L_BGSECTOR = True
    malo = False
    for i in range(3, e.IFC + 1):
        e.DNUM, imit = dbl(e, i, e.DNUM)
        if imit == -1:
            e.errhdl(e.PATH, m, "E", "208", fwrite("('BGSECT',I1)", i - 2)[0])
            malo = True
            continue
        e.BGSECT[i - 2] = e.DNUM
        b = e.BGSECT[i - 2]
        if b < 0.0 or b > 360.0:
            if b > 9999.0:
                d = "BGSECT>9999."
            elif b < -999.0:
                d = "BGSECT<-999."
            else:
                d = fwrite("('BGSECT=',F5.0)", b)[0]
            e.errhdl(e.PATH, m, "E", "380", d)
    if malo:
        return
    e.NUMBGSECTS = e.IFC - 2
    n = e.NUMBGSECTS
    bs = e.BGSECT
    for i in range(1, n):
        if bs[i + 1] < bs[i]:
            e.errhdl(e.PATH, m, "E", "222", fwrite("('BGSECT',I1,' < #',I1)", i + 1, i)[0])
        elif bs[i + 1] < bs[i] + 30.0:
            e.errhdl(e.PATH, m, "E", "227", fwrite("('BGSECT',I1,' < 30')", i + 1)[0])
        elif bs[i + 1] < bs[i] + 60.0:
            e.errhdl(e.PATH, m, "W", "227", fwrite("('BGSECT',I1,' < 60')", i + 1)[0])
    if (bs[1] + 360.0) - bs[n] < 30.0:
        e.errhdl(e.PATH, m, "E", "227", fwrite("('BGSECT',I1,' < 30')", n)[0])
    elif (bs[1] + 360.0) - bs[n] < 60.0:
        e.errhdl(e.PATH, m, "W", "227", fwrite("('BGSECT',I1,' < 60')", n)[0])


def emunit(e):
    """EMUNIT: factor y etiquetas de unidades de emisión y salida."""
    m = "EMUNIT"
    if e.IFC <= 2:
        e.errhdl(e.PATH, m, "E", "200", e.KEYWRD)
        return
    elif e.IFC < 5:
        e.errhdl(e.PATH, m, "E", "201", e.KEYWRD)
        return
    elif e.IFC > 5:
        e.errhdl(e.PATH, m, "E", "202", e.KEYWRD)
        return
    e.DNUM, imit = dbl(e, 3, e.DNUM)
    e.IMIT = imit
    if imit != 1:
        e.errhdl(e.PATH, m, "E", "208", e.KEYWRD)
        return
    e.EMIFAC[1] = e.DNUM
    e.EMILBL[1] = fc(e.FIELD[4], 40)
    e.OUTLBL[1] = fc(e.FIELD[5], 40)
    if not e.CONC and e.ANNUAL:
        e.PERLBL[1] = fc(e.RUNST1[int(e.LOCB[5]) - 1:int(e.LOCE[5])] + "/YR", 40)
    else:
        e.PERLBL[1] = fc(e.FIELD[5], 40)


def counit(e):
    """COUNIT: factor y etiquetas de unidades de concentración."""
    m = "COUNIT"
    if e.IFC <= 2:
        e.errhdl(e.PATH, m, "E", "200", e.KEYWRD)
        return
    elif e.IFC < 5:
        e.errhdl(e.PATH, m, "E", "201", e.KEYWRD)
        return
    elif e.IFC > 5:
        e.errhdl(e.PATH, m, "E", "202", e.KEYWRD)
        return
    e.DNUM, imit = dbl(e, 3, e.DNUM)
    e.IMIT = imit
    if imit != 1:
        e.errhdl(e.PATH, m, "E", "208", e.KEYWRD)
        return
    e.EMIFAC[1] = e.DNUM
    e.EMILBL[1] = fc(e.FIELD[4], 40)
    e.OUTLBL[1] = fc(e.FIELD[5], 40)
    e.PERLBL[1] = fc(e.FIELD[5], 40)


# ---------------------------------------------------------------------------- deposición
def dpunit(e):
    """DPUNIT: factor y etiquetas de unidades de los depósitos (DEPOUNIT). Se aplica a los NTYP
    tipos (o del 2 en adelante si se calcula también CONC)."""
    m = "DPUNIT"
    if e.IFC <= 2:
        e.errhdl(e.PATH, m, "E", "200", e.KEYWRD)
        return
    elif e.IFC < 5:
        e.errhdl(e.PATH, m, "E", "201", e.KEYWRD)
        return
    elif e.IFC > 5:
        e.errhdl(e.PATH, m, "E", "202", e.KEYWRD)
        return
    e.DNUM, imit = dbl(e, 3, e.DNUM)
    e.IMIT = imit
    if imit != 1:
        e.errhdl(e.PATH, m, "E", "208", e.KEYWRD)
        return
    for i in range(1 if not e.CONC else 2, e.NTYP + 1):
        e.EMIFAC[i] = e.DNUM
        e.EMILBL[i] = fc(e.FIELD[4], 40)
        e.OUTLBL[i] = fc(e.FIELD[5], 40)
        if e.ANNUAL:
            e.PERLBL[i] = fc(e.RUNST1[int(e.LOCB[5]) - 1:int(e.LOCE[5])] + "/YR", 40)
        else:
            e.PERLBL[i] = fc(e.FIELD[5], 40)


def partdep(e):
    """PARTDEP: parámetros de deposición de partículas (PARTDIAM, MASSFRAX, PARTDENS)."""
    m = "PARTDEP"
    if e.IFC <= 2:
        e.errhdl(e.PATH, m, "E", "200", e.KEYWRD)
        return
    elif e.IFC == 3:
        e.errhdl(e.PATH, m, "E", "201", e.KEYWRD)
        return
    if e.KEYWRD == "PARTDIAM":
        inppdm(e)
    elif e.KEYWRD == "MASSFRAX":
        inpphi(e)
    elif e.KEYWRD == "PARTDENS":
        inppdn(e)


def _error_npd(e, m):
    e.DUMMY = fwrite("('NPD= ',I7)", e.NPDMAX)[0]
    e.errhdl(e.PATH, m, "E", "290", e.DUMMY)


def _inppdm_fuente(e, m, isdx, rango):
    """Diámetros de una fuente (INPPDM). Devuelve False si el original salta a la fuente
    siguiente (CYCLE SOURCE_LOOP) sin guardar el contador."""
    e.ISET = int(e.IWRK2[isdx, 5])
    for k in range(4, e.IFC + 1):
        e.DNUM, imit = dbl(e, k, e.DNUM)
        e.IMIT = imit
        if imit == -1:
            e.errhdl(e.PATH, m, "E", "208", e.KEYWRD)
            if rango:
                return False
            continue
        elif imit > 1:
            # la repetición «n*valor» no tiene sentido para los diámetros
            e.errhdl(e.PATH, m, "E", "288", e.KEYWRD)
            if rango:
                return False
            continue
        elif e.DNUM <= 0.001 or e.DNUM > 1000.0:
            e.errhdl(e.PATH, m, "E", "335", e.SRCID[isdx])
        e.ISET += 1
        if e.ISET <= e.NPDMAX:
            e.APDIAM[e.ISET, isdx] = e.DNUM
        else:
            _error_npd(e, m)
    e.IWRK2[isdx, 5] = e.ISET
    return True


def inppdm(e):
    """INPPDM: diámetros de las categorías de tamaño de partícula (PARTDIAM)."""
    m = "INPPDM"
    soid = e.FIELD[3]
    r = _rango(e, m, soid)
    if r is None:
        isdx, found = sindex(e.SRCID, e.NSRC, soid)
        if found and not e.L_METHOD2[isdx]:
            _inppdm_fuente(e, m, isdx, False)
        elif found and e.L_METHOD2[isdx]:
            e.errhdl(e.PATH, m, "E", "386", e.SRCID[isdx])
        else:
            e.errhdl(e.PATH, m, "E", "300", e.KEYWRD)
    elif r:
        lid, hid = r
        for i in range(1, e.NUMSRC + 1):
            ingrp = asngrp(e.SRCID[i], lid, hid)
            if ingrp and not e.L_METHOD2[i]:
                _inppdm_fuente(e, m, i, True)
            elif ingrp and e.L_METHOD2[i]:
                e.errhdl(e.PATH, m, "E", "386", e.SRCID[i])


def _inpphi_fuente(e, m, isdx, rango):
    """Fracciones másicas de una fuente (INPPHI)."""
    e.ISET = int(e.IWRK2[isdx, 6])
    for k in range(4, e.IFC + 1):
        e.DNUM, imit = dbl(e, k, e.DNUM)
        e.IMIT = imit
        if imit == -1:
            e.errhdl(e.PATH, m, "E", "208", e.KEYWRD)
            if rango:
                return
            continue
        if e.DNUM < 0.0 or e.DNUM > 1.0:
            e.errhdl(e.PATH, m, "E", "332", e.SRCID[isdx])
        for _j in range(imit):
            e.ISET += 1
            if e.ISET <= e.NPDMAX:
                e.APHI[e.ISET, isdx] = e.DNUM
            else:
                _error_npd(e, m)
    e.IWRK2[isdx, 6] = e.ISET


def inpphi(e):
    """INPPHI: fracciones másicas de cada categoría de tamaño (MASSFRAX)."""
    m = "INPPHI"
    soid = e.FIELD[3]
    r = _rango(e, m, soid)
    if r is None:
        isdx, found = sindex(e.SRCID, e.NSRC, soid)
        if found:
            _inpphi_fuente(e, m, isdx, False)
        else:
            e.errhdl(e.PATH, m, "E", "300", e.KEYWRD)
    elif r:
        lid, hid = r
        for i in range(1, e.NUMSRC + 1):
            if asngrp(e.SRCID[i], lid, hid):
                _inpphi_fuente(e, m, i, True)


def _inppdn_fuente(e, m, isdx, rango):
    """Densidades de una fuente (INPPDN). Con rango de fuentes el original rechaza también la
    repetición «n*valor» (IMIT distinto de 1)."""
    e.ISET = int(e.IWRK2[isdx, 7])
    for k in range(4, e.IFC + 1):
        e.DNUM, imit = dbl(e, k, e.DNUM)
        e.IMIT = imit
        if (rango and imit != 1) or (not rango and imit == -1):
            e.errhdl(e.PATH, m, "E", "208", e.KEYWRD)
            if rango:
                return
            continue
        if e.DNUM <= 0.0:
            e.errhdl(e.PATH, m, "E", "334", e.SRCID[isdx])
        elif e.DNUM <= 0.1:
            e.errhdl(e.PATH, m, "W", "334", e.SRCID[isdx])
        for _j in range(imit):
            e.ISET += 1
            if e.ISET <= e.NPDMAX:
                e.APDENS[e.ISET, isdx] = e.DNUM
            else:
                _error_npd(e, m)
    e.IWRK2[isdx, 7] = e.ISET


def inppdn(e):
    """INPPDN: densidad de las partículas de cada categoría (PARTDENS)."""
    m = "INPPDN"
    soid = e.FIELD[3]
    r = _rango(e, m, soid)
    if r is None:
        isdx, found = sindex(e.SRCID, e.NSRC, soid)
        if found:
            _inppdn_fuente(e, m, isdx, False)
        else:
            e.errhdl(e.PATH, m, "E", "300", e.KEYWRD)
    elif r:
        lid, hid = r
        for i in range(1, e.NUMSRC + 1):
            if asngrp(e.SRCID[i], lid, hid):
                _inppdn_fuente(e, m, i, True)


# valores por defecto de GASDEPOS (campo = 0) para los contaminantes de la tabla (D068): difusividad
# en aire y en agua (cm2/s), resistencia cuticular de las hojas (s/cm) y constante de Henry
_GAS_TABLA = {"HG0": (5.5e-02, 6.4e-06, 1.0e05, 7.19e02), "HGII": (4.5e-02, 5.2e-06, 1.0e05, 7.2e-05),
              "TCDD": (5.196e-02, 4.392e-06, 9.67, 1.46), "BAP": (5.13e-02, 4.44e-06, 4.41e-01, 4.6e-02),
              "SO2": (1.112e-01, 1.83e-05, 7.32e02, 7.2e01), "NO2": (1.361e-01, 1.4e-05, 1.2e04, 8.444e03)}
_GAS_CAMPOS = (("PDIFF", "PDIFF"), ("PDIFFW", "PDIFFW"), ("RCLI", "RCLI"), ("HENRY", "HENRY"))


def _gasdep_fuente(e, m, isdx, aviso):
    e.SOGAS[isdx] = "Y"
    dlookup = False
    tabla = _GAS_TABLA.get(e.POLLUT)
    for n, (nom, etq) in enumerate(_GAS_CAMPOS):
        e.DNUM, imit = dbl(e, 4 + n, e.DNUM)
        e.IMIT = imit
        if tabla is not None and e.DNUM == 0.0:
            e.DNUM = tabla[n]
            dlookup = True
        elif imit != 1:
            e.errhdl(e.PATH, m, "E", "208", e.KEYWRD)
        elif e.DNUM <= 0.0:
            e.errhdl(e.PATH, m, "E", "380", etq)
        getattr(e, nom)[isdx] = e.DNUM
    if aviso and dlookup:
        e.errhdl(e.PATH, m, "W", "473", e.SRCID[isdx])


def gasdep(e):
    """GASDEP: parámetros de deposición de gases (GASDEPOS): difusividad en aire y en agua,
    resistencia cuticular y constante de Henry."""
    m = "GASDEP"
    if e.IFC <= 2:
        e.errhdl(e.PATH, m, "E", "200", e.KEYWRD)
        return
    elif e.IFC < 7:
        e.errhdl(e.PATH, m, "E", "201", e.KEYWRD)
        return
    elif e.IFC > 7:
        e.errhdl(e.PATH, m, "E", "202", e.KEYWRD)
        return
    soid = e.FIELD[3]
    r = _rango(e, m, soid)
    if r is None:
        isdx, found = sindex(e.SRCID, e.NSRC, soid)
        if found:
            _gasdep_fuente(e, m, isdx, True)
        else:
            e.errhdl(e.PATH, m, "E", "300", e.KEYWRD)
    elif r:
        lid, hid = r
        for i in range(1, e.NUMSRC + 1):
            if asngrp(e.SRCID[i], lid, hid):
                # (con rango de fuentes el original no avisa del valor por defecto)
                _gasdep_fuente(e, m, i, False)


# valores por defecto de METHOD_2 (campo = 0): fracción fina y diámetro medio másico
_M2_TABLA = {"AR": (7.5e-01, 5.0e-01), "CD": (7.0e-01, 6.0e-01), "PB": (7.5e-01, 5.0e-01),
             "HG": (8.0e-01, 4.0e-01), "POC": (9.0e-01, 1.0e-01)}


def _meth_2_valores(e, m, isdx, rango):
    """Campos de METHOD_2 de una fuente. Devuelve False si el original sale (GO TO 999)."""
    tabla = _M2_TABLA.get(e.POLLUT)
    dlookup = False
    e.DNUM, imit = dbl(e, 4, e.DNUM)
    e.IMIT = imit
    if imit != 1:
        e.errhdl(e.PATH, m, "E", "208", e.KEYWRD)
        return False
    if rango:
        if e.DNUM < 0.0 or e.DNUM > 1.0:
            e.errhdl(e.PATH, m, "E", "332", e.SRCID[isdx])
        elif tabla is not None and e.DNUM == 0.0:
            e.DNUM = tabla[0]
    else:
        if tabla is not None and e.DNUM == 0.0:
            e.DNUM = tabla[0]
            dlookup = True
        elif e.DNUM < 0.0 or e.DNUM > 1.0:
            e.errhdl(e.PATH, m, "E", "332", e.SRCID[isdx])
    e.FINEMASS[isdx] = e.DNUM
    e.DNUM, imit = dbl(e, 5, e.DNUM)
    e.IMIT = imit
    if imit != 1:
        e.errhdl(e.PATH, m, "E", "208", e.KEYWRD)
        return False
    elif tabla is not None and e.DNUM == 0.0:
        e.DNUM = tabla[1]
        dlookup = True
    e.APDIAM[1, isdx] = e.DNUM
    e.APHI[1, isdx] = 1.0
    e.APDENS[1, isdx] = 1.0
    e.INPD[isdx] = 1
    if not rango and dlookup:
        e.errhdl(e.PATH, m, "W", "473", e.SRCID[isdx])
    return True


def meth_2(e):
    """METH_2: deposición de partículas por el método 2 (METHOD_2): fracción fina (< 2,5 micras)
    y diámetro medio másico; una sola categoría con fracción 1 y densidad 1."""
    m = "METH_2"
    if e.IFC <= 2:
        e.errhdl(e.PATH, m, "E", "200", e.KEYWRD)
        return
    elif e.IFC < 5:
        e.errhdl(e.PATH, m, "E", "201", e.KEYWRD)
        return
    elif e.IFC > 5:
        e.errhdl(e.PATH, m, "E", "202", e.KEYWRD)
        return
    soid = e.FIELD[3]
    r = _rango(e, m, soid)
    if r is None:
        isdx, found = sindex(e.SRCID, e.NSRC, soid)
        if found and not e.L_METHOD2[isdx] and e.IWRK2[isdx, 5] == 0:
            e.L_METHOD2[isdx] = True
            _meth_2_valores(e, m, isdx, False)
        elif found and e.L_METHOD2[isdx]:
            e.errhdl(e.PATH, m, "E", "387", e.SRCID[isdx])
        elif found and e.IWRK2[isdx, 5] > 0:
            e.errhdl(e.PATH, m, "E", "386", e.SRCID[isdx])
        else:
            e.errhdl(e.PATH, m, "E", "300", e.KEYWRD)
    elif r:
        lid, hid = r
        for i in range(1, e.NUMSRC + 1):
            if asngrp(e.SRCID[i], lid, hid):
                if not e.L_METHOD2[i] and e.IWRK2[i, 5] == 0:
                    e.L_METHOD2[i] = True
                elif e.L_METHOD2[i]:
                    e.errhdl(e.PATH, m, "E", "387", e.SRCID[i])
                    continue
                elif e.IWRK2[i, 5] > 0:
                    e.errhdl(e.PATH, m, "E", "386", e.SRCID[i])
                    continue
                if not _meth_2_valores(e, m, i, True):
                    return


def vdp1(e):
    """VDP1: cálculos de la deposición que no dependen de la hora (tras SETUP): paso a unidades SI
    de los parámetros de los gases y, para las partículas, factor de corrección de Cunningham
    (SCF), velocidad de sedimentación (AVGRAV) y tiempo de frenado (ATSTOP). SCF es un vector
    global que cada fuente sobrescribe: VDP usa después el de la última fuente con partículas
    (como en el original)."""
    a1, a2, a3 = 1.257, 0.4, 0.55
    xmfp = 6.5e-6
    vcon = 1.81e-4
    vair = 0.15
    rhoair = 1.2e-3
    if e.DEBUG:
        from . import depura
        depura.vdp1_ent(e)
    e.VAIRMS = 1.0e-4 * vair
    e.VDPHOR = 0.0001
    for j in range(1, e.NUMSRC + 1):
        npd = int(e.INPD[j])
        if npd <= 0 and not e.LUSERVD:
            if e.PDIFF[j] != 0.0 and e.PDIFFW[j] != 0.0 and e.RCLI[j] != 0.0 and e.HENRY[j] != 0.0:
                e.PDIFF[j] = e.PDIFF[j] * 1.0e-4
                e.PDIFFW[j] = e.PDIFFW[j] * 1.0e-4
                e.RCLI[j] = e.RCLI[j] * 1.0e2
                if e.DEBUG:
                    from . import depura
                    depura.vdp1_gas(e)
        elif npd > 0:
            for i in range(1, npd + 1):
                diamcm = 1.0e-4 * e.APDIAM[i, j]
                e.SCF[i] = 1.0 + 2.0 * xmfp * (a1 + a2 * math.exp(-a3 * diamcm / xmfp)) / diamcm
                e.AVGRAV[i, j] = max(0.0, (e.APDENS[i, j] - rhoair)) * e.G * (diamcm * diamcm) * \
                    e.SCF[i] / (18.0 * vcon)
                e.ATSTOP[i, j] = e.AVGRAV[i, j] / e.G
            if e.DEBUG:
                from . import depura
                depura.vdp1_part(e)


def sogrp(e):
    """SOGRP: grupos de fuentes (SRCGROUP)."""
    m = "SOGRP"
    f = e.FIELD
    if e.IFC <= 2:
        e.errhdl(e.PATH, m, "E", "200", e.KEYWRD)
        return
    elif e.IFC <= 3 and f[3] != "ALL":
        e.errhdl(e.PATH, m, "E", "201", e.KEYWRD)
        return
    cont = False
    if e.LOCE[3] - e.LOCB[3] <= 7:
        tempid = fc(f[3], 12)
        for i in range(1, e.NUMGRP + 1):
            if tempid == e.GRPID[i]:
                cont = True
                break
    else:
        e.errhdl(e.PATH, m, "E", "245", f[3][:12])
        return
    if not cont:
        e.IGRP += 1
        if e.IGRP > e.NGRP:
            e.DUMMY = fwrite("('NGRP=',I7)", e.NGRP)[0]
            e.errhdl(e.PATH, m, "E", "290", e.DUMMY)
            return
        e.NUMGRP += 1
        e.GRPID[e.IGRP] = fc(tempid, 8)
    igrp = e.IGRP
    if e.GRPID[igrp] == "ALL" and not cont:
        for i in range(1, e.NUMSRC + 1):
            e.IGROUP[i, igrp] = 1
        if e.L_BACKGRND:
            # el fondo NO entra por defecto en el grupo ALL
            if f[4] in ("NOBACKGROUND", "NOBACKGRND"):
                e.GRP_BACK[igrp] = False
                e.errhdl(e.PATH, m, "W", "298", "NOBACKGROUND")
            elif f[4] in ("BACKGROUND", "BACKGRND"):
                e.GRP_BACK[igrp] = True
                e.errhdl(e.PATH, m, "W", "298", "BACKGROUND  ")
            elif f[4] == "":
                e.GRP_BACK[igrp] = False
                e.errhdl(e.PATH, m, "W", "298", "NOBACKGROUND")
            return
        e.GRP_BACK[igrp] = False
        if e.IFC > 3:
            if f[4] in ("BACKGROUND", "BACKGRND"):
                e.errhdl(e.PATH, m, "E", "323", e.GRPID[igrp])
            else:
                e.errhdl(e.PATH, m, "E", "203", e.KEYWRD)
        return
    for i in range(4, e.IFC + 1):
        if e.L_BACKGRND:
            if f[i] in ("BACKGROUND", "BACKGRND"):
                e.GRP_BACK[igrp] = True
                continue
        elif f[i] in ("BACKGROUND", "BACKGRND"):
            e.errhdl(e.PATH, m, "E", "323", e.GRPID[igrp])
            continue
        if "-" not in f[i]:
            found = False
            for k in range(1, e.NUMSRC + 1):
                if f[i] == e.SRCID[k]:
                    found = True
                    if e.IGROUP[k, igrp] > 0:
                        e.DUMMY = fwrite("('G',I4.4,' S',I5.5)", min(igrp, 9999), min(k, 99999))[0]
                        e.errhdl(e.PATH, m, "W", "314", e.DUMMY)
                    e.IGROUP[k, igrp] = 1
                    break
            if not found:
                e.errhdl(e.PATH, m, "E", "224", f[i][:12])
        else:
            _r, lowid, higid = fsplit(e, e.PATH, e.KEYWRD, f[i], ILEN_FLD, "-")
            lowid, higid = fc(lowid, 12), fc(higid, 12)
            l1, il, l2 = setidg(lowid)
            h1, ih, h2 = setidg(higid)
            if h1 < l1 or ih < il or h2 < l2:
                e.errhdl(e.PATH, m, "E", "203", "SRCRANGE")
                continue
            for k in range(1, e.NUMSRC + 1):
                if asngrp(e.SRCID[k], lowid, higid):
                    e.IGROUP[k, igrp] = 1


def asngrp(inid, lowid, higid):
    """ASNGRP: ¿está el identificador dentro del rango LOWID-HIGID?"""
    i1, n, i2 = setidg(inid)
    l1, il, l2 = setidg(lowid)
    h1, ih, h2 = setidg(higid)
    return (l1 <= i1 <= h1) and (il <= n <= ih) and (l2 <= i2 <= h2)


def setidg(inid):
    """SETIDG: divide un identificador en (prefijo de letras, número, sufijo)."""
    s = inid[:12].ljust(12)
    ii = len(inid[:12].rstrip(" "))
    numid = c1 = c2 = ""
    i = 1
    chki = s[0]
    fin = False
    while chki < "0" or chki > "9":
        c1 = s[0:i]
        i += 1
        if i > ii:
            fin = True
            break
        chki = s[i - 1]
    if not fin:
        istr = i
        while "0" <= chki <= "9":
            numid = s[istr - 1:i]
            i += 1
            if i > ii:
                fin = True
                break
            chki = s[i - 1]
        if not fin:
            istr = i
            while i <= ii:
                c2 = s[istr - 1:i]
                i += 1
                if i > ii:
                    break
                chki = s[i - 1]
    t = numid[:8].replace(" ", "")
    idnum = int(t) if t else 0
    return c1.rstrip(" "), idnum, c2.rstrip(" ")


def locate(parray, lvlblw, lvlabv, value):
    """LOCATE (iblval.f): índice del nivel inmediatamente inferior (búsqueda binaria)."""
    jl = lvlblw - 1
    ju = lvlabv + 1
    while ju - jl > 1:
        jm = (ju + jl) // 2
        if value >= parray[jm]:
            jl = jm
        else:
            ju = jm
    return min(jl, lvlabv - 1)


def _suma_sse2(t):
    """Suma de una reducción tal como la vectoriza el exe (2 carriles SSE2): términos impares y pares
    por separado, los dos carriles juntos y el término sobrante al final. Importa en el centroide de
    AREAPOLY, que con coordenadas UTM está muy mal condicionado (lo nota la distancia de TTRM)."""
    m = len(t) // 2 * 2
    a = b = 0.0
    for j in range(0, m, 2):
        a = a + t[j]
        b = b + t[j + 1]
    s = a + b
    for j in range(m, len(t)):
        s = s + t[j]
    return s


def srcqa(e):
    """SRCQA: control de calidad de las fuentes al terminar la vía SO."""
    m = "SRCQA"
    w = e.IWRK2
    for i in range(1, e.NUMSRC + 1):
        if w[i, 1] > 0 or w[i, 2] > 0 or w[i, 11] > 0 or w[i, 12] > 0 or w[i, 13] > 0:
            for col, cod in ((1, "236"), (2, "237"), (11, "241"), (12, "246"), (13, "247")):
                if w[i, col] < e.NSEC:
                    e.errhdl(e.PATH, m, "E", cod, e.SRCID[i])
        if e.OSPLAT[i] and w[i, 1] > 0:
            e.errhdl(e.PATH, m, "E", "633", e.SRCID[i])
        q = e.QFLAG[i]
        if q:
            if q in _IQMAX:
                if w[i, 4] < _IQMAX[q]:
                    e.errhdl(e.PATH, m, "E", "239", e.SRCID[i])
            elif q == "HOURLY":
                # lee el primer registro para fijar L_HRLYSIG (ILINE = 1); el contador IQLINE se
                # incrementa en las fuentes que comparten fichero con ISRC (la última definida),
                # no con I, como en el original
                ilsave = e.ILINE
                u = e.HOUREMISARRAY[e.ISRC]
                for jj in range(1, e.NSRC + 1):
                    if e.HOUREMISARRAY[jj] == u:
                        e.IQLINE[jj] += 1
                e.ILINE = 1
                e.KURDAT = 0
                if e.AFTSRC[i] == "Y":
                    raise NoTraducido("fuentes de aeronaves")
                emisiones.hrqread(e, i)
                e.ILINE = ilsave
        if w[i, 5] != 0 or w[i, 6] != 0 or w[i, 7] != 0:
            # número de categorías de tamaño de partícula de la fuente
            e.INPD[i] = w[i, 5]
            if w[i, 5] != w[i, 6] or w[i, 5] != w[i, 7]:
                e.errhdl(e.PATH, m, "E", "240", e.SRCID[i])
            atot = 0.0
            n = int(e.INPD[i])
            if n <= e.NPDMAX:
                for j in range(1, n + 1):
                    atot = atot + e.APHI[j, i]
                if atot < 0.98 or atot > 1.02:
                    e.errhdl(e.PATH, m, "W", "330", e.SRCID[i])
            else:
                e.DUMMY = fwrite("('NPD= ',I7)", e.NPDMAX)[0]
                e.errhdl(e.PATH, m, "E", "290", e.DUMMY)
        if e.INPD[i] == 0:
            if (e.DEPOS or e.DDEP or e.WDEP or e.DDPLETE or e.WDPLETE) and not e.LUSERVD and e.SOGAS[i] == "N":
                e.errhdl(e.PATH, m, "E", "242", e.SRCID[i])
        elif e.INPD[i] > 0 and e.SOGAS[i] == "Y":
            e.errhdl(e.PATH, m, "E", "289", e.SRCID[i])
        if e.SRCTYP[i] == "AREAPOLY":
            nv = int(e.NVERTS[i])
            if w[i, 10] < nv:
                e.errhdl(e.PATH, m, "E", "265", e.SRCID[i])
            else:
                xv, yv = e.AXVERT, e.AYVERT
                xv[nv + 1, i] = xv[1, i]
                yv[nv + 1, i] = yv[1, i]
                cs = [xv[j, i] * yv[j + 1, i] - xv[j + 1, i] * yv[j, i] for j in range(1, nv + 1)]
                area = 0.5 * _suma_sse2(cs)
                e.AXINIT[i] = math.sqrt(abs(area))
                e.AYINIT[i] = math.sqrt(abs(area))
                sumx = _suma_sse2([(xv[j, i] + xv[j + 1, i]) * cs[j - 1] for j in range(1, nv + 1)])
                sumy = _suma_sse2([(yv[j, i] + yv[j + 1, i]) * cs[j - 1] for j in range(1, nv + 1)])
                if abs(area) < 0.0001:
                    e.errhdl(e.PATH, m, "E", "266", e.SRCID[i])
                    e.AXCNTR[i] = 0.0
                    e.AYCNTR[i] = 0.0
                else:
                    e.AXCNTR[i] = sumx / (6.0 * area)
                    e.AYCNTR[i] = sumy / (6.0 * area)
        if e.URBSRC[i] == "Y":
            e.NURBSRC += 1
        if e.AFTSRC[i] == "Y":
            e.NAFTSRC += 1
        t = e.SRCTYP[i]
        if t == "POINTCAP":
            e.NUMCAP += 1
        elif t == "POINTHOR":
            e.NUMHOR += 1
        if t[:5] == "POINT":
            e.NUMPNT += 1
        elif t == "VOLUME":
            e.NUMVOL += 1
        elif t[:4] == "AREA":
            e.NUMAREA += 1
        elif t == "LINE":
            e.NUMLINE += 1
        elif t == "OPENPIT":
            e.NUMPIT += 1
        elif t == "SWPOINT":
            e.NUMSWP += 1
        e.NDXSTK[i] = locate(e.GRIDHT, 1, 29, e.AHS[i])
    if e.L_AREAMNDR and e.NUMAREA == 0:
        e.errhdl(e.PATH, "RLINE", "W", "668", "AREAMNDR")
    for i in range(1, e.NUMSRC + 1):
        u = int(e.HOUREMISARRAY[i])
        if e.HOURLY and u > 0 and u in e.U:
            e.U[u].rewind()
            e.IQLINE[:] = 0
    if e.PSDCREDIT:
        entrada_no2.srcqa_psd(e, m)
    else:
        numback = 0
        for j in range(1, e.NUMGRP + 1):
            itot = int((e.IGROUP[1:e.NUMSRC + 1, j] == 1).sum())
            if e.GRP_BACK[j]:
                numback += 1
            if itot == 0 and not e.GRP_BACK[j]:
                e.errhdl(e.PATH, m, "W", "319", e.GRPID[j])
        if e.L_BACKGRND and numback == 0:
            e.errhdl(e.PATH, m, "W", "321", " ")
        for i in range(1, e.NUMSRC + 1):
            itot = int((e.IGROUP[i, 1:e.NUMGRP + 1] == 1).sum())
            if itot == 0:
                e.errhdl(e.PATH, m, "W", "316", e.SRCID[i])
    if e.HBPLUME and e.NHBP == 0:
        e.errhdl(e.PATH, m, "E", "130", "HBPSRCID")
    if e.URBAN and e.NURBSRC == 0:
        e.errhdl(e.PATH, m, "E", "130", "URBANSRC")
    if e.ARCFT and e.NAFTSRC == 0:
        e.errhdl(e.PATH, m, "E", "822", "ARCFTSRC")
    for i in range(1, e.NUMSRC + 1):
        if e.NUMURB > 0 and int((e.IURBGRP[i, 1:e.NUMURB + 1] == 1).sum()) > 1:
            e.errhdl(e.PATH, m, "E", "302", e.SRCID[i])
    fuente_linea_flotante.srcqa_bl(e, m)
    entrada_no2.srcqa_no2(e, m)
    fuente_linea_flotante.srcqa_depos_bl(e, m)
    if e.SCREEN:
        for n, txt in ((e.NBLTOTAL, "BUOYLINE"), (e.NRLINES, "RLINE/RLINEXT"), (e.NSWP, "SWPOINT"),
                       (e.NAREA, "AREA"), (e.NPOLY, "AREAPOLY"), (e.NCIRC, "AREACIRC"),
                       (e.NPIT, "OPENPIT"), (e.NLINE, "LINE")):
            if n > 0:
                e.errhdl(e.PATH, m, "W", "731", txt)
    entrada_no2.srcqa_no2_final(e, m)
    if e.L_BACKGRND:
        _qa_fondo(e, m)


def _qa_fondo(e, m):
    """Final de SRCQA: valores de fondo completos por sector y unidades por defecto."""
    def n_vals(i):
        if e.IBKGRD[i] < 100:
            return fwrite("('BGSECT',I1,' N=',I2)", i, e.IBKGRD[i])[0]
        return fwrite("('SECT',I1,' N=',I4)", i, e.IBKGRD[i])[0]

    if e.L_BGSECTOR:
        for i in range(1, e.NUMBGSECTS + 1):
            if not e.L_BGFILE[i] or e.BKGRND_FILE[i] == "":
                if not e.L_BGVALUES[i]:
                    e.errhdl(e.PATH, m, "E", "238", fwrite("('No BG SECT',I1,'!')", i)[0])
                elif e.IBKGRD[i] < e.IBGMAX[i]:
                    e.errhdl(e.PATH, m, "E", "238", n_vals(i))
                elif e.L_BGFILE[i]:
                    e.errhdl(e.PATH, m, "W", "248", fwrite("('BGFILE SECT',I1)", i)[0])
            else:
                if not e.L_BGVALUES[i]:
                    e.errhdl(e.PATH, m, "W", "248", fwrite("('BGVALs SECT',I1)", i)[0])
                elif e.IBKGRD[i] < e.IBGMAX[i]:
                    e.errhdl(e.PATH, m, "E", "238", n_vals(i))
    else:
        i = 1
        num = fwrite("('NumVals=',I4)", e.IBKGRD[i])[0]
        if not e.L_BGFILE[i] or e.BKGRND_FILE[i] == "":
            if not e.L_BGVALUES[i]:
                e.errhdl(e.PATH, m, "E", "238", "No BGVALUES!")
            elif e.IBKGRD[i] < e.IBGMAX[i]:
                e.errhdl(e.PATH, m, "E", "238", num)
        else:
            if not e.L_BGVALUES[i]:
                e.errhdl(e.PATH, m, "W", "248", "BGVALs Msg")
            elif e.IBKGRD[i] < e.IBGMAX[i]:
                e.errhdl(e.PATH, m, "E", "238", num)
    if e.ISSTAT[41] != 1:
        if e.POLLUT in ("NO2", "SO2"):
            e.BACKUNITS = "PPB"
        elif e.POLLUT == "CO":
            e.BACKUNITS = "PPM"
        else:
            e.BACKUNITS = "UG/M3"
