# `lagaus.meteo.capa_limite` — capa_limite

Equivale a **AERMET**: traducido del código de AERMET (dominio público); cada función indica la rutina original.

<!-- manual -->
## Qué hace
Procesa las **observaciones meteorológicas** (superficie, altura y estación propia) y calcula los
parámetros de **capa límite** que necesita el penacho: velocidad de fricción, longitud de
Monin-Obukhov, velocidad convectiva, alturas de mezcla mecánica y convectiva, y los perfiles.

## Entradas y salidas
| | |
|---|---|
| Entrada | fichero de control por etapas (altura, superficie, estación propia, cálculo), datos de observación y características de superficie (de `terreno.superficie`) |
| Salida | fichero de superficie (`.sfc`) y de perfiles (`.pfl`) para `dispersion.penacho`, e informes de cada etapa |

## Uso
```bash
python -m lagaus capa_limite aermet.inp
```
```python
from lagaus.meteo.capa_limite.__main__ import ejecutar
ejecutar("aermet.inp")
```

## Ejemplo
Un año de observaciones horarias de una estación y su sondeo más cercano produce 8760 registros
de `.sfc` con u\*, L, w\* y alturas de mezcla, y el `.pfl` con viento y temperatura por niveles.

## Validación y alcance
73 de 73 pasos comparables idénticos al original en todos sus ficheros (39 casos: oficiales,
datos reales de 2024 y contraste con ERA5). Fuera: formatos antiguos de EE. UU. (TD-6201,
CD-144, SCRAM, SAMSON, HUSWO) y COARE sobre el mar.
<!-- /manual -->

## Ficheros

| Fichero | Contenido | Viene de | Equivale a |
|---|---|---|---|
| `__init__.py` | paquete | `__init__.py` | — |
| `__main__.py` | programa principal (aermet.f90) y CLEANUP (mod_misc.f90). | `__main__.py` | `aermet.f90`, `mod_misc.f90` |
| `calculo_cl.py` | módulo PBL, etapa 2. | `pbl.py` | `mod_pbl.f90` |
| `comun.py` | subrutinas comunes de MAIN1. | `comun.py` | — |
| `control.py` | lectura del fichero de control (módulo READ_INPUT: readinp, check_line, job_path). | `control.py` | — |
| `control_cl.py` | módulo PBL, parte de control. | `pbl_control.py` | — |
| `estacion_local.py` | módulo ONSITE (datos de estación propia y datos pronósticos PROG/MMIF): lectura del control, extracción, promedios subhorarios, control de calidad y fichero QAOUT. | `onsite.py` | `mod_onsite.f90` |
| `estado.py` | estado global. | `estado.py` | — |
| `formato.py` | Compatibilidad de E/S y numérica con el Fortran de AERMET 26135 (US EPA, dominio público). | `fortran.py` | — |
| `informes.py` | módulo REPORTS (fichero de informe). | `informes.py` | — |
| `obs_superficie.py` | módulo SURFACE (estación de superficie). | `surface.py` | `mod_surface.f90` |
| `sondeos.py` | módulo UPPERAIR (radiosondeos). | `upperair.py` | `mod_upperair.f90` |
| `tablas.py` | Tablas de AERMET 26135 (US EPA, dominio público). | `tablas.py` | — |

## Funciones por fichero

219 funciones; 168 con equivalencia explícita. Las auxiliares de la traducción no tienen rutina propia en el original.

### `__main__.py`

programa principal (aermet.f90) y CLEANUP (mod_misc.f90).

| Función | Definición | Equivale a |
|---|---|---|
| `cleanup(E)` | — | AERMET `CLEANUP` (mod_misc.f90) |
| `_fin(E, mal)` | — | auxiliar de la traducción |
| `ejecutar(inpfile, eco)` | Ejecuta AERMET sobre `inpfile`. | — |
| `main(argv)` | — | — |

### `calculo_cl.py`

módulo PBL, etapa 2.

