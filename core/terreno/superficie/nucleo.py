# -*- coding: utf-8 -*-
"""Núcleo de AERSURFACE v26135 traducido y vectorizado (mod_GetData.f: GetLCCounts,
GetGridVars, ProcessLC; mod_AvgParams.f: AvgSfcCharsSimple, AvgSfcCharsGeom,
EffectiveRoughness4, z0_eff_func; mod_LandCoverParams.f: ConsolSfcVals).

OPTIMIZACIÓN: el original recorre ~113.000 píxeles uno a uno llamando a ProcessLC; aquí
se calculan todos a la vez con numpy. Para que el resultado sea el MISMO:
  · las sumas por sector/mes se hacen con np.bincount, que acumula en el mismo orden
    secuencial (fila a fila) que el bucle Fortran;
  · se respetan los literales de precisión simple (0.10, 0.90, 1.0e-3);
  · NINT/IDNINT con empates lejos del cero;
  · la renormalización de arbolado+impermeable se repite mes a mes como en el original
    (modifica las variables dentro del bucle de meses);
  · peculiaridad ZOEFF: el original cambia la variable global ZoRad a 5050 m dentro del
    bucle en cuanto procesa el primer píxel válido; se replica.
"""
import math
from dataclasses import dataclass, field

import numpy as np

from . import tablas as T
from .albers import Albers, RAD2DEG
from .formato import F32_0_10, F32_0_90, F32_1E_3, nint

F32_1E_4 = float(np.float32(0.0001))
from .geotiff import leer_tags, leer_ventana

STUDY_DOM_M = 5050.0
STUDY_RADIUS_M = 5050.0
MIN_D_FACTOR = 0.5
MISS = 0
NUM_SEAS = 4
IBL_MIN, IBL_MAX = 30.0, 600.0
CANIMP_SUM_THR = 1.5


class ErrorAersurface(Exception):
    pass


@dataclass
class Rejilla:
    vars: object
    datos: np.ndarray            # [filas, cols] int64
    fila0: int                   # GridFrstRow (1-based, del fichero)
    col0: int
    fila_c: int
    col_c: int
    cx: float                    # CntrAlbersX
    cy: float
    giro: float                  # GridToTruDif (grados)
    ll_x: float                  # DomAlbersLLX
    ll_y: float
    lat: float
    lon: float


@dataclass
class Resultado:
    alb: np.ndarray              # [12] (o 4 / 1)
    bowen: np.ndarray
    zo: np.ndarray               # [nsec, 12]
    zo_fetch: np.ndarray = None
    cuentas_br: np.ndarray = None
    cuentas_z0: np.ndarray = None
    rejillas: dict = field(default_factory=dict)
    avisos: list = field(default_factory=list)


# ── tablas consolidadas (ConsolSfcVals) ───────────────────────────────────────────────
def _tabla(d):
    a = np.zeros((100, 5))
    for k, v in d.items():
        a[k] = v
    return a


def tablas_consolidadas(airport, humedad, arido):
    bow = _tabla({"A": T.BowenAvg, "W": T.BowenWet, "D": T.BowenDry}[humedad])
    alb = _tabla(T.Albedo)
    z0 = _tabla(T.Z0)
    src = T.Z0_Airp if airport else T.Z0_NAirp
    for k in (21, 22, 23, 24, 81, 82):
        z0[k] = src[k]
    suf = "_Ar" if arido else "_NAr"
    bsrc = getattr(T, {"A": "BowenAvg", "W": "BowenWet", "D": "BowenDry"}[humedad] + suf)
    for k in (31, 51, 52):
        z0[k] = getattr(T, "Z0" + suf)[k]
        alb[k] = getattr(T, "Albedo" + suf)[k]
        bow[k] = bsrc[k]
    return alb, bow, z0


