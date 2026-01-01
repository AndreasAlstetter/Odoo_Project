# importers/qc_importer.py
"""
Importer für Qualitätskontrollpunkte (Quality Control Points).

Modellbezug:
- In neueren Odoo-Versionen werden QC-Punkte üblicherweise über
  ``quality.point`` abgebildet (Modul *quality* / *quality_control*).

Die konkrete Feldbelegung kann je nach Installation leicht variieren;
hier wird eine einfache, generische Anlage umgesetzt.
"""

from __future__ import annotations

from typing import Dict

from odoo_api import OdooAPI
from core import info, warning


class QCImporter:
    """Importiert Qualitätskontrollpunkte und -prüfungen aus CSV oder Datenstrukturen."""

    def __init__(self, api: OdooAPI) -> None:
        self.api = api

    def create_qc_point(
        self,
        product_id: int,
        stage: str,
        control_type: str,
        criteria: str,
    ) -> int:
        """
        Legt einen QC-Kontrollpunkt (quality.point) in Odoo an.

        Parameters
        ----------
        product_id:
            ID des Produkts (product.product oder product.template, je nach Modul).
        stage:
            Prozessstufe, z. B. \"Wareneingang\", \"Montage\", \"Endtest\".
        control_type:
            Art der Kontrolle (z. B. \"pass_fail\", \"measure\").
        criteria:
            Beschreibung der Prüfkriterien.

        Returns
        -------
        int
            ID des QC-Kontrollpunkts.
        """
        vals: Dict[str, object] = {
            "name": f"{stage}: {criteria}",
            "product_id": product_id,
            "picking_type_id": False,
            "team_id": False,
            "type": control_type,
            "note": criteria,
        }
        qc_id = self.api.create("quality.point", vals)
        if isinstance(qc_id, (list, tuple)):
            qc_id = qc_id[0]
        qc_id = int(qc_id)
        info(f"QC-Point '{stage}: {criteria}' angelegt (ID {qc_id}).")
        return qc_id

    def import_from_csv(self, filepath: str) -> bool:
        """
        Importiert Qualitätskontrollpunkte aus einer CSV-Datei.

        Erwartete Spalten:
        - product_name
        - stage
        - control_type
        - criteria
        """
        import csv

        with open(filepath, "r", encoding="utf-8") as f:
            reader = csv.DictReader(f)
            for row in reader:
                product_name = (row.get("product_name") or "").strip()
                stage = (row.get("stage") or "").strip()
                control_type = (row.get("control_type") or "").strip() or "pass_fail"
                criteria = (row.get("criteria") or "").strip()

                if not product_name or not stage or not criteria:
                    warning(f"Ignoriere unvollständige QC-Zeile: {row}")
                    continue

                prod = self.api.search_read(
                    "product.product",
                    [["name", "=", product_name]],
                    ["id"],
                    limit=1,
                )
                if not prod:
                    warning(f"Produkt für QC nicht gefunden: '{product_name}'")
                    continue

                self.create_qc_point(prod[0]["id"], stage, control_type, criteria)

        info(f"QC-Import aus {filepath} abgeschlossen.")
        return True
