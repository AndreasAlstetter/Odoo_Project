# cli.py
"""
Typer-CLI für das Odoo-Drohnen-Projekt.

Ziele:
- Vollständiger Setup-Prozess von 0 auf (sobald alle Daten vorhanden sind)
- Schrittweise Ausführung einzelner Teilaufgaben (Stammdaten, Prozesse, Schnittstellen)
- Dokumentation und Validierung über strukturierte Terminalausgabe

Die CLI ist so strukturiert, dass sie sowohl für:
- interaktive Tests (Einzelkommandos) als auch
- automatisierte End-to-End-Läufe (run-all, setup-all, prozesse demo-endtoend)
verwendet werden kann.

Top-Level-Gruppierungen:
- Hauptkommandos: Systemcheck, run-all, setup-all
- stammdaten: Importe/Setup für Produkte, BoMs, Lager, Lieferanten, Workcenter, Routings
- prozesse: End-to-End-Geschäftsprozesse (Sales, Purchase, Manufacturing, Inventory, Shipping, Produktion, End-to-End + UMH)
- tests: Test- und Demo-Skripte (End-to-End-File-Demo usw.)
"""



import typer

import datetime
import time

from config import ODOO_URL, DB_NAME, LOGIN, UMH_MASTERDATA_EXPORT_FILE, UMH_EVENTS_ENDTOEND_FILE, DATA_DIR, MQTT_BASE_TOPIC
from core import info, success, warning, error, debug
from odoo_api import OdooAPI

from importers.bom_importer import BOMImporter
from importers.structured_bom_importer import StructuredBOMImporter
from importers.stock_importer import StockImporter
from importers.supplier_importer import SupplierImporter
from importers.customer_importer import CustomerImporter
from importers.location_importer import LocationImporter
from importers.workcenter_importer import WorkcenterImporter
from importers.routing_importer import RoutingImporter
from importers.users_roles import UsersRolesImporter

from processes.sales_flow import SalesFlow
from processes.purchase_flow import PurchaseFlow
from processes.manufacturing_flow import ManufacturingFlow
from processes.shipping_flow import ShippingFlow
from processes.inventory_flow import InventoryFlow
from processes.production_flow import ProductionFlow

from integration.umh_events import UMHEventManager, EventType
from integration.umh_client_sim import UMHClientSimulator
from integration.umh_export_masterdata import export_masterdata

from config import REORDERING_CSV_PATH
from importers.reordering_rules import ReorderingRulesImporter

from processes.traceability import TraceabilityManager

from kpi.kpi_extractor import KpiExtractor
from messaging.mqtt_client import MqttClient

from core.logging_utils import info

# Zentrale Typer-App
app = typer.Typer(help="Odoo-Drohnen-Projekt: Komplettaufbau & Validierung")

prozesse_app = typer.Typer(help="Kommandos für End-to-End-Geschäftsprozesse.")
app.add_typer(prozesse_app, name="prozesse")

tests_app = typer.Typer(help="Test- und Demo-Skripte (End-to-End etc.).")
app.add_typer(tests_app, name="tests")

stammdaten_app = typer.Typer(
    help="Kommandos für Stammdaten-Importe (Produkte, BoMs, Lager, Lieferanten, Workcenter, Routings)."
)
app.add_typer(stammdaten_app, name="stammdaten")


def get_api(debug_enabled: bool = False) -> OdooAPI:
    """
    Erstellt eine OdooAPI-Instanz und führt den Login aus.

    Alle Kommandos verwenden diese Funktion, um sicherzustellen, dass
    die Verbindung konsistent aufgebaut wird.

    Raises:
    - RuntimeError, wenn die Verbindung nicht aufgebaut werden kann.
    """
    info("Stelle Verbindung zu Odoo her...")
    debug(
        "Odoo-Konfigurationsparameter",
        {
            "url": ODOO_URL,
            "db": DB_NAME,
            "user": LOGIN,
        },
        enabled=debug_enabled,
    )
    api = OdooAPI()
    # UID nur ausgeben, wenn vorhanden
    uid = getattr(api, "uid", None)
    if uid is not None:
        success(f"Login erfolgreich, UID = {uid}")
    else:
        success("Login erfolgreich.")
    return api


# ============================================================================
# Basis-Kommandos: System-Check & Login
# ============================================================================


@app.command()
def check_connection(
    debug_flag: bool = typer.Option(False, "--debug", help="Detailierte Debug-Ausgaben aktivieren."),
) -> None:
    """
    Prüft die Verbindung zu Odoo (Login-Test).
    """
    try:
        api = get_api(debug_enabled=debug_flag)
        users = api.search_read("res.users", [], ["id", "login"], limit=1)
        debug("Test-Read res.users", users, enabled=debug_flag)
        success("Verbindungstest erfolgreich abgeschlossen.")
    except Exception as exc:
        error(f"Verbindungstest fehlgeschlagen: {exc}")
        raise typer.Exit(code=1)


@app.command("run-all")
def run_all(
    variant: str = typer.Option(
        "spartan",
        "--variant",
        "-v",
        case_sensitive=False,
        help="Drohnenvariante für den Durchlauf (spartan | lightweight | balance).",
    ),
    debug_flag: bool = typer.Option(False, "--debug", help="Debug-Ausgaben aktivieren."),
) -> None:
    """
    Führt das gesamte Projekt in einem Lauf durch:
    Stammdaten → Routings → Lager → End-to-End-Prozesse → UMH-Exports.
    """
    variant = variant.lower().strip()
    if variant not in ("spartan", "lightweight", "balance"):
        error("Ungültige Variante. Erlaubt sind: spartan, lightweight, balance.")
        raise typer.Exit(code=1)

    # 0) Verbindungscheck
    info("==> Schritt 0: Verbindung prüfen")
    api = get_api(debug_enabled=debug_flag)

    # 1) Stammdaten / BoMs / Lieferanten / Lager / Workcenter / Routings
    info("==> Schritt 1: Stammdaten & BoMs")
    import_suppliers(debug_flag=debug_flag)
    import_bom_varianten(variant=variant, debug_flag=debug_flag)
    import_structured_boms(variant=variant, debug_flag=debug_flag)
    import_stock(debug_flag=debug_flag)
    setup_workcenters(debug_flag=debug_flag)
    # setup_routings(debug_flag=debug_flag)  # Odoo 19: mrp.routing nicht vorhanden

    # 2) Prozess-Demos (Sales, Purchase, Manufacturing, Inventory, Shipping)
    info("==> Schritt 2: Prozess-Demos")
    demo_sales(debug_flag=debug_flag)
    demo_purchase(debug_flag=debug_flag)
    demo_manufacturing(debug_flag=debug_flag)
    demo_inventory(debug_flag=debug_flag)
    demo_shipping(debug_flag=debug_flag)

    # 3) Produktions-Simulation mit UMH-Events
    info("==> Schritt 3: Produktionssimulation mit UMH-Events")
    demo_production_all()

    # 4) UMH-Masterdatenexport
    info("==> Schritt 4: UMH-Masterdaten exportieren")
    cli_export_umh_masterdata(output_file="umh_masterdata.json")

    # 5) End-to-End mit UMH-Events
    info("==> Schritt 5: End-to-End-Demo mit UMH-Events")
    demo_endtoend(debug_flag=debug_flag)

    success("Vollständiger run-all Durchlauf erfolgreich abgeschlossen.")

