# `teodors.fuentes` — fuentes de datos

<!-- manual -->
## Qué hace

Baja de internet lo que necesita una planta y lo deja en su carpeta de DATOS: terreno, usos del suelo, edificios, estaciones, reanálisis y
pronóstico. No son motores ni equivalen a ningún programa. Lo ya descargado no se vuelve a pedir.

⚠️ **Son servicios de España, salvo ERA5 y GFS.** No se ha intentado generalizarlos: una planta de otro sitio necesita otras fuentes.

| Módulo | Servicio | Cobertura | Licencia |
|---|---|---|---|
| `terreno` | MDT del IGN (WCS, servido en EPSG:25830), CORINE 2018 (fichero `CLC2018_ES.gpkg`, ~3 GB, no se descarga), nombres de CartoCiudad | España | CC BY 4.0 (IGN) |
| `catastro` | WFS INSPIRE del Catastro | España | se guarda solo el dato transformado; el GML original no se redistribuye |
| `meteocat` | datos abiertos de la Generalitat (red XEMA), sin clave | Cataluña | la del portal |
| `era5` | Climate Data Store de Copernicus; **hace falta clave** | mundial | la del CDS, que hay que aceptar con la cuenta |
| `gfs_noaa` | GRIB2 de GFS 0,25° con niveles de presión (NOAA en AWS); con `extra=True` (la predicción, 0.1.12), también lo que necesita el MOS: el viento a 100 m y la media de la nubosidad y de la onda corta (`EXTRA`, `EXTRA_MEDIA`, `mensajes`) | mundial | datos públicos de NOAA |
| `gfs_dynamical` | archivo de predicciones de GFS (dynamical.org). ⚠️ Python ≥ 3.12 | mundial | CC BY 4.0 |
| `lidar` | no descarga: de una nube de puntos `.laz` con las clases de ASPRS a rejillas de 1 m | la de sus ficheros | la de sus ficheros |
| `ortofoto` | las teselas XYZ del primer fondo de la planta (`fuentes.fondos`), para el plano de la página Focos; se guarda con la planta, en `terreno/` | la del fondo | la del fondo: su atribución va en la imagen |

Las URL de los servicios están en el código: no son datos de una planta.

## Uso

```python
from teodors import planta
from teodors.fuentes import catastro, meteocat, terreno

planta.activar("ruta/de/la/planta")
emp = planta.cargar_emplazamiento()
info = terreno.descargar(emp["lat"], emp["lon"], planta.DOMINIO_DESCARGA_KM)   # MDT + CORINE; una vez
Z, U, transform = terreno.cargar(terreno.ultimo_caso(emp["lat"], emp["lon"]))
catastro.descargar(emp["lat"], emp["lon"])                                     # a RADIO_EDIFICIOS_KM
meteocat.cercanas(emp["lat"], emp["lon"])                                      # al radio de su bloque `estaciones`
```

Por línea de órdenes, con la carpeta de la planta en `TEODORS_PLANTA`:

```bash
python -m teodors.fuentes.descargar_era5
python -m teodors.fuentes.descargar_meteocat
python -m teodors.fuentes.gfs_noaa [--semanas aaaa-mm-dd …] [--hilos 9] [--paralelo 2]
python -m teodors.fuentes.gfs_dynamical [--desde 2021-05] [--hasta 2026-09] [--hilos 16]     # Python ≥ 3.12
python -I core/fuentes/lidar.py <carpeta .laz> <carpeta de librerías> <salida.npz> x y semilado
```

`lidar` se lanza con `python -I`, por su ruta y desde otra carpeta: los `.laz` son datos descargados. No importa nada de teOdors ni del
proyecto, y `laspy` y `numpy` salen de la carpeta que se le da.

`gfs_dynamical` corre en un entorno aparte: al importarlo solo carga numpy y pandas, y de teOdors, `teodors.planta` (biblioteca estándar).

## De la planta

| De planta.json | Lo usa |
|---|---|
| `identidad.agente_http` | `terreno`, `catastro` y, si no tiene el suyo, `meteocat` |
| `dominio.res_terreno_m`, `radio_edificios_km`, `radio_edificios_focos_m` | `terreno`, `catastro` |
| `reanalisis.anios` | `era5`, `meteocat`; el anemómetro de una estación se busca desde el primero |
| `estaciones.radio_km`, `estaciones.agente_http` | `meteocat` |
| `pronostico.caja_gfs`, `pronostico.semanas_mos` | `gfs_noaa`, `gfs_dynamical` |
| `fuentes.fondos` (el primero: nombre, URL `{z}/{x}/{y}`, atribución y zoom máximo) | `ortofoto` |

Un valor por defecto `None` se resuelve al llamar: importar estos módulos no lee la planta.

## Lo que hay que saber de cada servicio

- **IGN.** Sobre el mar devuelve **0 m**, no «sin dato», y su cabecera no trae `nodata_value`. La respuesta es multipart: los datos acaban en
  la primera línea `--`. Los negativos pasan a 0.
