import asyncio
import os
import json
import time
import serial
import secrets
import hmac
import threading
import logging

from pathlib import Path
from datetime import datetime, timedelta
from collections import defaultdict
from functools import wraps

from dotenv import load_dotenv

from create_user import create_user
from mfrc522 import SimpleMFRC522

from flask import (
    Flask,
    request,
    redirect,
    url_for,
    session,
    jsonify,
    render_template_string
)

from werkzeug.security import check_password_hash


# ==========================================
# OT/ICS CYBERSECURITY MONITOR (RFID SIMPLE)
# ==========================================

BASE_DIR = Path(__file__).resolve().parent
load_dotenv(BASE_DIR / ".env")

SECRET_KEY = os.getenv("FLASK_SECRET_KEY")
if not SECRET_KEY or len(SECRET_KEY) < 32:
    raise RuntimeError("FLASK_SECRET_KEY is missing or too short")

app = Flask(__name__)
app.config.update(
    SECRET_KEY=SECRET_KEY,
    SESSION_COOKIE_HTTPONLY=True,
    SESSION_COOKIE_SAMESITE="Lax",
    SESSION_COOKIE_SECURE=False,
    PERMANENT_SESSION_LIFETIME=timedelta(minutes=30)
)

SERIAL_PORT = "/dev/ttyACM0"
BAUD_RATE = 9600

MAX_TEMP_F = 90.0
RESET_TEMP_F = 88.0

MIN_SPEED = 50
MAX_SPEED = 100

logging.basicConfig(
    filename=str(BASE_DIR / "security.log"),
    level=logging.INFO,
    format="%(asctime)s | %(levelname)s | %(message)s"
)

data = {
    "temperature": None,
    "motor": "UNKNOWN",
    "speed": 0,
    "connected": False,
    "last_update": None,
    "last_received": 0,
    "temperature_alert": False,
    "security_alert": False,
    "security_message": "No security alerts"
}

data_lock = threading.Lock()
serial_lock = threading.Lock()
alarm_lock = threading.Lock()

arduino_connection = None
alarm_running = False


# ==========================================
# ARDUINO SERIAL MONITOR
# ==========================================

def read_arduino():
    global arduino_connection

    while True:
        try:
            with serial.Serial(SERIAL_PORT, BAUD_RATE, timeout=1) as arduino:
                with serial_lock:
                    arduino_connection = arduino

                time.sleep(3)
                print("Arduino connected!")

                while True:
                    line = arduino.readline().decode("utf-8", errors="replace").strip()
                    if not line:
                        continue

                    with data_lock:
                        if line.startswith("TEMP="):
                            try:
                                temp_c = float(line.split("=")[1])
                                temp_f = temp_c * 1.8 + 32
                                data["temperature"] = round(temp_f, 1)
                                data["temperature_alert"] = temp_f > MAX_TEMP_F
                            except:
                                data["temperature"] = None

                        elif line.startswith("MOTOR="):
                            value = line.split("=")[1]
                            if value in ("ON", "OFF"):
                                data["motor"] = value

                        elif line.startswith("SPEED="):
                            try:
                                speed = int(line.split("=")[1])
                                if 0 <= speed <= 100:
                                    data["speed"] = speed
                                    data["last_received"] = time.time()
                                    data["last_update"] = datetime.now().strftime("%H:%M:%S")
                                    data["connected"] = True
                            except:
                                pass

        except Exception as e:
            print("Arduino connection error:", e)

        finally:
            with serial_lock:
                arduino_connection = None
            with data_lock:
                data["connected"] = False
                data["temperature"] = None
                data["motor"] = "UNKNOWN"
                data["speed"] = 0
                data["last_received"] = 0

        time.sleep(3)


# ==========================================
# SEND COMMAND TO ARDUINO
# ==========================================

def send_arduino_command(command):
    with serial_lock:
        if arduino_connection is None:
            return False
        try:
            arduino_connection.write((command + "\n").encode("utf-8"))
            arduino_connection.flush()
            logging.info("Arduino command sent: %s", command)
            return True
        except Exception as e:
            logging.error("Arduino communication error: %s", e)
            return False


# ==========================================
# SECURITY ALARM
# ==========================================

def alarm_worker():
    global alarm_running
    try:
        if send_arduino_command("ALARM:ON"):
            print("SECURITY ALARM ACTIVATED")
            time.sleep(5)
            send_arduino_command("ALARM:OFF")
            print("SECURITY ALARM DEACTIVATED")
    finally:
        with alarm_lock:
            alarm_running = False


@app.route("/api/activate_security_alarm/<message>", methods=["POST"])
def activate_security_alarm(message):
    global alarm_running

    with data_lock:
        data["security_alert"] = True
        data["security_message"] = message

    logging.warning(message)

    with alarm_lock:
        if alarm_running:
            return jsonify({"message": "Alarm already running"})
        alarm_running = True

    threading.Thread(target=alarm_worker, daemon=True).start()
    return jsonify({"message": "Alarm activated"})


