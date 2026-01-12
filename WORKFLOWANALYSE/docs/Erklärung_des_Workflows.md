# Odoo-Drohnenprojekt – Gesamtarchitektur, Prozesse und Eventmodell

> Ziel: Das ERP-System Odoo unterstützt alle existierenden Prozesse der Drohnen GmbH so, dass ca. 500 Drohnen pro Tag gebaut, geprüft und ausgeliefert werden können. Die Abnahme erfolgt durch einen vollständigen Durchlauf des Beschaffungs- und Kundenauftragsprozesses. 
---

## 1. Einleitung

Dieses Dokument beschreibt das Odoo-basierte System der Drohnen GmbH aus fachlicher, technischer und eventbasierter Sicht. Es verbindet:

- End-to-End-Prozesse (von Kundenbedarf bis Auslieferung)
- Zentrale Odoo-Objekte (SOs, MOs, Lagerbewegungen, Qualität)
- Architekturkomponenten (Odoo-Module, Shopfloor, UMH/Digital Twin)
- Ein schlankes Eventmodell für die Integration mit UMH / Digital Twin 

Odoo fungiert ausschließlich als ERP: es verwaltet Stammdaten, Aufträge, Beschaffung, Lager, Fertigung, Qualität, Versand und Rechnungsstellung. Simulation und Digital Twin sind externe Systeme, die über Events und Masterdaten mit Odoo gekoppelt sind. 

---

## 2. Prozesssicht (Aktivitätsdiagramme)

### 2.1 End-to-End-Workflow (High-Level)

Der Gesamtprozess gliedert sich in folgende Hauptbereiche:

1. Kunde / Vertrieb  
2. Planung & MRP  
3. Einkauf  
4. Lager & Logistik  
5. Produktion klassisch  
6. Montagezelle AMR/SCARA/NEXTLAP  
7. Qualität & Versand  
8. Controlling / UMH 

Jeder Bereich wird durch ein eigenes Aktivitätsdiagramm verfeinert, das die Odoo-relevanten Schritte hervorhebt.

---

### 2.2 Kunde / Vertrieb

- Kunde formuliert Bedarf.  
- Vertrieb erfasst ein Angebot in Odoo (Produkt, Variante, Menge, Preis, Lieferdatum).  
- Kunde prüft das Angebot und akzeptiert oder lehnt ab.  
- Bei Akzeptanz: Angebot → Verkaufsauftrag (Sales Order, SO); Auftrag wird bestätigt und löst MRP/Fertigung aus.  
- Bei Ablehnung: Angebot wird als verloren markiert. 

Wichtige Odoo-Objekte:  
`sale.order`, `sale.order_line`, `res.partner`, `product.product`. 

---

### 2.3 Planung & MRP

- Eingang: bestätigte Verkaufsaufträge (SOs).  
- MRP-Lauf (Periodenplanung) wird in Odoo gestartet.  
- Entscheidung: Make-to-Order (direkter Bedarf aus SO) vs. Make-to-Stock (Sicherheitsbestand / Prognose).  
- Parallel:
  - Bedarf für Kaufteile berechnen; ggf. Beschaffungsvorschläge (RFQs/POs) erzeugen.  
  - Fertigungsbedarf je Drohnenvariante berechnen; MOs anlegen. 

Wichtige Odoo-Objekte:  
`mrp.production`, `product.product`, `mrp.bom`, `purchase.order`. 

---

### 2.4 Einkauf, Lager, Logistik

- MRP erzeugt Beschaffungsvorschläge für Kaufteile.  
- Einkauf erstellt RFQs, verhandelt Preise/Termine, bestätigt Bestellungen.  
- Lieferant liefert Ware; Lager prüft Menge/Qualität und bucht Wareneingang.  
- Bestände werden aktualisiert und auf Lager- und Kanbanplätze verteilt.  
- Kanban-Bestand wird überwacht; bei Unterschreitung wird ein Nachschubauftrag (Reordering/Umlagerung) angestoßen.  
- Material wird für die Produktion kommissioniert und ins Produktionslager transferiert. 

