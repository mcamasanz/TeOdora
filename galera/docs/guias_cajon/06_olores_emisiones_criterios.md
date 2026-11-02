# 06 · Olores: unidades, emisiones, estadísticos y criterios

Bibliografía completa en `referencias/bibliografia/`:

- `olores/compostaje.md`: focos, factores de emisión, el caso AERMOD publicado y los errores típicos.
- `metodologia/olores_metodologia.md`: pico-media, percentiles y olfatometría.
- `normativa/`: normativa de España, la UE, Países Bajos e Italia.

## Unidades: la fuente de los dos peores errores del proyecto

- **1 ou_E/m³ es el umbral olfativo** (UNE-EN 13725). Los modelos solo entienden **masa**.
- Una fuente en ou_E necesita su **factor**: los µg/m³ que equivalen a 1 ou_E. Para H2S puro el factor
  es **0,571485 µg/m³ por ou_E**, con el umbral de 0,41 ppb de Nagata. Ojo: en la literatura el umbral
  del H2S va de 0,4 a 13 ppb (×30). En un expediente hay que escribir de dónde sale el factor.
- **AREA/AREAPOLY (AERMOD) y las áreas de CALPUFF piden g/(s·m²), es decir, POR m²**:
  `q = Q_total[g/s] / área[m²]`. Ejemplo de las pilas: 32 ou_E/(s·m²) × 0,571485 × 1e-6 =
  **1,8288e-5 g/(s·m²)**.
- Errores reales:
  - Se metió 234 «µg/s» como si fuera g/s·m² y el máximo salió en **49 millones de µg/m³**.
  - CALPUFF recibió el 32 sin convertir, porque se perdió el campo `factor`: **×1,75 millones**.

  **Comprueba siempre los dos `.inp`**, SRCPARAM y subgrupo 14b, con
  `utilidades/olor_fuentes.py` a mano.
- Conversión a ppm (25 °C, 1 atm): `ppm = µg/m³ · 24,45 / (M · 1000)`. La app muestra el H2S en ppm.

## Emisión de las pilas

- **Fuente de ÁREA por pila, alineada con su eje.** No conviene un único polígono que lo envuelva todo.
- **La altura de emisión es la decisión que más condiciona el resultado.** Ver `compostaje.md` §A.3.
  En las 17 pilas se usó 2 m.
- **Volteos:**
  - Se modelizan con un perfil de 24 factores (`EMISFACT HROFDY` en AERMOD, `IVARY=1` en CALPUFF,
    ojo al **desfase de 1 h** de CALPUFF, ver [04](04_calmet_calpuff_receta_y_errores.md)).
  - Si el volteo dura 20 minutos, **promédialo en la hora** (`perfil_volteo(..., duracion_min=20)`).
    Poner el pico la hora entera triplica la masa.
  - Volteos a las 7–9 h caen en el pico de calmas de la mañana, justo donde AERMOD anula horas.
- **Agrupar pilas** para CALPUFF: conservar **Q = Σ(flujo·área)**, no sumar flujos. Los rectángulos de
  CALPUFF tienen 4 vértices.
- `pilas.py` + `app2.py` (configurador): catálogo de pilas, tipos (flujo base y pico, horas de volteo)
  y escenario → `sources.json`.

## Estadísticos

- **P98 horario sobre HORAS VÁLIDAS** (calmas y huecos fuera). Es lo que hace
  `utilidades/postfile_aermod.estadisticos(df, horas_validas=...)`.
- ⚠️ El `concentraciones.csv` trae **una fila por receptor** con la media del periodo. Calcular un
  percentil sobre esa columna da un percentil *espacial entre receptores*: un número sin sentido con
  aspecto de resultado. El P98 sale de la **serie horaria** del POSTFILE o del `.lst` de CALPUFF.
- **Factor pico-media:** `getAermod.PEAK_FACTOR_OLOR = 2.3` forma parte del criterio italiano
  (D. MASE 309/2023), cuyo «1 ou_E/m³» ya lo presupone. El enfoque neerlandés no usa factor.
  **No mezcles umbral y factor de criterios distintos.**
- **En predicción no hay P98:** la media es sobre el periodo pronosticado y el máximo es horario.

## Criterios disponibles en el código (`getAermod.CRITERIO_OLOR_IT`)

Clases del decreto italiano, sobre el P98 de picos (×2,3):

| Clase | Umbral | Receptor |
|---|---|---|
| 1 | 1 ou_E/m³ | Residencial denso, hospitales, colegios |
| 2 | 2 ou_E/m³ | Residencial disperso, comercial |
| 3 | 3 ou_E/m³ | Casas dispersas; es la que usa la app por defecto en compostaje en campo abierto |
| 4 | 4 ou_E/m³ | Industrial, agrícola |
| 5 | 5 ou_E/m³ | Sin presencia ordinaria de personas |

Otras referencias para el compostaje:

- Canarias, Decreto 185/2025: 3/6/9 ou_E/m³ al P98.
- Bibliografía: 3 ou_E/m³ para compostaje de verde y 1,5 ou_E/m³ si el residuo no es vegetal.
- Ordenanza tipo de la Diputació de Barcelona: 5 ou_E/m³.

**En Cataluña no hay ley de olores aprobada.** Hay que acordar el criterio con el cliente.

## Representación (decisiones del usuario, ya implementadas)

- **Capas de resultados en reanálisis:**
  - H2S medio y máximo en ppm, en continuo y por bandas.
  - Olor medio y máximo con los mismos colormaps (turbo para el continuo, inferno para las bandas).
  - P98.
- **Escala de olor:** tope de 10 ou_E y bandas 0,001 · 0,5 · 1 · 2 · 3 · 5 · 10 (`OLOR_TOPE`,
  `OLOR_BANDAS`). Con `vmin` fijo en 0,001: si se toma el mínimo del dato, la escala del máximo
  arrancaba mal.
- **Iconos de núcleos CORINE:** casa azul (111/112), fábrica amarilla (121) y balón naranja (142).
- **Fichas por núcleo:** media, máximo y P98 por especie, olor y la **hora del máximo**.
- **Circunferencias negras** a 3/4, 1/2 y 1/3 del semilado del dominio, centradas en el punto.
- **«Dominio» es el LADO del cuadrado de cálculo, no un radio.** Ver [09](09_lecciones_aprendidas.md).
