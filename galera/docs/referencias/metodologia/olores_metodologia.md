---
tipo: metodologia
contaminantes: [ou_E]
estadistico: percentil
ambito: España + UE
anio: 2026
origen: vigilancia tecnológica
---

# Metodología de estudios de olor — de la media horaria al criterio

> AERMOD entrega **medias horarias** de `ou_E/m³`; los criterios normativos se expresan en
> **percentiles de picos de segundos**. Entre una cosa y la otra hay tres operaciones que el modelo
> **no** hace y que decide el técnico: caracterizar la emisión por olfatometría, aplicar un
> **factor pico-media**, y calcular el **percentil sobre un año completo**. Este documento
> describe esas tres operaciones, sus fórmulas verificadas y los errores que se cometen en cada una.

**Normativa — no se repite aquí.** Ver:
- [`../normativa/marco_normativo_ES_UE.md`](../normativa/marco_normativo_ES_UE.md) — marco español
  y europeo, incluido el **Decreto 185/2025 de Canarias** (3/6/9 ou_E/m³ al P98 anual de medias horarias).
- [`../normativa/criterios_olor_internacional.md`](../normativa/criterios_olor_internacional.md) —
  Países Bajos e Italia sobre norma primaria (factor pico-media italiano 2,3; derogación neerlandesa 1/1/2024).

---

## A. La unidad de olor y la olfatometría

### A.1 Qué es una `ou_E`

La unidad de olor europea se define **por dilución, no por química**: 1 ou_E/m³ es la concentración
a la que el 50 % de un panel humano cualificado distingue la muestra del aire de referencia. La
concentración de olor de una muestra es el número de diluciones necesario para llevarla a ese
umbral. Es por tanto una **magnitud sensorial medida con un instrumento biológico** (el panel),
calibrado con **n-butanol** como referencia.

Consecuencia práctica inmediata: `ou_E` **no es aditiva con la química**. No se puede calcular la
concentración de olor sumando contribuciones de compuestos (ver A.4).

### A.2 EN 13725 y la revisión de 2022

La norma es **EN 13725** (olfatometría dinámica). La versión de 2003 fue sustituida por
**EN 13725:2022**. Los cambios más citados por los laboratorios:

| Aspecto | Cambio en la versión 2022 |
|---|---|
| Materiales | Se revisan los materiales admisibles del equipo; el caucho sigue prohibido |
| Condiciones ambientales | Se acota la sala de análisis: temperatura de consigna **> 21 °C** con tolerancia estrecha, y **humedad relativa 20–80 %** |
| Muestreo | Recomendaciones más detalladas de toma, almacenamiento y manipulación de muestras; pre-dilución |
| Calidad | Requisitos ampliados de control de calidad, validación del método e incertidumbre |
| Seguridad | Se añade guía de seguridad y salud para el personal de olfatometría |

> ⚠️ Esta tabla procede de **fuentes secundarias** (laboratorios y divulgación técnica), no del
> texto de la norma, que es de pago. Antes de citar un requisito concreto en un expediente,
> verifíquese sobre la norma. Ver apartado H.

**Por qué importa a la modelización:** la revisión afecta a la **incertidumbre del dato de entrada**.
El caudal de olor que se introduce en AERMOD procede de un ensayo olfatométrico, y ese ensayo tiene
una incertidumbre que domina la del estudio completo — muy por encima de la del modelo de dispersión.

### A.3 Cómo se mide en campo: la fuente manda

La herramienta admite **fuentes puntuales** (`ou_E/s`) y **fuentes de área AREAPOLY**
(`ou_E/(s·m²)`). Esa distinción no es un detalle de configuración: **corresponde a dos técnicas de
muestreo distintas y no intercambiables**.

| Tipo de foco | Ejemplos | Técnica de muestreo | Magnitud obtenida | Unidad para la herramienta |
|---|---|---|---|---|
| **Puntual / canalizada** | Chimenea, salida de biofiltro, extractor | Toma en conducto (sonda + bomba de vacío, llenado indirecto de bolsa) | `C_olor` (ou_E/m³) × caudal (m³/s) | `ou_E/s` |
| **Área activa** | Balsa aireada, lecho de biofiltro con flujo ascendente | Campana estática / dispositivo de flujo sobre la superficie | SOER, caudal específico por superficie | `ou_E/(s·m²)` |
| **Área pasiva** | Balsa en calma, pila de compost, vertedero, lodos | **Campana de flujo** (*flux chamber*) o **túnel de viento** (*wind tunnel*) | SOER | `ou_E/(s·m²)` |

El caudal de emisión de una fuente puntual es directo:

```
E [ou_E/s] = C_olor [ou_E/m³] × Q [m³/s]
```

Para fuentes de área se obtiene la **tasa específica de emisión de olor** (SOER, *Specific Odour
Emission Rate*), en `ou_E/(m²·s)`, que es exactamente lo que espera AREAPOLY:

```
SOER [ou_E/(m²·s)] = C_olor,campana [ou_E/m³] × Q_barrido [m³/s] / A_cubierta [m²]
```

donde `Q_barrido` es el caudal de aire neutro que se hace pasar por el dispositivo y `A_cubierta`
la superficie que este cubre.

> ⚠️ **El escollo número uno del muestreo de fuentes de área.** La SOER medida **depende del
> dispositivo**. Comparaciones publicadas entre campana de flujo y túnel de viento sobre la misma
> superficie encuentran tasas sistemáticamente mayores con túnel de viento, con ratios reportados
> del orden de **60:1 a 240:1** en el caso más desfavorable. Esto no es ruido experimental: es que
> ambos dispositivos imponen condiciones de transferencia de materia distintas sobre la interfase.
> Para emisiones controladas por transferencia de materia (compuestos volátiles desde un líquido
> en calma) el resultado depende de la velocidad de barrido; para emisiones controladas por
> generación biológica en el seno del material, mucho menos.
>
> **Regla operativa:** el informe debe declarar **qué dispositivo se usó y con qué velocidad de
> barrido**. Una SOER sin esa información no es trazable y no debería alimentar un modelo.

Valores de referencia frecuentemente citados en este contexto (⚠️ verificar sobre norma antes de
usarlos como criterio): velocidad mínima de expulsión de **0,008 m/s** para considerar una fuente
como activa según EN 13725:2022, coherente con los 30 m/h de VDI 3880:2011; y un límite de flujo
específico de **50 m³·h⁻¹·m⁻²** en VDI 3880, que recomienda además un tiempo de muestreo mínimo de
**30 min**.

