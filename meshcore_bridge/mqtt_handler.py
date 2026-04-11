"""MQTT handler for MeshCore bridge."""

import logging
from collections.abc import Callable

import paho.mqtt.client as mqtt

from .config import MqttConfig

logger = logging.getLogger(__name__)

# Reconnection settings
RECONNECT_DELAY_MIN = 1  # seconds
RECONNECT_DELAY_MAX = 120  # seconds


class MqttHandler:
    """Handles MQTT communication for mesh bridging."""

    def __init__(
        self,
        config: MqttConfig,
        node_id: str,
        on_packet: Callable[[bytes], None],
    ) -> None:
        self._config = config
        self._node_id = node_id
        self._on_packet = on_packet
        self._connected = False

        client_id = f"mc-bridge-{node_id}"
        self._client = mqtt.Client(mqtt.CallbackAPIVersion.VERSION2, client_id=client_id)
        self._client.on_connect = self._handle_connect
        self._client.on_disconnect = self._handle_disconnect
        self._client.on_message = self._handle_message

        # Enable automatic reconnection with exponential backoff
        self._client.reconnect_delay_set(RECONNECT_DELAY_MIN, RECONNECT_DELAY_MAX)

        if config.username:
            self._client.username_pw_set(config.username, config.password)

    @property
    def connected(self) -> bool:
        """Return True if currently connected to broker."""
        return self._connected

    @property
    def _topic(self) -> str:
        """Topic for publishing and subscribing."""
        return self._config.topic

    def connect(self) -> None:
        """Connect to MQTT broker and start network loop."""
        logger.info(
            "Connecting to MQTT broker %s:%d",
            self._config.broker,
            self._config.port,
        )
        self._client.connect(self._config.broker, self._config.port)
        self._client.loop_start()

    def disconnect(self) -> None:
        """Stop network loop and disconnect from broker."""
        self._client.loop_stop()
        self._client.disconnect()
        logger.info("Disconnected from MQTT broker")

    def publish_packet(self, payload: bytes) -> None:
        """Publish a packet received from local serial to MQTT."""
        if not self._connected:
            logger.debug("Cannot publish: not connected to MQTT broker")
            return

        self._client.publish(self._topic, payload)
        logger.debug("Published packet to %s: %d bytes", self._topic, len(payload))

    def _handle_connect(
        self,
        client: mqtt.Client,
        userdata: object,
        flags: mqtt.ConnectFlags,
        reason_code: mqtt.ReasonCode,
        properties: mqtt.Properties | None,
    ) -> None:
        if reason_code == 0:
            self._connected = True
            logger.info("Connected to MQTT broker")
            client.subscribe(self._topic)
            logger.info("Subscribed to %s", self._topic)
        else:
            self._connected = False
            logger.error("MQTT connection failed: %s", reason_code)

    def _handle_disconnect(
        self,
        client: mqtt.Client,
        userdata: object,
        disconnect_flags: mqtt.DisconnectFlags,
        reason_code: mqtt.ReasonCode,
        properties: mqtt.Properties | None,
    ) -> None:
        self._connected = False
        if reason_code == 0:
            logger.info("Disconnected from MQTT broker (clean)")
        else:
            logger.warning(
                "Disconnected from MQTT broker: %s (will reconnect)",
                reason_code,
            )

    def _handle_message(
        self,
        client: mqtt.Client,
        userdata: object,
        msg: mqtt.MQTTMessage,
    ) -> None:
        payload = msg.payload
        if not payload:
            return

        logger.debug(
            "Received packet: %d bytes",
            len(payload),
        )
        self._on_packet(payload)
