# Bibliografía — estudios de referencia por temática

Estudios reales de dispersión de contaminantes, organizados por tipo. Sirven de **modelo para
redactar informes**: qué estructura siguen, qué criterios aplican y cómo presentan los
resultados en cada temática.

> **Para qué es esto:** que un agente pueda, **dado un tipo de estudio**, coger los resultados
> numéricos que produce la herramienta (`tmp/Results/…`) y **generar el informe** siguiendo la
> estructura y los criterios que se usan de verdad en esa temática. Un estudio de olor de una
> EDAR y uno de partículas de una cantera no se parecen en nada: ni el estadístico, ni el
> límite, ni las secciones del documento.

---

## Estructura

```
bibliografia/
├── olores/         EDAR, compostaje, granjas, vertederos · unidades ou_E, percentiles
├── industrial/     chimeneas, SO₂/NOₓ/CO · calidad del aire, máximos y medias anuales
├── particulas/     canteras, acopios, obra · PM10/PM2.5, deposición
├── trafico/        viario · fuentes lineales (ver aviso al final)
├── normativa/      límites legales y criterios aplicables (varían por CCAA y país)
└── metodologia/    modelización, validación, factor pico-media, olfatometría
```

Las cuatro primeras son **por temática de proyecto** y se corresponden con el recetario de
[`../guias/user_guide.md`](../guias/user_guide.md) (Parte 8). Las dos últimas son
**transversales**: se consultan sea cual sea el tipo de estudio.

---

## Índice — estado actual

### ✅ Disponibles

**Transversales — léelos primero, los temáticos se apoyan en ellos**

| Documento | Qué cubre |
|---|---|
| [**normativa/marco_normativo_ES_UE.md**](normativa/marco_normativo_ES_UE.md) | El marco completo: jerarquía UE→España→CCAA, valores límite de calidad del aire (vigentes **y** los de 2030 de la Directiva 2024/2881), emisiones industriales (IED, MCP), el mapa autonómico de olores y cuándo es obligatorio modelar. **Empieza por aquí.** |
| [**normativa/criterios_olor_internacional.md**](normativa/criterios_olor_internacional.md) | Criterios de olor de Países Bajos e Italia, verificados sobre norma primaria. Incluye **cinco errores frecuentes corregidos** — buena parte de lo que se cita en informes está desactualizado. |
| [**metodologia/olores_metodologia.md**](metodologia/olores_metodologia.md) | Cómo pasar de la media horaria al criterio: olfatometría EN 13725, **factor pico-media** (Smith, Schauberger) con sus ecuaciones, cálculo del percentil, ley de Stevens, umbrales por compuesto. ⚠️ Documenta también **por qué el P98 no se puede calcular hoy con la salida de la herramienta**. |

**Por temática**

| Documento | Qué cubre |
|---|---|
| [**olores/edar.md**](olores/edar.md) | EDAR: **factores de emisión reales por unidad de proceso** en ou_E/(s·m²), listos para AREAPOLY; criterio de la Comunidad de Madrid (7 uo_E/m³ P98); eficacias de biofiltro medidas en planta. |
| [**olores/compostaje.md**](olores/compostaje.md) | Compostaje: factores por fase (guía de la Generalitat con tablas NeR/EA), **un caso AERMOD real publicado con todos sus parámetros de fuente**, factores de confinamiento, NEA-MTD 200–1.000 ou_E/Nm³. |
| [**olores/vertederos.md**](olores/vertederos.md) | Vertederos: **cuatro órdenes de magnitud de emisión** dentro del mismo vaso y cuál usar en cada zona; el efecto de la **presión barométrica**; troceado de superficies grandes; RD 646/2020. |
| [**olores/granjas.md**](olores/granjas.md) | Ganadería intensiva: **factores de olor por plaza y especie**, NEA-MTD de NH₃ (Decisión 2017/302), umbrales de la Directiva 2024/1785, RD 306/2020 y 637/2021, la trampa de los extractores laterales. |
| [**olores/industria_alimentaria.md**](olores/industria_alimentaria.md) | Agroalimentaria (mataderos, SANDACH, secaderos, almazaras, bodegas, café): reparto en las tres categorías canarias, los dos BREF (FDM y mataderos), criterio británico H4, y la **estacionalidad** que invalida el P98 anual en campañas. |
| [**industrial/chimeneas_industriales.md**](industrial/chimeneas_industriales.md) | Chimeneas: **ecuaciones de sobreelevación de Briggs** verificadas del documento de formulación de AERMOD, criterio **GEP**, el problema del **NO₂** (ARM2/OLM/PVMRM), tratamiento del **fondo**, eficacias de depuración. **Base común de los dos siguientes.** |
| [**industrial/combustion_mcp.md**](industrial/combustion_mcp.md) | Combustión mediana (Directiva 2015/2193, RD 1042/2017): **VLE por combustible y potencia** con sus notas al pie (que mandan sobre la cabecera), la conversión **mg/Nm³ → g/s** paso a paso, particularidades de la biomasa, divergencias de Canarias. |
| [**industrial/incineracion.md**](industrial/incineracion.md) | Incineración y coincineración: VLE del RD 815/2013 y NEA-MTD (Decisión 2019/2010); y **por qué esta herramienta no puede cerrar sola un estudio de riesgo** de dioxinas y metales — actúan por deposición e ingesta, no por inhalación. |
| [**industrial/cov.md**](industrial/cov.md) | COV (tanques, cargaderos, fugitivas, gasolineras): la **doble naturaleza salud/olor** (benceno anual vs olor por percentil), las **pérdidas por evaporación** (AP-42 cap. 7, TANKS), y la normativa propia (RD 117/2003, recuperación de vapores). |
| [**particulas/canteras_y_obras.md**](particulas/canteras_y_obras.md) | Canteras, acopios y obras: **ecuaciones de factores de emisión AP-42** con sus rangos de validez, estructura de informe, normativa PM10/PM2.5 y medidas correctoras. |

