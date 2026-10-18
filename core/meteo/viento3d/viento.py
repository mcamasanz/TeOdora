# -*- coding: utf-8 -*-
"""Módulo de viento diagnóstico (paso 1 sobre el campo inicial del pronóstico y paso 2 sin
observaciones). Procedencia de cada regla en FUENTES.md del laboratorio.

  - Flujos de ladera ([UG] ec. 2-8 a 2-16) en la dirección de drenaje (−∇h de noche, +∇h de día),
    repartidos en las capas que ocupa su espesor h = 0,05 ΔZ.
  - Bloqueo ([UG] ec. 2-17): Fr = V / (N Δh), Δh = h_max(TERRAD) − h − z_k; si Fr < CRITFN y el
    viento sube la ladera, se gira a la tangente al terreno sin cambiar la velocidad.
  - Suavizado ([UG] ec. 2-26), secuencial (Gauss-Seidel) con NSMTH pasadas por capa.
  - Velocidad vertical por continuidad ([UG] ec. 2-27).
  - O'Brien ([UG] ec. 2-28) y minimización de la divergencia con W fija ([UG] ec. 2-29 a 2-36):
    4 pasos simultáneos por iteración hasta DIVLIM o NITER [V13, V14].
  - Efectos cinemáticos (IKINE, [UG] ec. 2-3 a 2-5): W del terreno con el viento medio de la capa
    1 y decaimiento k = N/|V| con el de la capa superior, y minimización [V15].
"""
import math

import numpy as np

try:
    from numba import njit
except ImportError:                     # pragma: no cover - sin numba, mismo código en Python
    def njit(*a, **k):
        return (lambda f: f) if not a or not callable(a[0]) else a[0]

G_FR = 9.8
GRAD_MIN_FROUDE = 1.5e-4   # sin bloqueo en pendientes menores (aproximación; caja negra: rampas)


# ───────────────────────────── suavizado ─────────────────────────────
@njit(cache=True)
def _suaviza_capa(f, n, normal_x, fijas):
    """n pasadas de (2-26) en el sitio desde la esquina suroeste. Fuera del dominio, la
    componente normal al borde usa su valor previo al suavizado y la tangencial el actual. Las
    celdas `fijas` (regiones de brisa) no se suavizan [UG] sec. 2.2.2."""
    ny, nx = f.shape
    f0 = f.copy()
    for _ in range(n):
        for j in range(ny):
            for i in range(nx):
                if fijas[j, i]:
                    continue
                c = f[j, i]
                if i + 1 < nx:
                    e = f[j, i + 1]
                else:
                    e = f0[j, i] if normal_x else c
                if i > 0:
                    w = f[j, i - 1]
                else:
                    w = f0[j, i] if normal_x else c
                if j + 1 < ny:
                    nn = f[j + 1, i]
                else:
                    nn = c if normal_x else f0[j, i]
                if j > 0:
                    s = f[j - 1, i]
                else:
                    s = c if normal_x else f0[j, i]
                f[j, i] = 0.5 * c + 0.125 * (e + w + nn + s)
    return f


def suavizar(u, v, nsmth, fijas1=None):
    """fijas1: celdas de la capa 1 que no se suavizan (regiones de brisa)."""
    u = u.astype(np.float32).copy()
    v = v.astype(np.float32).copy()
    nada = np.zeros(u.shape[1:], np.bool_)
    for k in range(u.shape[0]):
        n = int(nsmth[k]) if k < len(nsmth) else int(nsmth[-1])
        if n > 0:
            fijas = fijas1 if (k == 0 and fijas1 is not None) else nada
            u[k] = _suaviza_capa(u[k], n, True, fijas)
            v[k] = _suaviza_capa(v[k], n, False, fijas)
    return u, v


