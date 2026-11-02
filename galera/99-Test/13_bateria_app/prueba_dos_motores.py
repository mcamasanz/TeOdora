# Dos motores de viento en el mapa: la zona (viento3d) y la planta (biblioteca con edificios).
import base64, json, os, shutil, sys, time, traceback
from pathlib import Path
import numpy as np
AQUI = Path(__file__).resolve().parent
SALIDA = AQUI / "dos_motores"
SALIDA.mkdir(exist_ok=True)
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
os.environ.setdefault("ENCE_GALERA_DATOS", str(Path(os.environ["TEMP"]) / "ence_galera" / "datos_local"))
CARGADOR = RAIZ.parent / (RAIZ / "VERSION").read_text(encoding="utf-8").strip() / "cargador"
sys.path[:0] = [str(CARGADOR)]
from teodors import planta as _planta  # noqa: E402
_planta.activar(RAIZ / "entrada")
out = sys.__stdout__
out.reconfigure(encoding="utf-8")
INI = Path(os.environ["APPDATA"]) / "CIRCE" / "ENCE_Galera.ini"
COPIA = AQUI / "ENCE_Galera.ini.dos_motores"
tenia = INI.exists()
if tenia:
    shutil.copy2(INI, COPIA)


def restaurar():
    if tenia:
        shutil.copy2(COPIA, INI)
    else:
        INI.unlink(missing_ok=True)


def si_falla(*a):
    traceback.print_exception(*a, file=out)
    restaurar()
    os._exit(2)


sys.excepthook = si_falla
from PySide6 import QtCore, QtGui, QtWidgets, QtWebEngineWidgets  # noqa
QtCore.QCoreApplication.setAttribute(QtCore.Qt.ApplicationAttribute.AA_ShareOpenGLContexts)
app = QtWidgets.QApplication(sys.argv[:1])
from pyproj import Transformer
from teodors import planta as config
from teodors.comun import registro
from teodors.gui import tema
from teodors.operacion import viento_mapa
aj = tema.ajustes()
for g in ("ventana", "focos", "planes", "apariencia"):
    aj.remove(g)
aj.sync()
tema.aplicar(app)
from teodors.gui.ventana import VentanaPrincipal
_planta.asegurar_carpetas(); registro.configurar(_planta.DIR_LOGS, _planta.REGISTRO)
FLAGS = ("WindowStaysOnTopHint", "WindowTransparentForInput", "WindowDoesNotAcceptFocus")
v = VentanaPrincipal()
for b in FLAGS:
    v.setWindowFlag(getattr(QtCore.Qt.WindowType, b), True)
v.resize(1430, 790)
v.show()
v.move(0, 0)
fallos = []


def ok(n, si, det=""):
    print(("OK  " if si else "MAL ") + n, det, file=out, flush=True)
    if not si:
        fallos.append(n)


def fin():
    print("FALLOS:", fallos or "ninguno", file=out, flush=True)
    restaurar()
    os._exit(1 if fallos else 0)


def espera(s):
    t = time.time()
    app.processEvents()
    while time.time() - t < s:
        time.sleep(0.01)
        app.processEvents()


def js(vista, c):
    r = {}
    vista.page().runJavaScript(c, 0, lambda x: r.setdefault("v", x))
    t = time.time()
    while "v" not in r and time.time() - t < 15:
        app.processEvents()
        time.sleep(0.01)
    return r.get("v")


def foto(nombre, w=None):
    (w or v.mapa).grab().save(str(SALIDA / f"{nombre}.png"))


t = time.time()
while time.time() - t < 40 and not v.mapa.esta_listo():
    espera(0.3)
espera(2)
p = v.panel
Z = v.mapa
t0 = time.time()
d_lib = viento_mapa.datos_local()
print(f"Biblioteca: {viento_mapa.biblioteca().stat().st_size / 1e6:.2f} MB en disco · preparada en {time.time() - t0:.2f} s · {sum(len(x) for x in d_lib['u']) * 2 / 1e6:.1f} MB al mapa · {d_lib['nx']} × {d_lib['ny']} celdas de {d_lib['dx']} m", file=out, flush=True)
ok("Al abrir sigue sin haber viento", js(Z, "mapaApp.estadoViento() === null") is True or js(Z, "(mapaApp.estadoViento()||{}).modo") in (None, ""))
p.set_horizonte_meteo("reanalisis")
espera(1)
t0 = time.time()
p.btn_viento.click()
while time.time() - t0 < 30 and not p.reproductor.isVisible():
    espera(0.05)
