# importers/bom_operation_importer.py

from __future__ import annotations

from typing import List, Dict
import csv
from pathlib import Path

from odoo_api import OdooAPI
from config import (
    PRODUCT_SPARTAN_NAME,
    PRODUCT_LIGHTWEIGHT_NAME,
    PRODUCT_BALANCE_NAME,
    ROUTING_CSV_PATH,
)
from core import info


class BomOperationImporter:
    """Legt BoM-Operationen je Drohnenvariante aus routings.csv an."""

    def __init__(self, api: OdooAPI, csv_path: Path | None = None) -> None:
        self.api = api
        self.csv_path = csv_path or Path(ROUTING_CSV_PATH)

    def _load_rows(self) -> List[Dict[str, str]]:
        if not self.csv_path.exists():
            raise FileNotFoundError(f"Routing-CSV nicht gefunden: {self.csv_path}")
        with self.csv_path.open("r", encoding="utf-8") as f:
            reader = csv.DictReader(f)
            return list(reader)

    def _product_name_for_variant(self, variant: str) -> str:
        v = (variant or "").lower().strip()
        if v == "spartan":
            return PRODUCT_SPARTAN_NAME
        if v == "lightweight":
            return PRODUCT_LIGHTWEIGHT_NAME
        if v == "balance":
            return PRODUCT_BALANCE_NAME
        return variant

    def _find_product_tmpl(self, variant: str) -> int:
        name = self._product_name_for_variant(variant)
        res = self.api.search_read(
            "product.template",
            [["name", "=", name]],
            ["id"],
            limit=1,
        )
        if not res:
            raise RuntimeError(f"Produktvorlage für Variante '{variant}' nicht gefunden ({name})")
        return res[0]["id"]

    def _find_bom_for_template(self, tmpl_id: int) -> int:
        """Einfachste Variante: erste Stückliste der Vorlage verwenden."""
        res = self.api.search_read(
            "mrp.bom",
            [["product_tmpl_id", "=", tmpl_id]],
            ["id"],
            limit=1,
        )
        if not res:
            raise RuntimeError(f"Keine BoM für product.template {tmpl_id} gefunden")
        return res[0]["id"]

    def _get_workcenter_by_code(self, code: str) -> int:
        res = self.api.search_read(
            "mrp.workcenter",
            [["code", "=", code]],
            ["id"],
            limit=1,
        )
        if not res:
            raise RuntimeError(f"Workcenter mit Code '{code}' nicht gefunden.")
        return res[0]["id"]

    @staticmethod
    def _safe_float(val, default: float = 0.0) -> float:
        try:
            if val is None or val == "":
                return default
            return float(val)
        except Exception:
            return default

    def _clear_operations_for_bom(self, bom_id: int) -> None:
        """Optionale Bereinigung, damit der Import wiederholbar ist."""
        op_ids = self.api.search_read(
            "mrp.bom.operation",
            [["bom_id", "=", bom_id]],
            ["id"],
        )
        ids = [o["id"] for o in op_ids]
        if ids:
            self.api.unlink("mrp.bom.operation", ids)

    def _create_operations_for_variant(self, variant: str, rows: List[Dict[str, str]]) -> None:
        tmpl_id = self._find_product_tmpl(variant)
        bom_id = self._find_bom_for_template(tmpl_id)

        # optional: alte Operationen löschen
        self._clear_operations_for_bom(bom_id)

        sorted_rows = sorted(
            rows,
            key=lambda r: int((r.get("operation_seq") or "0").strip() or "0"),
        )

        seq = 1
        for row in sorted_rows:
            op_name = (row.get("operation_name") or "").strip()
            wc_code = (row.get("workcenter_code") or "").strip()
            if not op_name or not wc_code:
                continue

            setup_min = self._safe_float(row.get("setup_time_min"), 0.0)
            run_min = self._safe_float(row.get("run_time_min"), 0.0)
            wc_id = self._get_workcenter_by_code(wc_code)

            op_vals = {
                "name": op_name,
                "bom_id": bom_id,
                "workcenter_id": wc_id,
                "sequence": seq,
                # je nach Version: Zeit je Zyklus in Minuten
                "time_cycle": run_min,
                "time_cycle_manual": run_min,
                "time_cycle_setup": setup_min,
            }

            op_id = self.api.create("mrp.bom.operation", op_vals)
            if isinstance(op_id, (list, tuple)) and op_id:
                op_id = op_id[0]

            seq += 1

        info(f"BoM-Operationen für Variante '{variant}' erstellt (BoM-ID {bom_id}).")

    def import_operations(self) -> int:
        rows = self._load_rows()
        by_variant: Dict[str, List[Dict[str, str]]] = {}
        for r in rows:
            variant = (r.get("variant") or "").strip().lower()
            if not variant:
                continue
            by_variant.setdefault(variant, []).append(r)

        count = 0
        for variant, vrows in by_variant.items():
            self._create_operations_for_variant(variant, vrows)
            count += 1

        info(f"BoM-Operations-Import abgeschlossen. Varianten mit Operationen: {count}.")
        return count
