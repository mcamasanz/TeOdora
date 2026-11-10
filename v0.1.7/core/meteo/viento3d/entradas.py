# -*- coding: utf-8 -*-
"""Lectores de las entradas de CALMET que usamos: GEO.DAT 2.0, 3D.DAT 2.1, CLOUD.DAT, SURF.DAT,
UPn.DAT, SEAn.DAT y PRECIP.DAT.

Fuentes de los formatos:
  - GEO.DAT: [V6] sec. 8.2, tablas 8-5 a 8-8 (lectura en formato libre, filas de norte a sur,
    opciones 0/1/2 para cada parámetro de superficie y tabla por defecto de 14 categorías).
  - 3D.DAT: [V6] sec. 8.9, tablas 8-22 y 8-23 (registros de cabecera y de datos con sus formatos).
    Se aceptan también las variantes que escribe digicompost (cabecera de proyección «UTM» y
    menos indicadores en el registro de opciones).
  - CLOUD.DAT: el fichero que escribe digicompost (`getCalpuff.write_cloud_dat`): por hora,
    «"CLOUDFRA" AAAAJJJHH» seguido de NX·NY fracciones de nubosidad (0-1), filas de sur a norte.
"""
import re

import numpy as np

# [V6] tabla 8-6 / [UG] tabla 4-45: categorías por defecto (14) y sus parámetros
# (z0 m, albedo, Bowen, parámetro de flujo de calor del suelo, flujo antropogénico W/m2, LAI)
TABLA_DEFECTO = {
    10: (1.0, 0.18, 1.5, 0.25, 0.0, 0.2),
    20: (0.25, 0.15, 1.0, 0.15, 0.0, 3.0),
    -20: (0.25, 0.15, 0.5, 0.15, 0.0, 3.0),
    30: (0.05, 0.25, 1.0, 0.15, 0.0, 0.5),
    40: (1.0, 0.10, 1.0, 0.15, 0.0, 7.0),
    51: (0.001, 0.10, 0.0, 1.0, 0.0, 0.0),
    54: (0.001, 0.01, 0.0, 1.0, 0.0, 0.0),
    55: (0.001, 0.10, 0.0, 1.0, 0.0, 0.0),
    60: (1.0, 0.10, 0.5, 0.25, 0.0, 2.0),
    61: (1.0, 0.1, 0.5, 0.25, 0.0, 2.0),
    62: (0.2, 0.1, 0.1, 0.25, 0.0, 1.0),
    70: (0.05, 0.30, 1.0, 0.15, 0.0, 0.05),
    80: (0.20, 0.30, 0.5, 0.15, 0.0, 0.0),
    90: (0.05, 0.70, 0.5, 0.15, 0.0, 0.0),
}
PARAMS = ("z0", "albedo", "bowen", "hcg", "qf", "lai")


class _Lineas:
    def __init__(self, texto):
        self.l = texto.replace("\r", "").split("\n")
        self.i = 0

    def sig(self):
        s = self.l[self.i]
        self.i += 1
        return s

    def numeros(self, n, tipo=float):
        """Lee n números en formato libre (separados por comas o blancos), en una o varias
        líneas; lo que sobra de la última línea se ignora (lectura de lista de Fortran)."""
        out = []
        while len(out) < n:
            for x in re.split(r"[,\s]+", self.sig().strip()):
                if x and len(out) < n:
                    out.append(x)
        return [tipo(float(x)) if tipo is int else tipo(x) for x in out]


