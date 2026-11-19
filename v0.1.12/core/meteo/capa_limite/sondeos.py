# -*- coding: utf-8 -*-
"""Traducción de AERMET 26135 (US EPA, dominio público): módulo UPPERAIR (radiosondeos).

Lectura del control, extracción de los formatos FSL (NOAA/ESRL RAOB) e IGRA (globales) y del
EXTRACT/QAOUT, control de calidad, modificaciones automáticas y ficheros EXTRACT/QAOUT.
Fuera de alcance: los formatos TD-6201 (sólo EE. UU.)."""
import datetime as _dt
import math

from . import tablas as T
from .comun import (checkfile, data_dates, dataline, fmt_msg, getdates, getfields, getloc, getunit,
                    leapyr, numdays, pid, range_mod, var_list)
from .estado import OUTPUT_UNIT, Uavar
from .formato import ch, fread, fwrite, fx, lread, nint, sub
from .control_cl import NoTraducido


class Sondeos:
    """updata1(ivar, nivel, sondeo, día): sólo se guardan los sondeos que existen."""

    def __init__(self, nvars, defecto, maxlevels):
        self.nvars = nvars
        self.defecto = defecto        # lista 1..nvars con el valor inicial de cada variable
        self.maxlevels = maxlevels
        self.d = {}

    def get(self, d, h):
        k = (d, h)
        a = self.d.get(k)
        if a is None:
            a = [None] + [[v] * (self.maxlevels + 2) for v in self.defecto[1:]]
            self.d[k] = a
        return a


class SondeosEst:
    """updata(ivar, nivel, sondeo, día, estación)."""

    def __init__(self):
        self.d = {}

    def get(self, st, d, h):
        return self.d.get((st, d, h)) or _VACIO


_VACIO = [None] + [[0.0] * 302 for _ in range(6)]


class SdInfo:
    __slots__ = ("snddate", "nsnding", "snd_hr", "nlevels", "sounding")

    def __init__(self):
        self.snddate = 0
        self.nsnding = 0
        self.snd_hr = None
        self.nlevels = None
        self.sounding = False


def upper_init(E):
    u = E.up
    u.upvars = [None] + [Uavar(t) for t in T.UPVARS[1:]]
    from .estado import Formato
    u.upformats = [None] + [Formato(t, ("uformat", "lupform", "maxblock", "rdsz", "rdpos", "offset"))
                            for t in T.UPFORMATS[1:]]
    ef = {1: "a,1x,a)", 2: "a,1x,i3,1x,a,1x,i3,1x,a,1x,i8)", 3: "a,1x,i5,2(1x,a))", 4: "5(a,1x),i5,1x,a20)",
          5: "a,1x,i3,1x,a3,1x,a)", 6: "3(a,1x),i5)", 7: "a,1x,i4,1x,a,1x,i5,2(1x,a))", 8: "a,1x,i5,1x,a20)",
          9: "2(a,1x,i5,1x),a20)", 10: "a,1x,i5,1x,a20)", 11: "a,1x,i5,2(1x,a),1x,a20)", 12: "a,1x,i5,1x,a20)",
          13: "a)", 14: "a,1x,i5)"}
    for k, v in ef.items():
        u.ext_form[k] = fmt_msg(E, v)


EXT_ERRSTR = [None, "ERROR READING DATE/HOUR FOR SOUNDING #", "ERROR READING MONTH FOR SOUNDING #",
              "ERROR READING STATION INFORMATION FOR SOUNDING #", "ERROR DETERMINING LINE TYPE FOR SOUNDING #",
              "ERROR DETERMINING NUMBER OF LEVELS FOR SOUNDING #"]
EXT_ENDSTR = [None, "END OF DATA WINDOW ENCOUNTERED", "NO SOUNDINGS RETRIEVED; NO OTHER ERRORS",
              "NO SOUNDINGS RETRIEVED; EXITING WITH AN ERROR", "EXTRACT NOT COMPLETED; STOPPED AFTER SDG #"]


def upper_path(E):
    m, u = E.m, E.up
    modnam = fx("UPPER_PATH", 10)
    f1 = fmt_msg(E, "a,1x,a)")
    f2 = fmt_msg(E, "i3,2(1x,a))")
    f3 = fmt_msg(E, "a,1x,i3,3(1x,a))")
    f4 = fmt_msg(E, "a,3(1x,a))")
    f5 = fmt_msg(E, "a)")
    form1 = "(a%3d)" % m.flength
    getunit(E)
    m.lbad = False
    ikey = m.ikey
    if ikey == 0:
        upper_init(E)
        return
    kw = m.keywrd[ikey].strip()
    i = m.inpline1.find(kw) + 1
    i1 = len(kw)
    istation = 1
    if ikey in (4, 5) or 7 <= ikey <= 13 or ikey >= 42:
        if ikey <= 5:
            jj = ikey - 3
        elif ikey >= 42:
            jj = ikey - 32
            istation = 2
            if not u.lsecondary:
                u.lsecondary = True
                u.nstation = 2
        else:
            jj = ikey - 4
        while len(u.lupkeywords) <= jj:
            u.lupkeywords.append(False)
        if not u.lupkeywords[jj]:
            u.lupkeywords[jj] = True
        else:
            if ikey == 4 or 7 <= ikey < 11:
                E.w(m.writeunit, f1, pid(E), "E03", modnam, "DUPLICATE ENTRY OF KEYWORD:", kw)
                m.lbad = True
                return
    else:
        E.w(m.writeunit, f1, pid(E), "E01", modnam, "INVALID KEYWORD:", kw)
        m.lbad = True
        return

    def mal():
        E.w(m.writeunit, f2, pid(E), "E03", modnam, m.nfield, "IS AN INVALID NUMBER OF FIELDS FOR KEYWORD", kw)
        m.lbad = True

    if ikey == 4 or ikey == 42:
        u.upstage1[istation] = True
        if m.nfield < 3 or m.nfield > 5:
            mal()
        else:
            if m.nfield != 3:
                E.w(m.writeunit, f3, pid(E), "W01", modnam, "TOO MANY FIELDS", m.nfield, "FOR", kw,
                    "KEYWORD; BLOCKING FACTOR AND/OR TYPE NOT NEEDED")
            dataline(E, i, i1)
            m.up_inpfile[istation] = sub(m.inpline, m.fileind[1], m.fileind[2])
            m.up_inpfile[istation], lgood = checkfile(E, m.up_data_unit[istation], m.up_inpfile[istation], 1)
            v, io, _ = lread(sub(m.inpline1, m.formind[1], m.formind[2]), [("a", 10)])
            fileform = v[0].strip() if v else ""
            j = 1
            lvalid = False
            while j <= u.nupformats and not lvalid:
                if fileform == u.upformats[j].uformat.strip():
                    u.upformats[j].lupform = True
                    lvalid = True
                    u.iupform[istation] = j
                j += 1
            if not lvalid:
                E.w(m.writeunit, f4, pid(E), "E04", modnam, "INVALID FILE FORMAT", fileform, "FOR UPPER AIR FILE",
                    m.up_inpfile[istation].strip())
                m.lbad = True
    elif ikey == 5 or ikey == 43:
        upper_list(E, i + i1, istation)
    elif ikey == 7 or ikey == 44:
        u.upstage1[istation] = True
        if m.nfield != 2:
            mal()
        else:
            m.up_extfile[istation] = fread(form1, sub(m.inpline, i + i1 + 1, m.ilen), [("a", m.flength)])[0][0]
            m.up_extfile[istation], lgood = checkfile(E, m.up_extract_unit[istation], m.up_extfile[istation], 4)
    elif ikey == 8 or ikey == 45:
        if m.nfield != 2:
            mal()
        else:
            m.up_qafile[istation] = fread(form1, sub(m.inpline, i + i1 + 1, m.ilen), [("a", m.flength)])[0][0]
            m.up_qafile[istation], lgood = checkfile(E, m.up_qaout_unit[istation], m.up_qafile[istation], 4)
    elif ikey == 9:
        if m.nfield not in (3, 4, 7, 8):
            mal()
        else:
            a, b, dts = getdates(E, i + i1)
            u.upstarts[1], u.upends[1] = a, b
            u.updates1[1] = [list(r) for r in dts]
            u.updates = [[0] * 4 for _ in range(3)]
    elif ikey == 10 or ikey == 46:
        if m.nfield < 4 or m.nfield > 6:
            mal()
        else:
            r = getloc(E, i + i1, u.lgmt2lst[istation], u.lelev[istation])
            u.upid[istation] = r["stid"]
            u.uplat[istation], u.uplon[istation] = r["lat"], r["lon"]
            u.upgmt2lst[istation], u.upelev[istation] = r["gmt2lst"], r["elev"]
            u.lgmt2lst[istation], u.lelev[istation] = r["lgmt2lst"], r["lelev"]
            if not u.lelev[istation]:
                E.w(m.writeunit, f5, pid(E), "E05", modnam,
                    "STATION ELEVATION NOT ENTERED; MAY BE NEEDED FOR UPPERAIR PROCESSING")
                m.lbad = True
    elif ikey == 12 or ikey == 48:
        if m.nfield != 6:
            mal()
        else:
            up_range(E, i + i1, istation)
    elif ikey == 13 or ikey == 49:
        upper_list(E, i + i1, istation)
    elif ikey == 11 or ikey == 48:
        if m.nfield > u.nmods + 1:
            mal()
        else:
            up_modkey(E, i + i1, istation)
    else:
        E.w(m.writeunit, f1, pid(E), "E01", modnam, "INVALID KEYWORD:", kw)


def upper_list(E, i1, istation):
    m, u = E.m, E.up
    modnam = fx("UPPER_LIST", 10)
    nfield1 = m.nfield - 1
    formstr = fmt_msg(E, "a,3(1x,a))")
    uvar = [None] + [u.upvars[i].varname for i in range(1, u.nupvars + 1)]
    ul = [None]
    for i in range(1, u.nupvars + 1):
        if m.ikey == 5 or m.ikey == 50:
            ul.append(u.upvars[i].lnomiss[istation])
        else:
            ul.append(u.upvars[i].laudit[istation])
    var_list(E, i1, nfield1, uvar, ul, u.nupvars)
    for i in range(1, u.nupvars + 1):
        v = u.upvars[i]
        if m.ikey == 5 or m.ikey == 43:
            if v.lnomiss[istation]:
                E.w(m.writeunit, formstr, pid(E), "W02", modnam, "DUPLICATING LISTING OF VARIABLE FOR",
                    v.varname.strip(), "KEYWORD", m.keywrd[m.ikey].strip())
            v.lnomiss[istation] = ul[i]
        else:
            if v.laudit[istation] and v.varname in m.inpline1:
                E.w(m.writeunit, formstr, pid(E), "W02", modnam, "DUPLICATING LISTING OF VARIABLE FOR",
                    v.varname.strip(), "KEYWORD", m.keywrd[m.ikey].strip())
            else:
                v.laudit[istation] = ul[i]


