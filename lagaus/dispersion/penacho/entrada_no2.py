# -*- coding: utf-8 -*-
"""Traducción de AERMOD 26135 (US EPA, dominio público): entrada de las opciones de química del
NO2 (OLM, PVMRM, ARM2, TTRM, GRSM y PSDCREDIT).

Vía CO (coset.f): O3VAL, NOXVAL, O3FILE, NOXFILE, NO2EQ, NO2STK, ARM2_Ratios, O3VALS, NOXVALS,
O3FILL, NOXFILL, OZON_UNIT, NOX_UNIT, O3SECTOR, NOXSECTOR y las comprobaciones de FINISHED que les
afectan. Vía SO (soset.f): NO2RAT, OLMGRP, PSDGRP y la parte de SRCQA del NO2."""
from .control import dbl, fsplit, i8, sindex
from .estado import ILEN_FLD
from .formato import fc, fwrite

_UNIDADES = ("PPM", "PPB", "UG/M3")

_NMAX = {"ANNUAL": 1, "SEASON": 4, "MONTH": 12, "HROFDY": 24, "WSPEED": 6, "SEASHR": 96,
         "HRDOW": 72, "HRDOW7": 168, "SHRDOW": 288, "SHRDOW7": 672, "MHRDOW": 864,
         "MHRDOW7": 2016}
_DIA_SEMANA = ("HRDOW", "HRDOW7", "SHRDOW", "SHRDOW7", "MHRDOW", "MHRDOW7")


# =================================================================================== vía CO
def cocard(e, k):
    """Ramas de COCARD de las claves del NO2. Devuelve False si la clave no es de las suyas."""
    m = "COCARD"
    qui = e.PVMRM or e.OLM or e.RUNTTRM or e.GRSM
    if k == "OZONEVAL":
        e.ICSTAT[24] += 1
        if qui:
            o3val(e)
        else:
            e.errhdl(e.PATH, m, "E", "600", k)
    elif k == "O3VALUES":
        e.ICSTAT[25] += 1
        if qui:
            o3vals(e)
        else:
            e.errhdl(e.PATH, m, "E", "600", k)
    elif k == "OZONEFIL":
        e.ICSTAT[26] += 1
        if qui:
            o3file(e)
        else:
            e.errhdl(e.PATH, m, "E", "600", k)
    elif k == "OZONUNIT":
        e.ICSTAT[27] += 1
        if e.ICSTAT[27] != 1:
            e.errhdl(e.PATH, m, "E", "135", k)
        elif qui:
            ozon_unit(e)
        else:
            e.errhdl(e.PATH, m, "E", "600", k)
    elif k == "NO2STACK":
        e.ICSTAT[28] += 1
        if e.ICSTAT[28] != 1:
            e.errhdl(e.PATH, m, "E", "135", k)
        elif qui:
            no2stk(e)
        else:
            e.errhdl(e.PATH, m, "E", "600", k)
    elif k == "NO2EQUIL":
        e.ICSTAT[29] += 1
        if e.ICSTAT[29] != 1:
            e.errhdl(e.PATH, m, "E", "135", k)
        elif e.PVMRM or e.OLM or e.RUNTTRM:
            no2eq(e)
        else:
            e.errhdl(e.PATH, m, "E", "142", k)
    elif k == "O3SECTOR":
        e.ICSTAT[31] += 1
        if e.ICSTAT[31] != 1:
            e.errhdl(e.PATH, m, "E", "135", k)
        elif qui:
            o3sector(e)
        else:
            e.errhdl(e.PATH, m, "E", "600", k)
    elif k == "ARMRATIO":
        e.ICSTAT[32] += 1
        if e.ICSTAT[32] != 1:
            e.errhdl(e.PATH, m, "E", "135", k)
        elif e.ARM2:
            arm2_ratios(e)
        else:
            e.errhdl(e.PATH, m, "E", "145", k)
    elif k == "NOXSECTR":
        e.ICSTAT[35] += 1
        if e.ICSTAT[35] != 1:
            e.errhdl(e.PATH, m, "E", "135", k)
        elif e.GRSM:
            noxsector(e)
        else:
            e.errhdl(e.PATH, m, "E", "602", k)
    elif k == "NOXVALUE":
        e.ICSTAT[36] += 1
        if e.GRSM:
            noxval(e)
        else:
            e.errhdl(e.PATH, m, "E", "602", k)
    elif k == "NOX_VALS":
        e.ICSTAT[37] += 1
        if e.GRSM:
            noxvals(e)
        else:
            e.errhdl(e.PATH, m, "E", "602", k)
    elif k == "NOX_UNIT":
        e.ICSTAT[38] += 1
        if e.ICSTAT[38] != 1:
            e.errhdl(e.PATH, m, "E", "135", k)
        elif e.GRSM:
            nox_unit(e)
        else:
            e.errhdl(e.PATH, m, "E", "602", k)
    elif k == "NOX_FILE":
        e.ICSTAT[39] += 1
        if e.GRSM:
            noxfile(e)
        else:
            e.errhdl(e.PATH, m, "E", "602", k)
    else:
        return False
    return True


def _sector_simple(e, m, nombre, nsect):
    """Sector de los campos 3 (SECT1..SECT6) sin comprobar el número de sectores (O3VAL/NOXVAL).
    Devuelve el sector o 0 si hay error."""
    f3 = e.FIELD[3]
    if f3 in ("SECT1", "SECT2", "SECT3", "SECT4", "SECT5", "SECT6"):
        return int(f3[4])
    e.errhdl(e.PATH, m, "E", "203", nombre)
    return 0


