# debug/check_orders.py
from __future__ import annotations

from datetime import datetime, timedelta
from typing import List, Dict, Any

from odoo_api import OdooAPI
from core.logging_utils import info


def check_recent_orders(api: OdooAPI, days: int = 7) -> None:
    date_from = datetime.utcnow() - timedelta(days=days)
    orders: List[Dict[str, Any]] = api.search_read(
        "sale.order",
        [["date_order", ">=", date_from.strftime("%Y-%m-%d %H:%M:%S")]],
        ["id", "name", "date_order"],
        limit=30,
    )

    info(f"{len(orders)} Sales Orders in den letzten {days} Tagen gefunden.")
    for so in orders:
        pickings = api.search_read(
            "stock.picking",
            [
                ["origin", "=", so["name"]],
                ["picking_type_code", "=", "outgoing"],
            ],
            ["id", "state", "date_done"],
            limit=3,
        )
        info(f"SO {so['name']} | date_order={so['date_order']} | Pickings={pickings}")
