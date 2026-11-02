"""Cliente HTTP que solo habla con fuentes oficiales."""

from __future__ import annotations

import time
from dataclasses import dataclass

import requests
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry

from .fuentes import exigir_fuente_oficial, fuente_de

TAMANO_MAXIMO = 60 * 1024 * 1024  # 60 MB por documento


@dataclass
class Respuesta:
    url: str
    contenido: bytes
    tipo: str  # content-type en minúsculas

    @property
    def es_pdf(self) -> bool:
        return "pdf" in self.tipo or self.contenido[:5] == b"%PDF-"


class NavegadorNoDisponible(RuntimeError):
    """Playwright no está instalado y la página requiere JavaScript."""


INSTRUCCIONES_NAVEGADOR = (
    "Esta página oficial se arma con JavaScript. Instale el navegador automatizado una sola vez:\n"
    "    pip install playwright\n"
    "    python -m playwright install chromium"
)


class Cliente:
    """Descarga con reintentos, pausa de cortesía y validación de dominio."""

    def __init__(self, pausa: float = 1.0, timeout: float = 60.0):
        self.pausa = pausa
        self.timeout = timeout
        self._ultimo = 0.0
        self.sesion = requests.Session()
        self.sesion.headers["User-Agent"] = (
            "BibliotecaJurisprudencia/1.0 (uso academico y judicial; consulta de fuentes oficiales)"
        )
        reintentos = Retry(
            total=4,
            backoff_factor=2,
            status_forcelist=(429, 500, 502, 503, 504),
            allowed_methods=("GET",),
        )
        adaptador = HTTPAdapter(max_retries=reintentos)
        self.sesion.mount("https://", adaptador)
        self.sesion.mount("http://", adaptador)

    def get(self, url: str, params: dict | None = None) -> Respuesta:
        exigir_fuente_oficial(url)
        espera = self.pausa - (time.monotonic() - self._ultimo)
        if espera > 0:
            time.sleep(espera)
        try:
            r = self.sesion.get(url, params=params, timeout=self.timeout, stream=True)
        finally:
            self._ultimo = time.monotonic()
        # Una redirección hacia un dominio no oficial también se rechaza.
        for paso in [*r.history, r]:
            exigir_fuente_oficial(paso.url)
        r.raise_for_status()
        contenido = bytearray()
        for bloque in r.iter_content(64 * 1024):
            contenido.extend(bloque)
            if len(contenido) > TAMANO_MAXIMO:
                r.close()
                raise ValueError(f"Documento demasiado grande: {url}")
        return Respuesta(r.url, bytes(contenido), r.headers.get("Content-Type", "").lower())

    # ------------------------------------------------------------ navegador
    _pw = None
    _navegador = None

    def renderizar(self, url: str, esperar_selector: str | None = None) -> Respuesta:
        """Abre la página en Chromium sin ventana (para sitios hechos con JavaScript).

        Toda petición a un dominio que no sea oficial (publicidad, estadísticas,
        redes sociales) se bloquea.
        """
        exigir_fuente_oficial(url)
        espera = self.pausa - (time.monotonic() - self._ultimo)
        if espera > 0:
            time.sleep(espera)
        if self._navegador is None:
            try:
                from playwright.sync_api import sync_playwright
            except ImportError as error:
                raise NavegadorNoDisponible(INSTRUCCIONES_NAVEGADOR) from error
            self._pw = sync_playwright().start()
            self._navegador = self._pw.chromium.launch()
        pagina = self._navegador.new_page(user_agent=self.sesion.headers["User-Agent"])

        def filtrar(ruta):
            destino = ruta.request.url
            if destino.startswith(("data:", "blob:")) or fuente_de(destino):
                ruta.continue_()
            else:
                ruta.abort()

        try:
            pagina.route("**/*", filtrar)
            pagina.goto(url, wait_until="networkidle", timeout=self.timeout * 1000)
            if esperar_selector:
                try:
                    pagina.wait_for_selector(esperar_selector, timeout=30_000)
                except Exception:  # noqa: BLE001 - se valida el contenido después
                    pass
            exigir_fuente_oficial(pagina.url)
            html = pagina.content().encode("utf-8")
            return Respuesta(pagina.url, html, "text/html; charset=utf-8")
        finally:
            pagina.close()
            self._ultimo = time.monotonic()

    def cerrar(self) -> None:
        if self._navegador is not None:
            self._navegador.close()
            self._pw.stop()
            self._navegador = self._pw = None
