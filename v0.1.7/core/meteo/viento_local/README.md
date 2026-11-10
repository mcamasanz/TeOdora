# `teodors.meteo.viento_local` — viento alrededor de los edificios

⚠️ **NO VALIDADO y fuera de los motores.** No está en `teodors.MOTORES` ni se lanza con `python -m teodors`. Solo **enseña** el efecto
de los edificios: **no da valores para un sensor** y **el penacho no lo usa** (`dispersion.puffs` lee un solo viento). No equivale a
ningún programa y nunca se ha comparado con una medida de una planta.

<!-- manual -->
## Qué hace
`meteo.viento3d` trabaja con celdas de cientos de metros y sin obstáculos. Este paquete dibuja, a pocos metros, cómo los rodea el
viento. Es un **modelo de masa consistente con zonas empíricas** (Röckle 1990; Kaplan y Dinar 1996; Pardyjak y Brown 2003; Singh et
al. 2008), escrito desde las ecuaciones publicadas:

1. **Campo inicial:** perfil logarítmico neutro, con la dirección y la velocidad que se le den.
2. **Zonas de cada edificio,** con fórmulas: delante, un frenado; detrás, una cavidad con flujo inverso y una estela con menos velocidad.
3. **Corrección de masa:** el campo más cercano al anterior que no crea ni destruye aire y no atraviesa los sólidos (∇²φ = −∇·u₀,
   u = u₀ + ∇φ, resuelto con SOR rojo-negro). Es lo que hace que el viento rodee los edificios y se acelere a los lados.

No resuelve ecuaciones de movimiento. Como es neutro, el campo escala con la velocidad: basta **una biblioteca por dirección**, sin
calcular las horas una a una. Cada campo va relativo al viento SIN edificios a esa altura: lejos de ellos vale 1 y empalma con el
viento de la zona. Por eso NO es la velocidad real a esa altura.

## Entradas y salidas
| | |
|---|---|
| Entrada de `modelo.calcula` | `Dominio` (rejilla regular con suelo y alturas) y `edificios`: `[{"poligono", "h", "mascara"}]` |
| Entrada de `modelo.lee_lidar` | Un `.npz` con rejillas de 1 m: `dsm` (lo más alto), `dtm` (suelo), `dsm_edif` (lo más alto de la clase edificio), `edificio` (puntos de esa clase), `x0`, `y0` |
| Salida de `modelo.calcula` | `u`, `v`, `w` en los centros (nz, ny, nx), `iteraciones`, `residuo`, `div_antes`, `div_despues`, `cavidad` |
| Salida de `biblioteca.principal` | Un `.npz`: `u`, `v` en int16 (direcciones, ny, nx), `paso`, `x0`, `y0`, `dx`, los dos puntos, los radios, `escala`, `solido`, `alto` |

Necesita scipy para leer el LiDAR y sacar los obstáculos (`pip install teodors[viento_local]`); `calcula` y `mezcla` solo necesitan numpy y numba.

## Uso
```python
from teodors.meteo.viento_local import biblioteca, modelo

# Un obstáculo a mano: dominio de 120 x 80 x 60 m con celdas de 2,5 x 1,25 m
dom = modelo.Dominio(-40.0, -40.0, 48, 32, 2.5, 48, 1.25, altura=altura)
c = modelo.calcula(dom, 270.0, [{"poligono": poligono, "h": 10.0, "mascara": altura > 0}])

# La biblioteca de una planta: lo propio del sitio va en el bloque `viento_local` de su planta.json
from teodors import planta
biblioteca.main(activa=planta.actual())             # --lidar <rejillas de 1 m>  --paso <grados entre direcciones>

# Un viento cualquiera (u, v) de la zona: elige los dos campos más cercanos y los mezcla
lib = biblioteca.lee("campos.npz")
u_mapa, v_mapa = biblioteca.mezcla(lib, u, v)       # en m/s, con NaN dentro de los edificios
```

⚠️ Este paquete no importa `teodors.planta`, como los motores: los datos del sitio llegan por parámetro o con `activa`.

## Validación y alcance
**No hay validación:** ni una medida de una planta. Las pruebas (`auditor/pruebas/unitarias/test_viento_local.py`, con obstáculos
inventados) comprueban que el código hace lo que dicen sus ecuaciones y dejan medido dónde queda frente a referencias externas.

