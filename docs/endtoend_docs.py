# docs_tools/endtoend_docs.py

from __future__ import annotations
from typing import TextIO

from endtoend.run import run_endtoend_demo
from odoo_api import OdooAPI


def generate_endtoend_markdown(out: TextIO) -> None:
    """Erzeugt eine einfache Markdown-Doku für den End-to-End-Fluss."""
    api = OdooAPI()
    info = run_endtoend_demo(api)

    out.write("# End-to-End-Demo\n\n")
    out.write("Dieser Lauf enthält:\n\n")
    out.write(f"- Verkaufsaufträge: {len(info.get('orders', []))}\n")
    out.write(f"- Fertigungsaufträge: {len(info.get('manufacturing_orders', []))}\n")
    out.write(f"- UMH-Events: {info.get('umh_events_count', 0)}\n")
