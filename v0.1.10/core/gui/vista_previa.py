# -*- coding: utf-8 -*-
"""Mapa de la ventana de configuración: un campo de viento y un penacho guardados, para ver cómo quedan las escalas de
color. Solo sirven para eso (usuario, 2026-11-01): el mapa principal no tiene viento hasta elegir la meteorología ni
penacho hasta simular.

Los datos van con la planta (`operacion.ejemplo` de planta.json, de `operacion.ejemplo_configuracion`): se ven también sin la unidad de datos.
No son un resultado, y por eso su leyenda no lleva unidades. Una planta nueva aún no los tiene: el mapa sale sin viento ni penacho."""
import json

from teodors import planta as config
from teodors.gui.mapa import VistaMapa
from teodors.operacion import penacho_mapa
from teodors.operacion.ejemplo_configuracion import carpeta_ejemplo


class VistaPrevia(VistaMapa):

    def __init__(self, emp, parent=None):
        super().__init__(parent)
        self._ejemplo = carpeta_ejemplo().resolve()
        ficha = self._ejemplo / "ejemplo.json"
        self._meta = json.loads(ficha.read_text(encoding="utf-8")) if ficha.is_file() else None
        self.listo.connect(self._rellenar)
        encuadre = self._meta["encuadre"] if self._meta else [[emp["lat"] - 0.03, emp["lon"] - 0.03], [emp["lat"] + 0.03, emp["lon"] + 0.03]]
        self.cargar(emp, encuadre, ruta=config.DIR_WEB / "mapa_previa.html")

    def _rellenar(self):
        self.js("document.querySelector('.leaflet-control-layers').style.display='none'")
        if self._meta is None:
            return
        imagenes = [{"url": (self._ejemplo / f"penacho_{k}.png").as_uri(), "limites": lim}
                    for k, lim in enumerate(self._meta["limites"])]
        for escala, titulo in (("olor", "Olores"), ("gases", "Gases")):
            leyenda = penacho_mapa.leyenda_html({"vmin": self._meta["vmin"], "decadas": self._meta["decadas"],
                                                 "escala": escala}, titulo)
            self.set_imagenes(f"previa_{escala}", titulo, imagenes, leyenda, visible=escala == "olor",
                              opacidad=penacho_mapa.OPACIDAD, grupo="previa", escala=escala)
        viento = json.loads((self._ejemplo / "viento.json").read_text(encoding="utf-8"))
        self.set_viento(dict(viento, opciones={"nmax": 1200, "ms": 50}))

    def ver_escala(self, escala):
        """Enseña el penacho con la escala de esa magnitud («olor» o «gases»)."""
        if self._meta:
            self.ver_capa(f"previa_{escala}")
