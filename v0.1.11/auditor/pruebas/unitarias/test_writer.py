# -*- coding: utf-8 -*-
"""writer · el informe en PDF de un caso del reanálisis (usuario, 2026-11-10), con la planta inventada de test_operacion y casos hechos a mano:
los datos, los textos de cada situación (ningún pueblo por encima de 1 ou_E/m³, por encima de 1, de 3 o de 5; sin pueblos), las páginas con
uno o muchos focos y con planes constantes, semanales o de un mes, y el PDF. Las imágenes, que salen de la app, no se prueban aquí."""
import copy
import json
import os
import re
import subprocess
import sys
from importlib.util import find_spec
from pathlib import Path

import numpy as np
import pytest

from test_operacion import LAT, LON, _contorno, _foco, _guarda_respuestas, _guarda_serie, _planta, sin_red_y_con_planta  # noqa: F401  (la planta inventada)
from teodors import planta
from teodors.operacion import periodos, planes as E, simulacion as S
from teodors.writer import datos, informe
from teodors.writer.reanalisis_caso import textos, graficas   # el writer se dividió por tipos (v0.1.8): los textos y gráficos de un caso del reanálisis

con_qt = pytest.mark.skipif(find_spec("PySide6") is None, reason="sin teodors[pruebas_gui]")


def _caso(focos=None, esc=None, fin="2023-01-03", nombre="Prueba", valor=lambda i, t, r: 1e-3 * (r + 1)):
    """Un caso guardado: la serie (C = Q · valor en cada hora), el reanálisis con el plan y «Guardar resultados»."""
    focos = focos or [_foco("F01")]
    cat = {"focos": focos}
    _guarda_serie(focos, valor, fin=fin)
    esc = esc or E.nuevo(cat, "Plan de prueba")
    res = S.calcular(esc, cat)
    return S.guardar_caso(res, S.carpeta_caso(nombre), cat)["carpeta"], cat


def _texto(html):
    return re.sub(r"\s+", " ", re.sub("<[^>]+>", "", html))


def test_un_caso_guardado_lleva_lo_que_necesita_su_informe():
    carpeta, cat = _caso()
    r = Path(carpeta) / "resultados"
    assert {"lugares.json", "edificios_planta.json", "focos.json", "plan_operacion.json"} <= {p.name for p in r.iterdir()}
    lug = json.loads((r / "lugares.json").read_text(encoding="utf-8"))
    assert [e["nombre"] for e in lug["etiquetas"]] == ["Vecino", "Pueblo"] and len(lug["centro"]) == 2


def test_datos_y_lo_esencial_de_un_caso():
    carpeta, cat = _caso()
    d = datos.reunir(carpeta, viento=False)
    assert d["estadistico"] == "p98" and d["avisos"] == [] and d["terreno"] is None and d["viento"] is None
    assert [f["nombre"] for f in d["pueblos"]] == ["Pueblo"] and d["pueblos"][0]["p98"] == pytest.approx(6.0, rel=0.04)    # C = r + 1, r = 5
    assert d["vivienda"]["p98"] == pytest.approx(16.0, rel=0.04)
    assert [c["pueblos"] for c in d["criterios"]] == [1, 1, 1] and d["criterios"][0]["hasta_km"] > 0
    op = d["operacion"]
    assert op["constante"] and op["media"] == pytest.approx(1.0) and op["anio"] == 2023 and op["q"] == pytest.approx(1000.0)
    t = {k: _texto(v) for k, v in textos.esencial(d).items()}
    assert t["que"].startswith("El caso «") and "del 1/1/2023 al 3/1/2023" in t["que"] and "funciona siempre así" in t["que"]
    assert t["pueblos"].startswith("1 pueblo pasa de 5 ou_E/m³ de P98, el menos exigente") and "podría molestar en él" in t["pueblos"]
    assert "La vivienda más expuesta" in t["alcance"] and "por encima de 5 ou_E/m³" in t["alcance"]
    assert t["gases"].endswith("sin el olor de fondo de la zona.")


@pytest.mark.parametrize("p98, empieza", [(0.17, "Ningún pueblo pasa de 1 ou_E/m³"), (1.7, "1 pueblo pasa de 1 ou_E/m³ de P98, el más exigente"),
                                          (4.0, "1 pueblo pasa de 3 ou_E/m³ de P98, el intermedio"), (17.0, "1 pueblo pasa de 5 ou_E/m³ de P98")])
def test_lo_esencial_dice_cada_situacion(p98, empieza):
    carpeta, _ = _caso()
    d = datos.reunir(carpeta, viento=False)
    d["pueblos"][0].update(p98=p98)
    for c in d["criterios"]:
        c["pueblos"] = int(p98 > c["umbral"])
    t = _texto(textos.esencial(d)["pueblos"])
    assert t.startswith(empieza), t
    sin = copy.copy(d)
    sin["pueblos"] = []
    assert _texto(textos.esencial(sin)["pueblos"]).startswith("En la zona de cálculo no hay pueblos")


def test_lo_esencial_dice_tambien_la_peor_hora_de_los_pueblos():
    # usuario, 2026-11-10: «aunque indique que el P98 cumple, también se ve que algún día llegó a umbrales de molestia»
    carpeta, _ = _caso()
    d = datos.reunir(carpeta, viento=False)
    assert [(c["pueblos"], c["pueblos_maximo"]) for c in d["criterios"]] == [(1, 1), (1, 1), (1, 1)]
    assert "Pero el P98" not in _texto(textos.esencial(d)["pueblos"])          # los mismos que por el P98: no hace falta
    assert "<div class='v'>1 · 1 · 1</div><div class='t'>pueblos con máximo horario &gt; 1 · 3 · 5 ou_E/m³</div>" in informe.crear(d).html()
    d["pueblos"][0].update(p98=0.17, maximo=6.0)                                # el P98 no llega a 1, pero su peor hora, a 6
    for c in d["criterios"]:
        c["pueblos"] = 0
    assert _texto(textos.esencial(d)["pueblos"]).endswith(
        "Pero el P98 deja fuera el 2 % de las horas más altas, unas 175 al año: en su peor hora, 1 pueblo pasa de 1 ou_E/m³ (Pueblo, 6,0), 1 de 3 "
        "y 1 de 5: aunque su P98 no pase de 1, algún día el olor puede llegar a notarse en él.")
    d["pueblos"][0].update(maximo=0.5)
    assert _texto(textos.esencial(d)["pueblos"]).endswith("Ni en su peor hora del reanálisis pasa ningún pueblo de 1 ou_E/m³.")


