# `teodors.terreno.edificios` — edificios

Equivale a **BPIPPRM**: traducido del código de BPIPPRM (dominio público); cada función indica la rutina original.

<!-- manual -->
## Qué hace
Calcula, para cada chimenea y cada una de las 36 direcciones de viento, las **dimensiones del
edificio que la afecta** (altura, anchura, longitud y desplazamientos) y la altura de buena
práctica (GEP). Son las que usa el penacho para la estela y la cavidad de los edificios.

## Entradas y salidas
| | |
|---|---|
| Entrada | fichero con los edificios (niveles y vértices) y las chimeneas |
| Salida | fichero con las dimensiones por dirección (tarjetas de la vía SO del penacho) y resumen |

## Uso
```bash
python -m teodors edificios entrada.inp salida.out resumen.sum
```
```python
from teodors.terreno.edificios.__main__ import main
main(["entrada.inp", "salida.out", "resumen.sum"])
```

## Ejemplo
Una nave de 70 × 20 × 9 m y una chimenea de 15 m a 10 m de su fachada dan, para el viento del
oeste, una altura de edificio de 9 m y la anchura proyectada de la nave; con esas tarjetas el
penacho activa la estela.

## Validación y alcance
37 de 37 casos idénticos al original (salida, resumen y pantalla). Sin opciones fuera de alcance.
Los bucles de direcciones van compilados con numba (`gep_rapido.py`).
<!-- /manual -->

## Ficheros

