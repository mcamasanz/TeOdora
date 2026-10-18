# `lagaus.meteo.viento3d` — viento3d

Equivale a **CALMET**: reescrito en **sala limpia** desde la documentación publicada de CALMET; la equivalencia es funcional: nunca se ha abierto su código.

<!-- manual -->
## Qué hace
Calcula el **campo de viento 3D** hora a hora sobre una malla: parte del pronóstico, lo ajusta al
terreno (bloqueo, flujos de ladera, efectos cinemáticos), incorpora observaciones si las hay y
calcula la **micrometeorología** de cada celda (clase de estabilidad, u\*, L, w\*, altura de
mezcla, precipitación).

## Entradas y salidas
| | |
|---|---|
| Entrada | fichero de control, GEO.DAT (de `terreno.geofisica`), pronóstico 3D (3D.DAT), nubosidad (CLOUD.DAT) y, opcionalmente, estaciones de superficie (SURF.DAT), sondeos (UPn.DAT), boyas (SEAn.DAT) y pluviómetros (PRECIP.DAT) |
| Salida | CALMET.DAT (formato binario) para `dispersion.puffs`; opcionalmente PACOUT.DAT |

## Uso
```bash
python -m lagaus viento3d CMET.INP
```
```python
from lagaus.meteo.viento3d.principal import ejecutar
from lagaus.meteo.viento3d import fichero_viento
ejecutar(["CMET.INP"], carpeta="caso")
cab, horas = fichero_viento.leer("caso/CALMET.DAT")    # cabecera y campos de cada hora
```

## Ejemplo
Con el pronóstico ERA5 de un día y una malla de 10 × 10 km a 250 m, el motor escribe 24 horas de
viento en 10 capas y la altura de mezcla de cada celda.

## Validación y alcance
Reescrito en **sala limpia**. 51 de 51 casos dentro del criterio (peor dirección media 0,30°,
peor sesgo de velocidad 0,22 %): pronóstico solo, estaciones, sondeos, costa (boyas, COARE con
oleaje, OCD), brisa, pluviómetros, temperatura 3D de sondeos, O'Brien, efectos cinemáticos,
barreras y proyecciones LCC/TTM. Pendiente: IDIOPT, capa caliente/piel fría de COARE e ITWPROG=2
(ver PENDIENTES.md).
<!-- /manual -->

## Ficheros

| Fichero | Contenido | Viene de | Equivale a |
|---|---|---|---|
| `__init__.py` | Modelo de viento diagnóstico y micrometeorología (equivalente propio, en sala limpia, de CALMET). | `__init__.py` | funcional (CALMET) |
| `__main__.py` | — | `__main__.py` | funcional (CALMET) |
| `control.py` | Lector de ficheros de control con la sintaxis publicada de CALMET (la misma de la fase 06). | `control.py` | funcional (CALMET) |
| `entradas.py` | Lectores de las entradas de CALMET que usamos: GEO.DAT 2.0, 3D.DAT 2.1, CLOUD.DAT, SURF.DAT, UPn.DAT, SEAn.DAT y PRECIP.DAT. | `entradas.py` | funcional (CALMET) |
| `fichero_viento.py` | Lectura y escritura del fichero de salida CALMET.DAT (versión de dataset 2.0). | `calmetdat.py` | funcional (CALMET) |
| `lluvia.py` | Pluviómetros (NPSTA > 0): estaciones del grupo 9, PRECIP.DAT e interpolación de la precipitación a la malla. | `lluvia.py` | funcional (CALMET) |
| `malla.py` | Malla de cálculo: centros de celda, caras y centros de las capas, gradiente del terreno. | `malla.py` | funcional (CALMET) |
| `mar.py` | Estaciones sobre el agua (SEAn.DAT, NOWSTA > 0) y capa límite marina sobre las celdas de agua. | `mar.py` | funcional (CALMET) |
| `micromet.py` | Micrometeorología sobre tierra: radiación, flujos, u*, L, alturas de mezcla, w* y clase PGT. | `micromet.py` | funcional (CALMET) |
| `observaciones.py` | Observaciones (NOOBS=1 y 0): estaciones de superficie del grupo 7 y datos del SURF.DAT, sondeos del grupo 8 (UPn.DAT), paso 2 del viento y campos de superficie desde las estaciones (ITPROG=1). | `observ.py` | funcional (CALMET) |
| `principal.py` | Programa principal: fichero de control -> CALMET.DAT 2.0 (o PACOUT.DAT con IFORMO=2). | `principal.py` | funcional (CALMET) |
| `prognostico.py` | Campo inicial desde el pronóstico (3D.DAT, IPROG=14) y perfiles de temperatura (ITPROG=2). | `prognostico.py` | funcional (CALMET) |
| `proyeccion.py` | Proyección de la malla (grupo 2 del fichero de control): UTM, LCC y TTM. | `proyeccion.py` | funcional (CALMET) |
| `sol.py` | Elevación solar en el punto medio de la hora. | `sol.py` | funcional (CALMET) |
| `viento.py` | Módulo de viento diagnóstico (paso 1 sobre el campo inicial del pronóstico y paso 2 sin observaciones). Procedencia de cada regla en FUENTES.md del laboratorio. | `viento.py` | funcional (CALMET) |

