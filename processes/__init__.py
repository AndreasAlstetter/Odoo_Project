# processes/__init__.py

"""
Geschäftsprozess-Paket für das Odoo-Drohnen-Projekt.

Dieses Paket enthält High-Level-Skripte, die komplette End-to-End-Flows
in Odoo und im UMH-Digital-Twin durchspielen:

- Verkauf (Angebot → Auftrag → Lieferung → Rechnung)
- Einkauf (Anfrage/RFQ → Bestellung → Wareneingang)
- Fertigung (MO aus Verkaufsauftrag, Materialentnahme, Fertigmeldung)
- Lagerprozesse (Bestände, Inventur, Ausschuss)
- Versand (Lieferung, Tracking)
- Traceability und einfache KPI-Auswertung

Die Flows sind so gestaltet, dass sie sowohl über die Typer-CLI als auch
aus Tests heraus in isolierten Szenarien ausgeführt werden können.
"""

from .inventory_flow import InventoryFlow
from .sales_flow import SalesFlow
from .purchase_flow import PurchaseFlow
from .manufacturing_flow import ManufacturingFlow
from .production_flow import ProductionFlow
from .production_routing import get_routing
from .shipping_flow import ShippingFlow
from .traceability import TraceabilityManager
from .kpi_extractor import KPIExtractor

__all__ = [
    "InventoryFlow",
    "SalesFlow",
    "PurchaseFlow",
    "ManufacturingFlow",
    "ProductionFlow",
    "get_routing",
    "ShippingFlow",
    "TraceabilityManager",
    "KPIExtractor",
]