# ── rejilla de un fichero (GetGridVars) ───────────────────────────────────────────────
def rejilla(v, alb_proj, lat, lon, inicial, es_uso, extra=()):
    dom = nint(STUDY_DOM_M / v.cell_res)
    cx, cy = alb_proj.a_albers(lat, lon)
    col_c = nint((cx - float(v.ul_x)) / v.cell_res) + 1
    fila_c = nint((float(v.ul_y) - cy) / v.cell_res) + 1
    f0, f1, c0, c1 = fila_c - dom, fila_c + dom, col_c - dom, col_c + dom
    ll_x = float(v.ul_x) + (c0 - 1) * v.cell_res - v.cell_res / 2.0
    ll_y = float(v.ul_y) - (f1 - 1) * v.cell_res - v.cell_res / 2.0
    elat, elon = alb_proj.a_latlon(cx, cy + STUDY_RADIUS_M)
    ex, ey = alb_proj.a_albers(elat, lon)
    giro = math.atan2(ex - cx, ey - cy) * RAD2DEG
    if (col_c - dom < 0 or col_c + dom > v.cols or fila_c - dom < 0
            or fila_c + dom > v.rows):
        raise ErrorAersurface(f"El área de estudio se sale del fichero {v.path} (error 600)")
    datos, leido = leer_ventana(v, f0, f1 - f0 + 1, c0, c1 - c0 + 1, inicial, es_uso)
    if es_uso:
        validos = np.isin(datos, list(T.LCCATSALL01) + list(extra))
        if np.any(leido & ~validos):
            raise ErrorAersurface(
                f"{v.path}: códigos de uso del suelo no válidos para NLCD 2001+ "
                "(el original aborta: error 8025)")
    if v.tipo == "tile":
        datos = np.where(leido & (datos < 0), 0, datos)
    return Rejilla(v, datos, f0, c0, fila_c, col_c, cx, cy, giro, ll_x, ll_y, lat, lon)


# ── rugosidad efectiva (EffectiveRoughness4 + z0_eff_func), 1-based como el original ──
def _z0_eff_func(z0_init, xrad, href):
    vonk, iterlimit, err, it = 0.4, 10, 10.0, 1
    z0_old = z0_init
    z0_new = z0_old
    while err >= F32_1E_3 and it < iterlimit:
        z0_new = (href * math.log(href / z0_old) - vonk * xrad) / (href / z0_old - 1.0)
        err = abs((z0_new - z0_old) / z0_old)
        z0_old = z0_new
        it += 1
    return z0_new


