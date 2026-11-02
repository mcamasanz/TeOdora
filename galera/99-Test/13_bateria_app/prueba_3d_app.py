# El recorrido entero en la app, con eventos simulados: reanálisis (5 años y un día), episodio y visor 3D en la zona central.
import json, os, shutil, sys, time
from pathlib import Path
import os as _os, sys as _sys
_aj = _os.environ.get("ENCE_AJUSTES_PRUEBA")
if not _aj:
    raise SystemExit("Falta ENCE_AJUSTES_PRUEBA: las pruebas no tocan el INI del usuario.")
_os.environ["APPDATA"] = _aj
from PySide6 import QtCore as _QC
_QC.QSettings.setPath(_QC.QSettings.Format.IniFormat, _QC.QSettings.Scope.UserScope, _aj)
RAIZ = Path(__file__).resolve().parents[2]
_salir = _os._exit
def _fin(c=0):
    g = _sys.modules.get("teodors")
    print("CODIGO:", getattr(g, "__file__", "sin cargar"), file=_sys.__stdout__, flush=True)
    _salir(c)
_os._exit = _fin
AQUI = Path(__file__).resolve().parent
SALIDA = AQUI / "modalidades"
SALIDA.mkdir(exist_ok=True)
os.environ.setdefault("ENCE_GALERA_DATOS", str(Path(os.environ["TEMP"]) / "ence_galera" / "datos_local"))
CARGADOR = RAIZ.parent / (RAIZ / "VERSION").read_text(encoding="utf-8").strip() / "cargador"
sys.path[:0] = [str(CARGADOR)]
from teodors import planta as _planta  # noqa: E402
_planta.activar(RAIZ / "entrada")
_planta.actual().DIR_PLANES = _planta.DATOS / "escenarios"      # los planes de las pruebas, con la copia de los datos: nunca en la carpeta de la planta
out = sys.__stdout__
out.reconfigure(encoding="utf-8")
INI = Path(os.environ["APPDATA"]) / "CIRCE" / "ENCE_Galera.ini"
COPIA = AQUI / "ENCE_Galera.ini.3d"
tenia = INI.exists()
if tenia:
    shutil.copy2(INI, COPIA)


def fin(codigo):
    if tenia:
        shutil.copy2(COPIA, INI)
    os._exit(codigo)


from PySide6 import QtCore, QtWidgets, QtWebEngineWidgets  # noqa
QtCore.QCoreApplication.setAttribute(QtCore.Qt.ApplicationAttribute.AA_ShareOpenGLContexts)
app = QtWidgets.QApplication(sys.argv[:1])
from teodors import planta as config
from teodors.gui import penacho_3d as P
from teodors.operacion import periodos
from teodors.operacion import simulacion as PC
from teodors.comun import registro
from teodors.gui import tema
aj = tema.ajustes()
for g in ("ventana", "focos", "planes", "apariencia"):
    aj.remove(g)
aj.sync()
tema.aplicar(app)
from teodors.gui.ventana import VentanaPrincipal
_planta.asegurar_carpetas(); registro.configurar(_planta.DIR_LOGS, _planta.REGISTRO)
fallos = []


def ok(n, si, det=""):
    print(("OK  " if si else "MAL ") + n, det, file=out, flush=True)
    if not si:
        fallos.append(n)


def espera(s):
    t = time.time()
    while time.time() - t < s:
        app.processEvents()
        time.sleep(0.01)


def js(vista, c, t_max=15):
    r = {}
    vista.page().runJavaScript(c, 0, lambda x: r.setdefault("v", x))
    t = time.time()
    while "v" not in r and time.time() - t < t_max:
        app.processEvents()
        time.sleep(0.01)
    return r.get("v")


def hasta(cond, t_max=600):
    t = time.time()
    while time.time() - t < t_max and not cond():
        espera(0.1)
    return time.time() - t


def foto(nombre, w=None):
    (w or v).grab().save(str(SALIDA / f"{nombre}.png"))


v = VentanaPrincipal()
for b in ("WindowStaysOnTopHint", "WindowTransparentForInput", "WindowDoesNotAcceptFocus"):
    v.setWindowFlag(getattr(QtCore.Qt.WindowType, b), True)
v.resize(1500, 950)
v.show()
v.move(0, 0)
hasta(lambda: v.mapa.esta_listo(), 40)
p = v.panel
Z = v.mapa
ESTADO = """JSON.stringify((function(){var n=0;document.querySelectorAll('img.leaflet-image-layer').forEach(function(){n++;});return {imagenes:n};})())"""

