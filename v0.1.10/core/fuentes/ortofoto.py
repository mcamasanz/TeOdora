# -*- coding: utf-8 -*-
"""La ortofoto de la planta para el plano de la página Focos (usuario, 2026-11-08: «que en el mapa de los focos del panel se vea la imagen
satélite y encima los focos»).

Son las teselas del PRIMER fondo de la planta (`fuentes.fondos` de planta.json: XYZ en Web Mercator, el que el mapa enseña al abrir) que
cubren un cuadrado alrededor de los focos, cosidas y llevadas a la cuadrícula UTM de la planta: así no quedan giradas la convergencia de
meridianos (en un huso, de 0 a unos 3°) respecto a los focos. En unos cientos de metros, el paso de UTM a Web Mercator es afín a menos de
una centésima de píxel: basta una transformación afín, ajustada sobre 25 puntos.

Se guarda con la planta, en su carpeta `terreno/` (`ortofoto_focos.jpg` y `ortofoto_focos.json`), como el relieve: el ejecutable la lleva
y no hace falta red. Se pide otra solo si los focos se salen de la que hay.

    {"recuadro": [x0, y0, x1, y1], "epsg", "res_m", "fondo": nombre, "credito": texto, "z", "teselas", "fallos", "fecha"}

Lo que devuelven `cargar`, `vigente`, `descargar` y `para_focos` es eso mismo con «ruta», la del JPEG.
"""
import datetime as dt
import io
import json
import math
import re
import ssl
import time
import urllib.error
import urllib.request

import numpy as np

from teodors import planta as config
from teodors.comun import registro
from teodors.planta import geo

log = registro.get("ortofoto")

try:
    import certifi
    _SSL = ssl.create_default_context(cafile=certifi.where())
except Exception:                                                   # noqa: BLE001
    _SSL = ssl.create_default_context()

NOMBRE = "ortofoto_focos"
RES_M = 0.25            # m por píxel de lo que se guarda: la ortofoto del PNOA a zoom 19 es de unos 0,23 m en la península
MARGEN_M = 18.0         # alrededor de los focos, el del plano (`gui.focos_graficos.PlanoFocos.MARGEN_M`): tiene que estar siempre
HOLGURA = 1.7           # y más allá, porque el plano se encuadra a lo ancho del panel
ZOOM_MAX = 19
TESELAS_MAX = 144       # si hicieran falta más, un zoom menos
TESELA = 256
TIMEOUT = 20


def fondo():
    """[nombre, url, atribución, zoom máximo] del primer fondo de la planta, o None si no tiene."""
    fondos = config.bloque("fuentes").get("fondos") or []
    return list(fondos[0]) if fondos else None


def ruta():
    return config.DIR_TERRENO / f"{NOMBRE}.jpg"


def _puntos(catalogo):
    xs, ys = [], []
    for f in (catalogo or {}).get("focos", []):
        u = f.get("ubicacion") or {}
        pts = u.get("poligono") or ([[u["x"], u["y"]]] if u.get("x") is not None and u.get("y") is not None else [])
        xs += [float(p[0]) for p in pts]
        ys += [float(p[1]) for p in pts]
    return xs, ys


def recuadros(catalogo):
    """(lo que se descarga, lo que tiene que cubrir) en UTM, (x0, y0, x1, y1): un cuadrado centrado en los focos, con su margen y holgura
    (redondeado a 10 m); y el de los focos con el margen del plano. None si no hay focos ubicados."""
    xs, ys = _puntos(catalogo)
    if not xs:
        return None
    nucleo = (min(xs) - MARGEN_M, min(ys) - MARGEN_M, max(xs) + MARGEN_M, max(ys) + MARGEN_M)
    cx, cy = (nucleo[0] + nucleo[2]) / 2, (nucleo[1] + nucleo[3]) / 2
    media = math.ceil(max(nucleo[2] - nucleo[0], nucleo[3] - nucleo[1]) / 2 * HOLGURA / 10) * 10
    cx, cy = round(cx / 10) * 10, round(cy / 10) * 10
    return (cx - media, cy - media, cx + media, cy + media), nucleo


def _cubre(fuera, dentro):
    return fuera[0] <= dentro[0] and fuera[1] <= dentro[1] and fuera[2] >= dentro[2] and fuera[3] >= dentro[3]


