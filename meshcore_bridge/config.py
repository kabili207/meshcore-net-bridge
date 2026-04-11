"""Configuration loading and validation."""

from dataclasses import dataclass
from pathlib import Path

import yaml


@dataclass
class MqttConfig:
    broker: str
    port: int = 1883
    username: str | None = None
    password: str | None = None
    topic: str = "meshcore/bridge"


@dataclass
class NodeConfig:
    id: str


@dataclass
class SerialConfig:
    port: str
    baud: int = 115200


@dataclass
class Config:
    mqtt: MqttConfig
    node: NodeConfig
    serial: SerialConfig


def load_config(path: Path) -> Config:
    """Load and validate configuration from YAML file."""
    with open(path) as f:
        raw = yaml.safe_load(f)

    errors = []

    # Validate required sections
    if "mqtt" not in raw:
        errors.append("missing 'mqtt' section")
    elif "broker" not in raw["mqtt"]:
        errors.append("mqtt.broker is required")

    if "node" not in raw:
        errors.append("missing 'node' section")
    elif "id" not in raw["node"]:
        errors.append("node.id is required")

    if "serial" not in raw:
        errors.append("missing 'serial' section")
    elif "port" not in raw["serial"]:
        errors.append("serial.port is required")

    if errors:
        raise ValueError(f"configuration validation failed: {'; '.join(errors)}")

    mqtt_raw = raw["mqtt"]
    mqtt = MqttConfig(
        broker=mqtt_raw["broker"],
        port=mqtt_raw.get("port", 1883),
        username=mqtt_raw.get("username"),
        password=mqtt_raw.get("password"),
        topic=mqtt_raw.get("topic", "meshcore/bridge"),
    )

    node = NodeConfig(id=raw["node"]["id"])

    serial_raw = raw["serial"]
    serial = SerialConfig(
        port=serial_raw["port"],
        baud=serial_raw.get("baud", 115200),
    )

    return Config(mqtt=mqtt, node=node, serial=serial)
