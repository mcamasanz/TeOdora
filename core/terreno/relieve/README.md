# `odora.terreno.relieve` — relieve

Equivale a **AERMAP**: traducido del código de AERMAP (dominio público); cada función indica la rutina original.

<!-- manual -->
## Qué hace
Calcula la **cota del terreno** de cada receptor y fuente y su **altura de colina** (la altura que
controla el flujo sobre el relieve, que usa el penacho para el terreno complejo), a partir de un
modelo digital del terreno.

## Entradas y salidas
| | |
|---|---|
| Entrada | fichero de control (vías CO, SO, RE, OU), MDT en GeoTIFF (geográfico o UTM WGS84), receptores (rejillas cartesianas o polares, discretos) y fuentes |
| Salida | listado (`.out`), receptores con cota y altura de colina, fuentes con cota, ficheros de detalle del dominio |

## Uso
```bash
python -m odora relieve caso.inp caso.out
```
```python
from odora.terreno.relieve.__main__ import ejecutar
ejecutar("caso.inp", "caso.out")          # en la carpeta del caso
```

## Ejemplo
Un `caso.inp` con `RE GRIDCART` de 50 × 50 receptores y un MDT de 5 m produce el fichero de
receptores con `DISCCART x y z zcolina` listo para la vía RE del penacho.

## Validación y alcance
65 de 66 casos idénticos al original carácter a carácter (el restante necesita NADCON, fuera de
alcance), incluidos los casos oficiales y casos reales de digicompost. Fuera: MDT en formato DEM
del USGS y NADCON (datums de EE. UU.).
<!-- /manual -->

## Ficheros

| Fichero | Contenido | Viene de | Equivale a |
|---|---|---|---|
| `__init__.py` | relieve (equivale a AERMAP). | `__init__.py` | — |
| `__main__.py` | programa principal (aermap.f, PROGRAM AERMAP). | `__main__.py` | `aermap.f` |
| `colina.py` | altura de colina (hill height scale) de cada receptor: sub_calchc.f (CALCHC, DISTLL, GPNHRI, GPNARC, GPNLOA) y GETNOD. | `colina.py` | `sub_calchc.f` |
| `control.py` | lectura del fichero de control (aermap.f: PRESET y sus PRE*, SETUP, LWRUPR, DEFINE, GETFLD, EXPATH, EXKEY, SETORD, COCARD, SOCARD, RECARD, OUCARD, INCLUD y todas las subrutinas de cada clave). | `control.py` | `aermap.f` |
| `cotas.py` | cota de receptores y fuentes (sub_recelv.f: RECELV, FIND4, INT2D; sub_srcelv.f: SRCELV, FIND4S; aermap.f: RECNUM). | `elev.py` | `sub_recelv.f`, `sub_srcelv.f`, `aermap.f` |
| `dominio.py` | dominio y asignación de puntos (sub_domcnv.f, sub_reccnv.f, sub_srccnv.f, sub_chkext.f, sub_demrec.f, sub_demsrc.f). | `dominio.py` | `sub_domcnv.f`, `sub_reccnv.f`, `sub_srccnv.f`, `sub_chkext.f`, `sub_demrec.f`, `sub_demsrc.f` |
| `estado.py` | estado global (módulo MAIN1 y VARINI de aermap.f) y gestión de mensajes (ERRHDL, TERRST, SUMTBL, HEADER). | `estado.py` | `aermap.f` |
| `formato.py` | Compatibilidad numérica y de formato con el Fortran de AERMAP v24142 (US EPA, dominio público). Cada función reproduce una semántica concreta del original. | `fortran.py` | — |
| `mdt_externo.py` | ficheros de terreno GeoTIFF («NED»): sub_nedchk.f (NEDCHK), sub_cnrcnv.f (CNRCNV), sub_chkadj.f (CHKADJ) y sub_initer_ned.f (INITER_NED). | `ned.py` | `sub_nedchk.f`, `sub_cnrcnv.f`, `sub_chkadj.f`, `sub_initer_ned.f` |
| `mensajes.py` | GENERADO por ../generar_mensajes.py a partir de mod_main1.f de AERMAP v24142 (US EPA, dominio público). No editar a mano. | `mensajes.py` | `mod_main1.f` |
| `salida.py` | ficheros de resultados (aermap.f: SRCOUT, WRITER, RECOUT, WRITE_INCLUD, WRITGC, WRITGP, WRITRZ, WRITDC, WRITEV, WRITDP) y resumen del fichero de salida (INPSUM). | `salida.py` | `aermap.f` |
| `tiff.py` | lector de GeoTIFF (sub_read_tifftags.f y la parte de lectura de datos de sub_initer_ned.f). | `tiff.py` | `sub_read_tifftags.f`, `sub_initer_ned.f` |
| `utm.py` | sub_utmgeo.f (UTMGEO, TMCOF, TMINV, TMFWD). Es el MISMO código que el de AERSURFACE (comprobado línea a línea), pero aquí se traduce completo: zona automática (IZONIN = 0) y la semántica de argumentos de entrada y salida… | `utm.py` | `sub_utmgeo.f` |

