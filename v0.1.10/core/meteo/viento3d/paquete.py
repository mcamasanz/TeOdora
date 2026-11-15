# -*- coding: utf-8 -*-
"""Paquete de viento: una serie de viento 3D de varios años (los .cmz de `almacen`, uno por mes) en una carpeta de
~1 GB, para llevarla con la aplicación sin la carpeta de cálculos.

Cada variable grande se guarda como patrones espaciales fijos (POD, los mismos para todos los meses) y, por hora, sus
coeficientes; donde el error pasaría de la tolerancia, se corrige:

    x(t) = media + Σ_k a_k(t) · φ_k + c(t) · paso,     |error| ≤ paso / 2 en todas las celdas y horas

con c entero, casi siempre 0, guardado disperso. U, V, W y T llevan sus capas juntas en cada patrón. L (Monin-Obukhov)
va como asinh(L / L0): pasa por 0 sin saltos y su paso es un error RELATIVO (paso / 2 ≈ 2,5 % con 0,05). La humedad,
entera, se redondea. Lo demás (clase de estabilidad, lluvia, campos fijos, cabeceras) va tal cual, como en el .cmz.
El error se mide frente al .cmz, que ya está cuantizado (`almacen`).

Carpeta:
  indice.json           formato, serie, malla, meses y, por variable, modos, paso y errores medidos al construirlo
  bases/<VAR>_<cc>.xz   por variable y capa: sus modos (int16, con escala por modo) y su media
  AAAAMM.vz             por mes: lo pequeño del .cmz tal cual, su caso.json y, por variable, coeficientes y correcciones
Todo con lzma (biblioteca estándar); ningún fichero pasa de unas decenas de MB. Los meses que lleguen después (otro año)
se añaden con `anadir`, con los mismos patrones: no hace falta rehacer el paquete.

No conoce la planta: recibe rutas (`casos.viento3d` decide si se lee del .cmz o de aquí).
"""
import io
import json
import lzma
import struct
import time
import zipfile
import zlib
from functools import lru_cache
from pathlib import Path

import numpy as np

from . import almacen

FORMATO = 1
PRESET = 6                                      # lzma
BLOQUE_H = 96                                   # horas que se reconstruyen a la vez al escribir el fichero de viento
# Variable: modos, paso de la corrección (error máximo = paso / 2) y, si hace falta, transformada o redondeo.
# Medido con 2024 (2026-11-06): con estos, ~6 MB por mes más ~290 MB de bases. Lo que más pesa son las correcciones, así
# que los pasos son lo que el uso admite: L es un orden de magnitud (±10 %), la humedad no la usa el motor de puffs.
AJUSTES = {
    "U-LEV": {"k": 300, "paso": 0.5},             # ±0,25 m/s
    "V-LEV": {"k": 300, "paso": 0.5},
    "WFACE": {"k": 150, "paso": 0.05},            # ±0,025 m/s
    "T-LEV": {"k": 150, "paso": 1.0},             # ±0,5 K
    "EL": {"k": 400, "paso": 0.2, "l0": 0.01},    # ±10 % de L
    "USTAR": {"k": 100, "paso": 0.02},            # ±0,01 m/s
    "ZI": {"k": 100, "paso": 50.0},               # ±25 m
    "WSTAR": {"k": 100, "paso": 0.02},            # ±0,01 m/s
    "TEMPK": {"k": 100, "paso": 0.2},             # ±0,1 K
    "RHO": {"k": 25, "paso": 0.002},              # ±0,001 kg/m³
    "QSW": {"k": 10, "paso": 2.0},                # ±1 W/m²
    "IRH": {"k": 25, "paso": 5.0},                # ±3 % (entera)
}
_PASOS_Q, _CENTRO = 65000.0, 32500


# ── utilidades ──────────────────────────────────────────────────────────────────────────────────────────────
def _empaquetar(**arrays):
    b = io.BytesIO()
    np.savez(b, **arrays)
    return lzma.compress(b.getvalue(), preset=PRESET)


