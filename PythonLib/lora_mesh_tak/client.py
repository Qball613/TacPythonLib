"""LoRa Mesh TAK Serial Client.

High-level Python API for communicating with LoRa Mesh TAK firmware
over serial (USB) connection using SLIP-framed protobufs.
"""

from __future__ import annotations

import threading
import time
from dataclasses import dataclass
from typing import Callable, Optional, Iterator
from contextlib import contextmanager

import serial

from lora_mesh_tak.slip import slip_encode, SlipReader, SLIP_END
from lora_mesh_tak.proto.v1 import serial_pb2, common_pb2, messages_pb2


# Type aliases for callbacks
MessageCallback = Callable[[serial_pb2.MessageReceivedEvent], None]
GPSCallback = Callable[[serial_pb2.GPSReceivedEvent], None]
NeighborCallback = Callable[[serial_pb2.NeighborChangedEvent], None]
EmergencyCallback = Callable[[serial_pb2.EmergencyReceivedEvent], None]
LogCallback = Callable[[serial_pb2.LogEvent], None]


@dataclass
class NodeInfo:
    """Node information."""
    node_id: str
    latitude: Optional[float] = None
    longitude: Optional[float] = None
    altitude: Optional[float] = None
    battery_level: int = 0
    rssi: int = 0
    last_seen: int = 0
    
    @classmethod
    def from_proto(cls, proto: common_pb2.NodeInfo) -> "NodeInfo":
        """Create from protobuf message."""
        lat = lon = alt = None
        if proto.HasField("position"):
            lat = proto.position.latitude
            lon = proto.position.longitude
            alt = proto.position.altitude
        return cls(
            node_id=proto.node_id,
            latitude=lat,
            longitude=lon,
            altitude=alt,
            battery_level=proto.battery_level,
            rssi=proto.rssi,
            last_seen=proto.last_seen,
        )


@dataclass
class GPSPosition:
    """GPS position data."""
    latitude: float
    longitude: float
    altitude: float = 0.0
    accuracy: float = 0.0
    speed: float = 0.0
    bearing: float = 0.0
    timestamp: int = 0
    has_fix: bool = True
    satellites: int = 0
    hdop: float = 0.0
    
    @classmethod
    def from_proto(cls, proto: common_pb2.GPSCoordinate, 
                   has_fix: bool = True, satellites: int = 0, 
                   hdop: float = 0.0) -> "GPSPosition":
        """Create from protobuf message."""
        return cls(
            latitude=proto.latitude,
            longitude=proto.longitude,
            altitude=proto.altitude,
            accuracy=proto.accuracy,
            speed=proto.speed,
            bearing=proto.bearing,
            timestamp=proto.timestamp,
            has_fix=has_fix,
            satellites=satellites,
            hdop=hdop,
        )
    
    def to_proto(self) -> common_pb2.GPSCoordinate:
        """Convert to protobuf message."""
        return common_pb2.GPSCoordinate(
            latitude=self.latitude,
            longitude=self.longitude,
            altitude=self.altitude,
            accuracy=self.accuracy,
            speed=self.speed,
            bearing=self.bearing,
            timestamp=self.timestamp,
        )


@dataclass
class RouteEntry:
    """Routing table entry."""
    destination: str
    next_hop: str
    hop_count: int
    rssi: int
    last_update: int
    
    @classmethod
    def from_proto(cls, proto: serial_pb2.RouteEntry) -> "RouteEntry":
        """Create from protobuf message."""
        return cls(
            destination=proto.destination,
            next_hop=proto.next_hop,
            hop_count=proto.hop_count,
            rssi=proto.rssi,
            last_update=proto.last_update,
        )


@dataclass 
class RosterEntry:
    """Team roster entry."""
    node: NodeInfo
    is_self: bool
    is_active: bool
    
    @classmethod
    def from_proto(cls, proto: serial_pb2.RosterEntry) -> "RosterEntry":
        """Create from protobuf message."""
        return cls(
            node=NodeInfo.from_proto(proto.node),
            is_self=proto.is_self,
            is_active=proto.is_active,
        )


