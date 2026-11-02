# Panel según la modalidad y tabla de resultados, con clics simulados: qué se ve en cada opción de Meteorología, el orden de la tabla,
# las columnas de cada magnitud y los valores que pasan de su límite.
import os, shutil, sys, time
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
SALIDA = AQUI / "tabla"
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
COPIA = AQUI / "ENCE_Galera.ini.tabla"
tenia = INI.exists()
if tenia:
    shutil.copy2(INI, COPIA)
from PySide6 import QtCore, QtGui, QtTest, QtWidgets, QtWebEngineWidgets  # noqa
QtCore.QCoreApplication.setAttribute(QtCore.Qt.ApplicationAttribute.AA_ShareOpenGLContexts)
app = QtWidgets.QApplication(sys.argv[:1])
from teodors.operacion import normativa as N
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


v = VentanaPrincipal()
for b in ("WindowStaysOnTopHint", "WindowTransparentForInput", "WindowDoesNotAcceptFocus"):
    v.setWindowFlag(getattr(QtCore.Qt.WindowType, b), True)
v.resize(1430, 900)
v.show()
v.move(0, 0)
t = time.time()
while time.time() - t < 40 and not v.mapa.esta_listo():
    espera(0.3)
p = v.panel

# ── Qué se ve en cada modalidad ─────────────────────────────────────────────────────────
p.ir_a("simulacion")
espera(0.3)
ok("Ninguno: nada que simular", not p.sec_anios.isVisible() and not p.sec_periodo.isVisible())
ok("Hay 6 páginas, con 3D tras Simular", [c for c, *_ in p.PAGINAS][-2:] == ["simulacion", "visor3d"])
p.set_horizonte_meteo("reanalisis")
espera(0.5)
ok("Reanálisis: va a su página y enseña el viento de un día", p.caja_viento.isVisible() and not p.caja_periodo.isVisible())
p.ir_a("simulacion")
espera(0.3)
ok("Reanálisis: 5 años y un día", p.sec_anios.isVisible() and p.sec_periodo.isVisible() and p.fila_dia.isVisible())
ok("Reanálisis: los botones", p.b_simular.text() == "Simular 5 años" and p.b_simular_periodo.text() == "Simular día" and p.sec_periodo.titulo.text() == "Un día")
ok("Reanálisis: calendario limitado a los días con respuestas", p.fecha_dia.date().toString("yyyy-MM-dd") in periodos.dias_reanalisis())
ok("Reanálisis: se puede simular", p.b_simular.isEnabled() and p.b_simular_periodo.isEnabled())
p.grab().save(str(SALIDA / "simular_reanalisis.png"))
p.set_horizonte_meteo("queja")
espera(0.5)
ok("Episodio: su bloque, y va a Meteorología", p.caja_periodo.isVisible() and not p.caja_viento.isVisible() and p.fecha_periodo.isVisible())
ok("Episodio: 1-3 días", [p.cmb_dias.itemData(i) for i in range(p.cmb_dias.count())] == [1, 2, 3] and p.cmb_dias.currentData() == 1)
p.fecha_periodo.setDate(QtCore.QDate(2024, 3, 3))
espera(0.2)
ok("Episodio sin preparar", "sin preparar" in p.lbl_periodo.text() and p.b_preparar.text() == "Preparar" and not p.b_ver_periodo.isEnabled(), p.lbl_periodo.text())
p.grab().save(str(SALIDA / "meteo_queja.png"))
p.ir_a("simulacion")
espera(0.3)
ok("Episodio: sin los 5 años ni el calendario", not p.sec_anios.isVisible() and p.sec_periodo.isVisible() and not p.fila_dia.isVisible())
ok("Episodio: su botón", p.b_simular_periodo.text() == "Simular episodio" and p.sec_periodo.titulo.text() == "Episodio")
ok("Episodio sin preparar: no se puede simular", not p.b_simular_periodo.isEnabled() and "Falta" in p.lbl_sim_meteo.text(), p.lbl_sim_meteo.text())
p.grab().save(str(SALIDA / "simular_queja.png"))
p.set_horizonte_meteo("prediccion")
espera(0.5)
ok("Predicción: 1-5 días, 3 por defecto, sin fecha", [p.cmb_dias.itemData(i) for i in range(p.cmb_dias.count())] == [1, 2, 3, 4, 5] and p.cmb_dias.currentData() == 3 and not p.fecha_periodo.isVisible())
ok("Predicción: dice qué ejecución es", "Ejecución de las 00 UTC" in p.lbl_periodo.text(), p.lbl_periodo.text())
p.grab().save(str(SALIDA / "meteo_prediccion.png"))
p.ir_a("simulacion")
espera(0.3)
ok("Predicción: su botón", p.b_simular_periodo.text() == "Simular predicción" and p.sec_periodo.titulo.text() == "Predicción" and not p.sec_anios.isVisible())
ok("Tiempo real sigue desactivado", not p._radios_meteo["presente"].isEnabled())
p.set_horizonte_meteo("reanalisis")
espera(0.5)
p.ir_a("simulacion")
espera(0.3)

