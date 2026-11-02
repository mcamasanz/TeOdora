# -*- coding: utf-8 -*-
"""Vídeo de la herramienta: evolución del penacho de un día y pueblos alcanzados, con la media y
el máximo del día en cada uno (pedido del usuario, 2026-10-29).

Arranca la app DE VERDAD (con --dia), la conduce paso a paso y captura su ventana fotograma a
fotograma con QWidget.grab() (sale el mapa aunque haya otras ventanas delante: no hace falta
grabar la pantalla). Rótulos con PIL y MP4 (H.264) con ffmpeg por tubería.

    C:\\e2s\\python.exe 99-Test\\03_video_penacho\\grabar_video.py [--dia 2026-10-21] [--salida x.mp4]

Guion: presentación · penacho hora a hora (cuartos de hora, con el viento en partículas) · capa
de la media del día con las fichas de los pueblos más alcanzados · capa del máximo · resumen.
No toca la disposición guardada de la app (no se cierra con closeEvent).
"""
import argparse
import builtins
import os
import queue
import subprocess
import sys
import threading
import time
from pathlib import Path

ENCE = Path(__file__).resolve().parents[2]
CARGADOR = ENCE.parent / (ENCE / "VERSION").read_text(encoding="utf-8").strip() / "cargador"
sys.path[:0] = [str(CARGADOR)]
from teodors import planta as _planta  # noqa: E402
_planta.activar(ENCE / "entrada")
os.environ.setdefault("ENCE_GALERA_DATOS", os.path.expandvars(r"%TEMP%\ence_galera\datos_local"))
# Escala 100 % SOLO para la grabación: con el 125 % de Windows una ventana de 1600×900 no cabe en
# la pantalla (1536×816 útiles) y la captura cambiaba de tamaño a mitad del vídeo (medido).
os.environ["QT_ENABLE_HIGHDPI_SCALING"] = "0"

from PIL import Image, ImageDraw, ImageFont  # noqa: E402
from PySide6 import QtCore, QtGui, QtWidgets, QtWebEngineWidgets  # noqa: E402,F401

ANCHO, ALTO, FPS = 1600, 900, 25
POR_PASO = 4                       # fotogramas por cuarto de hora: 96 × 4 / 25 ≈ 15 s de día
FUENTE = r"C:\Windows\Fonts\segoeui.ttf"
FUENTE_N = r"C:\Windows\Fonts\segoeuib.ttf"
_print = builtins.print


def avisa(*a):                     # la app se queda con sys.stdout (su consola)
    _print(*a, file=sys.__stdout__, flush=True)


def num(x, cifras=2):
    """Número con coma y 2 cifras significativas (µg/m³ de la fuente de prueba)."""
    if x is None or x == 0:
        return "0"
    from math import floor, log10
    dec = max(0, cifras - 1 - int(floor(log10(abs(x)))))
    return f"{x:.{dec}f}".replace(".", ",")


