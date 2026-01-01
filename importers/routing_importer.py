# importers/routing_importer.py
"""
Importer für einfache Routings/Operationen je Drohnenvariante.

Wichtiger Hinweis:
- In neueren Odoo-Versionen (z. B. 16+ und 19) existiert das Modell
  ``mrp.routing`` nicht mehr bzw. wurde durch andere Konzepte ersetzt.
- Dieser Importer ist deshalb primär für Instanzen gedacht, in denen
  ``mrp.routing`` und ``mrp.routing.workcenter`` verfügbar sind.

Die CSV-Datei ``data/routings.csv`` definiert pro Variante eine Sequenz
von Operationen mit Zuordnung zu Workcentern und Zeiten.

Erwartete Spalten:

- variant           : Variantenname (spartan, lightweight, balance)
- operation_seq     : Reihenfolge der Operation (integer)
- operation_name    : Name der Operation
- workcenter_code   : Code des Workcenters (muss bereits existieren)
- setup_time_min    : Rüstzeit in Minuten
- run_time_min      : Laufzeit in Minuten
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
)
from core import info


ROUTING_CSV_PATH = Path("data/routings.csv")


class RoutingImporter:
    """Legt einfache Routings/Operationen je Drohnenvariante aus einer CSV-Datei an."""

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
        self.csv_path = csv_path or ROUTING_CSV_PATH

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

    def _product_name_for_variant(self, variant: str) -> str:
        """
        Liefert den Produktnamen (fertige Drohne) für eine Variante.

        Parameters
        ----------
        variant:
            Variantenbezeichnung, z. B. ``\"spartan\"``.

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

    def _create_routing_for_variant(self, variant: str, rows: List[Dict[str, str]]) -> int:
        """
        Legt ein Routing (mrp.routing) und die zugehörigen Operationen
        (mrp.routing.workcenter) für eine Variante an.

        Parameters
        ----------
        variant:
            Variantenbezeichnung, z. B. ``\"spartan\"``.
        rows:
            Alle CSV-Zeilen, die zu dieser Variante gehören.

        Returns
        -------
        int
            ID des erzeugten Routings.
        """
        tmpl_id = self._find_product_tmpl(variant)

        routing_vals = {
            "name": f"Routing {variant.capitalize()}",
            "product_tmpl_id": tmpl_id,
            # optional: weitere Felder je nach Odoo-Version
        }

        routing_id = self.api.create("mrp.routing", routing_vals)

        # Absichern wie bei anderen create-Calls
        if isinstance(routing_id, (list, tuple)):
            if not routing_id:
                raise RuntimeError("Routing-Erstellung hat keine ID geliefert.")
            routing_id = routing_id[0]

        routing_id = int(routing_id)

        # Zeilen nach sequence sortieren
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
                "routing_id": routing_id,
                "workcenter_id": wc_id,
                "sequence": seq,
                # Odoo erwartet Zeit in Minuten je Zyklus
                "time_cycle": run_min,
                "time_cycle_manual": run_min,
                "time_cycle_setup": setup_min,
            }

            op_id = self.api.create("mrp.routing.workcenter", op_vals)
            if isinstance(op_id, (list, tuple)):
                if not op_id:
                    continue
                op_id = op_id[0]

            seq += 1

        info(f"Routing für Variante '{variant}' erstellt (ID {routing_id}).")
        return routing_id

    def import_routings(self) -> int:
        """
        Importiert Routings für alle in der CSV vorkommenden Varianten.

        Returns
        -------
        int
            Anzahl der Varianten, für die ein Routing angelegt wurde.
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
            self._create_routing_for_variant(variant, vrows)
            count += 1

        info(f"Routing-Import abgeschlossen. Varianten mit Routing: {count}.")
        return count
