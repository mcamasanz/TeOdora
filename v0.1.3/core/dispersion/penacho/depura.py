# -*- coding: utf-8 -*-
"""Traducción de AERMOD 26135 (US EPA, dominio público): opciones de depuración (DEBUGOPT).

- DEBOPT (coset.f): la clave puede repetirse; las opciones de todas las tarjetas se procesan
  juntas en la última (D144), con los nombres de fichero por defecto o los que siguen a cada opción.
- OPEN_DEBUGFILE y OPEN_ALL_DEBUGFILES (coset.f): apertura de los ficheros con la cabecera común.
- Los volcados de cada rutina (MODEL, METEOR, AREA, PRIME, PVMRM, OLM, ARM2, GRSM, DEPOS, AWMADW,
  TTRM, URBANDB, BLPDBUG, SWPOINT, RLINE...) están aquí como funciones que llaman las rutinas de
  cálculo con una sola sentencia `depura.nombre(e, ...)`: el generador del núcleo numba las
  sustituye, y con cualquier opción de depuración activa el cálculo va por la vía Python
  (`nucleo.activo()` devuelve False), que escribe los mismos ficheros que el original.

La escritura dirigida por lista (WRITE(u,*)) usa `fortran.lwrite`, que reproduce la de Intel
(I12, 1PG24.15E3 para DOUBLE PRECISION, 1PG15.7E2 para REAL, registros de 80 columnas)."""
import numpy as np

from .formato import fc, fwrite, fx, lwrite

F32 = np.float32

# opciones de DEBUGOPT (DEBUGOPT_ARRAY del original)
_OPCIONES = ("MODEL", "METEOR", "AREA", "LINE", "RLINE", "PRIME", "PVMRM", "OLM", "ARM2", "GRSM",
             "DEPOS", "AWMADW", "TTRM", "TTRM2", "PLATFORM", "URBANDB", "BLPDBUG", "SWPOINT",
             "AIRCRAFT", "HBPDBG", "SBARRIER", "BAREDGE", "VBARRIER")

# banderas -> (atributo de la bandera, nombre de la opción); el orden es el de DEBOPT
_BANDERAS = {"MODEL": "DEBUG", "METEOR": "METEORDBG", "PRIME": "PRIMEDBG", "PVMRM": "PVMRMDBG",
             "OLM": "OLMDEBUG", "ARM2": "ARM2DEBUG", "GRSM": "GRSMDEBUG", "DEPOS": "DEPOSDBG",
             "PLATFORM": "PLATFMDBG", "AWMADW": "AWMADWDBG", "RLINE": "RLINEDBG", "TTRM": "TTRMDBG",
             "TTRM2": "TTRM2DBG", "URBANDB": "URBDBUG", "BLPDBUG": "BLPDBUG", "SWPOINT": "SWDBG",
             "AIRCRAFT": "ARCFTDEBUG", "HBPDBG": "HBPDBG"}


def w(e, u, *items):
    """WRITE(u,*) dirigido por lista."""
    e.U[u].w(lwrite(*items))


def wf(e, u, fmt, *items):
    """WRITE(u,fmt) formateado."""
    e.U[u].w(fwrite(fmt, *items))


def activa(e):
    """¿Hay alguna opción de depuración que escriba desde el cálculo? (fuerza la vía Python)."""
    return bool(e.DEBUG or e.METEORDBG or e.AREADBG or e.PRIMEDBG or e.PVMRMDBG or e.OLMDEBUG or
                e.ARM2DEBUG or e.GRSMDEBUG or e.DEPOSDBG or e.PLATFMDBG or e.AWMADWDBG or e.RLINEDBG or
                e.TTRMDBG or e.TTRM2DBG or e.URBDBUG or e.BLPDBUG or e.SWDBG or e.ARCFTDEBUG or
                e.HBPDBG or e.BARDBG or e.EDGEDBG or e.VBRDBG)


# ------------------------------------------------------------------------------------- DEBOPT
def debopt(e):
    """DEBOPT: tarjeta CO DEBUGOPT (repetible)."""
    m = "DEBOPT"
    if e.IFC < 3:
        e.errhdl(e.PATH, m, "E", "200", e.KEYWRD)
    elif e.IFC > 13:
        e.errhdl(e.PATH, m, "E", "202", e.KEYWRD)
    for i in range(3, e.IFC + 1):
        e.DEBUG_FLS[e.DEBUG_INDEX] = e.FIELD[i].lstrip(" ")
        e.DEBUG_FLS1[e.DEBUG_INDEX] = e.FIELD1[i].lstrip(" ")
        e.DEBUG_INDEX += 1
    if e.CURRENT_DEBUGOPT != e.DEBUG_COUNT:
        return
    f = list(e.DEBUG_FLS)
    f1 = list(e.DEBUG_FLS1)
    locb_sv, loce_sv = e.LOCB.copy(), e.LOCE.copy()
    e.LOCB[:] = 0                 # LOCB_DEBUG / LOCE_DEBUG nunca se rellenan
    e.LOCE[:] = 0
    pos = {}
    nopts = 0
    linedbg = 0
    i = 1
    while i < len(f) and f[i] != "":
        kopt = f[i][:9]
        if kopt == "AREA":
            if not e.AREADBG:
                e.AREADBG = True
                nopts += 1
                pos["AREA"] = i
            elif e.AREADBG and linedbg > 0:
                e.errhdl(e.PATH, m, "E", "738", kopt)
            else:
                e.errhdl(e.PATH, m, "E", "135", kopt)
        elif kopt == "LINE":
            linedbg += 1
            if not e.AREADBG:
                e.AREADBG = True
                nopts += 1
                pos["AREA"] = i
            elif linedbg > 1:
                e.errhdl(e.PATH, m, "E", "135", kopt)
            elif e.AREADBG and linedbg > 0:
                e.errhdl(e.PATH, m, "E", "738", kopt)
        elif kopt in ("SBARRIER", "BAREDGE", "VBARRIER"):
            setattr(e, {"SBARRIER": "BARDBG", "BAREDGE": "EDGEDBG", "VBARRIER": "VBRDBG"}[kopt], True)
            nopts += 1
            pos[kopt] = i
        elif kopt in _BANDERAS:
            b = _BANDERAS[kopt]
            if getattr(e, b):
                e.errhdl(e.PATH, m, "E", "135", kopt)
            setattr(e, b, True)
            nopts += 1
            pos[kopt] = i
        i += 1
    if nopts == 0:
        t = f[3] if len(f) > 3 else ""
        e.DUMMY = fwrite("(A:)", t[:min(12, len(t.rstrip(" ")))])[0]
        e.errhdl(e.PATH, m, "E", "203", e.DUMMY)
        return
    # opciones de depuración sin la opción del modelo a la que se refieren
    for act, cond, txt in ((e.PVMRMDBG, e.PVMRM, "PVMRMDBG"), (e.OLMDEBUG, e.OLM, "OLMDEBUG"),
                           (e.ARM2DEBUG, e.ARM2, "ARM2DEBUG"), (e.GRSMDEBUG, e.GRSM, "GRSMDEBUG"),
                           (e.TTRMDBG, e.RUNTTRM, "TTRMDEBUG"), (e.TTRM2DBG, e.RUNTTRM2, "TTRM2DEBUG"),
                           (e.HBPDBG, e.HBPLUME, "HBPDBG"),
                           (e.DEPOSDBG, e.DEPOS or e.DDEP or e.WDEP, "DEPOSDBG")):
        if act and not cond:
            e.errhdl(e.PATH, m, "E", "194", txt)
    if e.AREADBG and e.NAREA == 0 and e.NCIRC == 0 and e.NLINE == 0 and e.NPIT == 0:
        if f[pos["AREA"]] == "AREA":
            e.errhdl(e.PATH, m, "E", "194", "AREADEBUG")
        elif f[pos["AREA"]] == "LINE":
            e.errhdl(e.PATH, m, "E", "194", "LINEDEBUG")
    nblp = getattr(e, "NBLP", 0) or 0
    for act, cond, txt in ((e.URBDBUG, e.NURB == 0, "URBANDB"), (e.PRIMEDBG, e.NSEC == 0, "PRIMEDBG"),
                           (e.AWMADWDBG, e.NSEC == 0, "AWMADWDBG"), (e.BLPDBUG, nblp == 0, "BLPDBUG"),
                           (e.RLINEDBG, e.NRLINES == 0, "RLINEDBG"), (e.PLATFMDBG, e.NPNT == 0, "PLATFMDBG"),
                           (e.SWDBG, e.NSWP == 0, "SWDBG"), (e.ARCFTDEBUG, e.NAFTSRC == 0, "ARCFTDEBUG"),
                           (e.BARDBG, e.NSBR == 0, "BARDBG"), (e.EDGEDBG, not e.BAREDGE, "BAREDGE")):
        if act and cond:
            e.errhdl(e.PATH, m, "E", "194", txt)

    def nombre(opc, defecto):
        """Fichero que sigue a la opción (FIELD1, con mayúsculas y minúsculas) o el de defecto."""
        j = pos[opc] + 1
        sig = f[j] if j < len(f) else ""
        if sig != "" and sig not in _OPCIONES:
            return fc(f1[j], 200), j
        return defecto, None

    if e.DEBUG:
        e.DBGFIL = nombre("MODEL", "MODEL.DBG")[0]
    if e.METEORDBG:
        e.DBMFIL = nombre("METEOR", "METEOR.DBG")[0]
    if e.AREADBG:
        e.DBAREAFIL = nombre("AREA", "AREA.DBG")[0]
    if e.PRIMEDBG:
        e.DBPRMFIL = nombre("PRIME", "PRIME.DBG")[0]
    if e.PVMRMDBG:
        n, j = nombre("PVMRM", None)
        if j is not None:
            e.DBPVFIL = n
        elif e.PVMRM:
            e.DBPVFIL = "PVMRM.DBG"
        e.RDISPFIL = "RelDisp.dbg"
    if e.OLMDEBUG:
        e.DBOLMFIL = nombre("OLM", "OLM.DBG")[0]
    if e.ARM2DEBUG:
        e.DBARM2FIL = nombre("ARM2", "ARM2.DBG")[0]
    if e.GRSMDEBUG:
        e.DBGRSMFIL = nombre("GRSM", "GRSM.DBG")[0]
    if e.AWMADWDBG:
        e.DBAWMADWFIL = nombre("AWMADW", "AWMADW.DBG")[0]
    if e.RLINEDBG:
        n, j = nombre("RLINE", "RLINE.DBG")
        e.RLINEDBGFIL = n
        if j is not None:
            lt = len(f[j].rstrip(" "))
            e.RLINEDBGFIL_WS = fc(f1[j][:lt - 4] + "_GRIDWS" + f1[j][lt - 4:lt], 200)
        else:
            e.RLINEDBGFIL_WS = "RLINE_GRIDWS.DBG"
    if e.PLATFMDBG:
        e.PLATFMDBGFILE = nombre("PLATFORM", "PLATFORM.DBG")[0]
    if e.DEPOSDBG:
        j = pos["DEPOS"] + 1
        sig = f[j] if j < len(f) else ""
        if e.DBGFIL.strip(" ") == "" or sig != "MODEL":
            e.DBGFIL = "DEPOS.DBG"
        if sig != "" and sig not in _OPCIONES:
            e.errhdl(e.PATH, m, "W", "203", "DEPOSDBG")
    if e.TTRMDBG:
        e.TTRMFIL = nombre("TTRM", "TTRM_DEBUG.DBG")[0]
    if e.URBDBUG:
        n, j = nombre("URBANDB", "URBDBUG.DBG")
        e.URBFIL = n
        if j is not None:
            lt = len(f[j].rstrip(" "))
            e.URBFIL1 = fc(f1[j][:lt - 4] + "1" + f1[j][lt - 4:lt], 200)
            e.URBFIL2 = fc(f1[j][:lt - 4] + "2" + f1[j][lt - 4:lt], 200)
        else:
            e.URBFIL1 = "URBDBUG1.DBG"
            e.URBFIL2 = "URBDBUG2.DBG"
    if e.BLPDBUG:
        e.BLPFIL = nombre("BLPDBUG", "BLPDBUG.DBG")[0]
    if e.SWDBG:
        e.SWFIL = nombre("SWPOINT", "SWPOINT.DBG")[0]
    if e.ARCFTDEBUG:
        e.DBARCFTFIL = nombre("AIRCRAFT", "AIRCRAFT.DBG")[0]
    if e.HBPDBG:
        e.HBPFIL = nombre("HBPDBG", "HBP_DEBUG.DBG")[0]
    if e.BARDBG:
        e.SBARDBGFIL = nombre("SBARRIER", "SBARRIER.DBG")[0]
    if e.EDGEDBG:
        e.EDGEDBGFIL = nombre("BAREDGE", "BAREDGE.DBG")[0]
    if e.VBRDBG:
        e.VBARDBGFIL = nombre("VBARRIER", "VBARRIER.DBG")[0]
    # el original deja FIELD en blanco e IFC = 0 (FIELD_sv/IFC_SV nunca se guardan)
    for k in range(len(e.FIELD)):
        e.FIELD[k] = ""
    e.IFC = 0
    e.LOCB[:] = locb_sv
    e.LOCE[:] = loce_sv


