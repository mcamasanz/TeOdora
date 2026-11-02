---
tipo: olores-vertedero
fuente: mixta
contaminantes: [ou_E, H2S, NH3, CH4, COV]
estadistico: percentil-98
umbral: "1,5 ou_E/m³ P98 horario (EA/EPA-IE: los vertederos son categoría «más ofensiva»); 3 ou_E/m³ P98 en Canarias (D. 185/2025, Categoría 1); 300 ou_E/m³ en foco (Abruzzo/Cerdeña)"
ambito: España + UE
anio: 2026
origen: vigilancia tecnológica
---

# Vertederos — estudio de olores y emisiones difusas

> El vertedero es el caso extremo de fuente difusa: una superficie de hectáreas cuya emisión varía en
> **dos órdenes de magnitud** entre el frente de descarga activo y una celda sellada, y que además
> **se enciende y se apaga con la presión atmosférica** en ciclos de horas. La decisión que más
> condiciona el resultado no es el caudal medio sino **qué se modeliza como fuente separada**: un único
> polígono envolviendo todo el vaso reparte la emisión del frente activo sobre superficie sellada y
> destruye el resultado. Este documento aporta factores de emisión verificados por tipo de superficie,
> los modelos de generación de biogás (LandGEM / IPCC) y su relación —problemática— con el caudal de olor.

**Documentos hermanos (no se repite su contenido aquí):**
- [Marco normativo España + UE](../normativa/marco_normativo_ES_UE.md) — Decreto 185/2025 de Canarias
  (3/6/9 ou_E/m³ al P98 de medias horarias anuales), vacío estatal, UNE-EN 13725:2022.
- [Criterios de olor internacionales](../normativa/criterios_olor_internacional.md) — Países Bajos e
  Italia; **Abruzzo y Cerdeña: 300 ou_E/m³ en foco** para plantas de residuos.
- [Metodología de olores](../metodologia/olores_metodologia.md) — pico-media, percentiles, olfatometría,
  umbrales por compuesto.
- [Compostaje y tratamiento de residuos orgánicos](compostaje.md) — comparte con este documento el
  problema de la fuente de área pasiva, la balsa de lixiviados y el biofiltro.

---

## A. CÓMO MODELAR → para el agente 1

### A.0 · La bifurcación previa: con o sin captación de biogás

Igual que en compostaje la pregunta previa era «abierto o cerrado», aquí es **si el vaso tiene red de
desgasificación activa**. No es un matiz: cambia qué focos existen y de qué orden es la emisión difusa.

| | **Vertedero SIN captación** (o con captación pasiva) | **Vertedero CON captación activa** |
|---|---|---|
| Foco dominante | La **superficie del vaso** — todo el biogás generado sale por la cobertura | El **frente de descarga activo** (no está bajo aspiración) y las **fugas de la red** |
| Focos puntuales | Ninguno, o chimeneas pasivas | **Antorcha** y/o **motogeneradores** — focos puntuales calientes y con empuje real |
| Emisión difusa | Alta y repartida por todo el vaso | Reducida, pero **no nula**: la captación nunca es total |
| Palanca de reducción | Instalar la red; sellar | Aumentar la depresión, sellar, reducir el frente activo |
| Trampa de modelización | Olvidar que la emisión no es uniforme por m² | **Suponer que la captación elimina el problema**: el frente activo abierto sigue emitiendo |

> **Consecuencia contraintuitiva y muy útil en un informe:** en un vertedero bien desgasificado, los
> focos puntuales (antorcha, motogeneradores) suelen ser **irrelevantes para el olor** —queman el
> biogás y salen altos y calientes, con sobreelevación real— mientras que **el frente de descarga
> abierto, a ras de suelo y sin empuje, domina el resultado**. El foco que se ve desde lejos no es el
> que huele.

### A.1 · Focos típicos y cómo representarlos

| Foco | Tipo de fuente AERMOD | Altura típica de emisión | Notas de modelización |
|---|---|---|---|
| **Frente de descarga activo** (*working face*) | `AREA` o `AREAPOLY` **propia y separada** | 0 m sobre la superficie de trabajo (ver A.4) | **El foco que más huele**, con diferencia (A.3.1). Superficie pequeña (típicamente cientos a pocos miles de m²) y tasa específica muy alta. **Emisión discontinua**: sólo en horario de admisión → `EMISFACT HROFDY`. Su posición **se desplaza a lo largo del año**: es un foco móvil, no fijo |
| **Celda con cobertura diaria** (tierra o material alternativo) | `AREA` / `AREAPOLY` | 0 m | Un orden de magnitud por debajo del frente activo (A.3.1) |
| **Cobertura temporal / intermedia** | `AREA` / `AREAPOLY` | 0 m | Escalón intermedio. Con lámina sintética, ~1/10–1/20 del frente activo (A.3.1) |
| **Celdas selladas y taludes** (cobertura final) | `AREA` / `AREAPOLY` troceada por cotas | 0 m sobre la cota del talud (ver A.2) | Emisión difusa residual. Es la superficie mayor y la de menor tasa: **el producto tasa × superficie puede seguir siendo dominante**. No despreciar por defecto |
| **Balsa de lixiviados** | `AREA` / `AREAPOLY` sobre la lámina de agua | 0 m | En compostaje, la percolación de lixiviados sin tratar da **500 ou_E/(s·m²)**, el factor más alto de toda la serie ([compostaje §A.2.2](compostaje.md)). En vertedero es el mismo tipo de foco. **Comprobar siempre antes de asumir que manda el vaso** |
| **Planta de tratamiento de lixiviados** (evaporación, ósmosis, biológico) | `AREA` para balsas y decantadores abiertos; `POINT` si hay extracción a biofiltro | 0 m (láminas) / altura de chimenea | Se modeliza igual que una EDAR pequeña → ver [edar.md](edar.md) |
| **Antorcha de biogás** | `POINT` | Altura del quemador | Foco **caliente y con empuje**. Ver A.4.3 para el tratamiento de la temperatura y la velocidad de salida. En antorcha cerrada la combustión destruye los odorantes: su contribución al olor suele ser menor que la del frente activo |
| **Motogenerador (chimenea)** | `POINT` | Altura de chimenea | Gases de combustión: relevante para NOx/CO y para el balance energético; **poco relevante para olor** si la combustión es correcta. Sí importa si hay **paradas y venteo directo** |
| **Pozos y red de desgasificación** | `VOLUME` por pozo, o `AREA` de baja intensidad englobando la red | Altura de la boca del pozo | Las fugas de juntas y purgadores son un foco real y sistemáticamente olvidado en los inventarios |
| **Estación de transferencia / báscula / lavado de ruedas** | `AREA` pequeña o `VOLUME` | 0–3 m | Menor, pero está en el límite de parcela, que es donde se evalúa |

**Distinción operativa que hay que declarar en el informe:** el frente activo, la cobertura diaria y la
cobertura intermedia **no son la misma fuente con distinto factor: son fuentes distintas** con distinto
régimen horario y distinta posición. Modelizarlas como una sola es el error nº 1 del apartado A.5.

### A.2 · El problema de la geometría: superficies enormes y AREAPOLY

#### A.2.1 · Por qué NO vale un solo punto (ni un solo polígono) en el centro

Un vaso de vertedero puede medir **cientos de metros de lado y decenas de hectáreas**. Tres razones
independientes, cualquiera de ellas suficiente, para no representarlo con una fuente única:

1. **El máximo cae pegado a la fuente.** En una fuente de área pasiva —sin empuje ni momento— el
   penacho no se eleva: el máximo de concentración se produce **en el borde de la propia fuente**, que
   normalmente coincide con el límite de parcela y con el receptor. Una fuente puntual en el centro
   genera el máximo *a cierta distancia* y valores bajos junto al foco: **es exactamente la geometría
   contraria a la real** y subestima justo donde se evalúa el cumplimiento.
2. **La emisión no es uniforme.** Entre el frente activo y la cobertura intermedia hay más de un orden
   de magnitud (A.3.1). Un polígono único con la tasa media reparte la emisión del frente sobre las
   hectáreas selladas: **rebaja el máximo local y sube artificialmente el fondo**. El campo resultante
   no se parece al real en ningún punto.
3. **El relieve.** Un vaso tiene taludes de decenas de metros. La cota de emisión de la coronación y la
   del pie del talud pueden diferir 20–40 m. Con una única fuente plana se pierde por completo la
   posición vertical de la emisión, que es el parámetro más sensible del modelo (A.4.1).

#### A.2.2 · Cómo trocear

**Criterio de troceado, por orden de prioridad:**

1. **Por estado de la superficie** — frente activo / cobertura diaria / intermedia / sellado final.
   Es el criterio que más varianza explica.
2. **Por cota** — una fuente por banco o por franja de cota del talud, para que la altura de la fuente
   siga el relieve. AERMOD sitúa cada fuente de área a su propia elevación de base.
3. **Por régimen horario** — separar lo que sólo emite en horario de admisión de lo que emite 24 h.
4. **Por resolución del receptor** — como el máximo cae pegado a la fuente, el troceado debe ser al
   menos tan fino como la separación de receptores en el límite de parcela.

