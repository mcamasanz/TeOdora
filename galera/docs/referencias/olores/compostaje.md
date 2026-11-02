---
tipo: olores-compostaje
fuente: area
contaminantes: [ou_E, NH3, H2S]
estadistico: percentil-98
umbral: "3 ou_E/m³ P98 horario (compostaje de verde bien aireado); 1,5 ou_E/m³ P98 si el residuo no es vegetal; Canarias: 3 ou_E/m³ (Categoría 1)"
ambito: España + UE
anio: 2026
origen: vigilancia tecnológica
---

# Compostaje y tratamiento de residuos orgánicos — estudio de olores

> El compostaje es el caso más difícil de modelizar con AERMOD porque el foco dominante no es una
> chimenea sino una superficie pasiva, caliente y sin empuje, cuyo penacho toca el suelo pegado a la
> propia pila. La decisión que más condiciona el resultado no es el caudal sino **la altura de emisión**,
> y la que más condiciona la validez del informe es **si la planta es abierta o cerrada**: el cerrado
> canaliza el aire a un biofiltro y convierte el problema en un foco puntual acotado.
> Este documento aporta factores de emisión verificados, parámetros de modelización reales de un caso
> AERMOD publicado, y los errores que invalidan un estudio.

**Documentos hermanos (no se repite su contenido aquí):**
- [Marco normativo España + UE](../normativa/marco_normativo_ES_UE.md) — Decreto 185/2025 de Canarias
  (3/6/9 ou_E/m³ al P98 de medias horarias anuales), vacío estatal, UNE-EN 13725:2022.
- [Criterios de olor internacionales](../normativa/criterios_olor_internacional.md) — Países Bajos e Italia.
- [Metodología de olores](../metodologia/olores_metodologia.md) — pico-media, percentiles, olfatometría.

---

## A. CÓMO MODELAR → para el agente 1

### A.0 · La bifurcación que hay que resolver ANTES de tocar el modelo

Todo lo demás depende de esto. **No existe «la planta de compostaje»: existen dos plantas distintas
que se modelizan de forma incompatible.**

| | **Compostaje ABIERTO** (pilas/hileras al aire libre) | **Compostaje CERRADO** (túneles, naves, contenedores) |
|---|---|---|
| Naturaleza del foco dominante | **Superficie pasiva** — el gas rezuma por la costra de la pila | **Foco canalizado** — el aire se aspira y se trata |
| Tipo de fuente AERMOD | `AREA` / `AREAPOLY` (varias) | `POINT` (chimenea del biofiltro) + `AREA` residual (fugitivas) |
| Sobreelevación de penacho | **Ninguna** (AERMOD no la calcula para fuentes de área) | Escasa: el biofiltro sale a ~ambiente y a <1 m/s |
| Dónde cae el máximo | **Pegado a la fuente**, en el borde de la parcela | A cierta distancia, según altura de chimenea |
| Palanca de reducción | Cubrición, gestión del volteo, distancia | Eficacia del biofiltro y estanqueidad de la nave |
| Incertidumbre dominante | El caudal Q por m² y la altura de emisión | Las **fugitivas** de la nave, no el biofiltro |

> **Aviso que se repite en toda la bibliografía y que conviene poner en el informe:** en una planta
> cerrada, *el biofiltro no suele ser el problema*. La guía de la Generalitat de Catalunya lo cuantifica:
> **«el 10 % de emisiones fugitivas de un edificio equivalen a las emisiones residuales de un sistema de
> tratamiento con [90 % de eficacia]»**, y exige que la permeabilidad del edificio sea **≤ 2 m³/m²·h a
> 50 kPa** (criterio ATTMA 2006). Modelizar sólo la chimenea del biofiltro y olvidar las fugitivas de
> puertas y muelles es el error estructural típico de estos estudios.

### A.1 · Focos típicos y cómo representarlos

| Unidad / foco | Tipo de fuente AERMOD | Altura típica de emisión | Notas de modelización |
|---|---|---|---|
| **Recepción y descarga** | `AREA` si es a cielo abierto o nave abierta; `POINT`/`VOLUME` si va a extracción | 0 m (solera) o altura del muelle | Es el foco de mayor tasa específica documentada (ver A.2). **Emisión discontinua**: sólo en horario de descarga → usar `EMISFACT HROFDY` |
| **Triturado / pretratamiento** | `AREA` pequeña o `VOLUME` | 1–3 m (proyección del material) | Emisión episódica ligada a la operación. Genera además partículas y bioaerosoles |
| **Pilas / hileras de fermentación (fase termófila)** | **`AREA` rectangulares alineadas con el eje de la pila** (no un único `AREAPOLY` envolvente) | Ver A.3 — decisión crítica | Foco continuo dominante en planta abierta. Fase de máxima emisión |
| **VOLTEO de las pilas** | `AREA` coincidente con la pila, **con factor horario** | Igual que la pila | Ver A.2. Pico intenso y breve; **no se promedia en el año, se modeliza como escenario** |
| **Trincheras / canales con aireación forzada y cubrición** | `AREA` con factor reductor | Altura de la lona/cubierta | Los factores del NeR distinguen explícitamente este caso (ver tabla A.2.1) |
| **Túneles de compostaje** | **No es fuente de área**: el aire va al biofiltro → `POINT` | — | Sólo se modelizan como área las **fugitivas** por puertas al abrir el túnel |
| **Maduración** | `AREA` | Ver A.3 | Factor de emisión específico por m² disponible y verificado (33 ou_E/m²·s, ver A.2) |
| **Afino / cribado** | `AREA` o `VOLUME` | 1–3 m | Emisión por tonelada procesada; episódica |
| **Almacenamiento de compost maduro** | `AREA` de baja intensidad | 0–2 m | El NeR lo da como **nulo si la masa está por debajo de 50 °C**. Si está caliente, no está maduro |
| **Biofiltro (planta cerrada)** | `POINT` si tiene chimenea o cubierta con caperuza; `AREA` **activa** si es un lecho abierto | 3–8 m con chimenea; ~1 m si es lecho abierto | Ver A.3: aunque sea `POINT`, se comporta casi como pasivo |
| **Balsa de lixiviados** | `AREA` / `AREAPOLY` | 0 m (lámina de agua) | Uno de los factores más altos de toda la bibliografía (500 ou_E/m²·s si hay percolación sin tratar) |

**Nota sobre AREAPOLY y las 20 vértices.** Una pila de compostaje es un prisma alargado: su planta es un
rectángulo. **No hace falta AREAPOLY para una pila** — basta `AREA` con longitud, anchura y ángulo de
rotación. Reserve `AREAPOLY` para el contorno de la balsa o de la playa de maduración. Y como el máximo
cae pegado a la fuente, **partir la era de fermentación en varias fuentes rectangulares (una por hilera)
da un campo de concentraciones mucho más realista** que una sola fuente envolvente que rellena de
emisión los pasillos vacíos entre pilas.

### A.2 · Datos de emisión (factores de emisión)

#### A.2.1 · Factores del NeR (Países Bajos) — planta de Fracción Orgánica de Residuos ✅ VERIFICADO