def leer_geo(ruta):
    """GEO.DAT 2.0 -> dict con nx, ny, xorg, yorg (km), dgrid (km), pmap, zona, hem, datum,
    nlu, iwat1, iwat2, categorias, y campos (ny, nx) lu, elev (m) y los de PARAMS."""
    L = _Lineas(open(ruta, encoding="latin-1", newline="").read())
    cab = L.sig()
    if not cab.startswith("GEO.DAT"):
        raise ValueError("%s no es un GEO.DAT" % ruta)
    ncom = int(L.sig().split()[0])
    comentarios = [L.sig() for _ in range(ncom)]
    g = {"comentarios": [cab] + comentarios}
    g["pmap"] = L.sig().strip().upper()
    if g["pmap"] == "UTM":
        z = L.sig().strip()
        g["zona"], g["hem"] = int(z[:-1]), z[-1]
    elif g["pmap"] in ("LCC", "TTM", "LAZA", "PS", "EM"):
        # RLAT0, RLON0, XLAT1, XLAT2 (y FEAST, FNORTH en LCC, TTM y LAZA) [V6] tabla 8-8
        g["parametros"] = L.sig().split()
        if g["pmap"] in ("LCC", "TTM", "LAZA"):
            g["feast"], g["fnorth"] = (float(x) for x in L.sig().split()[:2])
    else:
        raise ValueError("GEO.DAT con proyección %s desconocida" % g["pmap"])
    d = L.sig().split()
    g["datum"], g["daten"] = d[0], (d[1] if len(d) > 1 else "")
    v = L.sig().split()
    g["nx"], g["ny"] = int(v[0]), int(v[1])
    g["xorg"], g["yorg"], g["dgrid"], g["dgridy"] = map(float, v[2:6])
    g["unidades"] = L.sig().strip()
    nx, ny = g["nx"], g["ny"]
    iopt1 = int(L.sig().split()[0])
    if iopt1 == 1:
        v = L.sig().split()
        g["nlu"], g["iwat1"], g["iwat2"] = int(v[0]), int(v[1]), int(v[2])
        g["categorias"] = L.numeros(g["nlu"], int)
    else:
        g["nlu"], g["iwat1"], g["iwat2"] = 14, 55, 55
        g["categorias"] = list(TABLA_DEFECTO)
    lu = np.zeros((ny, nx), int)
    for j in range(ny - 1, -1, -1):
        lu[j] = L.numeros(nx, int)
    g["lu"] = lu
    htfac = float(L.sig().split()[0])
    el = np.zeros((ny, nx))
    for j in range(ny - 1, -1, -1):
        el[j] = L.numeros(nx)
    g["elev"] = el * htfac
    for k, nombre in enumerate(PARAMS):
        op = int(L.sig().split()[0])
        if op == 2:
            a = np.zeros((ny, nx))
            for j in range(ny - 1, -1, -1):
                a[j] = L.numeros(nx)
        else:
            if op == 1:
                tabla = {}
                for _ in range(g["nlu"]):
                    c, val = L.numeros(2)
                    tabla[int(c)] = val
            else:
                tabla = {c: p[k] for c, p in TABLA_DEFECTO.items()}
            a = np.vectorize(lambda c: tabla[int(c)])(lu).astype(float)
        g[nombre] = a
    return g


def _f(s):
    s = s.strip()
    return float(s) if s else 0.0


def _i(s):
    s = s.strip()
    return int(float(s)) if s else 0


