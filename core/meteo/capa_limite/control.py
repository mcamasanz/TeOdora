# -*- coding: utf-8 -*-
"""Traducción de AERMET 26135 (US EPA, dominio público): lectura del fichero de control
(módulo READ_INPUT: readinp, check_line, job_path)."""
import os

from .comun import checkfile, fmt_msg, getunit, pid
from .estado import OUTPUT_UNIT
from .formato import ch, fx, sub, fread


def _mayus(s):
    return s.upper() if s.isascii() else "".join(c.upper() if "a" <= c <= "z" else c for c in s)


def readinp(E):
    """READINP. Devuelve False si el fichero de control no existe (el original hace STOP)."""
    from . import sondeos, obs_superficie, estacion_local, control_cl as pbl
    m = E.m
    modnam = fx("READINP", 10)
    formstr = fmt_msg(E, "a,1x,a)")
    if not os.path.isfile(m.inpfile.rstrip()):
        E.w(OUTPUT_UNIT, "(3(1x,a))", "Input file", m.inpfile.strip(), "not found")
        return False
    with open(m.inpfile.rstrip(), "r", encoding="latin-1", newline=None) as fh:
        lineas = fh.read().split("\n")
    if lineas and lineas[-1] == "":
        lineas.pop()
    m.linenum = 0
    for raw in lineas:
        m.inpline = raw[:m.linelen]
        m.linenum += 1
        m.ilen = len(m.inpline.rstrip(" "))
        m.lbad = False
        m.ikey = 0
        if m.ilen > 0 and m.inpline[0:2] != "**":
            m.inpline1 = _mayus(m.inpline)
            check_line(E)
            if not m.lbad:
                if m.ipath == 1:
                    job_path(E)
                    if not m.lbad1 and m.lbad:
                        m.lbad1 = True
                elif m.ipath == 2:
                    sondeos.upper_path(E)
                    if not m.lbad1 and m.lbad:
                        m.lbad1 = True
                elif m.ipath == 3:
                    obs_superficie.surf_path(E)
                    if not m.lbad1 and m.lbad:
                        m.lbad1 = True
                elif m.ipath == 4 or m.ipath == 5:
                    estacion_local.os_path(E)
                    if not m.lbad1 and m.lbad:
                        m.lbad1 = True
                elif m.ipath == 6:
                    pbl.pbl_path(E)
                    if not m.lbad1 and m.lbad:
                        m.lbad1 = True
            else:
                if not m.lbad1:
                    m.lbad1 = True
    if m.lbad1:
        return True

    lp, ls = m.lpath, m.lstage
    wu = m.writeunit
    if ls[1] or ls[2]:
        if lp[5] and (lp[3] or lp[4]):
            if ls[1] and ls[2]:
                E.w(wu, "(12x,a3,5x,a10,6(1x,a))", "E07", modnam,
                    "INVALID PATHS CHOSEN FOR STAGES 1 AND 2;", m.pathid[5], "WITH", m.pathid[3],
                    "OR", m.pathid[4])
            else:
                m.istage = 1 if ls[1] else 2
                E.w(wu, "(12x,a3,5x,a10,1x,a,1x,i2,5(1x,a))", "E07", modnam,
                    "INVALID PATHS CHOSEN FOR STAGE", m.istage, m.pathid[5], "WITH", m.pathid[3],
                    "OR", m.pathid[4])
            m.lbad1 = True
        elif not lp[2] and not lp[3] and not lp[4] and not lp[5]:
            if ls[1] and ls[2]:
                E.w(wu, "(12x,a3,5x,a10,1x,a)", "E07", modnam, "NO PATHS LISTED FOR STAGES 1 AND 2")
            else:
                m.istage = 1 if ls[1] else 2
                E.w(wu, "(12x,a3,5x,a10,1x,a,1x,i1)", "E07", modnam, "NO PATHS LISTED FOR", m.istage)
            m.lbad1 = True
        else:
            if ls[1] and ls[2]:
                E.w(wu, "(12x,a3,5x,a10,1x,a)", "I01", modnam, "PROCESSING STAGES 1 AND 2")
            else:
                m.istage = 1 if ls[1] else 2
                E.w(wu, "(12x,a3,5x,a10,1x,a,1x,i1)", "I01", modnam, "PROCESSING STAGE", m.istage)

    if not m.ljbkeywords[1]:
        m.rpt_unit = OUTPUT_UNIT
    if not m.ljbkeywords[2]:
        m.msg_unit = OUTPUT_UNIT
    if not lp[1]:
        E.w(m.msg_unit, "(12x,a3,5x,a10,2(1x,a))", "E06", modnam, m.pathid[1], "PATHWAY IS MISSING")
        m.lbad1 = True
    else:
        if not m.ljbkeywords[2]:
            E.w(m.msg_unit, formstr, pid(E), "E08", modnam, "MISSING MANDATORY KEYWORD",
                m.keywrd[2])
            m.lbad1 = True

    if not m.lbad1:
        if not lp[2] and not lp[3] and not lp[4] and not lp[5] and not lp[6]:
            for i in range(2, m.npath + 1):
                if not lp[i]:
                    E.w(m.writeunit, "(12x,a3,5x,a10,2(1x,a))", "E06", modnam, m.pathid[i],
                        "PATHWAY IS MISSING")
            m.lbad1 = True
        else:
            if lp[2]:
                m.ipath = 2
                sondeos.up_test(E)
                for istation in range(1, E.up.nstation + 1):
                    if not E.up.upstage1[istation]:
                        sondeos.up_stage2(E, istation)
                    if m.lbad and not m.lbad1:
                        m.lbad1 = True
            if lp[3]:
                m.ipath = 3
                obs_superficie.sf_test(E)
                if not E.sf.sfstage1:
                    obs_superficie.sf_stage2(E)
                if m.lbad and not m.lbad1:
                    m.lbad1 = True
            if lp[4] or lp[5]:
                m.ipath = 4 if lp[4] else 5
                estacion_local.os_test(E)
                if not E.os.osstage1:
                    estacion_local.os_stage2(E)
                if m.lbad and not m.lbad1:
                    m.lbad1 = True
            if lp[6]:
                m.ipath = 6
                pbl.pbl_test(E)
                if m.lbad and not m.lbad1:
                    m.lbad1 = True
    return True


