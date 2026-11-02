# -*- coding: utf-8 -*-
"""El viento local en la planta: obstáculos medidos con LiDAR (ICGC 2021-2023), varias direcciones y resoluciones.

Mide lo que importa para colocar sensores: hasta qué distancia cambian los edificios el viento a 3 m del suelo, cuánto
pesan los olivos y el relieve, y qué resolución hace falta. Los campos van relativos al viento de entrada a 10 m.

    python prueba_planta.py [carpeta con planta_1m.npz]
"""
import json
import os
import sys
import time
from pathlib import Path

import matplotlib
import numpy as np
import requests
from scipy.ndimage import binary_dilation, binary_opening, distance_transform_edt

matplotlib.use("Agg")
import matplotlib.pyplot as plt  # noqa: E402

RAIZ = Path(__file__).resolve().parents[2]
CARGADOR = RAIZ.parent / (RAIZ / "VERSION").read_text(encoding="utf-8").strip() / "cargador"
sys.path[:0] = [str(CARGADOR)]
from teodors import planta as _planta  # noqa: E402
_planta.activar(RAIZ / "entrada")
from teodors.meteo.viento_local import modelo as vl  # noqa: E402

AQUI = Path(__file__).resolve().parent
PESADO = Path(sys.argv[1]) if len(sys.argv) > 1 else Path(os.environ["TEMP"]) / "ence_galera" / "99-Test" / "06_viento_local"
CENTRO = (286796.0, 4507440.0)         # los depósitos y la nave; la marca de la planta está en 286 763, 4 507 474
SEMILADO = 300.0
ALTO_MEDIDA = 3.0                      # m sobre el suelo: un sensor en un mástil corto
DIRECCIONES = {"NO": 315.0, "O": 270.0, "S": 180.0, "SE": 135.0}   # las dominantes en C9 (de noche NO/O; de día S/E-SE)
a_altura, obstaculos = vl.a_altura, vl.obstaculos


def monta(*a, **k):
    return vl.monta(*a, centro=CENTRO, semilado=SEMILADO, **k)


def a_rejilla(L, campo, dx, **k):
    return vl.a_rejilla(L, campo, dx, CENTRO, SEMILADO, **k)


def arboles(L, edificios):
    no = np.zeros_like(L["edif"], dtype=bool)
    for e in edificios:
        no |= e["masc_1m"]
    # sin cables ni bordes: lo fino se va con la apertura
    return binary_opening((L["alto"] > 2.0) & ~binary_dilation(no, iterations=2), iterations=1) * L["alto"]


def dif_rumbo(u1, v1, u2, v2):
    a = np.degrees(np.arctan2(u1, v1) - np.arctan2(u2, v2))
    return np.abs((a + 180) % 360 - 180)


def ortofoto(dom):
    f = PESADO / "ortofoto.png"
    bbox = (dom.x0, dom.y0, dom.x0 + dom.nx * dom.dx, dom.y0 + dom.ny * dom.dx)
    if not f.is_file():
        r = requests.get("https://www.ign.es/wms-inspire/pnoa-ma", timeout=60, params={
            "service": "WMS", "request": "GetMap", "version": "1.3.0", "layers": "OI.OrthoimageCoverage", "styles": "",
            "format": "image/png", "crs": "EPSG:25831", "bbox": ",".join(str(v) for v in bbox), "width": 1400, "height": 1400})
        if r.status_code == 200 and r.headers.get("content-type", "").startswith("image"):
            f.write_bytes(r.content)
    return plt.imread(f) if f.is_file() else None, bbox


def figura(dom, eds, campos, base, ruta, titulo):
    u, v = a_altura(dom, campos["u"]), a_altura(dom, campos["v"])
    u0, v0 = a_altura(dom, base["u"]), a_altura(dom, base["v"])
    vel, vel0 = np.hypot(u, v), np.hypot(u0, v0)
    foto, bbox = ortofoto(dom)
    fig, ax = plt.subplots(1, 2, figsize=(15.5, 7.4), sharex=True, sharey=True)
    ext = [bbox[0], bbox[2], bbox[1], bbox[3]]
    for a in ax:
        if foto is not None:
            a.imshow(foto, extent=ext, origin="upper", alpha=0.85)
    sp = ax[0].streamplot(dom.xc, dom.yc, np.ma.masked_invalid(u), np.ma.masked_invalid(v), color=np.nan_to_num(vel),
                          cmap="turbo", norm=plt.Normalize(0, 1.2), density=3.2, linewidth=1.0, arrowsize=0.8)
    fig.colorbar(sp.lines, ax=ax[0], shrink=0.75, label="Velocidad a 3 m / viento de entrada a 10 m")
    c = ax[1].imshow(np.ma.masked_invalid(100 * (vel / np.maximum(vel0, 1e-3) - 1)), extent=ext, origin="lower", cmap="RdBu_r",
                     vmin=-100, vmax=100, alpha=0.8)
    fig.colorbar(c, ax=ax[1], shrink=0.75, label="Cambio de velocidad por los edificios (%)")
    for a in ax:
        for e in eds:
            p = np.vstack([e["poligono"], e["poligono"][:1]])
            a.plot(p[:, 0], p[:, 1], "k", lw=1.1)
        a.set_xlim(CENTRO[0] - 170, CENTRO[0] + 170)
        a.set_ylim(CENTRO[1] - 170, CENTRO[1] + 170)
        a.set_aspect("equal")
        a.ticklabel_format(useOffset=False, style="plain")
        a.tick_params(labelsize=8)
    ax[0].set_title(titulo, fontsize=11)
    ax[1].set_title("Dónde cambian los edificios la velocidad", fontsize=11)
    fig.tight_layout()
    fig.savefig(Path(ruta).with_suffix(".jpg"), dpi=105, pil_kwargs={"quality": 84})
    plt.close(fig)


