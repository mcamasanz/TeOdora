# -*- coding: utf-8 -*-
"""Traducción de AERMET 26135 (US EPA, dominio público): estado global.

El original reparte su estado en módulos Fortran (MAIN1, FILE_UNITS, READ_INPUT, UPPERAIR,
SURFACE, ONSITE, PBL) con variables globales que las subrutinas leen y modifican. La traducción
conserva ese diseño: un objeto `Estado` con un espacio de nombres por módulo (``E.m``, ``E.up``,
``E.sf``, ``E.os``, ``E.pb``) y los mismos nombres de variable. Los vectores pequeños son listas
con el índice 0 sin usar; las matrices de datos son ``numpy`` con una posición extra por
dimensión para usar directamente los índices 1..N del Fortran.

Las unidades de E/S se emulan con `fortran.Fichero`; la unidad 6 es la pantalla.
"""
import os
from types import SimpleNamespace

import numpy as np

from . import tablas as T
from .formato import Fichero, fwrite

OUTPUT_UNIT = 6
VERSN = "26135"
MSG_FORM = "(1x,a10,1x,a3,5x,a10,1x,"


def arr(*dims, val=0.0, dtype=float):
    """Matriz con índices 1..dims (posición 0 sin usar en cada dimensión)."""
    return np.full(tuple(d + 1 for d in dims), val, dtype=dtype)


def vec(n, val=0):
    return [val] * (n + 1)


class Ovar:
    """Tipo ovars (mod_onsite)."""
    __slots__ = ("varname", "lread", "laudit", "lmod", "lnomiss", "luse", "lincbound", "readvar",
                 "misscount", "missval", "lowbound", "upbound", "firstlev", "nlevels", "conv")

    def __init__(self, t):
        for k, v in zip(self.__slots__, t):
            setattr(self, k, v)


class Uavar:
    """Tipo uavars (mod_upperair): componentes de 2 estaciones (índices 1 y 2)."""

    def __init__(self, t):
        nom, la, lm, ln, li, mv, lo, hi, cv = t
        self.varname = nom
        self.laudit = [None, la, la]
        self.lmod = [None, lm, lm]
        self.lnomiss = [None, ln, ln]
        self.lincbound = [None, li, li]
        self.missval = [None, mv, mv]
        self.lowbound = [None, lo, lo]
        self.upbound = [None, hi, hi]
        self.conv = [None, cv, cv]


class Svar:
    """Tipo svars (mod_surface)."""
    __slots__ = ("varname", "laudit", "lmod", "lnomiss", "lincbound", "missval", "lowbound",
                 "upbound", "conv")

    def __init__(self, t):
        for k, v in zip(self.__slots__, t):
            setattr(self, k, v)


class Formato:
    def __init__(self, t, campos):
        for k, v in zip(campos, t):
            setattr(self, k, v)


class Asos:
    __slots__ = ("city", "location", "state", "iwban", "intcall", "usacall", "ddlat", "ddlon",
                 "commisdate", "pub", "sitetype", "anem_feet", "anem_meters")

    def __init__(self, t):
        for k, v in zip(self.__slots__, t):
            setattr(self, k, v)


