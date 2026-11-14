# -*- coding: utf-8 -*-
"""Traducción de AERMET 26135 (US EPA, dominio público): módulo PBL, parte de control.

Vía METPREP del fichero de control (pbl_path, year_str, sstdepth, zigust, zimin, vptg_def,
mol_min, methods, up_window), comprobaciones de la etapa 2 (pbl_test) y lectura de las
características de superficie (aersurf, surf_years, freq_sec, site_char, sectors)."""
from .comun import (checkfile, dataline, fmt_msg, getdates, getfields, getloc, getunit, pid)
from .estado import OUTPUT_UNIT
from .formato import ch, fread, fwrite, fx, lread, sub


class NoTraducido(Exception):
    """Opción del original fuera del alcance de la traducción."""


def pbl_path(E):
    from . import obs_superficie
    m, p = E.m, E.pb
    modnam = fx("PBL_PATH", 10)
    formstr1 = fmt_msg(E, "a,1x,a)")
    formstr2 = fmt_msg(E, "i3,2(1x,a))")
    formstr3 = fmt_msg(E, "2(a,1x),a)")
    form1 = "(a%3d)" % m.flength
    getunit(E)
    m.lbad = False
    ikey = m.ikey
    if ikey == 0:
        p.lpblkeywords = [False] * (p.npblkeys + 1)
        p.litems = [False] * 10
        p.lactions = [False] * 32
        return
    kw = m.keywrd[ikey].strip()
    i = m.inpline1.find(kw) + 1
    i1 = len(kw)
    if (ikey in (4, 9, 10) or 18 <= ikey <= 24 or 28 <= ikey <= 31 or 33 <= ikey <= 35 or ikey == 26
            or ikey >= 37):
        if ikey == 4:
            jj = 18
        elif ikey <= 10:
            jj = ikey - 8
        elif 18 <= ikey <= 24:
            jj = ikey - 15
        elif 28 <= ikey <= 31:
            jj = ikey - 17
        elif 33 <= ikey <= 35:
            jj = ikey - 18
        elif 37 <= ikey < 50:
            jj = ikey - 18
        elif ikey == 50:
            jj = ikey - 26
        else:
            jj = ikey - 16
        if 18 <= ikey <= 20 or ikey == 33:
            p.save_pbl_path_isite = 1
        if 29 <= ikey <= 31 or ikey == 34:
            p.save_pbl_path_isite = 2
        isite = p.save_pbl_path_isite
        lk = p.lpblkeywords
        while len(lk) <= jj:
            lk.append(False)
        if not lk[jj]:
            lk[jj] = True
        else:
            if (ikey != 4 and ikey <= 10) or ikey in (21, 22, 24, 26) or ikey >= 37:
                E.w(m.writeunit, formstr1, pid(E), "E03", modnam, "DUPLICATE ENTRY OF KEYWORD:", kw)
                m.lbad = True
                return
    else:
        E.w(m.writeunit, formstr1, pid(E), "E01", modnam, "INVALID KEYWORD:", kw)
        m.lbad = True
        return

    def mal_campos():
        E.w(m.writeunit, formstr2, pid(E), "E03", modnam, m.nfield,
            "IS AN INVALID NUMBER OF FIELDS FOR KEYWORD", kw)
        m.lbad = True

    if not hasattr(p, "save_pbl_path_yrstr"):
        p.save_pbl_path_yrstr = "-9"
    if ikey == 9:
        if m.nfield not in (3, 4, 7, 8):
            mal_campos()
        else:
            p.pblstart, p.pblend, p.pbldates = getdates(E, i + i1)
    elif ikey == 10:
        if m.nfield < 4 or m.nfield > 6:
            mal_campos()
        else:
            if m.nfield == 6:
                E.w(m.writeunit, formstr3, pid(E), "W70", modnam, "EXTRA FIELD FOR KEYWORD", kw,
                    "IGNORING EXTRA FIELD")
            r = getloc(E, i + i1, p.lgmt2lst, p.lelev)
            p.pblid = r["stid"]
            p.pbllat, p.pbllon, p.pblgmt2lst = r["lat"], r["lon"], r["gmt2lst"]
            p.lgmt2lst, p.lelev = r["lgmt2lst"], r["lelev"]
            # pblelev es aquí una variable LOCAL de pbl_path: el pblelev del módulo no cambia
    elif ikey == 18 or ikey == 29:
        if m.nfield < 3:
            mal_campos()
        else:
            if isite == 1:
                if m.sfc_charfile1 is None:
                    m.sfc_charfile1 = [None] + [""] * 20
                    p.yrstr1 = [None] + [""] * 20
                p.nsc_files1 += 1
                m.sfc_charfile1[p.nsc_files1] = m.inpfile
                if m.nfield > 3:
                    p.yrstr1[p.nsc_files1] = year_str(E, i1)
                else:
                    p.yrstr1[p.nsc_files1] = p.save_pbl_path_yrstr
            else:
                if m.sfc_charfile2 is None:
                    m.sfc_charfile2 = [None] + [""] * 20
                    p.yrstr2 = [None] + [""] * 20
                p.nsc_files2 += 1
                m.sfc_charfile2[p.nsc_files2] = m.inpfile
                if m.nfield > 3:
                    p.yrstr2[p.nsc_files2] = year_str(E, i1)
                else:
                    p.yrstr2[p.nsc_files2] = p.save_pbl_path_yrstr
    elif ikey == 19 or ikey == 30:
        jj = ikey - 15 if ikey == 19 else ikey - 17
        if m.nfield != 6:
            mal_campos()
        elif not p.lpblkeywords[jj - 1]:
            E.w(m.writeunit, formstr3, pid(E), "E76", modnam, kw, "HAS BEEN LISTED BEFORE",
                m.keywrd[ikey - 1].strip())
            m.lbad = True
    elif ikey == 20 or ikey == 31:
        jj = ikey - 15 if ikey == 20 else ikey - 17
        if m.nfield != 4:
            mal_campos()
        elif not p.lpblkeywords[jj - 2]:
            E.w(m.writeunit, formstr3, pid(E), "E76", modnam, kw, "HAS BEEN LISTED BEFORE",
                m.keywrd[ikey - 2].strip())
            m.lbad = True
    elif ikey == 21:
        if m.nfield != 2:
            mal_campos()
        else:
            m.sfc_outfile = fread(form1, sub(m.inpline, i + i1 + 1, m.ilen), [("a", m.flength)])[0][0]
            m.sfc_outfile, lgood = checkfile(E, m.sfc_out_unit, m.sfc_outfile, 4)
    elif ikey == 22:
        pass
    elif ikey == 23:
        if m.nfield != 3:
            mal_campos()
        else:
            methods(E, i + i1)
    elif ikey == 24:
        if m.nfield != 3:
            mal_campos()
        else:
            up_window(E, i + i1)
    elif ikey == 26:
        if m.nfield != 2:
            mal_campos()
        else:
            m.pfl_outfile = fread(form1, sub(m.inpline, i + i1 + 1, m.ilen), [("a", m.flength)])[0][0]
            m.pfl_outfile, lgood = checkfile(E, m.pfl_out_unit, m.pfl_outfile, 4)
    elif ikey == 28:
        if m.nfield != 3:
            mal_campos()
        else:
            obs_superficie.nws_hgts(E, i1)
    elif ikey <= 34 and ikey not in (4, 22, 25):
        if m.nfield < 2:
            mal_campos()
        else:
            isite = ikey - 32
            if isite == 1:
                if m.sfc_charfile1 is None:
                    m.sfc_charfile1 = [None] + [""] * 20
                    p.yrstr1 = [None] + [""] * 20
                p.nsc_files1 += 1
            else:
                if m.sfc_charfile2 is None:
                    m.sfc_charfile2 = [None] + [""] * 20
                    p.yrstr2 = [None] + [""] * 20
                p.nsc_files2 += 1
            dataline(E, i, i1)
            tempfil = sub(m.inpline, m.fileind[1], m.fileind[2])
            if m.nfield > 2:
                p.save_pbl_path_yrstr = sub(m.inpline1, m.formind[1], m.ilen)
            if isite == 1:
                m.sfc_charfile1[p.nsc_files1] = tempfil
                m.sfc_charfile1[p.nsc_files1], lgood = checkfile(E, m.sfc_char_unit[isite],
                                                                 m.sfc_charfile1[p.nsc_files1], 1)
                p.yrstr1[p.nsc_files1] = p.save_pbl_path_yrstr
            else:
                m.sfc_charfile2[p.nsc_files2] = tempfil
                m.sfc_charfile2[p.nsc_files2], lgood = checkfile(E, m.sfc_char_unit[isite],
                                                                 m.sfc_charfile2[p.nsc_files2], 1)
                p.yrstr2[p.nsc_files2] = p.save_pbl_path_yrstr
            E.cerrar(m.sfc_char_unit[isite])
    elif ikey == 35:
        if m.nfield != 2:
            mal_campos()
        else:
            obs_superficie.sf_thresh(E, i1 + i)
    elif ikey in (37, 38, 39, 40, 41):
        if m.nfield != 2:
            mal_campos()
        else:
            raise NoTraducido("palabra clave COARE %s" % kw)
    elif ikey == 50:
        if m.nfield != 3:
            mal_campos()
        else:
            up_window(E, i1 + i)
    else:
        if ikey not in (4, 22, 25):
            E.w(m.writeunit, formstr1, pid(E), "E01", modnam, "INVALID KEYWORD:", kw)
            m.lbad = True


