# -*- coding: utf-8 -*-
"""Fichero de control de AERSURFACE (mod_ProcCtrlFile.f), con la misma semántica:
valores por defecto, orden de procesado de las palabras clave, ordenación de sectores
(incluida la peculiar reordenación de POSTSECT) y textos de meses por estación.

Alcance: CO TITLEONE/TITLETWO, OPTIONS, DEBUGOPT, CENTERLL y CENTERXY (NAD83), DATAFILE
(NLCD/MPRV/CNPY), ANEM_HGT, ZORADIUS, CLIMATE, FREQ_SECT (AP/NONAP/VARYAP/SECTRING), SECTOR
(con anillos H/L), SEASON, RUNORNOT; OU SFCCHAR, NLCDGRID, MPRVGRID, CNPYGRID.
Fuera (avisa y se niega): datum NAD27 (NADCON: solo EE. UU.)."""
import shlex
from dataclasses import dataclass, field
from pathlib import Path

import numpy as np

from .formato import nint, stodbl
from .utm import utm_a_geo

MAX_SEC, MAX_RINGS = 16, 25
EPS = float(np.float32(0.001))          # «eps = 0.001» de POSTSECT: literal REAL (simple)


@dataclass
class Control:
    titulo1: str = ""
    titulo2: str = ""
    estacion: str = "PRIMARY"
    metodo_zo: str = "ZORAD"
    zo_eff_flg: bool = False
    zo_rad_flg: bool = False
    anem_height: float = -9.0
    ibl_factor: float = 6.0
    zo_rad: float = 1000.0              # m
    coord_tipo: str = "LATLON"
    lat: float = None
    lon: float = None
    utm_e: float = None
    utm_n: float = None
    utm_zona: int = None
    datum: str = "NAD83"
    lc_file: str = ""
    imp_file: str = ""
    can_file: str = ""
    nlcd_year: int = 0
    imp_year: int = 0
    can_year: int = 0
    got_imp: bool = False
    got_can: bool = False
    num_sectores: int = 1
    vary_ap: bool = False
    airport: bool = True
    sect_ring: bool = False
    n_sec_ring: int = 0
    sec_id: list = field(default_factory=lambda: [0] * MAX_SEC)
    sec_start: list = field(default_factory=lambda: [0.0] * MAX_SEC)
    sec_end: list = field(default_factory=lambda: [0.0] * MAX_SEC)
    # sec_ap[sector][anillo]: anillo 1..25 (el 0 no se usa); por defecto .TRUE.
    sec_ap: list = field(default_factory=lambda: [[True] * (MAX_RINGS + 1)
                                                  for _ in range(MAX_SEC)])
    start_dir: list = field(default_factory=lambda: [0.0] * MAX_SEC)
    n_sector_kw: int = 0
    dflt_sec: bool = False
    humedad: str = "A"
    humedad_txt: str = "Average"
    nieve: bool = False
    nieve_chr: str = " "
    arido: bool = False
    arido_chr: str = " "
    res_temporal: str = "M"
    res_temporal_txt: str = "MONTHLY"
    asigna_meses: bool = False
    meses_estacion: list = field(default_factory=lambda: [1, 1, 3, 3, 3, 4, 4, 4, 5, 5, 5, 1])
    txt_inv_sin: str = ""
    txt_inv_con: str = ""
    txt_prim: str = ""
    txt_ver: str = ""
    txt_oto: str = ""
    dbg_grid: bool = False
    dbg_tiff: bool = False
    dbg_effrad: bool = False
    run: bool = True
    ou_sfc: str = ""
    ou_lc_grid: str = ""
    ou_imp_grid: str = ""
    ou_can_grid: str = ""
    avisos: list = field(default_factory=list)


class ErrorControl(Exception):
    pass


AP_FLAGS = ("AP", "LOWZ0", "LOWZO")
NONAP_FLAGS = ("NONAP", "HIGHZ0", "HIGHZO")


def _campos(linea):
    """Campos de una línea: como el original, en MAYÚSCULAS salvo lo entrecomillado."""
    out = []
    for p in shlex.split(linea, posix=False):
        out.append(p[1:-1] if (len(p) > 1 and p[0] == p[-1] == '"') else p.upper())
    return out