# ═══ Reanálisis: 5 años ═══
print("── Reanálisis", file=out, flush=True)
p.set_horizonte_meteo("reanalisis")
espera(1)
p.ir_a("simulacion")
espera(0.5)
t = time.time()
p.b_simular.click()
print(f"5 años: {hasta(lambda: v._trabajo_sim is None and v._resultados['anios'] is not None):.0f} s", file=out, flush=True)
r5 = v._resultados["anios"]
ok("5 años simulados, sin penacho", r5 is not None and r5["periodo"] is None and all(m["penacho"] is None for m in r5["magnitudes"].values()))
espera(1)
ok("Se ve su tabla, y no la del día", p.res_anios.isVisible() and not p.res_periodo.isVisible())
ok("A la vista en el mapa, la media", p._botones_capa["plan_media"].isChecked())
medias = [p.res_anios.tabla.item(i, 1).valor for i in range(p.res_anios.tabla.rowCount())]
ok("Tabla real ordenada por la media", medias == sorted(medias, reverse=True), medias[:4])
filas = [p.res_anios.tabla.item(i, 0).text() for i in range(p.res_anios.tabla.rowCount())]
ok("Dacame no está en la tabla, como se decidió", "Dacame" not in filas and "Peor vivienda (< 2 km)" in filas)
ok("El gas con límite trae su norma", "norma_hora" in [c["clave"] for c in r5["magnitudes"]["NOx"]["columnas"]])
print("  Magnitudes:", {k: (round(m["maximos"]["maximo"], 3)) for k, m in r5["magnitudes"].items()}, f"· {r5['segundos']} s", file=out, flush=True)
foto("rea_5anios")

# ═══ Reanálisis: un día ═══
p.b_simular_periodo.click()
print(f"Un día: {hasta(lambda: v._trabajo_sim is None and v._resultados['periodo'] is not None):.0f} s", file=out, flush=True)
rd = v._resultados["periodo"]
ok("El día, con su penacho", rd is not None and rd["periodo"]["dias"] == 1 and len(rd["magnitudes"]["olor"]["penacho"]["frames"]) == 24)
espera(2)
ok("Las dos tablas a la vista", p.res_anios.isVisible() and p.res_periodo.isVisible())
ok("Enciende el penacho", p._botones_capa["penacho"].isChecked() and not p._botones_capa["plan_media"].isChecked())
hasta(lambda: p.reproductor.isVisible(), 40)
espera(1)
ok("Con el reproductor en marcha", p.btn_play.isChecked())
p.btn_play.setChecked(False)
p.hora_viento.setValue(4 * 7)
espera(0.5)
ok("El reproductor da UTC y hora oficial", p.lbl_hora_viento.text() == "07:00 UTC · 09:00 oficial" and p.lbl_dia_repro.text() == "21/10/2026", p.lbl_hora_viento.text())
ok("El tooltip lleva los dos resultados", "5 años" in v._tabla_plan(*next(iter(v._valores["anios"]))) and "21/10/2026" in v._tabla_plan(*next(iter(v._valores["anios"]))))
foto("rea_dia")
i = p.cmb_magnitud.findData("NOx")
p.cmb_magnitud.setCurrentIndex(i)
espera(2)
ok("Otra magnitud cambia las dos tablas", p.res_anios.tabla.columnCount() == 5 and p.res_periodo.tabla.columnCount() == 5 and p._botones_capa["penacho"].isChecked(), (p.res_anios.tabla.columnCount(), p.res_periodo.tabla.columnCount()))
ok("NOx: en 5 años, sus normas; en el día, horas por encima", p.res_anios.tabla.horizontalHeaderItem(3).text() == "1 h" and p.res_periodo.tabla.horizontalHeaderItem(4).text() == "H > 200")
foto("rea_nox")
p.cmb_magnitud.setCurrentIndex(p.cmb_magnitud.findData("olor"))
espera(1)
# Simular otra vez lo mismo: se lee
t = time.time()
p.b_simular_periodo.click()
espera(0.2)
ok("Lo ya simulado se lee, sin calcular", v._trabajo_sim is None and v._resultados["periodo"] is not None, f"{time.time() - t:.2f} s")
espera(1)

