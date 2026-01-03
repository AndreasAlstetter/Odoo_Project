# debug/check_workorders.py
from __future__ import annotations

from datetime import datetime, timedelta
from typing import List, Dict, Any

from odoo_api import OdooAPI
from core.logging_utils import info


def check_recent_workorders(api: OdooAPI, days: int = 2) -> None:
    """
    Prüft, ob Workorders in den letzten N Tagen date_start und date_finished gesetzt haben.
    """
    date_from = datetime.utcnow() - timedelta(days=days)
    workorders: List[Dict[str, Any]] = api.search_read(
        "mrp.workorder",
        [
            ["state", "=", "done"],
            ["date_finished", ">=", date_from.strftime("%Y-%m-%d %H:%M:%S")],
        ],
        ["id", "name", "production_id", "date_start", "date_finished", "qty_produced"],
        limit=50,
    )

    info(f"{len(workorders)} Workorders in den letzten {days} Tagen gefunden.")
    for wo in workorders:
        prod = wo.get("production_id") or [None, ""]
        msg = (
            f"WO {wo['id']} | {wo.get('name')} | MO={prod[1]} | "
            f"date_start={wo.get('date_start')} | date_finished={wo.get('date_finished')} | "
            f"qty_produced={wo.get('qty_produced')}"
        )
        info(msg)
