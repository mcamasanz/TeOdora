# -*- coding: utf-8 -*-
"""Traducción de AERMET 26135 (US EPA, dominio público): módulo REPORTS (fichero de informe).

input_summ, dates_loc, sum_files, audit_summ, sfchar_sum, obs_sum, pbl_sum, write_msg."""
from .comun import start_stop
from .formato import fwrite, fx, fread

AST = "*" * 28 + " "  # character(len=29) asterisks='****************************' (28 * + blanco)


def _w(E, fmt, *items):
    E.w(E.m.rpt_unit, fmt, *items)


def input_summ(E):
    m, u, s, o, p = E.m, E.up, E.sf, E.os, E.pb
    success_str = "UN-SUCCESSFUL" if (m.lbad1 or p.lbadout) else "SUCCESSFUL"
    _w(E, "(2(1x,a/))", "AERMET_SETUP", success_str)
    _w(E, "(1x,a,1x,a5/)", "AERMET VERSION ", m.versn)
    start_stop(E, 1, m.rpt_unit)
    _w(E, "(/2(1x,a))", "RUNSTREAM CONTROL FILE:", m.inpfile.strip())
    if m.ljbkeywords[3]:
        _w(E, "(/,1x,a)", "THIS RUN ONLY CHECKS THE RUNSTREAM INPUT")
    if m.lstage[1] and m.lstage[2]:
        stage_str = "1 AND 2"
    elif m.lstage[1]:
        stage_str = "1"
    else:
        stage_str = "2"
    _w(E, "(//1x,a29,1x,a,1x,a29,//2(1x,a))", AST, "INPUT SUMMARY", AST, "PROCESSING STAGES", stage_str)
    _w(E, "(///1x,i1,a/)", 1, ".  JOB FILE NAMES")
    for jk, kk, fname in ((2, 2, m.msgfile), (1, 1, m.rptfile), (5, 25, m.dbgfile)):
        if m.ljbkeywords[jk]:
            fs = "OPEN" if E.abierto(fname) else "NOT OPEN"
            _w(E, "(1x,a10,1x,a8,1x,a)", fx(m.keywrd[kk], 10), fx(fs, 8), fname.strip())
        else:
            _w(E, "(1x,a10,1x,a)", fx(m.keywrd[kk], 10), "NO FILE")
    for i in range(2, m.npath):
        _w(E, "(///1x,i1,a1,2(1x,a))", i, ".", m.pathid[i], "DATA")
        if not m.lpath[i]:
            _w(E, "(/1x,a/)", "NO PROCESSING REQUESTED")
            continue
        if i == 2:
            for istation in range(1, u.nstation + 1):
                if u.nstation == 2:
                    _w(E, "(/a,2(1x,a)/)", "PROCESSING", u.station_type[istation], "STATION")
                dates_loc(E, i, u.upstarts[istation], u.upends[istation], u.updates1[istation], u.upid[istation],
                          u.uplat[istation], u.uplon[istation], u.upgmt2lst[istation], u.upelev[istation])
                if istation == 1:
                    ik1, ik2, ik3, ik4 = 1, 3, 4, 7
                else:
                    ik1, ik2, ik3, ik4 = 10, 12, 13, 15
                sum_files(E, 1, u.lupkeywords[ik1], m.up_inpfile[istation])
                sum_files(E, 2, u.lupkeywords[ik2], m.up_extfile[istation])
                sum_files(E, 3, u.lupkeywords[ik3], m.up_qafile[istation])
                _w(E, "(/1x,a,1x,i4,1x,a)", "UPPER AIR DATA ABOVE", u.uptop, "NOT EXTRACTED")
                if u.lupkeywords[ik4]:
                    _w(E, "(/1x,a)", "UPPER AIR AUTOMATIC DATA CHECKS ARE: ON")
                    if u.lmodify[1][istation]:
                        _w(E, "(/1x,a)", "DELETE MANDATORY LEVELS")
                    if u.lmodify[2][istation]:
                        _w(E, "(/1x,a)", "RESET WIND DIRECTION FOR UAWS=0")
                    if u.lmodify[3][istation]:
                        _w(E, "(/1x,a)", "INTERPOLATE MISSING UATT AND UATD")
                else:
                    _w(E, "(/1x,a)", "UPPER AIR AUTOMATIC DATA CHECKS ARE: OFF")
        elif i == 3:
            dates_loc(E, i, s.sfstart, s.sfend, s.sfdates, s.sfid, s.sflat, s.sflon, s.sfgmt2lst, s.sfelev)
            if s.lasos and s.iasos > 0:
                _w(E, "(/1x,a,1x,i8)", "ASOS COMMISSION DATE:", s.asoscommdates[s.iasos].commisdate)
            sum_files(E, 1, s.lsfkeywords[1], m.sf_inpfile)
            if m.lstage[2]:
                sum_files(E, 4, s.lsfkeywords[9], m.one_minfile)
            sum_files(E, 2, s.lsfkeywords[3], m.sf_extfile)
            sum_files(E, 3, s.lsfkeywords[4], m.sf_qafile)
        elif i == 6:
            dates_loc(E, i, p.pblstart, p.pblend, p.pbldates, p.pblid, p.pbllat, p.pbllon, p.pblgmt2lst, p.pblelev)
            sum_files(E, 5, p.lpblkeywords[6], m.sfc_outfile)
            sum_files(E, 6, p.lpblkeywords[10], m.pfl_outfile)
            _w(E, "(2(/1x,a)/)", "METPREP PROCESSING OPTIONS", "PROCESS                     OPTION  DESCRIPTION")
            F = "(1x,a,t30,a7,1x,a)"
            A = [None] + [fx(a, 10) for a in m.actions[1:]]
            if p.litems[1]:
                if p.lactions[1]:
                    _w(E, F, "WIND DIRECTION", A[1], "WIND DIRECTIONS ARE RAMDOMNIZED")
                else:
                    _w(E, F, "WIND DIRECTION", A[2], "WIND DIRECTIONS ARE NOT RAMDOMNIZED")
            else:
                _w(E, F, "WIND DIRECTION ", "DEFAULT", "WIND DIRECTIONS ARE RAMDOMNIZED")
            if p.litems[2]:
                if p.lactions[3]:
                    _w(E, F, m.items[2].strip(), A[3], "NWS WINDS AND TEMPS SUBSTITUED FOR MISSING ONSITE DATA")
                else:
                    _w(E, F, m.items[2].strip(), A[3], "NWS WINDS AND TEMPS ARE NOT SUBSTITUED FOR MISSING ONSITE DATA")
            if p.litems[3]:
                if p.lactions[4]:
                    if not p.run_coare:
                        _w(E, F, "STABLE BOUNDARY LAYER", A[4], "BULK-RICHARSON METHOD USED")
                        _w(E, "(t38,a,2(1x,f6.1))", "DELTA-T HEIGHTS (M):", o.osdt_hts[1][1], o.osdt_hts[1][2])
                    else:
                        _w(E, F, "STABLE BOUNDARY LAYER", A[4], "BULK-RICHARDSON METHOD REQUESTED BUT NOT USED")
                if p.lactions[7]:
                    if not p.run_coare:
                        _w(E, F, "STABLE BOUNDARY LAYER", A[7], "ADJUSTED U* USED")
                    else:
                        _w(E, F, "STABLE BOUNDARY LAYER", A[7], "ADJUSTED U* REQUESTED BUT NOT USED")
            if p.litems[4]:
                if p.lactions[5]:
                    _w(E, F, "ASOS WIND ADJUSTMENT", A[5], "ASOS WIND ARE NOT ADJUSTED FOR TRUNCATION")
                else:
                    _w(E, F, "ASOS WIND ADJUSTMENT", "DEFAULT", "ASOS WIND ARE ADJUSTED FOR TRUNCATION")
            if p.subcloud:
                _w(E, F, "CLOUD COVER", A[8], "CLOUD COVER SUBSTITUTED")
            else:
                _w(E, F, "CLOUD COVER", A[9], "CLOUD COVER NOT SUBSTITUTED")
            if p.subtemp:
                _w(E, F, "TEMPERATURE", A[10], "TEMPERATURE SUBSTITUTED")
            else:
                _w(E, F, "TEMPERATURE", A[11], "TEMPERATURE NOT SUBSTITUTED")
            if m.lpath[2]:
                if p.litems[5]:
                    if p.lactions[6]:
                        _w(E, F, "UPPER AIR SELECTION", A[6], "SOUNDING SELECTION BASED ON SUNRISE TIME")
                if p.lpblkeywords[9]:
                    _w(E, "(1x,a,2(i3,1x))", "SOUNDING TIME WINDOW:", p.snding_win[1], p.snding_win[2])
                if p.sub_upper:
                    if m.use_second:
                        _w(E, "(1x,a)", "UPPER AIR SUBSTITUTION WILL BE SUBSTITUTED WITH SECONDARY STATION INCLUDED")
                        if p.check_sec_first:
                            _w(E, "(1x,a)", "SECONDARY STATION CHECKED FIRST FOR FOR PRIMARY STATION MISSING DAY")
                        else:
                            _w(E, "(1x,a)", "PRIMARY STATION CHECKED FIRST FOR PRIMARY STATION MISSING DAY")
                    else:
                        _w(E, "(1x,a)", "UPPER AIR SUBSTITUTION WILL BE SUBSTITUTED WITH PRIMARY STATION ONLY")
                    if p.lpblkeywords[24]:
                        _w(E, "(1x,a,2(i3,1x))", "SUBSTITUTION TIME WINDOW (DAYS):", p.day_window[1], p.day_window[2])
                else:
                    _w(E, "(1x,a)", "UPPER AIR SUBSTITUTION WILL NOT BE SUBSTITUTED")
            else:
                if o.osvars[o.mix_var].lread:
                    _w(E, "(1x,a,t30,a)", "UPPER AIR SELECTION", "NONE    USE ONSITE MIXING HEIGHTS")
            if p.lpblkeywords[17] and m.lpath[4]:
                _w(E, "(1x,a,1x,f4.2)", "ASOS 1-MINUTE THRESHOLD SPEED (M/S):", s.asos_thresh)
            if not p.run_coare and p.run_coare_orig:
                _w(E, "(/1x,a)", "COARE ORIGINALLY REQUESTED BUT NOT BEING RUN; SEE MESSAGE FILE FOR DETAILS")
        else:
            dates_loc(E, i, o.osstart, o.osend, o.osdates, o.osid, o.oslat, o.oslon, o.osgmt2lst, o.oselev)
            sum_files(E, 1, o.loskeywords[1], m.os_inpfile)
            sum_files(E, 3, o.loskeywords[4], m.os_qafile)
            if m.lpath[5]:
                _w(E, "(/1x,a)", "GRID CELL TYPE: OVERLAND" if o.overland else "GRID CELL TYPE: OVERWATER")
            _w(E, "(/1x,a,1x,i2)", "NUMBER OF OBSERVATIONS/HOUR:", o.nobs_hr)
            if o.loskeywords[9]:
                _w(E, "(/1x,a,2(1x,f7.2))", "DELTA T HEIGHTS:", o.osdt_hts[1][1], o.osdt_hts[1][2])
            if o.loskeywords[11]:
                _w(E, "(/1x,a,1x,f6.2)", "THRESHOLD WIND SPEED (M/S): ", o.threshspeed)
            if o.loskeywords[10] and o.os_heights is not None:
                _w(E, "(/1x,a/)", "HEIGHTS FOR TOWER DATA (M) BASED ON THE OSHEIGHTS KEYWORD:")
                for j in range(o.noshts, 0, -1):
                    _w(E, "(1x,f7.2)", o.os_heights[j])


