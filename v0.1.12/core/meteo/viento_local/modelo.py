# -*- coding: utf-8 -*-
"""Viento local alrededor de los edificios: modelo de masa consistente con zonas empíricas de estela.

⚠️ NO VALIDADO y fuera de los motores: no está en `teodors.MOTORES` ni se lanza con `python -m teodors`. Solo ENSEÑA el efecto de
los edificios: no da valores para un sensor y el penacho no lo usa (`dispersion.puffs` lee un solo viento). Límites: README.md.

Es el método de Röckle (1990) con las zonas de Kaplan y Dinar (1996), Pardyjak y Brown (2003) y Singh et al. (2008),
escrito desde las ecuaciones publicadas:

1. Campo inicial: perfil logarítmico neutro, con la dirección y la velocidad que se le den (en una planta, las de `viento3d`).
2. Cada edificio impone zonas con fórmulas empíricas: delante, un frenado; detrás, una cavidad con flujo inverso y una
   estela lejana con menos velocidad. ⚠️ El tamaño de la cavidad NO sale de resolver el flujo: lo da una fórmula.
3. Corrección de masa: el campo más cercano al anterior que no crea ni destruye aire y no atraviesa los sólidos
   (∇²φ = −∇·u₀, u = u₀ + ∇φ). Es lo que hace que el viento rodee los edificios y se acelere a los lados.

No resuelve ecuaciones de movimiento ni depende de la hora: con viento neutro, el campo escala con la velocidad, así que
basta una biblioteca por dirección (`biblioteca.py`). No tiene en cuenta la estabilidad.

Rejilla escalonada: u (nz, ny, nx + 1), v (nz, ny + 1, nx), w (nz + 1, ny, nx); fila j hacia el norte, columna i al este.
"""
from pathlib import Path

import numpy as np
from numba import njit, prange

KARMAN = 0.4


class Dominio:
    """Rejilla regular: x0, y0 es la esquina suroeste; `suelo` (ny, nx) es la cota del terreno sobre su mínimo, en m,
    y `altura` (ny, nx) lo que hay encima del suelo en cada celda, 0 donde no hay nada."""

    def __init__(self, x0, y0, nx, ny, dx, nz, dz, altura=None, suelo=None):
        self.x0, self.y0, self.nx, self.ny, self.dx, self.nz, self.dz = x0, y0, nx, ny, dx, nz, dz
        self.xc = x0 + (np.arange(nx) + 0.5) * dx
        self.yc = y0 + (np.arange(ny) + 0.5) * dx
        self.zc = (np.arange(nz) + 0.5) * dz
        self.suelo = np.zeros((ny, nx)) if suelo is None else suelo
        self.altura = np.zeros((ny, nx)) if altura is None else altura
        z = self.zc[:, None, None]
        self.solido = z < self.suelo[None] + self.altura[None]

    def sobre_suelo(self):
        """Altura de cada celda sobre el terreno (nz, ny, nx)."""
        return self.zc[:, None, None] - self.suelo[None]


def perfil(z, z_ref, z0):
    """Perfil logarítmico neutro relativo a la velocidad a z_ref (0 por debajo del suelo)."""
    return np.log(np.maximum(z, z0) / z0) / np.log(z_ref / z0)


def direccion_a_vector(rumbo):
    """Rumbo meteorológico (de dónde viene, grados respecto al norte de la CUADRÍCULA) → vector unitario hacia donde va."""
    a = np.radians(rumbo)
    return -np.sin(a), -np.cos(a)


