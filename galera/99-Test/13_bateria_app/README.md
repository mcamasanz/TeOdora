# Batería de la aplicación

La aplicación entera, con clics simulados: paneles, capas, estilos, escalas, focos, planes, simulación, visor 3D y arranque de `main.py`. Abre ventanas
siempre encima que no cogen ni el ratón ni el teclado; se puede seguir usando el PC, aunque irá más lento. Tarda unos 30 minutos.

```bash
export ENCE_GALERA_DATOS=<copia de los datos>     # nunca los de trabajo: las pruebas guardan planes y resultados
sh regresion.sh
```

Cada prueba dice `FALLOS: ninguno` o la lista de lo que falla, y `CODIGO:` con el código que ha cargado. El cierre de la aplicación tiene su propia prueba, en `../11_cierre`.

**Los ajustes del usuario no se tocan:** las pruebas trabajan con una copia en `ENCE_AJUSTES_PRUEBA`. Lo que dejan al correr (capturas, salidas) está en `.gitignore`.
