import csv
import json
import re
from pathlib import Path

import pytest
from fpdf import FPDF

from jurisprudencia import corte_constitucional, enlaces_oficiales
from jurisprudencia.biblioteca import Biblioteca
from jurisprudencia.fuentes import FuenteNoOficialError, exigir_fuente_oficial, fuente_de
from jurisprudencia.red import Respuesta
from jurisprudencia.texto import contiene, descriptores_relatoria, fragmentos, html_a_texto

RELLENO = "<p>" + "Consideraciones de la Sala sobre el caso concreto. " * 40 + "</p>"

SENTENCIA_HTML = ("""<html><head><meta charset="utf-8"><title>T-025/04</title></head><body>
<nav>Inicio La Corte Relatoría</nav>
<div class="amplia">
<p>REPÚBLICA DE COLOMBIA</p><p>Sentencia T-025/04</p>
<p>AGENCIA OFICIOSA EN TUTELA
-Asociaciones de desplazados
/AGENCIA
OFICIOSA EN TUTELA
-Condiciones para que las asociaciones de desplazados interpongan la acción</p>
<p>Dada la condición de extrema vulnerabilidad de la población desplazada, procede.</p>
<p>ESTADO DE COSAS INCONSTITUCIONAL-Concepto</p>
<p>Referencia: expediente T-653010</p>
<p>Bogotá, D.C., veintidós (22) de enero de dos mil cuatro (2004).</p>
<p>La Corte declara el estado de cosas inconstitucional en la situación de la
población desplazada.</p>""" + RELLENO + """
</div><footer>Sede principal calle 12</footer></body></html>""").encode("utf-8")

PAGINA_VACIA = b"<html><body><app-root></app-root><script src='main.js'></script></body></html>"

OTRA_HTML = ("<html><body><div class='amplia'><p>Sentencia T-100/04</p><p>Servicios públicos.</p>"
             + RELLENO + "</div></body></html>").encode()

FILAS = [
    {"proceso": "Tutela", "expediente_tipo": "T", "expediente_numero": "653010",
     "magistrado_a": "Manuel José Cepeda Espinosa", "sala": "Sala Tercera de Revisión",
     "sentencia_tipo": "T", "sentencia": "T-025/04", "fecha_sentencia": "2004-01-22T00:00:00.000",
     "sv_spv": "s.d.", "av_apv": "s.d."},
    {"proceso": "Tutela", "expediente_tipo": "T", "expediente_numero": "1",
     "magistrado_a": "Otro", "sala": "Sala", "sentencia_tipo": "T", "sentencia": "T-100/04",
     "fecha_sentencia": "2004-02-01T00:00:00.000", "sv_spv": "s.d.", "av_apv": "s.d."},
]


class ClienteFalso:
    def __init__(self, respuestas, renderizadas=None):
        self.respuestas = respuestas
        self.renderizadas = renderizadas or {}
        self.pedidas = []

    def renderizar(self, url, esperar_selector=None):
        exigir_fuente_oficial(url)
        self.pedidas.append((url, "navegador"))
        return Respuesta(url, self.renderizadas[url], "text/html")

    def get(self, url, params=None):
        exigir_fuente_oficial(url)
        self.pedidas.append((url, params))
        if url == corte_constitucional.API_DATASET:
            filas = FILAS if params["$offset"] == 0 else []
            return Respuesta(url, json.dumps(filas).encode(), "application/json")
        contenido, tipo = self.respuestas[url]
        return Respuesta(url, contenido, tipo)


def pdf_valido() -> bytes:
    pdf = FPDF()
    pdf.add_page()
    pdf.set_font("Helvetica", size=12)
    pdf.cell(0, 10, "Sala de Casacion Civil - 3 de marzo de 2021 - embargo")
    return bytes(pdf.output())


# ------------------------------------------------------------------ fuentes
@pytest.mark.parametrize("url", [
    "https://www.corteconstitucional.gov.co/relatoria/2004/T-025-04.htm",
    "https://consultajurisprudencial.ramajudicial.gov.co/WebRelatoria/csj/index.xhtml",
    "https://www.suin-juriscol.gov.co/viewDocument.asp?id=30019250",
    "https://cortesuprema.gov.co/corte/wp-content/uploads/relatorias/x.pdf",
])
def test_acepta_fuentes_oficiales(url):
    assert fuente_de(url) is not None


