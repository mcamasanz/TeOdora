# -*- coding: utf-8 -*-
"""Prueba 05 · PLANES por días (diario, semanal, mensual) a partir de las respuestas (alcance 1).

Pedido del usuario (2026-10-31): planes diarios, semanales e incluso mensuales de cada foco. La
superposición de la prueba 01 está validada con UN perfil de 24 h que se repite igual todos los días.
Las respuestas R_h(t, r) mezclan todas las emisiones de la hora h del día, de cualquier fecha. Pero si
un puff no dura más de 24 h en el dominio, lo que hay de h en el instante t viene SOLO de la última vez
que fue la hora h, y se puede pesar con lo que dice el plan para esa fecha:

    C(t, r) = Σ_h  R_h(t, r) · E(te),   te = última hora ≤ t en la que se emitió h

Sin ningún cálculo nuevo del motor: te sale de t y h, que ya están guardados por cada valor.

Referencia DIRECTA, solo con el motor y linealidad: un foco que emite el 1.er día y se apaga después es
A − B, con A = emisión constante desde las 06 del 20 (42 h) y B = la misma desde las 06 del 21 (18 h).
Si queda olor de hace más de 24 h, la suma se equivoca justo ahí: la prueba mide ese error.

Datos: viento local de 48 h y focos INVENTADOS de la prueba 01. Una sola situación meteorológica: el
caso difícil (calmas largas) hay que repetirlo con la serie de 5 años, cuando vuelva Z:.

    C:\\e2s\\python.exe 99-Test\\05_planes\\prueba_planes.py
Resultados: resultados.json; casos en %TEMP%\\ence_galera\\99-Test\\05_planes.
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
sys.path[:0] = [str(CARGADOR), str(RAIZ / "99-Test" / "01_superposicion"),
                str(RAIZ / "99-Test" / "02_respuestas_dispersas")]
from teodors import planta as _planta  # noqa: E402
_planta.activar(RAIZ / "entrada")
sys.stdout.reconfigure(encoding="utf-8")

import numpy as np  # noqa: E402
import pandas as pd  # noqa: E402

import control_multiple as cm  # noqa: E402
from teodors.planta import geo  # noqa: E402
from teodors.fuentes import terreno  # noqa: E402
from teodors import planta as config  # noqa: E402
from teodors.casos import receptores as receptores_mapa  # noqa: E402
from teodors.meteo.viento3d import almacen  # noqa: E402
from teodors.preparacion.puffs import salida  # noqa: E402

SERIE, MES = "odora_gfs_8est", "202610"
INI_A, HORAS_A = pd.Timestamp("2026-10-20 06:00"), 42
INI_B, HORAS_B = pd.Timestamp("2026-10-21 06:00"), 18
TRABAJO = config.LOCAL / "99-Test" / "05_planes"
HORAS = ["H%02d" % h for h in range(24)]


def focos(xp, yp, cota):
    """Los tres focos inventados de la prueba 01, con 1 g/s en total."""
    def rect(x0, y0, lx, ly):
        return [(x0, y0), (x0 + lx, y0), (x0 + lx, y0 + ly), (x0, y0 + ly)]
    pilas = {"id": "PILAS", "verts": rect(xp - 110, yp + 30, 60.0, 12.0), "h": 2.5, "q0": 1.0 / 720.0}
    biofiltro = {"id": "BIOFILTRO", "verts": rect(xp + 40, yp - 50, 30.0, 20.0), "h": 1.0, "q0": 1.0 / 600.0}
    chimenea = {"id": "CHIMENEA", "x": xp + 20.0, "y": yp + 60.0, "h": 12.0, "d": 0.5, "w": 10.0, "t": 400.0, "q0": 1.0}
    for a in (pilas, biofiltro):
        cx, cy = np.mean(a["verts"], axis=0)
        a["cota"] = cota(cx, cy)
    chimenea["cota"] = cota(chimenea["x"], chimenea["y"])
    return [pilas, biofiltro, chimenea]


def correr(nombre, malla, zona, ini, horas, especies, foco, recs):
    """Lanza teOdors puffs. Devuelve (fines, {especie: C}), reutilizando el resultado si ya está."""
    dat = TRABAJO / (nombre + ".dat")
    if not dat.exists():
        nom = {"viento": "viento3d.dat", "listado": nombre + ".lst", "concentraciones": nombre + ".dat"}
        es_area = "verts" in foco
        cm.escribir(TRABAJO / (nombre + ".inp"), malla, config.VIENTO3D_ZFACE, ini, horas, zona, especies,
                    [foco] if es_area else [], [] if es_area else [foco], recs, nombres=nom)
        env = dict(os.environ, PYTHONPATH=str(CARGADOR), PYTHONIOENCODING="utf-8")
        t0 = time.time()
        with open(TRABAJO / (nombre + ".log"), "w", errors="replace") as fo:
            rc = subprocess.call([sys.executable, "-m", "teodors", "puffs", nombre + ".inp"], cwd=str(TRABAJO),
                                 stdout=fo, stderr=subprocess.STDOUT, env=env)
        if rc != 0:
            raise RuntimeError(nombre + ": " + (TRABAJO / (nombre + ".log")).read_text(errors="replace")[-1500:])
        print(f"  {nombre:24s} {len(especies):2d} especies · {time.time() - t0:6.1f} s", flush=True)
    fines = pd.to_datetime(salida.concentraciones(dat)[0])
    return fines, {e: np.asarray(salida.concentraciones(dat, especie=e)[1]) for e in especies}


def indice_emision(fines):
    """(t, h) → te: periodo de la última emisión de la hora h a la hora del periodo t. Motor: el factor
    h se aplica en el periodo cuyo fin tiene hora h + 1 (`principal`: hora_reloj = tfin.hour, 24 si es 0)."""
    hora_fin = np.array([f.hour for f in fines])
    t = np.arange(len(fines))[:, None]
    h = np.arange(24)[None, :]
    return t - (hora_fin[:, None] - (h + 1)) % 24           # (periodos, 24); < 0: aún no se había emitido


def componer(R, te, W):
    """C(t, r) = Σ_h R_h(t, r) · W[te(t, h)], W = emisión del plan en cada periodo."""
    C = np.zeros_like(R[HORAS[0]], dtype=float)
    for h, e in enumerate(HORAS):
        ok = te[:, h] >= 0
        C[ok] += R[e][ok] * W[te[ok, h]][:, None]
    return C


def compara(C, D, gruesa):
    """Diferencias entre la suma por plan C y el cálculo directo D."""
    tope = float(D.max())
    dif = np.abs(C - D)
    m = D > tope * 1e-3
    rel = dif[m] / D[m]
    masa = float(dif[:, gruesa].sum() / D[:, gruesa].sum())
    def est(F, G):
        mm = G > G.max() * 1e-3
        return {"max_rel_pct": float((np.abs(F[mm] - G[mm]) / G[mm]).max() * 100),
                "mediana_rel_pct": float(np.median(np.abs(F[mm] - G[mm]) / G[mm]) * 100)}
    return {"max_directo_ug_m3": tope * 1e6, "dif_max_rel_al_maximo": float(dif.max() / tope),
            "receptor_horas_evaluadas": int(m.sum()), "rel_p50_pct": float(np.median(rel) * 100),
            "rel_p99_pct": float(np.percentile(rel, 99) * 100), "rel_max_pct": float(rel.max() * 100),
            "masa_mal_atribuida_pct": masa * 100,
            "media": est(C.mean(0), D.mean(0)), "maximo": est(C.max(0), D.max(0)),
            "p98": est(np.percentile(C, 98, axis=0), np.percentile(D, 98, axis=0))}


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
    m = receptores_mapa.malla(res["nucleos"], None)
    recs = [(x, y, cota(x, y)) for x, y, _ in m]
    gruesa = np.array([c == "gruesa" for _, _, c in m])      # rejilla regular: suma ≈ masa en el dominio
    unos = [[1.0 if k == h else 0.0 for k in range(24)] for h in range(24)]
    print(f"{len(recs)} receptores", flush=True)
    out = {"fecha": time.strftime("%Y-%m-%d %H:%M"), "receptores": len(recs), "focos": {}}
    for f in focos(xp, yp, cota):
        print(f["id"], flush=True)
        uno = dict(f, q={"UNO": f["q0"]}, perfil=None)
        fa, A = correr(f["id"] + "_A", malla, info["zona"], INI_A, HORAS_A, ["UNO"], uno, recs)
        fb, B = correr(f["id"] + "_B", malla, info["zona"], INI_B, HORAS_B, ["UNO"], uno, recs)
        g = dict(f, q={e: f["q0"] for e in HORAS}, perfil={e: unos[h] for h, e in enumerate(HORAS)})
        fr, R = correr(f["id"] + "_R", malla, info["zona"], INI_A, HORAS_A, HORAS, g, recs)
        A, B = A["UNO"], B["UNO"]
        # B en el reloj de A
        i0 = int(np.where(fa == fb[0])[0][0])
        if not (fa[i0:i0 + len(fb)] == fb).all():
            raise RuntimeError("los periodos de A y B no coinciden")
        D = A.copy()
        D[i0:i0 + len(fb)] -= B
        te = indice_emision(fr)
        # comprobaciones: la 1.ª aparición de cada especie es su 1.er periodo de emisión; Σ R_h = A
        primeros = {}
        for h, e in enumerate(HORAS):
            tf = np.where(R[e].max(1) > 0)[0]
            primeros[e] = bool(len(tf)) and int(tf[0]) == int(np.where(te[:, h] >= 0)[0][0])
        suma = sum(R[e] for e in HORAS)
        W = np.array([1.0 if k < i0 else 0.0 for k in range(len(fr))])
        C = componer(R, te, W)
        fila = {"inicio_B_periodo": i0, "convencion_emision_ok": all(primeros.values()),
                "suma_R_igual_A_dif_rel": float(np.abs(suma - A).max() / A.max()),
                "directo_negativos_rel": float(min(D.min(), 0.0) / A.max()),
                "plan_on_off": compara(C, D, gruesa)}
        # ¿cuánto olor queda tras apagar? por horas desde el apagado
        cola = []
        for k in range(i0, len(fa)):
            cola.append({"horas_desde_apagar": k - i0 + 1, "fin": str(fa[k]),
                         "resto_masa_pct": float(D[k, gruesa].sum() / max(A[k, gruesa].sum(), 1e-30) * 100),
                         "max_directo_ug_m3": float(D[k].max() * 1e6), "max_constante_ug_m3": float(A[k].max() * 1e6)})
        fila["tras_apagar"] = cola
        # un plan con dos días distintos (día 1 × 1, día 2 × 0,25): por linealidad = D + 0,25·B
        W2 = np.array([1.0 if k < i0 else 0.25 for k in range(len(fr))])
        D2 = D.copy()
        D2[i0:i0 + len(fb)] += 0.25 * B
        fila["plan_dos_dias"] = compara(componer(R, te, W2), D2, gruesa)
        out["focos"][f["id"]] = fila
        p = fila["plan_on_off"]
        print(f"  convención {fila['convencion_emision_ok']} · ΣR = A {fila['suma_R_igual_A_dif_rel']:.1e} · plan: "
              f"mediana {p['rel_p50_pct']:.3f} % · P99 {p['rel_p99_pct']:.3f} % · máx {p['rel_max_pct']:.2f} % · "
              f"masa mal atribuida {p['masa_mal_atribuida_pct']:.4f} %", flush=True)
        print("  tras apagar (h: % que queda): " + " · ".join(
            f"{c['horas_desde_apagar']}: {c['resto_masa_pct']:.2f}" for c in cola), flush=True)
        (AQUI / "resultados.json").write_text(json.dumps(out, indent=1, ensure_ascii=False, default=float), encoding="utf-8")
    print("resultados →", AQUI / "resultados.json", flush=True)


if __name__ == "__main__":
    main()