def up_range(E, i1, istation):
    m, u = E.m, E.up
    modnam = fx("UP_RANGE", 10)
    nfield1 = m.nfield - 1
    formstr = fmt_msg(E, "3(a,1x),a)")
    varnam1 = getfields(E, i1, nfield1)
    i = 1
    lfound = False
    while i <= u.nupvars and not lfound:
        if varnam1[1].strip() == u.upvars[i].varname.strip():
            lfound = True
        else:
            i += 1
    if lfound:
        linc, lowval, hival, missval, lgood = range_mod(E, varnam1[2], varnam1[3], varnam1[4], varnam1[5])
        if lgood:
            v = u.upvars[i]
            if v.lmod[istation]:
                E.w(m.writeunit, formstr, pid(E), "W02", modnam, "DUPLICATING LISTING OF VARIABLE FOR",
                    m.keywrd[m.ikey].strip(), "KEYWORD:", v.varname.strip())
            v.lincbound[istation] = linc
            v.lowbound[istation] = lowval
            v.upbound[istation] = hival
            v.missval[istation] = missval
            if not v.lmod[istation]:
                v.lmod[istation] = True
    else:
        E.w(m.writeunit, formstr, pid(E), "E05", modnam, "INVALID VARIABLE NAME FOR", m.keywrd[m.ikey].strip(),
            "KEYWORD:", varnam1[1].strip())
        m.lbad = True


def up_modkey(E, i1, istation):
    m, u = E.m, E.up
    modnam = fx("UP_MODKEY", 10)
    formstr = fmt_msg(E, "a,3(1x,a))")
    u_mods = [None, "DELMAND", "CALMDIR", "SUB_TTTD"]
    nfield1 = m.nfield - 1
    if nfield1 == 0:
        for j in range(1, u.nmods + 1):
            for st in (1, 2):
                u.lmodify[j][st] = True
        return
    mods1 = getfields(E, i1, nfield1)
    for i in range(1, nfield1 + 1):
        lfound = False
        j = 1
        while j <= u.nmods and not lfound:
            if mods1[i].strip() == u_mods[j]:
                lfound = True
                if u.lmodify[j][istation]:
                    E.w(m.writeunit, formstr, pid(E), "W02", modnam, "DUPLICATING LISTING OF MODIFICATION",
                        mods1[i].strip(), "FOR KEYWORD:", m.keywrd[m.ikey].strip())
                u.lmodify[j][istation] = True
            else:
                j += 1
        if not lfound:
            if mods1[i].strip() == "ALL":
                for jj in range(1, u.nmods + 1):
                    u.lmodify[jj][istation] = True
            else:
                E.w(m.writeunit, formstr, pid(E), "E05", modnam, "INVALID MODIFICATION", mods1[i].strip(),
                    "FOR KEYWORD:", m.keywrd[m.ikey].strip())
                m.lbad = True


def up_test(E):
    m, u = E.m, E.up
    modnam = fx("UP_TEST", 10)
    f1 = fmt_msg(E, "a,1x,a)")
    f2 = fmt_msg(E, "a)")
    mu = m.msg_unit
    u.upstart = u.upstarts[1]
    u.upend = u.upends[1]
    u.updates = [list(r) for r in u.updates1[1]]
    if u.lsecondary and u.upstage1[2]:
        u.updates1[2] = [list(r) for r in u.updates]
        u.upstarts[2] = u.upstart
        u.upends[2] = u.upend
    if u.lsecondary and not m.lstage[2] and not u.lupkeywords[10]:
        u.lsecondary = False
        u.nstation = 1
        E.w(mu, f2, pid(E), "W37", modnam, "SECONDARY STATION WILL NOT BE READ; STAGE 2 PROCESSING NOT REQUESTED")
    for istation in range(1, u.nstation + 1):
        if istation == 1:
            ik1, ik2 = 1, 4
            ik3, ik4 = ik2 + 3, ik2 + 4
        else:
            ik1, ik2 = 10, 42
            ik3, ik4 = ik2 + 2, ik2 + 3
        if u.upstage1[istation] and not u.lupkeywords[ik1]:
            no_extract = False
            if u.lupkeywords[ik1 + 2]:
                f = E.units.get(m.up_extract_unit[istation])
                rec = f.leer() if f else None
                if rec is None:
                    no_extract = True
                else:
                    v, io, _ = lread(rec, [("a", 8)])
                    junk = v[0] if v else ""
                    if (io == 0 and "LOCATION" not in junk) or io != 0:
                        no_extract = True
                if f:
                    f.rewind()
            else:
                no_extract = True
            if (no_extract or (not no_extract and not u.lupkeywords[ik1 + 3])) and not m.lstage[2]:
                E.w(mu, f1, pid(E), "E08", modnam, "MISSING KEYWORD", m.keywrd[ik2].strip())
                m.lbad = True
        elif u.lupkeywords[ik1]:
            u.writeext = [None, True, True]
        if u.upstage1[istation] and not m.lstage[2] and not u.lupkeywords[ik1 + 2]:
            E.w(mu, f1, pid(E), "E08", modnam, "MISSING KEYWORD", m.keywrd[ik3].strip())
            m.lbad = True
        if not u.upstage1[istation] and m.lstage[2] and not u.lupkeywords[ik1 + 3]:
            E.w(mu, f1, pid(E), "E08", modnam, "MISSING KEYWORD", m.keywrd[ik4].strip())
            m.lbad = True
    if u.upstage1[1] or u.upstage1[2]:
        if not u.lupkeywords[5]:
            if m.lstage[2]:
                E.w(mu, f2, pid(E), "W03", modnam, "XDATES KEYWORD MISSING; READ XDATES FROM METPREP XDATES")
            else:
                E.w(mu, f1, pid(E), "E08", modnam, "MISSING KEYWORD", m.keywrd[9].strip())
                m.lbad = True
    for istation in range(1, u.nstation + 1):
        ik1, ik2 = (6, 10) if istation == 1 else (14, 46)
        if u.upstage1[istation] and not u.lupkeywords[ik1]:
            E.w(mu, f1, pid(E), "E08", modnam, "MISSING KEYWORD", m.keywrd[ik2].strip())
            m.lbad = True
    if u.upstage1[2] and u.lsecondary and not u.lupkeywords[17] and u.lupkeywords[9]:
        for v in u.upvars[1:]:
            v.laudit[2] = v.laudit[1]


def up_stage2(E, istation):
    m, u = E.m, E.up
    f = E.units.get(m.up_qaout_unit[istation])
    m.lbad = False
    iline = 0
    if f is None:
        return
    while not m.lbad and iline <= 3:
        raw = f.leer()
        if raw is None:
            break
        iline += 1
        L = raw[:m.linelen].upper()
        m.inpline1 = L
        m.ilen = len(L.rstrip(" "))
        if "LOCATION" in L:
            n = 0
            for i in range(1, m.ilen + 1):
                if ch(L, i + 1) == " " and ch(L, i) != " ":
                    n += 1
            m.nfield = n
            i = L.find("LOCATION") + 1
            r = getloc(E, i + 8, u.lgmt2lst[istation], u.lelev[istation])
            u.upid[istation] = r["stid"]
            u.uplat[istation], u.uplon[istation] = r["lat"], r["lon"]
            u.upgmt2lst[istation], u.upelev[istation] = r["gmt2lst"], r["elev"]
            u.lgmt2lst[istation], u.lelev[istation] = r["lgmt2lst"], r["lelev"]
        if "DATES" in L:
            i = L.find("DATES") + 1
            m.nfield = 7
            a, b, dts = getdates(E, i + 5)
            u.upstarts[istation], u.upends[istation] = a, b
            u.updates1[istation] = [list(r) for r in dts]
            u.updates = [[0] * 4 for _ in range(3)]
        if "RANGE" in L:
            i = L.find("RANGE") + 1
            m.nfield = 6
            up_range(E, i + 5, istation)
    f.rewind()