@pytest.mark.parametrize("url", [
    "https://www.corteconstitucional.gov.co.sitiofalso.com/x",
    "https://vlex.com.co/sentencia",
    "https://corteconstitucional.gov.co@evil.com/x",
    "https://www.tribunalconstitucional.es/sentencia",
    "ftp://www.corteconstitucional.gov.co/x",
    "https://fakecortesuprema.gov.co/x",
])
def test_rechaza_fuentes_no_oficiales(url):
    with pytest.raises(FuenteNoOficialError):
        exigir_fuente_oficial(url)


def test_datos_abiertos_no_es_fuente_de_providencias():
    with pytest.raises(FuenteNoOficialError):
        exigir_fuente_oficial("https://www.datos.gov.co/resource/x.json", providencia=True)


# ------------------------------------------------------------------ Corte Constitucional
@pytest.mark.parametrize("numero,esperada", [
    ("T-025/04", "https://www.corteconstitucional.gov.co/relatoria/2004/T-025-04.htm"),
    ("C-004/92", "https://www.corteconstitucional.gov.co/relatoria/1992/C-004-92.htm"),
    ("SU-039/97", "https://www.corteconstitucional.gov.co/relatoria/1997/SU-039-97.htm"),
    ("t-760/08", "https://www.corteconstitucional.gov.co/relatoria/2008/T-760-08.htm"),
])
def test_url_relatoria(numero, esperada):
    assert corte_constitucional.url_relatoria(numero) == esperada


def test_url_relatoria_invalida():
    with pytest.raises(ValueError):
        corte_constitucional.url_relatoria("cualquier cosa")


def test_busqueda_sin_tildes_y_modos():
    texto = "La Corte protege a la población desplazada."
    assert contiene(texto, ["poblacion desplazada"])
    assert not contiene(texto, ["desplazada", "pensión"], "todas")
    assert contiene(texto, ["desplazada", "pensión"], "alguna")


def test_fragmento_es_literal():
    texto = "Inicio. " * 100 + "La población desplazada merece protección." + " Fin." * 100
    frag = fragmentos(texto, ["poblacion desplazada"])
    assert len(frag) == 1 and "población desplazada" in frag[0]


def test_descriptores_formato_real():
    _, texto = html_a_texto(SENTENCIA_HTML, corte_constitucional.SELECTOR_TEXTO)
    assert descriptores_relatoria(texto) == [
        "AGENCIA OFICIOSA EN TUTELA-Asociaciones de desplazados",
        "AGENCIA OFICIOSA EN TUTELA-Condiciones para que las asociaciones de desplazados interpongan la acción",
        "ESTADO DE COSAS INCONSTITUCIONAL-Concepto",
    ]


def test_texto_une_lineas_y_quita_menu():
    _, texto = html_a_texto(SENTENCIA_HTML, corte_constitucional.SELECTOR_TEXTO)
    assert "situación de la población desplazada" in texto
    assert "Inicio La Corte" not in texto and "Sede principal" not in texto


def test_pagina_vacia_usa_navegador(tmp_path):
    url = corte_constitucional.url_relatoria("T-025/04")
    cliente = ClienteFalso({url: (PAGINA_VACIA, "text/html")}, {url: SENTENCIA_HTML})
    texto = corte_constitucional.texto_sentencia(cliente, url, "T-025/04", tmp_path)
    assert "estado de cosas inconstitucional" in texto
    assert (url, "navegador") in cliente.pedidas
    # El caché guarda la versión válida: la siguiente vez no se descarga nada.
    pedidas = len(cliente.pedidas)
    corte_constitucional.texto_sentencia(cliente, url, "T-025/04", tmp_path)
    assert len(cliente.pedidas) == pedidas


