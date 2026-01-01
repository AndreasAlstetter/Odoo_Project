# processes/inventory_flow.py

"""
Inventur & Ausschuss (vereinfacht).

Ziele:
- Einen Inventurfall für zentrale Komponenten simulieren.
- Ausschuss über ein Schrottlager buchen.

Nutzt:
- stock.location (Schrottlager)
- stock.scrap (vereinfachte Ausschussbuchung)
"""

from __future__ import annotations

from typing import Dict

from odoo_api import OdooAPI
from core.logging_utils import info, success, warning
from core.validation import safe_float


class InventoryFlow:
    """Kapselt vereinfachte Inventur- und Ausschussprozesse."""

    def __init__(self, api: OdooAPI) -> None:
        self.api = api

    def _get_or_create_scrap_location(self) -> int:
        """
        Stellt ein Schrottlager (stock.location, usage='inventory') bereit.

        Es wird zuerst nach einem bestehenden Lager mit Name 'Scrap'
        und usage='inventory' gesucht; falls keines existiert, wird
        ein neues angelegt.
        """
        existing = self.api.search_read(
            "stock.location",
            [["usage", "=", "inventory"], ["name", "=", "Scrap"]],
            ["id"],
            limit=1,
        )
        if existing:
            return existing[0]["id"]

        vals: Dict[str, object] = {
            "name": "Scrap",
            "usage": "inventory",
        }
        loc_id = self.api.create("stock.location", vals)
        if isinstance(loc_id, (list, tuple)):
            loc_id = loc_id[0]
        return int(loc_id)

    def run_demo_inventory_case(self) -> None:
        """
        Simuliert eine Inventur für eine Komponente.

        Vereinfachung:
        - Es wird kein echtes stock.inventory-Objekt angelegt, sondern
          nur der Ablauf auf Log-Ebene dokumentiert.
        """
        info("Demo-Inventurfall (vereinfachte Darstellung) wird ausgeführt...")
        # Hier könnte echtes stock.inventory angelegt werden; für jetzt nur Logik-Skizze.
        success("Demo-Inventurfall dokumentiert (Details in produktiver Umgebung zu ergänzen).")

    def scrap_product(self, product_name: str, quantity: float) -> None:
        """
        Bucht Ausschuss für ein Produkt in das Schrottlager.

        Logik:
        - Sucht das angegebene Produkt über seinen Namen.
        - Legt einen Scrap-Datensatz (stock.scrap) an.
        - Versucht, die Buchung über action_validate zu bestätigen.
        """
        info(f"Buche Ausschuss: Produkt '{product_name}', Menge {quantity}...")

        prod = self.api.search_read(
            "product.product",
            [["name", "=", product_name]],
            ["id"],
            limit=1,
        )

        if not prod:
            # Produkt on-the-fly anlegen (vereinfachter Demo-Fall)
            prod_id = self.api.create(
                "product.product",
                {
                    "name": product_name,
                    "default_code": "SCRAP-DEMO",
                    "type": "consu",  # gültiger Wert für dein Odoo
                },
            )
            if isinstance(prod_id, (list, tuple)):
                prod_id = prod_id[0]
            prod_id = int(prod_id)
            info(f"Demo-Produkt '{product_name}' für Ausschuss angelegt (ID {prod_id}).")
        else:
            prod_id = prod[0]["id"]

        qty = safe_float(quantity, default=0.0, allow_negative=False)
        if qty <= 0.0:
            warning("Ausschussmenge ist 0 oder ungültig; keine Buchung durchgeführt.")
            return

        scrap_loc = self._get_or_create_scrap_location()

        vals = {
            "product_id": prod_id,
            "scrap_qty": qty,
            "scrap_location_id": scrap_loc,
        }

        try:
            scrap_id = self.api.create("stock.scrap", vals)
            if isinstance(scrap_id, (list, tuple)):
                scrap_id = scrap_id[0]
            scrap_id = int(scrap_id)

            # In neueren Odoo-Versionen: Aktion zur Buchung aufrufen
            self.api.call_kw("stock.scrap", "action_validate", [scrap_id], {})
            success(f"Ausschuss für '{product_name}' (Menge {qty}) gebucht.")
        except Exception:
            warning(
                "Ausschuss konnte nicht vollständig automatisch gebucht werden. "
                "Bitte Odoo-Version und stock.scrap-Konfiguration prüfen."
            )

    def run_demo_inventory_and_scrap(self) -> None:
        """Führt eine kombinierte Demo für Inventur und Ausschuss aus."""
        self.run_demo_inventory_case()
        # Beispiel: 1 Stück des Demo-Produkts als Ausschuss
        self.scrap_product("Akku", 1.0)