Fuente: **Guia sectorial de gestió de les olors a plantes de compostatge i tractament de residus
municipals**, Generalitat de Catalunya, Departament de Territori i Sostenibilitat, Direcció General de
Qualitat Ambiental, **Taula 3** (p. 17), que a su vez los toma de la **Netherlands Emission Guidelines
[NeR, 2000], capítulo 3.3, sección G4**.
URL: <https://mediambient.gencat.cat/web/.content/home/ambits_dactuacio/atmosfera/contaminacio_odorifera/prevencio_i_regulacio/mesures_correctores_i_preventives/guia_compostatge.pdf>

| Fase del proceso | Factor de emisión | Unidades |
|---|---|---|
| Recepción de residuos — **descarga** | **15·10⁵** | ou_E/tonelada |
| Recepción de residuos — **almacenamiento** | **5·10⁵** | ou_E/m²·h |
| Pretratamiento — **triaje** | **15·10⁵** | ou_E/tonelada |
| Compostaje, fase de descomposición — **en naves tipo «hall»** | **15·10⁵** | ou_E/tonelada·h |
| Compostaje, descomposición — **en celdas abiertas pero cubiertas (lona) con aireación y evacuación de aire** | **1,1·10⁵** | ou_E/tonelada·h |
| Compostaje, descomposición — **en túneles** | **7·10⁵** | ou_E/tonelada·h |
| Compostaje, descomposición — **en contenedores** | **0,65·10⁵** | ou_E/tonelada·h |
| Procesado de material descompuesto | **10·10⁵** | ou_E/tonelada |
| **Compostaje: fase de maduración** | **1,2·10⁵** | **ou_E/m²·h** |
| Postratamiento — afino de material madurado | **10·10⁵** | ou_E/tonelada |
| Almacenamiento de compost maduro | **Nulo** si la masa está a **T < 50 °C** | — |

**Conversión directa a lo que pide AERMOD** (el modelo quiere ou_E/(s·m²)):

| Foco | Factor original | **Valor para AERMOD** |
|---|---|---|
| Maduración | 1,2·10⁵ ou_E/m²·h | **33,3 ou_E/(s·m²)** |
| Almacenamiento en recepción | 5·10⁵ ou_E/m²·h | **139 ou_E/(s·m²)** |

⚠️ **Aviso sobre la tabla original.** En el PDF publicado, las llamadas a pie de tabla (1, 2, 3) están
**mal alineadas con las filas**: la nota 3 («número de ou_E por m² de residuo almacenado por hora») está
asociada a la fila *triaje*, cuyas unidades son ou_E/tonelada. Se ha reproducido la tabla tal cual figura
en la fuente. **Antes de usar el factor de triaje hay que decidir y documentar la unidad**; el resto de
filas son internamente coherentes.

#### A.2.2 · Factores por foco (Environment Agency, EA 2002d) — compostaje de estiércol, gallinaza, césped y paja ✅ VERIFICADO

Misma guía catalana, **Taula 4** (p. 18). **Éstos ya vienen en ou_E/(s·m²)**, es decir, listos para
introducir en una fuente de área de AERMOD.

| Foco | Factor de emisión | Unidades |
|---|---|---|
| **Percolación de lixiviados no tratados** | **500** | ou_E/m²·s |
| Gallinaza mezclada con césped | **500** | ou_E/m²·s |
| Estiércol de caballo (y estiércol de caballo aireado) | **200** | ou_E/m²·s |
| Almacenamiento de gallinaza | **150** | ou_E/m²·s |
| Paja mojada | **20** | ou_E/m²·s |
| **Almacenamiento de compost al descubierto** | **17** | ou_E/m²·s |
| Preparación de mezclas | 120 | ou_E/tonelada de mezcla |
| **Compostaje en pilas** de la mezcla | **170** | ou_E/tonelada·s |
| **Compostaje confinado con aireación** de la mezcla | **325** | ou_E/tonelada·s |

**Lectura útil:** la balsa/percolación de lixiviados (500) emite por m² **casi 30 veces más que el compost
maduro almacenado (17)**. En muchas plantas el foco que decide el resultado no es la era de fermentación
sino la balsa. Conviene comprobarlo siempre antes de dar por hecho que la pila manda.

#### A.2.3 · Factores de corrección por confinamiento ✅ VERIFICADO

Metodología del NeR recogida por la guía catalana (§2.3.3). Se aplican **multiplicando** los factores de
A.2.1 y A.2.2:

| Situación | Factor |
|---|---|
| Instalación **no confinada**, o edificio abierto, o cerrado con extracción **sin tratamiento posterior** | **× 1,0** |
| **Edificio cerrado sin extracción** | **× 0,5** |
| **Edificio cerrado con extracción y tratamiento posterior** | **× 0,1** (corresponde a una eficacia de eliminación del **90 %**) |

Este es el modo más rápido y defendible de cuantificar el efecto del encapsulado en un estudio
preliminar, y viene de una guía oficial.

#### A.2.4 · Tasas medidas en recepción ✅ VERIFICADO (fuente académica)

Toledo Padrón, M. (2018), *Evaluación del impacto odorífero en el tratamiento de residuos orgánicos*,
tesis doctoral, Universidad de Córdoba / repositorio Universidad de Valladolid. Medidas en planta
industrial (Córdoba):

| Foco | Tasa específica de emisión |
|---|---|
| **Recepción de basura orgánica** | **14,57 ou_E/(s·m²)** |
| **Recepción de lodos de depuradora** | **2,41 ou_E/(s·m²)** |

URL: <https://portaldelaciencia.uva.es/documentos/61e263f96e594f314e9ca8a5>

El mismo trabajo identifica el **índice respirométrico dinámico (DRI)** y la tasa de emisión de olor
como las dos variables más influyentes en la varianza: **cuanto menos estabilizado está el material, más
huele**. Es el argumento técnico que sostiene por qué la fase de descomposición domina sobre la maduración.

#### A.2.5 · Concentración de olor a lo largo del proceso ✅ VERIFICADO

Szyłak-Szydłowski et al. (2025), *Assessment of Odour Emission During the Composting Process by Using
Olfactory Methods and Gas Sensor Array Measurements*, **Sensors 25(10):3153**.
URL: <https://pmc.ncbi.nlm.nih.gov/articles/PMC12115676/>

| Fase | Semanas | Concentración de olor | Tendencia |
|---|---|---|---|
| Descomposición inicial | 0–2 | de 200–235 ou/m³ hasta un **máximo de ~10 000 ou/m³** al final de la semana 2 | +1 933 a +3 255 ou/m³ por semana |
| Degradación activa | 2–5 | descenso sostenido | −880 a −1 602 ou/m³ por semana |
| Maduración y estabilización | >5 | prácticamente plana | −5 a −49 ou/m³ por semana |

**Consecuencia para el modelo:** la emisión **no es uniforme en el tiempo ni en la planta**. Una pila de
la semana 2 emite dos órdenes de magnitud más que una de la semana 8. Si la era se modeliza como una
única fuente con un factor medio, se subestima el máximo local y se sobreestima el fondo. Lo correcto es
asignar a cada zona de la era el factor de su fase.

#### A.2.6 · El VOLTEO — el problema que no encaja en una media horaria

Lo verificado:

- **El máximo de emisión de una pila ocurre durante e inmediatamente después del volteo.** Verificado en
  varios estudios independientes.
- En hileras de lodos de depuradora, **la máxima concentración de COV (6 676 µg/m³) se midió durante el
  volteo**, con picos adicionales posteriores.
  *Odorous gas emissions from sewage sludge composting windrows affected by the turning operation*,
  Science of the Total Environment (2022). URL: <https://pubmed.ncbi.nlm.nih.gov/35588837/>
