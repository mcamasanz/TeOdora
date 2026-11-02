# -*- coding: utf-8 -*-
"""Traducción de AERMET 26135 (US EPA, dominio público): módulo ONSITE (datos de estación propia
y datos pronósticos PROG/MMIF): lectura del control, extracción, promedios subhorarios, control
de calidad y fichero QAOUT."""
import datetime as _dt
import math
import re

import numpy as np

from . import tablas as T
from .comun import (checkfile, data_dates, dataline, fmt_msg, getdates, getfields, getloc,
                    getunit, leapyr, numdays, pid, range_mod, var_list)
from .estado import OUTPUT_UNIT, Ovar, arr
from .formato import ch, fread, fx, fwrite, lread, sub

OMIT = None


# ------------------------------------------------------------------------------------------
# Inicialización y lectura del fichero de control
# ------------------------------------------------------------------------------------------
def onsite_init(E):
    o = E.os
    o.osvars = [None] + [Ovar(t) for t in T.OSVARS[1:]]
    nombres = {
        "HFLX": "hflux_var", "LFLX": "lflux_var", "USTR": "ustar_var", "MHGT": "mix_var",
        "ZOHT": "zo_var", "SAMT": "samt_var", "INSO": "inso_var", "NRAD": "nrad_var",
        "DT01": "dt01_var", "VPTG": "vptg_var", "MOBL": "l_var", "WSTR": "wstar_var",
        "ALBD": "alb_var", "BOWN": "bo_var", "SLVP": "slp_var", "PRES": "pres_var",
        "CLHT": "clht_var", "TSKC": "cloud_var", "TSEA": "tsea_var", "ZDEP": "sstd_var",
        "HWAV": "hwav_var", "TWAV": "twav_var", "RDOW": "rdow_var", "HTNN": "height_var",
        "SENN": "se_var", "SVNN": "sv_var", "SWNN": "sw_var", "TTNN": "temp_var",
        "DPNN": "dewpt_var", "RHNN": "rh_var", "VVNN": "vv_var",
    }
    for ivar in range(1, o.nosvars + 1):
        nom = o.osvars[ivar].varname.strip()
        if nom in nombres:
            setattr(o, nombres[nom], ivar)
        if nom == "PAMT":
            o.prcp_vars[1] = ivar
        if nom == "PRCP":
            o.prcp_vars[2] = ivar
        if nom == "SANN":
            o.std_vars[1] = ivar
            o.sa_var = ivar
        if nom == "SUNN":
            o.std_vars[2] = ivar
            o.su_var = ivar
        if nom == "WDNN":
            o.wind_vars[1] = ivar
        if nom == "WSNN":
            o.wind_vars[2] = ivar


def os_path(E):
    m, o = E.m, E.os
    modnam = fx("OS_PATH", 10)
    formstr1 = fmt_msg(E, "a,1x,a)")
    formstr2 = fmt_msg(E, "i3,2(1x,a))")
    form1 = "(a%3d)" % m.flength
    getunit(E)
    m.lbad = False
    if m.ikey == 0:
        onsite_init(E)
        return
    ikey = m.ikey
    i = m.inpline1.find(m.keywrd[ikey].strip()) + 1
    i1 = len(m.keywrd[ikey].rstrip())
    if (4 <= ikey <= 6) or (8 <= ikey <= 10) or ikey == 27 or (12 <= ikey <= 17):
        if 4 <= ikey <= 6:
            jj = ikey - 3
        elif 8 <= ikey <= 10:
            jj = ikey - 4
        elif ikey == 27:
            jj = ikey - 14
        else:
            jj = ikey - 5
        if not o.loskeywords[jj]:
            o.loskeywords[jj] = True
        else:
            if ikey == 4 or (8 <= ikey <= 10) or ikey == 16 or ikey == 27:
                E.w(m.writeunit, formstr1, pid(E), "E03", modnam, "DUPLICATE ENTRY OF KEYWORD:",
                    m.keywrd[ikey].strip())
                m.lbad = True
                return
    else:
        E.w(m.writeunit, formstr1, pid(E), "E01", modnam, "INVALID KEYWORD", m.keywrd[ikey].strip())
        m.lbad = True
        return

    if ikey == 4:
        o.osstage1 = True
        if m.nfield != 2 and m.nfield != 3:
            E.w(m.writeunit, formstr2, pid(E), "E03", modnam, m.nfield,
                "IS AN INVALID NUMBER OF FIELDS FOR KEYWORD", m.keywrd[ikey].strip())
            m.lbad = True
        else:
            dataline(E, i, i1)
            m.os_inpfile = sub(m.inpline, m.fileind[1], m.fileind[2])
            if m.nfield == 3:
                v, io, _ = lread(sub(m.inpline1, m.formind[1], m.formind[2]), [("a", 6)])
                landflag = v[0].strip() if v else ""
                if landflag == "OW":
                    o.overland = False
                elif landflag != "OW" and landflag != "OL":
                    m.lbad = True
                    E.w(m.writeunit, formstr1, pid(E), "E03", modnam, "INVALID OVERLAND/WATER FLAG:",
                        landflag)
            m.os_inpfile, lgood = checkfile(E, m.os_data_unit, m.os_inpfile, 1)
    elif ikey == 5:
        os_list(E, i + i1)
    elif ikey == 6:
        if m.nfield != 3:
            E.w(m.writeunit, formstr2, pid(E), "E03", modnam, m.nfield,
                "IS AN INVALID NUMBER OF FIELDS FOR KEYWORD", m.keywrd[ikey].strip())
            m.lbad = True
        else:
            os_form(E)
    elif ikey == 8:
        if m.nfield != 2:
            E.w(m.writeunit, formstr2, pid(E), "E03", modnam, m.nfield,
                "IS AN INVALID NUMBER OF FIELDS FOR KEYWORD", m.keywrd[ikey].strip())
            m.lbad = True
        else:
            m.os_qafile = fread(form1, sub(m.inpline, i + i1 + 1, m.ilen), [("a", m.flength)])[0][0]
            m.os_qafile, lgood = checkfile(E, m.os_qaout_unit, m.os_qafile, 4)
    elif ikey == 9:
        if m.nfield not in (3, 4, 7, 8):
            E.w(m.writeunit, formstr2, pid(E), "E03", modnam, m.nfield,
                "IS AN INVALID NUMBER OF FIELDS FOR KEYWORD", m.keywrd[ikey].strip())
            m.lbad = True
        else:
            o.osstart, o.osend, o.osdates = getdates(E, i + i1)
    elif ikey == 10:
        if m.nfield < 4 or m.nfield > 6:
            E.w(m.writeunit, formstr2, pid(E), "E03", modnam, m.nfield,
                "IS AN INVALID NUMBER OF FIELDS FOR KEYWORD", m.keywrd[ikey].strip())
            m.lbad = True
        else:
            _getloc_os(E, i + i1)
    elif ikey == 12:
        if m.nfield != 6:
            E.w(m.writeunit, formstr2, pid(E), "E03", modnam, m.nfield,
                "IS AN INVALID NUMBER OF FIELDS FOR KEYWORD", m.keywrd[ikey].strip())
            m.lbad = True
        else:
            os_range(E, i + i1)
    elif ikey == 13:
        os_list(E, i + i1)
        if " ALL" in m.inpline1:
            o.laudit_all = True
    elif ikey == 14:
        if m.nfield != 4:
            E.w(m.writeunit, formstr2, pid(E), "E03", modnam, m.nfield,
                "IS AN INVALID NUMBER OF FIELDS FOR KEYWORD", m.keywrd[ikey].strip())
            m.lbad = True
        else:
            if o.osdt_hts is None:
                o.osdt_hts = [[None, -9.0, -9.0] for _ in range(o.maxdtind + 1)]
            delta_t_ht(E, i + i1)
    elif ikey == 15:
        if m.nfield < 2 or m.nfield > o.maxlevel + 1:
            E.w(m.writeunit, formstr2, pid(E), "E03", modnam, m.nfield,
                "IS AN INVALID NUMBER OF FIELDS FOR KEYWORD", m.keywrd[ikey].strip())
            m.lbad = True
        else:
            osheights(E, i1 + i)
    elif ikey == 16:
        if m.nfield != 2:
            E.w(m.writeunit, formstr2, pid(E), "E03", modnam, m.nfield,
                "IS AN INVALID NUMBER OF FIELDS FOR KEYWORD", m.keywrd[ikey].strip())
            m.lbad = True
        else:
            os_thresh(E, i1 + i)
    elif ikey == 17:
        if m.nfield < 3 or m.nfield > o.maxvars + 2:
            E.w(m.writeunit, formstr2, pid(E), "E03", modnam, m.nfield,
                "IS AN INVALID NUMBER OF FIELDS FOR KEYWORD", m.keywrd[ikey].strip())
            m.lbad = True
        else:
            os_vars(E, i1 + i)
    else:
        if m.nfield != 2 and m.nfield != 3:
            E.w(m.writeunit, formstr2, pid(E), "E03", modnam, m.nfield,
                "IS AN INVALID NUMBER OF FIELDS FOR KEYWORD", m.keywrd[ikey].strip())
            m.lbad = True
        else:
            os_obsnum(E, i1 + i)


def _getloc_os(E, i1):
    o = E.os
    r = getloc(E, i1, o.lgmt2lst, o.loselev)
    o.osid = r["stid"]
    o.oslat, o.oslon, o.osgmt2lst, o.oselev = r["lat"], r["lon"], r["gmt2lst"], r["elev"]
    o.lgmt2lst, o.loselev = r["lgmt2lst"], r["lelev"]


def os_list(E, i1):
    m, o = E.m, E.os
    modnam = fx("OS_LIST", 10)
    nfield1 = m.nfield - 1
    formstr = fmt_msg(E, "3(a,1x),a)")
    osvar = [None]
    oslog = [None]
    for i in range(1, o.nosvars + 1):
        v = o.osvars[i]
        if i < o.height_var:
            osvar.append(v.varname)
        else:
            osvar.append(fwrite("(a2,i2)", v.varname[0:2], o.maxlevel)[0])
        oslog.append(v.lnomiss if m.ikey == 5 else v.laudit)
    var_list(E, i1, nfield1, osvar, oslog, o.nosvars)
    for i in range(1, o.nosvars + 1):
        v = o.osvars[i]
        if m.ikey == 5:
            if v.lnomiss:
                E.w(m.writeunit, formstr, pid(E), "W02", modnam, "DUPLICATING LISTING OF VARIABLE FOR",
                    v.varname.strip(), "KEYWORD:", "NO_MISSING")
            v.lnomiss = oslog[i]
        else:
            if v.laudit and v.varname in m.inpline1 and (i < o.temp_var or i > o.wind_vars[2]):
                E.w(m.writeunit, formstr, pid(E), "W02", modnam, "DUPLICATING LISTING OF VARIABLE FOR",
                    v.varname.strip(), "KEYWORD:", "AUDIT")
            else:
                if oslog[i]:
                    if not v.luse:
                        oslog[i] = False
                v.laudit = oslog[i]


def os_range(E, i1):
    m, o = E.m, E.os
    modnam = fx("OS_RANGE", 10)
    nfield1 = m.nfield - 1
    formstr = fmt_msg(E, "a,1x,a)")
    varnam1 = getfields(E, i1, nfield1)
    if len(varnam1[1].rstrip(" ")) == 2:
        varnam1[1] = fx(fwrite("(2(2a))", varnam1[1].strip(), "NN")[0], 100)
    i = 1
    lfound = False
    while i <= o.nosvars and not lfound:
        if varnam1[1].strip() == o.osvars[i].varname.strip():
            lfound = True
        else:
            i += 1
    if lfound:
        linc, lowval, hival, missval, lgood = range_mod(E, varnam1[2], varnam1[3], varnam1[4],
                                                        varnam1[5])
        if lgood:
            v = o.osvars[i]
            if v.lmod:
                E.w(m.writeunit, formstr, pid(E), "W02", modnam,
                    "DUPLICATING LISTING OF VARIABLE FOR RANGE KEYWORD:", v.varname.strip())
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


