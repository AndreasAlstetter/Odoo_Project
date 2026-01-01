# processes/manufacturing_flow.py

"""
Fertigungsprozess: MO aus Verkaufsauftrag, Materialentnahme, Fertigmeldung.

Ziele:
- Fertigungsaufträge (mrp.production) aus bestätigten Verkaufsaufträgen
  erzeugen (Make To Order).
- Materialbereitstellung über Reservierung/Transfers (vereinfacht).
- Fertigmeldung mit Ist-Mengen (und ggf. Ausschuss, stark vereinfacht).

Nutzt:
- mrp.production, stock.move, stock.picking
"""

from __future__ import annotations

from typing import List, Dict, Any

from odoo_api import OdooAPI
from core.logging_utils import info, success, warning


class ManufacturingFlow:
    """Kapselt typische Schritte des Fertigungsprozesses."""

    def __init__(self, api: OdooAPI) -> None:
        self.api = api

    def create_mos_from_sales_orders(self, order_ids: List[int]) -> List[int]:
        """
        Erzeugt Fertigungsaufträge (MOs) aus Verkaufsaufträgen.

        Vereinfachung:
        - Liest alle sale.order.line je Auftrag.
        - Erzeugt pro Zeile einen mrp.production mit Produkt und Menge.
        - Nutzt NICHT den kompletten Odoo-MTO-Automatikfluss, sondern
          demonstriert das Prinzip mit explizitem MO-Create.
        """
        info("Erzeuge Fertigungsaufträge aus Verkaufsaufträgen...")

        mo_ids: List[int] = []

        for order_id in order_ids:
            lines = self.api.search_read(
                "sale.order.line",
                [["order_id", "=", order_id]],
                ["id", "product_id", "product_uom_qty"],
                limit=100,
            )

            if not lines:
                warning(f"Keine Auftragszeilen für Auftrag {order_id} gefunden.")
                continue

            for line in lines:
                product_id = line["product_id"][0]
                qty = line["product_uom_qty"]

                vals: Dict[str, Any] = {
                    "product_id": product_id,
                    "product_qty": qty,
                    # Optional: 'origin': sale.order-Name etc.
                }

                mo_id = self.api.create("mrp.production", vals)
                # Rückgabewert absichern
                if isinstance(mo_id, (list, tuple)):
                    if not mo_id:
                        continue
                    mo_id = mo_id[0]
                mo_id = int(mo_id)

                mo_ids.append(mo_id)

        if mo_ids:
            success(f"{len(mo_ids)} Fertigungsaufträge erzeugt.")
        else:
            warning("Keine Fertigungsaufträge erzeugt (prüfe Routen/Produkte).")

        return mo_ids

    def start_mo(self, mo_id: int) -> None:
        """Startet einen Fertigungsauftrag (vereinfacht)."""
        info(f"Starte Fertigungsauftrag {mo_id}...")
        try:
            self.api.call_kw("mrp.production", "action_confirm", [mo_id], {})
            self.api.call_kw("mrp.production", "action_assign", [mo_id], {})
        except Exception:
            # Nicht alle Odoo-Versionen nutzen dieselben Methoden
            warning(f"Start für MO {mo_id} konnte nicht vollständig durchgeführt werden.")

    def finish_mo(self, mo_id: int, qty_done: float | None = None) -> None:
        """
        Meldet einen Fertigungsauftrag als fertig.

        Logik:
        - Wenn qty_done nicht angegeben: geplante Menge (product_qty) verwenden.
        - Versucht zuerst button_mark_done, dann action_finish.
        """
        info(f"Melde Fertigungsauftrag {mo_id} als fertig...")

        mo_data = self.api.read("mrp.production", [mo_id], ["product_qty", "qty_producing"])
        planned = mo_data[0].get("product_qty", 0.0) if mo_data else 0.0

        if qty_done is None:
            qty_done = planned or 0.0

        # In modernen Odoo-Versionen über Workorders; hier vereinfachter Aufruf
        try:
            # Setze qty_producing, falls Feld vorhanden
            self.api.write("mrp.production", mo_id, {"qty_producing": qty_done})
        except Exception:
            pass

        try:
            self.api.call_kw("mrp.production", "button_mark_done", [mo_id], {})
        except Exception:
            try:
                self.api.call_kw("mrp.production", "action_finish", [mo_id], {})
            except Exception:
                warning(f"Fertigmeldung für MO {mo_id} konnte nicht automatisch durchgeführt werden.")

        success(f"MO {mo_id} wurde (ggf. vereinfacht) fertiggemeldet.")

    def run_demo_mo_chain(self, order_ids: List[int]) -> List[int]:
        """
        Führt die Demo-Kette „Auftrag → MO → Materialbereitstellung → Fertigmeldung“ aus.

        Rückgabe:
        - Liste der verarbeiteten MO-IDs.
        """
        info("Starte Demo: Auftragskette inkl. Fertigung...")

        mo_ids = self.create_mos_from_sales_orders(order_ids)

        for mo in mo_ids:
            self.start_mo(mo)
            self.finish_mo(mo)

        if mo_ids:
            success(f"{len(mo_ids)} Fertigungsaufträge durchlaufen die Demo-Kette.")
        else:
            warning("Keine MOs für die Demo-Kette verfügbar.")

        return mo_ids