def _sector(e, m, nombre, nsects):
    """Sector del campo 3 comprobando que exista (O3FILE, O3VALS, NOXFILE, NOXVALS). Devuelve el
    sector o 0 si hay error."""
    f3 = e.FIELD[3]
    if f3 == "SECT1":
        return 1
    if f3 in ("SECT2", "SECT3", "SECT4", "SECT5") and nsects >= int(f3[4]):
        return int(f3[4])
    if f3 == "SECT6" and nsects == 6:
        return 6
    e.errhdl(e.PATH, m, "E", "203", nombre)
    return 0


def _valor_fondo(e, m, sector_on, lval, back, nombre_sect, aviso_unid, attr_unid, attr_sect,
                 conv):
    """Parte común de O3VAL y NOXVAL. ``conv(valor, unidades)`` pasa a µg/m3. Devuelve el
    sector si se ha leído el valor (0 si hay error)."""
    f = e.FIELD
    if not sector_on:
        if e.IFC <= 2:
            e.errhdl(e.PATH, m, "E", "200", e.KEYWRD)
            return 0
        if e.IFC > 4:
            e.errhdl(e.PATH, m, "E", "202", e.KEYWRD)
            return 0
        if f[3][:4] == "SECT":
            e.errhdl(e.PATH, m, "E", "171", e.KEYWRD)
            return 0
        isect = 1
        i = 3
    else:
        if e.IFC <= 2:
            e.errhdl(e.PATH, m, "E", "200", e.KEYWRD)
            return 0
        if e.IFC == 4:
            if f[3][:4] != "SECT":
                e.errhdl(e.PATH, m, "E", "203", nombre_sect)
                return 0
        elif e.IFC > 5:
            e.errhdl(e.PATH, m, "E", "202", e.KEYWRD)
            return 0
        isect = _sector_simple(e, m, nombre_sect, 0)
        if isect == 0:
            return 0
        i = 4
    setattr(e, attr_sect, isect)
    lval[isect] = True
    e.DNUM, imit = dbl(e, i, e.DNUM)
    if imit != 1:
        e.errhdl(e.PATH, m, "E", "208", e.KEYWRD)
        return 0
    back[isect] = e.DNUM
    if e.IFC == i + 1:
        if f[i + 1] in _UNIDADES:
            setattr(e, attr_unid, fc(f[i + 1], 200))
        else:
            e.errhdl(e.PATH, m, "E", "203", aviso_unid)
    back[isect] = conv(back[isect], getattr(e, attr_unid))
    return isect


def o3val(e):
    """O3VAL: ozono de fondo constante (OZONEVAL), por sector si hay O3SECTOR."""
    m = "O3VAL"

    def conv(v, u):
        if u == "PPB":
            return v * e.O3_PPB
        if u == "PPM":
            return v * e.O3_PPM
        return v

    isect = _valor_fondo(e, m, e.L_O3SECTOR, e.L_O3VAL, e.O3BACK, "O3SECTOR ID", " O3UNITS",
                         "O3VALUNITS", "IO3SECT", conv)
    if isect > 0:
        if e.O3BACK[isect] <= 0.0 or e.O3BACK[isect] > 500.0:
            e.errhdl(e.PATH, m, "W", "320", " O3BACK ")


def noxval(e):
    """NOXVAL: NOx de fondo constante (NOXVALUE), por sector si hay NOXSECTR."""
    m = "NOXVAL"

    def conv(v, u):
        if u == "PPB":
            return v / e.NO2_PPB
        if u == "PPM":
            return v / e.NO2_PPM
        return v

    isect = _valor_fondo(e, m, e.L_NOXSECTOR, e.L_NOXVALUE, e.NOXBACK, "NOXSECTOR ID", " NOXUNITS",
                         "NOXVALUNITS", "INOXSECT", conv)
    if isect > 0:
        if e.NOXBACK[isect] <= 0.0:
            e.errhdl(e.PATH, m, "W", "320", " NOXBACK ")


def _fichero(e, m, sector_on, nsects, nombre_sect):
    """Parte común de O3FILE y NOXFILE. Devuelve (sector, campo del fichero, _abierto) o
    (0, 0, None) si hay error."""
    from .entrada_meteo import _abierto
    if not sector_on:
        if e.IFC <= 2:
            e.errhdl(e.PATH, m, "E", "200", e.KEYWRD)
            return 0, 0, None
        if e.IFC < 3:
            e.errhdl(e.PATH, m, "E", "201", e.KEYWRD)
            return 0, 0, None
        if e.IFC > 5:
            e.errhdl(e.PATH, m, "E", "202", e.KEYWRD)
            return 0, 0, None
        if e.FIELD[3][:4] == "SECT":
            e.errhdl(e.PATH, m, "E", "171", e.KEYWRD)
            return 0, 0, None
        isect = 1
        i = 3
    else:
        if e.IFC <= 2:
            e.errhdl(e.PATH, m, "E", "200", e.KEYWRD)
            return 0, 0, None
        if e.IFC < 4:
            e.errhdl(e.PATH, m, "E", "201", e.KEYWRD)
            return 0, 0, None
        if e.IFC > 6:
            e.errhdl(e.PATH, m, "E", "202", e.KEYWRD)
            return 0, 0, None
        isect = _sector(e, m, nombre_sect, nsects)
        if isect == 0:
            return 0, 0, None
        i = 4
    return isect, i, _abierto


