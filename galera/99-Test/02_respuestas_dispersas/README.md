# 02 · Respuestas dispersas (alcance 1)

## Qué se quiere saber
Las respuestas unitarias de la prueba 01 son casi todo ceros (el penacho barre una franja). Si se
guardan SOLO los valores por encima de `umbral · máximo del foco`, ¿cuánto ocupan, cuánto cambian
la media, el máximo y el P98 por receptor del escenario y cuánto se tarda en leer y calcular?

## Formato (`almacen_respuestas.py`)
Por foco, ordenado por RECEPTOR y dentro por hora (como una matriz CSR): por cada valor guardado,
la hora (uint16), la hora de emisión del perfil h = 0…23 (uint8) y el valor en cuantización
LOGARÍTMICA de 16 bits entre umbral·máximo y máximo (error relativo uniforme ≈ 1·10⁻⁴). 5 bytes
por valor + 8 por receptor. El escenario se calcula por bloques de receptores: serie horaria
completa de cada receptor (pesos = emisión · perfil) → media, máximo y P98.

## Cómo se corre
    C:\e2s\python.exe 99-Test\02_respuestas_dispersas\prueba_dispersas.py [umbral de la escala]
Necesita los casos de la prueba 01. Lo pesado en `%TEMP%\ence_galera\99-Test\02_respuestas_dispersas`.

## Resultado (2026-10-24)
**Exactitud** (3 focos de la prueba 01, olor y NH3, 42 h, 8 011 receptores; error relativo máximo
en los receptores con valor ≥ 0,1 % del máximo, frente al escenario SIMULADO directamente):

| Umbral | Ocupa (42 h, 3 focos) | Comprimido | Media | Máximo | P98 |
|---|---|---|---|---|---|
| 10⁻⁶ | 2,21 MB | 0,87 MB | ≤ 0,37 % | ≤ 0,18 % | ≤ 0,17 % |
| 10⁻⁵ | 1,28 MB | 0,48 MB | ≤ 2,8 % | ≤ 1,1 % | ≤ 2,2 % |
| 10⁻⁴ | 0,57 MB | 0,18 MB | ≤ 19 % | ≤ 16 % | ≤ 15 % |
| denso (float32) | 97 MB | — | — | — | — |

⚠️ El umbral relativo al máximo de CADA foco engaña: lejos, un receptor suma muchas contribuciones
pequeñas (24 horas × focos) y truncarlas todas se nota. Con 10⁻⁶ el error es menor que el de la
propia cuantización del viento (0,4 %) y muchísimo menor que el del modelo; **10⁻⁶ es el umbral**.

**Escala, 5 años** (las 42 h repetidas hasta 43 806 h; comprobado que cualquier tramo repetido da
el mismo campo que la prueba corta y el mismo máximo), umbral 10⁻⁶, 3 focos, 8 011 receptores:

| | Medido |
|---|---|
| Ocupa sin comprimir | 2,1 GB (pilas 0,62 · biofiltro 0,33 · chimenea 1,15 GB) |
| Comprimido (con la proporción real de las 42 h, 0,39) | ≈ 0,8 GB para los 3 focos |
| Lo mismo en denso / en ficheros de concentraciones del motor | ≈ 101 GB / ≈ 11,5 GB |
| Leer los 3 focos | 4,2 s |
| Escenario completo: media, máximo y P98 en los 8 011 receptores | 69 s |
| Campo hora a hora de un día | 2,7 s (4,8 s la primera vez) |
| Memoria máxima del proceso | 5,2 GB (incluye las respuestas densas de partida) |

## Conclusión
Con umbral 10⁻⁶ las respuestas de 5 años ocupan ≈ 1/125 de lo denso y ≈ 1/14 de los ficheros del
motor, con error ≤ 0,4 %, y cualquier escenario se calcula en ~1 min sin el viento ni el motor.

## Pendiente
- Fijar el umbral en ABSOLUTO frente al criterio de olor más bajo (con la emisión máxima prevista de
  cada foco) en vez de relativo al máximo; medir con 5 años reales.
- Ficheros .npy con lectura por mapeo de memoria (hoy .npz se carga entero: memoria alta).
- Acelerar el escenario (por bloques en paralelo o numba) si 1 min resulta lento en la app.
