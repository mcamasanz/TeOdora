# teOdors

Herramienta propia para simular cómo se dispersan los olores y los contaminantes de una instalación industrial: motores de terreno, de
meteorología y de dispersión, y una aplicación de escritorio para quien opera la planta.

Este repositorio guarda por separado **el código común** y **los datos de cada instalación**, y cada instalación dice qué versión del
código usa. Así se pueden tener muchas plantas y saber siempre con qué código funciona cada una.

## Cómo está organizado

```
teOdors/
├── README.md              este fichero
├── v0.1.3/                una versión del código común (el «núcleo»)
│   ├── core/              motores, aplicación, descargas de datos…: se importa como `teodors`
│   ├── auditor/           las reglas y las pruebas que tiene que pasar cada versión
│   ├── cargador/          permite usar esta versión sin instalar nada
│   ├── nueva_planta.py    crea la carpeta de una instalación nueva
│   └── README.md          documentación técnica de esta versión (CHANGELOG.md, LICENSE…)
├── galera/                una instalación
│   ├── VERSION            la versión del núcleo que usa: v0.1.3
│   ├── main.py            abre su aplicación con esa versión
│   ├── entrada/           sus datos de entrada: terreno, usos del suelo, edificios, focos…
│   ├── docs/              su documentación
│   ├── 99-Test/           sus pruebas
│   └── README.md
└── .github/workflows/     el auditor se ejecuta en cada subida a `main`
```

Dos reglas sostienen todo lo demás:

1. **Una versión publicada no se vuelve a tocar.** Un cambio en el núcleo es una carpeta nueva (`v0.1.4/`). Una planta que funciona con la
   `v0.1.3` seguirá dando los mismos resultados aunque salgan versiones nuevas, hasta que se decida pasarla a otra.
2. **Una instalación no lleva código, solo datos.** Lo que sirve para más de una planta va al núcleo. Cambiar de planta es cambiar de carpeta.

## Instalaciones y la versión que usa cada una

| Instalación | Carpeta | Versión | Estado |
|---|---|---|---|
| Planta de biometano de ENCE en La Galera (Montsià, Tarragona) | [`galera/`](galera/) | v0.1.3 | En desarrollo: los focos son de ejemplo, así que sus resultados aún no valen |

Al crear una instalación o cambiar su fichero `VERSION`, actualiza esta tabla. El auditor comprueba que cada planta usa una versión que existe.

## Versiones del núcleo

| Versión | Fecha | Qué trae |
|---|---|---|
| [`v0.1.3`](v0.1.3/CHANGELOG.md) | 2026-11-02 | La herramienta entera pasa al núcleo: aplicación, descargas, planes de operación, gases, normativa, visor 3D y viento local |
| `v0.1.2` y anteriores | hasta 2026-10-23 | Solo los motores y sus utilidades, con el nombre antiguo (`odora`). Están en sus etiquetas de git, sin carpeta |

## Qué hay en la carpeta de una instalación

| Qué | Dónde | Para qué |
|---|---|---|
| Versión del núcleo | `VERSION` | La que carga `main.py`. Si no existe o no coincide, la aplicación no arranca y lo dice |
| Identidad y parámetros | `entrada/planta.json` | Nombre, huso, tamaño del dominio, malla de receptores, servicios de datos… |
| Coordenadas | `entrada/emplazamiento.json` | Dónde está la planta |
| Terreno y usos del suelo | `entrada/terreno/` | Cotas, usos y núcleos de población: se descargan una vez |
| Edificios | `entrada/edificios/` | Los que hay alrededor de la planta: se descargan una vez |
| Focos | `entrada/focos.json` | Cada foco de emisión: tipo, ubicación, emisiones y funcionamiento |
| Receptores y normativa | `entrada/receptores.json`, `entrada/normativa.json` | Puntos con nombre donde dar resultados, y los límites que se aplican |
| Dónde van los cálculos | `entrada/rutas.json` | La carpeta de los cálculos, fuera del repositorio |
| Opcionales | `entrada/viento_local/`, `entrada/recursos/` | Viento alrededor de los edificios, ejemplo de la ventana de configuración y ortofoto del visor 3D |

