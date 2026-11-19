# -*- coding: utf-8 -*-
"""Traducción de AERMET 26135 (US EPA, dominio público): módulo SURFACE (estación de superficie).

Lectura del control, extracción de los formatos globales ISHD (NOAA ISD) y GHCN-h y del
EXTRACT/QAOUT, duplicados, ASOS, auditoría, ficheros EXTRACT/QAOUT, datos de 1 minuto (AERMINUTE).
Fuera de alcance: CD144, SCRAM, SAMSON y HUSWO (formatos antiguos de EE. UU.)."""
import datetime as _dt
import math
from itertools import accumulate

from . import tablas as T
from .comun import (checkfile, data_dates, dataline, fmt_msg, getdates, getfields, getloc, getunit,
                    humidity, leapyr, numdays, pid, pressure, range_mod, var_list)
from .estado import OUTPUT_UNIT, Formato, Svar, arr
from .formato import (FORRTL_CONV_FORMATO, FORRTL_EOF_LISTA, ErrorEjecucion, ch, fread, fwrite, fx,
                      lread, nint, sub)
from .control_cl import NoTraducido


class SfInfo:
    __slots__ = ("sfcdate", "nsfcobs", "asos_hr", "have_obs", "sobs")


class Sf1Min:
    __slots__ = ("sf1mindate", "ifwhr", "wdir", "wspd")


def _idiv(a, b):
    """División entera de Fortran (trunca hacia cero)."""
    q = abs(a) // abs(b)
    return q if (a >= 0) == (b > 0) else -q


def sfc_init(E):
    s = E.sf
    s.sfvars = [None] + [Svar(t) for t in T.SFVARS[1:]]
    s.sfformats = [None] + [Formato(t, ("sformat", "lsfform", "validstart", "validend")) for t in T.SFFORMATS[1:]]
    ef = {1: "a,1x,a)", 2: "a,1x,i5,2(1x,a))", 3: "a,1x,i3,1x,a3,1x,a)", 4: "2(a,1x),a)", 5: "a,1x,a20)",
          6: "a,1x,i5)", 7: "a,1x,i8,1x,a,1x,i8)", 8: "a,1x,i8,1x,a,1x,a20)", 9: "a,1x,f9.2,1x,a,1x,f9.2,a)",
          10: "a,1x,a4,2(1x,a),1x,a20)"}
    for k, v in ef.items():
        s.ext_form[k] = fmt_msg(E, v)


def surf_path(E):
    m, s = E.m, E.sf
    modnam = fx("SURF_PATH", 10)
    f1 = fmt_msg(E, "a,1x,a)")
    f2 = fmt_msg(E, "i3,2(1x,a))")
    f3 = fmt_msg(E, "a,1x,i3,3(1x,a))")
    f4 = fmt_msg(E, "3(a,1x),a)")
    form1 = "(a%3d)" % m.flength
    getunit(E)
    m.lbad = False
    ikey = m.ikey
    if ikey == 0:
        s.lsfkeywords[8] = True
        sfc_init(E)
        return
    kw = m.keywrd[ikey].strip()
    i = m.inpline1.find(kw) + 1
    i1 = len(kw)
    if ikey in (4, 5, 12, 13, 32) or 7 <= ikey <= 10:
        if ikey <= 5:
            jj = ikey - 3
        elif ikey in (12, 13):
            jj = ikey - 5
        elif ikey == 32:
            jj = 9
        else:
            jj = ikey - 4
        if not s.lsfkeywords[jj]:
            s.lsfkeywords[jj] = True
        else:
            if ikey == 4 or 7 <= ikey < 11:
                E.w(m.writeunit, f1, pid(E), "E03", modnam, "DUPLICATE ENTRY OF KEYWORD:", kw)
                m.lbad = True
                return
    else:
        E.w(m.writeunit, f1, pid(E), "E03", modnam, "INVALID KEYWORD:", kw)
        m.lbad = True
        return

    def mal():
        E.w(m.writeunit, f2, pid(E), "E03", modnam, m.nfield, "IS AN INVALID NUMBER OF FIELDS FOR KEYWORD", kw)
        m.lbad = True

    if ikey == 4:
        s.sfstage1 = True
        if m.nfield < 3 or m.nfield > 6:
            mal()
        else:
            if m.nfield > 4:
                E.w(m.writeunit, f3, pid(E), "W01", modnam, "TOO MANY FIELDS", m.nfield, "FOR", kw,
                    "KEYWORD; BLOCKING FACTOR AND/OR TYPE NOT NEEDED")
            dataline(E, i, i1)
            m.sf_inpfile = sub(m.inpline, m.fileind[1], m.fileind[2])
            v, io, _ = lread(sub(m.inpline1, m.formind[1], m.formind[2]), [("a", 10)])
            fileform = v[0].strip() if v else ""
            m.sf_inpfile, lgood = checkfile(E, m.sf_data_unit, m.sf_inpfile, 1)
            j = 1
            lvalid = False
            while j <= s.nsfformats and not lvalid:
                if fileform == s.sfformats[j].sformat.strip():
                    s.sfformats[j].lsfform = True
                    lvalid = True
                    s.isfform = j
                j += 1
            if not lvalid:
                E.w(m.writeunit, f4, pid(E), "E04", modnam, "INVALID FILE FORMAT", fileform, "FOR SURFACE FILE",
                    m.sf_inpfile.strip())
                m.lbad = True
            elif lvalid and (s.sfformats[4].lsfform or s.sfformats[5].lsfform):
                E.w(m.writeunit, f4, pid(E), "E04", modnam, "OBSOLETE FILE FORMAT", fileform, "FOR SURFACE FILE",
                    m.sf_inpfile.strip())
                m.lbad = True
            if m.nfield == 4:
                v, io, _ = lread(sub(m.inpline1, m.formind[2] + 1, m.ilen), [("a", 4)])
                asosflag = v[0].strip() if v else ""
                if asosflag == "ASOS":
                    if s.sfformats[7].lsfform or s.sfformats[10].lsfform:
                        s.lasos = True
                    else:
                        E.w(m.writeunit, f1, pid(E), "E05", modnam, "ASOS FLAG NOT ALLOWED FOR DATA TYPE:",
                            s.sfformats[j - 1].sformat.strip())
                        m.lbad = True
                else:
                    if s.sfformats[7].lsfform or s.sfformats[10].lsfform:
                        E.w(m.writeunit, f1, pid(E), "E05", modnam, "INVALID VALUE FOR ASOS FLAG", asosflag)
                        m.lbad = True
                    else:
                        E.w(m.writeunit, f3, pid(E), "W01", modnam, "TOO MANY FIELDS", m.nfield, "FOR", kw,
                            "KEYWORD; BLOCKING FACTOR AND/OR TYPE NOT NEEDED")
    elif ikey == 5:
        surf_list(E, i + i1)
    elif ikey == 7:
        s.sfstage1 = True
        if m.nfield != 2:
            mal()
        else:
            m.sf_extfile = fread(form1, sub(m.inpline, i + i1 + 1, m.ilen), [("a", m.flength)])[0][0]
            m.sf_extfile, lgood = checkfile(E, m.sf_extract_unit, m.sf_extfile, 4)
    elif ikey == 8:
        if m.nfield != 2:
            mal()
        else:
            m.sf_qafile = fread(form1, sub(m.inpline, i + i1 + 1, m.ilen), [("a", m.flength)])[0][0]
            m.sf_qafile, lgood = checkfile(E, m.sf_qaout_unit, m.sf_qafile, 4)
    elif ikey == 9:
        if m.nfield not in (3, 4, 7, 8):
            mal()
        else:
            s.sfstart, s.sfend, s.sfdates = getdates(E, i + i1)
    elif ikey == 10:
        if m.nfield < 4 or m.nfield > 6:
            mal()
        else:
            _getloc_sf(E, i + i1, user=True)
    elif ikey == 12:
        if m.nfield != 6:
            mal()
        else:
            surf_range(E, i + i1)
    elif ikey == 13:
        surf_list(E, i + i1)
    else:
        if m.nfield != 2:
            mal()
        else:
            m.one_minfile = fread(form1, sub(m.inpline, i + i1 + 1, m.ilen), [("a", m.flength)])[0][0]
            m.one_minfile, lgood = checkfile(E, m.one_min_unit, m.one_minfile, 1)


def _getloc_sf(E, i1, user):
    s = E.sf
    if user:
        r = getloc(E, i1, s.lgmt2lst, s.user_elev)
        s.sfid = r["stid"]
        s.sflat, s.sflon, s.sfgmt2lst, s.sfelev = r["lat"], r["lon"], r["gmt2lst"], r["elev"]
        s.lgmt2lst, s.user_elev = r["lgmt2lst"], r["lelev"]
        s.sf_user_elev = s.sfelev
    return None


def surf_list(E, i1):
    m, s = E.m, E.sf
    modnam = fx("SURF_LIST", 10)
    nfield1 = m.nfield - 1
    formstr = fmt_msg(E, "3(a,1x),a)")
    sfvar = [None] + [s.sfvars[i].varname for i in range(1, s.nsfvars + 1)]
    sl = [None] + [(s.sfvars[i].lnomiss if m.ikey == 5 else s.sfvars[i].laudit) for i in range(1, s.nsfvars + 1)]
    var_list(E, i1, nfield1, sfvar, sl, s.nsfvars)
    for i in range(1, s.nsfvars + 1):
        v = s.sfvars[i]
        if m.ikey == 5:
            if v.lnomiss:
                E.w(m.writeunit, formstr, pid(E), "W02", modnam, "DUPLICATING LISTING OF VARIABLE FOR",
                    v.varname.strip(), "KEYWORD:", "NO_MISSING")
            v.lnomiss = sl[i]
        else:
            if v.laudit and v.varname in m.inpline1:
                E.w(m.writeunit, formstr, pid(E), "W02", modnam, "DUPLICATING LISTING OF VARIABLE FOR",
                    v.varname.strip(), "KEYWORD:", "AUDIT")
            else:
                v.laudit = sl[i]


def surf_range(E, i1):
    m, s = E.m, E.sf
    modnam = fx("SURF_RANGE", 10)
    formstr = fmt_msg(E, "a,1x,a)")
    nfield1 = m.nfield - 1
    varnam1 = getfields(E, i1, nfield1)
    i = 1
    lfound = False
    while i <= s.nsfvars and not lfound:
        if varnam1[1].strip() == s.sfvars[i].varname.strip():
            lfound = True
        else:
            i += 1
    if lfound:
        linc, lowval, hival, missval, lgood = range_mod(E, varnam1[2], varnam1[3], varnam1[4], varnam1[5])
        if lgood:
            v = s.sfvars[i]
            if v.lmod:
                E.w(m.writeunit, formstr, pid(E), "W02", modnam, "DUPLICATING LISTING OF VARIABLE FOR RANGE KEYWORD:",
                    v.varname.strip())
            v.lincbound = linc
            v.lowbound = lowval
            v.upbound = hival
            v.missval = missval
            if not v.lmod:
                v.lmod = True
    else:
        E.w(m.writeunit, formstr, pid(E), "E05", modnam, "INVALID VARIABLE NAME FOR RANGE KEYWORD:",
            varnam1[1].strip())
        m.lbad = True


def sf_test(E):
    m, s = E.m, E.sf
    modnam = fx("SF_TEST", 10)
    f1 = fmt_msg(E, "a,1x,a)")
    f2 = fmt_msg(E, "a)")
    f3 = fmt_msg(E, "2(a,1x),a)")
    f4 = fmt_msg(E, "3(a,1x),a)")
    f5 = fmt_msg(E, "3(a,1x),i8)")
    mu = m.msg_unit
    if s.sfstage1 and not s.lsfkeywords[1]:
        if s.lsfkeywords[3]:
            f = E.units.get(m.sf_extract_unit)
            rec = f.leer() if f else None
            no_extract = False
            if rec is None:
                no_extract = True
            else:
                v, io, _ = lread(rec, [("a", 8)])
                junk = v[0] if v else ""
                if (io == 0 and "AERMET" not in junk) or io != 0:
                    no_extract = True
            if f:
                f.rewind()
        else:
            no_extract = True
        if (no_extract or (not no_extract and not s.lsfkeywords[4])) and not m.lstage[2]:
            E.w(mu, f1, pid(E), "E08", modnam, "MISSING MANDATORY KEYWORD", m.keywrd[4])
            m.lbad = True
    elif s.lsfkeywords[1]:
        s.writeext = True
    if s.sfstage1 and not m.lstage[2] and not s.lsfkeywords[3]:
        E.w(mu, f1, pid(E), "E08", modnam, "MISSING MANDATORY KEYWORD", m.keywrd[7])
        m.lbad = True
    if not s.sfstage1 and m.lstage[2] and not s.lsfkeywords[4]:
        E.w(mu, f1, pid(E), "E08", modnam, "MISSING MANDATORY KEYWORD", m.keywrd[8])
        m.lbad = True
    if s.sfstage1:
        if not s.lsfkeywords[5]:
            if m.lstage[2]:
                E.w(mu, f2, pid(E), "W03", modnam, "XDATES KEYWORD MISSING; READ XDATES FROM METPREP XDATES")
            else:
                E.w(mu, f1, pid(E), "E08", modnam, "MISSING MANDATORY KEYWORD", m.keywrd[9])
                m.lbad = True
    if s.sfstage1 and not m.lstage[2] and not s.lsfkeywords[6]:
        E.w(mu, f1, pid(E), "E08", modnam, "MISSING MANDATORY KEYWORD", m.keywrd[10])
        m.lbad = True
    if s.sfstage1 and s.lsfkeywords[6]:
        v, io, _ = lread(s.sfid, ["i"])
        s.isfid = v[0] if io == 0 else 9999
        lfound = check_asos(E, s.isfid, 0, 0, True, False, False, False)[0]
        if lfound:
            if s.sfformats[7].lsfform:
                if s.lasos:
                    E.w(mu, f3, pid(E), "W53", modnam, "STATION", s.sfid.strip(), "FOUND IN ASOS LIST FOR ISHD DATA FORMAT")
                else:
                    s.lasos = True
            else:
                if s.lasos:
                    for i in range(1, s.nsfformats + 1):
                        if s.sfformats[i].lsfform and i != 8:
                            E.w(mu, f4, pid(E), "W55", modnam, "STATION", s.sfid.strip(),
                                " FOUND IN ASOS LIST FOR NON-ISHD DATA FORMAT:", s.sfformats[i].sformat.strip())
                            if s.lasos:
                                E.w(mu, f3, pid(E), "W52", modnam, "ASOS FLAG SET FOR NON-ISHD DATA FORMAT:",
                                    s.sfformats[i].sformat.strip(), "RESET ASOS FLAG TO NON-ASOS")
                                s.lasos = False
            E.w(mu, f5, pid(E), "I59", modnam, "STATION", s.sfid.strip(), " ASOS COMMISSION DATE:",
                s.asoscommdates[s.iasos].commisdate)
        else:
            if s.lasos:
                E.w(mu, f3, pid(E), "W54", modnam, "ASOS FLAG SET FOR STATION", s.sfid.strip(), "NOT LISTED IN ASOS LIST")
            else:
                E.w(mu, f3, pid(E), "W54", modnam, "STATION", s.sfid.strip(), "NOT LISTED IN ASOS LIST; CHECK STATION ID")


