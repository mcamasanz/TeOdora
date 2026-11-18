# -*- coding: utf-8 -*-
"""Las gráficas del informe, en SVG dentro del HTML (nítidas en el PDF), sin Qt: una serie diaria de varios años (usuario, 2026-11-10: «gráficas
de los valores medios por día de estos 5 años»), como línea (cada día, fina, y su media de 30 días, gruesa), con su banda (lo menos y lo más
del día, en su media de 30 días: el día a día de la capa de mezcla, de 20 a 3 000 m, aplastaba la línea), en barras (la lluvia) o en puntos (de dónde sopla el viento). Un solo eje y una sola serie en cada una: el título de su casilla
dice lo que es; los años, abajo.
"""
import math

import numpy as np

from teodors.comun.formato import num as _num

ANCHO, ALTO = 300.0, 128.0                 # el viewBox: en la página, el ancho de su casilla (el alto, en proporción)
IZQ, DER, ARR, ABA = 30.0, 4.0, 5.0, 14.0  # márgenes: los números del eje y, a la izquierda; los años, abajo
COLOR = "#1f7a60"                          # el verde oscuro del informe (el de las cifras)
REJILLA, EJE, TEXTO = "#e6ece8", "#c9d2cc", "#6b7a72"
LETRA = 9.5                                # la de los ejes, en unidades del viewBox (≈ 5,5 pt en una casilla de un tercio de la página)
MEDIA_DIAS = 30
RUMBOS_EJE = ((0, "N"), (90, "E"), (180, "S"), (270, "O"), (360, "N"))


def pasos(lo, hi, n=5):
    """Unas `n` marcas limpias (1, 2, 2,5 o 5 por una potencia de 10) que cubren [lo, hi]."""
    if not (math.isfinite(lo) and math.isfinite(hi)) or hi <= lo:
        hi = lo + 1.0
    bruto = (hi - lo) / max(n - 1, 1)
    p = 10 ** math.floor(math.log10(bruto))
    paso = next(k * p for k in (1, 2, 2.5, 5, 10) if k * p >= bruto)
    a = math.floor(lo / paso + 1e-9) * paso
    marcas = []
    while a <= hi + paso * 1e-9:
        marcas.append(round(a, 10))
        a += paso
    if marcas[-1] < hi - 1e-9:
        marcas.append(round(marcas[-1] + paso, 10))
    return marcas


def media_movil(v, n=MEDIA_DIAS):
    """La media de `n` días centrada en cada uno, sin los huecos (NaN); en los bordes, con los que haya (al menos la mitad)."""
    v = np.asarray(v, float)
    ok = np.isfinite(v)
    k = np.ones(n)
    suma = np.convolve(np.where(ok, v, 0.0), k, mode="same")
    cuenta = np.convolve(ok.astype(float), k, mode="same")
    return np.where(cuenta >= n / 2, suma / np.maximum(cuenta, 1), np.nan)


def decimales(marcas):
    """Los decimales que necesitan las marcas del eje (0, 0,25, 0,5 → 2)."""
    return next((k for k in range(4) if all(abs(round(m, k) - m) < 1e-9 for m in marcas)), 3)


def _trazo(xs, ys):
    """El `d` de un camino por los puntos, cortado en los huecos."""
    partes, nuevo = [], True
    for x, y in zip(xs, ys):
        if not math.isfinite(y):
            nuevo = True
            continue
        partes.append(f"{'M' if nuevo else 'L'}{x:.1f} {y:.1f}")
        nuevo = False
    return "".join(partes)


