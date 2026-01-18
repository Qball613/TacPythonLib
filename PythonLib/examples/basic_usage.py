#!/usr/bin/env python3
"""Basic usage example for LoRa Mesh TAK Python API.

This example demonstrates how to connect to a LoRa Mesh TAK device
and perform basic operations.
"""

import lora_mesh_tak as mt


def on_message_received(event: mt.serial_pb2.MessageReceivedEvent):
    """Handle incoming messages."""
    print(f"Message from {event.node_id}: {event.text}")


def on_gps_received(event: mt.serial_pb2.GPSReceivedEvent):
    """Handle incoming GPS updates."""
    pos = event.position
    print(f"GPS from {event.node_id}: {pos.latitude}, {pos.longitude}")


def on_emergency(event: mt.serial_pb2.EmergencyReceivedEvent):
    """Handle emergency alerts."""
    print(f"🚨 EMERGENCY from {event.node_id}: {event.description}")


def main():
    # Replace with your actual serial port
    # Windows: "COM3", "COM4", etc.
    # Linux: "/dev/ttyUSB0", "/dev/ttyACM0", etc.
    # macOS: "/dev/cu.usbmodem...", etc.
    port = "COM3"
    
    print(f"Connecting to LoRa Mesh TAK device on {port}...")
    
    with mt.LoRaMeshClient(port) as client:
        # Register event callbacks
        client.on_message(on_message_received)
        client.on_gps(on_gps_received)
        client.on_emergency(on_emergency)
        
        # Get device info
        info = client.get_info(timeout=5.0)
        if info:
            print(f"\nDevice Info:")
            print(f"  Node ID: {info.node_id}")
            print(f"  Callsign: {info.callsign}")
            print(f"  Firmware: {info.firmware_version}")
            print(f"  Neighbors: {info.neighbor_count}")
            print(f"  Routes: {info.route_count}")
        
        # Get GPS position
        gps = client.get_gps(timeout=5.0)
        if gps and gps.has_fix:
            print(f"\nGPS Position:")
            print(f"  Latitude: {gps.latitude}")
            print(f"  Longitude: {gps.longitude}")
            print(f"  Altitude: {gps.altitude_m}m")
            print(f"  Satellites: {gps.satellites}")
        
        # Get neighbors
        neighbors = client.get_neighbors(timeout=5.0)
        if neighbors:
            print(f"\nNeighbors ({len(neighbors)}):")
            for n in neighbors:
                print(f"  - {n.node_id} ({n.callsign}) RSSI: {n.rssi}dBm")
        
        # Get routing table
        routes = client.get_routes(timeout=5.0)
        if routes:
            print(f"\nRoutes ({len(routes)}):")
            for r in routes:
                print(f"  - {r.destination} via {r.next_hop} ({r.hop_count} hops)")
        
        # Send a message to the mesh network
        # result = client.send_message("Hello from Python!")
        # if result:
        #     print(f"Message sent: {result}")
        
        print("\nListening for events (Ctrl+C to stop)...")
        try:
            while True:
                # Process incoming events
                client.process_events()
        except KeyboardInterrupt:
            print("\nStopping...")


if __name__ == "__main__":
    main()
