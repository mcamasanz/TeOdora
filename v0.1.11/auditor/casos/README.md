# Casos de regresión

Entradas pequeñas de cada motor con sus salidas de referencia (ver ../README.md). La columna
«Contraste con el original» dice cómo se comprobó que la referencia es correcta: los casos
recortados se corrieron también con el programa original; los demás son casos completos de las
baterías de validación del laboratorio.

| Caso | Qué comprueba | Duración | Contraste con el original |
|---|---|---|---|
| `capa_limite/era5_lleida_2dias` | Estación propia (ERA5 en Lleida) y sondeo IGRA de Barcelona, dos días: extracción, control de calidad y cálculo del .sfc y el .pfl. | 0.5 s | idéntico al original salvo fecha y hora |
| `edificios/nave` | Nave de varios niveles y chimenea junto a ella: dimensiones por dirección y GEP. | 0.2 s | idéntico al original salvo fecha y hora |
| `geofisica/agua` | Malla de 1 km con celdas de agua (CFRACT 0,30): uso dominante y propiedades ponderadas. | 0.2 s | laboratorio: batería de geofísica, caso A_agua_cfract030 (OK) |
| `penacho/chimenea` | Pilas y una chimenea puntual (sobreelevación, terreno), 4 receptores y 6 horas. | 0.4 s | idéntico al original salvo fecha y hora |
| `penacho/deposicion` | Deposición seca y húmeda de gas en las pilas, con lluvia sintética. | 1.0 s | idéntico al original salvo fecha y hora |
| `penacho/linea` | Fuente LINE junto a las pilas. | 0.4 s | idéntico al original salvo fecha y hora |
| `penacho/no2_olm` | Química del NO2 con OLM: pilas, área circular, volumen y chimenea. | 0.4 s | idéntico al original salvo fecha y hora |
| `penacho/nucleo_compilado` | Las 17 pilas con el núcleo compilado (numba): debe dar lo mismo que la vía Python. | 1.7 s | idéntico al original salvo fecha y hora |
| `penacho/pilas_area` | Las 17 pilas de compostaje (áreas poligonales) con terreno, 4 receptores y 6 horas. | 0.4 s | idéntico al original salvo fecha y hora |
| `puffs/area_D` | Pila de compostaje (área) en clase D a 3 m/s: puffs de área, Fr y σy0. | 1.1 s | laboratorio: batería de puffs, caso S_area_D (OK) |
| `relieve/redes_polares` | Rejilla cartesiana y polar sobre el MDT de Lleida: cotas y alturas de colina. | 0.5 s | idéntico al original salvo fecha y hora |
| `superficie/corine_lleida` | CORINE de Lleida adaptado a clases NLCD: z0, Bowen y albedo por sector y mes. | 0.5 s | idéntico al original salvo fecha y hora (sitio_sfc.txt) |
| `viento3d/llano_lleida` | Terreno llano de Lleida con el pronóstico como campo inicial (configuración de digicompost). | 1.5 s | laboratorio: batería de viento3d, caso S_llano_lleida (OK) |

Cada caso: `entrada/` (lo que lee el motor), `referencia/` (lo que debe escribir) y `caso.json`
(cómo se corre: motor, carpeta, órdenes, variables de entorno y ficheros que se comparan).
