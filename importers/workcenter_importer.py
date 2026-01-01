# importers/workcenter_importer.py
"""
Importer für Arbeitsplätze (mrp.workcenter) aus einer CSV-Datei.

Die CSV-Datei ``data/workcenters.csv`` definiert die Arbeitsplätze
(Montage, Test, Verpackung usw.), die in den Produktions- und
Routingszenarien verwendet werden.

Erwartete Spalten (Headerzeile in der CSV):

- code           : Kurzcode des Arbeitsplatzes (eindeutig, Pflicht)
- name           : Klartextname des Arbeitsplatzes (Pflicht)
- category       : Optionale Kategorie / Gruppe
- capacity       : Kapazität (z. B. Anzahl paralleler Aufträge)
- cost_per_hour  : Stundensatz für die Kostenrechnung
"""

from __future__ import annotations

from typing import List, Dict

import csv
from pathlib import Path

from odoo_api import OdooAPI
from core import info, warning

from config import WORKCENTER_CSV_PATH


class WorkcenterImporter:
    """Importiert oder aktualisiert ``mrp.workcenter`` aus einer CSV-Datei."""

    def __init__(self, api: OdooAPI, csv_path: Path | None = None) -> None:
        """
        Parameters
        ----------
        api:
            Bereits authentifizierte OdooAPI-Instanz.
        csv_path:
            Optionaler Pfad zur Workcenter-CSV. Standard ist
            ``data/workcenters.csv``.
        """
        self.api = api
        self.csv_path = Path(csv_path or WORKCENTER_CSV_PATH)

    def _load_rows(self) -> List[Dict[str, str]]:
        """
        Lädt alle Zeilen aus der Workcenter-CSV.

        Returns
        -------
        list[dict[str, str]]
            Liste von Dicts, wie sie ``csv.DictReader`` liefert.

        Raises
        ------
        FileNotFoundError
            Falls die CSV-Datei nicht existiert.
        """
        if not self.csv_path.exists():
            raise FileNotFoundError(f"Workcenter-CSV nicht gefunden: {self.csv_path}")

        with self.csv_path.open("r", encoding="utf-8") as f:
            reader = csv.DictReader(f)
            return list(reader)

    def _get_or_create_workcenter(
        self,
        code: str,
        name: str,
        category: str | None,
        capacity: float | None,
        cost_per_hour: float | None,
    ) -> int:
        """
        Sucht ein Workcenter über seinen ``code`` oder legt es neu an.

        Bei bestehendem Datensatz werden die wichtigsten Felder aktualisiert.

        Parameters
        ----------
        code:
            Eindeutiger Kurzcode des Arbeitsplatzes.
        name:
            Klartextname des Arbeitsplatzes.
        category:
            Optionale Kategorie/Gruppe.
        capacity:
            Kapazität (float) oder ``None``.
        cost_per_hour:
            Stundensatz (float) oder ``None``.

        Returns
        -------
        int
            ID des Workcenters.
        """
        domain = [["code", "=", code]]
        existing = self.api.search_read(
            "mrp.workcenter",
            domain,
            ["id"],
            limit=1,
        )

        vals: Dict[str, object] = {
            "name": name,
            "code": code,
        }
        if category is not None:
            # Kategorie nur als Notiz hinterlegen, solange kein eigenes Feld existiert
            vals["note"] = category
            # vals["oee_target"] = 0.0  # Nur setzen, wenn du dieses Feld wirklich brauchst

        # Feld 'capacity' gibt es in deinem mrp.workcenter nicht -> entfernen
        # if capacity is not None:
        #     vals["capacity"] = capacity

        if cost_per_hour is not None:
            vals["costs_hour"] = cost_per_hour


        if existing:
            wc_id = existing[0]["id"]
            self.api.write("mrp.workcenter", wc_id, vals)
            return int(wc_id)

        wc_id = self.api.create("mrp.workcenter", vals)

        # Ergebnis absichern: create kann Liste liefern
        if isinstance(wc_id, (list, tuple)):
            if not wc_id:
                raise RuntimeError("Workcenter-Erstellung hat keine ID geliefert.")
            wc_id = wc_id[0]

        return int(wc_id)

    def import_workcenters(self) -> int:
        """
        Importiert alle in der CSV definierten Arbeitsplätze.

        Ablauf:
        - CSV-Zeilen laden.
        - Zeilen ohne ``code`` oder ``name`` überspringen (mit Warnung).
        - Kapazität und Kosten robust in float umwandeln.
        - Workcenter anlegen oder aktualisieren.

        Returns
        -------
        int
            Anzahl der verarbeiteten (gültigen) Arbeitsplätze.
        """
        rows = self._load_rows()
        count = 0

        def safe_float(val: object | None) -> float | None:
            try:
                if val is None or val == "":
                    return None
                v = float(val)
                return v
            except Exception:
                return None

        for row in rows:
            code = (row.get("code") or "").strip()
            name = (row.get("name") or "").strip()

            if not code or not name:
                warning(f"Ignoriere Zeile ohne Code/Name: {row}")
                continue

            category = (row.get("category") or "").strip() or None
            capacity = safe_float(row.get("capacity"))
            cost_per_hour = safe_float(row.get("cost_per_hour"))

            self._get_or_create_workcenter(
                code=code,
                name=name,
                category=category,
                capacity=capacity,
                cost_per_hour=cost_per_hour,
            )

            count += 1

        info(f"Workcenter-Import abgeschlossen. Verarbeitete Arbeitsplätze: {count}.")
        return count
