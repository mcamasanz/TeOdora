# Gimenells

Planta de compostaje en pilas en **41,61854 N, 0,34222 E** (huso 31, EPSG:25831). Viene del proyecto DIGICOMPOST, que la sitúa en Gimenells
(Lleida), pero según el Catastro está al otro lado del límite: polígono 7, parcela 205, paraje Moncalvo, **Zaidín (Huesca)**. La versión de teOdors
que usa está en [`VERSION`](VERSION).

⚠️ **Las emisiones de las pilas son provisionales** (ver abajo): lo que se calcule con ellas prueba la herramienta, pero no es un resultado.
La serie de viento de 5 años aún no existe: el reanálisis repite el día de prueba, el 21 de octubre de 2026.

## Abrir la aplicación

```bash
python main.py                  # modo operario: consulta los focos y crea planes de operación
python main.py --circe          # además, añade y cambia focos
```

También `--dia AAAA-MM-DD`, `--focos` y `--planes`.

## Datos de entrada: `entrada/`

| Qué | Dónde | De dónde sale |
|---|---|---|
| Identidad, huso, dominio de 50 × 50 km, malla de receptores, estaciones (VH, VK, XY, XN de Meteocat) | `planta.json` | plantilla de teOdors |
| Coordenadas de la nave | `emplazamiento.json` | dadas por CIRCE (2026-11-03) |
| Cotas, a 25 m | `terreno/41.61854_0.34222_50km_25m/elevacion.tif` | MDT del IGN |
| Usos del suelo | `terreno/…/usos.tif`, `terreno/…/corine.gpkg` | CORINE Land Cover 2018, recortado y pasado a rejilla |
| Núcleos de población | `terreno/…/nucleos_nombres.json` | CORINE, con los nombres de CartoCiudad |
| Edificios a menos de 2 km | `edificios/41.61854_0.34222_r2km/edificios.gpkg` | Catastro: solo huella, uso y plantas |
| Las 30 pilas de la nave, P01 a P30 | `focos.json` | catálogo de pilas de DIGICOMPOST (ver abajo) |
| Plan de operación «Operación normal» | `planes/operacion_normal.json` | el volteo mensual (ver abajo) |
| Receptores con nombre: Gimenells (5,4 km al NE), Santa Maria de Gimenells (6,6 km) y el Pla de la Font (7,7 km al N) | `receptores.json` | centros de población de CartoCiudad |
| Viento alrededor de los edificios | `viento_local/viento_local.npz` | calculado con `viento_local/planta_1m.npz`, del LiDAR del ICGC (teselas 278610 y 278611). ⚠️ No validado: solo enseña el efecto de los edificios |
| Ejemplo de la ventana de configuración | `recursos/ejemplo/` | una hora de viento y de penacho del día de prueba. No es un resultado |
| Ortofoto del visor 3D | `recursos/visor3d/ortofoto.jpg` | PNOA, ±3,2 km |

Sin `normativa.json` propio: vale la plantilla nacional de teOdors (RD 102/2011). Los tres pueblos del municipio son receptores con nombre porque
CORINE no los ve como zona residencial (su unidad mínima son 25 ha), y sin ellos la tabla de la simulación solo tendría núcleos de Aragón y de más lejos.
Las viviendas del Catastro a menos de 2 km, que también son receptores, son una sola.

## Las pilas

El número de cada pila de DIGICOMPOST es el de su foco: la pila 7 es `P07`.

| Clase | Pilas | Tamaño | Altura |
|---|---|---|---|
| L70 | 1 a 5 | 70 × 7 m | 3,5 m |
| L40 | 6 a 28, las pares | 40 × 7 m | 3,0 m |
| L50 | 7 a 29, las impares, y la 30 | 50 × 7 m | 3,0 m |

Los polígonos vienen de `src/pilas_catalogo.json` de DIGICOMPOST, en grados, pasados a EPSG:25831. Las 30 suman 10 366 m². El material de cada pila
es el de la última campaña guardada en DIGICOMPOST (2026-10-08): 29 con NA y la 15 con NG.

**Cómo emiten (CIRCE, 2026-11-03):** constante, salvo un día al mes, el del volteo, en el que durante unas horas emiten 10 veces más.