L = vl.lee_lidar(PESADO / "planta_1m.npz")
eds = obstaculos(L)
tabla = [{"centro_x": round(e["centro"][0]), "centro_y": round(e["centro"][1]), "area_m2": e["area"], "altura_m": round(e["h"], 1),
          "ancho_m": round(float(np.ptp(e["poligono"][:, 0])), 1), "fondo_m": round(float(np.ptp(e["poligono"][:, 1])), 1)} for e in eds]
print(f"{len(eds)} obstáculos en la zona; los mayores:", flush=True)
for f in tabla[:9]:
    print("  ", f, flush=True)
res = {"obstaculos": tabla}
dx, dz = 2.5, 1.25
t0 = time.time()
dom, ed, altura = monta(L, eds, dx, dz)
print(f"Rejilla {dx} m: {dom.nx} × {dom.ny} × {dom.nz} = {dom.nx * dom.ny * dom.nz / 1e6:.1f} M celdas · montada en {time.time() - t0:.1f} s", flush=True)
dosel_1m = arboles(L, eds)
s, c, *_ = a_rejilla(L, dosel_1m, dx, cubierta=dosel_1m > 0)
dosel = np.where(c >= 0.3 * dx ** 2, s / np.maximum(c, 1), 0.0)
print(f"Árboles: {100 * (dosel > 0).mean():.0f} % de la zona, altura media {dosel[dosel > 0].mean():.1f} m", flush=True)
sin_ed = vl.Dominio(dom.x0, dom.y0, dom.nx, dom.ny, dx, dom.nz, dz, suelo=dom.suelo)
dist = distance_transform_edt(altura == 0) * dx
anillos = [(0, 25), (25, 50), (50, 100), (100, 150), (150, 250)]
tiempos, por_dir, base_no = [], {}, None
for nombre, rumbo in DIRECCIONES.items():
    t0 = time.time()
    r = vl.calcula(dom, rumbo, ed)
    tiempos.append(time.time() - t0)
    b = vl.calcula(sin_ed, rumbo)
    print(f"{nombre}: {tiempos[-1]:.0f} s, {r['iteraciones']} iteraciones, divergencia {r['div_antes']:.2e} → {r['div_despues']:.1e}", flush=True)
    u, v, u0, v0 = (a_altura(dom, x) for x in (r["u"], r["v"], b["u"], b["v"]))
    vel, vel0 = np.hypot(u, v), np.hypot(u0, v0)
    cam = np.abs(vel / np.maximum(vel0, 1e-3) - 1) * 100
    gir = dif_rumbo(u, v, u0, v0)
    ok = np.isfinite(cam)
    filas = {}
    for a, z in anillos:
        m = ok & (dist >= a) & (dist < z)
        filas[f"{a}-{z} m"] = {"cambio_vel_mediana_%": round(float(np.median(cam[m])), 1), "cambio_vel_P90_%": round(float(np.percentile(cam[m], 90)), 1),
                               "giro_P90_grados": round(float(np.percentile(gir[m], 90)), 1),
                               "celdas_con_mas_de_20%_o_20grados_%": round(float(100 * ((cam[m] > 20) | (gir[m] > 20)).mean()), 1)}
    afect = ok & ((cam > 20) | (gir > 20))
    por_dir[nombre] = {"anillos": filas, "alcance_P95_m": round(float(np.percentile(dist[afect], 95)), 0), "alcance_max_m": round(float(dist[afect].max()), 0)}
    print(f"   alcance del cambio > 20 %: P95 {por_dir[nombre]['alcance_P95_m']:.0f} m · máx. {por_dir[nombre]['alcance_max_m']:.0f} m", flush=True)
    figura(dom, ed, r, b, AQUI / f"planta_{nombre}.png", f"Viento del {nombre} a 3 m, con edificios ({dx} m)")
    if nombre == "NO":
        base_no = {"r": r, "b": b, "u": u, "v": v, "vel": vel}
