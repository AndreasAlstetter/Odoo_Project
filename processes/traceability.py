# processes/traceability.py

"""
Traceability (Serien-/Chargennummern, einfache Verwendungsnachverfolgung).

Ziele:
- Seriennummer einem Produkt zuordnen (lot/serial).
- Seriennummer optional einer Charge (Batch) zuordnen.
- Nutzung einer Seriennummer in einem Fertigungsauftrag festhalten.
- Traceability-Kette für ein Endprodukt nachvollziehen:
  BOM-Komponenten → MOs → Lieferungen.
"""

from __future__ import annotations

from typing import Dict, List, Optional

from odoo_api import OdooAPI
from core.logging_utils import info, warning


class TraceabilityManager:
    """Verwaltet einfache Serial-/Batch-Traceability auf Odoo-Basis."""

    def __init__(self, api: OdooAPI) -> None:
        self.api = api

    def assign_serial_number(self, product_id: int, serial: str) -> int | None:
        """
        Legt eine Seriennummer (stock.lot) für ein Produkt an, falls noch nicht vorhanden.

        Returns
        -------
        int | None
            ID des stock.lot oder None bei Fehler.
        """
        serial = (serial or "").strip()
        if not serial:
            warning("Leere Seriennummer; keine Aktion.")
            return None

        existing = self.api.search_read(
            "stock.lot",
            [["name", "=", serial], ["product_id", "=", product_id]],
            ["id"],
            limit=1,
        )
        if existing:
            lot_id = existing[0]["id"]
            info(f"Seriennummer '{serial}' für Produkt {product_id} existiert bereits (Lot {lot_id}).")
            return lot_id

        vals = {
            "name": serial,
            "product_id": product_id,
        }
        lot_id = self.api.create("stock.lot", vals)
        if isinstance(lot_id, (list, tuple)):
            if not lot_id:
                warning("stock.lot konnte nicht angelegt werden.")
                return None
            lot_id = lot_id[0]
        lot_id = int(lot_id)
        info(f"Seriennummer '{serial}' für Produkt {product_id} angelegt (Lot {lot_id}).")
        return lot_id

    def link_to_batch(self, serial_number: str, batch_id: str) -> bool:
        """
        Verknüpft eine Seriennummer mit einer Batch-ID.

        Vereinfachung:
        - Batch-ID wird in einem benutzerdefinierten Feld 'x_batch_id'
          auf stock.lot gespeichert (falls vorhanden).
        """
        serial_number = (serial_number or "").strip()
        if not serial_number:
            warning("Leere Seriennummer; keine Batch-Verknüpfung möglich.")
            return False

        lots = self.api.search_read(
            "stock.lot",
            [["name", "=", serial_number]],
            ["id"],
            limit=1,
        )
        if not lots:
            warning(f"Seriennummer '{serial_number}' nicht gefunden.")
            return False

        lot_id = lots[0]["id"]
        try:
            self.api.write("stock.lot", lot_id, {"x_batch_id": batch_id})
            info(f"Seriennummer '{serial_number}' mit Batch '{batch_id}' verknüpft.")
            return True
        except Exception:
            warning(
                "Batch-Verknüpfung konnte nicht gespeichert werden. "
                "Benutzerdefiniertes Feld 'x_batch_id' prüfen."
            )
            return False

    def track_component_usage(self, mo_id: int, component_id: int, serial_number: str) -> bool:
        """
        Markiert, dass eine bestimmte Seriennummer einer Komponente in einem MO verwendet wurde.

        Vereinfachung:
        - Hinterlegt MO-Referenz im Lot-Feld 'x_used_in_mo' (Text- oder Many2many-Feld).
        """
        serial_number = (serial_number or "").strip()
        if not serial_number:
            warning("Leere Seriennummer; keine Verwendungsnachverfolgung möglich.")
            return False

        lots = self.api.search_read(
            "stock.lot",
            [
                ["name", "=", serial_number],
                ["product_id", "=", component_id],
            ],
            ["id"],
            limit=1,
        )
        if not lots:
            warning(
                f"Seriennummer '{serial_number}' für Komponente {component_id} nicht gefunden."
            )
            return False

        lot_id = lots[0]["id"]
        try:
            self.api.write("stock.lot", lot_id, {"x_used_in_mo": str(mo_id)})
            info(f"Seriennummer '{serial_number}' als in MO {mo_id} verwendet markiert.")
            return True
        except Exception:
            warning(
                "Verwendungsmarkierung konnte nicht gespeichert werden. "
                "Benutzerdefiniertes Feld 'x_used_in_mo' prüfen."
            )
            return False

    def get_traceability_chain(self, product_id: int) -> Dict:
        """
        Liefert eine einfache Traceability-Kette für ein Produkt.

        Vorgehen (vereinfachte Demo):
        - Sucht Fertigungsaufträge mit diesem Produkt als Endprodukt.
        - Sucht zugehörige Lieferscheine (stock.picking, outgoing) über origin.
        - Gibt strukturierte IDs zurück, die in Reports/KPIs weiterverwendet
          werden können.

        Returns
        -------
        dict
            Struktur:
            {
                "product_id": int,
                "mos": [mo_id, ...],
                "deliveries": [picking_id, ...],
            }
        """
        mos = self.api.search_read(
            "mrp.production",
            [["product_id", "=", product_id]],
            ["id", "name"],
            limit=50,
        )
        mo_ids = [m["id"] for m in mos]

        delivery_ids: List[int] = []
        for mo in mos:
            origin = mo.get("name")
            if not origin:
                continue
            pickings = self.api.search_read(
                "stock.picking",
                [
                    ["origin", "=", origin],
                    ["picking_type_id.code", "=", "outgoing"],
                ],
                ["id"],
                limit=20,
            )
            delivery_ids.extend(p["id"] for p in pickings)

        chain = {
            "product_id": product_id,
            "mos": mo_ids,
            "deliveries": delivery_ids,
        }
        info(
            f"Traceability-Kette für Produkt {product_id}: "
            f"{len(mo_ids)} MOs, {len(delivery_ids)} Lieferungen."
        )
        return chain