- El flujo de CO tras el volteo fue de **1,7 a 13,7 veces** el previo al volteo (pilas abiertas: de 0,60
  a 5,11 mg/m²·h; pilas hermetizadas: de 23,25 a 69,38 mg/m²·h). Es un **trazador de la perturbación**,
  no una medida de olor, pero da el orden de magnitud del salto.
- **Paradoja importante y bien documentada:** la planta con **mayor frecuencia de volteo** presentó la
  **menor emisión de olor por tonelada de compost y hora**, y el volteo frecuente redujo las tasas de
  emisión hasta **cinco veces** frente a tratamientos sin voltear. El volteo **provoca picos pero evita
  la anaerobiosis**, que es la que genera los compuestos reducidos (H₂S, mercaptanos) realmente ofensivos.

**Cómo se trata en AERMOD.** No existe una forma canónica; hay que elegir una y **declararla**:

1. **Escenario separado (recomendado).** Se corre el año completo con la emisión de base (pila sin
   voltear) y, aparte, un escenario de volteo aplicando el factor de pico sólo a las horas de volteo
   mediante `EMISFACT` (variación horaria/estacional). Se reportan los dos.
2. **Promediado horario.** Si el volteo dura 30 min dentro de una hora, la media horaria que compara
   AERMOD ya diluye el pico por dos. Esto es **coherente con el criterio del P98 de medias horarias** del
   Decreto 185/2025 y del marco EA/EPA-IE, pero **oculta el episodio real de molestia**.
3. **Lo que no se puede hacer:** repartir la emisión del volteo sobre las 8 760 horas del año. Eso
   convierte un pico en un fondo y hace desaparecer justo el episodio que genera las quejas.

⚠️ **No se ha verificado ningún factor multiplicador de olor específico para el volteo** (del tipo «×N
ou_E durante el volteo»). Los saltos de ×1,7–13,7 anteriores son de **CO**, no de olor. Cualquier factor
de pico de olor que se use debe medirse en la planta o declararse explícitamente como hipótesis. Ver F.

### A.3 · Parámetros de modelización

#### A.3.1 · Caso real AERMOD publicado — el mejor precedente localizado ✅ VERIFICADO

**Enviroguide Consulting para Enrich Environmental Ltd. (febrero 2022),** *Odour Emissions Assessment,
Larch Hill Stud, Newtownrathganley, Co. Meath* — expediente de la EPA de Irlanda. Planta mixta: túneles
cerrados con biofiltro **+** hileras abiertas de residuo verde. **AERMOD v18081**, con AERMET, AERMAP y
BPIPPRM. URL: <https://leap.epa.ie/docs/090151b28082cd0e.pdf>

**Fuente de ÁREA — hileras (windrows):**

| Parámetro | Valor usado |
|---|---|
| Tipo de fuente | `AREA` |
| **Tasa de emisión** | **0,12 ou_E/(s·m²)** |
| **Altura de emisión** | **2,5 m** — «generalmente, hasta el 50 % de la altura de la fuente» |
| **Dimensión vertical inicial (σz₀)** | **2,3 m** = altura de la pila (5 m) **/ 2,15** |
| Dimensiones | 70 m × 51 m |

**Fuente PUNTUAL — biofiltro (con caperuza antilluvia):**

| Parámetro | Valor usado |
|---|---|
| Tipo de fuente | `POINT` |
| Concentración en foco | **750 ou_E/m³** (el VLE de su licencia, usado como peor caso) |
| Caudal | 85 000 m³/h = **23,61 m³/s** |
| **Tasa de emisión** | 23,61 × 750 = **17 708 ou_E/s** |
| **Altura** | **7 m** |
| **Diámetro** | **10,01 m** |
| **Temperatura** | **25 °C** (≈ ambiente) |
| **Velocidad de salida** | **0,30 m/s** |

**Criterio y periodo:** 1,5 ou_E/m³ al **P98 de medias horarias**, evaluado sobre el **peor año** y sobre
un **periodo de 5 años (2016–2020)**. Rejilla: 100 m hasta 3 km, 50 m hasta 1 km, y receptores cada 25 m
en el límite de parcela (5 021 puntos).

> **Detalle que merece leerse dos veces:** el informe señala que la instalación **«colocará una caperuza
> antilluvia en el biofiltro, lo que lo convertirá en un foco de emisión puntual»**. Es la frase que
> mejor resume la bifurcación del apartado A.0: la misma unidad física es fuente de área o fuente puntual
> según cómo se cierre.

#### A.3.2 · La altura de emisión: el parámetro que decide el informe

**El equipo ha medido que, para una fuente de área, pasar de 1 m a 6 m de altura de emisión multiplica
el máximo por 12.** Nada de lo que se discuta sobre el caudal tiene ese peso. Y sin embargo la altura se
suele fijar «a ojo».

Por qué es tan brutal en fuentes de área y no tanto en chimeneas: en una fuente de área pasiva **el
máximo cae pegado a la fuente**, donde el penacho aún no ha crecido verticalmente. Ahí la concentración
va aproximadamente como el inverso del espesor de la capa en la que se ha mezclado la emisión, y esa capa
es del orden de la propia altura de emisión. Subir el punto de emisión no «aleja» el penacho: lo **despega
del suelo** justo en la zona donde se evalúa. En una chimenea alta, en cambio, el máximo ya está lejos y
la sensibilidad se reparte entre altura, sobreelevación y estabilidad.

**Recomendación operativa:**

1. **Fijar la altura de emisión en la superficie emisora, no a media altura de la pila.** Físicamente, el
   gas sale por *toda* la superficie del prisma, desde la solera hasta la cresta. La forma limpia de
   representarlo es **altura de emisión ≈ 0 y σz₀ = H/2,15**, dejando que la dimensión vertical inicial
   —y no la altura— represente el volumen de la pila.
2. ⚠️ **Existe una discrepancia real de práctica profesional.** El caso irlandés verificado usa
   **altura = 50 % de H *y además* σz₀ = H/2,15**, lo que **puede estar contabilizando dos veces** el
   espesor de la pila. No se ha localizado guía oficial que zanje la cuestión. **Lo defendible es correr
   ambas hipótesis, reportar la diferencia y justificar la elegida.** Con una sensibilidad de ×12 entre
   1 y 6 m, esta decisión no puede quedar sin documentar.
3. **Hacer siempre una tabla de sensibilidad a la altura** en el informe (ver B.7). Es barato y blinda
   el trabajo.

#### A.3.3 · Por qué una pila a 60 °C se modeliza como PASIVA y no boyante

Es la pregunta que más veces se plantea mal. Una pila en fase termófila está a **55–65 °C**, muy por
encima del ambiente. La intuición dice «penacho térmico». **Es falsa**, y AERMOD tiene razón en no ofrecer
sobreelevación para las fuentes de área.

Tres razones, en orden de peso:

1. **No hay chorro.** La sobreelevación de penacho necesita un **flujo volumétrico** con momento o
   flotabilidad. En una pila sin aireación forzada el gas **rezuma** a través de la costra por difusión y
   convección natural, con velocidades superficiales del orden de **milímetros por segundo**. El flujo de
   flotabilidad, que escala con el caudal volumétrico y con ΔT/T, es despreciable porque el primer factor
   lo es. Sin caudal no hay penacho, por caliente que esté el sólido.
