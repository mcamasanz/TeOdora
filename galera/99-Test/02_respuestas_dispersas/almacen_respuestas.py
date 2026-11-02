# -*- coding: utf-8 -*-
"""Almacén DISPERSO de las respuestas unitarias de un foco (prototipo para el alcance 1).

R[h, t, r] = concentración en el receptor r a la hora t debida al foco con emisión 1 emitida solo
en la hora h del día (h = 0…23). Casi todo son ceros (el penacho barre una franja), así que se
guardan solo los valores por encima de `umbral · vmax`, ordenados por RECEPTOR y, dentro, por hora
(como una matriz CSR): así el P98 de cada receptor se saca leyendo solo lo suyo.

Por valor: t (uint16 si hay menos de 65 536 horas; 5 años = 43 824), h (uint8) y el valor en
CUANTIZACIÓN LOGARÍTMICA de 16 bits entre umbral·vmax y vmax: error relativo uniforme ≤
ln(1/umbral) / (2·65 534) (1·10⁻⁴ con umbral 10⁻⁶), igual en los valores grandes que en los
pequeños (con float16 los pequeños pierden precisión). 5 bytes por valor + 8 bytes por receptor.
"""
import numpy as np

NIVELES = 65535                 # códigos 1…65535; el 0 no se usa (los ceros no se guardan)


def codificar(v, vmax, umbral):
    x = np.log(np.asarray(v, float) / vmax) / np.log(umbral)        # 0 en vmax, 1 en el umbral
    k = np.rint((1.0 - x) * (NIVELES - 1)) + 1
    return np.clip(k, 1, NIVELES).astype(np.uint16)


def decodificar(k, vmax, umbral):
    x = 1.0 - (np.asarray(k, float) - 1.0) / (NIVELES - 1)
    return vmax * np.exp(x * np.log(umbral))


def desde_coo(r, t, h, v, nrec, horas, vmax, umbral):
    """Almacén a partir de valores sueltos (r, t, h, v); los ordena por receptor y hora."""
    orden = np.lexsort((t, r))
    r, t, h, v = r[orden], t[orden], h[orden], v[orden]
    indptr = np.zeros(nrec + 1, np.int64)
    np.cumsum(np.bincount(r, minlength=nrec), out=indptr[1:])
    return {"indptr": indptr, "t": t.astype(np.uint16 if horas < 65536 else np.uint32),
            "h": h.astype(np.uint8), "k": codificar(v, vmax, umbral),
            "vmax": float(vmax), "umbral": float(umbral), "horas": int(horas), "nrec": int(nrec)}


def comprimir(R, umbral, vmax=None):
    """Almacén de R (24, horas, receptores) con los valores > umbral·vmax."""
    R = np.asarray(R)
    vmax = float(R.max()) if vmax is None else float(vmax)
    h, t, r = np.nonzero(R > umbral * vmax)
    return desde_coo(r, t, h, R[h, t, r], R.shape[2], R.shape[1], vmax, umbral)


def bytes_(alm):
    return sum(alm[c].nbytes for c in ("indptr", "t", "h", "k"))


def guardar(ruta, alm, comprimido=False):
    (np.savez_compressed if comprimido else np.savez)(ruta, **{k: np.asarray(v) for k, v in alm.items()})


def cargar(ruta):
    with np.load(ruta) as z:
        alm = {k: z[k] for k in z.files}
    for k in ("vmax", "umbral"):
        alm[k] = float(alm[k])
    for k in ("horas", "nrec"):
        alm[k] = int(alm[k])
    return alm


def escenario(alms, pesos, percentil=98.0, bloque=500):
    """Media, máximo y percentil por receptor de la serie horaria del escenario
    C(t, r) = Σ_foco Σ_h pesos[foco][h] · R_foco(h, t, r), con pesos = emisión · perfil (24).
    Se recorre por bloques de receptores (cada bloque: serie completa en memoria)."""
    horas, nrec = alms[0]["horas"], alms[0]["nrec"]
    media, maximo, perc = np.zeros(nrec), np.zeros(nrec), np.zeros(nrec)
    for r0 in range(0, nrec, bloque):
        r1 = min(r0 + bloque, nrec)
        nb = r1 - r0
        acum = np.zeros(horas * nb)
        for a, w in zip(alms, pesos):
            i0, i1 = a["indptr"][r0], a["indptr"][r1]
            if i1 == i0:
                continue
            rr = np.repeat(np.arange(nb), np.diff(a["indptr"][r0:r1 + 1]))
            val = decodificar(a["k"][i0:i1], a["vmax"], a["umbral"]) * np.asarray(w, float)[a["h"][i0:i1]]
            acum += np.bincount(a["t"][i0:i1].astype(np.int64) * nb + rr, weights=val,
                                minlength=horas * nb)
        M = acum.reshape(horas, nb)
        media[r0:r1] = M.mean(0)
        maximo[r0:r1] = M.max(0)
        perc[r0:r1] = np.percentile(M, percentil, axis=0)
    return media, maximo, perc


def horas_escenario(alms, pesos, t0, t1):
    """Campo horario (t1 − t0, receptores) del escenario entre las horas t0 y t1 (un día)."""
    nrec = alms[0]["nrec"]
    out = np.zeros((t1 - t0) * nrec)
    for a, w in zip(alms, pesos):
        t = a["t"]
        m = (t >= t0) & (t < t1)
        if not m.any():
            continue
        if "_r" not in a:                       # receptor de cada valor (se calcula una vez)
            a["_r"] = np.repeat(np.arange(nrec, dtype=np.int32), np.diff(a["indptr"]))
        val = decodificar(a["k"][m], a["vmax"], a["umbral"]) * np.asarray(w, float)[a["h"][m]]
        out += np.bincount((t[m].astype(np.int64) - t0) * nrec + a["_r"][m], weights=val,
                           minlength=(t1 - t0) * nrec)
    return out.reshape(t1 - t0, nrec)