# ------------------------------------------------------------------ apertura de los ficheros
def open_debugfile(e, unidad, fname, nam, dbgoption, dbgopt, ftyp):
    """OPEN_DEBUGFILE: abre el fichero (si no lo está ya) y escribe la cabecera común."""
    modnam = fwrite("(A6,A6)", "OPDBG:", nam.rstrip(" "))[0]
    abierto = any(getattr(f, "nombre", None) == fname for k, f in e.U.items() if k != 6)
    if not abierto:
        try:
            e.abrir_salida(unidad, fname)
        except OSError:
            e.errhdl(e.PATH, modnam, "E", "500", dbgoption)
        else:
            e.FUNITARRAY[e.FUNITIND] = unidad
            e.FNAMEARRAY[e.FUNITIND] = fname
            e.FTYPARRAY[e.FUNITIND] = ftyp
            e.FUNITIND += 1
    else:
        e.errhdl(e.PATH, modnam, "E", "501", dbgoption)
        e.errhdl(e.PATH, modnam, "E", "500", dbgoption)
    if unidad not in e.U:
        # escribir en una unidad sin abrir crea fort.N (Intel)
        e.abrir_salida(unidad, "fort.%d" % unidad)
    out = fwrite("('*** AERMOD - VERSION ',A6,' ***',3X,'*** ',A68,' ***',8X,A8)", fx(e.VERSN, 6),
                 fx(e.TITLE1, 68), fx(e.RUNDAT, 8))
    out += fwrite("('*** AERMET - VERSION ',A6,' ***',3X,'*** ',A19,49X,' ***',8X,A8/)", fx(e.C_METVER, 6),
                  "   EVENT Processing" if e.EVONLY else "NonEVENT Processing", fx(e.RUNTIM, 8))
    out += fwrite("( ' OPTIONS: ', A /)", e.MODOPS_STRING)
    # A12 de una constante más corta: se ajusta a la derecha
    out += fwrite("('************ CO DEBUGOPT: ', 3X, A12,3X,'(Filename: ',A,')','************'/)",
                  dbgopt, fname.rstrip(" "))
    e.w(unidad, out)