def _desempaquetar(datos):
    with np.load(io.BytesIO(lzma.decompress(datos))) as z:
        return {k: z[k] for k in z.files}


def _capa(etiqueta):
    """«U-LEV 12» -> 12; un campo 2D -> 1."""
    resto = etiqueta[len(almacen._nombre(etiqueta)):].strip()
    return int(resto) if resto.isdigit() else 1


def _fichero_var(nombre):
    return nombre.replace("-", "")


def _cuantizar(a, eje):
    """int16 con mínimo y escala por fila (eje=1) o por columna (eje=0), como `almacen`."""
    lo = a.min(axis=eje).astype(np.float64)
    esc = (a.max(axis=eje) - lo) / _PASOS_Q
    esc = np.where(esc > 0, esc, 1.0)
    forma = (-1, 1) if eje == 1 else (1, -1)
    q = np.round((a - lo.reshape(forma)) / esc.reshape(forma)) - _CENTRO
    return q.astype(np.int16), lo, esc


def _descuantizar(q, lo, esc, eje):
    forma = (-1, 1) if eje == 1 else (1, -1)
    return ((q.astype(np.float64) + _CENTRO) * esc.reshape(forma) + lo.reshape(forma)).astype(np.float32)


def _rsvd(X, k, extra=20, potencias=2, semilla=0):
    """Los k modos espaciales principales de X (horas, celdas), ya centrada: SVD aleatorizada (Halko et al. 2011)."""
    n = min(k + extra, *X.shape)
    O = np.random.default_rng(semilla).standard_normal((X.shape[1], n), dtype=np.float32)
    Q, _ = np.linalg.qr(X @ O)
    for _ in range(potencias):
        Q, _ = np.linalg.qr(X.T @ Q)
        Q, _ = np.linalg.qr(X @ Q)
    _, _, Vt = np.linalg.svd(Q.T @ X, full_matrices=False)
    return np.ascontiguousarray(Vt[:min(k, n)].T, dtype=np.float32)          # (celdas, k)


def _indice_cmz(ruta):
    with zipfile.ZipFile(ruta) as z:
        return json.loads(z.read("indice.json"))


