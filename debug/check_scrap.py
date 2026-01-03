# debug/check_scrap.py
from __future__ import annotations

from datetime import datetime, timedelta
from typing import List, Dict, Any

from odoo_api import OdooAPI
from core.logging_utils import info


def check_recent_scrap(api: OdooAPI, days: int = 7) -> None:
    """
    Prüft, ob Scrap-Einträge (stock.scrap) vorhanden sind und wie sie aussehen.
    """
    date_from = datetime.utcnow() - timedelta(days=days)
    scraps: List[Dict[str, Any]] = api.search_read(
        "stock.scrap",
        [["date_done", ">=", date_from.strftime("%Y-%m-%d %H:%M:%S")]],
        ["id", "product_id", "scrap_qty", "date_done", "origin"],
        limit=100,
    )

    info(f"{len(scraps)} Scrap-Einträge in den letzten {days} Tagen gefunden.")
    for s in scraps:
        prod = s.get("product_id") or [None, ""]
        msg = (
            f"Scrap {s['id']} | Produkt={prod[1]} | Menge={s.get('scrap_qty')} | "
            f"Datum={s.get('date_done')} | Origin={s.get('origin')}"
        )
        info(msg)