# ==========================================
# CSRF
# ==========================================

def get_csrf_token():
    if "csrf_token" not in session:
        session["csrf_token"] = secrets.token_hex(32)
    return session["csrf_token"]


def validate_csrf_token():
    expected = session.get("csrf_token", "")
    received = request.headers.get("X-CSRF-Token") or request.form.get("csrf_token", "")
    return bool(expected) and hmac.compare_digest(expected, received)


# ==========================================
# AUTH DECORATOR (FIXED)
# ==========================================

def login_required(fn):
    @wraps(fn)
    def wrapper(*args, **kwargs):
        if not session.get("authenticated"):
            return redirect(url_for("login"))
        return fn(*args, **kwargs)
    return wrapper


# ==========================================
# RFID LOGIN SIMPLE
# ==========================================

VALID_UIDS = ["266520233454", "17877238968"]

@app.route("/api/read_rfid")
def api_read_rfid():
    reader = SimpleMFRC522()
    try:
        uid, text = reader.read()
        uid = str(uid)

        print("RFID UID:", uid)

        if uid in VALID_UIDS:
            session.clear()
            session["authenticated"] = True
            session["username"] = f"rfid_{uid}"
            session["role"] = "Administrator"
            get_csrf_token()
            return jsonify({"status": "ok"})
        else:
            activate_security_alarm("Unknown RFID badge")
            return jsonify({"status": "invalid"})

    except Exception as e:
        logging.error("RFID error: %s", e)
        return jsonify({"status": "error"})

    finally:
        try:
            reader.READER.Close_MFRC522()
        except:
            pass


# ==========================================
# PAGES
# ==========================================

with open("./webpages/login.html") as f:
    LOGIN_HTML = f.read()

with open("./webpages/dashboard.html") as f:
    DASHBOARD_HTML = f.read()

with open("./webpages/create_user.html") as f:
    CREATE_USER = f.read()


@app.route("/login", methods=["GET"])
def login():
    return render_template_string(LOGIN_HTML)


@app.route("/")
@login_required
def dashboard():
    return render_template_string(DASHBOARD_HTML, csrf_token=get_csrf_token())


@app.route("/api/status")
def status():
    if not session.get("authenticated"):
        return jsonify({"error": "Unauthorized"}), 401

    with data_lock:
        result = data.copy()

    if result["last_received"] > 0 and time.time() - result["last_received"] > 10:
        result["connected"] = False
        result["temperature"] = None
        result["motor"] = "UNKNOWN"
        result["speed"] = 0

    return jsonify(result)


# ==========================================
# MOTOR CONTROL
# ==========================================

@app.route("/api/motor/<action>", methods=["POST"])
def motor_control(action):
    if not session.get("authenticated"):
        return jsonify({"error": "Unauthorized"}), 401

    if not validate_csrf_token():
        return jsonify({"error": "Invalid security token"}), 403

    if action == "on":
        command = "MOTOR:ON"
    elif action == "off":
        command = "MOTOR:OFF"
    else:
        return jsonify({"error": "Invalid motor command"}), 400

    if send_arduino_command(command):
        return jsonify({"message": f"Command sent: {command}"})
    return jsonify({"error": "Arduino unavailable"}), 503


@app.route("/api/motor/speed", methods=["POST"])
def motor_speed_control():
    if not session.get("authenticated"):
        return jsonify({"error": "Unauthorized"}), 401

    if not validate_csrf_token():
        return jsonify({"error": "Invalid security token"}), 403

    payload = request.get_json(silent=True)
    if not isinstance(payload, dict):
        return jsonify({"error": "Invalid JSON"}), 400

    speed = payload.get("speed")
    if type(speed) is not int:
        return jsonify({"error": "Speed must be an integer"}), 400

    if speed < MIN_SPEED or speed > MAX_SPEED:
        return jsonify({"error": "Speed must be between 50 and 100"}), 400

    command = f"SPEED:{speed}"
    if send_arduino_command(command):
        return jsonify({"message": f"Speed command sent: {speed}%"})
    return jsonify({"error": "Arduino unavailable"}), 503


# ==========================================
# LOGOUT
# ==========================================

@app.route("/logout", methods=["POST"])
@login_required
def logout():
    if not validate_csrf_token():
        return jsonify({"error": "Invalid security token"}), 403

    session.clear()
    return redirect(url_for("login"))


# ==========================================
# START
# ==========================================

if __name__ == "__main__":
    #threading.Thread(target=read_arduino, daemon=True).start()

    print("===================================")
    print(" OT SECURITY DASHBOARD (RFID SIMPLE)")
    print("===================================")

    app.run(host="0.0.0.0", port=5050, debug=False, use_reloader=False)
