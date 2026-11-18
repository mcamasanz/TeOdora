# -*- coding: utf-8 -*-
"""Del HTML del informe al PDF, con el motor web de la app (sin nada más que instalar), y, si se pide, cada página en PNG.

Qt se carga al usarlo, no al importar esto.
"""
from pathlib import Path

from teodors.comun import registro

log = registro.get("writer")

_vivas = []                     # las páginas web que están imprimiendo: si no, Python las recogería antes de acabar

# Cada página que no cabe (su contenido pasa de su margen de abajo, 16 mm) se aprieta por niveles (estilo: .apretada-1 a 3): letra, márgenes,
# mapas. Devuelve las que siguen sin caber.
AJUSTAR_JS = """(function(){
  var mm = 96 / 25.4, siguen = [];
  document.querySelectorAll('section.pag').forEach(function (s, k) {
    if (s.classList.contains('portada')) { return; }
    function rebosa() {
      var limite = s.getBoundingClientRect().bottom - 16 * mm, abajo = 0;
      Array.prototype.forEach.call(s.children, function (c) {
        if (c.classList.contains('pie') || c.classList.contains('cab')) { return; }
        abajo = Math.max(abajo, c.getBoundingClientRect().bottom);
      });
      return abajo > limite + 1;
    }
    for (var n = 1; n <= 3 && rebosa(); n++) { s.classList.add('apretada-' + n); }
    if (rebosa()) { siguen.push(k + 1); }
  });
  return siguen;
})()"""


def imprimir(html, pdf, al_acabar, pngs=None, espera_ms=1500):
    """Imprime `html` en `pdf` (A4, sin márgenes: los pone el informe) y llama a `al_acabar(ok, pdf)`. Con `pngs`, una carpeta: deja allí cada
    página como pagina_NN.png."""
    from PySide6 import QtCore, QtGui
    from PySide6.QtWebEngineCore import QWebEnginePage
    html, pdf = Path(html), Path(pdf)
    pdf.parent.mkdir(parents=True, exist_ok=True)
    pagina = QWebEnginePage()
    _vivas.append(pagina)

    def cargado(ok):
        if not ok:
            _vivas.remove(pagina)
            al_acabar(False, pdf)
            return
        disposicion = QtGui.QPageLayout(QtGui.QPageSize(QtGui.QPageSize.PageSizeId.A4), QtGui.QPageLayout.Orientation.Portrait,
                                        QtCore.QMarginsF(0, 0, 0, 0))

        def ajustado(siguen):
            if siguen:
                log.warning(f"Informe: {'la página' if len(siguen) == 1 else 'las páginas'} {', '.join(map(str, siguen))} no caben del todo.")
            pagina.printToPdf(str(pdf), disposicion)
        QtCore.QTimer.singleShot(espera_ms, lambda: pagina.runJavaScript(AJUSTAR_JS, 0, ajustado))

    def hecho(_ruta, ok):
        if ok and pngs is not None:
            a_png(pdf, pngs)
        _vivas.remove(pagina)
        al_acabar(ok, pdf)
    pagina.loadFinished.connect(cargado)
    pagina.pdfPrintingFinished.connect(hecho)
    pagina.load(QtCore.QUrl.fromLocalFile(str(html)))


def a_png(pdf, carpeta, ancho=1240):
    """Cada página del PDF, en `carpeta`/pagina_NN.png (`ancho` px). Devuelve cuántas."""
    from PySide6 import QtCore
    from PySide6.QtPdf import QPdfDocument
    carpeta = Path(carpeta)
    carpeta.mkdir(parents=True, exist_ok=True)
    doc = QPdfDocument()
    doc.load(str(pdf))
    for i in range(doc.pageCount()):
        doc.render(i, QtCore.QSize(ancho, round(ancho * 297 / 210))).save(str(carpeta / f"pagina_{i + 1:02d}.png"))
    return doc.pageCount()
