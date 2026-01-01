# docs/generate_uml_endtoend.py

import os
import sys
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent.parent
sys.path.append(str(BASE_DIR))

from processes.production_routing import get_routing, VariantName  # type: ignore[import]


OUTPUT_DIR = Path("docs/uml")


def generate_endtoend_puml(variant: VariantName) -> Path:
    ops = get_routing(variant)
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    out_path = OUTPUT_DIR / f"endtoend_{variant}.puml"

    lines: list[str] = []
    lines.append("@startuml")
    lines.append(f"title End-to-End Prozess EVO2 {variant.capitalize()}")
    lines.append("")

    # Akteure / Systeme
    lines.append("actor Kunde")
    lines.append("participant \"Odoo Verkaufsmodul\" as Sales")
    lines.append("participant \"Odoo Einkauf\" as Purchase")
    lines.append("participant \"Odoo Lager\" as Stock")
    lines.append("participant \"Odoo Fertigung\" as MRP")
    lines.append("participant \"Shopfloor-Steuerung\" as SFS")
    lines.append("")

    # Kundenauftrag
    lines.append("Kunde -> Sales : Kundenauftrag anlegen")
    lines.append("Sales -> MRP : Fertigungsbedarf erzeugen")
    lines.append("")

    # Einkauf / Wareneingang (vereinfacht nach PurchaseFlow)
    lines.append("MRP -> Purchase : Bedarf an kritischen Teilen (z.B. Akku)")
    lines.append("Purchase -> Purchase : RFQ/Bestellung anlegen")
    lines.append("Purchase -> Stock : Wareneingang buchen")
    lines.append("Stock -> MRP : Bestand aktualisieren")
    lines.append("")

    # Fertigung mit Routing
    lines.append("MRP -> SFS : Fertigungsauftrag freigeben")
    lines.append("")

    for op in ops:
        label = f"{op.seq} - {op.name} ({op.workcenter_code})"
        lines.append(f"SFS -> SFS : {label}")
        lines.append("activate SFS")
        lines.append("SFS -> MRP : Fortschritt / Rückmeldung")
        lines.append("deactivate SFS")
        lines.append("")

    # QS und Lieferung
    lines.append("SFS -> MRP : Fertigmeldung Drohne")
    lines.append("MRP -> Stock : Fertigprodukt einlagern")
    lines.append("Stock -> Sales : Verfügbare Drohne bereitstellen")
    lines.append("Sales -> Kunde : Lieferung / Auftragsabschluss")
    lines.append("")
    lines.append("@enduml")

    out_path.write_text("\n".join(lines), encoding="utf-8")
    print(f"End-to-End PlantUML erzeugt: {out_path}")
    return out_path


def generate_all() -> None:
    for variant in ("spartan", "balance", "lightweight"):
        generate_endtoend_puml(variant)  # type: ignore[arg-type]


if __name__ == "__main__":
    generate_all()