# ═══ Visor 3D ═══
print("── Visor 3D", file=out, flush=True)
p.btn_play.setChecked(False)
p.ir_a("visor3d")
espera(0.5)
nombres = [p.cmb_3d.itemText(i) for i in range(p.cmb_3d.count())]
print("  Penachos:", nombres, file=out, flush=True)
ok("La lista trae el día simulado", any("Reanálisis · 21/10/2026 · Base" in n for n in nombres))
ok("Sigue el mapa hasta abrir uno", v._central.currentWidget() is v.mapa)
p.cmb_3d.setCurrentIndex(next(i for i, n in enumerate(nombres) if "21/10/2026 · Base" in n))
p.cmb_3d_mag.setCurrentIndex(p.cmb_3d_mag.findData("olor"))
espera(0.2)
ok("Lo guardado se abre", p.b_3d.text() == "Abrir", p.b_3d.text())
t = time.time()
p.b_3d.click()
espera(0.1)
ok("No lanza el motor", v._trabajo_3d is None)
ok("Zona central: el visor", v.vista3d is not None and v._central.currentWidget() is v.vista3d)
Vz = v.vista3d
print(f"  Visor listo: {hasta(lambda: js(Vz, '!!(window.visor && visor.estado)', 2) is True, 40) + time.time() - t - (time.time() - t):.1f} s", file=out, flush=True)
espera(1.5)
ok("WebGL", js(Vz, "!!window.visor && !visor.sin3d") is True)
ok("Título", js(Vz, "document.getElementById('titulo').textContent") == "Plan «Base» · Olor", js(Vz, "document.getElementById('titulo').textContent"))
ok("Niveles 1, 3 y 5", js(Vz, "Array.from(document.querySelectorAll('#niveles .nivel')).map(function(n){return n.textContent}).join('|')") == "1|3|5")
ok("Sin controles de hora propios: los lleva el reproductor", js(Vz, "!document.getElementById('h') && !document.getElementById('play')") is True)
ok("El reproductor manda: 24 horas", p.hora_viento.maximum() == 4 * 23, p.hora_viento.maximum())
p.hora_viento.setValue(4 * 7)
espera(0.6)
e = json.loads(js(Vz, "JSON.stringify(visor.estado())"))
ok("Hora del reproductor", e["hora"] == 7 and e["frac"] == 0 and e["mallas"] == 3, e)
foto("visor_h07")
p.hora_viento.setValue(4 * 7 + 2)
espera(0.5)
e = json.loads(js(Vz, "JSON.stringify(visor.estado())"))
ok("Entre dos horas, a medias, como el penacho 2D", e["hora"] == 7 and abs(e["frac"] - 0.5) < 1e-6, e)
op = js(Vz, "JSON.stringify(visor.mundo.children.filter(function(g){return g.visible&&g.type==='Group';}).map(function(g){return g.children.map(function(m){return Math.round(m.material.opacity*100)/100;});}))")
print("  Opacidades con las dos horas:", op, file=out, flush=True)
ok("Se ven las dos horas, cada una a la mitad", json.loads(op) == [[0.11, 0.18, 0.5], [0.11, 0.18, 0.5]], op)
foto("visor_fundido")
p.btn_play.setChecked(True)
h0 = p.hora_viento.value()
espera(2.5)
h1 = json.loads(js(Vz, "JSON.stringify(visor.estado())"))
ok("Con el reproductor en marcha, avanza", p.hora_viento.value() != h0 and h1["hora"] * 4 + round(h1["frac"] * 4) != h0, h1["etiqueta"])
p.btn_play.setChecked(False)
# controles propios
js(Vz, "var e=document.getElementById('e');e.value=1;e.dispatchEvent(new Event('input'))")
espera(0.3)
ok("Exageración ×1", js(Vz, "visor.mundo.scale.y") == 1)
js(Vz, "var e=document.getElementById('e');e.value=3;e.dispatchEvent(new Event('input'))")
js(Vz, "document.querySelector('#niveles input').click()")
espera(0.3)
ok("Quitar un nivel", js(Vz, "visor.mundo.children.filter(function(g){return g.visible&&g.type==='Group';})[0].children.filter(function(m){return m.visible;}).length") == 2)
js(Vz, "document.querySelector('#niveles input').click()")
# estilos
js(Vz, "window.__sigue = 1")
tema.poner("claro")
espera(0.8)
ok("Otro estilo, sin recargar", js(Vz, "window.__sigue") == 1 and js(Vz, "getComputedStyle(document.documentElement).getPropertyValue('--fondo').trim()") == tema.c("fondo"))
foto("visor_claro")
tema.poner("oscuro")
espera(0.5)
# volver al mapa
p.ir_a("simulacion")
espera(0.5)
ok("Al salir de la página, el mapa", v._central.currentWidget() is v.mapa)
ok("El reproductor vuelve a las horas del mapa", p.horas_reproductor()[0].startswith("2026-10-21") and len(p.horas_reproductor()) >= 24)
ok("El visor oculto no pinta", js(Vz, "document.visibilityState") == "hidden", js(Vz, "document.visibilityState"))
p.ir_a("visor3d")
espera(0.5)
ok("Al volver, el visor sigue abierto", v._central.currentWidget() is v.vista3d and js(Vz, "document.visibilityState") == "visible")

