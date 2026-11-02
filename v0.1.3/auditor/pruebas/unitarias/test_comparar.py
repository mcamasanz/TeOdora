# -*- coding: utf-8 -*-
"""La comparación de salidas detecta cualquier cambio de resultados y solo ignora la fecha y la hora
de la corrida (y, al contrastar con el original, los finales de línea)."""
import struct

from auditor.comparar import comparar_carpetas, diferencia


def _escribir(ruta, texto):
    ruta.write_bytes(texto if isinstance(texto, bytes) else texto.encode("latin-1"))
    return ruta


def test_iguales_salvo_fecha_y_hora(tmp_path):
    a = _escribir(tmp_path / "a.out", " *** v1 ***   10/18/26\n   20:25:40\n VALOR  0.317307E+02\n")
    b = _escribir(tmp_path / "b.out", " *** v1 ***   01/02/27\n   08:00:01\n VALOR  0.317307E+02\n")
    assert diferencia(a, b) == ""


def test_ignora_la_fecha_en_todos_los_formatos_de_los_motores(tmp_path):
    # cada pareja: la misma línea escrita otro día y a otra hora
    parejas = [
        (" START PROCESSING DATE/TIME: OCTOBER 18, 2026  20:25:40 PM\n",     # capa_limite, informe
         " START PROCESSING DATE/TIME: MAY 3, 2027  09:05:03 AM\n"),
        (" PRIMARY UPPER AIR EXTRACTION BEGIN 20261018 20:25:40\n",          # capa_limite, mensajes
         " PRIMARY UPPER AIR EXTRACTION BEGIN 20270503  9: 5: 3\n"),
        (" DATE : 10/18/2026\n TIME : 21:16:40\n",                           # edificios
         " DATE :  1/ 5/2027\n TIME :  9: 6: 4\n"),
        (" *** AERMOD ***   10/18/26\n   20:25:40\n",                        # penacho, relieve, superficie
         " *** AERMOD ***   01/05/27\n   09:05:03\n"),
    ]
    for i, (hoy, otro_dia) in enumerate(parejas):
        a = _escribir(tmp_path / ("a%d" % i), hoy)
        b = _escribir(tmp_path / ("b%d" % i), otro_dia)
        assert diferencia(a, b) == "", hoy


def test_las_fechas_de_los_datos_no_se_ignoran(tmp_path):
    # una fecha de sondeo sin hora detrás es un dato, no la fecha de la corrida
    a = _escribir(tmp_path / "a.msg", " SOUNDING #     4 DATE: 20230601 HR 12\n")
    b = _escribir(tmp_path / "b.msg", " SOUNDING #     4 DATE: 20230602 HR 12\n")
    assert diferencia(a, b) != ""


def test_ignora_la_duracion_de_la_corrida(tmp_path):
    a = _escribir(tmp_path / "a.lst", "Celdas: 400\nTiempo: 0.03 s\n")
    b = _escribir(tmp_path / "b.lst", "Celdas: 400\nTiempo: 12.5 s\n")
    c = _escribir(tmp_path / "c.lst", "Celdas: 401\nTiempo: 0.03 s\n")
    assert diferencia(a, b) == ""
    assert "Celdas: 401" in diferencia(a, c)


def test_detecta_un_digito_cambiado(tmp_path):
    a = _escribir(tmp_path / "a.out", " VALOR  0.317307E+02\n")
    b = _escribir(tmp_path / "b.out", " VALOR  0.317308E+02\n")
    d = diferencia(a, b)
    assert "línea 1" in d and "0.317308E+02" in d


def test_detecta_lineas_de_mas(tmp_path):
    a = _escribir(tmp_path / "a.out", "x\n")
    b = _escribir(tmp_path / "b.out", "x\ny\n")
    assert "longitud distinta" in diferencia(a, b)


def test_finales_de_linea_solo_se_ignoran_al_contrastar(tmp_path):
    a = _escribir(tmp_path / "a.txt", "x\r\ny\r\n")
    b = _escribir(tmp_path / "b.txt", "x\ny\n")
    assert diferencia(a, b) != ""
    assert diferencia(a, b, contraste=True) == ""


def _postfile(valores):
    datos = b"".join(struct.pack("<d", v) for v in valores)
    cuerpo = b"\x00" * 16 + datos
    n = struct.pack("<i", len(cuerpo))
    return n + cuerpo + n


def test_binario_exacto_en_regresion_y_ultimos_bits_al_contrastar(tmp_path):
    a = _escribir(tmp_path / "a.pst", _postfile([1.0, 2.0]))
    b = _escribir(tmp_path / "b.pst", _postfile([1.0, 2.0 * (1 + 1e-15)]))
    assert diferencia(a, b) == "binario distinto"
    assert diferencia(a, b, contraste=True) == ""
    c = _escribir(tmp_path / "c.pst", _postfile([1.0, 2.1]))
    assert diferencia(a, c, contraste=True).startswith("binario distinto")


def test_falta_un_fichero(tmp_path):
    (tmp_path / "ref").mkdir()
    (tmp_path / "obt").mkdir()
    _escribir(tmp_path / "ref" / "s.out", "x\n")
    assert comparar_carpetas(tmp_path / "ref", tmp_path / "obt", ["s.out"]) == ["s.out: no se ha generado"]
