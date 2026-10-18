# `lagaus.terreno.geofisica` — geofisica

Equivale a **MAKEGEO**: reescrito en **sala limpia** desde la documentación publicada de MAKEGEO; la equivalencia es funcional: nunca se ha abierto su código.

<!-- manual -->
## Qué hace
Prepara la **malla geofísica** del campo de viento: en cada celda, el uso del suelo dominante y
las propiedades de superficie ponderadas por las fracciones de cada uso (rugosidad, albedo,
Bowen, flujo de calor del suelo, calor antropogénico, índice foliar) y la cota media.

## Entradas y salidas
| | |
|---|---|
| Entrada | fichero de control, fracciones de uso por celda (LU.DAT) y cotas (TERR.DAT) |
| Salida | GEO.DAT para `meteo.viento3d`, listado y mallas de control de calidad |

`corine.py` prepara LU.DAT y TERR.DAT desde una rejilla fina de CORINE y del MDT.

## Uso
```bash
python -m lagaus geofisica geo.inp
```
```python
from lagaus.terreno.geofisica import corine
from lagaus.terreno.geofisica.principal import ejecutar
corine.preparar("caso", uso_fino, z_fino, extension, res_m=250)   # escribe lu.dat, terr.dat, geo.inp
ejecutar(["caso/geo.inp"])
```

## Ejemplo
Para un dominio de 10 × 10 km a 250 m en Lleida, cada celda recibe el uso dominante de CORINE y una
z0 media ponderada en lugar de un valor fijo para todo el dominio.

## Validación y alcance
Reescrito en **sala limpia** (sin el código del original). 24 de 24 casos dentro del criterio:
14 idénticos y 10 con ±1 en la última cifra en 20 de ~400 000 valores. Fuera: división de
categorías (NSPLIT), segundo fichero de usos y proyecciones distintas de UTM.
<!-- /manual -->

## Ficheros

| Fichero | Contenido | Viene de | Equivale a |
|---|---|---|---|
| `__init__.py` | Geofísica de la malla para CALMET (equivalente propio, en sala limpia, de MAKEGEO). | `__init__.py` | funcional (MAKEGEO) |
| `__main__.py` | — | `__main__.py` | funcional (MAKEGEO) |
| `calculo.py` | Geofísica de la malla para CALMET (GEO.DAT) a partir de fracciones de uso del suelo y cotas. | `geo.py` | funcional (MAKEGEO) |
| `control.py` | Lector de ficheros de control con la sintaxis de los preprocesadores de CALMET. | `control.py` | funcional (MAKEGEO) |
| `corine.py` | Adaptador de datos propios a la rejilla de CALMET: CORINE Land Cover + MDT -> fracciones de uso del suelo y cota media por celda, y de ahí LU.DAT, TERR.DAT y el fichero de control. | `corine.py` | funcional (MAKEGEO) |
| `principal.py` | Programa principal: ``python -m lagaus.terreno.geofisica [fichero_de_control]``. | `principal.py` | funcional (MAKEGEO) |

## Funciones por fichero

27 funciones; 0 con equivalencia explícita. Las auxiliares de la traducción no tienen rutina propia en el original.

### `calculo.py`

Geofísica de la malla para CALMET (GEO.DAT) a partir de fracciones de uso del suelo y cotas.

| Función | Definición | Equivale a |
|---|---|---|
| `class ErrorGeo` | Error que impide escribir el GEO.DAT (el original para con un mensaje FATAL). | — |
| `_cabecera(lineas)` | Cabecera «2.0» común a LU.DAT y TERR.DAT: | — |
| `_malla(lineas, k)` | PMAP, zona/hemisferio u origen, datum y la línea de la malla; | — |
| `leer_lu(ruta)` | LU.DAT de fracciones (formato 2.0): | — |
| `leer_terr(ruta)` | TERR.DAT de cotas medias por celda (formato 2.0): | — |
| `class Tabla` | Propiedades por categoría de entrada (grupo 4b) y datos de las categorías de salida. | — |
| `calcular(c, tabla, fr)` | Campos de salida a partir de las fracciones [ny, nx, ncat]. | — |
| `_fila(vals, fmt, por_linea)` | Valores de una fila con el formato y comas como separador; | — |
| `_f(x, w, d)` | Fortran Fw.d (asteriscos si no cabe). | — |
| `escribir_geo(ruta, c, malla, campos, z, comentario)` | — | — |
| `_e_fortran(x, w, d)` | Fortran Ew.d sin factor de escala: | — |
| `escribir_grd(ruta_lu, ruta_te, malla, campos, z, vacios)` | Ficheros de control en formato Surfer ASCII (DSAA): | — |

### `control.py`

Lector de ficheros de control con la sintaxis de los preprocesadores de CALMET.

| Función | Definición | Equivale a |
|---|---|---|
| `leer(texto)` | Devuelve (título, {VARIABLE: | — |
| `class Control` | Acceso tipado a las variables leídas. | — |

### `corine.py`

Adaptador de datos propios a la rejilla de CALMET: CORINE Land Cover + MDT -> fracciones de uso del suelo y cota media por celda, y de ahí LU.DAT, TERR.DAT y el fichero de control.

| Función | Definición | Equivale a |
|---|---|---|
| `malla_calmet(ext, forma, res_m)` | Factor de agregación y malla gruesa (alineada con la esquina SO de la fina). | — |
| `fracciones(uso, fac)` | Fracción de cada clase CORINE (columnas en el orden de CODIGOS) por celda gruesa. | — |
| `cotas(z, fac)` | — | — |
| `escribir_lu(ruta, fr, x0_km, y0_km, d_km, zona, hem, datum)` | — | — |
| `escribir_terr(ruta, z, x0_km, y0_km, d_km, zona, hem, datum)` | — | — |
| `escribir_control(ruta, titulo, nx, ny, x0_km, y0_km, d_km, ludat, terrdat, geodat, runlst, zona, hem, datum)` | Fichero de control con la sintaxis publicada (grupos 0 a 4). | — |
| `preparar(carpeta, uso, z, ext, res_m, titulo, zona, hem, datum)` | Escribe en `carpeta` lu.dat, terr.dat y geo.inp para la malla CALMET de `res_m` metros a partir de las rejillas finas (fila 0 al sur) de CORINE y cotas. | — |

### `principal.py`

Programa principal: ``python -m lagaus.terreno.geofisica [fichero_de_control]``.

| Función | Definición | Equivale a |
|---|---|---|
| `class NoImplementado` | — | — |
| `_nombres(c)` | — | — |
| `_malla_control(c)` | — | — |
| `_comprobar(m, otra, nombre)` | — | — |
| `ejecutar(argv, comentario)` | — | — |
| `_listado(ruta, log, t0)` | — | — |
