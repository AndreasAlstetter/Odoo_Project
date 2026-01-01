# processes/sales_flow.py

"""
Verkaufsprozess: Angebot → Auftrag.

Ziele:
- Angebot für eine Drohnenvariante anlegen.
- Angebot bestätigen (wird zum Auftrag).
- Optional: Mehrere Testfälle (z. B. verschiedene Kunden/Varianten).

Nutzt:
- Modelle: sale.order, sale.order.line, res.partner, product.product
"""

from __future__ import annotations

from typing import List, Dict, Any

from odoo_api import OdooAPI
from core.logging_utils import info, success, warning


class SalesFlow:
    """Kapselt typische Schritte des Verkaufsprozesses."""

    def __init__(self, api: OdooAPI) -> None:
        self.api = api

    def _find_customer(self, name: str) -> int | None:
        """Sucht einen Kunden anhand des Namens und liefert dessen ID oder None."""
        res = self.api.search_read(
            "res.partner",
            [["name", "=", name]],
            ["id"],
            limit=1,
        )
        return res[0]["id"] if res else None

    def _find_product(self, name: str) -> int | None:
        """Sucht ein Produkt anhand des Namens und liefert dessen ID oder None."""
        res = self.api.search_read(
            "product.product",
            [["name", "=", name]],
            ["id"],
            limit=1,
        )
        return res[0]["id"] if res else None

    def create_quotation(
        self,
        customer_name: str,
        product_name: str,
        quantity: float = 1.0,
        price_unit: float | None = None,
    ) -> int:
        """
        Legt ein Angebot (sale.order) für einen Kunden und ein Produkt an.

        Schritte:
        - Kunde und Produkt suchen.
        - sale.order anlegen.
        - passende sale.order.line erzeugen.

        Rückgabe:
        - ID des angelegten sale.order.
        """
        info(f"Erzeuge Angebot für Kunde '{customer_name}' und Produkt '{product_name}'...")

        partner_id = self._find_customer(customer_name)
        if not partner_id:
            raise RuntimeError(f"Kunde '{customer_name}' nicht gefunden.")

        product_id = self._find_product(product_name)
        if not product_id:
            raise RuntimeError(f"Produkt '{product_name}' nicht gefunden.")

        order_vals: Dict[str, Any] = {
            "partner_id": partner_id,
            # weitere optionale Felder (z. B. pricelist_id, payment_term_id)
            # können bei Bedarf ergänzt werden.
        }

        order_id = self.api.create("sale.order", order_vals)
        # create kann Liste/Tuple zurückgeben → absichern
        if isinstance(order_id, (list, tuple)):
            if not order_id:
                raise RuntimeError("Erstellung von sale.order hat keine ID geliefert.")
            order_id = order_id[0]
        order_id = int(order_id)

        # Standardpreis aus Produkt holen, falls kein Preis angegeben
        if price_unit is None:
            prod = self.api.read("product.product", [product_id], ["list_price"])
            price_unit = prod[0].get("list_price", 0.0) if prod else 0.0

        line_vals: Dict[str, Any] = {
            "order_id": order_id,
            "product_id": product_id,
            "product_uom_qty": quantity,
            "price_unit": price_unit,
        }

        self.api.create("sale.order.line", line_vals)
        success(f"Angebot {order_id} erstellt.")
        return order_id

    def confirm_quotation(self, order_id: int) -> None:
        """
        Bestätigt ein Angebot und erzeugt daraus einen Auftrag.

        - Ruft `action_confirm` auf sale.order auf.
        """
        info(f"Bestätige Angebot/Auftrag {order_id}...")
        self.api.call_kw("sale.order", "action_confirm", [order_id], {})
        success(f"Angebot/Auftrag {order_id} bestätigt.")

    def run_demo_quotes_to_orders(self) -> List[int]:
        """
        Führt mehrere Demo-Angebote durch und bestätigt sie.

        Annahmen:
        - Mindestens ein Demo-Kunde: „Demo Kunde 1“, „Demo Kunde 2“.
        - Drohnenvarianten:
          - „EVO2 Spartan Drohne“
          - „EVO2 Lightweight Drohne“
          - „EVO2 Balance Drohne“

        Rückgabe:
        - Liste der erzeugten sale.order-IDs.
        """
        info("Starte Demo: Angebot → Auftrag (mehrere Testfälle)...")

        orders: List[int] = []
        scenarios = [
            ("Demo Kunde 1", "EVO2 Spartan Drohne", 1.0),
            ("Demo Kunde 1", "EVO2 Lightweight Drohne", 2.0),
            ("Demo Kunde 2", "EVO2 Balance Drohne", 1.0),
        ]

        for cust, prod, qty in scenarios:
            try:
                order_id = self.create_quotation(cust, prod, qty)
                self.confirm_quotation(order_id)
                orders.append(order_id)
            except RuntimeError as exc:
                warning(f"Demo-Szenario übersprungen: {exc}")

        if not orders:
            warning("Keine Demo-Angebote konnten erzeugt werden (Kunden/Produkte prüfen).")
        else:
            success(f"{len(orders)} Demo-Aufträge erzeugt und bestätigt.")

        return orders
