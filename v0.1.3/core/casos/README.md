# `teodors.casos` — los casos de una planta

<!-- manual -->
## Qué hace

Une la carpeta de una planta (`planta`), sus datos (`fuentes`) y los motores (`preparacion`, `meteo.viento3d`). No son motores ni equivalen a ningún programa. `preparacion` escribe ficheros a partir de tablas y no sabe nada de ninguna planta; esto es lo que sabe de dónde salen esas tablas.

| Módulo | Qué da |
|---|---|
| `viento3d` | un mes de viento 3D con ERA5 y, si se dan, estaciones de Meteocat: lo prepara, lo lanza, saca las series en la planta y en las estaciones, lo guarda comprimido sin las horas de arranque y vigila el disco; lectura del fichero de viento |
| `gfs_columnas` | de los ficheros de `fuentes.gfs_noaa` a las columnas que pide `preparacion.viento3d.pronostico.escribir_columnas` |
| `receptores` | la malla de receptores: niveles de la planta, núcleos, viviendas y receptores con nombre; los estilos de su capa del mapa |

Necesita `teodors[fuentes]`. Importar estos módulos no lee la planta.

Lo que no necesita planta ni fuentes no está aquí: el control de puffs con varias especies y fuentes es `preparacion.puffs.control_fuentes`.

## Uso

```python
from teodors import planta
from teodors.casos import receptores, viento3d

planta.activar("ruta/de/la/planta")
viento3d.mes_serie(2024, 7, "teodors", "NOMBRE_DE_LA_SERIE", estaciones=["AA", "BB"])
    # DATOS/viento3d/<serie>/cmz/202407.cmz  y  DATOS/viento3d/<serie>/202407/{caso.json, puntos.csv, resumen.json, viento3d.inp}
malla = receptores.malla(nucleos, edificios)        # [(x, y, clase)]
```

## De la planta

| De planta.json | Lo usa |
|---|---|
| `dominio.celda_viento_m`, `dominio.zface` | `viento3d.rejilla`, `viento3d.preparar_mes` |
| `identidad.nombre_casos` (opcional, en ASCII) | `viento3d.cabecera`: el texto de las cabeceras de los ficheros, que el motor no usa |
| `series.r1_km`, `series.rmax_km` | `viento3d.preparar_mes` y `mes_serie`: radios de las estaciones, solo si hay estaciones |
| `pronostico.n_col`, `pronostico.paso_col_m` | `gfs_columnas.columnas` |
| `receptores.niveles` | `receptores.malla`: [clase, paso en m, semilado en m o `null` = todo el dominio], de dentro afuera |
| `receptores.estilos` | `receptores.estilos`: {clase: [color, radio en píxeles, texto]} |

El nombre de cada serie es de la planta y lo da quien llama. Un valor por defecto `None` se resuelve al llamar.

## Lo que hay que saber

- **Arranque:** el viento 3D tiene memoria nocturna. `preparar_mes` empieza `ARRANQUE_H` = 24 h antes si hay ERA5 de esas horas y `mes_serie` las quita al comprimir (`recorte_de`). Sin ERA5 de antes, arranca en frío y no recorta nada, sin avisar.
- **Columnas de GFS:** la predicción a 1 día de cada hora es la ejecución de las 00 UTC de H − 1 h: las 00 UTC salen del plazo 24 del día anterior. Con `ciclo`, las horas posteriores salen de esa ejecución. Entre plazos de 3 h, interpolación lineal. Los niveles bajo el suelo del modelo se escalonan 2 m en `escribir_columnas`: a la misma altura, el motor dividía por cero.
- **Estaciones:** son las de `fuentes.meteocat`, que solo cubre Cataluña. Las marcadas por `metricas.calidad` no entran.
- **Receptores:** un receptor con nombre o un núcleo sustituye al de la rejilla en el mismo punto. Solo son discretas las viviendas: uso «Residencial» del Catastro.
- **Mientras se calcula:** el motor necesita sus ficheros en una carpeta local (`DIR_TRABAJO`); en DATOS solo queda lo de `CONSERVAR` y el `.cmz`.

⚠️ Heredado, sin cambiar:
- `_reservado_gb` mira también `viento3d_estudios/icon` y `viento3d_estudios/experimentos`: restos de estudios de una planta, sin efecto si no existen.
- Las columnas de GFS llevan lluvia y radiación a 0: GFS no las da en esos ficheros.
- `preparar_mes` usa 10 m para una estación sin altura de anemómetro, sin avisar, y `terrad_km` = 5,0 por defecto, que no viene de la planta.
- `gfs_columnas.niveles` junta ejecuciones con plazos distintos (la predicción larga) con `xr.concat` sin `join`: xarray avisa de que en una versión futura ese valor por defecto cambiará y fallará.
- `mes_serie` recibe un `motor` que solo apunta en el resumen: hay uno.

## Validación
Pruebas en `auditor/pruebas/unitarias/test_casos_planta.py`, **sin red** y con una planta y unos datos inventados: un mes entero con el motor de verdad, y los ficheros se vuelven a leer con los lectores de los motores. Comprueban la superposición, las unidades, lo que lee el motor, la malla, las columnas de GFS y el arranque.

Comprueban el código: **no dicen nada de la calidad del viento en ningún sitio.** Viene del proyecto de La Galera y es el mismo función a función, salvo lo que dice el CHANGELOG. Las descargas de `fuentes` no se han lanzado con este código.
<!-- /manual -->

## Ficheros

| Fichero | Contenido | Viene de | Equivale a |
|---|---|---|---|
| `__init__.py` | La lista de módulos. | — | — |
| `viento3d.py` | Casos y series de viento 3D de una planta. | proyecto La Galera (`gui/tareas/viento3d_casos.py`) | — |
| `gfs_columnas.py` | Columnas de GFS para el pronóstico 3D. | proyecto La Galera (`gui/tareas/gfs_columnas.py`) | — |
| `receptores.py` | Malla de receptores y estilos de su capa. | proyecto La Galera (`gui/receptores_mapa.py`) | — |