def dates_loc(E, i, startdate, enddate, dates1, statid, lat, lon, gmt2lst, elev):
    valdate = startdate > 0 and enddate > 0 and startdate <= enddate
    if valdate:
        _w(E, "(/1x,a,1x,2(i2.2,a),i4,1x,a,1x,2(i2.2,a),i4)", "PROCESSING DATES:", dates1[1][2], "/", dates1[1][3],
           "/", dates1[1][1], "-", dates1[2][2], "/", dates1[2][3], "/", dates1[2][1])
    else:
        _w(E, "(/1x,a)", "ONE OR MORE DATES ARE INVALID")
    adj = fx(statid, 8).rstrip().rjust(8)
    if i == 6:
        _w(E, "(/20x,a/19x,a/1x,a,9x,a8,2(6x,f7.2),11x,i3/)",
           "SITE ID     LATITUDE    LONGITUDE     TIME ADJUSTMENT",
           "--------     --------    ---------     ---------------", "LOCATION:", adj, lat, lon, gmt2lst)
    else:
        _w(E, "(/20x,a/19x,a/1x,a,9x,a8,2(6x,f7.2),11x,i3,10x,f9.2/)",
           "SITE ID     LATITUDE    LONGITUDE     TIME ADJUSTMENT    ELEVATION",
           "--------     --------    ---------     ---------------    ---------", "LOCATION:", adj, lat, lon,
           gmt2lst, elev)