def _zonas(dom, edificio, ex, ey, z_ref, z0, us, cavidad):
    """Aplica las zonas empíricas de un edificio a la velocidad en el sentido del viento `us` (nz, ny, nx)."""
    xv, yv = edificio["poligono"][:, 0], edificio["poligono"][:, 1]
    xm, ym = xv.mean(), yv.mean()
    s_v = (xv - xm) * ex + (yv - ym) * ey                      # a lo largo del viento
    t_v = -(xv - xm) * ey + (yv - ym) * ex                     # a lo ancho
    W, L, H = np.ptp(t_v), np.ptp(s_v), float(edificio["h"])
    if W < dom.dx or H <= 0:
        return
    Lf = 2.0 * W / (1.0 + 0.8 * W / H)                         # zona delantera (Röckle 1990)
    # cavidad (Fackrell 1984, como en Hosker), con el cociente acotado como en Singh et al. (2008)
    Lr = 1.8 * W / (max(L / H, 0.3) ** 0.3 * (1.0 + 0.24 * W / H))
    # superficie delantera y trasera de la huella, por banda de t
    X, Y = np.meshgrid(dom.xc, dom.yc)
    s = (X - xm) * ex + (Y - ym) * ey
    t = -(X - xm) * ey + (Y - ym) * ex
    bandas = np.linspace(t_v.min(), t_v.max(), max(int(W / dom.dx) + 1, 2))
    centros = 0.5 * (bandas[1:] + bandas[:-1])
    dentro = edificio["mascara"]
    frente, trasera = np.full(centros.shape, np.inf), np.full(centros.shape, -np.inf)
    b = np.clip(np.digitize(t[dentro], bandas) - 1, 0, len(centros) - 1)
    np.minimum.at(frente, b, s[dentro])
    np.maximum.at(trasera, b, s[dentro])
    malas = ~np.isfinite(frente)
    if malas.all():
        return
    frente[malas], trasera[malas] = s_v.min(), s_v.max()
    banda = np.clip(np.digitize(t, bandas) - 1, 0, len(centros) - 1)
    en_ancho = (t >= t_v.min()) & (t <= t_v.max())
    y_rel = np.clip(2.0 * (t - 0.5 * (t_v.min() + t_v.max())) / W, -1, 1)
    z_rel = dom.sobre_suelo()
    u_h = perfil(np.array(H), z_ref, z0)                       # velocidad a la altura del edificio
    ancho = np.sqrt(np.maximum(1.0 - y_rel ** 2, 0.0))
    for k in range(dom.nz):
        z = z_rel[k]
        if (z > H).all():
            break
        alto = np.sqrt(np.maximum(1.0 - (z / H) ** 2, 0.0))
        u_z = perfil(z, z_ref, z0)
        # estela: cavidad (flujo inverso) y estela lejana (menos velocidad), desde la superficie trasera
        x = s - trasera[banda]
        dN = Lr * alto * ancho
        zona = en_ancho & (x > 0) & (z < H) & (z > 0) & (dN > 0)
        cav = zona & (x < dN)
        lejos = zona & (x >= dN) & (x < 3.0 * dN)
        us[k][lejos] *= 1.0 - (dN[lejos] / x[lejos]) ** 1.5
        us[k][cav] = -u_h * (1.0 - x[cav] / dN[cav]) ** 2
        cavidad[k][cav] = True
        # delante: frenado dentro de un elipsoide hasta 0,6 H
        if (z < 0.6 * H).any():
            x = frente[banda] - s
            alto_f = np.sqrt(np.maximum(1.0 - (z / (0.6 * H)) ** 2, 0.0))
            cae = en_ancho & (x > 0) & (z > 0) & (z < 0.6 * H) & (alto_f > 0)
            cae[cae] = (x[cae] / (Lf * alto_f[cae])) ** 2 + y_rel[cae] ** 2 <= 1.0
            cae &= ~cavidad[k]
            us[k][cae] = 0.4 * u_z[cae]


