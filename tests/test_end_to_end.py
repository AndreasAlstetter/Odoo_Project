# tests/test_end_to_end.py

import unittest

from odoo_api import OdooAPI
from endtoend.run import run_endtoend_demo


class TestEndToEndDemo(unittest.TestCase):
    """End-to-End-Demo: nur Smoke- / Integrations-Test, keine Detail-Logik."""

    def test_endtoend_smoke(self) -> None:
        api = OdooAPI()
        result = run_endtoend_demo(api)

        orders = result.get("orders", [])
        mos = result.get("manufacturing_orders", [])
        events_count = result.get("umh_events_count", 0)

        # Sehr einfache Integrations-Assertions:
        self.assertGreaterEqual(len(orders), 1, "Mindestens ein Verkaufsauftrag erwartet.")
        self.assertGreaterEqual(len(mos), 1, "Mindestens ein Fertigungsauftrag erwartet.")
        self.assertGreater(events_count, 0, "Es sollten UMH-Events erzeugt worden sein.")
        

if __name__ == "__main__":
    unittest.main()
