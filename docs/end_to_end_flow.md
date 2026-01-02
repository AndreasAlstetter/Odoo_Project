# End-to-End Flow – Odoo-Drohnenprojekt

*Stand: 2026-01-02T19:05:15*

Dieses Dokument beschreibt den vollständigen End-to-End-Prozess im Prototyp:
Von Kundenbedarf über Verkauf, Fertigung, Einkauf, Lager/Inventur, Versand
bis zur Erzeugung von UMH-Events sowie den Export der UMH-Masterdaten.

---

## 1. Fachlicher Ablauf

- Kundenbedarf wird als Demo-Kundenanfragen simuliert.
- Es werden mehrere Angebote und anschließend bestätigte Verkaufsaufträge für Drohnenvarianten
  (z. B. **Spartan**, **Lightweight**, **Balance**) erzeugt.
- Zu jedem Auftrag wird mindestens ein Fertigungsauftrag (MO) angelegt, gestartet und fertiggemeldet.
- Für kritische Komponenten (z. B. Akku) wird ein Beschaffungsprozess RFQ → Bestellung → Wareneingang durchlaufen.
- Ein Inventurfall und eine Ausschussbuchung (Schrottlager) werden demonstriert.
- Zu den Verkaufsaufträgen werden Lieferungen erstellt und gebucht.
- Aus Odoo heraus werden UMH-Events erzeugt und in einer JSON-Datei gespeichert.
- Stammdaten (Produkte, BoMs, Routing) werden als UMH-Masterdaten in eine separate JSON-Datei exportiert.

---

## 2. Technischer Ablauf (CLI-Kommandos)

### 2.1 Gesamtdurchlauf

Der komplette Aufbau (Stammdaten, Prozesse, UMH-Exports) kann mit einem Kommando gestartet werden:

```bash
python main.py run-all -v spartan --debug
```

Interne Schritte von `run-all` (verkürzt):
1. Verbindung zu Odoo prüfen (`check_connection`).
2. Stammdaten & BoMs importieren (Supplier-, BOM-, Structured-BOM-, Stock-, Workcenter-Importer).
3. Prozess-Demos (Sales, Purchase, Manufacturing, Inventory, Shipping) ausführen.
4. UMH-Masterdaten exportieren (`export_masterdata` → `data/export/umh_masterdata.json`).
5. End-to-End-Demo mit UMH-Events ausführen (`prozesse demo-endtoend`).

### 2.2 End-to-End-Demo (inkl. UMH-Events)

Direkte Ausführung der End-to-End-Demo:

```bash
python main.py prozesse demo-endtoend --debug
```

Interne Schritte:
1. **Verkauf (`SalesFlow`)** – `run_demo_quotes_to_orders()` erzeugt und bestätigt mehrere Demo-Verkaufsaufträge.
2. **Fertigung (`ManufacturingFlow`)** – `run_demo_mo_chain(orders)` legt Fertigungsaufträge an, startet sie und meldet sie fertig.
3. **Einkauf (`PurchaseFlow`)** – `run_demo_purchasing()` demonstriert RFQ → Bestellung → Wareneingang.
4. **Inventur & Ausschuss (`InventoryFlow`)** – `run_demo_inventory_and_scrap()` führt einen Inventurfall und eine Ausschussbuchung ins Schrottlager aus.
5. **Versand (`ShippingFlow`)** – `run_demo_shipping(orders)` bucht Lieferungen für die Demo-Verkaufsaufträge.
6. **UMH-Events** – `UMHEventManager` erzeugt Events, `UMHClientSimulator` schreibt sie nach
   `C:\Users\andre\OneDrive\Dokumente\Studium_Systems_Engineering\W_2 Schwerpunkt\Projekt\Odoo\Code\Prototyp_2\data\umh\umh_events_endtoend.json`.

---

## 3. UMH-Eventmodell

### 3.1 Eventtypen

Definiert in `integration/umh_events.py`:

- `stock_change` – Bestandsänderung pro Produkt und Lagerort.
- `mo_started` – Start eines Fertigungsauftrags.
- `mo_completed` – Abschluss eines Fertigungsauftrags.
- `delivery_shipped` – Versandereignis (Lieferung gebucht).
- `quality_check` – Qualitätsereignis (z. B. Pass/Fail).

Gemeinsame Struktur aller Events:

- `type` – Eventtyp (z. B. `"mo_completed"`).
- `timestamp` – ISO-Zeitstempel.
- `payload` – strukturierte Nutzdaten (z. B. `mo_id`, `product_id`, `location_id`, `delivery_id`).

### 3.2 Beispiel-Events aus der End-to-End-Demo

Dateipfad: `C:\Users\andre\OneDrive\Dokumente\Studium_Systems_Engineering\W_2 Schwerpunkt\Projekt\Odoo\Code\Prototyp_2\data\umh\umh_events_endtoend.json`.

Beispielauszug:

```json
[
  {
    "type": "mo_completed",
    "timestamp": "2026-01-02T17:33:08.982825",
    "payload": {
      "mo_id": 73
    }
  },
  {
    "type": "mo_completed",
    "timestamp": "2026-01-02T17:33:08.982825",
    "payload": {
      "mo_id": 74
    }
  },
  {
    "type": "mo_completed",
    "timestamp": "2026-01-02T17:33:08.982825",
    "payload": {
      "mo_id": 75
    }
  }
]
```

---

## 4. UMH-Masterdaten-Export

Die Stammdaten werden über `integration/umh_export_masterdata.export_masterdata` als UMH-Masterdaten exportiert.

- CLI-Kommando:

```bash
python main.py prozesse export-umh-masterdata --debug
```

- Standardpfad für die Ausgabe: `data/export/umh_masterdata.json`.
- Enthaltene Blöcke:
  - `products` – verkaufsrelevante Produkte und Komponenten.
  - `boms` – Stücklisten inkl. Linien.
  - `routing` – aggregiertes Routing aus `processes.production_routing`.

---

## 5. Dateien & Einstiegspunkte

- **CLI-Einstieg:** `main.py` → ruft `app` aus `cli.py` auf (Typer-CLI).
- **CLI-Kommandos:** `cli.py`
  - `check-connection` – Verbindungstest.
  - `run-all` – kompletter Durchlauf (Stammdaten, Prozesse, UMH-Exports).
  - `prozesse demo-*` – Prozess-Demos (Sales, Purchase, Manufacturing, Inventory, Shipping).
  - `prozesse demo-endtoend` – kompletter End-to-End-Lauf mit UMH-Events.
  - `prozesse export-umh-masterdata` – Export der UMH-Masterdaten.
- **Integration:**
  - `integration/umh_events.py` – Eventtypen, Eventmodell und Eventmanager.
  - `integration/umh_client_sim.py` – simulierter UMH-Client, schreibt JSON-Events in Datei.
  - `integration/umh_export_masterdata.py` – Export der UMH-Masterdaten.
