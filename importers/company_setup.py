# importers/company_setup.py
"""
Setup-Helfer für Firmendaten, Sprache, Währung und Modulinstallation.

Das Drohnen-Projekt nutzt typischerweise eine bereits konfigurierte
Datenbank, aber dieses Modul ermöglicht ein teil-automatisiertes Setup
für Test- oder Demo-Instanzen.
"""

from __future__ import annotations

from typing import Any

from odoo_api import OdooAPI
from core import info, warning


class CompanySetup:
    """Richtet eine Firma ein und nimmt Basis-Konfigurationen vor."""

    def __init__(self, api: OdooAPI) -> None:
        """
        Parameters
        ----------
        api:
            Authentifizierte OdooAPI-Instanz.
        """
        self.api = api

    def create_company(self, name: str, country_code: str, currency_code: str) -> int:
        """
        Legt eine Firma in Odoo an, falls noch keine mit diesem Namen existiert.

        Returns
        -------
        int
            ID der bestehenden oder neu erzeugten Firma.
        """
        existing = self.api.search_read(
            "res.company", [["name", "=", name]], ["id"], limit=1
        )
        if existing:
            company_id = existing[0]["id"]
            info(f"Firma '{name}' existiert bereits (ID {company_id}).")
            return company_id

        vals: dict[str, Any] = {"name": name}

        # Land zuordnen, falls vorhanden
        if country_code:
            country = self.api.search_read(
                "res.country",
                [["code", "=", country_code.upper()]],
                ["id"],
                limit=1,
            )
            if country:
                vals["country_id"] = country[0]["id"]

        company_id = self.api.create("res.company", vals)
        if isinstance(company_id, (list, tuple)):
            company_id = company_id[0]
        company_id = int(company_id)

        info(f"Firma '{name}' angelegt (ID {company_id}).")

        # Währung setzen, falls möglich
        if currency_code:
            self.set_currency(currency_code, company_id=company_id)

        return company_id

    def set_language(self, language_code: str) -> bool:
        """
        Aktiviert eine Sprache, falls sie in Odoo vorhanden ist.

        Hinweis:
        - Das reine Aktivieren einer Sprache reicht, um sie in der UI
          nutzen zu können; eine globale „Defaultsprache“ ist in Odoo
          eher Benutzer-/Kontextabhängig.
        """
        lang_code = language_code.replace("_", "-")
        langs = self.api.search_read(
            "res.lang",
            [["code", "=", lang_code]],
            ["id", "active"],
            limit=1,
        )
        if not langs:
            warning(f"Sprache '{lang_code}' nicht gefunden.")
            return False

        lang = langs[0]
        if not lang.get("active", False):
            self.api.write("res.lang", lang["id"], {"active": True})
            info(f"Sprache '{lang_code}' aktiviert.")
        else:
            info(f"Sprache '{lang_code}' ist bereits aktiv.")
        return True

    def set_currency(self, currency_code: str, company_id: int | None = None) -> bool:
        """
        Setzt die Standardwährung für eine Firma, falls möglich.

        Parameters
        ----------
        currency_code:
            ISO-Währungscode, z. B. EUR, USD.
        company_id:
            ID der Firma; wenn None, wird die aktuelle Benutzerfirma verwendet.
        """
        curr = self.api.search_read(
            "res.currency",
            [["name", "=", currency_code.upper()]],
            ["id"],
            limit=1,
        )
        if not curr:
            warning(f"Währung '{currency_code}' nicht gefunden.")
            return False

        currency_id = curr[0]["id"]

        if company_id is None:
            # aktuelle Firma des Benutzers bestimmen
            user = self.api.search_read("res.users", [["id", "=", self.api.uid]], ["company_id"], limit=1)
            if not user:
                warning("Aktueller Benutzer hat keine Firma.")
                return False
            company_id = user[0]["company_id"][0]

        self.api.write("res.company", company_id, {"currency_id": currency_id})
        info(f"Währung für Firma {company_id} auf {currency_code} gesetzt.")
        return True

    def install_modules(self, module_names: list[str]) -> bool:
        """
        Markiert Module zur Installation über ``ir.module.module``.

        Achtung:
        - Die eigentliche Installation erfolgt in Odoo über den Update-Mechanismus
          und nicht direkt per JSON-RPC. Dieses Hilfsmodul setzt nur den State.
        """
        ok = True
        for mod in module_names:
            recs = self.api.search_read(
                "ir.module.module",
                [["name", "=", mod]],
                ["id", "state"],
                limit=1,
            )
            if not recs:
                warning(f"Modul '{mod}' nicht gefunden.")
                ok = False
                continue

            rec = recs[0]
            if rec["state"] in ("installed", "to install", "to upgrade"):
                info(f"Modul '{mod}' ist bereits im Installationsfluss ({rec['state']}).")
                continue

            self.api.write("ir.module.module", rec["id"], {"state": "to install"})
            info(f"Modul '{mod}' zur Installation markiert.")
        return ok

    def run_setup(self, config: dict[str, Any]) -> bool:
        """
        Führt einen einfachen Setup-Lauf anhand einer Konfiguration durch.

        Erwartete Keys in ``config`` (alle optional):
        - company_name
        - country_code
        - currency_code
        - language_code
        - modules (Liste von Modulnamen)
        """
        company_id: int | None = None

        if name := config.get("company_name"):
            company_id = self.create_company(
                name=name,
                country_code=config.get("country_code", ""),
                currency_code=config.get("currency_code", ""),
            )

        if lang := config.get("language_code"):
            self.set_language(lang)

        if not company_id and (curr := config.get("currency_code")):
            self.set_currency(curr)

        modules = config.get("modules") or []
        if modules:
            self.install_modules(modules)

        info("Basis-Setup abgeschlossen.")
        return True
