# Prueba 07: el penacho en 3D (isosuperficies)

**Pregunta (usuario, 2026-11-01):** ¿cómo se ve el penacho como un volumen de igual concentración sobre el terreno, y cuánto
cuesta? Solo prototipo: nada de esto entra en la app.
⚠️ RECTIFICACIÓN (2026-11-01, pedido del usuario): ya está en la app, en `lib/galera/gui/penacho_3d.py` y `gui/ventana_3d.py` (botón «Ver en 3D» bajo los
resultados de Simular). Lo de abajo sigue siendo la prueba y sus medidas; no se ha tocado. Comprobado de nuevo allí: el suelo frente al penacho de la app, 1,2·10⁻⁷ del máximo.

**Respuesta de la prueba:** se ve bien y cuesta poco: un día entero, unos 10 minutos con 4 procesos en este PC, y la página pesa
3,3 MB. Pero añade poca información: con estos focos, la superficie de 1 ou_E/m³ no pasa de 20-75 m de altura en 0,6-3 km de
largo, así que a escala real es una mancha casi plana y hay que exagerar la vertical para ver el volumen. Desde arriba es lo mismo que el mapa
2D. Lo que sí se aprecia mejor es lo pegado al suelo que va el olor y la diferencia entre el día y la noche.

⚠️ Los focos son de EJEMPLO y el viento es el de un solo día: la forma no es un resultado de la planta.

**Abrir:** [`penacho_3d.html`](penacho_3d.html), un solo fichero que funciona sin internet. Hora, exageración vertical, niveles,
animación; girar con el botón izquierdo, acercar con la rueda.

## Qué se hizo
- **Plan Base** (12 focos; la antorcha no tiene emisión), de una copia fija del commit `f1cfddb` (`focos_f1cfddb.*`,
  `control_f1cfddb.py`), con la serie `odora_gfs_8est` del 21-oct-2026. Una sola corrida de `odora puffs` con la emisión
  total, sin superposición.
- **Receptores en altura.** El motor los admite (x, y, cota, altura), pero `odora.preparacion.puffs.control` fija la altura a 0: `comun.py`
  reescribe esas líneas del control, sin tocar odora.
- **Dos pasadas.** La primera (`calcular.py`) es la malla pedida, ±3 km cada 100 m y 15 alturas (0, 2, 5, 10, 20, 35, 50, 75, 100,
  150, 200, 300, 400, 600, 800 m). Con 100 m, un penacho estrecho en diagonal sale a dientes de sierra, porque los nudos lo cogen a ratos.
  Por eso hay una segunda (`afinar.py`): cada 25 m, pero solo donde la primera ve más de 0,3 ou_E/m³ (con 200 m de margen y ±400 m
  alrededor de la planta), hora a hora, arrancando 2 horas antes. Son 27 000-81 000 receptores en vez de 871 815.
- **Superficies** (`mallas.py`): 1, 3 y 5 ou_E/m³ sobre el logaritmo de C, en una rejilla que sigue el terreno, con vtk.
- **Vista** (`plantilla.html`, `empaquetar.py`): three.js r147 (MIT), relieve del MDT cada 50 m y una ortofoto PNOA de ±3,2 km (IGN, CC BY 4.0),
  todo dentro del HTML.

## Coste medido (i7-1255U, 4 procesos, con otra sesión trabajando a la vez en el PC)
| Paso | Receptores × periodos | Tiempo | Memoria por proceso |
|---|---|---|---|
| Solo suelo, 100 m (referencia) | 3 721 × 42 | 29 s | 421 MB |
| 3D, 100 m, todo el día con su arranque | 55 815 × 42 | **181 s** | 426 MB |
| 3D, 25 m, una hora | 27 000-81 000 × 3 | 9-55 s (media 16,5) | 427 MB |
| 3D, 25 m, las 24 horas | | **396 s** | 427 MB |
| Isosuperficies, 24 h × 3 niveles | 136 886 triángulos | 1,7 s | |

- **Día entero a 25 m: 181 + 396 s ≈ 10 min.** El de 100 m solo, 3 min, pero con dientes de sierra.
- **La memoria es casi toda del viento** (48 h cargadas): apenas cambia con los receptores. En total, unos 1,7 GB.
- **Frente a la estimación previa** (~1,5 min, con 55 µs por receptor y hora): quedaba corta. Aquella medida era de una sola fuente y no contaba el
  arranque. Lo medido sale de ~278 µs de un proceso por receptor y periodo con 12 fuentes, unos 23 µs por fuente, más ~25 s fijos.
- **Tamaños:** página 3,30 MB (librería 0,63, ortofoto 0,91, mallas 1,74). Concentraciones comprimidas: 1,2 MB a 100 m y 3,1 MB a 25 m.

## Validación
1. **El suelo de la corrida en altura = una corrida solo en el suelo:** los 156 282 valores (3 721 nudos × 42 periodos) iguales bit
   a bit. Añadir alturas no cambia nada, como debe ser: los receptores son independientes.
