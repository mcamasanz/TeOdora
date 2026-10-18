# `lagaus.dispersion` — modelos de dispersión

Los dos modelos que dan nombre a la herramienta (LAGrange + GAUSS):

| Carpeta | Qué hace | Equivale a | Cuándo usarlo |
|---|---|---|---|
| [`penacho/`](penacho/README.md) | penacho gaussiano estacionario: convectiva bi-gaussiana, estable, meandro, terreno complejo, estelas, urbano, química del NO2, deposición | AERMOD | estudios regulatorios horarios (P98, máximos), terreno moderado, muchas fuentes y receptores |
| [`puffs/`](puffs/README.md) | puffs gaussianos que viajan con el viento 3D, con memoria entre horas | CALPUFF | calmas, recirculaciones, costa y brisas, viento muy variable en el dominio |

## Entradas que reciben

```
penacho ◄── .sfc + .pfl (meteo.capa_limite) + receptores con cota (terreno.relieve)
            [+ dimensiones de edificio (terreno.edificios), emisiones horarias, fondo, ozono]
puffs   ◄── CALMET.DAT (meteo.viento3d) + fuentes y receptores del fichero de control
            [+ dimensiones de edificio (terreno.edificios)]
```

## Ejemplo: las mismas fuentes con los dos modelos

```python
from lagaus.dispersion.penacho.principal import ejecutar as penacho
from lagaus.dispersion.puffs.principal import ejecutar as puffs

penacho(["penacho/caso.inp", "penacho/caso.out"])       # concentración por receptor y hora
cab, periodos = puffs("puffs/CALPUFF.INP")              # ídem, con el viento 3D
```

Las salidas tienen el mismo formato que las de los programas de referencia, así que sirven las
mismas herramientas de posproceso.
