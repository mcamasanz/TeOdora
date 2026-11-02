# ENCE Tarragona — herramienta de dispersión de contaminantes y olores

> ⚠️ **RECTIFICACIÓN (2026-11-02): el proyecto se ha reorganizado, y odora se llama teOdors.** Esto vive en el repositorio https://github.com/mcamasanz/TeOdora.git, en la carpeta `galera/`. Lo que sigue se escribió
> antes y conserva los nombres de entonces (regla 6). Cuando diga… léelo como:
>
> | Dice | Ahora |
> |---|---|
> | `odora`, `lib/odora/core` | `teodors`, `../v0.1.3/core` (la versión, en `VERSION`) |
> | `lib/galera/gui/planta/` | `entrada/` |
> | `DATOS/terreno`, `DATOS/edificios` | `entrada/terreno`, `entrada/edificios`: van con la planta. En DATOS, solo los cálculos |
> | `DATOS/viento_local/planta_1m.npz`, `gui/planta/viento_local.npz` | `entrada/viento_local/` |
> | `gui/recursos/ejemplo`, `gui/recursos/visor3d/ortofoto.jpg` | `entrada/recursos/` |
> | `lib/galera/gui/*.py`, `gui/tareas/*.py`, `entradas/`, `viento/` | en `../v0.1.3/core`: `gui`, `operacion`, `casos`, `fuentes`, `metricas`, `mos`, `planta`. Ya no queda código en la planta |
> | `planes_calculo`, `escenarios`, `respuestas_dia`, `viento_dia_local` | `operacion.simulacion`, `operacion.planes`, `operacion.respuestas`, `operacion.viento_periodo` |
> | `window.ence`, clases `ence-*` | `window.mapaApp`, clases `mapa-*` |
>
> Cómo se organiza y cómo se trabaja: `../README.md`. Los datos de entrada y sus créditos: `README.md`. **Abrir la app:** `C:\e2s\python.exe main.py`, desde esta carpeta. Para cambiar el núcleo, una versión nueva: una publicada no se toca.
> Los scripts `99-Test/10_migracion/comparar_movidos*.py` y `07_isosuperficies/*_f1cfddb.py` son historia: miran commits antiguos y ya no se lanzan.

## 1. Qué se construye

Herramienta en **Python** que simula la dispersión de contaminantes y olores de la planta de
**biometano + compostaje de ENCE en La Galera (Montsià, Tarragona)** en tres horizontes, y que
acabará funcionando como **servicio en el ordenador de un operario** de la planta.

**El emplazamiento es fijo.** Terreno, uso del suelo y meteo de reanálisis se descargan UNA vez
para un dominio extenso (por defecto 50 km de lado) y luego se recortan al dominio de cálculo.

- Planta: antigua Biometagàs La Galera S.L., comprada por ENCE en dic. 2024, ~5 ha, hasta 50 GWh/año.
  ⚠️ RECTIFICACIÓN (2026-10-30): ENCE publica «diseñada para producir hasta 45 GWh» (julio de 2026);
  confirmar la cifra con ENCE, y también si hoy hay compostaje (la prensa leída no lo menciona).
- **Quejas (contraste de prensa, 2026-10-30):** el foco es Santa Bàrbara (≈ 3 km al NNE) y hay OTRA
  fuente cerca, Biosansa CatSud (secado de sansa). La auditoría de 2024 no vio incumplimiento, pero sí
  molestias. Detalle y qué pedir a ENCE: `docs/contexto_quejas_olores.md`.
- **Coordenadas FIJAS de la planta (dadas por el usuario):** **40.6905923 N, 0.4764197 E**
  (UTM 31: 286 763, 4 507 474 m), ~1,5 km al NE del núcleo de La Galera. Guardadas en
  `lib/galera/planta/emplazamiento.json`. **La planta NO se mueve desde la app** (se quitó «Fijar planta en
  el mapa» a petición del usuario: con él se movió por error 9,3 km el 2026-10-14 y se restauró).
  No cambiarlas sin que lo pida el usuario. (Las 40° 40′ 54″ N, 0° 27′ 48″ E que se dieron antes
  eran las del pueblo, no las de la planta.)
- No es Tarragona ciudad: está a 0,46° E (huso 31), a ~13 km de la costa. Un dominio de 50 km
  incluye el **delta del Ebro y mar** al este y las estribaciones de **Els Ports** al noroeste.
- CORINE ya existe en este PC (no hay que descargarlo):
  `Escritorio\Mountains\inundaciones\src\data\usos\CLC2018_ES.gpkg` (y copias en PyroSmoke, stl).

| Horizonte | Meteo de entrada | Motor |
|---|---|---|
| **Pasado** (reanálisis) | ERA5 + las 8 estaciones de Meteocat (2021-2025) | odora `viento3d` (≡ CALMET) → odora `puffs` (≡ CALPUFF) |
| **Presente** | ⚠️ por decidir con el usuario (ver §6) | — |
| **Futuro** (predicción) | GFS 0,25° ciclo 00Z, ≤ 120 h (+ MOS en las estaciones) | odora `viento3d` → odora `puffs` |

Punto de partida: el material de CIERZOFLOW (olores de compostaje en Gimenells, Lleida) del antiguo
`cajon_reutilizable/`. **Se borró el 2026-10-22** (decisión del usuario) tras rescatar lo útil a
`docs/` (ver §2 y `docs/README.md`).

## 2. Dónde mirar primero

**Regla:** si la pregunta o la tarea toca uno de estos temas, abre **primero** el fichero indicado
antes de responder de memoria, investigar fuera o escribir código nuevo. Si no lo cubre, dilo.

| Si la pregunta va de… | Leer primero |
|---|---|
| Focos de la planta, qué pedir a ENCE | `docs/guias_cajon/00_ARRANQUE_ENCE_TARRAGONA.md` (§2.3) |
| Quejas vecinales, pueblos afectados, auditoría de olor de 2024, otras fuentes cercanas, receptores sensibles | `docs/contexto_quejas_olores.md` |
| Emisiones, ou_E ↔ g, pilas, volteos, factores de emisión | `docs/guias_cajon/06_olores_emisiones_criterios.md`, `docs/emisiones/` |
| P98, criterios de olor, normativa (Cataluña, UE, Italia), límites de inmisión | `docs/referencias/normativa/` + guía 06 |
| Un error, un aviso de la EPA, un resultado absurdo | §5 de este fichero (lo medido aquí) y `docs/guias_cajon/09_lecciones_aprendidas.md` |
| Licencias, redistribución, qué se puede entregar a ENCE, precios | `docs/guias_cajon/10_licencias_y_precios.md` |
| Teoría (gaussiano, estabilidad, Monin-Obukhov, z0…), uso de la app, informes | `docs/guias_cajon/theory_guide.md`, `user_guide.md` |
| Los motores (viento3d, puffs, penacho…) y sus límites | `lib/odora/README.md`, `lib/odora/PENDIENTES.md`, `lib/odora/docs/` |
| Qué se mueve de galera a odora, qué se queda y en qué orden | `docs/auditoria_galera_odora.md` |
| Huso, datos de entrada, receptores, mapas, app, rendimiento | §5 de este fichero |

⚠️ Las guías del cajón son históricas (hablan de los .exe y de rutas que ya no existen): si
discrepan del código, manda el código (regla 6).

## 3. Reglas no negociables (cada una ya costó un error real)

1. **Unidades de emisión.** AREA/AREAPOLY de AERMOD y las áreas de CALPUFF van en **g/(s·m²) por m²**.
   Una fuente en ou_E lleva siempre su `factor` (µg/m³ por ou_E) pegado. Comprueba SRCPARAM y el
   subgrupo 14b con `docs/emisiones/olor_fuentes.py`. Dos errores de ×10⁶–10⁸ salieron de aquí.
2. **El P98 sale de la serie horaria y sobre horas válidas**, nunca del CSV de medias por receptor ni
   contando calmas como cero.
3. **Huso UTM:** una sola constante, `lib/galera/gui/config.py → EPSG_UTM = "EPSG:25831"`. En La Galera
   la convergencia es **γ = −1,65°** (≈ 200 m de desvío a 7 km) en 25831 y +2,26° en 25830:
   ningún huso la anula, así que el viento del `.sfc` de AERMOD se gira SIEMPRE con
   `galera.geo.dir_geo_a_rejilla`. Al reutilizar código del cajón, quitar cualquier 25830 fijo.
4. **OneDrive** bloquea y borra ficheros: ejecutables, canales de control y caché van en `%TEMP%` o en
   una ruta local. Este propio proyecto está en OneDrive.
5. **Ante un aviso o error de la EPA, primero su código fuente** (`aermod_source.zip`), después la teoría.
6. **Si una guía y el código discrepan, manda el código.** Si una afirmación escrita resulta falsa,
   se marca «⚠️ RECTIFICACIÓN» y no se borra en silencio.
7. **Nunca claves de API** en el repositorio ni en paquetes (`src/config/keys/`). Cada usuario pone
   las suyas (CDS, AEMET).
8. **Los ejecutables de CALPUFF no se entregan al cliente** (EULA de Lakes). Por eso los motores
   son odora (propios, 2026-10-18) y los .exe de terceros quedan SOLO para validaciones
   secundarias, fuera del proyecto: `%LOCALAPPDATA%\CIRCE\terceros`. Desde el 2026-10-23 la
   herramienta ya no los lanza (las funciones `*_exe` están en el zip de archivo).
   Licencias: `docs/guias_cajon/10_licencias_y_precios.md`.
9. **Dominio FIJO** (decisión del usuario): no hay control de dominio en la interfaz. Es todo el
   terreno descargado (50 × 50 km) y el cálculo usa `config.RADIO_CALCULO_KM` = 24,5 km al centro
   (500 m de borde para AERMAP). Se expresa como DISTANCIA AL CENTRO (mitad del lado); el cajón
   usaba el LADO: al reutilizar su código, `lado = 2 · distancia`.
10. **Medir antes de afirmar y validar contra una referencia externa.** Un número plausible no
    demuestra nada.
11. **Sin nombres de programas de terceros** (decisión del usuario, 2026-10-23): ni CALMET,
    CALPUFF, AERMOD, MAKEGEO… en módulos, funciones, ficheros de caso ni textos de la herramienta;
    se usan los nombres de los motores de odora (viento3d, puffs, penacho, geofisica…). Código nuevo
    con nombres neutros desde el principio; al tocar un módulo con nombre de tercero, renombrarlo.
    El .exe solo se nombra donde se lanza para validación secundaria (`puffs.EXE`).

## 4. Entorno

- Intérprete con el geostack completo: `C:\e2s\python.exe` (Python 3.11). Ejecutar con
  `PYTHONIOENCODING=utf-8` (la consola cp1252 rompe con γ, emojis o «·»).
- Ejecutables de terceros (solo validaciones secundarias): `%LOCALAPPDATA%\CIRCE\terceros`
  (aermap, aermod, bpipprm, calmet, calpost, calpuff, makegeo; rescatados del cajón el 2026-10-22,
  comprobados byte a byte). Se lanzan desde ahí (`calmet.exe_tercero`); ya no se copian a TEMP.
- No están en el proyecto: CORINE (`CLC2018_ES.gpkg`, ~3 GB) ni las claves.
- Respuestas y documentación en **español**, a nivel de 1.º de ingeniería (estilo de
  `docs/guias_cajon/theory_guide.md`).

## 5. Código de la herramienta

### Migración a teOdors (en curso desde el 2026-11-01; decisiones del usuario)
**⚠️ RECTIFICACIÓN (2026-11-02, decisión del usuario): odora se llama teOdors.** En el texto y en GitHub, `teOdors`; en el código, `teodors` (`import teodors`, `python -m teodors`, `lib/teodors`, `TEODORS_PLANTA`). En este fichero, «odora» sigue donde cuenta lo que pasó. Se quedan con su nombre, porque son datos ya en disco o fuera del proyecto: las series `odora_gfs_8est` y `odora_era5_8est`, `odora_run.log`, la caché `%TEMP%\ence_odora_numba`, `DATOS/pruebas/odora` y la copia de desarrollo `%LOCALAPPDATA%\CIRCE\odora_dev`.
**GitHub (decisión del usuario, 2026-11-02):** un solo repositorio privado, `teOdors`, con una carpeta por versión EXACTA del core y una por planta, que dice qué versión usa en su archivo de versión; prevé ~10 plantas en 2 años. Se publica UNA vez, al acabar la migración, como **0.1.3** (en GitHub, la última es v0.1.2):
```
teOdors/
  v0.1.3/    core/ auditor/ docs/ pyproject.toml CHANGELOG.md LICENSE…
  galera/    VERSION (v0.1.3) · main.py · planta/ · docs/ · 99-Test/ · CLAUDE.md
```
⚠️ Mover el core a una subcarpeta rompe lo que supone la raíz del repositorio: R4-R6 del auditor (rutas `core/…` en la raíz de git), `pyproject`, integración continua y gancho de subida. Se resuelve en la tanda 9. Aquí no hay `gh`: renombrar el repositorio lo hace el usuario o hay que instalarlo.
**El código se mueve por script, nunca reescrito a mano** (2026-11-02): al reescribir `formato.num`, un espacio duro pasó a normal, se ve igual en pantalla y solo lo cazó una prueba de la app.
**Las pruebas no tocan el INI del usuario** (`ENCE_AJUSTES_PRUEBA`): copiarlo y restaurarlo acabó perdiendo la disposición guardada; la app abrirá la próxima vez como la primera.

Todo lo replicable va a odora, también la GUI; en galera solo queda lo de esta planta. Detalle fichero a fichero: `docs/auditoria_galera_odora.md`. Se trabaja en la rama `migracion-odora`, en la copia
`%LOCALAPPDATA%\CIRCE\ENCE_migracion` (fuera de OneDrive, con los datos de prueba en `%TEMP%\ence_galera\datos_migracion`), para no tocar la app que se esté usando. Decisiones: `openmeteo`, `penacho_dia` y `puffs_casos` se archivan;
el MOS entra al final; `viento_local` entra marcado como no validado y fuera de los motores; normativa con plantilla nacional en odora que cada planta puede sustituir; se mantiene la palabra «planta»; ⚠️ RECTIFICACIÓN (2026-11-02): ya no se publica por bloques, sino una sola vez al final, con el auditor APTO.
**Comprobación de cada tanda:** `99-Test/10_migracion/linea_base.py` (77 huellas: focos, malla, viento, casos, una corrida del motor, simulaciones, imágenes) frente a la inicial con `comparar.py`, y las pruebas de 05, 08, 09 y las de clics.
- **Tanda 0 → HECHA:** sin mover nada a odora. ⚠️ RECTIFICACIÓN de lo que sigue en este fichero: `entradas/openmeteo.py`, `gui/tareas/penacho_dia.py` y `puffs_casos.py` ya no existen (`%LOCALAPPDATA%\CIRCErchivo\galera_codigo_2026-11-01_antes_de_migrar.zip`, ⚠️ copiar a Z:). Las tareas se lanzan con `python -m galera.gui.tareas.X` y `PYTHONPATH=lib;lib/paquetes`. **`--datos` ya no existe:** la carpeta se da con `ENCE_GALERA_DATOS`, y sin ella `viento_dia_local` escribe donde diga `rutas.json` (Z:), no en local. El panel del tiempo sale solo de `<serie>/AAAAMM/meteo.json`: ⚠️ al volver Z:, mirar si algún día de `dispersion/` se queda sin él. Dos fórmulas de dirección de viento conviven a propósito (`geo.direccion` y `270 − atan2(v, u)` en la superficie de ERA5: el 27 % de los valores difiere hasta 1,1·10⁻¹³° y en calma exacta dan 180 y 270): no unificarlas sin medir el efecto. Nuevos `galera/errores.py` (`Cancelado`) y `gui/formato.py`; `COLORES_VEL` en `escalas`, `elevacion_solar` en `geo`, `terreno.a_mercator`, `tema.ESTILO_VENTANAS`.
- **Tanda 1 → HECHA:** `teodors.planta` (lee cada planta de su carpeta; `gui/planta/planta.json` es nuevo) y `teodors.comun` (`registro`, `formato`, `errores`, `procesos`, `mercator`, `escalas`). `config`, `geo`, `registro`, `formato`, `errores` y `escalas` de galera quedan como envoltorios hasta la tanda 9. Cambia el nombre del logger en el registro: `odora.mapa` → `teodors.mapa`. ⚠️ `comun/red` pasa a la tanda 3, con sus usuarios: las 5 versiones de HTTP con reintentos no son iguales.
- **Tanda 2 → HECHA:** `teodors.meteo.viento_local` (`modelo`, `biblioteca`; extra `viento_local` = scipy), **marcado como NO validado y fuera de `MOTORES`**. `viento/local.py` y `gui/tareas/viento_local_biblioteca.py` quedan como envoltorios hasta la tanda 9; lo propio de la planta, en el bloque `viento_local` de `planta.json`. ⚠️ RECTIFICACIÓN de lo que sigue en este fichero: ya no hay constantes en el código ni está «pendiente de llevar a odora». El paquete NO importa `teodors.planta` (vive en `core/meteo`, y `test_los_motores_no_dependen_de_ninguna_planta` lo prohíbe): recibe el bloque por parámetro y la planta en `main(activa=…)`. Reproduce byte a byte 2 de las 36 direcciones de `viento_local.npz` (0° y 180°, 89 s) y la cadena original de git a 5 y 10 m. `biblioteca.mezcla` es nueva: la misma cuenta que `mapa_web.campoLocal`, que sigue siendo la que usa el mapa (comprobado en Edge: mismos NaN y 5,8·10⁻⁷ m/s como mucho). `puntos` exige dos puntos distintos: con uno, `enPlanta` divide por cero. `lidar` es una ruta relativa a DATOS; la zona de `lidar_planta` queda para la tanda 3. ⚠️ RECTIFICACIÓN de «reataque 1,35-1,38 H»: eso es la primera celda con u > 0; el cruce por cero da 1,30 H a 1 m y 1,19 H a 2,5 m (medido 1,61 H). Una loma baja acelera un 40 % de lo que dicen Jackson y Hunt (1975).
- **Tanda 3 → HECHA:** `teodors.fuentes` (`terreno`, `catastro`, `meteocat`, `era5`, `descargar_era5`, `descargar_meteocat`, `gfs_noaa`, `gfs_dynamical`, `lidar`; extras `fuentes`, `lidar` y `gfs_historico`). `entradas/*` y las 5 tareas quedan como envoltorios hasta la tanda 9, con `__getattr__`: cualquier nombre, también los privados, es el de allí. ⚠️ RECTIFICACIÓN de lo que sigue en este fichero: lo propio de la planta ya no está en esos módulos, sino en `planta.json`: bloques `estaciones` y `pronostico`, `identidad.agente_http` y `viento_local.lidar_zona`; `f1_estacion`, `mos_tabla` y `viento3d_series` leen de ahí códigos, objetivo y ceros sospechosos. **Ninguna descarga real se ha lanzado con este código:** las pruebas simulan las respuestas, así que comprueban el código y no que los servicios sigan respondiendo así. `estaciones_dias` pasa de `viento_dia_local` a `meteocat`: es del servicio, y hacía falta probar que no pierde lo que había. Los agentes HTTP son dos a propósito, como estaban: Meteocat lleva el suyo. `lidar_planta.py` sigue sin importar nada con `python -I`: lee `planta.json` como texto y carga UN fichero del core por su ruta, que tampoco importa nada del proyecto. El cliente del CDS es `ecmwf-datastores-client`, no `cdsapi`. Las 5 versiones de HTTP con reintentos siguen separadas (ninguna es idéntica a otra), igual que `a_horario` y `medias_horarias`, que no se han tocado. ⚠️ Visto y sin tocar: en `descargar_mdt`, en la costura entre tramos gana la celda del primero aunque su ventana bilineal quede incompleta (medido sobre un plano del 2 %: 0,26 m en 96 de 19 023 celdas; las demás, ≤ 0,05 m). El terreno de 50 km son 2 × 2 tramos, así que el descargado tiene esas costuras; no se ha medido su efecto.
- **Tanda 4 → HECHA:** `teodors.metricas` (`viento`, de `viento/validacion.py`; `calidad`, de `gui/tareas/f1_estacion.py`, también como `python -m teodors.metricas.calidad`). Los dos ficheros de galera quedan como envoltorios hasta la tanda 9. ⚠️ RECTIFICACIÓN de lo que sigue en este fichero: ni la ventana de la hora de las estaciones ni los ceros sospechosos están ya en el código. **`convencion` deducía «inicio» o «fin» con una ventana fija de 11,4 a 12,6 h UTC, que solo vale cerca del meridiano 0** (a −6° tomaría el inicio por el final): ahora va alrededor de `mediodia_h`. Esta planta fija `estaciones.mediodia_utc_h` = 12,0 en `planta.json` para que no cambie la convención deducida, aunque su mediodía solar sea 11,97 h; una planta sin ese campo usa el de su longitud. `metricas`, `rosa` y `figura_rosas` se mueven y siguen sin llamador. `a_horario` y `medias_horarias` no se han fundido: una prueba deja escrita la diferencia. Las estaciones siguen siendo solo las de Meteocat. ⚠️ Visto y sin tocar, medido con datos inventados: `calidad` reparte las figuras con `[:6]`, pensado para 5 años; un año o una estación del año sin horas válidas hace fallar `figura` (`ValueError`); `rosas_dia` da 23 horas el 1 de enero; `metricas` descarta la hora entera si falta la temperatura. Y, por búsqueda en el código, `meteocat.para_mapa` lee `validacion/era5_vs_meteocat.json`, que ya no escribe nadie desde la tanda 0.
- **Tanda 5 → HECHA:** `teodors.casos` (`viento3d`, `gfs_columnas`, `receptores`) y, porque no necesita planta ni fuentes, `teodors.preparacion.puffs.control_fuentes`. Los cuatro de galera quedan como envoltorios hasta la tanda 9. ⚠️ RECTIFICACIÓN de lo que sigue en este fichero: niveles y estilos de la malla, columnas de GFS, radios de las estaciones y el nombre de las cabeceras ya no están en el código, sino en `planta.json`: `receptores.niveles` y `estilos`, `pronostico.n_col` y `paso_col_m`, `series.r1_km` y `rmax_km`, `identidad.nombre_casos`. De `series` solo está lo que algo lee: `preferidas`, `titulos`, `era5` y `gfs` siguen en `viento_mapa`, `viento3d_series` y `viento_dia_local`, y van con ellos en la tanda 6. `control_fuentes.geometria` recibe el módulo de los focos por parámetro hasta la tanda 6. ⚠️ RECTIFICACIÓN de «NZ y ZFACE tienen que coincidir o el motor aborta»: eso era del .exe. `dispersion.puffs` solo aborta por NX y NY y toma NZ y ZFACE del viento: medido, con otros en el control da el mismo resultado, sin avisar. `viento3d_casos` y `gfs_columnas` NO pasan por la línea base. Se comprobó, sin red y por los envoltorios, `viento_dia_local.preparar_caso` del episodio del 23-oct: `caso.json` idéntico al guardado y `viento3d.inp` igual salvo su título (odora → teOdors); `mes_serie` entero, solo con los datos inventados de las pruebas. **Un mes real con ERA5 no se ha lanzado con este código.** La prueba es `test_casos_planta.py` porque `test_casos.py` ya es la de regresión. ⚠️ Visto y sin tocar: `gfs_columnas.niveles` junta plazos distintos (la predicción larga) con `xr.concat` sin `join` y xarray avisa de que fallará en una versión futura; `_reservado_gb` aún mira `viento3d_estudios/icon` y `experimentos`, de estudios ya borrados; sin ERA5 de antes, `preparar_mes` arranca en frío sin avisar; una estación sin altura de anemómetro pasa a 10 m sin avisar.
- **Tanda 6 → HECHA:** `teodors.operacion` (`focos`, `planes`, `normativa`, `periodos`, `simulacion`, `penacho_mapa`, `viento_mapa`, `penacho_3d`, `respuestas`, `viento_periodo`, `viento3d_series`, `ejemplo_configuracion`). Los doce de galera quedan como envoltorios hasta la tanda 9, y lo que una prueba ponga en uno llega al módulo de teOdors (`galera/envoltorio.py`: `F.guardar = falso`, `PC._capas = …`, `P._correr = espia`, `N.RUTA = …`, `viento_mapa.BIBLIOTECA = …`); `config.MODO_CIRCE` se queda en `gui/config.py`, y nada del core lo lee. ⚠️ RECTIFICACIÓN de lo que sigue en este fichero: `periodos._lanzar` lanza ya `python -m teodors.operacion.viento_periodo` y `.respuestas`, que encuentran la planta por `TEODORS_PLANTA` y los datos por `ENCE_GALERA_DATOS`; `python -m galera.gui.tareas.X` sigue valiendo, con sus argumentos. La zona horaria, las series, los títulos, el día de prueba, el ejemplo y lo del visor están en `planta.json`: `proyeccion.zona_horaria`, `series.era5`, `gfs`, `preferidas`, `titulos` y `dia_prueba`, `operacion.ejemplo` y `tipos_foco_extra` (vacío) y el bloque `visor3d`. **Normativa:** plantilla nacional en `operacion/normativa_nacional.json` (RD 102/2011, PRELIMINAR); el `gui/planta/normativa.json` de esta planta manda entero, y hoy dice lo mismo. `geometria` pasa de `control_fuentes` a `operacion.focos`: `preparacion` ya no sabe de focos. `pagina` del visor se queda en `gui/penacho_3d.py` hasta la tanda 8, porque usa `tema`. Los iconos del panel del tiempo van con el código, y `package-data` ya los lleva. **`firma` da el mismo valor:** comprobado con el código original sacado de git, en los 7 resultados guardados en `datos_migracion`, que se siguen leyendo; el penacho 3D guardado se abre, con el mismo terreno y los mismos rótulos, y la página, con unos datos de prueba, sale igual byte a byte. ⚠️ `operacion.penacho_3d.calcular` entero **no se ha lanzado** con este código (~10 min por día): solo `_correr`, `_rotulos`, `_terreno_vista` y `_superficies`, y lo guardado se abre. `viento_periodo.main` no se ha lanzado con red; sí `preparar_caso` del episodio y la predicción frente a lo guardado. ⚠️ Visto y sin tocar: `ejemplo_configuracion.principal` lee `resultados_planes/<plan>/` y `dia_viento`, de antes de las modalidades: falla con lo de hoy, y por eso `recursos/ejemplo` no se puede rehacer; un gas sin límite ni umbral (NOx o CO, si `normativa.json` les quita el límite) da `ref` None y la simulación falla; otro día de la misma serie y el mismo mes sustituye el `.cmz`, y `viento_mapa._mes` no lo ve hasta reiniciar; un plan mensual de enero se lleva las 2 últimas horas UTC del último año; `panel.py:43` sigue con su `ZoneInfo("Europe/Madrid")` (Qt, tanda 8).
- **Tanda 7 → HECHA:** `teodors.mos` (`tabla`, `entrenar`; extra `mos`), paquete propio porque usa la planta y `fuentes`, y fuera de `MOTORES`. `gui/tareas/mos_tabla.py` y `mos_entrenar.py` quedan como envoltorios hasta la tanda 9, con sus mismos argumentos (ninguno). ⚠️ RECTIFICACIÓN de lo que sigue en este fichero: la última hora que cuenta ya no está en el código, sino en `pronostico.mos_hasta`, y las estaciones se leen al empezar, no al importar. El extra lleva también `dask[array]` y `scipy`: medido bloqueando cada módulo, sin ellos fallan `open_mfdataset` e `interp`. **Con este código no se ha lanzado nada con datos reales:** los del MOS están en Z:, y `datos_migracion` no tiene `mos/` ni `meteo/gfs/`; las pruebas usan datos inventados, entrenan de verdad y comprueban que se corrige un sesgo conocido. No se ha instalado el extra en un entorno limpio. ⚠️ Visto y sin tocar: la columna `anemometro_m` de la tabla vale siempre 10, porque `meteocat.cercanas` no da la altura (ningún modelo la usa); `entrenar` guarda los modelos, pero nada los aplica a una predicción nueva ni los lleva a `viento3d` (lo de las pseudoestaciones se borró con `mos_fuera_una`); `entrenar` importa `error_dir` sin usarlo.
- **Tanda 8 → HECHA:** `teodors.gui` (ventana, panel, mapa y su página, focos, planes, configuración, visor 3D, `tema`, `widgets`…; extras `gui` y `gui3d`), y `principal.main`, el arranque: `main.py` de la planta queda en unas diez líneas. Los de `gui/` quedan como envoltorios hasta la tanda 9, también `entradas/*`, `viento/validacion` y `receptores_mapa` con `reenviar`, porque la interfaz ya no los lee. En la planta, de `recursos/` solo quedan `ejemplo/` y `visor3d/ortofoto.jpg`. ⚠️ RECTIFICACIÓN de lo que sigue en este fichero: **el objeto de la página ya no lleva el nombre del cliente:** `window.ence.*` → `window.mapaApp.*`, clases `ence-*` → `mapa-*`, panel `enceViento` → `mapaViento`, puente `ENCE:` → `MAPA:`. Lo de la marca está en `planta.json`: `identidad.ajustes`, `app_id`, `version`, `entidad` y `red_datos`; `fuentes.mdt`, `usos`, `edificios`, `nombres_nucleos`, `fondos` y `creditos`; `estaciones.proveedor`; `operacion.texto_modo_edicion`. **El INI no cambia:** `%APPDATA%\CIRCE\ENCE_Galera.ini`, con las mismas claves. `config.MODO_CIRCE` es `planta.MODO_EDICION`, también al asignarlo, que es lo que lee la interfaz; `--circe` sale de `operacion.modo_edicion`. `galera.__version__` ya no llega a la ventana. `test_importa`: los módulos con Qt llevan `skipif` si falta PySide6 o folium, y solo esos; un proceso aparte comprueba que lo demás no los carga. Con los dos ocultos: APTO con 651 pruebas, frente a 687. **Comprobado con `comparar_movidos_tanda8.py`:** 422 nombres iguales en texto y AST tras la sustitución del nombre y 41 con su motivo; los dos HTML del mapa, iguales byte a byte salvo 2 comentarios de JavaScript; y, frente al código original sacado de git, sin pantalla: mismos textos, estilos y listas en las 5 ventanas (419, 222, 236, 138 y 71 widgets) y los mismos píxeles en las 6 páginas del panel × 4 estilos. `humo_tanda8.py`: el `main.py` entero, también con `--circe --focos --planes`, sin errores en el registro. ⚠️ **Sin ventanas de verdad: el contenido web sale en blanco,** así que el mapa con sus capas no se ha mirado con este código; es lo que tiene que comprobar la batería de clics. Sin probar: ratón real, Z:, el PC del operario y la instalación en un entorno limpio. Una planta nueva necesita `recursos/ejemplo` o la ventana de configuración falla al abrirse, y el generador falla con lo de hoy (tanda 6). ⚠️ Visto y sin tocar: en `ventana_focos`, un combo local se llama `c` y tapa a `tema.c`; un mismo módulo entra en `ventana` con dos alias (`receptores_mapa` y `receptores`); `panel._muestra` pinta su borde con un color fijo (`#777`), que no sigue al estilo; `web._descarga` espera hasta 40 s por recurso en el hilo de la interfaz, si no hay red ni caché; three.js ya está en el core y su `LICENSE` aún no contempla a terceros (tanda 9).

