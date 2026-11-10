# -*- coding: utf-8 -*-
"""Observaciones (NOOBS=1 y 0): estaciones de superficie del grupo 7 y datos del SURF.DAT, sondeos
del grupo 8 (UPn.DAT), paso 2 del viento y campos de superficie desde las estaciones (ITPROG=1).

Reglas (procedencia en FUENTES.md del laboratorio, claves O*):
  - Paso 2 ([UG] ec. 2-18) en cada capa: (u,v) = [(u,v)₁/R² + Σ (u,v)ₖ/rₖ²] / [1/R² + Σ 1/rₖ²],
    R = R1 en la capa 1 y R2 encima; rₖ (km) ≥ RMIN; solo cuentan las estaciones con viento
    válido a ≤ RMAX de la celda (RMAX3 en las celdas de agua, RMAX1 en la capa 1 y RMAX2 encima)
    y, de ellas, las NINTR2 más cercanas; con LVARY, si no hay ninguna, la más cercana [O1-O4].
  - BIAS no cambia nada con el pronóstico como campo inicial [O5]. Extrapolación vertical
    (IEXTRP): ±1 solo capa 1; ±3 la observación × FEXTR2(k) en todas las capas (también la 1);
    ±4 perfil de semejanza (ψ de COARE 3.0) y giro de van Ulden y Holtslag en las capas cuya cara
    superior no pasa de la altura de mezcla de la estación [O6, O7].
  - Sondeos: viento medio de cada capa con alturas desde su primer nivel, lineal en el tiempo, en
    las capas 2..NZ (y en la 1 con IEXTRP > 0) [O18].
  - Temperatura (ITPROG=1): media ponderada con peso mín(1, 1/r^IRAD), r en celdas, de las
    estaciones a ≤ TRADKM (NUMTS más cercanas); la humedad con los mismos pesos y truncada; la
    presión, la de la estación más cercana (NEARS) [O9-O11].
  - Estaciones sobre el agua: entran en el paso 2 como estaciones de superficie más [W7].
  - Regiones de brisa (LLBREZE): capa 1 por 1/d² con distancias relativas a la costa [B1-B4].
  - Barreras (NBAR): sin las observaciones al otro lado de una barrera en las capas 1..KBAR [O21].
  - Potencial (IEXTRP = ±2) con el exponente del uso del suelo de la celda de la estación [O19];
    RMIN2 en celdas de malla [O20].
  - Temperatura 3D de los sondeos (ITPROG=0): caras de las capas, pesos mín(1, 1/r^IRAD), último
    sondeo de IUPT para ψ₁ y gradiente del bloqueo [T7-T9].
"""
import math
import re

import numpy as np

from .entradas import AUSENTE


def leer_estaciones(control, nssta):
    """Registros SSn del grupo 7 -> lista de dicts (nombre, id, x, y en m, zona, anemómetro)."""
    out = []
    for n in range(1, nssta + 1):
        clave = "SS%d" % n
        if not control.hay(clave):
            raise ValueError("falta la estación %s en el grupo 7" % clave)
        s = control.cadena(clave)
        m = re.match(r"\s*'([^']*)'\s*(.*)", s)
        nombre, resto = (m.group(1), m.group(2)) if m else ("", s)
        v = [x for x in re.split(r"[,\s]+", resto.strip()) if x]
        out.append({"nombre": nombre.strip(), "id": int(float(v[0])), "x": float(v[1]) * 1000.0,
                    "y": float(v[2]) * 1000.0, "zona": v[3] if len(v) > 3 else "0",
                    "zanem": float(v[4]) if len(v) > 4 else 10.0})
    return out


def _uv(ws, wd):
    r = np.radians(wd)
    return -ws * np.sin(r), -ws * np.cos(r)


