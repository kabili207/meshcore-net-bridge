"""MQTT handler for MeshCore bridge."""

import base64
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
        mesh_id: str,
        on_packet: Callable[[bytes], None],
    ) -> None:
        self._config = config
        self._mesh_id = mesh_id
        self._on_packet = on_packet
        self._connected = False

        client_id = f"meshcore-bridge-{mesh_id}"
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
    def _rx_topic(self) -> str:
        """Topic for publishing packets received from local mesh."""
        return f"{self._config.root_topic}/{self._mesh_id}"

    @property
    def _subscribe_pattern(self) -> str:
        """Topic pattern for receiving packets from other meshes."""
        return f"{self._config.root_topic}/+"

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

        encoded = base64.b64encode(payload).decode("ascii")
        self._client.publish(self._rx_topic, encoded)
        logger.debug("Published packet to %s: %d bytes", self._rx_topic, len(payload))

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
            # Resubscribe on every connect (handles reconnection)
            client.subscribe(self._subscribe_pattern)
            logger.info("Subscribed to %s", self._subscribe_pattern)
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
        # Extract mesh_id from topic: {root}/{mesh_id}
        parts = msg.topic.split("/")
        if len(parts) < 2:
            return

        source_mesh = parts[-1]

        # Ignore our own messages
        if source_mesh == self._mesh_id:
            return

        try:
            payload = base64.b64decode(msg.payload)
        except Exception:
            logger.warning("Failed to decode base64 payload from %s", msg.topic)
            return

        logger.debug(
            "Received packet from mesh '%s': %d bytes",
            source_mesh,
            len(payload),
        )
        self._on_packet(payload)
