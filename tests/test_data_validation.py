# tests/test_data_validation.py

"""
Test data validation.
"""

import unittest

from core.validation import DataValidator


class TestDataValidation(unittest.TestCase):
    """Test data validation utilities."""

    def setUp(self) -> None:
        self.validator = DataValidator()

    def test_validate_csv_structure(self) -> None:
        """Erwartete und tatsächliche Spaltenmenge werden geprüft."""
        expected = {"col1", "col2"}
        actual = {"col1", "col2", "col3"}
        # sollte True sein, da alle erwarteten Spalten vorhanden sind
        self.assertTrue(self.validator.validate_csv_structure(expected, actual))

        actual_missing = {"col1"}
        self.assertFalse(self.validator.validate_csv_structure(expected, actual_missing))

    def test_validate_required_fields(self) -> None:
        """Required-Felder werden auf Nicht-Leerheit geprüft."""
        rows = [
            {"name": "A", "code": "1"},
            {"name": "", "code": "2"},
        ]
        required = ["name"]
        ok, errors = self.validator.validate_required_fields(rows, required)
        self.assertFalse(ok)
        self.assertGreater(len(errors), 0)

    def test_validate_references(self) -> None:
        """Referenzen werden gegen erlaubte IDs geprüft."""
        rows = [{"product_id": 1}, {"product_id": 2}]
        allowed_ids = {1}
        ok, errors = self.validator.validate_references(rows, "product_id", allowed_ids)
        self.assertFalse(ok)
        self.assertGreater(len(errors), 0)

    def test_validate_unique_constraint(self) -> None:
        """Dublettenverletzungen werden erkannt."""
        rows = [{"code": "A"}, {"code": "A"}, {"code": "B"}]
        ok, duplicates = self.validator.validate_unique_constraint(rows, "code")
        self.assertFalse(ok)
        self.assertIn("A", duplicates)


if __name__ == "__main__":
    unittest.main()
