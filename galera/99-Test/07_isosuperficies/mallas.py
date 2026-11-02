# -*- coding: utf-8 -*-
"""De las corridas a las mallas de la vista: isosuperficies por hora y nivel, terreno y rótulos.

Cada hora sale de fino_HH.npz (afinar.py) si existe y, si no, de la corrida «vol». Las superficies se sacan del logaritmo
de la concentración sobre una rejilla estructurada que sigue el terreno (cota + altura sobre el suelo). Coordenadas
respecto al centro, en m: x = este, y = norte, z = cota real.

    python mallas.py [--grueso]   →  %TEMP%/ence_galera/99-Test/07_isosuperficies/mallas_<nombre>.json
"""
import argparse
import base64
import json
import sys
import time

import comun as K
import numpy as np
import pyvista as pv
from pyproj import Transformer

sys.stdout.reconfigure(encoding="utf-8")
a = argparse.ArgumentParser()
a.add_argument("--niveles", default="1,3,5")
a.add_argument("--semilado", type=float, default=3200.0)
a.add_argument("--grueso", action="store_true", help="solo la corrida de 100 m")
a.add_argument("--nombre", default=None)
a.add_argument("--origen", default="vol", help="corrida de partida (chim_caliente_30: chimenea.py)")
A = a.parse_args()
NIVELES = [float(x) for x in A.niveles.split(",")]
ESCALA_M = 0.25
NOMBRE = A.nombre or ("grueso" if A.grueso else "fino")
d = np.load(K.TRABAJO / f"{A.origen}.npz")
xc, yc = K.CENTRO
b64 = lambda v: base64.b64encode(v.tobytes()).decode()
_rejillas = {}


def rejilla(xs, ys, Z):
    """Rejilla estructurada que sigue el terreno, una por paso."""
    clave = (len(xs), len(ys), len(Z))
    if clave not in _rejillas:
        cotas = np.array([[K.cota(float(x), float(y)) for x in xs] for y in ys])
        Xg = np.broadcast_to((xs - xc)[None, :, None], (len(ys), len(xs), len(Z)))
        Yg = np.broadcast_to((ys - yc)[:, None, None], (len(ys), len(xs), len(Z)))
        Zg = cotas[:, :, None] + Z[None, None, :]
        _rejillas[clave] = pv.StructuredGrid(Xg.transpose(1, 0, 2).astype(float), Yg.transpose(1, 0, 2).astype(float),
                                             Zg.transpose(1, 0, 2).astype(float))
    return _rejillas[clave]


def espesores(Z):
    """Espesor que le toca a cada altura (trapecios)."""
    e = np.zeros(len(Z))
    e[1:] += np.diff(Z) / 2
    e[:-1] += np.diff(Z) / 2
    return e


horas, tabla = {}, []
t_mallas = 0.0
fines = [str(f) for f in d["fines"]]
for H in range(24):
    f = K.TRABAJO / f"fino_{H:02d}.npz"
    if f.is_file() and not A.grueso:
        z = np.load(f)
        campo, xs, ys, Z = z["C"], z["x"], z["y"], z["alturas"]
    else:
        campo, xs, ys, Z = d["C"][fines.index(f"2026-10-21 {H:02d}:00")], d["x"], d["y"], d["alturas"]
    paso = float(xs[1] - xs[0])
    malla = rejilla(xs, ys, Z)
    malla["c"] = np.log10(np.maximum(campo, 1e-3)).transpose(2, 1, 0).ravel(order="F")
    salida = {}
    fila = {"fin_utc": H, "paso_m": paso, "maximo": round(float(campo.max()), 1), "maximo_suelo": round(float(campo[0].max()), 1)}
    t0 = time.time()
    tri = 0
    for nv in NIVELES:
        s = malla.contour(isosurfaces=[float(np.log10(nv))], scalars="c", method="contour").clean().triangulate()
        if s.n_points == 0:
            continue
        ind = np.asarray(s.faces, np.uint32).reshape(-1, 4)[:, 1:]
        if s.n_points >= 65536:
            raise RuntimeError(f"{s.n_points} vértices no caben en 16 bits")
        # posiciones en 16 bits, cada ESCALA_M: ±8 km y media página menos que con 32 bits
        salida[str(nv)] = {"p": b64(np.round(np.asarray(s.points) / ESCALA_M).astype("<i2")), "i": b64(ind.ravel().astype("<u2")),
                           "n": int(len(ind))}
        tri += len(ind)
    t_mallas += time.time() - t0
    nv = NIVELES[0]
    arriba = (campo >= nv).any(axis=(1, 2))
    planta = (campo >= nv).any(axis=0)
    X, Y = np.meshgrid(xs, ys)
    dist = np.hypot(X - xc, Y - yc)
    if planta.any():
        lejos = np.unravel_index(np.argmax(np.where(planta, dist, -1.0)), dist.shape)
        fila.update(altura_max_m=float(Z[arriba].max()), alcance_m=round(float(dist[lejos])),
                    rumbo_alcance=round(float((np.degrees(np.arctan2(X[lejos] - xc, Y[lejos] - yc)) + 360) % 360)),
                    area_suelo_km2=round(float((campo[0] >= nv).sum() * paso * paso / 1e6), 3),
                    volumen_Mm3=round(float(((campo >= nv) * espesores(Z)[:, None, None]).sum() * paso * paso / 1e6), 2),
                    toca_borde=bool(planta[0].any() or planta[-1].any() or planta[:, 0].any() or planta[:, -1].any()),
                    toca_techo=bool(arriba[-1]), triangulos=tri)
    horas[f"{H:02d}"] = salida
    tabla.append(fila)
    print(fila, flush=True)

