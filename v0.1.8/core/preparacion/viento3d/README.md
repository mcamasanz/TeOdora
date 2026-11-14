# `teodors.preparacion.viento3d` — casos del viento 3D

<!-- manual -->
## Qué hace

Monta un caso de `meteo.viento3d` en una carpeta, con nombres de fichero propios:

| Fichero del caso | Lo escribe | Contenido |
|---|---|---|
| `viento3d.inp` | `control.escribir` | control: malla, periodo, niveles, modo con o sin estaciones |
| `geo.dat` | `geofisica.escribir` | usos del suelo y cota por celda (lanza `terreno.geofisica`) |
| `pronostico3d.dat` | `pronostico.escribir_columna` / `escribir_columnas` | campo inicial: una columna de reanálisis o columnas de un modelo |
| `nubes.dat` | `nubes.escribir` / `escribir_zonas` | nubosidad uniforme o por zonas de las columnas |
| `estaciones.dat` | `estaciones.escribir` | medias horarias de las estaciones de superficie |

Salida del motor: `viento3d.dat` (y `viento3d.lst`). Para ella, `salida` da la fecha de los
registros, el recorte de las horas de arranque (el viento tiene memoria nocturna: cada periodo se
calcula desde el día anterior y se recorta) y la interpolación del viento en un punto con la
dirección GEOGRÁFICA (girada por la convergencia de meridianos).

## Convenciones
- Coordenadas en metros de un UTM fijo para todo el dominio (`comun.geo`); la malla va alineada con
  su esquina suroeste.
- Fechas: los registros llevan la hora FINAL (AAAAJJJHH).
- Medidas semihorarias: `estaciones.medias_horarias(df, conv)` con `conv = "inicio"` si la hora es la
  del inicio del intervalo (Meteocat) o `"fin"` si es la del final.
- Tablas de entrada (pandas): superficie (time, sp hPa, t2m y d2m °C, tp mm, ssrd W/m², wdir, wspd,
  tcc 0-1), perfiles (time, level hPa, height_asl_m, temp_c, wdir, wspd) o columnas de un modelo en
  formato ancho (time, i, j y las variables por nivel `…_<p>hPa`).

## Validación
Ver el README de `preparacion`.
<!-- /manual -->

## Ficheros

| Fichero | Contenido | Viene de | Equivale a |
|---|---|---|---|
| `__init__.py` | Preparación de casos de `meteo.viento3d`. | — | — |
| `parametros.py` | Asignaciones de partida del control, en orden (generado; no se edita a mano). | proyecto La Galera | — |
| `control.py` | `preparar` / `escribir`: control del caso (malla, periodo, niveles, estaciones, radios, ajustes extra); `registro_estacion`. | proyecto La Galera (`casos.py`) | — |
| `geofisica.py` | `malla`: malla del viento sobre el terreno fino; `escribir`: fichero geofísico con `terreno.geofisica`. | proyecto La Galera (`casos.py`) | — |
| `pronostico.py` | `escribir_columna` (reanálisis en una columna), `rejilla_puntos`, `escribir_columnas` (columnas de un modelo). | proyecto La Galera (`ficheros.py`, `columnas.py`) | — |
| `nubes.py` | `escribir` (uniforme), `escribir_zonas` (de la columna más cercana). | proyecto La Galera | — |
| `estaciones.py` | `medias_horarias`, `escribir` (fichero de estaciones; en una hora sin temperatura en ninguna estación, temperatura, humedad y presión de la superficie del modelo). | proyecto La Galera (`ficheros.py`) | — |
| `salida.py` | `fecha_registro`, `recorte`, `recortar_arranque`, `en_punto`, `viento_en_punto`. | proyecto La Galera (`casos.py`, `ficheros.py`) | — |
