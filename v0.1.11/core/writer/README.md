# `teodors.writer` — el informe en PDF de un caso

<!-- manual -->
## Qué hace

Hace solo el informe de un caso guardado del reanálisis («Guardar resultados»: `casos/reanalisis/AAAA-MM-DD-nombre/resultados`). Deja el PDF en la carpeta del caso, con su nombre, al lado de «resultados». La app lo hace sola al guardar un caso (usuario, 2026-11-10), en otro proceso (`informe.lanzar`), con su avance en el panel: la app sigue mientras (~2 min). Las imágenes salen de la propia app (los mapas de una ventana principal oculta, los visores 3D y las fichas de los focos), así que el informe se ve como la app. Por ahora, el de un caso del reanálisis; el de un episodio de queja y el de una predicción, más adelante.

    python -m teodors.writer CARPETA_DEL_CASO [CARPETA_DEL_OTRO] [--planta CARPETA] [--html] [--png] [--sin-viento]

Con dos casos, el informe de su comparación (usuario, 2026-11-10: «mantener la estructura del informe de las cosas en común (lugar, pueblos, focos, meteo) y comparar la operabilidad entre los dos casos, luego el informe de resultados individual de cada uno y por último una página comparativa»): el primero es la referencia (A). Va a `casos/reanalisis/comparaciones/AAAA-MM-DD-A frente a B.pdf`. En la app, «Comparar escenarios» › «Informe de la comparación (PDF)», en otro proceso (~2,5 min).

| Página (comparación) | Qué lleva |
|---|---|
| Portada | los dos escenarios, A y B; de fondo, el cambio del P98 alrededor de la planta |
| 1 · La planta y su entorno, 2 · Focos, 3 · Meteorología | como en el de un escenario (los de A: son los mismos) |
| 2 · La operación | los dos planes (`datos.operacion_comparada`): lo que emite la planta con cada uno, su año día a día con la misma escala, su día medio (`graficas.dia_dos`: A y B, verde y naranja, validados para daltonismo), cada foco con su media en A y en B y el cambio, y su texto (`textos.operacion_comparada`); luego, la semana tipo en A y en B de los focos que cambian |
| 4 · Resultados de A, 5 · Resultados de B | los de un escenario (los mapas del olor y cuándo se huele), de cada uno |
| 6 · Comparación | el cambio del P98 de A a B en el mapa (`comparacion.comparar`), la superficie, el alcance y los pueblos por encima de 1, 3 y 5 ou_E/m³ en los dos, la tabla de los pueblos (P98, máximo y horas al año en A y en B) y el texto final (`textos.comparacion`) |