# Otra magnitud sin calcular: se lanza y se cancela
otra = next(m for m in next(x for x in p._penachos if x["ruta"] == p.cmb_3d.currentData())["magnitudes"] if not m["listo"])
p.cmb_3d_mag.setCurrentIndex(p.cmb_3d_mag.findData(otra["clave"]))
espera(0.2)
ok("Sin calcular, el botón lo dice", p.b_3d.text() == "Calcular", p.b_3d.text())
t0 = time.time()
p.b_3d.click()
espera(0.2)
ok("Lanza el cálculo", v._trabajo_3d is not None and p.b_3d.text() == "Cancelar" and not p.b_simular.isEnabled() and not p.cmb_3d.isEnabled())
trabajo = config.DIR_TRABAJO / "penacho_3d"
hasta(lambda: any(trabajo.glob("*.inp")), 60)
espera(5)
print("  Progreso:", p.barra_3d.value(), p.lbl_3d.text(), file=out, flush=True)
foto("visor_calculando")
ok("Hay motor en marcha", any(trabajo.glob("*.inp")))
t0 = time.time()
p.b_3d.click()
hasta(lambda: v._trabajo_3d is None, 40)
print(f"  Cancelado en {time.time() - t0:.1f} s", file=out, flush=True)
ok("Se cancela sin mensaje de error", v._trabajo_3d is None and p.b_3d.text() == "Calcular" and p.b_simular.isEnabled() and not p.lbl_3d.isVisibleTo(p), p.lbl_3d.text())
espera(1)
ok("No deja ficheros de trabajo", not trabajo.exists())
import psutil
vivos = [q for q in psutil.Process().children(recursive=True) if "teodors" in " ".join(q.cmdline())]
ok("No quedan procesos del motor", not vivos, [q.pid for q in vivos])

# ═══ Episodio ═══
print("── Episodio", file=out, flush=True)
ep = periodos.nuevo("queja", "2026-10-23", 3)
if not periodos.listo(ep):
    print("  ⚠ Episodio sin preparar: no se prueba", file=out, flush=True)
    fallos.append("episodio sin preparar")
else:
    p.ir_a("meteo")
    p.set_horizonte_meteo("queja")
    espera(1)
    ok("Al cambiar de modalidad se limpia lo simulado", not any(v._resultados.values()) and not p.res_anios.isVisibleTo(p))
    p.fecha_periodo.setDate(QtCore.QDate(2026, 10, 23))
    p.cmb_dias.setCurrentIndex(p.cmb_dias.findData(3))
    p.cmb_dias.activated.emit(p.cmb_dias.currentIndex())
    espera(0.3)
    ok("Episodio listo", "listo" in p.lbl_periodo.text() and p.b_ver_periodo.isEnabled() and p.b_preparar.text() == "Volver a preparar", p.lbl_periodo.text())
    foto("queja_meteo")
    p.ir_a("simulacion")
    espera(0.3)
    p.b_simular_periodo.click()
    print(f"Episodio: {hasta(lambda: v._trabajo_sim is None and v._resultados['periodo'] is not None):.0f} s", file=out, flush=True)
    re = v._resultados["periodo"]
    ok("72 horas de penacho", len(re["magnitudes"]["olor"]["penacho"]["frames"]) == 72)
    hasta(lambda: p.reproductor.isVisible() and p.hora_viento.maximum() > 95, 60)
    espera(1)
    ok("El reproductor cubre los 3 días, hasta las 23:00 del último", p.hora_viento.maximum() == 4 * 71, p.hora_viento.maximum())
    ok("Y el viento también", v._dia_viento == ("2026-10-23", 3), v._dia_viento)
    p.btn_play.setChecked(False)
    p.hora_viento.setValue(4 * 30)
    espera(0.8)
    ok("Hora y día del periodo", p.lbl_dia_repro.text() == "24/10/2026" and p.lbl_hora_viento.text().startswith("06:00 UTC"), (p.lbl_dia_repro.text(), p.lbl_hora_viento.text()))
    cab = [p.res_periodo.tabla.horizontalHeaderItem(i).text() for i in range(p.res_periodo.tabla.columnCount())]
    ok("Olor: media, máximo y hora del máximo", cab[1:] == ["Media", "Máx.", "Hora máx."], cab)
    print("  Filas:", [(p.res_periodo.tabla.item(i, 0).text(), p.res_periodo.tabla.item(i, 1).text(), p.res_periodo.tabla.item(i, 3).text()) for i in range(4)], file=out, flush=True)
    foto("queja_resultado")
    p.ir_a("visor3d")
    espera(0.5)
    ok("El 3D ya lo ofrece", any("Episodio · 23-25/10/2026" in p.cmb_3d.itemText(i) for i in range(p.cmb_3d.count())))
    p.ir_a("simulacion")
    espera(0.3)
    p.cmb_magnitud.setCurrentIndex(p.cmb_magnitud.findData("SO2"))
    espera(1.5)
    cab = [p.res_periodo.tabla.horizontalHeaderItem(i).text() for i in range(p.res_periodo.tabla.columnCount())]
    ok("SO₂ en el episodio: horas por encima y media diaria", cab[1:] == ["Media", "Máx.", "Hora máx.", "H > 350", "24 h"], cab)
    ok("Con capa de norma: el botón está", p.res_periodo.botones["norma"].isVisibleTo(p))
    foto("queja_so2")
    p.cmb_magnitud.setCurrentIndex(p.cmb_magnitud.findData("olor"))
    espera(1)

