# -*- coding: utf-8 -*-
"""Prueba 09, 1.ª parte: los estadísticos de gui/normativa.py, con series hechas a mano cuyo resultado se sabe de antemano, y que la
normativa se cambie en su fichero sin tocar el código (usuario, 2026-11-01: es preliminar, se modificará).

    C:\\e2s\\python.exe 99-Test\\09_modalidades\\prueba_normativa.py
"""
import json
import os
import sys
import tempfile
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

from teodors.operacion import focos as F  # noqa: E402
from teodors.operacion import normativa as N  # noqa: E402

fallos = []


def ok(nombre, si, detalle=""):
    print(f"  {'OK ' if si else 'MAL'} {nombre} {detalle}", flush=True)
    if not si:
        fallos.append(nombre)


def col(clave, largo="anios", gas="NO2"):
    return next(c for c in N.columnas(gas, largo) if c["clave"] == clave)


fines = pd.date_range("2021-01-01 01:00", "2023-01-01 00:00", freq="h")
n = len(fines)
anios = np.asarray(fines.year)
print(f"{n} horas de 2021-01-01 01:00 a 2023-01-01 00:00; años: {sorted(set(anios))}")

print("1. La 19.ª hora más alta del peor año (NO₂, 18 superaciones)")
C = np.ones((n, 3), np.float32)
i21, i22 = np.flatnonzero(anios == 2021), np.flatnonzero(anios == 2022)
C[i21[:19], 0] = 300            # receptor 0: 19 horas altas en 2021, supera
C[i21[:18], 1] = 300            # receptor 1: 18 horas en 2021 y 18 en 2022: cumple, aunque sean 36 en los dos años
C[i22[:18], 1] = 300
C[i22[:40], 2] = 500            # receptor 2: 40 horas solo en 2022: supera ese año
v = N.estadistico(col("norma_hora"), C, fines)
ok("19 horas en un año: la 19.ª es alta", v[0] == 300, v[0])
ok("18 cada año: cumple, porque cuenta por año civil", v[1] == 1, v[1])
ok("40 en 2022: cuenta el peor año", v[2] == 500, v[2])
D = np.ones((n, 1), np.float32)
D[i21[:30], 0] = 300            # 30 horas en un solo año: por encima de las 18 que admite, pero repartidas en dos años no se nota
juntos = np.percentile(D[:, 0], 100 * (1 - 18 / 8760))
ok("Con el percentil de los dos años juntos habría parecido que cumple", juntos == 1 and N.estadistico(col("norma_hora"), D, fines)[0] == 300, f"percentil {juntos:.0f} frente a 300")

print("2. La media anual del peor año (NO₂)")
C = np.zeros((n, 2), np.float32)
C[i21, 0] = 10
C[i22, 0] = 30
C[i21, 1] = 20
C[i22, 1] = 20
v = N.estadistico(col("norma_anio"), C, fines)
ok("10 y 30: cuenta el 30", abs(v[0] - 30) < 1e-6, v[0])
ok("igual los dos años: 20", abs(v[1] - 20) < 1e-6, v[1])

print("3. El 4.º día más alto del peor año (SO₂, 3 superaciones)")
C = np.zeros((n, 2), np.float32)
dias = fines.normalize()
dias_21 = pd.DatetimeIndex(sorted(set(dias[anios == 2021])))[1:6]          # 5 días completos
for k, d in enumerate(dias_21):
    C[dias == d, 0] = 100 + 10 * k         # medias 100, 110, 120, 130, 140: la 4.ª más alta es 110
C[dias == dias_21[0], 1] = 200             # un solo día alto: el 4.º es 0
v = N.estadistico(col("norma_dia", gas="SO2"), C, fines)
ok("Medias 100 a 140: el 4.º más alto es 110", abs(v[0] - 110) < 1e-6, v[0])
ok("Un solo día alto: el 4.º es 0, cumple", v[1] == 0, v[1])