def test_la_pagina_de_la_operacion_lo_cuenta_con_texto():
    # usuario, 2026-11-10: «en la página 7 queda espacio por rellenar… texto narrativo»; sale de los datos, para cualquier plan
    carpeta, _ = _caso()
    d = datos.reunir(carpeta, viento=False)
    t = {k: _texto(v) for k, v in textos.operacion(d)}
    assert list(t) == ["Cómo funciona la planta con este plan", "Quién emite el olor", "Cómo entra en el cálculo", "De dónde sale el olor de cada foco"]
    assert t["Cómo funciona la planta con este plan"].startswith("El foco funciona las 24 horas, todos los días del año, al 100 %")
    assert t["Quién emite el olor"] == ("Foco F01 lo da todo: sale a poca altura (hasta 3,0 m), sin la elevación ni el empuje de una chimenea, y su olor "
                                       "suele ser el que más pesa en los receptores cercanos.")
    assert "a las 72 horas del reanálisis (2023): en cada hora" in t["Cómo entra en el cálculo"]
    assert t["De dónde sale el olor de cada foco"] == "El olor del foco es el medido por olfatometría, en ou_E."
    assert "<div class='narra'><p><b>Cómo funciona la planta con este plan.</b>" in informe.crear(d).html()
    # un plan que cambia: de lunes a viernes, de 8 a 14 h al 100 % y el resto al 20 %; el fin de semana, al 20 %
    focos = [_foco("F01"), _foco("F02", q=3000.0)]
    cat = {"focos": focos}
    esc = E.nuevo(cat, "Turnos")
    pf = E.plan_foco(focos[1], esc)
    E.cambiar_plan(pf, "semanal")
    E.poner_perfil(pf, range(5), [1.0 if 8 <= h < 14 else 0.2 for h in range(24)])
    E.poner_perfil(pf, (5, 6), [0.2] * 24)
    carpeta, _ = _caso(focos, esc, nombre="Turnos")
    t = _texto(dict(textos.operacion(datos.reunir(carpeta, viento=False)))["Cómo funciona la planta con este plan"])
    assert "En su día medio, lo más es de 8 a 14 h" in t and "y lo menos, de 14 a 8 h" in t and "De lunes a viernes, el " in t, t
    assert "Cambia el plan de un foco: foco F02 (semanal); el del otro, siempre igual." in t, t
    # un foco parado todo el año
    esc = E.nuevo(cat, "Sin el grande")
    E.poner_perfil(E.plan_foco(focos[1], esc), [0], [0.0] * 24)
    carpeta, _ = _caso(focos, esc, nombre="Sin el grande")
    t = {k: _texto(v) for k, v in textos.operacion(datos.reunir(carpeta, viento=False))}
    assert t["Cómo funciona la planta con este plan"].endswith("todos los días del año: foco F02, sin emitir; el otro, al 100 %."), t
    assert t["Quién emite el olor"] == ("Todo el olor que emite la planta con el plan sale del foco de volumen (foco F01). Sale a poca altura (hasta "
                                       "3,0 m), sin la elevación ni el empuje de una chimenea, y su olor suele ser el que más pesa en los receptores cercanos."), t
    # un plan de un mes
    f = _foco("F01")
    esc = E.nuevo({"focos": [f]}, "Enero")
    esc["mes"] = "2023-01"
    pf = E.plan_foco(f, esc)
    E.cambiar_plan(pf, "mensual", "2023-01")
    E.poner_perfil(pf, range(24, 31), [0.0] * 24)                            # parado la última semana
    carpeta, _ = _caso([f], esc, nombre="Enero")
    t = _texto(dict(textos.operacion(datos.reunir(carpeta, viento=False)))["Cómo funciona la planta con este plan"])
    assert "todos los días de enero (el plan es de un mes: los demás no cuentan)" in t and t.endswith("Por días, el 100 %, salvo del 25 al 31 de enero (0 %)."), t


def test_las_paginas_con_un_foco_y_sin_imagenes():
    carpeta, _ = _caso()
    d = datos.reunir(carpeta, viento=False)
    html = informe.crear(d).html()
    assert html.count("<section class='pag") == 10             # portada, lo esencial, relieve y usos, lugares, 3D, fichas, operación ×2, resultados ×2
    t = _texto(html)
    assert "Sin imagen: resultado zona" in t and "no tiene el terreno descargado" in t and "El foco de olor" in t
    assert "Informe de dispersión de olores · reanálisis 2023–2023" in t and "1 foco" in t
    assert "100 % de lo que emitiría con todos los focos al 100 %, igual todos los días" in t and "100 % siempre" in t
    assert [n for n in re.findall(r"<span>(\d+)</span></div></section>", html)] == [str(k) for k in range(2, 11)]   # el pie, de la 2 a la 10
    con = informe.crear(d, {"resultado_entorno": "resultado_entorno.jpg", "foco_F01": "foco_F01.jpg"}).html()
    assert "img/resultado_entorno.jpg" in con and "img/foco_F01.jpg" in con


def test_muchos_focos_y_planes_que_cambian_siguen_en_otras_paginas():
    focos = [dict(_foco(f"F{k:02d}", q=100.0 * (k + 1)), nombre=f"Foco {k}") for k in range(10)]
    cat = {"focos": focos}
    esc = E.nuevo(cat, "Volteos")
    pf = E.plan_foco(focos[0], esc)
    E.cambiar_plan(pf, "semanal")
    E.poner_perfil(pf, range(5), [1.0 if 8 <= h < 14 else 0.2 for h in range(24)])
    E.poner_perfil(pf, (5, 6), [0.2] * 24)
    carpeta, _ = _caso(focos, esc)
    d = datos.reunir(carpeta, viento=False)
    op = d["operacion"]
    assert not op["constante"] and op["tipos"] == {"semanal": 1, "diario": 9} and len(op["focos"]) == 10
    f0 = next(f for f in op["focos"] if f["id"] == "F00")
    assert [w for w, _ in f0["semana"]] == list(range(7)) and f0["semana"][0][1][8] == 1.0 and f0["semana"][6][1][8] == 0.2
    assert f0["media"] == pytest.approx((5 * (6 + 18 * 0.2) / 24 + 2 * 0.2) / 7, rel=0.02)
    html = informe.crear(d).html()
    t = _texto(html)
    assert html.count("<section class='pag") == 13            # 3D: 8 + 2 más; fichas y operación de cada foco: 8 + 2; resultados ×2
    assert t.count("(sigue)") == 3 and "10 focos" in t and "con cambios a lo largo del día o de la semana" in _texto(textos.esencial(d)["que"])


