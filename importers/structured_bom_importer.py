# importers/structured_bom_importer.py
"""
Importer für strukturierte Stücklisten aus ``strukturst_ckliste.csv``.

Ziel:
- Eigenfertigungsartikel (Artikelart = "Eigenfertigung") als Produkte anlegen.
- Pro Eigenfertigungsartikel eine eigene Stückliste (mrp.bom) anlegen.
- Komponenten anhand der Gruppen-ID (Spalte "ID Nummer") zuordnen und
  als BoM-Zeilen anlegen.

Unterstützte Varianten:
- spartan
- lightweight
- balance
"""

from __future__ import annotations

import math
from typing import Literal, Any

import pandas as pd

from config import STRUKTUR_CSV_PATH
from odoo_api import OdooAPI
from core.logging_utils import info

VariantName = Literal["spartan", "lightweight", "balance"]

COL = {
    "stufe1": "Stufe_1",
    "stufe2": "Stufe_2",
    "stufe3": "Stufe_3",
    "stufe4": "Stufe_4",
    "idnummer": "ID Nummer",
    "artikelart": "Artikelart",
    "name": "Artikelbezeichnung",
    "sapcode": "Artikel-/SAP-Nummer",
    "qty_spartan": "Menge EVO Spartan",
    "qty_light": "Menge EVO Lightweight",
    "qty_balance": "Menge EVO Balance",
    "price": "Einzelpreiß",
}


class StructuredBOMImporter:
    """
    Importiert strukturierte Stücklisten aus ``strukturst_ckliste.csv``.

    Fokus:
    - Nur Eigenfertigungsartikel (Artikelart = "Eigenfertigung") erhalten
      eigene BoMs.
    - Komponenten werden anhand der ID-Gruppierung (``ID Nummer``) zugeordnet.
    """

    def __init__(self, api: OdooAPI) -> None:
        """
        Parameters
        ----------
        api:
            Bereits authentifizierte OdooAPI-Instanz.
        """
        self.api = api

    def load_df(self) -> pd.DataFrame:
        """
        Lädt die CSV-Datei mit den strukturierten Stücklisten.

        Schritte:
        - Versuch mit Komma als Trennzeichen.
        - Fallback auf Semikolon, falls nur eine Spalte erkannt wird.
        - Log der erkannten Spalten zur Nachvollziehbarkeit.

        Returns
        -------
        pandas.DataFrame
            DataFrame mit allen in ``COL`` referenzierten Spalten.
        """
        df = pd.read_csv(STRUKTUR_CSV_PATH, sep=",")
        if len(df.columns) == 1:
            df = pd.read_csv(STRUKTUR_CSV_PATH, sep=";")

        info(f"Spalten CSV '{STRUKTUR_CSV_PATH}': {df.columns.tolist()}")
        return df

    def variant_qty_col(self, variant: VariantName) -> str:
        """
        Liefert den passenden Mengen-Spaltennamen je Variante.

        Parameters
        ----------
        variant:
            Drohnenvariante: ``\"spartan\"``, ``\"lightweight\"`` oder ``\"balance\"``.

        Returns
        -------
        str
            Name der Spalte mit der Mengenangabe für diese Variante.
        """
        if variant == "spartan":
            return COL["qty_spartan"]
        if variant == "lightweight":
            return COL["qty_light"]
        return COL["qty_balance"]

    @staticmethod
    def _safe_qty(v: Any) -> float | None:
        """
        Konvertiert einen Wert robust in eine Mengenangabe.

        Regeln:
        - Nicht konvertierbare Werte → ``None``.
        - NaN, Inf oder Werte <= 0 → ``None``.

        Returns
        -------
        float | None
            Gültige Menge oder ``None``, wenn die Menge verworfen werden soll.
        """
        try:
            f = float(v)
        except (TypeError, ValueError):
            return None

        if math.isnan(f) or math.isinf(f) or f <= 0.0:
            return None
        return f

    def import_eigenfertigung_boms(self, variant: VariantName) -> None:
        """
        Importiert die BoMs für alle Eigenfertigungsartikel einer Variante.

        Logik:
        - Filtere alle Zeilen mit Artikelart = "Eigenfertigung".
        - Für jede eindeutige ``ID Nummer`` (Gruppen-ID):
          - Produkt für den Eigenfertigungsartikel anlegen/holen.
          - BoM für dieses Produkt anlegen/holen und bestehende BoM-Zeilen löschen.
          - Alle Zeilen, deren ``ID Nummer`` mit der Gruppen-ID beginnt,
            als Komponenten interpretieren und als BoM-Zeilen anlegen.

        Parameters
        ----------
        variant:
            Drohnenvariante: ``\"spartan\"``, ``\"lightweight\"`` oder ``\"balance\"``.
        """
        df = self.load_df()
        qty_col = self.variant_qty_col(variant)

        eigen_df = df[df[COL["artikelart"]] == "Eigenfertigung"]

        for _, row in eigen_df.iterrows():
            name = str(row.get(COL["name"], "") or "").strip()
            sapcode = str(row.get(COL["sapcode"], "") or "").strip()
            price_raw = row.get(COL["price"], 0)

            if not name:
                continue

            # Preis robust konvertieren
            try:
                price_val = float(price_raw)
                if math.isnan(price_val) or math.isinf(price_val):
                    price_val = 0.0
            except (TypeError, ValueError):
                price_val = 0.0

            default_code = sapcode if sapcode else name

            # Eigenfertigungsprodukt anlegen/holen
            product_id = self.api.get_or_create_product(
                default_code=default_code,
                name=name,
                standard_price=price_val,
                product_type=None,  # Standard-Odoo-Typ (stockable) verwenden
            )

            # BoM für dieses Produkt anlegen/holen und bereinigen
            bom_id = self.api.get_or_create_bom(product_id)
            self.api.clear_bom_lines(bom_id)

            # Gruppen-ID (z.B. "1" aus "1.1", "1.2" etc.)
            group_id = str(row.get(COL["idnummer"], "") or "").split(".")[0]
            if not group_id:
                continue

            # Komponenten über ID-Gruppierung finden
            comprows = df[
                df[COL["idnummer"]].astype(str).str.startswith(group_id + ".")
            ]

            for _, crow in comprows.iterrows():
                cname = str(crow.get(COL["name"], "") or "").strip()
                csap = str(crow.get(COL["sapcode"], "") or "").strip()
                cqty_raw = crow.get(qty_col, 0)
                cqty = self._safe_qty(cqty_raw)

                if not cname or cqty is None:
                    continue

                cdefault_code = csap if csap else cname

                cprod_id = self.api.get_or_create_product(
                    default_code=cdefault_code,
                    name=cname,
                    standard_price=0.0,
                    product_type=None,
                )

                self.api.add_bom_line(
                    bom_id=bom_id,
                    product_id=cprod_id,
                    quantity=cqty,
                )