@njit(parallel=True, cache=False)
def _sor(phi, div, solido, dx, dz, omega, n_iter, tol):
    """Poisson ∇²φ = −div con SOR rojo-negro, en paralelo. Condiciones: φ = 0 en los lados y la tapa (el aire entra y
    sale); sin flujo en el suelo y en los sólidos. Devuelve iteraciones y residuo máximo."""
    nz, ny, nx = phi.shape
    ax, az = 1.0 / dx ** 2, 1.0 / dz ** 2
    res = 0.0
    it = 0
    for it in range(n_iter):
        for color in (0, 1):
            for k in prange(nz):
                for j in range(ny):
                    for i in range((k + j + color) % 2, nx, 2):
                        if solido[k, j, i]:
                            continue
                        s, a = 0.0, 0.0
                        if i == 0:
                            a += ax
                        elif not solido[k, j, i - 1]:
                            s += ax * phi[k, j, i - 1]
                            a += ax
                        if i == nx - 1:
                            a += ax
                        elif not solido[k, j, i + 1]:
                            s += ax * phi[k, j, i + 1]
                            a += ax
                        if j == 0:
                            a += ax
                        elif not solido[k, j - 1, i]:
                            s += ax * phi[k, j - 1, i]
                            a += ax
                        if j == ny - 1:
                            a += ax
                        elif not solido[k, j + 1, i]:
                            s += ax * phi[k, j + 1, i]
                            a += ax
                        if k > 0 and not solido[k - 1, j, i]:
                            s += az * phi[k - 1, j, i]
                            a += az
                        if k == nz - 1:
                            a += az
                        elif not solido[k + 1, j, i]:
                            s += az * phi[k + 1, j, i]
                            a += az
                        if a > 0:
                            phi[k, j, i] += omega * ((s + div[k, j, i]) / a - phi[k, j, i])
        if it % 25 == 24 or it == n_iter - 1:
            res = 0.0
            for k in range(nz):
                for j in range(ny):
                    for i in range(nx):
                        if solido[k, j, i]:
                            continue
                        s, a = 0.0, 0.0
                        if i == 0:
                            a += ax
                        elif not solido[k, j, i - 1]:
                            s += ax * phi[k, j, i - 1]
                            a += ax
                        if i == nx - 1:
                            a += ax
                        elif not solido[k, j, i + 1]:
                            s += ax * phi[k, j, i + 1]
                            a += ax
                        if j == 0:
                            a += ax
                        elif not solido[k, j - 1, i]:
                            s += ax * phi[k, j - 1, i]
                            a += ax
                        if j == ny - 1:
                            a += ax
                        elif not solido[k, j + 1, i]:
                            s += ax * phi[k, j + 1, i]
                            a += ax
                        if k > 0 and not solido[k - 1, j, i]:
                            s += az * phi[k - 1, j, i]
                            a += az
                        if k == nz - 1:
                            a += az
                        elif not solido[k + 1, j, i]:
                            s += az * phi[k + 1, j, i]
                            a += az
                        r = abs(s - a * phi[k, j, i] + div[k, j, i])
                        if r > res:
                            res = r
            if res < tol:
                break
    return it + 1, res


def _a_caras(dom, uc, vc):
    """De velocidades en los centros a las caras, sin flujo a través de los sólidos ni del suelo."""
    u = np.zeros((dom.nz, dom.ny, dom.nx + 1))
    v = np.zeros((dom.nz, dom.ny + 1, dom.nx))
    w = np.zeros((dom.nz + 1, dom.ny, dom.nx))
    u[:, :, 1:-1] = 0.5 * (uc[:, :, 1:] + uc[:, :, :-1])
    u[:, :, 0], u[:, :, -1] = uc[:, :, 0], uc[:, :, -1]
    v[:, 1:-1] = 0.5 * (vc[:, 1:] + vc[:, :-1])
    v[:, 0], v[:, -1] = vc[:, 0], vc[:, -1]
    _anula_solidos(dom, u, v, w)
    return u, v, w


def _anula_solidos(dom, u, v, w):
    s = dom.solido
    u[:, :, :-1][s] = 0.0
    u[:, :, 1:][s] = 0.0
    v[:, :-1][s] = 0.0
    v[:, 1:][s] = 0.0
    w[:-1][s] = 0.0
    w[1:][s] = 0.0
    w[0] = 0.0


