---
tipo: normativa
ambito: España + UE
anio: 2026
origen: vigilancia tecnológica
---

# Marco normativo de calidad del aire y emisiones — España y UE

> La calidad del aire (inmisión) se rige por la Directiva (UE) 2024/2881, que sustituye a la 2008/50/CE
> y endurece drásticamente los límites con horizonte 2030; en España sigue vigente el RD 102/2011 hasta
> que se transponga (plazo: 11 de diciembre de 2026). Las emisiones (foco) van por otra rama: IED
> 2010/75/UE, revisada por la 2024/1785, más el RDL 1/2016 y el RD 815/2013. El olor **no tiene norma
> estatal**: hasta diciembre de 2025 sólo había ordenanzas y borradores, y Canarias es la primera CCAA
> que fija valores objetivo de inmisión de olor (Decreto 185/2025).

---

## A. El marco, de arriba abajo

Hay dos cosas que la gente confunde constantemente y que conviene separar desde el principio:

- **Inmisión** = lo que hay *en el aire que respira la gente*, lejos del foco. Se mide en µg/m³ y se
  compara con **valores límite de calidad del aire**. **Es lo que calcula AERMOD.**
- **Emisión** = lo que sale *por la chimenea*. Se mide en mg/Nm³ o g/s y se compara con **valores
  límite de emisión (VLE)** fijados en la autorización. **Es un dato de entrada de AERMOD, no un
  resultado.**

Un informe de dispersión vive en el primer mundo (inmisión) pero se alimenta del segundo (emisión).
Casi todos los errores graves de un estudio están en la frontera entre ambos.

### La jerarquía

```
             ┌──────────────────────────────────────────────────────┐
             │  DERECHO DE LA UNIÓN EUROPEA                         │
             │  Directivas: obligan en el RESULTADO, no en la forma │
             └──────────────────────────────────────────────────────┘
                    │                              │
       INMISIÓN     │                              │   EMISIÓN (foco)
       (calidad     │                              │
        del aire)   ▼                              ▼
        Dir. (UE) 2024/2881               Dir. 2010/75/UE (IED)
        (deroga 2008/50/CE y                 modificada por
         2004/107/CE el 12-12-2026)       Dir. (UE) 2024/1785
                    │                     Dir. (UE) 2015/2193 (MCP)
                    │                              │
                    ▼                              ▼
             ┌──────────────────────────────────────────────────────┐
             │  ESTADO — legislación básica (art. 149.1.23 CE)      │
             │  Ley 34/2007 de calidad del aire y protección de la  │
             │  atmósfera  ·  RD 102/2011 (inmisión)                │
             │  RDL 1/2016 (IPPC) · RD 815/2013 · RD 100/2011       │
             │  RD 1042/2017 (combustión mediana) · RD 818/2018     │
             └──────────────────────────────────────────────────────┘
                                     │
                                     ▼
             ┌──────────────────────────────────────────────────────┐
             │  COMUNIDADES AUTÓNOMAS                               │
             │  Ejecutan, autorizan (AAI y autorización de          │
             │  emisiones), vigilan, y PUEDEN SER MÁS ESTRICTAS.    │
             │  Aquí es donde vive TODO lo relativo al OLOR.        │
             │  Ej.: Canarias D. 185/2025 · Andalucía D. 239/2011   │
             └──────────────────────────────────────────────────────┘
                                     │
                                     ▼
             ┌──────────────────────────────────────────────────────┐
             │  MUNICIPIOS — ordenanzas y licencia de actividad     │
             │  Ej.: modelo de ordenanza de olores de la Diputació  │
             │  de Barcelona (BOPB 29-04-2024)                      │
             └──────────────────────────────────────────────────────┘
```

### Cómo leerla en la práctica

1. **Una Directiva no se aplica directamente** al titular de una actividad: hay que buscar la norma
   española que la transpone. La excepción es el efecto directo tras vencer el plazo de transposición,
   que es terreno jurídico y no debe darse por supuesto en un informe técnico.
2. **El Estado fija mínimos; las CCAA pueden endurecer**, nunca relajar. Si un informe se hace para
   Canarias, la referencia es el decreto canario *además* de la norma estatal.
3. **El escalón autonómico es el que decide en olores**, porque el Estado no ha legislado.
4. **La ordenanza municipal puede añadir** condiciones a la licencia de actividad.

**Norma marco estatal:** Ley 34/2007, de 15 de noviembre, de calidad del aire y protección de la
atmósfera (BOE-A-2007-19744). Su **Anexo IV** contiene el Catálogo de Actividades Potencialmente
Contaminadoras de la Atmósfera (CAPCA), y su **Anexo I** la lista de contaminantes. Casi toda la
normativa posterior de emisiones cuelga de estos dos anexos.

---

## B. Calidad del aire (inmisión) — los límites que se comparan con el resultado del modelo

Esta es **la tabla contra la que se contrasta la salida de AERMOD** en un estudio de contaminantes de
masa. Todos los valores están referidos a **293 K y 101,3 kPa** (RD 102/2011, Anexo I).

### B.1 · Valores límite VIGENTES HOY en España

Fuente: RD 102/2011, Anexo I (texto consolidado del BOE, verificado literalmente).

| Contaminante | Valor límite | Periodo de promediado | Superaciones permitidas | Norma |
|---|---|---|---|---|
| **SO₂** | 350 µg/m³ | 1 hora | 24/año civil | RD 102/2011, Anexo I.A.I |
| **SO₂** | 125 µg/m³ | 24 horas | 3/año civil | RD 102/2011, Anexo I.A.I |
| **SO₂** (nivel crítico vegetación) | 20 µg/m³ | Año civil e invierno (1 oct – 31 mar) | — | RD 102/2011, Anexo I.A.I |
| **NO₂** | 200 µg/m³ | 1 hora | 18/año civil | RD 102/2011, Anexo I.B.I |
| **NO₂** | 40 µg/m³ | Año civil | — | RD 102/2011, Anexo I.B.I |
| **NOₓ** (nivel crítico vegetación) | 30 µg/m³ (como NO₂) | Año civil | — | RD 102/2011, Anexo I.B.I |
| **PM10** | 50 µg/m³ | 24 horas | 35/año | RD 102/2011, Anexo I.C.I |
| **PM10** | 40 µg/m³ | Año civil | — | RD 102/2011, Anexo I.C.I |
| **PM2,5** (fase I) | 25 µg/m³ | Año civil | — | RD 102/2011, Anexo I.D.I |
| **PM2,5** (fase II) ⚠️ | 20 µg/m³ | Año civil | — | RD 102/2011, Anexo I.D.I — desde 1-1-2020 (ver H) |
| **CO** | 10 mg/m³ | Máxima diaria de las medias móviles octohorarias | — | RD 102/2011, Anexo I.G |
| **Benceno** | 5 µg/m³ | Año civil | — | RD 102/2011, Anexo I.F |
| **Plomo** | 0,5 µg/m³ | Año civil | — | RD 102/2011, Anexo I.E |
| **O₃** (valor objetivo salud) | 120 µg/m³ | Máxima diaria de las medias móviles 8 h | 25 días/año civil, promediados en 3 años | RD 102/2011, Anexo I.H.I |
| **H₂S** | **No existe valor límite** | — | — | *Verificado: el RD 102/2011 no regula el H₂S* |

**Umbrales de activación, información y alerta** (RD 102/2011, Anexo I). Son los que disparan los
planes de acción a corto plazo, no criterios de diseño, pero aparecen en informes de episodios:

