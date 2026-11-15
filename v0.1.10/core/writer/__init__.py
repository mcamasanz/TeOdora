# -*- coding: utf-8 -*-
"""writer: el informe en PDF de un caso (usuario, 2026-11-10: «exista un script que lo haga de forma automática, dentro de teOdors core en
writer»). Cada TIPO de informe vive AISLADO en su subcarpeta (usuario, 2026-11-12: para ajustar tamaños, formatos, textos y gráficos de cada uno
por separado), con sus propias `paginas`, `textos`, `graficas`, `estilo` y `capturas`:

    reanalisis_caso/          el informe de un caso del reanálisis (los años completos: P98, calendario anual)
    reanalisis_comparacion/   el informe de la comparación de dos escenarios del reanálisis
    episodio/                 el informe de un episodio (el día de la queja: máximo, calendario de 3 días, penacho)
    prediccion/               (pendiente) el informe de un escenario de predicción; por ahora solo la carpeta

Y lo COMPARTIDO, en la raíz:

    datos      lo que necesita el informe, de la carpeta del caso y de la planta (sin Qt)
    pdf        del HTML al PDF con el motor web de la app (Qt, al usarlo)
    informe    todo junto, el enrutado por tipo (`crear`) y la línea de órdenes: python -m teodors.writer CARPETA_DEL_CASO
    estilo / textos / graficas   base que necesita `datos` (cada subcarpeta tiene además su copia propia)

Importar el paquete no carga Qt: solo `capturas`, `pdf` e `informe` lo usan, y al llamarlos.
"""
