# tests/test_end_to_end.py

"""
End-to-End-Demo-Skript (kein klassischer Unit-Test).

Führt exemplarisch folgende Schritte aus:
- Odoo-Verbindung aufbauen.
- BoMs und Lieferanten importieren.
- Platzhalter: Prozess-Demos (Sales, Purchase, Manufacturing, Inventory, Shipping).
- UMH-Events erzeugen und nach JSON exportieren.
"""

import json

from ..odoo_api import OdooAPI
from ..importers.bom_importer import BOMImporter
from ..importers.structured_bom_importer import StructuredBOMImporter
from ..importers.supplier_importer import SupplierImporter
from ..processes.sales_flow import SalesFlow
from ..processes.purchase_flow import PurchaseFlow
from ..processes.manufacturing_flow import ManufacturingFlow
from ..processes.shipping_flow import ShippingFlow
from ..processes.inventory_flow import InventoryFlow
from ..integration.umh_events import UMHEventManager, EventType
from ..integration.umh_client_sim import UMHClientSimulator


def main() -> None:
    # 1) Odoo-Verbindung
    api = OdooAPI()

    # 2) Stammdaten / BoMs / Lieferanten
    bom_importer = BOMImporter(api)
    for variant in ("spartan", "lightweight", "balance"):
        bom_importer.import_variant(variant)

    structured_importer = StructuredBOMImporter(api)
    for variant in ("spartan", "lightweight", "balance"):
        structured_importer.import_eigenfertigung_boms(variant)

    supplier_importer = SupplierImporter(api)
    supplier_importer.import_suppliers()

    # 3) Prozess-Demos (optional, je nach verfügbarer Demo-Datenbank)
    sales = SalesFlow(api)
    purchase = PurchaseFlow(api)
    mfg = ManufacturingFlow(api)
    shipping = ShippingFlow(api)
    inventory = InventoryFlow(api)

    # Beispiel: einfacher Durchlauf, Fehler werden nur geloggt
    order_ids = sales.run_demo_quotes_to_orders()
    po_ids = purchase.run_demo_purchasing()
    mo_ids = mfg.run_demo_mo_chain(order_ids)
    shipping.run_demo_shipping(order_ids)
    inventory.run_demo_inventory_and_scrap()

    # 4) UMH-Events sammeln (vereinfachtes Beispiel)
    umh_manager = UMHEventManager()
    umh_manager.queue_event(umh_manager.create_mo_event(mo_id=1, event_type=EventType.MO_STARTED))
    umh_manager.queue_event(umh_manager.create_mo_event(mo_id=1, event_type=EventType.MO_COMPLETED))
    umh_manager.queue_event(umh_manager.create_stock_event(product_id=1, location_id=1, qty_change=10.0))
    umh_manager.queue_event(umh_manager.create_shipping_event(delivery_id=1))

    events = [e.to_dict() for e in umh_manager.get_pending_events()]
    output_file = "umh_events_endtoend.json"
    UMHClientSimulator(output_file=output_file).send_events_batch(events)

    with open(output_file, "w", encoding="utf-8") as f:
        json.dump(events, f, ensure_ascii=False, indent=2)

    print(f"End-to-end Demo fertig. Events in {output_file} geschrieben.")


if __name__ == "__main__":
    main()