| Contaminante | Activación | Información | Alerta |
|---|---|---|---|
| SO₂ (horario) | 200 µg/m³ | 350 µg/m³ | 500 µg/m³ (3 h consecutivas) |
| NO₂ (horario) | 180 µg/m³ | 200 µg/m³ | 400 µg/m³ (3 h consecutivas) |
| PM10 (24 h o móvil 24 h) | 40 µg/m³ | 50 µg/m³ | 80 µg/m³ |
| PM2,5 (24 h o móvil 24 h) | 25 µg/m³ | 35 µg/m³ | 50 µg/m³ |

### B.2 · Valores límite que deberán cumplirse A MÁS TARDAR EL 1 DE ENERO DE 2030

Fuente: Directiva (UE) 2024/2881, **Anexo I, Sección 1, Cuadro 1** (DOUE L de 20.11.2024, verificado
literalmente sobre el PDF oficial).

Este es el cambio grande: se alinean los valores con las guías OMS 2021 y **aparecen límites diarios
para NO₂, SO₂ y CO que hoy no existen**.

| Contaminante | Valor límite 2030 | Periodo de promediado | Superaciones permitidas | Norma |
|---|---|---|---|---|
| **PM2,5** | **10 µg/m³** | Año civil | — | Dir. (UE) 2024/2881, Anexo I.1, Cuadro 1 |
| **PM2,5** | **25 µg/m³** | 1 día | 18/año civil | ídem |
| **PM10** | **20 µg/m³** | Año civil | — | ídem |
| **PM10** | **45 µg/m³** | 1 día | 18/año civil | ídem |
| **NO₂** | **20 µg/m³** | Año civil | — | ídem |
| **NO₂** | **50 µg/m³** | 1 día *(nuevo)* | 18/año civil | ídem |
| **NO₂** | 200 µg/m³ | 1 hora | **3**/año civil (hoy 18) | ídem |
| **SO₂** | **20 µg/m³** | Año civil *(nuevo)* | — | ídem |
| **SO₂** | **50 µg/m³** | 1 día (hoy 125) | 18/año civil | ídem |
| **SO₂** | 350 µg/m³ | 1 hora | **3**/año civil (hoy 24) | ídem |
| **CO** | 10 mg/m³ | Máxima diaria de las medias octohorarias | — | ídem |
| **CO** | **4 mg/m³** | 1 día *(nuevo)* | 18/año civil | ídem |
| **Benceno** | **3,4 µg/m³** | Año civil | — | ídem |
| **Plomo** | 0,5 µg/m³ | Año civil | — | ídem |
| **Arsénico** | 6,0 ng/m³ | Año civil | — | ídem |
| **Cadmio** | 5,0 ng/m³ | Año civil | — | ídem |
| **Níquel** | 20 ng/m³ | Año civil | — | ídem |
| **Benzo(a)pireno** | 1,0 ng/m³ | Año civil | — | ídem |

**Lo que cambia de verdad, en una frase por contaminante:**
- **PM2,5 anual: de 25 a 10 µg/m³.** Es una división por 2,5. Es el cambio más severo de todo el paquete.
- **NO₂ anual: de 40 a 20 µg/m³**, y aparece un límite diario de 50 µg/m³ que hoy no existe.
- **SO₂**: aparece un límite anual (20) y el diario baja de 125 a 50 µg/m³.
- **PM10 anual: de 40 a 20 µg/m³**; el diario baja de 50 a 45 y las superaciones de 35 a 18.

### B.3 · Régimen transitorio hasta 2030

La Directiva 2024/2881 mantiene, en su **Anexo I, Sección 1, Cuadro 2**, valores que deben cumplirse
**a más tardar el 11 de diciembre de 2026** y que coinciden con los actualmente vigentes
(PM2,5 anual 25; PM10 50/día con 35 superaciones y 40 anual; NO₂ 200/h con 18 superaciones y 40 anual;
SO₂ 350/h con 24 y 125/día con 3; benceno 5; CO 10 mg/m³ 8 h; Pb 0,5).

**Umbrales nuevos de alerta e información** (Anexo I, Sección 4) — ojo, cambian respecto a los del
RD 102/2011:

| Contaminante | Alerta | Información |
|---|---|---|
| SO₂ (1 h) | 350 µg/m³ | 275 µg/m³ |
| NO₂ (1 h) | 200 µg/m³ | 150 µg/m³ |
| PM2,5 (1 día) | 50 µg/m³ | 50 µg/m³ |
| PM10 (1 día) | 90 µg/m³ | 90 µg/m³ |
| O₃ (1 h) | 240 µg/m³ | 180 µg/m³ |

### B.4 · Umbrales de evaluación (por qué importan a un modelizador)

La Directiva 2024/2881, Anexo II, sustituye los antiguos umbrales superior/inferior por un único
**umbral de evaluación** por contaminante (media anual salvo indicación): PM2,5 5; PM10 15; NO₂ 10;
SO₂ 40 µg/m³ (24 h, P99); benceno 1,7; CO 4 mg/m³ (24 h, P99); Pb 0,25 µg/m³; As 3,0; Cd 2,5; Ni 10;
B(a)P 0,30 ng/m³; O₃ 100 µg/m³ (máx. 8 h, P99).

Esto es relevante porque **por debajo del umbral la evaluación puede hacerse sólo con modelización**
(criterio heredado del art. 6.6 del RD 102/2011: «será suficiente con utilizar técnicas de
modelización»). Es el reconocimiento normativo de que un modelo como AERMOD es método de evaluación
admisible, no un mero apoyo.

---

## C. Emisiones industriales (foco) — el otro lado

Aquí se fija **cuánto puede salir por la chimenea**, que es el dato que alimenta el modelo.

### C.1 · Directiva 2010/75/UE (DEI / IED) — el marco integrado

**Directiva 2010/75/UE, de 24 de noviembre de 2010, sobre las emisiones industriales (prevención y
control integrados de la contaminación)** (DOUE L 334 de 17.12.2010).

Enfoque **integrado**: una sola autorización que considera a la vez aire, agua y suelo. Su **Anexo I**
lista las actividades sujetas, con umbrales de capacidad (p. ej. combustión ≥ 50 MW térmicos, refino,
química, gestión de residuos, cría intensiva de aves y cerdos). El art. 4 prohíbe explotar una
instalación del Anexo I sin permiso.

**El mecanismo BREF → MTD → NEA-MTD**, que es lo que de verdad fija los números:

| Concepto | Qué es (definiciones del art. 3 de la Directiva) |
|---|---|
| **MTD** (Mejores Técnicas Disponibles) | «La fase más eficaz y avanzada de desarrollo de las actividades y de sus modalidades de explotación, que demuestren la capacidad práctica de determinadas técnicas para constituir la base de los valores límite de emisión…» |
| **BREF** (documento de referencia MTD) | Documento del intercambio de información del art. 13: describe técnicas aplicadas, emisiones actuales, técnicas consideradas y conclusiones sobre MTD |
| **Conclusiones sobre las MTD** | La parte del BREF jurídicamente vinculante: incluye los niveles de emisión asociados y los requisitos de seguimiento |
| **NEA-MTD / BAT-AEL** | «El rango de niveles de emisión obtenido en condiciones normales de funcionamiento haciendo uso de una de las mejores técnicas disponibles o de una combinación…, expresada como una media durante un determinado período de tiempo» |

El **art. 15** vincula los VLE del permiso a los NEA-MTD. **Consecuencia práctica para un estudio de
dispersión:** si la instalación está bajo AAI, el caudal de emisión no se inventa — sale del BREF
sectorial y de la propia AAI. Citar el BREF aplicable es lo que hace defendible la hipótesis de emisión.

### C.2 · Directiva (UE) 2024/1785 — la «DEI 2.0» ⚠️

