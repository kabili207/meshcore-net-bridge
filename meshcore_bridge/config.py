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
    root_topic: str = "meshcore"


@dataclass
class MeshConfig:
    id: str


@dataclass
class SerialConfig:
    port: str
    baud: int = 115200


@dataclass
class Config:
    mqtt: MqttConfig
    mesh: MeshConfig
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

    if "mesh" not in raw:
        errors.append("missing 'mesh' section")
    elif "id" not in raw["mesh"]:
        errors.append("mesh.id is required")

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
        root_topic=mqtt_raw.get("root_topic", "meshcore"),
    )

    mesh = MeshConfig(id=raw["mesh"]["id"])

    serial_raw = raw["serial"]
    serial = SerialConfig(
        port=serial_raw["port"],
        baud=serial_raw.get("baud", 115200),
    )

    return Config(mqtt=mqtt, mesh=mesh, serial=serial)
