# -*- coding: utf-8 -*-
"""Traducción de AERMET 26135 (US EPA, dominio público): módulo PBL, etapa 2.

pbl_proc y la física de la capa límite: sundat, check_obs, upp_dates, get_sound, winds, temps,
clouds, substitute, press, rh, precip, stability, calc_ustar, nr_ang, netrad, sfc_chars,
have_data, bulk_rich, check_flux, mech_ht, read_sound, conv_ht, wstar, vptg, profile,
sfc_header, writefiles, check_surf, check_prof.

COARE (algoritmo sobre agua) queda fuera del alcance."""
import datetime as _dt
import math

from . import tablas as T
from .comun import data_dates, fmt_msg, jday as _jday, leapyr, numdays, pid
from .estado import OUTPUT_UNIT
from .formato import dsign, fwrite, fx, nint, sngl
from .control_cl import NoTraducido, aersurf

R4_01 = sngl(0.1)          # literal simple 0.1 de NR_ANG (-0.1*angle); SFC_CHARS usa 0.1_r8
R4_24097 = sngl(240.97)
SQRT2_MINSIGV = math.sqrt(2.0) * 0.2


class Dia:
    """Un elemento de sfc_data (tipo sfdat1): 24 horas de variables de superficie."""
    __slots__ = ("sfcdate", "jday", "hflux", "ustar", "wstar", "vptg", "zic", "zim", "mol", "zo",
                 "bowen", "albedo", "wspd", "wdir", "wind_ht", "airtemp", "temp_ht", "pamt", "rh",
                 "pres", "theta_star", "ipcode", "ccvr", "windsrcflag", "subflag")

    def __init__(self):
        self.sfcdate = 0
        self.jday = 0
        self.hflux = [-999.0] * 25
        self.ustar = [-9.0] * 25
        self.wstar = [-9.0] * 25
        self.vptg = [-9.0] * 25
        self.zic = [-999.0] * 25
        self.zim = [-999.0] * 25
        self.mol = [-99999.0] * 25
        self.zo = [-9.0] * 25
        self.bowen = [-9.0] * 25
        self.albedo = [-9.0] * 25
        self.wspd = [999.0] * 25
        self.wdir = [999.0] * 25
        self.wind_ht = [-9.0] * 25
        self.airtemp = [999.0] * 25
        self.temp_ht = [-9.0] * 25
        self.pamt = [-9.0] * 25
        self.rh = [999.0] * 25
        self.pres = [99999.0] * 25
        self.theta_star = [-9.0] * 25
        self.ipcode = [9999] * 25
        self.ccvr = [99] * 25
        self.windsrcflag = ["NAD"] * 25
        self.subflag = ["NoSubs"] * 25


class Perfil:
    """Un elemento de pfl_data (tipo pfldat)."""
    __slots__ = ("pfldate", "ht", "speed", "dir", "airtemp", "sigma_a", "sigma_w")


def _mat(nh, nd, val):
    return [[val] * (nd + 1) for _ in range(nh + 1)]