## Funciones por fichero

98 funciones; 0 con equivalencia explícita. Las auxiliares de la traducción no tienen rutina propia en el original.

### `control.py`

Lector de ficheros de control con la sintaxis publicada de CALMET (la misma de la fase 06).

| Función | Definición | Equivale a |
|---|---|---|
| `leer(texto)` | Devuelve (título, {VARIABLE: | — |
| `class Control` | Acceso tipado a las variables leídas. | — |

### `entradas.py`

Lectores de las entradas de CALMET que usamos: GEO.DAT 2.0, 3D.DAT 2.1, CLOUD.DAT, SURF.DAT, UPn.DAT, SEAn.DAT y PRECIP.DAT.

| Función | Definición | Equivale a |
|---|---|---|
| `class _Lineas` | — | — |
| `leer_geo(ruta)` | GEO.DAT 2.0 -> dict con nx, ny, xorg, yorg (km), dgrid (km), pmap, zona, hem, datum, nlu, iwat1, iwat2, categorias, y campos (ny, nx) lu, elev (m) y los de PARAMS. | — |
| `_f(s)` | — | — |
| `_i(s)` | — | — |
| `leer_3d(ruta)` | 3D.DAT 2.1 -> dict con la cabecera y, por hora, los campos de superficie y de niveles. | — |
| `leer_surf(ruta)` | SURF.DAT formateado (IFORMS=2) -> {ids, ibtz, horas: | — |
| `leer_up(ruta)` | UP.DAT (un sondeo por estación) -> lista de (datetime, niveles (n, 5): | — |
| `leer_sea(ruta)` | SEAn.DAT (una estación sobre el agua por fichero) -> {id, nombre, registros}. | — |
| `leer_precip(ruta)` | PRECIP.DAT formateado (IFORMP=2) -> {ids, ibtz, horas: | — |
| `leer_nubes(ruta, nx, ny)` | CLOUD.DAT (formato libre) -> {AAAAJJJHH: | — |

### `fichero_viento.py`

Lectura y escritura del fichero de salida CALMET.DAT (versión de dataset 2.0).

| Función | Definición | Equivale a |
|---|---|---|
| `class Cabecera` | — | — |
| `class Hora` | — | — |
| `_c(s, n)` | — | — |
| `_s(b)` | — | — |
| `class _Escritor` | — | — |
| `_malla(a, tipo)` | (ny, nx) -> bytes en el orden Fortran ((a(i,j), i=1,nx), j=1,ny), fila 1 = sur. | — |
| `escribir(ruta, cab, horas)` | Escribe un CALMET.DAT 2.0. | — |
| `_media_capas(col, zface, a, b)` | Media ponderada por espesores de los valores por capa col (nz, ny, nx) entre a y b (ny, nx). | — |
| `escribir_pacout(ruta, cab, horas, jul_ini, xs, ys, xu, yu)` | PACOUT.DAT (IFORMO=2, formato de MESOPUFF II, [UG] sec. | — |
| `_registros(ruta)` | — | — |
| `leer(ruta, horas)` | Lee un CALMET.DAT 2.0 -> (Cabecera, [Hora, ...]). | — |
| `leer_pacout(ruta, nusta)` | Lee un PACOUT.DAT -> (Cabecera mínima, [Hora]) con u, v de dos «capas» (la baja y la alta de MESOPUFF II), w y t nulos y los campos 2D ZI, USTAR, WSTAR, EL, IPGT, RMM y RHO (la med… | — |

### `lluvia.py`

Pluviómetros (NPSTA > 0): estaciones del grupo 9, PRECIP.DAT e interpolación de la precipitación a la malla.

| Función | Definición | Equivale a |
|---|---|---|
| `leer_pluviometros(control, npsta)` | Registros PSn del grupo 9 -> lista de dicts (nombre, id, x, y en m). | — |
| `class Pluviometros` | Distancias pluviómetro-celda y lluvia en la malla de cada hora. | — |

### `malla.py`

Malla de cálculo: centros de celda, caras y centros de las capas, gradiente del terreno.

| Función | Definición | Equivale a |
|---|---|---|
| `class Malla` | — | — |

### `mar.py`

Estaciones sobre el agua (SEAn.DAT, NOWSTA > 0) y capa límite marina sobre las celdas de agua.

| Función | Definición | Equivale a |
|---|---|---|
| `z0_hosker(u)` | [UG] ec. 2-69 con U ≥ 1 m/s [caja negra: dominio de agua con viento de 0,3 a 15 m/s]. | — |
| `ustar_neutro(u)` | — | — |
| `es_goff_gratch(t)` | Presión de vapor de saturación sobre agua (hPa), Goff-Gratch; | — |
| `rsat(t, p)` | — | — |
| `_psi_bd(zl)` | Businger-Dyer (Kansas): (ψm, ψh) con 15 y 9 inestable, 4,7 estable y Prandtl 0,74. | — |
| `ocd(u, ta, dt, rh, zt)` | Método OCD: (u*, L, flujo de flotabilidad cinemático w'θv' (K m/s), z0) [W2]. | — |
| `_psiu(zet)` | — | — |
| `_psit(zet)` | — | — |
| `_qsat_coare(t, p)` | — | — |
| `_z0_olas(jwave, usr, ut, visa, hwave, twave)` | Rugosidad con oleaje de COARE 3.0 (Fairall et al., 2003): | — |
| `coare(u, ta, dt, rh, zt, zu, jwave, hwave, twave, jcool)` | COARE 3.0 con una iteración [W3]. | — |
| `pgt_agua(el)` | Clase PGT sobre el agua por la longitud de Monin-Obukhov [W6]. | — |
| `class EstacionesMar` | Datos de las estaciones sobre el agua de cada hora: | — |
| `mas_cercana(dist, valor, defecto)` | Valor en cada celda de la estación sobre el agua más cercana que lo tiene (dist: | — |
| `olas_por_defecto(u)` | Oleaje por defecto de COARE 3.0 (Tp = 0,729 U, Hs = 0,018 U² (1 + 0,015 U)) con U el viento de la capa 1 (sin la ráfaga de COARE); | — |
| `flujos(icoare, u, ta, dt, rh, zt, olas, icool)` | u*, L, w'θv' y z0 sobre el agua; | — |

### `micromet.py`

Micrometeorología sobre tierra: radiación, flujos, u*, L, alturas de mezcla, w* y clase PGT.

| Función | Definición | Equivale a |
|---|---|---|
| `radiacion_solar(sinphi, nubes)` | — | — |
| `flujo_sensible_diurno(qsw, t, nubes, albedo, bowen, hcg, qf)` | — | — |
| `_psim(zl)` | — | — |
| `ustar_l_diurno(u, z0, qh, t, rho, nit)` | — | — |
| `ustar_l_estable(u, z0, t, nubes)` | — | — |
| `psi1_niveles(zl, tl, h, dzzi, dptmin)` | Gradiente de θ (= T + 0,0098 z) entre h y h + DZZI en los niveles del pronóstico de la hora anterior interpolados a cada celda (zl, tl: | — |
| `_interp_niv(zl, th, zq)` | Interpolación lineal en z por columna (niveles crecientes; | — |
| `turner(ws10, sin_elev, nubes, techo)` | Clase PGT por Turner. techo: altura de nubes en cientos de pies (ICLOUD=0, estaciones); sin ella se comporta como un techo bajo (< 7000 pies) [M7, O15]. | — |
| `_promedio(campos, u, v, dx, dt, mnmdav, hafang)` | Promedio espacial a barlovento ([UG] ec. | — |
| `class AlturaMezcla` | Estado de la altura de mezcla convectiva entre horas (por celda). | — |
| `ustar_agua(u)` | — | — |
| `crece_agua(q, h_ant, psi, p, rho, dt)` | Altura convectiva sobre el agua (Maul-Carson, [UG] ec. | — |
| `crece_bg(h0, q, gam, ust, el, t, rho, thresh, dt, npasos)` | Altura convectiva de Batchvarova y Gryning (1991, 1994): | — |
| `wstar(qh, hconv, t, rho)` | — | — |

### `observaciones.py`

Observaciones (NOOBS=1 y 0): estaciones de superficie del grupo 7 y datos del SURF.DAT, sondeos del grupo 8 (UPn.DAT), paso 2 del viento y campos de superficie desde las estaciones (ITPROG=1).

| Función | Definición | Equivale a |
|---|---|---|
| `leer_estaciones(control, nssta)` | Registros SSn del grupo 7 -> lista de dicts (nombre, id, x, y en m, zona, anemómetro). | — |
| `_uv(ws, wd)` | — | — |
| `class Observaciones` | Distancias estación-celda, estación más cercana y análisis de cada hora. | — |
| `class Barreras` | Barreras a la interpolación del viento (NBAR > 0): | — |
| `class Brisa` | Regiones de brisa (LLBREZE): | — |
| `pesos_t(dist, validas, dx, p)` | Pesos de la interpolación de temperatura y humedad: | — |
| `leer_estaciones_altura(control, nusta)` | Registros USn del grupo 8 -> lista de dicts (nombre, id, x, y en m). | — |
| `_media_capa(z, f, a, b)` | Media de la función lineal a trozos f(z) (constante fuera de los extremos) en [a, b]. | — |
| `class Sondeos` | Sondeos (UPn.DAT) de las estaciones del grupo 8: | — |
| `class GradienteSondeo` | Gradiente térmico del dominio (N del bloqueo) con ITPROG=0 [T9]: | — |
| `giro_200(el)` | D(h) por interpolación lineal en 1/L de la tabla 2-1 [UG]; | — |
| `giro(z, dh)` | [UG] ec. 2-21: D(z) = D(h)·d1·(1 − exp(−d2 z/h)). | — |
| `psi_m(z, el)` | Funciones de estabilidad del perfil de extrapolación: | — |
| `perfil_semejanza(ws, z1, z, z0, el)` | [UG] ec. 2-22: U(z) = U(z1)·[ln(z/z0) − ψ(z/L)] / [ln(z1/z0) − ψ(z1/L)]. | — |

### `principal.py`

Programa principal: fichero de control -> CALMET.DAT 2.0 (o PACOUT.DAT con IFORMO=2).

| Función | Definición | Equivale a |
|---|---|---|
| `class NoImplementado` | — | — |
| `class ErrorOriginal` | Configuración con la que el original se detiene: | — |
| `_reales(c, nombre)` | — | — |
| `_extrapolacion_semejanza(obs, dat, malla, p, z0, t1, t1p, nub, qh_dia, rho, hraw, psi, agua, hem)` | IEXTRP=±4: L y altura de mezcla de cada estación con su viento observado y los campos de su celda (balance de energía de día, Venkatram de noche, como en la malla) y función (k, ws… | — |
| `_adiabatica(tk, ts, h, adiab, malla, caras)` | Temperatura adiabática bajo la altura de mezcla convectiva h. | — |
| `_media_dos_tramos(t0, g1, g2, h, za, zb)` | Media en [za, zb] del perfil T(z) = t0 + g1·z bajo h y T(h) + g2·(z − h) encima. | — |
| `_vientos_mar(dm, dmar, po, malla, p, icoare, hem, alto, h_agua, agua, olas_boya, icool)` | Vientos por capa de las estaciones sobre el agua para el paso 2: | — |
| `ejecutar(argv, carpeta)` | — | — |

### `prognostico.py`

Campo inicial desde el pronóstico (3D.DAT, IPROG=14) y perfiles de temperatura (ITPROG=2).

| Función | Definición | Equivale a |
|---|---|---|
| `class Pronostico` | Datos del 3D.DAT y pesos de interpolación a la malla. | — |
| `_viento(zc, z, w)` | — | — |
| `perfil_t(zc, z, t, p, dia, estado, oceano, sst)` | Temperatura en los centros de capa de una columna del pronóstico. | — |

### `proyeccion.py`

Proyección de la malla (grupo 2 del fichero de control): UTM, LCC y TTM.

| Función | Definición | Equivale a |
|---|---|---|
| `grados(s, defecto)` | '41.5N', '3.2W', '90W', '-3.2' -> grados con signo (N y E positivos). | — |
| `class Proyeccion` | Parámetros de la proyección leídos del fichero de control y cadena PROJ (en metros). | — |

### `sol.py`

Elevación solar en el punto medio de la hora.

| Función | Definición | Equivale a |
|---|---|---|
| `seno_elevacion(anio, dia_juliano, hora_utc, lat, lon)` | sin(elevación) para la hora UTC decimal dada (lat, lon en grados, este positivo). | — |

### `viento.py`

Módulo de viento diagnóstico (paso 1 sobre el campo inicial del pronóstico y paso 2 sin observaciones). Procedencia de cada regla en FUENTES.md del laboratorio.

| Función | Definición | Equivale a |
|---|---|---|
| `_suaviza_capa(f, n, normal_x, fijas)` | n pasadas de (2-26) en el sitio desde la esquina suroeste. | — |
| `suavizar(u, v, nsmth, fijas1)` | fijas1: celdas de la capa 1 que no se suavizan (regiones de brisa). | — |
| `h_max_radio(elev, dx, radio)` | Cota máxima de las celdas cuyo centro está a distancia <= radio (círculo inclusivo). | — |
| `brunt_vaisala(t, zc, zupt)` | N del dominio con la temperatura media de la capa 1 y la interpolada a ZUPT [caja negra]. | — |
| `froude(u, v, elev, gx, gy, zc, hmax, n_bv, critfn)` | — | — |
| `_crestas(elev, dx, radio)` | Para cada celda: cota máxima y mínima dentro del radio (círculo inclusivo) y distancia a la celda más próxima que tiene la máxima. | — |
| `ladera(u, v, malla, gx, gy, qh, t, terrad, crestas)` | Suma el flujo de ladera ([UG] 2-13 de noche, 2-16 de día) a las capas que alcanza su espesor h = 0,05 ΔZ, en la proporción de cada capa que ocupa. | — |
| `vertical(u, v, malla, u_prev, v_prev)` | W (sistema que sigue al terreno) en la cara superior de cada capa por continuidad ([UG] 2-27, divergencia centrada como en 2-30). | — |
| `obrien(w, zface)` | [UG] ec. 2-28 (O'Brien, 1970): W₂(z) = W₁(z) − (z/z_top)·W₁(z_top), con W en las caras superiores de las capas (nula en la cima) [caja negra: exacto] [V13]. | — |
| `_divergencia(u, v, dw, dx)` | D = dW/dz + (u(i+1) − u(i−1))/2Δx + (v(j+1) − v(j−1))/2Δy ([UG] ec. | — |
| `_minimiza_capa(u, v, dw, dx, divlim, niter)` | Una capa: en cada paso se calcula D en todos los puntos y cada uno corrige a la vez sus vecinas u(i±1) ∓ D·Δx/2 y v(j±1) ∓ D·Δy/2 ([UG] ec. 2-31 a 2-36; Goodin et al., 1980), sin c… | — |
| `minimizar(u, v, w, malla, divlim, niter)` | Minimización de la divergencia 3D con W fija (en las caras superiores) [V14]. | — |
| `cinematico(u, v, malla, gx, gy, n_bv, alpha, divlim, niter)` | Efectos cinemáticos del terreno (IKINE=1, [UG] ec. | — |