@app.command("run-all-variants")
def run_all_variants(
    debug_flag: bool = typer.Option(
        False,
        "--debug",
        help="Debug-Ausgaben aktivieren.",
    ),
) -> None:
    """
    Führt den vollständigen End-to-End-Durchlauf für alle Varianten aus:
    spartan → lightweight → balance.

    Pro Variante werden nacheinander ausgeführt:
    - Stammdaten/BoMs/Lager/Workcenter (über run-all)
    - Prozess-Demos (Sales, Purchase, Manufacturing, Inventory, Shipping)
    - Produktionssimulation
    - UMH-Masterdatenexport
    - End-to-End-Demo inkl. UMH-Events
    """
    variants = ["spartan", "lightweight", "balance"]

    for variant in variants:
        info(f"=== Starte vollständigen Durchlauf für Variante: {variant} ===")
        try:
            # Re-Use der bestehenden Logik
            run_all(
                variant=variant,
                debug_flag=debug_flag,
            )
            success(f"Durchlauf für Variante '{variant}' erfolgreich abgeschlossen.")
        except Exception as exc:
            error(f"Fehler im Durchlauf für Variante '{variant}': {exc}")
            # Je nach gewünschtem Verhalten:
            # - continue: nächste Variante trotzdem versuchen
            # - raise: Gesamtlauf abbrechen
            raise typer.Exit(code=1)

    success("run-all-variants: Alle Varianten (spartan, lightweight, balance) erfolgreich durchlaufen.")

# ============================================================================
# Stammdaten-Importe
# ============================================================================


@stammdaten_app.command("setup-locations")
def setup_locations(
    debug_flag: bool = typer.Option(False, "--debug", help="Debug-Ausgaben aktivieren."),
) -> None:
    """
    Stellt zentrale Lagerorte (Wareneingang, Hauptlager, Produktion, Versand) bereit.
    """
    info("Starte Einrichtung der zentralen Lagerorte...")
    api = get_api(debug_enabled=debug_flag)
    importer = LocationImporter(api)
    try:
        importer.setup_core_locations()
    except Exception as exc:
        error(f"Fehler bei der Lagerort-Einrichtung: {exc}")
        raise typer.Exit(code=1)


@stammdaten_app.command("import-customers")
def import_customers(
    csv_path: str = typer.Option(
        None,
        "--csv-path",
        help="Pfad zur Kunden-CSV (Standard: data/csv_raw/customers.csv).",
    ),
    debug_flag: bool = typer.Option(False, "--debug", help="Debug-Ausgaben aktivieren."),
) -> None:
    """Importiert Kundenstammdaten aus einer CSV-Datei."""
    api = get_api(debug_enabled=debug_flag)

    from importers.customer_importer import CustomerImporter
    from config import CUSTOMERS_CSV_PATH

    effective_path = csv_path or CUSTOMERS_CSV_PATH

    import os
    if not os.path.exists(effective_path):
        error(f"Kunden-CSV nicht gefunden: {effective_path}")
        raise typer.Exit(code=1)

    importer = CustomerImporter(api, effective_path)
    try:
        count = importer.import_customers()
        success(f"Kundenimport abgeschlossen. Verarbeitete Kunden: {count}.")
    except Exception as exc:
        error(f"Fehler beim Kundenimport: {exc}")
        raise typer.Exit(code=1)



@stammdaten_app.command("import-bom-varianten")
def import_bom_varianten(
    variant: str = typer.Option(
        "spartan",
        "--variant",
        "-v",
        case_sensitive=False,
        help="Drohnenvariante: spartan | lightweight | balance.",
    ),
    debug_flag: bool = typer.Option(False, "--debug", help="Debug-Ausgaben aktivieren."),
) -> None:
    """
    Importiert Mengenstücklisten (einfache BoMs) für die angegebene Drohnenvariante.
    """
    variant = variant.lower().strip()
    if variant not in ("spartan", "lightweight", "balance"):
        error("Ungültige Variante. Erlaubt sind: spartan, lightweight, balance.")
        raise typer.Exit(code=1)

    info(f"Starte Import der Mengenstückliste für Variante '{variant}'...")
    api = get_api(debug_enabled=debug_flag)
    importer = BOMImporter(api)
    try:
        importer.import_variant(variant)
        success(f"Import der Mengenstückliste für '{variant}' abgeschlossen.")
    except Exception as exc:
        error(f"Fehler beim BoM-Import für '{variant}': {exc}")
        raise typer.Exit(code=1)


