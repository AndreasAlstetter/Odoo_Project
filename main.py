# main.py
"""
Einstiegspunkt für das Odoo-Drohnen-Projekt.

Dieses Modul startet die Typer-CLI aus `cli.py` und stellt damit den
zentralen Kommandozeilen-Einstieg bereit.

Beispiele:

- python main.py check-connection
- python main.py stammdaten import-bom-varianten --variant spartan
- python main.py setup-all --variant lightweight
- python main.py prozesse demo-endtoend
"""

from cli import app


def main() -> None:
    """
    Startet die Typer-App.

    Diese Funktion dient als klarer Einstiegspunkt und kann bei Bedarf
    auch von Tests direkt aufgerufen werden.
    """
    app()


if __name__ == "__main__":
    main()