### A.4 Por qué el olor de una MEZCLA no se deduce de la composición química

Es la razón de fondo por la que existe la olfatometría y por la que un análisis de COVs no la
sustituye. Tres mecanismos:

1. **No aditividad.** La intensidad y el tono hedónico de una mezcla por encima del umbral son
   habitualmente **distintos** de lo que predice la suma de las contribuciones individuales
   calculadas a partir de la concentración de cada componente y su umbral.
2. **Sinergia.** Amplificación mutua: dos compuestos juntos huelen más que la suma de sus partes.
3. **Enmascaramiento y neutralización.** Un componente puede sustituir perceptivamente a otro
   (enmascaramiento) o hacer desaparecer el olor / reducir marcadamente su intensidad
   (neutralización).

A esto se añade un problema de sensibilidad instrumental: buena parte de los compuestos que
gobiernan la percepción están **por debajo del límite de detección** de los métodos analíticos
habituales, precisamente porque sus umbrales olfativos son bajísimos (ver la tabla del apartado F:
el escatol se huele a 0,0056 ppb).

**Corolario para el modelizador:** modelar `H2S` o `NH3` como trazador y luego «convertir a olor»
mediante su umbral es una aproximación que **subestima sistemáticamente** el olor de una mezcla
real. Si el criterio a comparar está en `ou_E/m³`, el dato de entrada debe ser olfatométrico.
Modelar el trazador químico es legítimo para otros fines (salud, comparación con umbrales
individuales), pero es **otro estudio**.

---

## B. El factor pico-media — el punto clave

### B.1 El problema

AERMOD calcula **medias horarias**. La nariz humana no promedia: detecta en el tiempo de una
inhalación, del orden de **1 a 5 segundos**. Dentro de una hora cuya media es 0,5 ou_E/m³ puede
haber ráfagas de 5 ou_E/m³ perfectamente perceptibles. Modelar el olor sin corregir esto
**subestima el impacto**.

La corrección se llama **factor pico-media** (*peak-to-mean*, F):

```
F = C_p / C_m
```

con `C_m` la concentración media sobre el intervalo `t_m` (la hora de AERMOD) y `C_p` la
concentración "pico" sobre el intervalo corto `t_p`.

> **⚠️ Aviso crítico antes de cualquier fórmula: «pico» no está unívocamente definido.**
> `C_p` puede definirse como (1) media + desviación típica, (2) percentil 90 de la distribución
> instantánea, (3) percentil 98 o 99, o (4) el máximo. Schauberger et al. (2012) muestran con un
> ejemplo numérico que, para un mismo caso, los factores resultantes son
> **F_i = 1,35 · F_90 = 1,47 · F_98 = 1,85** para un intervalo de integración, y
> **F_i = 2,23 · F_90 = 2,79 · F_98 = 5,17** para otro más corto. **Un factor pico-media sin la
> definición de pico y sin `t_p` no significa nada.**

### B.2 Ley potencial de Smith (1973) — la formulación básica

Es la expresión que usa prácticamente toda la práctica regulatoria:

```
C_p / C_m = ( t_m / t_p ) ^ u
```

Equivalentemente, con exponente negativo (forma usada en la literatura sobre CALPUFF):

```
C_p / C_m = ( t_p / t_m ) ^ a        con  a = -u
```

Las dos formas son idénticas. Los exponentes publicados dependen de la **estabilidad atmosférica**:

**Tabla B.1 — Exponente `u` y factor resultante para `t_p` = 5 s y `t_m` = 3600 s**

| Estabilidad | `u` (Smith 1973) | `C_p/C_m` | `u` (Trinity Consultants 1976) | `C_p/C_m` |
|---|---|---|---|---|
| Inestable | 0,64 | 67,4 | 0,68 | 87,7 |
| Ligeramente inestable | 0,51 | 28,7 | 0,55 | 37,3 |
| Neutra | 0,38 | 12,2 | 0,43 | 16,9 |
| Ligeramente estable | 0,25 | 5,2 | 0,30 | 7,2 |
| Estable | 0 | 1,0 | 0,18 | 3,3 |
| Muy estable | 0 | 1,0 | 0,18 | 3,3 |

Fuente: Schauberger et al. (2012), Tabla 1, citando a Smith (1973) y Trinity Consultants (1976)
vía Beychok (1994). *Aritmética verificada*: `(3600/5)^0,38 = 12,2` ✓.

> ⚠️ **Estos son factores MÁXIMOS, en el campo próximo y con `C_p` definido como máximo.** No son
> los factores a aplicar directamente sobre toda la malla de receptores. Aplicar F = 67 a todo el
> dominio produce resultados absurdos. Deben atenuarse con la distancia (B.4).

**Rango del exponente.** La literatura sitúa `a` entre −1 y 0 (es decir, `u` entre 0 y 1), con
**`a = −0,2` (`u = 0,2`) como valor recomendado por la mayoría de autores y el usado por CALPUFF**,
que para 5 s/1 h da **F = 3,73**.

**Dependencia de la geometría de la fuente.** Best et al. (2001) proponen exponentes distintos:

| Tipo de fuente | `u` propuesto | `C_p/C_m` para 5 s / 1 h |
|---|---|---|
| Fuente puntual | 6/17 ≈ 0,353 | ≈ 10,2 |
| Fuente lineal | 3/14 ≈ 0,214 | ≈ 4,1 |

*Los exponentes son de Best et al. (2001) según cita de Schauberger et al. (2012); los factores
resultantes los he calculado yo aplicando la ecuación.* Katestone Scientific (1998) documenta que
las **fuentes de área presentan factores pico-media menores que las fuentes puntuales elevadas** —
directamente relevante aquí, donde se modelan ambas con AREAPOLY y puntuales.

### B.3 Vía alternativa: intensidad de fluctuación e intermitencia

Lung et al. (2002), a partir de medidas en el campo próximo de una fuente puntual (20–100 m):

```
F = 1 + α · i²          con α = 3,6
```

donde `i = σ / C_m` es la **intensidad de fluctuación** (desviación típica de la concentración
dividida por la media). Este `F` corresponde a un pico integrado en **1 s** frente a la media horaria.

La intensidad de fluctuación se relaciona con la **intermitencia** `γ` (fracción de intervalos con
concentración no nula):

