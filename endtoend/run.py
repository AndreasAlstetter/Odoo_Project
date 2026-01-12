# endtoend/run.py

from __future__ import annotations
from typing import Sequence

from odoo_api import OdooAPI
from importers.bom_importer import BOMImporter
from importers.structured_bom_importer import StructuredBOMImporter
from importers.supplier_importer import SupplierImporter
from processes.sales_flow import SalesFlow
from processes.purchase_flow import PurchaseFlow
from processes.manufacturing_flow import ManufacturingFlow
from processes.shipping_flow import ShippingFlow
from processes.inventory_flow import InventoryFlow
from integration.umh_events import UMHEventManager, EventType
from integration.umh_client_sim import UMHClientSimulator
from config import UMH_EVENTS_ENDTOEND_FILE
from core.logging_utils import info, success



def import_masterdata_for_variants(api: OdooAPI,
                                   variants: Sequence[str] = ("spartan", "lightweight", "balance")
                                   ) -> None:
    """BoMs (einfach + strukturiert) und Lieferanten für die angegebenen Varianten importieren."""
    bom_importer = BOMImporter(api)
    structured_importer = StructuredBOMImporter(api)
    supplier_importer = SupplierImporter(api)

    info("Starte BoM- und Lieferantenimporte für Varianten: " + ", ".join(variants))

    for variant in variants:
        bom_importer.import_variant(variant)
    for variant in variants:
        structured_importer.import_eigenfertigung_boms(variant)

    supplier_importer.import_suppliers()
    success("Stammdatenimporte für Varianten abgeschlossen.")


def run_process_demos(api: OdooAPI) -> dict:
    """Führt Sales, Purchase, Manufacturing, Inventory und Shipping-Demos aus.

    Rückgabe: einfache ID-Übersicht für mögliche Tests/Assertions.
    """
    sales = SalesFlow(api)
    purchase = PurchaseFlow(api)
    mfg = ManufacturingFlow(api)
    shipping = ShippingFlow(api)
    inventory = InventoryFlow(api)

    order_ids = sales.run_demo_quotes_to_orders()
    po_ids = purchase.run_demo_purchasing()
    mo_ids = mfg.run_demo_mo_chain(order_ids)
    shipping.run_demo_shipping(order_ids)
    inventory.run_demo_inventory_and_scrap()

    return {
        "orders": order_ids,
        "purchase_orders": po_ids,
        "manufacturing_orders": mo_ids,
    }


def generate_umh_endtoend_events(output_file: str = UMH_EVENTS_ENDTOEND_FILE) -> list[dict]:
    """Erzeugt vereinfachte UMH-Events und schreibt sie in eine JSON-Datei."""
    from json import dump

    umh_manager = UMHEventManager()
    umh_manager.queue_event(
        umh_manager.create_mo_event(mo_id=1, event_type=EventType.MO_STARTED)
    )
    umh_manager.queue_event(
        umh_manager.create_mo_event(mo_id=1, event_type=EventType.MO_COMPLETED)
    )
    umh_manager.queue_event(
        umh_manager.create_stock_event(product_id=1, location_id=1, qty_change=10.0)
    )
    umh_manager.queue_event(
        umh_manager.create_shipping_event(delivery_id=1)
    )

    events = [e.to_dict() for e in umh_manager.get_pending_events()]

    client = UMHClientSimulator(output_file=output_file)
    client.send_events_batch(events)

    with open(output_file, "w", encoding="utf-8") as f:
        dump(events, f, ensure_ascii=False, indent=2)

    success(f"UMH-Events in {output_file} geschrieben.")
    return events


def run_endtoend_demo(api: OdooAPI) -> dict:
    """Kapselt den kompletten End-to-End-Durchlauf.

    Schritte:
      1) Stammdaten/BoMs/Lieferanten
      2) Prozess-Demos (Sales, Purchase, Manufacturing, Inventory, Shipping)
      3) UMH-Events erzeugen und exportieren
    """
    info("Starte End-to-End-Demo...")
    import_masterdata_for_variants(api)
    process_info = run_process_demos(api)
    events = generate_umh_endtoend_events()
    success("End-to-End-Demo abgeschlossen.")

    process_info["umh_events_count"] = len(events)
    return process_info


def run_endtoend_demo_light(api: OdooAPI) -> dict:
    """Minimaler End-to-End-Demo: nur Sales + Manufacturing ohne Scheduler/Orderpoints."""
    info("Starte Light-End-to-End-Demo (Sales + Manufacturing)...")

    sales = SalesFlow(api)
    manuf = ManufacturingFlow(api)

    orders = sales.run_demo_quotes_to_orders()
    mos = manuf.run_demo_mo_chain(orders)

    success(
        f"Light-End-to-End-Demo abgeschlossen "
        f"({len(orders)} SOs, {len(mos)} MOs)."
    )

    return {
        "orders": orders,
        "manufacturing_orders": mos,
    }
