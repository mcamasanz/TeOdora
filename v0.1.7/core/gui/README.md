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

Opciones: `--dia AAAA-MM-DD`, `--focos` y `--planes`. La app arranca siempre con el usuario normal: el administrador (que puede añadir, quitar y cambiar focos) se abre desde la terminal de la app con un comando oculto, `_<operacion.modo_edicion>` (los ocultos empiezan por «_»), y su contraseña, y se vuelve con `_<operacion.usuario>` (`operacion.administrador`; usuario, 2026-11-08); ya no hay opción de la línea de órdenes para eso. Lo que no reconoce se queda para Qt. Si a la planta le falta un campo de la tabla de abajo, `main` lo dice al arrancar.

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
| `identidad.icono` (opcional, relativo) | `tema.icono_app`: el icono de la ventana y de la barra de tareas, y la marca de la barra superior. Mejor un .ico: Qt no aplica el `clipPath` de un .svg (medido con Qt 6.11.3), y lo recortado sale entero. Sin él, o si no se puede leer, la marca de teOdors en el acento del estilo | `icono/icono.ico` |
| `identidad.version`, `entidad` | La ayuda (botón «Ayuda» del riel) y el registro. La versión es la de la app, no la de teOdors | `1.0`, `Mi empresa` |
| `identidad.red_datos` | el aviso de que no se llega a la carpeta de datos: «conéctate a…» | `la red de la empresa` |
| `proyeccion.zona_horaria` | `panel`: la hora oficial del reproductor | `Europe/Madrid` |
| `reanalisis.anios` | `panel`: «N años» y la fecha mínima de un periodo (2 de enero del primero) | `[2021, 2022]` |
| `fuentes.fondos` | `mapa_web`, `focos_mapa`: `[nombre, url, atribución, zoom nativo máximo]`, el primero el que se ve al abrir; el primero, también bajo el plano de la página Focos (`fuentes.ortofoto`) | |
| `fuentes.creditos` | La ayuda; las librerías las añade este paquete | |
| `fuentes.mdt`, `usos`, `edificios`, `nombres_nucleos` | cómo se llama a cada servicio en los textos | |
| `estaciones.proveedor` | tooltip de las estaciones y registro | |
| `operacion.modo_edicion`, `texto_modo_edicion` | el comando oculto de la terminal que cambia al administrador y su nombre, en títulos y botones | `circe`, `CIRCE` |
| `operacion.usuario`, `texto_usuario` (opcionales) | el comando que vuelve al usuario de la planta y su nombre (por defecto, `normal`) | `cliente`, `Cliente` |
| `visor3d.credito` | `penacho_3d.pagina` | |

`planta.MODO_EDICION` es lo que lee la interfaz: empieza en False al activar la planta y lo cambian los comandos ocultos de los dos usuarios en la terminal (`ventana._poner_admin`).

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
| `focos_graficos.py` | lo de la página Focos, dibujado: el plano de los focos sobre la ortofoto de la planta (o, sin ella, sobre sus edificios), la lista de los focos con su emisión (de olor o de un gas), y el calendario de emisión de la planta con un plan de operación y las horas del día elegido; y los colores de los modelos de foco, también del plano de la ventana de focos; y, para el editor de un punto, la chimenea y los edificios de alrededor en perspectiva, con las 36 direcciones del viento en el suelo y la estela del viento elegido, que gira al arrastrar (`PanelEstela`), la composición del gas de salida en una barra (`BarraComposicion`) y el olor que aporta cada gas, el dominante delante (`OlorGases`); y los edificios de la planta en 3D, con la misma cámara (`VisorEdificios`, en la página Planta y en el editor de edificios); y una superficie en 3D, una balsa hundida o la boca de un tanque, con los edificios de alrededor (`PanelSuperficie`, en el editor de focos); y un volumen en 3D, una pila de compost con su sección o una nave, con la fila de volúmenes del motor (`PanelVolumen`); y todos los focos de la planta en 3D, bajo la lista de la ventana de los focos (`VisorFocos3D`); y una semana como la de Outlook, con la operación del foco elegido y la emisión de toda la planta hora a hora (`SemanaEmision`, en la ventana de la operación) |
| `planta_graficos.py` | lo de la página Planta, dibujado: la elevación en barras por franja de cota y los usos del suelo en una barra al 100 % |
| `viento_planta.py` | el viento en la planta, dibujado para Meteorología → Reanálisis: el calendario del viento (cada día, su viento medio y hacia dónde sopla) y las horas del día cargado. Su `Calendario` es la base del de la emisión |
| `mapa.py`, `mapa_web.py` | la vista del mapa con su puente, y su página |
| `focos_mapa.py` | el plano de la ventana de focos |
| `editor_edificios.py` | los edificios de la planta (solo el administrador): la lista con su origen y su altura, el plano para dibujarlos con un rectángulo, un círculo o un polígono, su nombre y su altura, con la del LiDAR a un clic, y todos en 3D (`focos_graficos.VisorEdificios`); al guardar, la estela de los focos punto se rehace |
| `editor_focos.py` | crear o modificar un foco (solo el administrador): el modelo en tres tarjetas, la actividad (los focos ya guardados, para no repetir nombres: el nombre es la actividad), su geometría en el plano con un rectángulo, un círculo, un polígono o un punto, sus medidas, y su ficha sin la operabilidad |
| `ventana_focos.py` | los focos, para consultar: la lista, el plano y la ficha (`FichaVista`); crear, modificar y eliminar, solo el administrador. `Ficha`, la de casillas, para el editor: el punto, con el panel de la chimenea y los edificios (que calcula `operacion.estela` al marcarlo), su altura, diámetro y hacia dónde sale, y el gas de salida en una fila (temperatura, velocidad ⇄ caudal en m³/h, Nm³/h o kg/h: el no escrito, calculado) con su composición (CO₂, CO, CH₄, H₂, C₂H₆, O₂ y N₂, en una barra) y su densidad, y la emisión con los gases primero y la olfatometría opcional |
| `ventana_planes.py` | la operación: los focos con el plano debajo; en el centro, el mes y la semana de la emisión con el plan abierto; a la derecha, los días del plan del foco y su perfil de 24 h, con un día que se copia y se pega en muchos (elegidos arrastrando, por día de la semana o por grupos), y la operación de un foco, a otros del mismo tipo |
| `ventana_ajustes.py` | la configuración |
| `vista_previa.py` | el mapa de la ventana de configuración |
| `vista_3d.py`, `penacho_3d.py` | el visor 3D y la página que enseña |
| `tema.py` | estilos, colores, letra e iconos |
| `widgets.py`, `consola.py`, `terminal.py`, `trabajos.py`, `web.py` | widgets pequeños, registro de actividad, terminal, hilos y HTML sin CDN |
| `recursos/visor3d/` | la plantilla del visor, three.js r147 y sus controles (MIT) |
