# -*- coding: utf-8 -*-
"""Estilos visuales de toda la app (rama interfaz-moderna, pedido del usuario, 2026-10-31: «una gui más
atractiva, práctica, que apetezca quedarse con la app abierta»).

Un solo sitio para colores, letra e iconos, con varios estilos a elegir en la ventana de configuración.
No dependen de Windows en modo claro u oscuro: `setColorScheme` y Fusion evitan que la paleta del sistema
cambie nada (ver el fallo de la ventana de focos del 2026-10-31). La página del mapa toma los mismos colores
de `css_variables`.

**Se cambia de estilo con la app abierta** (`poner`), sin reiniciar. Para que eso funcione, lo que lleve
colores se pone con estas funciones y no a mano, porque guardan el NOMBRE del color y se rehacen solas:
`pon_icono` (iconos), `texto` (texto enriquecido con $tenue, $aviso…) y `estilo` (hoja de estilos de un
widget). Lo que no es un widget escucha `avisos.cambiado` (los mapas, la consola, las acciones de menú).
Pintar con `c("tenue")` dentro de un paintEvent también vale: se lee al pintar.
"""
import json
from string import Template

from PySide6 import QtCore, QtGui, QtSvg, QtWidgets

from teodors import planta as config
from teodors.comun import escalas

# acento_claro: el acento para TEXTO sobre `tinte` (en los estilos claros es más oscuro que el acento).
# cristal: fondo translúcido de los controles del mapa; fam_*: punto de cada tipo de núcleo en el panel.
TEMAS = {
    "oscuro": {
        "nombre": "Oscuro",
        "esquema": "oscuro", "colores": {
            "fondo": "#101412", "superficie": "#181d1b", "elevada": "#212826", "hover": "#2a3230",
            "borde": "#2f3835", "borde_fuerte": "#46514d",
            "texto": "#eef2ee", "tenue": "#a7b2ac", "apagado": "#6f7b75",
            "acento": "#59c9a5", "acento_claro": "#7fdcbd", "sobre_acento": "#07201a", "tinte": "#1d3a31",
            "aviso": "#f2b84b", "tinte_aviso": "#332a14", "fallo": "#f28b82", "tinte_fallo": "#3a1f1d",
            "barra_inactiva": "#46514d",
            "cristal": "rgba(24,29,27,.84)", "cristal_solido": "rgba(24,29,27,.95)",
            "cristal_suave": "rgba(16,20,18,.62)", "linea": "rgba(255,255,255,.11)",
            "chip": "rgba(16,20,18,.86)", "sombra": "rgba(0,0,0,.38)", "estacion": "#4fd1c5",
            "fam_residencial": "#7cc0ff", "fam_industrial": "#f2b84b", "fam_deportivo": "#f59e6b"}},
    "claro": {
        "nombre": "Claro",
        "esquema": "claro", "colores": {
            "fondo": "#f3f5f3", "superficie": "#ffffff", "elevada": "#edf0ed", "hover": "#e2e7e3",
            "borde": "#d5dbd6", "borde_fuerte": "#aeb8b1",
            "texto": "#17201c", "tenue": "#515e57", "apagado": "#87928b",
            "acento": "#0d7f60", "acento_claro": "#0a6a50", "sobre_acento": "#ffffff", "tinte": "#d9f1e8",
            "aviso": "#7f5200", "tinte_aviso": "#fcf0d4", "fallo": "#ad231b", "tinte_fallo": "#fbe5e3",
            "barra_inactiva": "#c6cec8",
            "cristal": "rgba(255,255,255,.88)", "cristal_solido": "rgba(255,255,255,.97)",
            "cristal_suave": "rgba(255,255,255,.74)", "linea": "rgba(20,40,30,.16)",
            "chip": "rgba(255,255,255,.95)", "sombra": "rgba(20,40,30,.24)", "estacion": "#0f766e",
            "fam_residencial": "#1d6fc2", "fam_industrial": "#a86400", "fam_deportivo": "#c2410c"}},
    "noche": {
        "nombre": "Azul noche",
        "esquema": "oscuro", "colores": {
            "fondo": "#0d1421", "superficie": "#141d2e", "elevada": "#1c2840", "hover": "#25334f",
            "borde": "#2a3854", "borde_fuerte": "#43557a",
            "texto": "#e9eef7", "tenue": "#a3b1c9", "apagado": "#6c7b96",
            "acento": "#5aa9f7", "acento_claro": "#8cc4fb", "sobre_acento": "#061426", "tinte": "#18304f",
            "aviso": "#f2b84b", "tinte_aviso": "#33290f", "fallo": "#f28b82", "tinte_fallo": "#3a1f24",
            "barra_inactiva": "#43557a",
            "cristal": "rgba(20,29,46,.86)", "cristal_solido": "rgba(20,29,46,.96)",
            "cristal_suave": "rgba(13,20,33,.64)", "linea": "rgba(200,220,255,.14)",
            "chip": "rgba(13,20,33,.88)", "sombra": "rgba(0,0,0,.42)", "estacion": "#5eead4",
            "fam_residencial": "#8cc4fb", "fam_industrial": "#f2b84b", "fam_deportivo": "#f59e6b"}},
    "contraste": {
        "nombre": "Alto contraste",
        "esquema": "oscuro", "colores": {
            "fondo": "#000000", "superficie": "#0b0b0b", "elevada": "#191919", "hover": "#2a2a2a",
            "borde": "#5c5c5c", "borde_fuerte": "#929292",
            "texto": "#ffffff", "tenue": "#dadada", "apagado": "#9c9c9c",
            "acento": "#ffd400", "acento_claro": "#ffe566", "sobre_acento": "#000000", "tinte": "#332b00",
            "aviso": "#ffb000", "tinte_aviso": "#2e2000", "fallo": "#ff7b7b", "tinte_fallo": "#3a1010",
            "barra_inactiva": "#5c5c5c",
            "cristal": "rgba(0,0,0,.90)", "cristal_solido": "rgba(0,0,0,.97)",
            "cristal_suave": "rgba(0,0,0,.78)", "linea": "rgba(255,255,255,.45)",
            "chip": "rgba(0,0,0,.92)", "sombra": "rgba(0,0,0,.6)", "estacion": "#00e5ff",
            "fam_residencial": "#66b8ff", "fam_industrial": "#ffd400", "fam_deportivo": "#ff9d4d"}},
}
ESTILO_DEFECTO = "oscuro"
# Los colores del estilo en uso. Siempre este mismo diccionario: se cambia su contenido, no se sustituye.
T = dict(TEMAS[ESTILO_DEFECTO]["colores"])
# Lo que se elige en la ventana de configuración, además del estilo
# Blanco por defecto (usuario, 2026-10-24: los colores se confundían con los del penacho), y del todo (2026-11-09).
PREFERENCIAS = {"viento_forma": "particulas", "viento_color": "blanco", "viento_cantidad": "normal",
                "escala_viento": "azul_rojo", "escala_olor": "turbo", "escala_gases": "viridis"}
