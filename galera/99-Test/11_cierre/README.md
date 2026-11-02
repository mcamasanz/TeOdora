# Cerrar la app con focos o planes abiertos

Lo vio el usuario el 2026-11-02: al cerrar los focos salía el diálogo de guardar y la app se quedaba sin poder cerrarse.

    set ENCE_GALERA_DATOS=<copia de los datos>
    C:\e2s\python.exe 99-Test\11_cierre\prueba_cierre.py

La X se simula con un WM_CLOSE de Windows, que es lo que manda el botón de verdad: `QWidget.close()` se salta el bloqueo de
los diálogos. Cada caso corre en su proceso, dentro de `app.exec()`, y se comprueba si la app termina sola. Nunca guarda en
`focos.json`: `focos.guardar` va sustituida. Copia y restaura el INI de la ventana.

## Lo medido antes del arreglo (2026-11-02, PC bloqueado)
- Cerrar la principal, aunque no hubiera cambios: seguían abiertas focos, planes y configuración, y la app no terminaba.
- «No guardar» en planes no descartaba: seguía con `*` y al reabrir salían los cambios (0,123 frente a 0,1 guardado).
- El diálogo era de toda la app: con él abierto, Windows ignora la X de las demás ventanas.
- Abrir y pasearse sin tocar nada NO marca cambios: el diálogo solo sale con cambios de verdad.

## Después
12 casos y 55 comprobaciones sin fallos. ⚠️ Una primera versión del arreglo perdía un plan: con la pregunta abierta,
`QWidget.close()` devuelve True sin mandar el evento (`QWindow::close` y su `inClose`), así que la principal daba por cerrada
la ventana y la app salía sin contestar. Por eso `pregunta_abierta` se mira ANTES de `close()`.

⚠️ Sin probar con ratón real: el PC estaba bloqueado. El «siempre encima» se comprueba con el estilo WS_EX_TOPMOST de Windows,
no viendo la ventana.