def open_all_debugfiles(e):
    """OPEN_ALL_DEBUGFILES: abre los ficheros de las opciones de depuración elegidas y escribe las
    cabeceras de columnas de cada uno."""
    from . import nucleo
    if activa(e):
        nucleo.desactivar()
    m = ""                        # MODNAM sin asignar en el original
    nombre_no2 = ("Hourly & Average EVENT results sorted by day/event/grp/src" if e.EVONLY else
                  "Hourly non-EVENT results sorted by hour/rec/srcgrp/src")
    f201 = "( '******* NO2 ', A50 ,'*******'/)"
    if e.DEBUG or e.DEPOSDBG:
        e.DUMMY = "DebugFile"
        open_debugfile(e, e.DBGUNT, e.DBGFIL, m, e.DUMMY, "MODEL", "DBGUNT")
    if e.METEORDBG:
        e.DUMMY = "DbgMetFile"
        open_debugfile(e, e.DBMUNT, e.DBMFIL, m, e.DUMMY, "METEOR", "Meteorology debug file")
    if e.AREADBG and (e.NAREA > 0 or e.NCIRC > 0 or e.NLINE > 0 or e.NPIT > 0):
        e.DUMMY = "AreaDbgFile"
        open_debugfile(e, e.AREADBUNT, e.DBAREAFIL, m, e.DUMMY, "AREA", "AREADBUNT")
    if e.RLINEDBG:
        e.DUMMY = "RLINEFIL"
        open_debugfile(e, e.RLINEDBUNT, e.RLINEDBGFIL, m, e.DUMMY, "RLINE", "RLINEDBUNT")
        e.DUMMY = "RLINEFIL_WS"
        open_debugfile(e, e.RLINEDBUNT_WS, e.RLINEDBGFIL_WS, m, e.DUMMY, "RLINE", "RLINEDBUNT_WS")
        wf(e, e.RLINEDBUNT_WS, "(3X,'YR',2X,'MO',2X,'DY',2X,'HR',3X,'HT_m',5x,'WS_m_s')")
    if e.PRIMEDBG and e.NSEC > 0:
        e.DUMMY = "PrimeDbgFile"
        open_debugfile(e, e.PRMDBUNT, e.DBPRMFIL, m, e.DUMMY, "PRIME", "PRMDBUNT")
    if e.PVMRMDBG:
        e.DUMMY = "PVMRMFIL"
        open_debugfile(e, e.PVMDBG, e.DBPVFIL, m, e.DUMMY, "PVMRM", "PVMDBG")
        wf(e, e.PVMDBG, f201, fx(nombre_no2, 50))
        if not e.EVONLY:
            wf(e, e.PVMDBG, "(1x,'TYPE    DOM_SRCID     DATE    IREC    GRPID','   ISRC    SRCID       NUMCONT     "
                            "DISTDOM     ','MAXCONC_NOx     O3CONC        O3MOLES      ','NOxMOLES       BHORIZ  "
                            "      BVERT         ','BVERT3       ','PLUMEVOL      OrigConc  X  PercentNO2 =    ',"
                            "'HRVAL         AVEVAL')")
        else:
            wf(e, e.PVMDBG, "(1x,'TYPE    DOM_SRCID     DATE    IEVE     ','EVENTID    IAVE    GRPID   ISRC    "
                            "SRCID     ','NUMCONT   DISTDOM     MAXCONC_NOx     O3CONC   ','     O3MOLES      "
                            "NOxMOLES       BHORIZ        ','BVERT         BVERT3       PLUMEVOL      ',"
                            "'OrigConc  X  PercentNO2 =    ','HRVAL         AVEVAL')")
        e.DUMMY = "RELDISPF"
        open_debugfile(e, e.RDISPUNT, e.RDISPFIL, m, e.DUMMY, "PVMRM", "RDISPUNT")
    if e.OLMDEBUG:
        e.DUMMY = "OLMFIL"
        open_debugfile(e, e.OLMDBG, e.DBOLMFIL, m, e.DUMMY, "OLM", "OLMDBG")
        wf(e, e.OLMDBG, f201, fx(nombre_no2, 50))
        if not e.EVONLY:
            wf(e, e.OLMDBG, "(3X,'DATE    IREC    GRPID   ISRC    SRCID',7X,'IOLM    OLMID     O3CONC',7X,"
                            "'OLMVAL',3X,'X   NO2Ratio  =  NO2VAL',7X,'NO_VAL',6X,'OrigConc  ',"
                            "'X  PercentNO2 =  HRVAL',8X,'AVEVAL')")
        else:
            wf(e, e.OLMDBG, "(3X,'DATE    IEVE   EVENTID   IAVE    GRPID',3x,'ISRC',4x,'SRCID       IOLM  OLMID"
                            "       O3CONC',7x,'OLMVAL   X   NO2Ratio  =  NO2VAL       NO_VAL',6x,"
                            "'OrigConc  X  PercentNO2 =  HRVAL       EV_AVEVAL')")
    if e.ARM2DEBUG:
        e.DUMMY = "ARM2FIL"
        open_debugfile(e, e.ARM2DBG, e.DBARM2FIL, m, e.DUMMY, "ARM2", "ARM2DBG")
        wf(e, e.ARM2DBG, f201, fx(nombre_no2, 50))
        if not e.EVONLY:
            wf(e, e.ARM2DBG, "(3X,'DATE',4x,'IREC    GRPID   ISRC    SRCID',11x,'NOXCONC',5x,"
                             "'OrigConc  X  ARM2Ratio =',3x,'HRVAL',8x,'AVEVAL')")
        else:
            wf(e, e.ARM2DBG, "(3X,'DATE',4x,'IEVE   EVENTID   IAVE    GRPID',3x,'ISRC',4x,'SRCID',11x,"
                             "'NOXCONC',6x,'OrigConc X  ','ARM2Ratio =',4x,'HRVAL',6x,'EV_AVEVAL')")
    if e.GRSMDEBUG:
        e.DUMMY = "GRSMFIL"
        open_debugfile(e, e.GRSMDBG, e.DBGRSMFIL, m, e.DUMMY, "GRSM", "GRSMDBG")
        wf(e, e.GRSMDBG, f201, fx(nombre_no2, 50))
        comun = ("'NIGHT-TIME?',2X,'O3 BGD BEFORE (PPB)',2X,'NOX BGD BEFORE (PPB)',2X,"
                 "'NO2 BGD BEFORE (PPB)',2X,'TRAVEL TIME (S)',2X,'CONC x TRAVEL TIME (MICROG.S/M3)',2X,"
                 "'PRIMARY NO2 FRAC',2X,'ORIG NOX CONC (MICROG/M3)',2X,'NO2 FRAC AFTER',2X,"
                 "'NO2 BGD AFTER (PPB)',2X,'HRVAL (MICROG/M3)',2X,")
        cola = ("2X,'INST. PL. AREA (M2)',2X,'ENSEMBLE PL. AREA (M2)',2X,'BUILDINGS FACTOR',2X,"
                "'MULT PLUMES FACTOR')")
        if not e.EVONLY:
            wf(e, e.GRSMDBG, "(1X,'DATE (YYMMDDHH)',2X,'  IREC',2X,'GRPID   ',2X,'  ISRC',2X,'SRCID       ',2X,"
                             + comun + "'AVEVAL (MICROG/M3)'," + cola)
        else:
            wf(e, e.GRSMDBG, "(1X,'DATE (YYMMDDHH)',2X,'  IEVE',2X,'EVENTID   ',2X,'IAVE',2X,'GRPID   ',2X,"
                             "'  ISRC',2X,'SRCID       ',2X," + comun + "'EV_AVEVAL (MICROG/M3)'," + cola)
    if (e.DEBUG or e.DEPOSDBG) and e.LDGAS:
        e.DUMMY = "GDEPFILE"
        open_debugfile(e, e.GDEPDBG, "GDEP.DAT", m, e.DUMMY, "DEPOS", "GDEPDBG")
        wf(e, e.GDEPDBG, "(1X,'YYMMDDHH',3X,'ISRC',4X,'Ra',12X,'Rb',12X,'Rc',12X,'Vdepg')")
    if (e.DEBUG or e.DEPOSDBG) and e.LDPART:
        e.DUMMY = "PDEPFILE"
        open_debugfile(e, e.PDEPDBG, "PDEP.DAT", m, e.DUMMY, "DEPOS", "PDEPDBG")
        wf(e, e.PDEPDBG, "(1X,'YYMMDDHH',3X,'ISRC',1X,'ICAT',2X,'Method No.',3X,'Ra',12X,'Rp',12X,'Vg(i)',9x,"
                         "'Vdep(i)')")
    if e.AWMADWDBG:
        e.DUMMY = "AwmaDwDbgFile"
        open_debugfile(e, e.AWMADWDBUNT, e.DBAWMADWFIL, m, e.DUMMY, "AWMADW", "AwmaDwDBUNT")
    if e.TTRMDBG:
        e.DUMMY = "TTRMFIL"
        open_debugfile(e, e.TTRMUNT, e.TTRMFIL, m, e.DUMMY, "TTRM", "TTRMUNT")
        resto = ("'O3CONC (ppb),Amb. Temp. (K),k1, time coefficent,Distance (m),',"
                 "'Effective WSPD (m/s),Transit Time (s),PRIME Eff. WSPD (m/s),',"
                 "'PRIME Transit Time (s),Plume Type,Downwind Distance,',"
                 "'Radial Distance,Crosswind Distance,UEFF,UEFFD,UEFF3,FRAN,PPF,',"
                 "'GAMFACT,CHI-Indirect,CHI-DIRECT,TOTAL NO,Instack-NO2,',"
                 "'Available NO (as NO2),TTRM FRACTIONAL,TTRM Converted NO2,','Source Sub-total NO2')")
        if not e.EVONLY:
            wf(e, e.TTRMUNT, "(' KURDAT,XREC,YREC,SRCGRP,SRCID,O3CONC (UG/M3),'," + resto)
        else:
            wf(e, e.TTRMUNT, "(' KURDAT,XREC,YREC,ievent,EVNAME,EVAPER,','SRCGRP,SRCID,O3CONC (UG/M3),'," + resto)
    if e.PLATFMDBG:
        e.DUMMY = "PLATFMDBGFILE"
        open_debugfile(e, e.PLATFMDBUNT, e.PLATFMDBGFILE, m, e.DUMMY, "PLATFORM", "PLATFMDBUNT")
    if e.URBDBUG:
        e.DUMMY = "URBFIL"
        open_debugfile(e, e.URBUNT, e.URBFIL, m, e.DUMMY, "URBANDB", "URBUNT")
        wf(e, e.URBUNT, "(1X,'URBAN METEOROLOGY OUTPUT',//,1X,'IURB',2x, 'YR',2X,'MO',2X,'DY',2X,'HR',4X,"
                        "'URBOBLEN',3X,'URBOBLSAV',3X,'RUROBULEN',4X,'URBUSTAR',2x,'URBUSTRSAV',5X,'RURUSTR',6X,"
                        "'DELTUR',7X,'ZIURB',6X,'ZIMECH',6X,'ZICONV',6X,'URBPOP',7X,'URBHF',5X,'URBWSTR',7X,"
                        "'WSTAR',4X,'Amb_Temp',8X,'UREF', 7X,'BOWEN',3X,'STABLE',3x,'MornTrns')")
        e.DUMMY = "URBFIL1"
        open_debugfile(e, e.URBUNT1, e.URBFIL1, m, e.DUMMY, "URBANDB", "URBUNT1")
        wf(e, e.URBUNT1, "('URBDBUG Debug File',51x,a8,/70x,a8)", fx(e.RUNDAT, 8), fx(e.RUNTIM, 8))
        wf(e, e.URBUNT1, "(1X,'URBAN METEOROLOGY OUTPUT',//,1X,'IURB',2x, 'YR',2X,'MO',2X,'DY',2X,'HR',1x,'LVL',"
                         "4X,'GRIDHT',4X,'GRIDSv',4x,'SvCURB',4X,'GRDSvU',4X,'GRIDSw',4X,'SwCURB',4X,'GRDSwU')")
        e.DUMMY = "URBFIL2"
        open_debugfile(e, e.URBUNT2, e.URBFIL2, m, e.DUMMY, "URBANDB", "URBUNT2")
        wf(e, e.URBUNT2, "('URBDBUG Debug File',51x,a8,/70x,a8)", fx(e.RUNDAT, 8), fx(e.RUNTIM, 8))
        wf(e, e.URBUNT2, "(1X,'URBAN METEOROLOGY OUTPUT',//,1X,'IURB',2x, 'YR',2X,'MO',2X,'DY',2X,'HR',1x,'LVL',"
                         "1x,'NBELOW',4X,'GRIDHT',4X,'GRIDTG',4X,'GRDTGU',4x,'GRIDPT',4X,'GRDPTU')")
    if e.BLPDBUG:
        e.DUMMY = "BLPFIL"
        open_debugfile(e, e.BLPUNT, e.BLPFIL, m, e.DUMMY, "BLPDBUG", "BLPUNT")
        wf(e, e.BLPUNT, "(1X,'PLUME RISE HEIGHTS AND DISTANCES OUTPUT',//,1X,'SRCID',9x,'YR',2X,'MO',2X,'DY',2X,"
                        "'HR',5X,'DH1',4X,'DH2',5X,'DH3',4X,'DH4',5X,'DH5',5X,'DH6',5X,'DH7',7X,'XF1',3X,'XF2',5X,"
                        "'XF3',5X,'XF4',5X,'XF5',5X,'XF6',5X,'XF7',7X,'XFB',5X,'XFS',4X,'STAB',1X,'URBOBLEN',2X,"
                        "'OBULEN',5X,'Hs',3X,'FINAL_HT')")
    if e.SWDBG:
        e.DUMMY = "SWFIL"
        open_debugfile(e, e.SWDBGUNT, e.SWFIL, m, e.DUMMY, "SWPOINT", "SWDBGUNT")
    if e.ARCFTDEBUG:
        e.DUMMY = "ARCFTFIL"
        open_debugfile(e, e.ARCFTDBG, e.DBARCFTFIL, m, e.DUMMY, "AIRCRAFT", "ARCFTDBG")
        wf(e, e.ARCFTDBG, "('*** AERMOD - VERSION ',A6,' ***',52X,'*** ',A28,' ***',2X,A8,/115X,' ***',2X,A8/)",
           fx(e.VERSN, 6), fx(e.TITLE1, 68)[:28], fx(e.RUNDAT, 8), fx(e.RUNTIM, 8))
    if e.HBPDBG:
        e.DUMMY = "HBPFIL"
        open_debugfile(e, e.HBPUNT, e.HBPFIL, m, e.DUMMY, "HBPDBG", "HBPUNT")
        wf(e, e.HBPUNT, "(' KURDAT,IREC,SCRID,Current_ZIC,Current_ZIM,','NextHr_ZIC,NextHr_ZIM,Avg_ZI,"
                        "Centerline_HE3,','SigmaZ_SZ3,HTOP,HBOT,HTOPDIF,ZRT,PPF,PPFN,HBP_HRVAL')")
    if e.RUNTTRM2 and e.TTRM2DBG:
        t = e.TTRM2TMP
        e.DUMMY = "AFTTTRM2FIL"
        open_debugfile(e, t[1], "AFTER_TTRM.DBG", m, e.DUMMY, "TTRM2", "TTRM2TMP(1)")
        if e.ARM2:
            e.DUMMY = "AFTARM2FIL"
            open_debugfile(e, t[2], "AFTER_ARM2.DBG", m, e.DUMMY, "ARM2/TTRM2", "TTRM2TMP(2)")
        elif e.OLM:
            e.DUMMY = "AFTOLMFIL"
            open_debugfile(e, t[2], "AFTER_OLM.DBG", m, e.DUMMY, "OLM/TTRM2", "TTRM2TMP(2)")
        else:
            e.DUMMY = "AFTPVMRMFIL"
            open_debugfile(e, t[2], "AFTER_PVMRM.DBG", m, e.DUMMY, "PVMRM/TTRM2", "TTRM2TMP(2)")
        e.DUMMY = "MRGTRM2FIL"
        open_debugfile(e, t[3], "TTRM2_MERGE.DBG", m, e.DUMMY, "TTRM2", "TTRM2TMP(3)")
        for i in (1, 2, 3):
            wf(e, t[i], "('*        X             Y      AVERAGE CONC    ZELEV    ','ZHILL    ZFLAG    AVE     "
                        "GRP       DATE     SRC ID   ',/,'* ____________  ____________  ____________   ______   _',"
                        "'_____   ______  ______  ________  ________  ________  ')")
    if e.EDGEDBG:
        e.DUMMY = "EDGEDBGFIL"
        open_debugfile(e, e.EDGEDBUNT, e.EDGEDBGFIL, m, e.DUMMY, "BAREDGE", "EDGEDBUNT")
        wf(e, e.EDGEDBUNT, "(/'*********   Barrier Influence Zone   ********'/,/45('*')/)")
        wf(e, e.EDGEDBUNT, "(/7X,'Y-COORD',8X,'X-COORD',5X,'Barrier',5X/,5X,'(METERS)',7X,'(METERS)',5X,"
                           "'Zone',7X)")
        it = []
        for ir in range(1, e.NREC + 1):
            it += [e.AYR[ir], e.AXR[ir], bool(e.RL.REEDGE[ir])]
        wf(e, e.EDGEDBUNT, "(/3X, F12.2, 3X, F12.2, 6X, L1, 9X)", *it)
    if e.VBRDBG:
        e.DUMMY = "VBARDBGFIL"
        open_debugfile(e, e.VBRDBUNT, e.VBARDBGFIL, m, e.DUMMY, "VBARRIER", "VBRDBUNT")
        wf(e, e.VBRDBUNT, "(/85('*')/, 'SRCID', 9X, 'BAR#', 4X 'HT', 5X, 'WT',5X, 'DCL', 4X, 'LAI', 3X, 'LAD', 3X,"
                          "'WAKE')")
        for isrc in range(1, e.NSRC + 1):
            if e.SRCTYP[isrc] == "RLINEXT":
                vb = e.RL.VEGBARR[isrc]
                for k in (1, 2):
                    wf(e, e.VBRDBUNT, "(A12, 3X, I1, 4X, F5.1, 2X, F5.1, 2X, F6.1, 2X,F4.1, 2X, F4.1, 2X, F5.1)",
                       fx(e.SRCID[isrc], 12), k, vb.HT[k], vb.WT[k], vb.DCL[k], vb.LAI[k], vb.LM[k], vb.WAKE[k])