_CANTIDADES = {"pocas": 0.5, "normal": 1.0, "muchas": 1.5}
_OPCIONES = {"viento_forma": ("particulas", "lineas", "flechas"), "viento_color": ("blanco", "velocidad"),
             "viento_cantidad": tuple(_CANTIDADES), "escala_viento": tuple(escalas.ESCALAS),
             "escala_olor": tuple(escalas.ESCALAS), "escala_gases": tuple(escalas.ESCALAS)}
FUENTES = ("Segoe UI Variable Text", "Segoe UI Variable", "Segoe UI")
FUENTE_CSS = '"Segoe UI Variable Text","Segoe UI",Arial,sans-serif'

# Iconos propios, de trazo, en una rejilla de 24 × 24
_ICONOS = {
    "inicio": '<path d="M3 11.5 12 4l9 7.5"/><path d="M5.5 9.8V20h13V9.8"/><path d="M10 20v-5.5h4V20"/>',
    # un digestor con su cúpula y un silo, como el icono de la app (usuario, 2026-11-07: «un tanque [...] más que una fábrica»)
    "planta": '<path d="M2 20.5h20"/><path d="M3.5 20.5V14h10v6.5"/><path d="M2.8 14h11.4"/><path d="M3.6 14c.7-4.7 9.1-4.7 9.8 0"/>'
              '<path d="M15.5 20.5V7.5h4v13"/><path d="M15 7.5h5"/>',
    # un matraz que emite (usuario, 2026-11-07: «un matraz o algo más referido a la química que una localización»)
    "focos": '<path d="M10 7v3.2L4.7 18.6A1.6 1.6 0 0 0 6.1 21h11.8a1.6 1.6 0 0 0 1.4-2.4L14 10.2V7"/><path d="M9.2 7h5.6"/>'
             '<path d="M7.4 16h9.2"/><path d="M11 4.6c-.8-.8.8-1.4 0-2.3M13.8 4.6c-.8-.8.8-1.4 0-2.3"/>',
    "meteo": '<path d="M3 8.5h10.5a3 3 0 1 0-3-3"/><path d="M3 13.5h15a3 3 0 1 1-3 3"/><path d="M3 18.5h6"/>',
    "simulacion": '<circle cx="12" cy="12" r="9"/><path d="M10 8.2 16 12l-6 3.8z"/>',
    # el penacho: una chimenea y sus bocanadas, como los puffs del motor, que crecen y se diluyen al alejarse, llenando el recuadro (usuario,
    # 2026-11-07: «un penacho o un humo»; «la idea de puff me gusta, pero un icono más artístico»; más grande, «reduciendo los bordes»)
    "visor3d": '<path d="M1 22.6h11"/><path d="M2.8 22.6l.8-7.2h4.6l.8 7.2"/>'
               '<circle cx="6" cy="10.9" r="3.4" fill="currentColor" stroke="none"/>'
               '<circle cx="11.5" cy="7.1" r="4.3" fill="currentColor" fill-opacity=".8" stroke="none"/>'
               '<circle cx="18.3" cy="6.3" r="4.9" fill="currentColor" fill-opacity=".6" stroke="none"/>',
    "actividad": '<path d="M3 12.5h4L9.5 6l4 12 2.5-5.5h5"/>',
    "ayuda": '<circle cx="12" cy="12" r="9"/><path d="M9.6 9.4a2.5 2.5 0 1 1 3.6 2.3c-.7.4-1.2 1-1.2 1.8v.5"/>'
             '<circle cx="12" cy="17" r="1" fill="currentColor" stroke="none"/>',
    "solo_mapa": '<path d="M4 9V4h5M20 9V4h-5M4 15v5h5M20 15v5h-5"/>',
    # las categorías de «Comprobar la herramienta»: instalación (un paquete), datos de entrada (una carpeta), servicios en línea (descargar de
    # la nube) y conexión (el globo); el viento y la dispersión llevan los de sus páginas
    "paquete": '<path d="M12 3 20 7.5v9L12 21l-8-4.5v-9z"/><path d="M4 7.5 12 12l8-4.5M12 12v9"/>',
    "carpeta": '<path d="M3 6.5A1.5 1.5 0 0 1 4.5 5H9l2 2.5h8.5A1.5 1.5 0 0 1 21 9v9.5a1.5 1.5 0 0 1-1.5 1.5h-15A1.5 1.5 0 0 1 3 18.5z"/>',
    "descarga": '<path d="M7 17.5h-.5a4 4 0 0 1-.6-7.95A5.5 5.5 0 0 1 16.6 8.2 4 4 0 0 1 17.5 16"/><path d="M12 11.5v8.5M9 17l3 3 3-3"/>',
    "red": '<circle cx="12" cy="12" r="9"/><path d="M3 12h18M12 3a14 14 0 0 1 0 18M12 3a14 14 0 0 0 0 18"/>',
    # las cifras de la página Planta: la cota (una montaña), el terreno (un cuadro con su rejilla), los núcleos (casas, fábrica, deporte)
    # y los edificios
    "relieve": '<path d="M2.5 19.5 9 8.5l3.6 6 2.4-3.6 6.5 8.6z"/><path d="M7.4 11.2 9 12.6l1.6-1.4"/>',
    "dominio": '<rect x="4" y="4" width="16" height="16" rx="2"/><path d="M4 12h16M12 4v16" stroke-opacity=".55"/>',
    "casas": '<path d="M2.5 20.5v-8l5-4 5 4v8z"/><path d="M12.5 20.5V10l4.5-3.5 4.5 3.5v10.5"/><path d="M6 20.5v-4h3v4"/>',
    "fabrica": '<path d="M3 20.5V10l6 4v-4l6 4V4.5h6v16z"/><path d="M7 17h2M12 17h2M17 17h1"/>',
    "deporte": '<circle cx="12" cy="12" r="8.5"/><path d="M12 3.5v17M3.5 12h17" stroke-opacity=".7"/><path d="M6 6c3 3 3 9 0 12M18 6c-3 3-3 9 0 12"/>',
    "edificio": '<rect x="5" y="3.5" width="14" height="17" rx="1.5"/><path d="M9 8h2M13 8h2M9 12h2M13 12h2M10.5 20.5v-4h3v4"/>',
    # los modelos de foco, en la página Focos: una superficie, un punto (una chimenea vista desde arriba) y un volumen
    "f_superficie": '<path d="M4 8 11.5 4l8.5 5-2 10.5H6.5z"/>',
    "f_punto": '<circle cx="12" cy="12" r="3.2" fill="currentColor" stroke="none"/><circle cx="12" cy="12" r="7.5"/>',
    "f_volumen": '<path d="M12 3 20 7.5v9L12 21l-8-4.5v-9z"/><path d="M4 7.5 12 12l8-4.5M12 12v9"/>',
    # el botón de la operación de la página Focos (los planes): un calendario
    "calendario": '<rect x="3.5" y="5" width="17" height="15.5" rx="2"/><path d="M3.5 10h17M8 3v4M16 3v4"/>'
                  '<path d="M7.5 14h2M11 14h2M14.5 14h2M7.5 17.5h2M11 17.5h2"/>',
    # las cifras de la ficha de un foco: altura, diámetro, caudal, velocidad, temperatura y material
    "altura": '<path d="M12 3.5V18M8.5 7 12 3.5 15.5 7"/><path d="M4 20.5h16"/>',
    "diametro": '<circle cx="12" cy="12" r="8.5"/><path d="M6 18 18 6"/><path d="M14.5 6H18v3.5M9.5 18H6v-3.5"/>',
    "caudal": '<path d="M3 8.5h9.5a3 3 0 1 0-3-3"/><path d="M3 12.5h13.5a3 3 0 1 1-3 3"/><path d="M3 16.5h5"/>',
    "velocidad": '<path d="M4.5 17a8 8 0 1 1 15 0"/><path d="M12 13l4-5"/><circle cx="12" cy="13" r="1.3" fill="currentColor" stroke="none"/>',
    "temperatura": '<path d="M10 14.5V5a2 2 0 1 1 4 0v9.5a4 4 0 1 1-4 0z"/><path d="M12 9v7"/>',
    "material": '<path d="M3 19.5h18L15.5 9l-3 4-2.5-3z"/>',
    # hacia dónde sale el gas de una chimenea (el editor de un foco punto): la chimenea, gruesa, y la flecha del gas
    "sal_vertical": '<path d="M12 21.5V10" stroke-width="3.6"/><path d="M12 7.2V2.8M9.6 5.2 12 2.8l2.4 2.4"/>',
    "sal_sombrerete": '<path d="M12 21.5V11" stroke-width="3.6"/><path d="M6.5 8.2h11M12 8.2V11"/><path d="M6.5 11l-2.2 2.2M17.5 11l2.2 2.2"/>',
    "sal_horizontal": '<path d="M8 21.5V11.5h7" stroke-width="3.6"/><path d="M17.5 11.5h4M19.6 9.4l2.1 2.1-2.1 2.1"/>',
    "sal_abajo": '<path d="M7.5 21.5V9a3.8 3.8 0 0 1 7.6 0v3" stroke-width="3.6"/><path d="M15.1 14.5v5M12.8 17.5l2.3 2.3 2.3-2.3"/>',
    # la clase de una superficie: una balsa con su agua, un tanque abierto y un biofiltro con el aire que lo atraviesa
    "sup_balsa": '<path d="M2.5 8.5h19l-2.6 9.5H5.1z"/><path d="M6 12.6c1.5-1.1 3-1.1 4.5 0s3 1.1 4.5 0 2.4-.9 3-.5"/>',
    "sup_tanque": '<ellipse cx="12" cy="6.3" rx="7.5" ry="2.6"/><path d="M4.5 6.3v11.2c0 1.4 3.4 2.6 7.5 2.6s7.5-1.2 7.5-2.6V6.3"/>'
                  '<path d="M8.2 6.6c1.3.7 2.5.7 3.8 0s2.5-.7 3.8 0"/>',
    # la emisión, constante o creciendo con el viento
    "viento_constante": '<path d="M3 12h18"/><path d="M3 7h10M3 17h10" stroke-dasharray="2 2"/>',
    "viento_viento": '<path d="M3 19c6 0 11-4 16-13"/><path d="M15.5 6H19v3.5"/><path d="M3 9h5M3 13h3"/>',
    "rumbo": '<circle cx="12" cy="12" r="8.5"/><path d="M12 5.5l2.4 6.5L12 18.5 9.6 12z"/><path d="M12 5.5l2.4 6.5h-4.8z" fill="currentColor"/>',
    # la clase de un volumen y la sección de una pila
    "vol_pila": '<path d="M2.5 19h19L14 7.5c-.9-1.4-3.1-1.4-4 0z"/><path d="M8 13.5c1.2.6 2.6.6 3.6 0M12.6 16c1.2.6 2.6.6 3.6 0"/>',
    "vol_nave": '<path d="M3.5 20V10l8.5-5 8.5 5v10z"/><path d="M9.5 20v-5.5h5V20"/>',
    "sec_hilera": '<path d="M3 18h18L12 7z"/>',
    "sec_meseta": '<path d="M3 18h18l-5.5-9h-7z"/>',
    "sup_biofiltro": '<path d="M3 13h18v7H3z"/><path d="M3 16.5h18"/><path d="M8 11V5.5M12 11V4M16 11V5.5"/><path d="M10.4 5.6 12 4l1.6 1.6"/>',
    # las formas del editor de focos: un rectángulo y un círculo con sus vértices de agarre
    "forma_rect": '<rect x="4" y="6" width="16" height="12" rx="1"/><path d="M4 6h0M20 6h0M20 18h0M4 18h0" stroke-width="4" stroke-linecap="round"/>',
    "forma_circ": '<circle cx="12" cy="12" r="8"/><path d="M12 12h8" stroke-dasharray="2 2"/><circle cx="12" cy="12" r="1.3" fill="currentColor" stroke="none"/>',
    "copiar": '<rect x="8.5" y="8.5" width="11" height="11" rx="2"/><path d="M15.5 8.5v-2a2 2 0 0 0-2-2h-7a2 2 0 0 0-2 2v7a2 2 0 0 0 2 2h2"/>',
    "ok": '<circle cx="12" cy="12" r="9"/><path d="M8 12.3l2.7 2.7 5.5-5.5"/>',
    "fallo": '<circle cx="12" cy="12" r="9"/><path d="M9 9l6 6M15 9l-6 6"/>',
    "pendiente": '<circle cx="12" cy="12" r="9" stroke-dasharray="2.2 3.2"/>',
    "aviso": '<path d="M12 3.8 21.2 19.8H2.8z"/><path d="M12 10v4.3"/><circle cx="12" cy="17" r="1" fill="currentColor" stroke="none"/>',
    "play": '<path d="M8 5.5v13l10.5-6.5z" fill="currentColor"/>',
    "pausa": '<path d="M8 5.5v13M16 5.5v13" stroke-width="3.2"/>',
    "flotar": '<path d="M4 9h11v11H4z"/><path d="M9 9V4h11v11h-5"/>',
    "cerrar": '<path d="M6 6l12 12M18 6 6 18"/>',
    "chevron": '<path d="M9 5.5 15.5 12 9 18.5"/>',
    "chevron_izq": '<path d="M15 5.5 8.5 12l6.5 6.5"/>',
    "chevron_abajo": '<path d="M5.5 9 12 15.5 18.5 9"/>',
    "terminal": '<path d="M4.5 6.5 10.5 12l-6 5.5"/><path d="M12.5 18h7"/>',
    "ajustes": '<path d="M4 7h8.5M17.5 7H20M4 17h2.5M11.5 17H20"/><circle cx="15" cy="7" r="2.5"/>'
               '<circle cx="9" cy="17" r="2.5"/>',
    "logo": '<path d="M3 8.5h10.5a3 3 0 1 0-3-3"/><path d="M3 13.5h15a3 3 0 1 1-3 3"/><path d="M3 18.5h6"/>',
}