# ───────────────────────────── bloqueo (Froude) ─────────────────────────────
def h_max_radio(elev, dx, radio):
    """Cota máxima de las celdas cuyo centro está a distancia <= radio (círculo inclusivo)."""
    ny, nx = elev.shape
    r = int(math.floor(radio / dx + 1e-9))
    out = elev.copy()
    for dj in range(-min(r, ny - 1), min(r, ny - 1) + 1):
        for di in range(-min(r, nx - 1), min(r, nx - 1) + 1):
            if (dj * dj + di * di) * dx * dx > radio * radio * (1 + 1e-9):
                continue
            sh = np.full_like(elev, -np.inf)
            js = slice(max(0, dj), ny + min(0, dj))
            jd = slice(max(0, -dj), ny + min(0, -dj))
            is_ = slice(max(0, di), nx + min(0, di))
            id_ = slice(max(0, -di), nx + min(0, -di))
            sh[jd, id_] = elev[js, is_]
            out = np.maximum(out, sh)
    return out


def brunt_vaisala(t, zc, zupt):
    """N del dominio con la temperatura media de la capa 1 y la interpolada a ZUPT [caja negra]."""
    tm = t.reshape(t.shape[0], -1).mean(axis=1)
    t1 = tm[0]
    tz = np.interp(zupt, zc, tm)
    n2 = G_FR / t1 * ((tz - t1) / (zupt - zc[0]) + 0.01)
    return math.sqrt(n2) if n2 > 0 else 0.0


def froude(u, v, elev, gx, gy, zc, hmax, n_bv, critfn):
    if n_bv <= 0:
        return u, v
    u = u.copy()
    v = v.copy()
    gm = np.hypot(gx, gy)
    tx = np.where(gm > 0, -gy / np.where(gm > 0, gm, 1), 0.0)
    ty = np.where(gm > 0, gx / np.where(gm > 0, gm, 1), 0.0)
    for k in range(u.shape[0]):
        dh = hmax - elev - zc[k]
        vel = np.hypot(u[k], v[k])
        with np.errstate(divide="ignore", invalid="ignore"):
            fr = np.where(dh > 0, vel / (n_bv * dh), np.inf)
        sube = (u[k] * gx + v[k] * gy) > 0
        m = (fr < critfn) & sube & (gm > GRAD_MIN_FROUDE)
        sgn = np.sign(u[k] * tx + v[k] * ty)
        sgn = np.where(sgn == 0, 1.0, sgn)
        u[k] = np.where(m, vel * tx * sgn, u[k])
        v[k] = np.where(m, vel * ty * sgn, v[k])
    return u, v


# ───────────────────────────── flujos de ladera ─────────────────────────────
CD_K_BAJADA = 0.08        # CD + k para flujos de bajada [UG] (2-13)
RHO_CP_LADERA = 1231.0    # ρ·cp fijo en los flujos de ladera [caja negra: colinas de 300 y 800 m]
PEND_MIN = math.tan(math.radians(0.5))   # pendiente mínima [caja negra: rampas]


@njit(cache=True)
def _crestas(elev, dx, radio):
    """Para cada celda: cota máxima y mínima dentro del radio (círculo inclusivo) y distancia a
    la celda más próxima que tiene la máxima."""
    ny, nx = elev.shape
    r = int(radio / dx + 1e-9)
    hmax = np.empty((ny, nx))
    hmin = np.empty((ny, nx))
    dmax = np.empty((ny, nx))
    r2 = radio * radio * (1.0 + 1e-9)
    for j in range(ny):
        for i in range(nx):
            mx = -1e30
            mn = 1e30
            dd = 1e30
            for dj in range(-r, r + 1):
                jj = j + dj
                if jj < 0 or jj >= ny:
                    continue
                for di in range(-r, r + 1):
                    ii = i + di
                    if ii < 0 or ii >= nx:
                        continue
                    d2 = (dj * dj + di * di) * dx * dx
                    if d2 > r2:
                        continue
                    e = elev[jj, ii]
                    if e < mn:
                        mn = e
                    if e > mx + 1e-9:
                        mx = e
                        dd = d2
                    elif abs(e - mx) <= 1e-9 and d2 < dd:
                        dd = d2
            hmax[j, i] = mx
            hmin[j, i] = mn
            dmax[j, i] = math.sqrt(dd)
    return hmax, hmin, dmax