# ------------------------------------------------------------------------------------------
def up_proc(E, ahora=None):
    m, u, p = E.m, E.up, E.pb
    modnam = fx("UP_PROC", 10)
    f1 = fmt_msg(E, "2(a,1x),a8,1x,i2.2,2(a,i2.2))")
    f2 = fmt_msg(E, "a,1x,i5)")
    f3 = fmt_msg(E, "a,1x,i8,1x,a,1x,i8,2(1x,a),a)")
    f4 = fmt_msg(E, "i8.8,3(1x,a,))")
    extract_msgs = [None, "NUMBER OF EXTRACTED SOUNDINGS:", "NUMBER OF UNIQUE VALID SOUNDINGS:",
                    "NUMBER OF DUPLICATE SOUNDINGS:", "NUMBER OF SKIPPED SOUNDINGS:"]
    mu = m.msg_unit
    m.lbad = False
    if u.lsecondary and m.lstage[2] and not m.use_second:
        u.lsecondary = False
        E.w(mu, f2, pid(E), "W37", modnam, "SECONDARY STATION WILL NOT BE PROCESSED; NO SECONDARY SUBSTITUTION REQUESTED")
        E.cerrar(m.up_qaout_unit[2])
        E.cerrar(m.up_extract_unit[2])
    u.nupdays = numdays(u.upstart, u.upend)
    nd = u.nupdays
    u.sound_info = [None] + [[None] + [SdInfo() for _ in range(u.nstation)] for _ in range(nd)]
    u.snd_date = [0] * (nd + 1)
    iday1 = 0
    for y in range(u.updates[1][1], u.updates[2][1] + 1):
        leap = leapyr(y)
        imon1 = u.updates[1][2] if y == u.updates[1][1] else 1
        imon2 = u.updates[2][2] if y == u.updates[2][1] else 12
        for mm in range(imon1, imon2 + 1):
            idy1 = 1
            idy2 = m.days[mm] + (1 if (mm == 2 and leap) else 0)
            if mm == imon1 and y == u.updates[1][1]:
                idy1 = u.updates[1][3]
            if mm == imon2 and y == u.updates[2][1]:
                idy2 = u.updates[2][3]
            for dd in range(idy1, idy2 + 1):
                iday1 += 1
                u.snd_date[iday1] = y * 10000 + mm * 100 + dd
                for st in range(1, u.nstation + 1):
                    u.sound_info[iday1][st].snddate = u.snd_date[iday1]
    u.updata = SondeosEst()
    for istation in range(1, u.nstation + 1):
        nup_calc_audit = 0
        for ivar in range(1, u.nupvars + 1):
            if u.upvars[ivar].laudit[istation]:
                u.nup_audit_vars[istation] += 1
                if ivar > u.nupvars_keep:
                    nup_calc_audit += 1
        if istation == 1:
            lqaout, laudit = u.lupkeywords[4], u.lupkeywords[9]
        else:
            lqaout, laudit = u.lupkeywords[13], u.lupkeywords[17]
        u.nupvars1 = u.nupvars_keep + nup_calc_audit
        defecto = [None] * (u.nupvars1 + 1)
        u.qaout_vars = None
        if lqaout or (laudit and m.istage == 1 and u.upstage1[istation]):
            u.qaout_vars = [""] * (u.nupvars1 + 1)
        ivar1 = 0
        for ivar in range(1, u.nupvars + 1):
            uv = u.upvars[ivar]
            if ivar <= u.nupvars_keep:
                defecto[ivar] = float(uv.missval[istation]) * uv.conv[istation]
                if u.qaout_vars is not None:
                    u.qaout_vars[ivar] = uv.varname
            else:
                if uv.laudit[istation]:
                    ivar1 += 1
                    defecto[ivar1 + u.nupvars_keep] = float(uv.missval[istation]) * uv.conv[istation]
                    if u.qaout_vars is not None:
                        u.qaout_vars[ivar1 + u.nupvars_keep] = uv.varname
        u.updata1 = Sondeos(u.nupvars1, defecto, u.maxlevels)
        u.snd_hrs = [[-9] * 25 for _ in range(nd + 1)]
        u.s_levels = [[1] * 25 for _ in range(nd + 1)]
        u.nsnding1 = [0] * (nd + 1)
        u.lsound = [False] * (nd + 1)
        t = ahora or _dt.datetime.now()
        E.w(mu, f1, pid(E), "I20", modnam, u.station_type[istation].strip(), "UPPER AIR EXTRACTION BEGIN",
            t.strftime("%Y%m%d"), t.hour, ":", t.minute, ":", t.second)
        if u.upstage1[istation]:
            iform = u.iupform[istation]
            if iform == 1 or iform == 2:
                raise NoTraducido("formato de radiosondeo TD-6201 (sólo EE. UU.)")
            elif iform == 3:
                read_fsl(E, istation)
            elif iform == 4:
                read_igra(E, istation)
            else:
                read_ext(E, istation)
        else:
            read_ext(E, istation)
        for jj in range(23, 27):
            extract_code = "I%2d" % jj
            if jj == 23:
                icount = u.nsnd[2][istation]
            elif jj == 24:
                if m.istage == 1 and u.upstage1[istation]:
                    icount = u.nsnd[4][istation] - u.nsnd[5][istation]
                else:
                    icount = u.nsnd[2][istation]
            else:
                icount = u.nsnd[5][istation]
            E.w(mu, f2, pid(E), extract_code, modnam, extract_msgs[jj - 22], icount)
        t = ahora or _dt.datetime.now()
        E.w(mu, f1, pid(E), "I20", modnam, u.station_type[istation].strip(), "UPPER AIR EXTRACTION END",
            t.strftime("%Y%m%d"), t.hour, ":", t.minute, ":", t.second)
        if not u.lbadup:
            if ((m.istage == 1 and u.upstage1[istation] and (u.nsnd[4][istation] - u.nsnd[5][istation]) == 0) or
                    (m.istage == 2 and u.nsnd[2][istation] == 0)):
                E.w(mu, f3, pid(E), "W34", modnam, "NO EXTRACTED DATA BETWEEN", u.upstart, "-", u.upend, "FOR",
                    u.station_type[istation].strip(), "; CHECK XDATES")
                u.have_soundings[istation] = False
            else:
                u.have_soundings[istation] = True
                for d in range(1, nd + 1):
                    si = u.sound_info[d][istation]
                    if u.nsnding1[d] > 0:
                        si.nsnding = u.nsnding1[d]
                    else:
                        si.nsnding = 1
                        u.no_sound_days[istation] += 1
                        if u.upstarts[istation] <= si.snddate <= u.upends[istation]:
                            E.w(mu, f4, pid(E), "I28", modnam, u.snd_date[d], "NO SOUNDINGS FOR THE DAY FOR",
                                u.station_type[istation].strip(), "STATION")
                    si.sounding = u.lsound[d]
                    si.snd_hr = [None] * (si.nsnding + 1)
                    si.nlevels = [None] * (si.nsnding + 1)
                    if u.nsnding1[d] > 0:
                        for h in range(1, u.nsnding1[d] + 1):
                            if min(u.snd_hrs[d][1:]) > 11:
                                u.no_am_days[istation] += 1
                                E.w(mu, f4, pid(E), "I29", modnam, u.snd_date[d], "NO AM SOUNDINGS FOR THE DAY FOR",
                                    u.station_type[istation].strip(), "STATION")
                            si.snd_hr[h] = u.snd_hrs[d][h]
                            si.nlevels[h] = u.s_levels[d][h]
                    else:
                        si.snd_hr[1] = u.snd_hrs[d][1]
                        si.nlevels[1] = u.s_levels[d][1]
                if m.istage == 1 and u.upstage1[istation]:
                    if u.lupkeywords[3] and u.writeext[istation]:
                        header(E, m.up_extract_unit[istation], istation, 1)
                        data_form = fwrite("(a,i2,a)", "(i8.8,3x,i3,3x,i2.2,1x,i3,", u.nupvars_keep, "(1x,f8.1))")[0]
                        L = []
                        for d in range(1, nd + 1):
                            si = u.sound_info[d][istation]
                            if not si.sounding:
                                continue
                            for h in range(1, si.nsnding + 1):
                                U = u.updata1.get(d, h)
                                for lv in range(1, si.nlevels[h] + 1):
                                    L.extend(fwrite(data_form, si.snddate, h, si.snd_hr[h], lv,
                                                    *[U[iv][lv] for iv in range(1, u.nupvars_keep + 1)]))
                        E.units[m.up_extract_unit[istation]].escribir(L)
                    if (u.lupkeywords[7] and istation == 1) or (u.lupkeywords[15] and istation == 2):
                        up_modify(E, istation)
                    ik1, ik2 = (9, 4) if istation == 1 else (17, 13)
                    if u.lupkeywords[ik1] or (u.lupkeywords[ik2] and u.upstage1[istation]):
                        up_audit(E, istation)
                for d in range(1, nd + 1):
                    for h in range(1, u.nsound[istation] + 1):
                        U = u.updata1.get(d, h)
                        nl = u.nuplevels[istation]
                        V = [None] + [U[iv][:] for iv in range(1, u.nupvars_keep + 1)]
                        for iv in range(1, u.nupvars_keep + 1):
                            V[iv] = V[iv][:nl + 1] + [0.0] * (u.maxlevels + 2 - (nl + 1))
                        u.updata.d[(istation, d, h)] = V
                if m.istage == 1 and u.upstage1[istation]:
                    ik1 = 4 if istation == 1 else 13
                    if u.lupkeywords[ik1] and u.upstage1[istation]:
                        header(E, m.up_qaout_unit[istation], istation, 2)
                        data_form = fwrite("(a,i2,a)", "(i8.8,3x,i3,3x,i2.2,1x,i3,", u.nupvars1, "(1x,f8.1))")[0]
                        L = []
                        for d in range(1, nd + 1):
                            si = u.sound_info[d][istation]
                            if not si.sounding:
                                continue
                            for h in range(1, si.nsnding + 1):
                                U = u.updata1.get(d, h)
                                for lv in range(1, si.nlevels[h] + 1):
                                    L.extend(fwrite(data_form, si.snddate, h, si.snd_hr[h], lv,
                                                    *[U[iv][lv] for iv in range(1, u.nupvars1 + 1)]))
                        E.units[m.up_qaout_unit[istation]].escribir(L)
        u.updata1 = None
        u.qaout_vars_hdr = u.qaout_vars
        u.qaout_vars = None


def header(E, iunit, istation, itype):
    m, u = E.m, E.up
    outtype = [None, "EXTRACT", "QAOUT"]
    cgmt2lst = fwrite("(i3)", u.upgmt2lst[istation])[0] if u.lgmt2lst[istation] else ""
    celev = fwrite("(f9.3)", u.upelev[istation])[0] if u.lelev[istation] else ""
    if u.uplat[istation] < 0.0:
        alat = fwrite("(f7.3,a1)", abs(u.uplat[istation]), "S")[0]
    else:
        alat = fwrite("(f7.3,a1)", u.uplat[istation], "N")[0]
    if u.uplon[istation] < 0.0:
        alon = fwrite("(f8.3,a1)", abs(u.uplon[istation]), "W")[0]
    else:
        alon = fwrite("(f8.3,a1)", u.uplon[istation], "E")[0]
    L = fwrite("(a,a5/a,a8,2(1x,a10),2(1x,a)/2(a)/a,i4,2(1x,i2.2),1x,i4,2(1x,i2.2))", "AERMET ", m.versn,
               "LOCATION ", fx(u.upid[istation], 8), fx(alat, 10), fx(alon, 10), cgmt2lst.strip(), celev.strip(),
               "FILE TYPE: ", outtype[itype].strip(), "DATES ", u.updates[1][1], u.updates[1][2], u.updates[1][3],
               u.updates[2][1], u.updates[2][2], u.updates[2][3])
    for ivar in range(1, u.nupvars + 1):
        v = u.upvars[ivar]
        if v.lmod[istation]:
            bndstr = "<=" if v.lincbound[istation] else "< "
            L += fwrite("(a5,1x,a4,i6,1x,a2,1x,2(1x,i6))", "RANGE", v.varname, v.lowbound[istation], bndstr,
                        v.upbound[istation], v.missval[istation])
    if itype == 1:
        hf = fwrite("(a,i2,a)", "(a,4x,a4,", u.nupvars_keep - 1, "(5x,a4))")[0]
        L += fwrite(hf, "DATE       SND   HR  LEV", *[u.upvars[iv].varname.strip() for iv in range(1, u.nupvars_keep + 1)])
    else:
        hf = fwrite("(a,i2,a)", "(a,4x,a4,", u.nupvars1 - 1, "(5x,a4))")[0]
        L += fwrite(hf, "DATE       SND   HR  LEV", *[u.qaout_vars[iv].strip() for iv in range(1, u.nupvars1 + 1)])
    E.units[iunit].escribir(L)


