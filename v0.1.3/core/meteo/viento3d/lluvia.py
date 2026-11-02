# -*- coding: utf-8 -*-
"""Pluviómetros (NPSTA > 0): estaciones del grupo 9, PRECIP.DAT e interpolación de la
precipitación a la malla.

Reglas (procedencia en FUENTES.md del laboratorio, claves P*):
  - NFLAGP = 1 o 2 ([UG] ec. 2-71): R = Σ Rₖ/dₖⁿ / Σ 1/dₖⁿ con las estaciones con dato a
    ≤ SIGMAP de la celda (dₖ ≥ 0,01 km); si no hay ninguna, el valor de la más cercana con dato
    (sin aplicar CUTP); el resultado interpolado < CUTP pasa a 0 [P1].
  - NFLAGP = 3 ([UG] ec. 2-72): pesos e^(−d²/σ²)/d² con todas las estaciones; con SIGMAP = 0,
    σ = la distancia MÍNIMA (no la mitad) entre una estación con lluvia y otra sin ella [P2].
  - Sin ninguna estación con dato en la hora, lluvia nula [UG] sec. 2.3.3 [P1].
  - IPCODE de cada celda: el código de precipitación de la estación de superficie más cercana
    (NEARS), con los ausentes tal cual ([UG] sec. 1.3) [P3].
"""
import re

import numpy as np

D_MIN = 0.01            # km [UG] sec. 2.3.3
SIGMA_DEF = 100.0       # km, cuando no hay pareja con y sin lluvia (SIGMAP = 0, NFLAGP = 3)


def leer_pluviometros(control, npsta):
    """Registros PSn del grupo 9 -> lista de dicts (nombre, id, x, y en m)."""
    out = []
    for n in range(1, npsta + 1):
        clave = "PS%d" % n
        if not control.hay(clave):
            raise ValueError("falta el pluviómetro %s en el grupo 9" % clave)
        m = re.match(r"\s*'([^']*)'\s*(.*)", control.cadena(clave))
        v = [x for x in re.split(r"[,\s]+", m.group(2).strip()) if x]
        out.append({"nombre": m.group(1).strip(), "id": int(float(v[0])), "x": float(v[1]) * 1000.0,
                    "y": float(v[2]) * 1000.0})
    return out


class Pluviometros:
    """Distancias pluviómetro-celda y lluvia en la malla de cada hora."""

    def __init__(self, estaciones, precip, malla, p):
        self.est = estaciones
        self.p = p
        ids = precip["ids"]
        self.col = [ids.index(e["id"]) if e["id"] in ids else k for k, e in enumerate(estaciones)]
        self.horas = precip["horas"]
        X, Y = np.meshgrid(malla.xc, malla.yc)
        self.x = np.array([e["x"] for e in estaciones])
        self.y = np.array([e["y"] for e in estaciones])
        self.d = np.maximum(np.hypot(X[None] - self.x[:, None, None],
                                     Y[None] - self.y[:, None, None]) / 1000.0, D_MIN)

    def hora(self, t):
        clave = (t.year, t.timetuple().tm_yday, t.hour)
        if clave not in self.horas:
            raise ValueError("PRECIP.DAT sin datos para %s" % (clave,))
        r = self.horas[clave][self.col]
        ok = ~np.isnan(r)
        shape = self.d.shape[1:]
        if not ok.any():
            return np.zeros(shape)
        rv = np.where(ok, r, 0.0)
        nflag = int(self.p["NFLAGP"])
        sigma = float(self.p["SIGMAP"])
        d = self.d
        if nflag in (1, 2):
            w = np.where(ok[:, None, None] & (d <= sigma), 1.0 / d ** nflag, 0.0)
            sw = w.sum(0)
            nada = sw == 0
            interp = (w * rv[:, None, None]).sum(0) / np.where(nada, 1.0, sw)
            interp = np.where(interp >= self.p["CUTP"], interp, 0.0)
            cer = np.argmin(np.where(ok[:, None, None], d, np.inf), axis=0)
            return np.where(nada, rv[cer], interp)
        if sigma <= 0:
            con = np.nonzero(ok & (rv > 0))[0]
            sin = np.nonzero(ok & (rv == 0))[0]
            if con.size and sin.size:
                sigma = min(np.hypot(self.x[a] - self.x[b], self.y[a] - self.y[b]) / 1000.0
                            for a in con for b in sin)
            else:
                sigma = SIGMA_DEF
        w = np.where(ok[:, None, None], np.exp(-d ** 2 / sigma ** 2) / d ** 2, 0.0)
        sw = w.sum(0)
        cer = np.argmin(np.where(ok[:, None, None], d, np.inf), axis=0)
        out = np.where(sw > 0, (w * rv[:, None, None]).sum(0) / np.where(sw > 0, sw, 1.0), rv[cer])
        return np.where(out >= self.p["CUTP"], out, 0.0)
