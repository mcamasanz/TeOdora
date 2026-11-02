# -*- coding: utf-8 -*-
"""Tanda 8: la interfaz movida a teOdors frente al original de git, función a función.

    python comparar_movidos_tanda8.py <raíz de la planta> <commit original de la planta> <commit original del core> <carpeta core nueva>

Con ENCE_GALERA_DATOS, una copia de los datos: además lanza una sonda con el código original, sacado de git a una carpeta temporal, y otra con el nuevo, sin ventanas de verdad (offscreen),
y compara sus páginas, sus colores y, en los 4 estilos, sus textos y los píxeles del panel. Con T8_PAQUETES, el cargador de la copia de desarrollo del core.

Por cada función, método, cuerpo de clase y constante, el TEXTO sin docstrings (caza comentarios y caracteres invisibles), también el del JavaScript y el CSS, que van en cadenas. Las diferencias
esperadas se quitan de forma explícita, con su motivo; lo demás tiene que dar igual byte a byte. La primera sustitución es mecánica y va para todo: el nombre del cliente en el JavaScript.
"""
import ast
import difflib
import hashlib
import importlib
import io
import json
import os
import re
import subprocess
import sys
import tarfile
import tempfile
import textwrap
from pathlib import Path

PLANTA, COMMIT, COMMIT_CORE, CORE = Path(sys.argv[1]), sys.argv[2], sys.argv[3], Path(sys.argv[4])
REPO_CORE = CORE.parent
RARO = {0xa0: "NBSP", 0x202f: "NNBSP", 0x2009: "fino", 0x200b: "ancho cero", 0x2011: "guion duro", 0xad: "guion blando", 0x2212: "menos", 0x200a: "muy fino"}
sys.stdout.reconfigure(encoding="utf-8")
MODULOS = ["consola", "focos_mapa", "mapa", "mapa_web", "panel", "tema", "terminal", "trabajos", "ventana", "ventana_ajustes", "ventana_focos", "ventana_planes", "vista_3d", "vista_previa", "web", "widgets"]
GUI = "lib/galera/gui/"
RENOMBRES = [(r"\bence-", "mapa-"), (r"\benceViento\b", "mapaViento"), (r"\bence\b", "mapaApp"), (r"\bENCE:", "MAPA:")]


def renombra(t):
    for de, a in RENOMBRES:
        t = re.sub(de, a, t)
    return t


def _git(repo, rev, rel):
    return subprocess.run(["git", "-C", str(repo), "show", f"{rev}:{rel}"], capture_output=True, check=True).stdout


def viejo(rel):
    return _git(PLANTA, COMMIT, rel).decode("utf-8").replace("\r\n", "\n")


def nuevo(rel):
    return (CORE / rel).read_bytes().decode("utf-8").replace("\r\n", "\n")


def _doc(n):
    return isinstance(n, (ast.FunctionDef, ast.ClassDef)) and isinstance(n.body[0], ast.Expr) and isinstance(getattr(n.body[0], "value", None), ast.Constant) and isinstance(n.body[0].value.value, str)


def _inicio(n):
    return min([d.lineno for d in getattr(n, "decorator_list", [])] + [n.lineno])


def _texto(src, nodo, excluir=()):
    """El texto del nodo, comentarios incluidos, sin docstrings ni las líneas de `excluir`."""
    lineas = src.splitlines(keepends=True)
    fuera = set(excluir)
    for n in ast.walk(nodo):
        if _doc(n):
            fuera.update(range(n.body[0].lineno, n.body[0].end_lineno + 1))
    return "".join(lineas[i - 1] for i in range(_inicio(nodo), nodo.end_lineno + 1) if i not in fuera)


def tabla(src):
    """{nombre: texto}: funciones, métodos (Clase.metodo), lo que queda de cada clase (Clase.<cuerpo>) y constantes."""
    d = {}
    for n in ast.parse(src).body:
        if isinstance(n, ast.FunctionDef):
            d[n.name] = _texto(src, n)
        elif isinstance(n, ast.ClassDef):
            metodos = [m for m in n.body if isinstance(m, ast.FunctionDef)]
            fuera = set()
            for m in metodos:
                d[f"{n.name}.{m.name}"] = _texto(src, m)
                fuera.update(range(_inicio(m), m.end_lineno + 1))
            d[f"{n.name}.<cuerpo>"] = _texto(src, n, fuera)
        elif isinstance(n, ast.Assign):
            for o in n.targets:
                for x in ast.walk(o):
                    if isinstance(x, ast.Name):
                        d[x.id] = _texto(src, n)
    return d


def _ast(fragmento):
    a = ast.parse(textwrap.dedent(fragmento))
    for n in ast.walk(a):
        if _doc(n):
            n.body = n.body[1:] or [ast.Pass()]
    return ast.dump(a)


COM = "comentario: "                          # un motivo así no cambia el AST
JS = "comentario de JavaScript: "             # sí cambia la cadena de Python, pero el navegador no lo ve
CIRCE = "el texto del modo de edición, de operacion.texto_modo_edicion: da lo mismo"
ANIOS = "«5 años»: salía de reanalisis.anios; da lo mismo"
RED = "a qué conectarse, de identidad.red_datos: da lo mismo"
ED = "el nombre del servicio de edificios, de fuentes.edificios: da lo mismo"
MODO = "config.MODO_CIRCE pasa a planta.MODO_EDICION"
PROV = "el nombre del proveedor de las estaciones, de estaciones.proveedor: da lo mismo"
TX_MOD = '''config.pide('operacion', 'texto_modo_edicion')'''

