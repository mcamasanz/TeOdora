# ¿Cambiar de estilo en caliente deja lo mismo que arrancar con ese estilo? Pixel a pixel en Qt y color a color en el mapa.
#   prueba_estilos.py fresco <estilo>   arranca con ese estilo y guarda capturas y colores
#   prueba_estilos.py vivo              arranca en oscuro, recorre los estilos en caliente y mide
#   prueba_estilos.py comparar          compara y además mide el contraste de cada estilo
import json, os, shutil, sys, time
from pathlib import Path
AQUI = Path(__file__).resolve().parent
SALIDA = AQUI / "estilos"
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
ESTILOS = ("claro", "noche", "contraste", "oscuro")
modo = sys.argv[1]


def lumin(h):
    r, g, b = (int(h[i:i + 2], 16) / 255 for i in (1, 3, 5))
    f = lambda x: x / 12.92 if x <= 0.03928 else ((x + 0.055) / 1.055) ** 2.4
    return 0.2126 * f(r) + 0.7152 * f(g) + 0.0722 * f(b)


def contraste(a, b):
    la, lb = sorted((lumin(a), lumin(b)), reverse=True)
    return (la + 0.05) / (lb + 0.05)


if modo == "comparar":
    from PIL import Image, ImageChops
    sys.path[:0] = [str(CARGADOR)]
    from teodors.gui import tema
    malos = 0
    for x in ESTILOS:
        a, b = SALIDA / f"fresco_{x}", SALIDA / f"vivo_{x}"
        for f in sorted(a.glob("*.png")):
            ia, ib = Image.open(f).convert("RGB"), Image.open(b / f.name).convert("RGB")
            if ia.size != ib.size:
                print(f"MAL {x} {f.name}: tamaños {ia.size} y {ib.size}")
                malos += 1
                continue
            d = ImageChops.difference(ia, ib)
            caja = d.getbbox()
            n = sum(1 for p in d.getdata() if p != (0, 0, 0)) if caja else 0
            if n:
                print(f"MAL {x} {f.name}: {n} píxeles distintos en {caja}")
                d.point(lambda v: min(255, v * 6)).save(SALIDA / f"dif_{x}_{f.name}")
                malos += 1
            else:
                print(f"OK  {x} {f.name}")
        for nombre in ("mapa", "focos", "planes"):
            ca, cb = (json.loads((d / f"colores_{nombre}.json").read_text(encoding="utf-8")) for d in (a, b))
            sa, sb = set(ca), set(cb)
            if sa != sb:
                print(f"MAL {x} página {nombre}: {len(sa - sb)} solo al arrancar, {len(sb - sa)} solo en caliente")
                for s in sorted(sa - sb)[:6]:
                    print("    arrancar:", s[:170])
                for s in sorted(sb - sa)[:6]:
                    print("    caliente:", s[:170])
                malos += 1
            else:
                print(f"OK  {x} página {nombre}: {len(sa)} combinaciones de color iguales")
    print("\nContraste (WCAG: 4,5 texto normal)")
    PARES = [("texto", "fondo", 4.5), ("texto", "superficie", 4.5), ("texto", "elevada", 4.5), ("texto", "hover", 4.5),
             ("tenue", "fondo", 4.5), ("tenue", "superficie", 4.5), ("tenue", "elevada", 4.5),
             ("sobre_acento", "acento", 4.5), ("acento_claro", "tinte", 4.5), ("aviso", "tinte_aviso", 4.5),
             ("fallo", "tinte_fallo", 4.5), ("aviso", "superficie", 4.5), ("apagado", "superficie", 2.5)]
    for x, t in tema.TEMAS.items():
        col = t["colores"]
        peor = min(((contraste(col[a], col[b]), a, b, m) for a, b, m in PARES), key=lambda v: v[0] / v[3])
        fallan = [(a, b, round(contraste(col[a], col[b]), 2)) for a, b, m in PARES if contraste(col[a], col[b]) < m]
        print(("OK  " if not fallan else "MAL ") + f"{x}: peor {peor[1]}/{peor[2]} = {peor[0]:.2f}" + (f" · fallan {fallan}" if fallan else ""))
        malos += len(fallan)
    print("\nTiempos:", (SALIDA / "tiempos.txt").read_text(encoding="utf-8"))
    print("RESULTADO:", "todo igual" if not malos else f"{malos} diferencias")
    sys.exit(0)

# ── los dos modos con la app: los ajustes del usuario, aparte ───────────────────────────
INI = Path(os.environ["APPDATA"]) / "CIRCE" / "ENCE_Galera.ini"
COPIA = AQUI / "ENCE_Galera.ini.estilos"
tenia = INI.exists()
if tenia:
    shutil.copy2(INI, COPIA)
from PySide6 import QtCore, QtWidgets, QtWebEngineWidgets  # noqa
QtCore.QCoreApplication.setAttribute(QtCore.Qt.ApplicationAttribute.AA_ShareOpenGLContexts)
app = QtWidgets.QApplication(sys.argv[:1])
from teodors.comun import registro
from teodors.gui import tema
aj = tema.ajustes()
aj.remove("ventana")
aj.remove("focos")
aj.remove("planes")
aj.setValue("apariencia/estilo", sys.argv[2] if modo == "fresco" else "oscuro")
aj.setValue("apariencia/viento_muestra", False)            # todo quieto para comparar píxeles
aj.sync()
tema.aplicar(app)
from teodors.gui.ventana import VentanaPrincipal
_planta.asegurar_carpetas(); registro.configurar(_planta.DIR_LOGS, _planta.REGISTRO)
v = VentanaPrincipal()
FLAGS = ("WindowStaysOnTopHint", "WindowTransparentForInput", "WindowDoesNotAcceptFocus")


