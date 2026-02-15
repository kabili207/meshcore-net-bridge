"""Serial port handler for MeshCore RS232 bridge."""

import logging
import threading
import time

import serial

from .config import SerialConfig
from .protocol import FrameDecoder, encode_frame

logger = logging.getLogger(__name__)

# Reconnection settings
RECONNECT_DELAY_MIN = 1  # seconds
RECONNECT_DELAY_MAX = 60  # seconds


class SerialHandler:
    """Handles serial communication with MeshCore device."""

    def __init__(self, config: SerialConfig) -> None:
        self._config = config
        self._port: serial.Serial | None = None
        self._decoder = FrameDecoder()
        self._write_lock = threading.Lock()
        self._reconnect_delay = RECONNECT_DELAY_MIN

    @property
    def connected(self) -> bool:
        """Return True if serial port is open."""
        return self._port is not None and self._port.is_open

    def open(self) -> None:
        """Open the serial port."""
        self._port = serial.Serial(
            port=self._config.port,
            baudrate=self._config.baud,
            timeout=0.1,  # 100ms read timeout for polling
        )
        self._reconnect_delay = RECONNECT_DELAY_MIN  # Reset backoff on success
        logger.info(
            "Opened serial port %s at %d baud",
            self._config.port,
            self._config.baud,
        )

    def close(self) -> None:
        """Close the serial port."""
        if self._port and self._port.is_open:
            self._port.close()
            logger.info("Closed serial port")
        self._port = None

    def try_reconnect(self) -> bool:
        """
        Attempt to reconnect to the serial port.

        Returns True if reconnection successful, False otherwise.
        Uses exponential backoff between attempts.
        """
        self.close()
        self._decoder = FrameDecoder()  # Reset decoder state

        logger.info(
            "Attempting serial reconnection in %d seconds...",
            self._reconnect_delay,
        )
        time.sleep(self._reconnect_delay)

        try:
            self.open()
            return True
        except serial.SerialException as e:
            logger.warning("Serial reconnection failed: %s", e)
            # Exponential backoff
            self._reconnect_delay = min(
                self._reconnect_delay * 2,
                RECONNECT_DELAY_MAX,
            )
            return False

    def read_packets(self) -> list[bytes]:
        """
        Read and decode any available packets.

        Returns list of decoded payloads, or empty list if no data or error.
        Raises SerialDisconnected if the port is no longer available.
        """
        if not self.connected:
            return []

        try:
            data = self._port.read(self._port.in_waiting or 1)
        except serial.SerialException as e:
            logger.error("Serial read error: %s", e)
            raise SerialDisconnected() from e

        if not data:
            return []

        packets = self._decoder.feed(data)
        for pkt in packets:
            logger.debug("Received packet from serial: %d bytes", len(pkt))
        return packets

    def write_packet(self, payload: bytes) -> None:
        """Write a packet to the serial port (thread-safe)."""
        if not self.connected:
            logger.warning("Cannot write: serial port not open")
            return

        frame = encode_frame(payload)
        try:
            with self._write_lock:
                self._port.write(frame)
            logger.debug("Sent packet to serial: %d bytes", len(payload))
        except serial.SerialException as e:
            logger.error("Serial write error: %s", e)
            # Don't raise here - let the main loop detect via read_packets


class SerialDisconnected(Exception):
    """Raised when serial port becomes unavailable."""

    pass