def effective_roughness4(z0p, href, delx, xdnum):
    """z0p: lista 1-based (z0p[0] sin uso). Devuelve (z0_eff, fetch)."""
    k, iterlimit = 0.4, 10
    err = 10.0
    href_tmp = href
    z0 = z0p
    xd = [0.0] * (xdnum + 2)
    xd[1] = delx
    for i in range(2, xdnum + 1):
        xd[i] = xd[i - 1] + delx
    hb = [0.0] * (xdnum + 2)
    hb_r = [0.0] * (xdnum + 2)
    z0_r = [0.0] * (xdnum + 2)
    endofdom = False
    i = 1
    z0_avg = math.sqrt(z0[i] * z0[i + 1])
    hb[1] = z0[1]
    for j in range(2, xdnum + 1):
        hb[j] = 2.0 * max(z0[1:j + 1])
    hb_new = None
    while hb[i] <= href_tmp and not endofdom:
        aa = hb[i] * (math.log(hb[i] / z0_avg) - 1.0) + k * delx
        it = 1
        hb_old = hb[i + 1]
        while err > F32_1E_3 and it < iterlimit:
            hb_new = (hb_old + aa) / math.log(hb_old / z0_avg)
            err = abs((hb_new - hb_old) / hb_old)
            hb_old = hb_new
            it += 1
        i += 1
        if i == xdnum - 1:
            endofdom = True
            href_tmp = hb_new
            break
        hb[i] = hb_new
        z0_avg = math.sqrt(z0[i] * z0[i + 1])
        err = 10.0
    if endofdom:
        xrad = xd[i + 1]
    else:
        slope = (xd[i] - xd[i - 1]) / (hb[i] - hb[i - 1])
        xrad = xd[i - 1] + slope * (href_tmp - hb[i - 1])
    z0_out = _z0_eff_func(min(z0[1:i + 1]), xrad, href_tmp)
    startndx = i
    ornghb0 = irnghb0 = 0.0
    gotirng = gotorng = gotfnl = False
    irngndx = orngndx = 0
    while not gotfnl:
        if startndx + 1 > xdnum:
            raise ErrorAersurface("EffectiveRoughness4: fuera de la rejilla de anillos "
                                  "(comportamiento indefinido en el original)")
        for ii in range(1, startndx + 2):
            z0_r[ii] = z0[startndx - ii + 2]
        if endofdom:
            gotfnl = True
            xrad = xd[startndx + 1]
            break
        hb_r[1] = z0_r[1]
        mx = 2.0 * max(z0_r[1:startndx + 2])
        for ii in range(2, startndx + 2):
            hb_r[ii] = mx
        for ii in range(1, startndx + 1):
            z0_avg = math.sqrt(z0_r[ii] * z0_r[ii + 1])
            aa = hb_r[ii] * (math.log(hb_r[ii] / z0_avg) - 1.0) + k * delx
            it, err = 1, 10.0
            hb_old = hb_r[ii + 1]
            while err > F32_1E_3 and it < iterlimit:
                hb_new = (hb_old + aa) / math.log(hb_old / z0_avg)
                err = abs((hb_new - hb_old) / hb_old)
                hb_old = hb_new
                it += 1
            if ii <= startndx:
                hb_r[ii + 1] = hb_new
        hb0 = hb_r[startndx + 1]
        if abs(hb0 - href_tmp) < 0.01:
            gotfnl = True
            xrad = xd[startndx + 1]
        elif hb0 < href_tmp:
            gotirng, irngndx, irnghb0 = True, startndx, hb0
            if gotirng and gotorng:
                xrad = xd[irngndx] + ((href_tmp - irnghb0) / (ornghb0 - irnghb0)) * delx
                gotfnl = True
            else:
                startndx += 1
        elif hb0 > href_tmp:
            gotorng, orngndx, ornghb0 = True, startndx, hb0
            if gotirng and gotorng:
                xrad = xd[orngndx] + ((href_tmp - irnghb0) / (ornghb0 - irnghb0)) * delx
                gotfnl = True
            else:
                startndx -= 1
    z0_in = _z0_eff_func(min(z0_r[1:startndx + 2]), xrad, href_tmp)
    z0_eff = math.sqrt(z0_in * z0_out)
    fetch = (href_tmp * math.log(href_tmp / z0_eff) - href_tmp + z0_eff) / k
    return z0_eff, fetch


