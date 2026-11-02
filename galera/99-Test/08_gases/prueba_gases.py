# -*- coding: utf-8 -*-
"""Prueba 08: resultados de gases y olor estimado a partir de ellos (gui/focos.py, gui/planes_calculo.py).

Con cuentas independientes del código que se prueba:
1. Unidades: ley de los gases ideales, a mano, y que la masa no dependa de la temperatura si el caudal normal es el mismo.
2. Olor de un foco: manda la olfatometría; si no, el gas dominante con el umbral de Nagata (2003), frente a los µg/m³ de
   docs/referencias/metodologia/olores_metodologia.md §F.1; un gas sin umbral no cuenta.
3. Un foco con un solo gas: C_gas = C_olor × umbral en todos los receptores, y las imágenes salen idénticas.
4. Media de un gas de varios focos continuos = Σ Q · Σ R / 24, a mano con las respuestas.
5. Estadístico de un gas con límite horario, a mano con la serie (y con series a medida, en 99-Test/09_modalidades).
6. Tiempo: todas las magnitudes frente a solo el olor.

Necesita las respuestas de gui/tareas/respuestas_dia.py. Los focos son de EJEMPLO: esto prueba la herramienta, no da resultados.

    C:\\e2s\\python.exe 99-Test\\08_gases\\prueba_gases.py
"""
import copy
import hashlib
import json
import os
import shutil
import sys
import time
from pathlib import Path

AQUI = Path(__file__).resolve().parent
RAIZ = AQUI.parents[1]
os.environ.setdefault("ENCE_GALERA_DATOS", str(Path(os.environ["TEMP"]) / "ence_galera" / "datos_local"))
CARGADOR = RAIZ.parent / (RAIZ / "VERSION").read_text(encoding="utf-8").strip() / "cargador"
sys.path[:0] = [str(CARGADOR)]
from teodors import planta as _planta  # noqa: E402
_planta.activar(RAIZ / "entrada")
sys.stdout.reconfigure(encoding="utf-8")

import numpy as np  # noqa: E402

from teodors.operacion import planes as E  # noqa: E402
from teodors.operacion import focos as F  # noqa: E402
from teodors.operacion import simulacion as PC  # noqa: E402

fallos = []
resumen = {}
R_GAS, P_ATM = 8.314462618, 101325.0


def ok(nombre, si, detalle=""):
    print(f"  {'OK ' if si else 'MAL'} {nombre} {detalle}", flush=True)
    if not si:
        fallos.append(nombre)


def parecido(a, b, tol=2e-3):
    return abs(a - b) <= tol * abs(b)


def foco_punto(t_c, gases, olor=None, **salida):
    return {"modelo": "punto", "salida": dict(diametro_m=0.5, temperatura_C=t_c, **salida), "gases": gases, "olor": olor or {}}


