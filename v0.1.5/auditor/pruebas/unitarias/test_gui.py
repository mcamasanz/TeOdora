# -*- coding: utf-8 -*-
"""gui · humo de la interfaz, SIN RED, sin ventanas de verdad (plataforma offscreen) y con una planta inventada a propósito: que importe, que no arrastre a Qt fuera de su paquete, que lo de cada planta salga de su
carpeta y que nada de otra planta se cuele. Sin PySide6 o sin folium, las pruebas que los necesitan no se ejecutan (`teodors[pruebas_gui]`, que usa la integración continua). El mapa de verdad, con el
contenido web, no se puede comprobar aquí: en offscreen sale en blanco."""
import json
import os
import re
import socket
import subprocess
import sys
import tomllib
from importlib.util import find_spec
from pathlib import Path

import pytest

from teodors import planta
from teodors.comun.errores import Cancelado
from teodors.gui import penacho_3d as P3D, principal, web

RAIZ = Path(__file__).resolve().parents[3]
GUI = RAIZ / "core" / "gui"
con_qt = pytest.mark.skipif(find_spec("PySide6") is None or find_spec("folium") is None, reason="sin teodors[pruebas_gui]")
# Lo que no puede salir en ninguna planta distinta de la suya
AJENO = re.compile(r"Galera|\bENCE\b|\bence\b|\bence-|CIRCE|Dacame|Montsià|Tarragona|Europe/Madrid|PNOA|\bIGN\b|\bOSM\b|OpenStreetMap|Catastro|CORINE|CartoCiudad|Meteocat|scne\.es")
JSON_PLANTA = {
    "formato": 1,
    "identidad": {"app_nombre": "Inventada · Prueba", "organizacion": "ORG_X", "ajustes": "Ajustes_X", "app_id": "ORG.X.Prueba", "version": "9.9", "entidad": "Empresa X", "red_datos": "la red X",
                  "prefijo_env": "PRUEBA_GUI", "carpeta_local": "prueba_gui", "registro": "prueba_gui"},
    "proyeccion": {"epsg": "EPSG:25831", "crs_geo": "EPSG:4258", "zona_horaria": "Atlantic/Canary"},
    "dominio": {"lado_km": 3, "margen_m": 250, "res_terreno_m": 25, "radio_edificios_km": 1.5, "radio_edificios_focos_m": 150, "celda_viento_m": 100, "zface": [0, 20, 40, 80]},
    "receptores": {"por_km2": 5, "niveles": [["a", 100.0, 500.0], ["b", 400.0, None]], "estilos": {"a": ["#ff0000", 2, "A"], "b": ["#00ff00", 2, "B"]}},
    "reanalisis": {"anios": [2019, 2020, 2021]},
    "estaciones": {"proveedor": "Proveedor X"},
    "series": {"era5": "serie_a", "gfs": "serie_b", "preferidas": ["serie_a"], "titulos": {}},
    "fuentes": {"mdt": "Mdt X", "usos": "Usos X", "edificios": "Edificios X", "nombres_nucleos": "Nombres X", "fondos": [["Fondo X", "http://127.0.0.1:9/{z}/{x}/{y}.png", "Atribución X", 18]], "creditos": ["Crédito X"]},
    "operacion": {"modo_edicion": "edicion", "texto_modo_edicion": "modo X", "ejemplo": "ejemplo"},
    "visor3d": {"ortofoto": "ortofoto.jpg", "semilado_m": 400.0, "credito": "Crédito de la ortofoto X"},
}


def _escribe_planta(carpeta):
    carpeta.mkdir(parents=True, exist_ok=True)
    (carpeta / "planta.json").write_text(json.dumps(JSON_PLANTA), encoding="utf-8")
    (carpeta / "emplazamiento.json").write_text(json.dumps({"nombre": "Prueba", "lat": 38.6, "lon": 1.4}), encoding="utf-8")
    (carpeta / "focos.json").write_text(json.dumps({"formato": 2, "epsg": "EPSG:25831", "focos": []}), encoding="utf-8")
    (carpeta / "ortofoto.jpg").write_bytes(b"\xff\xd8\xff")