def _divergencia(dom, u, v, w):
    return ((u[:, :, 1:] - u[:, :, :-1]) / dom.dx + (v[:, 1:] - v[:, :-1]) / dom.dx + (w[1:] - w[:-1]) / dom.dz)


def calcula(dom, rumbo, edificios=(), z_ref=10.0, z0=0.25, vel=1.0, omega=1.85, n_iter=4000, tol=1e-4, dosel=None,
            a_dosel=1.5):
    """Campo de viento para una dirección. `edificios`: [{"poligono": (n, 2) en m, "h": altura, "mascara": (ny, nx)}];
    `dosel` (ny, nx): altura de los árboles, que frenan el aire sin ser sólidos (Cionco 1965: u = u(h)·exp(a·(z/h − 1))).
    Devuelve {u, v, w en los centros (nz, ny, nx), iteraciones, residuo, div_antes, div_despues}."""
    ex, ey = direccion_a_vector(rumbo)
    z = dom.sobre_suelo()
    us = perfil(z, z_ref, z0)
    if dosel is not None:
        hay = dosel > 0
        for k in range(dom.nz):
            dentro = hay & (z[k] > 0) & (z[k] < dosel)
            if not dentro.any():
                continue
            us[k][dentro] = perfil(dosel[dentro], z_ref, z0) * np.exp(a_dosel * (z[k][dentro] / dosel[dentro] - 1.0))
    cavidad = np.zeros(us.shape, dtype=bool)
    # de barlovento a sotavento: lo que está más abajo en el flujo actúa sobre lo que ya llega frenado
    orden = sorted(edificios, key=lambda e: (e["poligono"][:, 0].mean() * ex + e["poligono"][:, 1].mean() * ey))
    for e in orden:
        _zonas(dom, e, ex, ey, z_ref, z0, us, cavidad)
    u, v, w = _a_caras(dom, us * ex, us * ey)
    div = _divergencia(dom, u, v, w)
    div[dom.solido] = 0.0
    antes = float(np.abs(div).max())
    phi = np.zeros(dom.solido.shape)
    n, res = _sor(phi, div, dom.solido, dom.dx, dom.dz, omega, n_iter, tol)
    u[:, :, 1:-1] += (phi[:, :, 1:] - phi[:, :, :-1]) / dom.dx
    u[:, :, 0] += phi[:, :, 0] / dom.dx
    u[:, :, -1] -= phi[:, :, -1] / dom.dx
    v[:, 1:-1] += (phi[:, 1:] - phi[:, :-1]) / dom.dx
    v[:, 0] += phi[:, 0] / dom.dx
    v[:, -1] -= phi[:, -1] / dom.dx
    w[1:-1] += (phi[1:] - phi[:-1]) / dom.dz
    w[-1] -= phi[-1] / dom.dz
    _anula_solidos(dom, u, v, w)
    d = _divergencia(dom, u, v, w)
    d[dom.solido] = 0.0
    uc = vel * 0.5 * (u[:, :, 1:] + u[:, :, :-1])
    vc = vel * 0.5 * (v[:, 1:] + v[:, :-1])
    wc = vel * 0.5 * (w[1:] + w[:-1])
    return {"u": uc, "v": vc, "w": wc, "iteraciones": n, "residuo": float(res), "div_antes": antes,
            "div_despues": float(np.abs(d).max()), "cavidad": cavidad}


