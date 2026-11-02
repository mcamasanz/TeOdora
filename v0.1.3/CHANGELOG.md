# Historial de versiones

Formato basado en [Keep a Changelog](https://keepachangelog.com/es-ES/1.1.0/); versionado
semántico.

## [0.1.3] — 2026-11-02

**odora pasa a llamarse teOdors.** El paquete es `teodors` (`import teodors`, `python -m teodors`). Lo
que sigue, hasta la 0.1.2, conserva el nombre antiguo porque cuenta lo que pasó entonces.

La herramienta entera pasa de los proyectos a teOdors, por tandas, para que replicarla en otra planta
sea cambiar de carpeta. Los motores no cambian: solo el texto de 7 mensajes, que nombraban el programa al que equivalen.

**El repositorio se organiza por versiones y plantas:** cada versión exacta, en su carpeta (`v0.1.3/`), que no se vuelve a tocar; cada planta, en
la suya, con sus datos de entrada y un fichero `VERSION` con la versión que usa. Ver el `README.md` de la raíz. Las versiones anteriores siguen en
sus etiquetas, con la organización de entonces.

### Añadido
- `planta.nueva`: crea la carpeta de una planta a partir de sus coordenadas y, con `--descargar`, baja su terreno, sus usos del suelo y
  sus edificios y anota las estaciones cercanas. El ejemplo de la configuración y la ortofoto del visor 3D pasan a ser opcionales.
- `planta`: el terreno, los usos del suelo y los edificios van en la carpeta de la planta, no en DATOS (los cálculos): sin la unidad de datos sigue
  habiendo mapa. `rutas.json` admite una ruta relativa a esa carpeta.
- `planta`: una planta se lee de su carpeta (`planta.json`, `emplazamiento.json`, `rutas.json`…).
  `planta.activar(carpeta)` la fija para el proceso y sus hijos; `planta.DATOS`, `planta.EPSG_UTM`…
  dan los suyos; `planta.geo` hace las cuentas de `comun.geo` en su huso. Los motores no la usan: lo
  comprueba una prueba.
- `comun.registro`, `comun.formato`, `comun.errores`, `comun.procesos`, `comun.mercator` y
  `comun.escalas` (extra `odora[mapas]` = matplotlib); `comun.geo.direccion` y
  `comun.geo.elevacion_solar`.
- `meteo.viento_local` (extra `teodors[viento_local]` = scipy). ⚠️ **NO VALIDADO y fuera de los motores:** no está en `MOTORES` ni
  se lanza con `python -m teodors`. Solo enseña el efecto de los edificios en el viento: no da valores para un sensor y el penacho no
  lo usa. `modelo`: masa consistente con zonas empíricas de estela, y de un LiDAR en rejilla a los obstáculos. `biblioteca`: un campo
  por dirección, y `mezcla` para un viento cualquiera. Viene del proyecto de La Galera: mismo código función a función, salvo el
  import perezoso de scipy, y lo propio del sitio pasa al bloque `viento_local` de su `planta.json`. Allí reproduce byte a byte las
  2 direcciones que se han recalculado de su biblioteca de 36. `mezcla` es nueva en Python: la hacía el mapa de su aplicación.

- `fuentes` (extras `teodors[fuentes]`, `teodors[lidar]` y `teodors[gfs_historico]`): de un servicio de internet a la carpeta de DATOS de la
  planta. `terreno` (MDT del IGN, CORINE, CartoCiudad), `catastro`, `meteocat`, `era5` (CDS), `gfs_noaa`, `gfs_dynamical` y `lidar`, más
  `descargar_era5` y `descargar_meteocat` por línea de órdenes. **Son servicios de España**, salvo ERA5 y GFS: no se ha intentado generalizarlos.
  Vienen del proyecto de La Galera: mismo código función a función, salvo lo propio del sitio, que pasa a planta.json (bloques `estaciones` y
  `pronostico`; `identidad.agente_http`; `viento_local.lidar_zona`), y los valores por defecto que dependían de la planta, que se resuelven al
  llamar. Nuevo: `gfs_noaa.indices_caja` admite una caja al oeste de Greenwich (allí no se ha usado). Las versiones de HTTP con reintentos
  no son iguales y se mueven sin fundirlas. Las pruebas no usan la red: ninguna descarga de verdad se ha lanzado con este código.
- `planta.pide` (un campo que hace falta, con un error que dice cuál) y `planta.AGENTE_HTTP`.
- `metricas` (`teodors[preparacion,mapas]`; matplotlib, solo para las figuras): validación del viento frente a las estaciones. `viento`: métricas y
  umbrales de Emery, Tai y Yarwood (2001), horas de una estación, rosas y su figura. `calidad`: control de calidad de una estación y sus rosas, con
  `python -m teodors.metricas.calidad`. No son motores. Vienen del proyecto de La Galera: mismo código función a función, salvo los valores por
  defecto que dependían de la planta, que se resuelven al llamar; la lectura de `estaciones.ceros_sospechosos`, al llamar y opcional, y
  `viento.convencion`, cuya ventana fija de 11,4 a 12,6 h UTC solo valía cerca del meridiano 0 y ahora va alrededor de `mediodia_h`: por
  defecto, `estaciones.mediodia_utc_h` de la planta y, sin él, el mediodía solar en su longitud (`viento.mediodia_solar`, nueva). Las
  estaciones son las de `fuentes.meteocat`. `a_horario` y `preparacion.viento3d.estaciones.medias_horarias` no se funden: dan horas distintas.
- `casos` (`teodors[fuentes]`): lo único que junta una planta, sus datos y los motores. `viento3d`: prepara, lanza y guarda los meses de una serie de viento 3D,
  con ERA5 y estaciones. `gfs_columnas`: las columnas de GFS para el pronóstico 3D. `receptores`: la malla de la planta y los estilos de su capa.
  `preparacion.puffs.control_fuentes`: control de puffs con varias especies y fuentes de área, punto y volumen, con un perfil de 24 h por fuente y especie; no
  necesita planta. Vienen del proyecto de La Galera: mismo código función a función, salvo lo propio del sitio, que pasa a planta.json (`receptores.niveles` y
  `estilos`, `pronostico.n_col` y `paso_col_m`, `series.r1_km` y `rmax_km`, `identidad.nombre_casos`); los valores por defecto que dependían de la planta,
  que se resuelven al llamar. Los radios solo hacen falta si hay estaciones.
- `operacion` (`teodors[fuentes]`; el penacho en 3D, también `teodors[penacho_3d]` = pyvista): de los focos y los planes de una planta a sus resultados, sin interfaz. `focos`: tipos,
  fichero y unidades; `planes`: diarios, semanales o mensuales, en hora oficial; `normativa`: columnas y estadísticos, por año civil en el peor año; `periodos`; `simulacion`: suma las
  respuestas sin lanzar el motor; `penacho_mapa`, `viento_mapa`, `penacho_3d`; y por línea de órdenes, `respuestas`, `viento_periodo`, `viento3d_series` y `ejemplo_configuracion`.
  Vienen del proyecto de La Galera: mismo código función a función, salvo lo propio del sitio, que pasa a planta.json (`proyeccion.zona_horaria`; `series.era5`, `gfs`, `preferidas`,
  `titulos` y `dia_prueba`; `operacion.tipos_foco_extra` y `ejemplo`; `visor3d`). La firma de un resultado da el mismo valor y lo guardado se sigue leyendo. Nuevo: la plantilla nacional
  de normativa (`normativa_nacional.json`, RD 102/2011, PRELIMINAR), que el `normativa.json` de la planta sustituye, y `package-data` para ella y los iconos.
  `geometria` (de una ficha de foco a una fuente del motor) está en `operacion.focos`: `preparacion` no sabe nada de los focos. `penacho_3d` calcula y guarda; montar su página es de la interfaz.
- `mos` (`teodors[mos]`): corrección estadística de la predicción de GFS en cada estación. `tabla`: tabla de entrenamiento, partición por semanas de la hora de validez y error de GFS sin
  corregir; `entrenar`: modelos por estación y sus métricas en las semanas de validación; los dos, también por línea de órdenes. No es un motor y no entra en `MOTORES`. ⚠️ Su mejora de
  dirección es local a la estación: ver su README. Guarda los modelos, pero ninguna función los aplica aún a una predicción nueva. Viene del proyecto de La Galera: mismo código función a
  función, salvo `estaciones.codigos`, que se leía al importar y ahora al empezar; la última hora que cuenta, que pasa a `pronostico.mos_hasta`; el número de estaciones de un rótulo, y
  scikit-learn, joblib y xarray, que se importan al usarlos. Mismas rutas y formatos en `DATOS/mos/`. Con este código no se ha entrenado nada con datos reales.

- `gui` (`teodors[gui]`; con el penacho en 3D, `teodors[gui3d]`): la aplicación de escritorio de una planta, en PySide6 y con el mapa en una página web. Importar el paquete, `web`, `penacho_3d` o `principal` no
  carga Qt, y nada fuera de este paquete lo carga: lo comprueba una prueba, y los módulos con Qt no se prueban si no está instalado (`teodors[pruebas_gui]`, que usa la integración continua).
  `principal.main`: el arranque, lo que llama el `main.py` de cada planta. Viene del proyecto de La Galera: mismo código función a función, salvo lo propio del sitio, que pasa a planta.json (`identidad.ajustes`, `app_id`,
  `version`, `entidad` y `red_datos`; `fuentes.mdt`, `usos`, `edificios`, `nombres_nucleos`, `fondos` y `creditos`; `estaciones.proveedor`; `operacion.texto_modo_edicion`), y la zona horaria, la fecha mínima y «N años», que salen de lo que ya tenía. El
  objeto de la página pasa de llevar el nombre de un cliente a `window.mapaApp`, las clases CSS a `mapa-*`, el panel de las partículas a `mapaViento` y el puente a `MAPA:`, por script. Allí da los mismos textos, los mismos colores y, en los 4
  estilos, los mismos píxeles en el panel, y las mismas páginas, sin ventanas de verdad. `planta.CLAVE_EDICION`: el valor de `operacion.modo_edicion`. three.js va con su licencia, pero el `LICENSE` de teOdors aún no contempla a terceros.

### Cambiado
- `preparacion.viento3d.geofisica` lanza su proceso con `comun.procesos.entorno`, que además quita
  `PYTHONHOME`.

## [0.1.2] — 2026-10-23

Utilidades que no son motores, para que los proyectos (La Galera, digicompost…) no las tengan
repetidas: coordenadas, almacén y lectura selectiva del viento, preparación de casos de viento3d
y de puffs con el control escrito desde cero, y malla de receptores. Los motores no cambian (las
baterías y los casos de regresión dan lo mismo). Las fuentes de datos y las métricas de
validación quedan para otra versión (PENDIENTES §3).

### Añadido
- `comun.geo`: huso y EPSG del UTM (ETRS89 o WGS-84), ida y vuelta de coordenadas, convergencia de
  meridianos, giro del viento a la cuadrícula, distancia y rumbo, cuadrados de dominio. Viene del
  proyecto de La Galera (validado allí con pyproj: γ = −1,65° en EPSG:25831).
- `meteo.viento3d.almacen`: almacén comprimido (.cmz) del fichero de viento, ≈ 9× con error máximo
  de medio paso de cuantización por variable (enteros y EL sin pérdida), recorte al vuelo de las
  horas de arranque y lectura de una sola variable sin reconstruir el fichero. Lee los .cmz que ya
  escribía el proyecto de La Galera (mismo formato).
- `meteo.viento3d.fichero_viento.leer_campos`: lectura selectiva por capas y campos 2D (un mes de
  125×125×12 baja de ~5,5 GB a unos cientos de MB en memoria).
- `preparacion` (necesita pandas: extra `odora[preparacion]`): casos de `meteo.viento3d` montados
  desde datos ya descargados. `preparacion.control.Control` guarda las asignaciones EN ORDEN y
  escribe el control solo con `! NOMBRE = valor !` y `!END!` (los lectores ignoran el resto), con
  nombres de fichero propios (`viento3d.inp`, `geo.dat`, `pronostico3d.dat`, `nubes.dat`,
  `estaciones.dat`, `viento3d.dat`). `preparacion.viento3d`: control con y sin estaciones, malla y
  fichero geofísico, pronóstico 3D en una columna (reanálisis) o en columnas (modelo), nubes,
  medias horarias y fichero de estaciones, recorte de las horas de arranque y viento en un punto
  con dirección geográfica. Viene del proyecto de La Galera: allí da los mismos ficheros byte a
  byte y la misma secuencia de asignaciones en el control.
- `preparacion.puffs`: control de `dispersion.puffs` desde cero para una especie sin química ni
  deposición, fuentes de área (`fuente_area`, g/(s·m²) por m²) y receptores discretos sobre el
  viento 3D; `salida.concentraciones` (fin de cada periodo y matriz por receptor). En La Galera:
  misma secuencia de asignaciones que su escritor salvo los nombres de las salidas de
  deposición y visibilidad, y el mismo penacho bit a bit.
- `preparacion.receptores.malla_anidada`: rejillas regulares anidadas alrededor de un centro
  (cada nivel fuera del interior, sin duplicados) más receptores discretos dentro del dominio.

## [0.1.1] — 2026-10-20

Corrección de `meteo.viento3d` en las horas de transición (amanecer y atardecer) con relieve.

### Motivo
En un caso real de relieve complejo (La Galera, Montsià: 125×125 celdas de 400 m, cotas de 0 a
1 437 m, ERA5 en una columna, NOOBS = 2, ITPROG = 2), el viento a 10 m de la v0.1.0 se separaba de
calmet.exe 5.8.5 justo a las 06-07 y a las 19 UTC: |Δv| > 0,1 m/s en 767, 2 621 y 3 300 de las
15 625 celdas, sobre todo en ladera, con la clase de estabilidad cambiada en cientos de ellas. En
la cadena completa (viento3d + puffs, 24 h, 441 receptores) el P98 por receptor difería un 16 % de
media y hasta un 66 %. El resto del día coincidía, y `dispersion.puffs` con el MISMO fichero de
viento es idéntico a calpuff.exe: el problema estaba solo en viento3d. Los 51 casos de la batería
lo pasaban porque el criterio es la media de todas las horas y celdas, y los casos reales son de
llano (Lleida, Huesca), donde el bloqueo apenas actúa.

### Causa (medida como caja negra)
No era la clase de Turner: con su propio viento, cada programa reproduce su clase en el ~100 % de
las celdas. Con IFRADJ = 0 las diferencias desaparecen: venían del **bloqueo (Froude)**, que usa
una sola N para todo el dominio, y N depende de cómo se ajusta la temperatura a la capa de mezcla
justo cuando esta nace o se deshace. Tres reglas del original, cada una medida por separado:
1. **N del bloqueo**: temperatura de la hora SIN ajustar y T(ZUPT) adiabática solo donde la
   altura convectiva GUARDADA de la hora anterior (la promediada) llega a ZUPT. La v0.1.0 usaba la
   convectiva de la hora actual sin promediar. Con N forzada a las 07 UTC, el original usa 0,0061
   (mínimo neto: 15 celdas distintas frente a 1 444 con 0,0045 y 773 con 0,0072); la v0.1.0 daba
   0,0034.
2. **ψ de la convectiva** (solo ITPROG = 2): por debajo del primer nivel del pronóstico, θ de la
   temperatura 3D de la hora anterior (centros de capa, lineal y prolongada hasta el suelo) en vez
   de θ constante. Con el 975 hPa de ERA5 a ~100 m del suelo, la ψ de la primera hora convectiva
   salía 2-3 veces menor y su altura un 25-50 % mayor. En un caso llano y uniforme, con el LDB del
   original: Δθ 0,26 K frente a 0,17; ψ implícita 0,005184, calculada 0,005183.
3. **Temperatura 3D de salida**: ajustada con la altura convectiva YA promediada (IAVEZI), no con
   la de antes del promedio.

### Cambiado
- `meteo.viento3d.principal`: las tres reglas, con sus constantes de módulo para volver al
  comportamiento de la v0.1.0 si hiciera falta (`N_CON_ALTURA_ANTERIOR`, `N_MASCARA`,
  `PSI_DE_T3D`, `T3D_CON_PROMEDIADA`) y las funciones `_n_zupt` y `_theta_capas`. ITPROG = 0
  (sondeos) no cambia. La regla 2 no se aplica con ITPROG = 1: allí la capa 1 viene de las
  estaciones y empeoraba un caso con ICON-EU y 36 estaciones.
- README del motor, §Transiciones, con las medidas.

### Validación
| Caso (48 h, 24 de arranque) | celdas·hora \|Δv\| > 0,1 m/s | P98 por receptor, \|Δ\| medio (máx.) |
|---|---|---|
| ERA5, NOOBS = 2, ITPROG = 2 | 6 800 → **89** | 16,3 % (66 %) → **0,2 % (2 %)** |
| ICON-EU 10×10 + 36 estaciones, NOOBS = 1, ITPROG = 1 | 942 → **227** | 0,9 % (15 %) → **0,1 % (3 %)** |

Pruebas: 158 de 158 (5 nuevas en `test_viento3d_transiciones.py`); el caso de regresión
`viento3d/llano_lleida` sale idéntico byte a byte, sin cambiar ninguna referencia.

### Pendiente
- Volver a correr la batería de laboratorio de 51 casos de viento3d con la v0.1.1.
- La altura convectiva de la tarde se separa poco a poco del original (|ΔZI| relativo medio
  0,6 %) y, con ITPROG = 1 y estaciones, la ZI y la temperatura de día (2,3 %), igual que en la
  v0.1.0.

## [0.1.0] — 2026-10-18

Primera versión del núcleo: los ocho motores propios reunidos en un solo paquete, ordenados por
uso y con nombres propios.

### Añadido
- `terreno.relieve` (≡ AERMAP), `terreno.superficie` (≡ AERSURFACE, con adaptador CORINE),
  `terreno.edificios` (≡ BPIPPRM) y `terreno.geofisica` (≡ MAKEGEO, con adaptador CORINE).
- `meteo.capa_limite` (≡ AERMET) y `meteo.viento3d` (≡ CALMET), con estaciones de superficie,
  sondeos, costa (boyas, COARE, OCD), brisa, pluviómetros, O'Brien y efectos cinemáticos.
- `dispersion.penacho` (≡ AERMOD), con todas las fuentes salvo aeronaves, plataformas y HBP: química
  del NO2, deposición, RLINE, BUOYLINE, OPENPIT y SWPOINT; varios años y re-arranque (MULTYEAR,
  SAVEFILE, INITFILE), MAXDAILY, FASTAREA y FASTALL, y la mayoría de los volcados de DEBUGOPT.
  Núcleo compilado con numba generado desde el propio Python.
- `dispersion.puffs` (≡ CALPUFF), con áreas, volúmenes, chimeneas con sobreelevación, efecto
  edificio (ISC y PRIME), deposición seca y húmeda, malla de receptores, emisiones variables
  (PTEMARB, VOLEMARB) y dispersión MDISP 2, 3 y 4.
- Línea de órdenes común `python -m odora <motor>`.
- El código en la carpeta `core/`, instalado e importado como `odora`.
- README por carpeta con la definición y la equivalencia de cada función.
- **Auditor** (`python -m auditor`): reglas para entrar en `main` (pruebas que pasan, rápidas, con
  pruebas nuevas para el código nuevo, referencias justificadas, sin perder pruebas), 13 casos de
  regresión (todos los motores) contrastados con los programas originales, hook `pre-push` y flujo
  de GitHub Actions. La rapidez se mide con la caché de numba caliente.

### Validación
Cada motor se ha validado frente a su programa original con su batería de casos, 472 en total
(ver [docs/validacion.md](docs/validacion.md)). El código de esta versión es el de la traducción
validada, con los nombres nuevos. Las ocho baterías se han vuelto a correr sobre este paquete y dan
los mismos resultados que en el laboratorio.

### Pendiente
Ver [PENDIENTES.md](PENDIENTES.md).
