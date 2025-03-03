import tkinter as tk
from tkinter import ttk
import threading
import time

class RSSIMonitorUI:
    def __init__(self, root, rssi_server):
        self.root = root
        self.rssi_server = rssi_server
        self.setup_ui()
        
        # Start the update loop
        self.update_ui()
    
    def setup_ui(self):
        """Set up the UI components"""
        self.root.title("Wi-Fi Device RSSI Monitor")
        self.root.geometry("500x400")
        
        # Create header frame
        header_frame = ttk.Frame(self.root, padding="10")
        header_frame.pack(fill=tk.X)
        
        ttk.Label(
            header_frame, 
            text="Wi-Fi Device RSSI Monitor", 
            font=("Arial", 16, "bold")
        ).pack(side=tk.LEFT)
        
        # Server status indicator
        self.status_var = tk.StringVar(value="Server Running")
        self.status_label = ttk.Label(
            header_frame, 
            textvariable=self.status_var,
            foreground="green"
        )
        self.status_label.pack(side=tk.RIGHT)
        
        # Create treeview for device list
        tree_frame = ttk.Frame(self.root, padding="10")
        tree_frame.pack(fill=tk.BOTH, expand=True)
        
        # Create scrollbar
        scrollbar = ttk.Scrollbar(tree_frame)
        scrollbar.pack(side=tk.RIGHT, fill=tk.Y)
        
        # Create and configure treeview
        columns = ("device", "rssi", "signal_quality")
        self.tree = ttk.Treeview(
            tree_frame, 
            columns=columns,
            show="headings",
            yscrollcommand=scrollbar.set
        )
        
        # Define column headings
        self.tree.heading("device", text="Device Name")
        self.tree.heading("rssi", text="RSSI (dBm)")
        self.tree.heading("signal_quality", text="Signal Quality")
        
        # Define column widths
        self.tree.column("device", width=200)
        self.tree.column("rssi", width=100)
        self.tree.column("signal_quality", width=150)
        
        # Pack the treeview
        self.tree.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        
        # Configure the scrollbar
        scrollbar.config(command=self.tree.yview)
        
        # Status bar for information
        self.info_var = tk.StringVar(value="Ready")
        status_bar = ttk.Label(
            self.root, 
            textvariable=self.info_var,
            relief=tk.SUNKEN, 
            anchor=tk.W
        )
        status_bar.pack(side=tk.BOTTOM, fill=tk.X)
        
        # Instructions label
        instructions = (
            "Devices can connect using 'python client.py <device_name> <server_ip>'\n"
            "Password is 'login'"
        )
        ttk.Label(
            self.root, 
            text=instructions,
            foreground="gray"
        ).pack(side=tk.BOTTOM, fill=tk.X, padx=10, pady=5)
    
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
    
    def update_ui(self):
        """Update the UI with current device information"""
        try:
            # Get the latest device data
            devices = self.rssi_server.get_devices()
            print(f"[DEBUG] UI update - Found {len(devices)} devices")
            
            # Clear existing entries
            for item in self.tree.get_children():
                self.tree.delete(item)
            
            # Add each device to the treeview
            for device_name, rssi in devices.items():
                quality = self.rssi_to_quality(rssi)
                self.tree.insert(
                    "", 
                    "end", 
                    values=(device_name, rssi, quality)
                )
            
            # Update the status information
            self.info_var.set(f"Last updated: {time.strftime('%H:%M:%S')} - {len(devices)} device(s) connected")
            
        except Exception as e:
            print(f"[ERROR] UI update error: {e}")
            self.status_var.set("Error")
            self.status_label.config(foreground="red")
        
        # Schedule the next update
        self.root.after(1000, self.update_ui)

# If this file is run directly, start both server and UI
if __name__ == "__main__":
    import socket
    from server import RSSIServer
    
    # Get local IP address for display purposes
    hostname = socket.gethostname()
    try:
        local_ip = socket.gethostbyname(hostname)
    except:
        local_ip = "127.0.0.1"
    
    print(f"[INFO] Server IP address: {local_ip}")
    print("[INFO] Starting RSSI monitoring server...")
    
    # Create the server
    rssi_server = RSSIServer()
    
    # Start server in a separate thread
    server_thread = threading.Thread(target=rssi_server.start)
    server_thread.daemon = True
    server_thread.start()
    
    # Create and start the UI
    print("[INFO] Starting UI...")
    root = tk.Tk()
    app = RSSIMonitorUI(root, rssi_server)
    
    # Add IP address information to the UI
    info_label = ttk.Label(
        root,
        text=f"Server running at: {local_ip}:5000",
        font=("Arial", 10)
    )
    info_label.pack(side=tk.BOTTOM, fill=tk.X, padx=10)
    
    # Start the UI main loop
    root.mainloop() 