def leer_3d(ruta):
    """3D.DAT 2.1 -> dict con la cabecera y, por hora, los campos de superficie y de niveles.

    Devuelve:
      cab: dict (ioutw, ioutq, ioutc, iouti, ioutg, mapa, ibyr..ibhr, nhrs, nxp, nyp, nzp,
           sigma, lat, lon, elev, lu de cada celda (nyp, nxp))
      horas: lista de dicts {fecha: (año, mes, día, hora), sup: {campo: (nyp, nxp)},
             niv: {campo: (nzp, nyp, nxp)}} con niv pres (hPa), z (m snm), tk (K),
             wd (grados), ws (m/s) y, si vienen, w, rh, vapmr.
    """
    L = _Lineas(open(ruta, encoding="latin-1", newline="").read())
    l1 = L.sig()
    if not l1.startswith("3D.DAT"):
        raise ValueError("%s no es un 3D.DAT" % ruta)
    ncom = int(L.sig().split()[0])
    for _ in range(ncom):
        L.sig()
    fl = [int(x) for x in L.sig().split()]
    fl += [0] * (6 - len(fl))
    cab = dict(zip(("ioutw", "ioutq", "ioutc", "iouti", "ioutg", "iosrf"), fl))
    cab["mapa"] = L.sig()
    L.sig()                                              # opciones de física (informativo)
    s = L.sig()
    cab.update(ibyr=int(s[0:4]), ibmo=int(s[4:6]), ibdy=int(s[6:8]), ibhr=int(s[8:10]),
               nhrs=int(s[10:15]), nxp=int(s[15:19]), nyp=int(s[19:23]), nzp=int(s[23:27]))
    s = L.sig()
    cab.update(nx1=_i(s[0:4]), ny1=_i(s[4:8]), nx2=_i(s[8:12]), ny2=_i(s[12:16]),
               rxmin=_f(s[24:34]), rxmax=_f(s[34:44]), rymin=_f(s[44:53]), rymax=_f(s[53:62]))
    nxp, nyp, nzp = cab["nxp"], cab["nyp"], cab["nzp"]
    cab["sigma"] = [float(L.sig()) for _ in range(nzp)]
    lat = np.zeros((nyp, nxp))
    lon = np.zeros((nyp, nxp))
    elev = np.zeros((nyp, nxp))
    lu = np.zeros((nyp, nxp), int)
    for _ in range(nxp * nyp):
        s = L.sig()
        i, j = int(s[0:4]) - 1, int(s[4:8]) - 1
        lat[j, i], lon[j, i], elev[j, i], lu[j, i] = _f(s[8:17]), _f(s[17:27]), _i(s[27:32]), _i(s[32:35])
    cab.update(lat=lat, lon=lon, elev=elev, lu=lu)
    nombres_sup = ("pres", "rain", "sc", "radsw", "radlw", "t2", "q2", "wd10", "ws10", "sst")
    horas = []
    actual = None
    while L.i < len(L.l):
        s = L.sig()
        if not s.strip():
            continue
        fecha = (int(s[0:4]), int(s[4:6]), int(s[6:8]), int(s[8:10]))
        if actual is None or actual["fecha"] != fecha:
            actual = {"fecha": fecha,
                      "sup": {n: np.zeros((nyp, nxp)) for n in nombres_sup},
                      "niv": {n: np.zeros((nzp, nyp, nxp)) for n in ("pres", "z", "tk", "wd", "ws")}}
            if cab["ioutw"]:
                actual["niv"]["w"] = np.zeros((nzp, nyp, nxp))
            if cab["ioutq"]:
                actual["niv"]["rh"] = np.zeros((nzp, nyp, nxp))
                actual["niv"]["vapmr"] = np.zeros((nzp, nyp, nxp))
            horas.append(actual)
        i, j = int(s[10:13]) - 1, int(s[13:16]) - 1
        cortes = ((16, 23), (23, 28), (28, 30), (30, 38), (38, 46), (46, 54), (54, 62), (62, 70),
                  (70, 78), (78, 86))
        for n, (a, b) in zip(nombres_sup, cortes):
            actual["sup"][n][j, i] = _f(s[a:b])
        for k in range(nzp):
            t = L.sig()
            niv = actual["niv"]
            niv["pres"][k, j, i] = _f(t[0:4])
            niv["z"][k, j, i] = _f(t[4:10])
            niv["tk"][k, j, i] = _f(t[10:16])
            niv["wd"][k, j, i] = _f(t[16:20])
            niv["ws"][k, j, i] = _f(t[20:25])
            p = 25
            if cab["ioutw"]:
                niv["w"][k, j, i] = _f(t[p:p + 6])
                p += 6
            if cab["ioutq"]:
                niv["rh"][k, j, i] = _f(t[p:p + 3])
                niv["vapmr"][k, j, i] = _f(t[p + 3:p + 8])
    return {"cab": cab, "horas": horas}


AUSENTE = 9999.0           # indicador de dato ausente de SURF.DAT ([UG] tabla 4-51)
CAMPOS_SURF = ("ws", "wd", "iceil", "icc", "tk", "irh", "pres", "ipcode")


