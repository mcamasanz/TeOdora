# -*- coding: utf-8 -*-
"""Prueba 05, 2.ª parte: la cadena de verdad con gui/escenarios.py.

1. Un plan SEMANAL en hora oficial pasado a emisión hora a hora con `escenarios.factores` y sumado con las
   respuestas de `prueba_planes.py` (hay que correrla antes), frente al motor. 20-oct-2026 es martes y
   21, miércoles, y cada día oficial empieza a las 22 UTC (horario de verano): plan «el martes emite, el
   miércoles no» = A − B, con B = emisión constante desde el periodo de 22 a 23 UTC del 20. ⚠️ El 1.er
   periodo del motor lleva fin = hora de inicio: B empieza a las 23 UTC (si no, ya emite de 21 a 22).
2. Cambio de hora y calendario: horas oficiales y días de la semana y del mes en fechas conocidas.
3. Conversiones entre planes y guardar y leer.

    C:\\e2s\\python.exe 99-Test\\05_planes\\prueba_plan_semanal.py
"""
import json
import sys
import tempfile
from pathlib import Path

AQUI = Path(__file__).resolve().parent
sys.path.insert(0, str(AQUI))
import prueba_planes as pp  # noqa: E402  (pone las rutas de lib/ y el sys.stdout)

import numpy as np  # noqa: E402
import pandas as pd  # noqa: E402

from teodors.planta import geo  # noqa: E402
from teodors.fuentes import terreno  # noqa: E402
from teodors import planta as config  # noqa: E402
from teodors.operacion import planes as E  # noqa: E402
from teodors.casos import receptores as receptores_mapa  # noqa: E402

fallos = []


def comprueba(nombre, bien, detalle=""):
    print(f"  {'OK ' if bien else 'MAL'} {nombre} {detalle}", flush=True)
    if not bien:
        fallos.append(nombre)


def calendario():
    print("Calendario y cambio de hora")
    pf = {"plan": "semanal", "dias": [0, 1, 2, 3, 4, 5, 6],
          "perfiles": [[float(d * 100 + h) for h in range(24)] for d in range(7)]}
    casos = [("2026-10-20 21:00", 123), ("2026-10-20 22:00", 200),      # verano: martes 23 h → miércoles 00 h
             ("2026-01-05 22:00", 23), ("2026-01-05 23:00", 100),      # invierno: lunes 23 h → martes 00 h
             ("2026-03-29 00:00", 601), ("2026-03-29 01:00", 603),     # domingo: de 01 h salta a 03 h
             ("2026-10-25 00:00", 602), ("2026-10-25 01:00", 602)]     # domingo: las 02 h se repiten
    v = E.factores(pf, [pd.Timestamp(c) for c, _ in casos])
    for (c, esperado), x in zip(casos, v):
        comprueba(f"semanal {c} UTC", x == esperado, f"→ {x:g} (esperado {esperado})")
    pm = {"plan": "mensual", "dias": list(range(31)),
          "perfiles": [[float(d)] * 24 for d in range(31)]}
    comprueba("mensual: día 15", E.factores(pm, [pd.Timestamp("2026-07-15 10:00")])[0] == 14.0)
    pd1 = {"plan": "diario", "dias": [0], "perfiles": [[0.5 if h == 8 else 0.0 for h in range(24)]]}
    comprueba("diario: 8 h oficiales = 6 UTC en verano", E.factores(pd1, [pd.Timestamp("2026-07-15 06:00")])[0] == 0.5)
    comprueba("diario: 8 h oficiales = 7 UTC en invierno", E.factores(pd1, [pd.Timestamp("2026-01-15 07:00")])[0] == 0.5)
    esc = {"mes": "2026-11", "focos": {"F": {"plan": "mensual"}}}
    fines = pd.DatetimeIndex(["2024-11-15 12:00", "2025-07-15 12:00", "2021-11-30 12:00"])
    comprueba("mensual: se evalúa ese mes en todos los años", E.horas_del_plan(esc, fines).tolist() == [True, False, True])
    esc2 = {"mes": None, "focos": {"F": {"plan": "semanal"}}}
    comprueba("semanal: se evalúa todo el año", E.horas_del_plan(esc2, fines).all())


