# integration/umh_mapping.py
"""
Mapping von Odoo-Stammdaten auf das UMH-Masterdata-Format.

Genutzt für:
- Export von Produkten, BoMs und (Python-)Routings in eine
  UMH-kompatible JSON-Struktur (z. B. ``umh_masterdata.json``).
"""

from __future__ import annotations

from typing import Dict, Any, List

import json


class UMHMapper:
    """Mappt Odoo-Stammdaten in ein generisches UMH-Masterdata-Format."""

    def __init__(self) -> None:
        self.mapping_rules: Dict[str, Any] = {}

    def map_product(self, odoo_product: Dict[str, Any]) -> Dict[str, Any]:
        """
        Mappt ein Odoo-Produkt in das UMH-Produktformat.

        Erwartete Keys im Odoo-Produktdict:
        - id, name, default_code, type, uom_id, categ_id, standard_price, active
        """
        return {
            "umh_id": f"product:{odoo_product.get('id')}",
            "name": odoo_product.get("name"),
            "default_code": odoo_product.get("default_code"),
            "type": odoo_product.get("type"),
            "uom_id": odoo_product.get("uom_id"),
            "categ_id": odoo_product.get("categ_id"),
            "standard_price": odoo_product.get("standard_price"),
            "active": odoo_product.get("active", True),
        }

    def map_bom(self, odoo_bom: Dict[str, Any]) -> Dict[str, Any]:
        """
        Mappt eine Odoo-Stückliste in das UMH-BoM-Format.

        Erwartete Keys:
        - id, product_tmpl_id, product_id, product_qty, type, code
        """
        return {
            "umh_id": f"bom:{odoo_bom.get('id')}",
            "product_tmpl_id": odoo_bom.get("product_tmpl_id"),
            "product_id": odoo_bom.get("product_id"),
            "product_qty": odoo_bom.get("product_qty"),
            "type": odoo_bom.get("type"),
            "code": odoo_bom.get("code"),
        }

    def map_routing(self, routing_ops: List[Dict[str, Any]], routing_id: str = "evo2") -> Dict[str, Any]:
        """
        Mappt eine Liste von Routing-Operationen in das UMH-Routingformat.

        Erwartete Keys je Operation:
        - seq, name, workcenter_code, setup_time_min, run_time_min, qty_per_cycle
        """
        return {
            "umh_id": f"routing:{routing_id}",
            "operations": [
                {
                    "seq": op.get("seq"),
                    "name": op.get("name"),
                    "workcenter_code": op.get("workcenter_code"),
                    "setup_time_min": op.get("setup_time_min"),
                    "run_time_min": op.get("run_time_min"),
                    "qty_per_cycle": op.get("qty_per_cycle"),
                }
                for op in routing_ops
            ],
        }

    def load_mapping_config(self, filepath: str) -> bool:
        """
        Lädt optionale Mappingregeln aus einer JSON-Konfigurationsdatei.

        Diese Regeln werden aktuell noch nicht angewendet, erlauben aber
        zukünftige Anpassungen des Mapping-Verhaltens ohne Codeänderung.
        """
        try:
            with open(filepath, "r", encoding="utf-8") as f:
                self.mapping_rules = json.load(f)
            return True
        except OSError:
            return False