# ── de la nube de puntos a la rejilla de cálculo ────────────
def lee_lidar(ruta):
    """Rejillas de 1 m: terreno, altura sobre el suelo, altura de los edificios y puntos clasificados como edificio.

    La altura de los edificios (`obstaculo`) sale de los puntos de esa clase, y en la celda de al lado no pasa del techo
    vecino: con el punto más alto de cada celda, los cables de alta tensión levantaban un cobertizo de 3 m a 31 m (medido en una
    planta real). `ruta`: un .npz con las rejillas `dsm`, `dtm`, `dsm_edif` y `edificio` y su esquina suroeste `x0`, `y0`.
    Necesita scipy (`teodors[viento_local]`)."""
    from scipy.interpolate import NearestNDInterpolator
    from scipy.ndimage import gaussian_filter, maximum_filter

    z = np.load(Path(ruta))
    dsm, dtm, x0, y0 = z["dsm"], z["dtm"], float(z["x0"]), float(z["y0"])
    n = dsm.shape[0]
    j, i = np.nonzero(np.isfinite(dtm))
    J, I = np.mgrid[:n, :n]
    ter = gaussian_filter(NearestNDInterpolator(np.c_[i, j], dtm[j, i])(I, J), 3)
    alto = np.clip(np.where(np.isfinite(dsm), dsm, ter) - ter, 0, None)
    techo = np.clip(np.where(np.isfinite(z["dsm_edif"]), z["dsm_edif"], ter) - ter, 0, None)
    obstaculo = np.minimum(np.where(z["edificio"] > 0, techo, alto), maximum_filter(techo, size=3))
    return {"terreno": ter, "alto": alto, "obstaculo": obstaculo, "edif": z["edificio"], "x0": x0, "y0": y0, "n": n}


def _misma_cubierta(alto, suave, a, b, parecidos=0.6, baja=0.5, sube=1.25):
    """¿Dos picos son del mismo tejado? Tienen alturas parecidas y, por la recta que los une, ni se baja de `baja` veces el
    menor ni se sube de `sube` veces el mayor (la recta cruzaría algo más alto). Medido en una planta real: entre depósitos
    pegados se baja a 0-0,22 del menor; en los dientes de sierra de unas naves, nunca de 0,56. Dos tanques de alturas muy
    distintas con otros más altos en medio dan 0,83: por eso lo de las alturas parecidas."""
    ha, hb = suave[tuple(a)], suave[tuple(b)]
    if min(ha, hb) < parecidos * max(ha, hb):
        return False
    t = np.linspace(0.0, 1.0, int(np.hypot(*(a - b))) + 2)
    z = alto[np.round(a[0] + t * (b[0] - a[0])).astype(int), np.round(a[1] + t * (b[1] - a[1])).astype(int)]
    return z.min() >= baja * min(ha, hb) and z.max() <= sube * max(ha, hb)


def obstaculos(L):
    """Lo clasificado como edificio y que levanta del suelo, separando los depósitos que se tocan. Necesita scipy
    (`teodors[viento_local]`). ⚠️ Sus umbrales salen de una sola planta: mirar el resultado antes de usarlos en otra."""
    from scipy.ndimage import binary_dilation, gaussian_filter, label, maximum_filter
    from scipy.spatial import ConvexHull

    alto = L["obstaculo"]
    m = (alto > 2.5) & binary_dilation(L["edif"] > 0, iterations=1)
    lab, n = label(m)
    suave = gaussian_filter(alto, 2)
    picos = (suave == maximum_filter(suave, size=13)) & (suave > 4)
    salida = []
    for k in range(1, n + 1):
        pieza = lab == k
        if pieza.sum() < 20:
            continue
        p = np.argwhere(picos & pieza)
        if pieza.sum() > 800 and len(p) > 1:   # un racimo: cada celda, al pico más cercano, y los de un mismo tejado juntos
            grupo = list(range(len(p)))

            def raiz(q):
                while grupo[q] != q:
                    q = grupo[q]
                return q

            for a in range(len(p)):
                for b in range(a + 1, len(p)):
                    if _misma_cubierta(alto, suave, p[a], p[b]):
                        grupo[raiz(a)] = raiz(b)
            jj, ii = np.nonzero(pieza)
            d = (jj[:, None] - p[:, 0]) ** 2 + (ii[:, None] - p[:, 1]) ** 2
            cerca = np.array([raiz(q) for q in range(len(p))])[d.argmin(axis=1)]
            for q in np.unique(cerca):
                t = np.zeros_like(pieza)
                t[jj[cerca == q], ii[cerca == q]] = True
                salida.append(t)
        else:
            salida.append(pieza)
    res = []
    for t in salida:
        jj, ii = np.nonzero(t)
        xy = np.c_[ii + L["x0"] + 0.5, jj + L["y0"] + 0.5]
        if len(xy) < 20:
            continue
        pol = xy[ConvexHull(xy).vertices]
        res.append({"masc_1m": t, "poligono": pol, "h": float(np.percentile(alto[t], 95)), "area": int(t.sum()),
                    "centro": [float(xy[:, 0].mean()), float(xy[:, 1].mean())]})
    return sorted(res, key=lambda e: -e["area"])


