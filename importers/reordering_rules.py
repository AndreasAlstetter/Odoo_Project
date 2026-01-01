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
            raise RuntimeError(f"Produkt für Reordering Rule nicht gefunden: '{product_name}'")

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
