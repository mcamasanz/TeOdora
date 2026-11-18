# -*- coding: utf-8 -*-
"""Campo inicial desde el pronóstico (3D.DAT, IPROG=14) y perfiles de temperatura (ITPROG=2).

Reglas (procedencia en FUENTES.md del laboratorio):
  - Cada columna del pronóstico se interpola en vertical a las alturas de las capas de CALMET
    medidas sobre el terreno del propio punto del pronóstico [V1]; después, cada celda de la malla
    toma la media ponderada 1/R² de los 4 puntos del pronóstico más cercanos [V5].
  - Viento: lineal en (u, v) entre niveles; por debajo del primer nivel, dirección del primer
    nivel y perfil logarítmico de z0 = 0,5 m [V2, V6].
  - Temperatura: lineal en T entre niveles [T2]; por debajo del primer nivel, de día adiabática
    seca desde el primer nivel [T3]; de noche, perfil exponencial de θ anclado en una θ de
    referencia que se fija de día (o en la primera hora) [T4].
  - ITWPROG=2: en los puntos de mar, por debajo del primer nivel, perfil entre la SST del 3D.DAT
    (z = 0) y el primer nivel: lineal en T de día y lineal en θ de noche [T11]; los flujos sobre el
    agua salen del punto «de mar adentro» más cercano (de mar él y sus 8 vecinos) [W16].
"""
import math

import numpy as np

KAPPA = 0.286
GAMMA_D = 0.0098          # K/m
Z0_LOG = 0.5              # m, perfil logarítmico bajo el primer nivel [V2]
B_MAX = 15.0              # K, tope del déficit nocturno de θ en superficie [T4]
C_H0 = 3.8505             # H0 = z2 / C_H0 [T4]
SOLO_MAR_ADENTRO = 0


