# `odora.terreno` — terreno, superficie y edificios

Todo lo que describe el **suelo** sobre el que se dispersa la emisión: la cota y la forma del
relieve, las propiedades de la superficie, los edificios que generan estelas y la malla
geofísica que necesita el campo de viento 3D.

| Carpeta | Qué hace | Equivale a | Lo usa |
|---|---|---|---|
| [`relieve/`](relieve/README.md) | cota de receptores y fuentes y altura de colina, desde un MDT | AERMAP | `dispersion.penacho` (vía RE y SO) |
| [`superficie/`](superficie/README.md) | rugosidad z0, Bowen y albedo por sector y periodo, desde el uso del suelo; adaptador CORINE | AERSURFACE | `meteo.capa_limite` |
| [`edificios/`](edificios/README.md) | dimensiones del edificio que afecta a cada chimenea en 36 direcciones y altura GEP | BPIPPRM | `dispersion.penacho` (estela PRIME) y `dispersion.puffs` |
| [`geofisica/`](geofisica/README.md) | uso dominante y propiedades de superficie ponderadas por celda, y cota media; adaptador CORINE | MAKEGEO | `meteo.viento3d` |

## Flujo típico

```
MDT (GeoTIFF) ───────────────► relieve ──────► receptores con cota y colina ─► penacho
CORINE ─► superficie.corine ─► superficie ───► z0, Bowen, albedo ─────────────► capa_limite
edificios + chimeneas ───────► edificios ────► dimensiones por dirección ─────► penacho / puffs
CORINE + MDT ─► geofisica.corine ─► geofisica ─► GEO.DAT ─────────────────────► viento3d
```

## Ejemplo: el terreno de un caso en cuatro órdenes

```bash
python -m odora relieve aermap.inp aermap.out          # receptores y fuentes con cota
python -m odora superficie control.inp                 # características de superficie
python -m odora edificios bpip.inp bpip.out bpip.sum   # dimensiones de edificio
python -m odora geofisica geo.inp                      # GEO.DAT para el campo de viento
```

Cada motor es independiente: se puede usar solo el que haga falta.
