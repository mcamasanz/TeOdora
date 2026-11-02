# Auditoría galera → odora (2026-11-01)

⚠️ RECTIFICACIÓN (2026-11-02, decisiones del usuario): odora se llama **teOdors** (paquete `teodors`) y se publica una sola vez al final como **0.1.3**, no por bloques ni con otro número (§6). En GitHub es un solo repositorio, con una carpeta por versión exacta y una por planta con su archivo de versión: ver «Migración a teOdors» en `CLAUDE.md`. Este documento conserva el nombre antiguo porque cuenta la auditoría tal como se hizo.

**Pedido del usuario:** llevar a odora todo lo que se pueda replicar para otras plantas y actividades, también la GUI. En galera solo debe quedar la información de esta planta: localización, núcleos urbanos e industriales, elevaciones, usos del suelo, viento local…

**Estado:** solo lectura, no se ha movido nada. Lo comprobado sale del código (grafo de imports con `ast`, sin ejecutar nada). `(D)` significa deducción. Se volvió a comprobar a mano: líneas, constantes de planta, número de importadores, `argparse` al importar, `test_importa` y `conftest` del auditor. En las tablas, `L` es el número de línea; las rutas `odora/…` son relativas a `lib/odora/core`.

**Clave:** **G** genérico tal cual · **P** genérico con parámetros · **D** dato de esta planta · **O** obsoleto o sin uso.

## Resumen
- 13 723 líneas `.py` en `lib/galera` más 73 de `main.py`. Se pueden mover unas 13 100-13 400. En galera quedarían menos de 100 líneas de Python y unos 7,2 MB de datos.
- **Coordenadas fijas en el código: solo 5 sitios** (`penacho_3d.py:53`, `descargar_gfs_historico.py:40`, `descargar_gfs_niveles.py:41-42`, `lidar_planta.py:16`, `viento_local_biblioteca.py:27-28`).
- **El bloqueo real es el acoplamiento:** `gui/config.py` lo importan 42 módulos y fija `DATOS` al importar; `registro` 25, `geo` 16; 23 valores por defecto ligados a `config` al definir la función; 3 tareas con `argparse` al importar.
- **Constantes de planta escondidas:** `validacion.py:63-66` (ventana de 11,4-12,6 h UTC, solo vale para esta longitud) y `descargar_gfs_niveles.py:41-42` (`I = slice(0, 5)` en una malla 0-360: al oeste de Greenwich no basta con cambiar números).
- **Elevaciones, usos y núcleos NO están en `lib/galera`:** viven en `DATOS/terreno/<caso>/` (`elevacion.tif`, `usos.tif`, `corine.gpkg`, `nucleos_nombres.json`) y los núcleos se calculan al vuelo.
- **Auditor de odora:** ninguna regla prohíbe dependencias, nombres ni binarios. El choque real es `test_paquete.test_importa`: importa TODOS los módulos con solo `.[pruebas]` instalado.

## 1. Fichero a fichero
### Raíz y `lib/galera`
| Fichero · función | Líneas | Clase | Incrustado | Destino |
|---|---|---|---|---|
| `main.py` · lanzador Qt | 73 | P | L2 nombre; L29 `ENCE_GALERA_MODO`; L34,54,57 `galera.gui`; L50 `CIRCE.ENCE.LaGalera` | `odora/gui/__main__.py` (`--planta <carpeta>`). Queda un main de ~10 líneas |
| `__init__.py` · versión y `sys.path` | 26 | D | L16; L24-26 `lib/paquetes` | Se queda, reducido |
| `geo.py` · envoltorio con EPSG fijo | 43 | P | L8; L11-41 | Desaparece: `odora.comun.geo` con `planta.epsg` explícito |

