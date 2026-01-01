# core/validation.py
"""
Validierungs- und Konvertierungsfunktionen für CSV- und Stammdaten.

Dieses Modul bündelt:
- Struktur-Checks für DataFrames (z. B. Pflichtspalten)
- einfache inhaltliche Checks (nicht-leere Felder)
- robuste Konvertierungen (safe_float, safe_int)

Alle Importer-Module sollten diese Funktionen verwenden, um ein
einheitliches Verhalten und konsistente Fehlermeldungen zu gewährleisten.
"""

from typing import Iterable, List, Sequence, Set, Union, Any, Optional

import math

import pandas as pd


class CSVValidationError(Exception):
    """
    Fehlerklasse für Probleme mit Eingabedateien (insb. CSV).

    Wird geworfen, wenn:
    - Pflichtspalten fehlen
    - Datenstrukturen nicht den Erwartungen entsprechen
    """


def validate_required_columns(
    df: pd.DataFrame,
    required: Sequence[str],
    context: str = "",
) -> None:
    """
    Prüft, ob alle Spalten aus `required` im DataFrame `df` vorhanden sind.

    Parameter:
    - df: Eingabe-DataFrame
    - required: Liste von Pflichtspaltennamen
    - context: Optionale Kontextbeschreibung (z. B. Dateiname)

    Raises:
    - CSVValidationError, wenn Spalten fehlen
    """
    missing: Set[str] = set(required) - set(df.columns)
    if missing:
        ctx = f" in {context}" if context else ""
        raise CSVValidationError(
            f"Fehlende Pflichtspalten{ctx}: {', '.join(sorted(missing))}"
        )


def validate_non_empty(
    df: pd.DataFrame,
    columns: Sequence[str],
    context: str = "",
    allow_zero: bool = True,
) -> List[int]:
    """
    Prüft, dass die angegebenen Spalten keine leeren Werte enthalten.

    Parameter:
    - df: Eingabe-DataFrame
    - columns: zu prüfende Spalten
    - context: optionale Kontextbeschreibung
    - allow_zero: wenn False, werden numerische 0-Werte ebenfalls als "leer"
      interpretiert.

    Rückgabe:
    - Liste der Zeilenindizes, die Verstöße enthalten.
    """
    bad_rows: List[int] = []

    for idx, row in df.iterrows():
        for col in columns:
            val = row.get(col, None)
            if val is None:
                bad_rows.append(idx)
                break
            if isinstance(val, str):
                if not val.strip():
                    bad_rows.append(idx)
                    break
            else:
                # numerische Werte
                if not allow_zero and isinstance(val, (int, float)):
                    try:
                        if float(val) == 0.0:
                            bad_rows.append(idx)
                            break
                    except Exception:
                        bad_rows.append(idx)
                        break

    if bad_rows and context:
        # Hinweis: Kein Exception-Throw, sondern Rückgabe; Caller entscheidet.
        pass

    return bad_rows


def safe_float(
    value: Any,
    default: float = 0.0,
    *,
    allow_negative: bool = True,
) -> float:
    """
    Konvertiert einen beliebigen Wert robust in einen float.

    Regeln:
    - None, leere Strings oder nicht konvertierbare Werte → `default`
    - NaN/Inf → `default`
    - wenn `allow_negative` False und Wert < 0 → `default`
    """
    if value is None:
        return default
    if isinstance(value, str):
        if not value.strip():
            return default

    try:
        v = float(value)
    except (TypeError, ValueError):
        return default

    if math.isnan(v) or math.isinf(v):
        return default

    if not allow_negative and v < 0:
        return default

    return v


def safe_int(
    value: Any,
    default: int = 0,
    *,
    allow_negative: bool = True,
) -> int:
    """
    Konvertiert einen beliebigen Wert robust in einen int.

    Regeln analog zu `safe_float`, aber Rückgabe ist int.
    """
    f = safe_float(value, float(default), allow_negative=allow_negative)
    try:
        return int(round(f))
    except Exception:
        return default