| Función | Definición | Equivale a |
|---|---|---|
| `class Dia` | Un elemento de sfc_data (tipo sfdat1): | — |
| `class Perfil` | Un elemento de pfl_data (tipo pfldat). | — |
| `_mat(nh, nd, val)` | — | auxiliar de la traducción |
| `pbl_proc(E, ahora)` | — | AERMET `PBL_PROC` (mod_pbl.f90) |
| `sundat(E, rlat, rlon, tzone, jday, angs)` | — | AERMET `SUNDAT` (mod_pbl.f90) |
| `check_obs(E, iswitch, iday1)` | CHECK_OBS. Devuelve (station_use, lsub1, lsub2). | AERMET `CHECK_OBS` (mod_pbl.f90) |
| `upp_dates(E, iday1, istation)` | UPP_DATES. Devuelve (target_date, target_hr, snd_hr, snd_window, lgo). | AERMET `UPP_DATES` (mod_pbl.f90) |
| `get_sound(E, iday1, istation, target_date, target_hr, snd_hr, snd_window, lgo)` | — | AERMET `GET_SOUND` (mod_pbl.f90) |
| `winds(E, d, h)` | WINDS. Devuelve (wind_reset, orig_wind_speed). | AERMET `WINDS` (mod_pbl.f90) |
| `temps(E, d, h)` | — | AERMET `TEMPS` (mod_pbl.f90) |
| `clouds(E, d, h)` | — | AERMET `CLOUDS` (mod_pbl.f90) |
| `substitute(E, d, h, ostemp)` | — | AERMET `SUBSTITUTE` (mod_pbl.f90) |
| `press(E, d, h, ostemp)` | — | AERMET `PRESS` (mod_pbl.f90) |
| `rh(E, d, h)` | RH. Devuelve (rh_ht, have_rh). | AERMET `RH` (mod_pbl.f90) |
| `precip(E, d, h)` | — | AERMET `PRECIP` (mod_pbl.f90) |
| `stability(E, d, h)` | — | AERMET `STABILITY` (mod_pbl.f90) |
| `calc_ustar(E, d, h, wind_reset, wspeed)` | CALC_USTAR. Devuelve (ustar, mol, thetastar1). | AERMET `CALC_USTAR` (mod_pbl.f90) |
| `nr_ang(E, d, h, ccvrin, tempin)` | — | — |
| `netrad(E, d, h)` | NETRAD. Devuelve lcycle. | AERMET `NETRAD` (mod_pbl.f90) |
| `sfc_chars(E, isite, d, wd, missdir)` | SFC_CHARS. Devuelve (albedo, bowen, zo). | AERMET `SFC_CHARS` (mod_pbl.f90) |
| `have_data(E, d, h, invar1)` | — | AERMET `HAVE_DATA` (mod_pbl.f90) |
| `bulk_rich(E, d, h)` | — | AERMET `BULK_RICH` (mod_pbl.f90) |
| `check_flux(E, d, h)` | — | AERMET `CHECK_FLUX` (mod_pbl.f90) |
| `_sq(x)` | — | auxiliar de la traducción |
| `_dv(a, b)` | a/b con la aritmética IEEE del original (x/0 = ±Inf, 0/0 = NaN) en vez de una excepción. | auxiliar de la traducción |
| `_dmax1(a, b)` | — | auxiliar de la traducción |
| `_p4(x)` | — | auxiliar de la traducción |
| `_p6(x)` | — | auxiliar de la traducción |
| `_pow(x, y)` | x**y de Fortran para x<=0: | auxiliar de la traducción |
| `mech_ht(E, d, h)` | — | AERMET `MECH_HT` (mod_pbl.f90) |
| `read_sound(E, d, station_use, lsub1)` | — | AERMET `READ_SOUND` (mod_pbl.f90) |
| `conv_ht(E, d, station_use, cblhr1)` | — | AERMET `CONV_HT` (mod_pbl.f90) |
| `wstar(E, d, h)` | — | — |
| `vptg(E, d, h)` | — | — |
| `profile(E, d, h, ostemp)` | — | AERMET `PROFILE` (mod_pbl.f90) |
| `sfc_header(E)` | — | AERMET `SFC_HEADER` (mod_pbl.f90) |
| `writefiles(E, d)` | — | AERMET `WRITEFILES` (mod_pbl.f90) |
| `check_surf(E, d, h, sfcline)` | — | AERMET `CHECK_SURF` (mod_pbl.f90) |
| `check_prof(E, d, h, ilev, pflline)` | — | AERMET `CHECK_PROF` (mod_pbl.f90) |

### `comun.py`

subrutinas comunes de MAIN1.

