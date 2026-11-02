# -*- coding: utf-8 -*-
"""Prueba 04 · MALLA MUY FINA CERCA DE LA PLANTA (propuesta del usuario, 2026-10-31).

Anidamiento propuesto: 5 m a ±100 m, 25 m a ±500 m, 50 m a ±1 km y el resto como hoy (100 m a
±2 km, 300 m a ±6 km, 700 m hasta el borde). Preguntas:
  1. ¿Cuántos receptores salen y cuánto cuesta (tiempo, memoria, valores que hay que guardar)?
  2. ¿Qué aporta cada nivel? Cada rejilla contiene a la siguiente más gruesa, así que en una sola
     corrida se puede comparar el valor calculado con el interpolado desde la rejilla gruesa.
  3. ¿El campo a 5 m es razonable o aparecen singularidades o cuentas de collar? (figuras)

Datos: viento de 48 h en local (serie odora_gfs_8est, 2026-10-20/21), 42 h desde las 06 del 20,
y los focos INVENTADOS de la prueba 01, cada uno por separado con una unidad de emisión (no los
13 de ejemplo de focos.json). Sin las viviendas del Catastro, para comparar con la prueba 01.

    C:\\e2s\\python.exe 99-Test\\04_malla_cercana\\prueba_malla.py
Resultados: resultados.json y figuras junto a este script; casos en
%TEMP%\\ence_galera\\99-Test\\04_malla_cercana.
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
sys.path[:0] = [str(CARGADOR), str(RAIZ / "99-Test" / "01_superposicion")]
from teodors import planta as _planta  # noqa: E402
_planta.activar(RAIZ / "entrada")
sys.stdout.reconfigure(encoding="utf-8")

import numpy as np  # noqa: E402
import pandas as pd  # noqa: E402
import psutil  # noqa: E402
from scipy.interpolate import RegularGridInterpolator as RGI  # noqa: E402

import control_multiple as cm  # noqa: E402
from teodors.planta import geo  # noqa: E402
from teodors.fuentes import terreno  # noqa: E402
from teodors import planta as config  # noqa: E402
from teodors.meteo.viento3d import almacen  # noqa: E402
from teodors.preparacion import receptores as rec  # noqa: E402
from teodors.preparacion.puffs import salida  # noqa: E402

SERIE, MES = "odora_gfs_8est", "202610"
INI, NHORAS = pd.Timestamp("2026-10-20 06:00"), 42
TRABAJO = config.LOCAL / "99-Test" / "04_malla_cercana"
# La malla que había el 2026-10-31 antes de esta prueba (fija: receptores_mapa ya cambió)
ACTUAL = (("fina", 100.0, 2000.0), ("media", 300.0, 6000.0), ("gruesa", 700.0, None))
PROPUESTA = (("n5", 5.0, 100.0), ("n25", 25.0, 500.0), ("n50", 50.0, 1000.0)) + ACTUAL
# (zona: semilado interior, semilado exterior, paso calculado, pasos gruesos con los que comparar)
ZONAS = ((0.0, 100.0, 5.0, (25.0, 50.0)), (100.0, 500.0, 25.0, (50.0, 100.0)),
         (500.0, 1000.0, 50.0, (100.0,)), (1000.0, 2000.0, 100.0, (300.0,)))


def focos(xp, yp, cota):
    """Los tres focos inventados de la prueba 01, con una unidad de emisión."""
    def rect(x0, y0, lx, ly):
        return [(x0, y0), (x0 + lx, y0), (x0 + lx, y0 + ly), (x0, y0 + ly)]
    pilas = {"id": "PILAS", "verts": rect(xp - 110, yp + 30, 60.0, 12.0), "h": 2.5,
             "q": {"UNO": 1.0 / 720.0}, "perfil": None}                  # 1 g/s en total
    biofiltro = {"id": "BIOFILTRO", "verts": rect(xp + 40, yp - 50, 30.0, 20.0), "h": 1.0,
                 "q": {"UNO": 1.0 / 600.0}, "perfil": None}
    chimenea = {"id": "CHIMENEA", "x": xp + 20.0, "y": yp + 60.0, "h": 12.0, "d": 0.5, "w": 10.0,
                "t": 400.0, "q": {"UNO": 1.0}, "perfil": None}
    for a in (pilas, biofiltro):
        cx, cy = np.mean(a["verts"], axis=0)
        a["cota"] = cota(cx, cy)
    chimenea["cota"] = cota(chimenea["x"], chimenea["y"])
    return [pilas, biofiltro, chimenea]


def correr(nombre, malla, zona, foco, recs):
    nom = {"viento": "viento3d.dat", "listado": nombre + ".lst", "concentraciones": nombre + ".dat"}
    es_area = "verts" in foco
    cm.escribir(TRABAJO / (nombre + ".inp"), malla, config.VIENTO3D_ZFACE, INI, NHORAS, zona, ["UNO"],
                [foco] if es_area else [], [] if es_area else [foco], recs, nombres=nom)
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
    C = salida.concentraciones(TRABAJO / (nombre + ".dat"), especie="UNO")[1]
    tam = (TRABAJO / (nombre + ".dat")).stat().st_size / 1e6
    print(f"  {nombre:24s} {len(recs):6d} receptores · {seg:6.1f} s · memoria {pico / 1e6:5.0f} MB · "
          f"{tam:6.1f} MB", flush=True)
    return {"segundos": seg, "memoria_mb": pico / 1e6, "fichero_mb": tam, "C": np.asarray(C)}


class Rejilla:
    """Acceso a los receptores por su posición relativa a la planta en una rejilla de paso dado."""

    def __init__(self, recs_xy, xp, yp):
        self.ind = {(round(x - xp, 1), round(y - yp, 1)): i for i, (x, y) in enumerate(recs_xy)}

    def indices(self, paso, semilado):
        n = int(round(semilado / paso))
        k = np.arange(-n, n + 1) * paso
        I = np.full((len(k), len(k)), -1, dtype=int)
        for j, yy in enumerate(k):
            for i, xx in enumerate(k):
                I[j, i] = self.ind.get((round(float(xx), 1), round(float(yy), 1)), -1)
        return k, I


def analiza(C, rej, foco, xp, yp):
    """Por zona: qué se pierde si en vez del paso calculado solo hubiera el grueso."""
    out = []
    media, maximo = C.mean(0), C.max(0)
    for r0, r1, paso, gruesos in ZONAS:
        kf, If = rej.indices(paso, r1)
        faltan = If < 0
        if faltan.any():
            raise RuntimeError(f"faltan {faltan.sum()} puntos en la rejilla de {paso} m a ±{r1} m")
        Y, X = np.meshgrid(kf, kf, indexing="ij")
        zona = (np.maximum(np.abs(X), np.abs(Y)) >= r0) & (np.maximum(np.abs(X), np.abs(Y)) <= r1)
        for g in gruesos:
            kg, Ig = rej.indices(g, r1)
            if (Ig < 0).any():
                raise RuntimeError(f"faltan puntos en la rejilla de {g} m a ±{r1} m")
            fila = {"zona_m": [r0, r1], "paso": paso, "grueso": g}
            hueco = zona & ~(np.isin(X, kg) & np.isin(Y, kg))         # solo los que faltarían
            for nom, campo in (("media", media), ("maximo", maximo)):
                F = campo[If]
                G = RGI((kg, kg), campo[Ig], bounds_error=False, fill_value=None)((Y, X))
                sel = hueco & (F > F[zona].max() * 1e-3) if F[zona].max() > 0 else hueco & False
                e = np.abs(G[sel] - F[sel]) / F[sel] if sel.any() else np.array([0.0])
                Yg, Xg = np.meshgrid(kg, kg, indexing="ij")
                zona_g = (np.maximum(np.abs(Xg), np.abs(Yg)) >= r0) & (np.maximum(np.abs(Xg), np.abs(Yg)) <= r1)
                pico_f, pico_g = float(F[zona].max()), float(campo[Ig][zona_g].max())
                fila[nom] = {"n": int(sel.sum()), "mediana_pct": float(np.median(e) * 100),
                             "p95_pct": float(np.percentile(e, 95) * 100), "pico_fino": pico_f,
                             "pico_grueso": pico_g,
                             "pico_perdido_pct": float(100 * (1 - pico_g / pico_f)) if pico_f > 0 else 0.0}
            # hora a hora: mediana de la mediana del error en cada hora con penacho en la zona
            eh = []
            for h in range(C.shape[0]):
                F = C[h][If]
                if F[zona].max() <= 0:
                    continue
                G = RGI((kg, kg), C[h][Ig], bounds_error=False, fill_value=None)((Y, X))
                sel = hueco & (F > F[zona].max() * 1e-3)
                if sel.sum() >= 3:
                    eh.append(np.median(np.abs(G[sel] - F[sel]) / F[sel]))
            fila["horaria_mediana_pct"] = float(np.median(eh) * 100) if eh else 0.0
            fila["horas_con_penacho"] = len(eh)
            out.append(fila)
    return out


def figura(C, rej, foco, ruta):
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt
    from matplotlib.colors import LogNorm
    hora = int(np.argmax(C.sum(1)))
    fig, ej = plt.subplots(2, 2, figsize=(11, 10))
    for col, (paso, r, tit) in enumerate(((5.0, 100.0, "±100 m, cada 5 m"), (25.0, 500.0, "±500 m, cada 25 m"))):
        k, I = rej.indices(paso, r)
        for fila, (campo, nom) in enumerate(((C.max(0), "máximo de las 42 h"), (C[hora], f"periodo {hora}"))):
            F = campo[I] * 1e6
            ax = ej[fila, col]
            vmax = max(F.max(), 1e-9)
            im = ax.pcolormesh(k, k, np.maximum(F, vmax * 1e-3), norm=LogNorm(vmax * 1e-3, vmax), cmap="viridis",
                               shading="nearest")
            fig.colorbar(im, ax=ax, label="µg/m³ por 1 g/s")
            if "verts" in foco:
                vx = [v[0] - foco["xp"] for v in foco["verts"]] + [foco["verts"][0][0] - foco["xp"]]
                vy = [v[1] - foco["yp"] for v in foco["verts"]] + [foco["verts"][0][1] - foco["yp"]]
                ax.plot(vx, vy, "r-", lw=1)
            else:
                ax.plot([foco["x"] - foco["xp"]], [foco["y"] - foco["yp"]], "r+", ms=10)
            ax.set_xlim(-r, r); ax.set_ylim(-r, r); ax.set_aspect("equal")
            ax.set_title(f"{foco['id']} · {nom} · {tit}", fontsize=10)
    fig.tight_layout()
    fig.savefig(ruta, dpi=110)
    plt.close(fig)


def main():
    TRABAJO.mkdir(parents=True, exist_ok=True)
    base = config.DIR_VIENTO3D / SERIE
    if not (TRABAJO / "viento3d.dat").exists():
        almacen.descomprimir(base / "cmz" / f"{MES}.cmz", TRABAJO / "viento3d.dat")
    info = json.loads((base / MES / "caso.json").read_text(encoding="utf-8"))
    malla = {k: info[k] for k in ("nx", "ny", "celda_m", "ext")}
    emp = config.cargar_emplazamiento()
    xp, yp = geo.a_utm(emp["lat"], emp["lon"])
    Z, U, tr = terreno.cargar(terreno.ultimo_caso(emp["lat"], emp["lon"]))

    def cota(x, y):
        f = int((tr.f - y) / -tr.e)
        c = int((x - tr.c) / tr.a)
        return float(max(Z[min(max(f, 0), Z.shape[0] - 1), min(max(c, 0), Z.shape[1] - 1)], 0.0))

    res = terreno.resumen(Z, U, tr, emp["lat"], emp["lon"])
    discretos = [(n["x"], n["y"], "nucleo") for n in res["nucleos"]]
    m_act = rec.malla_anidada((xp, yp), config.RADIO_CALCULO_KM * 1000.0, ACTUAL, discretos)
    m_pro = rec.malla_anidada((xp, yp), config.RADIO_CALCULO_KM * 1000.0, PROPUESTA, discretos)
    print("Actual:   ", rec.resumen(m_act), flush=True)
    print("Propuesta:", rec.resumen(m_pro), flush=True)
    r_act = [(x, y, cota(x, y)) for x, y, _ in m_act]
    r_pro = [(x, y, cota(x, y)) for x, y, _ in m_pro]
    rej = Rejilla([(x, y) for x, y, _ in m_pro], round(xp, 1), round(yp, 1))
    clases = np.array([c for _, _, c in m_pro])
    resultados = {"fecha": time.strftime("%Y-%m-%d %H:%M"), "horas": NHORAS,
                  "receptores": {"actual": rec.resumen(m_act), "propuesta": rec.resumen(m_pro)}, "focos": {}}
    for f in focos(xp, yp, cota):
        print(f["id"], flush=True)
        A = correr(f["id"] + "_actual", malla, info["zona"], dict(f), r_act)
        P = correr(f["id"] + "_propuesta", malla, info["zona"], dict(f), r_pro)
        umbral = float(A["C"].max()) * 1e-6
        nnz = {c: int((P["C"][:, clases == c] > umbral).sum()) for c in sorted(set(clases))}
        # receptores que ya están en la malla actual (la de 100 m) frente a los nuevos
        act = {(round(x, 1), round(y, 1)) for x, y, _ in m_act}
        es_vieja = np.array([(round(x, 1), round(y, 1)) in act for x, y, _ in m_pro])
        n_viejos = int((P["C"][:, es_vieja] > umbral).sum())
        n_nuevos = int((P["C"][:, ~es_vieja] > umbral).sum())
        # mismos receptores en las dos mallas: el resultado no debe cambiar
        ia = {(round(x, 1), round(y, 1)): i for i, (x, y, _) in enumerate(m_act)}
        ip = [ia[(round(x, 1), round(y, 1))] for (x, y, _), v in zip(m_pro, es_vieja) if v]
        dif = np.abs(P["C"][:, es_vieja] - A["C"][:, ip])
        i_max = np.unravel_index(int(np.argmax(P["C"])), P["C"].shape)
        xm, ym, _ = m_pro[i_max[1]]
        cerca = P["C"].max(0)
        dx, dy = round(xm - xp, 1), round(ym - yp, 1)
        xy = np.array([(x, y) for x, y, _ in m_pro])
        orden = np.argsort(np.hypot(xy[:, 0] - xm, xy[:, 1] - ym))[1:9]
        vec = cerca[orden]
        foco_f = dict(f, xp=xp, yp=yp)
        figura(P["C"], rej, foco_f, AQUI / f"campo_{f['id']}.png")
        resultados["focos"][f["id"]] = {
            "coste": {"actual": {k: A[k] for k in ("segundos", "memoria_mb", "fichero_mb")},
                      "propuesta": {k: P[k] for k in ("segundos", "memoria_mb", "fichero_mb")}},
            "misma_malla_dif_max_rel": float(dif.max() / max(A["C"].max(), 1e-30)),
            "valores_a_guardar": {"umbral_1e-6_del_max": umbral, "viejos": n_viejos, "nuevos": n_nuevos,
                                  "por_clase": nnz},
            "pico": {"valor_ug_m3": float(P["C"].max() * 1e6), "dx_m": dx, "dy_m": dy,
                     "max_8_vecinos_ug_m3": float(vec.max() * 1e6), "distancia_vecinos_m": float(np.hypot(*(xy[orden[0]] - [xm, ym]))),
                     "pico_malla_actual_ug_m3": float(A["C"].max() * 1e6)},
            "zonas": analiza(P["C"], rej, f, xp, yp)}
        (AQUI / "resultados.json").write_text(json.dumps(resultados, indent=1, ensure_ascii=False, default=float),
                                              encoding="utf-8")
    print("resultados →", AQUI / "resultados.json", flush=True)


if __name__ == "__main__":
    main()
