# `odora.dispersion.puffs` — puffs

Equivale a **CALPUFF**: reescrito en **sala limpia** desde la documentación publicada de CALPUFF; la equivalencia es funcional: nunca se ha abierto su código.

<!-- manual -->
## Qué hace
**Modelo lagrangiano de puffs**: emite bocanadas gaussianas que viajan con el viento variable del
campo 3D, con memoria entre horas. Trata las calmas y las recirculaciones, que el penacho
estacionario no puede representar. Incluye fuentes de área, chimeneas con sobreelevación y el
efecto de los edificios.

## Entradas y salidas
| | |
|---|---|
| Entrada | fichero de control y CALMET.DAT (de `meteo.viento3d`) |
| Salida | CONC.DAT (concentraciones por receptor y hora) y listado |

## Uso
```bash
python -m odora puffs CALPUFF.INP
```
```python
from odora.dispersion.puffs.principal import ejecutar
from odora.dispersion.puffs import fichero_conc
cab, periodos = ejecutar("caso/CALPUFF.INP")                 # o leer el CONC.DAT escrito:
cab, periodos = fichero_conc.leer("caso/CONC.DAT")
```

## Ejemplo
Con el CALMET.DAT de Lleida (25 h) y las 17 pilas de área, el CONC.DAT coincide con el del
original (FAC2 1,000, FB 0,0001) y el motor tarda unas 6 veces menos.

## Validación y alcance
Reescrito en **sala limpia**. 65 de 65 casos dentro del criterio (FAC2 ≥ 0,993):
- áreas, volúmenes e IVARY 1-5;
- chimeneas: Briggs, transición, efecto punta, penetración parcial, calmas y cizalla;
- efecto edificio ISC y PRIME;
- deposición seca de gases y partículas, húmeda y mixta;
- malla de receptores anidada;
- emisiones variables PTEMARB y VOLEMARB;
- dispersión MDISP 2, 3 y 4.

Pendiente: MDISP 1 y 5, slugs, división de puffs, química, terreno subrejilla, fuentes de área y
de línea con emisión variable, líneas flotantes y MSHEAR=1 (ver PENDIENTES.md).
<!-- /manual -->

## Ficheros

| Fichero | Contenido | Viene de | Equivale a |
|---|---|---|---|
| `__init__.py` | Modelo de dispersión por puffs gaussianos (equivalente propio, en sala limpia, de CALPUFF). | `__init__.py` | funcional (CALPUFF) |
| `control.py` | Lector de ficheros de control con la sintaxis publicada de CALMET (la misma de la fase 06). | `control.py` | funcional (CALPUFF) |
| `deposicion.py` | Deposición seca y húmeda: velocidades de deposición por celda y coeficientes de lavado. | `deposicion.py` | funcional (CALPUFF) |
| `edificios.py` | Efecto edificio sobre las chimeneas (building downwash), método ISC (MBDW = 1). | `edificios.py` | funcional (CALPUFF) |
| `emisiones.py` | Ficheros de emisión con parámetros variables: PTEMARB.DAT (fuentes puntuales) y VOLEMARB.DAT (fuentes de volumen). | `emisiones.py` | funcional (CALPUFF) |
| `entrada.py` | Lectura del fichero de control CALPUFF.INP (sintaxis publicada) a una configuración. | `entrada.py` | funcional (CALPUFF) |
| `estela_edificio.py` | Efecto edificio PRIME (MBDW = 2): sobreelevación numérica con la estela, tablas de σ de la estela y de la cavidad, fracción capturada por la cavidad y concentración en la zona de la cavidad. | `prime.py` | funcional (CALPUFF) |
| `fichero_conc.py` | Lectura y escritura del fichero de concentraciones CONC.DAT (versión de dataset 2.1). | `concdat.py` | funcional (CALPUFF) |
| `fichero_viento.py` | Lectura y escritura del fichero de salida CALMET.DAT (versión de dataset 2.0). | `calmetdat.py` | funcional (CALPUFF) |
| `muestreo.py` | Función de muestreo integrada de un puff a lo largo de su tramo y término vertical. | `muestreo.py` | funcional (CALPUFF) |
| `nucleo.py` | Núcleo del modelo de puffs: avance de una hora (numba). | `nucleo.py` | funcional (CALPUFF) |
| `principal.py` | Programa principal: CALPUFF.INP + CALMET.DAT -> CONC.DAT (concentraciones horarias). | `principal.py` | funcional (CALPUFF) |
| `sigmas.py` | Coeficientes de dispersión σy, σz y sus inversas (distancia o tiempo virtual). | `sigmas.py` | funcional (CALPUFF) |
| `sobreelevacion.py` | Sobreelevación de fuentes puntuales: Briggs (flotación y cantidad de movimiento), transición, efecto punta de chimenea y penetración parcial en la inversión. | `sobreelevacion.py` | funcional (CALPUFF) |