def delta_t_ht(E, i1):
    m, o = E.m, E.os
    modnam = fx("DELTA_T_HT", 10)
    nfield1 = m.nfield - 1
    formstr1 = fmt_msg(E, "a,1x,a)")
    formstr2 = fmt_msg(E, "2(a,1x),a)")
    datafield = getfields(E, i1, nfield1)
    ht_index = 0
    ht = [None, -9.0, -9.0]
    iflag = [None, 0, 0, 0]
    v, iflag[1], _ = lread(datafield[1], ["i"])
    if iflag[1] == 0:
        ht_index = v[0]
    for k in (1, 2):
        v, iflag[k + 1], _ = lread(datafield[k + 1], ["f"])
        if iflag[k + 1] == 0:
            ht[k] = v[0]
    if iflag[1] == 0:
        if ht_index < 1 or ht_index > o.maxdtind:
            E.w(m.writeunit, formstr1, pid(E), "E05", modnam, "INVALID HEIGHT INDEX FOR DELTA_TEMP:",
                datafield[1].strip())
            m.lbad = True
        elif ht_index > 1:
            E.w(m.writeunit, formstr2, pid(E), "W64", modnam, "HEIGHT INDEX", datafield[1].strip(),
                "NOT USED")
        else:
            o.delta_t_ind = ht_index
            if o.osdt_hts[ht_index][1] != -9.0 and o.osdt_hts[ht_index][2] != -9.0:
                E.w(m.writeunit, formstr2, pid(E), "W02", modnam, "DUPLICATING LISTING OF HEIGHT INDEX",
                    datafield[1].strip(), "FOR DELTA_TEMP KEYWORD")
    else:
        E.w(m.writeunit, formstr1, pid(E), "E05", modnam, "INVALID HEIGHT INDEX FOR DELTA_TEMP:",
            datafield[1].strip())
        m.lbad = True
    for k in (1, 2):
        if iflag[k + 1] != 0 or ht[k] < 0.0:
            E.w(m.writeunit, formstr1, pid(E), "E05", modnam, "INVALID HEIGHT LISTED FOR DELTA_TEMP:",
                datafield[k + 1].strip())
            m.lbad = True
    if iflag[1] == 0 and iflag[2] == 0 and iflag[3] == 0 and not m.lbad:
        if ht[1] < ht[2]:
            o.osdt_hts[ht_index][1] = ht[1]
            o.osdt_hts[ht_index][2] = ht[2]
        else:
            E.w(m.writeunit, formstr2, pid(E), "E05", modnam, "HEIGHT 1 ", datafield[2].strip(),
                ">= HEIGHT 2 ", datafield[3].strip())
            m.lbad = True


def os_thresh(E, i1):
    m, o = E.m, E.os
    modnam = fx("OS_THRESH", 10)
    nfield1 = m.nfield - 1
    formstr1 = fmt_msg(E, "2(a),1x,a)")
    formstr2 = fmt_msg(E, "2(a,1x),f5.3,1x,a,1x,f3.1,1x,a)")
    datafield = getfields(E, i1, nfield1)
    v, iflag, _ = lread(datafield[1], ["f"])
    if iflag == 0:
        o.threshspeed = v[0]
        kw = m.keywrd[m.ikey].strip()
        if o.threshspeed < o.minthresh:
            E.w(m.writeunit, formstr2, pid(E), "E05", modnam, kw, "SPEED", o.threshspeed,
                " M/S IS BELOW", o.minthresh, "M/S")
            m.lbad = True
        elif o.threshspeed > o.maxthresh:
            E.w(m.writeunit, formstr2, pid(E), "E05", modnam, kw, "SPEED", o.threshspeed,
                " M/S EXCEEDS", o.maxthresh, "M/S")
            m.lbad = True
        elif abs(o.threshspeed - o.progthresh) > m.eps and m.lpath[5]:
            E.w(m.writeunit, formstr2, pid(E), "W65", modnam, kw, "SPEED", o.threshspeed,
                " M/S IS NOT EQUAL TO PROG THRESHOLD", o.progthresh, "M/S")
        else:
            if o.threshspeed > o.warnthresh:
                E.w(m.writeunit, formstr2, pid(E), "W65", modnam, kw, "SPEED", o.threshspeed,
                    " M/S EXCEEDS", o.warnthresh, "M/S")
    else:
        E.w(m.writeunit, formstr1, pid(E), "E05", modnam, "INVALID VALUE FOR KEYWORD",
            m.keywrd[m.ikey].strip(), ":", datafield[1].strip())
        m.lbad = True


def osheights(E, i1):
    m, o = E.m, E.os
    modnam = fx("OSHEIGHTS", 10)
    formstr1 = fmt_msg(E, "a,1x,a)")
    formstr2 = fmt_msg(E, "a,1x,f10.4,1x,a,1x,i2,1x,a,1x,f10.4,1x,a,1x,i2)")
    nfield1 = m.nfield - 1
    datafield = getfields(E, i1, nfield1)
    if o.osheights1 is None:
        o.osheights1 = [0.0] * (o.maxlevel + 1)
    for i in range(1, nfield1 + 1):
        v, iflag, _ = lread(datafield[i], ["f"])
        ht = v[0] if iflag == 0 else 0.0
        if iflag == 0 and ht > 0.0:
            o.noshts += 1
            o.osheights1[o.noshts] = ht
            if o.noshts > 1:
                if o.osheights1[o.noshts] <= o.osheights1[o.noshts - 1]:
                    m.lbad = True
                    E.w(m.msg_unit, formstr2, pid(E), "E62", modnam, "OSHEIGHTS HEIGHT",
                        o.osheights1[o.noshts], "M LEVEL", o.noshts, "IS <= OSHEIGHTS HEIGHT",
                        o.osheights1[o.noshts - 1], "M LEVEL", o.noshts - 1)
        else:
            E.w(m.writeunit, formstr1, pid(E), "E05", modnam, "INVALID HEIGHT LISTED FOR OSHEIGHTS:",
                datafield[i].strip())
            m.lbad = True


def os_vars(E, i1):
    m, o = E.m, E.os
    modnam = fx("OS_VARS", 10)
    nfield1 = m.nfield - 1
    formstr1 = fmt_msg(E, "3(a,1x),i2)")
    formstr2 = fmt_msg(E, "2(a,1x),a)")
    formstr4 = fmt_msg(E, "a,1x,i2,1x,a,1x,i2,a)")
    formstr5 = fmt_msg(E, "a,1x,a)")
    datafield = getfields(E, i1, nfield1)
    if o.varmap1 is None:
        o.varmap1 = np.zeros((o.maxread + 1, o.nosvars + 1, 3), dtype=int)
    if o.os_reads is None:
        o.os_reads = ["*"] * (o.maxread + 1)
    add1 = 0
    v, iflag, _ = lread(datafield[1], ["i"])
    iread = v[0] if iflag == 0 else 0
    if iflag == 0:
        if iread > o.maxread:
            E.w(m.writeunit, formstr1, pid(E), "E05", modnam, "READ INDEX", datafield[1].strip(),
                "EXCEEDS MAXIMUMN NUMBER OF READ LINES", o.maxread)
            m.lbad = True
        elif iread <= 0:
            E.w(m.writeunit, formstr2, pid(E), "E05", modnam, "READ INDEX", datafield[1].strip(),
                "IS LESS THAN ZERO")
            m.lbad = True
        elif iread == o.nread:
            L = m.inpline1
            ir = L.find("READ") + 1
            il = ir + 4
            lletter = False
            lt = len(L.rstrip(" "))
            while il <= lt and not lletter:
                if "A" <= ch(L, il) <= "Z":
                    lletter = True
                else:
                    il += 1
            lfound = False
            add1 = 1
            while add1 <= o.nosvars and not lfound:
                if o.varmap1[iread, add1, 1] == 0:
                    lfound = True
                else:
                    add1 += 1
            add1 = add1 - 1
            o.os_reads[iread] = fwrite("(a,1x,a)", o.os_reads[iread].strip(), sub(L, il, lt).strip())[0]
        elif iread > o.nread + 1:
            E.w(m.writeunit, formstr4, pid(E), "E05", modnam, "READ INDEX", iread,
                "EXCEEDS CURRENT NUMBER OF READ INDICES +1", o.nread, "; CHECK READ ORDER")
            m.lbad = True
        else:
            o.nread = iread
            add1 = 0
            o.os_reads[iread] = m.inpline1
    else:
        E.w(m.writeunit, formstr5, pid(E), "E05", modnam, datafield[1].strip(),
            "IS AN INVALID VALUE FOR READ INDEX")
        m.lbad = True
    if not m.lbad:
        for ifield in range(2, nfield1 + 1):
            i = 1
            lfound = False
            ilev = 0
            df = datafield[ifield]
            varlen = len(df.rstrip(" "))
            if varlen == 4:
                while i <= o.nosvars and not lfound:
                    if df.strip() == o.osvars[i].varname.strip():
                        lfound = True
                    else:
                        if i >= o.height_var and df[0:2] == o.osvars[i].varname[0:2]:
                            v, io, _ = lread(df[2:4], ["i"])
                            if io == 0:
                                ilev = v[0]
                            if io == 0 and ilev <= o.maxlevel:
                                lfound = True
                            else:
                                i += 1
                        else:
                            i += 1
            if lfound:
                ov = o.osvars[i]
                if not ov.luse:
                    E.w(m.writeunit, formstr2, pid(E), "W64", modnam, "VARIABLE", ov.varname.strip(),
                        "IS NOT USED BY AERMET AND WILL BE READ BUT NOT BE PROCESSED")
                ov.lread = True
                if i == o.sstd_var:
                    o.read_sst_depth = ov.lread
                o.varmap1[iread, ifield - 1 + add1, 1] = i
                o.varmap1[iread, ifield - 1 + add1, 2] = ilev
                if ilev > 0:
                    if ilev > ov.nlevels:
                        ov.nlevels = ilev
                    if ov.firstlev == 0 or ilev < ov.firstlev:
                        ov.firstlev = ilev
            else:
                E.w(m.writeunit, formstr2, pid(E), "E05", modnam, "INVALID VARIABLE NAME", df.strip(),
                    "FOR READ STATEMENT")
                m.lbad = True


def os_form(E):
    m, o = E.m, E.os
    modnam = fx("OS_FORM", 10)
    formstr1 = fmt_msg(E, "a,1x,i4,1x,a)")
    formstr3 = fmt_msg(E, "a,1x,i2,1x,a,1x,i2)")
    formstr4 = fmt_msg(E, "a,1x,i2,1x,a,1x,i2,a)")
    formstr5 = fmt_msg(E, "a,1x,a)")
    formstr6 = fmt_msg(E, "a,1x,i2,1x,a,1x,i3)")
    if o.os_format1 is None:
        o.os_format1 = ["*"] * (o.maxread + 1)
    L = m.inpline1
    v, iflag, _ = lread(L, [("a", 12), "i"])
    iread = v[1] if (iflag == 0 and len(v) > 1) else 0
    l_long = False
    if iflag == 0:
        if iread > o.maxread:
            E.w(m.writeunit, formstr1, pid(E), "E05", modnam, "FORMAT INDEX", iread,
                "EXCEEDS MAXIMUMN NUMBER OF FORMAT LINES", o.maxread)
            m.lbad = True
        elif iread <= 0:
            E.w(m.writeunit, formstr1, pid(E), "E05", modnam, "FORMAT INDEX", iread, "IS LESS THAN ZERO")
            m.lbad = True
        elif iread == o.nformat:
            E.w(m.writeunit, formstr3, pid(E), "E05", modnam, "FORMAT INDEX", iread,
                "EQUALS CURRENT NUMBER OF FORMAT INDICES", o.nformat)
            m.lbad = True
        elif iread > o.nformat + 1:
            E.w(m.writeunit, formstr4, pid(E), "E05", modnam, "FORMAT INDEX", iread,
                "IS GREATER THAN NUMBER OF FORMAT INDICES + 1", o.nformat, "; CHECK FORMAT ORDER")
            m.lbad = True
        else:
            o.nformat = iread
    else:
        E.w(m.writeunit, formstr5, pid(E), "E05", modnam, L.strip(), "IS AN INVALID VALUE FOR FORMAT INDEX")
        m.lbad = True
    if not m.lbad:
        aread = "%2d" % iread
        iform = L.find(aread) + 1
        if iread < 10:
            o.os_format1[iread] = fx(sub(L, iform + 2, m.ilen).strip(), o.formlen).rstrip()
            if (m.ilen - iform - 1) > o.formlen:
                l_long = True
        else:
            o.os_format1[iread] = fx(sub(L, iform + 3, m.ilen).strip(), o.formlen).rstrip()
            if (m.ilen - iform - 2) > o.formlen:
                l_long = True
        if l_long:
            E.w(m.writeunit, formstr6, pid(E), "E63", modnam, "FORMAT INDEX", iread,
                "EXCEEDS CHARACTER STRING LENGTH", o.formlen)
            m.lbad = True


