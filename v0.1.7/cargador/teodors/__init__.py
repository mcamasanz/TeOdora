# -*- coding: utf-8 -*-
"""Cargador de ESTA versión de teOdors: con la carpeta `cargador` en el camino de Python, «import teodors» y «python -m teodors» usan el
core/ de al lado, sin instalar nada. Así una planta elige su versión con el fichero VERSION y varias versiones conviven en el repositorio.

La caché de numba va a una carpeta temporal, fuera de OneDrive o de una unidad de red, salvo que ya se haya fijado NUMBA_CACHE_DIR.
"""
import os
import tempfile

_CORE = os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))), "core")
os.environ.setdefault("NUMBA_CACHE_DIR", os.path.join(tempfile.gettempdir(), "teodors_numba"))

__path__ = [_CORE]                       # los submódulos (teodors.meteo, …) se buscan en core/
__file__ = os.path.join(_CORE, "__init__.py")
with open(__file__, encoding="utf-8") as _f:
    exec(compile(_f.read(), __file__, "exec"))