@stammdaten_app.command("import-structured-boms")
def import_structured_boms(
    variant: str = typer.Option(
        "spartan",
        "--variant",
        "-v",
        case_sensitive=False,
        help="Drohnenvariante: spartan | lightweight | balance.",
    ),
    debug_flag: bool = typer.Option(False, "--debug", help="Debug-Ausgaben aktivieren."),
) -> None:
    """
    Importiert strukturierte Stücklisten (mehrstufige BoMs) für Eigenfertigungsartikel.
    """
    variant = variant.lower().strip()
    if variant not in ("spartan", "lightweight", "balance"):
        error("Ungültige Variante. Erlaubt sind: spartan, lightweight, balance.")
        raise typer.Exit(code=1)

    info(f"Starte Import der strukturierten Stücklisten für Variante '{variant}'...")
    api = get_api(debug_enabled=debug_flag)
    importer = StructuredBOMImporter(api)
    try:
        importer.import_eigenfertigung_boms(variant)
        success(f"Import der strukturierten Stücklisten für '{variant}' abgeschlossen.")
    except AttributeError:
        error(
            "Die Methode 'import_eigenfertigung_boms' existiert nicht "
            "im StructuredBOMImporter. Bitte Modul prüfen/anpassen."
        )
        raise typer.Exit(code=1)
    except Exception as exc:
        error(f"Fehler beim Import strukturierter BoMs für '{variant}': {exc}")
        raise typer.Exit(code=1)


@stammdaten_app.command("import-suppliers")
def import_suppliers(
    debug_flag: bool = typer.Option(False, "--debug", help="Debug-Ausgaben aktivieren."),
) -> None:
    """
    Importiert Lieferantenstammdaten aus `lieferanten.csv`.
    """
    info("Starte Import der Lieferanten-Stammdaten...")
    api = get_api(debug_enabled=debug_flag)
    importer = SupplierImporter(api)
    try:
        created, updated = importer.import_suppliers()
        success(f"Lieferantenimport abgeschlossen. Neu: {created}, aktualisiert: {updated}.")
    except Exception as exc:
        error(f"Fehler beim Lieferantenimport: {exc}")
        raise typer.Exit(code=1)


@stammdaten_app.command("import-stock")
def import_stock(
    debug_flag: bool = typer.Option(False, "--debug", help="Debug-Ausgaben aktivieren."),
) -> None:
    """
    Importiert Basislagerbestände aus `lagerdaten.csv`.
    """
    info("Starte Import der Lagerbestände (Basis)...")
    api = get_api(debug_enabled=debug_flag)
    importer = StockImporter(api)
    try:
        importer.import_quantities()
        success("Lagerbestände erfolgreich importiert.")
    except Exception as exc:
        error(f"Fehler beim Lagerbestandsimport: {exc}")
        raise typer.Exit(code=1)


@stammdaten_app.command("setup-workcenters")
def setup_workcenters(
    debug_flag: bool = typer.Option(False, "--debug", help="Debug-Ausgaben aktivieren."),
) -> None:
    """
    Legt zentrale Arbeitsplätze (Workcenter) aus data/workcenters.csv an/aktualisiert sie.
    """
    info("Starte Einrichtung der Arbeitsplätze (Workcenter)...")
    api = get_api(debug_enabled=debug_flag)
    importer = WorkcenterImporter(api)
    try:
        count = importer.import_workcenters()
        success(f"Workcenter-Setup abgeschlossen. Verarbeitete Workcenter: {count}.")
    except Exception as exc:
        error(f"Fehler beim Workcenter-Setup: {exc}")
        raise typer.Exit(code=1)


@stammdaten_app.command("setup-routings")
def setup_routings(
    debug_flag: bool = typer.Option(False, "--debug", help="Debug-Ausgaben aktivieren."),
) -> None:
    """
    Legt Routings je Variante an (sofern das Modell in der Odoo-Version verfügbar ist).
    """
    info("Starte Einrichtung der Routings je Variante...")
    api = get_api(debug_enabled=debug_flag)
    importer = RoutingImporter(api)
    try:
        count = importer.import_routings()
        success(f"Routing-Setup abgeschlossen. Varianten mit Routing: {count}.")
    except Exception as exc:
        warning(f"Routing-Setup übersprungen (Modell mrp.routing fehlt?): {exc}")


@stammdaten_app.command("setup-users-roles")
def setup_users_roles(
    debug_flag: bool = typer.Option(False, "--debug", help="Debug-Ausgaben aktivieren."),
) -> None:
    """
    Legt zentrale Demo-Benutzer mit typischen Rollen an, basierend auf
    data/csv_raw/users_roles.csv.
    """
    api = get_api(debug_enabled=debug_flag)
    importer = UsersRolesImporter(api)

    try:
        count = importer.import_from_csv()
        success(f"Benutzer-Setup abgeschlossen. Verarbeitete Benutzer: {count}.")
    except Exception as exc:
        error(f"Fehler beim Benutzer-/Rollen-Setup: {exc}")
        raise typer.Exit(code=1)
    

@stammdaten_app.command("import-all")
def import_all_masterdata(
    variant: str = typer.Option(
        "spartan",
        "--variant",
        "-v",
        case_sensitive=False,
        help="Drohnenvariante: spartan | lightweight | balance.",
    ),
    debug_flag: bool = typer.Option(False, "--debug", help="Debug-Ausgaben aktivieren."),
) -> None:
    """
    Importiert alle wesentlichen Stammdaten:
    Lieferanten, Kunden, Produkte, BoMs (einfach/strukturiert), Lagerbestände,
    Workcenter und Reordering-Regeln.
    """
    variant = variant.lower().strip()
    if variant not in ("spartan", "lightweight", "balance"):
        error("Ungültige Variante. Erlaubt sind: spartan, lightweight, balance.")
        raise typer.Exit(code=1)

    info(f"Starte Masterdaten-Import für Variante '{variant}'...")
    api = get_api(debug_enabled=debug_flag)

    SupplierImporter(api).import_suppliers()
    CustomerImporter(api).import_customers()
    try:
        from importers.product_importer import ProductImporter
        ProductImporter(api).import_products()
    except Exception:
        warning("Produktimporter nicht verfügbar oder Fehler – bitte prüfen.")

    BOMImporter(api).import_variant(variant)
    try:
        StructuredBOMImporter(api).import_eigenfertigung_boms(variant)
    except AttributeError:
        warning(
            "StructuredBOMImporter.import_eigenfertigung_boms nicht vorhanden – strukturierte BoMs werden übersprungen."
        )

    StockImporter(api).import_quantities()
    WorkcenterImporter(api).import_workcenters()
    try:
        ReorderingRulesImporter(api).import_from_csv(REORDERING_CSV_PATH)
    except Exception:
        warning("Reordering-Regeln konnten nicht importiert werden – config/CSV prüfen.")

    success(f"Masterdaten-Import für Variante '{variant}' abgeschlossen.")