def check_line(E):
    m = E.m
    L = m.inpline1
    ilen = m.ilen
    modnam = fx("CHECK_LINE", 10)
    formstr = fmt_msg(E, "3(a,1x),i3)")
    m.lbad = False
    istart = 0
    q1 = q2 = False
    sq1 = sq2 = False
    par1 = par2 = False
    m.nfield = 1
    i = 1
    while i <= ilen and istart == 0:
        if ch(L, i) != " ":
            istart = i
        i += 1
    tiene_format = "FORMAT" in L
    for i in range(istart, ilen):
        ci = ch(L, i)
        if i > 1:
            cm, cp = ch(L, i - 1), ch(L, i + 1)
            if (ci == '"' or ci == "'") and (cm == " " or cp == " " or cm == "," or cp == ","):
                if not q1:
                    q1 = True
                    sq1 = ci != '"'
                else:
                    q2 = True
                    sq2 = ci != '"'
            if tiene_format and ci == "(" and (cm == " " or cm == ",") and not par1:
                par1 = True
        cp = ch(L, i + 1)
        if (((cp == " " and ci != " " and ci != ",") or (cp == "," and ci != "," and ci != " "))
                and ((q1 and q2) or (not q1 and not q2))
                and ((par1 and par2) or (not par1 and not par2))):
            m.nfield += 1
            q1 = q2 = False
    if (sq1 and not sq2) or (not sq1 and sq2):
        E.w(m.writeunit, "(12x,a3,5x,a10,3(1x,a),i3)", "E01", modnam, "MIX OF SINGLE AND DOUBLE QUOTES",
            pid(E).strip(), " FOUND LINE NUMBER:", m.linenum)
        m.lbad = True

    curr = E.m.__dict__.setdefault("_curr_path", 0)
    tok = sub(L, istart, ilen).strip()
    if m.nfield == 1:
        lfound = False
        m.ipath = 1
        while not lfound and m.ipath <= m.npath:
            if tok == m.pathid[m.ipath]:
                lfound = True
            else:
                m.ipath += 1
        if lfound:
            if not m.lpath[m.ipath]:
                m.lpath[m.ipath] = True
                if m.ipath == 7:
                    E.w(m.writeunit, "(12x,a3,5x,a10,2(1x,a))", "W01", modnam, m.pathid[m.ipath],
                        "PATH IS OBSOLETE; ASSOCIATED KEYWORDS WILL BE IGNORED")
                if m.ipath == 6:
                    m.lstage[2] = True
            else:
                m.lbad = True
                E.w(m.writeunit, "(12x,a3,5x,a10,3(1x,a),i3)", "E01", modnam, "DUPLICATE ENTRY FOR PATH",
                    m.pathid[m.ipath], "FOUND LINE NUMBER:", m.linenum)
        else:
            if tok == m.keywrd[3] or tok == m.keywrd[25] or tok == m.keywrd[36]:
                lp = m.lpath
                if curr == 1 or (not lp[1] and not lp[2] and not lp[3] and not lp[4] and not lp[5]
                                 and not lp[6]):
                    m.ipath = 1
                    if tok == m.keywrd[3]:
                        m.ikey = 3
                    elif tok == m.keywrd[25]:
                        m.ikey = 25
                    else:
                        m.ikey = 36
                    lfound = True
                else:
                    getunit(E)
                    E.w(m.writeunit, "(12x,a3,5x,a10,3(1x,a),i3)", "E01", modnam,
                        "INVALID PLACEMENT FOR KEYWORD", L.strip(), "LINE NUMBER:", m.linenum)
                    m.lbad = True
            elif tok == m.keywrd[11]:
                lfound = True
                m.ikey = 11
                if curr == 2:
                    m.ipath = 2
                else:
                    getunit(E)
                    E.w(m.writeunit, "(12x,a3,5x,a10,3(1x,a),i3)", "E01", modnam,
                        "INVALID PLACEMENT FOR KEYWORD", L.strip(), "LINE NUMBER:", m.linenum)
                    m.lbad = True
            else:
                getunit(E)
                E.w(m.writeunit, "(12x,a3,5x,a10,3(1x,a),i3)", "E01", modnam, "INVALID PATH",
                    L.strip(), "LINE NUMBER:", m.linenum)
                m.lbad = True
    else:
        firstblank = 0
        i = istart
        while firstblank == 0:
            if ch(L, i) == " " or ch(L, i) == ",":
                firstblank = i
            i += 1
        word = sub(L, istart, firstblank - 1).strip()
        m.ikey = 1
        lfound = False
        while not lfound and m.ikey <= m.nkeys:
            if word == m.keywrd[m.ikey]:
                lfound = True
            else:
                m.ikey += 1
        if lfound:
            m.lkey[m.ikey] = True
            if (m.ikey == 4 and m.ipath != 6) or m.ikey == 7:
                m.lstage[1] = True
            lp = m.lpath
            if m.ikey <= 2 and not lp[1] and not lp[2] and not lp[3] and not lp[4] and not lp[5] \
                    and not lp[6]:
                lp[1] = True
                m.ipath = 1
        else:
            getunit(E)
            if m.ipath <= m.npath:
                E.w(m.writeunit, formstr, pid(E), "E01", modnam, "INVALID KEYWORD:", word,
                    "LINE NUMBER:", m.linenum)
            else:
                E.w(m.writeunit, formstr, "UNKNOWN   ", "E01", modnam, "INVALID KEYWORD:", word,
                    "LINE NUMBER:", m.linenum)
            m.lbad = True
    m._curr_path = m.ipath


