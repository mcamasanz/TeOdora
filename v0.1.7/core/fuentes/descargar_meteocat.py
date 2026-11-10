# -*- coding: utf-8 -*-
"""Descarga (o completa) los datos de las estaciones de Meteocat cercanas a la planta (radio de su
bloque `estaciones`) para los años del reanálisis. Datos abiertos, sin clave. Reanudable.

    python -m teodors.fuentes.descargar_meteocat        (con la carpeta de la planta en TEODORS_PLANTA)
"""
import argparse
import sys

from teodors import planta as config
from teodors.comun import registro
from teodors.fuentes import meteocat as estaciones


def main():
    for flujo in (sys.stdout, sys.stderr):
        if flujo is not None and hasattr(flujo, "reconfigure"):
            flujo.reconfigure(encoding="utf-8", errors="replace")
    argparse.ArgumentParser(description=__doc__).parse_args()
    config.asegurar_carpetas()
    log = registro.configurar(config.DIR_LOGS, config.REGISTRO)
    emp = config.cargar_emplazamiento()
    est = estaciones.descargar(emp["lat"], emp["lon"])
    log.info(f"Descarga Meteocat terminada: {len(est)} estaciones")
    return 0


if __name__ == "__main__":
    sys.exit(main())
