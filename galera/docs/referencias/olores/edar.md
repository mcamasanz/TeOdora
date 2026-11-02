---
tipo: olores-edar
fuente: mixta
contaminantes: [ou_E, H2S, NH3]
estadistico: percentil-98
umbral: 3 ou_E/m³ (Canarias D.185/2025, Cat. 1) · ver normativa aplicable
ambito: España + UE
anio: 2026
origen: vigilancia tecnológica
---

# EDAR — estudio de olores

> Una EDAR es, para un modelo de dispersión, **un conjunto de fuentes de área pasivas a ras de suelo**
> más unas pocas chimeneas de desodorización. El 80 % del olor sale de la cabecera (pretratamiento,
> desarenado) y de la línea de fangos, no del reactor biológico. Y como el máximo cae pegado a la
> fuente, **la altura de emisión que asignes a cada tanque decide el resultado más que la meteorología**.

---

## A. CÓMO MODELAR → para el agente 1

### A.1 Focos típicos y cómo representarlos

La EDAR se modeliza foco a foco. La regla general: **todo lo que sea una lámina de agua o fango
descubierta es una fuente de ÁREA (AREAPOLY); todo lo que esté cubierto y aspirado sale por una
chimenea y es una fuente PUNTUAL.**

| Unidad de proceso | Tipo de fuente | Altura de emisión típica | Notas |
|---|---|---|---|
| **Pozo de gruesos / bombeo agua bruta** | Área (o puntual si está en edificio aspirado) | Cota de la lámina de agua; suele estar **enterrada** (altura negativa respecto a rasante → usar 0 y elevar el terreno, ver A.3) | 🔴 **Dominante.** Turbulencia de caída → *stripping* de H₂S |
| **Desbaste de gruesos / tamizado** | Área (canales) | Cota lámina, ~0–1 m | 🔴 **Dominante.** Superficie pequeña pero factor muy alto |
| **Desarenador-desengrasador** | Área | Cota lámina, ~0,5–1,5 m | 🔴 **Dominante.** Aireado → arrastre forzado. Superficie ya considerable |
| **Decantación primaria** | Área (círculo → polígono ≤20 vértices) | Cota del vertedero perimetral | 🔴 **El foco individual mayor** en la mayoría de EDAR: factor alto × superficie muy grande |
| **Reactor biológico / aireación** | Área | Cota lámina | Factor por m² **bajo** (aerobio), pero superficie enorme → contribuye por extensión. Zona anóxica ≈ 1,7× la óxica |
| **Decantación secundaria** | Área | Cota del vertedero perimetral | Factor bajo. Sólo importa por superficie |
| **Espesador de fangos (gravedad)** | Área | Cota lámina | 🔴 **Dominante en la línea de fangos.** Factor comparable al pozo de gruesos |
| **Deshidratación de fangos (centrífugas)** | Puntual (edificio aspirado) | Chimenea de la desodorización | Casi siempre confinado. Si no lo está, es un problema serio |
| **Almacenamiento de fangos (silos, tolvas)** | Puntual si es silo cerrado y aspirado; área si es era/depósito abierto | Boca del silo / cota de la lámina | 🔴 Factor volumétrico **el más alto de toda la planta** (57.162 uo_E/m³, ver A.2) |
| **Biofiltro / lavador / carbón activo** | Área activa (biofiltro abierto) o **puntual** (unidad canalizada) | Superficie del lecho / altura de chimenea | Es una fuente **residual**, no cero. Un biofiltro degradado emite más que lo que evita |

**Cuáles dominan.** Coincidencia entre las tres fuentes independientes consultadas:

- **Cabecera** (pozo de gruesos, desbaste, desarenado) y **decantación primaria**.
- **Línea de fangos** (espesado, silos, deshidratación).
- El reactor biológico y la decantación secundaria emiten **poco por m²** y sólo pesan si su superficie
  es muy grande y está descubierta.

> González et al. (2022), sobre una EDAR real de Barcelona: *«las principales fuentes de emisión fueron
> el tanque de recepción, la salida del desarenador y el decantador primario, siendo este último el más
> significativo»*. Capelli et al. (2009), sobre **17 EDAR italianas**: *«las mayores fuentes de emisión
> de olor fueron los pretratamientos y los decantadores primarios»*.

> **Aviso de tamaño.** AREAPOLY admite **máximo 20 vértices**. Un decantador circular se discretiza con
> 12–16 vértices sin error apreciable. No gastes vértices en detallar el vertedero.

---

### A.2 Datos de emisión

#### A.2.1 Factores de emisión superficiales — la tabla utilizable ✅ VERIFICADA

Ésta es la única tabla de factores de emisión de olor **por unidad de proceso de EDAR y por metro
cuadrado** que se ha localizado en un documento público español. Procede del estudio preoperacional de
olores de las futuras **EDAR Sur, Butarque y La China (Madrid)**, redactado por **LABAQUA S.A.** para
CYGSA (informe 20097263_ed2, 22/07/2020), publicado por el MITECO en información pública. Los factores
*«han sido calculados a partir de los numerosos estudios olfatométricos de impacto ambiental por olores
realizados por LABAQUA en un periodo de 20 años en instalaciones similares»*, con el número de
depuradoras que respalda cada valor.