def new_sound(E, sdate, ihr, istation):
    """NEW_SOUND. Devuelve iday1."""
    m, u = E.m, E.up
    modnam = fx("NEW_SOUND", 10)
    f1 = "(1x,a,1x,i1,a,1x,2(a2,a1),a4,1x,a)"
    f2 = fmt_msg(E, "a,1x,a20)")
    f3 = fmt_msg(E, "a,1x,i8,1x,a,1x,i8)")
    adate = "%08d" % sdate
    date_hr_str = fwrite("(a5,1x,i8,1x,a2,1x,i2.2)", "DATE:", sdate, "HR", ihr)[0]
    sv = E.up.__dict__.setdefault("_new_sound_save", {"station": 0, "date": 0})
    if sv["station"] != istation:
        sv["station"] = istation
        sv["date"] = 0
    if sdate < sv["date"]:
        E.w(m.msg_unit, f3, pid(E), "W35", modnam, "CURRENT DATE", sdate, "IS PRIOR TO PREVIOUS DATE IN SOUNDING",
            sv["date"])
    u.nsnd[2][istation] += 1
    iday1 = numdays(u.upstart, sdate)
    i = 1
    lfound = False
    while i <= 24 and not lfound:
        if u.snd_hrs[iday1][i] == ihr:
            lfound = True
            E.w(m.msg_unit, f2, pid(E), "I21", modnam, "DUPLICATE SOUNDING FOR", date_hr_str)
            u.nsnd[5][istation] += 1
        else:
            i += 1
    if not lfound:
        if not u.lsound[iday1]:
            if not m.noprint:
                E.w(OUTPUT_UNIT, f1, "Stage", m.istage, ": Extracting upper air data for month/day/year",
                    adate[4:6], "/", adate[6:8], "/", adate[0:4], "LST")
            u.lsound[iday1] = True
        u.nsnding1[iday1] += 1
        u.nsnd[3][istation] = u.nsnding1[iday1]
        if u.nupdays == 1:
            u.nsound[istation] = u.nsnd[3][istation]
        if u.nsound[istation] < u.nsnding1[iday1]:
            u.nsound[istation] = u.nsnding1[iday1]
        u.snd_hrs[iday1][u.nsnding1[iday1]] = ihr
        u.s_levels[iday1][u.nsnding1[iday1]] = 0
        u.writelevs = 0
        u.ltop = False
        u.lskip = False
        u.savepress = 0
    sv["date"] = sdate
    return iday1


def _final_extraccion(E, istation, lbad):
    m, u = E.m, E.up
    modnam = fx("READ_FSL", 10) if u.iupform[istation] == 3 else fx("READ_IGRA", 10)
    ef = u.ext_form
    if not u.lbadup and lbad:
        u.lbadup = True
    if not u.lbadup:
        E.w(m.msg_unit, ef[13], pid(E), "I22", modnam, EXT_ENDSTR[1])
    elif u.nsnd[2][istation] == 0 and not u.lbadup:
        E.w(m.msg_unit, ef[13], pid(E), "E37", modnam, EXT_ENDSTR[2])
    elif u.lbadup and u.nsnd[1][istation] > 0:
        E.w(m.msg_unit, ef[14], pid(E), "E38", modnam, EXT_ENDSTR[4], u.nsnd[1][istation])
    elif u.lbadup and u.nsnd[1][istation] == 0:
        E.w(m.msg_unit, ef[13], pid(E), "E39", modnam, EXT_ENDSTR[3])
    for iday1 in range(1, u.nupdays + 1):
        if u.lsound[iday1] and u.nsnding1[iday1] == 0:
            u.lsound[iday1] = False
            u.nsnding1[iday1] = 1


def _anular(u, iday1, istation):
    k = u.nsnd[3][istation]
    u.snd_hrs[iday1][k] = -9
    u.s_levels[iday1][k] = 0
    u.nsnding1[iday1] -= 1


def read_fsl(E, istation):
    m, u = E.m, E.up
    modnam = fx("READ_FSL", 10)
    ef = u.ext_form
    mu = m.msg_unit
    months = [None, "JAN", "FEB", "MAR", "APR", "MAY", "JUN", "JUL", "AUG", "SEP", "OCT", "NOV", "DEC"]
    pres_conv = [None, 1.0, 0.1]
    f = E.units[m.up_data_unit[istation]]
    sdate = 0
    iupvars = [None, 0, 0, 0, 0, 0, 0]
    readlevs = [None, 0, 0]
    linetype1 = 0
    eof = 0
    iflag1 = 0
    iflag = 0
    v = 0
    lgo = lgo1 = False
    lversion = [None, False, False]
    lsurface = False
    missval = [None, 32767, 99999]
    rupvars = [None, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0]
    iday1 = 0
    nlevs = 0
    iwarn = 0
    iline = 0
    u.writelevs = 0
    rbase = 0.0
    ikeepbase = 999999
    linetype = 0
    ibase = 0
    set_conv = False
    unit_conv = [None, 0.1, 1.0, 0.1, 0.1, 1.0, 0.1]
    date_hr_str = " " * 20
    lbad = False
    rec = f.leer()
    if rec is None:
        eof = -1
        datline = ""
    else:
        datline = rec[:60]
    vv, iflag, _ = lread(datline, ["i"])
    linetype = vv[0] if vv else linetype
    if linetype != 254:
        E.w(mu, ef[1], pid(E), "E30", modnam, "SOUNDING IS NOT FSL FORMAT LINE:", datline.strip())
        lbad = True
    if not lbad:
        f.rewind()
        eof = 0
    m.lbad = lbad
    while eof == 0 and sdate <= u.upend and iflag == 0 and iflag1 == 0 and not m.lbad:
        rec = f.leer()
        if rec is None:
            eof = -1
            datline = datline
        else:
            datline = rec[:60]
            iline += 1
        vv, iflag, _ = lread(datline, ["i"])
        if vv:
            linetype = vv[0]
        if iflag == 0 and eof == 0:
            if linetype == 254:
                if readlevs[1] < nlevs - 4:
                    E.w(mu, ef[9], pid(E), "E36", modnam, "NUMBER OF LEVELS", readlevs[1],
                        "IS LESS THAN NUMBER OF EXPECTED LEVELS", nlevs - 4, date_hr_str)
                    m.lbad = True
                lsurface = False
                readlevs = [None, 0, 0]
                if (iline > 1 and linetype1 < 4) or linetype1 > 9:
                    E.w(mu, ef[2], pid(E), "E31", modnam, "INVALID ORDER SOUNDING LINE TYPE", linetype,
                        "FOLLOWS LINE TYPE", linetype1, "LINE NUMBER", iline)
                    m.lbad = True
                else:
                    if eof == 0 and not m.lbad:
                        u.nsnd[1][istation] += 1
                    vv, iflag1, _ = lread(datline, [("a", 6), "i", "i", ("a", 3), "i"])
                    if iflag1 == 0:
                        ihr, iday, inmonth, iyear = vv[1], vv[2], vv[3], vv[4]
                        imonth = 1
                        lmonth = False
                        while imonth <= 12 and not lmonth:
                            if inmonth.strip() == months[imonth]:
                                lmonth = True
                            else:
                                imonth += 1
                        if lmonth:
                            ihr, iday, imonth, iyear, sdate, lgo = data_dates(
                                E, ihr, iday, imonth, iyear, u.upgmt2lst[istation], u.upstarts[istation],
                                u.upends[istation], 32)
                            date_hr_str = fwrite("(a5,1x,i8,1x,a2,1x,i2.2)", "DATE:", sdate, "HR", ihr)[0]
                            if lgo:
                                iday1 = new_sound(E, sdate, ihr, istation)
                        else:
                            E.w(mu, ef[3], pid(E), "E31", modnam, EXT_ERRSTR[2], u.nsnd[1][istation], "; LINE",
                                datline.strip())
                            m.lbad = True
                    else:
                        E.w(mu, ef[3], pid(E), "E31", modnam, EXT_ERRSTR[1], u.nsnd[1][istation], "; LINE",
                            datline.strip())
                        m.lbad = True
                linetype1 = linetype
            elif linetype == 1:
                if linetype1 != 254:
                    E.w(mu, ef[2], pid(E), "E31", modnam, "INVALID ORDER SOUNDING LINE TYPE", linetype,
                        "FOLLOWS LINE TYPE", linetype1, "LINE NUMBER", iline)
                    m.lbad = True
                else:
                    vv, iflag1, _ = lread(datline, [("a", 6), ("a", 8)])
                    if iflag1 == 0:
                        u.iupid = vv[1].strip()
                        if u.iupid != u.upid[istation].strip() and lgo:
                            iwarn += 1
                            if iwarn <= u.nwarnlim:
                                E.w(mu, ef[4], pid(E), "W30", modnam, "STATION ID FROM FILE", u.iupid,
                                    "DOES NOT MATCH USER ENTERED STATION ID", u.upid[istation].strip(),
                                    "FOR SOUNDING NUMBER", u.nsnd[1][istation], date_hr_str)
                            if iwarn == u.nwarnlim:
                                E.w(mu, ef[5], pid(E), "W33", modnam, "REACH LIMIT OF", u.nwarnlim, "W30",
                                    "WARNING MESSAGES")
                    else:
                        E.w(mu, ef[3], pid(E), "E31", modnam, EXT_ERRSTR[3], u.nsnd[1][istation], "; LINE",
                            datline.strip())
                        m.lbad = True
                linetype1 = linetype
            elif linetype == 2:
                if linetype1 != linetype - 1:
                    E.w(mu, ef[2], pid(E), "E31", modnam, "INVALID ORDER SOUNDING LINE TYPE", linetype,
                        "FOLLOWS LINE TYPE", linetype1, "LINE NUMBER", iline)
                    m.lbad = True
                else:
                    vv, iflag1, _ = lread(datline, [("a", 6)] * 4 + ["i"])
                    if iflag1 == 0:
                        nlevs = vv[4]
                        readlevs = [None, 0, 0]
                        if lgo:
                            v, set_conv, lgo1 = fsl_versn(E, datline, u.nsnd[1][istation], linetype,
                                                          u.upvars[1].missval[istation], v, set_conv)
                            if v > 0:
                                lversion[v] = True
                            if lversion[1] and lversion[2]:
                                E.w(mu, ef[8], pid(E), "E35", modnam, "FSL VERSION 1 AND 2 BOTH DETECTED FOR SOUNDING #",
                                    u.nsnd[1][istation], date_hr_str)
                                m.lbad = True
                    else:
                        E.w(mu, ef[3], pid(E), "E31", modnam, EXT_ERRSTR[5], u.nsnd[1][istation], "; LINE",
                            datline.strip())
                        m.lbad = True
                linetype1 = linetype
            elif linetype == 3:
                if linetype1 != linetype - 1:
                    E.w(mu, ef[2], pid(E), "E31", modnam, "INVALID ORDER SOUNDING LINE TYPE", linetype,
                        "FOLLOWS LINE TYPE", linetype1, "LINE NUMBER", iline)
                    m.lbad = True
                else:
                    wind_units = fx(datline, 60)[47:49]
                    if lgo:
                        v, set_conv, lgo1 = fsl_versn(E, datline, u.nsnd[1][istation], linetype,
                                                      u.upvars[1].missval[istation], v, set_conv)
                        if v > 0:
                            lversion[v] = True
                        if lversion[1] and lversion[2]:
                            E.w(mu, ef[8], pid(E), "E35", modnam, "FSL VERSION 1 AND 2 BOTH DETECTED FOR SOUNDING #",
                                u.nsnd[1][istation], date_hr_str)
                            m.lbad = True
                        if wind_units.strip() == "kt":
                            unit_conv[6] = 0.51
                        elif wind_units.strip() == "ms":
                            unit_conv[6] = 0.1
                        else:
                            E.w(mu, ef[6], pid(E), "E33", modnam, "INVALID WIND SPEED UNITS:", wind_units.strip(),
                                "FOR SOUNDING #", u.nsnd[1][istation])
                            m.lbad = True
                linetype1 = linetype
            elif linetype >= 4:
                if ((linetype == 9 and linetype1 != 3) or
                        (linetype != 9 and lsurface and (linetype1 <= 3 or linetype1 == 254))):
                    E.w(mu, ef[2], pid(E), "E31", modnam, "INVALID ORDER SOUNDING LINE TYPE", linetype,
                        "FOLLOWS LINE TYPE", linetype1, "LINE NUMBER", iline)
                    m.lbad = True
                if linetype == 9:
                    if lsurface:
                        E.w(mu, ef[12], pid(E), "E34", modnam, "MULTIPLE SURFACE DATA LINES FOR SOUNDING #",
                            u.nsnd[1][istation], date_hr_str)
                        m.lbad = True
                    else:
                        lsurface = True
                if not m.lbad:
                    vv, iflag1, _ = lread(datline, [("a", 6)] + ["i"] * 6)
                    for k in range(1, len(vv)):
                        if vv[k] is not None:
                            iupvars[k] = vv[k]
                    readlevs[1] += 1
                    if readlevs[1] > nlevs - 4:
                        E.w(mu, ef[9], pid(E), "E36", modnam, "NUMBER OF LEVELS", readlevs[1],
                            "EXCEEDS NUMBER OF EXPECTED LEVELS", nlevs - 4, date_hr_str)
                        m.lbad = True
                    if lgo:
                        if iflag1 == 0 and readlevs[1] <= u.maxlevels and not u.ltop:
                            v, set_conv, lgo1 = fsl_versn(E, datline, u.nsnd[1][istation], linetype, iupvars[1], v,
                                                          set_conv)
                            if v > 0:
                                lversion[v] = True
                            if lversion[1] and lversion[2]:
                                E.w(mu, ef[8], pid(E), "E35", modnam, "FSL VERSION 1 AND 2 BOTH DETECTED FOR SOUNDING #",
                                    u.nsnd[1][istation], date_hr_str)
                                lgo1 = False
                            if lgo1:
                                unit_conv[1] = pres_conv[v]
                                readlevs[2] += 1
                                if readlevs[1] == 1 and linetype != 9:
                                    u.lskip = True
                                    E.w(mu, ef[9], pid(E), "W31", modnam, "SKIP SOUNDING; 1ST LEVEL TYPE", linetype,
                                        "NOT TYPE 9, FOR SOUNDING #", u.nsnd[1][istation], date_hr_str)
                                    u.nsnd[6][istation] += 1
                                    _anular(u, iday1, istation)
                                    if u.nsnd[3][istation] > 1:
                                        u.nsnd[3][istation] -= 1
                                elif readlevs[1] == 1:
                                    if iupvars[2] == missval[v]:
                                        iupvars[2] = calc_base(E, istation, u.nsnd[1][istation], date_hr_str, ikeepbase,
                                                               iupvars[1], unit_conv[1], missval[1], iupvars[2],
                                                               unit_conv[2])
                                    else:
                                        ikeepbase = iupvars[2]
                                    if iupvars[2] != missval[v]:
                                        ibase = iupvars[2]
                                        rbase = float(iupvars[2])
                                    else:
                                        ibase = 0
                                        rbase = 0.0
                                        u.lskip = True
                                        u.nsnd[6][istation] += 1
                                        E.w(mu, ef[10], pid(E), "W32", modnam,
                                            "SKIP SOUNDING; SURFACE LEVEL HEIGHT MISSING FOR SOUNDING #",
                                            u.nsnd[1][istation], date_hr_str)
                                        _anular(u, iday1, istation)
                                lmissvals = [None] + [False] * 6
                                for ivar in range(1, 7):
                                    if iupvars[ivar] == missval[v]:
                                        lmissvals[ivar] = True
                                        rupvars[ivar] = float(u.upvars[ivar].missval[istation])
                                    else:
                                        rupvars[ivar] = float(iupvars[ivar]) * unit_conv[ivar]
                                        if ivar == 2:
                                            rupvars[ivar] = rupvars[ivar] - rbase
                                if (not lmissvals[3] and not lmissvals[1] and iupvars[1] != u.savepress and
                                        not lmissvals[2] and not u.lskip and linetype != 6):
                                    u.writelevs += 1
                                    u.s_levels[iday1][u.nsnd[3][istation]] = u.writelevs
                                    if u.writelevs > u.nuplevels[istation]:
                                        u.nuplevels[istation] = u.writelevs
                                    u.savepress = iupvars[1]
                                    if iupvars[2] > u.uptop + ibase:
                                        u.ltop = True
                                    U = u.updata1.get(iday1, u.nsnd[3][istation])
                                    for ivar in range(1, 7):
                                        U[ivar][u.writelevs] = rupvars[ivar]
                            else:
                                m.lbad = True
                        elif iflag1 != 0:
                            E.w(mu, ef[11], pid(E), "E31", modnam, "ERROR READING UPPER AIR DATA SOUNDING #",
                                u.nsnd[1][istation], "; LINE", datline.strip(), date_hr_str)
                            m.lbad = True
                linetype1 = linetype
            else:
                E.w(mu, ef[7], pid(E), "E31", modnam, "INVALID LINE TYPE", linetype, "FOR SOUNDING #",
                    u.nsnd[1][istation], "LINE", datline.strip())
                linetype1 = linetype
                m.lbad = True
        else:
            if eof == 0:
                E.w(mu, ef[3], pid(E), "E31", modnam, EXT_ERRSTR[4], u.nsnd[1][istation], "; LINE",
                    datline.strip())
                m.lbad = True
        if m.lbad:
            if iday1 > 0:
                _anular(u, iday1, istation)
        if not u.lskip and linetype == 9 and lgo:
            u.nsnd[4][istation] += 1
    _final_extraccion(E, istation, m.lbad)


