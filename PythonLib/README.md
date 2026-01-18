# LoRa Mesh TAK Python Library

Python API for communicating with LoRa Mesh TAK firmware devices via SLIP-framed protobuf serial protocol.

## Installation

```bash
pip install -e .
```

## Quick Start

```python
import lora_mesh_tak as mt

# Connect to device
with mt.LoRaMeshClient("COM3") as client:  # or "/dev/ttyUSB0" on Linux
    # Get device info
    info = client.get_info()
    print(f"Node ID: {info.node_info.node_id}")
    print(f"Firmware: {info.firmware_version}")
    
    # Get GPS position
    gps = client.get_gps()
    if gps.has_fix:
        print(f"Position: {gps.latitude}, {gps.longitude}")
    
    # Get neighbors
    neighbors = client.get_neighbors()
    for n in neighbors:
        print(f"Neighbor: {n.node_id} (RSSI: {n.rssi})")
    
    # Send a message to the mesh network
    client.send_message("Hello from Python!")
```

## Event Callbacks

Handle async events from the mesh network:

```python
import lora_mesh_tak as mt
import time

def on_message(event):
    print(f"Message from {event.from_}: {event.text}")

def on_emergency(event):
    print(f"EMERGENCY from {event.from_}: {event.description}")

client = mt.LoRaMeshClient("COM3")
client.connect()

# Register callbacks
client.on_message(on_message)
client.on_emergency(on_emergency)

# Keep running
try:
    while True:
        time.sleep(1)
except KeyboardInterrupt:
    client.disconnect()
```

## API Reference

### LoRaMeshClient

#### Query Methods
- `get_info()` - Get device information (node ID, firmware, etc.)
- `get_gps()` - Get current GPS position
- `get_neighbors()` - Get list of directly connected neighbors
- `get_routes()` - Get routing table
- `get_roster()` - Get team roster (all known nodes)
- `get_stats()` - Get device statistics

#### Configuration Methods
- `set_gps(lat, lon, alt, use_static)` - Set GPS position manually
- `set_node_id(node_id)` - Set the node ID

#### Action Methods
- `send_message(text)` - Send a message to the mesh network
- `send_gps()` - Broadcast current GPS position
- `send_emergency(type, description)` - Send emergency alert
- `ping(destination)` - Ping a node
- `discover()` - Trigger network discovery
- `join()` - Join the mesh network

#### Event Callbacks
- `on_message(callback)` - Received messages
- `on_gps(callback)` - GPS position updates
- `on_neighbor(callback)` - Neighbor changes
- `on_emergency(callback)` - Emergency alerts
- `on_log(callback)` - Log messages

## Protocol

This library implements the SLIP-framed protobuf serial protocol as defined in the firmware. 

- **Framing**: SLIP (RFC 1055) with 0xC0 delimiters
- **Serialization**: Protocol Buffers
- **Baud Rate**: 115200 (default)

## Regenerating Protobufs

The protobuf definitions are hosted on Buf Schema Registry. To regenerate:

```bash
# Install buf CLI
# See: https://buf.build/docs/installation

# Generate Python files
buf generate buf.build/qballq/tacprotobuf
```

## License

GPL-3.0
