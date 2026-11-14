# -*- coding: utf-8 -*-
"""Biblioteca del viento local: un campo a una altura fija por dirección, para no calcular las horas una a una.

⚠️ NO VALIDADO y fuera de los motores. Solo ENSEÑA el efecto de los edificios: no da valores para un sensor y el penacho no lo usa.

Cada instante, la dirección y la velocidad del viento de la zona eligen los dos campos más cercanos y se mezclan (`mezcla`). Cada
campo va relativo al viento SIN edificios a esa misma altura: lejos de ellos vale 1 y empalma con la zona sin un círculo donde el
viento se frene de golpe. Por eso NO es la velocidad real a esa altura: no leer de aquí valores para un sensor.

Lo propio de cada planta (puntos, radios, resolución, rutas) llega por parámetro: `parametros` lo saca de su bloque `viento_local` de
planta.json. Desde un proyecto, con su planta activa:

    from teodors import planta
    from teodors.meteo.viento_local import biblioteca
    biblioteca.main(activa=planta.actual())       # --lidar <rejillas de 1 m> --paso <grados entre direcciones>
"""
import argparse
import time
from pathlib import Path

import numpy as np

from . import modelo

ESCALA = 1e-3                          # int16: de −32,8 a +32,8 veces el viento de entrada
SOLIDO = -32768                        # dentro de un edificio


def _pide(bloque, clave):
    try:
        return bloque[clave]
    except KeyError:
        raise ValueError(f"planta.json: falta viento_local.{clave}") from None


def parametros(bloque, carpeta):
    """Del bloque `viento_local` de planta.json a los argumentos de `principal`, salvo `lidar` y `paso`. `carpeta`: la de la planta,
    de la que cuelga `biblioteca`. Sin valores por defecto: dependen del sitio y uno equivocado no se notaría."""
    puntos = [(float(x), float(y)) for x, y in _pide(bloque, "puntos")]
    if len(puntos) != 2 or puntos[0] == puntos[1]:
        raise ValueError("viento_local.puntos: hacen falta dos puntos distintos, los extremos del segmento")
    radio, radio_borde = float(_pide(bloque, "radio_m")), float(_pide(bloque, "radio_borde_m"))
    if radio_borde <= radio:
        raise ValueError("viento_local: radio_borde_m tiene que ser mayor que radio_m")
    return {"puntos": puntos, "radio": radio, "radio_borde": radio_borde, "margen": float(_pide(bloque, "margen_m")),
            "dx": float(_pide(bloque, "dx")), "dz": float(_pide(bloque, "dz")), "alto": float(_pide(bloque, "alto_m")),
            "salida": Path(carpeta) / _pide(bloque, "biblioteca")}


def zona(puntos, radio_borde, margen):
    """Rectángulo de cálculo alrededor de los dos `puntos`: (centro, semilado este-oeste y norte-sur), en m."""
    centro = ((puntos[0][0] + puntos[1][0]) / 2, (puntos[0][1] + puntos[1][1]) / 2)
    semilado = (abs(puntos[0][0] - puntos[1][0]) / 2 + radio_borde + margen, abs(puntos[0][1] - puntos[1][1]) / 2 + radio_borde + margen)
    return centro, semilado


def principal(lidar, paso, puntos, radio, radio_borde, margen, dx, dz, alto, salida):
    """Calcula y guarda la biblioteca. `lidar`: las rejillas de 1 m (`modelo.lee_lidar`); `paso`: grados entre direcciones;
    `puntos`: extremos del segmento alrededor del que manda este modelo; `radio`, `radio_borde`: m hasta los que manda y hasta
    los que se funde con el viento de la zona; `margen`: m de cálculo por fuera, para que las zonas de los edificios no toquen
    el borde; `dx`, `dz`: celda, ⚠️ con unas 4 por obstáculo como poco; `alto`: m sobre el suelo. Los da `parametros`."""
    salida = Path(salida)
    centro, semilado = zona(puntos, radio_borde, margen)
    L = modelo.lee_lidar(lidar)
    dom, eds, _ = modelo.monta(L, modelo.obstaculos(L), dx, dz, centro, semilado)
    rumbos = np.arange(0.0, 360.0, paso)
    borde = int(margen / dx)
    corta = (slice(borde, dom.ny - borde), slice(borde, dom.nx - borde))
    sin_edificios = float(modelo.perfil(np.array(alto), 10.0, 0.25))         # los valores de modelo.calcula por defecto
    us, vs = [], []
    t0 = time.time()
    for k, r in enumerate(rumbos):
        c = modelo.calcula(dom, float(r), eds)
        for campo, lista in ((c["u"], us), (c["v"], vs)):
            a = modelo.a_altura(dom, campo, alto)[corta] / sin_edificios
            lista.append(np.where(np.isfinite(a), np.round(np.nan_to_num(a) / ESCALA), SOLIDO).astype(np.int16))
        print(f"{r:5.0f}° · {c['iteraciones']} iteraciones · divergencia {c['div_despues']:.1e} · {time.time() - t0:.0f} s", flush=True)
    np.savez_compressed(salida, u=np.array(us), v=np.array(vs), paso=paso, x0=dom.xc[borde], y0=dom.yc[borde], dx=dx,
                        cx=puntos[0][0], cy=puntos[0][1], cx2=puntos[1][0], cy2=puntos[1][1], radio=radio, radio_borde=radio_borde,
                        escala=ESCALA, solido=SOLIDO, alto=alto)
    print(f"{salida}: {salida.stat().st_size / 1e6:.2f} MB · {len(rumbos)} direcciones · {us[0].shape} celdas · {len(eds)} edificios")


def lee(ruta):
    """La biblioteca: `u`, `v` (direcciones, ny, nx) relativos al viento de entrada, con NaN dentro de los edificios, y sus datos."""
    with np.load(ruta) as z:
        lib = {k: z[k].item() for k in z.files if k not in ("u", "v")}
        for k in ("u", "v"):
            lib[k] = np.where(z[k] == lib["solido"], np.nan, z[k] * lib["escala"]).astype(np.float32)
    return lib


def mezcla(lib, u, v):
    """Campo para un viento (u, v) de la zona, en m/s: su dirección elige los dos campos más cercanos, los mezcla en proporción a lo
    cerca que está de cada uno y la velocidad lo escala. NaN donde alguno de los dos tiene un edificio. Devuelve (u, v) en (ny, nx)."""
    n = len(lib["u"])
    vel = np.hypot(u, v)
    a = ((np.degrees(np.arctan2(-u, -v)) + 360.0) % 360.0) / lib["paso"]
    k0, f = int(np.floor(a)) % n, a - np.floor(a)
    k1 = (k0 + 1) % n
    return (vel * (lib["u"][k0] + (lib["u"][k1] - lib["u"][k0]) * f),
            vel * (lib["v"][k0] + (lib["v"][k1] - lib["v"][k0]) * f))


def main(argv=None, activa=None):
    """Línea de órdenes con la planta `activa`: --lidar y --paso, y lo demás de su bloque `viento_local`. Se le pasa la planta porque
    este paquete, como los motores, no depende de ninguna."""
    bloque = activa.bloque("viento_local")
    p = parametros(bloque, activa.PLANTA)
    a = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    a.add_argument("--lidar", default=str(activa.PLANTA / _pide(bloque, "lidar")))
    a.add_argument("--paso", type=float, default=10.0)
    A = a.parse_args(argv)
    principal(A.lidar, A.paso, **p)