```
i² = β · (1 - γ) / γ ... [ver ⚠️ en H: la forma exacta no es legible en la fuente consultada]
```

con `β` entre **2** (Hanna 1984), **3** (Best et al. 2001) y **3,6** (Lung et al. 2002).

Dependencia con la **distancia lateral** al eje de la pluma (la fluctuación **crece** al alejarse
del eje, donde la pluma pasa de forma intermitente):

```
i(x,y) = i(x) · exp( y² / (a · σ_y²) )
```

con **`a = 2`** según Best et al. (2001) y **`a = 4`** según Katestone Scientific (1998). `σ_y` es
el parámetro de dispersión lateral gaussiano.

Medidas en campo próximo (`t_p` = 1 s, `C_p` = máximo) dan factores en el rango
**4 < F_max < 99** (Lung et al. 2002) — magnitud del problema si se ignora la atenuación.

### B.4 Atenuación con la distancia — Schauberger et al. (2000)

Es la pieza que falta en la ley potencial simple, y la más importante para no sobrestimar:

```
F = 1 + ( F_0 - 1 ) · exp( - 0,7317 · T / t_L )
```

donde:
- `F_0` = factor pico-media en la fuente, tomado de la **Tabla B.1** según estabilidad
- `T = x / v` = tiempo de viaje (distancia `x` dividida por la velocidad media del viento `v`)
- `t_L` = escala de tiempo lagrangiana, que requiere las desviaciones típicas de las tres
  componentes del viento (Mylne 1992; cálculo mejorado por Piringer et al. 2007)

El comportamiento es el correcto físicamente: **F → F_0 en la fuente y F → 1 lejos**, porque la
mezcla turbulenta va borrando las fluctuaciones. Empíricamente la intensidad de fluctuación tiende
a un valor constante de **1,0 ± 0,3** (Mylne 1990).

Este es el enfoque del **AODM** (Austrian Odour Dispersion Model). Es un **post-proceso**: se aplica
sobre la salida del modelo gaussiano, exactamente el papel que tendría aquí sobre AERMOD.

### B.5 Factores constantes en uso regulatorio

Muchas administraciones renuncian a la formulación variable y fijan un número:

| Marco | Factor | Definición del pico |
|---|---|---|
| **Italia** (decreto MASE 309/2023, Lombardía, Trento, Piamonte) | **2,3** | Picos de 5–10 min, sobre P98 anual — ver [documento de normativa internacional](../normativa/criterios_olor_internacional.md) |
| **AUSTAL2000** (Alemania) | **4** | P90 de la concentración instantánea; umbral de "hora de olor" en 0,25 ou_E/m³ (= 1/4) |
| Modelo gaussiano regulatorio alemán anterior | **10** | (Rühling y Lohmeyer 1998) |
| Modelo danés | **7,8** | (Olesen et al. 2005) |
| CALPUFF (por defecto) | **3,73** | `a` = −0,2, 5 s / 1 h |
| **Países Bajos** | *ninguno nacional* | El percentil lo elige la continuidad del foco — ver [documento enlazado](../normativa/criterios_olor_internacional.md) |

> **La lectura correcta de esta tabla no es «elige uno».** Es: *el factor pico-media forma un par
> indisoluble con el criterio numérico*. El 2,3 italiano va con los umbrales italianos; el 4 alemán
> va con el criterio de frecuencia de horas de olor. **Mezclar el factor de un país con el criterio
> de otro invalida la comparación.** Schauberger et al. (2012) dedican el artículo precisamente a
> argumentar que un factor constante, independiente de estabilidad, distancia y geometría de la
> fuente, «no es apropiado» y solo sirve como estimación muy gruesa.

### B.6 Evidencia de que los factores clásicos se quedan cortos cerca de obstáculos

Dourado et al. (2012) compararon AERMOD y CALPUFF con simulaciones CFD/LES y túnel de viento
alrededor de un obstáculo cúbico (condiciones neutras):

| Posición (x/H) | P/M observado (LES) | `a` ajustado |
|---|---|---|
| 1,5 (sobre el obstáculo) | 10,1 – 11,8 | −0,37 a −0,39 |
| 2,5 (zona de recirculación) | 7,7 – 7,9 | −0,31 a −0,32 |
| 3,5 (inicio de la estela) | 6,1 – 6,8 | −0,28 |

Frente al `a = −0,2` de CALPUFF (P/M = 3,73). Santos et al. (2009) encontraron en campo
`a` entre −0,22 y −0,34 junto a un edificio complejo en condiciones neutras. Conclusión de los
autores: AERMOD y CALPUFF **subestimaron** los niveles altos de concentración, y convendría usar
valores de `a` dependientes de la distancia.

> **Aplicación aquí:** si el estudio incluye edificios (BPIPPRM en la cadena), en la estela
> próxima el factor pico-media real es mayor que el que da la ley potencial estándar.

---

## C. El criterio: percentiles, no máximos

### C.1 Qué significa el P98

El **percentil 98 de las medias horarias sobre un año natural** es el valor que solo se supera
durante el **2 % de las horas del año**:

```
8760 h/año × 2 % = 175,2 h/año  ≈  7,3 días/año
```

Es decir: un P98 de 5 ou_E/m³ en un receptor significa que *ese receptor está por debajo de
5 ou_E/m³ durante 8585 horas al año, y por encima durante 175*.

**Por qué percentil y no máximo.** El máximo anual de un modelo de dispersión es un valor
extraordinariamente inestable: depende de una única hora meteorológica, a menudo una situación
numéricamente extrema (calma, inversión fuerte) donde la formulación gaussiana es menos fiable.
Basar un criterio en él haría que el resultado dependiese del azar meteorológico de un año
concreto. El percentil es **robusto**: mover una hora no lo mueve.

**Por qué percentil y no media anual.** Porque la molestia por olor es **episódica**. Una media
anual baja es perfectamente compatible con episodios intensos y frecuentes. La media anual no
distingue entre una emisión constante e imperceptible y una emisión intermitente y muy molesta.

### C.2 Exige un año completo

Un P98 calculado sobre menos de 8760 h **no es un P98**. Razones:

1. **Ciclo estacional del olor.** Las emisiones de fuentes biológicas (balsas, compost, lodos,
   ganadería) dependen fuertemente de la temperatura. El verano puede multiplicar la emisión.