def sum_files(E, itype, lwrite, fname):
    ftypes = [None, "DATA", "EXTRACT", "QAOUT", "ASOS1MIN", "OUTPUT", "PROFILE"]
    if lwrite:
        os_ = "OPEN" if E.abierto(fname) else "NOT OPEN"
        _w(E, "(2(1x,a),t18,a8,2x,a)", ftypes[itype], "FILE:", fx(os_, 8), fname.strip())
    else:
        _w(E, "(2(1x,a))", ftypes[itype], "FILE: NO FILENAME INPUT")


def audit_summ(E):
    m, u, s, o, p = E.m, E.up, E.sf, E.os, E.pb
    qa_header_str = "VARIABLE   MISSING VALUE   LOWER BOUND          UPPER BOUND"
    f = {1: "(1x,a4,6x,f9.2,7x,2(1x,a20))",
         2: "(/1x,a,t23,a,t38,a1,t49,a1,t58,a,t70,a,t83,a1/t37,a,t46,a,t58,a,t70,a,t80,a)",
         3: "(1x,a15,t25,a,4(3x,i8),8x,f6.2)", 4: "(t25,a4,4(3x,i8),8x,f6.2)",
         5: "(/1x,a15,t25,a,4(3x,i8),8x,f6.2)", 6: "(/1x,a,/4(/1x,a,1x,i8))",
         7: "(/t2,a,t17,a1,t28,a1,t37,a,t49,a,t62,a1/t16,a,t25,a,t37,a,t49,a,t59,a)",
         8: "(t2,a4,2x,4(3x,i8),8x,f6.2)", 9: "(2(/t2,a),7(/i7,1x,a))",
         10: "(1x,a10,t25,a4,4(3x,i8),8x,f6.2)", 11: "(t25,a4,4(3x,i8),8x,f6.2)",
         12: "(/1x,a10,t25,a4,4(3x,i8),8x,f6.2)"}
    upsum = [None, "CALM WIND CONDITIONS (WS=0, WD=0):", "ZERO WIND SPEED; NON-ZERO WIND DIRECTION:",
             "DEW POINT GREATER THAN DRY BULB TEMPERATURE:", "NUMBER OF SOUNDINGS THAT DO NOT EXTEND TO 5000 M:"]
    sfsum = [None, "CALM WINDS (WDIR = 0, WSPD = 0)", "WDIR = 0, WSPD > 0", "WDIR > 0, WSPD = 0",
             "WINDS FLAGGED AS VARIABLE", "TEMPERATURE < DEWPOINT", "PRECIP WITHOUT WEATHER CODE",
             "WEATHER CODE WITHOUT PRECIP"]
    ossum = [None, "CALM WINDS (< THRESHOLD)", "NO INPUT WS WITH WD", "NO INPUT WD WITH WS", "TEMPERATURE < DEWPOINT"]
    if m.lstage[1]:
        _w(E, "(//1x,a29,1x,a,1x,a29)", AST, "QA SUMMARY", AST)
    if ((((u.lupkeywords[9] or u.lupkeywords[4]) and u.upstage1[1]) or
         ((u.lupkeywords[16] or u.lupkeywords[13]) and u.upstage1[2])) and not u.lbadup):
        _w(E, "(//1x,a)", "UPPERAIR DATA")
    for istation in range(1, u.nstation + 1):
        ik1, ik2 = (9, 4) if istation == 1 else (17, 13)
        if u.nstation == 2:
            _w(E, "(/a,2(1x,a)/)", "PROCESSING", u.station_type[istation], "STATION")
        if u.lupkeywords[ik1] and u.upstage1[istation] and not u.lbadup and u.have_soundings[istation]:
            _w(E, "(//1x,a)", qa_header_str)
            for iv in range(1, u.nup_audit_vars[istation] + 1):
                iv1 = u.up_audit_index[iv][istation]
                uv = u.upvars[iv1]
                lt, gt = ("<", ">") if uv.lincbound[istation] else ("<=", ">=")
                low_str1 = fwrite("(f9.2)", float(uv.lowbound[istation]) * uv.conv[istation])[0]
                low_str = lt.strip() + " " + low_str1.strip()
                up_str1 = fwrite("(f9.2)", float(uv.upbound[istation]) * uv.conv[istation])[0]
                up_str = gt.strip() + " " + up_str1.strip()
                _w(E, f[1], uv.varname.strip(), float(uv.missval[istation]), fx(low_str, 20), fx(up_str, 20))
            _w(E, f[2], "LEVEL", "VARIABLE", "#", "#", "LOWER", "UPPER", "%", "OBS", "MISSING", "BOUND", "BOUND",
               "ACCEPTED")
            for ilayer in range(1, 11):
                if ilayer == 1:
                    up_layers = "SURFACE"
                elif ilayer == 10:
                    up_layers = fwrite("(a,i4,a)", "     > ", 8 * u.up_inc, " M")[0]
                else:
                    up_layers = fwrite("(i4,a,i4,a)", (ilayer - 2) * u.up_inc, " - ", (ilayer - 1) * u.up_inc, " M")[0]
                for iv in range(1, u.nup_audit_vars[istation] + 1):
                    iv1 = u.up_audit_index[iv][istation]
                    if ilayer == 1 and iv1 >= 7:
                        continue
                    c = u.up_audit_counts[iv][ilayer]
                    tot_good = c[1][istation] - c[2][istation] - c[3][istation] - c[4][istation]
                    cnt = [c[k][istation] for k in range(1, 5)]
                    pct = (float(tot_good) / float(cnt[0])) * 100.0 if cnt[0] else float("nan")
                    nm = u.upvars[iv1].varname.strip()
                    if iv == 1:
                        if ilayer == 1:
                            _w(E, f[3], up_layers.strip(), nm, *cnt, pct)
                        else:
                            _w(E, f[5], up_layers.strip(), nm, *cnt, pct)
                    else:
                        _w(E, f[4], nm, *cnt, pct)
        if u.lupkeywords[ik2] and u.upstage1[istation] and not u.lbadup:
            _w(E, f[6], "NON-QA SUMMARY CHECKS", upsum[1], u.wind_stats[1][istation], upsum[2],
               u.wind_stats[2][istation], upsum[3], u.tempstat[istation], upsum[4], u.nsnd_5k[istation])
        if not u.lbadup and u.upstage1[istation]:
            _w(E, "(/1x,a,i5)", "NUMBER OF DAYS WITH NO SOUNDINGS:", u.no_sound_days[istation])
            if u.no_sound_days[istation] > 0:
                _w(E, "(1x,a)", "SEE MESSAGE CODE I28 IN MESSAGE FILE FOR DATES")
            _w(E, "(/1x,a,i5)", "NUMBER OF DAYS WITH SOUNDINGS BUT NO AM SOUNDINGS:", u.no_am_days[istation])
            if u.no_am_days[istation] > 0:
                _w(E, "(1x,a)", "SEE MESSAGE CODE I29 IN MESSAGE FILE FOR DATES")
    if m.lpath[3] and s.sfstage1 and not s.lbadsfc:
        _w(E, "(2(//1x,a))", "SURFACE DATA", qa_header_str)
        for iv in range(1, s.nsf_audit_vars + 1):
            iv1 = s.sf_audit_index[iv]
            sv = s.sfvars[iv1]
            lt, gt = ("<", ">") if sv.lincbound else ("<=", ">=")
            for isplit in range(1, s.nsplit + 1):
                low_str = lt + " " + fwrite("(f9.2)", s.lowbound[iv][isplit])[0].strip()
                up_str = gt + " " + fwrite("(f9.2)", s.upbound[iv][isplit])[0].strip()
                if iv1 in (4, 5, 19) or 13 <= iv1 <= 18:
                    nm = sv.varname[0:2] if isplit == 1 else sv.varname[2:4]
                    _w(E, f[1], nm.strip(), float(sv.missval), fx(low_str, 20), fx(up_str, 20))
                else:
                    if isplit == 1:
                        _w(E, f[1], sv.varname.strip(), float(sv.missval), fx(low_str, 20), fx(up_str, 20))
        _w(E, f[7], "VARIABLE", "#", "#", "LOWER", "UPPER", "%", "OBS", "MISSING", "BOUND", "BOUND", "ACCEPTED")
        for iv in range(1, s.nsf_audit_vars + 1):
            iv1 = s.sf_audit_index[iv]
            sv = s.sfvars[iv1]
            for isplit in range(1, s.nsplit + 1):
                c = s.sf_audit_counts[iv][isplit]
                tot_good = c[1] - c[2] - c[3] - c[4]
                pct = (float(tot_good) / float(c[1])) * 100.0 if c[1] else float("nan")
                if iv1 in (4, 5, 19) or 13 <= iv1 <= 18:
                    nm = sv.varname[0:2] if isplit == 1 else sv.varname[2:4]
                    _w(E, f[8], nm.strip(), c[1], c[2], c[3], c[4], pct)
                else:
                    if isplit == 1:
                        _w(E, f[8], sv.varname.strip(), c[1], c[2], c[3], c[4], pct)
        _w(E, f[9], "WIND, TEMPERATURE, AND PRECIPITATION CHECKS", "NUMBER OF HOURS:", s.sf_windstats[1], sfsum[1],
           s.sf_windstats[2], sfsum[2], s.sf_windstats[3], sfsum[3], s.nsfc[12], sfsum[4], s.sf_tempstat, sfsum[5],
           s.precip_wx[1], sfsum[6], s.precip_wx[2], sfsum[7])
        if s.sfformats[7].lsfform:
            _w(E, "(2(/1x,a,1x,i8))", "NUMBER OF DICARDED ISHD RECORDS (see ISHD_discard.txt):",
               s.nsfc[6] + s.nsfc[7] + s.nsfc[9] + s.nsfc[10],
               "NUMBER OF OVERWRITTEN ISHD RECORDS (see ISHD_replace.txt):", s.nsfc[8])
    audit_report = False
    iv = 1
    if o.osstage1:
        while iv <= o.nos_audit_vars and not audit_report:
            iv1 = o.os_audit_index[iv][2]
            if o.osvars[iv1].laudit:
                audit_report = True
            iv += 1
    if (m.lpath[4] or m.lpath[5]) and o.osstage1 and audit_report and not o.lbados:
        ipath1 = 4 if m.lpath[4] else 5
        apath = m.pathid[ipath1].strip() + " DATA"
        _w(E, "(2(//1x,a))", apath, qa_header_str)
        firstday = 1
        firsthr = 1
        lfound = False
        while firstday <= o.nosdays and not lfound:
            firsthr = 1
            while firsthr <= 24 and not lfound:
                if o.os_info[firstday].have_obs[firsthr]:
                    lfound = True
                else:
                    firsthr += 1
            if not lfound:
                firstday += 1
        ov = o.osvars
        for iv in range(1, o.nos_audit_vars + 1):
            iv1 = o.os_audit_index[iv][2]
            v = ov[iv1]
            lt, gt = ("<", ">") if v.lincbound else ("<=", ">=")
            low_str = lt + " " + fwrite("(f9.2)", float(v.lowbound) * v.conv)[0].strip()
            up_str = gt + " " + fwrite("(f9.2)", float(v.upbound) * v.conv)[0].strip()
            vname = v.varname if iv1 < o.height_var else fwrite("(a2)", v.varname[0:2].strip())[0]
            _w(E, f[1], vname.strip(), float(v.missval), fx(low_str, 20), fx(up_str, 20))
        nswitch = 2 if ov[5].lread else 1
        for iswitch in range(nswitch, 0, -1):
            _w(E, "(//a/)", "HOURLY VALUES" if iswitch == 1 else "SUB-HOURLY VALUES")
            _w(E, f[2], "LEVEL", "VARIABLE", "#", "#", "LOWER", "UPPER", "%", "OBS", "MISSING", "BOUND", "BOUND",
               "ACCEPTED")
            first_multi = False
            for ilayer in range(1, o.nlevel + 1):
                for iv in range(1, o.nos_audit_vars + 1):
                    iv1 = o.os_audit_index[iv][2]
                    v = ov[iv1]
                    if iv > 1:
                        first_multi = (o.os_audit_index[iv][2] >= o.height_var and
                                       o.os_audit_index[iv - 1][2] < o.height_var)
                    else:
                        if iv1 >= 26:
                            first_multi = True
                    if ((ilayer > v.nlevels and v.nlevels > 0) or (ilayer > 1 and v.nlevels == 0) or
                            ilayer < v.firstlev):
                        continue
                    vname = v.varname if iv1 < o.height_var else fwrite("(a2)", v.varname[0:2].strip())[0]
                    if ilayer == 1 and iv1 < o.height_var:
                        up_layers = "SCALAR"
                    else:
                        up_layers = fwrite("(f8.3,1x,a1)", float(o.osdata1[1, ilayer, firsthr, firstday]), "M")[0]
                    c = o.os_audit_counts
                    cnt = [int(c[iv, ilayer, iswitch, k]) for k in range(1, 5)]
                    tot_good = cnt[0] - cnt[1] - cnt[2] - cnt[3]
                    pct = (float(tot_good) / float(cnt[0])) * 100.0 if cnt[0] else float("nan")
                    if iv == 1 or first_multi:
                        if ilayer == 1:
                            _w(E, f[10], up_layers.strip(), vname.strip(), *cnt, pct)
                        else:
                            _w(E, f[12], up_layers.strip(), vname.strip(), *cnt, pct)
                    else:
                        _w(E, f[11], vname.strip(), *cnt, pct)
            if ((ov[o.wind_vars[1]].lread and ov[o.wind_vars[2]].lread) or
                    (ov[o.temp_var].lread and ov[o.dewpt_var].lread)):
                _w(E, "(2(/t2,a))", "WIND AND TEMPERATURE CHECKS (IF APPLICABLE)", "NUMBER OF OBS:")
            if ov[o.wind_vars[1]].lread and ov[o.wind_vars[2]].lread:
                _w(E, "(3(/i7,1x,a))", o.os_windstats[iswitch][1], ossum[1], o.os_windstats[iswitch][2], ossum[3],
                   o.os_windstats[iswitch][3], ossum[3])
            if ov[o.temp_var].lread and ov[o.dewpt_var].lread:
                _w(E, "(/i7,1x,a)", o.os_tempstat[iswitch], ossum[4])


