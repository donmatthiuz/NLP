"""Interfaz local: la persona resuelve el desafío en Firefox y Selenium descarga.

Iniciar con: PYTHONPATH=src venv/bin/python -m licigt.ingesta.local_browser
"""

from __future__ import annotations

import html
import json
import secrets
import tempfile
import threading
import time
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import parse_qs, urlparse

from .automatic import PortalUnavailable, ingest_nog, official_url
from .pipeline import IngestionService


class BrowserFetcher:
    """Lee la ficha visible y descarga PDF mediante la misma sesión de Firefox."""

    def __init__(self, driver, page_url: str, download_dir: Path):
        self.driver = driver
        self.page_url = page_url
        self.download_dir = download_dir

    def get(self, url: str, max_bytes: int) -> tuple[bytes, str, str]:
        if not official_url(url):
            raise ValueError("URL fuera del dominio oficial")
        if url == self.page_url:
            source = self.driver.page_source
            if any(marker in source.lower() for marker in ("cf-challenge", "cf-mitigated", "just a moment", "verifying you are human")):
                raise PortalUnavailable("El desafío de Cloudflare sigue abierto en Firefox")
            return source.encode("utf-8"), url, "text/html"
        before = {p.name for p in self.download_dir.iterdir() if p.is_file()}
        self.driver.set_page_load_timeout(45)
        try:
            self.driver.get(url)
        except Exception:
            # Firefox puede agotar el tiempo de navegación mientras descarga;
            # la comprobación real es la presencia de un PDF completo.
            pass
        end = time.monotonic() + 90
        last_size = -1
        stable = 0
        while time.monotonic() < end:
            parts = {p.name.removesuffix(".part") for p in self.download_dir.glob("*.part")}
            files = [p for p in self.download_dir.iterdir() if p.is_file() and p.name not in before and not p.name.endswith(".part")]
            for file in files:
                if file.name in parts:
                    continue
                size = file.stat().st_size
                if size > max_bytes:
                    file.unlink(missing_ok=True)
                    raise ValueError("PDF superior al límite de descarga")
                if size == last_size and size > 0:
                    stable += 1
                else:
                    stable = 0
                last_size = size
                if stable >= 2:
                    content = file.read_bytes()
                    file.unlink(missing_ok=True)
                    if content.startswith(b"%PDF-"):
                        return content, url, "application/pdf"
                    raise ValueError("El navegador descargó un archivo que no es PDF")
            time.sleep(0.5)
        raise PortalUnavailable("Firefox no completó la descarga del PDF en 90 segundos")


class State:
    def __init__(self, data_dir: Path):
        self.data_dir = data_dir
        self.token = secrets.token_urlsafe(24)
        self.status = "Abre la ficha del NOG en la pestaña de Firefox y resuelve el desafío si aparece."
        self.result: dict | None = None
        self.busy = False
        self.lock = threading.Lock()
        self.driver = None
        self.download_dir = None

    def begin(self, form: dict[str, str]) -> None:
        with self.lock:
            if self.busy:
                raise ValueError("Ya hay una descarga en curso")
            self.busy = True
            self.status = "Buscando la pestaña del NOG en Firefox…"
            self.result = None
        threading.Thread(target=self._run, args=(form,), daemon=True).start()

    def _run(self, form: dict[str, str]) -> None:
        try:
            nog = form["nog"]
            expected = f"https://www.guatecompras.gt/concursos/consultaConcurso.aspx?nog={nog}"
            target_handle = None
            for handle in self.driver.window_handles:
                self.driver.switch_to.window(handle)
                current = urlparse(self.driver.current_url)
                if official_url(self.driver.current_url) and parse_qs(current.query).get("nog") == [nog]:
                    target_handle = handle
                    break
            if target_handle is None:
                raise ValueError("Abre primero la ficha del NOG desde el enlace de esta página")
            fetcher = BrowserFetcher(self.driver, expected, self.download_dir)
            with self.lock:
                self.status = "Descargando los PDF desde la sesión de Firefox…"
            result = ingest_nog(
                nog, IngestionService(self.data_dir), fetcher=fetcher,
                title=form.get("titulo") or None, entity=form.get("entidad") or None,
                published=form.get("fecha") or None,
            )
            with self.lock:
                self.result = result
                self.status = f"Listo: {len(result['ingested'])} PDF ingeridos; {len(result['skipped'])} omitidos."
        except Exception as exc:
            with self.lock:
                self.status = f"No se completó: {exc}"
        finally:
            with self.lock:
                self.busy = False