def leer_surf(ruta):
    """SURF.DAT formateado (IFORMS=2) -> {ids, ibtz, horas: {(año, día juliano, hora): (nsta, 8)}}.

    Formato: cabecera de [V6] sec. 8.4 (DATASET, NCOM, comentarios, proyección «NONE») con la
    versión 2.0, que es la que lee calmet.exe 5.8.5 (la 2.1 con zona «UTC+hhmm» y segundos la
    rechaza) [caja negra]; después, como en [UG] tabla 4-51, en lectura libre: «IBYR IBJUL IBHR
    IEYR IEJUL IEHR IBTZ NSTA», los NSTA identificadores y, por hora, «IYR IJUL IHR» y por estación
    WS, WD, ICEIL, ICC, TEMPK, IRH, PRES, IPCODE (9999 = ausente). La hora del registro es la de la
    hora de CALMET con la misma etiqueta [caja negra: dirección distinta en cada hora]."""
    tok = []
    lineas = open(ruta, encoding="latin-1", newline="").read().replace("\r", "").split("\n")
    if not lineas[0].startswith("SURF.DAT"):
        raise ValueError("%s no es un SURF.DAT" % ruta)
    ncom = int(lineas[1].split()[0])
    for s in lineas[3 + ncom:]:                         # tras la línea de proyección
        tok += re.split(r"[,\s]+", s.strip()) if s.strip() else []
    p = 0
    cab = [int(float(x)) for x in tok[p:p + 8]]
    p += 8
    nsta = cab[7]
    ids = [int(float(x)) for x in tok[p:p + nsta]]
    p += nsta
    horas = {}
    while p + 3 <= len(tok):
        a, j, h = (int(float(x)) for x in tok[p:p + 3])
        p += 3
        horas[(a, j, h)] = np.array([float(x) for x in tok[p:p + 8 * nsta]]).reshape(nsta, 8)
        p += 8 * nsta
    return {"ids": ids, "ibtz": cab[6], "horas": horas}


def leer_up(ruta):
    """UP.DAT (un sondeo por estación) -> lista de (datetime, niveles (n, 5): p hPa, z m snm, T K,
    dirección, velocidad m/s), con los ausentes como NaN.

    Formato ([UG] tablas 4-48 y 4-49; [V6] sec. 8.3, tablas 8-9 y 8-10): cabecera de versión 2.0
    (DATASET, NCOM, comentarios, «NONE», fechas y PSTOP, opciones de READ62) y, por sondeo, un
    registro «ITPDK, STNID, AAAAMMDDHH, MLEV, ISTOP» (año de 4 cifras en las columnas 21-24, como
    lo lee calmet.exe 5.8.5 [caja negra]) seguido de ISTOP niveles «p/z/T/dir/vel» (o separados
    por comas). Ausentes: z = 9999, T = 999,9, dirección y velocidad = 999."""
    import datetime as dt
    lineas = open(ruta, encoding="latin-1", newline="").read().replace("\r", "").split("\n")
    if not lineas[0].startswith("UP.DAT"):
        raise ValueError("%s no es un UP.DAT" % ruta)
    ncom = int(lineas[1].split()[0])
    i = 2 + ncom + 3                                        # proyección, fechas, opciones
    out = []
    while i < len(lineas):
        s = lineas[i]
        i += 1
        if not s.strip():
            continue
        t = dt.datetime(int(s[20:24]), int(s[24:26]), int(s[26:28]), int(s[28:30]))
        n = int(s[68:70]) if len(s.rstrip()) >= 69 else int(s[35:37])
        vals = []
        while len(vals) < 5 * n:
            vals += [x for x in re.split(r"[/,\s]+", lineas[i].strip()) if x]
            i += 1
        a = np.array([float(x) for x in vals[:5 * n]]).reshape(n, 5)
        a[:, 1] = np.where(a[:, 1] >= 9998.0, np.nan, a[:, 1])
        a[:, 2] = np.where(a[:, 2] >= 999.0, np.nan, a[:, 2])
        a[:, 3:] = np.where(a[:, 3:] >= 998.5, np.nan, a[:, 3:])
        out.append((t, a))
    return out