# ── terreno ─────────────────────────────────────────────────────────────────────────────
PASO = 50.0
k = np.arange(-int(A.semilado / PASO), int(A.semilado / PASO) + 1) * PASO
cz = np.array([[K.cota(xc + float(u), yc + float(v)) for u in k] for v in k])
print(f"Terreno en la vista: {cz.min():.0f}-{cz.max():.0f} m, {len(k)}² puntos", flush=True)
# ── rótulos: planta, La Galera (coordenadas del pueblo, CLAUDE.md) y los núcleos con nombre de las respuestas de la app ──
meta = json.loads((K.REFERENCIA / "meta.json").read_text(encoding="utf-8"))
rec = np.load(K.REFERENCIA / "receptores.npz")
rotulos = [{"t": "Planta", "x": 0.0, "y": 0.0, "z": K.cota(xc, yc)}]
gx, gy = Transformer.from_crs("EPSG:4326", K.config.EPSG_UTM, always_xy=True).transform(0 + 27 / 60 + 48 / 3600, 40 + 40 / 60 + 54 / 3600)
rotulos.append({"t": "La Galera", "x": gx - xc, "y": gy - yc, "z": K.cota(gx, gy)})
vistos = {"Planta", "La Galera"}
for e in meta["etiquetas"]:
    x, y = float(rec["x"][e["i"]]) - xc, float(rec["y"][e["i"]]) - yc
    if max(abs(x), abs(y)) <= A.semilado and e["nombre"] not in vistos and e["clase"] == "nucleo":
        vistos.add(e["nombre"])
        rotulos.append({"t": e["nombre"], "x": x, "y": y, "z": float(rec["cota"][e["i"]])})
print("Rótulos:", [(r["t"], round(r["x"]), round(r["y"])) for r in rotulos], flush=True)
datos = {"niveles": NIVELES, "horas": horas, "alturas": [float(h) for h in Z], "escala_m": ESCALA_M,
         "terreno": {"n": len(k), "paso": PASO, "semilado": float(k[-1]), "z": b64(np.round(cz * 10).astype("<i2"))},
         "rotulos": rotulos, "serie": K.SERIE, "dia": "2026-10-21"}
ruta = K.TRABAJO / f"mallas_{NOMBRE}.json"
ruta.write_text(json.dumps(datos), encoding="utf-8")
por_hora = {h: sum(len(v["p"]) + len(v["i"]) for v in s.values()) for h, s in horas.items()}
res = {"tabla": tabla, "segundos_isosuperficies_24h": round(t_mallas, 2), "json_MB": round(ruta.stat().st_size / 1e6, 2),
       "base64_MB_por_hora_max": round(max(por_hora.values()) / 1e6, 3), "triangulos_total": sum(v["n"] for s in horas.values() for v in s.values())}
(K.AQUI / f"resultados_mallas_{NOMBRE}.json").write_text(json.dumps(res, ensure_ascii=False, indent=1), encoding="utf-8")
print({k: v for k, v in res.items() if k != "tabla"}, flush=True)
