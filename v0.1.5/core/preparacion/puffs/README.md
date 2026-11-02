# `teodors.preparacion.puffs` — casos de puffs

<!-- manual -->
## Qué hace

Escribe el fichero de control de `dispersion.puffs` desde cero (solo asignaciones) para el caso
más común de un estudio de olores: UNA especie sin química ni deposición, fuentes de ÁREA con
emisión constante y receptores discretos sobre un viento 3D ya calculado (`meteo.viento3d`), y lee
el fichero de concentraciones como fechas y matriz.

| Fichero del caso | Lo escribe / lee | Contenido |
|---|---|---|
| `puffs.inp` | `control.escribir` | control: periodo, malla, especie, fuentes de área, receptores |
| `viento3d.dat` | (`meteo.viento3d`) | viento 3D: la malla horizontal y vertical del control TIENE que ser la suya |
| `conc.dat` | `salida.concentraciones` | concentración por periodo y receptor (g/m³) |

## Uso

```python
import pandas as pd
from teodors.dispersion.puffs.principal import ejecutar
from teodors.preparacion.puffs import control, salida

pila = control.fuente_area("PILA1", vertices, 2.0, 98.0, q_g_s / area_m2)   # q POR m²
control.escribir(caso / "puffs.inp", malla, zface, pd.Timestamp("2024-07-01 00:00"), 744, 31,
                 [pila], receptores, especie="OLOR")
ejecutar(caso / "puffs.inp")
fines, conc = salida.concentraciones(caso / "conc.dat")      # (periodos, receptores), g/m³
```

⚠️ Las fuentes de área van en g/(s·m²) POR METRO CUADRADO. ⚠️ El periodo k lleva la fecha del
registro k del viento (hora FINAL): con el viento de un día que empieza a las 00, el primer periodo
es el de las 00.

⚠️ El motor solo aborta si NX y NY no coinciden con los del viento. NZ y ZFACE los toma del viento: medido, con otros en el control da el mismo resultado,
sin avisar. Aquí se escriben los del viento que se pasan.

## Varias especies y fuentes

`control_fuentes` escribe el control para lo que `control` no hace: varias especies, fuentes de área, punto y volumen, con un perfil de 24 h por fuente y especie, y
receptores con altura.

```python
from teodors.preparacion.puffs import control_fuentes as cf

fuente = {"id": "A1", "verts": vertices, "h": 2.0, "cota": 100.0}     # de una ficha de foco lo saca `operacion.focos.geometria`
fuente.update(q={"OLOR": q_por_m2}, perfil={"OLOR": perfil_de_24_factores})
cf.escribir(caso / "puffs.inp", malla, zface, ini, nhoras, zona, ["OLOR"], areas=[fuente], receptores=recs)
```

- **Unidades:** las del motor: en un área, POR m²; en un punto o un volumen, en total.
- **Respuestas:** el modelo es lineal, sin química ni deposición. Con una especie por hora del día, cada una emitida solo en su hora, la suma de las respuestas por
  un perfil cualquiera da la corrida directa con ese perfil, también con una chimenea con sobreelevación. Con el viento de `puffs/area_D` la diferencia es de
  7,5·10⁻⁸ del máximo. El factor h del motor va en el periodo cuyo FIN tiene hora h + 1, y el primer periodo emite la hora anterior a su inicio.
- ⚠️ Sin efecto de los edificios: no se pasan sus dimensiones al motor.

## Validación
Pruebas en `auditor/pruebas/unitarias/test_preparacion_puffs.py` y, las de `control_fuentes`, en `test_casos_planta.py`: el control se vuelve a leer con
`dispersion.puffs.entrada` (malla, fechas, especie, fuentes, receptores) y se lanza el motor sobre
el viento del caso de regresión `puffs/area_D`. En el proyecto de La Galera (2026-10-23) da la
misma secuencia de asignaciones que su escritor (plantilla + sustituciones) salvo los nombres de
las salidas de deposición y visibilidad, la misma configuración leída por el motor y el mismo
penacho bit a bit; el control pasa de 73 a 5 kB.
<!-- /manual -->

## Ficheros

| Fichero | Contenido | Viene de | Equivale a |
|---|---|---|---|
| `__init__.py` | Preparación de casos de `dispersion.puffs`. | — | — |
| `parametros.py` | Asignaciones de partida del control, en orden, con marcas para la especie, las fuentes de área y los receptores (generado; no se edita a mano). | proyecto La Galera | — |
| `control.py` | `fuente_area`, `preparar` / `escribir`: control del caso. | proyecto La Galera (`puffs.py`) | — |
| `control_fuentes.py` | `preparar` / `escribir`: control con varias especies y fuentes de área, punto y volumen, cada una con su perfil de 24 h. | proyecto La Galera (`gui/tareas/control_fuentes.py`) | — |
| `salida.py` | `fecha`, `concentraciones`: fin de cada periodo y matriz de una especie. | proyecto La Galera (`puffs.py`) | — |
