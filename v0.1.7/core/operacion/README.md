# `teodors.operacion` — la operación de una planta, sin interfaz

<!-- manual -->
## Qué hace

Lleva de los focos y los planes de una planta a lo que dice la norma en cada receptor. No son motores ni equivalen a ningún programa, y no necesitan Qt: la interfaz va encima.

| Módulo | Qué da |
|---|---|
| `focos` | los 13 tipos de foco (sin los de combustión), ampliables por planta; `focos.json`; de lo que se mide (ppm, mg/Nm³, ou_E/m³, por m²…) a lo que pide el modelo; el olor estimado por el gas dominante; la composición del gas de salida de un punto y su densidad; `geometria`: de una ficha a una fuente del motor |
| `estela` | los edificios alrededor de un foco punto (los descargados, con la altura del LiDAR de la planta si lo cubre) y su estela en las 36 direcciones del viento, con `terreno.edificios`: lo que el motor necesita para el efecto edificio, sin escribir nada a mano; por procedencia del viento, si la chimenea queda dentro y a qué altura saldría libre |
| `edificios_planta` | los edificios de la planta, los de la estela de sus chimeneas, por tres caminos: del Catastro (`desde_catastro`), del LiDAR (`desde_lidar`: las huellas del Catastro con la altura del LiDAR y lo que el LiDAR ve y el Catastro no tiene) y dibujados por el administrador; `importar`, que respeta lo dibujado; `recalcular_focos`, la estela de los focos punto al cambiarlos. En `edificios_planta.json` de la planta |
| `planes` | planes diarios, semanales o mensuales de cada foco, en hora oficial; `factores`: la emisión hora a hora, en UTC |
| `normativa` | qué columnas se enseñan de cada magnitud y sus estadísticos: por año civil en el peor año o, en un periodo de días, media, máximo y horas por encima |
| `periodos` | el periodo de una simulación (reanálisis, episodio, predicción) y `preparar`, que lanza `viento_periodo` y `respuestas` |
| `simulacion` | `calcular` (la serie del reanálisis, y la hora a hora del olor en cada pueblo y en la peor vivienda: `olor/horas_pueblos.npz`) y `calcular_periodo` (un día, un episodio o una predicción, con su penacho hora a hora), sin lanzar el motor; lo que guarda y su `firma`; las isolíneas rellenas; guardar y cargar un caso («AAAA-MM-DD-nombre», con sus resultados y la operación de los focos) |
| `comparacion` | compara dos escenarios ya simulados del reanálisis, sin volver a calcular: el cambio en % de cada receptor (sin darlo donde los dos casi no llegan), sus isolíneas (en LOCAL/comparacion, o en la `salida` que se le pida: la del informe de la comparación), los pueblos y, del olor, la superficie y los pueblos por encima de 1, 3 y 5 ou_E/m³ de P98 |
| `pueblos` | los pueblos de las tablas y del informe: los núcleos urbanos de CORINE y los que añade la planta en planta.json (los que CORINE no tiene como núcleo, porque no cartografía lo que mide menos de 25 ha); cada uno vale lo que el peor de sus receptores, los de dentro de su mancha urbana o de su contorno (el punto del núcleo, las viviendas y la malla). Lo guardado se pone al día al leerlo (`simulacion.pueblos_al_dia`), sin volver a calcular |
| `serie_respuestas` | las respuestas de todos los días de la serie del reanálisis, comprimidas en la carpeta `dispersion/` de la planta (~56 kB por foco y día); `importar` añade días o rehace un foco; `repetir` llena el resto con copias de unas semanas simuladas (banco de pruebas) y `dia_de_origen` dice de qué día es copia cada uno; es lo que lee `simulacion.calcular` |
| `penacho_mapa`, `viento_mapa` | las imágenes de concentración, su leyenda y el panel del tiempo; el viento en superficie, para la capa del mapa, y el de la celda de la planta hora a hora y por días (`serie_planta`, con su caché en LOCAL, y `resumen_planta`), para el calendario del viento |
| `penacho_3d` | el penacho en 3D: aquí sí se lanza el motor. Calcula y guarda; montar la página es de la interfaz |
| `comprobar` | «Comprobar la herramienta»: mini rutinas que miran que se leen los datos de la planta (carpeta de los cálculos, terreno, edificios, focos, viento 3D y local, estaciones, respuestas) y que responden los servicios de descarga (estaciones, ERA5 y su clave, GFS, MDT, edificios, nombres, fondos del mapa), sin descargar nada; cada resultado, ✓, ⚠ o ✗, al registro. También `python -m teodors.operacion.comprobar [--sin-red]` |
| `respuestas`, `serie_respuestas`, `viento_periodo`, `viento3d_series`, `ejemplo_configuracion`, `viento_local_biblioteca` | tareas por línea de órdenes: `python -m teodors.operacion.<tarea>` |