# ── construir ───────────────────────────────────────────────────────────────────────────────────────────────
def construir(cmzs, destino, serie, casos=None, ajustes=None, avisa=print):
    """Paquete de los .cmz `cmzs` ({(año, mes): ruta}) en la carpeta `destino`. `casos` ({(año, mes): ruta de su
    caso.json}) va dentro, para leer la malla sin la carpeta de cálculos. `ajustes` cambia los de AJUSTES por
    variable. Devuelve el índice (con los errores medidos)."""
    destino = Path(destino)
    (destino / "bases").mkdir(parents=True, exist_ok=True)
    meses = sorted(cmzs)
    ind0 = _indice_cmz(cmzs[meses[0]])
    nxy = ind0["nx"] * ind0["ny"]
    aj = {n: {**AJUSTES.get(n, {}), **(ajustes or {}).get(n, {})} for n in {**AJUSTES, **(ajustes or {})}}
    etiquetas = {}
    for etq in ind0["variables"]:
        n = almacen._nombre(etq)
        if n in aj and ind0["variables"][etq]["horas"] > 1:
            etiquetas.setdefault(n, []).append(etq)
    for n in etiquetas:
        etiquetas[n].sort(key=_capa)
    indice = {"formato": FORMATO, "serie": serie, "nx": ind0["nx"], "ny": ind0["ny"],
              "meses": [f"{a}{m:02d}" for a, m in meses], "variables": {},
              "creado": time.strftime("%Y-%m-%d %H:%M")}
    por_mes = {m: {} for m in meses}
    for nom, etqs in etiquetas.items():
        a = aj[nom]
        t0 = time.time()
        horas = [_indice_cmz(cmzs[m])["variables"][etqs[0]]["horas"] for m in meses]
        X = np.empty((sum(horas), len(etqs) * nxy), np.float32)           # una sola copia: 33 GB con U de 5 años
        i0 = 0
        for m, h in zip(meses, horas):
            for c, e in enumerate(etqs):
                X[i0:i0 + h, c * nxy:(c + 1) * nxy] = almacen.leer_campo(cmzs[m], e)[1].reshape(h, nxy)
            i0 += h
        if "l0" in a:
            np.arcsinh(X / np.float32(a["l0"]), out=X)
        media = X.mean(0, dtype=np.float64).astype(np.float32)
        X -= media
        modos = _rsvd(X, a["k"])
        k = modos.shape[1]
        mq, mlo, mesc = _cuantizar(modos.T, eje=1)                  # (k, celdas)
        P = _descuantizar(mq, mlo, mesc, eje=1)
        del modos
        Ginv = np.linalg.inv(P.astype(np.float64) @ P.T.astype(np.float64))
        bases = []
        for c in range(len(etqs)):
            sl = slice(c * nxy, (c + 1) * nxy)
            f = f"bases/{_fichero_var(nom)}_{c + 1:02d}.xz"
            (destino / f).write_bytes(_empaquetar(modos=mq[:, sl], lo=mlo, esc=mesc, media=media[sl]))
            bases.append(f)
        paso = float(a["paso"])
        tot = {"sse_pod": 0.0, "sse": 0.0, "max_pod": 0.0, "max": 0.0, "ncorr": 0, "n": 0}
        i0 = 0
        for m, h in zip(meses, horas):
            por_mes[m][nom], e = _mes_pod(X[i0:i0 + h], P, Ginv, paso)
            i0 += h
            for c in tot:
                tot[c] = max(tot[c], e[c]) if c.startswith("max") else tot[c] + e[c]
        del X
        indice["variables"][nom] = {
            "capas": len(etqs), "etiquetas": etqs, "k": k, "paso": paso, "l0": a.get("l0"),
            "entero": nom in almacen.ENTEROS, "bases": bases,
            "errores": {"rmse_pod": (tot["sse_pod"] / tot["n"]) ** 0.5, "max_pod": tot["max_pod"],
                        "rmse": (tot["sse"] / tot["n"]) ** 0.5, "max": tot["max"], "correcciones": tot["ncorr"] / tot["n"],
                        "unidades": "asinh(L/L0)" if "l0" in a else "las de la variable"}}
        if avisa:
            e = indice["variables"][nom]["errores"]
            avisa(f"{nom}: {len(etqs)} capa(s), {sum(horas)} h, {k} modos · RMSE {e['rmse_pod']:.4g} → {e['rmse']:.4g} · "
                  f"máx {e['max_pod']:.4g} → {e['max']:.4g} · correcciones {e['correcciones']:.3%} · "
                  f"{time.time() - t0:.0f} s")
    for m in meses:
        _escribir_mes(destino / f"{m[0]}{m[1]:02d}.vz", cmzs[m], por_mes[m], etiquetas,
                      (casos or {}).get(m))
    (destino / "indice.json").write_text(json.dumps(indice, indent=1), encoding="utf-8")
    _indice.cache_clear()
    return indice


def _mes_pod(Xm, P, Ginv, paso):
    """Un mes de una variable (Xm: horas × celdas, ya transformada y sin la media) con los modos P: (lo que se guarda, errores
    {"sse_pod", "sse", "max_pod", "max", "ncorr", "n"}). Coeficientes por proyección, cuantizados por modo; la corrección,
    donde el resto pasa de paso / 2."""
    A = ((Xm @ P.T).astype(np.float64) @ Ginv).astype(np.float32)
    aq, alo, aesc = _cuantizar(A, eje=0)                             # escala por modo
    R = Xm - _descuantizar(aq, alo, aesc, eje=0) @ P
    c = np.round(R / paso)
    idx = np.flatnonzero(c)
    val = c.ravel()[idx]
    fin = R - c * paso
    e = {"sse_pod": float(np.sum(R.astype(np.float64) ** 2)), "sse": float(np.sum(fin.astype(np.float64) ** 2)),
         "max_pod": float(np.abs(R).max()), "max": float(np.abs(fin).max()), "ncorr": int(idx.size), "n": int(R.size)}
    return _empaquetar(coef=aq, lo=alo, esc=aesc, salto=np.diff(idx, prepend=0).astype(np.uint32),
                       valor=np.clip(val, -32767, 32767).astype(np.int16)), e


