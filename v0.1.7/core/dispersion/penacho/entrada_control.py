# -*- coding: utf-8 -*-
"""Traducción de AERMOD 26135 (US EPA, dominio público): vía CO (coset.f).

COCARD y las claves del alcance: TITLEONE/TWO, MODELOPT, AVERTIME, POLLUTID, HALFLIFE, DCAYCOEF,
FLAGPOLE, RUNORNOT, ERRORFIL, las de la deposición de gases (GDSEASON, GASDEPDF, GDLANUSE,
GASDEPVD) y las de la química del NO2 (en entrada_no2.py), con todas las comprobaciones de FINISHED que
pueden darse con ellas. Las claves fuera de alcance (EVENT, SAVEFILE...) paran con NoTraducido."""
from . import entrada_no2
from .control import dbl, i8, num
from .estado import ILEN_FLD, NoTraducido
from .formato import fc, fwrite, nint, stonum

_FUERA = {"EVENTFIL": "EVENTFIL",
          "LOW_WIND": "LOW_WIND", "AWMADWNW": "AWMADWNW", "ORD_DWNW": "ORD_DWNW",
          "ARCFTOPT": "fuentes de aeronaves"}

_UNICAS = {"TITLEONE": 2, "TITLETWO": 3, "MODELOPT": 4, "AVERTIME": 5, "POLLUTID": 6, "FLAGPOLE": 11,
           "RUNORNOT": 12, "ERRORFIL": 17}


def cocard(e):
    """COCARD: claves de la vía CO."""
    m = "COCARD"
    k = e.KEYWRD
    if k == "STARTING":
        e.IURB = 0
        e.ISTART = True
        e.ICSTAT[1] += 1
        if e.ICSTAT[1] != 1:
            e.errhdl(e.PATH, m, "E", "135", k)
    elif k in _UNICAS:
        n = _UNICAS[k]
        e.ICSTAT[n] += 1
        if e.ICSTAT[n] != 1:
            e.errhdl(e.PATH, m, "E", "135", k)
        elif k in ("TITLEONE", "TITLETWO"):
            titles(e)
        elif k == "MODELOPT":
            modopt(e)
        elif k == "AVERTIME":
            avetim(e)
        elif k == "POLLUTID":
            pollid(e)
        elif k == "FLAGPOLE":
            flagdf(e)
        elif k == "RUNORNOT":
            runnot(e)
        elif k == "ERRORFIL":
            errfil(e)
    elif k in ("HALFLIFE", "DCAYCOEF"):
        if k == "HALFLIFE":
            if e.ICSTAT[8] != 0:
                e.errhdl(e.PATH, m, "W", "155", k)
                return
            e.ICSTAT[7] += 1
            if e.ICSTAT[7] != 1:
                e.errhdl(e.PATH, m, "E", "135", k)
                return
        else:
            if e.ICSTAT[7] != 0:
                e.errhdl(e.PATH, m, "W", "155", k)
                return
            e.ICSTAT[8] += 1
            if e.ICSTAT[8] != 1:
                e.errhdl(e.PATH, m, "E", "135", k)
                return
        if e.ICSTAT[4] != 1:
            e.errhdl(e.PATH, m, "E", "140", k)
        elif e.ICSTAT[6] != 1:
            e.errhdl(e.PATH, m, "E", "140", k)
        edecay(e)
    elif k == "URBANOPT":
        e.ICSTAT[23] += 1
        if e.ICSTAT[4] != 1:
            e.errhdl(e.PATH, m, "E", "140", k)
        urbopt(e)
    elif k in _DEPOS_CO:
        n, rutina = _DEPOS_CO[k]
        e.ICSTAT[n] += 1
        if e.ICSTAT[n] != 1:
            e.errhdl(e.PATH, m, "E", "135", k)
        else:
            rutina(e)
    elif entrada_no2.cocard(e, k):
        pass
    elif k == "DEBUGOPT":
        from . import depura
        e.ICSTAT[22] += 1
        e.CURRENT_DEBUGOPT += 1
        depura.debopt(e)
    elif not e.EVONLY and k in ("SAVEFILE", "INITFILE", "MULTYEAR"):
        n = {"SAVEFILE": 14, "INITFILE": 15, "MULTYEAR": 16}[k]
        e.ICSTAT[n] += 1
        if e.ICSTAT[n] != 1:
            e.errhdl(e.PATH, m, "E", "135", k)
        elif k == "SAVEFILE":
            savefl(e)
        elif k == "INITFILE":
            initfl(e)
        else:
            myear(e)
    elif k in _FUERA and not (e.EVONLY and k in ("EVENTFIL", "SAVEFILE", "INITFILE", "MULTYEAR")):
        raise NoTraducido("CO " + k + " (" + _FUERA[k] + ")")
    elif k == "FINISHED":
        _finished(e)
    else:
        e.errhdl(e.PATH, m, "E", "110", k)


def urbopt(e):
    """URBOPT: tarjeta URBANOPT (población, nombre y rugosidad de cada zona urbana)."""
    m = "URBOPT"
    multi = e.L_MULTURB
    if (not multi and e.IFC < 3) or (multi and e.IFC < 4):
        e.errhdl(e.PATH, m, "E", "200", e.KEYWRD)
        return
    if (not multi and e.IFC > 5) or (multi and e.IFC > 6):
        e.errhdl(e.PATH, m, "E", "202", e.KEYWRD)
        return
    if not e.L_URBAN_ALL and multi:
        if e.LOCE[3] - e.LOCB[3] > 7:
            e.errhdl(e.PATH, m, "E", "219", e.FIELD[e.ISC][:12])
            e.RECERR = True
            return
        tempid = fc(e.FIELD[3], 8)
        for i in range(1, e.NUMURB + 1):
            if tempid == e.URBID[i]:
                e.errhdl(e.PATH, m, "E", "303", tempid)
                return
        e.IURB += 1
        if e.IURB > e.NURB:
            e.errhdl(e.PATH, m, "E", "290", fwrite("('NURB=',I7)", e.NURB)[0])
            return
        e.NUMURB += 1
        e.URBID[e.IURB] = tempid
        k0 = 4
    elif e.L_URBAN_ALL and multi:
        e.errhdl(e.PATH, m, "E", "279", "URBANSRC ALL")
        e.URBAN = True
        return
    else:
        e.IURB = 1
        k0 = 3
    iu = e.IURB
    if e.IFC >= k0:
        e.URBPOP[iu], imit = dbl(e, k0, e.URBPOP[iu])
        if imit != 1:
            e.errhdl(e.PATH, m, "E", "208", "URB-POP")
        elif e.URBPOP[iu] < 100.0:
            e.errhdl(e.PATH, m, "E", "203", "URB-POP")
        elif e.URBPOP[iu] < 21206.0:
            e.errhdl(e.PATH, m, "W", "320", "URB-POP")
    if e.IFC >= k0 + 1:
        e.URBNAM[iu] = e.FIELD[k0 + 1]
    if e.IFC == k0 + 2:
        e.URBZ0[iu], imit = dbl(e, k0 + 2, e.URBZ0[iu])
        if imit != 1:
            e.errhdl(e.PATH, m, "E", "208", "URBAN_Z0")
        else:
            z0 = e.URBZ0[iu]
            if e.DFAULT and z0 != 1.0:
                e.errhdl(e.PATH, m, "W", "206", "URBAN_Z0")
                e.URBZ0[iu] = 1.0
            elif not e.DFAULT and z0 != 1.0:
                e.L_NONDFAULT = True
            z0 = e.URBZ0[iu]
            if z0 < 0.80 or 1.50 < z0 < 5.0:
                e.errhdl(e.PATH, m, "W", "353", fwrite("(F8.2)", z0)[0])
            elif z0 >= 5.0:
                e.errhdl(e.PATH, m, "E", "380", "URBAN Z0")
    else:
        e.URBZ0[iu] = 1.0
    if not multi:
        e.NUMURB = 1
    e.URBAN = True