2. **Ciclo estacional de la meteorología.** Las clases de estabilidad tienen distribución anual
   marcada. Las situaciones más desfavorables para el olor —estables, viento flojo, nocturnas—
   se concentran estacionalmente.
3. **Rosa de vientos.** Un receptor a sotavento en invierno puede estar a barlovento en verano.
4. **Aritmética.** Con 2190 h (un trimestre), el 2 % son 43,8 h: el P98 se apoya en muy pocos
   datos y su varianza muestral es alta.

> **Regla:** un año meteorológico completo y **representativo**. Si se dispone de varios años,
> conviene declarar cuál se usó y por qué. La cadena AERMET debe cubrir las 8760 h con una tasa de
> datos válidos aceptable.

### C.3 Focos discontinuos: el percentil deja de ser inocente

Si el foco **no emite de forma continua**, el P98 puede ser engañoso. Caso extremo: un foco que
emite 100 h al año, muy intensamente. Esas 100 h están *por debajo* del umbral de 175 h del P98:
**el P98 sería cero aunque el foco genere episodios severos**.

El enfoque neerlandés resuelve esto haciendo que **el percentil dependa de la continuidad del
foco**: P98 si el foco es continuo, y percentiles más exigentes (99,5 / 99,9 / 99,99) cuando es
discontinuo. Los detalles y la relación 1:4 entre P98 y P99,9 están en
[`../normativa/criterios_olor_internacional.md`](../normativa/criterios_olor_internacional.md).

**Regla operativa:** antes de elegir el percentil, caracterizar el **régimen temporal de emisión**
(continuo / por lotes / estacional / accidental) y declararlo. Si el foco es discontinuo y el
criterio aplicable exige P98 (como el Decreto 185/2025 de Canarias), conviene **calcular además**
un percentil más alto y comentarlo en el informe: cumplir el P98 no garantiza ausencia de molestia.

**Implicación para la modelización:** un foco discontinuo debe modelarse con su **factor de
emisión variable en el tiempo** (en AERMOD, opciones tipo `EMISFACT` por hora del día / mes /
estación), no con una emisión media constante. Promediar la emisión de un foco discontinuo sobre
todo el año **elimina exactamente la señal que se quiere evaluar**.

---

## D. Cómo se calcula el percentil a partir de la salida de AERMOD

Este es el apartado operativo. Los pasos son cinco, y en cada uno hay un error clásico.

### D.0 ⚠️ Primero: comprobar que se tienen las 8760 horas

> **✅ ACTUALIZACIÓN (22/07/2026) — ya está implementado.** Lo que este apartado describía como
> una carencia se resolvió: la herramienta vuelca la serie horaria con `prepare_case(...,
> postfile=True)` y calcula el estadístico con
> `percentiles_por_receptor(pct=(98.0,), rank=…, peak_factor=…)`. El `peak_factor` multiplica la
> serie **antes** de ordenar, que es el orden correcto (ver el error nº 4 de la tabla de abajo).
>
> El diagnóstico que sigue es correcto y se conserva porque explica **por qué** hacía falta.

**Hallazgo verificado sobre el código de esta herramienta** (`getAermod.py`): el fichero de entrada
de AERMOD se genera con

```
OU STARTING
   RECTABLE ALLAVE FIRST-SECOND
   MAXTABLE ALLAVE 50
   PLOTFILE <periodo|avertime> ALL <fichero>
```

y `concentraciones.csv` en `tmp/Results/<lat>_<lon>_<anio>/[<contaminante>/]` tiene la estructura:

```
x,y,conc,zelev,zhill
774117.6,4608397.4,99670.8,131.86,131.86
```

es decir **una sola fila por receptor y un solo valor de concentración**. Ese valor es el
1.º/2.º máximo o la media del periodo según la configuración — **no es la serie horaria**.

> **🔑 CONSECUENCIA: el P98 NO se puede calcular a partir de `concentraciones.csv` tal como está.**
> Ese fichero ya es un estadístico agregado. Calcular un "percentil" sobre la columna `conc` daría
> el percentil **espacial entre receptores** (el receptor que está en el puesto 98 % de la malla),
> que **no tiene absolutamente nada que ver** con el percentil temporal que pide la norma. Es el
> error más grave y más fácil de cometer en toda esta metodología.

Para obtener el percentil temporal hay que pedir a AERMOD la **serie horaria por receptor**:

| Vía | Palabra clave AERMOD | Qué da |
|---|---|---|
| **Recomendada** | `POSTFILE 1 ALL <fichero>` | Todos los valores horarios en todos los receptores. Fichero grande pero completo: permite cualquier percentil a posteriori |
| Alternativa | `RECTABLE 1 <n>TH` | El n-ésimo valor más alto por receptor, directamente |

La vía `POSTFILE` es preferible porque **permite aplicar el factor pico-media hora a hora** (que
depende de la estabilidad de cada hora) antes de ordenar. Con `RECTABLE` solo cabe aplicar un
factor constante.

### D.1 Paso a paso

```
1. Ejecutar AERMOD con AVERTIME 1 y POSTFILE
   → serie horaria C_m(receptor, hora), 8760 valores por receptor, en ou_E/m³

2. Aplicar el factor pico-media a CADA hora
   → C_p(receptor, hora) = F(estabilidad_hora, distancia, geometría) × C_m(receptor, hora)
   (si se usa un factor constante — 2,3 italiano, 4 alemán — este paso es una multiplicación
    escalar y puede hacerse igualmente antes de ordenar; el resultado es el mismo porque
    multiplicar por una constante positiva no altera el orden)

3. Para cada receptor, ordenar sus 8760 valores de C_p de mayor a menor

4. Tomar el percentil:
   n_exceed = round( 8760 × (1 - p/100) )
   P98  → n_exceed = 175  → valor en la posición 176 de la lista descendente
   P99,5 → n_exceed = 44  → posición 45
   P99,9 → n_exceed = 9   → posición 10

5. Comparar el valor resultante con el criterio (3 / 6 / 9 ou_E/m³ en Canarias, según uso del suelo)
   y cartografiar la isopleta correspondiente
```

Implementación mínima en Python, partiendo de un `DataFrame` con columnas
`receptor`, `hora`, `conc`:

```python
import numpy as np

F = 2.3  # factor pico-media constante; ver apartado B antes de fijarlo

# 1 valor por receptor: P98 temporal
def p98(serie_horaria):
    v = np.sort(np.asarray(serie_horaria))[::-1]  # descendente
    assert len(v) == 8760, f"faltan horas: {len(v)}"
    return v[175]          # posición 176 (índice 175)

p98_por_receptor = (df.assign(cp=df["conc"] * F)
                      .groupby("receptor")["cp"]
                      .apply(p98))
```

