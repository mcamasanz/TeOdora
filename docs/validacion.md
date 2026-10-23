# Validación

*v0.1.0 (2026-10-18).* Cada motor de `odora` se ha validado frente a su programa de referencia
con una batería de casos. Las ocho baterías se han vuelto a correr sobre el código de este
paquete, ya con los nombres nuevos, y dan los mismos resultados que en el laboratorio.

## Resumen

| Motor | Programa de referencia | Casos | Resultado |
|---|---|---|---|
| `terreno.relieve` | AERMAP v24142 | 66 | 65 idénticos · 1 fuera de alcance (NADCON) |
| `terreno.superficie` | AERSURFACE v26135 | 48 | 45 idénticos · 3 abortan en los dos, como deben |
| `terreno.edificios` | BPIPPRM 04274 | 37 | 37 idénticos |
| `terreno.geofisica` | MAKEGEO 2.29 | 24 | 14 idénticos · 10 con ±1 en la última cifra de unos pocos valores |
| `meteo.capa_limite` | AERMET v26135 | 87 pasos (39 casos) | 73 idénticos · 14 fuera de alcance (formatos antiguos de EE. UU.) |
| `meteo.viento3d` | CALMET 5.8.5 | 51 (+2 en v0.1.1) | 51 dentro del criterio (peor: 0,30° de dirección, 0,22 % de velocidad); v0.1.1: ver abajo |
| `dispersion.penacho` | AERMOD v26135 | 142 | 124 idénticos · 15 solo en los últimos bits · 2 solo en un volcado de depuración · 1 fuera de alcance |
| `dispersion.puffs` | CALPUFF 5.8.5 | 65 | 65 dentro del criterio (peor FAC2: 0,993) |

En ningún caso un motor da un resultado distinto del original sin avisar. Si una opción aún no
está dentro de su alcance, se para con un mensaje claro y no escribe resultados.

## Cómo se valida

Hay dos criterios, según cómo se ha construido el motor.

**Motores traducidos** (relieve, superficie, edificios, capa_limite y penacho). Su Fortran es de
dominio público y se ha traducido rutina a rutina. Cada caso se corre con el original y con
`odora` sobre las mismas entradas, y se comparan **todos** los ficheros que escriben:
- los de texto, carácter a carácter, salvo la fecha y la hora de la corrida;
- los binarios, byte a byte;
- también la pantalla y los mensajes de error, incluidos los casos que deben abortar.

**Motores de sala limpia** (geofisica, viento3d y puffs). Se han reescrito desde la documentación
publicada sin abrir nunca su código. El original solo se ha usado como caja negra. Se comparan los
campos de salida con criterios de aceptación:

| Motor | Qué se compara | Criterio |
|---|---|---|
| geofisica | GEO.DAT carácter a carácter (salvo la línea que nombra el programa) | idéntico, o ±1 en la última cifra |
| viento3d | CALMET.DAT en todas las horas, capas y celdas | dirección media ≤ 10° y sesgo de velocidad ≤ 10 % |
| puffs | CONC.DAT hora a hora y receptor a receptor | FAC2 ≥ 0,8 · \|FB\| ≤ 0,3 · NMSE ≤ 1,5 · huella del P98 ≥ 90 % |

Los resultados reales quedan muy por dentro de estos límites (ver cada motor).

## Por motor

### `terreno.relieve` (≡ AERMAP)
- **E**: casos oficiales de la EPA; los que tienen salida publicada la reproducen.
- **D**: corridas reales de digicompost sobre el MDT de Lleida.
- **C**: opciones del control, tipos de receptor y fuente, avisos y errores.
- **T**: variantes de GeoTIFF (CRS, tipos de dato, teselas, compresión, huecos) y terrenos que
  cruzan el meridiano 0 y el ecuador.

Fuera de alcance: E6, que usa un ancla NAD27 sobre datos NAD83 y necesita NADCON (solo EE. UU.).

En la revalidación del paquete no se pudo correr E5: un proceso del original, huérfano, tenía
bloqueados sus ficheros. Los otros 65 casos dan lo mismo que en el laboratorio (64 idénticos y
E6 fuera de alcance).

### `terreno.superficie` (≡ AERSURFACE)
48 casos: resolución anual, estacional y mensual; climas húmedo, árido y con nieve; radios y
alturas de rugosidad; y el adaptador CORINE. El caso oficial de la EPA (RDU 2021) coincide con la
salida **publicada** por la EPA. Los 3 casos que abortan lo hacen en los dos programas.

### `terreno.edificios` (≡ BPIPPRM)
37 casos idénticos (salida, resumen y pantalla), entre ellos 10 de 10 casos oficiales con salida
publicada. Familias:
- **E**: oficiales;
- **D**: edificios del catastro alrededor de la planta de digicompost;
- **S**: sintéticos (modos, niveles, edificios combinables, chimeneas en esquinas y tejados,
  polígonos de muchos lados).

### `terreno.geofisica` (≡ MAKEGEO)
24 casos:
- **V**: el caso de demostración;
- **C**: una regla por caso;
- **A**: aleatorios con semilla fija;
- **D**: mallas de digicompost desde CORINE y MDT05;
- **E**: entradas que el original rechaza.