def year_str(E, i1):
    m = E.m
    nfield1 = m.nfield - 1
    s = getfields(E, i1, nfield1)
    ystr = ""
    for ifield in range(3, nfield1 + 1):
        if ifield == 3:
            ystr = s[ifield].strip()
        else:
            ystr = ystr.strip() + " " + s[ifield].strip()
    return ystr


def methods(E, i1):
    m, p = E.m, E.pb
    modnam = fx("METHODS", 10)
    formstr1 = fmt_msg(E, "a,3(1x,a))")
    formstr2 = fmt_msg(E, "3(a,1x),2(a))")
    word1 = [None, "DUPLICATE ENTRY OF KEYWORD", "INVALID PROCESS", "INVALID PARAMETER"]
    word2 = [None, "PROCESS", "FOR KEYWORD", "PARAMETER"]
    nfield1 = m.nfield - 1
    datafield = getfields(E, i1, nfield1)
    kw = m.keywrd[m.ikey].strip()
    item = 1
    lfound = False
    while item <= m.nitems and not lfound:
        if datafield[1].strip() == m.items[item].strip():
            lfound = True
        else:
            item += 1
    gooditem = goodaction = False
    if lfound:
        if p.litems[item] and item != 3 and item != 8:
            E.w(m.writeunit, formstr1, pid(E), "E03", modnam, word1[1], kw, word2[1], m.items[item].strip())
            m.lbad = True
            gooditem = False
        else:
            p.litems[item] = True
            gooditem = True
    else:
        E.w(m.writeunit, formstr1, pid(E), "E05", modnam, word1[2], datafield[1].strip(), word2[2], kw)
        m.lbad = True
        gooditem = False
    iaction = 1
    lfound = False
    while iaction <= m.nactions and not lfound:
        if datafield[2].strip() == m.actions[iaction].strip():
            lfound = True
        else:
            iaction += 1
    if not lfound and datafield[2].strip() == "SUNRIS":
        lfound = True
        iaction = 6
    if lfound:
        if iaction != 12:
            if p.lactions[iaction]:
                E.w(m.writeunit, formstr1, pid(E), "E03", modnam, word1[1], kw, word2[3],
                    m.actions[iaction].strip())
                m.lbad = True
                goodaction = False
            else:
                p.lactions[iaction] = True
                goodaction = True
        else:
            # el original escribe con formstr(3), que nunca se define
            E.w(m.writeunit, fmt_msg(E, "3(a,1x),2(a))"), pid(E), "W81", modnam, "OBSOLETE PARAMETER",
                m.actions[iaction].strip(), word2[2], kw, "; IGNORE")
    else:
        E.w(m.writeunit, formstr1, pid(E), "E05", modnam, word1[3], datafield[2].strip(), word2[2], kw)
        m.lbad = True
        goodaction = False
    if gooditem and goodaction:
        if ((item == 1 and iaction > 2) or ((item in (2, 4, 5)) and iaction != item + 1) or
                (item == 3 and iaction != 4 and iaction != 7) or
                (item == 6 and iaction not in (8, 9, 12)) or (item == 7 and iaction not in (10, 11, 12)) or
                (item == 8 and (iaction < 13 or iaction > 27)) or (item == 9 and iaction < 28)):
            E.w(m.writeunit, formstr2, pid(E), "E77", modnam, "INVALID COMBINATION OF", m.items[item].strip(),
                m.actions[iaction].strip())
            m.lbad = True


def up_window(E, i1):
    m, p = E.m, E.pb
    modnam = fx("UP_WINDOW", 10)
    formstr1 = fmt_msg(E, "2(a,1x),i3,1x,a,1x,i3,1x,a)")
    formstr2 = fmt_msg(E, "3(a,1x),i3,1x,a)")
    formstr3 = fmt_msg(E, "a,4(1x,a))")
    formstr4 = fmt_msg(E, "2(a,1x),i3,2(i1x,a),1x,i3)")
    keywrd1 = [None, "UAWINDOW", "UADAYWIN"]
    str1 = [None, "HOUR", "DAY"]
    str2 = [None, "HRS", "DAYS"]
    thresh = [None, 12, 3]
    nfield1 = m.nfield - 1
    times = [None, 0, 0]
    datafield = getfields(E, i1, nfield1)
    j = 1 if "UAWINDOW" in m.inpline1 else 2
    v, iflag, _ = lread(datafield[1], ["i"])
    if iflag == 0:
        times[1] = v[0]
        if abs(times[1]) > thresh[j]:
            E.w(m.writeunit, formstr1, pid(E), "E05", modnam, keywrd1[j], str1[j], times[1], "EXCEEDS",
                thresh[j], str2[j])
            m.lbad = True
        elif times[1] > 0:
            E.w(m.writeunit, formstr2, pid(E), "E05", modnam, keywrd1[j], "BEGINNING", str1[j], times[1],
                "IS POSITIVE")
            m.lbad = True
    else:
        E.w(m.writeunit, formstr3, pid(E), "E05", modnam, "INVALID VALUE FOR", keywrd1[j], str1[j], ":",
            datafield[1].strip())
        m.lbad = True
    v, iflag, _ = lread(datafield[2], ["i"])
    if iflag == 0:
        times[2] = v[0]
        if times[2] > thresh[j]:
            E.w(m.writeunit, formstr1, pid(E), "E05", modnam, keywrd1[j], str1[j], times[1], "EXCEEDS",
                thresh[j], str2[j])
            m.lbad = True
        elif times[2] < 0:
            E.w(m.writeunit, formstr2, pid(E), "E05", modnam, keywrd1[j], "ENDING", str1[j], times[1],
                "IS NEGATIVE")
            m.lbad = True
        elif times[2] < times[1]:
            E.w(m.writeunit, formstr4, pid(E), "E78", modnam, keywrd1[j], "BEGINNING", str1[j], times[1],
                "IS GREATER THAN ENDING", str1[j], times[2])
            m.lbad = True
    else:
        E.w(m.writeunit, formstr3, pid(E), "E05", modnam, "INVALID VALUE FOR", keywrd1[j], str1[j], ":",
            datafield[1].strip())
        m.lbad = True
    if not m.lbad:
        for k in (1, 2):
            if j == 1:
                p.snding_win[k] = times[k]
            else:
                p.day_window[k] = times[k]


