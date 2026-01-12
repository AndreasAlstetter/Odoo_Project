import csv
from dataclasses import dataclass
from pathlib import Path
from typing import Dict, List, Tuple

from odoo_api import OdooAPI  # aus deinem Projekt

from config import MENGE_CSV_PATH, PRODUCT_SPARTAN_NAME, PRODUCT_LIGHTWEIGHT_NAME, PRODUCT_BALANCE_NAME, ROUTING_CSV_PATH, ODOO_URL, DB_NAME, LOGIN, API_KEY

# ---------- Datenmodelle ----------

@dataclass
class BaseVariant:
    name: str          # z.B. "EVO Spartan"
    key: str           # z.B. "spartan" für Routings


@dataclass
class DroneConfig:
    base: BaseVariant
    hull_color: str          # Haubenfarbe, z.B. "weiss"
    foot_color: str          # Füße, z.B. "blau"
    plate_color: str         # Grundplatte, z.B. "schwarz"


# ---------- Hilfsfunktionen CSV ----------

def load_mengenstueckliste(path) -> list[dict]:
    path = Path(path)  # String → Path
    rows = []
    with path.open(encoding="utf-8-sig") as f:
        reader = csv.DictReader(f)
        for row in reader:
            rows.append(row)
    return rows


def build_color_maps_mengen(rows):
    hauben = {}
    fuesse = {"spartan": {}, "lightweight": {}, "balance": {}}
    grundplatten = {"spartan": {}, "lightweight": {}, "balance": {}}

    for r in rows:
        bezeichnung = (r.get("Artikelbezeichnung") or "").strip()
        name = (r.get("Bennenung") or "").strip()
        internal_code = (r.get("Artikelnummer NextLap (Provisorium)") or "").strip()

        if not internal_code:
            continue

        text_bez = bezeichnung.lower()
        text_name = name.lower()

        # Hauben
        if "haube evo2" in text_bez or "haube evo2" in text_name:
            color = (text_bez or text_name).split()[-1]
            hauben[color] = internal_code
            continue

        # Grundplatten
        if "grundplatte evo 2 spartan" in text_bez:
            color = text_bez.split()[-1]
            grundplatten["spartan"][color] = internal_code
            continue
        if "grundplatte evo 2 lightweight" in text_bez:
            color = text_bez.split()[-1]
            grundplatten["lightweight"][color] = internal_code
            continue
        if "grundplatte evo 2 balance" in text_bez:
            color = text_bez.split()[-1]
            grundplatten["balance"][color] = internal_code
            continue

        # Füße – hier explizit im Namen suchen
        if "fuß evo2 spartan" in text_name:
            color = text_name.split()[-1]
            fuesse["spartan"][color] = internal_code
            continue
        if "fuß evo2 lightweight" in text_name:
            color = text_name.split()[-1]
            fuesse["lightweight"][color] = internal_code
            continue
        if "fuß evo2 balance" in text_name:
            color = text_name.split()[-1]
            fuesse["balance"][color] = internal_code
            continue

    print("Hauben:", hauben)
    print("Fuesse:", fuesse)
    print("Grundplatten:", grundplatten)
    return hauben, fuesse, grundplatten



def load_common_components(rows: List[Dict[str, str]]) -> List[Dict[str, str]]:
    """Teile, die für alle Varianten gleich sind (ohne farbspezifische Haube/Füße/Platte)."""
    common = []
    for r in rows:
        bezeichnung = r["Artikelbezeichnung"].strip()
        if "Haube EVO2" in bezeichnung or "Grundplatte EVO 2" in bezeichnung or "Fuß EVO2" in bezeichnung:
            continue
        common.append(r)
    return common


# ---------- Odoo-spezifische Helfer ----------

def find_product_by_name(api: OdooAPI, name: str) -> int:
    res = api.search_read(
        "product.product",
        [["name", "=", name]],
        ["id"],
        limit=1,
    )
    if not res:
        raise RuntimeError(f"Kein product.product mit name={name} in Odoo gefunden")
    return res[0]["id"]



def find_or_create_bom(api: OdooAPI, product_tmpl_id: int, product_id: int) -> int:
    # product_id wird ignoriert (0), BOM gilt für alle Varianten des Templates
    existing = api.search_read(
        "mrp.bom",
        [["product_tmpl_id", "=", product_tmpl_id]],
        ["id"],
        limit=1,
    )
    if existing:
        return existing[0]["id"]

    bom_id = api.create(
        "mrp.bom",
        {
            "product_tmpl_id": product_tmpl_id,
            "product_qty": 1.0,
            "type": "normal",
        },
    )
    return bom_id


def add_bom_line(
    api: OdooAPI,
    bom_id: int,
    product_id: int,
    quantity: float,
) -> None:
    api.create(
        "mrp.bom.line",
        {
            "bom_id": bom_id,
            "product_id": product_id,
            "product_qty": quantity,
        },
    )


