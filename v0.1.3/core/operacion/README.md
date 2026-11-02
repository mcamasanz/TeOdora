# `teodors.operacion` — la operación de una planta, sin interfaz

<!-- manual -->
## Qué hace

Lleva de los focos y los planes de una planta a lo que dice la norma en cada receptor. No son motores ni equivalen a ningún programa, y no necesitan Qt: la interfaz va encima.

| Módulo | Qué da |
|---|---|
| `focos` | los 15 tipos de foco, ampliables por planta; `focos.json`; de lo que se mide (ppm, mg/Nm³, ou_E/m³, por m²…) a lo que pide el modelo; el olor estimado por el gas dominante; `geometria`: de una ficha a una fuente del motor |
| `planes` | planes diarios, semanales o mensuales de cada foco, en hora oficial; `factores`: la emisión hora a hora, en UTC |
| `normativa` | qué columnas se enseñan de cada magnitud y sus estadísticos: por año civil en el peor año o, en un periodo de días, media, máximo y horas por encima |
| `periodos` | el periodo de una simulación (reanálisis, episodio, predicción) y `preparar`, que lanza `viento_periodo` y `respuestas` |
| `simulacion` | `calcular` (los años del reanálisis) y `calcular_periodo` (un día, un episodio o una predicción, con su penacho hora a hora), sin lanzar el motor; lo que guarda y su `firma` |
| `penacho_mapa`, `viento_mapa` | las imágenes de concentración, su leyenda y el panel del tiempo; el viento en superficie, para la capa del mapa |
| `penacho_3d` | el penacho en 3D: aquí sí se lanza el motor. Calcula y guarda; montar la página es de la interfaz |
| `respuestas`, `viento_periodo`, `viento3d_series`, `ejemplo_configuracion` | tareas por línea de órdenes: `python -m teodors.operacion.<tarea>` |

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

## Los procesos hijos

`periodos._lanzar` lanza `python -m teodors.operacion.<tarea>` con el entorno de `comun.procesos`: el hijo encuentra este mismo teOdors por su camino de Python, la planta por `TEODORS_PLANTA` (la deja `planta.activar`) y los datos por `<prefijo>_DATOS`. No sabe de qué proyecto viene. Sin planta, una tarea responde a `--help` y falla diciendo que no hay ninguna activa.

## De la planta

| De su carpeta | Lo usa |
|---|---|
| `focos.json` | `focos.cargar`, `focos.guardar` |
| `normativa.json` (opcional) | `normativa.ruta`: si no está, manda la plantilla nacional, `normativa_nacional.json` |
| `receptores.json` (opcional) | `simulacion._tabla`, `respuestas.etiquetas` |

| De planta.json | Lo usa |
|---|---|
| `proyeccion.zona_horaria` | `planes.zona`: la hora oficial |
| `reanalisis.anios` | `simulacion.horas_reanalisis`, `viento3d_series` |
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

`visor3d.ortofoto` y `visor3d.credito` son de la interfaz, que es quien monta la página. Un valor por defecto `None` se resuelve al llamar.

## Lo que hay que saber

- **El P98 sale de la serie horaria y sobre horas válidas:** sin el primer día, en el que aún no ha llegado todo, y, con un plan mensual, solo las horas de ese mes.
- **La norma cuenta por año civil, en el peor año:** la 19.ª hora más alta de NO₂ frente a 200 y la 25.ª de SO₂ frente a 350, no un percentil de todos los años juntos, que deja pasar 30 horas por encima en uno solo. En un periodo de días no se puede contar por año.
- **La plantilla nacional es PRELIMINAR** (RD 102/2011, Anexo I). Si la planta tiene su `normativa.json`, manda el suyo entero, sin mezclar. ⚠️ Es lo que aporta la planta, sin el fondo de la zona: no sirve para declarar que se cumple. El motor no tiene química: los NOx calculados como NO₂ son un tope.
- **De gas a olor con Nagata (2003):** manda la olfatometría y, si no hay, `máx(gas / umbral)` en el foco. ⚠️ Es un índice orientativo, NO son ou_E de la mezcla: no sustituye a la olfatometría ni justifica un criterio en ou_E/m³. El resultado dice qué focos están estimados.
- **Un caudal va a su temperatura:** `caudal_m3_h`, a la de salida; `caudal_Nm3_h`, a 0 °C; `mg/Nm3`, a 0 °C. ⚠️ No se distingue base seca de húmeda ni el O₂ de referencia.
- **Un área va por m²:** `geometria` da q0 = 1 / superficie. Con `respuestas`, un foco emite 1 g/s en total.
- **Los eventos** se reparten en todo el mes (`fraccion_eventos`): dan bien la media, no sus picos.
- **Los datos no cambian de nombre:** `DATOS/resultados_planes/reanalisis/5_anios/…` (se llame como se llame, tenga los años que tenga), `DATOS/respuestas/…`, `DATOS/escenarios/…`. `firma` no depende del nombre del plan: lo guardado vale mientras no cambien el plan, los focos, el periodo ni los gases de la normativa.
- **Sustituir una ruta para probar:** `normativa.RUTA` y `viento_mapa.BIBLIOTECA` mandan si se les pone algo.