@pytest.fixture(autouse=True)
def sin_red_y_con_planta(tmp_path, monkeypatch):
    def sin_red(*a, **k):
        raise AssertionError("una prueba ha intentado salir a la red")
    monkeypatch.setattr(socket.socket, "connect", sin_red)
    monkeypatch.setattr(socket, "getaddrinfo", sin_red)
    monkeypatch.setenv("PRUEBA_GUI_DATOS", str(tmp_path / "datos"))
    monkeypatch.setenv("PRUEBA_GUI_LOCAL", str(tmp_path / "local"))
    monkeypatch.setenv("QT_QPA_PLATFORM", "offscreen")
    monkeypatch.setenv("QT_QPA_FONTDIR", r"C:\Windows\Fonts")
    (tmp_path / "datos").mkdir()
    _escribe_planta(tmp_path / "planta")
    planta.desactivar()
    planta.activar(tmp_path / "planta")
    yield
    planta.desactivar()


@pytest.fixture
def app(tmp_path, monkeypatch):
    """La QApplication, con los ajustes en una carpeta temporal: nunca los del usuario."""
    from PySide6 import QtCore, QtWebEngineWidgets, QtWidgets  # noqa: F401  (WebEngine, antes de la QApplication: lo importa otra prueba)
    QtCore.QSettings.setPath(QtCore.QSettings.Format.IniFormat, QtCore.QSettings.Scope.UserScope, str(tmp_path / "ajustes"))
    QtCore.QCoreApplication.setAttribute(QtCore.Qt.ApplicationAttribute.AA_ShareOpenGLContexts)
    return QtWidgets.QApplication.instance() or QtWidgets.QApplication(["prueba"])


def _hijo(codigo, tmp_path, *args, timeout=60):
    """Un proceso aparte, con la planta inventada de esta prueba."""
    r = subprocess.run([sys.executable, "-c", codigo, *args], capture_output=True, text=True, encoding="utf-8", errors="replace", cwd=tmp_path, timeout=timeout, env=dict(os.environ, PYTHONIOENCODING="utf-8"))
    assert r.returncode == 0, "\n".join(l for l in r.stderr.splitlines() if "shared_image" not in l)[-1500:]
    return r.stdout


# ------------------------------------------------------------------------------ que no arrastre a Qt
def test_nada_fuera_de_la_interfaz_carga_qt_ni_folium(tmp_path):
    # quien no instale teodors[gui] tiene que poder usar todo lo demás. También se importa sin planta activa: leerla al importar fallaría aquí
    codigo = """
import importlib, pkgutil, sys
import teodors
CON_QT = {"consola", "focos_mapa", "mapa", "mapa_web", "panel", "tema", "terminal", "trabajos", "ventana", "ventana_ajustes", "ventana_focos", "ventana_planes", "vista_3d", "vista_previa", "widgets"}
hechos = []
for m in pkgutil.walk_packages(teodors.__path__, "teodors."):
    if m.name.endswith(("__main__", "_nucleo_gen")) or m.name.split(".")[-1] in CON_QT and m.name.startswith("teodors.gui."):
        continue
    importlib.import_module(m.name)
    hechos.append(m.name)
print(len(hechos), "teodors.gui.principal" in hechos, "teodors.gui.web" in hechos, "teodors.gui.penacho_3d" in hechos, "teodors.operacion.simulacion" in hechos, sorted(x for x, m in sys.modules.items() if m is not None and x.split(".")[0] in ("PySide6", "folium", "shiboken6", "branca", "pyvista")))
"""
    env_planta = os.environ.pop(planta.ENV_PLANTA)                  # sin planta activa
    try:
        salida = _hijo(codigo, tmp_path).split()
    finally:
        os.environ[planta.ENV_PLANTA] = env_planta
    assert int(salida[0]) > 100 and salida[1:5] == ["True"] * 4
    assert salida[5:] == ["[]"]