def job_path(E):
    m = E.m
    modnam = fx("JOB_PATH", 10)
    formstr1 = fmt_msg(E, "a,1x,a)")
    formstr2 = fmt_msg(E, "i3,2(1x,a))")
    getunit(E)
    form1 = "(a%3d)" % m.flength
    if m.ikey == 0:
        for k in range(1, m.njbkeys + 1):
            m.ljbkeywords[k] = False
        return
    i = m.inpline1.find(m.keywrd[m.ikey].strip()) + 1
    i1 = len(m.keywrd[m.ikey].rstrip())
    if m.ikey <= 3 or m.ikey == 25 or m.ikey == 36:
        if m.ikey == 36:
            m.ikey = 4
        if m.ikey == 25:
            m.ikey = 5
        if not m.ljbkeywords[m.ikey]:
            m.ljbkeywords[m.ikey] = True
            if m.ikey == 4:
                m.noprint = True
                m.ikey = 36
            if m.ikey == 5:
                m.debug = True
                m.ikey = 25
        else:
            E.w(m.writeunit, formstr1, pid(E), "E03", modnam, "DUPLICATE ENTRY OF KEYWORD:",
                m.keywrd[m.ikey].strip())
            m.lbad = True
            if m.ikey == 4:
                m.ikey = 36
            if m.ikey == 5:
                m.ikey = 25
            return
    else:
        E.w(m.writeunit, formstr1, pid(E), "E01", modnam, "INVALID KEYWORD:", m.keywrd[m.ikey].strip())
        m.lbad = True
        return
    resto = sub(m.inpline, i + i1 + 1, m.ilen)
    if m.ikey == 1:
        if m.nfield != 2:
            E.w(OUTPUT_UNIT, formstr2, pid(E), "E03", modnam, m.nfield,
                "IS AN INVALID NUMBER OF FIELDS FOR KEYWORD", m.keywrd[m.ikey].strip())
            m.lbad = True
        else:
            m.rptfile = fread(form1, resto, [("a", m.flength)])[0][0]
            m.rptfile, lgood = checkfile(E, m.rpt_unit, m.rptfile, 2)
            if not lgood:
                m.rpt_unit = OUTPUT_UNIT
    elif m.ikey == 2:
        if m.nfield != 2:
            E.w(OUTPUT_UNIT, formstr2, pid(E), "E03", modnam, m.nfield,
                "IS AN INVALID NUMBER OF FIELDS FOR KEYWORD", m.keywrd[m.ikey].strip())
            m.lbad = True
        else:
            m.msgfile = fread(form1, resto, [("a", m.flength)])[0][0]
            m.msgfile, lgood = checkfile(E, m.msg_unit, m.msgfile, 2)
            if not lgood:
                m.msg_unit = OUTPUT_UNIT
            else:
                getunit(E)
    elif m.ikey == 25:
        if m.nfield == 1:
            m.dbgfile = "aermet_debug.txt"
            m.dbgfile, lgood = checkfile(E, m.debug_unit, m.dbgfile, 2)
        elif m.nfield == 2:
            m.dbgfile = fread(form1, resto, [("a", m.flength)])[0][0]
            m.dbgfile, lgood = checkfile(E, m.debug_unit, m.dbgfile, 2)
            if not lgood:
                m.dbgfile = "aermet_debug.txt"
        elif m.nfield > 2:
            E.w(OUTPUT_UNIT, formstr2, pid(E), "E03", modnam, m.nfield,
                "IS AN INVALID NUMBER OF FIELDS FOR KEYWORD", m.keywrd[m.ikey].strip())
            m.lbad = True
    else:
        if m.nfield != 1:
            E.w(OUTPUT_UNIT, formstr2, pid(E), "E03", modnam, m.nfield,
                "IS AN INVALID NUMBER OF FIELDS FOR KEYWORD", m.keywrd[m.ikey].strip())
            m.lbad = True
