# -*- coding: utf-8 -*-
"""Traducción de AERMET 26135 (US EPA, dominio público): subrutinas comunes de MAIN1.

leapyr, checkfile, dataline, getdates, getfields, checkdates, getloc, coord, var_list,
range_mod, getunit, numdays, data_dates, humidity, pressure, datetime, start_stop.
"""
import datetime as _dt
import math
import os

from .estado import OUTPUT_UNIT
from .formato import ch, sub, lread, fread, fx

MESES = [None, "JANUARY", "FEBRUARY", "MARCH", "APRIL", "MAY", "JUNE", "JULY", "AUGUST",
         "SEPTEMBER", "OCTOBER", "NOVEMBER", "DECEMBER"]


def pid(E, ip=None):
    """adjustl(pathid(ipath)) como CHARACTER*10."""
    m = E.m
    if ip is None:
        ip = m.ipath
    if 1 <= ip <= m.npath:
        return fx(m.pathid[ip], 10)
    return fx("", 10)


def leapyr(iyear):
    return not (iyear % 4 != 0 or (iyear % 100 == 0 and iyear % 400 != 0))


def fmt_msg(E, sufijo):
    return E.m.msg_form.strip() + sufijo


def datetime(E, i, ahora=None):
    t = ahora or _dt.datetime.now()
    E.m.runtimes[i] = [None, t.year, t.month, t.day, 0, t.hour, t.minute, t.second,
                       t.microsecond // 1000]


def start_stop(E, i, ifile):
    rt = E.m.runtimes[i]
    if rt[5] <= 11:
        hr = rt[5]
        ampm = "AM"
    else:
        hr = 12 + (rt[5] - 12)
        ampm = "PM"
    stri = "START" if i == 1 else "END"
    E.w(ifile, "(3(1x,a),1x,i2.2,a1,1x,i4,2x,i2,a1,i2.2,a1,i2.2,1x,a2)", stri,
        "PROCESSING DATE/TIME:", MESES[rt[2]], rt[3], ",", rt[1], hr, ":", rt[6], ":", rt[7], ampm)


def getunit(E):
    m = E.m
    if m.lkey[2]:
        if E.abierto(m.msgfile) and m.msgfile.strip():
            m.writeunit = m.msg_unit
        else:
            m.writeunit = OUTPUT_UNIT
    else:
        m.writeunit = OUTPUT_UNIT


def checkfile(E, iunit, fname, itype):
    """Devuelve (fname, lgood). fname puede perder las comillas."""
    m = E.m
    ftypes = [None, "old", "replace", "new", "unknown"]
    form_str = fmt_msg(E, "3(a,1x),a)")
    fname = fname.strip()
    flen = len(fname)
    if flen > 0 and ((fname[0] == '"' and fname[-1] == '"') or (fname[0] == "'" and fname[-1] == "'")):
        fname = (" " + fname[1:-1] + " ") if flen > 1 else " "
    nombre = fname.strip()
    lopened = E.abierto(nombre) if nombre else False
    lexist = False
    if not lopened:
        if itype == 1:
            lexist = bool(nombre) and os.path.isfile(nombre)
            if lexist:
                E.abrir(iunit, nombre, ftypes[itype])
        elif itype != 3:
            lexist = bool(nombre) and os.path.isfile(nombre)
            if not lexist:
                io = E.abrir(iunit, nombre, ftypes[itype]) if nombre else 29
                lexist = io == 0
            else:
                E.abrir(iunit, nombre, ftypes[itype])
        else:
            io = E.abrir(iunit, nombre, ftypes[itype]) if nombre else 29
            lexist = io == 0
    else:
        lexist = True
    lgood = True
    if not lexist:
        E.w(m.writeunit, form_str, pid(E), "E02", fx("CHECKFILE", 10), "INVALID",
            m.keywrd[m.ikey].strip(), "FILENAME:", fname.strip())
        m.lbad = True
        lgood = False
    if lopened:
        E.w(m.writeunit, form_str, pid(E), "E02", fx("CHECKFILE", 10), "DUPLICATE",
            m.keywrd[m.ikey].strip(), "FILENAME:", fname.strip())
        m.lbad = True
        lgood = False
    else:
        if lexist:
            lgood = True
        else:
            lgood = False
            m.lbad = True
    return fname, lgood


def dataline(E, i, i1):
    m = E.m
    L = m.inpline1
    ilen = m.ilen
    m.fileind = [0, 0, 0]
    m.formind = [0, 0, 0]
    q1 = q2 = False
    j = i + i1
    while j <= ilen and m.fileind[2] == 0:
        cj = ch(L, j)
        if (cj == '"' or cj == "'") and (ch(L, j - 1) == " " or ch(L, j + 1) == " "):
            if not q1:
                q1 = True
            else:
                q2 = True
        if (ch(L, j - 1) == " " or ch(L, j + 1) == " ") and cj != " ":
            if m.fileind[1] == 0:
                m.fileind[1] = j
            else:
                if (q1 and q2) or (not q1 and not q2):
                    m.fileind[2] = j
        j += 1
    if m.fileind[2] == 0:
        m.fileind[2] = ilen + 1
    j = m.fileind[2] + 1
    while j <= ilen and m.formind[2] == 0:
        if (ch(L, j - 1) == " " or ch(L, j + 1) == " ") and ch(L, j) != " ":
            if m.formind[1] == 0:
                m.formind[1] = j
            else:
                m.formind[2] = j
        j += 1
    if m.formind[2] == 0:
        m.formind[2] = ilen


def getfields(E, i1, nfield1):
    """Devuelve la lista 1..nfield1 de campos (CHARACTER*100) de inpline1 a partir de i1+1."""
    m = E.m
    L = m.inpline1
    ilen = m.ilen
    ind = [0] * (nfield1 + 2)
    ifield = 0
    for j in range(i1 + 1, ilen + 1):
        a, b = ch(L, j - 1), ch(L, j)
        if (a == " " and b not in " ,") or (a == "," and b not in " ,"):
            ifield += 1
            if ifield <= nfield1 + 1:
                ind[ifield] = j
    fields = [None]
    for k in range(1, nfield1 + 1):
        if k != nfield1:
            t = sub(L, ind[k], ind[k + 1] - 1)
        else:
            t = sub(L, ind[k], ilen)
        t = fx(t, 100)
        lt = len(t.rstrip(" "))
        if lt > 0 and t[lt - 1] == ",":
            t = t[:lt - 1] + " " + t[lt:]
        fields.append(t)
    return fields


def checkdates(E, iyear, imonth, iday, istartend):
    """Devuelve (idate o None, lgood)."""
    m = E.m
    timestr1 = [None, "START", "END"]
    timestr2 = [None, "YEAR", "MONTH", "DAY"]
    formstr = fmt_msg(E, "2(a,1x),2(a),1x,i8)")
    lgood = True
    leap = False
    modnam = fx("CHECKDATES", 10)
    if iyear < 1000 or iyear > 9999:
        E.w(m.writeunit, formstr, pid(E), "E05", modnam, "XDATES: INVALID", timestr1[istartend],
            timestr2[1], ":", iyear)
        lgood = False
    else:
        leap = leapyr(iyear)
    if imonth < 1 or imonth > 12:
        E.w(m.writeunit, formstr, pid(E), "E05", modnam, "XDATES: INVALID", timestr1[istartend],
            timestr2[2], ":", imonth)
        lgood = False
        if iday < 1 or iday > 31:
            E.w(m.writeunit, formstr, pid(E), "E05", modnam, "XDATES: INVALID",
                timestr1[istartend], timestr2[3], ":", iday)
            lgood = False
    else:
        day1 = m.days[imonth] + 1 if (imonth == 2 and leap) else m.days[imonth]
        if iday < 1 or iday > day1:
            E.w(m.writeunit, formstr, pid(E), "E05", modnam, "XDATES: INVALID",
                timestr1[istartend], timestr2[3], ":", iday)
            lgood = False
    return (iyear * 10000 + imonth * 100 + iday if lgood else None), lgood


def getdates(E, i1):
    """GETDATES: devuelve (startdate, enddate, dates1) con dates1[ii][j] (1..2, 1..3)."""
    m = E.m
    modnam = fx("GETDATES", 10)
    nfield1 = m.nfield - 1
    dates1 = [[0] * 4 for _ in range(3)]
    startdate = 0
    enddate = 0
    adates = [[None, "-999", "-999", "-999"], [None, "-999", "-999", "-999"],
              [None, "-999", "-999", "-999"]]
    formstr1 = fmt_msg(E, "a,1x,a)")
    formstr2 = fmt_msg(E, "(3(a,1x),a)")
    formstr3 = fmt_msg(E, "a,1x,i8,1x,a,1x,i8)")
    timestr1 = [None, "START", "END"]
    timestr2 = [None, "YEAR", "MONTH", "DAY"]
    datefields = getfields(E, i1, nfield1)
    datefields1 = [None] * (nfield1 + 1)
    if nfield1 == 3 or nfield1 == 7:
        ifield = 2 if nfield1 == 3 else 4
        if datefields[ifield].strip() not in ("TO", "-"):
            E.w(m.writeunit, formstr1, pid(E), "E05", modnam, "INVALID DATE SEPARATOR FOR:",
                m.inpline1.strip())
            m.lbad = True
    if not m.lbad:
        ii = 0
        if nfield1 == 2 or nfield1 == 3:
            istep = 1 if nfield1 == 2 else 2
            for ifield in range(1, nfield1 + 1, istep):
                ii += 1
                lsep = False
                datefields1[ifield] = datefields[ifield]
                df = list(datefields[ifield])
                for j in range(len(datefields[ifield].rstrip(" "))):
                    c = df[j]
                    if c == "/" or c == "-":
                        df[j] = " "
                        lsep = True
                    else:
                        if (c != " " and ord(c) < 48) or ord(c) > 57:
                            m.lbad = True
                            E.w(m.writeunit, formstr1, pid(E), "E05", modnam,
                                "XDATES: INVALID CHARACTER IN FIELD", datefields1[ifield])
                datefields[ifield] = "".join(df)
                if not m.lbad:
                    if lsep:
                        v, io, _ = lread(datefields[ifield], [("a", 10)] * 3)
                        for j in range(len(v)):
                            adates[ii][j + 1] = v[j]
                    else:
                        v, io, _ = fread("(a4,2(a2))", datefields[ifield], [("a", 10)] * 3)
                        for j in range(len(v)):
                            adates[ii][j + 1] = v[j]
        else:
            for j in range(1, 4):
                v, io, _ = lread(datefields[j], [("a", 10)])
                if v:
                    adates[1][j] = v[0]
            istep = 0 if nfield1 == 6 else 1
            for j in range(1, 4):
                v, io, _ = lread(datefields[istep + 3 + j], [("a", 10)])
                if v:
                    adates[2][j] = v[0]
        if not m.lbad:
            for ii in (1, 2):
                iflag = [None, 0, 0, 0]
                idates = [None, -9, -9, -9]
                for j in (1, 2, 3):
                    v, io, _ = lread(adates[ii][j], ["i"])
                    iflag[j] = io
                    if io == 0:
                        idates[j] = v[0]
                    else:
                        E.w(m.writeunit, formstr2, pid(E), "E05", modnam, "XDATES: INVALID",
                            timestr1[ii], timestr2[j], adates[ii][j].strip())
                        m.lbad = True
                if iflag[1] == 0 and iflag[2] == 0 and iflag[3] == 0:
                    d, lgood = checkdates(E, idates[1], idates[2], idates[3], ii)
                    if lgood:
                        if ii == 1:
                            startdate = d
                        else:
                            enddate = d
                        for j in (1, 2, 3):
                            dates1[ii][j] = idates[j]
                    if not lgood:
                        m.lbad = True
        if not m.lbad:
            if startdate > enddate:
                E.w(m.writeunit, formstr3, pid(E), "E05", modnam, "XDATES: START DATE", startdate,
                    "IS AFTER END DATE", enddate)
                m.lbad = True
    return startdate, enddate, dates1


def coord(E, lfield):
    """COORD: lfield es CHARACTER*40 (se ve sólo lo que cabe)."""
    m = E.m
    lfield = fx(lfield, 40)
    modnam = fx("COORD", 10)
    formstr1 = fmt_msg(E, "a,1x,a)")
    formstr2 = fmt_msg(E, "2(a,1x),f11.4)")
    e = w = n = s = badloc = inum = 0
    nogood = False
    lt = len(lfield.rstrip(" "))
    for j in range(1, lt + 1):
        c = lfield[j - 1]
        if c == "E":
            e += 1
        elif c == "W":
            w += 1
        elif c == "N":
            n += 1
        elif c == "S":
            s += 1
        elif c == "." or "0" <= c <= "9":
            inum += 1
        else:
            badloc += 1
        if j == lt and c not in "EWNS":
            badloc += 1
    if e + w + n + s != 1:
        badloc += 1
    valor = 0.0
    if badloc != 0:
        E.w(m.writeunit, formstr1, pid(E), "E05", modnam, "INVALID FORMAT FOR STATION COORDINATE:",
            lfield.strip())
        nogood = True
    else:
        e = lfield.find("E") + 1
        w = lfield.find("W") + 1
        n = lfield.find("N") + 1
        s = lfield.find("S") + 1
        if e > 0:
            mult, k = 1.0, e
        elif w > 0:
            mult, k = -1.0, w
        elif n > 0:
            mult, k = 1.0, n
        else:
            mult, k = -1.0, s
        v, io, _ = lread(lfield[:k - 1], ["f"])
        if io != 0:
            E.w(m.writeunit, formstr1, pid(E), "E05", modnam,
                "INVALID FORMAT FOR STATION COORDINATE:", lfield.strip())
            m.lbad = True
            valor = 0.0
        else:
            valor = v[0]
            if e > 0 or w > 0:
                if valor < 0.0 or valor > 180.0:
                    E.w(m.writeunit, formstr2, pid(E), "E05", modnam, "INVALID VALUE FOR STATION",
                        "LONGITUDE", valor)
                    nogood = True
            else:
                if valor < 0.0 or valor > 90.0:
                    E.w(m.writeunit, formstr2, pid(E), "E05", modnam, "INVALID VALUE FOR STATION",
                        "LATITUDE", valor)
                    nogood = True
    if nogood:
        m.lbad = True
        return -999.0
    return valor * mult


def getloc(E, i1, lgmt2lst, lelev):
    """GETLOC: devuelve dict con stid, lat, lon, gmt2lst, elev, lgmt2lst, lelev."""
    m = E.m
    modnam = fx("GETLOC", 10)
    stid = "0"
    gmt2lst = 0
    lat = -999.0
    lon = -999.0
    elev = 0.0
    formstr1 = fmt_msg(E, "a,1x,a)")
    formstr2 = fmt_msg(E, "i6,1x,a)")
    formstr3 = fmt_msg(E, "i6,1x,a,1x,f10.4)")
    nfield1 = m.nfield - 1
    locfields = getfields(E, i1, nfield1)
    v, io, _ = lread(locfields[1], [("a", 8)])
    if io == 0 or v:
        stid = v[0]
    ifield = 2
    for ifield in (2, 3):
        lf = locfields[ifield]
        if "E" in lf or "W" in lf:
            lon = coord(E, lf)
        elif "N" in lf or "S" in lf:
            lat = coord(E, lf)
        else:
            E.w(m.writeunit, formstr1, pid(E), "E05", modnam, "INVALID FORMAT FOR STATION COORDINATE",
                lf.strip())
            m.lbad = True
    ifield = 4
    if nfield1 >= 4:
        lgmt2lst = True
        v, io, _ = lread(locfields[4], ["i"])
        if io != 0:
            m.lbad = True
            E.w(m.writeunit, formstr1, pid(E), "E05", modnam, "INVALID FORMAT FOR TIME ZONE ADJUSTMENT:",
                locfields[ifield].strip())
        else:
            gmt2lst = v[0]
            if abs(gmt2lst) > 12:
                E.w(m.writeunit, formstr2, pid(E), "E05", modnam, gmt2lst,
                    "EXCEEDS 12 HOUR ADJUSTMENT FOR TIME ZONE ADJUSTMENT")
                m.lbad = True
            if (gmt2lst > 0 and lon > 0.0) or (gmt2lst < 0 and lon < 0.0):
                E.w(m.writeunit, formstr3, pid(E), "W04", modnam, gmt2lst,
                    "GMT TO LST IS INCORRECT SIGN FOR LONGITUDE OF", lon)
                if abs(gmt2lst) > 3:
                    E.w(m.writeunit, formstr2, pid(E), "E05", modnam, gmt2lst,
                        "GMT TO LST IS MORE THAN THREE HOURS")
                    m.lbad = True
    if nfield1 == 5:
        lelev = True
        v, io, _ = lread(locfields[5], ["f"])
        if io != 0:
            m.lbad = True
            E.w(m.writeunit, formstr1, pid(E), "E05", modnam, "INVALID FORMAT FOR STATION ELEVATION:",
                locfields[5].strip())
        else:
            elev = v[0]
    return dict(stid=stid.rstrip(), lat=lat, lon=lon, gmt2lst=gmt2lst, elev=elev,
                lgmt2lst=lgmt2lst, lelev=lelev)


def var_list(E, i1, nfield1, varnam, varlogic, nvar):
    """VAR_LIST: varnam/varlogic con índices 1..nvar; modifica varlogic."""
    m = E.m
    modnam = fx("VAR_LIST", 10)
    formstr = fmt_msg(E, "3(a,1x),a)")
    varnam1 = getfields(E, i1, nfield1)
    for ifield in range(1, nfield1 + 1):
        ivar = 1
        lfound = False
        v1 = varnam1[ifield]
        lt = len(v1.rstrip(" "))
        while ivar <= nvar and not lfound and (lt == 4 or lt == 2):
            if v1.strip() == varnam[ivar].strip():
                lfound = True
                if not varlogic[ivar]:
                    varlogic[ivar] = True
                else:
                    E.w(m.writeunit, formstr, pid(E), "W02", modnam, "DUPLICATING LISTING OF VARIABLE",
                        v1.strip(), "ON INPUT LINE FOR KEYWORD:", m.keywrd[m.ikey].strip())
            else:
                if (m.ipath == 4 or m.ipath == 5) and ivar >= 26 and v1[0:2] == varnam[ivar][0:2]:
                    a, io1, _ = lread(v1[2:4], ["i"])
                    b, io2, _ = lread(fx(varnam[ivar], 4)[2:4], ["i"])
                    ilev = a[0] if io1 == 0 else 0
                    nlev = b[0] if io2 == 0 else 0
                    if (io1 == 0 and io2 == 0 and ilev <= nlev) or lt == 2:
                        lfound = True
                        if not varlogic[ivar]:
                            varlogic[ivar] = True
                        else:
                            E.w(m.writeunit, formstr, pid(E), "W02", modnam,
                                "DUPLICATING LISTING OF VARIABLE", v1[0:2].strip(),
                                "ON INPUT LINE FOR KEYWORD:", m.keywrd[m.ikey].strip())
                    else:
                        ivar += 1
                else:
                    ivar += 1
        if not lfound:
            if nfield1 == 1 and varnam1[nfield1].strip() == "ALL":
                for k in range(1, nvar + 1):
                    varlogic[k] = True
            else:
                E.w(m.writeunit, formstr, pid(E), "E05", modnam, "INVALID VARIABLE NAME FOR",
                    m.keywrd[m.ikey].strip(), "KEYWORD", v1.strip())
                m.lbad = True


def range_mod(E, v1, v2, v3, v4):
    """Devuelve (linc, lowval, hival, missval, lgood)."""
    m = E.m
    modnam = fx("RANGE_MOD", 10)
    formstr = fmt_msg(E, "a,1x,a)")
    lowval, hival, missval = -9, -9, 0
    linc = False
    v1, v2, v3, v4 = fx(v1, 40), fx(v2, 40), fx(v3, 40), fx(v4, 40)
    r, io, _ = lread(v1, ["i"])
    if io != 0:
        E.w(m.writeunit, formstr, pid(E), "E05", modnam, "INVALID VALUE FOR LOWER BOUND", v1.strip())
        m.lbad = True
    else:
        lowval = r[0]
    if v2.strip() == "<":
        linc = False
    elif v2.strip() == "<=":
        linc = True
    else:
        m.lbad = True
        E.w(m.writeunit, formstr, pid(E), "E05", modnam, "INVALID VALUE FOR RANGE INCLUSION KEY:",
            v2.strip())
    r, io, _ = lread(v3, ["i"])
    if io != 0:
        E.w(m.writeunit, formstr, pid(E), "E05", modnam, "INVALID VALUE FOR UPPER BOUND", v3.strip())
        m.lbad = True
    else:
        hival = r[0]
    r, io, _ = lread(v4, ["i"])
    if io != 0:
        E.w(m.writeunit, formstr, pid(E), "E05", modnam, "INVALID VALUE FOR MISSING VALUE", v4.strip())
        m.lbad = True
    else:
        missval = r[0]
    lgood = not m.lbad
    return linc, lowval, hival, missval, lgood


def _juliano(fecha):
    iyear = fecha // 10000
    imonth = (fecha // 100) % 100
    iday = fecha % 100
    jday1 = (imonth + 9) % 12
    jday2 = (jday1 * 153 + 2) // 5 + iday + 58
    if leapyr(iyear):
        ndays = 366
        jday2 += 1
    else:
        ndays = 365
    return iyear, 1 + jday2 % ndays


def numdays(start1, end1):
    y1, j1 = _juliano(start1)
    y2, j2 = _juliano(end1)
    n365 = n366 = 0
    for i in range(y1, y2):
        if leapyr(i):
            n366 += 1
        else:
            n365 += 1
    return j2 + n365 * 365 + n366 * 366 - j1 + 1


def jday(iyear, imonth, iday):
    iw1 = (imonth + 9) % 12
    iw2 = (iw1 * 153 + 2) // 5 + iday + 58
    if leapyr(iyear):
        iw3 = 366
        iw2 += 1
    else:
        iw3 = 365
    return 1 + iw2 % iw3


def data_dates(E, ihr, iday, imonth, iyear, gmt2lst, istart, iend, ierr):
    """DATA_DATES. Devuelve (ihr, iday, imonth, iyear, idate, lgo) tras la conversión GMT→LST."""
    m = E.m
    formstr = fmt_msg(E, "a,1x,2(a),1x,i8)")
    modnam = fx("DATA_DATES", 10)
    ecode = "E%02d" % ierr
    timestr2 = [None, "YEAR", "MONTH", "DAY", "HOUR"]
    idate = 0
    lgo = False
    leap = False
    if iyear < 1000 or iyear > 9999:
        E.w(m.msg_unit, formstr, pid(E), ecode, modnam, "INVALID", timestr2[1], ":", iyear)
        m.lbad = True
    else:
        leap = leapyr(iyear)
    if imonth < 1 or imonth > 12:
        E.w(m.msg_unit, formstr, pid(E), ecode, modnam, "INVALID", timestr2[2], ":", imonth)
        m.lbad = True
        if iday < 1 or iday > 31:
            E.w(m.msg_unit, formstr, pid(E), ecode, modnam, "INVALID", timestr2[3], ":", iday)
            m.lbad = True
    else:
        day1 = m.days[imonth] + 1 if (imonth == 2 and leap) else m.days[imonth]
        if iday < 1 or iday > day1:
            E.w(m.msg_unit, formstr, pid(E), ecode, modnam, "INVALID", timestr2[3], ":", iday)
            m.lbad = True
    if not m.lbad:
        if ihr < 0 or ihr > 24:
            E.w(m.msg_unit, formstr, pid(E), ecode, modnam, "INVALID", timestr2[4], ":", ihr)
            m.lbad = True
        else:
            ihr = ihr - gmt2lst
            if ihr <= 0:
                nd = abs(ihr) // 24 if ihr < -24 else 1
                ihr = 24 + ihr
                iday = iday - nd
                if iday <= 0:
                    imonth -= 1
                    if imonth == 0:
                        imonth = 12
                        iyear -= 1
                    iday = m.days[imonth] + 1 if (imonth == 2 and leap) else m.days[imonth]
                    if nd > 1:
                        iday = iday - nd + 1
            elif ihr > 24:
                nd = ihr // 24 if ihr > 36 else 1
                ihr = ihr - 24
                iday = iday + nd
                lastday = m.days[imonth] + 1 if (imonth == 2 and leap) else m.days[imonth]
                if iday > lastday:
                    iday = 1
                    imonth += 1
                    if imonth == 13:
                        imonth = 1
                        iyear += 1
                    if nd > 1:
                        iday = iday + nd - 1
    if not m.lbad:
        idate = iyear * 10000 + imonth * 100 + iday
    if not m.lbad and istart <= idate <= iend:
        lgo = True
    return ihr, iday, imonth, iyear, idate, lgo


def humidity(db, dp):
    dbk = db + 273.15
    dpk = dp + 273.15
    ttdb = (1.0 / 273.15) - (1.0 / dbk)
    ttdp = (1.0 / 273.15) - (1.0 / dpk)
    vpsat = 6.11 * math.exp(5418.0 * ttdb)
    vpact = 6.11 * math.exp(5418.0 * ttdp)
    return float(int(100.0 * (vpact / vpsat)))


def pressure(E, iopt, elev, tv, inp_pres):
    denom = E.m.r * tv / E.m.g
    if iopt == 1:
        return inp_pres * math.exp(elev / denom)
    return inp_pres * math.exp(-elev / denom)