def sf_stage2(E):
    m, s = E.m, E.sf
    f = E.units.get(m.sf_qaout_unit)
    m.lbad = False
    iline = 0
    if f is None:
        return
    while not m.lbad and iline <= 3:
        raw = f.leer()
        if raw is None:
            break
        L = raw[:m.linelen].upper()
        m.inpline1 = L
        m.ilen = len(L.rstrip(" "))
        iline += 1
        if "LOCATION" in L:
            n = 0
            for i in range(1, m.ilen + 1):
                if ch(L, i + 1) == " " and ch(L, i) != " ":
                    n += 1
            m.nfield = n
            i = L.find("LOCATION") + 1
            r = getloc(E, i + 8, s.lgmt2lst, s.user_elev)
            s.sfid = r["stid"]
            s.sflat, s.sflon, s.sfgmt2lst, s.sf_user_elev = r["lat"], r["lon"], r["gmt2lst"], r["elev"]
            s.lgmt2lst, s.user_elev = r["lgmt2lst"], r["lelev"]
            v, io, _ = lread(s.sfid, ["i"])
            s.isfid = v[0] if io == 0 else 9999
            s.lasos = check_asos(E, s.isfid, s.sfstart, 0, True, False, False, s.lasos)[0]
        if "RANGE" in L:
            i = L.find("RANGE") + 1
            m.nfield = 6
            surf_range(E, i + 5)
        if "DATES" in L:
            i = L.find("DATES") + 1
            m.nfield = 7
            s.sfstart, s.sfend, s.sfdates = getdates(E, i + 5)
    f.rewind()


def sf_thresh(E, i1):
    m, s = E.m, E.sf
    modnam = fx("SF_THRESH", 10)
    nfield1 = m.nfield - 1
    datafield = getfields(E, i1, nfield1)
    f1 = fmt_msg(E, "2(a,1x),f5.3,1x,a,1x,f3.1,1x,a)")
    f2 = fmt_msg(E, "2(a,1x,a))")
    v, iflag, _ = lread(datafield[1], ["f"])
    kw = m.keywrd[m.ikey].strip()
    if iflag == 0:
        s.asos_thresh = v[0]
        if s.asos_thresh < 0.0:
            E.w(m.writeunit, f1, pid(E), "E05", modnam, kw, "SPEED", s.asos_thresh, "M/S IS BELOW", 0.0, "M/S")
            m.lbad = True
        elif s.asos_thresh > 1.0:
            E.w(m.writeunit, f1, pid(E), "E05", modnam, kw, "SPEED", s.asos_thresh, "M/S EXCEEDS", 1.0, "M/S")
            m.lbad = True
        else:
            if s.asos_thresh > 0.5:
                E.w(m.writeunit, f1, pid(E), "W51", modnam, kw, "SPEED", s.asos_thresh, "M/S EXCEEDS", 0.5, "M/S")
    else:
        E.w(m.writeunit, f2, pid(E), "E05", modnam, "INVALID VALUE FOR KEYWORD", kw, ":", datafield[1].strip())
        m.lbad = True


def nws_hgts(E, i1):
    m, s = E.m, E.sf
    modnam = fx("NWS_HGTS", 10)
    nfield1 = m.nfield - 1
    datafield = getfields(E, i1, nfield1)
    f1 = fmt_msg(E, "a,1x,a)")
    f2 = fmt_msg(E, "a,1x,f7.2,1x,a)")
    if datafield[1].strip() != m.instr[1].strip():
        E.w(m.writeunit, f1, pid(E), "E79", modnam, "INVALID VARIABLE FOR NWS_HGT:", datafield[1].strip())
    else:
        v, iflag, _ = lread(datafield[2], ["f"])
        if iflag == 0:
            hgt = v[0]
            if hgt <= 0.0:
                E.w(m.writeunit, f2, pid(E), "E21", modnam, "NWS_HGT", hgt, "< 0 M")
                m.lbad = True
            else:
                if hgt > 30.0:
                    E.w(m.writeunit, f2, pid(E), "W72", modnam, "NWS_HGT", hgt, "> 30 M")
                s.nws_hgt = hgt
        else:
            E.w(m.writeunit, f1, pid(E), "E80", modnam, "INVALID HEIGHT FOR NWS_HGT:", datafield[2].strip())
            m.lbad = True


# ------------------------------------------------------------------------------------------
def sf_proc(E, ahora=None):
    m, s = E.m, E.sf
    modnam = fx("SF_PROC", 10)
    extract_msgs = [None, "NUMBER OF EXTRACTED SURFACE OBSERVATIONS:", "NUMBER OF RETAINED OBSERVATIONS:",
                    "NUMBER OF SPECIAL OBSERVATIONS USED:", "NUMBER OF REGULAR OBSERVATIONS USED:",
                    "NUMER OF DUPLICATE OBSERVATIONS NOT USED:", "NUMBER OF SPECIAL OBSERVATIONS NOT USED:",
                    "NUMBER OF REGULAR OBSERVATIONS NOT USED:", "NUMBER OF OVERWRITTEN OBSERVATIONS:",
                    "NUMBER OF NON-SUPPORTED OBSERVATIONS:", "NUMBER OF OBSERVATIONS OUTSIDE 30-MINUTE WINDOW:",
                    "NUMBER OF OBSERVATIONS FLAGGED AS CALM", "NUMBER OF OBSERVATIONS FLAGGED AS VARIABLE"]
    f1 = fmt_msg(E, "a,1x,a8,1x,2(i2.2,a),i2.2)")
    f2 = fmt_msg(E, "a,1x,i5)")
    f3 = fmt_msg(E, "a,1x,i8,1x,a1,1x,i8,a)")
    mu = m.msg_unit
    m.lbad = False
    s.nsfdays = numdays(s.sfstart, s.sfend)
    nd = s.nsfdays
    for ivar in range(1, s.nsfvars + 1):
        if s.sfvars[ivar].laudit:
            s.nsf_audit_vars += 1
            if ivar > s.nsfvars_keep:
                s.nsf_extra += 1
    s.nsfvars1 = s.nsfvars_keep + s.nsf_extra
    s.sfdata1 = arr(s.nsfvars1, 24, nd)
    s.qaout_vars = [""] * (s.nsfvars1 + 1) if (m.istage == 1 and s.sfstage1) else None
    sfc_date = [0] * (nd + 1)
    s.asoshr = arr(24, nd, val=False, dtype=bool)
    s.nomisshr = arr(24, nd, val=False, dtype=bool)
    s.nsfc1 = [0] * (nd + 1)
    s.lsfcobs = [False] * (nd + 1)
    ivar1 = 0
    for ivar in range(1, s.nsfvars + 1):
        v = s.sfvars[ivar]
        if ivar <= s.nsfvars_keep:
            s.sfdata1[ivar, :, :] = float(v.missval)
            if s.qaout_vars is not None:
                s.qaout_vars[ivar] = v.varname
        else:
            if v.laudit:
                ivar1 += 1
                s.sfdata1[ivar1 + s.nsfvars_keep, :, :] = float(v.missval)
                if s.qaout_vars is not None:
                    s.qaout_vars[ivar1 + s.nsfvars_keep] = v.varname
    iday1 = 0
    for y in range(s.sfdates[1][1], s.sfdates[2][1] + 1):
        leap = leapyr(y)
        imon1 = s.sfdates[1][2] if y == s.sfdates[1][1] else 1
        imon2 = s.sfdates[2][2] if y == s.sfdates[2][1] else 12
        for mm in range(imon1, imon2 + 1):
            idy1 = 1
            idy2 = m.days[mm] + (1 if (mm == 2 and leap) else 0)
            if mm == imon1 and y == s.sfdates[1][1]:
                idy1 = s.sfdates[1][3]
            if mm == imon2 and y == s.sfdates[2][1]:
                idy2 = s.sfdates[2][3]
            for dd in range(idy1, idy2 + 1):
                iday1 += 1
                sfc_date[iday1] = y * 10000 + mm * 100 + dd
    t = ahora or _dt.datetime.now()
    E.w(mu, f1, pid(E), "I40", modnam, "SURFACE EXTRACTION BEGIN:", t.strftime("%Y%m%d"), t.hour, ":", t.minute,
        ":", t.second)
    if s.sfstage1:
        if s.sfformats[1].lsfform or s.sfformats[9].lsfform or s.sfformats[2].lsfform or \
                s.sfformats[3].lsfform or s.sfformats[6].lsfform:
            raise NoTraducido("formato de superficie de EE. UU. (CD144/SCRAM/SAMSON/HUSWO)")
        elif s.sfformats[7].lsfform:
            read_ishd(E)
        elif s.sfformats[10].lsfform:
            read_ghcn(E)
        else:
            s.isfform = 8
            read_ext(E)
    else:
        s.isfform = 8
        read_ext(E)
    if s.user_elev and m.istage == 1 and s.sfstage1:
        s.sfelev = s.sf_user_elev
    if m.istage == 1 and s.sfstage1:
        for i in range(1, 13):
            code = "I%02d" % (i + 45)
            if not s.sfformats[7].lsfform and i in (3, 4, 6, 7, 9, 10, 12):
                continue
            E.w(mu, f2, pid(E), code, modnam, extract_msgs[i], s.nsfc[i])
    else:
        for i in (1, 2):
            E.w(mu, f2, pid(E), "I%02d" % (i + 45), modnam, extract_msgs[i], s.nsfc[i])
    t = ahora or _dt.datetime.now()
    E.w(mu, f1, pid(E), "I40", modnam, "SURFACE EXTRACTION END:", t.strftime("%Y%m%d"), t.hour, ":", t.minute,
        ":", t.second)
    if not s.lbadsfc:
        if s.nsfc[2] == 0:
            E.w(mu, f3, pid(E), "W46", modnam, "NO EXTRACTED DATA BETWEEN", s.sfstart, "-", s.sfend, "; CHECK DATES")
        else:
            s.sfc_info = [None]
            for d in range(1, nd + 1):
                si = SfInfo()
                si.sfcdate = sfc_date[d]
                si.nsfcobs = 24
                si.sobs = s.lsfcobs[d]
                si.asos_hr = [None] + [bool(s.asoshr[h, d]) for h in range(1, 25)]
                si.have_obs = [None] + [bool(s.nomisshr[h, d]) for h in range(1, 25)]
                s.sfc_info.append(si)
            if m.istage == 1 and s.sfstage1:
                if s.lsfkeywords[3] and s.writeext:
                    header(E, m.sf_extract_unit)
                    df = "(i8.8,3x,i2.2,5x,a1,1x,f8.2,10(1x,f8.1))"
                    L = []
                    for d in range(1, nd + 1):
                        if not s.sfc_info[d].sobs:
                            continue
                        for h in range(1, 25):
                            af = "Y" if s.sfc_info[d].asos_hr[h] else "N"
                            if s.nomisshr[h, d]:
                                L.extend(fwrite(df, s.sfc_info[d].sfcdate, h, af,
                                                *[float(s.sfdata1[k, h, d]) for k in range(1, s.nsfvars_keep + 1)]))
                    E.units[m.sf_extract_unit].escribir(L)
                sf_audit(E)
            s.sfdata = arr(s.nsfvars_keep, 24, nd)
            s.sfdata[:, :, :] = s.sfdata1[:s.nsfvars_keep + 1, :, :]
            if m.istage == 1 and s.sfstage1:
                if s.lsfkeywords[4] and s.sfstage1:
                    header(E, m.sf_qaout_unit)
                    df = fwrite("(a,i2,a)", "(i8.8,3x,i2.2,5x,a1,1x,f8.2,", s.nsfvars1 - 1, "(1x,f8.1))")[0]
                    L = []
                    for d in range(1, nd + 1):
                        if not s.sfc_info[d].sobs:
                            continue
                        for h in range(1, 25):
                            af = "Y" if s.sfc_info[d].asos_hr[h] else "N"
                            if s.nomisshr[h, d]:
                                L.extend(fwrite(df, s.sfc_info[d].sfcdate, h, af,
                                                *[float(s.sfdata1[k, h, d]) for k in range(1, s.nsfvars1 + 1)]))
                    E.units[m.sf_qaout_unit].escribir(L)
    s.sfdata1 = None
    s.qaout_vars_hdr = s.qaout_vars
    s.qaout_vars = None
    s.asoshr = s.lsfcobs = s.nomisshr = None