# Los import dentro de una función son mecánicos: cada módulo por su nombre en teodors. Ya eran envoltorios de eso.
IMPORTS = [("from galera.gui import planes_calculo as PC\n", "from teodors.operacion import simulacion as PC\n"),
           ("from galera.gui import planes_calculo, periodos\n", "from teodors.operacion import simulacion as planes_calculo, periodos\n"),
           ("from galera.gui import planes_calculo\n", "from teodors.operacion import simulacion as planes_calculo\n"),
           ("from galera.gui import escenarios, planes_calculo\n", "from teodors.operacion import planes as escenarios, simulacion as planes_calculo\n"),
           ("from galera.gui import escenarios, focos\n", "from teodors.operacion import planes as escenarios, focos\n"),
           ("from galera.gui import periodos\n", "from teodors.operacion import periodos\n"), ("from galera.gui import focos\n", "from teodors.operacion import focos\n"),
           ("from galera.gui import penacho_3d\n", "from teodors.gui import penacho_3d\n"), ("from galera.entradas.edificios import USO_COLOR\n", "from teodors.fuentes.catastro import USO_COLOR\n"),
           ("from galera.entradas import terreno\n", "from teodors.fuentes import terreno\n"), ("from galera.gui import viento_mapa\n", "from teodors.operacion import viento_mapa\n"),
           ("from galera.gui.vista_previa import VistaPrevia", "from teodors.gui.vista_previa import VistaPrevia"), ("from galera.gui.vista_3d import Vista3D\n", "from teodors.gui.vista_3d import Vista3D\n"),
           ("from galera.gui.ventana_focos import VentanaFocos\n", "from teodors.gui.ventana_focos import VentanaFocos\n"), ("from galera.gui.ventana_ajustes import VentanaAjustes\n", "from teodors.gui.ventana_ajustes import VentanaAjustes\n"),
           ("from galera.gui.ventana_planes import VentanaPlanes\n", "from teodors.gui.ventana_planes import VentanaPlanes\n")]