### D.2 Los errores que se cometen aquí

| # | Error | Consecuencia | Cómo evitarlo |
|---|---|---|---|
| 1 | **Calcular el percentil sobre `concentraciones.csv`** | Se obtiene un percentil *espacial* entre receptores. Resultado sin sentido físico ni normativo | Usar `POSTFILE`. Ver D.0 |
| 2 | **Serie incompleta** (< 8760 h) | El P98 se apoya en pocos datos; sesgo estacional | Verificar `len(serie) == 8760` con un `assert`. Documentar horas perdidas de AERMET |
| 3 | **Confundir el rango**: usar el 175.º en vez del 176.º, o aplicar `np.percentile(x, 98)` sin más | Diferencia pequeña pero el resultado no es reproducible ni auditable | Fijar y **declarar** la convención. `np.percentile` con interpolación lineal cae entre el 176.º y el 177.º; no es idéntico al recuento estricto |
| 4 | **Aplicar el factor pico-media DESPUÉS de calcular el percentil, con factor variable** | Si `F` depende de la estabilidad, el orden importa: la hora que da el P98 de `C_m` no es la que da el P98 de `C_p` | Con `F` variable, multiplicar **antes** de ordenar (paso 2). Con `F` constante da igual |
| 5 | **Olvidar el factor pico-media** | Subestimación directa, entre ×2,3 y ×10 según el criterio | Declararlo siempre, aunque sea 1,0, y justificarlo |
| 6 | **Mezclar factor y criterio de países distintos** | Comparación inválida | Ver B.5 |
| 7 | **Sumar percentiles de varios focos** | El P98 **no es aditivo**: los máximos de focos distintos ocurren con vientos distintos | Sumar las **series horarias** de todos los focos primero, y calcular el percentil sobre la suma |
| 8 | **Promediar la emisión de un foco discontinuo** | Se borra la señal episódica | Usar factores de emisión temporales (`EMISFACT`). Ver C.3 |
| 9 | **Unidades**: mezclar `ou_E/s` con `ou_E/(s·m²)` | Error de órdenes de magnitud | Puntual → `ou_E/s`; AREAPOLY → `ou_E/(s·m²)`. Ver A.3 |
| 10 | **Receptores solo en malla regular** | El punto crítico (una vivienda concreta) puede caer entre nodos | Añadir receptores discretos en los edificios sensibles reales |

> El **error 7** merece énfasis. Es intuitivo pensar que si el foco A da P98 = 2 y el foco B da
> P98 = 3, juntos dan 5. Es falso, y normalmente **sobrestima**: el P98 de A se alcanza con viento
> de una dirección y el de B con otra. La única forma correcta es sumar hora a hora.

---

## E. La ley de Stevens y por qué las medidas correctoras decepcionan

### E.1 La ley

La relación entre la magnitud física del estímulo y la intensidad percibida no es lineal, sino
potencial (Stevens, 1957):

```
I = k · C ^ n
```

con `I` la intensidad percibida, `C` la concentración, `k` una constante que depende de las
unidades y `n` un exponente característico de la modalidad sensorial. **Para el olfato `n < 1`**:
la percepción está **comprimida** respecto al estímulo.

> ⚠️ **Sobre el valor de `n`.** El único valor que he podido verificar en fuente consultable es
> **`n = 0,6` para heptano** en la tabla clásica de exponentes de Stevens (y la propia fuente
> advierte de que carece de cita inline). El valor «`n ≈ 0,5` para el olor» circula ampliamente
> como orden de magnitud, pero **no lo he verificado sobre fuente primaria**. Ver apartado H.
> Lo que sí es sólido y suficiente para el argumento es que **`n` está claramente por debajo de 1**.

### E.2 La consecuencia práctica: por qué decepcionan las medidas correctoras

Si la percepción va como `C^n` con `n < 1`, entonces **reducir la emisión a la mitad NO reduce el
olor percibido a la mitad**:

```
I₂ / I₁ = ( C₂ / C₁ ) ^ n
```

**Tabla E.1 — Reducción de intensidad percibida según la reducción de emisión**

| Reducción de emisión | `C₂/C₁` | Reducción percibida con n = 0,5 | Reducción percibida con n = 0,6 |
|---|---|---|---|
| 50 % | 0,50 | **29 %** | 34 % |
| 75 % | 0,25 | **50 %** | 57 % |
| 90 % | 0,10 | **68 %** | 75 % |
| 95 % | 0,05 | 78 % | 83 % |
| 99 % | 0,01 | 90 % | 94 % |

*(calculado por mí aplicando la ecuación; los exponentes son los discutidos en E.1)*

Y a la inversa — la pregunta que hace el gestor:

**Tabla E.2 — Reducción de emisión necesaria para un objetivo perceptivo**

| Objetivo: reducir la intensidad percibida a... | Reducción de emisión necesaria (n = 0,5) | (n = 0,6) |
|---|---|---|
| la mitad (50 %) | **75 %** (dividir por 4) | 68 % |
| un tercio | 89 % (dividir por 9) | 84 % |
| un cuarto | 94 % (dividir por 16) | 90 % |

> **El mensaje para el informe.** Instalar una medida correctora con **50 % de eficacia de
> eliminación de olor** produce una mejora percibida de apenas ~30 %, que muchos vecinos
> describirán como «no ha cambiado nada». Esto explica el patrón recurrente de quejas persistentes
> tras inversiones significativas en depuración. **Un informe honesto debe anticiparlo**: para que
> la mejora sea inequívocamente perceptible hay que apuntar a eficacias del **90 % o superiores**.
>
> Obsérvese además que esto **se acumula con el efecto del percentil**: reducir la emisión no
> desplaza el P98 proporcionalmente si el foco es discontinuo, ni cambia las direcciones de viento
> que llevan el penacho al receptor.

### E.3 Nota de coherencia

La ley de Stevens describe la **intensidad percibida**, mientras que la `ou_E/m³` es una medida de
**dilución al umbral**. Son magnitudes distintas: la `ou_E` es lineal por construcción (duplicar
las diluciones duplica el número de ou_E), y la intensidad percibida no lo es. Por eso la ley de
Stevens **no se aplica al cálculo del percentil** — se aplica a la *interpretación* de lo que
significa una reducción para las personas afectadas.

