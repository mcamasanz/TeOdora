# -*- coding: utf-8 -*-
"""Traducción de AERMOD 26135 (US EPA, dominio público): emisiones horarias desde fichero
(HOUREMIS): HRQREAD y HRQEXT de aermod.f. La tarjeta SO HOUREMIS (HREMIS) está en entrada_fuentes.py y la
lectura de cada hora en bucle_horario.py (HRLOOP)."""
from . import control
from .formato import fc, fwrite, nint
from .meteo_horaria import cent_date2
from .estado import NoTraducido


def _area_o_linea(t):
    return t[:4] == "AREA" or t in ("LINE", "RLINE", "RLINEXT")


def hrqread(e, i):
    """HRQREAD(IS): lee el registro de la fuente IS del fichero de emisiones horarias. Deja ILINE
    en el número de línea de ese fichero (IQLINE(IS)), como el original, que no lo restaura."""
    m = "HRQREAD"
    ilsave = e.ILINE
    e.ILINE = int(e.IQLINE[i])
    e.IHREMI = int(e.HOUREMISARRAY[i])
    reg = e.U[e.IHREMI].leer()
    if reg is None:
        e.EOF = True
        return
    control.cargar(e, reg)
    control.define(e)
    control.getfld(e)
    ifc = e.IFC
    if ifc < 7:
        e.errhdl(e.PATH, m, "E", "384", fwrite("(I8)", e.KURDAT)[0])
        e.RUNERR = True
        return
    fecha = []
    for k in (3, 4, 5, 6):
        e.FNUM, imit = control.num(e, k, e.FNUM)
        fecha.append(nint(e.FNUM))
        if imit != 1:
            e.errhdl(e.PATH, m, "E", "208", "HOUREMIS")
            e.RUNERR = True
            return
    ihyear, ihmon, ihday, ihhour = fecha
    if ihyear <= 99:
        _dos, ihyear = cent_date2(e, 0, ihyear)
    e.FULLHRQ = ihyear * 1000000 + ihmon * 10000 + ihday * 100 + ihhour
    if fc(e.FIELD[7], 12) != e.SRCID[i]:
        e.errhdl(e.PATH, m, "E", "342", e.SRCID[i])
        e.RUNERR = True
        return
    t = e.SRCTYP[i]
    hrly = bool(e.L_HRLYSIG[i])
    fhq = fwrite("(I10.10)", e.FULLHRQ)[0]

    def leer(k, nom):
        v, imit = control.dbl(e, k, getattr(e, nom))
        setattr(e, nom, v)
        if imit != 1:
            e.errhdl(e.PATH, m, "E", "208", "HOUREMIS")
            e.RUNERR = True
            return False
        return True

    def leer_q():
        if not leer(8, "HRQS"):
            return False
        if e.HRQS <= -90.0:
            e.HRQS = 0.0
            e.errhdl(e.PATH, m, "W", "341", fhq)
        return True

    def sigmas_horarias():
        """Primera línea (ILSAVE = 1, desde SRCQA): activa L_HRLYSIG; después, deben coincidir."""
        if ilsave == 1:
            e.L_HRLYSIG[i] = True
        elif ilsave > 1 and not e.L_HRLYSIG[i]:
            e.errhdl(e.PATH, m, "E", "345", fhq)
            e.HRQS = 0.0
            e.RUNERR = True
            return False
        return True

    def fallo(cod, *nombres):
        e.errhdl(e.PATH, m, "E", cod, fhq)
        for nom in nombres:
            setattr(e, nom, 0.0)
        e.RUNERR = True

    if ifc == 7:
        if not e.L_SKIPMESSAGES:
            e.errhdl(e.PATH, m, "W", "344", fhq)
        e.HRQS = e.HRTS = e.HRVS = e.HRHS = e.HRSY = e.HRSZ = e.HRFP = 0.0
    elif t[:5] == "POINT" and ifc == 10:
        if leer_q() and leer(9, "HRTS"):
            leer(10, "HRVS")
    elif t == "VOLUME" and ifc == 11:
        if sigmas_horarias() and leer_q() and leer(9, "HRHS") and leer(10, "HRSY"):
            leer(11, "HRSZ")
    elif t == "VOLUME" and ifc == 8:
        if hrly:
            fallo("345", "HRQS")
            return
        leer_q()
    elif _area_o_linea(t) and ifc == 10:
        if sigmas_horarias() and leer_q() and leer(9, "HRHS"):
            leer(10, "HRSZ")
    elif _area_o_linea(t) and ifc == 8:
        if hrly:
            fallo("345", "HRQS")
            return
        leer_q()
    elif t == "OPENPIT" and ifc == 8:
        leer_q()
    elif t == "BUOYLINE" and ifc == 9:
        if leer_q():
            leer(9, "HRFP")
    elif t[:5] == "POINT" and ifc > 10:
        fallo("346", "HRQS", "HRTS", "HRVS")
    elif t == "VOLUME" and ((hrly and ifc > 11) or (not hrly and ifc > 8)):
        fallo("346", "HRQS", "HRHS", "HRSY", "HRSZ")
    elif _area_o_linea(t) and ((hrly and ifc > 10) or (not hrly and ifc > 8)):
        fallo("346", "HRQS", "HRHS", "HRSZ")
    elif t == "OPENPIT" and ifc > 8:
        fallo("346", "HRQS")
    elif t == "BUOYLINE" and ifc > 9:
        fallo("346", "HRQS", "HRFP")
    elif t[:5] == "POINT":
        fallo("384", "HRQS", "HRTS", "HRVS")
    elif t == "VOLUME" and ((hrly and ifc < 11) or (not hrly and ifc < 8)):
        fallo("384", "HRQS", "HRHS", "HRSY", "HRSZ")
    elif _area_o_linea(t) and ((hrly and ifc < 10) or (not hrly and ifc < 8)):
        fallo("384", "HRQS", "HRHS", "HRSZ")
    elif t == "BUOYLINE":
        fallo("384", "HRQS", "HRFP")
    else:
        fallo("345", "HRQS")