# ------------------------------------------------------------------------------------------
def pbl_test(E):
    from . import estacion_local
    m, p, u, s, o = E.m, E.pb, E.up, E.sf, E.os
    modnam = fx("PBL_TEST", 10)
    f = {k: fmt_msg(E, v) for k, v in {
        1: "3(a,1x),i8,a1,i8,3(1x,a),1x,i8,a1,i8)", 2: "a,2(1x,a))", 3: "a,1x,a)",
        4: "2(a,1x,f5.2,1x),a,1x,a)", 5: "a)", 6: "a,3(1x,a))", 7: "2(a,1x),i8,1x,3(a,1x),i8)",
        8: "a,1x,i8,a1,i8)", 9: "a,1x,a4,1x,a)"}.items()}
    mu = m.msg_unit
    usercloud = usertemp = False
    use_os_ustar = use_os_cloud = True
    p.run_coare_orig = p.run_coare
    if not m.lpath[4] and not m.lpath[5]:
        estacion_local.onsite_init(E)
    ov = o.osvars
    if m.lpath[5] and o.overland:
        if ov[o.ustar_var].lread:
            if not o.osstage1:
                E.w(mu, f[9], pid(E), "I80", modnam, "LOCATION IS OVERLAND; PROGNOSTIC VARIABLE",
                    ov[o.ustar_var].varname, "READ IN STAGE 1 BUT CALCULATED IN STAGE 2")
            use_os_ustar = False
        if ov[o.cloud_var].lread:
            if not o.osstage1:
                E.w(mu, f[9], pid(E), "I80", modnam, "LOCATION IS OVERLAND; PROGNOSTIC VARIABLE",
                    ov[o.cloud_var].varname, "READ IN STAGE 1 BUT CALCULATED IN STAGE 2")
            use_os_cloud = False
    if m.lpath[4]:
        if not ov[o.ustar_var].lread:
            use_os_ustar = False
        if not ov[o.cloud_var].lread:
            use_os_cloud = False
    if p.litems[8]:
        if o.overland:
            E.w(mu, f[5], pid(E), "W82", modnam, "COARE ITEM DETECTED FOR OVERLAND DATA; COARE IGNORED")
            if p.lactions[14]:
                p.run_coare_orig = True
        else:
            raise NoTraducido("COARE (algoritmo sobre agua)")
    if (p.coare_mix[1] or p.coare_mix[2] or p.coare_mix[3] or p.coare_mix[5]) and \
            ((m.lpath[4] or m.lpath[5]) and not ov[o.mix_var].lread):
        raise NoTraducido("COARE (alturas de mezcla)")
    if p.litems[9] and (p.lactions[28] or p.lactions[30] or p.lactions[31]):
        p.sub_upper = True
        if u.lsecondary:
            if p.lactions[30]:
                E.w(mu, f[5], pid(E), "W89", modnam, "SECONDARY STATION WILL NOT BE USED FOR UPPER AIR SUBSTITUTION")
                u.nstation = 1
                u.lsecondary = False
            else:
                m.use_second = True
                if p.lactions[31]:
                    p.check_sec_first = True
        else:
            if p.lactions[31]:
                E.w(mu, f[5], pid(E), "W90", modnam, "NO SECONDARY STATION AVAILABLE FOR UPPER AIR SUBSTITUTION")
                p.check_sec_first = False
    elif not p.litems[9] or (p.litems[9] and p.lactions[29]):
        u.nstation = 1
    if u.lsecondary and abs(u.upgmt2lst[2] - u.upgmt2lst[1]) > 1:
        E.w(mu, f[5], pid(E), "W36", modnam, "PRIMARY AND SECONDARY STATIONS MORE THAN 1 TIMEZONE APART")
    if u.nstation == 2 and p.sub_upper:
        if u.upstarts[1] <= u.upstarts[2]:
            u.upstart = u.upstarts[1]
            u.updates[1] = list(u.updates1[1][1])
        else:
            u.upstart = u.upstarts[2]
            u.updates[1] = list(u.updates1[2][1])
        if u.upends[1] >= u.upends[2]:
            u.upend = u.upends[1]
            u.updates[2] = list(u.updates1[1][2])
        else:
            u.upend = u.upends[2]
            u.updates[2] = list(u.updates1[2][2])
    else:
        u.upstart = u.upstarts[1]
        u.upend = u.upends[1]
        u.updates = [list(r) for r in u.updates1[1]]
    lbaddate = [None, True, True, True]
    lp = m.lpath
    if p.lpblkeywords[1]:
        if lp[2]:
            if p.pblstart > u.upend or p.pblend < u.upstart:
                if ov[o.mix_var].lread:
                    lbaddate[1] = False
                E.w(mu, f[1], pid(E), "W80", modnam, "MISMATCH OF", m.pathid[2], "DATA PERIOD", u.upstart, "-",
                    u.upend, "AND", m.pathid[6], "DATA PERIOD", p.pblstart, "-", p.pblend)
                if not p.sub_upper:
                    u.upstart = p.pblstart
                    u.upend = p.pblend
                    u.updates = [list(r) for r in p.pbldates]
                    u.upstarts[1] = u.upstarts[2] = u.upstart
                    u.upends[1] = u.upends[2] = u.upend
            else:
                lbaddate[1] = False
                if p.pblstart < u.upstart:
                    E.w(mu, f[7], pid(E), "W80", modnam, m.pathid[2], "START DATE", u.upstart, "IS AFTER",
                        m.pathid[6], "START DATE", p.pblstart)
                else:
                    if not p.sub_upper and (not u.upstage1[1] or (not u.lupkeywords[3] and not u.lupkeywords[4])):
                        u.upstart = p.pblstart
                        u.updates[1] = list(p.pbldates[1])
                        u.upstarts[1] = u.upstarts[2] = u.upstart
                if u.upend < p.pblend:
                    E.w(mu, f[7], pid(E), "W80", modnam, m.pathid[2], "END DATE", u.upend, "IS BEFORE",
                        m.pathid[6], "END DATE", p.pblend)
                else:
                    if not p.sub_upper and (not u.upstage1[1] or (not u.lupkeywords[3] and not u.lupkeywords[4])):
                        u.upend = p.pblend
                        u.updates[2] = list(p.pbldates[2])
                        u.upends[1] = u.upends[2] = u.upend
        if lp[3]:
            if p.pblstart > s.sfend or p.pblend < s.sfstart:
                E.w(mu, f[1], pid(E), "W80", modnam, "MISMATCH OF", m.pathid[3], "DATA PERIOD", s.sfstart, "-",
                    s.sfend, "AND", m.pathid[6], "DATA PERIOD", p.pblstart, "-", p.pblend)
                s.sfstart = p.pblstart
                s.sfend = p.pblend
                s.sfdates = [list(r) for r in p.pbldates]
            else:
                lbaddate[2] = False
                if p.pblstart < s.sfstart:
                    E.w(mu, f[7], pid(E), "W80", modnam, m.pathid[3], "START DATE", s.sfstart, "IS AFTER",
                        m.pathid[6], "START DATE", p.pblstart)
                else:
                    if not s.sfstage1 or (not s.lsfkeywords[3] and not s.lsfkeywords[4]):
                        s.sfstart = p.pblstart
                        s.sfdates[1] = list(p.pbldates[1])
                if s.sfend < p.pblend:
                    E.w(mu, f[7], pid(E), "W80", modnam, m.pathid[3], "END DATE", s.sfend, "IS BEFORE",
                        m.pathid[6], "END DATE", p.pblend)
                else:
                    if not s.sfstage1 or (not s.lsfkeywords[3] and not s.lsfkeywords[4]):
                        s.sfend = p.pblend
                        s.sfdates[2] = list(p.pbldates[2])
        for i in (4, 5):
            if lp[i]:
                if p.pblstart > o.osend or p.pblend < o.osstart:
                    E.w(mu, f[1], pid(E), "W80", modnam, "MISMATCH OF", m.pathid[i], "DATA PERIOD", o.osstart,
                        "-", o.osend, "AND", m.pathid[6], "DATA PERIOD", p.pblstart, "-", p.pblend)
                    o.osstart = p.pblstart
                    o.osend = p.pblend
                    o.osdates = [list(r) for r in p.pbldates]
                else:
                    lbaddate[3] = False
                    if p.pblstart < o.osstart:
                        E.w(mu, f[7], pid(E), "W80", modnam, m.pathid[i], "START DATE", o.osstart, "IS AFTER",
                            m.pathid[6], "START DATE", p.pblstart)
                    else:
                        if not o.osstage1 or not o.loskeywords[4]:
                            o.osstart = p.pblstart
                            o.osdates[1] = list(p.pbldates[1])
                    if o.osend < p.pblend:
                        E.w(mu, f[7], pid(E), "W80", modnam, m.pathid[i], "END DATE", o.osend, "IS BEFORE",
                            m.pathid[6], "END DATE", p.pblend)
                    else:
                        if not o.osstage1 or not o.loskeywords[4]:
                            o.osend = p.pblend
                            o.osdates[2] = list(p.pbldates[2])
        if lbaddate[1] and lbaddate[2] and lbaddate[3]:
            m.lbad = True
            E.w(mu, f[8], pid(E), "E70", modnam, "NO DATA PERIODS DATES OVERLAP", p.pblstart, p.pblend)
    else:
        if lp[2] and lp[3]:
            if u.upstart > s.sfend or u.upend < s.sfstart:
                if ov[o.mix_var].lread:
                    lbaddate[1] = lbaddate[2] = False
                    E.w(mu, f[1], pid(E), "W80", modnam, "MISMATCH OF", m.pathid[2], "DATA PERIOD", u.upstart,
                        "-", u.upend, "AND", m.pathid[3], "DATA PERIOD", s.sfstart, "-", s.sfend)
            else:
                lbaddate[1] = lbaddate[2] = False
        if lp[2] and lp[4]:
            if u.upstart > o.osend or u.upend < o.osstart:
                if ov[o.mix_var].lread:
                    lbaddate[1] = lbaddate[3] = False
                E.w(mu, f[1], pid(E), "W80", modnam, "MISMATCH OF", m.pathid[2], "DATA PERIOD", u.upstart, "-",
                    u.upend, "AND", m.pathid[4], "DATA PERIOD", o.osstart, "-", o.osend)
            else:
                lbaddate[1] = lbaddate[3] = False
        if lp[2] and lp[5]:
            if u.upstart > o.osend or u.upend < o.osstart:
                if ov[o.mix_var].lread:
                    lbaddate[1] = lbaddate[3] = False
                E.w(mu, f[1], pid(E), "W80", modnam, "MISMATCH OF", m.pathid[2], "DATA PERIOD", u.upstart, "-",
                    u.upend, "AND", m.pathid[5], "DATA PERIOD", o.osstart, "-", o.osend)
            else:
                lbaddate[1] = lbaddate[3] = False
        if lp[3] and lp[4]:
            if s.sfstart > o.osend or s.sfend < o.osstart:
                E.w(mu, f[1], pid(E), "W80", modnam, "MISMATCH OF", m.pathid[3], "DATA PERIOD", u.upstart, "-",
                    u.upend, "AND", m.pathid[4], "DATA PERIOD", o.osstart, "-", o.osend)
            else:
                lbaddate[2] = lbaddate[3] = False
        if lbaddate[1] and lbaddate[2] and lbaddate[3]:
            m.lbad = True
            E.w(mu, f[5], pid(E), "E70", modnam, "NO DATA PERIODS DATES OVERLAP")
        else:
            if lp[2]:
                p.pblstart = u.upstart
                p.pblend = u.upend
                p.pbldates = [list(r) for r in u.updates]
            if lp[3]:
                if p.pblstart == 0:
                    p.pblstart = s.sfstart
                    p.pbldates[1] = list(s.sfdates[1])
                else:
                    if s.sfstart < p.pblstart:
                        p.pblstart = s.sfstart
                        p.pbldates[1] = list(s.sfdates[1])
                if p.pblend == 0:
                    p.pblend = s.sfend
                    p.pbldates[2] = list(s.sfdates[2])
                else:
                    if s.sfend > p.pblend:
                        p.pblend = s.sfend
                        p.pbldates[2] = list(s.sfdates[2])
            if lp[4] or lp[5]:
                if p.pblstart == 0:
                    p.pblstart = o.osstart
                    p.pbldates[1] = list(o.osdates[1])
                else:
                    if o.osstart < p.pblstart:
                        p.pblstart = o.osstart
                        p.pbldates[1] = list(o.osdates[1])
                if p.pblend == 0:
                    p.pblend = o.osend
                    p.pbldates[2] = list(o.osdates[2])
                else:
                    if o.osend > p.pblend:
                        p.pblend = o.osend
                        p.pbldates[2] = list(o.osdates[2])
    if p.lpblkeywords[2]:
        if not ((lp[4] or lp[5]) and ov[o.mix_var].lread and not lp[2]):
            E.w(mu, f[3], pid(E), "W70", modnam, m.keywrd[10], "KEYWORD NOT NEEDED")
            if lp[4] or lp[5]:
                p.pbllat, p.pbllon, p.pblid, p.pblgmt2lst = o.oslat, o.oslon, o.osid, o.osgmt2lst
            else:
                p.pbllat, p.pbllon, p.pblid, p.pblgmt2lst = s.sflat, s.sflon, s.sfid, s.sfgmt2lst
            if lp[2]:
                p.pblgmt2lst = u.upgmt2lst[1]
    else:
        if (lp[4] or lp[5]) and ov[o.mix_var].lread and not lp[2]:
            strx = "ONSITE" if lp[4] else "PROG"
            E.w(mu, f[2], pid(E), "E71", modnam, "LOCATION KEYWORD MISSING; NEEDED FOR", strx,
                "DATA WITH MIXHTS AND NO UPPERAIR DATA")
            m.lbad = True
        if lp[4] or lp[5]:
            p.pbllat, p.pbllon, p.pblid, p.pblgmt2lst = o.oslat, o.oslon, o.osid, o.osgmt2lst
        else:
            p.pbllat, p.pbllon, p.pblid, p.pblgmt2lst = s.sflat, s.sflon, s.sfid, s.sfgmt2lst
        if lp[2]:
            p.pblgmt2lst = u.upgmt2lst[1]
    if not lp[4] and not lp[5] and lp[3] and not p.lactions[3]:
        m.lbad = True
        E.w(m.writeunit, f[5], pid(E), "E87", modnam, "NWS DATA ONLY AND SUBNWS ACTION NOT INVOKED")
    if p.lpblkeywords[11]:
        if lp[3] and (s.lasos or (not s.lasos and s.iasos != 0)):
            a = s.asoscommdates[s.iasos]
            if p.pblend >= a.commisdate and abs(s.nws_hgt - a.anem_meters) > 0.1:
                E.w(m.writeunit, f[4], pid(E), "W71", modnam, "NWS_HGT", s.nws_hgt, "M NOT EQUAL TO ASOS HEIGHT",
                    a.anem_meters, "FOR STATION", s.sfid.strip())
    else:
        if lp[3] and p.lactions[3]:
            E.w(m.writeunit, f[5], pid(E), "E72", modnam, "NWS_HGT KEYWORD MISSING")
            m.lbad = True
    lbadsc = False
    scstr = [None, "PRIMARY", "SECONDARY"]
    lk = p.lpblkeywords
    for isurf in (15, 16):
        j = 3 if isurf == 15 else 12
        ikey1 = isurf + 18
        if lk[isurf] and (lk[j] or lk[j + 1] or lk[j + 2]):
            lbadsc = True
            E.w(m.writeunit, f[6], pid(E), "E73", modnam, m.keywrd[ikey1], "KEYWORD LISTED WITH",
                scstr[isurf - 14], "SITE SC KEYWORDS")
    if lp[3] != lp[4]:
        if lk[12] or lk[13] or lk[14] or lk[16]:
            E.w(m.writeunit, f[5], pid(E), "W74", modnam, "SECONDARY SITE SC KEYWORDS LISTED BUT NOT NEEDED")
        if (lk[3] != lk[4]) or (lk[3] != lk[5]):
            lbadsc = True
            E.w(m.writeunit, f[5], pid(E), "E73", modnam, "ONE OR MORE PRIMARY SITE SC KEYWORDS MISSING")
    if lp[3] and lp[4] and p.lactions[3]:
        if lk[15] != lk[16]:
            for i in (1, 2):
                j, isurf = (3, 15) if i == 1 else (12, 16)
                if not lk[isurf] and (not lk[j] or not lk[j + 1] or not lk[j + 2]):
                    lbadsc = True
                    E.w(m.writeunit, f[2], pid(E), "E73", modnam, "ONE OR MORE", scstr[i], "SITE SC KEYWORDS MISSING")
        elif not lk[15] and not lk[16]:
            for i in (1, 2):
                j = 3 if i == 1 else 12
                if not lk[j] or not lk[j + 1] or not lk[j + 2]:
                    lbadsc = True
                    E.w(m.writeunit, f[2], pid(E), "E73", modnam, "ONE OR MORE", scstr[i], "SITE SC KEYWORDS MISSING")
    if p.litems[6]:
        if p.lactions[8]:
            usercloud = True
        if p.lactions[9]:
            p.subcloud = False
    if p.litems[7]:
        if p.lactions[10]:
            usertemp = True
        if p.lactions[11]:
            p.subtemp = False
    if (lp[4] or lp[5]) and lp[3]:
        if (p.lactions[4] and not p.run_coare) or ov[o.inso_var].lread:
            p.subcloud = False
            if p.litems[6] and p.lactions[8]:
                E.w(mu, f[5], pid(E), "W73", modnam,
                    "BULKRN REQUESTED OR ONSITE INSO AVAILABLE; RESET CLOUD COVER SUBSTITUION TO NO SUBSTITUTION")
        elif use_os_cloud and p.subcloud and not usercloud:
            p.subcloud = False
        if ov[o.temp_var].lread and p.subtemp and not usertemp:
            p.subtemp = False
    elif lp[4] or lp[5]:
        if (p.lactions[4] and not p.run_coare) or ov[o.inso_var].lread:
            p.subcloud = False
            if p.litems[6] and p.lactions[8]:
                E.w(mu, f[5], pid(E), "W73", modnam,
                    "BULKRN REQUESTED OR ONSITE INSO AVAILABLE; RESET CLOUD COVER SUBSTITUION TO NO SUBSTITUTION")
        if not use_os_cloud and not ov[o.nrad_var].lread and (not ov[o.inso_var].lread or not p.lactions[4]):
            E.w(mu, f[5], pid(E), "W73", modnam, "NOT ENOUGH VARIABLES FOR STABLE BL CALCULATIONS")
    if p.lactions[4] and p.run_coare:
        E.w(mu, f[5], pid(E), "I94", modnam, "BULKRN REQUESTED WITH COARE; BULKRN NOT INVOKED")
    if p.litems[3] and p.lactions[7]:
        p.adjustar = True
        if lp[4] or lp[5]:
            if p.run_coare:
                p.adjustar = False
                E.w(mu, f[5], pid(E), "I93", modnam, "ADJUST U* REQUESTED WITH COARE; ADJUST U* NOT INVOKED")
            if use_os_ustar:
                E.w(mu, f[5], pid(E), "I85", modnam, "ADJUST U* REQUESTED; HOURS WITH VALID U* WILL NOT BE ADJUSTED")
    if p.lactions[6] and not m.lkey[24]:
        p.snding_win[1] = -6
        p.snding_win[2] = 2
    if lk[12] or lk[16]:
        p.sec_sc = True
    if not lbadsc:
        isite = 1
        lbadsc = aersurf(E, 1, isite)
        if lbadsc:
            m.lbad = True
        if p.sec_sc:
            lbadsc = aersurf(E, 1, 2)
            if lbadsc:
                m.lbad = True
    else:
        m.lbad = True
    if ((lp[4] or lp[5]) and o.oslat < 0.0) or (not lp[4] and not lp[5] and s.sflat < 0.0):
        p.ihem[1] = 2
    if p.sec_sc and s.sflat < 0.0:
        p.ihem[2] = 2
    if lk[18]:
        E.w(mu, f[3], pid(E), "W70", modnam, m.keywrd[4], "KEYWORD NOT NEEDED")


