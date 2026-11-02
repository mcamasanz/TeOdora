# -*- coding: utf-8 -*-
"""Controles de la página con eventos simulados (sin ratón real): girar, acercar, hora, exageración y niveles.

Hace una copia de la página en la carpeta de trabajo con un guion de prueba al final, la abre en Edge sin pantalla y lee
el resultado del DOM.
"""
import json
import os
import re
import subprocess
import sys
from pathlib import Path

sys.stdout.reconfigure(encoding="utf-8")
AQUI = Path(__file__).resolve().parent
TMP = Path(os.environ["TEMP"]) / "ence_galera" / "99-Test" / "07_isosuperficies"
EDGE = next(p for p in (Path(os.environ.get("PROGRAMFILES(X86)", "")) / "Microsoft/Edge/Application/msedge.exe",
                        Path(os.environ.get("PROGRAMFILES", "")) / "Microsoft/Edge/Application/msedge.exe") if p.is_file())
GUION = r"""
<pre id="salida"></pre>
<script>
(function () {
  var V = window.vista, C = V.render.domElement, R = {};
  C.setPointerCapture = function () {}; C.releasePointerCapture = function () {};      // un evento simulado no tiene puntero real
  function pos() { return V.cam.position.toArray(); }
  function dist(a, b) { return Math.hypot(a[0] - b[0], a[1] - b[1], a[2] - b[2]); }
  function ev(t, x, y) { return new PointerEvent(t, {pointerId: 1, pointerType: "mouse", button: 0, buttons: 1, clientX: x, clientY: y, bubbles: true}); }
  function campo(id, v) { var e = document.getElementById(id); e.value = v; e.dispatchEvent(new Event("input", {bubbles: true})); }
  var p0 = pos(), o0 = V.ctl.getAzimuthalAngle();
  C.dispatchEvent(ev("pointerdown", 700, 400));
  C.dispatchEvent(ev("pointermove", 820, 380));
  C.dispatchEvent(ev("pointerup", 820, 380));
  setTimeout(function () {
    var p1 = pos();
    R.girar_azimut_rad = V.ctl.getAzimuthalAngle() - o0;
    var d0 = dist(p1, V.ctl.target.toArray());
    C.dispatchEvent(new WheelEvent("wheel", {deltaY: -300, deltaMode: 0, clientX: 700, clientY: 400, bubbles: true, cancelable: true}));
    setTimeout(function () {
      R.acercar_antes_m = d0; R.acercar_despues_m = dist(pos(), V.ctl.target.toArray());
      campo("h", 15);
      R.hora_texto = document.getElementById("hora").textContent;
      R.hora_grupos_visibles = Object.keys(V.grupos).filter(function (k) { return V.grupos[k].visible; });
      campo("e", 1);
      R.exageracion = V.mundo.scale.y;
      var ch = document.querySelector("#niveles input");
      ch.click();
      var g = V.grupos["15"];
      R.niveles_visibles = g.children.map(function (m) { return [m.userData.nivel, m.visible]; });
      R.errores_gl = V.render.getContext().getError();
      R.triangulos_hora_15 = g.children.reduce(function (s, m) { return s + m.geometry.index.count / 3; }, 0);
      document.getElementById("salida").textContent = JSON.stringify(R);
    }, 800);
  }, 800);
})();
</script>
</body>"""
html = (AQUI / "penacho_3d.html").read_text(encoding="utf-8")
copia = TMP / "penacho_3d_prueba.html"
copia.write_text(html.replace("</body>", GUION), encoding="utf-8")
r = subprocess.run([str(EDGE), "--headless=new", "--use-angle=swiftshader", "--enable-unsafe-swiftshader", "--ignore-gpu-blocklist",
                    f"--user-data-dir={TMP / 'perfil_edge'}", "--window-size=1400,860", "--virtual-time-budget=9000", "--dump-dom", copia.as_uri()],
                   capture_output=True, text=True, encoding="utf-8", errors="replace", timeout=180)
m = re.search(r'<pre id="salida">(.*?)</pre>', r.stdout, re.S)
if not m or not m.group(1).strip():
    raise SystemExit(f"sin resultado (rc={r.returncode}): {r.stderr[-600:]}")
res = json.loads(m.group(1).replace("&quot;", '"'))
print(res)
fallos = []
if abs(res["girar_azimut_rad"]) < 0.02:
    fallos.append("no gira")
if res["acercar_despues_m"] >= res["acercar_antes_m"]:
    fallos.append("no acerca")
if not res["hora_texto"].startswith("15 UTC") or res["hora_grupos_visibles"] != ["15"]:
    fallos.append("hora")
if res["exageracion"] != 1:
    fallos.append("exageración")
if [v for n, v in res["niveles_visibles"] if n == 1] != [False] or not all(v for n, v in res["niveles_visibles"] if n != 1):
    fallos.append("niveles")
if res["errores_gl"]:
    fallos.append("WebGL")
print("FALLOS:", fallos or "ninguno")
res["fallos"] = fallos
(AQUI / "resultados_controles.json").write_text(json.dumps(res, ensure_ascii=False, indent=1), encoding="utf-8")
copia.unlink(missing_ok=True)