- **Meteocat.** Cada 30 min, en **UTC y con la etiqueta de INICIO del intervalo**, que se guarda tal cual: quien promedia tiene que saberlo
  (`preparacion.viento3d.estaciones.medias_horarias(df, "inicio")`). Se pide **mes a mes**: el año entero agota el tiempo de respuesta.
  `estaciones_dias` suma a lo que ya hubiera, sin perderlo. ⚠️ Medido el 2026-11-01: las lecturas acababan el 26/10 a las 17:30. Sin el
  inventario en la caché, `inventario` da el de las estaciones de la zona que trae la planta con su meteo procesada (`planta.meteo_procesada`,
  de `operacion.meteo_planta`): no se pide a la red.
- **ERA5.** La cola puede tardar horas: cada petición se sigue por su identificador. Un 5xx, un 429 o un corte de red **esperan la misma
  petición** (hasta 48 h); un 4xx **la reenvía** (`requests.HTTPError` hereda de `OSError`: sin mirar el código, un 404 parecía un corte de
  red); un rechazo por licencia para. La clave está en `%APPDATA%/<organizacion>/claves/cds-api-key.txt`, nunca en la carpeta de la planta. El
  cliente es `ecmwf-datastores-client`, no `cdsapi`.
- **Catastro.** Altura = plantas × 3 m: subestima las naves. Los elementos con muchas «plantas» pueden no ser edificios: mídelo antes de usarlo.
  Rechaza teselas grandes: se dividen solas, y se avisa si alguna mínima sigue rechazada.
- **GFS de NOAA.** La malla va de 0 a 360 en longitud. `indices_caja` admite una caja al oeste de Greenwich, sin usar aún allí.
- `FUENTE`, en `meteocat` y en `era5`: cómo se cita cada uno (lo usa el `LEEME.md` de la meteo procesada de la planta).

⚠️ **Los reintentos no son iguales y no se han fundido:** `terreno._wcs_tramo` (4 intentos, 2 s · k; también si la respuesta no es un grid),
`catastro._http` (3, 5 s · k; solo errores de red), `meteocat._get` (4, 5 s · k; cualquier error), `gfs_noaa._get` (6, 5 s · 2^k),
`gfs_dynamical.leer` (6, 10 s · 2^k), `era5._pedir` (5, 60 s · k, además de la espera de `_esperar`). Unificarlos cambiaría cuándo se rinde cada uno.

## Validación
Pruebas en `auditor/pruebas/unitarias/test_fuentes.py`, **sin red**: simulan las respuestas y una conexión de verdad hace fallar la prueba.
La planta de prueba está inventada. Referencias externas: pyproj para la reproyección del MDT, la ley logarítmica para `a_10m`, las unidades de
ERA5 y las clases de ASPRS.

⚠️ Comprueban el código, **no que los servicios sigan respondiendo así**: desde que este código está aquí no se ha lanzado ninguna descarga de
verdad. Viene del proyecto de La Galera, donde descargó sus datos, y es el mismo función a función salvo lo que dice el CHANGELOG.

⚠️ Heredado, sin cambiar: en `descargar_mdt`, en la costura entre tramos gana la celda del primero aunque su ventana bilineal quede incompleta
(medido sobre un plano del 2 %: 0,26 m en 96 de 19 023 celdas; las demás, ≤ 0,05 m). En `gfs_noaa.plazo`, un mensaje pedido que sea el último del
índice daría `IndexError`.
<!-- /manual -->

## Ficheros

| Fichero | Contenido | Viene de | Equivale a |
|---|---|---|---|
| `__init__.py` | La lista de fuentes. | — | — |
| `terreno.py` | MDT del IGN, CORINE, nombres de los núcleos de CartoCiudad, estadísticas, lo que rodea la planta (`alrededor`, v0.1.11) y capas para el mapa. | proyecto La Galera (`entradas/terreno.py`) | — |
| `catastro.py` | Edificios del Catastro: descarga, plantas, altura, distancia y capa para el mapa. | proyecto La Galera (`entradas/edificios.py`) | — |
| `meteocat.py` | Estaciones de Meteocat: inventario, lecturas, años en caché y suma de días. | proyecto La Galera (`entradas/estaciones.py`, `gui/tareas/viento_dia_local.py`) | — |
| `era5.py` | ERA5 del CDS: cola de peticiones, superficie y perfil. | proyecto La Galera (`entradas/meteo.py`) | — |
| `descargar_era5.py`, `descargar_meteocat.py` | Líneas de órdenes de las dos anteriores. | proyecto La Galera (`gui/tareas/`) | — |
| `gfs_noaa.py` | GFS 0,25° con niveles de presión, por rangos del GRIB. | proyecto La Galera (`gui/tareas/descargar_gfs_niveles.py`) | — |
| `gfs_dynamical.py` | Archivo de predicciones de GFS. Python ≥ 3.12. | proyecto La Galera (`gui/tareas/descargar_gfs_historico.py`) | — |
| `lidar.py` | De una nube de puntos a rejillas de 1 m. Se lanza con `python -I`. | proyecto La Galera (`gui/tareas/lidar_planta.py`) | — |
| `ortofoto.py` | La ortofoto bajo el plano de los focos: las teselas del primer fondo, cosidas y llevadas a UTM con una afín. | nuevo (2026-11-08) | — |