# ------------------------------------------------------------------------------------------
def pbl_proc(E, ahora=None):
    from . import estacion_local
    m, p, u, s, o = E.m, E.pb, E.up, E.sf, E.os
    if p.run_coare:
        raise NoTraducido("COARE")
    modnam = fx("PBL_PROC", 10)
    F = {k: fmt_msg(E, v) for k, v in {
        2: "a,1x,a8,1x,2(i2.2,a1),i2.2)", 3: "a20,1x,a,1x,f6.2,1x,a)", 4: "a20,1x,a,2(1x,f5.2,1x,a))",
        5: "a20,1x,a)", 6: "a,1x,i8,1x,a)", 7: "2(a,1x),a)", 8: "a,1x,a20,1x,a)", 9: "a)",
        10: "a,1x,f6.1,1x,a,1x,a20)", 11: "a)", 12: "a,1x,a20)", 13: "a,1x,i3,1x,a)"}.items()}
    F[1] = "(1x,a,1x,2(a2,a1),a4,1x,a)"
    mu = m.msg_unit
    ov = o.osvars
    csubg = 0.1
    homin = 0.0001
    sdg2use = T.SDG2USE
    if (((u.upstage1[1] and u.nsnd[4][1] - u.nsnd[5][1] == 0) or
         (not u.upstage1[1] and m.lstage[2] and u.nsnd[2][1] == 0)) and s.nsfc[4] == 0 and o.nos[2] == 0):
        E.w(mu, F[9], pid(E), "E70", modnam, "NO VALID DATA, ABORT PROCESSING")
        p.lbadpbl = True
        return
    t = ahora or _dt.datetime.now()
    E.w(mu, F[2], pid(E), "I70", modnam, "PBL CALCULATIONS BEGIN: ", t.strftime("%Y%m%d"), t.hour, ":",
        t.minute, ":", t.second)
    if m.debug:
        if m.lpath[4] or m.lpath[5]:
            p.os_ipath = 4 if m.lpath[4] else 5
    ol_ow_msg = False
    if o.overland and not o.osstage1:
        for v in range(5, o.nosvars + 1):
            if (v in (o.tsea_var, o.sstd_var, o.hwav_var, o.twav_var, o.rdow_var) and ov[v].lread
                    and not ol_ow_msg):
                ol_ow_msg = True
                E.w(mu, F[9], pid(E), "W60", modnam, "LOCATION IS OVERLAND BUT DATA FLAG INDICATES OVERWATER")
            if ov[v].lread and v in (o.l_var, o.hflux_var, o.wstar_var, o.vptg_var, o.zo_var, o.bo_var,
                                     o.alb_var, o.lflux_var, o.tsea_var, o.sstd_var, o.hwav_var,
                                     o.twav_var, o.rdow_var):
                E.w(mu, F[7], pid(E), "I80", modnam, "LOCATION IS OVERLAND; VARIABLE", ov[v].varname.strip(),
                    "WILL NOT BE USED FROM STAGE 1 BUT CALCULATED IN STAGE 2")
    if ov[o.l_var].lread and not o.overland:
        E.w(mu, F[11], pid(E), "I84", modnam,
            "MONIN-OBUKHOV LENGTH WILL BE USED FOR STABILITY DETERMINATION WHEN L IS NOT MISSING")
    else:
        E.w(mu, F[11], pid(E), "I84", modnam, "SOLAR ANGLE APPROACH WILL BE USED FOR STABILITY DETERMINATION")
    nd = p.npbldays = numdays(p.pblstart, p.pblend)
    p.sfc_data = [None] + [Dia() for _ in range(nd)]
    p.pbl_obs = [[0] * (nd + 1) for _ in range(6 if u.lsecondary else 5)]
    wind_reset = _mat(24, nd, False)
    orig_wind_speed = _mat(24, nd, 0.0)
    p.windsrc = _mat(24, nd, 0)
    p.tempsrc = _mat(24, nd, 0)
    p.cloudsrc = _mat(24, nd, 0)
    p.up_sunrise = [[-999.0] * (u.nstation + 1) for _ in range(nd + 1)]
    p.up_sunset = [[-999.0] * (u.nstation + 1) for _ in range(nd + 1)]
    p.local_sunrise = [-999.0] * (nd + 1)
    p.local_sunset = [-999.0] * (nd + 1)
    p.sun_ang = _mat(24, nd, -999.0)
    p.day_obs = [False] * (nd + 1)
    p.up_obs = [False] * (nd + 1)
    p.asos_hr = _mat(24, nd, False)
    p.nws_obs = _mat(24, nd, False)
    p.os_obs = _mat(24, nd, False)
    p.one_min_obs = _mat(24, nd, False)
    p.got_eq_ccvr = _mat(24, nd, False)
    p.cbl = _mat(24, nd, False)
    p.rho = _mat(24, nd, -9.0)
    if m.lpath[2]:
        p.iup = [1] * (nd + 1)
        p.isnd = [1] * (nd + 1)
    if m.lpath[3]:
        p.isf = [1] * (nd + 1)
        if m.lkey[32]:
            p.isf1 = [1] * (nd + 1)
    if m.lpath[4] or m.lpath[5]:
        p.ios = [1] * (nd + 1)
    p.nrad = float(ov[o.nrad_var].missval)
    p.inso = float(ov[o.inso_var].missval)
    if m.lpath[4] or m.lpath[5]:
        p.pfl_levels = o.nlevel
    else:
        estacion_local.onsite_init(E)
        ov = o.osvars
    nl = p.pfl_levels
    p.pfl_nlevels = _mat(24, nd, nl)
    p.pfl_data = [[None] * (nd + 1) for _ in range(25)]
    for istation in range(1, u.nstation + 1):
        if m.lpath[2] and not p.lactions[6]:
            ul = u.uplon[istation]
            if ul < 0.0:
                mz = -int(-ul / 15.0 + 0.5)
            elif ul > 0.0:
                mz = -int(-ul / 15.0 - 0.5)
            else:
                mz = 0
            p.my_sounding[istation] = sdg2use[mz + 12]
            p.target_hr_gmt[istation] = abs(p.my_sounding[istation])
            p.snd_hr_gmt[1][istation] = abs(p.my_sounding[istation]) + p.snding_win[1]
            p.snd_hr_gmt[2][istation] = abs(p.my_sounding[istation]) + p.snding_win[2]
            if p.snd_hr_gmt[1][istation] < 0:
                p.snd_hr_gmt[1][istation] = 25 + p.snd_hr_gmt[1][istation]
            if p.snd_hr_gmt[2][istation] > 24:
                p.snd_hr_gmt[2][istation] = 26 - p.snd_hr_gmt[2][istation]
        p.temp_upgmt[istation] = int(-u.uplon[istation] / 15.0)
        if u.upgmt2lst[istation] == 0:
            if abs(p.temp_upgmt[istation]) <= 1:
                p.temp_upgmt[istation] = 0
            else:
                if u.lsecondary:
                    pre = "PRIMARY " if istation == 1 else "SECONDARY "
                    E.w(mu, F[13], pid(E), "W88", modnam, pre + "UPPER AIR GMT TO LST", u.upgmt2lst[istation],
                        "DOES NOT ALIGN WITH UPPER AIR LONGITUDE")
                    E.w(mu, F[13], pid(E), "I91", modnam, pre + "UPPER AIR SUNRISE/SUNSET GMT TO LST",
                        p.temp_upgmt[istation], "BASED ON UPPER AIR LONGITUDE")
                else:
                    E.w(mu, F[13], pid(E), "W88", modnam, "UPPER AIR GMT TO LST", u.upgmt2lst[istation],
                        "DOES NOT ALIGN WITH UPPER AIR LONGITUDE")
                    E.w(mu, F[13], pid(E), "I91", modnam, "UPPER AIR SUNRISE/SUNSET GMT TO LST",
                        p.temp_upgmt[istation], "BASED ON UPPER AIR LONGITUDE")
        else:
            p.temp_upgmt[istation] = u.upgmt2lst[istation]
    temp_pblgmt = int(-p.pbllon / 15.0)
    if p.pblgmt2lst == 0:
        if abs(temp_pblgmt) <= 1:
            temp_pblgmt = 0
        else:
            E.w(mu, F[13], pid(E), "W88", modnam, "LOCAL GMT TO LST", p.pblgmt2lst,
                "DOES NOT ALIGN WITH LOCAL LONGITUDE")
            E.w(mu, F[13], pid(E), "I91", modnam, "LOCAL AIR SUNRISE/SUNSET GMT TO LST", temp_pblgmt,
                "BASED ON LOCAL LONGITUDE")
    else:
        temp_pblgmt = p.pblgmt2lst
    # valores iniciales de los perfiles
    onsite_pfl = (m.lpath[4] or m.lpath[5]) and o.nos[2] > 0
    sa0 = ov[o.sa_var].missval * ov[o.sa_var].conv
    sw0 = ov[o.sw_var].missval * ov[o.sw_var].conv
    if onsite_pfl:
        sp0 = ov[o.wind_vars[2]].missval * ov[o.wind_vars[2]].conv
        dr0 = ov[o.wind_vars[1]].missval * ov[o.wind_vars[1]].conv
        tt0 = ov[o.temp_var].missval * ov[o.temp_var].conv
        hts0 = [None] + [float(o.osdata1[1, ilev, 1, 1]) for ilev in range(1, nl + 1)]
    else:
        sv = s.sfvars
        sp0 = float(sv[11].missval)
        dr0 = float(sv[10].missval)
        tt0 = sv[7].missval * sv[7].conv
        hts0 = [None] + [s.nws_hgt] * nl
    iday1 = 0
    for y in range(p.pbldates[1][1], p.pbldates[2][1] + 1):
        leap = leapyr(y)
        imon1 = p.pbldates[1][2] if y == p.pbldates[1][1] else 1
        imon2 = p.pbldates[2][2] if y == p.pbldates[2][1] else 12
        for mm in range(imon1, imon2 + 1):
            idy1 = 1
            idy2 = m.days[mm] + (1 if (mm == 2 and leap) else 0)
            if mm == imon1 and y == p.pbldates[1][1]:
                idy1 = p.pbldates[1][3]
            if mm == imon2 and y == p.pbldates[2][1]:
                idy2 = p.pbldates[2][3]
            for dd in range(idy1, idy2 + 1):
                iday1 += 1
                sd = p.sfc_data[iday1]
                sd.sfcdate = y * 10000 + mm * 100 + dd
                for h in range(1, 25):
                    pf = Perfil()
                    pf.pfldate = sd.sfcdate
                    pf.sigma_a = [None] + [sa0] * nl
                    pf.sigma_w = [None] + [sw0] * nl
                    pf.speed = [None] + [sp0] * nl
                    pf.dir = [None] + [dr0] * nl
                    pf.airtemp = [None] + [tt0] * nl
                    pf.ht = list(hts0)
                    p.pfl_data[h][iday1] = pf
                iw1 = (mm + 9) % 12
                iw2 = (iw1 * 153 + 2) // 5 + dd + 58
                if leap:
                    iw3 = 366
                    iw2 += 1
                else:
                    iw3 = 365
                sd.jday = 1 + iw2 % iw3
                angs = [None] * 25
                p.local_sunrise[iday1], p.local_sunset[iday1] = sundat(E, p.pbllat, p.pbllon, temp_pblgmt,
                                                                      sd.jday, angs)
                for h in range(1, 25):
                    p.sun_ang[h][iday1] = angs[h]
                if m.lpath[2]:
                    for istation in range(1, u.nstation + 1):
                        p.up_sunrise[iday1][istation], p.up_sunset[iday1][istation] = sundat(
                            E, u.uplat[istation], u.uplon[istation], p.temp_upgmt[istation], sd.jday)
                check_obs(E, 1, iday1)
    if not p.run_coare:
        nsite = 2 if p.sec_sc else 1
        ny = p.pbldates[2][1] - p.pbldates[1][1] + 1
        for isite in range(1, nsite + 1):
            if isite == 1:
                p.nfreq1 = [0] * (ny + 1)
                p.nsectors1 = [0] * (ny + 1)
            else:
                p.nfreq2 = [0] * (ny + 1)
                p.nsectors2 = [0] * (ny + 1)
            aersurf(E, 2, isite)
    m.sfc_charfile1 = p.yrstr1 = m.sfc_charfile2 = p.yrstr2 = None
    if p.lbadpbl:
        return
    sfc_header(E)
    for d in range(1, nd + 1):
        sd = p.sfc_data[d]
        adate = "%8d" % sd.sfcdate
        if not m.noprint:
            E.w(OUTPUT_UNIT, F[1], "Stage 2: Initial data assignments for month/day/year", adate[4:6], "/",
                adate[6:8], "/", adate[0:4], "LST")
        if not p.day_obs[d]:
            continue
        for h in range(1, 25):
            if not p.nws_obs[h][d] and p.one_min_obs[h][d]:
                p.nws_obs[h][d] = p.one_min_obs[h][d]
            wind_reset[h][d], orig_wind_speed[h][d] = winds(E, d, h)
            temps(E, d, h)
            p.oncloud = have_data(E, d, h, o.cloud_var)
            if p.oncloud and o.overland and m.lpath[5]:
                p.oncloud = False
            clouds(E, d, h)
    for d in range(1, nd + 1):
        sd = p.sfc_data[d]
        adate = "%8d" % sd.sfcdate
        if not m.noprint:
            E.w(OUTPUT_UNIT, F[1], "Stage 2: PBL calculations for month/day/year", adate[4:6], "/",
                adate[6:8], "/", adate[0:4], "LST")
        if not p.day_obs[d]:
            writefiles(E, d)
            continue
        calc_conv = False
        cblhr1 = 1
        posflux = False
        firstcbl = False
        station_use, lsub1, lsub2 = check_obs(E, 2, d)
        if p.up_obs[d]:
            si = u.sound_info[p.iup[d]][station_use]
            if si.nlevels[p.isnd[d]] == 1 and \
                    u.updata.get(station_use, p.iup[d], p.isnd[d])[2][1] == 0.0:
                p.up_obs[d] = False
                if not ov[o.mix_var].lread:
                    E.w(mu, F[6], pid(E), "I78", modnam, "SOUNDING FOR DATE", sd.sfcdate,
                        "HAS ONLY ONE LEVEL AT SURFACE, NO CONVECTIVE PARAMETERS WILL BE CALCULATED")
            else:
                read_sound(E, d, station_use, lsub1)
        else:
            if not ov[o.mix_var].lread and not p.run_coare:
                E.w(mu, F[6], pid(E), "I78", modnam, "NO SOUNDING AVAILABLE FOR DATE", sd.sfcdate,
                    "NO CONVECTIVE PARAMETERS WILL BE CALCULATED")
        if not p.up_obs[d] and not ov[o.mix_var].lread and not p.run_coare:
            p.n_conv_miss += 1
        for h in range(1, 25):
            date_hr_str = fwrite("(a5,1x,i8,1x,a2,1x,i2.2)", "DATE:", sd.sfcdate, "HR", h)[0]
            if not p.nws_obs[h][d] and not p.os_obs[h][d] and not p.one_min_obs[h][d]:
                continue
            p.nrad = float(ov[o.nrad_var].missval)
            p.inso = float(ov[o.inso_var].missval)
            ostemp = False
            if (((p.subtemp and p.tempsrc[h][d] == 0) or (p.subcloud and p.cloudsrc[h][d] == 0)) and
                    ((h == 1 and d > 1) or (1 < h < 24) or (h == 24 and d < nd))):
                ostemp = substitute(E, d, h, ostemp)
            profile(E, d, h, ostemp)
            press(E, d, h, ostemp)
            rh_ht = 999.0
            have_rh = False
            if p.nws_obs[h][d] or (p.os_obs[h][d] and (ov[o.rh_var].lread or (ov[o.temp_var].lread and
                                                                             ov[o.dewpt_var].lread))):
                rh_ht, have_rh = rh(E, d, h)
            if p.nws_obs[h][d] or (p.os_obs[h][d] and (ov[o.prcp_vars[1]].lread or ov[o.prcp_vars[2]].lread)):
                precip(E, d, h)
            p.onustar = have_data(E, d, h, o.ustar_var)
            if p.onustar and o.overland and m.lpath[5]:
                p.onustar = False
            p.onmol = have_data(E, d, h, o.l_var)
            if p.onmol and o.overland:
                p.onmol = False
            p.onhflux = have_data(E, d, h, o.hflux_var)
            if p.onhflux and o.overland:
                p.onhflux = False
            p.onlflux = have_data(E, d, h, o.lflux_var)
            if p.onlflux and o.overland:
                p.onlflux = False
            p.onwstar = have_data(E, d, h, o.wstar_var)
            if p.onwstar and o.overland:
                p.onwstar = False
            p.onmix = have_data(E, d, h, o.mix_var)
            p.onvptg = have_data(E, d, h, o.vptg_var)
            if p.onvptg and o.overland:
                p.onvptg = False
            p.onnrad = have_data(E, d, h, o.nrad_var)
            p.oninso = have_data(E, d, h, o.inso_var)
            if not p.run_coare:
                stability(E, d, h)
            if not firstcbl and p.cbl[h][d]:
                firstcbl = True
                cblhr1 = h
            if p.tempsrc[h][d] == 0 or not p.havepress:
                E.w(mu, F[5], pid(E), "I72", modnam, date_hr_str, "TEMPERATURE AND/OR PRESSURE MISSING, SKIP CALCULATIONS")
                continue
            if p.tempsrc[h][d] > 0 and (sd.airtemp[h] < 208.0 or sd.airtemp[h] > 348.0):
                E.w(mu, F[3], pid(E), "W75", modnam, date_hr_str, "AIR TEMPERATURE", sd.airtemp[h], "< 208 K OR > 348 K")
            p.rho[h][d] = sd.pres[h] * 100.0 / (m.r * sd.airtemp[h])
            rhomin = 0.90 if sd.pres[h] > 800.0 else 0.75
            if p.rho[h][d] < rhomin or p.rho[h][d] > 1.5:
                E.w(mu, F[4], pid(E), "W75", modnam, date_hr_str, "DENSITY", p.rho[h][d], "<", rhomin, "OR > 1.5")
            ustar_ratio = 1.0
            osd = o.osdata1
            iosd = p.ios[d] if (m.lpath[4] or m.lpath[5]) else 1
            if p.onustar:
                us_os = float(osd[ov[o.ustar_var].readvar, 1, h, iosd])
                if wind_reset[h][d] and not p.cbl[h][d]:
                    E.w(mu, F[8], pid(E), "I85", modnam, "VALID ONSITE U* FOR", date_hr_str,
                        "WILL BE RECALCULATED BASED ON RESET WIND SPEED")
                    tu1 = calc_ustar(E, d, h, wind_reset[h][d], orig_wind_speed[h][d])[0]
                    tu2 = calc_ustar(E, d, h, wind_reset[h][d], sd.wspd[h])[0]
                    if tu1 == 0.0 or tu1 == 0.0:
                        ustar_ratio = 1.0
                        sd.ustar[h] = ustar_ratio * us_os
                    else:
                        ustar_ratio = tu2 / tu1
                        sd.ustar[h] = ustar_ratio * us_os
                elif not wind_reset[h][d]:
                    sd.ustar[h] = us_os
                    if m.debug:
                        if p.adjustar and not p.cbl[h][d]:
                            E.w(mu, F[8], pid(E), "I85", modnam, "VALID ONSITE U* FOR", date_hr_str,
                                "ADJUST U* NOT APPLIED")
            if p.onmol:
                l_os = float(osd[ov[o.l_var].readvar, 1, h, iosd])
                if wind_reset[h][d] and p.onustar and not p.cbl[h][d]:
                    E.w(mu, F[8], pid(E), "I86", modnam, "VALID ONSITE L FOR", date_hr_str,
                        "WILL BE SCALED BASED ON CUBED RATIO OF NEW/ORIGINAL U*")
                    sd.mol[h] = l_os * ustar_ratio * ustar_ratio * ustar_ratio
                elif not wind_reset[h][d]:
                    sd.mol[h] = l_os
            if p.onhflux:
                sd.hflux[h] = float(osd[ov[o.hflux_var].readvar, 1, h, iosd])
            if p.onnrad:
                p.nrad = float(osd[ov[o.nrad_var].readvar, 1, h, iosd])
                if not p.cbl[h][d]:
                    if abs(p.nrad - float(ov[o.nrad_var].missval)) > m.eps and p.nrad > 0.0:
                        E.w(mu, F[3], pid(E), "I76", modnam, date_hr_str, "NET RADIATION", p.nrad, "> 0 FOR STABLE HOUR")
            if p.oninso:
                p.inso = float(osd[ov[o.inso_var].readvar, 1, h, iosd])
            if p.cbl[h][d]:
                lcycle = False
                if not p.onnrad:
                    lcycle = netrad(E, d, h)
                if lcycle:
                    continue
                if abs(p.nrad - float(ov[o.nrad_var].missval)) > m.eps and not p.onhflux:
                    sd.hflux[h] = ((1.0 - csubg) * p.nrad) / (1.0 + (1.0 / sd.bowen[h]))
                if sd.hflux[h] <= 0.0 and abs(sd.hflux[h] - (-999.0)) > m.eps:
                    E.w(mu, F[3], pid(E), "I81", modnam, date_hr_str, " HEAT FLUX", sd.hflux[h],
                        "<= 0 FOR CONVECTIVE HOUR; RESET TO 0.1")
                    sd.hflux[h] = 0.1
                if sd.hflux[h] > 0.0:
                    posflux = True
                if p.onustar and wind_reset[h][d]:
                    E.w(mu, F[8], pid(E), "I86", modnam, "VALID ONSITE U* FOR", date_hr_str,
                        "WILL BE RECALCULATED BASED ON RESET WIND SPEED")
                    us_os = float(osd[ov[o.ustar_var].readvar, 1, h, iosd])
                    tu1 = calc_ustar(E, d, h, wind_reset[h][d], orig_wind_speed[h][d])[0]
                    tu2 = calc_ustar(E, d, h, wind_reset[h][d], sd.wspd[h])[0]
                    if tu1 == 0.0 or tu1 == 0.0:
                        ustar_ratio = 1.0
                        sd.ustar[h] = ustar_ratio * us_os
                    else:
                        ustar_ratio = tu2 / tu1
                        sd.ustar[h] = ustar_ratio * us_os
                if firstcbl and h == cblhr1 and sd.hflux[h] < homin:
                    firstcbl = False
                    cblhr1 = 1
                if p.onmix:
                    mx = float(osd[ov[o.mix_var].readvar, 1, h, iosd])
                    sd.zic[h] = min(mx, p.conv_max)
                    if mx > p.conv_max:
                        E.w(mu, F[10], pid(E), "I79", modnam, "CBL HT SET TO", p.conv_max, "FOR", date_hr_str)
                    if sd.zic[h] == 0.0:
                        E.w(mu, F[5], pid(E), "W75", modnam, date_hr_str, "CONVECTIVE MIXING HEIGHT = 0 M")
                    if p.onustar:
                        mech_ht(E, d, h)
                else:
                    calc_conv = True
                    if ov[o.mix_var].lread:
                        E.w(mu, F[5], pid(E), "I87", modnam, date_hr_str,
                            "CONVECTIVE MIXING HEIGHT MISSING; WILL BE CALCULATED IN CONV_HT")
                if (p.windsrc[h][d] == 0 or (sd.wspd[h] < m.eps and sd.wdir[h] < m.eps) or
                        (sd.wspd[h] > 900.0 and sd.wdir[h] > 900.0)):
                    E.w(mu, F[5], pid(E), "I72", modnam, date_hr_str, "WINDS CALM OR MISSING, SKIP CALCULATIONS")
                    continue
                if p.onmol and wind_reset[h][d] and p.onustar:
                    E.w(mu, F[8], pid(E), "I86", modnam, "VALID ONSITE L FOR", date_hr_str,
                        "WILL BE SCALED BASED ON CUBED RATIO OF NEW/ORIGINAL U*")
                    sd.mol[h] = float(osd[ov[o.l_var].readvar, 1, h, iosd]) * ustar_ratio * ustar_ratio * ustar_ratio
                if not p.onustar:
                    if p.onmol:
                        sd.ustar[h] = calc_ustar(E, d, h, wind_reset[h][d], sd.wspd[h])[0]
                    else:
                        r = calc_ustar(E, d, h, wind_reset[h][d], sd.wspd[h])
                        sd.ustar[h], sd.mol[h] = r[0], r[1]
                if p.onmix and not p.onustar:
                    mech_ht(E, d, h)
                if not p.onmol:
                    if p.onustar:
                        sd.mol[h] = (-p.rho[h][d] * m.cp * sd.airtemp[h] * (sd.ustar[h] * sd.ustar[h] * sd.ustar[h]) /
                                     (m.vonk * m.g * sd.hflux[h]))
                if p.onwstar:
                    sd.wstar[h] = float(osd[ov[o.wstar_var].readvar, 1, h, iosd])
                    if sd.wstar[h] < 0.001:
                        sd.wstar[h] = 0.001
                        E.w(mu, F[5], pid(E), "W78", modnam, date_hr_str, "W* < 0.001; RESET TO 0.001")
                else:
                    if (p.onmix and sd.mol[h] < 0.0 and abs(sd.mol[h] - (-99999.0)) > m.eps and p.rho[h][d] > 0.0
                            and 0.0 < sd.airtemp[h] < 900.0 and sd.hflux[h] > -900.0 and
                            abs(sd.hflux[h] - (-777.0)) > m.eps and sd.zic[h] > 0.0):
                        sd.wstar[h] = wstar(E, d, h)
                if p.onvptg:
                    sd.vptg[h] = max(float(osd[ov[o.vptg_var].readvar, 1, h, iosd]), 0.005)
                else:
                    if (p.onmix and sd.mol[h] < 0.0 and abs(sd.mol[h] - (-99999.0)) > m.eps and p.rho[h][d] > 0.0
                            and 0.0 < sd.airtemp[h] < 900.0 and sd.hflux[h] > -900.0 and
                            abs(sd.hflux[h] - (-777.0)) > m.eps and sd.zic[h] > 0.0):
                        if not p.up_obs[d]:
                            sd.vptg[h] = 0.005
                        else:
                            sd.vptg[h] = vptg(E, d, h)
            else:
                if p.onmix and p.onustar:
                    mech_ht(E, d, h)
                if (p.windsrc[h][d] == 0 or (sd.wspd[h] < m.eps and sd.wdir[h] < m.eps) or
                        (sd.wspd[h] > 900.0 and sd.wdir[h] > 900.0)):
                    E.w(mu, F[5], pid(E), "I72", modnam, date_hr_str, "WINDS CALM OR MISSING, SKIP CALCULATIONS")
                    continue
                stablecalcs = True
                if p.onustar:
                    if p.cloudsrc[h][d] > 0:
                        sd.theta_star[h] = 0.09 * (1.0 - 0.5 * _sq(float(sd.ccvr[h]) / 10.0))
                        stablecalcs = False
                    elif p.onmol and p.tempsrc[h][d] > 0:
                        sd.theta_star[h] = (sd.airtemp[h] / (m.vonk * m.g * sd.mol[h])) * sd.ustar[h] * sd.ustar[h]
                        stablecalcs = False
                    elif p.onhflux:
                        sd.theta_star[h] = -sd.hflux[h] / (p.rho[h][d] * m.cp * sd.ustar[h])
                        stablecalcs = False
                if p.lactions[4]:
                    bulkri = not (not stablecalcs or (p.onustar and p.onmol))
                else:
                    bulkri = False
                if bulkri and ov[o.dt01_var].lread and p.windsrc[h][d] == 1 and sd.wspd[h] > 0.0:
                    dt_os = float(osd[ov[o.dt01_var].readvar, 1, h, iosd])
                    if abs(dt_os - float(ov[o.dt01_var].missval)) > m.eps:
                        if dt_os + (o.osdt_hts[1][2] - o.osdt_hts[1][1]) * 0.0098 > 0.0:
                            stable_rate = True
                        else:
                            stable_rate = False
                            if not p.onustar:
                                sd.ustar[h] = m.vonk * sd.wspd[h] / math.log(sd.wind_ht[h] / sd.zo[h])
                            sd.theta_star[h] = 0.00001
                            if not p.onmol:
                                sd.mol[h] = 8888.0
                            E.w(mu, F[8], pid(E), "I82", modnam, "BULK RI NOT USED FOR", date_hr_str,
                                "UNSTABLE OR NEUTRAL LAPSE RATE")
                    else:
                        E.w(mu, F[8], pid(E), "I82", modnam, "BULK RI NOT USED FOR", date_hr_str, "MISSING LAPSE RATE")
                        stable_rate = False
                    if stable_rate or p.cloudsrc[h][d] == 0 or p.got_eq_ccvr[h][d]:
                        bulkri = True
                    elif p.cloudsrc[h][d] != 0 or not p.got_eq_ccvr[h][d]:
                        E.w(mu, F[8], pid(E), "I82", modnam, "BULK RI NOT USED FOR", date_hr_str,
                            "CC NOT MISSING OR DO NOT HAVE EQUIVALENT CC")
                        bulkri = False
                else:
                    if bulkri:
                        if p.windsrc[h][d] != 1:
                            E.w(mu, F[8], pid(E), "I82", modnam, "BULK RI NOT USED FOR", date_hr_str,
                                "MISSING ONSITE WINDS")
                        bulkri = False
                if bulkri:
                    bulk_rich(E, d, h)
                else:
                    if p.cloudsrc[h][d] == 0 and stablecalcs:
                        E.w(mu, F[5], pid(E), "I75", modnam, date_hr_str, "CLOUD COVER MISSING, SKIP CALCULATIONS")
                        continue
                    if not p.onustar:
                        r = calc_ustar(E, d, h, wind_reset[h][d], sd.wspd[h])
                        sd.ustar[h], sd.theta_star[h] = r[0], r[2]
                if sd.ustar[h] > 0.0 and sd.theta_star[h] > 0.0:
                    check_flux(E, d, h)
                if p.onmix:
                    mech_ht(E, d, h)
                if bulkri and (p.cloudsrc[h][d] == 0 or p.got_eq_ccvr[h][d]):
                    if sd.theta_star[h] >= 0.09:
                        sd.ccvr[h] = 0
                    else:
                        skyfract = math.sqrt((1.0 - sd.theta_star[h] / 0.09) / 0.5)
                        if skyfract <= 0.0:
                            sd.ccvr[h] = 0
                        elif skyfract >= 1.0:
                            sd.ccvr[h] = 10
                        else:
                            sd.ccvr[h] = nint(skyfract * 10.0)
                    p.cloudsrc[h][d] = 5
                if not p.onmol:
                    if sd.ustar[h] > 0.0 and sd.theta_star[h] > 0.0:
                        if p.adjustar:
                            if bulkri:
                                sd.mol[h] = (sd.airtemp[h] * sd.ustar[h] * sd.ustar[h] /
                                             (m.vonk * m.g * sd.theta_star[h]))
                            else:
                                sd.mol[h] = max((1100.0 * sd.ustar[h] * sd.ustar[h]),
                                                sd.airtemp[h] * sd.ustar[h] * sd.ustar[h] /
                                                (m.vonk * m.g * sd.theta_star[h]))
                        else:
                            sd.mol[h] = (sd.airtemp[h] * sd.ustar[h] * sd.ustar[h] /
                                         (m.vonk * m.g * sd.theta_star[h]))
                if not p.onhflux and sd.ustar[h] > 0.0 and sd.theta_star[h] > 0.0:
                    sd.hflux[h] = -sd.theta_star[h] * p.rho[h][d] * m.cp * sd.ustar[h]
                lcycle = False
                if not p.onnrad:
                    lcycle = netrad(E, d, h)
                if lcycle:
                    continue
            if abs(sd.mol[h] - (-99999.0)) > m.eps:
                if abs(sd.mol[h]) > 8888.0:
                    sd.mol[h] = 8888.0 * dsign(1.0, sd.mol[h])
                if abs(sd.mol[h]) < 1.0:
                    sd.mol[h] = 1.0 * dsign(1.0, sd.mol[h])
            if not p.onmix and abs(sd.ustar[h] - (-9.0)) > m.eps:
                mech_ht(E, d, h)
        if calc_conv and (not posflux or abs(sd.hflux[cblhr1] - (-999.0)) < m.eps or
                          max(sd.hflux[1:]) < homin):
            calc_conv = False
            E.w(mu, F[6], pid(E), "I78", modnam, "HEAT FLUX CONDITIONS NOT MET FOR DATE:", sd.sfcdate,
                " NO CONVECTIVE PARAMETERS WILL BE CALCULATED")
        if calc_conv:
            if p.up_obs[d]:
                conv_ht(E, d, station_use, cblhr1)
        writefiles(E, d)
        p.tempk = p.theta = p.pres = p.ht = None