def header(E, iunit):
    m, s = E.m, E.sf
    outtype = [None, "EXTRACT", "QAOUT"]
    cgmt2lst = fwrite("(i3)", s.sfgmt2lst)[0] if s.lgmt2lst else ""
    celev = fwrite("(f10.3)", s.sfelev)[0]
    if s.sflat < 0.0:
        alat = fwrite("(f7.3,a1)", abs(s.sflat), "S")[0]
    else:
        alat = fwrite("(f7.3,a1)", s.sflat, "N")[0]
    if s.sflon < 0.0:
        alon = fwrite("(f8.3,a1)", abs(s.sflon), "W")[0]
    else:
        alon = fwrite("(f8.3,a1)", s.sflon, "E")[0]
    L = fwrite("(a,a5/a,a8,2(1x,a10),2(1x,a)/2(a)/a,i4,2(1x,i2.2),1x,i4,2(1x,i2.2))", "AERMET ", m.versn,
               "LOCATION ", fx(s.sfid, 8), fx(alat, 10), fx(alon, 10), cgmt2lst.strip(), celev.strip(), "FILE TYPE: ",
               outtype[iunit - m.sf_extract_unit + 1].strip(), "DATES ", s.sfdates[1][1], s.sfdates[1][2],
               s.sfdates[1][3], s.sfdates[2][1], s.sfdates[2][2], s.sfdates[2][3])
    for ivar in range(1, s.nsfvars + 1):
        v = s.sfvars[ivar]
        if v.lmod:
            bndstr = "<=" if v.lincbound else "< "
            L += fwrite("(a5,1x,a4,i6,1x,a2,1x,2(1x,i6))", "RANGE", v.varname, v.lowbound, bndstr, v.upbound,
                        v.missval)
    if iunit == m.sf_extract_unit:
        hf = fwrite("(a,i2,a)", "(a,4x,a4,", s.nsfvars_keep - 1, "(5x,a4))")[0]
        L += fwrite(hf, "DATE       HR  ASOS", *[s.sfvars[iv].varname.strip() for iv in range(1, s.nsfvars_keep + 1)])
    else:
        hf = fwrite("(a,i2,a)", "(a,4x,a4,", s.nsfvars1 - 1, "(5x,a4))")[0]
        L += fwrite(hf, "DATE       HR  ASOS", *[s.qaout_vars[iv].strip() for iv in range(1, s.nsfvars1 + 1)])
    E.units[iunit].escribir(L)


def _indice_asos(s):
    """WBAN -> primera posición en la lista ASOS (la búsqueda lineal del original)."""
    idx = s.__dict__.get("_indice_asos")
    if idx is None:
        idx = {}
        for k in range(s.nasos, 0, -1):
            idx[s.asoscommdates[k].iwban] = k
        s._indice_asos = idx
    return idx


def _asos_por_ids(s, wban, call4, call3):
    """Primera posición k de la lista ASOS con iwban == wban, intcall == call4 o usacall == call3
    (comparaciones sin blancos), o None."""
    idx = s.__dict__.get("_indice_asos_ids")
    if idx is None:
        idx = ({}, {}, {})
        for k in range(s.nasos, 0, -1):
            a = s.asoscommdates[k]
            idx[0][a.iwban] = k
            idx[1][a.intcall.strip(" ")] = k
            idx[2][a.usacall.strip(" ")] = k
        s._indice_asos_ids = idx
    ks = [k for k in (idx[0].get(wban), idx[1].get(call4), idx[2].get(call3)) if k is not None]
    return min(ks) if ks else None


def check_asos(E, i_id, sdate, ihr, checkstat, checkhr, aflag, lfound, alias=False):
    """CHECK_ASOS. Devuelve (lfound, asoshr1). Con `alias`, el argumento `lfound` es la propia
    variable LASOS del módulo (llamadas de extracción del original): lo que la rutina asigna a
    `lfound` lo ve ya la comprobación de la hora, que lee LASOS."""
    m, s = E.m, E.sf
    modnam = fx("CHECK_ASOS", 10)
    asoshr1 = False
    if checkstat and i_id != 99999:
        k = _indice_asos(s).get(i_id)
        s.iasos = s.nasos + 1 if k is None else k
        lfound = k is not None
        if alias:
            s.lasos = lfound
    if checkstat and not lfound:
        s.iasos = 0
    if checkhr:
        if s.lasos:
            if s.iasos != 0:
                cd = s.asoscommdates[s.iasos].commisdate
                if sdate < cd and not s.write_asos:
                    if not aflag:
                        E.w(m.msg_unit, fmt_msg(E, "a,1x,i8,1x,a,1x,i8)"), pid(E), "W45", modnam, "STATION IS ASOS, BUT BEFORE COMMISSION DATE", cd,
                            "FOR DATE:", sdate)
                        s.write_asos = True
                        s.switch_asos[1] = True
                    else:
                        E.w(m.msg_unit, fmt_msg(E, "2(a,1x,i8,1x),a,1x,i2.2)"), pid(E), "W45", modnam, "DATA SOURCE FLAG = ASOS, BUT BEFORE COMMISSION DATE",
                            cd, "SET OBS=ASOS FOR DATE:", sdate, "HR", ihr)
                        asoshr1 = True
                else:
                    if sdate >= cd:
                        asoshr1 = True
                    if s.switch_asos[1] and not s.switch_asos[2] and asoshr1:
                        E.w(m.msg_unit, fmt_msg(E, "a,1x,i8,1x,a,1x,i8)"), pid(E), "W45", modnam, "STATION IS ASOS, AND AFTER COMMISSION DATE", cd,
                            "FOR DATE:", sdate)
                        s.switch_asos[2] = True
            else:
                asoshr1 = True
    return lfound, asoshr1


def new_obs(E, iyear, imonth, iday, ihr, savedate, savehr):
    """NEW_OBS. Devuelve (ihr, iday, imonth, iyear, lgo, iday1, sdate); iday1 None si no cambia."""
    m, s = E.m, E.sf
    modnam = fx("NEW_OBS", 10)
    f1 = "(1x,a,1x,i1,a,1x,2(a2,a1),a4,1x,a)"
    f2 = fmt_msg(E, "a,1x,i8,1x,a,1x,i2.2)")
    f3 = fmt_msg(E, "a,1x,i8,1x,a,1x,i8)")
    f4 = fmt_msg(E, "a,1x,i8,1x,3(a,1x),i8)")
    sv = E.sf.__dict__.setdefault("_new_obs_linvalid", [None, False, False])
    ihr, iday, imonth, iyear, sdate, lgo = data_dates(E, ihr, iday, imonth, iyear, s.sfgmt2lst, s.sfstart,
                                                      s.sfend, 42)
    ff = s.sfformats[s.isfform]
    if sdate < ff.validstart:
        if not sv[1]:
            E.w(m.msg_unit, f4, pid(E), "W50", modnam, "OBSERVATION", sdate, "IS BEFORE VALID", ff.sformat.strip(),
                "START DATE", ff.validstart)
        sv[1] = True
    if sdate > ff.validend:
        if not sv[2]:
            E.w(m.msg_unit, f4, pid(E), "W50", modnam, "OBSERVATION", sdate, "IS AFTER VALID", ff.sformat.strip(),
                "END DATE", ff.validend)
        sv[2] = True
    iday1 = None
    if lgo:
        s.nsfc[1] += 1
        adate = "%08d" % sdate
        if sdate == savedate:
            if ihr == savehr:
                E.w(m.msg_unit, f2, pid(E), "I43", modnam, "POTENTIAL DUPLICATE OBSERVATION FOR DATE:", sdate, "HR", ihr)
        else:
            if sdate < savedate:
                E.w(m.msg_unit, f3, pid(E), "W49", modnam, "CURRENT DATE", sdate, "IS PRIOR TO PREVIOUS DATE IN SURFACE FILE",
                    savedate)
            if not m.noprint:
                E.w(OUTPUT_UNIT, f1, "Stage", m.istage, ": Extracting surface data for month/day/year", adate[4:6], "/",
                    adate[6:8], "/", adate[0:4], "LST")
            iday1 = numdays(s.sfstart, sdate)
            s.write_asos = False
    return ihr, iday, imonth, iyear, lgo, iday1, sdate


def check_dup(E, iday1, ihr, prcp, tmpd, wdir, wspd, cc1, cc2, sky):
    """CHECK_DUP. Devuelve (miss_precip, miss_temp, miss_dir, miss_wind, miss_cloud, writedat)."""
    s = E.sf
    sv = s.sfvars
    D = s.sfdata1
    miss_precip = float(D[1, ihr, iday1]) != float(sv[1].missval) and prcp == float(sv[1].missval)
    miss_temp = float(D[7, ihr, iday1]) != float(sv[7].missval) and tmpd == float(sv[7].missval)
    miss_dir = float(D[10, ihr, iday1]) != float(sv[10].missval) and wdir == float(sv[10].missval)
    miss_wind = float(D[11, ihr, iday1]) != float(sv[11].missval) and wspd == float(sv[11].missval)
    v4 = int(float(D[4, ihr, iday1]))
    icloud1 = [None, _idiv(v4, 100), v4 - _idiv(v4, 100) * 100, int(float(D[6, ihr, iday1]))]
    icloud2 = [None, int(cc1), int(cc2), int(sky)]
    misscloud = [None, _idiv(sv[4].missval, 100), sv[4].missval - _idiv(sv[4].missval, 100) * 100, sv[6].missval]
    miss_cloud = [None, False, False, False]
    for i in (1, 2, 3):
        if icloud1[i] != misscloud[i] and icloud2[i] == misscloud[i]:
            miss_cloud[i] = True
    writedat = not (miss_temp or miss_dir or miss_wind)
    s.nsfc[5] += 1
    if not writedat:
        s.nsfc[3] -= 1
    else:
        s.nsfc[8] += 1
    return miss_precip, miss_temp, miss_dir, miss_wind, miss_cloud, writedat


