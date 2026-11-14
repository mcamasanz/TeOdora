# -*- coding: utf-8 -*-
"""auditor — la puerta de entrada a la rama principal de teOdors.

Ningún cambio entra en `main` si rompe una prueba existente, si no trae pruebas nuevas para el
código que añade o modifica, si cambia una referencia sin justificarlo o si sus pruebas no son
rápidas. Ver auditor/README.md.

    python -m auditor                  # todas las reglas frente a la rama main
    python -m auditor --base v0.1.0    # frente a otra referencia de git
    python -m auditor --solo-pruebas   # solo las pruebas y sus tiempos
"""
