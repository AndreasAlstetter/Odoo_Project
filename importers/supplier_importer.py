# importers/supplier_importer.py
"""
Importer für Lieferantenstammdaten und Lieferanteninformationen.

Dieses Modul liest die Datei aus ``config.LIEF_CSV_PATH`` (z. B.
``lieferanten.csv``) und legt in Odoo sowohl Lieferanten (``res.partner``)
als auch Lieferanteninformationen (``product.supplierinfo``) an.

Erwartetes CSV-Format (ohne Headerzeile):

    0: Produktname              (str, Pflicht)
    1: Lieferantennummer        (str, optional)
    2: Lieferantenname          (str, Pflicht)
    3: Adresse                  (str, optional)
    4: Telefon                  (str, optional)
    5: E-Mail                   (str, optional)
    6: URL / Website            (str, optional)

Hinweis:
- Produkte müssen in Odoo bereits existieren (z. B. über BoM-Importer),
  da Lieferanteninfos an ``product.template`` verknüpft werden.
"""

from __future__ import annotations

from typing import Tuple

import pandas as pd

from config import LIEF_CSV_PATH
from odoo_api import OdooAPI


class SupplierImporter:
    """
    Importiert Lieferanten (``res.partner``) und Lieferanteninfos
    (``product.supplierinfo``) aus einer CSV-Datei.

    Die Klasse ist bewusst einfach gehalten und wird über die Typer-CLI
    in ``cli.py`` angesteuert.
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
        Lädt die Lieferanten-CSV als DataFrame.

        Returns
        -------
        pandas.DataFrame
            Rohdaten aus ``LIEF_CSV_PATH`` ohne Headerzeile.
        """
        df = pd.read_csv(LIEF_CSV_PATH, header=None)
        return df

    def import_suppliers(self) -> Tuple[int, int]:
        """
        Importiert Lieferanten und Lieferanteninformationen aus der CSV.

        Ablauf:
        - Für jede Zeile wird (falls Produkt- und Lieferantenname vorhanden)
          ein Lieferant über ``get_or_create_vendor`` angelegt/gefunden.
        - Anschließend wird versucht, das zugehörige Produkt zu finden und
          eine ``product.supplierinfo``-Zeile anzulegen.

        Returns
        -------
        tuple[int, int]
            Anzahl neu oder aktualisiert angelegter Lieferanten,
            Anzahl angelegter Lieferanteninfos.
        """
        df = self.load_df()

        created_vendors = 0
        created_infos = 0

        for _, row in df.iterrows():
            prodname = str(row[0] or "").strip()
            vendorno = str(row[1] or "").strip()
            vendorname = str(row[2] or "").strip()
            address = str(row[3] or "").strip()
            phone = str(row[4] or "").strip()
            email = str(row[5] or "").strip()
            # URL aktuell nur gelesen, aber nicht verwendet
            url = str(row[6] or "").strip() if len(row) > 6 else ""

            # Minimalanforderung: Produktname und Lieferantenname
            if not prodname or not vendorname:
                continue

            # Lieferant anlegen oder holen
            vendor_id = self.api.get_or_create_vendor(
                name=vendorname,
                email=email,
                phone=phone,
                address=address,
                vendorref=vendorno,
            )

            if vendor_id:
                created_vendors += 1

            # Produkt zur Zuordnung der supplierinfo suchen
            prod = self.api.search_read(
                "product.product",
                [["name", "=", prodname]],
                ["id", "product_tmpl_id"],
                limit=1,
            )
            if not prod:
                # Produkt (noch) nicht angelegt → Lieferanteninfo wird übersprungen
                continue

            tmpl_id = prod[0]["product_tmpl_id"][0]

            vals = {
                "partner_id": vendor_id,
                "product_tmpl_id": tmpl_id,
                "min_qty": 1.0,
                "price": 0.0,
            }

            self.api.create("product.supplierinfo", vals)
            created_infos += 1

        return created_vendors, created_infos
