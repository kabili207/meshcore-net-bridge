"""MQTT handler for MeshCore bridge."""

import logging
import threading
import time
from collections.abc import Callable

import paho.mqtt.client as mqtt

from .config import MqttConfig

logger = logging.getLogger(__name__)

# Reconnection settings
RECONNECT_DELAY_MIN = 1  # seconds
RECONNECT_DELAY_MAX = 120  # seconds

# We publish and subscribe to the same topic, and MQTT 3.1.1 has no no_local
# option, so the broker echoes our own publishes right back. Record each packet
# we publish and drop the echo if it returns within this window. Full mesh
# packets carry routing metadata and sender hashes, so a byte-identical payload
# reappearing this quickly is our echo, not distinct traffic.
ECHO_SUPPRESS_TTL = 15  # seconds


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

        # Payloads we've published recently, for echo suppression. Maps a packet
        # to the monotonic timestamps at which we sent it (a list, so repeated
        # sends of the same bytes each get consumed by exactly one echo).
        # Accessed from both the main thread (publish) and paho's network thread
        # (receive), so guard it with a lock.
        self._sent_lock = threading.Lock()
        self._recent_sent: dict[bytes, list[float]] = {}

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

        # Record before publishing so the entry is in place before the echo can
        # come back.
        now = time.monotonic()
        with self._sent_lock:
            self._purge_expired(now)
            self._recent_sent.setdefault(payload, []).append(now)

        self._client.publish(self._topic, payload)
        logger.debug("Published packet to %s: %d bytes", self._topic, len(payload))

    def _purge_expired(self, now: float) -> None:
        """Drop sent-packet records older than the suppression window.

        Caller must hold _sent_lock.
        """
        for key in list(self._recent_sent):
            stamps = self._recent_sent[key]
            while stamps and now - stamps[0] > ECHO_SUPPRESS_TTL:
                stamps.pop(0)
            if not stamps:
                del self._recent_sent[key]

    def _is_own_echo(self, payload: bytes) -> bool:
        """Return True if this payload is an echo of one we recently published.

        Consumes the matching record so each publish suppresses at most one echo.
        """
        now = time.monotonic()
        with self._sent_lock:
            stamps = self._recent_sent.get(payload)
            if not stamps:
                return False
            while stamps and now - stamps[0] > ECHO_SUPPRESS_TTL:
                stamps.pop(0)
            if not stamps:
                del self._recent_sent[payload]
                return False
            stamps.pop(0)  # consume this echo
            if not stamps:
                del self._recent_sent[payload]
            return True

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

        if self._is_own_echo(payload):
            logger.debug("Suppressed own echoed packet: %d bytes", len(payload))
            return

        logger.debug(
            "Received packet: %d bytes",
            len(payload),
        )
        self._on_packet(payload)
