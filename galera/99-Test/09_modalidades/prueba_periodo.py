# -*- coding: utf-8 -*-
"""Prueba 09, 2.ª parte: un episodio o una predicción de varios días (gui/planes_calculo.py, `calcular_periodo`), frente a cuentas a mano
con las respuestas guardadas.

1. Foco continuo: C(t, r) = Q · Σ_h R[h, t, r]; de ahí la media, el máximo y la hora del máximo.
2. Un plan que solo emite el día central (semanal, en hora oficial): el día de antes, nada; el de después solo lo que queda en el aire.
3. Los planes de cada día y de los días de alrededor suman el foco continuo: no se pierde ni se duplica emisión al cruzar los días.
4. Todas las horas del periodo tienen su imagen, y el resultado se guarda y se vuelve a leer mientras nada cambie.

Necesita el periodo ya preparado (gui/periodos.py, `preparar`). Focos de EJEMPLO: esto prueba la herramienta, no da resultados.

    C:\\e2s\\python.exe 99-Test\\09_modalidades\\prueba_periodo.py queja 2026-10-23 3
"""
import copy
import json
import os
import sys
import time
from pathlib import Path

RAIZ = Path(__file__).resolve().parents[2]
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
from teodors.operacion import periodos as P  # noqa: E402
from teodors.operacion import simulacion as PC  # noqa: E402

modo, ini, n = sys.argv[1], sys.argv[2], int(sys.argv[3])
PERIODO = P.nuevo(modo, ini, n)
FOCO = "F03"                                       # biofiltro, continuo
NOMBRE = "prueba periodo"
fallos = []


def ok(nombre, si, detalle=""):
    print(f"  {'OK ' if si else 'MAL'} {nombre} {detalle}", flush=True)
    if not si:
        fallos.append(nombre)


cat = F.cargar()
carpeta = P.dir_respuestas(PERIODO)
meta = json.loads((carpeta / "meta.json").read_text(encoding="utf-8"))
print(f"{P.etiqueta(PERIODO)} · {meta['receptores']} receptores · {len(meta['focos'])} focos · {P.fuente(PERIODO).get('fuente')}", flush=True)
foco = next(f for f in cat["focos"] if f["id"] == FOCO)
Q = F.olor_ouE_s(foco)
with np.load(carpeta / f"R_{FOCO}.npz") as z:
    R = z["R"]
print(f"R {R.shape}: 24 horas de emisión × {24 * n} horas × receptores", flush=True)
ok("R tiene todas las horas del periodo", R.shape[:2] == (24, 24 * n))
apagado = {f["id"]: {"plan": "diario", "perfiles": [[0.0] * 24], "dias": [0]} for f in cat["focos"]}
salida = PC.carpeta_resultados({"nombre": NOMBRE}, PERIODO)


def penacho(pf):
    """Calcula el plan con solo ese foco. Devuelve C[t, r], en ou_E/m³, y el resultado."""
    res = PC.calcular_periodo(dict(E.base(cat), nombre=NOMBRE, focos=dict(apagado, **{FOCO: pf})), cat, PERIODO)
    return np.load(salida / "olor" / "penacho.npz")["C"].astype(float), res


print("1. Foco continuo, a mano")
t0 = time.time()
C, res = penacho({"plan": "diario", "perfiles": [[1.0] * 24], "dias": [0]})
print(f"  {time.time() - t0:.0f} s con imágenes", flush=True)
mano = Q * R.sum(axis=0).astype(float)
g = mano > mano.max() * 1e-3
d = np.abs(C[g] - mano[g]) / mano[g]
ok("Cada hora de cada día coincide", d.max() < 1e-5, f"dif. máx. {d.max():.1e}, sobre {mano.max():.3g} ou_E/m³")
with np.load(salida / "olor" / "resumen.npz") as z:
    media, maximo, hora_max = z["media"], z["maximo"], z["hora_max"]