def sfchar_sum(E):
    m, p = E.m, E.pb
    months = [None, "JANUARY", "FEBRUARY", "MARCH", "APRIL", "MAY", "JUNE", "JULY", "AUGUST", "SEPTEMBER",
              "OCTOBER", "NOVEMBER", "DECEMBER"]
    seasons = [None, "WINTER", "SPRING", "SUMMER", "AUTUMN"]
    hemisphere = [None, "NORTHERN", "SOUTHERN"]
    m2s = {1: [None, [None, 1, 2, 12], [None, 3, 4, 5], [None, 6, 7, 8], [None, 9, 10, 11]],
           2: [None, [None, 6, 7, 8], [None, 9, 10, 11], [None, 1, 2, 12], [None, 3, 4, 5]]}
    f1 = "(/a,1x,i4,2(1x,a)/t12,a,1x,i3)"
    f2 = "(/1x,a4,t9,a,t22,a,t38,a,t53,a,t65,a,t80,a)"
    f3 = "(1x,i4,t9,a10,t22,f4.0,t38,f4.0,t52,f5.2,t65,f5.2,t79,f7.4)"
    nsite = 2 if p.sec_sc else 1
    _w(E, "(//1x,a29,1x,a,1x,a29)", AST, "SFC CHARACTERISTICS SUMMARY", AST)
    writeseason = [None, False, False]
    for iyr in range(p.pbldates[1][1], p.pbldates[2][1] + 1):
        iyr1 = iyr - p.pbldates[1][1] + 1
        if p.nfreq1[iyr1] == 4:
            writeseason[1] = True
        if p.sec_sc:
            if p.nfreq2[iyr1] == 4:
                writeseason[2] = True
    for isite in range(1, nsite + 1):
        nf = p.nfreq1 if isite == 1 else p.nfreq2
        ns = p.nsectors1 if isite == 1 else p.nsectors2
        sct = p.sectors1 if isite == 1 else p.sectors2
        sfc = p.sfc_char1 if isite == 1 else p.sfc_char2
        _w(E, "(//2(1x,a))", p.sites[isite].strip(), "SITE CHARACTERISTICS")
        if writeseason[isite]:
            _w(E, "(/3(1x,a)//,1x,a)", "MONTH-SEASON ASSIGNMENTS:", hemisphere[p.ihem[isite]], "HEMISPHERE",
               "SEASON     MONTHS")
            for ifreq in range(1, 5):
                _w(E, "(1x,a,t13,2(a,1x),a)", seasons[ifreq], *[fx(months[m2s[p.ihem[isite]][ifreq][j]], 10)
                                                                  for j in range(1, 4)])
        freqname1 = ""
        for iyr in range(p.pbldates[1][1], p.pbldates[2][1] + 1):
            iyr1 = iyr - p.pbldates[1][1] + 1
            if nf[iyr1] == 1:
                freqname, freqname1 = "ANNUAL", ""
            elif nf[iyr1] == 4:
                freqname, freqname1 = "SEASONAL", "SEASON"
            else:
                freqname, freqname1 = "MONTHLY", "MONTH"
            _w(E, f1, "YEAR:", iyr, "FREQUENCY" if isite == 1 else "FREQUENCY:", freqname, "NUMBER OF SECTORS:",
               ns[iyr1])
        _w(E, f2, "YEAR", freqname1, "BEGIN SECTOR", "END SECTOR", "ALBEDO", "BOWEN RATIO", "ROUGHNESS LENGTH (M)")
        for iyr in range(p.pbldates[1][1], p.pbldates[2][1] + 1):
            iyr1 = iyr - p.pbldates[1][1] + 1
            for ifreq in range(1, nf[iyr1] + 1):
                if nf[iyr1] == 1:
                    atemp = ""
                elif nf[iyr1] == 4:
                    atemp = seasons[ifreq]
                else:
                    atemp = months[ifreq]
                for isec in range(1, ns[iyr1] + 1):
                    a, b, z = sfc[isec][ifreq][iyr1]
                    _w(E, f3, iyr, fx(atemp, 10), sct[1][isec][iyr1], sct[2][isec][iyr1], a, b, z)


