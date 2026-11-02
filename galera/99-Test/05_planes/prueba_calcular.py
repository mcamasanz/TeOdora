# -*- coding: utf-8 -*-
"""Prueba 05, 3.ª parte: «Calcular» (gui/planes_calculo.py) con el viento de un día repetido 5 años.

Comprueba con cuentas independientes que el resultado es el que tiene que ser:
1. Foco continuo, media a mano: con R periódica, media = Q · Σ_H Σ_h R[h, H] / 24.
2. Linealidad: la mitad de perfil da la mitad en media, máximo y P98.
3. Superposición de focos: un plan con todos da en media la suma de los planes de un solo foco.
4. Plan apagado: 0. Plan semanal con la semana «apagada» salvo el lunes: la media cae a 1/7 aprox.
5. Mensual: se evalúa solo ese mes; con el viento repetido, si el plan es constante da lo mismo que el diario.
6. El P98 sale de la serie horaria: en un receptor, a mano, con el foco continuo.

Mide también el tiempo. Necesita las respuestas de gui/tareas/respuestas_dia.py.

    C:\\e2s\\python.exe 99-Test\\05_planes\\prueba_calcular.py
"""
import json
import os
import sys
import time
from pathlib import Path

AQUI = Path(__file__).resolve().parent
RAIZ = AQUI.parents[1]
os.environ.setdefault("ENCE_GALERA_DATOS", str(Path(os.environ["TEMP"]) / "ence_galera" / "datos_local"))
CARGADOR = RAIZ.parent / (RAIZ / "VERSION").read_text(encoding="utf-8").strip() / "cargador"
sys.path[:0] = [str(CARGADOR)]
from teodors import planta as _planta  # noqa: E402
_planta.activar(RAIZ / "entrada")
sys.stdout.reconfigure(encoding="utf-8")

import numpy as np  # noqa: E402

from teodors.operacion import planes as E  # noqa: E402
from teodors.operacion import focos as F  # noqa: E402
from teodors.operacion import simulacion as PC  # noqa: E402

fallos = []
resumen = {}


def ok(nombre, si, detalle=""):
    print(f"  {'OK ' if si else 'MAL'} {nombre} {detalle}", flush=True)
    if not si:
        fallos.append(nombre)


def sin_imagenes(esc, cat):
    """Solo las series: las imágenes se comprueban aparte."""
    capas, PC._capas = PC._capas, lambda *a, **k: []
    try:
        return PC.calcular(esc, cat)
    finally:
        PC._capas = capas


def campos(esc):
    with np.load(PC.carpeta_resultados(esc) / "olor" / "resumen.npz") as z:
        return {c: z[c] for c, _, _ in PC.ESTADISTICAS}


def plan(nombre, cat, base=None):
    return E.nuevo(cat, "prueba " + nombre, base)


def solo(cat, id_foco):
    """Plan con todos los focos apagados salvo uno."""
    e = plan(id_foco, cat)
    for f in cat["focos"]:
        if f["id"] != id_foco:
            E.poner_perfil(E.plan_foco(f, e), [0], [0.0] * 24)
    return e


