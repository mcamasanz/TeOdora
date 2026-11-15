# -*- coding: utf-8 -*-
"""Traducción de AERMOD 26135 (US EPA, dominio público): vía ME (meset.f).

MECARD con SURFFILE, PROFFILE, SURFDATA, UAIRDATA, SITEDATA, PROFBASE, STARTEND, WDROTATE,
WINDCATS y NUMYEARS; MEOPEN (cabecera del .sfc y primer perfil del .pfl), CENT_DATE y DCDLAT."""
from . import meteo_horaria
from .control import dbl, fsplit, i8, num
from .estado import ILEN_FLD, NoTraducido
from .formato import fc, fread, fwrite, lread, nint, stonum

_IDYMAX = (0, 31, 29, 31, 30, 31, 30, 31, 31, 30, 31, 30, 31)


def mecard(e):
    """MECARD: claves de la vía ME."""
    m = "MECARD"
    k = e.KEYWRD
    simples = {"SURFFILE": (2, surfil), "PROFFILE": (3, profil), "SURFDATA": (4, sfdata),
               "UAIRDATA": (5, uadata), "WDROTATE": (8, wdrota), "SITEDATA": (9, ondata),
               "PROFBASE": (10, prbase), "WINDCATS": (11, wscats), "NUMYEARS": (13, numyr)}
    if k == "STARTING":
        e.IMSTAT[1] += 1
        if e.IMSTAT[1] != 1:
            e.errhdl(e.PATH, m, "E", "135", k)
    elif k in simples:
        n, fn = simples[k]
        e.IMSTAT[n] += 1
        if e.IMSTAT[n] != 1:
            e.errhdl(e.PATH, m, "E", "135", k)
        else:
            fn(e)
    elif not e.EVONLY and k == "STARTEND":
        e.IMSTAT[6] += 1
        if e.SCIM:
            e.errhdl(e.PATH, m, "E", "154", k)
        elif e.IMSTAT[6] != 1:
            e.errhdl(e.PATH, m, "E", "135", k)
        else:
            staend(e)
    elif not e.EVONLY and k == "DAYRANGE":
        e.IMSTAT[7] += 1
        if e.SCIM:
            e.errhdl(e.PATH, m, "E", "154", k)
        else:
            if e.IMSTAT[7] == 1:
                e.IPROC[:] = 0
                e.IPROCL[:] = 0
            dayrng(e)
    elif k == "SCIMBYHR" and e.SCIM:
        raise NoTraducido("SCIM")
    elif k in ("NOTURB", "NOTURBST", "NOTURBCO", "NOSA", "NOSW", "NOSAST", "NOSWST", "NOSACO", "NOSWCO"):
        raise NoTraducido("ME " + k)
    elif k == "FINISHED":
        e.IMSTAT[50] += 1
        if e.IMSTAT[50] != 1:
            e.errhdl(e.PATH, m, "E", "135", k)
            return
        for n, nom in ((1, "STARTING"), (2, "SURFFILE"), (3, "PROFFILE"), (4, "SURFDATA"), (5, "UAIRDATA"),
                       (10, "PROFBASE")):
            if e.IMSTAT[n] == 0:
                e.errhdl(e.PATH, m, "E", "130", nom)
        if e.SCIM and e.IMSTAT[12] == 0:
            e.errhdl(e.PATH, m, "E", "130", "SCIMBYHR")
        if e.IMSTAT[2] != 0 and e.IMSTAT[3] != 0:
            meopen(e)
        y = e.ISYEAR
        bisiesto = not (y % 4 != 0 or (y % 100 == 0 and y % 400 != 0))
        e.L_LEAPYEAR = bisiesto
        if e.MULTYR:
            e.INCRST = 366 if bisiesto else 365
        nd = 366 if bisiesto else 365
        ndys = 0
        for i in range(1, nd + 1):
            if nd == 365:
                if e.IPROC[i] == 1:
                    ndys += 1
            elif e.IPROCL[i] == 1:
                ndys += 1
        e.NHOURS = ndys * 24
    else:
        e.errhdl(e.PATH, m, "E", "110", k)