- **Fichas:** la emisión de referencia es la del volteo, 340 ou_E/(s·m²), de 8 a 16 h (hora oficial); fuera de esas horas, el 10 %, 34 ou_E/(s·m²),
  que es la emisión en reposo de DIGICOMPOST. Una ficha solo describe un día tipo: la «Base» es, por tanto, un volteo cada día.
- **Plan «Operación normal»** (mensual): el día 21, el perfil del volteo; los demás días, el 10 % todo el día. Es el que hay que simular.
  El día 21 se eligió para que el día de prueba enseñe el volteo; se cambia en la ventana de planes.

**Edificio, según el LiDAR del ICGC (vuelo de 2021-2023) y el Catastro:** solo hay uno, el de cubierta azul (11 161 m² en el Catastro), sobre las
pilas L70. Su mitad sur está clasificada como edificio, de 14 m; la norte, igual de alta, deja pasar el láser hasta el suelo, como una cubierta
abierta o translúcida, y el viento local no la cuenta. Donde están las pilas L40 y L50 el LiDAR ve las propias pilas, de 3 a 4,6 m, al aire libre:
o no tienen cubierta o es posterior al vuelo. DIGICOMPOST llama «nave» a todo el conjunto (26 768 m²). Hay que confirmarlo en la planta.

⚠️ **Las emisiones son PROVISIONALES:** los cinco materiales de DIGICOMPOST (NA, NG, NO, S1 y S2) tienen hoy los mismos valores, su propio código dice
que hay que sustituirlos por los reales, y las horas del volteo están por confirmar. Por eso `focos.json` lleva `"ejemplo": true`. Lo que sí es real es
dónde está cada pila.

## Los cálculos: fuera del repositorio

Van a `datos/` (ver `entrada/rutas.json`), que no se sube: viento, meteorología, respuestas de los focos y resultados.

Hecho el 2026-11-03 con el día de prueba, el mismo que en La Galera: viento de GFS + las 4 estaciones (18 min, casi todo en descargas), respuestas de
las 30 pilas (2,4 min) y el plan «Operación normal» simulado (43 s los 5 años, 5 s el día). Ese día el viento en la nave es de poniente, de 1 a 8 m/s,
y el penacho va hacia el este (rumbo de unos 100°): los pueblos de la tabla salen a cero.

Tareas, con `PYTHONPATH=../v0.1.5/cargador` y `TEODORS_PLANTA=entrada`:

| Para qué | Orden |
|---|---|
| Viento de un día (GFS + las 4 estaciones) | `python -m teodors.operacion.viento_periodo --dia 2026-10-21` |
| Respuestas de las pilas a ese viento | `python -m teodors.operacion.respuestas --dia 2026-10-21` |
| Rehacer el viento local, si cambian los edificios (21 min) | `python -m teodors.operacion.viento_local_biblioteca` |
| De las nubes LiDAR a sus rejillas de 1 m | `python -I ../v0.1.5/core/fuentes/lidar.py <carpeta .laz> <carpeta de las librerías> entrada/viento_local/planta_1m.npz 278575 4610786 400` |

Las teselas del LiDAR (`lidar-territorial-v3r1-full1km278610-2021-2023.laz` y la `278611`, 460 MB) están en
`https://datacloud.icgc.cat/datacloud/lidar-territorial/laz_unzip/full10km2761/`.

## Créditos de los datos

| Dato | Crédito | Condiciones |
|---|---|---|
| MDT y ortofoto PNOA | © Instituto Geográfico Nacional de España | CC BY 4.0, [scne.es](https://www.scne.es) |
| Usos del suelo | CORINE Land Cover 2018, Copernicus Land Monitoring Service ([doi:10.2909/71c95a07-e296-44fc-b22b-415f42acfdf0](https://doi.org/10.2909/71c95a07-e296-44fc-b22b-415f42acfdf0)), con su copia del IGN | Atribución. **Transformado:** recortado a 50 × 50 km y pasado a rejilla de 25 m |
| Edificios | © Dirección General del Catastro | Solo el dato transformado: huella, uso y plantas, no el GML original |
| Nombres de los núcleos | CartoCiudad, © Instituto Geográfico Nacional | CC BY 4.0 |
| Estaciones meteorológicas | Servei Meteorològic de Catalunya, datos abiertos | Atribución |
| Alturas de los edificios de la planta | LiDAR del Institut Cartogràfic i Geològic de Catalunya | Atribución |
