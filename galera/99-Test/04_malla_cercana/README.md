# Prueba 04 · Malla muy fina cerca de la planta

Propuesta del usuario (2026-10-31): 5 m a ±100 m, 25 m a ±500 m, 50 m a ±1 km y el resto como hoy
(100 m a ±2 km, 300 m a ±6 km, 700 m hasta el borde). ¿Cuánto cuesta y qué aporta cada nivel?

**Cómo:** `prueba_malla.py` calcula con odora puffs cada foco por separado y con las dos mallas: 1 g/s,
42 h desde las 06 del 20-oct-2026, viento local (`odora_gfs_8est`), sin viviendas del Catastro. Los focos
son los INVENTADOS de la prueba 01 (pilas, biofiltro, chimenea), no los de ejemplo de `focos.json`. Cada
rejilla contiene a la más gruesa, así que se compara el valor calculado con el que saldría interpolando
desde la rejilla gruesa, solo en los puntos que faltarían y con más de 10⁻³ del máximo de la zona.

```
C:\e2s\python.exe 99-Test\04_malla_cercana\prueba_malla.py     (5 min)
```
Salidas: `resultados.json` y `campo_{PILAS,BIOFILTRO,CHIMENEA}.png`; casos en
`%TEMP%\ence_galera\99-Test\04_malla_cercana`.

## Resultados

**Coste** (pilas / biofiltro / chimenea)

| | Malla de hoy | Propuesta |
|---|---|---|
| Receptores (con núcleos y viviendas) | 8 404 | 12 484 (+49 %) |
| Tiempo | 26,1 / 26,7 / 30,1 s | 35,3 / 33,5 / 37,9 s (+25-35 %) |
| Memoria | 328 / 330 / 338 MB | 339 / 358 / 350 MB (+3-8 %) |
| Valores que guardar (> 10⁻⁶ del máximo) | 66 097 / 52 164 / 73 623 | ×2,0 / ×1,7 / ×1,6 |

El nivel de 5 m se lleva el 40-60 % de los valores nuevos (41 438 de 68 994 en las pilas).

**Qué se pierde sin cada nivel** (mediana del error; rango entre los tres focos)

| Zona | Paso frente a | Máximo de las 42 h | Hora a hora |
|---|---|---|---|
| ±100 m | 5 m frente a 25 m | 6-12 % | 18-55 % |
| 100-500 m | 25 m frente a 100 m (hoy) | 15-23 % | 47-60 % |
| 500 m-1 km | 50 m frente a 100 m (hoy) | 8-14 % | 19-22 % |
| 1-2 km | 100 m (hoy) frente a 300 m | 18-23 % | 39-44 % |

El último renglón no compara nada nuevo: da una idea de lo que se pierde con los 300 m de hoy más allá de
±2 km, la zona de 2-3 km de la que habló el usuario.

**Otras medidas**
- **Sin efecto en el resto:** el mismo receptor da el MISMO valor en las dos mallas (diferencia 0,0 en
  los tres focos). Confirma con odora que los receptores son independientes (antes solo medido con el
  ejecutable): la malla se puede ampliar o repartir sin tocar lo ya calculado.
- **Sin problemas numéricos:** campo suave a 5 m, sin singularidades ni «cuentas de collar», ni con la
  chimenea sobre un punto de la rejilla (junto a ella, en el suelo, menos de 10⁻³ del máximo).
- **El pico está junto al foco:** sube ×1,47 en las pilas (1 502 → 2 204 µg/m³ por g/s, sobre el borde de
  la pila) y ×1,90 en el biofiltro (3 309 → 6 299, a 5 m), dentro de la planta. La chimenea, ×1,08
  (75,6 → 81,7, a 152 m).
- **Una sola celda de viento:** ±100 m cae entero en UNA celda de 400 m (caras a −213 y +187 m en x, −224
  y +176 m en y); ±500 m abarca 3 × 3 y ±1 km, 6 × 6.
- **La zona de ±100 m está dentro de la planta:** son 4 ha de unas 5 ha, y los focos de ejemplo llegan a
  143 m al E del punto central: las pilas quedan fuera de esa zona.

**Receptores de cada opción** (`malla_anidada` + 66 núcleos + 393 viviendas)

| Opción | Receptores |
|---|---|
| Hoy | 8 404 |
| Propuesta del usuario | 12 484 |
| Sin 5 m y con 100 m a ±3 km | 12 652 |
| Con 5 m y con 100 m a ±3 km | 14 252 |

## Decisión (2026-10-31)
El usuario aprobó la opción sin 5 m y con 100 m a ±3 km (`gui/receptores_mapa.py`). Comprobada con las
pilas: 12 259 receptores sin viviendas, 34,3 s (+31 % frente a los 26,1 s de la malla anterior), 339 MB;
en los 10 491 receptores comunes con esta prueba, diferencia 0. El script conserva fija la malla anterior.
Después se añadieron 4 receptores con nombre (naves de Dacame, `planta/receptores.json`): 12 656 en total.

## Límites de la prueba
- Son 42 h con una situación meteorológica: los errores de un mapa de 5 años (media, P98) serán menores,
  porque el penacho barre todas las direcciones. Falta medirlo con la serie larga.
- El error hora a hora incluye los bordes del penacho, donde el error relativo es grande.
- No dice qué valor es el CORRECTO, solo cuánto detalle del propio modelo se pierde. A menos de 100 m de
  los focos el modelo tiene un solo viento y no representa el flujo alrededor de los edificios (en los
  focos de superficie no hay efecto edificio).
