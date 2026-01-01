# importers/stock_importer.py
"""
Importer für Startlagerbestände aus ``lagerdaten.csv``.

Funktion:
- Liest die CSV-Datei mit Beständen aus.
- Sucht zugehörige Produkte anhand ihres ``default_code``.
- Erzeugt für jeden Bestand einen UMH-Stock-Event (ohne echte Odoo-Buchung).
- Schreibt alle Events in die Datei ``umh_stock_events.json``.

Hinweis:
- Es werden keine physischen Bestandsbuchungen in Odoo ausgeführt.
- Die Bestände dienen als initialer Zustand für den Digital Twin über UMH.
"""

from __future__ import annotations

import math
from typing import List, Dict

import pandas as pd

from config import LAGER_CSV_PATH
from odoo_api import OdooAPI
from integration.umh_events import UMHEventManager
from integration.umh_client_sim import UMHClientSimulator
from core import info, warning


class StockImporter:
    """
    Importiert Lagerbestände aus ``lagerdaten.csv`` und erzeugt entsprechende
    UMH-Stock-Events.
    """

    def __init__(self, api: OdooAPI) -> None:
        """
        Parameters
        ----------
        api:
            Authentifizierte OdooAPI-Instanz (aktuell nur für Produktsuche genutzt).
        """
        self.api = api
        self.umh_manager = UMHEventManager()
        self.umh_client = UMHClientSimulator(output_file="umh_stock_events.json")

    def _load_df(self) -> pd.DataFrame:
        """
        Lädt die Lager-CSV in einen DataFrame.

        Erwartete Spalten (mindestens):
        - ``__empty___2`` : Artikelnummer / default_code
        - ``Bestand Regal`` : menge im Regal
        """
        df = pd.read_csv(LAGER_CSV_PATH, sep=",")
        info(f"Spalten CSV '{LAGER_CSV_PATH}': {df.columns.tolist()}")
        return df

    def import_quantities(self, default_location_id: int = 1) -> int:
        """
        Erzeugt UMH-Stock-Events für alle Bestände aus der CSV.

        Parameters
        ----------
        default_location_id:
            Lagerort-ID in Odoo, die im Event als Standort verwendet wird.

        Returns
        -------
        int
            Anzahl der erzeugten Stock-Events.
        """
        df = self._load_df()
        event_count = 0

        for _, row in df.iterrows():
            code = str(row.get("__empty___2", "") or "").strip()
            qty_raw = row.get("Bestand Regal", 0)

            try:
                qty = float(qty_raw)
            except (TypeError, ValueError):
                continue

            if math.isnan(qty) or math.isinf(qty) or qty == 0:
                continue
            if not code:
                continue

            prod = self.api.search_read(
                "product.product",
                [["default_code", "=", code]],
                ["id"],
                limit=1,
            )
            if not prod:
                warning(f"Kein Produkt mit default_code='{code}' gefunden, Bestand wird ignoriert.")
                continue

            prod_id = prod[0]["id"]

            # UMH-Stock-Event für die Bestandszuweisung erzeugen
            stock_evt = self.umh_manager.create_stock_event(
                product_id=prod_id,
                location_id=default_location_id,
                qty_change=qty,
            )
            self.umh_manager.queue_event(stock_evt)
            event_count += 1

        # Alle bisher gesammelten Events in eine Datei schreiben
        events_dicts: List[Dict] = [e.to_dict() for e in self.umh_manager.get_pending_events()]
        if events_dicts:
            self.umh_client.send_events_batch(events_dicts)
            self.umh_client.export_to_file()
            self.umh_client.clear_events()
            self.umh_manager.clear_events()
            info(f"Lagerbestände erfolgreich importiert. Erzeugte Stock-Events: {event_count}.")
        else:
            warning("Keine Stock-Events erzeugt (evtl. leere oder ungeeignete CSV).")

        return event_count
