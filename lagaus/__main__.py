# -*- coding: utf-8 -*-
"""Línea de órdenes de lagaus: lanza cualquier motor con su fichero de control.

    python -m lagaus <motor> [argumentos]

    python -m lagaus relieve     [control [salida]]          cotas y altura de colina
    python -m lagaus superficie  [control]                   rugosidad, Bowen y albedo
    python -m lagaus edificios   entrada salida resumen      dimensiones de edificio
    python -m lagaus geofisica   [control]                   malla de usos y terreno
    python -m lagaus capa_limite [control]                   meteorología de capa límite
    python -m lagaus viento3d    [control]                   campo de viento 3D
    python -m lagaus penacho     [control [salida]]          dispersión gaussiana
    python -m lagaus puffs       [control]                   dispersión por puffs

Se ejecuta en la carpeta del caso. Códigos de salida: 0 terminado (los errores del caso van a
su fichero de salida), 1 orden desconocida, 2 opción fuera del alcance del motor.
"""
import sys

from . import MOTORES, __version__


def _fuera(motor, e):
    print("lagaus %s: opción fuera de alcance: %s" % (motor, e), file=sys.stderr)
    return 2


def main(argv=None):
    argv = list(sys.argv[1:] if argv is None else argv)
    if not argv or argv[0] in ("-h", "--help"):
        print(__doc__)
        return 0 if argv else 1
    if argv[0] in ("-V", "--version"):
        print("lagaus", __version__)
        return 0
    motor, args = argv[0].lower(), argv[1:]
    sys.argv = [sys.argv[0]] + args
    if motor == "relieve":
        from .terreno.relieve.__main__ import main as m
        return m(args)
    if motor == "superficie":
        from .terreno.superficie.__main__ import main as m
        return m(args)
    if motor == "edificios":
        from .terreno.edificios.__main__ import main as m
        return m(args)
    if motor == "capa_limite":
        from .meteo.capa_limite.__main__ import main as m
        return m(args)
    if motor == "penacho":
        from .dispersion.penacho.estado import NoTraducido
        from .dispersion.penacho.principal import ejecutar
        try:
            return ejecutar(args)
        except NoTraducido as e:
            return _fuera(motor, e)
    if motor == "geofisica":
        from .terreno.geofisica.principal import NoImplementado, ejecutar
        try:
            ejecutar(args or None)
            return 0
        except NoImplementado as e:
            return _fuera(motor, e)
    if motor == "viento3d":
        from .meteo.viento3d.principal import NoImplementado, ejecutar
        try:
            ejecutar(args or None)
            return 0
        except NoImplementado as e:
            return _fuera(motor, e)
    if motor == "puffs":
        from .dispersion.puffs.entrada import NoImplementado
        from .dispersion.puffs.principal import ejecutar
        try:
            ejecutar(args[0] if args else "CALPUFF.INP")
            return 0
        except NoImplementado as e:
            return _fuera(motor, e)
    print("lagaus: motor desconocido «%s». Motores: %s" % (motor, ", ".join(MOTORES)), file=sys.stderr)
    return 1


if __name__ == "__main__":
    sys.exit(main())