Necesita `teodors[fuentes]`; el penacho en 3D, también `teodors[penacho_3d]` (pyvista), que se carga al usarlo. Importar estos módulos no lee la planta.

## Uso

```python
from teodors import planta
from teodors.operacion import focos, periodos, planes, simulacion

planta.activar("ruta/de/la/planta")
catalogo = focos.cargar()
plan = planes.nuevo(catalogo, "Volteos por la tarde")
planes.poner_perfil(planes.plan_foco(catalogo["focos"][0], plan), [0], perfil_de_24_factores)
periodo = periodos.nuevo("queja", "2024-07-15", 3)
periodos.preparar(periodo)                                      # descargas, viento y respuestas: lanza procesos
res = simulacion.calcular_periodo(plan, catalogo, periodo)      # DATOS/resultados_planes/queja/20240715_3d/volteos_por_la_tarde/
```

La cuenta, para cada magnitud (el olor, con Q en ou_E/s, y cada gas, con Q en µg/s):

    C(t, r) = Σ_foco Q_foco Σ_h  R_foco[h, H(t), r] · F_foco(te),   te = última vez que fue la hora h

R son las respuestas guardadas, en (g/m³) por g/s; F, el plan por la parte del tiempo si el foco es por eventos. Cambiar un plan o un gas no lanza el motor.

## Códigos de «Comprobar la herramienta»

Cada problema que encuentra `comprobar` tiene un código: con él, quien da soporte sabe qué falla. El panel enseña las categorías y sus códigos; el registro (la actividad), además, el detalle y qué hacer. Esta tabla sale de `comprobar.CODIGOS` (`python -m teodors.operacion.comprobar --codigos`): si se cambia uno, se rehace.

La segunda cifra de un código dice qué le pasa al elemento, igual en todas las categorías: **1** falta; **2** está dañado o no arranca; **3** incompleto o a medias; **5** el servicio no responde; **6** el servicio responde con un error; **7** permiso o clave rechazados; **8** falta la clave.

### INS · Instalación

Elementos (primera cifra): 0 el programa; 1 la carpeta de trabajo; 2 la carpeta local del equipo; 3 la tabla de umbrales de olor (Nagata).

| Código | Gravedad | Qué pasa | Qué hacer |
|---|---|---|---|
| **INS-01** | ✗ fallo | Falta una librería del programa (mapa, geodatos o cálculo) | Reinstalar el programa. |
| **INS-02** | ✗ fallo | La carpeta de la planta pide otra versión del programa | Instalar la versión que pide el fichero VERSION de la planta. |
| **INS-11** | ✗ fallo | No se llega a la carpeta de trabajo (días descargados, cálculos y resultados) | Comprobar la ruta de entrada/rutas.json o la variable de entorno de la planta, y que la unidad esté conectada. |
| **INS-13** | ⚠ aviso | Queda poco espacio en la carpeta de trabajo (menos de 5 GB) | Liberar espacio: un episodio o una predicción ocupan ~1 GB. |
| **INS-17** | ✗ fallo | No se puede escribir en la carpeta de trabajo | Dar permiso de escritura al usuario en esa carpeta. |
| **INS-23** | ⚠ aviso | Queda poco espacio en el disco local (menos de 2 GB) | Liberar espacio en el disco del sistema. |
| **INS-27** | ✗ fallo | No se puede escribir en la carpeta local del equipo (registros y caché) | Dar permiso de escritura o liberar el disco. |
| **INS-31** | ✗ fallo | Falta la tabla de umbrales de olor de Nagata: no se puede pasar la emisión de un gas a olor | Reinstalar el programa. |
| **INS-32** | ✗ fallo | La tabla de umbrales de olor de Nagata está dañada | Reinstalar el programa. |
| **INS-33** | ✗ fallo | La tabla de umbrales de olor de Nagata está incompleta (faltan gases, umbrales o masas molares) | Reinstalar el programa. |