### `lib/galera/entradas`
| Fichero · función | Líneas | Clase | Incrustado | Destino |
|---|---|---|---|---|
| `terreno.py` · MDT IGN, CORINE, núcleos, CartoCiudad, capas | 569 | P | L34 `EPSG:25830` (del servicio); L97,111,407 resolución; 9 usos de `EPSG_UTM`; L212,215 CORINE; L159,359 agente HTTP; L447 `info["planta"]` | `odora/fuentes/{ign,corine,cartociudad,terreno}.py`, `comun/mercator.py`, `gui/capas.py` |
| `edificios.py` · WFS Catastro | 278 | P | L36; radios; L81 agente; L264 | `odora/fuentes/catastro.py`; `geojson_mapa` a gui |
| `estaciones.py` · Meteocat | 211 | P | L25-26 URLs; L64,144,184 `radio_km=20`; L104 fecha; L191 fichero | `odora/fuentes/meteocat.py`, con interfaz de proveedor |
| `meteo.py` · ERA5 del CDS | 597 | P | Sin coordenadas; L76-78 clave; L264 ruta; años | `odora/fuentes/era5.py` |
| `openmeteo.py` · modelos en puntos | 126 | O | 0 importadores; API gratis no comercial | Decisión 1 |

### `lib/galera/viento`
| Fichero · función | Líneas | Clase | Incrustado | Destino |
|---|---|---|---|---|
| `local.py` · masa consistente con estelas | 407 | G | Solo comentarios | `odora/meteo/viento_local/modelo.py`, sin validar; añade scipy |
| `validacion.py` · métricas, rosas | 330 | P | L52-53, **L63-66**; L272; L295 arrastra folium y Qt; L288-330 sin uso | `odora/metricas/{viento,figuras}.py`; `convencion(df, lon)` debe calcular el mediodía solar |

### `lib/galera/gui`
| Fichero · función | Líneas | Clase | Incrustado | Destino |
|---|---|---|---|---|
| `config.py` · emplazamiento, dominio, carpetas | 156 | D + P | L13-14; L21; L24-28; L32,69-70,80-81; L39-40; L46-60; L99-103; L134-136 | `odora/planta.py` (clase `Planta`) + `planta.json` |
| `registro.py` | 48 | P | L10, L32 | `odora/comun/registro.py` |
| `escalas.py` | 46 | G | — | `odora/gui/escalas.py` |
| `normativa.py` | 132 | P | L20 ruta | `odora/operacion/normativa.py` |
| `focos.py` | 461 | P | L131-154 config; L62-78 `TIPOS` | `odora/operacion/focos.py`; `TIPOS` ampliable por planta |
| `escenarios.py` | 189 | P | L40 Madrid; L159,181 | `odora/operacion/planes.py` |
| `periodos.py` | 128 | P | L28; L83-84; L110-125 | `odora/operacion/periodos.py` |
| `planes_calculo.py` | 432 | P | **L34 fechas**; L61; L429; L317 | `odora/operacion/simulacion.py` |
| `penacho_mapa.py` | 87 | G casi | L14; L44; L75-80 | `odora/gui/imagenes.py` |
| `receptores_mapa.py` | 72 | P | L27-28 `NIVELES`; textos | `odora/preparacion/receptores.py` |
| `viento_mapa.py` | 154 | P | L24-28; L73 | `odora/gui/viento_mapa.py` |
| `penacho_3d.py` | 351 | P | **L53**; L52; L126; L247-249; L343; L36 GUI→tarea | `operacion/penacho_3d.py` + `gui/visor3d.py` |
| `tema.py` | 500 | P | L131; L225; Qt al importar | `odora/gui/tema.py` |
| `mapa_web.py` | 1151 | P | 71 líneas `ence`; L21-41 fondos; L1035 zoom | `odora/gui/mapa_web.py`; `fondos` por planta |
| `mapa.py` | 214 | G | 26 líneas `ence` | `odora/gui/mapa.py` |
| `focos_mapa.py` | 281 | P | 17 líneas `ence`; L185,187 | `odora/gui/focos_mapa.py` |
| `panel.py` | 1053 | P | L54; L165,332; L323; **L497**; L706; L744; **L790-791** | `odora/gui/panel.py` |
| `ventana.py` | 1097 | P | L49,211; L171,264,269; L434-462 Meteocat; L588; L651,902; L664; L694-709; L727,763; L1087-1097 créditos | `odora/gui/ventana.py`; créditos y proveedor desde la planta |
| `ventana_focos.py` | 790 | G casi | L17; L533-534 | `odora/gui/` |
| `ventana_planes.py` | 659 | G casi | L22; L200 | `odora/gui/` |
| `ventana_ajustes.py` | 349 | G casi | L12; L181 | `odora/gui/` |
| `consola` 110 · `terminal` 79 · `trabajos` 44 · `web` 74 · `widgets` 101 · `vista_3d` 46 · `vista_previa` 39 | 493 | G | `trabajos` L9,35,44 (`terreno`); `web` L8-9; `vista_previa` L14 | `odora/gui/` |

