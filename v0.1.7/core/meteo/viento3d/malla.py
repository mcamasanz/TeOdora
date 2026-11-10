# -*- coding: utf-8 -*-
"""Malla de cálculo: centros de celda, caras y centros de las capas, gradiente del terreno.

[UG] sec. 2.1: celdas cuadradas, punto de malla en el centro de la celda, (XORIGKM, YORIGKM) es la
esquina suroeste de la celda (1,1); coordenada vertical que sigue al terreno (ec. 2-1).
"""
from dataclasses import dataclass

import numpy as np


@dataclass
class Malla:
    nx: int
    ny: int
    dx: float                  # m
    x0: float                  # m, esquina suroeste
    y0: float
    zface: np.ndarray          # (nz+1,) m sobre el suelo
    elev: np.ndarray           # (ny, nx) m

    @property
    def nz(self):
        return len(self.zface) - 1

    @property
    def zc(self):
        return 0.5 * (self.zface[1:] + self.zface[:-1])

    @property
    def xc(self):
        return self.x0 + (np.arange(self.nx) + 0.5) * self.dx

    @property
    def yc(self):
        return self.y0 + (np.arange(self.ny) + 0.5) * self.dx

    def gradiente(self):
        """dh/dx, dh/dy en el centro de cada celda: diferencias centradas; en el borde, la cota
        de la propia celda hace de vecina exterior [caja negra: dirección del ajuste de Froude en
        las celdas de borde]."""
        p = np.pad(self.elev.astype(float), 1, mode="edge")
        gx = (p[1:-1, 2:] - p[1:-1, :-2]) / (2.0 * self.dx)
        gy = (p[2:, 1:-1] - p[:-2, 1:-1]) / (2.0 * self.dx)
        return gx, gy