class _Avisos(QtCore.QObject):
    cambiado = QtCore.Signal()               # ha cambiado el estilo


avisos = _Avisos()
_estilo_actual = ESTILO_DEFECTO


def ajustes():
    """Los ajustes de la app: INI en %APPDATA%\\<organización>\\<identidad.ajustes>.ini (legible y fácil de borrar)."""
    return QtCore.QSettings(QtCore.QSettings.Format.IniFormat, QtCore.QSettings.Scope.UserScope,
                            config.ORGANIZACION, config.pide("identidad", "ajustes"))


def c(nombre):
    """Color del estilo en uso. Para pintar: se lee al pintar, así que sigue los cambios de estilo."""
    return T[nombre]


def estilo_actual():
    return _estilo_actual


# Lo que vale solo mientras la app está abierta: al abrirla, siempre lo de PREFERENCIAS (usuario, 2026-11-09: el viento, «siempre por
# defecto en blanco»; «Por velocidad», en la configuración, hasta cerrar)
_SESION = {"viento_color": PREFERENCIAS["viento_color"]}


def preferencia(clave):
    if clave in _SESION:
        return _SESION[clave]
    v = ajustes().value(f"apariencia/{clave}", PREFERENCIAS[clave])
    return v if v in _OPCIONES[clave] else PREFERENCIAS[clave]