2. **El contraste térmico se pierde en los primeros centímetros.** El gas emergente se mezcla
   inmediatamente con el aire de la capa límite superficial, que a esa escala tiene una turbulencia
   mecánica intensa. La diferencia de temperatura se disipa en un espesor de orden centimétrico y el gas
   alcanza el equilibrio térmico antes de haber ascendido nada apreciable. **Lo que está a 60 °C es la
   masa sólida, no el penacho.**
3. **Lo caliente y húmedo pesa poco… pero también es poco.** Aunque el gas saturado a 60 °C sea menos
   denso, el empuje resultante actúa sobre una masa de gas minúscula frente al aire que la envuelve.

**Corolario incómodo pero necesario:** **una pila caliente no dispersa mejor, dispersa peor**, porque toda
su emisión queda confinada cerca del suelo. La temperatura de la pila es un indicador de **actividad
biológica** —y por tanto de que la emisión es alta— **no de dispersión**.

**El caso límite: el biofiltro.** Incluso cuando el foco *sí* es canalizado, apenas hay empuje. En el caso
irlandés verificado, con 85 000 m³/h, la salida es a **25 °C y 0,30 m/s**. Eso es prácticamente ambiente y
prácticamente reposo:
- La **sobreelevación es casi nula**; modelizarlo como `POINT` sirve sobre todo para colocar la emisión a
  la altura correcta, no para ganar dispersión.
- ⚠️ Con velocidades de salida tan bajas hay que vigilar el **hundimiento de penacho por la propia
  boca (*stack-tip downwash*)**, que en AERMOD reduce la altura efectiva cuando la velocidad de salida es
  baja frente a la del viento. Con 0,30 m/s ocurre prácticamente siempre.
- Un biofiltro de lecho abierto sin chimenea **no es un foco puntual en absoluto**: es una **fuente de
  área activa** (con flujo hacia fuera), y así la contempla la UNE-EN 13725:2022.

#### A.3.4 · Periodo meteorológico

**Un año natural completo, como mínimo.** No es una recomendación de buenas prácticas: es una condición
aritmética. El criterio del **Decreto 185/2025 de Canarias** es el **P98 de medias horarias a lo largo de
un año natural**, y el marco EA/EPA-IE es el P98 horario. Un P98 sobre menos de 8 760 horas **no es el
estadístico que exige la norma**, y el 2 % que se descarta (175 horas) no es representativo si sólo se
simulan unos meses. El precedente irlandés va más allá y usa **5 años**, reportando el peor año y el
quinquenio. Ver [marco normativo](../normativa/marco_normativo_ES_UE.md) §F.2.

### A.4 · Errores típicos que invalidan un estudio

| # | Error | Por qué es grave | Qué hacer |
|---|---|---|---|
| 1 | **Modelizar la pila como fuente PUNTUAL en su centro** | Es el error más destructivo. Una fuente puntual genera un máximo *a cierta distancia* y concentraciones bajas junto al foco; la realidad de una fuente pasiva es la contraria: **el máximo cae pegado a la fuente**. El informe subestima justo donde está el límite de parcela y el vecino | `AREA` alineada con la hilera. Nunca `POINT` |
| 2 | **Suponer sobreelevación por la temperatura de la pila** | Ver A.3.3. No hay caudal, luego no hay flotabilidad. Meter una temperatura de 60 °C en un foco puntual ficticio **regala una dilución que no existe** y puede reducir el resultado en un orden de magnitud | Fuente pasiva, sin temperatura ni velocidad |
| 3 | **Fijar la altura de emisión sin justificarla** | Sensibilidad medida **×12 entre 1 y 6 m**. Un estudio cuyo resultado depende ×12 de un parámetro no documentado no es reproducible | A.3.2: declarar la hipótesis y presentar tabla de sensibilidad |
| 4 | **Ignorar el volteo** | Es el episodio de mayor emisión, y el que genera las quejas. Un estudio que sólo modeliza la pila en reposo no explica el historial de denuncias de la planta | Escenario específico con `EMISFACT` (A.2.6) |
| 5 | **Convertir masa → ou_E en una mezcla real** | **No existe factor de conversión general.** El olor de una mezcla **no es la suma** de los olores de sus componentes: hay sinergia, antagonismo y enmascaramiento, y cada compuesto tiene su propio umbral. Estimar ou_E a partir del NH₃ o del H₂S medidos es inventar el dato de entrada | Olfatometría dinámica **UNE-EN 13725:2022** sobre muestra real, o factores de emisión publicados (A.2). Si no hay ni una cosa ni otra, decirlo |
| 6 | **Menos de un año de meteorología** | El P98 horario anual no se puede calcular con menos. El resultado no es comparable con el criterio normativo | Año natural completo; mejor 3–5 años |
| 7 | **Modelizar sólo el biofiltro en una planta cerrada** | Las **fugitivas** de la nave pueden pesar tanto como el foco tratado: el 10 % de fugitivas ≈ las emisiones residuales de un tratamiento al 90 % | Añadir fuente de área para fugitivas y declarar la hipótesis de estanqueidad |
| 8 | **Una sola fuente de área envolviendo toda la era** | Rellena de emisión los pasillos vacíos y promedia fases con emisiones que difieren en dos órdenes de magnitud (A.2.5) | Una fuente por hilera o por zona de fase |
| 9 | **Olvidar la balsa de lixiviados** | Con 500 ou_E/m²·s en percolación sin tratar, puede ser el foco dominante y suele quedar fuera del inventario | Incluirla siempre en el inventario, aunque luego resulte menor |
| 10 | **Comparar la salida de AERMOD con un criterio de olfatometría de campo** | El P98 modelizado y el criterio de 30/60 min medidos en campo (tipo ordenanza Diba) **no son intercambiables** | Ver [marco normativo](../normativa/marco_normativo_ES_UE.md) §D.5 |

---

## B. ESTRUCTURA DEL INFORME → para el agente 2

Secciones numeradas de un informe real de dispersión de olores de una planta de compostaje.

**1. Objeto, alcance y marco normativo aplicable**
Actividad, promotor, procedimiento que motiva el estudio (EIA, AAI, autorización de emisiones o
requerimiento del órgano ambiental). Jurisdicción y **criterio de olor aplicable, elegido y justificado**
(ver C). *Tabla 1: criterio de evaluación adoptado y su fuente normativa.*

**2. Descripción de la instalación y del proceso**
Capacidad (t/año), tipo de residuo entrante (FORSU, verde, lodos, subproductos animales), tecnología
(abierto / trinchera cubierta / túnel / contenedor), esquema de flujo. **Debe quedar explícito si la
planta es abierta o cerrada**, porque condiciona todo el modelo (A.0).
*Figura 1: diagrama de proceso con los focos de olor marcados sobre el flujo de materia.*
*Figura 2: planta acotada de la instalación con la ubicación de cada foco.*

**3. Inventario de focos emisores**
Lista exhaustiva: recepción, triturado, fermentación, volteo, maduración, afino, biofiltro, balsa de
lixiviados, almacenamiento. Para cada uno: régimen (continuo/discontinuo), horario y superficie.
*Tabla 2: inventario de focos con superficie, régimen horario y fase del proceso.*

**4. Cuantificación de la emisión**
De dónde sale cada tasa: olfatometría propia (indicando norma, laboratorio y fecha), factor de emisión
bibliográfico (con cita) o balance. **Distinguir tipográficamente lo medido de lo estimado.**
*Tabla 3: tasa de emisión por foco en ou_E/s y ou_E/(s·m²), con columna «origen del dato».*
*Tabla 4: escenarios de emisión (operación normal / volteo / peor caso).*