def _fichero(e, m, attr):
    if e.IFC in (3, 4):
        if e.LOCE[3] - e.LOCB[3] <= ILEN_FLD - 1:
            setattr(e, attr, fc(e.RUNST1[int(e.LOCB[3]) - 1:int(e.LOCE[3])], 200))
        else:
            e.DUMMY = i8(ILEN_FLD)
            e.errhdl(e.PATH, m, "E", "291", e.DUMMY)
        if e.IFC == 4 and e.FIELD[4] != "FREE":
            e.errhdl(e.PATH, m, "W", "293", "format")
    elif e.IFC > 4:
        e.errhdl(e.PATH, m, "E", "202", e.KEYWRD)
    else:
        e.errhdl(e.PATH, m, "E", "200", e.KEYWRD)


def surfil(e):
    """SURFIL: fichero de superficie (.sfc)."""
    _fichero(e, "SURFIL", "METINP")


def profil(e):
    """PROFIL: fichero de perfiles (.pfl)."""
    _fichero(e, "PROFIL", "PROINP")


def cent_date(e, x):
    """CENT_DATE con los dos argumentos asociados a la MISMA variable (como la llama el original):
    año de 2 cifras -> 4 cifras, actualizando la ventana de siglo (ISTRT_WIND, ISTRT_CENT)."""
    if x != e.ISTRT_WIND:
        e.ISTRT_WIND = x
        if 50 <= x < 100:
            e.ISTRT_CENT = 19
        elif x < 50:
            e.ISTRT_CENT = 20
    if e.ISTRT_WIND <= x <= 99:
        x = e.ISTRT_CENT * 100 + x
    elif x > 99:
        x = x - 100 * (x // 100)
    return x


def _estacion(e, m, attr_id, attr_yr, attr_nom, attr_x, attr_y, cero_si_error=True):
    if e.IFC == 2:
        e.errhdl(e.PATH, m, "E", "200", e.KEYWRD)
        return
    elif e.IFC < 4:
        e.errhdl(e.PATH, m, "E", "201", e.KEYWRD)
        return
    elif e.IFC > 7:
        e.errhdl(e.PATH, m, "E", "202", e.KEYWRD)
        return
    e.FNUM, imit = num(e, 3, e.FNUM)
    if imit != 1:
        e.errhdl(e.PATH, m, "E", "208", e.KEYWRD)
        if cero_si_error:
            setattr(e, attr_id, 0)
    else:
        setattr(e, attr_id, nint(e.FNUM))
    e.FNUM, imit = num(e, 4, e.FNUM)
    e.IMIT = imit
    if imit != 1:
        e.errhdl(e.PATH, m, "E", "208", e.KEYWRD)
        if cero_si_error:
            setattr(e, attr_yr, 0)
    else:
        setattr(e, attr_yr, nint(e.FNUM))
        if cero_si_error and getattr(e, attr_yr) <= 99:
            setattr(e, attr_yr, cent_date(e, getattr(e, attr_yr)))
    setattr(e, attr_nom, fc(e.FIELD[5], 40) if e.IFC >= 5 else "UNKNOWN")
    if e.IFC == 7:
        v, imit = dbl(e, 6, getattr(e, attr_x))
        setattr(e, attr_x, v)
        if imit != 1:
            e.errhdl(e.PATH, m, "E", "208", e.KEYWRD)
        v, imit = dbl(e, 7, getattr(e, attr_y))
        e.IMIT = imit
        setattr(e, attr_y, v)
        if imit != 1:
            e.errhdl(e.PATH, m, "E", "208", e.KEYWRD)


def sfdata(e):
    """SFDATA: estación de superficie (SURFDATA)."""
    _estacion(e, "SFDATA", "IDSURF", "ISYEAR", "SFNAME", "SFX", "SFY")


def uadata(e):
    """UADATA: estación de altura (UAIRDATA)."""
    _estacion(e, "UADATA", "IDUAIR", "IUYEAR", "UANAME", "UAX", "UAY")


def ondata(e):
    """ONDATA: estación local (SITEDATA)."""
    _estacion(e, "ONDATA", "IDSITE", "IOYEAR", "ONNAME", "ONX", "ONY", cero_si_error=False)


def prbase(e):
    """PRBASE: cota base del perfil de temperatura potencial (PROFBASE)."""
    m = "PRBASE"
    if e.IFC in (3, 4):
        e.ZBASE, imit = dbl(e, 3, e.ZBASE)
        e.IMIT = imit
        if imit != 1:
            e.errhdl(e.PATH, m, "E", "208", e.KEYWRD)
            return
        if e.IFC == 4 and e.FIELD[4] == "FEET":
            e.ZBASE = 0.3048 * e.ZBASE
        elif e.IFC == 4 and e.FIELD[4] != "METERS":
            e.errhdl(e.PATH, m, "W", "203", "ZRUNIT")
        if e.ZBASE < 0.0 and imit == 1:
            e.errhdl(e.PATH, m, "W", "340", e.KEYWRD)
    elif e.IFC > 4:
        e.errhdl(e.PATH, m, "E", "202", e.KEYWRD)
    else:
        e.errhdl(e.PATH, m, "E", "200", e.KEYWRD)
    if e.FLAT:
        if not e.FLATSRCS:
            e.AZS[:] = e.ZBASE
        else:
            for isrc in range(1, e.NUMSRC + 1):
                if e.L_FLATSRC[isrc]:
                    e.AZS[isrc] = e.ZBASE
            e.ISRC = e.NUMSRC + 1
        if not e.FLATSRCS:
            for irec in range(1, e.NUMREC + 1):
                e.AZELEV[irec] = e.ZBASE
                e.AZHILL[irec] = e.ZBASE
            e.IREC = e.NUMREC + 1


def staend(e):
    """STAEND: periodo de cálculo (STARTEND)."""
    m = "STAEND"
    f = e.FIELD

    def leer(k):
        e.FNUM, imit = num(e, k, e.FNUM)
        e.IMIT = imit
        if imit != 1:
            e.errhdl(e.PATH, m, "E", "208", e.KEYWRD)
            return None
        return nint(e.FNUM)

    def mes(k, attr):
        v = leer(k)
        if v is not None:
            setattr(e, attr, v)
            if v < 1 or v > 12:
                e.errhdl(e.PATH, m, "E", "203", "MONTH")

    def dia(k, attr, attr_mes):
        v = leer(k)
        if v is not None:
            setattr(e, attr, v)
            mm = getattr(e, attr_mes)
            if 1 <= mm <= 12 and (v < 1 or v > _IDYMAX[mm]):
                e.errhdl(e.PATH, m, "E", "203", "DAY")

    def hora(k, attr):
        v = leer(k)
        if v is not None:
            setattr(e, attr, v)
            if v < 1 or v > 24:
                e.errhdl(e.PATH, m, "E", "203", "HOUR")

    if e.IFC == 8 or e.IFC == 10:
        larga = e.IFC == 10
        v = leer(3)
        if v is not None:
            e.ISYR = v
        mes(4, "ISMN")
        dia(5, "ISDY", "ISMN")
        if larga:
            hora(6, "ISHR")
        v = leer(7 if larga else 6)
        if v is not None:
            e.IEYR = v
        mes(8 if larga else 7, "IEMN")
        dia(9 if larga else 8, "IEDY", "IEMN")
        if larga:
            hora(10, "IEHR")
        if e.ISYR <= 99:
            e.ISYR = cent_date(e, e.ISYR)
        if e.IEYR <= 99:
            e.IEYR = cent_date(e, e.IEYR)
        e.ISJDAY = e.julian(e.ISYR, e.ISMN, e.ISDY)
        e.IEJDAY = e.julian(e.IEYR, e.IEMN, e.IEDY)
        if not larga:
            e.ISHR = 1
            e.IEHR = 24
        if e.ISYR <= 2147:
            e.ISDATE = e.ISYR * 1000000 + e.ISMN * 10000 + e.ISDY * 100 + e.ISHR
        else:
            e.errhdl(e.PATH, m, "E", "365", e.KEYWRD)
            e.ISDATE = 2147123124
        if e.IEYR <= 2147:
            e.IEDATE = e.IEYR * 1000000 + e.IEMN * 10000 + e.IEDY * 100 + e.IEHR
        else:
            e.errhdl(e.PATH, m, "E", "365", e.KEYWRD)
            e.IEDATE = 2147123124
    elif e.IFC > 8:
        e.errhdl(e.PATH, m, "E", "202", e.KEYWRD)
        return
    else:
        e.errhdl(e.PATH, m, "E", "201", e.KEYWRD)
        return
    if e.ISHR > 1:
        e.IENDHOUR = e.ISHR - 1
        e.IENDDY = e.ISDY
        e.IENDMN = e.ISMN
    else:
        e.IENDHOUR = 24
        if e.ISDY > 1:
            e.IENDDY = e.ISDY - 1
            e.IENDMN = e.ISMN
        else:
            e.IENDMN = e.ISMN - 1
            if e.IENDMN == 0:
                e.IENDMN = 12
            if e.IENDMN != 2 or (e.IEYR % 4 == 0):
                e.IENDDY = _IDYMAX[e.IENDMN]
            else:
                e.IENDDY = 28
    if e.IEYR < e.ISYR:
        e.errhdl(e.PATH, m, "E", "203", "END YEAR")
        return
    if e.ANNUAL or e.MULTYR or e.L_MAXDCONT:
        if e.IEYR == e.ISYR:
            if (e.ISMN != 1 or e.ISDY != 1 or e.ISHR != 1 or e.IEMN != 12 or e.IEDY != 31
                    or e.IEHR != 24):
                e.errhdl(e.PATH, m, "E", "480", e.KEYWRD)
        elif e.IEYR - e.ISYR == 1:
            if e.IEMN < e.IENDMN:
                e.errhdl(e.PATH, m, "E", "480", e.KEYWRD)
            elif e.IEMN == e.IENDMN:
                if e.IEDY < e.IENDDY:
                    e.errhdl(e.PATH, m, "E", "480", e.KEYWRD)
                elif e.IEDY == e.IENDDY:
                    if e.IEHR < e.IENDHOUR:
                        e.errhdl(e.PATH, m, "E", "480", e.KEYWRD)


def wdrota(e):
    """WDROTA: rotación de la dirección del viento (WDROTATE)."""
    m = "WDROTA"
    e.ROTANG = 0.0
    if e.IFC == 3:
        e.ROTANG, imit = dbl(e, 3, e.ROTANG)
        e.IMIT = imit
        if imit != 1:
            e.errhdl(e.PATH, m, "E", "208", e.KEYWRD)
        elif abs(e.ROTANG) > 180.0:
            e.errhdl(e.PATH, m, "E", "380", "ROTANG")
    elif e.IFC > 3:
        e.errhdl(e.PATH, m, "E", "202", e.KEYWRD)
    else:
        e.errhdl(e.PATH, m, "E", "200", e.KEYWRD)


def wscats(e):
    """WSCATS: límites de las categorías de velocidad del viento (WINDCATS)."""
    m = "WSCATS"
    if e.IFC == 7:
        for i in range(3, e.IFC + 1):
            e.DNUM, imit = dbl(e, i, e.DNUM)
            e.IMIT = imit
            if imit != 1:
                e.errhdl(e.PATH, m, "E", "208", e.KEYWRD)
            elif e.DNUM < 1.0 or e.DNUM > 20.0:
                e.errhdl(e.PATH, m, "E", "380", "UCAT")
            else:
                iws = i - 2
                e.UCAT[iws] = e.DNUM
                if iws > 1 and e.UCAT[iws] <= e.UCAT[iws - 1]:
                    e.errhdl(e.PATH, m, "E", "203", "UCAT")
    elif e.IFC > 7:
        e.errhdl(e.PATH, m, "E", "202", e.KEYWRD)
    else:
        e.errhdl(e.PATH, m, "E", "200", e.KEYWRD)


def numyr(e):
    """NUMYR: número de años de meteorología (NUMYEARS)."""
    m = "NUMYR"
    if e.IFC == 3:
        e.FNUM, imit = num(e, 3, e.FNUM)
        e.IMIT = imit
        if imit != 1:
            e.errhdl(e.PATH, m, "E", "208", e.KEYWRD)
        else:
            e.NYEARS = nint(e.FNUM)
            if abs(e.FNUM - float(e.NYEARS)) > 1.0e-5:
                e.errhdl(e.PATH, m, "E", "208", e.KEYWRD)
    elif e.IFC > 3:
        e.errhdl(e.PATH, m, "E", "202", e.KEYWRD)
    else:
        e.errhdl(e.PATH, m, "E", "200", e.KEYWRD)


def _abierto(e, nombre):
    import os
    n = os.path.normcase(os.path.abspath(nombre))
    for u, f in e.U.items():
        if getattr(f, "nombre", None) and os.path.normcase(os.path.abspath(f.nombre)) == n:
            return True
    return False


def meopen(e):
    """MEOPEN: abre los ficheros meteorológicos, lee la cabecera del .sfc y el primer perfil."""
    m = "MEOPEN"
    metver = 0
    mfopen = mpopen = False
    if not _abierto(e, e.METINP):
        if e.MFUNIT not in e.U:
            try:
                e.abrir_entrada(e.MFUNIT, e.METINP)
                e.FUNITARRAY[e.FUNITIND] = e.MFUNIT
                e.FNAMEARRAY[e.FUNITIND] = e.METINP
                e.FTYPARRAY[e.FUNITIND] = "SURFFILE"
                e.FUNITIND += 1
                mfopen = True
            except OSError:
                e.errhdl(e.PATH, m, "E", "500", "SURFFILE")
        else:
            e.errhdl(e.PATH, m, "E", "501", "SURFFILE")
    else:
        mfopen = True
    if not _abierto(e, e.PROINP):
        if e.MPUNIT not in e.U:
            try:
                e.abrir_entrada(e.MPUNIT, e.PROINP)
                e.FUNITARRAY[e.FUNITIND] = e.MPUNIT
                e.FNAMEARRAY[e.FUNITIND] = e.PROINP
                e.FTYPARRAY[e.FUNITIND] = "PROFFILE"
                e.FUNITIND += 1
                mpopen = True
            except OSError:
                e.errhdl(e.PATH, m, "E", "500", "PROFFILE")
                mpopen = False
        else:
            e.errhdl(e.PATH, m, "E", "501", "PROFFILE")
    else:
        mpopen = True
    if not mfopen and not mpopen:
        return
    e.DUMMY = "SURFFILE"
    if mfopen:
        rec = e.U[e.MFUNIT].leer()
        if rec is None:
            e.errhdl(e.PATH, m, "E", "510", e.DUMMY)
            return
        buf = rec[:256].ljust(256)
        _cabecera_sfc(e, m, buf)
    if not mpopen:
        return
    meteo_horaria.pflini(e)
    level = 1
    jflag = 0
    e.DUMMY = "PROFFILE"
    pfl = e.U[e.MPUNIT]
    while jflag == 0:
        tipos = ("i", "i", "i", "i", "f", "i", "f", "f", "f", "f", "f")
        previos = [e.KYEAR, e.KMONTH, e.KDAY, e.KHOUR, e.PFLHT[level], jflag, e.PFLWD[level],
                   e.PFLWS[level], e.PFLTA[level], e.PFLSA[level], e.PFLSW[level]]
        vals, ios, nr = lread(pfl.regs[pfl.ptr:pfl.ptr + 20], tipos, previos)
        if ios < 0:
            raise NoTraducido("fin del .pfl dentro del primer perfil (rama END=1000 de MEOPEN)")
        pfl.ptr += nr
        if ios > 0:
            e.errhdl(e.PATH, m, "E", "510", e.DUMMY)
            return
        (e.KYEAR, e.KMONTH, e.KDAY, e.KHOUR, e.PFLHT[level], jflag, e.PFLWD[level], e.PFLWS[level],
         e.PFLTA[level], e.PFLSA[level], e.PFLSW[level]) = vals
        meteo_horaria.pflcnv(e, level)
        e.NPLVLS = level
        e.IFLAG[level] = jflag
        if e.PFLHT[level] > 999.0 or e.PFLHT[level] <= 0.0:
            if not e.L_MMIF_DATA and not e.L_MMIF_PROFILE:
                e.DUMMY = fwrite("('LVL',I2.2,1X,I5,'m')", level, nint(e.PFLHT[level]))[0]
                e.errhdl(e.PATH, m, "W", "184", e.DUMMY)
                if jflag == 1:
                    e.L_MMIF_PROFILE = True
        if jflag == 0:
            level += 1
            if level > e.MXPLVL:
                if not e.PFLERR:
                    e.DUMMY = i8(e.MXPLVL)
                    e.errhdl(e.PATH, m, "E", "465", e.DUMMY)
                    e.PFLERR = True
                    e.RUNERR = True
                level = e.MXPLVL
    pfl.rewind()


def _cabecera_sfc(e, m, buf):
    """Parte de MEOPEN que interpreta la cabecera del .sfc (versión, opciones, estaciones)."""
    i = buf.find("VERSION:")
    if i >= 0:
        e.C_METVER = fc(buf[i + 8:i + 14], 6)
    elif buf[92:98] != "      ":
        e.C_METVER = fc(buf[92:98], 6)
    else:
        e.C_METVER = ""
        e.errhdl(e.PATH, m, "E", "395", "No Version")
    if "THRESH_1MIN" in buf:
        a = buf.find("=")
        b = buf.find("m/s")
        vals, _ios, _n = lread(buf[a + 1:b + 1], (("a", 6),))
        thr = vals[0] if vals else "      "
        e.errhdl(e.PATH, m, "W", "186", thr)
    if "ADJ_U*" in buf:
        e.L_ADJUSTAR = True
        e.errhdl(e.PATH, m, "W", "187", " ")
        e.MODOPS[23] = "ADJ_U*"
    if "MMIF" in buf or "PROG" in buf:
        e.L_MMIF_DATA = True
        e.errhdl(e.PATH, m, "W", "182", "  ")
        e.MODOPS[24] = "MMIF_Data"
        if "MMIF VERSION" in buf:
            j = buf.find("MMIF VERSION")
            e.MMIF_VERSION = fc(buf[j:j + 29], 29)
        elif "PROG VERSION" in buf:
            j = buf.find("PROG VERSION")
            e.MMIF_VERSION = fc(buf[j:j + 29], 29)
        else:
            e.MMIF_VERSION = ""
    if "COARE" in buf:
        e.L_COARE = True
        e.MODOPS[27] = "COARE"
        e.errhdl(e.PATH, m, "W", "422", "  ")
    if "BULKRN" in buf:
        e.L_BULKRN = True
        if not e.L_COARE:
            e.MODOPS[27] = "BULKRN"
        else:
            e.errhdl(e.PATH, m, "E", "423", "  ")
        e.errhdl(e.PATH, m, "W", "181", "with MMIF" if e.L_MMIF_DATA else "in AERMET")
    e.L_CCVR_SUB = "CCVR_Sub" in buf
    e.L_TEMP_SUB = "TEMP_Sub" in buf
    e.ALAT = fc(buf[0:10], 10)
    e.ALON = fc(buf[10:20], 10)

    def ident(clave):
        j = buf.find(clave)
        c = buf[j + 7:j + 15] if j >= 0 else "        "
        v, imit = stonum(c, 8, e.FNUM)
        e.FNUM = v
        return c.rstrip(" "), (nint(v) if imit == 1 else 0)

    cusi, iusi = ident("UA_ID:")
    cssi, issi = ident("SF_ID:")
    cosi, iosi = ident("OS_ID:")
    if e.SCREEN and e.C_METVER != "SCREEN":
        e.errhdl(e.PATH, m, "W", "397", e.C_METVER)
    elif not e.SCREEN and e.C_METVER == "SCREEN":
        e.errhdl(e.PATH, m, "W", "398", "        ")
    elif not e.SCREEN:
        vals, ios, _n = fread("(1X,I5)", e.C_METVER.ljust(6), ("i",))
        if ios != 0:
            e.errhdl(e.PATH, m, "W", "396", e.C_METVER)
            e.L_OLDMETVER = True
        else:
            metver = vals[0]
            if metver > 90000 or metver < 12345:
                e.DUMMY = fwrite("(2X,I5.5)", metver)[0]
                e.errhdl(e.PATH, m, "E", "395", e.DUMMY)
            elif 12345 <= metver < 14134:
                e.DUMMY = fwrite("(2X,I5.5)", metver)[0]
                e.errhdl(e.PATH, m, "W", "396", e.DUMMY)
                e.L_OLDMETVER = True
    if not cssi and e.IDSURF != 0:
        e.errhdl(e.PATH, m, "W", "531", "SURFDATA")
    elif issi != e.IDSURF:
        e.errhdl(e.PATH, m, "W", "530", "SURFDATA")
    if not cusi and e.IDUAIR != 0:
        e.errhdl(e.PATH, m, "W", "531", "UAIRDATA")
    elif iusi != e.IDUAIR:
        e.errhdl(e.PATH, m, "W", "530", "UAIRDATA")
    if e.IMSTAT[9] == 1:
        if not cosi and e.IDSITE != 0:
            e.errhdl(e.PATH, m, "W", "531", "SITEDATA")
        elif iosi != e.IDSITE:
            e.errhdl(e.PATH, m, "W", "530", "SITEDATA")
    dcdlat(e)


def dcdlat(e):
    """DCDLAT (aermod.f): latitud de la cabecera del .sfc."""
    m = "DCDLAT"
    e.PATH = "ME"
    a = e.ALAT
    if "N" in a or "n" in a:
        e.TSIGN = 1.0
        vals, ios, _n = fread("(F9.1)", a.ljust(10), ("f",))
        if ios != 0:
            e.errhdl(e.PATH, m, "W", "382", a)
            return
        e.XLAT = vals[0]
        if e.XLAT > 90.0 or e.XLAT < 0.0:
            e.errhdl(e.PATH, m, "W", "381", a)
    elif "S" in a or "s" in a:
        e.TSIGN = -1.0
        vals, ios, _n = fread("(F9.1)", a.ljust(10), ("f",))
        if ios != 0:
            e.errhdl(e.PATH, m, "W", "382", a)
            return
        e.XLAT = vals[0]
        if e.XLAT > 90.0 or e.XLAT < 0.0:
            e.errhdl(e.PATH, m, "W", "381", a)
    else:
        e.errhdl(e.PATH, m, "W", "382", a)


def dayrng(e):
    """DAYRNG: días y rangos de días que se procesan (DAYRANGE): días julianos sueltos (n), rangos
    (n1-n2) y fechas mes/día sueltas o en rango, con el año ISYEAR de SURFDATA."""
    m = "DAYRNG"
    if e.IFC < 3:
        e.errhdl(e.PATH, m, "E", "200", e.KEYWRD)
        return
    ip, ipl = e.IPROC, e.IPROCL
    no_bis = (e.ISYEAR % 4 != 0) or (e.ISYEAR % 100 == 0 and e.ISYEAR % 400 != 0)
    loc = e.__dict__.setdefault("_dayrng_loc", {"IDY1": 0, "IMN1": 0})

    def leer(c):
        e.FNUM, imit = stonum(c, 8, e.FNUM)
        e.IMIT = imit
        if imit != 1:
            e.errhdl(e.PATH, m, "E", "208", e.KEYWRD)
            return None
        return nint(e.FNUM)

    for i in range(3, e.IFC + 1):
        rmark, begrng, endrng = fsplit(e, e.PATH, e.KEYWRD, e.FIELD[i], ILEN_FLD, "-")
        begrng, endrng = begrng[:8], endrng[:8]
        gmark, cmn1, cdy1 = fsplit(e, e.PATH, e.KEYWRD, begrng, 8, "/")
        cmn2 = cdy2 = ""
        if rmark and gmark:
            gmark, cmn2, cdy2 = fsplit(e, e.PATH, e.KEYWRD, endrng, 8, "/")
        cmn1, cdy1, cmn2, cdy2 = cmn1[:8], cdy1[:8], cmn2[:8], cdy2[:8]
        if not rmark and not gmark:
            v = leer(begrng)
            if v is None:
                continue
            e.JDAY = v
            if 1 <= e.JDAY <= 366:
                ip[e.JDAY] = 1
                ipl[e.JDAY] = 1
            else:
                e.errhdl(e.PATH, m, "E", "203", "Juli Day")
            if e.JDAY < e.ISJDAY or e.JDAY > e.IEJDAY:
                e.errhdl(e.PATH, m, "W", "350", i8(e.JDAY))
        elif rmark and not gmark:
            jb = leer(begrng)
            if jb is None:
                continue
            je = leer(endrng)
            if je is None:
                continue
            if jb <= je and jb >= 1 and je <= 366:
                ip[jb:je + 1] = 1
                ipl[jb:je + 1] = 1
            else:
                e.errhdl(e.PATH, m, "E", "203", "Juli Day")
            if jb < e.ISJDAY or je > e.IEJDAY:
                e.errhdl(e.PATH, m, "W", "350", fwrite('(I3,"-",I3)', jb, je)[0])
        elif not rmark and gmark:
            imn = leer(cmn1)
            if imn is None:
                continue
            idy = leer(cdy1)
            if idy is None:
                continue
            e.JDAY = e.julian(e.ISYEAR, imn, idy)
            if no_bis:
                if 1 <= e.JDAY <= 365:
                    ip[e.JDAY] = 1
                    if imn > 2:
                        ipl[e.JDAY + 1] = 1
                    else:
                        ipl[e.JDAY] = 1
                else:
                    e.errhdl(e.PATH, m, "E", "203", "Juli Day")
            else:
                if 1 <= e.JDAY <= 366:
                    ipl[e.JDAY] = 1
                    if imn > 2:
                        ip[e.JDAY - 1] = 1
                    else:
                        ip[e.JDAY] = 1
                else:
                    e.errhdl(e.PATH, m, "E", "203", "Juli Day")
            if e.JDAY < e.ISJDAY or e.JDAY > e.IEJDAY:
                e.errhdl(e.PATH, m, "W", "350", i8(e.JDAY))
        elif rmark and gmark:
            v = leer(cmn1)
            if v is not None:
                loc["IMN1"] = v
                v = leer(cdy1)
                if v is not None:
                    loc["IDY1"] = v
            imn2 = leer(cmn2)
            if imn2 is None:
                continue
            idy2 = leer(cdy2)
            if idy2 is None:
                continue
            jb = e.julian(e.ISYEAR, loc["IMN1"], loc["IDY1"])
            je = e.julian(e.ISYEAR, imn2, idy2)
            if no_bis:
                if jb <= je and jb >= 1 and je <= 365:
                    ip[jb:je + 1] = 1
                    ipl[jb:je + 1] = 1
                    if je == 365:
                        ipl[366] = 1
                else:
                    e.errhdl(e.PATH, m, "E", "203", "Juli Day")
            else:
                if jb <= je and jb >= 1 and je <= 366:
                    ipl[jb:je + 1] = 1
                    for k in range(jb, je + 1):
                        if k <= 59:
                            ip[k] = 1
                        elif k > 60:
                            ip[k - 1] = 1
                else:
                    e.errhdl(e.PATH, m, "E", "203", "Juli Day")
            if jb < e.ISJDAY or je > e.IEJDAY:
                e.errhdl(e.PATH, m, "W", "350", fwrite('(I3,"-",I3)', jb, je)[0])
        else:
            e.errhdl(e.PATH, m, "E", "203", "DAYRANGE")