# ── Tabla: orden ────────────────────────────────────────────────────────────────────────
filas = [{"nombre": n, "km": k, "media": a, "maximo": b, "p98": c, "hora_max": h} for n, k, a, b, c, h in (
    ("Peor vivienda (< 2 km)", 0.2, 2.5, 90.0, 11.0, 3), ("La Galera", 1.4, 0.004, 12.0, 0.0, 1), ("Santa Bàrbara", 3.0, 10.0, 3.0, 25.0, 0),
    ("Godall", 3.9, 0.0, 0.0, 0.0, -1), ("Freginals", 4.3, 0.8, 100.0, 9.0, 2), ("Masdenverge", 6.0, 100.0, 7.0, 1.0, 4))]
base = {"unidad": "ou_E/m³", "maximos": {"maximo": 100.0}, "estimados": [], "fuera": [], "horas_txt": ["09:00", "10:00", "11:00", "12:00", "13:00"], "penacho": None}
m = dict(base, nombre="Olor", filas=filas, columnas=N.columnas("olor", "anios"))
filas_nox = [dict(f, norma_hora=f["maximo"] * 3, norma_anio=f["media"]) for f in filas]
nox = dict(base, nombre="NOₓ", unidad="µg/m³", filas=filas_nox, columnas=N.columnas("NOx", "anios"))
r = {"nombre": "x", "orden": ["olor", "H2S", "NOx"], "periodo": None, "magnitudes": {"olor": m, "H2S": dict(m, nombre="H₂S", unidad="µg/m³", filas=list(reversed(filas))), "NOx": nox}}
p.set_resultado(r, PC.cifra)
B = p.res_anios
T = B.tabla
cab = T.horizontalHeader()
espera(0.2)


def columna(k):
    return [T.item(i, k).text() for i in range(T.rowCount())]