def main():
    cat = F.cargar()
    carpeta = PC.dir_respuestas()
    meta = json.loads((carpeta / "meta.json").read_text(encoding="utf-8"))
    print(f"Respuestas: {carpeta.name} · {len(meta['focos'])} focos · {meta['receptores']} receptores", flush=True)

    print("Base")
    t0 = time.time()
    b = plan("base", cat)
    rb = PC.calcular(b, cat)
    resumen["base_con_imagenes_s"] = round(time.time() - t0, 1)
    resumen["base_series_s"] = rb["segundos_serie"]
    mb = rb["magnitudes"]["olor"]
    print(f"  {rb['segundos']:.0f} s en total ({rb['segundos_serie']:.0f} s las series) · {mb['focos']} focos · "
          f"{rb['horas']} horas · fuera: {mb['fuera']}", flush=True)
    print("  máximos:", {k: round(v, 2) for k, v in mb["maximos"].items()}, flush=True)
    for f in mb["filas"]:
        print(f"    {f['nombre']:<38s} {f['km']:5.1f} km · media {f['media']:9.3f} · máx {f['maximo']:9.2f} · P98 {f['p98']:9.2f}", flush=True)
    cb = campos(b)

    print("1. Foco continuo, a mano (F03 biofiltro)")
    f3 = next(f for f in cat["focos"] if f["id"] == "F03")
    q = F.olor_ouE_s(f3)
    with np.load(carpeta / "R_F03.npz") as z:
        R3 = z["R"]
    mano = q * R3.sum(axis=(0, 1)) / 24.0
    e3 = solo(cat, "F03")
    sin_imagenes(e3, cat)
    c3 = campos(e3)
    m = mano > mano.max() * 1e-3
    d = np.abs(c3["media"][m] - mano[m]) / mano[m]
    ok("la media coincide", d.max() < 2e-3, f"dif. máx. {d.max():.1e}")
    # 6. P98 a mano en el receptor con más media: serie del día repetida
    r = int(np.argmax(mano))
    dia = q * R3[:, :, r].sum(axis=0)
    ok("el máximo es el de la hora peor", abs(c3["maximo"][r] - dia.max()) / dia.max() < 2e-3, f"{c3['maximo'][r]:.3f} y {dia.max():.3f}")
    p98_mano = np.percentile(np.tile(dia, 40), 98)
    ok("el P98 sale de la serie horaria", abs(c3["p98"][r] - p98_mano) / p98_mano < 5e-3, f"{c3['p98'][r]:.3f} y {p98_mano:.3f}")

    print("2. Linealidad: perfil × 0,5")
    e2 = solo(cat, "F03")
    E.poner_perfil(E.plan_foco(f3, e2), [0], [x / 2 for x in F.perfil(f3)])
    sin_imagenes(e2, cat)
    c2 = campos(e2)
    for k in c2:
        mm = c3[k] > c3[k].max() * 1e-3
        dd = np.abs(c2[k][mm] - 0.5 * c3[k][mm]) / (0.5 * c3[k][mm])
        ok(f"{k} × 0,5", dd.max() < 1e-4, f"dif. máx. {dd.max():.1e}")

    print("3. Superposición de focos (media)")
    suma = np.zeros_like(cb["media"])
    for i in [f["id"] for f in cat["focos"] if f["id"] in meta["focos"] and F.olor_ouE_s(f) is not None]:
        ei = solo(cat, i)
        sin_imagenes(ei, cat)
        suma += campos(ei)["media"]
    mm = cb["media"] > cb["media"].max() * 1e-3
    dd = np.abs(suma[mm] - cb["media"][mm]) / cb["media"][mm]
    ok("la suma de los focos es el conjunto", dd.max() < 1e-3, f"dif. máx. {dd.max():.1e}")

    print("4. Planes por días")
    ap = plan("apagado", cat)
    for f in cat["focos"]:
        E.poner_perfil(E.plan_foco(f, ap), [0], [0.0] * 24)
    sin_imagenes(ap, cat)
    ok("apagado: 0", campos(ap)["maximo"].max() == 0.0)
    lu = solo(cat, "F03")
    pf = E.plan_foco(f3, lu)
    E.cambiar_plan(pf, "semanal")
    E.poner_perfil(pf, [1, 2, 3, 4, 5, 6], [0.0] * 24)
    t0 = time.time()
    sin_imagenes(lu, cat)
    resumen["semanal_series_s"] = round(time.time() - t0, 1)
    cl = campos(lu)
    mm = c3["media"] > c3["media"].max() * 1e-3
    ratio = cl["media"][mm] / c3["media"][mm]
    ok("solo el lunes: la media cae a 1/7", abs(np.median(ratio) - 1 / 7) < 2e-3, f"mediana {np.median(ratio):.4f} (1/7 = {1 / 7:.4f})")
    dd = np.abs(cl["maximo"][mm] - c3["maximo"][mm]) / c3["maximo"][mm]
    ok("solo el lunes: el máximo no cambia", np.percentile(dd, 99) < 2e-3, f"P99 de la dif. {np.percentile(dd, 99):.1e}")

    print("5. Mensual")
    me = solo(cat, "F03")
    me["mes"] = "2026-11"
    E.cambiar_plan(E.plan_foco(f3, me), "mensual")
    r5 = sin_imagenes(me, cat)
    c5 = campos(me)
    ok("solo las horas de noviembre", 3500 < r5["horas"] < 3700, f"{r5['horas']} horas")
    dd = np.abs(c5["media"][mm] - c3["media"][mm]) / c3["media"][mm]
    ok("constante: la misma media que el diario", dd.max() < 2e-3, f"dif. máx. {dd.max():.1e}")
    (AQUI / "resultados_calcular.json").write_text(json.dumps(resumen, indent=1), encoding="utf-8")
    # no deja rastro de las pruebas en los resultados de los planes
    import shutil
    for c in PC.carpeta_resultados(b).parent.glob("prueba_*"):
        if c.name != "prueba_base":
            shutil.rmtree(c, ignore_errors=True)
    print("FALLOS: " + (", ".join(fallos) if fallos else "ninguno"))
    sys.exit(1 if fallos else 0)


if __name__ == "__main__":
    main()