Wichtige Odoo-Objekte:  
`purchase.order`, `purchase.order_line`, `stock.picking` (incoming), `stock.move`, `stock.location`. 
---

### 2.5 Produktion, Qualität, Versand

- Fertigungsaufträge (MOs) werden freigegeben und gestartet.  
- Work Orders laufen durch: Lasern, 3D-Druck, Elektronikbestückung, Löten, Flashen, Endmontage.  
- Qualität führt In-Prozess- und Endprüfungen durch (Mechanik, Elektronik, Endtest).  
- Bei OK: MO wird fertiggemeldet, Seriennummer/RFID zugeordnet.  
- Bei NOK: Nacharbeit oder Ausschuss (Scrap) wird gebucht.  
- Fertige Drohnen werden ins Versandlager umgebucht.  
- Lieferaufträge aus SOs werden kommissioniert, verpackt und als Lieferungen (Warenausgänge) gebucht. 

Wichtige Odoo-Objekte:  
`mrp.production`, `mrp.workorder`, `stock.picking` (internal/outgoing), `stock.move`, `quality.check`, `stock.scrap`. 

---

### 2.6 Controlling / UMH

- Produktions-, Bestands- und Qualitätsdaten werden aus Odoo ausgelesen.  
- UMH-Events (Produktion, Bestand, Qualität, Versand) werden erzeugt und an den Digital Twin gesendet.  
- KPIs (Durchsatz, OEE-nahe Kennzahlen, Ausschuss, CO₂ je Produkt) werden berechnet. 

---

## 3. Ablaufsicht (Sequenzdiagramme)

### 3.1 Sales-Order-Sequenz

Akteure: Kunde, Vertrieb/Odoo, MRP, Lager/Versand, Buchhaltung. 

- Kunde → Vertrieb: Anfrage/Bedarf.  
- Vertrieb → Odoo: Angebot erfassen und speichern.  
- Kunde → Vertrieb: Angebot akzeptieren.  
- Vertrieb/Odoo: SO anlegen und bestätigen (Reservierungen, MRP-Trigger).  
- Odoo → MRP: Bedarf aus SO.  
- Odoo → Lager: Lieferauftrag erzeugen.  
- Odoo → Buchhaltung: Rechnung erstellen.

Wesentliche Methoden (logische Ebene):  
`create(sale.order)`, `action_confirm(sale.order)`. 

---

### 3.2 Purchase & Wareneingang

Akteure: Planung/MRP, Einkauf/Odoo, Lieferant, Lager/Odoo. 

- MRP → Einkauf: Beschaffungsvorschläge.  
- Einkauf → Odoo: RFQ/PO anlegen, Bestellung bestätigen.  
- Lieferant → Lager: Lieferung.  
- Lager → Odoo: Wareneingang prüfen und buchen, Bestand aktualisieren.

Wesentliche Methoden:  
`create(purchase.order)`, `button_confirm(purchase.order)`, `button_validate(stock.picking)`. 
---

### 3.3 MO-Kette, Qualität, Versand, UMH

Akteure: MRP/Odoo, Produktion/Odoo, Qualität/Odoo, Lager/Versand, UMH-Integration. 

- MRP → Produktion: `create(mrp.production)` (MO anlegen).  
- Produktion: `action_confirm`, `action_assign` (MO starten, Material reservieren).  
- Produktion → UMH: Event `mo_started`.  
- Work Orders je Operation werden durchlaufen.  
- Produktion → Qualität: Prüfling mit MO-Kontext.  
- Qualität: In-Prozess- und Endprüfung; Ergebnis OK/NOK.  
- Qualität → UMH: Event `quality_check`.  
- Bei OK: Produktion meldet MO fertig (`button_mark_done`/`action_finish`), UMH-Event `mo_completed`.  
- Bei NOK: Nacharbeit/Scrap, ebenfalls `mo_completed` mit Fehlerkontext.  
- Produktion → Lager: Umbuchung fertige Drohne ins Versandlager (`stock.move`/interner Picking).  
- Lager → UMH: ein oder mehrere `stock_change`-Events.  
- Lager → Lager: Lieferauftrag verarbeiten, Lieferung buchen (`button_validate`), UMH-Event `delivery_shipped`.  
- UMH-Integration: Events sammeln, in JSON serialisieren und an UMH/Digital Twin senden. 

