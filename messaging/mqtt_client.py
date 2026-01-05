# messaging/mqtt_client.py
from __future__ import annotations

import json
import ssl
from typing import Any, Dict

import paho.mqtt.client as mqtt

from config import (
    MQTT_BROKER_HOST,
    MQTT_BROKER_PORT,
    MQTT_USERNAME,
    MQTT_PASSWORD,
    MQTT_BASE_TOPIC,
    MQTT_KPI_EVENTS_TOPIC,
)
from core.logging_utils import info, warning


class MqttClient:
    def __init__(self) -> None:
        self._client = mqtt.Client()
        if MQTT_USERNAME:
            self._client.username_pw_set(MQTT_USERNAME, MQTT_PASSWORD)
        if MQTT_BROKER_PORT == 8883:
            self._client.tls_set(tls_version=ssl.PROTOCOL_TLS_CLIENT)

    def connect(self) -> None:
        try:
            self._client.connect(MQTT_BROKER_HOST, MQTT_BROKER_PORT, keepalive=60)
        except Exception as exc:
            warning(
                f"MQTT-Verbindung fehlgeschlagen zu {MQTT_BROKER_HOST}:{MQTT_BROKER_PORT} "
                f"({exc})."
            )
            raise
        info(f"Mit MQTT-Broker {MQTT_BROKER_HOST}:{MQTT_BROKER_PORT} verbunden.")

    def publish_json(self, payload: Dict[str, Any]) -> None:
        """KPI-Message an MQTT_BASE_TOPIC senden."""
        topic = MQTT_BASE_TOPIC.strip("/")
        msg = json.dumps(payload, default=str, separators=(",", ":"))
        result = self._client.publish(topic, msg, qos=0, retain=False)
        status = result[0]
        if status != 0:
            warning(f"MQTT-Publish auf Topic {topic} fehlgeschlagen (Status {status}).")
        else:
            info(f"MQTT: Topic={topic}, Payload={msg}")

    def publish_event(self, event: Dict[str, Any]) -> None:
        """Prozess-Event an MQTT_EVENTS_TOPIC senden."""
        topic = MQTT_KPI_EVENTS_TOPIC.strip("/")
        msg = json.dumps(event, default=str, separators=(",", ":"))
        result = self._client.publish(topic, msg, qos=0, retain=False)
        status = result[0]
        if status != 0:
            warning(f"MQTT-Event-Publish auf Topic {topic} fehlgeschlagen (Status {status}).")
        else:
            info(f"MQTT-Event: Topic={topic}, Payload={msg}")
