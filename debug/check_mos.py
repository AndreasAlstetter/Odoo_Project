# debug/check_mos.py
from __future__ import annotations

from datetime import datetime, timedelta
from typing import List, Dict, Any

from odoo_api import OdooAPI
from core.logging_utils import info


def check_recent_mos(api: OdooAPI, days: int = 7) -> None:
    date_from = datetime.utcnow() - timedelta(days=days)
    mos: List[Dict[str, Any]] = api.search_read(
        "mrp.production",
        [
            ["state", "=", "done"],
            ["date_finished", ">=", date_from.strftime("%Y-%m-%d %H:%M:%S")],
        ],
        ["id", "name", "product_id", "date_finished"],  # <== date_planned_start entfernt
        limit=50,
    )

    info(f"{len(mos)} MOs in den letzten {days} Tagen gefunden.")
    for mo in mos:
        prod = mo.get("product_id") or [None, ""]
        msg = (
            f"MO {mo['id']} | {mo['name']} | Produkt={prod[1]} | "
            f"finished={mo.get('date_finished')}"
        )
        info(msg)