class Pronostico:
    """Datos del 3D.DAT y pesos de interpolación a la malla."""

    def __init__(self, d3, malla, zona_utm, hem="N", proj=None, iluoc3d=16, itwprog=0):
        """proj: cadena PROJ o código EPSG de la malla (si no, UTM de zona_utm y hem).
        itwprog: con 2, perfil sobre el mar desde la SST y datos de los flujos sobre el agua."""
        from pyproj import Transformer
        self.d3 = d3
        c = d3["cab"]
        if proj is None:
            proj = "EPSG:%d" % ((32600 if hem == "N" else 32700) + int(zona_utm))
        tr = Transformer.from_crs("EPSG:4326", proj, always_xy=True)
        self.x3, self.y3 = tr.transform(c["lon"], c["lat"])        # (nyp, nxp) m
        self.elev3 = c["elev"].astype(float)
        self.nyp, self.nxp = c["elev"].shape
        self.malla = malla
        # 4 vecinos más cercanos y pesos 1/R² para cada celda de la malla
        X, Y = np.meshgrid(malla.xc, malla.yc)
        P = np.stack([self.x3.ravel(), self.y3.ravel()], 1)
        d = np.hypot(X[..., None] - P[:, 0], Y[..., None] - P[:, 1])  # (ny, nx, np)
        orden = np.argsort(d, axis=-1)[..., :4]
        dd = np.take_along_axis(d, orden, -1)
        w = 1.0 / np.maximum(dd, 1e-3) ** 2
        exacto = dd < 1e-3
        w = np.where(exacto.any(-1, keepdims=True), exacto.astype(float), w)
        self.vec = orden                                  # (ny, nx, 4) índices planos
        self.pes = w / w.sum(-1, keepdims=True)
        self.estado = None                                 # [θ1_ref, θ2_ref] por punto
        # puntos de mar del pronóstico (uso del suelo ILUOC3D): de noche, bajo el primer nivel,
        # extrapolación lineal de los dos primeros niveles en vez de la inversión exponencial
        # [caja negra] [T6]
        self.oceano = (c["lu"] == int(iluoc3d)).ravel()
        self.fechas = [h["fecha"] for h in d3["horas"]]
        self.itwprog = int(itwprog)
        self.mar_adentro = None
        if self.itwprog == 2:
            # puntos «de mar adentro» (true offshore): de mar ellos y sus 8 vecinos (los que
            # existen: en el borde del 3D.DAT solo cuentan los de dentro); sin ninguno el original
            # se detiene [caja negra: punto aislado, costa, vecino en diagonal o a dos puntos,
            # bloque 3×3, columna del borde] [W16]
            oc = c["lu"] == int(iluoc3d)
            pad = np.pad(oc, 1, constant_values=True)
            off = np.ones_like(oc)
            for dj in (0, 1, 2):
                for di in (0, 1, 2):
                    off &= pad[dj:dj + self.nyp, di:di + self.nxp]
            self.mar_adentro = off.ravel()
            if not self.mar_adentro.any():
                raise ValueError("ITWPROG=2 sin puntos de mar adentro en el 3D.DAT: el original se "
                                 "detiene («There are no true offshore 3D.DAT gridpoints»)")
            # punto de mar adentro más cercano a cada celda (mosaico, sin interpolar) [W16]
            idx = np.nonzero(self.mar_adentro)[0]
            dd = np.hypot(X[..., None] - P[idx, 0], Y[..., None] - P[idx, 1])
            self.cercano_mar = idx[np.argmin(dd, axis=-1)]                  # (ny, nx)

    def a_malla(self, campo_puntos):
        """(np, ...) por punto del pronóstico -> (..., ny, nx) en la malla."""
        a = campo_puntos[self.vec]                          # (ny, nx, 4, ...)
        w = self.pes.reshape(self.pes.shape + (1,) * (a.ndim - 3))
        r = (a * w).sum(axis=2)
        return np.moveaxis(r, (0, 1), (-2, -1)) if r.ndim > 2 else r

    def hora(self, k, dia):
        """Columnas de la hora k interpoladas a la malla.

        Solo cuentan los niveles por encima del terreno del punto del pronóstico (z sobre el suelo
        >= 0) [V12]. Devuelve u, v, t (nz, ny, nx), rho (ny, nx) y los niveles válidos de cada
        punto compactados al principio (zp, tp: (nzp, np), con los sobrantes elevados a 1e6 m)."""
        h = self.d3["horas"][k]
        n = h["niv"]
        zc = self.malla.zc
        npnt = self.nxp * self.nyp
        nzp = n["z"].shape[0]
        zl = (n["z"] - self.elev3[None]).reshape(nzp, npnt)          # (nzp, np) sobre el suelo
        tl = n["tk"].reshape(nzp, npnt)
        pl = n["pres"].reshape(nzp, npnt)
        ws = n["ws"].reshape(nzp, npnt)
        wd = np.radians(n["wd"].reshape(nzp, npnt))
        ul, vl = -ws * np.sin(wd), -ws * np.cos(wd)
        nz = len(zc)
        U = np.zeros((npnt, nz))
        V = np.zeros((npnt, nz))
        T = np.zeros((npnt, nz))
        rho = np.zeros(npnt)
        zp = np.full((nzp, npnt), 1e6)
        tp = np.zeros((nzp, npnt))
        if self.estado is None:
            self.estado = [[np.nan, np.nan] for _ in range(npnt)]
        sst = h["sup"]["sst"].reshape(npnt) if self.itwprog == 2 else None
        t1p, z1p, rh1p = np.zeros(npnt), np.zeros(npnt), np.zeros(npnt)
        for q in range(npnt):
            ok = zl[:, q] >= 0.0
            z, tt, pp = zl[ok, q], tl[ok, q], pl[ok, q]
            U[q] = _viento(zc, z, ul[ok, q])
            V[q] = _viento(zc, z, vl[ok, q])
            T[q] = perfil_t(zc, z, tt, pp, dia, self.estado[q], bool(self.oceano[q]),
                            sst[q] if (sst is not None and (self.oceano[q] if SOLO_MAR_ADENTRO == 0 else self.mar_adentro[q])) else None)
            rho[q] = pp[0] * 100.0 / (287.0 * tt[0])
            t1p[q], z1p[q] = tt[0], z[0]
            if "rh" in n:
                rh1p[q] = n["rh"].reshape(nzp, npnt)[ok, q][0]
            m = ok.sum()
            zp[:m, q] = z
            tp[:m, q] = tt
            if m < nzp:
                zp[m:, q] = 1e6 + np.arange(nzp - m)
                tp[m:, q] = tt[-1]
        rain = h["sup"]["rain"].reshape(npnt) * 10.0                         # cm/h -> mm/h
        self.t_puntos = T                                   # (np, nz) columnas por punto
        out = {"u": self.a_malla(U), "v": self.a_malla(V), "t": self.a_malla(T),
               "rho": self.a_malla(rho), "rain_puntos": rain, "zp": zp, "tp": tp}
        if sst is not None:
            # datos de los flujos sobre el agua con ITWPROG=2, del punto de mar adentro más
            # cercano a cada celda: SST, T del primer nivel válido, su altura sobre el suelo y su
            # humedad (0 si el 3D.DAT no la trae) [caja negra] [W16]
            ic = self.cercano_mar
            out["mar"] = {"sst": sst[ic], "ta": t1p[ic], "z": z1p[ic], "rh": rh1p[ic]}
        if "rh" in n:
            # humedad relativa del primer nivel válido de cada punto (IOUTQ=1) [caja negra] [W11]
            rl = n["rh"].reshape(nzp, npnt)
            prim = np.argmax(zl >= 0.0, axis=0)
            out["rh"] = self.a_malla(rl[prim, np.arange(npnt)])
        return out

    def theta_niveles(self, zp, tp, zq):
        """θ = T + 0,0098 z de los niveles de cada punto del pronóstico evaluada a la altura zq
        (ny, nx) de cada celda y promediada con los pesos 1/R² (θ del primer nivel por debajo de
        él) [M5]."""
        th = tp + 0.0098 * np.minimum(zp, 1e5)
        out = np.zeros(zq.shape)
        for c in range(4):
            idx = self.vec[..., c]                                      # (ny, nx)
            z = zp[:, idx]
            tt = th[:, idx]
            kk = np.clip((z <= zq[None]).sum(axis=0) - 1, 0, z.shape[0] - 2)
            z0 = np.take_along_axis(z, kk[None], 0)[0]
            z1 = np.take_along_axis(z, (kk + 1)[None], 0)[0]
            t0 = np.take_along_axis(tt, kk[None], 0)[0]
            t1 = np.take_along_axis(tt, (kk + 1)[None], 0)[0]
            f = np.clip((zq - z0) / (z1 - z0), 0.0, 1.0)
            out += self.pes[..., c] * (t0 + f * (t1 - t0))
        return out