| Página | Qué lleva |
|---|---|
| Portada | el P98 de olor alrededor de la planta, de fondo; el caso, el plan, las horas, los focos y las magnitudes |
| Lo esencial del caso | cuatro párrafos que se escriben solos: qué se simula y quién emite; los pueblos frente a 1, 3 y 5 ou_E/m³ de P98, con una redacción para cada caso (ninguno, de 1, de 3 o de 5; sin pueblos; sin olor); hasta dónde llega el olor y hacia dónde, la vivienda y la zona industrial más expuestas; los gases. Las cifras clave, con el máximo horario bajo el P98, los dos mapas y los pueblos más afectados |
| 1 · Relieve y usos | sus mapas en la zona y alrededor de la planta, sus barras y su texto, que sale del terreno (dónde está lo alto y el mar, qué usos predominan); el nombre de los sitios lo pone la planta en su planta.json, «informe» |
| 1 · Edificios y lugares | los edificios de la planta (mapa y 3D) y los pueblos y las zonas industriales, de cerca a lejos |
| 2 · Focos y operación | todos los focos en 3D y cada uno; la ficha de cada foco con su imagen; la operación de la planta (el año, día a día, y el día medio, y lo que cuenta: cómo funciona con el plan, quién emite, cómo entra en el cálculo y si el olor está medido o estimado) y la de cada foco (su semana tipo y su año) |
| 3 · Meteorología (el reanálisis) | el mapa de las estaciones de la zona (solas, en grande y con su código, con la planta y la celda del ERA5), la rosa de los vientos de la planta (el viento del reanálisis) y la de cada estación, con su código, y su texto; el viento en líneas de corriente, en la zona y de cerca (con los edificios de la planta), en tres situaciones: las dos más frecuentes (los dos rumbos que más soplan, cada uno con su velocidad típica y en días distintos, `datos.eventos_viento`) y la más extrema (la hora de más viento), con el mapa más apaisado (`estilo.PROPORCION_VIENTO`) para que quepan en una página; y el tiempo en la planta, día a día (`datos.clima`, `graficas.diaria`): el viento de la planta y, del ERA5, temperatura, humedad, nubes, lluvia, radiación, presión, velocidad de fricción, calor sensible y capa de mezcla, con el texto final de la meteorología (el tiempo, el viento de día y de noche, la mezcla del aire y las horas más difíciles para el olor). Sin la serie de viento (`--sin-viento`), no sale; sin el ERA5, sin la última página |
| 4 · Resultados | el olor en el mapa: la media, el máximo y el P98, en la zona y de cerca, con hasta dónde llega cada uno por encima de 1, 3 y 5 ou_E/m³ (`datos.alcances`) y su texto; y cuándo se huele en los pueblos (`datos.horas_pueblos`, de la hora a hora que guarda `simulacion.calcular`): horas y días al año por encima de cada umbral en cada pueblo y en la vivienda más expuesta, un mapa de calor mes × hora del día (`graficas.calor`) de los más afectados, los peores días con el viento en la planta y el aire, y su texto. Un caso calculado antes, sin su hora a hora: sin esta última página, con un aviso |

Lo que no cabe en una página sigue en otra (más de 8 focos), y lo que se pasa del pie se aprieta solo, por niveles, antes de imprimir (`pdf.AJUSTAR_JS`). Una imagen que falta deja su hueco con lo que es.

Comprobar la herramienta (`operacion.comprobar`, DIS-31 y DIS-32) mira que está su motor y monta, sin imágenes, el informe del último caso guardado.
<!-- /manual -->

## Ficheros

| Fichero | Contenido | Viene de | Equivale a |
|---|---|---|---|
| `__init__.py` | La lista de módulos. | nuevo (2026-11-10) | — |
| `__main__.py` | `python -m teodors.writer`. | nuevo (2026-11-10) | — |
| `datos.py` | Lo que necesita el informe, de la carpeta del caso y de la planta (sin Qt); sin la meteo en bruto, de la que trae la planta ya procesada (`tiempo_planta` y `normales_estaciones` la hacen, para `operacion.meteo_planta`). | nuevo (2026-11-10) | — |
| `textos.py` | Los textos que salen solos de los datos: lo esencial del caso, el relieve y los usos (sin Qt). | nuevo (2026-11-10) | — |
| `paginas.py` | Las páginas en HTML, A4 (sin Qt). | nuevo (2026-11-10) | — |
| `estilo.py` | Colores y hoja de estilos (sin Qt). | nuevo (2026-11-10) | — |
| `graficas.py` | Las gráficas en SVG dentro del HTML: una serie diaria de varios años, en línea (con su media de 30 días y su banda), barras o puntos (sin Qt). | nuevo (2026-11-10) | — |
| `capturas.py` | Las imágenes, de la app misma: mapas, visores 3D y fichas (Qt, al usarlo). | nuevo (2026-11-10) | — |
| `pdf.py` | Del HTML al PDF con el motor web de la app, y cada página en PNG (Qt, al usarlo). | nuevo (2026-11-10) | — |
| `informe.py` | Todo junto y la línea de órdenes. | nuevo (2026-11-10) | — |