# =========================================================================== MODEL (DBGUNT)
def hrloop(e):
    """Marca de la hora en el fichero MODEL (HRLOOP)."""
    u = e.DBGUNT
    w(e, u)
    w(e, u, "--------------------------------", "--------------------")
    w(e, u, "---  JDAY, IHOUR =  ", e.JDAY, e.IHOUR)
    w(e, u, "--------------------------------", "--------------------")


_F_PCALC_6000 = ("(/,5X,'INITIAL PLUME RISE ESTIMATE:  DELH = ',F6.1,' M; Uplume = ',F5.2,' M/S; DTHDZ = ',"
                 "F7.4,' DEG K/M')")
_F_6001 = ("(/,5X,'OPTH2 ITER. #',I1,': OLD DELH = ',F6.1,' M; NEW DELH = ',F6.1,' M; MET LEVEL = ',F6.1,"
           "' M; NEW Upl = ',F5.2,' M/S; NEW DTHDZ = ',F7.4,' K/M')")


def pcalc_delh(e):
    wf(e, e.DBGUNT, _F_PCALC_6000, e.DHFAER, e.UP, e.TGS)


def opth2_iter(e, kiter, dhold, dhnew, zplm):
    """Iteración de la sobreelevación estable (PCALC 6001 y DELTAH 6001)."""
    wf(e, e.DBGUNT, _F_6001, kiter, dhold, dhnew, zplm, e.UP, e.TGP)


def pcalc_noconv(e):
    wf(e, e.DBGUNT, "(/,5X,'PLUME RISE ITERATION FAILED TO CONVERGE; ',' PLUME RISE SET AT ',F6.1,' METERS.',/)",
       e.DHFAER)


def deltah_noconv(e):
    wf(e, e.DBGUNT, "(/,5X,'OPTH2 ITERATION FAILED TO CONVERGE; PLUME',' RISE SET AT ',F6.1,' METERS.',/)",
       e.DHP)


def pcalc_zmid(e):
    wf(e, e.DBGUNT, "(/,72('*'),//,5X,'YR/MN/DY/HR: ',I8,//,5X,'Height assigned to midpoint of ',"
                    "'well-mixed layer for effective parameters = ',F6.1,' meters.',/)", e.KURDAT, e.ZMIDMX)


_F_6011 = ("(5X,'For effective parameter calculations: ','\"Final\" plume rise = ',G14.6, ' m; Distance to final ',"
           "'rise = ',G14.6,' m',/,5x,'Distance to well-mixed ','state = ',G14.6,' m;',/,5x,"
           "'\"Effective\" flow vector = ',F6.2)")


def pcalc_efectivos(e, unidad=None):
    """PCALC: parámetros de los valores efectivos y PSRDEB (en VCALC/ACALC con aeronaves se
    escribe en ARCFTDBG sin PSRDEB)."""
    if unidad is None:
        wf(e, e.DBGUNT, _F_6011, e.DHCRIT, e.XFINAL, e.XMIXED, e.AFV)
        psrdeb(e)
    else:
        wf(e, unidad, _F_6011, e.DHCRIT, e.XFINAL, e.XMIXED, e.AFV)


def psrdeb(e):
    """PSRDEB: datos de la fuente puntual."""
    u = e.DBGUNT
    wf(e, u, "(20('===='),//,' YR/MN/DY/HR:  ', I8,//,8X,'<----------------- SOURCE INFORMATION ---------',"
             "'------> FINAL PLUME',/,' SOURCE   QS    TS      VS     DS   BUOY FLUX  MOM FLUX  ',' HS      RISE',/,"
             "'   #    (G/S)   (K)    (M/S)   (M)   (M4/S3)    (M4/S2)  ',' (M)      (M)',/)", e.KURDAT)
    wf(e, u, "(I4,F9.1,F7.1,F7.2,F7.2,F10.1,2X,F9.1,F6.1,F9.1,//,2X,'VARIABLES AT ',T21,'HEIGHT   WDIR   ',"
             "'USCAL  URISE  SIGV   SIGW   DTHDZ ',/,2X,'STACK HEIGHT:',T21,"
             "'  (M)    (DEG)  (M/S)  (M/S)  (M/S)  (M/S) (DEG/M)',/)",
       e.ISRC, e.QS, e.TS, e.VS, e.DS, e.FB, e.FM, e.HS, e.DHCRIT)
    wf(e, u, "(19X,F7.1,F7.0,F8.2,2F7.2,F7.2,F8.4,/)", e.HS, e.WDIR, e.US, e.UP, e.SVS, e.SWS, e.TGS)


def aerval_comp(e, aerpan, aerplm, fran, val, nombre="AERVAL"):
    """Componentes del penacho coherente y del meandro (PCALC: AERVAL; VCALC: HRVAL)."""
    for it in range(1, e.NUMTYP + 1):
        wf(e, e.DBGUNT, "(/,'" + nombre + "(ITYP) = FRAN*AERPAN(ITYP) + (1.-FRAN)','*AERPLM(ITYP)',//,"
                        "'PANCAKE/MEANDER COMPONENT, AERPAN(ITYP) = ',G16.8,/,'COHERENT PLUME COMPONENT,  "
                        "AERPLM(ITYP) = ',G16.8,/,'MEANDER FACTOR, FRAN = ',G16.8,/,'RESULTANT CONC, " + nombre +
                        "(ITYP) = ',G16.8,//)", aerpan[it], aerplm[it], fran, val[it])


