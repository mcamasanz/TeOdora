# `lagaus.meteo` — meteorología

Convierte los datos meteorológicos (observaciones, sondeos, pronósticos) en lo que necesitan los
modelos de dispersión: los **parámetros de capa límite** del punto para el penacho y el **campo de
viento 3D** de todo el dominio para los puffs.

| Carpeta | Qué hace | Equivale a | Lo usa |
|---|---|---|---|
| [`capa_limite/`](capa_limite/README.md) | u\*, L, w\*, alturas de mezcla y perfiles a partir de observaciones de superficie, sondeos y estación propia | AERMET | `dispersion.penacho` (`.sfc`, `.pfl`) |
| [`viento3d/`](viento3d/README.md) | viento 3D ajustado al terreno con pronóstico y observaciones, y micrometeorología por celda | CALMET | `dispersion.puffs` (CALMET.DAT) |

## Flujo típico

```
observaciones + sondeo + superficie ─► capa_limite ─► .sfc + .pfl ─────────► penacho
pronóstico 3D + GEO.DAT (+ estaciones, boyas, pluviómetros) ─► viento3d ─► CALMET.DAT ─► puffs
```

## Ejemplo

```bash
python -m lagaus capa_limite aermet.inp       # escribe el .sfc y el .pfl
python -m lagaus viento3d CMET.INP            # escribe el CALMET.DAT
```

```python
from lagaus.meteo.viento3d import fichero_viento
cab, horas = fichero_viento.leer("CALMET.DAT")
print(cab.nx, cab.ny, cab.nz, len(horas))     # tamaño de la malla y horas escritas
```
