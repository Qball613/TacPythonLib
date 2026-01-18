#!/usr/bin/env python3
"""Quick test script to interface with a LoRa Mesh TAK radio."""

import sys
import serial.tools.list_ports

# Add the current directory to path for imports
sys.path.insert(0, '.')

import lora_mesh_tak as mt


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
    
    print(f"\nConnecting to {port}...")
    
    try:
        with mt.LoRaMeshClient(port, timeout=2.0) as client:
            print("Connected!\n")
            
            # Get device info
            print("Requesting device info...")
            info = client.get_info(timeout=5.0)
            if info:
                node = info.node_info
                print(f"  Node ID: {node.node_id}")
                # 'callsign' is not present in the NodeInfo protobuf; skip if unavailable
                print(f"  Firmware: {info.firmware_version}")
                print(f"  Protocol: {info.protocol_version}")
                print(f"  Uptime: {info.uptime_ms / 1000:.1f}s")
                print(f"  Neighbors: {info.neighbor_count}")
                print(f"  Routes: {info.route_count}")
            else:
                print("  No response (timeout)")
            
            print()
            
            # Get GPS
            print("Requesting GPS...")
            gps = client.get_gps(timeout=5.0)
            if gps:
                if gps.has_fix:
                    print(f"  Position: {gps.latitude:.6f}, {gps.longitude:.6f}")
                    print(f"  Altitude: {gps.altitude_m:.1f}m")
                    print(f"  Satellites: {gps.satellites}")
                else:
                    print("  No GPS fix")
            else:
                print("  No response (timeout)")
            
            print()
            
            # Get neighbors
            print("Requesting neighbors...")
            neighbors = client.get_neighbors(timeout=5.0)
            if neighbors is not None:
                if neighbors:
                    for n in neighbors:
                        # `NodeInfo` does not include `callsign`; show available fields
                        print(f"  - {n.node_id} RSSI: {n.rssi}dBm")
                else:
                    print("  No neighbors")
            else:
                print("  No response (timeout)")
            
            print()
            
            # Get stats
            print("Requesting stats...")
            stats = client.get_stats(timeout=5.0)
            if stats:
                print(f"  Messages sent: {stats.messages_sent}")
                print(f"  Messages received: {stats.messages_received}")
                print(f"  Messages forwarded: {stats.messages_forwarded}")
            else:
                print("  No response (timeout)")
            
            print()
            print("Test complete!")
            
    except Exception as e:
        print(f"Error: {e}")
        import traceback
        traceback.print_exc()


if __name__ == "__main__":
    main()
