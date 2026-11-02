# -*- coding: utf-8 -*-
"""El penacho de un periodo en 3D (un día del reanálisis, un episodio, una predicción): superficies de igual concentración sobre el relieve.

Las respuestas de los focos (`operacion.respuestas`) están en el suelo, así que aquí SÍ se lanza el motor, con la
emisión del plan y receptores en altura, una vez por plan, periodo y magnitud; luego se lee de
<resultados del periodo>/<magnitud>/penacho_3d.json mientras el resultado 2D sea el mismo (su `firma`).

Cada día se calcula aparte, con el perfil de emisión del plan ese día:
1. Una pasada cada 100 m a ±3 km y 15 alturas, con su arranque desde las 06 UTC del día anterior.
2. En cada hora con algo que ver, otra cada 25 m solo donde hay penacho, arrancando poco antes. Si no coincide con la
   primera en los nudos comunes, se repite con más arranque (con calma, lo emitido tarda más en salir).
3. Superficies a 1, 3 y 5 veces la referencia de la magnitud, sobre el logaritmo de C, en una rejilla que sigue el terreno.

Esto calcula y guarda: montar la página que lo enseña es de la interfaz. Necesita pyvista para las superficies (`teodors[penacho_3d]`), que se carga al usarlo.

⚠️ El motor repite el mismo perfil de 24 h en cada cálculo: con un plan que cambia de un día a otro, las primeras horas de cada día
llevan lo emitido el anterior como si fuera el de ese día. ⚠️ Con una serie de varios años, el motor lee el mes entero:
habrá que recortar el viento a estos dos días. ⚠️ Fuera de ±3 km no hay nada calculado.
"""
import hashlib
import json
import shutil
import subprocess
import sys
import time
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

import numpy as np
import pandas as pd
from pyproj import Transformer
from scipy.ndimage import binary_dilation

from teodors import planta as config
from teodors.comun import procesos, registro
from teodors.fuentes import terreno
from teodors.meteo.viento3d import almacen
from teodors.operacion import focos as F, periodos, planes as E, simulacion as PC
from teodors.preparacion.puffs import control_fuentes as cf, salida as lector

log = registro.get("penacho_3d")

ALTURAS = (0, 2, 5, 10, 20, 35, 50, 75, 100, 150, 200, 300, 400, 600, 800)      # m sobre el suelo
SEMILADO, PASO, PASO_FINO = 3000.0, 100.0, 25.0
UMBRAL = 0.3                       # veces la referencia: de ahí para abajo no hace falta detalle
MARGEN_M, CUADRADO_PLANTA_M = 200.0, 400.0
PREVIAS = 2                        # horas de arranque de la 2.ª pasada; se dobla si no basta
TOLERANCIA = 0.02                  # diferencia con la 1.ª pasada en los nudos comunes
PROCESOS = 4
NIVELES = (1.0, 3.0, 5.0)          # veces la referencia (olor: ou_E/m³)
ESCALA_M = 0.25                    # posiciones de las mallas: cada 25 cm en 16 bits, ±8 km
PASO_TERRENO = 50.0
ESPECIE, VIENTO = "C", "viento3d.dat"
_b64 = __import__("base64").b64encode


def semilado_vista():
    """Lo que cubre la ortofoto de la planta alrededor de su centro, en m (`visor3d.semilado_m`): hasta ahí llegan terreno y rótulos."""
    return float(config.pide("visor3d", "semilado_m"))


def ruta_guardada(res, clave):
    return PC.carpeta_resultados({"nombre": res["nombre"]}, res["periodo"]) / clave / "penacho_3d.json"


def _factores(esc, catalogo, dia):
    """{id: 24 factores por hora UTC de inicio} del plan ese día: los que multiplican a la emisión de referencia."""
    inicios = pd.date_range(dia, periods=24, freq="h")
    salen = {}
    for f in catalogo["focos"]:
        duty = F.fraccion_eventos(f)
        if duty is not None:
            salen[f["id"]] = [float(x) for x in E.factores(E.plan_foco(f, esc), inicios) * duty]
    return salen


def firma(res, clave):
    """Vale mientras el resultado 2D sea el mismo: su firma ya recoge el plan, los focos y el periodo."""
    return hashlib.sha1(f"{res['firma']}|{clave}".encode()).hexdigest()


