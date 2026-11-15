# -*- coding: utf-8 -*-
"""La página del penacho en 3D: `operacion.penacho_3d` calcula y guarda, y aquí se monta lo que enseña el visor (`gui.vista_3d`), con los colores del estilo en uso. `abrir` y `calcular`
devuelven esa página; cualquier otro nombre es el de `operacion.penacho_3d`. La ortofoto y su crédito: `visor3d` de planta.json. Importar esto no carga Qt: `tema` se importa al montar la página.
"""
import json
from pathlib import Path

from teodors import planta as config
from teodors.operacion import penacho_3d as _fuente

RECURSOS = Path(__file__).resolve().parent / "recursos" / "visor3d"


def abrir(ruta_resultado, clave):
    """La página montada de lo guardado, y las horas para el reproductor; None si no vale."""
    r = _fuente.abrir(ruta_resultado, clave)
    return None if r is None else {"pagina": str(pagina(r["datos"])), "horas": r["horas"]}


def calcular(ruta_resultado, clave, progreso=None, cancelado=None):
    """Calcula y guarda el penacho en 3D de la magnitud `clave` del resultado de esa ruta. Devuelve lo mismo que `abrir`."""
    r = _fuente.calcular(ruta_resultado, clave, progreso, cancelado)
    return {"pagina": str(pagina(r["datos"])), "horas": r["horas"]}


def pagina(datos):
    """Monta la página con la librería, la ortofoto y las mallas, sin internet; la misma ruta siempre: solo se ve una."""
    from teodors.gui import tema                  # solo aquí, por sus variables de color: trae Qt y el cálculo no lo necesita
    html = (RECURSOS / "plantilla.html").read_text(encoding="utf-8")
    ortofoto = config.bloque("visor3d").get("ortofoto")      # una planta nueva aún no la tiene: el suelo sale liso
    orto = _fuente._b64((config.PLANTA / ortofoto).read_bytes()).decode() if ortofoto else ""
    for marca, texto in (("/*CREDITO*/", config.bloque("visor3d").get("credito", "")), ("/*VARIABLES*/", tema.css_variables()), ("/*THREE*/", (RECURSOS / "three.min.js").read_text(encoding="utf-8")),
                         ("/*ORBIT*/", (RECURSOS / "OrbitControls.js").read_text(encoding="utf-8")),
                         ("/*DATOS*/", json.dumps(datos)), ("/*ORTO*/", orto)):
        html = html.replace(marca, texto)
    ruta = config.DIR_WEB / "penacho_3d.html"
    ruta.parent.mkdir(parents=True, exist_ok=True)
    ruta.write_text(html, encoding="utf-8")
    return ruta


def __getattr__(nombre):
    return getattr(_fuente, nombre)