**Directiva (UE) 2024/1785, de 24 de abril de 2024**, que modifica la 2010/75/UE y la 1999/31/CE
(DOUE L de 15.7.2024). **Entrada en vigor: 4 de agosto de 2024.**
**Plazo de transposición (art. 4): 1 de julio de 2026** — es decir, **España está fuera de plazo o
justo en él a la fecha de este documento**; conviene verificar el estado antes de citar.

Novedades verificadas sobre el articulado:

| Novedad | Contenido |
|---|---|
| **Ganadería intensiva** | Régimen separado en un nuevo **Anexo I bis** (art. 70 bis), con umbrales en **UGM**: cerdos ≥ 350 UGM; gallinas ponedoras ≥ 300 UGM; otras aves ≥ 280 UGM; mezcla cerdos/aves ≥ 380 UGM. Se excluye la producción ecológica y la carga < 2 UGM/ha en extensivo |
| **Industria extractiva** | Nuevo punto 3.6 del Anexo I: extracción y tratamiento in situ a escala industrial de bauxita, cromo, cobalto, cobre, oro, hierro, plomo, litio, manganeso, níquel, paladio, platino, estaño, wolframio y zinc |
| **Baterías** | Nuevo punto 2.7 del Anexo I: fabricación de pilas o baterías ≥ 15.000 t/año de celdas |
| **Desempeño medioambiental** | Las conclusiones MTD incorporan **niveles vinculantes de desempeño medioambiental** (consumo, agua, energía, residuos), no sólo de emisión |
| **Sanciones (art. 79)** | Para personas jurídicas, el máximo de la sanción administrativa será **como mínimo el 3 % del volumen de negocios anual en la Unión** |
| **Indemnización (art. 79 bis)** | Cuando se produzcan **daños a la salud humana** por infracción, las personas afectadas «tengan derecho a reclamar y obtener compensación» |

El art. 79 bis es el que más debería preocupar a quien firma un estudio de dispersión: convierte una
evaluación mal hecha en un riesgo de responsabilidad civil.

### C.3 · España — el bloque IPPC

⚠️ **Corrección importante y muy frecuente en informes:** la **Ley 16/2002** de prevención y control
integrados de la contaminación **ya no está vigente**. Fue derogada expresamente por la disposición
derogatoria única del **Real Decreto Legislativo 1/2016, de 16 de diciembre**, que aprueba el **texto
refundido de la Ley de prevención y control integrados de la contaminación** (BOE núm. 316, de
31-12-2016; en vigor desde el 1-1-2017). Muchos documentos y hasta el propio **título** del RD 815/2013
siguen citando la Ley 16/2002; las referencias deben entenderse hechas al RDL 1/2016.

| Norma | Referencia | Qué hace |
|---|---|---|
| **RDL 1/2016, de 16 de diciembre** | BOE-A-2016-12601 | Texto refundido de la Ley de prevención y control integrados de la contaminación. Regula la **Autorización Ambiental Integrada (AAI)** |
| **RD 815/2013, de 18 de octubre** | BOE-A-2013-10949 (BOE 251, 19-10-2013) | **Reglamento de emisiones industriales.** Completa la transposición de la IED. Capítulos: disposiciones generales, AAI, inspección y control, incineración y coincineración, grandes instalaciones de combustión, dióxido de titanio. Modificado por RD 773/2017, RDL 36/2020 y RD 34/2023 |
| **RD 100/2011, de 28 de enero** | BOE-A-2011-1643 | Actualiza el **CAPCA** (Anexo IV de la Ley 34/2007) |
| **RD 818/2018, de 6 de julio** | BOE-A-2018-9466 | Transpone la Directiva (UE) 2016/2284 (techos nacionales, NEC). Regula el Programa Nacional de Control de la Contaminación Atmosférica (PNCCA) |

**El CAPCA y sus grupos A, B y C** (RD 100/2011, arts. 4 y 5, por remisión al art. 13 de la Ley
34/2007) — clasificación según potencial contaminador:

| Grupo | Potencial | Régimen |
|---|---|---|
| **A** | Alto | **Autorización administrativa previa** de la CCAA; los VLE se fijan en la autorización con base en las MTD |
| **B** | Medio | **Autorización administrativa previa** de la CCAA |
| **C** | Bajo | **Notificación** a la autoridad competente |

### C.4 · Instalaciones de combustión medianas (1–50 MW)

**Directiva (UE) 2015/2193, de 25 de noviembre de 2015** (DOUE L 313 de 28.11.2015), transpuesta por
el **Real Decreto 1042/2017, de 22 de diciembre** (BOE-A-2017-15368, BOE núm. 311 de 23-12-2017;
corrección de errores BOE-A-2018-3587).

Cubre el hueco que quedaba entre el CAPCA y la IED: **potencia térmica nominal ≥ 1 MW y < 50 MW**,
cualquiera que sea el combustible, pública o privada. Regula **SO₂, NOₓ y partículas**; el **CO
sólo se mide**, no tiene VLE.

| Hito | Fecha |
|---|---|
| Frontera nueva/existente | Puesta en funcionamiento antes del **20-12-2018** (o permiso anterior al 19-12-2017 con entrada en servicio ≤ 20-12-2018) → «existente» |
| VLE instalaciones **nuevas** | Desde el **20-12-2018** |
| Permiso/registro existentes **> 5 MW** | Desde el **1-1-2024** |
| **VLE existentes > 5 MW** | Desde el **1-1-2025** |
| Permiso/registro existentes **≤ 5 MW** | Desde el **1-1-2029** |
| **VLE existentes ≤ 5 MW** | Desde el **1-1-2030** |

⚠️ **Particularidad relevante:** los VLE del Anexo II de la Directiva 2015/2193 **no se aplican a las
instalaciones situadas en las Islas Canarias** (ni en los DOM franceses, Azores y Madeira); los Estados
miembros afectados fijan valores propios. Si el proyecto está en Canarias, hay que comprobar el valor
autonómico y no aplicar el europeo por defecto.

---

## D. Olores: el vacío estatal y el mapa autonómico

> **⚠️ Esta es la sección más delicada del documento y la que más se cita mal.** Circula mucha
> información secundaria errónea. Todo lo que sigue distingue explícitamente lo verificado sobre el
> texto legal de lo que no.

### D.1 · El punto de partida: no hay norma estatal

**En España no existe ninguna norma estatal que fije valores límite de olor.** El RD 102/2011 no
regula el olor ni el H₂S (verificado: cero menciones en el texto consolidado). La Ley 34/2007 sólo
contiene el mandato genérico de su art. 12.3 a las administraciones para adoptar medidas frente a
molestias — es precisamente el precepto que el decreto canario invoca como habilitación.

Consecuencia directa: **el criterio de olor aplicable a un estudio depende por completo de la
jurisdicción**. No hay un «límite español de olor» que citar.

### D.2 · Canarias — la primera CCAA con valores objetivo de inmisión de olor ✅ VERIFICADO

**Decreto 185/2025, de 10 de diciembre, de protección de la atmósfera de Canarias.**
BOC núm. 250, de 18 de diciembre de 2025 (ref. `boc-a-2025-250-4315`).
**En vigor desde el 19 de diciembre de 2025** (disposición final segunda: día siguiente al de su
publicación). **Es derecho vigente, no un borrador.**

Es, hasta donde se ha podido verificar, **la primera norma autonómica española que fija valores
objetivo numéricos de inmisión de olor**. Extracto literal del **art. 22.2**:

> «Se establecen además los siguientes valores objetivo de inmisión de olor por categorías para las
> actividades generadoras de olor: — Categoría 1: 3 UOE/m3. — Categoría 2: 6 UOE/m3. — Categoría 3:
> 9 UOE/m3. Estos valores objetivo están referidos al **percentil 98 de las medias horarias** de la
> concentración de olor a lo largo de **un año natural**.»