def a_rejilla(L, campo, dx, centro, semilado, cubierta=None):
    """De 1 m a la rejilla de cálculo: (suma, cuenta, x_ini, y_ini, ny, nx). `semilado`: un valor o (este-oeste, norte-sur);
    `cubierta` limita la suma a esas celdas de 1 m."""
    sx, sy = semilado if isinstance(semilado, tuple) else (semilado, semilado)
    x_ini, y_ini = centro[0] - sx, centro[1] - sy
    nx, ny = int(2 * sx / dx), int(2 * sy / dx)
    J, I = np.mgrid[:L["n"], :L["n"]]
    i = np.floor((I + L["x0"] + 0.5 - x_ini) / dx).astype(int)
    j = np.floor((J + L["y0"] + 0.5 - y_ini) / dx).astype(int)
    ok = (i >= 0) & (i < nx) & (j >= 0) & (j < ny)
    if cubierta is not None:
        ok &= cubierta
    s, c = np.zeros((ny, nx)), np.zeros((ny, nx))
    np.add.at(s, (j[ok], i[ok]), campo[ok])
    np.add.at(c, (j[ok], i[ok]), 1)
    return s, c, x_ini, y_ini, ny, nx


def monta(L, eds, dx, dz, centro, semilado, con_relieve=True, alto_tapa=60.0):
    """(dominio, edificios que caben en la rejilla, altura por celda)."""
    ter, c_t, x_ini, y_ini, ny, nx = a_rejilla(L, L["terreno"], dx, centro, semilado)
    ter = ter / np.maximum(c_t, 1)
    suelo = ter - ter.min() if con_relieve else np.zeros_like(ter)
    altura = np.zeros((ny, nx))
    editados = []
    for e in eds:
        s, c, *_ = a_rejilla(L, L["obstaculo"], dx, centro, semilado, cubierta=e["masc_1m"])
        cubre = c >= 0.5 * dx ** 2
        if not cubre.any():
            continue
        altura[cubre] = np.maximum(altura[cubre], s[cubre] / c[cubre])
        editados.append({"poligono": e["poligono"], "h": e["h"], "mascara": cubre})
    nz = int(np.ceil((suelo.max() + alto_tapa) / dz))
    dom = Dominio(x_ini, y_ini, nx, ny, dx, nz, dz, altura=altura, suelo=suelo)
    return dom, editados, altura


def a_altura(dom, campo, z=3.0):
    """Una capa a `z` metros sobre el suelo, interpolando en la vertical (si la celda de abajo es sólida, la de arriba:
    con capas gruesas no hay más); NaN dentro de los edificios."""
    zk = (dom.suelo + z) / dom.dz - 0.5
    k = np.clip(np.floor(zk).astype(int), 0, dom.nz - 2)
    f = np.clip(zk - k, 0.0, 1.0)
    J, I = np.indices(k.shape)
    v = (1.0 - f) * campo[k, J, I] + f * campo[k + 1, J, I]
    abajo = dom.solido[k, J, I]
    v[abajo] = campo[k + 1, J, I][abajo]
    v[dom.altura > z] = np.nan
    return v