# ------------------------------------------------------------------------------------------
def sundat(E, rlat, rlon, tzone, jday, angs=None):
    d2r = E.m.d2r
    dum = -rlon / 15.0 - float(tzone)
    tempz = 15.0 * float(tzone) - (-1.0 * rlon)
    sinlat = math.sin(rlat * d2r)
    coslat = math.cos(rlat * d2r)
    dayno = (float(jday) - 1.0) * 0.0172028
    tdayno = 2.0 * dayno
    sindayno = math.sin(dayno)
    cosdayno = math.cos(dayno)
    sintdayno = math.sin(tdayno)
    costdayno = math.cos(tdayno)
    sigma = (279.9348 + (dayno / d2r) + 1.914827 * sindayno - 0.079525 * cosdayno + 0.019938 * sintdayno
             - 0.00162 * costdayno)
    decsin = 0.39785 * math.sin(sigma * d2r)
    deccos = math.sqrt(1.0 - decsin * decsin)
    amm = 12.0 + 0.12357 * sindayno - 0.004289 * cosdayno + 0.153809 * sintdayno + 0.060783 * costdayno
    hcos = (-sinlat * decsin) / (coslat * deccos)
    if abs(hcos) < 1.0:
        if hcos > -1.0:
            h2 = (math.atan2(math.sqrt(1.0 - hcos * hcos), hcos) / 15.0) / d2r
            sr = amm - h2 + dum
            ss = amm + h2 + dum
        else:
            sr = ss = 24.0
    else:
        sr = ss = 12.0
    if angs is not None:
        for h in range(1, 25):
            hi = (15.0 * (float(h) - amm) + tempz) * d2r
            alfsn = sinlat * decsin + deccos * coslat * math.cos(hi)
            angs[h] = math.atan2(alfsn, math.sqrt(1.0 - alfsn * alfsn)) / d2r
    return sr, ss


def check_obs(E, iswitch, iday1):
    """CHECK_OBS. Devuelve (station_use, lsub1, lsub2)."""
    m, p, u, s, o = E.m, E.pb, E.up, E.sf, E.os
    station_use = 1
    lsub1 = lsub2 = False
    sd = p.sfc_data[iday1]
    if m.lpath[2] and iswitch == 1 and (u.have_soundings[1] or u.have_soundings[2]):
        iupday = 1
        lfound = False
        while iupday <= u.nupdays and not lfound:
            if sd.sfcdate == u.sound_info[iupday][1].snddate:
                lfound = True
                if u.sound_info[iupday][1].sounding:
                    p.pbl_obs[1][iday1] = u.sound_info[iupday][1].nsnding
                if u.lsecondary:
                    if u.sound_info[iupday][2].sounding:
                        p.pbl_obs[5][iday1] = u.sound_info[iupday][2].nsnding
            else:
                iupday += 1
    if m.lpath[2] and iswitch != 1 and (u.have_soundings[1] or (u.have_soundings[2] and m.use_second)):
        if p.sub_upper:
            nstep = abs(p.day_window[1]) + abs(p.day_window[2]) + 1
            nstation1 = u.nstation
        else:
            nstep = 1
            nstation1 = 1
        istep = 1
        station_use = 1
        lstop = False
        day_offset = 0
        while not lstop and not p.up_obs[iday1]:
            if istep == 1:
                day_offset = 0
            else:
                if day_offset == p.day_window[1]:
                    day_offset = 1
                elif day_offset <= 0:
                    day_offset -= 1
                else:
                    day_offset += 1
            iday2 = iday1 + day_offset
            target_date, target_hr, snd_hr, snd_window, lgo = upp_dates(E, iday2, station_use)
            if not lgo[1] and not lgo[2] and not lgo[3]:
                if istep == nstep:
                    if station_use == nstation1:
                        lstop = True
                    else:
                        station_use += 1
                        istep = 1
                else:
                    istep += 1
            else:
                lupper = get_sound(E, iday1, station_use, target_date, target_hr, snd_hr, snd_window, lgo)
                if (istep == 1 and station_use == 1 and p.check_sec_first and not lupper[1] and not lupper[2]
                        and not lupper[3]):
                    station_use = 2
                    lupper = get_sound(E, iday1, station_use, target_date, target_hr, snd_hr, snd_window, lgo)
                    if not lupper[1] and not lupper[2] and not lupper[3]:
                        station_use = 1
                if lupper[1] or lupper[2] or lupper[3]:
                    p.up_obs[iday1] = True
                else:
                    if istep == nstep:
                        if station_use == nstation1:
                            lstop = True
                        else:
                            station_use += 1
                            p.iup[iday1] = 1
                            istep = 1
                    else:
                        istep += 1
        if p.up_obs[iday1]:
            if station_use == 2:
                lsub2 = True
            else:
                if istep != 1:
                    lsub1 = True
    if (m.lpath[3] and s.sfstart <= sd.sfcdate <= s.sfend and iswitch == 1 and s.nsfc[2] > 0):
        lfound = False
        while (s.sfstart <= sd.sfcdate <= s.sfend and p.isf[iday1] <= s.nsfdays and not lfound):
            si = s.sfc_info[p.isf[iday1]]
            if sd.sfcdate == si.sfcdate:
                p.day_obs[iday1] = si.sobs
                for h in range(1, 25):
                    p.nws_obs[h][iday1] = si.have_obs[h]
                    p.asos_hr[h][iday1] = si.asos_hr[h]
                lfound = True
            else:
                p.isf[iday1] += 1
        if lfound:
            for h in range(1, 25):
                if p.nws_obs[h][iday1]:
                    p.pbl_obs[2][iday1] += 1
    if (m.lpath[3] and m.lkey[32] and s.sfstart1min <= sd.sfcdate <= s.sfend1min and iswitch == 1):
        lfound = False
        while (s.sfstart1min <= sd.sfcdate <= s.sfend1min and p.isf1[iday1] <= s.nsf1mindays and not lfound):
            if sd.sfcdate == s.one_mindat[p.isf1[iday1]].sf1mindate:
                for h in range(1, 25):
                    p.one_min_obs[h][iday1] = True
                lfound = True
            else:
                p.isf1[iday1] += 1
        if lfound:
            for h in range(1, 25):
                if p.one_min_obs[h][iday1]:
                    p.pbl_obs[4][iday1] += 1
    if ((m.lpath[4] or m.lpath[5]) and o.osstart <= sd.sfcdate <= o.osend and iswitch == 1 and o.nos[2] > 0):
        lfound = False
        while (o.osstart <= sd.sfcdate <= o.osend and p.ios[iday1] <= o.nosdays and not lfound):
            oi = o.os_info[p.ios[iday1]]
            if sd.sfcdate == oi.osdate:
                if not p.day_obs[iday1]:
                    p.day_obs[iday1] = oi.sobs
                for h in range(1, 25):
                    p.os_obs[h][iday1] = oi.have_obs[h]
                lfound = True
            else:
                p.ios[iday1] += 1
        if lfound:
            for h in range(1, 25):
                if p.os_obs[h][iday1]:
                    p.pbl_obs[3][iday1] += 1
    return station_use, lsub1, lsub2


