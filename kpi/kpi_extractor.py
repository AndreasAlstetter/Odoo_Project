"""
KPI extraction (simple KPIs from MO, QC, inventory data)
"""

from typing import Dict, List, Optional
from datetime import datetime, timedelta


class KpiExtractor:
    """Extract simple KPIs from manufacturing, QC, inventory and sales"""

    def __init__(self, odoo_client):
        self.client = odoo_client

    # -------------------------------------------------------------------------
    # 1) Output aggregiert je Produkt
    # -------------------------------------------------------------------------
    def get_output_aggregated(self, days: int = 7) -> Dict:
        """
        Aggregiert produzierte und ausgelieferte Stückzahlen je Produkt
        über einen Zeitraum.

        Rückgabe-Format (für MQTT):
        {
          "days": <int>,
          "per_product": {
            "<product_name>": {
              "qty_produced": <float>,
              "qty_delivered": <float>,
              "mo_count": <int>,
              "so_count": <int>
            },
            ...
          }
        }
        """
        end_date = datetime.now()
        start_date = end_date - timedelta(days=days)

        start_str = start_date.strftime("%Y-%m-%d 00:00:00")
        end_str = end_date.strftime("%Y-%m-%d 23:59:59")

        # Produktion (mrp.production)
        mo_domain = [
            ["create_date", ">=", start_str],
            ["create_date", "<=", end_str],
        ]
        mo_fields = ["id", "product_id", "product_qty"]
        mos = self.client.search_read("mrp.production", mo_domain, mo_fields, limit=2000)

        per_product: Dict[str, Dict[str, float]] = {}

        def add_prod(name: str, qty: float, mo_id: int):
            rec = per_product.setdefault(
                name,
                {"qty_produced": 0.0, "qty_delivered": 0.0, "mo_count": 0, "so_count": 0},
            )
            rec["qty_produced"] += qty
            rec["mo_count"] += 1

        for mo in mos:
            prod_field = mo.get("product_id")
            if not prod_field:
                continue
            prod_name = prod_field[1]
            qty = mo.get("product_qty") or 0.0
            add_prod(prod_name, qty, mo["id"])

        # Lieferungen: direkt über stock.move mit state=done und outgoing-Pickings
        move_domain = [
            ["state", "=", "done"],
            ["picking_id.picking_type_id.code", "=", "outgoing"],
            ["date", ">=", start_str],
            ["date", "<=", end_str],
        ]
        move_fields = ["id", "product_id", "product_uom_qty", "sale_line_id"]
        moves = self.client.search_read("stock.move", move_domain, move_fields, limit=5000)

        # Helper: SO-IDs zurückverfolgen
        so_counts_per_product: Dict[str, set] = {}

        for m in moves:
            prod_field = m.get("product_id")
            if not prod_field:
                continue
            prod_name = prod_field[1]
            qty = m.get("product_uom_qty") or 0.0
            rec = per_product.setdefault(
                prod_name,
                {"qty_produced": 0.0, "qty_delivered": 0.0, "mo_count": 0, "so_count": 0},
            )
            rec["qty_delivered"] += qty

            # SO ableiten über sale_line_id -> sale.order
            sale_line = m.get("sale_line_id")
            if sale_line:
                so_line_id = sale_line[0]
                so_line_data = self.client.read(
                    "sale.order.line", [so_line_id], ["order_id"]
                )
                if so_line_data:
                    so_id = so_line_data[0]["order_id"][0]
                    so_counts_per_product.setdefault(prod_name, set()).add(so_id)

        # SO-Count eintragen
        for prod_name, so_ids in so_counts_per_product.items():
            rec = per_product.setdefault(
                prod_name,
                {"qty_produced": 0.0, "qty_delivered": 0.0, "mo_count": 0, "so_count": 0},
            )
            rec["so_count"] = len(so_ids)

        return {"days": days, "per_product": per_product}

    # -------------------------------------------------------------------------
    # 2) Zykluszeit aggregiert je Produkt
    # -------------------------------------------------------------------------
    def get_cycle_time_aggregated(self, days: int = 7) -> Dict:
        """
        Aggregiert durchschnittliche MO-Durchlaufzeit je Produkt.

        Rückgabe:
        {
          "days": <int>,
          "per_product": {
            "<product_name>": {
              "avg_cycle_time_h": <float>,
              "samples": <int>
            },
            ...
          }
        }
        """
        end_date = datetime.now()
        start_date = end_date - timedelta(days=days)

        start_str = start_date.strftime("%Y-%m-%d 00:00:00")
        end_str = end_date.strftime("%Y-%m-%d 23:59:59")

        mo_domain = [
            ["create_date", ">=", start_str],
            ["create_date", "<=", end_str],
        ]
        mo_fields = ["id", "product_id", "create_date", "date_finished"]
        mos = self.client.search_read("mrp.production", mo_domain, mo_fields, limit=2000)

        per_product: Dict[str, Dict[str, float]] = {}

        for mo in mos:
            prod_field = mo.get("product_id")
            if not prod_field:
                continue
            prod_name = prod_field[1]
            start = mo.get("create_date")
            end_ = mo.get("date_finished")
            if not (start and end_):
                continue

            try:
                dt_start = datetime.fromisoformat(start)
                dt_end = datetime.fromisoformat(end_)
                delta_h = (dt_end - dt_start).total_seconds() / 3600.0
            except Exception:
                continue

            rec = per_product.setdefault(
                prod_name,
                {"_sum": 0.0, "_cnt": 0, "avg_cycle_time_h": 0.0, "samples": 0},
            )
            rec["_sum"] += delta_h
            rec["_cnt"] += 1

        for prod_name, rec in per_product.items():
            if rec["_cnt"] > 0:
                rec["avg_cycle_time_h"] = rec["_sum"] / rec["_cnt"]
                rec["samples"] = rec["_cnt"]
            del rec["_sum"]
            del rec["_cnt"]

        return {"days": days, "per_product": per_product}

    # -------------------------------------------------------------------------
    # 3) MO-Lead-Time je MO
    # -------------------------------------------------------------------------
    def get_mo_lead_time_aggregated(self, days: int = 30) -> Dict:
        """
        Lead-Time je MO (Start → Fertigmeldung).

        Rückgabe:
        {
          "days": <int>,
          "records": [
            {"mo_id": <int>, "product_name": "<name>", "lead_time_h": <float>},
            ...
          ]
        }
        """
        end_date = datetime.now()
        start_date = end_date - timedelta(days=days)

        start_str = start_date.strftime("%Y-%m-%d 00:00:00")
        end_str = end_date.strftime("%Y-%m-%d 23:59:59")

        mo_domain = [
            ["create_date", ">=", start_str],
            ["create_date", "<=", end_str],
        ]
        mo_fields = ["id", "product_id", "create_date", "date_finished"]
        mos = self.client.search_read("mrp.production", mo_domain, mo_fields, limit=2000)

        records: List[Dict] = []

        for mo in mos:
            start = mo.get("create_date")
            end_ = mo.get("date_finished")
            prod_field = mo.get("product_id")
            if not (start and end_ and prod_field):
                continue

            try:
                dt_start = datetime.fromisoformat(start)
                dt_end = datetime.fromisoformat(end_)
                delta_h = (dt_end - dt_start).total_seconds() / 3600.0
            except Exception:
                continue

            records.append(
                {
                    "mo_id": mo["id"],
                    "product_name": prod_field[1],
                    "lead_time_h": delta_h,
                }
            )

        return {"days": days, "records": records}

    # -------------------------------------------------------------------------
    # 4) Scrap aggregiert je Produkt
    # -------------------------------------------------------------------------
    def get_scrap_aggregated(self, days: int = 7) -> Dict:
        """
        Aggregiert Ausschuss und Gutmenge je Produkt.

        Rückgabe:
        {
          "days": <int>,
          "per_product": {
            "<product_name>": {
              "scrap_qty": <float>,
              "good_qty": <float>,
              "scrap_rate": <float>
            },
            ...
          }
        }
        """
        end_date = datetime.now()
        start_date = end_date - timedelta(days=days)

        start_str = start_date.strftime("%Y-%m-%d 00:00:00")
        end_str = end_date.strftime("%Y-%m-%d 23:59:59")

        # Scrap
        scrap_domain = [
            ["create_date", ">=", start_str],
            ["create_date", "<=", end_str],
        ]
        scrap_fields = ["id", "product_id", "scrap_qty"]
        scraps = self.client.search_read("stock.scrap", scrap_domain, scrap_fields, limit=2000)

        per_product: Dict[str, Dict[str, float]] = {}

        for s in scraps:
            prod_field = s.get("product_id")
            if not prod_field:
                continue
            prod_name = prod_field[1]
            qty = s.get("scrap_qty") or 0.0
            rec = per_product.setdefault(
                prod_name, {"scrap_qty": 0.0, "good_qty": 0.0, "scrap_rate": 0.0}
            )
            rec["scrap_qty"] += qty

        # Good qty aus MOs im gleichen Zeitraum
        mo_domain = [
            ["create_date", ">=", start_str],
            ["create_date", "<=", end_str],
        ]
        mo_fields = ["id", "product_id", "product_qty"]
        mos = self.client.search_read("mrp.production", mo_domain, mo_fields, limit=2000)

        for mo in mos:
            prod_field = mo.get("product_id")
            if not prod_field:
                continue
            prod_name = prod_field[1]
            qty = mo.get("product_qty") or 0.0
            rec = per_product.setdefault(
                prod_name, {"scrap_qty": 0.0, "good_qty": 0.0, "scrap_rate": 0.0}
            )
            rec["good_qty"] += qty

        for prod_name, rec in per_product.items():
            total = rec["good_qty"] + rec["scrap_qty"]
            rec["scrap_rate"] = (rec["scrap_qty"] / total) if total > 0 else 0.0

        return {"days": days, "per_product": per_product}

    # -------------------------------------------------------------------------
    # 5) Revenue aggregiert
    # -------------------------------------------------------------------------
    def get_revenue_aggregated(self, days: int = 30) -> Dict:
        """
        Aggregierter Umsatz über alle Aufträge im Zeitraum.

        Rückgabe:
        {
          "days": <int>,
          "revenue_total": <float>,
          "records_count": <int>
        }
        """
        end_date = datetime.now()
        start_date = end_date - timedelta(days=days)

        start_str = start_date.strftime("%Y-%m-%d 00:00:00")
        end_str = end_date.strftime("%Y-%m-%d 23:59:59")

        so_domain = [
            ["date_order", ">=", start_str],
            ["date_order", "<=", end_str],
            ["state", "in", ["sale", "done"]],
        ]
        so_fields = ["id", "amount_total"]
        orders = self.client.search_read("sale.order", so_domain, so_fields, limit=2000)

        revenue_total = sum((o.get("amount_total") or 0.0) for o in orders)
        records_count = len(orders)

        return {
            "days": days,
            "revenue_total": revenue_total,
            "records_count": records_count,
        }

    # -------------------------------------------------------------------------
    # 6) Lead-Time für Orders aggregiert
    # -------------------------------------------------------------------------
    def get_lead_time_orders_aggregated(self, days: int = 30) -> Dict:
        """
        Lead-Time je Kundenauftrag (Order → Lieferung).

        Rückgabe:
        {
          "days": <int>,
          "records": [
            {"so_id": <int>, "so_name": "<name>", "lead_time_h": <float>},
            ...
          ]
        }
        """
        end_date = datetime.now()
        start_date = end_date - timedelta(days=days)

        start_str = start_date.strftime("%Y-%m-%d 00:00:00")
        end_str = end_date.strftime("%Y-%m-%d 23:59:59")

        so_domain = [
            ["date_order", ">=", start_str],
            ["date_order", "<=", end_str],
            ["state", "in", ["sale", "done"]],
        ]
        so_fields = ["id", "name", "date_order"]
        orders = self.client.search_read("sale.order", so_domain, so_fields, limit=2000)

        records: List[Dict] = []

        for so in orders:
            so_id = so["id"]
            so_name = so.get("name")
            so_date = so.get("date_order")
            if not (so_name and so_date):
                continue

            try:
                dt_so = datetime.fromisoformat(so_date)
            except Exception:
                continue

            pick_domain = [["origin", "=", so_name], ["state", "=", "done"]]
            pick_fields = ["id", "date_done"]
            pickings = self.client.search_read("stock.picking", pick_domain, pick_fields, limit=10)

            lead_times = []
            for p in pickings:
                done = p.get("date_done")
                if not done:
                    continue
                try:
                    dt_done = datetime.fromisoformat(done)
                    delta_h = (dt_done - dt_so).total_seconds() / 3600.0
                    lead_times.append(delta_h)
                except Exception:
                    continue

            if lead_times:
                records.append(
                    {
                        "so_id": so_id,
                        "so_name": so_name,
                        "lead_time_h": min(lead_times),
                    }
                )

        return {"days": days, "records": records}

    # -------------------------------------------------------------------------
    # 7) Inventory-Snapshot aggregiert je Produkt
    # -------------------------------------------------------------------------
    def get_inventory_aggregated(self) -> Dict:
        """
        Einfacher Inventory-Snapshot je Produkt.

        Rückgabe:
        {
          "per_product": {
            "<product_name>": {
              "on_hand": <float>,
              "reserved": <float>
            },
            ...
          }
        }
        """
        try:
            quant_fields = ["product_id", "quantity", "reserved_quantity"]
            quants = self.client.search_read("stock.quant", [], quant_fields, limit=5000)
        except Exception:
            quants = []

        per_product: Dict[str, Dict[str, float]] = {}

        for q in quants:
            prod_field = q.get("product_id")
            if not prod_field:
                continue
            prod_name = prod_field[1]
            on_hand = q.get("quantity") or 0.0
            reserved = q.get("reserved_quantity") or 0.0

            rec = per_product.setdefault(
                prod_name, {"on_hand": 0.0, "reserved": 0.0}
            )
            rec["on_hand"] += on_hand
            rec["reserved"] += reserved

        return {"per_product": per_product}