### `lib/galera/gui/tareas`
| Fichero · función | Líneas | Clase | Incrustado | Destino |
|---|---|---|---|---|
| `control_fuentes.py` | 154 | G casi | L23-24 | Ampliar `odora/preparacion/puffs/control.py`; `geometria` a `operacion/focos.py` |
| `viento3d_casos.py` | 318 | P | L30-32; L82; L166; L232; L258-260 y L290 restos | `odora/preparacion/viento3d/casos.py` |
| `gfs_columnas.py` | 70 | P | L23; L17,20 arrastres; L33 | `odora/preparacion/viento3d/gfs.py` |
| `viento3d_series.py` | 70 | P | L28 8 códigos; L29; L34 | `odora/preparacion/viento3d/series.py` |
| `viento_dia_local.py` | 226 | P | L31; L44-45 al importar; L62-64; L137; L140 | `odora/operacion/viento_periodo.py` |
| `respuestas_dia.py` | 179 | P | L32,34; L37-39 al importar; L77; L123 | `odora/operacion/respuestas.py` |
| `descargar_era5` 41 · `descargar_meteocat` 28 | 69 | G casi | Rutas caducas | `odora/fuentes/` |
| `descargar_gfs_niveles.py` | 144 | P | **L41-42**; L37-38; L102; L31 pygrib | `odora/fuentes/gfs_noaa.py`; caja desde el emplazamiento, con cruce 0-360 |
| `descargar_gfs_historico.py` | 131 | P | **L40**; L37; L15-17 | `odora/fuentes/gfs_dynamical.py` (icechunk exige Python ≥ 3.12) |
| `lidar_planta.py` | 51 | P | **L16**; todo se ejecuta al importar | `odora/fuentes/lidar.py`, como función |
| `f1_estacion.py` | 190 | P | **L32 `{"C9": "2025-06-01"}`**; L127; L93 | `odora/metricas/calidad.py`; L32 a la planta |
| `mos_tabla` 166 · `mos_entrenar` 169 | 335 | P | L34; L35; L41; L40; L151 | `odora/meteo/mos/`; la app no los usa |
| `viento_local_biblioteca.py` | 67 | P | **L27-28**; L29-31; L38 | `odora/meteo/viento_local/biblioteca.py` |
| `ejemplo_configuracion.py` | 52 | P | L21-22 | `odora/gui/ejemplo.py` |
| `penacho_dia` 155 · `puffs_casos` 69 | 224 | O | La app no los lanza | Decisión 1 (quitar el retroceso de `penacho_mapa.py:75-80`) |

### Datos y recursos
| Ficheros | Clase | Destino |
|---|---|---|
| `planta/emplazamiento.json`, `focos.json`, `receptores.json`, `normativa.json`, `viento_local.npz` (6,37 MB) | D | Se quedan |
| `planta/rutas.json` | D de máquina | Se queda, fuera de `planta.json` |
| `recursos/iconos/` | G | `odora/gui/recursos/iconos/` |
| `recursos/visor3d/three.min.js`, `OrbitControls.js`, `LICENSE-three.txt` | G | `odora/gui/recursos/visor3d/` |
| `recursos/visor3d/plantilla.html` | P (L42, crédito PNOA) | `odora/gui/recursos/visor3d/`, crédito por planta |
| `recursos/visor3d/ortofoto.jpg` (±3,2 km) | D | Se queda. Ningún código de `lib` la genera: falta `odora/fuentes/pnoa.py` |
| `recursos/ejemplo/*` | D | Se queda |

## 2. Odora hoy
- `core`: `comun` (solo `geo`), `terreno`, `meteo`, `dispersion`, `preparacion`. No existen `fuentes` ni `gui`. v0.1.2; `odora_dev` sin trabajo posterior.
- Dependencias: numpy, numba, rasterio, pyproj; extras `preparacion` y `pruebas`. Licencia propietaria. `packages` es una lista explícita y no hay `package-data` (D: un wheel no llevaría html, js ni svg).
- `PENDIENTES` §3 ya prevé fuentes y métricas; no prevé GUI, viento local ni tareas. §2.1 prevé `identidad.py`, que encaja con el bloque `identidad` de abajo.