def unidades():
    print("1. Unidades")
    # 50 ppm de H2S a 35 °C con 300 m³/h reales: gases ideales, a mano
    T = 35 + 273.15
    a_mano = 50e-6 * P_ATM * 34.08 / (R_GAS * T) * (300 / 3600)
    f = foco_punto(35, [{"gas": "H2S", "valor": 50, "unidad": "ppm"}], caudal_m3_h=300)
    ok("ppm con caudal real", parecido(F.gases_g_s(f)["H2S"], a_mano), f"{F.gases_g_s(f)['H2S']:.6f} y {a_mano:.6f} g/s")
    # el mismo caudal normal a 25 y a 800 °C: la misma masa
    vals = [F.gases_g_s(foco_punto(t, [{"gas": "NOx", "valor": 10, "unidad": "ppm"}], caudal_Nm3_h=1000))["NOx"] for t in (25, 127, 400, 800)]
    ok("con el caudal normal, la masa no depende de T", max(vals) / min(vals) - 1 < 1e-12, f"{vals[0]:.6f} g/s")
    a_mano = 10e-6 * P_ATM * 46.01 / (R_GAS * 273.15) * (1000 / 3600)
    ok("y es la de los gases ideales a 0 °C", parecido(vals[0], a_mano), f"{a_mano:.6f} g/s")
    # con el mismo caudal REAL, lo que antes daba de más: T / 298 K
    for t, veces in ((127, 1.34), (400, 2.26)):
        f = foco_punto(t, [{"gas": "H2S", "valor": 1, "unidad": "ppm"}], caudal_m3_h=1000)
        antes = 1 * 34.08 / F.VM_25C * 1000 * (1000 / 3600) * 1e-6
        ok(f"a {t} °C el cálculo anterior daba ×{veces}", abs(antes / F.gases_g_s(f)["H2S"] - veces) < 0.01, f"×{antes / F.gases_g_s(f)['H2S']:.2f}")
    # mg/Nm³ con caudal normal: el producto directo
    f = foco_punto(180, [{"gas": "NOx", "valor": 120, "unidad": "mg/Nm3"}], caudal_Nm3_h=3600)
    ok("mg/Nm³ con caudal normal", parecido(F.gases_g_s(f)["NOx"], 0.120, 1e-9), f"{F.gases_g_s(f)['NOx']:.6f} g/s")
    # mg/Nm³ con velocidad (caudal real a 180 °C)
    f = foco_punto(180, [{"gas": "NOx", "valor": 120, "unidad": "mg/Nm3"}], velocidad_m_s=15)
    a_mano = 120e-3 * (15 * np.pi * 0.25 ** 2) * 273.15 / 453.15
    ok("mg/Nm³ con velocidad", parecido(F.gases_g_s(f)["NOx"], a_mano, 1e-9), f"{a_mano:.5f} g/s")
    # velocidad de salida a partir del caudal normal: la que ve el motor
    f = foco_punto(180, [], caudal_Nm3_h=1000)
    ok("caudal real desde el normal", parecido(F.caudal_m3_s(f), 1000 / 3600 * 453.15 / 273.15, 1e-9))
    # ou_E/m³ referidas a 20 °C
    f = foco_punto(20, [], {"valor": 500, "unidad": "ou_E/m3"}, caudal_m3_h=3600)
    ok("ou_E/m³ a 20 °C: valor × caudal", parecido(F.olor_ouE_s(f), 500.0, 1e-9))
    f = foco_punto(180, [], {"valor": 500, "unidad": "ou_E/m3"}, caudal_m3_h=3600)
    ok("ou_E/m³ a 180 °C: caudal pasado a 20 °C", parecido(F.olor_ouE_s(f), 500 * 293.15 / 453.15, 1e-9), f"{F.olor_ouE_s(f):.1f} ou_E/s")
    # regla 1: el factor del H2S de la guía 06
    ok("1 ou_E de H2S = 0,5715 µg (guía 06)", parecido(F.ug_por_ouE("H2S"), 0.571485, 1e-4), f"{F.ug_por_ouE('H2S'):.6f}")


def olor_de_un_foco():
    print("2. Olor de un foco")
    # µg/m³ a 20 °C de la tabla F.1 de la guía, copiados a mano: comprueban umbral y masa molar de cada gas
    guia = {"H2S": 0.58, "CH3SH": 0.14, "DMS": 7.8, "DMDS": 8.6, "NH3": 1062, "TMA": 0.079, "ESCATOL": 0.031, "INDOL": 1.5,
            "AC_VALERICO": 0.16, "AC_ISOVALERICO": 0.33, "AC_BUTIRICO": 0.70, "AC_PROPIONICO": 17.6, "AC_ACETICO": 15.0,
            "SO2": 2317, "NO2": 230}
    mal = {g: v for g, v in guia.items() if abs(F.GASES[g][1] * F.GASES[g][0] / 24.055 / v - 1) > 0.05}
    ok(f"los {len(guia)} umbrales de Nagata coinciden con la guía", not mal and all(F.GASES[g][1] for g in guia), mal)
    ok("sin umbral: NOx y CO", F.GASES["NOx"][1] is None and F.GASES["CO"][1] is None)
    ok("con límite, la escala sale del límite aunque tenga umbral", F.magnitud("SO2")["ref"] == 3.5)
    ok("sin límite, del umbral", F.magnitud("H2S")["ref"] == F.ug_por_ouE("H2S"))
    gases = [{"gas": "H2S", "valor": 1.0, "unidad": "g/s"}, {"gas": "NH3", "valor": 1.0, "unidad": "g/s"}]
    f = foco_punto(20, gases)
    ok("sin olfatometría, el gas dominante", F.gas_dominante(f)[1] == "H2S" and parecido(F.olor_ouE_s(f), 1e6 / F.ug_por_ouE("H2S"), 1e-9),
       f"{F.olor_ouE_s(f):.0f} ou_E/s")
    f = foco_punto(20, [{"gas": "H2S", "valor": 1.0, "unidad": "g/s"}, {"gas": "TMA", "valor": 1.0, "unidad": "g/s"}])
    ok("elige solo el de umbral más bajo", F.gas_dominante(f)[1] == "TMA")
    f = foco_punto(20, gases, {"valor": 5, "unidad": "ou_E/s"})
    ok("con olfatometría, manda ella", F.olor_ouE_s(f) == 5 and "H2S" in F.gases_g_s(f))
    f = foco_punto(20, [{"gas": "NOx", "valor": 1.0, "unidad": "g/s"}, {"gas": "CO", "valor": 1.0, "unidad": "g/s"}])
    ok("un gas sin umbral no da olor", F.olor_ouE_s(f) is None and F.gas_dominante(f) is None)
    f = {"modelo": "volumen", "ubicacion": {"x": 1, "y": 1}, "altura_m": 1, "dimensiones": {"largo_m": 1, "ancho_m": 1, "alto_m": 1},
         "funcionamiento": {"modo": "continuo"}, "olor": {}, "gases": [{"gas": "NOx", "valor": 1.0, "unidad": "g/s"}]}
    ok("un foco solo con gases no queda pendiente", F.pendientes(f) == [], F.pendientes(f))
    f["gases"] = []
    ok("sin nada, sí", F.pendientes(f) == ["emisión de olor o de gases"], F.pendientes(f))
    f = foco_punto(20, [{"gas": "H2S", "valor": 1.0, "unidad": "ppm"}])
    ok("una concentración sin caudal no da masa", F.gases_g_s(f) == {})
    ruta = AQUI / "formato_antiguo.json"
    ruta.write_text(json.dumps({"formato": 1, "epsg": "EPSG:25831", "focos": []}), encoding="utf-8")
    try:
        F.cargar(ruta)
        ok("un fichero del formato anterior se rechaza", False)
    except ValueError as e:
        ok("un fichero del formato anterior se rechaza", True, str(e))
    ruta.unlink()