@dataclass
class DeviceStats:
    """Device statistics."""
    messages_sent: int
    messages_received: int
    messages_forwarded: int
    messages_dropped: int
    route_discoveries: int
    route_errors: int
    mesh_version: int
    uptime_ms: int
    
    @classmethod
    def from_proto(cls, proto: serial_pb2.GetStatsResponse) -> "DeviceStats":
        """Create from protobuf message."""
        return cls(
            messages_sent=proto.messages_sent,
            messages_received=proto.messages_received,
            messages_forwarded=proto.messages_forwarded,
            messages_dropped=proto.messages_dropped,
            route_discoveries=proto.route_discoveries,
            route_errors=proto.route_errors,
            mesh_version=proto.mesh_version,
            uptime_ms=proto.uptime_ms,
        )
    
    @property
    def uptime_seconds(self) -> float:
        """Get uptime in seconds."""
        return self.uptime_ms / 1000.0


@dataclass
class DeviceInfo:
    """Device information."""
    node_info: NodeInfo
    firmware_version: str
    protocol_version: str
    mesh_version: int
    neighbor_count: int
    route_count: int
    uptime_ms: int
    
    @classmethod
    def from_proto(cls, proto: serial_pb2.GetInfoResponse) -> "DeviceInfo":
        """Create from protobuf message."""
        return cls(
            node_info=NodeInfo.from_proto(proto.node_info),
            firmware_version=proto.firmware_version,
            protocol_version=proto.protocol_version,
            mesh_version=proto.mesh_version,
            neighbor_count=proto.neighbor_count,
            route_count=proto.route_count,
            uptime_ms=proto.uptime_ms,
        )


