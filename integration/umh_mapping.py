# integration/umh_mapping.py
from __future__ import annotations

"""
UMH mapping - map master data and UNS namespaces
"""

from typing import Dict, Any, List, Optional
import json


class UMHMapper:
    """Map Odoo master data to UMH (Universal Manufacturing Hub) format"""

    def __init__(self) -> None:
        self.mapping_rules: Dict[str, Any] = {}

    def map_product(self, odoo_product: Dict) -> Dict:
        """Map Odoo product to UMH format"""
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

    def map_bom(self, odoo_bom: Dict) -> Dict:
        """Map BOM to UMH format"""
        return {
            "umh_id": f"bom:{odoo_bom.get('id')}",
            "product_tmpl_id": odoo_bom.get("product_tmpl_id"),
            "product_id": odoo_bom.get("product_id"),
            "product_qty": odoo_bom.get("product_qty"),
            "type": odoo_bom.get("type"),
            "code": odoo_bom.get("code"),
        }

    def map_routing(self, routing_ops: List[Dict]) -> Dict:
        """Map routing (list of operations) to UMH format"""
        return {
            "umh_id": "routing:evo2",
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
        """Load mapping rules from config file (optional, JSON)"""
        try:
            with open(filepath, "r", encoding="utf-8") as f:
                self.mapping_rules = json.load(f)
            return True
        except OSError:
            return False


# Zusätzliche UNS-Mapping-Utilities (für MQTT-Events/KPIs)

LOCATION_TO_UNS: Dict[str, str] = {
    "WH/Stock": "ttz-leipheim/warehouse/main",
    "WH/Incoming": "ttz-leipheim/warehouse/inbound",
    "WH/Production": "ttz-leipheim/production/buffer",
}

WORKCENTER_TO_UNS: Dict[str, str] = {
    "3D Drucker": "ttz-leipheim/assembly_1/3d_printer",
    "Lasercutter": "ttz-leipheim/assembly_1/laser",
    "Montage": "ttz-leipheim/assembly_2/assembly",
    "Qualität": "ttz-leipheim/quality/station_1",
}

PRODUCT_TO_UNS: Dict[str, str] = {
    "EVO2 Spartan Drohne": "ttz-leipheim/product/evo2_spartan",
    "EVO2 Lightweight Drohne": "ttz-leipheim/product/evo2_lightweight",
    "EVO2 Balance Drohne": "ttz-leipheim/product/evo2_balance",
}


def map_location_to_uns(location_name: str) -> str:
    return LOCATION_TO_UNS.get(location_name, f"ttz-leipheim/location/{location_name}")


def map_workcenter_to_uns(workcenter_name: str) -> str:
    return WORKCENTER_TO_UNS.get(
        workcenter_name, f"ttz-leipheim/workcenter/{workcenter_name}"
    )


def map_product_to_uns(product_name: str) -> str:
    return PRODUCT_TO_UNS.get(product_name, f"ttz-leipheim/product/{product_name}")


def enrich_event_with_uns(event: Dict[str, Any]) -> Dict[str, Any]:
    data = dict(event.get("data") or {})

    prod_name: Optional[str] = data.get("product_name")
    if prod_name:
        data["product_uns"] = map_product_to_uns(prod_name)

    loc_from_name: Optional[str] = data.get("location_from_name")
    if loc_from_name:
        data["location_from_uns"] = map_location_to_uns(loc_from_name)

    loc_to_name: Optional[str] = data.get("location_to_name")
    if loc_to_name:
        data["location_to_uns"] = map_location_to_uns(loc_to_name)

    event["data"] = data
    return event