| Categoría | Nivel de molestia | Valor objetivo | Estadístico |
|---|---|---|---|
| **1** | Alto | **3 ou_E/m³** | P98 de medias horarias, año natural |
| **2** | Medio | **6 ou_E/m³** | P98 de medias horarias, año natural |
| **3** | Bajo | **9 ou_E/m³** | P98 de medias horarias, año natural |

**Clasificación de actividades (art. 6.2), literal:**

- **Categoría 1 (molestia alta):** gestión de residuos susceptibles de generar olor; aprovechamiento de
  subproductos de origen animal; procesos que involucren restos de animales; mataderos; fabricación de
  pasta de papel; refino de petróleo; almacenamiento de productos petrolíferos; **tratamiento de aguas
  residuales e instalaciones accesorias**.
- **Categoría 2 (media):** procesado de carne; procesos de comida para engorde; **ganadería intensiva**;
  ahumado de alimentos; tratamiento de productos orgánicos; refinado de aceite; procesos lácteos;
  procesamiento de grasas y aceites; producción de aromas y fragancias; fabricación de cerveza;
  producción de comidas para animales; industria tabaquera.
- **Categoría 3 (baja):** fabricación de chocolate o cacao; fabricación industrial de pan, masas
  diversas o galletas; confiterías; secado de productos vegetales; tostación o torrefacción de café.

El art. 6.3 y 6.4 permiten al órgano competente reclasificar por orden motivada, y encajar por analogía
las actividades no listadas.

**Otras obligaciones del decreto relevantes para un estudio:**
- **Plan de minimización** de emisiones odoríferas obligatorio para actividades susceptibles de producir
  molestias por olor (arts. 11 y 12).
- El órgano competente **puede exigir «un estudio específico de emisión y de dispersión de olores»**
  (arts. 11.3 y 12.2). **Este es el gancho normativo directo para un estudio con AERMOD.**
- **Registro de quejas por olor** a disposición de la administración (art. 32).
- **Metodología (art. 42):** para emisión, la norma UNE vigente de olfatometría dinámica (UNE-EN 13725);
  para inmisión, normas UNE vigentes «y en su defecto se podrá utilizar cualquier técnica reconocida
  internacionalmente que permita verificar el cumplimiento de los valores objetivo de inmisión de olor,
  debiendo en este último caso demostrarse la validez de la técnica». **Esa cláusula es la que abre la
  puerta a acreditar el cumplimiento mediante modelización de dispersión.**
- Art. 22.1: valor objetivo de **partículas sedimentables 300 mg/m²·día** (media del periodo de muestreo).

> **Encaje con la herramienta:** el criterio canario —P98 de medias horarias sobre un año natural—
> es exactamente el estadístico que exige **un año meteorológico completo** de simulación. Con un
> periodo más corto el percentil no es defendible.

### D.3 · Andalucía — habilitación, pero SIN valores numéricos ✅ VERIFICADO

**Decreto 239/2011, de 12 de julio**, por el que se regula la calidad del medio ambiente atmosférico
y se crea el Registro de Sistemas de Evaluación de la Calidad del Aire en Andalucía
(BOJA núm. 152, de 4 de agosto de 2011).

Su **art. 19 («Actividades que produzcan olores»)** habilita al órgano ambiental competente a
**requerir** a los titulares que evalúen la incidencia de los olores y elaboren un estudio que
identifique y cuantifique las sustancias generadoras de molestias, así como a implantar medidas
correctoras.

**No fija ningún valor límite en ou_E/m³ ni percentil alguno.** Verificado sobre el texto del BOJA.

⚠️ **Aviso sobre fuentes:** múltiples fuentes secundarias (consultoras, medios, portales jurídicos)
afirman que «la única comunidad autónoma con una ley que regule la contaminación odorífera es
Andalucía, con el Decreto 239/2013 de 12 de julio». **Esa afirmación contiene dos errores**: el decreto
es de **2011**, no de 2013, y **no regula valores de olor**, sólo habilita a pedir estudios. No debe
reproducirse.

### D.4 · Cataluña — pionera, pero nunca aprobada ⚠️

Cataluña elaboró en **2005** un **anteproyecto de ley contra la contaminación odorífera**, con un
borrador que volvió a circular hacia **2015**. Su objeto declarado era regular las medidas para
prevenir y corregir la contaminación odorífera y establecer el régimen de intervención administrativa,
y remitía a la **UNE-EN 13725** para la medición de las unidades de olor de las emisiones.

**Nunca fue aprobado. No es derecho vigente.** Sin embargo, su Anexo 3 (valores objetivo de inmisión
por tipo de actividad) se ha usado *de facto* como referencia técnica por consultoras y ha sido copiado
por algunas ordenanzas municipales (p. ej., se documenta que la ordenanza de San Pedro del Pinatar,
Murcia, incorpora la tabla del borrador catalán).

⚠️ **No se ha podido verificar la tabla numérica del Anexo 3 sobre el texto del borrador.** Por eso
**este documento no reproduce sus cifras**. Si un informe necesita citarlas, hay que localizar el
borrador original y verificarlas — y en todo caso advertir de que se trata de un texto sin valor
normativo.

### D.5 · Nivel municipal — el modelo de ordenanza de la Diputació de Barcelona ✅ VERIFICADO

**Modelo de Ordenanza tipo reguladora de contaminación odorífera**, Diputació de Barcelona,
Boletín Oficial de la Provincia de Barcelona de 29-04-2024 (CVE 202410081250).

Es un modelo para que los ayuntamientos lo adopten; su valor jurídico nace cuando un municipio lo
aprueba. Interesa porque **su criterio es de naturaleza distinta al canario** y no es directamente
comparable:

**Anexo II — valores límite de inmisión** (literal):
1. **Zonas urbanas residenciales:** se superan cuando una emisión olorosa genera una inmisión
   **superior a 5 ou_E/m³ de media durante 30 minutos seguidos** en 2 días diferentes a lo largo de
   7 días consecutivos, o bien en 4 días diferentes a lo largo de 30 días consecutivos.
2. **Viviendas en zonas rurales:** lo mismo con **60 minutos seguidos** en lugar de 30.

**Metodología (art. 8 y Anexo I): olfatometría dinámica de campo**, no modelización. Cita la
**UNE-EN 16841-2** para las medidas de campo. Define la unidad conforme a UNE-EN 13725: 1 ou_E ≡ 123 µg
de n-butanol evaporados en 1 m³ de gas neutro ≡ 0,04 µmol/mol (40 ppbv). Disposición transitoria: un
año de adaptación para actividades existentes.

> **⚠️ Aviso metodológico importante.** El criterio de la Diba se basa en **medias de 30/60 minutos
> medidas en campo con frecuencia de repetición**, mientras que el canario se basa en el **P98 de medias
> horarias modelizadas en un año**. **No son intercambiables.** Un resultado de AERMOD no acredita
> directamente el cumplimiento de un criterio de olfatometría de campo, y viceversa. Si el marco
> aplicable es una ordenanza tipo Diba, hay que decir explícitamente en el informe que la modelización
> es una estimación complementaria, no la verificación normativa.

### D.6 · Resto de CCAA — lo que se ha podido y no se ha podido establecer