def fsl_versn(E, datline, nsnding, linetype, pressure, fsl_version, set_conv):
    """FSL_VERSN. Devuelve (fsl_version, set_conv, lgood); fsl_version conserva el valor previo
    en las ramas que no lo asignan (argumento intent(out) sin definir, como el original)."""
    m = E.m
    modnam = fx("FSL_VERSN", 10)
    f1 = fmt_msg(E, "a,1x,i5,2(1x,a))")
    f2 = fmt_msg(E, "a)")
    lgood = True
    dl = fx(datline, 60)
    nv1 = dl.find(" 32767 ") + 1
    nv2 = dl.find(" 99999 ") + 1
    if nv1 > 0 and nv2 > 0:
        E.w(m.msg_unit, f1, pid(E), "E35", modnam, "MULTIPLE MISSING VALUE INDICATORS FOR SOUNDING #", nsnding,
            "; LINE", datline.strip())
        lgood = False
    elif nv1 > 0:
        fsl_version = 1
        set_conv = True
    elif nv2 > 0:
        fsl_version = 2
        set_conv = True
    elif linetype == 9 and 6500 <= pressure <= 11000:
        fsl_version = 2
        set_conv = True
    elif linetype == 9 and 650 <= pressure <= 1100:
        fsl_version = 1
        set_conv = True
    elif not set_conv and linetype > 3:
        E.w(m.msg_unit, f2, pid(E), "E35", modnam, "CANNOT DETERMINE PRESSURE CONVERSION FACTOR")
        lgood = False
        fsl_version = 0
    return fsl_version, set_conv, lgood