def prime_gamfact(e):
    """PCALC con PRIMEDBG: mezcla de PRIME y AERMOD en el receptor."""
    u = e.PRMDBUNT
    for it in range(1, e.NUMTYP + 1):
        w(e, u, " ")
        w(e, u, "YR/MN/DY/HR:     ", e.KURDAT, " ISRC: ", e.ISRC, " IREC: ", e.IREC)
        w(e, u)
        w(e, u, " GAMFACT = ", e.GAMFACT)
        w(e, u, " AERVAL  = ", e.AERVAL[it])
        w(e, u, " PRMVAL  = ", e.PRMVAL[it])
        w(e, u, " HRVAL   = ", e.HRVAL[it])
        w(e, u, " ")


def efectivos_ini(e, l_plume):
    """AERCALC / VOLCALC: parámetros efectivos iniciales del penacho coherente o del meandro."""
    u = e.DBGUNT
    wf(e, u, "(//,'SRCID: ', A8)", fx(e.SRCID[e.ISRC], 12))
    comp = "COHERENT PLUME COMPONENT" if l_plume else "MEANDER COMPONENT"
    wf(e, u, "(//,'" + comp + "',/,5X,'Initial effective parameters for ','stable or direct convective ',"
             "'plume:',//,5x,'Ueff = ',F7.2,' m/s; ','SVeff = ',F7.2,' m/s; SWeff = ',F7.2,' m/s.',/)",
       e.UEFF, e.SVEFF, e.SWEFF)


def area_efectivos_ini(e):
    """ACALC: parámetros efectivos iniciales del área."""
    wf(e, e.DBGUNT, "(//,'AERMOD AREA SOURCE COMPONENT',/,5X,'Initial effective parameters for ',"
                    "'stable or direct convective ','plume:',//,5x,'Ueff = ',F7.2,' m/s; ','SVeff = ',F7.2,"
                    "' m/s; SWeff = ',F7.2,' m/s.',/)", e.UEFF, e.SVEFF, e.SWEFF)


def aer_pchi_conc(e, ityp, adj, aerout):
    wf(e, e.DBGUNT, "(/,'ITYP = ',I2,' - CONC:',/,'AEROUT(ITYP) = ADJ * EMIFAC(ITYP) * (FOPT * ',"
                    "'CWRAP + (1.0 -FOPT) * CLIFT) * D',/,' ADJ   = ',G16.8,/,' FOPT  = ',G16.8,/,"
                    "' CWRAP = ',G16.8,/,' CLIFT = ',G16.8,/,' D     = ',G16.8,/,' AEROUT(ITYP) = ',G16.8,/)",
       ityp, adj, e.FOPT, e.CWRAP, e.CLIFT, e.D, aerout)


def aer_pchi_dep(e, tipo, ityp, adj, a, b, c, aerout):
    """AER_PCHI: DEPOS (adj, vdinp, dryflux, wetflux), DDEP (adj, vdinp, dryflux) o WDEP (adj,
    zsubp, prate, wetflux)."""
    if tipo == "DEPOS":
        wf(e, e.DBGUNT, "(/,'ITYP = ',I2,' - DEPOS:',/,' ADJ     = ',G16.8,/,' VDINP   = ',G16.8,/,"
                        "' DRYFLUX = ',G16.8,/,' WETFLUX = ',G16.8,/,' AEROUT(ITYP) = ',G16.8,/)",
           ityp, adj, a, b, c, aerout)
    elif tipo == "DDEP":
        wf(e, e.DBGUNT, "(/,'ITYP = ',I2,' - DDEP:',/,' ADJ     = ',G16.8,/,' VDINP   = ',G16.8,/,"
                        "' DRYFLUX = ',G16.8,/,' AEROUT(ITYP) = ',G16.8,/)", ityp, adj, a, b, aerout)
    else:
        wf(e, e.DBGUNT, "(/,'ITYP = ',I2,' - WDEP:',/,' ADJ     = ',G16.8,/,' ZSUBP   = ',G16.8,/,"
                        "' PRATE   = ',G16.8,/,' WETFLUX = ',G16.8,/,' AEROUT(ITYP) = ',G16.8,/)",
           ityp, adj, a, b, c, aerout)


def debout(e):
    """DEBOUT: componentes del penacho en el receptor."""
    u = e.DBGUNT
    qe = e.QTK * e.EMIFAC[1]
    chid = chin = chi3 = 0.0
    if e.STABLE or (e.UNSTAB and e.HS >= e.ZI):
        chid = e.HRVAL[1]
    elif e.UNSTAB:
        chid = (qe * (1.0 - e.PPF) / e.UEFFD) * (e.FSUBYD * e.FSUBZD)
        chin = (qe * (1.0 - e.PPF) / e.UEFFN) * (e.FSUBYN * e.FSUBZN)
        if e.PPF > 0.0 and e.UEFF3 > 0.0:
            chi3 = (qe * e.PPF / e.UEFF3) * (e.FSUBY3 * e.FSUBZ3)
        else:
            chi3 = 0.0
    wf(e, u, "( 1X )")
    wf(e, u, "('  REC   REC-X    REC-Y    REC-Z    HILLHT  FLAGPL    ','DEL-X   DEL-Y  DEL-Z   HCRIT   PHEE  "
             "FOPT  DECAY   CWRAP ','     CLIFT      AERVAL    PRMVAL',/,'    #    (M)      (M)      (M)      "
             "(M)     (M)       (M)   ','  (M)    (M)     (M)                       (UG/M3)    ',"
             "'(UG/M3)    (UG/M3)',//,I5,F9.1,F10.1,F8.1,F9.1,F8.1,F10.1,F8.1,F7.1,F7.1,F7.3,F6.3,F7.3,4E11.4,/)",
       e.IREC, e.XR, e.YR, e.ZELEV, e.ZHILL, e.ZFLAG, e.X, e.Y, e.ZELEV - e.ZS, e.HCRIT, e.PHEE, e.FOPT, e.D,
       e.CWRAP * e.EMIFAC[1], e.CLIFT * e.EMIFAC[1], e.AERVAL[1], e.PRMVAL[1])
    wf(e, u, "('   PLUME   PART.  SOURCE  PLUME  <----- SIGMA-Y TERMS --','--->   GAUSS.     <--------- SIGMA-Z "
             "TERMS -------->   GAUSS.',/,' COMPONENT PEN.     Q     HEIGHT  AMB.  DOWNW.  BUOY.  TO','TAL   "
             "HORIZ.      AMB.  DOWNW.  BUOY.  SURF.  TOTAL   VERT.  ','       CHI ',/,'   TYPE    FRAC.   "
             "(G/S)   (M)    (M)    (M)     (M)    ','(M)    TERM        (M)    (M)     (M)    (M)    (M)    "
             "TERM ','       (UG/M3)',/)")
    if e.STABLE or (e.UNSTAB and e.HS >= e.ZI):
        wf(e, u, "(' GAUSSIAN ',F6.3,F9.2,F7.1,4F7.1,E11.4,2X,5F7.1,E11.4,E12.4)", e.PPF, e.QTK, e.HE, e.SYAMB,
           e.VSIGY, e.SYB, e.SY, e.FSUBY, e.SZAMB, e.VSIGZ, e.SZB, e.SZSURF, e.SZ, e.FSUBZ, chid)
    elif e.UNSTAB:
        q1 = (1.0 - e.PPF) * e.QTK
        if q1 > 0.0:
            wf(e, u, "(' DIRECT #1',F6.3,F9.2,F7.1,4F7.1,13X,5F7.1)", e.PPF, q1, e.HED1, e.SYAMB, e.VSIGY,
               e.SYB, e.SY, e.SZAD1, e.VSZD1, e.SZBD, e.SZSURF, e.SZD1)
            wf(e, u, "(' DIRECT #2',6X,F9.2,F7.1,4F7.1,E11.4,2X,5F7.1,E11.4,E12.4)", q1, e.HED2, e.SYAMB,
               e.VSIGY, e.SYB, e.SY, e.FSUBYD, e.SZAD2, e.VSZD2, e.SZBD, e.SZSURF, e.SZD2, e.FSUBZD, chid)
            wf(e, u, "(' INDIRECT1',F6.3,F9.2,F7.1,4F7.1,13X,4F7.1,F7.1)", e.PPF, q1, e.HEN1, e.SYAMB,
               e.VSIGY, e.SYB, e.SY, e.SZAN1, e.VSZN1, e.SZBN, e.SZSURF, e.SZN1)
            wf(e, u, "(' INDIRECT2',6X,F9.2,F7.1,4F7.1,E11.4,2X,5F7.1,E11.4,E12.4)", q1, e.HEN2, e.SYAMB,
               e.VSIGY, e.SYB, e.SY, e.FSUBYN, e.SZAN2, e.VSZN2, e.SZBN, e.SZSURF, e.SZN2, e.FSUBZN, chin)
        if e.PPF * e.QTK > 0.0:
            wf(e, u, "(' PENETRATE',F6.3,F9.2,F7.1,4F7.1,E11.4,2X,3F7.1,7X,F7.1,E11.4,E12.4,/)", e.PPF,
               e.PPF * e.QTK, e.HE3, e.SYA3, e.VSY3, e.SYB3, e.SY3, e.FSUBY3, e.SZA3, e.VSZ3, e.SZB3, e.SZ3,
               e.FSUBZ3, chi3)