---

## F. Umbrales olfativos por compuesto

### F.1 Tabla — Nagata (2003), método de la bolsa triangular

**Fuente primaria verificada.** Yoshio Nagata (Japan Environmental Sanitation Center),
*Measurement of Odor Threshold by Triangle Odor Bag Method*. 223 sustancias, ensayos entre 1976 y
1988, panel de 6 personas cribadas con olfatómetro T&T. El valor reportado es el **umbral de
detección**, en ppm v/v; se toma la **media geométrica** cuando hubo repeticiones.

Conversión a µg/m³ aplicada por mí, a **20 °C y 101,325 kPa** (volumen molar 24,055 L/mol):

```
µg/m³ = ppb × M [g/mol] / 24,055
```

| Compuesto | Umbral (ppb) | Umbral (µg/m³) | Descriptor ⚠️ |
|---|---|---|---|
| **Compuestos de azufre** | | | |
| Isoamil mercaptano | 0,00077 | 0,0033 | pútrido |
| n-Amil mercaptano | 0,00078 | 0,0033 | pútrido |
| n-Butil mercaptano | 0,0028 | 0,010 | mofeta, ajo |
| Isopropil mercaptano | 0,0060 | 0,018 | pútrido |
| Etil mercaptano | 0,0087 | 0,022 | col podrida |
| **Metil mercaptano** | **0,070** | **0,14** | col podrida |
| **Sulfuro de hidrógeno (H₂S)** | **0,41** | **0,58** | huevo podrido |
| **Disulfuro de dimetilo** | **2,2** | **8,6** | ajo, sulfuroso |
| **Sulfuro de dimetilo** | **3,0** | **7,8** | col cocida |
| Disulfuro de dietilo | 2,0 | 10,2 | ajo |
| Sulfuro de carbono (CS₂) | 210 | 665 | sulfuroso débil |
| Dióxido de azufre (SO₂) | 870 | 2 317 | picante, irritante |
| **Compuestos de nitrógeno** | | | |
| **Escatol (3-metilindol)** | **0,0056** | **0,031** | fecal, nauseabundo |
| **Trimetilamina** | **0,032** | **0,079** | pescado podrido |
| **Indol** | **0,30** | **1,5** | fecal, floral en dilución |
| Piridina | 63 | 207 | acre, quemado |
| Dimetilamina | 33 | 62 | pescado, amoniacal |
| Metilamina | 35 | 45 | pescado |
| Trietilamina | 5,4 | 22 | amoniacal |
| **Amoniaco (NH₃)** | **1 500** | **1 062** | picante, punzante |
| Dióxido de nitrógeno (NO₂) | 120 | 230 | irritante |
| **Ácidos grasos volátiles** | | | |
| **Ácido n-valérico** | **0,037** | **0,16** | sudor, rancio |
| **Ácido isovalérico** | **0,078** | **0,33** | sudor, queso |
| **Ácido n-butírico** | **0,19** | **0,70** | mantequilla rancia, vómito |
| Ácido isobutírico | 1,5 | 5,4 | rancio |
| **Ácido propiónico** | **5,7** | **17,6** | agrio, rancio |
| **Ácido acético** | **6,0** | **15,0** | vinagre |
| **Fenoles** | | | |
| p-Cresol | 0,054 | 0,24 | establo, alquitrán |
| m-Cresol | 0,10 | 0,45 | alquitrán |
| o-Cresol | 0,28 | 1,3 | alquitrán, medicinal |
| Fenol | 5,6 | 21,9 | medicinal, dulzón |
| **Aldehídos y otros** | | | |
| Geosmina | 0,0065 | 0,048 | tierra húmeda, moho |
| Diacetilo | 0,050 | 0,18 | mantequilla |
| n-Octilaldehído | 0,010 | 0,053 | grasiento |
| Isovaleraldehído | 0,10 | 0,36 | rancio, manzana |
| Acetaldehído | 1,5 | 2,7 | fruta, punzante |
| Formaldehído | 500 | 624 | punzante, irritante |
| Acetona | 42 000 | 100 400 | dulzón, disolvente |
| **Hidrocarburos (referencia)** | | | |
| Estireno | 35 | 152 | disolvente, dulzón |
| Tolueno | 330 | 1 264 | disolvente |
| Benceno | 2 700 | 8 750 | disolvente |
| Propano | 1 500 000 | — | (umbral más alto de la serie) |

Los valores en **negrita** son los compuestos habitualmente relevantes en depuradoras, ganadería,
compostaje y gestión de residuos.

### F.2 ⚠️ Aviso obligatorio: la dispersión entre fuentes es enorme

**No existe "el" umbral olfativo de un compuesto.** Es un dato con una variabilidad que hay que
declarar siempre. Para el **H₂S**, valores publicados:

| Fuente | Valor / rango publicado |
|---|---|
| **Nagata (2003)**, bolsa triangular | **0,41 ppb** |
| Ruth (1986), citado en revisiones | 0,5 – 10 ppb |
| ATSDR, *ToxGuide* / perfil toxicológico | 0,5 – 300 ppb («0,0005 a 0,3 ppm») |
| Otras compilaciones citadas por ATSDR | 8 – 130 ppb |
| Valor «detectable» citado con frecuencia | 0,5 ppb |

Es decir: **entre el valor más bajo y el más alto publicado hay casi tres órdenes de magnitud.**
El rango 0,4–13 ppb que se maneja habitualmente es ya una *selección* conservadora dentro de ese
abanico.

**Causas de la dispersión:**
1. **Definición de umbral distinta** — detección (se nota *algo*) vs. reconocimiento (se identifica
   *qué* es). El de reconocimiento suele ser 2–10 veces mayor.
2. **Método** — bolsa triangular, olfatometría dinámica, cámara sin olor, ascenso/descenso. No dan
   lo mismo.
3. **Panel** — edad, entrenamiento, cribado previo, tamaño; y la variabilidad interindividual en
   olfato es intrínsecamente grande.
4. **Criterio estadístico** — 50 % del panel es lo habitual, pero no universal.

Incluso **dentro del mismo laboratorio** Nagata documenta variabilidad: en ensayos repetidos sobre
la misma sustancia, la razón entre el umbral más alto y el más bajo llegó a **5** (25 sustancias
medidas 2–9 veces).