def _titulo(linea, kw):
    """TITLE1 = RUNST1(LOCE(2)+2:): el texto desde el 2.º carácter tras la palabra clave
    (se conserva el espacio inicial extra, como en el original)."""
    i = linea.upper().index(kw) + len(kw)
    return linea[i + 1:].rstrip()


def leer(path):
    c = Control()
    base = Path(path).resolve().parent
    tmp_ssn = [0] * 12
    via_actual = "CO"
    for linea in Path(path).read_text(encoding="latin-1").splitlines():
        s = linea.strip()
        if not s or s.startswith("**"):
            continue
        f = _campos(linea)
        # la vía (CO/OU) solo se escribe en la 1.ª línea del bloque: las demás la heredan
        if f[0] in ("CO", "OU"):
            via_actual = f[0]
        else:
            f = [via_actual] + f
        if len(f) < 2:
            continue
        via, kw = f[0], f[1]
        ifc = len(f)
        if via == "CO":
            if kw == "TITLEONE":
                c.titulo1 = _titulo(linea, "TITLEONE")
            elif kw == "TITLETWO":
                c.titulo2 = _titulo(linea, "TITLETWO")
            elif kw == "OPTIONS":
                for x in f[2:]:
                    if x in ("PRIMARY", "SECONDARY"):
                        c.estacion = x
                    elif x == "ZOEFF":
                        c.metodo_zo, c.zo_eff_flg = "ZOEFF", True
                    elif x == "ZORAD":
                        c.metodo_zo, c.zo_rad_flg = "ZORAD", True
            elif kw == "DEBUGOPT":
                for x in f[2:]:
                    c.dbg_grid |= x == "GRID"
                    c.dbg_tiff |= x == "TIFF"
                    c.dbg_effrad |= x == "EFFRAD"
            elif kw == "CENTERLL":
                c.coord_tipo = "LATLON"
                c.lat, c.lon = stodbl(f[2]), stodbl(f[3])
                c.datum = f[4] if ifc > 4 else "NAD83"
            elif kw == "CENTERXY":
                c.coord_tipo = "UTM"
                c.utm_e, c.utm_n = stodbl(f[2]), stodbl(f[3])
                c.utm_zona = nint(stodbl(f[4]))
                c.datum = f[5] if ifc > 5 else "NAD83"
            elif kw == "DATAFILE":
                tipo = f[2]
                fich = f[3] if Path(f[3]).is_absolute() else str((base / f[3]).resolve())
                anio = int(stodbl(tipo[4:]) or 0)
                if tipo.startswith("NLCD"):
                    c.lc_file, c.nlcd_year, c._lc_nombre = fich, anio, f[3]
                elif tipo.startswith("MPRV"):
                    c.imp_file, c.imp_year, c.got_imp, c._imp_nombre = fich, anio, True, f[3]
                elif tipo.startswith("CNPY"):
                    c.can_file, c.can_year, c.got_can, c._can_nombre = fich, anio, True, f[3]
            elif kw == "ANEM_HGT":
                c.anem_height = stodbl(f[2])
                if ifc > 3:
                    c.ibl_factor = stodbl(f[3])
            elif kw == "ZORADIUS":
                c.zo_rad = stodbl(f[2]) * 1000.0
            elif kw == "CLIMATE":
                snow_flg = False
                if ifc > 2:
                    c.humedad, c.humedad_txt = {
                        "AVERAGE": ("A", "Average"), "AVG": ("A", "Average"),
                        "WET": ("W", "Wet"), "DRY": ("D", "Dry")}[f[2]]
                if ifc > 3:
                    snow_flg = True
                    c.nieve = f[3] == "SNOW"
                    c.nieve_chr = "Y" if c.nieve else "N"
                if ifc > 4:
                    c.arido = f[4] == "ARID"
                    c.arido_chr = "Y" if c.arido else "N"
                if c.arido and c.nieve:
                    raise ErrorControl("CLIMATE: SNOW y ARID son incompatibles (error 255)")
                inv = 2 if (c.nieve and snow_flg) else 1
                c.meses_estacion[0] = c.meses_estacion[1] = c.meses_estacion[11] = inv
            elif kw == "FREQ_SECT":
                c.res_temporal, c.res_temporal_txt = {
                    "ANNUAL": ("A", "ANNUAL"), "SEASONAL": ("S", "SEASONAL"),
                    "MONTHLY": ("M", "MONTHLY")}[f[2]]
                c.num_sectores = nint(stodbl(f[3]))
                ap = f[4]
                if ap in AP_FLAGS:
                    c.airport, c.vary_ap, c.sect_ring = True, False, False
                elif ap in NONAP_FLAGS:
                    c.airport, c.vary_ap, c.sect_ring = False, False, False
                elif ap in ("VARYAP", "VARYZ0", "VARYZO"):
                    c.airport, c.vary_ap, c.sect_ring = False, True, False
                elif ap == "SECTRING":
                    c.airport, c.vary_ap, c.sect_ring = False, False, True
                else:
                    raise ErrorControl(f"FREQ_SECT: opción desconocida {ap} (error 105)")
                if not c.vary_ap and not c.sect_ring:
                    for i in range(c.num_sectores):
                        c.sec_ap[i][1] = c.airport
            elif kw == "SECTOR":
                _sector(c, f)
            elif kw == "SEASON":
                c.asigna_meses = True
                ssn = {"WINTERNS": 1, "WINTERWS": 2, "SPRING": 3, "SUMMER": 4,
                       "AUTUMN": 5}[f[2]]
                for x in f[3:]:
                    mo = nint(stodbl(x))
                    if 1 <= mo <= 12:
                        if tmp_ssn[mo - 1] == 0:
                            tmp_ssn[mo - 1] = ssn
                            c.meses_estacion[mo - 1] = ssn
                        else:
                            raise ErrorControl(f"SEASON: mes {mo} repetido (error 285)")
            elif kw == "RUNORNOT":
                c.run = f[2] == "RUN"
            elif kw == "FINISHED":
                _textos_meses(c)
                _postsect(c)
        elif via == "OU":
            if kw == "SFCCHAR":
                c.ou_sfc = f[2]
            elif kw == "NLCDGRID":
                c.ou_lc_grid = f[2]
            elif kw == "MPRVGRID":
                c.ou_imp_grid = f[2]
            elif kw == "CNPYGRID":
                c.ou_can_grid = f[2]
    if c.datum != "NAD83":
        raise ErrorControl("Solo se traduce el datum NAD83: NAD27/NADCON es exclusivo de EE. UU.")
    if c.coord_tipo == "UTM":
        c.lat, c.lon = utm_a_geo(c.utm_e, c.utm_n, c.utm_zona, 4)
    return c


