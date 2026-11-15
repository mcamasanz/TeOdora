# `teodors.planta` — una planta, leída de su carpeta

<!-- manual -->
## Qué hace

Reúne lo que teOdors necesita saber de un emplazamiento: dónde están sus datos, su huso, su dominio,
sus años de reanálisis. Cambiar de planta es cambiar de carpeta, sin tocar el código.

Los motores no la usan: reciben ficheros de control, y su resultado no puede depender de la planta
activa (`test_los_motores_no_dependen_de_ninguna_planta`). Es para lo que va encima de ellos.

## Uso

```python
from teodors import planta
planta.activar("ruta/de/la/carpeta")          # una vez, al arrancar
planta.DATOS, planta.EPSG_UTM, planta.RADIO_CALCULO_KM
planta.datos_disponibles()
planta.pide("estaciones", "radio_km")           # un campo que hace falta: sin él, el error dice cuál

from teodors.planta import geo                  # comun.geo en el huso de la planta
x, y = geo.a_utm(lat, lon)
```

⚠️ Un valor por defecto de una función no puede ser `planta.ALGO`: se evaluaría al importar, quizá sin
planta activa. Pon `None` y resuélvelo dentro.

⚠️ Un proceso trabaja con UNA planta. `activar` la deja en la variable `TEODORS_PLANTA` y los procesos
hijos usan la misma. Los valores se leen al activar: las variables de entorno van antes.

## La carpeta

| Fichero | Contenido |
|---|---|
| `planta.json` | Los bloques de abajo |
| `emplazamiento.json` | `nombre`, `lat`, `lon`, `fuente` |
| `focos.json`, `receptores.json`, `normativa.json` | Focos, receptores con nombre y límites |
| `edificios_planta.json` | Opcional: los edificios de la planta (del Catastro, del LiDAR o dibujados), los de la estela de las chimeneas (`operacion.edificios_planta`) |
| `planes/` | Sus planes de operación guardados: los crea quien opera la planta |
| `rutas.json` | Opcional: `{"datos": ruta}`, absoluta o relativa a esta carpeta |

| Bloque de `planta.json` | Campos | Obligatorio |
|---|---|---|
| `identidad` | `app_nombre`, `organizacion`, `prefijo_env`, `carpeta_local`, `registro`; `agente_http`, opcional: cómo se presenta a los servicios (`AGENTE_HTTP`); `nombre_casos`, opcional: su nombre en las cabeceras de los ficheros de entrada, en ASCII. `ajustes`, `app_id`, `version`, `entidad` y `red_datos` los lee `gui`, y también `icono`, opcional: el fichero del icono de la app, relativo a la carpeta de la planta | sí; esos cinco, para la interfaz |
| `proyeccion` | `epsg`, `crs_geo`. `zona_horaria`, la de su hora oficial, la lee `operacion.planes` | sí; `zona_horaria`, para simular |
| `dominio` | `lado_km`, `margen_m`, `res_terreno_m`, `radio_edificios_km`, `radio_edificios_focos_m`, `celda_viento_m`, `zface` | sí |
| `receptores` | `por_km2`. `niveles` y `estilos` los lee `casos.receptores` | sí |
| `reanalisis` | `anios` | sí |
| `fuentes` | `corine_gpkg`: copias conocidas del CORINE; admiten variables de entorno. `mdt`, `usos`, `edificios`, `nombres_nucleos`, `fondos` y `creditos` los lee `gui` | para la interfaz, esos seis |
| `estaciones` | `radio_km`, `agente_http` (opcional). `proveedor`, su nombre en los textos, lo lee `gui`. `codigos`, `objetivo` y `ceros_sospechosos` los lee cada proyecto; `codigos`, también `mos`. Lo lee `fuentes.meteocat` | para las estaciones |
| `pronostico` | `caja_gfs` {`lat`: [sur, norte], `lon`: [oeste, este]}, `semanas_mos`. Lo leen `fuentes.gfs_noaa` y `fuentes.gfs_dynamical`. `n_col` y `paso_col_m` los lee `casos.gfs_columnas`; `mos_hasta`, `mos.tabla` | para GFS |
| `series` | `r1_km`, `rmax_km`: radios de las estaciones en el viento 3D. Lo lee `casos.viento3d`. `era5`, `gfs`, `preferidas`, `titulos` y `dia_prueba` los lee `operacion` | con estaciones; para `operacion` |
| `operacion` | `modo_edicion`: el nombre del modo de edición (`CLAVE_EDICION`); el modo, `MODO_EDICION`, empieza siempre cerrado y lo abre el administrador desde la terminal de la app (`operacion.administrador`). `tipos_foco_extra` y `ejemplo` los lee `operacion`; `texto_modo_edicion` y `ejemplo`, `gui`. `paralelo`, opcional (false, true o cuántos procesos; la variable `<prefijo>_PARALELO` va antes): el reanálisis en varios procesos, `operacion.reanalisis_paralelo` | para la interfaz, esos dos |
| `visor3d` | `ortofoto`, `credito`: de la interfaz; `semilado_m` y `rotulos`, de `operacion.penacho_3d` | para el penacho en 3D |
| `viento_local` | `puntos`, `radio_m`, `radio_borde_m`, `margen_m`, `dx`, `dz`, `alto_m`, `lidar` (relativo a la carpeta), `biblioteca` (relativo a la carpeta). Lo lee `meteo.viento_local.biblioteca`, no esta clase. `lidar_zona` [x, y, semilado] y `lidar_teselas` son de la planta: `fuentes.lidar` recibe la zona | solo para calcular esa biblioteca |

