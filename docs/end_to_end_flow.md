# End-to-End Flow – Odoo Drohnenprojekt
*Stand: 2026-01-01T16:29:06*
Dieses Dokument beschreibt den vollständigen End-to-End-Prozess im Prototyp:
Von Kundenbedarf über Verkauf, Fertigung, Einkauf, Lager/Inventur, Versand bis zur Erzeugung von UMH-Events.
---
## 1. Fachlicher Ablauf
- Kundenbedarf wird als Demo-Kundenanfragen simuliert.
- Es werden drei Angebote und anschließend bestätigte Verkaufsaufträge für die Varianten **Spartan**, **Lightweight** und **Balance** erzeugt.
- Zu jedem Auftrag wird ein Fertigungsauftrag (MO) angelegt, gestartet und fertiggemeldet.
- Für kritische Komponenten (z. B. Akku) wird ein Beschaffungsprozess RFQ → Bestellung → Wareneingang durchlaufen.
- Ein Inventurfall und eine Ausschussbuchung (Schrottlager) werden demonstriert.
- Zu den Verkaufsaufträgen werden Lieferungen erstellt und gebucht.
---
## 2. Technischer Ablauf (CLI-Kommandos)
### 2.1 Vorbereitung (Stammdaten, BoMs, Lager, Lieferanten)

```bash
python main.py setup-all -v spartan
```

Wichtige Komponenten:
- `importers.bom_importer.BOMImporter` – Mengenstücklisten pro Variante.
- `importers.structured_bom_importer.StructuredBOMImporter` – mehrstufige BoMs.
- `importers.supplier_importer.SupplierImporter` – Lieferantenstammdaten.
- `importers.location_importer.LocationImporter` – Lagerstruktur.
- `importers.stock_importer.StockImporter` – Basisbestände.
### 2.2 End-to-End-Demo (inkl. UMH-Events)

```bash
python main.py prozesse demo-endtoend
```

Interne Schritte:
1. **Verkauf (SalesFlow)** – `run_demo_quotes_to_orders()` erzeugt und bestätigt drei Demo-Verkaufsaufträge.
2. **Fertigung (ManufacturingFlow)** – `run_demo_mo_chain(orders)` legt Fertigungsaufträge an, startet sie und meldet sie fertig.
3. **Einkauf (PurchaseFlow)** – `run_demo_purchasing()` demonstriert RFQ → Bestellung → Wareneingang.
4. **Inventur & Ausschuss (InventoryFlow)** – `run_demo_inventory_and_scrap()` führt einen Inventurfall und eine Ausschussbuchung ins Schrottlager aus.
5. **Versand (ShippingFlow)** – `run_demo_shipping(orders)` bucht Lieferungen für die drei Verkaufsaufträge.
6. **UMH-Events** – `UMHEventManager` erzeugt Events, `UMHClientSimulator` schreibt sie nach `umh_events_endtoend.json`.
---
## 3. UMH-Eventmodell
### 3.1 Eventtypen
Definiert in `integration/umh_events.py`:
- `stock_change` – Bestandsänderung pro Produkt und Lagerort.
- `mo_started` – Start eines Fertigungsauftrags.
- `mo_completed` – Abschluss eines Fertigungsauftrags.
- `delivery_shipped` – Versandereignis (Lieferung gebucht).
- `quality_check` – Qualitätsereignis (z. B. Pass/Fail).

Alle Events bestehen aus:
- `type` – Eventtyp (z. B. `"mo_completed"`).
- `timestamp` – ISO-Zeitstempel.
- `payload` – strukturierte Nutzdaten (z. B. `mo_id`, `product_id`, `location_id`, `delivery_id`).

### 3.2 Beispiel-Events aus umh_events_endtoend.json

Dateipfad: `umh_events_endtoend.json` im Projekt-Root.

Beispiel:

```json
[
  {
    "type": "mo_completed",
    "timestamp": "2026-01-01T15:28:12.620884",
    "payload": {
      "mo_id": 22
    }
  },
  {
    "type": "mo_completed",
    "timestamp": "2026-01-01T15:28:12.620884",
    "payload": {
      "mo_id": 23
    }
  },
  {
    "type": "mo_completed",
    "timestamp": "2026-01-01T15:28:12.620884",
    "payload": {
      "mo_id": 24
    }
  }
]
```
---
## 4. Dateien & Einstiegspunkte
- **CLI-Einstieg:** `main.py` → ruft `app` aus `cli.py` auf (Typer-CLI).
- **CLI-Kommandos:** `cli.py`
  - `setup-all` – Stammdaten & Bestände.
  - `stammdaten ...` – Einzelimporte.
  - `prozesse demo-*` – Prozess-Demos.
  - `prozesse demo-endtoend` – kompletter End-to-End-Lauf mit UMH-Events.
- **Integration:**
  - `integration/umh_events.py` – Eventtypen, Eventmodell und Eventmanager.
  - `integration/umh_client_sim.py` – Simulierter UMH-Client, schreibt JSON-Events in Datei.
