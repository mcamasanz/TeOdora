# -*- coding: utf-8 -*-
"""La aplicación de escritorio de una planta (`teodors[gui]`: PySide6 y folium). No es un motor. Importar el paquete no carga Qt, y nada fuera de este paquete lo carga.

    principal      el arranque: lo que llama el main.py de cada planta
    ventana        la ventana principal: barra superior, panel, mapa y registro de actividad
    panel          el panel, por páginas: Inicio, Planta, Focos, Meteo, Simular y 3D, y el reproductor
    mapa, mapa_web el mapa principal: la vista, con su puente JavaScript ↔ Python (`window.mapaApp`), y su página
    focos_mapa     el plano de la ventana de focos
    ventana_focos, ventana_planes, ventana_ajustes   las otras ventanas
    vista_previa   el mapa de la ventana de configuración, con el ejemplo de la planta
    vista_3d, penacho_3d   el visor 3D en la zona central, y la página que enseña
    tema           los estilos: colores, letra e iconos, que se cambian con la app abierta
    widgets, consola, terminal, trabajos, web   piezas: widgets pequeños, registro de actividad, terminal, hilos, HTML sin CDN

Lo de cada planta sale de su carpeta (ver el README).
"""
