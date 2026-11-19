# Historial de versiones

Formato basado en [Keep a Changelog](https://keepachangelog.com/es-ES/1.1.0/); versionado
semántico.

## [0.1.12] — sin publicar

Copia de la **0.1.11** (publicada el 2026-11-18) para la **predicción de 1 a 5 días** (usuario, 2026-11-18: «La versión 12 será añadir el
episodio de predicción de 1-5 días»): como el episodio, pero hacia delante, y con la previsión corregida con lo medido en las estaciones
(usuario, el mismo día, «Previsión corregida»).

### Añadido
- **El viento de la predicción, con la previsión corregida.** En cada estación, el viento de GFS corregido con su MOS, y la temperatura,
  la humedad y la presión de GFS. Donde hay medida (la víspera y lo que va de hoy), manda lo medido. Todo junto entra en el viento 3D como
  si fueran las estaciones (`viento_periodo --prediccion`) y se guarda con la serie (`prevision_estaciones.csv`).
  - Probado con la ejecución del 18/11/2026 a 3 días: 4,3 min, con las 8 estaciones corregidas.
  - En las estaciones, GFS daba 5,82 m/s de media y, corregido, 2,07 m/s. El MOS del sistema en vivo, con los mismos modelos y el archivo
    horario, da 2,08 m/s (0,10 m/s de diferencia media y 5° de dirección).
- `mos.aplicar`, el MOS en una ejecución nueva: `entradas`, `carpeta_modelos`, `cargar`, `corregir` y `horaria`. Sus entradas salen de las
  funciones del entrenamiento. Los modelos entrenados con scikit-learn 1.9.0 dan con la 1.9.1 exactamente lo mismo en sus 330.705 filas
  de validación.
- `operacion.prevision`, la previsión en las estaciones: `en_estaciones`, `completar` (el viento va por parejas: una calma medida no toma la
  dirección prevista), `guardar` y `leer`.
- `fuentes.gfs_noaa.ejecucion(…, extra=True)`: lo que necesita el MOS (`EXTRA`, `EXTRA_MEDIA`, `mensajes`), que es el viento a 100 m y, de la
  nubosidad y de la onda corta, la media del intervalo. Comprobado con la ejecución del 15/12/2025: lo mismo que el archivo con el que se
  entrenó, salvo su redondeo.
- **Los modelos del MOS viajan con la planta**, en `meteo/mos/` (24 ficheros, 2,9 MB), con su índice. Se copian con
  `python -m teodors.operacion.meteo_planta --mos` (`construir_mos`) sin tocar lo demás, y `construir` los incluye si están en la caché.
  La predicción los toma de la planta y, si no, de DATOS/mos/modelos.
- `casos.viento3d.es_temporal` y `SERIES_TEMPORALES`.
- **La predicción en la app, como el episodio pero hacia delante** (usuario, 2026-11-18, al boceto: «Sí»). En Meteo → Predicción hay un
  bloque nuevo (`panel._bloque_prediccion`):
  - los días, de 1 a 5 desde hoy (3 de entrada), y un calendario en el que solo se eligen esos días; se pintan con el viento previsto
    (intensidad y flecha), sin el día de arranque del cálculo;
  - **Simular viento** (descargar, corregir la previsión en las estaciones y simular el viento 3D), **Guardar viento**
    (`casos/prediccion/<primer día>/viento`) y **Cargar viento**;
  - su viento se anima en el mapa con el reproductor, y la rosa de cada estación es la de lo previsto (`metricas.viento.rosas_prevision`);
  - con otros días, el calendario y el mapa se quedan sin ese viento; al volver a sus días, se ve otra vez.

  En Simular, «Simular predicción» calcula al vuelo las respuestas de los focos que falten, como el episodio. Probado en la app, con la
  ejecución del 18/11/2026 a 3 días: el viento en 122 s y la predicción en 231 s, con su penacho, su tabla de pueblos y el aviso al cambiar
  de modo.
- **Las horas del viento en Episodio y Predicción** (usuario, 2026-11-18: «en episodio y predicción cuando las simulas también salen?»,
  y luego «¿puedes avanzar con lo que queda?»). Bajo su calendario salen las barras de cada hora en la planta (la velocidad y su flecha),
  como en Reanálisis, con las del día por el que va el reproductor: cambian de día con la animación, y pinchar una hora lleva el reproductor
  a ella (`panel.franja_ep`, `franja_pred`).
  - En la predicción, pinchar uno de sus días lleva el reproductor a ese día.
  - En el episodio, pinchar un día sigue eligiendo el de la queja.
- **El informe PDF de la predicción** (`writer/prediccion/`, que hasta ahora era un marcador). Es el del episodio pero hacia delante, y se hace
  solo al guardar el caso, como el del episodio. Con 3 días tiene 16 páginas:
  - la portada «predicción del … al …» y lo esencial en futuro, que avisa de que es una previsión: cuanto más lejos, más incierta, y la
    dirección lejos de las estaciones es la de GFS;
  - las rosas de lo previsto en cada estación; la de la planta y sus cifras van solo con sus días, sin el día de arranque;
  - «La meteo prevista frente a lo normal» (`datos._obs_prevision`);
  - «Cuándo se olerá, hora a hora»;
  - **el penacho previsto, una página por día, cada 4 horas**.

  El viento «más frecuente» de lo esencial es el previsto, no el de los años del reanálisis. Probado con la predicción del 18/11/2026: PDF de
  16 páginas en 3 min 40 s, sin una sola mención a episodio, queja, P98 ni reanálisis.
- `periodos.dir_vientos`, `fecha_caso` y `vientos_guardados`. `guardar_viento` y `cargar_viento` sirven para los dos modos, y el
  `viento.json` lleva el modo y la fecha. `preparar_viento` pasa `--prediccion`.

### Cambiado
- **Fuera la caja «Periodo» de la predicción**: los días en un desplegable, «Preparar» (el viento y las respuestas de una vez) y «Ver en el
  mapa». La sustituye el bloque nuevo. «Simular predicción» se activa en cuanto el viento está listo; antes, cuando lo estaban las
  respuestas.
- `writer.informe._carpeta` lleva la predicción a su carpeta, `prediccion`. Antes iba, provisional, a la del episodio.
- Al cerrar la app se cancela también el viento del episodio o de la predicción que esté en marcha. Antes, solo la caja «Preparar».
- Al cancelar el viento de un episodio o de una predicción se oculta también el reproductor. Antes se quedaba con las horas del viento
  anterior.
- **La predicción ya no va sin estaciones** (antes, NOOBS = 2): lleva lo medido y la previsión corregida (NOOBS = 1).
  - Una hora sin temperatura en ninguna estación la toma del modelo (`estaciones.escribir`) en vez de quitar todas las estaciones.
  - Si falla la descarga de una estación, la predicción sigue con su previsión. La altura de su anemómetro sale de la caché, o 10 m.
- **El viento y lo descargado de la predicción van a la carpeta temporal**, como los del episodio, hasta que se guardan
  (`casos.viento3d.dir_serie`).
- El `caso.json` de la predicción lleva `mos` (cuántas estaciones van corregidas) y `medido_hasta`.
- **Los extras `gui` y `gui3d` llevan scikit-learn y joblib** (usuario, 2026-11-19: «Sí, añádela»): la predicción los necesita para abrir
  los modelos del MOS. Sin ellos, quien instalaba la app con pip veía un error al simular el viento de la predicción.

### Corregido
- **El viento «más frecuente» de lo esencial, en el informe del episodio** (usuario, 2026-11-19: «Corrige lo del viento más frecuente en
  el episodio»). Era el de los años del reanálisis; ahora es el que más sopla en la planta en los días del episodio, sin el día de arranque
  (`datos._meteo` → `viento_periodo`), y la frase dice «el viento más frecuente de esos días». Probado con el episodio guardado del
  7/11/2026: sale del ONO (en ese caso coincide con el de los años) y el informe sigue con sus 15 páginas.

## [0.1.11] — 2026-11-18

Copia de la **0.1.10** (publicada el 2026-11-16) con la ficha de la página **Planta** corregida (el núcleo urbano más cercano cuenta
también los pueblos que la planta añade a mano, y la cuarta cifra dice qué rodea la planta) y, en la página **Simular**, una **barra
con iconos encima del mapa** con lo que se ve y cómo; los resultados, **solo del olor**.

### Añadido
- **La barra de encima del mapa** en la página Simular (`gui.barra_mapa`; usuario, 2026-11-17: «variable, isolíneas o degradado, escala
  logarítmica o normal, rango de la escala, transparencia, encuadre a la nave, a la zona intermedia o a la zona completa, copiar imagen
  y guardar imagen»), **con iconos, como la de ParaView** (usuario, el mismo día: «más botones con iconos, estilo paraview»; al ver el
  boceto, «muchísimo mejor»): botones pequeños, solo con su dibujo y, al pasar el ratón, lo que hacen; en grupos separados por una raya
  y, si no caben en una fila, en dos. Sale con lo simulado o la comparación a la vista:
  - **Variable**, en un desplegable: media, máximo o P98 (en el episodio y la predicción, también el penacho hora a hora; en la
    comparación, su cambio);
  - **Isolíneas o degradado** (la comparación, siempre en franjas de %);
  - **Escala** logarítmica o normal y su **rango** (desde, hasta y volver al automático): la media, el máximo y el P98 se repintan de
    su resumen, sin volver a calcular (`simulacion.vista_capa`, en LOCAL/vista_mapa). El penacho hora a hora y el cambio de la
    comparación siguen con su escala;
  - **Paleta de colores** del olor, en un desplegable con su tira: es la de la configuración, así que se queda para la próxima vez
    (también en los informes); el mapa cambia de color sin rehacer nada. Apagada en la comparación, que va con los colores del cambio;
  - **Leyenda**: verla u ocultarla (`mapa.ver_leyenda`, `mapaApp.verLeyenda`). Solo se oculta en Simular; fuera, siempre se ve;
  - **Transparencia**, al momento y sin rehacer nada (`mapa.opacidad_grupo`);
  - **Encuadre**: la nave (1 km), la zona intermedia (10 km) o la completa (todo el dominio);
  - **Copiar** y **Guardar** (la cámara), al final de la barra: la imagen del mapa como se ve, con su leyenda, su escala, un título (lo
    simulado y la variable) y la fecha.
- `ventana_ajustes.SelectorEscala(…, ancho=, alto=)`: la tira de cada escala, del tamaño que se pida (más corta en la barra del mapa).
- **El peor punto de cada pueblo**, en el mapa (usuario, 2026-11-17: en el reanálisis, Santa Bàrbara tiene 3,1 de máximo en la tabla
  pero su marca no sale en rojo con el rango hasta 3). Un pueblo vale lo que el peor de sus receptores (2026-11-10), y ese punto puede
  estar lejos de su marca: en Santa Bàrbara, en el borde que mira a la planta, a 1,1 km de la marca, que da 0,55. Con la media, el
  máximo o el P98 a la vista, un círculo blanco marca el peor punto de cada pueblo, con su valor, el de la tabla
  (`simulacion.peores_puntos`, `mapa.set_peores`, `mapaApp.setPeores`); la ficha del pueblo dice dónde queda desde su marca.
- `simulacion.niveles_rango`, `rango_de_serie`, `rango_automatico`, `columna_capa` y `vista_capa`; `penacho_mapa.pintar(…, lineal=)`,
  `paso_redondo`, `redondo_arriba`, `marcas_rango` y `leyenda_rango`.
- `fuentes.terreno.alrededor` y `RADIO_ALREDEDOR_M` (500 m): el uso del suelo que más hay a menos de ese radio de la planta, con su %.
  `terreno.resumen` lo devuelve como `alrededor`.
- `operacion.pueblos.urbanos`: los núcleos urbanos de CORINE y los pueblos de planta.json juntos, con su nombre si se sabe, el más
  cercano primero.
- Iconos del tema: `arbol` (la ficha de la planta) y, para la barra del mapa, `capas`, `isolineas`, `degradado`, `escala_log`,
  `escala_lineal`, `rango_auto`, `leyenda`, `transparencia`, `encuadre_nave`, `encuadre_intermedia`, `encuadre_completa` y `camara`.

### Cambiado
- **Solo se ven los resultados del olor** (usuario, 2026-11-17: «a partir de la versión v0.1.11 se dejarán de visualizar los resultados
  para diferentes gases, solo se visualizan los resultados de olor»): sin los botones de los gases en los resultados del reanálisis, del
  episodio y de la comparación. Los gases se siguen calculando y guardando como antes (lo de dejar de calcularlos, aparte).
- En el panel de Simular ya no están los botones de la media, el máximo y el P98 ni los de isolíneas o degradado: van en la barra de
  encima del mapa (usuario: «quitar los botones del menú lateral de resultados para cambiar entre variables y ver cómo»). Sus botones
  de capa siguen, ocultos, para llevar cuál está encendida.
- La cuarta cifra de la ficha de la página Planta es **lo que rodea la planta** (en La Galera, «Olivares · rodean la planta · 79 % a
  500 m») en vez de los edificios descargados a 2 km (usuario, 2026-11-16: «prefiero que ponga rodeado de olivares»). Los edificios
  siguen en su sección, «Núcleos y edificios».
- El núcleo urbano más cercano lleva su nombre cuando se sabe (el de la planta o el de la caché de nombres del terreno).
- **En la escala logarítmica, el rango empieza como poco en 0,001** (usuario, 2026-11-17: «para evitar los problemas con el logaritmo…
  si ponen un valor menor se fija a 0.001»). Un «desde» por debajo (también 0 o negativo) ya no se rechaza: se fija en 0,001, la
  casilla lo enseña y una nota lo dice (`BarraMapa.MINIMO_LOG`; en el cálculo, `simulacion.MINIMO_LOG`, el mismo, en `vista_capa`). Las
  casillas del rango, algo más anchas: cabe «0,001».

### Corregido
- **En el programa compilado, los botones de capa del mapa no hacían nada** (usuario, 2026-11-18, con el `.exe` de esta versión: «TypeError:
  `Panel._boton_capa.<locals>.<lambda>() missing 1 required positional argument: 'si'`» al pulsar «Ver usos del suelo» o «Ver edificios»; 32
  veces en el registro del día). Un hueco escrito como `lambda si, c=clave: …` —un argumento obligatorio y otro con valor por defecto, la forma
  de toda la vida de capturar la variable de un bucle— **no sobrevive al compilado**: en el `.exe` (Nuitka + PySide6) Qt no acierta con cuántos
  argumentos pasarle y la llama sin ninguno. En Python nativo funciona igual que siempre, así que no se veía ni en las pruebas. Eran 5 huecos:
  en `panel.py`, los dos del botón de capa, el radio del horizonte meteorológico y el margen de la barra de desplazamiento, y en
  `ventana_focos.py`, el radio de opción. Ahora los crean fábricas (`Panel._capa_nombrada`, `_capa_pulsada`, `_horizonte_pulsado`,
  `panel._margen_con_barra` y `ventana_focos._radio_elegido`): la variable se captura por cierre y la lambda solo declara los argumentos de la
  señal. Comprobado con programas compilados aparte: la fábrica se comporta igual en Python y en el `.exe`, también con señales de dos
  argumentos; `lambda si` a secas y `lambda *a, c=X` también valen, y `lambda si, c=X` no. Una prueba nueva recorre todo el código y falla si el
  patrón vuelve (`test_paquete.huecos_que_rompen_compilados`, con su detector probado en 8 casos).
  ⚠️ **La v0.1.10, publicada y empaquetada para el cliente, tiene los mismos huecos** (4) y no se toca: allí afecta además a las capas de
  resultados del panel (media, máximo y P98 de Simular y de la comparación), que en esta versión las elige la barra de encima del mapa.
- **El núcleo urbano más cercano de la página Planta** solo miraba los núcleos de CORINE: en La Galera daba Santa Bàrbara, a 3,2 km al
  NE, y el más cercano es **La Galera, a 1,4 km al SO**, que CORINE no ve por pequeña y la planta añade a mano (planta.json,
  «pueblos»). El mapa y los informes ya la tenían desde la 0.1.7; la cifra, y el recuento de núcleos urbanos de su sección, no.
- **Las isolíneas con un rango de la barra del mapa** (de hoy mismo): lo que pasaba del rango iba en la última franja, con su color; con
  el rango de 0 a 3 en escala normal salían solo dos franjas, de 1 a 2 y de 2 para arriba, así que 3,1 se veía naranja, como 2,1. Ahora,
  en la escala normal, el rango se parte en 4 a 8 trozos (de 0 a 3, de 0,5 en 0,5), y lo que pasa del rango va en su propia franja, con
  el color del final, y en la leyenda, «más» (`simulacion.niveles_rango`, `_isolineas(…, encima=)`, `_leyenda_isolineas(…, encima=)`).
  La caché de LOCAL/vista_mapa cambia de huella (`_VISTA_FORMATO`): lo pintado antes no se aprovecha.
- **La raya en cuadrado del degradado**, a unos 3 km de la planta (usuario, 2026-11-17: «sí», a arreglarla). El degradado son dos
  imágenes, la de cerca (cada 10 m) y la del resto (cada 100 m) con un hueco para la de cerca, y en el borde se pisaban hasta unos 100 m:
  allí el color salía doble. Ahora el hueco de la del resto es una celda más pequeño (`hueco_img` de `_rejillas`) y la de cerca se recorta
  justo a él tal como queda en su imagen (`penacho_mapa.hueco_mercator`, `pintar(…, solo_en=)`, `simulacion._solo_en`): ni se pisan ni
  dejan hueco. Las isolíneas no cambian: ya encajaban. Los resultados guardados se repintan solos la primera vez que se abren (unos
  segundos; cada capa apunta su «imagen», `_IMAGEN_FORMATO`), y para eso ya no hace falta la carpeta de las respuestas: el centro de sus
  rejillas sale del propio resultado (`_centro_rejillas`). El penacho hora a hora de los episodios ya guardados se queda como estaba: sus
  horas no se guardan.
- **El desplegable de la variable de la barra del mapa** (de hoy mismo): al pasar a una capa que va después en la lista (de «Máximo» a
  «P98») se quedaba en «Ninguna». Al cambiar llegan dos avisos, el de la nueva y luego el de la que se apaga, y la barra solo se rehacía
  con el primero, cuando las dos seguían encendidas (`ventana._capa_en_mapa`).

## [0.1.10] — 2026-11-16

Copia de la **0.1.8** con sus tres fallos corregidos, el **reanálisis acumulando y, con un interruptor, en paralelo** (también el episodio), el informe que ya no se cuelga si cae el motor web del mapa, y la **meteo de los informes en la planta, ya procesada**: un equipo sin la unidad de DATOS
(el del cliente) hace los informes completos, sin ningún fichero meteorológico en bruto y sin conocer la ruta de DATOS. **No hay 0.1.9**: una copia
de trabajo con ese número se descartó sin publicarse, y nada suyo entra aquí salvo que se vuelva a decidir y se rehaga.

### Añadido
- `operacion.meteo_planta` (`python -m teodors.operacion.meteo_planta`): la meteo de los informes, YA PROCESADA, en la carpeta `meteo/` de la planta
  (junto a `entrada/`), calculada una vez desde la caché en el equipo que tiene la meteo en bruto. De los años del reanálisis: `estaciones.json`
  (las estaciones de la zona), `rosas_estaciones.json` (la rosa de cada estación y la del ERA5 en las mismas horas), `tiempo_planta.json` (la media
  de cada día de cada variable en la planta, con su mínimo y su máximo la temperatura y la capa de mezcla, y su resumen) y
  `normales_estaciones.json` (lo normal de cada fecha y hora en las estaciones: el valor de cada año y su mínimo, su mediana, su máximo y su
  media), con su `indice.json` y un `LEEME.md` con el mínimo, la media y el máximo de cada variable. Unos 5 MB en lugar de los 64 MB de la meteo
  en bruto. Nada se descarga; si falta algo en la caché o algún fichero llevara la ruta de DATOS, no se escribe nada.
- `planta.DIR_METEO_PLANTA` (`meteo/`, junto a `entrada/`, o `<prefijo>_METEO`) y `planta.meteo_procesada(nombre)`: un producto, o None si en este
  equipo están todos los ficheros en bruto de los que salió (su lista `de`, relativa a la caché). Los pocos días que se bajan para un episodio no
  bastan para dejarlo. `DIR_METEO`, la caché, no cambia: las descargas van siempre allí.
- `writer.datos.tiempo_planta` y `writer.datos.normales_estaciones` (los productos), `metricas.viento.ficheros_rosas`, y `FUENTE` en
  `fuentes.meteocat` y `fuentes.era5` (cómo se cita cada uno).
- **El reanálisis, acumulando y en paralelo** (`operacion.reanalisis_paralelo`): los estadísticos de cada receptor se ACUMULAN mientras se
  resuelve cada día, así que ya no hace falta la serie hora a hora entera, que con 5 años ocupaba ~18 GB en ficheros temporales. Con
  `paralelo`, los días se reparten además en tramos de meses entre varios procesos.
  - **Las K horas más altas** de cada receptor (para el percentil 98) se ponen al día con un umbral: una hora por debajo de la más baja de las
    K ni se mira.
  - **El percentil** se calcula con la misma cuenta que `np.percentile`, solo con las dos horas que caen en su sitio.
  - **Tiempos** en la planta de trabajo (plan Base, 5 años; con la serie entera, 249-253 s):
    - 1 proceso, 247 s;
    - 2 procesos, 146 s;
    - 4 procesos, 94 s;
    - 8 procesos, 82 s.
  - **Resultados:** en 1 proceso, **idénticos bit a bit** a la serie entera, todo incluido; probado también desde la app. En varios procesos,
    también, salvo las medias, que se suman en otro orden y cambian en la cifra 14-15 (≤ 2·10⁻¹⁴ relativo). El informe sale igual.
  - **Cómo se activa:** `paralelo=False` (1 proceso) es lo que hay por defecto. Se enciende con `operacion.paralelo` en planta.json (true,
    false o cuántos procesos, hasta 8) o con la variable `<prefijo>_PARALELO`.
  - **Memoria:** ~1,5 GB de RAM en 1 proceso y ~1,1 GB por cada proceso más.
- **El episodio, también con el interruptor del paralelo** (`operacion.paralelo`, el mismo del reanálisis):
  - **Las respuestas de los focos** van en tantos procesos como diga: `periodos` le pasa `--procesos N` a `respuestas`. Apagado,
    como siempre: 4.
  - **El penacho hora a hora** (las imágenes de cada rejilla y las isolíneas del olor) se pinta repartido entre esos procesos
    (`operacion.imagenes_paralelo`), con las mismas funciones de `simulacion` y los mismos ficheros, byte a byte.
  - **Tiempos** con el episodio de prueba de 3 días (las respuestas desde cero, los estadísticos y el penacho):
    - sin la interfaz: 467 s apagado y 258 s con 8 procesos;
    - con la app: 807 s apagado y 264 s con 8 procesos.

    Con el interruptor a 1, las respuestas van en un solo proceso y tardan más que apagado (1068 s).
  - **Resultados:** idénticos bit a bit en Python nativo, apagado y con 1, 2, 4 y 8 procesos. Con la app y sin ella sale el mismo
    cálculo y el mismo texto del informe.

### Cambiado
- `simulacion.calcular(esc, catalogo, progreso, cancelado, paralelo=None)` acumula siempre (`reanalisis_paralelo.sumar_serie`); con `paralelo`
  sin dar, el de la planta (`reanalisis_paralelo.de_la_planta`; False, 1 proceso, si no dice nada). **Fuera** `simulacion._sumar_serie`,
  `simulacion._series_en` y `simulacion.EN_MEMORIA_MB`, el cálculo con la serie entera en `trabajo/reanalisis` (lo que dejara un cálculo
  cortado de una versión anterior se sigue borrando al empezar).
- `simulacion.calcular_periodo(esc, catalogo, periodo, progreso, cancelado, paralelo=None)`: con `paralelo` sin dar, el de la
  planta; con más de un proceso, el penacho hora a hora se pinta con `imagenes_paralelo`.
- Sin la meteo en bruto, el informe lee la de la planta: `writer.datos._era5` (el tiempo en la planta), `writer.datos._clima_comparacion` (lo
  normal de esas fechas; lo del episodio es siempre lo medido, con la hora de cada estación que trae la planta), `metricas.viento.rosas_estaciones`
  (las rosas; con `procesada=False`, las calcula siempre) y `fuentes.meteocat.inventario` (las estaciones de la zona, sin pedirlas a la red).
  Comparado en la planta de trabajo, con y sin la meteo en bruto, el informe sale igual, salvo los decimales con los que se guarda lo normal y el
  aire hora a hora.

### Corregido
- **El núcleo no compilaba en Python 3.11** (el mínimo de `requires-python`): f-strings anidadas con las mismas comillas en
  `writer.{episodio,reanalisis_caso,reanalisis_comparacion}.paginas`. Una prueba compila todo el código como 3.11, con un detector que sí las ve.
- **Faltaban los subpaquetes del escritor en `pyproject.toml`** (`teodors.writer.episodio`, `prediccion`, `reanalisis_caso`,
  `reanalisis_comparacion`): una instalación no editable se quedaba sin informes. Una prueba mira que estén todos.
- **En el ejecutable, un motor que lanza otro motor fallaba** (`viento_periodo` → viento 3D, `respuestas` → dispersión: todo el episodio):
  `comun.procesos.orden` tomaba como ejecutable `sys.argv[0]`, que en el hijo ya es el nombre del módulo. Ahora guarda el ejecutable antes.
- `writer.datos._clima_comparacion`: **una hora en calma daba dirección.** Con la velocidad a 0, la media de la hora la dejaba en 0° o en 180°
  según el signo de un cero, y una estación en calma movía la dirección media del episodio (hasta 16° en un episodio de noviembre de 2026). Ahora
  la calma no aporta dirección, ni a lo medido ni a la nube de lo normal, como en las rosas.
- **El informe se quedaba esperando para siempre si el mapa no funcionaba** (KI-40; ya pasaba en la 0.1.8). Si se cerraba el proceso de
  Chromium que pinta el mapa de la ventana oculta, las capturas esperaban 90 s a que el mapa estuviera listo y luego, sin tope, a que
  contestara a su JavaScript. Ahora:
  - `gui.mapa.VistaMapa` apunta el cierre en el registro y dice por qué (`caido()`).
  - Las capturas de los tres informes (`writer.{reanalisis_caso,reanalisis_comparacion,episodio}.capturas`) fallan al momento con ese
    motivo, o si el mapa lleva `ESPERA_JS_S` (120 s) sin contestar.
  - El informe acaba con «No se pudo hacer el informe: …», y la app lo enseña.
  - **Por qué se cerraba:** si la variable del PATH le llega como `PATH` en vez de `Path` (al lanzar desde el Bash de Git, o con un `env=`
    de Python), el Chromium de conda no encuentra sus librerías (0xC0000135). En el ejecutable no pasa, porque su Chromium lleva las
    librerías al lado (comprobado: las pruebas del ejecutable con interfaz se lanzaron así y sus informes salieron enteros).
- **El auditor nunca ejecutaba la prueba del PDF** (KI-41). Lanzaba pytest con la variable del PATH como `PATH` (así la deja
  `os.environ`), el Chromium de conda no arrancaba en los procesos hijos y la prueba se saltaba al prepararse. Ahora `auditor.reglas._pytest`
  la pasa como `Path`, con el mismo valor, y la prueba del PDF también se ejecuta en el auditor (unos 5 s).

## [0.1.8] — 2026-11-14

El modo **episodio**: una queja de olor de unos pocos días. Se define el periodo (víspera · día de la queja · siguiente) y los focos, se simula el
viento 3D de esos días (GFS + estaciones Meteocat), se calcula la dispersión con el penacho hora a hora y se genera un informe propio. El escritor
del informe se reorganiza por tipos (reanálisis-caso, comparación, episodio y predicción) para ajustar cada uno por separado sin descuadrar los
demás, y el informe del episodio compara su meteo con lo normal de esas fechas (de las estaciones Meteocat, 2021-2025, sin depender del CDS).

### Añadido
- `gui`: modo **Episodio** en el panel — definir el periodo y los focos sobre el calendario del viento, con los botones de **Simular / Cargar /
  Guardar** el viento del episodio y **«Simular episodio»** (la dispersión y el penacho). Al guardar el episodio, el informe se hace solo.
- `operacion.viento_periodo`: prepara el viento 3D de unos días sueltos (GFS por día + estaciones Meteocat cercanas, en paralelo). El viento del
  episodio (series «queja_…») es temporal (en `LOCAL/viento3d`) hasta que se guarda a `casos/episodios/<fecha>/viento`.
- `operacion.simulacion.calcular_periodo_preparando` y `operacion.periodos.preparar_respuestas`: la dispersión del episodio (media y máximo) más el
  penacho hora a hora, preparando las respuestas de los focos al vuelo si aún no están.
- `metricas.viento.rosas_periodo`: las rosas del viento de los días del episodio/predicción.
- **Informe de episodio** (`writer.episodio`): portada con la fecha del episodio, meteo de esos días (rosas + situaciones), operación con el
  calendario de los días, resultados con la media y el máximo (sin P98), tabla de pueblos, las páginas del **penacho** (evolución del día de la
  queja, cada 2 h) y **dos páginas nuevas**:
  - *La meteo del episodio frente a lo normal*: cada variable (viento, dirección, temperatura, humedad) hora a hora, con la banda de lo normal de
    2021-2025 y lo medido en el episodio, todo de las estaciones Meteocat (ya descargadas; sin ERA5 ni CDS), más una narrativa automática que lo
    relaciona con la dispersión.
  - *Cuándo se huele, hora a hora del episodio*: por cada pueblo y la peor vivienda, las horas del episodio por encima de 1, 3 y 5 ou_E/m³, su pico y
    cuándo, con mapas de calor día × hora (reconstruido del penacho, sin volver a simular).

### Cambiado
- `writer`: el escritor del informe se divide por tipos (`reanalisis_caso`, `reanalisis_comparacion`, `episodio`, `prediccion`), cada uno con sus
  páginas, textos, gráficos, estilo y capturas, para afinar cada informe por separado. Cada imagen de mapa tiene su alto propio (`ALTOS`) y el tamaño
  de las figuras es determinista (igual en cualquier pantalla ≥ 1920×1080).
- `casos.viento3d` y `casos.gfs_columnas`: el viento y el GFS del episodio van a una carpeta temporal; el del reanálisis/predicción, a la caché de
  DATOS.

## [0.1.7] — 2026-11-10

La 0.1.6 (empezada el 2026-11-06) no llegó a publicarse: lo suyo va en esta.

La serie de viento 3D ya no se para cuando cae la red de estaciones entera. El reanálisis de un plan lee las respuestas de cada día de la serie (comprimidas, en
`dispersion/`) y cuenta sobre las horas simuladas, en vez de repetir un día. El viento 3D y el local viajan con la planta, en `viento/`. La app deja
el menú; la configuración y la ayuda pasan al riel del panel, y una planta puede llevar su icono. El día del reanálisis se elige en un calendario del
viento, siempre abierto, con cada día pintado por su viento en la planta.

### Añadido
- `gui`: `identidad.icono` en planta.json, opcional y relativo a la carpeta de la planta: el icono de la ventana y de la barra de tareas, y la marca de la barra
  superior (`tema.icono_planta`). Sin él, o si no se puede leer, el de siempre: la marca de teOdors en el acento del estilo, y un aviso en el registro.
- `meteo.viento3d.paquete`: la serie de viento 3D de varios años en una carpeta pequeña, para llevarla con la aplicación sin la carpeta de cálculos. Las
  variables grandes (U, V, W y T de las capas, L, u*, altura de mezcla, w*, temperatura, densidad, radiación y humedad) como patrones espaciales fijos
  (POD) y sus coeficientes por hora, más una corrección dispersa donde el error pasaría de la tolerancia: el error máximo queda acotado en todas las
  celdas y horas (0,25 m/s en U y V; L como asinh(L/L0), con un error relativo). Lo demás, tal cual, como en el .cmz. Todo con lzma. Con la serie
  del reanálisis de La Galera (2021-2025, 60 meses): 714 MB, frente a 27 GB de .cmz. Comprobado en concentraciones con 15 días repartidos por los 5
  años (respuestas de los 13 focos con el viento original y con el reconstruido): la media y el P98 de cada receptor, a un 2 % y un 4,5 % típicos.
- `casos.viento3d`: `meses_serie`, `info_mes`, `campo_mes` y `descomprimir_mes` leen un mes del .cmz de DATOS si está y, si no, del paquete de la planta
  (`planta.DIR_VIENTO_PAQUETE`: `viento/3d/` junto a `entrada/`; `planta.DIR_VIENTO`, la carpeta `viento/`, o `<prefijo>_VIENTO`); `construir_paquete` lo hace con los .cmz de una serie. Los usan
  `operacion.viento_mapa`, `respuestas`, `penacho_3d` y `periodos`. `anadir_paquete` (y `paquete.anadir`) le suma los meses nuevos de la serie (otro año)
  con los patrones que ya tiene, sin rehacerlo: el error sigue acotado.
- `operacion.serie_respuestas`: las respuestas de los focos de todos los días de la serie, en la carpeta `dispersion/` de la planta (`planta.DIR_DISPERSION`, o
  `<prefijo>_DISPERSION`): por foco y mes, un fichero; por día, qué valores no son cero y su logaritmo con un byte. Por debajo de 10⁻⁸ s/m³, cero; encima, un
  error relativo del 3,5 % como mucho, y el máximo de cada foco y día, exacto. ~56 kB por foco y día (÷29 frente a los .npz de `respuestas`): con 13 focos,
  5 años en ~1,3 GB. `importar` (y `python -m teodors.operacion.serie_respuestas`) añade días o rehace un foco que ha cambiado (su huella). Con 15 días reales
  y tres planes, la media, el P98 y el máximo de cada receptor a un 0,5 % típico de los de las respuestas sin comprimir.
- `operacion.serie_respuestas.repetir` (y `--repetir DESDE HASTA`): un banco de pruebas de la dispersión del tamaño de la serie de verdad
  (usuario, 2026-11-09: mientras no estén los focos de la planta, unas semanas simuladas con focos ficticios y repetidas en los 5 años, «para
  buscar el método de convertir todos los datos de dispersión, que pesarían mucho, en menos espacio y ser capaces de leer y calcular de
  forma rápida», y aplicarlo luego a los focos de verdad). Cada día que falte, una copia del simulado del mismo día de la semana más cercano
  en el calendario (con una semana por estación, el verano se llena con la de verano); lo que ya estaba no se toca. Copias de verdad: el
  tamaño es lo que se busca (un método que busque parecidos entre días encontrará las copias: se mide con los días simulados). El índice lo
  dice (`repetida`: los días simulados y el periodo; `semanas_repetidas`) y la comprobación lo avisa con DIS-03, que pasa a «incompletas o
  de prueba», para que nadie lo tome por la serie de verdad.
- `preparacion.viento3d.salida.anteponer`: lo contrario de `recortar_arranque`, pone delante de un fichero de viento las horas del periodo
  anterior y corrige la cabecera.
- `simulacion.periodo_reanalisis`: del primer al último día con respuesta de todos los focos, sus horas y huecos, y las horas simuladas de cada año.
- `operacion.viento_mapa`: el viento del nivel 1 en la celda de la planta, hora a hora (`planta_mes`, `serie_planta`), con la procedencia desde el norte
  geográfico (`velocidad_procedencia`, `rumbo`); `serie_planta` lo guarda en LOCAL y solo relee el mes cuyo fichero cambia (la serie de La Galera, 60 meses:
  61 s la primera vez, 0,25 s luego). `resumen_planta`: el periodo (rosa, media, máxima, calmas, dominante) y cada día (media, máxima y su hora, dirección
  media, rumbo dominante, horas de calma). `datos_dia` lleva también las horas en la planta (`planta`). `casos.viento3d.origen_mes`: el .cmz o el .vz de un mes.
- `gui.viento_planta`: el calendario del viento (`CalendarioViento`: un mes, cada día con el color de su viento medio en la planta, en la escala del viento de
  la configuración, y una flecha hacia donde sopla; flechas de mes y menú de años y meses) y las horas del día cargado (`FranjaHoras`: una barra por hora,
  su color y su flecha; marca la hora del reproductor y lleva a la que se pinche).

- `simulacion`: las isolíneas rellenas de cada capa (usuario, 2026-11-09): `_isolineas` saca, de cada rejilla de las imágenes, una franja entre cada
  dos niveles fijos (`niveles_isolineas`) y las líneas de cada nivel, interpolando en logaritmos como las imágenes, en un GeoJSON junto a ellas
  (`<estadístico>_isolineas.json`, menos de 1 MB y 0,1 s por capa con la malla de La Galera). Del olor, `NIVELES_OLOR` («en olores tienes que añadir
  0,01-0,1 y de 0,1-1, 1-3, 3-5 y de 5-10»): 0,01 · 0,1 · 1 · 3 · 5 · 10 · 100 · 1000 ou_E/m³; de un gas, 4 órdenes de magnitud («el color map de 4
  órdenes de magnitud»), un orden por franja en potencias de 10. La última franja, también lo que pasa de ella, como el degradado. Las franjas se
  reparten la escala de color a partes iguales: con el color proporcional al logaritmo, 1-3, 3-5 y 5-10 casi no se distinguirían. La rejilla de la
  zona tiene un hueco donde está la cercana y acaba justo en su borde: no se solapan. Su leyenda, un cuadro por franja con el color de la escala
  elegida y los niveles en los bordes (`_leyenda_isolineas`). `leer_isolineas` las lee. Si las franjas cambian, un resultado guardado rehace sus
  isolíneas de su resumen al leerlo (`_isolineas_al_dia`, unas décimas de segundo), sin volver a calcular la serie.
- `operacion.comparacion`: comparar dos escenarios ya simulados del reanálisis (usuario, 2026-11-09: «la idea es comparar el porcentaje de más o
  de menos debido a un escenario diferente»), sin volver a calcular: con la media, el máximo y el P98 de cada receptor que guarda cada resultado,
  (comparado − referencia) / referencia × 100 (`cambio`), en cada magnitud que tienen los dos. Donde los dos están por debajo del primer nivel de
  sus isolíneas (0,01 ou_E/m³ con el olor) no se da. Isolíneas del cambio en LOCAL/comparacion, azules donde baja y rojas donde sube, en franjas de
  −75 · −50 · −25 · −10 · +10 · +25 · +50 · +75 %, sin color entre ±10 %; los pueblos con los dos valores y el cambio; y, del olor, la superficie y
  los pueblos por encima de 1, 3 y 5 ou_E/m³ de P98 en cada uno. Tienen que ser de las mismas horas y los mismos receptores (si no, dice por qué);
  si los focos o sus emisiones no son los mismos, se compara y se avisa. `escenarios`: los ya simulados, los casos guardados y los de otras carpetas que se abran. Con la Base y
  un plan con las dos balsas de digestato al 50 %, 2 s.
- `simulacion.en_rejilla` y `franjas_geojson`: un campo de los receptores en las rejillas de las imágenes y las franjas y líneas de cualquier campo;
  las usan las isolíneas y la comparación.
- `simulacion._tabla`: cada fila con su `tipo` («nombrado», «vivienda» o «pueblo») y, en el reanálisis (`todos_los_pueblos`), todos los pueblos y no los 10
  más cercanos, uno por nombre: un pueblo en varias partes, con lo peor de ellas y la distancia de la más cercana. `FORMATO_RESULTADO` pasa a 3 (con las
  isolíneas y los pueblos): lo guardado antes se vuelve a calcular.
- `simulacion.guardar_caso` y `cargar_caso`: guardar y cargar un caso (usuario, 2026-11-09: «te pide un nombre que se añade a la fecha, año/mes/día-
  nombre, creándose esa carpeta, donde guardará los resultados y la operabilidad de los focos en una carpeta llamada resultados»; luego, el informe en
  PDF). `carpeta_caso`: «AAAA-MM-DD-nombre» en `resultados_planes/guardados` (`dir_guardados`), sin lo que no puede ir en una carpeta. En su
  «resultados»: resultado.json, la carpeta de cada magnitud (resumen, imágenes e isolíneas), el plan con el que se simuló (plan_operacion.json) y los
  focos (focos.json), si son los de la simulación (su firma) o el caso ya los traía; si no, se dice. Guardar otra vez con el mismo nombre sustituye
  «resultados» y deja lo demás de la carpeta. Se carga tal cual, desde la carpeta del caso o desde su «resultados», con las rutas de sus imágenes e
  isolíneas rehechas: se puede mover o copiar a otro equipo. Lo que no es un caso, o es de otra versión, se dice. `valores` lee los de un caso de su carpeta.
- `gui.mapa`: `set_isolineas`, la capa de isolíneas rellenas (en canvas: las franjas con el color de su centro en la escala de su magnitud, que cambia al
  cambiar de escala, y las líneas encima), y `ocultar_viento`, el viento fuera del mapa y del selector de capas sin olvidar el día ni su forma.
- `writer`, paquete nuevo: el informe en PDF de un caso guardado del reanálisis (usuario, 2026-11-10: «exista un script que lo haga de forma
  automática, dentro de teOdors core en writer»; «por el momento céntrate en PDF de reanálisis»: el de queja y el de predicción, más adelante).
  `python -m teodors.writer CARPETA_DEL_CASO [--html] [--png] [--sin-viento]` deja `<caso>.pdf` en la carpeta del caso. Portada; «Lo esencial del
  caso», con cuatro párrafos que se escriben solos de los datos (`textos.esencial`: qué se simula, los pueblos frente a 1, 3 y 5 ou_E/m³ de P98 con
  una redacción para cada situación, hasta dónde llega el olor y hacia dónde, la vivienda y la zona industrial más expuestas, los gases), las cifras
  clave con el máximo horario bajo el P98, los dos mapas y los pueblos más afectados; y lo que el P98 no dice (usuario, 2026-11-10: «aunque indique
  que el P98 cumple, también se ve que algún día llegó a umbrales de molestia»): los pueblos que pasan de 1, 3 y 5 ou_E/m³ en su peor hora, en
  la casilla de los pueblos y en el texto (con la Base de La Galera, ninguno por el P98, pero 3 en su peor hora, hasta 3,3); relieve y usos del suelo con su texto, sacado del terreno
  descargado (`textos.terreno`; el nombre de los sitios, de la planta: `informe` en planta.json); edificios, pueblos y zonas industriales; los focos
  en 3D, todos y cada uno, y su ficha; la operación de la planta (el año día a día y el día medio, en una rampa cálida estirada entre su mínimo y su
  máximo, y cuatro párrafos que salen de los datos: cómo funciona la planta con el plan, quién emite el olor, cómo entra el plan en el
  cálculo y si el olor de cada foco está medido o estimado por sus gases; usuario, 2026-11-10: «queda espacio por rellenar») y la de cada
  foco (su semana tipo y su año); y la meteorología del reanálisis (usuario, 2026-11-10): la rosa de los vientos de la planta y la de cada
  estación de la zona, con lo que cuentan (de dónde sopla en cada una, sus calmas, dónde hay más viento fuerte y si la más cercana lo ve
  como la planta), y el viento en líneas de corriente, en la zona y de cerca, en las dos situaciones más frecuentes (los dos rumbos que más
  soplan, cada uno con su velocidad típica y en días distintos; usuario: «como queda espacio, pon los dos escenarios más frecuentes y el
  más intenso») y en la más extrema (la hora de más viento), tres filas en una página (las fotos del viento, más apaisadas), con su texto:
  de dónde y con qué fuerza sopla cada una, hacia dónde va el olor y cuál lo diluye antes; con el mapa de las estaciones (usuario: «una
  imagen del mapa con solo los iconos de las estaciones con un buen tamaño y referenciadas a su id»: solas, en grande y con su código, la
  planta y la celda del ERA5) junto a la rosa de la planta, y las de las estaciones con su código; y el tiempo en la planta día a día
  (usuario: «gráficas de los valores medios por día de estos 5 años… de todas las variables del ERA5… y un texto final describiendo toda
  esta meteo»; `datos.clima`, `graficas`: SVG dentro del HTML): el viento de la planta y, del ERA5, temperatura, humedad, nubes, lluvia,
  radiación, presión, velocidad de fricción, calor sensible y capa de mezcla, con un texto final que sale de los datos (el tiempo, el
  viento de día y de noche, la mezcla del aire y las horas más difíciles para el olor: viento flojo, aire estable y capa de mezcla baja,
  y hacia dónde va entonces el olor); y los resultados (usuario, 2026-11-10): el olor en el mapa (la media, el máximo y el P98, en la zona
  y de cerca, apaisados, con hasta dónde llega cada uno por encima de 1, 3 y 5 ou_E/m³ y lo que vale en el pueblo más afectado y en la
  vivienda más expuesta: `datos.alcances`) y cuándo se huele en los pueblos (usuario: «horas al año por encima de 1, 3 y 5 ou_E/m³, por mes y
  por hora del día, y los peores días con su viento»; `datos.horas_pueblos`): cuántas horas y días pasa cada pueblo y la vivienda más
  expuesta de cada umbral, su peor hora, un mapa de calor (mes × hora del día) de los más afectados, los peores días con el viento en la
  planta y el aire (ERA5) de esa hora, y su texto. Con una serie de prueba (semanas repetidas), cada peor día sale una vez por día simulado,
  con el viento del simulado del que se copió, y el informe avisa de que la dispersión es de prueba. Las imágenes salen de la app misma (`capturas`: una ventana principal oculta, los visores 3D
  y las fichas); el HTML pasa a PDF con el motor web de la app (`pdf`), y lo que se sale del pie de una página se aprieta solo antes de imprimir.
  Más de 8 focos siguen en otra página; una imagen que falta deja su hueco con lo que es; un periodo (queja o predicción) se rechaza
  (`datos.NoEsReanalisis`). Con el caso de prueba de La Galera: 13 páginas, ~110 s. `datos`, `textos`, `paginas` y `estilo` no cargan Qt.
- `operacion.comprobar`, «Informe en PDF» (usuario, 2026-11-10: «que el writer funcione también debería ser una de las comprobaciones de la
  herramienta»): mira que está su motor (el navegador de la app y su lector de PDF; si no, DIS-31) y monta, sin imágenes ni viento, el informe del
  último caso guardado (si no puede, o salen menos de 8 páginas, DIS-32 con el error); sin casos guardados, solo el motor. Con el caso de prueba de La Galera, 1,7 s.
- `simulacion.guardar_caso`: en «resultados», también los lugares de los receptores (lugares.json: el centro y las etiquetas de los pueblos y las
  zonas industriales) y los edificios de la planta (edificios_planta.json), para que el informe de un caso no dependa de cómo esté la planta luego.
- `operacion.pueblos`: los pueblos de las tablas, la comparación y el informe (usuario, 2026-11-10: un pueblo a 1,5 km de la planta no salía).
  Eran solo los núcleos urbanos de CORINE, que no cartografía lo que mide menos de 25 ha: un casco pequeño o en trozos le sale como cultivo
  (242, 222). Ahora, también los que la planta añade a mano en planta.json, «pueblos» › «lista»: {nombre, contorno}, con el contorno en
  anillos [[lon, lat], …] (el de su entidad de población de CartoCiudad, simplificado). Cada pueblo, con todos sus receptores: los de dentro
  de su mancha urbana de CORINE o de su contorno (el punto del núcleo, las viviendas del Catastro y la malla). Sin volver a calcular: esos
  receptores ya están en la serie. `simulacion.lugares_al_dia` y `pueblos_al_dia`: un resultado o un caso guardado antes rehace sus tablas
  al leerlo (`pueblos.firma`: cómo se reparten y los de la planta), en décimas de segundo, como las isolíneas; `comparacion.leer`, también.
  En el mapa, su icono, en el centro de su casco (`pueblos.centros`); el tooltip de un pueblo da su fila de la tabla (lo peor de sus receptores).
- El informe de la comparación de dos escenarios del reanálisis (usuario, 2026-11-10: «mantener la estructura del informe de las cosas en
  común (lugar, pueblos, focos, meteo) y comparar la operabilidad entre los dos casos, luego el informe de resultados individual de cada uno
  y por último una página comparativa»): `paginas.InformeComparacion`, `datos.reunir_comparacion`; `python -m teodors.writer A B`, y en la
  app, «Comparar escenarios» › «Informe de la comparación (PDF)», en otro proceso, a `casos/reanalisis/comparaciones/`. Lo común como en
  el de un escenario; la operación de los dos (lo que emite la planta con cada plan, su año y su día medio, cada foco y su cambio, y la
  semana tipo en A y en B de los que cambian) con su texto; los resultados de A y los de B; y la comparación: el cambio del P98 en el mapa,
  la superficie, el alcance y los pueblos por umbral en los dos, los pueblos con su P98, su máximo y sus horas al año en A y en B, y un texto
  final. Con «Base» frente a «Prueba · balsas al 50 %» de La Galera: 15 páginas, ~2,5 min.
- Los casos, en la carpeta de la planta (usuario, 2026-11-10: «una carpeta… que sean casos, con 3 carpetas: reanálisis, episodios y
  predicción»): `planta.DIR_CASOS` (`casos/`, junto a `entrada/`; o `<prefijo>_CASOS`), con `reanalisis/`, `episodios/` y `prediccion/`
  (`planta.CARPETAS_CASOS`, que crea `asegurar_carpetas`); `simulacion.dir_guardados(modo)` y `carpeta_caso(…, modo)`. Al guardar un caso
  del reanálisis, la app hace también su informe en PDF, a su lado (usuario: «se guarda… con los resultados y el informe»), en otro proceso
  (`writer.informe.lanzar`: la app sigue, con el avance en el panel y, al acabar, «abrir el informe»); con la Base de La Galera, ~2 min.
  El hijo hereda el entorno con el camino de Python de la app (abierta con su lanzador, teOdors no está en PYTHONPATH: «No module named
  'teodors'»), puesto solo mientras se lanza.
- `simulacion.calcular`: guarda la hora a hora del olor en cada pueblo (lo peor de sus receptores en cada hora) y en la peor vivienda,
  `olor/horas_pueblos.npz` (usuario, 2026-11-10: para el informe, cuándo y cuánto se huele en cada pueblo), sacada de la serie mientras
  se calculan los estadísticos (sin leerla otra vez); con la Base de La Galera, 39 lugares × 43 824 horas en 267 kB. Lo calculado antes
  vale igual (sin cambiar `FORMATO_RESULTADO`). `serie_respuestas.dia_de_origen`: de qué día simulado es copia un día de una serie de
  prueba (lo que hacía `repetir` por dentro).
### Cambiado
- «Simular» simula siempre, aunque el plan ya esté simulado con lo mismo (usuario, 2026-11-10: «si el usuario pide que lo vuelva a simular,
  lo vuelve a simular»); antes leía lo guardado si seguía valiendo. Lo ya simulado se ve sin calcular en «Comparar escenarios» y al cargar
  un caso guardado.
- El degradado de la media, el máximo y el P98 (y del penacho) empieza en 0,01 y no en 0,1 (usuario, 2026-11-10: «en modo degradado solo
  llega hasta 0,1: reduce a 0,01 el valor mínimo»): `simulacion.VMIN` 0,01 con 5 décadas (hasta 1000, como antes). Lo guardado con la
  escala de antes se repinta solo al abrirlo (`_imagenes_al_dia`), sin volver a calcular; las isolíneas de los gases, desde 0,01 × su
  umbral de olor.
- `simulacion._tabla` (usuario, 2026-11-10: «el peor receptor dentro de su contorno», también en los de CORINE): cada pueblo vale lo que el
  peor de sus receptores, y no lo del punto de su núcleo; su distancia sigue siendo la de su punto. Los valores suben donde la mancha urbana se
  acerca a la planta. En La Galera, con la Base: Santa Bàrbara, de 0,17 a 0,75 ou_E/m³ de P98 (su mancha llega a 2,3 km de la planta; su
  punto está a 3,2 km), y salen La Galera (1,4 km; 0,54), Freginals (0,29) y Godall (0,11); los demás, poco o nada.
- `simulacion.calcular` (el reanálisis): lee las respuestas de CADA día de `serie_respuestas`, no un día repetido en todos los años. Su periodo es el de los
  días que hay con todos los focos que entran (no `reanalisis.anios` de planta.json), con huecos si los hay, y al añadir días se amplía solo; la media, el
  máximo y el P98 salen de las horas simuladas (las del plan, con un plan mensual); la norma de los gases, por año civil con las horas simuladas de cada
  año, y el resultado dice qué años están incompletos (`datos`). El primer día ya cuenta: lo emitido la víspera va en sus respuestas. Va día a día, sin leer
  los días fuera del plan, y guarda la serie en un fichero temporal de LOCAL si no cabe en memoria (~2,2 GB por magnitud con 5 años). La `firma` del
  reanálisis lleva los días de `dispersion/`: al añadir días, lo guardado deja de valer. Se quita `horas_reanalisis`.
- `gui`, Meteorología → Reanálisis (usuario, 2026-11-07: «más manejable a la hora de moverte por el calendario, ya desplegado debajo del día seleccionado, y ver
  en mapa»): «Viento de un día» deja el selector de fecha desplegable por el calendario del viento, siempre abierto, y «Ver el dd/mm/aaaa en el mapa»
  (la fecha, en el botón: sin una línea encima, para que quepan las horas del día cargado). El resumen de cada día sale al pasar por él. Pinchar un día lo
  elige y el doble clic lo abre; con el calendario pinchado, las flechas del teclado mueven el día y la semana, e Intro lo abre. «Un día» de Simulación
  sigue al día elegido. El calendario se pinta en segundo plano al elegir Reanálisis (con su avance la primera vez). Las opciones
  del horizonte van en dos columnas, para que el calendario quepa debajo.
- `gui`: iconos del riel (usuario, 2026-11-07). Focos, un matraz que emite, en vez de una diana («más referido a la química que una localización»); 3D, un
  penacho, en vez de un cubo: una chimenea y sus bocanadas, como los puffs del motor, que crecen y se diluyen al alejarse; Planta, un digestor con su cúpula y un silo, como el icono de la app, en vez de una fábrica.
- `gui`, el emplazamiento, fijo encima de todas las páginas, en poco sitio (usuario, 2026-11-07; de ~200 px a ~95): el nombre y, debajo, las
  coordenadas con un botón para copiarlas, y los botones de ver la planta y toda la zona, con icono; la flecha despliega la latitud, la longitud y el UTM.
- `operacion.comprobar` (y `python -m teodors.operacion.comprobar [--sin-red | --codigos]`): «Comprobar la herramienta» (usuario, 2026-11-07:
  «un control de si todo lo que hace la herramienta funciona», y que cada problema tenga un código «para saber qué le está fallando» al cliente). Mini
  rutinas sobre lo que usa la app instalada, sin descargar nada: el programa (librerías y versión que pide la planta), la carpeta de trabajo y la local
  (se escribe, espacio), `entrada` (configuración, terreno, edificios, focos completos, planes, normativa y receptores, recursos), `viento` (meses del
  viento 3D, leyendo el primero y el último en la planta, y el viento local), `dispersion` (respuestas, y si hay focos sin ellas o que han cambiado),
  los dos motores (arrancan como proceso aparte, como en los episodios y la predicción), el visor 3D, y los servicios en línea de los episodios y la
  predicción (estaciones, ERA5 y si acepta la clave, GFS) y los fondos del mapa. Cada problema, un código de `CODIGOS` (fuente única: panel, registro y
  catálogo): categoría (INS, ENT, VIE, DIS, MET, RED) + elemento + qué le pasa (1 falta, 2 dañado o no arranca, 3 incompleto, 5 el servicio no responde,
  6 responde con un error, 7 clave o permiso rechazados, 8 falta la clave); sin conexión, además RED-05, y con la conexión segura rota, RED-17. El catálogo,
  en el README de `operacion`. Con la planta de La Galera en este equipo: DIS-01 (aún no hay `dispersion/`) y DIS-22 (falta pyvista en el entorno).
- `gui`, Inicio: «Comprobar la herramienta», con su botón (`Panel.comprobar`, que la cancela mientras dura) y una tarjeta por categoría
  (`widgets.TarjetaCategoria`, con su icono) que enseña que se está trabajando en ella hasta que sale bien o mal (usuario, 2026-11-07): en espera, un
  círculo de puntos; comprobándose, se ilumina, su indicador gira (`widgets.Indicador`) y una barra fina cuenta sus pruebas; al acabar, ✓, ⚠ o ✗ y, si
  falla, solo sus códigos en etiquetas de color, sin descripciones. Qué significa cada código, al pasar por encima; el detalle y qué hacer, en la
  actividad, que se abre. La actividad (`gui.consola`) sigue enseñando solo avisos y errores, salvo de la comprobación, de la que lo enseña todo: lo
  que sale bien, en el color del acento («que vaya soltando mensajes positivos o negativos»).
- `gui`: la comprobación de la herramienta se hace sola cada vez que se abre la app (usuario, 2026-11-09: «siempre que se abra la app, que se lleve a
  cabo la comprobación de la herramienta de forma automática»): 2 s después de que la ventana esté a la vista (`VentanaPrincipal.ESPERA_COMPROBAR_MS`),
  en segundo plano, con las tarjetas de Inicio girando como con el botón, que la cancela. Sin abrir la actividad, salvo si algo falla: entonces se abre,
  con el detalle y qué hacer. Si se cierra la app con ella en marcha, se cancela y se espera a que acabe la prueba en curso.
- `comun.procesos`: los motores y las tareas que la app lanza como procesos hijos (viento 3D, geofísica, puffs de las respuestas y del penacho 3D,
  `viento_periodo` y `respuestas` de los episodios y la predicción) arman su orden con `procesos.orden(modulo, …)`: fuera de un ejecutable, la de
  siempre (`python -m …`); compilado (Nuitka o PyInstaller, `procesos.congelado`), el propio .exe con `--teodors-hijo` delante, porque no entiende
  `-m`. El `main.py` de las plantas (y su plantilla, `planta.nueva.MAIN`) lo atiende antes de la interfaz con `procesos.despachar_hijo`, que corre el
  `main()` de ese módulo y sale; compilado, toma la carpeta del .exe como la de la planta. En el ejecutable, `entorno()` no pasa PYTHONPATH. Para el
  instalador de La Galera (usuario y sesión del instalador, 2026-11-07). `comprobar` arranca así los motores (`--motor`), sin `-c`.
- `gui`, página Planta (usuario, 2026-11-07: «mejorar el diseño de este panel», sin quitar los botones de las capas; y «dale una vuelta
  estética»; «una imagen por cada panel de terreno y de usos del suelo»): todo a la vista, sin plegables. Arriba, cuatro cifras con su icono (cota
  de la planta y su uso, terreno, núcleo urbano más cercano, edificios y viviendas a 2 km). Las tarjetas de la elevación y de los usos llevan cada una
  su imagen (`gui.planta_graficos.Miniatura`: el relieve sombreado y los usos del suelo, las mismas imágenes de las capas del mapa, recortadas
  alrededor de la planta, con su marca y una escala). La elevación, en barras finas por franja de
  cota con el color de la capa del mapa y la etiqueta «planta» en la suya (`BarrasCota`); los usos del suelo, en una barra al 100 % (`BarraUsos`) y
  los cinco primeros con su %, y los demás en «Otros», con sus clases al pasar por encima (deja el árbol, que reservaba un hueco vacío); los núcleos,
  en tres cifras con su icono y su color (cuántos y el más cercano), y los edificios de al lado, por uso. Las fechas de descarga, al pasar por encima.
  «Ver elevación», «Ver usos del suelo» y «Ver edificios», como estaban.
- `gui`, página Focos (usuario, 2026-11-07 y 2026-11-08: «imagen del mapa con los focos, y seguido el botón de configuración del foco. Después la
  lista de focos y un calendario igual que el del viento pero con olores y gases, y debajo de él el botón de configuración de la operabilidad»):
  - el plano de los focos con su forma real sobre la ortofoto de la planta («que se vea la imagen satélite y encima los focos») o, sin ella,
    sobre las huellas de sus edificios con una rejilla de 10 m; con escala, el crédito de la ortofoto y cuántos hay de cada modelo
    (`gui.focos_graficos.PlanoFocos`); el nombre de cada foco al pasar por encima;
  - «Ver focos…» (el usuario normal solo los ve, usuario, 2026-11-09; en el modo de edición, «Configurar los focos (…)…»), que abre la ventana de los focos;
  - la lista de los focos con la emisión del olor o del gas elegido en sus botones, de mayor a menor y en el color de su modelo (`BarrasEmision`);
    el foco bajo el ratón se resalta en el plano;
  - el calendario de emisión (`CalendarioEmision`): cada día pintado por la emisión media de la planta con el plan elegido encima (la Base o uno
    guardado), en la escala del olor o de los gases, con su perfil de 24 h en pequeño; las horas del día elegido, en la misma escala de
    color, con lo de cada modelo al pasar por encima (`FranjaEmision`); y «Configurar la operación…», que abre la ventana de los planes.
  Los colores de los modelos, en `focos_graficos.COLORES`, los mismos del plano de la ventana de focos, que los toma de ahí.
- `fuentes.ortofoto` (nuevo): la ortofoto bajo el plano de los focos. Las teselas del primer fondo de la planta que cubren los focos con
  holgura, cosidas y llevadas a la cuadrícula UTM con una afín (sin el giro de la convergencia de meridianos), a 0,25 m; se guarda con la
  planta, en `terreno/ortofoto_focos.jpg` y `.json`, y se pide otra solo si los focos se salen. La ventana la pide en segundo plano la
  primera vez.
- `gui`, página Focos (usuario, 2026-11-08: «la lista también dependerá del plan seleccionado, como en el calendario: que primero salga
  el calendario y luego el total de emisiones»): el calendario, con su plan y lo que se mira (olor o un gas) encima, va antes que la lista;
  la lista («Emisión por foco · d/m/aaaa») da lo que emite cada foco el día elegido en el calendario con ese plan
  (`operacion.planes.emision_focos_dia`).
- `gui.editor_focos` (nuevo): crear o modificar un foco, solo el administrador (usuario, 2026-11-08: «una ventana que le ayude a crear
  geométricamente el foco punto, superficie y volumen en el mapa, además de caracterizarlo; con formas geométricas, rectángulo o círculo,
  obteniendo el área»). A la izquierda, el tipo y el modelo (al crear), las formas que admite el modelo (superficie: rectángulo, círculo
  y polígono; volumen: rectángulo, que fija su largo y su ancho, y punto; punto: punto) y sus medidas (área, lados, radio); en el centro,
  el plano con los demás focos y el que se edita discontinuo (`focos_mapa.VistaFocos.forma` y `borrador`; el círculo, un polígono de 36
  vértices); a la derecha, la ficha con casillas sin la operabilidad. Trabaja sobre una copia; al guardar, el foco queda pendiente de
  simular si cambia lo que fija su respuesta. `focos.pendientes(foco, operacion=False)`: lo que falta sin mirar el funcionamiento.
  El plano de las dos ventanas dice «Cargando el plano…» hasta que está listo (`ventana_focos.PlanoEsperando`).
- `gui.editor_focos`, el punto (usuario, 2026-11-08: «los desplegables son poco atractivos; vamos opción por opción, empezando por el
  punto»): el modelo se elige con tres tarjetas con icono y la actividad con botones (los de ese modelo); al modificar, la suya marcada y
  sin poder cambiarla. La ficha del punto en el editor: el esquema de la chimenea junto a su edificio cercano, a escala, con su altura,
  diámetro, temperatura y velocidad, y un aviso si no sobresale del edificio (`focos_graficos.EsquemaChimenea`); los datos por grupos
  (chimenea; caudal de salida; edificio cercano) y el caudal con un selector «Velocidad / Caudal / Caudal normal» (solo cuenta uno: los
  otros dos se vacían). Lo que obliga a volver a simular, marcado con ⟳ en vez de «recalcula». El plano ya no sale en blanco: encuadraba
  con la vista aún sin tamaño (zoom 0); ahora encuadra cuando la vista tiene tamaño. Los g/s de un gas, con dos cifras significativas
  (antes, «0,0000» o «5e-05»); el desplegable de gases ya no ensancha la ficha.
- `gui.ventana_focos`, para consultar (usuario, 2026-11-08: «la lista de los focos a la izquierda, el mapa en medio y a la derecha la ficha
  que lo describe; debajo de la lista, crear, modificar y eliminar, solo accesibles con el usuario administrador»; «quitar la
  operabilidad»). La lista, con el color de su modelo, su emisión de olor y ⟳ si su dispersión está por calcular
  (`operacion.simulacion.estado_respuestas`: sin respuesta, o modificado desde que se simuló). La ficha (`FichaVista`), solo para
  leer: sus cifras con icono según el modelo, el olor (medido o estimado por Nagata) y sus gases con su olor equivalente, y lo que le
  falta; sin el horario ni los eventos; las observaciones, solo para el administrador. Eliminar guarda en el momento; crear y modificar
  abrirán el editor de focos (geometría en el mapa con rectángulos y círculos, y su ficha), el siguiente paso.
- Dos usuarios, el de la planta y el administrador (usuario, 2026-11-08: «mi idea de terminal es poder hacer diferentes comandos ocultos,
  como el cambio de usuario»; «el comando privado que pide cambiar de usuario de La Galera a usuario de CIRCE, con la contraseña»). La app
  arranca con el de la planta; en su terminal, el comando oculto `_<operacion.modo_edicion>` y la contraseña cambian al administrador (hoy,
  los permisos del antiguo modo de edición: añadir, quitar y cambiar focos) y `_<operacion.usuario>` vuelve; sus nombres, `texto_modo_edicion`
  y `texto_usuario` (en La Galera: `_circe` → CIRCE y `_galera` → La Galera). Los comandos ocultos empiezan por «_» («para que no se
  descubran») y no salen en `ayuda`; también `_clave`. La contraseña no se ve al escribirla, no sale en la terminal ni queda en el historial; se guarda solo su huella
  (PBKDF2-HMAC-SHA256 con sal, en `administrador.json` de la planta; `operacion.administrador`), con espera de 60 s tras 3 fallos.
  Arriba, la marca «Administrador» mientras dura. ⚠️ Ya no abren el modo de edición ni la opción `--<operacion.modo_edicion>` de la línea
  de órdenes ni la variable `<prefijo>_MODO`: lo daban sin contraseña.
- `operacion.focos`: los gases son los 223 de la tabla 2 de Nagata (2003), y ninguno más (usuario, 2026-11-08: «los gases que se
  permiten son los que producen olor, es decir los de Nagata: añade todos los gases del artículo»; «la app se centra en dispersión de
  olores, no de gases de combustión: quítalos»). `gases_nagata.json`: el umbral tal como está impreso (leído del PDF del artículo y
  comprobado fila a fila con la imagen de la tabla), la fórmula y la masa molar de PubChem; las 15 de antes conservan su clave y su
  nombre. El CO y los NOx salen del catálogo y de la plantilla nacional de normativa: un gas que no está en la tabla no cuenta y
  `focos.pendientes` lo dice. ⚠️ Cambia la firma de las simulaciones (incluye la normativa): las guardadas se recalculan.
- `operacion.focos.TIPOS`: sin «Antorcha» ni «Motor de cogeneración o caldera» (usuario, 2026-11-08: «se quitan»), por la misma razón: son focos de
  combustión. Quedan 13 tipos. Un foco guardado con uno de ellos sigue leyéndose, con su clave por nombre de tipo; una planta que los necesite los
  añade en `operacion.tipos_foco_extra`.
- Efecto de los edificios en los focos punto (usuario, 2026-11-08: «que no haya que introducir el edificio para las 36 direcciones, sino que sea el
  propio código, con los edificios descargados, el que configure esa información; como una especie de radar en función de donde localice yo el
  punto»). `operacion.estela`, nuevo: los edificios descargados a menos de 200 m de la chimenea, con la altura del LiDAR de la planta donde llega
  (percentil 90 de lo clasificado como edificio, desde el suelo de alrededor: bajo un tejado no hay suelo) y si no la del Catastro; con
  `terreno.edificios`, el alto, ancho, largo y desplazamientos del edificio que la afecta en las 36 direcciones del vector de flujo (criterio de
  las 5 L) y la altura de buena práctica. Va en el foco (`edificios`; cambia su `huella`: hay que volver a simularlo) y `focos.geometria` lo pasa
  al motor: `preparacion.puffs.control_fuentes` pone el indicador de efecto edificio y el subgrupo 13c, con cavidad (MBDW = 2). Antes el indicador
  iba siempre a 0 y el edificio de la ficha no llegaba al cálculo. Con La Galera, el Catastro daba 24 m a todas las piezas de la planta y 42 m a
  la de al lado; el LiDAR, de 3 a 14 m. El campo `edificio` (nombre y altura escritos a mano) ya no se pide.
- Los edificios de la planta (usuario, 2026-11-08: «poder configurar los edificios vía 3 caminos, Catastro, LiDAR y dibujar/modificar desde el
  usuario de CIRCE, todo en Planta y en el menú de edificios»). `operacion.edificios_planta`, nuevo, en `edificios_planta.json` de la planta:
  del Catastro (sus huellas y su altura, plantas × 3 m), del LiDAR (las huellas del Catastro con la altura de lo que el LiDAR clasifica como
  edificio, fuera las que no ve como tal, y lo que el LiDAR ve y el Catastro no tiene, con su contorno) o dibujados. Traer uno de los dos
  primeros sustituye a lo que viniera de ellos; lo dibujado o tocado a mano se queda. Con edificios propios, la estela de las chimeneas usa
  solo esos; al cambiarlos, se rehace la de los focos punto (`recalcular_focos`). Con La Galera, el Catastro da 14 piezas, casi todas de 24 m;
  el LiDAR, 6: la nave (9,4 m), tres digestores (12 a 14 m), el depósito abierto (6,2 m) y una caseta (2,7 m) que el Catastro no tiene.
  Los importados se llaman por su forma, «Depósito N» lo redondo y «Edificio N» lo demás, del más alto al más bajo; la referencia catastral,
  aparte (`ref`). `gui`, página Planta, «Núcleos y edificios»: cuántos tiene la planta y de qué origen y, para el administrador, «Del Catastro», «Del LiDAR» y
  «Dibujar…» (`gui.editor_edificios`: la lista, el plano con el rectángulo, el círculo y el polígono, y el nombre y la altura, con la del
  LiDAR a un clic). Uno dibujado donde el LiDAR mide menos de 2,5 m (un edificio más bajo o posterior al vuelo: en La Galera, la nave de
  tejado verde al oeste de la nave, 0,2 m) no toma esa altura: 6 m y un aviso para ponerla a mano.
- Los edificios de La Galera, guardados (usuario, 2026-11-08: «son los edificios clave que tienes que guardar, los que saldrán en modo usuario
  Galera»): los 6 del LiDAR y la nave de tejado verde, dibujada (6 m, a falta de su altura).
- `gui.focos_graficos.VisorEdificios`: los edificios de la planta en 3D (usuario, 2026-11-08: «introducir el visor 3D de estos edificios, como
  hicimos para los focos de punto, en el menú de edificios de planta»), con la cámara de `PanelEstela` (ahora en `_Visor3D`, común a los dos:
  arrastrar gira e inclina, el botón derecho desplaza, la rueda acerca, doble clic vuelve); el elegido, en el color del acento y con su nombre;
  al pasar, nombre, altura, área y origen; un clic lo elige. En la página Planta, bajo el resumen, para los dos usuarios; en el editor, bajo la
  ficha, siguiendo cada cambio y eligiendo en la lista al pinchar.
- Guardar los edificios llega a todo en la misma sesión (usuario, 2026-11-08: «si se cambió la altura de un edificio o se añadió, que en la
  misma sesión se actualice en el panel de focos del visor 3D»). Ya se guardaban en la carpeta de la planta (siguen al volver a abrir) y
  rehacían la estela de los focos punto en `focos.json`. Ahora, además, la ventana de los focos relee su lista y su ficha, el editor de focos
  abierto trae esa estela a su copia (si no, guardar el foco la desharía) y recalcula la del suyo en su panel 3D, que sigue mirando igual
  (`Ficha.edificios_cambiados`, `EditorFoco.edificios_cambiados`, `VentanaFocos.edificios_cambiados`), y la página Focos se recarga si
  algún foco ha cambiado de estela.
- Los focos de superficie en el editor (usuario, 2026-11-08: «focos de superficies, desde piscinas, superficies de tanques abiertos;
  también debemos poder verlo en 3D»). Como en AERMOD (AREA, AREACIRC, AREAPOLY) y CALPUFF, una fuente de área: su contorno, su altura de
  emisión y lo que emite por m², sin sobreelevación ni efecto edificio (el motor ya admite polígonos de cualquier número de vértices).
  `operacion.focos`: `superficie.clase` (`CLASES_SUPERFICIE`: balsa o piscina, a ras de suelo; tanque abierto, por su boca; biofiltro, a
  1,5 m y con su olor en ou_E/m³ por el caudal tratado), `clase_superficie`, `es_biofiltro`, `unidad_olor`, y `poner_sobre`: la superficie
  en la boca de un edificio de la planta (`superficie.sobre`), con su contorno y su altura, que le siguen al guardar los edificios
  (`edificios_planta.recalcular_focos`; si el edificio desaparece, se queda como estaba, sin el enlace). Escribir su altura o dibujarla a
  mano la suelta. `gui`: la ficha de una superficie en el editor (`Ficha._superficie_editor`): arriba, en 3D con los edificios de la planta
  (`focos_graficos.PanelSuperficie`: una balsa, hundida con sus taludes; un tanque o un biofiltro, levantado hasta su altura, con la lámina
  en la boca; encima, su área y su olor; con un tanque, un clic en un edificio lo pone en su boca); su clase en tres baldosas; los edificios
  de la planta en botones (lo redondo, delante) y su altura y su área. La cámara de los visores, también con `estado_vista`/`poner_vista`
  comunes: rehacer la ficha no cambia cómo se mira. Un biofiltro, con el grano de su lecho y el aire tratado que sale por toda su
  superficie (flechas); en la ficha, su carga superficial (m³/(m²·h), con la que se dimensiona) y el caudal tratado.
- Los dos primeros focos de superficie de La Galera, guardados (usuario, 2026-11-08: «las dos superficies que has definido pasan a ser
  escenarios fijos de La Galera»): F01, el depósito abierto de digestato, en la boca del Depósito 4 (240 m² a 6,2 m, enlazado), y F02, la
  balsa de digestato, a ras de suelo (1 699 m²). Sin emisión: falta su medida. Después (mismo día), F03, la 2.ª balsa (1 299 m²), y
  F04, el biofiltro (20 × 10 m a 1,5 m; sitio y tamaño de ejemplo, a confirmar en la visita).
  Con valores típicos de bibliografía hasta la visita (usuario, 2026-11-08), con su fuente en las observaciones de cada foco: el
  tanque y las balsas, por lo que emite cada gas por m² (NH₃, H₂S, DMS y DMDS; Zilio et al. 2020, Kupper et al. 2020, Rumsey et
  al. 2014), y su olor por Nagata cuadra con el medido en tanques de digestato y balsas de purín (~19 y ~5 ou_E/(s·m²)); el
  biofiltro, con 97 m³/(m²·h) a 25 °C y H₂S 0,001 ppm (Dorado et al. 2014, Sempere et al. 2015): sin los demás gases a la
  salida, su olor se queda muy corto. Metilmercaptano, p-cresol y los terpenos, sin dato.
- Las superficies se definen por sus gases (usuario, 2026-11-08: «quiero que definas los focos de superficie no por olor sino por gases»),
  como el punto: el olor sale del gas con más veces su umbral (Nagata). `operacion.focos`: lo que emite un gas por m² también en mg/(m²·h)
  y g/(m²·d), como lo da una cámara de flujo (`POR_M2`); `unidades_gas` (las que tienen sentido en cada foco: concentración en un punto,
  por m² en una superficie, las dos en un biofiltro), `unidad_gas` (la de un gas nuevo) y `GASES_TIPICOS` con `poner_gases_tipicos`: los
  de la lámina de digestato (NH₃, H₂S, metilmercaptano, DMS, DMDS y p-cresol) y los de un biofiltro (los mismos de azufre y el NH₃, más
  los terpenos de su lecho). En la ficha, «+ Gases típicos» los añade sin valor. Los cuatro focos de La Galera, con los suyos, sin
  cantidades: son de la planta. La ficha sigue la lógica del punto (usuario, 2026-11-08): los gases con su cantidad, el olor de cada uno y
  el del foco; la olfatometría, opcional, debajo. El caudal tratado de un biofiltro, con su superficie (`salida.caudal_m3_h`, como el de una
  chimenea), no en la olfatometría: con él valen sus gases en ppm o mg/m³. El valor de un gas ya no se aplasta junto a «mg/(m²·h)».
- Una superficie, con su gas de salida como el de un punto (usuario, 2026-11-08: «falta velocidad o caudal por área»; «además de
  temperatura y gases de salida como en el punto»): `salida.caudal_m3_m2_h` (m³/(m²·h), su velocidad en m/h: el aire que la atraviesa, un
  biofiltro, o el que la barre en la medida, la cámara de flujo o el túnel) ⇄ el caudal (m³/h, Nm³/h, kg/h), la temperatura y la
  composición con su densidad (`Ficha._salida_editor(por_m2=True)`, el mismo del punto). Sus gases, en ppm por defecto, como en un punto
  (o por m²), y `pendientes` pide su caudal y su temperatura si van en concentración. En el motor, un área no sube (AERMOD y CALPUFF): el
  caudal y la temperatura pasan la concentración a emisión. Su olfatometría, también en ou_E/m³ por defecto. Los cuatro focos de La
  Galera, así, sin valores.
- Los focos de volumen, con las pilas de compostaje (usuario, 2026-11-08: «pasamos a volúmenes donde añadiremos las pilas de compostaje»).
  Como en AERMOD y CALPUFF: su centro, su altura de emisión (sin dato, la mitad de su alto: `altura_emision`), σz0 = alto/2,15 y σy0 =
  lado/4,3 (un volumen solo) o lado/2,15 (una fila de volúmenes contiguos), sin sobreelevación. `operacion.focos`: `volumen.clase`
  (`CLASES_VOLUMEN`: pila o hilera; nave) y `volumen.seccion` de una pila (`SECCIONES_PILA`: hilera, triangular; meseta, con la cima plana
  y taludes a 45°); `dimensiones.orientacion_deg`, el rumbo de su largo (`rumbo`; sin él, 90, como se dibujaban), y `planta_volumen` (el
  plano la pinta girada); `seccion` y `piel_m2`: una pila emite por su piel (taludes, cima y testeros), no por su planta; `partes_volumen` y
  `fuentes_motor`: una pila alargada va al motor como una fila de volúmenes contiguos de lado cerca de su ancho («F05_01», «F05_02»…, que
  se reparten la emisión y suman su respuesta; `respuestas.fuente` y `penacho_3d` los usan); una nave, un volumen solo. Sus gases típicos
  (`GASES_TIPICOS`: el compost, con sus terpenos; la recepción, con ácidos grasos y fenoles) y su gas de salida, como el de un punto: una
  pila, con su caudal por m² de piel; una nave, con su ventilación. `CAMPOS_RECALCULA`, con «volumen». `gui`: en el editor, el volumen se
  dibuja también con el polígono (su largo, el lado más largo: una hilera girada con cuatro clics); la ficha (`Ficha._volumen_editor`):
  en 3D (`focos_graficos.PanelVolumen`: la pila con su sección y el grano del compost, o la nave; la raya de su altura de emisión y, en el
  suelo, las marcas de su fila de volúmenes; de costado, con su testero a la vista, mientras no se gire a mano), su clase y su sección en
  baldosas, sus medidas y su rumbo, la altura de emisión calculada en gris, lo que emite y su gas de salida.
- La emisión con el viento, en superficies y volúmenes (usuario, 2026-11-08: «tenemos que dejar una correlación en función del viento
  (añádelo en superficies); tenemos que hacer lo mismo para los volúmenes»): `emision_viento` (exponente β y viento de la medida u_ref):
  lo emitido × (u / u_ref)^β, la corrección de lo medido con túnel de viento (`focos.factor_viento`, `VIENTO_EXPONENTE`,
  `VIENTO_REF_M_S`). En la ficha, «Constante» o «Crece con el viento» en baldosas y, con ella, su exponente, el viento de la medida, la
  curva del factor con cada viento (`focos_graficos.CurvaViento`) y el factor con 2, 5 y 10 m/s. Aún no entra en la simulación
  (PENDIENTES §4): la ficha lo dice.
- La emisión con el viento, contrastada con la bibliografía (2026-11-08): la fórmula es la de Regione Lombardia (DGR IX/3018 de 2012,
  §3.5), hora a hora; β = 0,5 vale para una lámina líquida (Bliss et al. 1995; Capelli et al. 2013) y en una pila es experimental (entre
  0 y 0,5); u_ref = 0,3 m/s, la del túnel tipo UNSW; u, la del viento junto a la superficie, no la de 10 m (Lucernoni et al. 2016). Un
  biofiltro, fuente activa, no la lleva: la ficha la desactiva y lo dice. Las hileras de La Galera, con valores de bibliografía hasta la
  visita (α-pineno, limoneno, DMS y metilmercaptano: Jobson y Khosravi 2020; H₂S y DMDS: Jobson 2021; NH₃, sin dato por m²): ~2
  ou_E/(m²·s) por sus gases, entre una hilera madura (0,3) y una fresca (25–29, Miljøstyrelsen 2007).
- Las pilas de compostaje de La Galera (usuario, 2026-11-08: «las pilas van en el campo que está más al norte»; «varias hileras
  paralelas»; «más distribuidas por todo el campo, no solo en el centro»): F05 a F08, cuatro hileras de 40 × 6 × 2,5 m en el campo al
  nordeste de los depósitos, a lo largo de su eje (rumbo 118°), repartidas de punta a punta y a los dos lados; a 1,25 m, 327 m² de piel y 7
  volúmenes en el motor cada una; disposición de ejemplo, a confirmar en la visita.
- La ventana de los focos, para ver (usuario, 2026-11-08: «dentro del panel de ver focos, el listado de los focos creados, su
  visualización en el mapa interactivo y, cuando seleccionas un foco, en el panel derecho las características principales arriba y
  abajo el visor 3D»): `FichaVista`, arriba sus características en tarjetas según el modelo (una superficie: su clase, su área, su
  altura, la boca del edificio en que está; un volumen: su sección o su clase, sus medidas, su piel o su planta, su altura de emisión,
  su rumbo y sus volúmenes en el modelo; los dos: su caudal, su temperatura y su emisión con el viento; un punto, además, hacia dónde
  sale), su emisión y sus gases, con su propia barra; abajo, siempre a la vista, el foco en 3D con los edificios de la planta (el
  visor del editor, para mirar: la chimenea con su estela guardada, la superficie o el volumen).
- Debajo de la lista de la ventana de los focos, todos en 3D con los edificios de la planta (usuario, 2026-11-08: «debajo de la lista
  de focos, el visor 3D con todos los focos ya sería increíble»): `focos_graficos.VisorFocos3D`, con los mismos métodos de dibujo que
  los visores del editor (las balsas hundidas, el tanque en la boca de su depósito, el biofiltro con su aire, las hileras con su sección
  y su grano, las chimeneas); el elegido, perfilado y con su nombre; un clic en uno lo elige en la lista, el mapa y la ficha. Entre la
  lista y el 3D, un divisor que se arrastra. `focos_graficos._solido_volumen`: el sólido de un volumen, para los dos visores.
- La ventana de los focos y la de la operación se abren, cada vez, con la vista de «Ver la planta» (usuario, 2026-11-09): centradas en la
  planta y con su zoom (`mapa_web.ZOOM_PLANTA`, 18, el mismo del botón de la tarjeta de la planta). `focos_mapa.VistaFocos.ver_planta`;
  la vista se queda mientras nadie toque el plano: si cambia de tamaño (la ventana se monta o se arrastra un divisor), vuelve a la planta.
  Antes se encuadraban todos los focos con el plano aún sin su tamaño final, y la planta acababa en una esquina.
- La ventana de la operación, en tres columnas (usuario, 2026-11-09: «quitar el mapa interactivo y aprovechar todo el espacio del medio;
  lo desplazaría debajo de la lista de focos para saber de qué foco hablamos»). A la izquierda, los focos y, debajo, el plano con el
  elegido recuadrado, con todos los focos dentro (`VistaFocos.ver_planta(entera=True)`) y sin la leyenda (los colores van en la lista).
  En el centro, los calendarios de la emisión con el plan abierto, también lo que no se ha guardado, del olor o de un gas (como en la
  página Focos): arriba, el mes (`CalendarioEmision`); debajo, la semana del día elegido como la de Outlook («un calendario tipo
  Outlook con las emisiones de ese foco y las del resto»): `focos_graficos.SemanaEmision`, con la operación del foco elegido como citas
  (las horas seguidas con el mismo %, del color de su modelo, más llenas cuanto más emite; apagado, nada) y, al lado, toda la planta
  hora a hora en la escala del calendario, con la parte del foco delante. A la derecha, los días del plan y el perfil de 24 h, como
  antes. Un día elegido en el mes o en la semana elige el suyo en el plan, y los días con el perfil que se edita salen recuadrados en la
  semana. Se repinta a cada cambio (~0,01 s con La Galera).
- Un foco nace con su operación por defecto (usuario, 2026-11-09: «cada vez que se crea un foco debe crearse una operabilidad por defecto,
  que luego se modifica en la configuración de la operación»): `focos.funcionamiento_defecto`, la de su tipo y, sin tipo (el editor),
  continuo, todo el día al 100 %; el editor se la pone al guardar si no la tiene. La ventana de la operación, si ya estaba hecha, recoge
  los focos guardados (`VentanaPlanes.focos_cambiados`): el nuevo, con la suya; el eliminado, fuera; la Base, rehecha de las fichas.
- Copiar un día del plan y pegarlo en muchos de golpe (usuario, 2026-11-09: «cuando estás configurando la operabilidad en semanal o
  mensual, puedas copiar un día y seleccionar varios para poder pegar todos de golpe»). Ya se podía, con Ctrl+clic, pero no se veía cómo.
  Ahora los días se eligen arrastrando sobre ellos (en el mes, el rectángulo de semanas y días de la semana: de martes a viernes de
  cuatro semanas, de un tirón; `CeldaDia.arrastrada`), con la cabecera de un día de la semana (todos los lunes del mes) o con
  «Laborables», «Fin de semana» y «Todos»; con Ctrl, se suman, y Ctrl+clic sigue sumando o quitando uno. Lo copiado se ve en un
  portapapeles (`ventana_planes.MuestraCopiado`: su perfil en pequeño, su día, su foco y su media) y con el borde discontinuo en su día,
  como en una hoja de cálculo; se queda al cambiar de foco, para pegarlo en otro. El botón dice dónde pega («Pegar en 16 días») y, al
  pegar, «Pegado en 16 días» un momento. Con varios días de perfiles distintos, el rótulo dice cuál se ve. Atajos: Ctrl+C, Ctrl+V y Ctrl+A.
- Copiar la operación entera de un foco a otros del mismo tipo (usuario, 2026-11-09: «copiar una operabilidad de un foco, del mismo tipo, a
  otro: por ejemplo, pila 1 a pila 2»). «Copiar su operación a…», junto al nombre del foco, abre un menú con los otros focos de su tipo, cada
  uno con la operación que tiene ahora, para marcar uno, varios o «Todos» (`ventana_planes.ListaCopiarFoco`; si solo hay otro, ya va marcado);
  el botón dice a cuántos («Copiar a 3 focos») y, al copiar, sale «Copiada a 3 focos» y la lista se pone al día. Sin otro foco de su tipo, el
  botón, apagado. `focos.mismo_tipo`: con tipo los dos, el mismo; si no (los del editor), el mismo modelo y la misma clase (dos pilas, dos
  balsas o dos puntos; no una balsa y un tanque abierto); `focos.nombre_clase`, su nombre corto. `planes.copiar_operacion`: el plan entero
  (diario, semanal o mensual, con sus perfiles), una copia para cada uno.
- `gui.widgets.preguntar_si`: las preguntas de sí o no, con «Sí» y «No» (Qt no trae su traducción y salían «Yes»/«No»): traer los edificios,
  eliminar un foco y cerrar con una descarga en curso.
- `operacion.focos`: `salida.orientacion` de un punto (`ORIENTACIONES`: vertical, sombrerete, horizontal o hacia abajo). Salvo vertical, sin
  impulso en el motor (FMFAC = 0); solo sube por su temperatura.
- `operacion.focos`: la composición del gas de salida de un punto (usuario, 2026-11-08: «para el gas de salida poner CO₂, CO, metano, H₂, etano y
  su composición para calcular la densidad»; «añade O₂ y N₂, no aire»): `salida.composicion`, % en volumen de `GAS_SALIDA` (CO₂, CO, CH₄, H₂,
  C₂H₆, O₂ y N₂), que suman el 100 % (± 1, que se reparte); un foco nuevo empieza con N₂ 79 % y O₂ 21 %, la de un aire de ventilación, que es
  también la de los que no la tienen. `masa_molar_salida`, `densidad_salida` (gas ideal a 1 atm y su temperatura) y el caudal en kg/h
  (`caudal_kg_h`), que pasa a volumen con ella. El motor solo mira la temperatura: recibe la de un aire con la misma densidad
  (`temperatura_equivalente_K`), y un gas más pesado (el CO₂ del upgrading) sube menos o nada (la flotación negativa del motor es cero).
- `gui`, el editor de un foco punto (usuario, 2026-11-08: «un menú atractivo y práctico sin definiciones secundarias»). Arriba, la chimenea y los
  edificios de alrededor en perspectiva (`focos_graficos.PanelEstela`; «combinar el esquema de la chimenea con el radar de edificios, quedando como
  un panel casi tridimensional que ayude a entender los conceptos de la estela»): los edificios con su altura, del gris al color del aviso según la
  de la chimenea; en el suelo, la corona de las 36 procedencias del viento (las que la meten en una estela, en el color del aviso) y, para el viento
  elegido con un clic (al empezar, el peor), su flecha y la zona de influencia del edificio que manda; la chimenea, a escala y con su boca según
  hacia dónde sale, y fantasma hasta la altura a la que saldría libre. Sin humo («ya se entiende»). Las alturas, ×2, con su escala. Se mueve como
  un visor 3D («si pudieras girar y mover el 3D»): arrastrar gira e inclina, el botón derecho (o Mayúsculas) desplaza, la rueda acerca y el doble
  clic vuelve a la vista de partida. Se calcula al marcar la chimenea o cambiar su altura. Moverla no rehace la ficha: el panel sigue como se
  miraba (y la ficha rehecha por otra cosa conserva su vista y el viento elegido a mano), y se actualiza en ~0,05 s; el editor deja hechos al
  abrirse, en segundo plano, los edificios, el LiDAR, la altura de cada huella (`estela.precargar`, ~1,3 s) y el cálculo compilado (medido
  con La Galera: antes, el primer punto tardaba 1,3 s y los demás 0,1 s, y cada uno devolvía la vista a la de partida). Debajo, su altura y diámetro y hacia dónde sale, en
  cuatro tarjetas con icono, y el gas de salida en una fila: temperatura, velocidad ⇄ caudal (m³/h, Nm³/h o kg/h); se escribe uno y el otro sale
  calculado, en gris, con el diámetro, la temperatura y la densidad. Debajo, su composición: un % por componente, la mezcla en una barra
  (`BarraComposicion`: lo que falta hasta el 100 %, rayado; si pasa, en rojo) y su densidad y masa molar. Sin «habrá que simularlo» ni ⟳ en el editor: al guardar un foco se simulará solo.
  La emisión, en todos los modelos del editor: los gases primero, con su masa molar en su fila («una nueva columna que sea el peso molecular»), el
  olor que aporta cada uno por su umbral de Nagata (`OlorGases`, el dominante delante) y el del foco; la olfatometría, opcional, debajo.
  `FichaVista` enseña en cuántas de las 36 direcciones queda en la estela y a qué altura saldría libre.
- `gui.editor_focos`: sin los tipos de catálogo (usuario, 2026-11-08: «actividad solo puede salir si ya hay focos guardados [...] que no se pisen
  los nombres al crear nuevos equipos»). «Actividad» lista los focos ya guardados, de los tres modelos, con el color de su modelo, y marca el que se
  llama como el que se crea; sin ninguno, no sale. Un foco nuevo no tiene tipo (`focos.nuevo(datos, None, modelo)`): su actividad es su nombre, que
  no puede estar vacío ni repetirse (`focos.nombre_repetido`, sin mirar mayúsculas ni espacios). `focos.subtitulo`: «Modelo · F01» si no tiene tipo.
- `operacion.comprobar`: «Comprobar la herramienta» mira la tabla de Nagata, que pasa la emisión de un gas a olor (usuario, 2026-11-08):
  INS-31 falta, INS-32 dañada, INS-33 incompleta. Sin ella el programa arranca (sin gases) y la comprobación lo dice.
- `operacion.planes.emision_dias`: la emisión de toda la planta con un plan, hora a hora en hora oficial, cada día (en ou_E/s o en g/s), con los
  focos por eventos repartidos como en la simulación; `emision_maxima` (todos los focos al 100 %), `dias_calendario` (el mes de un plan mensual o,
  si no, del año pasado al que viene), `indice_dia`, `unidad_emision` y `en_unidad`.
- `gui.viento_planta`: el calendario del viento pasa a ser un `Calendario` general (la rejilla, el mes, el teclado y la elección del día) con
  `color_dia`, `dibujar_dia` y `texto_dia` propios, y una `Leyenda` con su escala; el de la emisión es otro.
- `gui.panel.texto_anios`: el periodo de `dispersion/` («5 años» o «d/m/aaaa – d/m/aaaa» si no son años completos); sin ella, los años de planta.json.
- `planta.DIR_VIENTO_PAQUETE` pasa a `viento/3d/`, dentro de la carpeta `viento/` (`planta.DIR_VIENTO`), que es la de `<prefijo>_VIENTO`.
- `gui`: la app no tiene menú (no aportaba nada). La configuración deja la barra superior (arriba a la derecha) y pasa al riel del panel: «Ajustes»,
  encima de Actividad («Configuración» no cabe en el riel: va en su ayuda). Debajo, «Ayuda» (`Panel.verAyuda`), que abrirá el manual de la app; mientras,
  la versión y las fuentes de datos con sus licencias, el «Acerca de» del menú. En la barra superior queda «Solo mapa». Los atajos siguen, sin menú y con
  el panel oculto: Ctrl+1, 2 y 3 (panel, actividad y terminal), F11, F5, Ctrl+, (configuración), Ctrl+Shift+F (focos) y Ctrl+Shift+P (planes). Con el menú
  se van «Abrir carpeta de datos», «Abrir carpeta de registros» (sigue en la actividad), «Volver a descargar el terreno», «Restablecer disposición» y
  «Salir» (en Windows no tenía atajo; la ventana se cierra con su X).

- `gui`, Simular (usuario, 2026-11-09: «organizar mucho mejor el panel de simular, lo veo poco organizado y algo caótico»). Con el reanálisis, una
  tarjeta con el periodo, el plan y tres botones: «Simular reanálisis» (mientras calcula, «Cancelar», con lo que lleva y lo que queda), «Guardar
  resultados» y «Cargar resultados». Al acabar, debajo, «Resultados»: un botón por magnitud (el olor y cada contaminante), «En el mapa»: media, máximo o
  P98 (sale el P98), en isolíneas rellenas (por defecto) o en degradado, y la tabla de los pueblos (usuario: «los resultados tabulados deben ser de los
  pueblos»): todos, con su distancia, su media, su máximo y su P98, de peor a mejor por el P98 (`BloqueResultado` con `pueblos`). Sin «Un día» ni su
  penacho: son 5 años; el episodio de queja y la predicción simulan su periodo con el mismo botón y siguen con su penacho. En Simular con el reanálisis,
  el viento del día sale del mapa y del selector de capas, y el reproductor se oculta; al volver a Meteo, como estaban.
- `gui`, Simular con el reanálisis: dos modos, «Simular escenario» y «Comparar escenarios» (usuario, 2026-11-09). Al comparar, la referencia y el
  escenario que se compara (cualquiera de los ya simulados o de los casos guardados, o «Abrir otro caso guardado…» de otra carpeta) y «Comparar
  escenarios»; debajo, «Comparación»:
  los dos escenarios y sus avisos, un botón por magnitud, «En el mapa · cambio (%)»: media, máximo o P98, en isolíneas del cambio, la tabla del
  olor por encima de 1, 3 y 5 ou_E/m³ (superficie y pueblos, en cada uno y su cambio) y los pueblos con los dos valores y el cambio, del que más
  cambia al que menos (`TablaCambio`), del estadístico que se ve en el mapa. En el mapa, la comparación o lo simulado, según el modo: nunca los dos.
- `gui`: lo simulado solo se ve en la página de Simular (usuario, 2026-11-09: «si pasas al panel de meteorología los resultados de olores y gases
  desaparecen, para evitar malentendidos de que resultados de 5 años se correspondan con un día del reanálisis»). En las demás, sus capas salen del mapa
  y del selector y las fichas de los núcleos no llevan sus valores; al volver, como estaba (`VentanaPrincipal._resultados_segun_pagina`).
### Corregido
- `comun.procesos.orden`, compilado con Nuitka (usuario, 2026-11-10, para el instalador): `sys.executable` no es el .exe sino un `python.exe`
  dentro de la carpeta del programa que no existe, y los motores no arrancaban (WinError 2; VIE-22 y DIS-12 en la comprobación). Compilado, la
  orden usa el propio .exe, `sys.argv[0]`. Fuera de un ejecutable, la de siempre.
- `operacion.comprobar`, el visor 3D (aviso de galera-66, 2026-11-10): solo miraba que estaba pyvista y daba ✓ aunque faltara VTK, que pyvista
  carga al usarlo; pasó en el ejecutable. Ahora dibuja una superficie de prueba con el código del penacho (`penacho_3d.prueba`: una rejilla sobre
  el terreno y la superficie de un nivel) en otro proceso, como los motores (`--motor visor3d`), para no cargar VTK en la app; si no puede, DIS-22
  («falta su librería o una parte de ella») con el error. Con La Galera, 1,3 s.
- `operacion.simulacion.calcular`: un cálculo de los años del reanálisis cortado a medias (cancelado, con error o con la app cerrada) dejaba
  su serie temporal en `LOCAL/trabajo/reanalisis`: con 5 años y 8 magnitudes, 17 GB. Ahora se borra al cancelar o fallar (cerrando antes los
  ficheros, que Windows no borra abiertos) y, si la app se cerró de golpe, al empezar el siguiente. Lo pesado, en `_sumar_serie`.
- `gui`, el mapa (usuario, 2026-11-09): el penacho y sus capas de media, máximo y P98, menos transparentes (`penacho_mapa.OPACIDAD`, de 0,72
  a 0,85); el viento en blanco, blanco del todo (antes, más transparente cuanto menos viento, y sobre el penacho se veía teñido), y la app
  arranca siempre con él: «Por velocidad», en la configuración, vale hasta cerrarla (`tema._SESION`).
- `operacion.respuestas`: el día 1 de cada mes fallaba («no hay meteorología para …»): el cálculo de un día arranca 18 h antes, y el
  fichero de viento de cada mes solo lleva sus horas (las de arranque se recortan). Ahora, si el arranque cae antes del mes, se pone delante lo
  de la víspera, del fichero del mes anterior (`salida.anteponer`). En la serie de verdad, eran 60 días de cada 5 años sin calcular. Salió
  con el 1 de agosto de 2024 del banco de pruebas de la dispersión.
- `preparacion.viento3d.estaciones.escribir`: en una hora sin temperatura en ninguna estación, la temperatura, la humedad y la presión que no tenga ninguna salen
  de la superficie del modelo (t2m, d2m y sp de `sfc`), la misma en todas, y un aviso dice qué horas. El viento sigue ausente. Antes, `meteo.viento3d` paraba
  con «ninguna estación con temperatura válida en la hora». Pasó con 6 meses de la serie de La Galera (2024-01, 2024-02, 2024-06, 2024-10, 2025-01 y 2025-07): la red
  XEMA de Meteocat no tiene ninguna lectura, de ninguna estación de Cataluña, en tramos de 1 a 19 h (comprobado en su portal el 2026-11-06).
  Las horas con temperatura en alguna estación se escriben igual que antes, byte a byte: los meses ya calculados no cambian. Sin t2m en `sfc` (como en
  `operacion.viento_periodo`, que solo pasa la nubosidad), la hora queda ausente como antes.

### Al pasar una planta a esta versión
Los meses de una serie que fallaron por la caída de la red se recalculan relanzando la serie: salta los que ya tienen su `.cmz`. El reanálisis de un plan
necesita `dispersion/`: las respuestas de los días de la serie (`respuestas` día a día y `serie_respuestas` para empaquetarlas); sin ella dice que aún no
hay respuestas. La biblioteca del viento local puede ir en `viento/local/` (su ruta, `viento_local.biblioteca` de planta.json, relativa a la carpeta de la planta).
El informe en PDF nombra los sitios del relieve y los usos que pone la planta en planta.json, `informe` (`relieve`, `usos`; opcional: sin él,
solo lo que sale del terreno).
Los casos se guardan ahora en `casos/` junto a `entrada/` (`casos/reanalisis/…`); los guardados antes en `DATOS/resultados_planes/guardados`
siguen allí: para verlos en «Comparar escenarios», se copian a `casos/reanalisis/` (o se abren con «Cargar resultados»).
Un caso del reanálisis calculado antes de esta entrada no tiene la hora a hora de sus pueblos (`olor/horas_pueblos.npz`): su informe sale
igual, sin la página de cuándo se huele y con un aviso; para tenerla, se vuelve a calcular (con la Base de La Galera, ~6 min).
Los pueblos que CORINE no tiene como núcleo (un casco de menos de 25 ha, o en trozos) se añaden en planta.json, «pueblos» › «lista»
({nombre, contorno}); los resultados guardados ponen al día sus tablas al leerlos.

## [0.1.5] — 2026-11-02

Los planes de operación pasan a la carpeta de la planta. No hay 0.1.4.

### Cambiado
- `planta`: `DIR_ESCENARIOS` (`DATOS/escenarios`) pasa a ser `DIR_PLANES` (`planes/` en la carpeta de la planta). Un plan lo crea quien opera la planta y no se
  puede recalcular: ahora va con ella, sube al repositorio y no depende de la unidad de datos. Los resultados de simular siguen en DATOS, y su firma no depende de dónde esté el plan.

### Al pasar una planta a esta versión
Mueve a `entrada/planes/` lo que haya en `DATOS/escenarios/`: si no, esos planes dejan de salir en la lista.

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
