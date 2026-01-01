"""
Integrations-Paket für das Odoo-Drohnen-Projekt.

Dieses Paket bündelt alle Module, die die Anbindung an den
Universal Manufacturing Hub (UMH) simulieren bzw. vorbereiten:

- Definition von UMH-Events (Bestand, Fertigung, Qualität, Versand)
- Dateibasierter UMH-Client-Simulator (statt echter MQTT/HTTP-Anbindung)
- Mapping von Odoo-Stammdaten in ein UMH-Masterdata-Format
- Export von Produkten, BoMs und Routing als UMH-Masterdata-JSON

Die Module werden sowohl aus den Import-Skripten (z. B. Lagerimport)
als auch aus End-to-End-Demos genutzt.
"""

from .umh_events import EventType, UMHEvent, UMHEventManager
from .umh_client_sim import UMHClientSimulator
from .umh_mapping import UMHMapper
from .umh_export_masterdata import export_masterdata

__all__ = [
    "EventType",
    "UMHEvent",
    "UMHEventManager",
    "UMHClientSimulator",
    "UMHMapper",
    "export_masterdata",
]
