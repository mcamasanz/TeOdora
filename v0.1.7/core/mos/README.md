# `teodors.mos` — corrección estadística de la predicción por estación

<!-- manual -->
## Qué hace

Corrige la predicción de GFS en cada estación con lo que esa estación ha medido (MOS, *model output statistics*). No es un motor: no está en `MOTORES` ni se lanza con `python -m teodors`, y no equivale a ningún programa.

| Módulo | Qué da |
|---|---|
| `tabla` | la tabla de entrenamiento (una fila por estación, ejecución de las 00 UTC y plazo de 0 a 120 h: GFS en el punto y lo medido), la partición por semanas y el error de GFS sin corregir, que es lo que el MOS tiene que batir |
| `entrenar` | por estación, tres modelos (u, v y velocidad) de dos familias (ridge y gradient boosting), entrenados con el 80 % y medidos en el 20 % |

Necesita `teodors[mos]`. Importar estos módulos no lee la planta ni carga scikit-learn, joblib, xarray ni dask.

⚠️ **La mejora de dirección es LOCAL a la estación: no se transmite a través de `viento3d` a 7-13 km.** Medido en un proyecto, en 3 estaciones dejadas fuera de una en una, con la predicción a 1 día (~1 340 h por estación): error medio de dirección de `viento3d` solo con GFS, 33-45°; añadiendo como pseudoestaciones el MOS de las otras 7, 32-42°; el MOS de la propia estación, 22-33°. La velocidad sí mejoró y la rosa no. Donde no hay estación, la dirección prevista sigue siendo de la calidad de GFS aunque haya MOS alrededor.

⚠️ **El paquete llega hasta medir.** Guarda los modelos, pero ninguna función los aplica a una predicción nueva ni los lleva a `viento3d`.

## Uso

Antes hacen falta las predicciones antiguas de GFS y el control de calidad de cada estación:

```bash
python -m teodors.fuentes.gfs_dynamical                 # DATOS/meteo/gfs/gfs00_AAAAMM.nc
python -m teodors.metricas.calidad --codigo CÓDIGO      # DATOS/reanalisis/01_estacion_<código>/horario_valido.csv, una vez por estación
```

Después, con la carpeta de la planta en `TEODORS_PLANTA`:

```bash
python -m teodors.mos.tabla        # DATOS/mos/: tabla_gfs00.parquet, particion.csv, referencia_gfs.csv, resumen.json
python -m teodors.mos.entrenar     # DATOS/mos/: modelos/<código>_<u|v|ws>.joblib, prediccion_valid.parquet, metricas.csv
```

Cada `.joblib` es `{"lineal": modelo, "gb": modelo, "entradas": [columnas, en su orden]}`.

## De la planta

| De planta.json | Lo usa |
|---|---|
| `estaciones.codigos` | `tabla.main`, `entrenar.main`: una tabla y unos modelos por código |
| `estaciones.radio_km` | `fuentes.meteocat.cercanas`, de donde salen sus coordenadas: un código fuera del radio da `KeyError` |
| `pronostico.mos_hasta` | `tabla.gfs`, `tabla.main`: la última hora que cuenta, «AAAA-MM-DD HH:MM». Lo posterior no entra en la tabla |

Un valor por defecto `None` se resuelve al llamar. `desde` de `tabla.gfs` no es de la planta: 2021-05 es donde empieza el archivo de `fuentes.gfs_dynamical`. `pronostico.semanas_mos` no se lee aquí: es lo que descarga `fuentes.gfs_noaa`.

## Lo que hay que saber

- **Partición:** por SEMANA (lunes a domingo) de la hora de VALIDEZ: validación si semana ISO + año ≡ 0 mod 5. Una ejecución predice 5 días y sí puede quedar repartida; una semana, no, y así entrenamiento y validación nunca comparten horas medidas. Sale en torno al 20 %.
- **Iteraciones del gradient boosting:** se eligen con otra parte del ENTRENAMIENTO (semana ISO + año ≡ 1 mod 5) y luego se reentrena con todo. La validación no se mira hasta el final.
- **Entradas:** solo GFS en el punto, sus derivados y el calendario (`entrenar.ENTRADAS`). Ninguna medida, ni de esa estación ni de otra: cada estación se entrena con sus filas.
- **Dirección:** sale de u y v, para que no haya salto en los 360°. La velocidad se predice aparte, porque la media de vectores la encoge. El error de dirección es circular y solo cuenta con viento medido ≥ 1 m/s (`VIENTO_MIN`).
- **Altura:** lo medido va a la altura del anemómetro de cada estación, y GFS a 10 m: el sesgo de GFS sin corregir mezcla las dos cosas.
- **Huecos:** el gradient boosting los admite; el ridge los toma como 0 (`np.nan_to_num`). Nubosidad y onda corta no existen en el plazo 0 del archivo.
- **Métricas:** por día de plazo (`DIAS`), de día y de noche (sol sobre el horizonte en la estación). La fila «media» es la media de las estaciones, no de todas las filas. `referencia_gfs.csv` lleva además el «día 0», solo la hora 00 UTC; `metricas.csv`, no.

⚠️ Heredado, sin cambiar:
- La columna `anemometro_m` de la tabla vale siempre 10: `fuentes.meteocat.cercanas` no da la altura, y `e.get("altura_viento_m") or 10.0` cae siempre en el 10. Ningún modelo la usa.
- `entrenar` importa `error_dir` y no lo usa.

## Validación
Pruebas en `auditor/pruebas/unitarias/test_mos.py`, **sin red** y con una planta, un GFS y unas estaciones inventados. Referencias externas: el calendario ISO y la geometría del círculo; un campo lineal, en el que la interpolación bilineal es exacta, y un sesgo conocido de velocidad y de dirección que cruza los 360°.

Comprueban el código: **no dicen lo bien que corrige ningún MOS en ningún sitio.** Viene del proyecto de La Galera y es el mismo función a función, salvo lo que dice el CHANGELOG. Con este código no se ha entrenado nada con datos reales.
<!-- /manual -->

## Ficheros

| Fichero | Contenido | Viene de | Equivale a |
|---|---|---|---|
| `__init__.py` | La lista de módulos. | — | — |
| `tabla.py` | Tabla de entrenamiento, partición por semanas y referencia de GFS sin corregir, con su línea de órdenes. | proyecto La Galera (`gui/tareas/mos_tabla.py`) | — |
| `entrenar.py` | Modelos por estación y sus métricas en validación, con su línea de órdenes. | proyecto La Galera (`gui/tareas/mos_entrenar.py`) | — |