### ENT · Datos de entrada

Elementos (primera cifra): 0 la configuración de la planta; 1 el terreno; 2 los edificios; 3 los focos; 4 los planes; 5 la normativa y los receptores; 6 los recursos de la interfaz.

| Código | Gravedad | Qué pasa | Qué hacer |
|---|---|---|---|
| **ENT-01** | ✗ fallo | Falta un fichero de configuración de la planta en entrada/ | Recuperar la carpeta entrada (reinstalar). |
| **ENT-02** | ✗ fallo | Un fichero de configuración de la planta está dañado | Recuperar la carpeta entrada (reinstalar). |
| **ENT-11** | ✗ fallo | Falta el terreno (elevaciones y usos del suelo) | Volver a descargarlo desde la página Planta, o reinstalar. |
| **ENT-12** | ✗ fallo | El terreno está dañado | Volver a descargarlo desde la página Planta, o reinstalar. |
| **ENT-13** | ⚠ aviso | El terreno tiene zonas sin cota | Volver a descargarlo desde la página Planta. |
| **ENT-21** | ✗ fallo | Faltan los edificios | Volver a descargarlos desde la página Planta, o reinstalar. |
| **ENT-22** | ✗ fallo | Los edificios están dañados | Volver a descargarlos desde la página Planta, o reinstalar. |
| **ENT-31** | ⚠ aviso | No hay focos | Darlos de alta en la ventana de focos (modo de edición). |
| **ENT-32** | ✗ fallo | El fichero de los focos está dañado o es de otra versión | Recuperar entrada/focos.json. |
| **ENT-33** | ✗ fallo | Un foco está incompleto (sin posición o sin emisión) | Completarlo en la ventana de focos (modo de edición). |
| **ENT-42** | ✗ fallo | Un plan de operación guardado no se puede leer | Abrirlo y volver a guardarlo en la ventana de planes, o borrarlo. |
| **ENT-52** | ✗ fallo | La normativa o los receptores con nombre están dañados | Recuperar entrada/normativa.json o entrada/receptores.json. |
| **ENT-61** | ⚠ aviso | Falta un recurso de la interfaz (la ortofoto del visor 3D o el icono) | Recuperar entrada/recursos o entrada/icono. |

### VIE · Viento

Elementos (primera cifra): 0 el viento 3D del reanálisis; 1 el viento alrededor de los edificios; 2 el motor del viento 3D.

| Código | Gravedad | Qué pasa | Qué hacer |
|---|---|---|---|
| **VIE-01** | ✗ fallo | No hay viento 3D del reanálisis | Recuperar la carpeta viento/3d (reinstalar). |
| **VIE-02** | ✗ fallo | Un mes del viento 3D está dañado | Recuperar la carpeta viento/3d (reinstalar). |
| **VIE-03** | ✗ fallo | Faltan meses del viento 3D | Recuperar la carpeta viento/3d (reinstalar). |
| **VIE-11** | ⚠ aviso | Falta el viento alrededor de los edificios: el mapa enseña el viento sin ellos | Recuperar viento/local/viento_local.npz (reinstalar). |
| **VIE-12** | ✗ fallo | El viento alrededor de los edificios está dañado | Recuperar viento/local/viento_local.npz (reinstalar). |
| **VIE-22** | ✗ fallo | El motor del viento 3D no arranca: no se pueden preparar episodios ni predicciones | Reinstalar el programa. |

### DIS · Dispersión

Elementos (primera cifra): 0 las respuestas de los focos; 1 el motor de dispersión; 2 el visor 3D; 3 el informe en PDF.

