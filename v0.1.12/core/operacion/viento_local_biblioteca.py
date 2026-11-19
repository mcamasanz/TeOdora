# -*- coding: utf-8 -*-
"""Rehace la biblioteca del viento local de la planta activa, con el bloque `viento_local` de su planta.json. Solo hace falta si cambian
los edificios. ⚠️ No validado: enseña el efecto de los edificios; no da valores para un sensor y el penacho no lo usa.

    python -m teodors.operacion.viento_local_biblioteca [--lidar <fichero>] [--paso 10]      (con TEODORS_PLANTA en la carpeta de la planta)
"""
import sys

from teodors import planta
from teodors.meteo.viento_local import biblioteca

def main(argv=None):
    return biblioteca.main(argv, activa=planta.actual())


if __name__ == "__main__":
    sys.exit(main())