@con_qt
def test_importar_la_interfaz_no_lee_ninguna_planta(tmp_path):
    codigo = """
import importlib, pkgutil
from teodors import planta, gui
for m in pkgutil.iter_modules(gui.__path__, "teodors.gui."):
    importlib.import_module(m.name)
print(planta._activa is None)
"""
    env_planta = os.environ.pop(planta.ENV_PLANTA)
    try:
        assert _hijo(codigo, tmp_path).strip() == "True"
    finally:
        os.environ[planta.ENV_PLANTA] = env_planta


def test_el_paquete_instalado_lleva_la_interfaz_y_el_extra_es_aparte():
    py = tomllib.loads((RAIZ / "pyproject.toml").read_text(encoding="utf-8"))
    conf = py["tool"]["setuptools"]
    assert "teodors.gui" in conf["packages"]
    ficheros = [f.relative_to(GUI) for f in GUI.rglob("*") if f.is_file() and f.suffix not in (".py", ".pyc", ".md")]
    assert {"plantilla.html", "three.min.js", "OrbitControls.js", "LICENSE-three.txt"} == {f.name for f in ficheros}
    for f in ficheros:
        assert any(f.match(p) for p in conf["package-data"]["teodors.gui"]), f
    # Qt, solo en sus extras: digicompost y los demás no lo heredan
    extras = py["project"]["optional-dependencies"]
    con_extra = {k for k, v in extras.items() if any(x.startswith(("PySide6", "folium")) for x in v)}
    assert con_extra == {"gui", "gui3d", "pruebas_gui"}
    assert not any("PySide6" in x or "folium" in x for x in py["project"]["dependencies"])
    assert any(x.startswith("pyvista") for x in extras["gui3d"]) and not any(x.startswith("pyvista") for x in extras["gui"])
    assert set(extras["fuentes"]) <= set(extras["gui"])


def test_readme_con_sus_ficheros():
    tabla = (GUI / "README.md").read_text(encoding="utf-8").split("## Ficheros")[1]
    for f in GUI.glob("*.py"):
        assert f.name == "__init__.py" or f"`{f.name}`" in tabla, f.name
    # lo que pide a la planta está en su tabla
    entera = (GUI / "README.md").read_text(encoding="utf-8")
    for bloque, clave in principal.CAMPOS:
        assert clave in entera, clave


# ------------------------------------------------------------------------------ el arranque
@pytest.mark.parametrize("argv, clave, sale, queda", [
    (["x"], "edicion", dict(dia=None, edicion=False, focos=False, planes=False), ["x"]),
    (["x", "--dia", "2024-01-02", "--edicion", "--focos", "--planes"], "edicion", dict(dia="2024-01-02", edicion=True, focos=True, planes=True), ["x"]),
    (["x", "--focos", "-platform", "offscreen"], "edicion", dict(dia=None, edicion=False, focos=True, planes=False), ["x", "-platform", "offscreen"]),
    (["x", "--mio", "--edicion"], "mio", dict(dia=None, edicion=True, focos=False, planes=False), ["x", "--edicion"]),      # la opción es la de la planta
    (["x", "--dia"], "edicion", dict(dia=None, edicion=False, focos=False, planes=False), ["x"]),
])
def test_opciones_sin_crear_ninguna_ventana(argv, clave, sale, queda):
    assert principal.opciones(argv, clave) == sale
    assert argv == queda


@pytest.mark.parametrize("bloque, clave", [("identidad", "ajustes"), ("identidad", "app_id"), ("fuentes", "fondos"), ("fuentes", "creditos"), ("estaciones", "proveedor"), ("operacion", "texto_modo_edicion")])
def test_si_a_la_planta_le_falta_algo_el_arranque_dice_que(tmp_path, bloque, clave):
    principal.comprobar_planta()                                    # la inventada lo tiene todo
    datos = json.loads(json.dumps(JSON_PLANTA))
    del datos[bloque][clave]
    (tmp_path / "planta" / "planta.json").write_text(json.dumps(datos), encoding="utf-8")
    planta.activar(tmp_path / "planta")
    with pytest.raises(ValueError, match=f"{bloque}.{clave}"):
        principal.comprobar_planta()


