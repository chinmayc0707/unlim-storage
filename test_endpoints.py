import subprocess
import time
import requests

# Start the app
process = subprocess.Popen(["python3", "app.py"])
time.sleep(2) # Wait for server to start

try:
    # 1. Register a user
    res = requests.post("http://localhost:5000/api/auth/register", json={"phone": "+123", "password": "pass"})
    print("Register response:", res.status_code, res.json())

    # 2. Login
    res = requests.post("http://localhost:5000/api/auth/login", json={"phone": "+123", "password": "pass"})
    print("Login response:", res.status_code, res.json())
    token = res.json().get('token')

    # 3. Access protected route
    res = requests.get("http://localhost:5000/api/auth/status", headers={"Authorization": f"Bearer {token}"})
    print("Status response with token:", res.status_code, res.json())

    # 4. Access protected route without token
    res = requests.get("http://localhost:5000/api/auth/status")
    print("Status response without token:", res.status_code, res.json())

finally:
    process.terminate()
