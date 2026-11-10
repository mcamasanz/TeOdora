# -*- coding: utf-8 -*-
"""Crea la carpeta de una planta nueva con esta versión de teOdors, sin instalar nada:

    python v0.1.7/nueva_planta.py <carpeta> --nombre "Mi planta" --lat 41.63 --lon 0.38 [--corine CLC2018_ES.gpkg] [--descargar]
"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent / "cargador"))

from teodors.planta.nueva import main  # noqa: E402

if __name__ == "__main__":
    sys.exit(main())
