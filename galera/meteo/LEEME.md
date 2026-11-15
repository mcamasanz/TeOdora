# Meteo de la planta, ya procesada: la que piden los informes

La hace `python -m teodors.operacion.meteo_planta` con la meteo en bruto de la caché, en el equipo que la tiene. Con ella, un equipo
sin esa meteo en bruto (el del cliente) hace los informes completos: el tiempo en la planta, las rosas de las estaciones y la meteo
de un episodio frente a lo normal de esas fechas. **No hay ningún fichero meteorológico en bruto**: solo lo ya calculado. Es de solo
lectura y no se edita a mano: se rehace con la misma orden.

- Años: 2021-2025 · estaciones: C9, U7, U9, US, UU, UW, UX, X5 · viento en la planta: odora_era5_8est
- 4 ficheros, 4,7 MB: su tamaño y su huella, en `indice.json`
- Hecha el 2026-11-15 a las 09:21 con teOdors 0.1.10

| Fichero | Qué hay |
|---|---|
| `estaciones.json` | las estaciones de la zona (de su inventario) |
| `rosas_estaciones.json` | la rosa de los vientos de cada estación y la del ERA5 en las mismas horas |
| `tiempo_planta.json` | la media de cada día de cada variable en la planta (la temperatura y la capa de mezcla, también su mínimo y su máximo), su resumen y, hora a hora, el calor sensible y la capa de mezcla |
| `normales_estaciones.json` | lo normal de cada fecha y hora en las estaciones: el valor de cada año y su mínimo, su mediana, su máximo y su media; de la dirección, los valores de cada año |

## Cada variable en la planta, 2021-2025

De sus valores de cada día; el mínimo y el máximo de la temperatura y de la capa de mezcla, de los de cada hora.

| Variable | Unidad | Mínimo | Media | Máximo |
|---|---|---|---|---|
| Velocidad del viento | m/s | 0,42 | 1,85 | 8,75 |
| Temperatura | °C | -0,9 | 16,9 | 36,3 |
| Humedad relativa | % | 32,8 | 68,9 | 93,9 |
| Nubosidad | % | 0,0 | 46,7 | 100,0 |
| Precipitación | mm/día | 0,0 | 1,7 | 57,2 |
| Radiación solar | W/m² | 12,7 | 193,5 | 345,5 |
| Presión en el suelo | hPa | 961 | 986 | 1 006 |
| Velocidad de fricción, u* | m/s | 0,04 | 0,17 | 0,68 |
| Calor sensible, hacia arriba | W/m² | -25,5 | 37,8 | 125,1 |
| Altura de la capa de mezcla | m | 11 | 489 | 3 227 |

Fuentes: el reanálisis ERA5 (Copernicus Climate Change Service, C3S) y las estaciones del Servei Meteorològic de Catalunya (Meteocat, red XEMA), datos abiertos, procesados con teOdors. Cada dato conserva las condiciones de uso de su proveedor.