def diaria(dias, v, vmin=None, vmax=None, forma="linea", desde_cero=False, titulo=""):
    """La serie diaria `v` (una por día de `dias`, `datetime.date`) en SVG. `forma`: «linea» (cada día y su media de 30 días; con `vmin` y
    `vmax`, la banda de lo menos y lo más del día, en su media de 30 días), «barras» (desde 0: la lluvia) o «rumbos» (puntos, de 0 a 360°: de
    dónde sopla). `titulo`: lo que lee un lector de pantalla."""
    v = np.asarray(v, float)
    n = len(v)
    banda = vmin is not None and vmax is not None
    if banda:
        lo_b, hi_b = np.fmin(media_movil(vmin), v), np.fmax(media_movil(vmax), v)    # la escala, con los días que se salgan de la banda
        b_lo, b_hi = media_movil(vmin), media_movil(vmax)
    else:
        lo_b, hi_b = v, v
    if forma == "rumbos":
        lo, hi, marcas = 0.0, 360.0, [m for m, _ in RUMBOS_EJE]
    else:
        fin = np.isfinite(lo_b) & np.isfinite(hi_b)
        lo = 0.0 if (forma == "barras" or desde_cero) else float(np.min(lo_b[fin])) if fin.any() else 0.0
        hi = float(np.max(hi_b[fin])) if fin.any() else 1.0
        marcas = pasos(lo, hi)
        lo, hi = marcas[0], marcas[-1]
    w, h = ANCHO - IZQ - DER, ALTO - ARR - ABA

    def X(i):
        return IZQ + w * (i + 0.5) / max(n, 1)

    def Y(y):
        return ARR + h * (1.0 - (y - lo) / (hi - lo))
    piezas = [f"<svg class='grafica' viewBox='0 0 {ANCHO:g} {ALTO:g}' xmlns='http://www.w3.org/2000/svg' role='img' aria-label='{titulo}'>"]
    # rejilla y eje y: finos, en gris
    for m in marcas:
        piezas.append(f"<line x1='{IZQ:g}' x2='{ANCHO - DER:g}' y1='{Y(m):.1f}' y2='{Y(m):.1f}' stroke='{REJILLA}' stroke-width='.6'/>")
        txt = dict(RUMBOS_EJE).get(m, "") if forma == "rumbos" else _num(m, decimales(marcas))
        piezas.append(f"<text x='{IZQ - 3:g}' y='{Y(m) + LETRA * 0.35:.1f}' text-anchor='end' font-size='{LETRA:g}' fill='{TEXTO}'>{txt}</text>")
    # los años: una raya donde empieza cada uno y su número en medio
    anios = {}
    for i, d in enumerate(dias):
        anios.setdefault(d.year, [i, i])[1] = i
    for a, (i0, i1) in anios.items():
        if i0 > 0:
            piezas.append(f"<line x1='{X(i0) - w / n / 2:.1f}' x2='{X(i0) - w / n / 2:.1f}' y1='{ARR:g}' y2='{ARR + h:g}' stroke='{REJILLA}' stroke-width='.6'/>")
        if i1 - i0 > n / 40:
            piezas.append(f"<text x='{(X(i0) + X(i1)) / 2:.1f}' y='{ALTO - 3:g}' text-anchor='middle' font-size='{LETRA:g}' fill='{TEXTO}'>{a}</text>")
    piezas.append(f"<line x1='{IZQ:g}' x2='{ANCHO - DER:g}' y1='{ARR + h:.1f}' y2='{ARR + h:.1f}' stroke='{EJE}' stroke-width='.7'/>")
    xs = [X(i) for i in range(n)]
    if forma == "barras":
        d = "".join(f"M{x:.1f} {Y(0):.1f}V{Y(y):.1f}" for x, y in zip(xs, v) if math.isfinite(y) and y > 0)
        piezas.append(f"<path d='{d}' stroke='{COLOR}' stroke-width='{max(w / n, .55):.2f}' fill='none'/>")
    elif forma == "rumbos":
        piezas.append("".join(f"<circle cx='{x:.1f}' cy='{Y(y):.1f}' r='.85' fill='{COLOR}' fill-opacity='.38'/>" for x, y in zip(xs, v)
                              if math.isfinite(y)))
    else:
        if banda:
            arriba = [(x, Y(y)) for x, y in zip(xs, b_hi) if math.isfinite(y)]
            abajo = [(x, Y(y)) for x, y in zip(xs, b_lo) if math.isfinite(y)]
            puntos = " ".join(f"{x:.1f},{y:.1f}" for x, y in arriba + abajo[::-1])
            piezas.append(f"<polygon points='{puntos}' fill='{COLOR}' fill-opacity='.14'/>")
        piezas.append(f"<path d='{_trazo(xs, [Y(y) for y in v])}' stroke='{COLOR}' stroke-opacity='.3' stroke-width='.5' fill='none' "
                      "stroke-linejoin='round'/>")
        piezas.append(f"<path d='{_trazo(xs, [Y(y) for y in media_movil(v)])}' stroke='{COLOR}' stroke-width='1.5' fill='none' "
                      "stroke-linejoin='round' stroke-linecap='round'/>")
    piezas.append("</svg>")
    return "".join(piezas)


MESES_INICIAL = ("E", "F", "M", "A", "M", "J", "J", "A", "S", "O", "N", "D")


COLOR_A, COLOR_B = "#0b7f57", "#d97a2b"     # los dos escenarios (validados: normal 25, daltónicos 8,9 de ΔE; contraste con el blanco ≥ 3)


