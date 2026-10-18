# -*- coding: utf-8 -*-
"""Traducción de AERMOD 26135 (US EPA, dominio público): concentraciones de fondo (BACKGRND):
BGEXT de aermod.f (lectura del fichero horario de fondo) y el paso horario de HRLOOP. Las
tarjetas SO están en entrada_fuentes.py, BGVAL en funciones_dispersion.py y SUMBACK en resultados.py."""
from . import funciones_dispersion
from .formato import fread, fwrite, lread
from .meteo_horaria import cent_date2


def _leer(e, i, tipos):
    """READ(IBGUNT(I),*) o READ(IBGUNT(I),BGFORM(I)). Devuelve (valores, iostat)."""
    u = e.U[int(e.IBGUNT[i])]
    if u.ptr >= len(u.regs):
        return None, -1
    regs = u.regs[u.ptr:u.ptr + 20]
    if e.BGFORM[i] == "FREE":
        vals, ios, nr = lread(regs, tipos, e._BG_PREVIOS[:len(tipos)])
    else:
        vals, ios, nr = fread(e.BGFORM[i], regs, tipos)
    u.ptr += nr
    if ios == 0:
        e._BG_PREVIOS[:len(vals)] = vals
    return vals, ios


def bgext(e):
    """BGEXT: valor de fondo de la hora desde el fichero horario del sector en curso (los ficheros
    de los demás sectores se leen para mantenerlos sincronizados); si falta, se sustituye por el
    valor variable del sector. Devuelve (L_ReadErr, ReadErr, EndErr)."""
    m = "BGEXT"
    if not hasattr(e, "_BG_FULLBGHR"):
        # FULLBGHR es local sin inicializar en el original: conserva el valor de la llamada
        # anterior (mismo marco de pila); se emula guardándolo entre llamadas
        e._BG_FULLBGHR = [0] * 7
        e._BG_PREVIOS = [0, 0, 0, 0, 0.0]
    readerr = enderr = ""
    e.ILINE = e.IBLINE
    bghrval = -99.0
    bgsub = [0.0] * 7
    full = e._BG_FULLBGHR
    for i in range(1, e.NUMBGSECTS + 1):
        if e.L_BGVALUES[i]:
            bgsub[i] = funciones_dispersion.bgval(e, i, bgsub[i])
        if not e.L_BGFILE[i]:
            continue
        readerr = fwrite("('SECT',I1)", i)[0]
        if i == e.IBGSECT:
            vals, ios = _leer(e, i, ("i", "i", "i", "i", "f"))
            if ios < 0:
                e.EOF = True
                enderr = fwrite("('SECT',I1)", i)[0]
                continue
            if ios > 0:
                return True, readerr, enderr
            ibgyr, ibgmn, ibgdy, ibghr, bghrval = vals
            if bghrval > 0.0:
                bu = e.BACKUNITS
                if e.POLLUT == "NO2":
                    if bu == "PPB":
                        bghrval = bghrval / e.NO2_PPB
                    elif bu == "PPM":
                        bghrval = bghrval / e.NO2_PPM
                elif e.POLLUT == "SO2":
                    if bu == "PPB":
                        bghrval = bghrval / e.SO2_PPB
                    elif bu == "PPM":
                        bghrval = bghrval / e.SO2_PPM
                elif e.POLLUT == "CO":
                    if bu == "PPB":
                        bghrval = bghrval * e.CO_PPB
                    elif bu == "PPM":
                        bghrval = bghrval * e.CO_PPM
        else:
            vals, ios = _leer(e, i, ("i", "i", "i", "i"))
            if ios < 0:
                e.EOF = True
                enderr = fwrite("('SECT',I1)", i)[0]
                continue
            if ios > 0:
                return True, readerr, enderr
            ibgyr, ibgmn, ibgdy, ibghr = vals
        if ibgyr <= 99:
            _dos, ibgyr = cent_date2(e, 0, ibgyr)
        full[i] = ibgyr * 1000000 + ibgmn * 10000 + ibgdy * 100 + ibghr
    for i in range(1, e.NUMBGSECTS + 1):
        if e.L_BGFILE[i] and e.FULLDATE != full[i]:
            e.errhdl(e.PATH, m, "E", "454", fwrite("(I10.10,'s',I1)", e.FULLDATE, i)[0])
            e.RUNERR = True
    if e.RUNERR:
        return False, readerr, enderr
    if bghrval < 0.0:
        ib = e.IBGSECT
        if ib > 0:
            if e.L_BGFILE[ib]:
                if e.L_BGVALUES[ib]:
                    e.BGCONC = bgsub[ib]
                    e.errhdl(e.PATH, m, "I", "453", fwrite("(I10.10,'s',I1)", e.FULLDATE, ib)[0])
                    e.NSUBBGHOUR += 1
                else:
                    e.errhdl(e.PATH, m, "E", "452", fwrite("(I10.10,'s',I1)", e.FULLDATE, ib)[0])
                    e.RUNERR = True
            elif e.L_BGVALUES[ib]:
                e.BGCONC = bgsub[ib]
        else:
            e.BGCONC = 0.0
    else:
        e.BGCONC = bghrval
    return False, readerr, enderr


def fondo_hora(e):
    """Paso de HRLOOP para el fondo: fichero horario (BGEXT) o valores variables (BGVAL)."""
    m = "HRLOOP"
    if e.L_BGHOURLY:
        e.IBLINE += 1
        l_err, readerr, enderr = bgext(e)
        if e.EOF:
            e.errhdl(e.PATH, m, "E", "580", fwrite("('BGFILE ',A5)", enderr)[0])
            e.RUNERR = True
        elif l_err:
            e.errhdl(e.PATH, m, "E", "510", fwrite("('BGFILE ',A5)", readerr)[0])
            e.RUNERR = True
    elif e.IBGSECT > 0 and e.L_BGVALUES[e.IBGSECT]:
        e.BGCONC = funciones_dispersion.bgval(e, e.IBGSECT, e.BGCONC)
    else:
        e.BGCONC = 0.0
    if e.RUNERR:
        return
    if not e.RSTINP and e.L_MAXDCONT and e.FULLDATE >= e.ISDATE:
        e.ABGCONC[e.IHR_NDX, e.IYR_NDX] = e.BGCONC
