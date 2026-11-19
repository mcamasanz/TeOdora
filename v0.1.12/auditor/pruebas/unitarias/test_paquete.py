# -*- coding: utf-8 -*-
"""Pruebas rápidas del paquete: todos los módulos importan, la línea de órdenes responde y los
puntos de entrada de cada motor existen; el paquete instalable lleva todos sus subpaquetes y el código compila en el Python mínimo que
declara. Las validaciones numéricas frente a los programas originales viven en el repositorio de laboratorio (ver docs/validacion.md)."""
import ast
import importlib
import io
import pkgutil
import sys
import tokenize
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


# ------------------------------------------------------------------------------ el paquete instalable (v0.1.10)
CORE = Path(teodors.__file__).resolve().parent                  # core/ de esta versión (con el cargador o instalado en modo editable)


def test_pyproject_lista_todos_los_subpaquetes():
    # pyproject.toml lista los paquetes a mano: en la 0.1.8 faltaban los cuatro tipos del writer (episodio, prediccion, reanalisis_caso y
    # reanalisis_comparacion) y una instalación no editable, como la del ejecutable, se quedaba sin informes. Todo core/**/__init__.py, dentro
    import tomllib
    lista = set(tomllib.loads((CORE.parent / "pyproject.toml").read_text(encoding="utf-8"))["tool"]["setuptools"]["packages"])
    reales = {".".join(("teodors",) + p.parent.relative_to(CORE).parts) for p in CORE.rglob("__init__.py") if "__pycache__" not in p.parts}
    assert not reales - lista, f"faltan en pyproject.toml: {sorted(reales - lista)}"
    assert not lista - reales, f"sobran en pyproject.toml: {sorted(lista - reales)}"


def test_la_interfaz_instala_lo_que_necesita_la_prediccion():
    # la predicción (v0.1.12) corrige el viento con los modelos del MOS, y abrirlos pide scikit-learn y joblib: sin ellos en `gui` y
    # `gui3d`, quien instala la app con pip ve un error al simular el viento de la predicción
    import tomllib
    extras = tomllib.loads((CORE.parent / "pyproject.toml").read_text(encoding="utf-8"))["project"]["optional-dependencies"]
    for extra in ("gui", "gui3d"):
        assert {"scikit-learn", "joblib"} <= set(extras[extra]), f"faltan en el extra {extra}"


def _comilla(literal):
    s = literal.lstrip("rRbBfFuU")
    return s[:3] if s[:3] in ('"""', "'''") else s[:1]


def _choca(dentro, fuera):
    """¿La comilla `dentro` cierra en 3.11 la cadena `fuera`? Con comilla simple, cualquiera del mismo carácter; con triple, la misma triple."""
    return dentro[0] == fuera[0] and (len(fuera) == 1 or dentro == fuera)


def incompatibles_311(texto):
    """Las f-strings que Python 3.11 no acepta (son de 3.12, PEP 701): una cadena dentro de la expresión de una f-string con su MISMA comilla,
    o una barra invertida en la parte de expresión. [(línea, motivo)]. Necesita el tokenizador de 3.12, que separa las partes de una f-string."""
    malos, pila = [], []
    for tok in tokenize.generate_tokens(io.StringIO(texto).readline):
        if tok.type == tokenize.FSTRING_START:
            q = _comilla(tok.string)
            if any(_choca(q, p) for p in pila):
                malos.append((tok.start[0], "f-string anidada con la misma comilla"))
            pila.append(q)
        elif tok.type == tokenize.FSTRING_END:
            pila.pop()
        elif tok.type == tokenize.STRING and pila:
            if any(_choca(_comilla(tok.string), p) for p in pila):
                malos.append((tok.start[0], "cadena con la misma comilla que la f-string que la contiene"))
            if "\\" in tok.string:
                malos.append((tok.start[0], "barra invertida en la expresión de una f-string"))
        elif tok.type == tokenize.FSTRING_MIDDLE and len(pila) > 1 and "\\" in tok.string:
            malos.append((tok.start[0], "barra invertida en una f-string anidada"))
    return malos


solo_312 = pytest.mark.skipif(sys.version_info < (3, 12), reason="el tokenizador de 3.11 no separa las f-strings; en 3.11 ya lo vigila R1 al compilar")