def surf_years(E, yrstr):
    m, p = E.m, E.pb
    modnam = fx("SURF_YEARS", 10)
    formstr1 = fmt_msg(E, "a,1x,a)")
    formstr2 = fmt_msg(E, "a,1x,i4,1x,a)")
    lbadsc = False
    if yrstr.strip() == "-9":
        p.nsc_years = p.pbldates[2][1] - p.pbldates[1][1] + 1
        p.sc_years = [None] + [p.pbldates[1][1] - 1 + iyr for iyr in range(1, p.nsc_years + 1)]
    else:
        nfields = 0
        ys = yrstr
        for i in range(1, len(ys.rstrip(" ")) + 1):
            if ch(ys, i + 1) == " " and ch(ys, i) != " ":
                nfields += 1
        v, io, _ = lread(ys, [("a", 15)] * nfields)
        yearfields = [None] + v
        p.nsc_years = 0
        yrs = [None, 0, 0]
        for ifield in range(1, nfields + 1):
            yf = yearfields[ifield]
            if "-" in yf:
                nn = yf.find("-") + 1
                a, i1f, _ = lread(yf[:nn - 1], ["i"])
                b, i2f, _ = lread(yf[nn:len(yf.rstrip())], ["i"])
                iflags = [None, i1f, i2f]
                if i1f == 0:
                    yrs[1] = a[0]
                if i2f == 0:
                    yrs[2] = b[0]
                for i in (1, 2):
                    if iflags[i] != 0:
                        E.w(m.msg_unit, formstr1, pid(E), "E74", modnam, "INVALID YEAR STRING", yf.strip())
                        lbadsc = True
                    elif yrs[i] < 1000:
                        E.w(m.msg_unit, formstr2, pid(E), "E74", modnam, "YEAR", yrs[i], "IS NOT 4-DIGIT")
                        lbadsc = True
                if not lbadsc:
                    if yrs[1] > yrs[2]:
                        E.w(m.msg_unit, formstr1, pid(E), "E74", modnam, "FIRST YEAR OF RANGE > SECOND YEAR ",
                            yf.strip())
                        lbadsc = True
                    else:
                        p.nsc_years += yrs[2] - yrs[1] + 1
            else:
                a, i1f, _ = lread(yf, ["i"])
                if i1f != 0:
                    E.w(m.msg_unit, formstr1, pid(E), "E74", modnam, "INVALID YEAR STRING", yf.strip())
                    lbadsc = True
                else:
                    yrs[1] = a[0]
                    if yrs[1] < 1000:
                        E.w(m.msg_unit, formstr2, pid(E), "E74", modnam, "YEAR", yrs[1], "IS NOT A 4-DIGIT YEAR")
                        lbadsc = True
                    else:
                        p.nsc_years += 1
        if not lbadsc:
            p.sc_years = [None]
            for ifield in range(1, nfields + 1):
                yf = yearfields[ifield]
                if "-" in yf:
                    nn = yf.find("-") + 1
                    a = lread(yf[:nn - 1], ["i"])[0][0]
                    b = lread(yf[nn:len(yf.rstrip())], ["i"])[0][0]
                    for i in range(a, b + 1):
                        p.sc_years.append(i)
                else:
                    p.sc_years.append(lread(yf, ["i"])[0][0])
    if lbadsc:
        m.lbad = True


