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
    "operacion": {"modo_edicion": "edicion", "texto_modo_edicion": "modo X", "usuario": "cliente", "texto_usuario": "Cliente X", "ejemplo": "ejemplo"},
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
CON_QT = {"consola", "editor_edificios", "editor_focos", "focos_mapa", "mapa", "mapa_web", "panel", "tema", "terminal", "trabajos", "ventana", "ventana_ajustes", "ventana_focos", "ventana_planes", "planta_graficos", "focos_graficos", "viento_planta", "vista_3d", "vista_previa", "widgets"}
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
@pytest.mark.parametrize("argv, sale, queda", [
    (["x"], dict(dia=None, focos=False, planes=False), ["x"]),
    (["x", "--dia", "2024-01-02", "--focos", "--planes"], dict(dia="2024-01-02", focos=True, planes=True), ["x"]),
    (["x", "--focos", "-platform", "offscreen"], dict(dia=None, focos=True, planes=False), ["x", "-platform", "offscreen"]),
    (["x", "--edicion"], dict(dia=None, focos=False, planes=False), ["x", "--edicion"]),      # ya no abre nada: el administrador, en la terminal
    (["x", "--dia"], dict(dia=None, focos=False, planes=False), ["x"]),
])
def test_opciones_sin_crear_ninguna_ventana(argv, sale, queda):
    assert principal.opciones(argv) == sale
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
# usuario, 2026-11-09: al abrir, la comprobación de la herramienta se hace sola; aquí, solo se apunta (sin red)
from teodors.gui import ventana as V
comprobaciones = []
V.VentanaPrincipal._comprobar = lambda self, al_abrir=False: comprobaciones.append(al_abrir)
V.VentanaPrincipal.ESPERA_COMPROBAR_MS = 0
ids = []
ctypes.windll.shell32.SetCurrentProcessExplicitAppUserModelID = ids.append
ayudas = []
QtWidgets.QMessageBox.about = lambda _padre, titulo, texto: ayudas.append([titulo, texto])
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
        filas.extend(a.text() for a in v.actions())
        barra = [b.toolTip() for b in v.findChild(QtWidgets.QWidget, "barra_app").findChildren(QtWidgets.QToolButton)]
        v.panel.b_ayuda.click()
        # usuario, 2026-11-08: dos usuarios; se cambia desde la terminal, el administrador con su contraseña
        from teodors.operacion import administrador as A
        t = v.terminal
        def escribe(x):
            t.entrada.setText(x)
            t._ejecutar()
            return t.salida.toPlainText().splitlines()[-1]
        adm = {"al_abrir": planta.MODO_EDICION, "sin_clave": escribe("_edicion"), "ayuda": escribe("ayuda"), "quien_antes": escribe("usuario"),
               "sin_guion": escribe("edicion")}
        A.poner_clave("clave-de-prueba")
        escribe("_edicion")
        adm.update(pide=t.pidiendo_clave(), eco=t.entrada.echoMode().value, mala=escribe("mala-clave"), tras_mala=planta.MODO_EDICION)
        escribe("_edicion")
        adm.update(buena=escribe("clave-de-prueba"), tras_buena=planta.MODO_EDICION, marca=v.findChild(QtWidgets.QLabel, "admin_marca").isVisible(),
                   boton=v.panel.b_conf_focos.text(), accion=v.acc_focos.text(), quien=escribe("usuario"))
        adm.update(normal=escribe("_cliente"), tras_normal=planta.MODO_EDICION, marca_fin=v.findChild(QtWidgets.QLabel, "admin_marca").isVisible(),
                   boton_fin=v.panel.b_conf_focos.text(), historial=t._historial, salida=t.salida.toPlainText(),
                   fichero=(planta.PLANTA / "administrador.json").read_text(encoding="utf-8"))
        sale.update(barra=barra, menus=[type(m.parent()).__name__ for m in v.findChildren(QtWidgets.QMenu)], ayuda=ayudas, atajos=sorted(a.shortcut().toString() for a in v.actions()))
        sale.update(comprobar=list(comprobaciones))
        sim = []
        for h in ("ninguno", "reanalisis"):                 # la tarjeta de Simular según la opción de Meteorología, sin cargar nada
            v.panel._radios_meteo[h].blockSignals(True)
            v.panel._radios_meteo[h].setChecked(True)
            v.panel._radios_meteo[h].blockSignals(False)
            v.panel._actualizar_simular()
            sim.append([v.panel.tarj_simular.titulo.text(), v.panel.b_simular.text(), not v.panel.fila_archivo.isHidden()])
        anios = sim
        sale.update(adm=adm, titulo=v.windowTitle(), rotulo=v.findChild(QtWidgets.QLabel, "app_titulo").text(), app=app.applicationName(), org=app.organizationName(), textos=filas, ajustes=tema.ajustes().fileName(),
                    fecha_min=v.panel.fecha_periodo.minimumDate().toString("yyyy-MM-dd"), anios=anios, edicion=planta.MODO_EDICION, env=os.environ.get("PRUEBA_GUI_MODO"), ids=ids, argv=sys.argv[1:])
        v.close()
        QtCore.QTimer.singleShot(200, app.quit)
    QtCore.QTimer.singleShot(300, mira)
    return real()

QtWidgets.QApplication.exec = exec_y_cerrar
sys.argv = ["x", "--edicion", "--dia", "2020-05-05"]          # «--edicion» ya no abre nada
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
    assert r["edicion"] is False and r["env"] is None and r["argv"] == ["--edicion"]            # la línea de órdenes ya no abre el modo de edición
    assert r["comprobar"] == [True]                     # usuario, 2026-11-09: al abrir, la comprobación de la herramienta, sola y una vez
    a = r["adm"]
    assert a["al_abrir"] is False and "no tiene contraseña de administrador" in a["sin_clave"] and a["quien_antes"] == "Cliente X"
    assert a["ayuda"] == "Comandos: ayuda · limpiar · usuario"                         # los ocultos empiezan por «_» y no salen
    assert a["sin_guion"] == "edicion: comando desconocido"
    assert a["pide"] is True and a["eco"] == 2 and a["mala"] == "Contraseña incorrecta." and a["tras_mala"] is False     # 2: EchoMode.Password
    assert a["buena"] == "Usuario modo X." and a["tras_buena"] is True and a["marca"] is True and a["quien"] == "modo X"
    assert a["boton"] == "Configurar los focos (modo X)…" and a["accion"] == "Focos de emisión… (modo X)"
    assert a["normal"] == "Usuario Cliente X." and a["tras_normal"] is False and a["marca_fin"] is False and a["boton_fin"] == "Ver focos…"
    # la contraseña no queda en ningún sitio: ni en el historial, ni en la terminal, ni en el fichero (solo su huella)
    for sitio in (" ".join(a["historial"]), a["salida"], a["fichero"]):
        assert "clave-de-prueba" not in sitio and "mala-clave" not in sitio
    assert a["historial"] == ["_edicion", "ayuda", "usuario", "edicion", "_edicion", "_edicion", "usuario", "_cliente"]
    assert r["fecha_min"] == "2019-01-02" and r["anios"] == [["Simular", "Simular", False], ["Reanálisis · 3 años", "Simular reanálisis", True]]
    assert r["barra"] == ["Solo mapa"] and "VentanaPrincipal" not in r["menus"], r["menus"]   # sin menú: la configuración y la ayuda, en el riel del panel
    assert r["atajos"] == sorted(["Ctrl+1", "Ctrl+2", "Ctrl+3", "F11", "F5", "Ctrl+,", "Ctrl+Shift+F", "Ctrl+Shift+P"])   # los de antes, sin el menú
    (titulo, ayuda), = r["ayuda"]                                               # el manual, más adelante; mientras, la versión y las fuentes
    assert titulo == "Ayuda" and "Versión 9.9 · Empresa X" in ayuda and "manual" in ayuda and "<li>Crédito X</li>" in ayuda
    textos = "\n".join(r["textos"] + [ayuda])
    assert "Focos de emisión…" in textos and "Ver focos…" in textos and "EDIFICIOS A MENOS DE 150 M (EDIFICIOS X)" in textos
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
@pytest.mark.parametrize("boton, sale", [("Yes", True), ("No", False), (None, False)])
def test_preguntar_si_va_en_espanol(app, boton, sale):
    # Qt no trae su traducción: «Yes»/«No» salían en inglés (2026-11-08, al traer los edificios del LiDAR)
    from PySide6 import QtCore, QtWidgets
    from teodors.gui import widgets
    B = QtWidgets.QMessageBox.StandardButton
    v = QtWidgets.QWidget()
    visto = {}

    def contesta():
        caja = v._pregunta
        visto["textos"] = [caja.button(B.Yes).text(), caja.button(B.No).text()]
        if boton:
            caja.button(getattr(B, boton)).click()
        else:
            caja.reject()
    QtCore.QTimer.singleShot(0, contesta)
    assert widgets.preguntar_si(v, "Título", "¿Seguro?") is sale
    assert visto == {"textos": ["Sí", "No"]} and v._pregunta is None
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
def test_el_icono_es_el_de_la_planta_y_sin_el_el_de_teodors(app, tmp_path):
    # identidad.icono, opcional y relativo a la carpeta de la planta; si falta el fichero, el de teOdors y un aviso: el arranque no se para
    from PySide6 import QtGui
    from teodors.gui import tema
    tema.aplicar(app)
    assert tema.icono_planta() is None and sorted(s.width() for s in tema.icono_app().availableSizes()) == [32, 64, 128]
    img = QtGui.QImage(48, 48, QtGui.QImage.Format.Format_ARGB32)
    img.fill(QtGui.QColor("#123456"))
    assert img.save(str(tmp_path / "planta" / "mio.png"))
    for ruta, propio in (("mio.png", True), ("no_esta.png", False)):
        datos = json.loads(json.dumps(JSON_PLANTA))
        datos["identidad"]["icono"] = ruta
        (tmp_path / "planta" / "planta.json").write_text(json.dumps(datos), encoding="utf-8")
        planta.activar(tmp_path / "planta")
        assert (tema.icono_planta() is not None) is propio
        assert (tema.icono_app().pixmap(48, 48).toImage().pixelColor(24, 24).name() == "#123456") is propio


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
def test_simular_el_reanalisis_con_tres_botones_y_la_tabla_de_los_pueblos(app):
    # usuario, 2026-11-09: «organizar mucho mejor el panel de simular»: con el reanálisis no hay un día ni su penacho; tres botones (simular,
    # guardar y cargar) y, al acabar, el olor o cada contaminante, en el mapa media, máximo y P98, también en isolíneas rellenas, y la tabla
    from teodors.gui import panel, tema
    tema.aplicar(app)
    p = panel.Panel(planta.cargar_emplazamiento())
    p.resize(450, 1000)
    p.show()
    p.ir_a("simulacion")
    assert p.pagina() == "simulacion"
    emitido = []
    for s in ("simular", "simularPeriodo", "cancelarSimulacion", "guardarResultados", "cargarResultados", "estiloCapas", "magnitudElegida"):
        getattr(p, s).connect(lambda *a, s=s: emitido.append((s, *a)))
    p._hay_respuestas = True
    p.set_horizonte_meteo("reanalisis")
    app.processEvents()
    assert p.tarj_simular.titulo.text().startswith("Reanálisis · ") and p.b_simular.text() == "Simular reanálisis" and p.b_simular.isEnabled()
    assert p.fila_archivo.isVisible() and not p.b_guardar_res.isEnabled() and p.b_cargar_res.isEnabled()
    assert not hasattr(p, "fecha_dia") and not p.sec_res.isVisible() and not p.sec_periodo.isVisible()
    p.b_simular.click()
    p.set_simulando(True)
    assert p.b_simular.text() == "Cancelar" and p.b_simular.property("cancelar") is True and not p.cmb_plan.isEnabled() and not p.b_cargar_res.isEnabled() and p.barra_sim.isVisible()
    p.set_progreso_simulacion(50, "Sumando las respuestas: 06/2023")
    assert "50 %" in p.lbl_sim.text()
    p.b_simular.click()
    assert p.b_simular.text() == "Cancelando…" and not p.b_simular.isEnabled()
    p.set_fallo_simulacion("RuntimeError: Cálculo cancelado.")
    p.fin_simulacion()
    assert p.b_simular.text() == "Simular reanálisis" and not p.b_simular.property("cancelar") and p.lbl_sim.text().startswith("Cancelado")
    assert emitido[:2] == [("simular", None), ("cancelarSimulacion",)]

    def mag(clave, nombre, unidad, media, maximo, p98):
        cols = [{"clave": "media", "titulo": "Media", "nombre": "Media", "tipo": "conc", "limite": None, "capa": "media"},
                {"clave": "maximo", "titulo": "Máx.", "nombre": "Máximo", "tipo": "conc", "limite": None, "capa": "maximo"},
                {"clave": "p98", "titulo": "P98", "nombre": "Percentil 98", "tipo": "conc", "limite": None, "capa": "norma"}]
        fila = lambda n, tipo, km, k: {"nombre": n, "tipo": tipo, "km": km, "media": media / k, "maximo": maximo / k, "p98": p98 / k}
        return {"clave": clave, "nombre": nombre, "unidad": unidad, "columnas": cols, "estimados": [], "fuera": [], "horas_txt": [],
                "maximos": {"media": media, "maximo": maximo, "p98": p98},
                "filas": [fila("Peor vivienda", "vivienda", 0.5, 10), fila("Lejos", "pueblo", 12.7, 1000), fila("Cerca", "pueblo", 3.2, 100)]}
    r = {"nombre": "Base", "fecha": "2026-11-09 18:41", "segundos": 386.7, "periodo": None, "orden": ["olor", "H2S"],
         "datos": {"dias": 1826, "horas": 43824}, "magnitudes": {"olor": mag("olor", "Olor", "ou_E/m³", 51.3, 237.1, 171.9),
                                                              "H2S": mag("H2S", "H₂S", "µg/m³", 29.2, 135.5, 98.25)}}
    from teodors.operacion import simulacion as S
    p.set_resultado(r, S.cifra)
    app.processEvents()
    # usuario, 2026-11-09: «los resultados tabulados deben ser de los pueblos»: solo los pueblos, de peor a mejor por el P98, con su distancia
    T = p.res_anios.tabla
    assert p.sec_res.isVisible() and p.b_guardar_res.isEnabled() and not hasattr(p, "tabla_mags") and not hasattr(p, "sec_lugares")
    assert [T.horizontalHeaderItem(k).text() for k in range(5)] == ["Pueblo", "km", "Media", "Máx.", "P98"]
    assert [[T.item(i, k).text() for k in range(5)] for i in range(2)] == [["Cerca", "3,2", "0,51", "2,4", "1,7"], ["Lejos", "12,7", "0,051", "0,24", "0,17"]]
    assert T.verticalScrollBar().maximum() == 0 and p.lbl_pueblos.text() == "PUEBLOS · Olor (ou_E/m³)" and not p.res_anios.lbl.isVisible()
    assert "simulado el 09/11/2026 a las 18:41 en 6 min 27 s" in p.lbl_res.text() and "43 824 horas" in p.lbl_res.text()
    assert [p._botones_capa[f"plan_{c}"].text() for c in ("media", "maximo", "norma")] == ["Media", "Máximo", "P98"]
    assert [(c, b.text(), b.isChecked()) for c, b in p.botones_mag_res.items()] == [("olor", "Olor", True), ("H2S", "H₂S", False)]
    p.botones_mag_res["H2S"].click()                     # otro gas: en la tabla de los pueblos y en el mapa
    assert emitido[-1] == ("magnitudElegida", "H2S") and p.magnitud() == "H2S" and p.lbl_pueblos.text().startswith("PUEBLOS · H₂S")
    assert not p.botones_mag_res["olor"].isChecked() and T.item(0, 2).text() == "0,29"
    r["magnitudes"]["olor"]["estimados"] = ["Balsa (H₂S)", "Hilera (DMS)"]
    p.botones_mag_res["olor"].click()                    # el olor estimado por sus gases: en una línea, y la lista al pasar por encima
    assert p.res_anios.lbl.text() == "Olor estimado por sus gases en 2 focos" and "Balsa (H₂S); Hilera (DMS)" in p.res_anios.lbl.toolTip()
    p.botones_mag_res["H2S"].click()
    p.botones_mag_res["H2S"].click()                     # el que ya se ve: sigue marcado y no avisa
    assert p.botones_mag_res["H2S"].isChecked() and emitido[-1] == ("magnitudElegida", "H2S") and len([e for e in emitido if e[0] == "magnitudElegida"]) == 3
    assert p.estilo_capas() == "isolineas"
    p._b_estilo["degradado"].click()
    assert emitido[-1] == ("estiloCapas", "degradado") and p.estilo_capas() == "degradado"
    p.b_guardar_res.click()
    p.b_cargar_res.click()
    assert emitido[-2:] == [("guardarResultados",), ("cargarResultados",)]
    # sin el reproductor en Simular con el reanálisis; al salir, vuelve si había un día
    p.set_viento_listo(["2024-07-15T12:00:00", "2024-07-15T13:00:00"])
    p.set_sin_reproductor(True)
    assert not p.reproductor.isVisible()
    p.set_sin_reproductor(False)
    assert not p.reproductor.isHidden()
    p.limpiar_resultado(False)
    assert not p.sec_res.isVisible() and T.rowCount() == 0 and not p.b_guardar_res.isEnabled()
    p.deleteLater()