### 🚧 Pendientes

| Documento | Estado |
|---|---|
| `trafico/viario.md` | Pendiente de decidir enfoque — ver aviso al final |

> **⚠️ Dos hallazgos que conviene no perder de vista**
>
> **1. Ya hay norma española de olor con números.** El **Decreto 185/2025 de Canarias** (en vigor
> desde el 19/12/2025) es la primera norma autonómica con **valores objetivo de inmisión**:
> 3 / 6 / 9 ou_E/m³ al **percentil 98 de medias horarias sobre año natural**, por categoría de
> actividad. Una EDAR es Categoría 1 → 3 ou_E/m³. Y el criterio británico/irlandés para
> compostaje de verde bien aireado **converge en ese mismo 3,0**: dos marcos independientes
> apuntando al mismo número, lo que lo hace la referencia más defendible.
>
> **2. ✅ Ya se pueden acreditar los criterios con superaciones permitidas** *(resuelto el
> 22/07/2026)*. Los criterios legales se definen sobre **el enésimo valor más alto** —el 19.º
> horario de NO₂, el 36.º diario de PM10, el **percentil 98 de olor**—, y durante la redacción de
> esta bibliografía la herramienta solo exportaba la media del periodo.
>
> Ahora el motor vuelca la **serie horaria por receptor** (`postfile=True`) y calcula el
> estadístico con `percentiles_por_receptor(pct=…, rank=…, peak_factor=…)`.
>
> ⚠️ **Varios informes de esta carpeta fueron escritos ANTES** y describen esa limitación como
> vigente (sobre todo `olores/granjas.md` y `metodologia/olores_metodologia.md`). El
> procedimiento que proponen es correcto; lo que ha cambiado es que **ya está implementado**.
> Detalle en
> [`metodologia/olores_metodologia.md`](metodologia/olores_metodologia.md) y en
> [`../guias/user_guide.md`](../guias/user_guide.md) §7.3.

---

## Cómo añadir un estudio

Deja el fichero en la carpeta que le toque. Si es un PDF o un documento que no se puede leer
como texto, **acompáñalo de una ficha `.md` con el mismo nombre**:

```
olores/2021_EDAR_Girona.pdf
olores/2021_EDAR_Girona.md      ← la ficha
```

> **⚠️ Por qué la ficha importa**
>
> Un agente que se encuentre veinte PDF sin fichas tiene que abrirlos todos para saber cuál le
> sirve. Con fichas, **filtra por metadatos y lee solo lo que necesita**. La ficha es lo que
> convierte un montón de documentos en algo consultable.
>
> Si el estudio ya es un `.md` legible, basta con ponerle la cabecera de metadatos.

### La cabecera de metadatos

Al principio de cada ficha (o del propio `.md`):

```markdown
---
tipo: olores                  # olores | industrial | particulas | normativa | metodologia
fuente: area                  # punto | area | volumen | linea | mixta
contaminantes: [H2S, NH3]     # o [ou_E] si es olor medido por olfatometría
estadistico: percentil-98     # máximo-horario | media-anual | percentil-98 | media-diaria
umbral: 3 ou_E/m3             # el límite con el que se compara
ambito: Cataluña              # jurisdicción cuya normativa aplica
anio: 2021
origen: "Consultoría X · expediente ambiental"
---
```

Y debajo, en texto libre y breve:

- **De qué va** el estudio, en dos líneas.
- **Cómo está estructurado el informe** (los títulos de sus apartados). Esto es lo más útil de
  todo para generar informes.