Si falta un campo obligatorio, el error dice cuál. No hay valores por defecto para lo que depende del
sitio: uno equivocado no se notaría.

## Rutas

- `DATOS`, los cálculos: variable `<prefijo>_DATOS`; si no, `rutas.json`; si no, `datos/` dentro de la carpeta. El terreno, los edificios y los planes van siempre con la planta.
- `LOCAL` (lo regenerable y los cálculos en marcha): variable `<prefijo>_LOCAL`; si no,
  `%TEMP%/<carpeta_local>`.
- Junto a la carpeta de la planta, para tener sin `DATOS` lo calculado una vez: `DIR_VIENTO` (`viento/`, o `<prefijo>_VIENTO`), con el paquete de viento
  3D en `DIR_VIENTO_PAQUETE` (`viento/3d/`) y, si su planta.json la pone ahí, la biblioteca del viento local; y `DIR_DISPERSION` (`dispersion/`, o
  `<prefijo>_DISPERSION`), las respuestas de los focos de la serie (`operacion.serie_respuestas`); y `DIR_CASOS` (`casos/`, o `<prefijo>_CASOS`),
  los casos guardados, en una carpeta por modo (`CARPETAS_CASOS`: `reanalisis/`, `episodios/` y `prediccion/`, que crea `asegurar_carpetas`),
  cada caso con «resultados» y, a su lado, su informe.
- La meteo: `DIR_METEO` (`DATOS/meteo`) es la **caché**, donde se descarga siempre (ERA5, estaciones, GFS…). `DIR_METEO_PLANTA` (`meteo/`, junto a
  `entrada/`, o `<prefijo>_METEO`) es la de los **informes**, YA PROCESADA: de los años del reanálisis, las estaciones de la zona, sus rosas, el
  tiempo en la planta y lo normal de cada fecha y hora, que hace una vez `operacion.meteo_planta` desde la caché. Ni un fichero meteorológico en
  bruto. Viaja con la planta y es de **solo lectura**. `meteo_procesada(nombre)` da un producto, o None si en este equipo están TODOS los ficheros
  en bruto de los que salió (su lista `de`, relativa a la caché): entonces se calcula de ellos, como siempre; los pocos días que se bajan para un
  episodio no bastan. Así un equipo sin la unidad de DATOS hace los informes completos, y ningún fichero de la planta lleva la ruta de DATOS.
- Claves de API: `%APPDATA%/<organizacion>/claves`, nunca en la carpeta de la planta.

## Validación
Pruebas en `auditor/pruebas/unitarias/test_planta.py`, con una planta inventada a propósito en un huso
distinto del de su longitud. `test_el_codigo_de_planta_no_trae_datos_de_un_emplazamiento` impide que
se cuelen datos de una planta concreta en este código.
<!-- /manual -->

## Ficheros

| Fichero | Contenido | Viene de | Equivale a |
|---|---|---|---|
| `__init__.py` | `Planta`, `activar`, `actual`, `desactivar` y el acceso a la planta activa como atributos del módulo. | proyecto La Galera (`gui/config.py`) | — |
| `geo.py` | Las cuentas de `comun.geo` en el huso de la planta activa. | proyecto La Galera (`geo.py`) | — |
