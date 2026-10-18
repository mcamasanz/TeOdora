# -*- coding: utf-8 -*-
"""Deposición seca y húmeda: velocidades de deposición por celda y coeficientes de lavado.

Fuentes (ver FUENTES.md del laboratorio):
  - [UG] sec. 2.7 (ecs. 2-230 a 2-251): modelo de resistencias. Gases: vd = 1/(ra + rd + rc),
    ra = [ln(zs/z0) − ψH]/(k·u*), rd = d1·Sc^d2/(k·u*), 1/rc = LAI/rf + LAI/rcut + 1/rg, rf = rs + rm,
    rs = p/(b·D), b = bmax·S/Smax + bmin (con los límites de temperatura y el estado de la vegetación),
    rcut = (Aref/A)·rcut_ref, rg = (Aref/A)·rg_ref (tierra) o H/(α*·d3·u*) (agua), z0 sobre el agua
    = 2·10⁻⁶·u^2,5. Partículas: vd = 1/(ra + rd + ra·rd·vg) + vg, rd = 1/[(Sc^−⅔ + 10^(−3/St))·u*],
    Stokes con la corrección de Cunningham, promedio sobre NINT intervalos de la distribución
    lognormal.
  - [UG] sec. 2.9 (ecs. 2-267, 2-268): lavado Λ = λ·R/R1, con λ líquida o helada según el código de
    precipitación.
  - Caja negra (validacion/exp_deposicion.py y la salida LDEBUG=T, bloques VD1/VDP1): zs = 10 m,
    k = 0,4, d1 = 2, d2 = ⅔, d3 = 4,8·10⁻⁴, ν = 0,15 cm²/s; ψH estable −5·zs/L e inestable
    exp(0,598 + 0,39·ln(−zs/L) − 0,09·ln²(−zs/L)) (forma de Wesely y Hicks), |L| ≥ 10 m y neutra con
    |L| ≥ 9990 m (9950 m aún no); b entre bmin = 0,1 µm y bmax = 2,5 µm, lineal con la radiación hasta 600 W/m²;
    T − 273 < 10 °C: bmin; > 35 °C: bmax; IVEG = 2: bmin, IVEG = 3: sin vía estomática (salvo en
    regadío, ILANDU < 0); agua IWAT1 ≤ ILANDU ≤ IWAT2 (solo rg del agua); partículas: λ = 6,5·10⁻⁶
    cm, μ = 1,81·10⁻⁴ g/(cm·s), ρp = 1 g/cm³, T = 293,15 K en la difusividad browniana, intervalos
    de anchura 8/NINT en unidades de ln σg entre −4 y +4 con fracciones normalizadas; lavado con λ
    líquida salvo códigos de precipitación ≥ 19 (helada).
"""
import math

import numpy as np

ZS = 10.0              # m, altura de referencia
VK = 0.4               # constante de von Kármán
D1, D2, D3 = 2.0, 2.0 / 3.0, 4.8e-4
NU_CGS = 0.15          # cm2/s, viscosidad cinemática del aire
P_EST = 2.3e-8         # m2, constante estomática
BMIN, BMAX = 0.1e-6, 2.5e-6
SMAX = 600.0           # W/m2
LAMBDA_CGS = 6.5e-6    # cm, recorrido libre medio
MU_CGS = 1.81e-4       # g/(cm·s)
RHO_P = 1.0            # g/cm3
KB_CGS = 1.38e-16      # erg/K
T_BROWN = 293.15       # K
L_MIN, L_NEUTRA = 10.0, 9990.0


def ra_malla(ustar, el, z0):
    """Resistencia aerodinámica (s/m) por celda ([UG] ec. 2-237; ψH de caja negra)."""
    us = np.maximum(ustar, 1e-6)
    L = np.where(np.abs(el) < L_MIN, np.where(el < 0, -L_MIN, L_MIN), el)
    psi = np.zeros_like(L)
    est = (L > 0) & (np.abs(el) < L_NEUTRA)
    ines = (L < 0) & (np.abs(el) < L_NEUTRA)
    psi[est] = -5.0 * ZS / L[est]
    x = np.log(-ZS / L[ines])
    psi[ines] = np.exp(0.598 + 0.39 * x - 0.09 * x * x)
    return (np.log(ZS / z0) - psi) / (VK * us)


def z0_efectiva(z0, agua, ws10):
    """z0 sobre el agua en función del viento a 10 m (Hosker, [UG] ec. 2-238)."""
    return np.where(agua, 2.0e-6 * np.maximum(ws10, 1e-3) ** 2.5, z0)