| CCAA | Situación | Estado de verificación |
|---|---|---|
| **Canarias** | Decreto 185/2025 con valores objetivo (3/6/9 ou_E/m³, P98 horario anual) | ✅ Verificado sobre el BOC |
| **Andalucía** | Decreto 239/2011, art. 19: habilita a exigir estudios, sin valores | ✅ Verificado sobre el BOJA |
| **Cataluña** | Anteproyecto de 2005/2015, **nunca aprobado**; ordenanzas municipales | ⚠️ Estado verificado; tabla numérica NO verificada |
| **Cataluña (municipal)** | Modelo de ordenanza Diba (BOPB 29-04-2024), 5 ou_E/m³ 30/60 min | ✅ Verificado |
| **Murcia** | Sin norma autonómica específica localizada. Ordenanzas municipales citadas: Alcantarilla (zonificación por saturación de olor), San Pedro del Pinatar (adopta la tabla del borrador catalán) | ⚠️ Sólo fuente secundaria; textos NO verificados |
| **País Vasco** | **No fija valores numéricos de olor**, pero **sí regula cómo se hacen los controles y las modelizaciones** — ver D.6 bis | ✅ Verificado sobre la sede euskadi.eus |
| **Galicia** | No se ha localizado norma autonómica de olores | ⚠️ No verificado |
| **Aragón** | No se ha localizado norma autonómica de olores | ⚠️ No verificado |
| **Comunidad Valenciana** | Se cita un intento de norma que no prosperó y alguna ordenanza municipal | ⚠️ Sólo fuente secundaria |

**Advertencia:** la ausencia de resultados **no equivale a la inexistencia de norma**. El presupuesto de
búsqueda de esta vigilancia se agotó antes de poder barrer boletines autonómicos uno a uno. Para un
informe real hay que **consultar el boletín de la CCAA concreta**.

### D.6 bis · País Vasco — no fija valores, pero sí obliga a modelizar de una forma concreta ✅ VERIFICADO

Hallazgo especialmente relevante para esta herramienta. La sede oficial euskadi.eus, en las
instrucciones técnicas para instalaciones con actividades potencialmente contaminadoras de la
atmósfera, establece (nota `03_IT-02_v0`, cita literal):

> «**Controles reglamentarios de emisión de olores**: Deben ser realizados por ECAs inscritas en el
> Registro del **Decreto 212/2012, de 16 de octubre**. Se realizarán con la norma UNE-EN 13275 y de
> conformidad con las instrucciones técnicas de la **Orden de 11 de julio de 2012**. **Las
> modelizaciones se deben realizar de acuerdo con la Guía de Buenas Prácticas para la elaboración de
> modelos de dispersión**.»

Tres consecuencias prácticas:
1. Los controles de emisión de olor **sólo son válidos si los hace una ECA inscrita** en el registro del
   Decreto 212/2012. Un dato de olfatometría de un laboratorio no inscrito no sirve en el País Vasco.
2. **La modelización está expresamente sujeta a una guía metodológica autonómica.** Si se hace un
   estudio para el País Vasco, **hay que obtener y seguir esa «Guía de Buenas Prácticas para la
   elaboración de modelos de dispersión»** — es probablemente el documento autonómico más directamente
   aplicable a esta herramienta que se ha localizado.
3. **No se han localizado valores objetivo de inmisión de olor** en esta fuente.

⚠️ La página oficial escribe «**UNE-EN 13275**», que **parece una errata** por **UNE-EN 13725** (la norma
de olfatometría dinámica). Se reproduce aquí tal cual figura en la fuente, pero conviene no propagar el
número erróneo.

⚠️ **No se ha obtenido el texto de la Guía de Buenas Prácticas ni el de la Orden de 11 de julio de 2012**;
sólo la referencia a ambas. Localizar la Guía es una tarea pendiente de alta prioridad.

### D.7 · La norma técnica: UNE-EN 13725:2022

**UNE-EN 13725:2022 — «Emisiones de fuentes estacionarias. Determinación de la concentración de olor por
olfatometría dinámica y de la tasa de emisión de olor».** Publicada el **26 de octubre de 2022**;
**sustituye a la UNE-EN 13725:2004**, que queda anulada.

Es **la** referencia: define la unidad de olor europea (ou_E), el método de olfatometría dinámica con
panel humano, los requisitos de los evaluadores y del olfatómetro, el muestreo y el aseguramiento de
la calidad.

**Novedad clave de la revisión de 2022 para un modelizador:** el título y el alcance incorporan
explícitamente **la tasa de emisión de olor** y cubren **focos puntuales (canalizados), fuentes de área
activas (p. ej. biofiltros) y fuentes pasivas**. Esto importa mucho aquí: da cobertura normativa al
tratamiento de una balsa de EDAR o una pila de compostaje como **fuente de área** (AREAPOLY), que es
justo lo que la herramienta modeliza. La versión de 2003/2004 se centraba en la concentración y dejaba
la tasa de emisión de superficies mucho menos definida.

Trabaja conjuntamente con **EN 15259** (mediciones en conductos) y **EN ISO 16911-1** (velocidad y
caudal). Para medidas de olor en aire ambiente se emplea la serie **EN 16841** (la ordenanza Diba cita
la parte 2).

---

## E. Cuándo es obligatorio modelar

No existe un precepto que diga «hágase un estudio de dispersión». La obligación aparece **por vías
indirectas**, y hay que identificar cuál aplica al caso.

### E.1 · Evaluación de impacto ambiental — Ley 21/2013

**Ley 21/2013, de 9 de diciembre, de evaluación ambiental** (BOE-A-2013-12913; BOE núm. 296 de
11-12-2013; en vigor desde el 12-12-2013).

Establece dos procedimientos: **EIA ordinaria** (proyectos del **Anexo I**) y **EIA simplificada**
(proyectos del **Anexo II**, que puede derivar en ordinaria si el informe de impacto ambiental así lo
determina).

El **art. 5.1.a)** incluye expresamente **el aire** entre los factores sobre los que hay que evaluar los
efectos significativos («el aire, el agua, el clima, el cambio climático…»). El estudio de impacto
ambiental debe «identificar, describir, cuantificar y analizar los posibles efectos significativos sobre
el medio ambiente».

**La palabra «cuantificar» es la clave.** Cuando el impacto relevante es la dispersión de un
contaminante o de olor, no hay forma razonable de cuantificarlo sin un modelo. De ahí que, en la
práctica administrativa, los órganos ambientales exijan el estudio de dispersión en el trámite de
alcance o en el requerimiento de subsanación, aunque la ley no lo nombre.

⚠️ **No se ha verificado** si el Anexo VI de la Ley 21/2013 (contenido del estudio de impacto ambiental)
menciona literalmente la modelización de dispersión. Ver apartado H.

⚠️ Cada CCAA tiene además **su propia normativa de evaluación ambiental**, que puede añadir supuestos
y contenidos. Hay que comprobarla siempre.

### E.2 · Autorización Ambiental Integrada (AAI)

Regulada por el **RDL 1/2016** y el **RD 815/2013**. Aplica a las instalaciones del Anexo I de la IED.
La AAI fija los VLE con base en los NEA-MTD del BREF sectorial (art. 15 de la Directiva 2010/75/UE).

En la práctica, la solicitud de AAI y sus modificaciones sustanciales suelen requerir justificar que
las emisiones **no comprometen los objetivos de calidad del aire** en el entorno — lo que remite a una
evaluación de inmisión, y por tanto a un modelo.

### E.3 · Autorización de emisiones a la atmósfera (CAPCA)

**RD 100/2011**: las actividades de los **grupos A y B** requieren autorización previa de la CCAA, en
la que se fijan los VLE con base en las MTD; las del **grupo C** sólo notificación. Es el cauce típico
para focos que no llegan al umbral de la IED.

### E.4 · La vía autonómica — el caso canario, que sí lo dice expresamente

