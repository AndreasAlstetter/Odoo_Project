from __future__ import annotations

from typing import List

from odoo_api import OdooAPI
from core import info, success


class SalesFlow:
    """Kapselt Demo-Szenarien für Angebot → Auftrag."""

    def __init__(self, api: OdooAPI) -> None:
        self.api = api

    def _create_quotation(
        self,
        customer_name: str,
        product_name: str,
        quantity: float,
        discount: float = 0.0,
    ) -> int:
        """Erstellt ein Angebot (sale.order) mit einer Position."""
        # Kunde suchen
        partners = self.api.search_read(
            "res.partner",
            [["name", "=", customer_name], ["customer_rank", ">", 0]],
            ["id"],
            limit=1,
        )
        if not partners:
            raise RuntimeError(f"Kunde '{customer_name}' nicht gefunden.")
        partner_id = partners[0]["id"]

        # Produkt suchen
        products = self.api.search_read(
            "product.product",
            [["name", "=", product_name]],
            ["id", "list_price"],
            limit=1,
        )
        if not products:
            raise RuntimeError(f"Produkt '{product_name}' nicht gefunden.")
        product_id = products[0]["id"]

        order_vals = {
            "partner_id": partner_id,
            "order_line": [
                (
                    0,
                    0,
                    {
                        "product_id": product_id,
                        "product_uom_qty": quantity,
                        "discount": discount,
                    },
                )
            ],
        }
        order_id = self.api.create("sale.order", order_vals)
        if isinstance(order_id, (list, tuple)):
            order_id = order_id[0]
        return int(order_id)

    def _confirm_order(self, order_id: int) -> None:
        """Bestätigt ein Angebot zu einem Auftrag (action_confirm)."""
        self.api.call_kw("sale.order", "action_confirm", [order_id], {})

    def scenario_standard_order(self) -> int:
        """Szenario 1: Standardauftrag ohne Rabatt."""
        info("Szenario 1: Standardauftrag ohne Rabatt.")
        order_id = self._create_quotation(
            customer_name="Demo Kunde GmbH",
            product_name="EVO2 Spartan Drohne",
            quantity=1.0,
        )
        self._confirm_order(order_id)
        success(f"Szenario 1 abgeschlossen: Auftrag {order_id}.")
        return order_id

    def scenario_discount_order(self) -> int:
        """Szenario 2: Auftrag mit Rabatt."""
        info("Szenario 2: Auftrag mit Rabatt.")
        order_id = self._create_quotation(
            customer_name="NextLap AG",
            product_name="EVO2 Lightweight Drohne",
            quantity=2.0,
            discount=10.0,
        )
        self._confirm_order(order_id)
        success(f"Szenario 2 abgeschlossen: Auftrag {order_id}.")
        return order_id

    def scenario_bulk_order(self) -> int:
        """Szenario 3: Sammelauftrag mit höherer Menge."""
        info("Szenario 3: Sammelauftrag mit höherer Menge.")
        order_id = self._create_quotation(
            customer_name="Demo Kunde GmbH",
            product_name="EVO2 Balance Drohne",
            quantity=5.0,
        )
        self._confirm_order(order_id)
        success(f"Szenario 3 abgeschlossen: Auftrag {order_id}.")
        return order_id

    def run_demo_quotes_to_orders(self) -> list[int]:
        """
        Führt alle drei Szenarien aus und gibt die Auftrags-IDs zurück.
        """
        orders: List[int] = []
        orders.append(self.scenario_standard_order())
        orders.append(self.scenario_discount_order())
        orders.append(self.scenario_bulk_order())
        return orders