def vd_gas(esp_gas, g9, ustar, el, z0, xlai, qsw, tempk, ilandu, agua, ws10):
    """Velocidad de deposición (m/s) de un gas por celda. esp_gas: (D cm2/s, α*, A, rm s/cm, H);
    g9: dict con RCUTR, RGR (s/cm), REACTR, IVEG."""
    dif, alfa, react, rm, henry = esp_gas
    dm = dif * 1e-4
    us = np.maximum(ustar, 1e-6)
    ra = ra_malla(ustar, el, z0_efectiva(z0, agua, ws10))
    sc = NU_CGS * 1e-4 / dm
    rd = D1 * sc ** D2 / (VK * us)
    rcut = g9["REACTR"] / react * g9["RCUTR"] * 100.0
    rg = g9["REACTR"] / react * g9["RGR"] * 100.0
    tc = tempk - 273.0
    riego = ilandu < 0
    b = BMIN + (BMAX - BMIN) * np.minimum(np.maximum(qsw, 0.0) / SMAX, 1.0)
    b = np.where(tc < 10.0, BMIN, np.where(tc > 35.0, BMAX, b))
    iveg = g9["IVEG"]
    if iveg == 2:
        b = np.where(riego, b, BMIN)
    rs = P_EST / (b * dm)
    inv_rf = 1.0 / (rs + rm * 100.0)
    if iveg == 3:
        inv_rf = np.where(riego, inv_rf, 0.0)
    rc_t = 1.0 / (xlai * inv_rf + xlai / rcut + 1.0 / rg)
    rc_a = henry / (alfa * D3 * us)
    rc = np.where(agua, rc_a, rc_t)
    return 1.0 / (ra + rd + rc)


def intervalos(dmm, sg, nint):
    """Intervalos de tamaño de una partícula: [(fracción, diámetro cm, vg m/s, D cm2/s)]."""
    if sg <= 0.0 or nint <= 1:
        zs, fr = [0.0], [1.0]
    else:
        dz = 8.0 / nint
        zs = [-4.0 + (i + 0.5) * dz for i in range(nint)]
        fi = lambda z: 0.5 * (1.0 + math.erf(z / math.sqrt(2.0)))
        fr = [fi(z + 0.5 * dz) - fi(z - 0.5 * dz) for z in zs]
        s = sum(fr)
        fr = [f / s for f in fr]
    out = []
    for z, f in zip(zs, fr):
        d = dmm * 1e-4 * (sg ** z if sg > 0.0 else 1.0)
        scf = 1.0 + 2.0 * LAMBDA_CGS / d * (1.257 + 0.4 * math.exp(-0.55 * d / LAMBDA_CGS))
        vg = d * d * 981.0 * RHO_P * scf / (18.0 * MU_CGS) / 100.0
        dif = KB_CGS * T_BROWN * scf / (3.0 * math.pi * MU_CGS * d)
        out.append((f, d, vg, dif))
    return out


def vd_particula(esp_part, nint, ustar, el, z0, agua, ws10):
    """Velocidad de deposición (m/s) de una partícula por celda ([UG] ecs. 2-247 a 2-251)."""
    us = np.maximum(ustar, 1e-6)
    ra = ra_malla(ustar, el, z0_efectiva(z0, agua, ws10))
    vd = np.zeros_like(ra)
    for f, d, vg, dif in intervalos(esp_part[0], esp_part[1], nint):
        sc = NU_CGS / dif
        st = (vg / 9.81) * (us * us / (NU_CGS * 1e-4))
        rd = 1.0 / ((sc ** (-2.0 / 3.0) + 10.0 ** (-3.0 / st)) * us)
        vd += f * (1.0 / (ra + rd + ra * rd * vg) + vg)
    return vd


def vg_media(esp_part, nint):
    """Velocidad de sedimentación media másica (m/s)."""
    return sum(f * vg for f, d, vg, dif in intervalos(esp_part[0], esp_part[1], nint))


def lavado(lam, rmm, ipcode):
    """Tasa de lavado Λ (1/s) por celda: λ·R/1 mm/h, λ líquida o helada según el código ([UG] sec. 2.9)."""
    helada = ipcode >= 19
    lt = np.where(helada, lam[1], lam[0])
    return np.where(rmm > 0.0, lt * rmm, 0.0)


def leer_vd(texto):
    """VD.DAT ([UG] sec. 4.7): {especie: 24 velocidades (m/s) de las horas 1 a 24}."""
    import re
    out = {}
    for m in re.finditer(r"!([^!]*)!", texto):
        c = m.group(1).strip()
        if not c or c.upper() == "END" or "=" not in c:
            continue
        k, val = c.split("=", 1)
        vals = []
        for x in val.replace(" ", "").replace("\n", "").replace("\r", "").split(","):
            if not x:
                continue
            if "*" in x:
                n, y = x.split("*", 1)
                vals += [float(y)] * int(n)
            else:
                vals.append(float(x))
        out[k.strip().upper()] = vals
    return out
