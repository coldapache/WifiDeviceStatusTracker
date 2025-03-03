import socket
import threading
import time

class RSSIServer:
    def __init__(self, host='0.0.0.0', port=5000):
        # Dictionary to store device data: {device_name: {"rssi": value, "last_seen": timestamp}}
        self.devices = {}
        self.lock = threading.Lock()  # For thread-safe updates
        self.server = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        # Allow port reuse for quick restarts
        self.server.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        self.server.bind((host, port))
        self.server.listen(5)
        print(f"[INFO] Server started - listening on {host}:{port}")
        print(f"[INFO] Waiting for devices to connect with password 'login'")

    def handle_client(self, conn, addr):
        """Handle individual device connections"""
        print(f"[INFO] New connection from {addr}")
        try:
            # Set a timeout to prevent hanging connections
            conn.settimeout(10)
            data = conn.recv(1024).decode().strip()
            
            # Debug the received data
            print(f"[DEBUG] Received data: {data}")
            
            # Expect data in format: "password|device_name|rssi"
            parts = data.split('|')
            if len(parts) == 3 and parts[0] == "login":
                device_name, rssi_str = parts[1], parts[2]
                try:
                    rssi = int(rssi_str)
                    with self.lock:
                        self.devices[device_name] = {
                            "rssi": rssi,
                            "last_seen": time.time()
                        }
                    print(f"[INFO] Updated device: {device_name} with RSSI: {rssi} dBm")
                    conn.sendall(b"SUCCESS")
                except ValueError:
                    print(f"[ERROR] Invalid RSSI value: {rssi_str}")
                    conn.sendall(b"ERROR: Invalid RSSI format")
            else:
                print(f"[WARN] Authentication failed or invalid data format: {data}")
                conn.sendall(b"ERROR: Authentication failed")
        except socket.timeout:
            print(f"[WARN] Connection from {addr} timed out")
        except Exception as e:
            print(f"[ERROR] Exception handling client {addr}: {e}")
        finally:
            conn.close()
            print(f"[INFO] Connection from {addr} closed")

    def start(self):
        """Start the server to accept connections"""
        print("[INFO] Server is now accepting connections")
        while True:
            try:
                conn, addr = self.server.accept()
                # Create a new thread for each client
                client_thread = threading.Thread(
                    target=self.handle_client, 
                    args=(conn, addr)
                )
                client_thread.daemon = True
                client_thread.start()
            except Exception as e:
                print(f"[ERROR] Exception accepting connection: {e}")

    def get_devices(self):
        """Return a copy of the current devices dictionary"""
        with self.lock:
            # Prune devices not seen in the last 30 seconds
            current_time = time.time()
            to_remove = []
            for device, data in self.devices.items():
                if current_time - data["last_seen"] > 30:
                    to_remove.append(device)
            
            # Remove stale devices
            for device in to_remove:
                print(f"[INFO] Removing stale device: {device}")
                del self.devices[device]
                
            # Return copy of current devices (just RSSI values)
            return {device: data["rssi"] for device, data in self.devices.items()}

# Start the server if run directly
if __name__ == "__main__":
    rssi_server = RSSIServer()
    
    try:
        # Run the server in the main thread
        rssi_server.start()
    except KeyboardInterrupt:
        print("[INFO] Server shutting down...")
    except Exception as e:
        print(f"[ERROR] Unexpected error: {e}") 