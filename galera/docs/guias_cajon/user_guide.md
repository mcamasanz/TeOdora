# Guía de usuario — la herramienta paso a paso

> **Para quién es esto:** para alguien de primero de ingeniería que quiera **usar** la
> herramienta y, de paso, entender qué está haciendo un estudio de dispersión atmosférica.
> No hace falta haber tocado AERMOD nunca. Sí ayuda haber leído antes la guía teórica
> (`theory_guide.md`): esta guía es su pareja. La teórica cuenta **por qué** (la física);
> esta cuenta **cómo** (los botones, los ficheros, el criterio de proyecto). Cuando algo se
> explica allí, aquí solo se enlaza y se dice qué botón lo pone en marcha.

> **✅ Estado de la herramienta (20 de julio de 2026)**
>
> **El ciclo completo funciona desde la ventana, de principio a fin.** Defines el dominio,
> descargas terreno y meteorología, dibujas las fuentes, pulsas **«Run»** y obtienes el mapa
> de concentración. La cadena AERMAP → BPIPPRM → AERMOD se ejecuta entera por dentro.
>
> Validado end-to-end con el caso real de Lleida (año completo 2023, 8760 horas, H₂S):
> **0 errores, 0 avisos** de AERMOD.
>
> *(Si vienes de la primera versión de esta guía: el botón «Run» ya **no** es un stub. Aquello
> quedó obsoleto y esta guía está reescrita contra el código actual.)*

---

## Índice