def sin_foco(w):
    for b in FLAGS:
        w.setWindowFlag(getattr(QtCore.Qt.WindowType, b), True)


sin_foco(v)
v.resize(1430, 790)
v.show()
v.move(0, 0)


def fin(codigo=0):
    if tenia:
        shutil.copy2(COPIA, INI)
    else:
        INI.unlink(missing_ok=True)
    os._exit(codigo)


def espera(s):
    t = time.time()
    app.processEvents()
    while time.time() - t < s:
        time.sleep(0.01)
        app.processEvents()


def jsen(vista, c):
    r = {}
    vista.page().runJavaScript(c, 0, lambda x: r.setdefault("v", x))
    t = time.time()
    while "v" not in r and time.time() - t < 10:
        app.processEvents()
        time.sleep(0.005)
    return r.get("v")


COLORES = """(function(){var r={},P=['color','backgroundColor','borderTopColor','fill','stroke','boxShadow'];
  document.querySelectorAll('body,body *').forEach(function(e){
    if(e.tagName==='IMG'||e.tagName==='CANVAS'||e.closest('.leaflet-tile-pane'))return;
    var s=getComputedStyle(e),k=[];P.forEach(function(q){k.push(s[q]);});
    var a=(typeof e.className==='string'?e.className:(e.className&&e.className.baseVal)||'').split(' ').slice(0,2).join('.');
    r[e.tagName+'.'+a+' '+k.join('|')]=1;
    ['::before','::after'].forEach(function(z){var y=getComputedStyle(e,z);if(y.content&&y.content!=='none'){r[e.tagName+'.'+a+z+' '+y.backgroundColor+'|'+y.borderTopColor]=1;}});
  });return JSON.stringify(Object.keys(r));})()"""


t = time.time()
while time.time() - t < 40 and not v.mapa.esta_listo():
    espera(0.2)
p = v.panel
v._reloj_app.stop()
v._lbl_hora.setText("12:00")
v._lbl_fecha.setText("sáb 31 de octubre")
v._ver_focos()
vf = v._ventana_focos
sin_foco(vf)
vf.resize(1400, 860)
vf.show()
v._ver_planes()
vp = v._ventana_planes
sin_foco(vp)
vp.resize(1400, 860)
vp.show()
v._ver_ajustes()
va = v._ventana_ajustes
sin_foco(va)
va.show()
for s in (va.pleg_estilo, va.pleg_viento, va.pleg_concentraciones, p.pleg_elevacion, p.pleg_usos, p.pleg_edificios):
    s.cabecera.setChecked(True)                        # que se compare también lo que va dentro
t = time.time()
while time.time() - t < 25 and not (vf.mapa._listo and vp.mapa._listo):
    espera(0.2)
espera(2)
p.reproductor.setVisible(True)
p.btn_play.setEnabled(True)


def guardar(carpeta):
    d = SALIDA / carpeta
    d.mkdir(exist_ok=True)
    for clave in ("inicio", "planta", "focos", "meteo", "simulacion"):
        p.ir_a(clave)
        espera(0.1)
        p.grab().save(str(d / f"panel_{clave}.png"))
    v.menuWidget().grab().save(str(d / "barra.png"))
    p.reproductor.grab().save(str(d / "reproductor.png"))
    v.menu_app.grab().save(str(d / "menu.png"))
    p.fecha_viento.calendarWidget().grab().save(str(d / "calendario.png"))
    vf.lista.grab().save(str(d / "focos_lista.png"))
    vf.area_ficha.grab().save(str(d / "focos_ficha.png"))
    vp.lista.grab().save(str(d / "planes_lista.png"))
    vp.divisor.widget(2).grab().save(str(d / "planes_derecha.png"))
    va.findChild(QtWidgets.QScrollArea).grab().save(str(d / "configuracion.png"))     # sin el mapa: se mueve
    for nombre, vista in (("mapa", v.mapa), ("focos", vf.mapa), ("planes", vp.mapa)):
        (d / f"colores_{nombre}.json").write_text(jsen(vista, COLORES) or "[]", encoding="utf-8")


if modo == "fresco":
    espera(1)
    guardar(f"fresco_{sys.argv[2]}")
    print("hecho", sys.argv[2], file=out, flush=True)
    fin()

origen = jsen(v.mapa, "performance.timeOrigin")
tiempos = []
for x in ESTILOS:
    t0 = time.perf_counter()
    va.tarjetas[x].click()                     # como el usuario: pulsando su tarjeta
    dt = time.perf_counter() - t0
    app.processEvents()
    dt2 = time.perf_counter() - t0
    # hasta que el mapa ya tiene los colores nuevos
    while jsen(v.mapa, "getComputedStyle(document.documentElement).getPropertyValue('--fondo')").strip() != tema.c("fondo"):
        espera(0.005)
    dt3 = time.perf_counter() - t0
    tiempos.append(f"{x}: Qt {dt * 1000:.0f} ms, con repintado {dt2 * 1000:.0f} ms, mapa al día {dt3 * 1000:.0f} ms")
    print(tiempos[-1], "| guardado:", tema.ajustes().value("apariencia/estilo"), file=out, flush=True)
    espera(1)
    guardar(f"vivo_{x}")
(SALIDA / "tiempos.txt").write_text("\n".join(tiempos), encoding="utf-8")
print("Sin recargar la página del mapa:", jsen(v.mapa, "performance.timeOrigin") == origen, file=out, flush=True)
fin()