| Código | Gravedad | Qué pasa | Qué hacer |
|---|---|---|---|
| **DIS-01** | ✗ fallo | Faltan las respuestas de los focos (carpeta dispersion): el reanálisis de un plan no se puede simular | Recuperar la carpeta dispersion (reinstalar) o pedir a soporte que la calcule. |
| **DIS-02** | ✗ fallo | Las respuestas de los focos están dañadas | Recuperar la carpeta dispersion (reinstalar). |
| **DIS-03** | ⚠ aviso | Las respuestas están incompletas o son de prueba: hay focos sin ellas o que han cambiado desde que se calcularon, o son unas semanas repetidas en todos los años | Pedir a soporte que calcule las respuestas de esos focos o, si son de prueba, la serie entera. |
| **DIS-12** | ✗ fallo | El motor de dispersión no arranca | Reinstalar el programa. |
| **DIS-22** | ⚠ aviso | El visor 3D no arranca: falta su librería o una parte de ella | Reinstalar el programa. |
| **DIS-31** | ✗ fallo | Falta el motor del informe en PDF (el navegador de la app o su lector de PDF) | Reinstalar el programa. |
| **DIS-32** | ✗ fallo | El informe en PDF no se puede montar con el último caso guardado | Avisar a soporte con el detalle del registro. |

### MET · Meteorología en línea

Elementos (primera cifra): 0 las estaciones; 1 el reanálisis ERA5; 2 la predicción GFS.

| Código | Gravedad | Qué pasa | Qué hacer |
|---|---|---|---|
| **MET-01** | ⚠ aviso | No hay inventario de estaciones: el mapa no las enseña | Se baja al preparar un episodio; si sigue, avisar a soporte. |
| **MET-05** | ✗ fallo | La web de las estaciones no responde (caída o sin conexión) | Esperar y volver a comprobar; si sigue, avisar a soporte. |
| **MET-06** | ✗ fallo | La web de las estaciones responde con un error (ha cambiado) | Avisar a soporte. |
| **MET-15** | ✗ fallo | El servicio del reanálisis ERA5 (Copernicus) no responde: no se pueden preparar episodios de queja | Esperar y volver a comprobar; si sigue, avisar a soporte. |
| **MET-16** | ✗ fallo | El servicio del reanálisis ERA5 (Copernicus) responde con un error (ha cambiado) | Avisar a soporte. |
| **MET-17** | ✗ fallo | Copernicus rechaza la clave, o falta aceptar la licencia de ERA5 | Revisar la clave y aceptar la licencia de ERA5 con su cuenta en la web de Copernicus. |
| **MET-18** | ✗ fallo | Falta la clave de Copernicus: no se pueden preparar episodios de queja | Poner la clave en el fichero que dice el detalle. |
| **MET-23** | ⚠ aviso | No está la predicción GFS de ayer ni la de anteayer | Volver a comprobar más tarde; si sigue, avisar a soporte. |
| **MET-25** | ✗ fallo | El servicio de la predicción GFS (NOAA) no responde: no se pueden hacer predicciones | Esperar y volver a comprobar; si sigue, avisar a soporte. |

### RED · Conexión

Elementos (primera cifra): 0 internet; 1 las conexiones seguras; 2 los fondos del mapa.

| Código | Gravedad | Qué pasa | Qué hacer |
|---|---|---|---|
| **RED-05** | ✗ fallo | No hay conexión a internet: no responde ningún servicio | Comprobar la red del equipo. |
| **RED-17** | ✗ fallo | Las conexiones seguras fallan (certificados o proxy de la empresa) | Revisar con informática el proxy o los certificados del equipo. |
| **RED-23** | ⚠ aviso | Un fondo del mapa no responde | Usar el otro fondo; si sigue, avisar a soporte. |
| **RED-25** | ✗ fallo | Ningún fondo del mapa responde | Comprobar la conexión; si sigue, avisar a soporte. |

## Los procesos hijos

`periodos._lanzar` lanza `python -m teodors.operacion.<tarea>` con el entorno de `comun.procesos`: el hijo encuentra este mismo teOdors por su camino de Python, la planta por `TEODORS_PLANTA` (la deja `planta.activar`) y los datos por `<prefijo>_DATOS`. No sabe de qué proyecto viene. Sin planta, una tarea responde a `--help` y falla diciendo que no hay ninguna activa.

## De la planta

