import socket
import time
import subprocess
import platform
import re
import sys
import random

def get_rssi():
    """Get the Wi-Fi RSSI from Windows using netsh"""
    try:
        print("[DEBUG] Running Windows netsh command")
        output = subprocess.check_output("netsh wlan show interfaces", shell=True).decode()
        print(f"[DEBUG] Command output: {output[:100]}...")
        
        signal_match = re.search(r"Signal\s+:\s(\d+)%", output)
        if signal_match:
            signal_percent = int(signal_match.group(1))
            # Convert percentage to dBm (approximate)
            rssi = int((signal_percent / 2) - 100)
            print(f"[INFO] Windows signal strength: {signal_percent}% ≈ {rssi} dBm")
            return rssi
        else:
            print("[WARN] Could not find signal strength in Windows output")
            return -70  # Default fallback value
    except Exception as e:
        print(f"[ERROR] RSSI detection failed: {e}")
        return -70  # Default fallback value

def send_rssi_to_server(device_name, server_host, server_port=5000):
    """Send the RSSI value to the server with authentication"""
    try:
        # Get the current RSSI
        rssi = get_rssi()
        
        # Connect to the server
        print(f"[INFO] Connecting to server at {server_host}:{server_port}")
        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
            s.settimeout(5)  # Set timeout to prevent hanging
            s.connect((server_host, server_port))
            
            # Format the message with password and send it
            message = f"login|{device_name}|{rssi}"
            print(f"[DEBUG] Sending message: {message}")
            s.sendall(message.encode())
            
            # Wait for server response
            response = s.recv(1024).decode()
            print(f"[INFO] Server response: {response}")
            
            return True
    except socket.timeout:
        print("[ERROR] Connection to server timed out")
    except ConnectionRefusedError:
        print(f"[ERROR] Connection refused - is the server running at {server_host}:{server_port}?")
    except Exception as e:
        print(f"[ERROR] Failed to send data: {e}")
    
    return False

def main(device_name, server_host, server_port=5000, interval=5):
    """Main loop to periodically send RSSI updates"""
    print(f"[INFO] Starting RSSI reporter for device '{device_name}'")
    print(f"[INFO] Will connect to server at {server_host}:{server_port}")
    print(f"[INFO] Update interval: {interval} seconds")
    
    while True:
        success = send_rssi_to_server(device_name, server_host, server_port)
        
        # Wait before the next update
        print(f"[INFO] Waiting {interval} seconds before next update")
        time.sleep(interval)

if __name__ == "__main__":
    # Parse command line arguments
    if len(sys.argv) < 3:
        print("Usage: python client.py <device_name> <server_host> [server_port] [interval]")
        print("Example: python client.py my-laptop 192.168.1.100 5000 10")
        sys.exit(1)
    
    device_name = sys.argv[1]
    server_host = sys.argv[2]
    
    # Optional arguments
    server_port = int(sys.argv[3]) if len(sys.argv) > 3 else 5000
    interval = int(sys.argv[4]) if len(sys.argv) > 4 else 5
    
    try:
        main(device_name, server_host, server_port, interval)
    except KeyboardInterrupt:
        print("[INFO] Client shutting down...")
    except Exception as e:
        print(f"[ERROR] Unexpected error: {e}") 