@con_qt
def test_la_ventana_entera_sale_de_la_planta_inventada(tmp_path):
    # el main() de verdad, en un proceso aparte: nombre, ajustes, identificador y modo de edición son los de la planta, y en toda la ventana no hay nada de otra. Offscreen, sin esperar al mapa: sale en blanco
    codigo = r"""
import ctypes, json, os, sys
from pathlib import Path
os.environ["QTWEBENGINE_CHROMIUM_FLAGS"] = "--host-resolver-rules=\"MAP * ~NOTFOUND\""
from PySide6 import QtCore, QtWebEngineWidgets, QtWidgets
QtCore.QSettings.setPath(QtCore.QSettings.Format.IniFormat, QtCore.QSettings.Scope.UserScope, sys.argv[1])
from teodors import planta
from teodors.gui import principal, web, tema
web._descarga = lambda *a, **k: None
planta.activar(sys.argv[2])
ids = []
ctypes.windll.shell32.SetCurrentProcessExplicitAppUserModelID = ids.append
sale = {}
real = QtWidgets.QApplication.exec

def exec_y_cerrar(*_a):
    app = QtWidgets.QApplication.instance()
    def mira():
        v = next(w for w in app.topLevelWidgets() if type(w).__name__ == "VentanaPrincipal")
        filas = [v.windowTitle()]
        for w in v.findChildren(QtWidgets.QWidget):
            for n in ("text", "title", "toolTip"):
                x = getattr(w, n, None)
                if callable(x):
                    filas.append(str(x()))
        def menu(m):
            for a in m.actions():
                filas.append(a.text())
                if a.menu():
                    menu(a.menu())
        menu(v.menu_app)
        sale.update(titulo=v.windowTitle(), rotulo=v.findChild(QtWidgets.QLabel, "app_titulo").text(), app=app.applicationName(), org=app.organizationName(), textos=filas, ajustes=tema.ajustes().fileName(),
                    fecha_min=v.panel.fecha_periodo.minimumDate().toString("yyyy-MM-dd"), anios=v.panel.b_simular.text(), edicion=planta.MODO_EDICION, env=os.environ.get("PRUEBA_GUI_MODO"), ids=ids, argv=sys.argv[1:])
        v.close()
        QtCore.QTimer.singleShot(200, app.quit)
    QtCore.QTimer.singleShot(300, mira)
    return real()

QtWidgets.QApplication.exec = exec_y_cerrar
sys.argv = ["x", "--edicion", "--dia", "2020-05-05"]
codigo = principal.main()
print("@@" + json.dumps(dict(sale, codigo=codigo)), flush=True)
os._exit(0)
"""
    (tmp_path / "ajustes").mkdir()
    salida = _hijo(codigo, tmp_path, str(tmp_path / "ajustes"), str(tmp_path / "planta"))
    r = json.loads(next(l for l in salida.splitlines() if l.startswith("@@"))[2:])
    assert r["codigo"] == 0
    assert (r["titulo"], r["rotulo"], r["app"], r["org"]) == ("Inventada · Prueba", "Inventada", "Inventada · Prueba", "ORG_X")
    assert Path(r["ajustes"]).parts[-2:] == ("ORG_X", "Ajustes_X.ini") and Path(r["ajustes"]).parent.parent == tmp_path / "ajustes"
    assert r["ids"] == ["ORG.X.Prueba"]
    assert r["edicion"] is True and r["env"] == "edicion" and r["argv"] == []                    # --edicion, también para los procesos hijos
    assert r["fecha_min"] == "2019-01-02" and r["anios"] == "Simular 3 años"
    textos = "\n".join(r["textos"])
    assert "Focos de emisión… (modo X)" in textos and "Focos… (modo X)" in textos and "Edificios cercanos (Edificios X, 150 m)" in textos
    assert not AJENO.search(textos), AJENO.search(textos)
    # las páginas y el registro de esa ventana tampoco
    pagina = (tmp_path / "local" / "web" / "mapa_base.html").read_text(encoding="utf-8")
    assert "Fondo X" in pagina and "window.mapaApp" in pagina and not AJENO.search(pagina)
    registro = next((tmp_path / "local" / "logs").glob("prueba_gui_*.log")).read_text(encoding="utf-8")
    assert "Inventada · Prueba · versión 9.9" in registro and not AJENO.search(registro)
    assert not re.search(r" (ERROR|CRÍTICO) ", registro), registro[-800:]


