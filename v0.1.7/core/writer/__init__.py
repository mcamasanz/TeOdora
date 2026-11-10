# -*- coding: utf-8 -*-
"""writer: el informe en PDF de un caso (usuario, 2026-11-10: «exista un script que lo haga de forma automática, dentro de teOdors core en
writer»). Por ahora, el de un caso del reanálisis; el de un episodio de queja y el de una predicción, más adelante.

    datos      lo que necesita el informe, de la carpeta del caso y de la planta (sin Qt)
    textos     los textos que salen solos de los datos: lo esencial del caso, el relieve y los usos (sin Qt)
    paginas    las páginas en HTML, A4 (sin Qt)
    estilo     colores y hoja de estilos (sin Qt)
    graficas   las gráficas en SVG: el tiempo en la planta, día a día (sin Qt)
    capturas   las imágenes, de la app misma: mapas, visores 3D y fichas (Qt, al usarlo)
    pdf        del HTML al PDF con el motor web de la app (Qt, al usarlo)
    informe    todo junto, y la línea de órdenes: python -m teodors.writer CARPETA_DEL_CASO

Importar el paquete no carga Qt: solo `capturas`, `pdf` e `informe` lo usan, y al llamarlos.
"""