def os_obsnum(E, i1):
    m, o = E.m, E.os
    modnam = fx("OS_OBSNUM", 10)
    nfield1 = m.nfield - 1
    formstr1 = fmt_msg(E, "a,1x,i3,1x,a,1x,i2)")
    formstr2 = fmt_msg(E, "a,1x,2(a),1x,a)")
    formstr3 = fmt_msg(E, "3(a,1x),a)")
    datafield = getfields(E, i1, nfield1)
    v, iflag, _ = lread(datafield[1], ["i"])
    if iflag == 0:
        o.nobs_hr = v[0]
        kw = m.keywrd[m.ikey].strip()
        if o.nobs_hr < o.min_obs_hr:
            E.w(m.writeunit, formstr1, pid(E), "E05", modnam, kw, o.nobs_hr, "IS LESS THAN", o.min_obs_hr)
            m.lbad = True
        elif o.nobs_hr > o.max_obs_hr:
            E.w(m.writeunit, formstr1, pid(E), "E05", modnam, kw, o.nobs_hr, "EXCEEDS", o.max_obs_hr)
            m.lbad = True
        else:
            if o.nobs_hr % 2 == 0:
                o.min_obs = o.nobs_hr // 2
            else:
                o.min_obs = (o.nobs_hr + 1) // 2
    else:
        E.w(m.writeunit, formstr2, pid(E), "E05", modnam, "INVALID VALUE FOR KEYWORD",
            m.keywrd[m.ikey].strip(), ":", datafield[1].strip())
        m.lbad = True
    if nfield1 == 2:
        if datafield[2].strip() == "VECTOR":
            o.lvector = True
        elif datafield[2].strip() == "SCALAR":
            o.lvector = False
        else:
            o.lvector = False
            m.lbad = True
            E.w(m.writeunit, formstr3, pid(E), "E05", modnam, "INVALID VALUE FOR WIND AVERAGING METHOD:",
                datafield[2].strip(), "FOR KEYWORD", m.keywrd[m.ikey].strip())
    else:
        o.lvector = False


def os_test(E):
    m, o = E.m, E.os
    modnam = fx("OS_TEST", 10)
    f = {k: fmt_msg(E, s) for k, s in {
        1: "a,1x,a)", 2: "a)", 3: "a,1x,i2,1x,a,1x,i2)", 4: "a,1x,a,1x,a,1x,a)",
        5: "a,1x,2(1x,f5.1,1x,a))", 6: "a,1x,2(1x,f5.1,1x,a),1x,a)", 7: "2(a,1x),a)",
        8: "a,1x,i3,1x,a,1x,i3)", 9: "a,1x,i2,1x,a,1x,i2)", 10: "a,1x,a4,1x,a)"}.items()}
    mu = m.msg_unit
    ol_ow_msg = False
    if o.osstage1 and not o.loskeywords[1]:
        E.w(mu, f[1], pid(E), "E08", modnam, "MISSING MANDATORY KEYWORD", m.keywrd[4])
        m.lbad = True
    if o.osstage1 and not o.loskeywords[3]:
        E.w(mu, f[1], pid(E), "E08", modnam, "MISSING MANDATORY KEYWORD", m.keywrd[6])
        m.lbad = True
    if o.osstage1 and not o.loskeywords[12]:
        E.w(mu, f[1], pid(E), "E08", modnam, "MISSING MANDATORY KEYWORD", m.keywrd[17])
        m.lbad = True
    if o.osstage1 and o.loskeywords[3] and o.loskeywords[12]:
        if o.nread != o.nformat:
            E.w(mu, f[3], pid(E), "E50", modnam, "NUMBER OF VALID READ STATEMENTS", o.nread,
                "IS NOT EQUAL TO NUMBER OF VALID FORMAT STATEMENTS", o.nformat)
            m.lbad = True
        else:
            lbad2 = osformread(E)
            if lbad2:
                m.lbad = True
            else:
                o.varmap = np.zeros((o.nread + 1, o.nreadvars + 1, 3), dtype=int)
                o.os_format = [None] + [o.os_format1[i] for i in range(1, o.nread + 1)]
                o.varmap[1:, 1:, :] = o.varmap1[1:o.nread + 1, 1:o.nreadvars + 1, :]
                o.varmap1 = None
                o.os_format1 = None
    if not o.osstage1 and m.lstage[2] and not o.loskeywords[4]:
        E.w(mu, f[1], pid(E), "E08", modnam, "MISSING MANDATORY KEYWORD", m.keywrd[7])
        m.lbad = True
    if o.osstage1:
        if not o.loskeywords[5]:
            if m.lstage[2]:
                E.w(mu, f[2], pid(E), "W03", modnam, "XDATES KEYWORD MISSING; READ XDATES FROM METPREP XDATES")
            else:
                E.w(mu, f[1], pid(E), "E08", modnam, "MISSING MANDATORY KEYWORD", m.keywrd[9])
                m.lbad = True
    if o.osstage1 and not m.lstage[2] and not o.loskeywords[6]:
        E.w(mu, f[1], pid(E), "E08", modnam, "MISSING MANDATORY KEYWORD", m.keywrd[10])
        m.lbad = True
    ov = o.osvars
    if o.osstage1 and ov[o.wind_vars[2]].lread and not o.loskeywords[11]:
        E.w(mu, f[1], pid(E), "E08", modnam, "MISSING MANDATORY KEYWORD", m.keywrd[16])
        m.lbad = True
    if o.osstage1:
        if o.loskeywords[13] and o.nobs_hr == 1 and ov[5].lread:
            E.w(mu, f[2], pid(E), "W66", modnam, "OBS/HOUR = 1 WITH OSMN; IGNORE OSMN")
        elif o.loskeywords[13] and o.min_obs_hr < o.nobs_hr <= o.max_obs_hr and not ov[5].lread:
            E.w(mu, f[4], pid(E), "E51", modnam, "OBS/HOUR KEYWORD", "PRESENT", "WITHOUT", "OSMN")
            m.lbad = True
        elif not o.loskeywords[13] and ov[5].lread:
            E.w(mu, f[4], pid(E), "E51", modnam, "OBS/HOUR KEYWORD", "NOT PRESENT", "WITH", "OSMN")
            m.lbad = True
    if o.overland and o.osstage1:
        for ivar in range(1, o.nosvars + 1):
            if (ivar in (o.tsea_var, o.sstd_var, o.hwav_var, o.twav_var, o.rdow_var)
                    and ov[ivar].lread and not ol_ow_msg):
                ol_ow_msg = True
                E.w(mu, f[2], pid(E), "W60", modnam, "LOCATION IS OVERLAND BUT DATA INDICATES OVERWATER")
            if (ivar in (o.hflux_var, o.lflux_var, o.zo_var, o.vptg_var, o.l_var, o.wstar_var,
                         o.alb_var, o.bo_var, o.tsea_var, o.sstd_var, o.hwav_var, o.twav_var,
                         o.rdow_var) and ov[ivar].lread):
                E.w(mu, f[10], pid(E), "I67", modnam, "LOCATION IS OVERLAND; VARIABLE",
                    ov[ivar].varname.strip(), "READ IN STAGE 1 BUT WILL NOT BE USED IN STAGE 2")
            if (ivar == o.ustar_var or ivar == o.cloud_var) and ov[ivar].lread and m.lpath[5]:
                E.w(mu, f[10], pid(E), "I67", modnam, "LOCATION IS OVERLAND; PROGNOSTIC VARIABLE",
                    ov[ivar].varname.strip(), "READ IN STAGE 1 BUT WILL NOT BE USED IN STAGE 2")
    if o.osstage1 and o.loskeywords[10]:
        o.os_heights = [None] + [o.osheights1[i] for i in range(1, o.noshts + 1)]
        o.osheights1 = None
        if ov[o.height_var].lread:
            E.w(mu, f[2], pid(E), "W67", modnam,
                "OSHEIGHTS AND HTNN BOTH SPECIFIED. OSHEIGHTS KEYWORD WILL BE USED AND HTnn VARIABLES IGNORED")
            if ov[o.height_var].nlevels != o.noshts:
                E.w(mu, f[8], pid(E), "E57", modnam, "NUMBER OF OSHEIGHTS", o.noshts,
                    "NOT EQUAL TO NUMBER OF HTNN LEVELS", ov[o.height_var].nlevels)
                m.lbad = True
        o.luseoshts = True
    if o.osstage1:
        if o.loskeywords[9]:
            if ov[o.dt01_var].lread:
                E.w(mu, f[5], pid(E), "I61", modnam, "DELTA_TEMP HEIGHTS:", o.osdt_hts[1][1], "M",
                    o.osdt_hts[1][2], "M")
            else:
                E.w(mu, f[6], pid(E), "W69", modnam, "TEMPERATURES FOR DELTA TEMP HEIGHTS:",
                    o.osdt_hts[1][1], "M", o.osdt_hts[1][2], "M", "WILL BE USED IF AVAILABLE")
        else:
            if ov[o.dt01_var].lread:
                E.w(mu, f[2], pid(E), "E54", modnam, "NO DELTA_TEMP HEIGHTS LISTED FOR DT01")
                m.lbad = True
    if o.osstage1:
        for i in range(6, o.nosvars + 1):
            if ov[i].laudit and ov[i].luse and not ov[i].lread:
                if not o.laudit_all:
                    E.w(mu, f[7], pid(E), "W68", modnam, "ONSITE VARIABLE", ov[i].varname.strip(),
                        "AUDITED BUT NOT READ IN, RESET TO NOT AUDIT")
                ov[i].laudit = False
    if ov[o.wind_vars[1]].lread != ov[o.wind_vars[2]].lread:
        E.w(mu, f[2], pid(E), "E60", modnam, "WIND SPEED AND DIRECTION ARE NOT PROCESSED TOGETHER")
        m.lbad = True
    if ov[o.sstd_var].lread and not ov[o.tsea_var].lread:
        E.w(mu, f[2], pid(E), "E61", modnam, "NO SEA SURFACE TEMPS WITH SEA SURFACE TEMP DEPTH")
        m.lbad = True
    wd, ws = ov[o.wind_vars[1]], ov[o.wind_vars[2]]
    if wd.lread and ws.lread and (wd.firstlev != ws.firstlev or wd.nlevels != ws.nlevels):
        if wd.firstlev != ws.firstlev:
            E.w(mu, f[9], pid(E), "W61", modnam, "FIRST LEVEL FOR WD", wd.firstlev,
                "NOT EQUAL TO FIRST LEVEL FOR WS", ws.firstlev)
        if wd.nlevels != ws.nlevels:
            E.w(mu, f[9], pid(E), "W61", modnam, "NUMBER OF LEVELS FOR WD", wd.nlevels,
                "NOT EQUAL TO NUMBER OF LEVELS FOR WS", ws.nlevels)


def osformread(E):
    m, o = E.m, E.os
    modnam = fx("OSFORMREAD", 10)
    formstr1 = fmt_msg(E, "3(a))")
    formstr2 = fmt_msg(E, "a,1x,i2,1x,3(a))")
    formstr3 = fmt_msg(E, "2(a,1x,i2,1x),a)")
    formstr4 = fmt_msg(E, "5(a,1x),i2,1x,a)")
    lbad2 = False
    timevars = 0
    for i in range(1, o.nread + 1):
        if i == 1:
            timevars = 5 if o.osvars[5].lread else 4
            for j in range(1, timevars + 1):
                if o.varmap1[i, j, 1] > 5:
                    lbad2 = True
            if lbad2:
                E.w(m.msg_unit, formstr1, pid(E), "E52", modnam, 'FIRST READ STATEMENT "',
                    o.os_reads[i].strip(), '" DOES NOT INCLUDE DATE/TIME VARIABLES AS FIRST SET OF VARIABLES')
        else:
            r = o.os_reads[i]
            if "OSYR" in r or "OSMO" in r or "OSDY" in r or "OSHR" in r or "OSMN" in r:
                for j in range(1, timevars + 1):
                    if o.varmap1[i, j, 1] > 5:
                        lbad2 = True
                if lbad2:
                    E.w(m.msg_unit, formstr2, pid(E), "E52", modnam, "READ STATEMENT", i, '"',
                        o.os_reads[i].strip(), '" INCLUDES DATE/TIME VARIABLES BUT THEY ARE NOT FIRST SET')
        j = 1
        lend = False
        while j <= o.nosvars and not lend:
            if o.varmap1[i, j, 1] == 0:
                lend = True
            else:
                j += 1
        j = j - 1
        if j > o.nreadvars:
            o.nreadvars = j
        fm = o.os_format1[i]
        if fm.strip() != "FREE":
            lt = len(fm.rstrip(" "))
            if fm[0:1] != "(" and fm[lt - 1:lt] != ")":
                lbad2 = True
                E.w(m.msg_unit, formstr4, pid(E), "E53", modnam, "FIRST CHARACTER", fm[0:1],
                    "AND/OR LAST CHARACTER", fm[lt - 1:lt], " IN FORMAT ", i, "ARE NOT PARENTHESES")
            n1 = fm.count("(")
            n2 = fm.count(")")
            if n1 != n2:
                E.w(m.msg_unit, formstr3, pid(E), "E53", modnam, "NUMBER OF LEFT PARENTHESES", n1,
                    "NOT EQUAL TO NUMBER OF RIGHT PARENTHESES", n2, "FOR FORMAT KEYWORD")
                if not lbad2:
                    lbad2 = True
    o.os_reads = None
    return lbad2