2. **Frente al penacho del plan Base de la app** (superposición de respuestas, otro camino): 3 721 nudos × 24 h, diferencia máxima 7,6·10⁻⁶
   sobre un máximo de 64,7 ou_E/m³ (1,2·10⁻⁷), correlación 1,0.
3. **Balance de masa con las alturas** (`balance.py`, biofiltro con 1 g/s constante, caja de ±1,5 km, 7 200 receptores en las
   paredes hasta 2 000 m): lo que sale por las paredes frente a lo que se emite, en las últimas 24 h.
   | Viento usado en cada altura | Salida / emisión, media | Hora a hora |
   |---|---|---|
   | El de esa altura | 1,067 | 0,98-1,17 |
   | El que el motor le da al puff (media en [0, σz]) | **1,000** | 0,95-1,06 |
   Con el viento de cada altura sobra un 7 %, sobre todo de noche, cuando el viento cambia más con la altura: el motor mueve el
   puff entero con un solo viento. No es una medida independiente de la física, porque el motor conserva la masa por construcción: lo que
   comprueba es que la concentración EN ALTURA está bien repartida y colocada. Si las alturas estuvieran mal, esto no cerraría.
4. **Forma del perfil** (`perfil_vertical.py`): C(z) ajusta a una gaussiana con reflexión en el suelo (R² ≥ 0,9997), pero es la fórmula del motor
   y no prueba nada por sí sola. Su anchura, en el balance, frente a la curva de la clase de estabilidad a 1,5-2 km: clase C 109-122 m
   frente a 112-119 m, clase D 47-54 m frente a 43-52 m. ⚠️ Clase F: 22-34 m frente a 18-20 m, sin explicar; puede venir de la clase
   de la celda de origen (a veces E), sin comprobar.
5. **Colocación:** los límites de cada superficie caen a menos de una celda (25 m) de los nudos que superan el nivel. Vista desde arriba, coincide con las curvas 2D;
   Santa Bàrbara y La Galera quedan sobre sus cascos en la ortofoto.
6. **Segunda pasada:** en los nudos comunes, diferencia 0 con la corrida larga en las 24 horas (basta con 2 horas de arranque ESTE día, con 2,6-5,6 m/s; ⚠️ con calma haría falta
   más). Justo fuera de la zona calculada no pasa de 0,29 ou_E/m³: ningún nivel se corta por ahí.
7. **Controles** (`prueba_controles.py`, eventos simulados en Edge sin pantalla, WebGL por software): girar, acercar, hora, exageración y niveles funcionan, sin errores de WebGL.

**Sin comprobar:** ratón real, GPU real y su fluidez, el PC del operario, y que el reparto vertical sea el de la realidad: no hay ninguna medida en altura.

## Qué se ve
| Fin de la hora (UTC) | Emisión (ou_E/s) | Clase, capa de mezcla | 1 ou_E/m³: altura | Alcance | Suelo | Volumen |
|---|---|---|---|---|---|---|
| 07 (volteos, por la mañana) | 231 036 | D, 186 m | 75 m | 3,0 km | 0,81 km² | 43 Mm³ |
| 15 (volteos, por la tarde) | 227 736 | D, 1 142 m | 50 m | 2,7 km | 0,63 km² | 24 Mm³ |
| 13 (mediodía) | 54 537 | C, 1 106 m | 20 m | 0,55 km | 0,09 km² | 1,4 Mm³ |
| 23 (noche) | 52 737 | F, 132 m | 35 m | 3,1 km, cortado en el borde | 0,56 km² | 16 Mm³ |

- [`penacho_07utc.jpg`](penacho_07utc.jpg), [`penacho_13utc.jpg`](penacho_13utc.jpg), [`penacho_23utc.jpg`](penacho_23utc.jpg): vertical ×3.
  [`penacho_07utc_escala_real.jpg`](penacho_07utc_escala_real.jpg): ×1, casi una mancha.
- **Con casi la misma emisión, el olor de noche ocupa 11 veces más que a mediodía.** Es lo más claro que enseña la vista, y el mapa 2D con
  animación también lo enseña.
- **La capa de mezcla no se llega a ver:** la superficie de 1 ou_E/m³ se queda muy por debajo, salvo a las 07 UTC, cuando llega a 75 m con la capa en 186 m. La malla hasta 800 m sobra para
  estos focos: desde 150-200 m ya no hay nada.
- **Con 100 m o con 25 m salen casi los mismos números** (07 UTC: 43,3 frente a 43,0 Mm³; alcance 2,9 frente a 3,0 km), pero el dibujo es muy distinto: la segunda
  pasada es por la forma, no por los números.
- ⚠️ Los colores de superficies anidadas y translúcidas se mezclan: el núcleo de 5 ou_E/m³ sale rojo anaranjado, no del rojo de la leyenda.

## ¿Se ve la altura de una chimenea? (`chimenea.py`, pregunta del usuario, 2026-11-01)
Sí. Chimenea INVENTADA en la planta, de 12 m y 1 m de diámetro, 100 000 ou_E/s constantes, el mismo día, ±3 km cada 50 m y 21 alturas (190-226 s por caso con 2 procesos):