**Fuera del repositorio:**
- los **cálculos** (viento de varios años, respuestas de los focos, resultados): pesan gigas y se pueden rehacer. Van a la carpeta de `rutas.json`;
- las **claves de API**, que cada usuario guarda en su equipo;
- los **ejecutables de terceros** y la gestión comercial.

## Cómo se trabaja

### Abrir la aplicación de una instalación

Hace falta Python 3.11 con las dependencias de la interfaz (`pip install -e "v0.1.3[gui3d]"`; lo instalado no interfiere, porque `main.py` usa siempre la versión de `VERSION`).

```bash
python galera/main.py
```

### Añadir una instalación

```bash
python v0.1.3/nueva_planta.py mi_planta --nombre "Mi planta" --lat 41.63 --lon 0.38 --corine ruta/CLC2018_ES.gpkg --descargar
python mi_planta/main.py
```

Crea `mi_planta/` con la versión actual del núcleo, calcula el huso de esas coordenadas, descarga el terreno, los usos del suelo y los edificios y anota las
estaciones cercanas. Después, en `entrada/`, se revisan `planta.json` y `rutas.json` y se añaden los focos desde la aplicación (`python mi_planta/main.py --edicion`).
El viento local, el ejemplo de la configuración y la ortofoto del visor son opcionales: sin ellos, la aplicación funciona igual, con el viento de la zona.

⚠️ Los servicios de datos son los de España (terreno, edificios) y Cataluña (estaciones). En otro sitio hay que cambiarlos o añadirlos.

### Pasar una instalación a otra versión

1. Cambia su fichero `VERSION` (por ejemplo, a `v0.1.4`).
2. Lanza sus pruebas y compara sus resultados con los de antes.
3. Actualiza la tabla de arriba y sube el cambio.

Si algo va mal, volver atrás es deshacer esa línea: la versión anterior sigue en su carpeta.

### Publicar una versión nueva del núcleo

1. Copia la última carpeta con el número nuevo: `v0.1.3/` → `v0.1.4/`.
2. Cambia el número en `core/__init__.py`, `pyproject.toml` y `auditor/pruebas/unitarias/test_paquete.py`, y añade la entrada en `CHANGELOG.md`.
3. Haz los cambios **solo en la carpeta nueva**.
4. Audita, desde ella: `python -m auditor`. Compara con la versión anterior y tiene que dar **APTO**.
5. Sube a `main`, ponle la etiqueta y añádela a la tabla de arriba:
   ```bash
   git tag -a v0.1.4 -m "teOdors 0.1.4"
   git push origin main v0.1.4
   ```

### Qué vigila el auditor

Se ejecuta en cada subida a `main` y se puede lanzar a mano. Las reglas, en [`v0.1.3/auditor/README.md`](v0.1.3/auditor/README.md):

| Regla | Qué exige |
|---|---|
| R1-R3 | El código compila, pasan todas las pruebas y son rápidas |
| R4 | Todo código nuevo o modificado trae sus pruebas |
| R5 | Un resultado de referencia solo cambia si se justifica por escrito |
| R6 | No se pierde ninguna prueba respecto a la versión anterior |
| R7 | Cada carpeta se llama como su versión, una versión publicada no ha cambiado y cada planta usa una versión que existe |

## Licencia

Software propietario, todos los derechos reservados (ver [`v0.1.3/LICENSE`](v0.1.3/LICENSE)). Las librerías de terceros, en
[`v0.1.3/THIRD-PARTY-NOTICES.md`](v0.1.3/THIRD-PARTY-NOTICES.md). Los datos de cada planta tienen sus propias condiciones, citadas en el `README.md` de su carpeta.