def poner_preferencia(clave, valor):
    if clave in _SESION:
        _SESION[clave] = valor if valor in _OPCIONES[clave] else PREFERENCIAS[clave]
        return
    ajustes().setValue(f"apariencia/{clave}", valor)


def estilo_viento():
    """Cómo se dibuja el viento en el mapa."""
    return {"modo": preferencia("viento_forma"), "blanco": preferencia("viento_color") == "blanco",
            "factor": _CANTIDADES[preferencia("viento_cantidad")],
            "pal": escalas.colores(preferencia("escala_viento"), 5)}       # una por clase de velocidad


def escalas_mapa():
    """Las escalas de color de las concentraciones, para la página del mapa."""
    return {"olor": escalas.para_mapa(preferencia("escala_olor")),
            "gases": escalas.para_mapa(preferencia("escala_gases"))}


def _rellena(plantilla):
    return Template(plantilla).safe_substitute(T)


def pon_icono(w, nombre, color, lado=20, activo=None):
    """Icono de un botón o una etiqueta, con los NOMBRES de sus colores: se rehace al cambiar de estilo."""
    w.setProperty("ico_tema", f"{nombre}|{color}|{lado}|{activo or ''}")
    _pinta_icono(w, nombre, color, lado, activo)


def _pinta_icono(w, nombre, color, lado, activo):
    lado = int(lado)
    if isinstance(w, QtWidgets.QLabel):
        w.setPixmap(pixmap(nombre, T[color], lado))
    else:
        w.setIcon(icono(nombre, T[color], lado, activo=T[activo] if activo else None))


def texto(etiqueta, plantilla):
    """Texto enriquecido de una etiqueta, con $tenue, $aviso…: se rehace al cambiar de estilo. TODOS los
    textos de esa etiqueta deben pasar por aquí: un setText suelto volvería a salir al cambiar de estilo."""
    etiqueta.setProperty("html_tema", plantilla)
    etiqueta.setText(_rellena(plantilla))


def estilo(w, plantilla):
    """Hoja de estilos de un widget, con $tenue, $aviso…: se rehace al cambiar de estilo."""
    w.setProperty("qss_tema", plantilla)
    w.setStyleSheet(_rellena(plantilla))


def _svg(nombre, color, grosor=1.8):
    return (f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 24 24" fill="none" stroke="{color}" '
            f'stroke-width="{grosor}" stroke-linecap="round" stroke-linejoin="round" color="{color}">'
            + _ICONOS[nombre].replace("currentColor", color) + "</svg>")


def pixmap(nombre, color=None, lado=20, escala=2):
    r = QtSvg.QSvgRenderer(QtCore.QByteArray(_svg(nombre, color or T["texto"]).encode()))
    pm = QtGui.QPixmap(lado * escala, lado * escala)
    pm.fill(QtCore.Qt.GlobalColor.transparent)
    p = QtGui.QPainter(pm)
    r.render(p)
    p.end()
    pm.setDevicePixelRatio(escala)
    return pm


