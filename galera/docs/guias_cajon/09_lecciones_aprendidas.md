# 09 · Lecciones aprendidas: síntoma → causa → arreglo

Lista para buscar con Ctrl+F. Los detalles de AERMOD y CALPUFF están en las guías [03](03_aermod_receta_y_errores.md)
y [04](04_calmet_calpuff_receta_y_errores.md).

## Resultados absurdos

| Síntoma | Causa | Arreglo |
|---|---|---|
| Máximo de 49 millones de µg/m³ | Caudal de área como total y en µg/s | AREA = g/(s·m²) |
| CALPUFF ×10⁶ por encima de AERMOD | El worker perdía `unidad` y `factor`, así que no se convertía ou_E→g | Pasar los dos campos. Comparar SRCPARAM con el subgrupo 14b |
| P98 demasiado bajo | Calmas y horas sin datos contadas como 0 | P98 sobre las horas válidas del `.sfc` |
| «P98» sin sentido | Percentil sobre el CSV de medias, que es un percentil espacial | P98 sobre la serie horaria |
| Penacho girado unos grados | Huso UTM fijo (30) lejos de su meridiano; AERMOD no gira el viento | Huso propio o `dir_geo_a_rejilla` (`utilidades/geo_utm.py`) |
| Picos de volteo exagerados | Pico de 20 minutos puesto la hora entera | Promediar en la hora |
| Escala del máximo de olor rara | `vmin` tomado del dato | `vmin` fijo (0,001) |

## Meteo y tiempo

| Síntoma | Causa | Arreglo |
|---|---|---|
| CALMET.DAT de 0 MB | Arranque a medianoche sin datos (ciclo 12Z) | Ciclo 00Z y primera medianoche con datos |
| CALMET falla en `interpqr` | NaN en f000 de GFS (acumulados) | Rellenar con 0 |
| «Record Out of Sequence» / `TypeError` en el 3D.DAT | Dos pronósticos solapados | Borrar el anterior y quitar duplicados con `keep='last'` |
| Huecos en predicción a más de 5 días | GFS pasa a cada 3 h | Tope de 120 h |
| ERA5 llega como `.zip` | El CDS nuevo empaqueta instantáneas y acumuladas | Detectar `PK` y unir los dos netCDF |
| Peticiones al CDS rechazadas | Coste por petición y concurrencia | Mes a mes, 2 hilos y reintentos |

## Mallas y mapas

| Síntoma | Causa | Arreglo |
|---|---|---|
| Franja falsa en el borde del mapa | Receptor urbano suelto fuera del anillo | Discretos solo dentro del cuadro |
| Un icono urbano desaparece | Redondeo de 3 mm al filtrar | 1 m de tolerancia |
| Resultados más pequeños que el cuadro de View Map | Terreno sin holgura y malla sin anillo | Holgura `300 + 0,045·lado` + anillo en el borde |
| Imagen descolocada | `mercator_project=True` de folium | Reproyectar con rasterio |
| Marcadores sin dibujo en el HTML | Fuentes de FontAwesome con ruta relativa | Embeber woff2 y png (`html_autonomo.py`) |
| Fotogramas listados en el control de capas | Se añadían con control | `control=False` |
| Viento desplazado respecto al penacho | `latLngToContainerPoint` redondea a enteros | Proyección sin redondear y vectores entre esquinas lejanas |
| Viento más grande que el penacho | CALMET cubre la holgura | Recorte al cuadro de receptores |
| Partículas invisibles o flechas diminutas | Velocidad y tamaño en m | Píxeles: de 0,8 a 3,4 px por fotograma, flechas con contorno |
| `\U0001F32C` roto en JS | Escape de Python en una cadena JS | Emoji literal |
| Mapa sin zoom en QWebEngine | `file://` sin acceso remoto | `LocalContentCanAccessRemoteUrls` |
| `plots/aermod_result.html` pisado | Dos funciones escribían el mismo fichero | Un nombre por función |

## Rendimiento

| Síntoma | Causa | Arreglo |
|---|---|---|
| La malla «1/2» tarda más que la completa | El umbral para repartir era receptores × horas | Umbral por tiempo estimado en serie (20 s) |
| 15 minutos con 17 actualizaciones de la vista previa | Una por bloque terminado | Vista previa por bloques más pequeños o cada 3 h simuladas |
| Escala ×2,6 con 9 procesos | Portátil de 15 W con núcleos E | Es el hardware; no extrapolar |

## Windows y OneDrive (el enemigo silencioso)

- **OneDrive bloquea ficheros recién escritos:** sale `PermissionError WinError 32` en renames y
  lecturas. Arreglos:
  - ejecutables en un espejo local en `%TEMP%`;
  - canal de control en `%TEMP%`;
  - renombrar con reintentos y copia de respaldo.
- **OneDrive BORRA ficheros** con Files On-Demand: desapareció un caso entero. Opciones: excluir
  `tmp/` y `data/` de OneDrive, o trabajar en una ruta local. **Haz copia de la caché fuera de OneDrive.**
- **Rutas largas:** clonar repositorios de la EPA o GitHub dentro del scratchpad desborda MAX_PATH.
  Usar `c:\tmp`.
- **Consola cp1252:** los `print` con γ, emojis o «·» fallan. Ejecutar con `PYTHONIOENCODING=utf-8`.
- **Heredocs de bash** con comillas y `\n` dentro de Python se rompen. Escribe el parche en un `.py`
  y ejecútalo.

## Interfaz y comunicación con el usuario

- «Dominio» se entendía como radio o diámetro. **Es el lado del cuadrado.** Pon el significado y las
  unidades en el tooltip.
- **Un diálogo modal bloquea la automatización:** prevé una respuesta inyectable.
- **No mates procesos del usuario** (otros Python, simulaciones en marcha) sin preguntar.