# ============================================================================
# High-Level-Szenario: setup-all
# ============================================================================


@app.command("setup-all")
def setup_all(
    variant: str = typer.Option(
        "spartan",
        "--variant",
        "-v",
        case_sensitive=False,
        help="Drohnenvariante für die vollständige Einrichtung (spartan | lightweight | balance).",
    ),
    debug_flag: bool = typer.Option(False, "--debug", help="Debug-Ausgaben aktivieren."),
) -> None:
    """
    Führt einen vollständigen Setup-Lauf für Odoo durch (Work-in-Progress).
    """
    variant = variant.lower().strip()
    if variant not in ("spartan", "lightweight", "balance"):
        error("Ungültige Variante. Erlaubt sind: spartan, lightweight, balance.")
        raise typer.Exit(code=1)

    info("Starte vollständigen Setup-Lauf (aktuelle Ausbaustufe)...")

    # 1) Verbindung testen
    api = get_api(debug_enabled=debug_flag)
    debug("Erfolgreich eingeloggt, beginne mit Stammdaten.", enabled=debug_flag)

    # 2) Lagerorte
    info("==> Schritt 0: Zentrale Lagerorte einrichten")
    loc_importer = LocationImporter(api)
    try:
        loc_importer.setup_core_locations()
    except Exception as exc:
        error(f"Fehler im Schritt 'Lagerorte': {exc}")
        raise typer.Exit(code=1)

    # 3) Lieferanten
    info("==> Schritt 1: Lieferanten importieren")
    importer_sup = SupplierImporter(api)
    try:
        created, updated = importer_sup.import_suppliers()
        success(f"Lieferantenimport abgeschlossen. Neu: {created}, aktualisiert: {updated}.")
    except Exception as exc:
        error(f"Fehler im Schritt 'Lieferantenimport': {exc}")
        raise typer.Exit(code=1)

    # 4) BoMs (einfache Mengenstückliste)
    info("==> Schritt 2: Mengenstückliste importieren")
    importer_bom = BOMImporter(api)
    try:
        importer_bom.import_variant(variant)
        success(f"Mengenstückliste für '{variant}' erfolgreich importiert.")
    except Exception as exc:
        error(f"Fehler im Schritt 'Mengenstückliste': {exc}")
        raise typer.Exit(code=1)

    # 5) strukturierte BoMs
    info("==> Schritt 3: Strukturierte BoMs (Eigenfertigung) importieren")
    importer_struct = StructuredBOMImporter(api)
    try:
        importer_struct.import_eigenfertigung_boms(variant)
        success(f"Strukturierte BoMs für '{variant}' erfolgreich importiert.")
    except AttributeError:
        warning(
            "StructuredBOMImporter hat keine Methode 'import_eigenfertigung_boms'. "
            "Bitte Modul anpassen. Schritt wird übersprungen."
        )
    except Exception as exc:
        error(f"Fehler im Schritt 'strukturierte BoMs': {exc}")
        raise typer.Exit(code=1)

    # 6) Lagerbestände
    info("==> Schritt 4: Basislagerbestände importieren")
    importer_stock = StockImporter(api)
    try:
        importer_stock.import_quantities()
        success("Basislagerbestände erfolgreich importiert.")
    except Exception as exc:
        error(f"Fehler im Schritt 'Lagerbestände': {exc}")
        raise typer.Exit(code=1)

    success("Setup-all (aktuelle Ausbaustufe) erfolgreich abgeschlossen.")


# ============================================================================
# Prozess-Demos
# ============================================================================


@prozesse_app.command("demo-sales")
def demo_sales(
    debug_flag: bool = typer.Option(False, "--debug", help="Debug-Ausgaben aktivieren."),
) -> None:
    """Führt die Demo Angebot → Auftrag mit mehreren Testfällen durch."""
    api = get_api(debug_enabled=debug_flag)
    flow = SalesFlow(api)
    try:
        flow.run_demo_quotes_to_orders()
    except Exception as exc:
        error(f"Fehler in demo-sales: {exc}")
        raise typer.Exit(code=1)



@prozesse_app.command("export-umh-masterdata")
def cli_export_umh_masterdata(
    output_file: str = typer.Option(
        None,
        "--output",
        "-o",
        help="Zieldatei für UMH-Stammdaten-Export (Standard: data/export/umh_masterdata.json).",
    ),
    debug_flag: bool = typer.Option(
        False,
        "--debug",
        help="Debug-Ausgaben aktivieren.",
    ),
) -> None:
    """
    Exportiert UMH-Stammdaten (Produkte, BoMs, Routing) in eine JSON-Datei.
    """
    # optional: Login nur für Konsistenz/Debug (export_masterdata nutzt eigene OdooAPI)
    get_api(debug_enabled=debug_flag)

    path = output_file or UMH_MASTERDATA_EXPORT_FILE
    try:
        export_masterdata(path)
        success(f"UMH-Stammdaten nach {path} exportiert.")
    except Exception as exc:
        error(f"Fehler beim UMH-Masterdaten-Export: {exc}")
        raise typer.Exit(code=1)



@prozesse_app.command("demo-purchase")
def demo_purchase(
    debug_flag: bool = typer.Option(False, "--debug", help="Debug-Ausgaben aktivieren."),
) -> None:
    """
    Führt die Demo 'RFQ → Bestellung → Wareneingang' durch.
    """
    api = get_api(debug_enabled=debug_flag)
    flow = PurchaseFlow(api)
    try:
        flow.run_demo_purchasing()
    except Exception as exc:
        error(f"Fehler in demo-purchase: {exc}")
        raise typer.Exit(code=1)


@prozesse_app.command("demo-production-all")
def demo_production_all(
    debug_flag: bool = typer.Option(False, "--debug", help="Debug-Ausgaben aktivieren."),
) -> None:
    api = get_api(debug_enabled=debug_flag)
    flow = ProductionFlow(api)
    flow.run_demo_all_variants()