def os_stage2(E):
    """Lee la cabecera del QAOUT ONSITE en una corrida de sólo etapa 2."""
    m, o = E.m, E.os
    modnam = fx("OS_STAGE2", 10)
    formstr1 = fmt_msg(E, "i3,2(1x,a))")
    formstr2 = fmt_msg(E, "3(a,1x),a)")
    formstr3 = fmt_msg(E, "a,1x,i6)")
    formstr4 = fmt_msg(E, "a4,1x,a,1x,i2,1x,a,i3)")
    formstr5 = fmt_msg(E, "a,1x,a4)")
    f = E.units.get(m.os_qaout_unit)
    m.lbad = False
    ldata = False
    iline = 0
    if f is None:
        return
    claves = [m.keywrd[k].strip() for k in range(1, m.nkeys + 1)]
    alguna = re.compile("|".join(re.escape(c) for c in claves))
    while not m.lbad:
        raw = f.leer()
        if raw is None:
            break
        iline += 1
        L = raw[:m.linelen].upper()
        m.inpline1 = L
        m.ilen = len(L.rstrip(" "))
        # primera palabra clave (por orden de la lista) contenida en la línea; el prefiltro
        # descarta de una vez las líneas de datos, que no contienen ninguna
        ikey = 1
        if alguna.search(L) is None:
            ikey = m.nkeys + 1
        else:
            while ikey <= m.nkeys and claves[ikey - 1] not in L:
                ikey += 1
        m.ikey = ikey
        kwt = m.keywrd[ikey].strip() if ikey <= m.nkeys else ""
        if "LOCATION" in L:
            m.nfield = _contar(L)
            i = L.find("LOCATION") + 1
            _getloc_os(E, i + 8)
        if "DELTA_TEMP" in L:
            m.nfield = _contar(L)
            if m.nfield != 4:
                E.w(m.writeunit, formstr1, pid(E), "E03", modnam, m.nfield,
                    "IS AN INVALID NUMBER OF FIELDS FOR KEYWORD", kwt)
                m.lbad = True
            else:
                if o.osdt_hts is None:
                    o.osdt_hts = [[None, -9.0, -9.0] for _ in range(o.maxdtind + 1)]
                for k in range(1, o.maxdtind + 1):
                    o.osdt_hts[k][1] = o.osdt_hts[k][2] = -9.0
                i = L.find("DELTA_TEMP") + 1
                delta_t_ht(E, i + 10)
        if "THRESHOLD" in L:
            m.nfield = _contar(L)
            if m.nfield != 2:
                E.w(m.writeunit, formstr1, pid(E), "E03", modnam, m.nfield,
                    "IS AN INVALID NUMBER OF FIELDS FOR KEYWORD", kwt)
                m.lbad = True
            else:
                i = L.find("THRESHOLD") + 1
                os_thresh(E, i + 10)
        if "OVERWATER" in L:
            o.overland = False
        if "OVERLAND" in L:
            o.overland = True
        if "DATES" in L:
            i = L.find("DATES") + 1
            m.nfield = 7
            o.osstart, o.osend, o.osdates = getdates(E, i + 5)
        if "RANGE" in L:
            i = L.find("RANGE") + 1
            m.nfield = 6
            os_range(E, i + 5)
        if "FIRST-LAST LEVELS" in L:
            nn = L.find("LEVELS") + 1
            ivar = o.height_var
            lfound = False
            while ivar <= o.nosvars and not lfound:
                if L[0:4].strip() == o.osvars[ivar].varname.strip():
                    lfound = True
                    v, io, _ = lread(sub(L, nn + 6, m.ilen), ["i", "i"])
                    if io == 0:
                        ilevs1, ilevs2 = v
                        ov = o.osvars[ivar]
                        if ilevs1 < 1:
                            E.w(m.writeunit, formstr4, pid(E), "E05", modnam, ov.varname, "FIRST", ilevs1,
                                "<", 1)
                            m.lbad = True
                        elif ilevs1 > o.maxlevel:
                            E.w(m.writeunit, formstr4, pid(E), "E05", modnam, ov.varname, "FIRST", ilevs1,
                                ">", o.maxlevel)
                            m.lbad = True
                        else:
                            ov.firstlev = ilevs1
                        if ilevs2 < 1:
                            E.w(m.writeunit, formstr4, pid(E), "E05", modnam, ov.varname, "LAST", ilevs2,
                                "<", 1)
                            m.lbad = True
                        elif ilevs2 > o.maxlevel:
                            E.w(m.writeunit, formstr4, pid(E), "E05", modnam, ov.varname, "LAST", ilevs2,
                                ">", o.maxlevel)
                            m.lbad = True
                        else:
                            ov.nlevels = ilevs2
                    else:
                        E.w(m.writeunit, formstr5, pid(E), "E05", modnam,
                            "ERROR READING FIRST AND/OR LAST LEVELS FOR", o.osvars[ivar].varname)
                else:
                    ivar += 1
            if not lfound:
                E.w(m.writeunit, formstr5, pid(E), "E05", modnam, "INVALID VARIABLE FOR FIRST-LAST LINE",
                    L[0:4])
                m.lbad = True
        if "DATE       HR     LEV" in L:
            ldata = True
            nfields = _contar(L)
            v, io, _ = lread(sub(L, 22, len(L.rstrip(" "))), [("a", 4)] * (nfields - 3))
            vlist = [None] + v
            o.ext_index = [None] + [0] * (nfields - 3)
            for ivar1 in range(1, nfields - 2):
                ivar = 1
                lfound = False
                while ivar <= o.nosvars and not lfound:
                    if vlist[ivar1].strip() == o.osvars[ivar].varname.strip():
                        lfound = True
                        o.osvars[ivar].lread = True
                        if ivar == o.sstd_var:
                            o.read_sst_depth = o.osvars[ivar].lread
                        o.ext_index[ivar1] = ivar
                    else:
                        ivar += 1
                if lfound and ivar <= 5:
                    E.w(m.writeunit, formstr2, pid(E), "E59", modnam, "INVALID DATE/TIME VARIABLE IN",
                        o.dattype[m.ipath - 3], "QAOUT FILE:", o.osvars[ivar].varname.strip())
                    m.lbad = True
                elif not lfound:
                    E.w(m.writeunit, formstr2, pid(E), "E05", modnam, "INVALID VARIABLE IN",
                        o.dattype[m.ipath - 3], "QAOUT FILE:", vlist[ivar1].strip())
                    m.lbad = True
        if ldata and "DATE       HR     LEV" not in L:
            v, io, _ = lread(L, ["i", "i", "i"])
            if io == 0:
                if v[2] > o.nlevel:
                    o.nlevel = v[2]
            else:
                m.lbad = True
                E.w(m.msg_unit, formstr3, pid(E), "E55", modnam, "ERROR READING DATA LINE:", iline)
    f.rewind()
    if m.lbad:
        o.lbados = True


def _contar(L):
    n = 0
    lt = len(L.rstrip(" "))
    for i in range(1, lt + 1):
        if ch(L, i + 1) == " " and ch(L, i) != " ":
            n += 1
    return n


