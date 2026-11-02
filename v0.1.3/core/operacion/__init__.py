# -*- coding: utf-8 -*-
"""La operación de una planta, sin interfaz: lo que hace falta para pasar de sus focos y sus planes a lo que dice la norma en cada receptor. No son motores.

    focos                  tipos de foco, su fichero y sus unidades
    planes                 cómo emiten los focos: planes diarios, semanales o mensuales, en hora oficial
    normativa              qué se enseña de cada magnitud y con qué límite se compara
    periodos               el periodo de una simulación: reanálisis, episodio o predicción
    simulacion             del plan y las respuestas de los focos a los resultados, sin lanzar el motor
    penacho_mapa           las imágenes de concentración y su leyenda
    viento_mapa            el viento en superficie, para la capa del mapa
    penacho_3d             el penacho en 3D: aquí sí se lanza el motor
    respuestas             respuesta de cada foco a una emisión unidad en cada hora (por línea de órdenes)
    viento_periodo         viento 3D de un periodo (por línea de órdenes)
    viento3d_series        series de viento 3D de los años del reanálisis (por línea de órdenes)
    ejemplo_configuracion  el ejemplo de la ventana de configuración (por línea de órdenes)

Importarlos no lee la planta. Las tareas por línea de órdenes usan la de TEODORS_PLANTA.
"""
