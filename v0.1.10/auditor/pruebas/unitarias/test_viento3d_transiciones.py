# -*- coding: utf-8 -*-
"""meteo.viento3d · horas de transición (amanecer y atardecer) con ITPROG = 1, 2: N del bloqueo con
la convectiva de la hora anterior en ZUPT y θ de la temperatura 3D por debajo del primer nivel del
pronóstico. Las comprobaciones frente al original están en el README del motor (§Transiciones)."""
import math

import numpy as np

from teodors.meteo.viento3d import principal, viento

ZC = np.array([10.0, 30.0, 50.0, 75.0, 110.0, 165.0, 250.0, 400.0])


def _perfil(gradiente=-0.004, t1=290.0, forma=(3, 4)):
    """Temperatura por capas con un gradiente constante (K/m), igual en todas las celdas."""
    return (t1 + gradiente * (ZC - ZC[0]))[:, None, None] * np.ones((1,) + forma)


def test_theta_capas_exacta_en_los_centros_y_lineal_por_debajo_del_primero():
    t = _perfil(gradiente=-0.004)
    th = principal._theta_capas(t, ZC)
    for k, z in enumerate(ZC):
        np.testing.assert_allclose(th(np.full((3, 4), z)), t[k] + 0.0098 * z, atol=1e-9)
    # por debajo del primer centro sigue la recta de los dos primeros (no queda constante)
    esperado = t[0] + 0.0098 * ZC[0] - (0.0098 - 0.004) * ZC[0]
    np.testing.assert_allclose(th(np.zeros((3, 4))), esperado, atol=1e-9)


def test_n_zupt_sin_convectiva_es_la_del_perfil():
    t = _perfil(gradiente=-0.004)
    n = principal._n_zupt(t, np.zeros((3, 4)), ZC, 200.0)
    assert math.isclose(n, viento.brunt_vaisala(t, ZC, 200.0), rel_tol=1e-12)
    assert math.isclose(n, math.sqrt(viento.G_FR / 290.0 * (-0.004 + 0.01)), rel_tol=1e-9)


def test_n_zupt_convectiva_por_debajo_de_zupt_no_ajusta():
    # una convectiva que cubre la capa de 165 m pero no llega a ZUPT no cambia la N (amanecer)
    t = _perfil(gradiente=-0.004)
    n0 = principal._n_zupt(t, np.zeros((3, 4)), ZC, 200.0)
    assert principal._n_zupt(t, np.full((3, 4), 180.0), ZC, 200.0) == n0


def test_n_zupt_convectiva_sobre_zupt_es_adiabatica():
    t = _perfil(gradiente=0.002)
    n = principal._n_zupt(t, np.full((3, 4), 900.0), ZC, 200.0)
    assert math.isclose(n, math.sqrt(viento.G_FR / 290.0 * (-0.0098 + 0.01)), rel_tol=1e-9)
    # mitad de las celdas con convectiva: T(ZUPT) media de las dos
    h = np.zeros((3, 4))
    h[:, :2] = 900.0
    g = 0.5 * (0.002 + -0.0098)
    assert math.isclose(principal._n_zupt(t, h, ZC, 200.0),
                        math.sqrt(viento.G_FR / 290.0 * (g + 0.01)), rel_tol=1e-9)


def test_constantes_de_transicion_por_defecto():
    assert principal.N_CON_ALTURA_ANTERIOR and principal.N_MASCARA == "zupt"
    assert principal.PSI_DE_T3D == "bajo_primer_nivel" and principal.T3D_CON_PROMEDIADA