# ── rótulos (PIL) ─────────────────────────────────────────────────────────────────────────
class Rotulos:
    def __init__(self, caja_mapa):
        self.x0, self.y0, self.w, self.h = caja_mapa
        self.f_t = ImageFont.truetype(FUENTE_N, 24)
        self.f_s = ImageFont.truetype(FUENTE, 16)
        self._cache = {}

    def banda(self, titulo, sub=""):
        """Banda oscura arriba, centrada en el mapa (entre el zoom y el selector de capas)."""
        clave = (titulo, sub)
        if clave not in self._cache:
            d0 = ImageDraw.Draw(Image.new("RGBA", (1, 1)))
            wt = d0.textlength(titulo, font=self.f_t)
            ws = d0.textlength(sub, font=self.f_s) if sub else 0
            w = int(max(wt, ws)) + 40
            h = 46 + (26 if sub else 0)
            im = Image.new("RGBA", (w, h), (0, 0, 0, 0))
            d = ImageDraw.Draw(im)
            d.rounded_rectangle([0, 0, w - 1, h - 1], 12, fill=(20, 30, 38, 215))
            d.text((20, 8), titulo, font=self.f_t, fill=(255, 255, 255, 255))
            if sub:
                d.text((20, 44), sub, font=self.f_s, fill=(214, 226, 234, 255))
            self._cache[clave] = im
        im = self._cache[clave]
        return im, (self.x0 + (self.w - im.width) // 2, self.y0 + 12)

    def tarjeta(self, titulo, sub, filas, pie):
        """Tarjeta centrada con la tabla de pueblos (nombre, municipio, media, máximo)."""
        f_c = ImageFont.truetype(FUENTE_N, 17)
        f_r = ImageFont.truetype(FUENTE, 17)
        cols = (0, 360, 580, 700)
        w, alto_fila = 840, 30
        h = 130 + alto_fila * (len(filas) + 1) + 40
        im = Image.new("RGBA", (w, h), (0, 0, 0, 0))
        d = ImageDraw.Draw(im)
        d.rounded_rectangle([0, 0, w - 1, h - 1], 16, fill=(255, 255, 255, 245),
                            outline=(11, 110, 153, 255), width=3)
        d.text((30, 20), titulo, font=self.f_t, fill=(31, 42, 51, 255))
        d.text((30, 58), sub, font=self.f_s, fill=(91, 102, 112, 255))
        y = 100
        for x, t in zip(cols, ("Pueblo / núcleo", "Municipio", "Media", "Máximo")):
            d.text((30 + x, y), t, font=f_c, fill=(91, 102, 112, 255))
        d.line([30, y + 26, w - 30, y + 26], fill=(196, 204, 210, 255), width=1)
        for fila in filas:
            y += alto_fila + (6 if fila is filas[0] else 0)
            for x, t in zip(cols, fila):
                d.text((30 + x, y), t, font=f_r, fill=(31, 42, 51, 255))
        d.text((30, h - 40), pie, font=self.f_s, fill=(91, 102, 112, 255))
        return im, (self.x0 + (self.w - w) // 2, self.y0 + (self.h - h) // 2)


# ── codificación en otro hilo ─────────────────────────────────────────────────────────────
class Codificador(threading.Thread):
    def __init__(self, salida):
        super().__init__(daemon=True)
        self.cola = queue.Queue(maxsize=60)
        self.n = 0
        self.proc = subprocess.Popen(
            ["ffmpeg", "-y", "-loglevel", "error", "-f", "rawvideo", "-pix_fmt", "rgb24",
             "-s", f"{ANCHO}x{ALTO}", "-r", str(FPS), "-i", "-", "-c:v", "libx264",
             "-preset", "veryfast", "-crf", "20", "-pix_fmt", "yuv420p", "-movflags", "+faststart",
             str(salida)], stdin=subprocess.PIPE)
        self.start()

    def run(self):
        while True:
            item = self.cola.get()
            if item is None:
                break
            im, capas = item
            for capa, pos in capas:
                im.alpha_composite(capa, pos)
            self.proc.stdin.write(im.convert("RGB").tobytes())
            self.n += 1

    def cerrar(self):
        self.cola.put(None)
        self.join()
        self.proc.stdin.close()
        return self.proc.wait()


# ── la app ────────────────────────────────────────────────────────────────────────────────
JS_VIDEO = """
window.__video = (function () {
  var m = null;
  for (var k in window) { try { if (window[k] instanceof L.Map) { m = window[k]; break; } } catch (e) {} }
  function cierra() { m.eachLayer(function (l) { if (l.getTooltip && l.getTooltip()) { l.closeTooltip(); } }); }
  return {
    encuadra: function (b) { m.invalidateSize({pan: false}); m.fitBounds(b, {padding: [30, 30]});
                             return [m.getZoom(), m.getSize().x, m.getSize().y]; },
    cierra: cierra,
    abre: function (lat, lon) {
      cierra();
      var mejor = null, d = 1e9;
      m.eachLayer(function (l) {
        if (l instanceof L.Marker && l.getTooltip()) {
          var p = l.getLatLng(), dd = Math.abs(p.lat - lat) + Math.abs(p.lng - lon);
          if (dd < d) { d = dd; mejor = l; }
        }
      });
      if (mejor) { mejor.openTooltip(); }
      return d;
    }
  };
})();
true;
"""


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--dia", default="2026-10-21")
    ap.add_argument("--salida", default=str(Path(__file__).with_name("penacho_pueblos.mp4")))
    args = ap.parse_args()

    QtCore.QCoreApplication.setAttribute(QtCore.Qt.ApplicationAttribute.AA_ShareOpenGLContexts)
    app = QtWidgets.QApplication(sys.argv[:1])
    from teodors.comun import registro
    from teodors.gui.ventana import VentanaPrincipal
    from teodors.fuentes import terreno
    registro.configurar()

    v = VentanaPrincipal(dia_inicial=args.dia)
    v.show()
    v.resize(ANCHO, ALTO)

    def espera(seg):
        t = time.time()
        while time.time() - t < seg:
            app.processEvents()
            time.sleep(0.005)

    def js(codigo):
        r = {}
        v.mapa.page().runJavaScript(codigo, 0, lambda x: r.setdefault("v", x))
        t = time.time()
        while "v" not in r and time.time() - t < 10:
            app.processEvents()
            time.sleep(0.005)
        return r.get("v")

    # 1) esperar a que estén el viento y el penacho del día
    t = time.time()
    while time.time() - t < 90:
        espera(0.5)
        if v._dia_penacho and (js("JSON.stringify(ence.estadoPenacho && ence.estadoPenacho())") or "").find("fotogramas") > 0:
            break
    else:
        raise SystemExit(f"No se cargó el penacho del {args.dia} (¿está en los DATOS?)")
    v.dock_consola.hide()
    v.resize(ANCHO, ALTO)
    espera(1.0)
    js(JS_VIDEO)

    # pueblos alcanzados (los mismos valores que enseñan las fichas de la app)
    nucleos = v._resumen["nucleos"]
    nombres = v._nombres
    filas = []
    for n, val in zip(nucleos, v._valores_nucleos or []):
        if val and val["maximo"] > 0:
            nom = nombres.get(terreno.clave_nucleo(n), {})
            filas.append(dict(n, **val, poblacion=nom.get("poblacion") or n["tipo"],
                              municipio=nom.get("municipio", "")))
    filas.sort(key=lambda f: -f["media"])
    avisa(f"Núcleos alcanzados el {args.dia}: {len(filas)}")
    for f in filas:
        avisa(f"  {f['poblacion']} ({f['municipio']}, {f['familia']}): media {num(f['media'])} · "
              f"máx {num(f['maximo'])} µg/m³ · {f['dist_m'] / 1000:.1f} km {f['rumbo']}")
    resid = [f for f in filas if f["familia"] == "residencial"]
    otros = [f for f in filas if f["familia"] != "residencial"]
    ruta_media = sorted(resid[:2] + otros[:1], key=lambda f: f["dist_m"])
    ruta_max = sorted(filas, key=lambda f: -f["maximo"])[:2]

    # encuadre: la planta y los pueblos alcanzados
    lats = [v.emp["lat"]] + [f["lat"] for f in filas[:6]]
    lons = [v.emp["lon"]] + [f["lon"] for f in filas[:6]]
    zoom = js(f"__video.encuadra([[{min(lats) - 0.02}, {min(lons) - 0.03}], "
              f"[{max(lats) + 0.02}, {max(lons) + 0.02}]])")
    avisa(f"Encuadre a zoom {zoom}; esperando las teselas…")
    espera(6)

    p = v.mapa.mapTo(v, QtCore.QPoint(0, 0))
    R = Rotulos((p.x(), p.y(), v.mapa.width(), v.mapa.height()))
    cod = Codificador(Path(args.salida))
    dia_txt = f"{args.dia[8:10]}/{args.dia[5:7]}/{args.dia[:4]}"
    fuente_txt = "Fuente de prueba de 1 g/s en la planta (aún no son los focos de ENCE) · µg/m³"

    tamanos = set()

    def cuadro(capas=()):
        t0 = time.time()
        img = v.grab().toImage().convertToFormat(QtGui.QImage.Format.Format_RGBA8888)
        if (img.width(), img.height()) not in tamanos:
            tamanos.add((img.width(), img.height()))
            avisa(f"Captura de {img.width()}×{img.height()} px")
        if img.width() != ANCHO or img.height() != ALTO:
            img = img.scaled(ANCHO, ALTO, QtCore.Qt.AspectRatioMode.IgnoreAspectRatio,
                             QtCore.Qt.TransformationMode.SmoothTransformation)
        im = Image.frombuffer("RGBA", (ANCHO, ALTO), bytes(img.constBits()), "raw", "RGBA", 0, 1).copy()
        cod.cola.put((im, list(capas)))
        resto = 1.0 / FPS - (time.time() - t0)       # ritmo real ≈ el del vídeo (partículas)
        espera(max(0.0, resto))

    def segundos(s, capas=()):
        for _ in range(int(s * FPS)):
            cuadro(capas)

    # 2) presentación
    titulo = R.banda("Herramienta de dispersión · ENCE La Galera",
                     f"Penacho del {dia_txt} · viento 3D de teOdors (GFS + 8 estaciones de Meteocat)")
    segundos(3.5, [titulo])

    # 3) el día, cuarto de hora a cuarto de hora (el deslizador del panel mueve viento y penacho)
    s = v.panel.hora_viento
    for q in range(s.maximum() + 1):
        s.setValue(q)
        hh = v.panel.lbl_hora_viento.text()
        banda = R.banda(f"Evolución del penacho · {dia_txt} · {hh}", fuente_txt)
        for _ in range(POR_PASO):
            cuadro([banda])
    s.setValue(0)

    # 4) media del día y fichas de los pueblos
    js("ence.quitarViento()")
    v.mapa.ver_capa("penacho_media", True)
    espera(1.0)
    banda = R.banda(f"Media del día en cada pueblo · {dia_txt}",
                    "Pasa el ratón por un pueblo: media, máximo y P98 del día · " + fuente_txt)
    segundos(2.0, [banda])
    for f in ruta_media:
        js(f"__video.abre({f['lat']}, {f['lon']})")
        segundos(3.0, [banda])

    # 5) máximo horario del día
    js("__video.cierra()")
    v.mapa.ver_capa("penacho_maximo", True)
    espera(1.0)
    banda = R.banda(f"Máximo horario del día · {dia_txt}", fuente_txt)
    segundos(1.5, [banda])
    for f in ruta_max:
        js(f"__video.abre({f['lat']}, {f['lon']})")
        segundos(3.0, [banda])
    js("__video.cierra()")

    # 6) resumen
    parte = {"residencial": "casco urbano", "industrial": "zona industrial",
             "deportivo": "zona deportiva"}
    tabla = [((f["poblacion"] if f["poblacion"].lower().startswith(("polígon", "polígono"))
               else f"{f['poblacion']} · {parte[f['familia']]}")[:34], f["municipio"][:22],
              num(f["media"]), num(f["maximo"])) for f in filas[:8]]
    tarjeta = R.tarjeta(f"Pueblos alcanzados por el penacho el {dia_txt}",
                        "Media y máximo horario del día en cada núcleo (µg/m³)", tabla,
                        "Fuente de prueba de 1 g/s en la planta · con los focos de ENCE saldrán en ou_E/m³")
    segundos(6.0, [tarjeta])

    rc = cod.cerrar()
    tam = Path(args.salida).stat().st_size / 1e6 if Path(args.salida).exists() else 0
    avisa(f"Vídeo: {args.salida} · {cod.n} fotogramas ({cod.n / FPS:.1f} s) · {tam:.1f} MB · ffmpeg rc={rc}")
    os._exit(0)                  # sin closeEvent: no cambia la disposición guardada de la app


if __name__ == "__main__":
    main()