ESPERADOS = {
    ("focos_mapa", "_JS"): [("// modo dibujo (CIRCE):", "// modo dibujo (edición):", JS + "sin el nombre de la entidad")],
    ("focos_mapa", "escribir_html"): [("enumerate(mapa_web.FONDOS)", "enumerate(mapa_web.fondos())", "los fondos, de fuentes.fondos en planta.json")],
    ("mapa_web", "_JS"): [("// A menos del radio del segmento planta-Dacame manda este motor", "// A menos del radio del segmento entre los dos puntos de la planta manda este motor", JS + "sin el nombre del vecino")],
    ("mapa_web", "escribir_mapa_base"): [("enumerate(FONDOS)", "enumerate(fondos())", "los fondos, de fuentes.fondos en planta.json")],
    ("panel", "Panel.<cuerpo>"): [("# los 5 años del reanálisis: ruta del plan", "# los años del reanálisis: ruta del plan", COM + "sin el número de años"), ("(los define CIRCE; el operario los consulta)", "(el operario los consulta; se cambian en el modo de edición)", COM + "sin el nombre de la entidad")],
    ("panel", "Panel._seccion_emplazamiento"): [("(galera.geo.dir_geo_a_rejilla)", "(planta.geo.dir_geo_a_rejilla)", COM + "el módulo por su nombre en teodors")],
    ("panel", "Panel._bloque_periodo"): [("QtCore.QDate(2021, 1, 2)", "QtCore.QDate(config.REANALISIS_ANIOS[0], 1, 2)", "la fecha mínima, de reanalisis.anios: la misma")],
    ("panel", "Panel.set_viento_listo"): [("        self._horas_oficial = [dt.datetime.fromisoformat(h).replace(tzinfo=dt.timezone.utc).astimezone(ZONA) for h in horas]\n",
                                           '        zona = ZoneInfo(config.pide("proyeccion", "zona_horaria"))\n        self._horas_oficial = [dt.datetime.fromisoformat(h).replace(tzinfo=dt.timezone.utc).astimezone(zona) for h in horas]\n', "la zona horaria, de proyeccion.zona_horaria: la misma")],
    ("panel", "Panel._seccion_edificios"): [('f"Edificios cercanos (Catastro, {_num(config.RADIO_EDIFICIOS_FOCOS_M)} m)"', '''f"Edificios cercanos ({config.pide('fuentes', 'edificios')}, {_num(config.RADIO_EDIFICIOS_FOCOS_M)} m)"''', ED)],
    ("panel", "Panel._seccion_focos"): [('"Focos… (modo CIRCE)" if config.MODO_CIRCE else "Ver focos…"', f'''f"Focos… ({{{TX_MOD}}})" if config.MODO_EDICION else "Ver focos…"''', CIRCE + "; " + MODO)],
    ("panel", "Panel._seccion_simulacion"): [('Tarjeta("5 años")', "Tarjeta(texto_anios())", ANIOS), ('QtWidgets.QPushButton("Simular 5 años", objectName="primario")', 'QtWidgets.QPushButton(f"Simular {texto_anios()}", objectName="primario")', ANIOS)],
    ("tema", "ajustes"): [('config.ORGANIZACION, "ENCE_Galera")', 'config.ORGANIZACION, config.pide("identidad", "ajustes"))', "el fichero de ajustes, de identidad.ajustes: el mismo")],
    ("ventana", "VentanaPrincipal.__init__"): [("# nombre de cada núcleo (CartoCiudad)", "# nombre de cada núcleo", COM + "sin el nombre del servicio"),
                                               ("# lo simulado: 5 años, y un día, el episodio o la predicción", "# lo simulado: los años del reanálisis, y un día, el episodio o la predicción", COM + "sin el número de años")],
    ("ventana", "VentanaPrincipal._menus"): [('"Focos de emisión…" + (" (modo CIRCE)" if config.MODO_CIRCE else "")', f'''"Focos de emisión…" + (f" ({{{TX_MOD}}})" if config.MODO_EDICION else "")''', CIRCE + "; " + MODO)],
    ("ventana", "VentanaPrincipal._mensajes_arranque"): [('log.info(f"{config.APP_NOMBRE} · versión {__version__}")', '''log.info(f"{config.APP_NOMBRE} · versión {config.pide('identidad', 'version')}")''', "la versión de la app, de identidad.version: la misma"),
                                                         ('f"unidad de red, conéctate a la red de CIRCE (o a la VPN) y reinicia la "', '''f"unidad de red, conéctate a {config.pide('identidad', 'red_datos')} y reinicia la "''', RED),
                                                         ('"Si está en la unidad de red, conéctate a la red de CIRCE (o a la VPN) y "', '''f"Si está en la unidad de red, conéctate a {config.pide('identidad', 'red_datos')} y "''', RED)],
    ("ventana", "VentanaPrincipal._pintar_receptores"): [("        from galera.gui import receptores_mapa as receptores\n", "        from teodors.casos import receptores\n        ESTILOS = receptores.estilos()\n", "los estilos, de receptores.estilos en planta.json: en el core es una función"),
                                                         ("clases = list(receptores.ESTILOS)", "clases = list(ESTILOS)", "ver arriba"), ('[{"color": receptores.ESTILOS[c][0], "radio": receptores.ESTILOS[c][1]}', '[{"color": ESTILOS[c][0], "radio": ESTILOS[c][1]}', "ver arriba"),
                                                         ('f"{receptores.ESTILOS[c][0]};border-radius:50%\'></span>{receptores.ESTILOS[c][2]}"', 'f"{ESTILOS[c][0]};border-radius:50%\'></span>{ESTILOS[c][2]}"', "ver arriba"),
                                                         ("""f"{receptores.ESTILOS[c][2]}: {_num(res['por_clase'].get(c, 0))}\"""", """f"{ESTILOS[c][2]}: {_num(res['por_clase'].get(c, 0))}\"""", "ver arriba")],
    ("ventana", "VentanaPrincipal._cargar_estaciones"): [('log.info(f"Estaciones Meteocat en el mapa: {len(self._estaciones)}")', '''log.info(f"Estaciones {config.pide('estaciones', 'proveedor')} en el mapa: {len(self._estaciones)}")''', PROV),
                                                         ('log.info("Sin estaciones Meteocat en la caché (lib/galera/gui/tareas/descargar_meteocat.py).")', '''log.info(f"Sin estaciones {config.pide('estaciones', 'proveedor')} en la caché (python -m teodors.fuentes.descargar_meteocat).")''', PROV + "; en el registro, la orden que vale desde teOdors")],
    ("ventana", "VentanaPrincipal._pintar_estaciones"): [('''f"<b>{e['nombre']}</b> ({e['codigo']}) · Meteocat<br>"''', '''f"<b>{e['nombre']}</b> ({e['codigo']}) · {config.pide('estaciones', 'proveedor')}<br>"''', PROV)],
    ("ventana", "VentanaPrincipal._cargar_viento"): [("viento_mapa.SERIE", "viento_mapa.serie_defecto()", "la serie, de series.era5: la misma"), ("viento_mapa.TITULOS.get(serie, serie)", "viento_mapa.titulos().get(serie, serie)", "los títulos, de series.titulos: los mismos")],
    ("ventana", "VentanaPrincipal._cargar_terreno_guardado"): [('log.info(f"Núcleos CORINE: {cuenta[', '''log.info(f"Núcleos {config.pide('fuentes', 'usos')}: {cuenta[''', "en el registro: el servicio de usos, de fuentes.usos; da lo mismo")],
    ("ventana", "VentanaPrincipal._pintar_nucleos"): [("# los receptores con nombre (Dacame…): CORINE no los ve", "# los receptores con nombre: el uso del suelo no los ve", COM + "sin el nombre del vecino ni del servicio")],
    ("ventana", "VentanaPrincipal._tabla_plan"): [('else "5 años"', "else texto_anios()", ANIOS)],
    ("ventana", "VentanaPrincipal._cargar_nombres"): [('log.info("Pidiendo a CartoCiudad (IGN) el nombre de los núcleos (solo la primera vez)…")', '''log.info(f"Pidiendo a {config.pide('fuentes', 'nombres_nucleos')} el nombre de los núcleos (solo la primera vez)…")''', "en el registro: el servicio de nombres, de fuentes.nombres_nucleos; da lo mismo")],
    ("ventana", "VentanaPrincipal._pintar_edificios"): [('leyenda = mapa_web.leyenda_html("Edificios (Catastro)", {', '''leyenda = mapa_web.leyenda_html(f"Edificios ({config.pide('fuentes', 'edificios')})", {''', ED),
                                                        ('self.mapa.set_capa_geojson("edificios", "Edificios (Catastro)",', '''self.mapa.set_capa_geojson("edificios", f"Edificios ({config.pide('fuentes', 'edificios')})",''', ED)],
    ("ventana", "VentanaPrincipal._descargar_edificios"): [('log.info(f"Descargando edificios del Catastro a menos de "', '''log.info(f"Descargando edificios del {config.pide('fuentes', 'edificios')} a menos de "''', "en el registro: " + ED)],
    ("ventana", "VentanaPrincipal._redescargar_terreno"): [('''f"carga del disco.\\nSolo hace falta descargarlo de nuevo si los datos del IGN o "
                f"de CORINE han cambiado.\\n\\n¿Descargarlo de nuevo?")''', '''f"carga del disco.\\nSolo hace falta descargarlo de nuevo si los datos del {config.pide('fuentes', 'mdt')} o "
                f"de {config.pide('fuentes', 'usos')} han cambiado.\\n\\n¿Descargarlo de nuevo?")''', "los servicios de terreno y usos, de fuentes.mdt y fuentes.usos: da lo mismo")],
    ("ventana", "VentanaPrincipal._terreno_fallo"): [('"Si es un fallo del servidor del IGN, suele ser temporal: reinténtalo en un minuto."', '''f"Si es un fallo del servidor del {config.pide('fuentes', 'mdt')}, suele ser temporal: reinténtalo en un minuto."''', "el servicio de terreno, de fuentes.mdt: da lo mismo")],
    ("ventana", "VentanaPrincipal._poner_magnitud"): [('nombre = periodos.etiqueta(r["periodo"]) if r["periodo"] else "5 años"', 'nombre = periodos.etiqueta(r["periodo"]) if r["periodo"] else texto_anios()', ANIOS)],
    ("ventana", "VentanaPrincipal._acerca_de"): [('''f"<h3>{config.APP_NOMBRE}</h3><p>Versión {__version__} · Fundación CIRCE</p>"''', '''f"<h3>{config.APP_NOMBRE}</h3><p>Versión {config.pide('identidad', 'version')} · {config.pide('identidad', 'entidad')}</p>"''', "versión y entidad, de identidad: las mismas"),
                                                 ('''            "<li>Satélite (ortofoto PNOA) y MDT: © Instituto Geográfico Nacional de España, "
            "CC BY 4.0 scne.es</li>"
            "<li>Uso del suelo: CORINE Land Cover 2018 (Copernicus / IGN)</li>"
            "<li>Edificios: © Dirección General del Catastro (dato transformado)</li>"
            "<li>Alturas de los edificios de la planta: LiDAR del Institut Cartogràfic i Geològic de Catalunya</li>"
            "<li>Callejero: © colaboradores de OpenStreetMap (ODbL)</li>"
            "<li>Nombres de los núcleos: CartoCiudad, © Instituto Geográfico Nacional, CC BY 4.0</li>"
''', '''            + "".join(f"<li>{c}</li>" for c in config.pide("fuentes", "creditos")) +
''', "los créditos de la planta, de fuentes.creditos; las librerías se quedan: mismo texto (comprobado abajo)")],
    ("ventana_focos", "VentanaFocos.<cuerpo>"): [("(solo modo CIRCE)", "(solo modo de edición)", COM + "sin el nombre de la entidad")],
    ("ventana_focos", "VentanaFocos.__init__"): [("self.editable = config.MODO_CIRCE\n", "self.editable = config.MODO_EDICION\n", MODO),
                                                 ('(" · modo CIRCE" if self.editable else "")', f'''(f" · {{{TX_MOD}}}" if self.editable else "")''', CIRCE)],
    ("vista_previa", "VistaPrevia.__init__"): [('        self._meta = json.loads((EJEMPLO / "ejemplo.json").read_text(encoding="utf-8"))\n', '        self._ejemplo = carpeta_ejemplo().resolve()\n        self._meta = json.loads((self._ejemplo / "ejemplo.json").read_text(encoding="utf-8"))\n', "el ejemplo, de operacion.ejemplo en planta.json: la misma carpeta")],
    ("vista_previa", "VistaPrevia._rellenar"): [('(EJEMPLO / f"penacho_{k}.png").as_uri()', '(self._ejemplo / f"penacho_{k}.png").as_uri()', "ver __init__"), ('(EJEMPLO / "viento.json").read_text', '(self._ejemplo / "viento.json").read_text', "ver __init__")],
}
QUITADOS = {("mapa_web", "_ATR_IGN"): "a fuentes.fondos de planta.json", ("mapa_web", "_ATR_OSM"): "a fuentes.fondos de planta.json", ("mapa_web", "_wmts_ign"): "solo montaba la URL del fondo: ya entera en fuentes.fondos", ("mapa_web", "FONDOS"): "a fuentes.fondos de planta.json: `fondos()`",
            ("panel", "ZONA"): "a proyeccion.zona_horaria de planta.json", ("vista_previa", "EJEMPLO"): "a operacion.ejemplo de planta.json: `self._ejemplo`"}