def _sector(c, f):
    c.n_sector_kw += 1
    k = c.n_sector_kw - 1
    ifc = len(f)
    c.sec_id[k] = nint(stodbl(f[2]))
    if c.n_sector_kw == 1:
        if c.num_sectores in (1, 8, 12, 16):
            c.dflt_sec = bool(c.vary_ap and ifc == 4)
        else:
            c.dflt_sec = False
    if c.vary_ap and c.dflt_sec:
        c.sec_ap[k][1] = f[3] in AP_FLAGS
    if not c.dflt_sec:
        c.sec_start[k] = stodbl(f[3])
        c.sec_end[k] = stodbl(f[4])
    if c.vary_ap and not c.dflt_sec:
        c.sec_ap[k][1] = f[5] in AP_FLAGS
    elif c.sect_ring:
        if ifc < 6:
            raise ErrorControl("SECTOR: faltan las marcas H/L de los anillos (error 273)")
        if c.n_sector_kw > 1 and (ifc - 5) != c.n_sec_ring:
            raise ErrorControl("SECTOR: nº de anillos distinto del sector anterior (error 274)")
        c.n_sec_ring = ifc - 5
        if c.n_sec_ring > MAX_RINGS:
            raise ErrorControl("SECTOR: más de 25 anillos (error 276)")
        for i in range(5, ifc):
            if f[i] == "H":
                c.sec_ap[k][i - 4] = False
            elif f[i] == "L":
                c.sec_ap[k][i - 4] = True
            else:
                raise ErrorControl(f"SECTOR: marca de anillo no válida {f[i]} (error 105)")


