# processes/kpi_extractor.py

"""
KPI-Extraktion (einfache Kennzahlen aus Fertigung, Qualität und Lager).

Ziele:
- Fertigungs-Performance (Durchsatz, MO-Durchlaufzeit).
- QC-Quoten (Pass-/Fail-Anteil).
- Lagerkennzahlen (Bestände).
- Lead Time von Verkaufsauftrag bis Lieferung.
"""

from __future__ import annotations

from typing import Dict, List, Optional
from datetime import datetime

from odoo_api import OdooAPI
from core.logging_utils import info, warning


class KPIExtractor:
    """Extrahiert einfache KPIs aus Fertigung, QC und Lager."""

    def __init__(self, api: OdooAPI) -> None:
        self.api = api

    def get_mo_performance(self, start_date: datetime, end_date: datetime) -> Dict:
        """
        Liefert einfache Fertigungs-KPIs im Zeitraum.

        Kennzahlen:
        - Anzahl fertiggestellter MOs.
        - Durchschnittliche MO-Durchlaufzeit (in Tagen), basierend auf
          create_date und date_finished (falls vorhanden).
        """
        info(f"Berechne MO-Performance von {start_date} bis {end_date}...")

        mos = self.api.search_read(
            "mrp.production",
            [
                ["state", "=", "done"],
                ["create_date", ">=", start_date.strftime("%Y-%m-%d %H:%M:%S")],
                ["create_date", "<=", end_date.strftime("%Y-%m-%d %H:%M:%S")],
            ],
            ["id", "create_date", "date_finished"],
            limit=500,
        )

        durations: List[float] = []
        for mo in mos:
            c = mo.get("create_date")
            f = mo.get("date_finished")
            if not c or not f:
                continue
            try:
                dt_c = datetime.fromisoformat(c)
                dt_f = datetime.fromisoformat(f)
                durations.append((dt_f - dt_c).total_seconds() / 86400.0)
            except Exception:
                continue

        avg_duration = sum(durations) / len(durations) if durations else 0.0

        return {
            "mo_count": len(mos),
            "avg_throughput_days": avg_duration,
        }

    def get_qc_metrics(self, product_id: Optional[int] = None) -> Dict:
        """
        Liefert einfache QC-Kennzahlen.

        Annahmen:
        - QC-Ergebnisse werden über ein Feld 'x_qc_result' auf quality.check
          oder einem ähnlichen Modell erfasst ( 'pass' / 'fail' ).

        Kennzahlen:
        - Anzahl QC-Prüfungen.
        - Pass-/Fail-Anteil.
        """
        info("Berechne QC-Kennzahlen...")

        domain = []
        if product_id:
            domain.append(["product_id", "=", product_id])

        checks = self.api.search_read(
            "quality.check",
            domain,
            ["id", "x_qc_result"],
            limit=1000,
        )

        total = len(checks)
        passed = sum(1 for c in checks if c.get("x_qc_result") == "pass")
        failed = sum(1 for c in checks if c.get("x_qc_result") == "fail")

        pass_rate = (passed / total) if total else 0.0
        fail_rate = (failed / total) if total else 0.0

        return {
            "checks_total": total,
            "checks_passed": passed,
            "checks_failed": failed,
            "pass_rate": pass_rate,
            "fail_rate": fail_rate,
        }

    def get_inventory_metrics(self) -> Dict:
        """
        Liefert einfache Lagerkennzahlen.

        Kennzahlen:
        - Anzahl Produkte mit Bestand > 0.
        - Summe aller Bestände (qty_available).
        """
        info("Berechne Lager-Kennzahlen...")

        products = self.api.search_read(
            "product.product",
            [],
            ["id", "qty_available"],
            limit=1000,
        )

        stock_values = [p.get("qty_available", 0.0) for p in products]
        positive = [q for q in stock_values if q > 0]
        total_stock = sum(stock_values)

        return {
            "products_with_stock": len(positive),
            "total_stock_qty": total_stock,
        }

    def get_lead_time(self, so_id: int) -> float:
        """
        Berechnet die Lead Time (in Tagen) von Verkaufsauftrag bis Lieferung.

        - Start: create_date des sale.order.
        - Ende: maximaler completed-Datum der zugehörigen outgoing-Lieferungen
          (date_done auf stock.picking).
        """
        info(f"Berechne Lead Time für SO {so_id}...")

        so = self.api.search_read(
            "sale.order",
            [["id", "=", so_id]],
            ["name", "create_date"],
            limit=1,
        )
        if not so:
            warning(f"Verkaufsauftrag {so_id} nicht gefunden.")
            return 0.0

        so_name = so[0]["name"]
        so_create = so[0]["create_date"]
        try:
            dt_start = datetime.fromisoformat(so_create)
        except Exception:
            warning(f"create_date für SO {so_id} ungültig.")
            return 0.0

        pickings = self.api.search_read(
            "stock.picking",
            [
                ["origin", "=", so_name],
                ["picking_type_id.code", "=", "outgoing"],
                ["state", "=", "done"],
            ],
            ["id", "date_done"],
            limit=50,
        )
        if not pickings:
            warning(f"Keine abgeschlossenen Lieferungen für SO {so_id} gefunden.")
            return 0.0

        dates_done: List[datetime] = []
        for p in pickings:
            d = p.get("date_done")
            if not d:
                continue
            try:
                dates_done.append(datetime.fromisoformat(d))
            except Exception:
                continue

        if not dates_done:
            return 0.0

        dt_end = max(dates_done)
        return (dt_end - dt_start).total_seconds() / 86400.0

    def generate_report(self) -> Dict:
        """
        Erzeugt einen kompakten KPI-Report über Fertigung, QC, Lager und Lead Time.

        Hinweis:
        - Lead Time wird exemplarisch für den zuletzt angelegten Verkaufsauftrag
          berechnet (falls vorhanden).
        """
        info("Erzeuge KPI-Report...")

        now = datetime.utcnow()
        start = now.replace(hour=0, minute=0, second=0, microsecond=0)
        mo_perf = self.get_mo_performance(start, now)
        qc_metrics = self.get_qc_metrics()
        inv_metrics = self.get_inventory_metrics()

        so = self.api.search_read(
            "sale.order",
            [],
            ["id"],
            limit=1,
        )
        lead_time = self.get_lead_time(so[0]["id"]) if so else 0.0

        report = {
            "mo_performance": mo_perf,
            "qc_metrics": qc_metrics,
            "inventory_metrics": inv_metrics,
            "example_lead_time_days": lead_time,
        }

        info("KPI-Report erstellt.")
        return report