def _abrir_lineas(E, iunit, fname):
    m = E.m
    if iunit == m.inp_unit:
        nombre = m.inpfile
    else:
        nombre = fname
    with open(nombre.strip(), "r", encoding="latin-1", newline=None) as fh:
        lin = fh.read().split("\n")
    if lin and lin[-1] == "":
        lin.pop()
    return lin


def aersurf(E, iswitch, isite):
    """AERSURF. Devuelve lbadsc."""
    m, p = E.m, E.pb
    modnam = fx("AERSURF", 10)
    formstr2 = fmt_msg(E, "a)")
    formstr3 = fmt_msg(E, "a,2(1x,a))")
    formstr4 = fmt_msg(E, "a,3(1x,a))")
    formstr5 = fmt_msg(E, "a,1x,i4,2(1x,a))")
    formstr6 = fmt_msg(E, "a,5(1x,a))")
    ny = p.pbldates[2][1] - p.pbldates[1][1] + 1
    have_sc = None
    if iswitch == 1:
        have_sc = [False] * (ny + 1)
    else:
        p.talbedo = [[[-9.0] * (ny + 1) for _ in range(13)] for _ in range(13)]
        p.tbowen = [[[-9.0] * (ny + 1) for _ in range(13)] for _ in range(13)]
        p.tzo = [[[-9.0] * (ny + 1) for _ in range(13)] for _ in range(13)]
        p.tsectors = [[[-9.0] * (ny + 1) for _ in range(13)] for _ in range(3)]
    lbadsc = False
    lfound2 = [[False] * 4 for _ in range(3)]
    sc_keys = [None, [None, "FREQ_SECT", "SECTOR", "SITE_CHAR"], [None, "FREQ_SECT2", "SECTOR2", "SITE_CHAR2"]]
    lfound1 = [False] * 4
    nfiles = p.nsc_files1 if isite == 1 else p.nsc_files2
    lskip = False
    nfreq = nsec = 0
    for ifiles in range(1, nfiles + 1):
        if p.lpblkeywords[isite + 14]:
            iunit = m.sfc_char_unit[isite]
        else:
            iunit = m.inp_unit
        if isite == 1:
            fname = m.sfc_charfile1[ifiles]
            surf_years(E, p.yrstr1[ifiles])
        else:
            fname = m.sfc_charfile2[ifiles]
            surf_years(E, p.yrstr2[ifiles])
        if iswitch == 1:
            for iyr1 in range(1, p.nsc_years + 1):
                yy = p.sc_years[iyr1]
                if p.pbldates[1][1] <= yy <= p.pbldates[2][1]:
                    if have_sc[yy - p.pbldates[1][1] + 1]:
                        lbadsc = True
                        E.w(m.msg_unit, formstr5, pid(E), "E74", modnam, "YEAR", yy, p.sites[isite].strip(),
                            "SURFACE CHARACTERSTICS PREVIOUSLY ASSIGNED")
                    else:
                        have_sc[yy - p.pbldates[1][1] + 1] = True
            if lbadsc:
                m.lbad = True
            if p.lpblkeywords[isite + 14]:
                # al llegar al final, el original procesa otra vez el último registro leído
                for raw in _abrir_lineas(E, iunit, fname) + [None]:
                    if raw is not None:
                        m.inpline1 = raw[:m.linelen]
                    L = m.inpline1
                    ilen = len(L.rstrip(" "))
                    m.ilen = ilen
                    if ilen > 0 and L[0:2] != "**":
                        L = L.upper()
                        m.inpline1 = L
                        if "FREQ_SECT" in L or "SITE_CHAR" in L or "SECTOR" in L:
                            akey = lread(L, [("a", 12)])[0][0].strip()
                            ikey1 = 1
                            lfound = False
                            while ikey1 <= 3 and not lfound:
                                if akey == sc_keys[isite][ikey1]:
                                    lfound = True
                                    lfound2[isite][ikey1] = True
                                elif isite == 2:
                                    if akey == sc_keys[isite][ikey1] or akey == sc_keys[isite - 1][ikey1]:
                                        lfound = True
                                        lfound2[isite][ikey1] = True
                                    else:
                                        ikey1 += 1
                                else:
                                    ikey1 += 1
                            if lfound:
                                lfound1[ikey1] = True
                                if ikey1 >= 2 and not lfound1[1]:
                                    E.w(m.writeunit, formstr2, pid(E), "E75", modnam, "FREQ_SECT OR FREQ_SECT2 NOT FOUND")
                                    m.lbad = True
                                    break
                if not lfound2[isite][1] or not lfound2[isite][2] or not lfound2[isite][3]:
                    for k in (1, 2, 3):
                        lbadsc = True
                        if not lfound2[isite][k]:
                            E.w(m.msg_unit, formstr6, pid(E), "E73", modnam, "MISSING KEYWORD ", sc_keys[isite][k],
                                "FOR", p.sites[isite].strip(), "SURFACE CHARACTERISTICS SITE; FILENAME",
                                fname.strip())
        iyr1 = 1
        lgo = False
        while iyr1 <= p.nsc_years and not lgo:
            if p.pbldates[1][1] <= p.sc_years[iyr1] <= p.pbldates[2][1]:
                lgo = True
            else:
                iyr1 += 1
        if not lgo:
            p.sc_years = None
            continue
        if not m.lbad and iswitch != 1:
            for raw in _abrir_lineas(E, iunit, fname) + [None]:
                if raw is not None:
                    m.inpline1 = raw[:m.linelen]
                L = m.inpline1
                ilen = len(L.rstrip(" "))
                m.ilen = ilen
                if L[0:2] == "**" and "MMIF VERSION" in L:
                    k = L.find("MMIF VERSION") + 1
                    vers = sub(L, k + 12, ilen)
                    if m.lpath[4]:
                        E.w(m.writeunit, formstr3, pid(E), "W79", modnam, "MMIF VERSION", vers.strip(),
                            "FOUND WHILE USING ONSITE PATHWAY")
                    else:
                        E.w(m.writeunit, formstr3, pid(E), "I83", modnam, "MMIF VERSION", vers.strip(), "FOUND")
                    if not p.lmmif_versn:
                        p.mmif_versn = vers
                        p.lmmif_versn = True
                    else:
                        if vers.strip() != p.mmif_versn.strip():
                            E.w(m.writeunit, formstr4, pid(E), "W80", modnam, "MMIF VERSION ", vers.strip(),
                                "DOES NOT MATCH CURRENT MMIF VERSION", p.mmif_versn.strip())
                        p.mmif_versn = vers
                if ilen > 0 and L[0:2] != "**":
                    L = L.upper()
                    m.inpline1 = L
                    if "FREQ_SECT" in L or "SITE_CHAR" in L or "SECTOR" in L:
                        akey = lread(L, [("a", 12)])[0][0].strip()
                        ikey1 = 1
                        lfound = False
                        while ikey1 <= 3 and not lfound:
                            if akey == sc_keys[isite][ikey1]:
                                lfound = True
                                lfound2[isite][ikey1] = True
                            else:
                                ikey1 += 1
                        if isite == 2 and iunit == m.sfc_char_unit[isite] and not lfound:
                            ikey1 = 1
                            lfound = False
                            while ikey1 <= 3 and not lfound:
                                if akey == sc_keys[1][ikey1]:
                                    lfound = True
                                    lfound2[isite][ikey1] = True
                                else:
                                    ikey1 += 1
                        if lfound:
                            lfound1[ikey1] = True
                            ii = L.find(sc_keys[isite][ikey1]) + 1
                            i1 = len(sc_keys[isite][ikey1])
                            if ikey1 == 1:
                                nfreq, nsec, lskip = freq_sec(E, ii + i1, isite)
                            elif ikey1 == 2:
                                if not lskip:
                                    sectors(E, ii + i1, isite, nsec)
                            else:
                                if not lskip:
                                    site_char(E, ii + i1, isite, nfreq, nsec)
        if m.lbad or lbadsc:
            p.lbadpbl = True
        p.sc_years = None
    if iswitch == 1:
        for iyr1 in range(p.pbldates[1][1], p.pbldates[2][1] + 1):
            if not have_sc[iyr1 - p.pbldates[1][1] + 1]:
                if not p.run_coare:
                    lbadsc = True
                    E.w(m.msg_unit, formstr5, pid(E), "E74", modnam, "YEAR", iyr1, p.sites[isite].strip(),
                        "SURFACE CHARACTERSTICS NOT ASSIGNED")
        if lbadsc:
            m.lbad = True
            p.lbadpbl = True
    if iswitch != 1:
        nf = p.nfreq1 if isite == 1 else p.nfreq2
        ns = p.nsectors1 if isite == 1 else p.nsectors2
        freq = max(nf[1:])
        sec = max(ns[1:])
        sfc = [[[None] * (ny + 1) for _ in range(freq + 1)] for _ in range(sec + 1)]
        sct = [[[None] * (ny + 1) for _ in range(sec + 1)] for _ in range(3)]
        for iyr in range(p.pbldates[1][1], p.pbldates[2][1] + 1):
            iyr1 = iyr - p.pbldates[1][1] + 1
            for ifreq in range(1, freq + 1):
                for isec in range(1, sec + 1):
                    sfc[isec][ifreq][iyr1] = (p.talbedo[isec][ifreq][iyr1], p.tbowen[isec][ifreq][iyr1],
                                              p.tzo[isec][ifreq][iyr1])
                    for idd in (1, 2):
                        sct[idd][isec][iyr1] = p.tsectors[idd][isec][iyr1]
        if isite == 1:
            p.sfc_char1 = sfc
            p.sectors1 = sct
        else:
            p.sfc_char2 = sfc
            p.sectors2 = sct
        p.talbedo = p.tbowen = p.tzo = p.tsectors = None
    return lbadsc