def _formato(e, m, i, isect, formas):
    """Formato del fichero horario (campo I+2) con la cuenta de descriptores de O3FILE/NOXFILE."""
    if e.IFC == i + 2:
        if e.LOCE[i + 2] - e.LOCB[i + 2] <= ILEN_FLD - 1:
            if e.FIELD[i + 2] == "FREE":
                formas[isect] = "FREE"
            else:
                form = fc(e.RUNST1[int(e.LOCB[i + 2]) - 1:int(e.LOCE[i + 2])], 200)
                formas[isect] = form
                num_int = num_real = 0
                for c in form:
                    if c in "Ii":
                        num_int += 1
                    elif c in "FfEeDd":
                        num_real += 1
                if num_int < 1 or num_int > 4:
                    e.errhdl(e.PATH, m, "W", "292", fwrite("('NumInts= ',I3)", num_int)[0])
                if num_real != 1:
                    e.errhdl(e.PATH, m, "W", "292", fwrite("('NumReal= ',I3)", num_real)[0])
        else:
            e.errhdl(e.PATH, m, "E", "292",
                     fwrite("('LEN=',I6)", int(e.LOCE[5] - e.LOCB[5]))[0])
    else:
        formas[isect] = "FREE"


def o3file(e):
    """O3FILE: fichero horario de ozono (OZONEFIL)."""
    m = "O3FILE"
    isect, i, abierto = _fichero(e, m, e.L_O3SECTOR, e.NUMO3SECTS, "O3SECTOR ID")
    if isect == 0:
        return
    e.IO3SECT = isect
    e.L_O3HOURLY = True
    e.L_O3FILE[isect] = True
    if e.LOCE[i] - e.LOCB[i] <= ILEN_FLD - 1:
        e.OZONFL[isect] = fc(e.RUNST1[int(e.LOCB[i]) - 1:int(e.LOCE[i])], 200)
    else:
        e.errhdl(e.PATH, m, "E", "291", i8(ILEN_FLD))
        return
    e.IO3UNT[isect] = 1000 + isect
    u = int(e.IO3UNT[isect])
    if abierto(e, e.OZONFL[isect]) or u in e.U:
        e.errhdl(e.PATH, m, "E", "501", e.KEYWRD)
        return
    try:
        e.abrir_entrada(u, e.OZONFL[isect])
    except OSError:
        e.errhdl(e.PATH, m, "E", "500", fwrite("('O3FILE SECT',I1)", isect)[0])
        return
    e.FUNITARRAY[e.FUNITIND] = u
    e.FNAMEARRAY[e.FUNITIND] = e.OZONFL[isect]
    e.FTYPARRAY[e.FUNITIND] = "OZONEfile"
    e.FUNITIND += 1
    f = e.FIELD
    if i == 3 and e.IFC >= 4:
        if f[4] in _UNIDADES:
            e.O3FILUNITS = fc(f[4], 200)
        else:
            e.errhdl(e.PATH, m, "E", "203", " O3UNITS")
    elif i == 4 and e.IFC >= 5:
        if f[5] in _UNIDADES:
            e.O3FILUNITS = fc(f[5], 200)
        else:
            e.errhdl(e.PATH, m, "E", "203", " O3UNITS")
    else:
        e.O3FILUNITS = "UG/M3"
    _formato(e, m, i, isect, e.O3FORM)


def noxfile(e):
    """NOXFILE: fichero horario de NOx (NOX_FILE)."""
    m = "NOXFILE"
    isect, i, abierto = _fichero(e, m, e.L_NOXSECTOR, e.NUMNOXSECTS, "NOXSECTR ID")
    if isect == 0:
        return
    e.INOXSECT = isect
    e.L_NOXHOURLY = True
    e.L_NOXFILE[isect] = True
    if e.LOCE[i] - e.LOCB[i] <= ILEN_FLD - 1:
        e.NOXFL[isect] = fc(e.RUNST1[int(e.LOCB[i]) - 1:int(e.LOCE[i])], 200)
    else:
        e.errhdl(e.PATH, m, "E", "291", i8(ILEN_FLD))
        return
    e.INOXUNT[isect] = 3000 + isect
    u = int(e.INOXUNT[isect])
    if abierto(e, e.NOXFL[isect]) or u in e.U:
        e.errhdl(e.PATH, m, "E", "501", e.KEYWRD)
        return
    try:
        e.abrir_entrada(u, e.NOXFL[isect])
    except OSError:
        e.errhdl(e.PATH, m, "E", "500", fwrite("('NOXFILE SCT',I1)", isect)[0])
        return
    e.FUNITARRAY[e.FUNITIND] = u
    e.FNAMEARRAY[e.FUNITIND] = e.NOXFL[isect]
    e.FTYPARRAY[e.FUNITIND] = "NOXfile"
    e.FUNITIND += 1
    f = e.FIELD
    if i == 3 and e.IFC >= 4:
        if f[4] in _UNIDADES:
            e.NOXFILUNITS = fc(f[4], 200)
        else:
            e.errhdl(e.PATH, m, "E", "203", "NOXUNITS")
    elif i == 4 and e.IFC >= 5:
        if f[5] in _UNIDADES:
            e.NOXFILUNITS = fc(f[5], 200)
        else:
            e.errhdl(e.PATH, m, "E", "203", "NOXUNITS")
    else:
        e.NOXFILUNITS = "UG/M3"
    _formato(e, m, i, isect, e.NOXFORM)


def no2eq(e):
    """NO2EQ: razón NO2/NOx de equilibrio (NO2EQUIL)."""
    m = "NO2EQ"
    if e.IFC <= 2:
        e.errhdl(e.PATH, m, "E", "200", e.KEYWRD)
        return
    if e.IFC > 3:
        e.errhdl(e.PATH, m, "E", "202", e.KEYWRD)
        return
    e.DNUM, imit = dbl(e, 3, e.DNUM)
    if imit != 1:
        e.errhdl(e.PATH, m, "E", "208", e.KEYWRD)
        return
    e.NO2EQUIL = e.DNUM
    if e.NO2EQUIL < 0.10 or e.NO2EQUIL > 1.0:
        e.errhdl(e.PATH, m, "E", "380", "NO2Equil")


