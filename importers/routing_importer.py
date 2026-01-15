# importers/routing_importer.py
"""
Importer für Operationen je Drohnenvariante auf Basis von routings.csv.

Die CSV-Datei ``data/routings.csv`` definiert pro Variante eine Sequenz
von Operationen mit Zuordnung zu Workcentern und Zeiten.

Spalten:
- variant         : Variantenname (spartan, lightweight, balance)
- operation_seq   : Reihenfolge der Operation (integer)
- operation_name  : Name der Operation
- workcenter_code : Code des Workcenters (muss bereits existieren)
- setup_time_min  : Rüstzeit in Minuten
- run_time_min    : Laufzeit in Minuten
- qty_per_cycle   : Stückzahl pro Zyklus (wird aktuell nur dokumentarisch genutzt)
"""

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
from core.logging_utils import info, warning


class RoutingImporter:
    """Legt Operationen je Drohnenvariante aus einer CSV-Datei an."""

    def __init__(self, api: OdooAPI, csv_path: Path | None = None) -> None:
        """
        Parameters
        ----------
        api:
            Bereits authentifizierte OdooAPI-Instanz.
        csv_path:
            Optionaler Pfad zur Routing-CSV. Standard ist
            ``data/routings.csv``.
        """
        self.api = api
        self.csv_path = csv_path or Path(ROUTING_CSV_PATH)

    # --------------------------------------------------------------------- #
    # CSV-Handling
    # --------------------------------------------------------------------- #

    def _load_rows(self) -> List[Dict[str, str]]:
        """
        Lädt alle Zeilen aus der Routing-CSV.

        Returns
        -------
        list[dict[str, str]]
            Liste von Dicts aus ``csv.DictReader``.

        Raises
        ------
        FileNotFoundError
            Falls die CSV-Datei nicht existiert.
        """
        if not self.csv_path.exists():
            raise FileNotFoundError(f"Routing-CSV nicht gefunden: {self.csv_path}")

        with self.csv_path.open("r", encoding="utf-8") as f:
            reader = csv.DictReader(f)
            return list(reader)

    # --------------------------------------------------------------------- #
    # Hilfsfunktionen für Odoo-Suche
    # --------------------------------------------------------------------- #

    def _product_name_for_variant(self, variant: str) -> str:
        """
        Liefert den Produktnamen (fertige Drohne) für eine Variante.

        Parameters
        ----------
        variant:
            Variantenbezeichnung, z. B. ``"spartan"``.

        Returns
        -------
        str
            Produktname laut ``config`` oder der Variantenstring selbst als Fallback.
        """
        v = (variant or "").lower().strip()
        if v == "spartan":
            return PRODUCT_SPARTAN_NAME
        if v == "lightweight":
            return PRODUCT_LIGHTWEIGHT_NAME
        if v == "balance":
            return PRODUCT_BALANCE_NAME
        # Fallback: Name direkt nutzen
        return variant

    def _find_product_tmpl(self, variant: str) -> int:
        """
        Sucht die product.template-ID für eine Variante.

        Returns
        -------
        int
            ID von ``product.template``.

        Raises
        ------
        RuntimeError
            Falls kein Produkt gefunden wurde.
        """
        name = self._product_name_for_variant(variant)
        res = self.api.search_read(
            "product.product",
            [["name", "=", name]],
            ["product_tmpl_id"],
            limit=1,
        )
        if not res:
            raise RuntimeError(f"Produkt für Variante '{variant}' nicht gefunden ({name})")
        # product_tmpl_id ist [id, name]
        return res[0]["product_tmpl_id"][0]

    def _find_boms_for_variant(self, variant: str) -> List[int]:
        """
        Sucht alle BoMs für die Template der Variante.

        Returns
        -------
        list[int]
            Liste von BoM-IDs (mrp.bom).
        """
        tmpl_id = self._find_product_tmpl(variant)
        res = self.api.search_read(
            "mrp.bom",
            [["product_tmpl_id", "=", tmpl_id]],
            ["id"],
        )
        if not res:
            raise RuntimeError(f"Keine BoM für Variante '{variant}' gefunden (tmpl_id={tmpl_id})")
        return [r["id"] for r in res]

    def _get_workcenter_by_code(self, code: str) -> int:
        """
        Sucht ein Workcenter über seinen Code.

        Raises
        ------
        RuntimeError
            Falls kein Workcenter mit diesem Code vorhanden ist.
        """
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
        """
        Konvertiert einen Wert robust in float.

        Leere Werte oder nicht konvertierbare Inhalte liefern den
        übergebenen Default.
        """
        try:
            if val is None or val == "":
                return default
            f = float(val)
            return f
        except Exception:
            return default

    # --------------------------------------------------------------------- #
    # Operationen an BoMs anlegen
    # --------------------------------------------------------------------- #

    def _create_operations_for_variant(self, variant: str, rows: List[Dict[str, str]]) -> int:
        bom_ids = self._find_boms_for_variant(variant)

        sorted_rows = sorted(
            rows,
            key=lambda r: int((r.get("operation_seq") or "0").strip() or "0"),
        )

        for bom_id in bom_ids:
            # aktuell nur Dokumentation, kein Schreiben in Odoo
            info(f"BoM {bom_id}: geplante Operationen für Variante '{variant}':")
            seq = 1
            for row in sorted_rows:
                op_name = (row.get("operation_name") or "").strip()
                wc_code = (row.get("workcenter_code") or "").strip()
                if not op_name or not wc_code:
                    continue
                setup_min = self._safe_float(row.get("setup_time_min"), 0.0)
                run_min = self._safe_float(row.get("run_time_min"), 0.0)
                info(
                    f"  #{seq:03d} {op_name} @ {wc_code} "
                    f"(setup={setup_min} min, run={run_min} min)"
                )
                seq += 1

        return len(bom_ids)


    # --------------------------------------------------------------------- #
    # Public API
    # --------------------------------------------------------------------- #

    def import_routings(self) -> int:
        """
        Importiert Operationen für alle in der CSV vorkommenden Varianten.

        Returns
        -------
        int
            Anzahl der Varianten, für die Operationen angelegt wurden.
        """
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

        info(f"Routing-/Operations-Import abgeschlossen. Varianten mit Operationen: {count}.")
        return count