def _postsect(c):
    """POSTSECT: sectores por defecto u ordenación y comprobación de los del usuario."""
    n = c.num_sectores
    if n in (1, 8, 12, 16) and not c.vary_ap and c.n_sector_kw == 0 and not c.sect_ring:
        c.dflt_sec = True
    if c.dflt_sec:
        ancho = 360.0 / float(n)
        ini = 0.0 if n in (1, 12) else 360.0 - ancho / 2.0
        for i in range(n):
            c.sec_id[i] = i + 1
            c.sec_start[i] = ini + ancho * float(i)
            c.sec_end[i] = c.sec_start[i] + ancho
            if c.sec_start[i] > 360.0:
                c.sec_start[i] -= 360.0
            if c.sec_end[i] > 360.0:
                c.sec_end[i] -= 360.0
        c.start_dir[:n] = c.sec_start[:n]
    else:
        if c.n_sector_kw != n:
            raise ErrorControl("Nº de palabras SECTOR distinto del de FREQ_SECT (error 208)")
        for i in range(n):                         # ordenar por id (inserción, como el original)
            for j in range(i, n):
                if c.sec_id[j] < c.sec_id[i]:
                    t = (c.sec_id[j], c.sec_start[j], c.sec_end[j], c.sec_ap[j])
                    for k in range(j, i, -1):
                        c.sec_id[k], c.sec_start[k] = c.sec_id[k - 1], c.sec_start[k - 1]
                        c.sec_end[k], c.sec_ap[k] = c.sec_end[k - 1], c.sec_ap[k - 1]
                    c.sec_id[i], c.sec_start[i], c.sec_end[i], c.sec_ap[i] = t
        suma = 0.0
        for i in range(n):
            if i > 0:
                if c.sec_id[i] - c.sec_id[i - 1] != 1:
                    raise ErrorControl("SECTOR: ids no consecutivos (error 266)")
                if abs(c.sec_start[i] - c.sec_end[i - 1]) > EPS:
                    raise ErrorControl("SECTOR: hueco o solape (error 267)")
            w = c.sec_end[i] - c.sec_start[i]
            if w < 0.0:
                w += 360.0
            if (2 <= n <= 12 and w < 30.0) or (n == 16 and w < 22.5):
                raise ErrorControl("SECTOR: sector demasiado estrecho (error 268/271)")
            suma += w
        if abs(suma - 360.0) > EPS:
            raise ErrorControl("SECTOR: no cubren 360° (error 269)")
        c.start_dir[:n] = c.sec_start[:n]
        if n > 1:
            c.start_dir[:n] = sorted(c.start_dir[:n])          # STRAIGHTSORT (ascendente)
        # reordenación de WndSectors para casar con StartDir (con su «cycle», tal cual)
        for i in range(n):
            for j in range(n):
                if abs(c.start_dir[i] - c.sec_start[j]) < EPS:
                    ti = (c.sec_start[i], c.sec_end[i], c.sec_ap[i])
                    c.sec_start[i], c.sec_end[i], c.sec_ap[i] = (c.sec_start[j],
                                                                c.sec_end[j], c.sec_ap[j])
                    c.sec_start[j], c.sec_end[j], c.sec_ap[j] = ti
    if c.sect_ring:
        if int(np.ceil(c.zo_rad / 200.0)) != c.n_sec_ring:
            raise ErrorControl("SECTRING: nº de anillos ≠ ZORADIUS/200 m (error 272)")
        if c.zo_rad % 200.0 != 0:
            c.avisos.append("ZORADIUS no es múltiplo de 200 m (aviso 278)")
        if c.zo_rad < 1000.0:
            c.avisos.append("ZORADIUS < 1 km con anillos (aviso 279)")


def _textos_meses(c):
    t = {1: "", 2: "", 3: "", 4: "", 5: ""}
    for i in range(1, 6):
        for j in range(1, 13):
            if c.meses_estacion[j - 1] == i and (c.nieve or i != 2):
                t[i] = t[i].rstrip() + f"{j:3d}"
    c.txt_inv_sin, c.txt_inv_con = t[1].strip(), t[2].strip()
    c.txt_prim, c.txt_ver, c.txt_oto = t[3].strip(), t[4].strip(), t[5].strip()