print("4. La máxima media móvil de 8 h (CO)")
C = np.zeros((n, 2), np.float32)
C[100:108, 0] = 800            # 8 horas seguidas a 800: 800
C[200:204, 1] = 800            # 4 horas a 800: 400, ni una ventana de 8 h llena
v = N.estadistico(col("norma_8h", gas="CO"), C, fines)
ok("8 horas a 800: 800", abs(v[0] - 800) < 1e-6, v[0])
ok("4 horas a 800: 400", abs(v[1] - 400) < 1e-6, v[1])
C2 = np.zeros((n, 1), np.float32)
C2[:8, 0] = 800                # la primera ventana también cuenta
ok("La primera ventana del periodo cuenta", abs(N.estadistico(col("norma_8h", gas="CO"), C2, fines)[0] - 800) < 1e-6)

print("5. El percentil y lo básico")
C = np.arange(n, dtype=np.float32)[:, None] % 100
c = next(x for x in N.columnas("olor", "anios") if x["clave"] == "p98")
ok("P98 de la serie horaria", abs(N.estadistico(c, C, fines)[0] - np.percentile(C, 98)) < 1e-3)
ok("Media y máximo", abs(N.estadistico(col("media"), C, fines)[0] - C.mean(dtype=np.float64)) < 1e-9 and N.estadistico(col("maximo"), C, fines)[0] == 99)
ok("Un receptor al que no llega nada da 0 en todo", all(N.estadistico(col(k), np.zeros((n, 1), np.float32), fines)[0] == 0 for k in ("norma_hora", "norma_anio")))

print("6. En un periodo de días no se cuenta por año")
fd = pd.date_range("2026-10-25 00:00", periods=72, freq="h")
C = np.zeros((72, 2), np.float32)
C[[5, 30, 60], 0] = [300, 250, 100]
cols = {c["clave"]: c for c in N.columnas("NO2", "dias")}
ok("NO₂: sin media anual ni 19.ª hora", set(cols) == {"media", "maximo", "hora_max", "horas_sobre"}, sorted(cols))
ok("Horas por encima de 200", N.estadistico(cols["horas_sobre"], C, fd)[0] == 2)
ok("Hora del máximo", N.estadistico(cols["hora_max"], C, fd)[0] == 5)
ok("Sin nada, sin hora", N.estadistico(cols["hora_max"], C, fd)[1] == -1)
ok("El olor, sin P98 en un episodio", [c["clave"] for c in N.columnas("olor", "dias")] == ["media", "maximo", "hora_max"])
so2 = {c["clave"]: c for c in N.columnas("SO2", "dias")}
Cs = np.zeros((72, 1), np.float32)
Cs[:24, 0] = 130               # un día a 130: pasa de 125
ok("SO₂: la media diaria más alta, sin descontar superaciones", abs(N.estadistico(so2["norma_dia"], Cs, fd)[0] - 130) < 1e-6)
ok("Una columna de capa por magnitud como mucho", all(sum(c["capa"] == "norma" for c in N.columnas(g, l)) <= 1 for g in ("olor", "H2S", "NO2", "SO2", "CO") for l in ("anios", "dias")))

print("7. La normativa se cambia en su fichero, sin tocar el código")
original = N.RUTA
d = json.loads(original.read_text(encoding="utf-8"))
ref_antes = F.magnitud("NO2")["ref"]
d["gases"]["NO2"] = [{"valor": 100, "promedio": "hora", "superaciones_anio": 3}]
d["gases"]["H2S"] = [{"valor": 7, "promedio": "dia"}]
d["sin_limite"]["percentil"] = 95
try:
    with tempfile.TemporaryDirectory() as t:
        N.RUTA = Path(t) / "normativa.json"
        N.RUTA.write_text(json.dumps(d), encoding="utf-8")
        cols = N.columnas("NO2", "anios")
        ok("Otro límite: otra columna", [c["clave"] for c in cols] == ["media", "maximo", "norma_hora"] and cols[2]["limite"] == 100 and cols[2]["n"] == 3, cols[2]["nombre"])
        ok("La escala de color lo sigue", F.magnitud("NO2")["ref"] == 1.0 and ref_antes == 2.0)
        ok("Un gas que no tenía límite lo tiene", [c["clave"] for c in N.columnas("H2S", "anios")] == ["media", "maximo", "norma_dia"])
        ok("El percentil de los que no tienen, también", N.columnas("NH3", "anios")[2]["titulo"] == "P95", N.columnas("NH3", "anios")[2]["titulo"])
finally:
    N.RUTA = original
print("FALLOS:", fallos or "ninguno")
sys.exit(1 if fallos else 0)