def no2stk(e):
    """NO2STK: razón NO2/NOx en chimenea por defecto para todas las fuentes (NO2STACK)."""
    m = "NO2STK"
    if e.IFC <= 2:
        e.errhdl(e.PATH, m, "E", "200", e.KEYWRD)
        return
    if e.IFC > 3:
        e.errhdl(e.PATH, m, "E", "202", e.KEYWRD)
        return
    e.DNUM, imit = dbl(e, 3, e.DNUM)
    if imit != 1:
        e.errhdl(e.PATH, m, "E", "208", e.KEYWRD)
        return
    e.NO2STACK = e.DNUM
    if e.NO2STACK < 0.0 or e.NO2STACK > 1.0:
        e.errhdl(e.PATH, m, "E", "380", "NO2Stack")
        return
    e.ANO2_RATIO[1:e.NSRC + 1] = e.NO2STACK


def _arm2_rango(e, m, v, nombre):
    if 0.0 < v < 0.50:
        if e.DFAULT:
            e.errhdl(e.PATH, m, "E", "380", nombre)
        else:
            e.errhdl(e.PATH, m, "W", "737", nombre)
    elif 0.90 < v <= 1.0:
        if e.DFAULT:
            e.errhdl(e.PATH, m, "E", "380", nombre)
        else:
            e.errhdl(e.PATH, m, "W", "737", nombre)
    elif v <= 0.0:
        e.errhdl(e.PATH, m, "E", "380", nombre)
    elif v > 1.0:
        e.errhdl(e.PATH, m, "E", "380", nombre)


def arm2_ratios(e):
    """ARM2_Ratios: razones mínima y máxima de ARM2 (ARMRATIO)."""
    m = "ARM2_Ratios"
    if e.ARM2 and e.IFC < 4:
        e.errhdl(e.PATH, m, "E", "201", e.KEYWRD)
        return
    e.DNUM, imit = dbl(e, 3, e.DNUM)
    if imit != 1:
        e.errhdl(e.PATH, m, "E", "208", e.KEYWRD)
        return
    e.ARM2_MIN = e.DNUM
    _arm2_rango(e, m, e.ARM2_MIN, " ARM2Min")
    e.DNUM, imit = dbl(e, 4, e.DNUM)
    if imit != 1:
        e.errhdl(e.PATH, m, "E", "208", e.KEYWRD)
        return
    e.ARM2_MAX = e.DNUM
    _arm2_rango(e, m, e.ARM2_MAX, " ARM2Max")
    if e.ARM2_MAX < e.ARM2_MIN:
        e.errhdl(e.PATH, m, "E", "380", "ARM2 Max<Min")


def _valores_variables(e, m, sector_on, nsects, nombre_sect, lvals, imax, flags, err_flag,
                       nombre_flag, attr_sect):
    """Parte común de O3VALS y NOXVALS. Devuelve el sector o 0 si hay error."""
    f = e.FIELD
    if not sector_on:
        if e.IFC <= 2:
            e.errhdl(e.PATH, m, "E", "200", e.KEYWRD)
            return 0
        if e.IFC == 3 or e.IFC < 4:
            e.errhdl(e.PATH, m, "E", "201", e.KEYWRD)
            return 0
        if f[3][:4] == "SECT":
            e.errhdl(e.PATH, m, "E", "171", e.KEYWRD)
            return 0
        isect = 1
        i = 3
        setattr(e, attr_sect, isect)
        lvals[isect] = True
        if imax[isect] >= 1 and flags[isect] != f[i]:
            e.errhdl(e.PATH, m, "E", err_flag, f[i])
        else:
            flags[isect] = fc(f[i], 8)
    else:
        if e.IFC <= 2:
            e.errhdl(e.PATH, m, "E", "200", e.KEYWRD)
            return 0
        if e.IFC == 4:
            if f[3][:4] != "SECT":
                e.errhdl(e.PATH, m, "E", "203", nombre_sect)
            else:
                e.errhdl(e.PATH, m, "E", "201", e.KEYWRD)
            return 0
        if e.IFC < 5:
            e.errhdl(e.PATH, m, "E", "201", e.KEYWRD)
            return 0
        isect = _sector(e, m, nombre_sect, nsects)
        if isect == 0:
            return 0
        i = 4
        setattr(e, attr_sect, isect)
        lvals[isect] = True
        if imax[isect] >= 1 and flags[isect] != f[i]:
            if len(f[i]) > 6:
                d = fwrite("('SEC',I1,1X,A)", isect, f[i])[0]
            else:
                d = fwrite("('SECT',I1,1X,A)", isect, f[i])[0]
            e.errhdl(e.PATH, m, "E", err_flag, d)
        else:
            flags[isect] = fc(f[i], 8)
    n = _NMAX.get(flags[isect])
    if n is None:
        e.errhdl(e.PATH, m, "E", "203", nombre_flag)
        return 0
    imax[isect] = n
    if flags[isect] in _DIA_SEMANA:
        e.L_DAYOFWEEKOPTS = True
    return isect


