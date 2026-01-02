# integration/umh_export_masterdata.py
"""
Exportiert Odoo-Stammdaten (Produkte, BoMs, Routing) in ein
UMH-kompatibles JSON-Format.

Ergebnisdatei:
- Standard: ``umh_masterdata.json`` im Projektverzeichnis.

Inhalt:
- products : Liste gemappter Produkte
- boms     : Liste gemappter Stücklisten inkl. Linien
- routing  : Python-Routing (z. B. Spartan) als Operationenliste
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import List, Dict, Any

from odoo_api import OdooAPI
from integration.umh_mapping import UMHMapper
from processes.production_routing import get_routing
from core import info

from config import UMH_MASTERDATA_EXPORT_FILE

def export_masterdata(output_file: str | None = None) -> None:
    path = output_file or UMH_MASTERDATA_EXPORT_FILE
    """
    Exportiert Masterdaten aus Odoo in eine UMH-Masterdata-Datei.

    Parameters
    ----------
    output_file:
        Pfad zur Ausgabedatei (JSON).

    Returns
    -------
    Path
        Pfad zur geschriebenen Datei.
    """
    api = OdooAPI()
    mapper = UMHMapper()

    # Produkte
    products: List[Dict[str, Any]] = api.search_read(
        "product.product",
        [["sale_ok", "=", True]],
        ["id", "name", "default_code", "type", "uom_id", "categ_id", "standard_price", "active"],
        limit=100,
    )
    umh_products = [mapper.map_product(p) for p in products]

    # BoMs + Linien
    boms: List[Dict[str, Any]] = api.search_read(
        "mrp.bom",
        [],
        ["id", "product_tmpl_id", "product_id", "product_qty", "type", "code"],
        limit=100,
    )

    umh_boms: List[Dict[str, Any]] = []
    for bom in boms:
        lines: List[Dict[str, Any]] = api.search_read(
            "mrp.bom.line",
            [["bom_id", "=", bom["id"]]],
            ["product_id", "product_qty"],
            limit=1000,
        )

        # Odoo Many2one sind [id, name]; hier nur id übernehmen
        bom["lines"] = [
            {
                "product_id": line.get("product_id")[0] if line.get("product_id") else None,
                "product_qty": line.get("product_qty"),
            }
            for line in lines
        ]

        umh_boms.append(mapper.map_bom(bom))

    # Routing (Python-basiert für Variante 'spartan')
    ops = get_routing("spartan")
    routing_ops = [
        {
            "seq": op.seq,
            "name": op.name,
            "workcenter_code": op.workcenter_code,
            "setup_time_min": op.setup_time_min,
            "run_time_min": op.run_time_min,
            "qty_per_cycle": op.qty_per_cycle,
        }
        for op in ops
    ]
    umh_routing = mapper.map_routing(routing_ops, routing_id="spartan")

    payload = {
        "products": umh_products,
        "boms": umh_boms,
        "routing": umh_routing,
    }

    out_path = Path(path)
    out_path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    info(f"UMH-Masterdata-Export abgeschlossen: {out_path}")
    return out_path
