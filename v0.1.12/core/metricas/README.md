# `teodors.metricas` — métricas de validación del viento

<!-- manual -->
## Qué hace

Compara un viento modelizado con lo que miden las estaciones y revisa antes esas medidas. No son motores ni equivalen a ningún programa.

| Módulo | Qué da |
|---|---|
| `viento` | sesgo, RMSE, índice de concordancia y umbrales de Emery, Tai y Yarwood (2001); medias horarias de una estación; rosas de los vientos de una serie, de un día o de los años del reanálisis, con su caché; figura de rosas |
| `calidad` | marcas de control de calidad por medida (duplicadas, rangos, atascos, picos, ceros dudosos), horas válidas, cobertura y rosas por año, estación del año, día y noche |

Necesita pandas (`teodors[preparacion]`); las figuras, además, matplotlib (`teodors[mapas]`). Importar estos módulos no lee la planta ni carga matplotlib.

⚠️ **Las estaciones son las de `fuentes.meteocat`**, que solo cubre Cataluña. `rosas_dia` da por hecho su convención horaria (etiqueta de INICIO). `metricas`, `ioa`, `rosa` y `a_horario` no dependen de ningún servicio: reciben tablas.

## Uso

```python
from teodors import planta
from teodors.fuentes import meteocat
from teodors.metricas import viento

planta.activar("ruta/de/la/planta")
emp = planta.cargar_emplazamiento()
era = viento.era5_horario(emp["lat"], emp["lon"])                       # time, ws, wd, t, rad
df = meteocat.cargar("CÓDIGO")
conv, _ = viento.convencion(df)                                         # «inicio» o «fin»
m = viento.metricas(viento.a_horario(df, conv), era, altitud_est, cota_era5, altura_viento)
m["wd_error"], m["cumple"]["wd_error"]
viento.rosas_dia(emp["lat"], emp["lon"], "2024-07-15")
```

Por línea de órdenes, con la carpeta de la planta en `TEODORS_PLANTA`:

```bash
python -m teodors.metricas.calidad [--codigo CÓDIGO]
```

Escribe en `DATOS/reanalisis/01_estacion_<código>/`: `medidas_30min_qc.csv.gz`, `horario_valido.csv`, `rosas_observadas.csv`, dos PNG y `resumen.json`.

## De la planta

| De planta.json | Lo usa |
|---|---|
| `reanalisis.anios` | `era5_horario`, `rosas_estaciones`, `calidad` |
| `estaciones.objetivo` | `calidad`, si no se da `--codigo` |
| `estaciones.ceros_sospechosos` (opcional) | `calidad`: {código: fecha}. Desde esa fecha, un 0 m/s exacto se marca como dudoso |
| `estaciones.mediodia_utc_h` (opcional) | `convencion`; sin él, el mediodía solar en la longitud de `emplazamiento.json` |
| `estaciones.radio_km` | las estaciones cercanas, en `fuentes.meteocat` |

Un valor por defecto `None` se resuelve al llamar.

## Lo que hay que saber

- **Error de dirección:** es circular, de −180° a 180°: 350° frente a 10° son 20°. Solo cuenta con viento ≥ 1 m/s en los dos lados (`VIENTO_MIN_DIR`).
- **Velocidad:** la de la estación se lleva a 10 m con la ley logarítmica (`meteocat.a_10m`), sin corregir la estabilidad. Las rosas no: van a la altura del anemómetro.
- **Temperatura:** la del modelo se corrige por la diferencia de cota con `GRADIENTE_T`.
- **Umbrales:** los de `UMBRALES`. Emery (2001) da también índice de concordancia en temperatura y criterios de humedad: aquí no están.
- **Convención horaria:** con pocos días el centroide de la radiación no es fiable y puede dar un error: si se conoce la convención, se da. Tampoco vale donde el día cruza las 00 UTC, porque el centroide no es circular.
- **Rosas:** `rosa` da % por sector y `_rosa_clases` % por sector y clase de velocidad, los dos sobre TODAS las horas, y con las calmas suman 100. Un sector va de −½ a +½ de su ancho y el borde inferior es suyo: con 8 sectores, 337,5° ya es N y 22,5° ya es NE.
- **Las rosas de los años del reanálisis sin la meteo en bruto:** si en este equipo no están todos los ficheros de los que salen (`ficheros_rosas`), `rosas_estaciones` da las que trae la planta ya calculadas (`planta.meteo_procesada`, de `operacion.meteo_planta`); con `procesada=False`, las calcula siempre.

⚠️ **Dos parejas que se parecen y no se han fundido:**
- `viento.a_horario` solo da las horas con las DOS medias (`n == 2`); `preparacion.viento3d.estaciones.medias_horarias`, también las que solo tienen una (`n >= 1`). Fundirlas cambia qué horas se validan. Una prueba deja escrita la diferencia.
- `planta.geo.elevacion_solar`, con la que se separan el día y la noche en `calidad`, y `meteo.viento3d.sol.seno_elevacion`: mismo fin, otra fórmula.

## Validación
Pruebas en `auditor/pruebas/unitarias/test_metricas.py`, **sin red** y con una planta y unas estaciones inventadas. Referencias externas: los umbrales de Emery, Tai y Yarwood (2001), el índice de Willmott (1981) a mano, la geometría del círculo y las horas de salida del sol en dos fechas conocidas.

Comprueban el código: **no dicen lo bien que acierta ningún modelo en ningún sitio.** Viene del proyecto de La Galera y es el mismo función a función, salvo lo que dice el CHANGELOG.

⚠️ Heredado, sin cambiar:
- En `calidad`, las figuras se reparten con `list(rosas)[:6]`, pensado para 5 años: con otro número, `rosas_total_y_anios.png` lleva también estaciones del año, o le faltan años.
- En `calidad`, un año o una estación del año sin ninguna hora válida deja su rosa en NaN y `figura` da `ValueError`; un `--codigo` fuera del radio da `StopIteration`.
- `metricas` quita la hora entera si falta cualquier columna: sin temperatura en la estación, tampoco cuenta su viento.
- `rosas_dia` solo lee el año del día pedido: el 1 de enero se queda con 23 horas, porque la primera necesita la última media del año anterior.
- `_rosa_clases` no admite vacíos: un NaN en la dirección da `IndexError` y uno en la velocidad cuenta como ≥ 8 m/s. Quien la llama aquí los quita antes.
- En `control_calidad`, de dos medidas con la misma hora se queda la primera tras ordenar con un método no estable: no se garantiza cuál de las dos.
<!-- /manual -->

## Ficheros

| Fichero | Contenido | Viene de | Equivale a |
|---|---|---|---|
| `__init__.py` | La lista de módulos. | — | — |
| `viento.py` | Métricas y umbrales, horas de una estación, convención horaria, rosas y figura de rosas. | proyecto La Galera (`viento/validacion.py`) | — |
| `calidad.py` | Control de calidad de una estación, sus rosas y su línea de órdenes. | proyecto La Galera (`gui/tareas/f1_estacion.py`) | — |