def _listo(res, clave):
    ruta = ruta_guardada(res, clave)
    if not ruta.is_file():
        return False
    with open(ruta, encoding="utf-8") as f:
        return f.read(80).startswith('{"firma": "' + firma(res, clave))


def lista():
    """Los resultados con penacho de las 3 modalidades, de lo último a lo primero: {ruta, texto, magnitudes: [{clave, nombre, listo}]}."""
    base = config.DATOS / "resultados_planes"
    salen = []
    for ruta in sorted(base.glob("*/*/*/resultado.json"), key=lambda p: p.stat().st_mtime, reverse=True) if base.is_dir() else []:
        try:
            res = json.loads(ruta.read_text(encoding="utf-8"))
        except (ValueError, OSError):
            continue
        p = res.get("periodo")
        if p:
            salen.append({"ruta": str(ruta), "texto": f"{periodos.MODOS[p['modo']]} · {periodos.etiqueta(p)} · {res['nombre']}",
                          "magnitudes": [{"clave": k, "nombre": res["magnitudes"][k]["nombre"], "listo": _listo(res, k)} for k in res["orden"]]})
    return salen


def abrir(ruta_resultado, clave):
    """Lo guardado, para montar su página, y las horas para el reproductor; None si no vale."""
    res = json.loads(Path(ruta_resultado).read_text(encoding="utf-8"))
    if not _listo(res, clave):
        return None
    datos = json.loads(ruta_guardada(res, clave).read_text(encoding="utf-8"))
    return {"datos": datos, "horas": datos["horas_utc"]}


def _fuentes(esc, catalogo, m, dia, cota):
    salen = {"superficie": [], "punto": [], "volumen": []}
    factores = _factores(esc, catalogo, dia)
    for f in catalogo["focos"]:
        q = m["emisiones"].get(f["id"])
        if q is None or not any(factores[f["id"]]):
            continue
        modelo, d, q0 = F.geometria(f, cota)
        d.update(perfil={ESPECIE: factores[f["id"]]}, q={ESPECIE: q * q0})
        salen[modelo].append(d)
    return salen


def _correr(carpeta, viento, ini, nhoras, salen, receptores, nombre, cancelado):
    """Lanza el motor con los receptores repartidos en PROCESOS (son independientes). Devuelve fines y C[periodo, receptor]."""
    env = procesos.entorno()

    def uno(k):
        base = f"{nombre}_{k}"
        cf.escribir(carpeta / (base + ".inp"), viento["malla"], config.VIENTO3D_ZFACE, ini, nhoras, viento["zona"], [ESPECIE],
                    areas=salen["superficie"], puntos=salen["punto"], volumenes=salen["volumen"],
                    receptores=receptores[k::PROCESOS], titulo="Penacho en 3D",
                    nombres={"viento": VIENTO, "listado": base + ".lst", "concentraciones": base + ".dat"})
        with open(carpeta / (base + ".log"), "w", errors="replace") as fo:
            p = subprocess.Popen([sys.executable, "-m", "teodors", "puffs", base + ".inp"], cwd=str(carpeta),
                                 stdout=fo, stderr=subprocess.STDOUT, env=env)
            while p.poll() is None:
                if cancelado and cancelado():
                    p.kill()
                    p.wait()
                    raise RuntimeError("Cálculo cancelado.")
                time.sleep(0.5)
        if p.returncode != 0 or not (carpeta / (base + ".dat")).exists():
            raise RuntimeError(f"El motor falló (rc={p.returncode}).\n" + (carpeta / (base + ".log")).read_text(errors="replace")[-1200:])
        return base
    with ThreadPoolExecutor(PROCESOS) as pool:
        bases = list(pool.map(uno, range(PROCESOS)))
    fines, C = None, None
    for k, base in enumerate(bases):
        fz, m = lector.concentraciones(carpeta / (base + ".dat"), especie=ESPECIE)
        if C is None:
            fines = pd.to_datetime(fz)
            C = np.zeros((len(fines), len(receptores)), np.float32)
        C[:, k::PROCESOS] = np.asarray(m, np.float32)
        (carpeta / (base + ".dat")).unlink()
    return fines, C


