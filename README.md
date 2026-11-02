# Jurisprudencia Colombia para Microsoft 365 Copilot

Programa en Python que arma una biblioteca de jurisprudencia colombiana descargada **solo de fuentes oficiales** y la guarda en OneDrive, para que Microsoft 365 Copilot pueda consultarla.

Por cada providencia genera:

- **Un PDF con el texto completo.** Si la fuente publica un PDF oficial, se guarda sin modificar. Si la publica en HTML, el PDF se genera a partir de ese texto oficial y en la primera línea indica la URL de origen y la fecha de consulta.
- **Una ficha en Markdown (`.md`).** Contiene corporación, fecha, magistrado ponente, sala, expediente, los temas asignados por la Relatoría y los fragmentos literales donde aparecen los términos buscados.
- **Un índice general (`indice.md`) y un catálogo (`catalogo.csv`).** El catálogo permite abrir la biblioteca en Excel y evita descargas duplicadas.

## Regla de fuentes (no negociable)

El archivo `jurisprudencia/fuentes.py` contiene una lista cerrada de dominios oficiales. Cualquier enlace de otro dominio se rechaza antes de descargarse. Lo mismo ocurre si un enlace oficial redirige a un sitio no oficial.

| Dominio | Entidad | Uso |
|---|---|---|
| `corteconstitucional.gov.co` | Corte Constitucional | Texto completo de las sentencias |
| `cortesuprema.gov.co` | Corte Suprema de Justicia | Providencias |
| `ramajudicial.gov.co` | Rama Judicial | Consulta de jurisprudencia |
| `suin-juriscol.gov.co` | Ministerio de Justicia y del Derecho | SUIN-Juriscol |
| `datos.gov.co` | Portal Nacional de Datos Abiertos | Solo la lista oficial de sentencias que publica la Corte Constitucional; nunca como fuente de providencias |

Las páginas que vienen de otros sitios (vLex, blogs, Google Drive, sitios de otros países) se rechazan siempre.

> El Senado de la República publica **leyes**, no jurisprudencia. Si más adelante quiere enlazar el texto de las leyes citadas, se agrega una línea con `secretariasenado.gov.co` en `fuentes.py`.

## Qué es automático y qué no

| Corporación | Modo | Motivo |
|---|---|---|
| Corte Constitucional | **Automático por tema** | La Corte publica en datos.gov.co la lista oficial de sus sentencias (dataset `v2k4-2t8s`, desde 1992, actualización mensual), y cada texto tiene una dirección fija en la Relatoría. |
| Corte Suprema de Justicia | **Semiautomático** | Su buscador oficial no ofrece una API estable. Usted busca allí y pega los enlaces en `enlaces.txt`. |
| SUIN-Juriscol | **Semiautomático** | Mismo motivo. Los documentos tienen enlace fijo (`viewDocument.asp?id=...`). |

## Instalación en Windows (una sola vez)

1. Instale Python 3.10 o superior desde https://www.python.org/downloads/ y marque la casilla **"Add Python to PATH"**.
2. Descargue este repositorio. En GitHub, botón verde **Code → Download ZIP**, y descomprímalo.
3. Abra la carpeta descomprimida, escriba `cmd` en la barra de direcciones del Explorador y presione Enter.
4. Ejecute:

```
py -m venv .venv
.venv\Scripts\activate
pip install -r requirements.txt
python -m playwright install chromium
```

Desde ese momento, cada vez que vaya a usar el programa abra `cmd` en la carpeta y ejecute primero `.venv\Scripts\activate`.

## Uso

### Corte Constitucional (automático)

```
python buscar_jurisprudencia.py constitucional --tema "embargo" --tema "salario mínimo" --desde 2015-01-01 --tipo T --tipo SU --max 15
```

| Opción | Qué hace |
|---|---|
| `--tema` | Palabra o frase a buscar en el texto completo. Se puede repetir. No distingue tildes ni mayúsculas. |
| `--modo todas` / `--modo alguna` | `todas` (por defecto): la sentencia debe contener todos los temas. `alguna`: basta con uno. |
| `--desde`, `--hasta` | Rango de fechas de la sentencia, en formato AAAA-MM-DD. |
| `--tipo` | `T` (tutela), `C` (constitucionalidad), `SU` (unificación). Se puede repetir. Por defecto, todos. |
| `--max` | Cuántas sentencias nuevas guardar como máximo (por defecto 20). |
| `--max-revisar` | Cuántas sentencias descargar y leer como máximo en esta ejecución (por defecto 300). Las más recientes se revisan primero. |

**Cómo busca.** Toma la lista oficial de sentencias del rango y tipo indicados, de la más reciente a la más antigua, descarga el texto de cada una desde la Relatoría y guarda solo las que contienen los términos. Deja una pausa de 1 segundo entre descargas para no sobrecargar el servidor de la Corte. Los textos ya revisados quedan en caché (`.cache`), así que una segunda búsqueda en el mismo rango es mucho más rápida.

> Consejo: use rangos de fechas acotados. Revisar 300 sentencias puede tardar entre 5 y 15 minutos, según si el sitio exige el navegador automatizado.

### Corte Suprema de Justicia y SUIN-Juriscol (semiautomático)