⚠️ Heredado, sin cambiar:
- `simulacion.calcular` trata las respuestas como periódicas: repite un día de viento en todos los años. Sirve para probar la herramienta, no da resultados. Con una serie de varios años, R cambiará de formato.
- `ejemplo_configuracion.principal` lee `DATOS/resultados_planes/<plan>/` y `res["dia_viento"]`, de antes de las modalidades de simulación: con lo que se guarda hoy, falla.
- Un gas sin límite y sin umbral (NOx o CO, si una planta les quita el límite en su `normativa.json`) da `ref` None en `focos.magnitud`, y las imágenes y la leyenda fallan.
- `viento_periodo.main` guarda el resultado en el `.cmz` del mes de `--dia`: otro día del mismo mes en la misma serie lo sustituye, y un periodo que cruza de mes va entero a ese fichero. `viento_mapa._mes` guarda los meses en memoria: no ve el cambio hasta reiniciar.
- `penacho_3d`: el motor repite el mismo perfil de 24 h en cada cálculo, así que con un plan que cambia de un día a otro las primeras horas llevan lo emitido el anterior como si fuera el de ese día; con una serie de varios años lee el mes entero (hay que recortar el viento), y fuera de ±3 km no hay nada calculado.
- `viento_periodo.preparar_caso` da por hecho que la etiqueta de las horas de una estación es la de inicio (la de Meteocat), y su comentario «Meteocat (5 años)» ya no es cierto: lee los años del periodo.
- `simulacion.calcular` escribe `raiz = carpeta_resultados(esc)` dos veces, sin efecto.
- `planes.horas_del_plan` mira el mes por el fin de la hora, en hora oficial: un plan de enero se lleva las 2 últimas horas UTC del último año, que ya son enero del siguiente.

## Validación

Pruebas en `auditor/pruebas/unitarias/test_operacion.py`, **sin red** y con una planta y unos focos inventados: media, máximo y P98 frente a una serie hecha a mano; linealidad, suma de focos, «solo el lunes» = 1/7 y mensual constante = diario; la hora oficial con los dos cambios de hora; las conversiones, frente a la ley de los gases ideales; la norma por año civil, frente a series cuyo resultado se sabe de antemano. La cuenta entera, frente a una corrida directa de `dispersion.puffs` con la emisión del plan: viento de `meteo.viento3d` con un GFS inventado, respuestas de verdad, y la suma coincide con el motor.

Comprueban el código: **no dicen nada de ningún resultado.** Viene del proyecto de La Galera y es el mismo función a función, salvo lo que dice el CHANGELOG. `viento_periodo.main` y `periodos.preparar` enteros necesitan red y no se lanzan aquí.
<!-- /manual -->

## Ficheros

| Fichero | Contenido | Viene de | Equivale a |
|---|---|---|---|
| `__init__.py` | La lista de módulos. | — | — |
| `focos.py` | Focos: tipos, fichero y unidades del modelo. | proyecto La Galera (`gui/focos.py`) | — |
| `planes.py` | Planes de operación. | proyecto La Galera (`gui/escenarios.py`) | — |
| `normativa.py` | Columnas y estadísticos de cada magnitud. | proyecto La Galera (`gui/normativa.py`) | — |
| `normativa_nacional.json` | Plantilla de límites: RD 102/2011, PRELIMINAR. | proyecto La Galera (`gui/planta/normativa.json`) | — |
| `periodos.py` | El periodo de una simulación y su preparación. | proyecto La Galera (`gui/periodos.py`) | — |
| `simulacion.py` | Del plan y las respuestas a los resultados. | proyecto La Galera (`gui/planes_calculo.py`) | — |
| `penacho_mapa.py` | Imágenes de concentración, leyenda y tiempo en la planta. | proyecto La Galera (`gui/penacho_mapa.py`) | — |
| `viento_mapa.py` | Viento en superficie para la capa del mapa. | proyecto La Galera (`gui/viento_mapa.py`) | — |
| `penacho_3d.py` | El penacho en 3D: cálculo y guardado. | proyecto La Galera (`gui/penacho_3d.py`) | — |
| `respuestas.py` | Respuesta de cada foco a una emisión unidad. | proyecto La Galera (`gui/tareas/respuestas_dia.py`) | — |
| `viento_periodo.py` | Viento 3D de un periodo. | proyecto La Galera (`gui/tareas/viento_dia_local.py`) | — |
| `viento3d_series.py` | Series de viento 3D de los años del reanálisis. | proyecto La Galera (`gui/tareas/viento3d_series.py`) | — |
| `ejemplo_configuracion.py` | El ejemplo de la ventana de configuración. | proyecto La Galera (`gui/tareas/ejemplo_configuracion.py`) | — |
| `recursos/iconos/` | Iconos del panel del tiempo (día o noche, cielo, termómetro). | proyecto La Galera (`gui/recursos/iconos/`) | — |
