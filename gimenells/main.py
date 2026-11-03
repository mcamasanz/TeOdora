# -*- coding: utf-8 -*-
"""Lanza la aplicación de esta planta con la versión de teOdors que dice su fichero VERSION. Opciones: --dia AAAA-MM-DD --focos --planes"""
import sys
from pathlib import Path

AQUI = Path(__file__).resolve().parent
VERSION = (AQUI / "VERSION").read_text(encoding="utf-8").strip()
CARGADOR = AQUI.parent / VERSION / "cargador"
if not CARGADOR.is_dir():
    sys.exit(f"{AQUI.name} pide teOdors {VERSION}, y no está en {CARGADOR.parent}.")
sys.path.insert(0, str(CARGADOR))

from teodors import __version__, planta  # noqa: E402

if f"v{__version__}" != VERSION:
    sys.exit(f"{AQUI.name} pide teOdors {VERSION}, y la carpeta {CARGADOR.parent} es la {__version__}.")

from teodors.gui.principal import main  # noqa: E402

if __name__ == "__main__":
    planta.activar(AQUI / "entrada")
    sys.exit(main())