# ------------------------------------------------------------------------------ tema
@con_qt
def test_tema_poner_cambia_los_colores_en_su_sitio_y_avisa(app):
    from teodors.gui import tema
    tema.aplicar(app)
    colores, avisos = tema.T, []
    tema.avisos.cambiado.connect(lambda: avisos.append(tema.T["fondo"]))
    try:
        for clave in tema.TEMAS:
            tema.poner(clave)
            assert tema.T is colores and tema.T == tema.TEMAS[clave]["colores"] and tema.estilo_actual() == clave and avisos[-1] == tema.T["fondo"]
            assert tema.ajustes().value("apariencia/estilo") == clave                 # se guarda para la próxima vez
            assert tema.c("texto") == tema.TEMAS[clave]["colores"]["texto"] and tema.T["texto"] in tema.css_variables() and tema.T["texto"] in tema.js_variables()
        assert len(avisos) == len(tema.TEMAS) == 4
    finally:
        tema.avisos.cambiado.disconnect()
        tema.poner(tema.ESTILO_DEFECTO)


def _luminancia(color):
    """WCAG 2.1, la cuenta a mano: cada canal de sRGB a lineal, con los pesos de Rec. 709."""
    def lineal(c):
        c /= 255.0
        return c / 12.92 if c <= 0.03928 else ((c + 0.055) / 1.055) ** 2.4
    r, g, b = (int(color[i:i + 2], 16) for i in (1, 3, 5))
    return 0.2126 * lineal(r) + 0.7152 * lineal(g) + 0.0722 * lineal(b)


def _contraste(a, b):
    la, lb = sorted((_luminancia(a), _luminancia(b)), reverse=True)
    return (la + 0.05) / (lb + 0.05)


def test_la_cuenta_del_contraste():
    assert _contraste("#000000", "#ffffff") == pytest.approx(21.0)
    assert _contraste("#ffffff", "#ffffff") == pytest.approx(1.0)
    assert _contraste("#777777", "#ffffff") == pytest.approx(4.478, abs=0.001)            # el gris que se queda justo por debajo de 4,5


# los pares de texto de la hoja de estilos; sin `apagado`, que es el texto de lo desactivado (WCAG no le pide contraste)
PARES = [(t, f) for t in ("texto", "tenue") for f in ("fondo", "superficie", "elevada")] + [("sobre_acento", "acento"), ("acento_claro", "tinte"), ("aviso", "tinte_aviso"), ("fallo", "tinte_fallo"),
                                                                                             ("acento_claro", "superficie"), ("aviso", "superficie"), ("fallo", "superficie")]


@con_qt
@pytest.mark.parametrize("estilo", ["oscuro", "claro", "noche", "contraste"])
def test_contraste_de_los_textos_en_los_cuatro_estilos(estilo):
    from teodors.gui import tema
    assert len(tema.TEMAS) == 4
    colores = tema.TEMAS[estilo]["colores"]
    for texto, fondo in PARES:
        assert _contraste(colores[texto], colores[fondo]) >= 4.5, (estilo, texto, fondo, _contraste(colores[texto], colores[fondo]))


# ------------------------------------------------------------------------------ cerrar: la pregunta de guardar
@con_qt
@pytest.mark.parametrize("boton", ["Save", "Discard", "Cancel"])
def test_preguntar_si_guardar_devuelve_lo_pulsado_y_va_en_espanol(app, boton):
    from PySide6 import QtCore, QtWidgets
    from teodors.gui import widgets
    B = QtWidgets.QMessageBox.StandardButton
    v = QtWidgets.QWidget()
    v.showMinimized()                            # sale delante aunque estuviera minimizada
    visto = {}

    def contesta():
        caja = v._pregunta
        visto.update(textos=[caja.button(x).text() for x in (B.Save, B.Discard, B.Cancel)], modal=caja.windowModality(), abierta=widgets.pregunta_abierta(v), encima=bool(caja.windowFlags() & QtCore.Qt.WindowType.WindowStaysOnTopHint), minimizada=v.isMinimized())
        caja.button(getattr(B, boton)).click()
    assert widgets.pregunta_abierta(v) is False
    QtCore.QTimer.singleShot(0, contesta)
    assert widgets.preguntar_si_guardar(v, "Título", "¿Guardar?") == getattr(B, boton)
    assert visto == {"textos": ["Guardar", "No guardar", "Cancelar"], "modal": QtCore.Qt.WindowModality.WindowModal, "abierta": True, "encima": True, "minimizada": False}
    assert v._pregunta is None and widgets.pregunta_abierta(v) is False     # contestada: ya no hay pregunta abierta
    v.close()