def icono(nombre, color=None, lado=20, activo=None):
    """QIcon nítido en pantallas escaladas; con `activo`, otro color al estar marcado."""
    i = QtGui.QIcon()
    i.addPixmap(pixmap(nombre, color, lado), QtGui.QIcon.Mode.Normal, QtGui.QIcon.State.Off)
    if activo:
        i.addPixmap(pixmap(nombre, activo, lado), QtGui.QIcon.Mode.Normal, QtGui.QIcon.State.On)
    return i


def _ficheros_qss():
    """Las hojas de estilo de Qt solo admiten imágenes desde fichero: flechas de desplegables y árboles.
    Una carpeta por estilo: Qt guarda las imágenes por su ruta y no vería el cambio de color."""
    d = config.LOCAL / "tema" / _estilo_actual
    d.mkdir(parents=True, exist_ok=True)
    chev = '<path d="M6 9.5 12 15.5 18 9.5"/>'
    formas = {"abajo": chev, "arriba": '<path d="M6 14.5 12 8.5 18 14.5"/>',
              "derecha": '<path d="M9.5 6 15.5 12 9.5 18"/>', "marca": '<path d="M5 12.5 10 17.5 19 7.5"/>'}
    rutas = {}
    for nombre, forma in formas.items():
        color = T["sobre_acento"] if nombre == "marca" else T["tenue"]
        (d / f"{nombre}.svg").write_text(
            f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 24 24" fill="none" stroke="{color}" '
            f'stroke-width="2.4" stroke-linecap="round" stroke-linejoin="round">{forma}</svg>', encoding="utf-8")
        rutas[f"ico_{nombre}"] = (d / f"{nombre}.svg").as_posix()
    return rutas