# ------------------------------------------------------------- deposición de gases (vía CO)
def gddef(e):
    """GDDEF: parámetros por defecto de la deposición seca de gases (GASDEPDF): reactividad Fo,
    fracción del LAI verde máximo de las categorías estacionales 2 y 5 y especie de referencia."""
    m = "GDDEF"
    if e.IFC <= 2:
        e.errhdl(e.PATH, m, "E", "200", e.KEYWRD)
        return
    elif e.IFC < 5:
        e.errhdl(e.PATH, m, "E", "201", e.KEYWRD)
        return
    elif e.IFC > 6:
        e.errhdl(e.PATH, m, "E", "202", e.KEYWRD)
        return
    for k, nom in ((3, "FO"), (4, "FSEAS2"), (5, "FSEAS5")):
        e.DNUM, imit = dbl(e, k, e.DNUM)
        e.IMIT = imit
        if imit != 1:
            e.errhdl(e.PATH, m, "E", "208", e.KEYWRD)
            return
        setattr(e, nom, e.DNUM)
    e.REFSPE = fc(e.FIELD[6], 40) if e.IFC == 6 else ""


def _indices_gd(e, m, nmax, imax, destino):
    """Lista de índices enteros (STONUM, con repetición n*valor) de GDSEASON/GDLANUSE."""
    e.ISET = 0
    for i in range(3, e.IFC + 1):
        e.FNUM, imit = num(e, i, e.FNUM)
        e.IMIT = imit
        if imit == -1:
            e.errhdl(e.PATH, m, "E", "208", e.KEYWRD)
            continue
        for _j in range(imit):
            e.ISET += 1
            if e.ISET <= nmax:
                n = nint(e.FNUM)
                if 1 <= n <= imax:
                    destino[e.ISET] = n
                else:
                    e.errhdl(e.PATH, m, "E", "380", e.KEYWRD)
            else:
                e.errhdl(e.PATH, m, "E", "234", e.KEYWRD)


def gdseas(e):
    """GDSEAS: categoría estacional de Wesely (1-5) de cada mes (GDSEASON)."""
    m = "GDSEAS"
    if e.IFC <= 2:
        e.errhdl(e.PATH, m, "E", "200", e.KEYWRD)
        return
    elif e.IFC < 3:
        e.errhdl(e.PATH, m, "E", "201", e.KEYWRD)
        return
    elif e.IFC > 14:
        e.errhdl(e.PATH, m, "E", "202", e.KEYWRD)
        return
    _indices_gd(e, m, 12, 5, e.ISEAS_GD)


def gvsubd(e):
    """GVSUBD: velocidad de deposición seca de gases dada por el usuario (GASDEPVD)."""
    m = "GVSUBD"
    if e.IFC <= 2:
        e.errhdl(e.PATH, m, "E", "200", e.KEYWRD)
        return
    elif e.IFC < 3:
        e.errhdl(e.PATH, m, "E", "201", e.KEYWRD)
        return
    elif e.IFC > 3:
        e.errhdl(e.PATH, m, "E", "202", e.KEYWRD)
        return
    e.DNUM, imit = dbl(e, 3, e.DNUM)
    e.IMIT = imit
    if imit != 1:
        e.errhdl(e.PATH, m, "E", "208", e.KEYWRD)
        return
    e.USERVD = e.DNUM
    if e.USERVD < 0.0:
        e.errhdl(e.PATH, m, "E", "209", " USERVD ")
    elif e.USERVD == 0.0:
        e.errhdl(e.PATH, m, "E", "380", "USERVD=0")
    elif e.USERVD > 0.05:
        e.errhdl(e.PATH, m, "W", "320", " USERVD ")
    e.LUSERVD = True


def gdland(e):
    """GDLAND: categoría de uso del suelo (1-9) de cada sector de 10 grados (GDLANUSE)."""
    m = "GDLAND"
    if e.IFC <= 2:
        e.errhdl(e.PATH, m, "E", "200", e.KEYWRD)
        return
    elif e.IFC < 3:
        e.errhdl(e.PATH, m, "E", "201", e.KEYWRD)
        return
    elif e.IFC > 38:
        e.errhdl(e.PATH, m, "E", "202", e.KEYWRD)
        return
    _indices_gd(e, m, 36, 9, e.ILAND_GD)


_DEPOS_CO = {"GDSEASON": (18, gdseas), "GASDEPDF": (19, gddef), "GDLANUSE": (20, gdland),
             "GASDEPVD": (21, gvsubd)}


