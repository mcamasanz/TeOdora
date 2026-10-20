# -*- coding: utf-8 -*-
"""odora — motores propios de terreno, meteorología y dispersión atmosférica.

Del latín *odor* (olor): nace para los estudios de impacto por olores. Reúne las dos familias de
modelos de dispersión, el penacho gaussiano estacionario (`dispersion.penacho`) y los puffs
lagrangianos que viajan con el viento (`dispersion.puffs`), junto con todo lo que necesitan:
terreno, superficie, edificios, meteorología de capa límite y campo de viento 3D.

Paquetes:
    terreno.relieve        cotas de receptores y fuentes, altura de colina
    terreno.superficie     rugosidad, Bowen y albedo desde el uso del suelo
    terreno.edificios      dimensiones de edificio por dirección (estelas)
    terreno.geofisica      malla de usos del suelo y terreno para el campo de viento
    meteo.capa_limite      meteorología de capa límite para el penacho
    meteo.viento3d         campo de viento 3D diagnóstico
    dispersion.penacho     dispersión gaussiana estacionaria
    dispersion.puffs       dispersión lagrangiana por puffs

Cada motor se puede lanzar por línea de órdenes: `python -m odora <motor> [argumentos]`.
"""
__version__ = "0.1.1"
__fecha__ = "2026-10-20"

MOTORES = ("relieve", "superficie", "edificios", "geofisica", "capa_limite", "viento3d", "penacho",
           "puffs")