# ------------------------------------------------------------------------------------------
# Procesamiento (etapa 1: extracción y QA; etapa 2: lectura del QAOUT)
# ------------------------------------------------------------------------------------------
def os_proc(E, ahora=None):
    m, o = E.m, E.os
    modnam = fx("OS_PROC", 10)
    formstr1 = fmt_msg(E, "3(a,1x),a8,1x,2(i2.2,a1),i2.2)")
    formstr2 = fmt_msg(E, "a,1x,i8)")
    formstr3 = fmt_msg(E, "a,1x,i8,1x,a1,i8,a)")
    formstr4 = fmt_msg(E, "a,1x,a2,1x,a,1x,i2)")
    ov = o.osvars
    m.lbad = False
    for ivar in range(6, o.nosvars + 1):
        if ov[ivar].laudit:
            o.nos_audit_vars += 1
    o.nosdays = numdays(o.osstart, o.osend)
    if m.istage == 1 and o.osstage1:
        o.nlevel = max(o.nlevel, int(o.varmap[:, :, 2].max()))
    o.nvars = sum(1 for ivar in range(6, o.nosvars + 1) if ov[ivar].lread)
    nv, nl, nd = o.nvars, o.nlevel, o.nosdays
    o.osdata1a = arr(nv, nl, 24, nd)
    o.read_index = [0] * (nv + 1)
    o.os_date = [0] * (nd + 1)
    if ov[5].lread:
        o.os_subhr_vals = arr(o.nobs_hr, nv, nl, 24, nd)
        o.obs_minutes = arr(o.nobs_hr, 24, nd, val=0, dtype=int)
        if ov[o.wind_vars[2]].lread:
            o.lcalm_obs = arr(o.nobs_hr, nl, 24, nd, val=False, dtype=bool)
    if ov[o.wind_vars[2]].lread:
        o.lcalm_obs_hr = arr(nl, 24, nd, val=False, dtype=bool)
    o.nomisshr = arr(nd, 24, val=False, dtype=bool)
    o.losobs = [False] * (nd + 1)
    j = 0
    for ivar in range(1, o.nosvars + 1):
        if ov[ivar].lread and ivar > 5:
            j += 1
            o.read_index[j] = ivar
            if ivar == o.height_var:
                ov[o.height_var].readvar = j
            if ivar == o.wind_vars[1]:
                ov[o.wind_vars[1]].readvar = j
            if ivar == o.wind_vars[2]:
                ov[o.wind_vars[2]].readvar = j
            o.osdata1a[j, :, :, :] = float(ov[ivar].missval)
            if ov[5].lread:
                o.os_subhr_vals[:, j, :, :, :] = float(ov[ivar].missval)
    iday1 = 0
    for y in range(o.osdates[1][1], o.osdates[2][1] + 1):
        leap = leapyr(y)
        imon1 = o.osdates[1][2] if y == o.osdates[1][1] else 1
        imon2 = o.osdates[2][2] if y == o.osdates[2][1] else 12
        for mm in range(imon1, imon2 + 1):
            idy1 = 1
            idy2 = m.days[mm] + (1 if (mm == 2 and leap) else 0)
            if mm == imon1 and y == o.osdates[1][1]:
                idy1 = o.osdates[1][3]
            if mm == imon2 and y == o.osdates[2][1]:
                idy2 = o.osdates[2][3]
            for d in range(idy1, idy2 + 1):
                iday1 += 1
                o.os_date[iday1] = y * 10000 + mm * 100 + d
    t = ahora or _dt.datetime.now()
    E.w(m.msg_unit, formstr1, pid(E), "I60", modnam, "BEGIN:", m.pathid[m.ipath].strip(), "EXTRACTION",
        t.strftime("%Y%m%d"), t.hour, ":", t.minute, ":", t.second)
    if m.istage == 1 and o.osstage1:
        read_os(E)
    else:
        read_ext(E)
    E.w(m.msg_unit, formstr2, pid(E), "I63", modnam, "NUMBER OF EXTRACTED OBSERVATIONS:", o.nos[2])
    E.w(m.msg_unit, formstr2, pid(E), "I64", modnam, "NUMBER OF DUPLICATE OBSERVATIONS:", o.nos[4])
    if ov[5].lread:
        E.w(m.msg_unit, formstr2, pid(E), "I65", modnam, "NUMBER OF SUB-HOURLY OBSERVATIONS NOT USED:",
            o.nos[5])
    if ov[o.height_var].lread:
        E.w(m.msg_unit, formstr2, pid(E), "I66", modnam, "NUMBER OF BAD HEIGHT LEVELS: ", o.nbadhts)
    t = ahora or _dt.datetime.now()
    E.w(m.msg_unit, formstr1, pid(E), "I60", modnam, "END:", m.pathid[m.ipath].strip(), "EXTRACTION",
        t.strftime("%Y%m%d"), t.hour, ":", t.minute, ":", t.second)
    if not o.lbados:
        if not o.luseoshts and ov[o.height_var].lread:
            check_hts(E)
    if not o.lbados:
        if o.nos[2] == 0:
            E.w(m.msg_unit, formstr3, pid(E), "W46", modnam, "NO EXTRACTED DATA BETWEEN", o.osstart, "-",
                o.osend, "; CHECK XDATES")
        else:
            o.os_info = [None]
            for d in range(1, nd + 1):
                o.os_info.append(SimpleOsinfo(o.os_date[d], o.losobs[d],
                                              [None] + [bool(o.nomisshr[d, h]) for h in range(1, 25)]))
            if ov[o.wind_vars[2]].lread and not ov[5].lread and m.istage == 1 and o.osstage1:
                check_wind(E)
            nombres = ("hflux_var", "lflux_var", "ustar_var", "mix_var", "zo_var", "inso_var",
                       "nrad_var", "dt01_var", "vptg_var", "l_var", "wstar_var", "alb_var", "bo_var",
                       "clht_var", "temp_var", "dewpt_var", "cloud_var", "slp_var", "pres_var",
                       "rh_var")
            nombres2 = ("samt_var", "sa_var", "se_var", "sv_var", "sw_var", "su_var", "vv_var",
                        "tsea_var", "sstd_var", "hwav_var", "twav_var", "rdow_var")
            if m.istage == 1 and o.osstage1 and (o.loskeywords[8] or ov[o.temp_var].lread
                                                  or ov[o.wind_vars[1]].lread
                                                  or ov[o.wind_vars[2]].lread):
                i = 0
                j = 0
                o.os_audit_index = [[0, 0, 0] for _ in range(o.nos_audit_vars + 1)]
                o.missvals = [0.0] * (o.nos_audit_vars + 1)
                o.lowbound = [0.0] * (o.nos_audit_vars + 1)
                o.upbound = [0.0] * (o.nos_audit_vars + 1)
                o.os_audit_counts = np.zeros((o.nos_audit_vars + 1, nl + 1, 3 if ov[5].lread else 2, 5),
                                             dtype=int)
                for ivar in range(6, o.nosvars + 1):
                    if ov[ivar].lread:
                        j += 1
                        _asignar_readvar(o, ivar, j, nombres + ("prcp1", "prcp2") + nombres2)
                        if ov[ivar].laudit:
                            if ov[ivar].firstlev > 1:
                                E.w(m.msg_unit, formstr4, pid(E), "Q60", modnam, "FIRST LEVEL FOR",
                                    ov[ivar].varname[0:2], "IS LEVEL", ov[ivar].firstlev)
                            i += 1
                            o.os_audit_index[i][1] = j
                            o.os_audit_index[i][2] = ivar
                            o.missvals[i] = float(ov[ivar].missval)
                            o.lowbound[i] = float(ov[ivar].lowbound) * ov[ivar].conv
                            o.upbound[i] = float(ov[ivar].upbound) * ov[ivar].conv
                if ov[o.temp_var].lread and ov[o.dewpt_var].lread:
                    o.checktempdew = True
            if not o.osstage1 and m.lstage[2]:
                j = 0
                for ivar in range(6, o.nosvars + 1):
                    if ov[ivar].lread:
                        j += 1
                        _asignar_readvar(o, ivar, j, nombres + ("prcp1", "prcp2") + nombres2)
            if m.istage == 1 and o.osstage1 and ov[5].lread:
                avg_hr(E)
            if m.istage == 1 and o.osstage1 and (o.loskeywords[8] or ov[o.temp_var].lread or
                                                  ov[o.wind_vars[1]].lread or ov[o.wind_vars[2]].lread):
                os_audithr(E)
            if ov[o.height_var].readvar == 0 and o.luseoshts:
                o.osdata1 = arr(nv + 1, nl, 24, nd)
                if m.istage == 1 and o.osstage1:
                    o.qaout_vars = [""] * (nv + 2)
                addvar = 1
                for nom in ("hflux_var", "lflux_var", "ustar_var", "mix_var", "zo_var", "inso_var",
                            "nrad_var", "dt01_var", "vptg_var", "l_var", "wstar_var", "clht_var"):
                    _incr(o, getattr(o, nom))
                _incr(o, o.wind_vars[1])
                _incr(o, o.wind_vars[2])
                for nom in ("temp_var", "dewpt_var", "cloud_var", "slp_var", "pres_var", "rh_var",
                            "sa_var", "se_var", "sv_var", "sw_var", "su_var", "vv_var"):
                    _incr(o, getattr(o, nom))
                _incr(o, o.prcp_vars[1])
                _incr(o, o.prcp_vars[2])
                for nom in ("tsea_var", "sstd_var", "hwav_var", "twav_var", "rdow_var"):
                    _incr(o, getattr(o, nom))
            else:
                for nom in ("hflux_var", "lflux_var", "ustar_var", "mix_var", "zo_var", "inso_var",
                            "nrad_var", "dt01_var", "vptg_var", "l_var", "wstar_var", "clht_var",
                            "cloud_var", "slp_var", "pres_var"):
                    _incr(o, getattr(o, nom))
                _incr(o, o.prcp_vars[1])
                _incr(o, o.prcp_vars[2])
                for nom in ("tsea_var", "sstd_var", "hwav_var", "twav_var", "rdow_var"):
                    _incr(o, getattr(o, nom))
                o.osdata1 = arr(nv, nl, 24, nd)
                if m.istage == 1 and o.osstage1:
                    o.qaout_vars = [""] * (nv + 1)
                addvar = 0
            hv = ov[o.height_var]
            if o.luseoshts:
                if m.istage == 1 and o.osstage1:
                    o.qaout_vars[1] = hv.varname
                for ilev in range(1, nl + 1):
                    o.osdata1[1, ilev, :, :] = o.os_heights[ilev]
                    if ilev == 1 and hv.firstlev != 1:
                        hv.firstlev = 1
                    if ilev == nl and hv.nlevels != nl:
                        hv.nlevels = nl
            elif hv.readvar != 0:
                o.osdata1[1, :, :, :] = o.osdata1a[hv.readvar, :, :, :]
                if m.istage == 1 and o.osstage1:
                    o.qaout_vars[1] = hv.varname
            for ivar1 in range(1, nv + 1):
                ri = o.read_index[ivar1]
                if ri == o.height_var:
                    continue
                if ((ri < o.height_var and (hv.readvar != 0 or o.luseoshts)) or
                        (ri > o.height_var and hv.readvar == 0)):
                    o.osdata1[ivar1 + 1, :, :, :] = o.osdata1a[ivar1, :, :, :]
                    if m.istage == 1 and o.osstage1:
                        o.qaout_vars[ivar1 + 1] = ov[ri].varname
                else:
                    o.osdata1[ivar1, :, :, :] = o.osdata1a[ivar1, :, :, :]
                    if m.istage == 1 and o.osstage1:
                        o.qaout_vars[ivar1] = ov[ri].varname
            if m.istage == 1 and o.osstage1 and o.loskeywords[4]:
                header(E, nv + addvar)
                data_form = fwrite("(a,i2,a)", "(i8.8,3x,i2.2,5x,i3,", nv + addvar, "(1x,f12.5))")[0]
                lineas = []
                nw = nv + addvar
                for d in range(1, nd + 1):
                    if o.os_info[d].sobs:
                        for h in range(1, 25):
                            if not o.os_info[d].have_obs[h]:
                                continue
                            for ilev in range(1, nl + 1):
                                lineas.extend(fwrite(data_form, o.os_info[d].osdate, h, ilev,
                                                     *o.osdata1[1:nw + 1, ilev, h, d].tolist()))
                E.units[m.os_qaout_unit].escribir(lineas)
    if ov[o.height_var].readvar > 0 or o.luseoshts:
        ov[o.height_var].readvar = 1
    o.osdata1a = None
    o.ext_index = None
    o.varmap = None
    o.qaout_vars = None
    o.os_date = None
    o.os_subhr_vals = None
    o.obs_minutes = None
    o.losobs = None
    o.lcalm_obs = None
    o.nomisshr = None
    o.missvals = o.upbound = o.lowbound = None
    o.os_format = None
    o.read_index = None


class SimpleOsinfo:
    __slots__ = ("osdate", "sobs", "have_obs")

    def __init__(self, osdate, sobs, have_obs):
        self.osdate = osdate
        self.sobs = sobs
        self.have_obs = have_obs


def _asignar_readvar(o, ivar, j, nombres):
    for nom in nombres:
        if nom == "prcp1":
            if ivar == o.prcp_vars[1]:
                o.osvars[o.prcp_vars[1]].readvar = j
        elif nom == "prcp2":
            if ivar == o.prcp_vars[2]:
                o.osvars[o.prcp_vars[2]].readvar = j
        else:
            k = getattr(o, nom)
            if ivar == k:
                o.osvars[k].readvar = j


def _incr(o, ivar):
    if o.osvars[ivar].lread:
        o.osvars[ivar].readvar += 1


def header(E, nwritevar):
    m, o = E.m, E.os
    f = E.units[m.os_qaout_unit]
    cgmt2lst = fwrite("(i3)", o.osgmt2lst)[0] if o.lgmt2lst else ""
    celev = fwrite("(f10.3)", o.oselev)[0] if o.loselev else ""
    olow_str = "OVERLAND" if o.overland else "OVERWATER"
    if o.oslat < 0.0:
        alat = fwrite("(f7.3,a1)", abs(o.oslat), "S")[0]
    else:
        alat = fwrite("(f7.3,a1)", o.oslat, "N")[0]
    if o.oslon < 0.0:
        alon = fwrite("(f8.3,a1)", abs(o.oslon), "W")[0]
    else:
        alon = fwrite("(f8.3,a1)", o.oslon, "E")[0]
    L = []
    L += fwrite("(2(a))", "AERMET VERSION ", m.versn)
    L += fwrite("(a,a8,2(1x,a10),2(1x,a))", "LOCATION ", fx(o.osid, 8), fx(alat, 10), fx(alon, 10),
                cgmt2lst.strip(), celev.strip())
    L += fwrite("(a)", "FILE TYPE: QAOUT")
    if o.loskeywords[11]:
        L += fwrite("(a,1x,f6.3)", "THRESHOLD", o.threshspeed)
    if o.loskeywords[9]:
        L += fwrite("(a,1x,i1,2(1x,f8.3))", "DELTA_TEMP", o.delta_t_ind, o.osdt_hts[1][1], o.osdt_hts[1][2])
    L += fwrite("(a)", olow_str.strip())
    L += fwrite("(a,i4,2(1x,i2.2),1x,i4,2(1x,i2.2))", "DATES ", o.osdates[1][1], o.osdates[1][2],
                o.osdates[1][3], o.osdates[2][1], o.osdates[2][2], o.osdates[2][3])
    ov = o.osvars
    for ivar in range(6, o.nosvars + 1):
        v = ov[ivar]
        if v.lread and v.luse and v.lmod:
            bndstr = "<=" if v.lincbound else "< "
            L += fwrite("(a,1x,a4,i6,1x,a2,1x,2(1x,i6))", "RANGE", v.varname, v.lowbound, bndstr,
                        v.upbound, v.missval)
    for ivar in range(o.height_var, o.nosvars + 1):
        v = ov[ivar]
        if (v.lread and v.luse) or (ivar == o.height_var and o.luseoshts):
            L += fwrite("(a4,1x,a,1x,2(i3,1x))", v.varname, "FIRST-LAST LEVELS", v.firstlev, v.nlevels)
    header_form = fwrite("(a,i2,a)", "(a,", nwritevar, "(9x,a4))")[0]
    L += fwrite(header_form, "DATE       HR     LEV",
                *[o.qaout_vars[k].strip() for k in range(1, nwritevar + 1)])
    f.escribir(L)


