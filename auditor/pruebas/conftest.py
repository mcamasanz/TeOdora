# -*- coding: utf-8 -*-
"""Configuración común de las pruebas.

- Marca `compilacion`: pruebas que compilan el núcleo numba la primera vez (pueden tardar minutos
  sin caché). Se ejecutan siempre, pero quedan fuera del límite de tiempo por prueba.
- Si la variable AUDITOR_TIEMPOS apunta a un fichero, se guarda en él la duración de cada prueba
  y sus marcas: el auditor lo usa para la regla de rapidez.
"""
import json
import os
import sys
from pathlib import Path

RAIZ = Path(__file__).resolve().parents[2]
if str(RAIZ) not in sys.path:
    sys.path.insert(0, str(RAIZ))

_TIEMPOS = {}


def pytest_configure(config):
    config.addinivalue_line("markers", "compilacion: compila el núcleo numba (fuera del límite de tiempo)")


def pytest_runtest_logreport(report):
    if report.when == "call":
        _TIEMPOS[report.nodeid] = {"segundos": round(report.duration, 3), "resultado": report.outcome,
                                   "marcas": sorted(k for k in report.keywords if k == "compilacion")}


def pytest_sessionfinish(session, exitstatus):
    ruta = os.environ.get("AUDITOR_TIEMPOS")
    if ruta:
        Path(ruta).write_text(json.dumps(_TIEMPOS, ensure_ascii=False, indent=1), encoding="utf-8")
