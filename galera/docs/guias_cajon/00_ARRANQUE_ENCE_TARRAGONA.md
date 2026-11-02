# Arranque del proyecto ENCE Tarragona: olores de compostaje en planta de biometano

> **Para quién:** quien monte la herramienta nueva, sea una persona o una IA. Supone que conoces
> CIERZOFLOW por encima. Aquí está lo que **cambia** respecto a Lleida y lo que se reutiliza tal cual.
> Fecha: 2026-10-14. Base: CIERZOFLOW en `main` (commit e8bdc36 y cambios posteriores sin commit).

---

## 1. Qué se reutiliza tal cual (≈ 80 % del trabajo)

| Pieza | Dónde está | Estado |
|---|---|---|
| Terreno (MDT05 por WCS, CORINE, Catastro por WFS) | `codigo_base/getMDT.py`, [guía 02](guias/02_datos_de_entrada.md) | Probado en toda la península (salvo Catastro en Navarra y País Vasco) |
| Meteo reanálisis ERA5 y predicción GFS | `codigo_base/getMeteo.py`, `getForecast.py` | Probado |
| Cadena AERMOD sin AERMET (`.sfc`/`.pfl` desde ERA5) | `codigo_base/getAermod.py`, [guía 03](guias/03_aermod_receta_y_errores.md) | 0 errores y 0 avisos; validado contra el modelo de un colega (≤ 7,5e-6) |
| Cadena CALMET → CALPUFF | `codigo_base/getCalpuff.py`, [guía 04](guias/04_calmet_calpuff_receta_y_errores.md) | Funciona en reanálisis y predicción |
| Pilas de compostaje: catálogo, tipos, volteos y configurador | `codigo_base/pilas.py`, `app2.py`, `plantillas/` | El caso de 17 pilas de Gimenells |
| Malla anidada y cálculo en paralelo | `utilidades/malla_receptores.py`, `paralelo_exe.py` | Probado |
| P98 sobre horas válidas, escalas de olor, mapas | `utilidades/postfile_aermod.py`, `raster_overlay.py`, [guía 06](guias/06_olores_emisiones_criterios.md) | Probado |
| App PySide6, mapas Leaflet, animación, capa de viento | `codigo_base/app.py`, `src/web/viento_calmet.js`, [guía 07](guias/07_mapas_web_leaflet.md) | Probado |
| Bibliografía de compostaje y normativa | `referencias/bibliografia/` | Revisado en julio de 2026 |

---

## 2. Lo que CAMBIA en Tarragona y hay que resolver antes de simular

### 2.1 Huso UTM: la herramienta tiene fijado el 30 🔴

`getAermod.CRS_UTM`, `getCalpuff.CRS_UTM_C` y `getMDT` usan **EPSG:25830** sin parámetro. En
Tarragona (unos 1,2° E), la cuadrícula del huso 30 está **girada +2,8°** respecto al norte geográfico.

- **AERMOD:** toma la dirección del viento del `.sfc` respecto al eje Y de los receptores.
  `write_sfc_pfl` no corrige ese giro, así que el penacho sale girado 2,8°. A 7 km son **unos 340 m de
  desvío lateral**. En Lleida eran 2,2° (270 m), y tampoco se corrigió.
- **CALMET:** recibe la latitud y longitud de cada celda y gestiona bien el giro.

**Recomendación:** convertir el EPSG en un parámetro, una única constante, y trabajar en el **huso 31
(EPSG:25831)**, donde el giro es de −1,15°. La otra opción es mantener el 25830 y girar la dirección al
escribir el `.sfc` con `utilidades/geo_utm.py → dir_geo_a_rejilla()`.

Cuidado en `getCalpuff.write_geo_dat(zone=30)` y en las cabeceras del 3D.DAT y del CMET.INP: el huso
aparece escrito como texto. El MDT del CNIG se sigue pidiendo en 25830 y se reproyecta.

### 2.2 Emplazamiento costero: brisa marina 🟠

- **Brisas de mar y tierra:** el viento rola a lo largo del día y lo emitido de madrugada puede volver
  a la planta. Es el caso en que AERMOD, que asume estado estacionario, peor encaja. En la tabla de
  decisión de `referencias/guias_proyecto/user_guide.md`, «brisas que cambian de sentido» lleva a
  **CALPUFF**. En Lleida medimos que, en un episodio con calmas, **el 51 % de la exposición que ve
  CALPUFF ocurre en horas que AERMOD descarta**.
- **ERA5 a 31 km mezcla tierra y mar.** El punto más cercano puede ser casi todo mar: flujo de calor
  bajo, capa de mezcla rara y z0 marino. Comprobar la máscara tierra-mar (`lsm`) del punto ERA5. Si es
  mar, usar el punto de tierra más cercano o contrastar con ERA5-Land, que es solo tierra, y con una
  estación AEMET cercana (Reus aeropuerto o la de Tarragona).
- **El mar dentro del dominio:**
  - CORINE 523, mar y océano, ya se traduce a agua: NLCD 11 en AERMOD y 55 en CALMET.
  - Falta por comprobar qué devuelve el WCS del MDT05 sobre el mar (¿nodata o 0?) y que AERMAP no
    aborte con receptores sobre el agua.
  - En los sectores de viento que vienen del mar, z0, Bowen y albedo cambian mucho. Esto ya se calcula
    por sectores, pero conviene revisar el resultado.