## Funciones por fichero

151 funciones; 126 con equivalencia explícita. Las auxiliares de la traducción no tienen rutina propia en el original.

### `__main__.py`

programa principal (aermap.f, PROGRAM AERMAP).

| Función | Definición | Equivale a |
|---|---|---|
| `_fecha()` | — | auxiliar de la traducción |
| `_nombres(argv)` | — | auxiliar de la traducción |
| `ejecutar(inpfil, outfil, fecha)` | Ejecuta AERMAP. Devuelve el Estado (con e.out, e.tmpmsg...). | — |
| `_punto(e, i, fuentes)` | Bucle sobre los ficheros de terreno de un receptor o fuente (programa principal): | auxiliar de la traducción |
| `_ausente(e, fuentes, cod, ident)` | — | auxiliar de la traducción |
| `main(argv)` | — | — |

### `colina.py`

altura de colina (hill height scale) de cada receptor: sub_calchc.f (CALCHC, DISTLL, GPNHRI, GPNARC, GPNLOA) y GETNOD.

| Función | Definición | Equivale a |
|---|---|---|
| `_gpnarc(amax, esq, pi, p1, p2)` | GPNARC: arco de meridiano entre dos latitudes (vectorizado en p2). | AERMAP `GPNARC` (sub_calchc.f) |
| `_gpnloa(amax, flat, esq, pi, dl)` | GPNLOA (escalar): constantes del punto antinodal. | AERMAP `GPNLOA` (sub_calchc.f) |
| `distll(p1, e1, p2, e2, pi)` | DISTLL/GPNHRI vectorizado: | AERMAP `DISTLL` (sub_calchc.f) |
| `_vincenty(p1, e1, p2, e2)` | Bloque «60» de GPNHRI con iteración por elemento. | auxiliar de la traducción |
| `calchc(e, irec)` | — | AERMAP `CALCHC` (sub_calchc.f) |
| `_ficheros(e, d, irec, local, indx_dem, plat1, plon1, xrs, yrs, zrec, hefmax)` | Bucle de perfiles y nodos de un fichero para un receptor. | auxiliar de la traducción |
| `_evaluar(e, d, p, z, lat, lon, xn, yn, x3, y3, z3, plat1, plon1, xrs, yrs, zrec)` | Máxima cota que cumple el criterio entre los nodos dados (o None). | auxiliar de la traducción |
| `_ecef(lat, lon)` | — | auxiliar de la traducción |
| `_ventana(e, d, p, saltos, plat1, plon1, xrs, yrs, zrec, hefmax)` | — | auxiliar de la traducción |
| `_recorrido(e, d, p, salta, plat1, plon1, xrs, yrs, zrec, hefmax)` | Caso general (perfiles de distinta longitud): | auxiliar de la traducción |
| `class _Prep` | — | auxiliar de la traducción |
| `_preparar(e, d)` | Datos de los nodos que no dependen del receptor (se calculan una vez por fichero): | auxiliar de la traducción |

### `control.py`

lectura del fichero de control (aermap.f: PRESET y sus PRE*, SETUP, LWRUPR, DEFINE, GETFLD, EXPATH, EXKEY, SETORD, COCARD, SOCARD, RECARD, OUCARD, INCLUD y todas las subrutinas de cada clave).

