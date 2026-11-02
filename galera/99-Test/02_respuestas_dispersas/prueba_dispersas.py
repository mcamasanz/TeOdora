# -*- coding: utf-8 -*-
"""Prueba 02 · RESPUESTAS DISPERSAS para el alcance 1.

Preguntas:
  1. Exactitud: guardando de las respuestas unitarias de la prueba 01 solo los valores por encima
     de umbral·máximo (10⁻⁶, 10⁻⁵, 10⁻⁴) en cuantización logarítmica de 16 bits, ¿cuánto cambian la
     media, el máximo y el P98 por receptor del escenario (3 focos, olor y NH3) frente al cálculo
     denso y frente al escenario simulado directamente?
  2. Escala: repitiendo esas 42 h hasta 5 años (43 806 h), ¿cuánto ocupan, cuánto se tarda en
     leerlas, en calcular media, máximo y P98 de un escenario en los 8 011 receptores y en sacar
     las 24 horas de un día? (Repetir el mismo trozo da patrones artificiales: el tamaño SIN
     comprimir es representativo; el comprimido, no.)

Necesita los casos de la prueba 01 (%TEMP%\\ence_galera\\99-Test\\01_superposicion).
    C:\\e2s\\python.exe 99-Test\\02_respuestas_dispersas\\prueba_dispersas.py
"""
import json
import os
import sys
import time
from pathlib import Path

AQUI = Path(__file__).resolve().parent
RAIZ = AQUI.parents[1]
CARGADOR = RAIZ.parent / (RAIZ / "VERSION").read_text(encoding="utf-8").strip() / "cargador"
sys.path[:0] = [str(CARGADOR), str(AQUI)]
from teodors import planta as _planta  # noqa: E402
_planta.activar(RAIZ / "entrada")
_planta.actual().DIR_PLANES = _planta.DATOS / "escenarios"      # los planes de las pruebas, con la copia de los datos: nunca en la carpeta de la planta
sys.stdout.reconfigure(encoding="utf-8")

import numpy as np  # noqa: E402
import psutil  # noqa: E402

import almacen_respuestas as ar  # noqa: E402
from teodors.preparacion.puffs import salida  # noqa: E402

P01 = Path(os.environ["TEMP"]) / "ence_galera" / "99-Test" / "01_superposicion"
TRABAJO = Path(os.environ["TEMP"]) / "ence_galera" / "99-Test" / "02_respuestas_dispersas"
ESPECIES = ["OLOR", "NH3"]
HORAS = ["H%02d" % h for h in range(24)]
CINCO_ANIOS = 43824


def pesos(foco, esp):
    p = foco.get("perfil") or [1.0] * 24
    if isinstance(p, dict):
        p = p[esp]
    return [foco["q"][esp] * x for x in p]


def estadisticas(S, percentil=98.0):
    return S.mean(0), S.max(0), np.percentile(S, percentil, axis=0)


def errores(ref, est, relevancia=1e-3):
    """Error relativo máximo donde el valor de referencia es relevante (> relevancia · su
    máximo) y error absoluto máximo relativo al máximo de la referencia."""
    tope = ref.max()
    m = ref > relevancia * tope
    rel = np.abs(est[m] - ref[m]) / ref[m]
    return {"rel_max": float(rel.max()) if m.any() else 0.0, "rel_p99": float(np.percentile(rel, 99)) if m.any() else 0.0,
            "abs_max_del_maximo": float(np.abs(est - ref).max() / tope) if tope else 0.0,
            "receptores_relevantes": int(m.sum())}


def tilar(a, n, T0):
    """Repite n veces en el tiempo las horas de un almacén (manteniendo el orden por receptor)."""
    ip, t, h, k = a["indptr"], a["t"].astype(np.int64), a["h"], a["k"]
    pt, ph, pk = [], [], []
    desp = T0 * np.arange(n, dtype=np.int64)[:, None]
    for r in range(a["nrec"]):
        p0, p1 = ip[r], ip[r + 1]
        if p1 > p0:
            pt.append((t[p0:p1][None, :] + desp).ravel())
            ph.append(np.tile(h[p0:p1], n))
            pk.append(np.tile(k[p0:p1], n))
    indptr = np.zeros(a["nrec"] + 1, np.int64)
    np.cumsum(np.diff(ip) * n, out=indptr[1:])
    horas = T0 * n
    return dict(a, indptr=indptr, t=np.concatenate(pt).astype(np.uint16 if horas < 65536 else np.uint32),
                h=np.concatenate(ph), k=np.concatenate(pk), horas=horas)


