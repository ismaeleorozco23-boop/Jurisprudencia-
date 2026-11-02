"""Lista cerrada de fuentes oficiales colombianas.

Regla no negociable del proyecto: solo se acepta material publicado por
entidades oficiales de Colombia. Cualquier URL cuyo dominio no esté en
esta lista se rechaza antes de descargarla y también después de seguir
redirecciones.
"""

from __future__ import annotations

from dataclasses import dataclass
from urllib.parse import urlparse


@dataclass(frozen=True)
class Fuente:
    dominio: str
    entidad: str
    carpeta: str
    publica_providencias: bool = True


# Para agregar una fuente nueva basta con añadir una línea aquí.
# Solo dominios .gov.co de entidades del Estado colombiano.
FUENTES_OFICIALES: tuple[Fuente, ...] = (
    Fuente("corteconstitucional.gov.co", "Corte Constitucional", "Corte Constitucional"),
    Fuente("cortesuprema.gov.co", "Corte Suprema de Justicia", "Corte Suprema de Justicia"),
    Fuente("ramajudicial.gov.co", "Rama Judicial", "Rama Judicial"),
    Fuente("suin-juriscol.gov.co", "SUIN-Juriscol (Ministerio de Justicia y del Derecho)", "SUIN-Juriscol"),
    # Solo se usa para metadatos publicados por la propia Corte Constitucional.
    Fuente("datos.gov.co", "Portal Nacional de Datos Abiertos", "Datos Abiertos", publica_providencias=False),
)


class FuenteNoOficialError(ValueError):
    """La URL no pertenece a una fuente oficial colombiana autorizada."""


def fuente_de(url: str) -> Fuente | None:
    """Devuelve la fuente oficial a la que pertenece la URL, o None."""
    partes = urlparse(url.strip())
    if partes.scheme not in ("http", "https"):
        return None
    host = (partes.hostname or "").lower().rstrip(".")
    if not host:
        return None
    for fuente in FUENTES_OFICIALES:
        if host == fuente.dominio or host.endswith("." + fuente.dominio):
            return fuente
    return None


def exigir_fuente_oficial(url: str, providencia: bool = False) -> Fuente:
    """Valida la URL. Con providencia=True exige además que la fuente publique
    providencias (el portal de datos abiertos solo aporta metadatos)."""
    fuente = fuente_de(url)
    if fuente is None:
        raise FuenteNoOficialError(
            f"Rechazado: {url!r} no pertenece a una fuente oficial colombiana autorizada."
        )
    if providencia and not fuente.publica_providencias:
        raise FuenteNoOficialError(
            f"Rechazado: {fuente.dominio} no es una fuente de providencias judiciales."
        )
    return fuente