**Solapes:** `geo.py` / `comun.geo`, `viento3d_casos.{rejilla, en_punto, leer…}` / `preparacion.viento3d.*`, `receptores_mapa.malla` / `malla_anidada` son envoltorios. `control_fuentes` amplía `puffs.control`. ⚠️ `validacion.a_horario` y `estaciones.medias_horarias` son casi iguales, no idénticas (`n == 2` frente a `n >= 1`): no fundir sin medir. `f1_estacion.elevacion_solar` y `viento3d.sol.seno_elevacion`: mismo fin, otra fórmula.

**Repetido dentro de galera:** `cota()` 3 veces, HTTP con reintentos 5 versiones, formatos de número 8 funciones, dirección desde u, v 3 veces.

## 3. Choques con el auditor y la licencia
| Regla | Efecto | Cómo resolverlo |
|---|---|---|
| R2 + `test_importa` | **Choque principal.** Fallan los imports de nivel superior de PySide6 (13 módulos), folium (2), scipy, xarray, pygrib, sklearn, joblib, laspy, y las tareas con `argparse` al importar | Imports perezosos, extras nuevos y CI con ellos, o filtrar `MODULOS` |
| R2, trampa de los saltos | `pytest.skip()` dentro de una prueba cuenta como fallo (`conftest.py:46-47` y `reglas.py:102`) | `skipif` o `importorskip` de módulo |
| R3 | 20 s por prueba, 300 s en total. `local._sor` tiene `cache=False`; `web._descarga` espera hasta 40 s sin red | Dominio mínimo o marca `compilacion`; simular la red |
| R4 | Mover cuenta como añadir, pero es débil: basta una prueba que nombre un módulo o «paquete» | Exigirse más que la regla |
| R1, R5, R6 | Sin efecto mientras no cambien las salidas de los motores; `test_version` exige cambiar el número | — |

**Hay que cambiar lo escrito:** `README.md:186-188` («las interfaces de cada proyecto se construyen encima»), `CLAUDE.md` («si conecta la GUI con odora, a gui/»), «8 motores validados» (`viento_local` es un prototipo: no entra en `MOTORES`). (D) digicompost no debe heredar Qt: la GUI tiene que ser extra.

**Licencia:** `LICENSE` prohíbe copiar «total o parcialmente» y no contempla terceros: three.js (MIT) necesita excepción expresa. `web.py:8-9` y la guía 10 piden `THIRD-PARTY-NOTICES`, que **no existe**. PySide6 es LGPL: la guía 10 pide modo carpeta y DLL sustituibles, frente a «Nuitka» en `PENDIENTES` §2.4 (aclararlo antes de empaquetar). PNOA exige crédito. Open-Meteo gratis es no comercial. Catastro: solo dato transformado.

## 4. Dependencias y estado global
- **Ciclos:** ninguno entre módulos. Sí entre paquetes: gui ↔ entradas, gui ↔ geo, gui ↔ viento, gui ↔ tareas.
- **Arrastres que romper antes:** `gfs_columnas` → `mos_tabla` y `descargar_gfs_niveles` (trae pygrib); `mos_entrenar` → `f1_estacion`; `ventana_focos` → `panel._num`; `ventana_ajustes` y `ventana_planes` → `ventana_focos` (trae folium); `validacion` y `f1_estacion` → `mapa_web.COLORES_VEL`; `penacho_mapa` → `terreno._a_mercator`; `trabajos` → `terreno`; `penacho_3d` → `control_fuentes`; `respuestas_dia` y `viento_dia_local` → `focos`, `receptores_mapa`, `penacho_mapa`.
- **Efectos al importar:** `config.py:79-81` fija `DATOS` y `LOCAL`; 23 valores por defecto; `argparse` en `penacho_dia:38`, `respuestas_dia:37`, `viento_dia_local:44`; `lidar_planta` entero; `sys.stdout.reconfigure` en 8 ficheros; `sys.path.insert` en 16; 12 imports por nombre suelto.
- **Rutas que se rompen al mover:** `config:21,24`, `normativa:20`, `penacho_3d:42`, `penacho_mapa:14`, `periodos:28`, `viento_mapa:73`, `vista_previa:14`, `ejemplo_configuracion:13,21`, `viento_local_biblioteca:19,38`, y `config.RAIZ/lib/paquetes` en 4 lanzadores.
- **Estado de módulo:** `tema.T`, `tema.avisos`, `meteo._INDICE_CDS`, `lru_cache` de `viento_mapa`.