def ladera(u, v, malla, gx, gy, qh, t, terrad, crestas=None):
    """Suma el flujo de ladera ([UG] 2-13 de noche, 2-16 de día) a las capas que alcanza su
    espesor h = 0,05 ΔZ, en la proporción de cada capa que ocupa."""
    elev = malla.elev.astype(float)
    hmax, hmin, x = crestas if crestas is not None else _crestas(elev, malla.dx, terrad)
    gm = np.hypot(gx, gy)
    sin_loc = gm / np.sqrt(1.0 + gm * gm)
    noche = qh < 0
    b = np.abs(qh) * 9.81 / (RHO_CP_LADERA * t)
    dz_b = hmax - elev
    with np.errstate(divide="ignore", invalid="ignore"):
        sa = np.minimum(sin_loc, np.where(x > 0, dz_b / x, 0.0))
        hh_b = 0.05 * dz_b
        le = hh_b / CD_K_BAJADA
        f = np.where(le > 0, 1.0 - np.exp(-x / np.where(le > 0, le, 1.0)), 0.0)
        s_b = np.cbrt(np.maximum(b * x * sa / CD_K_BAJADA * f, 0.0))
    dz_s = elev - hmin
    hh_s = 0.05 * dz_s
    s_s = np.cbrt(np.maximum(b * dz_s, 0.0))
    s = np.where(noche, s_b, s_s)
    hh = np.where(noche, hh_b, hh_s)
    s = np.where((gm > PEND_MIN) & np.isfinite(s), s, 0.0)
    sgn = np.where(noche, -1.0, 1.0)
    ex = np.where(gm > 0, gx / np.where(gm > 0, gm, 1), 0.0) * sgn
    ey = np.where(gm > 0, gy / np.where(gm > 0, gm, 1), 0.0) * sgn
    u = u.copy()
    v = v.copy()
    zf = malla.zface
    for k in range(u.shape[0]):
        frac = np.clip((hh - zf[k]) / (zf[k + 1] - zf[k]), 0.0, 1.0)
        u[k] = u[k] + s * frac * ex
        v[k] = v[k] + s * frac * ey
    return u, v


# ───────────────────────────── velocidad vertical ─────────────────────────────
def vertical(u, v, malla, u_prev=None, v_prev=None):
    """W (sistema que sigue al terreno) en la cara superior de cada capa por continuidad
    ([UG] 2-27, divergencia centrada como en 2-30). Fuera del dominio, la componente normal al
    borde toma el valor previo al suavizado (u_prev, v_prev) y, si no se da, el de la celda."""
    dx = malla.dx
    ue = u if u_prev is None else u_prev
    ve = v if v_prev is None else v_prev
    pu = np.concatenate([ue[:, :, :1], u, ue[:, :, -1:]], axis=2)
    pv = np.concatenate([ve[:, :1, :], v, ve[:, -1:, :]], axis=1)
    div = (pu[:, :, 2:] - pu[:, :, :-2]) / (2 * dx) + (pv[:, 2:, :] - pv[:, :-2, :]) / (2 * dx)
    dz = np.diff(malla.zface)[:, None, None]
    return -np.cumsum(div * dz, axis=0)


# ───────────────────────────── O'Brien y minimización de divergencia ─────────────────────────────
def obrien(w, zface):
    """[UG] ec. 2-28 (O'Brien, 1970): W₂(z) = W₁(z) − (z/z_top)·W₁(z_top), con W en las caras
    superiores de las capas (nula en la cima) [caja negra: exacto] [V13]."""
    zt = zface[1:] / zface[-1]
    return w - zt[:, None, None] * w[-1][None]


PASOS_POR_ITERACION = 4     # pasos simultáneos (Jacobi) por iteración [caja negra: impulso aislado]


