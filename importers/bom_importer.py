# importers/bom_importer.py
"""
Importer für Mengenstücklisten (einfache BoMs) aus ``mengenst_ckliste.csv``.

- Legt Komponentenprodukte als ``product.product`` an bzw. aktualisiert sie.
- Legt oder aktualisiert eine Stückliste (``mrp.bom``) für die jeweilige
  Drohnenvariante (Spartan, Lightweight, Balance).

Die CSV basiert auf der vorhandenen Simulation und den Kalkulationsdaten
des Drohnenprojekts.
"""

from __future__ import annotations

import math
from typing import Literal

import pandas as pd

from config import (
    MENGE_CSV_PATH,
    PRODUCT_SPARTAN_NAME,
    PRODUCT_LIGHTWEIGHT_NAME,
    PRODUCT_BALANCE_NAME,
)
from odoo_api import OdooAPI
from core.validation import validate_required_columns
from core.logging_utils import info

VariantName = Literal["spartan", "lightweight", "balance"]

# Abbildung der CSV-Spaltennamen
COLUMN_MAP = {
    "articletype": "Artikelart",
    "name": "Artikelbezeichnung",
    "sapcode": "Artikel-/SAP-Nummer",
    "price": "Einzelpreiß",
    "qty_spartan": "Menge EVO Spartan",
    "qty_lightweight": "Menge EVO Lightweight",
    "qty_balance": "Menge EVO Balance",
}


class BOMImporter:
    """
    Importiert Mengenstücklisten (einfache BoMs) aus ``mengenst_ckliste.csv``.

    Der Importer arbeitet variantenbezogen; pro Aufruf wird genau eine
    Drohnenvariante (spartan, lightweight oder balance) verarbeitet.
    """

    def __init__(self, api: OdooAPI) -> None:
        """
        Parameters
        ----------
        api:
            Bereits authentifizierte OdooAPI-Instanz.
        """
        self.api = api

    def load_dataframe(self) -> pd.DataFrame:
        """
        Lädt die CSV mit den Mengenstücklisten und prüft Pflichtspalten.

        Schritte:
        - Einlesen der Datei mit Komma als Trennzeichen.
        - Fallback auf Semikolon, falls nur eine Spalte erkannt wurde.
        - Prüfung der Pflichtspalten (Artikelart, Artikelbezeichnung).
        - Entfernen von Zeilen mit fehlenden Pflichtwerten.

        Returns
        -------
        pandas.DataFrame
            Bereinigter DataFrame mit allen relevanten Spalten.
        """
        # 1) Trennzeichen initial: Komma
        df = pd.read_csv(MENGE_CSV_PATH, sep=",")

        # 2) Fallback auf Semikolon, falls nur eine Spalte erkannt wurde
        if len(df.columns) == 1:
            df = pd.read_csv(MENGE_CSV_PATH, sep=";")

        # 3) Pflichtspalten prüfen
        required_cols = [
            COLUMN_MAP["articletype"],
            COLUMN_MAP["name"],
        ]
        validate_required_columns(df, required_cols, context=MENGE_CSV_PATH)

        info(f"Spalten CSV '{MENGE_CSV_PATH}': {df.columns.tolist()}")

        # 4) Zeilen mit fehlenden Pflichtfeldern verwerfen
        df = df.dropna(subset=required_cols, how="any")
        return df

    def variant_column(self, variant: VariantName) -> str:
        """
        Liefert die Mengen-Spalte für die angegebene Variante.

        Parameters
        ----------
        variant:
            Drohnenvariante: ``\"spartan\"``, ``\"lightweight\"`` oder ``\"balance\"``.

        Returns
        -------
        str
            Name der Spalte mit der Stücklistenmenge für diese Variante.
        """
        if variant == "spartan":
            return COLUMN_MAP["qty_spartan"]
        if variant == "lightweight":
            return COLUMN_MAP["qty_lightweight"]
        return COLUMN_MAP["qty_balance"]

    def variant_product_name(self, variant: VariantName) -> str:
        """
        Liefert den fertigen Produktnamen der Drohnenvariante aus ``config``.

        Parameters
        ----------
        variant:
            Drohnenvariante: ``\"spartan\"``, ``\"lightweight\"`` oder ``\"balance\"``.

        Returns
        -------
        str
            Produktname des fertigen Drohnenartikels in Odoo.
        """
        if variant == "spartan":
            return PRODUCT_SPARTAN_NAME
        if variant == "lightweight":
            return PRODUCT_LIGHTWEIGHT_NAME
        return PRODUCT_BALANCE_NAME

    def import_variant(self, variant: VariantName) -> None:
        """
        Importiert die Mengenstückliste für eine bestimmte Drohnenvariante.

        Ablauf:
        - Fertigprodukt (Drohnentyp) holen oder erzeugen.
        - Stückliste (BoM) für dieses Produkt holen oder erzeugen.
        - Bestehende BoM-Zeilen löschen.
        - Für jede Zeile in der CSV:
          - Komponentenprodukt anlegen/aktualisieren.
          - BoM-Zeile mit der jeweiligen Menge anlegen.

        Parameters
        ----------
        variant:
            Drohnenvariante: ``\"spartan\"``, ``\"lightweight\"`` oder ``\"balance\"``.
        """
        df = self.load_dataframe()
        qty_col = self.variant_column(variant)
        finished_name = self.variant_product_name(variant)

        # Fertigprodukt und zugehörige BoM
        finished_id = self.api.get_or_create_finished_product(finished_name)
        bom_id = self.api.get_or_create_bom(finished_id)
        self.api.clear_bom_lines(bom_id)

        # Komponenten aus CSV verarbeiten
        for _, row in df.iterrows():
            sapcode = str(row.get(COLUMN_MAP["sapcode"], "") or "").strip()
            name = str(row.get(COLUMN_MAP["name"], "") or "").strip()
            articletype = str(row.get(COLUMN_MAP["articletype"], "") or "").strip()
            qty_raw = row.get(qty_col, 0)
            price_raw = row.get(COLUMN_MAP["price"], 0)

            # Menge validieren
            try:
                qty_val = float(qty_raw)
            except (TypeError, ValueError):
                continue
            if math.isnan(qty_val) or math.isinf(qty_val) or qty_val == 0:
                continue

            # Preis robust in float wandeln
            try:
                price_val = float(price_raw)
                if math.isnan(price_val) or math.isinf(price_val):
                    price_val = 0.0
            except (TypeError, ValueError):
                price_val = 0.0

            if not name:
                # Ohne Bezeichnung kein sinnvolles Produkt
                continue

            default_code = sapcode if sapcode and sapcode.lower() != "nan" else name

            # Dienstleistungs-Artikel als service markieren
            ptype = None
            if "Dienstleistung" in articletype:
                ptype = "service"

            product_id = self.api.get_or_create_product(
                default_code=default_code,
                name=name,
                standard_price=price_val,
                product_type=ptype,
            )

            self.api.add_bom_line(
                bom_id=bom_id,
                product_id=product_id,
                quantity=qty_val,
            )