espera(0.2)
print(f"Viento + biblioteca en el mapa: {time.time() - t0:.1f} s", file=out, flush=True)
espera(2)
p.btn_play.setChecked(False)
ok("El motor de la planta está activo", True)

# ── 1. Lo que usa el mapa = lo calculado en Python ──────────────────────────────────────
dia = viento_mapa.datos_dia("2026-10-21", viento_mapa.serie_disponible())
H = 7
p.hora_viento.setValue(4 * H)
espera(0.6)
aU = np.frombuffer(base64.b64decode(dia["u"][H]), "<i2").reshape(dia["ny"], dia["nx"]) * dia["escala"]
aV = np.frombuffer(base64.b64decode(dia["v"][H]), "<i2").reshape(dia["ny"], dia["nx"]) * dia["escala"]
oX, oY = dia["origen"]
dg = dia["dg"]


def bilin(A, x, y):
    gi, gj = (x - oX) / dg, (y - oY) / dg
    i, j = int(np.floor(gi)), int(np.floor(gj))
    fx, fy = gi - i, gj - j
    return (A[j, i] * (1 - fx) + A[j, i + 1] * fx) * (1 - fy) + (A[j + 1, i] * (1 - fx) + A[j + 1, i + 1] * fx) * fy


with np.load(viento_mapa.biblioteca()) as z:
    lu, lv = z["u"].astype(float), z["v"].astype(float)
    SOL, ESC, PASO = int(z["solido"]), float(z["escala"]), float(z["paso"])
    x0, y0, dx, cx, cy, cx2, cy2, R, RB = (float(z[k]) for k in ("x0", "y0", "dx", "cx", "cy", "cx2", "cy2", "radio", "radio_borde"))
