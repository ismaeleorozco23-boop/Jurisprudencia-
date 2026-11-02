"""Extracción de texto y búsqueda de términos."""

from __future__ import annotations

import io
import re
import unicodedata

from bs4 import BeautifulSoup


def normalizar(texto: str) -> str:
    """Minúsculas y sin tildes, para comparar 'Constitución' con 'constitucion'."""
    sin_tildes = unicodedata.normalize("NFD", texto)
    sin_tildes = "".join(c for c in sin_tildes if unicodedata.category(c) != "Mn")
    return re.sub(r"\s+", " ", sin_tildes).lower()


_BLOQUES = ("p", "div", "br", "li", "tr", "h1", "h2", "h3", "h4", "h5", "h6", "table", "section", "blockquote")


def html_a_texto(contenido: bytes | str, selector: str | None = None) -> tuple[str, str]:
    """Devuelve (titulo, texto) de un documento HTML.

    Los HTML exportados desde Word cortan las frases con saltos de línea; aquí
    los saltos internos se convierten en espacios y solo los elementos de
    bloque (párrafos, celdas, títulos) generan un salto de línea real.
    """
    sopa = BeautifulSoup(contenido, "html.parser")
    titulo = sopa.title.get_text(" ", strip=True) if sopa.title else ""
    for etiqueta in sopa(["script", "style", "noscript", "header", "footer", "nav", "button"]):
        etiqueta.decompose()
    raiz = (sopa.select_one(selector) if selector else None) or sopa.body or sopa
    for nodo in raiz.find_all(string=True):
        nodo.replace_with(re.sub(r"\s+", " ", str(nodo)))
    for bloque in raiz.find_all(_BLOQUES):
        bloque.insert_after("\n")
    return titulo, limpiar(raiz.get_text(""))


def pdf_a_texto(contenido: bytes) -> str:
    from pypdf import PdfReader

    lector = PdfReader(io.BytesIO(contenido))
    return limpiar("\n".join((pagina.extract_text() or "") for pagina in lector.pages))


def limpiar(texto: str) -> str:
    texto = texto.replace("\xa0", " ").replace("\r", "")
    lineas = [re.sub(r"[ \t]+", " ", linea).strip() for linea in texto.split("\n")]
    salida: list[str] = []
    for linea in lineas:
        if linea or (salida and salida[-1]):
            salida.append(linea)
    return "\n".join(salida).strip()


def contiene(texto: str, terminos: list[str], modo: str = "todas") -> bool:
    """modo='todas': deben aparecer todos los términos; 'alguna': basta uno."""
    if not terminos:
        return True
    base = normalizar(texto)
    hallados = [normalizar(t) in base for t in terminos]
    return all(hallados) if modo == "todas" else any(hallados)


def fragmentos(texto: str, terminos: list[str], radio: int = 350, maximo: int = 3) -> list[str]:
    """Extractos literales del texto alrededor de cada término buscado."""
    plano = re.sub(r"\s+", " ", texto)
    base = normalizar(plano)
    # normalizar() conserva la longitud cuando el texto ya no tiene espacios dobles,
    # salvo letras compuestas raras; se valida para no cortar mal.
    if len(base) != len(plano):
        return []
    resultado: list[str] = []
    usados: list[tuple[int, int]] = []
    for termino in terminos:
        clave = normalizar(termino)
        pos = base.find(clave)
        if pos < 0:
            continue
        ini, fin = max(0, pos - radio), min(len(plano), pos + len(clave) + radio)
        if any(ini < f and fin > i for i, f in usados):
            continue
        usados.append((ini, fin))
        extracto = plano[ini:fin].strip()
        if ini > 0:
            extracto = "…" + extracto
        if fin < len(plano):
            extracto += "…"
        resultado.append(extracto)
        if len(resultado) >= maximo:
            break
    return resultado


_FIN_DESCRIPTORES = re.compile(
    r"^(referencia|ref\.|expediente|magistrad|accionante|actor|demandante|bogot|procedencia|norma demandada)",
    re.I,
)
# Encabezado en mayúsculas seguido de guion y subtema, o el encabezado solo.
_DESCRIPTOR = re.compile(r"^[A-ZÁÉÍÓÚÑÜ][A-ZÁÉÍÓÚÑÜ0-9 ,.;()]{5,}(?:\s*[-–‑]\s*\S|$)")
_NO_DESCRIPTOR = re.compile(r"^(REP[UÚ]BLICA DE COLOMBIA|SENTENCIA\b|AUTO\b|CORTE CONSTITUCIONAL|SALA\b)", re.I)


def descriptores_relatoria(texto: str, maximo: int = 15) -> list[str]:
    """Temas que la Relatoría de la Corte Constitucional pone al inicio de cada sentencia.

    Son párrafos del tipo 'DERECHO A LA SALUD -Alcance', a veces encadenados con
    '/'. Si no se detectan con seguridad se devuelve una lista vacía y la ficha
    omite la sección.
    """
    temas: list[str] = []
    for parrafo in texto.split("\n")[:600]:
        parrafo = parrafo.strip()
        if not parrafo:
            continue
        if _FIN_DESCRIPTORES.match(parrafo):
            break
        if _NO_DESCRIPTOR.match(parrafo):
            continue
        for parte in re.split(r"\s*/\s*(?=[A-ZÁÉÍÓÚÑ]{3})", parrafo):
            if not _DESCRIPTOR.match(parte):
                continue
            tema = re.sub(r"\s*[-–]\s*", "-", parte, count=1).strip(" /")
            if tema not in temas and len(tema) <= 200:
                temas.append(tema)
            if len(temas) >= maximo:
                return temas
    return temas