Reordenado el 2026-10-22 (decisión del usuario: TODO el código en `lib/`; odora es lo universal y
`lib/galera` lo que depende de esta planta) y otra vez el 2026-10-23 por USO (regla del usuario:
lo que conecta la app con odora → `gui/`; lo útil que odora no tiene → odora; lo demás se borra).
Los `import` van en absoluto (`from galera.gui import config`), con `lib/` y `lib/paquetes/` en el
camino de Python (`main.py` y la cabecera de cada tarea lo ponen; `galera/__init__` mete
`lib/paquetes` para que «import odora» sea siempre el clon fijo).

```
main.py                      lanzador:  C:\e2s\python.exe main.py [--dia AAAA-MM-DD]
lib/odora/                   MOTOR UNIVERSAL: clon fijo de la etiqueta v0.1.2 (con .git) de
                             github.com/mcamasanz/odora
lib/paquetes/odora/          cargador: «import odora» = lib/odora/core (el repo guarda ahí el paquete)
lib/galera/
  gui/                       LA APP de esta planta y lo que la conecta con odora y con los datos
    planta/                  emplazamiento.json (posición FIJA), rutas.json (DATOS: hoy
                             Z:\Miguel\03-Odora\ENCE_LaGalera), focos.json (los focos: hoy de
                             EJEMPLO), receptores.json (receptores con nombre: hoy Dacame), normativa.json
                             (límites: PRELIMINAR, se cambia sin tocar el código). Sin plantillas: los controles de viento3d y puffs los
                             escribe odora desde cero
    config.py · registro.py · tema.py · escalas.py  base de la app (tema.py: estilos, colores e iconos;
                             escalas.py: escalas de color del viento y las concentraciones)
    ventana · panel · mapa · consola · terminal · widgets · trabajos (QThread) · mapa_web (folium +
    window.ence.*) · web (HTML sin CDN) · viento_mapa · penacho_mapa · receptores_mapa ·
    focos · escenarios (planes: formato y cuentas) · planes_calculo (panel Simulación) · ventana_ajustes (configuración) · ventana_focos ·
    focos_mapa · ventana_planes (2.as ventanas) · vista_previa · recursos/iconos · recursos/ejemplo ·
    normativa (columnas y estadísticos) · periodos (reanálisis, episodio, predicción) · penacho_3d ·
    vista_3d · recursos/visor3d
    tareas/                  lo que prepara y lanza odora con los datos de la planta: descargar_
                             {era5, meteocat, gfs_niveles, gfs_historico}, viento3d_casos (casos
                             y series de viento 3D), puffs_casos, viento3d_series,
                             viento_dia_local (+ gfs_columnas), penacho_dia, respuestas_dia
                             (+ control_fuentes), f1_estacion, mos_{tabla, entrenar}, ejemplo_configuracion, lidar_planta y
                             viento_local_biblioteca (motor de viento de la planta)
  entradas/ · viento/{validacion, local} · geo.py   PENDIENTE de llevar a odora (fase 2: fuentes, métricas)
docs/                        lo rescatado del cajón (normativa, olores, emisiones, guías 06/09/10,
                             teoría y uso, arranque ENCE) · ver docs/README.md
Oferta/                      gestión (no es código)
99-Test/                     PRUEBAS y prototipos (pedido del usuario, 2026-10-24): una carpeta por
                             prueba con su README y resultados pequeños; lo pesado en
                             %TEMP%\ence_galera\99-Test. No forma parte de la herramienta
```
Fuera del proyecto: DATOS (Z:), claves (`%APPDATA%\CIRCE\claves`), cálculos en marcha, mapa y
registros (`%TEMP%\ence_galera`), archivo del código borrado
(`%LOCALAPPDATA%\CIRCE\archivo\galera_codigo_2026-10-23_antes_de_limpiar.zip`, ⚠️ pendiente de
copiar a `Z:\…\ENCE_LaGalera\archivo\` cuando vuelva Z:) y los .exe de terceros
(`%LOCALAPPDATA%\CIRCE\terceros`), que la herramienta YA NO lanza (2026-10-23).
Comprobado tras el reordenado: 59 ficheros compilan, todos los módulos importan, cada nombre
importado existe (también entre scripts, por su AST), `penacho_dia.py` da el MISMO penacho bit a
bit y la app (sin pantalla) carga viento y penacho como antes. ⚠️ El entorno aislado de Python
3.12 (`%TEMP%\ence_galera\venv312`, para `descargar_gfs_historico.py`) quedó roto al liberar
TEMP: su intérprete base (de `uv`) estaba en `%TEMP%\ence_galera\python`. Rehacerlo con `uv` si
hay que volver a descargar el histórico de GFS.

- **Terreno** (`DATOS/terreno/<lat>_<lon>_<lado>km_25m/`): `elevacion.tif`, `usos.tif`,
  `corine.gpkg` (extracto recortado, ~19 MB: el PC del operario NO necesita el CORINE de 3 GB),
  `info.json`, `mapa_*.png` (ya en Web Mercator para que el ImageOverlay cuadre). 50 km a 25 m
  = 2000×2000 celdas, ~20 s. Cota 0–1437 m (Els Ports), mar ~15 %, planta a ~98 m en olivar.
- **Comprobado del WCS del IGN:** sobre el MAR devuelve **0 m** (no nodata; la cabecera ni
  trae `nodata_value`); la respuesta es multipart y los datos acaban en la primera línea `--`;
  sirve en EPSG:25830 y se reproyecta. CORINE: capa `CLC18_ES`, EPSG:25830, lectura por bbox 0,1 s.
- **Entorno:** el geostack (geopandas, pyogrio, rasterio, shapely) está en los paquetes de
  USUARIO (`%APPDATA%\Python\Python311\site-packages`), no en `C:\e2s`. Por eso `python -I` no lo
  ve. Tenerlo en cuenta al llevar la app al PC del operario.

- **Disposición:** el mapa es la zona central; panel (izquierda) y consola (abajo) son
  `QDockWidget` movibles, flotantes, ocultables y con secciones plegables. «Solo mapa» = F11.
  Se probó con el mapa también acoplable y se descartó por lo medido (hueco gris al ocultarlo,
  panel que encogía): ver el docstring de `gui/ventana.py`.
  ⚠️ RECTIFICACIÓN (2026-10-31, rama `interfaz-moderna`): el panel ya no tiene secciones plegables
  y la consola se llama «Actividad» y arranca oculta. Ver «Interfaz moderna», más abajo.
- **Datos de trabajo (DATOS):** **`Z:\Miguel\03-Odora\ENCE_LaGalera`** (unidad de red
  `\\10.10.200.245\tb`, 4,7 TB libres; decisión del usuario del 2026-10-21 para dejar sitio en
  el disco local). Se resuelve con la variable `ENCE_GALERA_DATOS`, si no `lib/galera/planta/rutas.json`
  (`{"datos": …}`) y, si no, `ENCE\datos`. Copiados 1 163 ficheros / 10,66 GB con robocopy
  (64 MB/s), comprobados fichero a fichero (y hash de los 6 mayores) y borrada la copia local
  (C: pasa a 49,8 GB libres). Antes estuvieron en `ENCE\datos` (2026-10-20) y en
  `%LOCALAPPDATA%\ENCE_Galera`. ⚠️ Sin la unidad Z: la app no encuentra sus datos. Fuera de
  OneDrive y de la red quedan: los .exe de terceros en `%LOCALAPPDATA%\CIRCE\terceros` (ya no
  los lanza la herramienta), la **clave del CDS en `%APPDATA%\CIRCE\claves\cds-api-key.txt`**
  (regla 7), la caché de numba en `%TEMP%\ence_odora_numba` y los casos en marcha de CALMET/odora
  (2,7 GB por mes) en `config.DIR_TRABAJO` = `%TEMP%\ence_galera\trabajo` (de cada caso solo se
  guarda en DATOS el .cmz y lo pequeño). Disposición de la ventana: `%APPDATA%\CIRCE\ENCE_Galera.ini`.
- **Fondos del mapa:** solo DOS, por decisión del usuario: «Satélite (ortofoto PNOA)» (IGN,
  CC BY 4.0, por defecto) y «Callejero (OSM)». Nada de Esri. Si OSM restringe el acceso,
  cambiar el callejero por el mapa base del IGN (comentado en `mapa_web.FONDOS`).
- **Terreno: se descarga UNA vez** (50 × 50 km, ya hecho el 2026-10-14) y después solo se carga
  del disco. El botón de descarga solo aparece si no hay terreno; «Archivo → Volver a descargar
  el terreno…» queda para mantenimiento. El mapa NO dibuja cuadrados de dominio (decisión del
  usuario).
- **Bloque «Terreno y uso del suelo»:** cota (rango, en la planta, % por bandas), árbol de % de
  usos por grupo → clases CLC, y núcleos 🏠 urbanos (111/112), 🏭 industriales (121), ⚽
  deportivos (142) con el más cercano. En el mapa, los mismos núcleos con los iconos del cajón
  (casa azul, fábrica amarilla, balón naranja). Hay 40 / 26 / 2.
- **⚠️ CORINE no ve los pueblos pequeños:** su unidad mínima es 25 ha. El casco de La Galera
  (a 1,4 km al SO de la planta, el núcleo habitado más cercano) sale como «mosaico de cultivos»
  y no tiene icono. Los receptores sensibles cercanos habrá que añadirlos aparte. Medido el
  2026-10-30: tampoco salen Freginals (4,3 km) ni Godall (3,9 km).
- **Clic en el mapa** → consola: coordenadas, UTM, cota, uso del suelo (CLC) y distancia/rumbo
  desde la planta (o «fuera del terreno descargado»).
- **Zoom de «Ver planta» y «Ver todo el terreno»** (hoy «Ver toda la zona»; usuario, 2026-10-29): la planta a zoom 18
  (antes 16; 17 se quedaba corto) y la región centrada en la planta a un nivel más del que
  encuadra el terreno entero (`ence.centrar`, también al arrancar; «perfecto»). En el panel,
  «Focos de emisión» va ANTES que «Meteorología».
- **Nombre de los pueblos en las fichas de los núcleos** (2026-10-29, para «ver qué pueblos han
  sido afectados»): CORINE no los trae; `terreno.nombres_nucleos` los pide UNA vez a CartoCiudad
  (IGN, geocodificación inversa, CC BY 4.0) y los guarda en `nucleos_nombres.json` junto al
  terreno (68 de 68 en 10 s). El 2026-10-21 la fuente de prueba alcanzó sobre todo La Ràpita.

### Viento en superficie animado (pedido del usuario, 2026-10-21)
- ⚠️ RECTIFICACIÓN (2026-10-31, decisión del usuario): en Meteorología → Reanálisis solo se ve el VIENTO del día, sin
  penacho y sin sus valores en los tooltips de los núcleos. El penacho se ve en Simular, con la operación de los focos:
  `planes_calculo._penacho` da el plan hora a hora en el día del viento (`C(H, r)` con las 23 h anteriores de emisión), 2
  imágenes por hora como las capas de media, máximo y P98 (±3 km a 10 m, el resto a 100 m, misma escala fija) y
  `ence.setPenacho` lo anima con el reproductor. Sale encendido al simular; botón «Ver penacho». Borradas de
  `penacho_mapa`: `estadisticas`, `valores_en`, `tabla_punto`, `datos_dia`. El panel de tiempo, termómetro y brújula
  sale de `DATOS/dispersion/<serie>_<día>/meta.json` (`penacho_mapa.tiempo_dia`, de `gui/tareas/penacho_dia.py`): si no
  está, el penacho va sin panel. Lo que sigue sobre la fuente de prueba en la app es historia.
- Panel → Meteorología → **Reanálisis** → bloque «Viento en superficie (odora, 0–20 m)»: día
  (calendario limitado a los meses calculados), «Ver en el mapa», deslizador de hora y ▶ (≈ 4 h/s
  desde el 2026-10-24, antes 1 h/s; en cuartos de hora desde el 2026-10-22; antes 8 subpasos). Capa del selector «🌬️ Viento en superficie · partículas / flechas»
  (excluyentes entre sí; fuera del grupo temático) y recuadro con hora, media, máxima y escala
  azul → rojo (0-8 m/s). Al salir de Reanálisis se quita.
- `lib/galera/gui/viento_mapa.datos_dia(fecha, serie="odora_era5_8est")`: nivel 1 leído directamente del
  .cmz con `almacen.leer_campo` (solo U-LEV 1 y V-LEV 1, ~2 s por mes), u, v en int16
  (centésimas) y base64 (~2 MB/día) y solo 3 esquinas de la rejilla. JS en `mapa_web`
  (`ence.setViento`, `ence.vientoHora`, `ence.quitarViento`), adaptado de
  `cajon/codigo_base/src/web/viento_calmet.js` (con su arreglo de la desalineación: proyectar
  sin redondear). u, v van en ejes de la CUADRÍCULA UTM: la capa los coloca con la geometría de
  la rejilla en pantalla (no hay que girar por la convergencia). ⚠️ En capturas sin pantalla
  (Edge headless) las partículas no se ven (no anima); comprobado con los píxeles del canvas.
- **Fluidez al hacer zoom** (2026-10-22, el usuario notaba que se ralentizaba): antes, hasta
  6 000 partículas (área en pantalla / 120) dibujadas UNA A UNA a 60 fotogramas/s. Ahora: área /
  260 con tope de 2 500, trazos agrupados en las 5 clases de velocidad (5 órdenes de dibujo por
  fotograma), ~30 fotogramas/s (paso, estela y vida reescalados) y ajuste al equipo (si la media
  pasa de 14 ms por fotograma quita el 15 %, si baja de 6 ms añade hasta el objetivo); trazo algo
  más grueso al acercar. Medido en Edge (1 559 × 907 px, `ence.benchViento(60)`): 4,8 / 4,4 /
  3,6 ms por fotograma antes frente a 1,3 / 1,0 / 1,3 ms ahora a zoom 11 / 13 / 15 (≈ 7× menos
  trabajo por segundo). ⚠️ Con `--virtual-time-budget` el reloj (`performance.now`) se congela:
  medir sin esa opción y sin esperas.
- **Un día en local, sin la unidad Z:** (2026-10-22) `lib/galera/gui/tareas/viento_dia_local.py --dia AAAA-MM-DD`
  → DATOS locales `%TEMP%\ence_galera\datos_local` (no toca `lib/galera/planta/rutas.json`): terreno (IGN +
  CORINE de la copia de PyroSmoke; la de inundaciones ya no existe), las 8 estaciones de Meteocat
  de ese día y el anterior, GFS 0,25° con niveles (3 ejecuciones 00 UTC, predicción a 1 día) →
  odora 48 h con GFS en 4 × 4 columnas + 8 estaciones (NOOBS = 1) → serie `odora_gfs_8est`
  (`cmz/AAAAMM.cmz` + `caso.json` con `dias_completos`). 2026-10-21: odora 0,7 min, total 9,6 min
  (casi todo en descargas: Meteocat va lenta desde fuera; `altura_viento` consulta desde 2021).
  Viento medio por hora 2,9-5,8 m/s, máx. 9,2. La app la abre así:
  `$env:ENCE_GALERA_DATOS = "$env:TEMP\ence_galera\datos_local"; C:\e2s\python.exe main.py`.
  `viento_mapa.serie_disponible()` usa la primera de `PREFERIDAS` (odora_era5_8est, luego
  odora_gfs_8est) y `dia_inicial()` abre el calendario en el día calculado. Con pocos días la
  convención horaria no se puede deducir de la radiación: `ficheros.obs_horarias(…, conv="inicio")`.
- **Sin la unidad Z:** (2026-10-22, PC en otra wifi: la app NO arrancaba al crear carpetas y el
  registro en Z:). Ahora página del mapa, sus librerías y registros van a `config.LOCAL`
  (`%TEMP%\ence_galera\{web, web_assets, logs}`); `config.datos_disponibles()`; la app arranca,
  avisa (mensaje y consola) y bloquea las descargas hasta que vuelva la red de CIRCE o la VPN.
- **Penacho de un día** (2026-10-22, pedido del usuario: «intervalos de 15 minutos … con los
  iconos de haber lanzado ya la simulación»). `lib/galera/gui/tareas/penacho_dia.py --dia … --serie …`:
  CALMET.DAT del .cmz → odora puffs con la FUENTE DE PRUEBA (área 100 m, 1 g/s) y malla de
  197 × 197 receptores (TODO el dominio, ±`config.RADIO_CALCULO_KM` cada 250 m) →
  `DATOS/dispersion/<serie>_<AAAAMMDD>/` (24 `penacho_HH.png` en Web Mercator, escala log de 4
  décadas con tope = máximo del día / 10, `conc.npz`, `meta.json` con viento, T, radiación,
  lluvia y nubes de GFS en la planta). 2026-10-21: 2,0 min (odora 1,8), máx. 186 µg/m³.
  ⚠️ **RECTIFICACIÓN (2026-10-22, lo vio el usuario: «se apaga como si hubiera otro subdominio»):**
  la 1.ª versión tenía receptores solo a ±10 km y el penacho se CORTABA en ese cuadrado con 2-78
  veces el mínimo de la escala (los puffs sí se siguen en todo el dominio de CALMET: IBCOMP..IECOMP
  = 1..NX). Con todo el dominio llega al borde real (±25 km; allí aún 0,01-0,17 µg/m³; fuera no
  hay viento y los puffs se pierden). El tope P99 dependía de cuántos receptores lejanos hubiera
  (19,8 → 2,6 µg/m³ al ampliar la malla, saturando los primeros 5 km): por eso máx/10.
  ⚠️ Convención de odora puffs: el 1.er periodo lleva fin = hora de inicio y el periodo k usa el
  registro k de CALMET; con inicio a las 06 del día anterior hacen falta 18 + 24 = 42 periodos.
  En la app (`lib/galera/gui/penacho_mapa.py`, `ence.setPenacho / penachoHora / quitarPenacho`): se
  carga solo al pulsar «Ver en el mapa» si existe el día; capa «☁️ Penacho · fuente de prueba»,
  FUNDIDO de composición constante entre horas (`aa = 1 − (1 − OP)/(1 − OP·f)`, la opacidad total
  no cambia) y panel abajo a la derecha con los iconos del cajón (`lib/galera/gui/recursos/iconos/`:
  día/noche × despejado/nubes/lluvia, termómetro con la escala del día, brújula con la flecha
  hacia donde va el viento). El deslizador va en CUARTOS DE HORA (00:00-23:00) y ▶ avanza 15 min
  cada 125 ms (2 h/s; el usuario, 2026-10-24: primero ×4 desde 250 ms = 1 h/s, «muy rápido»,
  y luego ×0,5); viento y penacho se interpolan con el mismo (hora, fracción).
- **Tooltips con el día cargado** (pedido del usuario, 2026-10-24): cada NÚCLEO (pueblo,
  industria, deportivo) lleva la tabla de media, máximo y P98 del penacho del día en ese punto
  (`penacho_mapa.valores_en`: serie horaria interpolada bilineal en el punto desde conc.npz, y de
  ella las estadísticas; `tabla_punto`); 66 de los 68 núcleos caen en la malla de ±24,5 km. Cada
  ESTACIÓN lleva la rosa de lo MEDIDO ese día (`validacion.rosas_dia`: 24 medias horarias UTC,
  Meteocat con etiqueta de inicio) y, al lado, la de 2021-2025 si están sus datos (en Z:). ⚠️ Con
  los DATOS locales las rosas de 2021-2025 salen de «0 estaciones» (solo hay los días 20-21 de
  octubre de 2026): por eso no se veía ninguna rosa. Se calculan en el hilo de carga del día y se
  quitan al salir de Reanálisis.
- **Orden de las capas** (pedido del usuario, 2026-10-24: tablas y rosas POR ENCIMA del viento y
  la dispersión). El lienzo de las partículas colgaba del CONTENEDOR del mapa con z-index 450,
  por encima de todo el panel interno de Leaflet (z-index 400, que lleva dentro iconos y
  tooltips): tapaba tooltips e iconos. Ahora va en un panel propio `enceViento` (z-index 450)
  dentro del mapa: penacho (overlayPane 400) < viento (450) < iconos (markerPane 600) < tooltips
  (650). Se sigue dibujando en coordenadas de pantalla: `geom()` lo coloca en la esquina del
  contenedor con `L.DomUtil.setPosition(cv, mapa.containerPointToLayerPoint([0, 0]))`.
  Comprobado sin pantalla: desfase 0 px al cargar, tras `verPlanta()` y tras `centrar()`.
- **Partículas en BLANCO** (prueba pedida por el usuario, 2026-10-24: los colores se confundían
  con los del penacho): `viento_mapa.PARTICULAS_BLANCAS = True` → las 5 clases de velocidad en
  blanco con opacidad 0,35 → 1 (más viento, más opaca; la estela ya es más larga con más viento);
  el recuadro lo explica en vez de la escala de colores. `False` vuelve a azul → rojo. Las
  flechas siguen en color. Pendiente de que el usuario lo vea y decida.
  ⚠️ RECTIFICACIÓN (2026-10-31): ya no es una constante. Se elige en la ventana de configuración, y blancas sigue
  siendo lo normal; `viento_mapa.PARTICULAS_BLANCAS` ya no existe.
- **Capas de media, máximo y P98 del día** (pedido del usuario, 2026-10-24): «☁️ Penacho · media
  del día / máximo del día / P98 del día» en el selector, EXCLUYENTES con la animación (grupo
  `penacho_mapa.GRUPO`; al elegir una se apagan la animación y su panel del tiempo, y al revés).
  `penacho_mapa.estadisticas(dia, serie)` las saca de `conc.npz` (P98 de la serie horaria, regla 2;
  con 24 h queda entre las dos horas más altas, lo dice la leyenda) con la misma escala log de 4
  décadas (tope = máximo de la capa / 10) y las guarda en la carpeta del día
  (`penacho_{media,maximo,p98}.png` + `estadisticas.json`): las crea `penacho_dia.py` al acabar o,
  para días antiguos, la app al abrirlos (en el hilo de carga, 5,5 s la primera vez). El dibujo
  es UNA función, `penacho_mapa.pintar`, que usa también `penacho_dia` (sus 24 imágenes siguen
  idénticas byte a byte). Comprobado en la app sin pantalla con clics reales en el selector.
  Cuando haya 5 años, estas capas serán las del alcance 1 (media y máximo anuales, P98).
- **Arranque con un día ya cargado** (2026-10-23, pedido del usuario): `main.py --dia AAAA-MM-DD`
  → al estar listo el mapa, Meteorología abierta, Reanálisis, ese día en el calendario y su viento
  y penacho cargados (`panel.preparar_dia_viento` + `ventana._cargar_viento`). El 2026-10-21 está
  en los DATOS locales: `$env:ENCE_GALERA_DATOS = "$env:TEMP\ence_galera\datos_local";
  C:\e2s\python.exe main.py --dia 2026-10-21`.

### Interfaz moderna (en `main` desde el 2026-10-31, decisión del usuario; pedido del usuario: «que apetezca quedarse con la app abierta sin hacer nada»)
- ⚠️ RECTIFICACIÓN (2026-10-31): ya no es un tema único. Hay 4 estilos a elegir: ver «Estilos y configuración», abajo.
- **Tema único, oscuro:** `gui/tema.py` tiene los colores (`T`), el estilo de toda la app, la paleta y los iconos
  SVG propios; `ventana_focos.ESTILO`, `mapa_web.css_tema()` y los dibujos salen de esos mismos colores. Letra en
  PÍXELES: mezclar pt y px rompía la jerarquía con el escalado de Windows (el cuerpo salía mayor que los títulos).
  El CSS de Leaflet se carga después del nuestro: para ganarle hace falta `!important`.
- **Panel:** riel de iconos (Inicio, Planta, Focos, Meteo, Simular y, abajo, Actividad) + una página por sección
  (`Panel.ir_a`), con `Tarjeta`, `Plegable` y `FilaPaso` de `widgets.py`. **Emplazamiento fijo encima de las páginas**,
  con «Ver planta» y «Ver toda la zona» (usuario, 2026-10-31): una sola tarjeta, en todas. En Planta, «Elevación», «Usos
  del suelo» y, desde el 2026-11-01, «Edificios cercanos» son plegables y empiezan plegados; sus botones de capa van
  dentro (al descargar edificios, el suyo se abre para ver el avance). Con barra de desplazamiento, la página
  cambia su margen para seguir alineada con el emplazamiento. Inicio guía el flujo del usuario en 3 pasos:
  Focos → Meteorología → Simulación. **Barra superior propia** (`setMenuWidget`): marca, reloj, «Solo mapa» y el
  menú en un botón (`menu_app`). Ya no hay `menuBar()` ni barra de estado; los atajos siguen (`addActions`).
- **Sin consola a la vista:** «Actividad» arranca oculta (`dock_consola`). Lo importante sale en el mapa: avisos
  (`mapa.aviso`; los errores del registro también) y ficha flotante al pinchar un punto o una estación
  (`mapa.ficha`). **Reproductor** bajo el mapa (`Panel.reproductor`), con pausa y «Lento».
- **Viento de muestra al arrancar** (`ventana._viento_ambiente`): el último día calculado, calmado (1 200
  partículas, 20 fotogramas/s) y despacio, para que la app no esté quieta. ⚠️ RECTIFICACIÓN (2026-10-31, decisión del
  usuario): ya no se rotula como muestra; solo el reproductor enseña su fecha. ⚠️ RECTIFICACIÓN (2026-11-01, decisión
  del usuario): YA NO EXISTE, ni su casilla. Al abrir, el mapa no tiene viento ni penacho: el viento llega al elegir
  Reanálisis y pulsar «Ver en el mapa»; el penacho, la media, el máximo y el P98, al simular. Lo guardado solo se ve como
  ejemplo en la configuración (ver «Vista previa en la configuración»).
- **Sin textos secundarios (decisión del usuario, 2026-10-31: «toda descripción secundaria quítala»).** En la app solo
  nombres, datos, unidades, leyendas, estados breves y errores reales. Nada de frases que expliquen, subtítulos, avisos de
  «ejemplo» o «prueba», pistas de uso ni ayudas emergentes, salvo el nombre de un botón que solo es un icono y el texto
  entero de un nombre recortado. Quitados: subtítulos de barra y ventanas, bloque ERA5/Meteocat de Meteo, resumen de
  los planes, notas de focos, rótulos de las leyendas… ⚠️ Con focos de ejemplo y un día de viento repetido, los
  números de la simulación NO son resultados aunque la pantalla ya no lo diga: cuidado al enseñarlos.
  «Actividad» solo enseña avisos y errores (`ManejadorQt` en WARNING); el resto sigue en el fichero de registro.
- **Terminal (pedido del usuario, 2026-10-31; los comandos se definirán más adelante):** `gui/terminal.py`, panel
  junto a Actividad (botón «Terminal» del panel, Ctrl+3). Solo ejecuta lo registrado con `Terminal.registrar`, nunca
  Python ni órdenes del sistema; lo escrito no va al registro. Hoy solo existe `limpiar`, y sin contraseña: «secreto» aún
  no protege nada, y al añadir comandos de verdad habrá que decidir cómo se autoriza.
- **Comprobado tras estos cambios (2026-10-31, DATOS locales, sin Z:, PC bloqueado, clics simulados):** `99-Test/05_planes`
  (`prueba_calcular`, `prueba_penacho`), estilos en caliente idénticos a arrancar con ellos, ventana de planes, `main.py` con
  todas sus opciones, capas solo desde el panel, terminal, las 3 formas × 2 colores del viento. ⚠️ Sin medir: el consumo con
  líneas o flechas y con el penacho en marcha, con la pantalla activa; sin probar: ratón real, Z: y el PC del operario.
- **Viento en el mapa (pedido del usuario, 2026-10-31):** tres formas (partículas, líneas de corriente y flechas) y dos
  colores (blanco o por velocidad), en la configuración y sincronizadas con el selector del mapa; `viento_forma`,
  `viento_color`, `viento_cantidad`. Las líneas son recorridos con el método del punto medio desde una malla fija respecto
  a la rejilla (`malla`, vale a cualquier zoom), con una punta en el centro. Medido (PC bloqueado): 9-45 ms por dibujo.
- **Dacame e iconos (decisión del usuario, 2026-10-31):** ver «Tabla» en el alcance 1 y «Iconos de los núcleos».
- **Consumo, medido (i7-1255U, % del equipo entero):** abierta con la muestra 6-10 % (varía de una medida a otra),
  con el viento normal ~12 %, sin viento 0,1 %, **minimizada 0,2 %**; ~950 MB de memoria. El halo animado de la
  planta costaba ~2 %: se dejó fijo. El efecto cristal apenas cuenta. ⚠️ Tapada por otra ventana sigue animando (Qt
  no lo detecta; sin medir). ⚠️ Al minimizar, `page().setVisible(False)` no vale en el mismo evento (Qt vuelve a
  poner visible la página): va con 300 ms de retardo (`_segun_minimizada`).
- ⚠️ **Ajustes guardados:** un divisor guardado antes pisa los tamaños nuevos (la ficha de focos salía cortada).
  Claves `focos/divisor_v2`, `planes/divisor_v2`, `ventana/geometria_v2`, `ventana/estado_v3`: al cambiar una
  disposición, cambiar la clave. La ficha más ancha pide 454 px (dos columnas con «recalcula»): `area_ficha` ≥ 470.
- **Iconos de los núcleos (decisión del usuario, 2026-10-31):** en el rediseño pasaron a chapas redondas y se
  volvió a los de antes (`mapa_web.iconoNucleo`, idénticos a los del commit 2ab0f47): casa azul, fábrica amarilla y
  balón naranja. Sus colores son fijos, no siguen al estilo. El panel mantiene el punto de color (`fam_*`).
- **Estilos y configuración (pedido del usuario, 2026-10-31: «¿cada vez que se cambia hay que reiniciar?» NO).**
  `gui/ventana_ajustes.py`: icono de reguladores en la barra superior, «Ver → Configuración…» o Ctrl+,. Ventana no
  modal (la app se ve cambiar detrás) con 4 estilos (Oscuro, Claro, Azul noche, Alto contraste; `tema.TEMAS`), una
  miniatura pintada con los colores de cada uno, y el viento: forma, blanco o por velocidad, cantidad
  (poca ×0,5, normal, mucha ×1,5) y mover o no el viento de muestra (quitado el 2026-11-01). Se guarda en `apariencia/*`
  del INI.
  `tema.poner(clave)` cambia el contenido de `T`, vuelve a aplicar la hoja de estilos y la paleta, rehace lo propio de
  cada widget y avisa (`tema.avisos.cambiado`); en los mapas solo cambian las variables CSS, sin recargar.
  **Regla para código nuevo:** nada de colores fijados al crear algo, o no seguirá el cambio. En Qt, `tema.pon_icono`,
  `tema.texto` (con $tenue, $aviso…; TODOS los textos de esa etiqueta deben pasar por ahí) y `tema.estilo`, o `c("…")`
  dentro de un paintEvent. En el mapa, `var(--…)`: vale también en atributos SVG y en los `color` de Leaflet. Los
  colores de DATOS (penacho, usos, clases de viento) no dependen del estilo; el tiempo, el termómetro y la brújula
  van siempre sobre fondo oscuro porque sus iconos están hechos para eso.
  **Medido (con el PC bloqueado):** cada cambio en caliente, 0,3-0,4 s con la ventana principal y la de configuración, 0,4-0,6 s con focos y
  planes también abiertas. Frente a arrancar con ese estilo: las 14 capturas Qt IDÉNTICAS píxel a píxel en los 4
  estilos (5 páginas del panel, barra, reproductor, menú, calendario, listas y fichas de focos y planes, configuración) y
  los mismos colores calculados en las 3 páginas web. El día cargado, la simulación, la hora y la página siguen; la
  página del mapa no se recarga. Contraste WCAG ≥ 4,5 en los pares de texto de los 4 estilos (el peor, 4,97).
  ⚠️ **Con el PC bloqueado no se mide el consumo:** hasta una página vacía baja de ~19 a ~4 fotogramas/s (2026-10-31:
  salió 1,1 % de CPU y no era real). Antes de medir, comprobar que no hay pantalla de bloqueo (`LogonUI`).
  ⚠️ Sin medir: el consumo de cada estilo y de «Muchas» con la pantalla activa, y si se nota un parpadeo al cambiar.
  La ventana va por secciones plegables desde el 2026-11-01 (Estilo, Viento en el mapa, Concentraciones en el mapa;
  usuario: «desplegable también las opciones de configuración»), plegadas al abrir.
- **Escalas de color (pedido del usuario, 2026-11-01: «diferentes colormap para el viento y gases y para olores»).**
  `gui/escalas.py`: Turbo, Viridis, Plasma, Inferno, Cividis, Amarillo a rojo, Verde a rojo y Azul a rojo (los 5 colores
  de siempre del viento). Preferencias `escala_viento`, `escala_olor` (Turbo) y `escala_gases` (Viridis), con su tira en
  la configuración. Se aplican al momento. **Viento:** 5 colores, uno por clase de velocidad (`W.pal`), solo con «Por
  velocidad»; con blanco, su selector se bloquea. **Concentraciones:** las imágenes de los planes van en GRISES con alfa
  (`penacho_mapa.pintar(escala=None)`, PNG LA: 54 imágenes en 0,34 MB frente a 0,83) y el color lo pone el navegador, con
  un filtro SVG (`ence.setEscalas`; cada imagen lleva la clase `escala-olor` y la leyenda el degradado `--escala-olor`):
  no se rehace ninguna imagen ni se recarga el mapa. Sin `color-interpolation-filters="sRGB"` saldría mal. **Validado
  contra matplotlib:** sobre blanco, error medio 0,14-0,41 de 255 (máx. 5); en la app, sobre la ortofoto, 0,79 de media en
  los píxeles distintos, P99 3, máx. 16. A zoom 18 también funciona. `penacho_dia` sigue en color: mismos bytes que antes.
  ⚠️ RECTIFICACIÓN (2026-11-01): ya los simula, ver «Gases y olor estimado». ⚠️ **La app aún NO simula gases:** su escala se guarda y su filtro existe, pero no hay capa que los use; una capa de gases
  solo tiene que pasar `escala="gases"`. Las rosas de las estaciones conservan sus colores (elección del usuario).
  ⚠️ Consumo del filtro con el reproductor en marcha, medido con el PC BLOQUEADO (orientativo): con GPU 0,8-1,0 % del
  equipo frente a 0,7-0,9 % sin filtro (≈ 5 fps en los dos); con `--disable-gpu` 4,3-4,7 % frente a 2,2-2,3 % (≈ 2 fps).
  Sin GPU, el filtro duplica el consumo: repetir con la pantalla activa y mirar qué GPU tiene el PC del operario.
- **Vista previa en la configuración (decisión del usuario, 2026-11-01: «que sirvan solo como ejemplo de visualización en
  el configurable»).** La ventana va a dos columnas: opciones (640 px) y un mapa propio (`gui/vista_previa.py`, una
  `VistaMapa` con su página `mapa_previa.html`) con UNA hora de viento y de penacho de `gui/recursos/ejemplo/` (~100 kB;
  lo escribe `gui/tareas/ejemplo_configuracion.py`: la hora con más receptores por encima de 10 ou_E/m³, hoy 2026-10-21
  07:00, máximo 360, con los focos de ejemplo). Van con la app: funciona con DATOS vacío (probado). Su leyenda no lleva
  unidades, para que nadie lo tome por un resultado. Elegir una escala de olores o de gases enseña el penacho con esa
  escala (capas `previa_olor`, `previa_gases`). Solo pinta si se ve: cerrada o minimizada, la página queda oculta
  (comprobado con `visibilityState`, también con la ventana principal minimizada). ⚠️ El viento de un día de los DATOS
  locales (`odora_gfs_8est`) sigue saliendo en Reanálisis hasta que vuelva Z: con la serie de verdad.
- **Leyenda y panel del tiempo (usuario, 2026-10-31):** con el panel del tiempo a la vista, la leyenda llega como mínimo
  hasta el borde izquierdo del icono de día o noche (`igualaLeyenda`, en cada hora: el rótulo cambia el ancho del panel).
- ⚠️ **Los mapas no pueden esperar a las teselas (2026-10-31, lo vio el usuario: el plano de focos sin focos, sin recuadro
  y de lejos).** `iniciar` iba en `window.load`, que espera a TODAS las imágenes: sin él no hay `ence` y `VistaFocos` y
  `VistaMapa` guardan sus órdenes. Medido con un servidor de teselas que nunca responde: sin estar listos a los 20 s; con
  `DOMContentLoaded` (los scripts ya se han ejecutado), 1,6-2,3 s con los 13 focos, el recuadro y la leyenda. Es de
  2026-10-26: no lo trajo el rediseño. En pruebas, esperar a `_listo`, no un tiempo fijo. Medido con el servidor real, la
  app abierta y el PC bloqueado: focos a los 1,0-1,8 s, ortofoto entera a los 3,4-4,7 s y recuadro visible en los 13 focos en
  las dos ventanas. Hasta que llega la ortofoto, los focos se ven sobre el fondo oscuro.
- **Cerrar la app (lo vio el usuario, 2026-11-02: «se queda la app sin poder cerrar»; `99-Test/11_cierre`):** la principal cierra ya focos, planes y configuración, cada una pregunta si tiene cambios y, con «Cancelar», la principal sigue abierta. Antes la app seguía viva con ellas abiertas y el diálogo bloqueaba la X de todas. El diálogo (`widgets.preguntar_si_guardar`) bloquea solo su ventana, va siempre encima y en español (sin traductor de Qt salía «Save / Discard»). «No guardar» en planes ya descarta: antes, al reabrir, salían los cambios. ⚠️ Con la pregunta abierta, `QWidget.close()` devuelve True sin mandar el evento: `pregunta_abierta` se mira ANTES (la 1.ª versión del arreglo perdía el plan). ⚠️ Sin probar con ratón real: PC bloqueado, X simulada con WM_CLOSE.
- **Ficha del mapa al apartar el ratón (lo vio el usuario, 2026-11-02: «como si faltase conexión»; `99-Test/12_ficha_mapa`):** Leaflet la pone a opacidad 0 y la borra 200 ms después, y `opacity:1!important`, de la interfaz moderna, anulaba ese 0: seguía entera a la vista 209 ms. Ahora, menos de 1 ms en el mapa principal y en el plano de focos; la opacidad 1 es la opción por defecto (`L.Tooltip.mergeOptions`). Comprobado también con ratón real. ⚠️ Sin medir: el coste del desenfoque de la ficha con pantalla.
- **Capturas fieles:** plataforma real con `WindowStaysOnTopHint + WindowTransparentForInput +
  WindowDoesNotAcceptFocus` y el escalado real de la pantalla. `WA_DontShowOnScreen` deja la web en blanco y
  `offscreen` esconde los fallos de color; `QWidget.grab` guarda el contenido sin robar el ratón.
- **Comprobado (2026-10-31, DATOS locales, sin Z:):** 20 capturas vistas una a una (páginas, simulación, día con
  penacho, tooltips, capas con leyenda, menú, calendario, focos y planes, modo operario y CIRCE); `main.py --dia
  2026-10-21 --circe --focos --planes` arranca, cierra guardando y sin avisos en el registro; clics simulados en la
  ventana de planes, sin fallos; la simulación da el mismo máximo con el plan Base (423 ou_E/m³). ⚠️ Falta probarla en
  otra pantalla y en el PC del operario (WebEngine y GPU), con Z: y con ratón de verdad.

### Capas del mapa (decisiones del usuario, 2026-10-15)
- **Siempre visibles y FUERA del selector:** la planta y los núcleos (`control=False`).
- ⚠️ RECTIFICACIÓN (2026-10-31, decisión del usuario): Elevación, Uso del suelo y Edificios ya NO están en el selector:
  solo se encienden con sus botones del panel (`selector: false`, `ponCapa` en `mapa_web`); siguen siendo excluyentes.
- **Selector = capas temáticas EXCLUYENTES:** Elevación, Uso del suelo y Edificios (grupo
  `GRUPO_TEMATICO` en `gui/ventana.py`): al activar una se apaga la anterior; se pueden apagar
  todas. La exclusión se hace en un `setTimeout` tras el clic: Leaflet 1.9 lista las casillas
  marcadas antes de añadir y, si se quitaba la anterior durante el recorrido, la volvía a meter.
- Fondos: solo Satélite (PNOA) y Callejero (OSM).
- **Al arrancar:** ninguna capa temática encendida y TODAS las secciones del panel plegadas.
  Una capa solo se enciende sola justo después de descargarla.
  ⚠️ RECTIFICACIÓN (2026-10-31, rama `interfaz-moderna`): la app abre en la página Inicio; solo se pliegan «Elevación» y
  «Usos del suelo», en Planta, y empiezan plegados. Las capas pierden el emoji («Viento · partículas», «Penacho · media del día»…).
- **Leyendas:** siempre completas, sin barra de desplazamiento (35 clases de uso del suelo);
  si no caben en el alto del mapa se reparten en 2-6 columnas (`ajustaLeyenda`, también al
  redimensionar).
- **Selector de capas delante** (2026-10-22, el usuario no podía cambiar de capa: «queda por
  detrás de una leyenda»). Las esquinas de Leaflet tienen el mismo z-index (1000) y la de ABAJO
  (leyenda, panel del penacho) va después en la página, así que tapaba la lista desplegada del
  selector (arriba a la derecha). Ahora: (1) con el ratón encima o el foco dentro, su esquina
  lleva la clase `ence-delante` (z-index 1001); (2) `ajustaLeyenda` reserva 64 px arriba para
  el ICONO del selector y descuenta los otros controles de su esquina, para que nunca quede
  tapado (si no, no se puede ni desplegar). Medido en Edge, ventana de 700 px con uso del suelo
  + penacho: icono libre (leyenda a 3 columnas), y en un punto común a la lista y al panel el
  ratón llega al SELECTOR (sin el arreglo, al PANEL). ⚠️ Leaflet escucha `mouseover`, no
  `mouseenter`: para simular el ratón en pruebas hay que disparar `mouseover` con `relatedTarget`.

### Edificios (2026-10-15)
- `lib/galera/entradas/edificios.py`: WFS del Catastro (INSPIRE BU) a menos de 2 km (`config.RADIO_EDIFICIOS_KM`),
  descargado UNA vez → `DATOS/edificios/<lat>_<lon>_r2km/edificios.gpkg` (solo dato transformado,
  guía 10). 867 edificios: 393 residenciales, 279 agrarios, 177 industriales. Capa «Edificios
  (Catastro)» por uso + círculo de 2 km; el clic en el mapa dice qué edificio hay.
- ⚠️ Altura = plantas × 3 m: los elementos de la propia planta salen con 11 y 14 «plantas»
  (33 y 42 m): son depósitos/digestores. Pedir a ENCE las alturas reales antes de usar BPIPPRM.
  ⚠️ RECTIFICACIÓN (2026-11-01, medido con el LiDAR del ICGC): no eran digestores. El polígono de «8 plantas» (4 560 m²) mezcla
  balsas a ras de suelo y depósitos, y el de «14 plantas» mide 2,4 m. Lo real: 2 digestores de 13,3 m, tanques de 11,7 y
  6,4 m y una nave de 9,8 m; tabla en `99-Test/06_viento_local/README.md`. Las plantas del Catastro NO sirven aquí como altura.
  (2026-11-01: con solo los puntos de clase edificio, la nave sale de 9,1 m y el tanque bajo de 6,3 m.)
- 2026-10-24: descargados también en los DATOS LOCALES (`%TEMP%\ence_galera\datos_local`, sin Z:)
  a petición del usuario, en 255 s: los mismos 867 (393 residenciales, 279 agrarios, 177
  industriales, 7 comerciales, 6 servicios públicos, 4 otros, 1 oficinas; 18,2 ha construidas;
  el más cercano, industrial a 3 m, es la propia planta).
- **Solo los edificios a 200 m** (decisión del usuario, 2026-10-24: «los que importan para los
  focos»; estelas de chimenea ≈ 5 × la altura del edificio): `config.RADIO_EDIFICIOS_FOCOS_M = 200`,
  `edificios.cercanos(bld)`. El panel («Edificios cercanos (Catastro, 200 m)»), la capa del mapa y
  el clic en el mapa usan esos; se siguen DESCARGANDO a 2 km porque las 393 viviendas son
  receptores (malla de 12 656 con `ventana._edif_todos`). Hoy son 5: 3 de la propia planta (nave
  de 4 560 m² con «8 plantas», un elemento de 14 «plantas» ≈ 42 m a 33 m y otro de 11 «plantas» y
  8 m² a 81 m) y 2 casetas agrarias a 120 y 141 m. El radio se mide desde la posición de la
  planta; con los focos de ENCE, medir desde cada foco. El bloque del panel enseña SOLO la fecha
  de descarga, el número por categoría y el botón «Ver edificios» (decisión del usuario).
- **Los edificios y el viento (preguntado por el usuario, 2026-11-01; sin decidir).** `viento3d` no los ve: celda de 400 m
  (edificios de 375 × 316 m en 2 celdas), relieve sin construcciones, planta como «Olivares», primer nivel 0-20 m. Bajar
  su celda a 10 m en un radio de 200 m NO lo arregla: es diagnóstico (terreno, Froude, ladera, O'Brien; sin obstáculos ni
  recirculación), tiene una sola rejilla y `puffs` lee un solo fichero de viento (no anida). Sale de cómo está formulado:
  no se ha corrido a 10 m. Lo que hace falta es un modelo local aparte, precalculado por direcciones. ⚠️ Además, hoy la
  dispersión tampoco usa edificios: `control_fuentes` no pasa a `puffs` sus dimensiones ni el campo `edificio` de los focos,
  que solo cuenta para `pendientes` y `huella` (`lib/odora/PENDIENTES.md` §3).
  **Habrá sensores tan cerca (usuario, 2026-11-01): prueba `99-Test/06_viento_local`.** Prototipo de masa consistente con zonas
  empíricas y alturas del LiDAR: ~10 s por dirección a 2,5 m (3,6 M celdas, ±300 m). Cubo: reataque 1,35-1,38 H frente a 1,61 H
  medido (Martinuzzi y Tropea 1993), pero 0,75 H con 2 celdas por lado: **hacen falta unas 4 celdas por obstáculo, así que 10 m no
  vale** (a menos de 50 m, 10 % de error frente a 3 % con 5 m). Cambio de más del 20 % hasta 43-76 m del edificio, ⚠️ limitado por la fórmula de
  la estela: probablemente corto. Sin validar la estela lejana, sin estabilidad (noches en calma), sin concentraciones y con los
  ~30° de error de entrada.
  **Dos motores de viento en el mapa (decisión del usuario, 2026-11-01: «más visual que preciso, para que el cliente vea que los
  edificios influyen»).** Zona: `viento3d`, 400 m, sin edificios, como siempre. Planta: `lib/galera/viento/local.py` (⚠️ pendiente
  de llevar a odora; ⚠️ RECTIFICACIÓN del 2026-11-02: ya está en `teodors.meteo.viento_local`, tanda 2), biblioteca de 36 direcciones en `gui/planta/viento_local.npz` (2,45 MB, 200 × 200 celdas de 2,5 m; la rehace
  `gui/tareas/viento_local_biblioteca.py` en 7 min desde `DATOS/viento_local/planta_1m.npz`, que sale de
  `gui/tareas/lidar_planta.py`; hay que rehacerla si cambian los edificios). Cada instante, la dirección y la velocidad de la zona en la planta
  eligen y mezclan los 2 campos más cercanos (`mapa_web.campoLocal`). Radio 200 m desde los depósitos (286 796, 4 507 440), no desde la marca,
  que queda en el borde NO; fundido hasta 250 m. Va también en la vista previa. ⚠️ RECTIFICACIÓN (2026-11-01, decisión del usuario): la casilla «Edificios de
  la planta» de la configuración se quitó; el motor está SIEMPRE activo (sin la biblioteca, solo queda el de la zona).
  ⚠️ RECTIFICACIÓN (2026-11-01, decisión del usuario, «dada su proximidad con la planta también quiero que le aplique el viento local»): ya no es un círculo, sino la banda a menos de 200 m del
  segmento depósitos-Dacame (286 228, 4 507 320), con el mismo fundido hasta 250 m (`mapa_web.enPlanta`). Biblioteca de 6,37 MB, 248 × 427 celdas, 45 edificios; rehacerla son 10 M de celdas y unos 44 min con prioridad baja y otros
  cálculos a la vez. `planta_1m.npz` crece a x 285 912-287 112 con las mismas 2 teselas, que empiezan en x = 286 000: los últimos 22 m del fundido al oeste no tienen LiDAR. Dos fallos que Dacame sacó a la luz en `local.py`: (1) la regla de los depósitos
  pegados troceaba sus naves en 53 trozos, porque cada cumbrera es un pico: ahora une los picos del mismo tejado (`_misma_cubierta`: alturas parecidas y, por la recta entre ellos, sin bajar de la mitad; depósitos 0-0,22, dientes de sierra ≥ 0,56); (2) los cables
  de alta tensión levantaban un cobertizo de 3 m a 31 m: la altura de un edificio sale ya solo de los puntos de esa clase. **Comprobado frente a la biblioteca anterior, en la planta:** mediana 0,003 y P95 0,02 veces el viento de entrada, con las 5 piezas de siempre (la nave, de 9,8 a 9,1 m por ese cambio).
  Naves de Dacame: 14 439 m² de 9,8 m y 7 489 m² de 10,9 m. ⚠️ Toda la banda toma la dirección y la velocidad de la celda de la planta. ⚠️ Sigue siendo solo el dibujo del viento: el penacho y los valores en Dacame NO cambian (`puffs` lee un solo viento).
  ⚠️ **Solo enseña.** Cada campo va relativo al viento sin edificios a 3 m, para no dibujar un círculo donde el viento se frene: NO es la velocidad real a
  3 m (sería ~0,67 veces esto), así que no sacar de aquí valores para un sensor, y el penacho NO lo usa (`puffs` lee un solo viento): a zoom de planta
  el penacho no rodea los depósitos. ⚠️ La capa de la zona se coloca en pantalla con una sola transformación para 50 km y se desvía ~40 m en el centro
  (estimado por la curvatura y visto en la prueba: el campo caía fuera de los depósitos). La planta tiene su propia transformación (`VL.P`, `VL.Ei`, `VL.Ej`).
  Comprobado: el mapa coincide con Python en 48 puntos; a 195 m, planta / zona = 0,99 (de 0,88 a 1,04); 2,2 ms por fotograma a zoom 18 (PC bloqueado, solo el JS).

### Panel: botones «Ver …» y emplazamiento (pedido del usuario, 2026-10-24)
- Emplazamiento SIN la línea «Convergencia γ: −1,65° (≈ … m a 7 km)» (sigue en el registro al
  arrancar, como dato técnico).
- Botones que encienden la capa temática: «Ver elevación» justo debajo de los datos de cota,
  «Ver usos del suelo» debajo del árbol de usos y encima de los núcleos, «Ver edificios» debajo
  de los datos de edificios. Son conmutadores («Ocultar …» al estar encendida) y siguen la
  exclusión del grupo temático. Van SINCRONIZADOS con el selector del mapa en los dos sentidos:
  `ence.verCapa(id, si)` y, en `overlayadd`/`overlayremove`, el aviso `{evento: "capa", id,
  visible}` → `VistaMapa.capa` → `Panel.set_capa_visible`. Comprobado sin pantalla: cada botón
  enciende la suya y apaga las otras; el selector actualiza los botones; pulsar otra vez apaga.
### Meteorología (2026-10-15)
- **ERA5** (`lib/galera/entradas/meteo.py`, `lib/galera/gui/tareas/descargar_era5.py`, caché `DATOS/meteo/era5/`): celda
  40,75 N 0,50 E (6,9 km al N, tierra-mar 0,74, cota del modelo 267 m frente a 98 m reales).
  Superficie 2021–2025 por el dataset **«ERA5 time-series»** (5 años en ~1 min; idéntico a la
  cola mensual, |Δ| ≤ 0,0003 °C; pide `date` "aaaa-mm-dd/aaaa-mm-dd") + u* aparte por AÑOS (el CDS
  lo acepta). Perfil horario 975–700 hPa por quincenas en la cola normal (lenta: 10 min–4 h por
  petición). El perfil del time-series NO sirve: 6-horario y sin 975/950/900 hPa.
- **Meteocat XEMA** (`lib/galera/entradas/estaciones.py`): abierto y sin clave (Socrata `nzvn-apee`), cada 30 min,
  hasta ~2 h antes de ahora (⚠️ RECTIFICACIÓN, medido el 2026-11-01: acababa el 26/10 a las 17:30 en las 8 estaciones; sin ver aún si es puntual). Hora **UTC con etiqueta de INICIO** del intervalo (comprobado con el
  ciclo de radiación en las 7 estaciones). Pedir MES a MES (el año entero agota el tiempo). 8
  estaciones a < 20 km; viento a 10 m: Mas de Barberans C9 (7 km), Amposta UU, PN dels Ports X5
  (1056 m); el resto a 2 m (calmas no comparables con 10 m: abrigo del anemómetro).
- **Validación ERA5 vs Meteocat** (`lib/galera/viento/validacion.py`, Emery 2001): ERA5 acierta velocidad
  (IOA 0,69–0,84) y temperatura (error 1,2–2,0 K), pero **FALLA la dirección en TODAS las
  estaciones (error 33–56° > 30°)**: no ve la canalización local (valle del Ebro, Sénia, Ports).
  Es la referencia que WRF / las observaciones tienen que mejorar.
- Procesos largos: lanzarlos con `Start-Process` (independientes de la sesión). Al suspenderse el
  PC, las conexiones HTTP pueden quedarse colgadas: relanzar (todo es reanudable). Un REINICIO
  del PC mata la descarga (pasó el 2026-10-15 a las 20:05): relanzar `lib/galera/gui/tareas/descargar_era5.py`.
- ⚠️ El CDS puede PERDER peticiones ya enviadas (2026-10-16: dos quincenas de 2022 desaparecieron
  de la cuenta y respondían 404). `requests.HTTPError` hereda de OSError y se tomaba por corte de
  red → se esperaban 48 h. Ahora `meteo._es_de_red` mira el código: 4xx → se reenvía; 5xx/429
  y cortes de red → se espera la MISMA petición. En esta red hay cortes de DNS frecuentes.
- **Pruebas sin pantalla:** `QT_QPA_PLATFORM=offscreen` + `QT_QPA_FONTDIR=C:\Windows\Fonts` para
  que salga el texto. El contenido web sale en blanco en offscreen: para ver el mapa, captura del
  HTML con `msedge --headless=new --screenshot`. Comprobar geometrías numéricamente, no solo a ojo.
- **Estaciones en el mapa** (2026-10-15, pedido por el usuario): las 8 de Meteocat con icono de
  estación (mástil con anemómetro y veleta, verde azulado) y su código; SIEMPRE visibles y fuera
  del selector, como planta y núcleos. Se leen solo de la caché (`estaciones.para_mapa`, sin red
  al arrancar). Tooltip con altitud, altura del anemómetro, distancia y error de ERA5; clic →
  ficha en la consola.
- **Bloque Meteorología** (2026-10-15): horizonte Ninguno (al arrancar) / Reanálisis / Tiempo
  real y Predicción (deshabilitados, pendientes). Con **Reanálisis**, el tooltip de cada
  estación lleva su **rosa de los vientos 2021–2025** (pétalos por clase de velocidad a la
  altura del anemómetro, calmas; colores de lento a rápido azul → verde → amarillo → naranja →
  rojo, elegidos por el usuario: los tonos azules no le gustaron) (`validacion.rosas_estaciones`, caché
  `DATOS/meteo/validacion/rosas_estaciones.json`; `mapa_web.rosa_svg`).
  **Decisión del usuario: NADA de ERA5 en el tooltip de las estaciones**, con ningún horizonte
  (ni la línea «error de dirección» ni la rosa de ERA5 superpuesta). `rosa_svg(..., era5=…)`
  sigue admitiendo la línea por si se usa en otro sitio. La ficha de la consola (clic) sí
  conserva el dato de ERA5. Medido: las estaciones a 2 m tienen 30–44 % de calmas.

### Plan de reanálisis calibrado (2026-10-20)
- El usuario sigue `Escritorio\Mountains\inundaciones\PLAN_REANALISIS_LA_GALERA.md` (OneDrive,
  SOLO LECTURA): CALMET de odora calibrado con estaciones (80/20 por semanas), validado en la
  estación objetivo, sin .exe de terceros, paso a paso con PARADAS. **Estación objetivo = Mas de
  Barberans (C9)** («comparar con Barberans»: la más cercana a la planta; no hay estación
  operativa «La Galera»). Ir poco a poco: enseñar y esperar el visto bueno en cada paso.
- **Paso 1 / F1 en C9** (`lib/galera/gui/tareas/f1_estacion.py` → `DATOS/reanalisis/01_estacion_C9/`): sin
  duplicados, rangos, atascos ni picos; 99,8 % de horas válidas (2021-2025). Rosas: de noche
  NO/ONO/O (drenaje y mestral), de día S y E-SE (brisa), verano S, invierno NO.
  ⚠️ **Anemómetro sospechoso desde junio de 2025**: calmas 1-2 % → 10-17 %, ceros exactos con
  ERA5 > 2 m/s (antes nunca), C9/ERA5 cae a 0,62 en dic-2025; las vecinas no cambian (Amposta
  1,1→1,3 %). Probable rozamiento/umbral del sensor. Decisión del usuario: invalidar SOLO los
  0 m/s exactos desde 2025-06-01 (`CEROS_SOSPECHOSOS`).
- **Cambio de enfoque (decisión del usuario, 2026-10-20):** lo que quiere es **aprendizaje
  automático puro que corrija ERA5 en C9 a partir de las estaciones vecinas** (no calibrar los
  parámetros de CALMET, que es lo que proponía el plan §5.3). Se mantiene del plan: C9 nunca es
  entrada, partición 80/20 por SEMANAS (no horas sueltas), referencias que batir, métricas de
  §5.4 de día y de noche, y PARADAS. Entradas: ERA5 en el punto (superficie + perfil 975-700 hPa)
  y las 7 estaciones (U7, U9, US, UU, UW, UX, X5; datos 2021-2025 al ~100 %). Salida: u, v en
  C9 a 10 m. Pendiente decidir después cómo llevarlo a la planta y al dominio (pseudoestación en
  odora o modelo espacial validado dejando fuera cada estación).

### Metodología del reanálisis: referencia de UN mes (decisión del usuario, 2026-10-20)
- El usuario quiere la METODOLOGÍA con un mes (rosas y errores de velocidad y dirección en las
  estaciones) y probar ahí cómo reducir el error; los 5 años solo cuando esté claro el método.
  Mes de prueba: **julio de 2024** (hay también cadena V2 de ese mes; C9 sano).
- `referencia_mes.py` (borrado el 2026-10-23; en el zip de archivo) (odora v0.1.1 vía `casos.ejecutar`, ERA5 una columna,
  NOOBS = 2; 4,7 min) → `DATOS/reanalisis/02_referencia/202407_era5/` (metricas.csv, series.csv,
  rosas.png, planta.csv). **Referencia, media de las 8 (odora / ERA5 tal cual):** dirección
  38,2 / 40,3° (día 36,5 / 36,9 · noche 43,7 / 49,2); sesgo de velocidad −0,06 / +0,89 m/s;
  RMSE 1,40 / 1,74; desajuste de la rosa 38,2 / 36,6 % (noche 53,7 / 47,4: odora crea drenajes
  con la dirección equivocada, p. ej. O en US donde se mide NO). Peor X5 Els Ports 50°.
  Calmas medidas a 2 m altísimas (UX 33 %, U7 30 %, U9 14 %) frente a 5-8 % del modelo: abrigo
  del anemómetro; las de 10 m (C9, UU, X5) son la referencia más fiable de rosa y calmas.
- **Método 1: odora + estaciones** (`metodo_estaciones.py` (borrado el 2026-10-23; en el zip de archivo), julio 2024, 28 min, 9 casos
  ~10 min cada uno; R1 5 km, RMAX 30 km; obs con el control de calidad de F1) →
  `DATOS/reanalisis/03_metodo_estaciones/202407/`. **En la estación DEJADA FUERA (7 dentro),
  media de las 8: dirección 38,2 → 30,6°** (día 36,5 → 29,8 · noche 43,7 → 33,6); por estación
  C9 34,8 → 29,6 · UU 42,4 → 23,5 · U9 37,4 → 21,9 · UW 34,4 → 24,3 · US 40,7 → 35,5 · UX 38,1 →
  34,6 · X5 50,4 → 47,1 · U7 27,5 → 28,1. RMSE de velocidad 1,40 → 1,30; sesgo −0,06 → −0,37
  (las de 2 m, abrigadas, bajan la velocidad de alrededor); rosa 38,2 → 35,3 % (noche 51,7 %).
  Con las 8 dentro sale casi perfecto por construcción (1,6°). A diferencia del MOS de
  predicción, las medidas reales SÍ se transmiten (sobre todo entre estaciones cercanas en el
  llano: UU, U9, UW); no ayudan en las aisladas o de montaña (X5, UX, U7).
- **Series de 5 años con las 8 estaciones** (decisión del usuario del 2026-10-21; lanzadas ese
  día, PID 30312, `lib/galera/gui/tareas/viento3d_series.py --procesos 8`, log en `DATOS/logs/viento3d_series.log`):
  ERA5 + 8 estaciones (NOOBS = 1, R1 5 km, RMAX 30 km, 24 h de arranque) con **odora** y con
  **calmet.exe**, cada una aparte: `DATOS/viento3d/odora_era5_8est/` y `…/exe_era5_8est/` (antes `calmet_era5_8est`; motor `exe`)
  (`cmz/AAAAMM.cmz` + `AAAAMM/` con puntos.csv, caso.json, CMET.INP, resumen.json).
  `viento3d_casos.mes_serie(anio, mes, motor, nombre, estaciones)` (gui/tareas); reanudable. Medido con 8 a la vez:
  odora 15-20 min y calmet ~54 min por mes; ~450 MB por .cmz; ~4 GB locales por mes en marcha.
  **PARADAS por el usuario el 2026-10-21 (~19 h):** odora 18/60 (2021-01 a 2022-06) · calmet
  12/60 (2021-01 a 2021-10, 2022-01, 2022-02); los meses a medias se borraron (se rehacen).
  **Reanudar:** `C:\e2s\python.exe lib\galera\gui	areas\viento3d_series.py --procesos 8` (salta los meses con
  .cmz). ⚠️ El .log redirigido a Z: no se actualiza durante la corrida (caché de la unidad de
  red): mejor redirigir a %TEMP% o vigilar los .cmz.

### Encaje por alcance y fuentes de predicción gratuitas (2026-10-20)
- Revisado con el usuario: el ML «ERA5 + estaciones → C9» NO es producto en ningún alcance (en
  pasado y presente C9 está medida y entra en odora; en predicción no hay estaciones). El ML va
  como **MOS de la PREDICCIÓN por estación** (alcance 3, y para rellenar huecos en el 4), y las
  predicciones corregidas entran en odora como pseudoestaciones. Alcances 1-2: odora + estaciones.
- **Idea del usuario (2026-10-24) → APLAZADA al alcance 3** de la oferta («predicción a 3–5 días»,
  diap. 9 de la v4: actualización automática cada día). Modelo predictivo PROPIO entrenado con los
  5 años simulados del viento en todos los receptores: cada día entran las medidas más recientes
  de las estaciones (Meteocat, ~2 h de retraso), sale el viento de las próximas 24 h, al día
  siguiente se valida con lo medido y el modelo se va corrigiendo. Lo hablado (sin decidir):
  (1) solo con las horas pasadas se predicen bien las primeras 3-6 h (persistencia, ciclo diario)
  pero no los cambios de situación (entrada del mestral): propuesta híbrida = últimas horas de
  las estaciones + GFS de las próximas horas + hora del día (= el MOS del paso 3, que ya da 24,7°
  a un día, ampliado con observaciones recientes), midiendo también la variante «solo
  estaciones»; ⚠️ PREGUNTA ABIERTA al usuario: ¿con GFS o solo estaciones?; (2) pasar de las
  estaciones a los receptores aprendiendo del reanálisis (emulador de odora), validando con una
  estación fuera (fuera de las estaciones el reanálisis tiene ~30° de error); (3) corrección
  diaria del sesgo (filtro de Kalman) + reentrenamiento periódico, con semanas que el modelo no
  ve; (4) necesita la serie de 5 años TERMINADA (18/60 meses el 2026-10-21, hace falta Z:).
  Pasos propuestos: referencias a 1-24 h en las 8 estaciones (persistencia, ciclo medio, GFS,
  MOS) → modelo en las estaciones → receptores → ciclo diario como tarea de la app (05-06 UTC).
  El alcance 3 habla de 3-5 días: más allá de ~12 h el modelo sería esencialmente el MOS de GFS
  (día 5: 32,7° en las estaciones).
- Decisión del usuario: predicción **con la fuente gratuita**. Comprobado el 2026-10-20 (todas
  gratis con cita; el MOS necesita ARCHIVO de predicciones pasadas, no reanálisis):
  - **GFS 0,25°** (16 días): runs completos desde **2021-05** en dynamical.org (Icechunk/Zarr,
    CC BY 4.0, 0-120 h horario) y GRIB en `s3://noaa-gfs-bdp-pds` desde 2021-01. Única con 5 años.
  - **ICON-EU 7 km** (5 días, DWD, CC BY 4.0 según fuentes secundarias: confirmar en dwd.de): runs
    completos solo desde **2026-02-10** (dynamical, sin niveles de presión); el DWD guarda ~24 h.
  - **AROME** 0,01°/0,025° (Météo-France, Licence Ouverte; solo hasta 42-51 h).
  - **ECMWF IFS** abierto 0,25° (CC BY 4.0), runs en AWS desde 2023-01-18.
  - **Open-Meteo**: su API gratuita es NO comercial, pero su base de datos en AWS
    (`s3://openmeteo`, formato .om, `python-omfiles`) es **CC BY 4.0**: serie continua de ICON-EU,
    AROME HD, GFS… desde 2023-12-15 (incluye niveles de presión); runs completos solo 3 meses.
    Esto resuelve también la licencia de la cadena V2 (ICON + AROME) del reanálisis 2024-2025.
- **Paso 1 del MOS: archivo de GFS** (`lib/galera/gui/tareas/descargar_gfs_historico.py`, 2026-10-20): ejecución
  00 UTC, plazos 0-120 h horarios, caja 5 × 5 puntos (40,25-41,25 N, 0-1 E), 9 variables (u, v a
  10 y 100 m, T y HR a 2 m, nubosidad, onda corta, presión al nivel del mar) →
  `DATOS/meteo/gfs/gfs00_AAAAMM.nc` (un mes por fichero, reanudable; ~0,9 MB/mes; unidades de
  dynamical: °C, %, W/m², Pa). Medido: ~3,3 MB de tráfico por ejecución·variable (se lee el
  bloque de 121 × 121), 39 s por mes con 16 hilos, ~60 GB y ~40 min en total. Comprobado: plazo
  0 frente a ERA5 en la planta, r(u) 0,76 · r(v) 0,86 · T 14,7 frente a 15,0 °C.
  **Descargado el 2026-10-20 en 41 min:** 65 meses (2021-05 a 2026-09), 1 979 de 1 979 ejecuciones
  00 UTC, 54,7 MB; vacíos 0,017 % (nubosidad y onda corta 0,84 %: no existen en el plazo 0).
- **Paso 2 del MOS** (2026-10-20): control de calidad de las 8 estaciones con `f1_estacion.py`
  (todas limpias, cobertura 98,5-99,8 %; UX 37 semihoras de velocidad atascada, US 17 de
  dirección) y `lib/galera/gui/tareas/mos_tabla.py` → `DATOS/mos/`: `tabla_gfs00.parquet` (1 642 213 filas =
  estación × ejecución 00 UTC × plazo 0-120 h con medida; GFS bilineal al punto; 109 MB en
  float32), `particion.csv` (por SEMANA de la hora de VALIDEZ, semana ISO + año ≡ 0 mod 5 →
  validación: 20,1 %, por estación del año 19,1-20,7 %, por año 19,2-21,1 %) y
  `referencia_gfs.csv`. **GFS sin corregir, validación, media de las 8:** dirección 37,6° (día 1)
  → 38,3 · 39,0 · 41,6 · 44,4° (día 5); sesgo de velocidad +1,8 m/s (+2,0-2,5 en las de 2 m,
  +0,6-1,1 en las de 10 m); RMSE ~3,0-3,2 m/s. El «día 0» es solo la hora 00 UTC (noche).
- **Paso 3 del MOS** (`lib/galera/gui/tareas/mos_entrenar.py`, 2026-10-20; ~5 min): por estación, modelos de
  u, v y velocidad (dirección de u y v; velocidad aparte), ridge («lineal») y HistGradientBoosting
  («gb», iteraciones elegidas con semanas internas del ENTRENAMIENTO: 40-150). Entradas: GFS en
  el punto + hora, día del año y plazo. **Validación (20 %), media de las 8, día 1 → día 5:**
  dirección GFS 37,6 → 44,4° · lineal 27,4 → 34,7° · **gb 24,7 → 32,7°**; sesgo de velocidad
  +1,85 → ~0; RMSE 3,07 → **0,83** m/s (día 5 1,06); rosa 28,8 → **16,4 %**; calmas −15,5 →
  −5,9 puntos (el MOS sigue dando pocas calmas). De noche gb 23,4° (día 1). C9 41,9 → 33,7°;
  U7 Aldover 32,9 → 14,4°. Salidas en `DATOS/mos/` (`modelos/`, `prediccion_valid.parquet`,
  `metricas.csv`). ⚠️ Es el error EN las estaciones: el de la planta y los pueblos (sin
  estación) solo se puede estimar dejando una estación fuera (paso siguiente propuesto).
- **Paso 4 del MOS, «dejando una estación fuera»** (2026-10-20, en marcha): 8 semanas de
  VALIDACIÓN (2 por estación del año, antes de 2025-06 por el anemómetro de C9: 2021-11-01,
  2022-01-17, 2022-07-11, 2023-04-24, 2023-10-16, 2024-07-29, 2024-12-16, 2025-04-07).
  Campo inicial de GFS 0,25° con niveles de presión (`lib/galera/gui/tareas/descargar_gfs_niveles.py`: GRIB
  de `s3://noaa-gfs-bdp-pds` por rangos con el .idx, `pygrib` de C:\e2s; 7 niveles 1000-700 hPa
  × z, T, u, v + 8 de superficie; plazos 0-24 h cada 3 h; ~36 MB de tráfico por plazo; 72
  ejecuciones en 20 min, 5 MB → `DATOS/meteo/gfs_niveles/`). `mos_fuera_una.py` (borrado el 2026-10-23; en el zip de archivo):
  4 × 4 columnas cada 12,5 km, predicción a 1 día (hora H de la ejecución de las 00 UTC de
  H − 1 h, interpolada entre plazos de 3 h), 24 h de arranque; casos «gfs» (NOOBS = 2) y
  «mos7_sin_X» (MOS gb de las otras 7 como pseudoestaciones, R1 5 km, RMAX 30 km) para X = C9,
  UU, UX. odora ~5 min por caso de 192 h; 32 casos con 4 procesos. Velocidad de odora a 2 m con
  perfil logarítmico y z0 = 0,1 m fija (aproximación). Salida `DATOS/mos/fuera_una/`.
  **Resultado (31 min, ~1 340 h por estación y fuente):** en la estación DEJADA FUERA, dirección
  C9 / UU / UX: GFS en el punto 39,8 / 43,3 / 32,9° · odora solo GFS 39,9 / 45,3 / 33,3 ·
  **odora + MOS de las otras 7 40,1 / 41,5 / 31,7°** · MOS de la propia estación 32,9 / 27,6 /
  22,2°. Velocidad (RMSE) sí mejora: 2,32 → 1,54 / 2,15 → 1,73 / 3,50 → 1,42 m/s (sobre todo el
  sesgo). Rosa: no mejora (C9 28 → 32 %). ⚠️ **La mejora de dirección del MOS es LOCAL: no se
  transmite a 7-13 km a través de odora.** En la planta (sin estación) la dirección prevista
  sería de calidad GFS. Opciones: estación de ENCE en la planta (MOS local), mejor campo de fondo
  (ICON-EU/AROME: 27-30° en las estaciones sin corregir) o ajustar R1/RMAX/TERRAD.
  ⚠️ Necesita Python ≥ 3.12 (icechunk 2): entorno aislado `%TEMP%\ence_galera\venv312` creado con
  `uv` (Python 3.12 portátil en `%TEMP%\ence_galera\python`; NO toca `C:\e2s`). Si Windows limpia
  %TEMP%, se recrea con las órdenes del docstring del script.

### Revisión galera ↔ odora, módulo a módulo (pedida por el usuario, 2026-10-23)
- Objetivo: por cada pieza de `lib/galera`, ¿obsoleta?, ¿tiene equivalente en odora?, si no,
  ¿tiene sentido llevarla a odora para otras plantas? odora tiene los 8 motores y los LECTORES de
  sus ficheros; NO tiene descargas, escritores de entradas, almacén ni visualización.
  Mapa: (A) duplicado en odora: GEO.DAT, lector de CALMET.DAT, lector del listado de calpuff.exe ·
  (B) candidatos a odora: `calmet_pack` (.cmz), escritores de 3D/CLOUD/SURF.DAT (y CMET.INP y
  CALPUFF.INP, ⚠️ parten de la plantilla del sistema CALPUFF: mirar su licencia o escribirlos desde
  cero), `geo.py` (odora prevé `comun/`), parte general de `validacion`, `receptores.malla`,
  `nucleos` (aparcado) · (C) se quedan: config, registro, gui, procesos, descargas (IGN, CORINE,
  Catastro, Meteocat, ERA5, Open-Meteo) · (D) obsoleto: `estudios/arome.py`; sin uso
  `meteo.mes_pfl`, `terreno.caso_para`, `calmet.reconstruir`, `validacion.comparar_calmet[_anual]`;
  solo estudios `calmet.mes_completo`, `meses_disponibles`, `openmeteo.descargar_puntos`,
  `puntos_ence`, `calpuff.ejecutar_paralelo` (por nombre: confirmar al llegar a cada uno).
- **Punto 1, GEO.DAT → HECHO (decisión del usuario: opción «a»).** `calmet.rejilla` da solo la
  geometría (y las rejillas finas) y `calmet.escribir_geo_dat` lo encarga a odora:
  `terreno.geofisica.corine.preparar` + `python -m odora geofisica geo.inp` en
  `<caso>/geofisica` (el motor lee sus ficheros en la carpeta actual y devuelve 1 si falla).
  Fuera la tabla propia `CLC_A_CALMET`/`PROPIEDADES_USO`. Las lagunas del delta (CLC 521/522)
  pasan de 54 «bahía» a **55 «océano»**, como odora (aceptado por el usuario). El mar sin polígono
  de CORINE (código 0 a cota 0; 13 % de las celdas finas) entra como 523. Medido: GEO.DAT nuevo =
  odora puro en todos los campos; frente al antiguo, propiedades ±0,01 (redondeo) y categoría
  igual en el 98,9 % (45 celdas de lagunas + empates de usos mezclados). Cadena completa del
  2026-10-21 (GFS + 8 estaciones, odora viento3d): viento a 10 m |Δ| medio 0,0003 m/s, 0,03-0,04 %
  de celdas·hora con |Δ| > 0,1 m/s, velocidad media igual (3,067 m/s), dirección 0,01°. Los meses
  ya calculados con el GEO.DAT antiguo no hace falta repetirlos.
- `lib/galera/__init__.py` pone `lib/paquetes` (cargador del odora FIJO) delante en `sys.path`:
  con solo `lib/` (los scripts de procesos), `import odora` encontraba la carpeta del clon o el
  editable de inundaciones.
- **Punto 2, lector de CALMET.DAT → decisión del usuario: opción «a»** (llevar a odora la lectura
  selectiva por campos y niveles, unificando su lector repetido en viento3d y puffs, PENDIENTES
  §2.7), en UN solo cambio de odora junto con `calmet_pack` («almacén y lectura selectiva del
  viento») cuando se llegue a él; mientras tanto galera sigue con `calmet.leer`. Medido con 48 h: `calmet.leer`
  (U, V del nivel 1 + TEMPK, QSW, RMM) da los MISMOS valores que
  `odora.meteo.viento3d.fichero_viento.leer`, en 0,5 frente a 0,9 s y con 30 frente a 355 MB
  (un mes: 0,47 frente a ~5,5 GB): el de odora lo carga todo y no se puede usar tal cual para meses.
- **Punto 3, `dispersion/calpuff.py` → HECHO (2026-10-23): renombrado a `dispersion/puffs.py`**
  (regla 11). `escribir_inp` → `escribir_control` (cuerpo idéntico, comprobado con diff; ficheros
  del caso `puffs.inp`, `conc.dat`, `puffs.lst`); NUEVA `puffs.ejecutar(caso)` = `python -m odora
  puffs` + lector de odora (`fichero_conc.leer`) → {segundos, fin, conc (periodos × receptores,
  g/m³)}; `penacho_dia.py` la usa (antes, código en una cadena) y su viento se llama
  `viento3d.dat` (`calmet.leer(…, fichero=)`). Apartado «SOLO validación secundaria»:
  `ejecutar_exe`, `leer_listado_exe`, `ejecutar_paralelo_exe` (+ `nucleos`): sin uso hoy; el
  reparto por receptores se adaptará a odora en la dispersión de 5 años (idéntico bit a bit
  porque los receptores son independientes; medir entonces). Comprobado: penacho del 2026-10-21
  (24 h × 38 809 receptores) IDÉNTICO bit a bit al anterior.
- **Punto 4, obsoleto → HECHO (2026-10-23, regla acordada: en la biblioteca solo lo que usa la
  herramienta; lo que solo usan los estudios, a `estudios/`; lo que no usa nadie, se borra salvo
  que reproduzca resultados citados aquí).** Borradas: `meteo.mes_pfl`, `terreno.caso_para`,
  `calmet.reconstruir`. Movidas, con el código tal cual (líneas del AST): `calmet.mes_completo`
  y `meses_disponibles` → `estudios/cadena_era5_exe.py` (la usa `calmet_reanalisis.py`);
  `validacion.comparar_calmet`, `comparar_calmet_anual`, `calmet_puntos`, `_dd` →
  `estudios/validacion_2021.py`; `openmeteo.descargar_puntos`, `puntos_ence` y `VARIABLES` →
  `estudios/puntos_modelos.py` (la usa `descargar_modelos.py`). Las auxiliares que también usa
  lo que se queda, se quedan (se importan). Comprobado: 0 fallos (compila, importa, nombres) y
  la app igual. Los estudios conservan sus nombres históricos (no son parte de la herramienta).
- **Punto 5, `viento/calmet.py` y vecinos → HECHO (2026-10-23, regla 11; nombres aprobados por el
  usuario).** Script con el AST (posiciones exactas de cada nombre; se para si algo queda sin
  destino o sin traducir) + comprobación propia de nombres sin definir con `symtable` (no hay
  pyflakes): cazó dos fallos del propio script antes de escribir (`Path` sin importar y `RD, G`
  perdidas por ser una asignación múltiple).
  | Antes | Ahora |
  |---|---|
  | `calmet.py` (escritores y lectura) | `viento/ficheros.py`: `escribir_pronostico3d` (era `escribir_3d_dat`), `escribir_nubes` (`_cloud_dat`), `obs_horarias`, `escribir_estaciones` (`_surf_dat`), `escribir_control` (`escribir_cmet_inp`), `leer`, `en_punto`, `viento_en_punto`, `PLANTILLAS` |
  | `calmet.py` (casos y series) | `viento/casos.py`: `rejilla`, `escribir_geo` (`escribir_geo_dat`), `preparar_mes`, `ejecutar` (era `ejecutar_odora`), `ejecutar_exe` (era `ejecutar`, el .exe; `casos.EXE`), `entorno_privado`, `exe_tercero`, `recortar_arranque`, `recorte_de`, `extraer_puntos`, `conservar`, `_esperar_disco`, `dir_serie`, `mes_serie` (motor «odora» o «exe») |
  | `calmet.resultados_dir`, `ruta_cmz`, `_calmet_terminado` (solo estudios) | `estudios/cadena_era5_exe.py` (`_caso_terminado`) |
  | `calmet_modelo.py` | `viento/columnas.py` (`escribir_pronostico3d`, `escribir_nubes`, `rejilla_puntos`); `preparar_caso` y `pseudoestaciones` (solo estudios) → `estudios/cadena_icon.py` |
  | `calmet_pack.py` | `viento/almacen.py` (mismas funciones) |
  | `config.CALMET_CELDA_M / _MAX_CELDAS / _ZFACE`, `DIR_CALMET` | `config.VIENTO3D_*`, `DIR_VIENTO3D` (DATOS/viento3d) y `DIR_VIENTO3D_ESTUDIOS` |
  | ficheros del caso CMET.INP, CALMET.DAT, CMET.LST, GEO.DAT, 3D.DAT, SURF.DAT, CLOUD.DAT | `viento3d.inp`, `viento3d.dat`, `viento3d.lst`, `geo.dat`, `pronostico3d.dat`, `estaciones.dat`, `nubes.dat` (y `puffs.inp`); plantillas `planta/plantillas/viento3d.inp` y `puffs.inp` |
  | carpetas en Z: `calmet/` y `viento3d/calmet_era5_8est/` | `viento3d_estudios/` y `viento3d/exe_era5_8est/` (renombradas) |
  | `trabajo/calmet/AAAAMM`, clave de rosa `"calmet"`, textos «CALMET OK/falló/caso preparado», ayuda «AERMOD interpreta…» del panel | `trabajo/viento3d/`, `"modelo"`, «viento3d …» / «ejecutable de referencia …», «El penacho (odora) interpreta…» |
  Choques de nombres cazados por la prueba: función `columnas` en `procesos/mos_fuera_una.py`
  (el módulo se importa como `viento_columnas`) y variable local `casos` en
  `procesos/metodo_estaciones.py` (→ `configuraciones`). **Comprobado:** compila, importa, nombres
  importados y sin definir: 0 fallos; día 2026-10-21 (GFS + 8 estaciones) y julio 2024 (ERA5 + 8
  estaciones): las 4 entradas IDÉNTICAS byte a byte, el control solo cambia en las 6 líneas de
  nombres de fichero y el viento de odora IDÉNTICO campo a campo (48 h, u, v, w, T 3D y 2D; los
  bytes solo difieren en esas 6 líneas que la cabecera copia del control); penacho idéntico bit a
  bit; `--help` de los 8 procesos; app sin pantalla igual; desde Z:, 18 meses de la serie y las
  rosas de las 8 estaciones. ⚠️ Queda con nombres de terceros: el TEXTO de las plantillas (sus
  comentarios, que la cabecera del viento copia) → punto de los escritores; los nombres de los
  estudios cerrados (históricos) y `DATOS/pruebas/odora` (informes).
- **Reorganización por USO (2026-10-23, regla del usuario: «si conecta la GUI con odora, a gui/; si
  es útil y odora no lo tiene, a odora; si no, se borra»).** Medido con el grafo de imports desde
  `main.py`: la app usaba 22 de 59 ficheros y NO lanza odora (⚠️ RECTIFICACIÓN, 2026-11-01: ya sí, `periodos.preparar` y `penacho_3d.calcular`; solo enseña resultados: viento de
  los .cmz, penacho de sus PNG). Decisiones: descargas (IGN, CORINE, Catastro, Meteocat, ERA5, GFS,
  Open-Meteo) → **odora.fuentes**; procesos que se repiten → **gui/tareas/**; estudios,
  metodología cerrada y funciones `*_exe` → **borrar con zip de archivo**.
  **Fase 1 → HECHA:** zip verificado de TODO lib/galera previo (77 ficheros, 0,26 MB) en
  `%LOCALAPPDATA%\CIRCE\archivo\` (Z: se desconectó; ⚠️ copiarlo a Z:\…\archivo\ cuando vuelva);
  borrados `estudios/` (17), `referencia_mes`, `metodo_estaciones`, `mos_fuera_una` (sus
  `columnas`/`niveles`/`dia1`/`N_COL` → `gui/tareas/gfs_columnas.py`, salida idéntica: `equals` =
  True), `nucleos.py`, `casos.ejecutar_exe`/`exe_tercero`, `puffs.*_exe`, `config.DIR_TERCEROS` y
  `VIENTO3D_MAX_CELDAS` (tope del .exe), motor «exe» de `viento3d_series`; `config`, `registro` y
  `planta/` → `gui/`; 10 procesos → `gui/tareas/`; la app ya no importa `viento/casos`
  (`viento_mapa._dir_serie` = `config.DIR_VIENTO3D / serie`). Comprobado: compila, importa,
  nombres importados y sin definir 0 fallos (con `main.py`, que se había quedado fuera y el
  verificador cazó); penacho idéntico bit a bit; app sin pantalla con `--dia` igual.
  Sin uso tras borrar los estudios: `openmeteo` entero (solo lo usaba la cadena de ICON) y
  `validacion.figura_rosas_clases` → se deciden en la fase 2.
  **Fase 2 (pendiente):** versión nueva de odora con `fuentes` (ign, corine, catastro, meteocat,
  era5, gfs, openmeteo), preparación de casos de viento3d y puffs (escritores; ⚠️ las plantillas
  son del sistema de referencia: escribir el control desde cero), `almacen` + lectura selectiva,
  `comun/geo`, métricas de validación y malla de receptores, con pruebas y auditor APTO; después
  galera importa de odora y `entradas/`, `viento/`, `dispersion/`, `geo.py` desaparecen.
  Se desarrolla en la copia `%LOCALAPPDATA%\CIRCE\odora_dev` (rama **`v0.2.0-utilidades`**, desde
  `main` = v0.1.1, ya publicada como v0.1.2; para 2c/2d, rama nueva desde `main`; fuera de OneDrive) con el cargador `%LOCALAPPDATA%\CIRCE\odora_dev_paquetes`
  para pasar sus pruebas sin instalar nada (en C:\e2s está el editable del laboratorio: NO tocar).
  Batería de partida: 158/158. Cada paso: commit en la rama (SOLO local; subir solo si lo pide el
  usuario, con el auditor APTO), `lib/odora` fijado a ese commit (`git fetch <odora_dev>
  v0.2.0-utilidades` + `checkout --detach`) y galera pasa a usarlo, comprobando que todo da igual.
  **Paso 2a → HECHO** (commit `d069bc3`, auditor APTO R1-R6, 172 pruebas): `odora.comun.geo`
  (UTM, EPSG del huso, convergencia…; galera/geo.py queda como envoltorio que fija
  config.EPSG_UTM), `odora.meteo.viento3d.almacen` (el .cmz, código idéntico al de galera; borrado
  de galera) y `fichero_viento.leer_campos` (lectura selectiva; `ficheros.leer` lo envuelve).
  Comprobado frente a una línea base: viento del mapa, lectura selectiva (fechas, campos, tipos)
  y geo IDÉNTICOS; penacho idéntico bit a bit; app igual. Siguen: 2b preparación de casos, 2c
  fuentes, 2d métricas; al final, versión 0.2.0 (⚠️ al final se publicó la v0.1.2 con 2a y 2b: ver abajo).
  **Paso 2b-1 → HECHO** (commits `f695c58`, `7a8fbca`, `3cafeaf`; auditor APTO, 192 pruebas):
  `odora.preparacion` (extra `odora[preparacion]` = pandas). `preparacion.control.Control` guarda
  las asignaciones EN ORDEN y escribe el control SOLO con `! NOMBRE = valor !` y `!END!` (los
  lectores de odora ignoran el resto: fuera el texto de la plantilla de referencia, regla 11).
  `preparacion.viento3d`: `parametros.py` (186 asignaciones de partida, generadas desde la antigua
  plantilla: sin estaciones ni ficheros de ejemplo, nombres propios), `control.preparar/escribir`,
  `geofisica.malla/escribir` (el motor en un proceso aparte: el `chdir` no vale con hilos),
  `pronostico.escribir_columna/rejilla_puntos/escribir_columnas`, `nubes.escribir/escribir_zonas`,
  `estaciones.medias_horarias/escribir`, `salida.fecha_registro/recorte/recortar_arranque/
  en_punto/viento_en_punto`. En galera, lo propio de la planta (preparar_mes con ERA5 y Meteocat,
  ejecutar, extraer_puntos, disco, mes_serie, obs_horarias con el control de calidad de F1, leer)
  → **`gui/tareas/viento3d_casos.py`**; `viento_dia_local.preparar_caso` sale aparte (se puede
  probar sin descargas); borrados `viento/{casos, ficheros, columnas}.py` y
  `plantillas/viento3d.inp` (zip `%LOCALAPPDATA%\CIRCE\archivo\galera_codigo_2026-10-23_paso2b1.zip`,
  ⚠️ copiar a Z:); `entorno_privado` (TMP propio, solo era para los .exe de Lahey) fuera.
  Cabeceras de los ficheros con títulos propios (sin «3D.DAT», «SURF.DAT»…; deben ser ASCII y de
  ≤ 64 caracteres en el pronóstico). Comprobado, día 2026-10-21 viejo frente a nuevo con los mismos
  datos: geo, pronóstico, nubes y estaciones iguales salvo la línea de título; control con la MISMA
  secuencia de fichas (206; 42,9 → 4,5 kB; el generador tuvo que llevarse los `END` de los
  sondeos quitados y activar el de M3DDAT); fichero de viento de odora: los 2 841 registros de
  datos IDÉNTICOS (solo cambia el control que la cabecera repite: 1 049 → 209 líneas).
  Antes, `cmp_preparacion`: malla, columnas, nubes, medias horarias de las 8 estaciones, recorte y
  viento en un punto idénticos byte a byte. Sin probar aún con Z: (series de ERA5 de un mes).
  **Paso 2b-2 → HECHO** (commit `e331c45`, auditor APTO, 201 pruebas; los números «n/4» de los
  commits son solo el orden): `odora.preparacion.puffs` (`parametros.py` generado de la antigua
  plantilla sin la fuente puntual ni las 6 especies de ejemplo, con marcas `_ESPECIE`,
  `_AREAS_X`, `_AREAS_VERTICES`, `_RECEPTORES`; `control.fuente_area/preparar/escribir`;
  `salida.concentraciones` → fechas de FIN y matriz; acepta la especie por nombre: en el fichero
  la clave es el nombre a 12 caracteres + el nivel) y `odora.preparacion.receptores.
  malla_anidada/resumen`. Salidas de deposición y visibilidad con nombres propios
  (`deposicion_seca.dat`, `deposicion_humeda.dat`, `visibilidad.dat`; antes «CPUF.*»; odora solo
  las escribe con deposición). En galera: `gui/tareas/puffs_casos.py` (antes
  `dispersion/puffs.py`) y `gui/receptores_mapa.py` (antes `dispersion/receptores.py`: niveles,
  estilos y discretos de la planta); borrados `dispersion/`, `plantillas/puffs.inp` y
  `config.PLANTILLAS` (zip `…\archivo\galera_codigo_2026-10-23_paso2b2.zip`, ⚠️ copiar a Z:).
  Comprobado: control con la MISMA secuencia de fichas salvo esos 3 nombres (241 y 1 049 fichas;
  73 → 5 kB) y la MISMA configuración leída por el motor (variables, fuentes, receptores,
  especie); malla de receptores idéntica (7 945 / 8 011 con núcleos / 8 103 con viviendas
  sintéticas); prueba de odora con el motor sobre el viento de `puffs/area_D` (1,2 s).
  ⚠️ El periodo k de puffs lleva la fecha del registro k del viento (hora FINAL): con un viento que
  empieza a las 00, el primer periodo es el de las 00 (la prueba lo esperaba a la 01).
  **Publicado como odora v0.1.2** (2026-10-23, a petición del usuario: «subir a la main
  v.0.1.2»; el número lo eligió él, no 0.2.0): los 5 commits de trabajo y el de versión,
  juntados en uno (`fbf2a3f` en `main`, mismo árbol comprobado; etiqueta anotada `v0.1.2`; los
  originales en la rama local `historia/v0.1.2-pasos` de odora_dev, que vuelve a `main`).
  Auditor APTO R1-R6 (201 pruebas) antes de subir; `main` en GitHub seguía en la v0.1.1 (sin
  mezclas). `lib/odora` fijado a la etiqueta v0.1.2 bajada de GitHub. Quedan para otra versión
  2c fuentes y 2d métricas (PENDIENTES §3 de odora). La integración continua de GitHub corre el
  auditor en cada subida a `main`; sin `gh` no se ve desde aquí (mirarlo en la web).

### Motores propios: `odora` (2026-10-18, decisión del usuario: dejar los .exe de terceros)
- Repositorio PRIVADO del usuario `https://github.com/mcamasanz/odora` (acceso por el gestor de
  credenciales de git; `gh` no está instalado). Sustituye a AERMAP (`terreno.relieve`),
  AERSURFACE (`superficie`), BPIPPRM (`edificios`), MAKEGEO (`geofisica`), AERMET
  (`meteo.capa_limite`), CALMET (`meteo.viento3d`), AERMOD (`dispersion.penacho`) y CALPUFF
  (`dispersion.puffs`). Licencia propietaria: las partes EPA son traducciones de código de
  dominio público; CALMET/CALPUFF/MAKEGEO son de «sala limpia» (desde la documentación): esto
  resuelve el bloqueo del EULA de Lakes. Pendientes del propio odora en su `PENDIENTES.md`.
- **Versión FIJA** (su README lo pide): clon de la etiqueta **v0.1.2** (2026-10-23; antes v0.1.1 y
  v0.1.0) DENTRO del
  proyecto, en **`ENCE/lib/odora`** (decisión del usuario, 2026-10-20; 15 MB, con su `.git`).
  Se carga con el cargador `ENCE/lib/paquetes/odora/__init__.py` (no un junction: OneDrive no los
  sincroniza bien), que apunta `odora` a `lib/odora/core` y manda la caché de numba (~170 MB) a
  `%TEMP%\ence_odora_numba` (regla 4). Uso: `PYTHONPATH=ENCE/lib/paquetes` (va antes que el
  buscador editable, que está detrás de PathFinder en `sys.meta_path`). La copia antigua de
  `DATOS/lib` se borró. ⚠️ En `C:\e2s` hay un odora instalado en modo editable que apunta a la
  COPIA DE TRABAJO del laboratorio (`Escritorio\Mountains\inundaciones\odora`), que cambia con la
  otra sesión: NO usarla ni reinstalar encima.
- **odora frente a los .exe en NUESTRAS configuraciones** (2026-10-20, 48 h; informe y casos
  reproducibles en `DATOS/pruebas/odora/`): `dispersion.puffs` con el mismo CALMET.DAT =
  **idéntico** a calpuff.exe (P98 Δ 0 %, r = 1,0000). `meteo.viento3d` 2,4× más rápido pero NO
  idéntico: difiere en las TRANSICIONES de estabilidad (06-07 y 19 UTC: IPGT, u*, viento a 10 m
  en miles de celdas) y en la ZI convectiva durante el día; QSW idéntica. Efecto en la cadena
  completa: ERA5 sola (T1) P98 por receptor |Δ| 16 % (máx 66 %); ICON + pseudoestaciones (T2)
  0,9 % (máx 15 %). Contradice el «nunca da un resultado distinto sin avisar» de odora: avisado
  al usuario (regla del plan: no tocar odora; los arreglos van por su repositorio).
- **Causa encontrada y corregida** (2026-10-20, con permiso del usuario para modificar odora):
  NO era Turner (cada motor reproduce su IPGT con su propio viento) sino el **bloqueo (Froude)**:
  con IFRADJ = 0 las diferencias desaparecen. Tres reglas de calmet.exe medidas como caja negra:
  (1) N del bloqueo con la temperatura de la hora sin ajustar y T(ZUPT) adiabática solo donde la
  convectiva GUARDADA de la hora anterior llega a ZUPT (barrido de N a las 07 UTC: el .exe usa
  0,0061, odora daba 0,0034); (2) ψ de la convectiva (solo ITPROG = 2): por debajo del primer
  nivel del pronóstico (975 hPa de ERA5, ~100 m) θ de la temperatura 3D anterior y no constante
  (la 1.ª hora convectiva salía un 25-50 % más alta); (3) temperatura 3D de salida ajustada con la
  convectiva promediada. Resultado: T1 celdas·hora con |Δv| > 0,1 m/s 6 800 → 89, P98 16,3 % →
  **0,2 % (máx 2 %)**; T2 942 → 227, P98 0,9 % → **0,1 % (máx 3 %)**; 158/158 pruebas de odora.
  **Publicado como odora v0.1.1** (2026-10-20, a petición del usuario: commit 8869a49 en `main`
  y etiqueta anotada `v0.1.1`; auditor APTO R1-R6 antes de subir; el hook pre-push no corre aquí
  porque `python` del PATH es el acceso directo de la Store). Motivo y cambio en su CHANGELOG,
  `docs/validacion.md`, `PENDIENTES.md` y `core/meteo/viento3d/README.md` §Transiciones; y en
  `DATOS/pruebas/odora/INFORME_DIFERENCIAS_viento3d.md`. Sigue abierto (ya en v0.1.0): la ZI de
  la tarde (T1 0,6 %) y la ZI/temperatura de día con ITPROG = 1 (T2 2,3 %).
- ⚠️ **2026-10-20, decisión del usuario: se BORRÓ `%TEMP%\traduccion`** (31 GB: el banco de
  pruebas de la traducción de odora de la otra sesión, con las baterías de validación de los 8
  motores) y las carpetas temporales de otras sesiones de Claude. Repasar la batería de 51 casos
  de viento3d con la v0.1.1 (pendiente de odora) exige regenerarla desde el laboratorio. Quedó un
  `aermap.exe` zombi (PID 18440, del 16-oct) que no se deja cerrar y retiene ~100 MB hasta
  reiniciar el PC. Disco: de 6,5 a 39,9 GB libres.
- ⚠️ Para pasar sus pruebas con la copia fija (desde `ENCE/lib/odora`):
  `PYTHONPATH=../paquetes python -m pytest auditor/pruebas` (158/158 el 2026-10-20 tras traerla;
  el `python -m auditor` sin ese PYTHONPATH coge el editable de inundaciones y sale «0 pruebas»). Uso: `python -m odora viento3d CMET.INP` (en la carpeta del caso) y
  `odora.dispersion.puffs.principal.ejecutar(ruta_inp)` → (cabecera, periodos) en g/m³.

### Alcance 1: escenarios de operación (requisitos del usuario, 2026-10-24; foco de trabajo)
- Con los 5 años de viento 3D simulado: emisión CONSTANTE o PERFIL HORARIO de 24 h, dispersión
  repartida en paralelo, y como resultado el penacho hora a hora del día que se elija y, en cada
  receptor, la media y el máximo anuales y el P98 de los 5 años (regla 2). Sirve para evaluar
  escenarios: subir o bajar la emisión, pasar una operación de la mañana a la tarde o al revés…
- **El alcance 1 va SIEMPRE**: su viento 3D de 5 años es la base que ayuda y valida el resto de
  alcances.
- **Media, máximo y P98 se calculan SIEMPRE juntos** en cada escenario (decisión del usuario,
  2026-10-25): no son opciones; el operario solo elige cuál ver en el mapa.
- **Focos (decisión del usuario, 2026-10-25):** los define CIRCE tras la PRIMERA VISITA, una
  pestaña por unidad emisora en una 2.ª ventana; al pasar de pestaña, el mapa marca con un
  recuadro dónde está; los campos dependen del tipo. Lista APROBADA de tipos posibles (modelo):
  pila o hilera de compostaje (superficie) · túnel o trinchera (superficie o punto) · biofiltro
  (superficie) · lavador químico (punto) · soplador o extractor (punto) · venteo de digestores,
  gasómetro o tanques (punto, por eventos) · salida del upgrading (punto) · antorcha (punto) ·
  motor de cogeneración o caldera (punto) · recepción y descarga (superficie o volumen) ·
  pretratamiento y triturado (volumen) · digestato: balsa, tanque o separador (superficie o
  volumen) · balsa de lixiviados (superficie) · fugitivas de nave (superficie o volumen) ·
  cribado y almacén de compost (superficie o volumen). Campos comunes: identificación,
  ubicación, funcionamiento (continuo, horario, eventos), olor (medido u estimado por el gas
  dominante), gases opcionales, observaciones; punto: altura, diámetro, caudal o velocidad,
  temperatura, edificio cercano y su altura real; superficie: polígono, altura, emisión por m²;
  volumen: centro, dimensiones, altura. Ubicación, altura, diámetro, velocidad y temperatura solo
  los cambia CIRCE (recalcula ese foco); emisiones, composición y perfil, el operario.
  **Maqueta de la ventana de focos APROBADA por el usuario (2026-10-25: «es justo como lo
  quiero»)**: artboard «Ventana de focos» del lienzo https://claude.ai/artifact/H6gHGUo3RQghdcdNQkKs9C
  — pestañas verticales por foco (nombre, tipo, punto/superficie/volumen) + «Añadir foco» con
  los 15 tipos; plano en el centro con el foco elegido recuadrado y rotulado; ficha a la derecha
  según el modelo, con la etiqueta «recalcula» en los campos que obligan a recalcular el foco.
- **Qué puede hacer el operario (decisión del usuario, 2026-10-25):** CREAR, GUARDAR y CARGAR
  escenarios de operación (factor por foco y perfil de 24 h; ⚠️ RECTIFICACIÓN del 2026-11-01, decisión del usuario: ya sin
  factor, ver «Planes de operación por días»; «Nuevo», «Duplicar», «Guardar», lista
  de guardados), pero **JAMÁS crear focos**: un foco nuevo o modificado es una actualización de
  CIRCE con coste (oferta: «cambios en la planta»). En su app la ventana de focos es solo de
  consulta («Ver focos…»); «Añadir foco» y los campos «recalcula» son del modo CIRCE. Maqueta del
  editor de escenarios: artboard «Escenario de operación» del mismo lienzo.
- **Formato de focos y escenarios → HECHO (2026-10-26; el usuario: «el formato más limpio y rápido
  de leer y escribir»): JSON** (biblioteca estándar, legible, se compara con un diff; listas de
  números y fichas cortas en una línea; escritura con temporal + `os.replace`). Focos en
  `gui/planta/focos.json` (`gui/focos.py`: `cargar/guardar/nuevo`, `TIPOS` (los 15 aprobados),
  UTM 25831, cada magnitud con su unidad en el nombre). La emisión se guarda COMO SE MIDE (valor +
  unidad: ou_E/m³ con caudal, ou_E/(s·m²), ou_E/s; estimada por el gas dominante en ppm, mg/m³,
  mg/(s·m²) o g/s con los umbrales de Nagata 2003) y se pasa a lo del modelo en UN sitio
  (`olor_ouE_s`, `gases_g_s`, `por_m2`: regla 1). El perfil de 24 h (hora oficial) sale de
  «funcionamiento» (`perfil`: continuo, horario «8-16» / «8, 16» con % fuera de horas, eventos con
  frecuencia y duración). `huella(foco)` resume lo «recalcula» (tipo, modelo, ubicación, altura,
  salida, edificio, dimensiones). `pendientes(foco)`: lo que falta para calcular. Escenarios: un
  JSON por escenario en `DATOS/escenarios/` (`gui/escenarios.py`: {focos: {id: {factor, perfil}}};
  un foco que no figura emite como en su ficha; la «Base» no es fichero).
- **Ventana de focos en la app → HECHA (2026-10-26)**: `gui/ventana_focos.py` (pestañas, ficha
  según el modelo con «recalcula», perfil del día, olor resultante, pendientes) + `gui/focos_mapa.py`
  (ortofoto PNOA, focos coloreados por modelo, el elegido recuadrado y rotulado; en modo CIRCE se
  dibuja ahí la ubicación: vértices a clic, doble clic/Intro termina, Esc cancela). Se abre con
  «Planta → Focos de emisión…» (Ctrl+Mayús+F) o «Ver focos…» del bloque «Focos de emisión» del
  panel (sustituye a «Fuentes de emisión · pendiente»). **Modo operario por defecto (solo consulta:
  0 campos editables, comprobado); `main.py --circe` = modo CIRCE** (añadir/quitar, dibujar,
  Guardar; avisa de los focos que hay que recalcular). `main.py --focos` abre la ventana al
  arrancar. Los 13 focos de `focos.json` son de EJEMPLO (`"ejemplo": true`, aviso amarillo en la
  ventana y «de ejemplo» en el panel): posiciones leídas a ojo en la ortofoto (nave, digestores,
  tanque abierto, balsas) y valores inventados; ⚠️ sustituirlos por los de la visita y no calcular
  con ellos. ⚠️ RECTIFICACIÓN (2026-10-31, decisión del usuario): la app ya no lo dice; solo queda la marca en el fichero. Comprobado sin pantalla: 13 fichas, recuadro en cada una, los 15 tipos × modelos se
  añaden, ubicar, editar (altura → «recalcular»), horario → perfil, guardar y releer idéntico.
- **Planes de operación por días → HECHOS (2026-10-31, pedido del usuario: «planes diarios, semanales e
  incluso mensuales de cada foco»).** Cada foco lleva su plan: un perfil de 24 h por día, 1 (diario), 7
  (semanal, L-D) o 31 (mensual, por día del mes). ⚠️ RECTIFICACIÓN: `gui/escenarios.py` pasa al formato 2,
  {mes, focos: {id: {factor, plan, perfiles, dias}}} (⚠️ RECTIFICACIÓN del 2026-11-01, decisión del usuario, «lo del factor no lo veo
  útil»: ya sin `factor`, ni en la ventana, ni en el fichero, ni en el cálculo, para que nada multiplique a escondidas. Consecuencia:
  un plan no pasa del 100 % de la emisión de la ficha; subirla es cambiar la ficha, que es de CIRCE), en vez de {factor, perfil}, sin lectura del 1 (no se
  había guardado ninguno). **No hace falta más motor (`99-Test/05_planes`):** R_h(t, r) se pesa con la emisión
  de la ÚLTIMA vez que fue la hora h (`te`, sale de t y h, ya guardados) si un puff no dura más de 24 h: frente
  al motor, diferencia ≤ 8·10⁻⁸ del máximo, y a las 4 h de apagar no queda nada. ⚠️ Una sola situación, con
  viento: repetir con la peor calma de la serie cuando vuelva Z:. Hora oficial con cambio de hora
  (`escenarios.factores`; el cálculo va en UTC). ⚠️ El factor h del motor va en el periodo cuyo FIN tiene hora
  h + 1, y el 1.er periodo emite la hora anterior a su inicio. Semanal: se repite en los 5 años por día de la
  semana. Mensual: se evalúa con ese mes en los 5 años (`horas_del_plan`); propuesta mía, sin confirmar.
  Ventana `gui/ventana_planes.py` («Planta → Planes de operación…», Ctrl+Mayús+P, botón en «Focos de emisión» o
  `main.py --planes`), como la de focos: focos a la izquierda, PLANO en el centro (`VistaFocos`, el usuario: «se
  pierde el mapa»; elegir en la lista recuadra y pinchar en el plano elige) y a la derecha los días (Ctrl o Mayús
  + clic elige varios) y el perfil a golpe de ratón (desde el 2026-11-01, pedido del usuario, la barra bajo el ratón enseña su hora y su valor, también al arrastrar); Nuevo / Duplicar / Guardar. Comprobado con clics simulados
  (QTest): editar, guardar y releer idéntico (3,9 kB).
- **Tabla de la simulación (pedido del usuario, 2026-11-01):** sale ordenada por la media; al pulsar una columna de valores, de más a menos, y otra vez, al revés. Se ordena por el
  valor (`panel.CeldaValor`), no por el texto. Al cambiar de gas se mantiene la columna elegida; una simulación nueva vuelve a la media.
- **Visor 3D en la app (pedido del usuario, 2026-11-01).** ⚠️ RECTIFICACIÓN (decisión del usuario, ese mismo día): ya no es un botón bajo Simular con ventana aparte, sino una página del riel, «3D», debajo de Simular: lista de penachos de las 3 modalidades, «Abrir» o «Calcular»; al abrir, la zona central pasa del mapa a `gui/vista_3d.py`, con el MISMO reproductor y el mismo fundido entre horas, y al salir de la página vuelve el mapa. Cada día se calcula aparte, con el perfil del plan ese día: 3 días ≈ 30 min y 5 días ≈ 50 (estimado). Antes: Botón «Ver en 3D» bajo los resultados de Simular → `gui/ventana_3d.py`, con WebGL (three.js r147, MIT, y ortofoto PNOA de ±3,2 km, en
  `gui/recursos/visor3d/`). `gui/penacho_3d.py`: viene de `99-Test/07_isosuperficies`. ⚠️ **Es lo único de la app que lanza el motor en el PC del operario:** las respuestas de los focos están en el suelo. Una
  corrida con la emisión del plan por plan y magnitud, medido: 13,7 min con 4 procesos y otro cálculo a la vez (~10 min sin él). Se guarda en `DATOS/resultados_planes/<plan>/<magnitud>/penacho_3d.json` (1,75 MB) y luego se abre en 2-3 s; `firma` lo invalida si cambian el
  plan, los focos o el viento. Mientras calcula, el botón pasa a «Cancelar 3D» y no se puede simular. Superficies a 1, 3 y 5 veces la referencia de la magnitud (olor: ou_E/m³), con sus colores fijos; abre en la hora del reproductor, sin sincronizarse después; sigue al estilo sin recargar.
  Si la 2.ª pasada (cada 25 m) difiere más del 2 % de la 1.ª en los nudos comunes, repite con más arranque. **Comprobado:** el suelo frente al penacho de la app, por otro camino, 7,6·10⁻⁶ sobre 64,7 ou_E/m³ (1,2·10⁻⁷), correlación 1,0; WebGL 2 en la Intel Iris Xe de este PC, 3,2 ms por dibujo.
  ⚠️ Con un plan que cambia de un día a otro, las primeras horas llevan lo emitido el día anterior como si fuera el del día que se ve: el motor repite un perfil de 24 h. ⚠️ Con la serie de 5 años el motor lee el mes entero (~5 GB por proceso, 20 GB con 4; el PC tiene 16 GB): hay que recortar el viento
  a esos dos días antes de usarlo con Z:. También en `respuestas_dia` y `penacho_dia`. ⚠️ Necesita pyvista (vtk) en el PC del operario. ⚠️ Fuera de ±3 km no hay nada calculado: «Alcance: 3,1 km o más» avisa de que la superficie llega al borde. ⚠️ Un nivel que el penacho no alcance no se dibuja (el CO de ejemplo no llega a su
  referencia). ⚠️ Ni el viento local ni los edificios afectan al penacho, tampoco aquí. Una superficie sólida disimula los ~30° de error de dirección: es para enseñar, no un resultado.
- **Panel «Simulación» → FUNCIONA EN PRUEBA (2026-10-31, el usuario: «por probar, vamos a suponer que los 5 años
  tienen el mismo viento»).** Orden decidido por el usuario: **Focos → Meteorología → Simulación**. La ventana de
  planes solo CONFIGURA, sin calcular ni resultados; se simula desde el último bloque del panel: plan guardado (o la
  Base), «Simular» (solo con una meteorología elegida) y tabla, botones «Ver media / máximo / P98» y capas en el mapa
  principal, excluyentes con el penacho del día. Al cambiar de meteorología se limpia; al volver a guardar el plan simulado, avisa
  de que ya no vale. Los núcleos y las naves de Dacame (ahora con icono) llevan los valores en su tooltip. ⚠️ Viento de UN día (21-oct-2026, `odora_gfs_8est`) repetido en 43 824 h y focos de EJEMPLO:
  prueba la herramienta, NO son resultados (el penacho va siempre hacia el SE: Dacame y Santa Bàrbara salen a 0). ⚠️ RECTIFICACIÓN (2026-10-31, decisión del usuario): la app ya no avisa de ello. `gui/tareas/respuestas_dia.py`: una corrida de odora puffs por foco con 24 especies, en la malla
  de 12 656 receptores → `DATOS/respuestas/<serie>_<AAAAMMDD>/` (`R_<foco>.npz` R[h, H, r] en (g/m³) por g/s, 13 focos
  en 7,1 min con 4 procesos y 3 MB; `receptores.npz`; `meta.json` con la huella de cada foco). `gui/tareas/
  control_fuentes.py`: control con varias especies y áreas, puntos y VOLÚMENES (σy0 = √(largo·ancho) / 4,3; σz0 = alto
  / 2,15); viene de `99-Test/01` y ⚠️ pasará a odora. `gui/planes_calculo.py`: `calcular` da media, máximo y P98
  (regla 2) en ou_E/m³ por bloques de 500 receptores (≈ 45-60 s para 43 800 h y 12 focos), con emisión = ou_E/s ×
  `F.fraccion_eventos` × plan. ⚠️ Un foco por eventos se reparte en todo el mes: da bien la media, no sus picos. Un foco
  sin emisión se queda fuera y se avisa (hoy, la antorcha). Con la serie real, R dejará de ser periódica y pasará al
  formato disperso de la prueba 02 (estimado, sin medir: 13 focos y esta malla ≈ 15-18 GB sin comprimir; revisar el
  disco del operario). Tabla: naves de Dacame, peor vivienda y núcleos. ⚠️ RECTIFICACIÓN (2026-10-31, decisión del usuario): Dacame ya no sale en la tabla (`"en_tabla": false` en `planta/receptores.json`); sigue calculándose y sale en el mapa con su tooltip. Un receptor con nombre nuevo (un sensor) sí saldrá, salvo que lleve esa marca. Capas `plan_media`, `plan_maximo` y `plan_p98`
  (`VistaMapa.set_imagenes`, 2 imágenes por capa: ±3 km a 10 m y el resto a 100 m, interpolando en logaritmos; escala FIJA 0,1-1000 ou_E/m³, para que los valores de dentro de la planta no cambien el
  mapa). Se guarda en `DATOS/resultados_planes/<plan>/`. Comprobado (`99-Test/05_planes/prueba_calcular.py`): media,
  máximo y P98 a mano, linealidad, suma de focos, «solo el lunes» = 1/7 y mensual constante = diario; y en la ventana
  principal, en pantalla, con el botón de verdad (clics simulados, sin ratón real).
- **Gases y olor estimado → HECHOS (2026-11-01, pedido del usuario; prueba `99-Test/08_gases`).** Cada cosa que se emite es una MAGNITUD
  (`focos.magnitudes`): el olor y cada gas, con las MISMAS respuestas de los focos y sin lanzar el motor. `planes_calculo.calcular` las saca todas en una pasada → `DATOS/resultados_planes/<plan>/<magnitud>/`.
  Selector en Simulación: cambia capas, penacho, tabla y tooltips sin recalcular. Medido: 89 s con 7 magnitudes y 13 focos, frente a ~27 s antes solo con olor; 2,2 MB.
  **De gas a olor con Nagata (decisión del usuario, 2026-11-01):** manda la olfatometría y, si no hay, `máx(gas / umbral)`, en el foco y no en el receptor (así se suman focos medidos y estimados). 15 compuestos de
  `docs/referencias/metodologia/olores_metodologia.md` §F.1; NOx y CO no cuentan. ⚠️ Esa guía (§F.3) dice que esto NO son ou_E de la mezcla: es un índice orientativo, no sustituye a la olfatometría y no sirve para
  justificar un criterio en ou_E/m³. El umbral del H₂S varía casi tres órdenes de magnitud (§F.2) y su análisis de sensibilidad está SIN HACER. El panel dice «Estimado por gases: foco (gas)». Falta calibrar con olfatometrías.
  ⚠️ RECTIFICACIÓN de `focos.py`: antes usaba 25 °C con el caudal real (×1,34 a 127 °C, ×2,26 a 400 °C; también el olor en ou_E/m³). Ahora, a la temperatura de salida; nuevos `mg/Nm3` y `salida.caudal_Nm3_h`; `focos.json` pasa
  al formato 2 (sin `olor.origen`; cada gas una vez, en `gases`). No distingue base seca de húmeda ni O₂ de referencia. Escala de color: 0,1-1000 × `ref` (olor 1 ou_E/m³; gas con límite, límite / 100; los demás, su umbral).
  Percentil: P98, salvo NOx P99,8 y SO₂ P99,7 (límite horario, RD 102/2011); el CO (8 h) sigue en P98 (⚠️ RECTIFICACIÓN del mismo día: por año civil y con `planta/normativa.json`, ver «Menús y resultados según la meteorología»). Sin química: NOx como NO₂ es un tope. ⚠️ Los gases de `focos.json` son inventados.
- ⚠️ **Modo oscuro de Windows (medido el 2026-10-31, este PC está en oscuro):** la paleta trae texto blanco y en
  la ventana de focos los nombres, campos y botones salían blanco sobre blanco. Arreglado con colores explícitos en
  `ventana_focos.ESTILO` (el de las dos ventanas). `offscreen` NO lo enseña: para capturas fieles, plataforma real
  con `WA_DontShowOnScreen` y `QT_ENABLE_HIGHDPI_SCALING=0` (el contenido web sale en blanco). La ventana
  principal no se ha tocado: sigue la paleta del sistema.
- **Menús y resultados según la meteorología → HECHO (requisitos del usuario, 2026-11-01; `99-Test/09_modalidades`):** Simular depende de la opción de Meteorología. Reanálisis: 5 años de gases y olores (olor: media, máximo, P98; gas:
  media, máximo y normativa) y, si se quiere, un día con su penacho, con ambos resultados en tablas. Episodio de queja: 1-3 días, con máximo, media, normativa y penacho de esos días. Predicción: igual que el episodio, 1-5 días (3 por defecto; la oferta promete 3-5). Debajo de Simular, un visor 3D donde cargar los penachos de las 3 modalidades, con animación como la del 2D.
  Las 3 son lo mismo: un periodo de viento más las respuestas de cada foco en ese periodo (`gui/periodos.py`: {modo, ini, dias, serie}). `planes_calculo.calcular`: 5 años, sin penacho. `planes_calculo.calcular_periodo`: un día, el episodio o la predicción, con penacho; `R_<foco>.npz` pasa a R[h, t, r], con t la hora del periodo. `periodos.preparar`: `viento_dia_local.py` (`--dias`, `--serie`, `--prediccion`) + `respuestas_dia.py` (`--dias`), en procesos aparte y cancelable; serie propia `queja_<AAAAMMDD>_<n>d` o `prediccion_…`. Resultados en
  `DATOS/resultados_planes/reanalisis/5_anios/<plan>/` o `<modo>/<AAAAMMDD>_<n>d/<plan>/`, con su `firma`: lo simulado se lee si no cambian plan, focos, periodo ni normativa (`planes_calculo.guardado`). Medido: preparar 3 días, 16,5 min (8,4 descargas, 1,5 viento, 6,6 respuestas); predicción de 2 días, 9 min; simular 3 días, 147 s (1 008 imágenes); 5 años de día repetido, 97 s.
  **Normativa PRELIMINAR (usuario, 2026-11-01: aún no se conocen los gases ni las emisiones):** `gui/planta/normativa.json`, sin tocar el código; `gui/normativa.py` da las columnas y sus estadísticos. ⚠️ RECTIFICACIÓN: antes era un percentil de los 5 años juntos (P99,8 y P99,7, `focos.LIMITES`), y la norma cuenta por año civil: ahora, el peor año (19.ª hora más alta de NO₂ frente a 200, 25.ª de SO₂ frente a 350, 4.º día de SO₂ frente a 125, media anual de NO₂ frente a 40, máxima de 8 h de CO). Medido: 30 horas por encima en un año pasaban por el percentil de dos años juntos. En 1-5 días no se puede contar por año: media, máximo, hora oficial del máximo, horas por encima y, del diario y el de 8 h, su valor más alto; sin P98 (de 24-72 valores es casi la hora más alta). H₂S, NH₃ y mercaptanos no tienen límite en el RD 102/2011: P98. Lo que pasa de su límite sale en el color de aviso. ⚠️ Es lo que aporta la planta, sin el fondo de la zona: no sirve para declarar que se cumple.
  **Reproductor:** ya no es de 24 h, y dice UTC y hora oficial. ⚠️ **Sin Z:, el reanálisis sigue siendo un día repetido** y su calendario de «Un día» solo tiene ese día; con la serie real, R tendrá otro formato (prueba 02). ⚠️ El episodio y la predicción van con GFS: sin ERA5 (haría falta la clave del CDS en ese PC y llega con ~5 días de retraso) ni MOS. ⚠️ Sin tarea programada: la predicción se prepara con su botón, en 9 min para 2 días, y no se lanza sola.
- **Panel por alcances (en diseño, 2026-10-24/25):** el primer bloque fija el ALCANCE (las 4
  preguntas de la oferta: Escenarios · Episodio · Predicción · Ahora) y, según él, «Focos»
  (catálogo común + OPERACIÓN propia de cada alcance) y «Simulación y resultados» cambian
  (Escenarios/Episodio: «Calcular»; Predicción/Ahora: estado, avisos, mejores franjas).
  Reproductor de tiempo bajo el mapa. Maqueta de prueba (privada):
  https://claude.ai/artifact/H6gHGUo3RQghdcdNQkKs9C. Aún NO está en la app: el usuario quiere
  pensarlo bien antes de programarlo.
- **Focos**: VARIOS, cada uno con su perfil de 24 h y sus emisiones de gases y de olor,
  caracterizados por velocidad (de salida), composición y altura. Si la planta los mide en otras
  unidades (ou_E/m³ y caudal, ppm, mg/Nm³, flujo por m²…), la herramienta los convierte a las del
  modelo (regla 1: áreas en g/(s·m²) POR m²; ou_E con su factor). Ya hay base:
  `docs/emisiones/olor_fuentes.py` (conversiones), `pilas_tipos.json` (flujo en reposo y en
  volteo → 24 factores), `pilas_catalogo.json`, `sources_ejemplo_17pilas.json`.
- **Configurador** (idea del usuario, «para tenerlo en cuenta ya»): como en digicompost, una 2.ª
  app dentro de la principal que define el número de pilas, el tipo de pila y el perfil horario de
  ou_E; aquí habrá que reconfigurarlo en función de la ACTIVIDAD de la planta (biometano +
  compostaje: tabla de focos probables en `docs/guias_cajon/00_ARRANQUE…` §2.3).
  Cómo es el de digicompost (revisado el 2026-10-24, solo lectura): código en
  `Escritorio\Mountains\inundaciones\digicompost\` (`app2.py` interfaz con pestañas Tipos y Pilas
  + mapa; `pilas.py` modelo). La app principal lo lanza como PROCESO APARTE (`QProcess`, `--enviar
  tmp/Sources/sources_configurador.json`) y al cerrarse carga ese JSON. Catálogo fijo de la nave
  (30 pilas L70/L50/L40), tipos de material {pollutant, unidad, q_reposo, q_volteo} en
  g o ou_E por s·m², estado por pila (tipo, ocupada, horas de volteo, por defecto [8, 16]) → perfil
  de 24 FACTORES relativos (1 en volteo, q_reposo/q_volteo el resto) con q = q_volteo (media de la
  hora). Solo áreas pasivas (sin velocidad, temperatura ni gases), solo ciclo diario, solo volteo
  como operación. ⚠️ Para pasar de ou_E a g exige un «pollutant» (H2S) solo por su factor, y la
  vuelta a ou_E/m³ usa el umbral de tabla en vez del factor de la fuente (posible incoherencia).
- Diseño que se está estudiando (sin decidir): SUPERPOSICIÓN. La concentración es proporcional a
  la emisión, así que basta con la respuesta horaria de cada foco a una emisión unitaria emitida
  en cada una de las 24 horas del día; cualquier perfil = suma de esas 24 respuestas por sus
  emisiones. Los gases de un mismo foco (sin química ni deposición) comparten la respuesta: la
  composición no exige cálculo nuevo. ⚠️ Cambiar la ALTURA, la VELOCIDAD o la TEMPERATURA de
  salida de un foco cambia la sobreelevación y su respuesta: hay que recalcular ESE foco.
  Posible truco de cálculo (a medir): las 24 respuestas de un foco en UNA pasada, con 24
  «especies» de cálculo (no son gases), cada una emitida solo en su hora; el motor aplica el
  perfil (IVARY = 1) especie a especie (`principal._factor_emision`).
- Limitaciones medidas del motor para los 5 años: odora puffs lee el fichero de viento ENTERO
  (≈ 2,7 GB por mes → unos 5 GB de memoria por proceso; el PC tiene 16 GB) y no encadena ficheros
  (`NMETDAT` = 1, `MRESTART` = 0): hay que trocear (p. ej. semanas con 1 día de arranque, como el
  viento) y medir que el corte no cambia el resultado. Estimación (a medir, desde el penacho del
  2026-10-21: 55 µs por receptor·hora): 5 años × 8 404 receptores ≈ 5-6 h de un núcleo por pasada
  (~2 h con el equipo entero); serie horaria de una respuesta ≈ 1,5 GB en float32.
- **Prueba 01 de superposición → HECHA** (`99-Test/01_superposicion`, 2026-10-24; viento local de
  48 h, 42 h desde las 06 del 20-oct, 8 011 receptores, 3 focos inventados: pilas y biofiltro de
  área con perfiles de 24 h distintos y una chimenea de 12 m, 10 m/s, 400 K; olor y NH3): la suma
  de respuestas unitarias por hora de emisión reproduce el cálculo directo con |Δ| ≤ 4·10⁻⁸ del
  máximo y 0 de 336 462 receptor·horas con |Δ|/valor > 10⁻⁴ (EXACTA, también la chimenea). Las 24
  respuestas de un foco en UNA corrida (24 especies) cuestan 38-40 s frente a 22-25 s con una
  especie (×1,6-1,8, no ×24); memoria ≈ 400 MB (≈ 2,3 × el fichero de viento); concentraciones
  3,8 MB frente a 2,8 MB (van comprimidas). Estimación para 5 años: ≈ 11 h de un proceso por foco
  (≈ 4 h con el equipo entero), ≈ 4 GB por foco; luego cada escenario es una suma, sin motor.
  `control_multiple.py` (varias especies, chimeneas y perfiles) es un prototipo: pasarlo a odora.
- **Tamaño (pregunta del usuario, 2026-10-24: reducir lo guardado y lo que cuesta leerlo).**
  Medido con las respuestas de la prueba 01 (24 × 42 h × 8 011): solo el 0,14-0,59 % de los
  valores supera 10⁻⁴ del máximo del foco (1,9-0,3 % > 10⁻⁵; 3-4 % no son cero). Guardando solo
  esos (índice de receptor + valor float16, la hora por bloques: 4 B por valor) ocupan
  0,04-0,19 MB por 42 h frente a 3,5-3,8 MB del fichero de concentraciones y 32 MB en denso; el
  float16 escalado al máximo da error relativo ≤ 5·10⁻⁴. Estimación 5 años: ≈ 0,05-0,2 GB por foco
  (umbral 10⁻⁴) o 0,15-0,65 GB (10⁻⁵) frente a ≈ 4 GB, y sumar escenarios cuesta en proporción. El
  umbral hay que fijarlo frente al criterio de olor más bajo con margen (truncar muchas
  contribuciones pequeñas subestima un poco lejos). La media es lineal: basta un mapa medio por
  foco y hora de emisión. Ideas propuestas (sin decidir): viento 3D completo solo en el archivo
  de CIRCE (Z:), el PC del operario con las respuestas + el nivel 1 para la animación; odora puffs
  leyendo el viento hora a hora del almacén comprimido (memoria de ~6 GB a decenas de MB, sin
  troceo ni arranques, 5 años seguidos repartidos por receptores; cambio de E/S en odora);
  clases o análogos meteorológicos en vez de 43 824 h solo como último recurso (aproximación).
  El usuario aprobó el orden (2026-10-24): 1.º respuestas dispersas, 2.º lectura hora a hora en odora.
- **Prueba 02, respuestas dispersas → HECHA** (`99-Test/02_respuestas_dispersas`, 2026-10-24):
  formato CSR por receptor (hora uint16, hora de emisión uint8, valor en cuantización
  LOGARÍTMICA de 16 bits: error ≈ 1·10⁻⁴ uniforme). Error frente al escenario simulado (receptores
  ≥ 0,1 % del máximo): umbral 10⁻⁶ ≤ 0,4 % · 10⁻⁵ ≤ 2,8 % · 10⁻⁴ ≤ 19 % (⚠️ el umbral relativo al
  máximo de cada foco engaña: lejos se suman muchas contribuciones truncadas) → **umbral 10⁻⁶**.
  Escala 5 años (42 h repetidas, 43 806 h, comprobado): 3 focos 2,1 GB sin comprimir (≈ 0,8 GB
  comprimido) frente a ≈ 101 GB en denso y ≈ 11,5 GB en ficheros del motor; leer 4,2 s; media,
  máximo y P98 de un escenario en los 8 011 receptores 69 s; un día hora a hora 2,7 s; memoria
  5,2 GB (.npz se carga entero: pasar a .npy con mapeo de memoria). Pendiente: umbral ABSOLUTO
  frente al criterio de olor, y medir con 5 años reales.

### Receptores de cálculo (2026-10-18, propuesta a revisar con el usuario)
- ⚠️ Medido el 2026-10-30: la malla fina y las viviendas (±2 km) NO llegan a Santa Bàrbara, el foco de
  las quejas (Institut Les Planes a 2,5 km, núcleo a 3 km): queda con 300 m y un solo punto. Propuesta
  en `docs/contexto_quejas_olores.md` §6 (11 puntos de la auditoría de 2024 y pueblos); sin decidir.
  ⚠️ **RECTIFICACIÓN (2026-10-31):** con la malla nueva, los 100 m ya llegan a ±3 km: Institut Les
  Planes, centro del pueblo y el 89 % del polígono CORINE de Santa Bàrbara (y = 2 033-3 471 m al N de
  la planta; el 100 % exigiría ±3,5 km, +1 152 receptores). Godall y Freginals siguen a 300 m.
- Hoy `gui/receptores_mapa.py` + `odora.preparacion.receptores.malla_anidada` (adaptación de `cajon/utilidades/malla_receptores.py`):
  **malla del 2026-10-31 (decisión del usuario):** cercana 25 m a ±500 m (1 681) · próxima 50 m a
  ±1 km (1 240) · fina 100 m a ±3 km (3 280) · media 300 m a ±6 km (1 240) · gruesa 700 m en todo el
  dominio de ±24,5 km (4 752) · 66 núcleos CORINE · 393 viviendas del Catastro a < 2 km (CORINE no ve
  el pueblo) · 4 con nombre (Dacame) = **12 656** (antes 8 404: fina a ±2 km, sin cercana ni próxima; ⚠️ RECTIFICACIÓN del 2026-11-01, decisión
  del usuario: Dacame es UN punto, **12 653**). Mismo origen (la
  planta), cada nivel fuera del cuadrado interior; la
  gruesa llega justo al borde (35 × 700 m) y sustituye al anillo del cajón. Sin lista de focos,
  los niveles se centran en la planta. Capa «Receptores (malla de cálculo)» en el selector (fuera del
  grupo temático excluyente), apagada al arrancar, puntos en canvas. Coste CALPUFF estimado:
  ~15 ms por receptor, semana y fuente → ~1,8 h por fuente y año en un núcleo.
- **Más detalle cerca de la planta (2026-10-31; DECIDIDO: malla de arriba, sin nivel de 5 m, aprobada
  por el usuario; `99-Test/04_malla_cercana`).** Comprobada con las pilas de la prueba 04: 12 259
  receptores sin viviendas, 34,3 s frente a 26,1 s (+31 %); 10 491 receptores comunes con la prueba,
  diferencia 0. ⚠️ **RECTIFICACIÓN:** el edificio que el usuario llamó «de ENCE, a 500 m al sureste» no
  son oficinas de ENCE sino **Dacame S.L.** (fábrica de andamios vecina, 26-50 empleados según
  Iberinform; Ctra. Santa Bàrbara-La Sénia, TP-3311, km 4,6 según su web) y está al **OSO**, no al SE.
  Importa por quienes trabajan allí. Ubicación confirmada por el usuario (2026-10-31). ⚠️ RECTIFICACIÓN (2026-11-01, decisión del usuario, «pon solo
  1 nave»): un solo receptor «Dacame», en el centro de las naves ponderado por superficie (286 227,7, 4 507 319,8; 557 m, rumbo 254°). Antes: las 4 naves del
  Catastro de ese complejo (2,2 ha; 470-644 m, rumbo 251-260°) son receptores CON NOMBRE en
  `planta/receptores.json` (`receptores_mapa.con_nombre`). Caen a caballo entre la malla de 25 y la de
  50 m. Aún sin ficha en el mapa: solo puntos en la capa de receptores. **Sensores: aún no se sabe dónde
  irán (usuario, 2026-10-31).** Cuando se sepa, van a ese fichero y solo hay que calcular esos receptores
  (son independientes: el resto no cambia). El usuario quiere resultados
  precisos donde estarán los sensores y también el alcance
  a 25 km. Descartadas por ahora dos simulaciones con el mismo viento: darían lo mismo que una sola
  malla anidada (`99-Test/04_malla_cercana`: mismo receptor, mismo valor en las dos mallas,
  diferencia 0,0, ya medido con odora). Un viento propio a 100 m exigiría otra serie de 5 años: la
  estación más cercana (C9) está a 7 km y queda fuera de un dominio de ±5 km. Propuesta del usuario: 5 m a ±100 m, 25 m a
  ±500 m, 50 m a ±1 km y el resto igual → 12 484 receptores, +25-35 % de tiempo, valores que
  guardar ×1,6-2. Mediana de lo que se pierde en el máximo de 42 h sin cada nivel: 5 frente a 25 m
  6-12 % · 25 frente a 100 m 15-23 % · 50 frente a 100 m 8-14 % · 100 frente a 300 m (a 1-2 km)
  18-23 %. ⚠️ ±100 m cae en UNA sola celda de viento de 400 m y dentro de la planta (4 de ~5 ha). El
  pico junto a un foco de superficie sube ×1,5-1,9, y la escala de los mapas sale del máximo (máx /
  10): habría que excluir la planta o la escala cambiaría por valores de dentro. Mapa: `penacho_dia`
  usa su propia malla regular de 250 m, así que ver la zona cercana exige otra imagen. El error de
  dirección (30,6° en la estación dejada fuera) desvía el penacho 1,2-1,8 km a 2-3 km: lo que más
  ayudaría a la precisión cerca de la planta es un anemómetro allí; aparte, poner cada sensor como
  receptor discreto.

### CALMET precalculado (2026-10-15, en prueba)
- **Objetivo del usuario:** viento 3D horario de los 5 años YA simulado (CALMET solo con ERA5,
  `NOOBS = 2`) para calcular después solo la dispersión; y validarlo comparando, en el punto de
  CADA estación, la rosa de vientos de CALMET con la observada (`validacion.comparar_calmet`).
  Las estaciones no entran en CALMET: así son una referencia independiente.
- Hoy `gui/tareas/viento3d_casos.py` + `odora.preparacion.viento3d` (antes `calmet.py`, port de `getCalpuff.py`): rejilla 125×125 de 400 m sobre los 50 km, 12
  niveles (`config.VIENTO3D_ZFACE`), huso 31, z0/albedo/Bowen/IAF por celda (el cajón ponía z0 = 0,1
  en todo), columna ERA5 a la cota del modelo (267 m) y 975 hPa sustituido por el viento a 10 m
  cuando queda bajo el suelo de ERA5. Un caso por mes en `DATOS/viento3d_estudios/AAAAMM/` (antes `DATOS/calmet/`).
- CALMET etiqueta cada hora por su FINAL (`IBHR = 0` → primer registro 2021-001 00 h = instante
  ERA5 00 UTC). Un mes: ≈ 1,5-2 h en un núcleo y 2,7 GB de CALMET.DAT (59 campos/h de 125×125).
- `odora.meteo.viento3d.almacen` (v0.1.2; antes `calmet_pack.py`): `.cmz` por mes (16 bits + Δt + byte-shuffle + zlib; enteros, EL y
  campos estáticos sin pérdida): 9,3× medido, error de viento ≤ 0,0001 m/s. 5 años ≈ 18 GB.
- Hoy `gui/tareas/puffs_casos.py` + `odora.preparacion.puffs` (antes `dispersion/calpuff.py`): control de puffs mínimo (áreas, receptores discretos). ⚠️ NZ y ZFACE del
  control de puffs TIENEN que coincidir con los del CALMET.DAT (si no, METQA aborta). ⚠️ RECTIFICACIÓN (2026-11-02, medido): eso es del .exe; `dispersion.puffs` solo comprueba NX y NY, y NZ y ZFACE los toma del viento.
- ⚠️ Medido en las primeras horas: `TEMPK` sale UNIFORME en todo el dominio (no se corrige con la
  cota): en Els Ports da 7 K de error. Pendiente de corregir.
- **Validación de enero 2021 (solo ERA5):** CALMET NO corrige la dirección (error 16–46°, igual
  que ERA5 en las 8 estaciones) y no produce calmas. Falta ver los 5 años (brisas de verano).
- **2021 completo** (precalculado el 2026-10-16 en 1 h 50 min con 7 procesos, 0 fallos, ~300 MB
  por mes en .cmz; `validacion.comparar_calmet_anual`, `rosas_calmet_anual_2021.png`):
  dirección CALMET 29–52° frente a ERA5 32–54°: mejora poco (les Cases d'Alcanar 54→41°,
  l'Aldea 32→29°, que es la ÚNICA bajo 30°), empeora en Els Ports y Aldover; en verano tampoco
  mejora. Las rosas de CALMET siguen siendo las de ERA5 (NO + S); no reproduce la canalización
  medida (Aldover N, els Alfacs NNO, Ports O). Velocidad: baja la media (2,0–2,4 frente a 2,96
  m/s): mejor en las estaciones abrigadas de 2 m, peor en las expuestas (Amposta, Ports).
  Calmas 6–10 % (ERA5 3 %). Temperatura peor que ERA5 (TEMPK uniforme, pendiente).
  Conclusión: **ERA5 en una sola columna no basta para el viento local**; probar CALMET con
  estaciones (validando con la que se deja fuera), ajustar sus parámetros de relieve, o WRF.
- **Idea 1, CALMET + estaciones (NOOBS = 1)** (`preparar_mes(estaciones=…)`,
  `estudios/calmet_sin_estacion.py` (en el zip de archivo) y `evaluar_sin_estacion.py`). Dejando fuera C9 (la más cercana a la
  planta) y comparando ALLÍ, ene/jul 2021: dirección ERA5 40/39° · CALMET-ERA5 42/37° ·
  +7 estaciones R1 5 km **40/30°** · R1 15 km 39/33°. Velocidad RMSE 2,31→1,96 (ene),
  1,52→1,35 (jul). R1 = 15 km reparte las calmas de los anemómetros abrigados de 2 m (17,6 % en
  julio frente a 1,5 % medido): mejor R1 = 5 km. El NO del mestral sale demasiado del O en C9;
  la componente S (brisa) se queda corta. En la PLANTA el sector sur pasa de SSO (solo ERA5) a
  SSE (con estaciones): la configuración cambia hacia dónde iría el olor.
- **Idea 2, parámetros de relieve SOLO con ERA5** (para que valga en predicción;
  `estudios/calmet_ajustes.py` (en el zip de archivo), `evaluar_ajustes.py`), ene/jul 2021, error medio de dirección en
  las 8 estaciones: base 38,6/39,1° · TERRAD 15 km 38,9/40,9 · IKINE = 1 38,4/39,1 (no hace
  nada) · CRITFN 2 38,9/41,0 · combinada 39,2/45,8°. **No mejora**: mueve el error de unas
  estaciones a otras (els Alfacs 34→28° con TERRAD 15, pero l'Aldea 36→44° y en la combinada
  65°). Un modelo diagnóstico redistribuye el flujo de ERA5 pero no crea las circulaciones
  térmicas (brisa, vientos de valle, drenaje). Se quedan los parámetros base (TERRAD 5 km).
  En la planta el sector sur cambia de SSO a SO según la variante: incertidumbre real.
- **Idea 3, modelo dinámico de alta resolución: AROME HD de Météo-France (≈ 1,3 km)**
  (`estudios/arome.py` (en el zip de archivo), `estudios/evaluar_arome.py` (en el zip de archivo); archivo de predicciones de Open-Meteo, 2024-2025
  en las 8 estaciones y la planta). Comprobado el 2026-10-17: el dominio de AROME cubre La Galera;
  archivo AROME HD desde ≥ 2023-10 y AROME France (2,5 km) desde 2024-01; NO hay 2021-2023.
  Resultado: dirección media 42,8° (ERA5) → **30,1°**; bajo 30° en l'Aldea 23, Aldover 20
  (capta el eje N-S del Ebro), els Alfacs 26, les Cases d'Alcanar 27 (55 con ERA5); C9 44→35;
  Els Ports sigue mal (46°). Mejora en TODAS las estaciones del año. Temperatura mejor en todas
  (0,7-1,1 K). Velocidad SOBREESTIMADA (+0,5 a +1,7 m/s; RMSE 2,03 frente a 1,83 de ERA5) y
  pocas calmas. Archivo con alturas (20, 100 m…) en HD y algunos niveles de presión (850 hPa)
  solo en AROME France. ⚠️ API gratuito de Open-Meteo = uso NO comercial: en producción, GRIB
  oficiales de Météo-France (Licence Ouverte) o plan de pago.
- **Barrido de fuentes** (`lib/galera/entradas/openmeteo.py`, `estudios/descargar_modelos.py` (en el zip de archivo),
  `evaluar_modelos.py`; media de las 8 estaciones, mismas horas). 2024-2025: **AROME HD + ICON-EU
  (media vectorial) 27,6°** (6 de 8 bajo 30°, RMSE 1,58) · ICON-EU 29,5° · AROME HD 29,9° ·
  AROME FR 30,4 · ARPEGE 32,1 · IFS 9 km 34,1 · UKMO 34,4 · GFS 37,9 · IFS 0,25° 39,6 ·
  ERA5 41,2°. En las estaciones de 10 m, ICON-EU sin sesgo de velocidad (+0,03), AROME HD +0,89.
  2021-2023 (sin AROME/ICON): IFS 9 km 35,8° (ERA5 42,6°); 2022-2023 IFS + UKMO 33,7°.
  ⚠️ **En la PLANTA las fuentes no coinciden**: ERA5 da sobre todo NO (mestral), AROME HD e
  ICON-EU dan SO/SSO/S/OSO: el penacho iría a lados opuestos. Lo zanjaría la estación de ENCE.
- **CALMET con la mejor fuente** (hoy `odora.preparacion.viento3d.pronostico.escribir_columnas` + `estudios/cadena_icon.py` (en el zip de archivo), antes `calmet_modelo.py`; `estudios/calmet_icon.py` (en el zip de archivo),
  `evaluar_icon.py`; 2026-10-17, ene y jul 2024, 8 estaciones FUERA de CALMET):
  V1 = 3D.DAT con 10×10 columnas reales de ICON-EU (cada 6,25 km, 1000-600 hPa);
  V2 = V1 + 36 pseudoestaciones (6×6 cada 8 km) con la media vectorial AROME HD + ICON-EU a 10 m
  (NOOBS = 1, R1 4 km, RMAX 15 km). Error medio de dirección jul/ene: ERA5 41/43° · AROME HD +
  ICON-EU tal cual 25,4/30,5 · V1 27,4/32,3 · **V2 24,7/28,9°** (la mejor; en C9, la más
  cercana a la planta, 22,0/32,3° frente a 29,4/35,6 del modelo tal cual). Velocidad V2: RMSE
  1,24/1,50 m/s (ERA5 1,64/1,67), sesgo +0,55/+0,44; T 1,0/1,2 K. V1 da demasiadas calmas en enero
  (13,9 %) y peor T (2,2 K). En la planta V2 da S/SSE en julio y NO/ONO/OSO en enero, con ~11 % de
  calmas. ⚠️ Con varias capas bajo el suelo del modelo hay que ESCALONAR sus alturas (2 m) o
  CALMET divide por cero en `_stull0_`. Un mes V2 ≈ 90 min en un núcleo.
- **Reanálisis 2024-2025 con la cadena V2** (`estudios/calmet_reanalisis_icon.py` (en el zip de archivo), casos en
  `DATOS/viento3d_estudios/icon/AAAAMM`, almacén `DATOS/viento3d_estudios/cmz_icon/`): ene-may y jul 2024 hechos el
  2026-10-17 (~90-100 min por mes con 6 a la vez); el resto, en marcha y limitado por el cupo.
  ⚠️ **Cupo del API gratuito de Open-Meteo**: «Daily API request limit exceeded» (429) tras un
  día de barrido + experimentos. Cuenta llamadas PONDERADAS (variables, días y puntos): un mes de
  la cadena V2 (100 columnas × 45 variables + 2 × 36 pseudoestaciones) ≈ 1 200, así que caben
  ~8 meses al día. `openmeteo._get` ya espera a que se renueve el cupo (diario a las 00 UTC).
  Para producción comercial hace falta el plan de pago o las fuentes oficiales.
- ⚠️ **Disco lleno el 2026-10-18** (3,8 GB libres en C:, el único disco): 4 meses en marcha
  (2,8 GB cada CALMET.DAT) + la copia temporal de 2,8 GB de `recortar_arranque` + otros
  programas del PC. Tres meses murieron a medias. Arreglos: el arranque se recorta AL VUELO en
  `almacen.comprimir(recorte=casos.recorte_de(caso))` (sin copia); `_esperar_disco` cuenta
  los meses en marcha (3 GB cada uno); `--solo-series` guarda solo `puntos.csv` (validación) y
  borra el CALMET.DAT; los fallos se avisan al momento. Qué se guarda comprimido se decide en el
  tema de la BASE DE DATOS meteorológicos (pendiente con el usuario).
- ⚠️ **`LCALGRD = T` es necesario**: sin la W y la T 3D, CALPUFF cambia (47 % de valores
  idénticos, Δ hasta 92 µg/m³ sobre 559; medido 2026-10-17). No quitarlos para ahorrar disco.
- **Tamaño del almacén:** la cadena V2 comprime peor que la de ERA5 (≈ 770 MB/mes frente a
  ≈ 300: más detalle espacial); WFACE 26 %, U 21 %, V 21 %, T-LEV 20 %. Con paso físico
  (`almacen.PASOS_FISICOS`: 0,01 m/s, 0,001 m/s en W, 0,01 K) baja a ≈ 460 MB/mes, pero
  CALPUFF cambia (P98 por receptor −1,4 % de media, hasta 12,5 %): CALPUFF es caótico ante
  perturbaciones de 0,005 m/s. Por ahora se guarda la versión de 16 bits (siempre se puede
  recomprimir con paso físico; al revés no).
- **WRF propio:** este PC NO tiene WSL ni Docker (WRF es de Linux): instalar WSL requiere
  administrador y reiniciar. Solo haría falta para 2021-2023 (sin archivo de AROME) o para
  predicción a 1 km más allá de ~2 días.
- SURF.DAT que acepta calmet.exe 5.8.5 (medido con sus mensajes): cabecera con «NONE» y 8
  valores `IBYR IBJUL IBHR IEYR IEJUL IEHR IBTZ NSTA` (sin segundos ni línea UTC), registros
  `año día hora` (hora final). Sin SEA.DAT hay que poner `JWAT1 = JWAT2 = 999` o CALMET se para
  en la 1.ª hora («grid cell … has no valid sites»). Con NOOBS = 1 e `ITPROG = 1` la TEMPK ya
  varía con las estaciones (se acaba el campo uniforme).
- **Compresión medida con CALPUFF** (enero, 1 semana): 2,74 GB → 271 MB (10×); CALPUFF idéntico en
  166 de 168 h; las 2 h distintas son una noche muy estable y el receptor dentro de la fuente.

### Paralelización (medido 2026-10-15, i7-1255U)
- **CALPUFF se reparte por RECEPTORES** y el resultado es idéntico bit a bit (comprobado con 4
  estrategias). Coste: t = 2,1 s + 15 ms·receptor por semana y fuente → el 97 % es muestrear
  receptores; la parte fija equivale a ~140 receptores (`MIN_RECEPTORES_BLOQUE = 300`).
  ⚠️ RECTIFICACIÓN de la guía 05 del cajón («CALPUFF no se reparte»): no se reparte por TIEMPO
  (los puffs tienen memoria), pero por receptores sí.
- **Núcleos rápidos/eficientes** (`lib/galera/nucleos.py`, `estudios/medir_nucleos.py` (en el zip de archivo)): Windows dice
  el tipo (EfficiencyClass): lógicos 0-3 = 2 núcleos P con hyperthreading, 4-11 = 8 núcleos E.
  Con TODO cargado un lógico P rinde 1,28× uno E (no 2-3×: el portátil lo limita a 15 W).
  `calpuff.ejecutar_paralelo` da más receptores a los rápidos y fija cada proceso a su
  procesador: 4900 receptores ×2,83–3,0 frente a ×2,63 a partes iguales sin fijar (+7 %).
  Bloques pequeños en cola (48) son PEORES (×1,36): pagan 48 veces la parte fija.
- ⚠️ **Varios calmet/calpuff a la vez fallaban al azar (~6 %)**: compilados con Lahey/Fujitsu
  Fortran, crean su temporal (unidad 99) en %TMP% y chocaban entre procesos («DeleteFile,
  errno=32, unit=99» en `_wrout1_`). Arreglo: `casos.entorno_privado(caso)` → TMP propio por
  proceso (0 fallos en 60 corridas). Usarlo SIEMPRE que se lancen los .exe.
- **CALMET se reparte por TIEMPO** (no tiene receptores; el ajuste al relieve es de todo el
  dominio). Escala ×4,7 con 10 procesos (10 → 47 h simuladas/min); 5 años ≈ 16 h.
  ⚠️ **Arranque en frío:** CALMET tiene memoria NOCTURNA: un trozo que empieza a las 00 UTC
  difiere (viento a 10 m hasta 9 m/s, estabilidad, T) hasta la salida del sol (08 UTC en enero);
  desde ahí es idéntico bit a bit. Cada trozo debe empezar el día ANTERIOR y descartar esas
  24 h. Ya aplicado (antes figuraba como pendiente): `viento3d_casos.mes_serie` arranca 24 h antes y las recorta con `viento3d_casos.recorte_de`.

## 6. Decisiones abiertas (preguntar, no inventar)

- **Horizonte «presente»:** ERA5 llega con unos días de retraso y GFS es predicción. Opciones a valorar
  con el usuario: encadenar las primeras horas de los últimos ciclos GFS, observación horaria de AEMET,
  o una estación meteorológica de la propia planta si existe.
- **Qué es el «servicio»:** de momento, app de escritorio PySide6 (disposición propuesta por el
  usuario). Falta decidir si además habrá servicio de Windows o tarea programada.
- **Licencias** para instalar en el PC del operario: CALPUFF (permiso de Lakes o que ENCE lo descargue
  y acepte el EULA), fondo de mapa sin Esri, modelo de IA sin `qwen2.5:3b`.
- **Criterio de olor** acordado con el cliente y por escrito (1,5 / 3 / 5 ou_E/m³), y tipo de residuo
  que entra a compostaje (digestato, fracción sólida o verde). La auditoría de 2024 usó 5 ou_E/m³,
  30 min, 2 días de 7 (olfatometría de campo; modelo de ordenanza de la Diputació de Barcelona), que
  no es comparable con el P98 del modelo; en Cataluña el P98 no es norma.
- **Lista de focos** de la planta con sus datos (tabla en `00_ARRANQUE…` §2.3).
- **Bandas e isopletas (orden aprobado por el usuario el 2026-11-01; siguiente paso, tras los gases, ya hechos):** bandas con la tabla de color del filtro, sin rehacer imágenes (sin probar), e isopletas con `contourpy`: 1, 3 y 5
  en media, máximo y P98, y solo la de 1 en el penacho; niveles y factor pico-media juntos en un único criterio (el 1/3/5 italiano supone ×2,3). Más allá de ±3 km la malla pasa a 300 y 700 m, y el decreto italiano pide 25-250 m.
- ⚠️ RECTIFICACIÓN (2026-11-01, pedido del usuario): ya está en la app, ver «Visor 3D en la app». **Isosuperficies 3D: prototipo hecho (`99-Test/07_isosuperficies`, 2026-11-01; el usuario quiere verlas, y meterlas en la app queda para más adelante).** `penacho_3d.html`: solo el penacho del día, en una vista aparte. Un día
  ≈ 10 min con 4 procesos (15 alturas a 100 m y una 2.ª pasada a 25 m donde hay penacho); la altura 0 coincide bit a bit con la corrida 2D y el balance de masa cierra. A 1 ou_E/m³ no pasa de 20-75 m de altura: sin exagerar es casi plano,
  y desde arriba es lo mismo que el mapa 2D. Meterlo exigiría lanzar el motor en el PC del operario y disimula los ~30° de error de dirección.