def plan(nombre, cat):
    return E.nuevo(cat, "prueba gases " + nombre)


def solo(cat, ids, nombre):
    e = plan(nombre, cat)
    for f in cat["focos"]:
        if f["id"] not in ids:
            E.poner_perfil(E.plan_foco(f, e), [0], [0.0] * 24)
    return e


def campos(e, clave):
    with np.load(PC.carpeta_resultados(e) / clave / "resumen.npz") as z:
        return {c: z[c] for c in z.files if c not in ("x", "y", "clase")}


def hash_png(ruta):
    return hashlib.sha256(ruta.read_bytes()).hexdigest()


def main():
    unidades()
    olor_de_un_foco()
    cat = F.cargar()
    carpeta = PC.dir_respuestas()
    meta = json.loads((carpeta / "meta.json").read_text(encoding="utf-8"))
    por_id = {f["id"]: f for f in cat["focos"]}

    print("3. Un foco con un solo gas: F11, H2S")
    e = solo(cat, ["F11"], "f11")
    r = PC.calcular(e, cat)
    print(f"  {r['segundos']:.1f} s · magnitudes: {r['orden']}", flush=True)
    co, ch = campos(e, "olor"), campos(e, "H2S")
    u = F.ug_por_ouE("H2S")
    for c in co:
        m = co[c] > co[c].max() * 1e-6
        d = np.abs(ch[c][m] - co[c][m] * u) / (co[c][m] * u)
        ok(f"{c}: C_H2S = C_olor × umbral", d.max() < 1e-5 and co[c].max() > 0, f"dif. máx. {d.max():.1e}")
    raiz = PC.carpeta_resultados(e)
    for n in ("p98_0.png", "p98_1.png", "media_0.png"):
        ok(f"imagen idéntica en olor y H2S: {n}", hash_png(raiz / "olor" / n) == hash_png(raiz / "H2S" / n))

    print("4. Media de un gas de varios focos continuos, a mano")
    ids = ["F03", "F05", "F07", "F11"]
    e = solo(cat, ids, "continuos")
    r = PC.calcular(e, cat)
    mano = 0.0
    for i in ids:
        with np.load(carpeta / f"R_{i}.npz") as z:
            mano = mano + F.gases_g_s(por_id[i])["H2S"] * 1e6 * z["R"].sum(axis=(0, 1)).astype(float) / 24.0
    c = campos(e, "H2S")["media"]
    m = mano > mano.max() * 1e-3
    d = np.abs(c[m] - mano[m]) / mano[m]
    ok("H2S: media = Σ Q · Σ R / 24", d.max() < 2e-3, f"dif. máx. {d.max():.1e}, máx. {mano.max():.3g} µg/m³")
    ok("cuenta los focos que lo emiten", r["magnitudes"]["H2S"]["focos"] == len(ids), r["magnitudes"]["H2S"]["focos"])

    print("5. Gas con límite: NOx de F13, continuo")
    e = solo(cat, ["F13"], "f13")
    r = PC.calcular(e, cat)
    m = r["magnitudes"]["NOx"]
    ok("sus columnas salen de planta/normativa.json", [c["clave"] for c in m["columnas"]] == ["media", "maximo", "norma_hora", "norma_anio"]
       and m["columnas"][2]["limite"] == 200, [c["clave"] for c in m["columnas"]])
    ok("unidad y escala", m["unidad"] == "µg/m³" and m["escala"] == "gases" and "NOₓ" in m["capas"][0]["leyenda"])
    with np.load(carpeta / "R_F13.npz") as z:
        R = z["R"].astype(float)
    Q = F.gases_g_s(por_id["F13"])["NOx"] * 1e6
    media = Q * R.sum(axis=(0, 1)) / 24.0
    k = int(np.argmax(media))
    dia = Q * R[:, :, k].sum(axis=0)
    c = campos(e, "NOx")
    # El mismo día se repite: cada valor sale 365 veces al año, así que la 19.ª hora más alta es la hora más alta del día
    ok("la 19.ª hora del peor año sale de la serie horaria", parecido(c["norma_hora"][k], dia.max(), 5e-3), f"{c['norma_hora'][k]:.3f} y {dia.max():.3f}")
    ok("la media del peor año es la del día", parecido(c["norma_anio"][k], dia.mean(), 5e-3), f"{c['norma_anio'][k]:.3f} y {dia.mean():.3f}")
    r_olor = r["magnitudes"]["olor"]
    ok("dice qué focos del olor están estimados y con qué gas", any("Venteo" in t and "H₂S" in t for t in r_olor["estimados"])
       and not any("Pila" in t or "Biofiltro" in t for t in r_olor["estimados"]) and not r["magnitudes"]["NOx"]["estimados"], r_olor["estimados"])
    fuera = r["magnitudes"]["olor"]["fuera"]
    ok("la antorcha se avisa en el olor, no en los gases", any("Antorcha" in t for t in fuera) and not r["magnitudes"]["NOx"]["fuera"], fuera)

    print("6. Tiempo")
    t0 = time.time()
    r = PC.calcular(plan("base", cat), cat)
    resumen["todas_s"] = round(time.time() - t0, 1)
    resumen["todas_series_s"] = r["segundos_serie"]
    resumen["magnitudes"] = r["orden"]
    print(f"  {len(r['orden'])} magnitudes: {resumen['todas_s']} s (series {resumen['todas_series_s']} s)", flush=True)
    resumen["maximos"] = {k: round(m["maximos"]["maximo"], 3) for k, m in r["magnitudes"].items()}
    print("  máximos:", resumen["maximos"], flush=True)
    sin = copy.deepcopy(cat)
    for f in sin["focos"]:
        f["gases"] = [g for g in f["gases"] if F.olor_medido(f) is None and F.ug_por_ouE(g["gas"])]
    t0 = time.time()
    r2 = PC.calcular(plan("solo olor", sin), sin)
    resumen["solo_olor_s"] = round(time.time() - t0, 1)
    resumen["solo_olor_series_s"] = r2["segundos_serie"]
    print(f"  {r2['orden']}: {resumen['solo_olor_s']} s (series {resumen['solo_olor_series_s']} s)", flush=True)
    tam = sum(p.stat().st_size for p in PC.carpeta_resultados(plan("base", cat)).rglob("*") if p.is_file())
    resumen["disco_MB"] = round(tam / 1e6, 1)
    print(f"  en disco: {resumen['disco_MB']} MB", flush=True)
    (AQUI / "resultados_gases.json").write_text(json.dumps(resumen, ensure_ascii=False, indent=1), encoding="utf-8")
    for c in PC.carpeta_resultados(plan("x", cat)).parent.glob("prueba_gases*"):
        shutil.rmtree(c, ignore_errors=True)
    print("FALLOS: " + (", ".join(fallos) if fallos else "ninguno"))
    sys.exit(1 if fallos else 0)


if __name__ == "__main__":
    main()
