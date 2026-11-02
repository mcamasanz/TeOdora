# -*- coding: utf-8 -*-
"""meteo.viento_local · viento alrededor de obstáculos inventados: lo que la física exige y lo medido en túnel de viento.

⚠️ El modelo NO está validado (ver su README) y estas pruebas no lo validan. Comprueban que el código hace lo que dicen sus
ecuaciones y dónde queda frente a referencias externas:
- conservación de masa, sólidos, simetrías, perfil logarítmico y dosel de Cionco: lo exige la formulación, y da igual el sitio;
- cubo aislado frente a Martinuzzi y Tropea (1993, canal, Re = 40 000; ERCOFTAC UFR 3-14, tabla 1): separación delante 1,04 H y
  reataque detrás 1,612 H. ⚠️ La longitud detrás la impone una fórmula (1,45 H): se comprueba el código y la fórmula, no que el
  modelo prediga la estela;
- colina baja frente a Jackson y Hunt (1975), aceleración relativa ≈ 2 h / L: el modelo se queda corto, y aquí se deja medido.
"""
import importlib.util
import json
import re
import subprocess
import sys
import tomllib
from pathlib import Path

import numpy as np
import pytest

import teodors
from teodors import planta
from teodors.__main__ import main as linea_de_ordenes
from teodors.comun import procesos
from teodors.meteo.viento_local import biblioteca, modelo

RAIZ = Path(__file__).resolve().parents[3]
CARPETA = RAIZ / "core" / "meteo" / "viento_local"
CON_SCIPY = importlib.util.find_spec("scipy") is not None
pide_scipy = pytest.mark.skipif(not CON_SCIPY, reason="necesita scipy (teodors[viento_local])")

H = 10.0                    # el cubo de todas las pruebas
Z0 = 0.1
REATAQUE_MEDIDO = 1.612     # en H, detrás del cubo: Martinuzzi y Tropea (1993)
DELANTE_MEDIDO = 1.04       # en H, delante del cubo: Martinuzzi y Tropea (1993)


def _cubo(dx, dz, x=(-40.0, 80.0), y=(-40.0, 40.0), alto=60.0):
    """Un cubo de H m centrado en el origen. Con 2,5 m ocupa 4 celdas por lado; con 5 m, 2."""
    nx, ny, nz = int((x[1] - x[0]) / dx), int((y[1] - y[0]) / dx), int(alto / dz)
    dom = modelo.Dominio(x[0], y[0], nx, ny, dx, nz, dz)
    X, Y = np.meshgrid(dom.xc, dom.yc)
    m = (np.abs(X) < H / 2) & (np.abs(Y) < H / 2)
    dom = modelo.Dominio(x[0], y[0], nx, ny, dx, nz, dz, altura=np.where(m, H, 0.0))
    pol = np.array([[-H / 2, -H / 2], [H / 2, -H / 2], [H / 2, H / 2], [-H / 2, H / 2]])
    return dom, [{"poligono": pol, "h": H, "mascara": m}]


def _sin_obstaculos(dom):
    return modelo.Dominio(dom.x0, dom.y0, dom.nx, dom.ny, dom.dx, dom.nz, dom.dz)


def _calcula(dom, ed=(), rumbo=270.0):
    return modelo.calcula(dom, rumbo, ed, z_ref=H, z0=Z0)


@pytest.fixture(scope="module")
def cubo_25():
    """Viento del oeste contra el cubo: (dominio, campo, campo sin el cubo). Compila el núcleo la primera vez (`cache=False`)."""
    dom, ed = _cubo(2.5, 1.25)
    return dom, _calcula(dom, ed), _calcula(_sin_obstaculos(dom))


@pytest.fixture(scope="module")
def cubo_1():
    dom, ed = _cubo(1.0, 1.0)
    return dom, _calcula(dom, ed), _calcula(_sin_obstaculos(dom))


@pytest.fixture(scope="module")
def cuadrado():
    """El cubo en el centro de un dominio cuadrado, con el viento de tres lados: para las simetrías."""
    dom, ed = _cubo(2.5, 1.25, x=(-40.0, 40.0), y=(-40.0, 40.0))
    return {r: _calcula(dom, ed, r) for r in (270.0, 90.0, 0.0)}


def _espia_caras(monkeypatch):
    """Guarda las velocidades en las CARAS que `calcula` da por buenas: la última vez que mira la divergencia."""
    caras = {}
    original = modelo._divergencia

    def espia(dom, u, v, w):
        caras["uvw"] = (u.copy(), v.copy(), w.copy())
        return original(dom, u, v, w)

    monkeypatch.setattr(modelo, "_divergencia", espia)
    return caras


