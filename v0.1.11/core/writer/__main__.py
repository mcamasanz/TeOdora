# -*- coding: utf-8 -*-
"""python -m teodors.writer CARPETA_DEL_CASO [--planta CARPETA] [--html] [--png] [--sin-viento]: el informe en PDF de un caso del reanálisis."""
import sys

from teodors.writer.informe import main

sys.exit(main())