| Función | Definición | Equivale a |
|---|---|---|
| `pid(E, ip)` | adjustl(pathid(ipath)) como CHARACTER*10. | — |
| `leapyr(iyear)` | — | AERMET `LEAPYR` (mod_main1.f90) |
| `fmt_msg(E, sufijo)` | — | — |
| `datetime(E, i, ahora)` | — | AERMET `DATETIME` (mod_main1.f90) |
| `start_stop(E, i, ifile)` | — | AERMET `START_STOP` (mod_main1.f90) |
| `getunit(E)` | — | AERMET `GETUNIT` (mod_main1.f90) |
| `checkfile(E, iunit, fname, itype)` | Devuelve (fname, lgood). fname puede perder las comillas. | AERMET `CHECKFILE` (mod_main1.f90) |
| `dataline(E, i, i1)` | — | AERMET `DATALINE` (mod_main1.f90) |
| `getfields(E, i1, nfield1)` | Devuelve la lista 1..nfield1 de campos (CHARACTER*100) de inpline1 a partir de i1+1. | AERMET `GETFIELDS` (mod_main1.f90) |
| `checkdates(E, iyear, imonth, iday, istartend)` | Devuelve (idate o None, lgood). | AERMET `CHECKDATES` (mod_main1.f90) |
| `getdates(E, i1)` | GETDATES: devuelve (startdate, enddate, dates1) con dates1[ii][j] (1..2, 1..3). | AERMET `GETDATES` (mod_main1.f90) |
| `coord(E, lfield)` | COORD: lfield es CHARACTER*40 (se ve sólo lo que cabe). | — |
| `getloc(E, i1, lgmt2lst, lelev)` | GETLOC: devuelve dict con stid, lat, lon, gmt2lst, elev, lgmt2lst, lelev. | AERMET `GETLOC` (mod_main1.f90) |
| `var_list(E, i1, nfield1, varnam, varlogic, nvar)` | VAR_LIST: varnam/varlogic con índices 1..nvar; modifica varlogic. | AERMET `VAR_LIST` (mod_main1.f90) |
| `range_mod(E, v1, v2, v3, v4)` | Devuelve (linc, lowval, hival, missval, lgood). | AERMET `RANGE_MOD` (mod_main1.f90) |
| `_juliano(fecha)` | — | auxiliar de la traducción |
| `numdays(start1, end1)` | — | — |
| `jday(iyear, imonth, iday)` | — | — |
| `data_dates(E, ihr, iday, imonth, iyear, gmt2lst, istart, iend, ierr)` | DATA_DATES. Devuelve (ihr, iday, imonth, iyear, idate, lgo) tras la conversión GMT→LST. | AERMET `DATA_DATES` (mod_main1.f90) |
| `humidity(db, dp)` | — | — |
| `pressure(E, iopt, elev, tv, inp_pres)` | — | — |

### `control.py`

lectura del fichero de control (módulo READ_INPUT: readinp, check_line, job_path).

| Función | Definición | Equivale a |
|---|---|---|
| `_mayus(s)` | — | auxiliar de la traducción |
| `readinp(E)` | READINP. Devuelve False si el fichero de control no existe (el original hace STOP). | AERMET `READINP` (mod_read_input.f90) |
| `check_line(E)` | — | AERMET `CHECK_LINE` (mod_read_input.f90) |
| `job_path(E)` | — | AERMET `JOB_PATH` (mod_read_input.f90) |

### `control_cl.py`

módulo PBL, parte de control.

| Función | Definición | Equivale a |
|---|---|---|
| `class NoTraducido` | Opción del original fuera del alcance de la traducción. | — |
| `pbl_path(E)` | — | AERMET `PBL_PATH` (mod_pbl.f90) |
| `year_str(E, i1)` | — | AERMET `YEAR_STR` (mod_pbl.f90) |
| `methods(E, i1)` | — | AERMET `METHODS` (mod_pbl.f90) |
| `up_window(E, i1)` | — | AERMET `UP_WINDOW` (mod_pbl.f90) |
| `pbl_test(E)` | — | AERMET `PBL_TEST` (mod_pbl.f90) |
| `surf_years(E, yrstr)` | — | AERMET `SURF_YEARS` (mod_pbl.f90) |
| `_abrir_lineas(E, iunit, fname)` | — | auxiliar de la traducción |
| `aersurf(E, iswitch, isite)` | AERSURF. Devuelve lbadsc. | AERMET `AERSURF` (mod_pbl.f90) |
| `_contar_campos(L)` | — | auxiliar de la traducción |
| `freq_sec(E, i1, isite)` | Devuelve (nfreq, nsec, lskip). | AERMET `FREQ_SEC` (mod_pbl.f90) |
| `site_char(E, i1, isite, nfreq, nsec)` | — | AERMET `SITE_CHAR` (mod_pbl.f90) |
| `sectors(E, i1, isite, nsec)` | — | AERMET `SECTORS` (mod_pbl.f90) |