NUEVOS = {("mapa_web", "fondos"): "lee fuentes.fondos", ("panel", "texto_anios"): "«5 años», de reanalisis.anios"}

mal = 0
diferencias = []
iguales = 0
js_iguales = []
for mod in MODULOS:
    print(f"\n== {mod} ==")
    v_rel, n_rel = f"{GUI}{mod}.py", f"gui/{mod}.py"
    s0, s1 = viejo(v_rel), nuevo(n_rel)
    t0, t1 = tabla(s0), tabla(s1)
    for nombre in t0:
        if nombre not in t1:
            if (mod, nombre) in QUITADOS:
                print("quitado  ", nombre, "·", QUITADOS[(mod, nombre)])
                diferencias.append((mod, nombre, "quitado: " + QUITADOS[(mod, nombre)]))
            else:
                print("FALTA    ", nombre)
                mal += 1
            continue
        ta, tb = t0[nombre], t1[nombre]
        motivos = []
        for de, a_, motivo in ESPERADOS.get((mod, nombre), []):
            if ta.count(de) < 1:
                print("ESPERADO SIN USO", nombre, repr(de))
                mal += 1
            ta = ta.replace(de, a_)
            motivos.append(motivo)
        ta = renombra(ta)
        for de, a_ in IMPORTS:
            ta = ta.replace(de, a_)
        if ta != tb:
            print("DISTINTO ", nombre)
            for l in difflib.unified_diff(ta.splitlines(), tb.splitlines(), "esperado", "hay", lineterm="", n=0):
                print("   ", l[:300])
            mal += 1
            continue
        # sin motivos, el AST es el del original con la sustitución mecánica; con motivos, solo si son comentarios
        limpio = renombra(t0[nombre])
        for de, a_ in IMPORTS:
            limpio = limpio.replace(de, a_)
        if not nombre.endswith("<cuerpo>"):
            mismo = _ast(limpio) == _ast(tb)
            solo_com = motivos and all(m.startswith(COM) for m in motivos)
            if (not motivos and not mismo) or (solo_com and not mismo) or (motivos and not solo_com and mismo):
                print("EXPLICADO, PERO NO CUADRA CON EL AST", nombre)
                mal += 1
        if not motivos:
            iguales += 1
        else:
            print("explicado", nombre, "·", "; ".join(dict.fromkeys(motivos)))
            diferencias.append((mod, nombre, "; ".join(dict.fromkeys(motivos))))
        if nombre in ("_JS", "_CSS", "CSS_BASE"):
            js_iguales.append((mod, nombre, len(tb), "igual tras la sustitución del nombre" + (", salvo " + "; ".join(dict.fromkeys(motivos)) if motivos else "")))
    for nombre in t1:
        if nombre not in t0:
            if (mod, nombre) in NUEVOS:
                print("nuevo    ", nombre, "·", NUEVOS[(mod, nombre)])
                diferencias.append((mod, nombre, "nuevo: " + NUEVOS[(mod, nombre)]))
            else:
                print("SOBRA    ", nombre)
                mal += 1

print("\n== El JavaScript y el CSS, en cadenas de Python ==")
for fila in js_iguales:
    print(fila)
print("cuántas veces se ha sustituido el nombre:")
total = {}
for mod in MODULOS + ["penacho_3d"]:
    t = viejo(f"{GUI}{mod}.py")
    for de, a_ in RENOMBRES:
        n = len(re.findall(de, t))
        if n:
            total[(de, a_)] = total.get((de, a_), 0) + n
        t = re.sub(de, a_, t)
print({f"{k[0]} -> {k[1]}": v for k, v in total.items()})