def _finished(e):
    m = "COCARD"
    e.IFINIS = True
    e.ICSTAT[50] += 1
    if e.ICSTAT[50] != 1:
        e.errhdl(e.PATH, m, "E", "135", e.KEYWRD)
        return
    for n, nom in ((1, "STARTING"), (2, "TITLEONE"), (4, "MODELOPT"), (5, "AVERTIME"), (6, "POLLUTID"),
                   (12, "RUNORNOT")):
        if e.ICSTAT[n] == 0:
            e.errhdl(e.PATH, m, "E", "130", nom)
    entrada_no2.finished_ozono(e, m)
    if not _abrir_reinicio(e):
        return
    if e.SCREEN:
        if e.NUMAVE > 1:
            e.errhdl(e.PATH, m, "E", "295", " 1h Only")
        elif e.KAVE[1] != 1:
            e.errhdl(e.PATH, m, "E", "295", " 1h Only")
        if e.PERIOD:
            e.errhdl(e.PATH, m, "E", "295", " 1h Only")
    # opciones no reglamentarias de la deposición de gases (requieren ALPHA)
    for n, nom in ((18, "GDSEASON"), (19, "GASDEPDF"), (20, "GDLANUSE"), (21, "GASDEPVD")):
        if e.DFAULT and e.ICSTAT[n] > 0:
            e.errhdl(e.PATH, m, "E", "196", nom)
        elif not e.L_ALPHA and e.ICSTAT[n] > 0:
            e.errhdl(e.PATH, m, "E", "198", nom)
        elif e.ICSTAT[n] > 0:
            e.L_NONDFAULT = True
    if e.LUSERVD and (e.DEPOS or e.WDEP or e.WDPLETE):
        e.errhdl(e.PATH, m, "E", "243", "GASDEPVD")
    for n, nom in ((18, "GDSEASON"), (19, "GASDEPDF"), (20, "GDLANUSE")):
        if e.LUSERVD and e.ICSTAT[n] > 0:
            e.errhdl(e.PATH, m, "E", "195", nom)
    e.MODOPS[1] = "RegDFAULT" if e.DFAULT else ("NonDFAULT" if e.L_NONDFAULT else "")
    if e.CONC:
        e.MODOPS[2] = "CONC"
    if e.DEPOS:
        e.MODOPS[3] = "DEPOS"
    if e.DDEP:
        e.MODOPS[4] = "DDEP"
    if e.WDEP:
        e.MODOPS[5] = "WDEP"
    if e.FLATSRCS:
        e.MODOPS[6] = "FLAT and"
        e.MODOPS[7] = "ELEV"
    elif e.FLAT:
        e.MODOPS[6] = "FLAT"
    else:
        e.MODOPS[7] = "ELEV"
    if e.FLGPOL:
        e.MODOPS[8] = "FLGPOL"
    if e.NOSTD:
        e.MODOPS[9] = "NOSTD"
    if e.NOCHKD:
        e.MODOPS[10] = "NOCHKD"
    elif e.L_WARNCHKD:
        e.MODOPS[10] = "WARNCHKD"
    if e.FASTALL:
        e.MODOPS[11] = "FASTALL"
    elif e.FASTAREA:
        e.MODOPS[11] = "FASTAREA"
    elif e.NOWARN:
        e.MODOPS[11] = "NOWARN"
    if e.SCREEN:
        e.MODOPS[12] = "SCREEN"
    if e.MULTYR:
        e.MODOPS[13] = "MULTYR"
    if e.ARDPLETE:
        e.MODOPS[14] = "AREADPLT"
    elif e.ROMBERG:
        e.MODOPS[14] = "ROMBERG"
    elif e.DDPLETE:
        e.MODOPS[14] = "DRYDPLT"
    else:
        e.MODOPS[14] = "NODRYDPLT"
    e.MODOPS[15] = "WETDPLT" if e.WDPLETE else "NOWETDPLT"
    if e.SCIM:
        e.MODOPS[16] = "SCIM"
    if e.RUNTTRM2:
        if e.PVMRM:
            e.MODOPS[17] = "TTRM2_PVMRM"
        elif e.OLM:
            e.MODOPS[17] = "TTRM2_OLM"
        elif e.ARM2:
            e.MODOPS[17] = "TTRM2_ARM2"
    elif e.PVMRM:
        e.MODOPS[17] = "PVMRM"
    elif e.OLM:
        e.MODOPS[17] = "OLM"
    elif e.ARM2:
        e.MODOPS[17] = "ARM2"
    elif e.GRSM:
        e.MODOPS[17] = "GRSM"
    elif e.RUNTTRM:
        e.MODOPS[17] = "TTRM"
    if e.PSDCREDIT:
        e.MODOPS[18] = "PSDCREDIT"
    if not e.DFAULT and e.BETA and e.L_ALPHA:
        e.MODOPS[19] = "ALPHA  BETA"
    elif not e.DFAULT and e.L_ALPHA:
        e.MODOPS[19] = "ALPHA"
    elif not e.DFAULT and e.BETA:
        e.MODOPS[19] = "BETA"
    elif e.DFAULT and e.BETA:
        e.errhdl(e.PATH, m, "E", "204", "BETA")
    elif e.DFAULT and e.L_ALPHA:
        e.errhdl(e.PATH, m, "E", "204", "ALPHA")
    if e.NURBSRC == 0:
        e.MODOPS[20] = "RURAL"
    elif e.NURBSRC == e.NSRC:
        e.MODOPS[20] = "URBAN"
    else:
        e.MODOPS[20] = "Urb&Rur"
    if not e.L_URBANTRANSITION:
        e.MODOPS[21] = "NoUrbTran"
    if e.L_VECTORWS:
        e.MODOPS[23] = "VectorWS"
    if e.NOMINO3:
        e.MODOPS[28] = "NoMinO3"
    if e.NAFTSRC == e.NSRC or e.NAFTSRC > 0:
        e.MODOPS[24] = "AIRCRAFT"
        if not e.L_ALPHA:
            e.errhdl(e.PATH, m, "E", "198", "ARCFTOPT")
        if e.DFAULT:
            e.errhdl(e.PATH, m, "E", "204", "ARCFTOPT")
    if e.HBPLUME:
        e.MODOPS[29] = "HBP"
    if e.SCIM and e.NUMAVE > 0:
        e.errhdl(e.PATH, m, "E", "154", "ST AVES")
    if e.SCIM and e.PERIOD:
        e.errhdl(e.PATH, m, "E", "154", "PERIOD")
    if e.SCIM and e.DEPOS:
        e.DEPOS = False
        e.NUMTYP -= 1
        e.errhdl(e.PATH, m, "W", "156", " DEPOS ")
    if e.ANNUAL:
        for ityp in range(1, e.NUMTYP + 1):
            if not e.CONC or ityp > 1:
                e.PERLBL[ityp] = "GRAMS/M**2/YR"
    entrada_no2.finished_completos(e, m)
    if e.ICSTAT[27] != 1:
        e.OZONEUNITS = "PPB"
    if e.ICSTAT[38] != 1:
        e.NOXUNITS = "PPB"
    p = e.POLLUT
    nave, kave = e.NUMAVE, e.KAVE
    if p in ("PM25", "PM-2.5", "PM-25", "PM2.5"):
        if not e.L_NO_PM25AVE and not e.NOCHKD and not e.L_WARNCHKD and not e.EVONLY:
            e.PM25AVE = True
            if nave > 1 or (nave == 1 and kave[1] != 24):
                for i in range(1, nave + 1):
                    if kave[i] != 24:
                        e.DUMMY = fwrite("(I3,'-hr Ave')", int(kave[i]))[0]
                        e.errhdl(e.PATH, m, "E", "363", e.DUMMY)
                e.PM25AVE = False
            if e.PERIOD:
                e.errhdl(e.PATH, m, "E", "363", "PERIOD Ave")
                e.PM25AVE = False
        elif not e.SCREEN and not e.EVONLY:
            if e.NOCHKD:
                e.DUMMY = "NOCHKD"
            elif e.L_WARNCHKD:
                e.DUMMY = "WARNCHKD"
            e.errhdl(e.PATH, m, "W", "363", e.DUMMY)
            e.PM25AVE = False
        elif e.SCREEN or e.EVONLY or e.L_NO_PM25AVE:
            e.PM25AVE = False
    for gas, lno, attr in (("NO2", e.L_NO_NO2AVE, "NO2AVE"), ("SO2", e.L_NO_SO2AVE, "SO2AVE")):
        if p != gas:
            continue
        if not lno and not e.NOCHKD and not e.L_WARNCHKD and (gas == "SO2" or not e.SCREEN) and not e.EVONLY:
            per_ann = e.PERIOD or e.ANNUAL
            if gas == "NO2":
                c4 = nave > 1 or (nave == 1 and kave[1] != 1) and per_ann and not e.MULTYR
                c5 = nave > 1 or (nave == 1 and kave[1] != 1)
            else:
                mink = int(kave[1:nave + 1].min()) if nave > 0 else 0
                c4 = nave > 1 and mink == 1 and per_ann and not e.MULTYR
                c5 = nave > 1 and mink == 1
            if nave == 1 and kave[1] == 1 and not e.PERIOD and not e.ANNUAL:
                setattr(e, attr, True)
            elif nave == 1 and kave[1] == 1 and e.PERIOD and e.MULTYR:
                setattr(e, attr, True)
            elif nave == 1 and kave[1] == 1 and per_ann and not e.MULTYR:
                e.errhdl(e.PATH, m, "W", "361", "MULTYEAR Opt")
                setattr(e, attr, True)
            elif c4:
                e.errhdl(e.PATH, m, "W", "361", "MULTYEAR Opt")
                for i in range(1, nave + 1):
                    if kave[i] != 1:
                        e.DUMMY = fwrite("(I3,'-hr Ave')", int(kave[i]))[0]
                        e.errhdl(e.PATH, m, "W", "362", e.DUMMY)
                setattr(e, attr, False)
            elif c5:
                for i in range(1, nave + 1):
                    if kave[i] != 1:
                        e.DUMMY = fwrite("(I3,'-hr Ave')", int(kave[i]))[0]
                        e.errhdl(e.PATH, m, "W", "362", e.DUMMY)
                setattr(e, attr, False)
            else:
                setattr(e, attr, False)
        elif not e.SCREEN and not e.EVONLY:
            if nave == 1 and kave[1] == 1 and ((not e.PERIOD and not e.ANNUAL) or (e.PERIOD and e.MULTYR)
                                               or ((e.PERIOD or e.ANNUAL) and not e.MULTYR)):
                if gas == "NO2":
                    if e.NOCHKD:
                        e.DUMMY = "NOCHKD"
                        e.errhdl(e.PATH, m, "W", "362", e.DUMMY)
                    elif e.L_WARNCHKD:
                        e.DUMMY = "WARNCHKD"
                        e.errhdl(e.PATH, m, "W", "362", e.DUMMY)
                else:
                    if e.NOCHKD:
                        e.DUMMY = "NOCHKD"
                    elif e.L_WARNCHKD:
                        e.DUMMY = "WARNCHKD"
                    e.errhdl(e.PATH, m, "W", "362", e.DUMMY)
                setattr(e, attr, False)
        elif e.SCREEN or e.EVONLY:
            setattr(e, attr, False)
    if (e.PVMRM or e.OLM or e.ARM2 or e.GRSM) and p != "NO2":
        e.errhdl(e.PATH, m, "E", "284", " NO2 ")
    if e.PM25AVE or e.NO2AVE or e.SO2AVE:
        # la constante del original sigue en una línea de continuación: lleva sus 15 blancos dentro
        e.PLTFRM = "(3(1X,F13.5),3(1X,F8.2),2X,A6,2X,A8,2X,A5,5X,A8,2X," + " " * 15 + "10(F13.5,2X,I8.8,2X:))"
    if e.L_AWMA_UEFF and e.L_ORD_UEFF:
        e.errhdl(e.PATH, m, "E", "124", "  ")
    if e.L_AWMA_UTURB and e.L_AWMA_UTURBHX:
        e.errhdl(e.PATH, m, "W", "478", " ")


