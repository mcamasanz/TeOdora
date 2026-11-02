# Prueba 06: viento local alrededor de los edificios

**Pregunta (usuario, 2026-11-01):** habrá sensores muy cerca de los edificios. ¿Se puede obtener el viento con más
resolución y teniéndolos en cuenta? `viento3d` no puede: celda de 400 m, sin obstáculos.

**Respuesta de la prueba:** funciona como prototipo y es rápido, pero su alcance y sus estelas salen de fórmulas
empíricas. La parte cercana queda un 15 % corta frente a lo medido; la lejana está sin validar. No es todavía un resultado para
decidir dónde poner un sensor con garantías.

## Método
`lib/galera/viento/local.py`: modelo de masa consistente con zonas empíricas (Röckle 1990; Kaplan y Dinar 1996; Pardyjak y Brown 2003;
Singh et al. 2008), escrito desde las ecuaciones. Perfil logarítmico neutro de entrada → zonas de frenado, cavidad y estela
por edificio → corrección de masa (∇²φ = −∇·u₀, SOR rojo-negro en numba). Sin ecuaciones de movimiento. Solo neutro: el campo escala
con la velocidad, así que basta una biblioteca por dirección.

## Datos: alturas del LiDAR, no del Catastro
LiDAR territorial del ICGC 2021-2023, teselas `286507` y `287507` (790 MB, en `%TEMP%\ence_galera\99-Test\06_viento_local`), 30
puntos/m², EPSG:25831. `lib/galera/gui/tareas/lidar_planta.py` lo pasa a rejillas de 1 m; se lanza con `python -I`. ⚠️ Es anterior a la compra por ENCE (dic. 2024).

**El Catastro no sirve aquí:** el polígono de «8 plantas» (4 560 m²) mezcla balsas a ras de suelo y depósitos, así que con plantas ×
3 m las balsas saldrían como edificios de 24 m; el de «14 plantas» mide 2,4 m.

| Obstáculo (centro, UTM 31) | Altura | Ancho × fondo |
|---|---|---|
| Nave (286 775, 4 507 473) | 9,8 m | 30 × 25 m |
| Digestor (286 808, 4 507 459) | 13,3 m | 24 × 24 m |
| Digestor (286 809, 4 507 435) | 13,3 m | 21 × 23 m |
| Tanque (286 790, 4 507 446) | 11,7 m | 22 × 16 m |
| Tanque bajo (286 828, 4 507 448) | 6,4 m | 20 × 19 m |

Son extensiones de la huella en este y norte, no diámetros. Olivos en el 49 % de la zona, altura media 3,9 m.

## Banco de pruebas: cubo de 10 m (`prueba_cubo.py`)
Referencia: [ERCOFTAC UFR 3-14, tabla 1](https://kbwiki.ercoftac.org/w/index.php?title=UFR_3-14_Evaluation): medido
(Martinuzzi y Tropea 1993, canal, Re = 40 000) 1,04 H delante y 1,612 H detrás; LES 1,65-1,72 H; RANS k-ε 2,2-2,7 H detrás. La
página no deja claro a qué columna va cada número; se toma 1,612 como reataque trasero porque dice que el de techo no ocurre en los experimentos.

| Celda | Reataque detrás | Medido | Estela a 2 H y 5 H (u/u₀) | Lado a 0,5 H (u/u₀) |
|---|---|---|---|---|
| 1 m | 1,35 H | 1,61 H | 0,49 y 0,99 | 1,10 |
| 2,5 m | 1,38 H | 1,61 H | 0,54 y 0,99 | 1,09 |
| 5 m | **0,75 H** | 1,61 H | 0,67 y 0,99 | 1,11 |

- Divergencia: de ~1 a < 10⁻⁴. 576 000 celdas en 5 s, compilación incluida.
- **Un obstáculo necesita unas 4 celdas de lado:** con 2 celdas (10 m a 5 m) la cavidad cae a la mitad.
- ⚠️ La longitud detrás la impone una fórmula (1,45 H): esto comprueba el código y la fórmula, no una predicción.
- ⚠️ Sin vórtice delante ni recirculación a los lados, y a 5 H la estela ha desaparecido por construcción. La literatura señala estos mismos puntos débiles.

## La planta (`prueba_planta.py`, a 3 m del suelo, ±300 m, 2,5 m × 1,25 m, 3,6 M celdas)
- **Tiempo:** ~10 s por dirección. Una biblioteca de 36 direcciones, unos 6 min en este PC.
- **Alcance del cambio de más del 20 % o 20° desde el edificio más cercano:** NO 53 m (máx. 76), S 50 (69), O 38 (56), SE 28 (43). ⚠️ Lo limita la fórmula (3 veces la cavidad): probablemente corto.

| Distancia al edificio | Cambio de velocidad, P90 | Giro, P90 | Celdas con más de 20 % o 20° |
|---|---|---|---|
| 0-25 m | 62-80 % | 20-50° | 21-32 % |
| 25-50 m | 2-5 % | 2-3° | 1-5 % |
| 50-100 m | ≤ 1 % | ≤ 1° | ≤ 0,5 % |

- **Resolución** (frente a 2,5 m, viento del NO, a menos de 50 m): 5 m, 3 % del viento de entrada y 2,4° (P90); 10 m, 10 % y 5,6°, y deja de ver 4 de los 13 obstáculos. Usar 2,5 m, o 5 m si hace falta velocidad.
- **Relieve:** poco (1,2 % y 2,1° a menos de 150 m, con 14,8 m de desnivel).
- **Olivos** (dosel de Cionco con a = 1,5, supuesto): −13 % dentro del olivar y casi nada en la zona despejada. ⚠️ Sin medir: el valor real puede ser otro.

## Lo que este modelo no hace
1. **Noches estables y calmas:** solo es neutro, y es cuando suele haber más olor.
2. **Dirección de entrada:** hereda los ~30° de error de `viento3d`. El detalle no corrige eso: hace falta un anemómetro en la planta.
3. **Concentraciones:** `puffs` no puede usar este campo. Para eso haría falta un modelo local de dispersión.
4. **Validación real:** ni una medida de la planta. Los propios sensores servirán para comprobarlo.

## Repetir
```
python -I lib/galera/gui/tareas/lidar_planta.py <carpeta .laz> <librerías con laspy y lazrs> <TEMP>\…\planta_1m.npz 286796 4507414 400
python prueba_cubo.py
python prueba_planta.py
```
Salida: `resultados_cubo.json`, `resultados_planta.json` e imágenes `planta_*.jpg`.

## Pasó a la herramienta, solo para enseñar
Decisión del usuario, el mismo día: «más visual que preciso, para que el cliente vea que la presencia de los edificios tiene
influencia en el viento». El mapa tiene ahora dos motores: la zona (`viento3d`) y la planta (`lib/galera/viento/local.py`, con la biblioteca
`gui/planta/viento_local.npz`). Detalle en `CLAUDE.md`, «Dos motores de viento en el mapa». La prueba sigue valiendo para saber sus límites;
en la app, el campo va relativo al viento sin edificios a 3 m, así que no da la velocidad real a 3 m.
