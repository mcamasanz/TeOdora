# -*- coding: utf-8 -*-
"""Casos de regresión: entradas pequeñas de cada motor con sus salidas de referencia.

Cada caso vive en `auditor/casos/<motor>/<nombre>/`:

    entrada/       ficheros de entrada (control, meteorología, terreno…)
    referencia/    salidas que debe producir el motor
    caso.json      cómo se corre y qué se compara:
                   motor, descripcion, carpeta (donde se lanza, dentro de entrada),
                   ordenes (argumentos de `python -m odora <motor>`, una o varias corridas),
                   entorno (variables), salidas (ficheros que se comparan), marcas (p. ej.
                   «compilacion»), original (resultado del contraste con el programa original)
"""
import json
import os
import shutil
import subprocess
import sys
import time
from dataclasses import dataclass, field
from pathlib import Path

from .comparar import comparar_carpetas

AUDITOR = Path(__file__).resolve().parent
RAIZ = AUDITOR.parent
CASOS = AUDITOR / "casos"


@dataclass
class Caso:
    nombre: str                       # <motor>/<caso>
    ruta: Path
    motor: str
    descripcion: str
    carpeta: str
    ordenes: list
    entorno: dict
    salidas: list
    marcas: list = field(default_factory=list)
    original: str = ""

    def __str__(self):
        return self.nombre


def listar(motor=None):
    """Todos los casos (o los de un motor), ordenados por nombre."""
    out = []
    for js in sorted(CASOS.glob("*/*/caso.json")):
        m = json.loads(js.read_text(encoding="utf-8"))
        nombre = "%s/%s" % (js.parent.parent.name, js.parent.name)
        if motor and m["motor"] != motor:
            continue
        out.append(Caso(nombre=nombre, ruta=js.parent, motor=m["motor"], descripcion=m["descripcion"],
                        carpeta=m.get("carpeta", ""), ordenes=m["ordenes"], entorno=m.get("entorno", {}),
                        salidas=m["salidas"], marcas=m.get("marcas", []), original=m.get("original", "")))
    return out


# Lanza `python -m odora …` con el reloj fijado en una fecha y hora dadas (para comprobar que las
# salidas no dependen del día ni de la hora de la corrida). Los motores leen la hora con
# datetime.datetime.now(), que aquí devuelve siempre la fecha fijada.
_CON_RELOJ = """
import datetime as _d, runpy, sys
class _Reloj(_d.datetime):
    @classmethod
    def now(cls, tz=None):
        return cls(*%r)
_d.datetime = _Reloj
sys.argv = ["odora"] + sys.argv[1:]
runpy.run_module("odora", run_name="__main__", alter_sys=True)
"""


def ejecutar(caso, trabajo, reloj=None):
    """Copia las entradas del caso a `trabajo` y corre el motor. Devuelve los segundos empleados.
    Con `reloj` (un datetime), el motor ve esa fecha y hora como las de la corrida."""
    trabajo = Path(trabajo)
    if trabajo.exists():
        shutil.rmtree(trabajo)
    shutil.copytree(caso.ruta / "entrada", trabajo)
    env = dict(os.environ, PYTHONIOENCODING="utf-8", **caso.entorno)
    env["PYTHONPATH"] = str(RAIZ) + os.pathsep + env.get("PYTHONPATH", "")
    lanzar = [sys.executable, "-m", "odora"] if reloj is None else \
        [sys.executable, "-c", _CON_RELOJ % (tuple(reloj.timetuple())[:6],)]
    t0 = time.perf_counter()
    for args in caso.ordenes:
        r = subprocess.run(lanzar + [caso.motor] + list(args),
                           cwd=trabajo / caso.carpeta, env=env, capture_output=True, text=True,
                           encoding="latin-1")
        if r.returncode != 0:
            raise RuntimeError("odora %s %s terminó con código %d:\n%s" % (
                caso.motor, " ".join(args), r.returncode, (r.stderr or r.stdout)[-3000:]))
    return time.perf_counter() - t0


def diferencias(caso, trabajo):
    """Diferencias entre las salidas obtenidas en `trabajo` y la referencia (vacía si coinciden)."""
    return comparar_carpetas(caso.ruta / "referencia", trabajo, caso.salidas)