def titles(e):
    """TITLES: el título es el resto de la línea tras la clave (con mayúsculas y minúsculas)."""
    ini = int(e.LOCE[2]) + 2
    fin = min(len(e.RUNST1), ini + ILEN_FLD - 1)
    t = fc(e.RUNST1[ini - 1:fin], 200) if fin >= ini else ""
    if e.KEYWRD == "TITLEONE":
        e.TITLE1 = t
    else:
        e.TITLE2 = t
    if t == "":
        e.errhdl(e.PATH, "TITLES", "W", "200", e.KEYWRD)


_CHIDEP_CONC = ("AVER", "AGE ", "CONC", "ENTR", "ATIO", "N   ")
_CHIDEP = {"DEPOS": ("  TO", "TAL ", "DEPO", "SITI", "ON  ", "    "),
           "DDEP": ("    ", "DRY ", "DEPO", "SITI", "ON  ", "    "),
           "WDEP": ("    ", "WET ", "DEPO", "SITI", "ON  ", "    ")}


def _tipo(e, ityp, nombre):
    """Etiquetas de un tipo de salida (CONC, DEPOS, DDEP, WDEP)."""
    ch = _CHIDEP_CONC if nombre == "CONC" else _CHIDEP[nombre]
    for j in range(6):
        e.CHIDEP[j + 1, ityp] = ch[j].rstrip(" ")
    if nombre == "CONC":
        e.EMIFAC[ityp] = 1.0e06
        e.EMILBL[ityp] = "GRAMS/SEC"
        e.OUTLBL[ityp] = "MICROGRAMS/M**3"
        e.PERLBL[ityp] = "MICROGRAMS/M**3"
    else:
        e.EMIFAC[ityp] = 3600.0
        e.EMILBL[ityp] = "GRAMS/SEC"
        e.OUTLBL[ityp] = "GRAMS/M**2"
        e.PERLBL[ityp] = "GRAMS/M**2"
    e.OUTTYP[ityp] = nombre