| Función | Definición | Equivale a |
|---|---|---|
| `leer_lineas(ruta)` | Registros del fichero tal como los lee gfortran: | — |
| `cargar(e, linea)` | READ (A512,T1,512A1) + LWRUPR: | — |
| `define(e)` | DEFINE: localiza los campos de la línea (comillas dobles delimitan campos con blancos). | AERMAP `DEFINE` (aermap.f) |
| `getfld(e)` | GETFLD: contenido de los campos 1..IFC (truncados a ILEN_FLD). Los demás conservan el valor anterior. | AERMAP `GETFLD` (aermap.f) |
| `expath(e, inpfld)` | EXPATH -> nopath. | AERMAP `EXPATH` (aermap.f) |
| `exkey(e, inpfld)` | EXKEY -> nokey. | AERMAP `EXKEY` (aermap.f) |
| `kw(e)` | — | — |
| `setord(e)` | SETORD: orden de STARTING/FINISHED y de las vías. | AERMAP `SETORD` (aermap.f) |
| `_dbl(e, i, previo, length)` | — | auxiliar de la traducción |
| `_num(e, i, previo)` | — | auxiliar de la traducción |
| `_i8(n)` | — | auxiliar de la traducción |
| `preset(e, lineas)` | PRESET: primera pasada para dimensionar los vectores. | AERMAP `PRESET` (aermap.f) |
| `_srcsiz(e)` | — | AERMAP `SRCSIZ` (aermap.f) |
| `_recsiz(e)` | — | AERMAP `RECSIZ` (aermap.f) |
| `_abrir_incluido(e)` | Nombre del fichero INCLUDED (respeta mayúsculas/minúsculas) o None. | auxiliar de la traducción |
| `_preinclud(e)` | — | AERMAP `PREINCLUD` (aermap.f) |
| `_netid_pre(e, claves)` | Parte común de PRECART/PREPOLR para decidir NETIDT/KTYPE. | auxiliar de la traducción |
| `_isc(e, clave)` | — | auxiliar de la traducción |
| `_precart(e)` | — | AERMAP `PRECART` (aermap.f) |
| `_pregencar(e)` | — | AERMAP `PREGENCAR` (aermap.f) |
| `_prexypnts(e)` | — | AERMAP `PREXYPNTS` (aermap.f) |
| `_prepolr(e)` | — | AERMAP `PREPOLR` (aermap.f) |
| `setup(e, lineas)` | SETUP: lectura del control con eco al fichero de salida. | AERMAP `SETUP` (aermap.f) |
| `cocard(e)` | — | AERMAP `COCARD` (aermap.f) |
| `_comprobar_zona_ancla(e)` | Final de COCARD: coherencia entre las zonas del dominio y la del ANCHORXY. | auxiliar de la traducción |
| `_titles(e)` | — | AERMAP `TITLES` (aermap.f) |
| `_dattyp(e)` | — | AERMAP `DATTYP` (aermap.f) |
| `_datfil(e)` | — | AERMAP `DATFIL` (aermap.f) |
| `_rango_zonas(e)` | — | auxiliar de la traducción |
| `_domain(e)` | — | AERMAP `DOMAIN` (aermap.f) |
| `_anchor(e)` | — | AERMAP `ANCHOR` (aermap.f) |
| `_terrht(e)` | — | AERMAP `TERRHT` (aermap.f) |
| `_flagdf(e)` | — | AERMAP `FLAGDF` (aermap.f) |
| `_runnot(e)` | — | AERMAP `RUNNOT` (aermap.f) |
| `_debopt(e)` | — | AERMAP `DEBOPT` (aermap.f) |
| `_nadgrids(e)` | — | AERMAP `NADGRIDS` (aermap.f) |
| `socard(e)` | — | AERMAP `SOCARD` (aermap.f) |
| `sindex(arr, n, elem)` | — | AERMAP `SINDEX` (aermap.f) |
| `_soloca(e)` | — | AERMAP `SOLOCA` (aermap.f) |
| `recard(e)` | — | AERMAP `RECARD` (aermap.f) |
| `includ(e)` | INCLUD: procesa un fichero INCLUDED (solo vías SO y RE). | AERMAP `INCLUD` (aermap.f) |
| `_netid(e, claves, m)` | Cabecera común de RECART/REPOLR. | auxiliar de la traducción |
| `_fin_red(e, m)` | Comprobaciones comunes al END de una red (RECART/REPOLR, tras SETCAR/SETPOL). | auxiliar de la traducción |
| `_sta(e, m)` | — | auxiliar de la traducción |
| `recart(e)` | — | AERMAP `RECART` (aermap.f) |
| `_gencar(e)` | — | AERMAP `GENCAR` (aermap.f) |
| `_xypnts(e)` | — | AERMAP `XYPNTS` (aermap.f) |
| `_sbyval(a1, a2, inx)` | SBYVAL: ordenación por selección (estable como el original) de a1, arrastrando a2. | AERMAP `SBYVAL` (aermap.f) |
| `_setred(e, tipo)` | SETCAR (tipo 'GC') / SETPOL (tipo 'GP'). | AERMAP `SETCAR` (aermap.f) |
| `repolr(e)` | — | AERMAP `REPOLR` (aermap.f) |
| `_polorg(e)` | — | AERMAP `POLORG` (aermap.f) |
| `_poldst(e)` | — | AERMAP `POLDST` (aermap.f) |
| `_genpol(e)` | — | AERMAP `GENPOL` (aermap.f) |
| `_radrng(e)` | — | AERMAP `RADRNG` (aermap.f) |
| `_terhgt(e)` | — | AERMAP `TERHGT` (aermap.f) |
| `_flghgt(e)` | — | AERMAP `FLGHGT` (aermap.f) |
| `_lleno(e, m)` | — | auxiliar de la traducción |
| `_avanzar(e, i1, i2, i3, i4, i5)` | — | auxiliar de la traducción |
| `discar(e)` | — | AERMAP `DISCAR` (aermap.f) |
| `dispol(e)` | — | AERMAP `DISPOL` (aermap.f) |
| `evcart(e)` | — | AERMAP `EVCART` (aermap.f) |
| `oucard(e)` | — | AERMAP `OUCARD` (aermap.f) |
| `_oufich(e, m, atributo, txt_err)` | — | auxiliar de la traducción |
| `_abierto(e, nombre)` | INQUIRE(FILE=..., OPENED=...): | auxiliar de la traducción |
| `_oudeb(e, m, atributos)` | — | auxiliar de la traducción |

