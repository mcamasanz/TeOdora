# Historial de versiones

Formato basado en [Keep a Changelog](https://keepachangelog.com/es-ES/1.1.0/); versionado
semántico.

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
- Línea de órdenes común `python -m lagaus <motor>`.
- El código en la carpeta `core/`, instalado e importado como `lagaus`.
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