def _rellenar(e, m, sector_on, isect, iset_arr, imax, vary, d_sect, d_simple):
    """O3FILL / NOXFILL: guarda los valores de la tarjeta en VARY(:, ISECT)."""
    iset = int(iset_arr[isect])
    for k in range(5 if sector_on else 4, e.IFC + 1):
        e.DNUM, imit = dbl(e, k, e.DNUM)
        if imit == -1:
            e.errhdl(e.PATH, m, "E", "208", e.KEYWRD)
            continue
        fin = False
        for _j in range(imit):
            iset += 1
            if iset <= imax[isect]:
                vary[iset, isect] = e.DNUM
                if e.DNUM < 0.0:
                    e.errhdl(e.PATH, m, "E", "209", e.KEYWRD)
            else:
                d = fwrite(d_sect, isect)[0] if sector_on else d_simple
                e.errhdl(e.PATH, m, "E", "231", d)
                fin = True
                break
        if fin:
            break
    e.ISET = iset
    iset_arr[isect] = iset


def o3vals(e):
    """O3VALS: ozono de fondo que varía en el tiempo (O3VALUES)."""
    m = "O3VALS"
    isect = _valores_variables(e, m, e.L_O3SECTOR, e.NUMO3SECTS, "O3SECTOR ID", e.L_O3VALUES,
                               e.IO3MAX, e.O3FLAG, "167", "O3FLAG", "IO3SECT")
    if isect == 0:
        return
    _rellenar(e, "O3FILL", e.L_O3SECTOR, isect, e.IO3SET, e.IO3MAX, e.O3VARY,
              "('O3VALs SECT',I1)", "O3VALUES")


def noxvals(e):
    """NOXVALS: NOx de fondo que varía en el tiempo (NOX_VALS)."""
    m = "NOXVALS"
    isect = _valores_variables(e, m, e.L_NOXSECTOR, e.NUMNOXSECTS, "NOXSECTR ID", e.L_NOX_VALS,
                               e.INOXMAX, e.NOXFLAG, "606", "NOXFLG", "INOXSECT")
    if isect == 0:
        return
    _rellenar(e, "NOXFILL", e.L_NOXSECTOR, isect, e.INOXSET, e.INOXMAX, e.NOXVARY,
              "('NOXVAL SECT',I1)", "NOX_VALS")


def _unidad(e, m, attr, nombre):
    if e.IFC <= 2:
        e.errhdl(e.PATH, m, "E", "200", e.KEYWRD)
        return
    if e.IFC > 3:
        e.errhdl(e.PATH, m, "E", "202", e.KEYWRD)
        return
    if e.FIELD[3] in _UNIDADES:
        setattr(e, attr, fc(e.FIELD[3], 200))
    else:
        e.errhdl(e.PATH, m, "E", "203", nombre)


def ozon_unit(e):
    """OZON_UNIT: unidades de O3VALUES (OZONUNIT)."""
    _unidad(e, "OZON_UNIT", "OZONEUNITS", "OzoneUnits")


def nox_unit(e):
    """NOX_UNIT: unidades de NOX_VALS (NOX_UNIT)."""
    _unidad(e, "NOX_UNIT", "NOXUNITS", "NOxUnits")


def _sectores(e, m, sect, attr_l, attr_n, pre, pre_cmp, f_rango, lim_alto, lim_bajo):
    """Parte común de O3SECTOR y NOXSECTOR."""
    if e.IFC <= 2:
        e.errhdl(e.PATH, m, "E", "200", e.KEYWRD)
        return
    if e.IFC < 4:
        e.errhdl(e.PATH, m, "E", "201", e.KEYWRD)
        return
    if e.IFC > 8:
        e.errhdl(e.PATH, m, "E", "202", e.KEYWRD)
        return
    setattr(e, attr_l, True)
    malo = False
    for i in range(3, e.IFC + 1):
        e.DNUM, imit = dbl(e, i, e.DNUM)
        if imit == -1:
            e.errhdl(e.PATH, m, "E", "208", fwrite("('" + pre + "',I1)", i - 2)[0])
            malo = True
            continue
        sect[i - 2] = e.DNUM
        s = sect[i - 2]
        if s < 0.0 or s > 360.0:
            if s > lim_alto:
                d = pre + (">%d." % int(lim_alto))
            elif s < lim_bajo:
                d = pre + ("<%d." % int(lim_bajo))
            else:
                d = fwrite("('" + pre + "=',%s)" % f_rango, s)[0]
            e.errhdl(e.PATH, m, "E", "380", d)
    if malo:
        return
    n = e.IFC - 2
    setattr(e, attr_n, n)
    for i in range(1, n):
        if sect[i + 1] < sect[i]:
            e.errhdl(e.PATH, m, "E", "222", fwrite("('" + pre_cmp + "',I1,' < #',I1)", i + 1, i)[0])
        elif sect[i + 1] < sect[i] + 30.0:
            e.errhdl(e.PATH, m, "E", "227", fwrite("('" + pre_cmp + "',I1,' < 30')", i + 1)[0])
        elif sect[i + 1] < sect[i] + 60.0:
            e.errhdl(e.PATH, m, "W", "227", fwrite("('" + pre_cmp + "',I1,' < 60')", i + 1)[0])
    if (sect[1] + 360.0) - sect[n] < 30.0:
        e.errhdl(e.PATH, m, "E", "227", fwrite("('" + pre_cmp + "',I1,' < 30')", n)[0])
    elif (sect[1] + 360.0) - sect[n] < 60.0:
        e.errhdl(e.PATH, m, "W", "227", fwrite("('" + pre_cmp + "',I1,' < 60')", n)[0])


def o3sector(e):
    """O3SECTOR: límites de los sectores del ozono de fondo."""
    _sectores(e, "O3SECTOR", e.O3SECT, "L_O3SECTOR", "NUMO3SECTS", "O3SECT", "O3SECT", "F5.0",
              9999.0, -999.0)


def noxsector(e):
    """NOXSECTOR: límites de los sectores del NOx de fondo."""
    _sectores(e, "NOXSECTOR", e.NOXSECT, "L_NOXSECTOR", "NUMNOXSECTS", "NOXSECT", "NOXSCT", "F4.0",
              999.0, -99.0)


