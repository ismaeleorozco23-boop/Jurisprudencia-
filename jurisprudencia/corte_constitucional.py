"""Búsqueda automática en la Corte Constitucional.

1. Lista oficial de sentencias: dataset v2k4-2t8s de datos.gov.co, publicado
   por la propia Corte Constitucional (1992 en adelante, actualización mensual).
2. Texto completo: Relatoría oficial,
   https://www.corteconstitucional.gov.co/relatoria/AAAA/T-025-04.htm
3. Se conservan solo las sentencias cuyo texto contiene los términos buscados.
"""

from __future__ import annotations

import json
import logging
import re
from collections.abc import Iterator
from pathlib import Path

from .biblioteca import Biblioteca, Documento
from .red import Cliente, NavegadorNoDisponible
from .texto import contiene, descriptores_relatoria, fragmentos, html_a_texto, normalizar

API_DATASET = "https://www.datos.gov.co/resource/v2k4-2t8s.json"
RELATORIA = "https://www.corteconstitucional.gov.co/relatoria/{anio}/{archivo}.htm"
TIPOS_VALIDOS = {"T", "C", "SU"}
# Contenedor de la sentencia dentro de la página de la Relatoría.
SELECTOR_TEXTO = "div.amplia"

log = logging.getLogger(__name__)


def anio_de_sentencia(numero: str) -> int:
    """'T-025/04' -> 2004; 'C-004/92' -> 1992; 'T-100/2023' -> 2023."""
    sufijo = numero.rsplit("/", 1)[-1].strip()
    if not sufijo.isdigit():
        raise ValueError(f"Número de sentencia no reconocido: {numero!r}")
    anio = int(sufijo)
    if len(sufijo) == 4:
        return anio
    return 1900 + anio if anio >= 91 else 2000 + anio


def url_relatoria(numero: str) -> str:
    numero = re.sub(r"\s+", "", numero.upper())
    if not re.fullmatch(r"(T|C|SU|A)-\d+[A-Z]?/\d{2,4}", numero):
        raise ValueError(f"Número de sentencia no reconocido: {numero!r}")
    return RELATORIA.format(anio=anio_de_sentencia(numero), archivo=numero.replace("/", "-"))


def consultar_dataset(
    cliente: Cliente,
    desde: str,
    hasta: str,
    tipos: list[str],
    lote: int = 500,
) -> Iterator[dict]:
    """Recorre la lista oficial de sentencias, de la más reciente a la más antigua."""
    for tipo in tipos:
        if tipo not in TIPOS_VALIDOS:
            raise ValueError(f"Tipo inválido {tipo!r}. Use: {', '.join(sorted(TIPOS_VALIDOS))}")
    filtro = f"fecha_sentencia between '{desde}T00:00:00' and '{hasta}T23:59:59'"
    if tipos:
        filtro += " AND sentencia_tipo in (" + ",".join(f"'{t}'" for t in tipos) + ")"
    desplazamiento = 0
    while True:
        params = {
            "$where": filtro,
            "$order": "fecha_sentencia DESC, sentencia",
            "$limit": lote,
            "$offset": desplazamiento,
        }
        filas = json.loads(cliente.get(API_DATASET, params=params).contenido)
        if not filas:
            return
        yield from filas
        if len(filas) < lote:
            return
        desplazamiento += lote


def _metadatos(fila: dict) -> dict[str, str]:
    expediente = " ".join(
        v for v in (fila.get("expediente_tipo", ""), fila.get("expediente_numero", "")) if v and v != "s.d."
    )
    return {
        "Tipo de proceso": fila.get("proceso", ""),
        "Sala": fila.get("sala", ""),
        "Expediente": expediente,
        "Magistrado(a) ponente": fila.get("magistrado_a", ""),
        "Salvamentos de voto": fila.get("sv_spv", ""),
        "Aclaraciones de voto": fila.get("av_apv", ""),
    }


def buscar(
    cliente: Cliente,
    biblioteca: Biblioteca,
    terminos: list[str],
    desde: str,
    hasta: str,
    tipos: list[str],
    modo: str = "todas",
    maximo: int = 20,
    max_revisar: int = 300,
    cache: Path | None = None,
) -> list[Path]:
    guardadas: list[Path] = []
    revisadas = 0
    for fila in consultar_dataset(cliente, desde, hasta, tipos):
        if len(guardadas) >= maximo or revisadas >= max_revisar:
            break
        numero = (fila.get("sentencia") or "").strip()
        try:
            url = url_relatoria(numero)
        except ValueError:
            log.warning("Se omite registro con número no reconocido: %r", numero)
            continue
        if biblioteca.ya_existe(url):
            log.info("Ya está en la biblioteca: %s", numero)
            continue
        revisadas += 1
        try:
            texto = texto_sentencia(cliente, url, numero, cache)
        except NavegadorNoDisponible:
            raise
        except Exception as error:  # noqa: BLE001 - se informa y se sigue con la siguiente
            log.warning("No se pudo obtener %s (%s): %s", numero, url, error)
            continue
        if not contiene(texto, terminos, modo):
            log.debug("Sin coincidencia: %s", numero)
            continue
        doc = Documento(
            identificador=f"Sentencia {numero}",
            corporacion="Corte Constitucional",
            carpeta="Corte Constitucional",
            url=url,
            texto=texto,
            fecha=(fila.get("fecha_sentencia") or "")[:10],
            metadatos=_metadatos(fila),
            temas=descriptores_relatoria(texto),
            fragmentos=fragmentos(texto, terminos),
            terminos=terminos,
        )
        guardadas.append(biblioteca.guardar(doc))
        log.info("Guardada: %s", numero)
    log.info("Revisadas %d sentencias; guardadas %d.", revisadas, len(guardadas))
    return guardadas


def es_texto_de(texto: str, numero: str) -> bool:
    """Comprueba que el texto sea realmente la sentencia y no una página vacía o de error."""
    base = normalizar(texto)
    variantes = {normalizar(numero), normalizar(numero.replace("/", "-"))}
    return len(texto) >= 1500 and any(v in base for v in variantes)


def texto_sentencia(cliente: Cliente, url: str, numero: str, cache: Path | None) -> str:
    """Texto de la sentencia. Intenta descarga directa; si la página llega vacía
    (sitio armado con JavaScript), la abre con el navegador automatizado."""
    archivo = None
    if cache is not None:
        archivo = cache / (url.rsplit("/", 2)[-2] + "_" + url.rsplit("/", 1)[-1])
        if archivo.exists():
            _, texto = html_a_texto(archivo.read_bytes(), SELECTOR_TEXTO)
            if es_texto_de(texto, numero):
                return texto
    contenido = cliente.get(url).contenido
    _, texto = html_a_texto(contenido, SELECTOR_TEXTO)
    if not es_texto_de(texto, numero):
        log.debug("Descarga directa sin texto para %s; se usa el navegador.", numero)
        contenido = cliente.renderizar(url, SELECTOR_TEXTO).contenido
        _, texto = html_a_texto(contenido, SELECTOR_TEXTO)
        if not es_texto_de(texto, numero):
            raise ValueError("la página oficial no devolvió el texto de la sentencia")
    if archivo is not None:
        archivo.parent.mkdir(parents=True, exist_ok=True)
        archivo.write_bytes(contenido)
    return texto