## Funciones por fichero

157 funciones; 0 con equivalencia explícita. Las auxiliares de la traducción no tienen rutina propia en el original.

### `control.py`

Lector de ficheros de control con la sintaxis publicada de CALMET (la misma de la fase 06).

| Función | Definición | Equivale a |
|---|---|---|
| `leer(texto)` | Devuelve (título, {VARIABLE: | — |
| `class Control` | Acceso tipado a las variables leídas. | — |

### `deposicion.py`

Deposición seca y húmeda: velocidades de deposición por celda y coeficientes de lavado.

| Función | Definición | Equivale a |
|---|---|---|
| `ra_malla(ustar, el, z0)` | Resistencia aerodinámica (s/m) por celda ([UG] ec. | — |
| `z0_efectiva(z0, agua, ws10)` | z0 sobre el agua en función del viento a 10 m (Hosker, [UG] ec. | — |
| `vd_gas(esp_gas, g9, ustar, el, z0, xlai, qsw, tempk, ilandu, agua, ws10)` | Velocidad de deposición (m/s) de un gas por celda. | — |
| `intervalos(dmm, sg, nint)` | Intervalos de tamaño de una partícula: | — |
| `vd_particula(esp_part, nint, ustar, el, z0, agua, ws10)` | Velocidad de deposición (m/s) de una partícula por celda ([UG] ecs. | — |
| `vg_media(esp_part, nint)` | Velocidad de sedimentación media másica (m/s). | — |
| `lavado(lam, rmm, ipcode)` | Tasa de lavado Λ (1/s) por celda: | — |
| `leer_vd(texto)` | VD.DAT ([UG] sec. 4.7): {especie: 24 velocidades (m/s) de las horas 1 a 24}. | — |

### `edificios.py`

Efecto edificio sobre las chimeneas (building downwash), método ISC (MBDW = 1).

| Función | Definición | Equivale a |
|---|---|---|
| `sector(u, v)` | Sector 1..36 del vector de flujo (dirección hacia la que sopla el viento) para buscar las dimensiones del edificio: | — |
| `class Estela` | Efecto edificio ISC de una fuente para la hora (vector de flujo de la capa de la chimenea). | — |
| `_dh_chorro_2hb(hs, d, w, ts, tempk, us, clase, hb, zmid, tcol)` | Elevación del chorro a x = 2·hb ([ISC3] 1.1.4.10.1, ecs. | — |
| `isc(hs, d, w, ts, tempk, us, clase, hb, hw, tbd, zmid, tcol, urbano, symin, szmin)` | Efecto edificio ISC para la hora: | — |
| `dwsigs(x, esc, a, syc, k, urb)` | σy, σz del efecto edificio a la distancia x del origen ([ISC3] ecs. | — |
| `cubica(b, c, rhs)` | Raíz no negativa de Z³ + b·Z² + c·Z = rhs (b, c ≥ 0), por Newton. | — |
| `dh_ss(x, fb, fm, us, bj, sqs, xfb, xfm, r0, ly)` | Elevación de Schulman-Scire a la distancia x ([ISC3] ecs. | — |

### `emisiones.py`

Ficheros de emisión con parámetros variables: PTEMARB.DAT (fuentes puntuales) y VOLEMARB.DAT (fuentes de volumen).

| Función | Definición | Equivale a |
|---|---|---|
| `_tokens(texto)` | Elementos de una lectura dirigida por lista (cadenas entre comillas o valores). | — |
| `_fecha_v5(ymd, hh)` | YYYYJJJ (o YYJJJ) y hora de final de periodo -> datetime del final del periodo. | — |
| `_fecha_v21(y, j, h, s)` | Año, día juliano, hora y segundo (versión 2.1) -> datetime. | — |
| `class Arb` | Fichero de emisión variable leído: | — |
| `leer_ptemarb(texto, mbdw)` | PTEMARB.DAT (versión 5 o 2.1). | — |
| `_cabecera21(lin, a)` | Cabecera de la versión 2.1: | — |
| `_leer_ptemarb21(lin, a)` | — | — |
| `leer_volemarb(texto)` | VOLEMARB.DAT (versión 2.1 de la guía V6). | — |

### `entrada.py`

Lectura del fichero de control CALPUFF.INP (sintaxis publicada) a una configuración.

| Función | Definición | Equivale a |
|---|---|---|
| `class NoImplementado` | — | — |
| `_valores(v)` | — | — |
| `_real(x)` | — | — |
| `_36(val)` | 36 valores por dirección del subgrupo 13c (los que falten, 0; | — |
| `class Especie` | — | — |
| `class Fuente` | — | — |
| `class Config` | — | — |
| `_variacion(sub, nombres)` | IVARY y factores por especie de un subgrupo 13d/14d/16c. | — |
| `leer(texto)` | — | — |

### `estela_edificio.py`

Efecto edificio PRIME (MBDW = 2): sobreelevación numérica con la estela, tablas de σ de la estela y de la cavidad, fracción capturada por la cavidad y concentración en la zona de la cavidad.

| Función | Definición | Equivale a |
|---|---|---|
| `class Estado` | Variables de los módulos de PRIME para una fuente y hora. | — |
| `sigzpr(s, x, z)` | σz ambiental a la distancia x de la chimenea (curvas de dispersión de CALPUFF). | — |
| `sigypr(s, x, z)` | σy ambiental a la distancia x de la chimenea. | — |
| `_xv(s, sig, eje)` | Distancia (m) a la que la curva ambiental da `sig` (0 si sig ≤ 0). | — |
| `_sucesion(ntot, ntr, agrupada)` | Índices reales rn del submuestreo de paso creciente (más puntos cerca de la fuente), con la acumulación en reales de 4 bytes del original (caja negra: | — |
| `_proximos(ntot, ntr)` | Índices reales del submuestreo por valores más próximos: | — |
| `_rpot0(base, expo)` | — | — |
| `wake_scales(s)` | WAKE_SCALES: escala R y dimensiones de la cavidad (HR, LR, LC). | — |
| `wake_dim(x, h, w, r)` | WAKE_DIM: altura y semianchura de la estela a x de la cara de barlovento. | — |
| `cavity_ht(h, w, l, r, lc, lr, hr, x)` | CAVITY_HT: altura y semianchura de la cavidad a x de la cara de barlovento. | — |
| `position(s, x, y, z)` | POSITION: 1 dentro del edificio, 2 en la cavidad, 3 en la estela lejana, 4 fuera. | — |
| `zstream(h, w, l, r, lr, hr, x, y, z)` | ZSTREAM: pendiente media local de las líneas de corriente junto al edificio. | — |
| `wake_u(s, x, y, z)` | WAKE_U: cociente u(estela)/u(ambiente) y su gradiente vertical. | — |
| `wake_turb(s, xinp, l, rinp)` | WAKE_TURB: intensidades de turbulencia en la estela a xinp de la cara de barlovento. | — |
| `wake_xa(s, l, rinp)` | WAKE_XA: distancias desde la cara de barlovento a las que la turbulencia de la estela iguala la ambiental (limitadas a XBYRMAX escalas R). | — |
| `wake_sig(x, xd, xold, turbz, turby, szold, syold, h, w, r, zk, yk)` | WAKE_SIG: σ y dσz/dx en la estela al final de un paso pequeño (zk, yk de entrada/salida). | — |
| `wake_cav0(s, sycapt)` | WAKE_CAV0: σ iniciales de la fuente situada en el suelo de la cavidad. | — |
| `numgrad(x, xtr, ztr, ntr)` | NUMGRAD: interpolación en la tabla de la trayectoria. | — |
| `wake_drdx(s, x)` | WAKE_DRDX: ritmo de crecimiento del radio del penacho en la estela. | — |
| `class Perfil` | Perfil de la celda de la fuente para la sobreelevación numérica (caja negra, NUMMET): | — |
| `zmet(s, z)` | ZMET: viento, densidad, temperatura y gradientes a la altura z. Devuelve (ua, ra, ta, dudz, dpdz). | — |
| `class _Penacho` | — | — |
| `_rate(p, ua, dudz, ra, dpdz, ta, drdxa, rhs)` | RATE: segundos miembros de las ecuaciones del penacho. | — |
| `_lump(p, ua, ta, f)` | — | — |
| `_unlump(p, ua, ta, ra, f)` | — | — |
| `_entrada(s, p, h, sz0, sy0)` | Entrada del eje del penacho en la estela: | — |
| `numrise(s, h, reff, texit, wexit, sz0, sy0)` | NUMRISE: sobreelevación numérica con la reducción del viento y la inclinación de las líneas de corriente del edificio; al entrar el eje en la estela tabula las σ (WAKE_DFSN). Devue… | — |
| `wake_dfsn(s, xi, szi, syi, z)` | WAKE_DFSN: tablas de σ del penacho en la estela y de la fuente de la cavidad. Como el original de dominio público salvo el crecimiento ambiental, que en CALPUFF sigue la curva desd… | — |
| `_tablas(s, lwak, lcav, np_, nws, ncs, xi, szi, syi, xbc, szcav0, sycav0, dx, dist, asigz, asigy, dsz, csigz, csigy)` | Tablas de la estela (con la chimenea en x = 0 y filas a barlovento de la entrada en x = rn·dx, caja negra) y de la cavidad, submuestreadas a MXNTR puntos como el original. | — |
| `_tabla_estela(s, np_, nws, xi, szi, syi, dx, dist, asigz, asigy, dsz, barlovento)` | Tabla de la estela submuestreada a MXNTR puntos. | — |
| `_addbid(s, xtr, htr, ntr)` | WAKE_ADDBID: σ de las filas a barlovento de la entrada con la flotación de la elevación de la trayectoria (sin el descenso de las líneas de corriente). | — |
| `wake_fqc(s, xbi, xtr, ztr, ntr)` | WAKE_FQC: fracción máxima de la masa capturada por la cavidad. | — |
| `fqcav_ef(s)` | Fracción en la cavidad que se usa de verdad: | — |
| `fnerf(xx)` | — | — |
| `fnerfc(xx)` | — | — |
| `erfdif(x1, x2)` | — | — |
| `frgauss(hcntr, sigma, h1, h2)` | FRGAUSS: fracción de una gaussiana entre h1 y h2. | — |
| `_interp(xt, yt, n, x)` | — | — |
| `wake_xsig(s, x, hstk, rise, nobid)` | WAKE_XSIG: σ del penacho principal y de la fuente de la cavidad a la distancia x de la chimenea: interpolación en las tablas; fuera de ellas, curva ambiental (con flotación) antes … | — |
| `cav_src(s, xr, yr, zr)` | CAV_SRC: fuentes de la cavidad para un receptor (xr, yr, zr relativos a la chimenea, eje x con el flujo). Devuelve (n1, n2, qc, yrc, zrc, szc, syc) con índices 1..3 (1 = principal)… | — |
| `fila_tabla(s, tr)` | Tabla compacta (vector de NTCOL) con lo que necesitan los puffs de una fuente y hora. | — |
| `zona_exclusion(s, xr, yr)` | ¿Está el receptor (relativo a la chimenea, eje x con el flujo de la hora) antes del final de la zona de la cavidad, xb < LB + 1,15·LR? Ahí los puffs de la fuente no cuentan mientra… | — |
| `region_cavidad(s, xr, yr)` | ¿Recibe el receptor la concentración de la zona de la cavidad (CAV_CONC)? Desde la chimenea o desde la cara de barlovento (la que esté antes) hasta el final de la zona (caja negra)… | — |
| `_vertical_cav(h, z, sz, tapa, zsup)` | Término vertical (×√(2π)·σz) de CAV_CONC (caja negra): | — |
| `cav_conc(s, tr, xr, yr, zr, us, ub, tapa, zsup)` | CAV_CONC: concentración por unidad de emisión (s/m³) en un receptor de la zona de la cavidad: penacho principal (masa 1 − FQCAV, viento de la chimenea, altura de la trayectoria, σ … | — |

### `fichero_conc.py`

Lectura y escritura del fichero de concentraciones CONC.DAT (versión de dataset 2.1).

| Función | Definición | Equivale a |
|---|---|---|
| `_c(s, n)` | — | — |
| `_s(b)` | — | — |
| `_registros(b)` | — | — |
| `class Cabecera` | — | — |
| `class Periodo` | — | — |
| `_comprimir(a)` | — | — |
| `_descomprimir(c, n)` | — | — |
| `leer(ruta)` | Lee un CONC.DAT 2.1 -> (Cabecera, [Periodo, ...]). | — |
| `escribir(ruta, cab, periodos)` | Escribe un CONC.DAT 2.1 con la estructura de [V6] tabla 9-52. | — |

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
| `_registros(ruta)` | — | — |
| `leer(ruta, horas)` | Lee un CALMET.DAT 2.0 -> (Cabecera, [Hora, ...]). | — |

### `muestreo.py`

Función de muestreo integrada de un puff a lo largo de su tramo y término vertical.

| Función | Definición | Equivale a |
|---|---|---|
| `integral_tramo(a, b, c)` | ∫_0^1 exp(−(a·p² + 2·b·p + c)/2) dp (ecs. | — |
| `integral_tramo_p(a, b, c, i1)` | ∫_0^1 p·exp(−(a·p² + 2·b·p + c)/2) dp ([UG] ec. | — |
| `g_vertical(he, zr, sz, lid)` | Término vertical g (1/m) para un puff a altura he, receptor a altura zr, con reflexión en el suelo y, si lid < 1e4, en la tapa (ec. | — |
| `fr_area(yr, syr, sys, lc2)` | Factor de corrección de los puffs de fuentes de área (ec. | — |

### `nucleo.py`

Núcleo del modelo de puffs: avance de una hora (numba).

| Función | Definición | Equivale a |
|---|---|---|
| `ncol(nesp)` | Columnas del estado de un puff con nesp especies. | — |
| `_sy(x, k, urb, fav)` | σy de las curvas de dispersión con el factor de tiempo de promedio (AVET/PGTIME)^0,2. | — |
| `_xvy(sig, k, urb, fav)` | Distancia virtual de σy con el factor de tiempo de promedio. | — |
| `_nesp(P)` | — | — |
| `_mover_qu(P, i, fr)` | Pasa la fracción fr de la masa por encima de la tapa (QU) a la de debajo (QM). | — |
| `_repartir(P, i, fr)` | Reparte la masa total de cada especie: | — |
| `viento_capa(U, V, zface, ix, iy, zb, zt)` | Media por espesor de las componentes de capa en [zb, zt]. | — |
| `divergencia(W, zface, ix, iy, zb, zt)` | Media de dw/dz (1/s) en [zb, zt] con la divergencia de cada capa constante: | — |
| `celda(x, y, nx, ny)` | — | — |
| `_sig_rec_dist(sb, xb, s_ef, k, urb, eje, hef, ws)` | — | — |
| `en_ascenso(P, i)` | ¿Está el puff en la fase de elevación de transición (aún no ha recorrido XFINAL)? | — |
| `_interp_tab(TB, k, c0, cy, n, x)` | Interpolación lineal en la columna cy de la tabla k frente a la c0 (n puntos). | — |
| `_sig_mas_alla(s_fin, x_fin, x, kd, urb, eje)` | σ más allá del final de una tabla: | — |
| `sig_prime(P, i, TB, x, kd, urb)` | σy, σz de un puff PRIME a la distancia x de su origen (chimenea o fuente de la cavidad): | — |
| `en_tabla(P, i, TB)` | ¿Sigue el puff PRIME dentro de su tabla de σ (al principio del paso)? | — |
| `altura(P, i, x, TB)` | Altura del puff (m) cuando ha recorrido x m: | — |
| `techo_capa(P, i, k0, zi0)` | Techo de la capa de advección: | — |
| `viento_ascenso(P, i, U, V, zface, ix, iy, sz, techo, tsamp, ncount, TB)` | Viento de transporte de un paso con elevación de transición (caja negra): | — |
| `paso(P, i, tsamp, U, V, W, zface, IPGT, ZI, EL, ILU, svmin, swmin, ppc, par, xr, yr, zr, zp, conc, peso, lmax, ids, traza, ntr, nsam, ipaso, rdbg, cdbg, TB, EXC, DEP, M2, dflx, wflx)` | Avanza el puff i un paso de muestreo de tsamp s y muestrea los receptores. | — |
| `ws_puff(P, i, U, V, zface, ZI, IPGT, par)` | Velocidad de advección del puff en su posición actual (sin modificar su estado). | — |
| `nsam_viejo(P, i, U, V, zface, ZI, IPGT, par)` | Pasos de muestreo de un puff viejo para la hora (con el viento al principio). | — |
| `hora(P, npuf, nuevos, nnew, U, V, W, zface, IPGT, ZI, EL, ILU, svmin, swmin, ppc, par, xr, yr, zr, zp, conc, ids, traza, ntr, rdbg, cdbg, TB, EXC, DEP, M2, dflx, wflx)` | Avanza todos los puffs una hora. | — |
| `_recorrer(P, i, ns, k0, tope, U, V, W, zface, IPGT, ZI, EL, ILU, svmin, swmin, ppc, par, xr, yr, zr, zp, conc, ids, traza, ntr, rdbg, cdbg, TB, EXC, DEP, M2, dflx, wflx)` | Pasos k0..ns−1 de duración 3600/ns con subpasos (caja negra). | — |

### `principal.py`

Programa principal: CALPUFF.INP + CALMET.DAT -> CONC.DAT (concentraciones horarias).

| Función | Definición | Equivale a |
|---|---|---|
| `_fuentes_arb(cfg, carpeta, mbdw)` | Fuentes de los ficheros de emisiones variables: | — |
| `_actualizar_arb(f, tfin, nombres_emit, x0km, y0km)` | Parámetros de la hora de una fuente de fichero de emisiones variables. | — |
| `_comprobar(cfg)` | — | — |
| `_factor_emision(f, nombre, hora, mes, ws, clase, tk, wscat)` | Factor de variación de la emisión (subgrupos 13d, 14d y 16c; | — |
| `_f32(x)` | — | — |
| `_area_poligono(vx, vy)` | — | — |
| `_fila_estela(fila, est, symin, szmin)` | Efecto edificio ISC en el puff nuevo: | — |
| `_prime(f, u32, v32, us, U, V, T3, ix, iy, zface, clase, ilu, par, plx0)` | Efecto edificio PRIME de una fuente para la hora: | — |
| `_elevacion_prime(f, pri, us, tempk, clase, zi, zmid, tcol)` | Elevación de un puff PRIME: | — |
| `_fuente_cavidad(f, st, ux, uy)` | Posición (m) de la fuente de la cavidad: | — |
| `_fila_prime(fila, pri, kt, symin, szmin, tipo)` | Puff PRIME (1 penacho principal, 2 fuente de la cavidad): | — |
| `_malla_muestreo(cfg, cab, dg, nx, ny)` | Receptores de la malla de muestreo: | — |
| `_fila_masas(fila, masas, qfrac)` | Masa de cada especie del puff nuevo: | — |
| `_fila_elevacion(fila, e)` | Copia la sobreelevación de la fuente en el estado del puff nuevo. | — |
| `ejecutar(ruta_inp, carpeta, salida, verbose, traza_ids, receptor_dbg, al_periodo)` | Corre el modelo con el fichero de control `ruta_inp`. | — |

### `sigmas.py`

Coeficientes de dispersión σy, σz y sus inversas (distancia o tiempo virtual).

| Función | Definición | Equivale a |
|---|---|---|
| `sy_pg(x, k)` | σy rural (m) a la distancia x (m), clase k = 1..6. | — |
| `sz_pg(x, k)` | σz rural (m) a la distancia x (m). | — |
| `sy_mp(x, k)` | — | — |
| `sz_mp(x, k)` | — | — |
| `sigma_dist(x, k, urbano, eje)` | σ (m) a la distancia x (m): | — |
| `x_virtual(sig, k, urbano, eje)` | Distancia virtual (m) a la que la curva da `sig` (bisección en ln x; | — |
| `f_draxler(t, eje, estable)` | — | — |
| `sigma_tiempo(t, sv, eje, estable)` | — | — |
| `t_virtual(sig, sv, eje, estable)` | Tiempo virtual (s) al que σ(t) = sig. | — |
| `sigvw(z, h, us, ws, el)` | σv, σw (m/s) a la altura z con la capa de mezcla h, u*, w* y L. | — |

### `sobreelevacion.py`

Sobreelevación de fuentes puntuales: Briggs (flotación y cantidad de movimiento), transición, efecto punta de chimenea y penetración parcial en la inversión.

| Función | Definición | Equivale a |
|---|---|---|
| `t_altura(z, zmid, tcol)` | Temperatura (K) a la altura z: | — |
| `dthdz(z0, dz, zmid, tcol)` | Gradiente de θ (K/m) entre z0 y z0 + dz, con el mínimo DTHDZ_MIN. | — |
| `class Elevacion` | — | — |
| `_estable(e, hs, d, w, zmid, tcol, calma)` | Elevaciones finales en estable (clases E-F, o chimenea por encima de ZI). | — |
| `_neutra(e, d, w)` | Elevaciones finales en neutra/inestable (clases A-D). | — |
| `elevacion(hs, d, w, ts, tempk, us, clase, zi, zmid, tcol, mtip, mpartl, ss, fmfac)` | Sobreelevación de una fuente puntual para la hora: | — |
| `penetracion(e, estable, encima, zi, zmid, tcol, tempk, mpartl)` | Código del puff y reparto de la masa por la penetración en la inversión ([UG] sec. | — |
| `dh_trans(x, fb, fm, us, bj, sqs, xfb, xfm, dhbf, dhmf, dm, dhf)` | Elevación de transición (m) a la distancia x: | — |