1. Busque en el buscador oficial:
   - Corte Suprema: https://consultajurisprudencial.ramajudicial.gov.co/WebRelatoria/csj/index.xhtml
   - SUIN-Juriscol: https://www.suin-juriscol.gov.co/
2. Copie el enlace de cada providencia y péguelo en un archivo `enlaces.txt` en la carpeta del programa, uno por línea. Las líneas que empiezan con `#` se ignoran.
3. Ejecute:

```
python buscar_jurisprudencia.py enlaces --archivo enlaces.txt --tema "embargo"
```

El programa informa cuáles enlaces rechazó por no ser oficiales o porque no pudo descargarlos.

## Dónde queda la biblioteca y cómo usarla en Copilot

Sin la opción `--salida`, el programa guarda todo en **OneDrive (cuenta laboral o institucional) → `Jurisprudencia Colombia`**. Usa la variable de Windows `OneDriveCommercial` y, si no existe, `OneDrive`.

```
Jurisprudencia Colombia/
├── indice.md
├── catalogo.csv
├── Corte Constitucional/
│   └── 2004/
│       ├── Sentencia-T-025-04.pdf
│       └── Sentencia-T-025-04 - ficha.md
├── Corte Suprema de Justicia/
├── Rama Judicial/
└── SUIN-Juriscol/
```

Para usarla en **Microsoft 365 Copilot**:

1. Necesita una cuenta de Microsoft 365 laboral o institucional con licencia de Copilot. Copilot solo consulta archivos de OneDrive o SharePoint de esa cuenta.
2. Deje que OneDrive termine de sincronizar (ícono de nube con visto verde).
3. En Copilot Chat escriba `/` y elija el archivo o la carpeta, o pregunte directamente, por ejemplo: *"Según las sentencias de mi carpeta Jurisprudencia Colombia, ¿qué ha dicho la Corte sobre el embargo del salario mínimo?"*. Copilot cita el archivo del que toma cada dato.
4. Los archivos nuevos pueden tardar algunas horas en quedar indexados.

**Limitación honesta.** Copilot lee los PDF sin problema. No tengo certeza de que indexe los `.md` con la misma calidad que los `.docx` en todos los planes. Si nota que Copilot no encuentra las fichas, avíseme y cambio el formato de la ficha a Word.

## Limitaciones conocidas

- **Los sitios oficiales cambian.** Si la Corte rediseña su página, la extracción del texto puede requerir ajustes. El programa valida que el texto descargado sea efectivamente la sentencia (que contenga su número y una extensión mínima) y descarta el resto en lugar de guardar páginas vacías.
- **Temas de la Relatoría.** Se extraen de los descriptores que la Relatoría pone al inicio de cada sentencia. Si no se detectan con seguridad, la ficha omite esa sección.
- **La ficha no es un resumen.** Contiene datos oficiales y fragmentos literales, no interpretaciones. El análisis lo puede pedir a Copilot sobre el texto completo, verificando siempre contra el original.
- **PDF escaneados.** Si una corporación publica un PDF escaneado sin texto, se guarda igual, pero los fragmentos de búsqueda quedan vacíos.

## Para desarrolladores

```
pip install pytest
python -m pytest -q
```

```
jurisprudencia/
├── fuentes.py              # lista cerrada de dominios oficiales
├── red.py                  # descargas con reintentos, pausa y validación de dominio; navegador opcional
├── texto.py                # extracción de texto, búsqueda sin tildes, fragmentos, temas de Relatoría
├── corte_constitucional.py # búsqueda automática (datos.gov.co + Relatoría)
├── enlaces_oficiales.py    # importación desde enlaces.txt
├── biblioteca.py           # PDF, ficha Markdown, índice y catálogo
└── cli.py                  # comandos
```

## Guía rápida de GitHub y Claude Code

**Conceptos:**

- **Repositorio.** La carpeta del proyecto en GitHub, con todo su historial. Este es `Jurisprudencia-`.
- **Rama (branch).** Una copia paralela donde se trabaja sin tocar la versión principal (`main`). Claude Code trabajó en la rama `claude/awesome-noether-l5hjqi`.
- **Commit.** Una "foto" de los cambios, con un mensaje que dice qué se hizo.
- **Push.** Subir los commits de su computador o de Claude Code a GitHub.
- **Pull request (PR).** La solicitud para unir una rama a `main`. Allí se revisan los cambios antes de aceptarlos.

**Flujo recomendado con Claude Code:**

1. Pida el cambio en lenguaje natural, por ejemplo: *"Agrega el Consejo de Estado como fuente"*.
2. Claude Code modifica el código, ejecuta las pruebas, hace commit y push a su rama de trabajo.
3. En GitHub aparece un aviso amarillo **"Compare & pull request"** sobre esa rama. Ábralo, revise la pestaña **Files changed** y, si está conforme, presione **Merge pull request**. También puede pedirle a Claude Code que cree el PR.
4. Después del merge, la versión en `main` es la oficial. Descárguela de nuevo (Code → Download ZIP) o, si instaló Git, ejecute `git pull`.

**Buenas prácticas:**

- Un cambio por pedido. Es más fácil de revisar y de revertir.
- No suba la biblioteca descargada al repositorio. El `.gitignore` ya lo impide. El repositorio es para el código y la biblioteca vive en OneDrive.
- Si algo falla, copie el mensaje de error completo y péguelo en Claude Code.