gm = mano.mean(axis=0) > mano.mean(axis=0).max() * 1e-3
ok("La media", (np.abs(media[gm] - mano.mean(axis=0)[gm]) / mano.mean(axis=0)[gm]).max() < 1e-5)
ok("El máximo", np.abs(maximo - mano.max(axis=0)).max() / mano.max() < 1e-5)
r = int(np.argmax(mano.max(axis=0)))
ok("La hora del máximo", hora_max[r] == int(np.argmax(mano[:, r])), f"receptor {r}: hora {hora_max[r]:.0f} del periodo")
m = res["magnitudes"]["olor"]
ok("Todas las horas tienen su imagen", len(m["penacho"]["frames"]) == 24 * n and all(Path(PC.url_a_ruta(u)).is_file() for f in m["penacho"]["frames"] for u in f))
ok("Las horas de la tabla van en hora oficial", len(m["horas_txt"]) == 24 * n, m["horas_txt"][:2])
ok("Columnas de un periodo de días", [c["clave"] for c in m["columnas"]] == ["media", "maximo", "hora_max"])

print("2. Solo emite un día (plan semanal, hora oficial)")
dias = pd.date_range(ini, periods=n, freq="D")


def solo_el_dia(fecha):
    semana = [1] * 7
    semana[fecha.weekday()] = 0
    return penacho({"plan": "semanal", "perfiles": [[1.0] * 24, [0.0] * 24], "dias": semana})[0]


centro = dias[n // 2]
Cd = solo_el_dia(centro)
locales = pd.date_range(ini, periods=24 * n, freq="h").tz_localize("UTC").tz_convert(E.zona())
por_hora = Cd.max(axis=1)
primera = int(np.flatnonzero(por_hora > 0)[0])
print(f"  Primera hora con algo: {locales[primera]} (día oficial {centro:%d/%m})", flush=True)
ok("Antes de empezar, nada", por_hora[:primera].max(initial=0) == 0)
ok("Empieza al abrir el día oficial", locales[primera].date() == centro.date() or (locales[primera] - pd.Timedelta(hours=1)).date() == centro.date(), str(locales[primera]))
if n > 1:
    fin = np.flatnonzero(np.asarray(locales.date) == centro.date())[-1]
    resto = por_hora[fin + 1:]
    if len(resto):
        print(f"  Tras acabar el día: máximo {resto[0]:.3g}, luego {resto[min(6, len(resto) - 1)]:.3g} a las 6 h, de {por_hora.max():.3g}", flush=True)
        ok("Después, solo lo que queda en el aire y se va", resto[min(12, len(resto) - 1)] < 1e-3 * por_hora.max())

print("3. La suma de los días es el foco continuo")
# semana entera partida en sus 7 días: suma = continuo, con la emisión del día de antes y del de después incluida
suma = np.zeros_like(C)
vistos = set()
for f in pd.date_range(dias[0] - pd.Timedelta(days=3), periods=7, freq="D"):
    if f.weekday() not in vistos:
        vistos.add(f.weekday())
        suma += solo_el_dia(f)
g = C > C.max() * 1e-3
d = np.abs(suma[g] - C[g]) / C[g]
ok("Los 7 días de la semana suman el continuo", d.max() < 1e-4, f"dif. máx. {d.max():.1e}")

print("4. Se guarda y se vuelve a leer")
esc = dict(E.base(cat), nombre=NOMBRE, focos=dict(apagado, **{FOCO: {"plan": "diario", "perfiles": [[1.0] * 24], "dias": [0]}}))
PC.calcular_periodo(copy.deepcopy(esc), cat, PERIODO)
ok("Con lo mismo, se lee", PC.guardado(copy.deepcopy(esc), cat, PERIODO) is not None)
otro = copy.deepcopy(esc)
otro["focos"][FOCO]["perfiles"] = [[0.5] * 24]
ok("Con otro plan, no", PC.guardado(otro, cat, PERIODO) is None)
ok("Con otro periodo, no", PC.guardado(copy.deepcopy(esc), cat, P.nuevo(modo, "2020-01-01", n)) is None)
print("FALLOS:", fallos or "ninguno")
sys.exit(1 if fallos else 0)
