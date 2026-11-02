# -*- coding: utf-8 -*-
"""Descarga (o completa) el reanálisis ERA5 de la planta: superficie y perfil vertical de los
años de config.REANALISIS_ANIOS. Es REANUDABLE: si se corta, al relanzarlo solo pide lo que
falta. Deja el registro en config.DIR_LOGS.

    python -m teodors.fuentes.descargar_era5        (con la carpeta de la planta en TEODORS_PLANTA)
"""
import argparse
import sys
import time

from teodors import planta as config
from teodors.comun import registro
from teodors.fuentes import era5 as meteo


def main():
    for flujo in (sys.stdout, sys.stderr):
        if flujo is not None and hasattr(flujo, "reconfigure"):
            flujo.reconfigure(encoding="utf-8", errors="replace")
    argparse.ArgumentParser(description=__doc__).parse_args()
    config.asegurar_carpetas()
    log = registro.configurar(config.DIR_LOGS, config.REGISTRO)
    emp = config.cargar_emplazamiento()
    for pasada in range(1, 4):              # lo que falle (red, CDS) se reintenta solo
        try:
            r = meteo.descargar_reanalisis(emp["lat"], emp["lon"])
        except meteo.SinLicencia:
            return 2
        if not r["fallidos"]:
            log.info(f"Descarga ERA5 terminada: todo completo (pasada {pasada})")
            return 0
        log.warning(f"Pasada {pasada}: quedan {len(r['fallidos'])} peticiones; nueva pasada "
                    f"en 10 min")
        time.sleep(600)
    log.info(f"Descarga ERA5 terminada con {len(r['fallidos'])} peticiones sin completar: "
             f"relanzar el script")
    return 1


if __name__ == "__main__":
    sys.exit(main())