# ------------------------------------------------------------------------------------------
def read_ishd(E):
    m, s = E.m, E.sf
    modnam = fx("READ_ISHD", 10)
    F = {k: fmt_msg(E, v) for k, v in {1: "a)", 2: "2(a,1x,i2,1x),a,1x,a20)", 3: "3(a,1x),a20)",
                                       4: "a,1x,f9.2,1x,a1)", 5: "a,1x,a20,4(1x,a))", 6: "a,1x,a20,2(1x,a))"}.items()}
    ef = s.ext_form
    mu = m.msg_unit
    rpt_list = ["FM-12", "FM-13", "FM-14", "FM-15", "FM-16", "FM-18", "SAO", "SAOSP", "AERO", "AUTO", "SY-AE",
                "SY-SA", "SY-MT", "SY-AU", "SA-AU", "S-S-A", "SMARS"]
    control_len = [None, 60, 33]
    rpt_indx = [None, 42, 29]
    call_indx = [None, [None, 53, 52], [None, 39, 34]]
    missobs = [None, 9999, 99999, 99999, 99999, 9999, 99, 9999, 9999, 999, 999, 9999, 99, 99, 999999, 99, 9, 9, 9,
               9, 9, 9, 99, 99, 99, 99, 99, 99, 99999]
    fld = [None, "AA1", "AG1", "GD1", "GD2", "GD3", "GD4", "GD5", "GD6", "GF1", "MA1", "MW1", "MW2", "GA1", "GA2",
           "GA3", "GA4", "GA5", "GA6"]
    length = [None, 11, 7, 4, 4, 4, 4, 4, 4, 8, 15, 6, 6, 5, 5, 5, 5, 5, 5]
    inc = 30
    sv = s.sfvars
    D = s.sfdata1
    eps = m.eps
    fdata = E.units[m.sf_data_unit]
    E.abrir(m.ishd_units[1], m.ishd_files[1], "replace")
    E.abrir(m.ishd_units[2], m.ishd_files[2], "replace")
    fdis = E.units[m.ishd_units[1]]
    frep = E.units[m.ishd_units[2]]
    iwarn = 0
    spec_obs = reg_obs = False
    eof = 0
    sdate = 0
    savedate = 0
    savehr = 0
    gotwban = False
    savewban = 0
    iday1 = 0
    rpt_use = ""
    last_rpt = ""
    lastline = ""
    ishobs = [None] + list(missobs[1:])
    m.lbad = False
    while eof == 0 and not m.lbad and sdate <= s.sfend:
        rec = fdata.leer()
        if rec is None:
            eof = -1
            continue
        datline = rec[:10200]
        lgo2 = lgo3 = False
        have_elev = False
        lcdrom = False
        icontrol = 1
        control = fx(datline, 60)
        spec_obs = False
        ishobs = [None] + [0] * 28
        if ch(datline, 29) != "+" and ch(datline, 29) != "-":
            lcdrom = True
            icontrol = 2
        v, iflag, _ = lread(fx(datline, 4), ["i"])
        lendat = 0
        mandatory = ""
        variable = ""
        if iflag != 0:
            E.w(mu, F[1], pid(E), "E40", modnam, "ERROR READING VARIABLE DATA LENGTH")
            m.lbad = True
        else:
            lendat = v[0]
            cl = control_len[icontrol]
            mandatory = fx(datline[cl:cl + 45], 45)
            variable = fx(datline[cl + 45:cl + 45 + lendat], 1000)
        vd, iflag, _ = fread("(i4,4(i2))", control[15:27], ["i"] * 5)
        if iflag == 0:
            iyear, imonth, iday, ihr, imin = vd
            if imin > 0:
                ihr, iday, imonth, iyear, sdate, lgo = data_dates(E, ihr, iday, imonth, iyear, -1, s.sfstart, s.sfend, 42)
            else:
                ihr, iday, imonth, iyear, sdate, lgo = data_dates(E, ihr, iday, imonth, iyear, 0, s.sfstart, s.sfend, 42)
            ihr, iday, imonth, iyear, lgo, nd1, sdate = new_obs(E, iyear, imonth, iday, ihr, savedate, savehr)
            if nd1 is not None:
                iday1 = nd1
            date_hr_str = fwrite("(a5,1x,i8,1x,a2,1x,i2.2)", "DATE:", sdate, "HR", ihr)[0]
            if lgo:
                if imin == 0 or imin >= (60 - inc):
                    lgo2 = True
                else:
                    lgo2 = False
                    E.w(mu, F[2], pid(E), "I41", modnam, "OBSERVATION MINUTE", imin, "NOT WITHIN", inc,
                        "MINUTES OF HOUR FOR", date_hr_str)
                    s.nsfc[10] += 1
                    fdis.escribir(datline.strip())
                if lgo2:
                    ri = rpt_indx[icontrol]
                    rpt_type = control[ri - 1:ri + 4]
                    if rpt_type.strip() in rpt_list:
                        lgo3 = True
                    else:
                        if m.debug:
                            E.w(mu, F[3], pid(E), "I42", modnam, "REPORT TYPE", rpt_type.strip(), "NOT PROCESSED FOR",
                                date_hr_str)
                        s.nsfc[9] += 1
                        lgo3 = False
                        fdis.escribir(datline.strip())
            if lgo3:
                if sdate == savedate:
                    if ihr != savehr:
                        reg_obs = False
                        rpt_use = ""
                else:
                    reg_obs = False
                if rpt_type.strip() in ("SAOSP", "FM-16"):
                    spec_obs = True
                else:
                    reg_obs = True
                vv, iflag1, _ = fread("(a6,i5)", control[4:15], [("a", 8), "i"])
                if iflag1 == 0:
                    iusaf, s.iwban = vv
                    iwban = s.iwban
                    if not gotwban and iwban != 99999:
                        savewban = iwban
                        gotwban = True
                        if iwban != s.isfid and iwban != 99999:
                            if iusaf.strip() == s.sfid.strip():
                                E.w(mu, ef[4], pid(E), "W41", modnam, "STATION ID", iusaf, "IS WMO NUMBER; CONSIDER WBAN FOR STAGE 2")
                            else:
                                E.w(mu, ef[2], pid(E), "W40", modnam, "STATION ID", iwban, "DOES NOT MATCH USER ENTERED ID",
                                    s.sfid.strip())
                                iwarn += 1
                    else:
                        if iwban != savewban and iwban != 99999:
                            iwarn += 1
                            if iwarn <= s.nwarnlim:
                                E.w(mu, ef[2], pid(E), "W40", modnam, "STATION ID", iwban, "DOES NOT MATCH PREVIOUS WBAN",
                                    s.sfid.strip())
                            if iwarn == s.nwarnlim:
                                E.w(mu, ef[3], pid(E), "W42", modnam, "REACH LIMIT OF", s.nwarnlim, "W40", "WARNING MESSAGES")
                    s.lasos, ah = check_asos(E, iwban, sdate, ihr, True, True, False, s.lasos, alias=True)
                    s.asoshr[ihr, iday1] = ah
                else:
                    E.w(mu, ef[1], pid(E), "E47", modnam, "INVALID STATION ID FIELD:", control[4:15])
                    m.lbad = True
                ci1, ci2 = call_indx[icontrol][1], call_indx[icontrol][2]
                call_sign3 = lread(control[ci1 - 1:ci1 + 2], [("a", 3)])[0]
                call_sign3 = call_sign3[0] if call_sign3 else ""
                call_sign4 = lread(control[ci2 - 1:ci2 + 3], [("a", 4)])[0]
                call_sign4 = call_sign4[0] if call_sign4 else ""
                if lcdrom:
                    E.w(mu, F[1], pid(E), "W44", modnam, "STATION COORDINATES NOT PROVIDED IN FILE; DATA FROM CDROM")
                else:
                    vv, iflag1, _ = fread("(f6.3,f7.3)", control[28:41], ["f", "f"])
                    if iflag1 != 0:
                        E.w(mu, ef[1], pid(E), "E44", modnam, "INVALID COORDINATES FIELD:", control[28:41])
                        m.lbad = True
                if lcdrom:
                    if s.user_elev:
                        E.w(mu, F[4], pid(E), "W43", modnam,
                            "STATION ELEVATION NOT PROVIDED IN FILE; DATA FROM CDROM; USE USER ELEVATION", s.sfelev, "M")
                    else:
                        E.w(mu, ef[1], pid(E), "W43", modnam, "STATION ELEVATION NOT PROVIDED IN FILE; DATA FROM CDROM;",
                            "NO USER ELEVATION,CONSIDER INPUTTING ELEVATION")
                else:
                    vv, iflag1, _ = fread("(f5.0)", control[46:51], ["f"])
                    if iflag1 == 0:
                        elev = vv[0]
                        if elev == 9999.0:
                            if s.user_elev:
                                E.w(mu, F[4], pid(E), "W43", modnam,
                                    "STATION ELEVATION PROVIDED IN FILE BUT MISSING; USE USER ELEVATION", s.sfelev, "M")
                            else:
                                E.w(mu, ef[1], pid(E), "W43", modnam,
                                    "STATION ELEVATION PROVIDED IN FILE BUT MISSING; NO USER ELEVATION,",
                                    "CONSIDER INPUTTING ELEVATION")
                        else:
                            have_elev = True
                            if s.user_elev:
                                if abs(s.sfelev - elev) > 0.02 * elev:
                                    E.w(mu, ef[9], pid(E), "W43", modnam, "USER ENTERED ELEVATION", s.sfelev,
                                        "M DIFFERS FROM ELEVATION", elev, "M IN ISHD FILE")
                            s.sfelev = elev
                            s.lsfelev = True
                    else:
                        E.w(mu, ef[1], pid(E), "E43", modnam, "INVALID ELEVATION FIELD:", control[46:51])
                        m.lbad = True
                if not s.lasos:
                    k = _asos_por_ids(s, savewban, call_sign4.strip(), call_sign3.strip())
                    if k is None:
                        s.iasos = s.nasos + 1
                    else:
                        s.iasos = k
                        s.lasos = True
                    if s.lasos:
                        E.w(mu, ef[4], pid(E), "W53", modnam, "STATION", s.sfid.strip(),
                            "FOUND IN ASOS LIST BASED ON STATION IDENTIFIERS IN SURFACE FILE")
                        s.asoshr[ihr, iday1] = True
                data_source_flag = control[27:28]
                if data_source_flag in ("6", "7"):
                    if s.lasos:
                        if s.iasos == 0:
                            E.w(mu, ef[5], pid(E), "W45", modnam,
                                "DATA SOURCE FLAG = ASOS, BUT NO COMMISSION DATE, SET OBS=ASOS FOR", date_hr_str)
                        else:
                            if sdate < s.asoscommdates[s.iasos].commisdate:
                                E.w(mu, ef[8], pid(E), "W45", modnam, "DATA SOURCE FLAG = ASOS, BUT BEFORE COMMISSION DATE",
                                    s.asoscommdates[s.iasos].commisdate, "SET OBS=ASOS FOR", date_hr_str)
                    s.asoshr[ihr, iday1] = True
                ishobs[10] = _ri(mandatory[0:3])
                wind_code = mandatory[3:5]
                ishobs[11] = _ri(mandatory[5:9])
                ishobs[4] = _ri(mandatory[10:15])
                ishobs[14] = _ri(mandatory[18:24])
                ishobs[7] = _ri(mandatory[27:32])
                ishobs[8] = _ri(mandatory[33:38])
                ishobs[2] = _ri(mandatory[39:44])
                vr = variable
                if "REM" in vr:
                    endadd = vr.find("REM")
                elif "EQD" in vr:
                    endadd = vr.find("EQD")
                elif "QNN" in vr:
                    endadd = vr.find("QNN")
                else:
                    endadd = lendat
                additional = fx(vr[:endadd], 1000)
                field = [None, "AA10100009", "AG19999", "GD19999+99999", "GD29", "GD39", "GD49", "GD59", "GD69",
                         "GF199999", "MA1999999999999", "MW1001", "MW1002", "GA199", "GA299", "GA399", "GA499",
                         "GA599", "GA699"]
                field = [None] + [fx(x, 15) for x in field[1:]]
                if "AA101" in additional:
                    k = additional.find(fld[1])
                    field[1] = fx(additional[k:k + length[1]], 15)
                for ifield in range(3, 19):
                    if fld[ifield] in additional:
                        k = additional.find(fld[ifield])
                        field[ifield] = fx(additional[k:k + length[ifield]], 15)
                ishobs[1] = _ri(field[1][5:9])
                for ifield in range(3, 9):
                    ishobs[ifield + 13] = _ri(field[ifield][3:4])
                for ifield in range(13, 19):
                    ishobs[ifield + 9] = _ri(field[ifield][3:5])
                ishobs[12] = _ri(field[9][3:5])
                ishobs[13] = _ri(field[9][5:7])
                ishobs[28] = _ri(field[10][3:8])
                ishobs[3] = _ri(field[10][9:14])
                for ifield in (12, 13):
                    if ishobs[ifield] == missobs[ifield]:
                        ishobs[ifield] = 99
                    else:
                        if ishobs[ifield] > 1:
                            if ishobs[ifield] <= 5:
                                ishobs[ifield] += 1
                            elif ishobs[ifield] <= 8:
                                ishobs[ifield] += 2
                            elif ishobs[ifield] <= 10:
                                ishobs[ifield] = 10
                            else:
                                ishobs[ifield] = 99
                if ishobs[12] == missobs[12] and ishobs[13] == missobs[13]:
                    asky = missobs[6]
                    ifield = 21
                    while asky == missobs[6] and ifield >= 16:
                        if ishobs[ifield] != missobs[ifield]:
                            asky = ishobs[ifield]
                        ifield -= 1
                    if asky != missobs[6]:
                        if asky >= 4:
                            ishobs[6] = 10
                        elif asky == 3:
                            ishobs[6] = 7
                        elif asky == 2:
                            ishobs[6] = 4
                        elif asky == 1:
                            ishobs[6] = 2
                        else:
                            ishobs[6] = 0
                    else:
                        if ishobs[27] != missobs[27]:
                            asky = ishobs[27]
                        for ifield in range(26, 21, -1):
                            if ishobs[ifield] != missobs[ifield]:
                                if asky != missobs[6]:
                                    asky = max(asky, ishobs[ifield])
                                else:
                                    asky = ishobs[ifield]
                        if asky <= 1:
                            ishobs[6] = asky
                        elif asky <= 5:
                            ishobs[6] = asky + 1
                        elif asky <= 8:
                            ishobs[6] = asky + 2
                        elif asky <= 10:
                            ishobs[6] = 10
                        else:
                            ishobs[6] = 99
                else:
                    ishobs[6] = sv[6].missval
                calcrh = True
                for ifield in (7, 8):
                    if ishobs[ifield] == missobs[ifield]:
                        ishobs[ifield] = sv[ifield].missval
                        calcrh = False
                if calcrh:
                    ishobs[9] = int(humidity(float(ishobs[7]) / 10.0, float(ishobs[8]) / 10.0))
                else:
                    ishobs[9] = sv[9].missval
                if ishobs[10] == missobs[10]:
                    ishobs[10] = sv[10].missval
                    if (wind_code == "59" and ishobs[11] == 0) or wind_code[1:2] == "C":
                        ishobs[10] = 0
                        s.nsfc[11] += 1
                    elif wind_code[1:2] == "V" or (ishobs[10] == missobs[10] and ishobs[11] != missobs[11]):
                        ishobs[10] = sv[10].missval
                        s.nsfc[12] += 1
                if ishobs[11] == missobs[11]:
                    ishobs[11] = sv[11].missval
                if ishobs[4] == missobs[4]:
                    ishobs[4] = sv[12].missval
                elif ishobs[4] == 22000:
                    ishobs[4] = 300
                else:
                    ishobs[4] = int(float(ishobs[4]) / 100.0)
                if ishobs[14] == missobs[14]:
                    ishobs[14] = sv[21].missval
                else:
                    ishobs[14] = _idiv(ishobs[14], 1000) * 10
                mw = [None, 0, 0]
                for ifield in (11, 12):
                    w1 = _ri(field[ifield][3:5])
                    if w1 <= 19:
                        mw[ifield - 10] = 0
                    elif w1 == 22 or 36 <= w1 <= 39 or 70 <= w1 <= 79 or w1 == 85 or w1 == 86:
                        mw[ifield - 10] = 2
                    elif w1 == 21 or w1 == 25:
                        mw[ifield - 10] = 1
                    elif w1 <= 28:
                        mw[ifield - 10] = 3
                    elif w1 <= 49:
                        mw[ifield - 10] = 0
                    elif w1 in (56, 57) or 66 <= w1 <= 69 or 83 <= w1 <= 90 or w1 >= 93:
                        mw[ifield - 10] = 3
                    else:
                        mw[ifield - 10] = 1
                if (mw[1] == 0 and mw[2] == 0) or (mw[1] == 1 and mw[2] == 1) or (mw[1] == 2 and mw[2] == 2):
                    ishobs[5] = mw[1]
                elif (mw[1] == 1 and mw[2] == 2) or (mw[1] == 2 and mw[2] == 1):
                    ishobs[5] = 3
                else:
                    ishobs[5] = max(mw[1], mw[2])
                if ishobs[1] == missobs[1]:
                    ishobs[1] = sv[1].missval
                    ishobs[5] = 0
                if ishobs[1] == 0:
                    ishobs[5] = 0
                ishobs[28] = _ri(field[10][3:8])
                ishobs[3] = _ri(field[10][9:14])
                if ishobs[3] == missobs[3] and float(D[3, ihr, iday1]) == float(sv[3].missval):
                    if ishobs[28] != missobs[28] and ishobs[2] == missobs[2]:
                        pr = pressure(E, 2, s.sfelev, 290.0, float(ishobs[28]) / 10.0)
                        ishobs[3] = nint(pr) * 10
                    if ishobs[28] == missobs[28] and ishobs[2] == missobs[2]:
                        if have_elev and not s.user_elev:
                            ishobs[3] = nint(1013.25 * (1.0 - ((6.5e-3 / 288.15) * s.sfelev)) ** 5.255) * 10
                        else:
                            ishobs[3] = sv[3].missval
                        ishobs[2] = sv[2].missval
                    if ishobs[2] != missobs[2]:
                        if have_elev and not s.user_elev:
                            pr = pressure(E, 2, s.sfelev, 290.0, float(ishobs[2]) / 10.0)
                            ishobs[3] = nint(pr) * 10
                        else:
                            ishobs[3] = sv[3].missval
                else:
                    if ishobs[2] == missobs[2] and float(D[2, ihr, iday1]) == float(sv[2].missval):
                        if have_elev and not s.user_elev:
                            pr = pressure(E, 1, s.sfelev, 290.0, float(ishobs[3]) / 10.0)
                            ishobs[2] = nint(pr) * 10
                        else:
                            ishobs[2] = sv[2].missval
                for ifield in (2, 3):
                    if ishobs[ifield] == missobs[ifield]:
                        ishobs[ifield] = sv[ifield].missval
                if s.nomisshr[ihr, iday1]:
                    loverwrite = [None] + [True] * 28
                    mp, mt, md, mwd, mc, writedat = check_dup(E, iday1, ihr, float(ishobs[1]), float(ishobs[7]),
                                                              float(ishobs[10]), float(ishobs[11]), float(ishobs[12]),
                                                              float(ishobs[13]), float(ishobs[6]))
                    if spec_obs and reg_obs:
                        s.nsfc[6] += 1
                        writedat = False
                        fdis.escribir(datline.strip())
                    elif reg_obs and not writedat:
                        s.nsfc[7] += 1
                        fdis.escribir(datline.strip())
                    else:
                        if spec_obs and rpt_use.strip() in ("SAOSP", "FM-16"):
                            s.nsfc[6] += 1
                        if reg_obs:
                            if rpt_use.strip() in ("SAOSP", "FM-16"):
                                s.nsfc[4] += 1
                                s.nsfc[6] += 1
                                s.nsfc[3] -= 1
                            else:
                                s.nsfc[7] += 1
                        if m.debug:
                            E.w(mu, F[5], pid(E), "I45", modnam, "OBSERVATION REPLACED FOR", date_hr_str,
                                "WITH REPORT TYPE:", rpt_type.strip(), "REPLACING REPORT TYPE:", last_rpt.strip())
                        frep.escribir(lastline.strip())
                        if not mp and (ishobs[1] > 0 or (float(D[1, ihr, iday1]) == float(sv[1].missval) and
                                                         ishobs[1] == 0)):
                            D[1, ihr, iday1] = float(ishobs[1]) / 10.0
                            D[5, ihr, iday1] = float(ishobs[5])
                        if mc[1]:
                            ishobs[12] = _idiv(int(float(D[4, ihr, iday1])), 100)
                        if mc[2]:
                            v4 = int(float(D[4, ihr, iday1]))
                            ishobs[13] = v4 - _idiv(v4, 100) * 100
                        if 0 <= ishobs[12] <= 10 and 0 <= ishobs[13] <= 10 and ishobs[13] > ishobs[12]:
                            ishobs[13] = ishobs[12]
                        if mc[3]:
                            loverwrite[6] = False
                        if ishobs[2] == sv[2].missval and float(D[2, ihr, iday1]) != float(sv[2].missval):
                            loverwrite[2] = False
                        if ishobs[3] == sv[3].missval and float(D[3, ihr, iday1]) != float(sv[3].missval):
                            loverwrite[3] = False
                        if ishobs[8] == sv[8].missval and float(D[8, ihr, iday1]) != float(sv[8].missval):
                            loverwrite[8] = False
                        if ishobs[9] == sv[9].missval and float(D[9, ihr, iday1]) != float(sv[9].missval):
                            loverwrite[9] = False
                        for ifield in range(2, s.nsfvars_keep + 1):
                            if not loverwrite[ifield]:
                                continue
                            if (ifield < 10 and ifield != 4) or (ifield == 11 and ishobs[ifield] != sv[ifield].missval):
                                if ishobs[ifield] == sv[ifield].missval:
                                    D[ifield, ihr, iday1] = float(ishobs[ifield])
                                else:
                                    D[ifield, ihr, iday1] = float(ishobs[ifield]) * sv[ifield].conv
                            elif ifield == 4:
                                D[ifield, ihr, iday1] = float(ishobs[12] * 100 + ishobs[13])
                            else:
                                D[ifield, ihr, iday1] = float(ishobs[ifield])
                        rpt_use = rpt_type
                        _extra_ishd(s, D, ihr, iday1, ishobs, sustituir=True)
                else:
                    writedat = True
                    if not s.lsfcobs[iday1]:
                        s.lsfcobs[iday1] = True
                    s.nomisshr[ihr, iday1] = True
                    s.nsfc1[iday1] += 1
                    rpt_use = rpt_type
                    s.nsfc[2] += 1
                    if reg_obs:
                        s.nsfc[4] += 1
                    if spec_obs:
                        if m.debug:
                            E.w(mu, F[6], pid(E), "I44", modnam, "OBSERVATION FOR DATE:", date_hr_str,
                                "IS SPECIAL OBSERVATION REPORT TYPE:", rpt_type.strip())
                        s.nsfc[3] += 1
                    for ifield in range(1, s.nsfvars_keep + 1):
                        if (1 < ifield < 10 and ifield != 4) or (ifield == 11 and ishobs[ifield] != sv[ifield].missval):
                            if ishobs[ifield] == sv[ifield].missval:
                                D[ifield, ihr, iday1] = float(ishobs[ifield])
                            else:
                                D[ifield, ihr, iday1] = float(ishobs[ifield]) * sv[ifield].conv
                        elif ifield == 4:
                            D[ifield, ihr, iday1] = float(ishobs[12] * 100 + ishobs[13])
                        elif ifield == 1 and ishobs[ifield] != sv[ifield].missval:
                            D[ifield, ihr, iday1] = float(ishobs[1]) / 10.0
                        else:
                            D[ifield, ihr, iday1] = float(ishobs[ifield])
                    _extra_ishd(s, D, ihr, iday1, ishobs, sustituir=False)
                savedate = sdate
                savehr = ihr
                last_rpt = rpt_type
                lastline = datline
                ishobs = [None] + list(missobs[1:])
        else:
            E.w(mu, ef[1], pid(E), "E42", modnam, "INVALID DATE FIELD:", control[15:27])
            m.lbad = True
            fdis.escribir(datline.strip())
    if not s.lbadsfc and m.lbad:
        s.lbadsfc = True
    E.cerrar(m.ishd_units[1])
    E.cerrar(m.ishd_units[2])