def obs_sum(E):
    m, p = E.m, E.pb
    months = [None, "JAN", "FEB", "MAR", "APR", "MAY", "JUN", "JUL", "AUG", "SEP", "OCT", "NOV", "DEC"]
    obs_lines = [None, "NWS UPPER AIR  OBS", "NWS SURFACE    OBS", "", "1-MIN ASOS HR  OBS"]
    if m.lpath[4]:
        obs_lines[3] = "ONSITE         OBS"
    if m.lpath[5]:
        obs_lines[3] = "PROG           OBS"
    if not m.lpath[4] and not m.lpath[5]:
        obs_lines[3] = "ONSITE/PROG    OBS"
    nd = p.npbldays
    if nd < 10:
        nlines = 1
    else:
        nlines = nd // 10 if nd % 10 == 0 else nd // 10 + 1
    _w(E, "(//1x,a29,1x,a,1x,a29)", AST, "OBSERVATIONS PER DAY SUMMARY", AST)
    _w(E, "(//1x,a,1x,i2.2,a1,a3,a1,i4)", "STARTING:", p.pbldates[1][3], "-", months[p.pbldates[1][2]], "-",
       p.pbldates[1][1])
    _w(E, "(1x,a,1x,i2.2,a1,a3,a1,i4)", "ENDING:", p.pbldates[2][3], "-", months[p.pbldates[2][2]], "-",
       p.pbldates[2][1])
    totals = [None, 0, 0, 0, 0]
    for d in range(1, nd + 1):
        for o_ in range(1, 5):
            totals[o_] += p.pbl_obs[o_][d]
    _w(E, "(/t20,a/)", "***** TOTAL OBSERVATION COUNTS *****")
    for o_ in range(1, 5):
        _w(E, "(1x,a18,1x,i6)", obs_lines[o_], totals[o_])
    _w(E, "(/t20,a)", "***** DAILY OUTPUT STATISTICS *****")
    d2 = 0
    for iline in range(1, nlines + 1):
        yrstr = [" "] * 19
        d1 = d2 + 1
        if iline < nlines and nlines > 1:
            d2 = d2 + 10
        else:
            d2 = nd
        ndays = d2 - d1 + 1
        dates = []
        yr1 = yr2 = 0
        for d in range(d1, d2 + 1):
            adate = "%08d" % p.sfc_data[d].sfcdate
            dates.append(adate[4:6] + "/" + adate[6:8])
            if d == d1:
                yr1 = int(adate[0:4])
            if d == d2:
                yr2 = int(adate[0:4])
        if yr2 - yr1 == 0:
            t = fwrite("(i4,1x,a6)", yr1, "MO/DY:")[0]
            yrstr[8:19] = list(t[:11].ljust(11))
        else:
            t = fwrite("(i4,a1,i2.2,1x,a6)", yr1, "-", yr2 - (yr2 // 100) * 100, "MO/DY:")[0]
            yrstr[5:19] = list(t[:14].ljust(14))
        formstr = fwrite("(a,i6,a)", "(/a19,", ndays, "(3x,a5))")[0]
        _w(E, formstr, "".join(yrstr), *dates)
        if ndays > 1:
            formstr = fwrite("(a,i1,a)", "(2x,a18,3x,i2,", ndays - 1, "(6x,i2))")[0]
        else:
            formstr = "(2x,a18,3x,i2)"
        for o_ in range(1, 5):
            _w(E, formstr, obs_lines[o_], *[p.pbl_obs[o_][d] for d in range(d1, d2 + 1)])


def pbl_sum(E):
    m, p, s, o = E.m, E.pb, E.sf, E.os
    _w(E, "(//1x,a29,1x,a,1x,a29)", AST, "PBL PROCESSING SUMMARY", AST)
    if m.lpath[2] and not o.osvars[o.mix_var].lread:
        _w(E, "(/1x,a,1x,i6)", "NUMBER OF DAYS WITH NO CONVECTIVE CONDITIONS:", p.n_conv_miss)
    _w(E, "(/1x,a,1x,i6)", "NUMBER OF TOTAL CALMS:", p.pbl_windstats[1])
    if m.lpath[3]:
        if s.lasos and s.lsfkeywords[9] and p.lpblkeywords[17]:
            _w(E, "(1x,a,1x,f3.1,1x,a5,1x,i6/1x,a)", "NUMBER OF 1-MINUTE CALMS: (<", s.asos_thresh, "M/S):",
               p.pbl_windstats[2], "THESE HOURS ARE A SUBSET OF THE TOTAL CALMS")
        _w(E, "(1x,a,1x,i6//)", "NUMBER OF VARIABLE WINDS:", p.pbl_windstats[3])
    if p.subcloud:
        _w(E, "(/1x,a,1x,i6)", "NUMBER OF SUBSTITUTIONS (INTERPOLATION) FOR MISSING CLOUD COVER:", p.n_cloud_sub)
    if p.subtemp:
        _w(E, "(/1x,a,1x,i6)", "NUMBER OF SUBSTITUTIONS (INTERPOLATION) FOR MISSING TEMPERATURE:", p.n_temp_sub)
    _w(E, "(/1x,a,1x,i8)", "NUMBER OF BAD SURFACE RECORDS IN SURFACE FILE:", p.nsfc_over)
    if p.nsfc_over > 0:
        for ivar in range(1, 26):
            if p.bad_sfc_vars[ivar] > 0:
                _w(E, "(5x,a,1x,a6,1x,i8)", "NUMBER OF OVERFLOW RECORDS VARIABLE", fx(p.sfcvar[ivar], 6),
                   p.bad_sfc_vars[ivar])
    _w(E, "(/1x,a,1x,i8)", "NUMBER OF BAD PROFILE RECORDS IN SURFACE FILE:", p.npfl_over)
    if p.npfl_over > 0:
        for ivar in range(1, 12):
            if p.bad_pfl_vars[ivar] > 0:
                _w(E, "(5x,a,1x,a6,1x,i8)", "NUMBER OF OVERFLOW RECORDS VARIABLE", fx(p.pflvar[ivar], 6),
                   p.bad_pfl_vars[ivar])


def write_msg(E):
    m = E.m
    msgtype = [None, "ERROR", "WARNING", "INFORMATION", "QA"]
    mtype = [None, "E", "W", "I", "Q"]
    _w(E, "(//1x,a29,1x,a,1x,a29/)", AST, "MESSAGE SUMMARY", AST)
    lmessage = E.abierto(m.msgfile) if m.msgfile.strip() else False
    if lmessage:
        f = E.units[m.msg_unit]
        nmessages = [None, 0, 0, 0, 0]
        n1 = {}
        for rec in f.regs:
            v, io, _ = fread("(12x,a1,i2)", rec, [("a", 1), "i"])
            if io != 0:
                break
            st = v[0]
            icode = v[1] if len(v) > 1 else 0
            itype = {"E": 1, "W": 2, "I": 3}.get(st, 4)
            nmessages[itype] += 1
            n1[(icode, itype)] = n1.get((icode, itype), 0) + 1
        f.ptr = len(f.regs)
        for itype in range(1, 5):
            _w(E, "(//2(1x,a),1x,i8,1x,a/)", msgtype[itype], "MESSAGES", nmessages[itype], "MESSAGES")
            for icode in range(1, 101):
                if n1.get((icode, itype), 0) > 0:
                    _w(E, "(1x,a1,i2.2,a1,1x,i8)", mtype[itype], icode, ":", n1[(icode, itype)])
    else:
        _w(E, "(//1x,a//)", "NO MESSAGE FILE TO READ")