res["por_direccion"] = por_dir
res["segundos_por_direccion"] = round(float(np.mean(tiempos)), 1)

# ── ¿Cuánto pesan los árboles y el relieve? (viento del NO) ─────────────────────────────
t0 = time.time()
ra = vl.calcula(dom, 315.0, ed, dosel=dosel)
ua, va = a_altura(dom, ra["u"]), a_altura(dom, ra["v"])
vela = np.hypot(ua, va)
en_planta = np.isfinite(vela) & (dist < 60) & (dosel == 0)
en_arb = np.isfinite(vela) & (dosel > 0)
res["arboles_NO"] = {"velocidad_media_sin_arboles": {"zona_despejada_planta": round(float(np.nanmean(base_no["vel"][en_planta])), 2), "dentro_del_olivar": round(float(np.nanmean(base_no["vel"][en_arb])), 2)},
                     "velocidad_media_con_arboles": {"zona_despejada_planta": round(float(np.nanmean(vela[en_planta])), 2), "dentro_del_olivar": round(float(np.nanmean(vela[en_arb])), 2)},
                     "giro_P90_zona_despejada": round(float(np.percentile(dif_rumbo(ua, va, base_no["u"], base_no["v"])[en_planta], 90)), 1)}
print("Árboles:", res["arboles_NO"], flush=True)
figura(dom, ed, ra, base_no["b"], AQUI / "planta_NO_arboles.png", "Viento del NO a 3 m, con edificios y olivos (2,5 m)")
llano, ed_ll, _ = monta(L, eds, dx, dz, con_relieve=False)
rl = vl.calcula(llano, 315.0, ed_ll)
ul, vl_ = a_altura(llano, rl["u"]), a_altura(llano, rl["v"])
m = np.isfinite(ul) & np.isfinite(base_no["u"]) & (dist < 150)
res["relieve_NO"] = {"diferencia_vel_media": round(float(np.mean(np.abs(np.hypot(ul, vl_)[m] - base_no["vel"][m]))), 3),
                     "giro_P90_grados": round(float(np.percentile(dif_rumbo(ul, vl_, base_no["u"], base_no["v"])[m], 90)), 1),
                     "cota_min_max_en_150m": [round(float(dom.suelo[dist < 150].min()), 1), round(float(dom.suelo[dist < 150].max()), 1)]}
print("Relieve:", res["relieve_NO"], flush=True)

# ── ¿Qué resolución hace falta? (viento del NO, frente a 2,5 m, a menos de 150 m) ───────
refer_u, refer_v = base_no["u"], base_no["v"]
res["resolucion_NO"] = {}
for d, dzz in ((5.0, 2.5), (10.0, 5.0)):
    t0 = time.time()
    dm, ee, alt = monta(L, eds, d, dzz)
    rr = vl.calcula(dm, 315.0, ee)
    seg = time.time() - t0
    uu, vv = a_altura(dm, rr["u"]), a_altura(dm, rr["v"])
    f = int(d / dx)
    J, I = np.indices(refer_u.shape)
    jj, ii = J // f, I // f
    ug, vg = uu[jj, ii], vv[jj, ii]
    fila = {"celdas": int(dm.nx * dm.ny * dm.nz), "segundos": round(seg, 1), "obstaculos_que_se_ven": len(ee)}
    for radio in (50, 150):
        m = np.isfinite(ug) & np.isfinite(refer_u) & (dist < radio)
        gir = dif_rumbo(ug[m], vg[m], refer_u[m], refer_v[m])
        err = np.abs(np.hypot(ug[m], vg[m]) - np.hypot(refer_u[m], refer_v[m]))
        fila[f"a_menos_de_{radio}_m"] = {"error_vel_medio": round(float(err.mean()), 3), "error_vel_P90": round(float(np.percentile(err, 90)), 3),
                                         "giro_P90_grados": round(float(np.percentile(gir, 90)), 1)}
    res["resolucion_NO"][f"{d:g} m"] = fila
    print(f"Resolución {d} m:", res["resolucion_NO"][f"{d:g} m"], flush=True)
    figura(dm, ee, rr, vl.calcula(vl.Dominio(dm.x0, dm.y0, dm.nx, dm.ny, d, dm.nz, dzz, suelo=dm.suelo), 315.0), AQUI / f"planta_NO_{d:g}m.png", f"Viento del NO a 3 m, con edificios ({d:g} m)")
(AQUI / "resultados_planta.json").write_text(json.dumps(res, indent=1, ensure_ascii=False), encoding="utf-8")
print("Hecho", flush=True)