Los 10 casos «RED» coinciden en todo salvo unos pocos valores con ±1 en la última cifra impresa
(20 de unos 400 000): es el redondeo en precisión simple del original.

### `meteo.capa_limite` (≡ AERMET)
39 casos y 87 pasos. Cada paso compara todos sus ficheros: informe, mensajes, extracción, control
de calidad, SFC, PFL y pantalla. En total, 442 ficheros idénticos. Los 14 pasos fuera de alcance
usan formatos antiguos de EE. UU. (TD-6201, CD-144, SCRAM, SAMSON, HUSWO).

### `meteo.viento3d` (≡ CALMET)
51 casos dentro del criterio:
- **S**: sintéticos, uno por módulo;
- **O**: estaciones de superficie;
- **U**: sondeos;
- **C**: costa;
- **P**: pluviómetros;
- **E**: proyecciones y formatos;
- **R**: casos reales de Lleida y Huesca.

Peor dirección media: 0,30°. Peor sesgo de velocidad: 0,22 %.

**v0.1.1 (2026-10-20).** Cambian las horas de transición (amanecer y atardecer) con ITPROG = 1, 2
y el bloqueo activo (IFRADJ = 1); ITPROG = 0 no cambia. Contrastado con calmet.exe 5.8.5 en dos
casos reales de relieve complejo (La Galera, Montsià: 125×125 celdas de 400 m, 0-1 437 m), uno
con ERA5 sin estaciones y otro con ICON-EU y 36 estaciones: celdas·hora con |Δv| > 0,1 m/s a
10 m, 6 800 → 89 y 942 → 227; P98 de 24 h en 441 receptores, 16,3 % → 0,2 % y 0,9 % → 0,1 % de
diferencia media por receptor. El caso de regresión `llano_lleida` sale idéntico byte a byte.
⚠️ La batería de laboratorio de 51 casos aún no se ha vuelto a correr con la v0.1.1: los casos
con relieve y bloqueo (S, R) pueden moverse en las horas de transición. Detalle en
[core/meteo/viento3d/README.md](../core/meteo/viento3d/README.md) §Transiciones.

**v0.1.2 (2026-10-23).** Sin cambios en los motores: solo utilidades nuevas (`comun`,
`meteo.viento3d.almacen`, `fichero_viento.leer_campos`, `preparacion`) con sus pruebas
unitarias; los casos de regresión salen idénticos.

### `dispersion.penacho` (≡ AERMOD)
142 casos. Familias:
- **D**: el caso real de digicompost;
- **S**: variantes sintéticas;
- **E**: casos de prueba de la EPA;
- **F**: fondo y MAXDCONT;
- **V** y **N**: resto de entradas de la EPA;
- **O** y **W**: fosos y sidewash;
- **M**: varios años y re-arranque;
- **X**: MAXDAILY;
- **G**: volcados de depuración.

| Estado | Casos | Qué significa |
|---|---|---|
| idéntico | 124 | todos los ficheros iguales |
| últimos bits | 15 | solo difieren líneas de tres tipos: valores empatados en todas sus cifras que el original ordena de otra forma, un valor en la frontera de redondeo de su última cifra, o memoria sin inicializar que imprime el original |
| volcado de depuración | 2 | G_aertest_prime y G_capped_prime: solo difiere el fichero de DEBUGOPT PRIME, aún a medias; sus concentraciones coinciden |
| fuera de alcance | 1 | SCIM |

### `dispersion.puffs` (≡ CALPUFF)
65 casos dentro del criterio:
- **S**: mecanismos;
- **P**: chimeneas;
- **E**: efecto edificio ISC y PRIME;
- **D**: deposición seca, húmeda y mixta;
- **G**: malla de receptores;
- **F**: emisiones variables;
- **M**: MDISP 2 y 4;
- **R**: casos reales.

Peores valores: FAC2 0,993 (Huesca), |FB| 0,0075, NMSE 0,013 y huella del P98 0,980.

## Velocidad

Frente a los ejecutables originales, en los casos reales:
- `dispersion.puffs`, unas 6 veces más rápido;
- `meteo.viento3d`, de 3 a 5 veces más rápido;
- `terreno.relieve`, unas 12 veces más rápido;
- `dispersion.penacho`, unas 2 veces más lento. La primera corrida compila además el núcleo numba
  (unos 3 minutos; después se usa la caché).

En los casos diminutos pesa el arranque de Python (≈ 0,5 s por corrida). Las mejoras previstas
están en [PENDIENTES.md](../PENDIENTES.md).

## Dónde están las pruebas

- **Baterías completas**: necesitan los ejecutables originales y sus datos de prueba, así que
  viven en el repositorio privado de laboratorio, no en este.
- **Casos de regresión**: este repositorio lleva los 13 casos del [auditor](../auditor/README.md).
  Son pequeños, sus salidas de referencia se han contrastado con los originales, y se ejecutan
  sin ellos en unos segundos.