def modopt(e):
    """MODOPT: opciones del modelo (MODELOPT)."""
    m = "MODOPT"
    f = e.FIELD
    if e.IFC < 3:
        e.errhdl(e.PATH, m, "E", "200", e.KEYWRD)
    elif e.IFC > 14:
        e.errhdl(e.PATH, m, "W", "202", e.KEYWRD)
    e.SVMIN = 0.2
    e.WSMIN = 0.2828
    e.FRANMAX = 1.0
    e.FRANMIN = 0.0
    e.SWMIN = 0.02
    e.BIGT = 24.0
    e.FAC_DISPHT = 5.0
    e.SZCOEF = 2.15
    opts = [f[i][:9].rstrip(" ") for i in range(3, e.IFC + 1)]
    for kopt in opts:
        if kopt in ("DFAULT", "DEFAULT"):
            e.DFAULT = True
            e.ELEV = True
            for n in ("FLAT", "FLATSRCS", "NOSTD", "NOCHKD", "SCREEN", "SCIM", "PSDCREDIT", "BETA",
                      "L_ALPHA", "FASTAREA", "FASTALL", "L_EFFSIGY", "LOW_WIND", "L_NONDFAULT", "GRSM",
                      "NOMINO3", "L_AREAMNDR"):
                setattr(e, n, False)
            e.MSGPRO = True
            e.L_URBANTRANSITION = True
            break
    if not e.DFAULT:
        for kopt in opts:
            if kopt == "FLAT":
                e.FLAT = True
                e.ELEV = False
                break
        if e.FLAT:
            for kopt in opts:
                if kopt == "ELEV":
                    e.ELEV = True
                    e.FLATSRCS = True
                    break
    else:
        for kopt in opts:
            if kopt == "FLAT":
                e.errhdl(e.PATH, m, "W", "206", kopt)
    for kopt in opts:
        if kopt == "BETA" and not e.DFAULT:
            e.BETA = True
        elif kopt == "ALPHA" and not e.DFAULT:
            e.L_ALPHA = True
    e.NUMTYP = 0
    for kopt in opts:
        if kopt in ("DFAULT", "DEFAULT"):
            e.DFAULT = True
        elif kopt in ("CONC", "DEPOS", "DDEP", "WDEP"):
            if not getattr(e, kopt):
                setattr(e, kopt, True)
                e.NUMTYP += 1
        elif kopt in ("FLAT", "ELEV"):
            continue
        elif kopt == "DRYDPLT" and not e.NODRYDPLT:
            e.DDPLETE = True
            e.DRYDPLT = True
        elif kopt == "DRYDPLT" and e.NODRYDPLT:
            e.errhdl(e.PATH, m, "E", "149", kopt)
        elif kopt == "NODRYDPLT" and not e.DRYDPLT:
            e.DDPLETE = False
            e.NODRYDPLT = True
        elif kopt == "NODRYDPLT" and e.DRYDPLT:
            e.errhdl(e.PATH, m, "E", "149", kopt)
        elif kopt == "ROMBERG":
            e.ROMBERG = True
            e.DDPLETE = True
        elif kopt == "AREADPLT":
            if not e.DFAULT:
                e.ARDPLETE = True
                e.DDPLETE = True
            else:
                e.errhdl(e.PATH, m, "E", "204", kopt)
        elif kopt == "WETDPLT" and not e.NOWETDPLT:
            e.WDPLETE = True
            e.WETDPLT = True
        elif kopt == "WETDPLT" and e.NOWETDPLT:
            e.errhdl(e.PATH, m, "E", "149", kopt)
        elif kopt == "NOWETDPLT" and not e.WETDPLT:
            e.WDPLETE = False
            e.NOWETDPLT = True
        elif kopt == "NOWETDPLT" and e.WETDPLT:
            e.errhdl(e.PATH, m, "E", "149", kopt)
        elif kopt == "NOSTD":
            if not e.DFAULT:
                e.NOSTD = True
            else:
                e.errhdl(e.PATH, m, "W", "206", kopt)
                e.NOSTD = False
        elif kopt == "NOWARN":
            e.NOWARN = True
        elif kopt == "NOCHKD":
            if not e.DFAULT and not e.L_WARNCHKD:
                e.NOCHKD = True
            elif not e.DFAULT and e.L_WARNCHKD:
                e.errhdl(e.PATH, m, "E", "149", kopt)
            else:
                e.errhdl(e.PATH, m, "W", "206", kopt)
                e.NOCHKD = False
        elif kopt == "WARNCHKD":
            if not e.NOCHKD:
                e.L_WARNCHKD = True
            else:
                e.errhdl(e.PATH, m, "E", "149", kopt)
        elif kopt == "SCREEN":
            if not e.DFAULT:
                e.SCREEN = True
                e.NOCHKD = True
            else:
                e.errhdl(e.PATH, m, "W", "206", kopt)
                e.SCREEN = False
        elif kopt == "SCIM":
            if not e.DFAULT:
                e.SCIM = True
            else:
                e.errhdl(e.PATH, m, "E", "204", kopt)
                e.SCIM = False
        elif kopt == "TOXICS":
            if e.NAREA > 0 or e.NLINE > 0 or e.NPIT > 0:
                e.errhdl(e.PATH, m, "W", "198", "FASTAREA")
            else:
                e.errhdl(e.PATH, m, "W", "198", "        ")
            if not e.DFAULT:
                if e.NAREA > 0 or e.NLINE > 0 or e.NPIT > 0:
                    e.FASTAREA = True
            else:
                e.errhdl(e.PATH, m, "E", "204", kopt)
        elif kopt == "HBP":
            e.HBPLUME = True
            if not e.L_ALPHA:
                e.errhdl(e.PATH, m, "E", "198", kopt)
            if e.DFAULT:
                e.errhdl(e.PATH, m, "E", "204", kopt)
        elif kopt == "PVMRM":
            e.PVMRM = True
        elif kopt == "OLM":
            e.OLM = True
        elif kopt == "TTRM":
            e.RUNTTRM = True
            if not e.L_ALPHA:
                e.errhdl(e.PATH, m, "E", "198", kopt)
        elif kopt == "TTRM2":
            e.RUNTTRM2 = True
            e.RUNTTRM = True
            if not e.L_ALPHA:
                e.errhdl(e.PATH, m, "E", "198", kopt)
            if e.DFAULT:
                e.errhdl(e.PATH, m, "E", "204", kopt)
        elif kopt == "ARM2":
            e.ARM2 = True
            if e.DFAULT:
                e.ARM2_MIN = 0.50
                e.ARM2_MAX = 0.90
        elif kopt == "GRSM":
            e.GRSM = True
        elif kopt == "PSDCREDIT":
            if e.L_ALPHA and not e.DFAULT:
                e.PSDCREDIT = True
            elif not e.L_ALPHA and not e.DFAULT:
                e.errhdl(e.PATH, m, "E", "198", kopt)
            else:
                e.errhdl(e.PATH, m, "E", "204", kopt)
        elif kopt == "ALPHA":
            if not e.DFAULT:
                e.L_ALPHA = True
            else:
                e.errhdl(e.PATH, m, "E", "204", kopt)
        elif kopt == "BETA":
            if not e.DFAULT:
                e.BETA = True
            else:
                e.errhdl(e.PATH, m, "E", "204", kopt)
        elif kopt == "FASTAREA":
            if e.FASTALL:
                e.errhdl(e.PATH, m, "W", "192", "        ")
            if not e.DFAULT:
                e.FASTAREA = True
            else:
                e.errhdl(e.PATH, m, "E", "204", kopt)
        elif kopt == "FASTALL":
            if e.FASTAREA:
                e.errhdl(e.PATH, m, "W", "192", "        ")
            if not e.DFAULT:
                e.FASTAREA = True
                e.FASTALL = True
                e.L_EFFSIGY = True
            else:
                e.errhdl(e.PATH, m, "E", "204", kopt)
        elif kopt == "NOURBTRAN":
            if not e.DFAULT:
                e.L_URBANTRANSITION = False
                e.errhdl(e.PATH, m, "W", "151", "Keyword     ")
            else:
                e.errhdl(e.PATH, m, "E", "204", kopt)
        elif kopt == "VECTORWS":
            e.L_VECTORWS = True
            e.errhdl(e.PATH, m, "W", "116", kopt)
        elif kopt == "LOW_WIND":
            if e.L_ALPHA:
                e.LOW_WIND = True
                e.errhdl(e.PATH, m, "W", "136", "NonDFAULT")
                e.DFAULT = False
            else:
                e.LOW_WIND = False
                e.errhdl(e.PATH, m, "E", "133", "NonDFAULT")
        elif kopt == "AREAMNDR":
            if e.L_ALPHA:
                e.L_AREAMNDR = True
                e.errhdl(e.PATH, m, "W", "134", "NonDFAULT")
                e.DFAULT = False
            else:
                e.L_AREAMNDR = False
                e.errhdl(e.PATH, m, "E", "139", "NonDFAULT")
            if not e.DFAULT:
                e.errhdl(e.PATH, m, "W", "198", kopt)
            else:
                e.errhdl(e.PATH, m, "E", "204", kopt)
            e.WSMIN = 0.2828
        elif kopt == "RLINEFDH":
            if e.L_ALPHA:
                e.FAC_DISPHT = 0.0
            else:
                e.errhdl(e.PATH, m, "E", "198", "RLINEFDH")
        elif kopt == "NOMINO3":
            e.NOMINO3 = True
            if not e.OLM and not e.PVMRM and not e.GRSM and not e.RUNTTRM:
                e.errhdl(e.PATH, m, "E", "621", kopt)
        elif kopt == "BAREDGE":
            e.BAREDGE = True
        else:
            e.errhdl(e.PATH, m, "E", "203", kopt)
    if e.OLM and e.PVMRM:
        e.errhdl(e.PATH, m, "E", "141", "OLM & PVMRM")
    elif e.OLM and e.ARM2:
        e.errhdl(e.PATH, m, "E", "141", "OLM & ARM2")
    elif e.OLM and e.GRSM:
        e.errhdl(e.PATH, m, "E", "141", "OLM & GRSM")
    elif e.PVMRM and e.ARM2:
        e.errhdl(e.PATH, m, "E", "141", "PVMRM & ARM2")
    elif e.PVMRM and e.GRSM:
        e.errhdl(e.PATH, m, "E", "141", "PVMRM & GRSM")
    elif e.ARM2 and e.GRSM:
        e.errhdl(e.PATH, m, "E", "141", "ARM2 & GRSM")
    elif not e.RUNTTRM2 and e.RUNTTRM and e.ARM2:
        e.errhdl(e.PATH, m, "E", "141", "TTRM & ARM2")
    elif not e.RUNTTRM2 and e.RUNTTRM and e.OLM:
        e.errhdl(e.PATH, m, "E", "141", "TTRM & OLM")
    elif not e.RUNTTRM2 and e.RUNTTRM and e.PVMRM:
        e.errhdl(e.PATH, m, "E", "141", "TTRM & PVMRM")
    elif e.RUNTTRM and e.GRSM:
        e.errhdl(e.PATH, m, "E", "141", "TTRM & GRSM")
    elif e.RUNTTRM2 and e.GRSM:
        e.errhdl(e.PATH, m, "E", "141", "TTRM2 & GRSM")
    elif e.RUNTTRM2 and ((e.OLM and e.ARM2) or (e.PVMRM and e.ARM2) or (e.OLM and e.PVMRM)):
        e.errhdl(e.PATH, m, "E", "141", "TTRM2 & >2 NO2 Options")
    if e.PSDCREDIT and not e.PVMRM:
        e.errhdl(e.PATH, m, "E", "143", "PSDCREDIT")
    if e.PSDCREDIT and e.EVONLY:
        e.errhdl(e.PATH, m, "E", "147", " EVENTS ")
    if not e.DFAULT and (e.FLAT or e.FLATSRCS or e.ARDPLETE or e.NOSTD or e.NOCHKD or e.SCREEN or e.SCIM
                         or e.PSDCREDIT or e.BETA or e.FASTAREA or e.FASTALL or e.LOW_WIND or e.L_ALPHA
                         or e.GRSM or e.L_PBAL or not e.L_URBANTRANSITION):
        e.L_NONDFAULT = True
    if e.NUMTYP > e.NTYP:
        e.DUMMY = fwrite("(I4)", e.NTYP)[0]
        e.errhdl(e.PATH, m, "E", "280", e.DUMMY)
    elif e.NUMTYP == 0:
        e.errhdl(e.PATH, m, "W", "205", "CONC")
        e.NUMTYP = 1
        e.ITYP = 1
        e.CONC = True
        _tipo(e, 1, "CONC")
    else:
        orden = [n for n in ("CONC", "DEPOS", "DDEP", "WDEP") if getattr(e, n)]
        for ityp, n in enumerate(orden, 1):
            e.ITYP = ityp
            _tipo(e, ityp, n)
    e.EMICON = 1.0e06
    # formatos de PLOTFILE, POSTFILE y MAXDCONT con varios tipos de salida (FILE_FORMAT viene de
    # PRESET; PM25AVE/NO2AVE/SO2AVE aún no se han fijado aquí)
    nt = e.NUMTYP
    if nt > 1 and e.FILE_FORMAT == "FIX":
        if e.PM25AVE or e.NO2AVE or e.SO2AVE:
            e.PLTFRM = "(%d(1X,F13.5),3(1X,F8.2),2X,A6,2X,A8,2X,A5,5X,A8,2X,10(F13.5,2X,I8.8,2X:))" % (nt + 2)
        else:
            e.PLTFRM = "(%d(1X,F13.5),3(1X,F8.2),3X,A5,2X,A8,2X,A5,5X,A8,2X,I8)" % (nt + 2)
        e.PSTFRM = "(%d(1X,F13.5),3(1X,F8.2),2X,A6,2X,A8,2X,I8.8,2X,A8)" % (nt + 2)
        e.MXDFRM = "(%d(1X,F13.5),3(1X,F8.2),2X,A6,2X,A8,2X,I4,2X,I3,2X,I8.8,2X,A8)" % (nt + 2)
    elif nt > 1 and e.FILE_FORMAT == "EXP":
        if e.PM25AVE or e.NO2AVE or e.SO2AVE:
            e.PLTFRM = "(2(1X,F13.5),%d(1X,E13.6),3(1X,F8.2),2X,A6,2X,A8,2X,A5,5X,A8,2X,10(E13.6,2X,I8.8,2X:))" % nt
        else:
            e.PLTFRM = "(2(1X,F13.5),%d(1X,E13.6),3(1X,F8.2),3X,A5,2X,A8,2X,A5,5X,A8,2X,I8)" % nt
        e.PSTFRM = "(2(1X,F13.5),%d(1X,E13.6),3(1X,F8.2),2X,A6,2X,A8,2X,I8.8,2X,A8)" % nt
        e.MXDFRM = "(2(1X,F13.5),%d(1X,E13.6),3(1X,F8.2),2X,A6,2X,A8,2X,I4,2X,I3,2X,I8.8,2X,A8)" % nt


