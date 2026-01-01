"""
Users and roles importer (CSV-basiert).
"""

from typing import List, Dict
import csv
from pathlib import Path

from odoo_api import OdooAPI
from core import info, warning
from config import USERS_ROLES_CSV_PATH


class UsersRolesImporter:
    """Import users and assign roles/permissions from CSV."""

    def __init__(self, odoo_client: OdooAPI, csv_path: str | None = None) -> None:
        self.client = odoo_client
        self.csv_path = Path(csv_path or USERS_ROLES_CSV_PATH)

    def _find_group(self, full_xml_name: str) -> int | None:
        """
        Sucht eine Gruppe über ihr technisches XML-Name-Feld, z. B.
        'base.group_user' oder 'stock.group_stock_user', über ir.model.data.
        """
        if "." not in full_xml_name:
            warning(f"Ungültiger Gruppen-XML-Name: {full_xml_name}")
            return None

        module, name = full_xml_name.split(".", 1)

        records = self.client.search_read(
            "ir.model.data",
            [["module", "=", module], ["name", "=", name], ["model", "=", "res.groups"]],
            ["res_id"],
            limit=1,
        )
        if not records:
            warning(f"Gruppe '{full_xml_name}' nicht über ir.model.data gefunden.")
            return None

        return records[0]["res_id"]


    def create_user(
        self,
        login: str,
        name: str,
        email: str,
        password: str,
    ) -> int:
        existing = self.client.search_read(
            "res.users",
            [["login", "=", login]],
            ["id"],
            limit=1,
        )
        vals: Dict[str, object] = {
            "name": name,
            "login": login,
            "email": email,
        }
        if existing:
            user_id = existing[0]["id"]
            self.client.write("res.users", user_id, vals)
            info(f"Benutzer '{login}' aktualisiert (ID {user_id}).")
            return int(user_id)

        vals["password"] = password or "demo"
        user_id = self.client.create("res.users", vals)
        if isinstance(user_id, (list, tuple)):
            user_id = user_id[0]
        info(f"Benutzer '{login}' angelegt (ID {user_id}).")
        return int(user_id)

    def assign_group(self, user_id: int, full_xml_name: str) -> None:
        """
        Platzhalter: In Odoo 19-Instanz ist das Feld 'groups_id' auf res.users
        nicht verfügbar. Gruppen werden aktuell nicht automatisch zugewiesen.
        """
        warning(
            f"Gruppen-Zuweisung für Benutzer {user_id} "
            f"({full_xml_name}) wird in dieser Odoo-Version übersprungen."
        )
        return


    def import_from_csv(self) -> int:
        if not self.csv_path.exists():
            raise FileNotFoundError(f"Users/Roles-CSV nicht gefunden: {self.csv_path}")

        with self.csv_path.open("r", encoding="utf-8") as f:
            reader = csv.DictReader(f)
            rows = list(reader)

        count = 0
        for row in rows:
            login = (row.get("login") or "").strip()
            name = (row.get("name") or "").strip()
            email = (row.get("email") or "").strip()
            password = (row.get("password") or "").strip()

            if not login or not name:
                warning(f"Ignoriere Zeile ohne login/name: {row}")
                continue

            user_id = self.create_user(login, name, email, password)

            groups_str = (row.get("groups") or "").strip()
            if groups_str:
                for grp in groups_str.split(";"):
                    grp = grp.strip()
                    if grp:
                        self.assign_group(user_id, grp)

            count += 1

        info(f"Benutzer-/Rollen-Import abgeschlossen. Verarbeitete Benutzer: {count}.")
        return count