print("\n== Diff entero tras la sustitución del nombre: también docstrings, comentarios sueltos e imports de arriba ==")
for mod in MODULOS:
    print(f"--- {mod}")
    for linea in difflib.unified_diff(renombra(viejo(f"{GUI}{mod}.py")).splitlines(), nuevo(f"gui/{mod}.py").splitlines(), lineterm="", n=0):
        if not linea.startswith(("---", "+++", "@@")):
            print(linea[:260])

print("\n== Caracteres invisibles, original -> nuevo ==")
cuenta = lambda t: {RARO[ord(c)]: t.count(c) for c in set(t) if ord(c) in RARO}
for mod in MODULOS:
    a, b = cuenta(viejo(f"{GUI}{mod}.py")), cuenta(nuevo(f"gui/{mod}.py"))
    print(mod, a, "->", b)
    mal += a != b

print("\n== Los recursos del visor: los bytes de git ==")
for nombre in ("LICENSE-three.txt", "OrbitControls.js", "plantilla.html", "three.min.js"):
    a = _git(PLANTA, COMMIT, f"{GUI}recursos/visor3d/{nombre}")
    b = (CORE / "gui/recursos/visor3d" / nombre).read_bytes()
    print(nombre, len(a), "bytes, igual:", a == b)
    mal += a != b
    ausente = not (PLANTA / GUI / "recursos/visor3d" / nombre).exists()
    print("   ya no está en la planta:", ausente)
    mal += not ausente
for rel in ("recursos/visor3d/ortofoto.jpg", "recursos/ejemplo/ejemplo.json", "recursos/ejemplo/viento.json", "recursos/ejemplo/penacho_0.png", "recursos/ejemplo/penacho_1.png"):
    ok = (PLANTA / GUI / rel).read_bytes() == _git(PLANTA, COMMIT, GUI + rel) or (PLANTA / GUI / rel).read_bytes().replace(b"\r\n", b"\n") == _git(PLANTA, COMMIT, GUI + rel)
    print(rel, "sigue en la planta, igual:", ok)
    mal += not ok

print("\n== Lo que no puede quedar en el core ==")
vigilados = [*(CORE / "gui").glob("*.py"), CORE / "gui" / "recursos" / "visor3d" / "plantilla.html"]
patrones = [r"\bence\b", r"\bence-", r"enceViento", r"\bENCE", r"[Gg]alera", r"CIRCE|\bcirce\b", r"Dacame", r"Madrid", r"PNOA", r"\bIGN\b", r"\bOSM\b", r"OpenStreetMap", r"Catastro", r"CORINE", r"CartoCiudad", r"Meteocat", r"202[0-5]\b", r"5 años",
            r"CALPUFF|CALMET|AERMOD|AERMET|AERMAP|MAKEGEO|BPIP", r"99-Test", r"Santa B", r"Montsi", r"Tarragona"]
for f in vigilados:
    t = f.read_text(encoding="utf-8")
    for p in patrones:
        for m in re.finditer(p, t):
            ini = t.rfind("\n", 0, m.start()) + 1
            print("HAY", p, "en", f.name, ":", t[ini:ini + 150].strip())
            mal += 1

print("\n== Imports de nivel superior de los módulos sin Qt ==")
for nombre in ("web", "penacho_3d", "principal", "__init__"):
    fuera = []
    for n in ast.parse(nuevo(f"gui/{nombre}.py")).body:
        if isinstance(n, ast.Import):
            fuera += [a.name for a in n.names]
        elif isinstance(n, ast.ImportFrom):
            fuera += [f"{n.module}.{a.name}" for a in n.names]
    print(nombre, fuera)
    mal += any(x.startswith(("PySide6", "folium", "pyvista", "galera")) for x in fuera)
for f in (CORE / "gui").glob("*.py"):
    mal_import = re.findall(r"(?m)^\s*(?:from|import) galera\b.*$", f.read_text(encoding="utf-8"))
    if mal_import:
        print("IMPORTA GALERA", f.name, mal_import)
        mal += 1

print("\n== Constantes del original frente a planta.json ==")
if os.environ.get("T8_PAQUETES"):
    sys.path.insert(0, os.environ["T8_PAQUETES"])
    import teodors  # noqa: F401
sys.path[:0] = [str(PLANTA / "lib" / "paquetes"), str(PLANTA / "lib")]
trabajo = Path(tempfile.mkdtemp(prefix="t8_"))
os.environ["ENCE_GALERA_LOCAL"] = str(trabajo / "local")
os.environ["QT_QPA_PLATFORM"] = "offscreen"
os.environ["QT_QPA_FONTDIR"] = r"C:\Windows\Fonts"
from PySide6 import QtCore, QtWebEngineWidgets, QtWidgets  # noqa: E402,F401