def test_un_pueblo_que_anade_la_planta_sale_en_un_caso_ya_guardado():
    # usuario, 2026-11-10: un pueblo cerca de la planta no salía (CORINE no lo tiene como núcleo); se añade en planta.json y el caso guardado
    # lo da al leerlo, con el peor de sus receptores, sin volver a calcular
    from teodors.operacion import pueblos as P
    from teodors.planta import geo
    carpeta, _ = _caso()
    assert [f["nombre"] for f in datos.reunir(carpeta, viento=False)["pueblos"]] == ["Pueblo"]
    xc, yc = geo.a_utm(LAT, LON)
    _planta(planta.PLANTA, pueblos={"lista": [{"nombre": "Cerca", "contorno": [_contorno(xc + 550, xc + 950, yc + 550, yc + 650)]}]})
    d = datos.reunir(carpeta, viento=False)                      # receptores 10 y 11: C = r + 1, el peor, 12
    assert [f["nombre"] for f in d["pueblos"]] == ["Cerca", "Pueblo"] and d["pueblos"][0]["p98"] == pytest.approx(12.0, rel=0.04)
    r = Path(carpeta) / "resultados"
    res = json.loads((r / "resultado.json").read_text(encoding="utf-8"))
    assert res["pueblos"] == P.firma() and "Cerca" in [f["nombre"] for f in res["magnitudes"]["olor"]["filas"]]
    assert json.loads((r / "lugares.json").read_text(encoding="utf-8"))["pueblos"] == P.firma()
    assert _texto(textos.esencial(d)["pueblos"]).startswith("2 pueblos pasan de 5 ou_E/m³ de P98")


def test_un_plan_fijo_por_debajo_del_100_no_dice_que_cambia():
    # con el escenario de las balsas al 50 % decía «con cambios a lo largo del día o de la semana», y el reparto era el de todos al 100 %
    focos = [_foco("F01"), _foco("F02", q=3000.0)]
    cat = {"focos": focos}
    esc = E.nuevo(cat, "Balsa a la mitad")
    E.poner_perfil(E.plan_foco(focos[1], esc), [0], [0.6] * 24)
    carpeta, _ = _caso(focos, esc)
    d = datos.reunir(carpeta, viento=False)
    assert d["operacion"]["constante"] and not d["operacion"]["al_100"]
    t = _texto(textos.esencial(d)["que"])
    assert "con todos al 100 %; con este plan, emiten el 70 % (2 800 ou_E/s), igual todas las horas: foco F02, al 60 %." in t, t
    assert t.endswith("Foco F02 da el 64 % del olor con el plan."), t


def test_un_plan_de_un_mes_raya_los_demas():
    f = _foco("F01")
    cat = {"focos": [f]}
    esc = E.nuevo(cat, "Enero")
    esc["mes"] = "2023-01"
    E.cambiar_plan(E.plan_foco(f, esc), "mensual", "2023-01")
    carpeta, _ = _caso([f], esc)
    d = datos.reunir(carpeta, viento=False)
    op = d["operacion"]
    assert op["mes"] == 1 and all((v is None) == (fecha.month != 1) for fecha, v in op["dias"])
    assert set(op["focos"][0]["meses"]) == {1}
    t = _texto(informe.crear(d).html())
    assert "El plan es de ene: los demás meses no cuentan (rayados)." in t


def _serie_viento():
    """Tres días de viento en la planta: el 1, del S a 1 m/s; el 2, del ONO las 24 horas (2 m/s; a las 10, 2,5); el 3, del ONO a 3 m/s por la
    mañana, calma por la tarde y, a las 15, 9 m/s del NO."""
    horas, ws, wd = [], [], []
    for dia, viento in (("2023-03-01", lambda h: (1.0, 180.0)), ("2023-03-02", lambda h: (2.5 if h == 10 else 2.0, 292.5)),
                        ("2023-03-03", lambda h: (9.0, 315.0) if h == 15 else (3.0, 292.5) if h < 12 else (0.2, 90.0))):
        for h in range(24):
            horas.append(f"{dia} {h:02d}")
            v, d = viento(h)
            ws.append(v)
            wd.append(d)
    return horas, ws, wd


def _meteo_inventada():
    rosa = [[0.0] * 5 for _ in range(16)]
    rosa[13] = [4.0, 6.0, 3.0, 1.0, 0.5]
    estacion = lambda c, n, km, s, calmas, fuerte: {"codigo": c, "nombre": n, "km": km, "desde_planta": "NO", "altitud": 100.0, "altura": 10.0,
                                                    "horas": 43000, "desde": "2021", "hasta": "2025", "obs": rosa, "calmas": calmas,
                                                    "dominante": s, "dominante_grados": E_RUMBOS.index(s) * 22.5, "dominante_pct": 20.0, "fuerte": fuerte}
    return {"serie": "s", "titulo": "Serie", "eventos": datos.eventos_viento(*_serie_viento()),
            "planta": {"desde": "2021-01-01", "hasta": "2025-12-31", "horas": 43824, "rosa": rosa, "clases": [0.5, 2.0, 4.0, 6.0, 8.0],
                       "calmas": 9.2, "media": 1.85, "maxima": 11.9, "dominante": "ONO", "dominante_pct": 17.7},
            "estaciones": {"clases": [0.5, 2.0, 4.0, 6.0, 8.0], "lista": [estacion("A1", "Estación A", 5.0, "ONO", 3.0, 2.9),
                                                                              estacion("B2", "Estación B", 12.0, "SE", 44.0, 0.1)]}}


E_RUMBOS = ("N", "NNE", "NE", "ENE", "E", "ESE", "SE", "SSE", "S", "SSO", "SO", "OSO", "O", "ONO", "NO", "NNO")


