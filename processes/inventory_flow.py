# processes/inventory_flow.py

"""
Inventur & Ausschuss (Demo).

Ziele:
- Einen Inventurfall für eine zentrale Komponente simulieren.
- Ausschuss über ein Schrottlager buchen.

Nutzt:
- stock.location (Schrottlager)
- stock.inventory (Inventur)
- stock.scrap (vereinfachte Ausschussbuchung)
"""

from __future__ import annotations

from typing import Dict
from datetime import datetime

from odoo_api import OdooAPI
from core.logging_utils import info, success, warning
from core.validation import safe_float


class InventoryFlow:
    """Kapselt vereinfachte Inventur- und Ausschussprozesse."""

    def __init__(self, api: OdooAPI) -> None:
        self.api = api

    # -------------------------------------------------------------------------
    # Hilfsfunktionen
    # -------------------------------------------------------------------------

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

    def _ensure_demo_product_akku(self) -> int:
        """
        Sucht das Produkt 'Akku' oder legt es vereinfacht an.
        """
        prod = self.api.search_read(
            "product.product",
            [["name", "=", "Akku"]],
            ["id"],
            limit=1,
        )
        if prod:
            return prod[0]["id"]

        prod_id = self.api.create(
            "product.product",
            {
                "name": "Akku",
                "default_code": "15",
                "type": "consu",
            },
        )
        if isinstance(prod_id, (list, tuple)):
            prod_id = prod_id[0]
        return int(prod_id)

    def _get_default_internal_location(self) -> int | None:
        """
        Liefert einen internen Lagerort (z. B. Hauptlager) oder None,
        falls keiner existiert.
        """
        locations = self.api.search_read(
            "stock.location",
            [["usage", "=", "internal"]],
            ["id", "name"],
            limit=1,
        )
        if not locations:
            return None
        return locations[0]["id"]

    def _run_inventory_adjustment(self, product_id: int, location_id: int, new_qty: float) -> int:
        """
        Legt eine Inventur für ein Produkt an einem Lagerort an,
        setzt die gezählte Menge und validiert die Inventur.

        Gibt die Inventur-ID zurück.
        """
        inventory_vals: Dict[str, object] = {
            "name": f"Demo-Inventur {datetime.now().isoformat(timespec='seconds')}",
            "product_ids": [(6, 0, [product_id])],
            "location_ids": [(6, 0, [location_id])],
        }

        inv_id = self.api.create("stock.inventory", inventory_vals)
        if isinstance(inv_id, (list, tuple)):
            inv_id = inv_id[0]

        # Inventur starten
        self.api.call_kw("stock.inventory", "action_start", [inv_id], {})

        # Inventurlinien lesen und gezählte Menge setzen
        lines = self.api.search_read(
            "stock.inventory.line",
            [["inventory_id", "=", inv_id]],
            ["id"],
        )
        for line in lines:
            self.api.write("stock.inventory.line", [line["id"]], {"product_qty": new_qty})

        # Inventur validieren
        self.api.call_kw("stock.inventory", "action_validate", [inv_id], {})

        return int(inv_id)

    # -------------------------------------------------------------------------
    # Demo: Inventur
    # -------------------------------------------------------------------------

    def run_demo_inventory_case(self) -> None:
        """
        Simuliert eine Inventur für das Demo-Produkt 'Akku'.

        Ablauf:
        - Produkt 'Akku' sicherstellen.
        - Internen Lagerort bestimmen.
        - Inventur anlegen, gezählte Menge setzen, validieren.
        """
        info("Demo-Inventurfall wird ausgeführt...")

        prod_id = self._ensure_demo_product_akku()
        location_id = self._get_default_internal_location()
        if not location_id:
            warning("Kein interner Lagerort gefunden, Inventurfall wird nur protokolliert.")
            success("Demo-Inventurfall dokumentiert (ohne stock.inventory mangels Lagerort).")
            return

        try:
            # Beispiel: Zählung auf 10 Stück setzen
            inv_id = self._run_inventory_adjustment(product_id=prod_id, location_id=location_id, new_qty=10.0)
            success(
                f"Demo-Inventurfall für Produkt 'Akku' ausgeführt "
                f"(Inventur-ID {inv_id}, Lagerort-ID {location_id})."
            )
        except Exception:
            warning(
                "Inventur konnte nicht vollständig automatisch angelegt/validiert werden. "
                "Bitte Odoo-Version und stock.inventory-Konfiguration prüfen."
            )
            success("Demo-Inventurfall dokumentiert (Inventur nur teilweise ausgeführt).")

    # -------------------------------------------------------------------------
    # Demo: Ausschuss über stock.scrap
    # -------------------------------------------------------------------------

    def scrap_product(self, product_name: str, quantity: float) -> None:
        """
        Bucht Ausschuss für ein Produkt in das Schrottlager (stock.scrap).

        Logik:
        - Sucht das angegebene Produkt über seinen Namen oder legt es an.
        - Sichert eine Schrott-Location.
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
            prod_id = self.api.create(
                "product.product",
                {
                    "name": product_name,
                    "default_code": "SCRAP-DEMO",
                    "type": "consu",
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
            success(f"Ausschuss für '{product_name}' (Menge {qty}) gebucht (Scrap-ID {scrap_id}).")
        except Exception:
            warning(
                "Ausschuss konnte nicht vollständig automatisch gebucht werden. "
                "Bitte Odoo-Version und stock.scrap-Konfiguration prüfen."
            )

    # -------------------------------------------------------------------------
    # Kombinierte Demo
    # -------------------------------------------------------------------------

    def run_demo_inventory_and_scrap(self) -> None:
        """
        Führt eine kombinierte Demo für Inventur und Ausschuss aus.

        Schritte:
        1) Inventur des Demo-Produkts 'Akku' an einem internen Lagerort.
        2) Ausschussbuchung von 1 Stück 'Akku' ins Schrottlager.
        """
        self.run_demo_inventory_case()
        self.scrap_product("Akku", 1.0)