QtCore.QSettings.setPath(QtCore.QSettings.Format.IniFormat, QtCore.QSettings.Scope.UserScope, str(trabajo / "ajustes"))
config = importlib.import_module("galera.gui.config")
pj = json.loads((PLANTA / GUI / "planta/planta.json").read_text(encoding="utf-8"))
pj0 = json.loads(viejo(GUI + "planta/planta.json"))
mw0 = ast.parse(viejo(GUI + "mapa_web.py"))
ns = {}
exec(compile(ast.Module([n for n in mw0.body if (isinstance(n, ast.Assign) and n.targets[0].id in ("_ATR_IGN", "_ATR_OSM", "FONDOS")) or (isinstance(n, ast.FunctionDef) and n.name == "_wmts_ign")], []), "fondos", "exec"), ns)
mw = importlib.import_module("galera.gui.mapa_web")
tm = importlib.import_module("galera.gui.tema")
pn = importlib.import_module("galera.gui.panel")
ve = importlib.import_module("galera.gui.ventana")
main0 = viejo("main.py")
comprobaciones = [
    ("fondos: los mismos, con su URL y su atribución enteras", mw.fondos() == ns["FONDOS"] and mw.FONDOS == ns["FONDOS"]),
    ("identificador de Windows, el mismo", f'"{pj["identidad"]["app_id"]}"' in main0),
    ("fichero de ajustes y organización, los mismos", pj["identidad"]["ajustes"] == "ENCE_Galera" and pj["identidad"]["organizacion"] == "CIRCE" and Path(tm.ajustes().fileName()).parts[-2:] == ("CIRCE", "ENCE_Galera.ini")),
    ("zona horaria del panel, la misma", str(pn.ZONA) == "Europe/Madrid"),
    ("«5 años»", pn.texto_anios() == "5 años"),
    ("fecha mínima del periodo", config.REANALISIS_ANIOS[0] == 2021),
    ("versión de la app, la misma", pj["identidad"]["version"] == importlib.import_module("galera").__version__ == "0.1.0"),
    ("--circe: la misma opción y el mismo valor de la variable", config.CLAVE_EDICION == "circe" and config.nombre_env("MODO") == "ENCE_GALERA_MODO"),
    ("el texto del modo de edición", pj["operacion"]["texto_modo_edicion"] == "modo CIRCE"),
    ("la carpeta del ejemplo, la misma", importlib.import_module("galera.gui.vista_previa").EJEMPLO == (PLANTA / GUI / "recursos" / "ejemplo").resolve()),
    ("el proveedor y los servicios, los que decía el código", (pj["estaciones"]["proveedor"], pj["fuentes"]["mdt"], pj["fuentes"]["usos"], pj["fuentes"]["edificios"], pj["fuentes"]["nombres_nucleos"]) == ("Meteocat", "IGN", "CORINE", "Catastro", "CartoCiudad (IGN)")),
]
# «Acerca de»: el texto entero, el original evaluado desde git frente al que da el código nuevo
caja = {}
QtWidgets.QMessageBox.about = staticmethod(lambda padre, titulo, texto: caja.update(titulo=titulo, texto=texto))
ve.VentanaPrincipal._acerca_de(object())
arbol = next(n for n in ast.walk(ast.parse(viejo(GUI + "ventana.py"))) if isinstance(n, ast.FunctionDef) and n.name == "_acerca_de")
llamada = next(n for n in ast.walk(arbol) if isinstance(n, ast.Call) and getattr(n.func, "attr", "") == "about")
texto0 = eval(compile(ast.Expression(llamada.args[2]), "acerca", "eval"), {"config": config, "__version__": "0.1.0"})
comprobaciones.append(("«Acerca de», el mismo texto", texto0 == caja["texto"] and caja["titulo"] == "Acerca de"))
quita = {"identidad": {"ajustes", "app_id", "version", "entidad", "red_datos", "nota"}, "estaciones": {"proveedor"}, "fuentes": {"mdt", "usos", "edificios", "nombres_nucleos", "fondos", "creditos", "nota"}, "operacion": {"texto_modo_edicion", "nota"}}
for bloque in pj0:
    if isinstance(pj0[bloque], dict):
        a = {k: v for k, v in pj0[bloque].items() if k not in quita.get(bloque, ())}
        b = {k: v for k, v in pj[bloque].items() if k not in quita.get(bloque, ())}
        comprobaciones.append((f"planta.json, bloque {bloque}: lo de antes, igual", a == b))
comprobaciones.append(("planta.json: ningún bloque nuevo, solo campos", set(pj) == set(pj0)))
for texto, ok in comprobaciones:
    print(texto, ok)
    mal += not ok

print("\n== Envoltorios: cada nombre del original sigue, también los privados y los importados ==")
PERMITIDOS = {"__version__", "_ATR_IGN", "_ATR_OSM", "_wmts_ign", "Path", "km", "_km"}
for mod in MODULOS:
    m = importlib.import_module(f"galera.gui.{mod}")
    nombres = {k.split(".")[0] for k in tabla(viejo(f"{GUI}{mod}.py"))}
    for n in ast.parse(viejo(f"{GUI}{mod}.py")).body:
        if isinstance(n, (ast.Import, ast.ImportFrom)):
            nombres |= {(a.asname or a.name).split(".")[0] for a in n.names}
    faltan = sorted(n for n in nombres if not hasattr(m, n))
    print(mod, len(nombres), "nombres; sin él:", faltan)
    mal += bool(set(faltan) - PERMITIDOS)
    definidos = [n.name if isinstance(n, (ast.FunctionDef, ast.ClassDef)) else "=" for n in ast.parse((PLANTA / GUI / f"{mod}.py").read_text(encoding="utf-8")).body if isinstance(n, (ast.FunctionDef, ast.ClassDef, ast.Assign))]
    mal += bool(set(definidos) - {"__getattr__"})
for mod in ("penacho_3d",):
    m = importlib.import_module(f"galera.gui.{mod}")
    ok = all(hasattr(m, n) for n in ("abrir", "calcular", "pagina", "RECURSOS", "SEMILADO_VISTA", "lista", "_correr", "_rotulos"))
    print("penacho_3d: abrir, calcular, pagina y lo de operacion:", ok)
    mal += not ok

print("\n== Estado de módulo: los mismos objetos por las dos vías ==")
from teodors import planta as planta_core  # noqa: E402
from teodors.gui import focos_mapa as fm_core, mapa as mapa_core, mapa_web as mw_core, panel as panel_core, tema as tema_core, ventana as v_core, ventana_focos as vf_core, web as web_core, widgets as w_core  # noqa: E402

ok = tm.T is tema_core.T and tm.avisos is tema_core.avisos and tm.TEMAS is tema_core.TEMAS
print("tema.T, tema.avisos y tema.TEMAS, los mismos:", ok)
mal += not ok
app = QtWidgets.QApplication(sys.argv[:1])
tm.aplicar(app)
fondo0, avisos = tm.T["fondo"], []
tm.avisos.cambiado.connect(lambda: avisos.append(1))
referencia = tm.T
tm.poner("claro")
ok = tm.T is referencia and tema_core.T is referencia and tm.T["fondo"] == tema_core.TEMAS["claro"]["colores"]["fondo"] != fondo0 and avisos == [1] and tm.estilo_actual() == "claro" and tm._estilo_actual == "claro"
print("tema.poner cambia T en su sitio y avisa, por las dos vías:", ok)
mal += not ok
tm.poner("oscuro")

print("\n== Lo que se pone en un envoltorio llega al código movido ==")
falso = lambda *a, **k: None
F = importlib.import_module("galera.gui.focos")
from teodors.operacion import focos as f_core  # noqa: E402

