---
tipo: olores-alimentaria
fuente: mixta
contaminantes: [ou_E, COV, NH3, H2S]
estadistico: percentil-98
umbral: 3 / 6 / 9 ou_E/m3 (P98 anual, Decreto 185/2025 Canarias; la industria alimentaria se reparte entre las TRES categorias segun subsector). Referencia complementaria verificada: 1,5 / 3,0 / 6,0 ou_E/m3 (C98 horario) del criterio britanico H4-IAQM segun ofensividad, y 0,5-5 ou_E/m3 (P98) de las bijzondere regelingen neerlandesas
ambito: España + UE
anio: 2026
origen: vigilancia tecnologica
---

# Industria agroalimentaria — estudio de olores

> La industria alimentaria es el único sector donde el **mismo umbral no vale para toda la rama**: un matadero y una panadería son ambos «industria alimentaria», y los dos marcos que fijan valores numéricos —el canario y el británico— los separan por un factor 3 y 4 respectivamente. Elegir el subsector es, literalmente, elegir el umbral.
> Existen factores de emisión de olor publicados y trazables para **harinas y grasas animales (rendering)** y para **piensos**, expresados en ou_E por tonelada procesada, no en ou_E/s: convertirlos exige una hipótesis de producción horaria que es, en la práctica, la mayor fuente de error del estudio.
> Buena parte del sector es **estacional** (almazaras, conserveras, bodegas) o **discontinuo por lotes** (piensos, ahumaderos), y la guía neerlandesa dice de forma explícita que en esos casos **el P98 no describe bien la molestia**. Esto choca de frente con la limitación actual de la herramienta, que ni siquiera puede calcular el P98 (ver B).

Documentos previos que **no** se repiten aquí y a los que hay que remitirse:

- [`../normativa/marco_normativo_ES_UE.md`](../normativa/marco_normativo_ES_UE.md) — marco español y europeo, régimen IPPC/IED y **Decreto 185/2025 de Canarias** (3/6/9 ou_E/m³ al P98 anual). La clasificación de actividades del art. 6.2 reparte la industria alimentaria entre las tres categorías: ver apartado C.
- [`../normativa/criterios_olor_internacional.md`](../normativa/criterios_olor_internacional.md) — criterios de Países Bajos e Italia, con las correcciones sobre lo que se cita mal habitualmente (NeR y Wgv **derogadas** el 1/1/2024; factor pico-media italiano 2,3; percentil 98, nunca 99,5).
- [`../metodologia/olores_metodologia.md`](../metodologia/olores_metodologia.md) — olfatometría UNE-EN 13725, relación pico-media, cálculo de percentiles a partir de la salida de AERMOD, ley de Stevens y umbrales por compuesto.

Documentos hermanos con solape parcial: [`granjas.md`](granjas.md) (la materia prima viva y el purín), [`compostaje.md`](compostaje.md) (destino de subproductos vegetales) y [`edar.md`](edar.md) (la depuradora interna de la propia fábrica, que suele ser un foco propio y a menudo el más ofensivo del recinto).

---

## A. CÓMO MODELAR → para el agente 1

### A.1 Subsectores y sus focos característicos

La regla de partida es la misma que en el resto de la serie: **un foco es puntual si el aire sale por un orificio con velocidad y temperatura propias; es de área si sale por difusión sobre una superficie sin momento.** La particularidad de la industria alimentaria frente a la ganadería o el compostaje es que **la mayor parte de la emisión sí está canalizada** —hay extractores, chimeneas de cocción, secaderos, torres de enfriamiento— y por tanto la temperatura y la velocidad de salida **sí importan** y no pueden dejarse a valores por defecto.

La segunda particularidad, y la que más expedientes genera: **el foco pequeño en caudal suele ser el ofensivo**. El contenedor de subproductos, la sala de tripería, la balsa de la depuradora interna. Tienen un caudal ridículo comparado con la nave de proceso y son los que producen las denuncias.

| Subsector | Focos característicos | Tipo de fuente AERMOD | Notas de modelización |
|---|---|---|---|
| **Mataderos y salas de despiece** | Sala de sacrificio y escaldado (vapor caliente), **tripería y estómagos** (el foco ofensivo), depósito de sangre, contenedores de decomisos y SANDACH, playa de camiones de animales vivos, corrales de espera, depuradora interna | **POINT** para extractores de proceso; **AREAPOLY** para corrales, playa de descarga y balsas de la EDAR; **VOLUME** para muelles abiertos | La sangre y el contenido digestivo son los grandes responsables. El caudal de los extractores de tripería es pequeño y la concentración altísima. Los corrales de espera son un foco **ganadero** dentro de un foco industrial: ver [`granjas.md`](granjas.md) |
| **Subproductos animales (SANDACH), harinas y grasas** ⚠️ el más ofensivo | **Cocedores/digestores** (chimenea caliente y húmeda), **secadores**, prensas, condensadores, **recepción y tolva de materia prima** (foco difuso muy intenso), almacenamiento de grasa, biofiltro o lavador final | **POINT** para cocedores, secadores y salida de depuradora de gases; **AREAPOLY** para nave de recepción, playa de descarga y balsas | Es el subsector de referencia del olor alimentario y el único con **factores de emisión publicados y citables** (ver A.2). Distinguir el **aire de proceso** (caudal bajo, concentración enorme, siempre tratado) del **aire ambiente de nave** (caudal enorme, concentración baja): son dos focos con órdenes de magnitud distintos |
| **Secaderos de jamón y embutido curado** | **Extractores de las cámaras de secado y bodega** (aire húmedo, templado, saturado de aroma), sala de salazón, post-salado, cámaras de estufaje | **POINT**, uno por batería de extractores; a veces **AREAPOLY** si la ventilación es por rejilla de cubierta | Emisión **continua todo el año** pero con ciclo lento asociado a las fases de curación. Caudales grandes con concentración moderada. Hedónicamente el olor es **poco desagradable** (aroma cárnico curado), pero es denunciable por persistencia. ⚠️ Sin factores de emisión publicados que se hayan podido verificar (ver F) |
| **Industria láctea y quesera** | Torres de **secado por atomización** de leche/suero (chimenea muy caliente y con partículas), cámaras de maduración de queso, tratamiento de suero, depuradora interna | **POINT** para torres de secado y evaporadores; **AREAPOLY** para balsas y almacenamiento de suero | El suero en descomposición es el foco crítico, no el queso. Las torres de secado son chimeneas altas y calientes → **sobreelevación de pluma importante**, hay que caracterizarlas bien. En el decreto canario, «procesos lácteos» = Categoría 2 |
| **Conserveras y transformación de pescado** | Cocción y esterilización, **cocederos y autoclaves**, hornos, freidoras, línea de harina y aceite de pescado, almacenamiento de descartes y salmueras | **POINT** para cocederos, autoclaves y freidoras; **AREAPOLY** para depósitos de descartes y balsas | «Procesos que involucren restos de animales» y la producción de **harina de pescado** son de lo más ofensivo que existe. Fuertemente **estacional** (campaña) → ver A.3 |
| **Almazaras y orujeras** | Almazara: batidoras, tolvas de aceituna, patio, balsas de alpechín/alperujo. Orujera (extractora): **secaderos rotatorios de alperujo** (trómel, chimenea caliente), extracción con hexano, balsas y **eras de alperujo a la intemperie** | **POINT** para el secadero de la orujera (el foco dominante); **AREAPOLY** para patio, balsas y eras de alperujo | Dos actividades distintas que se confunden. La **almazara** tiene poco foco canalizado y mucho difuso; la **orujera** tiene una chimenea de secadero que es un foco puntual muy potente. Campaña de ~3–4 meses → ver A.3. El alperujo en balsa fermenta y sigue emitiendo **fuera de campaña** |
| **Bodegas y alcoholeras** | Depósitos de fermentación (venteo de CO₂ arrastrando ésteres), **destilación** en alcoholeras, tratamiento de orujos y lías, balsas de vinazas | **POINT** para venteos de fermentación y columnas de destilación; **AREAPOLY** para balsas de vinaza y pilas de orujo | La bodega emite un olor **hedónicamente positivo o neutro** durante 4–6 semanas de vendimia. La **alcoholera/vinaza** es distinta: olor claramente desagradable y continuo. No mezclarlas en el mismo escenario |
| **Panaderías industriales y tostaderos de café** | Hornos continuos, **tostadores de café** (chimenea caliente, con humos), enfriadores, extractores de amasado | **POINT** casi en su totalidad | Olor **no desagradable** (H positivo: la propia guía IAQM cita el olor a panadería como ejemplo de tono hedónico favorable) pero **plenamente denunciable** por frecuencia y persistencia. Es el subsector con el umbral **más permisivo** en los dos marcos numéricos disponibles: 9 ou_E/m³ en Canarias, 6 ou_E/m³ en el criterio británico |
| **Fabricación de piensos** | Prensa de granulado y **acondicionador de vapor** (foco dominante), enfriador de gránulo, molienda, secadero, silos y carga | **POINT** para enfriador y prensa; **AREAPOLY** para descarga de materias primas | Producción **por lotes** de ~1 h por batch, con materias primas que cambian por precio y estación. El factor de emisión varía **hasta ×80** según el % de proteína y la temperatura de la harina (ver A.2). Único subsector alimentario con caso documentado de límite de emisión **horario** en lugar de percentil de inmisión |

