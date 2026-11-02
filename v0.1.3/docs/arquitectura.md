# Arquitectura y convenciones

## Organización

- El código está en la carpeta **`core/`** y se instala e importa como **`teodors`**
  (`pyproject.toml`: `package-dir = {"teodors" = "core"}`). Así, `core/dispersion/penacho/` es el
  módulo `teodors.dispersion.penacho`.
- Un **paquete por motor**, agrupado por uso: `terreno`, `meteo`, `dispersion`. Los motores no se
  importan entre sí: se comunican por ficheros (los mismos formatos que los programas de
  referencia), así que cada uno se puede usar, probar y sustituir por separado.
- Cada motor tiene un **punto de entrada** con la misma firma que el programa original
  (`principal.ejecutar` o `__main__.main`) y se lanza desde la línea de órdenes común
  `python -m teodors <motor>`.
- La **sintaxis de los ficheros de control** y los **formatos de salida** son los del programa de
  referencia. Es lo que permite validar caso a caso y reutilizar las herramientas de posproceso.

## Motores traducidos (relieve, superficie, edificios, capa_limite, penacho)

Traducción fiel del Fortran, rutina a rutina:

- **Estado global**: un objeto `e` con las variables de los módulos del original en MAYÚSCULAS.
  Las matrices son numpy con índice desde 1, como en Fortran; las cadenas, `str` sin blancos
  finales.
- **E/S de formato fijo** (`formato.py`): lectura y escritura con descriptores Fortran (`fwrite`,
  `fread`), mismos redondeos y mismos ceros con signo que el compilador del original.
- **Peculiaridades replicadas a propósito**:
  - literales en precisión simple;
  - `NINT` con empates lejos del cero;
  - variables locales que conservan su valor entre llamadas;
  - reasociaciones del compilador donde cambian una decisión discreta;
  - reducciones vectorizadas.

  Cada caso está comentado en el código.
- **Tablas** (`tablas.py`): declaraciones, valores iniciales y mensajes extraídos del original con
  un script, nunca copiados a mano.

## Motores de sala limpia (geofisica, viento3d, puffs)

Escritos desde la documentación publicada (guías de usuario) y el comportamiento observado del
ejecutable original, usado como caja negra, sin abrir nunca su código. Cada regla no documentada
se dedujo con experimentos dirigidos. Su procedencia está en el repositorio de laboratorio.

## Núcleo compilado (numba)

- `dispersion.penacho.nucleo` **genera** `_nucleo_gen.py` a partir de las funciones Python de
  referencia, con transformaciones mecánicas:
  - escalares del estado en un registro numpy y matrices en un `structref`;
  - cadenas convertidas en códigos;
  - mensajes de error convertidos en eventos que se reproducen después en orden.

  La vía compilada y la Python dan resultados idénticos bit a bit (`AERMOD_NUMBA=0` fuerza la
  Python).
- `dispersion.puffs.nucleo`, `terreno.edificios.gep_rapido` y otros usan numba directamente.
- La primera corrida compila y guarda la caché junto al código. Por eso la carpeta del paquete
  tiene que ser escribible.

## Precisión

- Los ficheros de texto salen idénticos al original, salvo empates (valores iguales en todas las
  cifras impresas que se ordenan distinto) y valores en la frontera de redondeo de la última cifra.
- Los binarios difieren en los últimos bits (mediana ~1e-15 relativo). La libm del original lleva
  FMA y está compilada con reasociación. Ni las funciones correctamente redondeadas lo eliminan.

## Utilidades (no son motores)

Desde la v0.1.2 hay también código que no reproduce ningún programa: coordenadas (`comun`), el
almacén del viento (`meteo.viento3d.almacen`), la preparación de casos (`preparacion`: entradas y
control escritos desde cero, solo con asignaciones) y, por partes, las fuentes de datos. No se traduce ni se valida frente a un original: se escribe directamente en este
repositorio, con sus pruebas unitarias (regla R4 del auditor), y se valida frente al proyecto del
que viene (mismos resultados bit a bit en el proyecto de La Galera).

`meteo.viento_local` es un caso aparte: tampoco es un motor, pero además **no está validado**. Solo enseña el efecto de los edificios
en el viento: no da valores para un sensor y `dispersion.puffs` no lo usa. No está en `MOTORES` ni se lanza con `python -m teodors`,
y no importa `teodors.planta`: lo propio de cada sitio llega por parámetro.

`fuentes` (descargas) sí usa `teodors.planta`: no es un motor y su trabajo es llenar la carpeta de DATOS de una planta. Importarlo no la
lee, y lo opcional se carga al usarlo. Las URL de los servicios están en el código y son de España, salvo ERA5 y GFS: ver su
[README](../core/fuentes/README.md).

`metricas` (validación del viento frente a las estaciones) también usa `teodors.planta` y `teodors.fuentes`, y tampoco los lee al
importarse: ver su [README](../core/metricas/README.md).

`casos` une la carpeta de una planta, sus datos y los motores, y es el único sitio donde se juntan: `preparacion` y los motores no pueden
importar `teodors.planta` (lo comprueba una prueba). Lo que no necesita planta, como el control de puffs con varias especies y fuentes, va
a `preparacion`: ver su [README](../core/casos/README.md).

`operacion` va encima de todo eso y no necesita interfaz: focos, planes, normativa, periodos y la simulación, que suma las respuestas de los focos sin lanzar el motor. Lo
que lanza procesos lo hace como `python -m teodors.operacion.<tarea>`: el hijo hereda la planta por `TEODORS_PLANTA`. Ver su [README](../core/operacion/README.md).

`gui` es la aplicación de escritorio de una planta, en PySide6, con el mapa en una página web. Va encima de `operacion`, `fuentes`, `casos` y `metricas`, y nada fuera de este paquete carga Qt ni folium: quien no instale el extra `gui` no los hereda (lo comprueba una prueba). Lo de cada sitio (nombre, ajustes, créditos, fondos del mapa…) sale de `planta.json`: ver su [README](../core/gui/README.md).

`mos` (corrección estadística de la predicción de GFS en cada estación) también usa `teodors.planta` y `teodors.fuentes`, no es un motor ni entra en `MOTORES`, y su mejora de dirección es
local a la estación: ver su [README](../core/mos/README.md).

## Cómo añadir o ampliar un motor

1. Escribir o traducir el código en el laboratorio y validarlo allí frente al original, con su
   batería de casos.
2. Regenerar el paquete con la herramienta del laboratorio (renombrado automático con el
   analizador de Python).
3. Volver a pasar las baterías sobre `teodors`.
4. Regenerar los README.
5. Anotar el cambio en `CHANGELOG.md` y retirar lo hecho de `PENDIENTES.md`.
