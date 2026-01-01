import os

from dotenv import load_dotenv

load_dotenv()

# Odoo-Verbindungsdaten

ODOO_URL = os.getenv("ODOO_URL", "https://190-stage.odoo.721739.d9tcloud.de/").rstrip("/")

DB_NAME = os.getenv("DB_NAME", "odoo.190-stage_testing")

LOGIN = os.getenv("LOGIN", "felix.reich@tha.de")

API_KEY = os.getenv("API_KEY", "51ba1fb1ab26c77d6368b055e9f1c34b02583600")


BASE_DIR = os.path.dirname(os.path.abspath(__file__))

# Zentrales Datenverzeichnis
DATA_DIR = os.path.join(BASE_DIR, "data")

# Unterordner für verschiedene Domänen
RAW_CSV_DIR = os.path.join(DATA_DIR, "csv_raw")
DOMAIN_DATA_DIR = os.path.join(DATA_DIR, "domain")
UMH_DATA_DIR = os.path.join(DATA_DIR, "umh")
EXPORT_DIR = os.path.join(DATA_DIR, "export")

# CSV-Pfade (lesende Importe)
MENGE_CSV_PATH = os.getenv(
    "MENGE_CSV_PATH",
    os.path.join(RAW_CSV_DIR, "mengenstueckliste.csv"),
)
STRUKTUR_CSV_PATH = os.getenv(
    "STRUKTUR_CSV_PATH",
    os.path.join(RAW_CSV_DIR, "strukturstueckliste.csv"),
)
LAGER_CSV_PATH = os.getenv(
    "LAGER_CSV_PATH",
    os.path.join(RAW_CSV_DIR, "lagerdaten.csv"),
)
LIEF_CSV_PATH = os.getenv(
    "LIEF_CSV_PATH",
    os.path.join(RAW_CSV_DIR, "lieferanten.csv"),
)

# Weitere vorbereitete CSVs
DROHNENKALK_CSV_PATH = os.getenv(
    "DROHNENKALK_CSV_PATH",
    os.path.join(RAW_CSV_DIR, "drohnenkalkulation.csv"),
)
MATERIALBEDARF_CSV_PATH = os.getenv(
    "MATERIALBEDARF_CSV_PATH",
    os.path.join(RAW_CSV_DIR, "materialbedarfplanung.csv"),
)
FERTIGUNGSKOSTEN_CSV_PATH = os.getenv(
    "FERTIGUNGSKOSTEN_CSV_PATH",
    os.path.join(RAW_CSV_DIR, "fertigungskosten.csv"),
)
LEGENDE_CSV_PATH = os.getenv(
    "LEGENDE_CSV_PATH",
    os.path.join(RAW_CSV_DIR, "legende.csv"),
)

# Domain-spezifische Dokumentenpfade (jetzt unter DATA_DIR)
AA_DIR = os.path.join(DOMAIN_DATA_DIR, "arbeitsanweisungen")
ARBEITSPLAENE_DIR = os.path.join(DOMAIN_DATA_DIR, "arbeitsplaene")
KONZEPTE_DIR = os.path.join(DOMAIN_DATA_DIR, "konzepte")
SONSTIGE_DIR = os.path.join(DOMAIN_DATA_DIR, "sonstige_stammdaten")

# UMH-Dateien (JSON)
UMH_EVENTS_ENDTOEND_FILE = os.path.join(UMH_DATA_DIR, "umh_events_endtoend.json")
UMH_MASTERDATA_EXPORT_FILE = os.path.join(EXPORT_DIR, "umh_masterdata.json")

# Produktnamen für Varianten
PRODUCT_SPARTAN_NAME = "EVO2 Spartan Drohne"
PRODUCT_LIGHTWEIGHT_NAME = "EVO2 Lightweight Drohne"
PRODUCT_BALANCE_NAME = "EVO2 Balance Drohne"

if not (ODOO_URL and DB_NAME and LOGIN and API_KEY):
    raise RuntimeError("Bitte ODOO_URL, DB_NAME, LOGIN, API_KEY in .env setzen.")

# Workcenter CSV-Pfad
WORKCENTER_CSV_PATH = os.getenv(
    "WORKCENTER_CSV_PATH",
    os.path.join(RAW_CSV_DIR, "workcenters.csv"),
)

# User-Role CSV-Pfad
USERS_ROLES_CSV_PATH = os.getenv(
    "USERS_ROLES_CSV_PATH",
    os.path.join(RAW_CSV_DIR, "users_roles.csv"),
)

# Customer CSV-Pfad
CUSTOMERS_CSV_PATH = os.getenv(
    "CUSTOMERS_CSV_PATH",
    os.path.join(RAW_CSV_DIR, "customers.csv"),
)
