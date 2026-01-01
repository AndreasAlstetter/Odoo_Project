# core/__init__.py
"""
Zentrale Infrastruktur für das Odoo-Drohnen-Projekt.

Dieses Paket stellt grundlegende **Hilfsfunktionen** und **Basiskomponenten**
bereit, die in allen anderen Modulen wiederverwendet werden sollen:

- Logging- und Ausgabe-Hilfen für eine einheitliche CLI-Ausgabe
- Validierungsfunktionen für CSV- und Stammdaten
- Zentrale Fehlerklassen für konsistentes Fehlermanagement

Module in ``importers``, ``processes`` und ``integration`` sollten diese
Komponenten nutzen, um:

- ein konsistentes Logging (Info/Success/Warning/Error/Debug) sicherzustellen
- Eingabedaten robust zu prüfen, bevor Odoo-Operationen ausgeführt werden
"""

from .logging_utils import console, info, success, warning, error, debug
from .validation import (
    CSVValidationError,
    validate_required_columns,
    validate_non_empty,
    safe_float,
    safe_int,
)

__all__ = [
    "console",
    "info",
    "success",
    "warning",
    "error",
    "debug",
    "CSVValidationError",
    "validate_required_columns",
    "validate_non_empty",
    "safe_float",
    "safe_int",
]