### `cotas.py`

cota de receptores y fuentes (sub_recelv.f: RECELV, FIND4, INT2D; sub_srcelv.f: SRCELV, FIND4S; aermap.f: RECNUM).

| Función | Definición | Equivale a |
|---|---|---|
| `class _Indice` | El índice de perfiles tal como lo deja leído RECELV (vectores 1..NUMPRF). | auxiliar de la traducción |
| `indice(d)` | — | — |
| `elevacion(e, i, jdem, fuentes)` | RECELV(IREC,JDEM) / SRCELV(ISRC,JDEM). | AERMAP `RECELV` (sub_recelv.f) |
| `find4(e, d, ix, ir, xrr, yrr, fuentes)` | FIND4 / FIND4S. Devuelve (ierr, nx, ny1, ny2, x, y) con índices 1..2 / 1..4. | AERMAP `FIND4` (sub_recelv.f) |
| `int2d(params, x1, y1, xvalue, yvalue)` | INT2D: interpolación bilineal entre los cuatro nodos (orden 1-2-3-4 de FIND4). | AERMAP `INT2D` (sub_recelv.f) |

### `dominio.py`

dominio y asignación de puntos (sub_domcnv.f, sub_reccnv.f, sub_srccnv.f, sub_chkext.f, sub_demrec.f, sub_demsrc.f).

