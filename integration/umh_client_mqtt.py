# integration/umh_client_mqtt.py

from __future__ import annotations
from typing import Dict, List

from integration.umh_events import UMHEvent
from messaging.mqtt_client import MqttClient
from core.logging_utils import info

class UMHMqttClient:
    """
    UMH-Client, der Events direkt per MQTT überträgt.
    """

    def __init__(self) -> None:
        self._mqtt = MqttClient()
        self._mqtt.connect()
        self._sent_events: List[Dict] = []

    @staticmethod
    def _event_to_mqtt_payload(event: UMHEvent) -> Dict:
        """
        Transformiert ein UMHEvent in ein generisches MQTT-Event-Payload.
        """
        d = event.to_dict()
        return {
            "timestamp": d["timestamp"],
            "source": "odoo",
            "event_type": d["type"],
            "entity": "umh_event",
            "entity_id": None,
            "data": d["payload"],
        }

    def send_event(self, event: UMHEvent) -> bool:
        payload = self._event_to_mqtt_payload(event)
        self._mqtt.publish_event(payload)
        self._sent_events.append(payload)
        return True

    def send_events_batch(self, events: List[UMHEvent]) -> bool:
        for evt in events:
            self.send_event(evt)
        info(f"{len(events)} UMH-Events per MQTT gesendet.")
        return True

    def get_sent_events(self) -> List[Dict]:
        return list(self._sent_events)
