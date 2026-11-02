# -*- coding: utf-8 -*-
"""Prueba 05, 4.ª parte: el penacho del plan hora a hora (gui/planes_calculo.py, `calcular_periodo`), frente a cuentas a mano.

1. Foco continuo: C(H, r) = Q · Σ_h R[h, H, r], y sus 24 horas dan la media y el máximo de los 5 años.
2. Plan semanal que solo emite el día anterior: a primera hora queda lo que sigue en el aire y luego nada.
3. Plan semanal que solo emite el día siguiente: entra a las 22 UTC, porque el plan va en hora oficial (verano).
4. Los planes del día anterior, de ese día y del siguiente suman el foco continuo.

Necesita las respuestas de gui/tareas/respuestas_dia.py.

    C:\\e2s\\python.exe 99-Test\\05_planes\\prueba_penacho.py
"""
import json
import os
import shutil
import sys
from pathlib import Path

AQUI = Path(__file__).resolve().parent
RAIZ = AQUI.parents[1]
os.environ.setdefault("ENCE_GALERA_DATOS", str(Path(os.environ["TEMP"]) / "ence_galera" / "datos_local"))
CARGADOR = RAIZ.parent / (RAIZ / "VERSION").read_text(encoding="utf-8").strip() / "cargador"
sys.path[:0] = [str(CARGADOR)]
from teodors import planta as _planta  # noqa: E402
_planta.activar(RAIZ / "entrada")
_planta.actual().DIR_PLANES = _planta.DATOS / "escenarios"      # los planes de las pruebas, con la copia de los datos: nunca en la carpeta de la planta
sys.stdout.reconfigure(encoding="utf-8")

import numpy as np  # noqa: E402
import pandas as pd  # noqa: E402

from teodors.operacion import planes as E  # noqa: E402
from teodors.operacion import focos as F  # noqa: E402
from teodors.operacion import periodos  # noqa: E402
from teodors.operacion import simulacion as PC  # noqa: E402

NOMBRE = "prueba penacho"
FOCO = "F03"                                       # biofiltro, continuo
fallos = []


def ok(nombre, si, detalle=""):
    print(f"  {'OK ' if si else 'MAL'} {nombre} {detalle}", flush=True)
    if not si:
        fallos.append(nombre)


cat = F.cargar()
carpeta = PC.dir_respuestas()
meta = json.loads((carpeta / "meta.json").read_text(encoding="utf-8"))
dia = pd.Timestamp(meta["dia"])
apagado = {f["id"]: {"plan": "diario", "perfiles": [[0.0] * 24], "dias": [0]} for f in cat["focos"]}
PERIODO = periodos.nuevo("reanalisis", meta["dia"], 1, meta["serie"])
salida = PC.carpeta_resultados({"nombre": NOMBRE}, PERIODO)


def penacho(pf):
    """Calcula el plan con solo ese foco. Devuelve C[H, r], en ou_E/m³."""
    PC.calcular_periodo(dict(E.base(cat), nombre=NOMBRE, focos=dict(apagado, **{FOCO: pf})), cat, PERIODO)
    return np.load(salida / "olor" / "penacho.npz")["C"].astype(float)


def solo_el_dia(fecha):
    """Plan semanal que emite todo el día oficial de `fecha` y nada los demás."""
    dias = [1] * 7
    dias[fecha.weekday()] = 0
    return penacho({"plan": "semanal", "perfiles": [[1.0] * 24, [0.0] * 24], "dias": dias})


foco = next(f for f in cat["focos"] if f["id"] == FOCO)
Q = F.olor_ouE_s(foco) * F.fraccion_eventos(foco)
with np.load(carpeta / f"R_{FOCO}.npz") as z:
    ref = Q * z["R"].sum(axis=0).astype(float)
tol = 1e-3 * ref.max()

print(f"Día del viento: {dia:%Y-%m-%d}, {FOCO}, Q = {Q:.0f} ou_E/s", flush=True)
print("1. Foco continuo", flush=True)
C = penacho({"plan": "diario", "perfiles": [[1.0] * 24], "dias": [0]})
ok("C(H, r) = Q · Σ_h R[h, H, r]", C.shape == ref.shape and np.abs(C - ref).max() <= tol,
   f"máx. {ref.max():.3g}, diferencia {np.abs(C - ref).max():.2g}")
with np.load(salida / "olor" / "resumen.npz") as z:
    media, maximo = z["media"], z["maximo"]
ok("la media de sus 24 h = la de los 5 años", np.abs(C.mean(0) - media).max() <= tol, f"{np.abs(C.mean(0) - media).max():.2g}")
ok("el máximo de sus 24 h = el de los 5 años", np.abs(C.max(0) - maximo).max() <= tol, f"{np.abs(C.max(0) - maximo).max():.2g}")

print("2. Solo el día anterior", flush=True)
antes = solo_el_dia(dia - pd.Timedelta(days=1))
hora = antes.max(axis=1)
ok("a las 00 queda lo que sigue en el aire", hora[0] > 0, f"{hora[0]:.2g}")
ok("a las pocas horas, nada", hora[8:].max() == 0, f"máximo por hora, de 00 a 03: {[f'{v:.2g}' for v in hora[:4]]}")

print("3. Solo el día siguiente", flush=True)
despues = solo_el_dia(dia + pd.Timedelta(days=1))
ok("entra a las 22 UTC: hora oficial", despues[:22].max() == 0 and despues[22:].max() > 0, f"{despues[22:].max():.2g}")

print("4. Superposición", flush=True)
ese = solo_el_dia(dia)
ok("los tres planes suman el continuo", np.abs(antes + ese + despues - ref).max() <= tol, f"{np.abs(antes + ese + despues - ref).max():.2g}")

shutil.rmtree(salida, ignore_errors=True)
print("FALLOS:", fallos or "ninguno", flush=True)
sys.exit(1 if fallos else 0)
