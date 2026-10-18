# `lagaus.terreno.superficie` — superficie

Equivale a **AERSURFACE**: traducido del código de AERSURFACE (dominio público); cada función indica la rutina original.

<!-- manual -->
## Qué hace
Calcula las **características de la superficie** alrededor del emplazamiento (rugosidad z0,
razón de Bowen y albedo) por sectores de viento y por mes o estación, a partir del uso del suelo,
el sellado y el arbolado. Son la entrada de superficie de `meteo.capa_limite`.

## Entradas y salidas
| | |
|---|---|
| Entrada | fichero de control y GeoTIFF de uso del suelo (clases tipo NLCD), opcionalmente sellado e índice de arbolado |
| Salida | tabla de z0, Bowen y albedo por sector y periodo, registro del cálculo |

`corine.py` es el **adaptador europeo**: traduce CORINE (CLC) a las clases que espera el motor,
reproyecta a una Albers centrada en el sitio a 30 m y escribe los GeoTIFF y el control.

## Uso
```bash
python -m lagaus superficie control.inp
python -m lagaus.terreno.superficie.corine --npz elevacion_uso.npz --lat 41.61806 --lon 0.34259 --salida caso
```
```python
from lagaus.terreno.superficie.__main__ import main
main(["control.inp"])
```

## Ejemplo
Con el CORINE de Lleida (41,618° N, 0,343° E), 12 sectores y frecuencia mensual, la salida da para
cada sector y mes la z0 (p. ej. 0,08 m en regadío, 0,5 m en frutales con la clase de usuario) que
pasa al `.sfc`.

## Validación y alcance
48 de 48 casos idénticos al original (control, salida y registro), incluido el caso oficial y
Lleida con CORINE. Fuera: datum NAD27/NADCON y el volcado de depuración EFFRAD.
<!-- /manual -->

## Ficheros