### 2.3 La planta es distinta: biometano + compostaje 🟠

Una planta de biometano no es una nave de pilas. Antes de dibujar fuentes hay que pedir al cliente la
lista de focos y decidir cómo se representa cada uno. Ver la tabla A.1 de
`referencias/bibliografia/olores/compostaje.md`.

| Foco probable (a confirmar con ENCE) | Cómo se modeliza | Qué pedir |
|---|---|---|
| Recepción y descarga de residuos | AREA; si va a extracción, POINT/VOLUME | Horario de descargas (EMISFACT HROFDY) |
| Pretratamiento y triturado | AREA pequeña o VOLUME | Horario |
| Digestores (cerrados) y gasómetro | Normalmente no emiten olor salvo venteos | Venteos y válvulas de seguridad |
| Almacenamiento y separación de digestato | AREA o AREAPOLY | Superficie, si está cubierto |
| **Compostaje del digestato o la fracción sólida** | AREA por pila, alineadas con su eje | Medidas, altura, volteos y su **duración** |
| Biofiltro | AREA (sale a temperatura ambiente, menos de 1 m/s) | Superficie, caudal y concentración a la salida (ou_E/m³) |
| Antorcha, upgrading, motores | POINT | Chimeneas con alto, diámetro, temperatura y velocidad |
| **Fugitivas de la nave** (puertas, muelles) | AREA o VOLUME | Estanqueidad. La guía de la Generalitat dice que el 10 % de fugitivas equivale al residual de un biofiltro al 90 % |

**Las pilas se reutilizan tal cual**: `pilas.py` con su catálogo, tipos, horas de volteo y perfil de
24 factores, y `app2.py` como configurador. **Ojo con las unidades**, que ya costaron dos errores
gordos (guía 06): el flujo va por m² y en g/s·m², y el factor de conversión debe acompañar a la fuente.

### 2.4 Normativa: Cataluña 🟡

- **No hay ley autonómica de olores aprobada.** El anteproyecto catalán de 2005/2015 nunca salió.
  Fuente: `referencias/bibliografia/normativa/marco_normativo_ES_UE.md` §D.4.
- **Modelo de ordenanza de la Diputació de Barcelona** (BOPB 29-04-2024): 5 ou_E/m³ en 30/60 min.
  Mirar si el municipio de la planta tiene ordenanza.
- **Criterio que usa CIERZOFLOW:** P98 de picos horarios con factor pico-media 2,3, según el decreto
  italiano 309/2023, en clases de 1 a 5 ou_E/m³. Para compostaje de verde la bibliografía usa 3 ou_E/m³
  P98, y 1,5 si el residuo no es vegetal.
- **Hay que fijar el criterio con el cliente y dejarlo escrito antes de simular.** Si el residuo es
  digestato y no verde, el umbral más exigente (1,5) puede aplicar.
- La **guía sectorial de compostaje de la Generalitat** trae factores de emisión por fase. Está citada
  y resumida en `compostaje.md`.

### 2.5 Licencias, si se va a entregar software a ENCE 🔴

Ver [guía 10](guias/10_licencias_y_precios.md).

- **CALPUFF no se puede redistribuir** sin permiso escrito de Lakes Environmental.
- **El satélite de Esri** exige cuenta en un producto comercial.
- El modelo de IA **qwen2.5:3b no admite uso comercial**.

Si a ENCE se le entrega un **estudio**, un informe con resultados, no hay problema. Si se le entrega la
**herramienta**, hay que resolver los tres puntos antes.

---

## 3. Plan de arranque sugerido

1. **Repositorio nuevo** con `codigo_base/` como punto de partida, sin `src/config/keys`. Cada usuario
   pone sus propias claves del CDS y de AEMET.
2. **Parametrizar el huso** (§2.1). Hacer una prueba corta y comprobar que el penacho de un foco con
   viento constante sale en la dirección esperada.
3. **Terreno de Tarragona** a 15–20 km. Revisar el mar en el MDT, en CORINE y en AERMAP.
4. **Meteo:** ERA5 de un año con la máscara tierra-mar revisada (§2.2) y su rosa contrastada con AEMET.
5. **Fuentes:** lista de focos con el cliente (§2.3). Primero en ou_E con un factor documentado; luego
   la conversión a g/s·m², revisada con `utilidades/olor_fuentes.py`.
6. **Reanálisis con AERMOD y CALPUFF** sobre el mismo periodo y los mismos receptores. Comparar el P98
   en las zonas urbanas.
7. **Criterio y escenarios:** normal, volteo, avería del biofiltro y fugitivas.
8. **Predicción** a 1–3 días con GFS y CALPUFF, si el cliente la quiere.

## 4. Preguntas abiertas para el cliente

- ¿Estudio (informe) o herramienta (software)? Cambia el capítulo de licencias.
- ¿Qué residuo entra a compostaje: digestato, fracción sólida o restos verdes? Cambia el factor de
  emisión y el criterio (1,5 o 3 ou_E/m³).
- ¿Hay olfatometrías (UNE-EN 13725) de los focos? Si no las hay, se usan factores bibliográficos,
  con su incertidumbre.
- ¿Duración real del volteo? Un pico de 20 minutos promediado en la hora no es lo mismo que una hora
  entera a pico.
- ¿Receptores sensibles concretos (urbanizaciones, colegios) además de los núcleos CORINE?
