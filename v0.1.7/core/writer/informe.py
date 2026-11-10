# -*- coding: utf-8 -*-
"""El informe de un caso del reanálisis, de principio a fin: los datos (`datos`), las imágenes (`capturas`), las páginas (`paginas`) y el PDF
(`pdf`), en la carpeta del caso con su nombre («AAAA-MM-DD-nombre.pdf»). Lo intermedio (imágenes, fichas, HTML), en LOCAL/informes/<caso>:
`solo_html` rehace las páginas y el PDF con lo de la última vez, sin volver a hacer las imágenes.

    python -m teodors.writer CARPETA_DEL_CASO [CARPETA_DEL_OTRO] [--planta CARPETA] [--html] [--png] [--sin-viento]

Con dos casos, el informe de su comparación (el primero, la referencia: A), en `simulacion.dir_guardados()`/comparaciones.

Sin `--planta`, la de TEODORS_PLANTA. `--html`: solo las páginas y el PDF; `--png`: además, cada página en PNG; `--sin-viento`: sin leer el viento
de la planta (el más frecuente, en lo esencial del caso).
"""
import json
import os
import re
import shutil
import subprocess
import sys
from collections import deque
from pathlib import Path

from teodors import planta as config
from teodors.comun import registro
from teodors.writer import datos, paginas

log = registro.get("writer")


def carpeta_trabajo(d):
    return Path(config.LOCAL) / "informes" / d["caso_dir"].name


def ruta_pdf(d):
    """El PDF, en la carpeta del caso y con su nombre."""
    return d["caso_dir"] / f"{d['caso_dir'].name}.pdf"


def maquetar(d, carpeta_img, fichas=None):
    """Escribe el HTML del informe con las imágenes de `carpeta_img` y devuelve su ruta. `d`: lo de `datos.reunir` o, el de una comparación,
    lo de `datos.reunir_comparacion`."""
    carpeta_img = Path(carpeta_img)
    if fichas is None and (carpeta_img / "fichas.json").is_file():
        fichas = json.loads((carpeta_img / "fichas.json").read_text(encoding="utf-8"))
    imagenes = {p.stem: p.name for p in sorted(carpeta_img.iterdir()) if p.suffix.lower() in (".png", ".jpg", ".svg")}
    html = carpeta_img.parent / "informe.html"
    informe = paginas.InformeComparacion(d, imagenes, fichas) if "comp" in d else paginas.Informe(d, imagenes, fichas)
    html.write_text(informe.html(), encoding="utf-8")
    return html


def nombre_comparacion(dc):
    """«AAAA-MM-DD-Base frente a Balsas al 50»: el de la carpeta de trabajo y el del PDF de una comparación."""
    from teodors.operacion import simulacion as S
    a, b = (x["res"]["nombre"] or "Base" for x in (dc["a"], dc["b"]))
    return S.carpeta_caso(f"{a} frente a {b}", fecha=dc["hoy"]).name


def ruta_pdf_comparacion(dc):
    """El PDF de una comparación: en la carpeta de los casos del reanálisis, en «comparaciones»."""
    from teodors.operacion import simulacion as S
    return S.dir_guardados() / "comparaciones" / f"{nombre_comparacion(dc)}.pdf"