@solo_312
@pytest.mark.parametrize("codigo, mal", [
    ("x = f'{d[\"a\"]}'", False),                       # otra comilla: vale en 3.11
    ("x = f\"\"\"{d[\"a\"]}\"\"\"", False),             # dentro de una triple, la simple del mismo carácter vale
    ("x = f'{d['a']}'", True),                          # la misma comilla: solo 3.12
    ("x = f\"{f'{y}' + f'{d['a']}'}\"", True),         # f-string anidada que repite la comilla de la suya
    ("x = f'{chr(10).join(\"a\\nb\")}'", True),         # barra invertida en la expresión: solo 3.12
])
def test_el_detector_de_f_strings_de_3_12(codigo, mal):
    assert bool(incompatibles_311(codigo)) is mal


@solo_312
def test_el_codigo_compila_en_python_3_11():
    # requires-python >= 3.11 y el CI audita con 3.11, pero la 0.1.7-0.1.8 se escribieron con 3.12, que admite f-strings dentro de f-strings
    # con las mismas comillas: el núcleo no compilaba en 3.11 y el CI estuvo en rojo desde la 0.1.7. R1 compila con el Python que corre el auditor
    # (3.12 en el equipo de desarrollo), así que no lo veía: esto lo ve con cualquier Python >= 3.12
    malos = [f"{f.relative_to(CORE.parent)}:{linea}: {motivo}" for f in sorted(CORE.parent.rglob("*.py"))
             if "__pycache__" not in f.parts and "_nucleo_gen" not in f.name
             for linea, motivo in incompatibles_311(f.read_text(encoding="utf-8"))]
    assert malos == [], "\n".join(malos)

# ---------------------------------------------------------------------------------------------
# Huecos de señal que no sobreviven al compilado (2026-11-18)
# ---------------------------------------------------------------------------------------------
def huecos_que_rompen_compilados(texto):
    """Conexiones a una `lambda` con argumentos OBLIGATORIOS y otros con VALOR POR DEFECTO.

    Es la forma de toda la vida de capturar la variable de un bucle (`lambda si, c=clave: …`), y en
    Python funciona, pero NO sobrevive al compilado: en el `.exe` (Nuitka + PySide6), Qt no acierta
    con cuántos argumentos pasarle y la llama sin ninguno, así que el hueco revienta con un
    «TypeError: missing 1 required positional argument» y el botón no hace nada. Pasó el 2026-11-18
    con los botones de capa del mapa, y en la interfaz no se ve hasta que alguien lo pulsa.
    En su lugar, una fábrica que devuelva la lambda (ver `gui.panel.Panel._capa_nombrada`): así la
    variable se captura por cierre y la lambda solo declara los argumentos de la señal.
    """
    malos = []
    for n in ast.walk(ast.parse(texto)):
        if not (isinstance(n, ast.Call) and isinstance(n.func, ast.Attribute)
                and n.func.attr == "connect" and n.args):
            continue
        hueco = n.args[0]
        if not isinstance(hueco, ast.Lambda):
            continue
        n_def = len(hueco.args.defaults)
        if n_def and len(hueco.args.args) > n_def and hueco.args.vararg is None:
            obligatorios = [a.arg for a in hueco.args.args[:len(hueco.args.args) - n_def]]
            malos.append((hueco.lineno, f"lambda con argumento obligatorio ({', '.join(obligatorios)}) "
                                        "y otro con valor por defecto"))
    return malos


@pytest.mark.parametrize("codigo, mal", [
    ("b.clicked.connect(lambda si: f(si))", False),              # solo obligatorios: funciona compilado
    ("b.clicked.connect(lambda: f())", False),                   # sin argumentos: funciona
    ("b.clicked.connect(lambda *a, c=1: f(c))", False),          # *args: funciona
    ("b.clicked.connect(self._metodo)", False),                  # un método, no una lambda
    ("b.clicked.connect(hacer(clave))", False),                  # la fábrica, que es lo que hay que usar
    ("b.clicked.connect(lambda si, c=1: f(c, si))", True),       # el patrón que rompe
    ("s.rangeChanged.connect(lambda _a, b, v=v: g(v, b))", True),  # dos obligatorios y uno por defecto
    ("x = lambda si, c=1: 0", False),                            # no es una conexión: da igual
])
def test_el_detector_de_huecos_que_rompen_compilados(codigo, mal):
    assert bool(huecos_que_rompen_compilados(codigo)) is mal


def test_ninguna_senal_se_conecta_a_una_lambda_con_valores_por_defecto():
    malos = [f"{f.relative_to(CORE.parent)}:{linea}: {motivo}" for f in sorted(CORE.rglob("*.py"))
             if "__pycache__" not in f.parts and "_nucleo_gen" not in f.name
             for linea, motivo in huecos_que_rompen_compilados(f.read_text(encoding="utf-8"))]
    assert malos == [], "\n".join(malos)
