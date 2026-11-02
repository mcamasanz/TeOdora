# -*- coding: utf-8 -*-
"""Prueba 01 · SUPERPOSICIÓN para el alcance 1.

Pregunta: con varios focos (áreas y una chimenea), cada uno con su perfil de 24 h y con olor y un
gas, ¿da lo MISMO
  A) calcular directamente el escenario (todos los focos y especies con sus perfiles), que
  B) calcular UNA vez, por foco, la respuesta a una emisión unitaria emitida en cada hora del día
     (24 «especies» de cálculo H00…H23, cada una solo en su hora) y combinarlas:
        C_esp(t, r) = Σ_foco Σ_h  q(foco, esp) · perfil(foco)[h] · R(foco, h)(t, r) ?
Y ¿cuánto cuestan las corridas de 24 especies frente a la de una (tiempo y memoria)?

Datos: el viento 3D de 48 h que hay en local (serie odora_gfs_8est, 2026-10-20/21) y la malla de
receptores de la planta (sin las viviendas del Catastro, que están en Z:). Periodo: desde las 06
del 20 (como penacho_dia) 42 horas. Los focos son INVENTADOS (aún no hay los de ENCE).

    C:\\e2s\\python.exe 99-Test\\01_superposicion\\prueba_superposicion.py
Resultados: resultados.json y resultados.md junto a este script; casos en
%TEMP%\\ence_galera\\99-Test\\01_superposicion.
"""
import json
import os
import subprocess
import sys
import time
from pathlib import Path

AQUI = Path(__file__).resolve().parent
RAIZ = AQUI.parents[1]
os.environ.setdefault("ENCE_GALERA_DATOS", str(Path(os.environ["TEMP"]) / "ence_galera" / "datos_local"))
CARGADOR = RAIZ.parent / (RAIZ / "VERSION").read_text(encoding="utf-8").strip() / "cargador"
sys.path[:0] = [str(CARGADOR), str(AQUI)]
from teodors import planta as _planta  # noqa: E402
_planta.activar(RAIZ / "entrada")
_planta.actual().DIR_PLANES = _planta.DATOS / "escenarios"      # los planes de las pruebas, con la copia de los datos: nunca en la carpeta de la planta
sys.stdout.reconfigure(encoding="utf-8")

import numpy as np  # noqa: E402
import pandas as pd  # noqa: E402
import psutil  # noqa: E402

import control_multiple as cm  # noqa: E402
from teodors.planta import geo  # noqa: E402
from teodors.fuentes import terreno  # noqa: E402
from teodors import planta as config  # noqa: E402
from teodors.casos import receptores as receptores_mapa  # noqa: E402
from teodors.meteo.viento3d import almacen  # noqa: E402
from teodors.preparacion.puffs import salida  # noqa: E402

SERIE, MES = "odora_gfs_8est", "202610"
INI, NHORAS = pd.Timestamp("2026-10-20 06:00"), 42
TRABAJO = config.LOCAL / "99-Test" / "01_superposicion"
ESPECIES = ["OLOR", "NH3"]                      # olor en ou_E, NH3 en g
HORAS = ["H%02d" % h for h in range(24)]       # especies de cálculo: emisión unitaria en la hora h


def perfil(activas, resto):
    """24 factores: 1 en las horas `activas`, `resto` en las demás."""
    return [1.0 if h in activas else resto for h in range(24)]


def focos(xp, yp, cota):
    """Tres focos de prueba alrededor de la planta (inventados)."""
    def rect(x0, y0, lx, ly):
        return [(x0, y0), (x0 + lx, y0), (x0 + lx, y0 + ly), (x0, y0 + ly)]
    pilas = {"id": "PILAS", "verts": rect(xp - 110, yp + 30, 60.0, 12.0), "h": 2.5,
             "q": {"OLOR": 3.0, "NH3": 2.0e-5},                     # por m²
             "perfil": perfil({8, 9, 15, 16}, 0.2)}                 # volteos 08-10 y 15-17
    biofiltro = {"id": "BIOFILTRO", "verts": rect(xp + 40, yp - 50, 30.0, 20.0), "h": 1.0,
                 "q": {"OLOR": 1.5, "NH3": 1.0e-6},
                 "perfil": perfil(set(range(6, 22)), 0.5)}         # ventilación de día
    chimenea = {"id": "CHIMENEA", "x": xp + 20.0, "y": yp + 60.0, "h": 12.0, "d": 0.5, "w": 10.0,
                "t": 400.0, "q": {"OLOR": 2000.0, "NH3": 0.01},     # por segundo
                "perfil": None}                                     # constante
    for a in (pilas, biofiltro):
        cx, cy = np.mean(a["verts"], axis=0)
        a["cota"] = cota(cx, cy)
    chimenea["cota"] = cota(chimenea["x"], chimenea["y"])
    return [pilas, biofiltro], [chimenea]


