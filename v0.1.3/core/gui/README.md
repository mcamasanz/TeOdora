# `teodors.gui` — la aplicación de escritorio de una planta

<!-- manual -->
## Qué hace

La ventana de una planta: mapa, panel por páginas, focos, planes, simulación, visor 3D y configuración, en PySide6 y con el mapa en una página web (folium y Leaflet). Replicarla en otra planta es cambiar de carpeta: el código es este, y lo de cada sitio sale de su carpeta.

No es un motor y no se lanza con `python -m teodors`. Va encima de `operacion`, `fuentes`, `casos` y `metricas`, y nada fuera de este paquete la importa: quien instale teOdors sin el extra `gui` no hereda Qt (lo comprueba `test_gui.py`).

## Uso

El `main.py` de una planta:

```python
import sys
from teodors import planta
from teodors.gui.principal import main

planta.activar("ruta/de/la/planta")
sys.exit(main())
```

Opciones: `--dia AAAA-MM-DD`, `--focos`, `--planes` y `--<operacion.modo_edicion>` (por defecto, `--edicion`). Lo que no reconoce se queda para Qt. Si a la planta le falta un campo de la tabla de abajo, `main` lo dice al arrancar.

## Extras

| Extra | Qué trae |
|---|---|
| `teodors[gui]` | PySide6, folium y lo de `teodors[fuentes]` |
| `teodors[gui3d]` | lo anterior y pyvista: el visor 3D lanza el motor y hace las superficies |
| `teodors[pruebas_gui]` | solo PySide6 y folium, para que las pruebas de la interfaz no se salten |

Medido con PySide6 6.11.1 y folium 0.18.0; no se ha instalado en un entorno limpio.

## De la planta

| De su carpeta | Lo usa |
|---|---|
| `operacion.ejemplo` (carpeta, relativa) | `vista_previa`: `ejemplo.json`, `viento.json` y `penacho_*.png`, el ejemplo de la configuración. Sin ellos, esa ventana falla al abrirse. Lo escribe `operacion.ejemplo_configuracion` |
| `visor3d.ortofoto` (fichero, relativo) | `penacho_3d.pagina`. Ningún código lo genera |

| De planta.json | Lo usa | Ejemplo |
|---|---|---|
| `identidad.app_nombre`, `organizacion` | títulos; lo que va antes de « · » es el rótulo de la barra | `Mi planta · Dispersión` |
| `identidad.ajustes` | `tema.ajustes`: `%APPDATA%\<organizacion>\<ajustes>.ini`, con la disposición y las preferencias. Si cambia, quien usa la app las pierde | `Mi_Planta` |
| `identidad.app_id` | `principal`: su icono en la barra de tareas de Windows | `ORG.MiPlanta` |
| `identidad.version`, `entidad` | «Acerca de» y el registro. La versión es la de la app, no la de teOdors | `1.0`, `Mi empresa` |
| `identidad.red_datos` | el aviso de que no se llega a la carpeta de datos: «conéctate a…» | `la red de la empresa` |
| `proyeccion.zona_horaria` | `panel`: la hora oficial del reproductor | `Europe/Madrid` |
| `reanalisis.anios` | `panel`: «N años» y la fecha mínima de un periodo (2 de enero del primero) | `[2021, 2022]` |
| `fuentes.fondos` | `mapa_web`, `focos_mapa`: `[nombre, url, atribución, zoom nativo máximo]`, el primero el que se ve al abrir | |
| `fuentes.creditos` | «Acerca de»; las librerías las añade este paquete | |
| `fuentes.mdt`, `usos`, `edificios`, `nombres_nucleos` | cómo se llama a cada servicio en los textos | |
| `estaciones.proveedor` | tooltip de las estaciones y registro | |
| `operacion.modo_edicion`, `texto_modo_edicion` | la opción y el valor de `<prefijo>_MODO` (por defecto, `edicion`); cómo se rotula en títulos y botones | |
| `visor3d.credito` | `penacho_3d.pagina` | |

`planta.MODO_EDICION` es lo que lee la interfaz. Se fija al activar la planta (`<prefijo>_MODO`) o con la opción de `main`.

## El puente con el mapa

Python → JavaScript: `window.mapaApp.*` (`mapa.VistaMapa`, `focos_mapa.VistaFocos`). JavaScript → Python: `console.log("MAPA:" + JSON)`, que recoge `mapa.PaginaMapa`. Las clases CSS propias empiezan por `mapa-`, y la capa de las partículas va en el panel de Leaflet `mapaViento`.

## Reglas

- **Nada de textos secundarios en la interfaz:** solo nombres, datos, unidades, leyendas, estados breves y errores reales.
- **Los colores no se fijan al crear algo,** o no seguirán el cambio de estilo: `tema.pon_icono`, `tema.texto`, `tema.estilo`, `c("…")` dentro de un paintEvent y, en el mapa, `var(--…)`. Ver el docstring de `tema`.
- `tema.T` es siempre el mismo diccionario: `poner` cambia su contenido.
- Importar `web`, `penacho_3d`, `principal` o el paquete no carga Qt.

⚠️ `LICENSE-three.txt` va con three.js, pero el `LICENSE` de teOdors aún no contempla a terceros (three.js, y Leaflet, folium y lo que `web` embebe, que tampoco tienen `THIRD-PARTY-NOTICES`).

⚠️ Sin red, `web._descarga` espera hasta 40 s por recurso la primera vez, y las teselas son siempre de internet.

<!-- /manual -->

## Ficheros

| Fichero | Qué es |
|---|---|
| `principal.py` | el arranque: `main`, `opciones`, `comprobar_planta` |
| `ventana.py` | la ventana principal |
| `panel.py` | el panel, por páginas, y el reproductor |
| `mapa.py`, `mapa_web.py` | la vista del mapa con su puente, y su página |
| `focos_mapa.py` | el plano de la ventana de focos |
| `ventana_focos.py`, `ventana_planes.py`, `ventana_ajustes.py` | las otras ventanas |
| `vista_previa.py` | el mapa de la ventana de configuración |
| `vista_3d.py`, `penacho_3d.py` | el visor 3D y la página que enseña |
| `tema.py` | estilos, colores, letra e iconos |
| `widgets.py`, `consola.py`, `terminal.py`, `trabajos.py`, `web.py` | widgets pequeños, registro de actividad, terminal, hilos y HTML sin CDN |
| `recursos/visor3d/` | la plantilla del visor, three.js r147 y sus controles (MIT) |