**Nota importante sobre el límite de 20 vértices de `AREAPOLY`** ⚠️
Ese límite es un **límite de la implementación**, no de la física del problema. En el código histórico
de AERMOD existía un array fijo de 20 vértices para fuentes `AREAPOLY`; **las versiones modernas lo
sustituyeron por asignación dinámica de memoria**, permitiendo un número «ilimitado» de vértices.
Fuente: [Addendum al User's Guide de AERMOD (EPA)](https://downloads.regulations.gov/EPA-HQ-OAR-2015-0310-0016/content.pdf).
La misma documentación **advierte contra polígonos excesivamente complejos**, porque provocan errores
de ejecución y disparan el tiempo de cálculo.

Traducción práctica para esta herramienta, que sí impone 20 vértices:

- **No es una limitación grave.** El troceado que exige la física (A.2.2) produce de todos modos
  polígonos simples: bandas de talud, rectángulos de celda, el contorno de una balsa. Rara vez hace
  falta más de 20 vértices para uno solo de ellos.
- **Si un contorno real necesita más, se parte en dos polígonos adyacentes.** Dos `AREAPOLY` que
  comparten un lado son equivalentes a uno con el doble de vértices, y además permiten asignarles
  tasas o cotas distintas: casi siempre es una mejora, no un apaño.
- **Simplificar el contorno es preferible a forzar vértices.** Un vértice de más en un talud no cambia
  nada; una tasa mal repartida sí. El presupuesto de complejidad hay que gastarlo en A.2.2.1 y A.2.2.2,
  no en dibujar el perímetro con precisión topográfica.
- ⚠️ **Rectángulos frente a polígonos.** Para una celda o un frente de descarga rectangular, la fuente
  `AREA` (longitud, anchura, ángulo de rotación) es más simple, más rápida y menos propensa a error que
  `AREAPOLY`. Reservar `AREAPOLY` para contornos genuinamente irregulares: balsas, taludes curvos, el
  perímetro del vaso.

**Precedente publicado de área única** ⚠️: en un estudio con ISC-AERMOD View sobre una instalación
integrada de residuos, el vaso se modelizó como **una sola fuente de área de 212 × 184 m (39 008 m²)
con altura de emisión de 5 m**, y el metano por separado como fuente puntual
([Springer / PMC6582209](https://pmc.ncbi.nlm.nih.gov/articles/PMC6582209/)). Se cita como precedente
de práctica real, **no como recomendación**: es exactamente el enfoque de fuente única que A.2.1
desaconseja, y su flujo de olor declarado (7,95·10⁻⁵ ou/m²·s) está **cinco órdenes de magnitud por
debajo** de todos los demás valores publicados (A.3.1). Ver aviso en F.1.

### A.3 · Datos de emisión

#### A.3.1 · Factores de emisión de olor superficial ✅ VERIFICADOS

Ésta es la tabla central del documento. **Nótese la dispersión**: cuatro órdenes de magnitud entre el
frente activo y una superficie agotada.

| Superficie / situación | Factor | Unidades | Fuente |
|---|---|---|---|
| **Deposición de residuos (frente activo)** | **≈ 60** | ou/(m²·s) | [Waste Management — método del equipo de olfateo](https://www.sciencedirect.com/science/article/abs/pii/S0956053X05002825) |
| **Zona de trabajo del vertedero, en verano** | **46,5 – 136** | ou/(m²·s) | [PubMed 24812941](https://pubmed.ncbi.nlm.nih.gov/24812941/) |
| **Residuo descubierto donde ha cesado la deposición** | **1 – 25** | ou/(m²·s) | [Waste Management, ídem](https://www.sciencedirect.com/science/article/abs/pii/S0956053X05002825) |
| **Media de 7 vertederos italianos de RSU (OEF global)** | **5,5 ± 3,4** | ou_E/(s·m²) | [Sironi et al. (2005), *Atmospheric Environment* 39(29):5387-5394](https://www.sciencedirect.com/science/article/abs/pii/S1352231005004693) |
| **Vertedero completo, por modelización inversa (CALPUFF)** | **35,6** | ou/(m²·s) | Citado en la bibliografía de OEF (ver E) |
| **Superficie de vertedero agotada / sellada** | **0,011** | ou_E/(m²·s) | [Lucernoni et al. (2016), *Atmospheric Environment*](https://www.sciencedirect.com/science/article/abs/pii/S1352231016306574) |

**Cómo leer esta tabla —y esto va en el informe, no sólo en las notas:**

- El rango **46,5–136 ou/(m²·s) para el frente activo** y el **≈ 60 ou/(m²·s)** de la deposición son
  consistentes entre sí y proceden de métodos independientes. Es el intervalo defendible para el
  frente de descarga.
- El **5,5 ± 3,4 ou_E/(s·m²)** de Sironi es un **OEF promediado sobre todo el vaso**, no el factor del
  frente activo. Aplicarlo al frente activo lo subestima ~10 veces; aplicarlo al vaso completo es su
  uso correcto **sólo si el vaso tiene un reparto de superficies similar al de los vertederos
  italianos muestreados**, cosa que hay que comprobar y declarar.
- El **0,011 ou_E/(m²·s)** de Lucernoni es para superficie **agotada**, y los propios autores lo
  presentan como «considerablemente inferior a los valores publicados previamente». **No es el factor
  de una cobertura intermedia**, ni de un sellado reciente sobre residuo joven.
- ⚠️ **Estos valores no son intercambiables entre sí.** Cada uno procede de una técnica de muestreo
  distinta (campana de flujo, túnel de viento, olfateo de campo, modelización inversa) y **la técnica
  de muestreo cambia el resultado**. La modelización inversa, en particular, arrastra los errores del
  modelo de dispersión usado para invertir.

#### A.3.2 · Emisión relativa por tipo de cobertura ✅ VERIFICADO

Estudio de un vertedero sanitario de RSU a lo largo de sus fases de operación
([*Science of the Total Environment*, 2022](https://www.sciencedirect.com/science/article/abs/pii/S0048969722062106)):

| Superficie | SOER | Ratio frente al frente activo |
|---|---|---|
| **Frente de trabajo** | **138,34** µg/(m²·s) | **1** (referencia) |
| Cobertura temporal | 22,43 µg/(m²·s) | ≈ 1/6 |
| Cobertura diaria | 17,95 µg/(m²·s) | ≈ 1/8 |
| Cobertura intermedia | 6,24 µg/(m²·s) | ≈ 1/22 |
| **Zonas con cobertura de lámina (membrana)** | — | **≈ 1/10 a 1/20** del frente activo |

⚠️ **Aviso de unidades crítico:** estos valores están en **µg/(m²·s), es decir, en MASA, no en ou_E**.
No se pueden meter en AERMOD como caudal de olor. **Su valor es la razón entre filas, no el número
absoluto.** Se usan así: se toma un factor de olor verificado para el frente activo (A.3.1, en
ou_E/m²·s) y se aplican estos ratios para derivar los de las demás superficies, **declarando
explícitamente que se ha hecho esa transposición**. Es una hipótesis —supone que la composición
odorante no cambia entre superficies— pero es defendible y muy superior a inventarse los factores.

#### A.3.3 · Modelos de generación de biogás: LandGEM y el enfoque IPCC

Son la otra vía para estimar la emisión: en vez de medir el olor en superficie, **se calcula cuánto
biogás genera la masa de residuo enterrada** y se reparte por la superficie. Conviene entender qué dan
y —sobre todo— qué **no** dan.

**Qué son.** Ambos son **modelos de decaimiento de primer orden (FOD)**. Parten de la misma idea
física: la materia orgánica enterrada se degrada anaeróbicamente, la generación de metano alcanza su
máximo poco después del vertido (tras un desfase en que se establecen condiciones anaerobias) y luego
**decae exponencialmente** conforme se agota el sustrato.

**LandGEM (US EPA)** — el modelo estándar de la industria, asociado a AP-42 sección 2.4.
Ecuación en su forma clásica: **Q = L₀ · k · M · e^(−k·t)**

| Parámetro | Qué es | Valores por defecto EPA |
|---|---|---|
| **L₀** | Capacidad potencial de generación de metano: metano total que puede dar una tonelada de residuo al degradarse | **100 m³/Mg** (3 530 ft³/ton) — apropiado para la mayoría de vertederos |
| **k** | Constante de velocidad de generación: a qué ritmo decae el residuo. Función de humedad, nutrientes, pH y temperatura | **0,04 /año** en zonas con ≥ 25 in (≈ 635 mm) de lluvia/año; **0,02 /año** en zonas más secas |
| **M** | Masa de residuo admitida cada año | Dato de la instalación |
| **t** | Tiempo desde la admisión | — |

Fuentes: [EPA — LandGEM v3.1](https://cfpub.epa.gov/si/si_public_record_report.cfm?dirEntryId=365160&Lab=CESER) ·
[EPA — Landfill Gas Modeling, cap. 2](https://www.epa.gov/system/files/documents/2021-07/pdh_chapter2.pdf)

⚠️ **Cambio normativo reciente que hay que conocer:** la revisión de **AP-42 sección 2.4** se finalizó
en **agosto de 2024** y en **mayo de 2025** la EPA publicó una actualización significativa de la sección
y del propio LandGEM. Lo relevante: **se sustituyó la ecuación cinética de primer orden anterior por la
ecuación HH-1 del *Subpart HH*** del programa de notificación de GEI, y se aclaró que **los NMOC son un
buen sustituto de los COV** (diferencia < 50 ppmv), eliminando la anterior referencia a una relación
COV/NMOC del 39 %.
Fuentes: [ALL4 — resumen de la actualización](https://www.all4inc.com/4-the-record-articles/u-s-epa-releases-significant-update-to-ap-42-section-2-4-for-solid-waste-landfills/) ·
[SCS Engineers](https://www.scsengineers.com/epa-finalizes-ap-42-chapter-2-section-4-msw-landfills/) ·
[AP-42 cap. 2.4 (versión 2024)](https://www.epa.gov/system/files/documents/2024-01/c02s04_1_2024_rlso.pdf)
**Antes de citar valores por defecto de k y L₀ en un informe fechado en 2026, hay que verificar contra
la versión vigente**, porque su papel dentro de la nueva formulación puede haber cambiado.

**Enfoque IPCC (FOD)** — el usado para inventarios nacionales de GEI.
Misma familia de modelo, distinta parametrización: trabaja con el **carbono orgánico degradable (DOC)**
del residuo, que se supone decae lentamente a lo largo de décadas generando CH₄ y CO₂. Su parámetro de
velocidad se expresa a través de la **semivida**:

> **k = ln(2) / t½**, donde t½ es el tiempo medio de degradación del 50 % del DOC.

- Rango de k en las Directrices IPCC: **0,005 a 0,4** — un rango muy amplio, que hay que cerrar con
  criterio de clima y de composición del residuo.
- Requiere **datos históricos de 3 a 5 semividas** para dar un resultado aceptablemente exacto: no basta
  con los últimos años de admisión.

Fuentes: [IPCC 2006, Vol. 5, Cap. 3 — Solid Waste Disposal](https://www.ipcc-nggip.iges.or.jp/public/2006gl/pdf/5_Volume5/V5_3_Ch3_SWDS.pdf) ·
[IPCC — Chapter 5 Waste](https://www.ipcc.ch/site/assets/uploads/2018/03/5_Waste-1.pdf)

**Qué dan y qué no dan — la parte que importa aquí.**

| Dan | No dan |
|---|---|
| **m³/año de CH₄** (y por tanto de biogás) **generado** por la masa enterrada | **ou_E/s.** Ningún modelo FOD produce unidades de olor |
| La **curva temporal**: cuándo un vertedero cerrado deja de ser un problema | La **distribución espacial** sobre la superficie |
| El insumo para dimensionar antorcha y motogeneradores | La fracción que **escapa** frente a la que se capta |

**Cadena completa para llegar de LandGEM a AERMOD** (y dónde se rompe):

```
LandGEM/IPCC → CH₄ generado (m³/año)
   ↓ × (1 − eficiencia de captación)        ← A.3.4
   ↓ × (1 − factor de oxidación)            ← A.3.4
biogás emitido a superficie (m³/año)
   ↓ ÷ superficie emisora (m²) ÷ 31,54·10⁶ s/año
flujo volumétrico específico (m³/m²·s)
   ↓ × concentración de olor del biogás bruto (ou_E/m³)   ← ❌ ESLABÓN NO VERIFICADO
tasa de emisión de olor (ou_E/m²·s)  → AERMOD
```

⚠️ **El último eslabón es el que rompe la cadena.** No se ha localizado en esta revisión un valor
verificado y citable de **concentración de olor del biogás bruto de vertedero en ou_E/m³**. Sin ese
número, LandGEM **no puede alimentar directamente un modelo de olor**. Ver F.1.

**Conclusión operativa:** para el **olor**, la vía correcta es el **factor de emisión superficial**
(A.3.1–A.3.2), preferiblemente medido por olfatometría UNE-EN 13725:2022 sobre el propio vaso.
LandGEM/IPCC sirven para (a) **dimensionar la captación y la antorcha**, (b) **justificar la
evolución temporal** de la emisión —un vertedero cerrado hace 20 años emite mucho menos que uno en
explotación, y el modelo lo cuantifica—, y (c) **el balance de GEI** exigido por la normativa. Usarlos
como fuente del caudal de olor exige una hipótesis explícita que hoy no está respaldada.

#### A.3.4 · Eficiencia de captación y oxidación en cobertura ✅ VERIFICADO

Son los dos factores que convierten «biogás generado» en «biogás emitido». Ambos tienen enorme
dispersión y ambos deben declararse como hipótesis.

| Parámetro | Valor | Fuente / condición |
|---|---|---|
| **Eficiencia de captación — defecto IPCC sin medidas** | **20 %** | Valor por defecto muy conservador de las directrices IPCC cuando no hay medidas |
| **Eficiencia de captación — defecto EPA** | **95 %** | Valor medio adoptado por EPA para vertederos con **cobertura final de suelo y/o geomembrana** *y* **sistema activo de extracción** |
| **Oxidación de metano en cobertura (metanótrofos)** | **10 – 40 %** del flujo de CH₄ antes de alcanzar la atmósfera | Rango medido |
| **Crédito de oxidación en modelos US** | **0 – 35 %** según tipo de suelo | Coeficiente simple |

Fuentes: [SCS Engineers — *LFG Collection Efficiency: Debunking the Rhetoric*](https://www.scsengineers.com/wp-content/uploads/2015/03/Sullivan_LFG_Collection_Efficiency-Debunking_the_Rhetoric.pdf) ·
[Taylor & Francis — *Efficiency of landfill gas collection for methane emission reduction*](https://www.tandfonline.com/doi/full/10.1080/20430779.2012.730798) ·
[EPA — Inventory of U.S. GHG Emissions and Sinks, cap. 7 Waste](https://www.epa.gov/system/files/documents/2023-04/US-GHG-Inventory-2023-Chapter-7-Waste.pdf)

⚠️ **La horquilla 20 % – 95 % es de un factor 16 en la emisión difusa.** No es un parámetro que pueda
elegirse «razonablemente»: hay que justificarlo con el estado real de la cobertura y de la red, y
llevarlo al análisis de sensibilidad. Un vertedero en explotación, con frente abierto y cobertura
provisional, **no está en el 95 %** por mucho que tenga red activa.

### A.4 · Parámetros de modelización y errores típicos

#### A.4.1 · La altura de emisión de una superficie de vertedero

**El equipo tiene medido que, para una fuente de área, pasar de 1 m a 6 m de altura de emisión
multiplica el máximo por 12.** En un vertedero esta decisión es aún más delicada que en compostaje,
porque **existe una tentación específica y errónea: usar la altura del montículo como altura de
emisión**.

**Por qué es tan sensible.** En una fuente de área pasiva el máximo cae pegado a la fuente, donde el
penacho todavía no ha crecido verticalmente. La concentración va aproximadamente como el inverso del
espesor de la capa en que se ha mezclado la emisión, y ese espesor es del orden de la propia altura de
emisión. Subir el punto de emisión **no aleja el penacho: lo despega del suelo** justo donde se evalúa.

**Lo correcto:**

1. **La altura de emisión es 0 m sobre la cota del terreno emisor**, no la altura del montículo. El
   biogás rezuma por la cobertura; la superficie del talud *es* el terreno. Un vaso de 30 m de altura
   no emite a 30 m: emite a 0 m sobre una cota que está 30 m más arriba.
2. **El relieve entra por la elevación de base de cada fuente**, procesada con **AERMAP**, no por el
   parámetro de altura de emisión. Ésta es la distinción que más veces se hace mal.
3. ⚠️ **Precedente contrario en la bibliografía:** el estudio de PMC6582209 (A.2.2) usó **5 m «en
   representación de la elevación del montículo»** para el área del vaso. **Es precisamente la
   confusión descrita**: mezcla relieve con altura de emisión. Con la sensibilidad ×12 documentada,
   esa elección por sí sola puede cambiar el resultado en un factor de varias unidades.
4. **Tabla de sensibilidad obligatoria** en el informe (0, 1, 2, 3, 6 m). Es barata y blinda el trabajo.

#### A.4.2 · La emisión varía enormemente con la meteorología y la presión atmosférica ✅ VERIFICADO

Éste es **el rasgo que distingue al vertedero de casi cualquier otra fuente de olor**, y hay que
ponerlo en el informe.

| Hecho verificado | Consecuencia |
|---|---|
| **Con presión barométrica en descenso se registran los flujos máximos**; con presión en ascenso el flujo de CH₄ **se suprime hasta casi 0 µmol/(m²·s)** | La emisión superficial **no es constante: se enciende y se apaga** |
| Mecanismo: al subir la presión, el aire atmosférico penetra en el perfil del suelo y desplaza el gas hacia abajo (inhibición); al bajar, el gas del suelo se desplaza hacia arriba (realce) | Es advección forzada por gradiente de presión, no difusión |
| La respuesta del flujo al cambio de presión lleva **un retardo de 0 a 4 horas** | La emisión **no está en fase** con la meteorología horaria que usa AERMOD |
| El flujo **se invierte cada 20 h de media**; el **50 % de las fases de emisión duran ≤ 10 h** | La emisión es fuertemente episódica en escala sub-diaria |
| **Los efectos de presión a corto plazo pesan más que la temperatura y la velocidad del viento** | La presión es la variable de control, no la temperatura |
| No se halló relación clara entre emisión de CH₄ y temperatura ambiente; **grandes variaciones estacionales**, sin variabilidad diurna | No sirve un factor horario tipo día/noche |

Fuentes: [Xu et al. (2014), *Global Biogeochemical Cycles* — *Impact of changes in barometric pressure on landfill methane emission*](https://agupubs.onlinelibrary.wiley.com/doi/full/10.1002/2013GB004571) ·
[*Methane emission dynamics from a Danish landfill*, Waste Management (2021)](https://www.sciencedirect.com/science/article/pii/S0956053X21006310) ·
[*Passive landfill gas emission – Influence of atmospheric pressure*, Waste Management (2005)](https://www.sciencedirect.com/science/article/abs/pii/S0956053X0500067X) ·
[DTU — *Pressure effects on methane emissions from landfills*](https://orbit.dtu.dk/en/publications/pressure-effects-on-methane-emissions-from-landfills/)

⚠️ **La consecuencia incómoda para el modelo.** AERMOD se ejecuta con una **tasa de emisión constante**
(o modulada por `EMISFACT` con factores horarios/estacionales fijos). Pero la emisión real de un
vertedero está **correlacionada con la propia meteorología** que gobierna la dispersión, y con un
desfase de horas. Esto significa que:

- **La media del periodo probablemente se conserva razonablemente** (los ciclos de presión se
  compensan a lo largo del año).
- **Los percentiles altos NO se conservan.** Las fases de emisión máxima coinciden con borrascas —
  presión en descenso—, que son también situaciones de viento y mezcla; y las de emisión nula con
  anticiclón, que es cuando hay calma e inversión. **Hay un anticorrelación parcial que un modelo de
  emisión constante no reproduce**, y cuyo signo neto sobre el P98 no está establecido.
- **Declararlo es obligatorio.** No hay forma limpia de resolverlo con AERMOD estándar; lo honesto es
  documentar el fenómeno, señalar que la tasa constante es una hipótesis, y no presentar el P98 como
  si tuviera la precisión de un cálculo determinista.

#### A.4.3 · Focos puntuales: antorcha y motogenerador

| Parámetro | Antorcha | Motogenerador |
|---|---|---|
| Tipo AERMOD | `POINT` | `POINT` |
| Temperatura de salida | Muy alta (combustión) → **sobreelevación importante** | Alta (gases de escape) |
| Velocidad de salida | Alta | Alta |
| Relevancia para **olor** | **Baja** si la combustión es correcta: los odorantes se destruyen | **Baja** en operación normal |
| Relevancia para **otros contaminantes** | NOx, CO, SO₂ (del H₂S del biogás) | **NOx, CO, COV** — suele ser el foco dominante de la AAI |
| Escenario que sí importa | **Antorcha apagada / parada** → venteo directo de biogás crudo | **Parada del motor** → el biogás va a antorcha o se ventea |

⚠️ **Antorcha abierta vs. cerrada.** En antorcha abierta (llama a la vista) los parámetros de fuente
puntual son difíciles de definir: no hay chimenea con diámetro y velocidad bien definidos. La práctica
habitual es una **chimenea equivalente** (pseudo-stack) con diámetro y temperatura efectivos; **es una
hipótesis fuerte que hay que declarar**. En antorcha cerrada (encapsulada, con tiro), los parámetros
son los de una chimenea normal y el tratamiento es directo.

**El escenario que hay que modelizar y casi nunca se modeliza:** el **venteo por parada**. Es el único
momento en que un foco puntual de un vertedero desgasificado emite biogás **crudo** —con todo su H₂S y
sus mercaptanos— sin combustión. Es un escenario episódico, no un promedio anual, y encaja mal con un
criterio de P98; pero es la explicación de buena parte de los episodios de queja.

#### A.4.4 · Periodo meteorológico

**Un año natural completo, como mínimo.** El criterio del [Decreto 185/2025 de Canarias](../normativa/marco_normativo_ES_UE.md)
es el **P98 de medias horarias a lo largo de un año natural**, y el marco EA/EPA-IE es el P98 horario.
Un P98 sobre menos de 8 760 horas no es el estadístico que exige la norma. Para vertederos hay un motivo
adicional: la variabilidad estacional de la emisión está documentada (A.4.2) y **un periodo parcial la
muestrea sesgada**. Lo deseable son **3–5 años**, reportando el peor año y el conjunto.

### A.5 · Errores típicos que invalidan un estudio de vertedero

| # | Error | Por qué es grave | Qué hacer |
|---|---|---|---|
| 1 | **Un único polígono para todo el vaso** | Reparte la emisión del frente activo sobre hectáreas selladas. Rebaja el máximo local, sube el fondo: el campo no se parece al real en ningún punto | Trocear por estado de superficie, cota y régimen horario (A.2.2) |
| 2 | **Modelizar el vaso como fuente PUNTUAL en el centro** | Genera el máximo a distancia y valores bajos junto al foco. Es la geometría contraria a la real: **subestima justo en el límite de parcela** | `AREA` / `AREAPOLY` siempre. Nunca `POINT` |
| 3 | **Usar la altura del montículo como altura de emisión** | Confunde relieve con altura de emisión. Con sensibilidad ×12 entre 1 y 6 m, distorsiona el resultado en varias unidades | Altura de emisión = 0 m; el relieve entra por **AERMAP** (A.4.1) |
| 4 | **Omitir el frente de descarga activo como fuente separada** | Es **el foco que más huele** (46,5–136 ou/m²·s frente a ~0,01–25 del resto) y el único con horario. Diluirlo en la media del vaso lo hace desaparecer | Fuente propia, con `EMISFACT HROFDY` |
| 5 | **Suponer que la captación de biogás resuelve el olor** | El frente activo **no está bajo aspiración**. Un vertedero con red activa y frente abierto sigue teniendo su foco dominante intacto | A.0. Modelizar el frente aunque haya red |
| 6 | **Aplicar el OEF medio de Sironi (5,5) al frente activo** | Es un OEF **promediado sobre todo el vaso**. Aplicado al frente lo subestima ~10 veces | Usar 46,5–136 ou/m²·s para el frente (A.3.1) |
| 7 | **Meter en AERMOD los valores en µg/(m²·s) de A.3.2** | Son **masa, no ou_E**. Su valor es la razón entre filas, no el número absoluto | Usar los ratios sobre un factor de olor verificado, declarando la transposición |
| 8 | **Derivar ou_E/s de LandGEM sin declarar la hipótesis** | El eslabón «concentración de olor del biogás bruto» **no está verificado**. La cadena se rompe ahí | A.3.3. Usar factores superficiales; LandGEM para dimensionar captación y evolución temporal |
| 9 | **Elegir la eficiencia de captación sin justificarla** | La horquilla 20 % – 95 % es un factor 16 en la emisión difusa | A.3.4. Justificar con el estado real y llevar a sensibilidad |
| 10 | **Olvidar la balsa de lixiviados y la planta de tratamiento** | En compostaje la percolación sin tratar da 500 ou_E/(s·m²), el factor más alto de la serie. En vertedero es el mismo foco y suele quedar fuera del inventario | Incluirla siempre, aunque luego resulte menor |
| 11 | **Tratar el frente activo como foco fijo** | **Se desplaza a lo largo del año** conforme avanza la explotación. Su posición condiciona qué receptor es el crítico | Modelizar la posición del año evaluado y, si el plan de explotación lo permite, la peor posición prevista |
| 12 | **Presentar el resultado como determinista** | La emisión está modulada por la presión atmosférica con ciclos de horas (A.4.2) y no está en fase con la meteorología del modelo | Declarar la hipótesis de tasa constante y sus límites |
| 13 | **Ignorar el escenario de venteo por parada de antorcha** | Es el único momento con biogás crudo sin combustión, y explica buena parte de las quejas | Escenario episódico específico (A.4.3) |

---

## B. ESTRUCTURA DEL INFORME → para el agente 2

Secciones numeradas de un informe real de dispersión de olores de un vertedero.

**1. Objeto, alcance y marco normativo aplicable**
Actividad, titular, procedimiento que motiva el estudio (EIA, AAI, revisión de AAI, ampliación de vaso,
o requerimiento del órgano ambiental por quejas). Clase de vertedero (RNP / RP / inertes). Jurisdicción
y **criterio de olor adoptado y justificado** (ver C).
*Tabla 1: criterio de evaluación adoptado, valor, estadístico y fuente normativa.*

**2. Descripción de la instalación**
Capacidad autorizada y admitida (t/año), tipos de residuo (LER), superficie total del vaso y **desglose
por estado de superficie**, cotas, fases de explotación, vida útil restante. **Debe quedar explícito si
existe red de desgasificación activa y cuál es su alcance** (A.0).
*Figura 1: planta acotada con delimitación de frente activo, cobertura diaria, intermedia y sellado.*
*Figura 2: perfil / secciones del vaso con cotas — justifica el troceado por cota.*
*Tabla 2: superficie (m²) por estado de cobertura y por fase de explotación.*

**3. Inventario de focos emisores**
Exhaustivo: frente activo, coberturas, taludes sellados, balsa de lixiviados, planta de tratamiento de
lixiviados, pozos y red, antorcha, motogeneradores, báscula y accesos. Para cada uno: superficie o
dimensiones, régimen horario, cota de base.
*Tabla 3: inventario con tipo de fuente AERMOD asignado, superficie, régimen y cota.*

**4. Generación de biogás y balance de captación**
LandGEM o FOD IPCC: parámetros k y L₀ adoptados **con su justificación climática y de composición**,
serie histórica de admisiones, curva de generación. Balance: generado / captado / oxidado / emitido.
*Figura 3: curva de generación de CH₄ frente al tiempo, con el año evaluado marcado.*
*Tabla 4: balance de biogás con eficiencia de captación y factor de oxidación adoptados y su fuente.*

**5. Cuantificación de la emisión de olor**
Origen de cada tasa: olfatometría propia (norma, laboratorio, fecha, técnica de muestreo —campana de
flujo o túnel de viento—) o factor bibliográfico con cita. **Distinguir tipográficamente lo medido de
lo estimado.** Si se han usado los ratios de A.3.2, declararlo aquí.
*Tabla 5: tasa por foco en ou_E/s y ou_E/(s·m²), con columna «origen del dato».*
*Tabla 6: escenarios (explotación normal / venteo por parada de antorcha / peor caso).*

**6. Meteorología**
Estación, periodo (año/s completos), tratamiento de datos faltantes, características superficiales
(rugosidad, albedo, razón de Bowen) y su procedencia. Justificar representatividad.
*Figura 4: rosa de vientos anual.* *Figura 5: rosa de vientos de horas nocturnas y estables* — son las
que producen los episodios.
*Tabla 7: distribución de clases de estabilidad.*

**7. Configuración del modelo**
AERMOD (versión), AERMET, AERMAP, BPIPPRM. Dominio, rejilla de receptores y receptores discretos
(viviendas, núcleos, centros sensibles). **Tabla completa de parámetros de fuente**: es el corazón
auditable del informe.
*Tabla 8: parámetros de cada fuente (tipo, coordenadas/vértices, dimensiones, cota de base, altura de
emisión, σz₀, tasa, factor horario).*
*Figura 6: dominio, troceado de fuentes de área y rejilla de receptores sobre ortofoto.*

**8. Análisis de sensibilidad** *(la sección que distingue un informe serio)*
Como mínimo: **altura de emisión** (documentar el ×12), **eficiencia de captación** (20 % vs. 95 %),
tasa del frente activo (rango 46,5–136), troceado geométrico (una fuente vs. troceada) y año meteorológico.
*Tabla 9: resultado en el receptor crítico frente a altura de emisión (0, 1, 2, 3, 6 m).*
*Figura 7: gráfico de tornado con la contribución de cada hipótesis a la incertidumbre.*

**9. Resultados**

> ⚠️ **Limitación real de la herramienta, a declarar en esta sección.** La exportación por receptor
> proporciona únicamente la **media del periodo**. Los **máximos horarios y de 24 h** están disponibles
> en `aermod.out`, pero **no se exporta la serie horaria completa**, de modo que **hoy no es posible
> calcular directamente el P98 de medias horarias** —que es justamente el estadístico que exigen el
> Decreto 185/2025 de Canarias y el marco EA/EPA-IE.
>
> **Cómo estructurar el apartado en consecuencia, sin fingir un P98 que no se tiene:**
>
> | Estadístico | Disponibilidad hoy | Uso en el informe |
> |---|---|---|
> | **Media del periodo** por receptor | ✅ Exportada | Base del mapa de isopletas y de la comparación entre focos y escenarios |
> | **Máximo horario** | ⚠️ En `aermod.out`, no exportado por receptor | Cota superior. Extraer manualmente para el receptor crítico |
> | **Máximo de 24 h** | ⚠️ En `aermod.out` | Íd. |
> | **P98 de medias horarias** | ❌ **No calculable** con la salida actual | **No presentarlo.** Declarar la limitación |
>
> **Tres salidas honestas, por orden de preferencia:**
> 1. **Ampliar la salida** — activar en AERMOD la exportación de la serie horaria (`POSTFILE`) o
>    directamente el cálculo de percentiles, y recalcular. Es la solución correcta y no es costosa.
> 2. **Encuadrar el resultado** — presentar media del periodo y máximo horario como **cota inferior y
>    cota superior** del P98, declarando que el valor exigido queda entre ambas. Sirve para cribado
>    (si el máximo horario ya cumple, se cumple con holgura), **no para acreditar cumplimiento** cuando
>    el criterio queda dentro de la horquilla.
> 3. **Aplicar un factor pico-media documentado** para estimar el P98 desde la media —ver
>    [metodología de olores](../metodologia/olores_metodologia.md)—, **declarándolo como estimación
>    y no como cálculo**. Es la opción más débil y no debe usarse para acreditar cumplimiento.
>
> **Lo que no se puede hacer:** comparar la **media del periodo** con un valor límite definido sobre el
> **P98 horario**. Son estadísticos distintos por uno o dos órdenes de magnitud y la comparación no
> tiene sentido en ninguna dirección.

Contenido del apartado: campo de concentraciones y valores en receptores sensibles, con el estadístico
que efectivamente se tenga y su etiqueta correcta.
*Tabla 10: resultado por receptor con el estadístico declarado, frente al criterio.*
*Figura 8: isopletas sobre ortofoto, con la isopleta del criterio destacada.*
*Figura 9: mapa de contribución por foco* — es lo que permite decidir dónde invertir en medidas.
*Tabla 11: contribución porcentual de cada foco en el receptor crítico.*

**10. Escenarios episódicos**
Venteo por parada de antorcha; frente activo en su posición más desfavorable del plan de explotación.
Discusión de su encaje con un criterio de media horaria.

**11. Medidas correctoras y escenario con medidas**
Ver D. **Volver a correr el modelo con las medidas aplicadas**: una medida sin cuantificar es una
intención, no una medida.
*Tabla 12: medidas, eficacia aplicada, fuente de la eficacia y resultado.*

**12. Programa de vigilancia**
Control de gases conforme al **Anexo III del RD 646/2020**; olfatometría periódica en focos; **registro
de quejas** (exigible en Canarias, art. 32 del D. 185/2025); inspección de la red de desgasificación;
umbrales de acción.

**13. Conclusiones**

**14. Limitaciones e incertidumbres**
Sección obligatoria y honesta: origen de cada Q, hipótesis de altura de emisión, eficiencia de
captación, **modulación de la emisión por presión atmosférica**, troceado geométrico, no aditividad del
olor y **la limitación de estadístico del apartado 9**.

**15. Bibliografía y anexos**
Ficheros de entrada y salida de AERMOD, informes de olfatometría, certificados de laboratorio, serie de
admisiones usada en LandGEM.

---

## C. NORMATIVA APLICABLE

Lo general está en [marco normativo España + UE](../normativa/marco_normativo_ES_UE.md) y
[criterios internacionales](../normativa/criterios_olor_internacional.md). Aquí sólo lo específico de
vertederos.

### C.1 · La norma de la actividad: Directiva 1999/31/CE y su transposición vigente ✅ VERIFICADO

**Directiva 1999/31/CE del Consejo, de 26 de abril de 1999, relativa al vertido de residuos.** Fue la
primera en establecer un marco regulador común en la UE para la eliminación mediante depósito en
vertedero. Modificada por la **Directiva (UE) 2018/850**, dentro del paquete legislativo de economía
circular de 2018.

**Transposición española vigente: Real Decreto 646/2020, de 7 de julio**, por el que se regula la
eliminación de residuos mediante depósito en vertedero ([BOE-A-2020-7438](https://www.boe.es/buscar/doc.php?id=BOE-A-2020-7438)).

⚠️ **Éste es el cambio que hay que tener presente: el RD 646/2020 DEROGÓ el RD 1481/2001.** Muchos
informes, pliegos y AAI antiguas siguen citando el RD 1481/2001 como norma vigente. **No lo es.** El
RD 646/2020 consolidó las modificaciones europeas del paquete de economía circular y adaptó la materia
al marco general de residuos —hoy la **Ley 7/2022, de 8 de abril**, de residuos y suelos contaminados
para una economía circular, que sustituyó a la Ley 22/2011.

Norma posterior relacionada: **Orden TED/789/2023, de 7 de julio**, que establece el método de cálculo
del coste de emisión de gases de efecto invernadero en vertedero
([BOE-A-2023-16400](https://www.boe.es/diario_boe/txt.php?id=BOE-A-2023-16400)). Es relevante aquí
porque **formaliza el uso de factores de mitigación**: las cantidades mitigadas se determinan por
separado para gases captados y difusos, multiplicando el total generado por un factor de mitigación que
refleja la eficacia del tratamiento, y distinguiendo el gas **valorizado**, el **oxidado en antorcha** y
el tratado en **bioventanas**. Es la referencia española más directa para justificar los factores del
apartado A.3.4 en un expediente administrativo.

### C.2 · Control de gases de vertedero

**Obligación de fondo (Directiva 1999/31/CE, Anexo I):** en todos los vertederos que reciban residuos
biodegradables **el gas debe recogerse, tratarse y aprovecharse**; si el gas recogido no puede
aprovecharse para producir energía, **debe quemarse en antorcha**. Ésta es la disposición que convierte
la desgasificación en obligatoria y no en una mejora voluntaria — y, para el estudio de olor, la que
determina si estamos en la columna izquierda o derecha de la tabla A.0.

**Seguimiento y control (RD 646/2020, Anexo III):** el control incluye **aguas superficiales,
subterráneas, lixiviados y gases**. El control debe realizarse por **entidades de inspección
acreditadas conforme a UNE-EN ISO/IEC 17020**.
Fuentes: [AGQ Labs — inspección de vertederos y RD 646/2020](https://agqlabs.es/2025/11/06/inspeccion-de-vertederos-rd-646-2020/) ·
[MITECO — Vertederos](https://www.miteco.gob.es/en/calidad-y-evaluacion-ambiental/temas/prevencion-y-gestion-residuos/flujos/vertederos.html)

⚠️ **Ninguna de estas normas fija valores límite de olor.** El control de gases del Anexo III es de CH₄,
CO₂, O₂ y otros parámetros de seguridad y de GEI, **no de ou_E**. El criterio de olor sale siempre del
escalón autonómico, de la AAI o de un marco de referencia externo (C.4).

### C.3 · Qué exige la AAI

Un vertedero de residuos no peligrosos está sujeto a **autorización ambiental integrada** (Ley 16/2002
de prevención y control integrados de la contaminación, texto refundido RDL 1/2016). Lo que la AAI
suele imponer y que condiciona el estudio de olor:

- **Valores límite de emisión** para los focos canalizados (motogeneradores, antorcha): NOx, CO, SO₂,
  partículas. **Rara vez incluye olor** en foco, salvo que la comunidad autónoma lo haya introducido.
- **Obligación de red de desgasificación** y de aprovechamiento o quema, con exigencias de eficiencia
  de captación y de mantenimiento.
- **Programa de vigilancia ambiental** conforme al Anexo III del RD 646/2020.
- **Condiciones de explotación** que son, de facto, las medidas correctoras de olor: cobertura diaria,
  limitación de la superficie del frente activo, gestión de lixiviados.
- **Cláusula genérica de no causar molestias** por olores a la población, sin valor numérico asociado.
  Es la vía por la que el órgano ambiental puede exigir un estudio de dispersión ante quejas.
- ⚠️ **Cada AAI es distinta.** Antes de elegir criterio hay que **leer la AAI concreta**: puede contener
  un valor de olor, un compromiso del promotor asumido en la DIA, o una remisión a una guía autonómica.

### C.4 · El criterio de olor aplicable — vertederos son «categoría más ofensiva»

**Dato clave y muy favorable para argumentar:** en el criterio por ofensividad de la **EPA de Irlanda
(AG9, 2019)**, adaptado de la guía británica **EA (2011)** —reproducido en
[compostaje §C.3](compostaje.md)—, los **vertederos figuran explícitamente en la categoría «MÁS
OFENSIVA»**, junto a estaciones de transferencia, procesos con restos animales y fangos sépticos.

| Marco | Categoría del vertedero | Criterio |
|---|---|---|
| **EA (RU) / EPA Irlanda (AG9)** | **Más ofensivo** — vertederos citados literalmente | **1,5 ou_E/m³** al P98 de medias horarias en el receptor sensible más desfavorable |
| **Decreto 185/2025 de Canarias** | **Categoría 1** — «gestión de residuos susceptibles de generar olor» | **3 ou_E/m³** al P98 de medias horarias de un año natural |
| **Abruzzo y Cerdeña (Italia)** | Plantas de residuos | **300 ou_E/m³ en foco** — ver [criterios internacionales](../normativa/criterios_olor_internacional.md) |

**Lectura para el informe:** el criterio más exigente y mejor fundamentado para un vertedero es
**1,5 ou_E/m³ al P98 horario**. Es más restrictivo que los 3 ou_E/m³ de la Categoría 1 canaria, y la
razón es explícita: la ofensividad del olor de vertedero —sulfuros reducidos, mercaptanos— es superior
a la del compostaje de residuo verde. **En Canarias rige el Decreto 185/2025 (3 ou_E/m³) por ser norma
vigente**; fuera de Canarias, donde hay vacío normativo, **1,5 ou_E/m³ es la referencia defendible**, y
conviene presentar ambos.

El límite italiano de **300 ou_E/m³ en foco** aplica al foco canalizado (antorcha, biofiltro de la
planta de lixiviados), **no a la emisión difusa del vaso**, que es la dominante. Es útil para dimensionar
el tratamiento de aire de la planta de lixiviados, no para evaluar el vertedero.

---

## D. MEDIDAS CORRECTORAS

Principio rector, común con [compostaje](compostaje.md): **son prioritarias las medidas que actúan sobre
el origen** frente a los tratamientos finalistas. En un vertedero esto se traduce en una jerarquía muy
clara, porque el foco dominante es una superficie: **reducir superficie emisora y sellar** vence a
cualquier tratamiento.

### D.1 · Minimización del frente activo — la medida de mayor relación eficacia/coste

Es la primera medida y la más barata, porque **el frente activo es el foco dominante** (46,5–136
ou/(m²·s) frente a 0,011–25 del resto, A.3.1) y su emisión **escala linealmente con su superficie**.

- **Reducir el área del frente de descarga** al mínimo compatible con la operación: descargar en un
  área compacta en vez de repartir la admisión por una superficie amplia. Es aritmética directa: la
  mitad de superficie, la mitad de emisión de ese foco.
- **Compactar inmediatamente** tras la descarga, con pases suficientes de compactador.
- **Orientar el avance del frente** en función de la dirección predominante del viento hacia los
  receptores. Con un plan de explotación flexible, es una medida de coste cero.
- **Concentrar la admisión** en franjas horarias de buena mezcla atmosférica (media mañana a media
  tarde), evitando la calma nocturna y las inversiones. Trasladar la operación, no reducirla.

### D.2 · Cobertura diaria, intermedia y sellado — eficacias verificadas

| Medida | Reducción frente al frente activo | Fuente | Estado |
|---|---|---|---|
| **Cobertura diaria** | El SOER pasa de 138,34 a **17,95 µg/(m²·s)** → ≈ **1/8** (≈ 87 %) | [STOTEN 2022](https://www.sciencedirect.com/science/article/abs/pii/S0048969722062106) | ✅ Verificado (⚠️ en **masa**, no ou_E) |
| **Cobertura temporal** | 138,34 → **22,43 µg/(m²·s)** → ≈ **1/6** (≈ 84 %) | Ídem | ✅ Verificado (⚠️ masa) |
| **Cobertura intermedia** | 138,34 → **6,24 µg/(m²·s)** → ≈ **1/22** (≈ 95 %) | Ídem | ✅ Verificado (⚠️ masa) |
| **Cobertura con lámina / membrana** | Emisión ≈ **1/10 a 1/20** del frente activo (90–95 %) | Ídem | ✅ Verificado |
| **Sellado final (superficie agotada)** | Factor de **0,011 ou_E/(m²·s)** | [Lucernoni et al. 2016](https://www.sciencedirect.com/science/article/abs/pii/S1352231016306574) | ✅ Verificado — pero es superficie **agotada**, no recién sellada |

⚠️ **Aviso al usar estas eficacias en un informe:** las cuatro primeras filas están medidas **en masa
(µg/m²·s), no en unidades de olor**. Aplicarlas como reducciones de ou_E supone que la composición
odorante no cambia con la cobertura, lo cual es **una hipótesis, no un hecho**: es plausible que la
cobertura retenga selectivamente unos compuestos más que otros. Declararlo.

**Nota contraintuitiva que conviene explicar en el informe:** la cobertura **intermedia** reduce más
(1/22) que la **diaria** (1/8) y que la **temporal** (1/6). Es coherente: la cobertura intermedia es
más espesa, más consolidada y lleva más tiempo colocada, de modo que además de barrera física
**sostiene una población metanótrofa activa** que oxida parte del flujo (10–40 %, A.3.4). La cobertura
diaria, recién extendida y sin consolidar, no tiene esa capacidad.

### D.3 · Captación y quema/valorización del biogás

Es la medida estructural, y además **obligatoria** para todo vertedero que reciba residuos
biodegradables (C.2).

| Aspecto | Dato | Fuente |
|---|---|---|
| Eficiencia con **cobertura final de suelo y/o geomembrana + extracción activa** | **95 %** (valor medio adoptado por EPA) | [EPA GHG Inventory, cap. 7](https://www.epa.gov/system/files/documents/2023-04/US-GHG-Inventory-2023-Chapter-7-Waste.pdf) |
| Defecto IPCC **sin medidas** | **20 %** | Directrices IPCC |
| **Oxidación adicional en cobertura** | **10 – 40 %** del CH₄ restante | Rango medido en metanótrofos de cobertura |

**Lo que hay que entender para no vender humo:** el **95 % es el valor de un vertedero sellado con
geomembrana y red activa**, no el de un vertedero en explotación. La eficiencia real de un vaso con
frente abierto es sustancialmente menor, y **el frente activo está por definición fuera de la
captación**. La captación es imprescindible, pero **no resuelve el foco dominante durante la
explotación**: la que lo resuelve es D.1 + D.2.

**Jerarquía de aprovechamiento**, en línea con la Directiva y el RD 646/2020: valorización energética
(motogeneradores, inyección a red, biometano) > **quema en antorcha** > bioventanas de oxidación. La
antorcha **cerrada** es preferible a la abierta para el control de olor y de emisiones: garantiza
tiempo de residencia y temperatura, y su comportamiento como foco puntual es modelizable con
parámetros bien definidos (A.4.3).

**Mantenimiento de la red** — donde se pierde la eficiencia sobre el papel: purga de condensados,
regulación de la depresión pozo a pozo (una depresión excesiva **introduce aire** e inhibe la
metanogénesis; una insuficiente deja escapar biogás), sellado de bocas y juntas, y prolongación de
pozos conforme sube la cota de vertido.

### D.4 · Cobertura de balsas de lixiviados

La balsa es un foco de **lámina de agua a 0 m de altura de emisión** y, por analogía con compostaje,
potencialmente el factor específico más alto de la instalación (**500 ou_E/(s·m²)** para percolación de
lixiviados sin tratar, [compostaje §A.2.2](compostaje.md)).

- **Cubrición con lámina flotante o cubierta fija**: convierte un foco de área abierto en un foco
  confinado, que puede además canalizarse a tratamiento. Es la medida de mayor efecto por euro cuando
  la balsa resulta dominante en el mapa de contribución (figura 9 del informe).
- **Evitar la aireación superficial abierta** en el tratamiento de lixiviados: es un mecanismo de
  transferencia forzada de odorantes a la atmósfera. Preferir sistemas cerrados o sumergidos.
- **Minimizar la generación de lixiviado** mediante sellado y drenaje de pluviales: menos lixiviado es
  menos balsa y menos planta de tratamiento.
- **Recirculación de lixiviados sobre el vaso** ⚠️: se usa como técnica de biorreactor para acelerar la
  degradación, pero **crea una superficie húmeda y odorante donde se aplica**. Si se practica, hay que
  modelizarla como un foco propio. No es una medida correctora de olor: es un foco.

### D.5 · Biofiltros y tratamiento de aire ✅ VERIFICADO

Aplicables a **corrientes canalizadas**: aire extraído de la planta de tratamiento de lixiviados, de
naves de pretratamiento o de balsas cubiertas. **No son aplicables a la emisión difusa del vaso**, que
es la dominante — decirlo evita una recomendación inútil.

| Parámetro | Valor | Fuente |
|---|---|---|
| Eficacia típica sobre **H₂S** | **≈ 95 %**, para concentración de entrada **≤ 300 ppm** | [RETEMA — biofiltración avanzada](https://www.retema.es/articulos-reportajes/biocassette-de-biofiltracion-avanzada-para-tratar-emisiones-de-sulfuro-de) |
| Reducción de **olor** en fuentes orgánicas | **≈ 90 %** | Fichas técnicas de biofiltración |
| Eficacia en sistemas convencionales | **≈ 70 %** | Ídem |

Los parámetros de diseño detallados (carga volumétrica, superficie, umbral de coste-eficacia, límite de
partículas en la entrada, necesidad de lavador ácido previo cuando el NH₃ es alto) están en
[compostaje §D.4](compostaje.md) y son directamente trasladables. **La advertencia sobre el NH₃ aplica
igual aquí**: el aire extraído de una planta de lixiviados suele ser rico en amoníaco, y un biofiltro
sin lavador ácido previo se acidifica y pierde eficacia.

**Bioventanas (*biowindows*)** — mención específica de vertedero: zonas de la cobertura diseñadas para
maximizar la oxidación metanótrofa del biogás residual. Están reconocidas explícitamente en la
**Orden TED/789/2023** como mecanismo de mitigación junto a la valorización y la antorcha (C.1).
⚠️ No se ha verificado una eficacia de **eliminación de olor** para bioventanas; su función documentada
es la oxidación de metano.

### D.6 · Buenas prácticas de explotación

| Práctica | Efecto sobre el olor |
|---|---|
| **No admitir residuos en descomposición avanzada** sin tratamiento previo | Evita el pico de emisión en el frente |
| **Estanqueidad de la cubierta de los vehículos** de transporte y rutas que eviten zonas residenciales | El transporte es un foco lineal fuera de la instalación, y fuente habitual de quejas |
| **Lavado de ruedas** y limpieza de viales | Evita arrastre de material odorante fuera del recinto |
| **Barreras cortavientos / pantallas perimetrales** | Efecto sobre la dispersión local ⚠️ **no cuantificado en esta revisión**; AERMOD no lo modeliza directamente |
| **Desodorizantes / neutralizantes en cañones de niebla** | ⚠️ Eficacia **no verificada**. Se usan como medida paliativa; no reducen la emisión, actúan sobre la percepción |
| **Registro de quejas georreferenciado** | Es el mejor dato de validación del modelo, y es exigible en Canarias (art. 32 D. 185/2025) |
| **Suspender la descarga con meteorología adversa** (viento hacia receptores, inversión, calma nocturna) | Coste operativo bajo, efecto directo sobre los episodios que generan queja |

---

## E. FUENTES

| # | Fuente | URL | Uso y verificación |
|---|---|---|---|
| 1 | **Sironi et al. (2005)**, *Odour emission factors for assessment and prediction of Italian MSW landfills odour impact*, **Atmospheric Environment 39(29):5387-5394** | <https://www.sciencedirect.com/science/article/abs/pii/S1352231005004693> | ✅ **OEF medio 5,5 ± 3,4 ou_E/(s·m²)** sobre 7 vertederos italianos de RSU. Referencia más citada. ⚠️ Texto completo no accesible (403); el desglose por tipo de superficie no se ha podido extraer |
| 2 | **Lucernoni et al. (2016)**, *Evaluation of an Odour Emission Factor (OEF) to estimate odour emissions from landfill surfaces*, **Atmospheric Environment** | <https://www.sciencedirect.com/science/article/abs/pii/S1352231016306574> | ✅ **OEF de superficie agotada: 0,011 ou_E/(m²·s)**, explícitamente «considerablemente inferior a valores publicados previamente» |
| 3 | *Estimation of odour emission rate from landfill areas using the sniffing team method*, **Waste Management** | <https://www.sciencedirect.com/science/article/abs/pii/S0956053X05002825> | ✅ **Deposición ≈ 60 ou/(m²·s)**; **residuo descubierto sin deposición 1–25 ou/(m²·s)** |
| 4 | *Odor emission rate of municipal solid waste from landfill working area* | <https://pubmed.ncbi.nlm.nih.gov/24812941/> | ✅ **Zona de trabajo en verano: 46,5–136 ou/(m²·s)** |
| 5 | *Odor emission rate of a MSW sanitary landfill during different operation stages before final closure*, **Science of the Total Environment (2022)** | <https://www.sciencedirect.com/science/article/abs/pii/S0048969722062106> | ✅ SOER por cobertura: 138,34 / 22,43 / 17,95 / 6,24 **µg/(m²·s)**; membrana ≈ 1/10–1/20 del frente. ⚠️ **En masa, no ou_E** |
| 6 | *Landfill air and odour emissions from an integrated waste management facility*, **J. Environ. Health Sci. Eng.** | <https://pmc.ncbi.nlm.nih.gov/articles/PMC6582209/> | ✅ Texto extraído. Precedente de modelización con **ISC-AERMOD View**: área única 212×184 m, **altura de emisión 5 m**, metano como fuente puntual. ⚠️ Flujo declarado 7,95·10⁻⁵ ou/m²·s — **outlier de 5 órdenes de magnitud**. Ver F.1 |
| 7 | **EPA — LandGEM v3.1**, manual de usuario y herramienta | <https://cfpub.epa.gov/si/si_public_record_report.cfm?dirEntryId=365160&Lab=CESER> | ✅ Modelo FOD; Q = L₀·k·M·e^(−kt) |
| 8 | **EPA — Landfill Gas Modeling (cap. 2)** | <https://www.epa.gov/system/files/documents/2021-07/pdh_chapter2.pdf> | ✅ Defectos: **k = 0,04/año** (≥25 in lluvia), **0,02/año** en seco; **L₀ = 100 m³/Mg** |
| 9 | **EPA — AP-42, Vol. I, Cap. 2.4, MSW Landfills** (versión 2024) | <https://www.epa.gov/system/files/documents/2024-01/c02s04_1_2024_rlso.pdf> | ✅ Sección de referencia para factores de emisión de vertederos |
| 10 | **ALL4** — *U.S. EPA Releases Significant Update to AP-42 Section 2.4* | <https://www.all4inc.com/4-the-record-articles/u-s-epa-releases-significant-update-to-ap-42-section-2-4-for-solid-waste-landfills/> | ✅ Actualización de **mayo 2025**: sustitución de la ecuación FOD por **HH-1 del Subpart HH**; NMOC como sustituto de COV |
| 11 | **SCS Engineers** — *EPA Finalizes AP-42 Chapter 2, Section 4* | <https://www.scsengineers.com/epa-finalizes-ap-42-chapter-2-section-4-msw-landfills/> | ✅ Finalización en **agosto de 2024** |
| 12 | **IPCC (2006)**, *Guidelines for National GHG Inventories*, Vol. 5, Cap. 3 — Solid Waste Disposal | <https://www.ipcc-nggip.iges.or.jp/public/2006gl/pdf/5_Volume5/V5_3_Ch3_SWDS.pdf> | ✅ Modelo FOD con DOC; **k = ln2/t½**; rango k **0,005–0,4**; necesidad de 3–5 semividas de histórico |
| 13 | **IPCC** — Chapter 5 Waste | <https://www.ipcc.ch/site/assets/uploads/2018/03/5_Waste-1.pdf> | ✅ Ídem, marco general |
| 14 | **SCS Engineers** — *LFG Collection Efficiency: Debunking the Rhetoric* | <https://www.scsengineers.com/wp-content/uploads/2015/03/Sullivan_LFG_Collection_Efficiency-Debunking_the_Rhetoric.pdf> | ✅ Discusión crítica de las eficiencias de captación |
| 15 | **EPA** — *Inventory of U.S. GHG Emissions and Sinks*, cap. 7 Waste | <https://www.epa.gov/system/files/documents/2023-04/US-GHG-Inventory-2023-Chapter-7-Waste.pdf> | ✅ **95 %** con cobertura final geomembrana + extracción activa; crédito de oxidación **0–35 %** |
| 16 | *Efficiency of landfill gas collection for methane emission reduction*, **Taylor & Francis** | <https://www.tandfonline.com/doi/full/10.1080/20430779.2012.730798> | ✅ Defecto IPCC **20 %** sin medidas; oxidación metanótrofa **10–40 %** |
| 17 | **Xu et al. (2014)**, *Impact of changes in barometric pressure on landfill methane emission*, **Global Biogeochemical Cycles** | <https://agupubs.onlinelibrary.wiley.com/doi/full/10.1002/2013GB004571> | ✅ Presión descendente → flujo máximo; ascendente → supresión casi total; retardo 0–4 h |
| 18 | *Methane emission dynamics from a Danish landfill: the effect of changes in barometric pressure*, **Waste Management (2021)** | <https://www.sciencedirect.com/science/article/pii/S0956053X21006310> | ✅ Los efectos de presión a corto plazo **superan a temperatura y viento**; grandes variaciones estacionales, sin variabilidad diurna |
| 19 | *Passive landfill gas emission – Influence of atmospheric pressure*, **Waste Management (2005)** | <https://www.sciencedirect.com/science/article/abs/pii/S0956053X0500067X> | ✅ Inversión del flujo cada ~20 h; **50 % de las fases de emisión duran ≤ 10 h** |
| 20 | **DTU** — *Pressure effects on methane emissions from landfills* | <https://orbit.dtu.dk/en/publications/pressure-effects-on-methane-emissions-from-landfills/> | ✅ Confirmación independiente |
| 21 | **Real Decreto 646/2020, de 7 de julio**, eliminación de residuos mediante depósito en vertedero | <https://www.boe.es/buscar/doc.php?id=BOE-A-2020-7438> | ✅ **Norma vigente. Derogó el RD 1481/2001.** Transpone la Directiva (UE) 2018/850 que modifica la 1999/31/CE. Anexo III: control de gases |
| 22 | **Orden TED/789/2023, de 7 de julio** — método de cálculo del coste de emisión de GEI en vertedero | <https://www.boe.es/diario_boe/txt.php?id=BOE-A-2023-16400> | ✅ Factores de mitigación separados para gas **captado** y **difuso**; valorización, antorcha y **bioventanas** |
| 23 | **MITECO** — Vertederos | <https://www.miteco.gob.es/en/calidad-y-evaluacion-ambiental/temas/prevencion-y-gestion-residuos/flujos/vertederos.html> | ✅ Marco estatal |
| 24 | **AGQ Labs** — Inspección de vertederos y cumplimiento del RD 646/2020 | <https://agqlabs.es/2025/11/06/inspeccion-de-vertederos-rd-646-2020/> | ✅ Control por entidades acreditadas **UNE-EN ISO/IEC 17020**; Anexo III |
| 25 | **EPA** — *Addendum User's Guide for AERMOD* | <https://downloads.regulations.gov/EPA-HQ-OAR-2015-0310-0016/content.pdf> | ✅ **Límite histórico de 20 vértices en AREAPOLY sustituido por asignación dinámica**; advertencia contra polígonos complejos |
| 26 | **EPA** — *User's Guide for the AMS/EPA Regulatory Model (AERMOD)* | <https://gaftp.epa.gov/Air/aqmg/SCRAM/models/preferred/aermod/aermod_userguide.pdf> | ✅ Parámetros de AREAPOLY |
| 27 | **RETEMA** — Biocassette de biofiltración avanzada para H₂S y olores | <https://www.retema.es/articulos-reportajes/biocassette-de-biofiltracion-avanzada-para-tratar-emisiones-de-sulfuro-de> | ✅ **95 %** de eliminación de H₂S para entrada ≤ 300 ppm |
| 28 | **AIDIC** — *Odour Emission Factors: Fundamental Tools for Air Quality Management* | <https://www.aidic.it/cet/14/40/033.pdf> | ⚠️ Localizado, **no extraído**. Vía natural para ampliar el catálogo de OEF |
| 29 | **Environment Agency (RU) / EPA Irlanda AG9 (2019)** — criterio por ofensividad | Reproducido en [compostaje §C.3](compostaje.md) | ✅ **Vertederos = categoría «más ofensiva» → 1,5 ou_E/m³ al P98 horario** |

**Fecha de consulta de todas las fuentes: 21 de julio de 2026.**

---

## F. INCERTIDUMBRES Y AVISOS

### F.1 · Lo que NO se ha podido verificar

| Punto | Estado |
|---|---|
| **Concentración de olor del biogás bruto de vertedero (ou_E/m³)** | ❌ **No verificado.** Es el eslabón que permitiría conectar LandGEM/IPCC con AERMOD (A.3.3). Sin él, **los modelos de generación de biogás no pueden alimentar directamente un cálculo de olor**. Cualquier informe que lo haga debe explicitar el valor usado y su procedencia |
| **Desglose del OEF de Sironi (2005) por tipo de superficie** | ⚠️ **No extraído.** El texto completo devuelve 403. Se dispone del valor global **5,5 ± 3,4 ou_E/(s·m²)** pero no del reparto entre frente activo, cobertura temporal y sellado que el artículo pueda contener. **Es la laguna más relevante de este documento** |
| **Flujo de 7,95·10⁻⁵ ou/m²·s de PMC6582209** | ⚠️ **Outlier no explicado.** Está **cinco órdenes de magnitud** por debajo de todos los demás valores publicados (A.3.1). Puede deberse a un error de unidades en el artículo, a un vertedero proyectado y no operativo, o a una definición distinta de la unidad de olor. **No debe usarse como factor de emisión.** Se cita únicamente como precedente de configuración de AERMOD |
| **Factor de emisión de olor de balsa de lixiviados de VERTEDERO** | ⚠️ **Transpuesto, no medido en vertedero.** El valor de **500 ou_E/(s·m²)** procede de percolación de lixiviados en compostaje (EA 2002d, vía guía catalana). Es el mismo tipo de foco físico y es lo mejor disponible, pero **no es un dato de vertedero** |
| **Factores de emisión de olor de vertederos ESPAÑOLES** | ❌ **No localizados.** Todos los factores de A.3.1 son italianos, chinos o del norte de Europa. Ninguno es español ni mediterráneo-insular. Dado que la generación de biogás depende de clima y de composición del residuo, **la transferibilidad es una hipótesis** |
| **Eficacia de eliminación de OLOR de las bioventanas** | ❌ **No verificada.** Su función documentada (y la reconocida por la Orden TED/789/2023) es la **oxidación de metano**, no el control de olor |
| **Eficacia de pantallas cortavientos y de neutralizantes de olor** | ❌ **No verificada.** Se citan en D.6 como práctica habitual, sin respaldo cuantitativo. Los neutralizantes, además, **no reducen la emisión**: actúan sobre la percepción |
| **Valores de k y L₀ vigentes tras la actualización de mayo 2025** | ⚠️ **A verificar antes de citar.** Los defectos clásicos (k = 0,04/0,02 año⁻¹; L₀ = 100 m³/Mg) están verificados, pero la sustitución de la ecuación FOD por **HH-1 del Subpart HH** puede haber cambiado su papel dentro de la formulación. Consultar la versión vigente de AP-42 §2.4 |
| **Límite real de vértices de AREAPOLY en esta herramienta** | ⚠️ El límite de 20 es de la **implementación**, no de AERMOD moderno, que usa asignación dinámica (A.2.2). Si en algún caso resultara restrictivo, la solución es partir el polígono, no simplificar el troceado físico |
| **Contenido detallado de la AAI de referencia** | ⚠️ Cada AAI es distinta y puede contener un valor de olor, un compromiso de la DIA o una remisión autonómica. **Leer la AAI concreta antes de elegir criterio** (C.3) |

### F.2 · Avisos metodológicos

1. ⚠️ **El caudal Q es la mayor fuente de error de todo el estudio** — así lo tiene medido el equipo, y
   los datos de A.3.1 lo confirman de forma brutal: entre el frente activo (46,5–136) y una superficie
   agotada (0,011) hay **cuatro órdenes de magnitud** dentro de la misma instalación. **Tomar un valor
   «medio» de la bibliografía y aplicarlo a todo el vaso produce un resultado sin significado.** Para un
   informe con consecuencias: **olfatometría propia según UNE-EN 13725:2022**, con muestreo por tipo de
   superficie. Si es bibliográfico, **presentar un rango, no un valor**.

2. ⚠️ **La técnica de muestreo cambia el factor.** Campana de flujo, túnel de viento, equipo de olfateo
   de campo y modelización inversa dan resultados distintos sobre la misma superficie, y los valores de
   A.3.1 proceden de las cuatro. **No son intercambiables** y no deben mezclarse en una misma tabla de
   entrada sin declararlo.

3. ⚠️ **La altura de emisión es el parámetro más sensible del modelo (×12 entre 1 y 6 m)**, y en
   vertedero hay una confusión específica y frecuente: **usar la altura del montículo como altura de
   emisión**. El relieve entra por AERMAP, no por la altura de la fuente (A.4.1). **Tabla de
   sensibilidad obligatoria.**

4. ⚠️ **En fuentes de área pasivas el máximo cae pegado a la fuente.** Dos consecuencias a declarar:
   (a) los resultados son **muy sensibles a la geometría** y al mallado de receptores en el límite de
   parcela; (b) AERMOD, como modelo gaussiano de estado estacionario, **está en el límite inferior de su
   rango de validez** a decenas de metros del foco. Los valores en el propio perímetro deben leerse con
   prudencia.

5. ⚠️ **La emisión de un vertedero no es constante y está correlacionada con la meteorología.** La
   modulación por presión barométrica es fuerte, verificada y con retardo de horas (A.4.2). AERMOD se
   ejecuta con tasa constante. **La media del periodo probablemente se conserva; los percentiles altos
   no.** Es una limitación estructural del enfoque, no un defecto de la implementación, y hay que
   declararla.

6. ⚠️ **El frente activo es un foco MÓVIL.** Su posición cambia con el plan de explotación, y con ella
   cambia cuál es el receptor crítico. Un estudio válido para 2026 puede no serlo para 2030. **Declarar
   el año/fase evaluado** y, si es posible, evaluar la posición más desfavorable prevista.

7. ⚠️ **El olor no es aditivo y no se deduce de la masa.** No existe conversión general de µg/m³ o de
   mg/m³ de H₂S o NH₃ a ou_E/m³ en una mezcla real: los umbrales son específicos de cada compuesto y hay
   sinergia, antagonismo y enmascaramiento. **Esto afecta directamente a los datos de A.3.2 y D.2**, que
   están en masa: usarlos como ratios de olor es una hipótesis a declarar. Ver
   [metodología de olores](../metodologia/olores_metodologia.md).

8. ⚠️ **La salida actual no permite calcular el P98 de medias horarias** — sólo se exporta la media del
   periodo por receptor, y los máximos de 1 h y 24 h quedan en `aermod.out` sin serie horaria. **El P98
   es exactamente el estadístico que exigen el Decreto 185/2025 de Canarias y el marco EA/EPA-IE.**
   Mientras no se amplíe la salida (`POSTFILE` o cálculo de percentiles en AERMOD), **el informe no
   puede acreditar cumplimiento** frente a esos criterios: sólo puede acotar. Ver el recuadro del
   apartado B.9.

9. ⚠️ **Criterio aplicable: no hay uno solo, y los vertederos son «categoría más ofensiva».** El marco
   EA/EPA-IE da **1,5 ou_E/m³ al P98 horario**, más exigente que los **3 ou_E/m³** de la Categoría 1 del
   Decreto canario. En Canarias rige el Decreto por ser norma vigente; fuera, 1,5 es la referencia
   defendible. **La elección debe justificarse y declararse en la sección 1 del informe**, y conviene
   presentar ambos valores.

10. ⚠️ **Norma vigente: RD 646/2020, no RD 1481/2001.** El segundo está derogado pero sigue apareciendo
    en pliegos, AAI antiguas e informes en circulación. Citarlo como vigente es un error que resta
    credibilidad al conjunto del documento (C.1).