@con_qt
def test_simular_siempre_simula_aunque_ya_este_simulado(app, monkeypatch):
    # usuario, 2026-11-10: «si el usuario pide que lo vuelva a simular, lo vuelve a simular»: no se lee lo guardado aunque valga
    from types import SimpleNamespace
    from teodors.gui import ventana as V
    from teodors.operacion import simulacion as S
    lanzados, hecho = [], []

    class Falso:
        def __init__(self, funcion, *args, parent=None):
            lanzados.append((funcion, args))
            senal = SimpleNamespace(connect=lambda *_: None)
            self.progreso = self.hecho = self.fallo = self.finished = senal

        def start(self):
            hecho.append("start")
    monkeypatch.setattr(V, "Trabajo", Falso)
    monkeypatch.setattr(S, "guardado", lambda *a, **k: {"nombre": "Base", "periodo": None})
    esc, cat = {"nombre": "Base"}, {"focos": []}
    v = SimpleNamespace(_trabajo_sim=None, _leer_plan=lambda ruta: (esc, cat), _limpiar_simulacion=lambda *_: None,
                        _simulado=lambda r: hecho.append("leido"), _simulacion_fallida=None, _fin_simulacion=None)
    v.panel = SimpleNamespace(set_simulando=lambda *a: hecho.append(("simulando", a)), set_progreso_simulacion=None)
    lanzar = V.VentanaPrincipal._lanzar_simulacion.__get__(v)
    lanzar(None, None)                                                   # los años del reanálisis
    assert lanzados == [(S.calcular, (esc, cat))] and hecho == [("simulando", (True, False)), "start"]
    lanzados.clear(), hecho.clear()
    v._trabajo_sim = None
    periodo = {"modo": "episodio", "ini": "2024-05-01", "dias": 2}
    lanzar(None, periodo)                                                # un día, un episodio o una predicción: igual
    assert lanzados == [(S.calcular_periodo, (esc, cat, periodo))] and "leido" not in hecho


@con_qt
def test_lo_simulado_solo_se_ve_en_la_pagina_de_simular(app):
    # usuario, 2026-11-09: «si pasas al panel de meteorología los resultados de olores y gases desaparecen, para evitar malentendidos de que
    # resultados de 5 años se correspondan con un día del reanálisis»: fuera del mapa, del selector y de las fichas; al volver, como estaba
    from types import SimpleNamespace
    from teodors.gui import ventana as V
    hecho = []
    pagina, modo = ["meteo"], ["simular"]
    v = SimpleNamespace(_resultados_visibles=True, _encendida_oculta=None, _magnitud="olor", _valores={"anios": {(0.0, 0.0): {}}},
                        _resultados={"anios": {"nombre": "Base"}, "periodo": None}, _comparacion={"orden": ["olor"]}, _comparacion_visible=False,
                        _comp_oculta="comp_media")
    v.panel = SimpleNamespace(pagina=lambda: pagina[0], horizonte_meteo=lambda: "reanalisis", modo_reanalisis=lambda: modo[0],
                              capa_encendida=lambda ids: ids[1] if ids[0] == "comp_media" else "plan_media",
                              set_capa_visible=lambda i, si: hecho.append(("boton", i, si)))
    v.mapa = SimpleNamespace(quitar_capa=lambda i: hecho.append(("quitar", i)), quitar_penacho=lambda: hecho.append(("penacho",)))
    v._pintar_nucleos = lambda: hecho.append(("nucleos",))
    v._poner_magnitud = lambda clave, encendida: hecho.append(("poner", clave, encendida))
    v._poner_comparacion = lambda encendida: hecho.append(("comparacion", encendida))
    for nombre in ("_resultados_segun_pagina", "_ver_simulado", "_ver_comparacion", "_quitar_capas", "_ids_capas", "_ids_comparacion", "_tabla_plan"):
        setattr(v, nombre, getattr(V.VentanaPrincipal, nombre).__get__(v))
    v._resultados_segun_pagina()                          # a Meteo: fuera
    assert v._resultados_visibles is False and v._encendida_oculta == "plan_media" and v._valores == {}
    assert {("quitar", f"{p}_{c}") for p in ("plan", "dia") for c in ("media", "maximo", "norma")} <= set(hecho)
    assert ("penacho",) in hecho and hecho[-1] == ("nucleos",) and v._tabla_plan(0.0, 0.0) == ""
    hecho.clear()
    pagina[0] = "focos"
    v._resultados_segun_pagina()                          # de otra página que no es Simular a otra: nada
    assert hecho == []
    pagina[0] = "simulacion"
    v._resultados_segun_pagina()                          # de vuelta: la que se veía
    assert v._resultados_visibles is True and hecho == [("poner", "olor", "plan_media")]
    # usuario, 2026-11-09: comparar escenarios. En Simular, lo del modo: al comparar, la comparación y no lo simulado, y al revés
    hecho.clear()
    modo[0] = "comparar"
    v._resultados_segun_pagina()
    assert v._resultados_visibles is False and v._comparacion_visible is True and hecho[-1] == ("comparacion", "comp_media")
    hecho.clear()
    modo[0] = "simular"
    v._resultados_segun_pagina()
    assert v._comparacion_visible is False and v._comp_oculta == "comp_maximo" and ("quitar", "comp_norma") in hecho
    assert hecho[-1] == ("poner", "olor", "plan_media")


@con_qt
def test_comparar_escenarios_en_el_panel(app):
    # usuario, 2026-11-09: en el reanálisis, «simular un escenario» o «comparar dos escenarios» ya simulados o guardados: el % de más o
    # de menos en el mapa y en los pueblos, y del olor, la superficie y los pueblos por encima de 1, 3 y 5 ou_E/m³
    from teodors.gui import panel, tema
    from teodors.operacion import simulacion as S
    tema.aplicar(app)
    p = panel.Panel(planta.cargar_emplazamiento())
    p.resize(450, 1400)
    p.show()
    p.ir_a("simulacion")
    emitido = []
    for s in ("modoReanalisis", "compararEscenarios", "cargarEscenario", "magnitudComparada"):
        getattr(p, s).connect(lambda *a, s=s: emitido.append((s, *a)))
    p._hay_respuestas = True
    p.set_horizonte_meteo("reanalisis")
    app.processEvents()
    assert p.fila_modo.isVisible() and p.caja_simular.isVisible() and not p.caja_comparar.isVisible()
    p._b_modo["comparar"].click()
    app.processEvents()
    assert emitido == [("modoReanalisis", "comparar")] and p.modo_reanalisis() == "comparar"
    assert not p.caja_simular.isVisible() and p.caja_comparar.isVisible() and not p.b_comparar.isEnabled() and not p.sec_comp.isVisible()
    lista = [{"texto": "Base · 09/11/2026 20:36", "carpeta": "c:/a", "nombre": "Base", "fecha": "2026-11-09 20:36", "caso": None},
             {"texto": "Balsas · 09/11/2026 21:56", "carpeta": "c:/b", "nombre": "Balsas", "fecha": "2026-11-09 21:56", "caso": None}]
    p.set_escenarios(lista)
    assert [p.cmb_ref.itemText(i) for i in range(p.cmb_ref.count())] == ["Base · 09/11/2026 20:36", "Balsas · 09/11/2026 21:56", "Abrir otro caso guardado…"]
    assert (p.cmb_ref.currentData(), p.cmb_comp.currentData()) == ("c:/a", "c:/b") and p.b_comparar.isEnabled()
    p.cmb_comp.setCurrentIndex(2)                         # «Abrir otro caso guardado…»: vuelve a lo que había y lo pide
    p._escenario_elegido(p.cmb_comp)
    assert emitido[-1] == ("cargarEscenario",) and p.cmb_comp.currentData() == "c:/b"
    p.set_escenarios(lista + [{"texto": "2026-11-09-Otro · caso guardado", "carpeta": "c:/z", "nombre": "Otro", "fecha": "2026-11-09 22:00",
                               "caso": "2026-11-09-Otro"}])
    p.escenario_cargado("c:/z")
    assert p.cmb_comp.currentData() == "c:/z" and p.cmb_ref.currentData() == "c:/a"
    p.cmb_comp.setCurrentIndex(0)                         # el mismo que la referencia: no se puede
    p._escenario_elegido(p.cmb_comp)
    assert not p.b_comparar.isEnabled()
    p.cmb_comp.setCurrentIndex(1)
    p._escenario_elegido(p.cmb_comp)
    p.b_comparar.click()
    assert emitido[-1] == ("compararEscenarios", "c:/a", "c:/b")

    cols = [{"clave": "media", "titulo": "Media", "nombre": "Media", "capa": "media"}, {"clave": "p98", "titulo": "P98", "nombre": "Percentil 98", "capa": "norma"}]
    capas = [{"id": "comp_media", "clave": "media", "titulo": "Media", "nombre": "Media", "ruta": "x", "leyenda": ""},
             {"id": "comp_norma", "clave": "p98", "titulo": "P98", "nombre": "Percentil 98", "ruta": "x", "leyenda": ""}]
    pueblos = [{"nombre": "Lejos", "km": 15.0, "media": [0.002, 0.001, None], "p98": [0.03, 0.02, -33.3]},
               {"nombre": "Cerca", "km": 3.2, "media": [0.011, 0.008, -27.0], "p98": [0.167, 0.114, -31.75]},
               {"nombre": "Sube", "km": 6.5, "media": [0.004, 0.005, 25.0], "p98": [0.04, 0.05, 25.0]}]
    r = {"ref": {"nombre": "Base", "fecha": "2026-11-09 20:36"}, "otro": {"nombre": "Balsas", "fecha": "2026-11-09 21:56"}, "orden": ["olor", "H2S"],
         "avisos": ["Los focos o sus emisiones no son los mismos en los dos: el cambio no es solo de la operación."],
         "magnitudes": {"olor": {"clave": "olor", "nombre": "Olor", "unidad": "ou_E/m³", "umbral": 0.01, "columnas": cols, "capas": capas, "pueblos": pueblos},
                        "H2S": {"clave": "H2S", "nombre": "H₂S", "unidad": "µg/m³", "umbral": 0.1, "columnas": cols, "capas": capas, "pueblos": pueblos[:1]}},
         "criterios": [{"umbral": 1.0, "km2": [5.12, 3.29], "pueblos": [0, 0]}, {"umbral": 3.0, "km2": [1.43, 0.82], "pueblos": [1, 0]},
                       {"umbral": 5.0, "km2": [0.75, 0.45], "pueblos": [0, 0]}]}
    p.set_comparando(True)
    assert not p.b_comparar.isEnabled() and not p.cmb_ref.isEnabled()
    p.set_comparando(False)
    p.set_comparacion(r, S.cifra)
    app.processEvents()
    T = p.tabla_comp
    assert p.sec_comp.isVisible() and "frente a <b>Base</b>" in p.lbl_comp.text() and "⚠" in p.lbl_comp.text()
    assert [[T.item(i, k).text() for k in range(5)] for i in range(3)] == [["Lejos", "15,0", "0,030", "0,020", "−33 %"],
                                                                           ["Cerca", "3,2", "0,17", "0,11", "−32 %"],
                                                                           ["Sube", "6,5", "0,040", "0,050", "+25 %"]]
    assert p.lbl_pueblos_comp.text() == "PUEBLOS · Olor · P98 (ou_E/m³)" and T.verticalScrollBar().maximum() == 0
    texto = p.lbl_criterios.text()
    assert p.lbl_criterios.isVisible() and "5,12 → 3,29 km² <b>(−36 %)</b>" in texto and "<td align='right'>1 → 0</td>" in texto
    p.set_capa_visible("comp_media", True)                # la capa de la media en el mapa: la tabla, con la media
    assert p.lbl_pueblos_comp.text().startswith("PUEBLOS · Olor · Media") and T.item(2, 4).text() == "—"
    p.botones_mag_comp["H2S"].click()                     # un gas: sin los criterios del olor
    assert emitido[-1] == ("magnitudComparada", "H2S") and p.magnitud_comparada() == "H2S" and not p.lbl_criterios.isVisible() and T.rowCount() == 1
    p._b_modo["simular"].click()                          # de vuelta a simular: la comparación, oculta
    assert emitido[-1] == ("modoReanalisis", "simular") and not p.sec_comp.isVisible() and p.caja_simular.isVisible()
    p.deleteLater()


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
def test_el_dia_del_reanalisis_se_elige_en_el_calendario_abierto_y_sus_horas_mueven_el_reproductor(app):
    # usuario, 2026-11-07: «más manejable a la hora de moverte por el calendario, ya desplegado debajo del día seleccionado, y ver en mapa»;
    # luego, sin el día en letra ni su resumen encima, «para ganar espacio»: la fecha va en el botón y el día se mueve con el teclado
    import datetime as dt
    from PySide6 import QtCore, QtTest
    from teodors.gui import panel, tema
    from teodors.gui.viento_planta import color_velocidad, fecha_larga
    tema.aplicar(app)
    p = panel.Panel(planta.cargar_emplazamiento())
    p.resize(450, 1000)
    p.show()
    p.ir_a("meteo")
    app.processEvents()
    # las opciones del horizonte, en dos columnas: el calendario cabe debajo
    r = {k: b.geometry() for k, b in p._radios_meteo.items()}
    assert r["ninguno"].y() == r["reanalisis"].y() < r["queja"].y() == r["prediccion"].y() < r["presente"].y()
    assert r["ninguno"].x() < r["reanalisis"].x() and r["presente"].width() > 1.8 * r["ninguno"].width()
    p.set_horizonte_meteo("reanalisis")
    p.mostrar_viento(True)
    p.set_viento_dias((dt.datetime(2023, 2, 1), dt.datetime(2023, 3, 31)), dt.datetime(2023, 3, 15))
    cal, Izq = p.calendario, QtCore.Qt.MouseButton.LeftButton
    app.processEvents()
    assert cal.elegido() == dt.date(2023, 3, 15) and cal.mes() == (2023, 3) and p.dia_viento() == "2023-03-15"
    assert not hasattr(p, "lbl_dia_viento") and not hasattr(p, "b_dia_sig")
    assert p.btn_viento.isEnabled() and p.btn_viento.text() == "Ver el 15/03/2023 en el mapa" and not p.franja.isVisibleTo(p)
    assert p.btn_viento.toolTip() == fecha_larga(dt.date(2023, 3, 15)).capitalize() + " (día en UTC)" == "Miércoles, 15 de marzo de 2023 (día en UTC)"
    assert cal.b_ant.isEnabled() and not cal.b_sig.isEnabled()                  # abril no tiene viento
    pedidos = []
    p.vientoDia.connect(pedidos.append)
    celda = dict(cal.rejilla.dias())
    QtTest.QTest.mouseClick(cal.rejilla, Izq, pos=celda[dt.date(2023, 3, 20)].center().toPoint())
    assert cal.elegido() == dt.date(2023, 3, 20) and pedidos == []           # pinchar elige, no carga
    QtTest.QTest.mouseClick(cal.rejilla, Izq, pos=celda[dt.date(2023, 4, 2)].center().toPoint())
    assert cal.elegido() == dt.date(2023, 3, 20)                             # fuera del rango, nada
    QtTest.QTest.mouseDClick(cal.rejilla, Izq, pos=celda[dt.date(2023, 3, 21)].center().toPoint())
    assert pedidos == ["2023-03-21"]                                          # el doble clic lo abre
    p.btn_viento.click()
    assert pedidos == ["2023-03-21"] * 2
    # las flechas del teclado mueven el día y la semana, e Intro lo abre; el mes, con sus flechas
    Q = QtCore.Qt.Key
    QtTest.QTest.keyClick(cal.rejilla, Q.Key_Right)
    assert p.dia_viento() == "2023-03-22" and p.btn_viento.text() == "Ver el 22/03/2023 en el mapa"
    QtTest.QTest.keyClick(cal.rejilla, Q.Key_Up)
    assert p.dia_viento() == "2023-03-15"
    QtTest.QTest.keyClick(cal.rejilla, Q.Key_Return)
    assert pedidos == ["2023-03-21"] * 2 + ["2023-03-15"]
    QtTest.QTest.keyClick(cal.rejilla, Q.Key_Down)
    QtTest.QTest.keyClick(cal.rejilla, Q.Key_Right)
    cal.b_ant.click()
    assert cal.mes() == (2023, 2) and not cal.b_ant.isEnabled() and p.dia_viento() == "2023-03-23"
    p.preparar_dia_viento("2024-06-01")                                        # fuera del rango: el último día
    assert p.dia_viento() == "2023-03-31" and cal.mes() == (2023, 3)
    QtTest.QTest.keyClick(cal.rejilla, Q.Key_Right)                            # y de ahí no pasa
    assert p.dia_viento() == "2023-03-31"
    # el viento de cada día pinta su celda y sale al pasar por ella
    p.set_progreso_resumen(40, "24 de 60 meses")
    assert p.barra_resumen.isVisibleTo(p) and "24 de 60 meses" in p.lbl_resumen.text()
    p.set_resumen_viento({"dias": {"2023-03-31": {"media": 3.0, "maxima": 6.2, "hora_max": "14", "wd": 300.0, "rumbo": "ONO", "calmas": 2}}})
    assert not p.barra_resumen.isVisibleTo(p) and cal.info(dt.date(2023, 3, 31))["rumbo"] == "ONO" and cal.info(dt.date(2023, 3, 30)) is None
    app.processEvents()
    img = cal.rejilla.grab().toImage()
    for d, sale in ((dt.date(2023, 3, 31), True), (dt.date(2023, 3, 30), False)):
        c, k = celda[d].center(), img.devicePixelRatio()
        pix = img.pixelColor(QtCore.QPoint(int(c.x() * k), int(c.y() * k)))
        assert (abs(pix.hue() - color_velocidad(3.0).hue()) < 25 and pix.saturation() > 60) is sale, (d, pix.name())
    assert color_velocidad(0).name() != color_velocidad(8).name() == color_velocidad(12).name()
    # cargado el día: «En el mapa», sus horas en la franja, y pinchar una hora lleva el reproductor a ella
    p.set_viento_cargando(True)
    assert p.btn_viento.text() == "Cargando…" and not p.btn_viento.isEnabled()
    horas = [f"2023-03-31 {h:02d}:00" for h in range(24)] + ["2023-04-01 00:00"]
    p.set_viento_cargando(False)
    p.set_viento_listo(horas)
    p.set_viento_planta(horas, {"ws": [0.2] + [3.0] * 24, "wd": [300.0] * 25})
    assert p.btn_viento.text() == "31/03/2023 en el mapa" and not p.btn_viento.isEnabled() and p.franja.isVisibleTo(p) and len(p.franja.horas()) == 24
    app.processEvents()
    QtTest.QTest.mouseClick(p.franja, Izq, pos=QtCore.QPoint(int(p.franja.width() / 24 * 14.5), 40))
    assert p.hora_viento.value() == 56 and p.franja._actual == 14
    QtTest.QTest.keyClick(cal.rejilla, Q.Key_Left)                             # otro día: hay que volver a cargarlo
    assert p.btn_viento.text() == "Ver el 30/03/2023 en el mapa" and p.btn_viento.isEnabled()
    p.mostrar_viento(False)                                                     # otro horizonte: el viento sale del mapa
    assert not p.franja.isVisibleTo(p) and not p.reproductor.isVisibleTo(p)
    p.close()
    p.deleteLater()


