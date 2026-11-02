# -*- coding: utf-8 -*-
"""Lanzar procesos hijos que usen este mismo teOdors."""
import os
import sys


def entorno(**extra):
    """Entorno de un proceso hijo: el mismo camino de Python que este proceso (si no, `python -m teodors`
    podría encontrar otra copia) y salida en UTF-8. `extra`: variables que añadir o cambiar."""
    env = dict(os.environ, PYTHONPATH=os.pathsep.join(os.path.abspath(p) for p in sys.path if p),
               PYTHONIOENCODING="utf-8")
    env.pop("PYTHONHOME", None)
    env.update(extra)
    return env