def avetim(e):
    """AVETIM: periodos de promedio (AVERTIME)."""
    m = "AVETIM"
    f = e.FIELD
    if e.IFC < 3:
        e.errhdl(e.PATH, m, "E", "200", e.KEYWRD)
    for i in range(3, e.IFC + 1):
        kopt = f[i][:8]
        if kopt == "PERIOD":
            e.PERIOD = True
        elif kopt == "ANNUAL":
            e.ANNUAL = True
    if e.PERIOD and e.ANNUAL:
        e.errhdl(e.PATH, m, "E", "294", e.KEYWRD)
    elif e.PERIOD or e.ANNUAL:
        if e.IFC > e.NAVE + 3:
            e.errhdl(e.PATH, m, "E", "202", e.KEYWRD)
    else:
        if e.IFC > e.NAVE + 2:
            e.errhdl(e.PATH, m, "E", "202", e.KEYWRD)
    j = 0
    avenum = 0.0
    for i in range(3, e.IFC + 1):
        kopt = f[i][:8].rstrip(" ")
        if kopt in ("PERIOD", "ANNUAL"):
            continue
        if kopt != "MONTH":
            avenum, imit = stonum(kopt, 8, avenum)
            e.IMIT = imit
            if imit != 1:
                e.errhdl(e.PATH, m, "E", "208", e.KEYWRD)
            n = nint(avenum)
            if imit == 1 and n != 0 and _fmod(24, n) == 0:
                j += 1
                if j <= e.NAVE:
                    e.KAVE[j] = n
                    e.CHRAVE[j] = fwrite('(I2,"-HR")', n)[0]
                    e.NUMAVE = j
                    for k in range(j - 1, 0, -1):
                        if e.KAVE[j] == e.KAVE[k]:
                            e.errhdl(e.PATH, m, "E", "211", e.KEYWRD)
                else:
                    e.DUMMY = fwrite("('NAVE=',I7)", e.NAVE)[0]
                    e.errhdl(e.PATH, m, "E", "290", e.DUMMY)
            else:
                e.errhdl(e.PATH, m, "E", "203", "AVEPER")
        else:
            j += 1
            if j <= e.NAVE:
                e.KAVE[j] = 720
                e.MONTH = True
                e.CHRAVE[j] = "MONTH"
                e.NUMAVE = j
                for k in range(j - 1, 0, -1):
                    if e.KAVE[j] == e.KAVE[k]:
                        e.errhdl(e.PATH, m, "E", "211", e.KEYWRD)
            else:
                e.DUMMY = fwrite("('NAVE=',I7)", e.NAVE)[0]
                e.errhdl(e.PATH, m, "E", "290", e.DUMMY)


