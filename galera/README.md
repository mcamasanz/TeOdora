# La Galera

Planta de biometano de ENCE en La Galera (Montsià, Tarragona), en 40,6905923 N y 0,4764197 E. La versión de teOdors que usa está en [`VERSION`](VERSION).

⚠️ **Los 13 focos de `entrada/focos.json` son de ejemplo:** posiciones leídas a ojo en la ortofoto y valores inventados, a la espera de la visita a la planta. Lo que se calcule
con ellos prueba la herramienta, pero no es un resultado. La normativa de `entrada/normativa.json` también es preliminar, y la serie de viento de 5 años está sin terminar (18 de 60 meses el 2026-10-21, en la carpeta de cálculos).

## Abrir la aplicación

```bash
python main.py                  # modo operario: consulta los focos y crea planes de operación
python main.py --circe          # además, añade y cambia focos
```

También `--dia AAAA-MM-DD`, `--focos` y `--planes`. Sin la carpeta de cálculos se abre igual, con el terreno y los edificios, pero sin viento ni simulaciones.

## Datos de entrada: `entrada/`

| Qué | Dónde | De dónde sale |
|---|---|---|
| Identidad, huso (EPSG:25831), dominio de 50 × 50 km, malla de receptores | `planta.json` | decisiones de proyecto, explicadas en sus notas |
| Coordenadas | `emplazamiento.json` | fijas, no se cambian desde la aplicación |
| Cotas, a 25 m | `terreno/40.69059_0.47642_50km_25m/elevacion.tif` | MDT del IGN |
| Usos del suelo | `terreno/…/usos.tif`, `terreno/…/corine.gpkg` | CORINE Land Cover 2018, recortado y pasado a rejilla |
| Núcleos de población | `terreno/…/nucleos_nombres.json` | CORINE, con los nombres de CartoCiudad |
| Edificios a menos de 2 km (867) | `edificios/40.69059_0.47642_r2km/edificios.gpkg` | Catastro: solo huella, uso y plantas |
| Focos | `focos.json` | ⚠️ de ejemplo |
| Planes de operación guardados | `planes/` | los crea quien opera la planta, desde la aplicación. Aún no hay ninguno |
| Receptores con nombre (Dacame) | `receptores.json` | Catastro |
| Límites | `normativa.json` | ⚠️ preliminar |
| Viento alrededor de los edificios | `viento_local/viento_local.npz` | calculado con `viento_local/planta_1m.npz`, de LiDAR del ICGC. ⚠️ No validado: solo enseña el efecto de los edificios |
| Ejemplo de la ventana de configuración | `recursos/ejemplo/` | una hora de viento y de penacho, con los focos de ejemplo. No es un resultado |
| Ortofoto del visor 3D | `recursos/visor3d/ortofoto.jpg` | PNOA, ±3,2 km |

## Los cálculos: fuera del repositorio

Van a la carpeta de `entrada/rutas.json` (`Z:\Miguel\03-Odora\ENCE_LaGalera`), o a la de la variable `ENCE_GALERA_DATOS` si está puesta: viento, meteorología, respuestas de los focos y resultados. Las claves, en `%APPDATA%\CIRCE\claves`.

Tareas, con `PYTHONPATH=../v0.1.5/cargador` y `TEODORS_PLANTA=entrada`:

| Para qué | Orden |
|---|---|
| Serie de viento de varios años | `python -m teodors.operacion.viento3d_series` |
| Rehacer el viento local, si cambian los edificios | `python -m teodors.operacion.viento_local_biblioteca` |
| De las nubes LiDAR a sus rejillas de 1 m | `python -I ../v0.1.5/core/fuentes/lidar.py <carpeta .laz> <carpeta de las librerías> entrada/viento_local/planta_1m.npz 286512 4507400 600` |

## Pruebas y documentación del proyecto

No van en el repositorio, que solo lleva la instalación: las pruebas (`99-Test/`), la documentación (`docs/`) y las decisiones tomadas
(`CLAUDE.md`) están en el equipo de quien mantiene la planta.

## Créditos de los datos

| Dato | Crédito | Condiciones |
|---|---|---|
| MDT y ortofoto PNOA | © Instituto Geográfico Nacional de España | CC BY 4.0, [scne.es](https://www.scne.es) |
| Usos del suelo | CORINE Land Cover 2018, Copernicus Land Monitoring Service ([doi:10.2909/71c95a07-e296-44fc-b22b-415f42acfdf0](https://doi.org/10.2909/71c95a07-e296-44fc-b22b-415f42acfdf0)), con su copia del IGN | Atribución. **Transformado:** recortado a 50 × 50 km y pasado a rejilla de 25 m |
| Edificios | © Dirección General del Catastro | Solo el dato transformado: huella, uso y plantas, no el GML original |
| Nombres de los núcleos | CartoCiudad, © Instituto Geográfico Nacional | CC BY 4.0 |
| Alturas de los edificios de la planta | LiDAR del Institut Cartogràfic i Geològic de Catalunya | Atribución |