@con_qt
def test_cerrar_el_dialogo_sin_elegir_es_cancelar(app):
    from PySide6 import QtCore, QtWidgets
    from teodors.gui import widgets
    v = QtWidgets.QWidget()
    QtCore.QTimer.singleShot(0, lambda: v._pregunta.reject())
    assert widgets.preguntar_si_guardar(v, "T", "¿?") == QtWidgets.QMessageBox.StandardButton.Cancel
    v.close()


# ------------------------------------------------------------------------------ las páginas
def test_hacer_autonomo_mete_dentro_lo_que_tiene_y_deja_lo_que_no(tmp_path, monkeypatch):
    pagina = tmp_path / "p.html"
    pagina.write_text('<html><head><script src="https://cdn.x/a.js"></script><script src="https://cdn.x/b.js"></script><link rel="stylesheet" href="https://cdn.x/c.css"><link rel="icon" href="https://cdn.x/i.ico"></head></html>', encoding="utf-8")
    pedidos = []

    def descarga(url, cache, binario=False):
        pedidos.append(url)
        if url.endswith("a.js"):
            return "uno('</script>')"
        if url.endswith("c.css"):
            return "x{background:url(f.woff2)}y{background:url(data:zz)}"
        if url.endswith("f.woff2"):
            return b"\x01\x02"
        return None
    monkeypatch.setattr(web, "_descarga", descarga)
    assert web.hacer_autonomo(pagina, tmp_path / "cache") == (1, 1)
    t = pagina.read_text(encoding="utf-8")
    assert "uno('<\\/script>')" in t and 'src="https://cdn.x/b.js"' in t                       # lo que no se tiene se queda con su CDN
    assert "url(data:font/woff2;base64,AQI=)" in t and "url(data:zz)" in t and 'href="https://cdn.x/i.ico"' in t
    assert "https://cdn.x/f.woff2" in pedidos and "var(--fondo,#e9e9e9)" in t


def test_descarga_de_web_usa_su_cache_y_sin_red_no_rompe(tmp_path):
    nombre = "https://cdn.x/a.js"
    assert web._descarga(nombre, tmp_path) is None                                             # sin red: None, y un aviso
    import hashlib
    (tmp_path / (hashlib.md5(nombre.encode()).hexdigest() + "_a.js")).write_text("hola", encoding="utf-8")
    assert web._descarga(nombre, tmp_path) == "hola"


@con_qt
def test_mapa_web_genera_sus_paginas_sin_ventanas_y_sin_nada_de_otra_planta(tmp_path):
    # en un proceso sin QApplication: generar la página no necesita ninguna ventana
    codigo = r"""
import json, sys
from PySide6 import QtCore, QtWidgets
QtCore.QSettings.setPath(QtCore.QSettings.Format.IniFormat, QtCore.QSettings.Scope.UserScope, sys.argv[2])
from teodors import planta
planta.activar(sys.argv[1])
from teodors.gui import focos_mapa, mapa_web, web
web._descarga = lambda *a, **k: None
emp = planta.cargar_emplazamiento()
a = mapa_web.escribir_mapa_base(emp, [[38.5, 1.3], [38.7, 1.5]], autonomo=False)
b = focos_mapa.escribir_html(emp)
print(a, b, QtWidgets.QApplication.instance() is None, sep="|")
"""
    a, b, sin_app = _hijo(codigo, tmp_path, str(tmp_path / "planta"), str(tmp_path / "ajustes")).strip().split("|")
    assert sin_app == "True"
    for ruta, ventana in ((a, "mapa_base.html"), (b, "mapa_focos.html")):
        assert Path(ruta) == tmp_path / "local" / "web" / ventana                              # fuera de la carpeta del proyecto
        t = Path(ruta).read_text(encoding="utf-8")
        assert "Fondo X" in t and "Atribuci" in t and "http://127.0.0.1:9/" in t
        assert "window.mapaApp" in t and 'console.log("MAPA:"' in t and "--acento" in t
        assert not AJENO.search(t), AJENO.search(t)
    t = Path(a).read_text(encoding="utf-8")
    assert "mapaViento" in t and "mapa-leyenda" in t