# ------------------------------------------------------------------------- FINISHED de CO
def finished_ozono(e, m):
    """Comprobaciones de FINISHED de CO para OLM/PVMRM/TTRM/GRSM y ARM2 (tras RUNORNOT)."""
    if e.OLM or e.PVMRM or e.RUNTTRM or e.GRSM:
        c = e.ICSTAT
        if c[24] == 0 and c[25] == 0 and c[26] == 0:
            if e.OLM:
                d = "OLM Option"
            elif e.PVMRM:
                d = "PVMRM Option"
            elif e.GRSM:
                d = "GRSM Option"
            else:
                d = "TTRM Option"
            e.errhdl(e.PATH, m, "E", "283", d)
        elif c[24] > 0 and c[25] > 0:
            if not e.L_O3SECTOR:
                if e.OLM:
                    d = "for OLM"
                elif e.PVMRM:
                    d = "for PVMRM"
                elif e.GRSM:
                    d = "for GRSM"
                else:
                    d = "for TTRM"
                e.errhdl(e.PATH, m, "E", "148", d)
            else:
                for i in range(1, e.NUMO3SECTS + 1):
                    if e.L_O3VAL[i] and e.L_O3VALUES[i]:
                        if e.OLM:
                            d = fwrite("('  OLM SECT',I1)", i)[0]
                        elif e.PVMRM:
                            d = fwrite("('PVMRM SECT',I1)", i)[0]
                        elif e.GRSM:
                            d = fwrite("('GRSM SECT',I1)", i)[0]
                        else:
                            d = fwrite("('  TTRM SECT',I1)", i)[0]
                        e.errhdl(e.PATH, m, "E", "148", d)
        if e.GRSM:
            if c[36] == 0 and c[37] == 0 and c[39] == 0:
                e.L_CALCNOXFROMNO2 = True
                e.errhdl(e.PATH, m, "W", "612", "for GRSM")
            elif c[36] > 0 and c[37] > 0:
                if not e.L_NOXSECTOR:
                    e.errhdl(e.PATH, m, "E", "605", "for GRSM ")
                else:
                    for i in range(1, e.NUMNOXSECTS + 1):
                        if e.L_NOXVALUE[i] and e.L_NOX_VALS[i]:
                            e.errhdl(e.PATH, m, "E", "605", fwrite("('GRSM SECT',I1)", i)[0])
        if c[28] == 0:
            e.ANO2_RATIO[:] = -9.0
        if c[25] == 0 and c[27] > 0:
            e.errhdl(e.PATH, m, "E", "193", "CO O3VALUES")
        if c[37] == 0 and c[38] > 0:
            e.errhdl(e.PATH, m, "E", "193", "CO NOX_VALS")
    if e.ARM2 and e.ICSTAT[32] == 0:
        e.ARM2_MIN = 0.50
        e.ARM2_MAX = 0.90


def finished_completos(e, m):
    """FINISHED de CO: comprobación de que los datos de ozono y NOx de fondo estén completos."""
    def n_sect(pre, i, n):
        if n < 100:
            return fwrite("('" + pre + "',I1,' N=',I2)", i, n)[0]
        return fwrite("('SECT',I1,' N=',I4)", i, n)[0]

    if e.L_O3SECTOR:
        for i in range(1, e.NUMO3SECTS + 1):
            if e.L_O3FILE[i]:
                if e.L_O3VALUES[i]:
                    if e.IO3SET[i] < e.IO3MAX[i]:
                        e.errhdl(e.PATH, m, "E", "261", n_sect("O3SECT", i, int(e.IO3SET[i])))
                elif not e.L_O3VALUES[i] and not e.L_O3VAL[i]:
                    e.errhdl(e.PATH, m, "W", "271", fwrite("('O3SECT',I1)", i)[0])
            else:
                if e.L_O3VALUES[i]:
                    if e.IO3SET[i] < e.IO3MAX[i]:
                        e.errhdl(e.PATH, m, "E", "261", n_sect("O3SECT", i, int(e.IO3SET[i])))
                elif not e.L_O3VALUES[i] and not e.L_O3VAL[i]:
                    e.errhdl(e.PATH, m, "E", "261", fwrite("('O3SECT',I1,' Msg')", i)[0])
    else:
        i = 1
        if e.L_O3FILE[i]:
            if e.L_O3VALUES[i]:
                if e.IO3SET[i] < e.IO3MAX[i]:
                    e.errhdl(e.PATH, m, "E", "261", fwrite("('NumVals=',I4)", int(e.IO3SET[i]))[0])
            elif not e.L_O3VALUES[i] and not e.L_O3VAL[i]:
                e.errhdl(e.PATH, m, "W", "271", " ")
        elif e.L_O3VALUES[i]:
            if e.IO3SET[i] < e.IO3MAX[i]:
                e.errhdl(e.PATH, m, "E", "261", fwrite("('NumVals=',I4)", int(e.IO3SET[i]))[0])
    if e.L_NOXSECTOR:
        for i in range(1, e.NUMNOXSECTS + 1):
            if e.L_NOXFILE[i]:
                if e.L_NOX_VALS[i]:
                    if e.INOXSET[i] < e.INOXMAX[i]:
                        e.errhdl(e.PATH, m, "E", "603", n_sect("NOXSCT", i, int(e.INOXSET[i])))
                elif not e.L_NOX_VALS[i] and not e.L_NOXVALUE[i]:
                    e.errhdl(e.PATH, m, "W", "611", fwrite("('NOXSECT',I1)", i)[0])
            else:
                if e.L_NOX_VALS[i]:
                    if e.INOXSET[i] < e.INOXMAX[i]:
                        e.errhdl(e.PATH, m, "E", "603", n_sect("NOXSCT", i, int(e.INOXSET[i])))
                elif not e.L_NOX_VALS[i] and not e.L_NOXVALUE[i]:
                    e.errhdl(e.PATH, m, "E", "603", fwrite("('NOXSECT',I1,' Msg')", i)[0])
    else:
        i = 1
        if e.L_NOXFILE[i]:
            if e.L_NOX_VALS[i]:
                if e.INOXSET[i] < e.INOXMAX[i]:
                    e.errhdl(e.PATH, m, "E", "603", fwrite("('NumVals=',I4)", int(e.INOXSET[i]))[0])
            elif not e.L_NOX_VALS[i] and not e.L_NOXVALUE[i]:
                e.errhdl(e.PATH, m, "W", "611", " ")
        elif e.L_NOX_VALS[i]:
            if e.INOXSET[i] < e.INOXMAX[i]:
                e.errhdl(e.PATH, m, "E", "603", fwrite("('NumVals',I4)", int(e.INOXSET[i]))[0])