| De su carpeta | Lo usa |
|---|---|
| `focos.json` | `focos.cargar`, `focos.guardar` |
| `normativa.json` (opcional) | `normativa.ruta`: si no está, manda la plantilla nacional, `normativa_nacional.json` |
| `receptores.json` (opcional) | `simulacion._tabla`, `respuestas.etiquetas` |
| `../dispersion/` (`planta.DIR_DISPERSION`, o `<prefijo>_DISPERSION`) | `serie_respuestas`, `simulacion.calcular`, `simulacion.periodo_reanalisis` |
| `../casos/` (`planta.DIR_CASOS`, o `<prefijo>_CASOS`): `reanalisis/`, `episodios/`, `prediccion/` | `simulacion.dir_guardados`, `carpeta_caso`, `guardar_caso` (cada caso: `AAAA-MM-DD-nombre/resultados` y, a su lado, su informe); `comparacion.escenarios`, `comprobar` (el último caso guardado) |

| De planta.json | Lo usa |
|---|---|
| `proyeccion.zona_horaria` | `planes.zona`: la hora oficial |
| `reanalisis.anios` | `viento3d_series` (el reanálisis, no: su periodo es el de los días de `dispersion/`) |
| `dominio` | `simulacion._rejillas`, `simulacion._tabla` (`radio_edificios_km`), `respuestas`, `penacho_3d` (`zface`) |
| `series.era5`, `series.gfs` | la serie por defecto de `viento_mapa` y `viento3d_series`; la de `viento_periodo` y `respuestas` |
| `series.preferidas`, `series.titulos` | `viento_mapa`: la primera que exista, y el título de su leyenda |
| `series.dia_prueba` | `respuestas` sin `--dia` |
| `series.r1_km`, `series.rmax_km`, `identidad.nombre_casos`, `pronostico.n_col` | `viento_periodo.preparar_caso`: los radios, solo si hay estaciones |
| `estaciones.codigos` | `viento3d_series` |
| `operacion.tipos_foco_extra` | `focos.tipos`: {clave: [nombre, [modelos], funcionamiento]} |
| `operacion.ejemplo` | `ejemplo_configuracion`: relativa a la carpeta de la planta |
| `viento_local.biblioteca` | `viento_mapa.datos_local`: relativa a la carpeta de la planta; sin ella, None |
| `visor3d.semilado_m`, `visor3d.rotulos` | `penacho_3d`: lo que cubre su ortofoto; [{t, lon, lat}], los rótulos que no salen de los receptores |
| `pueblos.lista` | `pueblos.de_la_planta`: [{nombre, contorno}], los pueblos que CORINE no tiene; contorno, sus anillos [[lon, lat], …] en grados. Opcional |

`visor3d.ortofoto` y `visor3d.credito` son de la interfaz, que es quien monta la página. Un valor por defecto `None` se resuelve al llamar.

## Lo que hay que saber

