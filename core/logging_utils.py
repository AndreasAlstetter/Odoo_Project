# core/logging_utils.py
"""
Logging- und Ausgabe-Hilfen für das Odoo-Drohnen-Projekt.

Die Funktionen in diesem Modul kapseln die Ausgabe über Typer und sorgen
für eine einheitliche, gut lesbare CLI-Ausgabe. Gleichzeitig dienen
die Meldungen als Dokumentation der Prozessschritte.
"""

from typing import Any, Optional

import typer

# Zentrale Konsole für strukturierte Ausgaben
console = typer.echo


def _format_prefix(level: str) -> str:
    """Interner Helper zur einheitlichen Präfix-Erzeugung."""
    return f"[{level}]".ljust(8)


def info(message: str, *, nl: bool = True) -> None:
    """
    Informative Standardmeldung ausgeben.

    Wird für normale Prozessschritte genutzt (z. B. "Importiere Produkte...").
    """
    typer.secho(f"{_format_prefix('INFO')} {message}", fg=typer.colors.BLUE, nl=nl)


def success(message: str, *, nl: bool = True) -> None:
    """
    Erfolgsmeldung ausgeben.

    Wird genutzt, wenn ein logischer Schritt erfolgreich abgeschlossen wurde
    (z. B. "15 Produkte importiert").
    """
    typer.secho(f"{_format_prefix('OK')} {message}", fg=typer.colors.GREEN, bold=True, nl=nl)


def warning(message: str, *, nl: bool = True) -> None:
    """
    Warnung ausgeben.

    Für nicht-kritische Probleme, die nicht zum Abbruch führen, aber
    dokumentiert werden sollen (z. B. "3 Zeilen mit ungültiger Menge übersprungen").
    """
    typer.secho(f"{_format_prefix('WARN')} {message}", fg=typer.colors.YELLOW, nl=nl)


def error(message: str, *, nl: bool = True) -> None:
    """
    Fehlermeldung ausgeben.

    Für kritische Fehler, die i. d. R. zu einem Abbruch des aktuellen
    Kommandos führen.
    """
    typer.secho(f"{_format_prefix('ERROR')} {message}", fg=typer.colors.RED, bold=True, nl=nl)


def debug(message: str, data: Optional[Any] = None, *, enabled: bool = False) -> None:
    """
    Debug-Ausgabe (optional).

    Parameter:
    - message: Kurze Beschreibung.
    - data: Optionale Zusatzinformationen (z. B. dict, Liste).
    - enabled: Wenn False, wird nichts ausgegeben (globales Debug-Flag an z. B.
      CLI-Option binden).

    Diese Funktion erlaubt das gezielte Aktivieren von Detailausgaben ohne
    den Code zu verändern.
    """
    if not enabled:
        return

    text = f"{_format_prefix('DEBUG')} {message}"
    if data is not None:
        text += f" | {repr(data)}"
    typer.secho(text, fg=typer.colors.MAGENTA)