def _reataque(dom, r):
    """Detrás del cubo, en el eje y cerca del suelo, en H desde la cara trasera: (primera celda con u > 0, cruce por cero
    interpolado). La primera es lo que daba el prototipo, y se pasa hasta una celda por arriba."""
    k = max(int(0.1 * H / dom.dz), 0)
    u, x = r["u"][k, dom.ny // 2], dom.xc
    i = np.flatnonzero((x > H / 2) & (u > 0))[0]
    cruce = x[i - 1] - u[i - 1] * (x[i] - x[i - 1]) / (u[i] - u[i - 1])
    return (x[i] - H / 2) / H, (cruce - H / 2) / H


# ------------------------------------------------------------------------------ fórmulas de base
@pytest.mark.compilacion
def test_el_nucleo_compila():
    # `_sor` no guarda su compilación (`cache=False`): se paga una vez en cada proceso, aquí, la primera de este fichero
    n, residuo = modelo._sor(np.zeros((4, 4, 4)), np.zeros((4, 4, 4)), np.zeros((4, 4, 4), dtype=bool), 1.0, 1.0, 1.85, 30, 1e-4)
    assert n == 25 and residuo == 0.0            # sin nada que corregir, para en la primera comprobación del residuo


def test_perfil_logaritmico():
    assert modelo.perfil(np.array(H), H, Z0) == 1.0
    assert modelo.perfil(np.array(Z0), H, Z0) == 0.0
    assert modelo.perfil(np.array(Z0 / 10), H, Z0) == 0.0      # por debajo de z0, nada
    assert modelo.perfil(np.array(20.0), H, Z0) == pytest.approx(np.log(200.0) / np.log(100.0))


@pytest.mark.parametrize("rumbo, ex, ey", [(0.0, 0.0, -1.0), (90.0, -1.0, 0.0), (180.0, 0.0, 1.0), (270.0, 1.0, 0.0),
                                           (45.0, -np.sqrt(0.5), -np.sqrt(0.5))])
def test_el_rumbo_dice_de_donde_viene(rumbo, ex, ey):
    # convenio meteorológico: el viento del norte (0°) va hacia el sur
    assert modelo.direccion_a_vector(rumbo) == pytest.approx((ex, ey), abs=1e-12)


@pytest.mark.parametrize("rumbo", [270.0, 33.0])
def test_sin_obstaculos_queda_el_perfil_exacto(rumbo):
    # un perfil que solo depende de z no diverge: la corrección de masa no tiene nada que corregir
    dom = modelo.Dominio(-40.0, -40.0, 32, 32, 2.5, 32, 1.25)
    r = _calcula(dom, rumbo=rumbo)
    ex, ey = modelo.direccion_a_vector(rumbo)
    p = modelo.perfil(dom.zc, H, Z0)[:, None, None]
    assert r["div_antes"] < 1e-12 and r["div_despues"] < 1e-12
    assert np.abs(r["u"] - p * ex).max() < 1e-12 and np.abs(r["v"] - p * ey).max() < 1e-12 and np.abs(r["w"]).max() < 1e-12


def test_la_velocidad_solo_escala(cubo_25):
    # sin ecuaciones de movimiento ni estabilidad, el campo es lineal: por eso basta una biblioteca por dirección
    dom, r1, _ = cubo_25
    _, ed = _cubo(2.5, 1.25)
    r3 = modelo.calcula(dom, 270.0, ed, z_ref=H, z0=Z0, vel=3.0)
    for c in "uvw":
        assert np.array_equal(r3[c], 3.0 * r1[c])


# ------------------------------------------------------------------------------ conservación de masa y sólidos
@pytest.mark.parametrize("rumbo", [270.0, 33.0])
def test_conserva_la_masa(rumbo, monkeypatch):
    # con las velocidades en las CARAS, y contándolo aquí: ni lo que dice `calcula` ni su función de la divergencia
    caras = _espia_caras(monkeypatch)
    dom, ed = _cubo(2.5, 1.25)
    r = _calcula(dom, ed, rumbo)
    u, v, w = caras["uvw"]
    dx, dz = dom.dx, dom.dz
    d = np.diff(u, axis=2) / dx + np.diff(v, axis=1) / dx + np.diff(w, axis=0) / dz
    d[dom.solido] = 0.0
    assert np.abs(d).max() == pytest.approx(r["div_despues"])
    assert np.abs(d).max() < 2e-4                         # el residuo que se pide al resolver es 1e-4
    assert r["div_antes"] > 1000.0 * np.abs(d).max()      # las zonas empíricas sí crean y destruyen aire: de ~0,4 a < 2e-4
    # lo que entra por los lados y por la tapa es lo que sale
    cara_lat, cara_sup = dx * dz, dx * dx
    entra = (np.clip(u[:, :, 0], 0, None).sum() - np.clip(u[:, :, -1], None, 0).sum()
             + np.clip(v[:, 0], 0, None).sum() - np.clip(v[:, -1], None, 0).sum()) * cara_lat
    neto = (u[:, :, -1].sum() - u[:, :, 0].sum() + v[:, -1].sum() - v[:, 0].sum()) * cara_lat + (w[-1].sum() - w[0].sum()) * cara_sup
    assert abs(neto) < 1e-3 * entra


def test_nada_atraviesa_el_obstaculo_ni_el_suelo(monkeypatch):
    caras = _espia_caras(monkeypatch)
    dom, ed = _cubo(2.5, 1.25)
    r = _calcula(dom, ed, 33.0)
    s = dom.solido
    assert s.sum() == 4 * 4 * 8                  # 4 celdas de 2,5 m por lado y 8 de 1,25 m de alto
    for c in "uvw":
        assert (r[c][s] == 0.0).all()            # velocidad cero dentro, exactamente
    u, v, w = caras["uvw"]
    for cara in (u[:, :, :-1][s], u[:, :, 1:][s], v[:, :-1][s], v[:, 1:][s], w[:-1][s], w[1:][s], w[0]):
        assert (cara == 0.0).all()               # ni a través de sus caras, ni del suelo
    assert np.isnan(modelo.a_altura(dom, r["u"], 3.0)[dom.altura > 3.0]).all()


def test_condicion_de_contorno_a_la_entrada():
    # φ = 0 en los lados: lejos del obstáculo, el aire entra con el perfil sin tocar, y cuanto más lejos, más igual
    medido = {}
    for x0 in (-40.0, -100.0):                   # la entrada a 3,5 H y a 9,5 H de la cara de delante
        dom, ed = _cubo(2.5, 1.25, x=(x0, 80.0), y=(-100.0, 100.0), alto=80.0)
        r = _calcula(dom, ed)
        p = modelo.perfil(dom.zc, H, Z0)[:, None]
        q = r["u"][:, :, 0] / p
        assert (r["u"][:, :, 0] > 0).all()       # entra en toda la cara
        medido[x0] = np.abs(1.0 - q).max()
    assert medido[-40.0] < 0.06                  # medido: 0,048
    assert medido[-100.0] < 0.005                # medido: 0,0032


# ------------------------------------------------------------------------------ simetrías
def test_obstaculo_simetrico_da_un_campo_simetrico(cubo_25):
    # espejo respecto al eje del viento. La tolerancia es el residuo del cálculo: rojo-negro no recorre igual los dos lados
    _, r, _ = cubo_25
    assert np.abs(r["u"] - r["u"][:, ::-1]).max() < 1e-4
    assert np.abs(r["v"] + r["v"][:, ::-1]).max() < 1e-4
    assert np.abs(r["w"] - r["w"][:, ::-1]).max() < 1e-4
    assert np.abs(r["v"]).max() > 0.1            # el aire rodea el cubo: la simetría no sale de que no haya nada


def test_el_campo_gira_con_el_viento(cuadrado):
    # el cubo en el centro de un cuadrado: viento del este, espejo del del oeste; viento del norte, el del oeste girado 90°
    o, e, n = cuadrado[270.0], cuadrado[90.0], cuadrado[0.0]
    assert np.abs(o["u"] + e["u"][:, :, ::-1]).max() < 1e-4
    assert np.abs(o["v"] - e["v"][:, :, ::-1]).max() < 1e-4
    assert np.abs(o["w"] - e["w"][:, :, ::-1]).max() < 1e-4
    gira = lambda a: np.rot90(a, k=1, axes=(1, 2))
    assert np.abs(n["u"] - gira(o["v"])).max() < 1e-4
    assert np.abs(n["v"] + gira(o["u"])).max() < 1e-4
    assert np.abs(n["w"] - gira(o["w"])).max() < 1e-4


# ------------------------------------------------------------------------------ el cubo frente a lo medido
def test_reataque_detras_del_cubo_en_el_orden_de_lo_medido(cubo_1, cubo_25):
    # Martinuzzi y Tropea (1993): 1,612 H. Queda corto, y se deja dicho con su número
    primera_1, cruce_1 = _reataque(*cubo_1[:2])
    primera_25, cruce_25 = _reataque(*cubo_25[:2])
    assert primera_1 == pytest.approx(1.35, abs=0.02)    # con 10 celdas por lado: lo medido con el prototipo
    assert primera_25 == pytest.approx(1.38, abs=0.02)   # con 4 celdas por lado
    assert cruce_1 == pytest.approx(1.30, abs=0.02)      # el cruce por cero, sin el redondeo a la celda
    assert cruce_25 == pytest.approx(1.19, abs=0.02)
    assert abs(cruce_1 - REATAQUE_MEDIDO) / REATAQUE_MEDIDO < 0.25
    assert abs(primera_25 - REATAQUE_MEDIDO) / REATAQUE_MEDIDO < 0.25


def test_con_dos_celdas_por_obstaculo_la_estela_sale_a_la_mitad():
    # por eso hacen falta unas 4 celdas por obstáculo como poco: es el límite de resolución del modelo
    dom, ed = _cubo(5.0, 2.5)
    primera, _ = _reataque(dom, _calcula(dom, ed))
    assert primera == pytest.approx(0.75, abs=0.02)
    assert primera < 0.5 * REATAQUE_MEDIDO


def test_las_zonas_empiricas_salen_de_sus_formulas():
    # antes de corregir la masa: 2 W / (1 + 0,8 W / H) delante, 1,8 W / (1,24) detrás y 3 veces eso de estela, en un cubo
    dom, ed = _cubo(1.0, 1.0)
    us0 = modelo.perfil(dom.sobre_suelo(), H, Z0)
    us, cavidad = us0.copy(), np.zeros(us0.shape, dtype=bool)
    modelo._zonas(dom, ed[0], 1.0, 0.0, H, Z0, us, cavidad)
    j, x = dom.ny // 2, dom.xc
    z_rel = 0.5 / H                                    # la capa de abajo, centrada a 0,5 m
    lf = 2.0 / 1.8 * H * np.sqrt(1.0 - (0.5 / (0.6 * H)) ** 2)
    lr = 1.8 / 1.24 * H * np.sqrt(1.0 - z_rel ** 2)
    cambia = us[0, j] != us0[0, j]
    delante = (-H / 2 - x[cambia & (x < -H / 2)].min())
    assert lf - dom.dx <= delante <= lf
    detras = x[cavidad[0, j]].max() - H / 2
    assert lr - dom.dx <= detras <= lr
    assert (us[0, j][cavidad[0, j]] <= 0).all()        # dentro de la cavidad, el aire vuelve
    lejos = x[cambia & (x > H / 2)].max() - H / 2
    assert 3.0 * lr - dom.dx <= lejos <= 3.0 * lr
    # sus formas. Delante, 0,4 veces el perfil. La cavidad se estrecha hacia arriba y hacia los lados como una elipse
    frente = (x > -H / 2 - 0.9 * lf) & (x < -H / 2)
    assert np.allclose(us[0, j][frente], 0.4 * us0[0, j][frente])
    largo = lambda k, fila: x[cavidad[k, fila]].max() - H / 2
    k_08 = int(0.8 * H / dom.dz)                       # a 0,85 H
    assert largo(k_08, j) == pytest.approx(1.8 / 1.24 * H * np.sqrt(1.0 - 0.85 ** 2), abs=1.5 * dom.dx)    # se mide desde el centro de la última celda
    fila_09 = np.argmin(np.abs(dom.yc - 4.5))          # a 0,9 del semiancho
    assert largo(0, fila_09) == pytest.approx(lr * np.sqrt(1.0 - 0.9 ** 2), abs=1.5 * dom.dx)
    # la estela lejana: 1 − (cavidad / x)^1,5, con la cavidad en esa fila y x desde el centro de la última celda del edificio
    i_2 = np.argmin(np.abs(x - (H / 2 + 2.0 * lr)))
    cavidad_j = lr * np.sqrt(1.0 - (dom.yc[j] / (H / 2)) ** 2)
    assert us[0, j, i_2] / us0[0, j, i_2] == pytest.approx(1.0 - (cavidad_j / (x[i_2] - (H / 2 - dom.dx / 2))) ** 1.5)
    # frente a lo medido: delante, 1,11 H frente a 1,04 H; detrás, 1,45 H frente a 1,61 H
    assert abs(2.0 / 1.8 - DELANTE_MEDIDO) / DELANTE_MEDIDO < 0.10
    assert abs(1.8 / 1.24 - REATAQUE_MEDIDO) / REATAQUE_MEDIDO < 0.11


@pytest.mark.parametrize("ancho, fondo", [(20.0, 10.0), (10.0, 20.0)])
def test_la_cavidad_depende_del_ancho_y_del_fondo(ancho, fondo):
    # Fackrell: 1,8 W / ((L / H)^0,3 · (1 + 0,24 W / H)). Un edificio ancho y poco profundo deja más cavidad que al revés
    dom = modelo.Dominio(-60.0, -40.0, 160, 80, 1.0, 12, 1.0)
    X, Y = np.meshgrid(dom.xc, dom.yc)
    m = (np.abs(X) < fondo / 2) & (np.abs(Y) < ancho / 2)
    pol = np.array([[-fondo / 2, -ancho / 2], [fondo / 2, -ancho / 2], [fondo / 2, ancho / 2], [-fondo / 2, ancho / 2]])
    us = modelo.perfil(dom.sobre_suelo(), H, Z0)
    cavidad = np.zeros(us.shape, dtype=bool)
    modelo._zonas(dom, {"poligono": pol, "h": H, "mascara": m}, 1.0, 0.0, H, Z0, us, cavidad)
    lr = 1.8 * ancho / ((fondo / H) ** 0.3 * (1.0 + 0.24 * ancho / H))
    largo = dom.xc[cavidad[0, dom.ny // 2]].max() - fondo / 2
    assert largo == pytest.approx(lr, abs=1.5)


def test_rodea_el_obstaculo_y_recupera_detras(cubo_25):
    dom, r, sin = cubo_25
    j, x = dom.ny // 2, dom.xc
    k = int(0.5 * H / dom.dz)
    rel = r["u"][k, j] / sin["u"][k, j]
    estela = [float(np.interp(H / 2 + d * H, x, rel)) for d in (1, 2, 3, 5)]
    assert estela == sorted(estela)                      # se recupera poco a poco
    assert estela[1] == pytest.approx(0.54, abs=0.02)    # a 2 H, medido con el prototipo
    assert estela[3] == pytest.approx(0.99, abs=0.01)    # ⚠️ a 5 H ha desaparecido por construcción: la estela acaba en 3 veces la cavidad
    # el aire que no pasa por el cubo pasa por los lados y por encima: ahí, más rápido
    i = np.argmin(np.abs(x))
    al_lado = r["u"][k, np.argmin(np.abs(dom.yc - 0.8 * H)), i] / sin["u"][k, np.argmin(np.abs(dom.yc - 0.8 * H)), i]
    encima = r["u"][int(1.2 * H / dom.dz), j, i] / sin["u"][int(1.2 * H / dom.dz), j, i]
    assert 1.02 < al_lado < 1.3 and 1.02 < encima < 1.3
    # delante frena, y a 3 H ya casi no se nota
    cerca = r["u"][int(0.25 * H / dom.dz), j] / sin["u"][int(0.25 * H / dom.dz), j]
    assert np.interp(-H / 2 - 0.5 * H, x, cerca) < 0.5
    assert np.interp(-H / 2 - 3.0 * H, x, cerca) > 0.95


@pytest.mark.parametrize("rumbo", [33.0, 120.0, 210.0, 300.0])
def test_la_cavidad_queda_a_sotavento(rumbo):
    # un edificio de 20 x 10 m fuera del centro, con el viento de través: la cavidad, detrás de él y centrada con él
    dom = modelo.Dominio(-60.0, -60.0, 48, 48, 2.5, 24, 1.25)
    X, Y = np.meshgrid(dom.xc, dom.yc)
    xm, ym = 7.5, -5.0
    m = (np.abs(X - xm) < 10.0) & (np.abs(Y - ym) < 5.0)
    pol = np.array([[xm - 10, ym - 5], [xm + 10, ym - 5], [xm + 10, ym + 5], [xm - 10, ym + 5]])
    dom = modelo.Dominio(-60.0, -60.0, 48, 48, 2.5, 24, 1.25, altura=np.where(m, H, 0.0))
    c = modelo.calcula(dom, rumbo, [{"poligono": pol, "h": H, "mascara": m}], z_ref=H, z0=Z0)["cavidad"][0]
    ex, ey = modelo.direccion_a_vector(rumbo)
    assert c.sum() > 10 and not (c & m).any()
    s = (X[c] - xm) * ex + (Y[c] - ym) * ey                # a lo largo del viento
    t = -(X[c] - xm) * ey + (Y[c] - ym) * ex               # a lo ancho
    assert s.mean() > 5.0 and abs(t.mean()) < 3.0


def test_da_igual_en_que_orden_vengan_los_edificios():
    # se aplican de barlovento a sotavento, vengan como vengan
    dom = modelo.Dominio(-20.0, -20.0, 40, 16, 2.5, 24, 1.25)
    X, Y = np.meshgrid(dom.xc, dom.yc)

    def caja(xm):
        pol = np.array([[xm - 5, -5.0], [xm + 5, -5.0], [xm + 5, 5.0], [xm - 5, 5.0]])
        return {"poligono": pol, "h": H, "mascara": (np.abs(X - xm) < 5.0) & (np.abs(Y) < 5.0)}

    a, b = caja(0.0), caja(30.0)
    dom = modelo.Dominio(-20.0, -20.0, 40, 16, 2.5, 24, 1.25, altura=np.where(a["mascara"] | b["mascara"], H, 0.0))
    uno, otro = (modelo.calcula(dom, 270.0, e, z_ref=H, z0=Z0)["u"] for e in ([a, b], [b, a]))
    assert np.array_equal(uno, otro)


def test_edificio_mas_estrecho_que_la_celda_no_tiene_zonas():
    dom = modelo.Dominio(-20.0, -20.0, 16, 16, 2.5, 16, 1.25)
    us0 = modelo.perfil(dom.sobre_suelo(), H, Z0)
    us, cavidad = us0.copy(), np.zeros(us0.shape, dtype=bool)
    estrecho = {"poligono": np.array([[0.0, 0.0], [5.0, 0.0], [5.0, 1.0], [0.0, 1.0]]), "h": 5.0, "mascara": np.zeros((16, 16), bool)}
    modelo._zonas(dom, estrecho, 1.0, 0.0, H, Z0, us, cavidad)
    assert np.array_equal(us, us0) and not cavidad.any()


# ------------------------------------------------------------------------------ dosel y relieve
def test_dosel_uniforme_sigue_a_cionco():
    # Cionco (1965): u(z) = u(h)·exp(a·(z/h − 1)) dentro de los árboles. Uniforme, no diverge y queda la fórmula exacta
    h_dosel, a = 5.0, 1.5
    dom = modelo.Dominio(0.0, 0.0, 16, 16, 5.0, 12, 1.0)
    r = modelo.calcula(dom, 270.0, z_ref=H, z0=0.25, dosel=np.full((16, 16), h_dosel), a_dosel=a)
    uh = modelo.perfil(np.array(h_dosel), H, 0.25)
    z = dom.zc
    esperado = np.where(z < h_dosel, uh * np.exp(a * (z / h_dosel - 1.0)), modelo.perfil(z, H, 0.25))
    assert np.abs(r["u"] - esperado[:, None, None]).max() < 1e-12


def _colina(h, ancho=100.0):
    """Una loma alargada: suelo = h / (1 + (x / ancho)²), con el viento de frente."""
    nx, ny, nz, dx, dz = 120, 24, 80, 10.0, 2.5
    x = (np.arange(nx) + 0.5) * dx - 600.0
    dom = modelo.Dominio(-600.0, 0.0, nx, ny, dx, nz, dz, suelo=np.tile(h / (1.0 + (x / ancho) ** 2), (ny, 1)))
    r = modelo.calcula(dom, 270.0, z_ref=H, z0=Z0)
    a_10 = modelo.a_altura(dom, r["u"], 10.0)
    return dom, r, float(a_10[12, 60] / a_10[12, 2] - 1.0)


def test_colina_acelera_pero_menos_que_la_teoria():
    # Jackson y Hunt (1975): aceleración relativa ≈ 2 h / L en una loma baja. Sin ecuaciones de movimiento se queda corto:
    # medido, 0,155 frente a 0,4 con h = 20 m y 0,076 frente a 0,2 con h = 10 m. Crece con h como dice la teoría
    dom, r, ds_20 = _colina(20.0)
    _, _, ds_10 = _colina(10.0)
    assert dom.solido.any() and (r["u"][dom.solido] == 0.0).all()
    assert r["div_despues"] < 2e-4
    assert ds_20 == pytest.approx(0.155, abs=0.01) and ds_10 == pytest.approx(0.076, abs=0.01)
    assert 1.8 < ds_20 / ds_10 < 2.3
    assert 0 < ds_20 < 2.0 * 20.0 / 100.0


def test_a_altura_interpola_y_salta_lo_solido():
    altura = np.zeros((4, 4))
    altura[1, 1], altura[2, 2] = 5.0, 2.0
    suelo = np.zeros((4, 4))
    suelo[0, 0] = 2.5                      # con relieve, se cuenta desde su suelo
    dom = modelo.Dominio(0.0, 0.0, 4, 4, 2.5, 16, 1.25, altura=altura, suelo=suelo)
    campo = np.broadcast_to(dom.zc[:, None, None], dom.solido.shape).copy()
    v = modelo.a_altura(dom, campo, 3.0)
    assert v[3, 3] == pytest.approx(3.0) and v[0, 0] == pytest.approx(5.5)
    assert np.isnan(v[1, 1])               # edificio más alto que los 3 m
    # edificio de 2 m: a 3 m se está por encima de él, pero la celda de abajo es sólida: se toma la de arriba
    assert v[2, 2] == pytest.approx(dom.zc[2])


# ------------------------------------------------------------------------------ de una nube de puntos a los obstáculos
N, X0, Y0, PENDIENTE = 240, 1000.0, 2000.0, 0.01
TANQUES = ((1060.0, 2060.0, 13.0), (1085.0, 2060.0, 12.0))    # x, y y altura; radio 12 m


def _lidar(ruta):
    """Rejillas de 1 m inventadas, sobre un terreno con 1 % de pendiente:
    una nave aislada; un cobertizo con cables por encima; dos tanques unidos por un murete; una nave en dientes de sierra; y dos
    cosas que no cuentan, un cuartillo de 9 m² y una valla de 2 m."""
    J, I = np.mgrid[:N, :N]
    x, y = I + 0.5, J + 0.5
    ter = 100.0 + PENDIENTE * x
    alto, edif = np.zeros((N, N)), np.zeros((N, N), np.int32)

    def pon(m, h):
        alto[m], edif[m] = h, 5

    pon((x > 150) & (x < 180) & (y > 150) & (y < 175), 9.8)
    pon((x > 30) & (x < 38) & (y > 200) & (y < 208), 3.0)
    pon((x > 70) & (x < 75) & (y > 58) & (y < 62), 3.0)
    for xt, yt, h in TANQUES:
        pon((x - (xt - X0)) ** 2 + (y - (yt - Y0)) ** 2 < 12.0 ** 2, h)
    sierra = (x > 150) & (x < 190) & (y > 40) & (y < 80)
    pon(sierra, 0.0)
    alto[sierra] = 7.0 + 3.0 * ((x[sierra] - 150.0) % 10.0) / 10.0
    pon((x > 100) & (x < 103) & (y > 200) & (y < 203), 6.0)
    pon((x > 100) & (x < 130) & (y > 120) & (y < 124), 2.0)
    dsm = ter + alto
    cables = (y > 203) & (y < 205)
    dsm[cables] = ter[cables] + 31.0
    dtm = np.where(edif > 0, np.inf, ter)
    np.savez_compressed(ruta, dsm=dsm, dsm_edif=np.where(edif > 0, ter + alto, -np.inf), dtm=dtm, edificio=edif, x0=X0, y0=Y0)
    return ruta


@pytest.fixture(scope="module")
def lidar(tmp_path_factory):
    return _lidar(tmp_path_factory.mktemp("viento_local") / "lidar.npz")


@pide_scipy
def test_lee_lidar_terreno_y_alturas(lidar):
    L = modelo.lee_lidar(lidar)
    assert (L["x0"], L["y0"], L["n"]) == (X0, Y0, N)
    assert L["terreno"][120, 120] == pytest.approx(100.0 + PENDIENTE * 120.5, abs=0.01)   # bajo los edificios, de sus vecinos
    # los cables pasan a 31 m: `alto` los ve, pero de ellos no sale ningún obstáculo. Levantaban un cobertizo de 3 m a 31 m
    assert L["alto"][204, 34] == pytest.approx(31.0, abs=0.05)
    assert L["obstaculo"][204, 34] == pytest.approx(3.0, abs=0.05)
    assert L["alto"][204, 80] == pytest.approx(31.0, abs=0.05) and L["obstaculo"][204, 80] == 0.0


@pide_scipy
def test_obstaculos_separa_los_tanques_y_no_las_naves(lidar):
    eds = modelo.obstaculos(modelo.lee_lidar(lidar))
    assert len(eds) == 5                                   # sin el cuartillo (9 m²) ni la valla (2 m)
    assert [e["area"] for e in eds] == sorted((e["area"] for e in eds), reverse=True)
    # la nave en dientes de sierra es una sola, aunque cada cumbrera sea un pico; y la aislada, también
    sierra, nave = eds[0], eds[1]
    assert sierra["area"] == 1600 and sierra["centro"] == pytest.approx([1170.0, 2060.0], abs=0.5)
    assert nave["area"] == 750 and nave["centro"] == pytest.approx([1165.0, 2162.5], abs=0.5)
    assert nave["h"] == pytest.approx(9.8, abs=0.2)        # 0,15 m arriba o abajo por la pendiente
    # los dos tanques se tocan por el murete: son dos
    t1, t2 = eds[3], eds[2]
    assert t1["centro"] == pytest.approx(TANQUES[0][:2], abs=3.0) and t2["centro"] == pytest.approx(TANQUES[1][:2], abs=3.0)
    assert t1["area"] + t2["area"] > 800                   # es el tamaño a partir del cual se mira si hay que separar
    assert 11.5 < t2["h"] < 13.5 and 12.5 < t1["h"] < 13.5
    # el cobertizo, con su altura y no la de los cables
    assert eds[4]["area"] == 64 + 4 and eds[4]["h"] == pytest.approx(3.0, abs=0.1)    # + las 4 celdas de al lado, bajo los cables
    for e in eds:                                          # polígono convexo que contiene el centro
        (xa, ya), (xb, yb) = e["poligono"].min(axis=0), e["poligono"].max(axis=0)
        assert xa <= e["centro"][0] <= xb and ya <= e["centro"][1] <= yb


def test_misma_cubierta():
    alto = np.zeros((40, 40))
    alto[10, 5:35] = 8.0
    a, b = np.array([10, 5]), np.array([10, 34])
    assert modelo._misma_cubierta(alto, alto, a, b)                # un tejado corrido
    alto[10, 15:18] = 5.0
    assert modelo._misma_cubierta(alto, alto, a, b)                # dientes de sierra: nunca baja de la mitad
    alto[10, 15:18] = 1.0
    assert not modelo._misma_cubierta(alto, alto, a, b)            # depósitos pegados: entre ellos, casi el suelo
    alto[10, 15:18] = 20.0
    assert not modelo._misma_cubierta(alto, alto, a, b)            # la recta cruza algo más alto
    alto[10, 15:18] = 8.0
    alto[10, 5] = 3.0
    assert not modelo._misma_cubierta(alto, alto, a, b)            # alturas muy distintas


@pide_scipy
def test_a_rejilla_y_monta(lidar):
    L = modelo.lee_lidar(lidar)
    eds = modelo.obstaculos(L)
    s, c, x_ini, y_ini, ny, nx = modelo.a_rejilla(L, L["terreno"], 5.0, (1120.0, 2120.0), (100.0, 80.0))
    assert (x_ini, y_ini, ny, nx) == (1020.0, 2040.0, 32, 40)
    assert c.sum() == 200 * 160 and (c == 25).all()                # 25 celdas de 1 m en cada una de 5 m
    assert s.sum() == pytest.approx(L["terreno"][40:200, 20:220].sum())    # nada se pierde al pasar de rejilla
    dom, cabe, altura = modelo.monta(L, eds, 2.5, 1.25, (1120.0, 2120.0), 110.0)
    assert (dom.nx, dom.ny) == (88, 88) and len(cabe) == 5
    assert dom.x0 == 1010.0 and dom.y0 == 2010.0
    assert dom.nz == int(np.ceil((dom.suelo.max() + 60.0) / 1.25))
    assert dom.suelo.min() == 0.0 and dom.suelo.max() == pytest.approx(PENDIENTE * 220.0, abs=0.1)
    i, j = int((1165.0 - dom.x0) / dom.dx), int((2162.5 - dom.y0) / dom.dx)
    assert altura[j, i] == pytest.approx(9.8, abs=0.2) and dom.solido[0, j, i]
    assert altura[int((2000.0 + 120.0 - dom.y0) / dom.dx), int((1115.0 - dom.x0) / dom.dx)] == 0.0    # la valla y lo vacío
    llano, _, _ = modelo.monta(L, eds, 2.5, 1.25, (1120.0, 2120.0), 110.0, con_relieve=False)
    assert (llano.suelo == 0.0).all()


# ------------------------------------------------------------------------------ biblioteca
BLOQUE = {"puntos": [[1100.0, 2100.0], [1140.0, 2120.0]], "radio_m": 40.0, "radio_borde_m": 60.0, "margen_m": 20.0, "dx": 2.5, "dz": 1.25,
          "alto_m": 3.0, "lidar": "viento_local/lidar.npz", "biblioteca": "campos.npz"}


def test_parametros_del_bloque_de_la_planta(tmp_path):
    p = biblioteca.parametros(BLOQUE, tmp_path)
    assert p == {"puntos": [(1100.0, 2100.0), (1140.0, 2120.0)], "radio": 40.0, "radio_borde": 60.0, "margen": 20.0, "dx": 2.5, "dz": 1.25,
                 "alto": 3.0, "salida": tmp_path / "campos.npz"}
    assert biblioteca.zona(p["puntos"], p["radio_borde"], p["margen"]) == ((1120.0, 2110.0), (100.0, 90.0))


@pytest.mark.parametrize("cambio, error", [
    ({"radio_m": None}, r"viento_local\.radio_m"), ({"puntos": None}, r"viento_local\.puntos"), ({"biblioteca": None}, r"viento_local\.biblioteca"),
    ({"puntos": [[1.0, 2.0]]}, "dos puntos"), ({"puntos": [[1.0, 2.0], [1.0, 2.0]]}, "dos puntos"), ({"radio_borde_m": 40.0}, "radio_borde_m"),
])
def test_parametros_sin_valores_por_defecto(cambio, error, tmp_path):
    # dependen del sitio: uno equivocado no se notaría. Y con dos puntos iguales, el mapa divide por cero
    bloque = {k: v for k, v in {**BLOQUE, **cambio}.items() if v is not None}
    with pytest.raises(ValueError, match=error):
        biblioteca.parametros(bloque, tmp_path)


@pytest.fixture(scope="module")
def campos(lidar, tmp_path_factory):
    """Una biblioteca de 4 direcciones sobre el LiDAR inventado."""
    ruta = tmp_path_factory.mktemp("biblioteca") / "campos.npz"
    p = biblioteca.parametros(BLOQUE, ruta.parent)
    biblioteca.principal(lidar, 90.0, **p)
    return ruta, p


@pide_scipy
def test_principal_guarda_lo_que_necesita_el_mapa(campos):
    ruta, p = campos
    with np.load(ruta) as z:
        assert sorted(z.files) == sorted(["u", "v", "paso", "x0", "y0", "dx", "cx", "cy", "cx2", "cy2", "radio", "radio_borde", "escala", "solido", "alto"])
        assert z["u"].dtype == np.int16 and z["u"].shape == z["v"].shape == (4, 56, 64)     # 4 direcciones; ±90 y ±100 m sin el margen
        assert [float(z[k]) for k in ("cx", "cy", "cx2", "cy2", "radio", "radio_borde", "dx", "alto", "paso")] == [1100.0, 2100.0, 1140.0, 2120.0, 40.0, 60.0, 2.5, 3.0, 90.0]
        assert float(z["escala"]) == biblioteca.ESCALA and int(z["solido"]) == biblioteca.SOLIDO
        assert float(z["x0"]) == 1020.0 + 20.0 + 1.25 and float(z["y0"]) == 2020.0 + 20.0 + 1.25    # el centro de la 1.ª celda, sin el margen


@pide_scipy
def test_lejos_de_los_edificios_vale_uno(campos):
    # cada campo va relativo al viento sin edificios a esa altura: lejos de ellos, la dirección y la velocidad de entrada
    lib = biblioteca.lee(campos[0])
    i, j = int((1120.0 - lib["x0"]) / lib["dx"]), int((2130.0 - lib["y0"]) / lib["dx"])
    for k, rumbo in enumerate((0.0, 90.0, 180.0, 270.0)):
        ex, ey = modelo.direccion_a_vector(rumbo)
        assert lib["u"][k, j, i] == pytest.approx(ex, abs=0.05) and lib["v"][k, j, i] == pytest.approx(ey, abs=0.05)


@pide_scipy
def test_dentro_de_un_edificio_no_hay_campo(campos):
    lib = biblioteca.lee(campos[0])
    i, j = int((1165.0 - lib["x0"]) / lib["dx"]), int((2162.5 - lib["y0"]) / lib["dx"])    # la nave aislada, de 9,8 m
    assert np.isnan(lib["u"][:, j, i]).all() and np.isnan(lib["v"][:, j, i]).all()
    i, j = int((1120.0 - lib["x0"]) / lib["dx"]), int((2130.0 - lib["y0"]) / lib["dx"])
    assert np.isfinite(lib["u"][:, j, i]).all()
    with np.load(campos[0]) as z:
        assert (z["u"] == biblioteca.SOLIDO).sum() == np.isnan(lib["u"]).sum()
        assert np.isclose(np.nanmax(np.abs(lib["u"])), np.abs(z["u"][z["u"] != biblioteca.SOLIDO]).max() * biblioteca.ESCALA)


def _biblioteca_de_prueba(paso=90.0):
    """Campos fáciles de reconocer: cada dirección vale su número de orden, y la celda (0, 0) es sólida en la dirección 1."""
    n = int(360.0 / paso)
    u = np.array([np.full((2, 2), float(k)) for k in range(n)], dtype=np.float32)
    v = 10.0 * u
    u[1, 0, 0] = v[1, 0, 0] = np.nan
    return {"u": u, "v": v, "paso": paso}


def _viento_de(rumbo, vel):
    ex, ey = modelo.direccion_a_vector(rumbo)
    return vel * ex, vel * ey


@pytest.mark.parametrize("rumbo, k0, k1, f", [(0.0, 0, 1, 0.0), (90.0, 1, 2, 0.0), (270.0, 3, 0, 0.0), (45.0, 0, 1, 0.5), (135.0, 1, 2, 0.5),
                                              (22.5, 0, 1, 0.25), (315.0, 3, 0, 0.5), (337.5, 3, 0, 0.75)])
def test_mezcla_elige_los_dos_campos_mas_cercanos(rumbo, k0, k1, f):
    # de 315° a 360° se mezcla la última dirección con la primera: el rumbo da la vuelta
    lib = _biblioteca_de_prueba()
    u, v = biblioteca.mezcla(lib, *_viento_de(rumbo, 1.0))
    assert u[1, 1] == pytest.approx(k0 + (k1 - k0) * f, abs=1e-5) and v[1, 1] == pytest.approx(10.0 * (k0 + (k1 - k0) * f), abs=1e-4)


def test_mezcla_escala_con_la_velocidad_y_respeta_los_solidos():
    lib = _biblioteca_de_prueba()
    u1, _ = biblioteca.mezcla(lib, *_viento_de(120.0, 1.0))
    u3, _ = biblioteca.mezcla(lib, *_viento_de(120.0, 3.0))
    assert u3[1, 1] == pytest.approx(3.0 * u1[1, 1])
    assert np.isnan(u1[0, 0])                                     # entre la dirección 1 (sólida) y la 2
    assert np.isfinite(biblioteca.mezcla(lib, *_viento_de(200.0, 1.0))[0][0, 0])    # entre la 2 y la 3, no
    cero_u, cero_v = biblioteca.mezcla(lib, 0.0, 0.0)             # en calma, nada
    assert cero_u[1, 1] == 0.0 and cero_v[1, 1] == 0.0


@pide_scipy
def test_mezcla_reproduce_el_viento_de_entrada_lejos_de_los_edificios(campos):
    lib = biblioteca.lee(campos[0])
    i, j = int((1120.0 - lib["x0"]) / lib["dx"]), int((2130.0 - lib["y0"]) / lib["dx"])
    for rumbo, vel in ((0.0, 4.0), (90.0, 2.0), (270.0, 6.0)):      # justo en una dirección de la biblioteca
        ex, ey = _viento_de(rumbo, vel)
        u, v = biblioteca.mezcla(lib, ex, ey)
        assert u[j, i] == pytest.approx(ex, abs=0.05 * vel) and v[j, i] == pytest.approx(ey, abs=0.05 * vel)


@pide_scipy
def test_main_con_una_planta_inventada(lidar, tmp_path, monkeypatch, capsys):
    # el bloque lo da la planta, y el paquete no la importa: se le pasa
    monkeypatch.delenv("PLANTA_INVENTADA_DATOS", raising=False)
    json_planta = {"identidad": {"app_nombre": "P", "organizacion": "O", "prefijo_env": "PLANTA_INVENTADA", "carpeta_local": "p", "registro": "p"},
                   "proyeccion": {"epsg": "EPSG:25830", "crs_geo": "EPSG:4258"},
                   "dominio": {"lado_km": 20, "margen_m": 250, "res_terreno_m": 25, "radio_edificios_km": 1, "radio_edificios_focos_m": 100,
                               "celda_viento_m": 500, "zface": [0, 20]},
                   "receptores": {"por_km2": 5}, "reanalisis": {"anios": [2022]}, "viento_local": BLOQUE}
    (tmp_path / "planta.json").write_text(json.dumps(json_planta), encoding="utf-8")
    p = planta.Planta(tmp_path)
    with pytest.raises(SystemExit) as salida:
        biblioteca.main(["--help"], activa=p)
    assert salida.value.code == 0
    (p.PLANTA / "viento_local").mkdir(parents=True)
    (p.PLANTA / "viento_local" / "lidar.npz").write_bytes(Path(lidar).read_bytes())
    biblioteca.main(["--paso", "180"], activa=p)
    with np.load(tmp_path / "campos.npz") as z:
        assert z["u"].shape[0] == 2 and float(z["paso"]) == 180.0 and float(z["cx2"]) == 1140.0
    assert "2 direcciones" in capsys.readouterr().out


# ------------------------------------------------------------------------------ dónde está y qué dice de sí mismo
def test_no_es_un_motor():
    assert "viento_local" not in teodors.MOTORES and "modelo" not in teodors.MOTORES and "biblioteca" not in teodors.MOTORES
    assert linea_de_ordenes(["viento_local"]) == 1


@pytest.mark.parametrize("nombre", ["__init__.py", "modelo.py", "biblioteca.py", "README.md"])
def test_dice_arriba_que_no_esta_validado(nombre):
    inicio = (CARPETA / nombre).read_text(encoding="utf-8")[:900]
    assert "NO VALIDADO" in inicio
    assert "motores" in inicio


def test_readme_con_sus_ficheros_y_sin_datos_de_una_planta():
    texto = (CARPETA / "README.md").read_text(encoding="utf-8")
    for f in ("__init__.py", "modelo.py", "biblioteca.py"):
        assert f"`{f}`" in texto.split("## Ficheros")[1]
    for palabra in ("Dacame", "ENCE", "25831", "Montsià", "Santa Bàrbara"):
        assert palabra not in texto, palabra
    assert not re.search(r"\b\d{3}[  ]?\d{3}\b|\b\d[  ]?\d{3}[  ]?\d{3}\b", texto), "¿una coordenada en el README?"


def test_scipy_no_hace_falta_para_importarlo():
    # `test_paquete.test_importa` importa todo con solo el extra de pruebas: aquí se comprueba sin scipy de verdad
    r = subprocess.run([sys.executable, "-c", "import sys; sys.modules['scipy'] = None\n"
                        "import teodors.meteo.viento_local.modelo, teodors.meteo.viento_local.biblioteca\n"
                        "print('ok')"],
                       env=procesos.entorno(), capture_output=True, text=True, encoding="utf-8")
    assert r.returncode == 0, r.stderr
    assert r.stdout.strip() == "ok"


def test_se_instala_con_su_extra():
    pyproject = tomllib.loads((RAIZ / "pyproject.toml").read_text(encoding="utf-8"))
    assert "teodors.meteo.viento_local" in pyproject["tool"]["setuptools"]["packages"]
    extras = pyproject["project"]["optional-dependencies"]
    assert any(d.startswith("scipy") for d in extras["viento_local"])
    assert any(d.startswith("scipy") for d in extras["pruebas"])
    # el viento local no necesita laspy: lee rejillas ya hechas. Desde la tanda de las fuentes, solo lo trae el extra de leer el LiDAR
    assert [k for k, lista in extras.items() if any(d.startswith("laspy") for d in lista)] == ["lidar"]
    assert not any(d.startswith("scipy") for d in pyproject["project"]["dependencies"])