def test_la_meteorologia_del_reanalisis_las_rosas_y_las_situaciones():
    # usuario, 2026-11-10: «las rosas de los vientos de todas las estaciones… imágenes de vientos global y local… para el evento más
    # frecuente y el más extremo… que writer automatice describir esa información»; luego, «pon los dos escenarios más frecuentes y el
    # más intenso»
    ev = datos.eventos_viento(*_serie_viento())
    (f, g), x = ev["frecuentes"], ev["extremo"]
    assert (f["dia"], f["h"], f["ws"], f["rumbo"], f["rumbo_dominante"], f["horas_dia"], f["tipica"]) == ("2023-03-02", 0, 2.0, "ONO", "ONO", 24, 2.0)
    assert f["pct"] == pytest.approx(36 / 61 * 100) and (x["hora"], x["ws"], x["rumbo"]) == ("2023-03-03 15", 9.0, "NO")
    assert (g["dia"], g["h"], g["ws"], g["rumbo_dominante"], g["horas_dia"], g["tipica"]) == ("2023-03-01", 0, 1.0, "S", 24, 1.0)
    assert g["pct"] == pytest.approx(24 / 61 * 100)
    assert [c for c, _, _ in textos.situaciones(ev)] == ["frecuente1", "frecuente2", "extremo"]
    assert [t for _, t, _ in textos.situaciones(ev)] == ["La más frecuente", "La segunda más frecuente", "La más extrema"]
    # sin repetir día: el ONO y el S soplan más el mismo día (el 1: 14 y 10 horas); el S, otro día (el 2, 8 horas)
    horas, ws, wd = [], [], []
    for dia, viento in (("2023-03-01", lambda h: (2.0, 292.5) if h < 14 else (1.5, 180.0)), ("2023-03-02", lambda h: (1.5, 180.0) if h < 8 else (0.1, 0.0)),
                        ("2023-03-03", lambda h: (2.0, 292.5) if h < 10 else (0.1, 0.0))):
        for h in range(24):
            horas.append(f"{dia} {h:02d}")
            ws.append(viento(h)[0])
            wd.append(viento(h)[1])
    ev2 = datos.eventos_viento(horas, ws, wd)
    assert [(e["rumbo_dominante"], e["dia"], e["horas_dia"]) for e in ev2["frecuentes"]] == [("ONO", "2023-03-01", 14), ("S", "2023-03-02", 8)]
    assert len(datos.eventos_viento(*_serie_viento(), frecuentes=1)["frecuentes"]) == 1
    assert datos.eventos_viento(["2023-03-01 00"], [0.1], [10.0]) is None                  # todo calma
    assert textos.hora_local("2023-03-02 00") == ("2/3/2023", "1:00") and textos.hora_local("2023-07-02 00") == ("2/7/2023", "2:00")
    carpeta, _ = _caso()
    d = datos.reunir(carpeta, viento=False)
    assert d["meteo"] is None and informe.crear(d).html().count("<section class='pag") == 10        # sin viento, sin meteorología
    d["meteo"] = _meteo_inventada()
    t = {k: _texto(v) for k, v in textos.meteo_estaciones(d)}
    assert t["El viento en la planta"].startswith("El viento del reanálisis (2021–2025, el de la capa más baja del viento 3D) sopla en la "
                                                  "planta sobre todo del ONO: el 18 % de las horas con viento.")
    assert t["El viento en la planta"].endswith("La estación más cercana, Estación A, a 5,0 km al NO, lo mide sobre todo del ONO: como en la planta.")
    assert "El más frecuente sopla en Estación A, del NO; y en Estación B, del SE." in t["El viento en las estaciones"]
    assert "Las calmas van del 3 % de las horas en Estación A al 44 % en Estación B, la más resguardada" in t["El viento en las estaciones"]
    t = {k: _texto(v) for k, v in textos.meteo_situaciones(d)}
    assert t["Arriba, las dos más frecuentes"] == (
        "El viento del ONO es el que más sopla en la planta (59 % de las horas con viento, con 2,0 m/s de velocidad típica); después, el del S "
        "(39 %, 1,0 m/s). El 2/3/2023 sopló del ONO 24 de las 24 horas, y el 1/3/2023, del S, 24; en los mapas, a la 1:00 (2,0 m/s) y a la 1:00 "
        "(1,0 m/s). Entre los dos, el 98 % de las horas con viento: lo más habitual es que el olor de la planta vaya hacia el SE o el N. El del "
        "ONO sopla más fuerte y diluye antes el olor; con el del S, más flojo, llega más concentrado.")
    assert t["Abajo, la más extrema"].startswith("La hora de más viento en la planta en 2021–2025: el 3/3/2023 a las 16:00, 9,0 m/s del NO.")
    html = informe.crear(d).html()
    assert html.count("<section class='pag") == 12 and "3 · Meteorología" in _texto(html)
    assert "El viento en el mapa: las dos situaciones más frecuentes y la más extrema" in _texto(html)
    assert "La segunda más frecuente · 1/3/2023, 1:00 · 1,0 m/s del S en la planta" in _texto(html)
    assert [n for n in re.findall(r"<span>(\d+)</span></div></section>", html)] == [str(k) for k in range(2, 13)]     # detrás de todo
    assert "Sin imagen: rosa planta" in _texto(html) and "Sin imagen: viento extremo planta" in _texto(html)
    assert "Sin imagen: viento frecuente2 zona" in _texto(html)
    con = informe.crear(d, {"rosa_A1": "rosa_A1.svg", "viento_frecuente1_zona": "viento_frecuente1_zona.jpg"}).html()
    assert "img/rosa_A1.svg" in con and "img/viento_frecuente1_zona.jpg" in con
    # con una sola frecuente (un solo rumbo con viento), como antes
    d["meteo"]["eventos"] = dict(d["meteo"]["eventos"], frecuentes=d["meteo"]["eventos"]["frecuentes"][:1])
    t = {k: _texto(v) for k, v in textos.meteo_situaciones(d)}
    frase = "El 2/3/2023 sopló así 24 de las 24 horas; a la 1:00, 2,0 m/s del ONO. Es la situación más habitual: el olor de la planta va hacia el SE."
    assert frase in t["Arriba, la más frecuente"]
    assert "El viento en el mapa: la situación más frecuente y la más extrema" in _texto(informe.crear(d).html())


def _era5_inventado():
    """Dos años de ERA5 y de viento en la planta, en UTC, hechos para que salgan cifras redondas: de 9 a 16 h, sol, mezcla a 800 m, u* 0,3 y
    viento del SSE a 3 m/s; el resto, aire estable (calor hacia abajo), mezcla a 100 m, u* 0,1 y viento flojo del ONO (1 m/s). 20 °C, salvo
    -5 °C el 10/1/2022 a las 6 y 35 °C el 15/7/2023 a las 14; 1000 hPa, salvo 970 el 3/3/2022 a las 3; lluvia el día 1 de cada mes a las 12
    (5 mm en 2022, 1 mm en 2023); nubes al 10 % en 2022 y al 90 % en 2023."""
    import pandas as pd
    t = pd.date_range("2022-01-01 00:00", "2023-12-31 23:00", freq="h")
    dia = (t.hour >= 9) & (t.hour <= 16)
    t2m = np.full(len(t), 20.0)
    t2m[t == pd.Timestamp("2022-01-10 06:00")] = -5.0
    t2m[t == pd.Timestamp("2023-07-15 14:00")] = 35.0
    sp = np.full(len(t), 1000.0)
    sp[t == pd.Timestamp("2022-03-03 03:00")] = 970.0
    tp = np.where((t.day == 1) & (t.hour == 12), np.where(t.year == 2022, 5.0, 1.0), 0.0)
    sfc = pd.DataFrame({"time": t, "t2m": t2m, "d2m": t2m, "tcc": np.where(t.year == 2022, 0.1, 0.9), "ssrd": np.where(dia, 500.0, 0.0),
                        "sshf": np.where(dia, -100.0, 20.0), "blh": np.where(dia, 800.0, 100.0), "zust": np.where(dia, 0.3, 0.1), "sp": sp,
                        "tp": tp})
    horas = [x.strftime("%Y-%m-%d %H") for x in t]
    return sfc, horas, np.where(dia, 3.0, 1.0), np.where(dia, 157.5, 292.5)