> **Regla para el informe:** si se usa un umbral olfativo, (a) citar la fuente exacta, (b) indicar
> si es de detección o de reconocimiento, (c) declarar el método y (d) hacer un análisis de
> sensibilidad con el rango publicado, no con un valor puntual. **Un cálculo de impacto por olor
> basado en un único umbral de literatura, sin rango, no es defendible.**

### F.3 Uso legítimo e ilegítimo de esta tabla

| ✔️ Uso legítimo | ❌ Uso ilegítimo |
|---|---|
| Identificar qué compuestos vigilar en una fuente | Convertir concentraciones modeladas de un compuesto en `ou_E/m³` de la mezcla |
| Priorizar puntos de muestreo analítico | Sumar `C_i / umbral_i` y llamar al resultado «unidades de olor» |
| Interpretar cualitativamente un descriptor reportado por vecinos | Sustituir la olfatometría en el cálculo de la emisión |
| Comparar el potencial odorífero relativo de dos corrientes | Justificar el cumplimiento de un criterio en ou_E/m³ |

La razón está en A.4: sinergia, enmascaramiento y no aditividad. El cociente
`Σ (C_i / umbral_i)` se usa a veces como *índice de olor* orientativo, pero **no es una `ou_E`** y
no debe presentarse como tal.

---

## G. Fuentes

Todas consultadas el **21 de julio de 2026**.

**Factor pico-media (fuentes primarias descargadas y leídas)**

1. Schauberger G., Piringer M., Schmitzer R., Kamp M., Sowa A., Koch R., Eckhof W., Grimm E.,
   Kypke J., Hartung E. (2012). *Concept to assess the human perception of odour by estimating
   short-time peak concentrations from one-hour mean values. Reply to a comment by Müller et al.*
   Atmospheric Environment. — https://arxiv.org/pdf/1201.0914
   *(Fuente de la Tabla B.1, de las ecuaciones de B.3 y B.4, y de los factores constantes de B.5.)*
2. Dourado H., Santos J., Reis N. Jr., Melo A.M.V. (2012). *The Effects of Atmospheric Turbulence
   on Peak-to-Mean Concentration Ratio and its Consequence on the Odour Impact Assessment Using
   Dispersion Models.* Chemical Engineering Transactions, Vol. 30, 163–168. —
   https://www.aidic.it/cet/12/30/028.pdf
   *(Fuente de la ley potencial en forma de exponente negativo, del `a = −0,2` de CALPUFF y de la
   tabla comparativa CFD/LES de B.6.)*

**Referencias citadas dentro de las anteriores** (no consultadas en original; se citan como las
citan las fuentes primarias): Smith M.E. (1973); Trinity Consultants (1976) vía Beychok (1994);
Best P., Lunney K., Killip C. (2001), *Water Science & Technology* 44, 157–164; Katestone
Scientific (1998), informe para la EPA de Nueva Gales del Sur; Lung T. et al. (2002),
*Agrartechnische Forschung* 8, E5–E15; Schauberger G., Piringer M., Petz E. (2000),
*Atmospheric Environment* 34, 4839–4851; Piringer M. et al. (2007), *Atmospheric Environment* 41,
1725–1735; Mylne K.R. (1990, 1992); Hanna S.R. (1984); Santos J.M. et al. (2009),
*Building and Environment* 44, 1295–1305; VDI 3940 Parte 2 (2006).

**Umbrales olfativos (fuente primaria descargada y leída)**

3. Nagata Y. *Measurement of Odor Threshold by Triangle Odor Bag Method.* Japan Environmental
   Sanitation Center / Ministerio de Medio Ambiente de Japón. —
   https://www.env.go.jp/en/air/odor/measure/02_3_2.pdf
   *(Fuente de toda la tabla F.1 y de la variabilidad intralaboratorio de F.2.)*
4. ATSDR. *Toxicological Profile for Hydrogen Sulfide and Carbonyl Sulfide*, cap. 4 —
   https://www.atsdr.cdc.gov/toxprofiles/tp114-c4.pdf ; y *ToxGuide* —
   https://www.atsdr.cdc.gov/toxguides/toxguide-114.pdf
   *(Fuente de los rangos alternativos de H₂S en F.2.)*
5. US EPA. *Toxicological Review of Hydrogen Sulfide*, EPA/635/R-03/005 —
   https://iris.epa.gov/static/pdfs/0061tr.pdf

**Olfatometría y norma EN 13725** *(fuentes secundarias — la norma es de pago)*

6. Silsoe Odours. *BS EN 13725:2022 — The European Standard for Odour Measurement* —
   https://silsoeodours.com/en-13725-2022-odour-standard-uk/
7. LOD Srl. *UNI EN 13725:2022: how did the standard change?* —
   https://www.lodsrl.it/en/news/uni-en-13725-2022-how-did-the-standard-change
8. Olores.org. *What is new in the revised EN13725:2021 standard?* —
   https://www.olores.org/en/techniques/dynamic-olfactometry/1210-what-is-new-in-the-revised-en13725-2021-standard

**Muestreo de fuentes de área**

9. Capelli L., Sironi S., Del Rosso R. (2013). *Odor Sampling: Techniques and Strategies for the
   Estimation of Odor Emission Rates from Different Source Types.* Sensors 13(1), 938–955. —
   https://doi.org/10.3390/s130100938
10. *Odour Sampling on Passive Area Sources: Principles and Standardization.* Chemical Engineering
    Transactions Vol. 54 — https://www.aidic.it/cet/16/54/010.pdf
11. *A comparative study of wind tunnel and flux chamber for diffuse emission sampling.* —
    https://www.sciencedirect.com/science/article/pii/S0045653525001845

**Percepción, criterios y revisión internacional**

12. Stevens's power law (tabla de exponentes) —
    https://en.wikipedia.org/wiki/Stevens%27s_power_law ⚠️ *sin citas inline en el original*
13. Brancher M., Griffiths K.D., Franco D., de Melo Lisboa H. (2017). *A review of odour impact
    criteria in selected countries around the world.* Chemosphere. —
    https://effop.org/wp-content/uploads/2021/08/Odour-Brancher-et-al.-2017_Review-international-lugtregulering.pdf
14. CERC. *Odour regulations in Europe* (presentación) —
    https://www.cerc.co.uk/environmental-software/assets/data/doc_presentations/CERC_2015_Odour_regulations_in_Europe.pdf