- **Qué hipótesis declara** y cómo justifica el caudal de emisión.
- **Qué conviene copiar** y qué no.

---

## Qué mirar en un estudio, según su temática

Guía rápida de lo que hay que extraer de cada tipo. El detalle técnico está en las guías.

| Temática | El estadístico que decide | Lo que hay que buscar en el estudio |
|---|---|---|
| **Olores** | **Percentil** (típicamente P98) de medias horarias, en `ou_E/m³` | Qué percentil y umbral aplica, si usa **factor pico-media** y con qué formulación, y de dónde sale el caudal (olfatometría) |
| **Industrial** | Máximo horario o media anual, en µg/m³ | Contaminante y su norma, tratamiento del NO₂ (química no lineal), si modela *downwash* de edificios |
| **Partículas** | Media diaria y anual de PM10 | Si modela **deposición** (las partículas caen: rompen la hipótesis de gas conservativo) y cómo estima la emisión difusa |
| **Normativa** | — | El límite exacto, el periodo de promediado y **la jurisdicción**: en España no hay norma estatal de olor, va por CCAA u ordenanza |
| **Metodología** | — | Formulaciones de pico-media, criterios de validación, tratamiento de calmas |

> **⚠️ OJO · El estadístico no es un detalle de forma**
>
> Es lo que determina si un proyecto cumple o no. La herramienta calcula **medias horarias**;
> pasar de ahí al percentil o a la media anual, y aplicar el factor pico-media en los estudios
> de olor, **se hace por fuera** del modelo. Está explicado en
> [`../guias/user_guide.md`](../guias/user_guide.md) §7.3.

---

## Lo que la herramienta ya produce (la otra mitad del informe)

Para que un informe se genere solo hacen falta dos cosas: **la plantilla** (que sale de aquí) y
**los números** (que salen de la herramienta). Los números están, por cada simulación, en:

```
tmp/Results/<coordenadas>/     mapa + concentraciones.csv (todos los receptores) + resumen.json
tmp/Aermod/<caso>/caso.json    con qué parámetros se corrió
```

Y los datos de partida están en `data/` (terreno, meteo y fuentes del caso activo).

> **💼 Lo que un informe defendible tiene que declarar sí o sí**
>
> Sale de los dos análisis de sensibilidad de [`../guias/`](../guias/) — son los puntos donde
> de verdad se juega la credibilidad del estudio:
>
> 1. **De dónde sale el caudal `Q`.** Es la mayor fuente de error, con diferencia (se detectó un
>    caso con un error de ×10⁷ que solo se cazó por comprobación de orden de magnitud).
> 2. **La altura de emisión.** Mueve el máximo un **factor 12 entre 1 m y 6 m**.
> 3. **El periodo meteorológico** y que sea un año completo si se usan percentiles.
> 4. **La traducción CORINE→NLCD** del uso del suelo, que es un juicio técnico, no un dato.
> 5. **El umbral olfativo** empleado, si es un estudio de olor: varían hasta ×30 entre fuentes
>    bibliográficas.

---

---

## ⚠️ Tráfico viario: un aviso antes de empezar

La carpeta `trafico/` existe, pero conviene saber que **el tráfico rodado no encaja hoy con esta
herramienta**, por dos motivos independientes:

1. **Son fuentes lineales**, y la aplicación solo admite fuentes **puntuales** y **de área**.
2. **En la UE no se modela con AERMOD.** Lo habitual es CALINE/ADMS-Urban, o el enfoque de
   inventario del EMEP/EEA Guidebook.

Así que un documento de tráfico puede servir para dos cosas **distintas**, y hay que decidir cuál
antes de escribirlo: documentar **qué haría falta añadir a la herramienta**, o documentar **cuándo
derivar el caso a otra herramienta**.

## ⚠️ Lo que queda deliberadamente fuera: accidentes y fugas (Seveso)

Escapes de gases **densos** (cloro, GLP, CO₂ concentrado, criogénicos). No están aquí a propósito:
**AERMOD no sirve** para eso — la nube tiene densidad propia, se derrama por el suelo como un
líquido y no se deja llevar por el viento. Es otra física, y necesita modelos específicos (SLAB,
DEGADIS, PHAST). Está explicado en [`../guias/theory_guide.md`](../guias/theory_guide.md) §15.

Si algún día interesa cubrirlo, lo útil sería un documento de **«cuándo NO usar esta
herramienta»**, no un tipo de informe más.

---

*Documentación relacionada: [`../guias/user_guide.md`](../guias/user_guide.md) Parte 8
(recetario por tipo de proyecto) y [`../guias/theory_guide.md`](../guias/theory_guide.md) §9-§10
(olores y mezclas).*