def test_el_tiempo_en_la_planta_dia_a_dia_con_su_texto_final():
    # usuario, 2026-11-10: «gráficas de los valores medios por día de estos 5 años de… todas las variables del ERA5… y un texto final
    # describiendo toda esta meteo, narrativa»
    c = datos.clima(*_era5_inventado())
    assert len(c["dias"]) == 730 and str(c["dias"][0]) == "2022-01-01" and str(c["dias"][-1]) == "2023-12-31"
    assert set(c["series"]) == {"viento", "direccion", "temperatura", "humedad", "nubes", "lluvia", "radiacion", "presion", "friccion", "calor",
                                "mezcla"}
    assert all(len(s["v"]) == 730 for s in c["series"].values()) and c["series"]["humedad"]["v"][0] == pytest.approx(100.0)
    assert c["series"]["lluvia"]["v"][0] == 5.0 and c["series"]["temperatura"]["min"][9] == -5.0
    r = c["resumen"]
    assert r["lluvia"]["por_anio"] == {2022: 60.0, 2023: 12.0} and r["lluvia"]["dias_anio"] == 12 and r["lluvia"]["max_dia"] == "1/1/2022"
    assert (r["t"]["min"], r["t"]["min_dia"], r["t"]["max"], r["t"]["max_dia"]) == (-5.0, "10/1/2022", 35.0, "15/7/2023")
    assert r["presion"]["min_dia"] == "3/3/2022" and r["nubes"]["despejados"] == pytest.approx(50.0, abs=0.2)
    m = r["mezcla"]
    assert [m["dia"], m["noche"], m["friccion_dia"], m["friccion_noche"], m["estable_noche"]] == pytest.approx([800.0, 100.0, 0.3, 0.1, 100.0])
    v = r["viento"]
    assert (v["dom_noche"]["rumbo"], v["dom_dia"]["rumbo"], v["noche"], v["dia"]) == ("ONO", "SSE", 1.0, 3.0)
    assert r["dificil"]["pct"] == pytest.approx(100 * 16 / 24, abs=0.1) and r["dificil"]["dominante"]["rumbo"] == "ONO"
    assert datos.clima(None, [], [], []) is None
    # el texto final y lo que dice cada gráfica
    carpeta, _ = _caso()
    d = datos.reunir(carpeta, viento=False)
    d["meteo"] = dict(_meteo_inventada(), era5=dict(c, punto={"lat": 40.75, "lon": 0.5, "dist_planta_m": 6900.0, "rumbo_desde_planta": "N",
                                                              "cota_modelo_m": 267.0}))
    t = {k: _texto(h) for k, h in textos.meteo_clima(d)}
    assert list(t) == ["El tiempo en la planta", "El viento, de día y de noche", "La mezcla del aire", "Lo que más pesa para el olor"]
    assert t["El tiempo en la planta"].startswith("Según el ERA5, en su celda más cercana a la planta (a 6,9 km al N, con el suelo del modelo "
                                                  "a 267 m), en 2022–2023 la temperatura media es de 20,0 °C")
    assert "pero cambia mucho de un año a otro: 12 mm en 2023 y 60 mm en 2022; el día de más lluvia, el 1/1/2022, 5 mm." in t["El tiempo en la planta"]
    assert "sobre todo del ONO (100 % de esas horas con viento), y de día (de 11 a 17 h), del SSE (100 %): gira con el día" in t["El viento, de día y de noche"]
    assert "se mezcla hasta unos 800 m de altura" in t["La mezcla del aire"] and "la capa de mezcla baja a unos 100 m" in t["La mezcla del aire"]
    assert t["Lo que más pesa para el olor"].endswith("el olor de la planta va entonces hacia el ESE.")
    cifras = textos.clima_cifras(r)
    assert cifras["lluvia"] == "36 mm al año · 12 días de lluvia al año" and cifras["direccion"] == "de noche, sobre todo del ONO; de día, del SSE"
    # las gráficas
    assert graficas.pasos(-0.9, 36.3) == [-10, 0, 10, 20, 30, 40] and graficas.decimales([0, 0.25, 0.5]) == 2
    mm = graficas.media_movil([1.0, 1.0, np.nan, 3.0], n=2)
    assert mm[0] == 1.0 and np.isfinite(mm).all()
    s = c["series"]["temperatura"]
    svg = graficas.diaria(c["dias"], s["v"], s["min"], s["max"], titulo="Temperatura")
    assert svg.startswith("<svg class='grafica'") and "<polygon" in svg and "aria-label='Temperatura'" in svg and ">2023<" in svg
    assert "<circle" in graficas.diaria(c["dias"], c["series"]["direccion"]["v"], forma="rumbos")
    # la página: tras las del viento en el mapa; las estaciones, con su código
    html = informe.crear(d).html()
    assert html.count("<section class='pag") == 13 and "El tiempo en la planta, día a día" in _texto(html) and "Cómo se leen" in _texto(html)
    assert "<span class='cod'>A1</span>" in html and "Sin imagen: estaciones" in _texto(html)
    assert _texto(html).index("El viento en el mapa") < _texto(html).index("El tiempo en la planta, día a día")


