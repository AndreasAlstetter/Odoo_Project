from odoo_api import OdooAPI
from core.logging_utils import info, warning


def create_workorders_for_mo(api: OdooAPI, mo_name: str) -> None:
    # 1) Fertigungsauftrag per Referenz holen (z.B. WH/MO/01493)
    mos = api.search_read(
        "mrp.production",
        [["name", "=", mo_name]],
        ["id", "name", "product_id", "product_qty", "bom_id"],
        limit=1,
    )
    if not mos:
        raise RuntimeError(f"Fertigungsauftrag {mo_name} nicht gefunden")
    mo = mos[0]
    mo_id = mo["id"]
    product_id = mo["product_id"][0]
    qty = mo["product_qty"]
    bom_id = mo["bom_id"] and mo["bom_id"][0] or None

    if not bom_id:
        raise RuntimeError(f"MO {mo_name} hat keine BoM, keine Arbeitsaufträge möglich")

    # 2) Alle BoM-Operationen für diese BoM holen (wie aus Arbeitsplatznutzung abgeleitet)
    ops = api.search_read(
        "mrp.routing.workcenter",
        [["bom_id", "=", bom_id]],
        ["id", "name", "sequence", "workcenter_id", "time_cycle_manual", "note"],
        # Feldnamen ggf. an deine Odoo-Version anpassen
    )
    if not ops:
        warning(f"Keine Operationen für BoM {bom_id} gefunden, keine Workorders angelegt.")
        return

    # 3) Vorhandene Workorders optional löschen, damit wir sauber neu aufbauen
    existing_wos = api.search_read(
        "mrp.workorder",
        [["production_id", "=", mo_id]],
        ["id"],
    )
    if existing_wos:
        api.unlink("mrp.workorder", [w["id"] for w in existing_wos])

    # 4) Pro Operation einen Arbeitsauftrag erstellen
    for op in sorted(ops, key=lambda o: o["sequence"] or 0):
        wc_id = op["workcenter_id"][0]
        duration_expected = op.get("time_cycle_manual") or 0.0

        vals = {
            "name": f"{mo_name} - {op['name']}",
            "production_id": mo_id,
            "workcenter_id": wc_id,
            "product_id": product_id,
            "qty_production": qty,
            "duration_expected": duration_expected,
            "state": "ready",  # oder 'pending', je nach gewünschtem Startstatus
            # optionale Felder, damit Odoo-Export vollständig ist:
            # "note": op.get("note") or "",
        }
        wo_id = api.create("mrp.workorder", vals)
        info(
            f"Arbeitsauftrag {wo_id} für MO {mo_name}: "
            f"{op['name']} @ {op['workcenter_id'][1]} ({duration_expected} min erwartet)"
        )
