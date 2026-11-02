---
tipo: olores-ganaderia
fuente: mixta
contaminantes: [ou_E, NH3, H2S]
estadistico: percentil-98
umbral: 3 / 6 / 9 ou_E/m3 (P98 anual, Decreto 185/2025 Canarias; ganaderia intensiva = Categoria 2). Referencia complementaria: 2,0 / 3,0 / 8,0 / 14,0 / 20,0 / 35,0 ou_E/m3 (P98) del Bkl neerlandes, especifico de olor ganadero
ambito: España + UE
anio: 2026
origen: vigilancia tecnologica
---

# Ganadería intensiva — estudio de olores y amoniaco

> Una granja intensiva no es un foco: es un conjunto de focos de naturaleza física muy distinta (extractores puntuales, naves de ventilación natural, balsas de purín, estercoleros) que hay que representar por separado en AERMOD, y el reparto entre ellos condiciona el resultado más que la precisión de cualquier factor de emisión individual.
> Existen factores de emisión de olor por plaza publicados y trazables (normativa neerlandesa, en ou_E/s por animal) y niveles de emisión de NH₃ asociados a las MTD (Decisión (UE) 2017/302, en kg NH₃/plaza·año); ninguno de los dos está pensado para AERMOD, y su trasvase exige cautelas que se detallan en A.2.
> El cuello de botella de la herramienta hoy no es la física sino la salida: el criterio aplicable (Canarias, Países Bajos) es un **percentil 98 de medias horarias** y la herramienta sólo exporta la **media del periodo**, por lo que la comparación con umbral no puede cerrarse sin ampliar la salida (ver A.3 y F).

Documentos previos que **no** se repiten aquí y a los que hay que remitirse:

- [`../normativa/marco_normativo_ES_UE.md`](../normativa/marco_normativo_ES_UE.md) — marco español y europeo, Directiva (UE) 2024/1785, y **Decreto 185/2025 de Canarias** (3/6/9 ou_E/m³ al P98 anual; ganadería intensiva clasificada como **Categoría 2**).
- [`../normativa/criterios_olor_internacional.md`](../normativa/criterios_olor_internacional.md) — criterios de Países Bajos e Italia. Muy pertinente aquí: los **Países Bajos tienen normativa específica de olor ganadero** (Bkl art. 5.109), con valores 2,0 / 3,0 / 8,0 / 14,0 / 20,0 / 35,0 ou_E/m³ al P98 según se esté dentro o fuera del contorno de edificación y dentro o fuera de zona de concentración ganadera, modelo **V-Stacks**, y distancias fijas de 100/50 m para especies sin factor de emisión.
- [`../metodologia/olores_metodologia.md`](../metodologia/olores_metodologia.md) — relación pico-media, percentiles y umbrales de percepción.

---

## A. CÓMO MODELAR → para el agente 1

### A.1 Focos típicos y cómo representarlos

La granja se descompone en focos. La regla de oro: **un foco es puntual si el aire sale por un orificio con velocidad propia; es de área si el aire sale por difusión sobre una superficie sin momento**. El error más caro es meter toda la granja en un único polígono de área a 1 m de altura.

| Foco | Especie | Tipo de fuente AERMOD | Altura típica | Notas de modelización |
|---|---|---|---|---|
| **Extractores laterales** (ventilación forzada transversal) | Porcino cebo, avícola | **POINT**, uno por extractor o agrupados en pocos puntos equivalentes | **1,5–2,5 m** (a media altura del muro lateral) | Caso más desfavorable: descarga baja y horizontal. En AERMOD el chorro horizontal no se modela; se representa como punto vertical, lo que **sobreestima la elevación** de la pluma. Ver A.3. |
| **Extractores cenitales / chimeneas de cumbrera** | Porcino cebo moderno, avícola | **POINT** | **5–8 m** (cumbrera + tramo de chimenea) | Es el mismo caudal y la misma emisión, pero a 3–5 veces la altura: el impacto en receptor cae drásticamente (ver sensibilidad en A.3). Diferencia entre cumplir y no cumplir. |
| **Nave de ventilación natural** (ventanas, lucernario continuo, cortina lateral) | Vacuno de leche/carne, porcino tradicional, avícola campero | **AREAPOLY** con la huella de la nave, o **VOLUME** | **h ≈ altura de cumbrera** para el lucernario; **1,5–2 m** si domina la salida por cortinas laterales | Caudal muy variable y no medido. AREAPOLY admite `Release Height` e `Initial Vertical Dimension` (σ_z0): usar σ_z0 ≈ altura de la nave / 2,15 para simular el volumen ya mezclado. |
| **Balsa de purín descubierta** | Porcino, vacuno | **AREAPOLY** (máx. 20 vértices) | **0 m** (lámina) o ligeramente negativa si está excavada | Foco **pasivo**: sin momento ni empuje. Emisión por unidad de superficie, fuertemente dependiente de temperatura, viento y presencia de costra. Suele ser el segundo foco en importancia y a veces el primero en verano. |
| **Balsa cubierta** (lona, cubierta flotante, costra natural) | Porcino, vacuno | **AREAPOLY** con emisión reducida | 0 m | La cubierta es MTD (2017/302, MTD 14–16). Reducción específica de **olor** no cuantificada en la Decisión — ver D y F. |
| **Fosa bajo slat / foso interior** | Porcino | **No es foco independiente**: su emisión sale por los extractores | — | Modelarlo aparte duplicaría la emisión. Su papel es determinar la **concentración** del aire extraído, no añadir un foco. Excepción: fosa exterior con respiraderos propios. |
| **Estercolero / apilamiento de gallinaza o estiércol sólido** | Avícola, vacuno | **AREAPOLY** | **1,5–3 m** (altura media de la pila, no 0 m) | La pila tiene volumen y algo de convección térmica por el compostaje espontáneo. Modelarla a 0 m es conservador pero irreal. |
| **Silos de pienso, tolvas** | Todas | Despreciable para olor | — | Relevantes para **partículas**, no para ou_E. |
| **Sala de cadáveres / contenedor de subproductos** | Todas | **AREAPOLY** pequeña | 1–2 m | Foco pequeño en caudal pero de olor muy desagradable (alto factor hedónico). Justificar si se incluye o se excluye. |
| **Aplicación agrícola del purín en campo** | Porcino, vacuno | **AREAPOLY** sobre la parcela, **emisión intermitente** | 0 m | Foco de muy alta intensidad y muy corta duración (horas-días). No pertenece al escenario anual continuo: modelar como **escenario separado** si las parcelas de aplicación están en el ámbito. Con abanico/plato la emisión es máxima; con inyección o tubos colgantes cae mucho. |
| **Sistema de tratamiento / separador de fases / balsa de digestato** | Porcino con planta de biogás | **AREAPOLY** + POINT (antorcha, venteos) | Variable | Si hay digestión anaerobia, el olor del digestato es menor que el del purín crudo, pero aparecen venteos puntuales. |

**Diferencias por especie, en una frase cada una:**

- **Porcino** — el caso más exigente. Emisión de olor por plaza alta, gran peso de la balsa de purín, y la mayor parte de la emisión sale por ventilación forzada. Es el único subsector con normativa estatal específica de ordenación (RD 306/2020).
- **Avícola** — emisión de olor por plaza baja (dos órdenes de magnitud por debajo del cerdo, ver A.2) pero con **decenas de miles de plazas**, de modo que el total es comparable. Cama sobre yacija: el estiércol es sólido, no hay balsa; el foco secundario es el **estercolero de gallinaza** y la operación de vaciado al final del lote (pico de emisión de pocas horas).
- **Vacuno** — ventilación natural casi siempre, luego fuente de área/volumen. Olor por plaza intermedio-bajo por animal en leche, pero los cebaderos de terneros presentan factores altos en las tablas neerlandesas (ver A.2). Estabulaciones abiertas: la emisión es difusa y el caudal es esencialmente inmodelable con precisión.

