# processes/shipping_flow.py

"""
Versandprozess: Lieferung aus Verkaufsaufträgen.

Ziele:
- Lieferungen (stock.picking, outgoing) aus Verkaufsaufträgen finden.
- Warenausgang buchen (vereinfacht, ohne detaillierte Kommissionierlogik).

Nutzt:
- sale.order
- stock.picking (outgoing)
"""

from __future__ import annotations

from typing import List, Dict, Any

from odoo_api import OdooAPI
from core.logging_utils import info, success, warning


class ShippingFlow:
    """Kapselt typische Schritte des Versandprozesses."""

    def __init__(self, api: OdooAPI) -> None:
        self.api = api

    def _get_order_name(self, order_id: int) -> str | None:
        """Holt den 'name' eines sale.order (z. B. SO00010)."""
        data = self.api.read("sale.order", [order_id], ["name"])
        if not data:
            return None
        return data[0].get("name")

    def _find_outgoing_pickings(self, order_id: int) -> List[Dict[str, Any]]:
        """
        Sucht Warenausgangs-Pickings (Lieferungen) zu einem Verkaufsauftrag.
        """
        so_name = self._get_order_name(order_id)
        if not so_name:
            warning(f"Name für Verkaufsauftrag {order_id} nicht gefunden.")
            return []

        pickings = self.api.search_read(
            "stock.picking",
            [
                ["origin", "=", so_name],
                ["picking_type_id.code", "=", "outgoing"],
            ],
            ["id", "state", "picking_type_id"],
            limit=20,
        )
        return pickings

    def ship_order(self, order_id: int) -> None:
        """
        Bucht die Lieferungen (Warenausgang) zu einem Verkaufsauftrag.
        """
        info(f"Buche Lieferungen für Verkaufsauftrag {order_id}...")

        pickings = self._find_outgoing_pickings(order_id)
        if not pickings:
            warning(f"Keine Lieferungen für Verkaufsauftrag {order_id} gefunden.")
            return

        for picking in pickings:
            picking_id = picking["id"]
            try:
                self.api.call_kw(
                    "stock.picking",
                    "button_validate",
                    [[picking_id]],
                    {},
                )
                success(f"Lieferung {picking_id} für Auftrag {order_id} gebucht.")
            except Exception:
                warning(
                    f"Lieferung {picking_id} für Auftrag {order_id} "
                    f"konnte nicht gebucht werden."
                )

    def run_demo_shipping(self, order_ids: List[int]) -> List[int]:
        """
        Führt eine Versand-Demo für eine Liste von Verkaufsaufträgen aus.

        Rückgabe:
        - Liste der Auftrags-IDs, für die Lieferungen gebucht wurden (oder versucht wurden).
        """
        info("Starte Demo: Warenausgang / Versand...")

        processed: List[int] = []
        for oid in order_ids:
            self.ship_order(oid)
            processed.append(oid)

        if not processed:
            warning("Keine Aufträge für die Versand-Demo vorhanden.")
        else:
            success(f"{len(processed)} Aufträge in der Versand-Demo verarbeitet.")

        return processed
