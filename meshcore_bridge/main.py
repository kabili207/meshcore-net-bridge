"""Main entry point for MeshCore MQTT bridge."""

import argparse
import logging
import signal
import sys
import time
from pathlib import Path

import serial

from .config import load_config
from .mqtt_handler import MqttHandler
from .serial_handler import SerialDisconnected, SerialHandler

logger = logging.getLogger(__name__)

# Initial connection retry settings
INITIAL_RETRY_DELAY = 5  # seconds


def main() -> None:
    """Entry point for meshcore-bridge command."""
    parser = argparse.ArgumentParser(
        description="MQTT bridge for MeshCore RS232 serial protocol"
    )
    parser.add_argument(
        "-c",
        "--config",
        type=Path,
        default=Path("config.yaml"),
        help="Path to configuration file (default: config.yaml)",
    )
    parser.add_argument(
        "-v",
        "--verbose",
        action="store_true",
        help="Enable debug logging",
    )
    args = parser.parse_args()

    # Setup logging
    logging.basicConfig(
        level=logging.DEBUG if args.verbose else logging.INFO,
        format="%(asctime)s %(levelname)s %(name)s: %(message)s",
    )

    try:
        config = load_config(args.config)
    except FileNotFoundError:
        logger.error("Configuration file not found: %s", args.config)
        sys.exit(1)
    except ValueError as e:
        logger.error("Configuration error: %s", e)
        sys.exit(1)

    run(config)


def run(config) -> None:
    """Run the bridge with loaded configuration."""
    serial_handler = SerialHandler(config.serial)
    mqtt_handler = MqttHandler(
        config=config.mqtt,
        mesh_id=config.mesh.id,
        on_packet=serial_handler.write_packet,
    )

    # Graceful shutdown
    shutdown_requested = False

    def handle_signal(signum, frame):
        nonlocal shutdown_requested
        logger.info("Shutdown requested")
        shutdown_requested = True

    signal.signal(signal.SIGINT, handle_signal)
    signal.signal(signal.SIGTERM, handle_signal)

    try:
        # Initial serial connection with retry
        while not shutdown_requested:
            try:
                serial_handler.open()
                break
            except serial.SerialException as e:
                logger.error(
                    "Failed to open serial port: %s (retrying in %ds)",
                    e,
                    INITIAL_RETRY_DELAY,
                )
                time.sleep(INITIAL_RETRY_DELAY)

        if shutdown_requested:
            return

        mqtt_handler.connect()

        logger.info(
            "Bridge running: mesh_id='%s', publishing to '%s/%s/rx'",
            config.mesh.id,
            config.mqtt.root_topic,
            config.mesh.id,
        )

        # Main loop: poll serial, forward to MQTT
        while not shutdown_requested:
            if not serial_handler.connected:
                # Attempt reconnection
                if serial_handler.try_reconnect():
                    logger.info("Serial reconnected")
                continue

            try:
                packets = serial_handler.read_packets()
                for packet in packets:
                    mqtt_handler.publish_packet(packet)
            except SerialDisconnected:
                logger.warning("Serial connection lost, will attempt reconnection")
                # Loop will handle reconnection on next iteration

    except Exception as e:
        logger.error("Unexpected error: %s", e)
        sys.exit(1)
    finally:
        mqtt_handler.disconnect()
        serial_handler.close()
        logger.info("Bridge stopped")


if __name__ == "__main__":
    main()