def meandr(e, svef, uef, umean, ttrav, tran, totkin, sigran, fran):
    """MEANDR: términos del meandro (escritura dirigida por lista)."""
    u = e.DBGUNT
    w(e, u)
    w(e, u, "SVEF, UEF, UMEAN:")
    w(e, u, svef, uef, umean)
    w(e, u)
    w(e, u, "DISTR, TTRAV, TRAN:")
    w(e, u, e.DISTR, ttrav, tran)
    w(e, u)
    w(e, u, "TOTKIN, SIGRAN, FRAN:")
    w(e, u, totkin, sigran, fran)
    w(e, u, " ")


# --------------------------------------------------------------------- IBLVAL (DBGUNT)
def ibl_ini(e, cual):
    """IBLVAL: parámetros efectivos iniciales (estable, directo o penetrado)."""
    u = e.DBGUNT
    if cual == "S":
        wf(e, u, "(5X,'Initial effective parameters ','for the stable ','plume:',//,5x,'Ueff = ',F7.2,' m/s; ',"
                 "'SVeff = ',F7.2,' m/s; SWeff = ',F7.2,' m/s.',/)", e.UEFF, e.SVEFF, e.SWEFF)
    elif cual == "D":
        wf(e, u, "(5X,'Initial effective parameters ','for the direct convective ','plume:',//,5x,'UeffD = ',"
                 "F7.2,' m/s; ','SVeffD = ',F7.2,' m/s; SWeffD = ',F7.2,' m/s.',/)", e.UEFFD, e.SVEFFD, e.SWEFFD)
    else:
        wf(e, u, "(5X,'Penetration fraction = ',f6.3,/,5X,'Initial effective parameters ','for the penetrated ',"
                 "'plume:',//,5x,'Ueff3 = ',F7.2,' m/s; ','SVeff3 = ',F7.2,' m/s; SWeff3 = ',F7.2,' m/s.',/)",
           e.PPF, e.UEFF3, e.SVEFF3, e.SWEFF3)


def ibl_hbp(e):
    wf(e, e.DBGUNT, "(1X,'CONVN= ',F10.2,' MECHN= ',F10.2,' ZIN= ',F10.2,'ZIAVG= ',F10.2,'HE3= ',F10.2)",
       e.ZICONVN, e.ZIMECHN, e.ZIN, e.ZIAVG, e.HE3)


def ibl_capa(e, cual, centro, sz, zlo, zhi):
    """IBLVAL: capa sobre la que se promedian los parámetros (Stable / Penetrated / Direct)."""
    if e.EVONLY:
        etq, num = "EVENT", e.IEVENT
    else:
        etq, num = "receptor", e.IREC
    wf(e, e.DBGUNT, "(5X,'" + cual + " plume calculation',' for " + etq + " # ',I3,//,5x,"
                    "'Height of plume center of mass = ',f6.1,' m; Sigma-z estimate = ',f11.1,' m; ',"
                    "'Receptor height = ',f6.1,' m; ',/,5x,'New ','effective parameters are averaged between ',"
                    "f6.1,' and ',F6.1,' meters.',/)", num, centro, sz, e.ZRT, zlo, zhi)


def ibl_fin(e, cual):
    """IBLVAL: parámetros efectivos finales (estable, penetrado o directo)."""
    u = e.DBGUNT
    if cual == "S":
        wf(e, u, "(5X,'Effective parameters for stable ','plume:',//,5x,'Ueff = ',F7.2,' m/s; ','SVeff = ',F7.2,"
                 "' m/s; SWeff = ',F7.2,' m/s.',/)", e.UEFF, e.SVEFF, e.SWEFF)
    elif cual == "P":
        wf(e, u, "(5X,'Effective parameters for penetrated ','plume:',//,5x,'Ueff3 = ',F7.2,' m/s; ',"
                 "'SVeff3 = ',F7.2,' m/s; SWeff3 = ',F7.2,' m/s.',/)", e.UEFF3, e.SVEFF3, e.SWEFF3)
    else:
        wf(e, u, "(5X,'Effective parameters for direct ','plume:',//,5x,'UeffD = ',F7.2,' m/s; ','SVeffD = ',"
                 "F7.2,' m/s; SWeffD = ',F7.2,' m/s.',/)", e.UEFFD, e.SVEFFD, e.SWEFFD)


# ---------------------------------------------------------------------- METDEB (DBMUNT)
def metdeb(e):
    """METDEB: meteorología de la hora (cabecera una vez por fuente y hora) y parámetros efectivos
    en cada receptor."""
    from .formato import nint
    u = e.DBMUNT
    if e.METHDR:
        wf(e, u, "( 1X, 80('-'),//,'  SURFACE AND PROFILE MET DATA:',/,T48, 'MONIN-     SFC',/,T17,"
                 "'MIXING   TEMP                  OBUKHOV   ROUGH.',/,T17,"
                 "'HEIGHT   @ HS    U*      W*    LENGTH    LENGTH    THSTAR',/,'  YR  MO DA HR',"
                 "'    (M)    (K)   (M/S)   (M/S)    (M)       (M)',//,1X,I4,3I3,2X,F6.1,2X,F5.1,1X,F6.3,1X,F7.3,"
                 "2X,F7.1,3X,F7.3,3X,F7.4///,' <--AVG: SFC TO ZI---> <--------VALUE AT ZI-------->',/,"
                 "'   U    SIG-V  SIG-W      U    SIG-V  SIG-W   VPTG',/,"
                 "' (M/S)  (M/S)  (M/S)    (M/S)  (M/S)  (M/S)   (K/M)',//,1X,F5.2,2(2X,F5.2),3X,F5.2,2X,F5.2,2X,"
                 "F5.2,1X,F7.4,//)", e.IYR, e.IMONTH, e.IDAY, e.IHOUR, e.ZI, e.TA, e.USTAR, e.WSTAR, e.OBULEN,
           e.SFCZ0, e.THSTAR, e.UAVG, e.SVAVG, e.SWAVG, e.UATZI, e.SVATZI, e.SWATZI, e.VPTGZI)
        wf(e, u, "(5X,' GRID     WIND    WIND                    POT.',/,5X,'HEIGHT    DIR.    SPEED   SIG-V   "
                 "SIG-W   TEMP.','  VPTG',/,5X,' (M)     (DEG)    (M/S)   (M/S)   (M/S)    (K)  ',' (K/M)',/)")
        out = []
        for i in range(e.MXGLVL, 0, -1):
            out += fwrite("(I4,F7.1,2X,F6.1,2X,F7.2,1X,F7.2,1X,F7.2,1X,F6.2,1X,F9.6)", i, e.GRIDHT[i],
                          e.GRIDWD[i], e.GRIDWS[i], e.GRIDSV[i], e.GRIDSW[i], e.GRIDPT[i], e.GRIDTG[i])
        e.w(u, out)
        wf(e, u, "(//,1X, '            <-STABLE/DIRECT EFF. VALUES-> ','<-INDIRECT EFF. VALUES-> <-PENETRATED EFF. "
                 "VALUES->',/,' RECEPT  DIST.    U    SIG-V  SIG-W   ','       U    SIG-V  SIG-W          U    "
                 "SIG-V  SIG-W',/)")
        e.METHDR = False
    if abs(e.X) > 999999.0:
        ndist = -999999 if e.X < 0.0 else 999999
    else:
        ndist = nint(e.X)
    if e.STABLE or (e.UNSTAB and e.HS >= e.ZI):
        wf(e, u, "(I5,1X,I7,1X,3(2X,F5.2))", e.IREC, ndist, e.UEFF, e.SVEFF, e.SWEFF)
    elif e.PPF >= 1.0:
        wf(e, u, "(I5,1X,I7,1X,54X,3(2X,F5.2))", e.IREC, ndist, e.UEFF3, e.SVEFF3, e.SWEFF3)
    elif e.PPF <= 0.0:
        wf(e, u, "(I5,1X,I7,1X,2(3(2X,F5.2),6X))", e.IREC, ndist, e.UEFFD, e.SVEFFD, e.SWEFFD, e.UEFFN,
           e.SVEFFN, e.SWEFFN)
    else:
        wf(e, u, "(I5,1X,I7,1X,3(3(2X,F5.2),6X))", e.IREC, ndist, e.UEFFD, e.SVEFFD, e.SWEFFD, e.UEFFN,
           e.SVEFFN, e.SWEFFN, e.UEFF3, e.SVEFF3, e.SWEFF3)


# ======================================================================= DEPOS (DBGUNT, GDEP, PDEP)
def vdp1_ent(e):
    """VDP1: datos de partículas de cada fuente (MODEL)."""
    u = e.DBGUNT
    w(e, u)
    w(e, u, "SUBR. VDP1 -- INPUTS")
    w(e, u)
    for i in range(1, e.NUMSRC + 1):
        n = int(e.INPD[i])
        w(e, u, "SOURCE          = ", i)
        w(e, u, "INPD            = ", n)
        if n > 0:
            w(e, u, "APDIAM (um)     = ", *[float(e.APDIAM[k, i]) for k in range(1, n + 1)])
            w(e, u, "APHI            = ", *[float(e.APHI[k, i]) for k in range(1, n + 1)])
            w(e, u, "APDENS(g/cm**3) = ", *[float(e.APDENS[k, i]) for k in range(1, n + 1)])
        w(e, u)


def vdp1_gas(e):
    u = e.DBGUNT
    ns = e.NUMSRC
    w(e, u)
    w(e, u, "SUBR. VDP1 -- OUTPUT for GASES")
    w(e, u, "PDIFF (m**2/s)  = ", *[float(e.PDIFF[n]) for n in range(1, ns + 1)])
    w(e, u, "PDIFFW(m**2/s)  = ", *[float(e.PDIFFW[n]) for n in range(1, ns + 1)])
    w(e, u, "RCLI(s/m)       = ", *[float(e.RCLI[n]) for n in range(1, ns + 1)])
    w(e, u, "ZRDEP (m)       = ", e.ZRDEP)


