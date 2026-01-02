"""
Hilfsskript zur Generierung der End-to-End-Dokumentation für das Odoo-Drohnen-Projekt.

Erzeugt `docs/end_to_end_flow.md` auf Basis einer statischen Prozessbeschreibung
und optional einiger Beispiel-Events aus der End-to-End-Demo.

Die Events werden von der CLI (`python main.py prozesse demo-endtoend`)
in die Datei geschrieben, deren Pfad in `config.UMH_EVENTS_ENDTOEND_FILE`
konfiguriert ist (Standard: data/umh/umh_events_endtoend.json).
"""

from pathlib import Path
from datetime import datetime
import json

from config import UMH_EVENTS_ENDTOEND_FILE


DOCS_DIR = Path("docs")
DOC_FILE = DOCS_DIR / "end_to_end_flow.md"
EVENT_FILE = Path(UMH_EVENTS_ENDTOEND_FILE)


def load_example_events(max_events: int = 5):
    """Liest einige Beispiel-Events aus der End-to-End-Eventdatei ein."""
    if not EVENT_FILE.exists():
        return []
    try:
        with EVENT_FILE.open("r", encoding="utf-8") as f:
            data = json.load(f)
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
        "# End-to-End Flow – Odoo-Drohnenprojekt\n\n",
        f"*Stand: {now}*\n\n",
        (
            "Dieses Dokument beschreibt den vollständigen End-to-End-Prozess im Prototyp:\n"
            "Von Kundenbedarf über Verkauf, Fertigung, Einkauf, Lager/Inventur, Versand\n"
            "bis zur Erzeugung von UMH-Events sowie den Export der UMH-Masterdaten.\n\n"
        ),
        "---\n\n",
        "## 1. Fachlicher Ablauf\n\n",
        "- Kundenbedarf wird als Demo-Kundenanfragen simuliert.\n"
        "- Es werden mehrere Angebote und anschließend bestätigte Verkaufsaufträge für Drohnenvarianten\n"
        "  (z. B. **Spartan**, **Lightweight**, **Balance**) erzeugt.\n"
        "- Zu jedem Auftrag wird mindestens ein Fertigungsauftrag (MO) angelegt, gestartet und fertiggemeldet.\n"
        "- Für kritische Komponenten (z. B. Akku) wird ein Beschaffungsprozess RFQ → Bestellung → Wareneingang durchlaufen.\n"
        "- Ein Inventurfall und eine Ausschussbuchung (Schrottlager) werden demonstriert.\n"
        "- Zu den Verkaufsaufträgen werden Lieferungen erstellt und gebucht.\n"
        "- Aus Odoo heraus werden UMH-Events erzeugt und in einer JSON-Datei gespeichert.\n"
        "- Stammdaten (Produkte, BoMs, Routing) werden als UMH-Masterdaten in eine separate JSON-Datei exportiert.\n\n",
        "---\n\n",
        "## 2. Technischer Ablauf (CLI-Kommandos)\n\n",
        "### 2.1 Gesamtdurchlauf\n\n",
        "Der komplette Aufbau (Stammdaten, Prozesse, UMH-Exports) kann mit einem Kommando gestartet werden:\n\n",
        "```bash\n",
        "python main.py run-all -v spartan --debug\n",
        "```\n\n",
        "Interne Schritte von `run-all` (verkürzt):\n",
        "1. Verbindung zu Odoo prüfen (`check_connection`).\n",
        "2. Stammdaten & BoMs importieren (Supplier-, BOM-, Structured-BOM-, Stock-, Workcenter-Importer).\n",
        "3. Prozess-Demos (Sales, Purchase, Manufacturing, Inventory, Shipping) ausführen.\n",
        "4. UMH-Masterdaten exportieren (`export_masterdata` → `data/export/umh_masterdata.json`).\n",
        "5. End-to-End-Demo mit UMH-Events ausführen (`prozesse demo-endtoend`).\n\n",
        "### 2.2 End-to-End-Demo (inkl. UMH-Events)\n\n",
        "Direkte Ausführung der End-to-End-Demo:\n\n",
        "```bash\n",
        "python main.py prozesse demo-endtoend --debug\n",
        "```\n\n",
        "Interne Schritte:\n",
        "1. **Verkauf (`SalesFlow`)** – `run_demo_quotes_to_orders()` erzeugt und bestätigt mehrere Demo-Verkaufsaufträge.\n",
        "2. **Fertigung (`ManufacturingFlow`)** – `run_demo_mo_chain(orders)` legt Fertigungsaufträge an, startet sie und meldet sie fertig.\n",
        "3. **Einkauf (`PurchaseFlow`)** – `run_demo_purchasing()` demonstriert RFQ → Bestellung → Wareneingang.\n",
        "4. **Inventur & Ausschuss (`InventoryFlow`)** – `run_demo_inventory_and_scrap()` führt einen Inventurfall und eine Ausschussbuchung ins Schrottlager aus.\n",
        "5. **Versand (`ShippingFlow`)** – `run_demo_shipping(orders)` bucht Lieferungen für die Demo-Verkaufsaufträge.\n",
        "6. **UMH-Events** – `UMHEventManager` erzeugt Events, `UMHClientSimulator` schreibt sie nach\n",
        f"   `{UMH_EVENTS_ENDTOEND_FILE}` (Standard: `data/umh/umh_events_endtoend.json`).\n\n",
        "---\n\n",
        "## 3. Inventur und Ausschuss im Detail\n\n",
        "Die Inventur- und Ausschussprozesse werden durch `InventoryFlow` gekapselt\n",
        "(`processes/inventory_flow.py`):\n\n",
        "- `run_demo_inventory_case()` legt für das Demo-Produkt **Akku** eine Inventur an,\n",
        "  setzt eine gezählte Menge (z. B. 10 Stück) und validiert die Inventur.\n",
        "- `scrap_product(\"Akku\", 1.0)` bucht anschließend 1 Stück als Ausschuss in ein\n",
        "  Schrottlager (`stock.location` mit usage=`inventory`, Name `Scrap`).\n\n",
        "Im kombinierten CLI-Ablauf `prozesse demo-endtoend` wird dies über\n",
        "`InventoryFlow.run_demo_inventory_and_scrap()` zusammen ausgeführt.\n\n",
        "---\n\n",
        "## 4. UMH-Eventmodell\n\n",
        "### 4.1 Eventtypen\n\n",
        "Definiert in `integration/umh_events.py`:\n\n",
        "- `stock_change` – Bestandsänderung pro Produkt und Lagerort.\n",
        "- `mo_started` – Start eines Fertigungsauftrags.\n",
        "- `mo_completed` – Abschluss eines Fertigungsauftrags.\n",
        "- `delivery_shipped` – Versandereignis (Lieferung gebucht).\n",
        "- `quality_check` – Qualitätsereignis (z. B. Pass/Fail).\n\n",
        "Gemeinsame Struktur aller Events:\n\n",
        "- `type` – Eventtyp (z. B. `\"mo_completed\"`).\n",
        "- `timestamp` – ISO-Zeitstempel.\n",
        "- `payload` – strukturierte Nutzdaten (z. B. `mo_id`, `product_id`, `location_id`, `delivery_id`).\n\n",
        "### 4.2 Beispiel-Events aus der End-to-End-Demo\n\n",
        f"Dateipfad: `{UMH_EVENTS_ENDTOEND_FILE}`.\n\n",
        "Beispielauszug:\n\n",
        events_block,
        "\n\n---\n\n",
        "## 5. UMH-Masterdaten-Export\n\n",
        "Die Stammdaten werden über `integration/umh_export_masterdata.export_masterdata` als UMH-Masterdaten exportiert.\n\n",
        "- CLI-Kommando:\n\n",
        "```bash\n",
        "python main.py prozesse export-umh-masterdata --debug\n",
        "```\n\n",
        "- Standardpfad für die Ausgabe: `data/export/umh_masterdata.json`.\n",
        "- Enthaltene Blöcke:\n",
        "  - `products` – verkaufsrelevante Produkte und Komponenten.\n",
        "  - `boms` – Stücklisten inkl. Linien.\n",
        "  - `routing` – aggregiertes Routing aus `processes.production_routing`.\n\n",
        "---\n\n",
        "## 6. Dateien & Einstiegspunkte\n\n",
        "- **CLI-Einstieg:** `main.py` → ruft `app` aus `cli.py` auf (Typer-CLI).\n",
        "- **CLI-Kommandos:** `cli.py`\n",
        "  - `check-connection` – Verbindungstest.\n",
        "  - `run-all` – kompletter Durchlauf (Stammdaten, Prozesse, UMH-Exports).\n",
        "  - `prozesse demo-*` – Prozess-Demos (Sales, Purchase, Manufacturing, Inventory, Shipping).\n",
        "  - `prozesse demo-endtoend` – kompletter End-to-End-Lauf mit UMH-Events.\n",
        "  - `prozesse export-umh-masterdata` – Export der UMH-Masterdaten.\n",
        "- **Integration:**\n",
        "  - `integration/umh_events.py` – Eventtypen, Eventmodell und Eventmanager.\n",
        "  - `integration/umh_client_sim.py` – simulierter UMH-Client, schreibt JSON-Events in Datei.\n",
        "  - `integration/umh_export_masterdata.py` – Export der UMH-Masterdaten.\n",
        "---\n\n",
        "## 7. Traceability (Serien-/Chargennummern)\n\n",
        "Die Seriennummern- und Traceability-Funktionen werden über den\n",
        "`TraceabilityManager` in `processes/traceability.py` bereitgestellt:\n\n",
        "- `assign_serial_number(product_id, serial)` legt eine Seriennummer als `stock.lot`\n",
        "  für ein Produkt an (oder findet sie wieder).\n",
        "- `track_component_usage(mo_id, component_id, serial)` markiert eine Seriennummer\n",
        "  als in einem Fertigungsauftrag verwendet.\n",
        "- `get_traceability_chain(product_id)` liefert eine einfache Kette aus\n",
        "  Fertigungsaufträgen und zugehörigen Lieferungen für ein Produkt.\n\n",
        "Über das CLI-Kommando\n\n",
        "```bash\n",
        "python main.py prozesse trace-all-products --debug\n",
        "```\n\n",
        "kann eine Übersicht über die Traceability-Ketten aller Produkte ausgegeben werden.\n",

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