## 5. Lo que queda en galera: el paquete de planta
`main.py` (~10 líneas), `planta/planta.json` (nuevo), `focos.json`, `receptores.json`, `normativa.json`, `rutas.json`, `viento_local.npz`, `ortofoto.jpg`, `ejemplo/`, y su carpeta `DATOS` (terreno, edificios, meteo, series). (D) No conviene renombrar `DATOS` ni `ENCE_Galera` en QSettings: se perdería la caché y la disposición de ventanas.

| Bloque de `planta.json` | Campos | Hoy en |
|---|---|---|
| `identidad` | `app_nombre`, `organizacion`, `app_id`, `ajustes`, `prefijo_env`, `agente_http`, `registro` | `config:13-14`, `main:50`, `tema:131`, `registro:10` |
| `emplazamiento` | `nombre`, `lat`, `lon`, `fuente`, `rotulos` | `emplazamiento.json`, `penacho_3d:53` |
| `proyeccion` | `epsg`, `crs_geo`, `zona_horaria` | `config:39-40`, `escenarios:40`, `panel:54` |
| `dominio` | `lado_km`, `margen_m`, `res_terreno_m`, radios de edificios, `celda_viento_m`, `zface` | `config:46-59` |
| `receptores` | `niveles`, `por_km2` | `receptores_mapa:27-28`, `config:60` |
| `reanalisis` | `anios` (de ahí `INICIO`, `FIN`, fecha mínima, textos) | `config:103`, `planes_calculo:34`, `panel:497,790` |
| `fuentes` | `mdt`, `usos`, `corine_gpkg`, `edificios`, `fondos`, `creditos` | `terreno`, `config:128-140`, `mapa_web:36-41`, `ventana:1087-1097` |
| `estaciones` | `proveedor`, `radio_km`, `codigos`, `objetivo`, `ceros_sospechosos` | `estaciones:64`, `viento3d_series:28`, `mos_tabla:34`, `f1_estacion:32,127` |
| `pronostico` | `caja_gfs`, `n_col`, `paso_col_m`, `semanas_mos` | `descargar_gfs_*`, `gfs_columnas:23` |
| `series` | `era5`, `gfs`, `preferidas`, `titulos`, `r1_km`, `rmax_km` | `viento_mapa:24-28`, `viento_dia_local:62,137` |
| `viento_local` | `puntos`, `radio_m`, `radio_borde_m`, `margen_m`, `dx`, `dz`, `alto_m`, `lidar` | `viento_local_biblioteca:27-35`, `lidar_planta:16` |
| `visor3d` | `ortofoto`, `semilado_m`, `credito` | `penacho_3d:52`, `plantilla.html:42` |
| `operacion` | `tipos_foco_extra`, `modo_edicion` | `focos:62`, `config:32` |

⚠️ RECTIFICACIÓN (2026-11-02, tanda 2): en `viento_local`, `lidar` es la ruta de las rejillas, relativa a DATOS, y se añade `biblioteca`, relativa a la carpeta de la planta. La zona de `lidar_planta:16` queda para la tanda 3.

⚠️ RECTIFICACIÓN (2026-11-02, tanda 3): de `viento_local`, la zona ya está, como `lidar_zona`, con `lidar_teselas`. En `estaciones`, nuevo `agente_http` (el de Meteocat es otro) y sin `proveedor`: solo hay uno y nada lo leería. En `pronostico`, solo `caja_gfs` y `semanas_mos`; `n_col` y `paso_col_m` van con `gfs_columnas`, en la tanda 5. En `fuentes` no se añade nada: los créditos que hay en el código movido son del servicio y se quedan con él; los de `mapa_web` y `ventana` van con la GUI. El destino de `terreno.py` no se parte en 4 ficheros (`ign`, `corine`, `cartociudad`, `terreno`) y `geojson_mapa` e `imagenes_mapa` siguen con sus fuentes hasta la tanda 8. El extra de ERA5 es `ecmwf-datastores-client`, que es lo que se importa.