def anadir(cmzs, destino, casos=None, avisa=print):
    """Añade (o rehace) meses en un paquete ya hecho, con SUS patrones: no se vuelven a calcular. `cmzs`, {(año, mes): ruta del
    .cmz}; `casos`, como en `construir`. El error sigue acotado por la corrección (paso / 2): un mes que no se parezca a los de
    las bases solo lleva más correcciones y pesa más (lo dice `errores_meses` del índice). Devuelve el índice."""
    destino = Path(destino)
    indice = json.loads((destino / "indice.json").read_text(encoding="utf-8"))
    meses = sorted(cmzs)
    for m in meses:
        i = _indice_cmz(cmzs[m])
        if (i["nx"], i["ny"]) != (indice["nx"], indice["ny"]):
            raise ValueError(f"{cmzs[m]}: malla {i['nx']}×{i['ny']}, y el paquete es de {indice['nx']}×{indice['ny']}")
    nxy = indice["nx"] * indice["ny"]
    por_mes = {m: {} for m in meses}
    etiquetas = {}
    for nom, v in indice["variables"].items():
        t0 = time.time()
        etiquetas[nom] = v["etiquetas"]
        b = [_desempaquetar((destino / f).read_bytes()) for f in v["bases"]]
        P = _descuantizar(np.concatenate([x["modos"] for x in b], axis=1), b[0]["lo"], b[0]["esc"], eje=1)
        media = np.concatenate([x["media"] for x in b])
        Ginv = np.linalg.inv(P.astype(np.float64) @ P.T.astype(np.float64))
        for m in meses:
            Xm = np.concatenate([almacen.leer_campo(cmzs[m], e)[1].reshape(-1, nxy) for e in v["etiquetas"]],
                                axis=1).astype(np.float32)
            if v.get("l0"):
                np.arcsinh(Xm / np.float32(v["l0"]), out=Xm)
            por_mes[m][nom], e = _mes_pod(Xm - media, P, Ginv, v["paso"])
            v.setdefault("errores_meses", {})[f"{m[0]}{m[1]:02d}"] = {
                "rmse": (e["sse"] / e["n"]) ** 0.5, "max": e["max"], "correcciones": e["ncorr"] / e["n"]}
        if avisa:
            avisa(f"{nom}: {len(meses)} mes(es) con los {v['k']} modos de las bases · {time.time() - t0:.0f} s")
    for m in meses:
        _escribir_mes(destino / f"{m[0]}{m[1]:02d}.vz", cmzs[m], por_mes[m], etiquetas, (casos or {}).get(m))
    indice["meses"] = sorted(set(indice["meses"]) | {f"{a}{m:02d}" for a, m in meses})
    (destino / "indice.json").write_text(json.dumps(indice, indent=1), encoding="utf-8")
    _indice.cache_clear()
    return indice


def _escribir_mes(ruta, cmz, pods, etiquetas, caso):
    capas = {e: (n, c) for n, etqs in etiquetas.items() for c, e in enumerate(etqs)}
    with zipfile.ZipFile(cmz) as z, zipfile.ZipFile(ruta, "w", zipfile.ZIP_STORED) as s:
        ind = json.loads(z.read("indice.json"))
        s.writestr("cabeceras.z", z.read("cabeceras.z"))
        for etq, meta in ind["variables"].items():
            s.writestr(meta["fechas"], z.read(meta["fechas"]))
            if etq in capas:
                n, c = capas[etq]
                ind["variables"][etq] = {"tipo": "pod", "pod": n, "capa": c, "horas": meta["horas"],
                                         "fechas": meta["fechas"]}
            else:                                                           # tal cual, pero con lzma en vez de zlib
                s.writestr(meta["fichero"], lzma.compress(zlib.decompress(z.read(meta["fichero"])), preset=PRESET))
        for n, datos in pods.items():
            s.writestr(f"pod/{_fichero_var(n)}.xz", datos)
        if caso:
            s.writestr("caso.json", Path(caso).read_bytes())
        s.writestr("indice.xz", lzma.compress(json.dumps(ind).encode("utf-8"), preset=PRESET))