@prozesse_app.command("demo-manufacturing")
def demo_manufacturing(
    debug_flag: bool = typer.Option(False, "--debug", help="Debug-Ausgaben aktivieren."),
) -> None:
    """
    Führt die Demo-Kette 'Auftrag → MO → Fertigmeldung' durch.
    """
    api = get_api(debug_enabled=debug_flag)
    sales = SalesFlow(api)
    manuf = ManufacturingFlow(api)
    try:
        orders = sales.run_demo_quotes_to_orders()
        manuf.run_demo_mo_chain(orders)
    except Exception as exc:
        error(f"Fehler in demo-manufacturing: {exc}")
        raise typer.Exit(code=1)


@prozesse_app.command("demo-inventory")
def demo_inventory(
    debug_flag: bool = typer.Option(False, "--debug", help="Debug-Ausgaben aktivieren."),
) -> None:
    """
    Führt eine kombinierte Demo für Inventur und Ausschuss durch.
    """
    api = get_api(debug_enabled=debug_flag)
    inv = InventoryFlow(api)
    try:
        inv.run_demo_inventory_and_scrap()
    except Exception as exc:
        error(f"Fehler in demo-inventory: {exc}")
        raise typer.Exit(code=1)


@prozesse_app.command("demo-shipping")
def demo_shipping(
    debug_flag: bool = typer.Option(False, "--debug", help="Debug-Ausgaben aktivieren."),
) -> None:
    """
    Führt die Demo 'Versand aus Verkaufsauftrag' durch.
    """
    api = get_api(debug_enabled=debug_flag)
    sales = SalesFlow(api)
    ship = ShippingFlow(api)
    try:
        orders = sales.run_demo_quotes_to_orders()
        ship.run_demo_shipping(orders)
    except Exception as exc:
        error(f"Fehler in demo-shipping: {exc}")
        raise typer.Exit(code=1)


@prozesse_app.command("demo-endtoend")
def demo_endtoend(
    debug_flag: bool = typer.Option(False, "--debug", help="Debug-Ausgaben aktivieren."),
) -> None:
    """
    End-to-End-Demo: Verkauf → Fertigung → Einkauf → Inventur/Ausschuss → Versand → UMH-Events.
    """
    api = get_api(debug_enabled=debug_flag)

    sales = SalesFlow(api)
    manuf = ManufacturingFlow(api)
    purch = PurchaseFlow(api)
    inv = InventoryFlow(api)
    ship = ShippingFlow(api)

    umh_mgr = UMHEventManager()
    umh_client = UMHClientSimulator(output_file=UMH_EVENTS_ENDTOEND_FILE)
    try:
        info("Starte End-to-End-Demo...")

        # 1) Verkauf
        orders = sales.run_demo_quotes_to_orders()

        # 2) Fertigung
        mo_ids = manuf.run_demo_mo_chain(orders)

        # 3) Einkauf
        purch.run_demo_purchasing()

        # 4) Inventur & Ausschuss
        inv.run_demo_inventory_and_scrap()

        # 5) Versand
        ship.run_demo_shipping(orders)

        # 6) UMH-Events erzeugen (vereinfachtes Beispiel)
        for mo_id in mo_ids:
            evt = umh_mgr.create_mo_event(mo_id, EventType.MO_COMPLETED)
            umh_mgr.queue_event(evt)

        # Events in Datei „senden“
        events_dicts = [e.to_dict() for e in umh_mgr.get_pending_events()]
        umh_client.send_events_batch(events_dicts)
        umh_client.export_to_file()

        success("End-to-End-Demo inkl. UMH-Events (Datei umh_events_endtoend.json) abgeschlossen.")
    except Exception as exc:
        error(f"Fehler in demo-endtoend: {exc}")
        raise typer.Exit(code=1)

@prozesse_app.command("import-reordering-rules")
def import_reordering_rules(
    csv_path: str = typer.Option(
        None,
        "--csv",
        help="Pfad zur CSV-Datei mit Reordering-Regeln "
             "(Standard: REORDERING_CSV_PATH aus config.py).",
    ),
    debug_flag: bool = typer.Option(
        False, "--debug", help="Debug-Ausgaben aktivieren."
    ),
) -> None:
    """
    Importiert Reordering-/Mindestbestandsregeln aus einer CSV-Datei
    (product_name, location_name, min_qty, max_qty) in
    stock.warehouse.orderpoint.
    """
    api = get_api(debug_enabled=debug_flag)
    importer = ReorderingRulesImporter(api)

    path = csv_path or REORDERING_CSV_PATH
    info(f"Starte Reordering-Import aus {path}...")
    ok = importer.import_from_csv(path)
    if ok:
        success("Reordering-Regeln erfolgreich importiert.")

@prozesse_app.command("check-reordering-status")
def check_reordering_status(
    debug_flag: bool = typer.Option(
        False, "--debug", help="Debug-Ausgaben aktivieren."
    ),
) -> None:
    """
    Zeigt Reordering Rules (Min/Max) und aktuelle Verfügbarkeiten aus stock.quant an.
    """
    api = get_api(debug_enabled=debug_flag)
    importer = ReorderingRulesImporter(api)
    importer.print_reordering_status()

@prozesse_app.command("trace-all-products")
def trace_all_products(
    debug_flag: bool = typer.Option(False, "--debug", help="Debug-Ausgaben aktivieren."),
) -> None:
    """
    Erzeugt einfache Traceability-Informationen für alle Produkte:
    Fertigungsaufträge und zugehörige Lieferungen.
    """
    api = get_api(debug_enabled=debug_flag)
    tm = TraceabilityManager(api)

    products = api.search_read(
        "product.product",
        [],
        ["id", "name"],
        limit=200,  # bei Bedarf erhöhen oder filtern
    )
    if not products:
        info("Keine Produkte gefunden.")
        return

    for p in products:
        pid = p["id"]
        name = p.get("name", "")
        chain = tm.get_traceability_chain(pid)
        mos = len(chain.get("mos", []))
        dels = len(chain.get("deliveries", []))
        info(f"Traceability für Produkt '{name}' (ID {pid}): {mos} MOs, {dels} Lieferungen.")