_QSS = Template("""
QWidget { color:$texto; }
QMainWindow, QDialog, VentanaFocos, VentanaPlanes, VentanaAjustes { background:$fondo; }
QMainWindow::separator { background:$borde; width:1px; height:1px; }
QSplitter::handle { background:$borde; }
QSplitter::handle:horizontal { width:1px; }
QScrollArea { background:transparent; border:none; }
QLabel { background:transparent; }

QToolTip { color:$texto; background:$elevada; border:1px solid $borde_fuerte; padding:4px 6px; }
QMenu { color:$texto; background:$elevada; border:1px solid $borde_fuerte; padding:5px; }
QMenu::item { padding:6px 22px 6px 12px; border-radius:6px; }
QMenu::item:selected { background:$hover; }
QMenu::item:disabled { color:$apagado; }
QMenu::separator { height:1px; background:$borde; margin:5px 8px; }
QMenu::indicator:checked { image:url("$ico_marca"); background:$acento; border-radius:3px; margin-left:4px; }

QPushButton, QToolButton { color:$texto; background:$elevada; border:1px solid $borde; border-radius:8px;
                           padding:6px 12px; }
QPushButton:hover, QToolButton:hover { background:$hover; border-color:$borde_fuerte; }
QPushButton:pressed { background:$borde; }
QPushButton:checked { color:$acento_claro; background:$tinte; border-color:$acento; }
QPushButton:disabled, QToolButton:disabled { color:$apagado; background:$superficie; border-color:$borde; }
QPushButton#primario { color:$sobre_acento; background:$acento; border:none; font-weight:600; padding:8px 18px; }
QPushButton#primario:hover { background:$acento_claro; }
QPushButton#primario:disabled { color:$apagado; background:$elevada; }
QPushButton#primario[cancelar="true"] { color:$texto; background:$elevada; border:1px solid $borde_fuerte; font-weight:600; }
QPushButton#primario[cancelar="true"]:hover { background:$hover; }
QPushButton#segmento { border-radius:0; padding:6px 16px; }
QPushButton#segmento:checked { color:$sobre_acento; background:$acento; border-color:$acento; }

QLineEdit, QPlainTextEdit, QComboBox, QSpinBox, QDoubleSpinBox, QDateEdit {
    color:$texto; background:$superficie; border:1px solid $borde; border-radius:8px; padding:5px 8px;
    selection-background-color:$acento; selection-color:$sobre_acento; }
QLineEdit:focus, QPlainTextEdit:focus, QSpinBox:focus, QDateEdit:focus { border-color:$acento; }
QLineEdit[readOnly="true"], QPlainTextEdit[readOnly="true"] { color:$tenue; background:$fondo; }
QComboBox:hover, QSpinBox:hover, QDateEdit:hover { border-color:$borde_fuerte; }
QComboBox::drop-down, QDateEdit::drop-down { border:none; width:26px; }
QComboBox::down-arrow, QDateEdit::down-arrow { image:url("$ico_abajo"); width:12px; height:12px; }
QComboBox QAbstractItemView { color:$texto; background:$elevada; border:1px solid $borde_fuerte; outline:0;
                              selection-background-color:$tinte; selection-color:$acento_claro; padding:4px; }
QComboBox { background:$elevada; padding:6px 12px; border-radius:10px; min-height:20px; }
QComboBox:on { border-color:$acento; }
QComboBox QAbstractItemView { border-radius:10px; padding:6px; }
QComboBox QAbstractItemView::item { min-height:28px; padding:2px 10px; border-radius:6px; }
QComboBox QAbstractItemView::item:hover { background:$hover; }
QComboBox QAbstractItemView::item:selected { background:$tinte; color:$acento_claro; }
QSpinBox { padding-right:22px; }
QSpinBox::up-button, QSpinBox::down-button { border:none; width:20px; background:transparent; }
QSpinBox::up-button { subcontrol-position:top right; }
QSpinBox::down-button { subcontrol-position:bottom right; }
QSpinBox::up-arrow { image:url("$ico_arriba"); width:10px; height:10px; }
QSpinBox::down-arrow { image:url("$ico_abajo"); width:10px; height:10px; }

QCalendarWidget QWidget { alternate-background-color:$superficie; }
QCalendarWidget QToolButton { color:$texto; background:transparent; border:none; padding:4px 8px; }
QCalendarWidget QToolButton:hover { background:$hover; }
QCalendarWidget QMenu { background:$elevada; }
QCalendarWidget QSpinBox { padding:2px 18px 2px 4px; }
QCalendarWidget QWidget#qt_calendar_navigationbar { background:$elevada; }
QCalendarWidget QAbstractItemView:enabled { color:$texto; background:$superficie;
    selection-background-color:$acento; selection-color:$sobre_acento; outline:0; }
QCalendarWidget QAbstractItemView:disabled { color:$apagado; background:$superficie; }

QRadioButton, QCheckBox { spacing:8px; background:transparent; }
QRadioButton:disabled, QCheckBox:disabled { color:$apagado; }
QRadioButton::indicator { width:14px; height:14px; border-radius:8px; border:2px solid $borde_fuerte; background:$superficie; }
QRadioButton::indicator:checked { border:5px solid $acento; width:6px; height:6px; background:$fondo; }
QRadioButton::indicator:disabled { border-color:$borde; }
QCheckBox::indicator { width:15px; height:15px; border-radius:4px; border:2px solid $borde_fuerte; background:$superficie; }
QCheckBox::indicator:checked { image:url("$ico_marca"); background:$acento; border-color:$acento; }
QRadioButton#opcion, QRadioButton#opcion_h { padding:10px 12px; background:$superficie; border:1px solid $borde; border-radius:10px; }
QRadioButton#opcion:hover, QRadioButton#opcion_h:hover { border-color:$borde_fuerte; }
QRadioButton#opcion:checked, QRadioButton#opcion_h:checked { background:$tinte; border-color:$acento; }
QRadioButton#opcion:disabled, QRadioButton#opcion_h:disabled { background:transparent; }
QRadioButton#opcion_h { padding:8px 8px; spacing:6px; }

QSlider::groove:horizontal { height:6px; background:$barra_inactiva; border-radius:3px; }
QSlider::sub-page:horizontal { background:$acento; border-radius:3px; }
QSlider::handle:horizontal { width:16px; height:16px; margin:-5px 0; border-radius:8px; background:$texto; }
QSlider::handle:horizontal:hover { background:$acento_claro; }
QSlider::handle:horizontal:disabled { background:$apagado; }
QSlider::sub-page:horizontal:disabled { background:$barra_inactiva; }

QProgressBar { color:$texto; background:$superficie; border:1px solid $borde; border-radius:6px; text-align:center;
               min-height:16px; }
QProgressBar::chunk { background:$acento; border-radius:5px; }

QScrollBar:vertical { background:transparent; width:10px; margin:2px; }
QScrollBar::handle:vertical { background:$borde_fuerte; border-radius:3px; min-height:30px; }
QScrollBar:horizontal { background:transparent; height:10px; margin:2px; }
QScrollBar::handle:horizontal { background:$borde_fuerte; border-radius:3px; min-width:30px; }
QScrollBar::add-line, QScrollBar::sub-line { width:0; height:0; }
QScrollBar::add-page, QScrollBar::sub-page { background:transparent; }

QTreeWidget, QTableWidget, QListWidget { color:$texto; background:transparent; border:none; outline:0; }
QTreeWidget::item { padding:3px 2px; }
QTreeWidget::item:hover { background:$hover; }
QTreeWidget::item:selected { color:$texto; background:$tinte; }
QTreeWidget::branch:has-children:closed { image:url("$ico_derecha"); }
QTreeWidget::branch:has-children:open { image:url("$ico_abajo"); }
QTableWidget { gridline-color:$borde; border:1px solid $borde; border-radius:8px; }
QTableWidget::item { padding:2px 6px; }
QHeaderView { background:transparent; }
QHeaderView::section { color:$tenue; background:$superficie; border:none; border-bottom:1px solid $borde; padding:5px 6px;
                       font-weight:600; }
QTableCornerButton::section { background:$superficie; border:none; }

QWidget#barra_app { background:$superficie; border-bottom:1px solid $borde; }
QLabel#marca { background:$acento; border-radius:9px; }
QLabel#app_titulo { font-size:15px; font-weight:600; }
QLabel#admin_marca { color:$acento; background:$tinte; border:1px solid $acento; border-radius:10px; padding:2px 10px; font-size:12px;
                     font-weight:600; }
QLabel#reloj { font-size:15px; font-weight:600; }
QLabel#reloj_sub { color:$tenue; font-size:12px; }
QToolButton#icono { background:transparent; border:none; border-radius:8px; padding:7px; }
QToolButton#icono:hover { background:$hover; }
QToolButton#icono:checked { background:$tinte; }
QToolButton#icono::menu-indicator { image:none; width:0; }

QFrame#riel { background:$superficie; border-right:1px solid $borde; }
QToolButton#riel_b { color:$tenue; background:transparent; border:none; border-radius:10px; padding:7px 2px;
                     font-size:11px; }
QToolButton#riel_b:hover { color:$texto; background:$hover; }
QToolButton#riel_b:checked { color:$acento_claro; background:$tinte; font-weight:600; }
QWidget#pagina { background:$fondo; }
QWidget#titulo_dock { background:$fondo; border-bottom:1px solid $borde; }
QLabel#titulo_dock_t { font-size:15px; font-weight:600; }

QFrame#tarjeta { background:$superficie; border:1px solid $borde; border-radius:12px; }
QPushButton#plegable { background:transparent; border:none; border-radius:12px; padding:11px 14px; font-size:14px;
                       font-weight:600; text-align:left; }
QPushButton#plegable:hover, QPushButton#plegable:checked:hover { background:$hover; }
QPushButton#plegable:checked { color:$texto; background:transparent; }
QLabel#titulo_tarjeta { font-size:14px; font-weight:600; }
QLabel#nota { color:$tenue; font-size:12px; }
QLabel#seccion { color:$tenue; font-size:11px; font-weight:600; }
QToolButton#cal_titulo { background:transparent; border:none; border-radius:8px; padding:4px 10px; font-size:14px; font-weight:600; }
QToolButton#cal_titulo:hover { background:$hover; }
QToolButton#cal_titulo::menu-indicator { image:none; width:0; }
QFrame#cifra { background:$elevada; border:1px solid $borde; border-radius:10px; }
QLabel#cifra_v { font-size:17px; font-weight:700; }
QLabel#cifra_ico { background:$tinte; border-radius:8px; }
QPushButton#seg_mini { color:#ffffff; background:rgba(10,14,12,.55); border:none; border-radius:9px; padding:3px 11px;
                       font-size:11px; font-weight:600; }
QPushButton#seg_mini:hover { background:rgba(10,14,12,.75); }
QPushButton#seg_mini:checked { color:$sobre_acento; background:$acento; }
QPushButton#chip_mag { color:$texto; background:$elevada; border:1px solid $borde; border-radius:11px; padding:3px 10px;
                       font-size:12px; font-weight:600; }
QPushButton#chip_mag:hover { background:$hover; }
QPushButton#chip_mag:checked { color:$sobre_acento; background:$acento; border-color:$acento; }
QPushButton#chip_capa, QPushButton#chip_estilo { color:$texto; background:$elevada; border:1px solid $borde; border-radius:11px;
                       padding:3px 10px; font-size:12px; font-weight:600; }
QPushButton#chip_capa:hover, QPushButton#chip_estilo:hover { background:$hover; }
QPushButton#chip_capa:checked { color:$sobre_acento; background:$acento; border-color:$acento; }
QPushButton#chip_estilo { color:$tenue; font-weight:500; }
QPushButton#chip_estilo:checked { color:$acento_claro; background:$tinte; border-color:$acento; }
QTableWidget#tabla_mags::item:selected { color:$texto; background:$tinte; }
QTableWidget#tabla_mags::item:hover { background:$hover; }
QFrame#cat { background:$elevada; border:1px solid $borde; border-radius:10px; }
QFrame#cat[estado="en_curso"] { background:$tinte; border-color:$acento; }
QFrame#cat[estado="ok"] { border-color:$borde; }
QFrame#cat[estado="aviso"] { background:$tinte_aviso; border-color:$aviso; }
QFrame#cat[estado="fallo"] { background:$tinte_fallo; border-color:$fallo; }
QLabel#cat_ico { background:$superficie; border-radius:9px; }
QLabel#cat_t { font-weight:600; }
QLabel#chip_aviso { color:$aviso; background:$superficie; border:1px solid $aviso; border-radius:7px; padding:0px 6px; font-size:11px;
                    font-weight:700; }
QLabel#chip_fallo { color:$fallo; background:$superficie; border:1px solid $fallo; border-radius:7px; padding:0px 6px; font-size:11px;
                    font-weight:700; }
QProgressBar#cat_barra { background:$superficie; border:none; border-radius:2px; min-height:4px; max-height:4px; }
QProgressBar#cat_barra::chunk { background:$acento; border-radius:2px; }
QLabel#emplazamiento_t { font-size:14px; font-weight:600; }
QFrame#paso { background:$elevada; border:1px solid $borde; border-radius:10px; }
QFrame#paso:hover { background:$hover; border-color:$borde_fuerte; }
QLabel#paso_num { color:$acento_claro; background:$tinte; border-radius:13px; font-weight:700; }
QLabel#paso_num[hecho="true"] { color:$sobre_acento; background:$acento; }

QFrame#reproductor { background:$superficie; border-top:1px solid $borde; }
QLabel#hora_grande { font-size:17px; font-weight:600; }
QPushButton#play { background:$acento; border:none; border-radius:18px; padding:0; }
QPushButton#play:hover { background:$acento_claro; }
QPushButton#play:disabled { background:$elevada; }
QPlainTextEdit#actividad { color:$tenue; background:$fondo; border:none; border-radius:0; }
QFrame#terminal_fila { background:$fondo; border-top:1px solid $borde; }
QLabel#terminal_marca { color:$acento_claro; }
QLineEdit#terminal { color:$texto; background:transparent; border:none; border-radius:0; padding:4px 0; }
QTabBar { background:$fondo; qproperty-drawBase:0; }
QTabBar::tab { color:$tenue; background:$superficie; border:1px solid $borde; padding:6px 16px; }
QTabBar::tab:selected { color:$texto; background:$elevada; }
""")


