# importers/product_importer.py
"""
Generischer Importer für Produkte (product.template / product.product).

Aktueller Stand:
- Produkte werden im Projekt primär indirekt über die BoM-Importer
  (``BOMImporter``, ``StructuredBOMImporter``) angelegt.
- Dieses Modul dient als Erweiterungspunkt, um Produkte künftig auch
  direkt aus CSV oder anderen Quellen konsistent zu importieren bzw.
  zu aktualisieren.

Mögliche zukünftige Quellen:
- ``data/products.csv`` mit Stammdaten (Kategorien, Verkaufspreise usw.).
- Abgeleitete Daten aus Kalkulationstabellen (Fertigungskosten, EK/VK).
"""

from __future__ import annotations

from typing import Dict, List

from odoo_api import OdooAPI


class ProductImporter:
    """
    Importiert Produkte aus CSV-Dateien oder aus BoM-Daten.

    Die Implementierung ist bewusst minimal gehalten und kann bei Bedarf
    projektspezifisch erweitert werden, ohne die bestehenden
    BoM-Importer zu verändern.
    """

    def __init__(self, api: OdooAPI) -> None:
        """
        Parameters
        ----------
        api:
            Bereits authentifizierte OdooAPI-Instanz.
        """
        self.api = api

    def import_from_csv(self, filepath: str) -> bool:
        """
        Importiert Produkte aus einer CSV-Datei.

        Aktuell nicht implementiert; vorgesehen für zukünftige Erweiterungen.

        Parameters
        ----------
        filepath:
            Pfad zur CSV-Datei mit Produktstammdaten.

        Returns
        -------
        bool
            Immer ``False``, solange keine Implementierung hinterlegt ist.
        """
        # TODO: Bei Bedarf CSV-Import der Produktstammdaten implementieren.
        return False

    def create_product(self, data: Dict[str, object]) -> int:
        """
        Legt ein einzelnes Produkt in Odoo an.

        Aktuell nur als Interface vorgesehen. Für neue Projekte kann
        diese Methode direkt auf ``OdooAPI.get_or_create_product`` oder
        ``OdooAPI.create`` aufsetzen.

        Parameters
        ----------
        data:
            Dictionary mit den wichtigsten Produktfeldern
            (z. B. ``name``, ``default_code``, ``standard_price``).

        Returns
        -------
        int
            Aktuell immer ``0`` als Platzhalter.
        """
        # TODO: Implementierung an Odoo-Datenmodell anpassen.
        return 0

    def update_from_bom(self, bom_data: List[Dict[str, object]]) -> bool:
        """
        Aktualisiert Produktdaten auf Basis von BoM-Informationen.

        Mögliche Szenarien:
        - Ableitung von Standardkosten aus Komponenten- und Arbeitsplankosten.
        - Setzen von Gewicht/Volumen anhand der Stücklistenkomponenten.

        Aktuell nicht implementiert.

        Parameters
        ----------
        bom_data:
            Liste von Dicts mit BoM-Informationen.

        Returns
        -------
        bool
            Immer ``False``, solange keine Implementierung hinterlegt ist.
        """
        # TODO: Implementierung für kosten-/eigenschaftsbasierte Updates ergänzen.
        return False