| Función | Definición | Equivale a |
|---|---|---|
| `_isphere_nada(e)` | SELECT CASE (NADA) de DOMCNV/RECCNV/SRCCNV. | auxiliar de la traducción |
| `_a_geo(este, norte, zona, isph)` | UTMGEO 333 con ARGE = ARGN = 0 al entrar -> (slon, slat). | AERMAP `UTMGEO` (sub_utmgeo.f) |
| `_a_utm(slon, slat, zona, isph)` | UTMGEO 555 con XARG = YARG = 0 -> (zona_salida, este, norte, slon_modificada). | AERMAP `UTMGEO` (sub_utmgeo.f) |
| `domcnv(e)` | — | AERMAP `DOMCNV` (sub_domcnv.f) |
| `puntos_cnv(e, fuentes)` | RECCNV (fuentes=False) / SRCCNV (fuentes=True), rama sin NADCON. | AERMAP `RECCNV` (sub_reccnv.f) |
| `chkext(e)` | — | AERMAP `CHKEXT` (sub_chkext.f) |
| `puntos_dem(e, fuentes)` | DEMREC (fuentes=False) / DEMSRC (fuentes=True): | AERMAP `DEMREC` (sub_demrec.f) |
| `_peor_resolucion(a, d, eps)` | Condiciones del error 326/327: | auxiliar de la traducción |

### `estado.py`

estado global (módulo MAIN1 y VARINI de aermap.f) y gestión de mensajes (ERRHDL, TERRST, SUMTBL, HEADER).

| Función | Definición | Equivale a |
|---|---|---|
| `feq(a, b)` | Igualdad de cadenas de Fortran: | — |
| `fx(s, n)` | Asignación a una variable CHARACTER*n: | — |
| `fa(s, w)` | Descriptor de salida Aw: si el texto es más largo, se trunca; si es más corto, se escribe ajustado a la DERECHA. | — |
| `vec(n, valor)` | Vector 1..n (índice 0 sin usar). | — |
| `class NoTraducido` | Opción del original que queda fuera del alcance de la traducción (DEM USGS, NADCON). | — |
| `class AbortoFortran` | Situación en la que el ejecutable original (compilado con -fbounds-check) aborta con un error de ejecución de Fortran: | — |
| `class Estado` | — | — |

### `formato.py`

Compatibilidad numérica y de formato con el Fortran de AERMAP v24142 (US EPA, dominio público). Cada función reproduce una semántica concreta del original.

| Función | Definición | Equivale a |
|---|---|---|
| `nint(x)` | NINT/IDNINT: redondeo al entero más cercano, empates LEJOS del cero. | — |
| `stodbl(s, length, previo)` | STODBL de AERMAP (aermap.f). | AERMAP `STODBL` (aermap.f) |
| `stonum(s, length, previo)` | STONUM: como STODBL pero en PRECISIÓN SIMPLE (REAL) y sin exponente D. Devuelve (valor float32 promovido a float, imuti). | AERMAP `STONUM` (aermap.f) |

### `mdt_externo.py`

ficheros de terreno GeoTIFF («NED»): sub_nedchk.f (NEDCHK), sub_cnrcnv.f (CNRCNV), sub_chkadj.f (CHKADJ) y sub_initer_ned.f (INITER_NED).

| Función | Definición | Equivale a |
|---|---|---|
| `class Dem` | Parámetros de un fichero de terreno (los vectores (IDEM) del original). | — |
| `_i8(n)` | — | auxiliar de la traducción |
| `_q_d24(x)` | Ida y vuelta por D24.15: 15 cifras significativas. | auxiliar de la traducción |
| `_q_f155(x)` | Ida y vuelta por F15.5. | auxiliar de la traducción |
| `isphere_nadd(dem)` | SELECT CASE (NADD) habitual de RECELV/CALCHC/DEMREC/CHKEXT. | — |
| `nedchk(e)` | — | AERMAP `NEDCHK` (sub_nedchk.f) |
| `_datum(e, m, d, idem, codigo, tabla)` | — | auxiliar de la traducción |
| `cnrcnv(e)` | — | AERMAP `CNRCNV` (sub_cnrcnv.f) |
| `chkadj(e)` | — | AERMAP `CHKADJ` (sub_chkadj.f) |
| `_utm_de_lat(dmlat, eps)` | — | auxiliar de la traducción |
| `_lat_de_utm(dmutm, eps)` | — | auxiliar de la traducción |
| `initer_ned(e)` | — | AERMAP `INITER_NED` (sub_initer_ned.f) |
| `_nadflg(nada, nadd)` | — | auxiliar de la traducción |
| `_perfiles(e, d, typ, xdmn, ydmn, xdmx, ydmx, zminshft, zmaxshft, z)` | Bucle de perfiles (columnas) y nodos de INITER_NED. | auxiliar de la traducción |