# ── proceso principal ────────────────────────────────────────────────────────────────
def ejecutar(c):
    lcv = leer_tags(c.lc_file)
    impv = leer_tags(c.imp_file) if c.got_imp else None
    canv = leer_tags(c.can_file) if c.got_can else None
    nad83 = ("NAD83", "WGS72", "WGS84")

    def compatible(o):
        dat = o.hdatum == lcv.hdatum or (o.hdatum in nad83 and lcv.hdatum in nad83)
        if not dat:
            raise ErrorAersurface("Datum distinto entre uso del suelo y suplemento (810/815)")
        res = ((abs(lcv.pxl_x - o.pxl_x) < 1e-5 and abs(lcv.pxl_y - o.pxl_y) < 1e-5)
               or abs(lcv.pxl_x - o.pxl_x) <= 0.03)
        return res
    use_imp = bool(impv and compatible(impv))
    use_can = bool(canv and compatible(canv))
    if lcv.hdatum == "NAD27":
        raise ErrorAersurface("Ficheros NAD27: conversión NADCON fuera de alcance")
    # parámetros de Albers y elipsoide: los del ÚLTIMO fichero leído (globales en el original)
    ult = canv or impv or lcv
    proj = Albers(ult.std1, ult.std2, ult.origen_lat, ult.meridiano, ult.hdatum
                  if ult.hdatum in ("NAD27", "NAD83", "WGS84") else "NAD83")

    zo_rad = c.zo_rad
    if c.metodo_zo == "ZOEFF":
        zo_rad = min(c.anem_height * c.ibl_factor * 15.0, 5000.0)

    # EXTENSIÓN PROPIA (no está en el original; solo actúa si se pide): «clases de usuario»
    # {código: (clase NLCD base, (z0 de las estaciones 1..5))}. Se tratan como su clase base en
    # albedo, Bowen y cuentas, pero con su propia z0 por estación (p. ej. cultivos leñosos con
    # la rugosidad de Davenport-Wieringa). Sin ella el cálculo es el validado.
    usuario = dict(getattr(c, "clases_usuario", None) or {})
    g_lc = rejilla(lcv, proj, c.lat, c.lon, 0, True, extra=tuple(usuario))
    shape = g_lc.datos.shape
    g_imp = rejilla(impv, proj, c.lat, c.lon, 127, False) if use_imp else None
    g_can = rejilla(canv, proj, c.lat, c.lon, 127, False) if use_can else None
    LC = g_lc.datos.ravel()
    z0_usuario = []
    if usuario:
        LC = LC.copy()
        for cod, (base, z0s) in usuario.items():
            m_u = LC == cod
            if m_u.any():
                z0_usuario.append((m_u, tuple(float(z) for z in z0s)))
                LC[m_u] = base
    IMP = g_imp.datos[:shape[0], :shape[1]].ravel() if use_imp else np.zeros(LC.size, np.int64)
    CAN = g_can.datos[:shape[0], :shape[1]].ravel() if use_can else np.zeros(LC.size, np.int64)

    # coordenadas de cada celda en el orden del bucle (fila exterior, columna interior)
    jr, ic = np.meshgrid(np.arange(shape[0]), np.arange(shape[1]), indexing="ij")
    tmprow = (g_lc.fila0 + jr).ravel()
    tmpcol = (g_lc.col0 + ic).ravel()
    cell_x = float(lcv.ul_x) + (tmpcol - 1).astype(np.float64) * lcv.cell_res
    cell_y = float(lcv.ul_y) - (tmprow - 1).astype(np.float64) * lcv.cell_res
    dist = np.sqrt(np.abs(g_lc.cx - cell_x) ** 2 + (np.abs(g_lc.cy - cell_y) ** 2))
    min_d = lcv.pxl_x * MIN_D_FACTOR
    n = c.num_sectores
    sd = c.start_dir[:n]

    # sector de cada celda (bucle SectorLoop: el primero que encaje)
    if n == 1:
        sector = np.ones(LC.size, np.int64)
    else:
        ang = np.arctan2(cell_y - g_lc.cy, cell_x - g_lc.cx) * RAD2DEG + g_lc.giro
        ang = np.where(ang < 0.0, ang + 360.0, ang)
        flow = 90.0 - ang
        flow = np.where(flow < 0.0, flow + 360.0, flow)
        sector = np.zeros(LC.size, np.int64)
        for k in range(n):
            a0 = sd[k]
            a1 = sd[0] if k == n - 1 else sd[k + 1]
            if a0 > a1:
                m = (flow >= a0) & (flow <= 360.0) | (flow >= 0.0) & (flow < a1)
            else:
                m = (flow >= a0) & (flow < a1)
            sector = np.where((sector == 0) & m, k + 1, sector)
        if np.any(sector == 0):
            raise ErrorAersurface("Celda sin sector (índice 0: indefinido en el original)")

    # tablas: albedo y Bowen no dependen del aeropuerto; z0 sí (por sector si VARYAP)
    alb_t, bow_t, z0_ap = tablas_consolidadas(True, c.humedad, c.arido)
    _, _, z0_nap = tablas_consolidadas(False, c.humedad, c.arido)
    ap_tab = np.array([c.sec_ap[k] for k in range(n)], bool)     # [sector, anillo 0..25]
    if c.sect_ring:
        if c.metodo_zo != "ZORAD":
            raise ErrorAersurface("SECTRING con ZOEFF: índices de anillo fuera de rango en el "
                                  "original (comportamiento indefinido)")
        ring = np.where(dist <= zo_rad, np.ceil(dist / 200.0), c.n_sec_ring).astype(np.int64)
        if np.any(ring < 1):
            raise ErrorAersurface("Celda en el anillo 0 (índice indefinido en el original)")
    else:
        ring = np.ones(LC.size, np.int64)
    ap_sec_cel = ap_tab[sector - 1, ring]    # el bloque 21-24 usa SIEMPRE el flag sector/anillo
    if c.vary_ap or c.sect_ring:
        ap_cel = ap_sec_cel                  # ConsolSfcVals por celda
    else:
        ap_cel = np.full(LC.size, c.airport)

    # cuentas
    nlc = 100
    cnt_br = np.bincount(LC, minlength=nlc)
    lc_count_br = int(np.count_nonzero(LC != MISS))
    validos = LC != MISS
    # radio de las cuentas de rugosidad (peculiaridad ZOEFF: ZoRad cambia en el 1.er válido)
    if c.metodo_zo == "ZOEFF":
        idx_val = np.flatnonzero(validos)
        primero = idx_val[0] if idx_val.size else LC.size
        rad_cnt = np.where(np.arange(LC.size) > primero, STUDY_RADIUS_M, zo_rad)
        zo_rad_mes = STUDY_RADIUS_M
    else:
        rad_cnt = np.full(LC.size, zo_rad)
        zo_rad_mes = zo_rad
    en_r = dist <= rad_cnt
    cnt_z0 = np.zeros((n, nlc), np.int64)
    for s in range(1, n + 1):
        cnt_z0[s - 1] = np.bincount(LC[en_r & (sector == s)], minlength=nlc)
    imp_r = IMP.astype(np.float64) / 100.0
    can_r = CAN.astype(np.float64) / 100.0
    vld = ~((IMP < 0) | (IMP > 100) | (CAN < 0) | (CAN > 100))
    avisos = []
    if use_imp and use_can:
        n_zo = int(np.count_nonzero(en_r))
        n_mal = int(np.count_nonzero(en_r & vld & (can_r + imp_r > CANIMP_SUM_THR)))
        if n_zo and n_mal / n_zo > 0.01:
            avisos.append(f"Arbolado+impermeable > 150 % en el {100 * n_mal / n_zo:.1f} % "
                          "de las celdas del radio de rugosidad")

    # bucle de meses (vectorizado sobre las celdas)
    bowen_sum = np.zeros(12)
    zo_sum = np.zeros((n, 12))
    inv_sum = np.zeros((n, 12))
    ring_w = lcv.pxl_x
    n_rings = math.ceil(STUDY_RADIUS_M / ring_w)
    zo_sum_eff = np.zeros((n, 12, n_rings + 2))
    inv_sum_eff = np.zeros((n, 12, n_rings + 2))
    en_mes = validos & (dist <= zo_rad_mes)
    rama = en_mes & (use_imp or use_can) & vld
    peso = np.where(dist < min_d, 1.0 / min_d, 1.0 / np.where(dist == 0, 1.0, dist))
    dist_idx = (np.floor(dist / ring_w + 0.5)).astype(np.int64) + 1
    lc_v = LC
    for m in range(12):
        s = c.meses_estacion[m] - 1
        # Bowen: suma de logaritmos en el orden de las celdas
        lb = np.log(bow_t[lc_v[validos], s])
        bowen_sum[m] = np.bincount(np.zeros(lb.size, np.int64), weights=lb, minlength=1)[0]
        # renormalización arbolado+impermeable (persistente entre meses, como el original)
        sobra = rama & (can_r + imp_r > 1.00)
        if np.any(sobra):
            tot = np.where(sobra, can_r + imp_r, 1.0)
            can_r = np.where(sobra, can_r / tot, can_r)
            imp_r = np.where(sobra, imp_r / tot, imp_r)
        z0_cel = np.where(ap_cel, z0_ap[lc_v, s], z0_nap[lc_v, s])
        zot = z0_cel.copy()
        dev = rama & (lc_v >= 21) & (lc_v <= 24)
        if np.any(dev):
            l43, l22 = math.log(T.Z092_43[s]), math.log(T.Z092_22[s])
            l31, l85 = math.log(T.Z092_31[s]), math.log(T.Z092_85[s])
            a_ap = np.exp((l43 * can_r) + (F32_0_10 * l22 * imp_r) + (F32_0_90 * l31 * imp_r)
                          + (l85 * (1.0 - can_r - imp_r)))
            a_nap = np.exp((l43 * can_r) + (F32_0_90 * l22 * imp_r) + (F32_0_10 * l31 * imp_r)
                           + (l85 * (1.0 - can_r - imp_r)))
            zot = np.where(dev, np.where(ap_sec_cel, a_ap, a_nap), zot)
        hum = rama & (lc_v >= 90) & (lc_v <= 94) & (can_r < 0.25)
        if np.any(hum):
            l31, l85 = math.log(T.Z092_31[s]), math.log(T.Z092_85[s])
            with np.errstate(divide="ignore"):
                lz = np.log(z0_cel)
            w = np.exp((lz * can_r) + (l31 * imp_r) + (l85 * (1.0 - can_r - imp_r)))
            zot = np.where(hum, w, zot)
        for m_u, z0s in z0_usuario:
            zot = np.where(m_u, z0s[s], zot)
        sel = en_mes
        with np.errstate(divide="ignore"):
            lz = np.log(zot[sel])
        if c.metodo_zo == "ZORAD":
            sec = sector[sel] - 1
            inv_sum[:, m] = np.bincount(sec, weights=peso[sel], minlength=n)[:n]
            zo_sum[:, m] = np.bincount(sec, weights=peso[sel] * lz, minlength=n)[:n]
        else:
            grp = (sector[sel] - 1) * (n_rings + 2) + dist_idx[sel]
            tot = n * (n_rings + 2)
            inv_sum_eff[:, m, :] = np.bincount(grp, weights=peso[sel], minlength=tot)[:tot] \
                .reshape(n, n_rings + 2)
            zo_sum_eff[:, m, :] = np.bincount(grp, weights=peso[sel] * lz, minlength=tot)[:tot] \
                .reshape(n, n_rings + 2)

    # ── AvgSfcCharsSimple (albedo) ──
    tr = c.res_temporal
    alb_sum = np.zeros(12)
    avg_alb = np.zeros(12)
    if tr in ("A", "M"):
        for j in range(nlc):
            for k in range(12):
                if j != MISS:
                    alb_sum[k] = alb_sum[k] + (float(cnt_br[j]) * alb_t[j, c.meses_estacion[k] - 1])
        avg_alb[:] = alb_sum / float(lc_count_br)
        if tr == "A":
            s = 0.0
            for j in range(12):
                s = s + avg_alb[j]
            avg_alb[0] = s / 12.0
    else:
        for j in range(nlc):
            for k in range(1, NUM_SEAS + 1):
                if j != MISS:
                    col = 0 if (k == 1 and not c.nieve) else k
                    alb_sum[k - 1] = alb_sum[k - 1] + float(cnt_br[j]) * alb_t[j, col]
        avg_alb[:NUM_SEAS] = alb_sum[:NUM_SEAS] / float(lc_count_br)

    # ── AvgSfcCharsGeom (Bowen y z0) ──
    avg_zo = np.zeros((n, 12))
    avg_bow = np.zeros(12)
    fetch = np.zeros((n, 12))
    if c.metodo_zo == "ZOEFF":
        ibl = c.anem_height * c.ibl_factor
        if ibl < IBL_MIN:
            avisos.append(f"IBL {ibl:.1f} m < {IBL_MIN} m: se usa {IBL_MIN} m")
            c._ibl_txt = ("LESS THAN the minimum", ibl, IBL_MIN)
            ibl = IBL_MIN
        elif ibl > IBL_MAX:
            avisos.append(f"IBL {ibl:.1f} m > {IBL_MAX} m: se usa {IBL_MAX} m")
            c._ibl_txt = ("GREATER THAN the maximum", ibl, IBL_MAX)
            ibl = IBL_MAX
        for i in range(n):
            for j in range(12):
                prof = [0.0] * (n_rings + 1)
                for kk in range(1, n_rings + 1):
                    if inv_sum_eff[i, j, kk] < F32_1E_4:       # «.lt. 0.0001» (simple)
                        continue
                    prof[kk] = math.exp(zo_sum_eff[i, j, kk] / inv_sum_eff[i, j, kk])
                N = n_rings
                for l in range(1, N + 1):
                    if prof[l] < F32_1E_4:
                        for mm in range(l, N + 1):
                            if mm + 1 < N and prof[mm + 1] >= 0.0001:
                                prof[l] = prof[mm + 1]
                                break
                z_eff, fch = effective_roughness4(prof, ibl, ring_w, n_rings)
                avg_zo[i, j], fetch[i, j] = z_eff, fch
                if i == 0:
                    avg_bow[j] = math.exp(bowen_sum[j] / lc_count_br)
    else:
        with np.errstate(invalid="ignore", divide="ignore"):
            avg_zo[:, :] = np.exp(zo_sum / inv_sum)
        for j in range(12):
            avg_bow[j] = math.exp(bowen_sum[j] / float(lc_count_br))
        fetch[:, :] = zo_rad

    zo_mes = avg_zo.copy()                   # EffZoMnthSec (tabla mensual del log)
    if c.metodo_zo == "ZOEFF":
        fetch_medio = 0.0
        for i in range(n):
            for j in range(12):
                fetch_medio = fetch_medio + fetch[i, j]
        fetch_medio = fetch_medio / (12.0 * float(n))
    else:
        fetch_medio = zo_rad
    if tr == "S":
        zs = np.zeros((n, 12))
        bs = np.zeros(12)
        nm = [0] * NUM_SEAS
        for i in range(n):
            for j in range(12):
                se = c.meses_estacion[j]
                k = 0 if se in (1, 2) else se - 2
                if i == 0:
                    nm[k] += 1
                    bs[k] = bs[k] + avg_bow[j]
                zs[i, k] = zs[i, k] + avg_zo[i, j]
        avg_zo = np.zeros((n, 12))
        avg_bow = np.zeros(12)
        for i in range(n):
            for k in range(NUM_SEAS):
                avg_zo[i, k] = zs[i, k] / float(nm[k])
                if i == 0:
                    avg_bow[k] = bs[k] / float(nm[k])
    elif tr == "A":
        for i in range(n):
            s = 0.0
            for j in range(12):
                s = s + avg_zo[i, j]
            avg_zo[i, 0] = s / 12.0
        s = 0.0
        for j in range(12):
            s = s + avg_bow[j]
        avg_bow[0] = s / 12.0

    rej = {"LC": g_lc}
    if use_imp:
        rej["Imp"] = g_imp
    if use_can:
        rej["Can"] = g_can
    res = Resultado(avg_alb, avg_bow, avg_zo, fetch, cnt_br, cnt_z0, rej, avisos)
    res.zo_rad_final = zo_rad_mes if c.metodo_zo == "ZOEFF" else zo_rad
    res.use_imp, res.use_can = use_imp, use_can
    res.zo_mes, res.fetch_medio = zo_mes, fetch_medio
    res.ibl_avisos = [a for a in avisos if a.startswith("IBL")]
    res.canimp = (n_zo, n_mal) if (use_imp and use_can) else None
    res.ibl_txt = getattr(c, "_ibl_txt", None)
    return res
