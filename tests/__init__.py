# tests/__init__.py
"""
Test-Paket für das Odoo-Drohnen-Projekt.

Dieses Paket bündelt verschiedene Test-Skripte und -Module, mit denen
die wichtigsten Bausteine des Projekts überprüft werden können:

- Datenvalidierung (CSV-Strukturen, Pflichtfelder, Referenzen)
- UMH-Events und UMH-Client-Simulation
- End-to-End-Demo (Stammdatenimporte, Prozesse, UMH-Export)

Die Tests können klassisch über `pytest`/`unittest` oder manuell
als Demo-Skripte ausgeführt werden.
"""

from .test_data_validation import TestDataValidation
from .test_umh_events import TestUMHEvents
# test_end_to_end wird bewusst als Skript genutzt und nicht in __all__ exportiert.

__all__ = [
    "TestDataValidation",
    "TestUMHEvents",
]
