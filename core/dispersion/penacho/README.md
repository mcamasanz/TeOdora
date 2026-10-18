# `odora.dispersion.penacho` — penacho

Equivale a **AERMOD**: traducido del código de AERMOD (dominio público); cada función indica la rutina original.

<!-- manual -->
## Qué hace
**Modelo gaussiano estacionario de penacho**: capa convectiva con función de densidad
bi-gaussiana, capa estable gaussiana, meandro, sobreelevación, terreno complejo (altura crítica),
estela de edificios, capa límite urbana, química del NO2 y deposición. Calcula concentraciones y
depósitos hora a hora y sus estadísticos.

## Entradas y salidas
| | |
|---|---|
| Entrada | fichero de control (vías CO, SO, RE, ME, OU), `.sfc` y `.pfl` (de `meteo.capa_limite`), receptores con cota (de `terreno.relieve`), dimensiones de edificio (de `terreno.edificios`) y, opcionales, emisiones horarias, fondo y ozono |
| Salida | listado, resumen, ficheros de máximos, POSTFILE, PLOTFILE, MAXIFILE, RANKFILE, SEASONHR, contribuciones a los máximos diarios (MAXDCONT)… |

Fuentes: puntuales (también con caperuza u horizontales), volumen, área (rectangular, polígono,
círculo), línea, carretera con barreras y trinchera, línea flotante, foso abierto y chimenea con
sidewash.

## Uso
```bash
python -m odora penacho caso.inp caso.out
```
```python
from odora.dispersion.penacho.principal import ejecutar
ejecutar(["caso.inp", "caso.out"])     # en la carpeta del caso
```
Variable `AERMOD_NUMBA=0`: fuerza la vía Python pura (más lenta, mismos resultados bit a bit).

## Ejemplo
Las 17 pilas de compostaje de digicompost (fuentes de área poligonales), 1545 receptores y 672 h
de ERA5 producen el PLOTFILE del P98 de 1 h idéntico al del original.

## Núcleo compilado
`nucleo.py` **genera** `_nucleo_gen.py` (numba) a partir de las funciones Python de referencia de
`calculo_area`, `funciones_dispersion`, `sigmas`, `integracion_area`, `calculo_punto_volumen`…
La primera corrida compila (~3 min); las siguientes usan la caché.

## Validación y alcance
142 casos frente al original:
- 124 idénticos en todos sus ficheros;
- 15 que solo difieren en los últimos bits: empates ordenados distinto, la última cifra o memoria
  sin inicializar que imprime el original;
- 2 que solo difieren en el volcado de depuración de PRIME (DEBUGOPT PRIME, a medias); sus
  concentraciones coinciden;
- 1 fuera de alcance (SCIM).

Dentro y validado: corridas de varios años y re-arranque (MULTYEAR, SAVEFILE, INITFILE),
MAXDAILY y DAYRANGE, FASTAREA y FASTALL, y los volcados de DEBUGOPT salvo AREA, RLINE y PRIME.
Fuera (ver PENDIENTES.md): EVENT, EVALFILE, SCIM, TTRM2, opciones ALPHA de viento flojo,
aeronaves, plataformas y HBP.
<!-- /manual -->

## Ficheros