def handler_for(state: State):
    class Handler(BaseHTTPRequestHandler):
        def do_GET(self):
            if self.path == "/status":
                with state.lock:
                    body = json.dumps({"status": state.status, "busy": state.busy, "result": state.result}, ensure_ascii=False).encode()
                self.send_response(200)
                self.send_header("Content-Type", "application/json; charset=utf-8")
                self.send_header("Cache-Control", "no-store")
                self.send_header("Content-Length", str(len(body)))
                self.end_headers()
                self.wfile.write(body)
                return
            if self.path != "/":
                self.send_error(404)
                return
            body = f"""<!doctype html><html lang="es"><meta charset="utf-8"><title>LiciGT — descarga local</title>
<style>body{{font:16px system-ui;max-width:760px;margin:3rem auto;line-height:1.5;padding:0 1rem}}label{{display:block;margin:1rem 0}}input{{display:block;width:100%;padding:.5rem;box-sizing:border-box}}button{{padding:.7rem 1.2rem}}pre{{white-space:pre-wrap;background:#eee;padding:1rem}}</style>
<h1>Descarga de documentos por NOG</h1>
<p>1. Escribe el NOG y abre la ficha en la pestaña nueva. Resuelve allí el desafío de Cloudflare.</p>
<label>NOG <input id="nog" inputmode="numeric" pattern="[0-9]+" required></label>
<button type="button" onclick="openNog()">Abrir ficha de GUATECOMPRAS</button>
<p>2. Vuelve a esta pestaña y pulsa Descargar. Los campos siguientes solo son necesarios si la ficha no informa esos datos.</p>
<form method="post" action="/download" onsubmit="document.getElementById('nogField').value=document.getElementById('nog').value">
<input type="hidden" name="token" value="{state.token}"><input type="hidden" name="nog" id="nogField">
<label>Título (opcional) <input name="titulo"></label><label>Entidad (opcional) <input name="entidad"></label>
<label>Fecha de publicación AAAA-MM-DD (opcional) <input name="fecha" type="date"></label>
<button type="submit">Descargar e ingerir PDF</button></form>
<h2>Estado</h2><pre id="status"></pre><pre id="result"></pre>
<p>Los originales y manifiestos se guardan en <code>{html.escape(str(state.data_dir))}</code>.</p>
<script>function openNog(){{let n=document.getElementById('nog').value;if(!/^\\d{{1,20}}$/.test(n)){{alert('NOG inválido');return}}window.open('https://www.guatecompras.gt/concursos/consultaConcurso.aspx?nog='+n,'_blank')}}
async function poll(){{let s=await (await fetch('/status')).json();document.getElementById('status').textContent=s.status;document.getElementById('result').textContent=s.result?JSON.stringify(s.result,null,2):''}}setInterval(poll,1500);poll()</script></html>""".encode()
            self.send_response(200)
            self.send_header("Content-Type", "text/html; charset=utf-8")
            self.send_header("Cache-Control", "no-store")
            self.send_header("Content-Length", str(len(body)))
            self.end_headers()
            self.wfile.write(body)

        def do_POST(self):
            if self.path != "/download":
                self.send_error(404)
                return
            length = int(self.headers.get("Content-Length", "0"))
            if length > 4096:
                self.send_error(413)
                return
            values = parse_qs(self.rfile.read(length).decode("utf-8", "replace"))
            form = {key: val[0] for key, val in values.items() if val}
            if form.get("token") != state.token:
                self.send_error(403)
                return
            try:
                state.begin(form)
            except (KeyError, ValueError) as exc:
                self.send_error(400, str(exc))
                return
            self.send_response(303)
            self.send_header("Location", "/")
            self.end_headers()

    return Handler


def main() -> None:
    import argparse
    from selenium import webdriver
    from selenium.webdriver.firefox.options import Options

    parser = argparse.ArgumentParser(description="Interfaz local para descargar PDF tras verificación humana")
    parser.add_argument("--data-dir", type=Path, default=Path("data/ingesta"))
    parser.add_argument("--port", type=int, default=8765)
    args = parser.parse_args()
    state = State(args.data_dir.resolve())
    with tempfile.TemporaryDirectory(prefix="licigt-firefox-") as temporary:
        state.download_dir = Path(temporary) / "descargas"
        state.download_dir.mkdir()
        options = Options()
        options.set_preference("browser.download.folderList", 2)
        options.set_preference("browser.download.dir", str(state.download_dir))
        options.set_preference("browser.helperApps.neverAsk.saveToDisk", "application/pdf,application/octet-stream")
        options.set_preference("pdfjs.disabled", True)
        options.set_preference("browser.download.alwaysOpenPanel", False)
        server = ThreadingHTTPServer(("127.0.0.1", args.port), handler_for(state))
        server_thread = threading.Thread(target=server.serve_forever, daemon=True)
        server_thread.start()
        try:
            state.driver = webdriver.Firefox(options=options)
            state.driver.get(f"http://127.0.0.1:{args.port}/")
            print(f"LiciGT listo en http://127.0.0.1:{args.port}/", flush=True)
            server_thread.join()
        finally:
            server.shutdown()
            if state.driver:
                state.driver.quit()


if __name__ == "__main__":
    main()