**5. Meteorología**
Estación, periodo (año/s completos), tratamiento de datos faltantes, características superficiales
(rugosidad, albedo, razón de Bowen) y su procedencia. Justificar la representatividad de la estación.
*Figura 3: rosa de vientos anual.* *Figura 4: rosa de vientos de las horas nocturnas y estables* —
las condiciones estables y de viento flojo son las que producen los episodios de olor.
*Tabla 5: distribución de clases de estabilidad.*

**6. Configuración del modelo**
AERMOD (versión), AERMET, AERMAP, BPIPPRM. Dominio, rejilla de receptores y receptores discretos
(viviendas, escuelas, hospitales). **Tabla completa de parámetros de fuente** — el corazón auditable del
informe.
*Tabla 6: parámetros de cada fuente (tipo, coordenadas, dimensiones, altura de emisión, σz₀, tasa).*
*Figura 5: dominio, rejilla de receptores y receptores sensibles.*

**7. Análisis de sensibilidad** *(sección que distingue un informe serio)*
Como mínimo: **altura de emisión** (documentar el ×12), tasa de emisión (±factor 2–3) y año meteorológico.
*Tabla 7: P98 en el receptor crítico frente a altura de emisión (1, 2, 3, 4, 6 m).*
*Figura 6: gráfico de tornado con la contribución de cada hipótesis a la incertidumbre.*

**8. Resultados**
P98 de medias horarias en cada receptor sensible y campo de concentraciones.
*Tabla 8: P98 por receptor frente al criterio, con columna de cumplimiento.*
*Figura 7: isopletas del P98 sobre ortofoto, con la isopleta del criterio destacada.*
*Figura 8: mapa de contribución por foco* — es lo que permite decidir dónde invertir en medidas.
*Tabla 9: contribución porcentual de cada foco al P98 del receptor crítico.*

**9. Escenario de volteo** *(si aplica)*
Resultados del escenario episódico y discusión sobre su encaje con un criterio de media horaria.

**10. Medidas correctoras y escenario con medidas**
Ver D. **Volver a correr el modelo con las medidas aplicadas**: una medida sin cuantificar no es una
medida, es una intención. *Tabla 10: medidas, eficacia aplicada, fuente de la eficacia y P98 resultante.*

**11. Programa de vigilancia**
Olfatometría periódica en focos, registro de quejas (exigible en Canarias, art. 32 del D. 185/2025),
indicadores de proceso (temperatura, O₂, humedad) y umbrales de acción.

**12. Conclusiones**

**13. Limitaciones e incertidumbres**
Sección obligatoria y honesta: origen de cada Q, hipótesis de altura, periodo meteorológico,
simplificación geométrica de contornos y no aditividad del olor.

**14. Bibliografía y anexos**
Ficheros de entrada y salida de AERMOD, informes de olfatometría, certificados del laboratorio.

---

## C. NORMATIVA APLICABLE

Lo general está en [marco normativo España + UE](../normativa/marco_normativo_ES_UE.md) y
[criterios internacionales](../normativa/criterios_olor_internacional.md). Aquí sólo lo específico del
compostaje.

### C.1 · Normativa de residuos — el marco de la actividad

**Ley 7/2022, de 8 de abril, de residuos y suelos contaminados para una economía circular**
(BOE-A-2022-5809). Sustituye a la Ley 22/2011. Es la norma que ordena la actividad —régimen de
autorización de gestores de residuos, jerarquía de residuos, y sobre todo **la obligación de recogida
separada de biorresiduos**, que es la que ha multiplicado el número de plantas de compostaje en España y,
con ellas, los expedientes de olor. Una planta de compostaje necesita **autorización como instalación de
tratamiento de residuos** conforme a esta ley, con independencia de la autorización atmosférica.

⚠️ **La Ley 7/2022 no fija valores de olor.** Ninguna norma estatal española lo hace. El criterio sale
siempre del escalón autonómico o municipal.

### C.2 · El encaje en el Decreto 185/2025 de Canarias

Relevante porque la clasificación es directa: la **Categoría 1 (molestia alta)** del art. 6.2 incluye
literalmente la **«gestión de residuos susceptibles de generar olor»**. Una planta de compostaje de FORSU
o de lodos entra en Categoría 1 → **valor objetivo 3 ou_E/m³ al P98 de medias horarias de un año natural**.
La Categoría 2 incluye el «tratamiento de productos orgánicos» (6 ou_E/m³), encaje discutible para
compostaje exclusivamente vegetal. Detalle completo en [marco normativo](../normativa/marco_normativo_ES_UE.md) §D.2.

### C.3 · Criterio por ofensividad (EA Reino Unido / EPA Irlanda) — específico y muy útil ✅ VERIFICADO

Recogido en la *EPA Odour Emissions Guidance Note* **AG9 (2019)** de Irlanda, adaptado de la guía
británica **EA (2011)**, y reproducido en el informe de Larch Hill (Tabla 3-1). **Es el único criterio
localizado que distingue explícitamente tipos de compostaje:**

| Categoría de ofensividad | Actividades relevantes | Criterio indicativo |
|---|---|---|
| **Más ofensivo** | Vertederos, estaciones de transferencia y **plantas de compostaje de residuo NO vegetal**; procesos con restos animales; fangos y efluentes sépticos | **1,5 ou_E/m³** al P98 de medias horarias en el receptor sensible más desfavorable |
| **Moderadamente ofensivo** | **Compostaje de residuo VERDE bien aireado**; ganadería intensiva; procesado de alimentos | **3,0 ou_E/m³** al P98 de medias horarias |
| **Menos ofensivo** | Panadería, tostado de café, cervecera, confitería | **6,0 ou_E/m³** al P98 de medias horarias |

Dos lecturas importantes:
- **El criterio depende del sustrato y de la aireación, no del tamaño de la planta.** Compostar FORSU o
  lodos exige el doble de exigencia (1,5) que compostar poda bien aireada (3,0). Y «bien aireado» es
  condicional: **una planta de verde mal gestionada, con anaerobiosis, pierde el criterio favorable.**
- **El 3,0 ou_E/m³ coincide con el valor de Categoría 1 del Decreto canario.** La convergencia entre dos
  marcos independientes hace de **3 ou_E/m³ al P98 horario** la referencia más sólida disponible en España
  para compostaje, y de **1,5** el criterio prudente cuando el sustrato incluye materia animal o lodos.

### C.4 · Límites en FOCO — regiones italianas y BREF

**Regiones italianas** (detalle en [criterios internacionales](../normativa/criterios_olor_internacional.md)):

| Región | Límite en foco | Ámbito |
|---|---|---|
| **Abruzzo y Cerdeña** | **300 ou_E/m³** | Plantas de residuos y **compostaje** |
| **Sicilia** | **< 300 ou_E/m³** | **A la salida del biofiltro** |

**BREF de tratamiento de residuos — el límite europeo en foco** ✅ VERIFICADO
**Decisión de Ejecución (UE) 2018/1147 de la Comisión, de 10 de agosto de 2018**, por la que se
establecen las conclusiones sobre las MTD para el tratamiento de residuos. Su sección de **tratamiento
biológico de residuos** fija un **NEA-MTD (BAT-AEL) de concentración de olor para emisiones canalizadas
de:**