def _extra_ishd(s, D, ihr, iday1, ishobs, sustituir):
    sv = s.sfvars
    if sv[12].laudit or sv[20].laudit or sv[21].laudit:
        ifield1 = 0
        for ifield in range(s.nsfvars_keep + 1, s.nsfvars + 1):
            if sv[ifield].laudit:
                ifield1 += 1
            if ifield in (12, 20, 21) and sv[ifield].laudit:
                k = ifield1 + s.nsfvars_keep
                if sustituir:
                    if ifield == 12 and ishobs[4] != sv[12].missval:
                        D[k, ihr, iday1] = ishobs[4]
                    if ifield == 20 and ishobs[15] != sv[20].missval:
                        D[k, ihr, iday1] = ishobs[15]
                    if ifield == 21 and ishobs[14] != sv[21].missval:
                        D[k, ihr, iday1] = ishobs[14]
                else:
                    if ifield == 12:
                        D[k, ihr, iday1] = ishobs[4]
                    if ifield == 20:
                        D[k, ihr, iday1] = ishobs[15]
                    if ifield == 21:
                        D[k, ihr, iday1] = ishobs[14]


def _ri(txt):
    """read(txt,'(iN)') : entero con blancos ignorados (0 si vacío o no numérico como el FORMAT
    de Intel con error, que el original no comprueba)."""
    t = txt.replace(" ", "")
    if t == "" or t in "+-":
        return 0
    try:
        return int(t)
    except ValueError:
        return 0


def _lee_lista(txt, tipos):
    """READ(txt,*) sin IOSTAT: el original aborta si falla."""
    v, ios, _ = lread(txt, tipos)
    if ios != 0:
        raise ErrorEjecucion("lectura dirigida por lista fallida: %r" % txt, FORRTL_EOF_LISTA)
    return v


def _i2_estricto(txt):
    """READ(txt,'(i2)') sin IOSTAT (blancos ignorados; otro carácter aborta el original)."""
    t = txt.replace(" ", "")
    if t == "":
        return 0
    if not t.lstrip("+-").isdigit():
        raise ErrorEjecucion("lectura '(i2)' fallida: %r" % txt, FORRTL_CONV_FORMATO)
    return int(t)


GHCN_NVAR = 53
# variable de sfvars de cada variable GHCN (0: no se guarda)
GHCN_SFVAR = [0, 7, 8, 3, 2, 10, 11, 0, 1, 9, 22] + [19] * 9 + [0, 21] + [0] * 4 + [12] + [0] * 27