@con_qt
def test_el_emplazamiento_ocupa_poco_y_el_inicio_comprueba_la_herramienta(app):
    # usuario, 2026-11-07: el emplazamiento, fijo encima de todas las páginas, en poco sitio; en inicio, «Comprobar» la herramienta
    from PySide6 import QtWidgets
    from teodors.gui import panel, tema
    tema.aplicar(app)
    p = panel.Panel(planta.cargar_emplazamiento())
    p.resize(450, 900)
    p.show()
    app.processEvents()
    assert p.lbl_coords.text() == "38.600000, 1.400000" and not p._detalle_emp.isVisibleTo(p)
    pedidos = []
    p.verPlanta.connect(lambda: pedidos.append("planta"))
    p.verTerreno.connect(lambda: pedidos.append("zona"))
    p.b_ver_planta.click()
    p.b_ver_zona.click()
    p.b_copiar.click()
    assert pedidos == ["planta", "zona"] and QtWidgets.QApplication.clipboard().text() == "38.600000, 1.400000"
    p.b_mas_emp.click()
    assert p._detalle_emp.isVisibleTo(p) and p.lbl_utm.text().endswith(" m")
    p.b_mas_emp.click()
    assert not p._detalle_emp.isVisibleTo(p)
    assert p.findChild(QtWidgets.QFrame, "tarjeta").sizeHint().height() < 110        # antes, ~200 px
    # comprobar: una tarjeta por CATEGORÍA (no el detalle de cada prueba) que enseña que se está trabajando en ella hasta que sale bien o mal
    # (usuario, 2026-11-07), y sin descripciones: si falla, sus códigos en etiquetas; el botón pide la comprobación y la cancela mientras dura
    from teodors.operacion import comprobar
    T = p.categorias
    assert list(T) == ["INS", "ENT", "VIE", "DIS", "MET", "RED"] and [t.titulo.text() for t in T.values()] == [n for _, n in comprobar.CATEGORIAS]
    assert all(t.estado == "pendiente" and not t.indicador.girando() for t in T.values())
    assert not hasattr(p, "lbl_comprobar") and not any(isinstance(w, QtWidgets.QLabel) and w.objectName() == "nota"
                                                       for w in p.b_comprobar.parent().findChildren(QtWidgets.QLabel))   # ni nota ni resumen
    assert T["VIE"].total == sum(1 for x in comprobar.pruebas() if x[2] == "VIE") == 3
    pedidos = []
    p.comprobar.connect(lambda: pedidos.append("comprobar"))
    p.b_comprobar.click()
    assert pedidos == ["comprobar"]
    p.set_comprobando(True)
    assert p.b_comprobar.text() == "Cancelar"
    p.set_prueba(10, {"categoria": "VIE", "estado": "en_curso", "codigos": []})
    assert T["VIE"].estado == "en_curso" and T["VIE"].indicador.girando() and T["VIE"].barra.isVisibleTo(p)
    assert T["VIE"].property("estado") == "en_curso" and T["VIE"].barra.value() == 0
    p.set_prueba(20, {"categoria": "VIE", "estado": "ok", "codigos": []})
    p.set_prueba(25, {"categoria": "VIE", "estado": "en_curso", "codigos": []})
    assert T["VIE"].barra.value() == 1 and T["VIE"].indicador.girando()
    p.set_prueba(30, {"categoria": "VIE", "estado": "aviso", "codigos": [("VIE-11", "viento_local.npz")]})
    p.set_prueba(35, {"categoria": "VIE", "estado": "en_curso", "codigos": []})
    p.set_prueba(40, {"categoria": "VIE", "estado": "ok", "codigos": []})                  # la última: la categoría acaba
    assert T["VIE"].estado == "aviso" and not T["VIE"].indicador.girando() and not T["VIE"].barra.isVisibleTo(p)
    assert T["VIE"].codigos == ["VIE-11"]
    chip = T["VIE"].findChild(QtWidgets.QLabel, "chip_aviso")
    assert chip.text() == "VIE-11" and "Falta el viento alrededor de los edificios" in chip.toolTip()
    p.fin_comprobacion({"ok": 3, "aviso": 1, "fallo": 2, "fecha": "2026-11-07T21:46:55", "resultados": [],
                        "categorias": {"INS": {"estado": "ok", "codigos": []}, "VIE": {"estado": "aviso", "codigos": ["VIE-11"]},
                                       "MET": {"estado": "fallo", "codigos": ["MET-05"]}, "RED": {"estado": "fallo", "codigos": ["RED-05"]}}})
    assert p.b_comprobar.text() == "Volver a comprobar" and T["INS"].estado == "ok" and T["INS"].findChild(QtWidgets.QLabel, "chip_fallo") is None
    assert T["MET"].findChild(QtWidgets.QLabel, "chip_fallo").text() == "MET-05" and T["ENT"].estado == "pendiente"
    assert T["RED"].findChild(QtWidgets.QLabel, "chip_fallo").text() == "RED-05" and T["RED"].estado == "fallo"
    p.set_comprobando(True)                                                     # otra vez: todo vuelve a «en espera», sin etiquetas
    from PySide6 import QtCore
    QtCore.QCoreApplication.sendPostedEvents(None, QtCore.QEvent.Type.DeferredDelete)
    assert all(t.estado == "pendiente" and not t.codigos for t in T.values()) and T["VIE"].findChild(QtWidgets.QLabel, "chip_aviso") is None
    p.set_prueba(5, {"categoria": "INS", "estado": "en_curso", "codigos": []})
    p.fin_comprobacion(None)                                                    # cancelada a medias: la que giraba vuelve a «en espera»
    assert T["INS"].estado == "pendiente" and not T["INS"].indicador.girando()
    p.close()
    p.deleteLater()


