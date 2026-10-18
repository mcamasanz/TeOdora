# -*- coding: utf-8 -*-
"""Pruebas rápidas del paquete: todos los módulos importan, la línea de órdenes responde y los
puntos de entrada de cada motor existen. Las validaciones numéricas frente a los programas
originales viven en el repositorio de laboratorio (ver docs/validacion.md)."""
import importlib
import pkgutil
from pathlib import Path

import pytest

import lagaus
import lagaus.dispersion
from lagaus.__main__ import main

# sin `_nucleo_gen` (el núcleo numba se genera al correr y no se versiona): el número de pruebas
# no debe depender de si ya existe
MODULOS = sorted(m.name for m in pkgutil.walk_packages(lagaus.__path__, "lagaus.")
                 if not m.name.endswith(("__main__", "_nucleo_gen")))


def test_version():
    assert lagaus.__version__ == "0.1.0"


def test_se_importa_desde_core():
    # el código vive en core/ y se instala como lagaus (pyproject.toml, package-dir)
    raiz = Path(__file__).resolve().parents[3]
    assert Path(lagaus.__file__).resolve().parent == raiz / "core"
    assert Path(lagaus.dispersion.__file__).resolve().parent == raiz / "core" / "dispersion"


@pytest.mark.parametrize("nombre", MODULOS)
def test_importa(nombre):
    importlib.import_module(nombre)


@pytest.mark.parametrize("ruta, funcion", [
    ("lagaus.terreno.relieve.__main__", "ejecutar"),
    ("lagaus.terreno.superficie.__main__", "main"),
    ("lagaus.terreno.edificios.__main__", "main"),
    ("lagaus.terreno.geofisica.principal", "ejecutar"),
    ("lagaus.meteo.capa_limite.__main__", "ejecutar"),
    ("lagaus.meteo.viento3d.principal", "ejecutar"),
    ("lagaus.dispersion.penacho.principal", "ejecutar"),
    ("lagaus.dispersion.puffs.principal", "ejecutar"),
])
def test_puntos_de_entrada(ruta, funcion):
    assert callable(getattr(importlib.import_module(ruta), funcion))


def test_linea_de_ordenes():
    assert main(["--version"]) == 0
    assert main(["motor_que_no_existe"]) == 1
