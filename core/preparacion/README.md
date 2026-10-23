# `odora.preparacion` — preparación de casos

<!-- manual -->
## Qué hace

Escribe las entradas de los motores a partir de datos ya descargados (tablas de pandas, matrices de
numpy) y da utilidades para su salida. No es un motor ni equivale a ningún programa: es el código
que cada proyecto repetía para montar sus casos. Necesita pandas (`pip install odora[preparacion]`).

Los ficheros de control se escriben **desde cero**, solo con asignaciones `! NOMBRE = valor !` y
marcas `!END!`: los lectores de odora ignoran todo lo que va fuera de los signos de exclamación,
así que el texto explicativo de una plantilla no hace falta. El orden sí cuenta (los grupos se
reconocen por su primera variable y algunas variables se repiten), y por eso las asignaciones de
partida se guardan EN ORDEN (`viento3d/parametros.py`) y cada caso solo cambia, apaga o inserta
entradas (`control.Control`).

## Uso

```python
import pandas as pd
from odora.preparacion.viento3d import control, geofisica, nubes, pronostico

m = geofisica.malla(Z, U, transform, 400.0)              # terreno fino de 25 m -> celdas de 400 m
geofisica.escribir(caso / "geo.dat", m, zona=31, mar=mascara_mar)
pronostico.escribir_columna(caso / "pronostico3d.dat", perfiles, superficie, m["ext"], punto,
                            horas, "EPSG:25831")
nubes.escribir(caso / "nubes.dat", superficie, horas, m["nx"], m["ny"])
control.escribir(caso / "viento3d.inp", m, pd.Timestamp("2024-07-01"), 48, 31,
                 (0, 20, 40, 80, 160, 300, 600, 1000, 1500, 2200, 3000, 4000, 5000))
# python -m odora viento3d viento3d.inp   (en la carpeta del caso)
```

## Validación
Pruebas en `auditor/pruebas/unitarias/test_preparacion_viento3d.py` y `test_preparacion_puffs.py`
(ver también el README de `puffs/`): lo escrito se vuelve a leer
con los lectores del propio motor (`meteo.viento3d.control` y `entradas`). En el proyecto de La
Galera (2026-10-23) los ficheros salieron idénticos byte a byte a los que escribía allí (malla
geofísica, pronóstico en una y en varias columnas, nubes, estaciones, recorte del arranque) y el
control da la misma secuencia de asignaciones en 3 configuraciones, con 4,2 KB en vez de 42,5 KB.
<!-- /manual -->

## Ficheros

| Fichero | Contenido | Viene de | Equivale a |
|---|---|---|---|
| `__init__.py` | Preparación de casos de los motores (no es un motor). | — | — |
| `control.py` | `Control`: lista ordenada de asignaciones de un fichero de control (poner, apagar, quitar, insertar) y su texto. | proyecto La Galera | — |
| `viento3d/` | Entradas y control de `meteo.viento3d` y utilidades para su salida (ver su README). | proyecto La Galera | — |
| `puffs/` | Control de `dispersion.puffs` (una especie, fuentes de área, receptores) y lectura de las concentraciones (ver su README). | proyecto La Galera | — |
| `receptores.py` | `malla_anidada`: rejillas regulares de dentro afuera alrededor de un centro, sin duplicados, más receptores discretos; `resumen`. | proyecto La Galera (`receptores.py`) | — |
