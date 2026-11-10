# -*- coding: utf-8 -*-
"""Lanza la aplicación de esta planta con la versión de teOdors que dice su fichero VERSION. Opciones: --dia AAAA-MM-DD --focos --planes

Compilado en un ejecutable (Nuitka o PyInstaller), teOdors va dentro y el .exe tiene que estar en esta carpeta, junto a entrada/, viento/,
dispersion/ y datos/. Ahí, la app también se lanza a sí misma para correr los motores: `procesos.despachar_hijo` los atiende antes que nada.
"""
import os
import sys
from pathlib import Path

CONGELADO = bool(getattr(sys, "frozen", False)) or "__compiled__" in globals()
# la carpeta de la planta: la de este fichero o, compilado, la del .exe (__file__ apunta a otro sitio)
AQUI = Path(os.path.abspath(sys.argv[0])).parent if CONGELADO else Path(__file__).resolve().parent
VERSION = (AQUI / "VERSION").read_text(encoding="utf-8").strip()
if not CONGELADO:
    CARGADOR = AQUI.parent / VERSION / "cargador"
    if not CARGADOR.is_dir():
        sys.exit(f"{AQUI.name} pide teOdors {VERSION}, y no está en {CARGADOR.parent}.")
    sys.path.insert(0, str(CARGADOR))

from teodors.comun import procesos  # noqa: E402

procesos.despachar_hijo()             # un motor lanzado por la propia app: corre y sale, sin la interfaz ni activar la planta (la hereda)

from teodors import __version__, planta  # noqa: E402

if f"v{__version__}" != VERSION:
    sys.exit(f"{AQUI.name} pide teOdors {VERSION}, y {'este programa' if CONGELADO else f'la carpeta {CARGADOR.parent}'} es la {__version__}.")

from teodors.gui.principal import main  # noqa: E402

if __name__ == "__main__":
    planta.activar(AQUI / "entrada")
    sys.exit(main())
