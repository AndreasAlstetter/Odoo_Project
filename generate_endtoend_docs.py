# generate_endtoend_docs.py
"""
Hilfsskript zur Generierung der End-to-End-Dokumentation für das Odoo-Drohnen-Projekt.

Erzeugt `docs/end_to_end_flow.md` auf Basis einer statischen Prozessbeschreibung
und optional einiger Beispiel-Events aus `umh_events_endtoend.json`, die aus der
CLI (`prozesse demo-endtoend`) stammen.
"""

from pathlib import Path
from datetime import datetime
from config import UMH_EVENTS_ENDTOEND_FILE
import json

DOCS_DIR = Path("docs")
DOC_FILE = DOCS_DIR / "end_to_end_flow.md"
EVENT_FILE = Path(UMH_EVENTS_ENDTOEND_FILE)


def load_example_events(max_events: int = 5):
    """Liest einige Beispiel-Events aus umh_events_endtoend.json ein."""
    if not EVENT_FILE.exists():
        return []
    try:
        data = json.load(EVENT_FILE.open("r", encoding="utf-8"))
        if not isinstance(data, list):
            return []
        return data[:max_events]
    except (OSError, json.JSONDecodeError):
        return []


def format_event_snippet(events):
    """Formatiert Beispiel-Events als Markdown-Codeblock."""
    if not events:
        return "*(Noch keine Events vorhanden – zuerst `python main.py prozesse demo-endtoend` ausführen.)*"

    snippet = json.dumps(events, ensure_ascii=False, indent=2)
    return f"```json\n{snippet}\n```"


def generate_markdown() -> str:
    """Baut den Markdown-Inhalt für die End-to-End-Dokumentation zusammen."""
    events = load_example_events()
    events_block = format_event_snippet(events)

    now = datetime.now().isoformat(timespec="seconds")

    md_parts = [
        f"# End-to-End Flow – Odoo Drohnenprojekt\n",
        f"*Stand: {now}*\n",
        "Dieses Dokument beschreibt den vollständigen End-to-End-Prozess im Prototyp:\n"
        "Von Kundenbedarf über Verkauf, Fertigung, Einkauf, Lager/Inventur, Versand "
        "bis zur Erzeugung von UMH-Events.\n",
        "---\n",
        "## 1. Fachlicher Ablauf\n",
        "- Kundenbedarf wird als Demo-Kundenanfragen simuliert.\n"
        "- Es werden drei Angebote und anschließend bestätigte Verkaufsaufträge für die Varianten "
        "**Spartan**, **Lightweight** und **Balance** erzeugt.\n"
        "- Zu jedem Auftrag wird ein Fertigungsauftrag (MO) angelegt, gestartet und fertiggemeldet.\n"
        "- Für kritische Komponenten (z. B. Akku) wird ein Beschaffungsprozess RFQ → Bestellung → Wareneingang durchlaufen.\n"
        "- Ein Inventurfall und eine Ausschussbuchung (Schrottlager) werden demonstriert.\n"
        "- Zu den Verkaufsaufträgen werden Lieferungen erstellt und gebucht.\n",
        "---\n",
        "## 2. Technischer Ablauf (CLI-Kommandos)\n",
        "### 2.1 Vorbereitung (Stammdaten, BoMs, Lager, Lieferanten)\n\n",
        "```bash\n"
        "python main.py setup-all -v spartan\n"
        "```\n\n",
        "Wichtige Komponenten:\n",
        "- `importers.bom_importer.BOMImporter` – Mengenstücklisten pro Variante.\n"
        "- `importers.structured_bom_importer.StructuredBOMImporter` – mehrstufige BoMs.\n"
        "- `importers.supplier_importer.SupplierImporter` – Lieferantenstammdaten.\n"
        "- `importers.location_importer.LocationImporter` – Lagerstruktur.\n"
        "- `importers.stock_importer.StockImporter` – Basisbestände.\n",
        "### 2.2 End-to-End-Demo (inkl. UMH-Events)\n\n",
        "```bash\n"
        "python main.py prozesse demo-endtoend\n"
        "```\n\n",
        "Interne Schritte:\n",
        "1. **Verkauf (SalesFlow)** – `run_demo_quotes_to_orders()` erzeugt und bestätigt drei Demo-Verkaufsaufträge.\n",
        "2. **Fertigung (ManufacturingFlow)** – `run_demo_mo_chain(orders)` legt Fertigungsaufträge an, startet sie und meldet sie fertig.\n",
        "3. **Einkauf (PurchaseFlow)** – `run_demo_purchasing()` demonstriert RFQ → Bestellung → Wareneingang.\n",
        "4. **Inventur & Ausschuss (InventoryFlow)** – `run_demo_inventory_and_scrap()` führt einen Inventurfall und eine Ausschussbuchung ins Schrottlager aus.\n",
        "5. **Versand (ShippingFlow)** – `run_demo_shipping(orders)` bucht Lieferungen für die drei Verkaufsaufträge.\n",
        "6. **UMH-Events** – `UMHEventManager` erzeugt Events, `UMHClientSimulator` schreibt sie nach `umh_events_endtoend.json`.\n",
        "---\n",
        "## 3. UMH-Eventmodell\n",
        "### 3.1 Eventtypen\n",
        "Definiert in `integration/umh_events.py`:\n",
        "- `stock_change` – Bestandsänderung pro Produkt und Lagerort.\n",
        "- `mo_started` – Start eines Fertigungsauftrags.\n",
        "- `mo_completed` – Abschluss eines Fertigungsauftrags.\n",
        "- `delivery_shipped` – Versandereignis (Lieferung gebucht).\n",
        "- `quality_check` – Qualitätsereignis (z. B. Pass/Fail).\n\n",
        "Alle Events bestehen aus:\n",
        "- `type` – Eventtyp (z. B. `\"mo_completed\"`).\n",
        "- `timestamp` – ISO-Zeitstempel.\n",
        "- `payload` – strukturierte Nutzdaten (z. B. `mo_id`, `product_id`, `location_id`, `delivery_id`).\n\n",
        "### 3.2 Beispiel-Events aus umh_events_endtoend.json\n\n",
        "Dateipfad: `umh_events_endtoend.json` im Projekt-Root.\n\n",
        "Beispiel:\n\n",
        events_block,
        "\n---\n",
        "## 4. Dateien & Einstiegspunkte\n",
        "- **CLI-Einstieg:** `main.py` → ruft `app` aus `cli.py` auf (Typer-CLI).\n",
        "- **CLI-Kommandos:** `cli.py`\n",
        "  - `setup-all` – Stammdaten & Bestände.\n",
        "  - `stammdaten ...` – Einzelimporte.\n",
        "  - `prozesse demo-*` – Prozess-Demos.\n",
        "  - `prozesse demo-endtoend` – kompletter End-to-End-Lauf mit UMH-Events.\n",
        "- **Integration:**\n",
        "  - `integration/umh_events.py` – Eventtypen, Eventmodell und Eventmanager.\n",
        "  - `integration/umh_client_sim.py` – Simulierter UMH-Client, schreibt JSON-Events in Datei.\n",
    ]

    return "".join(md_parts)


def main() -> None:
    """
    Erzeugt die End-to-End-Dokumentation als Markdown-Datei im docs-Verzeichnis.
    """
    DOCS_DIR.mkdir(exist_ok=True)
    content = generate_markdown()
    DOC_FILE.write_text(content, encoding="utf-8")
    print(f"End-to-End-Dokumentation erzeugt: {DOC_FILE}")


if __name__ == "__main__":
    main()