def correr(nombre, malla, zona, especies, areas, puntos, recs):
    """Escribe el control y lanza teOdors puffs en un proceso aparte; mide tiempo y memoria máxima."""
    nom = {"viento": "viento3d.dat", "listado": nombre + ".lst", "concentraciones": nombre + ".dat"}
    for f in areas + puntos:                     # perfiles por especie (todas con el del foco)
        if f.get("perfil") is not None and not isinstance(f["perfil"], dict):
            f["perfil"] = {e: f["perfil"] for e in especies}
    cm.escribir(TRABAJO / (nombre + ".inp"), malla, config.VIENTO3D_ZFACE, INI, NHORAS, zona,
                especies, areas, puntos, recs, nombres=nom)
    env = dict(os.environ, PYTHONPATH=str(CARGADOR), PYTHONIOENCODING="utf-8")
    t0 = time.time()
    with open(TRABAJO / (nombre + ".log"), "w", errors="replace") as fo:
        pr = subprocess.Popen([sys.executable, "-m", "teodors", "puffs", nombre + ".inp"], cwd=str(TRABAJO),
                              stdout=fo, stderr=subprocess.STDOUT, env=env)
        ps, pico = psutil.Process(pr.pid), 0
        while pr.poll() is None:
            try:
                pico = max(pico, ps.memory_info().rss)
            except psutil.Error:
                pass
            time.sleep(0.2)
    seg = time.time() - t0
    if pr.returncode != 0:
        raise RuntimeError(nombre + ": " + (TRABAJO / (nombre + ".log")).read_text(errors="replace")[-1500:])
    conc = {e: salida.concentraciones(TRABAJO / (nombre + ".dat"), especie=e)[1] for e in especies}
    fines = salida.concentraciones(TRABAJO / (nombre + ".dat"))[0]
    print(f"  {nombre:24s} {len(especies):2d} especies · {len(areas) + len(puntos)} focos · {seg:6.1f} s · "
          f"memoria máx. {pico / 1e6:6.0f} MB", flush=True)
    return {"segundos": seg, "memoria_mb": pico / 1e6, "conc": conc, "fines": fines}


