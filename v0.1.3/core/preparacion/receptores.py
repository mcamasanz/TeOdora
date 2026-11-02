# -*- coding: utf-8 -*-
"""Malla de receptores ANIDADA alrededor de un centro (la planta), para los motores de dispersión.

Cada nivel es una rejilla regular (paso, semilado) con origen en el centro y solo se pone FUERA del
cuadrado del nivel interior, así que no hay receptores casi duplicados; el último nivel puede
llegar justo al borde del dominio (semilado = None). Los receptores discretos (pueblos, viviendas)
se añaden si caen dentro del dominio (con 1 m de tolerancia) y sustituyen al de la rejilla en el
mismo punto. Coordenadas en m de un UTM; redondeo a 0,1 m.
Viene del proyecto de La Galera (2026-10-23)."""
import numpy as np


def malla_anidada(centro, semilado_m, niveles, discretos=()):
    """Receptores [(x, y, clase)] ordenados por (x, y).
      centro      (x, y) en m
      semilado_m  mitad del lado del dominio de cálculo (m)
      niveles     [(clase, paso_m, semilado_m o None = todo el dominio)], de dentro afuera
      discretos   [(x, y, clase)]: se añaden en orden (el último gana) si están dentro"""
    xc, yc = centro
    puntos = {}
    interior = 0.0
    for clase, paso, radio in niveles:
        r = semilado_m if radio is None else radio
        k = np.arange(-int(np.floor(r / paso + 1e-9)), int(np.floor(r / paso + 1e-9)) + 1)
        X, Y = np.meshgrid(xc + k * paso, yc + k * paso)
        fuera = np.maximum(np.abs(X - xc), np.abs(Y - yc)) >= interior - 1e-6
        if interior == 0.0:
            fuera[:] = True
        for x, y in zip(np.round(X[fuera], 1), np.round(Y[fuera], 1)):
            puntos.setdefault((float(x), float(y)), clase)
        interior = r
    for x, y, clase in discretos:
        if abs(x - xc) <= semilado_m + 1 and abs(y - yc) <= semilado_m + 1:
            puntos[(round(float(x), 1), round(float(y), 1))] = clase
    return [(x, y, c) for (x, y), c in sorted(puntos.items())]


def resumen(receptores):
    """{"total", "por_clase": {clase: n}}"""
    cuenta = {}
    for _, _, c in receptores:
        cuenta[c] = cuenta.get(c, 0) + 1
    return {"total": len(receptores), "por_clase": cuenta}