**Cuáles son canalizados y cuáles difusos, en una frase:** son **canalizados** el rendering, los secaderos de jamón, las torres lácteas, los cocederos de conservera, el secadero de orujera, los hornos y tostadores, y la prensa de piensos —es decir, el núcleo del proceso—; son **difusos** los patios, playas de descarga, corrales de espera, contenedores de subproductos, balsas de la depuradora interna, eras de alperujo y almacenamiento de suero —es decir, la logística y los residuos. **La emisión está en los primeros; las denuncias, normalmente, en los segundos.**

### A.2 Datos de emisión

Aviso previo y capital: **no existe una tabla europea consolidada de factores de emisión de olor para la industria alimentaria** equivalente a la que sí existe para ganadería. Lo que hay son factores por subsector concreto en la literatura italiana y neerlandesa. Lo que sigue es **sólo lo que se ha podido verificar**. El resto está en el apartado F, sin números inventados.

#### A.2.1 Cómo se define y se usa un factor de emisión de olor (OEF)

La formulación estándar, de Capelli, Sironi y colaboradores ([AIDIC, *Chemical Engineering Transactions* vol. 40, 2014](https://www.aidic.it/cet/14/40/033.pdf)):

```
OER = OEF × A × (1 − ORE)
```

donde **OER** es el caudal de olor en **ou_E/s** (lo que pide AERMOD), **OEF** el factor de emisión, **A** el índice de actividad (t/h procesadas, m³/h de agua tratada, cabezas…) y **ORE** la eficacia global de reducción del sistema de depuración instalado.

Tres consecuencias prácticas que el agente 1 debe interiorizar:

1. **El OEF casi nunca está en ou_E/s.** Está en ou_E por tonelada o por m³. Convertirlo a ou_E/s exige dividir por el tiempo, es decir, **fijar un régimen de producción horario**. Si se usa la producción media anual, se subestima el pico; si se usa la capacidad nominal, se sobreestima el año. Ésta es, junto con la altura, la decisión que más condiciona el resultado.
2. **Los OEF deben evaluarse por etapa de proceso, no para la planta entera.** El propio artículo insiste en ello: sumar un único OEF global oculta que hay etapas con OEF ~10⁸ y otras con ~10³.
3. **El factor (1 − ORE) es donde entra la medida correctora.** Un biofiltro con 95 % de eficacia no es un foco nuevo: es el mismo foco multiplicado por 0,05, y con **otra altura, otra temperatura y otra velocidad de salida** (ver A.3 y D).

#### A.2.2 Harinas y grasas animales (rendering / SANDACH) — el único subsector alimentario con OEF publicados

| Foco | OEF | Unidad | Fuente |
|---|---|---|---|
| **Aire de proceso** (cocedores, secadores) | **4,52 × 10⁸** | ou_E por tonelada procesada | Capelli et al., *Odour emission factors for assessment and prediction of Italian rendering plants odour impact*, **Chem. Eng. J. 131 (2007) 225–231** |
| **Mezcla de aire de proceso y aire ambiente de nave** | **8,02 × 10⁷** | ou_E/t | ídem |
| **Tanques de tratamiento de aguas residuales** | **3,53 × 10³** | ou_E/t | ídem |

⚠️ **Cautela obligatoria sobre esta tabla.** Los tres valores proceden de la referencia primaria correcta ([ScienceDirect S1385894706005067](https://www.sciencedirect.com/science/article/abs/pii/S1385894706005067)), pero se han obtenido a través de fuentes secundarias, sin acceso al texto completo de pago. **Antes de usarlos en un expediente hay que verificarlos sobre el artículo original**, en particular: si el índice de actividad es tonelada de materia prima o de producto acabado, y si el OEF de aire de proceso está referido a la emisión **antes o después** del sistema de depuración. La diferencia entre ambas lecturas es de uno o dos órdenes de magnitud. Obsérvese además la coherencia interna del dato: el aire de proceso es ~5,6 veces el de la mezcla con aire de nave, y ~10⁵ veces el de los tanques de agua.

#### A.2.3 Fabricación de piensos — rango verificado y su lección

De la [*Handleiding geur* neerlandesa (InfoMil/VROM, 2012)](https://olores.mma.gob.cl/wp-content/uploads/2019/03/Handleiding-geur.pdf), caso real de la provincia de Utrecht (apdo. 10.4):

| Producto y condición | Emisión de olor | Fuente |
|---|---|---|
| Pienso de vacuno, **7 % proteína** | **7 Mou_E por tonelada** | *Handleiding geur*, § 10.4.2 |
| Pienso de porcino, **22 % proteína, harina a 90 °C** | **570 Mou_E por tonelada** | ídem |

**Factor 80 de diferencia entre dos productos de la misma fábrica.** Los dos parámetros que gobiernan la emisión son el **porcentaje de proteína** y la **temperatura de la harina**. Este dato es el mejor argumento disponible para exigir, en cualquier subsector alimentario, que el escenario modelizado declare **qué se está produciendo y a qué temperatura**, y no sólo cuántas toneladas.

El mismo caso da la cifra de inmisión: una emisión media anual de **1.386 Mou_E/h** produjo **1,4 ou_E/m³ como P98** en viviendas a ~700 m, correspondiente a un valor hedónico H = −0,5. Y la conclusión regulatoria, que es lo más valioso: como la producción a plena capacidad (50 t/h) habría supuesto **17 veces** la emisión horaria compatible con ese nivel, la autoridad **no concedió la autorización sobre el P98** e impuso en su lugar un **límite de emisión horario**. El Consejo de Estado neerlandés no suspendió esa condición (auto 201106394/2/A4).

#### A.2.4 Lo que NO hay

No se han localizado factores de emisión de olor publicados y verificables para **secaderos de jamón**, **almazaras y orujeras**, **bodegas**, **industria láctea**, **panaderías** ni **tostaderos de café** expresados en ou_E/s o ou_E/(s·m²). Existen estudios de compuestos aromáticos (p. ej. el trabajo sobre odorantes clave del jamón ibérico curado, que identifica ~40 compuestos olorosos, de los cuales 20–29 activos), pero **caracterización química no es caudal de olor** y no puede convertirse en ou_E: el motivo está explicado en [`../metodologia/olores_metodologia.md`](../metodologia/olores_metodologia.md), § A.4. Para estos subsectores **la única vía defendible es la medida en chimenea por olfatometría dinámica UNE-EN 13725**. Ver F.

#### A.2.5 Sustituto legítimo mientras no haya medida: los NEA-MTD de COVT

Cuando no hay olfatometría, el BREF de alimentación sí da límites verificados de **COVT** para ahumaderos, que son focos alimentarios canalizados típicos. **No son ou_E**, pero sirven para acotar el orden de magnitud de la emisión orgánica y para dimensionar la depuradora:

| Proceso | Parámetro | NEA-MTD (media del periodo de muestreo) | Nota |
|---|---|---|---|
| **Ahumado de pescado** (Cuadro 11, MTD 26) | COVT | **15–50 mg/Nm³** | El extremo inferior se alcanza con **oxidación térmica**. No aplicable si la carga de COVT < 500 g/h |
| **Ahumado de carne** (Cuadro 18, MTD 29) | COVT | **3–50 mg/Nm³** | El extremo inferior se alcanza con **adsorción u oxidación térmica**. No aplicable si la carga de COVT < 500 g/h |

Fuente: [Decisión de Ejecución (UE) 2019/2031](https://www.boe.es/buscar/doc.php?id=DOUE-L-2019-81871), anexo, cuadros 11 y 18 ([texto consolidado en PDF, MAPA](https://www.mapa.gob.es/dam/mapa/contenido/alimentacion/temas/industria-agroalimentaria/sostenibilidad-de-la-industria-agroalimentaria/decisionejecucionue201_2031-mtd_iab_leche.pdf)).

⚠️ **No se puede convertir mg/Nm³ de COVT en ou_E/m³.** No existe factor de conversión general y cualquiera que se proponga es específico de la mezcla. Úsese como indicador complementario, nunca como sustituto del ou_E.

### A.3 Parámetros de modelización

#### A.3.1 Focos canalizados: temperatura y velocidad no son opcionales

A diferencia del compostaje o las balsas, aquí la mayoría del caudal sale por chimenea. Los tres parámetros que AERMOD usa para la sobreelevación de pluma —**altura, temperatura de salida y velocidad de salida**— tienen efecto de primer orden, y en esta industria son a menudo *favorables*: los gases de cocedor, secadero de orujera, torre láctea o tostador de café salen **calientes**, y la pluma sube. Declararlos a temperatura ambiente por comodidad es un error conservador pero grosero, que puede multiplicar el impacto calculado.

Hay dos trampas específicas del sector:

- **Gases saturados de humedad.** Secaderos de jamón, cocedores, autoclaves y torres de secado emiten aire prácticamente saturado. AERMOD no modela la condensación del penacho; el penacho visible de vapor no es el penacho de olor. No confundir uno con otro al validar contra observaciones de campo.
- **Salidas de depuradora de gases.** La chimenea del **biofiltro** es el caso opuesto: gran superficie, velocidad de salida muy baja, temperatura casi ambiente. **No tiene prácticamente sobreelevación de pluma.** Un biofiltro superficial se modela mejor como **AREAPOLY a la altura del lecho** que como punto; modelarlo como chimenea con velocidad ficticia le regala una elevación que no existe y subestima el impacto. Ver D.

#### A.3.2 Altura de emisión — el parámetro más sensible

El equipo ha medido que **el máximo de concentración varía ×12 entre 1 y 6 m de altura de emisión**. En esta industria eso se traduce directamente en:

- Los focos difusos ofensivos (contenedor de subproductos, playa de descarga, balsa) están **todos** en el rango 0–3 m, es decir, en la zona de máxima sensibilidad. **Es donde hay que gastar el esfuerzo de caracterización.**
- Un error de 1 m en la altura del contenedor de decomisos pesa más en el resultado que un error del 50 % en el caudal de la chimenea del secadero.
- Corolario para la medida correctora: **elevar y canalizar un foco difuso bajo es, casi siempre, la intervención más rentable**, muy por delante de mejorar el rendimiento de una depuradora que ya trata el aire de proceso.

#### A.3.3 Estacionalidad y funcionamiento discontinuo — el problema estructural del sector

Éste es el punto donde la industria alimentaria se separa del resto de la serie. Muchos subsectores **no emiten 8.760 h/año**:

| Subsector | Régimen típico | Implicación |
|---|---|---|
| **Almazaras y orujeras** | Campaña de aceituna, ~3–4 meses (nov–feb) | Emisión concentrada en el trimestre de peor dispersión (invierno, inversiones térmicas). Las **balsas y eras de alperujo siguen emitiendo fuera de campaña** |
| **Conserveras y pescado** | Campaña según especie | Idem, con picos de días |
| **Bodegas** | Vendimia, 4–6 semanas (sep–oct) | Emisión muy corta y muy intensa |
| **Azucareras y deshidratadoras** | Campaña (la propia IED reconoce el régimen ≤90 días consecutivos) | Ver C |
| **Piensos, ahumaderos** | Continuo pero **por lotes** de ~1 h | Fluctuación fuerte *dentro* del año y *dentro* del día |
| **Rendering, secaderos de jamón, lácteas** | Continuo | Caso «normal» |

La consecuencia normativa está escrita de forma explícita en la [*Handleiding geur*](https://olores.mma.gob.cl/wp-content/uploads/2019/03/Handleiding-geur.pdf) (§ 9.1 y anexo 9):

> Para una fuente de olor **continua** el percentil 98 es una medida eficaz. La carga de olor de fuentes **no continuas** —duración de la emisión **inferior a 3.500 horas al año**— se describe mejor mediante **percentiles superiores al 98**: los habituales son el **99,5, el 99,9 y el 99,99**.

Y da el precedente: las propias *bijzondere regelingen* neerlandesas usan percentiles 98 / 99,5 / 99,9 para compostaje de verde y 98 / 99,99 para plantas de asfalto.

**Traducción operativa para el agente 1:** una almazara, una conservera de campaña o una bodega **caen de lleno bajo el umbral de las 3.500 h/año**. Evaluarlas con un P98 anual es metodológicamente incorrecto y, además, *favorable al promotor*: con la fuente apagada el 70 % del año, el percentil 98 puede caer casi a cero mientras las molestias reales se concentran en la campaña. Si el estudio se hace con P98, **hay que decirlo y justificarlo**, o usar en paralelo un percentil superior o un escenario «sólo campaña».

Mecanismo en AERMOD: la variación temporal se introduce con **factores de emisión variables** (`EMISFACT`, con opciones por estación, por hora del día, por mes, o combinaciones estación/hora/día-semana), no editando el caudal a mano. Poner un caudal medio anual «diluido» sobre 8.760 horas es el error equivalente a promediar la campaña, y borra exactamente el fenómeno que se quiere evaluar.

#### A.3.4 Fluctuaciones dentro de la hora, y las paradas

AERMOD trabaja con medias horarias. Hay operaciones alimentarias cuya emisión dura **minutos**: la propia guía neerlandesa pone como ejemplo la **retirada de residuos de matadero, con una duración media de 10 minutos por operación**, y advierte que esos picos intrahorarios son fuente de molestia por sí mismos. La norma técnica neerlandesa **NTA 9065** da un método para traducir la variación real dentro de la hora a una emisión horaria media. Alternativa regulatoria que ya se ha usado: fijar una **emisión momentánea máxima** en la autorización.

**Paradas.** Dos tipos, con tratamiento distinto: la **parada programada** (limpieza anual, vacío sanitario) reduce la emisión y debe reflejarse; la **parada no programada o el fallo de la depuradora** es lo contrario —un escenario de emisión sin abatimiento— y **no pertenece al escenario anual**, sino a un escenario de contingencia separado. No promediar nunca un fallo dentro del año: se diluye justo lo que se quería evaluar.

### A.4 Errores típicos

1. **Confundir concentración de olor con caudal de olor.** Una medida de chimenea da ou_E/m³. AERMOD necesita **ou_E/s**. Hay que multiplicar por el caudal volumétrico: `OER [ou_E/s] = C [ou_E/m³] × Q [m³/s]`. Es el error más frecuente y produce resultados absurdos por varios órdenes de magnitud.
2. **Mezclar Nm³ y m³ reales.** Los NEA-MTD y los informes de laboratorio vienen en **Nm³** (normalizados); los caudales de ventilación de proceso, en m³/h reales, calientes y húmedos. En un secadero a 70 °C el error de no corregir supera el 20 %. Declarar siempre la base (seco/húmedo, temperatura, oxígeno de referencia).
3. **Meter toda la fábrica en un único polígono de área.** Destruye la información de altura, que es el parámetro ×12. Hay que separar al menos: proceso canalizado, logística/patio y residuos.
4. **Olvidar la depuradora interna de la propia industria.** Casi toda industria alimentaria tiene una EDAR propia, y con frecuencia es el foco más ofensivo del recinto —en el criterio británico, «procesos con efluente séptico o fangos» está en la categoría **más ofensiva**, más que el propio matadero. Ver [`edar.md`](edar.md).
5. **Modelar el biofiltro como una chimenea.** Le regala sobreelevación de pluma que no tiene (A.3.1).
6. **Aplicar un P98 anual a una fuente de campaña** sin advertirlo (A.3.3).
7. **Usar COVT como sustituto del ou_E** (A.2.5).
8. **Elegir el umbral por «industria alimentaria» en bloque.** Los marcos numéricos disponibles separan matadero de panadería por un factor 3 a 4. Hay que justificar el subsector y, con él, la categoría.
9. **Ignorar el tono hedónico.** Una panadería y una harinera de pescado con la misma concentración calculada no producen la misma molestia. La guía neerlandesa lo cuantifica: con valor hedónico **por debajo de H = −2**, para fuentes continuas **se espera molestia grave**; por debajo de **0,5 ou_E/m³ al P98** (y H no inferior a ~−0,5) **no se espera molestia**.
10. **Dar por hecho que el olor agradable no es denunciable.** Lo es, por frecuencia y persistencia. Por eso el decreto canario incluye expresamente panaderías, confiterías, chocolate y torrefacción de café —con umbral más laxo, pero incluidas.

---

## B. ESTRUCTURA DEL INFORME → para el agente 2

Secciones numeradas de un informe real de dispersión de olores para una industria agroalimentaria.

**1. Objeto y alcance**
Actividad, subsector, encuadre administrativo (EIA / AAI / licencia / requerimiento por denuncias) y motivo del estudio.

**2. Descripción de la instalación y del proceso**
2.1 Capacidad de producción (nominal y real) y **régimen de funcionamiento**: horas/año, campaña, turnos, lotes.
2.2 Diagrama de proceso con **identificación de los puntos de generación de olor**.
2.3 Gestión de subproductos y residuos: SANDACH, aguas residuales, almacenamiento.
> *Tabla 1: régimen de funcionamiento por foco (h/día, días/año, estacionalidad).* Es la tabla que sostiene todo el apartado A.3.3.

**3. Inventario de focos**
> *Tabla 2 (la tabla central del informe): para cada foco — identificador, coordenadas UTM, tipo de fuente AERMOD (POINT / AREAPOLY / VOLUME), altura de emisión, diámetro o geometría del polígono, temperatura y velocidad de salida, caudal volumétrico, concentración de olor, caudal de olor en ou_E/s, y **origen del dato** (medido / factor de emisión / estimado).*

La columna «origen del dato» no es decorativa: es lo primero que mira un revisor.
> *Figura 1: planta del recinto con los focos y su tipología.*

**4. Caracterización de la emisión**
4.1 Campaña de muestreo olfatométrico: puntos, fechas, condiciones de operación durante el muestreo, laboratorio y acreditación **UNE-EN 13725**.
4.2 Focos no medidos: factor de emisión empleado, **fuente citada** y justificación de la transferencia.
4.3 **Análisis de incertidumbre del caudal de olor** — apartado obligatorio, no opcional (ver A.2 y F).

**5. Entorno y receptores**
5.1 Meteorología: estación, año completo, tratamiento AERMET, rosa de vientos.
5.2 Topografía y usos del suelo.
5.3 **Inventario de receptores sensibles** con distancia y dirección respecto a los focos.
> *Figura 2: rosa de vientos. Figura 3: receptores sobre ortofoto.*

**6. Metodología de modelización**
6.1 Modelo, versión y opciones de ejecución.
6.2 Malla de receptores y receptores discretos.
6.3 Tratamiento de la **variación temporal de la emisión** (factores `EMISFACT`).
6.4 Escenarios: operación normal, campaña/punta, y **contingencia por fallo de depuración**.

**7. Resultados**
7.1 Resultados por escenario.
7.2 **Contribución de cada foco al total** — el análisis que de verdad orienta la medida correctora.
7.3 Análisis de sensibilidad: como mínimo a la **altura de emisión** y al **caudal de olor**.
> *Figura 4: isopletas de concentración. Tabla 3: concentración en cada receptor sensible. Tabla 4: contribución porcentual por foco. Tabla 5: sensibilidad.*

**8. Comparación con criterios de referencia**
Umbral aplicable y su justificación (ver C), y **declaración explícita del estadístico realmente calculado** frente al estadístico exigido.

> ⚠️ **Limitación de la herramienta que debe constar en este apartado, redactada sin ambigüedad.**
> La herramienta exporta hoy únicamente la **media del periodo simulado**. **No** produce serie horaria completa ni el enésimo valor más alto por receptor. En consecuencia **no es posible calcular el percentil 98 de medias horarias** y, por tanto, **no puede acreditarse el cumplimiento del valor objetivo del art. 22.2 del Decreto 185/2025 de Canarias, ni del criterio C98 británico, ni de ninguna de las *bijzondere regelingen* neerlandesas**, que se expresan todos sobre ese mismo estadístico.
> Lo que sí puede hacerse con la salida actual: comparar escenarios entre sí, jerarquizar la contribución de los focos, dimensionar medidas correctoras y localizar la zona de máxima afección. Lo que **no** puede hacerse: afirmar que se cumple o se incumple un umbral de P98.
> Mientras la salida no se amplíe, el informe debe presentar el resultado como **media del periodo** y decir expresamente que la comparación con el umbral queda pendiente. Presentar una media anual como si fuera un P98 es un error grave y detectable: para una fuente continua el P98 es **varias veces** la media, y para una fuente de campaña la relación es aún mayor y de signo poco intuitivo. El procedimiento correcto de cálculo del percentil, para cuando la salida lo permita, está en [`../metodologia/olores_metodologia.md`](../metodologia/olores_metodologia.md), § D.

**9. Medidas correctoras propuestas**
Con eficacia esperada, foco sobre el que actúan y **recálculo del escenario con medidas**.

**10. Plan de gestión de olores**
Exigido como MTD por los dos BREF aplicables (ver C): protocolo de actuaciones y plazos, protocolo de monitorización, protocolo de respuesta a denuncias y programa de prevención y reducción.

**11. Conclusiones**

**12. Bibliografía y anexos**
Certificados de olfatometría, ficheros de entrada y salida del modelo, ficha meteorológica.

---

## C. NORMATIVA APLICABLE

El marco general está en [`../normativa/marco_normativo_ES_UE.md`](../normativa/marco_normativo_ES_UE.md). Aquí sólo lo específico del sector.

### C.1 Decreto 185/2025 de Canarias — la industria alimentaria está en las TRES categorías

Es el único texto español vigente con valores numéricos de inmisión de olor (art. 22.2: **3 / 6 / 9 ou_E/m³** al **P98 de medias horarias en año natural**). La clasificación del art. 6.2 reparte la industria alimentaria así:

| Categoría | Valor objetivo (P98 anual) | Subsectores alimentarios listados literalmente |
|---|---|---|
| **1** — molestia alta | **3 ou_E/m³** | **mataderos**; **aprovechamiento de subproductos de origen animal**; **procesos que involucren restos de animales**; tratamiento de aguas residuales e instalaciones accesorias *(la EDAR interna de la fábrica)* |
| **2** — media | **6 ou_E/m³** | **procesado de carne**; **ahumado de alimentos**; **procesos lácteos**; **refinado de aceite**; **procesamiento de grasas y aceites**; **fabricación de cerveza**; **producción de comidas para animales** *(piensos)*; producción de aromas y fragancias; tratamiento de productos orgánicos; procesos de comida para engorde |
| **3** — baja | **9 ou_E/m³** | **fabricación industrial de pan, masas diversas o galletas**; **confiterías**; **fabricación de chocolate o cacao**; **tostación o torrefacción de café**; **secado de productos vegetales** |

Dos observaciones de aplicación:

- **Subsectores no listados.** No aparecen expresamente los **secaderos de jamón**, las **bodegas y alcoholeras**, las **almazaras** ni las **conserveras de pescado**. Los arts. 6.3 y 6.4 permiten al órgano competente **encajar por analogía** las actividades no listadas y **reclasificar por orden motivada**. En un informe hay que **proponer y justificar** la analogía, no darla por hecha: un secadero de jamón es razonablemente «procesado de carne» (Cat. 2); una orujera podría defenderse como «secado de productos vegetales» (Cat. 3) o como «procesamiento de grasas y aceites» (Cat. 2), y la diferencia entre ambas lecturas es de 6 a 9 ou_E/m³. ⚠️ Decisión no evidente: hay que argumentarla.
- **Una fábrica puede estar en dos categorías a la vez.** Un matadero con sala de despiece y EDAR propia tiene focos de Categoría 1 y de Categoría 2. El decreto fija el valor por actividad; lo prudente es aplicar el más restrictivo al conjunto y decirlo.

### C.2 Encaje en la IED — dos BREF distintos, con umbrales distintos

Este es el punto que más se equivoca: **la industria alimentaria no tiene un BREF, tiene dos**, y desde 2023 el reparto ha cambiado.

**(a) BREF FDM — [Decisión de Ejecución (UE) 2019/2031](https://www.boe.es/buscar/doc.php?id=DOUE-L-2019-81871)**, industrias de alimentación, bebida y leche. Ámbito verificado sobre el texto:

| Actividad anexo I DEI | Umbral de capacidad |
|---|---|
| **6.4.b.i** — materia prima **solo animal** (que no sea exclusivamente leche) | **> 75 t/día** de productos acabados |
| **6.4.b.ii** — materia prima **solo vegetal** | **> 300 t/día**, o **> 600 t/día si la instalación funciona ≤ 90 días consecutivos** en un año |
| **6.4.b.iii** — materias animales y vegetales | **> 75 t/día si A ≥ 10**; en otro caso **> [300 − (22,5 × A)] t/día**, siendo A el % en peso de materia animal |
| **6.4.c** — **tratamiento y procesado de leche solamente** | **> 200 t/día de leche recibida** (valor medio anual) |
| **6.11** — tratamiento independiente de aguas residuales | cuando la carga contaminante principal proceda de 6.4.b o 6.4.c |

> El umbral **doble para vegetales (300 / 600 t/día según ≤90 días consecutivos)** es la constatación normativa de la estacionalidad descrita en A.3.3. Es directamente pertinente para **almazaras, conserveras vegetales y azucareras**: una instalación de campaña puede quedar fuera de la IED con el doble de capacidad diaria. Verificar siempre el criterio de «días consecutivos».

**MTD relevante para olor — MTD 15**, verbatim:

> «Para evitar o, cuando ello no sea posible, reducir la emisión de olores, la MTD consiste en establecer, aplicar y revisar periódicamente un **plan de gestión de olores** como parte del sistema de gestión ambiental (véase MTD 1), que incluya todos los elementos siguientes: — Un protocolo que contenga actuaciones y plazos. — Un protocolo para la **monitorización de los olores**. Puede complementarse con **mediciones o estimaciones de la exposición a los olores o la estimación del impacto de los olores**. — Un protocolo de respuesta a incidentes identificados en relación con los olores, por ejemplo, denuncias. — Un programa de prevención y reducción de olores destinado a determinar la fuente o las fuentes, medir o estimar la exposición a los olores, caracterizar las contribuciones de las fuentes, y aplicar medidas de prevención y/o reducción.»
>
> *Aplicabilidad:* «MTD 15 solo es aplicable en los casos en que se prevén molestias debidas al olor en **receptores sensibles** o se haya confirmado la existencia de tales molestias.»

La frase «estimación del impacto de los olores» y «caracterizar las contribuciones de las fuentes» es **el gancho normativo europeo directo para un estudio de dispersión**, en paralelo al del art. 11.3 del decreto canario.

**No hay NEA-MTD de concentración de olor en 2019/2031.** Los únicos NEA-MTD relacionados son los de COVT en ahumaderos (A.2.5).

**(b) BREF de mataderos y subproductos — [Decisión de Ejecución (UE) 2023/2749](https://www.boe.es/buscar/doc.php?id=DOUE-L-2023-81835)**, de 11 de diciembre de 2023, con [corrección de errores](https://www.boe.es/buscar/doc.php?id=DOUE-L-2024-80035) de enero de 2024. Sustituye para estas actividades al antiguo BREF SA. Ámbito verificado:

| Actividad anexo I DEI | Umbral |
|---|---|
| **6.4.a** — **mataderos** | capacidad de producción de **canales > 50 t/día** |
| **6.5** — **eliminación o aprovechamiento de canales o desechos de animales** *(rendering, harinas, grasas)* | capacidad de tratamiento **> 10 t/día** |
| **6.11** — tratamiento independiente de aguas residuales asociado | — |

Contenido sobre olor: **MTD 18** — plan de gestión de olores; **MTD 25** — técnicas de prevención y reducción de olores (separación de residuos, recogida rápida, almacenamiento en recipientes cerrados, tratamiento biológico, sistemas de tratamiento de gases residuales); **MTD 8** — monitorización de la **concentración de olor según EN 13725**, aplicable a mataderos, incineración de canales, fabricación de gelatina, producción de harina y aceite de pescado y aprovechamiento de subproductos; **MTD 12.a** — recogida rápida y almacenamiento en recipientes o salas cerrados, durante el menor tiempo posible.

⚠️ La numeración MTD 8 / 18 / 25 procede de dos consultas concordantes al texto de EUR-Lex, pero **no se ha podido reproducir el articulado íntegro verbatim**; confírmese contra el texto consolidado antes de citarla en un expediente, teniendo en cuenta además la corrección de errores de 2024.

> **Lo importante de este BREF:** es el primero del ámbito alimentario que exige **monitorización de olor por EN 13725 como MTD**, no sólo un plan de gestión. Para un matadero >50 t/día o una planta de harinas >10 t/día, la olfatometría deja de ser opcional.

### C.3 Reglamento SANDACH

[Reglamento (CE) n.º 1069/2009](https://eur-lex.europa.eu/legal-content/ES/TXT/?uri=CELEX:32009R1069) y su reglamento de aplicación [(UE) n.º 142/2011](https://eur-lex.europa.eu/legal-content/ES/TXT/?uri=CELEX:32011R0142) rigen los subproductos animales no destinados a consumo humano, clasificados en categorías 1, 2 y 3 según riesgo sanitario. Guía interpretativa española: [AESAN](https://www.aesan.gob.es/AECOSAN/docs/documentos/seguridad_alimentaria/gestion_riesgos/guia_sandach.pdf).

Su relevancia para un estudio de olores es **indirecta pero determinante**: el reglamento impone plazos y condiciones de recogida, refrigeración y almacenamiento de los subproductos por motivos **sanitarios**, y esas mismas condiciones son las que gobiernan la emisión de olor. En la práctica, la exigencia sanitaria de retirada rápida y almacenamiento cerrado **es ya una medida correctora de olor**, y su incumplimiento es la causa habitual de los episodios de queja en mataderos y salas de despiece. Un informe que proponga «retirada diaria de subproductos» como medida correctora debe comprobar antes si ya es obligatoria por SANDACH — en cuyo caso no es una medida adicional, sino el cumplimiento de la línea base.

### C.4 Los otros dos marcos numéricos que se citan

Ninguno es derecho español, pero ambos se usan como referencia y ambos **discriminan por subsector alimentario**, que es justo lo que aquí interesa.

**Reino Unido — criterio H4, recogido en la [guía IAQM sobre evaluación de olor (2014), Tabla 5](https://www.iaqm.co.uk/text/guidance/odour-guidance-2014.pdf).** Verbatim:

| Criterio, C98 (ou_E/m³) | Ofensividad | Fuentes de emisión listadas |
|---|---|---|
| **1,5** | *Most Offensive* | Procesos con **restos animales o de pescado en descomposición**; procesos con efluente séptico o fangos; olores biológicos de vertedero |
| **3,0** | *Moderately Offensive* | Ganadería intensiva; **fritura de grasa (procesado de alimentos)**; **procesado de remolacha azucarera**; compostaje de verde bien aireado |
| **6,0** | *Less Offensive* | **Cervecería**; **confitería**; **café** |

El estadístico es el **percentil 98 de medias horarias**, el mismo que el canario. La IAQM matiza que, a falta de información dosis-respuesta completa, **el criterio apropiado en un caso concreto puede situarse entre 1 y 10 ou_E/m³ como P98**, y que la elección debe justificarse profesionalmente.

**Países Bajos** — ver [`../normativa/criterios_olor_internacional.md`](../normativa/criterios_olor_internacional.md) para el estado actual (NeR derogada en 2024). Lo específicamente alimentario: de las 15 *bijzondere regelingen* que existieron, **ocho eran de industria alimentaria o afín** —industria transformadora de patata (VAVI), industria cárnica (PVVE), fábricas de galletas y bollería (Verbisko), fábricas de cacao (NCV), cervecerías (CBK), grandes panaderías y fábricas de pan (NBS), fábricas de aromas y saborizantes (NEA) y fábricas de piensos (FNM)—. Los valores de contraste iban de **0,5 ou_E/m³** (depuradoras) a **5 ou_E/m³** (panaderías) como **percentil 98** ([*Handleiding geur*, § 8](https://olores.mma.gob.cl/wp-content/uploads/2019/03/Handleiding-geur.pdf)), con las reglas de interpretación citadas en A.4.9.

> **Los tres marcos coinciden en el orden y casi en la escala.** Restos animales y fangos, lo más restrictivo; carne, grasas y lácteos, intermedio; cervecería, panadería y café, lo más permisivo. Canarias 3/6/9, Reino Unido 1,5/3/6, Países Bajos 0,5–5. **Ese acuerdo cualitativo es el mejor argumento disponible para justificar la elección de umbral en un expediente español fuera de Canarias**, donde no hay valor legal alguno.

---

## D. MEDIDAS CORRECTORAS

Orden de intervención, de más a menos rentable. Nótese que coincide con la jerarquía de las MTD: primero evitar, luego confinar, y sólo al final tratar.

**1. Prevención en origen y gestión de subproductos.** La más barata y la más eficaz en esta industria. Refrigeración de subproductos, recogida rápida, contenedores cerrados, limpieza frecuente, evitar acumulación de sangre y contenido digestivo. Es MTD 12.a de la Decisión 2023/2749 —«se recogen rápidamente… y se almacenan en recipientes o salas cerrados… durante el menor tiempo posible»— y en buena medida ya es obligación sanitaria SANDACH (C.3). La guía neerlandesa lo formula como condición de autorización: vaciar el residuo **con frecuencia suficiente y en momentos aceptables para los vecinos**, con la autoridad facultada para prescribirlo.

**2. Confinamiento y canalización de focos difusos.** Cerrar la playa de descarga, poner el contenedor bajo cubierto, mantener depresión en las salas de proceso, cubrir balsas. **Es la medida con mejor relación coste-eficacia según la física del problema**: convierte un foco de 1–2 m de altura —zona de máxima sensibilidad, factor ×12 medido por el equipo— en un foco canalizado y elevado. Efecto doble: reduce la emisión difusa y permite tratar el aire.

**3. Condensadores en secaderos y cocedores.** Primera etapa obligada en rendering y en secaderos de orujera: el grueso de la carga odorífera va en el vapor. Condensar reduce drásticamente el caudal a tratar y hace viable la etapa siguiente. En el caso documentado de cervecería, **la condensación por sí sola alcanzaba el 97 %** de reducción del olor de los vapores de cocción del mosto.

**4. Lavadores químicos (scrubbers).** Ácido para compuestos nitrogenados (aminas, NH₃), alcalino u oxidante para azufrados (H₂S, mercaptanos). Habituales en rendering en 2–3 etapas. Recogidos como técnica en MTD 26 y MTD 29 de la Decisión 2019/2031 y en MTD 25 de la 2023/2749.

**5. Biofiltros.** Técnica MTD 26.a de la 2019/2031, descrita verbatim como: *«el flujo de gases residuales pasa a través de un lecho de material orgánico (turba, brezo, raíces, corteza de árbol, compost, madera blanda) o de material inerte (arcilla, carbón activo, poliuretano), donde los componentes orgánicos —y algunos inorgánicos— se transforman por acción de microorganismos naturalmente presentes».* Requiere caudal estable, humedad y temperatura controladas, y **acondicionamiento previo** (humidificación, a veces lavador). Punto de modelización crítico: la salida del biofiltro es superficial, fría y lenta → **AREAPOLY, no POINT** (A.3.1).

**6. Oxidación térmica (regenerativa o recuperativa).** La técnica de mayor eficacia y mayor coste energético. Es el extremo inferior de los NEA-MTD de COVT en ahumaderos: **15–50 mg/Nm³ en pescado y 3–50 mg/Nm³ en carne, alcanzándose el límite inferior con oxidación térmica** (o adsorción, en carne). Descrita en el BREF como *«oxidación de los gases combustibles y las sustancias olorosas presentes en un flujo de gas residual»*.

**7. Adsorción sobre carbón activo.** MTD 29.a para ahumado de carne. Adecuada para caudales pequeños y concentraciones bajas; coste de reposición del lecho.

**8. Uso de humo purificado.** Específica de ahumaderos (MTD 26.e y 29.d): generar el humo a partir de condensados primarios purificados en lugar de combustión directa. Elimina el foco en origen en vez de tratarlo.

### Eficacias — sólo lo verificado

| Técnica | Eficacia | Contexto y fuente |
|---|---|---|
| **Condensación** (vapores de cocción de mosto, cervecería) | **97 %** de reducción de emisión de olor | Motivación de resolución de la Provincia de Zuid-Holland, 13/11/2003, recogida en [*Handleiding geur* § 10.5.1](https://olores.mma.gob.cl/wp-content/uploads/2019/03/Handleiding-geur.pdf) |
| **Condensación + postcombustión** (íd.) | **99 %**, tanto en emisión como en inmisión | ídem |
| **Oxidación térmica / adsorción** en ahumaderos | Permite alcanzar el extremo inferior de los NEA-MTD: **3 mg/Nm³** de COVT (carne), **15 mg/Nm³** (pescado) | [Decisión (UE) 2019/2031](https://www.boe.es/buscar/doc.php?id=DOUE-L-2019-81871), cuadros 11 y 18 |

Coste de referencia del mismo caso de cervecería, útil para la ponderación coste-eficacia que exige la MTD: **550.000 € de inversión y 87.000 €/año** de explotación (nivel de costes 1999) para una producción de 13 millones de hectolitros, equivalente a **~0,002 céntimos de euro por botella de 30 cl**. La autoridad consideró el coste razonable y exigió la medida.

⚠️ **No se han incluido eficacias de biofiltros ni de lavadores** porque no se ha localizado una fuente primaria que las cuantifique **específicamente para olor** en industria alimentaria. Circulan cifras del 90–99 % para biofiltros, pero **no se han verificado** y no deben citarse como dato. Ver F.

> **Aviso de expectativas, remitido a [`../metodologia/olores_metodologia.md`](../metodologia/olores_metodologia.md) § E:** por la ley de Stevens, la percepción crece con la potencia de la concentración, no linealmente. **Una reducción del 90 % en ou_E/s no reduce la molestia percibida en un 90 %**, sino mucho menos. Es la razón por la que instalaciones que han invertido en depuración siguen recibiendo denuncias, y debe advertirse **antes** de prometer un resultado.

---

## E. FUENTES

**Normativa europea**
- [Decisión de Ejecución (UE) 2019/2031](https://www.boe.es/buscar/doc.php?id=DOUE-L-2019-81871) — MTD industrias de alimentación, bebida y leche (BREF FDM). Ámbito, MTD 15 (olores), MTD 26 y 29 y cuadros 11 y 18 (NEA-MTD de COVT en ahumaderos). [Texto en PDF, MAPA](https://www.mapa.gob.es/dam/mapa/contenido/alimentacion/temas/industria-agroalimentaria/sostenibilidad-de-la-industria-agroalimentaria/decisionejecucionue201_2031-mtd_iab_leche.pdf) · [EUR-Lex CELEX 32019D2031](https://eur-lex.europa.eu/legal-content/ES/ALL/?uri=CELEX:32019D2031)
- [Decisión de Ejecución (UE) 2023/2749](https://www.boe.es/buscar/doc.php?id=DOUE-L-2023-81835) — MTD mataderos, subproductos animales y coproductos comestibles. [Corrección de errores (2024)](https://www.boe.es/buscar/doc.php?id=DOUE-L-2024-80035) · [Ficha del BREF, JRC EU-BRITE](https://bureau-industrial-transformation.jrc.ec.europa.eu/reference/slaughterhouses-and-animals-products-industries)
- [Reglamento (CE) 1069/2009](https://eur-lex.europa.eu/legal-content/ES/TXT/?uri=CELEX:32009R1069) y [Reglamento (UE) 142/2011](https://eur-lex.europa.eu/legal-content/ES/TXT/?uri=CELEX:32011R0142) — SANDACH · [Guía interpretativa AESAN](https://www.aesan.gob.es/AECOSAN/docs/documentos/seguridad_alimentaria/gestion_riesgos/guia_sandach.pdf)

**Normativa española** — en [`../normativa/marco_normativo_ES_UE.md`](../normativa/marco_normativo_ES_UE.md): Decreto 185/2025 de Canarias (BOC 250, 18/12/2025), Ley 34/2007, Ley 21/2013, RDL 1/2016.

**Criterios y guías técnicas**
- [IAQM, *Guidance on the assessment of odour for planning* (2014)](https://www.iaqm.co.uk/text/guidance/odour-guidance-2014.pdf) — Tabla 5 (criterios H4 por ofensividad, con entradas alimentarias explícitas), Tablas 6 y 7 (descriptores de efecto por sensibilidad del receptor), rango 1–10 ou_E/m³.
- [InfoMil/VROM, *Handleiding geur: bepalen van het aanvaardbaar hinderniveau van industrie en bedrijven (niet veehouderijen)*, 28/06/2012](https://olores.mma.gob.cl/wp-content/uploads/2019/03/Handleiding-geur.pdf) — valores de contraste 0,5–5 ou_E/m³ P98; regla de las 3.500 h/año y percentiles superiores; fluctuaciones intrahorarias y NTA 9065; listado de las 15 *bijzondere regelingen*; casos de piensos (§ 10.4) y cervecería (§ 10.5.1).
- [EPA Ireland, *Odour Emissions Guidance Note AG9* (2019)](https://www.epa.ie/publications/compliance--enforcement/air/air-guidance-notes/AG9_Odour-Emissions-Guidance-Note_Sep2019_v1.pdf) — guía nacional irlandesa, no explotada en detalle en esta ficha.
- [UK Environment Agency, *H4 Odour Management* (retirada, sustituida por guía en línea)](https://www.gov.uk/government/publications/environmental-permitting-h4-odour-management) — ⚠️ el documento H4 original ha sido **retirado**; sus criterios sobreviven citados en la guía IAQM, que es la referencia que debe usarse.

**Factores de emisión y metodología**
- Capelli, Sironi et al., *Odour emission factors for assessment and prediction of Italian rendering plants odour impact*, **Chemical Engineering Journal 131 (2007) 225–231** — [ScienceDirect](https://www.sciencedirect.com/science/article/abs/pii/S1385894706005067). Factores de rendering (A.2.2). ⚠️ Acceso de pago; valores obtenidos por vía secundaria.
- Capelli, Sironi, Del Rosso, *Odour Emission Factors: Fundamental Tools for Air Quality Management*, **Chemical Engineering Transactions vol. 40 (2014)** — [AIDIC, PDF abierto](https://www.aidic.it/cet/14/40/033.pdf). Definición y uso del OEF, fórmula `OER = OEF × A × (1 − ORE)`.
- [Informatiepunt Leefomgeving — *Geur van slachterijen*](https://iplo.nl/thema/geur/geur-slachterijen/) — inventario de focos de olor de matadero (sangre, residuos de sacrificio, aguas de limpieza, estiércol, purín); ⚠️ sin factores numéricos, y advierte de que tras la *Omgevingswet* el nivel aceptable lo fija el municipio.
- [Informatiepunt Leefomgeving — *Geuremissie en belasting van de mengvoederindustrie*](https://iplo.nl/thema/geur/mengvoederindustrie-geur/geuremissie-belasting-mengvoederindustrie/) — industria de piensos.

**Documentos hermanos de esta serie** — [`../normativa/marco_normativo_ES_UE.md`](../normativa/marco_normativo_ES_UE.md), [`../normativa/criterios_olor_internacional.md`](../normativa/criterios_olor_internacional.md), [`../metodologia/olores_metodologia.md`](../metodologia/olores_metodologia.md), [`granjas.md`](granjas.md), [`edar.md`](edar.md), [`compostaje.md`](compostaje.md), [`vertederos.md`](vertederos.md).

---

## F. INCERTIDUMBRES Y AVISOS

### F.1 Lo que NO se ha podido verificar

1. **Factores de emisión de olor para la mayor parte del sector.** No se han encontrado, con fuente citable, OEF en ou_E/s o ou_E/(s·m²) para **secaderos de jamón y embutido, almazaras, orujeras, bodegas y alcoholeras, industria láctea, conserveras vegetales, panaderías ni tostaderos de café**. **No se han inventado.** Para estos subsectores la única vía defendible hoy es la **medida en chimenea por olfatometría UNE-EN 13725**, o la transferencia explícita y justificada desde una instalación análoga medida.
2. **Los tres valores de rendering (A.2.2)** proceden de la referencia primaria correcta pero se han obtenido por vía secundaria. Pendiente de verificar sobre el artículo original: base del índice de actividad (materia prima o producto acabado) y si el factor es anterior o posterior a depuración.
3. **La numeración MTD 8 / 18 / 25 de la Decisión 2023/2749** procede de dos consultas concordantes a EUR-Lex, pero sin reproducción íntegra del articulado. Confírmese contra el texto consolidado y su corrección de errores de 2024. El **ámbito** de esa decisión (6.4.a > 50 t/día de canales; 6.5 > 10 t/día) sí se considera verificado.
4. **Eficacias de biofiltros y lavadores para olor en industria alimentaria.** No se ha localizado fuente primaria que las cuantifique. Las cifras del 90–99 % que circulan **no se han verificado** y no se citan aquí como dato.
5. **Los valores de contraste neerlandeses por rama alimentaria concreta** (cuánto para una cervecería, cuánto para una panadería) no se han podido extraer uno a uno: sólo consta el **rango global 0,5–5 ou_E/m³** y el extremo superior atribuido a panaderías. Las *bijzondere regelingen* individuales están además **derogadas** desde 2024 (ver [`../normativa/criterios_olor_internacional.md`](../normativa/criterios_olor_internacional.md)); su valor hoy es de **referencia técnica histórica**, no normativo.
6. **Analogías del decreto canario para subsectores no listados** (secaderos de jamón, bodegas, almazaras, conserveras de pescado). Son propuestas razonadas de esta ficha, **no clasificaciones oficiales**. Los arts. 6.3 y 6.4 dejan la decisión al órgano competente.

### F.2 Dónde discrepan las fuentes

- **Umbral aplicable a la misma actividad.** Un matadero es **3 ou_E/m³** en Canarias (Cat. 1) y **1,5 ou_E/m³** en el criterio británico si se acepta que hay «restos animales en descomposición». Una panadería es **9** en Canarias, **6** en Reino Unido y **5** en los Países Bajos. Los tres marcos coinciden en el **orden** de los subsectores pero difieren hasta en un factor 2 en el **valor**. En un informe hay que elegir uno, decir cuál, y justificar por qué.
- **Estadístico para fuentes discontinuas.** La *Handleiding geur* dice explícitamente que con emisión **< 3.500 h/año** el P98 es inadecuado y hay que ir a percentiles superiores. El decreto canario y el criterio británico **no contemplan esa excepción**: fijan P98 anual sin más. Para una almazara o una conservera de campaña, ambos criterios pueden dar «cumple» mientras la molestia real en campaña es intensa. **Es una laguna real de los marcos vigentes**, no un error de esta ficha, y debe hacerse constar en el informe.

### F.3 Jerarquía de incertidumbres — dónde está de verdad el error

En orden decreciente de contribución al error del resultado final, para esta industria:

1. **El caudal de olor Q** (medido por el equipo como la mayor fuente de error). En alimentaria se agrava porque la mayoría de los subsectores **no tiene factor de emisión publicado**, y porque los que lo tienen están **por tonelada**, exigiendo una hipótesis de producción horaria.
2. **La altura de emisión de los focos difusos** (×12 entre 1 y 6 m). Todos los focos ofensivos del sector están en ese rango.
3. **El reparto entre focos**: qué fracción va por chimenea de proceso y qué fracción sale difusa por puertas, muelles y patio.
4. **El régimen temporal**: campaña, lotes, paradas y picos intrahorarios.
5. La meteorología y la topografía.
6. Los parámetros de chimenea (temperatura, velocidad) — importantes, pero secundarios frente a los anteriores.

> **Consecuencia operativa.** Antes de refinar la malla de receptores o discutir la elección de umbral, hay que cerrar (1) y (2). Un estudio con un caudal de olor no medido y una altura estimada a ojo **no mejora** porque se afine cualquier otra cosa.

### F.4 La limitación que hoy bloquea el uso normativo — repetida aquí a propósito

Los **tres** marcos numéricos aplicables a esta industria —Decreto 185/2025 de Canarias, criterio británico H4/IAQM y valores de contraste neerlandeses— se expresan sobre el **percentil 98 de medias horarias**. La herramienta exporta hoy **sólo la media del periodo**, sin serie horaria ni enésimo valor más alto.

**Mientras eso no cambie, ningún informe producido con esta herramienta puede acreditar el cumplimiento de un umbral de olor.** Puede comparar escenarios, jerarquizar focos y dimensionar medidas correctoras —que es mucho, y es lo que más falta hace en la fase de diseño—, pero no puede concluir «cumple». Esta limitación debe aparecer en el apartado 8 del informe (ver B), redactada sin ambigüedad, y es la primera prioridad de desarrollo de la herramienta.