### A.2 Datos de emisión

#### A.2.1 Factores de emisión de OLOR (ou_E/s por plaza)

La fuente pública más completa y trazable son los factores de la **normativa neerlandesa de olor ganadero** (`Regeling geurhinder en veehouderij`, Bijlage 1), expresados en **ou_E/s por animal**. Valores para sistemas de alojamiento convencionales y con depuración de aire:

| Categoría animal (código Rgv) | Alojamiento convencional (*overige*) | Alojamiento de baja emisión | + Lavador **químico** | + Lavador **biológico** / biofiltro |
|---|---|---|---|---|
| Cerdos de cebo (D 3) | **23,0** | 17,9 | 12,5 (−30 %) | 9,8 (−45 %) |
| Cerdas gestantes/vacías (D 1.3) | **18,7** | 18,7 | 13,1 (−30 %) | 10,3 (−45 %) |
| Cerdas lactantes con lechones (D 1.2) | **27,9** | 27,9 | 19,5 (−30 %) | 15,3 (−45 %) |
| Lechones destetados (D 1.1) | **7,8** | 5,4 | 3,8 (−30 %) | 3,0 (−45 %) |
| Gallinas ponedoras, batería (E 2) | **0,35**; **0,69** si hay almacenamiento de gallinaza bajo batería | 0,35 | 0,21 (−40 %) | 0,19 (−45 %, biofiltro) |
| Pollos de engorde (E 5) | **0,33** | 0,33 | 0,20 (−40 %) | 0,18 (−45 %) |
| Pavos de engorde (F 4) | **1,55** | 1,55 | 0,93 (−40 %) | 0,85 (−45 %, biofiltro) |
| Terneros de cebo (A 4) | **35,6** ⚠️ | 35,6 | 24,9 (−30 %) | 19,6 (−45 %) |