def hrqext(e, i):
    """HRQEXT(IS): pasa los parámetros leídos de la hora a las matrices de la fuente y los
    comprueba."""
    m = "HRQEXT"
    if e.EVONLY:
        raise NoTraducido("EVENT")
    t = e.SRCTYP[i]
    hrly = bool(e.L_HRLYSIG[i])
    e.AQS[i] = e.HRQS
    if t[:5] == "POINT":
        e.ATS[i] = e.HRTS
        e.AVS[i] = e.HRVS
    elif t == "VOLUME" and hrly:
        e.AHS[i] = e.HRHS
        e.ASYINI[i] = e.HRSY
        e.ASZINI[i] = e.HRSZ
    elif _area_o_linea(t) and hrly:
        e.AHS[i] = e.HRHS
        e.ASZINI[i] = e.HRSZ
    elif t == "BUOYLINE":
        from . import fuente_linea_flotante
        fuente_linea_flotante.hrqext_bl(e, i)
    if e.AFTSRC[i] == "Y":
        raise NoTraducido("fuentes de aeronaves")
    sk = e.L_SKIPMESSAGES
    if t[:5] == "POINT":
        ats, aqs = e.ATS[i], e.AQS[i]
        if ats == 0.0:
            e.ATS[i] = -1.0e-5
        elif ats > 2000.0:
            if not sk:
                e.errhdl(e.PATH, m, "W", "320", "HRTS")
        elif abs(aqs) > 0.0 and 0.0 < ats < 200.0 and e.AVS[i] > 200.0:
            if not sk:
                e.errhdl(e.PATH, m, "E", "320", "HRTS")
                e.RUNERR = True
        elif abs(aqs) > 0.0 and 0.0 < ats < 200.0:
            if not sk:
                e.errhdl(e.PATH, m, "W", "320", "HRTS")
        avs = e.AVS[i]
        if avs < 0.0:
            if not sk:
                e.errhdl(e.PATH, m, "W", "325", e.SRCID[i])
            e.AVS[i] = 1.0e-5
        elif avs < 1.0e-5:
            e.AVS[i] = 1.0e-5
        elif avs > 50.0:
            if not sk:
                e.errhdl(e.PATH, m, "I", "320", "HRVS")
    elif t == "VOLUME" or _area_o_linea(t):
        ahs = e.AHS[i]
        if ahs < 0.0:
            e.errhdl(e.PATH, m, "E", "209", "HRHS")
        elif ahs > 100.0:
            if not sk:
                e.errhdl(e.PATH, m, "W", "320", "HRHS")
        elif ahs > 3000.0:
            e.errhdl(e.PATH, m, "E", "324", e.SRCID[i])
            e.RUNERR = True
        sigmas = (("ASYINI", "HRSY"), ("ASZINI", "HRSZ")) if t == "VOLUME" else (("ASZINI", "HRSZ"),)
        for attr, nom in sigmas:
            a = getattr(e, attr)
            if a[i] < 0.0:
                e.errhdl(e.PATH, m, "E", "209", nom)
                a[i] = 1.0e-5
            elif a[i] < 1.0e-5:
                if not sk:
                    e.errhdl(e.PATH, m, "W", "320", nom)
                a[i] = 1.0e-5
            elif a[i] > 200.0:
                if not sk:
                    e.errhdl(e.PATH, m, "W", "320", nom)
    elif t == "BUOYLINE":
        from . import fuente_linea_flotante
        fuente_linea_flotante.hrqext_bl_qa(e, i)