> **200 – 1 000 ou_E/Nm³**, como media durante el periodo de muestreo, aplicable a **todos los
> tratamientos biológicos de residuos**.

URL: <https://www.legislation.gov.uk/eudn/2018/1147/annex/division/3/data.xht?view=snippet&wrap=true>

**Este es el número que debe usarse para dimensionar el foco de un biofiltro en una planta española bajo
AAI**, y es también el dato de entrada correcto para el escenario «con medidas» del apartado B.10.
Comparación de los tres criterios en foco, que **no coinciden y conviene no mezclar**:

| Criterio | Valor en foco | Comentario |
|---|---|---|
| **NEA-MTD UE (2018/1147)** | **200 – 1 000 ou_E/Nm³** | Es un **rango**, no un límite único. Su extremo inferior es el más exigente de los tres; su extremo superior, el más laxo |
| **Abruzzo / Cerdeña / Sicilia** | **300 ou_E/m³** | Valor único; cae **dentro** del rango europeo |
| Licencia irlandesa de Larch Hill | 750 ou_E/m³ | VLE de una autorización concreta, **no un estándar**. Dentro del rango europeo, cerca del extremo laxo |

⚠️ **Referencia histórica, no vigente:** el BREF de tratamiento de residuos **de 2006** fijaba en su
**BAT 70**, para tratamiento mecánico-biológico, un gas de escape tratado con **olor < 500 – 6 000 ou_E/m³
y NH₃ < 1 – 20 mg/m³**, con una producción de gas de escape de **2 500 – 8 000 Nm³/tonelada**. Aparece
todavía en formularios de evaluación MTD en circulación. **Está superado por la Decisión 2018/1147** y no
debe citarse como vigente; el dato de **Nm³/tonelada** sigue siendo útil como orden de magnitud para
dimensionar caudales.

---

## D. MEDIDAS CORRECTORAS

Principio rector de la guía catalana, que conviene encabezar esta sección en cualquier informe:
**son prioritarias las medidas que actúan sobre el origen** (diseño de proceso y buenas prácticas) frente
a los tratamientos finalistas, porque a largo plazo son más viables económicamente.

### D.1 · Eficacias verificadas

| Medida | Eficacia | Fuente | Estado |
|---|---|---|---|
| **Confinamiento con extracción y tratamiento** | **90 %** (factor ×0,1 sobre el factor de emisión) | Guía Gencat §2.3.3 / NeR 2000 | ✅ Verificado |
| **Confinamiento sin extracción** (nave cerrada) | **50 %** (factor ×0,5) | Guía Gencat §2.3.3 / NeR 2000 | ✅ Verificado |
| **Biofiltración** | **≈ 95 %** de eliminación de olor como valor típico de diseño; **≥ 90 %** habitual | Guía Gencat, ficha de biofiltros | ✅ Verificado |
| **Lavadores (scrubbers) y adsorción** | **70 – 99 %**, con olor residual de salida de **500 – 1 000 ou_E/m³** | Guía Gencat, fichas de técnicas | ✅ Verificado |
| **Oxidación / técnicas para corrientes muy cargadas** | **60 – 90 %** para emisiones de partida > 100 000 ou/Nm³ | Guía Gencat | ✅ Verificado |
| **Eliminación de NH₃ en lavador** | **20 – 60 %**, para entradas de 200–1 000 mg/Nm³ | Guía Gencat | ✅ Verificado |
| **Cubrición con membrana semipermeable (tipo GORE® Cover)** | «hasta un **97 %**» de reducción de olor | Fabricante (W. L. Gore) | ⚠️ **Dato de fabricante, no verificado de forma independiente.** Ver F |

### D.2 · Cubrición de pilas con membrana semipermeable

**Mecanismo** (descrito por el fabricante y coherente con la física del proceso): una membrana de poro
muy fino cubre la pila, que se airea por soplado en presión positiva. Los poros dejan pasar vapor de agua
y CO₂ pero **retienen las moléculas grandes —odorantes y bioaerosoles—**. El vapor condensa en la cara
interna de la membrana, **los odorantes se disuelven en ese condensado y gotean de vuelta a la pila**,
donde los microorganismos los degradan. La pila se autodepura.

**Por qué encaja tan bien en la modelización:** convierte una fuente de área de alta intensidad en una de
baja intensidad **sin necesidad de nave ni de biofiltro**. Los factores del NeR ya recogen este caso: la
descomposición **«en celdas abiertas pero cubiertas (con lona) con aireación y evacuación de aire»** tiene
un factor de **1,1·10⁵ ou_E/tonelada·h**, frente a **15·10⁵ en nave tipo hall** y **7·10⁵ en túnel**
(A.2.1). Es decir: **según los factores oficiales, la trinchera cubierta y aireada emite menos que el
túnel**. Es un resultado contraintuitivo y muy relevante para el diseño; conviene contrastarlo con datos
de planta antes de apoyar una decisión de inversión.

⚠️ La cubrición **estorba el volteo**: hay que retirar y recolocar la membrana. En la práctica se combina
con aireación forzada precisamente para reducir la frecuencia de volteo.

### D.3 · Encapsulado y control de fugitivas

- **Nave de alta hermeticidad: permeabilidad ≤ 2 m³/m²·h a 50 kPa** (criterio ATTMA 2006, recogido por la
  guía catalana), con **extracción que mantenga ligera presión negativa** y tratamiento del aire extraído.
- **Puertas rápidas y esclusas automáticas estancas** con extracción local. Para residuos muy odorantes,
  **búnkeres de alimentación cerrados**.
- **No mantener puertas abiertas** y no operar con meteorología adversa (viento hacia los receptores,
  inversión térmica, calma nocturna).
- **Recordatorio cuantitativo:** un **10 % de fugitivas anula el beneficio de un tratamiento al 90 %.**
  La estanqueidad no es un detalle constructivo, es la medida correctora.

### D.4 · Biofiltros — parámetros de diseño verificados

De la ficha técnica de la guía de la Generalitat de Catalunya:

| Parámetro | Valor |
|---|---|
| Eficacia típica de eliminación de olor | **≈ 95 %** |
| Carga volumétrica | **50 – 200 m³/m² de biofiltro·h**; **< 100 m³/m³ de biofiltro·h** |
| Superficie habitual | **1 500 – 7 500 m²** |
| Umbral de coste-eficacia | Tratamiento de **> 1 500 Nm³/h** |
| Partículas en la entrada | **< 1 mg/Nm³** (por encima, colmatan el lecho) |
| Olor residual admisible en un biofiltro sano | **< 2 500 ou_E/m³** |
| **NH₃ en plantas de compostaje** | Generalmente **elevado (> 30 mg/Nm³)** → **es necesario un pretratamiento químico (lavador ácido) antes del biofiltro** |

Dos advertencias de la propia guía, muy pertinentes en compostaje:
- **El NH₃ alto es la causa habitual de fallo del biofiltro.** Un biofiltro sin lavador ácido previo se
  acidifica, pierde población microbiana y su eficacia se desploma. En una planta de FORSU o de lodos,
  **el lavador no es opcional**.
- **El criterio alemán de «< 500 GE/m³» a la salida del biofiltro no es trasladable a ou_E/m³.** Las GE
  (*Geruchseinheiten*) no se referían a un gas patrón y dan valores bastante más bajos que la olfatometría
  actual conforme a EN 13725. **Copiar ese 500 como si fuera ou_E/m³ es un error de unidades** que la guía
  señala expresamente.