def upp_dates(E, iday1, istation):
    """UPP_DATES. Devuelve (target_date, target_hr, snd_hr, snd_window, lgo)."""
    m, p, u = E.m, E.pb, E.up
    snd_hr = [None, 0, 0]
    snd_window = [None, 0, 0]
    lgo = [None, False, False, False]
    nd = p.npbldays
    if iday1 <= 0:
        dt = p.sfc_data[1].sfcdate
        iyr, imon, idy = dt // 10000, (dt // 100) % 100, dt % 100
        _, idy, imon, iyr, idate, _ = data_dates(E, 0, idy, imon, iyr, 24 * abs(iday1 - 1), u.upstart, u.upend, 42)
    elif iday1 > nd:
        dt = p.sfc_data[nd].sfcdate
        iyr, imon, idy = dt // 10000, (dt // 100) % 100, dt % 100
        _, idy, imon, iyr, idate, _ = data_dates(E, 1, idy, imon, iyr, -24 * (iday1 - nd), u.upstart, u.upend, 42)
    else:
        idate = p.sfc_data[iday1].sfcdate
    iyr, imon, idy = idate // 10000, (idate // 100) % 100, idate % 100
    target_date = 0
    if p.lactions[6]:
        if 0 < iday1 <= nd:
            target_hr = int(p.up_sunrise[iday1][istation])
        else:
            jd = _jday(iyr, imon, idy)
            rsunrise, rsunset = sundat(E, u.uplat[istation], u.uplon[istation], p.temp_upgmt[istation], jd)
            target_hr = int(rsunrise)
        th, idy2, imon2, iyr2, target_date, lgo[1] = data_dates(E, target_hr, idy, imon, iyr, 0, u.upstart,
                                                                u.upend, 42)
        target_hr = th
        for i in (1, 2):
            snd_hr[i] = target_hr
            iyr2, imon2, idy2 = target_date // 10000, (target_date // 100) % 100, target_date % 100
            snd_hr[i], _, _, _, snd_window[i], lgo[i + 1] = data_dates(E, snd_hr[i], idy2, imon2, iyr2,
                                                                       -p.snding_win[i], u.upstart, u.upend, 42)
    else:
        if p.my_sounding[istation] < 0:
            _, d2, m2, y2, target_date, _ = data_dates(E, 1, idy, imon, iyr, 2, u.upstart, u.upend, 42)
        else:
            _, d2, m2, y2, target_date, _ = data_dates(E, 1, idy, imon, iyr, 0, u.upstart, u.upend, 42)
        iyr2, imon2, idy2 = target_date // 10000, (target_date // 100) % 100, target_date % 100
        target_hr = p.target_hr_gmt[istation]
        target_hr, _, _, _, target_date, lgo[1] = data_dates(E, target_hr, idy2, imon2, iyr2,
                                                             u.upgmt2lst[istation], u.upstart, u.upend, 42)
        for i in (1, 2):
            snd_hr[i] = abs(p.my_sounding[istation] + p.snding_win[i])
            if snd_hr[1] < 0:
                snd_hr[1] = 25 + snd_hr[1]
            if snd_hr[2] > 24:
                snd_hr[2] = 26 - snd_hr[2]
            iyr2, imon2, idy2 = idate // 10000, (idate // 100) % 100, idate % 100
            if i == 1:
                if p.my_sounding[istation] <= 0:
                    _, _, _, _, snd_window[i], _ = data_dates(E, 1, idy2, imon2, iyr2, 2, u.upstart, u.upend, 42)
                else:
                    _, _, _, _, snd_window[i], _ = data_dates(E, 1, idy2, imon2, iyr2, 0, u.upstart, u.upend, 42)
                w = snd_window[i]
                snd_hr[i], _, _, _, snd_window[i], lgo[2] = data_dates(E, snd_hr[i], w % 100, (w // 100) % 100,
                                                                       w // 10000, u.upgmt2lst[istation],
                                                                       u.upstart, u.upend, 42)
            else:
                if p.my_sounding[istation] < 0:
                    _, _, _, _, snd_window[i], _ = data_dates(E, 1, idy2, imon2, iyr2, 2, u.upstart, u.upend, 42)
                else:
                    _, _, _, _, snd_window[i], _ = data_dates(E, 1, idy2, imon2, iyr2, 0, u.upstart, u.upend, 42)
                w = snd_window[i]
                snd_hr[i] = p.snd_hr_gmt[i][istation]
                snd_hr[i], _, _, _, snd_window[i], lgo[3] = data_dates(E, snd_hr[i], w % 100, (w // 100) % 100,
                                                                       w // 10000, u.upgmt2lst[istation],
                                                                       u.upstart, u.upend, 42)
    return target_date, target_hr, snd_hr, snd_window, lgo


def get_sound(E, iday1, istation, target_date, target_hr, snd_hr, snd_window, lgo):
    p, u = E.pb, E.up
    lupper = [None, False, False, False]
    if p.iup[iday1] > abs(p.day_window[1]) + 1:
        p.iup[iday1] = p.iup[iday1] + p.day_window[1] - 1
    si = lambda k: u.sound_info[min(k, u.nupdays)][istation]
    itargetday = 0
    if lgo[1]:
        lfound = False
        while p.iup[iday1] <= u.nupdays and not lfound:
            if target_date == u.sound_info[p.iup[iday1]][istation].snddate:
                lfound = True
            else:
                p.iup[iday1] += 1
        itargetday = p.iup[iday1]
        if lfound:
            S = si(p.iup[iday1])
            if S.sounding:
                lfound1 = False
                while p.isnd[iday1] <= S.nsnding and not lfound1:
                    if target_hr == S.snd_hr[p.isnd[iday1]] and S.nlevels[p.isnd[iday1]] > 0:
                        lfound1 = True
                    else:
                        p.isnd[iday1] += 1
                if lfound1:
                    lupper[1] = True
                else:
                    stophr = snd_hr[1] if snd_window[1] == target_date else 1
                    p.isnd[iday1] = S.nsnding
                    while p.isnd[iday1] >= 1 and not lfound1:
                        k = p.isnd[iday1]
                        if S.snd_hr[k] <= target_hr and S.snd_hr[k] >= stophr and S.nlevels[k] > 0:
                            lfound1 = True
                        else:
                            p.isnd[iday1] -= 1
                    if lfound1:
                        lupper[1] = True
                    else:
                        stophr = snd_hr[2] if snd_window[2] == target_date else 24
                        p.isnd[iday1] = 1
                        while p.isnd[iday1] <= S.nsnding and not lfound1:
                            k = p.isnd[iday1]
                            if S.snd_hr[k] >= target_hr and S.snd_hr[k] <= stophr and S.nlevels[k] > 0:
                                lfound1 = True
                            else:
                                p.isnd[iday1] += 1
                        if lfound1:
                            lupper[1] = True
    if lgo[2] and not lupper[1] and snd_window[1] != target_date:
        lfound = False
        if lgo[1] and p.iup[iday1] > 3:
            p.iup[iday1] -= 2
        else:
            p.iup[iday1] = 1
        while p.iup[iday1] <= u.nupdays and not lfound:
            if snd_window[1] == u.sound_info[p.iup[iday1]][istation].snddate:
                lfound = True
            else:
                p.iup[iday1] += 1
        S = si(p.iup[iday1])
        if S.sounding:
            lfound1 = False
            p.isnd[iday1] = S.nsnding
            while p.isnd[iday1] >= 1 and not lfound1:
                k = p.isnd[iday1]
                if S.snd_hr[k] >= target_hr and S.snd_hr[k] >= snd_hr[1] and S.nlevels[k] > 0:
                    lfound1 = True
                else:
                    p.isnd[iday1] -= 1
            if lfound1:
                lupper[2] = True
            if p.isnd[iday1] <= 0:
                p.isnd[iday1] = S.nsnding
    if lgo[3] and not lupper[1] and not lupper[2] and snd_window[2] != target_date:
        lfound = False
        if lgo[1]:
            p.iup[iday1] = itargetday
        else:
            p.iup[iday1] = 1
        while p.iup[iday1] <= u.nupdays and not lfound:
            if snd_window[2] == u.sound_info[p.iup[iday1]][istation].snddate:
                lfound = True
            else:
                p.iup[iday1] += 1
        S = si(p.iup[iday1])
        if S.sounding:
            lfound1 = False
            p.isnd[iday1] = 1
            while p.isnd[iday1] <= S.nsnding and not lfound1:
                k = p.isnd[iday1]
                if S.snd_hr[k] <= target_hr and S.snd_hr[k] <= snd_hr[2] and S.nlevels[k] > 0:
                    lfound1 = True
                else:
                    p.isnd[iday1] += 1
            if lfound1:
                lupper[3] = True
    return lupper


# ------------------------------------------------------------------------------------------
def winds(E, d, h):
    """WINDS. Devuelve (wind_reset, orig_wind_speed)."""
    m, p, s, o = E.m, E.pb, E.sf, E.os
    modnam = fx("WINDS", 10)
    formstr1 = fmt_msg(E, "a,1x,a20)")
    formstr2 = fmt_msg(E, "a20,1x,a,1x,f6.2,1x,a,1x,f4.2)")
    ov = o.osvars
    sd = p.sfc_data[d]
    eps = m.eps
    zmax, refcoeff, asosadj = 100.0, 7.0, 0.257
    wind_reset = False
    calmhr = lgotwind = onemin = varwind = validos = calmht = False
    albedo = bowen = zo = 0.0
    nws_speed = nws_dir = 0.0
    date_hr_str = fwrite("(a5,1x,i8,1x,a2,1x,i2.2)", "DATE:", sd.sfcdate, "HR", h)[0]
    isite = 0
    if p.os_obs[h][d] and ov[o.wind_vars[1]].lread and ov[o.wind_vars[2]].lread:
        isite = 1
        osd = o.osdata1
        iosd = p.ios[d]
        wv1, wv2 = ov[o.wind_vars[1]], ov[o.wind_vars[2]]
        ilev = 1
        while ilev <= o.nlevel and not lgotwind:
            misswind = [None, False, False]
            if not o.lcalm_obs_hr[ilev, h, iosd]:
                calmhr = False
                for i in (1, 2):
                    wv = ov[o.wind_vars[i]]
                    misswind[i] = abs(float(osd[wv.readvar, ilev, h, iosd]) - wv.missval) <= eps
            else:
                if sd.wind_ht[h] < 0.0:
                    sd.wind_ht[h] = float(osd[1, ilev, h, iosd])
                calmhr = True
                calmht = True
                validos = True
            htv = float(osd[1, ilev, h, iosd])
            missht = abs(htv - ov[o.height_var].missval) <= eps
            lskip = misswind[1] or misswind[2] or missht
            if not o.lcalm_obs_hr[ilev, h, iosd] and not lskip and htv <= zmax and not lgotwind:
                wdv = float(osd[wv1.readvar, ilev, h, iosd])
                if not p.run_coare:
                    albedo, bowen, zo = sfc_chars(E, isite, d, wdv, wv1.missval)
                if htv >= refcoeff * zo:
                    if ov[o.zo_var].lread and not o.overland:
                        zv = float(osd[ov[o.zo_var].readvar, 1, h, iosd])
                        if abs(zv - float(ov[o.zo_var].missval)) > eps and zv != 0.0:
                            sd.zo[h] = zv
                            if sd.zo[h] < 0.0001:
                                sd.zo[h] = 0.0001
                                E.w(m.msg_unit, formstr1, pid(E), "W75", modnam, "ZO < 0.0001; RESET TO 0.001 FOR",
                                    date_hr_str)
                        else:
                            sd.zo[h] = zo
                    else:
                        sd.zo[h] = zo
                    if ov[o.alb_var].lread and not o.overland:
                        av = float(osd[ov[o.alb_var].readvar, 1, h, iosd])
                        sd.albedo[h] = av if abs(av - float(ov[o.alb_var].missval)) > eps else albedo
                    else:
                        sd.albedo[h] = albedo
                    if ov[o.bo_var].lread and not o.overland:
                        bv = float(osd[ov[o.bo_var].readvar, 1, h, iosd])
                        sd.bowen[h] = bv if abs(bv - float(ov[o.bo_var].missval)) > eps else bowen
                    else:
                        sd.bowen[h] = bowen
                    sd.wspd[h] = float(osd[wv2.readvar, ilev, h, iosd])
                    sd.wdir[h] = wdv
                    sd.wind_ht[h] = htv
                    lgotwind = True
                    validos = True
                    p.windsrc[h][d] = 1
                    if sd.wind_ht[h] < 20.0 * sd.zo[h]:
                        E.w(m.msg_unit, formstr2, pid(E), "I73", modnam, date_hr_str, "WIND HEIGHT", sd.wind_ht[h],
                            "< 20X Z0", sd.zo[h])
                else:
                    ilev += 1
            else:
                ilev += 1
        if not lgotwind and calmht:
            sd.wspd[h] = 0.0
            sd.wdir[h] = 0.0
            calmhr = True
        pf = p.pfl_data[h][d]
        for ilev in range(1, o.nlevel + 1):
            pf.ht[ilev] = float(osd[1, ilev, h, iosd])
            if o.lcalm_obs_hr[ilev, h, iosd]:
                pf.speed[ilev] = wv2.missval * wv2.conv
                pf.dir[ilev] = wv1.missval * wv1.conv
            else:
                if wv1.lread:
                    v = float(osd[wv1.readvar, ilev, h, iosd])
                    if abs(v - float(wv1.missval)) > eps:
                        pf.dir[ilev] = v
                if wv2.lread:
                    v = float(osd[wv2.readvar, ilev, h, iosd])
                    if abs(v - float(wv2.missval)) > eps:
                        pf.speed[ilev] = v
            sa = ov[o.sa_var]
            if sa.lread:
                v = float(osd[sa.readvar, ilev, h, iosd])
                if abs(v - float(sa.missval)) > eps and v >= 0.0:
                    pf.sigma_a[ilev] = v
            sw = ov[o.sw_var]
            if sw.lread:
                v = float(osd[sw.readvar, ilev, h, iosd])
                if abs(v - float(sw.missval)) > eps and v >= 0.0:
                    pf.sigma_w[ilev] = v
    if (not p.os_obs[h][d] or (p.os_obs[h][d] and not lgotwind)) and p.nws_obs[h][d] and p.lactions[3]:
        sv = s.sfvars
        if p.one_min_obs[h][d]:
            om = s.one_mindat[p.isf1[d]]
            nws_speed = om.wspd[h]
            nws_dir = om.wdir[h]
            if nws_speed < 900.0 and nws_dir < 900.0 and nws_speed >= 0.0 and nws_dir > 0.0:
                onemin = True
            if nws_speed == 0.0 and nws_dir == 0.0:
                calmhr = True
            if not p.lactions[5] and onemin:
                nws_speed = nws_speed + asosadj
            if p.lpblkeywords[17] and nws_speed < s.asos_thresh:
                nws_dir = 0.0
                nws_speed = 0.0
                calmhr = True
                p.pbl_windstats[2] += 1
            else:
                calmhr = False
        if not onemin:
            nws_dir = float(s.sfdata[10, h, p.isf[d]])
            nws_speed = float(s.sfdata[11, h, p.isf[d]])
            if nws_dir == 0.0 or nws_speed == 0.0:
                calmhr = True
                nws_dir = 0.0
                nws_speed = 0.0
            else:
                if abs(nws_speed - float(sv[11].missval)) > eps and abs(nws_dir - sv[10].missval) > eps:
                    calmhr = False
            if (nws_speed <= 3.1 and abs(nws_speed - float(sv[11].missval)) > eps and not calmhr and
                    abs(nws_dir - sv[10].missval) <= eps and sd.sfcdate >= 19960701):
                varwind = True
            if p.asos_hr[h][d] and abs(nws_speed - float(sv[11].missval)) > eps and not p.lactions[5] and not calmhr:
                nws_speed = nws_speed + asosadj
            if not p.lactions[2] and abs(nws_dir - sv[10].missval) > eps and not calmhr:
                nws_dir = nws_dir + float(T.IRND[sd.jday][h]) - 4.0
                if nws_dir > 360.0:
                    nws_dir = nws_dir - 360.0
                elif nws_dir < 0.0:
                    nws_dir = nws_dir + 360.0
        if m.lpath[4]:
            isite = 1
            if not p.run_coare:
                albedo, bowen, zo = sfc_chars(E, isite, d, nws_dir, sv[10].missval)
            sd.bowen[h] = bowen
            sd.albedo[h] = albedo
            isite = 2
            if not p.run_coare:
                albedo, bowen, zo = sfc_chars(E, isite, d, nws_dir, sv[10].missval)
            sd.zo[h] = zo
        else:
            isite = 1
            if not p.run_coare:
                albedo, bowen, zo = sfc_chars(E, isite, d, nws_dir, sv[10].missval)
            sd.zo[h] = zo
            sd.bowen[h] = bowen
            sd.albedo[h] = albedo
        if varwind or (abs(nws_speed - sv[11].missval) > eps and abs(nws_dir - sv[10].missval) > eps):
            sd.wind_ht[h] = s.nws_hgt
        if nws_speed < SQRT2_MINSIGV and abs(nws_speed - float(sv[11].missval)) > eps and not calmhr:
            E.w(m.msg_unit, formstr1, pid(E), "I74", modnam, "RESET NWS WIND TO 0.282 M/S FOR", date_hr_str)
            nws_speed = SQRT2_MINSIGV
        if abs(nws_speed - float(sv[11].missval)) > eps:
            sd.wspd[h] = nws_speed
            lgotwind = True
            if abs(nws_dir - float(sv[11].missval)) > eps:
                sd.wdir[h] = nws_dir
            elif not varwind:
                lgotwind = False
        else:
            lgotwind = False
            nws_dir = 999.0
        if not p.os_obs[h][d]:
            p.pfl_nlevels[h][d] = 1
            pf = p.pfl_data[h][d]
            pf.speed[1] = nws_speed
            pf.dir[1] = nws_dir
            pf.ht[1] = s.nws_hgt
    if p.windsrc[h][d] == 1:
        sd.windsrcflag[h] = "NAD-OS" if m.lpath[4] else "PROG-OS"
    else:
        if validos and calmhr:
            sd.windsrcflag[h] = "NAD-OS" if m.lpath[4] else "PROG-OS"
        elif lgotwind:
            p.windsrc[h][d] = 2
            if not p.lactions[5]:
                if onemin:
                    sd.windsrcflag[h] = "ADJ-A1"
                else:
                    sd.windsrcflag[h] = "ADJ-SFC" if p.asos_hr[h][d] else "NAD-SFC"
            else:
                sd.windsrcflag[h] = "NAD-A1" if onemin else "NAD-SFC"
    if sd.wspd[h] > 900.0 and sd.wdir[h] > 900.0:
        sd.windsrcflag[h] = "NAD"
    if not lgotwind or calmhr or varwind:
        isite = 1
        if not p.run_coare:
            albedo, bowen, zo = sfc_chars(E, isite, d, 999.0, 999)
        sd.bowen[h] = bowen
        sd.albedo[h] = albedo
        sd.zo[h] = zo
        if m.lpath[4] and ((varwind or calmhr) and p.windsrc[h][d] == 2 and not validos):
            isite = 2
            if not p.run_coare:
                albedo, bowen, zo = sfc_chars(E, isite, d, 999.0, 999)
            sd.zo[h] = zo
    if calmhr:
        p.pbl_windstats[1] += 1
    if varwind:
        p.pbl_windstats[3] += 1
    orig_wind_speed = sd.wspd[h]
    if sd.wspd[h] < SQRT2_MINSIGV and not calmhr:
        E.w(m.msg_unit, formstr1, pid(E), "I74", modnam, "RESET WIND TO 0.282 M/S FOR", date_hr_str)
        sd.wspd[h] = SQRT2_MINSIGV
        wind_reset = True
    return wind_reset, orig_wind_speed


def temps(E, d, h):
    m, p, s, o = E.m, E.pb, E.sf, E.os
    ov = o.osvars
    sd = p.sfc_data[d]
    eps = m.eps
    lgottemp = False
    if p.os_obs[h][d] and ov[o.temp_var].lread:
        osd = o.osdata1
        iosd = p.ios[d]
        tv = ov[o.temp_var]
        ilev = 1
        while ilev <= o.nlevel and not lgottemp:
            tval = float(osd[tv.readvar, ilev, h, iosd])
            htv = float(osd[1, ilev, h, iosd])
            misstemp = abs(tval - float(tv.missval)) <= eps
            missht = abs(htv - float(ov[o.height_var].missval)) <= eps
            lskip = misstemp or missht
            if not lskip and htv <= 100.0 and not lgottemp:
                if htv >= sd.zo[h]:
                    sd.airtemp[h] = tval + 273.15
                    sd.temp_ht[h] = htv
                    lgottemp = True
                    p.tempsrc[h][d] = 1
                else:
                    ilev += 1
            else:
                ilev += 1
    if (not p.os_obs[h][d] or (p.os_obs[h][d] and not lgottemp)) and p.nws_obs[h][d] and p.lactions[3]:
        tv = float(s.sfdata[7, h, p.isf[d]])
        if abs(tv - float(s.sfvars[7].missval)) > eps:
            sd.airtemp[h] = tv + 273.15
            sd.temp_ht[h] = 2.0
            p.tempsrc[h][d] = 2
    if p.nws_obs[h][d]:
        tv = float(s.sfdata[7, h, p.isf[d]])
        if not p.os_obs[h][d] and abs(tv - float(s.sfvars[7].missval)) > eps:
            p.pfl_data[h][d].airtemp[1] = tv


def clouds(E, d, h):
    m, p, s, o = E.m, E.pb, E.sf, E.os
    ov = o.osvars
    sd = p.sfc_data[d]
    lgotcloud = False
    if p.os_obs[h][d] and p.oncloud:
        cv = float(o.osdata1[ov[o.cloud_var].readvar, 1, h, p.ios[d]])
        if abs(cv - float(ov[o.cloud_var].missval)) > m.eps:
            sd.ccvr[h] = nint(cv)
            p.cloudsrc[h][d] = 1
            lgotcloud = True
    if m.lpath[3]:
        sv = s.sfvars
        if ((not p.os_obs[h][d] or (p.os_obs[h][d] and not lgotcloud)) and
                (p.nws_obs[h][d] and (float(s.sfdata[4, h, p.isf[d]]) != float(sv[4].missval) or
                                      float(s.sfdata[6, h, p.isf[d]]) != float(sv[6].missval)))):
            v4 = int(float(s.sfdata[4, h, p.isf[d]]))
            icloud = [None, 0, 0, 0]
            icloud[2] = int(v4 / 100) if v4 >= 0 else -int(-v4 / 100)
            icloud[1] = v4 - icloud[2] * 100
            icloud[3] = int(float(s.sfdata[6, h, p.isf[d]]))
            misscloud = [None, 0, 0, 0]
            misscloud[2] = sv[4].missval // 100
            misscloud[1] = sv[4].missval - misscloud[2] * 100
            misscloud[3] = sv[6].missval
            i = 1
            lfound = False
            while i <= 3 and not lfound:
                if icloud[i] != misscloud[i]:
                    lfound = True
                else:
                    i += 1
            if lfound:
                sd.ccvr[h] = icloud[i]
                p.cloudsrc[h][d] = 2


def substitute(E, d, h, ostemp):
    m, p = E.m, E.pb
    nd = p.npbldays
    d1 = [None, 0, 0, 0]
    d2 = [None, 0, 0, 0]
    h1 = [None, 0, 0, 0]
    h2 = [None, 0, 0, 0]
    if h == 1:
        if d > 1:
            d1 = [None, d - 1, d - 1, d - 1]
            h1 = [None, 24, 24, 23]
            d2 = [None, d, d, d]
            h2 = [None, h + 1, h + 2, h + 1]
    elif h == 2:
        if d > 1:
            d1 = [None, d, d, d - 1]
            h1 = [None, h - 1, h - 1, 24]
            d2 = [None, d, d, d]
            h2 = [None, h + 1, h + 2, h + 1]
        else:
            d1 = [None, d, d, d]
            h1 = [None, h - 1, h - 1, h - 1]
            d2 = [None, d, d, d]
            h2 = [None, h + 1, h + 2, h + 2]
    elif h == 23:
        if d < nd:
            d1 = [None, d, d, d]
            h1 = [None, h - 1, h - 1, h - 2]
            d2 = [None, d, d + 1, d]
            h2 = [None, h + 1, 1, h + 1]
        else:
            d1 = [None, d, d, d]
            h1 = [None, h - 1, h - 1, h - 2]
            d2 = [None, d, d, d]
            h2 = [None, 24, 24, 24]
    elif h == 24:
        d1 = [None, d, d, d]
        h1 = [None, h - 1, h - 1, h - 2]
        d2 = [None, d + 1, d + 1, d + 1]
        h2 = [None, 1, 2, 1]
    else:
        d1 = [None, d, d, d]
        h1 = [None, h - 1, h - 1, h - 2]
        d2 = [None, d, d, d]
        h2 = [None, h + 1, h + 2, h + 1]
    sdd = p.sfc_data
    sd = sdd[d]
    eps = m.eps
    if p.tempsrc[h][d] == 0 and p.subtemp:
        lsub = False
        i = 1
        while i <= 3 and not lsub:
            a1, a2 = (h1[i], d1[i]), (h2[i], d2[i])
            if (p.tempsrc[a1[0]][a1[1]] > 0 and p.tempsrc[a1[0]][a1[1]] < 3 and p.tempsrc[a2[0]][a2[1]] > 0 and
                    abs(sdd[d1[i]].temp_ht[h1[i]] - sdd[d2[i]].temp_ht[h2[i]]) <= eps):
                delta_h1 = h - h1[i]
                delta_h2 = h2[i] - h1[i]
                if delta_h1 < 0:
                    delta_h1 += 24
                if delta_h2 < 0:
                    delta_h2 += 24
                delta = sdd[d2[i]].airtemp[h2[i]] - sdd[d1[i]].airtemp[h1[i]]
                sd.airtemp[h] = sdd[d1[i]].airtemp[h1[i]] + delta * (float(delta_h1) / float(delta_h2))
                sd.temp_ht[h] = sdd[d2[i]].temp_ht[h2[i]]
                if p.tempsrc[a1[0]][a1[1]] == 1 and p.tempsrc[a2[0]][a2[1]] == 1:
                    ostemp = True
                p.tempsrc[h][d] = 3
                lsub = True
                p.n_temp_sub += 1
            i += 1
    if p.cloudsrc[h][d] == 0 and p.subcloud:
        lsub = False
        i = 1
        while i <= 3 and not lsub:
            if (p.cloudsrc[h1[i]][d1[i]] > 0 and p.cloudsrc[h1[i]][d1[i]] < 3 and p.cloudsrc[h2[i]][d2[i]] > 0):
                delta_h1 = h - h1[i]
                delta_h2 = h2[i] - h1[i]
                if delta_h1 < 0:
                    delta_h1 += 24
                if delta_h2 < 0:
                    delta_h2 += 24
                cld_delta = sdd[d2[i]].ccvr[h2[i]] - sdd[d1[i]].ccvr[h1[i]]
                sd.ccvr[h] = nint(float(sdd[d1[i]].ccvr[h1[i]]) + float(cld_delta) *
                                  (float(delta_h1) / float(delta_h2)))
                p.cloudsrc[h][d] = 3
                lsub = True
                p.n_cloud_sub += 1
            i += 1
    if p.tempsrc[h][d] == 3:
        sd.subflag[h] = "Sub_CC-TT" if p.cloudsrc[h][d] == 3 else "Sub_TT"
    else:
        if p.cloudsrc[h][d] == 3:
            sd.subflag[h] = "Sub_CC"
    return ostemp


def press(E, d, h, ostemp):
    from .comun import pressure
    m, p, s, o = E.m, E.pb, E.sf, E.os
    ov = o.osvars
    sd = p.sfc_data[d]
    eps = m.eps
    tv = 290.0
    slpvar = ov[o.slp_var].readvar
    presvar = ov[o.pres_var].readvar
    ospres = [None, False, False]
    sfpres = [None, False, False]
    p.havepress = False
    popt = 0
    osd = o.osdata1
    iosd = p.ios[d] if (m.lpath[4] or m.lpath[5]) else 1
    if ov[o.pres_var].lread and p.os_obs[h][d]:
        if abs(float(osd[presvar, 1, h, iosd]) - float(ov[o.pres_var].missval)) > eps:
            ospres[1] = True
    if ov[o.slp_var].lread and p.os_obs[h][d]:
        if abs(float(osd[slpvar, 1, h, iosd]) - float(ov[o.slp_var].missval)) > eps and slpvar > 0:
            ospres[2] = True
    if p.nws_obs[h][d]:
        if abs(float(s.sfdata[3, h, p.isf[d]]) - float(s.sfvars[3].missval)) > eps:
            sfpres[1] = True
        if abs(float(s.sfdata[2, h, p.isf[d]]) - float(s.sfvars[2].missval)) > eps:
            sfpres[2] = True
    if s.lsfelev:
        nwselev = s.sfelev
    elif s.user_elev:
        nwselev = s.sf_user_elev
    else:
        nwselev = -99999.0
    ue = s.user_elev or s.lsfelev
    tsrc = p.tempsrc[h][d]
    if tsrc == 1 or (tsrc == 3 and ostemp):
        if ospres[1]:
            popt = 1
        elif ospres[2]:
            popt = 2
        elif sfpres[1] and o.loselev and ue:
            popt = 3
        elif sfpres[2] and o.loselev:
            popt = 4
        elif sfpres[1]:
            popt = 5
        elif sfpres[2] and ue:
            popt = 6
        elif o.loselev:
            popt = 7
        elif ue:
            popt = 8
        elif ospres[2] and not o.loselev:
            popt = 9
        elif sfpres[2] and not s.user_elev and not s.lsfelev:
            popt = 10
        else:
            popt = 11
    elif tsrc == 2 or (tsrc == 3 and not ostemp):
        if sfpres[1]:
            popt = 5
        elif sfpres[2] and ue:
            popt = 6
        elif ospres[1] and ue and o.loselev:
            popt = 12
        elif ospres[2] and ue:
            popt = 13
        elif ospres[1]:
            popt = 1
        elif ospres[2] and o.loselev:
            popt = 2
        elif ue and nwselev != 0.0:
            popt = 8
        elif o.loselev:
            popt = 7
        elif sfpres[2] and not s.lsfelev and not s.user_elev:
            popt = 14
        elif ospres[2] and not o.loselev:
            popt = 15
        else:
            popt = 11
    else:
        if ospres[1]:
            popt = 1
        elif sfpres[1]:
            popt = 5
        elif o.loselev:
            popt = 7
        elif ue:
            popt = 8
        else:
            popt = 11
    if popt > 0:
        p.havepress = True
    if popt == 1:
        sd.pres[h] = float(osd[presvar, 1, h, iosd])
    elif popt == 2:
        sd.pres[h] = pressure(E, 2, o.oselev, tv, float(osd[slpvar, 1, h, iosd]))
    elif popt == 3:
        sd.pres[h] = pressure(E, 2, o.oselev - nwselev, tv, float(s.sfdata[3, h, p.isf[d]]))
    elif popt == 4:
        sd.pres[h] = pressure(E, 2, o.oselev, tv, float(s.sfdata[2, h, p.isf[d]]))
    elif popt == 5:
        sd.pres[h] = float(s.sfdata[3, h, p.isf[d]])
    elif popt == 6:
        sd.pres[h] = pressure(E, 2, nwselev, tv, float(s.sfdata[2, h, p.isf[d]]))
    elif popt == 7:
        sd.pres[h] = 1013.25 * (1.0 - ((0.0065 / 288.15) * o.oselev)) ** 5.255
    elif popt == 8:
        sd.pres[h] = 1013.25 * (1.0 - ((0.0065 / 288.15) * nwselev)) ** 5.255
    elif popt == 9:
        sd.pres[h] = float(osd[slpvar, 1, h, iosd])
    elif popt == 10:
        sd.pres[h] = float(s.sfdata[2, h, p.isf[d]])
    elif popt == 11:
        sd.pres[h] = 1013.25
    elif popt == 12:
        sd.pres[h] = pressure(E, 2, nwselev - o.oselev, tv, float(osd[presvar, 1, h, iosd]))
    elif popt == 13:
        sd.pres[h] = pressure(E, 2, nwselev, tv, float(osd[slpvar, 1, h, iosd]))
    elif popt == 14:
        sd.pres[h] = float(s.sfdata[2, h, p.isf[d]])
    elif popt == 15:
        sd.pres[h] = float(osd[slpvar, 1, h, iosd])


def rh(E, d, h):
    """RH. Devuelve (rh_ht, have_rh)."""
    from .comun import humidity
    m, p, s, o = E.m, E.pb, E.sf, E.os
    ov = o.osvars
    sd = p.sfc_data[d]
    eps = m.eps
    rh_ht = 999.0
    lfound = lfound1 = False
    have_rh = False
    if p.os_obs[h][d]:
        osd = o.osdata1
        iosd = p.ios[d]
        if ov[o.rh_var].lread:
            ilev = 1
            while ilev <= o.nlevel and not lfound:
                v = float(osd[ov[o.rh_var].readvar, ilev, h, iosd])
                if abs(v - float(ov[o.rh_var].missval)) > eps:
                    lfound = True
                    sd.rh[h] = v
                    rh_ht = float(osd[1, ilev, h, iosd])
                ilev += 1
            if lfound:
                have_rh = True
        if not lfound or not ov[o.rh_var].lread:
            if ov[o.dewpt_var].lread and p.tempsrc[h][d] == 1:
                ilev = 1
                dewpt = 0.0
                while ilev <= o.nlevel and not lfound1:
                    diffht = abs(sd.temp_ht[h] - float(osd[1, ilev, h, iosd]))
                    dv = float(osd[ov[o.dewpt_var].readvar, ilev, h, iosd])
                    diffd = abs(dv - float(ov[o.dewpt_var].missval))
                    if diffht < eps and diffd > eps:
                        dewpt = dv
                        rh_ht = float(osd[1, ilev, h, iosd])
                        lfound1 = True
                    ilev += 1
                if lfound1:
                    irh = int(humidity(sd.airtemp[h] - 273.15, dewpt))
                    sd.rh[h] = float(irh)
                    have_rh = True
    if not lfound and not lfound1 and m.lpath[3]:
        sv = s.sfvars
        isf = p.isf[d]
        if p.nws_obs[h][d] and abs(float(s.sfdata[9, h, isf]) - float(sv[9].missval)) > eps:
            sd.rh[h] = float(s.sfdata[9, h, isf])
            have_rh = True
        else:
            diffd = abs(float(s.sfdata[8, h, isf]) - float(sv[8].missval))
            difft = abs(float(s.sfdata[7, h, isf]) - float(sv[7].missval))
            if diffd > eps and difft > eps:
                irh = int(humidity(float(s.sfdata[7, h, isf]), float(s.sfdata[8, h, isf])))
                sd.rh[h] = float(irh)
                rh_ht = 2.0
                have_rh = True
    return rh_ht, have_rh


def precip(E, d, h):
    m, p, s, o = E.m, E.pb, E.sf, E.os
    ov = o.osvars
    sd = p.sfc_data[d]
    i = 1
    lfound = False
    while i <= 2 and not lfound:
        pv = ov[o.prcp_vars[i]]
        if pv.lread and p.os_obs[h][d]:
            v = float(o.osdata1[pv.readvar, 1, h, p.ios[d]])
            if abs(v - float(pv.missval)) > m.eps:
                lfound = True
                sd.pamt[h] = v * 10.0 if i == 1 else v
        i += 1
    if not lfound and p.nws_obs[h][d]:
        sd.pamt[h] = float(s.sfdata[1, h, p.isf[d]])
        sd.ipcode[h] = int(float(s.sfdata[5, h, p.isf[d]]))
        if sd.ipcode[h] == 1 or sd.ipcode[h] == 3:
            sd.ipcode[h] = 11
        elif sd.ipcode[h] == 2:
            sd.ipcode[h] = 22
        elif sd.ipcode[h] == 9:
            sd.ipcode[h] = 99
    if sd.pamt[h] > 0.0:
        if p.tempsrc[h][d] > 0:
            sd.ipcode[h] = 22 if sd.airtemp[h] < 273.15 else 11
        else:
            if sd.ipcode[h] > 100:
                sd.ipcode[h] = 99
    else:
        if sd.ipcode[h] > 100:
            sd.ipcode[h] = 99
    if abs(sd.pamt[h] - 0.0) < m.eps:
        sd.ipcode[h] = 0


# ------------------------------------------------------------------------------------------
def stability(E, d, h):
    m, p, o = E.m, E.pb, E.os
    modnam = fx("STABILITY", 10)
    formstr = fmt_msg(E, "a20,1x,a)")
    ov = o.osvars
    sd = p.sfc_data[d]
    a1, a2 = 990.0, 30.0
    date_hr_str = fwrite("(a5,1x,i8,1x,a2,1x,i2.2)", "DATE:", sd.sfcdate, "HR", h)[0]
    if not p.onmol and not o.overland:
        E.w(m.msg_unit, formstr, pid(E), "I84", modnam, date_hr_str, "STABILITY BASED ON CRITICAL SOLAR ANGLE")
    if h == 1:
        d1 = d if d == 1 else d - 1
        h1 = 24
    else:
        d1 = d
        h1 = h - 1
    p.angle = (p.sun_ang[h1][d1] + p.sun_ang[h][d]) / 2.0
    angle = p.angle
    nt = 0
    if p.oninso:
        inso_os = float(o.osdata1[ov[o.inso_var].readvar, 1, h, p.ios[d]])
        if inso_os > 0.0 and angle > 0.0:
            p.cloudsrc[h][d] = 4
            qrnot = a1 * math.sin(angle * m.d2r) - a2
            if qrnot <= 0.0:
                skyfrac = 0.0
            elif inso_os > 0.0 and inso_os >= qrnot:
                skyfrac = 0.0
            elif inso_os > 0.0:
                skyfrac = ((1.0 - inso_os / qrnot) / 0.75) ** (1.0 / 3.4)
            else:
                skyfrac = 1.0
            if skyfrac <= 0.0:
                sd.ccvr[h] = 0
            elif skyfrac >= 1.0:
                sd.ccvr[h] = 10
            else:
                sd.ccvr[h] = nint(skyfrac * 10.0)
            if p.tempsrc[h][d] > 0 and sd.airtemp[h] < 900.0:
                p.crit_angle = nr_ang(E, d, h, sd.ccvr[h], sd.airtemp[h])
                if angle < p.crit_angle:
                    p.got_eq_ccvr[h][d] = True
            else:
                p.crit_angle = 94.0
        elif p.tempsrc[h][d] > 0 and sd.airtemp[h] < 900.0 and p.cloudsrc[h][d] > 0 and sd.ccvr[h] < 99:
            p.crit_angle = nr_ang(E, d, h, sd.ccvr[h], sd.airtemp[h])
        elif p.cloudsrc[h][d] > 0 and sd.ccvr[h] < 99:
            tt = 0.0
            for h2 in range(1, 25):
                if p.tempsrc[h2][d] > 0 and sd.airtemp[h2] < 900.0:
                    tt = tt + sd.airtemp[h2]
                    nt += 1
            tt = tt / float(nt) if nt >= 18 else 288.0
            p.crit_angle = nr_ang(E, d, h, sd.ccvr[h], tt)
        elif p.tempsrc[h][d] > 0 and sd.airtemp[h] < 900.0:
            p.crit_angle = nr_ang(E, d, h, 5, sd.airtemp[h])
        else:
            p.crit_angle = nr_ang(E, d, h, 5, 288.0)
    elif p.tempsrc[h][d] > 0 and sd.airtemp[h] < 900.0 and p.cloudsrc[h][d] > 0 and sd.ccvr[h] < 99:
        p.crit_angle = nr_ang(E, d, h, sd.ccvr[h], sd.airtemp[h])
    elif p.cloudsrc[h][d] > 0 and sd.ccvr[h] < 99:
        tt = 0.0
        for h2 in range(1, 25):
            if p.tempsrc[h2][d] > 0 and sd.airtemp[h2] < 900.0:
                tt = tt + sd.airtemp[h2]
                nt += 1
        tt = tt / float(nt) if nt >= 18 else 288.0
        p.crit_angle = nr_ang(E, d, h, sd.ccvr[h], tt)
    elif p.tempsrc[h][d] > 0 and sd.airtemp[h] < 900.0:
        p.crit_angle = nr_ang(E, d, h, 5, sd.airtemp[h])
    else:
        p.crit_angle = nr_ang(E, d, h, 5, 288.0)
    b1 = 1 - sd.albedo[h]
    if angle <= 0.0:
        sd.albedo[h] = 1.0
    else:
        sd.albedo[h] = sd.albedo[h] + b1 * math.exp(-0.1 * angle + (-0.5 * b1 * b1))
    if p.onmol:
        if float(o.osdata1[ov[o.l_var].readvar, 1, h, p.ios[d]]) < 0.0:
            p.cbl[h][d] = True
    else:
        if angle >= p.crit_angle:
            p.cbl[h][d] = True


def calc_ustar(E, d, h, wind_reset, wspeed):
    """CALC_USTAR. Devuelve (ustar, mol, thetastar1)."""
    m, p, o = E.m, E.pb, E.os
    sd = p.sfc_data[d]
    ustar = mol = thetastar1 = 0.0
    vonk, g, cp, pi, eps = m.vonk, m.g, m.cp, m.pi, m.eps
    zr, z0 = sd.wind_ht[h], sd.zo[h]
    if p.cbl[h][d]:
        lcalc = not (p.onmol and (not wind_reset or not p.onustar))
        if lcalc:
            psizl = psizol = lastl = 0.0
            if wspeed == 0.0:
                ustar = 0.0
            else:
                rho = p.rho[h][d]
                ustar = vonk * wspeed / (math.log(zr / z0) - psizl + psizol)
                mol = -rho * cp * sd.airtemp[h] * (ustar * ustar * ustar) / (vonk * g * sd.hflux[h])
                while abs(mol - lastl) > abs(eps * mol):
                    lastl = mol
                    mu = (1.0 - 16.0 * (zr / mol)) ** 0.25
                    mu0 = (1.0 - 16.0 * (z0 / mol)) ** 0.25
                    psizl = 2.0 * math.log((1.0 + mu) / 2.0) + math.log((1.0 + mu * mu) / 2.0) - 2.0 * math.atan(mu) + pi / 2.0
                    psizol = (2.0 * math.log((1.0 + mu0) / 2.0) + math.log((1.0 + mu0 * mu0) / 2.0) -
                              2.0 * math.atan(mu0) + pi / 2.0)
                    ustar = vonk * wspeed / (math.log(zr / z0) - psizl + psizol)
                    mol = -rho * cp * sd.airtemp[h] * (ustar * ustar * ustar) / (vonk * g * sd.hflux[h])
        else:
            l_os = float(o.osdata1[o.osvars[o.l_var].readvar, 1, h, p.ios[d]])
            ustar = ((-l_os * vonk * g * sd.hflux[h]) / (p.rho[h][d] * cp * sd.airtemp[h])) ** (1.0 / 3.0)
            mol = l_os
    else:
        angle, crit = p.angle, p.crit_angle
        if p.adjustar:
            betam = 4.7
            cdn = vonk / math.log((zr - 5.0 * z0) / z0)
            thetastar1 = 0.08
            if 0.0 < angle < crit:
                thetastar1 = thetastar1 * (1.0 - _sq(angle / crit))
            unot = math.sqrt((betam * (zr - 5.0 * z0 - z0) * g * thetastar1) / sd.airtemp[h])
            # con viento nulo (u* con el viento original de una hora en calma) el original
            # divide por cero en IEEE: se replica con _dv
            chek = _sq(_dv(2.0 * unot, math.sqrt(cdn) * wspeed))
            ustar = (cdn * wspeed / 2.0) * _dv(1.0 + math.exp(-1.0 * chek / 2.0),
                                               1.0 - math.exp(_dv(-2.0, math.sqrt(chek))))
            ucrit = (2.0 * unot) / math.sqrt(cdn)
            ustarcrit = cdn * ucrit / 4.0
            ustar = _dmax1(ustarcrit, ustar)
            if chek > 1.0:
                thetastar1 = _dv(thetastar1 * wspeed, ucrit)
        else:
            betam = 5.0
            cdn = vonk / math.log(zr / z0)
            thetastar1 = 0.09 * (1.0 - 0.5 * _sq(float(sd.ccvr[h]) / 10.0))
            if 0.0 < angle < crit:
                thetastar1 = thetastar1 * (1.0 - _sq(angle / crit))
            unot = math.sqrt((betam * zr * g * thetastar1) / sd.airtemp[h])
            chek = _sq(_dv(2.0 * unot, math.sqrt(cdn) * wspeed))
            if chek <= 1.0:
                ustar = (cdn * wspeed / 2.0) * (1.0 + math.sqrt(1.0 - chek))
            else:
                ucrit = (2.0 * unot) / math.sqrt(cdn)
                ustarcrit = cdn * ucrit / 2.0
                ustar = _dv(ustarcrit * wspeed, ucrit)
                thetastar1 = _dv(thetastar1 * wspeed, ucrit)
    return ustar, mol, thetastar1


def nr_ang(E, d, h, ccvrin, tempin):
    m, p = E.m, E.pb
    sd = p.sfc_data[d]
    sb, c1, c2, b1, b2, a1, a2 = 5.67e-08, 5.31e-13, 60.0, 0.75, 3.4, 990.0, 30.0
    eps = m.eps
    angle = p.angle
    ba1 = 1.0 - sd.albedo[h]
    if angle <= 0.0:
        albedo = 1.0
    else:
        albedo = sd.albedo[h] + ba1 * math.exp(-R4_01 * angle + (-0.5 * ba1 * ba1))
    sky = float(ccvrin)
    acrit1 = 0.0
    if 0.0 <= albedo < 1.0:
        acrit1 = angle
        lastacrit = 0.0
        i = 0
        while abs(acrit1 - lastacrit) > abs(eps * acrit1) and i <= 20:
            i += 1
            lastacrit = acrit1
            term1 = sb * tempin ** 4.0 - c1 * tempin ** 6.0 - c2 * sky / 10.0
            term2 = (1.0 - b1 * (sky / 10.0) ** b2) * (1.0 - albedo) * a1
            sinacrit = term1 / term2 + a2 / a1
            if sinacrit <= 0.0:
                acrit1 = 0.0
                break
            elif sinacrit > 1.0:
                acrit1 = 92.0
                break
            else:
                acrit1 = math.asin(sinacrit) / m.d2r
            if acrit1 <= 0.0:
                acrit1 = 0.0
                break
            else:
                albedo = sd.albedo[h] + ba1 * math.exp(-R4_01 * acrit1 + (-0.5 * ba1 * ba1))
    elif albedo >= 1.0:
        acrit1 = 94.0
    return acrit1


def netrad(E, d, h):
    """NETRAD. Devuelve lcycle."""
    m, p, o = E.m, E.pb, E.os
    modnam = fx("NETRAD", 10)
    formstr1 = fmt_msg(E, "a20,1x,a)")
    formstr2 = fmt_msg(E, "a20,1x,a,1x,g13.6,1x,a)")
    sd = p.sfc_data[d]
    sb, c1, c2, c3 = 5.67e-08, 5.31e-13, 60.0, 1.12
    date_hr_str = fwrite("(a5,1x,i8,1x,a2,1x,i2.2)", "DATE:", sd.sfcdate, "HR", h)[0]
    lcycle = False
    sky = float(sd.ccvr[h])
    if not p.onnrad:
        if p.cbl[h][d]:
            if p.oninso and p.inso > 0.0 and p.cloudsrc[h][d] > 0:
                p.nrad = ((1.0 - sd.albedo[h]) * p.inso + c1 * _p6(sd.airtemp[h]) - sb * _p4(sd.airtemp[h]) +
                          c2 * (sky / 10.0)) / c3
            elif p.cloudsrc[h][d] > 0:
                if p.angle <= 1.74:
                    p.inso = 0.0
                else:
                    p.inso = 990.0 * math.sin(p.angle * m.d2r) - 30.0
                    p.inso = p.inso * (1.0 - 0.75 * ((sky / 10.0) ** 3.4))
                p.nrad = ((1.0 - sd.albedo[h]) * p.inso + c1 * _p6(sd.airtemp[h]) - sb * _p4(sd.airtemp[h]) +
                          c2 * (sky / 10.0)) / c3
            else:
                E.w(m.msg_unit, formstr1, pid(E), "I71", modnam, date_hr_str, "MISSING INSOLATION AND CLOUD COVER")
                lcycle = True
        else:
            if abs(sd.hflux[h] - 999.0) > m.eps:
                p.nrad = sd.hflux[h] * (1.0 + 1.0 / sd.bowen[h]) / 0.9
    if not p.cbl[h][d]:
        if abs(p.nrad - float(o.osvars[o.nrad_var].missval)) > m.eps and p.nrad > 0.0:
            E.w(m.msg_unit, formstr2, pid(E), "I76", modnam, date_hr_str, "NET RADIATION", p.nrad, "> 0 FOR STABLE HOUR")
    return lcycle


def sfc_chars(E, isite, d, wd, missdir):
    """SFC_CHARS. Devuelve (albedo, bowen, zo)."""
    m, p = E.m, E.pb
    sd = p.sfc_data[d]
    iyr = sd.sfcdate // 10000
    imon = (sd.sfcdate // 100) % 100
    iyr1 = iyr - p.pbldates[1][1] + 1
    nfreq = p.nfreq1[iyr1] if isite == 1 else p.nfreq2[iyr1]
    month2seas = [None, [None, 1, 1, 2, 2, 2, 3, 3, 3, 4, 4, 4, 1], [None, 3, 3, 4, 4, 4, 1, 1, 1, 2, 2, 2, 3]]
    if nfreq == 1:
        ifreq = 1
    elif nfreq == 12:
        ifreq = imon
    else:
        ifreq = month2seas[p.ihem[isite]][imon]
    if isite == 1:
        nsec, sects, sfc = p.nsectors1[iyr1], p.sectors1, p.sfc_char1
    else:
        nsec, sects, sfc = p.nsectors2[iyr1], p.sectors2, p.sfc_char2
    albedo = bowen = zo = 0.0
    if abs(wd - float(missdir)) <= m.eps:
        for isec in range(1, nsec + 1):
            a, b, z = sfc[isec][ifreq][iyr1]
            albedo = albedo + a
            bowen = bowen + b
            zo = zo + z
        albedo = albedo / float(nsec)
        bowen = bowen / float(nsec)
        zo = zo / float(nsec)
    else:
        isec = 1
        lfound = False
        while isec <= nsec and not lfound:
            s1, s2 = sects[1][isec][iyr1], sects[2][isec][iyr1]
            if s1 < s2:
                if wd >= s1 and ((wd < s2 and s2 != 360.0) or (wd <= s2 and abs(s2 - 360.0) <= m.eps)):
                    lfound = True
                else:
                    isec += 1
            else:
                if (wd >= s1 and wd > s2) or (wd <= s1 and wd < s2):
                    lfound = True
                else:
                    isec += 1
        k = min(isec, len(sfc) - 1)
        albedo, bowen, zo = sfc[k][ifreq][iyr1]
    return albedo, bowen, zo


def have_data(E, d, h, invar1):
    m, p, o = E.m, E.pb, E.os
    v = o.osvars[invar1]
    if p.os_obs[h][d] and v.lread:
        val = float(o.osdata1[v.readvar, 1, h, p.ios[d]])
        return abs(val - float(v.missval)) > m.eps
    return False


def bulk_rich(E, d, h):
    m, p, o = E.m, E.pb, E.os
    sd = p.sfc_data[d]
    vonk, g, eps = m.vonk, m.g, m.eps
    betam, alpha1, beta1, gamma1 = 5.0, 4.0, 0.5, 0.3
    zr, z0, ws, T = sd.wind_ht[h], sd.zo[h], sd.wspd[h], sd.airtemp[h]
    z1, z2 = o.osdt_hts[1][1], o.osdt_hts[1][2]
    angle, crit = p.angle, p.crit_angle
    lst = [0.0] * 21
    ust = [0.0] * 21
    thst = [0.0] * 21
    z_over_l = [0.0] * 21
    dt_os = float(o.osdata1[o.osvars[o.dt01_var].readvar, 1, h, p.ios[d]])
    dtheta = dt_os + (z2 - z1) * 0.0098
    if dtheta <= 0.0:
        sd.ustar[h] = vonk * ws / (math.log(zr / z0))
        sd.mol[h] = 8888.0
        sd.theta_star[h] = 0.00001
        return
    a = betam * z2 * g / T
    if p.adjustar:
        cdn = vonk / math.log((zr - betam * z0) / z0)
    else:
        cdn = vonk / math.log(zr / z0)
    mol = zr / 2.0
    thetastar1 = vonk * dtheta / (math.log(z2 / z1) + betam * (z2 - z1) / mol)
    if 0.0 < angle < crit:
        thetastar1 = thetastar1 * (1.0 - _sq(angle / crit))
    ustar1 = math.sqrt(cdn * a * thetastar1)
    mol = ustar1 * ustar1 * T / (vonk * g * thetastar1)
    templ, tempu, tempth = mol, ustar1, thetastar1
    lastu = lastmol = lastth = 0.0
    iter_ = 0
    imin = 3
    z_on_l = z0_on_l = term = term0 = 0.0

    def corr_th(th):
        if 0.0 < angle < crit:
            return th * (1.0 - _sq(angle / crit))
        return th

    while ((abs(lastmol - mol) > abs(eps * mol) or abs(lastu - ustar1) > abs(eps * ustar1) or
            abs(lastth - thetastar1) > abs(eps * thetastar1) or imin >= 1) and mol >= 1.0 and iter_ < 20):
        imin = max(0, imin - 1)
        iter_ += 1
        lastmol, lastu, lastth = mol, ustar1, thetastar1
        if p.adjustar:
            z_on_l = zr / mol
            if zr > 0.7 * mol:
                z0_on_l = z0 / mol
                term = alpha1 * z_on_l ** beta1 * (1.0 + gamma1 * z_on_l ** (1.0 - beta1))
                term0 = alpha1 * z0_on_l ** beta1 * (1.0 + gamma1 * z0_on_l ** (1.0 - beta1))
                ustar1 = vonk * ws / (term - term0)
            else:
                ustar1 = vonk * ws / (math.log((zr - betam * z0) / z0) + betam * z_on_l)
            thetastar1 = vonk * dtheta / (math.log(z2 / z1) + betam * (z2 - z1) / mol)
            thetastar1 = corr_th(thetastar1)
            mol = ustar1 * ustar1 * T / (vonk * g * thetastar1)
            lst[iter_] = mol
            ust[iter_] = ustar1
            thst[iter_] = thetastar1
            z_over_l[iter_] = z_on_l
        else:
            if zr > 0.5 * mol:
                ustar1 = vonk * ws / (math.log(zr / z0) + 7.0 * math.log(zr / mol) + 4.25 / (zr / mol) -
                                      0.5 / ((zr / mol) * (zr / mol)) + (betam / 2.0) - 1.648)
            else:
                ustar1 = vonk * ws / (math.log(zr / z0) + betam * zr / mol)
            thetastar1 = vonk * dtheta / (math.log(z2 / z1) + betam * (z2 - z1) / mol)
            thetastar1 = corr_th(thetastar1)
            mol = ustar1 * ustar1 * T / (vonk * g * thetastar1)
    thetastar1 = vonk * dtheta / (math.log(z2 / z1) + betam * (z2 - z1) / mol)
    thetastar1 = corr_th(thetastar1)

    def recalcular():
        nonlocal mol, ustar1, thetastar1, z_on_l, z0_on_l, term, term0
        mol, ustar1, thetastar1 = templ, tempu, tempth
        z_on_l = zr / mol
        z0_on_l = z0 / mol
        term = alpha1 * z_on_l ** beta1 * (1.0 + gamma1 * z_on_l ** (1.0 - beta1))
        term0 = alpha1 * z0_on_l ** beta1 * (1.0 + gamma1 * z0_on_l ** (1.0 - beta1))
        ustar1 = vonk * ws / (term - term0)
        thetastar1 = vonk * dtheta / (math.log(z2 / z1) + betam * (z2 - z1) / mol)
        ustarmax = 0.6 * (zr / (math.log(zr / z0))) ** 0.33333
        thetastar1 = min(thetastar1, 0.1 * (1.0 - (min((2.0 * ustar1) / ustarmax, 1.0) - 1.0) ** 2))
        if ustarmax <= ustar1:
            ustar1 = ustarmax
        thetastar1 = corr_th(thetastar1)
        mol = ustar1 * ustar1 * T / (vonk * g * thetastar1)
        z_on_l = zr / mol

    if p.adjustar:
        if iter_ == 20:
            if z_over_l[20] > 99.0:
                recalcular()
            else:
                k = 0
                rpt = 0
                test = True
                while test:
                    k += 1
                    if k < 20:
                        if abs(z_over_l[20] - z_over_l[20 - k]) < 0.0001:
                            rpt = k
                            test = False
                    else:
                        recalcular()
                        break
                iter_ += 1
                utemp = thtemp = ltemp = 0.0
                counter = 0
                if rpt > 0:
                    for j in range(1, rpt + 1):
                        if z_over_l[iter_ - j] < 0.7:
                            utemp += ust[iter_ - j]
                            thtemp += thst[iter_ - j]
                            ltemp += lst[iter_ - j]
                            counter += 1
                    if counter == 0:
                        ustar1 = -9.0
                        thetastar1 = -9.0
                        mol = -99999.0
                    else:
                        ustar1 = utemp / float(counter)
                        thetastar1 = thtemp / float(counter)
                        mol = ltemp / float(counter)
                    z_on_l = zr / mol
        elif iter_ < 20:
            if z_on_l > 0.7:
                recalcular()
                thetastar1 = vonk * dtheta / (math.log(z2 / z1) + betam * (z2 - z1) / mol)
                thetastar1 = corr_th(thetastar1)
                mol = ustar1 * ustar1 * T / (vonk * g * thetastar1)
                z_on_l = zr / mol
    sd.theta_star[h] = thetastar1
    sd.ustar[h] = ustar1
    sd.mol[h] = mol


def check_flux(E, d, h):
    m, p = E.m, E.pb
    sd = p.sfc_data[d]
    vonk, g, cp = m.vonk, m.g, m.cp
    hlim = -64.0
    betam = 4.7 if p.adjustar else 5.0
    zr, z0, T = sd.wind_ht[h], sd.zo[h], sd.airtemp[h]
    rho = p.rho[h][d]
    if p.adjustar:
        cdn = vonk / math.log((zr - 5.0 * z0) / z0)
        xlimit = -hlim / (rho * cp)
        cc = betam * (zr - 5.0 * z0) * g * xlimit * cdn / T
    else:
        cdn = vonk / math.log(zr / z0)
        xlimit = -hlim / (rho * cp)
        cc = betam * zr * g * xlimit * cdn / T
    if sd.ustar[h] * sd.theta_star[h] > xlimit:
        aa = -cdn * sd.wspd[h]
        bb = 0.0
        a3 = aa / 3.0
        ap = bb - aa * a3
        bp = 2.0 * (a3 * a3 * a3) - a3 * bb + cc
        ap3 = ap / 3.0
        bp2 = bp / 2.0
        troot = bp2 * bp2 + ap3 * ap3 * ap3
        if troot > 0.0:
            tr = math.sqrt(troot)
            test = -bp2 + tr
            bsv = -bp2 - tr
            if test > 0.0:
                ustrout = -9.0
            else:
                app = _pow(test, 0.333333)
                if bsv != 0.0:
                    sgn = dsign(1.0, bsv)
                    bpp = sgn * (abs(bsv)) ** 0.333333
                    ustrout = sngl(app + bpp - a3)
                else:
                    ustrout = sngl(app - a3)
        else:
            cm = 2.0 * math.sqrt(-ap3)
            alpha = math.acos(bp / (ap3 * cm)) / 3.0
            ustrout = sngl(cm * math.cos(alpha) - a3)
        if abs(ustrout - (-9.0)) > 0.01:
            sd.ustar[h] = ustrout
            sd.theta_star[h] = xlimit / sd.ustar[h]
        else:
            sd.theta_star[h] = -hlim / (rho * cp * sd.ustar[h])


def _sq(x):
    return x * x


def _dv(a, b):
    """a/b con la aritmética IEEE del original (x/0 = ±Inf, 0/0 = NaN) en vez de una excepción."""
    if b != 0.0:
        return a / b
    if a != a or a == 0.0:
        return math.nan
    return math.copysign(math.inf, a) * math.copysign(1.0, b)


# DMAX1(a, NaN) de Intel devuelve NaN (comprobado con aermet.exe: u* = NaN con ADJ_U* y viento repuesto)
DMAX1_NAN_DEVUELVE_A = False


def _dmax1(a, b):
    if b != b:
        return a if DMAX1_NAN_DEVUELVE_A else b
    if a != a:
        return b
    return a if a >= b else b


def _p4(x):
    t = x * x
    return t * t


def _p6(x):
    t = x * x
    return t * t * t


def _pow(x, y):
    """x**y de Fortran para x<=0: 0**y=0; base negativa con exponente no entero → NaN."""
    if x == 0.0:
        return 0.0
    if x < 0.0:
        return float("nan")
    return x ** y


def mech_ht(E, d, h):
    m, p, o = E.m, E.pb, E.os
    modnam = fx("MECH_HT", 10)
    formstr1 = fmt_msg(E, "a,1x,f6.1,1x,a,1x,a20)")
    formstr2 = fmt_msg(E, "a20,1x,a)")
    sd = p.sfc_data[d]
    betatau, deltat, xconst, explim = 2.0, 3600.0, 2400.0, 50.0
    date_hr_str = fwrite("(a5,1x,i8,1x,a2,1x,i2.2)", "DATE:", sd.sfcdate, "HR", h)[0]
    ov = o.osvars
    if p.onmix and (not p.cbl[h][d] and not p.run_coare):
        mixht = float(o.osdata1[ov[o.mix_var].readvar, 1, h, p.ios[d]])
    else:
        mixht = xconst * sd.ustar[h] ** 1.5
        if ov[o.mix_var].lread and not p.onmix and not p.cbl[h][d]:
            E.w(m.msg_unit, formstr2, pid(E), "I87", modnam, date_hr_str, "CALCULATED MECHANICAL MIXING HEIGHT")
    if mixht > p.mech_max:
        mixht = p.mech_max
        E.w(m.msg_unit, formstr1, pid(E), "I79", modnam, "SBL HT SET TO", p.mech_max, "FOR", date_hr_str)
    if h == 1 and d == 1:
        sd.zim[h] = mixht
    else:
        if h == 1:
            prev_hr, prev_day = 24, d - 1
        else:
            prev_hr, prev_day = h - 1, d
        zprev = p.sfc_data[prev_day].zim[prev_hr]
        if zprev > 0.0 and abs(sd.ustar[h] - (-9.0)) > m.eps:
            tau = zprev / (betatau * sd.ustar[h])
            xponen = deltat / tau
            if xponen > explim:
                sd.zim[h] = mixht
            else:
                sd.zim[h] = zprev * math.exp(-xponen) + mixht * (1.0 - math.exp(-xponen))
        elif zprev > 0.0 and abs(sd.ustar[h] - (-9.0)) <= m.eps:
            sd.zim[h] = mixht
        else:
            sd.zim[h] = mixht
    if sd.zim[h] == 0.0:
        E.w(m.msg_unit, formstr2, pid(E), "W75", modnam, date_hr_str, "MECHANICAL MIXING HEIGHT = 0 M")


def read_sound(E, d, station_use, lsub1):
    m, p, u = E.m, E.pb, E.up
    modnam = fx("READ_SOUND", 10)
    formstr1 = fmt_msg(E, "2(a,1x,i8,1x),a,1x,i2.2,1x,a,1x,i2)")
    formstr2 = fmt_msg(E, "a,1x,i8,1x,a)")
    formstr3 = fmt_msg(E, "a,1x,i8,1x,a,1x,f4.1,1x,a)")
    formstr4 = fmt_msg(E, "a,1x,i8,1x,a,2(1x,f4.1,1x,a))")
    sd = p.sfc_data[d]
    p.lextend = False
    p.lextended = False
    si = u.sound_info[p.iup[d]][station_use]
    isnd = p.isnd[d]
    if station_use == 1:
        if lsub1:
            E.w(m.msg_unit, formstr1, pid(E), "I77", modnam, "SOUNDING FOR DATE:", sd.sfcdate,
                "IS SUBSTITUTED WITH DATE/HR", si.snddate, "HR", si.snd_hr[isnd], "SOUNDING #", isnd)
        else:
            E.w(m.msg_unit, formstr1, pid(E), "I77", modnam, "SOUNDING FOR DATE:", sd.sfcdate, "IS",
                si.snddate, "HR", si.snd_hr[isnd], "SOUNDING #", isnd)
    else:
        E.w(m.msg_unit, formstr1, pid(E), "I77", modnam, "SOUNDING FOR DATE:", sd.sfcdate,
            "IS SECONDARY SUBSTITUTION WITH DATE/HR", si.snddate, "HR", si.snd_hr[isnd], "SOUNDING #", isnd)
    U = u.updata.get(station_use, p.iup[d], isnd)
    nlv = si.nlevels[isnd]
    if U[2][nlv] < float(u.uptop):
        nlevs = nlv + 1
        p.lextend = True
    else:
        nlevs = nlv
    p.nlevs = nlevs
    uv = u.upvars
    m1 = float(uv[1].missval[station_use])
    m2 = float(uv[2].missval[station_use])
    m3 = float(uv[3].missval[station_use])
    pres = [m1] * (nlevs + 1)
    ht = [m2] * (nlevs + 1)
    tempk = [m3] * (nlevs + 1)
    theta = [m3] * (nlevs + 1)
    eps = m.eps
    for ilev in range(1, nlevs + 1):
        if ilev <= nlv:
            pres[ilev] = U[1][ilev]
            ht[ilev] = U[2][ilev]
            tempk[ilev] = U[3][ilev]
        if abs(pres[ilev] - m1) < eps or abs(ht[ilev] - m2) < eps or abs(tempk[ilev] - m3) < eps:
            continue
        tempk[ilev] = tempk[ilev] + 273.15
        theta[ilev] = tempk[ilev] * (1000.0 / pres[ilev]) ** 0.2857
    if p.lextend:
        zdz = ht[nlevs - 1] - 500.0
        if zdz >= 100.0:
            ilev = nlevs - 2
            p.lextended = False
            while ilev >= 1 and not p.lextended:
                if ht[nlevs - 1] - ht[ilev] >= 500.0:
                    ptzdz = theta[ilev] + (zdz - ht[ilev]) / (ht[ilev + 1] - ht[ilev]) * (theta[ilev + 1] - theta[ilev])
                    dtdz = (theta[nlevs - 1] - ptzdz) / 500.0
                    dt = (float(u.uptop) - ht[nlevs - 1]) * dtdz
                    theta[nlevs] = theta[nlevs - 1] + dt
                    ht[nlevs] = float(u.uptop)
                    p.lextended = True
                else:
                    ilev -= 1
            if not p.lextended:
                E.w(m.msg_unit, formstr2, pid(E), "W76", modnam, "DATE:", sd.sfcdate,
                    "CANNOT EXTEND SOUNDING; TWO LEVELS NOT FOUND FOR POTENTIAL TEMPERATURE")
                nlevs -= 1
        else:
            E.w(m.msg_unit, formstr3, pid(E), "W76", modnam, "DATE:", sd.sfcdate, "TOP OF SOUNDING",
                ht[nlevs - 1] / 1000.0, "KM IS TOO LOW; SOUNDING NOT EXTENDED")
            nlevs -= 1
    else:
        E.w(m.msg_unit, formstr4, pid(E), "W76", modnam, "DATE", sd.sfcdate, "TOP OF SOUNDING",
            ht[nlevs] / 1000.0, "KM EXTENDS BEYOND", float(u.uptop) / 1000.0, "KM; SOUNDING NOT EXTENDED")
    p.nlevs = nlevs
    p.pres, p.ht, p.tempk, p.theta = pres, ht, tempk, theta


def conv_ht(E, d, station_use, cblhr1):
    m, p, u = E.m, E.pb, E.up
    modnam = fx("CONV_HT", 10)
    formstr1 = fmt_msg(E, "a,1x,f7.1,1x,a,1x,a20,1x,a,1x,f7.1)")
    formstr2 = fmt_msg(E, "a,1x,f6.1,1x,a,1x,a20)")
    formstr3 = fmt_msg(E, "a20,1x,a)")
    sd = p.sfc_data[d]
    inc = 15
    capa = 0.2
    homin = 0.0001
    eps = m.eps
    nlevs = p.nlevs
    theta, ht = p.theta, p.ht
    theta_sum = [0.0] * (nlevs + 1)
    theta_a = [0.0] * (nlevs + 1)
    theta_max = theta[1]
    theta_sum[1] = 0.0
    for ilev in range(2, nlevs + 1):
        if theta[ilev] < theta_max:
            theta_a[ilev] = 0.0
            theta[ilev] = theta_max
        else:
            theta_a[ilev] = 0.5 * (theta[ilev] - theta[ilev - 1]) * (ht[ilev] + ht[ilev - 1])
            theta_max = max(theta[ilev], theta_max)
        theta_sum[ilev] = theta_sum[ilev - 1] + theta_a[ilev]
    hf = sd.hflux
    for h in range(cblhr1 + 1, 24):
        if (p.cbl[h][d] and abs(hf[h] - (-999.0)) <= eps and abs(hf[h - 1] - (-999.0)) > eps and
                abs(hf[h + 1] - (-999.0)) > eps and (hf[h - 1] > 0.0 or hf[h + 1] > 0.0)):
            hf[h] = (hf[h - 1] + hf[h + 1]) / 2.0
    last_conv_hr = 0
    h = cblhr1 + 1
    while last_conv_hr == 0 and h <= 24:
        if (hf[h] < homin and abs(hf[h] - (-999.0)) > eps and hf[h - 1] < homin and
                abs(hf[h - 1] - (-999.0)) > eps):
            last_conv_hr = h - 2
        else:
            h += 1
    if last_conv_hr == 0:
        h = 23
        while last_conv_hr == 0 and h >= cblhr1:
            if hf[h] <= 0.0 and hf[h - 1] > 0.0:
                last_conv_hr = h - 1
            else:
                h -= 1
    mm1 = cblhr1 * 60 - 30
    mm2 = last_conv_hr * 60
    smh = [0.0] * 25
    for h in range(1, last_conv_hr + 1):
        if h == cblhr1:
            smh[h] = hf[h] * 3600.0
        elif h > cblhr1 and hf[h] >= 0.0:
            smh[h] = hf[h] * 3600.0 + smh[h - 1]
        elif h > cblhr1 and hf[h] <= 0.0:
            smh[h] = smh[h - 1]
    oldh = 0.0
    for kk in range(mm1 + inc, mm2 + 1, inc):
        it1 = kk // 60
        it2 = it1 + 1
        if it1 == 0:
            it1 = 1
        if it2 == 25:
            it2 = 24
        sheat = smh[it1] + ((smh[it2] - smh[it1]) / 60.0) * (float(kk) - float(it1) * 60.0)
        if sheat < oldh:
            sheat = oldh
        oldh = sheat
        kk60 = kk // 60
        density = p.rho[kk60][d] if p.rho[kk60][d] > 0.0 else 1.2
        harea = (sheat / (density * m.cp)) * (1.0 + 2.0 * capa)
        gotzi = False
        ilev = 2
        pblht = 0.0
        while not gotzi and ilev <= nlevs:
            if harea < theta_sum[ilev]:
                if theta_sum[ilev] == theta_sum[ilev - 1]:
                    pblht = ht[ilev - 1]
                else:
                    pblht = math.sqrt(_sq(ht[ilev - 1]) + (harea - theta_sum[ilev - 1]) *
                                      (_sq(ht[ilev]) - _sq(ht[ilev - 1])) / (theta_sum[ilev] - theta_sum[ilev - 1]))
                gotzi = True
            else:
                ilev += 1
        if not gotzi and harea >= theta_sum[nlevs]:
            pblht = ht[nlevs]
        if pblht == 0:
            pblht = -999.0
        if kk % 60 == 0:
            if p.cbl[kk60][d] and sd.zic[kk60] < 0.0:
                sd.zic[kk60] = pblht
                date_hr_str = fwrite("(a5,1x,i8,1x,a2,1x,i2.2)", "DATE:", sd.sfcdate, "HR", kk60)[0]
                if sd.zic[kk60] == 0.0:
                    E.w(m.msg_unit, formstr3, pid(E), "W75", modnam, date_hr_str, "CONVECTIVE MIXING HEIGHT = 0 M")
                if p.lextended:
                    if pblht > ht[nlevs - 1]:
                        E.w(m.msg_unit, formstr1, pid(E), "W77", modnam, "CBL HT", pblht, "FOR", date_hr_str,
                            "EXCEEDS ORIGINAL SOUNDING TOP", ht[nlevs - 1])
                if sd.zic[kk60] > p.conv_max:
                    sd.zic[kk60] = p.conv_max
                    E.w(m.msg_unit, formstr2, pid(E), "I79", modnam, "CBL HT SET TO", p.conv_max, "FOR", date_hr_str)
            if (sd.mol[kk60] < 0.0 and abs(sd.mol[kk60] - (-99999.0)) > eps and p.rho[kk60][d] > 0.0 and
                    0.0 < sd.airtemp[kk60] < 900.0 and hf[kk60] > -900.0 and abs(hf[kk60] - 777.0) > eps and
                    pblht > 0.0 and not p.onwstar):
                if not p.onwstar:
                    sd.wstar[kk60] = wstar(E, d, kk60)
                if not p.onvptg:
                    sd.vptg[kk60] = vptg(E, d, kk60)


def wstar(E, d, h):
    m, p = E.m, E.pb
    modnam = fx("WSTAR", 10)
    formstr = fmt_msg(E, "a,1x,a20)")
    sd = p.sfc_data[d]
    date_hr_str = fwrite("(a5,1x,i8,1x,a2,1x,i2.2)", "DATE:", sd.sfcdate, "HR", h)[0]
    x = m.g * sd.hflux[h] * sd.zic[h] / (p.rho[h][d] * m.cp * sd.airtemp[h])
    w = _pow(x, 0.333)
    if 0.0 < w < 0.001:
        w = 0.001
        E.w(m.msg_unit, formstr, pid(E), "W78", modnam, "W* < 0.001; RESET TO 0.001 FOR", date_hr_str)
    return w


def vptg(E, d, h):
    p = E.pb
    sd = p.sfc_data[d]
    zi = max(sd.zic[h], sd.zim[h])
    nlevs = p.nlevs
    ht, theta = p.ht, p.theta
    sound_top = ht[nlevs - 1] if p.lextended else ht[nlevs]
    if (sound_top - zi) > 250.0:
        delz = min(500.0, (sound_top - 0.1))
        levs_found1 = False
        ilev = 1
        ilev1 = ilev2 = 0
        while not levs_found1 and ilev <= nlevs:
            if zi > ht[ilev]:
                ilev1 = ilev
            else:
                ilev2 = ilev
                if ilev1 > 0:
                    levs_found1 = True
            ilev += 1
        if levs_found1:
            theta_zi = ((zi - ht[ilev1]) / (ht[ilev2] - ht[ilev1])) * (theta[ilev2] - theta[ilev1]) + theta[ilev1]
            levs_found2 = False
            ilev = 1
            z_delz = zi + delz
            ilev3 = ilev4 = 0
            while not levs_found2 and ilev <= nlevs:
                if z_delz > ht[ilev]:
                    ilev3 = ilev
                else:
                    ilev4 = ilev
                    levs_found2 = True
                ilev += 1
            if levs_found2:
                theta_dz = ((z_delz - ht[ilev3]) / (ht[ilev4] - ht[ilev3])) * (theta[ilev4] - theta[ilev3]) + theta[ilev3]
            else:
                theta_dz = 0.0
            dtheta_dz = (theta_dz - theta_zi) / (z_delz - zi)
            return max(dtheta_dz, 0.005)
        return 0.005
    return 0.005


def profile(E, d, h, ostemp):
    m, p, s, o = E.m, E.pb, E.sf, E.os
    modnam = fx("PROFILE", 10)
    formstr = fmt_msg(E, "3(a,1x),a20)")
    ov = o.osvars
    sd = p.sfc_data[d]
    pf = p.pfl_data[h][d]
    date_hr_str = fwrite("(a5,1x,i8,1x,a2,1x,i2.2)", "DATE:", sd.sfcdate, "HR", h)[0]
    gotos = False
    eps = m.eps
    if p.os_obs[h][d]:
        osd = o.osdata1
        iosd = p.ios[d]
        tv = ov[o.temp_var]
        tsrc = p.tempsrc[h][d]
        if (tsrc == 1 or (tsrc == 3 and ostemp)) or (tsrc == 0 and tv.lread):
            for ilev in range(1, p.pfl_levels + 1):
                if p.windsrc[h][d] != 2:
                    pf.airtemp[ilev] = float(osd[tv.readvar, ilev, h, iosd])
                else:
                    if abs(float(osd[1, ilev, h, iosd]) - sd.temp_ht[h]) < eps:
                        pf.airtemp[ilev] = float(osd[tv.readvar, ilev, h, iosd])
                    pf.sigma_a[ilev] = 99.0
                    pf.sigma_w[ilev] = 99.0
        ws, wd, sa, sw = ov[o.wind_vars[2]], ov[o.wind_vars[1]], ov[o.sa_var], ov[o.sw_var]
        ilev = 1
        while ilev <= p.pfl_levels and not gotos:
            if (abs(pf.speed[ilev] - (ws.missval * ws.conv)) > eps or abs(pf.dir[ilev] - (wd.missval * wd.conv)) > eps
                    or abs(pf.airtemp[ilev] - (tv.missval * tv.conv)) > eps or
                    abs(pf.sigma_a[ilev] - (sa.missval * sa.conv)) > eps or
                    abs(pf.sigma_w[ilev] - (sw.missval * sw.conv)) > eps):
                gotos = True
            ilev += 1
    if not gotos and m.lpath[4]:
        if p.lactions[3]:
            pf.speed[1] = sd.wspd[h]
            pf.dir[1] = sd.wdir[h]
            if sd.airtemp[h] < 900.0:
                pf.airtemp[1] = sd.airtemp[h] - 273.15
            pf.ht[1] = s.nws_hgt
            p.pfl_nlevels[h][d] = 1
            if m.lpath[4]:
                E.w(m.msg_unit, formstr, fx(m.pathid[4], 10), "I90", modnam, "NWS DATA SUBSTITUTED FOR",
                    m.pathid[4].strip(), "DATA FOR", date_hr_str)


def sfc_header(E):
    m, p, u, s, o = E.m, E.pb, E.up, E.sf, E.os
    if p.pbllat < 0.0:
        alat = fwrite("(f7.3,a1)", abs(p.pbllat), "S")[0]
    else:
        alat = fwrite("(f7.3,a1)", p.pbllat, "N")[0]
    if p.pbllon < 0.0:
        alon = fwrite("(f8.3,a1)", abs(p.pbllon), "W")[0]
    else:
        alon = fwrite("(f8.3,a1)", p.pbllon, "E")[0]
    hdrstr = fwrite("(2x,a9,a9,8x,3(a,a8),t85,a,1x,a5)", fx(alat, 9), fx(alon, 9), "  UA_ID: ", fx(u.upid[1], 8),
                    "  SF_ID: ", fx(s.sfid, 8), "  OS_ID: ", fx(o.osid, 8), "VERSION:", m.versn)[0]
    if p.subcloud:
        substr = "CCVR_Sub TEMP_Sub" if p.subtemp else "CCVR_Sub"
    else:
        substr = "TEMP_Sub" if p.subtemp else ""
    threshstr = ""
    if m.lkey[35]:
        threshstr = fwrite("(a,f5.2,a)", "THRESH_1MIN = ", s.asos_thresh, " m/s;")[0]
    adjustarstr = m.actions[7].strip() if p.adjustar else ""
    progstr = ""
    if m.lpath[5]:
        progstr = fx(fwrite("(a,1x,a)", m.pathid[5].strip(), p.mmif_versn.strip())[0], 25)
    bulkrnstr = ""
    if p.lactions[4] and not p.run_coare:
        if m.lpath[5]:
            bulkrnstr = fwrite("(a7,a4)", "BULKRN/", m.pathid[5].strip())[0]
        else:
            bulkrnstr = fwrite("(a6)", "BULKRN")[0]
    coarestr = ""
    E.w(m.sfc_out_unit, "(a98,6(1x,a))", fx(hdrstr, 98), threshstr.strip(), adjustarstr.strip(),
        bulkrnstr.strip(), substr.strip(), progstr.strip(), coarestr.strip())


SFCFORM = ("(i4,1x,2(i2,1x),i3,1x,i2,1x,f6.1,1x,f6.3,1x,f6.3,1x,f6.3,1x,2(f5.0,1x),f8.1,1x,f7.4,1x,f6.2,1x,"
           "f6.2,1x,f7.2,1x,f6.1,3(1x,f6.1),1x,i5,1x,f6.2,2(1x,f6.0),1x,i5,1x,a7,1x,a9)")
PFLFORM = "(i4,1x,3(i2,1x),f7.1,1x,i1,1x,f7.1,1x,f8.2,1x,f8.2,1x,f8.2,1x,f8.2)"


def writefiles(E, d):
    m, p = E.m, E.pb
    sd = p.sfc_data[d]
    iyear, imonth, iday = sd.sfcdate // 10000, (sd.sfcdate // 100) % 100, sd.sfcdate % 100
    fs = E.units.get(m.sfc_out_unit)
    fp = E.units.get(m.pfl_out_unit)
    lin_s = []
    lin_p = []
    for h in range(1, 25):
        sfcline = fwrite(SFCFORM, iyear, imonth, iday, sd.jday, h, sd.hflux[h], sd.ustar[h], sd.wstar[h],
                         sd.vptg[h], sd.zic[h], sd.zim[h], sd.mol[h], sd.zo[h], sd.bowen[h], sd.albedo[h],
                         sd.wspd[h], sd.wdir[h], sd.wind_ht[h], sd.airtemp[h], sd.temp_ht[h], sd.ipcode[h],
                         sd.pamt[h], sd.rh[h], sd.pres[h], sd.ccvr[h], fx(sd.windsrcflag[h], 7),
                         fx(sd.subflag[h], 9))[0]
        if "*" in sfcline or "NaN" in sfcline:
            p.nsfc_over += 1
            check_surf(E, d, h, sfcline)
            p.lbadout = True
        lin_s.append(sfcline)
        pf = p.pfl_data[h][d]
        nlv = p.pfl_nlevels[h][d]
        for ilev in range(1, nlv + 1):
            itop = 1 if ilev == nlv else 0
            pflline = fwrite(PFLFORM, iyear, imonth, iday, h, pf.ht[ilev], itop, pf.dir[ilev], pf.speed[ilev],
                             pf.airtemp[ilev], pf.sigma_a[ilev], pf.sigma_w[ilev])[0]
            if "*" in pflline or "NaN" in pflline:
                p.npfl_over += 1
                check_prof(E, d, h, ilev, pflline)
                p.lbadout = True
            lin_p.append(pflline)
    if fs is not None:
        fs.escribir(lin_s)
    else:
        for x in lin_s:
            E.w(m.sfc_out_unit, "(a)", x)
    if fp is not None:
        fp.escribir(lin_p)
    else:
        for x in lin_p:
            E.w(m.pfl_out_unit, "(a)", x)


def check_surf(E, d, h, sfcline):
    m, p = E.m, E.pb
    modnam = fx("CHECK_SURF", 10)
    istops = [None, 2, 5, 8, 12, 15, 22, 29, 36, 43, 49, 55, 64, 72, 79, 86, 94, 101, 108, 115, 122, 128, 135,
              142, 149, 155]
    warnlim = 100
    p.save_check_surf_iwarn += 1
    iwarn = p.save_check_surf_iwarn
    formstr1 = fmt_msg(E, "a,1x,i3,1x,a3,1x,a)")
    formstr2 = fmt_msg(E, "3(a,1x),a20)")
    if iwarn == warnlim:
        E.w(m.msg_unit, formstr1, pid(E), "W87", modnam, "REACH LIMIT OF", warnlim, "E85", "ERROR MESSAGES")
    sd = p.sfc_data[d]
    date_hr_str = fwrite("(a5,1x,i8,1x,a2,1x,i2.2)", "DATE:", sd.sfcdate, "HR", h)[0]
    for ivar in range(1, 26):
        istart = 1 if ivar == 1 else istops[ivar - 1] + 1
        istop = istops[ivar]
        seg = sfcline[istart - 1:istop]
        if "*" in seg:
            if iwarn <= warnlim:
                E.w(m.msg_unit, formstr2, pid(E), "E85", modnam, "SURFACE VARIABLE", p.sfcvar[ivar].strip(),
                    "EXCEEDS FORMAT FOR", date_hr_str)
            p.bad_sfc_vars[ivar] += 1
        if "NaN" in seg:
            if iwarn <= warnlim:
                E.w(m.msg_unit, formstr2, pid(E), "E85", modnam, "SURFACE VARIABLE", p.sfcvar[ivar].strip(),
                    "HAS BAD VALUE FOR", date_hr_str)
            p.bad_sfc_vars[ivar] += 1


def check_prof(E, d, h, ilev, pflline):
    m, p = E.m, E.pb
    modnam = fx("CHECK_PROF", 10)
    istops = [None, 2, 5, 8, 11, 19, 21, 29, 38, 47, 56, 65]
    warnlim = 100
    p.save_check_prof_iwarn += 1
    iwarn = p.save_check_prof_iwarn
    formstr1 = fmt_msg(E, "a,1x,i3,1x,a3,1x,a)")
    formstr2 = fmt_msg(E, "3(a,1x),i4,1x,a,1x,a20)")
    date_hr_str = fwrite("(a5,1x,i8,1x,a2,1x,i2.2)", "DATE:", p.pfl_data[h][d].pfldate, "HR", h)[0]
    if iwarn == warnlim:
        E.w(m.msg_unit, formstr1, pid(E), "W87", modnam, "REACH LIMIT OF", warnlim, "E86", "ERROR MESSAGES")
    for ivar in range(1, 12):
        istart = 1 if ivar == 1 else istops[ivar - 1] + 1
        istop = istops[ivar]
        seg = pflline[istart - 1:istop]
        if "*" in seg:
            if iwarn <= warnlim:
                E.w(m.msg_unit, formstr2, pid(E), "E86", modnam, "PROFILE VARIABLE", p.pflvar[ivar].strip(),
                    "EXCEEDS FORMAT FOR LEVEL", ilev, "FOR", date_hr_str)
            p.bad_pfl_vars[ivar] += 1
        if "NaN" in seg:
            if iwarn <= warnlim:
                E.w(m.msg_unit, formstr2, pid(E), "E86", modnam, "PROFILE VARIABLE", p.pflvar[ivar].strip(),
                    "HAS BAD VALUE FOR LEVEL", ilev, "FOR", date_hr_str)
            p.bad_pfl_vars[ivar] += 1