def read_os(E):
    m, o = E.m, E.os
    modnam = fx("READ_OS", 10)
    formstr1 = "(1x,a,1x,a,1x,a,1x,2(a2,a1),a4,1x,a)"
    formstr2 = fmt_msg(E, "a,1x,a20)")
    formstr3 = fmt_msg(E, "a,1x,i6,1x,a,1x,i2,1x,a)")
    formstr5 = fmt_msg(E, "a,1x,a20,1x,a,1x,i2.2)")
    formstr6 = fmt_msg(E, "2(a,1x,i3,1x),a20,1x,a,1x,i2.2)")
    formstr7 = fmt_msg(E, "a,1x,i8,1x,a,1x,i8)")
    formstr8 = fmt_msg(E, "a,1x,i1,1x,a,1x,i1)")
    formstr9 = fmt_msg(E, "2(a,1x,i3,1x),a20)")
    ov = o.osvars
    f = E.units[m.os_data_unit]
    centuries = [None, (o.osstart // 1000000) * 100, (o.osend // 1000000) * 100]
    sv = o.save_read_os
    iread = 1
    eof = 0
    sdate = 0
    crossover = False
    last_year = 0
    icent = 0
    irec1 = 0
    savemin = 0
    imin2 = 0
    savehr = 0
    iday1 = 0
    iyear = imonth = iday = ihr = imin = 0
    lgo = False
    nintvar1 = 5 if ov[5].lread else 4
    intvars = [0] * (nintvar1 + 1)
    # posición de cada variable entre las leídas (ivar >= 6)
    pos_leida = {}
    i = 0
    for ivar in range(6, o.nosvars + 1):
        if ov[ivar].lread:
            i += 1
            pos_leida[ivar] = i
    eps = m.eps
    por_read = {}
    while eof == 0 and not m.lbad and sdate <= o.osend:
        datline = f.leer()
        irec1 += 1
        if datline is None:
            eof = -1
            continue
        datline = datline[:5000]
        # número de enteros y reales de la línea READ iread (no cambia entre registros)
        pr = por_read.get(iread)
        if pr is None:
            nrealvar = 0
            nintvar = 0
            ivar1 = 1
            lstop = False
            while ivar1 <= o.nreadvars and not lstop:
                if o.varmap[iread, ivar1, 1] > 0:
                    if o.varmap[iread, ivar1, 1] > 5:
                        nrealvar += 1
                    else:
                        nintvar += 1
                else:
                    lstop = True
                ivar1 += 1
            reales = []
            for k in range(1, nrealvar + 1):
                svar = int(o.varmap[iread, k + nintvar, 1])
                ilev = int(o.varmap[iread, k + nintvar, 2])
                reales.append((float(ov[svar].missval), ov[svar].conv, pos_leida.get(svar, 0), ilev or 1))
            pr = por_read[iread] = (nintvar, nrealvar, ["i"] * nintvar + ["f"] * nrealvar, reales)
        nintvar, nrealvar, tipos, reales = pr
        if o.os_format[iread].strip() == "FREE":
            vals, iflag, _ = lread(datline, tipos)
        else:
            vals, iflag, _ = fread(o.os_format[iread], datline, tipos)
        for k in range(min(len(vals), nintvar)):
            if vals[k] is not None:
                intvars[k + 1] = vals[k]
        realvars = [None] + [vals[nintvar + k] if nintvar + k < len(vals) else 0.0
                             for k in range(nrealvar)]
        if iflag == 0:
            o.nos[1] += 1
            if nintvar > 0:
                for ivar1 in range(1, nintvar + 1):
                    vm = o.varmap[iread, ivar1, 1]
                    if vm == 1:
                        iday = intvars[ivar1]
                    elif vm == 2:
                        imonth = intvars[ivar1]
                    elif vm == 3:
                        iyear = intvars[ivar1]
                    elif vm == 4:
                        ihr = intvars[ivar1]
                    else:
                        imin = intvars[ivar1]
                if iyear < 100:
                    iyear2 = iyear
                    if iyear < last_year:
                        crossover = True
                        icent += 1
                    if crossover:
                        iyear = iyear + centuries[1] + icent * 100
                    else:
                        iyear = iyear + centuries[1]
                    last_year = iyear2
                if ov[5].lread and imin != 0:
                    ihr, iday, imonth, iyear, sdate, lgo = data_dates(E, ihr, iday, imonth, iyear, -1,
                                                                      o.osstart, o.osend, 51)
                ihr, iday, imonth, iyear, sdate, lgo = data_dates(E, ihr, iday, imonth, iyear, o.osgmt2lst,
                                                                  o.osstart, o.osend, 51)
                if ov[5].lread and (sv["savedate"] != sdate or ihr != savehr):
                    if 0 < imin2 < o.nobs_hr:
                        dhs = fwrite("(a5,1x,i8,1x,a2,1x,i2.2)", "DATE:", sv["savedate"], "HR", savehr)[0]
                        E.w(m.msg_unit, formstr9, pid(E), "W57", modnam, "NUMBER OF OBS/HR", imin2,
                            "IS LESS THAN INPUT OBS/HR", o.nobs_hr, dhs)
                    imin2 = 0
                date_hr_str = fwrite("(a5,1x,i8,1x,a2,1x,i2.2)", "DATE:", sdate, "HR", ihr)[0]
                if ov[5].lread and lgo:
                    imin2 += 1
                    if imin2 > o.nobs_hr:
                        m.lbad = True
                        E.w(m.msg_unit, formstr6, pid(E), "E56", modnam, "NUMBER OF OBS/HR", imin2,
                            "EXCEEDS INPUT OBS/HR", o.nobs_hr, date_hr_str, "MIN", imin)
                        lgo = False
            date_hr_str = fwrite("(a5,1x,i8,1x,a2,1x,i2.2)", "DATE:", sdate, "HR", ihr)[0]
            if lgo:
                if iread == 1:
                    o.nos[2] += 1
                adate = "%08d" % sdate
                if sdate == sv["savedate"]:
                    if iread == 1 and ((ihr == savehr and not ov[5].lread) or
                                       (ihr == savehr and imin == savemin and ov[5].lread)):
                        o.nos[4] += 1
                        if ov[5].lread:
                            E.w(m.msg_unit, formstr5, pid(E), "I62", modnam,
                                "POTENTIAL DUPLICATE OBSERVATION FOR", date_hr_str, "MIN", imin)
                        else:
                            E.w(m.msg_unit, formstr2, pid(E), "I62", modnam,
                                "POTENTIAL DUPLICATE OBSERVATION FOR", date_hr_str)
                    else:
                        o.nos[3] += 1
                        o.nomisshr[iday1, ihr] = True
                else:
                    if sdate < sv["savedate"]:
                        E.w(m.msg_unit, formstr7, pid(E), "W62", modnam, "CURRENT DATE", sdate,
                            "IS PRIOR TO PREVIOUS DATE IN DATA FILE", sv["savedate"])
                    if not m.noprint and (not ov[5].lread or (ov[5].lread and imin2 == 1)):
                        E.w(OUTPUT_UNIT, formstr1, "Stage 1: Extracting", o.dattype[m.ipath - 3],
                            "data for month/day/year", adate[4:6], "/", adate[6:8], "/", adate[0:4], "LST")
                    o.nos[3] = 1
                    iday1 = numdays(o.osstart, sdate)
                    o.nomisshr[iday1, ihr] = True
                    o.losobs[iday1] = True
                if ov[5].lread:
                    o.obs_minutes[imin2, ihr, iday1] = imin
                subhr = ov[5].lread
                for ivar1 in range(1, nrealvar + 1):
                    miss, conv, i, ilev = reales[ivar1 - 1]
                    rv = realvars[ivar1]
                    if abs(rv - miss) > eps:
                        if subhr:
                            o.os_subhr_vals[imin2, i, ilev, ihr, iday1] = rv * conv
                        else:
                            o.osdata1a[i, ilev, ihr, iday1] = rv * conv
            sv["savedate"] = sdate
            savehr = ihr
            if ov[5].lread:
                savemin = imin
        else:
            E.w(m.msg_unit, formstr3, pid(E), "W63", modnam, "ERROR READING DATA LINE: ", irec1,
                " CHECK FORMAT", iread, o.os_format[iread].strip())
            sv["nbad"] += 1
            if sv["nbad"] > 3:
                m.lbad = True
                E.w(m.msg_unit, formstr8, pid(E), "E55", modnam, "NUMBER OF DATA READ ERRORS", sv["nbad"],
                    "EXCEEDS MAXIMUM NUMBER ALLOWED", 3)
        iread += 1
        if iread > o.nread:
            iread = 1
    if not o.lbados and m.lbad:
        o.lbados = True


def findvar(E, ivar):
    o = E.os
    fv = 1
    lfound = False
    while fv < o.nos_audit_vars and not lfound:
        if ivar == o.os_audit_index[fv][2]:
            lfound = True
        else:
            fv += 1
    return fv


def audit(E, rvar, ivar, d, h, imin, ilev, iv, iswitch):
    m, o = E.m, E.os
    v = o.osvars[ivar]
    eps = m.eps
    o.os_audit_counts[iv, ilev, iswitch, 1] += 1
    lowv = upv = writemiss = False
    lb, ub = o.lowbound[iv], o.upbound[iv]
    if abs(rvar - o.missvals[iv]) < eps:
        o.os_audit_counts[iv, ilev, iswitch, 2] += 1
        writemiss = iswitch == 1 and not v.lnomiss
    else:
        if v.lincbound:
            if rvar < lb and abs(rvar - lb) > eps:
                lowv = True
            if rvar > ub and abs(rvar - ub) > eps:
                upv = True
        else:
            if rvar <= lb:
                lowv = True
            if rvar >= ub:
                upv = True
    if writemiss or lowv or upv:
        _audit_mensajes(E, rvar, v, d, h, imin, ilev, iv, iswitch, writemiss, lowv, upv, lb, ub)


def _audit_mensajes(E, rvar, v, d, h, imin, ilev, iv, iswitch, writemiss, lowv, upv, lb, ub):
    """Mensajes de AUDIT (los textos solo se preparan cuando hay algo que escribir)."""
    m, o = E.m, E.os
    modnam = fx("AUDIT", 10)
    if v.varname[2:4] == "NN":
        vname = fwrite("(a2,i2.2)", v.varname[0:2], ilev)[0]
    else:
        vname = v.varname
    formstr1 = fmt_msg(E, "4(a,1x),i2)")
    formstr2 = fmt_msg(E, "3(a,1x),a)")
    formstr3 = fmt_msg(E, "3(a,1x),a2,f9.1,1x,a,f9.1,1x,a,1x,i2)")
    formstr4 = fmt_msg(E, "3(a,1x),a2,f9.1,1x,a,f9.1)")
    if iswitch == 1:
        datestr = "%8d" % o.os_info[d].osdate
        timestr = fwrite("(a,i2)", "HR ", h)[0]
    else:
        dt = o.os_info[d].osdate
        iyear, imonth, iday = dt // 10000, (dt // 100) % 100, dt % 100
        orig_hr, iday, imonth, iyear, orig_date, lgo = data_dates(E, h, iday, imonth, iyear, 1, o.osstart,
                                                                  o.osend, 42)
        datestr = fwrite("(a,i8)", "ORIGINAL DATE ", orig_date)[0]
        timestr = fwrite("(a,i2.2,1x,a,i2.2)", "HR ", orig_hr, "MINUTE ", imin)[0]
    lstr2, ustr2 = ("<", ">") if v.lincbound else ("<=", ">=")
    writelev = v.nlevels != 0
    if writemiss:
        if writelev:
            E.w(m.msg_unit, formstr1, pid(E), "Q61", modnam, datestr.strip(), timestr.strip(), vname.strip(),
                "MISSING LEVEL", ilev)
        else:
            E.w(m.msg_unit, formstr2, pid(E), "Q61", modnam, datestr.strip(), timestr.strip(), vname.strip(),
                "MISSING")
    if lowv:
        o.os_audit_counts[iv, ilev, iswitch, 3] += 1
        if rvar < lb - 0.5 * abs(ub - lb):
            lstr1 = fwrite("(a,1x,a)", "MUCH", lstr2)[0]
        else:
            lstr1 = lstr2
        if writelev:
            E.w(m.msg_unit, formstr3, pid(E), "Q62", modnam, datestr.strip(), timestr.strip(), vname.strip(),
                "LB", rvar, lstr1.strip(), lb, "LEVEL", ilev)
        else:
            E.w(m.msg_unit, formstr4, pid(E), "Q62", modnam, datestr.strip(), timestr.strip(), vname.strip(),
                "LB", rvar, lstr1.strip(), lb)
    if upv:
        o.os_audit_counts[iv, ilev, iswitch, 4] += 1
        if rvar > ub + 0.5 * abs(ub - lb):
            ustr1 = fwrite("(a,1x,a)", "MUCH", ustr2)[0]
        else:
            ustr1 = ustr2
        if writelev:
            E.w(m.msg_unit, formstr3, pid(E), "Q63", modnam, datestr.strip(), timestr.strip(), vname.strip(),
                "UB", rvar, ustr1.strip(), ub, "LEVEL", ilev)
        else:
            E.w(m.msg_unit, formstr4, pid(E), "Q63", modnam, datestr.strip(), timestr.strip(), vname.strip(),
                "UB", rvar, ustr1.strip(), ub)


def avg_hr(E):
    m, o = E.m, E.os
    modnam = fx("AVG_HR", 10)
    ov = o.osvars
    formstr1 = "(1x,a,1x,a,1x,a,1x,2(a2,a1),a4,1x,a)"
    formstr2 = fmt_msg(E, "i8,1x,a,1x,i2.2,1x,a,1x,2(a,1x,i2,1x),a)")
    formstr3 = fmt_msg(E, "i8,1x,a,1x,i2.2,1x,a,1x,3(a,1x,i2,1x),a)")
    eps = m.eps
    iswitch = 2
    icalms = 0
    nobs_hr = o.nobs_hr
    S = o.os_subhr_vals
    A = o.osdata1a
    for d in range(1, o.nosdays + 1):
        if not o.os_info[d].sobs:
            continue
        adate = "%08d" % o.os_info[d].osdate
        if not m.noprint:
            E.w(OUTPUT_UNIT, formstr1, "Stage 1: Averaging sub-hourly", o.dattype[m.ipath - 3],
                "data for month/day/year", adate[4:6], "/", adate[6:8], "/", adate[0:4], "LST")
        for h in range(1, 25):
            if not o.os_info[d].have_obs[h]:
                continue
            for ilev in range(1, o.nlevel + 1):
                for ivar1 in range(1, o.nvars + 1):
                    ivar = o.read_index[ivar1]
                    v = ov[ivar]
                    if ((ilev > v.nlevels and v.nlevels > 0) or (ilev > 1 and v.nlevels == 0) or
                            v.firstlev > ilev or (o.std_vars[1] <= ivar <= o.std_vars[2]) or
                            ivar == o.wind_vars[1] or ivar == o.wind_vars[2]):
                        continue
                    writelev = v.nlevels != 0
                    if v.varname[2:4] == "NN":
                        vname = fwrite("(a2,i2.2)", v.varname[0:2], ilev)[0]
                    else:
                        vname = v.varname
                    hrval = 0.0
                    nobs_hr1 = nobs_hr
                    for imin1 in range(1, nobs_hr + 1):
                        imin = int(o.obs_minutes[imin1, h, d])
                        if v.laudit:
                            iv = findvar(E, ivar)
                            audit(E, float(S[imin1, ivar1, ilev, h, d]), ivar, d, h, imin, ilev, iv, iswitch)
                        val = float(S[imin1, ivar1, ilev, h, d])
                        if abs(val - float(v.missval)) < eps:
                            nobs_hr1 -= 1
                        else:
                            hrval = hrval + val
                        if o.checktempdew:
                            tr = ov[o.temp_var].readvar
                            if (ivar1 == ov[o.dewpt_var].readvar and abs(val - float(v.missval)) >= eps and
                                    abs(float(S[imin1, tr, ilev, h, d]) - float(ov[o.temp_var].missval)) >= eps
                                    and float(S[imin1, tr, ilev, h, d]) < val):
                                o.os_tempstat[iswitch] += 1
                    if nobs_hr1 < o.min_obs:
                        if not writelev:
                            if (ivar == o.prcp_vars[1] or ivar == o.prcp_vars[2] or
                                    (ivar == o.samt_var and nobs_hr1 > 0)):
                                E.w(m.msg_unit, formstr2, pid(E), "Q70", modnam, o.os_info[d].osdate, "HR", h,
                                    vname.strip(), "# OF MINUTES", nobs_hr1, "<", o.min_obs, "MINUTES")
                                A[ivar1, ilev, h, d] = hrval
                            else:
                                E.w(m.msg_unit, formstr2, pid(E), "Q68", modnam, o.os_info[d].osdate, "HR", h,
                                    vname.strip(), "# OF MINUTES", nobs_hr1, "<", o.min_obs,
                                    "MINUTES FOR AVG; SET TO MISSING")
                        else:
                            E.w(m.msg_unit, formstr3, pid(E), "Q68", modnam, o.os_info[d].osdate, "HR", h,
                                vname.strip(), "# OF MINUTES", nobs_hr1, "<", o.min_obs,
                                "MINUTES FOR AVG LEVEL", ilev, "SET TO MISSING")
                    else:
                        if ivar == o.prcp_vars[1] or ivar == o.prcp_vars[2] or ivar == o.samt_var:
                            A[ivar1, ilev, h, d] = hrval
                        else:
                            A[ivar1, ilev, h, d] = hrval / float(nobs_hr1)
                havedir = False
                havespeed = False
                if ov[o.wind_vars[2]].lread:
                    ivar = o.wind_vars[2]
                    v = ov[ivar]
                    ivar1 = v.readvar
                    nobs_hr1 = nobs_hr
                    hrval = 0.0
                    icalms = 0
                    if v.firstlev <= ilev <= v.nlevels:
                        havespeed = True
                        vname = fwrite("(a2,i2.2)", v.varname[0:2], ilev)[0]
                        for imin1 in range(1, nobs_hr + 1):
                            imin = int(o.obs_minutes[imin1, h, d])
                            iv = findvar(E, ivar)
                            audit(E, float(S[imin1, ivar1, ilev, h, d]), ivar, d, h, imin, ilev, iv, iswitch)
                            val = float(S[imin1, ivar1, ilev, h, d])
                            if abs(val - float(v.missval)) > eps:
                                if val < o.threshspeed:
                                    o.os_windstats[iswitch][1] += 1
                                    o.lcalm_obs[imin1, ilev, h, d] = True
                                    icalms += 1
                                    S[imin1, ivar1, ilev, h, d] = o.threshspeed / 2.0
                                hrval = hrval + float(S[imin1, ivar1, ilev, h, d])
                            else:
                                nobs_hr1 -= 1
                        if icalms >= o.min_obs:
                            A[ivar1, ilev, h, d] = hrval / float(nobs_hr1)
                        elif nobs_hr1 < o.min_obs:
                            E.w(m.msg_unit, formstr3, pid(E), "Q68", modnam, o.os_info[d].osdate, "HR", h,
                                vname.strip(), "# OF MINUTES", nobs_hr1, "<", o.min_obs,
                                "MINUTES FOR AVG LEVEL", ilev, "SET TO MISSING")
                        else:
                            if not o.lvector:
                                A[ivar1, ilev, h, d] = hrval / float(nobs_hr1)
                        if (float(A[ivar1, ilev, h, d]) < o.threshspeed and
                                abs(float(A[ivar1, ilev, h, d]) - float(v.missval)) > eps):
                            o.lcalm_obs_hr[ilev, h, d] = True
                if ov[o.wind_vars[1]].lread:
                    ivar = o.wind_vars[1]
                    v = ov[ivar]
                    ivar1 = v.readvar
                    nobs_hr1 = nobs_hr
                    hrval = 0.0
                    dircount = 0
                    o.xdir = o.ydir = o.dirsum = 0.0
                    if o.lcalm_obs_hr[ilev, h, d]:
                        A[ivar1, ilev, h, d] = 0.0
                    if v.firstlev <= ilev <= v.nlevels:
                        havedir = True
                        vname = fwrite("(a2,i2.2)", v.varname[0:2], ilev)[0]
                        for imin1 in range(1, nobs_hr + 1):
                            imin = int(o.obs_minutes[imin1, h, d])
                            if o.lcalm_obs[imin1, ilev, h, d]:
                                S[imin1, ivar1, ilev, h, d] = float(v.missval)
                            iv = findvar(E, ivar)
                            audit(E, float(S[imin1, ivar1, ilev, h, d]), ivar, d, h, imin, ilev, iv, iswitch)
                            if abs(float(S[imin1, ivar1, ilev, h, d]) - float(v.missval)) < eps:
                                nobs_hr1 -= 1
                            else:
                                dircount += 1
                                calc_wind(E, dircount, d, h, imin1, ilev)
                        if nobs_hr1 < o.min_obs:
                            if icalms >= o.min_obs:
                                A[ov[o.wind_vars[2]].readvar, ilev, h, d] = 0.0
                                o.lcalm_obs_hr[ilev, h, d] = True
                                E.w(m.msg_unit, formstr3, pid(E), "Q65", modnam, o.os_info[d].osdate, "HR", h,
                                    vname.strip(), " # OF MINUTES", nobs_hr - icalms, "<", o.min_obs,
                                    "MINUTES FOR AVG LEVEL", ilev, "RESET TO CALM (0)")
                                A[ivar1, ilev, h, d] = 0.0
                            else:
                                E.w(m.msg_unit, formstr3, pid(E), "Q66", modnam, o.os_info[d].osdate, "HR", h,
                                    vname.strip(), " # OF MINUTES", nobs_hr1, "<", o.min_obs,
                                    "MINUTES FOR AVG LEVEL", ilev, "SET TO MISSING")
                        else:
                            avg_wind(E, dircount, d, h, ilev)
                if (ov[o.wind_vars[1]].lread and ov[o.wind_vars[2]].lread and
                        ((havespeed and not havedir) or (not havespeed and havedir))):
                    if havespeed and not havedir:
                        o.os_windstats[iswitch][3] += 1
                    else:
                        o.os_windstats[iswitch][2] += 1
                for ivar in range(o.std_vars[1], o.std_vars[2] + 1):
                    v = ov[ivar]
                    if not v.lread:
                        continue
                    ivar1 = 1
                    lfound = False
                    nobs_hr1 = nobs_hr
                    hrval = 0.0
                    while ivar1 <= o.nvars and not lfound:
                        if ivar == o.read_index[ivar1]:
                            lfound = True
                        else:
                            ivar1 += 1
                    if ilev > v.nlevels or v.firstlev > ilev:
                        continue
                    vname = fwrite("(a2,i2.2)", v.varname[0:2], ilev)[0]
                    for imin1 in range(1, nobs_hr + 1):
                        imin = int(o.obs_minutes[imin1, h, d])
                        if o.lcalm_obs[imin1, ilev, h, d]:
                            S[imin1, ivar1, ilev, h, d] = float(v.missval)
                        if v.laudit:
                            iv = findvar(E, ivar)
                            audit(E, float(S[imin1, ivar1, ilev, h, d]), ivar, d, h, imin, ilev, iv, iswitch)
                        val = float(S[imin1, ivar1, ilev, h, d])
                        if abs(val - float(v.missval)) < eps:
                            nobs_hr1 -= 1
                        else:
                            hrval = hrval + val * val
                    if nobs_hr1 < o.min_obs:
                        E.w(m.msg_unit, formstr3, pid(E), "Q68", modnam, o.os_info[d].osdate, "HR", h,
                            vname.strip(), " # OF MINUTES", nobs_hr1, "<", o.min_obs,
                            "MINUTES FOR AVG LEVEL", ilev, "SET TO MISSING")
                    else:
                        A[ivar1, ilev, h, d] = math.sqrt(hrval / float(nobs_hr1))


def calc_wind(E, dircount, d, h, imin1, ilev):
    m, o = E.m, E.os
    ov = o.osvars
    ivar1 = ov[o.wind_vars[1]].readvar
    S = o.os_subhr_vals
    if o.lvector:
        ws = float(S[imin1, ov[o.wind_vars[2]].readvar, ilev, h, d])
        wd = float(S[imin1, ivar1, ilev, h, d])
        xd = -ws * math.sin(wd * m.d2r)
        o.xdir = o.xdir + xd
        yd = -ws * math.cos(wd * m.d2r)
        o.ydir = o.ydir + yd
    else:
        val = float(S[imin1, ivar1, ilev, h, d])
        if dircount == 1:
            o.dirsum = val
            o.save_calc_wind_lastdir = val
        else:
            diff = val - o.save_calc_wind_lastdir
            if diff < -180.0:
                corr = 360.0
            elif diff > 180.0:
                corr = -360.0
            else:
                corr = 0.0
            o.save_calc_wind_lastdir = o.save_calc_wind_lastdir + diff + corr
            o.dirsum = o.dirsum + o.save_calc_wind_lastdir


def avg_wind(E, dircount, d, h, ilev):
    m, o = E.m, E.os
    ov = o.osvars
    ivar1 = ov[o.wind_vars[1]].readvar
    A = o.osdata1a
    corr = 0.0
    if o.lvector:
        xd = o.xdir / float(dircount)
        yd = o.ydir / float(dircount)
        if (xd > 0.0 and yd > 0.0) or (xd < 0.0 and yd > 0.0):
            corr = 180.0
        if xd < 0.0 and yd < 0.0:
            corr = 0.0
        if xd > 0.0 and yd < 0.0:
            corr = 360.0
        if xd == 0:
            A[ivar1, ilev, h, d] = 360.0 if yd > 0.0 else 180.0
        if yd == 0:
            A[ivar1, ilev, h, d] = 270.0 if xd > 0.0 else 90.0
        if xd != 0.0 and yd != 0.0:
            A[ivar1, ilev, h, d] = math.atan(xd / yd) / m.d2r + corr
        A[ov[o.wind_vars[2]].readvar, ilev, h, d] = math.sqrt((xd * xd) + (yd * yd))
    else:
        dir1 = o.dirsum / float(dircount)
        while dir1 > 360.0 or dir1 < 0.0:
            if dir1 > 360.0:
                dir1 = dir1 - 360.0
            elif dir1 < 0.0:
                dir1 = dir1 + 360.0
        A[ivar1, ilev, h, d] = dir1
    val = float(A[ivar1, ilev, h, d])
    if 0.0 <= val < 0.05:
        A[ivar1, ilev, h, d] = 360.0
    elif val < 0.0:
        A[ivar1, ilev, h, d] = 360.0 + val
    elif val > 360.0:
        A[ivar1, ilev, h, d] = val - 360.0


def check_wind(E):
    m, o = E.m, E.os
    modnam = fx("CHECK_WIND", 10)
    ov = o.osvars
    formstr = fmt_msg(E, "i8,1x,a,1x,i2.2,1x,a,1x,f4.2,1x,a,1x,i2)")
    eps = m.eps
    iswitch = 1
    A = o.osdata1a
    wsr = ov[o.wind_vars[2]].readvar
    wdr = ov[o.wind_vars[1]].readvar
    if (A[wsr, 1:, 1:, 1:].min() < o.threshspeed or
            (A[wdr, 1:, 1:, 1:].min() < 0.05 and A[wsr, 1:, 1:, 1:].min() >= o.threshspeed)):
        for d in range(1, o.nosdays + 1):
            if not o.os_info[d].sobs:
                continue
            for h in range(1, 25):
                if not o.os_info[d].have_obs[h]:
                    continue
                for ilev in range(1, o.nlevel + 1):
                    havespeed = False
                    havedir = False
                    ws, wd = ov[o.wind_vars[2]], ov[o.wind_vars[1]]
                    if ws.firstlev <= ilev <= ws.nlevels:
                        havespeed = True
                        val = float(A[wsr, ilev, h, d])
                        if 0.0 <= val < o.threshspeed and abs(val - float(ws.missval)) > eps:
                            o.os_windstats[iswitch][1] += 1
                            A[wsr, ilev, h, d] = o.threshspeed / 2.0
                            o.lcalm_obs_hr[ilev, h, d] = True
                            E.w(m.msg_unit, formstr, pid(E), "Q64", modnam, o.os_info[d].osdate, "HR", h,
                                "WIND SPEED <", o.threshspeed, "LEVEL", ilev)
                    if wd.lread and wd.firstlev <= ilev <= ws.nlevels:
                        havedir = True
                        if o.lcalm_obs_hr[ilev, h, d]:
                            A[wdr, ilev, h, d] = float(wd.missval)
                        else:
                            val = float(A[wdr, ilev, h, d])
                            if abs(val - float(wd.missval)) > eps:
                                if 0.0 <= val <= 0.05:
                                    A[wdr, ilev, h, d] = 360.0
                                elif val < 0.0:
                                    A[wdr, ilev, h, d] = val + 360.0
                                elif val > 360.0:
                                    A[wdr, ilev, h, d] = val - 360.0
                    if (wd.lread and ws.lread and ((havespeed and not havedir) or
                                                   (not havespeed and havedir))):
                        if havespeed and not havedir:
                            o.os_windstats[iswitch][3] += 1
                        else:
                            o.os_windstats[iswitch][2] += 1
                    for ivar in range(o.std_vars[1], o.std_vars[2] + 1):
                        if not ov[ivar].lread:
                            continue
                        if o.lcalm_obs_hr[ilev, h, d]:
                            ivar1 = 1
                            lfound = False
                            while ivar1 <= o.nvars and not lfound:
                                if ivar == o.read_index[ivar1]:
                                    lfound = True
                                else:
                                    ivar1 += 1
                            A[ivar1, ilev, h, d] = float(ov[ivar].missval)


def os_audithr(E):
    m, o = E.m, E.os
    modnam = fx("OS_AUDITHR", 10)
    ov = o.osvars
    formstr1 = "(1x,a,1x,a,1x,a,1x,2(a2,a1),a4,1x,a)"
    formstr2 = fmt_msg(E, "i8,1x,a,1x,i2.2,1x,a,1x,i2)")
    iswitch = 1
    A = o.osdata1a
    # variables auditadas en cada nivel (no depende de la hora)
    por_nivel = {}
    for ilev in range(1, o.nlevel + 1):
        lst = []
        for iv in range(1, o.nos_audit_vars + 1):
            ivar1 = o.os_audit_index[iv][1]
            ivar = o.os_audit_index[iv][2]
            v = ov[ivar]
            if ((ilev > v.nlevels and v.nlevels > 0) or (ilev > 1 and v.nlevels == 0) or
                    ilev < v.firstlev):
                continue
            lst.append((iv, ivar1, ivar))
        por_nivel[ilev] = lst
    if o.checktempdew:
        itt, idp = ov[o.temp_var].readvar, ov[o.dewpt_var].readvar
    for d in range(1, o.nosdays + 1):
        if not o.os_info[d].sobs:
            continue
        adate = "%08d" % o.os_info[d].osdate
        if not m.noprint:
            E.w(OUTPUT_UNIT, formstr1, "Stage 1: QA'ing", o.dattype[m.ipath - 3], "data for month/day/year",
                adate[4:6], "/", adate[6:8], "/", adate[0:4], "LST")
        for h in range(1, 25):
            if not o.os_info[d].have_obs[h]:
                continue
            for ilev in range(1, o.nlevel + 1):
                col = A[:, ilev, h, d].tolist()
                for iv, ivar1, ivar in por_nivel[ilev]:
                    audit(E, col[ivar1], ivar, d, h, 0, ilev, iv, iswitch)
                if o.checktempdew:
                    if col[itt] < col[idp]:
                        o.os_tempstat[iswitch] += 1
                        E.w(m.msg_unit, formstr2, pid(E), "Q67", modnam, o.os_info[d].osdate, "HR", h,
                            "TT < DP LEVEL", ilev)


def read_ext(E):
    m, o = E.m, E.os
    modnam = fx("READ_EXT", 10)
    formstr1 = "(1x,a,1x,i1,3(a,1x),2(a2,a1),a4,1x,a)"
    formstr2 = fmt_msg(E, "a,1x,i8,1x,a,1x,i2.2)")
    formstr3 = fmt_msg(E, "a,1x,i6)")
    ov = o.osvars
    f = E.units[m.os_qaout_unit]
    m.lbad = False
    iline = 0
    ldata = False
    iday1 = 0
    savehr = 0
    savelev = 0
    sv = o.save_read_ext
    eps = m.eps
    previos = [" " * 8, 0, 0] + [0.0] * o.nvars   # un valor nulo deja el de la línea anterior
    pos_leida = {}
    for k in range(1, o.nvars + 1):
        pos_leida.setdefault(o.read_index[k], k)
    # cada variable del fichero va a una posición de osdata1a; si dos van a la misma, queda la
    # última (como en el bucle del original), y la calma se comprueba con cada valor de viento leído
    destino = {}
    for ivar1 in range(1, o.nvars + 1):
        destino[pos_leida.get(o.ext_index[ivar1], o.nvars + 1)] = ivar1
    dst = np.array(list(destino.keys()), dtype=np.intp)
    src = [2 + ivar1 for ivar1 in destino.values()]
    viento = [2 + ivar1 for ivar1 in range(1, o.nvars + 1) if o.ext_index[ivar1] == o.wind_vars[2]]
    miss_ws = float(ov[o.wind_vars[2]].missval)
    tipos = [("a", 8), "i", "i"] + ["f"] * o.nvars
    while not m.lbad:
        raw = f.leer()
        if raw is None:
            break
        L = raw[:m.linelen]
        iline += 1
        if not ldata:
            L = L.upper()
        if "DATE       HR     LEV" in L:
            ldata = True
        if ldata and "DATE       HR     LEV" not in L:
            v, iflag1, _ = lread(L, tipos, previos)
            if iflag1 == 0:
                previos = v
                adate = v[0]
                ihr = v[1]
                ilev = v[2]
                o.nos[1] += 1
                dv, io, _ = fread("(i4,2(i2))", adate, ["i", "i", "i"])
                iyear, imonth, iday = dv
                ihr, iday, imonth, iyear, sdate, lgo = data_dates(E, ihr, iday, imonth, iyear, o.osgmt2lst,
                                                                  o.osstart, o.osend, 51)
                if lgo:
                    if ilev == 1:
                        if sdate != sv["savedate"]:
                            iday1 += 1
                        o.nos[2] += 1
                    o.losobs[iday1] = True
                    if sdate == sv["savedate"]:
                        if ihr == savehr and ilev == savelev:
                            o.nos[4] += 1
                            E.w(m.msg_unit, formstr2, pid(E), "I62", modnam,
                                "POTENTIAL DUPLICATE OBSERVATION FOR DATE:", sdate, "HR", ihr)
                        else:
                            o.nos[3] += 1
                            o.nomisshr[iday1, ihr] = True
                    else:
                        if not m.noprint:
                            E.w(OUTPUT_UNIT, formstr1, "Stage", m.istage, ": Extracting", o.dattype[m.ipath - 3],
                                "data for month/day/year", adate[4:6], "/", adate[6:8], "/", adate[0:4], "LST")
                        o.nos[3] = 1
                        iday1 = numdays(o.osstart, sdate)
                        o.nomisshr[iday1, ihr] = True
                    o.osdata1a[dst, ilev, ihr, iday1] = [v[k] for k in src]
                    for k in viento:
                        if v[k] < o.threshspeed and abs(v[k] - miss_ws) > eps:
                            o.lcalm_obs_hr[ilev, ihr, iday1] = True
                savehr = ihr
                sv["savedate"] = sdate
                savelev = ilev
            else:
                m.lbad = True
                E.w(m.msg_unit, formstr3, pid(E), "E55", modnam, "ERROR READING DATA LINE:", iline)
    if m.lbad:
        o.lbados = True


def check_hts(E):
    m, o = E.m, E.os
    modnam = fx("CHECK_HTS", 10)
    ov = o.osvars
    formstr1 = fmt_msg(E, "a,1x,i8,1x,a,2(1x,a,1x,i2,1x,f8.3),1x,a)")
    formstr2 = fmt_msg(E, "a)")
    formstr3 = fmt_msg(E, "a,1x,i3,1x,a)")
    eps = m.eps
    hv = ov[o.height_var]
    htvar = hv.readvar
    ivar = o.height_var + 1
    lmatch = True
    if hv.firstlev != 1:
        E.w(m.msg_unit, formstr3, pid(E), "E58", modnam, "FIRST HT LEVEL", hv.firstlev, "IS NOT EQUAL TO 1")
        m.lbad = True
    else:
        while ivar <= o.nosvars and lmatch:
            if hv.nlevels < ov[ivar].nlevels:
                lmatch = False
            ivar += 1
        if not lmatch:
            E.w(m.msg_unit, formstr3, pid(E), "E58", modnam, "LAST HT LEVEL", hv.nlevels,
                "IS LESS THAN ONE OF THE OTHER MULTI-LEVEL VARIABLES")
            m.lbad = True
    if not m.lbad and hv.lread and o.nos[2] > 0:
        for d in range(1, o.nosdays + 1):
            if not o.losobs[d]:
                continue
            for h in range(1, 25):
                if not o.nomisshr[d, h]:
                    continue
                for ilev in range(2, o.nlevel + 1):
                    if ilev < hv.firstlev or ilev > hv.nlevels:
                        continue
                    if ov[5].lread:
                        for imin1 in range(1, o.nobs_hr + 1):
                            a = float(o.os_subhr_vals[imin1, htvar, ilev, h, d])
                            b = float(o.os_subhr_vals[imin1, htvar, ilev - 1, h, d])
                            if abs(a - float(hv.missval)) > eps and a <= b:
                                o.nbadhts += 1
                                m.lbad = True
                                if o.nbadhts <= 100:
                                    imin = int(o.obs_minutes[imin1, h, d])
                                    timestr = fwrite("(a2,1x,i2.2,1x,a3,1x,i2.2)", "HR", h, "MIN", imin)[0]
                                    E.w(m.msg_unit, formstr1, pid(E), "E58", modnam, "DATE", o.os_date[d],
                                        timestr.strip(), "HT LEVEL", ilev, a, "M <=  HT LEVEL ", ilev - 1, b, "M")
                                elif o.nbadhts == 101:
                                    E.w(m.msg_unit, formstr2, pid(E), "W60", modnam,
                                        "REACHED LIMIT OF BAD HEIGHT CHECKS")
                    else:
                        a = float(o.osdata1a[htvar, ilev, h, d])
                        b = float(o.osdata1a[htvar, ilev - 1, h, d])
                        if abs(a - float(hv.missval)) > eps and a <= b:
                            o.nbadhts += 1
                            m.lbad = True
                            if o.nbadhts <= 100:
                                timestr = fwrite("(a2,1x,i2.2)", "HR", h)[0]
                                E.w(m.msg_unit, formstr1, pid(E), "E58", modnam, "DATE", o.os_date[d],
                                    timestr.strip(), "HT LEVEL", ilev, a, "M <=  HT LEVEL ", ilev - 1, b, "M")
                            elif o.nbadhts == 101:
                                E.w(m.msg_unit, formstr2, pid(E), "W60", modnam, "REACHED LIMIT OF BAD HEIGHT CHECKS")
    if m.lbad:
        o.lbados = True