| Fichero | Contenido | Viene de | Equivale a |
|---|---|---|---|
| `__init__.py` | paquete | `__init__.py` | — |
| `__main__.py` | python -m lagaus.terreno.superficie control.inp | `__main__.py` | — |
| `albers.py` | Proyección cónica equivalente de Albers tal como la implementa AERSURFACE v26135 (mod_Geographic.f: ComputeQ, LATLON2ALBERS, ALBERS2LATLON; Snyder 1987). | `albers.py` | `mod_Geographic.f` |
| `control.py` | Fichero de control de AERSURFACE (mod_ProcCtrlFile.f), con la misma semántica: valores por defecto, orden de procesado de las palabras clave, ordenación de sectores (incluida la peculiar reordenación de POSTSECT) y texto… | `control.py` | `mod_ProcCtrlFile.f` |
| `corine.py` | Adaptador CORINE -> AERSURFACE para Europa/España (NO forma parte de la traducción: es una decisión nuestra, documentada aquí). | `corine.py` | — |
| `formato.py` | Compatibilidad numérica con el Fortran de AERSURFACE v26135 (US EPA, dominio público). | `fortran.py` | — |
| `geotiff.py` | Lectura de los GeoTIFF de NLCD con la semántica de AERSURFACE (mod_TiffParams.f, mod_GetData.f: GetGridVars + Read_TiffData), usando rasterio en lugar de su lector propio de TIFF (≈3.000 líneas: OPTIMIZACIÓN, y además ad… | `geotiff.py` | `mod_TiffParams.f`, `mod_GetData.f` |
| `nucleo.py` | Núcleo de AERSURFACE v26135 traducido y vectorizado (mod_GetData.f: GetLCCounts, GetGridVars, ProcessLC; mod_AvgParams.f: AvgSfcCharsSimple, AvgSfcCharsGeom, EffectiveRoughness4, z0_eff_func; mod_LandCoverParams.f: Conso… | `nucleo.py` | `mod_GetData.f`, `mod_AvgParams.f`, `mod_LandCoverParams.f` |
| `salida.py` | Escritura de salidas con el formato exacto de AERSURFACE v26135 (mod_SfcChars.f: Write_SfcChars; mod_GetData.f: Write_DbgGrid). Solo cambian las dos líneas de fecha/hora. | `salida.py` | `mod_SfcChars.f`, `mod_GetData.f` |
| `tablas.py` | TABLAS GENERADAS AUTOMÁTICAMENTE por ../generar_tablas.py a partir de mod_LandCoverParams.f (AERSURFACE v26135, US EPA, dominio público). NO EDITAR A MANO. | `tablas.py` | `mod_LandCoverParams.f` |
| `utm.py` | UTM <-> geográficas tal como lo hace AERSURFACE v26135 (mod_Geographic.f: UTMGEO, TMCOF, TMINV, TMFWD; rutinas de origen USGS). | `utm.py` | `mod_Geographic.f` |

## Funciones por fichero

44 funciones; 17 con equivalencia explícita. Las auxiliares de la traducción no tienen rutina propia en el original.

### `__main__.py`

python -m lagaus.terreno.superficie control.inp

| Función | Definición | Equivale a |
|---|---|---|
| `main(argv)` | — | — |

### `albers.py`

Proyección cónica equivalente de Albers tal como la implementa AERSURFACE v26135 (mod_Geographic.f: ComputeQ, LATLON2ALBERS, ALBERS2LATLON; Snyder 1987).

| Función | Definición | Equivale a |
|---|---|---|
| `class Albers` | — | — |

### `control.py`

Fichero de control de AERSURFACE (mod_ProcCtrlFile.f), con la misma semántica: valores por defecto, orden de procesado de las palabras clave, ordenación de sectores (incluida la peculiar reordenación de POSTSECT) y texto…

| Función | Definición | Equivale a |
|---|---|---|
| `class Control` | — | — |
| `class ErrorControl` | — | — |
| `_campos(linea)` | Campos de una línea: como el original, en MAYÚSCULAS salvo lo entrecomillado. | auxiliar de la traducción |
| `_titulo(linea, kw)` | TITLE1 = RUNST1(LOCE(2)+2:): | auxiliar de la traducción |
| `leer(path)` | — | — |
| `_sector(c, f)` | — | AERSURFACE `SECTOR` (mod_ProcCtrlFile.f) |
| `_postsect(c)` | POSTSECT: sectores por defecto u ordenación y comprobación de los del usuario. | AERSURFACE `POSTSECT` (mod_ProcCtrlFile.f) |
| `_textos_meses(c)` | — | auxiliar de la traducción |

### `corine.py`

Adaptador CORINE -> AERSURFACE para Europa/España (NO forma parte de la traducción: es una decisión nuestra, documentada aquí).

| Función | Definición | Equivale a |
|---|---|---|
| `albers_local(lat, lon)` | Albers centrada en el emplazamiento (giro de cuadrícula ~0) con datum WGS84. | — |
| `a_geotiff(clc, transform, crs, lat, lon, carpeta, prefijo, imp, can, codigos_usuario)` | clc: array de códigos CORINE en `crs`/`transform`. imp/can: arrays opcionales en % (0-100) en la MISMA rejilla. Escribe <prefijo>_lc.tif (y _imp/_can) y devuelve sus rutas. | — |
| `desde_npz(npz, lat, lon, carpeta)` | Desde el elevacion_uso.npz de digicompost (USE = CORINE, ext en EPSG:25830). | — |
| `control(rutas, lat, lon, freq, sectores, ap, clima, zorad, titulo, sfc, anio)` | — | — |
| `main(argv)` | — | — |

### `formato.py`

Compatibilidad numérica con el Fortran de AERSURFACE v26135 (US EPA, dominio público).

| Función | Definición | Equivale a |
|---|---|---|
| `nint(x)` | NINT/IDNINT de Fortran: redondeo al entero más cercano, empates LEJOS del cero (numpy redondea los empates al par). | — |
| `nint_arr(x)` | NINT vectorizado (empates lejos del cero). | — |
| `stodbl(s)` | STODBL de AERSURFACE: convierte texto en número acumulando dígito a dígito (CNUM = CNUM*10 + d; decimales con FDEC = FDEC/10). Puede diferir en el último bit del redondeo correcto … | AERSURFACE `STODBL` (mod_ProcCtrlFile.f) |
| `fmt_f(valor, w, d)` | Descriptor Fw.d de Fortran (alineado a la derecha; | — |
| `fmt_i(valor, w)` | — | — |

### `geotiff.py`

Lectura de los GeoTIFF de NLCD con la semántica de AERSURFACE (mod_TiffParams.f, mod_GetData.f: GetGridVars + Read_TiffData), usando rasterio en lugar de su lector propio de TIFF (≈3.000 líneas: OPTIMIZACIÓN, y además ad…

| Función | Definición | Equivale a |
|---|---|---|
| `class TiffVars` | — | — |
| `leer_tags(path)` | — | — |
| `leer_ventana(v, fila0, filas, col0, cols, inicial, es_uso)` | Rejilla [filas, cols] desde la fila/columna `fila0`/`col0` (1-based, del fichero). | — |

### `nucleo.py`

Núcleo de AERSURFACE v26135 traducido y vectorizado (mod_GetData.f: GetLCCounts, GetGridVars, ProcessLC; mod_AvgParams.f: AvgSfcCharsSimple, AvgSfcCharsGeom, EffectiveRoughness4, z0_eff_func; mod_LandCoverParams.f: Conso…

| Función | Definición | Equivale a |
|---|---|---|
| `class ErrorAersurface` | — | — |
| `class Rejilla` | — | — |
| `class Resultado` | — | — |
| `_tabla(d)` | — | auxiliar de la traducción |
| `tablas_consolidadas(airport, humedad, arido)` | — | — |
| `rejilla(v, alb_proj, lat, lon, inicial, es_uso, extra)` | — | — |
| `_z0_eff_func(z0_init, xrad, href)` | — | AERSURFACE `Z0_EFF_FUNC` (mod_AvgParams.f) |
| `effective_roughness4(z0p, href, delx, xdnum)` | z0p: lista 1-based (z0p[0] sin uso). Devuelve (z0_eff, fetch). | — |
| `ejecutar(c)` | — | — |

### `salida.py`

Escritura de salidas con el formato exacto de AERSURFACE v26135 (mod_SfcChars.f: Write_SfcChars; mod_GetData.f: Write_DbgGrid). Solo cambian las dos líneas de fecha/hora.

| Función | Definición | Equivale a |
|---|---|---|
| `_cabecera(texto, ahora)` | — | auxiliar de la traducción |
| `_ids_no_aeropuerto(c)` | — | auxiliar de la traducción |
| `escribir_sfc(path, c, r, ahora)` | — | — |
| `_a(texto, w)` | Descriptor Aw de Fortran: ajusta a la derecha si sobra, recorta si falta. | auxiliar de la traducción |
| `escribir_log(path, c, r, ahora)` | Parte CALCULADA del .log del original (desde «Getting grid information»): | — |
| `escribir_rejilla(path, g, tipo, nombre_tiff, inicial, ahora)` | — | — |

### `utm.py`

UTM <-> geográficas tal como lo hace AERSURFACE v26135 (mod_Geographic.f: UTMGEO, TMCOF, TMINV, TMFWD; rutinas de origen USGS).

| Función | Definición | Equivale a |
|---|---|---|
| `_tmcof(A)` | — | AERSURFACE `TMCOF` (mod_Geographic.f) |
| `_parametros(izone, ispher, sur)` | — | auxiliar de la traducción |
| `_tminv(north, east, A)` | — | AERSURFACE `TMINV` (mod_Geographic.f) |
| `_tmfwd(slat, slon, A)` | — | AERSURFACE `TMFWD` (mod_Geographic.f) |
| `utm_a_geo(east, north, zona, ispher)` | UTMGEO(KOD=333): -> (lat, lon) en grados decimales (oeste negativo), como hace GetGridVars al dividir entre 3600. | AERSURFACE `UTMGEO` (mod_Geographic.f) |
| `geo_a_utm(lat, lon, zona, ispher)` | UTMGEO(KOD=555) con zona forzada: | AERSURFACE `UTMGEO` (mod_Geographic.f) |
