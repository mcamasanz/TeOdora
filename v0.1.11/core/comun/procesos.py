# -*- coding: utf-8 -*-
"""Lanzar procesos hijos que usen este mismo teOdors: su orden (`orden`) y su entorno (`entorno`).

En un ejecutable congelado (Nuitka o PyInstaller), `sys.executable` es el propio .exe, que no es un intérprete y no entiende `-m`: se lanza
a sí mismo con `HIJO` delante, y su punto de entrada lo despacha con `despachar_hijo` antes de abrir la interfaz (usuario, 2026-11-07,
para el instalador de La Galera). Fuera de un ejecutable, la orden es la de siempre: `python -m <módulo> …`.
"""
import importlib
import os
import sys

HIJO = "--teodors-hijo"          # marca de un proceso hijo en un ejecutable congelado: <exe> --teodors-hijo <módulo> [argumentos]
_EXE = None                      # el .exe real, guardado por `despachar_hijo` ANTES de cambiar sys.argv (si no, un hijo no puede lanzar otro)


def congelado():
    """¿Corre como ejecutable compilado? (`sys.frozen` en PyInstaller; `__compiled__` en los módulos que compila Nuitka)."""
    return bool(getattr(sys, "frozen", False)) or "__compiled__" in globals()


def orden(modulo, *args):
    """La orden para lanzar `python -m <modulo> <args>` con este mismo teOdors: [sys.executable, "-m", modulo, …] o, en un ejecutable
    congelado, [<exe>, HIJO, modulo, …]. Los argumentos, como texto.

    OJO (congelado con Nuitka): `sys.executable` NO es el .exe, sino un `python.exe` fantasma dentro del .dist que no existe;
    el .exe real es `sys.argv[0]`. Por eso, congelado, se usa `sys.argv[0]` (si no, subprocess da WinError 2). En un hijo ya despachado,
    `sys.argv[0]` es el nombre del módulo (lo cambia `despachar_hijo`): se usa el .exe que guardó al despachar. Así un motor lanzado por la
    app puede lanzar otro (`viento_periodo` → `viento3d`, `respuestas` → `puffs`: todo el episodio en el ejecutable)."""
    if congelado():
        return [_EXE or os.path.abspath(sys.argv[0]), HIJO, modulo, *map(str, args)]
    return [sys.executable, "-m", modulo, *map(str, args)]


def despachar_hijo(argv=None):
    """En el punto de entrada de un ejecutable, ANTES de la interfaz: si se lanzó con `HIJO`, corre el `main()` de ese módulo (el de
    `teodors.__main__` para «teodors»), como haría `python -m`, y sale con su código. Si no, no hace nada y devuelve False. Sin runpy:
    con módulos compilados no siempre funciona."""
    global _EXE
    argv = sys.argv if argv is None else argv
    if len(argv) < 3 or argv[1] != HIJO:
        return False
    _EXE = os.path.abspath(argv[0])                                  # el .exe, antes de que sys.argv pase a ser el del módulo
    modulo, args = argv[2], list(argv[3:])
    m = importlib.import_module("teodors.__main__" if modulo == "teodors" else modulo)
    sys.argv = [modulo, *args]
    sys.exit(m.main() or 0)


def entorno(**extra):
    """Entorno de un proceso hijo: el mismo camino de Python que este proceso (si no, `python -m teodors`
    podría encontrar otra copia) y salida en UTF-8. `extra`: variables que añadir o cambiar. En un ejecutable congelado, sin PYTHONPATH:
    teOdors va compilado dentro, y una copia en disco podría tapar la suya."""
    env = dict(os.environ, PYTHONPATH=os.pathsep.join(os.path.abspath(p) for p in sys.path if p),
               PYTHONIOENCODING="utf-8")
    if congelado():
        env.pop("PYTHONPATH")
    env.pop("PYTHONHOME", None)
    env.update(extra)
    return env