def dia_dos(ha, hb, etiquetas=("A", "B"), titulo=""):
    """El día medio de dos escenarios, hora a hora, en % (`ha`, `hb`: 24 valores en tanto por uno): dos líneas, A y B, con su letra al final
    de cada una; un solo eje, desde 0."""
    ha, hb = np.asarray(ha, float) * 100, np.asarray(hb, float) * 100
    ancho, alto_v, letra = 600.0, 112.0, 7.5                    # a lo ancho de la página: las letras, como las de las otras gráficas
    izq, arr, aba = 34.0, 6.0, 16.0
    w = ancho - izq - 18.0
    h = alto_v - arr - aba
    marcas = pasos(0.0, max(float(ha.max()), float(hb.max()), 1.0), n=4)
    hi = marcas[-1]

    def X(i):
        return izq + w * i / 23.0

    def Y(v):
        return arr + h * (1.0 - v / hi)
    piezas = [f"<svg class='grafica dia2' viewBox='0 0 {ancho:g} {alto_v:g}' xmlns='http://www.w3.org/2000/svg' role='img' aria-label='{titulo}'>"]
    for m in marcas:
        piezas.append(f"<line x1='{izq:g}' x2='{izq + w:g}' y1='{Y(m):.1f}' y2='{Y(m):.1f}' stroke='{REJILLA}' stroke-width='.6'/>")
        piezas.append(f"<text x='{izq - 4:g}' y='{Y(m) + letra * 0.35:.1f}' text-anchor='end' font-size='{letra:g}' fill='{TEXTO}'>{_num(m, decimales(marcas))} %</text>")
    for j in (0, 3, 6, 9, 12, 15, 18, 21, 23):
        piezas.append(f"<text x='{X(j):.1f}' y='{alto_v - 4:g}' text-anchor='middle' font-size='{letra:g}' fill='{TEXTO}'>{j} h</text>")
    for v, color in ((ha, COLOR_A), (hb, COLOR_B)):
        d = "".join(f"{'M' if i == 0 else 'L'}{X(i):.1f} {Y(x):.1f}" for i, x in enumerate(v))
        piezas.append(f"<path d='{d}' stroke='{color}' stroke-width='1.5' fill='none' stroke-linejoin='round' stroke-linecap='round'/>")
    ya, yb = Y(ha[-1]), Y(hb[-1])
    if abs(ya - yb) < 8:                                         # las letras, sin pisarse: se separan un poco
        medio = (ya + yb) / 2
        ya, yb = (medio - 4, medio + 4) if ha[-1] >= hb[-1] else (medio + 4, medio - 4)
    for yy, cual in ((ya, etiquetas[0]), (yb, etiquetas[1])):
        piezas.append(f"<text x='{izq + w + 4:g}' y='{yy + letra * 0.35:.1f}' font-size='{letra:g}' font-weight='700' fill='#2b3631'>{cual}</text>")
    piezas.append("</svg>")
    return "".join(piezas)


def calor(M, tope, titulo=""):
    """Un mapa de calor de 12 meses (filas) por 24 horas del día (columnas): `M` (12 × 24), con el color de la rampa del informe estirada de
    0 a `tope` (el mismo para los que van juntos); lo que es 0, en gris. Un hueco blanco entre casillas."""
    from . import estilo
    M = np.asarray(M, float)
    izq, arr, aba = 12.0, 2.0, 12.0
    w = (ANCHO - izq - DER) / 24.0
    h = w * 0.88                                              # filas lo bastante altas para su inicial
    alto = arr + 12 * h + aba
    piezas = [f"<svg class='grafica calor' viewBox='0 0 {ANCHO:g} {alto:.1f}' xmlns='http://www.w3.org/2000/svg' role='img' aria-label='{titulo}'>"]
    for i in range(12):
        y = arr + i * h
        piezas.append(f"<text x='{izq - 3:g}' y='{y + h * 0.72:.1f}' text-anchor='end' font-size='{LETRA * 0.8:.1f}' fill='{TEXTO}'>{MESES_INICIAL[i]}</text>")
        for j in range(24):
            v = M[i, j]
            color = estilo.rampa(min(v / tope, 1.0)) if v > 0 and tope > 0 else "#eef2ef"
            piezas.append(f"<rect x='{izq + j * w + .4:.1f}' y='{y + .4:.1f}' width='{w - .8:.1f}' height='{h - .8:.1f}' rx='.8' fill='{color}'/>")
    for j in (0, 6, 12, 18, 23):
        piezas.append(f"<text x='{izq + (j + 0.5) * w:.1f}' y='{alto - 3:.1f}' text-anchor='middle' font-size='{LETRA * 0.85:.1f}' fill='{TEXTO}'>{j}</text>")
    piezas.append("</svg>")
    return "".join(piezas)


def muestra(forma):
    """Un trocito de cada forma, para la clave de cómo se leen las gráficas."""
    if forma == "banda":
        return ("<svg viewBox='0 0 26 12' class='muestra'><path d='M0 3C8 1 17 2 26 4V10C17 9 8 11 0 9Z' fill='%s' fill-opacity='.16'/></svg>" % COLOR)
    if forma == "dia":
        return ("<svg viewBox='0 0 26 12' class='muestra'><path d='M0 7L3 4L6 8L9 3L12 7L15 5L18 9L21 4L26 6' stroke='%s' stroke-opacity='.45' "
                "stroke-width='.8' fill='none'/></svg>" % COLOR)
    if forma == "media":
        return "<svg viewBox='0 0 26 12' class='muestra'><path d='M0 8C8 3 16 3 26 6' stroke='%s' stroke-width='1.8' fill='none'/></svg>" % COLOR
    if forma == "barras":
        return ("<svg viewBox='0 0 26 12' class='muestra'><path d='M3 11V6M7 11V2M12 11V8M17 11V4M22 11V9' stroke='%s' stroke-width='1.2'/></svg>"
                % COLOR)
    return ("<svg viewBox='0 0 26 12' class='muestra'>" + "".join(f"<circle cx='{x}' cy='{y}' r='1' fill='{COLOR}' fill-opacity='.5'/>"
                                                                 for x, y in ((3, 4), (7, 5), (10, 3), (14, 8), (18, 4), (22, 5)))
            + "</svg>")