def generar(caso, ventana=None, progreso=None, al_acabar=None, fallo=None, solo_html=False, viento=True, pngs=False, otro=None):
    """Hace el informe del caso de la carpeta `caso` con la ventana principal `ventana` (oculta) para las imágenes. Asíncrono, con el reloj de
    Qt: al acabar, `al_acabar(ruta del PDF)`; si falla, `fallo(mensaje)`. Necesita una QApplication."""
    from teodors.gui import tema
    avisa = progreso or (lambda *_: None)
    falla = fallo or (lambda m: log.error(f"Informe: {m}"))
    escalas = {"olor": tema.preferencia("escala_olor"), "gases": tema.preferencia("escala_gases")}
    dc = None
    try:
        if otro is None:
            avisa(1, "Reuniendo los datos del caso…")
            d = datos.reunir(caso, viento=viento, escalas=escalas)
        else:                                                         # la comparación de dos escenarios (usuario, 2026-11-10)
            avisa(1, "Reuniendo los datos de los dos escenarios y comparándolos…")
            dc = datos.reunir_comparacion(caso, otro, viento=viento, escalas=escalas)
            d = dc["a"]
    except (ValueError, OSError) as ex:
        falla(str(ex))
        return
    trabajo = carpeta_trabajo(d) if dc is None else Path(config.LOCAL) / "informes" / nombre_comparacion(dc)
    img = trabajo / "img"

    def a_pdf(capturado=None):
        from teodors.writer import pdf
        avisa(97, "Páginas y PDF…")
        try:                                                          # un fallo aquí, dicho: si no, el proceso se queda esperando
            html = maquetar(d if dc is None else dc, img, (capturado or {}).get("fichas"))
            destino = ruta_pdf(d) if dc is None else ruta_pdf_comparacion(dc)
            destino.parent.mkdir(parents=True, exist_ok=True)
        except Exception as ex:                                       # noqa: BLE001 (se dice y se para)
            import traceback
            log.error("Informe: fallo al montar las páginas:\n" + traceback.format_exc())
            falla(f"{type(ex).__name__}: {ex}")
            return

        def hecho(ok, ruta):
            if not ok:
                falla(f"No se pudo escribir el PDF en {ruta}.")
                return
            log.info(f"Informe {'del caso «' + d['caso_dir'].name if dc is None else 'de la comparación «' + nombre_comparacion(dc)}»: {ruta}")
            avisa(100, "Hecho")
            if al_acabar:
                al_acabar(str(ruta))
        pdf.imprimir(html, destino, hecho, pngs=trabajo / "paginas" if pngs else None)

    if solo_html:
        if not img.is_dir():
            falla(f"No hay imágenes de la última vez en {img}: hay que hacerlas.")
            return
        a_pdf()
        return
    if ventana is None:
        falla("Para hacer las imágenes hace falta la ventana principal de la app.")
        return
    shutil.rmtree(img, ignore_errors=True)
    from teodors.writer.capturas import Capturas
    Capturas(ventana, d, img, avisa, a_pdf, falla, comparacion=dc).empezar()


def lanzar(caso, progreso=None, otro=None):
    """El informe de un caso en otro proceso (`python -m teodors.writer.informe CASO --planta …`), para la app (usuario, 2026-11-10: al
    guardar un caso del reanálisis, «se guarda… con los resultados y el informe»): la app sigue mientras, y no toca su estilo ni sus ajustes.
    Con el entorno heredado: con uno explícito (`env=`), el motor web del hijo no arranca en Windows; el camino de Python de este proceso
    (`procesos.entorno`), puesto en el entorno solo mientras se lanza. `progreso(pct, texto)`, lo que va
    diciendo. Con `otro`, el de la comparación de los dos (`caso`, la referencia). Devuelve {"pdf": su ruta}; si falla, RuntimeError con sus
    últimas líneas."""
    from teodors.comun import procesos
    avisa = progreso or (lambda *_: None)
    casos = [str(caso)] + ([str(otro)] if otro is not None else [])
    # el mismo teOdors que este proceso: la app lo pone en su camino de Python (main.py), no en el entorno, y sin él el hijo no lo encuentra
    # («No module named 'teodors'»). En el entorno de este proceso solo mientras se lanza, porque el hijo lo tiene que heredar
    camino, antes = procesos.entorno().get("PYTHONPATH"), os.environ.get("PYTHONPATH")
    if camino is not None:
        os.environ["PYTHONPATH"] = camino
    try:
        p = subprocess.Popen(procesos.orden("teodors.writer.informe", *casos, "--planta", str(config.PLANTA)), stdout=subprocess.PIPE,
                             stderr=subprocess.STDOUT, text=True, encoding="utf-8", errors="replace", cwd=str(config.PLANTA),
                             creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0))
    finally:
        if camino is not None and antes is None:
            os.environ.pop("PYTHONPATH", None)
        elif camino is not None:
            os.environ["PYTHONPATH"] = antes
    ultimas, ruta = deque(maxlen=12), None
    for linea in p.stdout:
        linea = linea.rstrip()
        ultimas.append(linea)
        m = re.match(r"\s*(\d+) % (.*)", linea)
        if m:
            avisa(int(m.group(1)), m.group(2))
        elif linea.startswith("Informe: "):
            ruta = linea[len("Informe: "):]
    p.wait()
    if p.returncode != 0 or not ruta:
        raise RuntimeError("el informe no se pudo hacer:\n" + "\n".join(x for x in ultimas if x and "GDAL" not in x))
    return {"pdf": ruta}