def read_igra(E, istation):
    m, u = E.m, E.up
    modnam = fx("READ_IGRA", 10)
    ef = u.ext_form
    mu = m.msg_unit
    f = E.units[m.up_data_unit[istation]]
    ikeepbase = 999999
    sdate = 0
    iupvars = [None, 0, 0, 0, 0, 0, 0]
    readlevs = [None, 0, 0]
    linetype1 = 0
    eof = 0
    iday1 = 0
    iflag1 = iflag = 0
    iwarn = 0
    rbase = 0.0
    lgo = False
    lsurface = False
    missval = [None, -9999, -8888]
    rupvars = [None, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0]
    nlevs = 0
    iline = 0
    u.writelevs = 0
    linetype = 0
    ibase = 0
    unit_conv = [None, 0.01, 1.0, 0.1, 0.1, 1.0, 0.1]
    date_hr_str = " " * 20
    m.lbad = False
    rec = f.leer()
    datline = rec[:75] if rec is not None else ""
    if datline[0:1] != "#":
        E.w(mu, ef[1], pid(E), "E30", modnam, "SOUNDING IS NOT IGRA FORMAT LINE:", datline.strip())
        m.lbad = True
    if not m.lbad:
        f.rewind()
    while eof == 0 and sdate <= u.upend and iflag == 0 and iflag1 == 0 and not m.lbad:
        rec = f.leer()
        if rec is None:
            eof = -1
        else:
            datline = rec[:75]
            iline += 1
        if datline[0:1] == "#":
            linetype = 1
            iflag = 0
        else:
            vv, iflag, _ = lread(fx(datline, 75)[0:2], ["i"])
            if vv:
                linetype = vv[0]
            if linetype == 1:
                linetype = 30
        if iflag == 0 and eof == 0:
            if linetype == 1:
                if readlevs[1] < nlevs and iline > 1:
                    E.w(mu, ef[9], pid(E), "E36", modnam, "NUMBER OF LEVELS", readlevs[1],
                        "IS LESS THAN NUMBER OF EXPECTED LEVELS", nlevs, date_hr_str)
                    m.lbad = True
                readlevs = [None, 0, 0]
                lsurface = False
                u.savepress = 0
                if iline > 1 and linetype1 < 10:
                    E.w(mu, ef[2], pid(E), "E31", modnam, "INVALID ORDER SOUNDING LINE TYPE", linetype,
                        "FOLLOWS LINE TYPE", linetype1, "LINE NUMBER", iline)
                    m.lbad = True
                else:
                    if eof == 0 and not m.lbad:
                        u.nsnd[1][istation] += 1
                    vv, iflag1, _ = lread(datline, [("a", 12), "i", "i", "i", "i", "i", "i"])
                    if iflag1 == 0:
                        j1, iyear, imonth, iday, ihr, rtime, nlevs = vv
                        if ihr == 99 and rtime != 9999:
                            ihr = rtime // 100
                        if ihr == 99:
                            lgo = False
                        else:
                            ihr, iday, imonth, iyear, sdate, lgo = data_dates(
                                E, ihr, iday, imonth, iyear, u.upgmt2lst[istation], u.upstarts[istation],
                                u.upends[istation], 32)
                            date_hr_str = fwrite("(a5,1x,i8,1x,a2,1x,i2.2)", "DATE:", sdate, "HR", ihr)[0]
                        if lgo:
                            iday1 = new_sound(E, sdate, ihr, istation)
                            k = 1
                            k1 = 0
                            jt = j1.rstrip()
                            while k <= len(jt) and k1 == 0:
                                if "0" <= jt[k - 1] <= "9":
                                    k1 = k
                                else:
                                    k += 1
                            vv2, iflag2, _ = lread(jt[k1 - 1:] if k1 > 0 else jt, [("a", 8)])
                            if iflag2 == 0:
                                u.iupid = vv2[0].strip()
                                if u.iupid != u.upid[istation].strip():
                                    iwarn += 1
                                    if iwarn <= u.nwarnlim:
                                        E.w(mu, ef[4], pid(E), "W30", modnam, "STATION ID FROM FILE", u.iupid,
                                            "DOES NOT MATCH USER ENTERED STATION ID", u.upid[istation].strip(),
                                            "FOR SOUNDING NUMBER", u.nsnd[1][istation], date_hr_str)
                                    if iwarn == u.nwarnlim:
                                        E.w(mu, ef[5], pid(E), "W33", modnam, "REACH LIMIT OF", u.nwarnlim, "W30",
                                            "WARNING MESSAGES")
                            else:
                                E.w(mu, ef[3], pid(E), "E31", modnam, EXT_ERRSTR[3], u.nsnd[1][istation], "; LINE",
                                    datline.strip())
                                m.lbad = True
                    else:
                        E.w(mu, ef[3], pid(E), "E31", modnam, EXT_ERRSTR[1], u.nsnd[1][istation], "; LINE",
                            datline.strip())
                        m.lbad = True
                linetype1 = linetype
            elif 10 <= linetype < 40:
                if (((linetype == 21 or linetype == 11) and linetype1 != 1) or
                        ((linetype != 21 and linetype != 11) and lsurface and linetype1 == 1)):
                    E.w(mu, ef[2], pid(E), "E31", modnam, "INVALID ORDER SOUNDING LINE TYPE", linetype,
                        "FOLLOWS LINE TYPE", linetype1, "LINE NUMBER", iline)
                    m.lbad = True
                if linetype == 21 or linetype == 11:
                    if lsurface:
                        E.w(mu, ef[12], pid(E), "E34", modnam, "MULTIPLE SURFACE DATA LINES FOR SOUNDING #",
                            u.nsnd[1][istation], date_hr_str)
                        m.lbad = True
                    else:
                        lsurface = True
                if not m.lbad:
                    dl = datline.replace("B", " ").replace("A", " ")
                    datline = dl
                    vv, iflag1, _ = lread(dl, [("a", 12), "i", "i", "i", "i", "i", "i", "i", "i"])
                    if len(vv) >= 2:
                        pass
                    if len(vv) >= 5:
                        iupvars[1], iupvars[2], iupvars[3] = vv[2], vv[3], vv[4]
                    if len(vv) >= 9:
                        iupvars[4], iupvars[5], iupvars[6] = vv[6], vv[7], vv[8]
                    else:
                        for k in range(len(vv)):
                            pass
                    readlevs[1] += 1
                    if readlevs[1] > nlevs:
                        E.w(mu, ef[9], pid(E), "E36", modnam, "NUMBER OF LEVELS", readlevs[1],
                            "EXCEEDS NUMBER OF EXPECTED LEVELS", nlevs, date_hr_str)
                        m.lbad = True
                    if lgo:
                        if iflag1 == 0 and readlevs[1] <= u.maxlevels and not u.ltop:
                            readlevs[2] += 1
                            if readlevs[1] == 1 and (linetype != 21 and linetype != 11):
                                u.lskip = True
                                u.nsnd[6][istation] += 1
                                E.w(mu, ef[9], pid(E), "W31", modnam, "SKIP SOUNDING; 1 LEVEL TYPE", linetype,
                                    "NOT TYPE 11 or 21, FOR SOUNDING #", u.nsnd[1][istation], date_hr_str)
                                _anular(u, iday1, istation)
                                u.nsnd[3][istation] -= 1
                            elif readlevs[1] == 1:
                                if iupvars[2] != missval[1] and iupvars[2] != missval[2]:
                                    ikeepbase = iupvars[2]
                                else:
                                    iupvars[2] = calc_base(E, istation, u.nsnd[1][istation], date_hr_str, ikeepbase,
                                                           iupvars[1], unit_conv[1], missval[1], iupvars[2],
                                                           unit_conv[2])
                                if iupvars[2] != missval[1] and iupvars[2] != missval[2]:
                                    ibase = iupvars[2]
                                else:
                                    ibase = 0
                                    u.lskip = True
                                    u.nsnd[6][istation] += 1
                                    E.w(mu, ef[10], pid(E), "W32", modnam,
                                        "SKIP SOUNDING; SURFACE LEVEL HEIGHT MISSING FOR SOUNDING #",
                                        u.nsnd[1][istation], date_hr_str)
                                    _anular(u, iday1, istation)
                            lmissvals = [None] + [False] * 6
                            for ivar in range(1, 7):
                                if iupvars[ivar] == missval[1] or iupvars[ivar] == missval[2]:
                                    lmissvals[ivar] = True
                                    rupvars[ivar] = float(u.upvars[ivar].missval[istation])
                                else:
                                    if ivar == 4:
                                        if lmissvals[3]:
                                            lmissvals[ivar] = True
                                            rupvars[ivar] = float(u.upvars[ivar].missval[istation])
                                        else:
                                            rupvars[ivar] = rupvars[3] - float(iupvars[ivar]) * unit_conv[ivar]
                                    else:
                                        rupvars[ivar] = float(iupvars[ivar]) * unit_conv[ivar]
                                    if ivar == 2:
                                        rupvars[ivar] = rupvars[ivar] - rbase
                            if (not lmissvals[3] and not lmissvals[1] and iupvars[1] != u.savepress and
                                    not lmissvals[1] and not lmissvals[2] and not u.lskip and linetype < 30):
                                u.writelevs += 1
                                u.s_levels[iday1][u.nsnd[3][istation]] = u.writelevs
                                if u.writelevs > u.nuplevels[istation]:
                                    u.nuplevels[istation] = u.writelevs
                                u.savepress = iupvars[1]
                                if iupvars[2] > u.uptop + ibase:
                                    u.ltop = True
                                rupvars[2] = float(iupvars[2]) - float(ibase)
                                U = u.updata1.get(iday1, u.nsnd[3][istation])
                                for ivar in range(1, 7):
                                    U[ivar][u.writelevs] = rupvars[ivar]
                        elif iflag1 != 0:
                            E.w(mu, ef[11], pid(E), "E31", modnam, "ERROR READING UPPER AIR DATA SOUNDING #",
                                u.nsnd[1][istation], "; LINE", datline.strip(), date_hr_str)
                            m.lbad = True
                linetype1 = linetype
            else:
                E.w(mu, ef[7], pid(E), "E31", modnam, "INVALID LINE TYPE", linetype, "FOR SOUNDING #",
                    u.nsnd[1][istation], "LINE", datline.strip())
                linetype1 = linetype
                m.lbad = True
        else:
            if eof == 0:
                E.w(mu, ef[3], pid(E), "E31", modnam, EXT_ERRSTR[4], u.nsnd[1][istation], "; LINE",
                    datline.strip())
                m.lbad = True
        if m.lbad:
            _anular(u, iday1, istation)
        if not u.lskip and (linetype == 21 or linetype == 11) and lgo:
            u.nsnd[4][istation] += 1
    _final_extraccion(E, istation, m.lbad)


def read_ext(E, istation):
    m, u = E.m, E.up
    modnam = fx("READ_EXT", 10)
    errstr = [None, "ERROR READING STATION INFORMATION; LINE", "INCORRECT FILE TYPE LINE; LINE",
              "ERROR READING EXTRACTION DATES INFORMATION; LINE", "ERROR READING DATA; LINE"]
    f1 = fmt_msg(E, "a,1x,i3,1x,a)")
    f2 = fmt_msg(E, "3(a,1x),a)")
    f3 = fmt_msg(E, "a)")
    f4 = fmt_msg(E, "a,1x,i2,1x,a,1x,i2)")
    f5 = fmt_msg(E, "a,1x,a)")
    mu = m.msg_unit
    eps = m.eps
    if u.upstage1[istation]:
        ifile = m.up_data_unit[istation] if u.lupkeywords[1] else m.up_extract_unit[istation]
    else:
        ifile = m.up_qaout_unit[istation]
    f = E.units[ifile]
    iline = 0
    u.writelevs = 0
    iday1 = 0
    m.lbad = False
    gmt2lst = 0
    while not m.lbad:
        rec = f.leer()
        if rec is None:
            break
        datline = rec[:100]
        iline += 1
        if iline == 2:
            vv, iflag, _ = lread(datline, [("a", 8)])
            j1 = vv[0] if vv else ""
            if j1.strip() == "LOCATION":
                ifield = 0
                for j in range(9, len(datline.rstrip()) + 1):
                    if ch(datline, j - 1) == " " and ch(datline, j) != " ":
                        ifield += 1
                alat = alon = ""
                if ifield == 3:
                    vv, iflag, _ = lread(datline, [("a", 8), ("a", 8), ("a", 10), ("a", 10)])
                    if len(vv) == 4:
                        _, u.iupid, alat, alon = vv
                elif ifield == 4 or ifield == 5:
                    vv, iflag, _ = lread(datline, [("a", 8), ("a", 8), ("a", 10), ("a", 10), "i"])
                    if len(vv) == 5:
                        _, u.iupid, alat, alon, gmt2lst = vv
                else:
                    m.lbad = True
                    E.w(mu, f1, pid(E), "E31", modnam, "INCORRECT NUMBER OF FIELDS", ifield, "ON LOCATION LINE")
                if not m.lbad:
                    s_ = alat.find("S") + 1
                    n_ = alat.find("N") + 1
                    e_ = alon.find("E") + 1
                    w_ = alon.find("W") + 1
                    iflag1 = -1
                    rlat = rlon = 0.0
                    if s_ > 0:
                        vv, iflag1, _ = lread(alat[:s_ - 1], ["f"])
                        rlat = -vv[0] if vv else 0.0
                    elif n_ > 0:
                        vv, iflag1, _ = lread(alat[:n_ - 1], ["f"])
                        rlat = vv[0] if vv else 0.0
                    if iflag1 == -1:
                        E.w(mu, f5, pid(E), "E31", modnam, "LOCATION: ERROR READING LATITUDE", alat.strip())
                        m.lbad = True
                    iflag2 = -1
                    if w_ > 0:
                        vv, iflag2, _ = lread(alon[:w_ - 1], ["f"])
                        rlon = -vv[0] if vv else 0.0
                    elif e_ > 0:
                        vv, iflag2, _ = lread(alon[:e_ - 1], ["f"])
                        rlon = vv[0] if vv else 0.0
                    if iflag2 == -1:
                        E.w(mu, f5, pid(E), "E31", modnam, "LOCATION: ERROR READING LONGITUDE", alon.strip())
                        m.lbad = True
                    if iflag == 0 and iflag1 == 0 and iflag2 == 0:
                        if u.iupid.strip() != u.upid[istation].strip():
                            E.w(mu, f2, pid(E), "W30", modnam, "STATION ID FROM FILE", u.iupid.strip(),
                                "DOES NOT MATCH USER ENTERED STATION ID", u.upid[istation].strip())
                        if abs(rlat - u.uplat[istation]) > eps or abs(rlon - u.uplon[istation]) > eps:
                            E.w(mu, f3, pid(E), "W30", modnam,
                                "STATION COORDINATES DO NOT MATCH INPUT COORDINATES IN RUNSTREAM FILE")
                        if ifield >= 4 and gmt2lst != u.upgmt2lst[istation] and m.istage == 1:
                            E.w(mu, f4, pid(E), "W30", modnam, "GMT TO LST CONVERSION", gmt2lst,
                                "DOES NOT MATCH INPUT GMT TO LST CONVERSION", u.upgmt2lst[istation])
                    else:
                        E.w(mu, f5, pid(E), "E31", modnam, errstr[1], datline.strip())
                        m.lbad = True
            else:
                E.w(mu, f5, pid(E), "E31", modnam, errstr[1], datline.strip())
                m.lbad = True
        elif iline == 3:
            vv, io, _ = lread(datline, [("a", 8)] * 3)
            j1, j2, j3 = (vv + ["", "", ""])[:3]
            if j1.strip() != "FILE" or j2.strip() != "TYPE:" or (j3.strip() != "EXTRACT" and j3.strip() != "QAOUT"):
                E.w(mu, f5, pid(E), "E31", modnam, errstr[2], datline.strip())
                m.lbad = True
        elif iline == 4:
            vv, iflag, _ = lread(datline, [("a", 8)] + ["i"] * 6)
            if iflag != 0:
                E.w(mu, f5, pid(E), "E31", modnam, errstr[3], datline.strip())
                m.lbad = True
        elif iline > 4 and "RANGE" not in datline and "DATE " not in datline:
            vv, iflag, _ = lread(datline, ["i", "i", "i", "i"] + ["f"] * u.nupvars_keep)
            if iflag == 0:
                sdate, isnd, ihr, ilev = vv[0], vv[1], vv[2], vv[3]
                rup = vv[4:]
                if ilev == 1:
                    u.nsnd[1][istation] += 1
                if u.upstart <= sdate <= u.upend:
                    if ilev == 1:
                        iday1 = new_sound(E, sdate, ihr, istation)
                        if ihr == -9:
                            u.lsound[iday1] = False
                        else:
                            u.nsnd[4][istation] += 1
                    u.writelevs += 1
                    u.s_levels[iday1][isnd] = u.writelevs
                    if u.writelevs > u.nuplevels[istation]:
                        u.nuplevels[istation] = u.writelevs
                    U = u.updata1.get(iday1, isnd)
                    for ivar in range(1, u.nupvars_keep + 1):
                        U[ivar][u.writelevs] = rup[ivar - 1]
            else:
                E.w(mu, f5, pid(E), "E31", modnam, errstr[4], datline.strip())
                m.lbad = True
    if not u.lbadup and m.lbad:
        u.lbadup = True


