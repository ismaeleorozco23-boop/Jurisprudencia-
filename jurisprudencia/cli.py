"""Interfaz de línea de comandos."""

from __future__ import annotations

import argparse
import logging
import os
import sys
from datetime import date
from pathlib import Path

from . import corte_constitucional, enlaces_oficiales
from .biblioteca import Biblioteca
from .red import Cliente, NavegadorNoDisponible


def carpeta_por_defecto() -> Path:
    """OneDrive de trabajo o escuela si existe (lo indexa Microsoft 365 Copilot)."""
    if os.environ.get("JURIS_SALIDA"):
        return Path(os.environ["JURIS_SALIDA"])
    for variable in ("OneDriveCommercial", "OneDrive"):
        if os.environ.get(variable):
            return Path(os.environ[variable]) / "Jurisprudencia Colombia"
    return Path("biblioteca")


def _fecha(valor: str) -> str:
    try:
        return date.fromisoformat(valor).isoformat()
    except ValueError as error:
        raise argparse.ArgumentTypeError(f"Fecha inválida {valor!r}; use AAAA-MM-DD") from error


def construir_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(
        prog="buscar_jurisprudencia",
        description="Biblioteca de jurisprudencia colombiana desde fuentes oficiales.",
    )
    p.add_argument("--salida", type=Path, default=None, help="Carpeta de la biblioteca (por defecto, OneDrive).")
    p.add_argument("-v", "--detalle", action="store_true", help="Mostrar más mensajes.")
    sub = p.add_subparsers(dest="comando", required=True)

    cc = sub.add_parser("constitucional", help="Búsqueda automática por tema en la Corte Constitucional.")
    cc.add_argument("--tema", action="append", required=True, help="Palabra o frase. Repetible.")
    cc.add_argument("--modo", choices=("todas", "alguna"), default="todas",
                    help="'todas': deben aparecer todos los temas; 'alguna': basta uno.")
    cc.add_argument("--desde", type=_fecha, default="1992-01-01")
    cc.add_argument("--hasta", type=_fecha, default=date.today().isoformat())
    cc.add_argument("--tipo", action="append", choices=sorted(corte_constitucional.TIPOS_VALIDOS),
                    help="T, C o SU. Repetible. Por defecto, todos.")
    cc.add_argument("--max", type=int, default=20, help="Máximo de sentencias a guardar.")
    cc.add_argument("--max-revisar", type=int, default=300,
                    help="Máximo de sentencias a descargar y revisar en esta ejecución.")

    en = sub.add_parser("enlaces", help="Importar enlaces oficiales (Corte Suprema, SUIN-Juriscol).")
    en.add_argument("--archivo", type=Path, default=Path("enlaces.txt"))
    en.add_argument("--tema", action="append", default=[], help="Términos para extraer fragmentos.")
    return p


def main(argv: list[str] | None = None) -> int:
    args = construir_parser().parse_args(argv)
    cliente = Cliente()
    try:
        return _ejecutar(args, cliente)
    except NavegadorNoDisponible as error:
        print(f"\n{error}", file=sys.stderr)
        return 3
    except KeyboardInterrupt:
        print("\nInterrumpido. Lo ya guardado queda en la biblioteca.", file=sys.stderr)
        return 130
    finally:
        cliente.cerrar()


def _ejecutar(args: argparse.Namespace, cliente: Cliente) -> int:
    logging.basicConfig(
        level=logging.DEBUG if args.detalle else logging.INFO,
        format="%(levelname)s  %(message)s",
    )
    salida = args.salida or carpeta_por_defecto()
    biblioteca = Biblioteca(salida)
    print(f"Biblioteca: {salida.resolve()}")

    if args.comando == "constitucional":
        if args.desde > args.hasta:
            print("Error: --desde es posterior a --hasta.", file=sys.stderr)
            return 2
        fichas = corte_constitucional.buscar(
            cliente, biblioteca, args.tema, args.desde, args.hasta, args.tipo or [],
            modo=args.modo, maximo=args.max, max_revisar=args.max_revisar,
            cache=salida / ".cache",
        )
        print(f"Listo: {len(fichas)} sentencias nuevas guardadas.")
        return 0

    if not args.archivo.exists():
        print(f"Error: no existe el archivo {args.archivo}", file=sys.stderr)
        return 2
    enlaces = enlaces_oficiales.leer_enlaces(args.archivo)
    fichas, rechazados = enlaces_oficiales.importar(cliente, biblioteca, enlaces, args.tema)
    print(f"Listo: {len(fichas)} documentos guardados; {len(rechazados)} rechazados o fallidos.")
    for url in rechazados:
        print(f"  - {url}")
    return 1 if rechazados and not fichas else 0