- **El reanálisis cuenta sobre las horas simuladas:** las de los días que hay en `dispersion/` con todos los focos que entran (y, con un plan mensual, solo las de ese mes): la media es la suma entre esas horas y el P98 sale de todas ellas, sin contar con años completos y con huecos si los hay. El primer día cuenta: lo emitido la víspera ya va en sus respuestas. Al añadir días (`serie_respuestas`), el periodo se amplía solo y lo guardado deja de valer (`firma`).
- **La norma cuenta por año civil, en el peor año:** la 19.ª hora más alta de NO₂ frente a 200 y la 25.ª de SO₂ frente a 350, no un percentil de todos los años juntos, que deja pasar 30 horas por encima en uno solo. Cada año, con sus horas simuladas: el resultado dice cuáles están incompletos (`datos.incompletos`). En un periodo de días no se puede contar por año.
- **Las respuestas guardadas llevan un error relativo del 3,5 % como mucho** (`serie_respuestas.ERROR`), y por debajo de 10⁻⁸ s/m³ son cero. El máximo de cada foco y día sale exacto.
- **La plantilla nacional es PRELIMINAR** (RD 102/2011, Anexo I). Si la planta tiene su `normativa.json`, manda el suyo entero, sin mezclar. ⚠️ Es lo que aporta la planta, sin el fondo de la zona: no sirve para declarar que se cumple. El motor no tiene química: los NOx calculados como NO₂ son un tope.
- **De gas a olor con Nagata (2003):** manda la olfatometría y, si no hay, `máx(gas / umbral)` en el foco. ⚠️ Es un índice orientativo, NO son ou_E de la mezcla: no sustituye a la olfatometría ni justifica un criterio en ou_E/m³. El resultado dice qué focos están estimados.
- **Un caudal va a su temperatura:** `caudal_m3_h`, a la de salida; `caudal_Nm3_h`, a 0 °C; `mg/Nm3`, a 0 °C. ⚠️ No se distingue base seca de húmeda ni el O₂ de referencia.
- **Un área va por m²:** `geometria` da q0 = 1 / superficie. Con `respuestas`, un foco emite 1 g/s en total.
- **Los eventos** se reparten en todo el mes (`fraccion_eventos`): dan bien la media, no sus picos.
- **El degradado va de 0,01 a 1000 veces `ref`** (`VMIN`, `DECADAS`: usuario, 2026-11-10; antes, desde 0,1). Cada capa apunta con qué escala se pintó; lo guardado con otra se repinta al abrirlo (`_imagenes_al_dia`, unos segundos la primera vez), sin volver a calcular. Las isolíneas de los gases siguen la misma escala.
- **Los datos no cambian de nombre:** `DATOS/resultados_planes/reanalisis/5_anios/…` (se llame como se llame, tenga los años que tenga), `DATOS/respuestas/…`. `firma` no depende del nombre del plan: lo guardado vale mientras no cambien el plan, los focos, el periodo, los gases de la normativa ni, en el reanálisis, los días de `dispersion/`. La app no lo usa al simular: «Simular» simula siempre, aunque ya esté simulado con lo mismo (usuario, 2026-11-10); lo ya simulado se ve en «Comparar escenarios» y al cargar un caso guardado.
- **El reanálisis va día a día:** lee de cada foco solo los días que entran en el plan y guarda C(t, r) por bloques de receptores, en memoria hasta `EN_MEMORIA_MB` y si no en un fichero temporal de `LOCAL/trabajo/reanalisis` (~2,2 GB por magnitud con 5 años), que se borra al acabar. Con los 13 focos de La Galera y 7 magnitudes, ~0,3 s por día.
- **Sustituir una ruta para probar:** `normativa.RUTA` y `viento_mapa.BIBLIOTECA` mandan si se les pone algo.

⚠️ Heredado, sin cambiar:
- `ejemplo_configuracion.principal` lee `DATOS/resultados_planes/<plan>/` y `res["dia_viento"]`, de antes de las modalidades de simulación: con lo que se guarda hoy, falla.
- Un gas sin límite y sin umbral (NOx o CO, si una planta les quita el límite en su `normativa.json`) da `ref` None en `focos.magnitud`, y las imágenes y la leyenda fallan.
- `viento_periodo.main` guarda el resultado en el `.cmz` del mes de `--dia`: otro día del mismo mes en la misma serie lo sustituye, y un periodo que cruza de mes va entero a ese fichero. `viento_mapa._mes` guarda los meses en memoria: no ve el cambio hasta reiniciar.
- `penacho_3d`: el motor repite el mismo perfil de 24 h en cada cálculo, así que con un plan que cambia de un día a otro las primeras horas llevan lo emitido el anterior como si fuera el de ese día; con una serie de varios años lee el mes entero (hay que recortar el viento), y fuera de ±3 km no hay nada calculado.
- `viento_periodo.preparar_caso` da por hecho que la etiqueta de las horas de una estación es la de inicio (la de Meteocat), y su comentario «Meteocat (5 años)» ya no es cierto: lee los años del periodo.
- `planes.horas_del_plan` mira el mes por el fin de la hora, en hora oficial: un plan de enero se lleva las 2 últimas horas UTC del último año, que ya son enero del siguiente.

## Validación

Pruebas en `auditor/pruebas/unitarias/test_operacion.py`, **sin red** y con una planta y unos focos inventados: media, máximo y P98 frente a una serie hecha a mano; linealidad, suma de focos, «solo el lunes» = 1/7 y mensual constante = diario; la hora oficial con los dos cambios de hora; las conversiones, frente a la ley de los gases ideales; la norma por año civil, frente a series cuyo resultado se sabe de antemano. La cuenta entera, frente a una corrida directa de `dispersion.puffs` con la emisión del plan: viento de `meteo.viento3d` con un GFS inventado, respuestas de verdad, y la suma coincide con el motor.