El **Decreto 185/2025 de Canarias** es el ejemplo más explícito encontrado: sus **arts. 11.3 y 12.2**
habilitan al órgano competente a **exigir «un estudio específico de emisión y de dispersión de
olores»**, y su art. 42.2 admite acreditar el cumplimiento de los valores objetivo de inmisión mediante
técnicas reconocidas internacionalmente cuya validez se demuestre. Además, el art. 7 somete a
autorización las actividades de los grupos A y B del CAPCA no sujetas a AAI.

### E.5 · La modelización como método de evaluación reconocido

Esto es lo que legitima el uso de un modelo, y conviene citarlo en el informe:

- **RD 102/2011, art. 6.3:** la evaluación se realizará «utilizando mediciones fijas, técnicas de
  modelización, campañas de mediciones representativas, mediciones indicativas o investigaciones, o una
  combinación de todos o algunos de estos métodos».
- **RD 102/2011, art. 6.5:** entre umbral inferior y superior de evaluación, «podrá utilizarse una
  combinación de mediciones fijas y técnicas de modelización».
- **RD 102/2011, art. 6.6:** por debajo del umbral inferior, «**será suficiente con utilizar técnicas de
  modelización** para la evaluación de la calidad del aire ambiente».
- **Directiva (UE) 2024/2881:** refuerza el papel de las «aplicaciones de modelización», les fija
  objetivos de calidad cuantitativos (Anexo V) y prevé actos de ejecución sobre ellas.

### E.6 · Licencia de actividad municipal

La licencia o comunicación previa municipal puede exigir documentación adicional, y la ordenanza local
(p. ej. de olores) puede imponer criterios propios. Es el escalón que más se olvida.

---

## F. Qué implica todo esto para un informe

Lista práctica. Esto es lo que debería comprobarse antes de dar por cerrado un estudio.

### F.1 · Lo primero: fijar la jurisdicción

**Antes de elegir un límite, hay que saber qué normativa aplica.** El orden de comprobación es:

1. ¿Hay **ordenanza municipal** aplicable? (sobre todo en olores)
2. ¿Hay **norma autonómica** con valores propios? (en olores, es casi la única fuente)
3. ¿Qué dice la **norma estatal**? (RD 102/2011 para inmisión de masa)
4. ¿Y la **Directiva**, con su horizonte 2030?

### F.2 · Qué estadístico usar, según el caso

| Caso | Estadístico | Límite de comparación | Periodo mínimo de simulación |
|---|---|---|---|
| **Olor, marco canario** | **P98 de medias horarias** | 3 / 6 / 9 ou_E/m³ según categoría | **Año natural completo** — el percentil no es defendible con menos |
| **Olor, ordenanza tipo Diba** | Medias de 30 min (urbano) / 60 min (rural) + frecuencia | 5 ou_E/m³ | ⚠️ Criterio de olfatometría de campo: la modelización es complementaria |
| **SO₂, NO₂ — corto plazo** | Máximo horario y nº de superaciones | Ver tabla B.1 / B.2 | Año completo (hacen falta las superaciones) |
| **NO₂, PM, benceno — largo plazo** | Media del periodo (anual) | Ver tabla B.1 / B.2 | Año completo |
| **CO** | Máxima diaria de las medias móviles octohorarias | 10 mg/m³ | Año completo |
| **PM10 / PM2,5** | Media diaria (con superaciones) y media anual | Ver tabla B.1 / B.2 | Año completo |
| **Partículas sedimentables (Canarias)** | Media del periodo de muestreo | 300 mg/m²·día | — |

> **⚠️ El punto que más informes suspende:** AERMOD entrega **medias horarias** y medias del periodo.
> El percentil, la media móvil octohoraria, el recuento de superaciones y el **factor pico-media** de
> los estudios de olor se calculan **por fuera del modelo**. Si el informe no explica esa
> transformación, el número no es trazable.

### F.3 · Objetivos de calidad de la modelización — el criterio de aceptación

Esto rara vez se cita y es lo que diferencia un informe defendible de uno opinable.

**Vigente — RD 102/2011, Anexo V (incertidumbre máxima de la modelización):**

| Promediado | SO₂, NO₂, NOₓ, CO | Benceno | PM y plomo |
|---|---|---|---|
| Medias horarias | 50 % | — | — |
| Medias octohorarias | 50 % | — | — |
| Medias diarias | 50 % | — | *Sin definir por el momento* |
| Medias anuales | 30 % | 50 % | 50 % |

**Futuro — Directiva (UE) 2024/2881, Anexo V.** Cambia el enfoque: en lugar de un porcentaje absoluto,
fija la **relación máxima entre la incertidumbre de la modelización y la de las mediciones fijas**.

*Medias anuales (Cuadro 1)* — incertidumbre máx. de la medición fija | relación máx. modelización:

| Contaminante | Valor absoluto | Valor relativo | Relación máx. |
|---|---|---|---|
| PM2,5 | 3,0 µg/m³ | 30 % | **1,7** |
| PM10 | 4,0 µg/m³ | 20 % | **1,3** |
| SO₂ / NO₂ / NOₓ | 6,0 µg/m³ | 30 % | **1,4** |
| Benceno | 0,85 µg/m³ | 25 % | **1,7** |
| Plomo | 0,125 µg/m³ | 25 % | **1,7** |

*Corto plazo (Cuadro 2):*

| Contaminante | Valor absoluto | Valor relativo | Relación máx. |
|---|---|---|---|
| PM2,5 (24 h) | 6,3 µg/m³ | 25 % | 2,5 |
| PM10 (24 h) | 11,3 µg/m³ | 25 % | 2,2 |
| NO₂ (24 h) | 7,5 µg/m³ | 15 % | 3,2 |
| **NO₂ (horaria)** | **30 µg/m³** | 15 % | **3,2** |
| SO₂ (24 h) | 7,5 µg/m³ | 15 % | 3,2 |
| **SO₂ (horaria)** | **52,5 µg/m³** | 15 % | **3,2** |
| CO (24 h) | 0,6 mg/m³ | 15 % | 3,2 |
| CO (8 h) | 1,0 mg/m³ | 10 % | 4,9 |
| O₃ (8 h) | 18 µg/m³ | 15 % | 2,2 |

La Directiva añade que, cuando se use un modelo, «se reunirán referencias a las descripciones de la
aplicación de modelización e información sobre el cálculo del objetivo de calidad de la modelización».
**Traducción: hay que documentar el modelo y justificar que cumple el objetivo de calidad.**

### F.4 · Qué hay que citar sí o sí

- **Inmisión de masa:** RD 102/2011, Anexo I (valor vigente) **y** Directiva (UE) 2024/2881, Anexo I,
  Cuadro 1 (horizonte 2030). Citar sólo el vigente deja el informe corto de vida.
- **Olor:** la norma **autonómica o municipal concreta**, nunca «la normativa española de olores»
  (no existe). Y la **UNE-EN 13725:2022** como base metodológica.
- **Emisión:** el **BREF/conclusiones MTD** del sector si hay AAI, o la autorización de emisiones.
- **Legitimación del método:** art. 6 del RD 102/2011.
- **Criterio de aceptación:** Anexo V del RD 102/2011 y/o de la Directiva 2024/2881.

### F.5 · Lo que hay que declarar como hipótesis (y no dar por sabido)

Coherente con lo que ya recoge el README de esta carpeta:

1. **De dónde sale el caudal Q** — es la mayor fuente de error. Si viene de olfatometría, indicar
   norma (UNE-EN 13725:2022), laboratorio y fecha.