def _ajustes_de_prueba():
    """Los ajustes de Qt, en una copia de los de la app (sus escalas de color) con el estilo claro: el informe no toca los de verdad."""
    from PySide6 import QtCore
    copia = Path(config.LOCAL) / "informes" / "ajustes"
    nombre = f"{config.pide('identidad', 'ajustes')}.ini"
    origen = Path(os.environ.get("APPDATA", Path.home())) / config.ORGANIZACION / nombre
    (copia / config.ORGANIZACION).mkdir(parents=True, exist_ok=True)
    if origen.is_file():
        shutil.copy2(origen, copia / config.ORGANIZACION / nombre)
    QtCore.QSettings.setPath(QtCore.QSettings.Format.IniFormat, QtCore.QSettings.Scope.UserScope, str(copia))


def main(argv=None):
    argv = list(sys.argv[1:] if argv is None else argv)
    if not argv or argv[0] in ("-h", "--help"):
        print(__doc__)
        return 0 if argv else 1
    opciones = {o for o in argv if o.startswith("--")}
    if "--planta" in argv:
        i = argv.index("--planta")
        config.activar(argv[i + 1])
        del argv[i:i + 2]
        opciones.discard("--planta")
    desconocidas = opciones - {"--html", "--png", "--sin-viento"}
    caso = [a for a in argv if not a.startswith("--")]
    if desconocidas or len(caso) not in (1, 2):
        print("Uso: python -m teodors.writer CARPETA_DEL_CASO [CARPETA_DEL_OTRO] [--planta CARPETA] [--html] [--png] [--sin-viento]",
              file=sys.stderr)
        return 1
    for flujo in (sys.stdout, sys.stderr):
        if flujo is not None and hasattr(flujo, "reconfigure"):
            flujo.reconfigure(encoding="utf-8", errors="replace")
    config.asegurar_carpetas()
    registro.configurar(config.DIR_LOGS, config.REGISTRO)
    from PySide6 import QtCore, QtWidgets
    from PySide6 import QtWebEngineWidgets  # noqa: F401  (antes de la QApplication)
    _ajustes_de_prueba()
    QtCore.QCoreApplication.setAttribute(QtCore.Qt.ApplicationAttribute.AA_ShareOpenGLContexts)
    app = QtWidgets.QApplication([sys.argv[0]])
    app.setApplicationName(config.APP_NOMBRE)
    app.setOrganizationName(config.ORGANIZACION)
    from teodors.gui import tema
    tema.ajustes().setValue("apariencia/estilo", "claro")              # para imprimir
    tema.aplicar(app)
    solo_html = "--html" in opciones
    ventana = None
    if not solo_html:
        from teodors.gui.ventana import VentanaPrincipal
        ventana = VentanaPrincipal()
        ventana._comprobar = lambda *a, **k: None                       # sin la comprobación de la herramienta: no hace falta aquí
        ventana.resize(2100, 1400)
        ventana.show()
        ventana.move(-4000, -4000)                                      # fuera de la pantalla
    salida = {"codigo": 1}

    def acabar(codigo):
        salida["codigo"] = codigo
        QtCore.QTimer.singleShot(0, app.quit)

    def hecho(ruta):
        print(f"Informe: {ruta}", flush=True)
        acabar(0)

    def fallo(m):
        print(f"No se pudo hacer el informe: {m}", file=sys.stderr, flush=True)
        acabar(1)
    def arrancar():
        try:                                                          # un fallo, dicho y fuera: no se queda esperando
            generar(caso[0], ventana, lambda p, m: print(f"{p:3d} % {m}", flush=True), hecho, fallo, solo_html=solo_html,
                    viento="--sin-viento" not in opciones, pngs="--png" in opciones, otro=caso[1] if len(caso) == 2 else None)
        except Exception as ex:                                       # noqa: BLE001
            import traceback
            traceback.print_exc()
            fallo(f"{type(ex).__name__}: {ex}")
    QtCore.QTimer.singleShot(0, arrancar)
    app.exec()
    if ventana is not None:
        ventana.hide()
    return salida["codigo"]


if __name__ == "__main__":                     # `python -m teodors.writer.informe` (el de `lanzar`)
    sys.exit(main())
