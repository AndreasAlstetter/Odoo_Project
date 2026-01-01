# integration/umh_client_sim.py
"""
UMH-Client-Simulator – rein dateibasierte Simulation.

Einsatz:
- Aufnahme von Events aus Produktions-, Lager- und End-to-End-Flows.
- Persistenz als JSON-Datei (z. B. umh_events_endtoend.json) für die
  Weiterverarbeitung in UMH oder Analyse-Tools.
"""

from __future__ import annotations

from typing import Dict, List, Optional
from config import UMH_EVENTS_ENDTOEND_FILE

import json
from pathlib import Path

EVENT_FILE = Path(UMH_EVENTS_ENDTOEND_FILE)

class UMHClientSimulator:
    """
    Simuliert einen UMH-Client (MQTT/HTTP) durch pures Dateischreiben.

    Events werden in-memory gesammelt und können als JSON-Datei
    exportiert werden.
    """

    def __init__(self, use_mqtt: bool = False, output_file: Optional[str] = None) -> None:
        """
        Parameters
        ----------
        use_mqtt:
            Platzhalterflag; in dieser Simulation ohne Funktion.
        output_file:
            Zieldatei für den JSON-Export der Events.
        """
        self.use_mqtt = use_mqtt
        self.output_file = output_file or EVENT_FILE
        self.events_sent: List[Dict] = []

    def send_event(self, event: Dict) -> bool:
        """
        Sendet (simuliert) ein einzelnes Event an UMH.

        In der Simulation:
        - Event wird in der internen Liste gespeichert.
        """
        self.events_sent.append(event)
        return True

    def send_events_batch(self, events: List[Dict]) -> bool:
        """
        Sendet (simuliert) mehrere Events als Batch.

        Alle Events werden intern zur Liste hinzugefügt.
        """
        for evt in events:
            self.send_event(evt)
        return True

    def get_sent_events(self) -> List[Dict]:
        """
        Gibt alle bisher „gesendeten“ Events zurück.

        Returns
        -------
        list[dict]
            Defensive Kopie der Eventliste.
        """
        return list(self.events_sent)

    def export_to_file(self) -> bool:
        """
        Exportiert alle Events in die konfigurierte JSON-Datei.

        Returns
        -------
        bool
            True bei Erfolg, False bei I/O-Fehlern.
        """
        try:
            with open(self.output_file, "w", encoding="utf-8") as f:
                json.dump(self.events_sent, f, ensure_ascii=False, indent=2)
            return True
        except OSError:
            return False

    def clear_events(self) -> None:
        """Löscht alle bisher gespeicherten Events."""
        self.events_sent.clear()
