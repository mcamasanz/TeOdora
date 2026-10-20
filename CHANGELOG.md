# Historial de versiones

Formato basado en [Keep a Changelog](https://keepachangelog.com/es-ES/1.1.0/); versionado
semántico.

## [0.1.1] — 2026-10-20

Corrección de `meteo.viento3d` en las horas de transición (amanecer y atardecer) con relieve.

### Motivo
En un caso real de relieve complejo (La Galera, Montsià: 125×125 celdas de 400 m, cotas de 0 a
1 437 m, ERA5 en una columna, NOOBS = 2, ITPROG = 2), el viento a 10 m de la v0.1.0 se separaba de
calmet.exe 5.8.5 justo a las 06-07 y a las 19 UTC: |Δv| > 0,1 m/s en 767, 2 621 y 3 300 de las
15 625 celdas, sobre todo en ladera, con la clase de estabilidad cambiada en cientos de ellas. En
la cadena completa (viento3d + puffs, 24 h, 441 receptores) el P98 por receptor difería un 16 % de
media y hasta un 66 %. El resto del día coincidía, y `dispersion.puffs` con el MISMO fichero de
viento es idéntico a calpuff.exe: el problema estaba solo en viento3d. Los 51 casos de la batería
lo pasaban porque el criterio es la media de todas las horas y celdas, y los casos reales son de
llano (Lleida, Huesca), donde el bloqueo apenas actúa.

### Causa (medida como caja negra)
No era la clase de Turner: con su propio viento, cada programa reproduce su clase en el ~100 % de
las celdas. Con IFRADJ = 0 las diferencias desaparecen: venían del **bloqueo (Froude)**, que usa
una sola N para todo el dominio, y N depende de cómo se ajusta la temperatura a la capa de mezcla
justo cuando esta nace o se deshace. Tres reglas del original, cada una medida por separado:
1. **N del bloqueo**: temperatura de la hora SIN ajustar y T(ZUPT) adiabática solo donde la
   altura convectiva GUARDADA de la hora anterior (la promediada) llega a ZUPT. La v0.1.0 usaba la
   convectiva de la hora actual sin promediar. Con N forzada a las 07 UTC, el original usa 0,0061
   (mínimo neto: 15 celdas distintas frente a 1 444 con 0,0045 y 773 con 0,0072); la v0.1.0 daba
   0,0034.
2. **ψ de la convectiva** (solo ITPROG = 2): por debajo del primer nivel del pronóstico, θ de la
   temperatura 3D de la hora anterior (centros de capa, lineal y prolongada hasta el suelo) en vez
   de θ constante. Con el 975 hPa de ERA5 a ~100 m del suelo, la ψ de la primera hora convectiva
   salía 2-3 veces menor y su altura un 25-50 % mayor. En un caso llano y uniforme, con el LDB del
   original: Δθ 0,26 K frente a 0,17; ψ implícita 0,005184, calculada 0,005183.
3. **Temperatura 3D de salida**: ajustada con la altura convectiva YA promediada (IAVEZI), no con
   la de antes del promedio.

### Cambiado
- `meteo.viento3d.principal`: las tres reglas, con sus constantes de módulo para volver al
  comportamiento de la v0.1.0 si hiciera falta (`N_CON_ALTURA_ANTERIOR`, `N_MASCARA`,
  `PSI_DE_T3D`, `T3D_CON_PROMEDIADA`) y las funciones `_n_zupt` y `_theta_capas`. ITPROG = 0
  (sondeos) no cambia. La regla 2 no se aplica con ITPROG = 1: allí la capa 1 viene de las
  estaciones y empeoraba un caso con ICON-EU y 36 estaciones.
- README del motor, §Transiciones, con las medidas.

### Validación
| Caso (48 h, 24 de arranque) | celdas·hora \|Δv\| > 0,1 m/s | P98 por receptor, \|Δ\| medio (máx.) |
|---|---|---|
| ERA5, NOOBS = 2, ITPROG = 2 | 6 800 → **89** | 16,3 % (66 %) → **0,2 % (2 %)** |
| ICON-EU 10×10 + 36 estaciones, NOOBS = 1, ITPROG = 1 | 942 → **227** | 0,9 % (15 %) → **0,1 % (3 %)** |

Pruebas: 158 de 158 (5 nuevas en `test_viento3d_transiciones.py`); el caso de regresión
`viento3d/llano_lleida` sale idéntico byte a byte, sin cambiar ninguna referencia.

### Pendiente
- Volver a correr la batería de laboratorio de 51 casos de viento3d con la v0.1.1.
- La altura convectiva de la tarde se separa poco a poco del original (|ΔZI| relativo medio
  0,6 %) y, con ITPROG = 1 y estaciones, la ZI y la temperatura de día (2,3 %), igual que en la
  v0.1.0.

## [0.1.0] — 2026-10-18

Primera versión del núcleo: los ocho motores propios reunidos en un solo paquete, ordenados por
uso y con nombres propios.

### Añadido
- `terreno.relieve` (≡ AERMAP), `terreno.superficie` (≡ AERSURFACE, con adaptador CORINE),
  `terreno.edificios` (≡ BPIPPRM) y `terreno.geofisica` (≡ MAKEGEO, con adaptador CORINE).
- `meteo.capa_limite` (≡ AERMET) y `meteo.viento3d` (≡ CALMET), con estaciones de superficie,
  sondeos, costa (boyas, COARE, OCD), brisa, pluviómetros, O'Brien y efectos cinemáticos.
- `dispersion.penacho` (≡ AERMOD), con todas las fuentes salvo aeronaves, plataformas y HBP: química
  del NO2, deposición, RLINE, BUOYLINE, OPENPIT y SWPOINT; varios años y re-arranque (MULTYEAR,
  SAVEFILE, INITFILE), MAXDAILY, FASTAREA y FASTALL, y la mayoría de los volcados de DEBUGOPT.
  Núcleo compilado con numba generado desde el propio Python.
- `dispersion.puffs` (≡ CALPUFF), con áreas, volúmenes, chimeneas con sobreelevación, efecto
  edificio (ISC y PRIME), deposición seca y húmeda, malla de receptores, emisiones variables
  (PTEMARB, VOLEMARB) y dispersión MDISP 2, 3 y 4.
- Línea de órdenes común `python -m odora <motor>`.
- El código en la carpeta `core/`, instalado e importado como `odora`.
- README por carpeta con la definición y la equivalencia de cada función.
- **Auditor** (`python -m auditor`): reglas para entrar en `main` (pruebas que pasan, rápidas, con
  pruebas nuevas para el código nuevo, referencias justificadas, sin perder pruebas), 13 casos de
  regresión (todos los motores) contrastados con los programas originales, hook `pre-push` y flujo
  de GitHub Actions. La rapidez se mide con la caché de numba caliente.

### Validación
Cada motor se ha validado frente a su programa original con su batería de casos, 472 en total
(ver [docs/validacion.md](docs/validacion.md)). El código de esta versión es el de la traducción
validada, con los nombres nuevos. Las ocho baterías se han vuelto a correr sobre este paquete y dan
los mismos resultados que en el laboratorio.

### Pendiente
Ver [PENDIENTES.md](PENDIENTES.md).
