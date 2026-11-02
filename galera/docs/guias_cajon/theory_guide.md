# Guía teórica — Dispersión atmosférica y el modelo gaussiano

> **Para quién es esto:** para alguien de primero de ingeniería. Se supone que sabes
> derivar, integrar y que has oído hablar de la campana de Gauss. Nada más. Cada término
> nuevo se explica en una casilla la primera vez que aparece.

> **⚠️ Aviso de sesgo, léelo antes que nada**
>
> Casi toda la bibliografía de dispersión está escrita **pensando en una chimenea
> industrial**: un tubo alto que escupe gases calientes. Y hoy la mayoría de los estudios
> reales no son eso, sino **plantas de compostaje, EDAR, vertederos, balsas, granjas,
> canteras** — y muy a menudo el problema no es un tóxico, sino el **olor**.
>
> Esos casos **no son una chimenea pequeña**: cambian la física (emisión fría, a ras de
> suelo, repartida por una superficie, sin sobreelevación) e incluso **la magnitud que se
> calcula** (unidades de olor en vez de µg/m³, y percentiles en vez de medias).
>
> Esta guía está escrita con la **fuente genérica** por delante. La chimenea aparece como
> *un caso particular*, no como el caso.

## Índice

**Parte I — La física, común a todos los casos**
1. [El problema: de la fuente al receptor](#1-el-problema-de-la-fuente-al-receptor)
2. [Los tres transportes](#2-los-tres-transportes)
3. [El viento: advección](#3-el-viento-advección)
4. [La turbulencia y la estabilidad atmosférica](#4-la-turbulencia-y-la-estabilidad-atmosférica)
5. [El modelo gaussiano](#5-el-modelo-gaussiano)

**Parte II — Las fuentes reales**
6. [Tipos de fuente: punto, área, volumen, línea](#6-tipos-de-fuente)
7. [¿Sube el penacho? Emisiones boyantes vs. pasivas](#7-sube-el-penacho)
8. [Cuando el contaminante no se conserva](#8-cuando-el-contaminante-no-se-conserva)

**Parte III — Olores**
9. [Olores: por qué son otro problema](#9-olores-por-qué-son-otro-problema)
10. [Mezclas de gases](#10-mezclas-de-gases)

**Parte IV — Los datos de entrada: de dónde sale cada número**
11. [Catálogo de variables: qué alimenta cada dato](#11-catálogo-de-variables)
12. [El uso del suelo: cómo un bosque se convierte en tres números](#12-el-uso-del-suelo)
13. [El perfil vertical: los datos en altura](#13-el-perfil-vertical)
14. [¿Cuánto importa cada uno? Dos experimentos de sensibilidad](#14-cuánto-importa-cada-uno)

**Parte V — Cierre**
15. [Qué NO hace el modelo gaussiano](#15-qué-no-hace-el-modelo-gaussiano)
16. [De la teoría a esta herramienta](#16-de-la-teoría-a-esta-herramienta)

---

# Parte I — La física, común a todos los casos

## 1. El problema: de la fuente al receptor

Un foco emite algo al aire. La pregunta es siempre la misma, da igual el caso:

> *Si emito `Q` por segundo, ¿cuánto habrá en el aire a 800 m hacia el sureste, a la
> altura de la nariz de una persona?*

Lo que cambia de un caso a otro es **quién emite, qué, y desde qué geometría**:

| Caso real | Qué emite | Geometría | Temperatura |
|---|---|---|---|
| Chimenea industrial | SO₂, NOx, partículas | **punto**, alto (20–100 m) | caliente (400–500 K) |
| Planta de compostaje | NH₃, VOC, olor | **área**, a ras de suelo | templada (pilas a 50–70 °C) |
| EDAR (decantadores, aireación) | H₂S, mercaptanos, olor | **área**, a ras de suelo | ambiente |
| Vertedero | CH₄, H₂S, olor | **área** grande | ambiente |
| Balsa de purines | NH₃, olor | **área** | ambiente |
| Cantera, acopio | partículas (PM10) | **área** o **volumen** | ambiente |
| Nave ganadera | NH₃, olor | **volumen** o punto (extractores) | ligeramente cálida |
| Tráfico | NOx, partículas | **línea** | ambiente |

Fíjate en la columna de temperatura: **la chimenea es la excepción**, no la regla. Casi
todo lo demás emite a temperatura ambiente. Eso tendrá consecuencias enormes (sección 7).

> **🧠 CONCEPTO · Emisión vs. inmisión**
>
> Dos palabras que se confunden todo el rato y significan cosas distintas:
>
> - **Emisión:** lo que *sale* del foco. Masa por tiempo (g/s). Es una propiedad de la
>   instalación.
> - **Inmisión:** lo que *hay* en el aire donde está la gente. Masa por volumen (µg/m³).
>   Es una propiedad del sitio, y depende del tiempo que haga.
>
> La misma emisión produce inmisiones distintísimas según sople el viento. La normativa
> —y las quejas del vecindario— van de **inmisión**. Todo este documento va de cómo pasar
> de una a la otra.

> **🔢 VARIABLE · `Q` — término fuente**
>
> - **Qué es:** lo que sale del foco por unidad de tiempo.
> - **Unidades:** dependen de la geometría, y esto es fuente de errores constante:
>
> | Tipo de fuente | Unidades de `Q` |
> |---|---|
> | Puntual | g/s |
> | **Área** | **g/(s·m²)** — por metro cuadrado de superficie |
> | Volumen | g/s |
> | Línea | g/(s·m) |
>
> - **Para olores:** en vez de gramos se usan **unidades de olor**: `ou_E/s` o
>   `ou_E/(s·m²)` (sección 9).
> - **De dónde sale:** medido en campo (campana de flujo, túnel de viento, olfatometría)
>   o de **factores de emisión** tabulados (EPA AP-42 y equivalentes).
> - **En la app:** el campo *Caudal* de AERSOURCE, que **cambia de unidades** según
>   dibujes un punto (g/s) o un área (g/s·m²).

> **⚠️ OJO · `Q` es la mayor incertidumbre de todo el estudio**
>
> Se dedica muchísimo esfuerzo a afinar el modelo de dispersión, y luego resulta que el
> error dominante está en `Q`. En una chimenea `Q` se mide bien (hay un caudalímetro y un
> analizador). En una **pila de compostaje o una balsa**, `Q` se estima con una campana
> de flujo sobre unos pocos m² y se extrapola a toda la superficie, con variaciones de
> **un orden de magnitud** según la zona, la hora y el día que midas.
>
> Un modelo perfecto alimentado con una `Q` que falla ×10 te da un resultado que falla
> ×10. **La cadena vale lo que su eslabón más débil**, y casi nunca es el modelo.

> **🔢 VARIABLE · `C` — concentración (la incógnita)**
>
> - **Qué es:** masa (o unidades de olor) por volumen de aire, en cada punto.
> - **Unidades:** µg/m³ · mg/m³ · ppb · **ou_E/m³** (olores).
> - **En la app:** es lo que pinta el mapa de colores de la pestaña AERMOD.

---

## 2. Los tres transportes

Suelta una gota de tinta en un río. Le pasan tres cosas a la vez:

1. **Baja con la corriente.** La mancha entera viaja río abajo.
2. **Se ensancha** porque el agua no baja en línea recta: hay remolinos que la revuelven.
3. **Se difunde** poquísimo por agitación molecular.

El aire es igual, cambiando "corriente" por **viento** y "remolinos" por **turbulencia**.

> **🧠 CONCEPTO · Advección**
>
> El transporte *en bloque* por el movimiento medio del fluido. La nube va donde la
> lleva el viento. No cambia de forma por advección: solo se traslada.
>
> Si el viento sopla a 4 m/s, en 200 segundos la nube ha recorrido 800 m. Eso es todo.

> **🧠 CONCEPTO · Difusión turbulenta**
>
> El ensanchamiento por los remolinos del aire. Es lo que hace que la nube crezca y, al
> crecer, se **diluya**: la misma masa repartida en más volumen = menos concentración.
>
> Es **el mecanismo que baja la concentración**. Sin turbulencia, el penacho sería un hilo
> infinitamente fino y concentrado.

> **⚠️ OJO · La difusión molecular no pinta nada**
>
> En un laboratorio, la difusión molecular (la ley de Fick, la de química) es la
> protagonista. En la atmósfera es **entre 10⁵ y 10⁶ veces más débil** que la turbulenta.
> Se desprecia siempre. Cuando en meteorología se dice "difusión", se quiere decir
> *turbulenta*.

Y hay un cuarto proceso, que en la Parte I ignoraremos y recuperaremos en la sección 8:
que el contaminante **desaparezca** (se deposite, se lave con la lluvia, reaccione).

---

## 3. El viento: advección

> **🔢 VARIABLE · `u` — velocidad del viento**
>
> - **Qué es:** la velocidad media del aire a la altura de interés.
> - **Unidades:** m/s.
> - **Rango típico:** 1–10 m/s. Por debajo de ~0,5 m/s los modelos gaussianos **fallan**
>   (ya verás por qué: `u` está dividiendo).
> - **De dónde sale:** el viento se guarda en dos componentes, `u` (hacia el este) y `v`
>   (hacia el norte). La velocidad es el módulo:
>
> ```
> wspd = √(u² + v²)
> ```
>
> - **En la app:** `u10` y `v10` de ERA5 (el `10` es "a 10 metros de altura").

> **🧠 CONCEPTO · Dirección meteorológica del viento**
>
> Una trampa clásica. En meteorología la dirección dice **de dónde VIENE** el viento, no
> hacia dónde va. "Viento del norte" = sopla *desde* el norte *hacia* el sur.
>
> Se mide en grados, 0° = norte, 90° = este, girando **en sentido horario**. Eso es al
> revés que el ángulo de matemáticas de toda la vida (que empieza en el este y gira
> antihorario). De ahí que la conversión lleve dos signos menos y parezca magia:
>
> ```
> wdir = (degrees(arctan2(-u, -v)) + 360) mod 360
> ```
>
> Compruébalo: viento del norte = el aire va hacia el sur = `v = -1`, `u = 0`.
> Sustituye: `arctan2(0, 1) = 0` → 0° = norte. ✔

> **🧠 CONCEPTO · Rosa de los vientos**
>
> El histograma polar de la dirección del viento: cuántas horas al año sopla de cada
> dirección, y con qué fuerza. Es **el resumen de por dónde va a irse el penacho**.
>
> Si la rosa dice que el 40 % del tiempo el viento viene del noroeste, el pueblo del
> sureste se come el 40 % del penacho. Antes de calcular nada, mirar la rosa ya te dice
> quién va a quejarse.
>
> **En la app:** las capas 🌹 de la pestaña AERMET (una por fuente de datos, para poder
> compararlas entre sí).

### Perfil vertical del viento

El viento no sopla igual a 2 m que a 100 m: el suelo lo frena por rozamiento. En
condiciones neutras el perfil es **logarítmico**:

```
u(z) = (u* / k) · ln(z / z₀)
```

> **🔢 VARIABLE · `z₀` — longitud de rugosidad**
>
> - **Qué es:** un número que resume "cuán rugoso" es el suelo para el viento. Sale de
>   ajustar la ecuación de arriba a mediciones, así que no tiene significado literal (no
>   es la altura de los obstáculos, es del orden de 1/10 de ella).
> - **Unidades:** m.
> - **Rango típico:** 0,0002 (agua en calma) · 0,03 (hierba) · 0,1–0,5 (cultivos,
>   matorral) · 1–2 (bosque, ciudad).
> - **En la app:** se deduce del **uso del suelo** (CORINE) que descarga `getTerrain`.
>   Por eso la herramienta baja el mapa de usos y no solo la elevación.

> **⚠️ OJO · La rugosidad importa MUCHO más en emisiones bajas**
>
> Para una chimenea de 80 m, `z₀` es casi un detalle. Para una **pila de compostaje que
> emite a 2 m**, el penacho vive entero dentro de la capa rugosa: `z₀` gobierna el viento
> que se lo lleva y la turbulencia que lo diluye. En estudios de olor, acertar con el uso
> del suelo **no es cosmética**.

> **🔢 VARIABLE · `k` — constante de von Kármán**
>
> Vale **0,4**. Constante empírica que aparece en toda la teoría de la capa límite. No se
> deduce de nada: se midió.

---

## 4. La turbulencia y la estabilidad atmosférica

Aquí está la chicha. **La turbulencia es lo que diluye**, así que necesitamos saber
cuánta hay. Y la hay por dos motivos distintos:

> **🧠 CONCEPTO · Turbulencia mecánica**
>
> La que produce el **rozamiento** con el suelo. El viento roza el terreno, se frena
> abajo pero no arriba, y esa diferencia de velocidades genera remolinos.
>
> Más viento y más rugosidad ⇒ más turbulencia mecánica. Es la que manda de noche y con
> viento fuerte.

> **🧠 CONCEPTO · Turbulencia térmica (convectiva)**
>
> La que produce el **calor**. De día el sol calienta el suelo, el suelo calienta el aire
> de abajo, ese aire se vuelve menos denso y **sube** en burbujas. Eso es una térmica —
> lo mismo que usan los buitres y los planeadores para ganar altura.
>
> Es turbulencia muy energética. Es la que manda un mediodía soleado de verano.

Estas dos compiten, y de quién gane depende **todo**:

> **🧠 CONCEPTO · Estabilidad atmosférica**
>
> Piensa en una burbuja de aire que empujas hacia arriba. Al subir se expande (hay menos
> presión) y por tanto se enfría. La pregunta es cómo queda respecto al aire de
> alrededor:
>
> - **Inestable:** la burbuja queda **más caliente** que el entorno → menos densa → sigue
>   subiendo sola. La atmósfera *amplifica* el empujón. Mucha turbulencia, penacho
>   serpenteante ("looping"), gran dilución. → *Día soleado, viento flojo.*
> - **Neutra:** la burbuja queda igual que el entorno → se queda donde la dejaste.
>   Penacho en forma de cono. → *Cielo cubierto o viento fuerte.*
> - **Estable:** la burbuja queda **más fría** que el entorno → más densa → vuelve a
>   bajar. La atmósfera *amortigua* el empujón. Poca turbulencia, penacho fino en cinta
>   ("fanning"), poquísima dilución. → *Noche despejada y en calma.*
>
> **La consecuencia que importa:** la peor situación suele ser la **noche estable con
> calma**. El contaminante no se diluye y se queda pegado al suelo.

> **🧠 CONCEPTO · Por qué las quejas por olor llegan de madrugada**
>
> Junta tres cosas de esta sección y tienes la explicación de casi todos los expedientes
> de olores:
>
> 1. De noche la atmósfera es **estable**: no diluye.
> 2. La capa de mezcla se hunde a 100–200 m: el volumen disponible se desploma.
> 3. En valles aparece el **viento catabático**: aire frío que baja por las laderas,
>    flojo y persistente, siempre en la misma dirección.
>
> Resultado: el penacho de una planta que emite a ras de suelo viaja **concentrado,
> pegado al terreno y siempre hacia el mismo sitio**. Por eso las denuncias son casi
> siempre "de madrugada" y "siempre en la misma casa". No es casualidad: es física.

### Cómo se mide todo eso con dos números

La teoría moderna (la que usa AERMOD, y por eso descargamos lo que descargamos) resume
el estado de la atmósfera en dos variables:

> **🔢 VARIABLE · `u*` — velocidad de fricción** *(se lee "u estrella")*
>
> - **Qué es:** la medida de la **turbulencia mecánica**. No es una velocidad que puedas
>   medir con un anemómetro: es la tensión de rozamiento del viento sobre el suelo,
>   expresada con unidades de velocidad (`u* = √(τ/ρ)`).
> - **Unidades:** m/s.
> - **Rango típico:** 0,05 (calma) a 1 (temporal). Suele rondar `u/10`.
> - **En la app:** `zust` de ERA5.

> **🔢 VARIABLE · `H` — flujo de calor sensible**
>
> - **Qué es:** la medida de la **turbulencia térmica**. Cuánta energía por segundo y m²
>   pasa del suelo al aire (o al revés).
> - **Unidades:** W/m².
> - **Signo (¡cuidado!):** en dispersión, **positivo = hacia arriba** = el suelo calienta
>   el aire = día = inestable. Negativo = noche = estable.
> - **Rango típico:** −50 W/m² (noche) a +400 W/m² (mediodía de verano).
> - **En la app:** `sshf` de ERA5 — **pero ERA5 usa el signo contrario** (positivo hacia
>   abajo). Por eso el conversor hace `H = -sshf`. Es exactamente el tipo de detalle que,
>   si se te pasa, te da un modelo que funciona y da resultados al revés.

Y con esos dos se construye el número que lo resume todo:

> **📐 TEORÍA · La longitud de Monin-Obukhov `L`**
>
> La joya de la corona de la micrometeorología. Combina las dos turbulencias en una sola
> magnitud, con unidades de longitud:
>
> ```
>           u*³ · T · ρ · cp
> L = −  ─────────────────────
>              k · g · H
> ```
>
> donde `T` es la temperatura (K), `ρ` la densidad del aire (~1,2 kg/m³), `cp` el calor
> específico (~1005 J/kg·K), `k` = 0,4 y `g` = 9,81 m/s².
>
> **Qué significa físicamente:** `|L|` es *la altura a la que la turbulencia térmica
> empieza a ganarle a la mecánica*. Por debajo manda el rozamiento; por encima, las
> térmicas.
>
> **Cómo se lee el signo:** fíjate en el `−` de delante y en que `u*³`, `T`, `ρ`, `cp`,
> `k` y `g` son todos positivos → **el signo de `L` es el contrario al de `H`**:
>
> | Situación | `H` | `L` | Turbulencia |
> |---|---|---|---|
> | Día soleado | > 0 | **< 0** | Inestable, mucha |
> | Cubierto / viento fuerte | ≈ 0 | **→ ±∞** | Neutra |
> | Noche despejada | < 0 | **> 0** | Estable, poca |
>
> Y sí: en condiciones neutras `L` se va a infinito. Es feo pero correcto — significa "la
> térmica no manda a ninguna altura".

> **🔢 VARIABLE · `zi` — altura de la capa de mezcla**
>
> - **Qué es:** la altura del "techo" invisible de la atmósfera. Por debajo el aire se
>   mezcla; por encima, no. El contaminante **rebota** en ese techo y no lo atraviesa.
> - **Unidades:** m.
> - **Rango típico:** 100–300 m (noche estable) · 1000–2000 m (tarde de verano).
> - **Por qué importa tanto:** es el volumen en el que se reparte todo lo que emites. Una
>   capa de mezcla de 100 m concentra **diez veces más** que una de 1000 m. Las peores
>   crisis de contaminación urbana son episodios de capa de mezcla baja.
> - **En la app:** `blh` (*boundary layer height*) de ERA5.

---

## 5. El modelo gaussiano

Ya tenemos la física. Vamos con las cuentas. Empezamos por el caso más simple —una fuente
**puntual**— y en la sección 6 lo generalizamos a todo lo demás.

### 5.1 ¿Por qué una campana de Gauss?

> **📐 TEORÍA · De dónde sale la campana**
>
> Sigue una molécula concreta del penacho. La empuja el viento (advección: siempre hacia
> adelante) y la zarandean los remolinos (turbulencia: **al azar**, a un lado y a otro).
>
> Cada segundo esa molécula da un pasito aleatorio en `y`. Su posición tras N pasos es
> **la suma de N variables aleatorias independientes**. Y el Teorema Central del Límite
> dice que esa suma tiende a una **distribución normal**, sea cual sea la forma de cada
> paso.
>
> Es decir: la campana de Gauss no se elige por comodidad ni por ajustar bien. **Sale
> sola** de que la turbulencia sea aleatoria. Es el mismo argumento del paseo aleatorio
> que hay detrás del movimiento browniano.

> **⚠️ OJO · El penacho NO se ensancha como √x (y es un error que se lee mucho)**
>
> El paseo aleatorio de libro dice que la desviación típica crece con **√t**, y es
> tentador concluir que `σy ∝ √x`. **Es falso cerca de la fuente**, y conviene entender
> por qué.
>
> El paseo aleatorio supone que cada pasito es **independiente** del anterior. Pero un
> remolino atmosférico no funciona así: si una molécula queda atrapada en un remolino, se
> va con él **de forma coherente** durante un rato. Los pasos están *correlacionados*.
>
> La teoría de Taylor (1921) lo resuelve con un tiempo característico `TL` (cuánto
> "recuerda" una partícula su velocidad):
>
> | Régimen | Comportamiento | Crecimiento |
> |---|---|---|
> | **Cerca** (`t ≪ TL`) | la partícula viaja con su remolino | `σ ∝ t` → **lineal** |
> | **Lejos** (`t ≫ TL`) | ya olvidó su velocidad inicial: paseo aleatorio de verdad | `σ ∝ √t` |
>
> Y no es teoría de salón: las curvas empíricas de Pasquill-Gifford dan `σy ≈ a·x^0.9`,
> o sea **casi lineal** — mucho más cerca de Taylor que del √x. Los datos le dan la razón.
>
> Moraleja: la campana **sí** sale del argumento aleatorio, pero **la velocidad a la que
> crece, no**. Por eso `σy` y `σz` hay que medirlos o calcularlos con la física de la capa
> límite (§5.4), y no se pueden deducir del paseo aleatorio.

### 5.2 La ecuación

> **📐 TEORÍA · Ecuación de la pluma gaussiana (fuente puntual)**
>
> ```
>                  Q                ⎡    y²  ⎤   ⎧    ⎡ −(z−H)² ⎤       ⎡ −(z+H)² ⎤ ⎫
> C(x,y,z) = ───────────────  · exp ⎢ − ──── ⎥ · ⎨ exp⎢ ─────── ⎥ + exp ⎢ ─────── ⎥ ⎬
>             2π · u · σy · σz      ⎣   2σy² ⎦   ⎩    ⎣  2σz²   ⎦       ⎣  2σz²   ⎦ ⎭
> ```
>
> Da miedo, pero son cuatro trozos y cada uno dice algo simple.

**El sistema de coordenadas** (importante, y es lo que hace la fórmula tan compacta): el
eje `x` **se coloca a favor del viento**, saliendo de la fuente. Así:

- `x` = distancia viento abajo (m)
- `y` = distancia lateral, perpendicular al viento (m); `y=0` es el eje del penacho
- `z` = altura sobre el suelo (m)

**Trozo 1 — el factor `Q / (2π·u·σy·σz)`: la dilución.**

- `Q` arriba: el doble de emisión, el doble de concentración. Lineal. Obvio.
- `u` abajo: **el doble de viento, la mitad de concentración**. No es tan obvio, pero es
  puro sentido común: si el viento va el doble de rápido, la misma masa que sale por
  segundo se estira sobre el doble de longitud → la mitad por metro.
- `σy·σz` abajo: es el **área** de la sección del penacho. Cuanto más gordo, más diluido.

> **⚠️ OJO · Por qué el modelo revienta en calma**
>
> `u` está en el denominador. Si `u → 0`, entonces `C → ∞`: concentración infinita, lo
> cual es absurdo.
>
> Físicamente el fallo es que si no hay viento **no hay una dirección** hacia la que
> mandar el penacho, y toda la construcción se cae. Por eso los modelos gaussianos
> imponen un `u` mínimo (~0,5 m/s) y marcan esas horas como *calmas*, que se excluyen.
>
> **Y esto es un problema serio justo en olores:** las peores situaciones reales son
> noches de calma… que es exactamente cuando el modelo se declara incompetente y no
> calcula. Se maquilla con el `u` mínimo, pero conviene saber que ahí el resultado es el
> más flojo de todos.

**Trozo 2 — `exp(−y²/2σy²)`: la campana horizontal.** Máxima en el eje (`y=0`) y cae hacia
los lados. En `y = σy` ya has bajado al 61 %; en `y = 2σy`, al 14 %.

**Trozo 3 — `exp(−(z−H)²/2σz²)`: la campana vertical.** Igual, centrada en `H`, la altura
a la que va el penacho.

**Trozo 4 — `exp(−(z+H)²/2σz²)`: la reflexión.** Merece casilla propia.

> **📐 TEORÍA · El método de las imágenes (la reflexión en el suelo)**
>
> Problema: el penacho se ensancha hacia abajo, pero **el suelo no deja pasar el
> contaminante**. ¿Qué pasa con la masa que "debería" ir por debajo de z=0?
>
> Como no se deposita (lo asumimos), tiene que **rebotar**. Matemáticamente, la condición
> "flujo nulo en el suelo" se cumple con un truco elegantísimo que quizá hayas visto en
> electrostática o en óptica: **te inventas una fuente imagen**, idéntica, enterrada a la
> misma distancia por debajo del suelo (a `−H`).
>
> ```
>          fuente real  ●  ← H
>       ═══════════════════════  suelo (z=0)
>          fuente imagen ○  ← −H
> ```
>
> La suma de las dos campanas da automáticamente flujo neto nulo en `z=0`, que es lo que
> queríamos. La imagen no existe: es un artificio para imponer el rebote.
>
> Consecuencia práctica fuerte: **en el suelo, la reflexión DUPLICA la concentración**.
>
> Y ojo: si `zi` es baja, el penacho rebota **también** en el techo de la capa de mezcla,
> luego otra vez en el suelo… Hay que meter infinitas imágenes. En la práctica, cuando
> `σz > 1,6·zi` se da la mezcla por uniforme en la vertical y se sustituye todo por
> `C = Q/(√(2π)·u·σy·zi)`.

### 5.3 El caso que de verdad importa

A ras de suelo (`z = 0`) y en el eje (`y = 0`), los dos exponenciales se hacen iguales y
la fórmula colapsa a:

```
                Q            ⎡   −H²  ⎤
C(x, 0, 0) = ───────── · exp ⎢ ────── ⎥
              π·u·σy·σz      ⎣  2σz²  ⎦
```

Esta es **la ecuación con la que se trabaja el 90 % del tiempo**, porque la gente respira
a ras de suelo. El `2π` se ha convertido en `π`: eso es la duplicación por reflexión.

> **🧠 CONCEPTO · Dónde está el máximo (y por qué depende tantísimo de `H`)**
>
> Mira la fórmula pensando en qué pasa según te alejas:
>
> - **Cerca:** `σz` es pequeñísimo → `−H²/2σz²` es muy negativo → `exp(...)` ≈ 0. **No
>   llega nada al suelo**: el penacho aún va por arriba.
> - **Lejos:** `σy` y `σz` son enormes y están dividiendo → `C → 0`. Todo diluido.
> - **En medio** hay un **máximo**.
>
> Ese máximo, y a qué distancia cae, es *la respuesta* que busca un estudio de impacto.
>
> Pero fíjate en el papel de `H`, porque aquí se separan los dos mundos:
>
> | | `H` grande (chimenea) | `H` ≈ 0 (compostaje, EDAR) |
> |---|---|---|
> | `exp(−H²/2σz²)` cerca | ≈ 0 | **≈ 1** |
> | Máximo | lejos (cientos de m o km) | **pegado a la fuente** |
> | Valor del máximo | moderado | **alto** |
>
> Con `H → 0` el exponencial vale 1 desde el primer metro: **no hay protección ninguna**.
> La concentración es máxima justo al lado y solo puede bajar. Por eso una planta de
> compostaje molesta a sus vecinos inmediatos y una chimenea alta no.
>
> Y de ahí la regla de oro clásica: **subir `H` aleja y rebaja el máximo**, porque `H` va
> al cuadrado dentro de una exponencial negativa. Doblar la altura no reduce el máximo a
> la mitad: lo reduce muchísimo más. El problema es que en una balsa o una pila **no
> puedes subir `H`**: es lo que hay.

> **📐 TEORÍA · Comprobación de que no perdemos masa**
>
> Un modelo que se invente o pierda contaminante no vale. Integra la concentración sobre
> todo el plano perpendicular al viento (todos los `y`, todos los `z ≥ 0`). Usando
> `∫exp(−a²/2σ²)da = σ√(2π)`:
>
> ```
> ∫∫ C · u · dy dz = Q
> ```
>
> Sale `Q` exactamente. La masa se conserva: todo lo que emites cruza cada sección del
> penacho. Los `σ` solo la **redistribuyen**, no la destruyen. Si alguna vez tocas la
> fórmula, esta integral es tu red de seguridad.

### 5.4 Los coeficientes de dispersión

> **🔢 VARIABLE · `σy`, `σz` — coeficientes de dispersión**
>
> - **Qué son:** las desviaciones típicas de la campana, lateral y vertical. En cristiano:
>   **cómo de gordo es el penacho** a una distancia `x`.
> - **Unidades:** m. Y **crecen con `x`**: no son constantes, son funciones.
> - **Por qué son la pieza clave:** todo lo demás de la fórmula es geometría y
>   conservación de masa. **Toda la física de la turbulencia está metida aquí dentro.**
>   Acertar con `σy` y `σz` *es* el problema de la dispersión.

> **📈 CORRELACIÓN · Las curvas de Pasquill-Gifford**
>
> El enfoque clásico (años 60), puramente empírico: se soltaron trazadores en el campo, se
> midió el penacho y se ajustaron curvas de la forma
>
> ```
> σy = a · x^b
> ```
>
> agrupando el tiempo en seis **clases de estabilidad**, de la A a la F:
>
> | Clase | Situación | Turbulencia |
> |---|---|---|
> | A | Sol fuerte, viento flojo | Muy inestable |
> | B, C | Intermedias | Inestable |
> | D | Cubierto o viento fuerte | Neutra |
> | E, F | Noche despejada y calma | Estable |
>
> **Es una correlación, no una teoría:** funciona razonablemente en terreno llano y
> abierto parecido a donde se midió, y no tiene por qué funcionar fuera de ahí. Y meter la
> atmósfera en seis cajones es brutalmente basto: la atmósfera es continua.

> **🔗 EN LA HERRAMIENTA · Por qué AERMOD no usa Pasquill**
>
> Aquí está la razón de ser de media herramienta. **AERMOD no usa clases de estabilidad.**
> Calcula `σy` y `σz` de forma **continua** desde la física real de la capa límite: `u*`,
> `L`, `zi` y `w*` (velocidad convectiva).
>
> Por eso el paquete que descarga `getMeteo` es el que es: `zust` (=`u*`), `sshf` (→`H`
> →`L`), `blh` (=`zi`). **No son variables decorativas: son literalmente los ingredientes
> de `σy` y `σz`.** Sin ellas, AERMOD no sabría cómo de gordo es el penacho.
>
> Y en condiciones convectivas va más allá: **abandona la gaussiana en la vertical** y usa
> una bi-gaussiana asimétrica, porque en una térmica el aire sube rápido en columnas
> estrechas y baja despacio en zonas anchas. La realidad no es simétrica, y se nota.

---

# Parte II — Las fuentes reales

## 6. Tipos de fuente

La ecuación de §5.2 es para un **punto**. Casi ninguna fuente real lo es. Pero hay una
propiedad que nos salva:

> **📐 TEORÍA · Superposición: la clave para generalizar**
>
> La ecuación de dispersión es **lineal** en `Q`. Y en un problema lineal vale el
> principio de superposición: *la solución de la suma es la suma de las soluciones*.
>
> Consecuencia práctica enorme: **cualquier fuente se puede construir como una suma (o
> integral) de fuentes puntuales.** No hace falta una teoría nueva por cada geometría, ni
> por cada foco adicional.
>
> Por eso, para varias fuentes, `C_total = Σ C_i`. Sin más. Y por eso puedes calcular el
> impacto de una planta entera con veinte focos sumando veinte penachos.
>
> (Esto deja de valer en cuanto el contaminante **reacciona**, porque la química no es
> lineal: dos penachos de NOx que se cruzan no dan la suma de sus ozonos. Ver §8.)

### 6.1 Fuente puntual

El caso de §5: una chimenea, un extractor, un venteo. Se describe con posición, `hs`, y
—si los gases son calientes o rápidos— `ds`, `Ts`, `vs` para la sobreelevación (§7).

**En la app:** el modo 📍 *Punto* de AERSOURCE.

### 6.2 Fuente de área ← *la reina de los estudios de olor*

Una pila de compostaje, un decantador de EDAR, una balsa, la celda de un vertedero, un
acopio. Emite por **toda una superficie**, no por un punto.

> **📐 TEORÍA · Cómo se resuelve un área**
>
> Se integra la solución puntual sobre la superficie:
>
> ```
> C_área(receptor) = ∫∫  C_punto(x−x', y−y') · q · dx' dy'
>                    A
> ```
>
> donde `q` es la emisión **por unidad de superficie** (g/s·m²). AERMOD lo hace
> numéricamente, con un algoritmo de integración adaptativo.
>
> **Por qué no vale aproximarla por un punto equivalente en el centro:** para un receptor
> **lejano** sí (a 5 km, una pila de 50 m es un punto). Pero para el vecino que está a
> 100 m de una pila de 200 m de largo, la diferencia es abismal: el punto equivalente le
> daría una concentración disparatada, y el área le da la contribución repartida. **Y el
> vecino cercano es justo el que se queja.**

> **🧠 CONCEPTO · El límite de "caja" de un área muy grande**
>
> Un caso que ayuda a entender la física. Imagina un área **enorme** (un vertedero de
> kilómetros) y un receptor en medio. El penacho ya no crece: lo que ganas de dispersión
> lo compensa el área nueva que vas pisando. La concentración tiende a un valor de
> equilibrio del estilo
>
> ```
> C ≈ q · x / (u · zi)     [modelo de caja]
> ```
>
> Que se lee bien: emisión por unidad de área × recorrido, dividido por el caudal de aire
> que barre la capa de mezcla. **Nada que ver con la fórmula de la chimenea**, y muestra
> que en áreas grandes los que mandan son `zi` y `u`, no `σz`.

**En la app:** el modo ▭ *Área* de AERSOURCE. Dibujas el polígono con clics y el caudal va
en **g/(s·m²)**. Corresponde a una fuente **AREAPOLY** de AERMOD (máx. 20 vértices).

### 6.3 Fuente de volumen

Una nave ganadera con ventilación difusa, un edificio con fugas repartidas, una cinta
transportadora. La emisión no sale de una superficie plana sino de un **volumen**, y ya
sale "pre-dispersada" por la turbulencia del propio recinto.

> **📐 TEORÍA · El truco de la fuente virtual**
>
> Se modela como una fuente puntual… **que ya nace gorda**: se le asignan unas
> dispersiones iniciales `σy0`, `σz0` del tamaño del recinto.
>
> ¿Y cómo se mete un `σ` inicial en una fórmula donde `σ` solo depende de `x`? Con un
> truco precioso: se coloca una **fuente virtual** *aguas arriba*, a la distancia `xv` a
> la que el penacho habría alcanzado ese `σ0` por sí solo:
>
> ```
>     fuente virtual          fuente real
>          ✕ ·  ·  ·  ·  ·  ·  ·  ▣ ═══════▶
>       (no existe)          (σ ya vale σ0)
>       |◀─── xv ───▶|
> ```
>
> A partir de ahí se aplica la fórmula normal midiendo desde la virtual. El penacho llega
> a la fuente real con el grosor correcto. Otra vez: no hace falta teoría nueva, basta con
> mover el origen.

**En la app:** no implementado hoy (solo punto y área).

### 6.4 Fuente lineal

Una carretera, una zanja. Es el caso 1-D: se integra la puntual a lo largo de una línea, o
se aproxima por una ristra de fuentes de área.

**En la app:** no implementado hoy.

---

## 7. ¿Sube el penacho?

Habíamos usado `H` como "la altura del penacho". Pero:

```
H = hs + Δh
```

Y `Δh` es donde se separan radicalmente la chimenea y todo lo demás.

> **🧠 CONCEPTO · Sobreelevación (`Δh`, *plume rise*)**
>
> Los humos de una chimenea **salen subiendo**, y siguen subiendo un rato antes de
> plegarse al viento. Por dos motivos:
>
> - **Empuje térmico (*buoyancy*):** los gases salen calientes (400–500 K frente a los
>   ~290 K del aire). Menos densos ⇒ flotan ⇒ suben. Es el mecanismo dominante.
> - **Cantidad de movimiento:** salen disparados a 10–20 m/s, y esa inercia los eleva.
>
> No es un detalle: `Δh` puede ser **mayor que `hs`**. Y como `H` va al cuadrado dentro de
> una exponencial, equivocarse aquí lo estropea todo.

> **📈 CORRELACIÓN · Las fórmulas de Briggs**
>
> El estándar desde los 70. Primero, el **flujo de flotabilidad**:
>
> ```
>            ds²        Ts − Ta
> F = g · vs · ─── · ───────────      [m⁴/s³]
>             4          Ts
> ```
>
> Ahí ves los ingredientes: **si `Ts = Ta` (gases fríos), `F = 0`** y no hay empuje
> térmico. Guarda esta frase.
>
> Y la sobreelevación mientras el penacho aún sube:
>
> ```
>          F^(1/3) · x^(2/3)
> Δh = 1,6 · ─────────────────
>                  u
> ```
>
> Léela: **más viento, menos sobreelevación** (`u` divide) — el viento tumba el penacho. Y
> el `1,6` es un número ajustado a medidas de campo: por eso esto es una correlación, no
> una teoría.
>
> El penacho no sube indefinidamente: a una distancia `xf` se estabiliza y `Δh` se congela.

> **🧠 CONCEPTO · Emisión pasiva: el caso de compostaje, EDAR y balsas**
>
> Ahora aplica lo anterior a una pila de compostaje o un decantador:
>
> - `Ts ≈ Ta` → `F ≈ 0` → **sin empuje térmico**
> - `vs ≈ 0` (no hay chorro, el gas rezuma de una superficie) → **sin empuje por
>   cantidad de movimiento**
> - ⇒ **`Δh ≈ 0`** ⇒ **`H ≈ hs`**, que además vale 0–3 m
>
> A esto se le llama **emisión pasiva**: el contaminante se comporta como un trazador que
> simplemente se deja llevar. Y junta esto con lo que vimos en §5.3 (`exp(−H²/2σz²) ≈ 1`
> cuando `H≈0`):
>
> **Una fuente pasiva a ras de suelo es el peor escenario posible para el vecino
> cercano.** Sin sobreelevación que la aleje, sin altura que la proteja, con el máximo
> pegado a la valla. No hay ningún truco de diseño que lo arregle desde la dispersión: o
> reduces `Q` (cubrir, biofiltro, aspirar) o alejas la instalación.
>
> Y una ironía útil: para una EDAR, **cubrir los tanques y sacar el aire por una chimenea
> con un biofiltro** no solo reduce `Q` — además convierte una fuente pasiva a ras de
> suelo en una fuente puntual elevada, que dispersa muchísimo mejor. Se gana por los dos
> lados.

> **⚠️ OJO · El compostaje sí está caliente (pero no lo suficiente)**
>
> Una pila de compostaje en fase termófila está a **50–70 °C**: hay contraste térmico
> real. ¿No debería haber empuje?
>
> Un poco sí, pero es despreciable frente a una chimenea, y por dos motivos: (1) el gas no
> sale en chorro, sino que rezuma por la superficie a velocidad casi nula; y (2) se mezcla
> con el aire ambiente **en los primeros centímetros**, perdiendo el contraste enseguida.
>
> La práctica habitual es modelarlas como **áreas pasivas**. Algunas guías admiten una
> pequeña sobreelevación, pero es un refinamiento de segundo orden. Si dudas, la hipótesis
> conservadora (la que da más concentración) es `Δh = 0`.

> **🔢 VARIABLE · Los datos de fuente que pide la app, y cuándo importan**
>
> | Campo (AERSOURCE) | Símbolo | Para qué | ¿Importa en compostaje/EDAR? |
> |---|---|---|---|
> | Altura emisión | `hs` | la base de `H` | **Sí** (y vale 0–3 m) |
> | Caudal | `Q` | la emisión | **Sí, es lo que más** |
> | Ø chimenea | `ds` | sección de salida → `F` | No (`F≈0`) |
> | Tª gas | `Ts` | contraste de densidad → `F` | No (`Ts≈Ta`) |
> | Vel. salida | `vs` | empuje por inercia | No (`vs≈0`) |
>
> Los tres últimos existen **solo para calcular `Δh`**. En una fuente pasiva puedes
> dejarlos a sus valores por defecto: no van a hacer nada, porque `Ts−Ta ≈ 0` anula `F`.

---

## 8. Cuando el contaminante no se conserva

Hasta aquí hemos supuesto un gas **inerte**: ni se pega al suelo, ni se lava, ni
reacciona. Vale para muchos casos (SO₂ a corta distancia, un trazador, la mayoría de
olores en 1–2 km). Pero no siempre.

> **🧠 CONCEPTO · Deposición seca**
>
> El contaminante **toca el suelo y se queda**: lo absorbe la vegetación, se pega al
> terreno. Se modela con una **velocidad de deposición** `vd` (cm/s), que no es una
> velocidad real sino una constante de proporcionalidad: `flujo = vd · C`.
>
> Rompe la hipótesis de la reflexión perfecta de §5.2: ya no rebota **todo**. El truco de
> la fuente imagen se corrige con un factor, o se resuelve con una imagen "parcial".
>
> Importa mucho en **partículas** (PM10, polvo de cantera: pesan y caen) y en gases muy
> solubles (NH₃). Poco en gases inertes.

> **🧠 CONCEPTO · Deposición húmeda**
>
> La lluvia **lava** el penacho. Se modela con un coeficiente de lavado `Λ` (s⁻¹):
> `C(t) = C₀·exp(−Λt)`.
>
> Suele ser un efecto de segundo orden en distancias cortas… salvo que estés estudiando
> justo la deposición (lluvia ácida, aporte de nitrógeno a un espacio protegido).

> **🧠 CONCEPTO · Decaimiento y reacción química**
>
> Algunas especies **se transforman**. Lo más simple es un decaimiento exponencial de
> primer orden, con una vida media `t½`:
>
> ```
> C = C_gauss · exp(−λ·t) ,   λ = ln2 / t½ ,   t = x/u
> ```
>
> Basta multiplicar el resultado gaussiano por ese factor.
>
> Ejemplo relevante para olores: el **H₂S se oxida** en la atmósfera, con vida media de
> horas. A pocos cientos de metros da igual; a 10 km, no.

> **⚠️ OJO · Donde el gaussiano se rinde: la química no lineal**
>
> El decaimiento exponencial vale porque es **lineal** (§6, superposición). Pero la
> química de verdad no lo es.
>
> El ejemplo canónico es el **NO₂**: una chimenea emite sobre todo NO, que solo se
> convierte en NO₂ reaccionando con el **ozono del entorno**. O sea que la concentración
> de NO₂ depende de cuánto ozono haya, que a su vez depende del sol, de otras fuentes…
> **No es una función de tu penacho solo.** La superposición se cae.
>
> AERMOD lo apaña con esquemas semi-empíricos (OLM, PVMRM, ARM2) que reparten el NO
> según el ozono disponible. Son parches razonables, no química de verdad. Para eso hacen
> falta modelos fotoquímicos (CMAQ, CAMx), que juegan en otra liga de coste.

---

# Parte III — Olores

## 9. Olores: por qué son otro problema

Un estudio de olor **no es un estudio de contaminantes con otro número**. Cambia la
magnitud, cambia el criterio y cambia hasta la escala de tiempo. Es donde más se
equivoca la gente que viene de chimeneas.

> **🔢 VARIABLE · `ou_E` — unidad de olor europea**
>
> - **Qué es:** la magnitud del olor. Y es **sensorial, no química**: no mide moléculas,
>   mide *cuánto huele para una nariz humana*.
> - **Cómo se define (norma EN 13725):** se coge la muestra de aire y se diluye con aire
>   limpio hasta que **la mitad de un panel de personas** entrenadas deja de detectarla.
>   El número de diluciones necesarias **es** la concentración en `ou_E/m³`.
> - **La consecuencia elegante:** el **umbral de detección vale exactamente
>   `1 ou_E/m³`**, por construcción. Si en un punto sale 1, ahí lo huele la mitad de la
>   gente. Si sale 5, huele claramente.
> - **Unidades del término fuente:** `ou_E/s` o, en áreas, **`ou_E/(s·m²)`**.
>
> Lo bonito: **la dispersión no se entera**. `ou_E` se transporta y se diluye como si
> fueran gramos, porque las ecuaciones son lineales y les da igual la unidad. Puedes usar
> AERMOD tal cual, metiendo `Q` en `ou_E/s` y leyendo `C` en `ou_E/m³`.

> **⚠️ OJO · El problema del pico y la media (esto es LO importante)**
>
> Si te quedas con una sola idea de esta sección, que sea esta.
>
> **AERMOD calcula medias horarias.** La nariz humana detecta en **menos de 5 segundos**.
>
> Y la concentración instantánea **no** es la media: el penacho serpentea y late, de forma
> que en un punto pasas de nada a una bocanada intensa y otra vez a nada. La media horaria
> puede ser 0,5 ou_E/m³ —"no huele"— mientras la realidad son **bocanadas de 5 ou_E/m³
> durante unos segundos, varias veces por hora**. Y esas bocanadas son las que generan la
> denuncia.
>
> Se corrige con un **factor pico-media** `F = C_pico / C_media`:
>
> | Situación | `F` típico |
> |---|---|
> | Cerca de la fuente, atmósfera estable | **hasta 10** (o más) |
> | Lejos, atmósfera inestable | 2–3 |
>
> `F` **crece con la estabilidad y decrece con la distancia** (lejos, el penacho ya se ha
> mezclado y sus picos se han limado). Hay formulaciones para estimarlo
> (Smith, Best, Schauberger…).
>
> **La moraleja:** un mapa de medias horarias de olor **infravalora sistemáticamente la
> molestia**, y más justo en las condiciones (noche estable, cerca) que provocan las
> quejas. Si presentas medias horarias sin corregir, estás contando una película optimista.

> **🧠 CONCEPTO · Percentiles: el criterio no es el máximo**
>
> Para un tóxico se compara el **máximo** con un límite. Para el olor no tiene sentido:
> que huela una hora al año no molesta a nadie.
>
> Se usan criterios de **frecuencia**, con esta forma:
>
> > *"El percentil 98 de las medias horarias del año no debe superar X ou_E/m³ en zona
> > residencial."*
>
> Léelo: el percentil 98 significa que **el 2 % de las horas del año (unas 175 h) sí
> superan X**, y se acepta. Es un criterio de *molestia tolerable*, no de seguridad.
>
> El valor de X y el percentil **cambian según la comunidad autónoma o el país** (típico:
> P98, con X entre 1 y 5 ou_E/m³, más estricto en residencial que en industrial). No hay
> un número universal: hay que mirar la normativa aplicable.
>
> **Consecuencia para la herramienta:** no basta con simular el peor caso. Hacen falta
> **8760 horas del año completo** para poder sacar un percentil. De ahí que `getMeteo`
> baje años enteros y no un día bonito.

> **🧠 CONCEPTO · El olor no es proporcional a la concentración**
>
> Un último clavo. La intensidad *percibida* de un olor sigue la **ley de Stevens**:
>
> ```
> I = k · C^n        con n ≈ 0,2 – 0,7
> ```
>
> Con `n = 0,5`, **cuadruplicar la concentración solo duplica la intensidad percibida**.
>
> Lo que significa en la práctica: si una planta reduce su emisión un 50 %, el vecino
> **no** percibe la mitad de olor — percibe un 30 % menos, y probablemente siga quejándose.
> Las medidas correctoras de olor tienen que ser **agresivas** para notarse. Es una
> conversación incómoda que conviene tener pronto.

---

## 10. Mezclas de gases

Casi ninguna fuente real emite una sola sustancia. Una EDAR emite H₂S, mercaptanos, NH₃ y
docenas de VOC a la vez. ¿Cómo se trata?

> **📐 TEORÍA · Cada compuesto por separado (mientras no reaccionen)**
>
> Por linealidad (§6), cada especie se dispersa **independientemente** de las demás: no
> se estorban. Así que se ejecuta el modelo una vez por compuesto, con su `Q`, y se
> compara cada `C` con su propio límite.
>
> El truco de la eficiencia: como la dispersión no depende de la especie, el campo
> `C/Q` **es el mismo para todas**. Se calcula una vez y se escala por cada `Q`. (Deja de
> valer si tienen deposición o vida media distintas.)

> **⚠️ OJO · Cada compuesto tiene su umbral, y varían órdenes de magnitud**
>
> Aquí está la trampa. Los umbrales olfativos son **brutalmente distintos**:
>
> | Compuesto | Umbral olfativo aprox. | Nota |
> |---|---|---|
> | **H₂S** (huevo podrido) | ~0,5 **ppb** | se huele muchísimo antes de ser tóxico |
> | Mercaptanos | ~0,1–1 ppb | de los más potentes |
> | **NH₃** (amoniaco) | ~5.000 ppb (5 ppm) | ¡10.000 veces menos oloroso que el H₂S! |
>
> Consecuencia contraintuitiva: en una EDAR, el **NH₃** puede ser el compuesto más
> abundante en masa y el **H₂S** el que causa todas las quejas, estando mil veces más
> diluido. **Ordenar los compuestos por `Q` te lleva a la conclusión equivocada**: hay que
> ordenarlos por `Q/umbral`.

> **⚠️ OJO · Sumar olores no es sumar concentraciones**
>
> Y si quieres el **olor total** de una mezcla, no puedes sumar las contribuciones de cada
> compuesto: los olores no se suman así. Pueden ser **aditivos**, pero también
> **sinérgicos** (juntos huelen más que la suma) o **antagónicos** (uno enmascara a otro).
> No hay una regla general fiable.
>
> **Por eso existe la olfatometría.** Se mide el olor de la mezcla **como un todo**, con
> narices, y se obtiene un único `Q` en `ou_E/s`. Se esquiva el problema en vez de
> resolverlo — que es, honestamente, la decisión correcta.

> **🧠 CONCEPTO · Tóxico vs. molesto: dos estudios distintos**
>
> Un mismo compuesto puede exigir dos análisis con criterios opuestos:
>
> | | Olor (molestia) | Toxicidad (salud) |
> |---|---|---|
> | Magnitud | ou_E/m³ | µg/m³, ppb |
> | Criterio | percentil (P98) | máximo, o media anual |
> | Escala de tiempo | **segundos** (pico) | 1 h, 8 h, 24 h, año |
> | Umbral H₂S | ~0,5 ppb (olfativo) | ~7 ppm = 7.000 ppb (irritación aguda) |
>
> Fíjate en la última fila: para el H₂S, **el olor aparece unas 10⁴ veces antes que el
> riesgo** (con estos valores, ×14.000). Un vecindario puede estar sufriendo un problema
> serio de olor con concentraciones toxicológicamente irrelevantes. Ambas cosas son
> ciertas a la vez, y confundirlas —en cualquiera de los dos sentidos— es el origen de la
> mitad de los conflictos en estos expedientes.
>
> **Y trata estas cifras como órdenes de magnitud, no como constantes.** Los umbrales
> olfativos publicados para el H₂S van de ~0,5 a ~13 ppb (¡un factor 25!) según el estudio
> y el panel, y los límites toxicológicos dependen de la norma y del tiempo de exposición
> que se aplique. Para un expediente real: coge los valores de la normativa vigente que te
> aplique, no de una tabla de una guía.

---

# Parte IV — Los datos de entrada: de dónde sale cada número

> Hasta aquí hemos montado la ecuación y hemos visto que toda la física vive en `σy`, `σz`,
> `u` y `H`. Pero esos símbolos hay que **rellenarlos con números reales** de un sitio real y
> de un año concreto. Esta parte responde a la pregunta que suele quedar colgando:
> **¿por qué descargamos exactamente estos datos y no otros, y qué le pasa al resultado si uno
> está mal?**

---

## 11. Catálogo de variables: qué alimenta cada dato <a id="11-catálogo-de-variables"></a>

La herramienta descarga **once variables meteorológicas horarias** de ERA5, más el terreno y
el uso del suelo. No es una lista arbitraria: **cada una tapa un hueco concreto** de la
cadena que va del viento a la concentración.

> **🧠 CONCEPTO · La cadena completa, de un vistazo**
>
> Ninguna variable entra "directamente" en la ecuación gaussiana. Todas pasan por dos
> intermediarios —**`u*`** (turbulencia mecánica) y **`L`** (estabilidad)— que son los que
> gobiernan `σy` y `σz`:
>
> ```
>  DATOS QUE SE DESCARGAN          SE COMBINAN EN            GOBIERNAN
>
>  u10, v10  ──────────────────►  u, dirección  ───────────►  advección (§3)
>       │
>  zust (u*) ──────────────────►  u*  ──────────┐
>  sshf      ──► H = −sshf ─────►  H   ─────────┤
>  t2m       ──► T ─────────────►  ρ, T ────────┼──►  L  ──►  σy, σz  ──►  C
>  sp        ──► ρ = p/(R·T) ────►  ρ  ─────────┤          (§4, §5.4)
>  z₀ (uso del suelo) ──────────►  u*, perfil ──┘
>       │
>  blh       ──────────────────►  zi (la tapa) ────────────►  reflexión superior
>  ssrd, tcc ──────────────────►  balance de radiación ────►  H (y albedo nocturno)
>  d2m       ──────────────────►  humedad relativa ────────►  (dato de contexto)
>  tp        ──────────────────►  lavado por lluvia ───────►  (§8, hoy NO se usa)
>  elevación ──────────────────►  cota de cada receptor ───►  geometría vertical
> ```

Vamos una por una. Para cada dato: **qué es**, **dónde entra** y **qué pasa si falla**.

### 11.1 Viento a 10 m (`u10`, `v10`) — el transporte

> **🔢 VARIABLE · `u10`, `v10` (m/s)**
>
> Las dos **componentes** del viento a 10 m: `u10` hacia el este, `v10` hacia el norte. No
> vienen como "velocidad y dirección" porque un promedio de direcciones en grados no tiene
> sentido (¿la media de 350° y 10° es 180°?). Con componentes, promediar es sumar vectores.
>
> Se convierten con:
>
> ```
> velocidad:  u = √(u10² + v10²)
> dirección:  θ = atan2(−u10, −v10) · 180/π   (mód 360)
> ```
>
> El **doble signo menos** es la convención meteorológica: la dirección es **de dónde viene**
> el viento, no hacia dónde va. Un viento del norte (θ=0°) empuja el penacho **hacia el sur**.

**Dónde entra:** en el denominador de la ecuación gaussiana (`C ∝ Q/u`) y en la elección de
**hacia dónde** va el penacho. También decide **qué sector de rugosidad** se aplica esa hora
(§12.5).

**Si falla:** es el error más caro de todos. `u` está **dividiendo**: un viento un 30 % bajo
te da una concentración un 43 % alta. Y un error de dirección te pone el penacho encima del
pueblo equivocado.

### 11.2 Temperatura a 2 m (`t2m`) — densidad y estabilidad

> **🔢 VARIABLE · `t2m` (K, se maneja en °C)**
>
> La temperatura del aire a 2 m. Entra en tres sitios:
> 1. La **densidad del aire** `ρ` (ver §11.6).
> 2. La **longitud de Monin-Obukhov** `L` (aparece explícitamente en la fórmula).
> 3. El **contraste térmico** de la sobreelevación: `Δh` depende de `(Ts − Ta)` (§7). Si los
>    gases salen a 450 K y el ambiente está a 280 K, el empuje es enorme; en agosto a 310 K,
>    bastante menor.

**Si falla:** el efecto es de segundo orden salvo en el `Δh` de chimeneas calientes. Un error
de 2-3 K apenas se nota.

### 11.3 Flujo de calor sensible (`sshf`) — el motor de la convección

> **🔢 VARIABLE · `sshf` → `H` (W/m²)**
>
> Es **cuánto calor pasa del suelo al aire**. Es *la* variable que decide si la atmósfera
> hierve o está dormida:
>
> - **`H > 0`** (día soleado): el suelo calienta el aire, suben térmicas → **convectivo**,
>   mezcla intensa, penacho que serpentea y toca suelo a rachas.
> - **`H < 0`** (noche despejada): el suelo se enfría, el aire de abajo se queda frío y
>   pesado → **estable**, sin mezcla, el penacho viaja como una cinta.
>
> **⚠️ El signo:** ERA5 da los flujos **positivos hacia abajo**, y AERMOD los quiere
> **positivos hacia arriba**. Por eso en el código se escribe `H = −sshf`. Equivocarse de
> signo aquí es catastrófico: convertiría todos los días en noches y viceversa. *Comprobado
> en el caso de Lleida:* `H > 0` de día (hasta +515 W/m²) y `H < 0` de noche. ✅

**Dónde entra:** en `L` (abajo) y en la velocidad convectiva `w*`:

```
w* = [ g · H · zi / (ρ · cp · T) ]^(1/3)
```

`w*` es la velocidad típica de una térmica ascendente. Solo tiene sentido con `H > 0`; por eso
en las horas estables se escribe como **dato ausente** (y no ponerlo así fue la causa real de
un aviso persistente de AERMOD — ver `notas_perfil_vertical.md §1`).

### 11.4 Velocidad de fricción (`zust`, `u*`) — la turbulencia mecánica

> **🔢 VARIABLE · `zust` → `u*` (m/s)**
>
> La **velocidad de fricción**: una medida de cuánta turbulencia genera el **rozamiento** del
> viento contra el suelo. Es el "otro motor" de la mezcla, el que funciona aunque no haya sol.
>
> Físicamente es la raíz de la tensión de cizalla dividida por la densidad, y define el
> **perfil logarítmico del viento** (§3):
>
> ```
> u(z) = (u* / k) · ln(z / z₀)          k = 0,41 (constante de von Kármán)
> ```
>
> Fíjate en que aquí aparecen **juntos** `u*` y `z₀`: la rugosidad del suelo (§12) y la
> fricción son dos caras de lo mismo. Un bosque (z₀ grande) genera más `u*` con el mismo
> viento que un lago.

**Dónde entra:** en `L`, y directamente en `σz` en condiciones estables (donde la turbulencia
es puramente mecánica).

### 11.5 La longitud de Monin-Obukhov `L` — donde todo converge

No se descarga: **se calcula** a partir de las anteriores. Merece su propio apartado porque es
el número que resume la estabilidad:

> **📐 TEORÍA · La fórmula de `L`**
>
> ```
>            ρ · cp · T · u*³
> L = −  ─────────────────────────
>              k · g · H
> ```
>
> donde `cp` = calor específico del aire, `g` = gravedad, `k` = von Kármán.
>
> **Cómo leerla:** es un cociente entre lo que genera el **rozamiento** (`u*³`, arriba) y lo
> que genera el **calor** (`H`, abajo).
>
> | Situación | `H` | `L` | Qué pasa |
> |---|---|---|---|
> | Día soleado | `> 0` | **negativo, pequeño** | Convección: mezcla brutal |
> | Cielo cubierto y ventoso | `≈ 0` | **±∞** | Neutro: solo turbulencia mecánica |
> | Noche despejada y calma | `< 0` | **positivo, pequeño** | Estable: sin mezcla → *el peor caso* |
>
> `|L|` es, con dimensiones de longitud, **la altura por encima de la cual el calor manda
> sobre el rozamiento**. Un `L` de +10 m es una noche muy estable; un `L` de −10 m es un
> mediodía de julio.

> **⚠️ OJO · `L` diverge, y hay que ponerle topes**
>
> Con `H → 0` (neutro), `L → ∞`: matemáticamente correcto, numéricamente inmanejable. Y con
> `u*` pequeño, `L → 0`. En la práctica se **satura** `|L|` entre un mínimo y un máximo, igual
> que hace el preprocesador oficial AERMET.
>
> Además, en horas **estables** hay un suelo extra que depende de `u*`: si `L` es demasiado
> pequeño, el gradiente de temperatura que AERMOD deduce se dispara y salta el aviso
> `W479 TGINIT`. La herramienta despeja el `L` mínimo que mantiene el gradiente en rango.
> Es un detalle feo pero real: **los modelos tienen costuras**, y saber dónde están es parte
> de usarlos bien.

### 11.6 Presión superficial (`sp`) — densidad y la escalera vertical

> **🔢 VARIABLE · `sp` (Pa → hPa)**
>
> Dos papeles muy distintos:
>
> **1. La densidad del aire**, por la ley de los gases ideales:
> ```
> ρ = p / (R_d · T)          R_d = 287 J/(kg·K)
> ```
> `ρ` entra en `L` y en `w*`. En Lleida (198 m, ~988 hPa) la densidad es ~2,5 % menor que al
> nivel del mar: pequeño, pero es gratis hacerlo bien.
>
> **2. La escalera del perfil vertical.** Los datos en altura de ERA5 vienen por **niveles de
> presión**, no por altura en metros. Convertir un nivel de presión a una altura sobre el
> suelo **exige saber la presión en el suelo**, y esa presión **cambia cada hora**. Es lo que
> hace que un mismo nivel (975 hPa) esté a 290 m en un anticiclón y **132 m bajo tierra** en
> una borrasca. Todo el §13 va de esto.

### 11.7 Nubosidad (`tcc`) y radiación solar (`ssrd`) — el balance de energía

> **🔢 VARIABLE · `tcc` (fracción 0–1 → décimas 0–10)**
>
> La fracción de cielo cubierto. AERMOD la usa en el **balance de radiación nocturno**: una
> noche **despejada** irradia calor al espacio y se enfría mucho (→ muy estable, inversión
> térmica, el peor escenario de olores). Una noche **cubierta** tiene las nubes de manta: el
> suelo se enfría poco y la atmósfera se queda casi neutra.
>
> Es decir: **la nubosidad es la que distingue una noche mala de una noche inofensiva.** Para
> un estudio de olor, no es un dato decorativo.

> **🔢 VARIABLE · `ssrd` (J/m² acumulados → W/m²)**
>
> La radiación solar que llega al suelo. En la herramienta cumple una función muy concreta:
> **decidir si es de día o de noche** (`ssrd ≤ 0` → noche). Y esa etiqueta se usa para el
> albedo, por una convención del formato:
>
> ```
> albedo de la hora = 1.00           si es de noche
>                   = albedo del uso del suelo   si es de día
> ```
>
> Tiene sentido físico: **de noche no hay radiación solar que reflejar**, así que el albedo
> deja de significar nada y se marca con el valor convencional 1,00.

### 11.8 Altura de la capa límite (`blh`, `zi`) — la tapa

> **🔢 VARIABLE · `blh` → `zi` (m)**
>
> La altura hasta la que el aire se mezcla. Es una **tapa**: el contaminante rebota en ella
> igual que rebota en el suelo (§5.2, la fuente imagen). Todo lo que se emita queda encerrado
> entre el suelo y `zi`.
>
> - **De día:** 1000–2000 m. Un volumen enorme para diluir.
> - **De noche:** puede bajar de 100 m. *En Lleida la mediana nocturna es 219 m.*
>
> El mismo caudal repartido en 1500 m de espesor o en 100 m da concentraciones que difieren
> en **más de un orden de magnitud**. Esta variable, sola, explica buena parte de por qué las
> quejas por olor llegan de madrugada.
>
> La herramienta la escribe en dos columnas del fichero meteorológico: la **convectiva**
> (solo en horas con `H > 0`) y la **mecánica** (siempre).

### 11.9 Punto de rocío (`d2m`) — humedad

> **🔢 VARIABLE · `d2m` → humedad relativa (%)**
>
> La temperatura a la que el aire se satura. Con `t2m` se obtiene la humedad relativa por la
> fórmula de Magnus:
>
> ```
> e_s(T) = 6,112 · exp( 17,67·T / (T + 243,5) )        (presión de vapor saturante, hPa)
> HR = 100 · e_s(d2m) / e_s(t2m)
> ```
>
> Es un **dato de contexto** en el fichero meteorológico: AERMOD lo arrastra pero no gobierna
> la dispersión de un gas pasivo. Importa si algún día se modela deposición húmeda o química
> dependiente de la humedad.

### 11.10 Precipitación (`tp`) — la honestidad de lo que no se usa

> **⚠️ RECTIFICACIÓN · Se descarga, pero HOY NO SE USA**
>
> `tp` (precipitación total horaria) se descarga y se guarda, pero **en el fichero
> meteorológico se escribe "sin precipitación"**. No es un descuido: es coherente con que la
> herramienta modela **gas pasivo conservativo** (§8), sin deposición húmeda.
>
> La lluvia **lava** el penacho (*washout*): arrastra el contaminante al suelo y reduce la
> concentración aguas abajo. Ignorarla es **conservador** (sale más concentración de la que
> habría), que es el lado correcto por el que equivocarse en un estudio de impacto.
>
> Está descargada porque el día que se modele deposición húmeda, el dato ya estará ahí.
> Decirlo por escrito evita que alguien suponga que la lluvia está en el modelo.

> **📈 CORRELACIÓN · Resumen: qué pasa si cada dato está mal**
>
> | Variable | Sensibilidad | Por qué |
> |---|---|---|
> | `u10`,`v10` | 🔴 **Muy alta** | `u` divide; la dirección decide a quién le llega |
> | `sshf` (`H`) | 🔴 **Muy alta** | Decide estable/convectivo — cambia `σz` por completo |
> | `blh` (`zi`) | 🔴 **Muy alta** | El volumen de dilución nocturno |
> | `zust` (`u*`) | 🟠 Alta | Turbulencia mecánica, domina de noche |
> | uso del suelo (`z₀`) | 🟠 Alta *(depende del sitio, §14)* | Perfil de viento y `u*` |
> | elevación | 🟠 Alta *(depende del relieve, §14)* | Geometría vertical fuente-receptor |
> | `tcc` | 🟡 Media | Distingue noche despejada (mala) de cubierta |
> | `t2m`, `sp` | 🟢 Baja | Entran vía `ρ`, efecto de segundo orden |
> | `d2m` | 🟢 Nula hoy | Dato de contexto |
> | `tp` | 🟢 Nula hoy | No se modela deposición húmeda |

---

## 12. El uso del suelo: cómo un bosque se convierte en tres números <a id="12-el-uso-del-suelo"></a>

Esta es la parte que más sorprende a quien llega nuevo. Descargamos un **mapa de usos del
suelo** (CORINE) que dice "aquí hay un bosque, aquí un embalse, aquí regadío". Pero AERMOD
**no sabe qué es un bosque**. Lo único que entiende son **tres números** por celda:

| Número | Símbolo | Qué representa | Rango típico |
|---|---|---|---|
| **Rugosidad** | `z₀` (m) | Cuánto frena el suelo al viento | 0,001 (agua) – 1,3 (bosque) |
| **Albedo** | `α` (0–1) | Qué fracción de la radiación solar refleja | 0,10 (agua) – 0,70 (nieve) |
| **Razón de Bowen** | `B` | Cómo reparte el suelo el calor: calentar aire vs. evaporar agua | 0,1 (agua) – 10 (desierto seco) |

Toda la sección va de **cómo se hace esa traducción** y **por qué importa**.

### 12.1 Qué hace cada uno de los tres números

> **📐 TEORÍA · `z₀`, la rugosidad: la altura donde el viento "se apaga"**
>
> `z₀` es un parámetro del perfil logarítmico (§3, §11.4):
>
> ```
> u(z) = (u* / k) · ln(z / z₀)
> ```
>
> Matemáticamente es **la altura a la que la fórmula da viento cero**. Físicamente es una
> medida del tamaño de los obstáculos: hierba, matorral, árboles, edificios. La regla
> aproximada es `z₀ ≈ h/10`, con `h` la altura de los elementos rugosos (un bosque de 13 m
> → z₀ ≈ 1,3 m; hierba de 20 cm → z₀ ≈ 0,02 m).
>
> **Por qué importa tanto:** `z₀` está **dentro de un logaritmo**, así que cambiarlo mueve
> todo el perfil de viento. Compara a 10 m de altura, con el mismo `u*` = 0,3 m/s:
>
> | Superficie | `z₀` | `ln(10/z₀)` | `u(10 m)` |
> |---|---|---|---|
> | Lámina de agua | 0,001 m | 9,21 | **6,7 m/s** |
> | Regadío (invierno) | 0,03 m | 5,81 | **4,3 m/s** |
> | Bosque de coníferas | 1,30 m | 2,04 | **1,5 m/s** |
>
> El mismo forzamiento da **4 veces más viento** sobre agua que sobre bosque. Y como `u`
> divide en la ecuación gaussiana, eso es un factor 4 en la concentración… en sentido
> contrario del que mucha gente espera: **más rugosidad = menos viento, pero también más
> turbulencia**. Los dos efectos compiten, y por eso el resultado neto no es obvio (§14).

> **📐 TEORÍA · El albedo `α`: cuánta energía se queda el suelo**
>
> El albedo es la fracción de radiación solar que el suelo **devuelve** sin absorber. Entra en
> el balance de radiación neta:
>
> ```
> R_n = (1 − α) · R_solar  +  (radiación de onda larga)
> ```
>
> Menos albedo → más energía absorbida → más calor disponible → **más `H`** → atmósfera más
> inestable → más mezcla. Un bosque oscuro (α = 0,12) absorbe mucho más que un campo nevado
> (α = 0,60), y por eso la nieve "apaga" la convección.

> **📐 TEORÍA · La razón de Bowen `B`: calentar aire o evaporar agua**
>
> La energía que absorbe el suelo se reparte entre dos caminos:
> - **Calor sensible `H`** — calienta el aire (esto es lo que genera turbulencia térmica).
> - **Calor latente `LE`** — evapora agua (esto **no** calienta el aire).
>
> La razón de Bowen es simplemente el cociente:
>
> ```
> B = H / LE
> ```
>
> - **`B` bajo (0,1 — un lago, un regadío):** casi toda la energía se va en evaporar. El aire
>   se calienta poco → poca convección.
> - **`B` alto (6 — un secarral):** no hay agua que evaporar, así que **toda** la energía
>   calienta el aire → convección fuerte.
>
> Por eso el mismo sol produce atmósferas distintas sobre un arrozal y sobre un yermo. Y por
> eso la herramienta tiene un parámetro de **humedad del suelo** (`wet`/`average`/`dry`): el
> mismo uso del suelo en un año seco tiene un Bowen mucho más alto.

> **🧠 CONCEPTO · La cadena completa, en una línea**
>
> ```
> uso del suelo → (z₀, α, B) → (u*, H) → L → σy, σz → C
> ```
>
> El uso del suelo **no entra como paisaje: entra como meteorología**. Es un dato de terreno
> que acaba modificando el viento y la estabilidad. Esa es la idea que hay que llevarse.

### 12.2 El eslabón débil: traducir CORINE a NLCD

> **⚠️ OJO · El programa oficial de la EPA no entiende los mapas europeos**
>
> La EPA tiene un programa, **AERSURFACE**, que hace exactamente esta traducción. El problema:
> solo lee **NLCD**, el mapa de usos del suelo de Estados Unidos. En Europa tenemos **CORINE**,
> que tiene otras clases y otra numeración.
>
> La solución de la herramienta: **traducir CORINE → NLCD** y luego aplicar las tablas
> oficiales de AERSURFACE. Funciona, pero **es un juicio técnico, no un dato**: es el eslabón
> más débil de toda la cadena y **conviene declararlo en el protocolo del estudio**, no
> esconderlo.

Un extracto de la correspondencia (la tabla completa está en el código):

| CORINE | Descripción | → NLCD | Comentario |
|---|---|---|---|
| 111 | Tejido urbano continuo | 24 | Urbano denso |
| 112 | Tejido urbano discontinuo | 22 | Urbano medio |
| 124 | Aeropuertos | 21 | Activa el modificador *airport* |
| 211/212 | Cultivos herbáceos / **regadío** | 82 | *La clase dominante en Lleida* |
| 221/222/223 | **Viñedos / frutales / olivares** | 82 | ⚠️ Ver §12.6 |
| 231 | Prados | 81 | |
| 311 | Bosque de frondosas | 41 | Caduco |
| 312 | Bosque de coníferas | 42 | Perenne |
| 313 | Bosque mixto | 43 | |
| 321/322 | Pastizal / matorral | 71 / 52 | |
| 511/512 | Ríos / láminas de agua | 11 | |

> **⚠️ RECTIFICACIÓN · Los valores se sacaron del código fuente, no del PDF**
>
> Un detalle que ilustra lo que cuesta hacer esto bien. Las tablas de AERSURFACE están
> publicadas en un PDF de la EPA… **con erratas**. Se comprobaron contra el código fuente
> Fortran del programa y hay al menos cuatro discrepancias (por ejemplo, el albedo de la
> clase 23 en la estación 2: el PDF imprime 0,18 y el código usa 0,35).
>
> Una de ellas se delató sola por **incoherencia física**: en la clase 42 el Bowen "medio"
> que imprime el PDF es *mayor* que el "seco", lo cual es imposible — un suelo húmedo no
> puede calentar más el aire que el mismo suelo seco. Se les había caído un valor al
> componer la tabla.
>
> Moraleja: **cuando un número no cuadra con la física, sospecha del número.**

### 12.3 Las cinco estaciones (que no son cuatro)

Los tres parámetros **cambian a lo largo del año**: un bosque de frondosas sin hojas en enero
no frena el viento igual que en julio. AERSURFACE define **cinco** categorías estacionales
(ojo, no coinciden con las cuatro estaciones del año):

| # | Estación AERSURFACE | Meses asignados |
|---|---|---|
| 1 | Otoño tardío tras las heladas / invierno **sin** nieve | Dic, Ene, Feb |
| 2 | Invierno **con nieve continua** en el suelo | *solo si se declara* |
| 3 | Primavera de transición, cobertura verde parcial | Mar, Abr, May |
| 4 | Pleno verano, vegetación exuberante | Jun, Jul, Ago |
| 5 | Otoño con cultivo sin cosechar | Sep, Oct, Nov |

> **🧪 EJEMPLO · El mismo cultivo a lo largo del año (NLCD 82)**
>
> | Estación | `z₀` (m) | Albedo | Bowen (medio) |
> |---|---|---|---|
> | 1 · Invierno sin nieve | 0,03 | 0,18 | 0,7 |
> | 2 · Invierno con nieve | 0,014 | **0,60** | 0,5 |
> | 3 · Primavera | 0,04 | 0,14 | 0,3 |
> | 4 · Verano (cultivo alto) | **0,20** | 0,20 | 0,5 |
> | 5 · Otoño sin cosechar | 0,20 | 0,20 | 0,7 |
>
> La rugosidad varía **×14** entre el invierno pelado y el verano con el cultivo crecido. Y
> con nieve el albedo se **triplica** (0,18 → 0,60): el suelo pasa de absorber a reflejar,
> y la convección se apaga.

### 12.4 Los números de verdad: bosque, ciudad y agua

> **🧪 EJEMPLO · De "un bosque" a tres números, paso a paso**
>
> Supongamos una celda de **bosque de coníferas** en julio. La cadena es:
>
> ```
> 1. CORINE dice:        clase 312 «Bosque de coníferas»
> 2. Traducción:         312 → NLCD 42 «Evergreen Forest»
> 3. Mes julio:          → estación 4 (pleno verano)
> 4. Se leen las tablas: z₀ = 1,30 m · α = 0,12 · B = 0,3 (humedad media)
> ```
>
> Y compárala con sus vecinas, el mismo día:
>
> | Uso del suelo | `z₀` (m) | Albedo | Bowen |
> |---|---|---|---|
> | Lámina de agua (11) | **0,001** | 0,10 | 0,1 |
> | Regadío en verano (82) | 0,20 | 0,20 | 0,5 |
> | Bosque de coníferas (42) | **1,30** | 0,12 | 0,3 |
> | Urbano denso (24) | 0,70 | 0,18 | 1,5 |
>
> La rugosidad va de **0,001 a 1,3 m: un factor 1300**. Ese es el rango que el uso del suelo
> puede mover, y por eso no es un detalle cosmético… *cuando el dominio es heterogéneo*
> (matiz importante, ver §14).

### 12.5 El promediado espacial: tres recetas distintas, y no por capricho

Aquí viene lo que casi nadie explica. AERMOD **no quiere un `z₀` por celda**: quiere **un
valor representativo** para el emplazamiento. ¿Cómo se pasa de un mapa a un número? Con tres
recetas **deliberadamente distintas**:

> **📐 TEORÍA · Receta 1 — `z₀`: media geométrica ponderada por 1/distancia, por sectores**
>
> - **Radio: 1 km** alrededor del punto.
> - **Por sectores:** se divide la rosa en **12 sectores de 30°** y se calcula **un `z₀` por
>   sector**. Cada hora se usa el sector **del que viene el viento**.
> - **Media geométrica**, ponderada por `1/d` (lo cercano pesa más):
>
> ```
> ln z₀(sector) = Σ [ w_i · ln z₀_i ] / Σ w_i        con  w_i = 1/d_i
> ```
>
> **¿Por qué geométrica y no aritmética?** Porque `z₀` entra en las ecuaciones **dentro de un
> logaritmo**. Lo que tiene sentido físico es promediar `ln z₀`, no `z₀`. Con la media
> aritmética, una sola celda de bosque (1,3) dominaría a 99 celdas de agua (0,001) y daría un
> disparate.
>
> **¿Por qué por sectores?** Porque el viento del norte recorre un terreno distinto que el del
> sur. Si tu planta tiene un bosque al norte y un embalse al sur, el aire llega con historias
> de rozamiento distintas.

> **📐 TEORÍA · Receta 2 — Bowen: media geométrica simple, cuadrado de 10 km**
>
> Sin sectores y en un cuadrado mucho más grande. El motivo es físico: el reparto de energía
> es un fenómeno **regional**, no depende de la dirección desde la que sople el viento.
> Geométrica porque el Bowen es un **cociente** y los cocientes se promedian en logaritmos.

> **📐 TEORÍA · Receta 3 — Albedo: media ARITMÉTICA, mismo cuadrado de 10 km**
>
> Y aquí la asimetría que llama la atención: **el albedo se promedia aritméticamente**,
> mientras que el Bowen —en la misma caja— se promedia geométricamente.
>
> **No es una incoherencia:** el albedo es una **fracción de energía reflejada**, y sumar
> energías reflejadas de trozos distintos de superficie es literalmente una **suma
> aritmética**. El Bowen es un **cociente entre dos flujos**, y ahí la media correcta es la
> geométrica. La asimetría es real y está en la especificación oficial de AERSURFACE.

### 12.6 Un juicio técnico declarado: los cultivos leñosos

> **⚠️ OJO · Cuando la tabla oficial no tiene tu paisaje**
>
> NLCD es un mapa **de Estados Unidos**. No tiene una clase para **viñedos, frutales y
> olivares**, así que la traducción los manda todos a NLCD 82 «Cultivated Crops», cuya
> rugosidad de verano es **0,20 m** — la de un herbáceo.
>
> Pero un frutal maduro no es un trigal: mide 4-5 m y frena el viento **el doble o más**. Y
> esto no es un matiz de laboratorio: **en el dominio de Lleida los frutales ocupan ~36 %**.
>
> La herramienta **sobrescribe solo `z₀`** (el albedo y el Bowen se quedan con los del
> cultivo, que es lo razonable: lo que falla es la rugosidad) usando la clasificación de
> **Davenport-Wieringa**, adoptada por la OMM:
>
> | CORINE | `z₀` en pleno desarrollo | Clase Davenport |
> |---|---|---|
> | 221 Viñedos | 0,25 m | 5 «rough» — *vineyards* |
> | 222 Frutales | 0,50 m | 6 «very rough» — *mature orchards* |
> | 223 Olivares | 0,50 m | 6 «very rough» |
>
> Y el ciclo estacional restante (los frutales y la viña pierden hoja, el olivo no) es una
> **atenuación razonada, no un dato medido**. Está escrito en el código, a la vista, para que
> se pueda discutir y ajustar.
>
> **Por qué contarlo así:** esto es exactamente el tipo de decisión que, escondida, convierte
> un estudio en una caja negra. Declarada, es una hipótesis que un revisor puede aceptar,
> discutir o cambiar. **Ponlo en el protocolo del estudio.**

---

## 13. El perfil vertical: los datos en altura <a id="13-el-perfil-vertical"></a>

Casi toda la meteorología que hemos visto es **de superficie**: viento a 10 m, temperatura a
2 m. Pero AERMOD funciona mejor si sabe **cómo cambian el viento y la temperatura con la
altura**.

> **🧠 CONCEPTO · Qué aporta el perfil (y qué no)**
>
> **Lo que SÍ aporta: la cizalladura y el giro del viento con la altura.** Datos reales de una
> noche en Lleida (1 de enero de 2023, 00:00):
>
> | Altura sobre el suelo | Dirección | Velocidad |
> |---|---|---|
> | 10 m | 82° (E) | 1,6 m/s |
> | 233 m | 134° (SE) | 2,7 m/s |
> | 452 m | 174° (S) | 3,1 m/s |
> | 908 m | 223° (SO) | 4,2 m/s |
>
> El viento **gira 141° y casi triplica su velocidad** en 900 m. Eso es real, y la teoría de
> semejanza **no puede inventárselo** a partir del dato del suelo. Si el penacho sube, se va a
> encontrar ese giro.
>
> **Lo que NO aporta:** no resuelve la microestructura de la capa nocturna (abajo).

> **⚠️ CLAVE · Los datos vienen por presión, y algunos niveles caen bajo tierra**
>
> ERA5 no da "la temperatura a 100 m": la da **a 1000 hPa, 975 hPa, 950 hPa…**. Y la altura de
> un nivel de presión **depende de la presión que haya en el suelo**, que cambia cada hora.
>
> En Lleida (198 m de altitud, presión media en el suelo **988 hPa**) el nivel de 1000 hPa
> corresponde a un punto **98 m bajo tierra**: no existe. ERA5 lo rellena por extrapolación
> matemática, pero **no es aire real**, así que se descarta.
>
> Y no basta con una lista fija: el nivel de 975 hPa oscila entre **−132 m** (bajo tierra, en
> borrasca) y **+290 m** (en anticiclón). Hay que **recalcular la altura hora a hora** y tirar
> lo que caiga bajo el suelo — el 2,6 % de las horas del año.

> **⚠️ OJO · El límite honesto: la capa nocturna cabe por debajo del primer nivel**
>
> El primer nivel utilizable (975 hPa) está típicamente a ~113 m. Pero **el 35 % de las horas
> nocturnas** tienen toda la capa estable **por debajo de esa altura**. En esas noches, toda la
> acción —la inversión térmica donde queda atrapado el contaminante— ocurre entre el suelo y
> los 113 m, y ahí ERA5 solo tiene **un** dato: el de superficie.
>
> No se arregla bajando más niveles: **no existe ningún nivel de ERA5 por debajo de 975 hPa
> que sirva en este punto**. Haría falta un radiosondeo local o una torre meteorológica. El
> perfil **mejora** el modelo, pero **no vendas que resuelve la capa nocturna**.

> **📖 La nota completa:** todo esto —incluida una hipótesis que resultó falsa y su
> rectificación— está desarrollado en **`notas_perfil_vertical.md`**, con los datos medidos,
> los dos filtros que se aplican (techo de 999 m y separación mínima de 60 m entre niveles) y
> el coste de descarga.

---

## 14. ¿Cuánto importa cada uno? Dos experimentos de sensibilidad <a id="14-cuánto-importa-cada-uno"></a>

Todo lo anterior explica **por qué** cada dato debería importar. Pero "debería importar" y
"cambia el resultado" no son lo mismo. Así que se midió.

> **🧪 EL EXPERIMENTO · Diseño factorial 2×2**
>
> Se simuló **el mismo caso** (Lleida, H₂S, año completo 2023, 650 receptores, dos fuentes)
> **cuatro veces**, activando y desactivando los dos datos de terreno:
>
> | Caso | Relieve | Uso del suelo |
> |---|---|---|
> | **ELEV+USO** *(referencia)* | Real (MDT05: 132–255 m) | Real (12 clases CORINE) |
> | **ELEV** | Real | **Constante** (z₀ = 0,03 · Bowen 0,70) |
> | **USO** | **Plano** (201,92 m = la media) | Real |
> | **NINGUNO** | **Plano** | **Constante** |
>
> Todo lo demás —meteorología, fuentes, malla— idéntico. Así, la diferencia entre dos casos
> **solo** puede venir del dato que se ha quitado.

### 14.1 El resultado

> **🔢 DATO · Máximos de concentración y desviación respecto al caso real**
>
> | Caso | Máx (µg/m³) | Mediana | Percentil 90 | Máxima | Receptores con error > 20 % |
> |---|---|---|---|---|---|
> | **ELEV+USO** (real) | 18,0 | — | — | — | — |
> | **ELEV** (sin uso del suelo) | 16,5 | **0,5 %** | ~2 % | 11 % | **0 %** |
> | **USO** (sin relieve) | 23,1 | **30,1 %** | 480 % | **1275 %** | **80 %** |
> | **NINGUNO** (sin nada) | 21,2 | **29,7 %** | 470 % | 1253 % | 76 % |
>
> *Configuración: H₂S, 2 fuentes de área (4993 m² a 3 m de altura), caudal 1·10⁻⁵ g/(s·m²),
> 8760 h de ERA5 con perfil multinivel, malla refinada de 650 receptores. Terreno real
> 111–269 m (desviación típica 35,6 m) frente a plano de 201,9 m.*

![Desviaciones respecto al caso real](images/desviaciones.png)

> **🧠 CONCEPTO · La lectura: en Lleida, el relieve manda y el uso del suelo casi no**
>
> - **Quitar el uso del suelo:** error mediano **0,5 %**, máximo 11 %. Prácticamente
>   indistinguible.
> - **Quitar el relieve:** error mediano **30 %**, percentil 90 del **480 %**, máximo
>   **1275 %** (más de ×13). **Ocho de cada diez receptores** se van más de un 20 %.
>
> Y fíjate en algo importante: **el máximo, solo, te engañaría.** El caso sin relieve da un
> máximo de 23,1 frente a 18,0 — parece "un 28 % de error". Pero el máximo cae en el mismo
> sitio en los cuatro casos (pegado a la fuente, como manda §5.3 para fuentes bajas). Lo que
> se destruye es **el patrón espacial**: dónde llega el penacho y con qué intensidad a cada
> receptor. Por eso el experimento compara **receptor a receptor**, no máximos.
>
> En los mapas se ve de un vistazo: con relieve real el penacho **se deforma y se fragmenta**
> (hay zonas que el terreno protege); en los mapas planos es una **elipse lisa y simétrica**
> alrededor del foco. La elipse limpia es bonita y es mentira.

> **📈 CORRELACIÓN · Dos hallazgos que refuerzan la conclusión**
>
> **1. No hay interacción entre los dos factores.** Quitar *ambos* (29,7 %) da prácticamente
> lo mismo que quitar *solo el relieve* (30,1 %). Es decir: el uso del suelo no aporta nada
> **ni siquiera combinado** con el relieve. En un diseño factorial eso significa que los
> efectos son independientes y que uno de ellos es, sencillamente, despreciable aquí.
>
> **2. El terreno plano SOBRESTIMA, siempre.** Todas las desviaciones al quitar el relieve son
> **positivas**: el escenario plano da más concentración. Tiene sentido físico —sin relieve que
> desvíe el penacho ni rugosidad que lo mezcle, el contaminante llega más concentrado—, así que
> modelar en plano sería *conservador*… **pero por el motivo equivocado y con errores punto a
> punto de hasta ×13**. Un conservadurismo que no controlas no es conservadurismo: es suerte.

### 14.2 Por qué sale así (y por qué no vale generalizar)

> **⚠️ OJO · Este resultado es de Lleida. En otro sitio puede invertirse.**
>
> Es tentador concluir "el uso del suelo da igual". **Sería un error.** Mira *por qué* sale
> tan pequeño aquí:
>
> **1. La clase dominante de Lleida tiene, casualmente, la rugosidad del valor constante.**
> El uso dominante es CORINE 212 «Terrenos regados permanentemente» → NLCD 82, cuyo `z₀` de
> invierno es **exactamente 0,03 m**… que es el valor constante que se usó en el caso
> simplificado. El dominio real da `z₀` entre 0,03 y 0,042 según el sector. **La
> "simplificación" resultó ser casi el valor verdadero**, así que no cambió nada.
>
> **2. El dominio es agrícola y homogéneo.** 12 clases CORINE, pero casi todas variantes de
> cultivo. No hay el contraste bosque/agua/ciudad que haría explotar la diferencia.
>
> **3. El relieve, en cambio, sí varía: 158 m de desnivel** (de 111 a 269 m, desviación típica
> 35,6 m). Aplanar el terreno a la media (201,9 m) mueve receptores que estaban **decenas de
> metros por debajo** de la fuente a estar por encima de ella. Eso cambia por completo la
> geometría vertical fuente-receptor, y la concentración depende de esa geometría por un
> `exp(−H²/2σz²)`: un **exponencial**.
>
> **Cuándo se invertiría el resultado:** un dominio con **bosque a un lado y embalse a otro**
> (`z₀` de 1,3 frente a 0,001, factor 1300) sobre **terreno llano**. Ahí el uso del suelo
> mandaría y el relieve daría igual.
>
> **La conclusión transferible no es "el uso del suelo no importa", sino:**
> **manda el dato que más *varía dentro de tu dominio*.** Antes de simplificar, mira tu mapa:
> ¿cuánto desnivel hay? ¿cuánto contraste de usos? El experimento se puede repetir en
> cualquier emplazamiento — es el mismo caso corrido cuatro veces.

![Mapa del caso real](images/mapa_ELEV_USO.png)

> **📈 CORRELACIÓN · El error no decae con la distancia (pero su dispersión sí crece)**
>
> Es tentador suponer que "cerca de la fuente el terreno da igual". **Los datos no lo
> sostienen.** Por anillos de distancia, al quitar el relieve:
>
> | Distancia al foco | Mediana | Percentil 90 |
> |---|---|---|
> | 0–250 m | 25 % | 134 % |
> | 250–500 m | 32 % | 443 % |
> | 500–1000 m | 30 % | 413 % |
> | 1000–2000 m | 31 % | 620 % |
> | 2000–3000 m | 33 % | 550 % |
> | > 3000 m | 30 % | 663 % |
>
> La mediana es prácticamente **plana** (25–33 % en todo el rango) y la correlación con la
> distancia es despreciable (**r = +0,13**). Lo que **sí** crece es la **dispersión**: el
> percentil 90 pasa de 134 % cerca del foco a 663 % lejos.
>
> Traducción: **el error típico es el mismo en todas partes, pero los casos extremos solo
> aparecen lejos** — que es donde el penacho ya ha tenido tiempo de tropezar con una colina o
> de colarse por un valle.

> **📖 El análisis completo**, con los cuatro mapas, la tabla de 50 receptores muestreados y
> las instrucciones para reproducirlo, está en **`analisis_sensibilidad_terreno.md`**.
> Los cuatro casos quedan guardados en `tmp/Results/` y se pueden abrir con «Load».

> **⚠️ OJO · Un aviso que salió de este experimento: cuidado con `Q`**
>
> Al preparar las simulaciones se descubrió que el caso guardado tenía un caudal de
> **234 g/(s·m²)** que, sobre 4993 m², son **3,7 millones de kg/h**: unos **siete órdenes de
> magnitud** por encima de lo físicamente posible (casi con seguridad, un valor tecleado en
> otra unidad). Se corrigió a un valor realista de 1·10⁻⁵ g/(s·m²) ≈ 180 g/h.
>
> Dos lecciones. **Una:** como la dispersión es **lineal**, las desviaciones **en %** no
> dependen del caudal — el experimento seguía siendo válido. **Y dos, la importante:** el
> parámetro que de verdad domina la incertidumbre de un estudio **no es el relieve ni el uso
> del suelo, sino `Q`**. Aquí se coló un error de 10⁷ y solo se detectó al mirar los valores
> absolutos. Haz siempre la comprobación de orden de magnitud: *«¿cuántos kg/h son esto?»*

### 14.3 La contraprueba: ¿cuánto contraste hace falta para que el uso del suelo importe?

El experimento de §14.1 mostró que *en Lleida* el uso del suelo pesa poco. Pero eso **no
demuestra que CORINE sea prescindible**: podía ser que en Lleida no hubiera nada que perder. La
pregunta correcta no era *«¿importa el uso del suelo?»* sino **«¿cuánto contraste hace falta
para que importe?»**.

> **🧪 EL EXPERIMENTO · Cambiar el paisaje sin cambiar su geometría**
>
> Se simuló el mismo dominio de Lleida —mismo relieve real, misma meteorología, mismas
> fuentes— con **cuatro paisajes de contraste creciente**. La clave del diseño: se conserva
> **la geometría real del mosaico** (las parcelas son idénticas en los cuatro casos) y solo
> cambia **qué clase recibe cada parcela**.

![Los cuatro patrones de uso del suelo](images/usos_patrones.png)

> | | Escenario (58 % ↔ 42 %) | Contraste de clases | Aísla |
> |---|---|---|---|
> | 🟢 **BAJO** | regadío ↔ frutales *(el mosaico real)* | `z₀` **×5** | — (control) |
> | 🟡 **MEDIO** | zonas verdes urbanas ↔ casco denso | `z₀` **×27** | rugosidad |
> | 🟠 **ALTO** | marisma ↔ esclerófila | Bowen **×6**, `z₀` ×2 | **Bowen** |
> | 🔴 **MÁXIMO** | agua ↔ bosque de coníferas | `z₀` **×1300** | rugosidad |
>
> Cada patrón se corre **dos veces**: *heterogéneo* (con el patrón) y *uniforme* (todo el
> dominio con su clase dominante). La diferencia mide **cuánto aporta conocer el uso del
> suelo** en ese paisaje.

### 14.3.1 El hallazgo central: el contraste que ve el modelo no es el de las clases

Antes de mirar concentraciones hay que mirar **qué le llega realmente a AERMOD**, porque el
promediado espacial de §12.5 cambia el problema por completo:

> **🔢 DATO · El contraste de clases se derrumba al promediar**
>
> | Escenario | Contraste de **clases** | Contraste **direccional** real (`z₀` máx/mín entre sectores) |
> |---|---|---|
> | 🟢 BAJO | ×5 | **×2,6** |
> | 🟡 MEDIO | ×27 | **×5,9** |
> | 🟠 ALTO | ×2 (Bowen ×6) | **×1,3** |
> | 🔴 MÁXIMO | **×1300** | **×53** |
>
> En el escenario MÁXIMO, un contraste de clases de **×1300 se queda en ×53**. El motivo es
> geométrico: como las parcelas están **entremezcladas**, cualquier sector de 30° dentro del
> radio de 1 km contiene **de todo**, y la media **geométrica** la manda la clase más lisa.
> Un sector mitad agua mitad bosque no da 0,65 m, sino:
>
> ```
> z₀ = √(0,001 × 1,3) = 0,036 m
> ```
>
> Es decir: **casi el valor del agua**. La media geométrica de valores muy dispares se pega al
> pequeño — que es justo la propiedad que la hace correcta para `z₀` (§12.5), pero que aquí
> destruye el contraste.

> **🔑 LA IDEA CENTRAL DE TODO ESTE EXPERIMENTO**
>
> **Lo que importa no es cuánto difieren las clases, sino si esa diferencia está ORGANIZADA a
> la escala del sector de dirección.**
>
> Un paisaje **fragmentado** se promedia solo, por extremas que sean sus clases. Un paisaje
> **organizado** (embalse a un lado, bosque al otro) sí le llega al modelo. Mira la figura de
> los patrones: las cuatro parcelas están igual de troceadas, y por eso ninguna consigue mover
> mucho el resultado.

### 14.3.2 Los resultados

![Desviaciones al uniformizar el uso del suelo](images/usos_desviaciones.png)

> **🔢 DATO · Desviación al uniformizar, sobre 650 receptores (foco a 3 m)**
>
> | Escenario | Mediana | Percentil 90 | Máxima | > 20 % | Máximo de concentración (het → unif) |
> |---|---|---|---|---|---|
> | 🟢 BAJO | **0,5 %** | 4,0 % | 11 % | 0 % | 18,00 → 16,47 µg/m³ (**−9 %**) |
> | 🟡 MEDIO | **0,8 %** | 6,9 % | 17 % | 0 % | 17,35 → 15,04 µg/m³ (**−13 %**) |
> | 🟠 ALTO | **0,2 %** | 1,3 % | 4 % | 0 % | 19,19 → 18,62 µg/m³ (**−3 %**) |
> | 🔴 MÁXIMO | **1,1 %** | 9,4 % | 22 % | 0 % | 15,15 → 12,95 µg/m³ (**−15 %**) |

> **⚠️ RECTIFICACIÓN · La predicción de esta guía era demasiado optimista**
>
> La versión anterior de esta sección predecía que el escenario 🔴 «dispararía» el efecto, con
> un razonamiento logarítmico (`ln(1300)/ln(1,4) ≈ ×21` de señal). **No ocurrió.** Pasar del
> mosaico agrícola real al contraste de rugosidad más grande que permite CORINE multiplica la
> desviación mediana solo **×2: de 0,5 % a 1,1 %**.
>
> ¿Por qué falló el razonamiento? Porque aplicaba el logaritmo al **contraste de clases**,
> ignorando que el promediado sectorial lo derrumba antes de llegar al modelo (§14.3.1). La
> física del logaritmo era correcta; el número al que se aplicaba, no.
>
> **Comparación honesta:** quitar el relieve movía el receptor mediano un **30 %**. El relieve
> pesa **~27 veces más** que el uso del suelo, *incluso comparándolo con el paisaje más
> contrastado que se puede construir*.

> **🧠 CONCEPTO · Por qué el Bowen (🟠) es el que MENOS efecto produce**
>
> Contra lo que esta guía anticipaba, el escenario de Bowen da el efecto **más pequeño**
> (0,2 %), pese a partir de un contraste de clases de ×6. Dos razones se suman:
>
> 1. **Bowen no tiene resolución direccional.** Es **un solo número para todo el dominio**
>    (§12.5), sin sectores. Un paisaje heterogéneo y uno uniforme difieren en *un* valor
>    (0,286 vs 0,100), no en un patrón espacial que el modelo pueda explotar.
> 2. **Actúa indirectamente.** Bowen reparte energía y modula la estabilidad; `z₀` entra
>    **directamente** en el perfil logarítmico del viento y en el cálculo de `u*`.
>
> **Orden real de importancia:** `z₀` > Bowen > albedo — y los tres muy por detrás del relieve.

### 14.3.3 Donde sí se nota: el pico, no la mediana

![Mapas del escenario máximo](images/usos_mapas_maximo.png)

> **📈 CORRELACIÓN · La mediana y el máximo responden a cosas distintas**
>
> La mediana se mueve un 1 %, pero **el máximo de concentración cae entre un 9 % y un 15 %** al
> uniformizar, de forma **consistente en los cuatro escenarios**.
>
> El mecanismo: el pico aparece cuando el viento llega **por el sector más liso** —menos
> turbulencia, penacho más concentrado— y al uniformizar, ese sector privilegiado se pierde.
>
> **Y esto es lo que decide el cumplimiento normativo.** El límite legal se compara con el
> pico, no con la mediana. Ignorar el uso del suelo introduce un **sesgo sistemático a la baja
> del 10-15 % justo en el valor que decide si apruebas o no**. Por eso se mantiene CORINE en la
> herramienta: cuesta poco y evita ese sesgo.

### 14.3.4 La altura del foco: la intuición estaba al revés

Se repitieron los cuatro escenarios a **1 m, 3 m y 6 m** de altura de emisión.

![Sensibilidad según la altura del foco](images/usos_altura.png)

> **🔢 DATO · Desviación mediana al uniformizar, por altura**
>
> | Escenario | Contraste direccional | **z = 1 m** | **z = 3 m** | **z = 6 m** | 1 m → 6 m |
> |---|---|---|---|---|---|
> | 🟢 BAJO | ×2,6 | 0,30 % | 0,51 % | **0,76 %** | ×2,5 |
> | 🟡 MEDIO | ×5,9 | 0,45 % | 0,81 % | **1,22 %** | ×2,7 |
> | 🟠 ALTO | ×1,3 | 0,10 % | 0,16 % | **0,26 %** | ×2,5 |
> | 🔴 MÁXIMO | ×53 | 0,57 % | 1,14 % | **1,59 %** | ×2,8 |

> **⚠️ RECTIFICACIÓN · «Un foco más bajo es más sensible a la rugosidad» es FALSO**
>
> Era la predicción natural, y esta guía la defendía: *un foco a ras de suelo vive dentro de la
> capa donde `z₀` manda, así que debería notar más el uso del suelo.*
>
> **Los datos dicen exactamente lo contrario.** La sensibilidad **crece de forma monótona con
> la altura** en los cuatro escenarios, multiplicándose por **~2,6** entre 1 m y 6 m. Las
> cuatro curvas del panel central de la figura suben sin excepción.
>
> Y suben **manteniendo su orden**: el escenario más contrastado sigue siendo el más sensible a
> cualquier altura. Es decir, **la altura escala el efecto, no cambia el mecanismo** — la
> conclusión de §14.3.1 se mantiene intacta.
>
> *(Hay una hipótesis de por qué —`z₀` actúa por dos vías opuestas: frena el viento pero genera
> turbulencia, y para un foco a ras de suelo el receptor ya está en el eje del penacho, así que
> la segunda vía pierde peso— pero **no está comprobada** y no explica el punto siguiente. Se
> deja como hipótesis, no como explicación.)*

> **⚠️ OJO · El pico NO sigue la misma regla: hace máximo a 3 m**
>
> | Caída del máximo al uniformizar | z = 1 m | z = 3 m | z = 6 m |
> |---|---|---|---|
> | 🟢 BAJO | −4,5 % | **−8,5 %** | −7,1 % |
> | 🟡 MEDIO | −7,5 % | **−13,3 %** | −10,9 % |
> | 🟠 ALTO | −1,5 % | **−3,0 %** | −2,6 % |
> | 🔴 MÁXIMO | −9,5 % | **−14,5 %** | −10,1 % |
>
> El máximo **no crece con la altura: hace pico en torno a 3 m** y vuelve a bajar a 6 m, en los
> cuatro escenarios. Así que mediana y pico responden a la altura de manera distinta, igual que
> ya respondían de manera distinta al contraste (§14.3.3).
>
> **No hay explicación comprobada para ese óptimo intermedio**, y con solo tres alturas tampoco
> se puede situar con precisión. Queda anotado como lo que es: un hecho medido sin teoría.

> **🔑 EL RESULTADO MÁS ÚTIL DE TODO EL EXPERIMENTO**
>
> Mira los valores **absolutos** del escenario BAJO al cambiar la altura del foco:
>
> ```
> foco a 1 m  →  máximo 68,7 µg/m³
> foco a 3 m  →  máximo 18,0 µg/m³
> foco a 6 m  →  máximo  5,7 µg/m³
> ```
>
> **Un factor ×12 en cinco metros de altura.** Frente al 0,3-0,8 % que mueve el uso del suelo
> en ese mismo escenario.
>
> **Acertar la altura de emisión importa muchísimo más que acertar el uso del suelo.** Si tienes
> que elegir dónde gastar el esfuerzo de medición en campo, mide bien a qué altura emite tu
> fuente antes de refinar nada del terreno.

### 14.3.5 Dos rectificaciones del propio experimento

El análisis corrige una versión anterior de sí mismo. Ambos errores se detectaron **verificando
el código, no mirando los resultados** — que es como se detectan los errores que importan:

> **⚠️ 1. El escenario ALTO no medía lo que decía**
>
> Las clases NLCD 31 y 52 no se indexan por `airport`/`non_airport` sino por
> **`arid`/`non_arid`**, y el script de diseño cogía por descarte la variante árida. La
> vegetación esclerófila no tiene Bowen 4,0 sino **1,10** con `arid=False`, que es como corre
> la aplicación. El contraste era **×2, no ×8**, y la conclusión «la rugosidad pesa más que el
> Bowen» se apoyaba en una comparación mal etiquetada. Rehecho con el contraste real (×6), la
> conclusión **se mantiene — ahora sí fundamentada**.

> **⚠️ 2. Los patrones sintéticos inflaban el efecto ×4**
>
> La primera versión repartía las clases en **sectores angulares** alrededor del foco. Fue un
> error de diseño: como AERMOD resuelve la rugosidad **por sector de dirección**, unos sectores
> sintéticos alinean el contraste exactamente con el eje que el modelo mejor capta.
>
> Resultado: un contraste direccional de ×1300 donde un paisaje real da ×53, y medianas de
> 2,7 % / 4,8 % en vez de 0,8 % / 1,1 %. Al hacer realista **solo la geometría**, el máximo del
> caso heterogéneo bajó de **25,59 a 15,15 µg/m³**: **la mitad de lo que parecía "efecto del
> uso del suelo" era efecto del patrón inventado.**
>
> Es una lección metodológica general: **al diseñar un experimento sintético, cuidado con
> construir sin querer la geometría que tu modelo resuelve mejor.** Lo que mides entonces es tu
> propio diseño, no la física.

### 14.3.6 Qué queda establecido

> **🧠 CONCEPTO · Prioridad de esfuerzo, ordenada por lo medido**
>
> ```
> caudal Q  ≫  altura del foco  ≫  relieve  ≫  rugosidad (z₀)  >  Bowen  >  albedo
>  (error ×10⁷)   (×12 en 5 m)      (30 %)         (~1 %)
> ```
>
> Los dos primeros son **datos de la fuente que tú aportas**; los demás se descargan solos. Y
> es justo al revés de donde suele ponerse el esfuerzo: se discute mucho la resolución del
> terreno y muy poco de dónde sale el caudal o a qué altura emite realmente el foco.

> **💼 Cuándo prestar atención especial al uso del suelo**
>
> La clave es **la escala de las manchas**, no las clases:
>
> | Situación | Riesgo de simplificar |
> |---|---|
> | Foco en la orilla de un **embalse, mar o llanura lisa** con bosque o ciudad enfrente — contraste **grande y direccional** | 🔴 alto |
> | **Frente urbano-rural** neto que cubre varios sectores de 30° | 🟡 medio |
> | Contraste **seco/regadío** sin cambio de rugosidad | 🟢 bajo |
> | **Mosaico fragmentado** de cualquier tipo, aunque sus clases sean extremas | 🟢 despreciable |
>
> Y un límite duro: el radio de promediado de `z₀` es de **1 km**. Un contraste que solo exista
> a escala menor **no llegará al modelo en ningún caso**.

> **⚠️ OJO · Alcance: nada de esto se ha probado con chimeneas**
>
> Todo el experimento es con **fuentes de área** a 1, 3 y 6 m. La tendencia medida es
> *creciente* con la altura, así que extrapolar sugeriría que una chimenea sería **más**
> sensible al uso del suelo — lo contrario de lo que suele afirmarse.
>
> **No lo damos por bueno.** 6 m sigue siendo una fuente baja, la tendencia podría invertirse
> más arriba (el pico ya se invierte en §14.3.4), y **la última extrapolación no medida de este
> documento resultó ser falsa**. Si tu caso son chimeneas, hay que medirlo.

> **📖 El análisis completo**, con las tablas de 50 receptores a las tres alturas y las
> instrucciones para reproducirlo, está en **`analisis_sensibilidad_usos.md`**.

> **🧠 CONCEPTO · Lo que este par de experimentos deja establecido**
>
> **La importancia de un dato de entrada no es una propiedad del dato: es una propiedad del
> emplazamiento y de la fuente.** No existe "el uso del suelo importa un 1 %". Existe "el uso
> del suelo importa un 1 % *en un paisaje fragmentado, para una fuente de área a 3 m*".
>
> Y una lección sobre el método, que estas secciones ilustran mejor que cualquier discurso:
> **de las predicciones que esta guía hizo antes de medir, dos resultaron falsas** (que el
> efecto se dispararía con el contraste; que un foco bajo sería más sensible). Estaban
> razonadas y eran plausibles. Por eso se mide.

---

# Parte V — Cierre

## 15. Qué NO hace el modelo gaussiano <a id="15-qué-no-hace-el-modelo-gaussiano"></a>

Un modelo que no sabes dónde falla es un modelo peligroso. La ecuación de §5.2 lleva
**hipótesis metidas dentro**:

> **⚠️ OJO · Las hipótesis que has aceptado sin darte cuenta**
>
> | Hipótesis | Qué significa | Cuándo te traiciona |
> |---|---|---|
> | **Estado estacionario** | El viento no cambia mientras el penacho viaja | Brisas que rolan, frentes |
> | **Homogeneidad** | El mismo viento en todo el dominio | Terreno complejo, valles |
> | **Terreno llano** | No hay montañas | Justo lo tuyo: montaña |
> | **Conservación de masa** | Ni se deposita ni reacciona | Partículas, NOx, lluvia (§8) |
> | **`u` no nulo** | Hay una dirección de transporte | Calmas nocturnas |
> | **Sin difusión en `x`** | Se desprecia frente a la advección | Solo falla si `u` ≈ 0 |
> | **Gas pasivo** | La nube no tiene densidad propia | Gases densos (abajo) |

> **⚠️ OJO · Gases densos: aquí el gaussiano NO vale, y punto**
>
> Todo esto supone que la nube **se deja llevar** por el aire. Si el gas es
> significativamente **más denso** (cloro, GLP, CO₂ concentrado, un vertido criogénico),
> la nube tiene vida propia: **se derrama por el suelo como un líquido**, fluye cuesta
> abajo, se mete en depresiones y se resiste a mezclarse.
>
> Eso no es un ajuste del gaussiano: es otra física. Necesita modelos de gas denso (SLAB,
> DEGADIS, PHAST). **AERMOD no sirve** para un escape de cloro. Saber cuándo *no* usar tu
> herramienta es parte de saber usarla.

> **🔗 EN LA HERRAMIENTA · Qué añade AERMOD sobre el gaussiano de libro**
>
> AERMOD es un gaussiano *de última generación*: mantiene la campana como esqueleto pero
> arregla los peores defectos.
>
> - **Terreno:** trata cada receptor como mezcla de dos estados —un penacho que *rodea* el
>   obstáculo y otro que lo *remonta*— y pesa ambos. Por eso hace falta `getTerrain` y el
>   `.npz` de elevaciones.
> - **Turbulencia continua:** `σy`, `σz` desde `u*`/`L`/`zi`, sin clases de Pasquill.
> - **Convección realista:** bi-gaussiana asimétrica cuando `L < 0`.
> - **Rugosidad por uso del suelo:** `z₀`, albedo y razón de Bowen desde CORINE.
> - **Edificios:** el penacho puede quedar atrapado en la estela de un edificio
>   (*downwash*). De ahí que se descarguen los edificios.
> - **Áreas y volúmenes:** integración numérica sobre la geometría real (§6).
>
> Lo que **sigue sin hacer**: química no lineal, gases densos, no-estacionariedad, y el
> factor pico-media de los olores (§9), que hay que aplicar por fuera.

> **🔗 EN LA HERRAMIENTA · Y por eso entra un segundo motor: CALPUFF**
>
> Varias de las limitaciones de la tabla anterior no son defectos de implementación: son
> consecuencia de que AERMOD modela un **penacho estacionario**. Da igual lo bien que estén
> `σy` y `σz`: si el modelo supone que el viento es el mismo mientras el penacho viaja, no
> puede representar un viento que rola ni una calma.
>
> **CALPUFF ataca justo eso.** En vez de un penacho continuo, suelta **bocanadas** (*puffs*)
> que viajan cada una con el viento que encuentra en su momento y su posición. Eso lo hace
> **no estacionario**, y le permite representar:
>
> | Limitación del gaussiano | Qué hace CALPUFF |
> |---|---|
> | Estado estacionario | Cada bocanada lleva su propia historia meteorológica |
> | Homogeneidad (mismo viento en todo el dominio) | **CALMET** construye un campo de viento **3D** que varía en el espacio |
> | `u` no nulo (las calmas rompen el modelo) | Una bocanada en calma simplemente no avanza — y se sigue dispersando |
> | Terreno llano | Campo de viento diagnóstico que rodea el relieve |
>
> El precio es que la cadena es más pesada: **CALMET** no es un preprocesador como AERMET,
> es un **modelo meteorológico** por derecho propio.
>
> **⚠️ Y no es gratis en precisión.** El estudio de evaluación de referencia (Rzeszutek 2019)
> encuentra que ni la mejor configuración de CALPUFF cumple los criterios de sesgo habituales,
> con una incertidumbre estructural del orden de **±50 %** — y que **sus peores métricas salen
> precisamente en condiciones estables y de calma**, que es el caso que motiva usarlo. Que sea
> el modelo adecuado para un problema **no significa** que su resultado sea exacto.
>
> Detalle completo, con la configuración recomendada y el estado de la implementación, en
> [`notas_calpuff.md`](notas_calpuff.md).

---

## 16. De la teoría a esta herramienta <a id="16-de-la-teoría-a-esta-herramienta"></a>

Cerremos el círculo. Todo lo que hace la app es **rellenar los huecos de la ecuación
gaussiana**:

| Hueco de la ecuación | Qué hace falta | Quién lo consigue |
|---|---|---|
| `Q` y geometría del foco | emisión y forma | **AERSOURCE** (tú los dibujas) |
| `hs`, `ds`, `Ts`, `vs` → `H` | sobreelevación (§7) | **AERSOURCE** |
| `u`, dirección | viento | **getMeteo** → `u10`, `v10` (§11.1) |
| `σy`, `σz` | `u*`, `L`, `zi` | **getMeteo** → `zust`, `sshf`, `blh` (§11.3–11.8) |
| `z₀`, albedo, Bowen | uso del suelo | **getTerrain** → CORINE (§12) |
| cota de cada receptor | elevación | **getTerrain** → MDT05 (`.npz`) (§14) |
| cizalladura en altura | perfil de presión | **getMeteo** → niveles ERA5 (§13) |
| *downwash* | edificios | **getTerrain** → WFS de edificios |
| 8760 h para percentiles (§9) | año completo | **getMeteo** → años enteros |
| `C` en cada punto | **la incógnita** | **AERMOD** → mapa de la pestaña AERMOD |

> **🧠 CONCEPTO · Por qué hay tres programas y no uno**
>
> La cadena oficial de la EPA separa responsabilidades:
>
> - **AERMET** — coge la meteorología cruda y calcula los parámetros de la capa límite
>   (`u*`, `L`, `zi`). Produce `.sfc` (superficie) y `.pfl` (perfil).
> - **AERMAP** — coge el terreno y calcula, para cada receptor, su cota y su *escala de
>   altura de colina*.
> - **AERMOD** — coge las salidas de los dos anteriores más las fuentes, y calcula `C`.
>
> Y ahora las pestañas de la app tienen sentido: **AERMET** y **AERMAP** no son nombres
> caprichosos, son las dos etapas de preproceso; **AERSOURCE** son los focos; y **AERMOD**
> es el resultado.

---

## Resumen en dieciocho líneas

1. Queremos pasar de **emisión** (g/s) a **inmisión** (µg/m³ o ou_E/m³).
2. Al contaminante lo **transporta** el viento y lo **diluye** la turbulencia.
3. La turbulencia es **mecánica** (rozamiento, `u*`) y **térmica** (calor, `H`).
4. `L` combina ambas y dice si la atmósfera es **estable** o **inestable**.
5. Lo peor: **noche estable, calma, capa de mezcla baja**. De ahí las quejas de madrugada.
6. Como la turbulencia es aleatoria, el penacho sale **gaussiano** (TCL) — pero **crece
   casi lineal**, no como √x.
7. Toda la física vive en **`σy` y `σz`**; el resto es geometría y conservación de masa.
8. El suelo **refleja**: fuente imagen, y **duplica** la concentración.
9. Por **linealidad**, cualquier fuente (área, volumen, línea) es una suma de puntuales.
   Se acabó necesitar teoría nueva.
10. **La chimenea es la excepción:** tiene `Δh` grande y su máximo cae lejos. Compostaje,
    EDAR y balsas son **fuentes pasivas** (`Δh≈0`, `H≈0`): máximo **pegado a la valla**.
11. **Olores:** unidad sensorial (`ou_E`), umbral = 1 por definición, criterio por
    **percentil** (no máximo), y el modelo da medias horarias mientras la nariz detecta
    **picos de segundos** → factor pico-media de hasta ×10.
12. En mezclas, ordena por **`Q`/umbral**, no por `Q`: el H₂S manda aunque el NH₃ sea más
    abundante.
13. Ninguna variable entra "directa": todas pasan por **`u*`** (rozamiento) y **`L`**
    (estabilidad), que son los que fabrican `σy` y `σz`. Las críticas son **viento, flujo de
    calor y altura de capa de mezcla** (§11).
14. El **uso del suelo no entra como paisaje, sino como meteorología**: se traduce a
    **`z₀`, albedo y Bowen**, y de ahí modifica el viento y la estabilidad (§12).
15. Los datos **en altura** vienen por **presión**, no por metros: algunos niveles caen
    **bajo tierra** y hay que filtrarlos hora a hora (§13).
16. **Manda el dato que más varía dentro de TU dominio** — y lo que cuenta del uso del suelo
    no es el contraste entre clases, sino si está **organizado** a la escala del sector de
    viento: un mosaico fragmentado se promedia solo (§14.3).
17. **Prioridad de esfuerzo, medida:** `Q` ≫ **altura del foco** ≫ relieve ≫ `z₀` > Bowen >
    albedo. La altura mueve el máximo **×12 en 5 metros**; el uso del suelo, un 1 % (§14.3.4).
18. El uso del suelo casi no mueve la **mediana** (~1 %) pero sesga el **pico un 10-15 %** —
    y el pico es lo que se compara con el límite legal. Por eso se mantiene CORINE (§14.3.3).

---

## Referencias

> **Cómo leer esta lista.** Está dividida en dos bloques según su grado de comprobación, porque
> una cita mal puesta en un informe es tan dañina como un número mal puesto:
>
> - **✅ Verificadas** — contrastadas contra el código de la herramienta, contra la documentación
>   oficial del programa o contra el texto normativo primario.
> - **⚠️ Por verificar** — literatura clásica citada de conocimiento general. Los conceptos son
>   correctos y de dominio común, pero **el detalle bibliográfico exacto (año, volumen, páginas)
>   no se ha comprobado contra la fuente**. Antes de llevar cualquiera de estas a un informe,
>   compruébala.

### ✅ El modelo y su cadena (EPA)

Todos los ejecutables son de dominio público y se descargan del **SCRAM** de la EPA
(*Support Center for Regulatory Atmospheric Modeling*): <https://www.epa.gov/scram>

| Programa | Qué hace | Ruta en SCRAM |
|---|---|---|
| **AERMOD** | El modelo de dispersión | `models/preferred/aermod/aermod_exe.zip` |
| **AERMAP** | Preprocesador de terreno | `models/related/aermap/aermap_exe.zip` |
| **BPIPPRM** | *Downwash* de edificios | `models/related/bpip/bpipprime.zip` |

- Versión de AERMAP empleada en los casos de estas guías: **24142**.
- **AERSURFACE** — guía de usuario **EPA-454/B-26-007**, versión 26135, Apéndice B. De aquí salen
  las tablas de `z₀`, albedo y razón de Bowen por clase NLCD y estación (§12).
  ⚠️ Los valores de la herramienta se tomaron del **código fuente Fortran** del programa
  (`mod_LandCoverParams.f`, subrutina `InitLCSurfChar`), **no del PDF**, porque el PDF contiene
  al menos cuatro erratas comprobadas (§12.2).

### ✅ Fuentes de datos

| Dato | Origen | Acceso |
|---|---|---|
| Elevación (MDT05) | CNIG / PNOA, IGN España | <https://centrodedescargas.cnig.es> · <https://www.ign.es> |
| Uso del suelo (CORINE Land Cover) | Copernicus Land Monitoring Service | <https://land.copernicus.eu> |
| Meteorología (ERA5, ERA5-Land) | Copernicus Climate Data Store, ECMWF | <https://cds.climate.copernicus.eu> |
| Viento de estación | AEMET OpenData | <https://opendata.aemet.es> |
| Edificios | Sede Electrónica del Catastro | <https://ovc.catastro.meh.es> |
| Servicios geográficos | IDEE — Infraestructura de Datos Espaciales de España | <https://servicios.idee.es> |

### ✅ Normas

- **UNE-EN 13725** — *Calidad del aire. Determinación de la concentración de olor por
  olfatometría dinámica.* Define la **unidad de olor europea (ou_E)**: 1 ou_E/m³ es, por
  construcción, la concentración a la que la mitad de un panel detecta el olor (§9).
- **Wieringa, J. (1993)** — «Representative roughness parameters for homogeneous terrain»,
  *Boundary-Layer Meteorology* **63**: 323-363. Clasificación de rugosidad de
  **Davenport-Wieringa**, adoptada por la OMM y ESDU. Es la base de la corrección de `z₀` para
  cultivos leñosos (§12.6).
- **Nagata, Y. (2003)** — compendio de **umbrales olfativos** por compuesto, el más citado. Base
  de la tabla de umbrales de la herramienta.
  ⚠️ Los umbrales publicados varían **hasta ×30** entre fuentes (para el H₂S se publican valores
  de 0,4 a 13 ppb). Para un expediente, usa el umbral que exija la normativa aplicable y déjalo
  escrito (§10).

Para la normativa de calidad del aire, emisiones industriales y olores, ver los documentos
dedicados en [`../bibliografia/normativa/`](../bibliografia/normativa/), que citan el texto legal
primario con su fecha y estado de vigencia.

### ⚠️ Literatura científica — por verificar

Conceptos de dominio común en dispersión atmosférica. **El detalle bibliográfico no está
comprobado**; se listan para orientar la búsqueda, no para citar tal cual.

| Concepto de esta guía | Referencia habitual |
|---|---|
| Formulación de AERMOD (§15) | Cimorelli *et al.* — descripción del modelo, *J. Applied Meteorology* (2005) |
| Tratamiento del terreno en AERMOD (§15) | Perry *et al.* — AERMOD y terreno complejo (2005) |
| Teoría de semejanza, `L` (§4, §11.5) | Monin & Obukhov (1954) |
| Capa límite atmosférica (§4) | Stull, *An Introduction to Boundary Layer Meteorology* |
| Sobreelevación del penacho `Δh` (§7) | Briggs — *Plume rise* (1975) |
| Clases de estabilidad, `σy`/`σz` clásicos (§5.4) | Pasquill (1961); Gifford (1961); Turner, *Workbook of Atmospheric Dispersion Estimates* |
| Química atmosférica, NOₓ (§8) | Seinfeld & Pandis, *Atmospheric Chemistry and Physics* |
| Factor pico-media en olores (§9) | Smith; Best *et al.*; Schauberger |
| Ley potencial de la percepción (§9) | Stevens — «On the psychophysical law» |
| Reanálisis ERA5 (§11, §13) | Hersbach *et al.* (2020), *Q. J. R. Meteorol. Soc.* |

### 📁 Documentación propia del proyecto

| Documento | Contenido |
|---|---|
| [`user_guide.md`](user_guide.md) | La herramienta paso a paso |
| [`notas_perfil_vertical.md`](notas_perfil_vertical.md) | El perfil de ERA5 por niveles de presión y el "nivel bajo tierra" |
| [`analisis_sensibilidad_terreno.md`](analisis_sensibilidad_terreno.md) | Experimento 1: relieve vs uso del suelo (§14.1-14.2) |
| [`analisis_sensibilidad_usos.md`](analisis_sensibilidad_usos.md) | Experimento 2: contraste de paisaje y altura del foco (§14.3) |
| [`../bibliografia/`](../bibliografia/) | Normativa y estudios de referencia por temática |

---

*Siguiente: `user_guide.md` — cómo usar la herramienta paso a paso.*
*Nota técnica relacionada: `notas_perfil_vertical.md` — el perfil de ERA5 en detalle.*