class Observaciones:
    """Distancias estación-celda, estación más cercana y análisis de cada hora."""

    def __init__(self, estaciones, surf, malla, agua, p):
        self.est = estaciones
        self.malla = malla
        self.agua = agua
        self.p = p
        ns = len(estaciones)
        # columnas del SURF.DAT de cada estación (por identificador; si no, por orden)
        ids = surf["ids"]
        self.col = [ids.index(e["id"]) if e["id"] in ids else k for k, e in enumerate(estaciones)]
        self.horas = surf["horas"]
        X, Y = np.meshgrid(malla.xc, malla.yc)
        self.xs = np.array([e["x"] for e in estaciones])
        self.ys = np.array([e["y"] for e in estaciones])
        self.d = np.hypot(X[None] - self.xs[:, None, None], Y[None] - self.ys[:, None, None]) / 1000.0
        self.nears = np.argmin(self.d, axis=0) + 1                 # 1..NSSTA
        # celda de cada estación (para el perfil de semejanza); fuera de la malla, la del borde
        self.ic = np.clip(((self.xs - malla.x0) // malla.dx).astype(int), 0, malla.nx - 1)
        self.jc = np.clip(((self.ys - malla.y0) // malla.dx).astype(int), 0, malla.ny - 1)
        self.ns = ns

    # ───────────────────────────── datos de la hora ─────────────────────────────
    def datos(self, t):
        """(nsta, 8) de la hora t (datetime) en el orden de las estaciones del grupo 7, con los
        ausentes de techo, nubosidad, humedad y presión rellenados con el valor de la estación más
        cercana que tiene dato ([UG] apéndice B, MISSFC). La temperatura no se rellena: la
        estación sin dato queda fuera de la interpolación [caja negra] [O8]."""
        clave = (t.year, t.timetuple().tm_yday, t.hour)
        if clave not in self.horas:
            raise ValueError("SURF.DAT sin datos para %s" % (clave,))
        dat = self.horas[clave][self.col].copy()
        dss = np.hypot(self.xs[:, None] - self.xs[None], self.ys[:, None] - self.ys[None])
        for c in (2, 3, 5, 6):
            ok = dat[:, c] < AUSENTE * 0.999
            if ok.all() or not ok.any():
                continue
            for s in np.nonzero(~ok)[0]:
                dat[s, c] = dat[np.argmin(np.where(ok, dss[s], np.inf)), c]
        return dat

    # ───────────────────────────── paso 2 del viento ─────────────────────────────
    def viento(self, u, v, dat, zc, extra=None, alto=None, mar=None, barreras=None):
        """Paso 2 en todas las capas. u, v (nz, ny, nx) del paso 1; dat (nsta, 8) de la hora.
        extra(k, ws, wd, validas) -> (ws_k, wd_k, usar_k) para la extrapolación vertical.
        alto: sondeos de la hora (Sondeos.hora): sus vientos entran en las capas 2..NZ y, con
        IEXTRP > 0, también en la 1 [O18]. mar: estaciones sobre el agua de la hora ({d, u, v,
        ok} con u, v, ok por capa): entran como estaciones de superficie más, también en su
        extrapolación vertical [W7]."""
        p = self.p
        ws, wd = dat[:, 0], dat[:, 1]
        validas = (ws < AUSENTE * 0.999) & (wd < AUSENTE * 0.999) & (ws >= 0)
        u = u.astype(float).copy()
        v = v.astype(float).copy()
        iextrp = abs(int(p["IEXTRP"]))
        nada = np.zeros(self.ns, bool)
        extrapola = validas & ((ws > 0) | bool(p["ICALM"]))
        if alto is not None and p.get("RMIN2", -1.0) > 0:
            # sin extrapolar las estaciones a menos de RMIN2 de un sondeo ([UG] sec. 2.2.2); el
            # original mide esa distancia en celdas de malla (RMIN2·DGRIDKM km), no en km
            # [caja negra: umbral entre 0,95 y 1,0 km con RMIN2 = 4 y celdas de 0,24 km; entre 1,9
            # y 2,1 km con celdas de 0,5 km] [O20]
            dsu = np.hypot(self.xs[:, None] - alto["x"][None], self.ys[:, None] - alto["y"][None]) / 1000.0
            extrapola &= ~(dsu < p["RMIN2"] * self.malla.dx / 1000.0).any(axis=1)
        # potencial (IEXTRP = ±2): exponente 0,143 en tierra y 0,286 en el agua (uso del suelo de
        # la celda de la estación), desde la altura del anemómetro hasta el centro de cada capa,
        # también la 1 ([UG] ec. 2-19; caja negra) [O19]
        pot = np.where(self.agua[self.jc, self.ic], 0.286, 0.143)
        za = np.array([e["zanem"] for e in self.est])
        for k in range(u.shape[0]):
            wsk, wdk, usar = ws, wd, nada
            if k == 0:
                usar = validas
                if iextrp == 3:
                    wsk = ws * p["FEXTR2"][0]
                elif iextrp == 2:
                    wsk = ws * (zc[0] / za) ** pot
            elif iextrp == 2:
                usar = extrapola
                wsk = ws * (zc[k] / za) ** pot
            elif iextrp == 3:
                usar = extrapola
                wsk = ws * p["FEXTR2"][min(k, len(p["FEXTR2"]) - 1)]
            elif iextrp == 4 and extra is not None:
                wsk, wdk, usar = extra(k, ws, wd, extrapola)
            uo, vo = _uv(np.where(usar, wsk, 0.0), np.where(usar, wdk, 0.0))
            d = self.d
            if mar is not None:
                d = np.concatenate([d, mar["d"]])
                uo = np.concatenate([uo, mar["u"][:, k]])
                vo = np.concatenate([vo, mar["v"][:, k]])
                usar = np.concatenate([usar, mar["ok"][:, k]])
            if alto is not None and (k > 0 or int(p["IEXTRP"]) > 0):
                ok = alto["ok"][:, k] & (alto["capa1"] if k == 0 else True)
                d = np.concatenate([d, alto["d"]])
                uo = np.concatenate([uo, alto["u"][:, k]])
                vo = np.concatenate([vo, alto["v"][:, k]])
                usar = np.concatenate([usar, ok])
            if not usar.any():
                continue
            R = p["R1"] if k == 0 else p["R2"]
            rmax = np.where(self.agua, p["RMAX3"], p["RMAX1"] if k == 0 else p["RMAX2"])
            nint = int(p["NINTR2"][min(k, len(p["NINTR2"]) - 1)])
            if barreras is not None and k < barreras.kbar:
                # sin las observaciones al otro lado de una barrera [O21]
                xs, ys = self.xs, self.ys
                if mar is not None:
                    xs, ys = np.concatenate([xs, mar["x"]]), np.concatenate([ys, mar["y"]])
                if alto is not None and (k > 0 or int(p["IEXTRP"]) > 0):
                    xs, ys = np.concatenate([xs, alto["x"]]), np.concatenate([ys, alto["y"]])
                d = np.where(barreras.bloqueo(xs, ys), np.inf, d)
            u[k], v[k] = self._interp(u[k], v[k], uo, vo, usar, R, rmax, nint, d)
        return u, v

    def _interp(self, u1, v1, uo, vo, usar, R, rmax, nint, dist):
        p = self.p
        idx = np.nonzero(usar)[0]
        d = dist[idx]                                         # (nv, ny, nx) km
        r = np.maximum(d, p["RMIN"])
        orden = np.argsort(d, axis=0, kind="stable")
        ds = np.take_along_axis(d, orden, 0)
        rs = np.take_along_axis(r, orden, 0)
        dentro = (ds <= rmax[None]) & (np.arange(len(idx))[:, None, None] < nint)
        w = np.where(dentro, 1.0 / rs ** 2, 0.0)
        if p["LVARY"]:
            nada = ~dentro.any(axis=0)
            w[0] = np.where(nada, 1.0 / rs[0] ** 2, w[0])
        uo_s = np.asarray(uo)[idx][orden]
        vo_s = np.asarray(vo)[idx][orden]
        w1 = 1.0 / R ** 2
        den = w1 + w.sum(axis=0)
        return (w1 * u1 + (w * uo_s).sum(axis=0)) / den, (w1 * v1 + (w * vo_s).sum(axis=0)) / den

    # ───────────────────────────── campos de superficie ─────────────────────────────
    def _pesos_t(self, validas, dist=None):
        """Pesos de la interpolación de temperatura (ny, nx) por estación válida [O9]. dist:
        distancias (nsta, ny, nx) en km de otro conjunto de estaciones (las del agua)."""
        return pesos_t(self.d if dist is None else dist, validas, self.malla.dx, self.p)

    def superficie(self, dat):
        """Temperatura (K), humedad relativa (entera, %) y presión (hPa) en la malla."""
        tk, irh, pres = dat[:, 4], dat[:, 5], dat[:, 6]
        ok_t = tk < AUSENTE * 0.999
        if not ok_t.any():
            raise ValueError("ninguna estación con temperatura válida en la hora")
        idx, w = self._pesos_t(ok_t)
        t = (w * tk[idx][:, None, None]).sum(0) / w.sum(0)
        rh = self.humedad(dat)
        if not (pres < AUSENTE * 0.999).all():
            raise ValueError("ninguna estación con presión válida en la hora")
        return t, rh, pres[self.nears - 1]

    def humedad(self, dat):
        """Humedad relativa (entera, %) en la malla con los pesos de la temperatura, truncada
        [O10]."""
        irh = dat[:, 5]
        ok_h = irh < AUSENTE * 0.999
        if not ok_h.any():
            return np.zeros((self.malla.ny, self.malla.nx), int)
        idh, wh = self._pesos_t(ok_h)
        rh = (wh * irh[idh][:, None, None]).sum(0) / wh.sum(0)
        return np.floor(rh + 1e-6).astype(int)


class Barreras:
    """Barreras a la interpolación del viento (NBAR > 0): una observación no entra en una celda si
    el segmento estación-centro de celda corta alguna barrera (segmento XBBAR,YBBAR-XEBAR,YEBAR en
    km, con sus coordenadas exactas aunque el listado del original las escriba como índices de
    malla enteros), en las capas 1..KBAR ([UG] sec. 2.2.2; caja negra) [O21]."""

    def __init__(self, control, malla):
        def lista(n):
            v = control.lista(n)
            return [float(x) for x in v[-1]] if v else []
        n = control.entero("NBAR", 0)
        self.kbar = control.entero("KBAR", malla.nz)
        xb, yb, xe, ye = lista("XBBAR"), lista("YBBAR"), lista("XEBAR"), lista("YEBAR")
        dx = malla.dx
        g = lambda v, o: (v * 1000.0 - o) / dx
        self.seg = [(g(xb[q], malla.x0), g(yb[q], malla.y0), g(xe[q], malla.x0), g(ye[q], malla.y0))
                    for q in range(n)]
        self.malla = malla
        X, Y = np.meshgrid(np.arange(malla.nx) + 0.5, np.arange(malla.ny) + 0.5)
        self.X, self.Y = X, Y

    def bloqueo(self, xs, ys):
        """(n, ny, nx): True si la barrera separa el punto n (m) de la celda."""
        m = self.malla
        px = (np.asarray(xs, float) - m.x0) / m.dx
        py = (np.asarray(ys, float) - m.y0) / m.dx
        out = np.zeros((len(px),) + self.X.shape, bool)
        orient = lambda ax, ay, bx, by, cx, cy: (bx - ax) * (cy - ay) - (by - ay) * (cx - ax)
        for (bx, by, ex, ey) in self.seg:
            for q in range(len(px)):
                o1 = orient(px[q], py[q], self.X, self.Y, bx, by)
                o2 = orient(px[q], py[q], self.X, self.Y, ex, ey)
                o3 = orient(bx, by, ex, ey, px[q], py[q])
                o4 = orient(bx, by, ex, ey, self.X, self.Y)
                out[q] |= (o1 * o2 < 0) & (o3 * o4 < 0)
        return out


class Brisa:
    """Regiones de brisa (LLBREZE): en cada caja (XG1-XG2, YG1-YG2, celdas inclusivas, base 1) el
    viento de la capa 1 se sustituye, antes del suavizado, por la interpolación 1/d² de las
    estaciones de la región (METBXID: primero las de superficie y después las de altura) con
    d = |d_celda − d_estación|, las distancias con signo a la recta de la costa (se suman si
    están a lados distintos), sin campo inicial ([UG] sec. 2.2.2, «Lake/Sea Breeze Option»; caja
    negra: costa recta con 3 estaciones, error 1e-4 m/s; región parcial y suavizado) [B1-B3]. Los
    sondeos de METBXID solo entran con IEXTRP > 0 (con su viento de la capa 1, como en el paso 2);
    con IEXTRP < 0 no cambian nada [caja negra] [B4]."""

    def __init__(self, control, obs, malla, sond=None):
        def lista(n):
            v = control.lista(n)
            return [float(x) for x in v[-1]] if v else []
        nbox = control.entero("NBOX", 0)
        xg1, xg2, yg1, yg2 = lista("XG1"), lista("XG2"), lista("YG1"), lista("YG2")
        xb, yb, xe, ye = lista("XBCST"), lista("YBCST"), lista("XECST"), lista("YECST")
        nlb = [int(x) for x in lista("NLB")] or [len(lista("METBXID"))]
        ids = [int(x) for x in lista("METBXID")]
        X, Y = np.meshgrid(malla.xc, malla.yc)
        self.cajas = []
        q = 0
        ids_sup = [e["id"] for e in obs.est] if obs is not None else []
        ids_alt = [e["id"] for e in sond.est] if sond is not None else []
        for b in range(nbox):
            n = nlb[min(b, len(nlb) - 1)]
            mios = ids[q:q + n]
            q += n
            sel = [k for k, i in enumerate(ids_sup) if i in mios]
            selu = [k for k, i in enumerate(ids_alt) if i in mios]
            if len(sel) + len(selu) < len(mios):
                raise ValueError("brisa: METBXID con estaciones que no están en los grupos 7 u 8")
            bx, by = xb[b] * 1000.0, yb[b] * 1000.0
            ex, ey = xe[b] * 1000.0, ye[b] * 1000.0
            lon = math.hypot(ex - bx, ey - by)
            dist = lambda px, py: ((ex - bx) * (py - by) - (ey - by) * (px - bx)) / lon / 1000.0
            dc = dist(X, Y)
            ds = dist(obs.xs[sel], obs.ys[sel]) if sel else np.zeros(0)
            du = dist(sond.x[selu], sond.y[selu]) if selu else np.zeros(0)
            m = np.zeros(X.shape, bool)
            i1, i2 = sorted((int(round(xg1[b])), int(round(xg2[b]))))
            j1, j2 = sorted((int(round(yg1[b])), int(round(yg2[b]))))
            m[max(j1 - 1, 0):j2, max(i1 - 1, 0):i2] = True
            self.cajas.append((m, np.array(sel, int), np.abs(dc[None] - ds[:, None, None]),
                               np.array(selu, int), np.abs(dc[None] - du[:, None, None])))
        self.mascara = np.zeros(X.shape, np.bool_)
        for c in self.cajas:
            self.mascara |= c[0]

    def aplicar(self, u, v, dat, alto=None, iextrp=-1):
        """Sustituye la capa 1 de u, v (nz, ny, nx) en las cajas con el viento de la hora."""
        u = u.copy()
        v = v.copy()
        for m, sel, d, selu, du in self.cajas:
            uo, vo, dd = [], [], []
            if dat is not None and len(sel):
                ws, wd = dat[sel, 0], dat[sel, 1]
                ok = (ws < AUSENTE * 0.999) & (wd < AUSENTE * 0.999)
                a, b = _uv(ws[ok], wd[ok])
                uo.append(a); vo.append(b); dd.append(d[ok])
            if alto is not None and len(selu) and iextrp > 0:
                ok = alto["ok"][selu, 0]
                uo.append(alto["u"][selu, 0][ok]); vo.append(alto["v"][selu, 0][ok]); dd.append(du[ok])
            if not uo or sum(len(x) for x in uo) == 0:
                continue
            uo, vo, dd = np.concatenate(uo), np.concatenate(vo), np.concatenate(dd)
            w = 1.0 / np.maximum(dd, 1e-9) ** 2
            sw = w.sum(0)
            u[0] = np.where(m, (w * uo[:, None, None]).sum(0) / sw, u[0])
            v[0] = np.where(m, (w * vo[:, None, None]).sum(0) / sw, v[0])
        return u, v


def pesos_t(dist, validas, dx, p):
    """Pesos de la interpolación de temperatura y humedad: mín(1, 1/r^IRAD) con r en celdas de
    malla, solo estaciones a ≤ TRADKM y, de ellas, las NUMTS más cercanas; sin ninguna, la más
    cercana [O9]. dist: (nsta, ny, nx) en km. Devuelve (índices válidos, pesos)."""
    idx = np.nonzero(validas)[0]
    if idx.size == 0:
        return idx, None
    d = dist[idx]
    rc = np.maximum(d * 1000.0 / dx, 1e-6)
    w = np.minimum(1.0, 1.0 / rc ** int(p["IRAD"]))
    orden = np.argsort(d, axis=0, kind="stable")
    rango = np.empty_like(orden)
    np.put_along_axis(rango, orden, np.arange(len(idx))[:, None, None], 0)
    dentro = (d <= p["TRADKM"]) & (rango < int(p["NUMTS"]))
    nada = ~dentro.any(axis=0)
    dentro = dentro | (nada[None] & (rango == 0))           # sin ninguna: la más cercana
    return idx, np.where(dentro, w, 0.0)


def leer_estaciones_altura(control, nusta):
    """Registros USn del grupo 8 -> lista de dicts (nombre, id, x, y en m)."""
    out = []
    for n in range(1, nusta + 1):
        clave = "US%d" % n
        if not control.hay(clave):
            raise ValueError("falta la estación de altura %s en el grupo 8" % clave)
        m = re.match(r"\s*'([^']*)'\s*(.*)", control.cadena(clave))
        v = [x for x in re.split(r"[,\s]+", m.group(2).strip()) if x]
        out.append({"nombre": m.group(1).strip(), "id": int(float(v[0])), "x": float(v[1]) * 1000.0,
                    "y": float(v[2]) * 1000.0})
    return out


def _media_capa(z, f, a, b):
    """Media de la función lineal a trozos f(z) (constante fuera de los extremos) en [a, b]."""
    zz = np.concatenate([[a], z[(z > a) & (z < b)], [b]])
    ff = np.interp(zz, z, f)
    return float(np.sum(0.5 * (ff[1:] + ff[:-1]) * np.diff(zz)) / (b - a))


class Sondeos:
    """Sondeos (UPn.DAT) de las estaciones del grupo 8: viento de cada capa por hora [O18]:
    alturas sobre el primer nivel del sondeo, componentes (u, v) lineales entre niveles válidos y
    promediadas en el espesor de cada capa, e interpolación lineal en el tiempo entre sondeos."""

    def __init__(self, estaciones, sondeos, malla, nombres_sup=()):
        self.est = estaciones
        self.son = [sorted(s, key=lambda q: q[0]) for s in sondeos]
        self.malla = malla
        X, Y = np.meshgrid(malla.xc, malla.yc)
        self.x = np.array([e["x"] for e in estaciones])
        self.y = np.array([e["y"] for e in estaciones])
        self.d = np.hypot(X[None] - self.x[:, None, None], Y[None] - self.y[:, None, None]) / 1000.0
        self.ic = np.clip(((self.x - malla.x0) // malla.dx).astype(int), 0, malla.nx - 1)
        self.jc = np.clip(((self.y - malla.y0) // malla.dx).astype(int), 0, malla.ny - 1)
        # sondeo en el mismo sitio que una estación de superficie (mismo nombre): sin capa 1
        self.capa1 = np.array([e["nombre"][:4] not in [n[:4] for n in nombres_sup] for e in estaciones])

    def _perfil(self, a):
        """(u, v) medios por capa de un sondeo (n, 5); None si no tiene viento. Si el sondeo no
        llega a la cara superior de la malla el original se detiene («ERROR IN SUBR. VERTAV --
        cell face is above top sounding level») [caja negra] [O18]."""
        ok = np.isfinite(a[:, 1]) & np.isfinite(a[:, 3]) & np.isfinite(a[:, 4])
        if ok.sum() < 1:
            return None
        z0 = a[np.isfinite(a[:, 1]), 1][0]
        ztop = a[np.isfinite(a[:, 1]), 1][-1] - z0
        if ztop < self.malla.zface[-1]:
            raise ValueError("sondeo más bajo que la cara superior de la malla (%.1f m < %.1f m): "
                             "el original se detiene («cell face is above top sounding level»)"
                             % (ztop, self.malla.zface[-1]))
        z = a[ok, 1] - z0
        uu, vv = _uv(a[ok, 4], a[ok, 3])
        zf = self.malla.zface
        return (np.array([_media_capa(z, uu, zf[k], zf[k + 1]) for k in range(len(zf) - 1)]),
                np.array([_media_capa(z, vv, zf[k], zf[k + 1]) for k in range(len(zf) - 1)]))

    @staticmethod
    def _pares(son, t):
        """Sondeos que rodean la hora t con sus pesos lineales en el tiempo."""
        tiempos = [s[0] for s in son]
        if t <= tiempos[0]:
            return [(son[0][1], 1.0)]
        if t >= tiempos[-1]:
            return [(son[-1][1], 1.0)]
        i = max(j for j, tt in enumerate(tiempos) if tt <= t)
        f = (t - tiempos[i]).total_seconds() / (tiempos[i + 1] - tiempos[i]).total_seconds()
        return [(son[i][1], 1.0 - f), (son[i + 1][1], f)]

    @staticmethod
    def _t_perfil(a, zq):
        """T (K) del sondeo a (n, 5) a las alturas zq (m sobre su primer nivel): lineal entre los
        niveles con temperatura válida, constante fuera; None sin temperatura [T7]."""
        okz = np.isfinite(a[:, 1])
        ok = okz & np.isfinite(a[:, 2])
        if not ok.any():
            return None
        z = a[ok, 1] - a[okz, 1][0]
        return np.interp(zq, z, a[ok, 2])

    def temperatura(self, t, zq):
        """Temperatura de cada sondeo a las alturas zq (m sobre su primer nivel), lineal en el
        tiempo entre sondeos ([UG] sec. 2.3.2, pasos 1 y 2) [T7]. Devuelve (T (n, len(zq)),
        válido (n,))."""
        n = len(self.est)
        T = np.zeros((n, len(zq)))
        ok = np.zeros(n, bool)
        for q, son in enumerate(self.son):
            perf = [(self._t_perfil(a, zq), w) for a, w in self._pares(son, t) if w > 0]
            if any(pf is None for pf, _ in perf):
                continue
            T[q] = sum(w * pf for pf, w in perf)
            ok[q] = True
        return T, ok

    def ultimo(self, t):
        """Último sondeo de cada estación a la hora t o antes (el primero si no hay ninguno)."""
        out = []
        for son in self.son:
            previos = [s for s in son if s[0] <= t]
            out.append((previos[-1] if previos else son[0])[1])
        return out

    def theta(self, t, zq, q):
        """θ = T + 0,0098 z del último sondeo (a la hora t o antes) de la estación q a las alturas
        zq (m sobre su primer nivel), para el gradiente sobre la altura de mezcla convectiva con
        ITPROG=0: el mismo sondeo (IUPT) en toda la malla ([UG] sec. 2.3.1: «the latest sounding
        ... is used to determine ψ1»; caja negra) [T8]."""
        flat = np.asarray(zq, float).ravel()
        tt = self._t_perfil(self.ultimo(t)[q], flat)
        return (tt + 0.0098 * flat).reshape(np.shape(zq))

    def hora(self, t):
        nz = self.malla.nz
        n = len(self.est)
        U, V, OK = np.zeros((n, nz)), np.zeros((n, nz)), np.zeros((n, nz), bool)
        for q, son in enumerate(self.son):
            perf = [(self._perfil(a), w) for a, w in self._pares(son, t) if w > 0]
            if any(pf is None for pf, _ in perf):
                continue
            U[q] = sum(w * pf[0] for pf, w in perf)
            V[q] = sum(w * pf[1] for pf, w in perf)
            OK[q] = True
        return {"d": self.d, "u": U, "v": V, "ok": OK, "capa1": self.capa1, "x": self.x, "y": self.y}


class GradienteSondeo:
    """Gradiente térmico del dominio (N del bloqueo) con ITPROG=0 [T9]: el del perfil del sondeo
    IUPT entre su primer nivel y ZUPT, que evoluciona de hora en hora: el de la hora anterior se
    interpola linealmente en el tiempo hacia el del sondeo siguiente y, si la altura de mezcla
    convectiva de la hora anterior llegaba a ZUPT, pasa a ser el adiabático (−0,0098 K/m)
    ([UG] sec. 2.2.1, IUPT, ZUPT; caja negra: N medido con un barrido de CRITFN hora a hora tras
    la puesta de sol, que tiende de forma lineal al del sondeo siguiente)."""

    def __init__(self, sondeos, zupt):
        self.son = sorted(sondeos, key=lambda q: q[0])
        self.zupt = zupt
        self.g = None

    def _g(self, a):
        tt = Sondeos._t_perfil(a, np.array([0.0, self.zupt]))
        return (tt[1] - tt[0]) / self.zupt

    def hora(self, t, h_ant):
        import datetime as dt
        una = dt.timedelta(hours=1)
        if self.g is None:
            g = sum(w * self._g(a) for a, w in Sondeos._pares(self.son, t - una))
        else:
            g = self.g
        sig = [s for s in self.son if s[0] >= t]
        if sig:
            n = (sig[0][0] - (t - una)).total_seconds() / 3600.0
            g = g + (self._g(sig[0][1]) - g) / n
        if h_ant >= self.zupt:
            g = -0.0098
        self.g = g
        return g


# ───────────────────────────── extrapolación por semejanza (IEXTRP=±4) ─────────────────────
# [UG] tabla 2-1: giro del viento a 200 m (grados, horario) frente a la longitud de Monin-Obukhov
L_GIRO = np.array([-30.0, -100.0, -370.0, 1e4, 350.0, 130.0, 60.0, 20.0, 9.0])
D_GIRO = np.array([12.0, 10.0, 9.0, 12.0, 18.0, 28.0, 35.0, 38.0, 39.0])
H_GIRO, D1_GIRO, D2_GIRO = 200.0, 1.58, 1.0


def giro_200(el):
    """D(h) por interpolación lineal en 1/L de la tabla 2-1 [UG]; fuera, el extremo."""
    x = 1.0 / np.asarray(L_GIRO)
    o = np.argsort(x)
    return np.interp(1.0 / el, x[o], D_GIRO[o])


def giro(z, dh):
    """[UG] ec. 2-21: D(z) = D(h)·d1·(1 − exp(−d2 z/h))."""
    return dh * D1_GIRO * (1.0 - np.exp(-D2_GIRO * z / H_GIRO))


def psi_m(z, el):
    """Funciones de estabilidad del perfil de extrapolación: las de COARE 3.0 (inestable: mezcla
    de la de Kansas, x = (1 − 16ζ)^¼, y la convectiva, y = (1 − 10,15ζ)^⅓, con peso ζ²/(1 + ζ²);
    estable: −[(1 + ζ) + 0,6667 (ζ − 14,28) e^(−mín(50, 0,35ζ)) + 8,525]) [caja negra: la ec. 2-23
    a 2-25 de [UG] no reproduce el original; estas, a 1e-5] [O7]."""
    zet = np.asarray(z, float) / np.asarray(el, float)
    zn = np.minimum(zet, 0.0)
    x = np.power(1.0 - 16.0 * zn, 0.25)
    pk = 2 * np.log((1 + x) / 2) + np.log((1 + x * x) / 2) - 2 * np.arctan(x) + np.pi / 2
    y = np.power(1.0 - 10.15 * zn, 1.0 / 3.0)
    pc = (1.5 * np.log((1 + y + y * y) / 3) - math.sqrt(3) * np.arctan((1 + 2 * y) / math.sqrt(3))
          + np.pi / math.sqrt(3))
    f = zn * zn / (1 + zn * zn)
    inest = (1 - f) * pk + f * pc
    zp = np.maximum(zet, 0.0)
    est = -((1 + zp) + 0.6667 * (zp - 14.28) * np.exp(-np.minimum(50.0, 0.35 * zp)) + 8.525)
    return np.where(zet < 0, inest, est)


def perfil_semejanza(ws, z1, z, z0, el):
    """[UG] ec. 2-22: U(z) = U(z1)·[ln(z/z0) − ψ(z/L)] / [ln(z1/z0) − ψ(z1/L)]."""
    return ws * (np.log(z / z0) - psi_m(z, el)) / (np.log(z1 / z0) - psi_m(z1, el))
