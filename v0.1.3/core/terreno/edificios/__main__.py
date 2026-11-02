# -*- coding: utf-8 -*-
"""Traducción de BPIPPRM 04274 (US EPA, dominio público).

Uso:  python -m teodors.terreno.edificios entrada salida resumen      (los mismos argumentos que el original)
Códigos de salida: 0 terminado, 3 el original aborta en ese punto con un error de ejecución
(se escribe su mismo mensaje).
"""
import sys

from .formato import ErrorEjecucion
from .nucleo import ejecutar


def main(argv=None):
    argv = sys.argv[1:] if argv is None else argv
    if len(argv) < 3:
        sys.stdout.write(" Uso: python -m teodors.terreno.edificios entrada salida resumen\n")
        return 1
    pant = []
    try:
        pant = ejecutar(argv[0], argv[1], argv[2])
    except ErrorEjecucion as e:
        sys.stdout.write((e.forrtl or " LA TRADUCCION SE DETIENE: %s" % e) + "\n")
        return 3
    finally:
        pass
    sys.stdout.write("".join(x + "\n" for x in pant))
    return 0


if __name__ == "__main__":
    sys.exit(main())