def _contar_campos(L):
    lt = len(L.rstrip(" "))
    i = 1
    istart = 0
    while i <= lt and istart == 0:
        if ch(L, i) != " ":
            istart = i
        i += 1
    n = 1
    for i in range(istart, lt):
        if ch(L, i + 1) == " " and ch(L, i) != " ":
            n += 1
    return n


def freq_sec(E, i1, isite):
    """Devuelve (nfreq, nsec, lskip)."""
    m, p = E.m, E.pb
    modnam = fx("FREQ_SEC", 10)
    formstr1 = fmt_msg(E, "i3,1x,a)")
    formstr2 = fmt_msg(E, "a,3(1x,a))")
    formstr3 = fmt_msg(E, "2(a,1x),i3,1x,a,i3)")
    lskip = True
    nfreq = nsec = 0
    nfield1 = _contar_campos(m.inpline1)
    if nfield1 < 3:
        E.w(m.writeunit, formstr1, pid(E), "E03", modnam, m.nfield,
            "IS AN INVALID NUMBER OF FIELDS FOR KEYWORD FREQ_SECT")
        m.lbad = True
        return nfreq, nsec, lskip
    nfield1 -= 1
    datafield = getfields(E, i1, nfield1)
    if nfield1 > 2:
        lfound = False
        ifield = 3
        while ifield <= nfield1 and not lfound:
            df = datafield[ifield]
            if "-" in df:
                idash = df.find("-") + 1
                yr1 = lread(df[idash - 5:idash - 1], ["i"])[0][0]
                yr2 = lread(df[idash:idash + 4], ["i"])[0][0]
                if yr1 <= p.sc_years[1] and p.sc_years[2] <= yr2:
                    lfound = True
            else:
                yr1 = lread(df, ["i"])[0][0]
                if p.sc_years[1] == yr1:
                    lfound = True
            if not lfound:
                ifield += 1
        lskip = not lfound
    else:
        lskip = False
    if not lskip:
        ifreq = 0
        isec = 0
        f1 = datafield[1].strip()
        if f1 == "ANNUAL":
            ifreq = 1
        elif f1 == "MONTHLY":
            ifreq = 12
        elif f1 == "SEASONAL":
            ifreq = 4
        else:
            E.w(m.writeunit, formstr2, pid(E), "E75", modnam, "INVALID FREQUENCY FOR", p.sites[isite].strip(),
                "SITE SURFACE CHARACTERISTICS:", f1)
            m.lbad = True
        v, iflag, _ = lread(datafield[2], ["i"])
        if iflag == 0:
            isec = v[0]
            if isec < p.minsec or isec > p.maxsec:
                if isec < p.minsec:
                    E.w(m.writeunit, formstr3, pid(E), "E75", modnam, p.sites[isite].strip(),
                        "SITE NUMBER OF SECTORS:", isec, "<", p.minsec)
                else:
                    E.w(m.writeunit, formstr3, pid(E), "E75", modnam, p.sites[isite].strip(),
                        "SITE NUMBER OF SECTORS:", isec, ">", p.maxsec)
                m.lbad = True
        else:
            E.w(m.writeunit, formstr2, pid(E), "E75", modnam, "INVALID SECTOR NUMBER FOR", p.sites[isite].strip(),
                "SITE SURFACE CHARACTERISTICS:", datafield[2].strip())
            m.lbad = True
        if not m.lbad:
            nfreq = ifreq
            nsec = isec
            nyr = p.pbldates[2][1] - p.pbldates[1][1] + 1
            for iyr in range(1, p.nsc_years + 1):
                iyr1 = p.sc_years[iyr] - p.pbldates[1][1] + 1
                if iyr1 > 0 and iyr <= nyr:
                    if isite == 1:
                        p.nfreq1[iyr1] = ifreq
                        p.nsectors1[iyr1] = isec
                    else:
                        p.nfreq2[iyr1] = ifreq
                        p.nsectors2[iyr1] = isec
    return nfreq, nsec, lskip