# =================================================================================== vía SO
def socard(e, k, orden_grupo):
    """Ramas de SOCARD de NO2RATIO, OLMGROUP y PSDGROUP. Devuelve False si no es de las suyas."""
    m = "SOCARD"
    if k == "NO2RATIO":
        e.ISSTAT[29] += 1
        orden_grupo(e, m)
        if e.PVMRM or e.OLM or e.RUNTTRM or e.GRSM:
            no2rat(e)
        else:
            e.errhdl(e.PATH, m, "E", "600", k)
    elif k == "OLMGROUP":
        e.ISSTAT[30] += 1
        orden_grupo(e, m)
        if e.OLM:
            olmgrp(e)
        else:
            e.errhdl(e.PATH, m, "E", "144", k)
    elif k == "PSDGROUP":
        e.ISSTAT[34] += 1
        if e.PSDCREDIT:
            psdgrp(e)
        else:
            e.errhdl(e.PATH, m, "E", "146", k)
    else:
        return False
    return True


def no2rat(e):
    """NO2RAT: razón NO2/NOx en chimenea de una fuente o de un rango de fuentes (NO2RATIO)."""
    from .entrada_fuentes import asngrp, setidg
    m = "NO2RAT"
    if e.IFC <= 2:
        e.errhdl(e.PATH, m, "E", "200", e.KEYWRD)
        return
    if e.IFC < 4:
        e.errhdl(e.PATH, m, "E", "201", e.KEYWRD)
        return
    if e.IFC > 4:
        e.errhdl(e.PATH, m, "E", "202", e.KEYWRD)
        return
    soid = e.FIELD[3]
    _r, lid, hid = fsplit(e, e.PATH, e.KEYWRD, soid, ILEN_FLD, "-")
    lid, hid = fc(lid, 12), fc(hid, 12)
    if lid == hid:
        isdx, found = sindex(e.SRCID, e.NSRC, soid)
        if found:
            e.DNUM, imit = dbl(e, 4, e.DNUM)
            if imit != 1:
                e.errhdl(e.PATH, m, "E", "208", e.KEYWRD)
                return
            if e.DNUM < 0.0 or e.DNUM > 1.0:
                e.errhdl(e.PATH, m, "E", "336", e.SRCID[isdx])
            e.ANO2_RATIO[isdx] = e.DNUM
        else:
            e.errhdl(e.PATH, m, "E", "300", e.KEYWRD)
    else:
        l1, il, l2 = setidg(lid)
        h1, ih, h2 = setidg(hid)
        if h1 < l1 or ih < il or h2 < l2:
            e.errhdl(e.PATH, m, "E", "203", "SRCRANGE")
            return
        for i in range(1, e.NUMSRC + 1):
            if asngrp(e.SRCID[i], lid, hid):
                e.DNUM, imit = dbl(e, 4, e.DNUM)
                if imit != 1:
                    e.errhdl(e.PATH, m, "E", "208", e.KEYWRD)
                    return
                if e.DNUM < 0.0 or e.DNUM > 1.0:
                    e.errhdl(e.PATH, m, "E", "336", e.SRCID[i])
                e.ANO2_RATIO[i] = e.DNUM


def olmgrp(e):
    """OLMGRP: grupos de fuentes que se combinan en OLM (OLMGROUP)."""
    from .entrada_fuentes import asngrp, setidg
    m = "OLMGRP"
    f = e.FIELD
    if e.IFC <= 2:
        e.errhdl(e.PATH, m, "E", "200", e.KEYWRD)
        return
    if e.IFC <= 3 and f[3] != "ALL":
        e.errhdl(e.PATH, m, "E", "201", e.KEYWRD)
        return
    cont = False
    if e.LOCE[3] - e.LOCB[3] <= 7:
        tempid = fc(f[3], 8)
        for i in range(1, e.NUMOLM + 1):
            if tempid == e.OLMID[i]:
                cont = True
                break
    else:
        e.errhdl(e.PATH, m, "E", "232", f[3][:12])
        return
    if not cont:
        e.IOLM += 1
        if e.IOLM > e.NOLM:
            e.errhdl(e.PATH, m, "E", "290", fwrite("('NOLM=',I7)", e.NOLM)[0])
            return
        e.NUMOLM += 1
        e.OLMID[e.IOLM] = tempid
    iolm = e.IOLM
    if e.OLMID[iolm] == "ALL" and not cont:
        if e.NUMSRC < e.NSRC:
            e.errhdl(e.PATH, m, "E", "140", "OLMGROUP ALL")
            return
        for i in range(1, e.NUMSRC + 1):
            e.IGRP_OLM[i, iolm] = 1
            e.L_OLMGRP[i] = True
        return
    for i in range(4, e.IFC + 1):
        if "-" not in f[i]:
            found = False
            for k in range(1, e.NUMSRC + 1):
                if f[i] == e.SRCID[k]:
                    found = True
                    e.L_OLMGRP[k] = True
                    e.IGRP_OLM[k, iolm] = 1
                    break
            if not found:
                e.errhdl(e.PATH, m, "E", "225", f[i][:12])
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
                    e.L_OLMGRP[k] = True
                    e.IGRP_OLM[k, iolm] = 1


