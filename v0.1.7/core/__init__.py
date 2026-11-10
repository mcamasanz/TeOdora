# -*- coding: utf-8 -*-
"""teOdors — motores propios de terreno, meteorología y dispersión atmosférica.

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

Utilidades (no son motores):
    comun                  UTM y convergencia, registro, formatos de número, procesos hijos, imágenes
                           para mapas web y escalas de color
    planta                 lo que teOdors sabe de un emplazamiento, leído de su carpeta (los motores
                           no lo usan)
    fuentes                descargas de terreno, usos, edificios, estaciones, ERA5 y GFS a la carpeta
                           de datos de la planta; son servicios de España, salvo ERA5 y GFS
    metricas               validación del viento frente a las estaciones: métricas, rosas y control
                           de calidad
    casos                  los casos de una planta: une su carpeta, sus datos y los motores (viento 3D
                           de un mes o una serie, columnas de GFS, malla de receptores)
    operacion              de los focos y los planes de una planta a sus resultados, sin interfaz:
                           unidades, normativa, periodos, simulación sin motor, imágenes, penacho en 3D
    mos                    corrección estadística de la predicción de GFS en cada estación; su mejora de
                           dirección es local a la estación
    writer                 el informe en PDF de un caso del reanálisis, con las imágenes de la propia app: datos, textos y páginas
                           sin Qt; capturas y PDF, con la interfaz, al usarlos
    gui                    la aplicación de escritorio de una planta (`teodors[gui]`: PySide6 y folium): lo de cada
                           sitio sale de su carpeta, y nada fuera de este paquete carga Qt
    meteo.viento3d.almacen almacén comprimido (.cmz) del fichero de viento 3D
    meteo.viento_local     viento alrededor de los edificios. NO VALIDADO: solo enseña su efecto
    preparacion            entradas y control de los motores escritos desde cero (viento3d,
                           puffs) y malla de receptores anidada

Cada motor se puede lanzar por línea de órdenes: `python -m teodors <motor> [argumentos]`.
"""
__version__ = "0.1.7"
__fecha__ = "2026-10-23"

MOTORES = ("relieve", "superficie", "edificios", "geofisica", "capa_limite", "viento3d", "penacho",
           "puffs")