orig = F.guardar
F.guardar = falso
ok = f_core.guardar is falso
F.guardar = orig
print("F.guardar:", ok and f_core.guardar is orig)
mal += not ok
for m, core, nombre in ((importlib.import_module("galera.gui.web"), web_core, "_descarga"), (importlib.import_module("galera.gui.widgets"), w_core, "preguntar_si_guardar"), (importlib.import_module("galera.gui.ventana_focos"), vf_core, "preguntar_si_guardar"),
                        (importlib.import_module("galera.gui.mapa_web"), mw_core, "escribir_mapa_base"), (importlib.import_module("galera.gui.ventana"), v_core, "Trabajo")):
    orig = getattr(m, nombre)
    setattr(m, nombre, falso)
    ok = getattr(core, nombre) is falso and getattr(m, nombre) is falso
    setattr(m, nombre, orig)
    ok = ok and getattr(core, nombre) is orig
    print(f"{m.__name__}.{nombre}:", ok)
    mal += not ok
config.MODO_CIRCE = True
ok = planta_core.MODO_EDICION is True and config.MODO_CIRCE is True
config.MODO_CIRCE = False
ok = ok and planta_core.MODO_EDICION is False and config.MODO_CIRCE is False
print("config.MODO_CIRCE llega a planta.MODO_EDICION, que es lo que lee la interfaz:", ok)
mal += not ok
ok = fm_core.PaginaMapa is mapa_core.PaginaMapa and importlib.import_module("galera.gui.mapa").PaginaMapa is mapa_core.PaginaMapa and importlib.import_module("galera.gui.ventana").VentanaPrincipal is v_core.VentanaPrincipal and importlib.import_module("galera.gui.panel").Panel is panel_core.Panel
print("las clases, las mismas por las dos vías:", ok)
mal += not ok

print("\n== Con los datos: el código original, sacado de git, frente al nuevo; los dos sin ventanas de verdad ==")
datos = os.environ.get("ENCE_GALERA_DATOS")
if not datos:
    print("sin ENCE_GALERA_DATOS: no se comprueba")