def main():
    TRABAJO.mkdir(parents=True, exist_ok=True)
    focos = json.loads((AQUI.parent / "01_superposicion" / "resultados.json").read_text(encoding="utf-8"))["focos"]
    R = {f["id"]: np.stack([salida.concentraciones(P01 / f"B_{f['id']}.dat", especie=h)[1] for h in HORAS])
         for f in focos}                                                   # (24, horas, receptores)
    A = {e: salida.concentraciones(P01 / "A_directo.dat", especie=e)[1] for e in ESPECIES}
    T0, nrec = next(iter(R.values())).shape[1:]
    print(f"respuestas de la prueba 01: {len(focos)} focos × 24 × {T0} h × {nrec} receptores", flush=True)
    out = {"exactitud": {}, "escala": {}}

    # 1) exactitud
    densas = {}
    for e in ESPECIES:
        S = sum(np.tensordot(np.asarray(pesos(f, e)), R[f["id"]], axes=(0, 0)) for f in focos)
        densas[e] = estadisticas(S)
        dA = np.abs(S - A[e]).max() / A[e].max()
        print(f"  {e}: denso frente al directo |Δ| máx {dA:.1e} del máximo", flush=True)
    for umbral in (1e-6, 1e-5, 1e-4):
        alms = {f["id"]: ar.comprimir(R[f["id"]], umbral) for f in focos}
        res = {"bytes": {k: ar.bytes_(a) for k, a in alms.items()},
               "densos_float32": int(24 * T0 * nrec * 4)}
        for k, a in alms.items():                      # tamaño real del fichero comprimido
            ar.guardar(TRABAJO / f"{k}_{umbral:g}.npz", a, comprimido=True)
            res.setdefault("npz_comprimido", {})[k] = (TRABAJO / f"{k}_{umbral:g}.npz").stat().st_size
            v = R[k][R[k] > umbral * a["vmax"]]
            dec = ar.decodificar(ar.codificar(v, a["vmax"], umbral), a["vmax"], umbral)
            res.setdefault("cuantizacion_rel_max", {})[k] = float((np.abs(dec - v) / v).max())
        for e in ESPECIES:
            est = ar.escenario([alms[f["id"]] for f in focos], [pesos(f, e) for f in focos])
            directo = estadisticas(A[e])
            res[e] = {n: {"frente_al_denso": errores(d, s), "frente_al_directo": errores(x, s)}
                      for n, d, s, x in zip(("media", "maximo", "p98"), densas[e], est, directo)}
        out["exactitud"][f"{umbral:g}"] = res
        tam = sum(res["bytes"].values())
        print(f"  umbral {umbral:g}: {tam / 1e6:.2f} MB sin comprimir ({sum(res['npz_comprimido'].values()) / 1e6:.2f} "
              f"comprimido) frente a {3 * res['densos_float32'] / 1e6:.0f} MB densos · error rel. máx (relevantes) "
              + " · ".join(f"{e} media {res[e]['media']['frente_al_denso']['rel_max']:.1e} máx "
                           f"{res[e]['maximo']['frente_al_denso']['rel_max']:.1e} P98 {res[e]['p98']['frente_al_denso']['rel_max']:.1e}"
                           for e in ESPECIES), flush=True)

    # 2) escala: 5 años repitiendo las 42 h (umbral: 1.er argumento, por defecto 1e-6)
    umbral, n = float(sys.argv[1]) if len(sys.argv) > 1 else 1e-6, CINCO_ANIOS // T0
    out["escala"]["umbral"] = umbral
    t = time.perf_counter()
    grandes = {f["id"]: tilar(ar.comprimir(R[f["id"]], umbral), n, T0) for f in focos}
    out["escala"]["construir_s"] = time.perf_counter() - t
    out["escala"]["horas"] = T0 * n
    out["escala"]["valores"] = {k: int(a["t"].size) for k, a in grandes.items()}
    out["escala"]["bytes"] = {k: ar.bytes_(a) for k, a in grandes.items()}
    t = time.perf_counter()
    for k, a in grandes.items():
        ar.guardar(TRABAJO / f"grande_{k}.npz", a)
    out["escala"]["guardar_s"] = time.perf_counter() - t
    del grandes
    t = time.perf_counter()
    grandes = {f["id"]: ar.cargar(TRABAJO / f"grande_{f['id']}.npz") for f in focos}
    out["escala"]["leer_s"] = time.perf_counter() - t
    t = time.perf_counter()
    media, maximo, p98 = ar.escenario([grandes[f["id"]] for f in focos], [pesos(f, "OLOR") for f in focos])
    out["escala"]["escenario_media_max_p98_s"] = time.perf_counter() - t
    t = time.perf_counter()
    dia = ar.horas_escenario([grandes[f["id"]] for f in focos], [pesos(f, "OLOR") for f in focos], 24000, 24024)
    out["escala"]["un_dia_primera_vez_s"] = time.perf_counter() - t
    t = time.perf_counter()
    dia = ar.horas_escenario([grandes[f["id"]] for f in focos], [pesos(f, "OLOR") for f in focos], 30000, 30024)
    out["escala"]["un_dia_s"] = time.perf_counter() - t
    out["escala"]["memoria_pico_mb"] = psutil.Process().memory_info().peak_wset / 1e6
    # comprobación: con un trozo repetido, el máximo de 5 años = el de las 42 h con el MISMO umbral
    peq = ar.escenario([ar.comprimir(R[f["id"]], umbral) for f in focos], [pesos(f, "OLOR") for f in focos])
    out["escala"]["maximo_igual_al_de_42h"] = bool(np.array_equal(maximo, peq[1]))
    e = out["escala"]
    print(f"  5 años ({e['horas']} h), umbral {umbral:g}: {sum(e['bytes'].values()) / 1e6:.0f} MB para 3 focos "
          f"({', '.join(f'{k} {v / 1e6:.0f}' for k, v in e['bytes'].items())} MB) · leer {e['leer_s']:.1f} s · "
          f"escenario (media, máx, P98) {e['escenario_media_max_p98_s']:.1f} s · un día {e['un_dia_s']:.2f} s "
          f"(1.ª vez {e['un_dia_primera_vez_s']:.2f}) · memoria pico {e['memoria_pico_mb']:.0f} MB · "
          f"máximo coherente {e['maximo_igual_al_de_42h']}", flush=True)
    (AQUI / "resultados.json").write_text(json.dumps(out, indent=1, ensure_ascii=False), encoding="utf-8")
    print("resultados →", AQUI / "resultados.json", flush=True)


if __name__ == "__main__":
    main()