def read_ghcn(E):
    """READ_GHCN: formato GHCN-h separado por barras (11 campos de estación y 53 variables de
    6 campos: valor, medida, calidad, tipo de informe, fuente y estación de origen)."""
    m, s = E.m, E.sf
    modnam = fx("READ_GHCN", 10)
    F = {k: fmt_msg(E, v) for k, v in {1: "a)", 2: "2(a,1x,i2,1x),a,1x,a20)", 3: "3(a,1x),a20)",
                                       4: "a,1x,f9.2,1x,a1)", 5: "a,1x,a20,4(1x,a))", 6: "a,1x,a20,2(1x,a))"}.items()}
    ef = s.ext_form
    mu = m.msg_unit
    nvar = GHCN_NVAR
    inc = 30
    tenths = [0, 0, 0, 3, 3, 5, 8, 10, 10]
    sky = ["SKC", "CLR", "CLR1", "FEW", "FEW2", "SCT", "BKN", "VV", "OVC"]
    rpt_list = ("FM12", "FM13", "FM14", "FM15", "FM16", "FM18", "SAO", "SAOSP", "AERO", "AUTO", "SYAE",
                "SYSA", "SYMT", "SYAU", "SAAU", "SSA", "SMARS")
    pvar, slpvar, altvar = 3, 4, 22
    sv = s.sfvars
    D = s.sfdata1
    sfvar = GHCN_SFVAR
    miss6 = sv[6].missval
    imiss_total = _idiv(sv[4].missval, 100)
    imiss_opaque = sv[4].missval - imiss_total * 100
    # posiciones de las barras del bloque de estación: el original no las borra entre registros
    P0 = [0] * 12
    rvar = [0.0] * (nvar + 1)
    reinicio = [(iv, 0.0 if iv == 8 else float(sv[sfvar[iv]].missval)) for iv in range(1, nvar + 1) if sfvar[iv]]
    fdata = E.units[m.sf_data_unit]
    E.abrir(m.ghcn_units[1], m.ghcn_files[1], "replace")
    E.abrir(m.ghcn_units[2], m.ghcn_files[2], "replace")
    fdis = E.units[m.ghcn_units[1]]
    frep = E.units[m.ghcn_units[2]]
    call_sign4 = call_sign3 = ""
    iwarn = 0
    spec_obs = reg_obs = False
    eof = 0
    sdate = savedate = savehr = 0
    gotwban = False
    savewban = 0
    iday1 = 0
    ihr = 0
    intvar = 0
    elev = 0.0
    iusaf = ""
    s.iwban = 0
    rpt_type = rpt_use = last_rpt = lastline = ""
    nremarks1 = 0
    remarks = []
    m.lbad = False
    while eof >= 0 and not m.lbad and sdate <= s.sfend:
        rec = fdata.leer()
        if rec is None:
            eof = -1
        else:
            eof = 0
            datline = rec[:10000].rstrip(" ")
        lgo2 = lgo3 = False
        have_elev = False
        npipes = 0
        total_cloud, opaque_cloud = imiss_total, imiss_opaque
        icloud = [None, imiss_total, imiss_opaque]
        if eof == 0 and "|Station_name|" in datline:
            eof = 2                                   # cabecera (ficheros concatenados): se salta
        if eof != 0:
            continue
        for iv, val in reinicio:
            rvar[iv] = val
        field = {}                                   # (variable, subcampo) -> texto
        lmiss = [True] * (nvar + 1)
        spec_obs = False
        # posiciones de las barras. Estación (ivar 0): pipe_loc(1) es la columna 0 y pipe_loc(j)
        # la barra j-1 (j = 2..11); variable iv: pipe_loc(ip) es la barra 11+6(iv-1)+ip-1
        partes = datline.split("|")
        npipes = len(partes) - 1
        if npipes > 6 * nvar + 10:
            raise ErrorEjecucion("registro GHCN con más campos de los previstos")
        pos = list(accumulate(len(x) + 1 for x in partes[:-1]))
        for j in range(2, min(npipes + 1, 11) + 1):
            P0[j] = pos[j - 2]

        def ploc(iv, ip):
            n = 6 * iv + ip + 4
            return pos[n - 1] if n <= npipes else 0

        j1, j2 = P0[4] + 1, P0[9] - 1
        vd, iflag, _ = fread("(i4,4(1x,i2.2))", sub(datline, j1, j2), ["i"] * 5)
        if iflag != 0:
            E.w(mu, ef[1], pid(E), "E42", modnam, "INVALID DATE FIELD:", sub(datline, j1, j2))
            m.lbad = True
            fdis.escribir(datline.strip(" "))
            continue
        iyear, imonth, iday, ihr, imin = vd
        ihr, iday, imonth, iyear, sdate, lgo = data_dates(E, ihr, iday, imonth, iyear, -1 if imin > 0 else 0,
                                                          s.sfstart, s.sfend, 42)
        ihr, iday, imonth, iyear, lgo, nd1, sdate = new_obs(E, iyear, imonth, iday, ihr, savedate, savehr)
        if nd1 is not None:
            iday1 = nd1
        date_hr_str = fwrite("(a5,1x,i8,1x,a2,1x,i2.2)", "DATE:", sdate, "HR", ihr)[0]
        if lgo:
            if imin == 0 or imin >= (60 - inc):
                lgo2 = True
            else:
                E.w(mu, F[2], pid(E), "I41", modnam, "OBSERVATION MINUTE", imin, "NOT WITHIN", inc,
                    "MINUTES OF HOUR FOR", date_hr_str)
                s.nsfc[10] += 1
                fdis.escribir(datline.strip(" "))
            if lgo2:
                # tipo de informe: el de la primera variable que lo tenga
                ivar = 1
                have_report = False
                rpt_type = ""
                while ivar <= nvar and not have_report:
                    j1, j2 = ploc(ivar, 4) + 1, ploc(ivar, 5) - 1
                    if j2 > j1:
                        ndash = sub(datline, j1, j2).find("-") + 1
                        rpt_type = fx(sub(datline, j1, j2) if ndash == 0 else sub(datline, j1, j1 + ndash - 2), 5)
                        have_report = True
                    else:
                        ivar += 1
                if rpt_type.strip(" ") in rpt_list:
                    lgo3 = True
                else:
                    if m.debug:
                        E.w(mu, F[3], pid(E), "I42", modnam, "REPORT TYPE", rpt_type.strip(" "), "NOT PROCESSED FOR",
                            date_hr_str)
                    s.nsfc[9] += 1
                    lgo3 = False
                    fdis.escribir(datline.strip(" "))
        if not lgo3:
            continue
        if sdate == savedate:
            if ihr != savehr:
                reg_obs = False
                rpt_use = ""
        else:
            reg_obs = False
        if rpt_type.strip(" ") in ("SAOSP", "FM16"):
            spec_obs = True
        else:
            reg_obs = True
        # identificadores: WBAN en el Station_ID, USAF en la estación de origen de la 1.ª variable que la tenga
        vv, iflag1, _ = fread("(i8)", sub(datline, 4, P0[2] - 1), ["i"])
        if iflag1 == 0:
            s.iwban = vv[0]
        ivar = 1
        lfound = False
        while ivar <= 37 and not lfound:
            j1, j2 = ploc(ivar, 6) + 1, ploc(ivar + 1, 1) - 1
            if j2 > j1:
                lfound = True
                t = sub(datline, j1, j2)
                if "ICAO" not in t:
                    ndash = t.find("-") + 1
                    v = _lee_lista(sub(datline, j1, j1 + ndash - 1), [("a", 8)])[0]
                    if v is not None:
                        iusaf = v
            else:
                ivar += 1
        if iflag1 == 0:
            iwban = s.iwban
            if not gotwban and iwban != 99999:
                savewban = iwban
                gotwban = True
                if iwban != s.isfid and iwban != 99999:
                    if iusaf.strip(" ") == s.sfid.strip(" "):
                        E.w(mu, ef[4], pid(E), "W41", modnam, "STATION ID", fx(iusaf, 8),
                            "IS WMO NUMBER; CONSIDER WBAN FOR STAGE 2")
                    else:
                        E.w(mu, ef[2], pid(E), "W40", modnam, "STATION ID", iwban, "DOES NOT MATCH USER ENTERED ID",
                            s.sfid.strip(" "))
                        iwarn += 1
            else:
                if iwban != savewban and iwban != 99999:
                    iwarn += 1
                    if iwarn <= s.nwarnlim:
                        E.w(mu, ef[2], pid(E), "W40", modnam, "STATION ID", iwban, "DOES NOT MATCH PREVIOUS WBAN",
                            s.sfid.strip(" "))
                    if iwarn == s.nwarnlim:
                        E.w(mu, ef[3], pid(E), "W42", modnam, "REACH LIMIT OF", s.nwarnlim, "W40", "WARNING MESSAGES")
            s.lasos, ah = check_asos(E, iwban, sdate, ihr, True, True, False, s.lasos, alias=True)
            s.asoshr[ihr, iday1] = ah
        else:
            # el original muestra la última subcadena buscada (la de la estación de origen)
            E.w(mu, ef[1], pid(E), "E47", modnam, "INVALID STATION ID FIELD:", sub(datline, j1, j2))
            m.lbad = True
        j1, j2 = ploc(1, 6) + 1, ploc(2, 1) - 1
        t = sub(datline, j1, j2)
        if "ICAO" in t:
            ndash = t.find("-") + 1
            v = _lee_lista(sub(datline, j1 + ndash, j2), [("a", 4)])[0]
            if v is not None:
                call_sign4 = v
            v = _lee_lista(sub(datline, j1 + ndash + 1, j2), [("a", 3)])[0]
            if v is not None:
                call_sign3 = v
        # coordenadas: solo se comprueba que se leen (la «longitud» lee el campo del mes, como el original)
        for a, b in ((9, 10), (5, 6)):
            j1, j2 = P0[a] + 1, P0[b] - 1
            _, iflag1, _ = lread(sub(datline, j1, j2), ["f"])
            if iflag1 != 0:
                E.w(mu, ef[1], pid(E), "E44", modnam, "INVALID COORDINATES FIELD:", sub(datline, j1, j2))
                m.lbad = True
        j1, j2 = P0[11] + 1, ploc(1, 1) - 1
        vv, iflag1, _ = lread(sub(datline, j1, j2), ["f"])
        if iflag1 == 0:
            if vv[0] is not None:
                elev = vv[0]
            if elev == 9999.0:
                if s.user_elev:
                    E.w(mu, F[4], pid(E), "W43", modnam,
                        "STATION ELEVATION PROVIDED IN FILE BUT MISSING; USE USER ELEVATION", s.sfelev, "M")
                else:
                    E.w(mu, ef[1], pid(E), "W43", modnam,
                        "STATION ELEVATION PROVIDED IN FILE BUT MISSING; NO USER ELEVATION,",
                        "CONSIDER INPUTTING ELEVATION")
            else:
                have_elev = True
                if s.user_elev:
                    if abs(s.sfelev - elev) > 0.02 * elev:
                        E.w(mu, ef[9], pid(E), "W43", modnam, "USER ENTERED ELEVATION", s.sfelev,
                            "M DIFFERS FROM ELEVATION", elev, "M IN GHCN FILE")
                s.sfelev = elev
                s.lsfelev = True
        else:
            E.w(mu, ef[1], pid(E), "E43", modnam, "INVALID ELEVATION FIELD:", sub(datline, j1, j2))
            m.lbad = True
        if not s.lasos:
            # primera estación de la lista ASOS con el mismo WBAN o indicativo (búsqueda lineal
            # del original, con índices)
            k = _asos_por_ids(s, savewban, call_sign4.strip(" "), call_sign3.strip(" "))
            if k is None:
                s.iasos = s.nasos + 1
            else:
                s.iasos = k
                s.lasos = True
            if s.lasos:
                E.w(mu, ef[4], pid(E), "W53", modnam, "STATION", s.sfid.strip(" "),
                    "FOUND IN ASOS LIST BASED ON STATION IDENTIFIERS IN SURFACE FILE")
                s.asoshr[ihr, iday1] = True
        # campos de cada variable; el valor (campo 1) se interpreta según la variable
        for iv, ip, fv in _campos_ghcn(datline, partes, npipes, nvar, ploc):
            field[iv, ip] = fv
            lmiss[iv] = False
            if ip != 1:
                continue
            if iv in (1, 2, 3, 4, 5, 6, 8, 9, 10, 20, 21, 22):
                if "." in fv:
                    vv, iflag, _ = lread(fv, ["f"])
                    if iflag == 0 and vv[0] is not None:
                        rvar[iv] = vv[0]
                else:
                    vv, iflag, _ = lread(fv, ["i"])
                    if iflag == 0 and vv[0] is not None:
                        intvar = vv[0]
                        rvar[iv] = float(intvar)
            elif iv == 26:                                    # techo de nubes
                vv, iflag, _ = lread(fv, ["i"])
                if iflag == 0:
                    if vv[0] is not None:
                        intvar = vv[0]
                    intvar = 300 if intvar == 22000 else int(float(intvar) / 100.0)
                    rvar[iv] = float(intvar)
            elif iv == 24:                                    # nubosidad total;opaca (octas)
                fv = fv.replace(";", ",")
                field[iv, ip] = fv
                vv, iflag, _ = lread(fv, ["i", "i"])
                for kk, x in enumerate(vv, 1):
                    if x is not None:
                        icloud[kk] = x
                for i in (1, 2):
                    if icloud[i] > 1:
                        if icloud[i] <= 5:
                            icloud[i] += 1
                        elif icloud[i] <= 8:
                            icloud[i] += 2
                        elif icloud[i] <= 10:
                            icloud[i] = 10
                total_cloud, opaque_cloud = icloud[1], icloud[2]
            elif iv in (27, 28, 29, 30, 35, 36, 37, 38):      # cobertura por capas
                ncolon = fv.find(":") + 1
                vv, iflag, _ = lread(sub(fv, ncolon + 1, ncolon + 2), ["i"])
                ft = fv.strip(" ")
                if iflag == 0:
                    if vv[0] is not None:
                        intvar = vv[0]
                    if intvar > 1:
                        if intvar <= 5:
                            intvar += 1
                        elif intvar <= 8:
                            intvar += 2
                        elif intvar <= 10:
                            intvar = 10
                        else:
                            intvar = miss6
                elif ft == "CLR":
                    intvar = 0
                elif ft == "FEW":
                    intvar = 2
                elif ft == "SCT":
                    intvar = 5
                elif ft == "BKN":
                    intvar = 7
                elif ft in ("OVC", "VV", "X"):
                    intvar = 10
                else:
                    intvar = miss6
                rvar[iv] = float(intvar)
        if total_cloud == 999:
            total_cloud = imiss_total
        if opaque_cloud == 999:
            opaque_cloud = imiss_opaque
        ivar = 38
        asky = miss6
        if s.asoshr[ihr, iday1] and total_cloud == imiss_total and opaque_cloud == imiss_opaque:
            while ivar > 34 and asky == miss6:
                if not lmiss[ivar]:
                    asky = int(rvar[ivar])
                    if asky == miss6:
                        raise ErrorEjecucion("el original entra en un bucle sin fin (cobertura ASOS de la "
                                             "variable GHCN %d ausente)" % ivar)
                else:
                    ivar -= 1
            if asky == miss6:
                # el original recorre 29..27 pero mira siempre la variable 30
                if not lmiss[30]:
                    asky = int(rvar[30])
        rem = field.get((nvar, 1), "")
        if (total_cloud == imiss_total and opaque_cloud == imiss_opaque and asky == miss6 and
                sub(rem, 1, 3) in ("MET", "SYN")):
            rem = rem.replace("/", "_")
            field[nvar, 1] = rem
            nremarks = 0
            infield = inquote = False
            for c in rem.rstrip(" "):
                if not infield and c == '"':
                    infield = inquote = True
                    nremarks += 1
                elif not infield and c != " ":
                    infield = True
                    nremarks += 1
                elif inquote and c == '"':
                    infield = inquote = False
                elif not inquote and infield and c == " ":
                    infield = False
            remarks = [""] * nremarks
            vv = _lee_lista(fx(rem, 300), [("a", 20)] * nremarks)
            for kk, x in enumerate(vv):
                if x is not None:
                    remarks[kk] = x
            nremarks1 = nremarks
            if rem[:3] == "MET":
                for r in remarks:
                    for isky in range(9):
                        if sub(r, 1, len(sky[isky])) == sky[isky]:
                            asky = tenths[isky] if asky == miss6 else max(asky, tenths[isky])
                            break
            else:
                intvar = 99
                vv, iflag, _ = lread(sub(remarks[2] if nremarks >= 3 else "", 1, 1), ["i"])
                if iflag == 0:
                    if vv[0] is not None:
                        intvar = vv[0]
                    if intvar <= 5:
                        asky = intvar + 1
                    elif intvar <= 8:
                        asky = intvar + 2
                    elif intvar <= 10:
                        asky = 10
        if lmiss[9] and not lmiss[1] and not lmiss[2]:
            rvar[9] = humidity(rvar[1], rvar[2])
        # calmas y vientos variables (el original compara con el ausente de la variable 22)
        m22 = float(sv[sfvar[10]].missval)
        if not lmiss[5] and rvar[5] == m22:
            if ch(field.get((5, 2), ""), 1) == "C" or ch(field.get((6, 2), ""), 1) == "C" or rvar[6] == 0.0:
                rvar[5] = 0.0
                s.nsfc[11] += 1
            elif ch(field.get((5, 2), ""), 1) == "V" or rvar[6] == m22:
                s.nsfc[12] += 1
        if not lmiss[21]:
            rvar[21] = rvar[21] * 10.0
        ipcode1 = [None, 0, 0]
        for iv in (11, 12):
            if lmiss[iv]:
                continue
            fv = field.get((iv, 1), "")
            ncolon = fv.find(":") + 1
            w1 = _i2_estricto(sub(fv, 1, 2) if ncolon == 0 else sub(fv, ncolon + 1, ncolon + 2))
            if w1 <= 19:
                ipcode1[iv - 10] = 0
            elif w1 == 22 or 36 <= w1 <= 39 or 70 <= w1 <= 79 or w1 == 85 or w1 == 86:
                ipcode1[iv - 10] = 2
            elif w1 == 21 or w1 == 25:
                ipcode1[iv - 10] = 1
            elif w1 <= 28:
                ipcode1[iv - 10] = 3
            elif w1 <= 49:
                ipcode1[iv - 10] = 0
            elif w1 in (56, 57) or 66 <= w1 <= 69 or 83 <= w1 <= 90 or w1 >= 93:
                ipcode1[iv - 10] = 3
            else:
                ipcode1[iv - 10] = 1
        if ipcode1[1] <= 2 and ipcode1[2] == ipcode1[1]:
            ipcode = ipcode1[1]
        elif (ipcode1[1], ipcode1[2]) in ((1, 2), (2, 1)):
            ipcode = 3
        else:
            ipcode = max(ipcode1[1], ipcode1[2])
        if rvar[8] == float(sv[1].missval) or rvar[8] == 0.0:
            ipcode = 0
        # presiones (los valores calculados no se guardan: la variable sigue «ausente», como en el original)
        if lmiss[pvar] and float(D[3, ihr, iday1]) == float(sv[3].missval):
            if not lmiss[altvar] and lmiss[slpvar]:
                rvar[pvar] = pressure(E, 2, s.sfelev, 290.0, rvar[altvar])
            if lmiss[altvar] and lmiss[slpvar]:
                if have_elev and not s.user_elev:
                    rvar[pvar] = 1013.25 * (1.0 - ((6.5e-3 / 288.15) * s.sfelev)) ** 5.255
            if not lmiss[slpvar]:
                if have_elev and not s.user_elev:
                    rvar[pvar] = pressure(E, 2, s.sfelev, 290.0, rvar[slpvar])
        else:
            if lmiss[slpvar] and float(D[2, ihr, iday1]) == float(sv[2].missval):
                if have_elev and not s.user_elev:
                    rvar[slpvar] = pressure(E, 1, s.sfelev, 290.0, rvar[pvar])
        if s.nomisshr[ihr, iday1]:
            loverwrite = [True] * (nvar + 1)
            mp, mt, md, mwd, mc, writedat = check_dup(E, iday1, ihr, rvar[8], rvar[1], rvar[5], rvar[6],
                                                      float(total_cloud), float(opaque_cloud), float(asky))
            if spec_obs and reg_obs:
                s.nsfc[6] += 1
                writedat = False
                fdis.escribir(datline.strip(" "))
            elif reg_obs and not writedat:
                s.nsfc[7] += 1
                fdis.escribir(datline.strip(" "))
            else:
                if spec_obs and rpt_use.strip(" ") in ("SAOSP", "FM16"):
                    s.nsfc[6] += 1
                if reg_obs:
                    if rpt_use.strip(" ") in ("SAOSP", "FM16"):
                        s.nsfc[4] += 1
                        s.nsfc[6] += 1
                        s.nsfc[3] -= 1
                    else:
                        s.nsfc[7] += 1
                if m.debug:
                    E.w(mu, F[5], pid(E), "I45", modnam, "OBSERVATION REPLACED FOR", date_hr_str,
                        "WITH REPORT TYPE:", rpt_type.strip(" "), "REPLACING REPORT TYPE:", last_rpt.strip(" "))
                frep.escribir(lastline.strip(" "))
                if not mp and (rvar[8] > 0.0 or (float(D[1, ihr, iday1]) == float(sv[1].missval) and rvar[8] == 0.0)):
                    D[1, ihr, iday1] = rvar[8]
                    D[5, ihr, iday1] = float(ipcode)
                if rvar[4] == float(sv[2].missval) and float(D[2, ihr, iday1]) != float(sv[2].missval):
                    loverwrite[4] = False
                if rvar[3] == float(sv[3].missval) and float(D[3, ihr, iday1]) != float(sv[3].missval):
                    loverwrite[3] = False
                if rvar[2] == float(sv[8].missval) and float(D[8, ihr, iday1]) != float(sv[8].missval):
                    loverwrite[2] = False
                if rvar[9] == float(sv[9].missval) and float(D[9, ihr, iday1]) != float(sv[9].missval):
                    loverwrite[9] = False
                for iv in range(1, nvar + 1):
                    if not loverwrite[iv] or lmiss[iv] or sfvar[iv] == 0 or sfvar[iv] >= 12 or iv == 8:
                        continue
                    D[sfvar[iv], ihr, iday1] = rvar[iv]
                if mc[1]:
                    total_cloud = _idiv(int(float(D[4, ihr, iday1])), 100)
                if mc[2]:
                    v4 = int(float(D[4, ihr, iday1]))
                    opaque_cloud = v4 - _idiv(v4, 100) * 100
                if 0 <= total_cloud <= 10 and 0 <= opaque_cloud <= 10 and opaque_cloud > total_cloud:
                    opaque_cloud = total_cloud
                D[4, ihr, iday1] = float(total_cloud * 100 + opaque_cloud)
                if mc[3] and s.asoshr[ihr, iday1]:
                    asky = int(float(D[6, ihr, iday1]))
                D[6, ihr, iday1] = float(asky)
                rpt_use = rpt_type
                if sv[12].laudit or sv[20].laudit or sv[21].laudit or sv[22].laudit:
                    _extra_ghcn(s, D, ihr, iday1, rvar, sustituir=True)
        else:
            writedat = True
            if not s.lsfcobs[iday1]:
                s.lsfcobs[iday1] = True
            s.nomisshr[ihr, iday1] = True
            s.nsfc1[iday1] += 1
            rpt_use = rpt_type
            s.nsfc[2] += 1
            if reg_obs:
                s.nsfc[4] += 1
            if spec_obs:
                if m.debug:
                    E.w(mu, F[6], pid(E), "I44", modnam, "OBSERVATION FOR DATE:", date_hr_str,
                        "IS SPECIAL OBSERVATION REPORT TYPE:", rpt_type.strip(" "))
                s.nsfc[3] += 1
            for iv in range(1, nvar + 1):
                if (lmiss[iv] and iv != 8) or sfvar[iv] == 0 or sfvar[iv] >= 12 or iv == 12:
                    continue
                D[sfvar[iv], ihr, iday1] = rvar[iv]
            D[4, ihr, iday1] = float(total_cloud * 100 + opaque_cloud)
            D[5, ihr, iday1] = float(ipcode)
            D[6, ihr, iday1] = float(asky)
            if sv[12].laudit or sv[20].laudit or sv[21].laudit:
                _extra_ghcn(s, D, ihr, iday1, rvar, sustituir=False)
        savedate = sdate
        savehr = ihr
        last_rpt = rpt_type
        lastline = datline
    if not s.lbadsfc and m.lbad:
        s.lbadsfc = True
    E.cerrar(m.ghcn_units[1])
    E.cerrar(m.ghcn_units[2])