def site_char(E, i1, isite, nfreq, nsec):
    m, p = E.m, E.pb
    modnam = fx("SITE_CHAR", 10)
    sv = p.save_site_char
    formstr1 = fmt_msg(E, "i3,1x,a)")
    formstr2 = fmt_msg(E, "3(a,1x),i3)")
    formstr3 = fmt_msg(E, "a,3(1x,a))")
    formstr4 = fmt_msg(E, "a,1x,a,1x,a,1x,f8.2)")
    formstr5 = fmt_msg(E, "a,3(1x,a))")
    formstr6 = fmt_msg(E, "3(a,1x),f8.6,1x,a)")
    nfield1 = _contar_campos(m.inpline1)
    if nfield1 != 6:
        E.w(m.writeunit, formstr1, pid(E), "E03", modnam, m.nfield,
            "IS AN INVALID NUMBER OF FIELDS FOR KEYWORD SITE_CHAR")
        m.lbad = True
        return
    nfield1 -= 1
    datafield = getfields(E, i1, nfield1)
    site = p.sites[isite].strip()
    ifreq = isec = 0
    v, iflag, _ = lread(datafield[1], ["i"])
    if iflag == 0:
        ifreq = v[0]
        if ifreq < 1 or ifreq > nfreq:
            E.w(m.writeunit, formstr2, pid(E), "E75", modnam, "INVALID FREQUENCY FOR", site,
                "SITE SURFACE CHARACTERISTICS:", ifreq)
            m.lbad = True
        else:
            sv["goodfreq"] = True
    else:
        E.w(m.writeunit, formstr3, pid(E), "E75", modnam, "INVALID FREQUENCY FOR", site,
            "SITE SURFACE CHARACTERISTICS:", datafield[1].strip())
        m.lbad = True
    v, iflag, _ = lread(datafield[2], ["i"])
    if iflag == 0:
        isec = v[0]
        if isec < p.minsec or isec > nsec:
            E.w(m.writeunit, formstr2, pid(E), "E75", modnam, "INVALID SECTOR NUMBER FOR", site,
                "SITE SURFACE CHARACTERISTICS:", isec)
            m.lbad = True
        else:
            sv["goodsec"] = True
    else:
        E.w(m.writeunit, formstr3, pid(E), "E75", modnam, "INVALID SECTOR NUMBER FOR", site,
            "SITE SURFACE CHARACTERISTICS:", datafield[2].strip())
        m.lbad = True
    v, iflag, _ = lread(datafield[3], ["f"])
    if iflag == 0:
        sv["albedo"] = v[0]
        if sv["albedo"] < 0.0 or sv["albedo"] > 1.0:
            E.w(m.writeunit, formstr4, pid(E), "E75", modnam, "INVALID ALBEDO FOR", site,
                "SITE SURFACE CHARACTERISTICS:", sv["albedo"])
            m.lbad = True
    else:
        E.w(m.writeunit, formstr5, pid(E), "E75", modnam, "INVALID ALBEDO FOR", site,
            "SITE SURFACE CHARACTERISTICS:", datafield[3].strip())
        m.lbad = True
    v, iflag, _ = lread(datafield[4], ["f"])
    if iflag == 0:
        sv["bowen"] = v[0]
        b = sv["bowen"]
        if abs(b) > 10.0 and b != -999.0:
            E.w(m.writeunit, formstr4, pid(E), "W75", modnam, "BOWEN RATIO FOR", site, "MAY BE SUSPECT:", b)
        elif b == -999.0:
            E.w(m.writeunit, formstr4, pid(E), "E75", modnam, "INVALID BOWEN RATIO FOR", site,
                "SITE SURFACE CHARACTERISTICS:", b)
            m.lbad = True
    else:
        E.w(m.writeunit, formstr5, pid(E), "E75", modnam, "INVALID BOWEN RATIO FOR", site,
            "SITE SURFACE CHARACTERISTICS:", datafield[4].strip())
        m.lbad = True
    v, iflag, _ = lread(datafield[5], ["f"])
    if iflag == 0:
        sv["zo"] = v[0]
        zo = sv["zo"]
        if zo <= 0.0:
            E.w(m.writeunit, formstr4, pid(E), "E75", modnam, "INVALID Z0 FOR", site,
                "SITE SURFACE CHARACTERISTICS:", zo)
            m.lbad = True
        elif zo < 0.0001:
            E.w(m.writeunit, formstr6, pid(E), "W75", modnam, "Z0 FOR", site, " < 0.0001:", zo, "RESET TO 0.0001")
            sv["zo"] = 0.0001
        elif zo < 0.001:
            E.w(m.writeunit, formstr6, pid(E), "W75", modnam, "Z0 FOR", site, " < 0.001:", zo, "MAY BE SUSPECT")
    else:
        E.w(m.writeunit, formstr5, pid(E), "E75", modnam, "INVALID Z0 FOR", site,
            "SITE SURFACE CHARACTERISTICS:", datafield[5].strip())
        m.lbad = True
    if not m.lbad and sv["goodsec"] and sv["goodfreq"]:
        nyr = p.pbldates[2][1] - p.pbldates[1][1] + 1
        for iyr in range(1, p.nsc_years + 1):
            iyr1 = p.sc_years[iyr] - p.pbldates[1][1] + 1
            if iyr1 > 0 and iyr <= nyr:
                p.talbedo[isec][ifreq][iyr1] = sv["albedo"]
                p.tbowen[isec][ifreq][iyr1] = sv["bowen"]
                p.tzo[isec][ifreq][iyr1] = sv["zo"]