### `estacion_local.py`

módulo ONSITE (datos de estación propia y datos pronósticos PROG/MMIF): lectura del control, extracción, promedios subhorarios, control de calidad y fichero QAOUT.

| Función | Definición | Equivale a |
|---|---|---|
| `onsite_init(E)` | — | AERMET `ONSITE_INIT` (mod_onsite.f90) |
| `os_path(E)` | — | AERMET `OS_PATH` (mod_onsite.f90) |
| `_getloc_os(E, i1)` | — | auxiliar de la traducción |
| `os_list(E, i1)` | — | AERMET `OS_LIST` (mod_onsite.f90) |
| `os_range(E, i1)` | — | AERMET `OS_RANGE` (mod_onsite.f90) |
| `delta_t_ht(E, i1)` | — | AERMET `DELTA_T_HT` (mod_onsite.f90) |
| `os_thresh(E, i1)` | — | AERMET `OS_THRESH` (mod_onsite.f90) |
| `osheights(E, i1)` | — | AERMET `OSHEIGHTS` (mod_onsite.f90) |
| `os_vars(E, i1)` | — | AERMET `OS_VARS` (mod_onsite.f90) |
| `os_form(E)` | — | AERMET `OS_FORM` (mod_onsite.f90) |
| `os_obsnum(E, i1)` | — | AERMET `OS_OBSNUM` (mod_onsite.f90) |
| `os_test(E)` | — | AERMET `OS_TEST` (mod_onsite.f90) |
| `osformread(E)` | — | AERMET `OSFORMREAD` (mod_onsite.f90) |
| `os_stage2(E)` | Lee la cabecera del QAOUT ONSITE en una corrida de sólo etapa 2. | AERMET `OS_STAGE2` (mod_onsite.f90) |
| `_contar(L)` | — | auxiliar de la traducción |
| `os_proc(E, ahora)` | — | AERMET `OS_PROC` (mod_onsite.f90) |
| `class SimpleOsinfo` | — | — |
| `_asignar_readvar(o, ivar, j, nombres)` | — | auxiliar de la traducción |
| `_incr(o, ivar)` | — | auxiliar de la traducción |
| `header(E, nwritevar)` | — | AERMET `HEADER` (mod_onsite.f90) |
| `read_os(E)` | — | AERMET `READ_OS` (mod_onsite.f90) |
| `findvar(E, ivar)` | — | — |
| `audit(E, rvar, ivar, d, h, imin, ilev, iv, iswitch)` | — | AERMET `AUDIT` (mod_onsite.f90) |
| `_audit_mensajes(E, rvar, v, d, h, imin, ilev, iv, iswitch, writemiss, lowv, upv, lb, ub)` | Mensajes de AUDIT (los textos solo se preparan cuando hay algo que escribir). | auxiliar de la traducción |
| `avg_hr(E)` | — | AERMET `AVG_HR` (mod_onsite.f90) |
| `calc_wind(E, dircount, d, h, imin1, ilev)` | — | AERMET `CALC_WIND` (mod_onsite.f90) |
| `avg_wind(E, dircount, d, h, ilev)` | — | AERMET `AVG_WIND` (mod_onsite.f90) |
| `check_wind(E)` | — | AERMET `CHECK_WIND` (mod_onsite.f90) |
| `os_audithr(E)` | — | AERMET `OS_AUDITHR` (mod_onsite.f90) |
| `read_ext(E)` | — | AERMET `READ_EXT` (mod_onsite.f90) |
| `check_hts(E)` | — | AERMET `CHECK_HTS` (mod_onsite.f90) |

### `estado.py`

estado global.

| Función | Definición | Equivale a |
|---|---|---|
| `arr()` | Matriz con índices 1..dims (posición 0 sin usar en cada dimensión). | — |
| `vec(n, val)` | — | — |
| `class Ovar` | Tipo ovars (mod_onsite). | — |
| `class Uavar` | Tipo uavars (mod_upperair): | — |
| `class Svar` | Tipo svars (mod_surface). | — |
| `class Formato` | — | — |
| `class Asos` | — | — |
| `class Estado` | — | — |
| `_norm(nombre)` | — | auxiliar de la traducción |
| `_crear(nombre)` | — | auxiliar de la traducción |

