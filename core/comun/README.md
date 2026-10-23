# `odora.comun` — utilidades comunes

<!-- manual -->
## Qué hace

Utilidades que no son motores ni equivalen a ningún programa, comunes a los motores y a los
proyectos que usan odora.

## Uso

```python
from odora.comun import geo
x, y = geo.a_utm(40.6905923, 0.4764197)                  # huso de la longitud (EPSG:25831)
g = geo.convergencia_deg(40.6905923, 0.4764197, "EPSG:25831")   # −1,65°
wd_rejilla = geo.dir_geo_a_rejilla(350.0, 40.69, 0.476, "EPSG:25831")
vertices, ext = geo.cuadrado_utm(40.69, 0.476, 50.0)     # dominio de 50 km alineado con el UTM
```

⚠️ En un dominio, todos los puntos tienen que usar el MISMO `epsg`: fíjalo una vez y pásalo
siempre (si no, dos puntos a ambos lados de un límite de huso caerían en husos distintos).

## Validación
Pruebas en `auditor/pruebas/unitarias/test_comun_geo.py`, con los valores de control de La Galera
(Montsià) medidos con pyproj en el proyecto: UTM 31 (286 763, 4 507 474) m, γ = −1,65° en
EPSG:25831 y +2,26° en EPSG:25830.
<!-- /manual -->

## Ficheros

| Fichero | Contenido | Viene de | Equivale a |
|---|---|---|---|
| `__init__.py` | Utilidades comunes a los motores y a los proyectos. | — | — |
| `geo.py` | Huso y EPSG del UTM, ida y vuelta de coordenadas, convergencia de meridianos, giro del viento a la cuadrícula, distancia y rumbo, desvío lateral, cuadrados de dominio. | proyecto La Galera (`geo.py`) | — |