class LoRaMeshClient:
    """High-level client for LoRa Mesh TAK devices.
    
    Provides a clean Python API for communicating with LoRa Mesh TAK
    firmware over serial (USB) connection.
    
    Example:
        >>> client = LoRaMeshClient("/dev/ttyUSB0")
        >>> client.connect()
        >>> info = client.get_info()
        >>> print(f"Node ID: {info.node_info.node_id}")
        >>> client.send_message("NODE_B", "Hello!")
        >>> client.disconnect()
        
    With context manager:
        >>> with LoRaMeshClient("/dev/ttyUSB0") as client:
        ...     info = client.get_info()
        ...     print(f"Connected to {info.node_info.node_id}")
    """
    
    DEFAULT_BAUDRATE = 115200
    DEFAULT_TIMEOUT = 5.0
    
    def __init__(
        self,
        port: str,
        baudrate: int = DEFAULT_BAUDRATE,
        timeout: float = DEFAULT_TIMEOUT,
    ) -> None:
        """Initialize the client.
        
        Args:
            port: Serial port path (e.g., "COM3" or "/dev/ttyUSB0").
            baudrate: Serial baud rate (default: 115200).
            timeout: Default timeout for commands in seconds.
        """
        self._port = port
        self._baudrate = baudrate
        self._timeout = timeout
        self._serial: Optional[serial.Serial] = None
        self._slip_reader = SlipReader()
        self._packet_id = 0
        self._lock = threading.Lock()
        
        # Callbacks for async events
        self._on_message: Optional[MessageCallback] = None
        self._on_gps: Optional[GPSCallback] = None
        self._on_neighbor: Optional[NeighborCallback] = None
        self._on_emergency: Optional[EmergencyCallback] = None
        self._on_log: Optional[LogCallback] = None
        
        # Background reader thread
        self._reader_thread: Optional[threading.Thread] = None
        self._running = False
        self._pending_responses: dict[int, serial_pb2.FromDevice] = {}
        self._response_events: dict[int, threading.Event] = {}
    
    def __enter__(self) -> "LoRaMeshClient":
        self.connect()
        return self
    
    def __exit__(self, exc_type, exc_val, exc_tb) -> None:
        self.disconnect()
    
    @property
    def is_connected(self) -> bool:
        """Check if connected to device."""
        return self._serial is not None and self._serial.is_open
    
    def connect(self) -> None:
        """Open connection to the device.
        
        Raises:
            serial.SerialException: If connection fails.
        """
        if self.is_connected:
            return
            
        self._serial = serial.Serial(
            port=self._port,
            baudrate=self._baudrate,
            timeout=0.1,  # Short timeout for non-blocking reads
        )
        self._slip_reader.clear()
        self._running = True
        self._reader_thread = threading.Thread(target=self._read_loop, daemon=True)
        self._reader_thread.start()
    
    def disconnect(self) -> None:
        """Close connection to the device."""
        self._running = False
        if self._reader_thread:
            self._reader_thread.join(timeout=1.0)
            self._reader_thread = None
        if self._serial:
            self._serial.close()
            self._serial = None
        self._slip_reader.clear()
    
    def _next_packet_id(self) -> int:
        """Get next packet ID."""
        self._packet_id = (self._packet_id + 1) % 0xFFFFFFFF
        return self._packet_id
    
    def _send_packet(self, packet: serial_pb2.SerialPacket) -> None:
        """Send a SLIP-encoded packet."""
        if not self.is_connected:
            raise ConnectionError("Not connected to device")
        
        data = packet.SerializeToString()
        framed = slip_encode(data)
        with self._lock:
            self._serial.write(framed)
            self._serial.flush()
    
    def _send_command(
        self,
        to_device: serial_pb2.ToDevice,
        timeout: Optional[float] = None,
    ) -> serial_pb2.FromDevice:
        """Send command and wait for response.
        
        Args:
            to_device: The command to send.
            timeout: Response timeout in seconds (uses default if None).
            
        Returns:
            Response from device.
            
        Raises:
            TimeoutError: If no response received within timeout.
            ConnectionError: If not connected.
        """
        timeout = timeout if timeout is not None else self._timeout
        packet_id = self._next_packet_id()
        
        packet = serial_pb2.SerialPacket(
            packet_id=packet_id,
            to_device=to_device,
        )
        
        # Set up response waiting
        event = threading.Event()
        self._response_events[packet_id] = event
        
        try:
            self._send_packet(packet)
            
            # Wait for response
            if not event.wait(timeout):
                raise TimeoutError(f"No response within {timeout}s")
            
            return self._pending_responses.pop(packet_id)
        finally:
            self._response_events.pop(packet_id, None)
    
    def _read_loop(self) -> None:
        """Background thread for reading serial data."""
        while self._running and self._serial:
            try:
                data = self._serial.read(256)
                if data:
                    self._slip_reader.feed(data)
                    while self._slip_reader.has_packet():
                        packet_data = self._slip_reader.get_packet()
                        if packet_data:
                            self._handle_packet(packet_data)
            except Exception:
                if self._running:
                    time.sleep(0.1)
    
    def _handle_packet(self, data: bytes) -> None:
        """Handle a received packet."""
        try:
            packet = serial_pb2.SerialPacket()
            packet.ParseFromString(data)
            
            if packet.HasField("from_device"):
                response = packet.from_device
                request_id = response.request_id
                
                # Check if this is a response to a pending command
                if request_id in self._response_events:
                    self._pending_responses[request_id] = response
                    self._response_events[request_id].set()
                else:
                    # Handle async events
                    self._handle_event(response)
        except Exception:
            pass  # Ignore malformed packets
    
    def _handle_event(self, response: serial_pb2.FromDevice) -> None:
        """Handle async events from device."""
        payload_type = response.WhichOneof("payload")
        
        if payload_type == "message_received" and self._on_message:
            self._on_message(response.message_received)
        elif payload_type == "gps_received" and self._on_gps:
            self._on_gps(response.gps_received)
        elif payload_type == "neighbor_changed" and self._on_neighbor:
            self._on_neighbor(response.neighbor_changed)
        elif payload_type == "emergency_received" and self._on_emergency:
            self._on_emergency(response.emergency_received)
        elif payload_type == "log" and self._on_log:
            self._on_log(response.log)
    
    # Event callbacks
    def on_message(self, callback: Optional[MessageCallback]) -> None:
        """Set callback for received messages."""
        self._on_message = callback
    
    def on_gps(self, callback: Optional[GPSCallback]) -> None:
        """Set callback for GPS position updates."""
        self._on_gps = callback
    
    def on_neighbor(self, callback: Optional[NeighborCallback]) -> None:
        """Set callback for neighbor changes."""
        self._on_neighbor = callback
    
    def on_emergency(self, callback: Optional[EmergencyCallback]) -> None:
        """Set callback for emergency alerts."""
        self._on_emergency = callback
    
    def on_log(self, callback: Optional[LogCallback]) -> None:
        """Set callback for log messages."""
        self._on_log = callback
    
    # Query commands
    def get_info(self, timeout: Optional[float] = None) -> DeviceInfo:
        """Get device information.
        
        Returns:
            Device info including node ID, firmware version, etc.
        """
        cmd = serial_pb2.ToDevice(get_info=serial_pb2.GetInfoRequest())
        response = self._send_command(cmd, timeout)
        return DeviceInfo.from_proto(response.info)
    
    def get_gps(self, timeout: Optional[float] = None) -> GPSPosition:
        """Get current GPS position.
        
        Returns:
            Current GPS position data.
        """
        cmd = serial_pb2.ToDevice(get_gps=serial_pb2.GetGPSRequest())
        response = self._send_command(cmd, timeout)
        gps = response.gps
        return GPSPosition.from_proto(
            gps.position,
            has_fix=gps.has_fix,
            satellites=gps.satellites,
            hdop=gps.hdop,
        )
    
    def get_neighbors(self, timeout: Optional[float] = None) -> list[NodeInfo]:
        """Get list of neighboring nodes.
        
        Returns:
            List of directly connected neighbor nodes.
        """
        cmd = serial_pb2.ToDevice(get_neighbors=serial_pb2.GetNeighborsRequest())
        response = self._send_command(cmd, timeout)
        return [NodeInfo.from_proto(n) for n in response.neighbors.neighbors]
    
    def get_routes(self, timeout: Optional[float] = None) -> list[RouteEntry]:
        """Get routing table.
        
        Returns:
            List of known routes to destination nodes.
        """
        cmd = serial_pb2.ToDevice(get_routes=serial_pb2.GetRoutesRequest())
        response = self._send_command(cmd, timeout)
        return [RouteEntry.from_proto(r) for r in response.routes.routes]
    
    def get_roster(self, timeout: Optional[float] = None) -> list[RosterEntry]:
        """Get team roster.
        
        Returns:
            List of all known nodes in the mesh.
        """
        cmd = serial_pb2.ToDevice(get_roster=serial_pb2.GetRosterRequest())
        response = self._send_command(cmd, timeout)
        return [RosterEntry.from_proto(r) for r in response.roster.roster]
    
    def get_stats(self, timeout: Optional[float] = None) -> DeviceStats:
        """Get device statistics.
        
        Returns:
            Message counts, uptime, and other statistics.
        """
        cmd = serial_pb2.ToDevice(get_stats=serial_pb2.GetStatsRequest())
        response = self._send_command(cmd, timeout)
        return DeviceStats.from_proto(response.stats)
    
    # Configuration commands
    def set_gps(
        self,
        latitude: float,
        longitude: float,
        altitude: float = 0.0,
        use_static: bool = False,
        timeout: Optional[float] = None,
    ) -> bool:
        """Set GPS position manually.
        
        Args:
            latitude: Latitude in degrees.
            longitude: Longitude in degrees.
            altitude: Altitude in meters.
            use_static: If True, persist position (survives reboot).
            
        Returns:
            True if successful.
        """
        position = common_pb2.GPSCoordinate(
            latitude=latitude,
            longitude=longitude,
            altitude=altitude,
        )
        cmd = serial_pb2.ToDevice(
            set_gps=serial_pb2.SetGPSRequest(
                position=position,
                use_static=use_static,
            )
        )
        response = self._send_command(cmd, timeout)
        return response.result.success if response.HasField("result") else True
    
    def set_node_id(self, node_id: str, timeout: Optional[float] = None) -> bool:
        """Set the node ID.
        
        Args:
            node_id: New node ID string.
            
        Returns:
            True if successful.
            
        Note:
            Device may require restart after changing node ID.
        """
        cmd = serial_pb2.ToDevice(
            set_node_id=serial_pb2.SetNodeIDRequest(node_id=node_id)
        )
        response = self._send_command(cmd, timeout)
        return response.result.success if response.HasField("result") else True
    
    # Action commands
    def send_message(
        self,
        text: str,
        priority: Optional[int] = None,
        timeout: Optional[float] = None,
        auto_split: bool = False,
    ) -> str:
        """Send a text message to the mesh network.
        
        Note: All messages are broadcast to the mesh network.
        The mesh protocol handles routing and delivery.
        
        Args:
            text: Message text (max 180 chars due to firmware 256-byte buffer).
            priority: Message priority (0-5, where 3=NORMAL, 4=HIGH, 5=CRITICAL).
            auto_split: If True, automatically split long messages into multiple sends.
                       If False, raise ValueError for messages over 180 chars.
            
        Returns:
            Empty string.
            
        Raises:
            ValueError: If message is too long and auto_split=False.
        """
        MAX_LENGTH = 180  # Firmware buffer constraint
        
        # Single message - send directly
        if len(text) <= MAX_LENGTH:
            cmd = serial_pb2.ToDevice(
                send_message=serial_pb2.SendMessageRequest(
                    destination="",
                    text=text,
                )
            )
            self._send_command(cmd, timeout)
            return ""
        
        # Message too long
        if not auto_split:
            raise ValueError(
                f"Message too long ({len(text)} chars). Max: {MAX_LENGTH}\n"
                f"Use auto_split=True to automatically split into multiple messages, "
                f"or split manually."
            )
        
        # Split and send multiple messages
        return self._send_split_message(text, priority, timeout)
    
    def _send_split_message(
        self,
        text: str,
        priority: Optional[int],
        timeout: Optional[float],
    ) -> str:
        """Split a long message and send as multiple parts."""
        CHUNK_SIZE = 160  # Leave room for part indicator
        
        # Split into chunks
        chunks = [text[i:i+CHUNK_SIZE] for i in range(0, len(text), CHUNK_SIZE)]
        total = len(chunks)
        
        for i, chunk in enumerate(chunks):
            # Add part indicator
            part_text = f"[{i+1}/{total}] {chunk}"
            
            cmd = serial_pb2.ToDevice(
                send_message=serial_pb2.SendMessageRequest(
                    destination="",
                    text=part_text,
                )
            )
            
            self._send_command(cmd, timeout)
            
            # Small delay between parts
            if i < total - 1:
                time.sleep(0.3)
        
        return ""
    
    def broadcast(self, text: str, timeout: Optional[float] = None) -> str:
        """Send a message to the mesh network.
        
        Alias for send_message(). All messages are broadcast to the mesh.
        
        Args:
            text: Message text.
            
        Returns:
            Message ID of the sent message.
        """
        return self.send_message(text, timeout)
    
    def send_gps(self, timeout: Optional[float] = None) -> bool:
        """Broadcast current GPS position.
        
        Returns:
            True if successful.
        """
        cmd = serial_pb2.ToDevice(send_gps=serial_pb2.SendGPSRequest())
        response = self._send_command(cmd, timeout)
        return response.result.success if response.HasField("result") else True
    
    def send_emergency(
        self,
        emergency_type: messages_pb2.EmergencyType = messages_pb2.EMERGENCY_TYPE_OTHER,
        description: str = "",
        timeout: Optional[float] = None,
    ) -> bool:
        """Send an emergency alert.
        
        Args:
            emergency_type: Type of emergency.
            description: Optional description.
            
        Returns:
            True if successful.
        """
        cmd = serial_pb2.ToDevice(
            send_emergency=serial_pb2.SendEmergencyRequest(
                emergency_type=emergency_type,
                description=description,
            )
        )
        response = self._send_command(cmd, timeout)
        return response.result.success if response.HasField("result") else True
    
    def ping(self, destination: str, timeout: Optional[float] = None) -> bool:
        """Ping a destination node.
        
        Args:
            destination: Node ID to ping.
            
        Returns:
            True if successful.
        """
        cmd = serial_pb2.ToDevice(
            ping=serial_pb2.PingRequest(destination=destination)
        )
        response = self._send_command(cmd, timeout)
        return response.result.success if response.HasField("result") else True
    
    def discover(self, timeout: Optional[float] = None) -> bool:
        """Trigger network discovery.
        
        Returns:
            True if successful.
        """
        cmd = serial_pb2.ToDevice(discover=serial_pb2.DiscoverRequest())
        response = self._send_command(cmd, timeout)
        return response.result.success if response.HasField("result") else True
    
    def join(self, timeout: Optional[float] = None) -> bool:
        """Join the mesh network.
        
        Returns:
            True if successful.
        """
        cmd = serial_pb2.ToDevice(join=serial_pb2.JoinRequest())
        response = self._send_command(cmd, timeout)
        return response.result.success if response.HasField("result") else True


# Convenience function to list available serial ports
def list_ports() -> list[str]:
    """List available serial ports.
    
    Returns:
        List of port names that could be LoRa Mesh TAK devices.
    """
    import serial.tools.list_ports
    ports = []
    for port in serial.tools.list_ports.comports():
        ports.append(port.device)
    return ports