---

## 4. Struktursicht (Klassendiagramm – Domänenmodell)

Zentrale Entitäten und Beziehungen (fachliche Sicht, angelehnt an Odoo):

- **Kunden & Lieferanten**  
  - `res.partner`: Kunden und Lieferanten (`customer_rank`, `supplier_rank`). 

- **Sales**  
  - `sale.order` – Kopf eines Kundenauftrags.  
  - `sale.order.line` – Position(en) eines Auftrags, referenziert `product.product`. 

- **Produkte & Stücklisten**  
  - `product.product` – Produkt/Variante der Drohne oder Komponenten.  
  - `mrp.bom` – Stückliste für Produkt/Variante.  
  - `mrp.bom.line` – BoM-Zeilen (Komponenten mit Menge). 

- **Purchase**  
  - `purchase.order` – Bestellung.  
  - `purchase.order_line` – Bestellpositionen. 

- **Manufacturing**  
  - `mrp.production` – Fertigungsauftrag (MO).  
  - `mrp.workorder` – Arbeitsgänge je MO.  
  - `mrp.workcenter` – Maschinen/Arbeitsplätze (Laser, 3D-Druck, Montage). 

- **Lager & Logistik**  
  - `stock.location` – Lagerorte (WH/Stock, Produktion, Versand, Scrap).  
  - `stock.picking` – Wareneingänge/-ausgänge/Umlagerungen.  
  - `stock.move` – einzelne Bewegungen pro Produkt. 
- **Inventur & Scrap**  
  - `stock.inventory` / `stock.inventory.line` – Inventuren.  
  - `stock.scrap` – Ausschussbuchungen. 

- **Qualität & Traceability**  
  - `quality.check` – Prüfergebnis (In-Prozess, Endtest).  
  - `stock.lot` – Serien-/Chargennummern.  
  - Eigener TraceabilityManager in `traceability.py` verknüpft MOs, Lots und Lieferungen. 

- **UMH-Events**  
  - `UMHEvent`: `type`, `timestamp`, `payload`.  
  - `UMHEventManager`: Liste von Events + Methoden zum Erzeugen (Stock, MO, Shipping, Quality) und Queue-Verwaltung. 

Dieses Modell verknüpft die fachlichen Begriffe aus Prozessen und UML mit konkreten Tabellen und Feldern in Odoo.

---

## 5. Architektursicht (Komponentendiagramm)

### 5.1 Odoo-Module

Im Kern existiert eine Odoo-Instanz mit folgenden logischen Komponenten:

- **Sales** – Angebote, Verkaufsaufträge, Preislisten. 
- **Purchase** – RFQs, Bestellungen. 
- **Inventory** – Lagerorte, Bewegungen, Inventur, Kanban/Reordering. 
- **Manufacturing (MRP)** – MOs, Work Orders, Workcenter, Routings. 
- **Quality** – Prüfungen, Qualitätskontrollpunkte (optional über Quality-App).  
- **Accounting** – Rechnungen, Buchhaltung (fachlich relevant, nicht im Repo detailliert).  
- **Integration/UMH-Connector** – Odoo-API-Client (`OdooAPI`), Eventmanager, MQTT/HTTP-Client für UMH, Export von Masterdaten/KPIs. 

### 5.2 Externe Systeme

- **Shopfloor/Drohnenfabrik** – physische Maschinen (Lasercutter, 3D-Drucker), Montagezellen, Worker; sie reagieren auf Arbeitsaufträge und Materialbereitstellung aus Odoo. 
- **UMH / Digital Twin** – erhält Events, Masterdaten und ggf. KPI-Daten; bildet eine virtuelle Fabrik ab.  
- **Energie / Smart Meter** – liefert Messwerte (kWh, PV-Erzeugung), die in KPI-/CO₂-Berechnungen einfließen. 