### `formato.py`

Compatibilidad de E/S y numérica con el Fortran de AERMET 26135 (US EPA, dominio público).

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

### `informes.py`

módulo REPORTS (fichero de informe).

| Función | Definición | Equivale a |
|---|---|---|
| `_w(E, fmt)` | — | auxiliar de la traducción |
| `input_summ(E)` | — | AERMET `INPUT_SUMM` (mod_reports.f90) |
| `dates_loc(E, i, startdate, enddate, dates1, statid, lat, lon, gmt2lst, elev)` | — | AERMET `DATES_LOC` (mod_reports.f90) |
| `sum_files(E, itype, lwrite, fname)` | — | AERMET `SUM_FILES` (mod_reports.f90) |
| `audit_summ(E)` | — | AERMET `AUDIT_SUMM` (mod_reports.f90) |
| `sfchar_sum(E)` | — | AERMET `SFCHAR_SUM` (mod_reports.f90) |
| `obs_sum(E)` | — | AERMET `OBS_SUM` (mod_reports.f90) |
| `pbl_sum(E)` | — | AERMET `PBL_SUM` (mod_reports.f90) |
| `write_msg(E)` | — | AERMET `WRITE_MSG` (mod_reports.f90) |

### `obs_superficie.py`

módulo SURFACE (estación de superficie).