def cargar():
    """La info de la ortofoto guardada, con «ruta» (la del JPEG), o None."""
    j = config.DIR_TERRENO / f"{NOMBRE}.json"
    try:
        info = json.loads(j.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return None
    return dict(info, ruta=str(ruta())) if ruta().is_file() and info.get("epsg") == config.EPSG_UTM else None


def vigente(catalogo):
    """La ortofoto guardada si cubre los focos con el margen del plano; si no, None (y hay que pedirla: `para_focos`)."""
    g, r = cargar(), recuadros(catalogo)
    return g if g is not None and r is not None and _cubre(g["recuadro"], r[1]) else None


def _merc(lat, lon, z):
    """Píxel global de Web Mercator a zoom z (TESELA píxeles por tesela)."""
    n = TESELA * 2 ** z
    lat = np.clip(np.asarray(lat, float), -85.05112878, 85.05112878)
    return (np.asarray(lon, float) + 180.0) / 360.0 * n, (1 - np.arcsinh(np.tan(np.radians(lat))) / np.pi) / 2 * n


def _tesela(url, z, x, y):
    """Los bytes de una tesela, con tres intentos."""
    req = urllib.request.Request(url.replace("{z}", str(z)).replace("{x}", str(x)).replace("{y}", str(y)),
                                 headers={"User-Agent": config.AGENTE_HTTP})
    for k in range(3):
        try:
            with urllib.request.urlopen(req, timeout=TIMEOUT, context=_SSL) as r:
                return r.read()
        except (urllib.error.URLError, TimeoutError, ConnectionError) as e:
            if k == 2:
                raise
            log.debug(f"Ortofoto: reintento {k + 1} de la tesela {z}/{x}/{y} ({e!r})")
            time.sleep(2 * (k + 1))


def descargar(recuadro, progreso=None):
    """Pide las teselas del primer fondo que cubren `recuadro` (UTM), las cose, las lleva a UTM con RES_M y lo guarda; devuelve su info.
    Una tesela que falla queda en gris; si fallan más de la cuarta parte, RuntimeError. `progreso(pct, texto)`, si se da."""
    from PIL import Image
    f = fondo()
    if f is None:
        raise ValueError("la planta no tiene fondos de mapa (fuentes.fondos de planta.json)")
    nombre, url = f[0], f[1]
    credito = re.sub(r"<[^>]+>", "", f[2] if len(f) > 2 else "").strip()
    x0, y0, x1, y1 = (float(v) for v in recuadro)
    lat, lon = geo.a_geo(np.array([x0, x1, x1, x0]), np.array([y0, y0, y1, y1]))
    z = int(min(f[3] if len(f) > 3 and f[3] else ZOOM_MAX, ZOOM_MAX))
    while True:
        px, py = _merc(lat, lon, z)
        tx0, tx1, ty0, ty1 = int(px.min() // TESELA), int(px.max() // TESELA), int(py.min() // TESELA), int(py.max() // TESELA)
        n = (tx1 - tx0 + 1) * (ty1 - ty0 + 1)
        if n <= TESELAS_MAX or z <= 10:
            break
        z -= 1
    mosaico = Image.new("RGB", ((tx1 - tx0 + 1) * TESELA, (ty1 - ty0 + 1) * TESELA), (128, 128, 128))
    fallos, hechas = 0, 0
    for ty in range(ty0, ty1 + 1):
        for tx in range(tx0, tx1 + 1):
            try:
                with Image.open(io.BytesIO(_tesela(url, z, tx, ty))) as t:
                    mosaico.paste(t.convert("RGB").resize((TESELA, TESELA)), ((tx - tx0) * TESELA, (ty - ty0) * TESELA))
            except (OSError, ValueError) as e:                    # sin respuesta, o no es una imagen
                fallos += 1
                log.debug(f"Ortofoto: sin la tesela {z}/{tx}/{ty} ({e!r})")
            hechas += 1
            if progreso:
                progreso(int(100 * hechas / n), f"Ortofoto: {hechas} de {n} teselas")
    if fallos > n / 4:
        raise RuntimeError(f"{nombre}: {fallos} de {n} teselas sin respuesta")
    # a la cuadrícula UTM: el píxel (i, j) de la imagen es la esquina (x0 + i·RES_M, y1 − j·RES_M)
    ancho, alto = int(round((x1 - x0) / RES_M)), int(round((y1 - y0) / RES_M))
    ii, jj = np.meshgrid(np.linspace(0, ancho, 5), np.linspace(0, alto, 5))
    la, lo = geo.a_geo(x0 + ii.ravel() * RES_M, y1 - jj.ravel() * RES_M)
    u, v = _merc(la, lo, z)
    A = np.column_stack([ii.ravel(), jj.ravel(), np.ones(ii.size)])
    cu = np.linalg.lstsq(A, u - tx0 * TESELA, rcond=None)[0]
    cv = np.linalg.lstsq(A, v - ty0 * TESELA, rcond=None)[0]
    img = mosaico.transform((ancho, alto), Image.Transform.AFFINE, tuple(cu) + tuple(cv), resample=Image.Resampling.BICUBIC)
    config.DIR_TERRENO.mkdir(parents=True, exist_ok=True)
    img.save(ruta(), quality=85)
    info = {"recuadro": [x0, y0, x1, y1], "epsg": config.EPSG_UTM, "res_m": RES_M, "fondo": nombre, "credito": credito, "z": z,
            "teselas": n, "fallos": fallos, "fecha": dt.date.today().isoformat()}
    (config.DIR_TERRENO / f"{NOMBRE}.json").write_text(json.dumps(info, ensure_ascii=False, indent=1), encoding="utf-8")
    log.info(f"Ortofoto del plano de focos: {n} teselas de «{nombre}» a zoom {z}" + (f", {fallos} sin respuesta" if fallos else ""))
    return dict(info, ruta=str(ruta()))


def para_focos(catalogo, progreso=None):
    """La ortofoto que cubre los focos: la guardada si los cubre y, si no, una nueva. None si no hay focos ubicados."""
    g = vigente(catalogo)
    if g is not None:
        return g
    r = recuadros(catalogo)
    return None if r is None else descargar(r[0], progreso)