def main():
    TRABAJO.mkdir(parents=True, exist_ok=True)
    base = config.DIR_VIENTO3D / SERIE
    if not (TRABAJO / "viento3d.dat").exists():
        almacen.descomprimir(base / "cmz" / f"{MES}.cmz", TRABAJO / "viento3d.dat")
    info = json.loads((base / MES / "caso.json").read_text(encoding="utf-8"))
    malla = {k: info[k] for k in ("nx", "ny", "celda_m", "ext")}
    emp = config.cargar_emplazamiento()
    xp, yp = geo.a_utm(emp["lat"], emp["lon"])
    t_inf = terreno.ultimo_caso(emp["lat"], emp["lon"])
    Z, U, tr = terreno.cargar(t_inf)

    def cota(x, y):
        f = int((tr.f - y) / -tr.e)
        c = int((x - tr.c) / tr.a)
        return float(max(Z[min(max(f, 0), Z.shape[0] - 1), min(max(c, 0), Z.shape[1] - 1)], 0.0))

    res = terreno.resumen(Z, U, tr, emp["lat"], emp["lon"])
    malla_r = receptores_mapa.malla(res["nucleos"], None)
    recs = [(x, y, cota(x, y)) for x, y, _ in malla_r]
    areas, puntos = focos(xp, yp, cota)
    print(f"{len(recs)} receptores · {NHORAS} h desde {INI:%d/%m %H:%M} · focos: "
          + ", ".join(f["id"] for f in areas + puntos), flush=True)

    # A) escenario directo: los tres focos, olor y NH3, cada foco con su perfil
    A = correr("A_directo", malla, info["zona"], ESPECIES, [dict(a) for a in areas],
               [dict(p) for p in puntos], recs)
    # B) respuestas unitarias por foco y hora de emisión (24 especies de cálculo)
    unos = [[1.0 if k == h else 0.0 for k in range(24)] for h in range(24)]
    R, costes = {}, {}
    for f in areas + puntos:
        g = dict(f, q={e: 1.0 for e in HORAS}, perfil={e: unos[h] for h, e in enumerate(HORAS)})
        es_area = "verts" in f
        R[f["id"]] = correr("B_" + f["id"], malla, info["zona"], HORAS, [g] if es_area else [],
                            [] if es_area else [g], recs)
        # C) referencia de coste: el mismo foco con UNA especie y emisión constante
        u = dict(f, q={"UNO": 1.0}, perfil=None)
        costes[f["id"]] = correr("C_" + f["id"] + "_1esp", malla, info["zona"], ["UNO"],
                                 [u] if es_area else [], [] if es_area else [u], recs)
    # combinación
    comp = {}
    for e in ESPECIES:
        S = np.zeros_like(A["conc"][e])
        for f in areas + puntos:
            pf = f.get("perfil")
            p = (pf[e] if isinstance(pf, dict) else pf) if pf else [1.0] * 24
            for h in range(24):
                S += f["q"][e] * p[h] * R[f["id"]]["conc"][HORAS[h]]
        Ae = A["conc"][e]
        tope = float(Ae.max())
        dif = np.abs(S - Ae)
        rel = dif / np.maximum(np.abs(Ae), tope * 1e-6)
        comp[e] = {"max_directo": tope, "max_dif_abs": float(dif.max()),
                   "max_dif_rel_al_maximo": float(dif.max() / tope) if tope else 0.0,
                   "p99_dif_rel_por_valor": float(np.percentile(rel, 99)),
                   "receptor_horas_con_dif_rel_>1e-4": int((rel > 1e-4).sum()),
                   "receptor_horas": int(Ae.size),
                   "media_directo": float(Ae.mean()), "media_superposicion": float(S.mean()),
                   "maximo_por_receptor_igual_1e-4": bool(np.allclose(S.max(0), Ae.max(0), rtol=1e-4, atol=tope * 1e-9))}
        print(f"  {e}: máx {tope:.4g} · |Δ| máx {dif.max():.3g} ({dif.max() / tope:.2e} del máximo) · "
              f"receptor·horas con |Δ|/valor > 1e-4: {comp[e]['receptor_horas_con_dif_rel_>1e-4']} de {Ae.size}",
              flush=True)
    # suma de las 24 horas = emisión constante (comprobación del truco por foco)
    trucos = {}
    for f in areas + puntos:
        suma = sum(R[f["id"]]["conc"][h] for h in HORAS)
        uno = costes[f["id"]]["conc"]["UNO"]
        trucos[f["id"]] = float(np.abs(suma - uno).max() / uno.max()) if uno.max() else 0.0
    out = {"fecha": time.strftime("%Y-%m-%d %H:%M"), "receptores": len(recs), "horas": NHORAS,
           "inicio": str(INI), "focos": [{k: v for k, v in f.items() if k not in ("verts",)} for f in areas + puntos],
           "comparacion": comp, "suma_24h_frente_a_constante_dif_rel": trucos,
           "coste": {"A_directo": {"segundos": A["segundos"], "memoria_mb": A["memoria_mb"]},
                     **{"B_" + k: {"segundos": v["segundos"], "memoria_mb": v["memoria_mb"]} for k, v in R.items()},
                     **{"C_" + k + "_1esp": {"segundos": v["segundos"], "memoria_mb": v["memoria_mb"]}
                        for k, v in costes.items()}}}
    (AQUI / "resultados.json").write_text(json.dumps(out, indent=1, ensure_ascii=False, default=float),
                                          encoding="utf-8")
    print("resultados →", AQUI / "resultados.json", flush=True)


if __name__ == "__main__":
    main()