@con_qt
def test_los_fondos_y_la_ficha_del_mapa():
    from teodors.gui import mapa_web
    assert mapa_web.fondos() == [("Fondo X", "http://127.0.0.1:9/{z}/{x}/{y}.png", "Atribución X", 18)]
    assert "<h4>Lo &lt;mío&gt;</h4>" in mapa_web.ficha_html("Lo <mío>", [("a", 1)]) and "mapa-ficha" in mapa_web.ficha_html("T", [])


@con_qt
def test_el_puente_del_mapa_solo_atiende_a_su_prefijo(tmp_path):
    # lo que el mapa escribe en la consola llega a Python solo con su prefijo. En un proceso aparte: es una página de WebEngine
    codigo = r"""
import json, os
from PySide6 import QtCore, QtWebEngineWidgets, QtWidgets
QtCore.QCoreApplication.setAttribute(QtCore.Qt.ApplicationAttribute.AA_ShareOpenGLContexts)
app = QtWidgets.QApplication(["x"])
from teodors.gui import mapa
p = mapa.PaginaMapa()
eventos = []
p.evento.connect(eventos.append)
nivel = p.JavaScriptConsoleMessageLevel.InfoMessageLevel
for texto in ('MAPA:{"evento": "listo"}', 'OTRO:{"evento": "no"}', "MAPA:{no es json"):
    p.javaScriptConsoleMessage(nivel, texto, 1, "x")
print("@@" + json.dumps(eventos), flush=True)
os._exit(0)
"""
    salida = _hijo(codigo, tmp_path)
    assert json.loads(next(l for l in salida.splitlines() if l.startswith("@@"))[2:]) == [{"evento": "listo"}]


# ------------------------------------------------------------------------------ lo que sale de la planta
@con_qt
def test_los_ajustes_llevan_el_nombre_de_la_planta(app, tmp_path):
    from teodors.gui import tema
    assert Path(tema.ajustes().fileName()) == tmp_path / "ajustes" / "ORG_X" / "Ajustes_X.ini"


@con_qt
@pytest.mark.parametrize("anios, texto", [([2020], "1 año"), ([2019, 2020, 2021], "3 años")])
def test_los_textos_de_los_anios_salen_del_reanalisis(tmp_path, anios, texto):
    from teodors.gui import panel
    datos = json.loads(json.dumps(JSON_PLANTA))
    datos["reanalisis"]["anios"] = anios
    (tmp_path / "planta" / "planta.json").write_text(json.dumps(datos), encoding="utf-8")
    planta.activar(tmp_path / "planta")
    assert panel.texto_anios() == texto


@con_qt
def test_la_zona_horaria_del_reproductor_es_la_de_la_planta(app):
    # 12:00 UTC del 15 de julio: en Canarias, las 13:00; en otra zona, otra cosa
    from teodors.gui import panel, tema
    tema.aplicar(app)
    p = panel.Panel(planta.cargar_emplazamiento())
    p.set_viento_listo(["2024-07-15T12:00:00"])
    assert p._horas_oficial[0].hour == 13
    p.deleteLater()