def test_los_resultados_los_mapas_del_olor_y_cuando_se_huele_en_los_pueblos():
    # usuario, 2026-11-10: los mapas del olor (media, máximo y P98) y «cuándo se huele en cada pueblo: horas al año por encima de 1, 3 y 5
    # ou_E/m³, por mes y por hora del día, y los peores días con su viento»; la hora a hora, guardada al simular
    from teodors.operacion import simulacion as S
    carpeta, _ = _caso(valor=lambda i, t, r: 1e-3 * (r + 1) if t < 6 else 1e-5)        # de 0 a 5 h (UTC), (r + 1) ou_E/m³; el resto, casi nada
    d = datos.reunir(carpeta, viento=False)
    assert set(d["alcances"]) == {"media", "maximo", "p98"} and all(len(a) == 3 for a in d["alcances"].values())
    assert d["alcances"]["maximo"][0]["km2"] >= d["alcances"]["p98"][0]["km2"] >= d["alcances"]["media"][0]["km2"]
    h = d["horas"]
    nombres = {f["nombre"]: f for f in h["lugares"]}
    assert set(nombres) == {"Pueblo", "Peor vivienda (< 1.5 km)"} and nombres["Pueblo"]["tipo"] == "pueblo"
    p = nombres["Pueblo"]
    assert p["horas"][0] == pytest.approx(6 * 3 / h["anios"]) and p["dias"] == pytest.approx(3 / h["anios"])   # 3 días, 6 horas cada uno
    assert p["peor"]["valor"] == pytest.approx(next(f for f in d["res"]["magnitudes"]["olor"]["filas"] if f["nombre"] == "Pueblo")["maximo"], rel=1e-5)
    assert h["todos"]["noche"] == 100.0 and sum(map(sum, h["calor"][0]["M"])) == pytest.approx(p["horas"][0])
    assert len(h["peores"]) == 4 and h["peores"][0]["pueblo"] == "Pueblo" and h["peores"][0]["horas"] == 6 and h["peores"][0]["ws"] is None
    t = {k: _texto(v) for k, v in textos.cuando(d)}
    assert t["Cuántas horas"].startswith("En Pueblo (a ") and "casi siempre de noche (el 100 %, de 20 a 8 h)" in t["Cuándo"]
    assert t["Los peores días"].startswith(f"El peor día, el {h['peores'][0]['dia']}: ")
    t = {k: _texto(v) for k, v in textos.resultados_mapas(d)}
    assert list(t) == ["Media", "Máximo horario", "P98", "Cómo se leen"] and t["P98"].startswith("El P98, lo que se pasa el 2 % de las horas")
    html = informe.crear(d).html()
    assert "El olor en el mapa: la media, el máximo y el P98" in _texto(html) and "Cuándo se huele en los pueblos" in _texto(html)
    assert "Sin imagen: resultado media zona" in _texto(html) and html.count("<svg class='grafica calor'") == 1
    # un caso calculado antes de guardar la hora a hora: los mapas sí, cuándo se huele no, y el aviso
    (Path(carpeta) / "resultados" / "olor" / S.HORAS_PUEBLOS).unlink()
    d = datos.reunir(carpeta, viento=False)
    html = informe.crear(d).html()
    assert d["horas"] is None and "El olor en el mapa" in _texto(html) and "Cuándo se huele" not in _texto(html)
    assert any("vuelve a calcularlo" in a for a in d["avisos"])


def test_al_guardar_un_caso_su_informe_se_hace_en_otro_proceso(monkeypatch, tmp_path):
    # usuario, 2026-11-10: «le damos a guardar, se guarda el caso en la carpeta reanálisis con los resultados y el informe»
    from teodors.writer import informe
    lanzado = {}

    class Proceso:
        def __init__(self, orden, **k):
            lanzado.update(orden=orden, camino=os.environ.get("PYTHONPATH"), **k)
            self.stdout = iter(["  1 % Reuniendo los datos del caso…\n", "Warning 3: GDAL\n", " 52 % Las estaciones…\n",
                                f"Informe: {tmp_path / 'caso.pdf'}\n"] if "bien" in orden[-3] else ["Traceback…\n", "ValueError: roto\n"])
            self.returncode = None

        def wait(self):
            self.returncode = 0 if "bien" in lanzado["orden"][-3] else 1
    monkeypatch.setattr(informe.subprocess, "Popen", Proceso)
    # la app abierta con su lanzador tiene teOdors en su camino de Python, no en el entorno (usuario, 2026-11-10: «sale que no pudo hacer el
    # informe», «No module named 'teodors'»): el hijo lo hereda solo mientras se lanza
    from teodors.comun import procesos
    monkeypatch.delenv("PYTHONPATH", raising=False)
    pasos = []
    assert informe.lanzar(tmp_path / "bien", lambda p, m: pasos.append((p, m))) == {"pdf": str(tmp_path / "caso.pdf")}
    assert pasos == [(1, "Reuniendo los datos del caso…"), (52, "Las estaciones…")]
    assert lanzado["orden"][-4:] == ["teodors.writer.informe", str(tmp_path / "bien"), "--planta", str(planta.PLANTA)] and "env" not in lanzado
    assert lanzado["camino"] == procesos.entorno()["PYTHONPATH"] and "PYTHONPATH" not in os.environ
    monkeypatch.setenv("PYTHONPATH", "antes")
    informe.lanzar(tmp_path / "bien")
    assert os.environ["PYTHONPATH"] == "antes"
    with pytest.raises(RuntimeError, match="ValueError: roto"):
        informe.lanzar(tmp_path / "mal")
    lanzado.clear()                                              # la comparación: los dos casos, la referencia primero
    with pytest.raises(RuntimeError):
        informe.lanzar(tmp_path / "a", otro=tmp_path / "mal")
    assert lanzado["orden"][-5:] == ["teodors.writer.informe", str(tmp_path / "a"), str(tmp_path / "mal"), "--planta", str(planta.PLANTA)]


