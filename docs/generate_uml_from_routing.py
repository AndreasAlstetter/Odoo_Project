# docs/generate_uml_from_routing.py

import os
import sys
from pathlib import Path

# Projektwurzel auf sys.path legen
BASE_DIR = Path(__file__).resolve().parent.parent
sys.path.append(str(BASE_DIR))

from processes.production_routing import get_routing, VariantName

OUTPUT_DIR = Path("docs/uml")


def generate_sequence_puml(variant: VariantName) -> Path:
    """Erstellt ein UML-Sequenzdiagramm für einen Produktionsablauf der EVO2-Produktion.

    Das Diagramm enthält die Hauptrollen "Kunde", "Odoo MRP" und "Shopfloor-Steuerung".
    Es wird der Ablauf der Produktion dargestellt, indem die Hauptrollen miteinander interagieren.
    """
    ops = get_routing(variant)
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    out_path = OUTPUT_DIR / f"production_sequence_{variant}.puml"

    lines: list[str] = []
    lines.append("@startuml")
    lines.append(f"title Produktionsablauf EVO2 {variant.capitalize()}")
    lines.append("")
    # einfache Rollen
    lines.append("actor Kunde")
    lines.append("participant \"Odoo MRP\" as Odoo")
    lines.append("participant \"Shopfloor-Steuerung\" as SFS")

    lines.append("")
    lines.append("Kunde -> Odoo : Kundenauftrag anlegen")
    lines.append("Odoo -> Odoo : Fertigungsauftrag erzeugen")
    lines.append("Odoo -> SFS : Produktionsauftrag freigeben")
    lines.append("")

    for op in ops:
        wc = op.workcenter_code
        op_label = f"{op.seq} - {op.name} ({wc})"
        lines.append(f"SFS -> SFS : {op_label}")
        lines.append(f"activate SFS")
        lines.append(f"SFS -> Odoo : Buchung / Fortschritt melden")
        lines.append("deactivate SFS")
        lines.append("")

    lines.append("SFS -> Odoo : Fertigmeldung Drohne")
    lines.append("Odoo -> Kunde : Lieferung / Abschluss")
    lines.append("")
    lines.append("@enduml")

    out_path.write_text("\n".join(lines), encoding="utf-8")
    print(f"PlantUML-Sequenzdiagramm erzeugt: {out_path}")
    return out_path


def generate_all_variants() -> None:
    """
    Erstellt PlantUML-Sequenzdiagramme fr alle Varianten.
    """
    for variant in ("spartan", "balance", "lightweight"):
        generate_sequence_puml(variant)  # type: ignore[arg-type]


if __name__ == "__main__":
    generate_all_variants()
