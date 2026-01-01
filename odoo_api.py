# odoo_api.py
"""
Low-Level Odoo-API-Client für das Odoo-Drohnen-Projekt.

Dieses Modul kapselt den Zugriff auf die Odoo-JSON-RPC-API und stellt eine
Hilfsklasse bereit:

- Login und Session-Verwaltung über JSON-RPC (common.login)
- Generischer Wrapper für object.execute_kw (call_kw)
- Komfort-Methoden für search_read, read, create, write
- Fachliche Helper:
  - Lieferanten-Handling (get_or_create_vendor)
  - Produkt-Handling (get_or_create_product, get_or_create_finished_product)
  - BoM-Handling (get_or_create_bom, add_bom_line, clear_bom_lines)

Die Klasse OdooAPI wird von Importern und Prozess-Flows genutzt, um
Daten in Odoo anzulegen, zu lesen oder zu aktualisieren.
"""

import math
from typing import Any, Dict, List, Sequence, Union

import requests

from config import ODOO_URL, DB_NAME, LOGIN, API_KEY


JsonId = Union[int, str]
IdLike = Union[int, Sequence[int]]


class OdooAPI:
    """
    Zentrale Infrastrukturklasse für Odoo-JSON-RPC-Zugriffe.

    Verantwortlichkeiten:
    - Aufbau der HTTP-Session und Login gegen Odoo (common.login)
    - Generische JSON-RPC-Aufrufe über _json_rpc und call_kw
    - Standardoperationen:
      - search_read: Datensätze finden und Felder lesen
      - read: Datensätze nach ID lesen
      - create: Datensätze anlegen
      - write: Datensätze aktualisieren
    - Fach-Helper für:
      - Lieferanten (res.partner, supplier_rank > 0)
      - Produkte (product.product inkl. sicherem Preis-Handling)
      - Stücklisten (mrp.bom, mrp.bom.line) mit Robustheit für Many2one-/Listen-Rückgaben

    Die Instanz wird in CLI-Kommandos, Importern und Prozess-Flows wiederverwendet,
    um konsistente Odoo-Zugriffe im gesamten Projekt sicherzustellen.
    """

    def __init__(self) -> None:
        self.url = ODOO_URL.rstrip("/")
        self.session = requests.Session()
        self.session.headers.update({"Content-Type": "application/json"})
        self.uid = self._login()  # Login direkt beim Erzeugen

    # ---------------------------------------------------------
    # Basis-JSON-RPC / Auth
    # ---------------------------------------------------------

    def _login(self) -> int:
        """
        Führt den Login gegen Odoo durch und gibt die User-ID zurück.
        """
        payload: Dict[str, Any] = {
            "jsonrpc": "2.0",
            "method": "call",
            "params": {
                "service": "common",
                "method": "login",
                "args": [DB_NAME, LOGIN, API_KEY],
            },
            "id": 1,
        }

        resp = self.session.post(f"{self.url}/jsonrpc", json=payload)
        resp.raise_for_status()
        res = resp.json()

        if "error" in res:
            raise Exception(res["error"])

        uid = res.get("result")
        if not uid:
            raise RuntimeError("Login fehlgeschlagen")

        return int(uid)

    def _json_rpc(self, service: str, method: str, args: list) -> Any:
        """
        Führt einen generischen JSON-RPC-Call auf dem angegebenen Service aus.
        """
        payload: Dict[str, Any] = {
            "jsonrpc": "2.0",
            "method": "call",
            "params": {
                "service": service,
                "method": method,
                "args": args,
            },
            "id": 1,
        }

        resp = self.session.post(f"{self.url}/jsonrpc", json=payload)
        resp.raise_for_status()
        res = resp.json()

        if "error" in res:
            raise Exception(res["error"])

        return res.get("result")

    def call_kw(
        self,
        model: str,
        method: str,
        args: list,
        kwargs: Dict[str, Any] | None = None,
    ) -> Any:
        """
        Wrapper für object.execute_kw.
        """
        if kwargs is None:
            kwargs = {}

        return self._json_rpc(
            "object",
            "execute_kw",
            [DB_NAME, self.uid, API_KEY, model, method, args, kwargs],
        )

    # ---------------------------------------------------------
    # Hilfsfunktionen: search_read, read, create, write
    # ---------------------------------------------------------

    def search_read(
        self,
        model: str,
        domain: List[Any],
        fields: List[str],
        limit: int = 100,
    ) -> List[Dict[str, Any]]:
        """
        Führt einen search_read auf dem angegebenen Modell aus.
        """
        return self.call_kw(
            model,
            "search_read",
            [domain],
            {"fields": fields, "limit": limit},
        )

    def read(
        self,
        model: str,
        ids: List[int],
        fields: List[str] | None = None,
    ) -> List[Dict[str, Any]]:
        """
        Wrapper für 'read' auf einem beliebigen Modell.
        """
        kwargs: Dict[str, Any] = {}
        if fields is not None:
            kwargs["fields"] = fields
        return self.call_kw(model, "read", [ids], kwargs)

    def create(self, model: str, vals: Dict[str, Any]) -> int:
        """
        Legt einen Datensatz im angegebenen Modell an.
        """
        res = self.call_kw(model, "create", [[vals]])
        return self._ensure_single_id(res, "Erstellung")

    def write(self, model: str, record_id: int, vals: Dict[str, Any]) -> bool:
        """
        Schreibt Werte auf einen bestehenden Datensatz.
        """
        return bool(self.call_kw(model, "write", [[record_id], vals]))

    # ---------------------------------------------------------
    # Lieferanten / Partner
    # ---------------------------------------------------------

    def get_or_create_vendor(
        self,
        name: str,
        email: str,
        phone: str,
        address: str,
        vendorref: str,
    ) -> int:
        """
        Holt oder erzeugt einen Lieferanten (res.partner).

        - Sucht nach exaktem Namen.
        - Legt bei Bedarf einen Partner mit supplier_rank > 0 an.
        """
        existing = self.search_read(
            "res.partner",
            [["name", "=", name]],
            ["id"],
            limit=1,
        )
        if existing:
            return int(existing[0]["id"])

        vals: Dict[str, Any] = {
            "name": name,
            "email": email or False,
            "phone": phone or False,
            "street": address or False,
            "ref": vendorref or False,
            "is_company": True,
            "supplier_rank": 1,
        }

        partner_id = self.create("res.partner", vals)
        return int(partner_id)

    # ---------------------------------------------------------
    # Produkte
    # ---------------------------------------------------------

    def get_or_create_product(
        self,
        default_code: str,
        name: str,
        standard_price: float,
        product_type: str | None = None,
    ) -> int:
        """
        Holt oder aktualisiert ein Produkt anhand default_code,
        oder legt es neu an, falls nicht vorhanden.
        """

        def _safe_price(val: Any) -> float:
            try:
                v = float(val)
                if math.isnan(v) or math.isinf(v):
                    return 0.0
                return v
            except Exception:
                return 0.0

        safe_price = _safe_price(standard_price)

        existing = self.search_read(
            "product.product",
            [["default_code", "=", default_code]],
            ["id"],
            limit=1,
        )

        if existing:
            prod_id: IdLike = existing[0]["id"]
            prod_id_int = self._ensure_single_id(prod_id, "Produkt-Ermittlung")

            vals: Dict[str, Any] = {
                "name": name,
                "standard_price": safe_price,
            }
            if product_type:
                vals["type"] = product_type

            self.write("product.product", prod_id_int, vals)
            return prod_id_int

        vals = {
            "name": name,
            "default_code": default_code,
            "standard_price": safe_price,
        }
        if product_type:
            vals["type"] = product_type

        prod_id = self.create("product.product", vals)
        return int(prod_id)

    def get_or_create_finished_product(self, name: str) -> int:
        """
        Holt oder erzeugt ein Fertigprodukt anhand des Namens.
        """
        existing = self.search_read(
            "product.product",
            [["name", "=", name]],
            ["id"],
            limit=1,
        )
        if existing:
            return int(existing[0]["id"])

        vals = {"name": name}
        prod_id = self.create("product.product", vals)
        return int(prod_id)

    # ---------------------------------------------------------
    # BoM
    # ---------------------------------------------------------

    def get_or_create_bom(self, product_id: int) -> int:
        """
        Holt oder erzeugt eine BoM (mrp.bom) für eine gegebene Produktvariante.
        """
        # Produkt-Template ermitteln
        prod = self.search_read(
            "product.product",
            [["id", "=", product_id]],
            ["product_tmpl_id"],
            limit=1,
        )
        if not prod:
            raise RuntimeError(f"Produkt {product_id} nicht gefunden")

        # product_tmpl_id ist ein Many2one: [id, name] oder False
        tmpl_m2o = prod[0].get("product_tmpl_id")
        tmpl_id = self._ensure_many2one_id(tmpl_m2o, f"Produkt {product_id} hat kein Template.")

        # Existierende BoM nach Template suchen
        existing = self.search_read(
            "mrp.bom",
            [["product_tmpl_id", "=", tmpl_id]],
            ["id"],
            limit=1,
        )
        if existing:
            bom_id = self._ensure_single_id(existing[0]["id"], "BoM-Ermittlung")
            return bom_id

        # Neue BoM anlegen
        vals: Dict[str, Any] = {
            "product_tmpl_id": tmpl_id,
            "product_id": product_id,
            "product_qty": 1.0,
            "type": "normal",
        }
        bom_id = self.create("mrp.bom", vals)
        return int(bom_id)

    def add_bom_line(self, bom_id: int, product_id: int, quantity: float) -> int:
        """
        Fügt eine BoM-Zeile (mrp.bom.line) hinzu.
        """
        bom_id_int = self._ensure_single_id(bom_id, "BoM-ID")
        prod_id_int = self._ensure_single_id(product_id, "Produkt-ID")

        try:
            qty = float(quantity)
        except Exception:
            return 0

        if math.isnan(qty) or math.isinf(qty) or qty <= 0:
            return 0

        vals = {
            "bom_id": bom_id_int,
            "product_id": prod_id_int,
            "product_qty": qty,
        }
        line_id = self.create("mrp.bom.line", vals)
        return int(line_id)

    def clear_bom_lines(self, bom_id: int) -> None:
        """
        Löscht alle BoM-Zeilen für eine gegebene BoM.
        """
        bom_id_int = self._ensure_single_id(bom_id, "BoM-ID")
        lines = self.search_read(
            "mrp.bom.line",
            [["bom_id", "=", bom_id_int]],
            ["id"],
            limit=10000,
        )
        line_ids = [l["id"] for l in lines]
        if line_ids:
            self.call_kw("mrp.bom.line", "unlink", [line_ids])

    # ---------------------------------------------------------
    # interne Helpers für IDs
    # ---------------------------------------------------------

    @staticmethod
    def _ensure_single_id(value: IdLike, context: str) -> int:
        """
        Normiert Rückgaben, die int oder Liste/Tuple von IDs sein können, auf eine einzelne int-ID.
        """
        if isinstance(value, (list, tuple)):
            if not value:
                raise RuntimeError(f"{context}: leere ID-Liste erhalten.")
            value = value[0]
        return int(value)

    @staticmethod
    def _ensure_many2one_id(m2o: Any, error_msg: str) -> int:
        """
        Extrahiert die ID aus einem Many2one-Feld ([id, name] oder int/False).
        """
        if isinstance(m2o, (list, tuple)):
            if not m2o:
                raise RuntimeError(error_msg)
            return int(m2o[0])
        if not m2o:
            raise RuntimeError(error_msg)
        return int(m2o)
