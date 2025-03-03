import threading
import socket
import tkinter as tk
from tkinter import ttk
import time
import sys
import importlib
from http.server import HTTPServer, BaseHTTPRequestHandler
import json
import urllib.parse
import random
import math

# Try to import Flask, but continue if not available
try:
    from web_server import start_web_server
    has_flask = True
    print("[INFO] Flask found - web interface will be enabled")
except ImportError:
    has_flask = False

class RSSIServer:
    def __init__(self, host='0.0.0.0', port=5001):  # Socket server on port 5001
        # Dictionary to store device data: {device_name: {"rssi": value, "last_seen": timestamp}}
        self.devices = {}
        self.lock = threading.Lock()  # For thread-safe updates
        self.server = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        # Allow port reuse for quick restarts
        self.server.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        self.server.bind((host, port))
        self.server.listen(5)
        print(f"[INFO] Socket server started - listening on {host}:{port}")
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
                        # Add connection timestamp for tracking active status
                        self.devices[device_name] = {
                            "rssi": rssi,
                            "last_seen": time.time(),
                            "ip": addr[0],
                            "active": True  # Mark as active
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
        print("[INFO] Socket server is now accepting connections")
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
            # No more stale device removal - keep all devices
            return self.devices.copy()

class SimpleHTTPRequestHandler(BaseHTTPRequestHandler):
    def do_GET(self):
        """Serve a simple HTML page with a form"""
        if self.path == '/':
            self.send_response(200)
            self.send_header('Content-type', 'text/html')
            self.end_headers()
            self.wfile.write(b"""
            <html>
            <head>
                <title>Wi-Fi RSSI Reporter</title>
                <style>
                    body { font-family: Arial, sans-serif; padding: 20px; }
                    .success { color: green; }
                    .error { color: red; }
                </style>
            </head>
            <body>
                <h1>Wi-Fi RSSI Reporter</h1>
                <div id="status"></div>
                <form id="rssiForm" onsubmit="submitForm(event)">
                    <label for="device_name">Device Name:</label>
                    <input type="text" id="device_name" name="device_name" required><br><br>
                    <label for="password">Password:</label>
                    <input type="password" id="password" name="password" required><br><br>
                    <input type="submit" value="Submit">
                </form>

                <script>
                function submitForm(event) {
                    event.preventDefault();
                    const deviceName = document.getElementById('device_name').value;
                    const password = document.getElementById('password').value;
                    const status = document.getElementById('status');

                    // Get client IP address from server
                    fetch('/submit?' + new URLSearchParams({
                        device_name: deviceName,
                        password: password,
                        client_ip: window.location.hostname
                    }))
                    .then(response => response.json())
                    .then(data => {
                        if (data.success) {
                            status.innerHTML = `<p class="success">Successfully connected! RSSI: ${data.rssi} dBm (${data.quality})</p>`;
                            // Keep updating status
                            setInterval(() => updateStatus(deviceName), 5000);
                        } else {
                            status.innerHTML = `<p class="error">Error: ${data.message}</p>`;
                        }
                    })
                    .catch(error => {
                        status.innerHTML = `<p class="error">Error: ${error}</p>`;
                    });
                }

                function updateStatus(deviceName) {
                    fetch('/status?' + new URLSearchParams({device_name: deviceName}))
                    .then(response => response.json())
                    .then(data => {
                        const status = document.getElementById('status');
                        if (data.connected) {
                            status.innerHTML = `<p class="success">Connected! RSSI: ${data.rssi} dBm (${data.quality})</p>`;
                        } else {
                            status.innerHTML = `<p class="error">Device disconnected</p>`;
                        }
                    });
                }
                </script>
            </body>
            </html>
            """)
        elif self.path.startswith('/submit'):
            query = urllib.parse.urlparse(self.path).query
            params = dict(urllib.parse.parse_qsl(query))
            device_name = params.get('device_name', '')
            password = params.get('password', '')
            client_ip = self.client_address[0]  # Get actual client IP
            rssi = random.randint(-90, -30)  # Simulate RSSI value

            if password == "login":
                with rssi_server.lock:
                    rssi_server.devices[device_name] = {
                        "rssi": rssi,
                        "last_seen": time.time(),
                        "ip": client_ip  # Store client IP
                    }
                quality = self.rssi_to_quality(rssi)
                print(f"[INFO] New device connected - Name: {device_name}, IP: {client_ip}, RSSI: {rssi}")
                self.send_response(200)
                self.send_header('Content-type', 'application/json')
                self.end_headers()
                self.wfile.write(json.dumps({
                    "success": True,
                    "rssi": rssi,
                    "quality": quality
                }).encode())
            else:
                self.send_response(403)
                self.send_header('Content-type', 'application/json')
                self.end_headers()
                self.wfile.write(json.dumps({
                    "success": False,
                    "message": "Invalid password"
                }).encode())
        elif self.path.startswith('/status'):
            query = urllib.parse.urlparse(self.path).query
            params = dict(urllib.parse.parse_qsl(query))
            device_name = params.get('device_name', '')
            
            self.send_response(200)
            self.send_header('Content-type', 'application/json')
            self.end_headers()
            
            with rssi_server.lock:
                device = rssi_server.devices.get(device_name)
                if device and (time.time() - device["last_seen"]) < 30:
                    quality = self.rssi_to_quality(device["rssi"])
                    self.wfile.write(json.dumps({
                        "connected": True,
                        "rssi": device["rssi"],
                        "quality": quality
                    }).encode())
                else:
                    self.wfile.write(json.dumps({
                        "connected": False
                    }).encode())

    def rssi_to_quality(self, rssi):
        """Convert RSSI value to a human-readable quality description"""
        if rssi >= -50:
            return "Excellent"
        elif rssi >= -60:
            return "Good"
        elif rssi >= -70:
            return "Fair"
        elif rssi >= -80:
            return "Poor"
        else:
            return "Very Poor"

    def log_message(self, format, *args):
        """Override to prevent printing to stderr"""
        return

def get_local_ip():
    """Get the local IP address of this machine"""
    try:
        # This is more reliable for getting the correct network IP
        s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        s.connect(("8.8.8.8", 80))
        ip = s.getsockname()[0]
        s.close()
        return ip
    except:
        print("[WARN] Could not determine network IP, falling back to hostname method")
        try:
            return socket.gethostbyname(socket.gethostname())
        except:
            print("[ERROR] Could not determine IP address, using localhost")
            return "127.0.0.1"

def start_http_server(host='0.0.0.0', port=5000, server=None):
    """Start the simple HTTP server"""
    global rssi_server
    rssi_server = server
    
    # Print the actual addresses the server will be available on
    local_ip = get_local_ip()
    print(f"[INFO] Server will be available at:")
    print(f"[INFO] Local machine: http://localhost:{port}")
    print(f"[INFO] Network devices: http://{local_ip}:{port}")
    
    try:
        httpd = HTTPServer((host, port), SimpleHTTPRequestHandler)
        print(f"[INFO] HTTP server is ready to accept connections")
        httpd.serve_forever()
    except Exception as e:
        print(f"[ERROR] Failed to start HTTP server: {e}")
        raise

class RSSIMonitorUI:
    def __init__(self, root, rssi_server):
        self.root = root
        self.rssi_server = rssi_server
        self.setup_ui()
        
        # Start the update loop
        self.update_ui()
    
    def setup_ui(self):
        """Set up the UI components"""
        self.root.title("Wi-Fi RSSI Monitor")
        self.root.geometry("1000x600")  # Made wider for the chart
        self.root.configure(bg='#1a1a1a')
        
        # Configure styles
        style = ttk.Style()
        style.configure(".", background='#1a1a1a', foreground='#00ff00')
        style.configure("TNotebook", background='#1a1a1a')
        style.configure("TNotebook.Tab", background='white', foreground='black')
        style.configure("DeviceList.Treeview", 
            background='white', 
            foreground='black',
            fieldbackground='white'
        )
        style.configure("DeviceList.Treeview.Heading", 
            background='#f0f0f0',
            foreground='black'
        )
        
        # Create main container
        main_frame = ttk.Frame(self.root)
        main_frame.pack(fill=tk.BOTH, expand=True, padx=10, pady=5)
        
        # Create left frame for tabs
        left_frame = ttk.Frame(main_frame)
        left_frame.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        
        # Create notebook (tabbed interface)
        self.notebook = ttk.Notebook(left_frame)
        self.notebook.pack(fill=tk.BOTH, expand=True)
        
        # Tab 1: Device List
        devices_tab = ttk.Frame(self.notebook)
        self.notebook.add(devices_tab, text='Connected Devices')
        
        # Setup device list
        columns = ("device", "ip", "rssi", "distance")
        self.tree = ttk.Treeview(devices_tab, columns=columns, show="headings", style="DeviceList.Treeview")
        
        self.tree.heading("device", text="Device Name")
        self.tree.heading("ip", text="IP Address")
        self.tree.heading("rssi", text="RSSI (dBm)")
        self.tree.heading("distance", text="Est. Distance (m)")
        
        self.tree.column("device", width=100)
        self.tree.column("ip", width=120)
        self.tree.column("rssi", width=80)
        self.tree.column("distance", width=100)
        
        self.tree.pack(fill=tk.BOTH, expand=True)
        
        # Tab 2: History Chart
        history_tab = ttk.Frame(self.notebook)
        self.notebook.add(history_tab, text='Signal History')
        
        # Setup history chart with dark theme
        self.history_canvas = tk.Canvas(
            history_tab,
            background='black',
            width=400,
            height=300
        )
        self.history_canvas.pack(fill=tk.BOTH, expand=True, padx=5, pady=5)
        
        # Initialize history data structure with more points for longer timeline
        self.signal_history = {}  # {device_name: [(timestamp, rssi), ...]}
        self.history_max_points = 300  # 5 minutes at 1 update per second
        
        # Create right frame for radar
        map_frame = ttk.Frame(main_frame)
        map_frame.pack(side=tk.RIGHT, fill=tk.BOTH, expand=True)
        
        # Setup radar map (right side)
        self.canvas = tk.Canvas(
            map_frame, 
            width=400, 
            height=400, 
            bg='#1a1a1a',
            highlightbackground='#00ff00',
            highlightthickness=1
        )
        self.canvas.pack(padx=10, pady=10)
        
        # Draw radar circles
        center_x, center_y = 200, 200
        for radius in [45, 90, 135, 180]:  # Represents 1m, 2m, 3m, 4m
            self.canvas.create_oval(
                center_x - radius, 
                center_y - radius,
                center_x + radius, 
                center_y + radius,
                outline='#00ff00',
                dash=(2, 4)
            )
            # Add distance label
            self.canvas.create_text(
                center_x, 
                center_y - radius,
                text=f"{radius/45}m",
                fill='#00ff00',
                font=('Courier', 8)
            )
        
        # Draw crosshairs
        self.canvas.create_line(200, 0, 200, 400, fill='#00ff00', dash=(2, 4))
        self.canvas.create_line(0, 200, 400, 200, fill='#00ff00', dash=(2, 4))
        
        # Draw router at center with glow effect
        self.canvas.create_oval(190, 190, 210, 210, fill='#00ff00', outline='#00ff00')
        self.canvas.create_text(200, 170, text="Router", fill='#00ff00', font=('Courier', 10))
        
        # Status bar
        self.status_var = tk.StringVar(value="Radar Active")
        self.status_label = ttk.Label(
            self.root,
            textvariable=self.status_var,
            font=("Courier", 10)
        )
        self.status_label.pack(side=tk.BOTTOM, fill=tk.X, padx=10)

    def rssi_to_distance(self, rssi):
        """Convert RSSI to approximate distance in meters"""
        # Calibrated conversion based on known distances:
        # -50 dBm ≈ 1 meter
        # -70 dBm ≈ 3 meters
        if rssi >= -30:  # Very close
            return 0.5
        elif rssi >= -50:  # Around 1 meter
            return 1.0
        elif rssi >= -60:  # Around 2 meters
            return 2.0
        elif rssi >= -70:  # Around 3 meters
            return 3.0
        elif rssi >= -80:  # Around 4 meters
            return 4.0
        else:  # Very far
            return 5.0

    def update_device_positions(self, devices):
        """Update device positions on the radar"""
        print("[DEBUG] Updating device positions on radar")
        self.canvas.delete("device")  # Remove old device markers
        
        center_x, center_y = 200, 200
        
        for device_name, data in devices.items():
            rssi = data["rssi"]
            distance = self.rssi_to_distance(rssi)
            print(f"[DEBUG] Device: {device_name}, RSSI: {rssi}, Distance: {distance}m")
            
            # Convert distance to canvas coordinates (scale: 45 pixels = 1 meter)
            radius = min(distance * 45, 180)
            
            # Calculate position (use device name hash for consistent angle)
            angle = hash(device_name) % 360
            x = center_x + radius * math.cos(math.radians(angle))
            y = center_y + radius * math.sin(math.radians(angle))
            
            # Draw device blip with pulsing effect
            for size in [10, 8, 6]:
                self.canvas.create_oval(
                    x-size, y-size, x+size, y+size,
                    fill='#00ff00',
                    stipple='gray50',
                    tags="device"
                )
            
            # Device label
            self.canvas.create_text(
                x, y-20,
                text=f"{device_name}\n{rssi}dBm",
                fill='#00ff00',
                font=('Courier', 9),
                tags="device"
            )
            
            print(f"[DEBUG] Placed {device_name} at ({x}, {y}) on radar")

    def update_history_chart(self):
        """Update the signal history chart"""
        try:
            self.history_canvas.delete("all")
            
            # Chart dimensions
            padding = 40
            width = self.history_canvas.winfo_width() - 2 * padding
            height = self.history_canvas.winfo_height() - 2 * padding
            
            # Draw grid
            for i in range(0, height + padding, 20):
                y = padding + i
                self.history_canvas.create_line(
                    padding, y,
                    width + padding, y,
                    fill='#333333',
                    dash=(1, 2)
                )
            
            for i in range(0, width + padding, 40):
                x = padding + i
                self.history_canvas.create_line(
                    x, padding,
                    x, height + padding,
                    fill='#333333',
                    dash=(1, 2)
                )
            
            # Draw axes
            self.history_canvas.create_line(
                padding, padding,
                padding, height + padding,
                fill='#666666',
                width=2
            )
            self.history_canvas.create_line(
                padding, height + padding,
                width + padding, height + padding,
                fill='#666666',
                width=2
            )
            
            # Draw RSSI scale (-30 to -90 dBm)
            for rssi in range(-30, -91, -10):
                y = padding + ((-30 - rssi) / 60.0) * height
                self.history_canvas.create_line(
                    padding - 5, y,
                    padding, y,
                    fill='#666666'
                )
                self.history_canvas.create_text(
                    padding - 10, y,
                    text=str(rssi),
                    fill='#666666',
                    anchor='e',
                    font=('Courier', 8)
                )
            
            # Plot data for each device
            colors = {'#0066ff': 'blue', '#ff3333': 'red', '#00ff00': 'green', '#ff00ff': 'purple', '#ff9900': 'orange'}
            legend_y = padding
            
            for i, (device, history) in enumerate(self.signal_history.items()):
                if len(history) > 1:
                    color = list(colors.keys())[i % len(colors)]
                    points = []
                    
                    # Convert timestamps to x-coordinates
                    newest_time = max(t for t, _ in history)
                    oldest_time = newest_time - (self.history_max_points * 0.5)  # 5 minutes
                    
                    for timestamp, rssi in history:
                        # Skip points older than our window
                        if timestamp < oldest_time:
                            continue
                        
                        x = padding + ((timestamp - oldest_time) / (newest_time - oldest_time)) * width
                        y = padding + ((-30 - rssi) / 60.0) * height
                        points.extend([x, y])
                    
                    if len(points) >= 4:
                        # Draw line with slight glow effect
                        for offset in [2, 1, 0]:
                            self.history_canvas.create_line(
                                points,
                                fill=color,
                                width=3-offset,
                                smooth=True,
                                stipple='gray50' if offset > 0 else ''
                            )
                    
                    # Add device label to legend
                    self.history_canvas.create_text(
                        width + padding - 10,
                        legend_y,
                        text=device,
                        fill=color,
                        anchor='e',
                        font=('Courier', 10)
                    )
                    legend_y += 20
            
            # Add time labels
            current_time = time.strftime('%H:%M:%S')
            self.history_canvas.create_text(
                width + padding, height + padding + 15,
                text=current_time,
                fill='#666666',
                anchor='e',
                font=('Courier', 8)
            )
            
            five_min_ago = time.strftime('%H:%M:%S', time.localtime(time.time() - 300))
            self.history_canvas.create_text(
                padding, height + padding + 15,
                text=five_min_ago,
                fill='#666666',
                anchor='w',
                font=('Courier', 8)
            )
            
        except Exception as e:
            print(f"[ERROR] History chart update error: {e}")

    def update_ui(self):
        """Update the UI with current device information"""
        try:
            devices = self.rssi_server.get_devices()
            current_time = time.time()
            
            # Update device list and history
            for item in self.tree.get_children():
                self.tree.delete(item)
            
            for device_name, data in devices.items():
                rssi = data["rssi"]
                ip = data.get("ip", "Unknown")
                distance = self.rssi_to_distance(rssi)
                
                # Update device list
                self.tree.insert(
                    "", 
                    "end",
                    values=(device_name, ip, f"{rssi} dBm", f"{distance}m")
                )
                
                # Update signal history
                if device_name not in self.signal_history:
                    self.signal_history[device_name] = []
                
                self.signal_history[device_name].append((current_time, rssi))
                
                # Keep history within time window (5 minutes)
                cutoff_time = current_time - 300  # 5 minutes ago
                self.signal_history[device_name] = [
                    (t, r) for t, r in self.signal_history[device_name]
                    if t >= cutoff_time
                ]
            
            # Update visualizations
            self.update_device_positions(devices)
            self.update_history_chart()
            
            # Update status bar
            self.status_var.set(
                f"Connected Devices: {len(devices)} | "
                f"Last Updated: {time.strftime('%H:%M:%S')}"
            )
            
        except Exception as e:
            print(f"[ERROR] UI update error: {e}")
            self.status_var.set("Error updating UI")
        
        # Schedule next update
        self.root.after(1000, self.update_ui)  # Update every second

def main():
    """Main function to start the entire system"""
    local_ip = get_local_ip()
    print("\n=== Network Configuration ===")
    print(f"[INFO] Local IP address: {local_ip}")
    
    # Print all network interfaces
    print("\n[DEBUG] Available Network Interfaces:")
    for iface in socket.if_nameindex():
        try:
            addr = socket.gethostbyname(socket.gethostname())
            print(f"[DEBUG] Interface {iface[1]}: {addr}")
        except:
            print(f"[DEBUG] Interface {iface[1]}: Unable to get address")
    
    print("\n=== Starting Servers ===")
    
    # Create a single server instance that will be shared
    socket_port = 5001  # Use a different port for the socket server
    web_port = 5000     # Use the standard port for web
    
    rssi_server = RSSIServer(port=socket_port)
    
    # Start the HTTP server in a separate thread with the same server instance
    print(f"[INFO] Starting web interface on port {web_port}...")
    web_thread = threading.Thread(
        target=start_http_server,
        args=('0.0.0.0', web_port, rssi_server),
        daemon=True
    )
    web_thread.start()
    
    # Start socket server in a separate thread
    print(f"[INFO] Starting socket server on port {socket_port}...")
    server_thread = threading.Thread(target=rssi_server.start)
    server_thread.daemon = True
    server_thread.start()
    
    # Start the UI with the same server instance
    print("[INFO] Starting UI...")
    root = tk.Tk()
    app = RSSIMonitorUI(root, rssi_server)
    
    # Add IP address information to the UI with instructions for web access
    web_instructions = f"Web Interface: http://{local_ip}:{web_port}"
    socket_instructions = f"Socket Server: {local_ip}:{socket_port}"
    
    info_frame = ttk.Frame(root)
    info_frame.pack(side=tk.BOTTOM, fill=tk.X, padx=10, pady=5)
    
    ttk.Label(
        info_frame,
        text=web_instructions,
        font=("Arial", 10)
    ).pack(side=tk.TOP, anchor=tk.W)
    
    ttk.Label(
        info_frame,
        text=socket_instructions,
        font=("Arial", 10)
    ).pack(side=tk.TOP, anchor=tk.W)
    
    # Start the UI main loop
    root.mainloop()

if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        print("[INFO] Application shutting down...")
    except Exception as e:
        print(f"[ERROR] Unexpected error: {e}")
        sys.exit(1) 