def test_el_informe_de_la_comparacion_de_dos_escenarios():
    # usuario, 2026-11-10: «mantener la estructura del informe de las cosas en común (lugar, pueblos, focos, meteo) y comparar la operabilidad
    # entre los dos casos, luego sacar el informe de resultados individual de cada uno y por último una última página comparativa»
    from teodors.writer.reanalisis_comparacion import graficas, textos as textos_comp   # los textos y gráficos de la comparación (su subcarpeta)
    focos = [_foco("F01"), _foco("F02", q=3000.0)]
    cat = {"focos": focos}
    valor = lambda i, t, r: 1e-3 * (r + 1) if t < 6 else 1e-5                       # noqa: E731
    base = E.nuevo(cat, "Base")
    carpeta_a, _ = _caso(focos, base, nombre="Base", valor=valor)
    mitad = E.nuevo(cat, "Mitad")
    E.poner_perfil(E.plan_foco(focos[1], mitad), [0], [0.5] * 24)
    carpeta_b, _ = _caso(focos, mitad, nombre="Mitad", valor=valor)
    dc = datos.reunir_comparacion(carpeta_a, carpeta_b, viento=False)
    op = dc["op"]
    assert op["cambian"] == ["F02"] and op["a"]["emite"] == pytest.approx(4000.0) and op["b"]["emite"] == pytest.approx(2500.0)
    assert [f["id"] for f in op["focos"]] == ["F02", "F01"] and op["focos"][1]["igual"] and op["focos"][0]["b"] == pytest.approx(0.5)
    assert dc["comp"]["orden"] == ["olor"] and dc["receptores"]["bajan"] > 99 and dc["receptores"]["suben"] == 0
    t = {k: _texto(v) for k, v in textos_comp.operacion_comparada(dc)}
    assert t["Lo que emite la planta"].endswith("con «Mitad», 2 500 ou_E/s (el 62 %): un 38 % menos que con «Base».")
    assert t["Qué cambia"] == "Cambia foco F02, del 100 % al 50 % de media. El otro foco opera igual en los dos."
    assert t["Cuánto pesa"].startswith("Con «Base», ese foco da el 75 % del olor que emite la planta")
    t = {k: _texto(v) for k, v in textos_comp.comparacion(dc)}
    assert set(t) == {"En la zona", "En los pueblos", "Las horas al año"} and "Pueblo, el P98 pasa de " in t["En los pueblos"]
    html = informe.crear(dc).html()
    texto = _texto(html)
    assert html.count("<section class='pag") == 12          # portada, lugar ×2, 3D, fichas, operación, el foco que cambia, resultados A ×2 y B ×2, comparación
    for frase in ("Informe de comparación de escenarios", "La operación: «Base» frente a «Mitad»", "Los focos que cambian",
                  "4 · Resultados de A · Base", "5 · Resultados de B · Mitad", "6 · Comparación", "De «Base» a «Mitad»",
                  "informe de la comparación de dos escenarios del reanálisis"):
        assert frase in texto, frase
    assert "Sin imagen: a resultado p98 zona" in texto and "Sin imagen: b resultado p98 zona" in texto and "Sin imagen: cambio zona" in texto
    assert html.count("<svg class='grafica dia2'") == 1 and graficas.COLOR_A in html and graficas.COLOR_B in html
    assert informe.nombre_comparacion(dc) == f"{dc['hoy']:%Y-%m-%d}-Base frente a Mitad"
    assert informe.ruta_pdf_comparacion(dc).parent == planta.DIR_CASOS / "reanalisis" / "comparaciones"
    with pytest.raises(ValueError, match="mismo escenario"):
        datos.reunir_comparacion(carpeta_a, carpeta_a, viento=False)


def test_comprobar_la_herramienta_monta_el_informe_del_ultimo_caso():
    # usuario, 2026-11-10: «que el writer funcione también debería ser una de las comprobaciones de la herramienta»
    from teodors.operacion import comprobar as C
    assert C._informe() == ([], "Su motor está (aún no hay casos guardados para montar uno)")
    carpeta, _ = _caso()
    codigos, texto = C._informe()
    assert codigos == [] and texto.startswith(f"Monta las 10 páginas del caso «{Path(carpeta).name}»")
    (Path(carpeta) / "resultados" / "olor" / "resumen.npz").write_bytes(b"roto")
    with pytest.raises(C.Problema) as p:
        C._informe()
    assert p.value.codigo == "DIS-32" and Path(carpeta).name in p.value.detalle


@pytest.fixture(scope="module")
def motor_web(tmp_path_factory):
    """¿Arranca el motor web en un proceso hijo desde esta consola? (desde algunas, no: p. ej. con el entorno dado con env=, como lanza el
    auditor las pruebas). Si no, la prueba se salta al prepararla y no al correr: el auditor cuenta como fallo lo que se salta al correr."""
    codigo = """
from PySide6 import QtCore, QtWebEngineWidgets, QtWidgets
QtCore.QCoreApplication.setAttribute(QtCore.Qt.ApplicationAttribute.AA_ShareOpenGLContexts)
app = QtWidgets.QApplication(["x"])
from PySide6.QtWebEngineCore import QWebEnginePage
prueba = QWebEnginePage()
motor = {}
prueba.loadFinished.connect(lambda ok: (motor.update(ok=ok), app.quit()))
prueba.setHtml("<p>hola</p>")
QtCore.QTimer.singleShot(20000, app.quit)
app.exec()
print("@@", bool(motor.get("ok")))
"""
    r = subprocess.run([sys.executable, "-c", codigo], capture_output=True, text=True, encoding="utf-8", errors="replace",
                       cwd=tmp_path_factory.mktemp("motor_web"), timeout=60)
    if "@@ True" not in r.stdout:
        pytest.skip("el motor web no arranca desde esta consola: " + " | ".join(x for x in r.stderr.splitlines() if "shared_image" not in x)[-600:])


@con_qt
def test_el_pdf_se_escribe_y_cada_pagina_cabe(tmp_path, monkeypatch, motor_web):
    carpeta, _ = _caso()
    monkeypatch.setenv("PYTHONIOENCODING", "utf-8")             # el entorno, heredado: con env= el motor web del hijo no arranca (Windows)
    codigo = f"""
from PySide6 import QtCore, QtWebEngineWidgets, QtWidgets
QtCore.QCoreApplication.setAttribute(QtCore.Qt.ApplicationAttribute.AA_ShareOpenGLContexts)
app = QtWidgets.QApplication(["x"])
from teodors.writer import datos, informe, pdf
d = datos.reunir({str(carpeta)!r}, viento=False)
img = informe.carpeta_trabajo(d) / "img"
img.mkdir(parents=True, exist_ok=True)
html = informe.maquetar(d, img)
salida = {{}}
def hecho(ok, ruta):
    salida.update(ok=ok, ruta=str(ruta), paginas=pdf.a_png(ruta, img.parent / "paginas"))
    app.quit()
pdf.imprimir(html, informe.ruta_pdf(d), hecho)
QtCore.QTimer.singleShot(60000, app.quit)
app.exec()
print("@@", salida.get("ok"), salida.get("paginas"), salida.get("ruta"))
"""
    r = subprocess.run([sys.executable, "-c", codigo], capture_output=True, text=True, encoding="utf-8", errors="replace", cwd=tmp_path, timeout=120)
    linea = next((x for x in r.stdout.splitlines() if x.startswith("@@")), "")
    assert linea.split()[1:3] == ["True", "10"], (r.stdout[-500:], "\n".join(x for x in r.stderr.splitlines() if "shared_image" not in x)[-1500:])
    ruta = Path(linea.split(maxsplit=3)[3])
    assert ruta == Path(carpeta) / f"{Path(carpeta).name}.pdf" and ruta.stat().st_size > 20000
    assert "no caben" not in r.stderr


# ------------------------------------------------------------------------------ KI-40: el informe no se cuelga si el mapa no funciona
CAPTURAS = ["reanalisis_caso", "reanalisis_comparacion", "episodio"]   # las tres copias de capturas.py (KI-31): el mismo arreglo en cada una
CHROMIUM_CERRADO = ("su motor web (Chromium) se ha cerrado (CrashedTerminationStatus, código -1073741515 = 0xC0000135: no encuentra una de "
                    "sus librerías)")