def calc_base(E, istation, sndno, datestr, ikeepbase, pres, pres_conv, missval, ibase, ht_conv):
    m, u = E.m, E.up
    modnam = fx("UP_STAGE2", 10)
    f1 = fmt_msg(E, "a,1x,i5,1x,a,1x,i5,1x,a20)")
    f2 = fmt_msg(E, "a,1x,i5,1x,a,1x,f7.2,1x,a,1x,i5,1x,a20)")
    if ikeepbase != 999999:
        ibase = ikeepbase
        E.w(m.msg_unit, f1, pid(E), "I30", modnam, "SURFACE LEVEL HEIGHT BASED ON MOST RECENT SURFACE LEVEL", ibase,
            "M FOR SOUNDING #", sndno, datestr)
    elif u.lelev[istation]:
        ibase = nint(u.upelev[istation])
        E.w(m.msg_unit, f1, pid(E), "I31", modnam, "SURFACE LEVEL HEIGHT BASED ON UPPER AIR STATION ELEVATION", ibase,
            "M FOR SOUNDING #", sndno, datestr)
    elif pres != missval:
        rpres = float(pres) * pres_conv
        expon = 1.0 / 5.255
        rbase = (288.15 / 0.0065) * (1.0 - (rpres / 1013.25) ** expon)
        ibase = nint(rbase / ht_conv)
        E.w(m.msg_unit, f2, pid(E), "I32", modnam, "SURFACE LEVEL HEIGHT", ibase, "BASED ON SURFACE LEVEL PRESSURE",
            rpres, "& STD. ATMOSPHERE FOR SOUNDING #", sndno, datestr)
    return ibase


def up_modify(E, istation):
    m, u = E.m, E.up
    modnam = fx("UP_MODIFY", 10)
    mand_levs = [None, 1000.0, 950.0, 900.0, 850.0, 800.0, 750.0, 700.0, 650.0, 600.0, 550.0, 500.0, 450.0,
                 400.0, 350.0, 300.0, 250.0, 200.0, 150.0, 100.0]
    f1 = fmt_msg(E, "i8,1x,a6,2(1x,a),1x,f6.0,1x,a)")
    f2 = fmt_msg(E, "i8,1x,a6,2(1x,a))")
    f3 = fmt_msg(E, "i8,1x,a6,2(1x,a),1x,i3,1x,a)")
    misspress = float(u.upvars[1].missval[istation])
    misstemp = [None, float(u.upvars[3].missval[istation]) * 0.1, float(u.upvars[4].missval[istation]) * 0.1]
    st = u.station_type[istation].strip()
    if u.lmodify[1][istation]:
        for d in range(1, u.nupdays + 1):
            if u.lsound[d]:
                for h in range(1, u.nsnding1[d] + 1):
                    orig_levs = u.s_levels[d][h]
                    hrstr = fwrite("(a3,1x,i2.2)", "HR:", u.snd_hrs[d][h])[0]
                    newlevs = orig_levs
                    U = u.updata1.get(d, h)
                    for lv in range(1, orig_levs):
                        if newlevs <= lv:
                            continue
                        if U[1][lv] == misspress or U[1][lv + 1] == misspress:
                            continue
                        pcheck1 = U[1][lv] - U[1][lv + 1]
                        if lv < 2:
                            continue
                        elif U[1][lv - 1] == misspress:
                            continue
                        pcheck2 = U[1][lv - 1] - U[1][lv]
                        if pcheck1 <= 0.01 * U[1][lv] or pcheck2 <= 0.01 * U[1][lv]:
                            l1 = 1
                            ip1 = nint(U[1][lv])
                            ip2 = 0
                            while l1 <= 19 and ip1 != ip2:
                                ip2 = nint(mand_levs[l1])
                                if ip1 == ip2:
                                    newlevs -= 1
                                    u.s_levels[d][h] = newlevs
                                    for ilev in range(lv, newlevs + 1):
                                        for ivar in range(1, 7):
                                            U[ivar][ilev] = U[ivar][ilev + 1]
                                    E.w(m.msg_unit, f1, pid(E), "I23", modnam, u.snd_date[d], hrstr, st,
                                        "STATION MANDATORY LEVEL: DELETED", mand_levs[l1], "MB")
                                l1 += 1
                    if u.s_levels[d][h] == 0:
                        E.w(m.msg_unit, f2, pid(E), "I23", modnam, u.snd_date[d], hrstr, st,
                            "STATION SOUNDING HAS NO LEVELS AFTER MANDATORY LEVEL DELETIONS")
                        u.nsnding1[d] -= 1
                        u.snd_hrs[d][h] = -9
            if u.lsound[d] and u.nsnding1[d] == 0:
                u.lsound[d] = False
    if u.lmodify[2][istation] or u.lmodify[3][istation]:
        for d in range(1, u.nupdays + 1):
            if u.lsound[d]:
                for h in range(1, u.nsnding1[d] + 1):
                    hrstr = fwrite("(a3,1x,i2.2)", "HR:", u.snd_hrs[d][h])[0]
                    U = u.updata1.get(d, h)
                    for lv in range(1, u.s_levels[d][h] + 1):
                        if u.lmodify[2][istation] and nint(U[5][lv]) != 0 and nint(U[6][lv]) == 0:
                            U[5][lv] = 0.0
                            E.w(m.msg_unit, f3, pid(E), "I24", modnam, u.snd_date[d], hrstr, st, "STATION LEVEL", lv,
                                "WIND DIRECTION SET TO 0 - CALM WIND")
                        if u.lmodify[3][istation] and lv >= 2 and lv < u.s_levels[d][h]:
                            for ivar in (3, 4):
                                if U[ivar][lv] == misstemp[ivar - 2]:
                                    U[ivar][lv] = newtemp(E, istation, lv, h, d, ivar)


def newtemp(E, istation, lv, h, d, v):
    m, u = E.m, E.up
    modnam = fx("NEWTEMP", 10)
    tname = [None, "TEMPERATURE", "DEW POINT"]
    misspress = float(u.upvars[1].missval[istation])
    misstemp = float(u.upvars[v].missval[istation]) * 0.1
    istr = "I%2d" % (v + 22)
    U = u.updata1.get(d, h)
    res = U[v][lv]
    formstr = fmt_msg(E, "i8,1x,a6,1x,a,1x,i3,2(1x,a))")
    hrstr = fwrite("(a3,1x,i2.2)", "HR", u.snd_hrs[d][h])[0]
    if U[1][lv - 1] != misspress and U[1][lv] != misspress and U[v][lv - 1] != misstemp:
        l1 = lv + 1
        lsub = False
        while l1 <= u.s_levels[d][h] and not lsub:
            if U[1][l1] != misspress and U[v][l1] != misstemp:
                plog = math.log(U[1][lv] / U[1][lv - 1]) / math.log(U[1][l1] / U[1][lv - 1])
                res = U[v][lv - 1] + (U[v][l1] - U[v][lv - 1]) * plog
                E.w(m.msg_unit, formstr, pid(E), istr, modnam, u.snd_date[d], hrstr, "LEVEL", lv, tname[v - 2],
                    "ESTIMATED")
                lsub = True
            l1 += 1
    return res


def virt_temp(U, lv):
    clr = 2500.0 / 0.461
    t0 = 1.0 / 302.16
    e = math.exp(clr * (t0 - 1.0 / (U[4][lv] + 273.16)) * 40.0)
    q = (0.62197 * e) / (U[1][lv] - 0.37803 * e)
    return (U[3][lv] + 273.16) * (1.0 + 0.6078 * q)


