from flask import Flask, render_template, request, jsonify
import os
import random
import time

# Create app and set template folder
app = Flask(__name__)

# Store reference to the RSSI server
rssi_server = None

@app.route('/')
def index():
    """Main page with login form"""
    return '''
    <!DOCTYPE html>
    <html>
    <head>
        <title>Wi-Fi RSSI Reporter</title>
        <meta name="viewport" content="width=device-width, initial-scale=1">
        <style>
            body {
                font-family: Arial, sans-serif;
                margin: 0;
                padding: 20px;
                max-width: 500px;
                margin: 0 auto;
            }
            h1 {
                color: #333;
            }
            .form-group {
                margin-bottom: 15px;
            }
            label {
                display: block;
                margin-bottom: 5px;
                font-weight: bold;
            }
            input[type="text"], input[type="password"] {
                width: 100%;
                padding: 8px;
                border: 1px solid #ddd;
                border-radius: 4px;
            }
            button {
                background-color: #4CAF50;
                color: white;
                padding: 10px 15px;
                border: none;
                border-radius: 4px;
                cursor: pointer;
            }
            button:hover {
                background-color: #45a049;
            }
            .response {
                margin-top: 20px;
                padding: 10px;
                border-radius: 4px;
                display: none;
            }
            .success {
                background-color: #dff0d8;
                border: 1px solid #d6e9c6;
                color: #3c763d;
            }
            .error {
                background-color: #f2dede;
                border: 1px solid #ebccd1;
                color: #a94442;
            }
        </style>
    </head>
    <body>
        <h1>Wi-Fi RSSI Reporter</h1>
        <p>Enter your device name and the password to report your Wi-Fi signal strength.</p>
        
        <div id="form-container">
            <div class="form-group">
                <label for="device_name">Device Name:</label>
                <input type="text" id="device_name" name="device_name" placeholder="e.g., my-phone">
            </div>
            
            <div class="form-group">
                <label for="password">Password:</label>
                <input type="password" id="password" name="password" placeholder="Enter password">
            </div>
            
            <button id="submit-btn">Submit</button>
        </div>
        
        <div id="response" class="response"></div>
        
        <script>
            // Function to simulate RSSI measurement 
            function simulateRSSI() {
                // Generate random RSSI between -30 (excellent) and -90 (poor)
                return Math.floor(Math.random() * (-30 - (-90)) + (-90));
            }
            
            document.getElementById('submit-btn').addEventListener('click', function() {
                const deviceName = document.getElementById('device_name').value;
                const password = document.getElementById('password').value;
                const rssi = simulateRSSI();
                
                if (!deviceName || !password) {
                    showResponse('Please enter both device name and password.', false);
                    return;
                }
                
                // Send data to server
                fetch('/submit', {
                    method: 'POST',
                    headers: {
                        'Content-Type': 'application/json',
                    },
                    body: JSON.stringify({
                        device_name: deviceName,
                        password: password,
                        rssi: rssi
                    }),
                })
                .then(response => response.json())
                .then(data => {
                    if (data.success) {
                        showResponse(`Successfully registered device "${deviceName}" with RSSI: ${rssi} dBm (${data.quality})`, true);
                    } else {
                        showResponse(`Error: ${data.message}`, false);
                    }
                })
                .catch(error => {
                    showResponse('Error connecting to server: ' + error, false);
                });
            });
            
            function showResponse(message, isSuccess) {
                const responseDiv = document.getElementById('response');
                responseDiv.textContent = message;
                responseDiv.className = isSuccess ? 'response success' : 'response error';
                responseDiv.style.display = 'block';
            }
        </script>
    </body>
    </html>
    '''

@app.route('/submit', methods=['POST'])
def submit():
    """Handle form submission"""
    # Get data from request
    data = request.json
    device_name = data.get('device_name', '')
    password = data.get('password', '')
    rssi = data.get('rssi', 0)
    
    # Print debug information
    print(f"[DEBUG] Web submission: device={device_name}, rssi={rssi}")
    
    # Check password
    if password != "login":
        return jsonify({"success": False, "message": "Invalid password"})
    
    # Add device to RSSI server
    if rssi_server:
        # Use the server's existing mechanism to track devices
        with rssi_server.lock:
            rssi_server.devices[device_name] = {
                "rssi": int(rssi),
                "last_seen": time.time()
            }
        print(f"[INFO] Web registered device: {device_name} with RSSI: {rssi} dBm")
        
        # Convert RSSI to quality for the response
        quality = "Unknown"
        if rssi >= -50:
            quality = "Excellent"
        elif rssi >= -60:
            quality = "Good"
        elif rssi >= -70:
            quality = "Fair"
        elif rssi >= -80:
            quality = "Poor"
        else:
            quality = "Very Poor"
            
        return jsonify({"success": True, "quality": quality})
    else:
        return jsonify({"success": False, "message": "Server not available"})

def start_web_server(host='0.0.0.0', port=5000, server=None):
    """Start the Flask web server"""
    global rssi_server
    rssi_server = server
    print(f"[INFO] Starting web server at http://{host}:{port}")
    app.run(host=host, port=port, debug=False, threaded=True) 