Fuente: [`Regeling geurhinder en veehouderij`, Bijlage 1 — wetten.overheid.nl/BWBR0020711](https://wetten.overheid.nl/BWBR0020711/) (consultada la versión previa a su derogación).

**Cinco cautelas imprescindibles antes de usar esta tabla:**

1. ⚠️ **La norma fue derogada el 01/01/2024** al integrarse el régimen neerlandés en la `Omgevingswet`; los factores subsisten en la `Omgevingsregeling` asociada al Bkl, pero **hay que verificar los valores vigentes** antes de citarlos en un informe. Los recogidos arriba son los de la versión histórica consultada.
2. ⚠️ **El valor de terneros de cebo (35,6 ou_E/s) es anómalamente alto** frente al cerdo de cebo (23,0) y merece contraste con la fuente primaria antes de usarlo. Se marca como no consolidado.
3. Son factores **medios anuales**, calibrados para el modelo **V-Stacks** dentro de un sistema regulatorio cerrado (factor de emisión + modelo + umbral P98). **Trasplantarlos a AERMOD rompe esa calibración.** V-Stacks y AERMOD no producen el mismo P98 para la misma emisión. Si se usan, debe declararse explícitamente como transferencia metodológica y discutirse en el apartado de incertidumbre.
4. Cubren **la emisión de la nave**, no la balsa de purín ni el estercolero, que en el sistema neerlandés se tratan aparte.
5. Los porcentajes de reducción implícitos en las columnas de depuración (**−30 % lavador químico en porcino, −40 % en avicultura, −45 % lavador biológico/biofiltro**) son, en sí mismos, un dato regulatorio útil y citable: son la **eficacia de olor reconocida oficialmente**, mucho menor que la eficacia sobre amoniaco. Ver D.

**Balsas de purín y almacenamiento (fuente de área).** No existe un factor normativo español ni europeo. Valores de la literatura:

| Foco | Tasa de emisión específica de olor | Fuente |
|---|---|---|
| Almacenamiento de purín porcino/digestato, valle del Po (Italia) | 12.124 ± 7.914 y 35.207 ± 41.706 ou_E/m²·h → **≈ 3,4 y 9,8 ou_E/m²·s** | [Evaluation of ammonia and odour emissions from animal slurry and digestate storage in the Po Valley — *Waste Management*](https://www.sciencedirect.com/science/article/abs/pii/S0956053X19307925) |
| Mediana de literatura, almacenamiento de purín porcino | **≈ 5 ou_E/m²·s** | [Liu et al., *A review of practices and technologies for odor control in swine production facilities*](https://bae.k-state.edu//~zifeiliu/files/fac_zifeiliu/Zifeiliu/19%20Liu2014_A%20review%20of%20practices%20and%20technologies%20for%20odor%20control%20in%20swine%20production%20facilities.pdf) |

⚠️ La desviación típica de la medida italiana es del orden de la propia media (±65 % y ±118 %). **Ese es el nivel de incertidumbre real de este foco.** La literatura consultada insiste en que no hay unanimidad en las tasas publicadas y que, cuando el resultado dependa de la balsa, procede **medir en campo por campana de flujo** (`flux chamber`) y olfatometría **UNE-EN 13725**.

#### A.2.2 Factores de emisión de AMONIACO (kg NH₃/plaza·año)

La referencia normativa directa son los **NEA-MTD** (niveles de emisión asociados a las mejores técnicas disponibles) de la **Decisión de Ejecución (UE) 2017/302**, sobre cría intensiva de aves de corral o de cerdos. No son factores de inventario: son **rangos de cumplimiento** que una instalación IED debe respetar, lo que los hace más útiles todavía en un informe ambiental porque marcan a la vez el dato de partida y el criterio.

| Categoría animal | NEA-MTD, emisión de NH₃ de la nave (kg NH₃/plaza·año) |
|---|---|
| Gallinas ponedoras, sistema de jaula | 0,02 – 0,08 |
| Gallinas ponedoras, sistema sin jaula | 0,02 – 0,13 |
| Pollos de engorde | 0,01 – 0,08 |
| Cerdas gestantes / vacías | 0,2 – 2,7 |
| Cerdas lactantes con lechones | 0,4 – 5,6 |
| Lechones destetados | 0,03 – 0,53 |
| Cerdos de engorde | 0,1 – 2,6 |
| *Naves existentes con fosa profunda + gestión nutricional* | *límite superior 4,0* |

Fuente: [Decisión de Ejecución (UE) 2017/302 — EUR-Lex](https://eur-lex.europa.eu/legal-content/ES/TXT/HTML/?uri=CELEX:32017D0302) · [versión BOE/DOUE en PDF](https://www.boe.es/doue/2017/043/L00231-00279.pdf)

⚠️ **Advertencia de uso.** Los NEA-MTD están sujetos a condiciones, exclusiones y periodos transitorios recogidos en las notas al pie de los cuadros 2.1, 3.1 y siguientes de la Decisión (por ejemplo, aplicabilidad a naves nuevas frente a existentes, y no aplicabilidad a determinados sistemas). **Antes de usarlos como factor de emisión hay que leer las notas del cuadro correspondiente en el texto original**; la tabla anterior es un extracto y no las reproduce. Existe además una [corrección de errores](https://www.boe.es/buscar/doc.php?id=DOUE-L-2017-80778) que debe consultarse.

**Fuente alternativa para inventario (no verificada en esta revisión):** el capítulo **3.B *Manure management*** del [EMEP/EEA air pollutant emission inventory guidebook 2023](https://www.eea.europa.eu/en/analysis/publications/emep-eea-guidebook-2023/part-b-sectoral-guidance-chapters/3-agriculture/3-b-manure-management-2023) proporciona factores de emisión de NH₃ desagregados por **etapa** (alojamiento, almacenamiento, aplicación al campo y pastoreo) y por categoría animal, que es exactamente la desagregación que necesita el modelo de dispersión. Es la fuente correcta para repartir el NH₃ entre focos. ⚠️ **No se han podido extraer sus valores numéricos en esta revisión** (los PDF no eran legibles por la herramienta): deben tomarse directamente del capítulo. Lo mismo aplica al Inventario Nacional español ([SEI, MITECO](https://www.miteco.gob.es/en/calidad-y-evaluacion-ambiental/temas/sistema-espanol-de-inventario-sei-/inventario-contaminantes-atmosfericos.html)), que es la referencia oficial para España.

#### A.2.3 Sulfuro de hidrógeno (H₂S)

No se ha localizado en esta revisión una tabla de factores de emisión de H₂S por plaza de referencia europea. El H₂S es relevante en dos contextos: (a) como **trazador medible** del penacho de olor, con umbral de percepción muy bajo, y (b) como **riesgo agudo de seguridad laboral** durante el agitado y vaciado de fosas, no como problema de inmisión en el vecindario. Se recomienda tratarlo cualitativamente salvo que existan medidas propias. Ver F.

### A.3 Parámetros de modelización y errores típicos

#### Altura de emisión: el parámetro dominante

El equipo ha medido que **entre 1 m y 6 m de altura de emisión el máximo en receptor cambia en un factor ×12**. Esto no es un detalle de afinado: es el parámetro que decide el resultado del estudio. Consecuencias operativas:

- **La altura de los extractores debe medirse en campo, no suponerse.** Un extractor lateral a media altura de muro está a ~2 m; una chimenea cenital sobre cumbrera está a 6–8 m. Confundirlos cambia el resultado en más de un orden de magnitud.
- **Hay que declarar la altura de cada foco y su origen** (medida en visita, plano de proyecto, hipótesis) en la memoria del modelo.
- **La altura es también la principal palanca de corrección** (ver D): elevar la descarga es casi siempre más barato y más eficaz que depurar el aire.
- En el análisis de sensibilidad del informe, la altura debe aparecer con un rango realista (± 1 m sobre el valor adoptado), no como valor único.

#### Momento del chorro: sí existe en ventilación forzada

A diferencia de una balsa, **un ventilador sí tiene momento**, aunque no tenga empuje térmico apreciable (el aire de la nave sale sólo unos grados por encima del ambiente en verano, y bastante más caliente en invierno — pero el caudal es entonces mínimo, de modo que la flotabilidad rara vez aporta elevación útil).

- **Elevación por momento**: exige introducir en AERMOD el diámetro de salida y la velocidad de salida reales. Velocidades típicas de extractores agrícolas: **orden de 5–10 m/s** en el plano del ventilador ⚠️ *(valor de diseño habitual, no verificado documentalmente en esta revisión)*. Con esa velocidad y un diámetro de 0,6–1,25 m hay una elevación de penacho no despreciable.
- ⚠️ **Trampa clásica**: si el extractor descarga **horizontalmente** (lateral, sin codo), AERMOD lo modela igualmente como descarga vertical y **atribuye una elevación de penacho que no existe**. La práctica conservadora consiste en asignar a estos focos una **velocidad de salida nominal muy baja (p. ej. 0,1–1 m/s)** conservando el caudal correcto mediante el ajuste del diámetro, de modo que el modelo no genere elevación espuria. Debe documentarse esta decisión: es una de las que más condiciona el resultado.
- **Temperatura de salida**: usar la temperatura de la nave (típicamente 20–25 °C en cebo) o marcarla como ambiente. Nunca dejar el valor por defecto sin justificar.

#### Caudal Q: la mayor fuente de error, y además estacional

El equipo ya ha identificado Q como el mayor contribuyente al error. En ganadería, además, **Q no es constante**:

- La ventilación se regula por temperatura. **En verano el caudal extraído puede ser un orden de magnitud superior al de invierno**, porque el criterio de invierno es la calidad del aire (mínimo higiénico) y el de verano es la disipación de calor.
- Simultáneamente, **la concentración de olor en el aire extraído baja al aumentar el caudal** (dilución), pero **la tasa de emisión total (ou_E/s) sube**, porque la superficie emisora dentro de la nave emite más al aumentar la velocidad del aire sobre ella y la temperatura.
- Neto: **la emisión de olor de una granja es claramente mayor en verano.** Un modelo alimentado con un valor anual único subestima el verano y sobreestima el invierno, y el verano es cuando hay quejas (ventanas abiertas, vida al aire libre).
- **Recomendación**: modelar al menos **dos escenarios estacionales** (verano/invierno) con su caudal y su altura de emisión, o usar variación horaria de emisión (`EMISFACT` con `SEASHR` o `HROFDY`) si la herramienta lo permite. Si sólo se puede un escenario, usar el de verano y declararlo como conservador.

#### Errores típicos, en orden de gravedad

1. **Meter toda la granja como un único polígono de área a 1 m.** Anula la altura de los extractores y sobreestima brutalmente el impacto cercano.
2. **Modelar la fosa bajo slat como foco independiente además de los extractores.** Doble contabilidad de la misma emisión.
3. **Dejar velocidad de salida por defecto en extractores laterales.** Genera elevación de penacho inexistente y subestima el impacto (error en el sentido no conservador).
4. **Usar factores neerlandeses con AERMOD sin declarar la transferencia.** El paquete factor+modelo+umbral es indivisible en origen.
5. **Ignorar la estacionalidad del caudal.**
6. **Omitir el efecto de estela de los edificios (*building downwash*).** Las naves ganaderas son edificios largos y bajos, y los extractores están **en el propio edificio**: el downwash es casi seguro dominante para los focos laterales. **Hay que ejecutar BPIPPRM** con la geometría real de las naves y pasar los parámetros de estela a AERMOD. Omitirlo es un error no conservador de primer orden.
7. **Modelar la aplicación de purín en campo dentro del escenario anual continuo.** Es un episodio, no un régimen.
8. ⚠️ **Comparar una media del periodo con un umbral definido al P98.** Ver el aviso siguiente.

#### Limitación crítica de la salida actual: no hay P98

La herramienta exporta hoy, por receptor, únicamente la **media del periodo**; los máximos de 1 h y 24 h quedan en `aermod.out` y **no hay serie horaria**. Pero:

- El criterio de **Canarias (Decreto 185/2025)** es un **P98 anual de medias horarias**.
- El criterio **neerlandés** (Bkl art. 5.109) es también un **P98**.

**La media del periodo no es comparable con ninguno de los dos y no puede convertirse en P98 mediante un factor genérico** sin una hipótesis fuerte sobre la distribución de concentraciones en cada receptor, que varía con la distancia, la topografía y la rosa de vientos.

Recomendaciones concretas para cerrar la brecha, por orden de preferencia:

1. **Configurar AERMOD para que calcule el percentil directamente.** AERMOD admite periodos de promediado de 1 h y salida por rango; para una simulación anual, el **P98 de medias horarias equivale aproximadamente al valor de rango 176** (≈ 2 % de 8.760 h). Configurar `AVERTIME 1`, la opción de rangos altos y un `PLOTFILE` de ese rango resuelve el problema sin postprocesado.
2. **Alternativamente, volcar la serie horaria** con `POSTFILE` (formato `UNFORM` o `PLOT`) y calcular el P98 fuera del modelo. Es el camino más flexible y el que además permite construir curvas de frecuencia de superación de cualquier umbral.
3. **Mientras tanto**, presentar la media del periodo como lo que es (un indicador de exposición crónica, útil para comparar alternativas entre sí) y **declarar expresamente que no se ha verificado el cumplimiento del umbral normativo**. No maquillar la media como si fuera un P98.
4. La relación **pico-media** documentada en [`../metodologia/olores_metodologia.md`](../metodologia/olores_metodologia.md) corrige el promediado de 1 h hacia la escala de la percepción instantánea (segundos); es un problema **distinto y adicional** al del percentil, y ambos deben aplicarse, no uno en lugar del otro.

---

## B. ESTRUCTURA DEL INFORME → para el agente 2

Secciones numeradas de un informe real de impacto por olores y amoniaco de una explotación ganadera intensiva.

**1. Objeto, alcance y promotor**
Identificación de la instalación, censo autorizado por categoría animal, situación administrativa (¿está sujeta a autorización ambiental integrada?, ver C), y motivo del estudio (nueva instalación, ampliación, respuesta a denuncias).

**2. Descripción de la instalación**
2.1 Emplazamiento y entorno. 2.2 Naves: número, dimensiones, orientación, sistema de alojamiento y de ventilación. 2.3 Gestión de deyecciones: fosas, balsas, estercolero, capacidad de almacenamiento en meses, destino final. 2.4 Alimentación y manejo (relevante para emisión: ver MTD 3).
*Figura 2.1: planta acotada con todos los focos numerados. Tabla 2.1: censo por categoría animal y plazas.*

**3. Marco normativo y criterio de evaluación adoptado**
Remisión a [`../normativa/marco_normativo_ES_UE.md`](../normativa/marco_normativo_ES_UE.md). **Declaración explícita del umbral aplicado, su percentil y su altura de evaluación.** Si aplica el Decreto 185/2025 de Canarias, indicar la categoría (ganadería intensiva = Categoría 2) y el valor de la escala 3/6/9 ou_E/m³ al P98 que le corresponde. Si no hay norma autonómica aplicable, justificar el criterio de referencia elegido (p. ej. el neerlandés, por ser el único específico de olor ganadero).
*Tabla 3.1: criterio adoptado — contaminante, estadístico, umbral, fuente.*

**4. Inventario de focos y estimación de emisiones**
4.1 Identificación y tipificación de focos (tabla del apartado A.1). 4.2 Factores de emisión adoptados **con su fuente y su fecha**. 4.3 Cálculo de la emisión de cada foco en ou_E/s y en g NH₃/s. 4.4 Escenarios estacionales (verano/invierno). 4.5 Balance: ¿qué fracción del total aporta cada foco?
*Tabla 4.1: focos × (tipo, coordenadas, altura, dimensiones, caudal, temperatura, velocidad de salida). Tabla 4.2: emisión por foco y escenario. Figura 4.1: gráfico de reparto de la emisión total por foco — esta figura suele ser la más informativa del informe.*

**5. Metodología de modelización**
5.1 Modelo (AERMOD, versión). 5.2 Meteorología: estación, periodo, tratamiento con AERMET, rosa de vientos, porcentaje de calmas y horas no válidas. 5.3 Terreno: AERMAP, MDT empleado. 5.4 Rugosidad, Bowen y albedo: origen del uso del suelo. 5.5 **Efecto de estela de edificios: BPIPPRM**, con la geometría de naves considerada. 5.6 Malla de receptores y receptores discretos (viviendas aisladas, núcleo urbano, equipamientos sensibles). 5.7 Tratamiento del percentil (ver A.3).
*Figura 5.1: rosa de vientos. Figura 5.2: malla de receptores sobre ortofoto con focos y receptores sensibles señalados.*

**6. Resultados: olor**
6.1 Mapa de isopletas del estadístico normativo. 6.2 Tabla de concentración en receptores sensibles frente a umbral. 6.3 Distancia a la que se cruza el umbral, por sectores de dirección. 6.4 Contribución de cada foco al receptor más afectado (**análisis de contribución**: dice dónde actuar).
*Figura 6.1: isopletas de ou_E/m³ al P98. Tabla 6.1: receptores × concentración × umbral × cumplimiento.*

**7. Resultados: amoniaco**
7.1 Inmisión de NH₃ en receptores. 7.2 **Deposición de nitrógeno en hábitats sensibles** si hay Red Natura 2000 en el ámbito — es frecuentemente el condicionante real de una granja, más que el olor. 7.3 Comparación con los NEA-MTD de la Decisión 2017/302 en términos de emisión por plaza.
*Tabla 7.1: emisión por plaza calculada frente a rango NEA-MTD.*

**8. Análisis de sensibilidad e incertidumbre**
Obligatorio, no opcional, dado lo expuesto en A.3. Como mínimo: altura de emisión (±1 m), caudal Q (rango realista), factor de emisión de olor (rango de la literatura), y emisión de la balsa. Presentar como **barrido paramétrico**, no como frase cualitativa.
*Figura 8.1: gráfico tornado o de barrido — concentración en el receptor crítico frente a cada parámetro.*

**9. Medidas preventivas y correctoras**
Jerarquizadas por relación coste-eficacia según el análisis de contribución del apartado 6.4 (ver D). Cada medida con su eficacia esperada, su fuente y su efecto modelado.
*Tabla 9.1: medida × foco afectado × eficacia × fuente × coste orientativo.*

**10. Escenario corregido**
Nueva ejecución del modelo con las medidas adoptadas y verificación del cumplimiento.
*Figura 10.1: isopletas antes/después.*

**11. Programa de vigilancia ambiental**
Olfatometría de campo (norma de referencia: UNE-EN 16841 para inspección de campo; UNE-EN 13725 para olfatometría dinámica de muestras), registro de quejas, y protocolo de revisión del modelo.

**12. Conclusiones**

**Anexos**: ficheros de entrada y salida de AERMOD, certificados de la meteorología, informes de olfatometría, fichas de los factores de emisión.

---

## C. NORMATIVA APLICABLE

Desarrollo completo en [`../normativa/marco_normativo_ES_UE.md`](../normativa/marco_normativo_ES_UE.md) y [`../normativa/criterios_olor_internacional.md`](../normativa/criterios_olor_internacional.md). Aquí sólo lo específico de ganadería.

### C.1 ¿Está la granja sujeta a autorización ambiental integrada (IED)?

Determina si le aplican las MTD de la Decisión 2017/302 y si debe tramitar AAI. **Este umbral acaba de cambiar.**

**Régimen anterior — Directiva 2010/75/UE, Anexo I, punto 6.6:** 40.000 plazas de aves de corral; 2.000 plazas de cerdos de cebo de más de 30 kg; 750 plazas de cerdas reproductoras. ⚠️ *Valores de amplia circulación que no se han verificado contra el texto original en esta revisión; contrastar antes de citar.*

**Régimen nuevo — Directiva (UE) 2024/1785**, en vigor desde el **4 de agosto de 2024** ([EUR-Lex](https://eur-lex.europa.eu/eli/dir/2024/1785/oj?locale=es) · [BOE/DOUE](https://www.boe.es/buscar/doc.php?id=DOUE-L-2024-81092)). Cambios de fondo:

- Se crea un **Anexo I bis** específico para cría de aves de corral y cerdos, separado del Anexo I industrial.
- Los umbrales pasan a expresarse en **UGM (unidades de ganado mayor)** en lugar de en plazas, lo que permite **agregar categorías animales** y cubre explotaciones mixtas que antes se fragmentaban para quedar por debajo del umbral.
- **Se amplía el ámbito**: deja de exigirse que la cría sea "intensiva".
- Factores de conversión a UGM del Anexo I bis: cerdas reproductoras ≥50 kg = **0,500**; lechones ≤20 kg = **0,027**; otros cerdos = **0,300**; pollos de engorde = **0,007**; gallinas ponedoras = **0,014**; pavos = **0,030**; patos = **0,010**; ocas = **0,020**; avestruces = **0,350**; otras aves = **0,001**.
- Umbrales: **cerdos, > 350 UGM**; **aves distintas de ponedoras, 280 UGM**; **gallinas ponedoras, 300 UGM**.
- **Exclusión** de explotaciones en régimen **ecológico o extensivo** con baja carga ganadera, y de la cría de cerdos en pastos con baja carga.
- **Aplicación a partir de 2030**, con medidas transitorias escalonadas. ⚠️ *El calendario detallado por tramos de UGM no se ha podido verificar en esta revisión (los PDF consultados no eran legibles); consultar el artículo 3 y las disposiciones transitorias del texto original.*

**Implicación práctica para el estudio de olores:** el cambio de umbral **incorpora al régimen IED explotaciones que hoy no lo están**, y con ello les hace exigibles las MTD 12 y 13 (plan de gestión de olores y técnicas de reducción). Un estudio de olores hecho hoy para una granja mediana debe verificar en qué lado del umbral queda **tras 2030**.

### C.2 MTD específicas de olor — Decisión de Ejecución (UE) 2017/302

[Texto en EUR-Lex](https://eur-lex.europa.eu/legal-content/ES/TXT/HTML/?uri=CELEX:32017D0302) · [PDF DOUE](https://www.boe.es/doue/2017/043/L00231-00279.pdf) · [corrección de errores](https://www.boe.es/buscar/doc.php?id=DOUE-L-2017-80778)

- **MTD 12** — elaborar, aplicar y revisar periódicamente un **plan de gestión de olores**, con protocolos de seguimiento y de respuesta a episodios. Aplicable cuando quepa esperar molestias en receptores sensibles.
- **MTD 13** — reducir las emisiones de olor y/o su impacto mediante una **combinación** de técnicas: distancia adecuada a receptores sensibles, sistema de alojamiento de baja emisión, optimización de la ventilación y de la **salida de aire**, depuración del aire, cubrición del estiércol y purín, tratamiento del estiércol, y **aplicación al campo con técnicas de baja emisión**. Obsérvese que *la altura y disposición de la salida de aire es una MTD reconocida*, lo que respalda directamente la recomendación de D.
- **MTD 3** — reducir el contenido de **proteína bruta** de la dieta mediante alimentación equilibrada, multifase y suplementación con aminoácidos. Actúa sobre el nitrógeno excretado y por tanto sobre el NH₃ **en origen**.
- **MTD 14–17** — almacenamiento de estiércol sólido y de purín, incluidas **cubiertas** rígidas, láminas flexibles, costra natural, capa de paja y bolas/pellets flotantes. ⚠️ La Decisión **no cuantifica** la reducción de olor asociada a cada cubierta (ver D y F).

### C.3 Ordenación sectorial estatal (España)

**Porcino — [Real Decreto 306/2020](https://www.boe.es/buscar/act.php?id=BOE-A-2020-2110)**, normas básicas de ordenación de las granjas porcinas intensivas:

- **Clasificación por capacidad**: explotaciones reducidas **≤ 5,1 UGM**; **grupo primero ≤ 120 UGM**; **grupo segundo > 120 y ≤ 480 UGM**; **grupo tercero > 480 y ≤ 720 UGM**. Las comunidades autónomas pueden incrementar la capacidad del grupo tercero hasta un **20 %** en función de características locales.
- **Almacenamiento de deyecciones** (art. 9.1): capacidad mínima de **tres meses** de producción. *Dato directamente utilizable: fija el tamaño mínimo de la balsa y por tanto la superficie del foco de área.*
- **Minimización de olores** (art. 5.1.h): obligación expresa de "minimizar en la medida de lo posible los ruidos, partículas, polvo y **olores**".
- **Distancias mínimas**: se regulan en el **Anexo V** (distancias entre explotaciones y entre explotaciones y otros establecimientos). Las CCAA pueden reducirlas hasta un **10 %** en casos excepcionales, y hasta un **20 %** las comunidades insulares. Excepción para mataderos de especies distintas del porcino, con distancia mínima de **500 m** y aislamiento sanitario adecuado.
  ⚠️ **Los valores numéricos concretos del Anexo V no se han podido extraer en esta revisión** (el servidor del BOE no devolvió el anexo). Deben tomarse directamente del [texto consolidado](https://www.boe.es/buscar/act.php?id=BOE-A-2020-2110), incluida la [corrección de errores](https://noticias.juridicas.com/base_datos/Admin/722146-correccion-de-errores-rd-306-2020-de-11-feb-normas-basicas-de-ordenacion.html). **No deben suponerse.**
- **Aplicación de estiércoles al terreno**: distancia mínima de **100 m** a instalaciones de categoría 1 y **200 m** a las de categorías 2 y 3 y a **núcleos urbanos**.

**Avícola — [Real Decreto 637/2021](https://www.boe.es/diario_boe/txt.php?id=BOE-A-2021-12609)** ([consolidado en PDF](https://www.boe.es/buscar/pdf/2021/BOE-A-2021-12609-consolidado.pdf)), normas básicas de ordenación de las granjas avícolas:

- Toda instalación nueva posterior a su entrada en vigor debe respetar **500 m** respecto de instalaciones avícolas existentes o de cualquier otro establecimiento que pueda suponer riesgo higiénico-sanitario.
- **Aplicación de estiércoles, purines o lodos** al terreno: **100 m** de cualquier instalación, salvo **200 m** con instalaciones de selección o multiplicación de aves reproductoras, excepto si el estiércol procede de la propia instalación.

⚠️ Importante: estas distancias son de naturaleza **higiénico-sanitaria y de bioseguridad**, no criterios de protección frente al olor. **No sustituyen a un estudio de dispersión** ni pueden usarse como justificación de ausencia de impacto odorífero. Su cumplimiento es condición necesaria, no suficiente.

### C.4 El enfoque neerlandés como referencia de criterio

Es hoy el único ordenamiento europeo con un **criterio de olor específicamente ganadero, cerrado y cuantitativo**: factor de emisión reglado por especie y sistema de alojamiento → modelo obligatorio (**V-Stacks**) → umbral en ou_E/m³ al **P98** diferenciado según se esté dentro o fuera del contorno de edificación y dentro o fuera de zona de concentración ganadera (**2,0 / 3,0 / 8,0 / 14,0 / 20,0 / 35,0 ou_E/m³**), más **distancias fijas de 100/50 m** para especies sin factor de emisión asignado. Detalle en [`../normativa/criterios_olor_internacional.md`](../normativa/criterios_olor_internacional.md).

Es la mejor referencia disponible para **justificar un criterio** cuando no hay norma autonómica, pero con la cautela ya señalada en A.2: **el paquete factor-modelo-umbral es indivisible en origen**, y sustituir V-Stacks por AERMOD manteniendo factor y umbral es una transferencia metodológica que hay que declarar y discutir.

---

## D. MEDIDAS CORRECTORAS

Ordenadas por el criterio que realmente importa: **cuánto reducen la inmisión en el receptor por euro invertido**. El análisis de contribución por foco (apartado 6.4 del informe) es lo que decide dónde actuar; lo que sigue es el catálogo.

### D.1 Altura y disposición de la salida de aire — la palanca más eficaz

**Chimeneas de extracción cenital frente a extractores laterales.** Es, con diferencia, la medida de mejor relación coste-eficacia en una nave de ventilación forzada, y está reconocida como MTD (MTD 13, "optimización de la salida de aire"). Razones:

- No reduce la emisión: **redistribuye la inmisión**. El mismo Q y el mismo ou_E/s, descargados a 6–8 m en lugar de 2 m, producen concentraciones en receptor drásticamente menores — el propio equipo ha medido **×12 entre 1 y 6 m**.
- Añade **descarga vertical con momento**, lo que genera elevación de penacho real (a diferencia del extractor lateral horizontal, ver A.3).
- **Reduce el *building downwash***, sacando la descarga de la zona de recirculación de la nave.
- Es **compatible y acumulativa** con cualquier medida de reducción en origen.
- Coste bajo comparado con un lavador de aire, y sin consumo energético relevante más allá de la pérdida de carga añadida.

⚠️ Contrapartida honesta: al elevar la descarga se **aleja** el máximo pero se **extiende** la huella de bajas concentraciones. Si hay receptores lejanos sensibles, verificar en el modelo que no se traslada el problema.

### D.2 Depuración del aire extraído: lavadores y biofiltros

Dato clave, y contraintuitivo: **la eficacia sobre amoniaco y sobre olor son muy distintas.**

| Técnica | Eficacia NH₃ | Eficacia OLOR | Fuente |
|---|---|---|---|
| Lavador **ácido/químico**, porcino | > 90 % | **≈ 30 %** (valor reglado NL) | [3tres3](https://www.3tres3.com/articulos/tratamiento-de-gases-en-la-explotacion-ganadera-fundamentos-de-la-bio_2175/) · [Rgv Bijlage 1](https://wetten.overheid.nl/BWBR0020711/) |
| Lavador **ácido/químico**, avicultura | — | **≈ 40 %** (valor reglado NL) | [Rgv Bijlage 1](https://wetten.overheid.nl/BWBR0020711/) |
| Lavador **biológico** / biofiltro percolador | > 90 % | **≈ 45 %** (valor reglado NL) | [Rgv Bijlage 1](https://wetten.overheid.nl/BWBR0020711/) · [3tres3](https://www.3tres3.com/articulos/tratamiento-de-gases-en-la-explotacion-ganadera-fundamentos-de-la-bio_2175/) |
| **Biofiltro** orgánico (compost, virutas), avicultura | hasta **79 %** (prototipo) | — | [Industria Avícola](https://www.industriaavicola.net/uncategorized/reduccion-de-emisiones-contaminantes-del-aire-en-granjas-avicolas-mediante-un-biofiltro/) |
| **Biofiltro** orgánico, porcino: parámetros de diseño | alta reducción de NH₃ y H₂S con **espesor de lecho 0,33 m** y **humedad 55 %** | — | [3tres3](https://www.3tres3.com/latam/abstracts/biofiltros-en-explotaciones-porcinas-profundidad-del-medio-y-humedad_6864/) |

**Lectura para el modelizador:** un lavador ácido resuelve el problema de amoniaco y **apenas el 30 % del de olor**. Nunca aplicar la eficacia de NH₃ al olor. Los porcentajes de la normativa neerlandesa son la referencia más defendible porque son **valores reglados**, no comerciales. La razón física es que el lavador ácido captura el NH₃ (básico y muy soluble) pero deja pasar los compuestos orgánicos volátiles (ácidos grasos volátiles, fenoles, indoles, compuestos azufrados) que son los que aportan la mayor parte del olor y su carácter desagradable.

⚠️ El lavador de aire **sólo funciona si toda la extracción está canalizada**, lo que exige ventilación forzada centralizada. En una nave con extractores laterales distribuidos, instalarlo implica reformar el sistema de ventilación completo. Coste de inversión y de operación (agua, ácido, energía de ventilación adicional) muy superior al de una chimenea.

### D.3 Reducción en origen: alimentación baja en proteína

**MTD 3** de la Decisión 2017/302. Reducir la proteína bruta mediante dieta equilibrada, **alimentación multifase** y suplementación con **aminoácidos sintéticos** (lisina, metionina, treonina, triptófano). Reduce el nitrógeno excretado en forma de urea y, con ello, el NH₃ en origen.

Ventajas: actúa sobre **todos los focos a la vez** (nave, fosa, balsa y aplicación al campo), no requiere obra, y suele tener retorno económico. Es la primera medida a considerar.
⚠️ **Eficacia porcentual no verificada en esta revisión** — la Decisión la establece como MTD pero no se ha extraído un rango cuantitativo. No citar cifras sin verificar.

### D.4 Cubrición de balsas y gestión del purín

**MTD 14–17.** Cubiertas rígidas, láminas flexibles, **costra natural**, capa de paja, y bolas o pellets flotantes.

- Efecto directo sobre el foco de área, que puede ser el primero o el segundo en contribución (A.2.1).
- La cubierta rígida o de lámina flexible es la más eficaz; la costra natural es gratuita pero se destruye con cada agitado y con la lluvia.
- ⚠️ **La Decisión 2017/302 no cuantifica la reducción de olor** de cada tipo de cubierta. No inventar porcentajes: si se necesita un valor para el escenario corregido, tomarlo de una fuente específica y citarla, o presentar el escenario corregido como un **rango** de eficacia.

**Manejo asociado, igualmente relevante y a menudo olvidado:**
- **Vaciado frecuente de la fosa bajo slat** hacia almacenamiento exterior cubierto: reduce la superficie emisora activa dentro de la nave y por tanto la concentración del aire extraído.
- **Evitar el agitado en condiciones desfavorables** (viento hacia el núcleo, atmósfera estable, tarde de verano). El agitado previo al vaciado es el **episodio de emisión máxima** de toda la explotación y la causa habitual de las quejas puntuales.
- **Digestión anaerobia** del purín: reduce la materia orgánica degradable y con ella el potencial odorífero del digestato, aunque introduce focos nuevos (venteos, balsa de digestato).

### D.5 Aplicación al campo con baja emisión

**MTD 13** la incluye expresamente. Sustituir el **abanico o plato** (máxima emisión: gotas finas, gran superficie de contacto con el aire) por **tubos colgantes, zapatas o inyección** reduce drásticamente tanto el NH₃ como el olor, y además mejora el aprovechamiento agronómico del nitrógeno. **Enterrado inmediato** tras la aplicación en superficie.

Además: **planificar la aplicación** evitando fines de semana, festivos, horas de tarde-noche con atmósfera estable, y vientos dirigidos hacia núcleos habitados. Una medida de coste cero que resuelve una fracción desproporcionada de las quejas.

### D.6 Distancia y ordenación

La medida más eficaz y la menos disponible a posteriori: **elegir el emplazamiento**. Sólo aplicable a instalaciones nuevas o ampliaciones. La MTD 13 la reconoce ("distancia adecuada a receptores sensibles"), y los RD 306/2020 y 637/2021 fijan distancias mínimas que —insistimos— son **sanitarias, no de olor** (ver C.3).

Complementariamente: **barreras vegetales** perimetrales. Su efecto sobre la concentración es modesto y difícil de modelar en AERMOD, pero actúan sobre la turbulencia de mezcla y sobre la **percepción visual** del foco, que tiene un efecto documentado sobre la tasa de quejas. ⚠️ No atribuirles una eficacia numérica sin medida propia.

---

## E. FUENTES

**Normativa europea**
- [Decisión de Ejecución (UE) 2017/302 — MTD para la cría intensiva de aves de corral o de cerdos (EUR-Lex)](https://eur-lex.europa.eu/legal-content/ES/TXT/HTML/?uri=CELEX:32017D0302) · [PDF DOUE](https://www.boe.es/doue/2017/043/L00231-00279.pdf) · [ficha BOE](https://www.boe.es/buscar/doc.php?id=DOUE-L-2017-80314) · [corrección de errores](https://www.boe.es/buscar/doc.php?id=DOUE-L-2017-80778)
- [Directiva (UE) 2024/1785, revisión de la Directiva de Emisiones Industriales (EUR-Lex)](https://eur-lex.europa.eu/eli/dir/2024/1785/oj?locale=es) · [ficha BOE](https://www.boe.es/buscar/doc.php?id=DOUE-L-2024-81092)
- [Novedades de la Directiva (UE) 2024/1785 — Generalitat de Catalunya / MITECO](https://mediambient.repositori.gencat.cat/bitstream/handle/20.500.14343/766/2025_Transposic_D2024_1785_Ministerio.pdf?sequence=6&isAllowed=y)
- [Transposición de la DEI 2.0 — PRTR España, MITECO](https://prtr-es.miteco.gob.es/Data/images/250206CPPtransposicDEI20.pdf)
- [Revisión de la DEI y del Portal Europeo de Emisiones Industriales — CONAMA 2024](https://www.conama.org/conama/download/files/conama2024/STs%202024/10012792_ppt_MOFraile.pdf)

**Normativa española**
- [Real Decreto 306/2020 — ordenación de granjas porcinas intensivas (BOE, consolidado)](https://www.boe.es/buscar/act.php?id=BOE-A-2020-2110) · [corrección de errores](https://noticias.juridicas.com/base_datos/Admin/722146-correccion-de-errores-rd-306-2020-de-11-feb-normas-basicas-de-ordenacion.html) · [preguntas y respuestas, MAPA](https://www.mapa.gob.es/dam/mapa/contenido/ganaderia/temas/produccion-y-mercados-ganaderos/ordenacion-sectorial/documentacion/preguntasyrespuestassobreelrd306-2020deordenacion-v12.pdf)
- [Real Decreto 637/2021 — ordenación de granjas avícolas (BOE)](https://www.boe.es/diario_boe/txt.php?id=BOE-A-2021-12609) · [texto consolidado en PDF](https://www.boe.es/buscar/pdf/2021/BOE-A-2021-12609-consolidado.pdf)

**Factores de emisión de olor**
- [`Regeling geurhinder en veehouderij`, Bijlage 1 — factores en ou_E/s por animal (wetten.overheid.nl)](https://wetten.overheid.nl/BWBR0020711/) — derogada 01/01/2024, integrada en el régimen de la `Omgevingswet`
- [`Wet geurhinder en veehouderij` (wetten.overheid.nl)](https://wetten.overheid.nl/BWBR0020396/)
- [RIVM — *Geur uitstoot in de buurt van veehouderijen*](https://www.rivm.nl/ggd-richtlijn-mmk-veehouderij/emissies-veehouderij/geur-uitstoot)
- [Wageningen UR Livestock Research, Rapport 391](https://edepot.wur.nl/146661)

**Factores de emisión de amoniaco**
- [EMEP/EEA air pollutant emission inventory guidebook 2023, cap. 3.B *Manure management*](https://www.eea.europa.eu/en/analysis/publications/emep-eea-guidebook-2023/part-b-sectoral-guidance-chapters/3-agriculture/3-b-manure-management-2023) · [descarga directa](https://www.eea.europa.eu/en/analysis/publications/emep-eea-guidebook-2023/part-b-sectoral-guidance-chapters/3-agriculture/3-b-manure-management-2023/@@download/file)
- [Sistema Español de Inventario — Inventario Nacional de Contaminantes Atmosféricos (MITECO)](https://www.miteco.gob.es/en/calidad-y-evaluacion-ambiental/temas/sistema-espanol-de-inventario-sei-/inventario-contaminantes-atmosfericos.html)
- [Hutchings et al., *New Emission Factors for Calculation of Ammonia Volatilization From European Livestock Manure Management Systems* — Frontiers in Sustainable Food Systems](https://www.frontiersin.org/journals/sustainable-food-systems/articles/10.3389/fsufs.2019.00101/full)

**Emisión de balsas y modelización de olor ganadero**
- [*Evaluation of ammonia and odour emissions from animal slurry and digestate storage in the Po Valley (Italy)* — Waste Management](https://www.sciencedirect.com/science/article/abs/pii/S0956053X19307925)
- [Liu et al., *A review of practices and technologies for odor control in swine production facilities*](https://bae.k-state.edu//~zifeiliu/files/fac_zifeiliu/Zifeiliu/19%20Liu2014_A%20review%20of%20practices%20and%20technologies%20for%20odor%20control%20in%20swine%20production%20facilities.pdf)
- [*Odour emission scenarios for fattening pigs as input for dispersion models: A step from an annual mean value to time series*](https://www.sciencedirect.com/science/article/abs/pii/S0167880914002473)
- [*A dispersion modelling approach to determining the odour impact of intensive pig production units in Ireland*](https://www.sciencedirect.com/science/article/abs/pii/S0960852403001792)
- [*Odour and Ammonia Emissions from Intensive Pig Units in Ireland* — UCD Research Repository](https://researchrepository.ucd.ie/rest/bitstreams/10473/retrieve)
- [Olores.org — *Odour concentration of various emitting area sources from cattle farms*](https://olores.org/en/techniques/dynamic-olfactometry/1188-odour-concentration-of-various-emitting-area-sources-from-cattle-farms)
- [Olores.org — Gestión de impactos por emisiones odoríferas procedentes de actividades ganaderas](https://olores.org/index.php?Itemid=40&catid=1%3Acontenido&id=194%3Amanaging-the-impact-of-odour-emissions-from-livestock-activities-&lang=es&option=com_content&view=article)

**Medidas correctoras y emisiones en granja**
- [*Guía para la minimización de las emisiones de gases en las granjas porcinas* — Observatori del Porcí, Generalitat de Catalunya](https://agricultura.gencat.cat/web/.content/de_departament/de02_estadistiques_observatoris/08_observatoris_sectorials/04_observatori_porci/estudis/fitxers-binaris/Guia-para-la-minimizacion-de-las-emisiones.pdf)
- [3tres3 — *Tratamiento de gases en la explotación ganadera: fundamentos de la biofiltración*](https://www.3tres3.com/articulos/tratamiento-de-gases-en-la-explotacion-ganadera-fundamentos-de-la-bio_2175/)
- [3tres3 — *Biofiltros en explotaciones porcinas: profundidad del medio y humedad*](https://www.3tres3.com/latam/abstracts/biofiltros-en-explotaciones-porcinas-profundidad-del-medio-y-humedad_6864/)
- [3tres3 — *Emisiones de gases y olores de las explotaciones de engorde de porcino*](https://www.3tres3.com/articulos/emisiones-de-gases-y-olores-de-las-explotaciones-de-engorde-de-porcino_2869/)
- [Industria Avícola — *Reducción de emisiones contaminantes del aire en granjas avícolas mediante un biofiltro*](https://www.industriaavicola.net/uncategorized/reduccion-de-emisiones-contaminantes-del-aire-en-granjas-avicolas-mediante-un-biofiltro/)
- [3tres3 — *Emisiones de amoníaco en el sector porcino español: un nuevo marco*](https://www.3tres3.com/articulos/emisiones-de-amoniaco-en-el-sector-porcino-espanol-un-nuevo-marco_53508/)

**Documentos internos relacionados**
- [`../normativa/marco_normativo_ES_UE.md`](../normativa/marco_normativo_ES_UE.md)
- [`../normativa/criterios_olor_internacional.md`](../normativa/criterios_olor_internacional.md)
- [`../metodologia/olores_metodologia.md`](../metodologia/olores_metodologia.md)

---

## F. INCERTIDUMBRES Y AVISOS

### F.1 Datos NO verificados en esta revisión — no usar sin comprobar

1. ⚠️ **Valores numéricos del Anexo V del RD 306/2020** (distancias mínimas de granjas porcinas). El servidor del BOE no devolvió el contenido del anexo en las tres consultas realizadas. Se conocen las reglas de modulación (10 % general, 20 % insular) y la excepción de mataderos (500 m), pero **no las distancias base**. La cifra de "1.000 m a núcleos de población" circula ampliamente y **no ha podido confirmarse**: no citarla.
2. ⚠️ **Factores de emisión de NH₃ del EMEP/EEA Guidebook 2023 (cap. 3.B)** en kg NH₃/plaza·año desagregados por etapa. No extraídos: los PDF no fueron legibles por la herramienta de consulta. Es la fuente correcta y hay que ir a ella directamente.
3. ⚠️ **Factores de emisión de NH₃ del Inventario Nacional español (MITECO/SEI)**. Localizada la página de entrada, no los valores.
4. ⚠️ **Umbrales del Anexo I de la Directiva 2010/75/UE, punto 6.6** (40.000 aves / 2.000 cerdos de cebo >30 kg / 750 cerdas). Ampliamente citados pero no verificados contra el texto original en esta sesión.
5. ⚠️ **Calendario escalonado de aplicación del Anexo I bis de la Directiva 2024/1785** por tramos de UGM. Confirmado que la aplicación empieza en **2030** y que hay medidas transitorias; no confirmados los tramos intermedios ni sus fechas.
6. ⚠️ **Eficacia porcentual de la alimentación baja en proteína (MTD 3)** sobre NH₃ y sobre olor. No cuantificada.
7. ⚠️ **Eficacia de cubrición de balsas sobre el OLOR.** La Decisión 2017/302 establece las cubiertas como MTD (14–17) pero **no publica porcentajes de reducción de olor**. Los porcentajes que circulan en literatura comercial no están verificados aquí.
8. ⚠️ **Velocidad de salida y caudal de extractores agrícolas** (5–10 m/s; caudales por plaza en verano e invierno). Valores de orden de magnitud de ingeniería, **no documentados** en esta revisión. Deben tomarse de la ficha técnica del ventilador instalado o medirse.
9. ⚠️ **Factores de emisión de H₂S por plaza.** No localizados.
10. ⚠️ **Factor de emisión de olor de terneros de cebo (35,6 ou_E/s)**, anómalamente alto frente al cerdo de cebo. Contrastar con la fuente primaria antes de usar.
11. ⚠️ **Vigencia de los factores neerlandeses.** La `Regeling geurhinder en veehouderij` fue **derogada el 01/01/2024**; los valores de la tabla A.2.1 son los de la versión histórica. Verificar los vigentes en la `Omgevingsregeling` antes de citarlos.

### F.2 Incertidumbres estructurales del método

**(a) La brecha del percentil — ✅ resuelta el 22/07/2026, después de redactar este documento.** Los criterios aplicables (Canarias, Países Bajos) son percentiles 98 de medias horarias, y **no existe un factor universal de conversión** desde la media. Cuando se escribió este informe la herramienta solo exportaba la media del periodo, lo que impedía afirmar cumplimiento. **Ya no**: se simula con `postfile=True` y se obtiene el P98 con `percentiles_por_receptor(pct=(98.0,), peak_factor=…)`. Lo que sigue siendo cierto es la advertencia de fondo: **comparar una media anual con un umbral P98 es metodológicamente incorrecto y, además, NO conservador**, porque el P98 es sustancialmente mayor que la media.

**(b) Transferencia factor↔modelo.** Los factores de olor neerlandeses están calibrados contra V-Stacks dentro de un sistema regulatorio cerrado. Usarlos con AERMOD y compararlos con umbrales neerlandeses **no reproduce el nivel de protección de origen**. Debe declararse en la memoria como hipótesis, y su efecto acotarse en el análisis de sensibilidad.

**(c) Doble corrección: percentil y pico-media.** Son dos problemas distintos. El **percentil** corrige la estadística temporal (qué hora del año se evalúa); la relación **pico-media** corrige la escala de promediado (media horaria del modelo frente a percepción en segundos). **Ambas se aplican, no una en lugar de la otra.** Ver [`../metodologia/olores_metodologia.md`](../metodologia/olores_metodologia.md).

**(d) Variabilidad intrínseca del foco de balsa.** Las medidas de campo publicadas tienen desviaciones típicas del orden de la propia media (±65 % a ±118 %). Si el resultado del estudio depende de la balsa, **el resultado es incierto en un factor 2 o más** salvo que se mida en campo.

**(e) Estacionalidad no capturada.** Una emisión anual media subestima el verano —justo cuando se producen las molestias— y sobreestima el invierno. Sin `EMISFACT` o escenarios estacionales separados, el modelo **no representa la situación de queja**.

**(f) *Building downwash*.** En naves ganaderas, largas, bajas, y con los focos situados en el propio edificio, la estela es previsiblemente dominante para los extractores laterales. **Omitir BPIPPRM es un error no conservador de primer orden**, no un refinamiento opcional.

**(g) Emisión no estacionaria.** Agitado y vaciado de fosas, vaciado de estercolero al final del lote avícola, aplicación de purín al campo: son **episodios de horas** con emisiones muy superiores al régimen normal, y son la causa habitual de las quejas reales. Un modelo de régimen continuo, por bien calibrado que esté, **no los representa**. Deben abordarse como escenarios separados o, cuando eso no sea posible, mediante medidas de gestión (D.4, D.5) y reconocerse explícitamente como limitación.

**(h) Factor hedónico.** La ou_E mide **intensidad**, no **desagrado**. El olor ganadero tiene un tono hedónico marcadamente negativo, de modo que el mismo número de ou_E genera más molestia que en otras actividades. Ningún modelo de dispersión captura esto; sólo lo captura el umbral, y sólo si el umbral se ha fijado teniendo en cuenta el tipo de actividad —que es exactamente lo que hacen tanto el Decreto canario (con su categorización) como el sistema neerlandés (con su norma específica de olor ganadero).