def conversiones():
    print("Conversiones y guardar")
    perfiles = [[1.0] * 24, [0.0] * 24]
    pf = {"plan": "semanal", "perfiles": [list(p) for p in perfiles], "dias": [0, 1, 0, 1, 0, 1, 1]}
    E.cambiar_plan(pf, "mensual", "2026-11")             # 1-nov-2026 es domingo
    comprueba("semanal → mensual: 1-nov es domingo", pf["perfiles"][pf["dias"][0]] == [0.0] * 24 and len(pf["dias"]) == 31)
    comprueba("semanal → mensual: 2-nov es lunes", pf["perfiles"][pf["dias"][1]] == [1.0] * 24)
    E.cambiar_plan(pf, "semanal", "2026-11")
    comprueba("mensual → semanal: vuelve al original", [pf["perfiles"][k][0] for k in pf["dias"]] == [1, 0, 1, 0, 1, 0, 0])
    E.poner_perfil(pf, [0, 2, 4], [0.5] * 24)
    comprueba("no quedan perfiles sin usar", len(pf["perfiles"]) == 2 and sorted(set(pf["dias"])) == [0, 1])
    E.poner_perfil(pf, [1, 3, 5, 6], [0.5] * 24)
    comprueba("los perfiles iguales se juntan", len(pf["perfiles"]) == 1)
    cat = {"focos": [{"id": "F1", "funcionamiento": {"modo": "continuo"}}]}
    esc = E.nuevo(cat, "Volteos de noviembre")
    p = E.plan_foco(cat["focos"][0], esc)
    E.cambiar_plan(p, "semanal")
    E.poner_perfil(p, [0], [0.25] * 24)
    with tempfile.TemporaryDirectory() as d:
        ruta = E.guardar(esc, d)
        lee = E.cargar(ruta)
        comprueba("guardar y leer", lee["focos"] == esc["focos"], ruta.name)
        esc["mes"] = None
        E.cambiar_plan(p, "diario")
        E.cambiar_plan(p, "mensual")
        try:
            E.guardar(esc, d)
            comprueba("un plan mensual sin mes no se guarda", False)
        except ValueError:
            comprueba("un plan mensual sin mes no se guarda", True)
        comprueba("lista los guardados", [n for n, _, _ in E.listar(d)] == ["Volteos de noviembre"])


def motor():
    print("Plan semanal frente al motor (pilas)")
    base = config.DIR_VIENTO3D / pp.SERIE
    info = json.loads((base / pp.MES / "caso.json").read_text(encoding="utf-8"))
    malla = {k: info[k] for k in ("nx", "ny", "celda_m", "ext")}
    emp = config.cargar_emplazamiento()
    xp, yp = geo.a_utm(emp["lat"], emp["lon"])
    Z, U, tr = terreno.cargar(terreno.ultimo_caso(emp["lat"], emp["lon"]))

    def cota(x, y):
        f = int((tr.f - y) / -tr.e)
        c = int((x - tr.c) / tr.a)
        return float(max(Z[min(max(f, 0), Z.shape[0] - 1), min(max(c, 0), Z.shape[1] - 1)], 0.0))

    res = terreno.resumen(Z, U, tr, emp["lat"], emp["lon"])
    m = receptores_mapa.malla(res["nucleos"], None)
    recs = [(x, y, cota(x, y)) for x, y, _ in m]
    gruesa = np.array([c == "gruesa" for _, _, c in m])
    f = pp.focos(xp, yp, cota)[0]
    uno = dict(f, q={"UNO": f["q0"]}, perfil=None)
    fa, A = pp.correr(f["id"] + "_A", malla, info["zona"], pp.INI_A, pp.HORAS_A, ["UNO"], uno, recs)
    ini_b = pd.Timestamp("2026-10-20 23:00")
    fb, B = pp.correr(f["id"] + "_B23", malla, info["zona"], ini_b, 25, ["UNO"], uno, recs)
    unos = [[1.0 if k == h else 0.0 for k in range(24)] for h in range(24)]
    g = dict(f, q={e: f["q0"] for e in pp.HORAS}, perfil={e: unos[h] for h, e in enumerate(pp.HORAS)})
    fr, R = pp.correr(f["id"] + "_R", malla, info["zona"], pp.INI_A, pp.HORAS_A, pp.HORAS, g, recs)
    A, B = A["UNO"], B["UNO"]
    i0 = int(np.where(fa == fb[0])[0][0])
    D = A.copy()
    D[i0:i0 + len(fb)] -= B
    te = pp.indice_emision(fr)
    # el plan de verdad: martes sí, miércoles no, en hora oficial
    pf = {"plan": "semanal", "perfiles": [[1.0] * 24, [0.0] * 24], "dias": [1, 0, 1, 1, 1, 1, 1]}
    W = E.factores(pf, fr - pd.Timedelta(hours=1))
    print(f"  periodos con emisión: {int(W.sum())} de {len(W)}; el último, {fr[np.where(W > 0)[0][-1]]} UTC; B empieza en {fb[0]}", flush=True)
    comprueba("el plan se apaga donde empieza B", int((W > 0).sum()) == i0, f"{int((W > 0).sum())} y {i0}")
    r = pp.compara(pp.componer(R, te, W), D, gruesa)
    print("  " + json.dumps({k: r[k] for k in ("dif_max_rel_al_maximo", "rel_max_pct", "masa_mal_atribuida_pct")}), flush=True)
    comprueba("suma por plan = motor", r["dif_max_rel_al_maximo"] < 1e-6, f"dif. máx. {r['dif_max_rel_al_maximo']:.1e} del máximo")
    return {"periodos_con_emision": int((W > 0).sum()), **{k: r[k] for k in ("dif_max_rel_al_maximo", "rel_max_pct", "masa_mal_atribuida_pct", "receptor_horas_evaluadas")}}


if __name__ == "__main__":
    calendario()
    conversiones()
    out = motor()
    (AQUI / "resultados_plan_semanal.json").write_text(json.dumps(out, indent=1), encoding="utf-8")
    print("FALLOS: " + (", ".join(fallos) if fallos else "ninguno"))
    sys.exit(1 if fallos else 0)
