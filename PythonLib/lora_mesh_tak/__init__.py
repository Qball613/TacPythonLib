"""LoRa Mesh TAK Python API.

A Python library for communicating with LoRa Mesh TAK firmware devices
via SLIP-framed protobuf serial protocol.

Usage:
    import lora_mesh_tak as mt
    
    # Connect and use
    with mt.LoRaMeshClient("COM3") as client:
        client.send_message("Hello World", mt.MessagePriority.NORMAL)
"""

__version__ = "0.1.0"


def __getattr__(name):
    """Lazy import to avoid circular import issues with protobuf files."""
    # Main client class
    if name == "LoRaMeshClient":
        from lora_mesh_tak.client import LoRaMeshClient
        return LoRaMeshClient
    
    # Data classes
    if name == "NodeInfo":
        from lora_mesh_tak.client import NodeInfo
        return NodeInfo
    if name == "GPSPosition":
        from lora_mesh_tak.client import GPSPosition
        return GPSPosition
    if name == "RouteEntry":
        from lora_mesh_tak.client import RouteEntry
        return RouteEntry
    if name == "RosterEntry":
        from lora_mesh_tak.client import RosterEntry
        return RosterEntry
    if name == "DeviceStats":
        from lora_mesh_tak.client import DeviceStats
        return DeviceStats
    if name == "DeviceInfo":
        from lora_mesh_tak.client import DeviceInfo
        return DeviceInfo
    
    # SLIP encoding
    if name == "slip_encode":
        from lora_mesh_tak.slip import slip_encode
        return slip_encode
    if name == "slip_decode":
        from lora_mesh_tak.slip import slip_decode
        return slip_decode
    if name == "SlipReader":
        from lora_mesh_tak.slip import SlipReader
        return SlipReader
    
    # Utility functions
    if name == "list_ports":
        from lora_mesh_tak.client import list_ports
        return list_ports
    
    # Protobuf modules
    if name == "serial_pb2":
        from lora_mesh_tak.proto.v1 import serial_pb2
        return serial_pb2
    if name == "common_pb2":
        from lora_mesh_tak.proto.v1 import common_pb2
        return common_pb2
    if name == "messages_pb2":
        from lora_mesh_tak.proto.v1 import messages_pb2
        return messages_pb2
    
    # Enums and constants (from protobuf)
    if name == "MessagePriority":
        from lora_mesh_tak.proto.v1.messages_pb2 import MessagePriority
        return MessagePriority
    if name == "EmergencyType":
        from lora_mesh_tak.proto.v1.messages_pb2 import EmergencyType
        return EmergencyType
    
    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")


__all__ = [
    # Main client
    "LoRaMeshClient",
    "list_ports",
    
    # Data classes
    "NodeInfo",
    "GPSPosition",
    "RouteEntry",
    "RosterEntry",
    "DeviceStats",
    "DeviceInfo",
    
    # SLIP encoding
    "slip_encode",
    "slip_decode",
    "SlipReader",
    
    # Protobuf modules
    "serial_pb2",
    "common_pb2",
    "messages_pb2",
    
    # Enums
    "MessagePriority",
    "EmergencyType",
]