@prozesse_app.command("assign-serial")
def assign_serial(
    product_name: str = typer.Argument(..., help="Produktname in Odoo."),
    serial: str = typer.Argument(..., help="Seriennummer (Lot-Name)."),
    debug_flag: bool = typer.Option(False, "--debug", help="Debug-Ausgaben aktivieren."),
) -> None:
    """
    Legt eine Seriennummer (stock.lot) für ein Produkt an oder liefert die bestehende zurück.
    """
    api = get_api(debug_enabled=debug_flag)
    tm = TraceabilityManager(api)

    prod = api.search_read(
        "product.product",
        [["name", "=", product_name]],
        ["id"],
        limit=1,
    )
    if not prod:
        error(f"Produkt '{product_name}' nicht gefunden.")
        raise typer.Exit(code=1)

    product_id = prod[0]["id"]
    lot_id = tm.assign_serial_number(product_id, serial)
    if lot_id is None:
        error("Seriennummer konnte nicht angelegt/zugeordnet werden.")
        raise typer.Exit(code=1)

    success(f"Seriennummer '{serial}' für Produkt '{product_name}' verwendet (Lot-ID {lot_id}).")

@prozesse_app.command("demo-reordering-purchase")
def demo_reordering_purchase(
    product_name: str = typer.Option(
        "Akku",
        "--product",
        "-p",
        help="Produktname mit Reordering Rule (z. B. Akku).",
    ),
    debug_flag: bool = typer.Option(
        False,
        "--debug",
        help="Debug-Ausgaben aktivieren.",
    ),
) -> None:
    """
    Demo: Reordering-Status für ein Produkt prüfen und einen einfachen Einkaufsprozess ausführen.
    """
    api = get_api(debug_enabled=debug_flag)
    purch = PurchaseFlow(api)
    rr_importer = ReorderingRulesImporter(api)

    # 1) Produkt suchen
    prod = api.search_read(
        "product.product",
        [["name", "=", product_name]],
        ["id", "name"],
        limit=1,
    )
    if not prod:
        error(f"Produkt '{product_name}' nicht gefunden.")
        raise typer.Exit(code=1)

    product_id = prod[0]["id"]
    info(f"Starte Reordering/Einkaufs-Demo für Produkt '{product_name}' (ID {product_id})...")

    # 2) Reordering-Status für alle Produkte anzeigen (inkl. Zielprodukt)
    rr_importer.print_reordering_status()

    # 3) Einkaufsszenario ausführen (nutzt deine bestehende Purchase-Demo-Logik)
    info("Starte Einkaufs-Demo (RFQ → Bestellung → Wareneingang)...")
    purch.run_demo_purchasing()
    success("Einkaufs-Demo abgeschlossen.")

    # 4) Reordering-Status erneut anzeigen
    info("Reordering-Status nach Einkaufs-Demo:")
    rr_importer.print_reordering_status()

@prozesse_app.command("check-reordering-status-location")
def check_reordering_status_location(
    location: str = typer.Option("WH/Stock", "--location", "-l", help="Lagerort complete_name."),
    debug_flag: bool = typer.Option(False, "--debug", help="Debug-Ausgaben aktivieren."),
) -> None:
    api = get_api(debug_enabled=debug_flag)
    importer = ReorderingRulesImporter(api)
    importer.print_reordering_status_for_location(location)


# cli.py (Ausschnitt)
@prozesse_app.command("push-kpis-mqtt")
def push_kpis_mqtt(
    days: int = typer.Option(7, "--days", help="Zeitraum für zeitbasierte KPIs."),
    debug_flag: bool = typer.Option(False, "--debug", help="Debug-Ausgaben aktivieren."),
) -> None:
    """
    Liest aggregierte Rohdaten aus Odoo und sendet je KPI eine kompakte Message
    auf das Topic ttz-leipheim/odoo/kpi/data.
    """
    api = get_api(debug_enabled=debug_flag)
    from kpi.kpi_extractor import KpiExtractor
    from messaging.mqtt_client import MqttClient
    import time

    extractor = KpiExtractor(api)
    mqtt_client = MqttClient()
    mqtt_client.connect()

    ts = int(round(time.time() * 1000))

    # 1) Output aggregiert je Produkt
    out_agg = extractor.get_output_aggregated(days=days)
    mqtt_client.publish_json(
        {
            "timestamp": ts,
            "source": "odoo",
            "event_type": "output_per_product_agg",
            "window_days": out_agg["days"],
            "data": out_agg["per_product"],
        }
    )

    # 2) Zykluszeit-Basis aggregiert je Produkt
    cycle_agg = extractor.get_cycle_time_aggregated(days=days)
    mqtt_client.publish_json(
        {
            "timestamp": ts,
            "source": "odoo",
            "event_type": "cycle_time_per_product_agg",
            "window_days": cycle_agg["days"],
            "data": cycle_agg["per_product"],
        }
    )

    # 3) MO-Lead-Time je MO
    mo_lt_agg = extractor.get_mo_lead_time_aggregated(days=max(days, 30))
    mqtt_client.publish_json(
        {
            "timestamp": ts,
            "source": "odoo",
            "event_type": "mo_lead_time_agg",
            "window_days": mo_lt_agg["days"],
            "data": mo_lt_agg["records"],
        }
    )

    # 4) Scrap aggregiert je Produkt
    scrap_agg = extractor.get_scrap_aggregated(days=days)
    mqtt_client.publish_json(
        {
            "timestamp": ts,
            "source": "odoo",
            "event_type": "scrap_per_product_agg",
            "window_days": scrap_agg["days"],
            "data": scrap_agg["per_product"],
        }
    )

    # 5) Revenue aggregiert
    rev_agg = extractor.get_revenue_aggregated(days=max(days, 30))
    mqtt_client.publish_json(
        {
            "timestamp": ts,
            "source": "odoo",
            "event_type": "revenue_agg",
            "window_days": rev_agg["days"],
            "data": {
                "revenue_total": rev_agg["revenue_total"],
                "records_count": rev_agg["records_count"],
            },
        }
    )

    # 6) Orders Lead-Time-Basis
    lt_orders_agg = extractor.get_lead_time_orders_aggregated(days=max(days, 30))
    mqtt_client.publish_json(
        {
            "timestamp": ts,
            "source": "odoo",
            "event_type": "order_lead_time_agg",
            "window_days": lt_orders_agg["days"],
            "data": lt_orders_agg["records"],
        }
    )

    # 7) Inventory-Snapshot aggregiert je Produkt
    inv_agg = extractor.get_inventory_aggregated()
    mqtt_client.publish_json(
        {
            "timestamp": ts,
            "source": "odoo",
            "event_type": "inventory_snapshot_agg",
            "window_days": days,
            "data": inv_agg["per_product"],
        }
    )



