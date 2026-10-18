# -*- coding: utf-8 -*-
"""Configuración común de las pruebas.

- Marca `compilacion`: pruebas que compilan el núcleo numba la primera vez (pueden tardar minutos
  sin caché). Se ejecutan siempre, pero quedan fuera del límite de tiempo por prueba.
- Si la variable AUDITOR_TIEMPOS apunta a un fichero, se guarda en él la duración de cada prueba
  y sus marcas: el auditor lo usa para la regla de rapidez.
- El paquete `lagaus` tiene que importarse desde la carpeta core/ de este repositorio (instalado
  con `pip install -e .`); si no, se probaría otra copia y las pruebas se paran.
"""
import json
import os
import sys
from pathlib import Path

import pytest

RAIZ = Path(__file__).resolve().parents[2]
if str(RAIZ) not in sys.path:
    sys.path.insert(0, str(RAIZ))

_TIEMPOS = {}


def instalacion():
    """Texto del problema si `lagaus` no se importa desde core/ de este repositorio; "" si sí."""
    try:
        import lagaus
    except ImportError:
        return "no se encuentra el paquete lagaus: instala este repositorio con «pip install -e .»"
    origen = Path(lagaus.__file__).resolve().parent
    if origen != RAIZ / "core":
        return ("lagaus se importa desde %s y no desde %s: instala este repositorio con "
                "«pip install -e .»" % (origen, RAIZ / "core"))
    return ""


def pytest_configure(config):
    config.addinivalue_line("markers", "compilacion: compila el núcleo numba (fuera del límite de tiempo)")
    problema = instalacion()
    if problema:
        pytest.exit(problema, returncode=4)


def pytest_runtest_logreport(report):
    if report.when == "call":
        _TIEMPOS[report.nodeid] = {"segundos": round(report.duration, 3), "resultado": report.outcome,
                                   "marcas": sorted(k for k in report.keywords if k == "compilacion")}


def pytest_sessionfinish(session, exitstatus):
    ruta = os.environ.get("AUDITOR_TIEMPOS")
    if ruta:
        Path(ruta).write_text(json.dumps(_TIEMPOS, ensure_ascii=False, indent=1), encoding="utf-8")
