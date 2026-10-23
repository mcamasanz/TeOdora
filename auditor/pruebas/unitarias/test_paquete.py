# -*- coding: utf-8 -*-
"""Pruebas rápidas del paquete: todos los módulos importan, la línea de órdenes responde y los
puntos de entrada de cada motor existen. Las validaciones numéricas frente a los programas
originales viven en el repositorio de laboratorio (ver docs/validacion.md)."""
import importlib
import pkgutil
from pathlib import Path

import pytest

import odora
import odora.dispersion
from odora.__main__ import main

# sin `_nucleo_gen` (el núcleo numba se genera al correr y no se versiona): el número de pruebas
# no debe depender de si ya existe
MODULOS = sorted(m.name for m in pkgutil.walk_packages(odora.__path__, "odora.")
                 if not m.name.endswith(("__main__", "_nucleo_gen")))


def test_version():
    assert odora.__version__ == "0.1.2"


def test_se_importa_desde_core():
    # el código vive en core/ y se instala como odora (pyproject.toml, package-dir)
    raiz = Path(__file__).resolve().parents[3]
    assert Path(odora.__file__).resolve().parent == raiz / "core"
    assert Path(odora.dispersion.__file__).resolve().parent == raiz / "core" / "dispersion"


@pytest.mark.parametrize("nombre", MODULOS)
def test_importa(nombre):
    importlib.import_module(nombre)


@pytest.mark.parametrize("ruta, funcion", [
    ("odora.terreno.relieve.__main__", "ejecutar"),
    ("odora.terreno.superficie.__main__", "main"),
    ("odora.terreno.edificios.__main__", "main"),
    ("odora.terreno.geofisica.principal", "ejecutar"),
    ("odora.meteo.capa_limite.__main__", "ejecutar"),
    ("odora.meteo.viento3d.principal", "ejecutar"),
    ("odora.dispersion.penacho.principal", "ejecutar"),
    ("odora.dispersion.puffs.principal", "ejecutar"),
])
def test_puntos_de_entrada(ruta, funcion):
    assert callable(getattr(importlib.import_module(ruta), funcion))


def test_linea_de_ordenes():
    assert main(["--version"]) == 0
    assert main(["motor_que_no_existe"]) == 1