@prozesse_app.command("check-workorders")
def check_workorders(
    days: int = typer.Option(2, "--days"),
    debug_flag: bool = typer.Option(False, "--debug"),
) -> None:
    api = get_api(debug_enabled=debug_flag)
    from debug.check_workorders import check_recent_workorders

    check_recent_workorders(api, days=days)

@prozesse_app.command("check-scrap")
def check_scrap(
    days: int = typer.Option(7, "--days"),
    debug_flag: bool = typer.Option(False, "--debug"),
) -> None:
    api = get_api(debug_enabled=debug_flag)
    from debug.check_scrap import check_recent_scrap

    check_recent_scrap(api, days=days)

@prozesse_app.command("check-mos")
def check_mos(
    days: int = typer.Option(7, "--days"),
    debug_flag: bool = typer.Option(False, "--debug"),
) -> None:
    api = get_api(debug_enabled=debug_flag)
    from debug.check_mos import check_recent_mos

    check_recent_mos(api, days=days)

@prozesse_app.command("check-orders")
def check_orders(
    days: int = typer.Option(7, "--days"),
    debug_flag: bool = typer.Option(False, "--debug"),
) -> None:
    api = get_api(debug_enabled=debug_flag)
    from debug.check_orders import check_recent_orders

    check_recent_orders(api, days=days)

# cli.py – neues Kommando für MO-Events

@prozesse_app.command("push-mo-events-mqtt")
def push_mo_events_mqtt(
    hours: int = typer.Option(1, "--hours", help="Zeitraum rückwärts für MO-Events."),
    debug_flag: bool = typer.Option(False, "--debug", help="Debug-Ausgaben aktivieren."),
) -> None:
    """
    Liest MOs aus den letzten Stunden und sendet Start/Ende-Events an MQTT.
    (Polling-Variante, z. B. als Cron-Job nutzbar.)
    """
    api = get_api(debug_enabled=debug_flag)
    mqtt_client = MqttClient()
    mqtt_client.connect()

    now_utc = datetime.utcnow()
    date_from = now_utc - datetime.timedelta(hours=hours)
    date_from_str = date_from.strftime("%Y-%m-%d %H:%M:%S")

    # MOs im relevanten Zeitraum holen (vereinfachte Filterung über date_finished/date_planned_start)
    mos = api.search_read(
        "mrp.production",
        [
            "|",
            ["date_planned_start", ">=", date_from_str],
            ["date_finished", ">=", date_from_str],
        ],
        ["id", "name", "product_id", "product_qty", "state", "date_planned_start", "date_finished"],
        limit=500,
    )

    ts = int(round(time.time() * 1000))

    for mo in mos:
        product = mo.get("product_id") or [None, ""]
        data_common = {
            "mo_id": mo["id"],
            "mo_name": mo.get("name"),
            "product_id": product[0],
            "product_name": product[1],
            "qty": float(mo.get("product_qty", 0.0) or 0.0),
        }

        # MO-Start-Event, wenn geplanter Start im Zeitfenster
        if mo.get("date_planned_start") and mo["date_planned_start"] >= date_from_str:
            event_start = {
                "timestamp": ts,
                "source": "odoo",
                "event_type": "mo_started",
                "entity": "mrp.production",
                "entity_id": mo["id"],
                "data": {
                    **data_common,
                    "planned_start": mo["date_planned_start"],
                    "state": mo.get("state"),
                },
            }
            mqtt_client.publish_event(event_start)

        # MO-Ende-Event, wenn date_finished im Zeitfenster
        if mo.get("date_finished") and mo["date_finished"] >= date_from_str:
            event_end = {
                "timestamp": ts,
                "source": "odoo",
                "event_type": "mo_finished",
                "entity": "mrp.production",
                "entity_id": mo["id"],
                "data": {
                    **data_common,
                    "date_finished": mo["date_finished"],
                    "state": mo.get("state"),
                },
            }
            mqtt_client.publish_event(event_end)

    info(f"MO-Events für die letzten {hours} Stunden an MQTT gesendet.")

@prozesse_app.command("push-stock-events-mqtt")
def push_stock_events_mqtt(
    hours: int = typer.Option(1, "--hours", help="Zeitraum rückwärts für Bestands-Events."),
    debug_flag: bool = typer.Option(False, "--debug", help="Debug-Ausgaben aktivieren."),
) -> None:
    """
    Liest abgeschlossene Lagerbewegungen und sendet Stock-Change-Events an MQTT.
    """
    api = get_api(debug_enabled=debug_flag)
    mqtt_client = MqttClient()
    mqtt_client.connect()

    now_utc = datetime.utcnow()
    date_from = now_utc - datetime.timedelta(hours=hours)
    date_from_str = date_from.strftime("%Y-%m-%d %H:%M:%S")

    moves = api.search_read(
        "stock.move",
        [
            ["state", "=", "done"],
            ["date", ">=", date_from_str],
        ],
        ["id", "product_id", "product_uom_qty", "location_id", "location_dest_id", "date", "reference"],
        limit=500,
    )

    ts = int(round(time.time() * 1000))

    for mv in moves:
        prod = mv.get("product_id") or [None, ""]
        loc_from = mv.get("location_id") or [None, ""]
        loc_to = mv.get("location_dest_id") or [None, ""]
        event = {
            "timestamp": ts,
            "source": "odoo",
            "event_type": "stock_change",
            "entity": "stock.move",
            "entity_id": mv["id"],
            "data": {
                "product_id": prod[0],
                "product_name": prod[1],
                "qty": float(mv.get("product_uom_qty", 0.0) or 0.0),
                "location_from_id": loc_from[0],
                "location_from_name": loc_from[1],
                "location_to_id": loc_to[0],
                "location_to_name": loc_to[1],
                "date": mv.get("date"),
                "reference": mv.get("reference"),
            },
        }
        mqtt_client.publish_event(event)

    info(f"Stock-Events für die letzten {hours} Stunden an MQTT gesendet.")