else:
    viejo_dir = trabajo / "viejo"
    for repo, rev, rutas, destino in ((PLANTA, COMMIT, ["lib/galera", "lib/paquetes"], viejo_dir), (REPO_CORE, COMMIT_CORE, ["core"], viejo_dir / "lib" / "teodors")):
        crudo = subprocess.run(["git", "-C", str(repo), "archive", rev, *rutas], capture_output=True, check=True).stdout
        destino.mkdir(parents=True, exist_ok=True)
        with tarfile.open(fileobj=io.BytesIO(crudo)) as tar:
            tar.extractall(destino, filter="data")
    SONDA = r'''
import hashlib, json, os, sys, time
from pathlib import Path
salida = Path(sys.argv[1])
salida.mkdir(parents=True, exist_ok=True)
sys.stdout.reconfigure(encoding="utf-8")
from PySide6 import QtCore, QtWebEngineWidgets, QtWidgets
QtCore.QSettings.setPath(QtCore.QSettings.Format.IniFormat, QtCore.QSettings.Scope.UserScope, str(salida / "ajustes"))
QtCore.QCoreApplication.setAttribute(QtCore.Qt.ApplicationAttribute.AA_ShareOpenGLContexts)
app = QtWidgets.QApplication(sys.argv[:1])
from galera.gui import config, focos_mapa, mapa_web, penacho_3d, tema, web
import teodors
print("teodors:", teodors.__file__, file=sys.stderr)
tema.aplicar(app)
web._descarga = lambda *a, **k: None
emp = config.cargar_emplazamiento()
r = {}
r["mapa_base"] = Path(mapa_web.escribir_mapa_base(emp, [[40.4, 0.2], [40.9, 0.8]], salida / "mapa_base.html", autonomo=False)).read_text(encoding="utf-8")
r["mapa_focos"] = Path(focos_mapa.escribir_html(emp, salida / "mapa_focos.html")).read_text(encoding="utf-8")
r["css_tema"] = mapa_web.css_tema()
r["rosa"] = mapa_web.rosa_svg([[1.0, 2.0, 3.0, 0.5, 0.2]] * 16, [0.5, 1, 2, 4, 6]) + mapa_web.leyenda_rosa([0.5, 1, 2, 4, 6], 3.0, 10.0)
r["ficha"] = mapa_web.ficha_html("T", [("a", "b")])
datos3d = {"firma": "x", "titulo": "Plan «Base» · Olor", "dia": "d", "unidad": "ou_E/m³", "niveles": ["1"], "horas": [], "horas_utc": [], "escala_m": 0.25, "terreno": {}, "rotulos": [], "segundos": 1.0}
r["pagina_3d"] = hashlib.sha256(Path(penacho_3d.pagina(datos3d)).read_bytes()).hexdigest()

def letra(w):
    for nombre in ("text", "title", "windowTitle", "placeholderText", "toolTip", "styleSheet"):
        if hasattr(w, nombre) and callable(getattr(w, nombre)):
            try:
                v = getattr(w, nombre)()
            except TypeError:
                continue
            if isinstance(v, str) and v:
                yield nombre, v

def arbol(raiz):
    filas = []
    for w in [raiz] + raiz.findChildren(QtWidgets.QWidget):
        if isinstance(w, QtWidgets.QComboBox):
            extra = [w.itemText(i) for i in range(w.count())]
        else:
            extra = None
        filas.append([type(w).__name__, w.objectName(), sorted(letra(w)), extra])
    return filas

def acciones(menu):
    filas = []
    for a in menu.actions():
        filas.append([a.text(), a.shortcut().toString()])
        if a.menu():
            filas.append(acciones(a.menu()))
    return filas

def pixeles(w):
    im = w.grab().toImage().convertToFormat(w.grab().toImage().Format.Format_ARGB32)
    return [im.width(), im.height(), hashlib.sha256(bytes(im.constBits())).hexdigest()]

def espera(segundos, hasta=lambda: False):
    fin = time.time() + segundos
    while time.time() < fin and not hasta():
        app.processEvents()
        time.sleep(0.02)

from galera.gui.ventana import VentanaPrincipal
v = VentanaPrincipal()
v.resize(1500, 950)
v.show()
espera(40, lambda: v.mapa._listo)
espera(3)
r["listo"] = v.mapa._listo
r["titulo"] = v.windowTitle()
r["menu"] = acciones(v.menu_app)
r["arbol_ventana"] = arbol(v)
r["paginas"] = {}
for est in list(tema.TEMAS):
    tema.poner(est)
    espera(0.2)
    for clave, *_ in v.panel.PAGINAS:
        v.panel.ir_a(clave)
        espera(0.1)
        r["paginas"][f"{est}/{clave}"] = pixeles(v.panel)
tema.poner("oscuro")
aj = QtCore.QSettings(str(salida / "aj.ini"), QtCore.QSettings.Format.IniFormat)
from galera.gui.ventana_focos import VentanaFocos
from galera.gui.ventana_planes import VentanaPlanes
from galera.gui.ventana_ajustes import VentanaAjustes
for nombre, circe in (("focos_operario", False), ("focos_edicion", True)):
    config.MODO_CIRCE = circe
    w = VentanaFocos(emp, aj)
    r["arbol_" + nombre] = arbol(w)
    r["titulo_" + nombre] = w.windowTitle()
    w._sucio = False
    w.close()
config.MODO_CIRCE = False
w = VentanaPlanes(emp, aj)
r["arbol_planes"] = arbol(w)
w._sucio = False
w.close()
w = VentanaAjustes(emp, None)
r["arbol_ajustes"] = arbol(w)
w.close()
(salida / "salida.json").write_text(json.dumps(r, ensure_ascii=False), encoding="utf-8")
print("hecho", flush=True)
os._exit(0)
'''
    def lanza(nombre, camino):
        env = dict(os.environ, PYTHONPATH=os.pathsep.join(camino), PYTHONIOENCODING="utf-8", ENCE_GALERA_LOCAL=str(trabajo / f"local_{nombre}"))
        env.pop("TEODORS_PLANTA", None)
        cache = Path(os.environ.get("TEMP", "")) / "ence_galera" / "web_assets"
        (trabajo / f"local_{nombre}").mkdir(parents=True, exist_ok=True)
        if cache.is_dir():
            import shutil
            shutil.copytree(cache, trabajo / f"local_{nombre}" / "web_assets")
        r = subprocess.run([sys.executable, "-c", SONDA, str(trabajo / f"sonda_{nombre}")], capture_output=True, text=True, encoding="utf-8", errors="replace", env=env, cwd=str(trabajo), timeout=300)
        origen = next((l for l in r.stderr.splitlines() if l.startswith("teodors:")), "?")
        print(nombre, origen, "· salida", r.returncode, r.stdout.strip()[-200:])
        if r.returncode != 0 or not (trabajo / f"sonda_{nombre}" / "salida.json").is_file():
            print([l for l in r.stderr.splitlines() if "shared_image" not in l][-30:])
            return None
        return json.loads((trabajo / f"sonda_{nombre}" / "salida.json").read_text(encoding="utf-8"))

    camino_nuevo = ([os.environ["T8_PAQUETES"]] if os.environ.get("T8_PAQUETES") else []) + [str(PLANTA / "lib" / "paquetes"), str(PLANTA / "lib")]
    r0 = lanza("viejo", [str(viejo_dir / "lib" / "paquetes"), str(viejo_dir / "lib")])
    r1 = lanza("nuevo", camino_nuevo)
    if r0 is None or r1 is None:
        print("LA SONDA FALLA")
        mal += 1
    else:
        def sin_ids(t):
            vistos = {}
            return re.sub(r"[0-9a-f]{32}", lambda m: vistos.setdefault(m.group(0), f"id{len(vistos)}"), t)

        for clave in ("mapa_base", "mapa_focos"):
            a, b = sin_ids(renombra(r0[clave])), sin_ids(r1[clave])
            # los dos comentarios de JavaScript que han cambiado, y solo esos
            a = a.replace("// modo dibujo (CIRCE):", "// modo dibujo (edición):").replace("// A menos del radio del segmento planta-Dacame manda este motor", "// A menos del radio del segmento entre los dos puntos de la planta manda este motor")
            print(clave, len(a), "caracteres; igual byte a byte, tras la sustitución del nombre y los 2 comentarios de JavaScript:", a == b)
            mal += a != b
            if a != b:
                for l in list(difflib.unified_diff(a.splitlines(), b.splitlines(), lineterm="", n=0))[:20]:
                    print("   ", l[:300])
        for clave in ("css_tema", "rosa", "ficha", "pagina_3d", "listo", "titulo", "menu", "titulo_focos_operario", "titulo_focos_edicion"):
            a = json.dumps(r0[clave], ensure_ascii=False)
            a = renombra(a)
            b = json.dumps(r1[clave], ensure_ascii=False)
            print(clave, "igual:", a == b)
            mal += a != b
        print("título con el modo de edición:", r1["titulo_focos_edicion"])
        for clave in ("arbol_ventana", "arbol_focos_operario", "arbol_focos_edicion", "arbol_planes", "arbol_ajustes"):
            ok = r0[clave] == r1[clave]
            print(clave, len(r1[clave]), "widgets; clase, nombre, textos, estilos y listas, igual:", ok)
            mal += not ok
            if not ok:
                for x, y in zip(r0[clave], r1[clave]):
                    if x != y:
                        print("   ", str(x)[:300], "\n    ", str(y)[:300])
                        break
        ok = r0["paginas"] == r1["paginas"]
        print(len(r1["paginas"]), "páginas del panel × estilo: los mismos píxeles:", ok, "· tamaño", next(iter(r1["paginas"].values()))[:2])
        mal += not ok
        if not ok:
            print([k for k in r0["paginas"] if r0["paginas"][k] != r1["paginas"].get(k)])

print("\n== Diferencias, para el informe ==")
for f, n, motivo in diferencias:
    print(f"{f} · {n}: {motivo}")
print(f"\n{iguales} nombres iguales en texto y AST tras la sustitución mecánica, {len(diferencias)} con su explicación")
print("RESULTADO:", "todo igual, salvo lo que se dice" if not mal else f"{mal} distintos")
sys.exit(1 if mal else 0)
