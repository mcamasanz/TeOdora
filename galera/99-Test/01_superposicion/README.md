# 01 · Superposición de respuestas unitarias (alcance 1)

## Qué se quiere saber
Si el escenario de varios focos, cada uno con su perfil de 24 h y con olor y gases, se puede
obtener **sin volver a simular**, sumando respuestas unitarias calculadas una vez:

    C_especie(t, r) = Σ_foco Σ_h  q(foco, especie) · perfil(foco)[h] · R(foco, h)(t, r)

donde R(foco, h) es la concentración que produce el foco con emisión 1 emitida solo en la hora h
del día. Y si las 24 respuestas de un foco salen de UNA corrida con 24 «especies» de cálculo
(H00…H23, cada una emitida solo en su hora: IVARY = 1), y a qué coste.

## Cómo se corre
    C:\e2s\python.exe 99-Test\01_superposicion\prueba_superposicion.py
- `control_multiple.py`: control de odora puffs con varias especies, chimeneas y áreas, y perfil
  de 24 h por foco y especie (prototipo que amplía `odora.preparacion.puffs`, v0.1.2).
- Viento: las 48 h que hay en local (serie `odora_gfs_8est`, 2026-10-20/21); 42 h desde las 06
  del 20. Receptores: la malla de la planta sin viviendas (8 011). Focos INVENTADOS:
  - PILAS: área 60 × 12 m, 2,5 m, olor 3 ou_E/(s·m²) y NH3 2·10⁻⁵ g/(s·m²), volteos 08-10 y 15-17
    (1,0) y 0,2 el resto;
  - BIOFILTRO: área 30 × 20 m, 1 m, olor 1,5 ou_E/(s·m²), NH3 10⁻⁶ g/(s·m²), 1,0 de 06 a 22 y
    0,5 de noche;
  - CHIMENEA: 12 m, Ø 0,5 m, 10 m/s, 400 K, olor 2 000 ou_E/s, NH3 0,01 g/s, constante.
- Casos pesados en `%TEMP%\ence_galera\99-Test\01_superposicion` (≈ 200 MB).

## Resultado (2026-10-24)
| | Directo (A) | Superposición (B) |
|---|---|---|
| Olor, máximo | 3,244 ou_E/m³ | igual; máx. \|Δ\| = 4·10⁻⁸ del máximo |
| NH3, máximo | 2,16·10⁻⁵ g/m³ | igual; máx. \|Δ\| = 1,5·10⁻⁸ del máximo |
| Receptor·horas con \|Δ\|/valor > 10⁻⁴ | — | **0 de 336 462** (olor y NH3) |
| Suma de las 24 respuestas frente a emisión constante | — | ≤ 1·10⁻⁷ (los 3 focos) |

**La superposición es EXACTA** (las diferencias son de redondeo en reales de 4 bytes), también
para la chimenea, con su sobreelevación: el perfil cambia la masa, no la subida del penacho.

Coste (cada corrida en un proceso, 8 011 receptores, 42 h):

| Corrida | Tiempo | Memoria máx. | Fichero de concentraciones |
|---|---|---|---|
| Escenario directo (3 focos, 2 especies) | 67 s | 389 MB | 3,2 MB |
| 1 foco, 24 especies (las 24 respuestas) | 38-40 s | 415 MB | 3,5-3,8 MB |
| 1 foco, 1 especie | 22-25 s | 330-410 MB | 2,7-2,8 MB |

- Las **24 respuestas de un foco cuestan 1,6-1,8 veces una corrida normal**, no 24 veces.
- El fichero de concentraciones casi no crece con 24 especies (casi todo son ceros y va
  comprimido).
- La memoria es sobre todo el viento: ≈ 2,3 veces el fichero de viento (48 h ≈ 170 MB).

## Lo que se deduce para los 5 años (ESTIMACIÓN, a medir con un mes real)
- Tiempo: 0,9 s por hora simulada y foco (24 especies) → 43 824 h ≈ 11 h de un proceso por foco;
  con el equipo entero (rinde ≈ 3 veces un proceso) unas 4 h por foco. Se calcula UNA vez por foco;
  solo se repite si cambian su geometría, altura, velocidad o temperatura de salida.
- Disco: ≈ 90 kB por hora y foco → ≈ 4 GB por foco para los 5 años (8 011 receptores).
- Memoria: un mes de viento (2,7 GB) pediría ≈ 6 GB por proceso: trocear por semanas (≈ 1,4 GB).
- Después, cualquier escenario (subir o bajar emisiones, mover operaciones de hora, otro perfil)
  es una suma ponderada de esas series, sin motor: segundos o minutos.

## Pendiente
- Troceo por semanas con arranque: medir con un mes real que el corte no cambia el resultado
  (necesita la serie de 5 años, en Z:).
- Pasar el control de varias especies, chimeneas y perfiles a odora (`preparacion.puffs`) con sus
  pruebas.