def _fmod(a, b):
    r = abs(a) % abs(b)
    return -r if a < 0 else r


def pollid(e):
    """POLLID: identificador del contaminante (POLLUTID)."""
    m = "POLLID"
    f = e.FIELD
    pm25 = ("PM25", "PM-2.5", "PM-25", "PM2.5")
    if e.IFC <= 2:
        e.errhdl(e.PATH, m, "E", "200", e.KEYWRD)
        return
    elif e.IFC == 3:
        e.POLLUT = fc(f[3], 8)
    elif e.IFC == 4:
        if f[3] in ("NO2", "SO2") + pm25:
            e.POLLUT = fc(f[3], 8)
        else:
            e.POLLUT = fc(f[3], 8)
            if f[4] in ("H1H", "H2H", "INC"):
                e.DUMMY = fc(fwrite("(A,1X,A3)", e.POLLUT, f[4][:3].ljust(3))[0], 12)
                e.errhdl(e.PATH, m, "E", "277", e.DUMMY)
                e.NO2_FIELD4 = fc(f[4], 3)
                return
            e.errhdl(e.PATH, m, "E", "202", e.KEYWRD)
            return
        if f[4] in ("H1H", "H2H", "INC"):
            msg = fc(fwrite("(A,1X,A3)", e.POLLUT, f[4][:3].ljust(3))[0], 12)
            if e.POLLUT == "NO2":
                e.L_NO_NO2AVE = True
                e.NO2_FIELD4 = fc(f[4], 3)
                e.DUMMY = msg
                e.errhdl(e.PATH, m, "W", "276", e.DUMMY)
            elif e.POLLUT == "SO2":
                e.L_NO_SO2AVE = True
                e.SO2_FIELD4 = fc(f[4], 3)
                e.DUMMY = msg
                e.errhdl(e.PATH, m, "W", "276", e.DUMMY)
            elif e.POLLUT in pm25:
                e.L_NO_PM25AVE = True
                e.PM25_FIELD4 = fc(f[4], 3)
                e.DUMMY = msg
                e.errhdl(e.PATH, m, "W", "276", e.DUMMY)
            else:
                e.DUMMY = msg
                e.errhdl(e.PATH, m, "E", "277", e.DUMMY)
                return
    else:
        e.errhdl(e.PATH, m, "E", "202", e.KEYWRD)
        return
    e.POLLUT = fc(f[3], 8)
    e.POLLCRIT = e.POLLUT in ("SOX", "SO2", "NOX", "NO2", "CO", "TSP", "PM10", "PM-10", "PM25", "PM-2.5",
                              "PM2.5", "PM-25", "LEAD", "PB")


def edecay(e):
    """EDECAY: semivida o coeficiente de decaimiento."""
    m = "EDECAY"
    if e.IFC <= 2:
        e.errhdl(e.PATH, m, "E", "200", e.KEYWRD)
        return
    elif e.IFC > 3:
        e.errhdl(e.PATH, m, "E", "202", e.KEYWRD)
        return
    e.DNUM, imit = dbl(e, 3, e.DNUM)
    e.IMIT = imit
    if imit != 1:
        e.errhdl(e.PATH, m, "E", "208", e.KEYWRD)
        return
    if e.KEYWRD == "HALFLIFE":
        e.HAFLIF = e.DNUM
        e.DECOEF = 0.693 / e.HAFLIF
    else:
        e.DECOEF = e.DNUM
    if e.DFAULT and e.L_PRESET_URBAN and e.POLLUT == "SO2":
        if e.DECOEF != 4.81e-5:
            e.errhdl(e.PATH, m, "W", "206", "DCAYCOEF")
        e.DECOEF = 4.81e-5
    elif e.DFAULT:
        if e.DECOEF != 0.0:
            e.errhdl(e.PATH, m, "W", "206", "DCAYCOEF")
        e.DECOEF = 0.0
    elif not e.DFAULT and e.DECOEF != 0.0:
        e.L_NONDFAULT = True


def runnot(e):
    """RUNNOT: RUNORNOT RUN/NOT."""
    m = "RUNNOT"
    if e.IFC == 3:
        if e.FIELD[3] == "RUN":
            e.RUN = True
        elif e.FIELD[3] == "NOT":
            e.RUN = False
        else:
            e.errhdl(e.PATH, m, "E", "203", e.KEYWRD)
    elif e.IFC > 3:
        e.errhdl(e.PATH, m, "E", "202", e.KEYWRD)
    else:
        e.errhdl(e.PATH, m, "E", "200", e.KEYWRD)


def flagdf(e):
    """FLAGDF: altura de receptor por defecto (FLAGPOLE)."""
    m = "FLAGDF"
    e.FLGPOL = True
    if e.IFC == 3:
        zflg, imit = dbl(e, 3, 0.0)
        e.IMIT = imit
        if imit != 1:
            e.errhdl(e.PATH, m, "E", "208", e.KEYWRD)
        if imit == 1 and zflg >= 0.0:
            e.AZFLAG[:] = zflg
        elif imit == 1 and zflg < 0.0:
            e.errhdl(e.PATH, m, "E", "209", "ZFLAG")
        else:
            e.errhdl(e.PATH, m, "E", "203", e.KEYWRD)
    elif e.IFC > 3:
        e.errhdl(e.PATH, m, "E", "202", e.KEYWRD)
    else:
        e.errhdl(e.PATH, m, "W", "205", "ZFLAG=0.")


def errfil(e):
    """ERRFIL: fichero de mensajes detallado (ERRORFIL)."""
    m = "ERRFIL"
    if e.IFC == 3:
        e.ERRLST = True
        if e.LOCE[3] - e.LOCB[3] <= ILEN_FLD - 1:
            e.MSGFIL = fc(e.RUNST1[int(e.LOCB[3]) - 1:int(e.LOCE[3])], 200)
            try:
                e.abrir_salida(e.IERWRT, e.MSGFIL)
            except OSError:
                e.errhdl(e.PATH, m, "E", "500", "ERRORFIL")
                return
            e.FUNITARRAY[e.FUNITIND] = e.IERWRT
            e.FNAMEARRAY[e.FUNITIND] = e.MSGFIL
            e.FTYPARRAY[e.FUNITIND] = "IERWRT"
            e.FUNITIND += 1
        else:
            e.DUMMY = i8(ILEN_FLD)
            e.errhdl(e.PATH, m, "E", "291", e.DUMMY)
    elif e.IFC > 3:
        e.errhdl(e.PATH, m, "E", "202", e.KEYWRD)
    else:
        e.errhdl(e.PATH, m, "W", "207", e.KEYWRD)
        e.ERRLST = True
        e.MSGFIL = "ERRORS.LST"