def vdp1_part(e):
    u = e.DBGUNT
    w(e, u)
    w(e, u, "SUBR. VDP1 -- OUTPUT for PARTICLES")
    w(e, u)
    for i in range(1, e.NUMSRC + 1):
        n = int(e.INPD[i])
        w(e, u, "SOURCE          = ", i)
        w(e, u, "AVGRAV (m/s)    = ", *[float(e.AVGRAV[k, i]) for k in range(1, n + 1)])
        w(e, u, "ATSTOP (s)      = ", *[float(e.ATSTOP[k, i]) for k in range(1, n + 1)])
        w(e, u, "VAIRMS (m**2/s) = ", e.VAIRMS)
        w(e, u, "ZRDEP (m)       = ", e.ZRDEP)
        w(e, u, "VDPHOR (m/s)    = ", e.VDPHOR)
        w(e, u)


def vdp_part(e, ra, rds):
    """VDP: resistencias y velocidades de deposición de partículas del método 1 (MODEL)."""
    u = e.DBGUNT
    npd = e.NPD
    w(e, u)
    w(e, u, "RA (s/m)    = ", ra)
    w(e, u, "RD (s/m)    = ", *rds[1:npd + 1])
    w(e, u, "VDEP (m/s)  = ", *[float(e.VDEP[n]) for n in range(1, npd + 1)])


def vdp_fin(e, ra, rb, rc, rds, rp):
    """VDP: resistencias y velocidades a GDEP.DAT (gases) y PDEP.DAT (partículas)."""
    if e.LDGAS and e.NPD == 0:
        wf(e, e.GDEPDBG, "(1x,i8,1x,i6,4(2x,e12.6))", e.KURDAT, e.ISRC, ra, rb, rc, e.VDEPG)
    if e.LDPART and not e.L_METHOD2[e.ISRC]:
        for i in range(1, e.NPD + 1):
            wf(e, e.PDEPDBG, "(1x,i8,1x,i6,2x,i3,'  METHOD_1 ',4(2x,e12.6))", e.KURDAT, e.ISRC, i, ra, rds[i],
               e.VGRAV[i], e.VDEP[i])
    elif e.LDPART and e.L_METHOD2[e.ISRC]:
        wf(e, e.PDEPDBG, "(1x,i8,1x,i6,4x,'-  METHOD_2 ',4(2x,e12.6))", e.KURDAT, e.ISRC, ra, rp, e.VGRAV[1],
           e.VDEP[1])


def scavrat_ent(e):
    u = e.DBGUNT
    w(e, u)
    w(e, u, "SUBR. SCAVRAT -- Inputs")
    w(e, u, "IPCODE               = ", int(e.IPCODE))
    w(e, u, "PRATE (mm/hr)        = ", e.PRATE)
    w(e, u, "TA (deg K)           = ", e.TA)
    w(e, u, "NPD                  = ", e.NPD)
    w(e, u)


def scavrat_res(e):
    u = e.DBGUNT
    npd = e.NPD
    w(e, u, "SUBR. SCAVRAT -- Results")
    if npd == 0:
        w(e, u, "GSCVRT (1/s)= ", e.GSCVRT)
    elif npd > 0:
        w(e, u, "PSCVRT (1/s)= ", *[float(e.PSCVRT[n]) for n in range(1, npd + 1)])
        w(e, u, "COLL. EFF.  = ", *[float(e.ECOLL[n]) for n in range(1, npd + 1)])
        w(e, u, "WASHOUT COEF= ", *[float(e.WASHOUT[n]) for n in range(1, npd + 1)])
    w(e, u)


# ===================================================================================== AWMADW
def awma_pcalc(e):
    u = e.AWMADWDBUNT
    w(e, u, "========================================")
    w(e, u, " PCALC: YYMMDDHH ", e.KURDAT, "  Source  ", fx(e.SRCID[e.ISRC], 12))


def awma_receptor(e, irec):
    w(e, e.AWMADWDBUNT, "  Receptor  ", irec)


# ======================================================================= PRIME (PRMDBUNT / dbgunt)
def wu(e, u, *items):
    """WRITE(u,*) a una unidad que puede no estar abierta (Intel crea entonces fort.N)."""
    if u not in e.U:
        e.abrir_salida(u, "fort.%d" % u)
    e.U[u].w(lwrite(*items))


def wfu(e, u, fmt, *items):
    if u not in e.U:
        e.abrir_salida(u, "fort.%d" % u)
    e.U[u].w(fwrite(fmt, *items))


def numrise_paso(e, u, znf, ds0):
    wu(e, u, "NUMRISE - initial step reset")
    wfu(e, u, "(1x,a,3(f12.4,2x))", "znf,ds0,ds  :", znf, ds0, e.P.DS)


def numrise_traza(e, u, nnp, zc, ua, ra, ta, dudz, dpdz, dzds, ipositn, h):
    p = e.P
    if nnp % 1000 == 1:
        wfu(e, u, "(/3x,'NNP',7x,'X',6x,'Y',6x,'Z',6x,'R',6x,'U',5x,'V',6x,'W',5x,'USC',5x,'PHI',4x,'DEN',3x,'TP',"
                  "5x,'UA',5x,'RA',4x,'TA',6x,'DUDZ',4x,'DPDZ',3x,'DZDS',3x,'DYDS',1x,'IPOS',1x,'DELTAZ')")
    wfu(e, u, "(1x,i5,f9.2,3f7.2,4f7.2,f8.4,f6.3,f7.2,f6.2,f7.3,f7.2,f8.3,f8.3,2f7.3,i5,f7.3)", nnp, p.X, p.Y,
        zc, p.R, p.U, p.V, p.W, p.USC, p.PHI, p.DEN, p.TP, ua, ra, ta, dudz, dpdz, dzds, 0.0, ipositn, zc - h)


def numrise_dfsn_a(e, u, zc, xb, szi, syi):
    p = e.P
    wu(e, u, " ")
    wu(e, u, "NUMRISE call to WAKE_DFSN -- A")
    wfu(e, u, "(1x,a,4(f12.5,2x))", "x,y,z,z+zcum: ", p.X, p.Y, p.Z, zc)
    wfu(e, u, "(1x,a,3(f12.5,2x))", "ds,u,w      : ", p.DS, p.U, p.W)
    wfu(e, u, "(1x,a,2(f12.5,2x))", "xb,phi      : ", xb, p.PHI)
    wfu(e, u, "(1x,a,2(f12.5,2x))", "szi,syi     : ", szi, syi)


def numrise_dfsn_b(e, u, yfin, ztin, xbi, szi, syi):
    p = e.P
    wu(e, u, " ")
    wu(e, u, "NUMRISE call to WAKE_DFSN -- B")
    wfu(e, u, "(1x,a,4(f12.5,2x))", "x,y,z,z+zcum:", p.X, yfin, p.Z, ztin)
    wfu(e, u, "(1x,a,2(f12.5,2x))", "xb,phi      :", xbi, p.PHI)
    wfu(e, u, "(1x,a,2(f12.5,2x))", "szi,syi     :", szi, syi)


def numrise_error(e, u, nn, mxnw):
    """NUMRISE con NN > MXNW: el mensaje se escribe siempre (aunque no haya depuración)."""
    wu(e, u, " ")
    wu(e, u, "Error in Subr. NUMRISE -- NN too large:")
    wu(e, u, "                          NN   = ", nn)
    wu(e, u, "                          MXNW = ", mxnw)
    wu(e, u, " ")
    wu(e, u, "Source parameters may be suspect.")
    wu(e, u, "Do not use Clearinghouse procedure for ")
    wu(e, u, "capped/horizontal stacks with PRIME!")
    wu(e, u, " ")


def numrise_fin(e, u, texit, fb, fm, xmax, xfin0, x15r, xfin, yfin, zfin, h, rfin, zcumul):
    wu(e, u)
    wu(e, u, "      Initial Plume Temperature = ", texit)
    wu(e, u, "             Buoyancy flux (FB) = ", fb)
    wu(e, u, "             Momentum flux (FM) = ", fm)
    wu(e, u, "  Neutral dist. to final rise   = ", xmax)
    wu(e, u, "  Calc distance to final rise   = ", xfin0)
    wu(e, u, "Distance from final rise to 15R = ", x15r)
    wu(e, u, "Total distance tabulated (XFIN) = ", xfin)
    wu(e, u, "    Final Y displacement (YFIN) = ", yfin)
    wu(e, u, "      Final plume height (ZFIN) = ", zfin)
    wu(e, u, "     Final plume rise (DELZFIN) = ", zfin - h)
    wu(e, u, "      Final plume radius (RFIN) = ", rfin)
    wu(e, u, "Cumul. streamline adj. (ZCUMUL) = ", zcumul)
    wu(e, u)
    wu(e, u, "    Fraction of plume in CAVITY = ", e.P.FQCAV)
    wu(e, u)


def numrise_tray(e, u, despues, xtr, ytr, ztr, rtr, ntr):
    if despues:
        wfu(e, u, "('  -- Trajectory arrays after CALL WAKE_DFSN2')")
    else:
        wfu(e, u, "('  -- Trajectory arrays before CALL WAKE_DFSN2')")
    wfu(e, u, "(/4x,'I',10x,'XTR',8x,'YTR',8x,'ZTR',8x,'RTR',8x,'sz?'/)")
    out = []
    for i in range(1, ntr + 1):
        out += fwrite("(i5,3x,5(f10.4,1x))", i, xtr[i], ytr[i], ztr[i], rtr[i], rtr[i] * 0.8)
    if u not in e.U:
        e.abrir_salida(u, "fort.%d" % u)
    e.U[u].w(out)
    wu(e, u)