Comprueban el código: **no dicen nada de ningún resultado.** Viene del proyecto de La Galera y es el mismo función a función, salvo lo que dice el CHANGELOG. `viento_periodo.main` y `periodos.preparar` enteros necesitan red y no se lanzan aquí.
<!-- /manual -->

## Ficheros

| Fichero | Contenido | Viene de | Equivale a |
|---|---|---|---|
| `__init__.py` | La lista de módulos. | — | — |
| `comprobar.py` | Comprobar la herramienta: los datos de la planta y los servicios de descarga. | nuevo (2026-11-07) | — |
| `administrador.py` | El usuario administrador: la huella de su contraseña (PBKDF2 con sal) en `administrador.json` de la planta, la comprobación con espera tras 3 fallos y la línea de órdenes para ponerla. | nuevo (2026-11-08) | — |
| `focos.py` | Focos: tipos, fichero y unidades del modelo. | proyecto La Galera (`gui/focos.py`) | — |
| `edificios_planta.py` | Los edificios de la planta: del Catastro, del LiDAR o dibujados, en `edificios_planta.json`. | nuevo (2026-11-08) | — |
| `estela.py` | Los edificios alrededor de un foco punto y su estela por dirección del viento, calculados con los edificios descargados. | nuevo (2026-11-08) | — |
| `planes.py` | Planes de operación. | proyecto La Galera (`gui/escenarios.py`) | — |
| `normativa.py` | Columnas y estadísticos de cada magnitud. | proyecto La Galera (`gui/normativa.py`) | — |
| `normativa_nacional.json` | Plantilla de límites: RD 102/2011, PRELIMINAR. | proyecto La Galera (`gui/planta/normativa.json`) | — |
| `gases_nagata.json` | Los 223 gases de la tabla 2 de Nagata (2003) con su umbral olfativo (ppm, tal como está impreso), su fórmula y su masa molar (PubChem): el catálogo de `focos.GASES`: no hay más gases (la app es de olores; los de combustión, fuera). Lo comprueba `comprobar` (INS-31/32/33). | nuevo (2026-11-08), del PDF del artículo | — |
| `periodos.py` | El periodo de una simulación y su preparación. | proyecto La Galera (`gui/periodos.py`) | — |
| `simulacion.py` | Del plan y las respuestas a los resultados. | proyecto La Galera (`gui/planes_calculo.py`) | — |
| `comparacion.py` | Comparar dos escenarios ya simulados del reanálisis. | nuevo (2026-11-09) | — |
| `pueblos.py` | Los pueblos y sus receptores. | nuevo (2026-11-10) | — |
| `penacho_mapa.py` | Imágenes de concentración, leyenda y tiempo en la planta. | proyecto La Galera (`gui/penacho_mapa.py`) | — |
| `viento_mapa.py` | Viento en superficie para la capa del mapa. | proyecto La Galera (`gui/viento_mapa.py`) | — |
| `penacho_3d.py` | El penacho en 3D: cálculo y guardado. | proyecto La Galera (`gui/penacho_3d.py`) | — |
| `respuestas.py` | Respuesta de cada foco a una emisión unidad. | proyecto La Galera (`gui/tareas/respuestas_dia.py`) | — |
| `serie_respuestas.py` | Las respuestas de toda la serie, comprimidas, en `dispersion/`. | nuevo en la v0.1.7 | — |
| `viento_periodo.py` | Viento 3D de un periodo. | proyecto La Galera (`gui/tareas/viento_dia_local.py`) | — |
| `viento3d_series.py` | Series de viento 3D de los años del reanálisis. | proyecto La Galera (`gui/tareas/viento3d_series.py`) | — |
| `viento_local_biblioteca.py` | tarea: rehace la biblioteca del viento local de la planta, con su bloque `viento_local` | `meteo.viento_local` | — |
| `ejemplo_configuracion.py` | El ejemplo de la ventana de configuración. | proyecto La Galera (`gui/tareas/ejemplo_configuracion.py`) | — |
| `recursos/iconos/` | Iconos del panel del tiempo (día o noche, cielo, termómetro). | proyecto La Galera (`gui/recursos/iconos/`) | — |