**Fuente:** [Estudio preoperacional de impacto ambiental mediante modelización de la dispersión
atmosférica de las futuras EDARs Sur, Butarque y China (Madrid) — MITECO, Tabla 5.2](https://www.miteco.gob.es/content/dam/miteco/es/agua/participacion-publica/ap07_tcm30-512191.pdf)

| Unidad de proceso | Factor original (uo_E/h·m²) | **→ ou_E/(s·m²)** | Respaldo experimental |
|---|---:|---:|---|
| Pozo de gruesos | 48.788 | **13,55** | 7 depuradoras (entradas de agua bruta) |
| Bombeo de agua bruta | 48.788 | **13,55** | ídem |
| Zona tratamiento fosas sépticas | 48.788 | **13,55** | ⚠️ Sin datos propios; asimilado al pozo de gruesos |
| Canales de desbaste grueso | 33.570 | **9,32** | 8 depuradoras |
| Canales de tamizado | 33.570 | **9,32** | ⚠️ Asimilado al desbaste |
| Contenedores | 33.570 | **9,32** | ⚠️ Asimilado al desbaste |
| Cámara de llegada | 33.570 | **9,32** | ⚠️ Asimilado al desbaste |
| **Desarenado-desengrasado** | 34.958 | **9,71** | **42 depuradoras** ← el mejor respaldado |
| **Decantación primaria** | 28.268 | **7,85** | **46 decantadores primarios** |
| Reactor biológico — zona anóxica | 12.482 | **3,47** | 37 datos experimentales |
| Reactor biológico — zona óxica | 7.364 | **2,05** | 70 datos experimentales |
| Decantación secundaria | 4.017 | **1,12** | 46 decantadores secundarios |
| **Espesador de fangos / depósito de fangos** | 37.765 | **10,49** | 10 espesadores (depósitos asimilados) |
| Tratamiento terciario | 1.518 | **0,42** | 3 depuradoras |

> **Conversión aplicada:** ou_E/(s·m²) = (uo_E/h·m²) ÷ 3600. Es una conversión de unidades exacta, no una
> estimación. **Estos son los números que entran directamente en el campo de caudal por m² de AREAPOLY.**

#### A.2.2 Factores volumétricos — para edificios aspirados (fuente PUNTUAL)

Cuando la unidad está confinada en un edificio con extracción, el factor **no es por m² sino por m³ de
aire extraído**. Se multiplica por el caudal de aspiración para obtener uo_E/h, y de ahí el caudal de la
chimenea. Misma fuente (Tabla 5.2):

| Unidad | Factor (uo_E/m³ de aire extraído) | Respaldo |
|---|---:|---|
| **Silos de fangos** | **57.162** | 3 depuradoras ← el valor más alto de la planta |
| Edificio de pretratamiento (aspiración general) | 1.142 | 4 depuradoras |
| Edificio de tamizado de fangos | 8.435 | 30 depuradoras (entrada a desodorización) |
| Edificio de centrífugas de fangos | 8.435 | ídem |
| Edificio de tratamiento primario | 44 | 1 sola depuradora ⚠️ |

#### A.2.3 Factores referidos al agua tratada — para contraste, NO para AREAPOLY

⚠️ **Atención a la unidad.** Existe una segunda familia de factores, muy citada en la literatura, expresada
en **ou_E por m³ de agua influente** (ou_E·m⁻³_inf). **No son ou_E/m³ de aire y no sirven para alimentar el
modelo directamente.** Sirven para verificar el orden de magnitud del total de la planta.

| Fuente | Valor | Unidad | Referencia |
|---|---:|---|---|
| Capelli et al. (2009) — sedimentación primaria | 1,9 × 10⁵ | ou_E·m⁻³_inf | [PubMed 19232669](https://pubmed.ncbi.nlm.nih.gov/19232669/) |
| Capelli et al. (2009) — primeras etapas (rango) | 1,1 × 10⁴ – 1,9 × 10⁵ | ou_E·m⁻³_inf | ídem |
| Capelli et al. (2009) — etapas posteriores (rango) | 7,4 × 10³ – 4,3 × 10⁴ | ou_E·m⁻³_inf | ídem |
| Capelli et al. (2009) — OEF global, 17 EDAR italianas de 1.000 a 800.000 m³/d | 2,20 × 10⁴ – 1,82 × 10⁵ | ou_E·m⁻³_inf | citado en González et al. 2022 |
| **González et al. (2022) — OEF global, EDAR MBR Barcelona (33.000 m³/d)** | **9,90 × 10⁴** | ou_E·m⁻³_inf | [J. Environ. Manage. 313:115002](https://doi.org/10.1016/j.jenvman.2022.115002) |

> Que el OEF global de una EDAR española real (9,9 × 10⁴) caiga justo en mitad del rango italiano
> (2,2 × 10⁴ – 1,8 × 10⁵) es un buen control de sanidad. **Úsalo como test:** calcula el total de tu
> modelo en ou_E/s, divídelo por el caudal influente en m³/s, y comprueba que cae en ese rango.

#### A.2.4 Concentraciones de olor y de compuestos trazadores medidas en superficie ✅ VERIFICADAS

Útiles cuando modelizas en **µg/m³ de H₂S** en lugar de ou_E, o para dimensionar una desodorización.
Todas de [González et al. (2022)](https://doi.org/10.1016/j.jenvman.2022.115002), muestreo con **cámara
de flujo (flux chamber) USEPA**, EDAR MBR de Barcelona, campañas abril–agosto 2018:

| Magnitud | Valor medido | Dónde |
|---|---|---|
| Concentración de olor máxima | **2.578 ou_E/m³** | Superficie del decantador primario |
| Concentración de olor | **2.025 ou_E/m³** | Desarenador |
| H₂S | **0,6 – 1,0 ppm_v** | Superficie del decantador primario |
| NH₃ | **4,5 – 7 ppm_v** | Salida de desbaste y desarenador |
| COV totales | 1,9 – 2,3 ppm_v eq. isobutileno | Tanque de recepción |
| Factor de emisión NH₃ | 1,70 × 10⁻¹ g NH₃·m⁻³_inf (1,84 g NH₃/kg N_total inf) | Global planta |
| Factor de emisión H₂S | 5,08 × 10⁻² g H₂S·m⁻³_inf | Global planta |

Capelli et al. (2009), 17 EDAR italianas: concentraciones medias en pretratamientos y decantadores
primarios de **1.490 a 3.840 ou_E/m³** — coherente con lo anterior.

---

### A.3 Parámetros de modelización

#### A.3.1 Altura de emisión — el parámetro crítico

**El equipo ha medido que pasar de 1 m a 6 m de altura de emisión cambia el máximo en un factor ×12.**
No hay ningún otro parámetro del estudio con esa palanca. Consecuencias prácticas:

1. **La altura no se pone «a ojo».** Se toma de los planos de la planta: cota de la lámina de agua
   respecto a la rasante del terreno en ese punto.
2. **En un tanque abierto con muros, el olor escapa por la coronación del muro,** no por el nivel del
   líquido. El resguardo (*freeboard*) típico es de 0,2–0,5 m por debajo de la coronación. La convención
   defendible es **usar la cota de la lámina** y, si el muro sobresale mucho, tratarlo como reducción de
   la dispersión inicial, no como aumento de altura. ⚠️ No se ha localizado guía normativa que fije esta
   convención; **documenta la que elijas y haz un análisis de sensibilidad.**
3. **Estructuras enterradas** (pozo de gruesos, bombeos): la lámina está *por debajo* de la rasante.
   AERMOD no admite alturas negativas. Se pone **altura 0** y se acepta el conservadurismo.
4. **Haz siempre un caso alternativo** con la altura ± 1 m y reporta la horquilla. Con un ×12 en 5 m de
   rango, un informe que da una sola cifra sin sensibilidad no es defendible.

| Unidad | Altura de emisión de partida (a confirmar con planos) |
|---|---|
| Pozo de gruesos, bombeos (enterrados) | 0 m |
| Canales de desbaste / tamizado | 0 – 1 m |
| Desarenador-desengrasador | 0,5 – 1,5 m |
| Decantador primario / secundario | Cota del vertedero perimetral (típ. 1 – 3 m) |
| Reactor biológico | Cota de la lámina (típ. 0,5 – 2 m sobre rasante) |
| Espesador de gravedad | Cota del vertedero (típ. 2 – 4 m) |
| Chimenea de desodorización | Altura real de chimenea — **fuente puntual** |

#### A.3.2 Por qué temperatura y velocidad de salida son irrelevantes aquí

**Porque AERMOD no te los pide.** Una fuente de área (`AREA` / `AREAPOLY` / `AREACIRC`) sólo acepta
tres cosas: **caudal por unidad de superficie, altura de emisión y, opcionalmente, la dispersión
vertical inicial σ_z0**. No hay campo de temperatura ni de velocidad de salida, porque **no hay
sobreelevación de penacho**: una lámina de agua a 15–20 °C no tiene ni empuje térmico ni cantidad de
movimiento vertical. El gas odorífero sale por difusión y arrastre del viento, y **se queda a ras de suelo**.

Esto explica el hallazgo del equipo de que en fuentes de área pasivas **el máximo cae pegado a la
fuente**: sin sobreelevación no hay «distancia de despegue» del penacho, así que la concentración
máxima está en el propio borde del foco y decae monótonamente. Es exactamente lo contrario de una
chimenea caliente, cuyo máximo aparece a cientos de metros.

**Corolario operativo:** temperatura y velocidad **sólo** se rellenan en los focos puntuales — las
chimeneas de biofiltro, biotrickling o lavador. Ahí sí importan, y ahí sí conviene medirlas.

⚠️ **σ_z0 (dispersión vertical inicial):** algunos consultores la usan para representar el efecto de los
muros del tanque. No se ha localizado convención normativa; si la usas, justifícala y documenta el
valor. Por defecto, dejarla en 0 es lo conservador.

#### A.3.3 Periodo, meteorología y receptores

- **Periodo: un año natural completo, horario.** No es una recomendación, es aritmética: el criterio es
  el **percentil 98 de las medias horarias de un año**, y el P98 sobre menos de 8.760 horas no es el P98.
  El Decreto canario 185/2025 lo dice literalmente («a lo largo de un año natural»).
- **Salida:** medias horarias en ou_E/m³, post-procesadas al P98.
- **Receptores:** malla en el entorno **más receptores discretos en los núcleos habitados**, viviendas
  aisladas y usos sensibles (colegios, hospitales, zonas recreativas). La altura de receptor habitual en
  estudios de olor es **1,5–1,7 m** (altura de la nariz); el estudio de olores.org sobre EDAR usa
  *flagpole* de **1,7 m**.
- **Resolución de malla:** fina cerca del vallado. Como el máximo cae pegado a la fuente, una malla de
  100 m se salta el gradiente entero. El estudio de olores.org sobre EDAR usa celdas de **2,5 × 2,5 m**
  en el recinto.
- **Terreno y rugosidad:** AERMAP + rugosidad realista. Una EDAR suele estar en vega fluvial, terreno
  llano — el terreno importa menos que en otros estudios, pero la rugosidad sí, porque gobierna la
  dispersión a ras de suelo, que es donde está todo el olor.

---

### A.4 Errores típicos

| Error | Por qué es grave | Qué hacer |
|---|---|---|
| **Convertir masa → ou_E en una mezcla real** | El olor de una EDAR es una mezcla de H₂S, mercaptanos, aminas, COV y NH₃ con efectos **no aditivos y sinérgicos**. No existe factor de conversión µg H₂S → ou_E válido para una mezcla. El H₂S explica sólo parte del olor | Modeliza **en ou_E directamente**, con factores de emisión olfatométricos (A.2.1). Si necesitas H₂S, modelízalo **como contaminante aparte**, no como sustituto del olor |
| **Modelar tanques como fuente puntual** | Un decantador de 3.000 m² tratado como un punto concentra toda la emisión en un lugar, genera una sobreelevación ficticia si le pones temperatura, y **desplaza el máximo lejos de la fuente** — justo al revés de la realidad | AREAPOLY siempre. Un punto sólo para chimeneas de desodorización |
| **Olvidar el factor pico-media** | El modelo da **medias horarias**; la nariz percibe en **5 s**. Los picos instantáneos son mayores que la media horaria. En Italia el factor es **2,3** de forma unánime | Ver [criterios internacionales](../normativa/criterios_olor_internacional.md) y [metodología](../metodologia/olores_metodologia.md). Declara si tu umbral ya lo incorpora o no |
| **Menos de un año de meteorología** | El P98 anual con 3 meses de datos no es el P98 anual. Es rechazable de plano | Año natural completo |
| **Altura de emisión a ojo** | ×12 entre 1 y 6 m | Planos + análisis de sensibilidad (A.3.1) |
| ⚠️ **No incluir el aire de los difusores en el SOER de un tanque aireado** | En un reactor con aireación, el caudal de barrido de la campana **no es el único caudal**: los difusores inyectan aire que arrastra olor. Si se ignora, «el SOER (y en consecuencia el OER) se ve significativamente afectado» | Sumar el caudal de los difusores al balance de la campana |
| **Modelar la desodorización como eficacia 100 %** | Un biofiltro degradado puede bajar al 40 % (ver D). La chimenea de desodorización **es una fuente**, no un sumidero | Modelízala como foco puntual con su caudal residual |
| **Usar ou_E·m⁻³_inf como si fueran ou_E/m³ de aire** | Difieren en órdenes de magnitud. Es un error de unidades catastrófico | Ver el aviso de A.2.3 |
| **Asumir que la cabecera confinada no emite** | Si está aspirada, emite por la chimenea. Si la aspiración es insuficiente, emite además por rendijas y puertas | Balance de caudales |

---

## B. ESTRUCTURA DEL INFORME → para el agente 2

Estructura extraída del informe real de LABAQUA S.A. para las EDAR Sur, Butarque y La China de Madrid
([MITECO, informe 20097263_ed2](https://www.miteco.gob.es/content/dam/miteco/es/agua/participacion-publica/ap07_tcm30-512191.pdf),
73 páginas). Es un estudio olfatométrico preoperacional completo, aceptado en información pública.

| § | Sección | Contenido | Tablas / figuras |
|---|---|---|---|
| **1** | **Introducción** | Quién encarga, qué se evalúa, sobre qué base (factores de emisión de plantas similares + datos de diseño + meteorología y orografía locales) | — |
| **2** | **Antecedentes** | **Clave: de dónde sale el criterio de evaluación.** Aquí se cita la resolución de AAI/autorización que fija el valor objetivo de inmisión y la obligación de estudio olfatométrico UNE-EN 13725 periódico | Tabla del valor objetivo de inmisión y su estadístico |
| **3** | **Objetivo del estudio** | Las 4 actividades: (a) identificación de focos, (b) estimación de la emisión por foco, (c) modelización de la inmisión y curvas de isoconcentración, (d) interpretación frente a los niveles guía | Lista de actividades |
| **4** | **Información de la planta** | 4.1 Localización y **receptores cercanos**; 4.2 Descripción de las instalaciones (línea de agua y línea de fangos) | Fig.: ortofoto con la planta y los receptores próximos identificados y acotados. Tabla de receptores |
| **5** | **Cálculo de la emisión de olor** | 5.1 Justificación del uso de factores de emisión (precedente EPA e Infomil); 5.2 **Tabla de factores de emisión** con nota al pie del respaldo experimental de cada uno; 5.3–5.5 Emisiones teóricas por foco: superficie, caudal de extracción, rendimiento de desodorización, emisión de salida | **Tabla de factores de emisión** (uo_E/h·m² y uo_E/m³). **Tabla de cálculo por foco**: factor × superficie / caudal → emisión (10⁶ uo_E/h) → rendimiento desodorización (%) → emisión de salida y Q de salida. **Tabla de asignación de cada unidad a su equipo de desodorización** |
| **6** | **Modelización de la inmisión de olor** | 6.1 Descripción del modelo; 6.2 Procedimiento: meteorología (modelo meteorológico + dominios anidados), topografía y usos del suelo, **datos de receptores** (malla), y resultados | Fig.: dominios meteorológicos anidados. Fig.: campos de viento a 10 m en fechas representativas. Fig.: módulo de definición de la malla de receptores. **Figs. de isodoras sobre ortofoto (2D) y sobre ortofoto en 3D**, una pareja por instalación |
| **7** | **Interpretación de resultados y conclusiones** | 7.1 Molestias causadas en el entorno, **una subsección por instalación**: se recuerda el valor objetivo aplicable, se indica **hasta dónde llega la isodora del umbral en metros y por qué rumbo**, y se concluye si alcanza o no núcleos de población. Se explica la causa física de las diferencias entre plantas | Referencia cruzada a las figuras de isodoras |
| **Anexo I** | **Referencias de legislación en materia de olores** | Marco normativo y niveles guía nacionales e internacionales | Tabla de criterios por país |
| **Anexo II** | **La olfatometría: descripción y metodología** | UNE-EN 13725, definición de ou_E, panel, olfatómetro | Esquemas |
| **Anexo III** | **Modelización de la inmisión: detalle del modelo** | Formulación, configuración y ficheros de entrada | Capturas de configuración |

**Cómo se redactan las conclusiones (literal del informe, buen modelo a imitar):**

> *«la curva 7 uo_E/m³ percentil 98 incide a 350 metros en dirección noroeste al perímetro de la futura
> instalación, 250 metros en dirección noreste y a 125 metros en dirección oeste. La curva 7 uo_E/m³
> percentil 98 no alcanza núcleos de población urbanos.»*

Y, muy importante, **se explica la causa física de la diferencia entre plantas**:

> *«El mayor radio de alcance de las curvas isodoras de la futura EDAR Sur respecto a las futuras EDAR
> China y Butarque es debido a la gran superficie de exposición que tienen los reactores biológicos y la
> decantación secundaria que están proyectadas sin cubrición.»*

> **Nota de conceptos:** el informe distingue explícitamente **generación** (concentración en la fuente,
> ou_E/m³), **emisión** (caudal de olor, ou_E/h) e **inmisión** (concentración en el entorno, ou_E/m³).
> Mantener esos tres términos separados evita la mitad de las confusiones de un informe de olor.

**Añadidos recomendados** que el informe de referencia no trae y hoy serían exigibles:

- **Análisis de sensibilidad a la altura de emisión** (×12; ver A.3.1) y **al caudal Q**.
- **Declaración explícita del factor pico-media** aplicado o no aplicado.
- **Rosa de vientos** del año modelizado y justificación de su representatividad.

---

## C. NORMATIVA APLICABLE

Marco completo en [`../normativa/marco_normativo_ES_UE.md`](../normativa/marco_normativo_ES_UE.md) y
criterios extranjeros en [`../normativa/criterios_olor_internacional.md`](../normativa/criterios_olor_internacional.md).
Aquí sólo lo específico de EDAR.

### C.1 Canarias — la EDAR es Categoría 1 → **3 ou_E/m³**

El **Decreto 185/2025, de 10 de diciembre, de protección de la atmósfera de Canarias** (en vigor desde
el 19/12/2025) lista en su art. 6.2, dentro de la **Categoría 1 (molestia alta)**, de forma literal:
**«tratamiento de aguas residuales e instalaciones accesorias»**.

| | |
|---|---|
| Categoría | **1 — molestia alta** |
| Valor objetivo de inmisión | **3 ou_E/m³** |
| Estadístico | **Percentil 98 de las medias horarias, año natural** |

Es el criterio **más exigente** de los que aparecen en este documento, y el único **jurídicamente
vinculante** para una EDAR en España. Añade además la obligación de **plan de minimización** de emisiones
odoríferas (arts. 11 y 12) y faculta al órgano competente a exigir un estudio específico de emisión y
dispersión de olores. Detalle y cita literal en el marco normativo.

### C.2 Fuera de Canarias — el criterio se fija en la autorización ambiental

No hay norma estatal ni, salvo Canarias, autonómica con valores numéricos. En la práctica **el umbral lo
fija la propia autorización ambiental de la planta**. Precedente español documentado y directamente
aplicable a EDAR:

> **Comunidad de Madrid.** Las resoluciones de la Dirección General de Evaluación Ambiental que otorgan
> la autorización de la Ley 34/2007 a la **EDAR La China** (10/12/2014) y a la **EDAR Butarque**
> (28/10/2014) fijan, para la actividad *«Sistemas de saneamiento de aguas residuales»*, un **valor
> objetivo de inmisión de 7 uo_E/m³ al percentil 98 de las medias horarias de un año**, y obligan a
> realizar un estudio olfatométrico según **UNE-EN 13725 cada 3 años**, coincidiendo con los controles
> externos de emisión.

**Comparativa de criterios aplicables a una EDAR:**

| Referencia | Umbral | Estadístico | Naturaleza |
|---|---:|---|---|
| **Canarias, D. 185/2025 (Cat. 1)** | **3 ou_E/m³** | P98 medias horarias, año natural | ✅ Norma vigente |
| Comunidad de Madrid, AAI EDAR La China / Butarque | 7 uo_E/m³ | P98 medias horarias, año | ✅ Condición de autorización (caso concreto) |
| Italia — factor pico-media 2,3 sobre P98 | — | P98 anual | Ver [criterios internacionales](../normativa/criterios_olor_internacional.md) |
| Países Bajos | — | Competencia municipal desde 1/1/2024 | ⚠️ NeR y Wgv **derogadas** — no citar de memoria |

> **Criterio práctico.** Si el proyecto está en Canarias: **3 ou_E/m³ al P98, sin discusión**. Fuera de
> Canarias: buscar primero el condicionado de la AAI; si no dice nada, presentar las isodoras de **3, 5 y
> 7 ou_E/m³ al P98** (que es lo que hace el informe de Madrid) y razonar frente a las tres.

### C.3 Norma de medida

**UNE-EN 13725** (olfatometría dinámica). Su **revisión de 2022** es relevante aquí: incorpora
explícitamente la **tasa de emisión de olor** y cubre focos canalizados, **fuentes de área activas**
(p. ej. biofiltros) y **fuentes pasivas** — es decir, da cobertura normativa a tratar una lámina de agua
de EDAR como fuente de área, que es justo lo que hace AREAPOLY. La versión de 2003/2004 dejaba las
superficies mucho menos definidas.

---

## D. MEDIDAS CORRECTORAS

La cadena es siempre la misma: **cubrir → captar → tratar → emitir por chimenea**. Cada eslabón hace algo
distinto y el último es el que más cambia el resultado del modelo.

### D.1 Cubrición y captación

Cubrir un tanque **no reduce la emisión: la traslada**. El olor que salía por 3.000 m² de lámina pasa a
salir por un conducto. Lo que se gana es que ahora **es tratable** y que **sale por una chimenea elevada**.
Ejemplos reales del informe de Madrid: decantación lamelar confinada con **10.800 m³/h** de extracción
sobre 720 m²; desarenado-desengrasado con **4.400 m³/h** sobre 440 m² (≈ 10 m³/h por m² de lámina).

### D.2 Tratamiento — eficacias

| Tecnología | Eficacia | Condiciones / fuente |
|---|---:|---|
| **Biofiltro avanzado** | **95 %** | Dato de proveedor recogido en el informe de Madrid, **válido sólo si la concentración de entrada es < 10.000 uo_E/m³** — [MITECO](https://www.miteco.gob.es/content/dam/miteco/es/agua/participacion-publica/ap07_tcm30-512191.pdf) |
| **Biotrickling (biofiltro percolador)** | **80 %** | ídem, misma condición de entrada |
| Biofiltro real, EDAR A | **98 %** | 7.351 → 136 ou_E/m³ — [olores.org](https://www.olores.org/es/tecnicas/olfatometria-dinamica/497-formacion-y-cuantificacion-de-emisiones-de-olor-en-estaciones-depuradoras-de-aguas-residuales) |
| Biofiltro real, EDAR B | **97 %** | 11.527 → 347 ou_E/m³ — ídem |
| Biofiltro real, EDAR C | **40 %** ⚠️ | 8.843 → 5.256 ou_E/m³ — **mismo tipo de equipo, mal operado.** ídem |
| Biofiltro bien operado (rango de salida) | >90 %, salida 200–5.000 ou_E/m³ | ídem |
| ⚠️ Carbón activo granular impregnado (NaOH/KOH), sobre H₂S | 90–100 % si entrada < 500 ppm; 80–90 % si entrada > 1.000 ppm | Dato de literatura comercial; **no verificado sobre fuente primaria**. Trata H₂S preferentemente, no la mezcla completa |
| Lavador químico | ⚠️ **No verificada** | Ver apartado F |

> 🔴 **El dato más importante de esta tabla es el 40 %.** Tres biofiltros del mismo tipo, en tres EDAR,
> con eficacias de 98 %, 97 % y 40 %. **La eficacia de un biofiltro no es una propiedad del equipo, es
> una propiedad de su operación y mantenimiento.** En un estudio prospectivo, usar el 95 % del catálogo
> sin más es optimista; conviene modelizar también un escenario degradado.

### D.3 El efecto de convertir una fuente de área en puntual elevada

Es, con diferencia, **la medida correctora con más efecto sobre el resultado del modelo**, y por una
razón puramente física:

| | Fuente de área pasiva (tanque abierto) | Fuente puntual elevada (chimenea de desodorización) |
|---|---|---|
| Altura de emisión | 0–3 m | 10–20 m o más |
| Sobreelevación de penacho | **Ninguna** (sin temperatura ni velocidad) | Sí (velocidad de salida del ventilador) |
| Dónde cae el máximo | **Pegado a la fuente** | A cientos de metros, muy diluido |
| Dilución antes de llegar al vallado | Mínima | Grande |

Se acumulan **tres efectos multiplicativos**: (1) la eficacia del tratamiento reduce el caudal de olor
(×0,05 con un biofiltro al 95 %); (2) la altura sube de ~1 m a ~15 m, y la sensibilidad medida por el
equipo (×12 entre 1 y 6 m) indica que ese salto por sí solo vale otro orden de magnitud; (3) aparece
sobreelevación de penacho, que aleja y diluye el máximo.

**Contrapartida honesta:** cubrir concentra el olor. Si el sistema de tratamiento falla o se satura, se
pasa de una emisión difusa y moderada a **una emisión concentrada en un punto**. Por eso conviene
modelizar el escenario de fallo.

> El informe de Madrid ilustra el efecto contrario con un caso real: la EDAR Sur, con **reactores
> biológicos y decantación secundaria proyectados SIN cubrición**, extiende su isodora de 7 uo_E/m³ a un
> radio de **1.500 m**, frente a los 350 m de Butarque y a la no aparición de la curva en La China, ambas
> con esas unidades confinadas.

---

## E. FUENTES

| # | Fuente | Qué aporta | Estado |
|---|---|---|---|
| 1 | **LABAQUA S.A. / CYGSA (2020).** *Estudio preoperacional de impacto ambiental mediante modelización de la dispersión atmosférica de las futuras EDARs Sur, Butarque y China (Madrid).* Informe 20097263_ed2, 22/07/2020. [PDF MITECO](https://www.miteco.gob.es/content/dam/miteco/es/agua/participacion-publica/ap07_tcm30-512191.pdf) | **Tabla de factores de emisión por unidad de proceso** (A.2.1, A.2.2), estructura de informe (B), criterio de Madrid 7 uo_E/m³ (C.2), eficacias de desodorización (D.2) | ✅ Documento completo leído |
| 2 | **González, D.; Colón, J.; Sánchez, A.; Gabriel, D. (2022).** *Multipoint characterization of the emission of odour, volatile organic compounds and greenhouse gases from a full-scale membrane-based municipal WWTP.* J. Environ. Manage. 313:115002. [doi:10.1016/j.jenvman.2022.115002](https://doi.org/10.1016/j.jenvman.2022.115002) (open access, CC BY) | OEF global 9,9×10⁴ ou_E·m⁻³_inf, concentraciones y factores de H₂S/NH₃/COV, jerarquía de focos, método de cámara de flujo USEPA | ✅ Artículo completo leído |
| 3 | **Capelli, L.; Sironi, S.; Del Rosso, R.; Céntola, P. (2009).** *Predicting odour emissions from wastewater treatment plants by means of odour emission factors.* Water Research 43(7):1977–1985. [doi:10.1016/j.watres.2009.01.022](https://doi.org/10.1016/j.watres.2009.01.022) · [PubMed 19232669](https://pubmed.ncbi.nlm.nih.gov/19232669/) | OEF por etapa sobre 17 EDAR italianas (A.2.3), confirmación de que dominan pretratamiento y decantación primaria | ✅ Abstract y datos citados verificados |
| 4 | **olores.org** — *Formación y cuantificación de emisiones de olor en EDAR.* [enlace](https://www.olores.org/es/tecnicas/olfatometria-dinamica/497-formacion-y-cuantificacion-de-emisiones-de-olor-en-estaciones-depuradoras-de-aguas-residuales) | Eficacias reales de biofiltros en 3 EDAR (98/97/40 %), jerarquía de focos | ✅ Leído |
| 5 | **olores.org** — *Dispersion modelling as a tool for assessment and management of odour emissions from a WWTP.* [enlace](https://olores.org/en/techniques/dispersion-modelling/1146-dispersion-modelling-as-a-tool-for-assessment-and-management-of-odour-emissions-from-a-wastewater-treatment-plant) | Configuración AERMOD para EDAR: malla 2,5×2,5 m, flagpole 1,7 m, dispersión rural, resolución horaria | ✅ Leído |
| 6 | **Decreto 185/2025, de 10 de diciembre, de protección de la atmósfera de Canarias.** BOC 250, 18/12/2025 | Categoría 1 = tratamiento de aguas residuales → 3 ou_E/m³ al P98 | ✅ Vía [marco normativo](../normativa/marco_normativo_ES_UE.md) (verificado sobre BOC) |
| 7 | **UNE-EN 13725** (rev. 2022) | Olfatometría dinámica; cobertura de fuentes de área pasivas | ✅ Vía [marco normativo](../normativa/marco_normativo_ES_UE.md) |
| 8 | *Evaluation of the Odour Emission Rate from Wastewater Aerated Tanks: a Methodological Approach* | Definición de SOER = C_od · Q_out / A_hood; campana alemana (0,5 m², 6,4 cm/s) vs. italiana (2.500 L/h); necesidad de incluir el caudal de los difusores | ⚠️ Sólo resumen de búsqueda; texto completo no accedido |

**Documentos hermanos de esta biblioteca:**
[marco normativo ES/UE](../normativa/marco_normativo_ES_UE.md) ·
[criterios de olor internacionales](../normativa/criterios_olor_internacional.md) ·
[metodología de olores](../metodologia/olores_metodologia.md) (en redacción)

---

## F. INCERTIDUMBRES Y AVISOS

### F.1 El caudal Q es la mayor fuente de error del estudio

Lo ha medido el equipo y la bibliografía lo confirma. Concretamente, en una EDAR:

- Los factores de A.2.1 son **medias de campañas en decenas de plantas distintas**. La dispersión real
  entre plantas es de **al menos un orden de magnitud**: los OEF globales de Capelli van de
  2,2×10⁴ a 1,8×10⁵ ou_E·m⁻³_inf, un **factor 8 entre EDAR reales**.
- Varios factores de la tabla **no tienen datos propios** y están asimilados por analogía (fosas
  sépticas, canales de tamizado, contenedores, cámara de llegada, depósitos de fangos). Están marcados
  ⚠️ en A.2.1.
- El factor del **edificio de tratamiento primario (44 uo_E/m³)** se basa en **una sola planta**.
- **El olor de una EDAR es estacional y episódico:** la temperatura del agua, la septicidad del colector
  de llegada y las paradas de unidades lo cambian radicalmente. Un caso documentado registró
  **34,76 ou_E/(s·m²)** en un decantador primario **fuera de servicio**, frente a los 7,85 ou_E/(s·m²) de
  operación normal — **un factor 4,4 por una incidencia operativa**. ⚠️ Dato procedente de un resumen de
  búsqueda (MDPI *Atmosphere* 16(5):577); **no se pudo acceder al texto completo** (HTTP 403).

**Recomendación:** presentar siempre el resultado como **horquilla**, no como cifra única, y hacer
explícito el escenario (operación normal / incidencia / degradación de la desodorización).

### F.2 Datos NO verificados — no usar sin comprobar

| Dato | Problema |
|---|---|
| **Eficacia del lavador químico** | ❌ **No se ha localizado ninguna cifra en fuente primaria.** No se da valor. Hay que pedirla al proveedor con ensayo |
| Eficacias del carbón activo (90–100 % / 80–90 % sobre H₂S) | ⚠️ Proceden de literatura comercial vía resumen de búsqueda. Además son **eficacias sobre H₂S, no sobre olor total** — no son intercambiables |
| SOER 34,76 y 49,89 ou_E/(s·m²) | ⚠️ MDPI bloqueó el acceso (403). Sólo se dispone del resumen de búsqueda |
| OER por unidad citados como 62.100 / 55.800 / 88.400 / 11.300 ou_E/s | ❌ Aparecieron en un resumen de búsqueda pero **no se pudo confirmar a qué publicación pertenecen**. **No se han incluido en el cuerpo del documento.** No citar |
| Convención de altura de emisión para tanques con muro | ⚠️ No se ha localizado guía normativa. Lo propuesto en A.3.1 es criterio razonado, no norma |
| Uso y valor de σ_z0 en fuentes de área de EDAR | ⚠️ Sin convención localizada |

### F.3 Limitación de fondo: el modelo gaussiano y las calmas

⚠️ Aviso recogido en olores.org y relevante para una EDAR: *«para fuentes de poca altura como EDAR no es
recomendable usar un modelo gaussiano, ya que la mayoría de los episodios de olor son generados durante
calmas o velocidades de viento muy pequeñas»*. AERMOD, como modelo gaussiano estacionario, **trata mal
las calmas**, y las calmas son precisamente cuando se producen las quejas.

Es coherente con que el informe de referencia de Madrid usara **CALPUFF** (modelo lagrangiano de
puff, con CALMET/WRF) en lugar de AERMOD. **No invalida el uso de AERMOD** —es el modelo preferente de
la US EPA y el que aceptan las administraciones— pero conviene:

1. Declarar la limitación en el informe.
2. Revisar el número de horas de calma descartadas en el fichero meteorológico y reportarlo.
3. No presentar el resultado como predicción de quejas, sino como **cumplimiento de un valor objetivo
   normativo**, que es lo que realmente se está evaluando.

### F.4 Otros avisos

- **Los factores de A.2.1 son de 2020 y se basan en 20 años de campañas anteriores.** Reflejan tecnología
  de EDAR convencional. Para una EDAR de membranas (MBR) o con procesos distintos, contrastar con la
  referencia 2.
- **El P98 no es el máximo.** Un P98 de medias horarias deja fuera **175 horas al año** por encima del
  umbral. Cumplir el valor objetivo no significa ausencia de episodios de olor.
- **El factor pico-media no está resuelto en este documento.** Corresponde a
  [`../metodologia/olores_metodologia.md`](../metodologia/olores_metodologia.md), pendiente de redacción.
  Antes de comparar un resultado de AERMOD con un umbral, hay que saber si ese umbral está definido sobre
  medias horarias o sobre picos. El criterio canario y el de Madrid están definidos sobre **medias
  horarias**, así que en esos dos casos la comparación es directa.