def wake_scales(e, u, kurdat):
    p = e.P
    wu(e, u)
    wu(e, u, "YR/MN/DY/HR:      ", kurdat)
    wu(e, u)
    wu(e, u, "WAKE_SCALES inputs: ")
    wu(e, u, "   HB    = ", p.HB, " (m)")
    wu(e, u, "   WB    = ", p.WB, " (m)")
    wu(e, u, "   LB    = ", p.XLB, " (m)")
    wu(e, u)
    wu(e, u, "WAKE_SCALES output: ")
    wu(e, u, "   Scale length (R)               = ", p.RB)
    wu(e, u, "   Max. cavity height (HR)        = ", p.HR)
    wu(e, u, "   Length of downwind cavity (LR) = ", p.XLR)
    wu(e, u, "   Length of roof cavity (LC)     = ", p.XLC)


def wake_dfsn_ambiente(e, u, dfsn2, xaz, xay, xi, awma=False):
    """WAKE_DFSN(2): el penacho no se ve alterado por la turbulencia de la estela."""
    p = e.P
    nom = "----- WAKE_DFSN2:       NWAK = " if dfsn2 else "----- WAKE_DFSN:        NWAK = "
    wu(e, u, " ")
    wu(e, u, nom, p.NWAK)
    wu(e, u, "Z-dispersion reaches ambient at: ", xaz + p.XBADJ)
    wu(e, u, "Y-dispersion reaches ambient at: ", xay + p.XBADJ)
    if dfsn2:
        wu(e, u, "xadj, yadj, xi        (m)    = ", p.XBADJ, p.YBADJ, xi)
    else:
        wfu(e, u, "(1x,a,2x,3(f14.5,2x))", "xadj, yadj, xi  (m) = ", p.XBADJ, p.YBADJ, xi)
    wu(e, u, "Plume NOT altered by wake turbulence!")
    wu(e, u)


def wake_dfsn_fin(e, u, ldbhr, xaz, xay, xi, xbc, xdc, lwak, lcav, np_, nws, ncs):
    """WAKE_DFSN: resumen y tablas de la estela y de la cavidad (DEBUG de PRIME y AWMADW). NPW y
    NPC solo se calculan con estela/cavidad; si no, el original imprime el valor que quedó de la
    llamada anterior (se emula)."""
    p = e.P
    if lwak:
        e._prm_npw = np_ - nws
    if lcav:
        e._prm_npc = np_ - ncs
    npw = getattr(e, "_prm_npw", 0)
    npc = getattr(e, "_prm_npc", 0)
    distc = p.XLB + p.XBADJ
    if ldbhr:
        wu(e, u)
        wu(e, u, "----- WAKE_DFSN:        NWAK = ", p.NWAK)
        wu(e, u, "Z-dispersion reaches ambient at: ", xaz + p.XBADJ)
        wu(e, u, "Y-dispersion reaches ambient at: ", xay + p.XBADJ)
        wfu(e, u, "(1x,a,2x,3(f14.5,2x))", "xadj, yadj, xi  (m) = ", p.XBADJ, p.YBADJ, xi)
        wfu(e, u, "(1x,a,2x,3(f14.5,2x))", "xbc, distc, xdc (m) = ", xbc, distc, xdc)
        wu(e, u, "lwak,  nws,  npw    = ", bool(lwak), nws, npw)
        wu(e, u, "lcav,  ncs,  npc    = ", bool(lcav), ncs, npc)
        wu(e, u)
        wfu(e, u, "(/4x,'I',9x,'XWAK',6x,'SZWAK',6x,'SYWAK',6x,'DRWAK',/)")
        out = []
        for i in range(1, p.NWAK + 1):
            out += fwrite("(i5,3x,4(f10.4,1x))", i, p.XWAK[i], p.SZWAK[i], p.SYWAK[i], p.DRWAK[i])
        e.U[u].w(out)
        wu(e, u)
        wfu(e, u, "(/4x,'I',9x,'XCAV',6x,'SZCAV',6x,'SYCAV',/)")
        out = []
        for i in range(1, p.NCAV + 1):
            out += fwrite("(i5,3x,3(f10.4,1x))", i, p.XCAV[i], p.SZCAV[i], p.SYCAV[i])
        e.U[u].w(out)
        wu(e, u)
    if e.AWMADWDBG:
        a = e.AWMADWDBUNT
        w(e, a)
        w(e, a, "----- WAKE_DFSN:        NWAK = ", p.NWAK)
        w(e, a, "Z-disp reaches ambient at xaz+xbadj: ", xaz + p.XBADJ)
        w(e, a, "Y-disp reaches ambient at xay+xbadj: ", xay + p.XBADJ)
        wf(e, a, "(1x,a,2x,3(f14.5,2x))", "xadj, yadj, xi  (m) = ", p.XBADJ, p.YBADJ, xi)
        wf(e, a, "(1x,a,2x,3(f14.5,2x))", "xbc, distc, xdc (m) = ", xbc, distc, xdc)
        w(e, a, "lwak,  nws,  npw    = ", bool(lwak), nws, npw)
        w(e, a, "lcav,  ncs,  npc    = ", bool(lcav), ncs, npc)
        w(e, a)


def wake_dfsn2_ambiente_awma(e, xaz, xay, xi):
    p = e.P
    a = e.AWMADWDBUNT
    w(e, a, " ")
    w(e, a, "----- WAKE_DFSN2:       NWAK = ", p.NWAK)
    w(e, a, "Z-dispersion reaches ambient at: ", xaz + p.XBADJ)
    w(e, a, "Y-dispersion reaches ambient at: ", xay + p.XBADJ)
    w(e, a, "xadj, yadj, xi        (m)    = ", p.XBADJ, p.YBADJ, xi)
    w(e, a, "Plume NOT altered by wake turbulence!")
    w(e, a)


def wake_dfsn2_awma_ini(e):
    a = e.AWMADWDBUNT
    w(e, a, " ")
    w(e, a, "----- WAKE_DFSN2:")
    w(e, a, "       xaz  = distance (m) from upwind ")
    w(e, a, "              bldg wall at which wake ")
    w(e, a, "              turbulence Iz = ambient")
    w(e, a, "       zxaz = plume height at transition")
    w(e, a, "              points from plume ht array")


def wake_dfsn2_fin(e, u, ldbhr):
    p = e.P
    if ldbhr:
        wu(e, u)
        wu(e, u, "----- WAKE_DFSN2:")
        wu(e, u, "PRIMARY SOURCE:")
        wu(e, u, " Lateral virtual source sigma,  VSIGY (m)  = ", p.VSIGY)
        wu(e, u, " Vertical virtual source sigma, VSIGZ (m)  = ", p.VSIGZ)
        wu(e, u, "CAVITY SOURCE:")
        wu(e, u, " Lateral virtual source sigma,  VSIGYC (m) = ", p.VSIGYC)
        wu(e, u, " Vertical virtual source sigma, VSIGZC (m) = ", p.VSIGZC)
        wu(e, u)
    if e.AWMADWDBG:
        a = e.AWMADWDBUNT
        w(e, a)
        w(e, a, "----- WAKE_DFSN2:")
        w(e, a, "PRIMARY SOURCE:")
        w(e, a, " Lateral virtual source sigma,  ", "VSIGY (m)  = ", p.VSIGY)
        w(e, a, " Vertical virtual source sigma, ", "VSIGZ (m)  = ", p.VSIGZ)
        w(e, a, "CAVITY SOURCE:")
        w(e, a, " Lateral virtual source sigma,  ", "VSIGYC (m) = ", p.VSIGYC)
        w(e, a, " Vertical virtual source sigma, ", "VSIGZC (m) = ", p.VSIGZC)
        w(e, a)


def wake_xa(e, ambiz, ambiy, farizt, fariyt, xaz, xay):
    u = e.PRMDBUNT
    wu(e, u, " ")
    wu(e, u, "WAKE_XA Calculations:")
    wu(e, u, "ambiz,  ambiy  = ", ambiz, ambiy)
    wu(e, u, "farizt, fariyt = ", farizt, fariyt)
    wu(e, u, "xaz,    xay    = ", xaz, xay)


def wake_fqc(e, u, xbi, xbstart, xbend, xstep, nstep, fractz0, xb85, xmax, fzmax):
    wu(e, u)
    wu(e, u, "WAKE_FQC:")
    wfu(e, u, "(a,2x,3(f12.5,2x))", "xbi, xbstart, xbend   = ", xbi, xbstart, xbend)
    wfu(e, u, "(a,2x,f12.5,I14,2x,f12.5)", "xstep, nstep, fractz0 = ", xstep, nstep, fractz0)
    wfu(e, u, "(a,2x,2(f12.5,2x))", "xb85,  xmax           = ", xb85, xmax)
    wfu(e, u, "(a,2x,2(f12.5,2x))", "fqcav, fzmax          = ", e.P.FQCAV, fzmax)
    wu(e, u)


def prmcalc_efectivos(e, zlo, zhi):
    u = e.PRMDBUNT
    wu(e, u, "PRIME Effective Parameters: ")
    if e.L_AWMA_UTURB or e.L_AWMA_UTURBHX:
        wu(e, u, "  AWMAUturb/HX applied to eff params")
    wu(e, u, "  ZLO, ZHI     = ", zlo, zhi)
    wu(e, u, "  SWEFF, SVEFF = ", e.SWEFF, e.SVEFF)
    wu(e, u, "  UEFF,  TGEFF = ", e.UEFF, e.TGEFF)


def wake_dbg(e, io, ntr, xtr, ytr, ztr, rtr, nobid, hstack):
    """WAKE_DBG (PRMDELH con PRIMEDBG): tabla de la trayectoria y de la estela."""
    from . import estela_edificio
    estela_edificio.wake_dbg(e, io, ntr, xtr, ytr, ztr, rtr, nobid, hstack)
