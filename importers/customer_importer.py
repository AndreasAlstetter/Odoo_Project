# importers/customer_importer.py

from __future__ import annotations

import csv
from pathlib import Path
from typing import Dict, List

from odoo_api import OdooAPI
from core import info, warning
from config import CUSTOMERS_CSV_PATH


class CustomerImporter:
    """Importiert Kundenstammdaten aus einer CSV-Datei."""

    def __init__(self, api: OdooAPI, csv_path: str | None = None) -> None:
        """
        Initialisiert the CustomerImporter with an OdooAPI instance and
        optionally a path to a customer CSV file.

        Args:
            api (OdooAPI): The OdooAPI instance to use for importing customers.
            csv_path (str | None, optional): The path to the customer CSV file.
                Defaults to None.
        """
        self.api = api
        self.csv_path = Path(csv_path or CUSTOMERS_CSV_PATH)

    def _load_rows(self) -> List[Dict[str, str]]:
        """
        Lädt eine Liste von Dictionarys aus der Kunden-CSV-Datei ein.

        Raises:
            FileNotFoundError: Wenn die Kunden-CSV-Datei nicht gefunden werden kann.
        """
        if not self.csv_path.exists():
            raise FileNotFoundError(f"Kunden-CSV nicht gefunden: {self.csv_path}")

        with self.csv_path.open("r", encoding="utf-8") as f:
            reader = csv.DictReader(f)
            return list(reader)

    def _get_or_create_country(self, code: str) -> int | None:
        """
        Sucht nach einem Land mit dem gegebenen Code und gibt die ID zurück.
        Wenn das Land nicht gefunden wird, wird eine Warnung ausgegeben und None zurückgegeben.
        """
        code = (code or "").strip().upper()
        if not code:
            return None
        countries = self.api.search_read(
            "res.country",
            [["code", "=", code]],
            ["id"],
            limit=1,
        )
        if countries:
            return countries[0]["id"]
        warning(f"Land mit Code '{code}' nicht gefunden.")
        return None

    def _get_or_create_customer(self, vals: Dict[str, object]) -> int:
        """
        Sucht nach einem Kunden mit dem gegebenen Namen und gibt die ID zurück.
        Wenn der Kunde nicht gefunden wird, wird ein neuer Kunde mit den gegebenen
        Werten angelegt und die ID zurückgegeben.
        """

        name = vals.get("name") or ""
        existing = self.api.search_read(
            "res.partner",
            [["name", "=", name], ["customer_rank", ">", 0]],
            ["id"],
            limit=1,
        )
        if existing:
            partner_id = existing[0]["id"]
            self.api.write("res.partner", partner_id, vals)
            return int(partner_id)

        partner_id = self.api.create("res.partner", vals)
        if isinstance(partner_id, (list, tuple)):
            partner_id = partner_id[0]
        return int(partner_id)

    def import_customers(self) -> int:
        """
        Importiert Kunden aus einer CSV-Datei und legt sie im System an.

        Die CSV-Datei muss die folgenden Spalten haben:
        - name: Der Name des Kunden
        - street: Die Strae des Kunden
        - zip: Die Postleitzahl des Kunden
        - city: Die Stadt des Kunden
        - country: Der Ländercode des Kunden
        - email: Die E-Mail-Adresse des Kunden
        - phone: Die Telefonnummer des Kunden
        - vat: Die Mehrwertsteuer-Nummer des Kunden
        - is_company: Ein Boolean-Wert, der angibt, ob es sich um eine Firma oder eine Privatperson handelt

        Gibt die Anzahl der erfolgreich importierten Kunden zurück.
        """
        rows = self._load_rows()
        count = 0

        for row in rows:
            name = (row.get("name") or "").strip()
            if not name:
                warning(f"Ignoriere Zeile ohne Kundenname: {row}")
                continue

            street = (row.get("street") or "").strip()
            zip_code = (row.get("zip") or "").strip()
            city = (row.get("city") or "").strip()
            country_code = (row.get("country") or "").strip()
            email = (row.get("email") or "").strip()
            phone = (row.get("phone") or "").strip()
            vat = (row.get("vat") or "").strip()
            is_company_raw = (row.get("is_company") or "").strip()

            is_company = is_company_raw in ("1", "true", "True", "ja", "JA")

            vals: Dict[str, object] = {
                "name": name,
                "street": street or False,
                "zip": zip_code or False,
                "city": city or False,
                "email": email or False,
                "phone": phone or False,
                "vat": vat or False,
                "customer_rank": 1,
                "company_type": "company" if is_company else "person",
            }

            country_id = self._get_or_create_country(country_code)
            if country_id:
                vals["country_id"] = country_id

            self._get_or_create_customer(vals)
            count += 1

        info(f"Kundenimport abgeschlossen. Verarbeitete Kunden: {count}.")
        return count
