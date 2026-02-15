# MeshCore Net Bridge

A companion application that bridges [MeshCore](https://github.com/ripplebiz/MeshCore) mesh networks to MQTT brokers via the RS232 serial protocol. Enables mesh-to-mesh connectivity and multi-mesh coordination on shared MQTT infrastructure without requiring custom MeshCore firmware.

## How It Works

The bridge connects to a stock MeshCore repeater configured with the RS232 bridge feature over serial, and relays packets bidirectionally to/from an MQTT broker.

- **Mesh to MQTT:** Packets received from the local mesh via serial are base64-encoded and published to `{root_topic}/{mesh_id}`
- **MQTT to Mesh:** Packets from other meshes are received via MQTT, decoded, and written back to the local repeater over serial
- **Loop prevention:** Messages originating from the local mesh ID are ignored
- **Identity preservation:** Full MeshCore packet structure (encrypted payload, sender pubkey hash, routing metadata) is preserved end-to-end

### MQTT Topics

```
meshcore/{mesh_id}
```

Each bridge publishes to its own mesh ID topic and subscribes to `meshcore/+` to receive from all other meshes. The `root_topic` prefix is configurable (default: `meshcore`).

Payloads are base64-encoded raw packet bytes with no additional envelope.

## Requirements

- Python 3.10+
- A MeshCore repeater with RS232 bridge enabled
- An MQTT broker

## Installation

```bash
pip install .
```

Or for development:

```bash
pip install -e .
```

## Configuration

Copy the example config and edit it:

```bash
cp config.example.yaml config.yaml
```

```yaml
mqtt:
  broker: "mqtt.example.com"
  port: 1883
  # username: ""
  # password: ""
  root_topic: "meshcore"

mesh:
  id: "cabin"

serial:
  port: "/dev/ttyAMA0"
  baud: 115200
```

- **mesh.id** - A unique identifier for this mesh network. Used in MQTT topics and the client ID.
- **serial.port** - The serial device connected to the MeshCore repeater.
- **serial.baud** - Baud rate (default: 115200, matching MeshCore's RS232 bridge default).

## Usage

```bash
meshcore-bridge -c config.yaml
```

Options:
- `-c`, `--config` - Path to config file (default: `config.yaml`)
- `-v`, `--verbose` - Enable debug logging

## Features

- Bidirectional packet bridging (serial <-> MQTT)
- Automatic reconnection with exponential backoff for both serial and MQTT
- Graceful shutdown on SIGINT/SIGTERM
- Thread-safe serial writes (MQTT callbacks write to serial from a separate thread)
- MeshCore RS232 frame protocol (0xC03E magic header, Fletcher-16 checksums)