# ------------------------------------------------------------------ re-arranque y varios años
def _fichero_campo(e, m, campo, lb=None):
    """RUNST1(LOCB(campo):LOCE(campo)) con la comprobación de longitud del original (`lb` es el
    índice del LOCB que usa la comprobación, que en MYEAR no siempre es el del campo). Devuelve
    None (error 291) si es demasiado largo."""
    lb = campo if lb is None else lb
    if e.LOCE[campo] - e.LOCB[lb] <= ILEN_FLD - 1:
        return fc(e.RUNST1[int(e.LOCB[campo]) - 1:int(e.LOCE[campo])], 200)
    e.DUMMY = i8(ILEN_FLD)
    e.errhdl(e.PATH, m, "E", "291", e.DUMMY)
    return None


def savefl(e):
    """SAVEFL: fichero de re-arranque (SAVEFILE)."""
    m = "SAVEFL"
    if e.MULTYR:
        e.errhdl(e.PATH, m, "E", "150", e.KEYWRD)
    elif e.IFC in (3, 4, 5):
        e.RSTSAV = True
        nom = _fichero_campo(e, m, 3)
        if nom is None:
            return
        e.SAVFIL = nom
        if e.IFC == 3:
            e.SAVFL2 = e.SAVFIL
            e.INCRST = 1
            return
        if e.IFC == 4:
            e.SAVFL2 = e.SAVFIL
        e.FNUM, imit = num(e, 4, e.FNUM)
        e.IMIT = imit
        e.INCRST = nint(e.FNUM)
        if imit != 1:
            e.errhdl(e.PATH, m, "E", "208", e.KEYWRD)
        if e.IFC == 5:
            nom = _fichero_campo(e, m, 5)
            if nom is None:
                return
            e.SAVFL2 = nom
    elif e.IFC > 5:
        e.errhdl(e.PATH, m, "E", "202", e.KEYWRD)
    else:
        e.errhdl(e.PATH, m, "W", "207", e.KEYWRD)
        e.RSTSAV = True
        e.SAVFIL = "SAVE.FIL"
        e.SAVFL2 = e.SAVFIL
        e.INCRST = 1


def initfl(e):
    """INITFL: fichero de inicio de un re-arranque (INITFILE)."""
    m = "INITFL"
    if e.MULTYR:
        e.errhdl(e.PATH, m, "E", "150", e.KEYWRD)
    elif e.IFC == 3:
        e.RSTINP = True
        nom = _fichero_campo(e, m, 3)
        if nom is None:
            return
        e.INIFIL = nom
    elif e.IFC > 3:
        e.errhdl(e.PATH, m, "E", "202", e.KEYWRD)
    else:
        e.errhdl(e.PATH, m, "W", "207", e.KEYWRD)
        e.RSTINP = True
        e.INIFIL = "SAVE.FIL"


_MYEAR_POL = ("PM10", "PM-10", "NO2", "SO2", "LEAD", "OTHER", "PM25", "PM-2.5", "PM-25", "PM2.5")


def myear(e):
    """MYEAR: corrida de varios años encadenados (MULTYEAR); INCRST se fija en MECARD."""
    m = "MYEAR"
    f = e.FIELD
    if e.RSTSAV:
        e.errhdl(e.PATH, m, "E", "150", "SAVEFILE")
    elif e.RSTINP:
        e.errhdl(e.PATH, m, "E", "150", "INITFILE")
    elif e.POLLUT not in _MYEAR_POL:
        e.errhdl(e.PATH, m, "E", "150", e.POLLUT)
    elif e.IFC >= 4 and f[3] == "H6H":
        e.errhdl(e.PATH, m, "W", "352", "Keyword ")
        if e.IFC in (4, 5):
            e.MULTYR = True
            e.RSTSAV = True
            nom = _fichero_campo(e, m, 4)
            if nom is None:
                return
            e.SAVFIL = nom
            e.SAVFL2 = e.SAVFIL
            if e.IFC == 5:
                e.RSTINP = True
                nom = _fichero_campo(e, m, 5)
                if nom is None:
                    return
                e.INIFIL = nom
        elif e.IFC > 5:
            e.errhdl(e.PATH, m, "E", "202", e.KEYWRD)
    elif e.IFC >= 3 and f[3] != "H6H":
        if e.IFC in (3, 4):
            e.MULTYR = True
            e.RSTSAV = True
            # con un solo campo el original compara LOCE(3) con LOCB(4) (resto de una línea anterior)
            nom = _fichero_campo(e, m, 3, lb=4 if e.IFC == 3 else 3)
            if nom is None:
                return
            e.SAVFIL = nom
            e.SAVFL2 = e.SAVFIL
            if e.IFC == 4:
                e.RSTINP = True
                nom = _fichero_campo(e, m, 4)
                if nom is None:
                    return
                e.INIFIL = nom
        elif e.IFC > 4:
            e.errhdl(e.PATH, m, "E", "202", e.KEYWRD)
    elif e.IFC == 3 and f[3] == "H6H":
        e.errhdl(e.PATH, m, "E", "201", e.KEYWRD)
    elif e.IFC < 3:
        e.errhdl(e.PATH, m, "E", "200", e.KEYWRD)


def _abrir_reinicio(e):
    """FINISHED: abre (vacíos) los SAVEFILE y comprueba el INITFILE. Devuelve False si falla la
    apertura (el original salta entonces al final de FINISHED, tras el error 500)."""
    import os
    m = "COCARD"
    if e.RSTSAV:
        e.DUMMY = "SAVEFILE"
        for nom in ([e.SAVFIL] + ([e.SAVFL2] if e.SAVFL2 != e.SAVFIL else [])):
            try:
                open(nom, "wb").close()
            except OSError:
                return _error_reinicio(e, m)
    if e.RSTINP:
        if e.RSTSAV and (e.INIFIL == e.SAVFIL or e.INIFIL == e.SAVFL2):
            e.errhdl(e.PATH, m, "E", "590", "       ")
        else:
            e.DUMMY = "INITFILE"
            if not os.path.isfile(e.INIFIL):
                return _error_reinicio(e, m)
            try:
                e.abrir_entrada_bin(e.IRSUNT, e.INIFIL)
            except OSError:
                return _error_reinicio(e, m)
            e.FUNITARRAY[e.FUNITIND] = e.IRSUNT
            e.FNAMEARRAY[e.FUNITIND] = e.INIFIL
            e.FTYPARRAY[e.FUNITIND] = "IRSUNT"
            e.FUNITIND += 1
    return True


def _error_reinicio(e, m):
    e.errhdl(e.PATH, m, "E", "500", e.DUMMY)
    if e.DUMMY == "SAVEFILE":
        e.RSTSAV = False
    elif e.DUMMY == "INITFILE":
        e.RSTINP = False
    return False
