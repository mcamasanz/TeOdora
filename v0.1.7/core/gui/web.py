# -*- coding: utf-8 -*-
"""HTML AUTÓNOMO para los mapas: los <script src=CDN> y <link href=CDN.css> se sustituyen por
su contenido y las fuentes .woff2 / imágenes .png del CSS van dentro como data-URI.

Motivo: en el PC del operario
el navegador embebido puede tener bloqueados los CDN aunque Python tenga salida, y el mapa
saldría en blanco. Las teselas siguen siendo online.
⚠️ Las librerías embebidas (Leaflet BSD-2, folium MIT, Font Awesome, Bootstrap, jQuery MIT)
deben figurar en el THIRD-PARTY-NOTICES del producto.
"""
import base64
import hashlib
import re
import urllib.parse
import urllib.request
from pathlib import Path

from teodors.comun import registro

log = registro.get("web")


def _descarga(url, cache, binario=False):
    cache.mkdir(parents=True, exist_ok=True)
    fn = cache / (hashlib.md5(url.encode()).hexdigest() + "_" + url.split("/")[-1].split("?")[0])
    if fn.exists():
        return fn.read_bytes() if binario else fn.read_text(encoding="utf-8", errors="replace")
    try:
        req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0"})
        b = urllib.request.urlopen(req, timeout=40).read()
        fn.write_bytes(b)
        return b if binario else b.decode("utf-8", "replace")
    except Exception as e:
        log.warning(f"Recurso web no disponible ({url.split('/')[-1]}): {e!r}")
        return None


def _incrusta_recursos_css(css, css_url, cache):
    def _sub(m):
        rel = m.group(1).strip("'\"")
        ext = rel.split("?")[0].rsplit(".", 1)[-1].lower()
        mime = {"woff2": "font/woff2", "png": "image/png"}.get(ext)
        if rel.startswith("data:") or mime is None:
            return m.group(0)
        b = _descarga(urllib.parse.urljoin(css_url, rel), cache, binario=True)
        return m.group(0) if b is None else \
            f"url(data:{mime};base64," + base64.b64encode(b).decode() + ")"
    return re.sub(r"url\(([^)]+)\)", _sub, css)


def hacer_autonomo(html_path, cache):
    """Reescribe el HTML en su sitio. Devuelve (n_js, n_css) embebidos."""
    html = Path(html_path).read_text(encoding="utf-8", errors="replace")
    n_js = n_css = 0
    for tag in set(re.findall(r'<script src="https?://[^"]+"[^>]*></script>', html)):
        url = re.search(r'src="([^"]+)"', tag).group(1)
        js = _descarga(url, cache)
        if js is not None:
            js = js.replace("</script>", "<\\/script>")
            html = html.replace(tag, "<script>\n" + js + "\n</script>")
            n_js += 1
    for tag in set(re.findall(r'<link[^>]*href="https?://[^"]+"[^>]*>', html)):
        url = re.search(r'href="([^"]+)"', tag).group(1)
        if "stylesheet" not in tag and not url.lower().endswith(".css"):
            continue
        css = _descarga(url, cache)
        if css is not None:
            html = html.replace(tag, "<style>\n" + _incrusta_recursos_css(css, url, cache)
                                + "\n</style>")
            n_css += 1
    html = html.replace("</head>", "<style>.leaflet-container{background:var(--fondo,#e9e9e9) "
                        "!important;}</style></head>", 1)
    Path(html_path).write_text(html, encoding="utf-8")
    return n_js, n_css