15. *Summary and Overview of the Odour Regulations Worldwide.* Atmosphere 12(2), 206 —
    https://www.mdpi.com/2073-4433/12/2/206
16. Brattoli M. et al. (2011). *Odour Detection Methods: Olfactometry and Chemical Sensors.*
    Sensors 11(5), 5290–5322. — https://www.mdpi.com/1424-8220/11/5/5290
    *(Fuente de los mecanismos de sinergia, enmascaramiento y no aditividad de A.4.)*

**Sobre la propia herramienta** *(verificado por lectura directa del código y de las salidas)*

17. `getAermod.py`, líneas ~798–849 — bloque `OU STARTING`, `RECTABLE ALLAVE FIRST-SECOND`,
    `PLOTFILE`.
18. `tmp/Results/41.61806_0.34259_2023/H2S/concentraciones.csv` — cabecera `x,y,conc,zelev,zhill`,
    533 líneas para 532 receptores.

---

## H. Incertidumbres y avisos

### H.1 Lo que NO he podido verificar

| # | Afirmación | Estado |
|---|---|---|
| 1 | **Exponente de Stevens `n ≈ 0,5` para el olor** | ⚠️ **No verificado en fuente primaria.** Lo único verificable en fuente consultable es `n = 0,6` para heptano, y esa propia fuente advierte de que la tabla carece de citas inline. Las tablas E.1 y E.2 dan por eso **dos columnas** (0,5 y 0,6). El argumento cualitativo (`n < 1`, la percepción está comprimida) es sólido; el valor exacto, no. **Antes de citar un número en un informe, verificar sobre Stevens (1957) o un manual de psicofísica.** |
| 2 | **Relación exacta entre intensidad de fluctuación e intermitencia** (`i²` vs `γ`) | ⚠️ La ecuación (3) de Schauberger et al. (2012) **no se extrae legiblemente** del PDF (maquetación con símbolos rotos). Sé que la relación existe, que se parametriza con `β`, y que **β = 2 (Hanna 1984), β = 3 (Best et al. 2001) y β = 3,6 (Lung et al. 2002)**. La **forma funcional exacta la he dejado marcada como no verificada en B.3.** No usarla sin ir al original. |
| 3 | **Contenido de EN 13725:2022** | ⚠️ Basado en **fuentes secundarias** (laboratorios y divulgación). La norma es de pago y no la he leído. Los requisitos concretos (temperaturas, humedades, materiales) deben verificarse antes de citarlos en un expediente. |
| 4 | **0,008 m/s / 30 m/h / 50 m³·h⁻¹·m⁻² / 30 min de VDI 3880 y EN 13725** | ⚠️ Proceden de resúmenes de búsqueda, no de las normas. Verificar antes de usar como criterio. |
| 5 | **Ratio 60:1 a 240:1 entre túnel de viento y campana de flujo** | ⚠️ Procede de un resumen de un estudio comparativo concreto, no de una revisión sistemática. La **dirección** del efecto (túnel de viento > campana) está bien establecida; la **magnitud** es muy dependiente del caso y del compuesto. No extrapolar. |
| 6 | **Sintaxis `RECTABLE 1 <n>TH` en AERMOD** | ⚠️ AERMOD admite rangos en `RECTABLE`, pero **el número máximo de rangos y la sintaxis exacta para el 176.º dependen de la versión y de los límites de compilación**. No he verificado que el 176.º sea directamente solicitable. **Por eso recomiendo `POSTFILE`,** que no tiene esa limitación. |
| 7 | **Descriptores de la tabla F.1** | ⚠️ La tabla de Nagata da **solo umbrales**, no descriptores. La columna «Descriptor» procede de conocimiento convencional del campo y **no está respaldada por la fuente citada**. Es orientativa. |

### H.2 Dónde discrepan las fuentes

**a) El factor pico-media es el mayor foco de discrepancia de toda la disciplina.**
Los valores en uso regulatorio van de **2,3** (Italia) a **10** (modelo alemán antiguo), con
**3,73** (CALPUFF), **4** (AUSTAL2000) y **7,8** (Dinamarca) en medio — un rango de **más de 4:1**
entre marcos igualmente oficiales. Y las formulaciones variables dan factores máximos de hasta
**67–88** en condiciones inestables junto a la fuente. Schauberger et al. sostienen que un factor
constante «no es apropiado»; los reguladores lo usan igualmente por operatividad.
**Esto no se resuelve eligiendo el número «correcto»: se resuelve declarando el usado, su
justificación, y haciendo análisis de sensibilidad.**

**b) Umbrales olfativos: hasta tres órdenes de magnitud** para el mismo compuesto. Ver F.2.

**c) Definición de «pico».** Sin acuerdo. Para los mismos datos, F varía entre 1,35 y 5,17 según
se defina el pico por la desviación típica, el P90 o el P98 (ejemplo de Schauberger et al.).
**Un factor pico-media sin definición de pico y sin `t_p` es un número sin significado.**

**d) Muestreo de fuentes de área.** Sin método universalmente aceptado. Es probablemente la mayor
fuente de incertidumbre en el dato de entrada para AREAPOLY, y domina sobre la incertidumbre del
modelo de dispersión.

**e) Convención del percentil.** El recuento estricto (176.º valor descendente) y la interpolación
lineal (`np.percentile(x, 98)`) no dan exactamente el mismo número. La diferencia suele ser
pequeña, pero **debe declararse** para que el resultado sea reproducible.

### H.3 Jerarquía de incertidumbres — dónde está de verdad el error

Orden de magnitud decreciente, para calibrar dónde merece la pena invertir esfuerzo:

```
1. Caracterización de la emisión (olfatometría + muestreo de área)   → puede ser un factor 10 o más
2. Factor pico-media                                                 → factor 2 a 10
3. Umbral olfativo, si se usa la vía química                         → hasta factor 1000 (¡evitarla!)
4. Régimen temporal de emisión (continuo vs. discontinuo)            → factor 2 a 5 sobre el percentil
5. Meteorología y año seleccionado                                   → factor 1,5 a 2
6. Modelo de dispersión (AERMOD) y terreno                           → factor 1,5 a 2
```

> **La conclusión operativa más importante de este documento:** afinar la malla de receptores o el
> tratamiento del terreno mientras se usa una SOER de literatura y un factor pico-media por defecto
> es optimizar el eslabón equivocado. **El esfuerzo debe ir a medir bien la emisión y a justificar
> el factor pico-media.**