@con_qt
def test_el_modo_de_edicion_lo_lee_la_interfaz_de_la_planta(tmp_path):
    # en un proceso aparte: la ventana lleva un mapa de WebEngine
    codigo = r"""
import json, os, sys
os.environ["QTWEBENGINE_CHROMIUM_FLAGS"] = "--host-resolver-rules=\"MAP * ~NOTFOUND\""
from PySide6 import QtCore, QtWebEngineWidgets, QtWidgets
QtCore.QSettings.setPath(QtCore.QSettings.Format.IniFormat, QtCore.QSettings.Scope.UserScope, sys.argv[1])
QtCore.QCoreApplication.setAttribute(QtCore.Qt.ApplicationAttribute.AA_ShareOpenGLContexts)
app = QtWidgets.QApplication(["x"])
from teodors import planta
from teodors.gui import tema, ventana_focos, web
web._descarga = lambda *a, **k: None
planta.activar(sys.argv[2])
tema.aplicar(app)
aj = QtCore.QSettings(sys.argv[1] + "/aj.ini", QtCore.QSettings.Format.IniFormat)
emp = planta.cargar_emplazamiento()
sale = []
for modo in (False, True):
    planta.actual().MODO_EDICION = modo
    v = ventana_focos.VentanaFocos(emp, aj)
    sale.append([v.editable, v.windowTitle()])
print("@@" + json.dumps(sale), flush=True)
os._exit(0)
"""
    salida = _hijo(codigo, tmp_path, str(tmp_path / "ajustes"), str(tmp_path / "planta"))
    assert json.loads(next(l for l in salida.splitlines() if l.startswith("@@"))[2:]) == [[False, "Focos de la planta · Inventada · Prueba"], [True, "Focos de la planta · Inventada · Prueba · modo X"]]


@con_qt
def test_la_pagina_del_visor_lleva_su_ortofoto_y_su_credito_sin_nada_de_otra_planta(tmp_path):
    # `tema`, solo para sus colores, al montar la página
    datos = {"firma": "x", "titulo": "T", "dia": "d", "unidad": "u", "niveles": ["1"], "horas": [], "horas_utc": [], "escala_m": 0.25, "terreno": {}, "rotulos": [], "segundos": 1.0}
    ruta = P3D.pagina(datos)
    assert ruta == tmp_path / "local" / "web" / "penacho_3d.html"
    t = ruta.read_text(encoding="utf-8")
    assert "Crédito de la ortofoto X" in t and "/9j/" in t and "THREE" in t and "--acento" in t      # /9j/: la cabecera del JPEG en base64
    assert not AJENO.search(t), AJENO.search(t)


@con_qt
def test_la_pagina_del_visor_sin_ortofoto_ni_credito_en_una_planta_nueva(tmp_path):
    datos = json.loads(json.dumps(JSON_PLANTA))
    datos["visor3d"] = {"semilado_m": 400.0}
    (tmp_path / "planta" / "planta.json").write_text(json.dumps(datos), encoding="utf-8")
    planta.activar(tmp_path / "planta")
    html = {"firma": "x", "titulo": "T", "dia": "d", "unidad": "u", "niveles": ["1"], "horas": [], "horas_utc": [], "escala_m": 0.25, "terreno": {}, "rotulos": [], "segundos": 1.0}
    t = P3D.pagina(html).read_text(encoding="utf-8")
    assert 'var ORTO = "data:image/jpeg;base64,";' in t and "/*CREDITO*/" not in t and "THREE" in t


@con_qt
def test_trabajo_informa_del_fallo_y_de_la_cancelacion():
    from PySide6 import QtCore
    from teodors.gui import trabajos

    def corre(funcion):
        t = trabajos.Trabajo(funcion)
        salen = []
        t.hecho.connect(lambda d: salen.append(d), QtCore.Qt.ConnectionType.DirectConnection)
        t.fallo.connect(lambda m: salen.append(m), QtCore.Qt.ConnectionType.DirectConnection)
        t.run()                                         # sin hilo: lo que importa es qué emite
        return salen

    def mal(progreso):
        raise ValueError("uy")

    def cancelada(progreso, cancelado):
        assert cancelado() is False
        raise Cancelado()
    assert corre(lambda progreso: {"a": 1}) == [{"a": 1}]
    assert corre(mal) == ["ValueError: uy"]
    assert corre(cancelada) == ["Descarga cancelada."]