| Fichero | Contenido | Viene de | Equivale a |
|---|---|---|---|
| `__init__.py` | paquete | `__init__.py` | — |
| `__main__.py` | python -m teodors.terreno.edificios entrada salida resumen (los mismos argumentos que el original) Códigos de salida: 0 terminado, 3 el original aborta en ese punto con un error de ejecución (se escribe su mismo mensaje). | `__main__.py` | — |
| `formato.py` | Compatibilidad de E/S y numérica con el Fortran original (copia del módulo de la traducción de AERMET, core/meteo/capa_limite/formato.py, validado allí; BPIPPRM 04274 está compilado con Compaq Visual Fortran 6.6, anteces… | `fortran.py` | — |
| `gep_rapido.py` | Bucles GEP de BPIPPRM 04274 (1.440 direcciones de cuarto de grado) compilados con numba. | `gep_rapido.py` | — |
| `nucleo.py` | Building Profile Input Program for PRIME. | `nucleo.py` | `Bpipprm.for` |

## Funciones por fichero

59 funciones; 35 con equivalencia explícita. Las auxiliares de la traducción no tienen rutina propia en el original.

### `__main__.py`

python -m teodors.terreno.edificios entrada salida resumen (los mismos argumentos que el original) Códigos de salida: 0 terminado, 3 el original aborta en ese punto con un error de ejecución (se escribe su mismo mensaje).

| Función | Definición | Equivale a |
|---|---|---|
| `main(argv)` | — | — |

### `formato.py`

Compatibilidad de E/S y numérica con el Fortran original (copia del módulo de la traducción de AERMET, core/meteo/capa_limite/formato.py, validado allí; BPIPPRM 04274 está compilado con Compaq Visual Fortran 6.6, anteces…

| Función | Definición | Equivale a |
|---|---|---|
| `class ErrorEjecucion` | Situación en la que el original aborta con un error de ejecución de Intel Fortran (una lectura interna sin IOSTAT que falla…) o no termina. | — |
| `dsign(a, b)` | SIGN/DSIGN: /a/ con el signo de b (el -0.0 cuenta como positivo salvo MENOS_CERO). | — |
| `nint(x)` | NINT/IDNINT: redondeo al entero más cercano, empates LEJOS del cero. | — |
| `sngl(x)` | SNGL / literal de precisión simple promovido a doble. | — |
| `ftrunc(x)` | INT() de un real: trunca hacia cero. | — |
| `_analizar(fmt)` | Devuelve (secuencia plana, índice de reversión). | auxiliar de la traducción |
| `_expandir(it)` | — | auxiliar de la traducción |
| `_lista(s, i)` | — | auxiliar de la traducción |
| `_redondear(x, d)` | Cadena decimal de /x/ con d decimales (redondeo correcto del valor binario exacto). | auxiliar de la traducción |
| `fmt_f(x, w, d)` | — | — |
| `_fmt_f_lento(x, w, d)` | — | auxiliar de la traducción |
| `_mantisa(x, d)` | Devuelve (dígitos, exponente k) con /x/ = 0.dígitos × 10^k, d dígitos. | auxiliar de la traducción |
| `fmt_e(x, w, d, e)` | — | — |
| `fmt_g(x, w, d, e)` | — | — |
| `fmt_i(v, w, m)` | — | — |
| `fmt_a(s, w)` | — | — |
| `_compilar_rapido(fmt)` | Plan secuencial (A, I, F, literales, X y ':') para la vía rápida de WRITE; | auxiliar de la traducción |
| `_plantilla(segs, ndatos)` | Plantilla '%' equivalente al FORMAT cuando se escriben todos sus datos: | auxiliar de la traducción |
| `_con_plantilla(pl, items)` | Registro con la plantilla '%'; | auxiliar de la traducción |
| `_escribir_rapido(segs, items)` | — | auxiliar de la traducción |
| `fwrite(fmt)` | WRITE formateado: devuelve la lista de registros escritos. | — |
| `class ErrorLectura` | — | — |
| `_a_entero(campo)` | — | auxiliar de la traducción |
| `_a_real(campo, d, lista)` | — | auxiliar de la traducción |
| `_compilar_lectura(fmt)` | Campos (descriptor, posición, anchura, decimales) de un FORMAT de lectura secuencial de un solo registro (I, F y A con anchura, nX); | auxiliar de la traducción |
| `fread(fmt, registros, tipos)` | READ formateado. `registros` es una lista de líneas (se consumen en orden con '/' o la reversión); `tipos` son 'i', 'f' o ('a', longitud). Devuelve (valores, iostat, nregistros). | — |
| `_fichas(rec)` | Divide un registro en fichas de lectura dirigida por lista. | auxiliar de la traducción |
| `lread(registros, tipos, previos)` | READ(...,*) . `registros`: cadena (fichero interno) o lista de líneas (fichero externo: sigue en los registros siguientes). `tipos`: 'i', 'f', ('a', lon) o 'a'. Devuelve (valores, … | — |
| `class Fichero` | Fichero secuencial formateado. | — |
| `ch(s, i)` | Carácter i (1-based) de una variable CHARACTER: | — |
| `sub(s, i, j)` | Subcadena s(i:j) de Fortran (1-based, inclusiva), con relleno de blancos. | — |
| `adjustl(s)` | ADJUSTL conservando la longitud. | — |
| `fx(s, n)` | Asignación a CHARACTER*n (trunca o rellena con blancos). | — |

### `gep_rapido.py`

Bucles GEP de BPIPPRM 04274 (1.440 direcciones de cuarto de grado) compilados con numba.

| Función | Definición | Equivale a |
|---|---|---|
| `_r4(x)` | — | auxiliar de la traducción |
| `_width(X, Y, ND, XC, YC, XMAX, XMIN, YMAX, YMIN, csaw, snaw, i, j, c)` | — | BPIPPRM `WIDTH` (Bpipprm.for) |
| `_dislin(x1, y1, x2, y2, l5, xsp, ysp)` | — | BPIPPRM `DISLIN` (Bpipprm.for) |
| `_cnrlin(x1, y1, x2, y2, xkp, ykp)` | — | BPIPPRM `CNRLIN` (Bpipprm.for) |
| `_gpc(G, GI, BELEV, SB, TNUM2, TLIST2, GEPIN, mxtrs, d, i, c, s, tw, ws, hta, ch, ig)` | G[:, 0..3] = GEP, GEPBH, GEPBW, GDIRS; | BPIPPRM `GPC` (Bpipprm.for) |
| `gep_niveles(X, Y, ND, NTRS, TH, BELEV, SB, XS, YS, LFLAT, mxtrs, nb, ns, csa32, sna32, csaw, snaw, XC, YC, XMAX, XMIN, YMAX, YMIN, W, TNUM2, TLIST2, GEPIN, G, GI)` | Etiquetas 100-106: cada nivel por separado. | — |
| `_gep_grupo(XC, YC, ND, TNUM2, TLIST2, LFLAT, mxtrs, i, j, c1, s, ws, l5, xpstk, ypstk)` | Etiquetas 131-135: True si hay que llamar a GPC. | auxiliar de la traducción |
| `gep_grupos(X, Y, ND, NTRS, TH, BELEV, SB, XS, YS, LFLAT, DISTMN, mxtrs, nb, ns, csa32, sna32, csaw, snaw, XC, YC, XMAX, XMIN, YMAX, YMIN, W, HT, TNUM, TLIST, TNUM2, TLIST2, GEPIN, G, GI)` | Etiquetas 110-136: grupos de niveles de edificios distintos que se pueden combinar. | — |

### `nucleo.py`

Building Profile Input Program for PRIME.

| Función | Definición | Equivale a |
|---|---|---|
| `r4(x)` | Asignación a una variable REAL (redondeo a simple). | — |
| `_lista(n, val)` | — | auxiliar de la traducción |
| `_matriz()` | — | auxiliar de la traducción |
| `class _Lector` | READ(10,*) sobre los registros del fichero de entrada. | auxiliar de la traducción |
| `cnrlin(x1, y1, x2, y2, xkp, ykp)` | CNRLIN: distancia de una esquina (XKP, YKP) a un lado y si el pie de la perpendicular cae entre sus extremos. Devuelve (XI, YI, BET, DIST). | BPIPPRM `CNRLIN` (Bpipprm.for) |
| `dislin(x1, y1, x2, y2, l5, xsp, ysp)` | DISLIN: 1 si la chimenea está a sotavento del lado y a 5L o menos. | BPIPPRM `DISLIN` (Bpipprm.for) |
| `class _Estado` | — | auxiliar de la traducción |
| `width(st, ang, i, j, c)` | WIDTH: esquinas giradas (XC, YC), extremos y anchura y longitud proyectadas (TW, BL). | BPIPPRM `WIDTH` (Bpipprm.for) |
| `_anchos(st, ang, nb, NTRS, mxtrs)` | WIDTH de todos los niveles para una dirección. | BPIPPRM `WIDTH` (Bpipprm.for) |
| `gpc(st, d, i, c, s, tw, ws, hta, ch, ig)` | GPC: altura de chimenea GEP (ecuación 1) y estructura que la determina. | BPIPPRM `GPC` (Bpipprm.for) |
| `_gpc_guarda(st, d, i, c, s, tw, hta, hwe)` | — | auxiliar de la traducción |
| `mxbwh(st, d, i, s, c, tw, hta, ws, tl1, ig, bl, xbadj, ybadj)` | MXBWH: valores de downwash (altura, anchura, longitud, XBADJ, YBADJ) de la estructura con mayor efecto de estela para la chimenea y la dirección. | BPIPPRM `MXBWH` (Bpipprm.for) |
| `ejecutar(f_entrada, f_salida, f_resumen, ahora)` | Ejecuta BPIPPRM. Devuelve las líneas de pantalla. | — |
| `_programa(f_entrada, o12, o14, w, wl, scr, pant, ahora)` | — | auxiliar de la traducción |
| `_usar_numba(nb, NTRS, ND, ns)` | — | auxiliar de la traducción |
| `_gep_numba(st, nb, ns, NTRS, TH, XS, YS, LFLAT, DISTMN, W, HT, scr, pant)` | Los dos bucles GEP de 1.440 direcciones con gep_rapido (numba): | auxiliar de la traducción |
| `_gep_grupo(st, d, i, j, c1, s, tw, ws, l5, hta, tl1, xpstk, ypstk, LFLAT)` | Etiquetas 131-136 del original: | auxiliar de la traducción |