# ── leer ────────────────────────────────────────────────────────────────────────────────────────────────────
@lru_cache(maxsize=4)
def _indice(paquete):
    return json.loads((Path(paquete) / "indice.json").read_text(encoding="utf-8"))


def es_paquete(carpeta):
    return (Path(carpeta) / "indice.json").is_file()


def serie(paquete):
    """Nombre de la serie de viento que lleva el paquete."""
    return _indice(str(paquete))["serie"]


def meses(paquete):
    """[(año, mes)] del paquete."""
    return [(int(m[:4]), int(m[4:])) for m in _indice(str(paquete))["meses"]]


def _ruta_mes(paquete, anio, mes):
    r = Path(paquete) / f"{anio}{mes:02d}.vz"
    if not r.is_file():
        raise FileNotFoundError(f"El paquete de viento {paquete} no tiene {anio}-{mes:02d}")
    return r


def caso(paquete, anio, mes):
    """El caso.json del mes (dict), o None si el paquete no lo lleva."""
    with zipfile.ZipFile(_ruta_mes(paquete, anio, mes)) as z:
        return json.loads(z.read("caso.json")) if "caso.json" in z.namelist() else None


@lru_cache(maxsize=64)
def _base(paquete, nom, capa):
    """(modos (k, nx·ny) float32, media (nx·ny,)) de una capa (desde 1)."""
    v = _indice(paquete)["variables"][nom]
    d = _desempaquetar((Path(paquete) / v["bases"][capa - 1]).read_bytes())
    return _descuantizar(d["modos"], d["lo"], d["esc"], eje=1), d["media"]


class _Variable:
    """Una variable POD de un mes: coeficientes y correcciones, para reconstruir capas y bloques de horas."""

    def __init__(self, paquete, z, nom):
        self.paquete, self.nom = paquete, nom
        self.v = _indice(paquete)["variables"][nom]
        d = _desempaquetar(z.read(f"pod/{_fichero_var(nom)}.xz"))
        self.A = _descuantizar(d["coef"], d["lo"], d["esc"], eje=0)                # (horas, k)
        self.h = self.A.shape[0]
        nxy = _indice(paquete)["nx"] * _indice(paquete)["ny"]
        self.nxy = nxy
        idx = np.cumsum(d["salto"].astype(np.int64))
        self.t, self.col = idx // (nxy * self.v["capas"]), idx % (nxy * self.v["capas"])
        self.val = d["valor"].astype(np.float32) * np.float32(self.v["paso"])

    def _acabar(self, Y):
        if self.v.get("l0"):
            Y = np.float32(self.v["l0"]) * np.sinh(Y)
        if self.v["entero"]:
            return np.round(Y).astype("<i4")
        return Y.astype("<f4")

    def capa(self, c, t0=0, t1=None):
        """Valores (horas t0..t1, nx·ny) de la capa c (desde 1)."""
        t1 = self.h if t1 is None else t1
        P, media = _base(self.paquete, self.nom, c)
        Y = self.A[t0:t1] @ P + media
        lo, hi = (c - 1) * self.nxy, c * self.nxy
        i0, i1 = np.searchsorted(self.t, [t0, t1])
        sel = slice(i0, i1)
        m = (self.col[sel] >= lo) & (self.col[sel] < hi)
        np.add.at(Y, (self.t[sel][m] - t0, self.col[sel][m] - lo), self.val[sel][m])
        return self._acabar(Y)


