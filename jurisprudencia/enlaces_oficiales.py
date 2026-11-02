"""Importación semiautomática desde enlaces oficiales (Corte Suprema, SUIN-Juriscol).

Estos buscadores oficiales no ofrecen una API estable. El usuario busca en el
buscador oficial, copia los enlaces de las providencias en un archivo de texto
(uno por línea) y este módulo valida cada dominio, descarga y cataloga.
"""

from __future__ import annotations

import logging
import re
from pathlib import Path
from urllib.parse import parse_qs, urlparse

from .biblioteca import Biblioteca, Documento
from .fuentes import FuenteNoOficialError, exigir_fuente_oficial
from .red import Cliente
from .texto import fragmentos, html_a_texto, pdf_a_texto

log = logging.getLogger(__name__)


def leer_enlaces(archivo: Path) -> list[str]:
    enlaces: list[str] = []
    for linea in Path(archivo).read_text(encoding="utf-8-sig").splitlines():
        linea = linea.strip()
        if linea and not linea.startswith("#") and linea not in enlaces:
            enlaces.append(linea)
    return enlaces


def _identificador(url: str, titulo: str, texto: str) -> str:
    if titulo and len(titulo) <= 150:
        titulo = re.sub(r"\s*[-|]\s*SUIN.*$", "", titulo, flags=re.I).strip()
        if titulo:
            return titulo
    for linea in texto.split("\n")[:30]:
        if 8 <= len(linea) <= 150:
            return linea
    partes = urlparse(url)
    doc_id = parse_qs(partes.query).get("id", [""])[0]
    return doc_id or Path(partes.path).stem or partes.hostname or "documento"


def _fecha(texto: str) -> str:
    """Primera fecha AAAA-MM-DD que aparezca escrita como '22 de enero de 2004'."""
    meses = {
        "enero": 1, "febrero": 2, "marzo": 3, "abril": 4, "mayo": 5, "junio": 6, "julio": 7,
        "agosto": 8, "septiembre": 9, "setiembre": 9, "octubre": 10, "noviembre": 11, "diciembre": 12,
    }
    m = re.search(
        r"\b(\d{1,2})\s*(?:\(\d+\)\s*)?de\s+(" + "|".join(meses) + r")\s+de\s+(?:dos mil[^(\d]*\(?)?(\d{4})",
        texto[:6000],
        re.I,
    )
    if not m:
        return ""
    dia, mes, anio = int(m.group(1)), meses[m.group(2).lower()], int(m.group(3))
    if not (1 <= dia <= 31 and 1990 <= anio <= 2100):
        return ""
    return f"{anio:04d}-{mes:02d}-{dia:02d}"


def importar(
    cliente: Cliente,
    biblioteca: Biblioteca,
    enlaces: list[str],
    terminos: list[str] | None = None,
) -> tuple[list[Path], list[str]]:
    """Devuelve (fichas guardadas, enlaces rechazados o fallidos)."""
    terminos = terminos or []
    guardadas: list[Path] = []
    rechazados: list[str] = []
    for url in enlaces:
        try:
            fuente = exigir_fuente_oficial(url, providencia=True)
        except FuenteNoOficialError as error:
            log.error("%s", error)
            rechazados.append(url)
            continue
        if biblioteca.ya_existe(url):
            log.info("Ya está en la biblioteca: %s", url)
            continue
        try:
            resp = cliente.get(url)
            if resp.es_pdf:
                titulo, texto, original = "", pdf_a_texto(resp.contenido), resp.contenido
            else:
                (titulo, texto), original = html_a_texto(resp.contenido), None
        except Exception as error:  # noqa: BLE001
            log.warning("No se pudo procesar %s: %s", url, error)
            rechazados.append(url)
            continue
        if not texto.strip():
            log.warning("El documento no tiene texto extraíble (¿escaneado?): %s", url)
        doc = Documento(
            identificador=_identificador(url, titulo, texto),
            corporacion=fuente.entidad,
            carpeta=fuente.carpeta,
            url=url,
            texto=texto,
            fecha=_fecha(texto),
            fragmentos=fragmentos(texto, terminos) if terminos else [],
            terminos=terminos,
            pdf_original=original,
        )
        guardadas.append(biblioteca.guardar(doc))
        log.info("Guardado: %s", doc.identificador)
    return guardadas, rechazados