def up_audit(E, istation):
    m, u = E.m, E.up
    modnam = fx("UP_AUDIT", 10)
    F = {k: fmt_msg(E, v) for k, v in {
        2: "a15,1x,a)", 3: "a15,1x,a,1x,i3,1x,a,2(1x,f7.1))", 4: "a15,1x,a,1x,i3,1x,a)",
        5: "a15,2(1x,a,1x,i3),a,1x,a)", 6: "a15,2(1x,a),1x,i3)", 7: "a15,2(1x,a),2(1x,f9.1,1x,a),1x,i3)",
        8: "a15,1x,a,1x,i3,2(1x,a,1x,f5.1))", 9: "a15,1x,a,1x,f6.1,1x,a)", 10: "a,2(1x,a))"}.items()}
    F[1] = "(1x,a,1x,i1,a,1x,2(a2,a1),a4,1x,a)"
    mu = m.msg_unit
    eps = m.eps
    nv = max(u.nup_audit_vars[1:])
    if u.up_audit_index is None:
        u.up_audit_index = [[0] * (u.nstation + 1) for _ in range(nv + 1)]
    if u.up_audit_counts is None:
        u.up_audit_counts = [[[[0] * (u.nstation + 1) for _ in range(5)] for _ in range(11)] for _ in range(nv + 1)]
    lstr = [None, "LB", ""]
    ustr = [None, "UB", ""]
    i = 0
    missvals = [None] * (u.nupvars + 1)
    lowbound = [None] * (u.nupvars + 1)
    upbound = [None] * (u.nupvars + 1)
    for ivar in range(1, u.nupvars + 1):
        uv = u.upvars[ivar]
        if uv.laudit[istation]:
            i += 1
            u.up_audit_index[i][istation] = ivar
        missvals[ivar] = float(uv.missval[istation])
        lowbound[ivar] = float(uv.lowbound[istation]) * uv.conv[istation]
        upbound[ivar] = float(uv.upbound[istation]) * uv.conv[istation]
    E.w(mu, F[10], pid(E), "Q19", modnam, "PERFORMING QA FOR", u.station_type[istation].strip(), "UPPER AIR STATION")
    cnt = u.up_audit_counts
    up_inc = u.up_inc
    for d in range(1, u.nupdays + 1):
        if not u.lsound[d]:
            continue
        adate = "%08d" % u.snd_date[d]
        if not m.noprint:
            E.w(OUTPUT_UNIT, F[1], "Stage", m.istage, ": QA'ing upper air data for month/day/year", adate[4:6], "/",
                adate[6:8], "/", adate[0:4], "LST")
        for h in range(1, u.nsnding1[d] + 1):
            sl = u.s_levels[d][h]
            if sl == 0:
                continue
            U = u.updata1.get(d, h)
            date_hr_str = fx(fwrite("(i8,1x,a2,1x,i2.2)", u.snd_date[d], "HR", u.snd_hrs[d][h])[0], 20)
            if (float(u.uptop) - U[2][sl]) > eps:
                E.w(mu, F[9], pid(E), "Q28", modnam, date_hr_str, "TOP OF SOUNDING", U[2][sl], "M < 5000 M")
                u.nsnd_5k[istation] += 1
            lcalc = True
            if (abs(U[2][1] - missvals[2]) < eps or abs(U[3][1] - missvals[3]) < eps or
                    abs(U[4][1] - missvals[4]) < eps):
                E.w(mu, F[2], pid(E), "Q20", modnam, date_hr_str, "CANNOT RECOMPUTE HEIGHTS")
                lcalc = False
            else:
                tv1 = virt_temp(U, 1)
                ht = 0.0
                ilev = 2
                while ilev <= sl and lcalc:
                    if (abs(U[3][ilev] - missvals[3]) < eps or abs(U[4][ilev] - missvals[4]) < eps or
                            abs(U[1][ilev] - missvals[1]) < eps or abs(U[1][ilev - 1] - missvals[1]) < eps):
                        E.w(mu, F[2], pid(E), "Q20", modnam, date_hr_str, "CANNOT RECOMPUTE HEIGHTS")
                        lcalc = False
                    else:
                        tv2 = virt_temp(U, ilev)
                        ht = ht + (m.r / m.g) * 0.5 * (tv2 + tv1) * math.log(U[1][ilev - 1] / U[1][ilev])
                        tv1 = tv2
                        if abs(U[2][ilev] - ht) > 50.0:
                            E.w(mu, F[3], pid(E), "Q21", modnam, date_hr_str, "LEVEL:", ilev, "|OBS - CALC| HT > 50 M",
                                U[2][ilev], ht)
                        ilev += 1
            for ilev in range(1, sl + 1):
                if ilev == 1:
                    ilayer = 1
                elif int(U[2][ilev] - U[2][1]) > (8 * up_inc):
                    ilayer = 10
                elif int(U[2][ilev] - U[2][1]) > 0:
                    ilayer = int((U[2][ilev] - U[2][1]) / up_inc) + 2
                else:
                    E.w(mu, F[4], pid(E), "I27", modnam, date_hr_str, "LEVEL", ilev, "COULD NOT COMPUTE LAYER INDEX")
                    ilayer = 1
                if abs(U[5][ilev] - missvals[5]) > eps and abs(U[6][ilev] - missvals[6]) > eps:
                    if abs(U[5][ilev] - 0.0) > eps:
                        if abs(U[6][ilev] - 0.0) < eps:
                            E.w(mu, F[4], pid(E), "Q26", modnam, date_hr_str, "LEVEL", ilev,
                                "WIND SPEED = 0 FOR NON-ZERO WIND DIRECTION")
                            u.wind_stats[2][istation] += 1
                    else:
                        if abs(U[6][ilev] - 0.0) < eps:
                            E.w(mu, F[4], pid(E), "Q28", modnam, date_hr_str, "LEVEL", ilev, "CALM WIND")
                            u.wind_stats[1][istation] += 1
                if (abs(U[3][ilev] - missvals[3]) > eps and abs(U[4][ilev] - missvals[4]) > eps and
                        U[4][ilev] > U[3][ilev] and (U[4][ilev] - U[3][ilev]) > eps):
                    u.tempstat[istation] += 1
                    E.w(mu, F[8], pid(E), "Q27", modnam, date_hr_str, "LEVEL", ilev, "UATT", U[3][ilev], "< UATD",
                        U[4][ilev])
                if (u.lupkeywords[9] and istation == 1) or (u.lupkeywords[17] and istation == 2):
                    i1 = 0
                    saltar = False
                    for ivar in range(1, u.nup_audit_vars[istation] + 1):
                        iv = u.up_audit_index[ivar][istation]
                        if iv > 6:
                            i1 += 1
                        if iv > 6 and ilev > 1:
                            if abs(U[2][ilev] - missvals[2]) < eps and abs(U[2][ilev - 1] - missvals[2]) < eps:
                                E.w(mu, F[5], pid(E), "Q22", modnam, date_hr_str, "HEIGHT MISSING FOR LEVEL", ilev - 1,
                                    "OR", ilev, "; CANNOT COMPUTE", u.upvars[iv].varname.strip())
                                cnt[ivar][ilayer][1][istation] += 1
                                saltar = True
                                break
                            dz = U[2][ilev] - U[2][ilev - 1]
                            if iv == 7 or iv == 9:
                                iv1 = 6 if iv == 7 else 3
                                if (abs(U[iv1][ilev] - missvals[iv1]) > eps and
                                        abs(U[iv1][ilev - 1] - missvals[iv1]) > eps and dz > 0.0):
                                    delta = U[iv1][ilev] - U[iv1][ilev - 1]
                                    if iv == 7:
                                        U[i1 + 6][ilev] = abs(delta / dz) * 100.0
                                    else:
                                        U[i1 + 6][ilev] = (delta / dz) * 100.0
                            elif iv == 8:
                                if (abs(U[5][ilev] - missvals[5]) > eps and abs(U[5][ilev - 1] - missvals[5]) > eps
                                        and dz > 0.0):
                                    wd1 = _fmod(int(U[5][ilev]), 360)
                                    if wd1 < 0:
                                        wd1 += 360
                                    wd2 = _fmod(int(U[5][ilev - 1]), 360)
                                    if wd2 < 0:
                                        wd2 += 360
                                    diff_dir = float(abs(wd1 - wd2))
                                    if diff_dir > 180.0:
                                        diff_dir = 360.0 - diff_dir
                                    U[i1 + 6][ilev] = (diff_dir / dz) * 100.0
                            else:
                                if ilev < sl:
                                    if (abs(U[4][ilev] - missvals[4]) > eps and abs(U[4][ilev - 1] - missvals[4]) > eps
                                            and abs(U[4][ilev + 1] - missvals[4]) > eps and
                                            abs(U[2][ilev + 1] - missvals[2]) > eps and dz > 0.0):
                                        dew_dev = U[4][ilev - 1] + dz / (U[2][ilev + 1] - U[2][ilev - 1]) * \
                                            (U[4][ilev + 1] - U[4][ilev - 1])
                                        U[i1 + 6][ilev] = (abs(dew_dev - U[4][ilev]) / dz) * 100.0
                        cnt[ivar][ilayer][1][istation] += 1
                        i2 = iv if iv <= 6 else 6 + i1
                        if (abs(U[i2][ilev] - missvals[iv]) < eps and
                                (iv <= 6 or (7 <= iv <= 9 and ilev > 1) or (iv == 10 and 1 < ilev < sl))):
                            cnt[ivar][ilayer][2][istation] += 1
                            if not u.upvars[iv].lnomiss[istation] and iv <= 6:
                                E.w(mu, F[6], pid(E), "Q23", modnam, date_hr_str, u.upvars[iv].varname.strip(),
                                    "MISSING FOR LEVEL", ilev)
                        lowv = upv = False
                        if abs(U[i2][ilev] - missvals[iv]) > eps:
                            if u.upvars[iv].lincbound[istation]:
                                if U[i2][ilev] < lowbound[iv] and abs(U[i2][ilev] - lowbound[iv]) > eps:
                                    lowv = True
                                    lstr[2] = "< "
                                if U[i2][ilev] > upbound[iv] and abs(U[i2][ilev] - upbound[iv]) > eps:
                                    upv = True
                                    ustr[2] = "> "
                            else:
                                if U[i2][ilev] <= lowbound[iv]:
                                    lowv = True
                                    lstr[2] = "<="
                                if U[i2][ilev] >= upbound[iv]:
                                    upv = True
                                    ustr[2] = ">="
                        if lowv:
                            cnt[ivar][ilayer][3][istation] += 1
                            E.w(mu, F[7], pid(E), "Q24", modnam, date_hr_str, u.upvars[iv].varname.strip(), lstr[1],
                                U[i2][ilev], lstr[2], lowbound[ivar], "LEVEL", ilev)
                        if upv:
                            cnt[ivar][ilayer][4][istation] += 1
                            E.w(mu, F[7], pid(E), "Q25", modnam, date_hr_str, u.upvars[iv].varname.strip(), ustr[1],
                                U[i2][ilev], ustr[2], upbound[ivar], "LEVEL", ilev)
                    if saltar:
                        continue


def _fmod(a, b):
    """MOD de Fortran (signo del dividendo)."""
    return int(math.fmod(a, b))