2. **La altura de emisión.**
3. **El periodo meteorológico** — y que sea **un año completo** si se usan percentiles o superaciones.
4. **La traducción CORINE → NLCD** del uso del suelo: es un juicio técnico, no un dato.
5. **El umbral olfativo** empleado, si es un estudio de olor.
6. **El factor pico-media** y su formulación, si se compara con criterios de corta duración.
7. **La limitación de AREAPOLY a 20 vértices**: si el contorno real se ha simplificado, decirlo.

---

## G. Fuentes

Todas consultadas el **21 de julio de 2026**. Se indica entre corchetes el método de verificación.

### Unión Europea

| Norma | URL | Verificación |
|---|---|---|
| Directiva (UE) 2024/2881, calidad del aire ambiente (refundición) | https://www.boe.es/buscar/doc.php?id=DOUE-L-2024-81722 · PDF oficial: https://www.boe.es/doue/2024/2881/L00001-00070.pdf | ✅ PDF descargado y texto extraído íntegramente; Anexos I, II y V citados literalmente |
| Directiva (UE) 2024/2881 (ficha EUR-Lex) | https://eur-lex.europa.eu/legal-content/es/ALL/?uri=CELEX:32024L2881 | ⚠️ EUR-Lex devolvió contenido vacío de forma sistemática (ver H) |
| Directiva 2010/75/UE (DEI/IED) | https://www.boe.es/doue/2010/334/L00017-00119.pdf · https://eur-lex.europa.eu/legal-content/ES/TXT/?uri=CELEX:32010L0075 | ✅ Definiciones del art. 3 citadas literalmente |
| Directiva (UE) 2024/1785 (DEI 2.0) | https://www.boe.es/doue/2024/1785/L00001-00047.pdf · ficha: https://www.boe.es/buscar/doc.php?id=DOUE-L-2024-81092 | ✅ Art. 4 (transposición) y Anexos citados literalmente |
| Directiva (UE) 2015/2193 (combustión mediana) | https://www.boe.es/doue/2015/313/L00001-00019.pdf | ✅ Arts. 1, 2, 3, 5, 6 y 17 verificados |
| Directiva (UE) 2016/2284 (NEC) | https://www.boe.es/doue/2016/344/L00001-00031.pdf | ✅ Art. 17 verificado |
| MITECO — normativa europea de calidad del aire | https://www.miteco.gob.es/es/calidad-y-evaluacion-ambiental/temas/atmosfera-y-calidad-del-aire/normativa-calidad-del-aire/normativa-europea.html | ✅ Consultada |

### España — Estado

| Norma | URL | Verificación |
|---|---|---|
| Ley 34/2007, calidad del aire y protección de la atmósfera | https://www.boe.es/buscar/act.php?id=BOE-A-2007-19744 | ✅ Referencia confirmada |
| **RD 102/2011**, mejora de la calidad del aire | https://www.boe.es/buscar/act.php?id=BOE-A-2011-1645 · consolidado PDF: https://www.boe.es/buscar/pdf/2011/BOE-A-2011-1645-consolidado.pdf | ✅ PDF consolidado descargado; **Anexo I y Anexo V citados literalmente** |
| RDL 1/2016, texto refundido de la Ley de prevención y control integrados de la contaminación | https://www.boe.es/buscar/act.php?id=BOE-A-2016-12601 | ✅ Disposición derogatoria única citada literalmente |
| RD 815/2013, Reglamento de emisiones industriales | https://www.boe.es/buscar/act.php?id=BOE-A-2013-10949 | ✅ Verificado |
| RD 100/2011, catálogo CAPCA | https://www.boe.es/buscar/act.php?id=BOE-A-2011-1643 | ✅ Arts. 4 y 5 verificados |
| RD 1042/2017, instalaciones de combustión medianas | https://www.boe.es/buscar/act.php?id=BOE-A-2017-15368 · corrección: https://www.boe.es/buscar/doc.php?id=BOE-A-2018-3587 | ✅ Arts. 1 y 2 y fechas verificados |
| RD 818/2018, reducción de emisiones nacionales (NEC) | BOE-A-2018-9466 | ⚠️ Identificador tomado de la página oficial de MITECO; ficha BOE no abierta directamente |
| Ley 21/2013, de evaluación ambiental | https://www.boe.es/buscar/act.php?id=BOE-A-2013-12913 | ✅ Denominación, fechas y art. 5.1.a) verificados |
| MITECO — normativa española de calidad del aire | https://www.miteco.gob.es/es/calidad-y-evaluacion-ambiental/temas/atmosfera-y-calidad-del-aire/normativa-calidad-del-aire/normativa-espanola.html | ✅ Consultada (cita RD 34/2023 como modificación del RD 102/2011) |
| MITECO — iniciativas nacionales sobre emisiones | https://www.miteco.gob.es/en/calidad-y-evaluacion-ambiental/temas/emisiones-a-la-atmosfera/normativa-en-relacion-con-emisiones-a-la-atmosfera/iniciativas_nacionales.html | ✅ Consultada |
| MITECO — consulta pública previa, transposición DEI 2.0 | https://www.miteco.gob.es/en/calidad-y-evaluacion-ambiental/participacion-publica/consulta-publica-previa-sobre-la-transposicion-de-la-directiva--.html | ✅ Consultada |

### Comunidades autónomas y municipal

| Norma | URL | Verificación |
|---|---|---|
| **Decreto 185/2025 de Canarias**, protección de la atmósfera | Índice BOC 250: https://www.gobiernodecanarias.org/boc/2025/250/ · PDF: https://sede.gobiernodecanarias.org/boc/boc-a-2025-250-4315.pdf | ✅ PDF oficial descargado; **arts. 6, 22 y 42 y disposición final citados literalmente** |
| Decreto 239/2011 de Andalucía, calidad del medio ambiente atmosférico | https://www.juntadeandalucia.es/boja/2011/152/5 | ✅ Art. 19 verificado |
| Modelo de ordenanza reguladora de contaminación odorífera, Diputació de Barcelona (BOPB 29-04-2024) | https://www.diba.cat/documents/d/mediambient/bopb_modelo_ordenanza_reguladora_contaminacion_odorifera_diba | ✅ PDF descargado; arts. 7-9 y Anexos I-II citados literalmente |
| Anteproyecto catalán de ley contra la contaminación odorífera (referencia secundaria) | https://www.eurofins-environment.es/es/borrador-del-anteproyecto-de-ley-contra-la-contaminacion-odorifera-en-cataluna/ | ⚠️ Fuente secundaria; tabla numérica NO obtenida |
| Panorama de normativa de olores en España (referencia secundaria) | https://olores.org/index.php?option=com_content&view=article&id=25&lang=es | ⚠️ Fuente secundaria y desactualizada (anterior al decreto canario) |
| **País Vasco** — instrucciones técnicas para actividades potencialmente contaminadoras de la atmósfera | https://www.euskadi.eus/informazioa/instrucciones-tecnicas-para-las-instalaciones-donde-se-desarrollan-actividades-potencialmente-contaminadoras-de-la-atmosfera/web01-a2ingair/es/ | ✅ Nota `03_IT-02_v0` citada literalmente (controles de olor y obligación de seguir la Guía de modelos de dispersión) |

### Normalización

| Norma | URL | Verificación |
|---|---|---|
| UNE-EN 13725:2022, olfatometría dinámica y tasa de emisión de olor | https://www.en.une.org/encuentra-tu-norma/busca-tu-norma/norma?c=norma-une-en-13725-2022-n0070408 | ✅ Título, fecha (26-10-2022) y alcance confirmados |
| Nota sobre la publicación de la UNE-EN 13725:2022 | https://www.olores.org/es/tecnicas/olfatometria-dinamica/1264-publicada-la-norma-une-en-13725-2022-el-26-de-octubre | ✅ Consultada (confirma sustitución de la UNE-EN 13725:2004) |

