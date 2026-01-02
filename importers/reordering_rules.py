# importers/reordering_rules.py
"""
Importer für Dispositions-/Reordering-Regeln (Mindestbestände).

Modellbezug:
- Standardmodell: ``stock.warehouse.orderpoint`` (Reordering Rules).

Diese Implementierung legt einfache Mindestbestandsregeln an, basierend
auf Produktname, Lagerort und Min/Max-Mengen.
"""

from __future__ import annotations

from typing import Dict

from odoo_api import OdooAPI
from core import info, warning


class ReorderingRulesImporter:
    """Importiert Reordering-Regeln und Mindestbestands-Einstellungen."""

    def __init__(self, api: OdooAPI) -> None:
        self.api = api

    def create_reordering_rule(self, data: Dict[str, object]) -> int:
        """
        Legt eine einzelne Reordering-Regel an.

        Erwartete Keys in ``data``:
        - product_name
        - location_name (optional; sonst WH/Stock)
        - min_qty
        - max_qty
        """
        product_name = str(data.get("product_name") or "").strip()
        if not product_name:
            raise ValueError("product_name ist erforderlich für eine Reordering Rule.")

        prod = self.api.search_read(
            "product.product",
            [["name", "=", product_name]],
            ["id"],
            limit=1,
        )
        if not prod:
            warning(f"Produkt für Reordering Rule nicht gefunden: '{product_name}', Zeile wird übersprungen.")
            return 0


        product_id = prod[0]["id"]

        location_id = None
        location_name = str(data.get("location_name") or "").strip()
        if location_name:
            loc = self.api.search_read(
                "stock.location",
                [["complete_name", "=", location_name]],
                ["id"],
                limit=1,
            )
            if loc:
                location_id = loc[0]["id"]
            else:
                warning(f"Lagerort '{location_name}' nicht gefunden, Standardlager wird verwendet.")

        if location_id is None:
            wh = self.api.search_read(
                "stock.warehouse",
                [],
                ["lot_stock_id"],
                limit=1,
            )
            if not wh:
                raise RuntimeError("Kein Warehouse gefunden, kann Standardlager nicht bestimmen.")
            location_id = wh[0]["lot_stock_id"][0]

        min_qty = float(data.get("min_qty") or 0.0)
        max_qty = float(data.get("max_qty") or 0.0)

        # NEU: prüfen, ob es schon eine Rule gibt
        existing = self.api.search_read(
            "stock.warehouse.orderpoint",
            [["product_id", "=", product_id], ["location_id", "=", location_id]],
            ["id"],
            limit=1,
        )
        if existing:
            op_id = existing[0]["id"]
            info(
                f"Reordering Rule für Produkt '{product_name}' am Lagerort {location_name or location_id} "
                f"existiert bereits (ID {op_id}), überspringe."
            )
            return int(op_id)

        vals: Dict[str, object] = {
            "product_id": product_id,
            "location_id": location_id,
            "product_min_qty": min_qty,
            "product_max_qty": max_qty,
        }

        op_id = self.api.create("stock.warehouse.orderpoint", vals)
        if isinstance(op_id, (list, tuple)):
            op_id = op_id[0]
        op_id = int(op_id)
        info(
            f"Reordering Rule für Produkt '{product_name}' "
            f"(Min {min_qty}, Max {max_qty}) angelegt (ID {op_id})."
        )
        return op_id

    def import_from_csv(self, filepath: str) -> bool:
        """
        Importiert Reordering-Regeln aus einer CSV-Datei.

        Erwartete Spalten:
        - product_name
        - location_name (optional)
        - min_qty
        - max_qty
        """
        import csv

        with open(filepath, "r", encoding="utf-8") as f:
            reader = csv.DictReader(f)
            for row in reader:
                product_name = (row.get("product_name") or "").strip()
                if not product_name:
                    warning(f"Ignoriere Zeile ohne product_name: {row}")
                    continue

                data: Dict[str, object] = {
                    "product_name": product_name,
                    "location_name": (row.get("location_name") or "").strip(),
                    "min_qty": row.get("min_qty") or 0.0,
                    "max_qty": row.get("max_qty") or 0.0,
                }
                self.create_reordering_rule(data)

        info(f"Reordering-Import aus {filepath} abgeschlossen.")
        return True
    
    def print_reordering_status(self) -> None:
        """
        Gibt einen Überblick über Reordering Rules (Min/Max) und aktuelle Verfügbarkeiten.
        Aktuell: Verfügbarkeit über alle Lagerorte (ohne Location-Filter).
        """
        rules = self.api.search_read(
            "stock.warehouse.orderpoint",
            [],
            ["id", "product_id", "location_id", "product_min_qty", "product_max_qty"],
            limit=200,
        )
        if not rules:
            info("Keine Reordering Rules gefunden.")
            return

        for op in rules:
            product_id, product_name = op["product_id"]
            location = op.get("location_id")
            location_id = location[0] if location else None
            location_name = location[1] if location else "N/A"
            min_qty = op.get("product_min_qty", 0.0)
            max_qty = op.get("product_max_qty", 0.0)

            # WICHTIG: ohne Location-Filter, um alle Quants zu sehen
            quants = self.api.search_read(
                "stock.quant",
                [["product_id", "=", product_id]],
                ["quantity"],
                limit=500,
            )
            available = sum(q.get("quantity", 0.0) for q in quants)

            info(
                f"Reordering '{product_name}': Min={min_qty}, Max={max_qty}, "
                f"Verfügbar={available} (Location={location_name})"
            )

    def print_reordering_status_for_location(self, location_complete_name: str) -> None:
        """
        Wie print_reordering_status, aber nur Quants im angegebenen Lagerort
        (complete_name, z. B. 'WH/Stock') berücksichtigen.
        """
        locs = self.api.search_read(
            "stock.location",
            [["complete_name", "=", location_complete_name]],
            ["id"],
            limit=1,
        )
        if not locs:
            warning(f"Lagerort '{location_complete_name}' nicht gefunden.")
            return

        location_id = locs[0]["id"]

        rules = self.api.search_read(
            "stock.warehouse.orderpoint",
            [["location_id", "=", location_id]],
            ["id", "product_id", "location_id", "product_min_qty", "product_max_qty"],
            limit=200,
        )
        if not rules:
            info(f"Keine Reordering Rules für Lagerort {location_complete_name} gefunden.")
            return

        for op in rules:
            product_id, product_name = op["product_id"]
            min_qty = op.get("product_min_qty", 0.0)
            max_qty = op.get("product_max_qty", 0.0)

            quants = self.api.search_read(
                "stock.quant",
                [
                    ["product_id", "=", product_id],
                    ["location_id", "=", location_id],
                ],
                ["quantity"],
                limit=500,
            )
            available = sum(q.get("quantity", 0.0) for q in quants)

            info(
                f"[{location_complete_name}] Reordering '{product_name}': "
                f"Min={min_qty}, Max={max_qty}, Verfügbar={available}"
            )