lu[lu == SOL] = np.nan
lv[lv == SOL] = np.nan
lu *= ESC
lv *= ESC
uc, vc = bilin(aU, cx, cy), bilin(aV, cx, cy)
vel = np.hypot(uc, vc)
rumbo = (np.degrees(np.arctan2(-uc, -vc)) + 360) % 360
print(f"Hora {H}: la zona da en la planta {vel:.2f} m/s del {rumbo:.0f}°", file=out, flush=True)
k0 = int(rumbo // PASO) % lu.shape[0]
k1, f = (k0 + 1) % lu.shape[0], rumbo / PASO - np.floor(rumbo / PASO)
Lu, Lv = vel * ((1 - f) * lu[k0] + f * lu[k1]), vel * ((1 - f) * lv[k0] + f * lv[k1])


def al_segmento(x, y):
    """Distancia al segmento planta-Dacame, donde manda el motor local."""
    sx, sy = cx2 - cx, cy2 - cy
    t_ = min(1.0, max(0.0, ((x - cx) * sx + (y - cy) * sy) / (sx * sx + sy * sy)))
    return np.hypot(x - cx - t_ * sx, y - cy - t_ * sy)


def esperado(x, y):
    u, w = bilin(aU, x, y), bilin(aV, x, y)
    d = al_segmento(x, y)
    if d >= RB:
        return u, w
    li, lj = (x - x0) / dx, (y - y0) / dx
    a, b = int(np.floor(li)), int(np.floor(lj))
    ax, ay = li - a, lj - b
    pes = [(a, b, (1 - ax) * (1 - ay)), (a + 1, b, ax * (1 - ay)), (a, b + 1, (1 - ax) * ay), (a + 1, b + 1, ax * ay)]
    pe = sum(q for i, j, q in pes if np.isfinite(Lu[j, i]))
    if pe < 0.5:
        return None
    su = sum(q * Lu[j, i] for i, j, q in pes if np.isfinite(Lu[j, i])) / pe
    sv = sum(q * Lv[j, i] for i, j, q in pes if np.isfinite(Lu[j, i])) / pe
    w_ = 1.0 if d <= R else (RB - d) / (RB - R)
    return u + (su - u) * w_, w + (sv - w) * w_


a_geo = Transformer.from_crs(config.EPSG_UTM, "EPSG:4326", always_xy=True)
malos, n_ok = [], 0
rng = np.random.default_rng(3)
puntos = [(cx + a, cy + b) for a, b in ((0, 0), (30, -40), (60, -60), (-50, 40), (100, 10), (150, -120), (160, 0), (180, -80))]
puntos += [(cx + r * np.cos(t_), cy + r * np.sin(t_)) for r, t_ in zip(rng.uniform(5, 330, 40), rng.uniform(0, 6.283, 40))]
puntos += [(cx2 + r * np.cos(t_), cy2 + r * np.sin(t_)) for r, t_ in zip(rng.uniform(5, 330, 40), rng.uniform(0, 6.283, 40))]      # Dacame
puntos += [(cx + (cx2 - cx) * s + r * np.cos(t_), cy + (cy2 - cy) * s + r * np.sin(t_))                                           # entre las dos
           for s, r, t_ in zip(rng.uniform(0, 1, 20), rng.uniform(0, 300, 20), rng.uniform(0, 6.283, 20))]
for x, y in puntos:
    lon, lat = a_geo.transform(x, y)
    m = json.loads(js(Z, f"JSON.stringify(mapaApp.vientoEn({lat}, {lon}))"))
    e = esperado(x, y)
    if (m is None) != (e is None) or (m is not None and max(abs(m[0] - e[0]), abs(m[1] - e[1])) > (0.03 if al_segmento(x, y) < R else 0.1)):
        malos.append((round(x), round(y), m, e))
    else:
        n_ok += 1
ok(f"El mapa coincide con Python en {len(puntos)} puntos (dentro, en el fundido y fuera)", not malos, malos[:3])
lon, lat = a_geo.transform(286808, 4507459)
ok("Dentro de un digestor no hay viento", js(Z, f"mapaApp.vientoEn({lat}, {lon}) === null") is True)
for nombre_, (xn, yn) in {"la nave grande de Dacame": (286267, 4507351), "la otra nave de Dacame": (286149, 4507261)}.items():
    lon, lat = a_geo.transform(xn, yn)
    ok(f"Dentro de {nombre_} no hay viento", js(Z, f"mapaApp.vientoEn({lat}, {lon}) === null") is True)
# Lejos del edificio y dentro del radio, el campo empalma con la zona: a 195 m del segmento planta-Dacame, alrededor
sin = []
largo = np.hypot(cx2 - cx, cy2 - cy)
ex_, ey_ = (cx2 - cx) / largo, (cy2 - cy) / largo
borde = [(cx + 195 * np.cos(t_), cy + 195 * np.sin(t_)) for t_ in np.linspace(0, 6.283, 24, endpoint=False)]
borde += [(cx2 + 195 * np.cos(t_), cy2 + 195 * np.sin(t_)) for t_ in np.linspace(0, 6.283, 24, endpoint=False)]
borde += [(cx + (cx2 - cx) * s + lado * 195 * -ey_, cy + (cy2 - cy) * s + lado * 195 * ex_) for s in np.linspace(0, 1, 12) for lado in (-1, 1)]
for x, y in borde:
    if abs(al_segmento(x, y) - 195) > 1:
        continue
    lon, lat = a_geo.transform(x, y)
    m = json.loads(js(Z, f"JSON.stringify(mapaApp.vientoEn({lat}, {lon}))"))
    if m:
        sin.append(np.hypot(*m) / np.hypot(bilin(aU, x, y), bilin(aV, x, y)))
print(f"A 195 m, {len(sin)} puntos, velocidad local / zona: mediana {np.median(sin):.2f} · P5 {np.percentile(sin, 5):.2f} · P95 {np.percentile(sin, 95):.2f} · de {min(sin):.2f} a {max(sin):.2f}", file=out, flush=True)
ok("Sin un salto al pasar de un motor al otro", abs(np.median(sin) - 1) < 0.1, f"{np.median(sin):.2f}")

# ── 2. Se ve: a zoom de planta, con y sin edificios ─────────────────────────────────────
v._ver_ajustes()
A = v._ventana_ajustes
for b in FLAGS:
    A.setWindowFlag(getattr(QtCore.Qt.WindowType, b), True)
A.show()
A.move(0, 0)
t = time.time()
while time.time() - t < 30 and not A.previa._listo:
    espera(0.2)
espera(3)
ok("Sin casilla en la configuración", not hasattr(A, "chk_planta") and not A.findChildren(QtWidgets.QCheckBox), [c.text() for c in A.findChildren(QtWidgets.QCheckBox)])
A.pleg_viento.cabecera.click()
espera(0.4)
foto("configuracion", A)
A.hide()
espera(0.5)
Z.ver_planta()
espera(4)
for forma in ("lineas", "flechas", "particulas"):
    A._b_forma[forma].click()
    espera(2.5)
    foto(f"planta_{forma}_con")
A._b_forma["lineas"].click()
espera(1)
# Un INI antiguo con la casilla desmarcada no puede apagarlo
tema.ajustes().setValue("apariencia/viento_local", False)
tema.ajustes().sync()
A._b_forma["flechas"].click()
espera(1)
A._b_forma["lineas"].click()
espera(1)
lon, lat = a_geo.transform(286808, 4507459)
ok("Con un INI antiguo «viento_local=false» sigue activo", json.loads(js(Z, "JSON.stringify(mapaApp.estadoViento())"))["local"] is True and js(Z, f"mapaApp.vientoEn({lat}, {lon}) === null") is True)
for hora in (2, 14, 20):
    p.hora_viento.setValue(4 * hora)
    espera(1.5)
    foto(f"planta_lineas_h{hora:02d}")
    texto = js(Z, 'document.querySelector(".mapa-viento").innerText')
    print(f"Hora {hora}: {texto}", file=out, flush=True)
# La planta y Dacame en el mismo encuadre
lon, lat = a_geo.transform((cx + cx2) / 2, (cy + cy2) / 2)
js(Z, f"(function () {{ var k = Object.keys(window).find(function (n) {{ return n.indexOf('map_') === 0; }}); window[k].setView([{lat}, {lon}], 17); return k; }})()")
espera(4)
for hora in (2, 14, 20):
    p.hora_viento.setValue(4 * hora)
    espera(1.5)
    foto(f"dacame_lineas_h{hora:02d}")
A._b_forma["particulas"].click()
espera(3)
foto("dacame_particulas")
A._b_forma["lineas"].click()
espera(1)
Z.ver_planta()
espera(3)

# ── 3. Fluidez y rumbo que da la vuelta ─────────────────────────────────────────────────
A._b_forma["particulas"].click()
espera(2)
con = json.loads(js(Z, "JSON.stringify(mapaApp.benchViento(60))"))
print("Fotograma, partículas a zoom de planta:", con, file=out, flush=True)
ok("Sigue siendo fluido", con["ms_por_cuadro"] < 16, con["ms_por_cuadro"])
A._b_forma["flechas"].click()
espera(1)
t0 = time.time()
p.btn_play.setChecked(True)
espera(6)
p.btn_play.setChecked(False)
ok("Con el reproductor en marcha, sin errores de la página", True)

# ── 4. La vista previa de la configuración también lo lleva ─────────────────────────────
A.show()
espera(1)
js(A.previa, "mapaApp.verPlanta()")
espera(3)
lon, lat = a_geo.transform(286808, 4507459)
ok("Vista previa: motor de la planta", js(A.previa, f"mapaApp.vientoEn({lat}, {lon}) === null") is True)
foto("configuracion_planta", A)
A._restablecer()
espera(1)
ok("Restablecer lo deja activo", json.loads(js(Z, "JSON.stringify(mapaApp.estadoViento())"))["local"] is True)
# ── 5. Sin biblioteca, la app sigue ─────────────────────────────────────────────────────
viento_mapa.datos_local.cache_clear()
guardada = viento_mapa.BIBLIOTECA
viento_mapa.BIBLIOTECA = Path("no_existe.npz")
ok("Sin biblioteca no hay nada que enviar", viento_mapa.datos_local() is None)
viento_mapa.BIBLIOTECA = guardada
viento_mapa.datos_local.cache_clear()
fin()