### `salida.py`

ficheros de resultados (aermap.f: SRCOUT, WRITER, RECOUT, WRITE_INCLUD, WRITGC, WRITGP, WRITRZ, WRITDC, WRITEV, WRITDP) y resumen del fichero de salida (INPSUM).

| Función | Definición | Equivale a |
|---|---|---|
| `ff(x, w, d)` | Fw.d de gfortran. | — |
| `_cab_version(e)` | — | auxiliar de la traducción |
| `_cabecera(e, n, que, ancho)` | — | auxiliar de la traducción |
| `n_dem(e)` | — | — |
| `srcout(e)` | — | AERMAP `SRCOUT` (aermap.f) |
| `writer(e)` | WRITER: relee el control y escribe el fichero RECEPTOR. | AERMAP `WRITER` (aermap.f) |
| `_escribir(ruta, lineas)` | — | auxiliar de la traducción |
| `recout(e, en_incluido)` | — | AERMAP `RECOUT` (aermap.f) |
| `write_includ(e)` | — | AERMAP `WRITE_INCLUD` (aermap.f) |
| `_netid_w(e, claves, m)` | Cabecera común de WRITGC/WRITGP -> idst o None. | auxiliar de la traducción |
| `_eco(e)` | — | auxiliar de la traducción |
| `writgc(e)` | — | AERMAP `WRITGC` (aermap.f) |
| `writgp(e)` | — | AERMAP `WRITGP` (aermap.f) |
| `writrz(e)` | WRITRZ: ELEV, HILL (y FLAG si hay FLAGPOLE) de la red, 6 valores por línea. | AERMAP `WRITRZ` (aermap.f) |
| `writdc(e)` | — | AERMAP `WRITDC` (aermap.f) |
| `writev(e)` | — | AERMAP `WRITEV` (aermap.f) |
| `writdp(e)` | — | AERMAP `WRITDP` (aermap.f) |
| `inpsum(e)` | — | AERMAP `INPSUM` (aermap.f) |

### `tiff.py`

lector de GeoTIFF (sub_read_tifftags.f y la parte de lectura de datos de sub_initer_ned.f).

| Función | Definición | Equivale a |
|---|---|---|
| `class Etiqueta` | — | — |
| `class LecturaTiff` | Resultado de read_tifftags. | — |
| `class _Fichero` | Acceso por bytes (registros de 1 byte del original). | auxiliar de la traducción |
| `leer_etiquetas(e, ruta)` | read_tifftags. `e` es el Estado (para ERRHDL). | — |
| `leer_elevaciones(ruta, d)` | Lectura de los datos de INITER_NED. | — |

### `utm.py`

sub_utmgeo.f (UTMGEO, TMCOF, TMINV, TMFWD). Es el MISMO código que el de AERSURFACE (comprobado línea a línea), pero aquí se traduce completo: zona automática (IZONIN = 0) y la semántica de argumentos de entrada y salida…

| Función | Definición | Equivale a |
|---|---|---|
| `_tmcof(A)` | — | AERMAP `TMCOF` (sub_utmgeo.f) |
| `_tminv(north, east, A)` | -> (slat, slon) o None si está fuera de rango (IERR = 1). | AERMAP `TMINV` (sub_utmgeo.f) |
| `_tmfwd(slat, slon, A)` | -> (north, east) o None si está fuera de rango (IERR = 1). | AERMAP `TMFWD` (sub_utmgeo.f) |
| `_idint(x)` | IDINT: truncamiento hacia cero. | auxiliar de la traducción |
| `utmgeo(kod, izonin, east, north, slon, slat, ispher)` | UTMGEO tal cual. Devuelve (izonout, east, north, slon, slat). | AERMAP `UTMGEO` (sub_utmgeo.f) |
| `utm_a_geo(east, north, zona, ispher)` | KOD = 333 con las salidas a 0 al entrar, como hacen los llamadores de AERMAP (ARGE = ARGN = 0). | — |
| `geo_a_utm(slon, slat, zona, ispher)` | KOD = 555 con XARG = YARG = 0 al entrar. | — |
| `utm_zona(lon)` | Función utm_zone de sub_cnrcnv.f (longitud en grados, oeste negativo). | — |