def _decodificar(meta, datos, nxy):
    """Un campo copiado del .cmz (como `almacen.descomprimir`): (horas, nx·ny)."""
    h = meta["horas"]
    datos = lzma.decompress(datos)
    if meta["tipo"] in ("i4", "f4"):
        return almacen._desbarajar(datos, "<" + meta["tipo"], h * nxy).reshape(h, nxy)
    d = almacen._desbarajar(datos, "<i2", h * nxy).reshape(h, nxy).astype(np.int32)
    q = (np.cumsum(d, axis=0) if meta["delta"] else d) + 32500
    return (q.astype(np.float64) * meta["esc"] + meta["lo"]).astype("<f4")


def _fechas(z, meta):
    return np.cumsum(np.frombuffer(zlib.decompress(z.read(meta["fechas"])), "<i4")).astype(np.int32)


def leer_campo(paquete, anio, mes, etiqueta):
    """Una variable de un mes, como `almacen.leer_campo`: (fechas AAAAJJJHH int32, valores (horas, ny, nx))."""
    paquete = str(paquete)
    ind = _indice(paquete)
    with zipfile.ZipFile(_ruta_mes(paquete, anio, mes)) as z:
        im = json.loads(lzma.decompress(z.read("indice.xz")))
        meta = im["variables"][etiqueta]
        fz = _fechas(z, meta)
        if meta["tipo"] == "pod":
            a = _Variable(paquete, z, meta["pod"]).capa(meta["capa"] + 1)
        else:
            a = _decodificar(meta, z.read(meta["fichero"]), ind["nx"] * ind["ny"])
    return fz, a.astype(np.float32).reshape(-1, ind["ny"], ind["nx"])


def descomprimir(paquete, anio, mes, destino):
    """Mes del paquete -> fichero de viento con la misma secuencia de registros que el .cmz del que salió."""
    paquete = str(paquete)
    ind = _indice(paquete)
    nxy = ind["nx"] * ind["ny"]
    with zipfile.ZipFile(_ruta_mes(paquete, anio, mes)) as z:
        im = json.loads(lzma.decompress(z.read("indice.xz")))
        cab_raw = zlib.decompress(z.read("cabeceras.z"))
        cabeceras, i = [], 0
        while i < len(cab_raw):
            n = struct.unpack_from("<i", cab_raw, i)[0]
            cabeceras.append(cab_raw[i + 4:i + 4 + n])
            i += 4 + n
        fechas = {etq: _fechas(z, meta) for etq, meta in im["variables"].items()}
        fijos = {etq: _decodificar(meta, z.read(meta["fichero"]), nxy)
                 for etq, meta in im["variables"].items() if meta["tipo"] != "pod"}
        pods = {n: _Variable(paquete, z, n) for n in {m["pod"] for m in im["variables"].values() if m["tipo"] == "pod"}}
    bloques = {}                                          # (variable, capa) -> (t0, valores del bloque)

    def valor(etq, k):
        meta = im["variables"][etq]
        if meta["tipo"] != "pod":
            return fijos[etq][k]
        clave, t0 = (meta["pod"], meta["capa"]), (k // BLOQUE_H) * BLOQUE_H
        if clave not in bloques or bloques[clave][0] != t0:
            var = pods[meta["pod"]]
            bloques[clave] = (t0, var.capa(meta["capa"] + 1, t0, min(t0 + BLOQUE_H, var.h)))
        return bloques[clave][1][k - t0]

    usados = {}
    destino = Path(destino)
    with open(destino, "wb") as f:
        for item in im["orden"]:
            if isinstance(item, int):
                b = cabeceras[item]
            else:
                k = usados.get(item, 0)
                usados[item] = k + 1
                b = item.encode("latin-1") + struct.pack("<i", int(fechas[item][k])) + valor(item, k).tobytes()
            n = struct.pack("<i", len(b))
            f.write(n + b + n)
    return destino