def leer_sea(ruta):
    """SEAn.DAT (una estación sobre el agua por fichero) -> {id, nombre, registros}.

    Formato ([V6] sec. 8.5, tablas 8-13 y 8-14; [UG] tabla 4-53): cabecera de versión 2.0
    (DATASET, NCOM, comentarios, proyección, zona UTM, datum, unidades e «IDOWSTA 'CHOWSTA'») y,
    en lectura libre, registros de 18 valores: x, y (km), longitud, altura de medida ZOWSTA (m),
    año, día juliano y hora de inicio y de fin del periodo, ΔT aire-mar (K), T del aire (K), HR
    (%), altura de mezcla (m), gradientes térmicos bajo y sobre ella (K/m), velocidad (m/s) y
    dirección del viento (9999 = ausente, devuelto como NaN). registros: lista de
    (t_ini, t_fin, valores (16,)) con t datetime y valores = x, y en m, lon, z, dT, Ta, rh, zi,
    tgb, tga, ws, wd."""
    import datetime as dt
    lineas = open(ruta, encoding="latin-1", newline="").read().replace("\r", "").split("\n")
    if not lineas[0].startswith("SEA.DAT"):
        raise ValueError("%s no es un SEA.DAT" % ruta)
    ncom = int(lineas[1].split()[0])
    i = 2 + ncom
    pmap = lineas[i].strip().upper()
    i += 1
    if pmap == "UTM":
        i += 1                                              # zona UTM
    elif pmap not in ("NONE", "LL"):
        i += 2 if pmap in ("LCC", "TTM", "LAZA") else 1      # parámetros de la proyección
    i += 2                                                  # datum y unidades
    m = re.match(r"\s*(\d+)\s*'?([^']*)'?", lineas[i])
    ident, nombre = int(m.group(1)), m.group(2).strip()
    tok = []
    for s in lineas[i + 1:]:
        tok += [x for x in re.split(r"[,\s]+", s.strip()) if x]
    regs = []
    for q in range(0, len(tok) - 17, 18):
        v = [float(x) for x in tok[q:q + 18]]
        t1 = dt.datetime(int(v[4]), 1, 1, int(v[6])) + dt.timedelta(days=int(v[5]) - 1)
        t2 = dt.datetime(int(v[7]), 1, 1, int(v[9])) + dt.timedelta(days=int(v[8]) - 1)
        a = np.array([v[0] * 1000.0, v[1] * 1000.0, v[2], v[3]] + v[10:18])
        a[4:] = np.where(a[4:] >= AUSENTE * 0.999, np.nan, a[4:])
        regs.append((t1, t2, a))
    return {"id": ident, "nombre": nombre, "registros": regs}


def leer_precip(ruta):
    """PRECIP.DAT formateado (IFORMP=2) -> {ids, ibtz, horas: {(año, día juliano, hora): (nsta,)}}.

    Como el SURF.DAT 2.0 ([UG] tablas 4-54 y 4-55; [V6] tabla 8-16 sin segundos): cabecera de
    versión, proyección «NONE», «IBYR IBJUL IBHR IEYR IEJUL IEHR IBTZ NSTA» en lectura libre,
    los identificadores y, por hora, «IYR IJUL IHR» con la lluvia (mm/h) de cada estación
    (9999 = ausente, devuelto como NaN)."""
    tok = []
    lineas = open(ruta, encoding="latin-1", newline="").read().replace("\r", "").split("\n")
    if not lineas[0].startswith("PRECIP.DAT"):
        raise ValueError("%s no es un PRECIP.DAT" % ruta)
    ncom = int(lineas[1].split()[0])
    for s in lineas[3 + ncom:]:
        tok += re.split(r"[,\s]+", s.strip()) if s.strip() else []
    cab = [int(float(x)) for x in tok[:8]]
    nsta = cab[7]
    ids = [int(float(x)) for x in tok[8:8 + nsta]]
    p = 8 + nsta
    horas = {}
    while p + 3 <= len(tok):
        a, j, h = (int(float(x)) for x in tok[p:p + 3])
        p += 3
        v = np.array([float(x) for x in tok[p:p + nsta]])
        horas[(a, j, h)] = np.where(v >= AUSENTE * 0.999, np.nan, v)
        p += nsta
    return {"ids": ids, "ibtz": cab[6], "horas": horas}


def leer_nubes(ruta, nx, ny):
    """CLOUD.DAT (formato libre) -> {AAAAJJJHH: (ny, nx) fracción de cielo cubierto}."""
    tok = open(ruta, encoding="latin-1", newline="").read().split()
    out = {}
    k = 0
    while k < len(tok):
        if not tok[k].strip('"').upper().startswith("CLOUDFRA"):
            raise ValueError("CLOUD.DAT: esperaba la etiqueta CLOUDFRA")
        nd = int(tok[k + 1])
        vals = np.array([float(x) for x in tok[k + 2:k + 2 + nx * ny]])
        out[nd] = vals.reshape(ny, nx)
        k += 2 + nx * ny
    return out