_PSD_TIPO = {"INCRCONS": "IC", "NONRBASE": "NB", "RETRBASE": "RB"}


def psdgrp(e):
    """PSDGRP: grupos de fuentes del cálculo de incremento PSD con créditos (PSDGROUP)."""
    from .entrada_fuentes import asngrp, setidg
    m = "PSDGRP"
    f = e.FIELD
    if e.IFC <= 2:
        e.errhdl(e.PATH, m, "E", "200", e.KEYWRD)
        return
    if e.IFC < 4:
        e.errhdl(e.PATH, m, "E", "201", e.KEYWRD)
        return
    cont = False
    if e.LOCE[3] - e.LOCB[3] <= 7:
        tempid = fc(f[3], 12)
        for i in range(1, e.NUMPSD + 1):
            if tempid == e.PSDID[i]:
                cont = True
                break
    else:
        e.errhdl(e.PATH, m, "E", "253", f[3][:12])
        return
    if not cont:
        e.IPSD += 1
        if e.IPSD > e.NPSD:
            e.errhdl(e.PATH, m, "E", "290", fwrite("('NPSD=',I7)", e.NPSD)[0])
            return
        e.NUMPSD += 1
        e.PSDID[e.IPSD] = fc(tempid, 8)
    ipsd = e.IPSD
    tipo = _PSD_TIPO.get(e.PSDID[ipsd])
    if tipo is None:
        e.errhdl(e.PATH, m, "E", "287", e.KEYWRD)
        return
    for i in range(4, e.IFC + 1):
        if "-" not in f[i]:
            found = False
            for k in range(1, e.NUMSRC + 1):
                if f[i] == e.SRCID[k]:
                    found = True
                    e.IGRP_PSD[k, ipsd] = 1
                    e.PSDSRCTYP[k] = tipo
            if not found:
                e.errhdl(e.PATH, m, "E", "226", f[i][:12])
        else:
            _r, lowid, higid = fsplit(e, e.PATH, e.KEYWRD, f[i], ILEN_FLD, "-")
            lowid, higid = fc(lowid, 12), fc(higid, 12)
            l1, il, l2 = setidg(lowid)
            h1, ih, h2 = setidg(higid)
            if h1 < l1 or ih < il or h2 < l2:
                e.errhdl(e.PATH, m, "E", "203", "PSDRANGE")
                continue
            for k in range(1, e.NUMSRC + 1):
                if asngrp(e.SRCID[k], lowid, higid):
                    e.IGRP_PSD[k, ipsd] = 1
                    e.L_PSDGRP[k] = True
                    e.PSDSRCTYP[k] = tipo


# --------------------------------------------------------------------------------- SRCQA
def srcqa_psd(e, m):
    """SRCQA con PSDCREDIT: grupos NAAQS y PSDINC y fuentes sin PSDGROUP."""
    e.NUMGRP = 2
    e.GRPID[1] = "NAAQS"
    e.GRPID[2] = "PSDINC"
    for i in range(1, e.NUMSRC + 1):
        itot = int((e.IGRP_PSD[i, 1:e.NUMPSD + 1] == 1).sum())
        if itot == 0:
            e.errhdl(e.PATH, m, "E", "317", e.SRCID[i])


def srcqa_no2(e, m):
    """Final de SRCQA: fuentes en varios OLMGROUP/PSDGROUP y datos de las opciones del NO2."""
    if e.NUMOLM > 0:
        for i in range(1, e.NUMSRC + 1):
            if int((e.IGRP_OLM[i, 1:e.NUMOLM + 1] == 1).sum()) > 1:
                e.errhdl(e.PATH, m, "E", "282", e.SRCID[i])
    return


def srcqa_no2_final(e, m):
    """SRCQA: PSDGROUP repetidos, emisiones negativas y razones NO2/NOx sin definir."""
    if e.PSDCREDIT:
        for i in range(1, e.NUMSRC + 1):
            if int((e.IGRP_PSD[i, 1:e.NUMPSD + 1] == 1).sum()) > 1:
                e.errhdl(e.PATH, m, "E", "286", e.SRCID[i])
    if e.OLM or e.PVMRM or e.RUNTTRM or e.GRSM:
        for i in range(1, e.NUMSRC + 1):
            if e.AQS[i] < 0.0:
                e.errhdl(e.PATH, m, "E", "338", e.SRCID[i])
        for i in range(1, e.NUMSRC + 1):
            if e.ANO2_RATIO[i] < 0.0:
                e.errhdl(e.PATH, m, "E", "336", e.SRCID[i])
    elif e.ARM2:
        indx = 0
        for i in range(1, e.NUMGRP + 1):
            if e.GRPID[i] == "ALL":
                indx = i
                break
        if indx == 0:
            e.errhdl(e.PATH, m, "W", "299", "ARM2 Option")
        for i in range(1, e.NUMSRC + 1):
            if e.AQS[i] < 0.0:
                e.errhdl(e.PATH, m, "E", "338", e.SRCID[i])
