"""Escritura de la biblioteca: PDF del texto completo, ficha Markdown e índice.

Regla: la ficha nunca contiene marcadores visibles. Si un dato no existe en
la fuente oficial, la línea correspondiente simplemente no se escribe.
"""

from __future__ import annotations

import csv
import re
from dataclasses import dataclass, field
from datetime import date
from pathlib import Path

from fpdf import FPDF

# Valores con los que las fuentes oficiales indican "sin dato".
_VACIOS = {"", "s.d.", "s.d", "sd", "n/a", "na", "null", "none", "-", "no aplica"}

CAMPOS_CATALOGO = ["identificador", "corporacion", "fecha", "ponente", "url", "pdf", "ficha", "consultado"]


@dataclass
class Documento:
    identificador: str  # p. ej. "T-025/04" o el título del documento
    corporacion: str
    carpeta: str
    url: str
    texto: str
    fecha: str = ""  # AAAA-MM-DD
    metadatos: dict[str, str] = field(default_factory=dict)  # etiqueta -> valor
    temas: list[str] = field(default_factory=list)
    fragmentos: list[str] = field(default_factory=list)
    terminos: list[str] = field(default_factory=list)
    pdf_original: bytes | None = None  # si la fuente publica PDF, se guarda tal cual


def tiene_valor(valor: str | None) -> bool:
    return valor is not None and str(valor).strip().lower() not in _VACIOS


def nombre_archivo(texto: str, maximo: int = 90) -> str:
    limpio = re.sub(r'[\\/:*?"<>|\s]+', " ", texto).strip()
    limpio = re.sub(r"\s+", "-", limpio)
    return (limpio[:maximo].rstrip("-.") or "documento")


class Biblioteca:
    def __init__(self, raiz: Path):
        self.raiz = Path(raiz)
        self.raiz.mkdir(parents=True, exist_ok=True)
        self.catalogo = self.raiz / "catalogo.csv"
        self._registros = self._leer_catalogo()

    # ------------------------------------------------------------------ catálogo
    def _leer_catalogo(self) -> list[dict[str, str]]:
        if not self.catalogo.exists():
            return []
        with self.catalogo.open(encoding="utf-8-sig", newline="") as f:
            return list(csv.DictReader(f))

    def ya_existe(self, url: str) -> bool:
        return any(r["url"] == url for r in self._registros)

    def _guardar_catalogo(self) -> None:
        with self.catalogo.open("w", encoding="utf-8-sig", newline="") as f:
            escritor = csv.DictWriter(f, fieldnames=CAMPOS_CATALOGO)
            escritor.writeheader()
            escritor.writerows(self._registros)
        self._escribir_indice()

    def _escribir_indice(self) -> None:
        lineas = [
            "# Biblioteca de jurisprudencia colombiana",
            "",
            "Documentos descargados exclusivamente de fuentes oficiales del Estado colombiano.",
            "",
        ]
        por_corporacion: dict[str, list[dict[str, str]]] = {}
        for r in self._registros:
            por_corporacion.setdefault(r["corporacion"], []).append(r)
        for corporacion in sorted(por_corporacion):
            lineas += [f"## {corporacion}", ""]
            for r in sorted(por_corporacion[corporacion], key=lambda x: x["fecha"], reverse=True):
                partes = [f"**{r['identificador']}**"]
                if tiene_valor(r["fecha"]):
                    partes.append(r["fecha"])
                if tiene_valor(r["ponente"]):
                    partes.append(f"M.P. {r['ponente']}")
                enlaces = f"[ficha]({_ruta_md(r['ficha'])}) · [texto completo]({_ruta_md(r['pdf'])})"
                lineas.append(f"- {' — '.join(partes)} — {enlaces}")
            lineas.append("")
        (self.raiz / "indice.md").write_text("\n".join(lineas), encoding="utf-8")

    # ------------------------------------------------------------------ guardado
    def guardar(self, doc: Documento) -> Path:
        anio = doc.fecha[:4] if re.match(r"^\d{4}", doc.fecha) else "sin-fecha"
        carpeta = self.raiz / doc.carpeta / anio
        carpeta.mkdir(parents=True, exist_ok=True)
        base = nombre_archivo(doc.identificador)
        ruta_pdf = carpeta / f"{base}.pdf"
        ruta_ficha = carpeta / f"{base} - ficha.md"

        consultado = date.today().isoformat()
        if doc.pdf_original:
            ruta_pdf.write_bytes(doc.pdf_original)
        else:
            escribir_pdf(ruta_pdf, doc, consultado)
        ruta_ficha.write_text(ficha_markdown(doc, ruta_pdf.name, consultado), encoding="utf-8")

        self._registros = [r for r in self._registros if r["url"] != doc.url]
        self._registros.append(
            {
                "identificador": doc.identificador,
                "corporacion": doc.corporacion,
                "fecha": doc.fecha,
                "ponente": doc.metadatos.get("Magistrado(a) ponente", ""),
                "url": doc.url,
                "pdf": ruta_pdf.relative_to(self.raiz).as_posix(),
                "ficha": ruta_ficha.relative_to(self.raiz).as_posix(),
                "consultado": consultado,
            }
        )
        self._guardar_catalogo()
        return ruta_ficha


