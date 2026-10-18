# Arquitectura y convenciones

## Organización

- El código está en la carpeta **`core/`** y se instala e importa como **`odora`**
  (`pyproject.toml`: `package-dir = {"odora" = "core"}`). Así, `core/dispersion/penacho/` es el
  módulo `odora.dispersion.penacho`.
- Un **paquete por motor**, agrupado por uso: `terreno`, `meteo`, `dispersion`. Los motores no se
  importan entre sí: se comunican por ficheros (los mismos formatos que los programas de
  referencia), así que cada uno se puede usar, probar y sustituir por separado.
- Cada motor tiene un **punto de entrada** con la misma firma que el programa original
  (`principal.ejecutar` o `__main__.main`) y se lanza desde la línea de órdenes común
  `python -m odora <motor>`.
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

## Cómo añadir o ampliar un motor

1. Escribir o traducir el código en el laboratorio y validarlo allí frente al original, con su
   batería de casos.
2. Regenerar el paquete con la herramienta del laboratorio (renombrado automático con el
   analizador de Python).
3. Volver a pasar las baterías sobre `odora`.
4. Regenerar los README.
5. Anotar el cambio en `CHANGELOG.md` y retirar lo hecho de `PENDIENTES.md`.
