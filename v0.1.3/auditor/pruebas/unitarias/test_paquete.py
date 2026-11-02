# -*- coding: utf-8 -*-
"""Pruebas rápidas del paquete: todos los módulos importan, la línea de órdenes responde y los
puntos de entrada de cada motor existen. Las validaciones numéricas frente a los programas
originales viven en el repositorio de laboratorio (ver docs/validacion.md)."""
import importlib
import pkgutil
from importlib.util import find_spec
from pathlib import Path

import pytest

import teodors
import teodors.dispersion
from teodors.__main__ import main

# sin `_nucleo_gen` (el núcleo numba se genera al correr y no se versiona): el número de pruebas
# no debe depender de si ya existe
MODULOS = sorted(m.name for m in pkgutil.walk_packages(teodors.__path__, "teodors.")
                 if not m.name.endswith(("__main__", "_nucleo_gen")))


# La interfaz necesita un extra aparte: sin él, sus módulos con Qt no se importan, y solo esos, con su marca; no es un salto dentro de la prueba, que contaría como fallo. Lo demás se importa siempre,
# también `teodors.gui` y los módulos de la interfaz que no cargan Qt. Que nada de lo demás lo cargue, sin que nadie lo instale, lo comprueba test_gui.py en un proceso aparte.
GUI_SIN_QT = ("teodors.gui", "teodors.gui.penacho_3d", "teodors.gui.principal", "teodors.gui.web")
HAY_GUI = find_spec("PySide6") is not None and find_spec("folium") is not None
sin_gui = pytest.mark.skipif(not HAY_GUI, reason="sin teodors[pruebas_gui]")


def _modulo(nombre):
    return pytest.param(nombre, marks=sin_gui) if nombre.startswith("teodors.gui.") and nombre not in GUI_SIN_QT else nombre


def test_version():
    # el mismo número en el paquete y en pyproject.toml; el de la carpeta lo mira la regla R7
    raiz = Path(__file__).resolve().parents[3]
    assert 'version = "%s"' % teodors.__version__ in (raiz / "pyproject.toml").read_text(encoding="utf-8")


def test_se_importa_desde_core():
    # el código vive en core/ y se instala como teOdors (pyproject.toml, package-dir)
    raiz = Path(__file__).resolve().parents[3]
    assert Path(teodors.__file__).resolve().parent == raiz / "core"
    assert Path(teodors.dispersion.__file__).resolve().parent == raiz / "core" / "dispersion"


@pytest.mark.parametrize("nombre", [_modulo(m) for m in MODULOS])
def test_importa(nombre):
    importlib.import_module(nombre)


@pytest.mark.parametrize("ruta, funcion", [
    ("teodors.terreno.relieve.__main__", "ejecutar"),
    ("teodors.terreno.superficie.__main__", "main"),
    ("teodors.terreno.edificios.__main__", "main"),
    ("teodors.terreno.geofisica.principal", "ejecutar"),
    ("teodors.meteo.capa_limite.__main__", "ejecutar"),
    ("teodors.meteo.viento3d.principal", "ejecutar"),
    ("teodors.dispersion.penacho.principal", "ejecutar"),
    ("teodors.dispersion.puffs.principal", "ejecutar"),
])
def test_puntos_de_entrada(ruta, funcion):
    assert callable(getattr(importlib.import_module(ruta), funcion))


def test_linea_de_ordenes():
    assert main(["--version"]) == 0
    assert main(["motor_que_no_existe"]) == 1