# Lo común está en _QSS; aquí, lo propio de las ventanas de focos, planes y configuración (se pone con `estilo`).
ESTILO_VENTANAS = """
QWidget#cabecera { background:$superficie; border-bottom:1px solid $borde; }
QLabel#titulo { font-size:16px; font-weight:600; }
QLabel#subtitulo { font-size:12px; color:$tenue; }
QLabel#recalcula { font-size:13px; font-weight:700; color:$aviso; padding:0px 2px; }
QToolButton#tile_modelo { color:$texto; background:$elevada; border:1px solid $borde; border-radius:12px; padding:10px 4px 8px 4px;
                          font-size:12px; font-weight:600; }
QToolButton#tile_modelo:hover { border-color:$borde_fuerte; background:$hover; }
QToolButton#tile_modelo:checked { color:$acento_claro; background:$tinte; border:2px solid $acento; }
QToolButton#tile_modelo:disabled:!checked { color:$apagado; }
QListWidget#actividad_focos { background:transparent; border:none; }
QListWidget#actividad_focos::item { color:$texto; padding:5px 6px; border-radius:7px; }
QListWidget#actividad_focos::item:hover { background:$hover; }
QPushButton#actividad { color:$texto; background:$elevada; border:1px solid $borde; border-radius:9px; padding:7px 12px;
                        text-align:left; }
QPushButton#actividad:hover { background:$hover; }
QPushButton#actividad:checked { color:$acento_claro; background:$tinte; border:1px solid $acento; font-weight:600; }
QPushButton#actividad:disabled:!checked { color:$apagado; }
QLabel#grupo_ficha { color:$tenue; font-size:11px; font-weight:700; }
QLabel#estado_falta { background:$tinte_aviso; color:$aviso; border-radius:8px; padding:7px 10px; }
QWidget#nav, QScrollArea#ficha, QWidget#cuerpo_ficha { background:$superficie; }
QListWidget#lista { border:none; background:$superficie; outline:0; }
QListWidget#lista::item { border:1px solid $borde; border-radius:10px; margin:3px 2px; }
QListWidget#lista::item:selected { border:2px solid $acento; background:$tinte; }
QListWidget#lista::item:hover:!selected { background:$hover; }
QPushButton#anadir { border:1px dashed $acento; border-radius:8px; color:$acento_claro; padding:7px;
                     text-align:left; background:transparent; }
"""


def aplicar(app):
    """Al arrancar: letra y el estilo guardado."""
    global _estilo_actual
    QtWidgets.QApplication.setStyle("Fusion")
    disponibles = set(QtGui.QFontDatabase.families())
    # en píxeles, como la hoja de estilos: mezclar puntos y píxeles rompe la jerarquía si el escalado cambia
    fuente = QtGui.QFont(next((f for f in FUENTES if f in disponibles), FUENTES[-1]))
    fuente.setPixelSize(13)
    fuente.setStyleStrategy(QtGui.QFont.StyleStrategy.PreferAntialias)
    app.setFont(fuente)
    guardado = ajustes().value("apariencia/estilo", ESTILO_DEFECTO)
    _estilo_actual = guardado if guardado in TEMAS else ESTILO_DEFECTO
    T.update(TEMAS[_estilo_actual]["colores"])
    _colores(app)