def test_pagina_sin_sentencia_falla(tmp_path):
    url = corte_constitucional.url_relatoria("T-025/04")
    cliente = ClienteFalso({url: (PAGINA_VACIA, "text/html")}, {url: PAGINA_VACIA})
    with pytest.raises(ValueError):
        corte_constitucional.texto_sentencia(cliente, url, "T-025/04", None)


def test_flujo_constitucional(tmp_path):
    cliente = ClienteFalso({
        corte_constitucional.url_relatoria("T-025/04"): (SENTENCIA_HTML, "text/html"),
        corte_constitucional.url_relatoria("T-100/04"): (OTRA_HTML, "text/html"),
    })
    bib = Biblioteca(tmp_path)
    fichas = corte_constitucional.buscar(
        cliente, bib, ["población desplazada"], "2004-01-01", "2004-12-31", ["T"], cache=tmp_path / ".cache"
    )
    assert len(fichas) == 1
    ficha = fichas[0].read_text(encoding="utf-8")
    assert "Manuel José Cepeda Espinosa" in ficha
    assert "s.d." not in ficha and "Salvamentos" not in ficha  # sin dato -> la línea no se escribe
    assert "ESTADO DE COSAS INCONSTITUCIONAL-Concepto" in ficha
    pdf = fichas[0].parent / "Sentencia-T-025-04.pdf"
    assert pdf.read_bytes().startswith(b"%PDF-")
    assert (tmp_path / "indice.md").exists()

    # Segunda ejecución: no duplica ni vuelve a descargar.
    descargas = len(cliente.pedidas)
    otra = corte_constitucional.buscar(cliente, Biblioteca(tmp_path), ["población desplazada"],
                                       "2004-01-01", "2004-12-31", ["T"], cache=tmp_path / ".cache")
    assert otra == []
    assert len(cliente.pedidas) == descargas + 1  # solo la consulta al dataset
    with (tmp_path / "catalogo.csv").open(encoding="utf-8-sig") as f:
        assert len(list(csv.DictReader(f))) == 1


# ------------------------------------------------------------------ enlaces
def test_flujo_enlaces(tmp_path):
    url_pdf = "https://cortesuprema.gov.co/corte/wp-content/uploads/relatorias/sc123-2021.pdf"
    url_suin = "https://www.suin-juriscol.gov.co/viewDocument.asp?id=30019250"
    original = pdf_valido()
    cliente = ClienteFalso({
        url_pdf: (original, "application/pdf"),
        url_suin: (b"<html><head><title>C-332 de 2014 - SUIN-Juriscol</title></head>"
                   b"<body><p>Texto de la sentencia.</p></body></html>", "text/html"),
    })
    archivo = tmp_path / "enlaces.txt"
    archivo.write_text(
        f"# comentario\n{url_pdf}\nhttps://vlex.com.co/no-oficial\n{url_suin}\n{url_pdf}\n", encoding="utf-8"
    )
    bib = Biblioteca(tmp_path / "bib")
    fichas, rechazados = enlaces_oficiales.importar(cliente, bib, enlaces_oficiales.leer_enlaces(archivo), ["embargo"])
    assert rechazados == ["https://vlex.com.co/no-oficial"]
    assert len(fichas) == 2
    pdfs = list((tmp_path / "bib" / "Corte Suprema de Justicia").rglob("*.pdf"))
    assert pdfs and pdfs[0].read_bytes() == original  # el PDF oficial se guarda sin modificar
    assert any("C-332 de 2014" in f.read_text(encoding="utf-8") for f in fichas)


def test_fichas_sin_marcadores(tmp_path):
    cliente = ClienteFalso({
        corte_constitucional.url_relatoria("T-025/04"): (SENTENCIA_HTML, "text/html"),
        corte_constitucional.url_relatoria("T-100/04"): (OTRA_HTML, "text/html"),
    })
    corte_constitucional.buscar(cliente, Biblioteca(tmp_path), [], "2004-01-01", "2004-12-31", ["T"])
    marcador = re.compile(r"\[(pendiente|completar|xxx|dato|insertar)|TODO|XXX|\{\{|<\s*completar", re.I)
    for ficha in Path(tmp_path).rglob("*.md"):
        assert not marcador.search(ficha.read_text(encoding="utf-8")), ficha