⚠️ RECTIFICACIÓN (2026-11-02, tanda 4): `validacion.py` no se parte en `viento` y `figuras`: va entero a `metricas/viento.py`, y `f1_estacion.py` a `metricas/calidad.py`. Ya no existen `validacion.comparar` ni los arrastres `mos_entrenar` → `f1_estacion` y `validacion` → `mapa_web` que cita esta auditoría: se fueron en la tanda 0. La ventana de `validacion.py:63-66` no pasa a `convencion(df, lon)`, sino a `convencion(df, mediodia_h)`: en `estaciones`, nuevo `mediodia_utc_h` (aquí 12,0, como estaba en el código), y sin él, el mediodía solar en la longitud del emplazamiento. Sin extra propio: pandas y matplotlib ya están en `preparacion` y `mapas`.

⚠️ RECTIFICACIÓN (2026-11-02, tanda 5): los destinos en `preparacion` de `viento3d_casos`, `gfs_columnas` y `receptores_mapa` no valen: usan la planta y las fuentes, y `test_los_motores_no_dependen_de_ninguna_planta` lo prohíbe allí. Van a un paquete nuevo, `casos` (`viento3d`, `gfs_columnas`, `receptores`). `control_fuentes` no amplía `puffs/control.py`: va entero a `preparacion/puffs/control_fuentes.py`; `geometria` sigue con él, con el módulo de los focos por parámetro, y se decide en la tanda 6 si pasa a `operacion/focos.py`. En `series`, solo `r1_km` y `rmax_km`: `era5`, `gfs`, `preferidas` y `titulos` los lee código de la tanda 6. Nuevos: `identidad.nombre_casos` (las cabeceras de los ficheros) y `receptores.estilos`. Sin extra propio: `teodors[fuentes]`.

⚠️ RECTIFICACIÓN (2026-11-02, tanda 6): `penacho_mapa` y `viento_mapa` no van a `gui/`, sino a `operacion/` con su nombre, porque no necesitan Qt. `viento_dia_local` pasa a `operacion/viento_periodo.py`, `respuestas_dia` a `operacion/respuestas.py`, y `viento3d_series` y `ejemplo_configuracion` a `operacion/`, con su nombre. `geometria` de `control_fuentes` pasa a `operacion/focos.py`, sin el módulo por parámetro. `pagina` de `penacho_3d` se queda en galera hasta la tanda 8: usa `tema`; `operacion.penacho_3d.abrir` y `calcular` devuelven los datos y el envoltorio monta la página. Los iconos van con el código (`operacion/recursos/iconos/`). Nuevos en `planta.json`: `proyeccion.zona_horaria`; `series.era5`, `gfs`, `preferidas`, `titulos` y `dia_prueba` (el `--dia` por defecto de `respuestas_dia`); `operacion.tipos_foco_extra` y `ejemplo`; y el bloque `visor3d`, con `rotulos`, que no van en `emplazamiento`. ⚠️ `panel.py:43` sigue con su propia `ZoneInfo("Europe/Madrid")`: es Qt, va con la tanda 8.

⚠️ RECTIFICACIÓN (2026-11-02, tanda 7): el MOS no va a `meteo/mos/`, sino a un paquete propio, `mos` (`tabla`, `entrenar`): usa la planta y `fuentes`, y `test_los_motores_no_dependen_de_ninguna_planta` lo prohíbe bajo `meteo/`. En `pronostico`, nuevo `mos_hasta`. El extra lleva lo que se usa de verdad, medido bloqueando cada módulo: también `dask[array]` (`open_mfdataset`) y `scipy` (`interp` de xarray). Ya no existe el arrastre `gfs_columnas` → `mos_tabla` que cita esta auditoría: se fue en la tanda 0. Las semanas de `pronostico.semanas_mos` no las lee el MOS, sino `fuentes.gfs_noaa`: eran de la prueba «dejando una estación fuera», ya borrada.