| Fichero | Contenido | Viene de | Equivale a |
|---|---|---|---|
| `__init__.py` | paquete | `__init__.py` | — |
| `bucle_horario.py` | bucle horario (aermod.f, HRLOOP). | `horas.py` | `aermod.f` |
| `calculo_area.py` | cálculo horario por fuente y receptor (calc1.f: CALC, ACALC, ARDIST, SETSRC, FLUXES, HEFF, PRMHEFF, PDIS, VDIS, ADISY, ADISZ, CENTROID, REFL_HT, PENFCT, CPLUME, PRM_PLUME, ACPLUME, AER_PCHI, AER_ACHI) y la deposición (VD… | `calc1.py` | `calc1.f` |
| `calculo_punto_volumen.py` | fuentes puntuales (calc1.f: PCALC, AERCALC, PRMCALC, GAMCALC, PRM_PCHI, y el agotamiento del penacho de PRIME: PRM_PDEP, PRM_PDEPG, PRM_F2INT) y de volumen (VCALC, VOLCALC). | `calc1_pv.py` | `calc1.f` |
| `contribuciones.py` | contribución de los grupos a los máximos diarios (MAXDCONT): MAXDCONT_LOOP y MAXD_METEXT de aermod.f, MAXDCALC y MAXDCNT_FILE de output.f. | `maxdcont.py` | `aermod.f`, `output.f` |
| `control.py` | lectura del fichero de control. | `control.py` | `setup.f`, `aermod.f` |
| `depura.py` | opciones de depuración (DEBUGOPT). | `depura.py` | `coset.f` |
| `emisiones.py` | emisiones horarias desde fichero (HOUREMIS): HRQREAD y HRQEXT de aermod.f. La tarjeta SO HOUREMIS (HREMIS) está en entrada_fuentes.py y la lectura de cada hora en bucle_horario.py (HRLOOP). | `emisiones.py` | `aermod.f` |
| `entrada_control.py` | vía CO (coset.f). | `coset.py` | `coset.f` |
| `entrada_fuentes.py` | vía SO (soset.f). | `soset.py` | `soset.f` |
| `entrada_meteo.py` | vía ME (meset.f). | `meset.py` | `meset.f` |
| `entrada_no2.py` | entrada de las opciones de química del NO2 (OLM, PVMRM, ARM2, TTRM, GRSM y PSDCREDIT). | `no2set.py` | `coset.f`, `soset.f` |
| `entrada_receptores.py` | vía RE (reset.f). | `reset.py` | `reset.f` |
| `entrada_salidas.py` | vía OU (ouset.f). | `ouset.py` | `ouset.f` |
| `estado.py` | estado global y servicios comunes. | `estado.py` | `modules.f`, `aermod.f` |
| `estela_edificio.py` | algoritmo PRIME de downwash por edificios (prime.f). Las variables de sus módulos están en ``e.P``. | `prime.py` | `prime.f` |
| `fondo.py` | concentraciones de fondo (BACKGRND): BGEXT de aermod.f (lectura del fichero horario de fondo) y el paso horario de HRLOOP. | `fondo.py` | `aermod.f` |
| `formato.py` | Compatibilidad de E/S y numérica con el Fortran de AERMOD 26135 (US EPA, dominio público). | `fortran.py` | `setup.f` |
| `fuente_carretera.py` | fuentes de carretera RLINE y RLINEXT. | `rline.py` | `rline.f` |
| `fuente_foso.py` | fuentes OPENPIT (canteras y fosos abiertos). | `openpit.py` | `calc1.f`, `pitarea.f`, `aermod.f`, `soset.f`, `inpsum.f` |
| `fuente_linea_flotante.py` | fuentes lineales flotantes BUOYLINE (algoritmo adaptado del modelo BLP). | `bline.py` | `bline.f` |
| `fuente_sidewash.py` | fuentes SWPOINT (chimenea junto a un edificio, con arrastre lateral o «sidewash»; opción ALPHA). | `sidewash.py` | `calc1.f`, `soset.f` |
| `funciones_dispersion.py` | rutinas numéricas de calc2.f (de EMFACT a ERFX): factores de emisión y de fondo, distancia a la sobreelevación final, estela, distancias fuente-receptor, términos laterales y verticales de la distribución gaussiana, mean… | `calc2.py` | `calc2.f` |
| `integracion_area.py` | integración numérica de las fuentes de área (pitarea.f): AVERTS, AREAIN, PLUMEF, PSIDE, XWIDTH, PWIDTH, ZBRENT, PSIDE2, HPSORT, QATR3 y QG2. | `pitarea.py` | `pitarea.f` |
| `meteo_horaria.py` | lectura de la meteorología (metext.f). | `metext.py` | `metext.f` |
| `nucleo.py` | Núcleo compilado con numba del cálculo por receptor (fuentes de área). | `nucleo.py` | — |
| `parametros_efectivos.py` | parámetros meteorológicos efectivos del penacho (iblval.f: IBLVAL y METINI; LOCATE y ANYAVG están en perfiles.py). | `iblval.py` | `iblval.f` |
| `perfiles.py` | perfiles meteorológicos en la malla de alturas GRIDHT (windgrid.f, tempgrid.f, siggrid.f y las utilidades GINTRP y ZIAVER de metext.f). | `perfiles.py` | `windgrid.f`, `tempgrid.f`, `siggrid.f`, `metext.f` |
| `principal.py` | programa principal (aermod.f, PROGRAM AERMOD y FILOPN). | `principal.py` | `aermod.f` |
| `quimica_cinetica.py` | esquema químico GRS para el NO2 (grsm.f: GRSM_CALC, RXNRATES, GETBGDEQUIL, QuadraticEquil, FindInitDt, DConcsDt, DoGRSMChem, AdaptiveRK, CashKarpRK y PLUMESIZES). | `grsm.py` | `grsm.f` |
| `quimica_no2.py` | química del NO2 en el cálculo horario. | `no2.py` | `aermod.f`, `calc1.f`, `calc2.f` |
| `reinicio.py` | re-arranque de corridas y corridas de varios años encadenados (SAVEFILE, INITFILE y MULTYEAR). | `reinicio.py` | `calc2.f`, `inpsum.f`, `ouset.f` |
| `resultados.py` | acumulación de resultados horarios (calc2.f: SUMVAL, AVER, HIVALS, NHIGH, HSETFG, MAXVALUE, MSETFG, MAXFIL, POSTFL). | `resultados.py` | `calc2.f` |
| `resumen_entrada.py` | resumen de las entradas (inpsum.f): INPSUM, PRTOPT, PRTSRC, PRTREC, CHKREC, PRTMET y RESINI, para las opciones del alcance. | `inpsum.py` | `inpsum.f` |
| `salida.py` | resultados finales (parte final del programa principal de aermod.f y output.f: PERAVE, HIPER, PSTANN, PLTANN, PLOTFL, OUTPUT, PRTANN, PRTNHI, SPRTHT, PRTMAX, PRTSUM) y las tablas diarias de DAYTABLE (PRTDAY, calc2.f). | `salida.py` | `aermod.f`, `output.f`, `calc2.f` |
| `sigmas.py` | coeficientes de dispersión (sigmas.f: SIGY, SIGZ, BID, SZSFCL, RMSSIG) y sobreelevación del penacho (prise.f: DELTAH, PRMDELH, HSPRIM, SBLRIS, CBLPRD, CBLPRN, CBLPR3). | `sigmas.py` | `sigmas.f` |
| `tablas.py` | GENERADO por ../generar_tablas.py a partir de modules.f de AERMOD 26135 (US EPA, dominio público). No editar a mano. | `tablas.py` | `modules.f` |

## Funciones por fichero

850 funciones; 740 con equivalencia explícita. Las auxiliares de la traducción no tienen rutina propia en el original.

### `bucle_horario.py`

bucle horario (aermod.f, HRLOOP).

| Función | Definición | Equivale a |
|---|---|---|
| `hrloop(e)` | HRLOOP: lee la meteorología hora a hora, calcula y acumula los promedios. | AERMOD `HRLOOP` (aermod.f) |
| `_emisiones_hora(e)` | Emisiones horarias (HOUREMIS) de cada fuente para la hora en curso. | auxiliar de la traducción |
| `_hora(e)` | Cuerpo del bucle para una hora que entra en el cálculo. | auxiliar de la traducción |
| `_mxdval(e, ia)` | — | auxiliar de la traducción |
| `chk_endyr(e)` | CHK_ENDYR: fin de año para ANNUAL / PM25 / NO2 / SO2 / MULTYEAR. | AERMOD `CHK_ENDYR` (aermod.f) |
| `mxdlyfl(e)` | MXDLYFL: máximos diarios (PM25AVE/NO2AVE/SO2AVE): fichero MAXDAILY y tabla HIMXDLY. | AERMOD `MXDLYFL` (calc2.f) |
| `mxdybyyr(e, n)` | MXDYBYYR (calc2.f): N-ésimo máximo diario del año de cada receptor al fichero MXDYBYYR. | AERMOD `MXDYBYYR` (calc2.f) |

### `calculo_area.py`

cálculo horario por fuente y receptor (calc1.f: CALC, ACALC, ARDIST, SETSRC, FLUXES, HEFF, PRMHEFF, PDIS, VDIS, ADISY, ADISZ, CENTROID, REFL_HT, PENFCT, CPLUME, PRM_PLUME, ACPLUME, AER_PCHI, AER_ACHI) y la deposición (VD…

| Función | Definición | Equivale a |
|---|---|---|
| `_m()` | — | auxiliar de la traducción |
| `calc(e)` | CALC: recorre las fuentes para la hora en curso. | AERMOD `CALC` (calc1.f) |
| `_setsrc_aft(e, i)` | SETSRC: parámetros de aeronave de la fuente I (o cero si no lo es). | AERMOD `SETSRC` (calc1.f) |
| `_setsrc_vert(e, i, n)` | SETSRC: vértices de la fuente I (los N más el primero repetido). | AERMOD `SETSRC` (calc1.f) |
| `setsrc(e)` | SETSRC: copia los parámetros de la fuente ISRC a las variables de trabajo. | AERMOD `SETSRC` (calc1.f) |
| `fluxes(e)` | FLUXES: flujos de flotabilidad y cantidad de movimiento. Devuelve VSEQ. | AERMOD `FLUXES` (calc1.f) |
| `heff(e, xarg)` | HEFF: altura efectiva del penacho a la distancia XARG. | AERMOD `HEFF` (calc1.f) |
| `prmheff(e)` | PRMHEFF: altura efectiva para el penacho de PRIME. | AERMOD `PRMHEFF` (calc1.f) |
| `pdis(e, xarg)` | PDIS: sigmas de una fuente puntual. | AERMOD `PDIS` (calc1.f) |
| `vdis(e, xarg)` | VDIS: sigmas de una fuente de volumen. | AERMOD `VDIS` (calc1.f) |
| `adisy(e, xarg)` | ADISY: sigma-y de una fuente de área. | AERMOD `ADISY` (calc1.f) |
| `adisz(e, xarg)` | ADISZ: sigma-z de una fuente de área. | AERMOD `ADISZ` (calc1.f) |
| `centroid(e, xarg)` | CENTROID: altura del centroide del penacho en convectiva. | AERMOD `CENTROID` (calc1.f) |
| `refl_ht(e, hearg, xarg, szbarg, vsigzarg)` | REFL_HT: altura de la superficie reflectora en estable. Devuelve HEREFL. | AERMOD `REFL_HT` (calc1.f) |
| `penfct(e)` | PENFCT: fracción de penacho que penetra la inversión. | AERMOD `PENFCT` (calc1.f) |
| `cplume(e, zarg)` | CPLUME: concentración del penacho (puntual/volumen) a la altura ZARG. Devuelve COUT. | AERMOD `CPLUME` (calc1.f) |
| `prm_plume(e, zarg, ueffph)` | PRM_PLUME: concentración del penacho de PRIME. Devuelve COUT. | AERMOD `PRM_PLUME` (calc1.f) |
| `acplume(e, zarg, fyarg)` | ACPLUME: concentración por unidad de emisión de un elemento de área. Devuelve COUT. | AERMOD `ACPLUME` (calc1.f) |
| `_humedo(e, adj, jin)` | — | auxiliar de la traducción |
| `aer_pchi(e, xarg, adj, vdinp, jin, aerout)` | AER_PCHI: concentración/depósito de AERMOD para puntual y volumen (AEROUT en sitio). | AERMOD `AER_PCHI` (calc1.f) |
| `aer_achi(e, xarg, adj, vdinp, jin, fyarg)` | AER_ACHI: concentración/depósito de un elemento de área para el tipo ITYP. Devuelve POUT. | AERMOD `AER_ACHI` (calc1.f) |
| `debout(e)` | DEBOUT: componentes del penacho en el receptor (fichero MODEL de DEBUGOPT). | AERMOD `DEBOUT` (calc1.f) |
| `_restab(lanuse, j, isea5)` | — | auxiliar de la traducción |
| `deposicion_fuente(e, puntual)` | Variables de deposición de la fuente ISRC para la hora (bloque común de PCALC, VCALC y ACALC antes del bucle de receptores): | — |
| `vdp(e)` | VDP: velocidades de deposición seca de partículas (VDEP, por categoría de tamaño; método 1 o método 2) y de gases (VDEPG) según Wesely et al. (2001). Fija también ZRDEP, XNU, SCHMI… | AERMOD `VDP` (calc1.f) |
| `scavrat(e)` | SCAVRAT: coeficientes de lavado húmedo (Walcek) de partículas (PSCVRT, WASHOUT, ECOLL; la eficiencia de colisión según Slinn y Seinfeld-Pandis) o de gases (GSCVRT); fija también LI… | AERMOD `SCAVRAT` (calc1.f) |
| `pdep(e, xarg)` | PDEP: factores de agotamiento del penacho de partículas a la distancia XARG, por sedimentación y deposición seca (DQCOR, integrando con DEPLETE) y por lavado (WQCOR). | AERMOD `PDEP` (calc1.f) |
| `pdepg(e, xarg)` | PDEPG: factores de agotamiento del penacho de gases (DQCORG seco, WQCORG húmedo). | AERMOD `PDEPG` (calc1.f) |
| `deplete(e, vdi, xri, lromb, ifct)` | DEPLETE (y PRM_DEPLETE con ifct = 2): | AERMOD `DEPLETE` (calc1.f) |
| `_fct_dep(e, ifct, x)` | Integrando de DEPLETE: F2INT (ifct = 1) o PRM_F2INT (ifct = 2). | auxiliar de la traducción |
| `qatr2(e, xl, xu, eps, ndim, ifct)` | QATR2: integración de Romberg (DQATR de IBM SSP) del integrando de DEPLETE, con el criterio de convergencia de AERMOD (integral < 1e-10, error relativo EPS o paso < 1 m). Devuelve … | AERMOD `QATR2` (calc1.f) |
| `qg2d2(e, xl, xu, ifct)` | QG2D2: integral por cuadratura de Gauss de 2 puntos del integrando de DEPLETE (los dos puntos se evalúan en el orden del original: A+Y y después A-Y). | AERMOD `QG2D2` (calc1.f) |
| `f2int(e, xi)` | F2INT: integrando de DEPLETE a la distancia XI (término vertical a la altura de referencia de la deposición, mezcla de los penachos horizontal y que sigue el terreno). Recalcula el… | AERMOD `F2INT` (calc1.f) |
| `_f2int_vertical(e)` | F2INT: término vertical dividido por el viento efectivo a la altura ZR (VWRAP o VLIFT). | AERMOD `F2INT` (calc1.f) |
| `_cero_chi(e, irec, isrc)` | Pone a cero CHI y, con PVMRM/GRSM, los datos del penacho de la fuente en el receptor (para que no persista el valor de la hora anterior). | auxiliar de la traducción |
| `_guardar_chi(e, irec, isrc)` | Guarda HRVAL de la fuente en el receptor (CHI) y, con PVMRM/GRSM, la altura del penacho, el viento efectivo, la disipación, la fracción penetrada y FOPT; | auxiliar de la traducción |
| `_cero_receptor(e, aerout)` | Pone a cero la contribución del receptor (ramas CYCLE RECEPTOR_LOOP de ACALC). | auxiliar de la traducción |
| `ardist(e, indx)` | ARDIST: distancias receptor-vértices de un área. Devuelve (XDEP, WIDTH, LENGTH, XMINREC, XMAXREC); fija XR, YR, ZELEV, ZHILL, ZFLAG, X, Y, DISTR, ZRT y SPA. | AERMOD `ARDIST` (calc1.f) |
| `_met_urbana(e)` | Selección de la meteorología urbana/rural de la fuente (común a ACALC, PCALC, VCALC). | auxiliar de la traducción |
| `_met_rural(e)` | — | auxiliar de la traducción |
| `acalc(e)` | ACALC: cálculo para una fuente de área (AREA, AREAPOLY, AREACIRC, LINE). | AERMOD `ACALC` (calc1.f) |
| `_acalc_bucle(e, qtksav, aerout)` | Bucle de receptores de ACALC (la parte que se compila con numba en nucleo.py). | auxiliar de la traducción |
| `_acalc_rapido(e, aerout, qtksav)` | Rama FASTAREA/FASTALL de ACALC: | auxiliar de la traducción |

### `calculo_punto_volumen.py`

fuentes puntuales (calc1.f: PCALC, AERCALC, PRMCALC, GAMCALC, PRM_PCHI, y el agotamiento del penacho de PRIME: PRM_PDEP, PRM_PDEPG, PRM_F2INT) y de volumen (VCALC, VOLCALC).

| Función | Definición | Equivale a |
|---|---|---|
| `_m()` | — | auxiliar de la traducción |
| `pcalc(e)` | PCALC: cálculo para una fuente puntual (POINT, POINTCAP, POINTHOR). | AERMOD `PCALC` (calc1.f) |
| `_pcalc_bucle(e, aerplm, aerpan)` | Bucle de receptores de PCALC (la parte que se compila con numba en nucleo.py). | auxiliar de la traducción |
| `aercalc(e, xarg, l_plume, aerout)` | AERCALC: concentración del penacho coherente (L_PLUME) o del meandro (AEROUT en sitio). | AERMOD `AERCALC` (calc1.f) |
| `prmcalc(e, xbrec, ybrec)` | PRMCALC: concentración con el algoritmo PRIME (downwash por edificios). | AERMOD `PRMCALC` (calc1.f) |
| `prm_pdep(e, xarg)` | PRM_PDEP: factores de agotamiento de las partículas para el penacho de PRIME. | AERMOD `PRM_PDEP` (calc1.f) |
| `prm_pdepg(e, xarg)` | PRM_PDEPG: factores de agotamiento de los gases para el penacho de PRIME. | AERMOD `PRM_PDEPG` (calc1.f) |
| `prm_f2int(e, xi)` | PRM_F2INT: integrando de PRM_DEPLETE (penacho de PRIME) a la distancia XI: sobreelevación y sigmas de la estela a esa distancia, inclinación por sedimentación y término vertical a … | AERMOD `PRM_F2INT` (calc1.f) |
| `gamcalc(e, xarg, yarg)` | GAMCALC: factor de mezcla GAMFACT entre PRIME y AERMOD. | AERMOD `GAMCALC` (calc1.f) |
| `prm_pchi(e, adj, vdinp, jin, insrc)` | PRM_PCHI: concentración/depósito del penacho de PRIME (acumula en PRMVAL). | AERMOD `PRM_PCHI` (calc1.f) |
| `vcalc(e)` | VCALC: cálculo para una fuente de volumen. | AERMOD `VCALC` (calc1.f) |
| `_vcalc_bucle(e, aerplm, aerpan)` | Bucle de receptores de VCALC (la parte que se compila con numba en nucleo.py). | auxiliar de la traducción |
| `volcalc(e, xarg, l_plume, aerout)` | VOLCALC: concentración del penacho coherente o del meandro de una fuente de volumen. | AERMOD `VOLCALC` (calc1.f) |

### `contribuciones.py`

contribución de los grupos a los máximos diarios (MAXDCONT): MAXDCONT_LOOP y MAXD_METEXT de aermod.f, MAXDCALC y MAXDCNT_FILE de output.f.

| Función | Definición | Equivale a |
|---|---|---|
| `maxd_metext(e)` | MAXD_METEXT: recupera la meteorología guardada de la hora (IHR_NDX, IYR_NDX). | AERMOD `MAXD_METEXT` (aermod.f) |
| `maxdcalc(e)` | MAXDCALC: cálculo de una hora de MAXDCONT (para el receptor guardado en la posición 1). | AERMOD `MAXDCALC` (output.f) |
| `_vaciar_chi(e)` | CHI (y las matrices de GRSM) a cero entre recálculos de MAXDCONT. | auxiliar de la traducción |
| `_nombre_rango(ival)` | — | auxiliar de la traducción |
| `maxdcnt_file(e, ig, ival)` | MAXDCNT_FILE: escribe las contribuciones del rango IVAL del grupo IG. | AERMOD `MAXDCNT_FILE` (output.f) |
| `maxdcont_loop(e)` | MAXDCONT_LOOP: recálculo receptor a receptor de las horas de los valores de diseño. | AERMOD `MAXDCONT_LOOP` (aermod.f) |

### `control.py`

lectura del fichero de control.

| Función | Definición | Equivale a |
|---|---|---|
| `cargar(e, linea)` | READ (A0512,T1,0512A1) + LWRUPR: | — |
| `define(e)` | DEFINE: localiza los campos de la línea (las comillas dobles delimitan campos con blancos). | AERMOD `DEFINE` (setup.f) |
| `getfld(e)` | GETFLD: contenido de los campos 1..IFC (truncados a ILEN_FLD); los demás quedan en blanco. FIELD va en mayúsculas; FIELD1 conserva el texto original (nombres de fichero). | AERMOD `GETFLD` (setup.f) |
| `expath(e, inpfld, pathwy)` | EXPATH -> nopath. | AERMOD `EXPATH` (aermod.f) |
| `exkey(e, inpfld)` | EXKEY -> nokey. | AERMOD `EXKEY` (setup.f) |
| `setord(e)` | SETORD: orden de STARTING/FINISHED y de las vías. | AERMOD `SETORD` (setup.f) |
| `sindex(arrin, idim, elem)` | SINDEX -> (índice, encontrado). | AERMOD `SINDEX` (setup.f) |
| `fsplit(e, pathin, keyin, inpfld, length, delim)` | FSPLIT: divide un campo por el delimitador (buscado desde el final). Devuelve (lflag, begfld, endfld) en forma canónica. | AERMOD `FSPLIT` (setup.f) |
| `dbl(e, i, previo)` | CALL STODBL(FIELD(i),ILEN_FLD,DNUM,IMIT) -> (valor, imit). | — |
| `num(e, i, previo)` | CALL STONUM(FIELD(i),ILEN_FLD,FNUM,IMIT) -> (valor, imit). | — |
| `i8(n)` | — | — |
| `setup(e)` | SETUP: lee y procesa el fichero de control, vía a vía. | AERMOD `SETUP` (setup.f) |
| `includ(e)` | INCLUD: procesa un fichero INCLUDED (vías SO, RE y EV). | AERMOD `INCLUD` (setup.f) |
| `preset(e)` | PRESET: primer pase por el fichero de control para dimensionar las matrices. | AERMOD `PRESET` (aermod.f) |
| `preinclud(e)` | PREINCLUD: pase previo de un fichero INCLUDED (no restaura ILINE al volver). | AERMOD `PREINCLUD` (aermod.f) |
| `_avisos_fuente(e, arm2)` | — | auxiliar de la traducción |
| `srcsiz(e)` | SRCSIZ: cuenta fuentes, grupos, vértices... (vía SO del pase previo). | AERMOD `SRCSIZ` (aermod.f) |
| `recsiz(e)` | RECSIZ: cuenta receptores y redes (vía RE del pase previo). | AERMOD `RECSIZ` (aermod.f) |
| `_red_pre(e, claves)` | — | auxiliar de la traducción |
| `precart(e)` | PRECART: tamaño de una red GRIDCART. | AERMOD `PRECART` (aermod.f) |
| `_isc(e, clave)` | — | auxiliar de la traducción |
| `pregencar(e)` | — | AERMOD `PREGENCAR` (aermod.f) |
| `prexypnts(e)` | — | AERMOD `PREXYPNTS` (aermod.f) |
| `prepolr(e)` | PREPOLR: tamaño de una red GRIDPOLR. | AERMOD `PREPOLR` (aermod.f) |
| `set_window(e)` | SET_WINDOW: ventana de siglo para los años de 2 cifras (ME SURFDATA). | AERMOD `SET_WINDOW` (aermod.f) |
| `allsetup(e)` | ALLSETUP: crea las matrices de entrada (las de opciones fuera de alcance no se crean). | AERMOD `ALLSETUP` (aermod.f) |
| `_allsetup_no2(e, a, nsrc, nrec, ntyp, ngrp)` | Matrices de la química del NO2 (ALLSETUP) con los valores iniciales de VARINI. | auxiliar de la traducción |
| `allresult(e)` | ALLRESULT: memoria estimada (STORE, en precisión simple) y matrices de resultados. | AERMOD `ALLRESULT` (aermod.f) |
| `varini(e)` | VARINI: valores iniciales de las variables (tras ALLSETUP). | AERMOD `VARINI` (setup.f) |

### `depura.py`

opciones de depuración (DEBUGOPT).

| Función | Definición | Equivale a |
|---|---|---|
| `w(e, u)` | WRITE(u,*) dirigido por lista. | — |
| `wf(e, u, fmt)` | WRITE(u,fmt) formateado. | — |
| `activa(e)` | ¿Hay alguna opción de depuración que escriba desde el cálculo? (fuerza la vía Python). | — |
| `debopt(e)` | DEBOPT: tarjeta CO DEBUGOPT (repetible). | AERMOD `DEBOPT` (coset.f) |
| `open_debugfile(e, unidad, fname, nam, dbgoption, dbgopt, ftyp)` | OPEN_DEBUGFILE: abre el fichero (si no lo está ya) y escribe la cabecera común. | AERMOD `OPEN_DEBUGFILE` (coset.f) |
| `open_all_debugfiles(e)` | OPEN_ALL_DEBUGFILES: abre los ficheros de las opciones de depuración elegidas y escribe las cabeceras de columnas de cada uno. | AERMOD `OPEN_ALL_DEBUGFILES` (coset.f) |
| `hrloop(e)` | Marca de la hora en el fichero MODEL (HRLOOP). | AERMOD `HRLOOP` (aermod.f) |
| `pcalc_delh(e)` | — | — |
| `opth2_iter(e, kiter, dhold, dhnew, zplm)` | Iteración de la sobreelevación estable (PCALC 6001 y DELTAH 6001). | — |
| `pcalc_noconv(e)` | — | — |
| `deltah_noconv(e)` | — | — |
| `pcalc_zmid(e)` | — | — |
| `pcalc_efectivos(e, unidad)` | PCALC: parámetros de los valores efectivos y PSRDEB (en VCALC/ACALC con aeronaves se escribe en ARCFTDBG sin PSRDEB). | AERMOD `PCALC` (calc1.f) |
| `psrdeb(e)` | PSRDEB: datos de la fuente puntual. | AERMOD `PSRDEB` (calc1.f) |
| `aerval_comp(e, aerpan, aerplm, fran, val, nombre)` | Componentes del penacho coherente y del meandro (PCALC: | — |
| `prime_gamfact(e)` | PCALC con PRIMEDBG: mezcla de PRIME y AERMOD en el receptor. | AERMOD `PCALC` (calc1.f) |
| `efectivos_ini(e, l_plume)` | AERCALC / VOLCALC: parámetros efectivos iniciales del penacho coherente o del meandro. | AERMOD `AERCALC` (calc1.f) |
| `area_efectivos_ini(e)` | ACALC: parámetros efectivos iniciales del área. | AERMOD `ACALC` (calc1.f) |
| `aer_pchi_conc(e, ityp, adj, aerout)` | — | — |
| `aer_pchi_dep(e, tipo, ityp, adj, a, b, c, aerout)` | AER_PCHI: DEPOS (adj, vdinp, dryflux, wetflux), DDEP (adj, vdinp, dryflux) o WDEP (adj, zsubp, prate, wetflux). | AERMOD `AER_PCHI` (calc1.f) |
| `debout(e)` | DEBOUT: componentes del penacho en el receptor. | AERMOD `DEBOUT` (calc1.f) |
| `meandr(e, svef, uef, umean, ttrav, tran, totkin, sigran, fran)` | MEANDR: términos del meandro (escritura dirigida por lista). | AERMOD `MEANDR` (calc2.f) |
| `ibl_ini(e, cual)` | IBLVAL: parámetros efectivos iniciales (estable, directo o penetrado). | AERMOD `IBLVAL` (iblval.f) |
| `ibl_hbp(e)` | — | — |
| `ibl_capa(e, cual, centro, sz, zlo, zhi)` | IBLVAL: capa sobre la que se promedian los parámetros (Stable / Penetrated / Direct). | AERMOD `IBLVAL` (iblval.f) |
| `ibl_fin(e, cual)` | IBLVAL: parámetros efectivos finales (estable, penetrado o directo). | AERMOD `IBLVAL` (iblval.f) |
| `metdeb(e)` | METDEB: meteorología de la hora (cabecera una vez por fuente y hora) y parámetros efectivos en cada receptor. | AERMOD `METDEB` (metext.f) |
| `vdp1_ent(e)` | VDP1: datos de partículas de cada fuente (MODEL). | AERMOD `VDP1` (soset.f) |
| `vdp1_gas(e)` | — | — |
| `vdp1_part(e)` | — | — |
| `vdp_part(e, ra, rds)` | VDP: resistencias y velocidades de deposición de partículas del método 1 (MODEL). | AERMOD `VDP` (calc1.f) |
| `vdp_fin(e, ra, rb, rc, rds, rp)` | VDP: resistencias y velocidades a GDEP.DAT (gases) y PDEP.DAT (partículas). | AERMOD `VDP` (calc1.f) |
| `scavrat_ent(e)` | — | — |
| `scavrat_res(e)` | — | — |
| `awma_pcalc(e)` | — | — |
| `awma_receptor(e, irec)` | — | — |
| `wu(e, u)` | WRITE(u,*) a una unidad que puede no estar abierta (Intel crea entonces fort.N). | — |
| `wfu(e, u, fmt)` | — | — |
| `numrise_paso(e, u, znf, ds0)` | — | — |
| `numrise_traza(e, u, nnp, zc, ua, ra, ta, dudz, dpdz, dzds, ipositn, h)` | — | — |
| `numrise_dfsn_a(e, u, zc, xb, szi, syi)` | — | — |
| `numrise_dfsn_b(e, u, yfin, ztin, xbi, szi, syi)` | — | — |
| `numrise_error(e, u, nn, mxnw)` | NUMRISE con NN > MXNW: el mensaje se escribe siempre (aunque no haya depuración). | AERMOD `NUMRISE` (prime.f) |
| `numrise_fin(e, u, texit, fb, fm, xmax, xfin0, x15r, xfin, yfin, zfin, h, rfin, zcumul)` | — | — |
| `numrise_tray(e, u, despues, xtr, ytr, ztr, rtr, ntr)` | — | — |
| `wake_scales(e, u, kurdat)` | — | AERMOD `WAKE_SCALES` (prime.f) |
| `wake_dfsn_ambiente(e, u, dfsn2, xaz, xay, xi, awma)` | WAKE_DFSN(2): el penacho no se ve alterado por la turbulencia de la estela. | AERMOD `WAKE_DFSN` (prime.f) |
| `wake_dfsn_fin(e, u, ldbhr, xaz, xay, xi, xbc, xdc, lwak, lcav, np_, nws, ncs)` | WAKE_DFSN: resumen y tablas de la estela y de la cavidad (DEBUG de PRIME y AWMADW). NPW y NPC solo se calculan con estela/cavidad; si no, el original imprime el valor que quedó de … | AERMOD `WAKE_DFSN` (prime.f) |
| `wake_dfsn2_ambiente_awma(e, xaz, xay, xi)` | — | — |
| `wake_dfsn2_awma_ini(e)` | — | — |
| `wake_dfsn2_fin(e, u, ldbhr)` | — | — |
| `wake_xa(e, ambiz, ambiy, farizt, fariyt, xaz, xay)` | — | AERMOD `WAKE_XA` (prime.f) |
| `wake_fqc(e, u, xbi, xbstart, xbend, xstep, nstep, fractz0, xb85, xmax, fzmax)` | — | AERMOD `WAKE_FQC` (prime.f) |
| `prmcalc_efectivos(e, zlo, zhi)` | — | — |
| `wake_dbg(e, io, ntr, xtr, ytr, ztr, rtr, nobid, hstack)` | WAKE_DBG (PRMDELH con PRIMEDBG): | AERMOD `WAKE_DBG` (prime.f) |

### `emisiones.py`

emisiones horarias desde fichero (HOUREMIS): HRQREAD y HRQEXT de aermod.f. La tarjeta SO HOUREMIS (HREMIS) está en entrada_fuentes.py y la lectura de cada hora en bucle_horario.py (HRLOOP).

| Función | Definición | Equivale a |
|---|---|---|
| `_area_o_linea(t)` | — | auxiliar de la traducción |
| `hrqread(e, i)` | HRQREAD(IS): lee el registro de la fuente IS del fichero de emisiones horarias. Deja ILINE en el número de línea de ese fichero (IQLINE(IS)), como el original, que no lo restaura. | AERMOD `HRQREAD` (aermod.f) |
| `hrqext(e, i)` | HRQEXT(IS): pasa los parámetros leídos de la hora a las matrices de la fuente y los comprueba. | AERMOD `HRQEXT` (aermod.f) |

### `entrada_control.py`

vía CO (coset.f).

| Función | Definición | Equivale a |
|---|---|---|
| `cocard(e)` | COCARD: claves de la vía CO. | AERMOD `COCARD` (coset.f) |
| `urbopt(e)` | URBOPT: tarjeta URBANOPT (población, nombre y rugosidad de cada zona urbana). | AERMOD `URBOPT` (coset.f) |
| `gddef(e)` | GDDEF: parámetros por defecto de la deposición seca de gases (GASDEPDF): reactividad Fo, fracción del LAI verde máximo de las categorías estacionales 2 y 5 y especie de referencia. | AERMOD `GDDEF` (coset.f) |
| `_indices_gd(e, m, nmax, imax, destino)` | Lista de índices enteros (STONUM, con repetición n*valor) de GDSEASON/GDLANUSE. | auxiliar de la traducción |
| `gdseas(e)` | GDSEAS: categoría estacional de Wesely (1-5) de cada mes (GDSEASON). | AERMOD `GDSEAS` (coset.f) |
| `gvsubd(e)` | GVSUBD: velocidad de deposición seca de gases dada por el usuario (GASDEPVD). | AERMOD `GVSUBD` (coset.f) |
| `gdland(e)` | GDLAND: categoría de uso del suelo (1-9) de cada sector de 10 grados (GDLANUSE). | AERMOD `GDLAND` (coset.f) |
| `_finished(e)` | — | auxiliar de la traducción |
| `titles(e)` | TITLES: el título es el resto de la línea tras la clave (con mayúsculas y minúsculas). | AERMOD `TITLES` (coset.f) |
| `_tipo(e, ityp, nombre)` | Etiquetas de un tipo de salida (CONC, DEPOS, DDEP, WDEP). | auxiliar de la traducción |
| `modopt(e)` | MODOPT: opciones del modelo (MODELOPT). | AERMOD `MODOPT` (coset.f) |
| `avetim(e)` | AVETIM: periodos de promedio (AVERTIME). | AERMOD `AVETIM` (coset.f) |
| `_fmod(a, b)` | — | auxiliar de la traducción |
| `pollid(e)` | POLLID: identificador del contaminante (POLLUTID). | AERMOD `POLLID` (coset.f) |
| `edecay(e)` | EDECAY: semivida o coeficiente de decaimiento. | AERMOD `EDECAY` (coset.f) |
| `runnot(e)` | RUNNOT: RUNORNOT RUN/NOT. | AERMOD `RUNNOT` (coset.f) |
| `flagdf(e)` | FLAGDF: altura de receptor por defecto (FLAGPOLE). | AERMOD `FLAGDF` (coset.f) |
| `errfil(e)` | ERRFIL: fichero de mensajes detallado (ERRORFIL). | AERMOD `ERRFIL` (coset.f) |
| `_fichero_campo(e, m, campo, lb)` | RUNST1(LOCB(campo):LOCE(campo)) con la comprobación de longitud del original (`lb` es el índice del LOCB que usa la comprobación, que en MYEAR no siempre es el del campo). | auxiliar de la traducción |
| `savefl(e)` | SAVEFL: fichero de re-arranque (SAVEFILE). | AERMOD `SAVEFL` (coset.f) |
| `initfl(e)` | INITFL: fichero de inicio de un re-arranque (INITFILE). | AERMOD `INITFL` (coset.f) |
| `myear(e)` | MYEAR: corrida de varios años encadenados (MULTYEAR); INCRST se fija en MECARD. | AERMOD `MYEAR` (coset.f) |
| `_abrir_reinicio(e)` | FINISHED: abre (vacíos) los SAVEFILE y comprueba el INITFILE. Devuelve False si falla la apertura (el original salta entonces al final de FINISHED, tras el error 500). | auxiliar de la traducción |
| `_error_reinicio(e, m)` | — | auxiliar de la traducción |

### `entrada_fuentes.py`

vía SO (soset.f).

| Función | Definición | Equivale a |
|---|---|---|
| `_orden_grupo(e, m)` | — | auxiliar de la traducción |
| `socard(e)` | SOCARD: claves de la vía SO. | AERMOD `SOCARD` (soset.f) |
| `urbans(e)` | URBANS: tarjeta URBANSRC (fuentes urbanas y zona urbana a la que pertenecen). | AERMOD `URBANS` (soset.f) |
| `hremis(e)` | HREMIS: tarjeta HOUREMIS (fichero de emisiones horarias y fuentes que lo usan). Un fichero ya declarado reutiliza su unidad; uno nuevo toma la siguiente unidad dinámica (FUNITINX). | AERMOD `HREMIS` (soset.f) |
| `_finished(e)` | — | auxiliar de la traducción |
| `soelun(e)` | SOELUN: unidades de la cota de las fuentes. | AERMOD `SOELUN` (soset.f) |
| `soloca(e)` | SOLOCA: LOCATION (identificador, tipo y coordenadas de la fuente). | AERMOD `SOLOCA` (soset.f) |
| `_cota(e, m, isrc, soid, k)` | Cota de la base de la fuente en el campo K de LOCATION (LINE, BUOYLINE, RLINE: | auxiliar de la traducción |
| `soparm(e)` | SOPARM: SRCPARAM (parámetros de la fuente según su tipo). | AERMOD `SOPARM` (soset.f) |
| `pparm(e, i, temp)` | PPARM: fuentes puntuales. | AERMOD `PPARM` (soset.f) |
| `vparm(e, i, temp)` | VPARM: fuentes de volumen. | AERMOD `VPARM` (soset.f) |
| `_qs_hs_area(e, m, i)` | — | auxiliar de la traducción |
| `_szini_area(e, m, i)` | — | auxiliar de la traducción |
| `aparm(e, i, temp)` | APARM: fuentes de área rectangulares. | AERMOD `APARM` (soset.f) |
| `lparm(e, i, temp)` | LPARM: fuentes LINE (se tratan como un área rectangular girada entre los dos extremos). | AERMOD `LPARM` (soset.f) |
| `apparm(e, i, temp)` | APPARM: fuentes de área poligonales (los vértices llegan con AREAVERT). | AERMOD `APPARM` (soset.f) |
| `arvert(e)` | ARVERT: vértices de una fuente AREAPOLY. | AERMOD `ARVERT` (soset.f) |
| `acparm(e, i, temp)` | ACPARM: fuentes de área circulares. | AERMOD `ACPARM` (soset.f) |
| `gencir(e, i)` | GENCIR: polígono equivalente (misma área) a un círculo. | AERMOD `GENCIR` (soset.f) |
| `_rango(e, m, soid)` | Identificadores LID-HID de un campo con rango (FSPLIT + SETIDG). | auxiliar de la traducción |
| `dsbldg(e)` | DSBLDG: dimensiones de edificios por sector (BUILDHGT/WID/LEN, XBADJ, YBADJ). | AERMOD `DSBLDG` (soset.f) |
| `dsfill(e, isdx)` | DSFILL: rellena los valores por sector de una fuente. | AERMOD `DSFILL` (soset.f) |
| `emvary(e)` | EMVARY: factores de emisión variables (EMISFACT). | AERMOD `EMVARY` (soset.f) |
| `effill(e, isdx, iqmax)` | EFFILL: valores de los factores de emisión. | AERMOD `EFFILL` (soset.f) |
| `back_grnd(e)` | BACK_GRND: tarjeta BACKGRND (valores de fondo que varían en el tiempo, o fichero horario con HOURLY), por sector si hay BGSECTOR. | AERMOD `BACK_GRND` (soset.f) |
| `bgfill(e)` | BGFILL: guarda los valores de fondo de la tarjeta en BACKGRND(:, IBGSECT). | AERMOD `BGFILL` (soset.f) |
| `back_unit(e)` | BACK_UNIT: unidades de los valores de fondo. | AERMOD `BACK_UNIT` (soset.f) |
| `bgsector(e)` | BGSECTOR: límites de los sectores (hacia donde sopla el viento) del fondo variable. | AERMOD `BGSECTOR` (soset.f) |
| `emunit(e)` | EMUNIT: factor y etiquetas de unidades de emisión y salida. | AERMOD `EMUNIT` (soset.f) |
| `counit(e)` | COUNIT: factor y etiquetas de unidades de concentración. | AERMOD `COUNIT` (soset.f) |
| `dpunit(e)` | DPUNIT: factor y etiquetas de unidades de los depósitos (DEPOUNIT). Se aplica a los NTYP tipos (o del 2 en adelante si se calcula también CONC). | AERMOD `DPUNIT` (soset.f) |
| `partdep(e)` | PARTDEP: parámetros de deposición de partículas (PARTDIAM, MASSFRAX, PARTDENS). | AERMOD `PARTDEP` (soset.f) |
| `_error_npd(e, m)` | — | auxiliar de la traducción |
| `_inppdm_fuente(e, m, isdx, rango)` | Diámetros de una fuente (INPPDM). | auxiliar de la traducción |
| `inppdm(e)` | INPPDM: diámetros de las categorías de tamaño de partícula (PARTDIAM). | AERMOD `INPPDM` (soset.f) |
| `_inpphi_fuente(e, m, isdx, rango)` | Fracciones másicas de una fuente (INPPHI). | auxiliar de la traducción |
| `inpphi(e)` | INPPHI: fracciones másicas de cada categoría de tamaño (MASSFRAX). | AERMOD `INPPHI` (soset.f) |
| `_inppdn_fuente(e, m, isdx, rango)` | Densidades de una fuente (INPPDN). | auxiliar de la traducción |
| `inppdn(e)` | INPPDN: densidad de las partículas de cada categoría (PARTDENS). | AERMOD `INPPDN` (soset.f) |
| `_gasdep_fuente(e, m, isdx, aviso)` | — | auxiliar de la traducción |
| `gasdep(e)` | GASDEP: parámetros de deposición de gases (GASDEPOS): difusividad en aire y en agua, resistencia cuticular y constante de Henry. | AERMOD `GASDEP` (soset.f) |
| `_meth_2_valores(e, m, isdx, rango)` | Campos de METHOD_2 de una fuente. | auxiliar de la traducción |
| `meth_2(e)` | METH_2: deposición de partículas por el método 2 (METHOD_2): fracción fina (< 2,5 micras) y diámetro medio másico; una sola categoría con fracción 1 y densidad 1. | AERMOD `METH_2` (soset.f) |
| `vdp1(e)` | VDP1: cálculos de la deposición que no dependen de la hora (tras SETUP): paso a unidades SI de los parámetros de los gases y, para las partículas, factor de corrección de Cunningha… | AERMOD `VDP1` (soset.f) |
| `sogrp(e)` | SOGRP: grupos de fuentes (SRCGROUP). | AERMOD `SOGRP` (soset.f) |
| `asngrp(inid, lowid, higid)` | ASNGRP: ¿está el identificador dentro del rango LOWID-HIGID? | AERMOD `ASNGRP` (soset.f) |
| `setidg(inid)` | SETIDG: divide un identificador en (prefijo de letras, número, sufijo). | AERMOD `SETIDG` (soset.f) |
| `locate(parray, lvlblw, lvlabv, value)` | LOCATE (iblval.f): índice del nivel inmediatamente inferior (búsqueda binaria). | AERMOD `LOCATE` (iblval.f) |
| `_suma_sse2(t)` | Suma de una reducción tal como la vectoriza el exe (2 carriles SSE2): | auxiliar de la traducción |
| `srcqa(e)` | SRCQA: control de calidad de las fuentes al terminar la vía SO. | AERMOD `SRCQA` (soset.f) |
| `_qa_fondo(e, m)` | Final de SRCQA: valores de fondo completos por sector y unidades por defecto. | auxiliar de la traducción |

### `entrada_meteo.py`

vía ME (meset.f).

| Función | Definición | Equivale a |
|---|---|---|
| `mecard(e)` | MECARD: claves de la vía ME. | AERMOD `MECARD` (meset.f) |
| `_fichero(e, m, attr)` | — | auxiliar de la traducción |
| `surfil(e)` | SURFIL: fichero de superficie (.sfc). | AERMOD `SURFIL` (meset.f) |
| `profil(e)` | PROFIL: fichero de perfiles (.pfl). | AERMOD `PROFIL` (meset.f) |
| `cent_date(e, x)` | CENT_DATE con los dos argumentos asociados a la MISMA variable (como la llama el original): | AERMOD `CENT_DATE` (meset.f) |
| `_estacion(e, m, attr_id, attr_yr, attr_nom, attr_x, attr_y, cero_si_error)` | — | auxiliar de la traducción |
| `sfdata(e)` | SFDATA: estación de superficie (SURFDATA). | AERMOD `SFDATA` (meset.f) |
| `uadata(e)` | UADATA: estación de altura (UAIRDATA). | AERMOD `UADATA` (meset.f) |
| `ondata(e)` | ONDATA: estación local (SITEDATA). | AERMOD `ONDATA` (meset.f) |
| `prbase(e)` | PRBASE: cota base del perfil de temperatura potencial (PROFBASE). | AERMOD `PRBASE` (meset.f) |
| `staend(e)` | STAEND: periodo de cálculo (STARTEND). | AERMOD `STAEND` (meset.f) |
| `wdrota(e)` | WDROTA: rotación de la dirección del viento (WDROTATE). | AERMOD `WDROTA` (meset.f) |
| `wscats(e)` | WSCATS: límites de las categorías de velocidad del viento (WINDCATS). | AERMOD `WSCATS` (meset.f) |
| `numyr(e)` | NUMYR: número de años de meteorología (NUMYEARS). | AERMOD `NUMYR` (meset.f) |
| `_abierto(e, nombre)` | — | auxiliar de la traducción |
| `meopen(e)` | MEOPEN: abre los ficheros meteorológicos, lee la cabecera del .sfc y el primer perfil. | AERMOD `MEOPEN` (meset.f) |
| `_cabecera_sfc(e, m, buf)` | Parte de MEOPEN que interpreta la cabecera del .sfc (versión, opciones, estaciones). | auxiliar de la traducción |
| `dcdlat(e)` | DCDLAT (aermod.f): latitud de la cabecera del .sfc. | AERMOD `DCDLAT` (aermod.f) |
| `dayrng(e)` | DAYRNG: días y rangos de días que se procesan (DAYRANGE): días julianos sueltos (n), rangos (n1-n2) y fechas mes/día sueltas o en rango, con el año ISYEAR de SURFDATA. | AERMOD `DAYRNG` (meset.f) |

### `entrada_no2.py`

entrada de las opciones de química del NO2 (OLM, PVMRM, ARM2, TTRM, GRSM y PSDCREDIT).

| Función | Definición | Equivale a |
|---|---|---|
| `cocard(e, k)` | Ramas de COCARD de las claves del NO2. | AERMOD `COCARD` (coset.f) |
| `_sector_simple(e, m, nombre, nsect)` | Sector de los campos 3 (SECT1..SECT6) sin comprobar el número de sectores (O3VAL/NOXVAL). | auxiliar de la traducción |
| `_sector(e, m, nombre, nsects)` | Sector del campo 3 comprobando que exista (O3FILE, O3VALS, NOXFILE, NOXVALS). | auxiliar de la traducción |
| `_valor_fondo(e, m, sector_on, lval, back, nombre_sect, aviso_unid, attr_unid, attr_sect, conv)` | Parte común de O3VAL y NOXVAL. | auxiliar de la traducción |
| `o3val(e)` | O3VAL: ozono de fondo constante (OZONEVAL), por sector si hay O3SECTOR. | AERMOD `O3VAL` (coset.f) |
| `noxval(e)` | NOXVAL: NOx de fondo constante (NOXVALUE), por sector si hay NOXSECTR. | AERMOD `NOXVAL` (coset.f) |
| `_fichero(e, m, sector_on, nsects, nombre_sect)` | Parte común de O3FILE y NOXFILE. | auxiliar de la traducción |
| `_formato(e, m, i, isect, formas)` | Formato del fichero horario (campo I+2) con la cuenta de descriptores de O3FILE/NOXFILE. | auxiliar de la traducción |
| `o3file(e)` | O3FILE: fichero horario de ozono (OZONEFIL). | AERMOD `O3FILE` (coset.f) |
| `noxfile(e)` | NOXFILE: fichero horario de NOx (NOX_FILE). | AERMOD `NOXFILE` (coset.f) |
| `no2eq(e)` | NO2EQ: razón NO2/NOx de equilibrio (NO2EQUIL). | AERMOD `NO2EQ` (coset.f) |
| `no2stk(e)` | NO2STK: razón NO2/NOx en chimenea por defecto para todas las fuentes (NO2STACK). | AERMOD `NO2STK` (coset.f) |
| `_arm2_rango(e, m, v, nombre)` | — | auxiliar de la traducción |
| `arm2_ratios(e)` | ARM2_Ratios: razones mínima y máxima de ARM2 (ARMRATIO). | AERMOD `ARM2_RATIOS` (coset.f) |
| `_valores_variables(e, m, sector_on, nsects, nombre_sect, lvals, imax, flags, err_flag, nombre_flag, attr_sect)` | Parte común de O3VALS y NOXVALS. | auxiliar de la traducción |
| `_rellenar(e, m, sector_on, isect, iset_arr, imax, vary, d_sect, d_simple)` | O3FILL / NOXFILL: guarda los valores de la tarjeta en VARY(:, ISECT). | AERMOD `O3FILL` (coset.f) |
| `o3vals(e)` | O3VALS: ozono de fondo que varía en el tiempo (O3VALUES). | AERMOD `O3VALS` (coset.f) |
| `noxvals(e)` | NOXVALS: NOx de fondo que varía en el tiempo (NOX_VALS). | AERMOD `NOXVALS` (coset.f) |
| `_unidad(e, m, attr, nombre)` | — | auxiliar de la traducción |
| `ozon_unit(e)` | OZON_UNIT: unidades de O3VALUES (OZONUNIT). | AERMOD `OZON_UNIT` (coset.f) |
| `nox_unit(e)` | NOX_UNIT: unidades de NOX_VALS (NOX_UNIT). | AERMOD `NOX_UNIT` (coset.f) |
| `_sectores(e, m, sect, attr_l, attr_n, pre, pre_cmp, f_rango, lim_alto, lim_bajo)` | Parte común de O3SECTOR y NOXSECTOR. | auxiliar de la traducción |
| `o3sector(e)` | O3SECTOR: límites de los sectores del ozono de fondo. | AERMOD `O3SECTOR` (coset.f) |
| `noxsector(e)` | NOXSECTOR: límites de los sectores del NOx de fondo. | AERMOD `NOXSECTOR` (coset.f) |
| `finished_ozono(e, m)` | Comprobaciones de FINISHED de CO para OLM/PVMRM/TTRM/GRSM y ARM2 (tras RUNORNOT). | — |
| `finished_completos(e, m)` | FINISHED de CO: comprobación de que los datos de ozono y NOx de fondo estén completos. | — |
| `socard(e, k, orden_grupo)` | Ramas de SOCARD de NO2RATIO, OLMGROUP y PSDGROUP. | AERMOD `SOCARD` (soset.f) |
| `no2rat(e)` | NO2RAT: razón NO2/NOx en chimenea de una fuente o de un rango de fuentes (NO2RATIO). | AERMOD `NO2RAT` (soset.f) |
| `olmgrp(e)` | OLMGRP: grupos de fuentes que se combinan en OLM (OLMGROUP). | AERMOD `OLMGRP` (soset.f) |
| `psdgrp(e)` | PSDGRP: grupos de fuentes del cálculo de incremento PSD con créditos (PSDGROUP). | AERMOD `PSDGRP` (soset.f) |
| `srcqa_psd(e, m)` | SRCQA con PSDCREDIT: grupos NAAQS y PSDINC y fuentes sin PSDGROUP. | AERMOD `SRCQA` (soset.f) |
| `srcqa_no2(e, m)` | Final de SRCQA: fuentes en varios OLMGROUP/PSDGROUP y datos de las opciones del NO2. | — |
| `srcqa_no2_final(e, m)` | SRCQA: PSDGROUP repetidos, emisiones negativas y razones NO2/NOx sin definir. | AERMOD `SRCQA` (soset.f) |

### `entrada_receptores.py`

vía RE (reset.f).

| Función | Definición | Equivale a |
|---|---|---|
| `recard(e)` | RECARD: claves de la vía RE. | AERMOD `RECARD` (reset.f) |
| `reelun(e)` | REELUN: unidades de la cota de los receptores. | AERMOD `REELUN` (reset.f) |
| `_id_red(e, m, claves)` | Identificador de red y tipo de línea (común a RECART y REPOLR). | auxiliar de la traducción |
| `_sta(e, m)` | — | auxiliar de la traducción |
| `_fin_red(e, m)` | Comprobaciones comunes al END de una red (cotas, alturas de colina y de receptor). | auxiliar de la traducción |
| `recart(e)` | RECART: red cartesiana (GRIDCART). | AERMOD `RECART` (reset.f) |
| `_isc(e, clave)` | — | auxiliar de la traducción |
| `gencar(e)` | GENCAR: red cartesiana a partir de origen, número de puntos e incremento. | AERMOD `GENCAR` (reset.f) |
| `_lista_coord(e, m, clave, cuenta, coord, lim, nomlim, polar)` | XPNTS/YPNTS/DIST/DDIR: lista de coordenadas que se añade a la red. | auxiliar de la traducción |
| `xypnts(e)` | XYPNTS: red cartesiana a partir de listas de X e Y. | AERMOD `XYPNTS` (reset.f) |
| `_volcar_z(e, m, tmp1, tmp2, n, irz, dest, cod)` | SBYVAL + copia de las cotas/alturas ordenadas por fila (parte común de SETCAR y SETPOL). | AERMOD `SBYVAL` (reset.f) |
| `_malla(e, m, polar)` | — | auxiliar de la traducción |
| `setcar(e)` | SETCAR: receptores de una red cartesiana. | AERMOD `SETCAR` (reset.f) |
| `setpol(e)` | SETPOL: receptores de una red polar. | AERMOD `SETPOL` (reset.f) |
| `repolr(e)` | REPOLR: red polar (GRIDPOLR). | AERMOD `REPOLR` (reset.f) |
| `polorg(e)` | POLORG: origen de una red polar (coordenadas o identificador de fuente). | AERMOD `POLORG` (reset.f) |
| `genpol(e)` | GENPOL: direcciones de una red polar a partir de inicial e incremento. | AERMOD `GENPOL` (reset.f) |
| `_hgt(e, clave, m)` | TERHGT/HILHGT/FLGHGT: cotas, alturas de colina o de receptor de una fila de la red. | AERMOD `TERHGT` (reset.f) |
| `_avisos_disc(e, m, base)` | Avisos por número de campos de DISCCART (base=4) y DISCPOLR (base=5). | auxiliar de la traducción |
| `_cotas_disc(e, m, base, i3, i4, i5)` | Cota, colina y altura de receptor opcionales de DISCCART/DISCPOLR. | auxiliar de la traducción |
| `_lleno(e, m, i1, i2, i3, i4, i5)` | — | auxiliar de la traducción |
| `discar(e)` | DISCAR: receptor cartesiano discreto (DISCCART). | AERMOD `DISCAR` (reset.f) |
| `dispol(e)` | DISPOL: receptor polar discreto (DISCPOLR) respecto a una fuente. | AERMOD `DISPOL` (reset.f) |
| `sbyval(a1, a2, inx)` | SBYVAL: ordena (por selección) a1 y arrastra a2, de 1 a inx. | AERMOD `SBYVAL` (reset.f) |
| `evcart(e)` | EVCART: receptor discreto de evaluación (EVALCART). | AERMOD `EVCART` (reset.f) |

### `entrada_salidas.py`

vía OU (ouset.f).

| Función | Definición | Equivale a |
|---|---|---|
| `oucard(e)` | OUCARD: claves de la vía OU. | AERMOD `OUCARD` (ouset.f) |
| `outqa(e)` | OUTQA: control de calidad de las opciones de salida. | AERMOD `OUTQA` (ouset.f) |
| `_periodo(e, m, campo, ilen)` | Periodo de promedio de un campo (o MONTH). | auxiliar de la traducción |
| `_grupo(e, m, campo)` | — | auxiliar de la traducción |
| `_nombre(e, campo)` | Nombre de fichero (con mayúsculas y minúsculas) del campo, o None si es demasiado largo. | auxiliar de la traducción |
| `_unidad(e, m, campo, nombre, dinamica)` | Unidad del fichero: la del campo opcional (con la comprobación de FUNITARRAY) o la siguiente dinámica (FUNITINX). Devuelve None si el campo no es numérico. | auxiliar de la traducción |
| `_registrar(e, unidad, nombre, tipo)` | — | auxiliar de la traducción |
| `_duplicado(e, m, nombre, unidad, otros)` | Mismo fichero con otra unidad, o misma unidad con otro fichero -> error 550 (False). | auxiliar de la traducción |
| `_reanudar(e, m, unidad, nombre, dummy, tipo, col, cod, ajustar_hora)` | Re-arranque (RSTINP): abre el fichero existente y lo posiciona tras su último registro con fecha anterior o igual a la del INITFILE (col = columnas de la fecha; None: POSTFILE sin … | auxiliar de la traducción |
| `_abrir(e, m, unidad, nombre, tipo, prefijo, binario)` | — | auxiliar de la traducción |
| `ouhigh(e)` | OUHIGH: tablas de valores altos por receptor (RECTABLE). | AERMOD `OUHIGH` (ouset.f) |
| `oumxvl(e)` | OUMXVL: tabla de máximos globales (MAXTABLE). | AERMOD `OUMXVL` (ouset.f) |
| `oudaly(e)` | OUDALY: tablas de valores diarios (DAYTABLE). | AERMOD `OUDALY` (ouset.f) |
| `_cabecera(e, unidad, t9007)` | Dos primeras líneas comunes de las cabeceras de MAXIFILE y POSTFILE. | auxiliar de la traducción |
| `oumxfl(e)` | OUMXFL: fichero de valores que superan un umbral (MAXIFILE). | AERMOD `OUMXFL` (ouset.f) |
| `oupost(e)` | OUPOST: ficheros de valores concurrentes (POSTFILE). | AERMOD `OUPOST` (ouset.f) |
| `_hdr_post(e)` | Las dos líneas de títulos de columnas del POSTFILE (formato HDRFRM del original). | auxiliar de la traducción |
| `ouplot(e)` | OUPLOT: ficheros de valores altos por receptor para gráficos (PLOTFILE). | AERMOD `OUPLOT` (ouset.f) |
| `perpst(e)` | PERPST: POSTFILE de los promedios del periodo. | AERMOD `PERPST` (ouset.f) |
| `perplt(e)` | PERPLT: PLOTFILE de los promedios del periodo. | AERMOD `PERPLT` (ouset.f) |
| `ouseas(e)` | OUSEAS: fichero de promedios por estación y hora del día (SEASONHR). | AERMOD `OUSEAS` (ouset.f) |
| `ourank(e)` | OURANK: fichero de valores ordenados (RANKFILE). | AERMOD `OURANK` (ouset.f) |
| `outoxx(e)` | OUTOXX: ficheros sin formato para el modelo TOXX (TOXXFILE). | AERMOD `OUTOXX` (ouset.f) |
| `oumaxdly(e, byyr)` | OUMAXDLY / OUMXDLY_BYYR: ficheros de máximos diarios por día (MAXDAILY) o de los máximos diarios ordenados de cada año (MXDYBYYR) de un grupo de fuentes. | AERMOD `OUMAXDLY` (ouset.f) |
| `oumaxd_cont(e)` | OUMAXD_CONT: contribución de cada grupo a los máximos diarios (MAXDCONT) de un grupo, para un intervalo de rangos o hasta un umbral (THRESH). | AERMOD `OUMAXD_CONT` (ouset.f) |
| `ousumm(e)` | OUSUMM: fichero de resumen (SUMMFILE). | AERMOD `OUSUMM` (ouset.f) |
| `fileform(e)` | FILEFORM: formato fijo o exponencial de los ficheros de resultados. | AERMOD `FILEFORM` (ouset.f) |
| `noheader(e)` | NOHEADER: suprime las cabeceras de los ficheros de salida. | AERMOD `NOHEADER` (ouset.f) |

### `estado.py`

estado global y servicios comunes.

| Función | Definición | Equivale a |
|---|---|---|
| `class Parada` | STOP del original: el programa termina sin pasar por el final normal. | — |
| `class NoTraducido` | Opción del original fuera del alcance de la traducción. | — |
| `_dim(d)` | — | auxiliar de la traducción |
| `crear(tipo, dims, lon, val)` | Matriz de un tipo Fortran con índices 1..dims (posición 0 sin usar en cada dimensión). | — |
| `class Salida` | Fichero formateado de salida (Intel en Windows: | — |
| `class SalidaBin` | Fichero secuencial SIN FORMATO de Intel: | — |
| `class SalidaReanudada` | Fichero formateado existente posicionado tras sus primeros `nbytes` (BACKSPACE tras leerlo en un re-arranque): | — |
| `class SalidaBinReanudada` | Fichero sin formato existente posicionado tras sus primeros `nbytes` (ver SalidaReanudada). | — |
| `class EntradaBin` | Fichero secuencial SIN FORMATO de entrada (registros de Intel entre marcas de longitud), con REWIND. | — |
| `class Pantalla` | Unidad * (pantalla). | — |
| `class Entrada` | Fichero formateado de entrada: | — |
| `_iniciar(obj, decl, data, params)` | Crea las variables de un módulo Fortran (declaraciones y valores iniciales) en `obj`. | auxiliar de la traducción |
| `class Prime` | Variables de los módulos de PRIME (PRIME_PARAMS, NUMPARM, DFSN, WAKEDAT, AMBIENT, PLU y PRM2_WAKEDAT), en su propio espacio porque varias coinciden en nombre con las de MAIN1. | — |
| `class Estado` | — | — |
| `fmod_fortran(a, b)` | MOD de enteros de Fortran: | — |
| `idiv(a, b)` | División entera de Fortran (trunca hacia cero). | — |

### `estela_edificio.py`

algoritmo PRIME de downwash por edificios (prime.f). Las variables de sus módulos están en ``e.P``.

| Función | Definición | Equivale a |
|---|---|---|
| `prime1(e)` | PRIME1: constantes de la difusión en la estela. | AERMOD `PRIME1` (prime.f) |
| `numpr1(e)` | NUMPR1: constantes de la sobreelevación numérica y malla meteorológica de PRIME. | AERMOD `NUMPR1` (prime.f) |
| `_rpot0(base, expo)` | Potencia real ``base**expo`` como el Fortran: | auxiliar de la traducción |
| `_dsqrt(x)` | DSQRT con argumento posiblemente negativo: | auxiliar de la traducción |
| `numrise(e, ldbhr, h, reff, texit, wexit, ntr, capped, horiz, capfact, xtr, ytr, ztr, rtr, dbgunt)` | NUMRISE: sobreelevación numérica (ecuaciones no Boussinesq) con difusión en la estela y fracción capturada por la cavidad. | AERMOD `NUMRISE` (prime.f) |
| `rate(e, ua, dudz, ra, dpdz, ta, drdxa, rhs)` | RATE: segundos miembros de las ecuaciones (rhs[1..7], en su sitio). Devuelve DRDXA (el original lo anula si hay coeficientes de arrastre perturbados y X queda fuera de XCAT). | AERMOD `RATE` (prime.f) |
| `lump(e, ua, ta, f)` | LUMP: variables agrupadas f[1..7] (en su sitio). | AERMOD `LUMP` (prime.f) |
| `marching(fold, fnew, rhs, ds)` | MARCHING: un paso en S (predictor o corrector); fnew en su sitio. Sin globales. | AERMOD `MARCHING` (prime.f) |
| `unlump(e, ua, ta, ra, f)` | UNLUMP: variables físicas de PRIME_PLU a partir de las agrupadas. | AERMOD `UNLUMP` (prime.f) |
| `zmet(e, z)` | ZMET: meteorología a la altura z a partir de los perfiles de AERMOD. Devuelve ``(ua, ra, tap, dudz, dpdz)``. | AERMOD `ZMET` (prime.f) |
| `zstream(h, w, l, r, lr, hr, x, y, z)` | ZSTREAM: pendiente media local de las líneas de corriente junto al edificio (DZDX). Sin globales. | AERMOD `ZSTREAM` (prime.f) |
| `position(e, x, y, z)` | POSITION: 1 dentro del edificio, 2 en la estela cercana, 3 en la lejana, 4 fuera. Devuelve IPOSITN. | AERMOD `POSITION` (prime.f) |
| `numgrad(x, xtr, ztr, ntr)` | NUMGRAD: altura efectiva gradual por interpolación en la tabla (ZEFF). Sin globales. | AERMOD `NUMGRAD` (prime.f) |
| `wake_drdx(e, x)` | WAKE_DRDX: ritmo de crecimiento del radio del penacho en la estela (DRDX). | AERMOD `WAKE_DRDX` (prime.f) |
| `wake_ini(e, kurdat, ldbhr, dbgunt, rural, dsbh, dsbw, dsbl, xadj, yadj, ubldg, ustack)` | WAKE_INI: refresca las variables de PRIME_WAKEDAT (edificio, escalas de la estela y tablas reiniciadas). Fija THIRD, LRURL, HB, WB, XLB, XBADJ, YBADJ, UB, URH, RB, HR, XLR, XLC, NW… | AERMOD `WAKE_INI` (prime.f) |
| `wake_scales(e, kurdat, ldbhr, dbgunt)` | WAKE_SCALES: escala de longitud RB y dimensiones de la cavidad (HR, XLR, XLC). Sin edificio (HB <= 0) anula RB, HB, XLR y XLC y deja HR como estaba (igual que el original). | AERMOD `WAKE_SCALES` (prime.f) |
| `_tablas_estela(e, lwak, lcav, np_, nws, ncs, xi, szi, syi, xbc, szcav0, sycav0, dist, asigz, asigy, dsz, csigz, csigy)` | Construcción de las tablas de PRIME_WAKEDAT (bloque idéntico al final de WAKE_DFSN y de WAKE_DFSN2): | auxiliar de la traducción |
| `wake_dfsn(e, ldbhr, xi, szi, syi, z, dbgunt)` | WAKE_DFSN: tabula sigmas y crecimiento del penacho en la estela (Weil 1996 modificado) para la fuente principal y la de la cavidad. xi: distancia desde la cara de barlovento al pun… | AERMOD `WAKE_DFSN` (prime.f) |
| `wake_dfsn2(e, ldbhr, xi, szi, syi, xtr, ztr, ntr, dbgunt)` | WAKE_DFSN2: como WAKE_DFSN pero con la trayectoria completa (xtr, ztr; índices 1..ntr) para las alturas de SIGYPR/SIGZPR y las sigmas de las fuentes virtuales; incluye la opción OR… | AERMOD `WAKE_DFSN2` (prime.f) |
| `wake_turb(e, xinp, l, rinp)` | WAKE_TURB: intensidades de turbulencia en la estela a la distancia xinp desde la cara de barlovento (l: distancia a la cara de sotavento; rinp: escala R). Devuelve ``(tiz, tiy)``. … | AERMOD `WAKE_TURB` (prime.f) |
| `wake_u(e, ldb, x, y, z, dbgunt)` | WAKE_U: cociente de velocidades u(estela)/u(ambiente) en (x, y, z) relativos a la cara de barlovento. Devuelve ``(ubyua, dufac)``. | AERMOD `WAKE_U` (prime.f) |
| `wake_u_turb(e, scope, xinp, znew, ambiz, ambiy)` | WAKE_U_TURB (AWMADWNW): déficit de velocidad y, con scope 'turb', intensidades de turbulencia en la estela. Devuelve ``(du_ua, tiz, tiy)``; con scope 'vel' tiz y tiy son None (el o… | AERMOD `WAKE_U_TURB` (prime.f) |
| `wake_xa(e, l, rinp)` | WAKE_XA: distancias desde la cara de barlovento a las que la turbulencia de la estela iguala la ambiental, limitadas a XBYRMAX escalas R. Devuelve ``(xaz, xay)``. | AERMOD `WAKE_XA` (prime.f) |
| `wake_xa2(e, l, rinp)` | WAKE_XA2: como WAKE_XA pero sin limitar a XBYRMAX escalas R. Devuelve ``(xaz, xay)``. | AERMOD `WAKE_XA2` (prime.f) |
| `wake_dim(x, h, w, r)` | WAKE_DIM: altura y semianchura de la estela a la distancia x de la cara de barlovento. Devuelve ``(hwake, wwake)``. Sin globales (THIRD es local). | AERMOD `WAKE_DIM` (prime.f) |
| `wake_sig(x, xd, xold, turbz, turby, szold, syold, h, w, r, zk, yk)` | WAKE_SIG: sigmas y d(sigma)/dx en la estela al final de un paso pequeño. zk, yk son de entrada/salida (constantes de la transición FDP → difusividad). Devuelve ``(zk, yk, sz, sy, d… | AERMOD `WAKE_SIG` (prime.f) |
| `wake_dbg(e, io, ntr, xtr, ytr, ztr, rtr, nobid, hstack)` | WAKE_DBG: informe de depuración de PRIME (DEBUGOPT PRIME) a la unidad io. Además de las escrituras tiene efectos laterales (WAKE_XSIG → SIGYPR/SIGZPR fijan SYAMB, SZAMB, SZAS, SZSU… | AERMOD `WAKE_DBG` (prime.f) |
| `wake_cav0(e, sycapt)` | WAKE_CAV0: sigmas iniciales de la fuente situada en el suelo de la cavidad. sycapt: sigma-y del penacho donde la cavidad captura la masa. Devuelve ``(szcav0, sycav0)``. | AERMOD `WAKE_CAV0` (prime.f) |
| `cav_src(e, xr, yr, zr, qc, hc, yrc, zrc, szc, syc)` | CAV_SRC: datos de las fuentes de la cavidad para un receptor (xr, yr, zr relativos a la chimenea). Rellena en su sitio qc, hc, yrc, zrc, szc, syc (índices 1..3; el 1 es de la fuent… | AERMOD `CAV_SRC` (prime.f) |
| `wake_fqc(e, ldb, xbi, xtr, ztr, ntr, dbgunt)` | WAKE_FQC: fracción máxima de la masa del penacho capturada por la cavidad (FQCAV). xbi: distancia desde la cara de barlovento a la entrada en la estela; xtr, ztr: trayectoria (índi… | AERMOD `WAKE_FQC` (prime.f) |
| `frgauss(hcntr, sigma, h1, h2)` | FRGAUSS: fracción de una distribución gaussiana entre h1 y h2 (FRACT). Sin globales. | AERMOD `FRGAUSS` (prime.f) |
| `erfdif(x1, x2)` | ERFDIF (FUNCTION): erf(x1) - erf(x2) evitando errores de redondeo. Sin globales. | AERMOD `ERFDIF` (prime.f) |
| `fnerf(xx)` | FNERF (FUNCTION): función de error, aproximación de Hastings. Sin globales. | AERMOD `FNERF` (prime.f) |
| `fnerfc(xx)` | FNERFC (FUNCTION): función de error complementaria (Hastings, con la expresión asintótica para x grande). Sin globales. | AERMOD `FNERFC` (prime.f) |
| `wake_xsig(e, x, hstk, rise, nobid)` | WAKE_XSIG: sigmas en la estela por interpolación en las tablas, o con las curvas ambientales (BID o fuente virtual) fuera de ellas. x: distancia desde la fuente; hstk: altura físic… | AERMOD `WAKE_XSIG` (prime.f) |
| `cavity_ht(h, w, l, r, lc, lr, hr, x)` | CAVITY_HT: altura y semianchura de la envolvente de la cavidad en x. Devuelve ``(zcav, ycav)``. Sin globales. | AERMOD `CAVITY_HT` (prime.f) |
| `sigypr(e, xarg, zarg)` | SIGYPR: sigma-y ambiental para PRIME. Fija e.SYAMB y devuelve SYOUT (= SYAMB; si no es ni estable ni inestable, el SYAMB previo, como el original). | AERMOD `SIGYPR` (prime.f) |
| `sigzpr(e, xarg, zarg, szout)` | SIGZPR: sigma-z ambiental para PRIME. Devuelve SZOUT. En estable fija e.SZAMB, e.SZAS (y e.SZSURF vía SZSFCLPR); en inestable, e.SZSURF. Si no es ni estable ni inestable el origina… | AERMOD `SIGZPR` (prime.f) |
| `szsfclpr(e, xarg, zarg)` | SZSFCLPR: término de capa superficial de sigma-z para PRIME (fija e.SZSURF). Solo usa MAIN1: THIRD es e.THIRD. | AERMOD `SZSFCLPR` (prime.f) |

### `fondo.py`

concentraciones de fondo (BACKGRND): BGEXT de aermod.f (lectura del fichero horario de fondo) y el paso horario de HRLOOP.

| Función | Definición | Equivale a |
|---|---|---|
| `_leer(e, i, tipos)` | READ(IBGUNT(I),*) o READ(IBGUNT(I),BGFORM(I)). | auxiliar de la traducción |
| `bgext(e)` | BGEXT: valor de fondo de la hora desde el fichero horario del sector en curso (los ficheros de los demás sectores se leen para mantenerlos sincronizados); si falta, se sustituye po… | AERMOD `BGEXT` (aermod.f) |
| `fondo_hora(e)` | Paso de HRLOOP para el fondo: | — |

### `formato.py`

Compatibilidad de E/S y numérica con el Fortran de AERMOD 26135 (US EPA, dominio público).

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
| `fc(s, n)` | Asignación a CHARACTER*n en forma canónica: | — |
| `lw()` | WRITE(u,*) dirigido por lista (Intel): | — |
| `_ld_real(x, dbl)` | Número real en la escritura dirigida por lista de Intel: | auxiliar de la traducción |
| `lwrite()` | WRITE(u,*) dirigido por lista de Intel. | — |
| `trim(s)` | — | — |
| `len_trim(s)` | — | — |
| `stodbl(s, length, previo)` | STODBL (setup.f): número en DOUBLE leído dígito a dígito (CNUM = CNUM*10 + d; decimales con FDEC = FDEC/10), signo, repetición «n*valor» y exponente E o D, que SOLO se admite despu… | AERMOD `STODBL` (setup.f) |
| `stonum(s, length, previo)` | STONUM (setup.f): como STODBL pero en REAL (precisión simple, cada operación redondeada a simple como en SSE) y con exponente solo E. Devuelve (valor float, imuti). | AERMOD `STONUM` (setup.f) |

### `fuente_carretera.py`

fuentes de carretera RLINE y RLINEXT.

| Función | Definición | Equivale a |
|---|---|---|
| `class RlineDatos` | Variables del módulo RLINE_DATA con su valor inicial (memoria estática: | — |
| `_delegada(nombre)` | — | auxiliar de la traducción |
| `reservar(e)` | Reserva de ALLSETUP (aermod.f) para RLINE: | — |
| `_div(a, b)` | División IEEE (±Inf o NaN al dividir por cero). | auxiliar de la traducción |
| `_sqrt(x)` | DSQRT IEEE (NaN para negativos). | auxiliar de la traducción |
| `_log(x)` | DLOG IEEE (-Inf en 0, NaN para negativos). | auxiliar de la traducción |
| `_exp(x)` | DEXP IEEE (+Inf si desborda). | auxiliar de la traducción |
| `_pow(x, y)` | x**y con exponente real como el Fortran (pow de C): | auxiliar de la traducción |
| `_acos(x)` | DACOS IEEE (NaN fuera de [-1, 1]). | auxiliar de la traducción |
| `_modulo(a, p)` | MODULO real: resto con el signo de P. | auxiliar de la traducción |
| `_i4(x)` | INT() de un real a INTEGER*4 (truncamiento, conversión de x86). | auxiliar de la traducción |
| `_floor_i4(x)` | FLOOR() de un real a INTEGER*4. | auxiliar de la traducción |
| `_ceiling_i4(x)` | CEILING() de un real a INTEGER*4. | auxiliar de la traducción |
| `_i32(n)` | Aritmética entera de 32 bits con desbordamiento cíclico. | auxiliar de la traducción |
| `_rad(y)` | y grados (/y/ <= 45) → (a, b) con a + b ≈ y*pi/180. | auxiliar de la traducción |
| `_sin_r(y)` | — | auxiliar de la traducción |
| `_cos_r(y)` | — | auxiliar de la traducción |
| `_reducir(x, periodo)` | — | auxiliar de la traducción |
| `_sind(x)` | — | auxiliar de la traducción |
| `_cosd(x)` | — | auxiliar de la traducción |
| `_tand(x)` | — | auxiliar de la traducción |
| `_print(e)` | PRINT * dirigido por lista (Intel): | auxiliar de la traducción |
| `rlcalc(e)` | RLCALC: concentración de la fuente RLINE/RLINEXT ISRC en todos los receptores (suma a los grupos con SUMVAL; con ARM2 la guarda en CHI). | AERMOD `RLCALC` (rline.f) |
| `_alpha_vs(z0, sfcz0)` | Alfa de Venkatram y Schulte (2018): | auxiliar de la traducción |
| `barrier_displacement(e)` | BARRIER_DISPLACEMENT: barreras a barlovento/sotavento de la fuente, distancias a lo largo del viento, alfas y desplazamiento de la fuente por la zona de recirculación. | AERMOD `BARRIER_DISPLACEMENT` (rline.f) |
| `vegbarrierset(e)` | VEGBARRIERSET: barrera vegetal a sotavento de la fuente (altura, distancias, ancho, LAI, densidad foliar y estela). | AERMOD `VEGBARRIERSET` (rline.f) |
| `compute_met(e)` | COMPUTE_MET: sigma-v a la altura de referencia, rugosidades/alfas de los casos sin barrera, barrera a sotavento y a barlovento, tabla de viento, viento mínimo, ajuste a UREF, vient… | AERMOD `COMPUTE_MET` (rline.f) |
| `create_exp_table(e)` | CREATE_EXP_TABLE: tabla de interpolación lineal de la exponencial en [-20, 0]. | AERMOD `CREATE_EXP_TABLE` (rline.f) |
| `create_wind_table(e)` | CREATE_WIND_TABLE: tabla del perfil de viento de Monin-Obukhov (alturas espaciadas en logaritmo) para los tres casos de barrera; pendientes y ordenadas para MOST_WIND. | AERMOD `CREATE_WIND_TABLE` (rline.f) |
| `most_wind(e, z, ia)` | MOST_WIND (FUNCTION): velocidad del viento a la altura Z (caso de barrera IA) por la tabla de CREATE_WIND_TABLE, con el ajuste WSPD_ADJ y el mínimo UMIN. | AERMOD `MOST_WIND` (rline.f) |
| `expx(e, xp)` | EXPX (FUNCTION): exponencial por la tabla de CREATE_EXP_TABLE. | AERMOD `EXPX` (rline.f) |
| `interp_coeffs(e)` | INTERP_COEFFS: coeficientes de interpolación de UEFF, SIGMAY y SIGMAZ (opción FASTALL) a partir de sus valores en x = 1, 10 y 500 m. | AERMOD `INTERP_COEFFS` (rline.f) |
| `effective_wind(e, xd, heff, hshift)` | EFFECTIVE_WIND: viento efectivo a la altura media del penacho (iterativo). Fija ``e.RL.UEFF``. | AERMOD `EFFECTIVE_WIND` (rline.f) |
| `sigmay(e, xd)` | SIGMAY (FUNCTION): dispersión horizontal (usa SIGZ_Y de la última llamada a SIGMAZ). | AERMOD `SIGMAY` (rline.f) |
| `sigmaz(e, xd)` | SIGMAZ (FUNCTION): dispersión vertical con los efectos de la configuración de la fuente (sigma-z inicial, depresión y barrera). Fija ``e.RL.SIGZ_Y``. | AERMOD `SIGMAZ` (rline.f) |
| `depressed_displacement(e, theta_line, ind)` | DEPRESSED_DISPLACEMENT (FUNCTION): | AERMOD `DEPRESSED_DISPLACEMENT` (rline.f) |
| `meander(e, x, y, z, hshift)` | MEANDER (FUNCTION): contribución del punto (X, Y, Z) suponiendo dispersión radial. | AERMOD `MEANDER` (rline.f) |
| `veg_calc(e, xd)` | VEG_CALC: sigma-z y viento efectivo tras una barrera vegetal a sotavento (Hashad et al. 2024). Devuelve (VSZ, VUEFF). | AERMOD `VEG_CALC` (rline.f) |
| `plume_conc(e, xd, yd, z, dwdt, heff, hshift, hbdeff, hbmax)` | PLUME_CONC: penacho directo de un punto (gaussiano o de estela mezclada tras una barrera). XD, HEFF y HSHIFT son de entrada y salida (XD no tiene INTENT en el original y se modific… | AERMOD `PLUME_CONC` (rline.f) |
| `point_conc(e, x, y, z)` | POINT_CONC (FUNCTION): concentración de un punto de la línea en el receptor: penacho directo y meandro, cada uno ponderado entre el estado horizontal (CWRAP) y el que sigue al terr… | AERMOD `POINT_CONC` (rline.f) |
| `polyinterp(xa, ya, x, n)` | POLYINTERP: interpolación polinómica de Neville (Numerical Recipes) en X de la tabla (XA, YA) de N puntos (listas con índices 1..N). Devuelve (Y, ERR). | AERMOD `POLYINTERP` (rline.f) |
| `numerical_line_source(e)` | NUMERICAL_LINE_SOURCE: integral de la línea en el receptor (trapecios sucesivos con extrapolación de Romberg). Devuelve (CONC_NUM, ERR). | AERMOD `NUMERICAL_LINE_SOURCE` (rline.f) |
| `rlemconv(e)` | RLEMCONV: factores de conversión de las unidades de MOVES (g/h/tramo) a las de RLINE (g/m/s) de las fuentes RLINE desde ISRC (1 si no hay RLEMCONV). | AERMOD `RLEMCONV` (rline.f) |
| `translate_rotate(e)` | TRANSLATE_ROTATE: traslada el origen al comienzo de la fuente ISRC y gira las fuentes RLINE (desde ISRC) y los receptores para que el eje x siga al viento; aplica el desplazamiento… | AERMOD `TRANSLATE_ROTATE` (rline.f) |
| `_orden_grupo(e, m)` | — | auxiliar de la traducción |
| `socard(e, k)` | Ramas de SOCARD de RLEMCONV, RBARRIER, SBARRIER, VBARRIER y RDEPRESS. | AERMOD `SOCARD` (soset.f) |
| `soloca_rline(e, m, isrc)` | Rama de SOLOCA de RLINE (campos 5-8: | — |
| `rlparm(e, isdx, temp)` | RLPARM: parámetros de SRCPARAM de las fuentes RLINE (Lnemis, HS, WIDTH[, SZINIT]) y RLINEXT (QEMIS, DCL, WIDTH, SZINIT). TEMP con índices 1.. (TEMP(1) = FIELD(4)). | AERMOD `RLPARM` (soset.f) |
| `_leer_campo(e, m, k, a, idx)` | CALL STODBL(FIELD(k), ILEN_FLD, A(idx), IMIT) con el mensaje 208 si no es numérico (A es una matriz numpy y IDX un índice o una tupla de índices). | auxiliar de la traducción |
| `rlinebar_inputs(e)` | RLINEBAR_INPUTS: barreras sólidas de una fuente RLINEXT (RBARRIER): altura y distancia al eje de una o dos barreras. | AERMOD `RLINEBAR_INPUTS` (soset.f) |
| `vbarrier_inputs(e)` | VBARRIER_INPUTS: barreras vegetales de una fuente RLINEXT (VBARRIER): altura, ancho, distancia al eje, LAI y densidad foliar máxima de una o dos barreras. | AERMOD `VBARRIER_INPUTS` (soset.f) |
| `vbarrier_setup(e)` | VBARRIER_SETUP: estela de las barreras vegetales (se anulan si la fuente tiene barreras sólidas). | AERMOD `VBARRIER_SETUP` (soset.f) |
| `sbarrier_inputs(e)` | SBARRIER_INPUTS: barreras sólidas por segmentos (SBARRIER): registro STA (identificador y número de segmentos), registros de segmento (extremos, altura y cota) y registro END. | AERMOD `SBARRIER_INPUTS` (soset.f) |
| `weight_sum(nseg, weights, var)` | WEIGHT_SUM (FUNCTION): media ponderada de los NSEG segmentos (listas con índices 1..). | AERMOD `WEIGHT_SUM` (soset.f) |
| `sbarrier_dcl(e)` | SBARRIER_DCL: altura y distancia al eje (con signo) efectivas de cada barrera SBARRIER para cada fuente RLINEXT (giro de los segmentos no paralelos, solape con la fuente, huecos) y… | AERMOD `SBARRIER_DCL` (soset.f) |
| `rlinedpr_inputs(e)` | RLINEDPR_INPUTS: vía deprimida de una fuente RLINEXT (RDEPRESS): profundidad y anchos superior e inferior. | AERMOD `RLINEDPR_INPUTS` (soset.f) |
| `barzone(e, bxs, bys, bht, rezone)` | BARZONE (FUNCTION): gira la barrera (extremos BXS, BYS con índices 1..2) al eje x y marca los receptores dentro de su zona de influencia. Devuelve la nueva matriz de zonas. | AERMOD `BARZONE` (reset.f) |
| `baredgezone(e)` | BAREDGEZONE (reset.f): receptores dentro de la zona de influencia de las barreras SBARRIER asociadas a fuentes RLINEXT (REEDGE); avisa si una barrera es demasiado corta. | AERMOD `BAREDGEZONE` (reset.f) |

### `fuente_foso.py`

fuentes OPENPIT (canteras y fosos abiertos).

| Función | Definición | Equivale a |
|---|---|---|
| `_div(a, b)` | División IEEE (±Inf o NaN al dividir por cero). | auxiliar de la traducción |
| `_sqrt(x)` | DSQRT IEEE: NaN para argumentos negativos (o NaN). | auxiliar de la traducción |
| `_pow(x, y)` | x**y real IEEE (exponente no entero): | auxiliar de la traducción |
| `seno_coseno(x)` | (sin x, cos x) correctamente redondeados para un doble x (radianes). | — |
| `_depos(nombre)` | Rutina de deposición del original (VDP, SCAVRAT, PDEP, PDEPG) en calc1, si ya existe. | auxiliar de la traducción |
| `soparm_pit(e, isdx, temp)` | Rama OPENPIT de SOPARM: comprueba el número de campos (8 o 9) y llama a OPARM. TEMP es la lista de valores leídos de los campos 4..IFC (TEMP[1] = campo 4). | — |
| `oparm(e, i, temp)` | OPARM: parámetros de una fuente OPENPIT (emisión por unidad de área, altura de emisión, dimensiones X/Y, volumen y orientación), vértices, ángulo del eje largo, profundidad efectiv… | AERMOD `OPARM` (soset.f) |
| `escape(e, icat)` | ESCAPE: fracción de escape de la categoría de tamaño ICAT. | AERMOD `ESCAPE` (pitarea.f) |
| `adjemi(e, icat, qptot)` | ADJEMI: emisión ajustada de la categoría ICAT. Devuelve QPTOT acumulado. | AERMOD `ADJEMI` (pitarea.f) |
| `amfrac(e, qptot)` | AMFRAC: fracciones másicas ajustadas de todas las categorías. | AERMOD `AMFRAC` (pitarea.f) |
| `ctheta(afvin, alfin)` | CTHETA: ángulo entre la dirección del viento y el eje largo del foso (0..90 grados). | AERMOD `CTHETA` (pitarea.f) |
| `lwind(e)` | LWIND: longitud del foso en la dirección del viento (PITL); fija THETA. | AERMOD `LWIND` (pitarea.f) |
| `pdepth(e)` | PDEPTH: profundidad relativa del foso (PDREL). | AERMOD `PDEPTH` (pitarea.f) |
| `ptfrac(e)` | PTFRAC: fracción del área del foso que ocupa el área efectiva (PITFRA). | AERMOD `PTFRAC` (pitarea.f) |
| `piteff(e)` | PITEFF: vértices del área efectiva del foso (XVERT, YVERT, en coordenadas del usuario), sus dimensiones XEFF, YEFF y su centro XCNTR, YCNTR. | AERMOD `PITEFF` (pitarea.f) |
| `pitemi(e, qptot)` | PITEMI: emisión por unidad de área del área efectiva (QEFF). | AERMOD `PITEMI` (pitarea.f) |
| `geometria(e)` | LWIND, PDEPTH, PTFRAC y PITEFF (la secuencia que repiten OCALC y las rutinas de PVMRM). | AERMOD `LWIND` (pitarea.f) |
| `pnpoly(px, py, x, y, n)` | PNPOLY (aermod.f): -1 si (PX,PY) está fuera del polígono de N vértices X(1..N), Y(1..N); 0 si está en un lado o en un vértice; 1 si está dentro. | AERMOD `PNPOLY` (aermod.f) |
| `ocalc(e)` | OCALC: concentración horaria de una fuente OPENPIT en todos los receptores. | AERMOD `OCALC` (calc1.f) |
| `_deposicion_fuente(e)` | Velocidades de deposición y razones de lavado de la fuente (bloque de OCALC antes del bucle de receptores). | auxiliar de la traducción |
| `_anular(e, aerout, qtksav, ttrm)` | Ramas CYCLE RECEPTOR_LOOP de OCALC: | auxiliar de la traducción |
| `_bucle(e, m, qtksav, aerout)` | Bucle de receptores de OCALC. | auxiliar de la traducción |
| `dentro_pit(e, isrc)` | Receptores (índices 1..NUMREC) dentro del foso real de la fuente ISRC (PNPOLY > 0). | — |
| `_bucle_nucleo(e, qtksav, aerout)` | Bucle de receptores de OCALC con el núcleo compilado del bucle de ACALC (nucleo.py), sin tocarlo. | auxiliar de la traducción |
| `_punto_virtual(e, aerout, qtksav)` | Aproximación de fuente puntual de FASTAREA/FASTALL con el área efectiva del foso (QTK * XEFF * YEFF). | auxiliar de la traducción |
| `prtsrc_pit(e, o, cabecera, iqun)` | Tabla «OPENPIT SOURCE DATA» de PRTSRC (va entre la de trincheras RLINE y la de BUOYLINE). | — |
| `vertices_pit(e, isrc)` | XVM, YVM de CHKREC/OCALC: los 5 vértices del foso real (índices 1..5). | — |
| `_major_cont(e, maxconc, idom)` | MAJOR_CONT con la rama OPENPIT (el resto, como no2._major_cont). | AERMOD `MAJOR_CONT` (calc1.f) |
| `_moles_nox(e, idom)` | MOLES_NOX con la rama OPENPIT (el resto, como no2._moles_nox). | AERMOD `MOLES_NOX` (calc1.f) |
| `pvmrm_bucle(e, srcs, maxchi, domidx)` | Bucle de receptores de PVMRM_CALC (copia en Python de no2._pvmrm_bucle) con las ramas OPENPIT del penacho dominante, MAJOR_CONT y MOLES_NOX. | — |

### `fuente_linea_flotante.py`

fuentes lineales flotantes BUOYLINE (algoritmo adaptado del modelo BLP).

| Función | Definición | Equivale a |
|---|---|---|
| `_div(a, b)` | División IEEE (±Inf o NaN al dividir por cero). | auxiliar de la traducción |
| `_sqrt(x)` | DSQRT IEEE: NaN para argumentos negativos. | auxiliar de la traducción |
| `_pow(x, y)` | x**y real IEEE (exponentes no enteros): | auxiliar de la traducción |
| `_exp(x)` | EXP IEEE: +Inf si desborda (en vez de OverflowError). | auxiliar de la traducción |
| `_log(x)` | DLOG IEEE: -Inf en 0 y NaN para negativos. | auxiliar de la traducción |
| `_acos(x)` | DACOS IEEE: NaN fuera de [-1, 1]. | auxiliar de la traducción |
| `_sy_de_th(xy, th)` | SY = 1000*XY*DSIN(TH)/(2.15*DCOS(TH)) (común a BL_DBTSIG y BL_SIGMAY); | auxiliar de la traducción |
| `_mods()` | Módulos que se importan al usarse (evita importaciones circulares). | auxiliar de la traducción |
| `_alias(nom)` | — | auxiliar de la traducción |
| `class BuoyantLine` | Variables del módulo BUOYANT_LINE (modules.f), con sus valores iniciales: | — |
| `reservar(e)` | ALLSETUP (aermod.f, «Buoyant line allocation», líneas 4273-4331): | AERMOD `ALLSETUP` (aermod.f) |
| `reservar_resultados_bl(e)` | ALLRESULT (aermod.f, rama L_MAXDCONT, línea 5052): | AERMOD `ALLRESULT` (aermod.f) |
| `reservar_maxd(e)` | Programa principal (aermod.f, líneas 614-620), antes de MAXDCONT_LOOP: | — |
| `starting_bl_contadores(e)` | SOCARD, STARTING (soset.f, líneas 83-91, antes del control de clave repetida): | AERMOD `SOCARD` (soset.f) |
| `starting_bl_indicadores(e)` | SOCARD, STARTING (soset.f, líneas 107-112, tras el control de clave repetida): | AERMOD `SOCARD` (soset.f) |
| `socard_bl(e, k)` | SOCARD, claves BLPINPUT (ISSTAT(43); | AERMOD `SOCARD` (soset.f) |
| `soloca_bl(e, isrc)` | SOLOCA (soset.f, líneas 2504-2509), tras NUMSRC = NUMSRC + 1: | AERMOD `SOLOCA` (soset.f) |
| `blparm(e, isdx, temp)` | BLPARM: SRCPARAM de una fuente BUOYLINE (emisión y altura medias de emisión). | AERMOD `BLPARM` (soset.f) |
| `bl_avginp(e)` | BL_AVGINP: clave BLPINPUT (parámetros medios de la sobreelevación de un grupo: longitud de línea, altura, anchura y separación de edificios, anchura de línea y flotabilidad F'). | AERMOD `BL_AVGINP` (soset.f) |
| `blpgrp(e)` | BLPGRP: clave BLPGROUP (líneas que forman cada grupo/fuente BUOYLINE). El número de grupo de una tarjeta de continuación es el guardado (SAVE) de la tarjeta anterior. | AERMOD `BLPGRP` (soset.f) |
| `hremis_bl(e, k)` | HREMIS (soset.f, líneas 6487-6489 y 6536-6539): | AERMOD `HREMIS` (soset.f) |
| `finished_bl(e)` | SOCARD, FINISHED (soset.f, líneas 864-952; | AERMOD `SOCARD` (soset.f) |
| `srcqa_bl(e, modnam)` | SRCQA (soset.f, líneas 1489-1708; | AERMOD `SRCQA` (soset.f) |
| `srcqa_depos_bl(e, modnam)` | SRCQA (soset.f, líneas 1725-1734; | AERMOD `SRCQA` (soset.f) |
| `srcqa_screen_bl(e, modnam)` | SRCQA (soset.f, líneas 1740-1746): | AERMOD `SRCQA` (soset.f) |
| `bl_rotate1(e, kk)` | BL_ROTATE1: traslada el grupo KK al origen de su primera línea y lo gira para alinear el eje x con las líneas; comprueba el orden de las líneas en y (389) y que sean paralelas a la… | AERMOD `BL_ROTATE1` (soset.f) |
| `recard_bl(e)` | RECARD, FINISHED (reset.f, líneas 183-188; | AERMOD `RECARD` (reset.f) |
| `blrecp(e, kk)` | BLRECP: primera traslación/rotación de los receptores para el grupo KK (la de sus líneas) y marca BL_RFLAG de los receptores dentro del rectángulo que ocupan las líneas (aviso 476 … | AERMOD `BLRECP` (reset.f) |
| `hrqext_bl(e, i)` | HRQEXT (aermod.f, líneas 2293-2294 y 2332-2333): | AERMOD `HRQEXT` (aermod.f) |
| `hrqext_bl_qa(e, i)` | HRQEXT (aermod.f, líneas 2489-2493): | AERMOD `HRQEXT` (aermod.f) |
| `hrloop_maxd_bl(e, isrc)` | HRLOOP (aermod.f, líneas 959-960): | AERMOD `HRLOOP` (aermod.f) |
| `maxdcalc_bl(e, isrc)` | MAXDCALC (output.f, líneas 3397-3398): | AERMOD `MAXDCALC` (output.f) |
| `set_metdata_bl(e)` | SET_METDATA (metext.f, líneas 1057-1059; | AERMOD `SET_METDATA` (metext.f) |
| `ltopg(e)` | LTOPG (calc1.f): clase de estabilidad de Pasquill-Gifford a partir de OBULEN y SFCZ0 (función LSTAB de CTDMPLUS, Golder 1972). Devuelve LSTAB. | AERMOD `LTOPG` (calc1.f) |
| `maxd_guardar_bl(e)` | MAXDCONT_LOOP (aermod.f, líneas 7931-7935): | AERMOD `MAXDCONT_LOOP` (aermod.f) |
| `maxd_receptor_bl(e, ir)` | MAXDCONT_LOOP (aermod.f, líneas 7985-7990): | AERMOD `MAXDCONT_LOOP` (aermod.f) |
| `maxd_restaurar_bl(e)` | MAXDCONT_LOOP (aermod.f, líneas 8195-8199): | AERMOD `MAXDCONT_LOOP` (aermod.f) |
| `calc_bl(e)` | Rama BUOYLINE de CALC (calc1.f, líneas 104-131), que se ejecuta una sola vez por hora (BLPROCESSED lo lleva quien llama): | — |
| `bl_calc(e, kk)` | BL_CALC(KK): concentraciones horarias del grupo BUOYLINE KK en todos los receptores (integración adaptativa a lo largo de cada línea, sobreelevación de BLP y sigmas de Briggs/PG). … | AERMOD `BL_CALC` (bline.f) |
| `bl_dbtsig(e, xz, xy, istab)` | BL_DBTSIG: sigma-y y sigma-z (m) de Briggs/PG a las distancias virtuales XZ y XY (km). Devuelve (SY, SZ). | AERMOD `BL_DBTSIG` (bline.f) |
| `bl_sigmay(e, xkm, istab)` | BL_SIGMAY: sigma-y (m) a XKM km. (En la estabilidad D el original usa 8.3333 en simple precisión y 0.72385, no 0.72382 como BL_DBTSIG.) | AERMOD `BL_SIGMAY` (bline.f) |
| `bl_rise(e, u, istab, s)` | BL_RISE: sobreelevación de la línea (DH(2..7)) en las distancias BL_XDIST(2..7), con el viento efectivo U y, en estable, el parámetro S. | AERMOD `BL_RISE` (bline.f) |
| `bl_zrise(e, il, is_, ir)` | BL_ZRISE(IL, IS, IR): altura del penacho del segmento IS de la línea IL en el receptor IR. (BL_CALC hace el mismo cálculo en línea, con BL_INTRSE evaluado una vez por receptor.) | AERMOD `BL_ZRISE` (bline.f) |
| `bl_intrse(e, x)` | BL_INTRSE: interpola la sobreelevación del elemento más alto a la distancia X entre los puntos BL_XDIST(1..7) (DH(1) = BL_XDIST(1) = 0, nunca se asignan). Si X = BL_XDIST(7) el índ… | AERMOD `BL_INTRSE` (bline.f) |
| `bl_gauss(e, istab, dpbl, crossy, sigy, sigz, h)` | BL_GAUSS: término gaussiano del segmento (con reflexiones en la capa de mezcla por serie de Fourier, o distribución vertical uniforme). Devuelve FT. | AERMOD `BL_GAUSS` (bline.f) |
| `bl_xvz(e, szo, istab)` | BL_XVZ: distancia virtual (km) que da el sigma-z inicial SZO. | AERMOD `BL_XVZ` (bline.f) |
| `bl_xvy(e, syo, istab)` | BL_XVY: distancia virtual (km) que da el sigma-y inicial SYO. | AERMOD `BL_XVY` (bline.f) |
| `bl_wsc(e, istab, um, s, p, nbl)` | BL_WSC: viento efectivo U de la ecuación de sobreelevación de la línea, ajustada en la distancia final XMATCH (UM = viento a la altura de los edificios). Devuelve U. | AERMOD `BL_WSC` (bline.f) |
| `bl_leng(e, theta, u, avfactor, nbl)` | BL_LENG: distancia de flotabilidad plena BL_XFB, longitud efectiva LEFF, longitud de estela LD y radio de borde R0 (variables del módulo) para el ángulo THETA del flujo. | AERMOD `BL_LENG` (bline.f) |
| `bl_sort(e, ftsave, ibmin, ibmax, iwpbl)` | BL_SORT: tramo de segmentos que contribuye (FTSAVE no nulo) alrededor del primero que se encuentra. Devuelve (IBMIN, IBMAX, IWPBL); IWPBL = 999 si ningún segmento contribuye (y ent… | AERMOD `BL_SORT` (bline.f) |
| `bl_cubic(e, a, b, c)` | BL_CUBIC: una raíz de Z**3 + A*Z**2 + B*Z + C = 0 (exponentes 0.333333, como el original). Devuelve Z. | AERMOD `BL_CUBIC` (bline.f) |
| `bl_rotate2(e, wd1, nrecep, nbl, kk)` | BL_ROTATE2: segmentos de las líneas del grupo KK y receptores, trasladados y girados para que el eje y quede paralelo al viento de la hora (WD1). Devuelve (THETA, ITHETA). | AERMOD `BL_ROTATE2` (bline.f) |

### `fuente_sidewash.py`

fuentes SWPOINT (chimenea junto a un edificio, con arrastre lateral o «sidewash»; opción ALPHA).

| Función | Definición | Equivale a |
|---|---|---|
| `_div(a, b)` | División IEEE (±Inf o NaN al dividir por cero). | auxiliar de la traducción |
| `_sqrt(x)` | SQRT IEEE: NaN para argumentos negativos (o NaN). | auxiliar de la traducción |
| `_exp(x)` | DEXP IEEE: +Inf si desborda. | auxiliar de la traducción |
| `_z(v)` | FTZ: un subnormal pasa a cero (con su signo). | auxiliar de la traducción |
| `_m(a, b)` | — | auxiliar de la traducción |
| `_d(a, b)` | — | auxiliar de la traducción |
| `_e(x)` | — | auxiliar de la traducción |
| `soparm_sw(e, isdx, temp)` | Rama SWPOINT de SOPARM: exige la opción ALPHA y 9 campos; después llama a SWPARM. | — |
| `swparm(e, i, temp)` | SWPARM: emisión, altura de la chimenea y anchura, longitud, altura y ángulo del edificio. | AERMOD `SWPARM` (soset.f) |
| `swcalc(e)` | SWCALC: concentración horaria de una fuente SWPOINT en todos los receptores. | AERMOD `SWCALC` (calc1.f) |
| `perpen(e)` | PERPEN: concentración con el viento perpendicular a la fachada (SWCONC). | AERMOD `PERPEN` (calc1.f) |
| `oblique(e)` | OBLIQUE: concentración con el viento oblicuo a la fachada (15 a 60 grados) (SWCONC). | AERMOD `OBLIQUE` (calc1.f) |
| `_terminos(e, u, sig_y1, sig_z1, sig_y2, sig_z2, rho)` | Ecuación gaussiana de doble penacho común a PERPEN y OBLIQUE (TERM1..TERM5): | auxiliar de la traducción |

### `funciones_dispersion.py`

rutinas numéricas de calc2.f (de EMFACT a ERFX): factores de emisión y de fondo, distancia a la sobreelevación final, estela, distancias fuente-receptor, términos laterales y verticales de la distribución gaussiana, mean…

| Función | Definición | Equivale a |
|---|---|---|
| `_div(a, b)` | División IEEE: ±Inf o NaN al dividir por cero (en vez de ZeroDivisionError). | auxiliar de la traducción |
| `_sqrt(x)` | DSQRT IEEE: NaN para argumentos negativos (en vez de ValueError). | auxiliar de la traducción |
| `_ndxvar(e, flag)` | Índice temporal común a EMFACT, BGVAL, OZONVALS y VARYNOXVALS para los indicadores de variación MONTH...MHRDOW7 (None si el indicador no es ninguno de ellos). | auxiliar de la traducción |
| `emfact(e, qarg)` | EMFACT: aplica el factor de emisión variable según QFLAG(ISRC). Fija ``e.QTK`` (si QFLAG no es ninguno de los reconocidos, QTK no se toca, como en el original). | AERMOD `EMFACT` (calc2.f) |
| `bgval(e, isect, barg)` | BGVAL: concentración de fondo variable del sector ISECT, convertida a µg/m3 según POLLUT y BACKUNITS. Devuelve BARG (argumento de entrada/salida). | AERMOD `BGVAL` (calc2.f) |
| `ozonvals(e, isect, o3arg)` | OZONVALS: ozono de fondo variable del sector ISECT en µg/m3. Devuelve O3ARG (entrada/salida). | AERMOD `OZONVALS` (calc2.f) |
| `varynoxvals(e, isect, noxarg)` | VARYNOXVALS: NOx de fondo variable del sector ISECT en µg/m3 (como NO2). Devuelve NOXARG (entrada/salida). | AERMOD `VARYNOXVALS` (calc2.f) |
| `distf(e)` | DISTF: distancia a la sobreelevación final (``e.XMAX``) y sobreelevación final (``e.DHFAER``). En capa estable urbana puede fijar también ``e.PSUBS``, ``e.HEDHH`` y ``e.PPF``; CBLP… | AERMOD `DISTF` (calc2.f) |
| `wakflg(e)` | WAKFLG: dimensiones del edificio del sector IFVSEC y bandera de estela. Fija ``e.DSBH``, ``e.DSBW``, ``e.DSBL``, ``e.XADJ``, ``e.YADJ``, ``e.B_SUBS``, ``e.B_SUBL``, ``e.RSCALE`` (s… | AERMOD `WAKFLG` (calc2.f) |
| `xydist(e, indx)` | XYDIST: coordenadas del receptor INDX y distancias a favor (``e.X``) y transversal al viento (``e.Y``), radial (``e.DISTR``) y altura del receptor sobre la base de la fuente (``e.Z… | AERMOD `XYDIST` (calc2.f) |
| `fterm(e)` | FTERM: término F ligado a la fracción de penacho bajo HCRIT. Fija ``e.FOPT``. | AERMOD `FTERM` (calc2.f) |
| `fyplm(e, syarg)` | FYPLM: término lateral gaussiano del penacho coherente (usa ``e.Y``). Devuelve FYOUT. | AERMOD `FYPLM` (calc2.f) |
| `fypan(e)` | FYPAN: término lateral de la componente aleatoria ("pancake"). Devuelve FYOUT. | AERMOD `FYPAN` (calc2.f) |
| `meandr(e, uef, svef)` | MEANDR: fracción del penacho en la distribución lateral aleatoria (meandro). Devuelve FRAN. Puede emitir los mensajes informativos 494 y 424 (fija ``e.DUMMY``). | AERMOD `MEANDR` (calc2.f) |
| `critds(e, hearg)` | CRITDS: altura de la línea de corriente divisoria para el receptor actual. Fija ``e.HCRIT``. | AERMOD `CRITDS` (calc2.f) |
| `pdf(e)` | PDF: parámetros de la función de densidad de probabilidad de la capa convectiva. | AERMOD `PDF` (calc2.f) |
| `skcalc(e)` | SKCALC: asimetría de la velocidad vertical. Fija ``e.SKEW``. | AERMOD `SKCALC` (calc2.f) |
| `crcalc(e)` | CRCALC: coeficiente de correlación lagrangiano. Fija ``e.R`` = 2. | AERMOD `CRCALC` (calc2.f) |
| `alcalc(e)` | ALCALC: coeficiente ALPHPD de la FDP. Fija ``e.ALPHPD``. | AERMOD `ALCALC` (calc2.f) |
| `becalc(e)` | BECALC: coeficiente BETAPD de la FDP. Fija ``e.BETAPD``. | AERMOD `BECALC` (calc2.f) |
| `aacalc(e)` | AACALC: cocientes de las velocidades medias de corrientes ascendentes y descendentes a sigma-w. Fija ``e.ASUB1`` y ``e.ASUB2``. | AERMOD `AACALC` (calc2.f) |
| `bbcalc(e)` | BBCALC: cocientes de la energía turbulenta de ascendentes y descendentes. Fija ``e.BSUB1`` y ``e.BSUB2``. | AERMOD `BBCALC` (calc2.f) |
| `llcalc(e)` | LLCALC: frecuencias relativas de ascendentes y descendentes. Fija ``e.LAMDA1`` y ``e.LAMDA2``. | AERMOD `LLCALC` (calc2.f) |
| `decay(e, xarg)` | DECAY: término de decaimiento. Fija ``e.D``; DECOEF se modifica temporalmente y se repone. | AERMOD `DECAY` (calc2.f) |
| `vrtsbl(e, szarg, hearg, ziarg)` | VRTSBL: término vertical estable con reflexiones múltiples en ZIARG (= max(HE, ZI)). Fija ``e.FSUBZ``. | AERMOD `VRTSBL` (calc2.f) |
| `vrtsbn(e, szarg, hearg)` | VRTSBN: término vertical estable SIN tapa de mezcla (penachos por encima de la capa convectiva). Fija ``e.FSUBZ``. | AERMOD `VRTSBN` (calc2.f) |
| `vrtcbl(e, he1, he2, sz1, sz2, fact)` | VRTCBL: término vertical bi-gaussiano convectivo (FACT = 1 penacho directo, -1 indirecto). Fija ``e.FSUBZ`` (el factor 1/SZ va dentro de V). | AERMOD `VRTCBL` (calc2.f) |
| `pfract(e, hearg)` | PFRACT: fracción del penacho por debajo de HCRIT. Fija ``e.PHEE``; si pasa de 1.01 (y no se omiten los mensajes) emite el mensaje 405 (fija ``e.DUMMY``) y la limita a 1. | AERMOD `PFRACT` (calc2.f) |
| `erfx(arg)` | ERFX (FUNCTION): función de error por la aproximación de Hastings (1955). No usa el estado global, por eso no recibe `e`. | AERMOD `ERFX` (calc2.f) |

### `integracion_area.py`

integración numérica de las fuentes de área (pitarea.f): AVERTS, AREAIN, PLUMEF, PSIDE, XWIDTH, PWIDTH, ZBRENT, PSIDE2, HPSORT, QATR3 y QG2.

| Función | Definición | Equivale a |
|---|---|---|
| `class _Perezoso` | Módulo hermano importado en el primer acceso; | auxiliar de la traducción |
| `_rutina_tox(nombre)` | PSIDE_TOX / PSIDE2_TOX (opción FASTAREA): | AERMOD `PSIDE_TOX` (pitarea.f) |
| `averts(e, xvin, yvin, xwd, ywd, numv)` | AVERTS: vértices en el sistema de coordenadas de la dirección del viento (OPENPIT). Escribe xwd, ywd en sitio (índices 1..numv). | AERMOD `AVERTS` (pitarea.f) |
| `areain(e)` | AREAIN: concentración horaria de una fuente de área por integración numérica. Fija UVERT, VVERT, VNVERT, WVERT, IVERT, NSEGS, UASEGS, UBSEGS, LSEG y HRVAL(ITYP) (o RUNERR y el mens… | AERMOD `AREAIN` (pitarea.f) |
| `plumef(e, xarg)` | PLUMEF: integrando de la fuente de área a la distancia xarg (m). Devuelve POUT. Fija XDIST, DQCORG/WQCORG o DQCOR/WQCOR, HV, HESETL, HSBL y lo que fijan las rutinas llamadas (CENTR… | AERMOD `PLUMEF` (pitarea.f) |
| `pside(e, u1, u2)` | PSIDE: integra el lado IVERT del polígono entre u1 y u2 según los casos de anchura normalizada fuera de [-3.9, 3.9]. Devuelve DVAL. Fija NSEGS, UASEGS, UBSEGS. | AERMOD `PSIDE` (pitarea.f) |
| `xwidth(e, u)` | XWIDTH: coordenada transversal del lado IVERT para la coordenada u. Devuelve XOUT. | AERMOD `XWIDTH` (pitarea.f) |
| `pwidth(e, xarg, v1)` | PWIDTH: anchura normalizada VN = v1/SY y fracción del penacho WIDTH (tabla GA). Devuelve (VN, WIDTH). Fija SY (y lo que fijan CENTROID, PDF, HEFF, IBLVAL, ADISY). Sin L_APLUME (pen… | AERMOD `PWIDTH` (pitarea.f) |
| `zbrent(e, ifd, x1, x2, vn1, vn2, tol, outval)` | ZBRENT: método de Brent para la u en la que VN = ifd*3.9 entre x1 y x2. Devuelve OUTVAL (entrada/salida: si VN-ifd*3.9 no cambia de signo en el intervalo, el original no lo asigna … | AERMOD `ZBRENT` (pitarea.f) |
| `pside2(e)` | PSIDE2: integra los segmentos con /VN/ > 3.9 eliminando solapes. Devuelve DVAL. Modifica UASEGS/UBSEGS (los ordena en cada segmento) y fija NSEGS. | AERMOD `PSIDE2` (pitarea.f) |
| `hpsort(nvar, uvar, idim)` | HPSORT: ordenación por montículo (heapsort) de uvar[1..nvar], en sitio. Rutina pura (no usa globales): no lleva `e`. idim (dimensión declarada) no se usa. | AERMOD `HPSORT` (pitarea.f) |
| `qatr3(e, xl, xu, eps, epst, ndim, imin, aux)` | QATR3: integral de PLUMEF entre xl y xu por Romberg (adaptación de DQATR de IBM SSP). aux (índices 1..ndim) es la matriz de trabajo, modificada en sitio. Devuelve (Y, IER, I): inte… | AERMOD `QATR3` (pitarea.f) |
| `qg2(e, xl, xu)` | QG2: integral de PLUMEF entre xl y xu por cuadratura de Gauss de 2 puntos. Devuelve Y. | AERMOD `QG2` (pitarea.f) |

### `meteo_horaria.py`

lectura de la meteorología (metext.f).

| Función | Definición | Equivale a |
|---|---|---|
| `pflini(e)` | PFLINI: inicializa las variables del perfil. | AERMOD `PFLINI` (metext.f) |
| `pflcnv(e, level)` | PFLCNV: convierte y controla un nivel del perfil (sigma-v desde sigma-theta, K, mínimos). | AERMOD `PFLCNV` (metext.f) |
| `class FinFichero` | — | — |
| `class ErrorLecturaMet` | — | — |
| `_leer_sfc(e, f)` | READ(MFUNIT,*) de los 25 valores de una hora del .sfc. | auxiliar de la traducción |
| `_leer_pfl(e, f, level, jflag)` | — | auxiliar de la traducción |
| `_qsw(e)` | Radiación solar QSW a partir del flujo de calor, la razón de Bowen, el albedo y la nubosidad (rama de deposición de METEXT, que también usa GRSM). | auxiliar de la traducción |
| `_agua_suelo(e)` | Variables de la deposición seca (METEXT): | auxiliar de la traducción |
| `metext(e)` | METEXT: lee una hora de meteorología (.sfc y perfil .pfl) y prepara los perfiles. | AERMOD `METEXT` (metext.f) |
| `_sector_flujo(fvref, sector_on, sect, n, previo)` | Sector de un fondo que varía con la dirección (O3SECTOR, NOXSECTR). | auxiliar de la traducción |
| `grdeps(e)` | GRDEPS: perfil de la tasa de disipación de la turbulencia (épsilon) para PVMRM y GRSM. | AERMOD `GRDEPS` (metext.f) |
| `_guardar_maxd(e)` | Final de METEXT con MAXDCONT: | auxiliar de la traducción |
| `_fin(e)` | Fin de fichero meteorológico (etiqueta 1000 de METEXT). | auxiliar de la traducción |
| `cent_date2(e, two, four)` | CENT_DATE(TwoDigitYear, FourDigitYear) con dos variables distintas. | AERMOD `CENT_DATE` (meset.f) |
| `set_dates(e)` | SET_DATES: año de 4 cifras, día juliano, KURDAT, FULLDATE, estación y día de la semana. | AERMOD `SET_DATES` (metext.f) |
| `set_metdata(e)` | SET_METDATA: controles de la hora, ZI, rotación del viento y perfiles en la malla. | AERMOD `SET_METDATA` (metext.f) |
| `metchk(e)` | METCHK: controles de la hora meteorológica. | AERMOD `METCHK` (metext.f) |
| `_aviso450(e, txt, error_cuenta)` | Mensaje 450 de CHKDAT: error (y RUNERR) o aviso si WARNCHKD. | auxiliar de la traducción |
| `chkdat(e)` | CHKDAT: secuencia de fechas del fichero meteorológico. | AERMOD `CHKDAT` (metext.f) |
| `cmpdat(e)` | CMPDAT: la fecha del .sfc y la del .pfl deben coincidir. | AERMOD `CMPDAT` (metext.f) |
| `chkclm(e)` | CHKCLM: hora de calma (UREF = 0). | AERMOD `CHKCLM` (metext.f) |
| `chkmsg(e)` | CHKMSG: hora con datos ausentes. | AERMOD `CHKMSG` (metext.f) |
| `metqa(e)` | METQA: control de calidad de la hora (y ajustes de WSTAR, OBULEN, VPTGZI, Z0, PRATE). | AERMOD `METQA` (metext.f) |
| `metdat(e, u)` | METDAT: primeras 24 horas de datos de superficie y primer perfil. | AERMOD `METDAT` (metext.f) |
| `urbcalc(e)` | URBCALC: capa límite urbana nocturna (o de la transición matinal) de cada zona urbana: altura de mezcla, velocidades convectiva y de fricción y longitud de Monin-Obukhov. | AERMOD `URBCALC` (metext.f) |
| `grdurban(e)` | GRDURBAN: perfiles de sigma-v, sigma-w y gradiente de temperatura potencial con la turbulencia convectiva urbana añadida (y copia de los rurales). | AERMOD `GRDURBAN` (metext.f) |
| `grdpturb(e)` | GRDPTURB: perfil de temperatura potencial urbano a partir de su gradiente. | AERMOD `GRDPTURB` (metext.f) |

### `nucleo.py`

Núcleo compilado con numba del cálculo por receptor (fuentes de área).

| Función | Definición | Equivale a |
|---|---|---|
| `desactivar()` | Fuerza la vía Python (opciones de depuración: | — |
| `activo()` | — | — |
| `_quitar_fwrite(lineas)` | Elimina las sentencias ``e.DUMMY = fwrite(...)`` y ``e.pantalla.w(...)`` (pueden ocupar varias líneas). | auxiliar de la traducción |
| `_transformar(src)` | — | auxiliar de la traducción |
| `_fuentes()` | Fuentes transformadas: las funciones de la lista, las plantillas y, por cierre transitivo, los ayudantes privados de esos módulos que se llamen. Devuelve (trozos, constantes). | auxiliar de la traducción |
| `_clasificar(c, e)` | ('a', None) si es una matriz; | auxiliar de la traducción |
| `_generar(e)` | — | auxiliar de la traducción |
| `_huella_fuentes()` | Huella de los ficheros de los que se genera el núcleo. | auxiliar de la traducción |
| `_cargar(e)` | — | auxiliar de la traducción |
| `_derivados(e)` | — | auxiliar de la traducción |
| `_ficticia(nom)` | Matriz de relleno para las no asignadas (p. | auxiliar de la traducción |
| `_leer(e, n)` | — | auxiliar de la traducción |
| `_ejecutar(e, nucleo)` | Empaqueta el estado, ejecuta un bucle compilado y devuelve el estado a ``e``. | auxiliar de la traducción |
| `acalc_bucle(e, qtksav, aerout)` | Bucle de receptores de ACALC con el núcleo compilado. | — |
| `pcalc_bucle(e, aerplm, aerpan)` | Bucle de receptores de PCALC (con PRIME) con el núcleo compilado. | — |
| `vcalc_bucle(e, aerplm, aerpan)` | Bucle de receptores de VCALC con el núcleo compilado. | — |
| `perfiles_hora(e)` | Perfiles meteorológicos de la hora en la malla con el núcleo compilado. | — |
| `pvmrm_bucle(e, srcs, maxchi, domidx)` | Bucle de receptores de PVMRM_CALC con el núcleo compilado. | — |
| `_reproducir(e, der)` | — | auxiliar de la traducción |

### `parametros_efectivos.py`

parámetros meteorológicos efectivos del penacho (iblval.f: IBLVAL y METINI; LOCATE y ANYAVG están en perfiles.py).

| Función | Definición | Equivale a |
|---|---|---|
| `iblval(e, xarg)` | IBLVAL: parámetros efectivos (Ueff, sigma-v, sigma-w, gradiente) promediados sobre la capa que ocupa el penacho, para el penacho estable, directo y penetrado. | AERMOD `IBLVAL` (iblval.f) |
| `metini(e)` | METINI: parámetros meteorológicos a la altura de la chimenea (o de emisión) de la fuente. | AERMOD `METINI` (iblval.f) |

### `perfiles.py`

perfiles meteorológicos en la malla de alturas GRIDHT (windgrid.f, tempgrid.f, siggrid.f y las utilidades GINTRP y ZIAVER de metext.f).

| Función | Definición | Equivale a |
|---|---|---|
| `gintrp(htbelo, vbelow, htabov, vabove, reqdht)` | GINTRP: interpolación lineal. | AERMOD `GINTRP` (metext.f) |
| `locate(parray, lvlblw, lvlabv, value)` | LOCATE: índice del nivel inmediatamente inferior (búsqueda binaria). | AERMOD `LOCATE` (iblval.f) |
| `ziaver(nlvls, hts, parray, zi, ndxblw, valzi)` | ZIAVER: promedio de un perfil entre el suelo y ZI. | AERMOD `ZIAVER` (metext.f) |
| `anyavg(nlvls, hts, parray, zbot, ndxabv, ztop, ndxblw)` | ANYAVG: promedio de un perfil entre ZBOT y ZTOP. Devuelve (promedio, zbot, ndxabv, ztop, ndxblw): el original modifica sus argumentos. | AERMOD `ANYAVG` (iblval.f) |
| `comptg(e)` | COMPTG: gradientes de temperatura potencial a partir del perfil observado. | AERMOD `COMPTG` (tempgrid.f) |
| `tginit(e)` | TGINIT: escala de temperatura THSTAR y gradientes de referencia para la capa estable. | AERMOD `TGINIT` (tempgrid.f) |
| `_tg4pfl(e)` | — | auxiliar de la traducción |
| `round_half_away(x)` | — | — |
| `refptg(e, height)` | REFPTG: gradiente de temperatura potencial teórico a una altura. | AERMOD `REFPTG` (tempgrid.f) |
| `ntrptg(e, htbelo, vbelow, htabov, vabove, reqdht)` | — | AERMOD `NTRPTG` (tempgrid.f) |
| `xtrptg(e, pflz, pflval, grdz)` | — | AERMOD `XTRPTG` (tempgrid.f) |
| `xtrpdn(e, grdz)` | — | AERMOD `XTRPDN` (tempgrid.f) |
| `grdptg(e)` | GRDPTG: gradiente de temperatura potencial en la malla. | AERMOD `GRDPTG` (tempgrid.f) |
| `grdpt(e)` | GRDPT: temperatura potencial en la malla integrando el gradiente desde TREFHT. | AERMOD `GRDPT` (tempgrid.f) |
| `grdden(e)` | GRDDEN: densidad del aire en la malla. | AERMOD `GRDDEN` (tempgrid.f) |
| `unstu(ustr, z, oblen, z0, valpi, valk)` | — | AERMOD `UNSTU` (windgrid.f) |
| `stblu(ustr, z, oblen, z0, valk)` | — | AERMOD `STBLU` (windgrid.f) |
| `refws(e, prflht)` | REFWS: velocidad del viento teórica (perfil de semejanza). | AERMOD `REFWS` (windgrid.f) |
| `_perfil_u(e, z)` | — | auxiliar de la traducción |
| `ntrpws(e, htbelo, vbelow, htabov, vabove, reqdht)` | — | AERMOD `NTRPWS` (windgrid.f) |
| `xtrpws(e, pflz, pflval, grdz)` | — | AERMOD `XTRPWS` (windgrid.f) |
| `grdws(e)` | GRDWS: velocidad del viento en la malla. | AERMOD `GRDWS` (windgrid.f) |
| `_ntrpwd(e, htbelo, vbelow, htabov, vabove, reqdht)` | — | AERMOD `NTRPWD` (windgrid.f) |
| `_xtrpwd(e, pflval)` | — | AERMOD `XTRPWD` (windgrid.f) |
| `grdwd(e)` | GRDWD: dirección del viento en la malla. | AERMOD `GRDWD` (windgrid.f) |
| `refsvc(e, height)` | — | AERMOD `REFSVC` (siggrid.f) |
| `refsvm(e, height)` | — | AERMOD `REFSVM` (siggrid.f) |
| `refsv(e, height)` | — | AERMOD `REFSV` (siggrid.f) |
| `refswc(e, height)` | — | AERMOD `REFSWC` (siggrid.f) |
| `refswm(e, height)` | — | AERMOD `REFSWM` (siggrid.f) |
| `refsw(e, height)` | — | AERMOD `REFSW` (siggrid.f) |
| `_ref(e, cual, height)` | — | auxiliar de la traducción |
| `_grdsig(e, pfl, grid, cual)` | GRDSV/GRDSW: interpolación de sigma-v (cual = 1) o sigma-w (2) a la malla. | AERMOD `GRDSV` (siggrid.f) |
| `grdsv(e)` | GRDSV: sigma-v en la malla. | AERMOD `GRDSV` (siggrid.f) |
| `grdsw(e)` | GRDSW: sigma-w en la malla. | AERMOD `GRDSW` (siggrid.f) |
| `perfiles_hora(e)` | Perfiles de la hora en la malla (bloque de SET_METDATA): | — |

### `principal.py`

programa principal (aermod.f, PROGRAM AERMOD y FILOPN).

| Función | Definición | Equivale a |
|---|---|---|
| `_nombres(argv)` | — | auxiliar de la traducción |
| `_uso(e)` | — | auxiliar de la traducción |
| `filopn(e)` | FILOPN: abre el fichero de control y el de salida. | AERMOD `FILOPN` (aermod.f) |
| `ejecutar(argv)` | Corre AERMOD con los argumentos de la línea de órdenes. | — |
| `_programa(e)` | — | auxiliar de la traducción |
| `_fin(e)` | — | auxiliar de la traducción |

### `quimica_cinetica.py`

esquema químico GRS para el NO2 (grsm.f: GRSM_CALC, RXNRATES, GETBGDEQUIL, QuadraticEquil, FindInitDt, DConcsDt, DoGRSMChem, AdaptiveRK, CashKarpRK y PLUMESIZES).

| Función | Definición | Equivale a |
|---|---|---|
| `_div(a, b)` | División IEEE (±Inf o NaN al dividir por cero). | auxiliar de la traducción |
| `_sqrt(x)` | — | auxiliar de la traducción |
| `_pow(x, y)` | x**y IEEE para x >= 0 (0**y negativo = +Inf). | auxiliar de la traducción |
| `rxnrates(e)` | RXNRATES: velocidades de NO + O3 -> NO2 (R1) y NO2 + hv -> NO + O3 (R2). | AERMOD `RXNRATES` (grsm.f) |
| `quadratic_equil(e, no2, no, o3)` | QuadraticEquil: equilibrio fotoestacionario conservando NOx y NO2 + O3. | — |
| `getbgdequil(e)` | GETBGDEQUIL: fondo de NO2, NO y O3 en equilibrio. | AERMOD `GETBGDEQUIL` (grsm.f) |
| `_dconcsdt(e, c)` | DConcsDt: derivadas temporales de NO, NO2 y O3. | AERMOD `DCONCSDT` (grsm.f) |
| `_find_init_dt(e, c)` | FindInitDt: paso inicial (que ninguna concentración cambie más de CFrac). | auxiliar de la traducción |
| `_cash_karp(e, c, d, dt)` | CashKarpRK: un paso de Runge-Kutta de Cash-Karp con su error. | auxiliar de la traducción |
| `_adaptive_rk(e, c, d, tlocal, dttry, cscal)` | AdaptiveRK: paso de Runge-Kutta reduciendo dt hasta que el error sea aceptable. Actualiza C y devuelve (tLocal, dtnext). | auxiliar de la traducción |
| `_do_grsm_chem(e, c, ttrav)` | DoGRSMChem: integra la química durante el tiempo de viaje TTRAV (modifica C). | auxiliar de la traducción |
| `plumesizes(e, xarg)` | PLUMESIZES: tamaño (sigma-y * sigma-z) del penacho instantáneo y del promediado (con serpenteo) de la fuente ISRC a la distancia XARG. Devuelve (SIGYSIGZ_I, SIGYSIGZ_E). | AERMOD `PLUMESIZES` (grsm.f) |
| `grsm_calc(e)` | GRSM_CALC: conversión NO -> NO2 con el esquema químico GRS (dilución y arrastre del fondo según el tamaño del penacho instantáneo, química durante el tiempo de viaje). | AERMOD `GRSM_CALC` (grsm.f) |

### `quimica_no2.py`

química del NO2 en el cálculo horario.

| Función | Definición | Equivale a |
|---|---|---|
| `_quimica(e)` | — | auxiliar de la traducción |
| `_leer(e, unidad, forma, previos)` | READ(u,*) o READ(u,forma) de (año, mes, día, hora, valor). | auxiliar de la traducción |
| `o3ext(e)` | O3EXT: ozono de fondo de la hora desde el fichero horario del sector en curso (los de los demás sectores se leen para mantenerlos sincronizados), con el mínimo de las horas estable… | AERMOD `O3EXT` (aermod.f) |
| `noxext(e)` | NOXEXT: NOx de fondo de la hora desde el fichero horario del sector en curso (GRSM). Devuelve (L_ReadErr, ReadErr, EndErr). | AERMOD `NOXEXT` (aermod.f) |
| `fondo_hora(e)` | Paso de HRLOOP con química del NO2: | — |
| `conversion(e)` | HRLOOP, horas que no son de calma ni ausentes: | AERMOD `HRLOOP` (aermod.f) |
| `vaciar(e)` | Final de la hora en HRLOOP: | — |
| `sumback_no2(e)` | SUMBACK_NO2: suma el fondo de la hora al receptor IREC del grupo IGRP (si es positivo). | AERMOD `SUMBACK_NO2` (calc2.f) |
| `olm_calc(e)` | OLM_CALC: método de limitación por ozono, fuente a fuente o por OLMGROUP. | AERMOD `OLM_CALC` (calc1.f) |
| `_cociente(a, b)` | DABS(a/b) si b > 0; 0 si no (tiempo de viaje de TTRM_STEP). | auxiliar de la traducción |
| `_ttrm_step(e)` | TTRM_STEP: tiempo de viaje de la fuente ISRC al receptor IREC según el tipo de fuente, la componente dominante del penacho (serpenteo o coherente, directa, indirecta o penetrada) y… | AERMOD `TTRM_STEP` (calc1.f) |
| `ttrm_calc(e)` | TTRM_CALC: método de reacción según el tiempo de viaje (conversión NO -> NO2 por el ozono durante el transporte de cada fuente a cada receptor). | AERMOD `TTRM_CALC` (calc1.f) |
| `_arm2_razon(x)` | Polinomio de ARM2 con las potencias enteras desarrolladas en productos, como el original. | auxiliar de la traducción |
| `arm2_calc(e)` | ARM2_CALC: método de la razón ambiental (versión 2) con el NOx total en cada receptor. | AERMOD `ARM2_CALC` (calc1.f) |
| `sumvalpsd(e, srcs)` | SUMVALPSD: suma ABVAL (NAAQS) o ABVAL-BCVAL (incremento PSD) al receptor IREC. | AERMOD `SUMVALPSD` (calc2.f) |
| `aermax(e, srcs)` | AERMAX: concentración máxima y fuente dominante en cada receptor entre las fuentes del grupo PSD indicado (1: IC y NB; 2: NB y RB). | AERMOD `AERMAX` (calc1.f) |
| `_maxloc_fuentes(e)` | MAXVAL(CHI, DIM=2) y MAXLOC(CHI, DIM=2) sobre todas las fuentes reservadas (primera en caso de empate). | auxiliar de la traducción |
| `_major_cont(e, maxconc, idom)` | MAJOR_CONT: extensión transversal y longitudinal y alturas de las fuentes que aportan al menos la mitad de la concentración máxima en el receptor. | AERMOD `MAJOR_CONT` (calc1.f) |
| `_fmax(a, b)` | — | auxiliar de la traducción |
| `_fmin(a, b)` | — | auxiliar de la traducción |
| `_contar(e, tercera)` | — | auxiliar de la traducción |
| `_moles_nox(e, idom)` | MOLES_NOX: emisión de NOx de las fuentes que caen dentro del volumen combinado. QTK de cada fuente es el de EMFACT de la hora (precalculado en e.QTKSRC). | AERMOD `MOLES_NOX` (calc1.f) |
| `_reldisp(e, xarg)` | RELDISP: dispersión relativa del penacho (Weil). Devuelve (SROUT, SROUT3). | AERMOD `RELDISP` (calc1.f) |
| `_plume_vol(e, xarg, irdx, isdx, bvarg, bvarg3, bharg, bharg3)` | PLUME_VOL: volumen del penacho de la fuente ISDX hasta la distancia XARG (integrado por tramos de la tabla de distancias), ampliado con las extensiones BV/BH de las fuentes que apo… | AERMOD `PLUME_VOL` (calc1.f) |
| `_psd_incluida(e, isrc, srcs)` | ¿Entra la fuente en el cálculo según PSDCREDIT y el conjunto de fuentes? | auxiliar de la traducción |
| `_aviso_411(e, irec)` | Aviso 411 de PVMRM_CALC (no hay emisión de NOx en el volumen combinado). | auxiliar de la traducción |
| `pvmrm_calc(e, srcs2use)` | PVMRM_CALC: método de la razón molar en el volumen del penacho. | AERMOD `PVMRM_CALC` (calc1.f) |
| `_pvmrm_bucle(e, srcs, maxchi, domidx)` | Bucle de receptores de PVMRM_CALC (la parte que se compila con numba en nucleo.py). | auxiliar de la traducción |

### `reinicio.py`

re-arranque de corridas y corridas de varios años encadenados (SAVEFILE, INITFILE y MULTYEAR).

| Función | Definición | Equivale a |
|---|---|---|
| `_f(a)` | Bloque a(1:d1, 1:d2, ...) aplanado en el orden de Fortran. | auxiliar de la traducción |
| `_d(a)` | — | auxiliar de la traducción |
| `_i(a)` | — | auxiliar de la traducción |
| `_c(a)` | — | auxiliar de la traducción |
| `_ints()` | — | auxiliar de la traducción |
| `rsdump(e)` | RSDUMP: resultados intermedios al SAVEFILE (alterna SAVFIL y SAVFL2 si son distintos). | AERMOD `RSDUMP` (calc2.f) |
| `class _FinDatos` | — | auxiliar de la traducción |
| `_leer(u, fmt_items)` | READ(IRSUNT) de un registro: | auxiliar de la traducción |
| `_poner(a, v)` | a(1:d1, ...) = v (aplanado en orden de Fortran). | auxiliar de la traducción |
| `_poner_c(a, s)` | — | auxiliar de la traducción |
| `rsinit(e)` | RSINIT: inicializa los resultados desde el fichero de re-arranque (INITFILE o el SAVEFILE del año anterior con MULTYEAR). | AERMOD `RSINIT` (inpsum.f) |
| `fecha_reinicio(e)` | READ(IRSUNT) IRSDATE + REWIND. | — |
| `_long_date(e, idat8, previo)` | LONG_DATE: fecha de 8 cifras (año de 2) a 10 cifras con el siglo ISTRT_CENT (si el año no cabe en 2 cifras, IDAT conserva el valor anterior). | AERMOD `LONG_DATE` (meset.f) |
| `reanudar_texto(e, m, unidad, nombre, col, irsdate, cod_multyr, ajustar_hora)` | Posiciona un fichero formateado de resultados (MAXIFILE, POSTFILE PLOT, MAXDAILY...) tras su último registro con fecha <= IRSDATE. | — |
| `reanudar_bin(e, m, unidad, nombre, irsdate)` | POSTFILE sin formato: igual que `reanudar_texto` leyendo la fecha (primer entero) de cada registro. | — |
| `existe(nombre)` | — | — |

### `resultados.py`

acumulación de resultados horarios (calc2.f: SUMVAL, AVER, HIVALS, NHIGH, HSETFG, MAXVALUE, MSETFG, MAXFIL, POSTFL).

| Función | Definición | Equivale a |
|---|---|---|
| `sumval(e)` | SUMVAL: suma HRVAL de la fuente ISRC al grupo IGRP en el receptor IREC. | AERMOD `SUMVAL` (calc2.f) |
| `sumback(e)` | SUMBACK: suma la concentración de fondo de la hora a todos los receptores del grupo IGRP (si el grupo incluye BACKGROUND). | AERMOD `SUMBACK` (calc2.f) |
| `aver(e)` | AVER: promedio de un periodo de varias horas (horas válidas o el 75 %). | AERMOD `AVER` (calc2.f) |
| `_dnint(x)` | — | auxiliar de la traducción |
| `hivals(e)` | HIVALS: actualiza las tablas de máximos por receptor y globales. | AERMOD `HIVALS` (calc2.f) |
| `_bandera(e)` | — | auxiliar de la traducción |
| `nhigh(e)` | NHIGH: inserta AVEVAL en la lista de los NHIVAL valores más altos de cada receptor. | AERMOD `NHIGH` (calc2.f) |
| `maxvalue(e)` | MAXVALUE: inserta AVEVAL en la tabla global de los NMXVAL valores máximos. | AERMOD `MAXVALUE` (calc2.f) |
| `maxfil(e)` | MAXFIL: escribe los valores que superan el umbral (MAXIFILE). | AERMOD `MAXFIL` (calc2.f) |
| `_partes_pst(e, nrec, ntyp)` | Partes fijas por receptor de las líneas del POSTFILE PLOT con los formatos estándar (X e Y; | auxiliar de la traducción |
| `postfl(e)` | POSTFL: escribe el fichero de posproceso (sin formato o PLOT) del periodo IAVE. | AERMOD `POSTFL` (calc2.f) |
| `toxxfl(e)` | TOXXFL (calc2.f): llena los búferes del TOXXFILE y los escribe cuando se llenan. | AERMOD `TOXXFL` (calc2.f) |
| `toxx_fin(e)` | Fin de HRLOOP: rellena con ceros los búferes del TOXXFILE, los escribe y cierra. | — |

### `resumen_entrada.py`

resumen de las entradas (inpsum.f): INPSUM, PRTOPT, PRTSRC, PRTREC, CHKREC, PRTMET y RESINI, para las opciones del alcance.

| Función | Definición | Equivale a |
|---|---|---|
| `resini(e)` | RESINI: pone a cero las matrices de resultados. | AERMOD `RESINI` (inpsum.f) |
| `inpsum(e)` | INPSUM: resumen de las entradas en el fichero de salida (y en el SUMMFILE). | AERMOD `INPSUM` (inpsum.f) |
| `prtopt(e, u)` | PRTOPT: resumen de las opciones del modelo. | AERMOD `PRTOPT` (inpsum.f) |
| `_opciones_quimica(e, o, nom, sector_on, nsect, sect, lfile, iset, lval, flags, nom_h)` | PRTOPT: resumen de los datos de ozono (OLM/PVMRM/GRSM) o de NOx (GRSM) de fondo. | AERMOD `PRTOPT` (inpsum.f) |
| `prtvals(e, isect, cual)` | PRTO3VALS / PRTNOXVALS: tabla de los valores de ozono (O3VALUES) o de NOx (NOX_VALS) que varían en el tiempo para el sector ISECT. | AERMOD `PRTO3VALS` (inpsum.f) |
| `_opciones_fondo(e, o)` | PRTOPT: líneas del resumen de opciones sobre los valores de fondo (BACKGRND). | AERMOD `PRTOPT` (inpsum.f) |
| `prtbkg(e, isect)` | PRTBKG: tabla de los valores de fondo del sector ISECT. | AERMOD `PRTBKG` (inpsum.f) |
| `_comunes(e, i)` | — | auxiliar de la traducción |
| `_edificio(e, i)` | — | auxiliar de la traducción |
| `prtsrc(e)` | PRTSRC: tablas de datos de las fuentes, grupos, edificios y factores de emisión. | AERMOD `PRTSRC` (inpsum.f) |
| `_factores(e, o, cabecera)` | — | auxiliar de la traducción |
| `_tabla_red(e, o, cabecera, i, titulo, valores)` | Tabla de cotas, alturas de colina o de receptor de una red (9 columnas x 40 filas). | auxiliar de la traducción |
| `prtrec(e)` | PRTREC: resumen de los receptores (redes y receptores discretos). | AERMOD `PRTREC` (inpsum.f) |
| `chkrec(e)` | CHKREC: combinaciones fuente-receptor a menos de 1 m (o más allá de MAXDIST). | AERMOD `CHKREC` (inpsum.f) |
| `prtmet(e, u)` | PRTMET: días meteorológicos a procesar y categorías de viento. | AERMOD `PRTMET` (inpsum.f) |

### `salida.py`

resultados finales (parte final del programa principal de aermod.f y output.f: PERAVE, HIPER, PSTANN, PLTANN, PLOTFL, OUTPUT, PRTANN, PRTNHI, SPRTHT, PRTMAX, PRTSUM) y las tablas diarias de DAYTABLE (PRTDAY, calc2.f).

| Función | Definición | Equivale a |
|---|---|---|
| `final(e)` | Tras HRLOOP: promedios del periodo, ficheros de gráficos y tablas del fichero de salida. | — |
| `_maxval(a)` | — | auxiliar de la traducción |
| `_interior(a)` | — | auxiliar de la traducción |
| `_aviso_exp(e)` | — | auxiliar de la traducción |
| `perave(e)` | PERAVE: promedio del periodo. | AERMOD `PERAVE` (output.f) |
| `hiper(e)` | HIPER: los NHIANN valores más altos del periodo. | AERMOD `HIPER` (output.f) |
| `_cab_comun(e, con_title2)` | — | auxiliar de la traducción |
| `_hdr_ann(e, etiqueta)` | — | auxiliar de la traducción |
| `_lineas_ann(e, igrp, perchr)` | — | auxiliar de la traducción |
| `pstann(e)` | PSTANN: fichero de posproceso con los promedios del periodo. | AERMOD `PSTANN` (output.f) |
| `pltann(e)` | PLTANN: fichero de gráficos con los promedios del periodo. | AERMOD `PLTANN` (output.f) |
| `_chrval(ival)` | — | auxiliar de la traducción |
| `plotfl(e)` | PLOTFL: ficheros de gráficos de los valores altos por receptor. | AERMOD `PLOTFL` (output.f) |
| `output(e)` | OUTPUT: tablas de resultados en el fichero de salida. | AERMOD `OUTPUT` (output.f) |
| `_workid(e, igrp)` | Lista de fuentes del grupo para las cabeceras (WORKID, INDGRP). | auxiliar de la traducción |
| `_chidep6(e, it)` | — | auxiliar de la traducción |
| `_poner(buf, a, b, texto)` | WRITE(BUF(a+1:b), ...): el registro interno ocupa b-a caracteres. | auxiliar de la traducción |
| `_malla(e, u, cab, ncpp, fmt_x_cart, fmt_x_polr, fila)` | Tablas de las redes GRIDCART/GRIDPOLR (común a PRTANN y SPRTHT). | auxiliar de la traducción |
| `prtann(e)` | PRTANN: tablas de los promedios del periodo por receptor. | AERMOD `PRTANN` (output.f) |
| `prtday(e)` | PRTDAY (calc2.f): tablas de los valores concurrentes del periodo IAVE que acaba en la hora en curso (DAYTABLE), para el tipo de salida ITYP. Siempre con formato fijo (F13.5). | AERMOD `PRTDAY` (calc2.f) |
| `_distdir(e, irec)` | — | auxiliar de la traducción |
| `_discretos(e, u, tipo, cab, lbl, cab_col, linea, r1, r2)` | Tablas de receptores discretos en dos columnas (DC o DP), 80 por página. | auxiliar de la traducción |
| `prtnhi(e)` | PRTNHI: tablas de los valores N-ésimos más altos y máximos por grupo (HMAX). | AERMOD `PRTNHI` (output.f) |
| `sprtht(e, ihnum)` | SPRTHT: tablas del IHNUM-ésimo valor más alto por receptor. | AERMOD `SPRTHT` (output.f) |
| `prtmax(e)` | PRTMAX: tablas de los valores máximos globales (MAXTABLE). | AERMOD `PRTMAX` (output.f) |
| `prtsum(e, iount)` | PRTSUM: resumen de resultados máximos (fichero de salida y SUMMFILE). | AERMOD `PRTSUM` (output.f) |
| `rankfl(e)` | RANKFL: ficheros de valores máximos ordenados sin periodos repetidos (RANKFILE). | AERMOD `RANKFL` (output.f) |
| `shave(e)` | SHAVE: promedios por estación y hora del día (SEASONHR). | AERMOD `SHAVE` (output.f) |
| `shout(e)` | SHOUT: ficheros de valores por estación y hora del día (SEASONHR). | AERMOD `SHOUT` (output.f) |
| `prtpm25(e)` | PRTPM25: tablas de los N-ésimos máximos diarios promediados en los años (SUMHNH). | AERMOD `PRTPM25` (output.f) |
| `maxpm25(e)` | MAXPM25: tabla global de los NMXPM valores máximos de SUMHNH. | AERMOD `MAXPM25` (output.f) |
| `prtpm25sum(e, iount)` | PRTPM25SUM: resumen de los máximos de SUMHNH (fichero de salida y SUMMFILE). | AERMOD `PRTPM25SUM` (output.f) |

### `sigmas.py`

coeficientes de dispersión (sigmas.f: SIGY, SIGZ, BID, SZSFCL, RMSSIG) y sobreelevación del penacho (prise.f: DELTAH, PRMDELH, HSPRIM, SBLRIS, CBLPRD, CBLPRN, CBLPR3).

| Función | Definición | Equivale a |
|---|---|---|
| `_rpot(base, expo)` | Potencia real ``base**expo`` como el Fortran: | auxiliar de la traducción |
| `sigy(e, xarg)` | SIGY: sigma-y ambiental (SYAMB; en convectivo también SYAN y SYA3). | AERMOD `SIGY` (sigmas.f) |
| `sigz(e, xarg)` | SIGZ: sigma-z ambiental (SZAMB/SZAS en estable; SZAD1, SZAD2, SZAN1, SZAN2 y SZA3 en convectivo). | AERMOD `SIGZ` (sigmas.f) |
| `bid(e)` | BID: dispersión inducida por la flotabilidad (SYB, SZB, SZBD, SZBN, SYB3, SZB3). | AERMOD `BID` (sigmas.f) |
| `szsfcl(e, xarg)` | SZSFCL: término de capa superficial de sigma-z (SZSURF). | AERMOD `SZSFCL` (sigmas.f) |
| `rmssig(e)` | RMSSIG: sigma-y y sigma-z totales como raíz de la suma de cuadrados (incluye los términos de downwash de plataformas). | AERMOD `RMSSIG` (sigmas.f) |
| `deltah(e, xarg)` | DELTAH: sobreelevación del penacho a la distancia XARG (DHP; en convectivo DHP1, DHP2 y DHP3). | AERMOD `DELTAH` (prise.f) |
| `prmdelh(e, xarg, l_inwake)` | PRMDELH: sobreelevación para el cálculo PRIME (DHP). Devuelve L_INWAKE (argumento de entrada/salida del original). | AERMOD `PRMDELH` (prise.f) |
| `hsprim(us, vs, hs, ds)` | HSPRIM (FUNCTION): altura de chimenea corregida por el downwash de la boca (HS'). | AERMOD `HSPRIM` (prise.f) |
| `sblris(e, xarg)` | SBLRIS: sobreelevación en la capa estable o por encima de la capa convectiva (DHP). | AERMOD `SBLRIS` (prise.f) |
| `cblprd(e, xarg)` | CBLPRD: sobreelevación del penacho directo en la capa convectiva (DHP1). | AERMOD `CBLPRD` (prise.f) |
| `cblprn(e, xarg)` | CBLPRN: sobreelevación del penacho indirecto en la capa convectiva (DHP2). | AERMOD `CBLPRN` (prise.f) |
| `cblpr3(e)` | CBLPR3: sobreelevación del penacho que penetra la capa convectiva (DHP3). | AERMOD `CBLPR3` (prise.f) |