def _viento(zc, z, w):
    out = np.interp(zc, z, w)
    bajo = zc < z[0]
    if bajo.any():
        out[bajo] = w[0] * np.log(zc[bajo] / Z0_LOG) / math.log(z[0] / Z0_LOG)
    return out


def perfil_t(zc, z, t, p, dia, estado, oceano=False, sst=None):
    """Temperatura en los centros de capa de una columna del pronóstico.

    z: alturas de los niveles sobre el terreno del punto; t (K), p (hPa).
    estado: [θ1_ref, θ2_ref] de la columna (NaN al empezar); se actualiza en el sitio.
    oceano: punto de mar del 3D.DAT (ILUOC3D): de noche, bajo el primer nivel, extrapolación
    lineal de T con los niveles 1 y 2 [caja negra: pronóstico todo mar, error 1e-3 K] [T6].
    sst: con ITWPROG=2, SST del punto de mar (K): bajo el primer nivel, de día T lineal entre la
    SST (z = 0) y el primer nivel; de noche θ lineal entre la SST (tomada como θ en z = 0) y θ₁,
    con la presión extrapolada log-linealmente desde los niveles 1 y 2 (como T3) [caja negra:
    primer nivel a 10, 20, 50 y 120 m, SST de 284 a 298 K, error 1e-3 K] [T11].
    Devuelve T (nz,)."""
    out = np.interp(zc, z, t)
    h1, z2 = z[0], z[1]
    p1, p2 = p[0], p[1]
    th1 = t[0] * (1000.0 / p1) ** KAPPA
    th2 = t[1] * (1000.0 / p2) ** KAPPA
    h0 = z2 / C_H0
    if dia:
        estado[0], estado[1] = th1, th2
    elif not np.isfinite(estado[0]):
        # primera hora nocturna de la corrida: exponencial de escala H0 por los niveles 1 y 2 y
        # referencia mezclada (θ2_ref = θ1_ref) [T3]
        b0 = (th2 - th1) / (math.exp(-h1 / h0) - math.exp(-z2 / h0))
        ref = th1 if b0 <= 0 else th2 + min(b0, B_MAX) * math.exp(-z2 / h0)
        estado[0], estado[1] = ref, ref
    bajo = zc < h1
    if not bajo.any():
        return out
    zb = zc[bajo]
    if sst is not None:
        if dia:
            out[bajo] = sst + (t[0] - sst) * zb / h1
            return out
        lp = math.log(p1) + (math.log(p1) - math.log(p2)) * (h1 - zb) / (z2 - h1)
        th = sst + (th1 - sst) * zb / h1
        out[bajo] = th * (np.exp(lp) / 1000.0) ** KAPPA
        return out
    if dia:
        out[bajo] = t[0] + GAMMA_D * (h1 - zb)
        return out
    if oceano:
        out[bajo] = t[0] + (t[0] - t[1]) / (z2 - h1) * (h1 - zb)
        return out
    # presión bajo el primer nivel: extrapolación log-lineal desde los niveles 1 y 2
    lp = math.log(p1) + (math.log(p1) - math.log(p2)) * (h1 - zb) / (z2 - h1)
    pz = np.exp(lp)
    ref1, ref2 = estado
    d1, d2 = th1 - ref1, th2 - ref2
    if d1 >= 0.0:
        th = np.full_like(zb, th1)
    else:
        # escala por los cambios desde la referencia en los niveles 1 y 2 [T3]
        hh = (z2 - h1) / math.log(d1 / d2) if (d2 < 0.0 and d1 / d2 > 1.0) else h0
        b = min(-d1 * math.exp(h1 / hh), B_MAX)
        th = ref1 - b * np.exp(-zb / hh)
    out[bajo] = th * (pz / 1000.0) ** KAPPA
    return out