def pulsa(k):
    QtTest.QTest.mouseClick(cab.viewport(), QtCore.Qt.MouseButton.LeftButton, pos=QtCore.QPoint(cab.sectionPosition(k) + 6, cab.height() // 2))
    app.processEvents()


ok("Sale ordenada por la media, de más a menos", columna(1) == ["100", "10", "2,5", "0,80", "< 0,01", "0"], columna(1))
ok("La indicación está en la media", cab.sortIndicatorSection() == 1 and cab.sortIndicatorOrder() == QtCore.Qt.SortOrder.DescendingOrder)
pulsa(2)
ok("Pulsar «Máx.»: de más a menos", columna(2) == ["100", "90", "12", "7,0", "3,0", "0"], columna(2))
pulsa(2)
ok("Otra vez: de menos a más", columna(2) == ["0", "3,0", "7,0", "12", "90", "100"], columna(2))
pulsa(3)
ok("Pulsar «P98»: de más a menos", columna(3) == ["25", "11", "9,0", "1,0", "0", "0"], columna(3))
pulsa(0)
ok("Pulsar «Lugar»: por nombre", columna(0) == sorted(f["nombre"] for f in filas), columna(0))
pulsa(2)
ok("Con otra magnitud se mantiene la columna elegida", True)
B.poner(r["magnitudes"]["H2S"], PC.cifra)
ok("Se mantiene", cab.sortIndicatorSection() == 2 and columna(2)[0] == "100", columna(2))
p.set_resultado(r, PC.cifra)
ok("Una simulación nueva vuelve a la media", cab.sortIndicatorSection() == 1 and columna(1)[0] == "100")

# ── Columnas según la magnitud ──────────────────────────────────────────────────────────
ok("Olor: Media, Máx., P98", [T.horizontalHeaderItem(i).text() for i in range(T.columnCount())][1:] == ["Media", "Máx.", "P98"])
ok("Olor: el botón dice P98", B.botones["norma"].text().endswith("P98") and B.botones["norma"].isVisibleTo(p))
B.poner(nox, PC.cifra)
espera(0.1)
cabeceras = [T.horizontalHeaderItem(i).text() for i in range(T.columnCount())]
ok("NOₓ: una columna por criterio de planta/normativa.json", cabeceras[1:] == ["Media", "Máx.", "1 h", "Año"], cabeceras)
ok("NOₓ: la cabecera dice qué es", "19.ª hora" in T.horizontalHeaderItem(3).toolTip() and "200" in T.horizontalHeaderItem(3).toolTip(), T.horizontalHeaderItem(3).toolTip())
ok("NOₓ: el botón dice norma", B.botones["norma"].text().endswith("norma"))
col = [c for c in range(T.rowCount()) if T.item(c, 0).text() == "Freginals"][0]
ok("Lo que pasa del límite, destacado", T.item(col, 3).font().bold() and T.item(col, 3).foreground().color().name().lower() == tema.c("aviso").lower(), T.item(col, 3).text())
col2 = [c for c in range(T.rowCount()) if T.item(c, 0).text() == "Godall"][0]
ok("Lo que no, sin destacar", not T.item(col2, 3).font().bold())
T.grab().save(str(SALIDA / "nox.png"))
tema.poner("claro")
espera(0.5)
ok("El aviso sigue al estilo", T.item([c for c in range(T.rowCount()) if T.item(c, 0).text() == "Freginals"][0], 3).foreground().color().name().lower() == tema.c("aviso").lower())
tema.poner("oscuro")
espera(0.3)
# Una magnitud con menos columnas que la que estaba ordenando
pulsa(4)
ok("Ordenada por la 4.ª columna", cab.sortIndicatorSection() == 4)
B.poner(m, PC.cifra)
ok("Si esa columna ya no existe, por la media", cab.sortIndicatorSection() == 1 and T.columnCount() == 4 and columna(1)[0] == "100")
p.grab().save(str(SALIDA / "panel.png"))

# ── Días: hora del máximo y horas por encima ────────────────────────────────────────────
filas_d = [dict(f, horas_sobre=3.0 if f["maximo"] > 50 else 0.0) for f in filas]
md = dict(base, nombre="NO₂", unidad="µg/m³", filas=filas_d, columnas=N.columnas("NO2", "dias"))
rd = {"nombre": "x", "orden": ["NO2"], "periodo": periodos.nuevo("queja", "2026-10-23", 3), "magnitudes": {"NO2": md}}
p.res_periodo.poner(md, PC.cifra)
p.res_periodo.setVisible(True)
Td = p.res_periodo.tabla
cabeceras = [Td.horizontalHeaderItem(i).text() for i in range(Td.columnCount())]
ok("Días: media, máximo, hora del máximo y horas por encima", cabeceras[1:] == ["Media", "Máx.", "Hora máx.", "H > 200"], cabeceras)
texto = {Td.item(i, 0).text(): (Td.item(i, 3).text(), Td.item(i, 4).text()) for i in range(Td.rowCount())}
ok("La hora se lee, y sin nada, una raya", texto["Santa Bàrbara"][0] == "09:00" and texto["Godall"][0] == "—", texto["Godall"])
ok("Las horas, enteras", texto["Freginals"][1] == "3" and texto["Godall"][1] == "0")
ok("Sin capa de norma, sin botón", not p.res_periodo.botones["norma"].isVisibleTo(p))
print("FALLOS:", fallos or "ninguno", file=out, flush=True)
if tenia:
    shutil.copy2(COPIA, INI)
os._exit(1 if fallos else 0)
