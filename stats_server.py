"""
Helix dashboard stats server.
Run this on Windows (same venv as voice_assistant.py):
    pip install psutil flask flask-cors
    python stats_server.py

Serves real, local system stats to helix_dashboard.html at
http://127.0.0.1:8765/stats  -  nothing here executes commands,
it only reads system metrics (CPU/RAM/disk/battery/temp).
"""
import socket
import time

import psutil
from flask import Flask, jsonify
from flask_cors import CORS

app = Flask(__name__)
CORS(app)

BOOT_TIME = psutil.boot_time()


def get_cpu_temp():
    """Best-effort CPU temperature. Real hardware sensors on Windows
    usually require WMI providers that aren't present by default
    (e.g. LibreHardwareMonitor). Returns None if unavailable rather
    than fabricating a number."""
    try:
        temps = psutil.sensors_temperatures()
        if temps:
            for name, entries in temps.items():
                for entry in entries:
                    if entry.current:
                        return round(entry.current, 1)
    except (AttributeError, NotImplementedError):
        pass

    try:
        import wmi
        w = wmi.WMI(namespace="root\\wmi")
        temp_infos = w.MSAcpi_ThermalZoneTemperature()
        if temp_infos:
            kelvin_tenths = temp_infos[0].CurrentTemperature
            celsius = (kelvin_tenths / 10.0) - 273.15
            return round(celsius, 1)
    except Exception:
        pass

    return None


@app.route("/stats")
def stats():
    cpu_percent = psutil.cpu_percent(interval=0.3)
    ram = psutil.virtual_memory()
    disk = psutil.disk_usage("C:\\" if psutil.WINDOWS else "/")

    battery = None
    battery_plugged = None
    try:
        b = psutil.sensors_battery()
        if b:
            battery = round(b.percent, 1)
            battery_plugged = b.power_plugged
    except Exception:
        pass

    return jsonify({
        "hostname": socket.gethostname(),
        "cpu_percent": cpu_percent,
        "ram_percent": ram.percent,
        "disk_percent": disk.percent,
        "temp_c": get_cpu_temp(),
        "uptime_seconds": int(time.time() - BOOT_TIME),
        "process_count": len(psutil.pids()),
        "battery_percent": battery,
        "battery_plugged": battery_plugged,
    })


if __name__ == "__main__":
    print("Helix stats server running on http://127.0.0.1:8765/stats")
    print("Open helix_dashboard.html in a browser to view it live.")
    app.run(host="127.0.0.1", port=8765, debug=False)