⚠️ RECTIFICACIÓN (2026-11-02, tanda 8): `main.py` no pasa a `gui/__main__.py` con `--planta`: la planta se activa en su `main.py` y este llama a `gui/principal.py`. `viento_mapa`, `penacho_mapa` y `escalas` ya estaban en `operacion` y `comun` (tanda 6 y 1): no van a `gui/`. `pagina` va a `gui/penacho_3d.py`, no a `gui/visor3d.py`. El bloque `reanalisis` ya existía. En `identidad`, nuevos `version`, `entidad` y `red_datos`. En `fuentes`, `mdt`, `usos`, `edificios` y `nombres_nucleos` son cómo la interfaz llama a cada servicio, no la fuente de los datos; el código de descarga sigue siendo el de `fuentes`. `estaciones.proveedor` vuelve, porque ya hay quién lo lea. En `operacion`, nuevo `texto_modo_edicion`, y `modo_edicion` también es la opción de `main`. `trabajos`, `web` y `vista_previa` no llevaban nada propio salvo la carpeta del ejemplo.

## 6. Orden por tandas
Cada tanda: rama en `odora_dev`, auditor APTO, fijar `lib/odora` y comparar frente a una línea base (viento del 2026-10-21 y plan «base»). Dejar reexportaciones en galera hasta el final mantiene viva la app (D). Las pruebas son una estimación.

| Tanda | Contenido | Líneas | Pruebas (D) | Extras |
|---|---|---|---|---|
| **0** Preparar, en galera | Confirmar lo pendiente; decidir lo obsoleto; sacar `main()` de las tareas; quitar `sys.path` y nombres sueltos; romper arrastres | 0 (~50 ficheros) | Línea base | — |
| **1** Base | `odora/planta.py`, `comun/{registro,formato,red,mercator,procesos}`, `escalas`; `geo` desaparece | ~350 | ~100 | — |
| **2** Viento local | `local`, `viento_local_biblioteca` | 474 | ~80 | scipy |
| **3** Fuentes | `entradas/*`, descargas, `lidar_planta` | 2 050 | ~350, sin red | `fuentes`, `lidar` |
| **4** Métricas | `validacion`, `f1_estacion` | 477 | ~150 | matplotlib |
| **5** Casos | `control_fuentes`, `viento3d_casos`, `gfs_columnas`, `receptores_mapa` | 614 | ~200 | — |
| **6** Operación sin Qt | `normativa`, `focos`, `escenarios`, `periodos`, `planes_calculo`, `penacho_mapa`, `viento_mapa`, `respuestas_dia`, `viento_dia_local`, `viento3d_series`, `ejemplo_configuracion` | 2 110 | ~350 | — |
| **7** MOS (opcional) | `mos_tabla`, `mos_entrenar` | 335 | ~60 | `mos` |
| **8** GUI Qt | Todo lo de Qt, recursos y `main` | 6 938, sobre todo mecánico (~40 puntos de marca o texto, y renombrar `ence`) | ~100 de humo | `gui`, `gui3d` |
| **9** Cierre | Galera solo datos; 21 scripts de `99-Test`; LICENSE, NOTICES, README, CLAUDE.md | 0 | — | — |

**Añadido a la auditoría (no sale de ella):** para que replicar sea «reajustar la localización» de verdad falta algo que hoy no existe: un comando que, con unas coordenadas, cree el paquete y `DATOS` de una planta nueva (terreno, usos, núcleos, edificios, ortofoto, estaciones cercanas, LiDAR y biblioteca de viento local). Sin eso, hoy son pasos sueltos. Iría al final de la tanda 8. Y las fuentes son españolas: IGN, PNOA, Catastro, CORINE vale para Europa, Meteocat solo para Cataluña.

## 7. Código frente a documentos (a corregir)
- `odora/docs/arquitectura.md` dice «por partes, las fuentes de datos»: no hay ninguna. `PENDIENTES.md` lleva la cabecera «Estado de la v0.1.0».
- `gui/tareas/__init__.py` dice que se lanzan a mano: la app lanza dos. `descargar_gfs_historico.py:18` dice «no importa nada de galera» y L35 lo importa.
- Rutas caducas: `descargar_era5.py:6`, `descargar_meteocat.py:5`, `viento_dia_local.py:6`. `penacho_dia.py:6` y `puffs_casos.py:8` dicen que no hay focos.
- Sin llamador: `validacion.comparar`, `terreno.recortar`, `meteo.estado_cache`.
- Restos de nombres de terceros (regla 11), en comentarios: `meteo:16`, `openmeteo:82`, `config:47,92`, `descargar_gfs_niveles:2`, `validacion:9,290`.
