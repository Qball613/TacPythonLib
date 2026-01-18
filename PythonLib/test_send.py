#!/usr/bin/env python3
"""Simple test script to debug message sending."""

import sys
sys.path.insert(0, '.')

import lora_mesh_tak as mt
import serial.tools.list_ports

def main():
    # List ports
    ports = list(serial.tools.list_ports.comports())
    if not ports:
        print("No serial ports found!")
        return
    
    print("Available ports:")
    for i, port in enumerate(ports):
        print(f"  [{i}] {port.device}")
    
    # Get port
    if len(sys.argv) > 1:
        port = sys.argv[1]
    else:
        sel = input("Select port (0): ").strip() or "0"
        port = ports[int(sel)].device
    
    print(f"\nConnecting to {port}...")
    
    try:
        client = mt.LoRaMeshClient(port, timeout=5.0)
        client.connect()
        print("Connected!")
        
        # Get info first to verify communication works
        print("\nGetting device info...")
        info = client.get_info(timeout=5.0)
        if info:
            print(f"  Device: {info.node_info.node_id}")
            print(f"  Firmware: {info.firmware_version}")
        else:
            print("  Failed to get info!")
            return
        
        # Now try to send a message
        print("\nSending test message...")
        try:
            result = client.send_message("Test message from Python", timeout=5.0)
            print(f"  Success! Message ID: {result if result else '(none)'}")
        except TimeoutError as e:
            print(f"  Timeout: {e}")
        except Exception as e:
            print(f"  Error: {type(e).__name__}: {e}")
            import traceback
            traceback.print_exc()
        
        # Disconnect
        client.disconnect()
        print("\nDisconnected")
        
    except Exception as e:
        print(f"Error: {e}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    main()
