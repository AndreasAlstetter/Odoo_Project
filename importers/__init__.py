# importers/__init__.py
"""
Import-Paket für Stammdaten (Produkte, BoMs, Lager, Lieferanten, Benutzer/Rollen usw.)
im Odoo-Drohnen-Projekt.
"""

from .bom_importer import BOMImporter
from .structured_bom_importer import StructuredBOMImporter
from .stock_importer import StockImporter
from .supplier_importer import SupplierImporter
from .customer_importer import CustomerImporter
from .location_importer import LocationImporter
from .workcenter_importer import WorkcenterImporter
from .routing_importer import RoutingImporter
from .users_roles import UsersRolesImporter

__all__ = [
    "BOMImporter",
    "StructuredBOMImporter",
    "StockImporter",
    "SupplierImporter",
    "CustomerImporter",
    "LocationImporter",
    "WorkcenterImporter",
    "RoutingImporter",
    "UsersRolesImporter",
]