**Parte 0 — Antes de empezar**
- [0.1 Qué hace la herramienta, en una frase](#01-que-hace)
- [0.2 Lo que necesitas instalado y dado de alta](#02-requisitos)
- [0.3 La ventana: un vistazo general](#03-la-ventana)
- [0.4 El modelo mental de los datos: `tmp/` vs `data/`](#04-datos)

**Parte 1 — El flujo de un proyecto**
- [1.1 Los cinco pasos = la cadena AERMOD](#11-cinco-pasos)
- [1.2 El ejemplo que seguiremos](#12-ejemplo)
- [1.3 Qué datos entran en el modelo y por qué (mapa general)](#13-que-datos)

**Parte 2 — Paso 1: definir el dominio**
- [2.1 El panel de configuración, campo a campo](#21-panel)
- [2.2 La malla de receptores: resolución y razón de crecimiento](#22-malla)
- [2.3 «View Map»: mira antes de descargar](#23-viewmap)
- [2.4 Criterio de proyecto: tamaño, resolución y periodo](#24-criterio-dominio)

**Parte 3 — Paso 2: el terreno (getTerrain → AERMAP)**
- [3.1 Qué hace «getTerrain»](#31-getterrain)
- [3.2 Las capas de terreno en la pestaña Mapa](#32-capas-mapa)
- [3.3 Qué es AERMAP en la cadena](#33-que-es-aermap)
- [3.4 El uso del suelo: cómo un bosque se convierte en tres números](#34-uso-del-suelo)
- [3.5 ¿Cuánto importa el terreno? El experimento de Lleida](#35-experimento)
- [3.6 «LoadTerrain»](#36-loadterrain)

**Parte 4 — Paso 3: la meteorología (getMeteo → AERMET)**
- [4.1 Qué hace «getMeteo»](#41-getmeteo)
- [4.2 Las once variables que se descargan, y para qué sirve cada una](#42-variables)
- [4.3 El perfil vertical: los datos en altura](#43-perfil)
- [4.4 Las gráficas de meteo en la pestaña Mapa](#44-meteo-mapa)
- [4.5 Qué es AERMET y por qué aquí no se usa](#45-que-es-aermet)
- [4.6 «LoadMeteo», caché y reutilización](#46-loadmeteo)
- [4.7 Dos motores: AERMOD y CALPUFF](#47-dos-motores)

**Parte 5 — Paso 4: las fuentes de emisión (pestaña Dispersión)**
- [5.1 Dibujar una fuente puntual](#51-punto)
- [5.2 Dibujar una fuente de área](#52-area)
- [5.3 Los parámetros de cada fuente](#53-parametros)
- [5.4 Contaminante y unidades: masa (g) u olor (ou_E)](#54-contaminante)
- [5.5 Guardar, cargar y `sources.json`](#55-guardar)
- [5.6 Criterio de proyecto: cómo modelar cada caso real](#56-criterio-fuentes)

**Parte 6 — Paso 5: la simulación («Run» → AERMOD)** <a id="parte-6"></a>
- [6.1 Pulsar «Run»: qué comprueba y qué ejecuta](#61-run)
- [6.2 Qué monta por dentro (la cadena entera)](#62-cadena)
- [6.3 «Save» y «Load»: guardar y recuperar resultados](#63-save-load)

**Parte 7 — Leer e interpretar el resultado**
- [7.1 El mapa de concentración](#71-mapa-conc)
- [7.2 Medias, máximos y periodos de promediado](#72-promedios)
- [7.3 El caso de los olores: lo que hay que hacer POR FUERA](#73-olores)
- [7.4 Comparar con la normativa](#74-normativa)

**Parte 8 — Recetario por tipo de proyecto**
- [8.1 Chimenea industrial](#81-chimenea)
- [8.2 Planta de compostaje](#82-compostaje)
- [8.3 EDAR con problema de olor](#83-edar)
- [8.4 Cantera / acopio (partículas)](#84-cantera)

**Parte 9 — Cuando algo falla**
- [9.1 Problemas frecuentes y su causa](#91-problemas)

**Parte 10 — Anexos**
- [10.1 Mapa de ficheros: qué es cada cosa que genera la herramienta](#101-ficheros)
- [10.2 Checklist de un estudio completo](#102-checklist)
- [10.3 Glosario exprés de siglas](#103-glosario)
- [10.4 Referencias y de dónde sale cada dato](#104-referencias)

---

# Parte 0 — Antes de empezar

## 0.1 Qué hace la herramienta, en una frase <a id="01-que-hace"></a>

> **Coges un punto del mapa y unos focos de emisión, y la herramienta te devuelve un mapa
> de colores de cuánto contaminante (u olor) habrá en el aire alrededor.**

Por dentro, eso es exactamente el problema de la guía teórica: pasar de **emisión** (lo que
sale del foco, g/s) a **inmisión** (lo que hay en el aire donde está la gente, µg/m³). La
herramienta es un **envoltorio** alrededor de **AERMOD**, el modelo de dispersión de la EPA
estadounidense, que es el estándar regulatorio en medio mundo.

Lo que la herramienta añade sobre "abrir AERMOD a pelo" es que **te consigue sola todos los
datos de entrada** —terreno, uso del suelo, edificios, meteorología de un año entero— desde
servicios públicos españoles y europeos, y te deja **dibujar los focos con el ratón** sobre
un mapa. Eso, que suena a poco, es el 90 % del trabajo tedioso de un estudio real.

> **🧠 CONCEPTO · La herramienta no calcula la dispersión: la calcula AERMOD**
>
> Es importante tenerlo claro desde el principio. La física (las campanas de Gauss, la
> turbulencia, el terreno) la resuelve **AERMOD**, un programa de la EPA que vive en
> `src/bin/aermod.exe`. La herramienta **prepara los ficheros que AERMOD necesita** y luego
> **pinta lo que AERMOD devuelve**. Si algún día el resultado te parece raro, el sospechoso
> casi nunca es AERMOD (lleva 20 años auditado): es **algún dato de entrada** que le hemos
> dado mal. Por eso esta guía insiste tanto en entender cada dato.

## 0.2 Lo que necesitas instalado y dado de alta <a id="02-requisitos"></a>

Antes de que nada funcione, cuatro cosas tienen que estar en su sitio. Las tres primeras se
montan una sola vez.

**1. El entorno de Python.** La herramienta se lanza con un intérprete de Python que trae
todas las librerías geoespaciales (rasterio, geopandas, pyproj, folium, PySide6…). En esta
máquina es:

```
C:\e2s\python.exe
```

No vale el Python que VSCode use por defecto (le faltan librerías; el editor marcará
"errores" de import que son falsos). Para arrancar la app:

```
C:\e2s\python.exe app.py
```

Si te llevas el proyecto a otro ordenador, sigue `README_ENTORNO.md` (en la raíz): explica
cómo recrear el entorno con conda + pip.

**2. Dos claves de API** (dos ficheros de texto, una línea cada uno). Sin ellas no hay
descargas de meteorología:

| Fichero | Qué es | Dónde se saca |
|---|---|---|
| `src/config/keys/aemet-api-key.txt` | Token de **AEMET OpenData** (viento de estaciones reales) | https://opendata.aemet.es |
| `src/config/keys/cds-api-key.txt` | Token del **CDS de Copernicus** (reanálisis ERA5) | https://cds.climate.copernicus.eu |

**3. Las licencias del CDS aceptadas.** Con tu cuenta de Copernicus, entra una vez en la web
del CDS y **acepta la licencia** de estos **tres** datasets, o las descargas darán error `403`:

- *ERA5 hourly data on single levels* (la meteo de superficie: las once variables de §4.2).
- *ERA5-Land hourly* (viento a más resolución).
- *ERA5 hourly data on **pressure levels*** (el perfil vertical, §4.3).

> **⚠️ Cambio respecto a versiones anteriores:** el perfil vertical **ya no es opcional**. Antes
> había una casilla para activarlo; ahora se descarga **siempre**, porque aporta la cizalladura
> real del viento en altura (§4.3) y su ausencia pasaba desapercibida. Si la licencia de
> *pressure levels* no está aceptada, la app te avisa explícitamente en la consola con
> `❌ PERFIL VERTICAL: no se descargó ni un fichero…` en lugar de fallar en silencio.

**4. Los ejecutables de AERMOD** ya vienen en el proyecto, en `src/bin/`:

```
src/bin/aermap.exe      ← procesa el terreno
src/bin/aermod.exe      ← el modelo de dispersión
src/bin/bpipprm.exe     ← edificios (efecto downwash)
```

Son los **binarios oficiales de la EPA** (SCRAM). No hay que instalarlos ni licenciarlos:
AERMOD es de dominio público. La versión de referencia de la EPA a día de hoy es la
**24142** (noviembre 2024).

> **🩺 SI FALLA aquí:** el síntoma típico de intérprete equivocado es un `ModuleNotFoundError`
> de numpy, rasterio o PySide6 nada más arrancar. El de clave/licencia es un mensaje de la
> consola con `403` o `licence`. Ninguno de los dos rompe la app entera: la meteo puede
> fallar y el terreno seguir yendo, porque cada descarga va en su propio `try/except`.

## 0.3 La ventana: un vistazo general <a id="03-la-ventana"></a>

Al arrancar verás la ventana partida en tres:

```
┌──────────────────────────┬────────────────────────────────┬───────────────┐
│  PANEL DE CONFIGURACIÓN  │  PESTAÑAS DE RESULTADO         │  ASISTENTE  ▶ │
│  (izquierda, fijo)       │  (centro)                      │  (derecha)    │
│                          │ ┌────┬──────────┬──────────┐   │               │
│  · Latitud / Longitud    │ │Mapa│Dispersión│Resultados│   │ ┌───────────┐ │
│  · Resolución (en focos) │ └────┴──────────┴──────────┘   │ │ historial │ │
│  · Razón de crecimiento  │                                │ │  de la    │ │
│  · Dist. elevación/uso   │   (aquí se van dibujando los   │ │ conversa- │ │
│  · Dist. edificios       │    mapas a medida que pulsas   │ │   ción    │ │
│  · Estación meteo        │    los botones)                │ └───────────┘ │
│  · Años / Meses          │                                │               │
│  · Receptores: 650 …     │ ← etiqueta viva: cuenta        │ Para empezar: │
│                          │   receptores y estima tiempo   │ [🧭 ¿Cómo…?]  │
│  [View Map]              │                                │ [📋 Redactar] │
│  [getTerrain][LoadTerr.] │                                │ [⚖️ Criterio] │
│  [getMeteo ][LoadMeteo]  │                                │ [🔍 Revisa…]  │
│  [Run      ][Save     ]  │                                │ ┌───────────┐ │
│  [Load                ]  │                                │ │ escribe…  │ │
│                          │                                │ └───────────┘ │
│  ▓▓▓▓░░ (barra progreso) │                                │ [Limpiar][▶] │
│  Estado: Listo.          │                                │               │
│  ┌─ Consola ───────────┐ │                                │               │
│  │ (mensajes del       │ │                                │               │
│  │  proceso, en negro) │ │                                │               │
│  └─────────────────────┘ │                                │               │
└──────────────────────────┴────────────────────────────────┴───────────────┘
```

**El panel de la izquierda** define *dónde* y *cuándo*, y tiene los botones que lanzan cada
paso. Abajo del todo hay una **consola** que refleja todo lo que el proceso va imprimiendo:
acostúmbrate a leerla, porque ahí salen las rutas de los ficheros, los avisos y los errores.

**Las tres pestañas de la derecha** te enseñan el resultado de cada paso, y —esto es lo
bonito del diseño— **se llaman como las etapas de la cadena AERMOD**:

| Pestaña | Qué muestra | Etapa de AERMOD |
|---|---|---|
| **Mapa** | La región, los recuadros de dominio (terreno y edificios), las estaciones meteo cercanas y la malla; tras getTerrain, elevación, uso del suelo y edificios en capas; tras getMeteo, las rosas de viento y las variables meteo como paneles fijos. Solo una capa encendida a la vez | Preprocesos de **terreno** y **meteo** |
| **Dispersión** | El mapa donde dibujas los focos de emisión | Las **fuentes** |
| **Resultados** | El mapa de concentración (el resultado) | El **modelo** |

**El panel de la derecha** es el **asistente**: un chat para describir tu caso y pedir ayuda.
Tiene cuatro prompts de arranque (*¿Cómo modelo este caso?* · *Redactar el informe* · *¿Qué
criterio aplica?* · *Revisa mi configuración*), una entrada donde **Intro envía** y
**Mayús+Intro salta de línea**, y el botón **▶** de la cabecera lo pliega a un carril estrecho
para devolverle el ancho a los mapas.

> **⚠️ Estado: la interfaz existe, el motor de IA aún no.** El panel funciona y recoge lo que
> escribes, pero hasta que se le conecte un motor te avisará de que no hay ninguno. No es un
> fallo: la inteligencia vive en su propio módulo y se enchufa desde fuera. El diseño está en
> [`../informes/arquitectura_agentes_informe.md`](../informes/arquitectura_agentes_informe.md).

## 0.4 El modelo mental de los datos: `tmp/` vs `data/` <a id="04-datos"></a>

Esto conviene entenderlo pronto porque, si no, las rutas de los ficheros parecen un caos.
Hay **dos** árboles de carpetas y cada uno tiene un papel:

> **🧠 CONCEPTO · `tmp/` es tu archivo; `data/` es la mesa de trabajo**
>
> - **`tmp/`** — el **archivo permanente**. Cada vez que descargas un terreno o una meteo,
>   se guarda aquí en una **carpeta-caso** con nombre descriptivo (ver abajo). Nunca se borra
>   solo. Es tu biblioteca de datos ya descargados.
> - **`data/`** — el **caso activo**, la copia sobre la que la herramienta trabaja **ahora
>   mismo**. Contiene UN terreno, UNA meteo y UN juego de fuentes: los que has cargado en
>   esta sesión.
>
> Cada vez que pulsas getTerrain/getMeteo (o LoadTerrain/LoadMeteo), la herramienta hace dos
> cosas: guarda/lee en `tmp/` **y** copia ese caso a `data/`, marcándolo como activo.

> **⚠️ OJO · `data/` se VACÍA en cada arranque, y está bien que sea así**
>
> Al abrir la app, lo primero que hace es **borrar `data/`**. Suena agresivo, pero es
> inofensivo: todo lo que había en `data/` era **copia** de algo que sigue intacto en `tmp/`.
> Simplemente empiezas la sesión con la mesa limpia y vuelves a "cargar" el caso que quieras
> con los botones **Load***. Lo verás en la consola:
> `🧹 Caso activo (data/) vaciado: …`
>
> La consecuencia práctica: **lo que de verdad no quieres perder vive en `tmp/`**. Y hay un
> matiz importante de Windows en la [Parte 9](#91-problemas) sobre OneDrive borrando `tmp/`.

Las carpetas-caso se nombran solas, de forma que sabes qué contienen sin abrirlas:

| Tipo | Nomenclatura de la carpeta | Ejemplo real |
|---|---|---|
| Terreno | `<lat>_<lon>_<dist>km_<res>m` | `41.61806_0.34259_10km_5m` |
| Meteo | `<lat>_<lon>_<añoIni-mesIni>_<añoFin-mesFin>` | `41.618_0.343_2023-01_2023-12` |
| Simulación | `<lat>_<lon>_<añoIni-añoFin>` | `41.61806_0.34259_2023-2023` |

Y `data/active.json` anota, en todo momento, de qué carpeta de `tmp/` viene cada cosa que
hay cargada. Si alguna vez dudas de "qué estoy mirando", ábrelo.

---

# Parte 1 — El flujo de un proyecto

## 1.1 Los cinco pasos = la cadena AERMOD <a id="11-cinco-pasos"></a>

Un estudio completo, de principio a fin, son **cinco pasos en orden**. Cada uno rellena un
hueco de la ecuación de dispersión (la de `theory_guide.md §5`), y cada uno se ve en una pestaña:

```
   TÚ ELIGES            LA HERRAMIENTA CONSIGUE           RELLENA EL HUECO
┌──────────────┐
│ 1. DOMINIO   │  punto, tamaño, resolución, periodo
│ (panel izq.) │
└──────┬───────┘
       │
┌──────▼───────┐
│ 2. TERRENO   │  getTerrain → elevación (MDT05)       cota de cada receptor,
│  → AERMAP    │              + uso del suelo (CORINE)  rugosidad z₀, downwash
│              │              + edificios (Catastro)
└──────┬───────┘
       │
┌──────▼───────┐
│ 3. METEO     │  getMeteo → viento, u*, L, capa de     u, σy, σz (dispersión),
│  → AERMET    │            mezcla… (ERA5, año entero)   8760 h para percentiles
└──────┬───────┘
       │
┌──────▼───────┐
│ 4. FUENTES   │  tú dibujas los focos con el ratón     Q, geometría, hs, Ts, vs
│  → Dispersión│
└──────┬───────┘
       │
┌──────▼───────┐
│ 5. SIMULAR   │  getAermod monta los ficheros y         C = la concentración
│  → AERMOD    │  lanza aermod.exe → mapa de colores      en cada punto
└──────────────┘
```

> **💼 EN LA PRÁCTICA · El orden importa, pero puedes ir y volver**
>
> El terreno y la meteo son **independientes** entre sí: puedes bajar uno u otro primero. Las
> fuentes puedes dibujarlas cuando quieras. Pero la **simulación (paso 5) necesita los tres
> anteriores hechos**: sin terreno no sabe las cotas, sin meteo no sabe el viento y sin
> fuentes no hay nada que emitir. Si intentas simular sin uno de ellos, el motor te lo dirá
> con un error claro ("falta `data/Terrain/elevacion_uso.npz`", etc.).

## 1.2 El ejemplo que seguiremos <a id="12-ejemplo"></a>

Para que la guía no sea abstracta, imagina un encargo real muy común:

> **🧪 EJEMPLO · Una planta de compostaje cerca de un pueblo**
>
> Te piden estudiar si una **planta de compostaje** molesta por **olor** a un núcleo de
> viviendas a ~800 m. La planta tiene dos pilas grandes al aire libre y un pequeño
> biofiltro con chimenea. Quieres saber cuántas horas al año el olor supera el umbral de
> molestia en las casas.
>
> Este ejemplo toca **todo lo interesante**: una fuente de **área** (las pilas, a ras de
> suelo, emisión pasiva), una fuente **puntual** (el biofiltro), **olor** (percentiles, no
> máximos) y un **receptor sensible** concreto (el pueblo). Lo iremos montando paso a paso.

## 1.3 Qué datos entran en el modelo y por qué (mapa general) <a id="13-que-datos"></a>

Antes de pulsar ningún botón, conviene tener claro **qué se descarga y para qué**. Porque la
pregunta natural de quien empieza es: *«vale, el viento lo entiendo… pero ¿por qué demonios
necesita la nubosidad, la presión y el uso del suelo?»*

> **🧠 CONCEPTO · Ningún dato entra "directo" en la fórmula**
>
> La concentración depende de cuatro cosas: cuánto emites (`Q`), a qué velocidad se lo lleva
> el viento (`u`), y cuánto se abre el penacho al viajar (`σy`, `σz`). Los datos que se
> descargan **no son esas cuatro cosas**: son los ingredientes con los que se **fabrican**.
>
> Y casi todos pasan por dos intermediarios:
> - **`u*` (velocidad de fricción)** — cuánta turbulencia genera el **rozamiento** del viento
>   contra el suelo. Funciona de día y de noche.
> - **`L` (longitud de Monin-Obukhov)** — el número que dice si la atmósfera está **inestable**
>   (mezcla mucho, de día) o **estable** (no mezcla nada, de noche). Es *el* parámetro de la
>   dispersión.
>
> ```
>   LO QUE SE DESCARGA            SE COMBINA EN          GOBIERNA
>
>   viento (u10, v10) ─────────►  u, dirección ────────►  a dónde va y cuánto diluye
>   flujo de calor (sshf) ─────►  H  ──────┐
>   fricción (zust) ───────────►  u* ──────┼──►  L  ────►  cuánto se ABRE el penacho
>   temperatura, presión ──────►  ρ, T ────┘
>   USO DEL SUELO ─────────────►  z₀, albedo, Bowen ────►  (alimenta u* y H)
>   capa de mezcla (blh) ──────►  zi ─────────────────►  la "tapa" que encierra el humo
>   nubosidad (tcc) ───────────►  enfriamiento nocturno ►  distingue noche mala de buena
>   radiación (ssrd) ──────────►  día/noche ───────────►  albedo efectivo
>   ELEVACIÓN ─────────────────►  cota de cada receptor ►  geometría fuente-receptor
>   edificios ─────────────────►  downwash ────────────►  penacho atrapado en la estela
> ```

Dos consecuencias prácticas que vale la pena interiorizar ya:

> **⚠️ OJO · El uso del suelo NO es un dato de paisaje: es un dato meteorológico**
>
> Descargamos un mapa que dice "aquí hay un bosque, aquí un embalse". Pero AERMOD no sabe qué
> es un bosque. Lo único que entiende son **tres números**: la **rugosidad `z₀`**, el
> **albedo** y la **razón de Bowen**. El uso del suelo se traduce a esos tres números y desde
> ahí **modifica el viento y la estabilidad**. Está explicado paso a paso en [§3.4](#34-uso-del-suelo).

> **⚠️ OJO · La elevación no es para dibujar bonito el mapa**
>
> La cota de cada receptor decide su **posición vertical respecto al penacho**, y la
> concentración depende de esa distancia vertical por una exponencial. Un receptor 60 m por
> debajo de la fuente no recibe lo mismo que uno a la misma altura. En el experimento de
> [§3.5](#35-experimento), aplanar el terreno cambia el resultado en **8 de cada 10
> receptores**.

**Dónde está cada cosa en esta guía:** el catálogo completo de las once variables
meteorológicas está en [§4.2](#42-variables); el uso del suelo en [§3.4](#34-uso-del-suelo);
el perfil vertical en [§4.3](#43-perfil). Las **ecuaciones** de todo ello están en
`theory_guide.md` **§11 a §14**, que es la pareja teórica de esta parte.

---

# Parte 2 — Paso 1: definir el dominio

## 2.1 El panel de configuración, campo a campo <a id="21-panel"></a>

Todo el panel izquierdo sirve para responder a dos preguntas: **¿dónde?** y **¿cuándo?**.
Campo por campo:

> **🔢 CAMPO · Latitud / Longitud (grados)**
>
> El **centro** de tu estudio, en grados decimales (WGS84, los de Google Maps). Todo el
> dominio se construye alrededor de este punto. En el ejemplo, pondrías las coordenadas del
> centro de la planta de compostaje.
> *Valor por defecto: 41.618060, 0.342591 (un punto cerca de Lleida, usado para pruebas).*

> **🔢 CAMPO · Resolución (en focos)** — de 30 a 1000 m, por defecto **30 m**
>
> El tamaño de celda de la malla de **receptores** *junto a las fuentes*. Los receptores son
> los puntos donde AERMOD calcula la concentración: son el "dónde" del resultado.
>
> Se llama **"en focos"** porque la malla **no es uniforme**: es fina pegada a las fuentes y
> se va agrandando al alejarse (ver [§2.2](#22-malla)). Este campo fija la celda **más fina**,
> la que rodea a los focos.
>
> *¿Por qué el mínimo es 30 m y no 5?* Porque bajar de ahí no aporta: 30 m es también la
> resolución a la que se remuestrea el terreno para AERMAP. El MDT05 español tiene 5 m de
> resolución nativa, pero pedirle a AERMAP un dominio de 30 km a 5 m son ~36 millones de
> nodos y se arrastra **sin cambiar el resultado**.

> **🔢 CAMPO · Razón de crecimiento** — de 1,00 a 3,00, por defecto **1,10**
>
> Cuánto crece la celda de la malla de receptores **al alejarse de las fuentes**. Con 1,10,
> cada anillo de receptores es un 10 % más ancho que el anterior.
> - **1,00** = malla uniforme (misma celda en todo el dominio) → muchísimos receptores.
> - **1,10–1,30** = malla telescópica: detalle donde importa, ahorro donde no.
>
> Es el mando con el que controlas el **coste** de la simulación sin perder detalle cerca de
> la fuente. Explicado en [§2.2](#22-malla).

> **🔢 CAMPO · Dist. elevación/uso (km)** y **Dist. edificios (km)**
>
> Son **dos radios distintos**, y esto es a propósito:
> - **Dist. elevación/uso** (0,5–30 km): el **semiancho** del dominio de terreno. Un valor
>   de 10 km te da un cuadrado de 20×20 km centrado en el punto. Tiene que ser lo bastante
>   grande para **cubrir a todos los receptores** que te interesan (el pueblo del ejemplo).
> - **Dist. edificios** (0,5–5 km): un radio más pequeño solo para **descargar edificios**.
>   Los edificios solo importan cerca de las chimeneas (efecto downwash, §3.3), así que no
>   tiene sentido bajarlos en 20 km: sería lentísimo e inútil.

> **🔢 CAMPO · Estación meteo**
>
> Un desplegable para elegir la estación de AEMET cuyo viento real quieres comparar. Por
> defecto va en **"(AEMET más cercana automática)"**, que es lo recomendable: la herramienta
> busca sola la estación más próxima **que tenga datos** (muchas estaciones automáticas no
> publican serie diaria y darían un hueco). Se rellena al pulsar «View Map».

> **🔢 CAMPO · Años (rango)** y **Meses**
>
> El **periodo meteorológico**. El rango de años (de 1950 a 2025) y las 12 casillas de meses
> (con un botón "Todos / ninguno"). Aplica **a la vez** a AEMET y a ERA5.
> *Por defecto: 2023–2023 y los 12 meses = un año natural completo.* Y esto no es casual:

> **⚠️ OJO · Para olores y percentiles, necesitas el AÑO ENTERO (8760 horas)**
>
> Es el error de novato más caro. Un estudio de olor se juzga por un **percentil** (p. ej.
> "el P98 de las medias horarias no debe superar X"; ver `theory_guide.md §9`). Un percentil
> **exige tener todas las horas del año**: no puedes sacar el percentil 98 de un mes bonito.
> Por eso la herramienta baja años completos, y por eso por defecto están los 12 meses. Si
> destildas meses, tu resultado **no vale para un criterio de percentil**, solo para
> explorar. Déjalos todos salvo que sepas muy bien lo que haces.

> **🔢 ETIQUETA · Receptores** *(no se edita: se calcula sola)*
>
> Debajo del formulario hay una etiqueta viva que te dice, **antes de simular**, en qué te
> estás metiendo. Por ejemplo:
>
> ```
> 650 receptores (malla refinada)
> ⏱ AERMAP ≈ 1 min + AERMOD ≈ 4 min por contaminante
> malla fina 30 m en las fuentes, ×1.10 al alejarse · 8760 h de meteo
> ```
>
> Se actualiza al tocar cualquier campo. Si te pasas de **25 000 receptores** te avisa
> (`⚠️ demasiados: sube resolución o razón`), porque a partir de ahí la simulación se vuelve
> impracticable. Y si ya has definido fuentes, desglosa el total por contaminante.
>
> **Úsala.** Es la diferencia entre lanzar una simulación de 4 minutos y una de 4 horas sin
> enterarte.

> **📌 Ya no existe: la casilla «Perfil vertical ERA5»**
>
> En versiones anteriores el perfil de niveles de presión era **opcional** y estaba apagado
> por defecto. Se quitó la casilla: ahora **se descarga siempre**. Motivo: su ausencia era
> silenciosa y aporta la cizalladura real del viento en altura ([§4.3](#43-perfil)). El coste
> (unas 2 h por año, en cola del CDS) se paga **una sola vez** por punto, porque queda
> cacheado.

## 2.2 La malla de receptores: resolución y razón de crecimiento <a id="22-malla"></a>

Los **receptores** son los puntos donde AERMOD calcula la concentración. Son, literalmente,
**dónde vas a tener resultado**: donde no hay receptor, no hay dato.

> **🧠 CONCEPTO · Por qué la malla no es uniforme**
>
> Lo intuitivo sería una cuadrícula regular. El problema es el **coste**: cubrir 10 km de
> radio con celdas de 30 m son **~350 000 receptores**, y AERMOD tarda del orden de un
> segundo cada mil receptores × 8760 horas. Se va a horas.
>
> Pero es que además **no lo necesitas**: la concentración cae muy rápido al alejarse de la
> fuente. Cerca hace falta detalle fino (ahí está el gradiente y el máximo); a 5 km, un
> receptor cada 300 m sobra.
>
> La solución es una **malla telescópica**: celda fina pegada a los focos, que crece
> geométricamente al alejarse.
>
> ```
>        ·  ·   ·    ·     ·      ·        ·          ·     ← lejos: celda ancha
>      · · ·  ·   ·    ·     ·
>    ·······  ·  ·   ·
>    ·······●·  ·                    ● = fuente
>    ·······  ·  ·   ·               ······ = celda fina (30 m)
>      · · ·  ·   ·    ·
>        ·  ·   ·    ·     ·      ·        ·          ·
> ```
>
> Con **Resolución (en focos) = 30 m** y **Razón de crecimiento = 1,10**, el caso de Lleida
> se resuelve con **650 receptores** en vez de 350 000 — y el detalle donde importa es el
> mismo.

> **💼 EN LA PRÁCTICA · Cómo ajustar los dos mandos**
>
> | Si quieres… | Toca… |
> |---|---|
> | Más detalle junto a la fuente | Bajar **Resolución (en focos)** (mínimo 30 m) |
> | Menos receptores / que corra antes | Subir la **Razón de crecimiento** (1,2 · 1,3) |
> | Malla uniforme (regulatorio estricto) | Razón = **1,00** — y prepárate a esperar |
>
> Mira siempre la etiqueta **Receptores** después de tocar: te dice el resultado de tu ajuste
> antes de gastar el tiempo.

## 2.3 «View Map»: mira antes de descargar <a id="23-viewmap"></a>

> **🖱️ CÓMO SE HACE**
>
> Rellena lat/lon y las dos distancias, y pulsa **«View Map»**. En la pestaña **Mapa**
> aparece: tu punto central, los **recuadros** de los dos dominios (elevación y edificios),
> las **estaciones meteo cercanas** y —si ya has definido fuentes— **la malla de receptores y
> los focos**. De paso, rellena el desplegable de estación.

Es un paso barato (no descarga nada pesado) y sirve para dos cosas: **comprobar que no te has
equivocado de sitio** antes de lanzar una descarga de minutos, y **ver la malla** que has
configurado en §2.2 antes de simular con ella. Mira que el recuadro grande cubra a los
receptores que te importan (el pueblo). Si se queda corto, sube la "Dist. elevación/uso" y
vuelve a pulsar.

## 2.4 Criterio de proyecto: tamaño, resolución y periodo <a id="24-criterio-dominio"></a>

Aquí es donde se separa "darle a los botones" de "hacer un estudio". Tres decisiones de
criterio:

> **💼 EN LA PRÁCTICA · ¿Cómo de grande debe ser el dominio?**
>
> Regla sencilla: **el dominio debe llegar más allá del receptor más lejano que te importe**,
> con margen. Si el pueblo está a 800 m pero hay un paraje protegido a 4 km que también
> cuenta, tu semiancho tiene que superar los 4 km. Para fuentes bajas y pasivas (compostaje),
> el impacto significativo suele quedar **dentro de 1–2 km** (la concentración cae rápido).
> Para chimeneas altas, el máximo puede caer a **varios km**, así que hace falta más dominio.
> En la duda, tira por lo ancho: sobra terreno barato antes que quedarte corto.

> **💼 EN LA PRÁCTICA · ¿Cómo de fina la malla?**
>
> El detalle importa **mucho más cuanto más baja emite la fuente y más complicado es el
> relieve** (ver `theory_guide.md §3` y el experimento de [§3.5](#35-experimento)). En terreno
> llano y con chimeneas altas, puedes subir la resolución a 60–100 m y una razón de 1,2 sin
> perder nada. En un valle, con una planta que emite a 3 m, quédate en los **30 m** del mínimo
> para que el modelo "vea" las laderas por las que baja el aire frío de madrugada (el viento
> catabático que trae las quejas). El ejemplo del compostaje pide fino.
>
> Regla operativa: **empieza en 30 m / 1,10**, mira la etiqueta *Receptores*, y si el tiempo
> estimado no te vale, sube la razón antes que la resolución — pierdes detalle lejos (donde no
> importa) en vez de cerca (donde sí).

> **💼 EN LA PRÁCTICA · Un año… ¿pero cuál?**
>
> Lo canónico regulatorio es **5 años meteorológicos** para promediar la variabilidad entre
> años. La herramienta te deja pedir un rango. Para un estudio serio, más de un año; para
> aprender o explorar, **un año representativo reciente** (2023 va bien) es suficiente y
> mucho más rápido. Evita años con anomalías fuertes (una sequía histórica, un año de
> vientos atípicos) si vas a defender el estudio.

---

# Parte 3 — Paso 2: el terreno (getTerrain → AERMAP)

## 3.1 Qué hace «getTerrain» <a id="31-getterrain"></a>

> **🖱️ CÓMO SE HACE**
>
> Con el dominio definido, pulsa **«getTerrain»**. La barra de progreso y la consola te van
> contando. Al terminar, la pestaña **Mapa** añade el terreno en capas, encima de los
> recuadros de dominio, las estaciones meteo y la malla.

Por dentro, getTerrain descarga y procesa **tres** cosas, todas de servicios públicos por
"bounding box" (sin scraping, sin navegador):

| Qué | De dónde | Para qué sirve en AERMOD |
|---|---|---|
| **Elevación** | MDT05 del PNOA (CNIG), vía servicio WCS | La **cota** de cada receptor y de cada fuente |
| **Uso del suelo** | CORINE Land Cover 2018 | La **rugosidad `z₀`**, el albedo y la razón de Bowen |
| **Edificios** | Catastro (WFS), huella + altura (nº plantas × 3 m) | El **downwash** (estela de edificios) |

> **⚠️ OJO · La altura de los edificios es una ESTIMACIÓN, y se queda corta en naves industriales**
>
> El Catastro no da la altura en metros: da el **número de plantas**. La herramienta la estima
> multiplicando por **3 m/planta**, que es razonable en vivienda… y **falso en una nave
> industrial**, que figura como «1 planta» y puede medir 10-12 m.
>
> Importa porque la altura del edificio es justo lo que gobierna el *downwash*: si subestimas la
> nave, subestimas la estela y **el resultado sale por el lado optimista**, que es el peligroso.
> Si tu caso tiene una chimenea junto a naves, **comprueba y corrige a mano las alturas** en
> `edificios.gpkg` antes de simular.

> **📁 FICHEROS · Qué deja getTerrain en disco**
>
> En `tmp/Terrain/<lat>_<lon>_<dist>km_<res>m/`:
> - `elevacion_uso.npz` — la matriz de elevación `Z` + el uso del suelo `USE` + la extensión
>   `ext` (en coordenadas UTM). **Es el fichero clave** que leerá la simulación.
> - `edificios.gpkg` — los edificios (huella + altura), si los hubo.
> - `mesh/nodes.txt` y `mesh/use.txt` — la red de nodos en texto plano (índice, x, y, z / uso).
> - `info.json` — un resumen legible (elevación mín/máx, nº de edificios, etc.).
>
> Y una copia de todo ello en `data/Terrain/` (el caso activo).

## 3.2 Las capas de terreno en la pestaña Mapa <a id="32-capas-mapa"></a>

Tras getTerrain (o LoadTerrain), la pestaña **Mapa** —la misma de View Map, con los recuadros
de dominio de terreno y de edificios, las estaciones meteo y la malla de receptores— suma
**capas conmutables** (arriba a la derecha, el control de capas):

- **Elevación** — el relieve en colores, con su barra de color (leyenda abajo).
- **Uso del suelo** — las clases de CORINE presentes, cada una con su color y nombre.
- **Edificios** — las huellas, coloreadas por uso (azul=residencial, morado=industrial,
  naranja=comercial, marrón=servicio público).

Las capas son **excluyentes** (al encender una se apaga la anterior) y la leyenda de abajo
**cambia sola** según la capa encendida. Ve alternando para inspeccionar: ¿hay un valle marcado? ¿el uso del suelo alrededor de la fuente es
"tejido urbano" (rugoso) o "cultivo" (liso)? Esas dos cosas van a gobernar la dispersión.

## 3.3 Qué es AERMAP en la cadena <a id="33-que-es-aermap"></a>

> **🔗 EN LA HERRAMIENTA · AERMAP = el preprocesador de terreno de la EPA**
>
> En la cadena oficial, **AERMAP** es el programa que coge el modelo digital de elevaciones y
> calcula, para **cada receptor**, dos números: su **cota** y una **escala de altura de
> colina** (cuánto de "montañoso" es su entorno, que AERMOD usa para decidir si el penacho
> rodea o remonta el relieve). La herramienta genera el GeoTIFF del terreno y lanza
> `aermap.exe` por ti al pulsar «Run».

> **🧠 CONCEPTO · Por qué la elevación cambia el resultado**
>
> La cota de un receptor decide su **posición vertical respecto al penacho**, y ahí la
> concentración depende de una **exponencial** (`theory_guide.md §5.2`). Un receptor 60 m por
> debajo de la fuente y otro a la misma altura reciben cantidades muy distintas del mismo
> penacho. No es un refinamiento estético: en [§3.5](#35-experimento) verás que aplanar el
> terreno estropea el resultado en **8 de cada 10 receptores**.

> **🧠 CONCEPTO · Downwash: por qué importan los edificios**
>
> Si una chimenea está pegada a un edificio, el viento al chocar con el edificio crea una
> **estela de remolinos** por detrás, y el penacho puede quedar **atrapado y arrastrado al
> suelo** mucho antes de lo que le tocaría. Eso se llama *building downwash* y puede disparar
> la concentración cerca. Se calcula con otro programa de la EPA, **BPIPPRM**, que a partir de
> las huellas de los edificios y la posición de las chimeneas produce unos coeficientes que se
> le pasan a AERMOD. La herramienta lo hace sola al simular, **pero solo si hay edificios y
> hay fuentes puntuales** (a una fuente de área a ras de suelo no le aplica el downwash).

## 3.4 El uso del suelo: cómo un bosque se convierte en tres números <a id="34-uso-del-suelo"></a>

Esta es **la** pregunta que más se repite: *«entiendo que baje la altura del terreno… pero
¿para qué quiere el modelo saber si hay un bosque o un campo de trigo?»*

> **🧠 CONCEPTO · AERMOD no sabe qué es un bosque**
>
> Lo único que entiende son **tres números** por celda del mapa:
>
> | Número | Qué significa | Cómo afecta |
> |---|---|---|
> | **Rugosidad `z₀`** (m) | Cuánto frena el suelo al viento | Cambia el **perfil de viento** y la turbulencia mecánica |
> | **Albedo** (0–1) | Qué fracción de la luz solar refleja | Menos albedo → más calor absorbido → **más mezcla** |
> | **Razón de Bowen** | Si el suelo calienta el aire o evapora agua | Más Bowen → **más convección** |
>
> Y la cadena completa es:
>
> ```
> uso del suelo → (z₀, albedo, Bowen) → viento y estabilidad → cuánto se abre el penacho
> ```
>
> Por eso el uso del suelo **no es un dato de paisaje: es un dato meteorológico disfrazado.**

### Cómo se hace la traducción, paso a paso

> **🧪 EJEMPLO · De "un bosque de coníferas" a tres números**
>
> ```
> 1. CORINE dice:         clase 312 «Bosque de coníferas»
> 2. Se traduce a NLCD:    312 → 42 «Evergreen Forest»
> 3. Se mira el mes:       julio → estación 4 (pleno verano)
> 4. Se leen las tablas:   z₀ = 1,30 m · albedo = 0,12 · Bowen = 0,3
> ```
>
> Y ahora compara ese bosque con lo que podría haber al lado, el mismo día:
>
> | Uso del suelo | `z₀` (m) | Albedo | Bowen |
> |---|---|---|---|
> | Lámina de agua | **0,001** | 0,10 | 0,1 |
> | Regadío en verano | 0,20 | 0,20 | 0,5 |
> | Bosque de coníferas | **1,30** | 0,12 | 0,3 |
> | Urbano denso | 0,70 | 0,18 | 1,5 |
>
> La rugosidad va de 0,001 a 1,3 m: **un factor 1300**. Ese es el rango que el uso del suelo
> puede mover.

> **📐 ¿Cuánto es eso en viento?** Con la misma fuerza del viento, a 10 m de altura:
> **6,7 m/s** sobre agua, **4,3 m/s** sobre regadío, **1,5 m/s** sobre bosque. Y como el
> viento **divide** en la fórmula de la concentración, ahí tienes un factor 4. (La ecuación,
> en `theory_guide.md §12.1`.)

> **⚠️ OJO · El eslabón débil: CORINE no es NLCD**
>
> El programa oficial de la EPA que hace esta traducción (**AERSURFACE**) solo entiende
> **NLCD**, el mapa de usos de Estados Unidos. En Europa tenemos **CORINE**. La herramienta
> traduce CORINE → NLCD y aplica las tablas oficiales, pero **esa traducción es un juicio
> técnico, no un dato medido**.
>
> Es el punto más discutible de toda la cadena, y por eso **conviene declararlo en el
> protocolo del estudio** en lugar de dejarlo enterrado en el código.

> **💼 EN LA PRÁCTICA · El caso de los frutales, un ejemplo de decisión declarada**
>
> NLCD no tiene clase para **viñedos, frutales ni olivares**, así que la traducción los manda
> a «Cultivated Crops», con la rugosidad de un herbáceo (0,20 m). Pero un frutal maduro mide
> 4-5 m y frena el doble. Y **en el dominio de Lleida los frutales son ~36 % de la superficie**:
> no es un matiz.
>
> La herramienta corrige **solo la rugosidad** (el albedo y el Bowen se quedan, que ahí el
> cultivo sí vale) con la clasificación de **Davenport-Wieringa**, adoptada por la OMM:
> viñedos 0,25 m, frutales y olivares 0,50 m.
>
> Lo cuento aquí porque es justo el tipo de decisión que, escondida, convierte un estudio en
> una caja negra — y declarada, es una hipótesis que un revisor puede discutir.

> **🧠 CONCEPTO · Cambia con la estación y con la dirección del viento**
>
> Dos refinamientos que la herramienta aplica sola, y que conviene saber que existen:
>
> - **Por estación del año:** un cultivo tiene `z₀` = 0,03 m en invierno y **0,20 m en verano**
>   (×7). Con nieve, el albedo se triplica y la convección se apaga.
> - **Por sectores de viento:** el `z₀` se calcula **por separado en 12 sectores de 30°**, y
>   cada hora se usa el del sector **del que viene el viento**. Si tienes bosque al norte y
>   embalse al sur, el aire llega con historias de rozamiento distintas.
>
> (El promediado espacial tiene sus reglas —media geométrica para `z₀` y Bowen, aritmética
> para el albedo— y el porqué está en `theory_guide.md §12.5`.)

## 3.5 ¿Cuánto importa el terreno? El experimento de Lleida <a id="35-experimento"></a>

Todo lo anterior dice por qué **debería** importar. Pero conviene medirlo, porque la respuesta
sorprende. Se simuló **el mismo caso cuatro veces**, quitando datos:

| Caso | Relieve | Uso del suelo | Máx (µg/m³) | Error mediano | Error máximo | Receptores con error > 20 % |
|---|---|---|---|---|---|---|
| **Real** | Real | Real | 18,0 | — | — | — |
| Sin uso del suelo | Real | Constante | 16,5 | **0,5 %** | 11 % | **0 %** |
| Sin relieve | Plano | Real | 23,1 | **30 %** | **1275 %** | **80 %** |
| Sin nada | Plano | Constante | 21,2 | **30 %** | 1253 % | **76 %** |

![Desviaciones respecto al caso real](images/desviaciones.png)

> **🧠 CONCEPTO · En Lleida el relieve manda; el uso del suelo casi no**
>
> Quitar el uso del suelo cambia el resultado un **0,5 %** (imperceptible, y nunca más de un
> 11 %). Quitar el relieve lo cambia un **30 % de mediana**, con casos de hasta **×13**, y
> afecta a **8 de cada 10 receptores**.
>
> Y ojo a una trampa: **si solo miras el máximo, te engañas**. El caso sin relieve da 23,1
> frente a 18,0, que "solo" parece un 28 % de error. Pero el máximo cae en el mismo sitio en
> los cuatro casos (pegado a la fuente). Lo que se destruye es **el patrón espacial**: a quién
> le llega el penacho y con cuánto. Por eso se compara **receptor a receptor**.
>
> En los mapas se ve a simple vista: con relieve real el penacho **se deforma y se fragmenta**
> (hay zonas que el terreno protege); sin relieve es una **elipse lisa y simétrica**. La elipse
> limpia es más bonita y es falsa.

> **💼 EN LA PRÁCTICA · Tres conclusiones que te puedes llevar**
>
> 1. **El relieve no es opcional.** Descargarlo es la diferencia entre acertar y equivocarse un
>    30 % de forma sistemática.
> 2. **Modelar en plano "sobrestima"**, sí — todas las desviaciones son positivas. Pero con
>    errores punto a punto de hasta ×13. Un conservadurismo que no controlas no te sirve para
>    defender un informe.
> 3. **El error no se concentra lejos.** La desviación mediana es ~30 % **a todas las
>    distancias**, desde 76 m hasta 4,9 km. Lo que crece con la distancia son los casos
>    extremos, no el error típico.

> **⚠️ OJO · La lección más útil de este experimento no fue sobre el terreno, sino sobre `Q`**
>
> Al preparar las simulaciones se descubrió que el caso guardado tenía un caudal de
> **234 g/(s·m²)**, que sobre 4993 m² son **3,7 millones de kg/h**. Siete órdenes de magnitud
> por encima de lo físicamente posible: casi seguro, un número tecleado en otra unidad.
>
> Como la dispersión es lineal, las desviaciones **en %** seguían siendo válidas. Pero si eso
> hubiera ido a un informe con valores absolutos, el resultado habría sido una barbaridad.
>
> **Acostúmbrate a hacer la comprobación de orden de magnitud:** multiplica tu caudal por la
> superficie, pásalo a kg/h y pregúntate *«¿tiene sentido que esta planta emita esto?»*. El
> caudal es, con diferencia, la mayor fuente de error de un estudio de dispersión — mucho más
> que el terreno o el uso del suelo.

> **⚠️ OJO · No generalices este resultado a tu caso**
>
> Sería facilísimo concluir "el uso del suelo da igual, me lo salto". **Error.** Sale pequeño
> en Lleida por dos razones muy locales:
>
> 1. **El uso dominante de Lleida es regadío**, cuya rugosidad de invierno (0,03 m) resulta ser
>    **casi exactamente** el valor constante con el que se comparó. La "simplificación"
>    coincidía con la realidad, así que no cambió nada.
> 2. **El dominio es agrícola y homogéneo:** no hay el contraste bosque/agua/ciudad que dispara
>    las diferencias.
>
> En cambio el relieve **sí varía**: **158 m de desnivel** (de 111 a 269 m). Aplanar el terreno
> a la media mueve receptores que estaban decenas de metros **por debajo** de la fuente a estar
> **por encima** de ella — y la concentración depende de esa geometría exponencialmente.
>
> **La regla que sí es transferible:** *manda el dato que más varía dentro de TU dominio*.
> Un emplazamiento llano con bosque a un lado y un embalse al otro daría el resultado
> **contrario**. Mira tu mapa en la pestaña Mapa antes de decidir qué puedes simplificar
> (spoiler: no simplifiques nada, que descargarlo es gratis).
>
> Este terreno tiene **158 m de desnivel en 10 km**: relieve *moderado*. En un valle encajado
> el efecto sería mayor; en una llanura, menor. **Repetir este análisis en un emplazamiento
> nuevo cuesta unos 10 minutos** — son cuatro ejecuciones del mismo caso.

> **📖 El análisis completo** —los cuatro mapas, la tabla de 50 receptores muestreados y cómo
> reproducirlo— está en **`analisis_sensibilidad_terreno.md`**. Los cuatro casos quedan
> guardados en `tmp/Results/` y se abren con **«Load»**.

### 3.5.1 La contraprueba: ¿y si el paisaje SÍ tuviera contraste? <a id="351-contraprueba"></a>

Quedarse en "en Lleida el uso del suelo importa poco" sería peligroso: mucha gente aplicaría el
titular a su caso. Así que se repitió el experimento **cambiando el paisaje**: mismo relieve,
misma meteo, mismas fuentes, y **la misma geometría real de las parcelas** — lo único que cambia
es **qué clase de suelo recibe cada parcela**.

![Los cuatro patrones de uso del suelo](images/usos_patrones.png)

| | Escenario | Contraste |
|---|---|---|
| 🟢 **BAJO** | regadío ↔ frutales *(el mosaico real de Lleida)* | `z₀` ×5 |
| 🟡 **MEDIO** | zonas verdes urbanas ↔ casco denso | `z₀` ×27 |
| 🟠 **ALTO** | marisma ↔ esclerófila | Bowen ×6 |
| 🔴 **MÁXIMO** | agua ↔ bosque de coníferas | `z₀` **×1300** |

Cada uno se simula **dos veces**: con el patrón (*heterogéneo*) y con todo el dominio de una
sola clase (*uniforme*). La diferencia mide **cuánto aporta conocer el uso del suelo**.

### El resultado: ni con el contraste máximo llega al 2 %

![Desviaciones al uniformizar el uso del suelo](images/usos_desviaciones.png)

| Escenario | Error mediano | Error máximo | Caída del **máximo** al uniformizar |
|---|---|---|---|
| 🟢 BAJO | 0,5 % | 11 % | −9 % |
| 🟡 MEDIO | 0,8 % | 17 % | −13 % |
| 🟠 ALTO | **0,2 %** | 4 % | −3 % |
| 🔴 MÁXIMO | **1,1 %** | 22 % | −15 % |

> **⚠️ RECTIFICACIÓN · La predicción de esta guía era demasiado optimista**
>
> La versión anterior de esta sección decía que con paisajes contrastados el efecto «debería
> dispararse». **No pasó.** Pasar del mosaico agrícola real al contraste más extremo que permite
> CORINE (agua contra bosque) solo multiplica el error mediano **×2, de 0,5 % a 1,1 %**.
>
> Comparación: quitar el **relieve** movía el receptor mediano un **30 %**. El relieve pesa
> **~27 veces más** que el uso del suelo, incluso comparándolo con el paisaje más contrastado
> que se puede construir.

> **🔑 CONCEPTO · Por qué: un mosaico fragmentado se promedia solo**
>
> Ésta es la idea que hay que llevarse, y explica todo lo demás.
>
> Recuerda que la rugosidad se promedia **por sectores de 30°, en un radio de 1 km** ([§3.4](#34-uso-del-suelo)).
> Si las parcelas están **entremezcladas**, cualquier sector contiene **de todo**, y la media
> se lo come. En el escenario MÁXIMO, un contraste de clases de **×1300 se queda en ×53** de
> contraste real entre sectores. Un trozo mitad agua mitad bosque no da un valor intermedio:
> da `√(0,001 × 1,3) = 0,036 m`, **casi el del agua**.
>
> **Lo que importa no es cuánto difieren las clases, sino si esa diferencia está ORGANIZADA
> a la escala del sector de viento.** Mira la figura de los patrones: los cuatro paisajes están
> igual de troceados, y por eso ninguno mueve mucho el resultado. Un embalse entero a un lado y
> un bosque entero al otro sí lo movería.

> **🧠 CONCEPTO · El Bowen (🟠) resulta ser el que MENOS pesa**
>
> Contra lo que esta guía anticipaba, el escenario de contraste de humedad da el efecto **más
> pequeño de los cuatro** (0,2 %). Por dos motivos: el Bowen es **un solo número para todo el
> dominio** (no se calcula por sectores, así que no puede crear un patrón espacial), y actúa
> **indirectamente** sobre la estabilidad, mientras que la rugosidad entra directamente en el
> perfil de viento.
>
> **Orden real:** rugosidad > Bowen > albedo. Los tres muy por detrás del relieve.

> **⚠️ OJO · Donde SÍ importa el uso del suelo: en el pico, no en la mediana**
>
> Fíjate en la última columna de la tabla: aunque la mediana apenas se mueve, **el máximo de
> concentración cae entre un 9 % y un 15 %** al ignorar el uso del suelo, de forma consistente
> en los cuatro escenarios.
>
> **Y el pico es lo que se compara con el límite legal.** Ignorar el uso del suelo mete un
> **sesgo sistemático a la baja del 10-15 % justo en el valor que decide si tu instalación
> cumple**. Por eso la herramienta descarga CORINE siempre: cuesta poco y te evita ese sesgo.

### La altura del foco: lo más importante de todo el experimento

Los cuatro escenarios se repitieron con el foco a **1 m, 3 m y 6 m**.

![Sensibilidad según la altura del foco](images/usos_altura.png)

> **⚠️ RECTIFICACIÓN · "Un foco más bajo nota más el uso del suelo" es FALSO**
>
> Es la intuición natural (un foco a ras de suelo está metido en la capa donde manda la
> rugosidad) y esta guía la daba por buena. **Los datos dicen lo contrario:** la sensibilidad
> al uso del suelo **crece con la altura**, multiplicándose por ~2,6 entre 1 m y 6 m, en los
> cuatro escenarios sin excepción.

> **🔑 Pero lo que de verdad tienes que llevarte es esto**
>
> Mira cómo cambia el **valor absoluto** al mover la altura del foco (escenario BAJO):
>
> ```
> foco a 1 m  →  máximo 68,7 µg/m³
> foco a 3 m  →  máximo 18,0 µg/m³
> foco a 6 m  →  máximo  5,7 µg/m³
> ```
>
> **Un factor ×12 en cinco metros.** Frente al ~1 % que mueve el uso del suelo.
>
> **Acertar la altura de emisión importa muchísimo más que cualquier refinamiento del terreno.**
> Si vas a medir algo en campo, mide bien **a qué altura emite realmente tu fuente**. Es el
> campo `Altura emisión` del formulario de Dispersión ([§5.3](#53-parametros)), y es de los
> pocos números que puedes acertar con una cinta métrica.

> **💼 EN LA PRÁCTICA · Prioridad de esfuerzo, ya medida**
>
> ```
> caudal Q  ≫  altura del foco  ≫  relieve  ≫  uso del suelo
> ```
>
> Los dos primeros **los aportas tú**; los otros dos se descargan solos con un botón. Es justo
> al revés de donde la gente suele poner el esfuerzo.

> **💼 EN LA PRÁCTICA · Cuándo preocuparte por el uso del suelo**
>
> Abre la capa **Uso del suelo** en la pestaña Mapa y mira **la escala de las manchas**, no
> las clases:
>
> | Lo que ves | Riesgo de simplificar |
> |---|---|
> | Tu foco en la orilla de un **embalse, mar o llanura lisa**, con bosque o ciudad enfrente | 🔴 alto |
> | Un **frente urbano-rural** neto, que ocupa varias direcciones enteras | 🟡 medio |
> | Contraste **seco/regadío** sin cambio de rugosidad | 🟢 bajo |
> | Un **mosaico troceado** de cualquier tipo, aunque las clases sean extremas | 🟢 despreciable |
>
> Y un límite duro: el promediado usa un radio de **1 km**. Un contraste que solo exista a
> escala menor **no le llega al modelo**, hagas lo que hagas.

> **⚠️ OJO · Nada de esto se ha probado con chimeneas**
>
> Todo el experimento es con **fuentes de área** a 1, 3 y 6 m — o sea, compostaje, EDAR, balsas.
> **No se ha ensayado ninguna chimenea alta.** La tendencia medida crece con la altura, pero 6 m
> sigue siendo una fuente baja y extrapolar sería precisamente el error que este experimento ya
> cometió una vez. Si tu caso son chimeneas, habría que medirlo.

> **📖 El análisis completo** —con las tablas de 50 receptores a las tres alturas y cómo
> reproducirlo— está en **`analisis_sensibilidad_usos.md`**.

## 3.6 «LoadTerrain» <a id="36-loadterrain"></a>

> **🖱️ CÓMO SE HACE**
>
> **«LoadTerrain»** abre un selector de carpeta: eliges una carpeta-caso de `tmp/Terrain/` ya
> descargada y la carga **sin volver a bajar nada de internet**. Úsalo al empezar cada sesión
> (recuerda: `data/` se vació al arrancar) para recuperar un terreno que ya tenías.

La diferencia getTerrain/LoadTerrain es la misma en todos los pares de botones: **get\* =
descargar de internet y guardar**; **Load\* = leer del disco**. Si ya lo bajaste una vez,
Load es instantáneo.

---

# Parte 4 — Paso 3: la meteorología (getMeteo → AERMET)

## 4.1 Qué hace «getMeteo» <a id="41-getmeteo"></a>

> **🖱️ CÓMO SE HACE**
>
> Con el punto y el periodo puestos, pulsa **«getMeteo»**. Es el paso **más lento** (descarga
> un año de datos horarios del CDS, que a veces te mete en cola). La consola te informa de
> cada fuente. Al terminar, la pestaña **Mapa** añade las rosas de viento y las variables
> como paneles fijos (arriba a la izquierda) que se eligen en el control de capas.

getMeteo baja **tres fuentes de viento** sobre el mismo periodo, para poder compararlas:

| Fuente | Qué es | Resolución | Papel |
|---|---|---|---|
| 🟦 **AEMET** | Estación real, dato diario | puntual (la estación) | La "verdad sobre el terreno", para contrastar |
| 🟥 **ERA5** | Reanálisis del ECMWF, **paquete horario completo** | ~31 km | **La que alimenta AERMOD** |
| 🟩 **ERA5-Land** | Reanálisis de tierra, solo viento | ~9 km | Comparación a más detalle |

> **🧠 CONCEPTO · Por qué ERA5 y no la estación de AEMET**
>
> La estación de AEMET da viento real, pero **solo viento, y solo diario**. AERMOD necesita
> **muchas más variables, y horarias**: la velocidad de fricción `u*`, la altura de la capa
> de mezcla, el flujo de calor del suelo, la nubosidad… (los ingredientes de `σy` y `σz`; ver
> `theory_guide.md §4`). Eso solo lo da un **reanálisis** como ERA5, que es un modelo global
> que reconstruye el estado completo de la atmósfera hora a hora. AEMET se usa para **validar**
> que la rosa de viento de ERA5 se parece a la realidad, no como dato de entrada del modelo.

> **📁 FICHEROS · Qué deja getMeteo en disco**
>
> En `tmp/Meteo/<lat>_<lon>_<periodo>/`, tres subcarpetas con **un CSV por mes**:
> - `era5/era5m_levels_full_<AAAAMM>_<lat>_<lon>.csv` — el paquete completo horario
>   (u10, v10, t2m, d2m, tcc, ssrd, sshf, blh, zust, sp, tp + wspd/wdir derivados). **Este es
>   el que usa la simulación.**
> - `eraland/era5m_land_wind_<AAAAMM>_<lat>_<lon>.csv` — solo viento, a 9 km.
> - `aemet/aemet_<idema>_<año>.csv` — viento diario de la estación.
> - `era5prof/era5m_plev_prof_<AAAAMM>_<lat>_<lon>.csv` — el perfil vertical (§4.3).
> - `info.json` con los recuentos.

## 4.2 Las once variables que se descargan, y para qué sirve cada una <a id="42-variables"></a>

Aquí está la respuesta a *«¿por qué necesita la nubosidad y la presión?»*. ERA5 trae **once
variables horarias**, y ninguna está de adorno.

> **🧠 CONCEPTO · Recuerda: casi ninguna entra "directa"**
>
> Todas se combinan en dos números que son los que de verdad gobiernan la dispersión:
> **`u*`** (turbulencia por rozamiento) y **`L`** (estabilidad). Las ecuaciones están en
> `theory_guide.md §11`; aquí va la versión de andar por casa.

| Variable | Qué es | Para qué la usa el modelo |
|---|---|---|
| **`u10`, `v10`** | Componentes del viento a 10 m | La **velocidad** (que divide en la fórmula: es *el* dato) y la **dirección** (a quién le llega) |
| **`sshf`** | Flujo de calor del suelo al aire | Decide si es **día convectivo** (mezcla) o **noche estable** (no mezcla) |
| **`zust`** | Velocidad de fricción `u*` | La turbulencia que genera el **rozamiento**, funcione o no el sol |
| **`blh`** | Altura de la capa de mezcla | La **"tapa"** que encierra el humo. De día 1500 m, de noche puede bajar de 100 |
| **`t2m`** | Temperatura a 2 m | Densidad del aire, y el **contraste térmico** que hace subir un penacho caliente |
| **`sp`** | Presión en superficie | Densidad del aire **y** la escalera de alturas del perfil vertical (§4.3) |
| **`tcc`** | Nubosidad total | Distingue una **noche despejada** (muy estable, la mala) de una **cubierta** (inofensiva) |
| **`ssrd`** | Radiación solar entrante | Marca **día/noche** (y con ello el albedo efectivo) |
| **`d2m`** | Punto de rocío | Da la **humedad relativa**; dato de contexto |
| **`tp`** | Precipitación | Se descarga, pero **hoy no se usa** (ver abajo) |

> **🧠 CONCEPTO · Las tres que de verdad mandan**
>
> Si tuvieras que vigilar solo tres, serían estas:
>
> 1. **El viento (`u10`,`v10`)** — porque **divide**: la mitad de viento es el doble de
>    concentración. Y su dirección decide a quién le llega el penacho.
> 2. **El flujo de calor (`sshf`)** — porque separa el día de la noche en términos de mezcla.
>    Una atmósfera convectiva diluye; una estable, no.
> 3. **La capa de mezcla (`blh`)** — porque es el **volumen** en el que se reparte todo. El
>    mismo caudal en 1500 m de espesor o en 100 m difiere en **más de un orden de magnitud**.
>
> Estas tres, juntas, explican por qué **las quejas de olor llegan de madrugada**: noche →
> `sshf` negativo (sin mezcla) + `blh` mínima (poco volumen) + viento flojo (poca dilución).
> Los tres factores empujan en la misma dirección a la vez.

> **⚠️ OJO · La nubosidad no es un dato decorativo**
>
> Es la que distingue **una noche mala de una noche inofensiva**. Una noche despejada irradia
> calor al espacio, el suelo se enfría mucho, se forma una inversión térmica y el contaminante
> queda atrapado abajo. Una noche cubierta tiene las nubes de manta: el suelo apenas se enfría
> y la atmósfera se queda casi neutra. Para un estudio de olor, esa diferencia **es el estudio**.

> **⚠️ RECTIFICACIÓN · La precipitación se descarga pero NO se usa**
>
> Conviene decirlo claro para que nadie suponga lo contrario: `tp` se baja y se guarda, pero en
> el fichero que recibe AERMOD **se escribe "sin precipitación"**.
>
> No es un olvido: la herramienta modela **gas pasivo conservativo** (`theory_guide.md §8`),
> sin deposición húmeda. La lluvia **lava** el penacho y reduce la concentración aguas abajo,
> así que ignorarla es **conservador** — sale más concentración de la que realmente habría, que
> es el lado correcto por el que equivocarse en un estudio de impacto.
>
> El dato está descargado para el día que se modele deposición húmeda.

## 4.3 El perfil vertical: los datos en altura <a id="43-perfil"></a>

Todo lo anterior es meteorología **de superficie**: viento a 10 m, temperatura a 2 m. Además,
la herramienta descarga **cómo cambian el viento y la temperatura con la altura**.

> **🧠 CONCEPTO · Qué aporta: el viento gira con la altura**
>
> Datos reales de una noche en Lleida (1 de enero de 2023, 00:00):
>
> | Altura | Dirección | Velocidad |
> |---|---|---|
> | 10 m | 82° (E) | 1,6 m/s |
> | 233 m | 134° (SE) | 2,7 m/s |
> | 908 m | 223° (SO) | 4,2 m/s |
>
> El viento **gira 141° y casi triplica su velocidad** en 900 m. Eso es real y **no se puede
> deducir** del dato del suelo. Si el penacho sube, se encuentra ese giro — y acaba en una
> dirección distinta de la que dice la veleta.

> **⚠️ OJO · La rareza: hay niveles que caen bajo tierra**
>
> ERA5 no da los datos "a 100 m, a 200 m": los da **por niveles de presión** (1000 hPa,
> 975 hPa…). Y la altura de un nivel depende de la presión que haya en el suelo, **que cambia
> cada hora**.
>
> En Lleida (198 m de altitud) el nivel de 1000 hPa correspondería a un punto **98 m bajo
> tierra**: no existe. Y el de 975 hPa oscila entre **−132 m** (bajo tierra, en borrasca) y
> **+290 m** (en anticiclón). La herramienta **recalcula la altura hora a hora** y descarta lo
> que caiga bajo el suelo.
>
> No tienes que hacer nada: es automático. Pero explica por qué en la consola verás que unas
> horas usan 5 niveles y otras 4.

> **⚠️ El límite honesto:** el primer nivel utilizable está a ~113 m, pero **el 35 % de las
> noches** toda la capa estable está **por debajo** de esa altura. En esas horas el modelo
> promedia a través de la inversión en vez de medirla por dentro. El perfil **mejora** el
> modelo, pero **no resuelve la capa nocturna**, y eso no se arregla con ERA5: haría falta un
> radiosondeo local. Está todo desarrollado en **`notas_perfil_vertical.md`**.

> **⏱ Coste:** el CDS no deja pedir un mes entero de perfil de golpe, así que va **por
> quincenas**: 24 peticiones por año, ~10 min cada una → **unas 2 horas por año**. Se paga
> **una sola vez** por punto (queda cacheado). Es la razón de que getMeteo tarde tanto la
> primera vez.

## 4.4 Las gráficas de meteo en la pestaña Mapa <a id="44-meteo-mapa"></a>

Tras getMeteo (o LoadMeteo) la pestaña **Mapa** suma una capa por gráfica en el control de
capas. Cada gráfica se ve como un **panel fijo** arriba a la izquierda: no se mueve ni cambia
de tamaño al desplazar o hacer zoom (igual que las leyendas). Las capas son **excluyentes**:
al encender una gráfica se apaga la capa anterior (otra gráfica, la elevación, el uso del
suelo o los edificios). Una etiqueta arriba al centro indica si la meteo es **histórica**
(ERA5, regulatoria) o **predictiva** (GFS, pronóstico).

- **Rosas de viento** 🌹 — una por cada fuente (AEMET, ERA5, ERA5-Land). Cada rosa muestra de qué direcciones sopla el viento y con qué fuerza. **Míralas
  antes de calcular nada:** te dicen hacia dónde se irá el penacho, y por tanto quién va a
  recibirlo. Si el 40 % del viento viene del noroeste, el receptor del sureste se come el
  penacho el 40 % del tiempo (`theory_guide.md §3`).
- **Paneles de variables** — para cada variable meteo (temperatura, capa de mezcla, flujo de
  calor…), un panel 2×2 con cuatro vistas: ciclo diario medio, mapa mes×hora, percentiles y
  anomalía. Sirven para entender el clima del sitio.

> **💼 EN LA PRÁCTICA · Compara las tres rosas**
>
> Que las tres fuentes coincidan en la dirección dominante te da **confianza** en los datos.
> Si AEMET y ERA5 discrepan mucho, sospecha: puede ser que la estación esté en un microclima
> (un valle encajado) que la malla de 31 km de ERA5 no capta. En terreno complejo, ERA5-Land
> (9 km) suele parecerse más a la estación. Esa discrepancia es información, no ruido.

## 4.5 Qué es AERMET y por qué aquí no se usa <a id="45-que-es-aermet"></a>

> **🔗 EN LA HERRAMIENTA · AERMET = el preprocesador meteorológico… que aquí sustituimos**
>
> En la cadena oficial de la EPA, **AERMET** es el programa que coge meteorología cruda
> (sondeos, estaciones) y **estima** los parámetros de la capa límite (`u*`, `L`, altura de
> mezcla) para dárselos a AERMOD. Produce dos ficheros: `.sfc` (superficie) y `.pfl` (perfil).
>
> **Esta herramienta se salta AERMET.** ¿Por qué? Porque **ERA5 ya trae calculado lo que
> AERMET existe para estimar**: la velocidad de fricción (`zust`), la altura de la capa de
> mezcla (`blh`), el flujo de calor (`sshf`). Así que la herramienta escribe directamente los
> ficheros `.sfc` y `.pfl` a partir de ERA5, sin ejecutar AERMET. Está **validado de extremo
> a extremo** (un año de Lleida: AERMOD termina sin errores ni avisos). El nombre de la
> pestaña "AERMET" se conserva porque es la **etapa** que estos datos ocupan en la cadena,
> aunque el programa `aermet.exe` no llegue a correr.

> **⚠️ OJO · Las calmas: cuando el modelo no puede calcular**
>
> Recuerda de la teoría (`theory_guide.md §5`) que el modelo gaussiano **revienta si el viento
> es casi nulo** (`u` está dividiendo → C → ∞). Esas horas de calma se marcan y se excluyen
> del cálculo. El problema es que las **peores situaciones de olor son noches de calma**…, que
> es justo cuando el modelo se declara incompetente. Es una limitación de fondo de AERMOD, no
> de la herramienta: tenlo presente al interpretar, porque tu resultado **infravalora** las
> noches más quietas.
>
> **Esta es una de las razones por las que existe un segundo motor** ([§4.7](#47-dos-motores)):
> CALPUFF sí puede representar una calma, porque su bocanada simplemente deja de avanzar.

## 4.6 «LoadMeteo», caché y reutilización <a id="46-loadmeteo"></a>

> **🖱️ CÓMO SE HACE**
>
> **«LoadMeteo»** abre un selector de carpeta y carga una meteo ya descargada de `tmp/Meteo/`,
> sin tocar internet. Es lo que usarás casi siempre tras la primera descarga.

> **🧠 CONCEPTO · La descarga es cara; cachea y reutiliza**
>
> El CDS de Copernicus **limita el tamaño y el número de peticiones**, y a veces te mete en
> cola varios minutos. Por eso la herramienta **guarda cada mes por separado** y, si vuelves a
> pedir un mes que ya tienes en cualquier carpeta de la caché, **lo copia (♻️) en vez de
> volver a descargarlo**. Traducción: **baja los datos una vez** y a partir de ahí trabaja con
> Load. Si cambias de punto (aunque sea 200 m), cambia el nombre del caché y toca descargar de
> nuevo: el nombre del fichero lleva las coordenadas.

## 4.7 Dos motores: AERMOD y CALPUFF <a id="47-dos-motores"></a>

La herramienta está incorporando **CALPUFF** como segundo motor de dispersión, junto a AERMOD.
No es un repuesto: resuelven problemas distintos.

> **🧠 CONCEPTO · Penacho continuo frente a bocanadas**
>
> - **AERMOD** modela un **penacho estacionario**: supone que, mientras el humo viaja, el
>   viento es el mismo. Es rápido, es el estándar regulatorio y funciona muy bien cuando esa
>   suposición se sostiene.
> - **CALPUFF** suelta **bocanadas** (*puffs*): cada una viaja con el viento que se encuentra
>   en su momento y su sitio. Al no suponer viento constante, representa situaciones que
>   AERMOD no puede.

> **💼 EN LA PRÁCTICA · Cuál usar**
>
> | Tu caso | Motor |
> |---|---|
> | Chimenea o foco en terreno más o menos llano, viento regular | **AERMOD** — más simple, más rápido, estándar |
> | Cumplimiento normativo de calidad del aire | **AERMOD** — es el modelo que espera el revisor |
> | **Calmas frecuentes** (el caso típico de quejas por olor de madrugada) | **CALPUFF** |
> | **Terreno complejo**: valles, laderas, viento que rola | **CALPUFF** |
> | **Brisas** marinas o de montaña que cambian de sentido | **CALPUFF** |
> | Distancias largas (decenas de km) | **CALPUFF** |
>
> Regla rápida: **si te preocupa lo que pasa cuando no hay viento o el viento no es el mismo en
> todo el dominio, ese es el terreno de CALPUFF.**

> **⚠️ Estado: en construcción — todavía no se puede lanzar desde la app**
>
> Lo que hay hecho es la **generación de los ficheros de entrada** de la cadena (GEO.DAT,
> 3D.DAT, CLOUD.DAT, CALMET.INP, CALPUFF.INP) en `getCalpuff.py`. Lo que **falta**: los
> ejecutables de CALMET/CALPUFF (en `src/bin/` solo están los de AERMOD), el lector de
> resultados y la integración en la interfaz.
>
> Además hay tres asuntos abiertos que conviene conocer antes de fiarse de una corrida:
> el parámetro **`MCTADJ`** (ajuste de terreno) no se está escribiendo y su omisión puede
> **infravalorar el resultado a la mitad**; la resolución de malla por defecto es de 250 m
> cuando el estudio de evaluación recomienda **400 m**; y los campos de **rugosidad, albedo y
> Bowen** van a un valor constante en vez de derivarse del uso del suelo como sí se hace en
> AERMOD ([§3.4](#34-uso-del-suelo)).
>
> Todo el detalle, con la configuración recomendada y sus fuentes, en
> [`notas_calpuff.md`](notas_calpuff.md).

---

# Parte 5 — Paso 4: las fuentes de emisión (pestaña Dispersión)

Esta es la pestaña donde **tú** aportas lo que ningún servicio puede darte: **qué emite,
cuánto y desde qué geometría**. Es, además, donde está la mayor incertidumbre de todo el
estudio (`theory_guide.md`, aviso sobre `Q`).

> **🖱️ CÓMO SE HACE · Abrir el mapa de fuentes**
>
> Ve a la pestaña **Dispersión** y pulsa **«🗺 Cargar / centrar mapa»**. Aparece un mapa
> interactivo centrado en tu punto (con capa de callejero y de satélite). A la izquierda
> tienes el **modo de edición**, la **lista de fuentes** y el **formulario de parámetros**.

El modo de edición son tres botones tipo interruptor:

| Modo | Qué hace |
|---|---|
| 🖐 **Navegar** | Mueves y haces zoom con normalidad (no crea nada) |
| 📍 **Punto** | Un clic crea una fuente **puntual** |
| ▭ **Área** | Cada clic añade un **vértice**; cierras el polígono para crear la fuente |

## 5.1 Dibujar una fuente puntual <a id="51-punto"></a>

> **🖱️ CÓMO SE HACE**
>
> 1. Pon el modo en **📍 Punto**. El cursor pasa a cruz.
> 2. Haz **un clic** justo sobre la chimenea (en la capa de satélite se ve bien). Aparece un
>    marcador rojo y la fuente se añade a la lista de la izquierda como `📍 P1 (lat, lon)`.
> 3. Selecciónala en la lista y rellena sus parámetros en el formulario (§5.3). Pulsa
>    **«Aplicar cambios»**.

## 5.2 Dibujar una fuente de área <a id="52-area"></a>

Una fuente de área es un **polígono**: la superficie de una pila de compostaje, un
decantador, una balsa, una celda de vertedero.

> **🖱️ CÓMO SE HACE**
>
> 1. Pon el modo en **▭ Área**.
> 2. Haz clic en cada **esquina** del polígono. Verás la línea de puntos siguiendo el cursor,
>    y el primer vértice marcado con un círculo blanco ("Cierra el polígono haciendo clic
>    aquí").
> 3. Para **cerrar**, haz clic **sobre el primer vértice** (necesitas al menos 3). Solo
>    entonces se crea la fuente, que aparece como `▭ A1  N vért. · X ha`.
> 4. **Clic derecho** deshace el último vértice; **Esc** cancela el polígono entero.

> **⚠️ OJO · Máximo 20 vértices**
>
> Una fuente de área corresponde a un tipo **AREAPOLY** de AERMOD, y **la herramienta limita a
> 20 vértices**. No dibujes polígonos con más esquinas: los rechaza. Para una pila rectangular,
> 4 vértices sobran; simplifica las formas curvas a un polígono de pocos lados.
>
> *(⚠️ Ese 20 es el límite histórico de AERMOD, que usaba un array fijo. Hay indicios de que las
> versiones modernas asignan memoria dinámicamente y admitirían más, pero **no está verificado**.
> En la práctica da igual: una superficie grande conviene trocearla en varios polígonos por
> razones físicas —distinta emisión por zonas— antes que por el límite de vértices.)*

## 5.3 Los parámetros de cada fuente <a id="53-parametros"></a>

El formulario cambia según el tipo. **Arriba, comunes a los dos:**

> **🔢 CAMPO · ID** — un nombre corto (P1, PILA_A, BIOFILTRO…). Te sirve para identificarla
> en la lista y en el resultado.
>
> **🔢 CAMPO · Contaminante** — qué emite este foco: `OTHER`, `SO2`, `NO2`, `CO`, `PM10`,
> `PM25`, `NH3`, `H2S` (o escribe el tuyo, el combo es editable). *Por defecto `OTHER`.*
>
> **🔢 CAMPO · Unidad del caudal** — `g (masa)` o `ou_E (olor)`. Ver [§5.4](#54-contaminante).
>
> **🔢 CAMPO · Altura emisión (m)** — la altura del foco sobre el suelo (`hs`). Para una
> chimenea, su altura física; para una pila de compostaje, ~2–3 m; para un decantador a ras
> de suelo, ~1 m. *Por defecto 10 m (3 m si la fuente es de área recién creada).*

> **🔑 OJO · Este es el campo más sensible del formulario, después del caudal**
>
> No es un parámetro más. El experimento de [§3.5.1](#351-contraprueba) lo midió sobre el mismo
> caso, cambiando solo la altura de una fuente de área:
>
> ```
> foco a 1 m  →  máximo 68,7 µg/m³
> foco a 3 m  →  máximo 18,0 µg/m³      ← ×12 entre 1 m y 6 m
> foco a 6 m  →  máximo  5,7 µg/m³
> ```
>
> Poner 1 m donde eran 3 m te multiplica el resultado por casi 4. Para comparar: acertar o no
> el uso del suelo de todo el dominio mueve el resultado un **1 %**.
>
> **Es, además, de los pocos datos que puedes acertar con una cinta métrica.** Mídelo en campo
> en vez de estimarlo a ojo: es donde mejor rinde el esfuerzo de medición.

> **⚠️ OJO · Un contaminante por simulación: si mezclas, habrá varias**
>
> AERMOD solo admite **un contaminante por ejecución**. Si defines fuentes con contaminantes
> distintos (por ejemplo H₂S en las pilas y NH₃ en el biofiltro), al pulsar «Run» la
> herramienta **agrupa las fuentes por contaminante y lanza una simulación por cada uno**.
>
> Consecuencia práctica: **el tiempo se multiplica por el número de contaminantes**. La
> etiqueta *Receptores* del panel te lo dice antes de lanzar
> (`2 fuente(s) · 2 contaminante(s): H2S, NH3 → total ≈ 8 min`).

**Si la fuente es PUNTUAL**, además:

| Campo | Símbolo | Qué es | Por defecto |
|---|---|---|---|
| Latitud / Longitud | — | Posición exacta (viene del clic, editable) | del clic |
| **Caudal (g/s)** | `Q` | La emisión: gramos por segundo | 1.0 |
| **Ø chimenea (m)** | `ds` | Diámetro de salida | 0.5 |
| **Tª gas (K)** | `Ts` | Temperatura de los gases (en **Kelvin**: 450 K ≈ 177 °C) | 450.0 |
| **Vel. salida (m/s)** | `vs` | Velocidad de salida de los gases | 10.0 |

> **🧠 CONCEPTO · Los tres últimos campos solo sirven para la sobreelevación**
>
> `ds`, `Ts` y `vs` existen para que AERMOD calcule cuánto **sube** el penacho al salir
> (`Δh`, ver `theory_guide.md §7`). Si tus gases salen calientes y rápidos (una chimenea de
> verdad), importan mucho. **Si la fuente es "fría" (Ts ≈ temperatura ambiente) y sin chorro,
> puedes dejarlos a sus valores por defecto: no harán nada**, porque sin contraste térmico no
> hay empuje. Es el caso del biofiltro tibio del ejemplo.

**Si la fuente es de ÁREA**, en cambio:

| Campo | Qué es |
|---|---|
| Vértices | (solo lectura) nº de esquinas del polígono |
| Área | (solo lectura) la superficie, en m² o ha |
| Centroide | (solo lectura) el centro geométrico |
| **Caudal (g/s·m²)** | `Q` **por metro cuadrado** de superficie. Por defecto 1e-5 |

> **⚠️ OJO · Las unidades del caudal CAMBIAN entre punto y área**
>
> Es el error de unidades más común. En una fuente **puntual**, `Q` va en **g/s** (todo el
> foco). En una fuente de **área**, `Q` va en **g/(s·m²)** — **por cada metro cuadrado**. Si
> tienes una emisión total de una pila y quieres meterla como área, tienes que **dividir por
> la superficie** primero. Ejemplo: 0,1 g/s repartidos en 1000 m² = 1e-4 g/s·m². Meter el
> 0,1 directo te daría un resultado ×1000.

> **💡 Los campos de caudal aceptan notación científica.** Puedes teclear `1e-5` o `3.4E-6`
> directamente; no hace falta contar ceros ni preocuparse de que se redondee a cero.

## 5.4 Contaminante y unidades: masa (g) u olor (ou_E) <a id="54-contaminante"></a>

El desplegable **«Unidad del caudal»** decide en qué unidades metes `Q` **y en qué unidades
sale el resultado**. Es la funcionalidad clave para estudios de olor.

> **🧠 CONCEPTO · A la dispersión le da igual la unidad**
>
> La ecuación de dispersión es **lineal**: multiplica el caudal por un factor geométrico y
> meteorológico. No sabe ni le importa si `Q` está en gramos o en unidades de olor. Así que:
>
> ```
> metes  g/s      →  sale  µg/m³      (masa)
> metes  ou_E/s   →  sale  ou_E/m³    (olor)
> ```
>
> Lo único que tienes que hacer es **ser coherente**. La herramienta cambia sola la etiqueta
> del campo (`Caudal (g/s)` ↔ `Caudal (ou_E/s)`) para que no te despistes.

> **🔢 CONCEPTO · Qué es una `ou_E` (unidad de olor europea, norma EN 13725)**
>
> Se define por **dilución**: **1 ou_E/m³ es la concentración a la que la mitad de un panel de
> narices detecta el olor**. Es decir, por construcción, el **umbral olfativo** de un compuesto
> es exactamente su 1 ou_E/m³. De ahí sale la conversión:
>
> ```
> C[ou_E/m³] = C[µg/m³] / umbral[µg/m³]
> ```

> **💡 La conversión, en vivo bajo el formulario**
>
> Al elegir contaminante y unidad, aparece una etiqueta con la equivalencia según el umbral
> olfativo tabulado. Con los valores reales de la herramienta:
>
> | Gas | Umbral olfativo | 1 ou_E/s equivale a | 1 g/s equivale a |
> |---|---|---|---|
> | **H₂S** (huevo podrido) | 0,571 µg/m³ | 5,7 · 10⁻⁷ g/s | 1,75 millones de ou_E/s |
> | **CH₃SH** (metilmercaptano) | 0,138 µg/m³ | 1,4 · 10⁻⁷ g/s | 7,3 millones de ou_E/s |
> | **NH₃** (amoniaco) | 1045 µg/m³ | 1,0 · 10⁻³ g/s | 957 ou_E/s |
>
> Sirve para pasar de masa a olor sin sacar la calculadora — pero **léete el aviso de abajo
> antes de fiarte**.

> **🧠 CONCEPTO · Mira la diferencia entre H₂S y NH₃: un factor 1800**
>
> El umbral del amoniaco (1045 µg/m³) es **1800 veces más alto** que el del sulfuro de
> hidrógeno (0,571 µg/m³). Traducción: **hace falta 1800 veces más amoniaco en el aire para
> olerlo igual.**
>
> Por eso, en una EDAR o una granja, **el H₂S manda aunque el NH₃ sea mucho más abundante en
> masa**. Es la razón de la regla de `theory_guide.md §10`: **ordena los compuestos por
> `Q/umbral`, no por `Q`.** Un gramo de mercaptano huele más que un kilo de amoniaco.

> **⚠️ OJO · La conversión masa ↔ olor SOLO vale para un compuesto puro**
>
> Este es el error conceptual más grave que se puede cometer en un estudio de olor.
>
> **El olor de una mezcla NO es la suma de los olores de sus componentes.** Hay **sinergia**
> (dos compuestos juntos huelen más que por separado) y **enmascaramiento** (uno tapa a otro).
> No existe una fórmula que lo prediga.
>
> Por eso existe la **olfatometría**: se coge la mezcla real, se mide con un panel de narices
> y se obtiene un `ou_E/s` **directo**.
>
> - Si tu fuente emite **un compuesto puro** (un escape de H₂S identificado) → puedes convertir.
> - Si tu fuente emite una **mezcla real** (EDAR, compostaje, granja) → **mide en ou_E y NO
>   conviertas desde masa**. El número que salga de sumar componentes será falso.
>
> La herramienta te avisa de esto en gris bajo la conversión, y si el gas no está en la tabla
> de umbrales te lo dice en vez de inventarse un número.

> **⚠️ OJO · Los umbrales olfativos varían muchísimo entre fuentes bibliográficas**
>
> Para el H₂S se publican valores de **0,4 a 13 ppb**: ¡un factor 30! Los que trae la
> herramienta son valores de referencia habituales (mayoría de Nagata 2003, el compendio más
> citado). **Para un expediente real, usa el umbral que exija la normativa aplicable y déjalo
> escrito en el informe.** Si no, tu resultado no es reproducible.

## 5.5 Guardar, cargar y `sources.json` <a id="55-guardar"></a>

Bajo la lista de fuentes hay cuatro botones: **Eliminar**, **Vaciar**, **Guardar**, **Cargar**.

> **🧠 CONCEPTO · No hace falta que te acuerdes de "Guardar"**
>
> Cada vez que creas, editas o borras una fuente, la herramienta **actualiza sola** el fichero
> `data/Sources/sources.json` — que es exactamente lo que leerá la simulación. Así que las
> fuentes que tengas en pantalla **son** las que se van a simular, sin que tengas que hacer
> nada. El botón **«Guardar»** es para otra cosa: exportar el juego de fuentes a un `.json`
> con nombre propio en `tmp/Sources/`, para **reutilizarlo** en otra sesión o como plantilla.
> **«Cargar»** lo vuelve a traer.

> **📁 FICHEROS · La estructura de `sources.json`**
>
> ```json
> {
>   "center": { "lat": 41.618, "lon": 0.343 },
>   "sources": [
>     { "type": "point", "id": "BIOFILTRO", "poll": "H2S", "unidad": "ou_E",
>       "lat": 41.6181, "lon": 0.3426,
>       "h": 8.0, "q": 500.0, "diam": 0.6, "temp": 305.0, "vel": 8.0 },
>     { "type": "area", "id": "PILA_A", "poll": "H2S", "unidad": "ou_E",
>       "verts": [[41.617,0.341],[41.618,0.341],[41.618,0.343],[41.617,0.343]],
>       "area_m2": 18500.0, "centroid": [41.6175, 0.342],
>       "h": 2.5, "q": 3e-5 }
>   ]
> }
> ```
>
> Puedes editarlo a mano si te resulta más cómodo que el ratón (para poner coordenadas
> exactas de un plano, por ejemplo). Al cargarlo, la herramienta valida y descarta lo que no
> sirva (un área necesita ≥3 vértices) y recalcula área/centroide si faltan.

> **💡 Al cargar un fichero de fuentes te pide confirmación** (*"Se sustituirán las N fuentes
> actuales por M del fichero. ¿Continuar?"*), porque **reemplaza** lo que tengas, no lo suma.

## 5.6 Criterio de proyecto: cómo modelar cada caso real <a id="56-criterio-fuentes"></a>

Aquí es donde la teoría se vuelve decisiones concretas. La regla maestra la da
`theory_guide.md §6 y §7`: **la chimenea es la excepción; casi todo lo demás es una fuente de
área pasiva a ras de suelo**.

> **💼 EN LA PRÁCTICA · Compostaje, EDAR, balsas, vertederos → ÁREA pasiva**
>
> - **Geometría:** dibuja el polígono real de la pila / el decantador / la balsa. No lo
>   aproximes por un punto en el centro: el vecino cercano (el que se queja) está tan cerca
>   que la diferencia es enorme.
> - **Altura:** la real de la emisión (1–3 m), no cero.
> - **Temperatura / velocidad:** irrelevantes (déjalas por defecto). Aunque una pila de
>   compostaje esté a 60 °C, el gas rezuma sin chorro y pierde el contraste en los primeros
>   centímetros: se modela como **pasiva** (`Δh ≈ 0`). Es la hipótesis conservadora.
> - **Caudal:** aquí está toda la incertidumbre. Sale de una **campana de flujo** medida en
>   campo o de factores de emisión tabulados, y **en g/(s·m²)**. Es, con diferencia, el dato
>   que más condiciona el resultado.

> **💼 EN LA PRÁCTICA · Chimeneas (biofiltro con extractor, secadero, caldera) → PUNTO**
>
> Rellena `hs`, `ds`, `Ts`, `vs` con los datos reales de la instalación. Si los gases salen
> calientes o rápidos, la sobreelevación `Δh` los llevará más arriba y más lejos, rebajando
> el impacto cercano. Una ironía útil de las EDAR: **cubrir los tanques y sacar el aire por
> una chimenea con biofiltro** convierte una fuente de área pasiva (mala para el vecino) en
> una fuente puntual elevada (que dispersa mejor) — y además reduce `Q`. Se gana por los dos
> lados.

> **💼 EN LA PRÁCTICA · Olores → mete `Q` en unidades de olor**
>
> Para un estudio de olor, el caudal no va en gramos sino en **unidades de olor europeas por
> segundo** (`ou_E/s` en un punto, `ou_E/(s·m²)` en un área), medidas por **olfatometría**.
> La herramienta te deja el campo etiquetado como "g/s", pero **a la dispersión le da igual la
> unidad**: si metes `ou_E/s`, el resultado sale en `ou_E/m³` (`theory_guide.md §9`). El
> truco es ser **coherente**: unidad de olor a la entrada → unidad de olor a la salida.

> **🧪 EJEMPLO · Nuestras dos fuentes del compostaje**
>
> - **PILA_A y PILA_B** → dos fuentes de **área**, polígonos de las pilas, `h≈2,5 m`, caudal
>   en `ou_E/(s·m²)` de la olfatometría, temperatura/velocidad por defecto.
> - **BIOFILTRO** → una fuente **puntual**, `hs` = altura de la chimenea del biofiltro, con su
>   `ds`/`vs` reales y `Ts` ≈ ambiente (biofiltro tibio → sin sobreelevación apreciable),
>   caudal en `ou_E/s`.

---

# Parte 6 — Paso 5: la simulación («Run» → AERMOD) <a id="parte-6"></a>

Con el terreno cargado, la meteo cargada y las fuentes dibujadas, ya solo queda un botón.

## 6.1 Pulsar «Run»: qué comprueba y qué ejecuta <a id="61-run"></a>

> **🖱️ CÓMO SE HACE**
>
> Pulsa **«Run»**. La app salta sola a la pestaña **Resultados** y empieza a trabajar; la barra
> de progreso y la consola te van contando cada etapa. Al terminar, aparece el **mapa de
> concentración**.

> **✅ Antes de arrancar, comprueba que tienes los tres ingredientes**
>
> Si falta alguno, «Run» **no arranca** y te dice exactamente cuál en el estado:
>
> | Comprueba que existe | Si falta, el mensaje dice | Se arregla con |
> |---|---|---|
> | `data/Terrain/elevacion_uso.npz` | `Falta terreno (getTerrain o LoadTerrain)` | getTerrain / LoadTerrain |
> | `data/Meteo/era5/*.csv` | `Falta meteo ERA5 (getMeteo o LoadMeteo)` | getMeteo / LoadMeteo |
> | `data/Sources/sources.json` | `Falta fuentes de emisión (pestaña Dispersión)` | Dibujarlas en la pestaña Dispersión |
>
> Recuerda que **`data/` se vacía en cada arranque de la app** (§0.4): al empezar una sesión
> nueva tienes que volver a cargar terreno y meteo con los botones **Load\***.

> **⚠️ OJO · Una simulación por contaminante**
>
> Al pulsar «Run», la herramienta **agrupa tus fuentes por contaminante** y lanza **una
> ejecución de AERMOD por cada uno** (es una limitación de AERMOD: un `POLLUTID` por corrida).
> Con fuentes de H₂S y NH₃ mezcladas, verás dos simulaciones seguidas.
>
> Lo que **no** depende del contaminante se calcula **una vez**: si dos contaminantes salen
> de la **misma geometría** (olor + H₂S de la misma pila), AERMAP se reutiliza; y en
> predicción, el **campo de viento** se calcula para el primero y los demás lo reutilizan.

> **⏱ Por qué una 2.ª fuente cuesta más del doble.** AERMOD calcula cada fuente sobre cada
> receptor y cada hora, pero además: (1) la malla se **refina alrededor de cada foco**, así
> que una fuente alejada trae su propio núcleo de receptores finos (+13 % de receptores a
> 300 m, +58 % a 3 km); y (2) en una fuente de **área** esos receptores cercanos son los más
> caros de integrar. Medido en Lleida (malla real): 2 áreas a 300 m **×2,8** el tiempo y a
> 3 km **×4,4**. Una fuente **puntual** cuesta ~1/7 de un área. Al pulsar «Run», la consola
> imprime el **tiempo estimado** con todo esto (por contaminante y en total, ±30 %). Si sale
> demasiado, sube la resolución en los focos o la razón de crecimiento (§2.2).

> **⏱ Cuánto tarda.** Para el caso de Lleida (650 receptores, 8760 horas, un contaminante):
> del orden de **5 minutos** en total. El grueso se lo lleva AERMOD; AERMAP es rápido. Si la
> etiqueta *Receptores* te anuncia mucho más, revisa la malla (§2.2) antes de lanzar.

> **👀 Mientras simula: vista previa en vivo**
>
> No hace falta esperar a ciegas. Mientras AERMOD recorre el año, la pestaña **Resultados**
> muestra un mapa que se va actualizando solo (cada 1-2 s), con dos capas excluyentes:
>
> - **⏱ Última hora simulada** — la pluma de la hora que AERMOD acaba de terminar: la ves
>   girar con el viento y cambiar entre el día y la noche a lo largo del año.
> - **Σ Media acumulada** — la media de todas las horas simuladas hasta ahora; va
>   convergiendo hacia la **media anual** final (las horas de calma no cuentan, igual que en
>   AERMOD).
>
> Arriba, la fecha simulada y el % del periodo; abajo, la escala (logarítmica) de la capa
> activa. La barra de progreso es **real** (horas simuladas / horas del periodo). Al terminar,
> el mapa de resultados sustituye a la vista previa.
>
> **Cómo funciona:** AERMOD escribe la serie horaria (el POSTFILE) a medida que simula; la
> app la lee a trozos según crece, sin cargarla entera. Se escribe **siempre** (en disco
> local, fuera de OneDrive) y en formato **binario**: medido, el formato de texto de antes
> multiplicaba ×2,3 el tiempo de AERMOD y pesaba 13 veces más (1,5 GB al año en el caso de
> Lleida); el binario no añade coste medible (~100 MB al año). Si el caso es tan grande que
> no conviene leer la serie entera, solo sirve para la vista previa y se borra al terminar,
> sin usarse para percentiles. Una instantánea por **día simulado** queda en caché en
> `%TEMP%\prosimnet_pst\<caso>\preview\`.
>
> **En predicción** (Modo meteo = Predicción) pasa lo mismo, por etapas: primero *«Calculando
> el campo de viento…»*; luego la dispersión **en vivo**, con las mismas dos capas: como
> va muy rápida (~6 horas simuladas por segundo), se muestra una instantánea **cada 3 horas
> simuladas**, todas en orden (ninguna se salta); y por último *«Generando
> resultados (animación y mapa)…»* con la última pluma a la vista, hasta que aparecen la
> **animación** y el **mapa estático** de siempre. Aquí la caché guarda una instantánea por
> **hora** (`%TEMP%\prosimnet_pst\<caso>_prediccion\preview\`); el `.lst` del modelo ya se
> escribe siempre, así que no ocupa disco extra.

## 6.2 Qué monta por dentro (la cadena entera) <a id="62-cadena"></a>

Aunque sea un botón, por debajo se ejecuta la **cadena oficial de la EPA** al completo. Merece
la pena saber qué pasa, porque si algo falla el mensaje se refiere a estas etapas:

```
data/ (terreno + meteo + fuentes)
        │
        ▼
 1. TERRENO → GeoTIFF sin comprimir       (elevacion_uso.npz → terreno.tif)
        │
        ▼
 2. AERMAP  → escribe aermap.inp, lanza aermap.exe
        │      → obtiene la cota + escala de colina de cada receptor
        ▼
 3. BPIPPRM → (si hay edificios + chimeneas) escribe bpip.inp, lanza bpipprm.exe
        │      → obtiene los coeficientes de downwash
        ▼
 4. METEO   → escribe aermet.sfc + aermet.pfl directamente desde ERA5 (sin AERMET)
        │
        ▼
 5. AERMOD  → escribe aermod.inp (fuentes + receptores + meteo + downwash)
        │
        ▼
 tmp/Aermod/<caso>/  con subcarpetas AERMAP/ BPIP/ AERMOD/  (+ copia a data/Aermod/)
```

Cuando termina, la pestaña AERMOD muestra el mapa y un resumen del tipo
`máx 17,99 µg/m³ · 2 fuente(s) · 0 aviso(s)`.

> **📁 FICHEROS · Lo que encuentras en un caso ya simulado**
>
> En `tmp/Aermod/<lat>_<lon>_<años>/`:
> - `AERMAP/` → `aermap.inp`, `terreno.tif`, `aermap.rec` (los receptores con su cota),
>   `aermap.out`.
> - `BPIP/` → `bpip.inp`, `bpip.out` (los coeficientes de downwash).
> - `AERMOD/` → `aermet.sfc`, `aermet.pfl`, **`aermod.inp`** (el fichero maestro), y tras
>   correr: `aermod.out` (el informe), `aermod.sum` (el resumen con el máximo), `aermod.plt`
>   (los valores para pintar), `ERRORS.OUT`.
> - `caso.json` / `resultado.json` — metadatos legibles. Ábrelos si quieres saber con qué
>   parámetros se corrió: nº de receptores, horas de meteo, cota base, si hubo downwash…

> **🔢 Detalles del cálculo que conviene conocer**
>
> - **Periodo de promediado:** AERMOD calcula 1 h, 24 h y periodo. Al mapa y al CSV sale la
>   **media del periodo**; los máximos de 1 h y 24 h están en `aermod.out`. Si tu criterio es un
>   **percentil o un valor enésimo**, simula con `postfile=True` y sácalo con
>   `percentiles_por_receptor` ([§7.3](#73-olores)).
> - **Terreno para AERMAP:** se remuestrea a **30 m** (el MDT05 a 5 m no aporta y ralentiza).
> - **Humedad del suelo:** fijada a `average` y clima **no árido**. No se expone en la
>   interfaz; si tu emplazamiento es claramente árido, es un parámetro a revisar en el código
>   (afecta a la razón de Bowen, [§3.4](#34-uso-del-suelo)).

> **🩺 SI FALLA:** los mensajes son explícitos y te dicen la etapa. "Falta el paquete ERA5
> completo" = cargaste una meteo antigua sin todas las variables. Un `E455` de AERMAP sería un
> GeoTIFF comprimido (no debería pasar: se genera sin comprimir a propósito). Los avisos
> `W465/W471` sobre el datum son **normales** y esperables: AERMAP no reconoce ETRS89 y asume
> NAD83, que es lo correcto.

## 6.3 «Save» y «Load»: guardar y recuperar resultados <a id="63-save-load"></a>

> **🖱️ «Save» — exportar el resultado**
>
> Guarda el resultado completo en `tmp/Results/<coordenadas>/`: el **mapa**, un **CSV** con los
> valores por receptor y un **resumen**. Es lo que te llevas al informe. El estado te confirma
> `Resultados guardados · máx X µg/m³`.

> **🖱️ «Load» — recuperar un resultado**
>
> Te pide una **carpeta de resultados** (la de `tmp/Results/<coordenadas>/`) y carga **todos
> los contaminantes de golpe**, cada uno como una capa. Si prefieres un fichero suelto, cancela
> el diálogo de carpeta y te deja elegir un `.html`, un `.plt` o un `.kmz`.

> **💡 Selector de contaminante en la pestaña AERMOD**
>
> Cuando hay **más de un resultado** (porque simulaste varios contaminantes, o cargaste una
> carpeta), aparece arriba una barra **`Contaminante:`** con un desplegable:
>
> - `TODOS (capas)` — el mapa combinado, con receptores, isolíneas y unidades de olor.
> - `H2S · máx 17,99 µg/m³` — cada contaminante por separado (solo la mancha de concentración).
>
> Empieza siempre por `TODOS (capas)`: es el que trae las isolíneas y la conversión a unidades
> de olor.

> **🧠 CONCEPTO · Y el KMZ, ¿para qué?**
>
> Un **KMZ** es el formato de Google Earth: lleva dentro una imagen del penacho más las
> coordenadas de sus esquinas. Es como las herramientas clásicas de AERMOD (AERPLOT) exportan
> un mapa de concentración.
>
> Aquí sirve sobre todo para **cargar simulaciones ajenas**: el resultado de otro consultor, un
> caso de referencia, un estudio anterior. Ya viene uno de ejemplo en el proyecto
> (`HF_F2_concentracion.kmz`). Para **tus** resultados no lo necesitas: usa Save/Load, que
> conservan los valores numéricos y no solo una imagen.

---

# Parte 7 — Leer e interpretar el resultado

## 7.1 El mapa de concentración <a id="71-mapa-conc"></a>

El resultado es un **mapa de colores**: cada punto tiene un valor de concentración `C` (la
incógnita de todo el estudio). Lo que buscas en él:

- **El máximo:** el valor más alto y **dónde cae**. Para una fuente pasiva a ras de suelo,
  caerá **pegado a la fuente**; para una chimenea alta, a cientos de metros o kilómetros
  (`theory_guide.md §5.3`).
- **La forma del penacho:** hacia dónde se estira. Debe ser coherente con la rosa de viento
  que viste en AERMET (hacia la dirección dominante).
- **El valor en los receptores sensibles:** cuánto le llega al pueblo del ejemplo. Ese es el
  número del informe.

> **⚠️ CLAVE · El mapa que ves es la MEDIA DEL PERIODO, no un pico**
>
> Es imprescindible entenderlo para no interpretar mal el resultado. El mapa de la pestaña
> AERMOD y el fichero `concentraciones.csv` contienen, para cada receptor, la **concentración
> media de todo el periodo simulado** — con un año completo, **la media anual**.
>
> Lo dice la propia cabecera del fichero que genera AERMOD:
> `PLOT FILE OF PERIOD VALUES ... AVERAGE CONC`.
>
> Consecuencia práctica: cuando la aplicación te dice `máx 17,99 µg/m³`, eso **no** es "la peor
> hora del año". Es **el receptor con la media anual más alta**. El pico horario real es
> bastante mayor.

## 7.2 Medias, máximos y periodos de promediado <a id="72-promedios"></a>

> **🧠 CONCEPTO · Toda concentración es una MEDIA sobre un tiempo**
>
> AERMOD no da "la concentración" a secas: da la **media** de la concentración sobre un
> **periodo de promediado**. No es lo mismo la media de 1 hora que la de 24 horas o la del
> año: cuanto más largo el periodo, más se suaviza el pico. La normativa siempre especifica el
> periodo ("media horaria", "media de 8 horas", "media anual"), porque comparar periodos
> distintos no tiene sentido.

> **🔢 DATO · Qué calcula el motor y qué llega a cada sitio**
>
> AERMOD calcula internamente **medias de 1 hora, de 24 horas y del periodo**. Pero no todo sale
> por el mismo sitio, y esto es lo que hay que saber:
>
> | Dónde mirar | Qué contiene |
> |---|---|
> | El **mapa** y `concentraciones.csv` | La **media del periodo** (anual) por receptor |
> | `aermod.out` (el informe) | Tablas con el **máximo y el segundo máximo** de 1 h, 24 h y periodo |
> | `aermod.pst` (**solo con `postfile=True`**) | La **serie horaria** por receptor — de aquí salen los percentiles y los valores enésimos (§7.3) |
>
> O sea: si necesitas el máximo horario, **está en `aermod.out`**, no en el CSV ni en el mapa.

> **⚠️ OJO · El máximo horario no es el criterio para todo**
>
> Para un tóxico agudo, el criterio suele ser el **máximo** (o un percentil alto) de las
> medias horarias. Para exposición crónica, la **media anual**. Para olor, un **percentil**
> (§7.3). No hay un único "resultado": hay que sacar el estadístico que pide **tu** normativa.

> **⚠️ OJO · El máximo horario no es el criterio para todo**
>
> Para un tóxico agudo, el criterio suele ser el **máximo** (o un percentil alto) de las
> medias horarias. Para exposición crónica, la **media anual**. Para olor, un **percentil**
> (§7.3). No hay un único "resultado": hay que sacar el estadístico que pide **tu** normativa.

## 7.3 El caso de los olores: lo que hay que hacer POR FUERA <a id="73-olores"></a>

Esta sección es la más importante si tu proyecto es de olor, porque hay dos cosas que
**AERMOD no hace** y tienes que aplicar tú.

> **⚠️ OJO · 1) El factor pico-media**
>
> AERMOD da **medias horarias**. Pero la nariz detecta un olor en **segundos**, y el penacho
> serpentea: en un punto pasas de nada a una bocanada intensa y otra vez a nada. La media
> horaria puede decir "no huele" mientras la realidad son **bocanadas** que sí se notan. Se
> corrige multiplicando por un **factor pico-media** `F = C_pico / C_media`, que **crece con
> la estabilidad y decrece con la distancia** (cerca y de noche puede llegar a ×10; lejos y de
> día, ×2–3). Hay formulaciones para estimarlo (Smith, Best, Schauberger). Un mapa de medias
> horarias **sin corregir infravalora la molestia** justo en las condiciones que causan las
> quejas (`theory_guide.md §9`).

> **🧠 CONCEPTO · 2) El criterio es un PERCENTIL, no un máximo**
>
> Que huela una hora al año no molesta a nadie, así que el olor no se juzga por el máximo sino
> por un **percentil de las medias horarias del año**. La forma típica del criterio:
>
> > *"El **percentil 98** de las medias horarias no debe superar **X ou_E/m³** en zona
> > residencial."*
>
> El P98 significa que se **acepta** superar X el 2 % de las horas del año (~175 h). El valor
> de X y el percentil **cambian según la comunidad autónoma / el país** (P98 con X entre 1 y
> 5 ou_E/m³ es lo habitual; más estricto en residencial que en industrial). Para sacar un
> percentil **necesitas el año completo** de horas simuladas — por eso getMeteo baja años
> enteros (§2.1).

> **✅ Cómo se calcula el P98 (desde el 22/07/2026 lo hace la herramienta)**
>
> Antes esto era una limitación: la salida solo traía la media del periodo y el percentil había
> que sacarlo por fuera. **Ya no.** El motor puede volcar la **serie horaria por receptor** y
> calcular el percentil él mismo.
>
> **1) Pide la serie al simular** — es opt-in, porque el fichero es grande (8760 × nº de
> receptores):
>
> ```python
> getAermod.prepare_case(..., postfile=True)
> ```
>
> **2) Saca el estadístico que necesites:**
>
> ```python
> getAermod.percentiles_por_receptor(
>     "…/aermod.pst",
>     pct=(98.0,),        # percentiles temporales: P98 de olor, P99,9…
>     rank=(19, 36),      # valores enésimos: 19.º horario de NO₂, 36.º diario de PM10
>     peak_factor=2.3)    # factor pico-media de olores (1.0 = sin factor)
> ```
>
> Devuelve, **por receptor**: `x, y, media, max, n`, una columna `P98` por cada percentil y una
> `R19`/`R36` por cada rango pedido.
>
> **El `peak_factor` merece atención:** multiplica la serie **antes** de calcular los
> estadísticos, que es el orden correcto — aplicar el factor pico-media después del percentil da
> un número distinto y erróneo. Ver
> [`../bibliografia/metodologia/olores_metodologia.md`](../bibliografia/metodologia/olores_metodologia.md).

> **⚠️ OJO · El error que sigue estando ahí: percentil temporal ≠ percentil espacial**
>
> Esto no lo arregla ningún código, así que conviene tenerlo presente. **No apliques un percentil
> a la columna `conc` de `concentraciones.csv`.** Ese fichero tiene **una fila por receptor** con
> su media del periodo, así que lo que obtendrías es el **percentil espacial entre receptores**
> («el punto que está peor que el 98 % de los puntos»), que **no tiene ninguna relación** con el
> percentil temporal que pide la norma («la concentración que se supera el 2 % de las horas»).
>
> El número resultante no significa nada, pero tiene aspecto de resultado. El percentil temporal
> sale de la **serie horaria** (`percentiles_por_receptor`), no del CSV de medias.

> **🔢 Qué estadístico sale de dónde**
>
> | Criterio | Qué hay que sacar | De dónde |
> |---|---|---|
> | Medias anuales (PM2,5, NO₂, PM10) | media del periodo | `concentraciones.csv` ✅ |
> | Máximo horario absoluto | el 1.º más alto | `aermod.out` ✅ |
> | NO₂ horario (18 superaciones/año) | el **19.º** más alto | `percentiles_por_receptor(rank=(19,))` ✅ |
> | SO₂ horario (24 superaciones) · diario (3) | el **25.º** · el **4.º** | ídem, `rank=(25,)` · `rank=(4,)` ✅ |
> | PM10 diario (35 superaciones/año) | el **36.º** más alto | ídem, `rank=(36,)` ✅ |
> | Olor, P98 horario | el percentil 98 de la serie | `percentiles_por_receptor(pct=(98.0,))` ✅ |
>
> Requisito para las cuatro últimas: haber simulado con `postfile=True`. Para los criterios
> **diarios** (SO₂ 24 h, PM10 24 h) el POSTFILE debe volcarse con el periodo de promediado de
> 24 h — ver `post_aveper` en `write_aermod_inp`.

> **🔢 Referencia rápida de criterios de olor por país ( órdenes de magnitud, verifica la
> norma que te aplique)**
>
> | País / región | Criterio típico |
> |---|---|
> | Reino Unido | P98 de 1,5 / 3 / 6 ou_E/m³ según lo "ofensivo" de la industria |
> | Italia (varias regiones) | P98, con factor pico-media constante ≈ 2,3 |
> | Alemania (GIRL) | frecuencia de horas de olor sobre el total del año |
> | España | **no hay norma estatal única**: depende de la CCAA / ordenanza municipal |
>
> **Esto son órdenes de magnitud para orientarte, no valores para un informe.** Coge siempre
> el criterio de la **normativa vigente** que aplique a tu emplazamiento.

## 7.4 Comparar con la normativa <a id="74-normativa"></a>

El paso final de un estudio: coger el estadístico correcto (máximo horario, media anual o
percentil, según el caso) en los **receptores sensibles**, y compararlo con el **límite legal**.
Si lo supera, toca proponer medidas correctoras.

> **🧠 CONCEPTO · El olor no baja proporcional a la emisión**
>
> Una última trampa de los olores (`theory_guide.md §9`): la intensidad **percibida** sigue la
> ley de Stevens (`I = k·C^n`, con `n ≈ 0,5`). Con `n = 0,5`, **reducir la emisión a la mitad
> no reduce el olor percibido a la mitad, sino solo ~30 %**. Las medidas correctoras de olor
> tienen que ser **agresivas** para notarse. Conviene explicarlo pronto al cliente: rebajar un
> 20 % la emisión y esperar que se acaben las quejas es esperar en vano.

---

# Parte 8 — Recetario por tipo de proyecto

Resumen operativo de cómo configurar cada caso típico. Todos comparten los pasos 1–3
(dominio, terreno, meteo); cambia sobre todo el **paso 4 (fuentes)** y el **estadístico** que
se mira al final.

## 8.1 Chimenea industrial <a id="81-chimenea"></a>

- **Fuente:** 📍 puntual, con `hs`, `ds`, `Ts`, `vs` reales (gases calientes y rápidos → hay
  sobreelevación, el máximo cae lejos).
- **Edificios:** sí, descárgalos (downwash puede importar si la chimenea es baja o hay naves
  cerca).
- **Dominio:** amplio (el máximo puede caer a varios km).
- **Perfil vertical:** planteártelo si la chimenea es alta.
- **Estadístico:** el que pida la norma del contaminante (SO₂, NOₓ, partículas): máximo
  horario, percentil o media anual.
- **Ojo:** si es NOₓ, recuerda que la química del NO₂ no es lineal (`theory_guide.md §8`);
  AERMOD lo aproxima con esquemas semi-empíricos, no lo resuelve de verdad.

## 8.2 Planta de compostaje <a id="82-compostaje"></a>

- **Fuente:** ▭ área(s) pasiva(s) (las pilas), `h≈2–3 m`, `Q` en g/(s·m²) o ou_E/(s·m²),
  temperatura/velocidad por defecto.
- **Dominio:** el impacto suele quedar en 1–2 km, pero cubre el receptor sensible.
- **Resolución:** fina (5–10 m) si hay relieve.
- **Estadístico:** si es olor, **percentil + factor pico-media** (§7.3).
- **Ojo:** el máximo cae **pegado a la valla**; no hay diseño de dispersión que lo arregle,
  solo reducir `Q` (cubrir, biofiltro) o alejar.

## 8.3 EDAR con problema de olor <a id="83-edar"></a>

- **Fuentes:** mezcla — decantadores y aireación como ▭ áreas pasivas; si hay tratamiento de
  aire, el escape como 📍 punto.
- **Compuestos:** H₂S, mercaptanos, NH₃… con umbrales olfativos **muy distintos**
  (`theory_guide.md §10`). Ordénalos por `Q/umbral`, no por `Q`: el H₂S manda aunque el NH₃
  sea más abundante. Para olor total, usa **una** medida olfatométrica de la mezcla, no sumes.
- **Estadístico:** percentil de olor + pico-media.

## 8.4 Cantera / acopio (partículas) <a id="84-cantera"></a>

- **Fuente:** ▭ área (el frente, el acopio), `Q` de partículas.
- **Ojo:** las partículas **se depositan** (pesan y caen): rompen la hipótesis de gas
  conservativo (`theory_guide.md §8`). Es un caso donde el resultado a distancia media sobra
  por el lado conservador si no modelas deposición.
- **Estadístico:** el de PM10 de la norma de calidad del aire (media diaria, media anual).

---

# Parte 9 — Cuando algo falla

## 9.1 Problemas frecuentes y su causa <a id="91-problemas"></a>

> **🩺 "Nada más arrancar, error de módulo (numpy / rasterio / PySide6)"**
> Estás usando el intérprete equivocado. Lanza con `C:\e2s\python.exe app.py`. En VSCode, los
> "errores" de import que marca el editor son **falsos** si no apunta a ese intérprete.

> **🩺 "getMeteo falla con 403 / licence / cost limits"**
> - `403 licence`: no has aceptado en la web del CDS la licencia de ese dataset (ERA5,
>   ERA5-Land y, para el perfil, ERA5 pressure-levels son licencias **distintas**).
> - `cost limits exceeded`: pediste demasiado de golpe (típico del perfil vertical; por eso
>   se trocea por quincenas). Con el paquete normal mes a mes no debería pasar.
> - Comprueba que las claves están en `src/config/keys/` y son de una sola línea.

> **🩺 "Me desaparecieron ficheros de `tmp/` que había descargado"**
> Es **OneDrive**. El proyecto está en una carpeta sincronizada, y OneDrive con "Archivos a
> petición" (Files On-Demand) puede **descargar/borrar** ficheros de caché. Soluciones:
> excluir la carpeta del proyecto de OneDrive, apagar "Archivos a petición", o mantener el
> backup que ya existe fuera de OneDrive en `%LOCALAPPDATA%\e2s_meteo_cache`. Cuando la app se
> empaquete como `.exe` no habrá OneDrive de por medio.

> **🩺 "La rosa de viento de AEMET sale muy lejos del punto o vacía"**
> Muchas estaciones automáticas no publican serie climatológica diaria (dan 404). La
> herramienta busca sola la más cercana **con datos**, que puede estar a decenas de km. Es
> normal en zonas rurales; ERA5/ERA5-Land no tienen ese problema (son malla, no estación).

> **🩺 "AERMOD suelta avisos W465 / W471 sobre el datum"**
> **Son normales, ignóralos.** AERMAP no reconoce ETRS89 y asume NAD83, que es exactamente lo
> correcto (su propia guía los trata como equivalentes). Aparecen en todas las ejecuciones.

> **🩺 "AERMOD termina pero suelta muchos avisos (W479 / TGINIT / gradiente de temperatura)"**
> No debería pasar ya: el caso de referencia de Lleida termina con **0 avisos**. Si te
> aparecen, lo más probable es que estés usando una **meteo antigua** descargada sin el perfil
> vertical. Vuelve a lanzar getMeteo para ese punto.
> *(Nota histórica: durante un tiempo se creyó que estos avisos venían de la falta de perfil.
> La causa real era otra —escribir el gradiente en horas estables, donde no aplica— y está
> contada en `notas_perfil_vertical.md §1`. Un buen recordatorio de que una hipótesis bien
> argumentada puede ser falsa.)*

> **🩺 "«Run» no arranca y dice que falta algo"**
> Recuerda que `data/` se vació al arrancar la app. Antes de simular, en **esta** sesión,
> tienes que haber cargado el terreno (getTerrain o LoadTerrain), la meteo (getMeteo o
> LoadMeteo) **y** tener fuentes dibujadas. Los tres. El mensaje te dice cuál falta.

> **🩺 "La simulación tarda muchísimo / me avisa de demasiados receptores"**
> Tienes la malla demasiado fina. Mira la etiqueta **Receptores** del panel: si pasa de 25 000
> te lo avisa. Sube la **Razón de crecimiento** (a 1,2 o 1,3) antes que la resolución: pierdes
> detalle lejos de la fuente, que es donde no importa ([§2.2](#22-malla)).
> Y recuerda que **cada contaminante es una simulación aparte**: tres contaminantes = triple
> de tiempo.

> **🩺 "Mi emplazamiento no está en el huso UTM 30"**
> La herramienta está fijada al **huso 30 (EPSG:25830 / ETRS89)**, que cubre la mayor parte de
> la España peninsular. Emplazamientos en husos 29 (Galicia oeste) o 31 (Cataluña este /
> Baleares) requerirían ajustar el código: hoy no están soportados de forma automática.

---

# Parte 10 — Anexos

## 10.1 Mapa de ficheros: qué es cada cosa que genera la herramienta <a id="101-ficheros"></a>

| Fichero | Lo genera | Qué es |
|---|---|---|
| `tmp/Terrain/<caso>/elevacion_uso.npz` | getTerrain | Elevación + uso del suelo + extensión. **La entrada de terreno.** |
| `tmp/Terrain/<caso>/edificios.gpkg` | getTerrain | Edificios (huella + altura), para downwash |
| `tmp/Terrain/<caso>/mesh/*.txt` | getTerrain | Red de nodos en texto (índice, x, y, z / uso) |
| `tmp/Meteo/<caso>/era5/era5m_levels_full_*.csv` | getMeteo | Paquete meteo horario completo (11 variables). **La entrada meteo.** |
| `tmp/Meteo/<caso>/era5prof/era5m_plev_prof_*.csv` | getMeteo | Perfil vertical por niveles de presión ([§4.3](#43-perfil)) |
| `tmp/Meteo/<caso>/eraland/*.csv`, `aemet/*.csv` | getMeteo | Viento a más resolución / de estación (comparación) |
| `tmp/Sources/sources_*.json` | Dispersión (Guardar) | Un juego de fuentes exportado con nombre |
| `data/Sources/sources.json` | Dispersión (auto) | **Las fuentes activas** que se simularán |
| `tmp/Aermod/<caso>/AERMAP/aermap.rec` | «Run» | Receptores con su cota y escala de colina |
| `tmp/Aermod/<caso>/AERMOD/aermod.inp` | «Run» | **El fichero maestro de AERMOD** |
| `tmp/Aermod/<caso>/AERMOD/aermet.sfc` / `.pfl` | «Run» | Meteo en formato AERMOD (superficie / perfil) |
| `tmp/Aermod/<caso>/AERMOD/aermod.out` | «Run» | El informe de la simulación |
| `tmp/Aermod/<caso>/AERMOD/aermod.plt` | «Run» | Los valores de concentración para pintar |
| `tmp/Aermod/<caso>/caso.json` · `resultado.json` | «Run» | Con qué parámetros se corrió y qué salió |
| `tmp/Results/<coords>/` | «Save» | Mapa + CSV + resumen, listo para el informe |
| `data/active.json` | (auto) | Qué caso de `tmp/` está cargado en `data/` ahora |
| `*.kmz` | AERPLOT / externo | Mapa de concentración de simulaciones ajenas |

## 10.2 Checklist de un estudio completo <a id="102-checklist"></a>

```
□ 1. Definir el punto (lat/lon) y comprobar con «View Map» que el dominio cubre
     todos los receptores sensibles.
□ 2. Ajustar la MALLA: resolución en focos + razón de crecimiento. Mirar la etiqueta
     «Receptores» y que el tiempo estimado sea asumible.
□ 3. Elegir periodo: AÑO COMPLETO si vas a sacar percentiles (olor).
□ 4. getTerrain → revisar las capas de terreno en la pestaña Mapa:
       · ¿cuánto DESNIVEL hay? (si es mucho, el relieve mandará)
       · ¿el uso del suelo es homogéneo o contrastado? (bosque/agua/ciudad → pesará)
□ 5. getMeteo → revisar las rosas en la pestaña Mapa (¿coinciden las tres? ¿dirección
     dominante razonable?). Primera vez: tarda (perfil vertical), luego va cacheado.
□ 6. Dispersión → dibujar las fuentes con la GEOMETRÍA y las UNIDADES correctas:
       · ¡g/s en punto, g/s·m² en área!
       · punto para chimeneas, área pasiva para compostaje/EDAR/balsas
       · elegir CONTAMINANTE y unidad (masa u ou_E); si es mezcla real, medir en ou_E
□ 7. «Run» → anotar el máximo y dónde cae. Comprobar que salió con 0 avisos.
□ 8. «Save» → guardar mapa + CSV + resumen para el informe.
□ 9. Sacar el ESTADÍSTICO que pide la norma (máximo horario / media anual / percentil).
□ 10. Si el criterio es un percentil o un valor enésimo (olor, NO₂ horario, PM10 diario):
       simular con postfile=True y sacarlo con percentiles_por_receptor().
       En olores, pasar ahí el factor pico-media (peak_factor), NO aplicarlo después (§7.3).
□ 11. Comparar con el límite legal en los receptores. Si supera, proponer medidas
      (y recordar que el olor no baja proporcional a la emisión).
□ 12. Documentar TODAS las hipótesis. Las tres que más se olvidan:
       · la procedencia de Q (el eslabón débil de todo el estudio)
       · la traducción CORINE→NLCD del uso del suelo (§3.4)
       · el umbral olfativo usado, si es un estudio de olor (§5.4)
```

> **🔑 Dónde gastar el esfuerzo, según lo medido (§3.5 y §3.5.1)**
>
> ```
> caudal Q  ≫  altura del foco  ≫  relieve  ≫  uso del suelo
>  (errores      (×12 en 5 m)      (30 %)         (~1 %)
>   de ×10⁷)
> ```
>
> Los dos primeros **los introduces tú a mano** y son los que más mueven el resultado. Los dos
> últimos se descargan solos con un botón. Si tienes una tarde para mejorar un estudio, dedícala
> a medir el caudal y la altura de emisión — no a refinar la malla.

## 10.3 Glosario exprés de siglas <a id="103-glosario"></a>

| Sigla | Qué es |
|---|---|
| **AERMOD** | El modelo de dispersión de la EPA. El que calcula la concentración. |
| **AERMAP** | Preprocesador de **terreno** de la EPA (cotas, altura de colina). |
| **AERMET** | Preprocesador **meteorológico** de la EPA (aquí sustituido por ERA5 directo). |
| **AERSURFACE** | Utilidad de la EPA que traduce uso del suelo → z₀, albedo, Bowen. |
| **BPIPPRM** | Programa de la EPA para el **downwash** de edificios. |
| **AERPLOT** | Utilidad que convierte la salida de AERMOD en un KMZ pintable. |
| **Dispersión** | (Nombre de la pestaña) donde defines las **fuentes**; antes se llamaba AERSOURCE. No es un programa EPA. |
| **MDT05** | Modelo Digital del Terreno de 5 m del PNOA (elevación, CNIG España). |
| **CORINE** | Mapa europeo de usos del suelo (de aquí sale z₀). |
| **ERA5 / ERA5-Land** | Reanálisis meteorológico horario del ECMWF (Copernicus). |
| **AEMET** | Agencia estatal de meteorología (viento real de estación, para validar). |
| **CDS** | Climate Data Store de Copernicus (de donde se baja ERA5). |
| **ou_E** | Unidad de olor europea (norma EN 13725). Umbral de detección = 1 ou_E/m³. |
| **`.sfc` / `.pfl`** | Ficheros meteo de AERMOD: superficie y perfil vertical. |
| **`.inp`** | Fichero de entrada (instrucciones) de cada programa de la cadena. |

---

> **Cierre.** Si has llegado hasta aquí, ya tienes el mapa completo: la guía teórica te dice
> **por qué** el penacho hace lo que hace, y esta te dice **qué botón** lo pone en marcha y
> **qué mirar** en el resultado. El consejo final es el mismo que atraviesa las dos guías:
> **la cadena vale lo que su eslabón más débil**, y ese eslabón casi nunca es el modelo — es
> un dato de entrada. Dedica tu atención a que el terreno, la meteo y sobre todo el **caudal
> `Q`** sean fieles a la realidad, y el resto lo hace AERMOD.

---

## 10.4 Referencias y de dónde sale cada dato <a id="104-referencias"></a>

Todo lo que la herramienta descarga viene de **servicios públicos**. Esta tabla te sirve para
dos cosas: entender de qué depende la aplicación, y **citar las fuentes en tu informe** (que hay
que hacerlo).

### Los datos que descarga la herramienta

| Dato | Origen | Acceso | Requiere clave |
|---|---|---|---|
| Elevación (**MDT05**, 5 m) | CNIG / PNOA — IGN España | <https://centrodedescargas.cnig.es> | No |
| Uso del suelo (**CORINE Land Cover**) | Copernicus Land Monitoring Service | <https://land.copernicus.eu> | No |
| Meteorología (**ERA5**, **ERA5-Land**) | Copernicus Climate Data Store — ECMWF | <https://cds.climate.copernicus.eu> | **Sí** |
| Viento de estación | **AEMET OpenData** | <https://opendata.aemet.es> | **Sí** |
| Edificios (huella y altura) | Sede Electrónica del **Catastro** | <https://ovc.catastro.meh.es> | No |

### Los programas que ejecuta

Son los **binarios oficiales de la EPA**, de dominio público, descargables del SCRAM
(*Support Center for Regulatory Atmospheric Modeling*): <https://www.epa.gov/scram>

| Programa | Qué hace | Versión de referencia |
|---|---|---|
| **AERMOD** | El modelo de dispersión | — |
| **AERMAP** | Cotas y escala de colina de cada receptor | **24142** |
| **BPIPPRM** | *Downwash* de edificios | — |
| *(AERSURFACE)* | Sus **tablas** se usan para traducir el uso del suelo a `z₀`, albedo y Bowen — el programa en sí no se ejecuta. Guía **EPA-454/B-26-007** | v26135 |

### Normas que conviene citar

- **UNE-EN 13725** — olfatometría dinámica. Es la que define la **unidad de olor `ou_E`**
  ([§5.4](#54-contaminante)).
- La normativa de **calidad del aire, emisiones y olores** está desarrollada, con el texto legal
  primario y su estado de vigencia, en [`../bibliografia/normativa/`](../bibliografia/normativa/).

> **💼 EN LA PRÁCTICA · Qué citar en el apartado de metodología de tu informe**
>
> Como mínimo: el **modelo y su versión** (AERMOD, con la versión del ejecutable), el **origen y
> periodo de la meteorología** (ERA5, año completo), el **origen del terreno y del uso del suelo**
> (MDT05 del CNIG, CORINE), y **de dónde sale el caudal de emisión** — que es el dato que más te
> van a discutir.
>
> Y declara las hipótesis del [checklist](#102-checklist), sobre todo la traducción CORINE→NLCD
> ([§3.4](#34-uso-del-suelo)) y el umbral olfativo si es un estudio de olor
> ([§5.4](#54-contaminante)).

### Documentación del proyecto

| Documento | Para qué |
|---|---|
| [`theory_guide.md`](theory_guide.md) | La física: **por qué** sale lo que sale. Incluye la lista completa de referencias científicas |
| [`notas_perfil_vertical.md`](notas_perfil_vertical.md) | El perfil de ERA5 en detalle |
| [`analisis_sensibilidad_terreno.md`](analisis_sensibilidad_terreno.md) | Cuánto importan el relieve y el uso del suelo |
| [`analisis_sensibilidad_usos.md`](analisis_sensibilidad_usos.md) | Contraste de paisaje y **altura del foco** |
| [`../bibliografia/`](../bibliografia/) | Normativa y estudios de referencia por temática |

---

*Pareja de este documento: `theory_guide.md` — la física de la dispersión, de la fuente al
receptor.*