def poner(clave):
    """Cambia de estilo con la app abierta, y lo guarda para la próxima vez. No hace falta reiniciar."""
    global _estilo_actual
    _estilo_actual = clave
    T.update(TEMAS[clave]["colores"])
    app = QtWidgets.QApplication.instance()
    ventanas = [w for w in app.topLevelWidgets() if w.isVisible()]
    for w in ventanas:                                    # todo de una vez, sin parpadeos a medias
        w.setUpdatesEnabled(False)
    _colores(app)
    _rehacer()
    avisos.cambiado.emit()
    for w in ventanas:
        w.setUpdatesEnabled(True)
    ajustes().setValue("apariencia/estilo", clave)


def _rehacer():
    """Lo que la hoja de estilos global no alcanza: los estilos, textos e iconos propios de cada widget."""
    for w in QtWidgets.QApplication.allWidgets():
        v = w.property("qss_tema")
        if v:
            w.setStyleSheet(_rellena(v))
        v = w.property("html_tema")
        if v:
            w.setText(_rellena(v))
        v = w.property("ico_tema")
        if v:
            _pinta_icono(w, *v.split("|"))
        if isinstance(w, QtWidgets.QCalendarWidget):
            calendario(w)


def _colores(app):
    """Marco de las ventanas, paleta, icono de la app y hoja de estilos con los colores en uso."""
    if hasattr(app.styleHints(), "setColorScheme"):       # no el del sistema: el marco sigue al estilo elegido
        app.styleHints().setColorScheme(QtCore.Qt.ColorScheme.Light if TEMAS[_estilo_actual]["esquema"] == "claro"
                                        else QtCore.Qt.ColorScheme.Dark)
    pal = QtGui.QPalette()
    R = QtGui.QPalette.ColorRole
    for rol, color in ((R.Window, "fondo"), (R.WindowText, "texto"), (R.Base, "superficie"),
                       (R.AlternateBase, "elevada"), (R.Text, "texto"), (R.Button, "elevada"),
                       (R.ButtonText, "texto"), (R.ToolTipBase, "elevada"), (R.ToolTipText, "texto"),
                       (R.Highlight, "acento"), (R.HighlightedText, "sobre_acento"), (R.PlaceholderText, "apagado"),
                       (R.Link, "acento_claro"), (R.Mid, "borde"), (R.Dark, "fondo"), (R.Light, "hover")):
        pal.setColor(rol, QtGui.QColor(T[color]))
    for rol in (R.WindowText, R.Text, R.ButtonText):
        pal.setColor(QtGui.QPalette.ColorGroup.Disabled, rol, QtGui.QColor(T["apagado"]))
    app.setPalette(pal)
    app.setWindowIcon(icono_app())
    app.setStyleSheet(_QSS.substitute(T, **_ficheros_qss()))


def icono_planta():
    """El icono propio de la planta (`identidad.icono`: un .ico, .png o .svg, relativo a su carpeta), o None si no tiene.
    Un .ico con cada tamaño dibujado aparte se ve mejor en 16-32 px que uno escalado."""
    ruta = config.bloque("identidad").get("icono")
    if not ruta:
        return None
    ruta = config.PLANTA / ruta
    i = QtGui.QIcon(str(ruta)) if ruta.is_file() else QtGui.QIcon()
    if i.isNull():
        from teodors.comun import registro
        registro.get("gui").warning(f"No se puede leer el icono de la planta, {ruta}: va el de teOdors.")
        return None
    return i


def icono_app():
    """Icono de la ventana y de la barra de tareas: el de la planta y, si no tiene, la marca de teOdors en el acento del estilo."""
    propio = icono_planta()
    if propio is not None:
        return propio
    i = QtGui.QIcon()
    for lado in (32, 64, 128):
        pm = QtGui.QPixmap(lado, lado)
        pm.fill(QtCore.Qt.GlobalColor.transparent)
        p = QtGui.QPainter(pm)
        p.setRenderHint(QtGui.QPainter.RenderHint.Antialiasing)
        p.setPen(QtCore.Qt.PenStyle.NoPen)
        p.setBrush(QtGui.QColor(T["acento"]))
        p.drawRoundedRect(0, 0, lado, lado, lado * 0.24, lado * 0.24)
        m = int(lado * 0.16)
        QtSvg.QSvgRenderer(QtCore.QByteArray(_svg("logo", T["sobre_acento"], 2.0).encode())).render(
            p, QtCore.QRectF(m, m, lado - 2 * m, lado - 2 * m))
        p.end()
        i.addPixmap(pm)
    return i


def calendario(cal):
    """Lo que el estilo global no alcanza: fin de semana sin el rojo de Qt y flechas de mes visibles."""
    fmt = QtGui.QTextCharFormat()
    fmt.setForeground(QtGui.QColor(T["tenue"]))
    for dia in (QtCore.Qt.DayOfWeek.Saturday, QtCore.Qt.DayOfWeek.Sunday):
        cal.setWeekdayTextFormat(dia, fmt)
    for nombre, ico in (("qt_calendar_prevmonth", "chevron_izq"), ("qt_calendar_nextmonth", "chevron")):
        b = cal.findChild(QtWidgets.QToolButton, nombre)
        pon_icono(b, ico, "texto", 16)
        b.setIconSize(QtCore.QSize(16, 16))


def manos(raiz):
    """Cursor de mano en todos los botones de un widget (se nota al pasar el ratón)."""
    for b in raiz.findChildren(QtWidgets.QAbstractButton):
        b.setCursor(QtCore.Qt.CursorShape.PointingHandCursor)


def css_variables():
    """Los colores del estilo en uso para la página del mapa."""
    return ":root{" + "".join(f"--{k}:{v};" for k, v in T.items()) + f"--letra:{FUENTE_CSS}}}"


def js_variables():
    """Lo mismo para una página ya abierta: basta con cambiar las variables, sin recargar el mapa."""
    return ("(function(r,v){for(var k in v){r.style.setProperty('--'+k,v[k]);}})(document.documentElement,"
            + json.dumps(T) + ")")