| Función | Definición | Equivale a |
|---|---|---|
| `class SfInfo` | — | — |
| `class Sf1Min` | — | — |
| `_idiv(a, b)` | División entera de Fortran (trunca hacia cero). | auxiliar de la traducción |
| `sfc_init(E)` | — | AERMET `SFC_INIT` (mod_surface.f90) |
| `surf_path(E)` | — | AERMET `SURF_PATH` (mod_surface.f90) |
| `_getloc_sf(E, i1, user)` | — | auxiliar de la traducción |
| `surf_list(E, i1)` | — | AERMET `SURF_LIST` (mod_surface.f90) |
| `surf_range(E, i1)` | — | AERMET `SURF_RANGE` (mod_surface.f90) |
| `sf_test(E)` | — | AERMET `SF_TEST` (mod_surface.f90) |
| `sf_stage2(E)` | — | AERMET `SF_STAGE2` (mod_surface.f90) |
| `sf_thresh(E, i1)` | — | AERMET `SF_THRESH` (mod_surface.f90) |
| `nws_hgts(E, i1)` | — | AERMET `NWS_HGTS` (mod_surface.f90) |
| `sf_proc(E, ahora)` | — | AERMET `SF_PROC` (mod_surface.f90) |
| `header(E, iunit)` | — | AERMET `HEADER` (mod_onsite.f90) |
| `_indice_asos(s)` | WBAN -> primera posición en la lista ASOS (la búsqueda lineal del original). | auxiliar de la traducción |
| `_asos_por_ids(s, wban, call4, call3)` | Primera posición k de la lista ASOS con iwban == wban, intcall == call4 o usacall == call3 (comparaciones sin blancos), o None. | auxiliar de la traducción |
| `check_asos(E, i_id, sdate, ihr, checkstat, checkhr, aflag, lfound, alias)` | CHECK_ASOS. Devuelve (lfound, asoshr1). Con `alias`, el argumento `lfound` es la propia variable LASOS del módulo (llamadas de extracción del original): lo que la rutina asigna a `… | AERMET `CHECK_ASOS` (mod_surface.f90) |
| `new_obs(E, iyear, imonth, iday, ihr, savedate, savehr)` | NEW_OBS. Devuelve (ihr, iday, imonth, iyear, lgo, iday1, sdate); iday1 None si no cambia. | AERMET `NEW_OBS` (mod_surface.f90) |
| `check_dup(E, iday1, ihr, prcp, tmpd, wdir, wspd, cc1, cc2, sky)` | CHECK_DUP. Devuelve (miss_precip, miss_temp, miss_dir, miss_wind, miss_cloud, writedat). | AERMET `CHECK_DUP` (mod_surface.f90) |
| `read_ishd(E)` | — | AERMET `READ_ISHD` (mod_surface.f90) |
| `_extra_ishd(s, D, ihr, iday1, ishobs, sustituir)` | — | auxiliar de la traducción |
| `_ri(txt)` | read(txt,'(iN)') : entero con blancos ignorados (0 si vacío o no numérico como el FORMAT de Intel con error, que el original no comprueba). | auxiliar de la traducción |
| `_lee_lista(txt, tipos)` | READ(txt,*) sin IOSTAT: el original aborta si falla. | auxiliar de la traducción |
| `_i2_estricto(txt)` | READ(txt,'(i2)') sin IOSTAT (blancos ignorados; | auxiliar de la traducción |
| `read_ghcn(E)` | READ_GHCN: formato GHCN-h separado por barras (11 campos de estación y 53 variables de 6 campos: valor, medida, calidad, tipo de informe, fuente y estación de origen). | AERMET `READ_GHCN` (mod_surface.f90) |
| `_campos_ghcn(datline, partes, npipes, nvar, ploc)` | Subcampos no vacíos (variable, subcampo 1..6, texto) en el orden del original, que los recorre por las posiciones de las barras. | auxiliar de la traducción |
| `_extra_ghcn(s, D, ihr, iday1, rvar, sustituir)` | Techo (12), visibilidad (21) y temperatura húmeda (22) auditados, tras las variables fijas. | auxiliar de la traducción |
| `read_ext(E)` | — | AERMET `READ_EXT` (mod_onsite.f90) |
| `sf_audit(E)` | — | AERMET `SF_AUDIT` (mod_surface.f90) |
| `read_1min(E)` | — | AERMET `READ_1MIN` (mod_surface.f90) |

### `sondeos.py`

módulo UPPERAIR (radiosondeos).

| Función | Definición | Equivale a |
|---|---|---|
| `class Sondeos` | updata1(ivar, nivel, sondeo, día): | — |
| `class SondeosEst` | updata(ivar, nivel, sondeo, día, estación). | — |
| `class SdInfo` | — | — |
| `upper_init(E)` | — | AERMET `UPPER_INIT` (mod_upperair.f90) |
| `upper_path(E)` | — | AERMET `UPPER_PATH` (mod_upperair.f90) |
| `upper_list(E, i1, istation)` | — | AERMET `UPPER_LIST` (mod_upperair.f90) |
| `up_range(E, i1, istation)` | — | AERMET `UP_RANGE` (mod_upperair.f90) |
| `up_modkey(E, i1, istation)` | — | AERMET `UP_MODKEY` (mod_upperair.f90) |
| `up_test(E)` | — | AERMET `UP_TEST` (mod_upperair.f90) |
| `up_stage2(E, istation)` | — | AERMET `UP_STAGE2` (mod_upperair.f90) |
| `up_proc(E, ahora)` | — | AERMET `UP_PROC` (mod_upperair.f90) |
| `header(E, iunit, istation, itype)` | — | AERMET `HEADER` (mod_onsite.f90) |
| `new_sound(E, sdate, ihr, istation)` | NEW_SOUND. Devuelve iday1. | AERMET `NEW_SOUND` (mod_upperair.f90) |
| `_final_extraccion(E, istation, lbad)` | — | auxiliar de la traducción |
| `_anular(u, iday1, istation)` | — | auxiliar de la traducción |
| `read_fsl(E, istation)` | — | AERMET `READ_FSL` (mod_upperair.f90) |
| `fsl_versn(E, datline, nsnding, linetype, pressure, fsl_version, set_conv)` | FSL_VERSN. Devuelve (fsl_version, set_conv, lgood); fsl_version conserva el valor previo en las ramas que no lo asignan (argumento intent(out) sin definir, como el original). | AERMET `FSL_VERSN` (mod_upperair.f90) |
| `read_igra(E, istation)` | — | AERMET `READ_IGRA` (mod_upperair.f90) |
| `read_ext(E, istation)` | — | AERMET `READ_EXT` (mod_onsite.f90) |
| `calc_base(E, istation, sndno, datestr, ikeepbase, pres, pres_conv, missval, ibase, ht_conv)` | — | AERMET `CALC_BASE` (mod_upperair.f90) |
| `up_modify(E, istation)` | — | AERMET `UP_MODIFY` (mod_upperair.f90) |
| `newtemp(E, istation, lv, h, d, v)` | — | — |
| `virt_temp(U, lv)` | — | — |
| `up_audit(E, istation)` | — | AERMET `UP_AUDIT` (mod_upperair.f90) |
| `_fmod(a, b)` | MOD de Fortran (signo del dividendo). | auxiliar de la traducción |