| Salida | Máximo en el suelo (ou_E/m³) | 1 ou_E/m³ | Toca el suelo | Altura del máximo a ~2 km, de noche | Briggs a mano (neutra) |
|---|---|---|---|---|---|
| 1 m/s, 20 °C | 33 | hasta 50-70 m, 0,8-3,7 km | 24 de 24 h | 0 m | 13 m |
| 30 m/s, 20 °C | 2,9 | hasta 60-80 m, 0,7-3,4 km | 24 de 24 h | 0-40 m | 37-43 m |
| 30 m/s, 200 °C | **0,76** | hasta 80-160 m, 0,5-2,0 km | **0 de 24 h** | 80-100 m | 84-104 m |

- El motor calcula la sobreelevación (Briggs: cantidad de movimiento y flotación) y los receptores en altura la recogen: la superficie caliente se despega del suelo las 24 horas, y el máximo en el suelo baja 43 veces.
- De día, a 2 km el máximo ya está en el suelo o casi: la turbulencia lo mezcla. Comparar con Briggs es de orden de magnitud: el motor usa esa misma fórmula, en las noches la estable, y aquí se compara con la neutra sobre alturas cada 20 m.
- [`chimenea_sin_impulso_lado.jpg`](chimenea_sin_impulso_lado.jpg) y [`chimenea_caliente_lado.jpg`](chimenea_caliente_lado.jpg): mismo encuadre, ×3. Desde arriba no se nota: hay que mirarlo de lado.
  Páginas: [`chimenea_sin_impulso.html`](chimenea_sin_impulso.html) y [`chimenea_caliente.html`](chimenea_caliente.html). Con 50 m, los bordes aún salen a escalones.
- ⚠️ **Que se vea depende de la emisión:** el modelo es lineal. Con los 343 ou_E/s de la caldera de ejemplo, ni el máximo en el aire llega más que a ~1 ou_E/m³, y las pilas emiten 200 veces más: por eso en la vista del plan Base no se distingue ninguna chimenea. Con focos reales habrá que elegir bien los niveles.
- ⚠️ **Sin efecto edificio:** `control_fuentes` no pasa al motor las dimensiones de los edificios (`CLAUDE.md`). Una chimenea junto a un digestor de 13 m bajaría antes de lo que sale aquí: la altura puede estar sobreestimada.

## Límites
- Viento de 400 m y sin edificios: el penacho no rodea los depósitos, y los ±100 m alrededor de la planta caen en una sola celda de viento. Lo cercano no es fiable por mucho que la malla sea de 25 m.
- Focos de ejemplo y un solo día. Con chimeneas altas y calientes reales, la superficie se despegaría del suelo y el 3D diría más; aquí no se ha podido ver.
- Los ~30° de error de dirección siguen ahí y una superficie sólida los disimula.
- La ventana de ±3 km corta la de 1 ou_E/m³ en 3 de las 24 horas (00, 06 y 23 UTC).
- Más allá de ±3 km no hay nada calculado: con más emisión o más calma haría falta otra ventana.

## Qué faltaría para meterlo en la app
1. La altura del receptor en `odora.preparacion.puffs.control` (una nueva versión de odora).
2. **Lanzar el motor en el PC del operario:** hoy la app no lo hace para los planes, que solo suman respuestas, y esas respuestas están en el suelo. Sería una corrida por plan y día (~10 min aquí).
   Precalcular respuestas en 3D de cada foco para no lanzarlo: sin medir, y mucho más caro.
3. Las isosuperficies sin vtk, o instalarlo en ese PC; aquí está en `C:\e2s`.
4. Una ventana 3D con QWebEngine, sincronizada con el reproductor, los estilos y las escalas. Comprobar WebGL en la GPU del operario.
5. La misma vista para gases: basta otra emisión y otros niveles.
6. La ortofoto y el relieve de la ventana, ya descargados, y su crédito (IGN).

## Reproducir
Con `C:\e2s\python.exe` y `PYTHONIOENCODING=utf-8`, desde esta carpeta, con `ENCE_GALERA_DATOS` en los DATOS locales (lo pone `comun.py`) y
`T=%TEMP%\ence_galera\99-Test\07_isosuperficies`:

    calcular.py --nombre suelo --alturas 0
    calcular.py --nombre vol --alturas 0,2,5,10,20,35,50,75,100,150,200,300,400,600,800
    comparar.py suelo vol      (necesita T\referencia: copia del penacho de la app del 2026-11-01)
    perfil_vertical.py
    balance.py
    afinar.py --horas 0,1,2,…,23
    mallas.py
    python -I empaquetar.py %T% fino penacho_3d.html resultados_mallas_fino.json
    captura.py penacho_3d.html penacho_07utc "h=07"
    prueba_controles.py

La librería y la ortofoto se descargaron a `T\descargas` desde `cdn.jsdelivr.net/npm/three@0.147.0` y `www.ign.es/wms-inspire/pnoa-ma`. Lo pesado (76 MB) queda en `T`.