- Además, el aire caliente debe **refrigerarse** antes de entrar al lecho.

### D.5 · Gestión del volteo

La medida más barata y la peor gestionada. Fundamento en A.2.6.

- **Voltear con criterio meteorológico**, no por calendario: evitar horas de viento hacia los receptores,
  calma nocturna e inversión térmica. Trasladar el volteo a las horas de mayor mezcla atmosférica (media
  mañana a media tarde) reduce el impacto sin coste alguno.
- **No suprimir el volteo para «reducir el pico»**: la anaerobiosis resultante genera compuestos reducidos
  mucho más ofensivos y **aumenta la emisión total**. El volteo frecuente redujo la emisión hasta **cinco
  veces** frente a no voltear.
- **Sustituir volteo por aireación forzada** donde sea posible: mantiene la oxigenación sin perturbar la
  masa. Es la lógica de los sistemas de trinchera cubierta y aireada.
- **Regar durante el volteo** para limitar la resuspensión de polvo y bioaerosoles.

### D.6 · Control de humedad, aireación y proceso

La emisión de olor es, en el fondo, **un síntoma de que el proceso va mal**. Las medidas de proceso
recogidas por la guía catalana y por el BREF:

| Variable | Criterio | Efecto sobre el olor |
|---|---|---|
| **Aireación** | Suficiente para **evitar la formación de zonas anaerobias** | Es *la* causa raíz. La anaerobiosis genera H₂S, mercaptanos y ácidos grasos volátiles, que son los compuestos verdaderamente ofensivos |
| **pH** | Adecuado para los microorganismos y **< 8** | Por encima de 8 se dispara la volatilización de **NH₃** |
| **Relación C:N** | Optimizarla (BAT «reducir emisiones de compuestos nitrogenados optimizando la relación C:N») | Exceso de N → NH₃ |
| **Humedad** | Mantenerla en rango mediante riego / aspersión en cubierta | Poca humedad frena el proceso; exceso colapsa la porosidad y provoca anaerobiosis |
| **Estructurante** | Recibir los residuos **sobre un lecho de material estructurante** y mezclar y cubrir rápidamente | Mantiene porosidad y absorbe lixiviados |
| **Estabilidad del material** | Controlar el **DRI** (índice respirométrico dinámico) | Es la variable más correlacionada con la emisión de olor (A.2.4). **Material inestable = material que huele** |

**Buenas prácticas de recepción** (donde están las tasas más altas, A.2.4): no superar la capacidad
nominal de tratamiento; **no aceptar residuos en estado de descomposición avanzado**; recibir sobre solera
pavimentada con recogida de lixiviados; **mezclar, cubrir e incorporar inmediatamente** al proceso; no
acumular durante periodos prolongados. Y en la recogida: rutas que eviten zonas residenciales y
**estanqueidad de la cubierta de los vehículos**.

### D.7 · Distancia y ubicación

La guía catalana incluye **nomogramas específicos para plantas de producción de compost** que relacionan
la tasa de emisión total (en ou_E/h) con la distancia mínima necesaria a receptores, trazados para las
curvas de **C98 horario = 3 ou_E/m³ y 5 ou_E/m³**. Cubren los rangos 0–90·10⁶ ou_E/h y 0–6 000·10⁶ ou_E/h.

El umbral de referencia que emplea, tomado del NeR: **10 000 ou_E/s (= 36·10⁶ ou_E/h)**. Por debajo de
esa emisión, la guía sólo considera problemática la ubicación **a menos de 200 m de receptores**; por
encima, la instalación se considera insuficientemente separada según los nomogramas.

Es una herramienta de **cribado previo** excelente: permite saber, antes de montar AERMOD, si el problema
es de orden de magnitud o de detalle. **No sustituye a la modelización** y sus curvas están construidas
para la meteorología neerlandesa/catalana.

---

## E. FUENTES

| # | Fuente | URL | Uso y verificación |
|---|---|---|---|
| 1 | **Generalitat de Catalunya**, Departament de Territori i Sostenibilitat, DG de Qualitat Ambiental — *Guia sectorial de gestió de les olors a plantes de compostatge i tractament de residus municipals* (124 p.) | <https://mediambient.gencat.cat/web/.content/home/ambits_dactuacio/atmosfera/contaminacio_odorifera/prevencio_i_regulacio/mesures_correctores_i_preventives/guia_compostatge.pdf> | ✅ **PDF descargado y texto extraído.** Taulas 3 y 4 (factores de emisión), factores de confinamiento, fichas de biofiltros y lavadores, nomogramas, buenas prácticas. **Fuente principal de este documento** |
| 2 | **NeR — Netherlands Emission Guidelines** (2000), cap. 3.3, sección G4 | — | ✅ Origen de la Taula 3; citado a través de (1). Texto original no consultado directamente |
| 3 | **Environment Agency (2002d)** | — | ✅ Origen de la Taula 4; citado a través de (1) |
| 4 | **Enviroguide Consulting / Enrich Environmental Ltd.** (feb. 2022), *Odour Emissions Assessment — Larch Hill Stud, Co. Meath*, EPA Irlanda | <https://leap.epa.ie/docs/090151b28082cd0e.pdf> | ✅ **PDF descargado y texto extraído.** Parámetros AERMOD reales (Tablas 4-1, 4-3, 4-4), criterio AG9, resultados. **Mejor precedente de modelización localizado** |
| 5 | **EPA Irlanda**, *Odour Emissions Guidance Note* **AG9 (2019)**, adaptada de **EA (2011)** | Reproducida en (4), Tabla 3-1 | ✅ Criterios 1,5 / 3,0 / 6,0 ou_E/m³ por ofensividad, con distinción explícita compostaje de verde / no verde |
| 6 | **Decisión de Ejecución (UE) 2018/1147** — conclusiones MTD para el tratamiento de residuos | <https://www.legislation.gov.uk/eudn/2018/1147/annex/division/3/data.xht?view=snippet&wrap=true> | ✅ **NEA-MTD de olor: 200–1 000 ou_E/Nm³** para todos los tratamientos biológicos de residuos |
| 7 | **BREF de tratamiento de residuos (2006), BAT 70** — reproducido en un formulario de evaluación MTD de la EPA de Irlanda | <https://epawebapp.epa.ie/licences/lic_eDMS/090151b28082cce7.pdf> | ✅ PDF descargado. Olor < 500–6 000 ou_E/m³ y NH₃ < 1–20 mg/m³ en gas tratado de TMB; 2 500–8 000 Nm³/t. ⚠️ **Superado por (6)** |
| 8 | **Toledo Padrón, M. (2018)**, *Evaluación del impacto odorífero en el tratamiento de residuos orgánicos*, tesis doctoral | <https://portaldelaciencia.uva.es/documentos/61e263f96e594f314e9ca8a5> | ✅ Tasas de recepción: 14,57 y 2,41 ou_E/(s·m²). Papel del DRI |
| 9 | **Szyłak-Szydłowski et al. (2025)**, *Assessment of Odour Emission During the Composting Process…*, **Sensors 25(10):3153** | <https://pmc.ncbi.nlm.nih.gov/articles/PMC12115676/> | ✅ Perfil de concentración de olor por fases; pico de ~10 000 ou/m³ al final de la semana 2 |
| 10 | *Odorous gas emissions from sewage sludge composting windrows affected by the turning operation and associated health risks*, **Science of the Total Environment (2022)** | <https://pubmed.ncbi.nlm.nih.gov/35588837/> | ✅ Máximo de COV (6 676 µg/m³) durante el volteo |
| 11 | *Assessment of emissions and potential occupational exposure to carbon monoxide during biowaste composting* | <https://www.ncbi.nlm.nih.gov/pmc/articles/PMC10923444/> | ✅ Flujos de CO antes/después del volteo (×1,7–13,7) — trazador de la perturbación |
| 12 | **W. L. Gore & Associates** — GORE® Cover para compostaje | <https://www.gore.com/products/organic-cover-composting-resource-recovery-bio-drying> · <https://utvag.de/en/gore-cover> | ⚠️ **Fuente comercial.** Mecanismo de la membrana semipermeable y afirmación de «hasta 97 %» de reducción |
| 13 | *Gaseous Emissions from the Composting Process: Controlling Parameters and Strategies of Mitigation*, **Processes 9(10):1844 (2021)** | <https://www.mdpi.com/2227-9717/9/10/1844> | ✅ Papel de la aireación en evitar zonas anaerobias |
| 14 | **Environment Agency**, *Biofilter performance and operation as related to commercial composting* (LIT 8166) | <https://assets.publishing.service.gov.uk/media/5a7c6f65ed915d6969f44d67/LIT_8166_d2eca5.pdf> | ⚠️ Localizado, **no extraído**. Pendiente para profundizar en biofiltros |
| 15 | **Ley 7/2022, de 8 de abril**, de residuos y suelos contaminados para una economía circular | BOE-A-2022-5809 | Marco de la actividad. **No fija valores de olor** |
| 16 | **Olores.org** — artículos sobre emisiones en tratamiento biológico de residuos y modelización | <https://olores.org/> | ⚠️ Consultado; los artículos revisados aportan factores en g C/Mg·día y g NH₃/Mg·día, **no en ou_E** |