@con_qt
def test_la_pagina_planta_ensena_su_ficha_y_sus_graficos_con_los_botones_de_las_capas(app, tmp_path):
    # usuario, 2026-11-07: «mejorar el diseño de este panel», sin quitar los botones de las capas; luego, «dale una vuelta estética»
    from PySide6 import QtWidgets
    from teodors.gui import panel, tema
    from teodors.gui.planta_graficos import color_gradiente
    tema.aplicar(app)
    p = panel.Panel(planta.cargar_emplazamiento())
    p.resize(450, 1200)
    p.show()
    p.ir_a("planta")
    app.processEvents()
    assert not p.findChildren(QtWidgets.QPushButton, "plegable")                  # todo a la vista
    assert p.b_terreno.isVisibleTo(p) and not p.tarj_elevacion.isVisibleTo(p) and p.cifras["cota"][0].text() == "—"
    info = {"lado_km": 3, "res_m": 25, "fecha": "2026-10-22T16:01:00", "estadisticas": {"z_min": 0, "z_max": 1200, "z_media": 300},
            "planta": {"z": 98, "uso_nombre": "Olivares"},
            "dir": str(tmp_path), "capas_mapa": [{"id": "elevacion", "png": "e.png", "bounds": [[38.5, 1.3], [38.7, 1.5]],
                                                  "leyenda": {"min": 0, "max": 1200, "gradiente": "#000000, #ffffff"}},
                                                 {"id": "usos", "png": "u.png", "bounds": [[38.5, 1.3], [38.7, 1.5]]}]}
    from PySide6 import QtGui
    for nombre, color in (("e.png", "#808080"), ("u.png", "#ffaa00")):
        img = QtGui.QImage(200, 200, QtGui.QImage.Format.Format_ARGB32)
        img.fill(QtGui.QColor(color))
        img.save(str(tmp_path / nombre))
    resumen = {"bandas": [{"banda": b, "pct": x} for b, x in (("< 50 m", 20), ("50–200 m", 30), ("200–500 m", 25), ("500–1000 m", 15), ("> 1000 m", 10))],
               "grupos": [{"nombre": "Forestal", "color": "#00aa00", "pct": 30.0, "clases": [{"nombre": "Pinar", "pct": 30.0}]},
                          {"nombre": "Agrícola", "color": "#ffee00", "pct": 70.0, "clases": []}, {"nombre": "Mar", "color": "#99ccff", "pct": 0.0}],
               "nucleos": [{"familia": "residencial", "dist_m": 3200, "rumbo": "NE"}, {"familia": "residencial", "dist_m": 5000, "rumbo": "S"},
                           {"familia": "industrial", "dist_m": 5800, "rumbo": "N"}]}
    p.set_terreno(info, resumen)
    p.set_edificios({"por_uso": {"Industrial": 3, "Agrario": 2}, "fecha": "2026-10-24T18:59", "n_descargados": 867, "viviendas": 393})
    app.processEvents()
    # la ficha: cuatro cifras; las fechas de descarga, al pasar por encima
    assert [p.cifras[k][0].text() for k in ("cota", "dominio", "nucleo", "edificios")] == ["98 m", "3 × 3 km", "3,2 km NE", "867"]
    assert p.cifras["cota"][1].text() == "cota de la planta · olivares" and p.cifras["edificios"][1].text() == "edificios a 1,5 km · 393 viviendas"
    assert "2026-10-22 16:01" in p.tarj_ficha.toolTip() and "2026-10-24 18:59" in p.lbl_edificios.toolTip() and not p.b_terreno.isVisibleTo(p)
    # una imagen en cada tarjeta (usuario: «una por cada panel de terreno y de usos del suelo»): el relieve en la de la elevación y los usos
    # en la suya, sin botón para cambiar; la planta, en el centro de la vista (está en el centro de las imágenes)
    R, U = p.mini_relieve, p.mini_usos
    assert R.parent() is p.tarj_elevacion and U.parent() is p.tarj_usos and R.isVisibleTo(p) and U.isVisibleTo(p)
    assert (R.modo, U.modo) == ("relieve", "usos") and not any(b.isVisibleTo(p) for m in (R, U) for b in m.botones.values())
    trozo, (fx, fy), parte = R.recorte(200, 200)
    assert abs(fx - 0.5) < 0.02 and abs(fy - 0.5) < 0.05 and 0 < parte <= 1 and trozo.height() < 200
    for m, color in ((R, "#808080"), (U, "#ffaa00")):
        img = m.grab().toImage()
        assert img.pixelColor(img.width() // 4, img.height() // 2).name() == color
    # la elevación: una barra por franja, del color de su cota en la capa del mapa, y la de la planta (98 m) marcada
    B = p.barras_cota
    assert len(B._bandas) == 5 and B._planta == 1 and p.tarj_elevacion.titulo.text() == "Elevación · 0 a 1 200 m"
    assert B._colores[0].name() == color_gradiente(["#000000", "#ffffff"], 25 / 1200).name() and B._colores[4].lightness() > B._colores[0].lightness()
    # los usos: la barra al 100 %, del mayor al menor y sin los que no hay; su leyenda, una fila por grupo con sus clases al pasar por encima
    assert [g["nombre"] for g in p.barra_usos._grupos] == ["Agrícola", "Forestal"]
    filas = [p.leyenda_usos.itemAtPosition(k, 1).widget().text() for k in range(2)]
    assert filas == ["<b>70,0 %</b>", "<b>30,0 %</b>"] and "Pinar: 30,0 %" in p.leyenda_usos.itemAtPosition(1, 0).widget().toolTip()
    assert p.leyenda_usos.rowCount() == 2                                          # con menos de USOS_A_LA_VISTA, sin «Otros»
    # los núcleos, por familia, con el más cercano a la derecha; los edificios de al lado, por uso
    N = p.cifras_nucleos
    assert (N["residencial"][0].text(), N["residencial"][1].text()) == ("2", "urbanos<br>a 3,2 km NE")
    assert (N["industrial"][0].text(), N["industrial"][1].text()) == ("1", "industrial<br>a 5,8 km N") and N["deportivo"][1].text() == "deportivos"
    assert "Industrial&nbsp;<b>3</b>" in p.lbl_edificios.text()
    # los botones de las capas, como estaban
    assert [b.text() for b in (p.b_ver_elevacion, p.b_ver_usos, p.b_ver_edificios)] == ["Ver elevación", "Ver usos del suelo", "Ver edificios"]
    p.close()
    p.deleteLater()


@con_qt
def test_la_pagina_focos_plano_configuracion_lista_y_calendario_de_emision(app, tmp_path):
    # usuario, 2026-11-08: «imagen del mapa con los focos, y seguido el botón de configuración del foco. Después la lista de focos y un
    # calendario igual que el del viento pero con olores y gases, y debajo de él el botón de configuración de la operabilidad»
    import datetime as dt
    from PySide6 import QtCore, QtGui, QtWidgets
    from teodors.gui import panel, tema
    from teodors.gui.focos_graficos import COLORES, cifra_corta, color_emision, forma
    from teodors.operacion import planes as E
    tema.aplicar(app)
    p = panel.Panel(planta.cargar_emplazamiento())
    p.resize(450, 1900)
    p.show()
    p.ir_a("focos")
    app.processEvents()
    assert not p.tarj_lista_focos.isVisibleTo(p) and not p.tarj_operacion.isVisibleTo(p)              # sin focos
    focos = [{"id": "A", "nombre": "Pila", "modelo": "superficie", "ubicacion": {"poligono": [[0, 0], [20, 0], [20, 10], [0, 10]]},
              "olor": {"valor": 50, "unidad": "ou_E/(s·m2)"}, "funcionamiento": {"modo": "horario", "horas": "8-16", "fuera_pct": 0}},
             {"id": "B", "nombre": "Chimenea", "modelo": "punto", "ubicacion": {"x": 40, "y": 30}, "olor": {},
              "gases": [{"gas": "PROPANE", "valor": 0.2, "unidad": "g/s"}]},
             {"id": "C", "nombre": "Nave", "modelo": "volumen", "ubicacion": {"x": 10, "y": 30}, "dimensiones": {"largo_m": 8, "ancho_m": 4},
              "olor": {"valor": 1500, "unidad": "ou_E/s"}}]
    cat = {"focos": focos, "actualizado": "2026-10-26"}
    p.set_focos(cat)
    p.set_huellas([[(30, 20), (50, 20), (50, 40), (30, 40)]])
    app.processEvents()
    assert "2026-10-26" in p.tarj_focos.toolTip() and p.tarj_lista_focos.isVisibleTo(p) and p.tarj_operacion.isVisibleTo(p)
    # en orden: el plano, el botón de configuración de los focos, el calendario con el botón de la operación y, después, la lista (usuario,
    # 2026-11-08: «que primero salga el calendario y luego el total de emisiones», que depende del plan)
    y = [w.mapTo(p, QtCore.QPoint(0, 0)).y() for w in (p.plano_focos, p.b_conf_focos, p.cal_emision, p.b_operacion, p.barras_emision)]
    assert y == sorted(y)
    assert p.b_conf_focos.text() == "Ver focos…" and p.b_operacion.text() == "Configurar la operación…"
    assert "caudal" in p.b_conf_focos.toolTip() and "temperatura" in p.b_conf_focos.toolTip()
    assert p.b_conf_focos.objectName() == p.b_operacion.objectName() == "primario"            # los dos, del mismo color
    # el plano: las formas de los focos (como el de la ventana de focos) sobre los edificios, cuántos hay de cada modelo y el foco bajo el ratón
    assert forma(focos[2]) == ("poligono", [(6.0, 28.0), (14.0, 28.0), (14.0, 32.0), (6.0, 32.0)]) and forma({"ubicacion": {}}) is None
    P = p.plano_focos
    assert P.cuantos() == {"superficie": 1, "punto": 1, "volumen": 1}
    enc = P._encuadre()
    assert P.foco_en(P._a_px(10, 5, enc))["id"] == "A" and P.foco_en(P._a_px(40, 30, enc))["id"] == "B"
    assert P.foco_en(P._a_px(10, 30, enc))["id"] == "C" and P.foco_en(QtCore.QPointF(2, 2)) is None
    img = P.grab().toImage()
    k = img.devicePixelRatio()
    pix = img.pixelColor(QtCore.QPoint(int(P._a_px(10, 5, enc).x() * k), int(P._a_px(10, 5, enc).y() * k)))
    assert abs(pix.hue() - QtGui.QColor(COLORES["superficie"][0]).hue()) < 15 and pix.saturation() > 20      # pintado con su color
    # usuario, 2026-11-08: «que se vea la imagen satélite y encima los focos». La ortofoto (`fuentes.ortofoto`), en su recuadro UTM
    assert not P.con_ortofoto()
    foto =QtGui.QImage(64, 64, QtGui.QImage.Format.Format_RGB32)
    foto.fill(QtGui.QColor(200, 30, 30))
    foto.save(str(tmp_path / "orto.jpg"))
    p.set_ortofoto({"ruta": str(tmp_path / "orto.jpg"), "recuadro": [-100, -100, 150, 150], "credito": "© Fondo X"})
    p.set_ortofoto(None)                                                     # sin ortofoto nueva, se queda la que hay
    assert P.con_ortofoto()
    img = P.grab().toImage()
    fuera = img.pixelColor(QtCore.QPoint(int(P._a_px(60, 15, enc).x() * k), int(P._a_px(60, 15, enc).y() * k)))
    assert abs(fuera.red() - 200) < 12 and fuera.green() < 45                                     # la foto, donde no hay focos
    pix = img.pixelColor(QtCore.QPoint(int(P._a_px(10, 5, enc).x() * k), int(P._a_px(10, 5, enc).y() * k)))
    assert abs(pix.hue() - QtGui.QColor(COLORES["superficie"][0]).hue()) < 15                    # y los focos, encima
    # lo que se emite, en botones encima del calendario (el olor y los gases); la lista, lo que emite cada foco el día elegido con el plan
    # (hoy, con la Base: la pila de 8 a 16 h), de mayor a menor y, sin dato, al final
    assert {c: b.text() for c, b in p.botones_mag.items()} == {"olor": "Olor", "PROPANE": "Propane"} and p.botones_mag["olor"].isChecked()
    B = p.barras_emision
    assert [(i, m) for i, _, m, _ in B.filas()] == [("A", "superficie"), ("C", "volumen"), ("B", "punto")]
    d0 = dt.date.today()
    # la chimenea, sin olfatometría, con el olor que da su propano por su umbral de Nagata (1 500 ppm): casi nada, pero cuenta
    from teodors.operacion import focos as F
    b = F.olor_ouE_s(focos[1])
    assert 0 < b < 0.1
    assert B.filas()[0][3] == pytest.approx(50 * 200 * 8 / 24) and B.filas()[1][3] == pytest.approx(1500) and B.filas()[2][3] == pytest.approx(b)
    assert p.tarj_lista_focos.titulo.text() == f"Emisión por foco · {d0.day}/{d0.month}/{d0.year} · olor, ou_E/s"
    assert p.rejilla_mag.parentWidget() is p.tarj_operacion
    assert [cifra_corta(v) for v in (343, 9827, 68500, 1234567, 0.0056, 0.00097)] == ["343", "9\u00a0827", "68,5 k", "1,23 M", "0,0056", "0,00097"]
    # el foco de la lista bajo el ratón, resaltado en el plano
    sin = QtCore.Qt.MouseButton.NoButton
    pos = QtCore.QPointF(40, B.FILA * 1.5)
    QtWidgets.QApplication.sendEvent(B, QtGui.QMouseEvent(QtCore.QEvent.Type.MouseMove, pos, QtCore.QPointF(B.mapToGlobal(pos)), sin, sin,
                                                          QtCore.Qt.KeyboardModifier.NoModifier))
    assert P._resaltado == "C"
    B.leaveEvent(None)
    assert P._resaltado is None
    # el calendario: con la Base, todos los días igual; su color, el de la escala del olor, y sus horas en la franja
    cal = p.cal_emision
    hoy = dt.date.today()
    assert cal.elegido() == hoy and cal.dentro(dt.date(hoy.year - 1, 1, 1)) and not cal.dentro(dt.date(hoy.year + 2, 1, 1))
    media = (8 * 10000 + 24 * 1500) / 24 + b
    assert cal.info(hoy)["media"] == pytest.approx(media) and p._tope_emision == pytest.approx(11500 + b)
    assert cal.color_dia(cal.info(hoy)) == color_emision("escala_olor", media / (11500 + b))
    assert "Media 4\u00a0833 ou_E/s · máxima 11,5 k a las 08:00" in cal.texto_dia(cal.info(hoy))
    assert p.franja_emision._modelos["superficie"][8] == 10000 and p.franja_emision._modelos["volumen"][3] == 1500
    assert cal.leyenda.texto() == "Emisión media del día, ou_E/s"
    # la franja, con la escala de color del calendario (usuario, 2026-11-08): las 8, con todo al 100 %, del color del tope
    Fr = p.franja_emision
    assert Fr.horas()[8] == pytest.approx(11500 + b) and Fr.horas()[3] == pytest.approx(1500 + b)
    img = Fr.grab().toImage()
    k = img.devicePixelRatio()
    pix = img.pixelColor(QtCore.QPoint(int(8.5 * Fr.width() / 24 * k), int((Fr.height() - Fr.ABAJO - 8) * k)))
    tope = color_emision("escala_olor", 1.0)
    assert max(abs(pix.red() - tope.red()), abs(pix.green() - tope.green()), abs(pix.blue() - tope.blue())) <= 3
    # un gas: la lista y el calendario lo siguen, con su unidad y la escala de los gases
    p.botones_mag["PROPANE"].click()
    assert p.tarj_lista_focos.titulo.text() == f"Emisión por foco · {d0.day}/{d0.month}/{d0.year} · Propane, g/s"
    assert B.filas()[0][:3] == ("B", "Chimenea", "punto")
    assert B.filas()[0][3] == pytest.approx(0.2) and cal.info(hoy)["media"] == pytest.approx(0.2)
    assert p.tarj_operacion.titulo.text() == "Calendario de emisión · Propane" and cal.leyenda.texto() == "Emisión media del día, g/s"
    assert cal.color_dia(cal.info(hoy)) == color_emision("escala_gases", 1.0)
    p.botones_mag["olor"].click()
    # un plan guardado: se elige encima del calendario y lo repinta; uno mensual lleva el calendario a su mes
    esc = E.nuevo(cat, "Pila parada en febrero")
    pf = E.plan_foco(focos[0], esc)
    E.cambiar_plan(pf, "mensual", f"{hoy.year + 1}-02")
    esc["mes"] = f"{hoy.year + 1}-02"
    E.poner_perfil(pf, [0], [0.0] * 24)                                      # el día 1, la pila parada
    ruta = E.guardar(esc, tmp_path)
    p.set_planes([(esc["nombre"], str(ruta)), ("Roto", str(tmp_path / "no_existe.json"))], False)
    assert [p.cmb_plan_focos.itemText(i) for i in range(p.cmb_plan_focos.count())] == ["Base", "Pila parada en febrero", "Roto"]
    p.cmb_plan_focos.setCurrentIndex(1)
    assert cal.mes() == (hoy.year + 1, 2) and cal.elegido() == dt.date(hoy.year + 1, 2, 1)
    assert cal.info(dt.date(hoy.year + 1, 2, 1))["media"] == pytest.approx(1500 + b) and cal.info(dt.date(hoy.year + 1, 2, 2))["media"] == pytest.approx(media)
    # la lista sigue al plan y al día: el 1 de febrero, la pila parada; el 2, como en la Base
    assert {i: v for i, _, _, v in B.filas()} == {"A": 0.0, "C": pytest.approx(1500), "B": pytest.approx(b)}
    assert p.tarj_lista_focos.titulo.text().startswith(f"Emisión por foco · 1/2/{hoy.year + 1} ·")
    cal.elegir(dt.date(hoy.year + 1, 2, 2), avisar=True)
    assert {i: v for i, _, _, v in B.filas()}["A"] == pytest.approx(50 * 200 * 8 / 24)
    p.cmb_plan_focos.setCurrentIndex(2)                                      # un plan que no se puede leer: la Base
    assert cal.info(dt.date(hoy.year + 1, 2, 1))["media"] == pytest.approx(media)
    # los dos botones abren sus ventanas
    vistos = []
    p.verFocos.connect(lambda: vistos.append("focos"))
    p.verPlanes.connect(lambda: vistos.append("planes"))
    p.b_conf_focos.click()
    p.b_operacion.click()
    assert vistos == ["focos", "planes"]
    p.close()
    p.deleteLater()


@con_qt
def test_la_actividad_ensena_avisos_y_errores_y_toda_la_comprobacion(app):
    # usuario, 2026-11-07: «que vaya soltando mensajes positivos o negativos en el log de actividad»; de lo demás, solo avisos y errores
    from teodors.comun import registro
    from teodors.gui import tema
    from teodors.gui.consola import Consola
    tema.aplicar(app)
    c = Consola()
    c.conectar()
    nivel = registro.get().level
    registro.get().setLevel("DEBUG")                                            # como lo deja registro.configurar en la app
    try:
        registro.get("gui").info("Mapa listo.")
        registro.get("comprobar").info("✓ Viento 3D del reanálisis: 60 meses")
        registro.get("comprobar").warning("⚠ VIE-11 · Falta el viento alrededor de los edificios")
        registro.get("gui").error("No se pudo cargar el viento")
        app.processEvents()
        lineas = [(color, texto) for color, texto in c._lineas]
        assert [t.split("  ", 1)[1].strip() for _, t in lineas] == [
            "INFO    ✓ Viento 3D del reanálisis: 60 meses", "AVISO   ⚠ VIE-11 · Falta el viento alrededor de los edificios",
            "ERROR   No se pudo cargar el viento"]
        assert [color for color, _ in lineas] == ["acento_claro", "aviso", "fallo"]          # lo bueno, en el color del acento
    finally:
        registro.get().setLevel(nivel)
        c.desconectar()
        c.deleteLater()


@con_qt
def test_el_panel_de_la_estela_elige_el_peor_viento_y_se_cambia_con_un_clic(app):
    # usuario, 2026-11-08: «un panel casi tridimensional que ayude a entender los conceptos de la estela»: una nave de 10 m al este de una
    # chimenea de 12 m (saldría libre a 25 m); al empezar, un viento que la mete en la estela; un clic en la corona elige otro
    from PySide6 import QtCore, QtGui, QtWidgets
    from teodors.gui import tema
    from teodors.gui.focos_graficos import PanelEstela
    from teodors.operacion import estela as ES
    tema.aplicar(app)
    nave = {"ref": "N1", "verts": [(20.0, -15.0), (50.0, -15.0), (50.0, 15.0), (20.0, 15.0)], "altura_m": 10.0, "fuente": "LiDAR", "dist_m": 20.0}
    est = ES.calcular(0.0, 0.0, 12.0, [nave])
    foco = {"id": "P", "modelo": "punto", "altura_m": 12.0, "ubicacion": {"x": 0.0, "y": 0.0},
            "salida": {"diametro_m": 0.8, "temperatura_C": 20.0, "orientacion": "vertical"}}
    p = PanelEstela()
    p.resize(460, 410)
    p.poner(foco, [nave], est)
    assert p.estado() == "ok" and len(p.filas()) == 36
    assert next(f for f in p.filas() if f["desde"] == p.elegido())["dentro"]            # el peor: uno que la mete en la estela
    p.elegir(90.0)
    huella, techo, manda = p._zona()
    assert techo == pytest.approx(25.0) and manda["ref"] == "N1" and max(x for x, _ in huella) == pytest.approx(50.0 + 2 * 10.0)    # 2 L a barlovento
    assert not p.grab().isNull()
    # un clic en la corona, en el sur: el viento del sur, sin edificio a barlovento
    g = p._geo()
    sur = p._p(g, 0.0, -g[5] * 1.07)
    QtWidgets.QApplication.sendEvent(p, QtGui.QMouseEvent(QtCore.QEvent.Type.MouseButtonPress, sur, p.mapToGlobal(sur), QtCore.Qt.MouseButton.LeftButton,
                                                          QtCore.Qt.MouseButton.LeftButton, QtCore.Qt.KeyboardModifier.NoModifier))
    assert p.elegido() == 180.0 and p._zona() is None
    # como un visor 3D (usuario, 2026-11-08: «si pudieras girar y mover el 3D»): arrastrar gira e inclina, el botón derecho mueve, la rueda acerca
    B, M, N = QtCore.Qt.MouseButton, QtCore.QEvent.Type, QtCore.Qt.KeyboardModifier.NoModifier

    def raton(tipo, pos, boton, pulsado):
        pos = QtCore.QPointF(*pos)
        QtWidgets.QApplication.sendEvent(p, QtGui.QMouseEvent(tipo, pos, p.mapToGlobal(pos), boton, pulsado, N))
    raton(M.MouseButtonPress, (8, 8), B.LeftButton, B.LeftButton)
    raton(M.MouseMove, (68, 38), B.NoButton, B.LeftButton)
    raton(M.MouseButtonRelease, (68, 38), B.LeftButton, B.NoButton)
    az, elev, zoom, mueve = p.vista()
    assert az == pytest.approx(30.0) and elev == pytest.approx(34.0 + 9.0) and zoom == 1.0 and mueve == (0.0, 0.0)
    raton(M.MouseButtonPress, (8, 8), B.RightButton, B.RightButton)
    raton(M.MouseMove, (48, 28), B.NoButton, B.RightButton)
    raton(M.MouseButtonRelease, (48, 28), B.RightButton, B.NoButton)
    assert p.vista()[3] == (40.0, 20.0)
    QtWidgets.QApplication.sendEvent(p, QtGui.QWheelEvent(QtCore.QPointF(230, 200), p.mapToGlobal(QtCore.QPointF(230, 200)), QtCore.QPoint(), QtCore.QPoint(0, 120),
                                                          B.NoButton, N, QtCore.Qt.ScrollPhase.NoScrollPhase, False))
    assert p.vista()[2] == pytest.approx(1.15) and not p.grab().isNull()
    # otro panel (la ficha rehecha) sigue igual: la vista y el viento elegido a mano, que se queda aunque se mueva la chimenea
    estado = p.estado_vista()
    q = PanelEstela()
    q.poner_vista(estado)
    q.poner(foco, [nave], est)
    assert q.vista() == p.vista() and q.elegido() == 180.0 and estado["desde"] == 180.0
    sin_elegir = PanelEstela()
    sin_elegir.poner(foco, [nave], est)
    assert sin_elegir.estado_vista()["desde"] is None and sin_elegir.filas()[round(sin_elegir.elegido() / 10) - 1]["dentro"]
    p.mouseDoubleClickEvent(None)
    assert p.vista() == (0.0, 34.0, 1.0, (0.0, 0.0))
    p.poner(dict(foco, ubicacion={}), [], None, "sin_punto")
    assert p.estado() == "sin_punto" and not p.grab().isNull()


@con_qt
def test_el_visor_3d_de_los_edificios_de_la_planta(app):
    # usuario, 2026-11-08: «introducir el visor 3D de estos edificios, como hicimos para los focos de punto, en el menú de edificios de planta»
    from PySide6 import QtCore, QtGui, QtWidgets
    from teodors.gui import tema
    from teodors.gui.focos_graficos import VisorEdificios
    tema.aplicar(app)

    def cuadro(x, y, lado, h, id_):
        return {"id": id_, "nombre": f"Nave {id_}", "origen": "lidar", "altura_m": h,
                "poligono": [[x, y], [x + lado, y], [x + lado, y + lado], [x, y + lado]]}
    eds = [cuadro(500000.0, 4500000.0, 20.0, 12.0, "E01"), cuadro(500060.0, 4500000.0, 10.0, 5.0, "E02")]
    v = VisorEdificios()
    v.resize(420, 320)
    v.poner(eds)
    centro, radio = v._centro, v._radio
    assert centro == (500035.0, 4500010.0) and len(v.edificios()) == 2 and v.elegido() is None
    assert not v.grab().isNull()
    # un clic (sin arrastrar) en un edificio lo elige y avisa
    pulsados = []
    v.pulsado.connect(pulsados.append)
    B, M, N = QtCore.Qt.MouseButton, QtCore.QEvent.Type, QtCore.Qt.KeyboardModifier.NoModifier

    def raton(tipo, pos, boton, pulsado):
        pos = QtCore.QPointF(*pos)
        QtWidgets.QApplication.sendEvent(v, QtGui.QMouseEvent(tipo, pos, v.mapToGlobal(pos), boton, pulsado, N))
    sil = next(s for s, e, _ in v._siluetas if e["id"] == "E01")
    c = sil.boundingRect().center()
    assert v.edificio_en(c)["id"] == "E01" and v.edificio_en(QtCore.QPointF(3, 3)) is None
    raton(M.MouseButtonPress, (c.x(), c.y()), B.LeftButton, B.LeftButton)
    raton(M.MouseButtonRelease, (c.x(), c.y()), B.LeftButton, B.NoButton)
    assert pulsados == ["E01"] and v.elegido() == "E01" and v.vista() == (0.0, 34.0, 1.0, (0.0, 0.0))
    assert not v.grab().isNull()                                                     # con su nombre encima
    # arrastrar gira e inclina (como el de la chimenea) y no elige
    raton(M.MouseButtonPress, (c.x(), c.y()), B.LeftButton, B.LeftButton)
    raton(M.MouseMove, (c.x() + 60, c.y() + 30), B.NoButton, B.LeftButton)
    raton(M.MouseButtonRelease, (c.x() + 60, c.y() + 30), B.LeftButton, B.NoButton)
    assert v.vista()[:2] == (pytest.approx(30.0), pytest.approx(43.0)) and pulsados == ["E01"]
    # cambiar un edificio no mueve el encuadre; uno que no cabe, sí
    eds[1]["altura_m"] = 7.0
    v.poner(eds, "E01")
    assert (v._centro, v._radio) == (centro, radio) and v.edificios()[1]["altura_m"] == 7.0
    v.poner(eds + [cuadro(500300.0, 4500000.0, 10.0, 5.0, "E03")], "E01")
    assert v._radio > radio
    v.poner([])
    assert v.edificios() == [] and not v.grab().isNull()                             # «Sin edificios de la planta»


@con_qt
def test_los_edificios_guardados_llegan_en_la_misma_sesion_al_3d_de_los_focos(app):
    # usuario, 2026-11-08: «si se cambió la altura de un edificio o se añadió, que en la misma sesión se actualice en el panel de focos del
    # visor 3D»; y al guardar, en la carpeta de la planta (la tendrá al volver a abrir) y en la configuración de los focos
    import types
    from teodors.gui import editor_focos, tema, ventana, ventana_focos
    from teodors.operacion import edificios_planta as EP
    from teodors.operacion import focos as F
    from teodors.planta import geo
    tema.aplicar(app)
    emp = planta.cargar_emplazamiento()
    x, y = geo.a_utm(emp["lat"], emp["lon"])

    def nave(h):
        return {"id": "E01", "nombre": "Nave", "origen": "dibujo", "altura_m": h,
                "poligono": [[x + 20, y - 10], [x + 40, y - 10], [x + 40, y + 10], [x + 20, y + 10]]}
    datos = EP.vacio()
    datos["edificios"] = [nave(10.0)]
    EP.guardar(datos)
    assert EP.ruta().parent == planta.actual().PLANTA and EP.cargar()["edificios"][0]["altura_m"] == 10.0     # en la carpeta de la planta
    f = F.nuevo(F.vacio(), None, "punto")
    f.update(id="F01", nombre="Chimenea", ubicacion={"x": x, "y": y}, altura_m=12.0)
    f["salida"].update(diametro_m=0.5, velocidad_m_s=10.0, temperatura_C=20.0)
    ficha = ventana_focos.Ficha(f, True, lambda _f: False, operabilidad=False, dibujo=False)
    app.processEvents()
    assert [e["altura_m"] for e in ficha.panel._ed] == [10.0] and max(f["edificios"]["hb"]) == pytest.approx(10.0)
    ficha.panel._az = 40.0                                                             # quien lo mira lo ha girado
    datos["edificios"] = [nave(20.0)]
    EP.guardar(datos)
    ficha.edificios_cambiados()
    assert [e["altura_m"] for e in ficha.panel._ed] == [20.0] and max(f["edificios"]["hb"]) == pytest.approx(20.0)
    assert ficha.panel.vista()[0] == 40.0                                              # y sigue mirando igual
    # el editor de focos abierto: la estela de los focos ya guardados, la que acaba de guardar `recalcular_focos` (guardar el foco no la deshace)
    guardado = dict(f, edificios={"hb": [7.0] * 36})
    F.guardar(dict(F.vacio(), focos=[guardado]))
    rehechas = []
    editor = types.SimpleNamespace(datos={"focos": [dict(f, edificios={"hb": [1.0] * 36})]}, f={"id": "F09", "modelo": "punto"},
                                   ficha=types.SimpleNamespace(edificios_cambiados=lambda: rehechas.append("ficha")))
    editor_focos.EditorFoco.edificios_cambiados(editor)
    assert editor.datos["focos"][0]["edificios"] == {"hb": [7.0] * 36} and rehechas == ["ficha"]
    # el tanque abierto que se edita, en la boca de un edificio: sigue al edificio, con la ficha y el plano rehechos
    pasos = []
    EP.guardar(dict(EP.vacio(), edificios=[dict(nave(8.0), id="E07")]))
    tanque = types.SimpleNamespace(datos={"focos": []}, f={"id": "F05", "modelo": "superficie", "superficie": {"clase": "tanque", "sobre": "E07"},
                                                          "ubicacion": {}, "altura_m": 6.0},
                                   area_ficha=types.SimpleNamespace(verticalScrollBar=lambda: types.SimpleNamespace(value=lambda: 0)),
                                   _mostrar_ficha=lambda _s=0: pasos.append("ficha"), _pinta_borrador=lambda: pasos.append("plano"),
                                   _marcar=lambda: pasos.append("marcar"))
    editor_focos.EditorFoco.edificios_cambiados(tanque)
    assert tanque.f["altura_m"] == 8.0 and len(tanque.f["ubicacion"]["poligono"]) == 4 and pasos == ["ficha", "plano", "marcar"]
    # la ventana de los focos: su lista y su ficha, y el editor abierto
    llamadas = []
    vf = types.SimpleNamespace(_recargar=lambda: llamadas.append("recargar"), _rellenar=lambda elegir=None: llamadas.append(("rellenar", elegir)),
                               _id_actual=lambda: "F01", editor=types.SimpleNamespace(isVisible=lambda: True,
                                                                                       edificios_cambiados=lambda: llamadas.append("editor")))
    ventana_focos.VentanaFocos.edificios_cambiados(vf)
    assert llamadas == ["recargar", ("rellenar", "F01"), "editor"]
    # la principal: la página Planta, la ventana de los focos y, si alguno cambió de estela, la página Focos
    llamadas.clear()
    vp = types.SimpleNamespace(_pinta_edificios_planta=lambda: llamadas.append("planta"), _cargar_focos=lambda: llamadas.append("focos"),
                               _ventana_focos=types.SimpleNamespace(edificios_cambiados=lambda: llamadas.append("ventana_focos")))
    ventana.VentanaPrincipal._edificios_cambiados(vp, ["F01"])
    assert llamadas == ["planta", "ventana_focos", "focos"]
    ficha.deleteLater()


@con_qt
def test_la_ficha_de_una_superficie_en_el_editor_con_su_3d(app):
    # usuario, 2026-11-08: «focos de superficies, desde piscinas, superficies de tanques abiertos; también debemos poder verlo en 3D»
    from PySide6 import QtCore, QtGui, QtWidgets
    import math
    from teodors.gui import editor_focos, tema, ventana_focos
    from teodors.operacion import edificios_planta as EP
    from teodors.operacion import focos as F
    from teodors.planta import geo
    tema.aplicar(app)
    emp = planta.cargar_emplazamiento()
    x, y = geo.a_utm(emp["lat"], emp["lon"])
    redondo = [[x + 30 + 8 * math.cos(k / 24 * 2 * math.pi), y + 8 * math.sin(k / 24 * 2 * math.pi)] for k in range(24)]
    nave = {"id": "E01", "nombre": "Nave", "origen": "lidar", "altura_m": 9.0, "poligono": [[x, y - 10], [x + 15, y - 10], [x + 15, y + 10], [x, y + 10]]}
    tanque = {"id": "E02", "nombre": "Depósito", "origen": "lidar", "altura_m": 6.2, "poligono": redondo}
    EP.guardar(dict(EP.vacio(), edificios=[nave, tanque]))
    f = F.nuevo(F.vacio(), None, "superficie")
    f["nombre"] = "Balsa"
    ficha = ventana_focos.Ficha(f, True, lambda _f: False, operabilidad=False, dibujo=False)
    rehechas = []
    ficha.rehacer.connect(lambda: rehechas.append(1))
    assert list(ficha.botones_clase) == ["balsa", "tanque", "biofiltro"] and ficha.botones_clase["balsa"].isChecked()
    assert ficha.botones_sobre == {} and "Sin dibujar" in ficha.lbl_superficie.text()             # una balsa no va en un edificio
    ficha._clase("biofiltro")                                                                         # su altura y su unidad
    assert f["superficie"]["clase"] == "biofiltro" and f["altura_m"] == 1.5 and f["olor"]["unidad"] == "ou_E/m3" and rehechas
    ficha._clase("tanque")
    ficha = ventana_focos.Ficha(f, True, lambda _f: False, operabilidad=False, dibujo=False)          # rehecha
    assert list(ficha.botones_sobre) == ["E02", "E01"] and f["olor"]["unidad"] == "ou_E/m3"          # lo redondo, delante
    # sin dibujar, el 3D enseña la planta; un clic en el depósito pone la superficie en su boca
    ficha.panel.resize(420, 360)
    assert not ficha.panel.grab().isNull() and len(ficha.panel.edificios()) == 2
    sil = next(s for s, e in ficha.panel._siluetas if e["id"] == "E02")
    c = sil.boundingRect().center()
    B, M, N = QtCore.Qt.MouseButton, QtCore.QEvent.Type, QtCore.Qt.KeyboardModifier.NoModifier
    for tipo, pulsado in ((M.MouseButtonPress, B.LeftButton), (M.MouseButtonRelease, B.NoButton)):
        QtWidgets.QApplication.sendEvent(ficha.panel, QtGui.QMouseEvent(tipo, c, ficha.panel.mapToGlobal(c), B.LeftButton, pulsado, N))
    assert f["superficie"]["sobre"] == "E02" and f["altura_m"] == 6.2 and F.area_m2(f) == pytest.approx(F.area_m2({"modelo": "superficie", "ubicacion": {"poligono": redondo}}), rel=0.01)
    ficha = ventana_focos.Ficha(f, True, lambda _f: False, operabilidad=False, dibujo=False)
    assert ficha.botones_sobre["E02"].isChecked() and "boca de Depósito" in ficha.lbl_superficie.text()
    assert [e["id"] for e in ficha.panel.edificios()] == ["E01"] and not ficha.panel.grab().isNull()      # el depósito es su cuerpo
    # la altura escrita a mano: ya no sigue al edificio
    ficha._editado(QtWidgets.QLineEdit("7"), ("altura_m",), True)
    assert f["altura_m"] == 7.0 and "sobre" not in f["superficie"]
    # una balsa dibujada: a ras de suelo, con su olor por m²
    b = F.nuevo(F.vacio(), None, "superficie")
    b["superficie"]["sobre"] = "E02"
    editor_focos.ubicar(b, "poligono", [(x, y + 40), (x + 30, y + 40), (x + 30, y + 60), (x, y + 60)])
    b["olor"] = {"valor": 3.0, "unidad": "ou_E/(s·m2)"}
    fb = ventana_focos.Ficha(b, True, lambda _f: False, operabilidad=False, dibujo=False)
    assert "sobre" not in b["superficie"] and "600 m² a ras de suelo" in fb.lbl_superficie.text() and "800 ou_E/s" in fb.lbl_superficie.text()    # 600 m\u00b2 \u00d7 3 ou_E/(s\u00b7m\u00b2) = 1 800
    fb.panel.resize(420, 360)
    assert not fb.panel.grab().isNull()
    vista = fb.panel.estado_vista()
    otra = ventana_focos.Ficha(b, True, lambda _f: False, operabilidad=False, dibujo=False)
    otra.panel.poner_vista(vista)
    assert otra.panel.vista() == fb.panel.vista()
    fb.edificios_cambiados()                                                       # se repinta con los edificios de ahora
    # un biofiltro: su olor en el aire tratado por el caudal tratado, y su carga superficial (el aire por m² de lecho)
    bio = F.nuevo(F.vacio(), None, "superficie")
    bio["superficie"]["clase"], bio["altura_m"] = "biofiltro", 1.5
    editor_focos.ubicar(bio, "rectangulo", [(x, y - 60), (x + 20, y - 60), (x + 20, y - 50), (x, y - 50)])
    bio["olor"] = {"valor": 300.0, "unidad": "ou_E/m3"}
    bio["salida"]["caudal_m3_h"] = 20000.0
    fbio = ventana_focos.Ficha(bio, True, lambda _f: False, operabilidad=False, dibujo=False)
    texto = fbio.lbl_superficie.text()
    assert "200 m² a 1,5 m" in texto and "carga 100 m³/(m²·h)" in texto and F.olor_ouE_s(bio) == pytest.approx(300.0 * 20000 / 3600)
    fbio.panel.resize(420, 360)
    assert not fbio.panel.grab().isNull()                                          # el lecho y el aire que sale
    # su gas de salida, como el de un punto: el caudal ⇄ el caudal por m² (su velocidad en m/h), la temperatura y la composición
    assert "Caudal por m²" in [w.text() for w in fbio.findChildren(QtWidgets.QLabel)] and fbio.lin_vel.placeholderText() == "≈ 100"
    assert fbio.lin_comp and "kg/m³" in fbio.lbl_densidad.text()
    bio2 = dict(bio, olor={"unidad": "ou_E/m3"}, salida={"caudal_m3_m2_h": 18.0}, gases=[{"gas": "H2S", "valor": 1.0, "unidad": "mg/m3"}])
    assert F.gases_g_s(bio2) == {"H2S": pytest.approx(1e-3)}                        # 1 mg/m³ × 18 m³/(m²·h) × 200 m² = 1 mg/s
    # por sus gases (usuario, 2026-11-08: «no por olor sino por gases»): los típicos de una vez, en mg/(m²·h)
    tip = next(w for w in fb.findChildren(QtWidgets.QPushButton) if w.text().startswith("+ Gases típicos"))
    tip.click()
    assert [g["gas"] for g in b["gases"]][:2] == ["NH3", "H2S"] and {g["unidad"] for g in b["gases"]} == {"ppm"}    # como un punto
    fg = ventana_focos.Ficha(b, True, lambda _f: False, operabilidad=False, dibujo=False)
    combos = [c for c in fg.findChildren(QtWidgets.QComboBox) if c.findData("mg/(m2·h)") >= 0]
    assert len(combos) == len(b["gases"]) and all(c.findData("ppm") >= 0 for c in combos)    # en concentración o por m²
    assert not [w for w in fg.findChildren(QtWidgets.QPushButton) if w.text().startswith("+ Gases típicos")]    # ya los tiene
    fg.deleteLater()
    for w in (ficha, fb, otra, fbio):
        w.deleteLater()


@con_qt
def test_la_ficha_de_un_volumen_pila_o_nave_con_su_3d(app):
    # usuario, 2026-11-08: «pasamos a volúmenes donde añadiremos las pilas de compostaje»: una hilera girada, dibujada con cuatro clics
    import math
    from PySide6 import QtWidgets
    from teodors.gui import editor_focos, tema, ventana_focos
    from teodors.operacion import focos as F
    from teodors.planta import geo
    tema.aplicar(app)
    emp = planta.cargar_emplazamiento()
    x, y = geo.a_utm(emp["lat"], emp["lon"])
    p = F.nuevo(F.vacio(), None, "volumen")
    p["nombre"] = "Hilera 1"
    t = math.radians(45.0)
    e, n = (math.sin(t), math.cos(t)), (math.cos(t), -math.sin(t))
    esq = [(x + a * 20 * e[0] + b * 3 * n[0], y + a * 20 * e[1] + b * 3 * n[1]) for a, b in ((-1, -1), (1, -1), (1, 1), (-1, 1))]
    medidas = editor_focos.ubicar(p, "poligono", esq)
    d = p["dimensiones"]
    assert (d["largo_m"], d["ancho_m"], d["orientacion_deg"]) == (40.0, 6.0, 45.0) and (medidas["largo"], medidas["ancho"]) == (40.0, 6.0)
    assert abs(p["ubicacion"]["x"] - x) < 0.1 and abs(p["ubicacion"]["y"] - y) < 0.1
    assert all(any(c == pytest.approx(q, abs=0.1) for q in esq) for c in F.planta_volumen(p))    # el plano la pinta girada, donde se dibujó
    d["alto_m"] = 3.0
    ficha = ventana_focos.Ficha(p, True, lambda _f: False, operabilidad=False, dibujo=False)
    assert list(ficha.botones_clase) == ["pila", "nave"] and ficha.botones_clase["pila"].isChecked() and list(ficha.botones_seccion) == ["hilera", "meseta"]
    assert ficha.lin_altura_vol.placeholderText() == "≈ 1,5" and "7 volúmenes en el modelo" in ficha.lbl_volumen.text()     # a media altura
    textos = [w.text() for w in ficha.findChildren(QtWidgets.QLabel)]
    assert "Caudal por m²" in textos and "Piel que emite" in textos
    ficha.panel.resize(420, 360)
    assert not ficha.panel.grab().isNull() and ficha.panel.partes() == 7
    piel = F.area_m2(p)
    ficha._seccion_pila("meseta")
    assert p["volumen"]["seccion"] == "meseta" and F.area_m2(p) != piel and not ficha.panel.grab().isNull()
    # una nave: un volumen solo, su planta y su caudal de ventilación, sin velocidad
    rehechas = []
    ficha.rehacer.connect(lambda: rehechas.append(1))
    ficha._clase_volumen("nave")
    assert rehechas and p["volumen"]["clase"] == "nave"
    nave = ventana_focos.Ficha(p, True, lambda _f: False, operabilidad=False, dibujo=False)
    textos = [w.text() for w in nave.findChildren(QtWidgets.QLabel)]
    assert nave.botones_seccion == {} and "Caudal de ventilación" in textos and "Planta" in textos and nave.lin_vel.isHidden()
    nave.panel.resize(420, 360)
    assert not nave.panel.grab().isNull() and nave.panel.partes() == 1 and "volúmenes en el modelo" not in nave.lbl_volumen.text()
    for w in (ficha, nave):
        w.deleteLater()


@con_qt
def test_los_edificios_de_la_planta_en_la_pagina_planta_solo_el_administrador_los_cambia(app):
    # usuario, 2026-11-08: «configurar los edificios vía 3 caminos: Catastro, LiDAR y dibujar/modificar desde el usuario de CIRCE, todo en Planta»
    from teodors.gui import panel, tema
    tema.aplicar(app)
    p = panel.Panel(planta.cargar_emplazamiento())
    assert p.fila_edificios_admin.isHidden() and list(p.botones_edificios) == ["catastro", "lidar", "dibujo"]       # el usuario normal, no
    p.set_admin(True)
    assert not p.fila_edificios_admin.isHidden()
    pedidos = []
    p.importarEdificios.connect(pedidos.append)
    p.editarEdificios.connect(lambda: pedidos.append("editar"))
    for b in p.botones_edificios.values():
        b.click()
    assert pedidos == ["catastro", "lidar", "editar"]
    assert "Sin edificios propios" in p.lbl_edificios_planta.text()
    assert p.visor_edificios.isHidden()                                                # sin edificios, sin visor
    p.set_edificios_planta({"total": 3, "por_origen": {"catastro": 0, "lidar": 2, "dibujo": 1}})
    assert "3 edificios" in p.lbl_edificios_planta.text() and "2 del LiDAR" in p.lbl_edificios_planta.text() and "1 dibujado" in p.lbl_edificios_planta.text()
    eds = [{"id": f"E0{k}", "nombre": f"E{k}", "origen": "lidar", "altura_m": 6.0 + k,
            "poligono": [[500000.0 + 30 * k, 4500000.0], [500010.0 + 30 * k, 4500000.0], [500010.0 + 30 * k, 4500010.0]]} for k in range(3)]
    p.set_edificios_planta({"total": 3, "por_origen": {"catastro": 0, "lidar": 3, "dibujo": 0}}, eds)
    assert not p.visor_edificios.isHidden() and len(p.visor_edificios.edificios()) == 3    # en 3D, también para el usuario normal
    p.set_admin(False)
    assert p.fila_edificios_admin.isHidden()
    p.deleteLater()


@con_qt
def test_el_editor_de_edificios_crea_cambia_y_elimina(tmp_path):
    # con el plano de verdad (un proceso aparte): un rectángulo crea un edificio, se le cambia la altura y el nombre, un círculo crea otro y se
    # elimina; al guardar, el fichero de la planta
    codigo = r"""
import json, os, sys
os.environ["QTWEBENGINE_CHROMIUM_FLAGS"] = "--host-resolver-rules=\"MAP * ~NOTFOUND\""
from PySide6 import QtCore, QtWebEngineWidgets, QtWidgets
QtCore.QCoreApplication.setAttribute(QtCore.Qt.ApplicationAttribute.AA_ShareOpenGLContexts)
app = QtWidgets.QApplication(["x"])
from teodors import planta
from teodors.gui import tema, web
web._descarga = lambda *a, **k: None
planta.activar(sys.argv[2])
planta.actual().MODO_EDICION = True
tema.aplicar(app)
from teodors.gui.editor_edificios import EditorEdificios
from teodors.operacion import edificios_planta as EP
from teodors.planta import geo
aj = QtCore.QSettings(sys.argv[1] + "/aj.ini", QtCore.QSettings.Format.IniFormat)
ed = EditorEdificios(planta.cargar_emplazamiento(), aj)
x, y = geo.a_utm(planta.cargar_emplazamiento()["lat"], planta.cargar_emplazamiento()["lon"])
r = {"al_abrir": [ed.lista.count(), ed.campos.isHidden(), len(ed.visor.edificios())]}
ed.nuevo()
esq = [geo.a_geo(x + a, y + b) for a, b in ((0, 0), (20, 0), (20, 10), (0, 10))]
ed.mapa.forma_dibujada.emit("rectangulo", esq)
e = ed._edificio(ed.sel)
r["rectangulo"] = [e["id"], e["origen"], e["altura_m"], round(EP.area_m2(e)), ed.lbl_medidas.text(), ed.windowTitle().endswith("*")]
ed.lin_altura.setText("12,5")
ed.lin_altura.editingFinished.emit()
ed.lin_nombre.setText("Nave de recepción")
ed.lin_nombre.editingFinished.emit()
r["editado"] = [e["altura_m"], e["nombre"], ed.lista.item(0).text(), [(d["id"], d["altura_m"]) for d in ed.visor.edificios()], ed.visor.elegido()]
ed.nuevo()
circ = [geo.a_geo(x + 50 + 8 * __import__("math").cos(t / 36 * 6.283185), y + 8 * __import__("math").sin(t / 36 * 6.283185)) for t in range(36)]
ed.mapa.forma_dibujada.emit("circulo", circ)
r["circulo"] = [ed.sel, len(ed._edificio(ed.sel)["poligono"]), ed.lista.count()]
ed.eliminar()
r["eliminado"] = [ed.lista.count(), ed.sel, len(ed.visor.edificios())]
ed.visor.pulsado.emit("E01")                        # un clic en el 3D lo elige en el editor
r["desde_3d"] = [ed.sel, ed.lin_nombre.text()]
ed.elegir("E01")
pts = [geo.a_geo(x + a, y + b) for a, b in ((0, 0), (30, 0), (30, 10), (0, 10))]
ed.mapa.forma_dibujada.emit("rectangulo", pts)
r["redibujado"] = [round(EP.area_m2(ed._edificio("E01"))), ed.lista.count()]
EP.altura_lidar = lambda puntos: 0.7                    # el LiDAR ve suelo ahí: un edificio posterior al vuelo
ed.nuevo()
ed.mapa.forma_dibujada.emit("rectangulo", [geo.a_geo(x + 100 + a, y + b) for a, b in ((0, 0), (10, 0), (10, 10), (0, 10))])
r["posterior"] = [ed._edificio(ed.sel)["altura_m"], ed.lbl_aviso_lidar.isHidden(), ed.b_lidar.text(), "posterior al vuelo" in ed.lbl_aviso_lidar.text()]
ed.eliminar()
ed.elegir("E01")
EP.altura_lidar = lambda puntos: 13.6
ed._pinta_ficha()
r["con_lidar"] = [ed.lbl_aviso_lidar.isHidden(), ed.b_lidar.text()]
guardados = []
ed.guardado.connect(guardados.append)
r["guardar"] = [ed.guardar(cerrar=False), guardados, [(e["id"], e["nombre"], e["origen"], e["altura_m"]) for e in EP.cargar()["edificios"]],
                ed.windowTitle().endswith("*")]
print("@@" + json.dumps(r, ensure_ascii=False), flush=True)
os._exit(0)
"""
    (tmp_path / "ajustes").mkdir()
    salida = _hijo(codigo, tmp_path, str(tmp_path / "ajustes"), str(tmp_path / "planta"))
    r = json.loads(next(l for l in salida.splitlines() if l.startswith("@@"))[2:])
    assert r["al_abrir"] == [0, True, 0]                                                # sin edificios, sin ficha
    ident, origen, alto, area, medidas, sucio = r["rectangulo"]
    assert (ident, origen, alto, area, sucio) == ("E01", "dibujo", 6.0, 200, True) and "20,0 × 10,0" in medidas    # sin LiDAR, 6 m
    assert r["editado"] == [12.5, "Nave de recepción", "Nave de recepción  ·  12,5 m", [["E01", 12.5]], "E01"]    # el 3D lo sigue
    assert r["desde_3d"] == ["E01", "Nave de recepción"]
    assert r["circulo"] == ["E02", 36, 2] and r["eliminado"] == [1, None, 1]
    assert r["redibujado"] == [300, 1]
    assert r["posterior"] == [6.0, False, "LiDAR 0,7 m", True]                         # no 0,7 m: los 6 m y un aviso para ponerla a mano
    assert r["con_lidar"] == [True, "LiDAR 13,6 m"]
    assert r["guardar"] == [True, [[]], [["E01", "Nave de recepción", "dibujo", 12.5]], False]


@con_qt
def test_el_riel_lleva_ajustes_y_ayuda_encima_de_actividad_y_no_hay_menu(app):
    # usuario: la configuración estaba arriba a la derecha, en la barra superior (2026-11-06); el menú no aportaba nada y su ayuda tiene botón (2026-11-07)
    from PySide6 import QtWidgets
    from teodors.gui import panel, tema
    tema.aplicar(app)
    p = panel.Panel(planta.cargar_emplazamiento())
    p.resize(450, 560)
    p.show()
    lay = p.findChild(QtWidgets.QFrame, "riel").layout()
    orden = []
    for i in range(lay.count()):
        w = lay.itemAt(i).widget()
        orden.append("—" if w is None else w.text() if isinstance(w, QtWidgets.QToolButton) else w.objectName())
    assert orden == [*(t for _, t, _, _ in panel.Panel.PAGINAS), "—", "Ajustes", "Ayuda", "Actividad", "Terminal"]
    assert p.b_ajustes.toolTip() == "Configuración"                 # «Configuración» no cabe en el riel
    assert not p.b_ayuda.isCheckable() and not p.b_ayuda.icon().isNull()
    pedidos = []
    p.verAjustes.connect(lambda: pedidos.append("ajustes"))
    p.verAyuda.connect(lambda: pedidos.append("ayuda"))
    p.b_ajustes.click()
    p.b_ayuda.click()
    assert pedidos == ["ajustes", "ayuda"]
    assert not hasattr(p, "b_menu") and not hasattr(p, "poner_menu")
    # Focos, con un matraz que emite y no con una diana; 3D, con una chimenea y sus bocanadas, que se diluyen, y no con un cubo; Planta, con un
    # digestor y su silo y no con una fábrica (usuario, 2026-11-07)
    assert "<circle" not in tema._ICONOS["focos"] and tema._ICONOS["focos"].count("<path") == 4
    assert tema._ICONOS["visor3d"].count("<circle") == 3 and tema._ICONOS["visor3d"].count("fill-opacity") == 2
    assert "V10l6 4v-4l6 4" not in tema._ICONOS["planta"] and "c.7-4.7 9.1-4.7 9.8 0" in tema._ICONOS["planta"]
    assert all(not p._b_pagina[k].icon().isNull() for k, _, _, _ in panel.Panel.PAGINAS)
    p.close()
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
from teodors.operacion import focos as F
datos = F.vacio()
datos["focos"] = [
    {"id": "F01", "nombre": "Chimenea", "tipo": "lavador", "modelo": "punto", "ubicacion": {"x": 500000.0, "y": 4500000.0}, "altura_m": 7.0,
     "salida": {"diametro_m": 0.3, "velocidad_m_s": 15.0, "temperatura_C": 180.0},
     "edificios": {"hb": [8.0] * 36, "hw": [20.0] * 36, "hl": [10.0] * 36, "xadj": [-5.0] * 36, "yadj": [0.0] * 36, "gep_m": 20.0},
     "olor": {"valor": 500, "unidad": "ou_E/m3"}, "gases": [{"gas": "H2S", "valor": 0.001, "unidad": "g/s"}], "observaciones": "nota interna"},
    {"id": "F02", "nombre": "Balsa", "tipo": "digestato", "modelo": "superficie",
     "ubicacion": {"poligono": [[500050.0, 4500000.0], [500070.0, 4500000.0], [500070.0, 4500010.0]]}, "altura_m": 0.5,
     "olor": {"valor": 3, "unidad": "ou_E/(s·m2)"}}]
F.guardar(datos)
from teodors.gui import widgets
widgets.preguntar_si = lambda *a, **k: True
avisos = []
QtWidgets.QMessageBox.warning = lambda _padre, _titulo, texto, *a, **k: avisos.append(texto)
sale = []
# el plano se abre con la vista de «Ver la planta» (usuario, 2026-11-09): centrado en la planta y con su zoom, cada vez que se abre la ventana
from teodors.gui import focos_mapa, mapa_web
html = focos_mapa.escribir_html(emp, ruta=__import__("pathlib").Path(sys.argv[1]) / "plano.html").read_text(encoding="utf-8")
vistas = []
focos_mapa.VistaFocos.ver_planta = lambda self, entera=False: vistas.append(type(self.window()).__name__ + (" entera" if entera else ""))
for modo in (False, True):
    planta.actual().MODO_EDICION = modo
    v = ventana_focos.VentanaFocos(emp, aj)
    filas = [v.lista.itemWidget(v.lista.item(k)) for k in range(v.lista.count())]
    ficha = v.ficha
    textos = [w.text() for w in ficha.findChildren(QtWidgets.QLabel)]
    r = {"editable": v.editable, "titulo": v.windowTitle(), "botones": [b.text() for b in (v.b_crear, v.b_modificar, v.b_eliminar) if b is not None],
         "filas": [[w.nombre.text(), w.tipo.text(), w.marca.isVisibleTo(w)] for w in filas], "cifras": [list(x) for x in ficha.cifras()],
         "gases": [[n, m] for n, m, _, _ in ficha.gases()], "observaciones": "nota interna" in textos,
         "funcionamiento": any("FUNCIONAMIENTO" in t or "Perfil del día" in t for t in textos),
         "sin_simular": any("Sin simular" in t for t in textos)}
    if not modo:
        v.show()
        v.hide()
        v.show()
        r["vistas"] = list(vistas)
        r["html"] = [f"var PLANTA = {json.dumps([emp['lat'], emp['lon']])}, ZOOM_PLANTA = {mapa_web.ZOOM_PLANTA}," in html,
                     "verPlanta: verPlanta" in html, "__PLANTA__" in html or "__ZOOM_PLANTA__" in html, mapa_web.ZOOM_PLANTA]
        v.hide()
    if modo:
        from teodors.gui import ventana_planes
        vp = ventana_planes.VentanaPlanes(emp, aj)
        vistas.clear()
        vp.show()
        r["vistas_planes"] = list(vistas)
        # usuario, 2026-11-09: el plano, debajo de la lista; en el centro, el mes y la semana (como Outlook) con la emisión del plan abierto
        import datetime as dt
        vp._elegir_id("F01")
        vp._cambiar_plan("semanal")
        vp.elegidos = {6}
        vp._aplicar([0.0] * 24)                                         # el domingo, apagada
        vp._dia_elegido(dt.date(2026, 11, 11))                          # un miércoles: su semana, y el miércoles del plan elegido
        sem = vp.semana
        r["operacion_ventana"] = [vp.mapa.parent() is not vp.divisor and vp.divisor_nav.isAncestorOf(vp.mapa), vp.divisor.count(),
                                  [d.isoformat() for d in sem._dias], sorted(vp.elegidos), [d.isoformat() for d in sorted(sem._marcados)],
                                  sem.bloques(0), sem.bloques(6), vp.lbl_semana.text(), sorted(vp.botones_mag), vp.cal.elegido().isoformat(),
                                  round(sum(sem._planta[0]) / 24), round(sum(sem._planta[6]) / 24), round(sum(sem._foco[0]) / 24),
                                  [round(F.emision(f, "olor")) for f in vp.catalogo["focos"]]]
        sem.dia_pulsado.emit("2026-11-14", QtCore.Qt.KeyboardModifier.NoModifier)
        r["operacion_ventana"] += [sorted(vp.elegidos), vp.lbl_dia.text()]
        vp._elegir_magnitud("H2S")
        r["operacion_ventana"] += [vp.lbl_calendario.text(), sem._unidad, vp.botones_mag["H2S"].isChecked()]
        # usuario, 2026-11-09: copiar un día y pegarlo de golpe en varios, elegidos arrastrando, por días de la semana o por grupos
        from PySide6 import QtGui, QtTest
        vp.esc["mes"] = "2026-11"
        vp._cambiar_plan("mensual")                                     # noviembre de 2026 empieza en domingo
        app.processEvents()                                             # la rejilla del mes, ya colocada: se arrastra sobre ella
        izq = QtCore.Qt.MouseButton.LeftButton
        QtTest.QTest.mousePress(vp.celdas[1], izq)                      # el lunes 2, con su horario, copiado
        horario = [1.0 if 7 <= h < 15 else 0.1 for h in range(24)]
        vp._aplicar(horario)
        vp.b_copiar.click()
        cp = [vp.celdas[1].copiada, sum(w.copiada for w in vp.celdas), vp.b_pegar.text(), vp.muestra.texto]
        QtTest.QTest.mousePress(vp.celdas[2], izq)                      # arrastrando del martes 3 al viernes 27
        g = vp.celdas[26].mapToGlobal(vp.celdas[26].rect().center())
        QtWidgets.QApplication.sendEvent(vp.celdas[2], QtGui.QMouseEvent(
            QtCore.QEvent.Type.MouseMove, QtCore.QPointF(vp.celdas[2].mapFromGlobal(g)), QtCore.QPointF(g), QtCore.Qt.MouseButton.NoButton,
            izq, QtCore.Qt.KeyboardModifier.NoModifier))
        QtTest.QTest.mouseRelease(vp.celdas[2], izq)
        cp += [sorted(i + 1 for i in vp.elegidos), vp.b_pegar.text()]
        vp.b_pegar.click()
        pf = vp._pf()
        cp += [vp.lbl_hecho.text(), [d + 1 for d in range(30) if list(ventana_planes.E.perfil_dia(pf, d)) == horario]]
        vp._elegir_columna(5, sumar=False)                              # la cabecera de los sábados, y con Ctrl, la de los domingos
        vp._elegir_columna(6, sumar=True)
        cp.append(sorted(i + 1 for i in vp.elegidos))
        vp._elegir_grupo("laborables", False)
        cp += [len(vp.elegidos), sorted(s.key().toString() for s in vp.findChildren(QtGui.QShortcut))]
        vp._elegir_id("F02")                                            # otro foco (diario): lo copiado sigue, sin su recuadro
        cp += [vp.b_pegar.isEnabled(), sum(w.copiada for w in vp.celdas), vp.fila_elegir.isHidden()]
        r["copiar_pegar"] = cp
        # usuario, 2026-11-09: la operación entera de un foco a otros del mismo tipo («copiar pila 1 a pila 2»); aquí, otra balsa, sin guardar
        otra = json.loads(json.dumps(next(f for f in vp.catalogo["focos"] if f["id"] == "F02")))
        otra.update(id="F09", nombre="Balsa 2")
        vp.catalogo["focos"].append(otra)
        vp._rellenar_lista()
        vp._elegir_id("F01")
        cf = [vp.b_copiar_foco.isEnabled()]                             # la chimenea: no hay otra
        vp._elegir_id("F02")
        vp._cambiar_plan("semanal")
        vp.elegidos = {6}
        vp._aplicar([0.0] * 24)
        vp.b_copiar_foco.click()
        menu = vp._menu_foco
        lista = menu.findChild(ventana_planes.ListaCopiarFoco)
        cf += [vp.b_copiar_foco.isEnabled(), menu.isVisible(), list(lista.marcas), lista.elegidos(), lista.b_copiar.text(), lista.todos.isHidden()]
        lista.b_copiar.click()
        pf2, pf9 = vp.esc["focos"]["F02"], vp.esc["focos"]["F09"]
        fila9 = next(vp.lista.itemWidget(vp.lista.item(k)).tipo.text() for k in range(vp.lista.count())
                     if vp.lista.item(k).data(QtCore.Qt.ItemDataRole.UserRole) == "F09")
        cf += [pf9 == pf2, pf9 is not pf2, menu.isVisible(), vp.lbl_copiada.text(), fila9, vp._texto_plan(next(f for f in vp.catalogo["focos"] if f["id"] == "F02"))]
        r["copiar_foco"] = cf
        vp.catalogo["focos"].remove(otra)
        vp._sucio = False
        vp._abrir(ventana_planes.E.base(vp.catalogo))
        vp.hide()
        guardados = []
        v.guardado.connect(lambda: guardados.append(1))
        v.eliminar()
        r["tras_eliminar"] = [f["id"] for f in F.cargar()["focos"]]
        r["guardado"] = len(guardados)
        r["filas_tras"] = v.lista.count()
        # crear: el editor, con las formas de cada modelo; un biofiltro (superficie) dibujado con el rectángulo
        from teodors.planta import geo
        v.crear()
        ed = v.editor
        r["editor"] = [ed.windowTitle(), ed.b_guardar.text(), list(ed.botones_forma), all(b.isEnabled() for b in ed.botones_modelo.values())]
        # el punto (usuario, 2026-11-08: sin tipo de catálogo, la actividad es el nombre; la actividad, los focos guardados, sin el que se edita)
        ed.botones_modelo["punto"].click()
        fp = ed.ficha
        r["punto"] = [ed.f["modelo"], [k for k, b in ed.botones_modelo.items() if b.isChecked()], hasattr(fp, "panel"), ed.f["nombre"], ed.f["tipo"],
                      [ed.lista_actividad.item(k).text() for k in range(ed.lista_actividad.count())], not ed.lista_actividad.isHidden()]
        # usuario, 2026-11-08: hacia dónde sale, en cuatro tarjetas; los edificios, en el panel (sin marcar la chimenea, vacío); los gases y su olor
        app.processEvents()
        r["orientacion"] = [list(fp.botones_orientacion), [k for k, b in fp.botones_orientacion.items() if b.isChecked()], fp.panel.estado()]
        fp.botones_orientacion["sombrerete"].click()
        r["orientacion"].append(ed.f["salida"]["orientacion"])
        # mover la chimenea no rehace la ficha: el panel 3D sigue como se miraba (usuario, 2026-11-08: «¿qué tal se actualiza el visor 3D?»)
        fp.panel._az = 40.0
        ed.mapa.forma_dibujada.emit("punto", [geo.a_geo(500300.0, 4500300.0)])
        ed.mapa.forma_dibujada.emit("punto", [geo.a_geo(500310.0, 4500320.0)])
        app.processEvents()
        r["mover"] = [ed.ficha is fp, fp.panel.vista()[0], {k: round(v) for k, v in ed.f["ubicacion"].items()}, ed.windowTitle().endswith("*")]
        ed.f["salida"].update(caudal_m3_h=1000.0, temperatura_C=20.0)
        ed.f["gases"] = [{"gas": "NH3", "valor": 3.0, "unidad": "mg/m3"}, {"gas": "H2S", "valor": 2.0, "unidad": "mg/m3"}]
        fp.refrescar()
        r["olor_gases"] = [[n, round(v)] for n, v in fp.olor_gases.filas()] + [fp.lbl_olor.text(), round(1000 / 3600 * 2 * 1000 / F.ug_por_ouE("H2S"))]
        ed.f["gases"] = []
        # usuario, 2026-11-08: la velocidad o el caudal (real o normal); el otro, calculado y en gris
        def flujo():
            return {k: v for k, v in ed.f["salida"].items() if k in ("velocidad_m_s", "caudal_m3_h", "caudal_Nm3_h", "caudal_kg_h")}
        ed.f["salida"].update(caudal_m3_h=None, diametro_m=0.5)
        fp.lin_caudal.setText("1 800")
        fp.lin_caudal.editingFinished.emit()
        r["caudal"] = [flujo(), fp.lin_vel.text(), fp.lin_vel.placeholderText()]
        fp.combo_caudal.setCurrentIndex(1)
        r["caudal"].append(flujo())
        fp.lin_vel.setText("12")
        fp.lin_vel.editingFinished.emit()
        from teodors.comun.formato import num
        r["caudal"] += [flujo(), fp.lin_caudal.text(), fp.lin_caudal.placeholderText(),
                        "≈ " + num(12 * 3.14159265 * 0.25 ** 2 * 3600 * 273.15 / 293.15, 0)]
        # la composición del gas de salida, para su densidad: empieza en N₂ 79 % y O₂ 21 %, y suma el 100 %; el caudal en kg/h pasa a velocidad
        # con ella (usuario, 2026-11-08)
        r["composicion"] = [[e.text() for e in fp.lin_comp.values()]]
        for gas, texto in (("N2", ""), ("O2", "1"), ("CO2", "97"), ("CH4", "2")):
            fp.lin_comp[gas].setText(texto)
            fp.lin_comp[gas].editingFinished.emit()
        r["composicion"] += [dict(ed.f["salida"]["composicion"]), [k for k, _ in fp.barra_comp.tramos()], fp.lbl_densidad.text()]
        fp.combo_caudal.setCurrentIndex(2)
        fp.lin_caudal.setText("500")
        fp.lin_caudal.editingFinished.emit()
        r["composicion"] += [flujo(), fp.lin_vel.placeholderText(), "≈ " + num(round(500 / 3600 / F.densidad_salida(ed.f) / (3.14159265 * 0.25 ** 2), 1), 1)]
        fp.lin_comp["CH4"].setText("5")
        fp.lin_comp["CH4"].editingFinished.emit()
        r["composicion"].append(fp.lbl_densidad.text())
        # la masa molar de cada gas, en su fila (usuario, 2026-11-08)
        ed.f["gases"] = [{"gas": "H2S", "valor": 2.0, "unidad": "ppm"}, {"gas": "NH3", "valor": 3.0, "unidad": "ppm"}]
        ed._mostrar_ficha()
        r["masas"] = [l.text() for _, l in ed.ficha.lbl_masas]
        ed.f["gases"] = []
        ed.botones_modelo["superficie"].click()
        r["formas_superficie"] = list(ed.botones_forma)
        (la0, lo0), (la1, lo1) = geo.a_geo(500100.0, 4500100.0), geo.a_geo(500120.0, 4500110.0)
        ed.mapa.forma_dibujada.emit("rectangulo", [(la0, lo0), (la0, lo1), (la1, lo1), (la1, lo0)])
        r["medidas"] = ed.lbl_medidas.text()
        r["funcionamiento_editor"] = any("FUNCIONAMIENTO" in w.text() for w in ed.ficha.findChildren(QtWidgets.QLabel))
        ed.f.update(altura_m=2.0, olor={"valor": 5, "unidad": "ou_E/(s·m2)"})
        # sin nombre o con el de otro (sin mirar mayúsculas ni espacios), no se guarda
        r["sin_nombre"] = [ed.guardar(cerrar=False), avisos[-1]]
        ed.f["nombre"] = " balsa"
        ed._pinta_actividad()
        r["repetido"] = [ed.guardar(cerrar=False), avisos[-1], ed.lbl_repetido.text()]
        ed.f["nombre"] = "Biofiltro nuevo"
        ed.guardar()
        r["tras_crear"] = [[f["id"], f["tipo"], round(F.area_m2(f) or 0), f["nombre"]] for f in F.cargar()["focos"]]
        r["elegido_tras_crear"] = v._id_actual()
        # nace con su operación por defecto, y la ventana de la operación ya hecha lo recoge (usuario, 2026-11-09)
        nuevo_f = next(f for f in F.cargar()["focos"] if f["nombre"] == "Biofiltro nuevo")
        antes = vp.lista.count()
        vp.focos_cambiados()
        filas_vp = [vp.lista.itemWidget(vp.lista.item(k)) for k in range(vp.lista.count())]
        r["operacion_nuevo"] = [nuevo_f["funcionamiento"], antes, vp.lbl_n.text(),
                                [[w.nombre.text(), w.tipo.text()] for w in filas_vp], sorted(vp.esc["focos"])]
        # modificar la balsa: el mismo tipo y modelo; redibujada con un círculo, sale un polígono de 36 vértices
        v._elegir_id("F02")
        v.modificar()
        ed = v.editor
        r["modificar"] = [any(b.isEnabled() for b in ed.botones_modelo.values()), [ed.lista_actividad.item(k).text() for k in range(ed.lista_actividad.count())],
                          list(ed.botones_forma)]
        c, b = geo.a_geo(500200.0, 4500200.0), geo.a_geo(500210.0, 4500200.0)
        pts = [geo.a_geo(500200.0 + 10 * __import__("math").cos(t / 36 * 6.283185), 4500200.0 + 10 * __import__("math").sin(t / 36 * 6.283185)) for t in range(36)]
        ed.mapa.forma_dibujada.emit("circulo", pts)
        r["medidas_circulo"] = ed.lbl_medidas.text()
        ed.guardar()
        balsa = next(f for f in F.cargar()["focos"] if f["id"] == "F02")
        r["balsa"] = [len(balsa["ubicacion"]["poligono"]), round(F.area_m2(balsa))]
    sale.append(r)
print("@@" + json.dumps(sale, ensure_ascii=False), flush=True)
os._exit(0)
"""
    salida = _hijo(codigo, tmp_path, str(tmp_path / "ajustes"), str(tmp_path / "planta"))
    galera, circe = json.loads(next(l for l in salida.splitlines() if l.startswith("@@"))[2:])
    # usuario, 2026-11-08: la lista a la izquierda, el mapa en medio y la ficha a la derecha; crear, modificar y eliminar, solo el administrador
    assert (galera["editable"], galera["titulo"]) == (False, "Focos de la planta · Inventada · Prueba") and galera["botones"] == []
    assert (circe["editable"], circe["titulo"]) == (True, "Focos de la planta · Inventada · Prueba · modo X")
    assert circe["botones"] == ["Crear", "Modificar", "Eliminar"]
    # la lista: el nombre, la emisión de olor y ⟳ (sin carpeta de respuestas: los dos, sin simular)
    assert [f[:2] for f in galera["filas"]][0][0] == "Chimenea" and all(f[2] for f in galera["filas"])
    assert galera["filas"][1] == ["Balsa", "300 ou_E/s", True]
    # la ficha, para leer: las cifras de un punto, sus gases, sin la operabilidad; las observaciones, solo para el administrador
    cifras = {q: v for _, v, q in galera["cifras"]}
    assert cifras["altura de emisión"] == "7,00 m" and cifras["diámetro"] == "0,30 m" and cifras["velocidad de salida"] == "15,0 m/s"
    assert cifras["temperatura"] == "180 °C"
    assert cifras["vientos en la estela de un edificio"] == "36 de 36" and cifras["altura para salir libre"] == "20,0 m"     # 8 + 1,5 × 8
    assert galera["gases"] == [["H₂S", "0,001 g/s"]] and not galera["funcionamiento"] and galera["sin_simular"]
    assert not galera["observaciones"] and circe["observaciones"]
    # eliminar (el administrador): se guarda, avisa y la lista lo pierde
    assert circe["tras_eliminar"] == ["F02"] and circe["guardado"] == 1 and circe["filas_tras"] == 1
    # el editor (usuario, 2026-11-08): formas según el modelo, el área de lo dibujado, sin la operabilidad; crear y modificar guardan
    titulo, boton, formas, tipo_libre = circe["editor"]
    assert titulo.startswith("Nuevo foco") and boton == "Crear el foco" and tipo_libre
    assert circe["formas_superficie"] == ["rectangulo", "circulo", "poligono"] and not circe["funcionamiento_editor"]
    assert circe["medidas"].startswith("Área: 20") and "× 10" in circe["medidas"]
    nuevo = [f for f in circe["tras_crear"] if f[3] == "Biofiltro nuevo"]
    assert len(nuevo) == 1 and nuevo[0][1] is None and abs(nuevo[0][2] - 200) <= 3 and circe["elegido_tras_crear"] == nuevo[0][0]
    assert circe["sin_nombre"] == [False, "Falta su nombre."]
    assert circe["repetido"] == [False, "Ya hay un foco «Balsa»: elige otro nombre.", "«Balsa» ya existe"]
    assert circe["modificar"] == [False, ["Biofiltro nuevo"], ["rectangulo", "circulo", "poligono"]] and "Radio: 10" in circe["medidas_circulo"]
    # el punto: su tarjeta marcada, el panel, sin nombre ni tipo; la actividad, los guardados (tras eliminar la chimenea, la balsa)
    assert circe["punto"] == ["punto", ["punto"], True, "", None, ["Balsa"], True]
    # el caudal escrito y la velocidad calculada, en gris; en Nm³/h, la misma cifra; escrita la velocidad, el caudal normal calculado
    escrito, vel, gris, normal, por_vel, caudal, gris_caudal, esperado = circe["caudal"]
    sin = {"velocidad_m_s": None, "caudal_m3_h": None, "caudal_Nm3_h": None, "caudal_kg_h": None}
    assert escrito == dict(sin, caudal_m3_h=1800.0) and vel == "" and gris == "≈ 2,5"
    assert normal == dict(sin, caudal_Nm3_h=1800.0)
    assert por_vel == dict(sin, velocidad_m_s=12.0) and caudal == "" and gris_caudal == esperado
    assert circe["masas"] == ["34,1 g/mol", "17,0 g/mol"]
    assert circe["mover"] == [True, 40.0, {"x": 500310, "y": 4500320}, True]
    al_principio, comp, tramos, densidad, kg, vel_gris, esperado_vel, pasa = circe["composicion"]
    assert al_principio == ["", "", "", "", "", "21", "79"]                             # CO₂, CO, CH₄, H₂, C₂H₆, O₂, N₂
    assert comp == {"O2": 1.0, "CO2": 97.0, "CH4": 2.0} and tramos == ["O2", "CO2", "CH4"] and "kg/m³" in densidad and "g/mol" in densidad
    assert kg == dict(sin, caudal_kg_h=500.0) and vel_gris == esperado_vel
    assert "suma 103" in pasa                                                           # 1 + 97 + 5 %
    assert circe["orientacion"] == [["vertical", "sombrerete", "horizontal", "abajo"], ["vertical"], "sin_punto", "sombrerete"]
    # el olor de cada gas por su umbral de Nagata, el dominante delante, y el del foco, el suyo: 1000 m³/h × 2 mg/m³ de H₂S
    (g1, ou1), (g2, ou2), texto, esperado = circe["olor_gases"]
    assert (g1, g2) == ("H₂S", "NH₃") and ou1 > ou2 > 0 and "Olor del foco" in texto and "H₂S" in texto and ou1 == esperado
    assert circe["balsa"][0] == 36 and abs(circe["balsa"][1] - 312) <= 3                       # 36 lados en un círculo de 10 m
    # usuario, 2026-11-09: las ventanas de focos y de la operación se abren con la vista de «Ver la planta», cada vez que se abren
    assert galera["vistas"] == ["VentanaFocos", "VentanaFocos"] and circe["vistas_planes"] == ["VentanaPlanes entera"]
    # usuario, 2026-11-09: la ventana de la operación, en tres columnas: los focos con el plano debajo; el mes y la semana de la emisión; el plan
    (plano_abajo, columnas, dias, elegidos, marcados, lunes, domingo, titulo, mags, elegido, planta_lun, planta_dom, foco_lun,
     (chimenea, balsa), elegidos_sab, dia_sab, lbl_gas, unidad_gas, chip_gas) = circe["operacion_ventana"]
    assert plano_abajo and columnas == 3
    assert dias == [f"2026-11-{d:02d}" for d in range(9, 16)] and elegidos == [2] and marcados == ["2026-11-11"] and elegido == "2026-11-11"
    assert lunes == [[0, 24, 1.0]] and domingo == []                    # la chimenea, como una cita todo el lunes; el domingo, apagada
    assert titulo == "Semana del 9 al 15 de noviembre de 2026" and mags == ["H2S", "olor"]
    assert balsa == 300 and abs(planta_lun - chimenea - balsa) <= 1 and planta_dom == balsa and foco_lun == chimenea > 0   # domingo: la balsa
    assert elegidos_sab == [5] and dia_sab == "Sábado"                  # un día de la semana elige el suyo en el plan
    assert lbl_gas == "CALENDARIO DE EMISIÓN · H₂S" and unidad_gas == "g/s" and chip_gas
    # usuario, 2026-11-09: «copiar un día y seleccionar varios para poder pegar todos de golpe»
    (origen, n_origen, pegar_1, muestra, arrastrados, pegar_16, hecho, con_horario, findes, laborables, atajos,
     pegar_otro, origen_otro, sin_elegir_diario) = circe["copiar_pegar"]
    assert origen and n_origen == 1 and pegar_1 == "Pegar en 1 día" and muestra.startswith("Copiado: Lunes 2 de noviembre · ")
    assert arrastrados == [3, 4, 5, 6, 10, 11, 12, 13, 17, 18, 19, 20, 24, 25, 26, 27] and pegar_16 == "Pegar en 16 días"   # de martes a viernes
    assert hecho == "Pegado en 16 días" and con_horario == [2] + arrastrados                   # el resto del mes, como estaba
    assert findes == [1, 7, 8, 14, 15, 21, 22, 28, 29] and laborables == 21
    assert {"Ctrl+A", "Ctrl+C", "Ctrl+V"} <= set(atajos)
    assert pegar_otro and origen_otro == 0 and sin_elegir_diario
    # usuario, 2026-11-09: «copiar una operabilidad de un foco, del mismo tipo, a otro: por ejemplo, pila 1 a pila 2»
    (sin_otro, con_otro, abierto, destinos, marcados, texto_boton, sin_todos, igual, copia, cerrado, aviso, fila, plan_origen) = circe["copiar_foco"]
    assert not sin_otro and con_otro and abierto and destinos == ["F09"] and marcados == ["F09"]       # solo otra balsa: ya marcada
    assert texto_boton == "Copiar a 1 foco" and sin_todos
    assert igual and copia and not cerrado and aviso == "Copiada a 1 foco" and fila == plan_origen and fila.startswith("Semanal")
    assert galera["html"] == [True, True, False, 18]
    # usuario, 2026-11-09: un foco nuevo nace con su operación por defecto (continuo, todo el día) y sale en la ventana de la operación abierta
    func, antes, titulo_n, filas_op, en_plan = circe["operacion_nuevo"]
    assert func == {"modo": "continuo"} and antes == 2 and titulo_n == "FOCOS (2)"             # antes: la chimenea y la balsa
    assert filas_op == [["Balsa", "Diario · 100 %"], ["Biofiltro nuevo", "Diario · 100 %"]] and len(en_plan) == 2


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


@con_qt
def test_el_3d_de_una_pila_la_mira_de_costado_hasta_que_se_gira(app):
    # una hilera vista por su testero no se entiende: el visor arranca de costado a su rumbo, y sigue así al rehacer la ficha
    from teodors.gui import tema
    from teodors.gui.focos_graficos import PanelVolumen
    from teodors.operacion import focos as F
    tema.aplicar(app)
    f = F.nuevo(F.vacio(), None, "volumen")
    f.update(ubicacion={"x": 500000.0, "y": 4500000.0})
    f["dimensiones"].update(largo_m=30.0, ancho_m=6.0, alto_m=3.0, orientacion_deg=30.0)
    a = PanelVolumen()
    a.poner(f, [])
    assert a.vista()[0] == 325.0
    b = PanelVolumen()
    b.poner(dict(f, dimensiones=dict(f["dimensiones"], orientacion_deg=60.0)), [])
    b.poner_vista(a.estado_vista())                                                  # nadie la giró: de costado a la nueva
    assert b.vista()[0] == 355.0
    a._tocada = True
    a._az = 10.0
    c = PanelVolumen()
    c.poner(f, [])
    c.poner_vista(a.estado_vista())                                                  # girada a mano: se queda como estaba
    assert c.vista()[0] == 10.0


@con_qt
def test_la_ficha_lleva_su_emision_con_el_viento_en_superficies_y_volumenes(app):
    # usuario, 2026-11-08: «una correlación en función del viento (añádelo en superficies); lo mismo para los volúmenes»
    from teodors.gui import tema, ventana_focos
    from teodors.operacion import focos as F
    tema.aplicar(app)
    for modelo in ("superficie", "volumen"):
        f = F.nuevo(F.vacio(), None, modelo)
        ficha = ventana_focos.Ficha(f, True, lambda _f: False, operabilidad=False, dibujo=False)
        assert ficha.botones_viento["constante"].isChecked() and not hasattr(ficha, "curva_viento")
        rehechas = []
        ficha.rehacer.connect(lambda: rehechas.append(1))
        ficha._modo_viento("viento")
        assert f["emision_viento"] == {"exponente": F.VIENTO_EXPONENTE, "viento_ref_m_s": F.VIENTO_REF_M_S} and rehechas
        otra = ventana_focos.Ficha(f, True, lambda _f: False, operabilidad=False, dibujo=False)
        assert otra.botones_viento["viento"].isChecked() and otra.curva_viento.factor(F.VIENTO_REF_M_S) == pytest.approx(1.0)
        assert "con 5 m/s" in otra.lbl_viento.text() and "Aún no entra en la simulación" in otra.lbl_viento.text()
        assert not otra.curva_viento.grab().isNull()
        otra._modo_viento("constante")
        assert "emision_viento" not in f
        for w in (ficha, otra):
            w.deleteLater()


@con_qt
def test_un_biofiltro_no_lleva_emision_con_el_viento(app):
    # una fuente activa (el aire sale empujado): lo que emite no depende del viento (Regione Lombardia, DGR IX/3018)
    from PySide6 import QtWidgets
    from teodors.gui import tema, ventana_focos
    from teodors.operacion import focos as F
    tema.aplicar(app)
    b = F.nuevo(F.vacio(), None, "superficie")
    b["superficie"]["clase"] = "biofiltro"
    ficha = ventana_focos.Ficha(b, True, lambda _f: False, operabilidad=False, dibujo=False)
    assert not ficha.botones_viento["viento"].isEnabled() and ficha.botones_viento["constante"].isChecked()
    assert any("fuente activa" in w.text() for w in ficha.findChildren(QtWidgets.QLabel))
    ficha.deleteLater()


@con_qt
def test_la_ficha_para_leer_lleva_sus_caracteristicas_arriba_y_el_3d_abajo(app):
    # usuario, 2026-11-08: «cuando seleccionas un foco, en el panel de la derecha las características principales arriba y abajo el visor 3D»
    from teodors.gui import focos_graficos as G
    from teodors.gui import tema, ventana_focos
    from teodors.operacion import focos as F
    tema.aplicar(app)
    sup = F.nuevo(F.vacio(), None, "superficie")
    sup.update(nombre="Balsa", ubicacion={"poligono": [[500000.0, 4500000.0], [500030.0, 4500000.0], [500030.0, 4500020.0], [500000.0, 4500020.0]]})
    sup["gases"] = [{"gas": "H2S", "valor": 10.0, "unidad": "mg/(m2·h)"}]
    vol = F.nuevo(F.vacio(), None, "volumen")
    vol.update(nombre="Hilera", ubicacion={"x": 500100.0, "y": 4500000.0}, emision_viento={"exponente": 0.5, "viento_ref_m_s": 0.3})
    vol["dimensiones"].update(largo_m=40.0, ancho_m=6.0, alto_m=2.5, orientacion_deg=118.0)
    pun = F.nuevo(F.vacio(), None, "punto")
    pun.update(nombre="Chimenea", ubicacion={"x": 500200.0, "y": 4500000.0}, altura_m=12.0)
    for foco, clase in ((sup, G.PanelSuperficie), (vol, G.PanelVolumen), (pun, G.PanelEstela)):
        v = ventana_focos.FichaVista(foco)
        v.resize(460, 900)
        assert isinstance(v.visor, clase) and v.visor.maximumHeight() == v.ALTO_VISOR and not v.grab().isNull()
        assert v.area_datos.widget().isAncestorOf(v.findChildren(type(v.lbl_avisos))[0])          # las características, arriba, con su barra
        v.deleteLater()
    cifras = {q: c for _, c, q in ventana_focos.FichaVista(sup).cifras()}
    assert cifras["clase"] == "Balsa o piscina" and cifras["altura de emisión"] == "a ras de suelo" and cifras["emisión con el viento"] == "Constante"
    cifras = {q: c for _, c, q in ventana_focos.FichaVista(vol).cifras()}
    assert cifras["pila o hilera"] == "Hilera" and cifras["altura de emisión"] == "1,25 m" and cifras["rumbo del largo"] == "118°"
    assert cifras["volúmenes en el modelo"] == "7" and cifras["emisión con el viento"].startswith("×") and "piel que emite" in cifras


@con_qt
def test_el_3d_de_todos_los_focos_bajo_la_lista(app):
    # usuario, 2026-11-08: «debajo de la lista de focos, el visor 3D con todos los focos ya sería increíble»
    import math
    from PySide6 import QtCore, QtGui, QtWidgets
    from teodors.gui import tema
    from teodors.gui.focos_graficos import VisorFocos3D
    from teodors.operacion import focos as F
    tema.aplicar(app)
    x0, y0 = 500000.0, 4500000.0
    tanque = {"id": "E05", "nombre": "Depósito 4", "origen": "lidar", "altura_m": 6.2,
              "poligono": [[x0 + 60 + 8 * math.cos(k / 12 * 2 * math.pi), y0 + 8 * math.sin(k / 12 * 2 * math.pi)] for k in range(12)]}
    nave = {"id": "E01", "nombre": "Nave", "origen": "lidar", "altura_m": 9.0, "poligono": [[x0 - 40, y0], [x0 - 20, y0], [x0 - 20, y0 + 15], [x0 - 40, y0 + 15]]}
    balsa = dict(F.nuevo(F.vacio(), None, "superficie"), id="F01", nombre="Balsa",
                 ubicacion={"poligono": [[x0, y0 - 40], [x0 + 30, y0 - 40], [x0 + 30, y0 - 20], [x0, y0 - 20]]})
    boca = dict(F.nuevo(F.vacio(), None, "superficie"), id="F02", nombre="Tanque")
    boca["superficie"]["clase"] = "tanque"
    F.poner_sobre(boca, tanque)
    bio = dict(F.nuevo(F.vacio(), None, "superficie"), id="F03", nombre="Biofiltro", altura_m=1.5,
               ubicacion={"poligono": [[x0, y0 + 30], [x0 + 20, y0 + 30], [x0 + 20, y0 + 40], [x0, y0 + 40]]})
    bio["superficie"]["clase"] = "biofiltro"
    hilera = dict(F.nuevo(F.vacio(), None, "volumen"), id="F04", nombre="Hilera", ubicacion={"x": x0 + 20, "y": y0 + 70})
    hilera["dimensiones"].update(largo_m=40.0, ancho_m=6.0, alto_m=2.5, orientacion_deg=118.0)
    chimenea = dict(F.nuevo(F.vacio(), None, "punto"), id="F05", nombre="Chimenea", ubicacion={"x": x0 - 10, "y": y0 + 10}, altura_m=12.0)
    v = VisorFocos3D()
    v.resize(300, 280)
    v.poner([balsa, boca, bio, hilera, chimenea], [tanque, nave], "F04")
    assert [f["id"] for f in v.focos()] == ["F01", "F02", "F03", "F04", "F05"] and v.elegido() == "F04"
    assert [e["id"] for e in v._ed] == ["E01"]                                    # el depósito es el cuerpo del tanque: no va aparte
    assert not v.grab().isNull() and len(v._siluetas) == 5
    pulsados = []
    v.pulsado.connect(pulsados.append)
    sil = next(s for s, f in v._siluetas if f["id"] == "F01")
    c = sil.boundingRect().center()
    B, M, N = QtCore.Qt.MouseButton, QtCore.QEvent.Type, QtCore.Qt.KeyboardModifier.NoModifier
    for tipo, pulsado in ((M.MouseButtonPress, B.LeftButton), (M.MouseButtonRelease, B.NoButton)):
        QtWidgets.QApplication.sendEvent(v, QtGui.QMouseEvent(tipo, c, v.mapToGlobal(c), B.LeftButton, pulsado, N))
    assert v.foco_en(c)["id"] == "F01" and pulsados == ["F01"] and v.elegido() == "F01"
    v.elegir("F05")
    assert v.elegido() == "F05" and not v.grab().isNull()


@con_qt
def test_la_semana_de_la_operacion_como_outlook(app):
    # usuario, 2026-11-09: «un calendario tipo Outlook con las emisiones de ese foco y las del resto»: la operación del foco como citas (las
    # horas seguidas con el mismo %), apagado sin nada; a la derecha de cada día, toda la planta en la escala del calendario
    import datetime as dt
    from PySide6 import QtCore, QtGui, QtWidgets
    from teodors.gui import tema
    from teodors.gui.focos_graficos import COLORES, SemanaEmision, color_emision
    S = SemanaEmision()
    S.resize(840, 560)
    lunes = dt.date(2026, 11, 9)
    dias = [lunes + dt.timedelta(days=k) for k in range(7)]
    horario = [0.2] * 8 + [1.0] * 8 + [0.2] * 8
    factores = [horario] * 6 + [[0.0] * 24]
    foco = [[100.0 * f for f in fs] for fs in factores]
    planta = [[300.0 + v for v in fs] for fs in foco]
    S.poner(dias, foco, planta, factores, "Hilera", "volumen", 400.0, "ou_E/s", [dias[2]])
    assert S.bloques(0) == [(0, 8, 0.2), (8, 16, 1.0), (16, 24, 0.2)] and S.bloques(6) == []
    img = S.grab().toImage()
    k = img.devicePixelRatio()
    w, hh, y0 = S._geo()

    def color(dia, hora, parte):                                    # parte: de 0 a 1 a lo ancho del día
        x = S.IZQ + dia * (w + S.HUECO) + parte * w
        return img.pixelColor(QtCore.QPoint(int(x * k), int((y0 + (hora + 0.5) * hh) * k)))

    cita, apagado = color(0, 12, 0.3), color(6, 12, 0.3)             # el lunes a las 12, al 100 %; el domingo, nada
    relleno = QtGui.QColor(COLORES["volumen"][0])
    assert abs(cita.red() - relleno.red()) <= 25 and abs(cita.blue() - relleno.blue()) <= 25
    assert abs(apagado.lightness() - QtGui.QColor(tema.c("elevada")).lightness()) <= 6
    # toda la planta, en la escala del calendario: a las 12 del lunes, al 100 % (400 de 400)
    tope = color_emision("escala_olor", 1.0)
    pix = color(0, 12, 0.93)
    assert max(abs(pix.red() - tope.red()), abs(pix.green() - tope.green()), abs(pix.blue() - tope.blue())) <= 40
    # un clic en un día lo elige
    pulsados = []
    S.dia_pulsado.connect(lambda iso, _m: pulsados.append(iso))
    M, B, N = QtCore.QEvent.Type, QtCore.Qt.MouseButton, QtCore.Qt.KeyboardModifier.NoModifier
    c = QtCore.QPointF(S.IZQ + 4 * (w + S.HUECO) + w / 2, y0 + 10 * hh)
    QtWidgets.QApplication.sendEvent(S, QtGui.QMouseEvent(M.MouseButtonRelease, c, S.mapToGlobal(c), B.LeftButton, B.NoButton, N))
    assert pulsados == ["2026-11-13"]
