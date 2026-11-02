# Ficha del mapa al apartar el ratón

**Pregunta:** el usuario notaba que la ficha de un pueblo tardaba en irse, «como si faltase conexión». ¿Por qué?

**Causa:** al quitar una ficha, Leaflet la pone a opacidad 0 y la borra 200 ms después. La regla `opacity:1!important`, que entró con la
interfaz moderna (2026-10-31), anulaba ese 0, así que la ficha seguía entera a la vista esos 200 ms y luego desaparecía de golpe.

**Arreglo:** fuera la regla; la opacidad 1 pasa a ser la opción por defecto de la ficha (`L.Tooltip.mergeOptions`), en el mapa principal y en el plano de focos.

| Medido sin pantalla, con la página real | Tiempo a la vista tras apartar el ratón | Opacidad con la ficha abierta |
|---|---|---|
| Antes, mapa principal | 209 ms (peor 215) | 1 |
| Ahora, mapa principal | 0,7 ms (peor 3,6) | 1 |
| Ahora, plano de focos | 0,8 ms (peor 2,0) | 1 |

Con ratón de verdad, el usuario lo da por bueno (2026-11-02: «funciona perfecto»).

**Lo que no se ha medido:**
- El efecto del desenfoque de la ficha (`backdrop-filter`). Sin pantalla, quitarlo no cambió los fotogramas, pero esa medida no sirve para juzgarlo. Se deja como estaba.
- Si hay errores de GPU con la app en uso largo rato. Sin pantalla salen miles («Context lost»); en la app real, 0 en una sesión muy corta.

**Uso:** `ENCE_GALERA_DATOS=<copia de los datos> python medir_ficha.py`. Las páginas van a `%TEMP%\ence_galera\99-Test\12_ficha_mapa`.