---

## H. Incertidumbres y avisos

### H.1 · Contradicciones entre fuentes detectadas (importantes)

1. **«Andalucía es la única CCAA con ley de contaminación odorífera, Decreto 239/2013».** ❌ **Falso por
   partida doble.** El decreto es el **239/2011, de 12 de julio** (BOJA 152 de 4-8-2011) y su art. 19
   **no fija valores de olor**, sólo habilita a exigir estudios. Verificado sobre el BOJA. Esta
   afirmación errónea aparece replicada en varias fuentes secundarias y no debe reproducirse.
2. **«La Ley 16/2002 de prevención y control integrados de la contaminación está vigente».** ❌ **Falso.**
   Fue derogada expresamente por la disposición derogatoria única del **RDL 1/2016**, en vigor desde el
   1-1-2017. El equívoco persiste porque el **título del RD 815/2013 sigue citándola**.
3. **«El RD 1/2016 transpone la Directiva NEC».** ❌ **Falso.** La NEC (Directiva (UE) 2016/2284) se
   transpone por el **RD 818/2018**. El «1/2016» es el RDL 1/2016, que es materia distinta (IPPC).
4. **Valores límite de olor «entre 3 y 5 ou_E al percentil 98»** citados genéricamente como si fueran
   norma española. Sólo se ha verificado el rango **3/6/9 ou_E/m³ al P98** del decreto canario. El resto
   no está verificado y **no debe presentarse como norma**.

### H.2 · Lo que NO se ha podido verificar

| Punto | Estado |
|---|---|
| **Tabla numérica del Anexo 3 del anteproyecto catalán** de ley de contaminación odorífera | ❌ **No localizada.** Por eso este documento **no reproduce ninguna cifra** del borrador catalán |
| **Normativa de olores de Murcia, Aragón, Galicia, País Vasco y Comunidad Valenciana** | ❌ **No verificada.** Sólo referencias secundarias. La ausencia de hallazgos **no prueba la inexistencia**: el presupuesto de búsqueda se agotó |
| **Guía de Buenas Prácticas para la elaboración de modelos de dispersión** (País Vasco) y **Orden de 11 de julio de 2012** | ⚠️ **Existencia verificada** en la sede euskadi.eus (ver D.6 bis), pero **no se ha obtenido el texto de ninguna de las dos**. Prioridad alta: la Guía es el documento autonómico más directamente aplicable a esta herramienta |
| **Anexo VI de la Ley 21/2013** (contenido del estudio de impacto ambiental): si menciona literalmente la modelización de dispersión | ❌ No verificado |
| **Umbrales concretos de los Anexos I y II de la Ley 21/2013** (plazas ganaderas, habitantes equivalentes de EDAR, t/día de vertedero) | ❌ **No verificados. No se citan cifras** para evitar inventarlas |
| **Ficha BOE del RD 818/2018** | ⚠️ El identificador BOE-A-2018-9466 procede de la página oficial de MITECO, no de la ficha BOE abierta directamente |
| **RD 34/2023**, que modifica el RD 102/2011 | ⚠️ Citado por MITECO y por la ficha de modificaciones del RD 815/2013. **No se ha localizado su identificador BOE.** El texto consolidado del RD 102/2011 empleado sí incorpora los umbrales de activación/información/alerta de PM10 y PM2,5, coherente con esa reforma |
| **Lista completa de modificaciones del RD 100/2011** | ⚠️ Incompleta |
| **Fechas transitorias adicionales de la Directiva (UE) 2024/1785** (sistema de gestión ambiental, planes de transformación, permisos electrónicos) | ⚠️ Aparecen en resúmenes automáticos pero **no confirmadas contra el articulado**. El único plazo confirmado literalmente es el del art. 4: **1 de julio de 2026** |
| **Calendario de aplicación del nuevo régimen ganadero** (art. 70 bis / Anexo I bis de la DEI 2.0) | ❌ No verificado |
| **Compromisos de reducción de España** del Anexo II de la Directiva 2016/2284 | ❌ No extraídos |
| **Número exacto de anexos del RD 815/2013** | ⚠️ Las fuentes discrepan entre cuatro y cinco |

### H.3 · En tramitación — puede cambiar

- ⚠️ **Transposición española de la Directiva (UE) 2024/2881.** Plazo: **11 de diciembre de 2026**. A
  fecha de consulta, la página oficial de MITECO **no anuncia ningún proyecto de real decreto** para
  transponerla. **Cuando se apruebe, la tabla B.1 de este documento quedará obsoleta.** Es el punto que
  antes envejecerá.
- ⚠️ **Transposición de la Directiva (UE) 2024/1785 (DEI 2.0).** Plazo: **1 de julio de 2026** — ya
  vencido o inmediato a la fecha de este documento. MITECO abrió consulta pública previa. **Verificar el
  estado antes de citar.**
- ⚠️ **Actos de ejecución de la Comisión sobre «aplicaciones de modelización»** previstos en la
  Directiva 2024/2881. Cuando se publiquen, fijarán requisitos técnicos concretos para estudios como los
  de esta herramienta. **Es lo más relevante que está por venir para este proyecto.**
- ⚠️ **Revisión de las normas de calidad del aire de la UE** prevista para 2030 y después cada cinco años.

### H.4 · Dudas concretas sobre valores

- ⚠️ **PM2,5, valor límite anual en España.** El RD 102/2011 fija una «fase II» de **20 µg/m³** desde el
  1-1-2020, pero el propio Anexo I la acompaña de una nota que la califica de **«valor límite indicativo
  que deberá ratificarse como valor límite en 2013»**. Además, el Cuadro 2 de la Directiva 2024/2881
  (régimen transitorio hasta 2030) fija **25 µg/m³**. Hay por tanto una **discrepancia entre el valor
  español (20) y el mínimo europeo transitorio (25)**. Lo prudente en un informe es **comparar contra
  20 µg/m³** (el más estricto y el que figura en la norma española) y **declarar expresamente la nota**.
  **Conviene confirmar este punto con el órgano ambiental competente.**
- ⚠️ **Ozono: número de días de superación.** El RD 102/2011 admite **25 días/año** promediados en 3
  años; la Directiva 2024/2881 lo reduce a **18 días** (exigible a más tardar el 11-12-2026). Es un
  cambio que ya está en el horizonte inmediato.
- ⚠️ **H₂S.** Verificado que **el RD 102/2011 no lo regula** (cero menciones en el texto consolidado).
  **No se han verificado** valores guía de la OMS ni límites autonómicos, por lo que **este documento no
  ofrece ninguna cifra para H₂S**. Si un estudio de EDAR o vertedero necesita un criterio de H₂S, hay
  que buscarlo y verificarlo específicamente para la jurisdicción del caso.

### H.5 · Limitaciones metodológicas de esta vigilancia

- **EUR-Lex devolvió sistemáticamente contenido vacío** por vía HTML y HTTP 202 por descarga directa.
  Se resolvió usando los **PDF oficiales del DOUE espejados en el BOE** (`boe.es/doue/…`) y extrayendo
  el texto localmente, lo que permitió **citar el articulado literalmente**. Es la ruta recomendada para
  futuras consultas.
- **El presupuesto de búsquedas web de la sesión se agotó (200/200)** antes de completar el barrido de
  boletines autonómicos en materia de olores. La sección D queda por tanto **completa en lo verificado
  pero incompleta en cobertura territorial**.
- Los valores de las tablas B.1, B.2, F.3 y del apartado D.2 proceden de **extracción directa del texto
  legal**, no de fuentes secundarias ni de memoria.