**Fecha de consulta de todas las fuentes: 21 de julio de 2026.**

---

## F. INCERTIDUMBRES Y AVISOS

### F.1 · Lo que NO se ha podido verificar

| Punto | Estado |
|---|---|
| **Factor multiplicador de olor durante el volteo** | ❌ **No verificado.** Está documentado que el máximo ocurre durante e inmediatamente después del volteo, pero **no se ha localizado ningún factor de pico expresado en ou_E**. Los saltos ×1,7–13,7 son de **CO**, y los 6 676 µg/m³ son de **COV**: ambos son trazadores, no olor. **No debe usarse ninguno de esos números como factor de olor** |
| **Eficacia del 97 % de la membrana semipermeable** | ⚠️ **Sólo fuente del fabricante.** No se ha encontrado validación independiente ni ensayo publicado con olfatometría de entrada y salida. Si se usa en un informe, citar como declaración del fabricante y considerar un valor más conservador |
| **Factores de emisión específicos de plantas ESPAÑOLAS por fase** | ❌ **No localizados.** Los factores de A.2.1 y A.2.2 son neerlandeses (NeR 2000) y británicos (EA 2002d), con **más de 20 años**, transpuestos por la guía catalana. Es lo mejor disponible, pero **no son datos españoles ni recientes** |
| **Guía sectorial catalana: fecha de publicación exacta** | ⚠️ El PDF no la explicita con claridad; por sus referencias (ATTMA 2006, REACH 2006, VDI 3475 de 2003/2005) es **posterior a 2006**. Citarla sin año o verificar en la sede de la Generalitat |
| **Alineación de las llamadas a pie de la Taula 3** | ⚠️ **Errata en la fuente original** (ver A.2.1). La unidad del factor de triaje es ambigua |
| **EA LIT 8166 sobre biofiltros en compostaje comercial** | ⚠️ Documento localizado pero **no extraído** por límite de tiempo. Es la vía natural para profundizar en eficacias reales de biofiltros |
| **Número exacto de la tabla del NEA-MTD de olor** en la Decisión 2018/1147 | ⚠️ El valor **200–1 000 ou_E/Nm³** está verificado; la referencia de tabla se ha tomado del extracto consultado. Verificar contra el DOUE antes de citarla con número de tabla en un informe |

### F.2 · Avisos metodológicos

1. ⚠️ **Los factores de emisión de A.2 son de orden de magnitud, no de proyecto.** Nótese la dispersión:
   las hileras del caso irlandés se modelizaron con **0,12 ou_E/(s·m²)**, mientras que la recepción de
   basura orgánica medida en Córdoba da **14,57 ou_E/(s·m²)** y la percolación de lixiviados **500**. Hay
   **cuatro órdenes de magnitud** entre los focos de una misma planta. **Coger un valor «medio» de la
   bibliografía y aplicarlo a toda la instalación produce un resultado sin significado.** Para un informe
   con consecuencias, **olfatometría propia según UNE-EN 13725:2022**.

2. ⚠️ **El caudal Q es la mayor fuente de error de todo el estudio** — así lo tiene medido el equipo, y la
   dispersión de los factores anteriores lo confirma. La estructura correcta del informe es: declarar el
   origen de cada Q, y **si es bibliográfico, presentar un rango, no un valor**.

3. ⚠️ **La altura de emisión es el parámetro más sensible del modelo (×12 entre 1 y 6 m)** y, a la vez, el
   que menos consenso tiene en la práctica profesional (A.3.2). **No se ha localizado guía oficial que
   resuelva si debe usarse la superficie emisora o la media altura de la pila.** Es una hipótesis a
   declarar y a someter a análisis de sensibilidad, siempre.

4. ⚠️ **El olor no es aditivo y no se deduce de la masa.** No existe conversión general de mg/m³ de NH₃ o
   H₂S a ou_E/m³ en una mezcla real: los umbrales son específicos de cada compuesto y hay sinergia,
   antagonismo y enmascaramiento. Cualquier informe que presente una conversión masa→ou_E debe explicitar
   la mezcla, el método y sus límites.

5. ⚠️ **En fuentes de área pasivas el máximo cae pegado a la fuente.** Esto tiene dos consecuencias que
   conviene declarar: (a) los resultados son **muy sensibles a la geometría** de la fuente y al mallado de
   receptores cerca del límite de parcela; (b) AERMOD, como modelo gaussiano de estado estacionario,
   **está en el límite inferior de su rango de validez** a distancias de decenas de metros del foco. Los
   valores en el propio límite de parcela deben leerse con prudencia.

6. ⚠️ **La emisión de una planta de compostaje es fuertemente estacional y dependiente de la operación.**
   Temperatura ambiente, humedad, composición del residuo entrante (estacionalidad de la poda y de la
   FORSU) y calendario de volteos hacen que un año de datos de emisión no represente al siguiente.
   El **año meteorológico completo** cubre la variabilidad atmosférica, **no la de la emisión**.

7. ⚠️ **Criterio aplicable: no existe uno solo.** Convergen en **3 ou_E/m³ al P98 horario** el Decreto
   185/2025 de Canarias (Categoría 1) y el criterio EA/EPA-IE para compostaje de verde bien aireado, pero
   este último baja a **1,5 ou_E/m³** si el sustrato no es vegetal. **La elección del criterio debe
   justificarse por jurisdicción y por sustrato, y declararse en la sección 1 del informe.**