def _divergencia(u, v, dw, dx):
    """D = dW/dz + (u(i+1) − u(i−1))/2Δx + (v(j+1) − v(j−1))/2Δy ([UG] ec. 2-30); fuera del
    dominio la vecina es la propia celda."""
    pu = np.concatenate([u[:, :1], u, u[:, -1:]], axis=1)
    pv = np.concatenate([v[:1, :], v, v[-1:, :]], axis=0)
    return dw + (pu[:, 2:] - pu[:, :-2]) / (2.0 * dx) + (pv[2:, :] - pv[:-2, :]) / (2.0 * dx)


def _minimiza_capa(u, v, dw, dx, divlim, niter):
    """Una capa: en cada paso se calcula D en todos los puntos y cada uno corrige a la vez sus
    vecinas u(i±1) ∓ D·Δx/2 y v(j±1) ∓ D·Δy/2 ([UG] ec. 2-31 a 2-36; Goodin et al., 1980), sin
    corregir las de fuera del dominio. Cada iteración son 4 pasos simultáneos y se para tras la
    primera iteración con |D| ≤ DIVLIM en toda la capa, o tras NITER [caja negra: un impulso
    aislado se reproduce exactamente con 4 pasos por iteración; el número de iteraciones hasta
    DIVLIM coincide con el que escribe el original en su fichero de prueba] [V14]."""
    if np.abs(_divergencia(u, v, dw, dx)).max() <= divlim:
        return u, v
    for it in range(niter):
        for _ in range(PASOS_POR_ITERACION):
            a = _divergencia(u, v, dw, dx) * dx / 2.0
            u[:, :-1] += a[:, 1:]
            u[:, 1:] -= a[:, :-1]
            v[:-1, :] += a[1:, :]
            v[1:, :] -= a[:-1, :]
        if np.abs(_divergencia(u, v, dw, dx)).max() <= divlim:
            break
    return u, v


def minimizar(u, v, w, malla, divlim, niter):
    """Minimización de la divergencia 3D con W fija (en las caras superiores) [V14]."""
    u = u.astype(float).copy()
    v = v.astype(float).copy()
    dz = np.diff(malla.zface)
    wb = np.concatenate([np.zeros((1,) + w.shape[1:]), w.astype(float)], 0)
    for k in range(u.shape[0]):
        dw = (wb[k + 1] - wb[k]) / dz[k]
        u[k], v[k] = _minimiza_capa(u[k], v[k], dw, float(malla.dx), float(divlim), int(niter))
    return u, v


def cinematico(u, v, malla, gx, gy, n_bv, alpha, divlim, niter):
    """Efectos cinemáticos del terreno (IKINE=1, [UG] ec. 2-2 a 2-5, Liu y Yocke, 1980): w
    cartesiana = V₁·∇h·[1 − ALPHA·(1 − e^(−k z))] con V₁ el viento de la capa 1 en la celda y
    k = N/|V_NZ| con la velocidad del viento medio de la capa superior en el dominio; en el sistema
    que sigue al terreno, W = w − u·∇h con el viento local de cada capa (W en las caras
    superiores); después, minimización de la divergencia con esa W fija [caja negra: colinas con
    viento uniforme, con perfil logarítmico y con cizalla, ALPHA = 0,1 a 0,5; con el pronóstico
    real del Prepirineo, el viento LOCAL de la capa 1 (capa 1: 5,4° frente a 0,8°)] [V15]."""
    s = math.hypot(float(np.mean(u[-1])), float(np.mean(v[-1])))
    k = n_bv / s if s > 0 else 0.0
    vg = u[0] * gx + v[0] * gy
    w = np.zeros(u.shape)
    for kk in range(u.shape[0]):
        w[kk] = vg * (1.0 - alpha * (1.0 - math.exp(-k * malla.zface[kk + 1]))) - (
            u[kk] * gx + v[kk] * gy)
    return minimizar(u, v, w, malla, divlim, niter)