def _ruta_md(ruta: str) -> str:
    return ruta.replace(" ", "%20")


def ficha_markdown(doc: Documento, nombre_pdf: str, consultado: str) -> str:
    lineas = [f"# {doc.identificador}", ""]
    datos = [("Corporación", doc.corporacion), ("Fecha", doc.fecha), *doc.metadatos.items()]
    for etiqueta, valor in datos:
        if tiene_valor(valor):
            lineas.append(f"- **{etiqueta}:** {str(valor).strip()}")
    lineas += [f"- **Fuente oficial:** {doc.url}", f"- **Fecha de consulta:** {consultado}", ""]

    if doc.temas:
        lineas += ["## Temas (descriptores de la Relatoría)", ""]
        lineas += [f"- {t}" for t in doc.temas]
        lineas.append("")
    if doc.fragmentos:
        titulo = "## Fragmentos donde aparecen los términos buscados"
        if doc.terminos:
            titulo += f" ({', '.join(doc.terminos)})"
        lineas += [titulo, ""]
        for frag in doc.fragmentos:
            lineas += [f"> {frag}", ""]
    lineas += ["## Texto completo", "", f"[{nombre_pdf}]({_ruta_md(nombre_pdf)})", ""]
    return "\n".join(lineas)


# ---------------------------------------------------------------------- PDF
_FUENTES_TTF = (
    Path("C:/Windows/Fonts/arial.ttf"),
    Path("/Library/Fonts/Arial.ttf"),
    Path("/System/Library/Fonts/Supplemental/Arial.ttf"),
    Path("/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf"),
    Path("/usr/share/fonts/TTF/DejaVuSans.ttf"),
)

_LATIN1 = str.maketrans({"“": '"', "”": '"', "‘": "'", "’": "'", "–": "-", "—": "-", "…": "...", "•": "-"})


def escribir_pdf(ruta: Path, doc: Documento, consultado: str) -> None:
    pdf = FPDF(format="Letter")
    pdf.set_auto_page_break(auto=True, margin=20)
    pdf.set_margins(22, 20, 22)
    ttf = next((p for p in _FUENTES_TTF if p.exists()), None)
    if ttf:
        pdf.add_font("Base", "", str(ttf))
        familia, convertir = "Base", (lambda s: s)
    else:
        familia = "Helvetica"
        convertir = lambda s: s.translate(_LATIN1).encode("latin-1", "replace").decode("latin-1")  # noqa: E731

    pdf.set_title(doc.identificador)
    pdf.set_author(doc.corporacion)
    pdf.add_page()
    pdf.set_font(familia, size=14)
    siguiente = {"new_x": "LMARGIN", "new_y": "NEXT"}
    pdf.multi_cell(0, 8, convertir(f"{doc.corporacion} — {doc.identificador}"), **siguiente)
    pdf.set_font(familia, size=8)
    pdf.multi_cell(
        0, 5, convertir(f"Texto tomado de la fuente oficial: {doc.url}\nFecha de consulta: {consultado}"),
        **siguiente,
    )
    pdf.ln(4)
    pdf.set_font(familia, size=10)
    for parrafo in doc.texto.split("\n"):
        if parrafo.strip():
            pdf.multi_cell(0, 5, convertir(parrafo), wrapmode="CHAR" if len(max(parrafo.split(), key=len)) > 60 else "WORD", **siguiente)
        else:
            pdf.ln(2)
    pdf.output(str(ruta))