Die Integration implementiert einen klaren, asynchronen Informationsfluss: Odoo sendet Ereignisse, UMH/Twin konsumiert sie.

---

## 6. Eventmodell (UMH)

Die Kopplung zu UMH basiert auf fünf Eventtypen, die alle in einer einheitlichen Struktur übertragen werden:

json
{
  "type": "<event_type>",
  "timestamp": "<ISO-8601>",
  "payload": { ... }
}

### 6.1 stock_change

- **Payload**  
  - `product_id`  
  - `location_id`  
  - `qty_change` 

- **Auslöser**  
  - Wareneingänge  
  - Umbuchungen  
  - Warenausgänge  
  - Inventuren  
  - Scrap 

- **Kontext**  
  - `stock.move`  
  - `stock.picking`  
  - `stock.inventory`  
  - `stock.scrap`

---

### 6.2 `mo_started`

- **Payload**  
  - `mo_id` 

- **Auslöser**  
  - Start eines MOs (`action_confirm` / `action_assign`) 

- **Kontext**  
  - `mrp.production` mit Produkt, Menge, Ursprung (SO) 

---

### 6.3 `mo_completed`

- **Payload**  
  - `mo_id` 

- **Auslöser**  
  - Fertigmeldung eines MOs (`button_mark_done` / `action_finish`) 

- **Kontext**  
  - Ist-Menge  
  - Ausschuss  
  - Dauer  
  - verknüpfte Work Orders (`mrp.workorder`) 

---

### 6.4 `delivery_shipped`

- **Payload**  
  - `delivery_id` (ID eines outgoing `stock.picking`) [conversation_history:1]

- **Auslöser**  
  - Buchen eines Warenausgangs (Lieferung) via `button_validate` 

- **Kontext**  
  - Kunde  
  - Produkte  
  - Mengen  
  - Referenz auf SO (`sale.order`) 
---

### 6.5 `quality_check`

- **Payload**  
  - `product_id`  
  - `stage`  
  - `result`  
  - `details` (optional) 

- **Auslöser**  
  - Abschluss einer Qualitätsprüfung (In-Prozess oder Endtest) 

- **Kontext**  
  - `quality.check`  
  - `mrp.workorder`  
  - `mrp.production`  
  - Seriennummer (`stock.lot`) 

---

### 6.6 Event-Lebenszyklus

- Events werden im Code durch `UMHEventManager.create_*_event(...)` erzeugt.  
- Jedes Event wird mit `queue_event` zur internen Warteschlange hinzugefügt.  
- Der UMH-Client (`umh_client_sim` bzw. produktive Variante) liest die Pending Events, serialisiert sie zu JSON und sendet sie (z.B. via HTTP oder MQTT) an UMH/Digital Twin.
- Nach erfolgreichem Versand wird die Eventliste geleert (`clear_events`). 

---

## 7. Fazit und Weiterentwicklung

Mit dieser Dokumentation liegt eine durchgehende Sicht auf das Drohnen-Odoo-System vor: 
- **Einleitung** – Zielbild und Abnahmekriterien.  
- **Prozesssicht** – Wertströme und Activity-Diagramme von Anfrage bis Auslieferung.  
- **Ablaufsicht** – Sequenzen für SO, Beschaffung, MO-Kette, Qualität, Versand, UMH.  
- **Struktursicht** – Domänenmodell der wichtigsten Odoo-Entitäten.  
- **Architektursicht** – Odoo-Module, Shopfloor, UMH/Digital Twin, Energie.  
- **Eventmodell** – fünf klare Eventtypen mit definierter Payload. 

Auf dieser Basis lassen sich nun:

- Lasttests (500 MOs/Tag) definieren und dokumentiert ausführen.  
- Kanban/Reordering, Quality-Control-Points und Worker-Oberflächen in Odoo gezielt verfeinern.  
- Die Anbindung an einen realen UMH/Digital-Twin-Endpunkt (statt JSON-Dateidumps) implementieren. 
