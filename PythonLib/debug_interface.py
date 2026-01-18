#!/usr/bin/env python3
"""Interactive messaging and serial debug interface for LoRa Mesh TAK.

A terminal-based UI for debugging, monitoring, and interacting with
LoRa Mesh TAK radio devices.
"""

import sys
import threading
import time
from datetime import datetime
from typing import Optional
import serial.tools.list_ports

sys.path.insert(0, '.')
import lora_mesh_tak as mt


class DebugInterface:
    """Interactive debug and messaging interface."""
    
    def __init__(self, port: str, baudrate: int = 115200):
        self.port = port
        self.baudrate = baudrate
        self.client: Optional[mt.LoRaMeshClient] = None
        self.running = False
        self.messages = []
        self.events = []
        self.raw_data = []
        self.max_log_lines = 100
        
        # Device state
        self.device_info = None
        self.gps_position = None
        self.neighbors = []
        self.routes = []
        
    def log_event(self, message: str, level: str = "INFO"):
        """Add an event to the log."""
        timestamp = datetime.now().strftime("%H:%M:%S")
        entry = f"[{timestamp}] [{level}] {message}"
        self.events.append(entry)
        if len(self.events) > self.max_log_lines:
            self.events.pop(0)
        print(entry)
    
    def log_raw(self, data: str):
        """Log raw serial data."""
        timestamp = datetime.now().strftime("%H:%M:%S.%f")[:-3]
        entry = f"[{timestamp}] {data}"
        self.raw_data.append(entry)
        if len(self.raw_data) > self.max_log_lines:
            self.raw_data.pop(0)
    
    def on_message_received(self, event: mt.serial_pb2.MessageReceivedEvent):
        """Handle incoming messages."""
        timestamp = datetime.now().strftime("%H:%M:%S")
        msg = f"[{timestamp}] FROM {event.node_id}: {event.text}"
        self.messages.append(msg)
        if len(self.messages) > self.max_log_lines:
            self.messages.pop(0)
        self.log_event(f"Message from {event.node_id}: {event.text}", "MSG")
    
    def on_gps_received(self, event: mt.serial_pb2.GPSReceivedEvent):
        """Handle GPS updates."""
        pos = event.position
        self.log_event(
            f"GPS from {event.node_id}: {pos.latitude:.6f}, {pos.longitude:.6f}",
            "GPS"
        )
    
    def on_neighbor_changed(self, event: mt.serial_pb2.NeighborChangedEvent):
        """Handle neighbor changes."""
        self.log_event(
            f"Neighbor {event.action}: {event.node_id} (RSSI: {event.rssi}dBm)",
            "NEIGHBOR"
        )
        # Refresh neighbor list
        threading.Thread(target=self._refresh_neighbors, daemon=True).start()
    
    def on_emergency(self, event: mt.serial_pb2.EmergencyReceivedEvent):
        """Handle emergency alerts."""
        self.log_event(
            f"🚨 EMERGENCY from {event.node_id}: {event.description}",
            "EMERGENCY"
        )
    
    def on_log(self, event: mt.serial_pb2.LogEvent):
        """Handle device log messages."""
        self.log_event(f"[DEVICE] {event.message}", "LOG")
    
    def _refresh_neighbors(self):
        """Refresh neighbor list."""
        if self.client:
            try:
                neighbors = self.client.get_neighbors(timeout=2.0)
                if neighbors is not None:
                    self.neighbors = neighbors
            except Exception as e:
                self.log_event(f"Failed to refresh neighbors: {e}", "ERROR")
    
    def _refresh_routes(self):
        """Refresh routing table."""
        if self.client:
            try:
                routes = self.client.get_routes(timeout=2.0)
                if routes is not None:
                    self.routes = routes
            except Exception as e:
                self.log_event(f"Failed to refresh routes: {e}", "ERROR")
    
    def connect(self):
        """Connect to the device."""
        try:
            self.log_event(f"Connecting to {self.port}...", "INFO")
            self.client = mt.LoRaMeshClient(self.port, baudrate=self.baudrate, timeout=2.0)
            self.client.connect()
            
            # Register callbacks
            self.client.on_message(self.on_message_received)
            self.client.on_gps(self.on_gps_received)
            self.client.on_neighbor(self.on_neighbor_changed)
            self.client.on_emergency(self.on_emergency)
            self.client.on_log(self.on_log)
            
            self.log_event("Connected successfully", "SUCCESS")
            
            # Get initial device info
            self.log_event("Requesting device info...", "INFO")
            info = self.client.get_info(timeout=5.0)
            if info:
                self.device_info = info
                node = info.node_info
                self.log_event(f"Device: {node.node_id}", "INFO")
                self.log_event(f"Firmware: {info.firmware_version}", "INFO")
                self.log_event(f"Protocol: {info.protocol_version}", "INFO")
            
            # Get initial GPS
            gps = self.client.get_gps(timeout=5.0)
            if gps:
                self.gps_position = gps
                if gps.has_fix:
                    self.log_event(
                        f"GPS: {gps.latitude:.6f}, {gps.longitude:.6f} ({gps.satellites} sats)",
                        "GPS"
                    )
                else:
                    self.log_event("GPS: No fix", "GPS")
            
            # Get neighbors
            self._refresh_neighbors()
            if self.neighbors:
                self.log_event(f"Found {len(self.neighbors)} neighbors", "INFO")
            
            # Get routes
            self._refresh_routes()
            if self.routes:
                self.log_event(f"Found {len(self.routes)} routes", "INFO")
            
            return True
            
        except Exception as e:
            self.log_event(f"Connection failed: {e}", "ERROR")
            return False
    
    def disconnect(self):
        """Disconnect from the device."""
        if self.client:
            try:
                self.client.disconnect()
                self.log_event("Disconnected", "INFO")
            except Exception as e:
                self.log_event(f"Disconnect error: {e}", "ERROR")
    
    def send_message(self, text: str):
        """Send a message to the mesh network."""
        if not self.client:
            self.log_event("Not connected", "ERROR")
            return
        
        try:
            msg_preview = text[:80] + '...' if len(text) > 80 else text
            
            if len(text) > 180:
                self.log_event(f"Message is {len(text)} chars (max 180), will auto-split", "INFO")
            
            self.log_event(f"Sending: {msg_preview}", "SEND")
            
            # Use auto_split for long messages
            result = self.client.send_message(text, timeout=5.0, auto_split=True)
            self.log_event(f"Message sent successfully", "SUCCESS")
            
        except ValueError as e:
            self.log_event(f"Message error: {e}", "ERROR")
        except TimeoutError as e:
            self.log_event(f"Timeout: {e}", "ERROR")
        except ConnectionError as e:
            self.log_event(f"Connection error: {e}", "ERROR")
        except Exception as e:
            self.log_event(f"Send error ({type(e).__name__}): {e}", "ERROR")
            import traceback
            traceback.print_exc()
    
    def show_status(self):
        """Display current status."""
        print("\n" + "="*80)
        print("DEVICE STATUS")
        print("="*80)
        
        if self.device_info:
            node = self.device_info.node_info
            print(f"Node ID:      {node.node_id}")
            print(f"Firmware:     {self.device_info.firmware_version}")
            print(f"Protocol:     {self.device_info.protocol_version}")
            print(f"Uptime:       {self.device_info.uptime_ms / 1000:.1f}s")
            print(f"Neighbors:    {self.device_info.neighbor_count}")
            print(f"Routes:       {self.device_info.route_count}")
        else:
            print("No device info available")
        
        print("\n" + "-"*80)
        print("GPS POSITION")
        print("-"*80)
        
        if self.gps_position:
            if self.gps_position.has_fix:
                print(f"Latitude:     {self.gps_position.latitude:.6f}")
                print(f"Longitude:    {self.gps_position.longitude:.6f}")
                print(f"Altitude:     {self.gps_position.altitude_m:.1f}m")
                print(f"Satellites:   {self.gps_position.satellites}")
                print(f"HDOP:         {self.gps_position.hdop:.1f}")
            else:
                print("No GPS fix")
        else:
            print("No GPS data")
        
        print("\n" + "-"*80)
        print(f"NEIGHBORS ({len(self.neighbors)})")
        print("-"*80)
        
        if self.neighbors:
            for n in self.neighbors:
                print(f"  {n.node_id:20s} RSSI: {n.rssi:4d}dBm  LastSeen: {n.last_seen}s")
        else:
            print("No neighbors")
        
        print("\n" + "-"*80)
        print(f"ROUTES ({len(self.routes)})")
        print("-"*80)
        
        if self.routes:
            for r in self.routes:
                print(f"  {r.destination:20s} via {r.next_hop:20s} ({r.hop_count} hops)")
        else:
            print("No routes")
        
        print("="*80 + "\n")
    
    def show_messages(self):
        """Display message history."""
        print("\n" + "="*80)
        print("MESSAGE HISTORY")
        print("="*80)
        
        if self.messages:
            for msg in self.messages[-20:]:  # Show last 20 messages
                print(msg)
        else:
            print("No messages")
        
        print("="*80 + "\n")
    
    def show_events(self):
        """Display event log."""
        print("\n" + "="*80)
        print("EVENT LOG")
        print("="*80)
        
        if self.events:
            for event in self.events[-30:]:  # Show last 30 events
                print(event)
        else:
            print("No events")
        
        print("="*80 + "\n")
    
    def interactive_mode(self):
        """Run interactive command-line interface."""
        print("\n" + "="*80)
        print("LoRa Mesh TAK - Debug Interface")
        print("="*80)
        print("\nCommands:")
        print("  send <message>            - Send message to mesh network")
        print("  status                    - Show device status")
        print("  messages                  - Show message history")
        print("  events                    - Show event log")
        print("  neighbors                 - Refresh and show neighbors")
        print("  routes                    - Refresh and show routes")
        print("  gps                       - Get GPS position")
        print("  help                      - Show this help")
        print("  quit                      - Exit")
        print("\n")
        
        while True:
            try:
                cmd = input(">> ").strip()
                
                if not cmd:
                    continue
                
                parts = cmd.split(None, 2)
                command = parts[0].lower()
                
                if command == "quit" or command == "exit":
                    break
                
                elif command == "help":
                    print("\nCommands:")
                    print("  send <message>            - Send message to mesh network")
                    print("  status                    - Show device status")
                    print("  messages                  - Show message history")
                    print("  events                    - Show event log")
                    print("  neighbors                 - Refresh and show neighbors")
                    print("  routes                    - Refresh and show routes")
                    print("  gps                       - Get GPS position")
                    print("  help                      - Show this help")
                    print("  quit                      - Exit\n")
                
                elif command == "send":
                    if len(parts) < 2:
                        print("Usage: send <message>")
                    else:
                        message = ' '.join(parts[1:])
                        self.send_message(message)
                
                elif command == "status":
                    self.show_status()
                
                elif command == "messages":
                    self.show_messages()
                
                elif command == "events":
                    self.show_events()
                
                elif command == "neighbors":
                    self.log_event("Refreshing neighbors...", "INFO")
                    self._refresh_neighbors()
                    if self.neighbors:
                        print(f"\nNeighbors ({len(self.neighbors)}):")
                        for n in self.neighbors:
                            print(f"  {n.node_id:20s} RSSI: {n.rssi:4d}dBm")
                    else:
                        print("No neighbors found")
                
                elif command == "routes":
                    self.log_event("Refreshing routes...", "INFO")
                    self._refresh_routes()
                    if self.routes:
                        print(f"\nRoutes ({len(self.routes)}):")
                        for r in self.routes:
                            print(f"  {r.destination:20s} via {r.next_hop:20s} ({r.hop_count} hops)")
                    else:
                        print("No routes found")
                
                elif command == "gps":
                    self.log_event("Requesting GPS...", "INFO")
                    gps = self.client.get_gps(timeout=5.0)
                    if gps:
                        self.gps_position = gps
                        if gps.has_fix:
                            print(f"\nGPS Position:")
                            print(f"  Latitude:   {gps.latitude:.6f}")
                            print(f"  Longitude:  {gps.longitude:.6f}")
                            print(f"  Altitude:   {gps.altitude_m:.1f}m")
                            print(f"  Satellites: {gps.satellites}")
                        else:
                            print("No GPS fix")
                    else:
                        print("No GPS response")
                
                else:
                    print(f"Unknown command: {command}. Type 'help' for available commands.")
                
            except KeyboardInterrupt:
                print("\nUse 'quit' to exit")
            except Exception as e:
                print(f"Error: {e}")


def list_ports():
    """List available serial ports."""
    ports = serial.tools.list_ports.comports()
    if not ports:
        print("No serial ports found!")
        return []
    
    print("Available serial ports:")
    for i, port in enumerate(ports):
        print(f"  [{i}] {port.device} - {port.description}")
    return ports


def main():
    # List available ports
    ports = list_ports()
    
    if not ports:
        return
    
    # Get port selection
    print()
    if len(sys.argv) > 1:
        port = sys.argv[1]
        print(f"Using port from command line: {port}")
    else:
        try:
            selection = input("Enter port number or name (default: 0): ").strip()
            if not selection:
                selection = "0"
            
            if selection.isdigit():
                port = ports[int(selection)].device
            else:
                port = selection
        except (ValueError, IndexError):
            print("Invalid selection")
            return
    
    # Create and connect interface
    interface = DebugInterface(port)
    
    if not interface.connect():
        print("Failed to connect. Exiting.")
        return
    
    try:
        # Run interactive mode
        interface.interactive_mode()
    finally:
        interface.disconnect()
        print("Goodbye!")


if __name__ == "__main__":
    main()
