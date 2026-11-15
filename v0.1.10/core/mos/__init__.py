# -*- coding: utf-8 -*-
"""Corrección estadística de la predicción de GFS en cada estación (MOS). No es un motor.

    tabla     tabla de entrenamiento GFS → estaciones, partición por semanas y error de GFS sin corregir (también por línea de órdenes)
    entrenar  modelos por estación y sus métricas en las semanas de validación (también por línea de órdenes)

Importarlos no lee la planta ni carga scikit-learn, joblib o xarray. ⚠️ La mejora de dirección es LOCAL a la estación: ver README.md.
"""