def find_variant_product(api: OdooAPI, base: BaseVariant, cfg: DroneConfig) -> tuple[int, int]:
    """
    Sucht die Produktvariante in Odoo.
    Annahme: Attributwerte (Variante, Haubenfarbe, Fußfarbe, Grundplatte) sind
    als product.template.attribute.value / product.attribute.value geführt.
    Hier wird zur Vereinfachung nur ein Search über Name und eventuell Default-Code gemacht.
    Das musst du ggf. an deine reale Attributstruktur anpassen.
    """
    if base.key == "spartan":
        tmpl_name = PRODUCT_SPARTAN_NAME  # "EVO2 Spartan Drohne"
    elif base.key == "lightweight":
        tmpl_name = PRODUCT_LIGHTWEIGHT_NAME
    else:
        tmpl_name = PRODUCT_BALANCE_NAME

    res = api.search_read(
        "product.template",
        [["name", "=", tmpl_name]],
        ["id"],
        limit=1,
    )
    if not res:
        raise RuntimeError(f"Produkt-Template nicht gefunden: {tmpl_name}")

    tmpl_id = res[0]["id"]

    # BOM nur auf Template, ohne konkrete Variante
    return 0, tmpl_id

# ---------- Hauptlogik BOM-Erzeugung ----------

def create_bom_for_config(
    api: OdooAPI,
    cfg: DroneConfig,
    hauben_map: Dict[str, str],
    fuesse_map: Dict[str, Dict[str, str]],
    grundplatten_map: Dict[str, Dict[str, str]],
    common_components: List[Dict[str, str]],
) -> None:
    # 1) Produktvorlage finden
    product_id, tmpl_id = find_variant_product(api, cfg.base, cfg)

    # 2) BOM holen oder anlegen
    bom_id = find_or_create_bom(api, tmpl_id, product_id)

    # 3) Gemeinsame Komponenten
    for r in common_components:
        qty_spartan = float(r["Menge EVO Spartan"] or 0)
        qty_light = float(r["Menge EVO Lightweight"] or 0)
        qty_balance = float(r["Menge EVO Balance"] or 0)

        if cfg.base.key == "spartan":
            qty = qty_spartan
        elif cfg.base.key == "lightweight":
            qty = qty_light
        else:
            qty = qty_balance

        if qty <= 0:
            continue

        comp_name = r["Artikelbezeichnung"].strip()
        if not comp_name:
            continue

        comp_product_id = find_product_by_name_ilike(api, [comp_name])
        add_bom_line(api, bom_id, comp_product_id, qty)

    # 4) Haube (eine pro Drohne)
    hull_product_id = find_product_by_name_ilike(
        api,
        ["haube", "evo2", cfg.hull_color],
    )
    add_bom_line(api, bom_id, hull_product_id, 1.0)

    # 5) Grundplatte (eine pro Drohne)
    variant_label = cfg.base.name.split()[-1].lower()  # spartan/lightweight/balance
    plate_product_id = find_product_by_name_ilike(
        api,
        ["grundplatte", "evo 2", variant_label, cfg.plate_color],
    )
    add_bom_line(api, bom_id, plate_product_id, 1.0)

    # 6) Füße (4 Stück)
    foot_product_id = find_product_by_name_ilike(
        api,
        ["fuß", "evo2", variant_label, cfg.foot_color],
    )
    add_bom_line(api, bom_id, foot_product_id, 4.0)


def generate_all_configs(
    bases: List[BaseVariant],
    hauben_map: Dict[str, str],
    fuesse_map: Dict[str, Dict[str, str]],
    grundplatten_map: Dict[str, Dict[str, str]],
) -> List[DroneConfig]:
    configs: List[DroneConfig] = []
    colors_hull = sorted(hauben_map.keys())
    # Füße & Platten je Variante; nur Farben verwenden, die für beide existieren
    for base in bases:
        foot_colors = sorted(fuesse_map[base.key].keys())
        plate_colors = sorted(grundplatten_map[base.key].keys())
        for hc in colors_hull:
            for fc in foot_colors:
                for pc in plate_colors:
                    configs.append(
                        DroneConfig(
                            base=base,
                            hull_color=hc,
                            foot_color=fc,
                            plate_color=pc,
                        )
                    )
    return configs

def find_product_by_name_ilike(api: OdooAPI, must_contain: list[str]) -> int:
    domain = [["name", "ilike", part] for part in must_contain]
    res = api.search_read(
        "product.product",
        domain,
        ["id", "name"],
        limit=1,
    )
    if not res:
        raise RuntimeError(f"Kein product.product gefunden für Filter: {must_contain}")
    return res[0]["id"]


def main():

 
    mengen_rows = load_mengenstueckliste(MENGE_CSV_PATH)
    hauben_map, fuesse_map, grundplatten_map = build_color_maps_mengen(mengen_rows)
    common_components = load_common_components(mengen_rows)

    bases = [
        BaseVariant(name="EVO Spartan", key="spartan"),
        BaseVariant(name="EVO Lightweight", key="lightweight"),
        BaseVariant(name="EVO Balance", key="balance"),
    ]

    configs = generate_all_configs(bases, hauben_map, fuesse_map, grundplatten_map)
    print(f"{len(configs)} Drohnenkonfigurationen vorberechnet")

    api = OdooAPI()  # ohne Argumente

    print(f"{len(configs)} Drohnenkonfigurationen vorberechnet")

    for cfg in configs:
        print(
            f"Erzeuge BOM für {cfg.base.name} | "
            f"Haube={cfg.hull_color} | Füße={cfg.foot_color} | Platte={cfg.plate_color}"
        )
        create_bom_for_config(
            api,
            cfg,
            hauben_map,
            fuesse_map,
            grundplatten_map,
            common_components,
        )


if __name__ == "__main__":
    main()