**Lo que la formulación exige, y se cumple:**
- Masa: en el cubo a 2,5 m, la divergencia baja de 0,39 a 8,6·10⁻⁵ 1/s (se pide 10⁻⁴) y el balance de toda la caja cierra a 1,6·10⁻⁴ de lo que entra.
- Dentro de los sólidos y a través de sus caras y del suelo, velocidad cero exacta.
- Sin obstáculos, el perfil logarítmico exacto. Con un dosel uniforme, la fórmula de Cionco (1965) exacta.
- Simetrías: obstáculo simétrico, viento opuesto y viento girado 90°, a menos de 10⁻⁴ (el residuo del cálculo).
- Entrada: lejos del obstáculo llega el perfil sin tocar: se desvía un 4,8 % a 3,5 H y un 0,32 % a 9,5 H.

**Un cubo frente a lo medido** en canal por Martinuzzi y Tropea (1993, Re = 40 000; ERCOFTAC UFR 3-14, tabla 1): separación delante 1,04 H
y reataque detrás 1,612 H. El canal no es la capa límite atmosférica: es una referencia de orden.

| Celda (celdas por lado) | Reataque: primera celda con u > 0 | Reataque: cruce por cero | Estela a 2 H y 5 H (u/u₀) | A un lado y encima (u/u₀) |
|---|---|---|---|---|
| 1 m (10) | 1,35 H | 1,30 H | 0,49 y 0,99 | 1,10 y 1,08 |
| 2,5 m (4) | 1,38 H | 1,19 H | 0,54 y 0,99 | 1,09 y 1,10 |
| 5 m (2) | **0,75 H** | **0,44 H** | 0,67 y 0,99 | 1,11 y 1,13 |

- ⚠️ **Esto no demuestra que prediga la estela:** la longitud detrás la impone una fórmula (Fackrell, 1,45 H en un cubo) y la de delante otra (Röckle, 1,11 H). Se comprueba el código y las fórmulas. Queda entre un 14 % y un 26 % corto, según cómo se mida.
- ⚠️ **Unas 4 celdas por obstáculo, como poco:** con 2, la cavidad cae a la mitad.
- ⚠️ A 5 H la estela ha desaparecido por construcción (acaba en 3 veces la cavidad). Sin vórtice delante ni recirculación a los lados.

**Una loma baja** frente a Jackson y Hunt (1975), aceleración relativa ≈ 2 h / L: 0,155 frente a 0,4 (h = 20 m, L = 100 m) y 0,076 frente a 0,2 (h = 10 m). Crece con h como dice la teoría, pero sin
ecuaciones de movimiento se queda en el 40 %.

**Medido en el proyecto del que viene, en una planta real** (no repetido aquí): el cambio de más del 20 % o 20° llega a 43-76 m del edificio, ⚠️ limitado por la fórmula, probablemente corto. Con 10 m de celda, 10 % de error a menos de 50 m frente a 3 % con 5 m, y se dejan de ver obstáculos. El dosel de los árboles usa a = 1,5, un supuesto.

**La mezcla** la hacía el mapa de la aplicación del proyecto: `mezcla` da lo mismo que esa función en un navegador (80 celdas × 11 vientos: los mismos NaN y 5,8·10⁻⁷ m/s como mucho, por los Float32 del mapa).

**Tiempo:** ~10 M de celdas, 42 s por dirección con otros cálculos a la vez (i7-1255U). `_sor` no guarda su compilación (`cache=False`): ~2 s en cada proceso.

## Lo que no hace
1. **Noches estables y calmas:** solo es neutro, y es cuando suele haber más olor.
2. **Corregir la dirección de entrada:** hereda el error del viento de la zona. El detalle no arregla eso.
3. **Concentraciones:** `dispersion.puffs` no puede usar este campo.
4. **Adaptarse a otra planta sin mirar:** los umbrales de `obstaculos` (2,5 m, 20 m², 800 m²…) y de `_misma_cubierta` salen de una sola planta. Mirar el resultado antes de usarlos.
5. **Un solo centro:** `puntos` son dos puntos distintos, los extremos de un segmento. Con uno solo, el mapa de la aplicación divide por cero.
<!-- /manual -->

## Ficheros

| Fichero | Contenido | Viene de | Equivale a |
|---|---|---|---|
| `__init__.py` | Aviso de que no está validado. | — | — |
| `modelo.py` | `Dominio`, `perfil`, `direccion_a_vector`, zonas empíricas de un edificio (`_zonas`), corrección de masa (`_sor`), `calcula`; del LiDAR a la rejilla: `lee_lidar`, `obstaculos`, `a_rejilla`, `monta`, `a_altura`. | proyecto La Galera (`viento/local.py`) | — |
| `biblioteca.py` | Un campo por dirección: `parametros` (del bloque de planta.json), `zona`, `principal`, `lee`, `mezcla` y la línea de órdenes `main`. | proyecto La Galera (`gui/tareas/viento_local_biblioteca.py`; `mezcla`, de su mapa) | — |