def _campos_ghcn(datline, partes, npipes, nvar, ploc):
    """Subcampos no vacíos (variable, subcampo 1..6, texto) en el orden del original, que los
    recorre por las posiciones de las barras. Con el registro completo (todas sus barras) es lo
    mismo que los trozos entre barras; si no, se sigue el recorrido por posiciones."""
    if npipes == 6 * nvar + 10:
        for iv in range(1, nvar + 1):
            b = 6 * iv + 5
            sp = partes[b:b + 6]
            if not any(sp):
                continue
            for ip in range(6):
                if sp[ip]:
                    yield iv, ip + 1, sp[ip][:300]
        return
    ltrim = len(datline)
    for iv in range(1, nvar + 1):
        for ip in range(1, 7):
            j1 = ploc(iv, ip)
            if ip < 6:
                j2 = ploc(iv, ip + 1)
            elif iv < nvar:
                j2 = ploc(iv + 1, 1)
            else:
                j2 = ltrim + 1
            if j2 - j1 > 1:
                yield iv, ip, datline[j1:j2 - 1][:300]


def _extra_ghcn(s, D, ihr, iday1, rvar, sustituir):
    """Techo (12), visibilidad (21) y temperatura húmeda (22) auditados, tras las variables fijas."""
    sv = s.sfvars
    ifield1 = 0
    for ifield in range(s.nsfvars_keep + 1, s.nsfvars + 1):
        if sv[ifield].laudit:
            ifield1 += 1
        if ifield in (12, 20, 21, 22) and sv[ifield].laudit:
            k = ifield1 + s.nsfvars_keep
            for f, iv in ((12, 26), (21, 21), (22, 10)):
                if ifield == f and (not sustituir or rvar[iv] != float(sv[ifield].missval)):
                    D[k, ihr, iday1] = rvar[iv]


def read_ext(E):
    m, s = E.m, E.sf
    modnam = fx("READ_EXT", 10)
    f1 = fmt_msg(E, "3(a,1x),a20)")
    f2 = fmt_msg(E, "2(a,1x),a)")
    f3 = fmt_msg(E, "a,1x,a20,1x,a)")
    f4 = fmt_msg(E, "a,1x,a)")
    ef = s.ext_form
    mu = m.msg_unit
    sv = s.sfvars
    D = s.sfdata1
    if s.sfstage1:
        ifile = m.sf_data_unit if s.lsfkeywords[1] else m.sf_extract_unit
    else:
        ifile = m.sf_qaout_unit
    f = E.units[ifile]
    iwarn = 0
    irec = 0
    savedate = E.sf.__dict__.setdefault("_read_ext_savedate", 0)
    savehr = 0
    iwban = 0
    iday1 = 0
    gmt2lst = 0
    m.lbad = False
    while not m.lbad:
        raw = f.leer()
        if raw is None:
            break
        L = raw[:m.linelen].upper()
        m.inpline1 = L
        m.ilen = len(L.rstrip(" "))
        irec += 1
        if irec == 2:
            n = 0
            for i in range(1, m.ilen + 1):
                if ch(L, i + 1) == " " and ch(L, i) != " ":
                    n += 1
            m.nfield = n
            i = L.find("LOCATION") + 1
            r = getloc(E, i + 8, s.lgmt2lst, s.lsfelev)
            s.sfid = r["stid"]
            s.sflat, s.sflon, s.sfgmt2lst, s.sfelev = r["lat"], r["lon"], r["gmt2lst"], r["elev"]
            s.lgmt2lst, s.lsfelev = r["lgmt2lst"], r["lelev"]
            v, io, _ = lread(s.sfid, ["i"])
            iwban = v[0] if v else 0
            gmt2lst = s.sfgmt2lst
            s.sfgmt2lst = 0
            if iwban != s.isfid:
                E.w(mu, ef[2], pid(E), "W40", modnam, "STATION ID ", iwban, "DOES NOT MATCH USER ENTERED ID",
                    s.sfid.strip())
            s.lasos = check_asos(E, iwban, 0, 0, True, False, False, s.lasos)[0]
            if not s.lasos:
                E.w(mu, f2, pid(E), "W54", modnam, "STATION", s.sfid.strip(), "NOT LISTED IN ASOS LIST; CHECK STATION ID")
            if not s.lasos and s.lsfkeywords[9]:
                E.w(mu, f4, pid(E), "W56", modnam, "DO NOT PROCESS 1-MINUTE DATA")
        elif irec == 3:
            vv, io, _ = lread(L, [("a", 8)] * 3)
            j1, j2, j3 = (vv + ["", "", ""])[:3]
            if j1.strip() != "FILE" or j2.strip() != "TYPE:" or (j3.strip() != "EXTRACT" and j3.strip() != "QAOUT"):
                E.w(mu, ef[1], pid(E), "E40", modnam, "INCORRECT FILE TYPE LINE; LINE", L.strip())
                m.lbad = True
        elif irec == 4:
            vv, iflag, _ = lread(L, [("a", 8)] + ["i"] * 6)
            if iflag != 0:
                E.w(mu, ef[1], pid(E), "E40", modnam, "ERROR READING EXTRACTION DATES INFORMATION; LINE", L.strip())
                m.lbad = True
        elif irec > 5 and "RANGE" not in L and "DATE " not in L:
            vv, iflag, _ = lread(L, ["i", "i", ("a", 1)] + ["f"] * s.nsfvars_keep)
            if iflag == 0:
                sdate, ihr, asosflag = vv[0], vv[1], vv[2]
                rsf = [None] + vv[3:]
                date_hr_str = fwrite("(a5,1x,i8,1x,a2,1x,i2.2)", "DATE:", sdate, "HR", ihr)[0]
                iyear, imonth, iday = sdate // 10000, (sdate // 100) % 100, sdate % 100
                ihr, iday, imonth, iyear, lgo, nd1, sdate = new_obs(E, iyear, imonth, iday, ihr, savedate, savehr)
                if nd1 is not None:
                    iday1 = nd1
                irec -= 1
                if lgo:
                    if asosflag == "Y":
                        s.asoshr[ihr, iday1] = True
                        if not s.lasos:
                            iwarn += 1
                            if iwarn <= s.nwarnlim:
                                E.w(mu, f3, pid(E), "W54", modnam, "STATION IS ASOS FOR", date_hr_str,
                                    "BUT NOT IN ASOS LIST OR NOT ASOS FOR DATE")
                            if iwarn == s.nwarnlim:
                                E.w(mu, ef[3], pid(E), "W42", modnam, "REACH LIMIT OF", s.nwarnlim, "W54", "WARNING MESSAGES")
                    elif asosflag == "N":
                        _, ah = check_asos(E, iwban, sdate, ihr, False, True, False, False)
                        s.asoshr[ihr, iday1] = ah
                    else:
                        E.w(mu, f1, pid(E), "E40", modnam, "INVALID ASOS FLAG", asosflag.strip(), " FOR", date_hr_str)
                        m.lbad = True
                    sky1 = _idiv(int(rsf[4]), 100)
                    sky2 = int(rsf[4]) - sky1 * 100
                    loverwrite = [None] + [True] * s.nsfvars_keep
                    if s.nomisshr[ihr, iday1]:
                        mp, mt, md, mwd, mc, writedat = check_dup(E, iday1, ihr, rsf[1], rsf[7], rsf[10], rsf[11],
                                                                  float(sky1), float(sky2), rsf[6])
                        if writedat:
                            E.w(mu, ef[5], pid(E), "I45", modnam, "OBSERVATION REPLACED FOR", date_hr_str)
                        if mc[1]:
                            sky1 = _idiv(int(float(D[4, ihr, iday1])), 100)
                        if mc[2]:
                            v4 = int(float(D[4, ihr, iday1]))
                            sky2 = v4 - _idiv(v4, 100) * 100
                        if 0 <= sky1 <= 10 and 0 <= sky2 <= 10 and sky2 > sky1:
                            sky2 = sky1
                        rsf[4] = float(sky1 * 100 + sky2)
                        if mc[3]:
                            loverwrite[6] = False
                        if mp or (rsf[1] == 0.0 and float(D[1, ihr, iday1]) != float(sv[1].missval)):
                            loverwrite[1] = False
                            loverwrite[5] = False
                        if rsf[2] == float(sv[2].missval) and float(D[2, ihr, iday1]) != float(sv[2].missval):
                            loverwrite[2] = False
                        if rsf[3] == float(sv[3].missval) and float(D[3, ihr, iday1]) != float(sv[3].missval):
                            loverwrite[3] = False
                        if rsf[8] == float(sv[8].missval) and float(D[8, ihr, iday1]) != float(sv[8].missval):
                            loverwrite[8] = False
                        if rsf[9] == float(sv[9].missval) and float(D[9, ihr, iday1]) != float(sv[9].missval):
                            loverwrite[9] = False
                    else:
                        if not s.lsfcobs[iday1]:
                            s.lsfcobs[iday1] = True
                        s.nomisshr[ihr, iday1] = True
                        writedat = True
                        s.nsfc1[iday1] += 1
                        s.nsfc[2] += 1
                    if writedat:
                        if rsf[10] == 0.0 and rsf[11] == 0.0:
                            s.nsfc[11] += 1
                        for ivar in range(1, s.nsfvars_keep + 1):
                            if not loverwrite[ivar]:
                                continue
                            D[ivar, ihr, iday1] = rsf[ivar]
                    savedate = sdate
                    savehr = ihr
            else:
                E.w(mu, ef[1], pid(E), "E40", modnam, "ERROR READING DATA; LINE", L.strip())
                m.lbad = True
    E.sf._read_ext_savedate = savedate
    s.sfgmt2lst = gmt2lst
    if not s.lbadsfc and m.lbad:
        s.lbadsfc = True