def _nudos(centro, semilado, paso):
    k = np.arange(-int(semilado / paso), int(semilado / paso) + 1) * paso
    return np.round(centro[0] + k, 1), np.round(centro[1] + k, 1)


def _segunda_pasada(H, dia, gruesa, xg, yg, xs, ys, factor, centro, ref, cota, carpeta, viento, salen, cancelado):
    """La hora H cada 25 m, solo donde hay penacho. Devuelve el campo (altura, j, i)."""
    Z = np.array(ALTURAS, float)
    hay = binary_dilation((gruesa >= UMBRAL * ref).any(axis=0), iterations=int(np.ceil(MARGEN_M / PASO)))
    mascara = hay[np.clip((np.arange(len(ys)) + factor // 2) // factor, 0, len(yg) - 1)[:, None],
                  np.clip((np.arange(len(xs)) + factor // 2) // factor, 0, len(xg) - 1)[None, :]]
    X, Y = np.meshgrid(xs, ys)
    mascara |= (np.abs(X - centro[0]) <= CUADRADO_PLANTA_M) & (np.abs(Y - centro[1]) <= CUADRADO_PLANTA_M)
    jj, ii = np.nonzero(mascara)
    recs = [(float(xs[i]), float(ys[j]), cota(float(xs[i]), float(ys[j])), float(h)) for h in Z for j, i in zip(jj, ii)]
    fin = pd.Timestamp(dia) + pd.Timedelta(hours=H)
    comunes = mascara[::factor, ::factor]
    previas = PREVIAS
    while True:
        fines, C = _correr(carpeta, viento, fin - pd.Timedelta(hours=previas), previas + 1, salen, recs, f"h{H:02d}", cancelado)
        if str(fines[-1])[:16] != str(fin)[:16]:
            raise RuntimeError(f"último periodo {fines[-1]}, no {fin}")
        campo = np.zeros((len(Z), len(ys), len(xs)), np.float32)
        campo[:, jj, ii] = C[-1].reshape(len(Z), len(jj))
        a, b = gruesa[:, comunes], campo[:, ::factor, ::factor][:, comunes]
        g = a > 0.1 * ref
        error = float((np.abs(a - b)[g] / a[g]).max()) if g.any() else 0.0
        if error <= TOLERANCIA or previas >= 16:
            if error > TOLERANCIA:
                log.warning(f"3D, {H:02d} UTC: {error:.1%} con la primera pasada tras {previas} h de arranque")
            return campo
        previas *= 2


def _malla_base(xs, ys, cota, xc, yc):
    """Rejilla estructurada que sigue el terreno."""
    import pyvista as pv                     # solo aquí: tarda en cargar y la app no lo necesita para lo demás
    Z = np.array(ALTURAS, float)
    cotas = np.array([[cota(float(x), float(y)) for x in xs] for y in ys])
    forma = (len(ys), len(xs), len(Z))
    Xg = np.broadcast_to((xs - xc)[None, :, None], forma)
    Yg = np.broadcast_to((ys - yc)[:, None, None], forma)
    Zg = cotas[:, :, None] + Z[None, None, :]
    return pv.StructuredGrid(Xg.transpose(1, 0, 2).astype(float), Yg.transpose(1, 0, 2).astype(float), Zg.transpose(1, 0, 2).astype(float))


def _superficies(campo, malla, niveles):
    """[{p, i, n} o None] por nivel: posiciones en 16 bits e índices en base64."""
    malla["c"] = np.log10(np.maximum(campo, niveles[0] / 1000.0)).transpose(2, 1, 0).ravel(order="F")
    salen = []
    for nv in niveles:
        s = malla.contour(isosurfaces=[float(np.log10(nv))], scalars="c", method="contour").clean().triangulate()
        if s.n_points == 0:
            salen.append(None)
            continue
        ind = np.asarray(s.faces, np.uint32).reshape(-1, 4)[:, 1:].ravel()
        grande = s.n_points >= 65536
        salen.append({"p": _b64(np.round(np.asarray(s.points) / ESCALA_M).astype("<i2").tobytes()).decode(),
                      "i": _b64(ind.astype("<u4" if grande else "<u2").tobytes()).decode(),
                      "n": int(len(ind) // 3), "i32": grande})
    return salen


def _resumen_hora(campo, xs, ys, centro, nivel, unidad):
    Z = np.array(ALTURAS, float)
    texto = f"Máximo: {PC.cifra(float(campo.max()))} {unidad}"
    arriba = campo >= nivel
    if not arriba.any():
        return texto
    planta = arriba.any(axis=0)
    X, Y = np.meshgrid(xs, ys)
    alcance = float(np.hypot(X - centro[0], Y - centro[1])[planta].max()) / 1000.0
    borde = planta[0].any() or planta[-1].any() or planta[:, 0].any() or planta[:, -1].any()
    return (texto + f"<br>Altura: {Z[arriba.any(axis=(1, 2))].max():.0f} m · Alcance: "
            + f"{alcance:.1f}".replace(".", ",") + " km" + (" o más" if borde else ""))


def _terreno_vista(centro, cota):
    k = np.arange(-int(semilado_vista() / PASO_TERRENO), int(semilado_vista() / PASO_TERRENO) + 1) * PASO_TERRENO
    z = np.array([[cota(centro[0] + float(u), centro[1] + float(v)) for u in k] for v in k])
    return {"n": len(k), "paso": PASO_TERRENO, "semilado": float(k[-1]), "z": _b64(np.round(z * 10).astype("<i2").tobytes()).decode()}


def _rotulos(meta, x, y, cotas, centro, cota):
    xc, yc = centro
    a_utm = Transformer.from_crs("EPSG:4326", config.EPSG_UTM, always_xy=True)
    rotulos = [{"t": "Planta", "x": 0.0, "y": 0.0, "z": cota(xc, yc)}]
    for r in config.bloque("visor3d").get("rotulos", []):         # los que no salen de los receptores: {t, lon, lat}
        gx, gy = a_utm.transform(r["lon"], r["lat"])
        rotulos.append({"t": r["t"], "x": gx - xc, "y": gy - yc, "z": cota(gx, gy)})
    vistos = {r["t"] for r in rotulos}
    for e in meta["etiquetas"]:
        dx, dy = float(x[e["i"]]) - xc, float(y[e["i"]]) - yc
        if max(abs(dx), abs(dy)) <= semilado_vista() and e["nombre"] not in vistos and e["clase"] in ("nucleo", "nombrado"):
            vistos.add(e["nombre"])
            rotulos.append({"t": e["nombre"], "x": dx, "y": dy, "z": float(cotas[e["i"]])})
    return rotulos


def calcular(ruta_resultado, clave, progreso=None, cancelado=None):
    """Calcula y guarda el penacho en 3D de la magnitud `clave` del resultado de esa ruta. Devuelve lo mismo que `abrir`."""
    t0 = time.time()
    avisa = progreso or (lambda *_: None)
    res = json.loads(Path(ruta_resultado).read_text(encoding="utf-8"))
    esc, catalogo, periodo = res["esc"], F.cargar(), res["periodo"]
    if PC.firma(esc, catalogo, periodo) != res["firma"]:
        raise RuntimeError("Los focos han cambiado desde que se simuló: vuelve a simular.")
    m = res["magnitudes"][clave]
    carpeta_r = periodos.dir_respuestas(periodo)
    meta = json.loads((carpeta_r / "meta.json").read_text(encoding="utf-8"))
    with np.load(carpeta_r / "receptores.npz") as z:
        xr, yr, cr = z["x"], z["y"], z["cota"]
    ini, n, centro = pd.Timestamp(periodo["ini"]), periodo["dias"], tuple(meta["centro"])
    serie = config.DIR_VIENTO3D / res["serie"]
    mes = f"{ini:%Y%m}"
    info = json.loads((serie / mes / "caso.json").read_text(encoding="utf-8"))
    viento = {"malla": {k: info[k] for k in ("nx", "ny", "celda_m", "ext")}, "zona": info["zona"]}
    emp = config.cargar_emplazamiento()
    Zt, _, tr = terreno.cargar(terreno.ultimo_caso(emp["lat"], emp["lon"]))

    def cota(x, y):                          # la misma cuenta que `operacion.respuestas`
        f = int((tr.f - y) / -tr.e)
        c = int((x - tr.c) / tr.a)
        return float(max(Zt[min(max(f, 0), Zt.shape[0] - 1), min(max(c, 0), Zt.shape[1] - 1)], 0.0))

    trabajo = config.DIR_TRABAJO / "penacho_3d"
    shutil.rmtree(trabajo, ignore_errors=True)
    trabajo.mkdir(parents=True)
    try:
        avisa(1, "Preparando el viento…")
        almacen.descomprimir(serie / "cmz" / f"{mes}.cmz", trabajo / VIENTO)
        ref = float(m["ref"])
        niveles = [k * ref for k in NIVELES]
        Z = np.array(ALTURAS, float)
        xg, yg = _nudos(centro, SEMILADO, PASO)
        xs, ys = _nudos(centro, SEMILADO, PASO_FINO)
        factor = int(round(PASO / PASO_FINO))
        recs = [(x, y, cota(x, y), h) for h in Z for y in yg for x in xg]
        fina, gruesa = None, None
        horas, horas_utc = [], []
        for d in range(n):
            dia = ini + pd.Timedelta(days=d)
            pct = lambda x: int(2 + 96 * (d + x) / n)
            prefijo = f"Día {d + 1} de {n}: " if n > 1 else ""
            salen = _fuentes(esc, catalogo, m, dia, cota)
            avisa(pct(0), prefijo + "primera pasada…")
            fines, C = _correr(trabajo, viento, dia - pd.Timedelta(hours=18), 18 + 24, salen, recs, "vol", cancelado)
            C = C.reshape(len(fines), len(Z), len(yg), len(xg))
            i_dia = {int(f.hour): k for k, f in enumerate(fines) if f.normalize() == dia}
            if len(i_dia) != 24:
                raise RuntimeError(f"{len(i_dia)} periodos del día, no 24")
            con_penacho = [H for H in range(24) if (C[i_dia[H]] >= UMBRAL * ref).any()]
            campos = {}
            for k, H in enumerate(con_penacho):
                avisa(pct(0.25 + 0.65 * k / max(len(con_penacho), 1)), prefijo + f"hora {k + 1} de {len(con_penacho)}…")
                campos[H] = _segunda_pasada(H, dia, C[i_dia[H]], xg, yg, xs, ys, factor, centro, ref, cota, trabajo, viento, salen, cancelado)
            avisa(pct(0.92), prefijo + "superficies…")
            if fina is None:
                fina, gruesa = _malla_base(xs, ys, cota, *centro), _malla_base(xg, yg, cota, *centro)
            zona = pd.date_range(dia, periods=24, freq="h").tz_localize("UTC").tz_convert(E.zona())
            for H in range(24):
                fino = H in campos
                campo, x_, y_, malla = (campos[H], xs, ys, fina) if fino else (C[i_dia[H]], xg, yg, gruesa)
                dia_txt = f"{zona[H]:%d/%m} · " if n > 1 else ""
                horas.append({"etiqueta": f"{dia_txt}{H:02d}:00 UTC · {zona[H]:%H:%M} oficial", "mallas": _superficies(campo, malla, niveles),
                              "texto": _resumen_hora(campo, x_, y_, centro, niveles[0], m["unidad"])})
                horas_utc.append(f"{dia + pd.Timedelta(hours=H):%Y-%m-%d %H:%M}")
        datos = {"firma": firma(res, clave), "titulo": f"Plan «{res['nombre']}» · {m['nombre']}", "dia": f"{periodos.MODOS[periodo['modo']]} · {periodos.etiqueta(periodo)}",
                 "unidad": m["unidad"], "niveles": [PC.cifra(k).removesuffix(",0") for k in niveles], "horas": horas, "horas_utc": horas_utc,
                 "escala_m": ESCALA_M, "terreno": _terreno_vista(centro, cota), "rotulos": _rotulos(meta, xr, yr, cr, centro, cota),
                 "segundos": round(time.time() - t0, 1)}
        ruta = ruta_guardada(res, clave)
        ruta.parent.mkdir(parents=True, exist_ok=True)
        ruta.write_text(json.dumps(datos), encoding="utf-8")
    finally:
        shutil.rmtree(trabajo, ignore_errors=True)
    avisa(100, "Hecho")
    log.info(f"Penacho en 3D del plan «{res['nombre']}» ({m['nombre']}, {periodos.etiqueta(periodo)}) calculado en {datos['segundos'] / 60:.1f} min.")
    return {"datos": datos, "horas": horas_utc}
