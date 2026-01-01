# importers/location_importer.py
"""
Importer für zentrale Lagerorte (stock.location).

Dieses Modul sorgt dafür, dass in Odoo eine minimal benötigte
Lagerstruktur existiert, die von den weiteren Prozessen verwendet wird:

- WH/Stock       – Hauptlager
- WH/IN          – Wareneingang
- WH/Production  – Produktionslager
- WH/Output      – Warenausgang / Versand

Falls bereits ein Warehouse mit Lagerort vorhanden ist, wird dieses
weiterverwendet; andernfalls werden die Basis-Lagerorte neu angelegt.
"""

from __future__ import annotations

from odoo_api import OdooAPI
from core.logging_utils import info, success


class LocationImporter:
    """
    Stellt zentrale Lagerorte bereit, die von Importern und Prozessflows
    (z. B. Wareneingang, Fertigung, Versand) genutzt werden.
    """

    def __init__(self, api: OdooAPI) -> None:
        """
        Parameters
        ----------
        api:
            Bereits authentifizierte OdooAPI-Instanz.
        """
        self.api = api

    def _get_or_create_location(
        self,
        complete_name: str,
        name: str,
        usage: str = "internal",
        parent_location_id: int | None = None,
    ) -> int:
        """
        Sucht einen Lagerort über ``complete_name`` oder legt ihn neu an.

        Parameters
        ----------
        complete_name:
            Vollständiger Pfadname des Lagerorts (z. B. ``"WH/Stock"``).
        name:
            Kurzname des Lagerorts (z. B. ``"Stock"``).
        usage:
            Verwendungsart des Lagerorts (z. B. ``"internal"``).
        parent_location_id:
            ID des übergeordneten Lagerorts oder ``None``.

        Returns
        -------
        int
            ID des gefundenen oder neu erzeugten Lagerorts.
        """
        existing = self.api.search_read(
            "stock.location",
            [["complete_name", "=", complete_name]],
            ["id"],
            limit=1,
        )
        if existing:
            return existing[0]["id"]

        vals: dict[str, object] = {
            "name": name,
            "usage": usage,
        }
        if parent_location_id:
            vals["location_id"] = parent_location_id

        loc_id = self.api.create("stock.location", vals)
        return loc_id

    def setup_core_locations(self) -> None:
        """
        Stellt die zentrale Lagerstruktur bereit.

        Ablauf:
        - Prüft, ob bereits ein Warehouse existiert und dessen Hauptlager
          (``lot_stock_id``) verwendet werden kann.
        - Falls kein Warehouse vorhanden ist, wird ein Basislagerort
          ``WH`` als Wurzel angelegt.
        - Darunter werden die zentralen Unterlager angelegt:
          - ``WH/Stock``, ``WH/IN``, ``WH/Production``, ``WH/Output``.
        """
        info("Stelle zentrale Lagerorte bereit...")

        wh = self.api.search_read(
            "stock.warehouse",
            [],
            ["id", "lot_stock_id"],
            limit=1,
        )

        if wh:
            stock_location_id = wh[0]["lot_stock_id"][0]
        else:
            stock_location_id = self._get_or_create_location(
                complete_name="WH",
                name="WH",
                usage="internal",
            )

        self._get_or_create_location("WH/Stock", "Stock", "internal", stock_location_id)
        self._get_or_create_location("WH/IN", "IN", "internal", stock_location_id)
        self._get_or_create_location(
            "WH/Production", "Production", "internal", stock_location_id
        )
        self._get_or_create_location("WH/Output", "Output", "internal", stock_location_id)

        success("Zentrale Lagerorte sind vorhanden.")