# Sin estaciones en todo el periodo
sin_est = periodos.nuevo("queja", "2026-10-25", 2)
if periodos.listo(sin_est):
    p.fecha_periodo.setDate(QtCore.QDate(2026, 10, 25))
    p.cmb_dias.setCurrentIndex(p.cmb_dias.findData(2))
    p.cmb_dias.activated.emit(p.cmb_dias.currentIndex())
    espera(0.3)
    p.ir_a("meteo")
    espera(0.3)
    ok("Lo dice si no ha podido usar las estaciones", "Estaciones hasta el 26/10" in p.lbl_periodo.text() and not periodos.fuente(sin_est)["con_estaciones"], p.lbl_periodo.text())
    foto("queja_sin_estaciones")

# ═══ Predicción ═══
print("── Predicción", file=out, flush=True)
import pandas as _pd
# La preparada en los datos de prueba: con la fecha real, la prueba depende de la hora a la que se lance
periodos.inicio_prediccion = lambda ahora=None: _pd.Timestamp("2026-11-01")
pr = periodos.nuevo("prediccion", periodos.inicio_prediccion(), 2)
if not periodos.listo(pr):
    print("  ⚠ Predicción sin preparar: no se prueba", file=out, flush=True)
    fallos.append("predicción sin preparar")
else:
    p.ir_a("meteo")
    p.set_horizonte_meteo("prediccion")
    espera(1)
    p.cmb_dias.setCurrentIndex(p.cmb_dias.findData(2))
    p.cmb_dias.activated.emit(p.cmb_dias.currentIndex())
    espera(0.3)
    ok("Predicción lista", "listo" in p.lbl_periodo.text() and "Ejecución" in p.lbl_periodo.text(), p.lbl_periodo.text())
    p.ir_a("simulacion")
    espera(0.3)
    p.b_simular_periodo.click()
    print(f"Predicción: {hasta(lambda: v._trabajo_sim is None and v._resultados['periodo'] is not None):.0f} s", file=out, flush=True)
    rp = v._resultados["periodo"]
    ok("48 horas de penacho", len(rp["magnitudes"]["olor"]["penacho"]["frames"]) == 48 and rp["periodo"]["modo"] == "prediccion")
    hasta(lambda: p.reproductor.isVisible() and v._dia_viento == (pr["ini"], 2), 60)
    espera(1)
    ok("Con su viento", v._dia_viento == (pr["ini"], 2), v._dia_viento)
    print("  Máximos:", {k: round(m["maximos"]["maximo"], 3) for k, m in rp["magnitudes"].items()}, file=out, flush=True)
    p.btn_play.setChecked(False)
    foto("prediccion_resultado")
    p.ir_a("visor3d")
    espera(0.5)
    ok("El 3D también la ofrece", any("Predicción" in p.cmb_3d.itemText(i) for i in range(p.cmb_3d.count())), [p.cmb_3d.itemText(i) for i in range(p.cmb_3d.count())])

# Cerrar con todo abierto
v.close()
espera(1)
print("FALLOS:", fallos or "ninguno", file=out, flush=True)
fin(1 if fallos else 0)