class _MapaFalso:
    """Lo que las capturas usan del mapa de la ventana: si está listo, si se ha cerrado su Chromium (`caido`) y el JavaScript, que contesta o no."""

    def __init__(self, listo=True, caido=None, contesta=True):
        self.listo, self.motivo, self.contesta = listo, caido, contesta

    def esta_listo(self):
        return self.listo

    def caido(self):
        return self.motivo

    def js(self, codigo, al_terminar=None):
        if al_terminar is not None and self.contesta:
            al_terminar(0)


class _VentanaFalsa:
    def __init__(self, mapa):
        self.mapa, self.terreno_info = mapa, {}


@con_qt
@pytest.mark.parametrize("tipo", CAPTURAS)
def test_las_capturas_fallan_al_momento_si_el_chromium_del_mapa_se_ha_cerrado(tipo, tmp_path):
    # KI-40 (2026-11-16): esperaban 90 s y luego, para siempre, a un mapa que ya no podía contestar; ahora fallan enseguida, diciendo por qué
    import importlib
    C = importlib.import_module(f"teodors.writer.{tipo}.capturas")
    fallos = []
    C.Capturas(_VentanaFalsa(_MapaFalso(listo=False, caido=CHROMIUM_CERRADO)), {}, tmp_path / "img", fallo=fallos.append).empezar()
    assert len(fallos) == 1 and "el mapa no funciona" in fallos[0] and "0xC0000135" in fallos[0]
    assert not C._en_marcha


@con_qt
@pytest.mark.parametrize("tipo", CAPTURAS)
def test_leer_la_vista_del_mapa_tiene_tope(tipo, tmp_path, monkeypatch):
    # KI-40: preguntar la vista a un mapa que no contesta esperaba para siempre; ahora, ESPERA_JS_S como mucho, y nada con su Chromium cerrado
    import importlib
    C = importlib.import_module(f"teodors.writer.{tipo}.capturas")
    mapa = _MapaFalso(contesta=False)
    cap = C.Capturas(_VentanaFalsa(mapa), {}, tmp_path / "img")
    pasos = cap._leer_vista()
    assert next(pasos) == 100                                       # sin respuesta todavía: espera
    with monkeypatch.context() as m:
        m.setattr(C, "ESPERA_JS_S", -1.0)                           # y pasado el tope, falla
        with pytest.raises(RuntimeError, match="no contesta"):
            next(pasos)
    mapa.motivo = CHROMIUM_CERRADO
    with pytest.raises(RuntimeError, match="Chromium"):
        next(cap._leer_vista())
    mapa.motivo, mapa.contesta = None, True                         # y si contesta, la vista, como siempre
    with pytest.raises(StopIteration) as fin:
        next(cap._leer_vista())
    assert fin.value.value == [0.0]


@con_qt
def test_si_el_mapa_no_contesta_las_capturas_fallan_al_tope_y_una_sola_vez(tmp_path, monkeypatch):
    # KI-40: la espera a que el mapa acabe de cargar, en las tres copias. Si contesta, siguen (y el tope no salta después); si no contesta,
    # fallan al tope; si su Chromium se cierra mientras, fallan con ese motivo; y lo que conteste tarde ya no hace nada. Con el reloj de Qt: en
    # un proceso aparte y con un tope de 0,5 s
    monkeypatch.setenv("PYTHONIOENCODING", "utf-8")
    codigo = r"""
import importlib, json, os, time
from PySide6 import QtCore
app = QtCore.QCoreApplication(["x"])


class Mapa:
    def __init__(self, contesta):
        self.contesta, self.motivo, self.tarde = contesta, None, []

    def esta_listo(self):
        return True

    def caido(self):
        return self.motivo

    def js(self, codigo, al_terminar=None):
        if al_terminar is None:
            return
        if self.contesta:
            QtCore.QTimer.singleShot(5, lambda: al_terminar(0))       # como Chromium: la respuesta llega luego
        else:
            self.tarde.append(al_terminar)


class Ventana:
    def __init__(self, mapa):
        self.mapa, self.terreno_info = mapa, {}


def girar(segundos, hasta=lambda: False):
    fin = time.time() + segundos
    while time.time() < fin and not hasta():
        app.processEvents()
        time.sleep(0.01)


def probar(C, contesta, muere=False):
    mapa, fallos, siguio = Mapa(contesta), [], []
    cap = C.Capturas(Ventana(mapa), {}, os.path.abspath("img"), fallo=fallos.append)

    def pasos():
        yield ("mapa", 0)
        siguio.append(1)
    cap._gen = pasos()
    if muere:
        QtCore.QTimer.singleShot(100, lambda: setattr(mapa, "motivo", "su motor web (Chromium) se ha cerrado (prueba)"))
    t0 = time.time()
    cap._siguiente()
    girar(5, lambda: fallos or siguio)
    s = time.time() - t0
    girar(0.7)                                                       # el tope de lo ya contestado no salta
    for cb in mapa.tarde:                                            # lo que contesta tarde: ni sigue ni falla otra vez
        cb(0)
    girar(0.7)
    return {"fallos": fallos, "siguio": len(siguio), "s": round(s, 2)}


salida = {}
for tipo in ("reanalisis_caso", "reanalisis_comparacion", "episodio"):
    C = importlib.import_module(f"teodors.writer.{tipo}.capturas")
    C.ESPERA_JS_S = 0.5
    salida[tipo] = {"contesta": probar(C, True), "no_contesta": probar(C, False), "muere": probar(C, False, muere=True)}
print("@@" + json.dumps(salida), flush=True)
os._exit(0)
"""
    r = subprocess.run([sys.executable, "-c", codigo], capture_output=True, text=True, encoding="utf-8", errors="replace", cwd=tmp_path, timeout=120)
    linea = next((x for x in r.stdout.splitlines() if x.startswith("@@")), None)
    assert linea, r.stderr[-1500:]
    for tipo, res in json.loads(linea[2:]).items():
        assert res["contesta"]["fallos"] == [] and res["contesta"]["siguio"] == 1, (tipo, res)
        assert res["no_contesta"]["siguio"] == 0 and len(res["no_contesta"]["fallos"]) == 1, (tipo, res)
        assert "el mapa no contesta" in res["no_contesta"]["fallos"][0] and res["no_contesta"]["s"] < 3, (tipo, res)
        assert res["muere"]["siguio"] == 0 and len(res["muere"]["fallos"]) == 1 and "Chromium" in res["muere"]["fallos"][0], (tipo, res)