@prozesse_app.command("push-delivery-events-mqtt")
def push_delivery_events_mqtt(
    hours: int = typer.Option(1, "--hours", help="Zeitraum rückwärts für Liefer-Events."),
    debug_flag: bool = typer.Option(False, "--debug", help="Debug-Ausgaben aktivieren."),
) -> None:
    """
    Liest abgeschlossene Lieferungen (Warenausgänge) und sendet Delivery-Events an MQTT.
    """
    api = get_api(debug_enabled=debug_flag)
    mqtt_client = MqttClient()
    mqtt_client.connect()

    now_utc = datetime.utcnow()
    date_from = now_utc - datetime.timedelta(hours=hours)
    date_from_str = date_from.strftime("%Y-%m-%d %H:%M:%S")

    pickings = api.search_read(
        "stock.picking",
        [
            ["state", "=", "done"],
            ["picking_type_code", "=", "outgoing"],
            ["date_done", ">=", date_from_str],
        ],
        ["id", "name", "origin", "date_done"],
        limit=300,
    )

    ts = int(round(time.time() * 1000))

    for pk in pickings:
        event = {
            "timestamp": ts,
            "source": "odoo",
            "event_type": "delivery_done",
            "entity": "stock.picking",
            "entity_id": pk["id"],
            "data": {
                "picking_name": pk.get("name"),
                "origin": pk.get("origin"),  # meist Sales-Order-Name
                "date_done": pk.get("date_done"),
            },
        }
        mqtt_client.publish_event(event)

    info(f"Delivery-Events für die letzten {hours} Stunden an MQTT gesendet.")

@prozesse_app.command("export-all-analytics")
def export_all_analytics(
    days: int = typer.Option(7, "--days", help="Zeitraum für zeitbasierte KPIs."),
    debug_flag: bool = typer.Option(False, "--debug", help="Debug-Ausgaben aktivieren."),
) -> None:
    """
    Führt alle Analytics-/Export-Schritte aus:
    - UMH-Masterdaten
    - End-to-End-Demo mit UMH-Events
    - KPI-Export auf MQTT
    """
    get_api(debug_enabled=debug_flag)

    info("==> Export UMH-Masterdaten")
    cli_export_umh_masterdata(debug_flag=debug_flag)

    info("==> End-to-End-Demo mit UMH-Events")
    demo_endtoend(debug_flag=debug_flag)

    info("==> KPI-Export auf MQTT")
    push_kpis_mqtt(days=days, debug_flag=debug_flag)

    success("export-all-analytics abgeschlossen.")


@prozesse_app.command("demo-all")
def demo_all(
    include_purchase: bool = typer.Option(True, "--purchase/--no-purchase"),
    include_inventory: bool = typer.Option(True, "--inventory/--no-inventory"),
    include_shipping: bool = typer.Option(True, "--shipping/--no-shipping"),
    debug_flag: bool = typer.Option(False, "--debug", help="Debug-Ausgaben aktivieren."),
) -> None:
    """
    Führt alle Kernprozesse als Demos aus:
    Sales → Manufacturing → (optional) Purchase → Inventory → Shipping.
    """
    api = get_api(debug_enabled=debug_flag)
    sales = SalesFlow(api)
    manuf = ManufacturingFlow(api)
    purch = PurchaseFlow(api)
    inv = InventoryFlow(api)
    ship = ShippingFlow(api)

    info("==> Sales-Demo (Angebot → Auftrag)")
    orders = sales.run_demo_quotes_to_orders()

    info("==> Manufacturing-Demo (Auftrag → MOs → Fertigmeldung)")
    manuf.run_demo_mo_chain(orders)

    if include_purchase:
        info("==> Purchase-Demo (RFQ → Bestellung → Wareneingang)")
        purch.run_demo_purchasing()

    if include_inventory:
        info("==> Inventory-Demo (Inventur + Ausschuss)")
        inv.run_demo_inventory_and_scrap()

    if include_shipping:
        info("==> Shipping-Demo (Lieferungen aus Aufträgen)")
        ship.run_demo_shipping(orders)

    success("demo-all: Alle ausgewählten Prozess-Demos erfolgreich durchlaufen.")

# ============================================================================
# Test- und Demo-Skripte
# ============================================================================


@tests_app.command("demo-endtoend-file")
def demo_endtoend_file(
    debug_flag: bool = typer.Option(False, "--debug", help="Debug-Ausgaben aktivieren."),
) -> None:
    """
    Führt die End-to-End-Demo wie in tests/demo_endto_end.py aus
    und schreibt Beispiel-UMH-Events in eine JSON-Datei.
    """
    from importers.bom_importer import BOMImporter
    from importers.structured_bom_importer import StructuredBOMImporter
    from importers.supplier_importer import SupplierImporter
    from integration.umh_events import UMHEventManager, EventType
    from integration.umh_client_sim import UMHClientSimulator

    info("Starte End-to-End-Demo (Script-Variante)...")
    api = get_api(debug_enabled=debug_flag)

    # 1) Stammdaten / BoMs / Lieferanten
    bom_importer = BOMImporter(api)
    bom_importer.import_variant("spartan")
    bom_importer.import_variant("lightweight")
    bom_importer.import_variant("balance")

    structured_importer = StructuredBOMImporter(api)
    structured_importer.import_eigenfertigung_boms("spartan")
    structured_importer.import_eigenfertigung_boms("lightweight")
    structured_importer.import_eigenfertigung_boms("balance")

    supplier_importer = SupplierImporter(api)
    supplier_importer.import_suppliers()

    # 2) Platzhalter für Prozess-Demos
    warning("TODO: Sales-, Manufacturing-, Purchase-, Inventory-, Shipping-Demos hier sinnvoll einbinden.")

    # 3) UMH-Events sammeln
    umh_manager = UMHEventManager()

    # Beispiel-Events
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

    umh_client = UMHClientSimulator(output_file=UMH_EVENTS_ENDTOEND_FILE)
    umh_client.send_events_batch(events)
    umh_client.export_to_file()

    success(f"End-to-End-Demo (Script-Variante) fertig. Events in {UMH_EVENTS_ENDTOEND_FILE} geschrieben.")