def sf_audit(E):
    m, s = E.m, E.sf
    modnam = fx("SF_AUDIT", 10)
    F = {k: fmt_msg(E, v) for k, v in {
        2: "i8,1x,a,1x,i2.2,2(1x,a),1x,i1,1x,a)", 3: "i8,1x,a,1x,i2.2,2(1x,a),1x,i1,1x,a2,i3,1x,a,i3)",
        4: "i8,1x,a,1x,i2.2,2(1x,a))", 5: "i8,1x,a,1x,i2.2,1x,a,1x,a2,i5,1x,a,i5)",
        6: "i8,1x,a,1x,i2.2,1x,a,1x,a2,f9.1,1x,a,f9.1)", 7: "i8,1x,a,1x,i2.2,1x,a)", 8: "i8,1x,a,1x,i2.2,1x,a)"}.items()}
    F[1] = "(1x,a,1x,i1,a,1x,2(a2,a1),a4,1x,a)"
    mu = m.msg_unit
    eps = m.eps
    sv = s.sfvars
    D = s.sfdata1
    s.sf_audit_index = [0] * (s.nsf_audit_vars + 1)
    i = 0
    lsplit = False
    for ivar in range(1, s.nsfvars + 1):
        if sv[ivar].laudit:
            i += 1
            s.sf_audit_index[i] = ivar
            if not lsplit:
                if ivar in (4, 5, 19) or 13 <= ivar <= 18:
                    lsplit = True
                    s.nsplit = 2
    ns = s.nsplit
    s.missvals = [[0.0] * (ns + 1) for _ in range(s.nsf_audit_vars + 1)]
    s.lowbound = [[0.0] * (ns + 1) for _ in range(s.nsf_audit_vars + 1)]
    s.upbound = [[0.0] * (ns + 1) for _ in range(s.nsf_audit_vars + 1)]
    s.sf_audit_counts = [[[0] * 5 for _ in range(ns + 1)] for _ in range(s.nsf_audit_vars + 1)]
    for ivar in range(1, s.nsf_audit_vars + 1):
        iv = s.sf_audit_index[ivar]
        v = sv[iv]
        if v.laudit:
            if iv in (4, 5, 19) or 13 <= iv <= 18:
                imult = 100 if iv == 4 else 1000
                s.missvals[ivar][1] = float(_idiv(v.missval, imult))
                s.missvals[ivar][2] = float(v.missval - _idiv(v.missval, imult) * imult)
                s.lowbound[ivar][1] = float(_idiv(v.lowbound, imult))
                s.upbound[ivar][1] = float(_idiv(v.upbound, imult))
                s.lowbound[ivar][2] = float(v.lowbound - _idiv(v.lowbound, imult) * imult)
                s.upbound[ivar][2] = float(v.upbound - _idiv(v.upbound, imult) * imult)
            else:
                for isplit in range(1, ns + 1):
                    s.missvals[ivar][isplit] = float(v.missval)
                    s.lowbound[ivar][isplit] = float(v.lowbound) * v.conv
                    s.upbound[ivar][isplit] = float(v.upbound) * v.conv
    lstr = [None, "LB", ""]
    ustr = [None, "UB", ""]
    for d in range(1, s.nsfdays + 1):
        si = s.sfc_info[d]
        if not si.sobs:
            continue
        adate = "%08d" % si.sfcdate
        if not m.noprint:
            E.w(OUTPUT_UNIT, F[1], "Stage", m.istage, ": QA'ing surface data for month/day/year", adate[4:6], "/",
                adate[6:8], "/", adate[0:4], "LST")
        for h in range(1, 25):
            iv2 = 0
            if not si.have_obs[h]:
                continue
            for ivar in range(1, s.nsf_audit_vars + 1):
                iv = s.sf_audit_index[ivar]
                v = sv[iv]
                if iv > s.nsfvars_keep:
                    iv2 += 1
                    iv1 = iv2
                else:
                    iv1 = iv
                c = s.sf_audit_counts[ivar]
                if iv in (4, 5, 19) or 13 <= iv <= 18:
                    imult = 100 if iv == 4 else 1000
                    val = int(float(D[iv1, h, d]))
                    parts = [None, _idiv(val, imult), 0]
                    parts[2] = val - parts[1] * imult
                    for isplit in range(1, ns + 1):
                        c[isplit][1] += 1
                        lowv = upv = False
                        pv = float(parts[isplit])
                        if abs(pv - s.missvals[ivar][isplit]) < eps:
                            c[isplit][2] += 1
                            if not v.lnomiss:
                                E.w(mu, F[2], pid(E), "Q40", modnam, si.sfcdate, "HR", h, v.varname.strip(), "PART", isplit,
                                    "MISSING")
                        else:
                            lb, ub = s.lowbound[ivar][isplit], s.upbound[ivar][isplit]
                            if v.lincbound:
                                if pv < lb and abs(pv - lb) > eps:
                                    lowv = True
                                    lstr[2] = "<"
                                if pv > ub and abs(pv - ub) > eps:
                                    upv = True
                                    ustr[2] = ">"
                            else:
                                if pv <= lb:
                                    lowv = True
                                    lstr[2] = "<="
                                if pv >= ub:
                                    upv = True
                                    ustr[2] = ">="
                            if lowv:
                                c[isplit][3] += 1
                                E.w(mu, F[3], pid(E), "Q41", modnam, si.sfcdate, "HR", h, v.varname.strip(), "PART",
                                    isplit, lstr[1], parts[isplit], lstr[2].strip(), int(lb))
                            if upv:
                                c[isplit][4] += 1
                                E.w(mu, F[3], pid(E), "Q42", modnam, si.sfcdate, "HR", h, v.varname.strip(), "PART",
                                    isplit, ustr[1], parts[isplit], ustr[2].strip(), int(ub))
                else:
                    lowv = upv = False
                    c[1][1] += 1
                    val = float(D[iv1, h, d])
                    if abs(val - s.missvals[ivar][1]) < eps:
                        c[1][2] += 1
                        if not v.lnomiss:
                            E.w(mu, F[4], pid(E), "Q40", modnam, si.sfcdate, "HR", h, v.varname.strip(), "MISSING")
                    else:
                        lb, ub = s.lowbound[ivar][1], s.upbound[ivar][1]
                        if v.lincbound:
                            if val < lb and abs(val - lb) > eps:
                                lowv = True
                                lstr[2] = "<"
                            if val > ub and abs(val - ub) > eps:
                                upv = True
                                ustr[2] = ">"
                        else:
                            if val <= lb:
                                lowv = True
                                lstr[2] = "<="
                            if val >= ub:
                                upv = True
                                ustr[2] = ">="
                        if lowv:
                            c[1][3] += 1
                            if iv == 6:
                                E.w(mu, F[5], pid(E), "Q41", modnam, si.sfcdate, "HR", h, v.varname.strip(), lstr[1],
                                    int(val), lstr[2].strip(), int(lb))
                            else:
                                E.w(mu, F[6], pid(E), "Q41", modnam, si.sfcdate, "HR", h, v.varname.strip(), lstr[1],
                                    val, lstr[2].strip(), lb)
                        if upv:
                            c[1][4] += 1
                            if iv == 6:
                                E.w(mu, F[5], pid(E), "Q42", modnam, si.sfcdate, "HR", h, v.varname.strip(), lstr[1],
                                    int(val), ustr[2].strip(), int(ub))
                            else:
                                E.w(mu, F[6], pid(E), "Q42", modnam, si.sfcdate, "HR", h, v.varname.strip(), lstr[1],
                                    val, ustr[2].strip(), ub)
            w10, w11 = float(D[10, h, d]), float(D[11, h, d])
            if abs(w10 - float(sv[10].missval)) > eps and abs(w11 - float(sv[11].missval)) > eps:
                if abs(w10 - 0.0) < eps:
                    if abs(w11 - 0.0) < eps:
                        s.sf_windstats[1] += 1
                        E.w(mu, F[7], pid(E), "Q43", modnam, si.sfcdate, "HR", h, "CALM WIND")
                    else:
                        s.sf_windstats[2] += 1
                        E.w(mu, F[8], pid(E), "Q45", modnam, si.sfcdate, "HR", h, "WDIR = 0, WSPD > 0")
                else:
                    if abs(w11 - 0.0) < eps:
                        s.sf_windstats[3] += 1
                        E.w(mu, F[8], pid(E), "Q44", modnam, si.sfcdate, "HR", h, "WDIR > 0, WSPD = 0")
            t7, t8 = float(D[7, h, d]), float(D[8, h, d])
            if abs(t7 - float(sv[7].missval)) > eps and abs(t8 - float(sv[8].missval)) > eps:
                if t7 < t8 and abs(t7 - t8) > eps:
                    s.sf_tempstat += 1
                    E.w(mu, F[7], pid(E), "Q43", modnam, si.sfcdate, "HR", h, "TMPD < TPDP")
            if sv[1].laudit and sv[5].laudit:
                v5 = int(float(D[5, h, d]))
                p1 = _idiv(v5, 1000)
                if float(D[1, h, d]) > 0.0 and abs(float(D[1, h, d]) - 0.0) > eps:
                    if abs(float(D[5, h, d]) - float(sv[5].missval)) < eps:
                        s.precip_wx[1] += 1
                        E.w(mu, F[7], pid(E), "Q46", modnam, si.sfcdate, "HR", h, "PRECIP WITHOUT WEATHER")
                else:
                    if (0 < p1 < 70) or p1 > 90:
                        s.precip_wx[2] += 1
                        E.w(mu, F[7], pid(E), "Q47", modnam, si.sfcdate, "HR", h, "WEATHER WITHOUT PRECIP")


def read_1min(E):
    m, s = E.m, E.sf
    modnam = fx("READ_1MIN", 10)
    f1 = "(1x,a,1x,i1,a,1x,2(a2,a1),a4,1x,a)"
    f2 = fmt_msg(E, "3(a,1x),a)")
    f3 = fmt_msg(E, "a,1x,a)")
    f4 = fmt_msg(E, "a,1x,i8,1x,a,1x,i8)")
    f5 = fmt_msg(E, "a,1x,i8,a1,i8,1x,a,1x,i8,a1,i8)")
    mu = m.msg_unit
    f = E.units[m.one_min_unit]
    lifw = False
    header_ = fx(f.leer() or "", 90)
    i = header_.find("WBAN:") + 1
    j = header_.find("Call") + 1
    if i > 0 and j > 0:
        s.sf1minid = header_[i + 4:j - 1]
    if s.sf1minid.strip() != s.sfid.strip():
        E.w(mu, f2, pid(E), "W40", modnam, "AERMINUTE WBAN", s.sf1minid.strip(), "DOES NOT MATCH SURFACE WBAN",
            s.sfid.strip())
        E.w(mu, f3, pid(E), "W56", modnam, "DO NOT PROCESS 1-MINUTE DATA")
        return
    i = header_.find("IFW:") + 1
    if i > 0:
        lifw = header_[i + 4:i + 5] == "Y"
    i = header_.find("IFW date:") + 1
    m.lbad = False
    if i > 0:
        vv, iflag1, _ = fread("(2(i2,1x),i4)", header_[i + 9:i + 19], ["i", "i", "i"])
        if iflag1 == 0:
            s.sonicdate = vv[2] * 10000 + vv[0] * 100 + vv[1]
        else:
            m.lbad = True
            E.w(mu, f3, pid(E), "E41", modnam, "INVALID DATE FIELD", header_[i + 10:i + 19].strip())
    savedate = 0
    irec = 0
    regs = f.restantes()
    k = 0
    while not m.lbad:
        vv, eof, n = lread(regs[k:], ["i", "i", "i", "i", "f", "f"])
        if eof != 0:
            break
        k += n
        iyear, imonth, iday, ihr, wspd1, wdir1 = vv
        irec += 1
        idate = (iyear + 2000) * 10000 + imonth * 100 + iday
        if idate < savedate:
            E.w(mu, f4, pid(E), "E41", modnam, "CURRENT DATE", idate, "IS BEFORE PREVIOUS DATE", savedate)
            m.lbad = True
        if irec == 1:
            s.sfstart1min = idate
        else:
            s.sfend1min = idate
        savedate = idate
    f.rewind()
    if not m.lbad:
        loverlap = True
        if s.sfend1min < s.sfstart or s.sfstart1min > s.sfend:
            loverlap = False
            E.w(mu, f5, pid(E), "W48", modnam, "SURFACE DATES,", s.sfstart, "-", s.sfend, "DO NOT OVERLAP AERMINUTE DATES",
                s.sfstart1min, "-", s.sfend1min)
        if loverlap:
            s.nsf1mindays = numdays(s.sfstart, s.sfend)
            s.one_mindat = [None]
            for _ in range(s.nsf1mindays):
                o = Sf1Min()
                o.sf1mindate = 0
                o.ifwhr = [None] + [False] * 24
                o.wdir = [None] + [float(s.sfvars[10].missval)] * 24
                o.wspd = [None] + [float(s.sfvars[11].missval)] * 24
                s.one_mindat.append(o)
            f.leer()
            regs = f.restantes()
            k = 0
            savedate = 0
            iday1 = 0
            while True:
                vv, eof, n = lread(regs[k:], ["i", "i", "i", "i", "f", "f"])
                if eof != 0:
                    break
                k += n
                iyear, imonth, iday, ihr, wspd1, wdir1 = vv
                idate = (iyear + 2000) * 10000 + imonth * 100 + iday
                if s.sfstart <= idate <= s.sfend:
                    if idate != savedate:
                        iday1 += 1
                        adate = "%08d" % idate
                        if not m.noprint:
                            E.w(OUTPUT_UNIT, f1, "Stage", m.istage, ": Extracting 1-minute data for month/day/year",
                                adate[4:6], "/", adate[6:8], "/", adate[0:4], "LST")
                    o = s.one_mindat[iday1]
                    o.sf1mindate = idate
                    if lifw and idate >= s.sonicdate:
                        o.ifwhr[ihr] = True
                    o.wspd[ihr] = wspd1
                    o.wdir[ihr] = wdir1
                savedate = idate
    else:
        s.lbadsfc = True
