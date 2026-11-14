# Librerías de terceros

**Va dentro de este repositorio:**

| Librería | Dónde | Licencia |
|---|---|---|
| three.js r147 y OrbitControls | `core/gui/recursos/visor3d/` | MIT (`LICENSE-three.txt`, en esa carpeta) |

**No va dentro: se instalan con el paquete** (`pyproject.toml`). Para entregar la herramienta hay que respetar las suyas:

| Librería | Para qué | Licencia | Al entregarla |
|---|---|---|---|
| PySide6 / Qt | la interfaz (extra `gui`) | LGPL v3 | en modo carpeta, con las DLL de Qt sustituibles, el texto de la LGPL y el enlace a su código fuente |
| folium y Leaflet | los mapas (extra `gui`); Leaflet va embebido en cada página que se genera | MIT y BSD-2 | conservar sus avisos |
| GEOS, a través de shapely | geometrías (extras `fuentes` y `gui`) | LGPL v2.1 | como PySide6 |
| numpy, numba, rasterio, pyproj, pandas, geopandas, scipy, matplotlib… | el cálculo | permisivas (BSD, MIT…) | conservar sus avisos |

**Los datos de cada planta** tienen sus propias condiciones de uso: se citan en el `README.md` de su carpeta.