class Estado:
    def __init__(self, inpfile="aermet.inp"):
        self.pantalla = []
        self.units = {}
        self._inicial_main1(inpfile)
        self.up = SimpleNamespace()
        self.sf = SimpleNamespace()
        self.os = SimpleNamespace()
        self.pb = SimpleNamespace()
        self._inicial_upperair()
        self._inicial_surface()
        self._inicial_onsite()
        self._inicial_pbl()

    # ------------------------------------------------------------------ MAIN1/FILE_UNITS
    def _inicial_main1(self, inpfile):
        m = self.m = SimpleNamespace()
        m.npath, m.nkeys, m.nitems, m.nactions, m.ninstr, m.linelen = 7, 50, 9, 31, 1, 500
        m.ikey = m.ipath = m.nfield = m.ilen = 0
        m.fileind = [0, 0, 0]
        m.formind = [0, 0, 0]
        m.writeunit = 0
        m.runtimes = [[-1] * 9 for _ in range(3)]
        m.istage = 0
        m.r = 287.0406
        m.g = 9.80655
        m.d2r = float(np.float32(3.141592654)) / 180.0   # literal SIMPLE en el original
        m.eps = 0.01
        m.cp = 1004.0
        m.pi = 3.14159
        m.vonk = 0.4
        m.lpath = vec(m.npath, False)
        m.lkey = vec(m.nkeys, False)
        m.lstage = vec(2, False)
        m.noprint = False
        m.debug = False
        m.lbad = False
        m.use_second = False
        m.pathid = T.PATHID
        m.keywrd = T.KEYWRD
        m.items = T.ITEMS
        m.actions = T.ACTIONS
        m.instr = T.INSTR
        m.days = T.DAYS
        m.inpline = ""
        m.inpline1 = ""
        m.versn = VERSN
        m.msg_form = MSG_FORM
        # file_units
        m.flength = 300
        m.inp_unit, m.msg_unit, m.rpt_unit, m.debug_unit = 11, 12, 13, 29
        m.inpfile = inpfile
        m.msgfile = ""
        m.rptfile = ""
        m.dbgfile = "aermet_debug.txt"
        m.up_data_unit = [None, 14, 29]
        m.up_extract_unit = [None, 15, 30]
        m.up_qaout_unit = [None, 16, 31]
        m.up_inpfile = [None, "", ""]
        m.up_qafile = [None, "", ""]
        m.up_extfile = [None, "", ""]
        m.sf_data_unit, m.sf_extract_unit, m.sf_qaout_unit, m.one_min_unit = 17, 18, 19, 20
        m.ishd_units = [None, 21, 22]
        m.ghcn_units = [None, 21, 22]
        m.sf_inpfile = m.sf_qafile = m.sf_extfile = m.one_minfile = ""
        m.ishd_files = [None, "ISHD_discard.txt", "ISHD_replace.txt"]
        m.ghcn_files = [None, "GHCN_discard.txt", "GHCN_replace.txt"]
        m.os_data_unit, m.os_qaout_unit = 23, 24
        m.os_inpfile = m.os_qafile = ""
        m.sfc_char_unit = [None, 27, 28]
        m.sfc_charfile1 = None
        m.sfc_charfile2 = None
        m.sfc_out_unit, m.pfl_out_unit = 25, 26
        m.sfc_outfile = m.pfl_outfile = ""
        # read_input
        m.linenum = 0
        m.njbkeys = 5
        m.ljbkeywords = vec(5, False)
        m.lbad1 = False

    # ------------------------------------------------------------------ UPPERAIR
    def _inicial_upperair(self):
        u = self.up
        u.upstart = u.upend = 0
        u.nstation = 1
        u.updates = [[0] * 4 for _ in range(3)]                     # (2,3)
        u.updates1 = [[[0] * 4 for _ in range(3)] for _ in range(3)]  # (2,2,3)
        u.nupdays = 0
        u.nup_audit_vars = [None, 0, 0]
        u.nupvars1 = 0
        u.writelevs = 0
        u.savepress = 0
        u.upgmt2lst = [None, -99, -99]
        u.iupform = [None, 1, 1]
        u.nsound = [None, 0, 0]
        u.nuplevels = [None, 0, 0]
        u.nsnd = [[0] * 3 for _ in range(7)]   # nsnd(6,2) → nsnd[i][st]
        u.wind_stats = [[0] * 3 for _ in range(3)]
        u.tempstat = [None, 0, 0]
        u.nsnd_5k = [None, 0, 0]
        u.no_sound_days = [None, 0, 0]
        u.no_am_days = [None, 0, 0]
        u.upstarts = [None, 0, 0]
        u.upends = [None, 0, 0]
        u.nwarnlim = 100
        u.ltop = False
        u.lskip = False
        u.have_soundings = [None, False, False]
        u.uptop, u.maxlevels, u.nupvars, u.nupvars_keep, u.nupformats = 5000, 300, 10, 6, 5
        u.nupkeys, u.nmods, u.up_inc = 17, 3, 500
        u.snd_date = u.snd_hrs = u.s_levels = u.nsnding1 = None
        u.up_audit_index = u.up_audit_counts = None
        u.uplat = [None, 0.0, 0.0]
        u.uplon = [None, 0.0, 0.0]
        u.upelev = [None, 0.0, 0.0]
        u.updata1 = u.updata = None
        u.lupkeywords = vec(u.nupkeys, False)
        u.lbadup = False
        u.lsound = None
        u.writeext = [None, False, False]
        u.lmodify = [[False] * 3 for _ in range(u.nmods + 1)]  # lmodify(nmods,2)
        u.lgmt2lst = [None, False, False]
        u.lelev = [None, False, False]
        u.upstage1 = [None, False, False]
        u.lsecondary = False
        u.iupid = "0"
        u.upid = [None, "", ""]
        u.qaout_vars = None
        u.station_type = [None, "PRIMARY", "SECONDARY"]
        u.upvars = [None] + [Uavar(t) for t in T.UPVARS[1:]]
        u.upformats = [None] + [Formato(t, ("uformat", "lupform", "maxblock", "rdsz", "rdpos",
                                             "offset")) for t in T.UPFORMATS[1:]]
        u.sound_info = None
        u.ext_form = [None] * 15

    # ------------------------------------------------------------------ SURFACE
    def _inicial_surface(self):
        s = self.sf
        s.sfstart = s.sfend = s.sfstart1min = s.sfend1min = s.sonicdate = 0
        s.sfgmt2lst = -99
        s.iasos = 0
        s.sfdates = [[0] * 4 for _ in range(3)]
        s.nsfdays = s.nsf1mindays = s.isfform = 0
        s.nsfc = vec(12, 0)
        s.nsfvars1 = s.nsf_audit_vars = s.nsf_extra = s.irec = 0
        s.sf_windstats = vec(3, 0)
        s.sf_tempstat = 0
        s.precip_wx = vec(2, 0)
        s.nsfvars, s.nsfvars_keep, s.nsfformats, s.nsfkeys, s.nasos = 22, 11, 10, 9, 886
        s.sf_audit_index = s.sf_audit_counts = s.nsfc1 = None
        s.nsplit = 1
        s.iwban = 0
        s.isfid = 0
        s.nwarnlim = 100
        s.sflat = s.sflon = s.sfelev = s.sf_user_elev = 0.0
        s.asos_thresh = 0.0
        s.nws_hgt = -9.0
        s.sfdata = s.sfdata1 = s.missvals = s.lowbound = s.upbound = None
        s.lsfkeywords = vec(s.nsfkeys, False)
        s.lbadsfc = s.lasos = s.lgmt2lst = s.user_elev = s.lsfelev = s.writeext = False
        s.write_asos = False
        s.switch_asos = [None, False, False]
        s.sfstage1 = False
        s.lsfcobs = s.asoshr = s.nomisshr = None
        s.sfid = ""
        s.sf1minid = "-9"
        s.ext_form = [None] * 11
        s.qaout_vars = None
        # sin vía SURFACE el original deja sfvars a cero (memoria estática)
        s.sfvars = [None] + [Svar(("", False, False, False, False, 0, 0, 0, 0.0)) for _ in range(22)]
        s.asoscommdates = [None] + [Asos(t) for t in T.ASOS[1:]]
        s.sfformats = None
        s.sfc_info = None
        s.one_mindat = None

    # ------------------------------------------------------------------ ONSITE
    def _inicial_onsite(self):
        o = self.os
        o.osstart = o.osend = 0
        o.osgmt2lst = -99
        o.delta_t_ind = 1
        o.noshts = 0
        o.nlevel = 1
        o.nobs_hr = 1
        o.nread = o.nformat = o.nreadvars = o.nbadhts = o.min_obs = 0
        o.osdates = [[0] * 4 for _ in range(3)]
        o.nosdays = 0
        o.os_windstats = [[0] * 4 for _ in range(3)]   # (2,3)
        o.os_tempstat = [None, 0, 0]
        o.nos_audit_vars = 0
        for nom in ("hflux_var", "lflux_var", "ustar_var", "mix_var", "zo_var", "inso_var",
                    "nrad_var", "dt01_var", "vptg_var", "l_var", "wstar_var", "clht_var",
                    "height_var", "temp_var", "dewpt_var", "cloud_var", "slp_var", "pres_var",
                    "rh_var", "sa_var", "se_var", "sv_var", "sw_var", "su_var", "vv_var",
                    "alb_var", "bo_var", "samt_var", "tsea_var", "sstd_var", "hwav_var",
                    "twav_var", "rdow_var"):
            setattr(o, nom, 0)
        o.wind_vars = [None, 0, 0]
        o.prcp_vars = [None, 0, 0]
        o.std_vars = [None, 0, 0]
        o.nosvars, o.maxread, o.maxvars, o.maxlevel, o.maxdtind = 47, 50, 50, 50, 3
        o.min_obs_hr, o.max_obs_hr = 1, 12
        o.noskeys = 14
        o.formlen = 150
        o.varmap1 = o.varmap = o.os_audit_index = o.os_audit_counts = None
        o.read_index = o.ext_index = None
        o.nos = vec(5, 0)
        o.nvars = 0
        o.os_date = o.obs_per_hr = o.obs_minutes = None
        o.osdt_hts = None
        o.osheights1 = o.os_heights = None
        o.os_subhr_vals = o.osdata1 = o.osdata1a = None
        o.missvals = o.lowbound = o.upbound = None
        o.threshspeed = 0.0
        o.minthresh = 0.0
        o.progthresh = 0.0
        o.warnthresh = 0.5
        o.maxthresh = 1.0
        o.oslat = o.oslon = o.oselev = 0.0
        o.xdir = o.ydir = o.dirsum = 0.0
        o.osvars = [None] + [Ovar(t) for t in T.OSVARS[1:]]
        o.loskeywords = vec(o.noskeys, False)
        o.luseoshts = o.lvector = o.lbados = o.checktempdew = o.laudit_all = False
        o.lgmt2lst = o.loselev = False
        o.overland = True
        o.osstage1 = False
        o.read_sst_depth = False
        o.losobs = o.nomisshr = o.lcalm_obs = o.lcalm_obs_hr = None
        o.osid = ""
        o.os_format1 = o.os_format = o.os_reads = o.qaout_vars = None
        o.dattype = [None, "onsite", "PROG"]
        o.os_info = None
        # variables SAVE de subrutinas
        o.save_calc_wind_lastdir = 0.0
        o.save_read_os = {"nbad": 0, "savedate": 0}
        o.save_read_ext = {"savedate": 0}

    # ------------------------------------------------------------------ PBL
    def _inicial_pbl(self):
        p = self.pb
        p.pblstart = p.pblend = 0
        p.pbldates = [[0] * 4 for _ in range(3)]
        p.npbldays = 0
        p.pblgmt2lst = -9
        p.my_sounding = [None, 0, 0]
        p.target_hr_gmt = [None, 0, 0]
        p.snd_hr_gmt = [[0] * 3 for _ in range(3)]   # (2,2)
        p.snding_win = [None, -1, 1]
        p.nsc_years = p.nsc_files1 = p.nsc_files2 = 0
        p.n_cloud_sub = p.n_temp_sub = p.n_conv_miss = 0
        p.pfl_levels = 1
        p.os_ipath = 0
        p.nlevs = 0
        p.ihem = [None, 1, 1]
        p.pbl_windstats = vec(3, 0)
        p.bad_sfc_vars = vec(25, 0)
        p.bad_pfl_vars = vec(11, 0)
        p.day_window = [None, -1, 1]
        p.temp_upgmt = [None, 0, 0]
        p.sc_years = None
        p.nfreq1 = p.nsectors1 = p.nfreq2 = p.nsectors2 = None
        p.npblvars, p.npblkeys, p.minsec, p.maxsec = 12, 24, 1, 12
        p.mixopt = 0
        p.nsfc_over = p.npfl_over = 0
        p.pbllat = p.pbllon = 0.0
        p.pblelev = 0.0
        p.angle = p.crit_angle = p.inso = p.nrad = 0.0
        p.sst_depth = 0.5
        p.min_sst_depth = 0.0
        p.max_sst_depth = 10.0
        p.zi_gust = 600.0
        p.zi_min = 25.0
        p.min_l = 5.0
        p.def_vptg = float(np.float32(0.01))
        p.mech_max = 4000.0
        p.conv_max = 4000.0
        p.lpblkeywords = vec(p.npblkeys, False)
        p.lactions = vec(31, False)
        p.litems = vec(9, False)
        p.sec_sc = p.lgmt2lst = p.lelev = p.lbadpbl = False
        p.subtemp = p.subcloud = True
        p.havepress = p.adjustar = False
        for nom in ("onustar", "onmol", "onhflux", "onlflux", "onwstar", "onmix", "onnrad",
                    "oninso", "onvptg", "oncloud"):
            setattr(p, nom, False)
        p.lextend = p.lextended = p.lmmif_versn = p.lbadout = False
        p.luse_sst_dep = p.valid_depth = p.run_coare = False
        p.warm_layer = p.cool_skin = False
        p.coare_zo = vec(3, False)
        p.coare_mix = vec(6, False)
        p.run_coare_orig = False
        p.sub_upper = p.check_sec_first = False
        p.sites = [None, "PRIMARY", "SECONDARY"]
        p.pblid = "-9"
        p.mmif_versn = "UNKNOWN"
        p.sfcvar = [None, "YEAR", "MONTH", "DAY", "JDAY", "HOUR", "HFLUX", "U*", "W*", "VPTG",
                    "ZIC", "ZIM", "L", "ZO", "BO", "ALBEDO", "WSPD", "WDIR", "ZREF", "TEMP",
                    "ZTEMP", "IPCODE", "PRECIP", "RH", "PRES", "CCVR"]
        p.pflvar = [None, "YEAR", "MONTH", "DAY", "HOUR", "HT", "ITOP", "WDIR", "WSDP", "TEMP",
                    "SA", "SW"]
        p.yrstr1 = p.yrstr2 = None
        # variables SAVE
        p.save_check_surf_iwarn = 0
        p.save_check_prof_iwarn = 0
        p.save_site_char = {"albedo": -999.0, "bowen": -999.0, "zo": -999.0,
                            "goodfreq": False, "goodsec": False}
        p.save_sectors_goodsec = False
        p.save_pbl_path_isite = 0

    # ------------------------------------------------------------------ E/S
    def w(self, unidad, fmt, *items):
        lineas = fwrite(fmt, *items)
        if unidad == OUTPUT_UNIT:
            self.pantalla.extend(lineas)
        else:
            f = self.units.get(unidad)
            if f is None:
                # unidad no conectada: Intel crea fort.N
                f = Fichero("fort.%d" % unidad, "w", existente=False)
                self.units[unidad] = f
            f.escribir(lineas)

    def msg(self, fmt, *items):
        self.w(self.m.msg_unit, fmt, *items)

    def abrir(self, unidad, nombre, status):
        """OPEN(unit,file,status). Devuelve iostat (0 bien)."""
        nombre_n = nombre.rstrip()
        if unidad in self.units:
            self.cerrar(unidad)
        existe = os.path.isfile(nombre_n)
        if status == "old":
            if not existe:
                return 29
            f = Fichero(nombre_n, "r")
        elif status == "new":
            if existe:
                return 10
            if not _crear(nombre_n):
                return 29
            f = Fichero(nombre_n, "r", existente=False)
            f.escrito = True
        elif status == "replace":
            if not _crear(nombre_n):
                return 29
            f = Fichero(nombre_n, "r", existente=False)
            f.escrito = True
        else:  # unknown
            if existe:
                f = Fichero(nombre_n, "r")
            else:
                if not _crear(nombre_n):
                    return 29
                f = Fichero(nombre_n, "r", existente=False)
        f.unidad = unidad
        self.units[unidad] = f
        return 0

    def cerrar(self, unidad):
        f = self.units.pop(unidad, None)
        if f is not None:
            f.volcar()

    def abierto(self, nombre):
        """INQUIRE(file=nombre, opened=...)."""
        n = _norm(nombre)
        for f in self.units.values():
            if _norm(f.nombre) == n:
                return True
        return False

    def unidad_abierta(self, unidad):
        return unidad in self.units


def _norm(nombre):
    return os.path.normcase(os.path.abspath(nombre.rstrip()))


def _crear(nombre):
    try:
        with open(nombre, "w"):
            pass
        return True
    except OSError:
        return False