def sectors(E, i1, isite, nsec):
    m, p = E.m, E.pb
    modnam = fx("SECTORS", 10)
    formstr1 = fmt_msg(E, "i3,1x,a)")
    formstr2 = fmt_msg(E, "3(a,1x),i3)")
    formstr3 = fmt_msg(E, "a,3(1x,a))")
    formstr4 = fmt_msg(E, "5(a,1x),f7.2)")
    formstr5 = fmt_msg(E, "a,5(1x,a))")
    dirs = [None, "STARTING", "ENDING"]
    site = p.sites[isite].strip()
    nfield1 = _contar_campos(m.inpline1)
    if nfield1 != 4:
        E.w(m.writeunit, formstr1, pid(E), "E03", modnam, m.nfield, "IS AN INVALID NUMBER OF FIELDS FOR KEYWORD SECTOR")
        m.lbad = True
        return
    nfield1 -= 1
    datafield = getfields(E, i1, nfield1)
    isec = 0
    v, iflag, _ = lread(datafield[1], ["i"])
    if iflag == 0:
        isec = v[0]
        if isec < p.minsec or isec > nsec:
            E.w(m.writeunit, formstr2, pid(E), "E75", modnam, "INVALID SECTOR NUMBER FOR", site,
                "SITE SURFACE CHARACTERISTICS:", isec)
            m.lbad = True
        else:
            p.save_sectors_goodsec = True
    else:
        E.w(m.writeunit, formstr3, pid(E), "E75", modnam, "INVALID SECTOR NUMBER FOR", site,
            "SITE SURFACE CHARACTERISTICS:", datafield[1].strip())
        m.lbad = True
    for i in (1, 2):
        v, iflag, _ = lread(datafield[i + 1], ["f"])
        if iflag == 0:
            d = v[0]
            if d < 0.0 or d > 360.0:
                E.w(m.writeunit, formstr4, pid(E), "E75", modnam, "INVALID", dirs[i], "DIRECTION FOR", site,
                    "SITE SURFACE CHARACTERISTICS:", d)
                m.lbad = True
            else:
                if p.save_sectors_goodsec:
                    nyr = p.pbldates[2][1] - p.pbldates[1][1] + 1
                    for iyr in range(1, p.nsc_years + 1):
                        iyr1 = p.sc_years[iyr] - p.pbldates[1][1] + 1
                        if iyr1 > 0 and iyr <= nyr:
                            p.tsectors[i][isec][iyr1] = d
        else:
            E.w(m.writeunit, formstr5, pid(E), "E75", modnam, "INVALID", dirs[i], "DIRECTION FOR", site,
                "SITE SURFACE CHARACTERISTICS:", datafield[i + 1].strip())
            m.lbad = True
