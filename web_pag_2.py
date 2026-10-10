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
# OT/ICS CYBERSECURITY DASHBOARD V6
# Raspberry Pi 5 + ELEGOO UNO R3
# ==========================================

BASE_DIR = Path(__file__).resolve().parent

load_dotenv(BASE_DIR / ".env")

SECRET_KEY = os.getenv("FLASK_SECRET_KEY")

if not SECRET_KEY or len(SECRET_KEY) < 32:
    raise RuntimeError(
        "FLASK_SECRET_KEY is missing or too short"
    )

app = Flask(__name__)

app.config.update(
    SECRET_KEY=SECRET_KEY,
    SESSION_COOKIE_HTTPONLY=True,
    SESSION_COOKIE_SAMESITE="Lax",
    SESSION_COOKIE_SECURE=False,
    PERMANENT_SESSION_LIFETIME=timedelta(minutes=30)
)

# HTTP configuration is for an isolated laboratory only.
# Use HTTPS before deployment on an untrusted network.


# ==========================================
# CONFIGURATION
# ==========================================

SERIAL_PORT = "/dev/ttyACM0"
BAUD_RATE = 9600

MAX_TEMP_F = 120.0

MIN_SPEED = 50
MAX_SPEED = 100

MAX_FAILED_ATTEMPTS = 3
FAILED_WINDOW = 300

USERS_FILE = BASE_DIR / "users.json"

logging.basicConfig(
    filename=str(BASE_DIR / "security.log"),
    level=logging.INFO,
    format="%(asctime)s | %(levelname)s | %(message)s"
)


# ==========================================
# LOAD ADMINISTRATOR
# ==========================================

with USERS_FILE.open("r") as file:
    USER = json.load(file)


# ==========================================
# SHARED DATA
# ==========================================

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
auth_lock = threading.Lock()
alarm_lock = threading.Lock()

arduino_connection = None

failed_attempts = defaultdict(list)
alarm_running = False


# ==========================================
# ARDUINO SERIAL MONITOR
# ==========================================

def read_arduino():

    global arduino_connection

    while True:

        try:

            with serial.Serial(
                SERIAL_PORT,
                BAUD_RATE,
                timeout=1
            ) as arduino:

                with serial_lock:
                    arduino_connection = arduino

                # Arduino may restart when serial opens
                time.sleep(3)

                print("Arduino connected!")

                while True:

                    line = arduino.readline().decode(
                        "utf-8",
                        errors="replace"
                    ).strip()

                    if not line:
                        continue

                    with data_lock:

                        if line.startswith("TEMP="):

                            value = line.split("=", 1)[1]

                            try:
                                temp_c = float(value)
                                temp_f = temp_c * 1.8 + 32

                                data["temperature"] = round(
                                    temp_f, 1
                                )

                                data["temperature_alert"] = (
                                    temp_f > MAX_TEMP_F
                                )

                            except ValueError:
                                data["temperature"] = None
                                data["temperature_alert"] = False

                        elif line.startswith("MOTOR="):

                            value = line.split("=", 1)[1]

                            if value in ("ON", "OFF"):
                                data["motor"] = value

                        elif line.startswith("SPEED="):

                            try:
                                speed = int(
                                    line.split("=", 1)[1]
                                )

                                if 0 <= speed <= 100:

                                    data["speed"] = speed

                                    data["last_received"] = time.time()

                                    data["last_update"] = (
                                        datetime.now().strftime(
                                            "%H:%M:%S"
                                        )
                                    )

                                    data["connected"] = True

                            except ValueError:
                                pass

        except (serial.SerialException, OSError) as error:

            print("Arduino connection error:", error)

        finally:

            with serial_lock:
                arduino_connection = None

            with data_lock:
                data["connected"] = False
                data["temperature"] = None
                data["motor"] = "UNKNOWN"
                data["speed"] = 0
                data["last_received"] = 0
                data["temperature_alert"] = False

        time.sleep(3)


# ==========================================
# SEND COMMAND TO ARDUINO
# ==========================================

def send_arduino_command(command):

    with serial_lock:

        if arduino_connection is None:
            return False

        try:

            arduino_connection.write(
                (command + "\n").encode("utf-8")
            )

            arduino_connection.flush()

            logging.info(
                "Arduino command sent: %s",
                command
            )

            return True

        except (serial.SerialException, OSError) as error:

            logging.error(
                "Arduino communication error: %s",
                error
            )

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


def activate_security_alarm(message):

    global alarm_running

    with data_lock:
        data["security_alert"] = True
        data["security_message"] = message

    logging.warning(message)

    with alarm_lock:

        if alarm_running:
            return

        alarm_running = True

    threading.Thread(
        target=alarm_worker,
        daemon=True
    ).start()


# ==========================================
# CSRF PROTECTION
# ==========================================

def get_csrf_token():

    if "csrf_token" not in session:
        session["csrf_token"] = secrets.token_hex(32)

    return session["csrf_token"]


def validate_csrf_token():

    expected = session.get("csrf_token", "")

    received = (
        request.headers.get("X-CSRF-Token")
        or request.form.get("csrf_token", "")
    )

    return bool(expected) and hmac.compare_digest(
        expected,
        received
    )


# ==========================================
# AUTHENTICATION
# ==========================================

def login_required(function):

    @wraps(function)
    def wrapper(*args, **kwargs):

        if not session.get("authenticated"):
            return redirect(url_for("login"))

        return function(*args, **kwargs)

    return wrapper


def check_login(username, password):

    if username != USER["username"]:
        return False

    return check_password_hash(
        USER["password_hash"],
        password
    )


# ==========================================
# LOGIN PAGE
# ==========================================

LOGIN_HTML = """
<!DOCTYPE html>
<html lang="en">

<head>
<meta charset="UTF-8">
<meta name="viewport"
content="width=device-width, initial-scale=1">

<title>OT Security Login</title>

<style>

body {
    background: #0f172a;
    color: white;
    font-family: Arial, sans-serif;
    display: flex;
    justify-content: center;
    align-items: center;
    min-height: 90vh;
}

.login {
    background: #1e293b;
    padding: 35px;
    border-radius: 15px;
    width: 320px;
    max-width: 90%;
}

h2 {
    color: #38bdf8;
}

input {
    width: 100%;
    padding: 12px;
    margin: 10px 0;
    box-sizing: border-box;
}

button {
    width: 100%;
    padding: 12px;
    background: #0284c7;
    color: white;
    border: none;
    cursor: pointer;
}

.error {
    color: #f87171;
}

</style>
</head>

<body>

<div class="login">

<h2>OT SECURITY LOGIN</h2>

<form method="POST">

<input
    name="username"
    placeholder="Username"
    required
    autocomplete="username">

<input
    name="password"
    type="password"
    placeholder="Password"
    required
    autocomplete="current-password">

<button type="submit">LOGIN</button>

</form>

<p class="error">{{ error }}</p>

</div>

</body>
</html>
"""


# ==========================================
# DASHBOARD PAGE
# ==========================================

DASHBOARD_HTML = """
<!DOCTYPE html>
<html lang="en">

<head>

<meta charset="UTF-8">

<meta name="viewport"
content="width=device-width, initial-scale=1">

<title>OT/ICS Cybersecurity Monitor</title>

<style>

body {
    background: #0f172a;
    color: white;
    font-family: Arial, sans-serif;
    padding: 25px;
}

.container {
    max-width: 1100px;
    margin: auto;
}

h1 {
    color: #38bdf8;
}

.subtitle {
    color: #94a3b8;
}

.cards {
    display: grid;
    grid-template-columns:
        repeat(auto-fit, minmax(180px, 1fr));
    gap: 15px;
    margin-top: 25px;
}

.card {
    background: #1e293b;
    padding: 25px;
    border-radius: 12px;
    text-align: center;
}

.label {
    color: #94a3b8;
    font-size: 14px;
}

.value {
    font-size: 30px;
    font-weight: bold;
    margin-top: 15px;
}

.green {
    color: #4ade80;
}

.red {
    color: #f87171;
}

.blue {
    color: #38bdf8;
}

.panel {
    background: #1e293b;
    padding: 25px;
    border-radius: 12px;
    margin-top: 25px;
}

button {
    padding: 12px 20px;
    border: none;
    border-radius: 8px;
    cursor: pointer;
    margin: 5px;
    font-weight: bold;
}

.start {
    background: #22c55e;
    color: #052e16;
}

.stop {
    background: #ef4444;
    color: white;
}

.apply {
    background: #38bdf8;
    color: #082f49;
}

.logout {
    background: #475569;
    color: white;
}

input[type="range"] {
    width: 100%;
    max-width: 400px;
}

.message {
    margin-top: 15px;
    color: #facc15;
}

</style>

</head>

<body>

<div class="container">

<h1>OT/ICS CYBERSECURITY MONITOR</h1>


<form method="POST" action="/logout">
<input
    type="hidden"
    name="csrf_token"
    value="{{ csrf_token }}">

<button class="logout" type="submit">
LOGOUT
</button>
</form>

<div class="cards">

<div class="card">
    <div class="label">TEMPERATURE</div>
    <div class="value blue" id="temperature">--</div>
</div>

<div class="card">
    <div class="label">MOTOR STATUS</div>
    <div class="value" id="motor">--</div>
</div>

<div class="card">
    <div class="label">MOTOR SPEED</div>
    <div class="value blue" id="speed">--</div>
</div>

<div class="card">
    <div class="label">ARDUINO CONNECTION</div>
    <div class="value" id="connection">--</div>
</div>

</div>
<div class="cards">

    <div class="panel">

    <h2>MOTOR CONTROL</h2>

    <p>Authorized users only</p>

    <button class="start" onclick="sendMotorCommand('on')">
    ON
    </button>

    <button class="stop" onclick="sendMotorCommand('off')">
    OFF
    </button>

    <h3>Motor Speed</h3>

    <input
        type="range"
        id="speedSlider"
        min="50"
        max="100"
        step="10"
        value="70"
        oninput="updateSpeedLabel()">

    <p>
    Selected Speed:
    <strong id="selectedSpeed">70%</strong>
    </p>

    <button class="apply" onclick="applySpeed()">
    APPLY SPEED
    </button>

    <p class="message" id="commandMessage"></p>

    </div>

    <div class="panel">

    <h2>SECURITY STATUS</h2>

    <div class="value green" id="security">
    SYSTEM NORMAL
    </div>

    </div>

    <p class="subtitle">
    Last update:
    <span id="updated">--</span>
    </p>

</div>

<script>

const csrfToken = {{ csrf_token | tojson }};


function updateSpeedLabel() {

    const speed =
        document.getElementById("speedSlider").value;

    document.getElementById(
        "selectedSpeed"
    ).textContent = speed + "%";
}


async function sendMotorCommand(action) {

    const message =
        document.getElementById("commandMessage");

    try {

        const response = await fetch(
            "/api/motor/" + action,
            {
                method: "POST",

                headers: {
                    "X-CSRF-Token": csrfToken
                }
            }
        );

        const result = await response.json();

        message.textContent =
            result.message || result.error;

    } catch (error) {

        message.textContent =
            "Motor command failed";
    }
}


async function applySpeed() {

    const speed = Number(
        document.getElementById("speedSlider").value
    );

    const message =
        document.getElementById("commandMessage");

    try {

        const response = await fetch(
            "/api/motor/speed",
            {
                method: "POST",

                headers: {
                    "Content-Type": "application/json",
                    "X-CSRF-Token": csrfToken
                },

                body: JSON.stringify({
                    speed: speed
                })
            }
        );

        const result = await response.json();

        message.textContent =
            result.message || result.error;

    } catch (error) {

        message.textContent =
            "Speed command failed";
    }
}


async function updateDashboard() {

    try {

        const response = await fetch("/api/status");

        if (!response.ok) {
            throw new Error("Connection error");
        }

        const data = await response.json();

        document.getElementById(
            "temperature"
        ).textContent =
            data.temperature === null
            ? "--"
            : data.temperature + " °F";

        document.getElementById(
            "motor"
        ).textContent = data.motor;

        document.getElementById(
            "speed"
        ).textContent = data.speed + "% PWM";

        const connection =
            document.getElementById("connection");

        connection.textContent =
            data.connected ? "ONLINE" : "OFFLINE";

        connection.className =
            data.connected
            ? "value green"
            : "value red";

        const security =
            document.getElementById("security");

        if (data.security_alert) {

            security.textContent =
                data.security_message;

            security.className = "value red";

        } else if (data.temperature_alert) {

            security.textContent =
                "HIGH TEMPERATURE";

            security.className = "value red";

        } else {

            security.textContent =
                "SYSTEM NORMAL";

            security.className = "value green";
        }

        document.getElementById(
            "updated"
        ).textContent =
            data.last_update || "--";

    } catch (error) {

        document.getElementById(
            "connection"
        ).textContent = "OFFLINE";

    }
}

updateDashboard();

setInterval(updateDashboard, 2000);

</script>

</body>
</html>
"""


# ==========================================
# ROUTES
# ==========================================

@app.route("/login", methods=["GET", "POST"])
def login():

    if request.method == "POST":

        username = request.form.get(
            "username", ""
        )

        password = request.form.get(
            "password", ""
        )

        ip = request.remote_addr or "unknown"
        now = time.time()

        with auth_lock:

            attempts = [
                t for t in failed_attempts[ip]
                if now - t < FAILED_WINDOW
            ]

            failed_attempts[ip] = attempts

            if len(attempts) >= MAX_FAILED_ATTEMPTS:

                return render_template_string(
                    LOGIN_HTML,
                    error="Too many attempts. Try later."
                ), 429

        if check_login(username, password):

            session.clear()

            session["authenticated"] = True
            session["username"] = username
            session.permanent = True

            get_csrf_token()

            with auth_lock:
                failed_attempts.pop(ip, None)

            logging.info(
                "Successful login from %s",
                ip
            )

            return redirect(url_for("dashboard"))

        with auth_lock:

            failed_attempts[ip].append(now)

            count = len(failed_attempts[ip])

        logging.warning(
            "Failed login from %s",
            ip
        )

        if count == MAX_FAILED_ATTEMPTS:

            activate_security_alarm(
                f"Unauthorized login attempts from {ip}"
            )

        return render_template_string(
            LOGIN_HTML,
            error="Invalid username or password"
        ), 401

    return render_template_string(
        LOGIN_HTML,
        error=""
    )


@app.route("/")
@login_required
def dashboard():

    return render_template_string(
        DASHBOARD_HTML,
        csrf_token=get_csrf_token()
    )


@app.route("/api/status")
def status():

    if not session.get("authenticated"):

        return jsonify({
            "error": "Unauthorized"
        }), 401

    with data_lock:
        result = data.copy()

    if (
        result["last_received"] > 0
        and time.time() - result["last_received"] > 10
    ):

        result["connected"] = False
        result["temperature"] = None
        result["motor"] = "UNKNOWN"
        result["speed"] = 0

    return jsonify(result)


# ==========================================
# MOTOR ON / OFF
# ==========================================

@app.route("/api/motor/<action>", methods=["POST"])
def motor_control(action):

    if not session.get("authenticated"):

        logging.warning(
            "Unauthorized motor control attempt from %s",
            request.remote_addr
        )

        return jsonify({
            "error": "Unauthorized"
        }), 401

    if not validate_csrf_token():

        logging.warning(
            "Invalid CSRF token from %s",
            request.remote_addr
        )

        return jsonify({
            "error": "Invalid security token"
        }), 403

    if action == "on":
        command = "MOTOR:ON"

    elif action == "off":
        command = "MOTOR:OFF"

    else:
        return jsonify({
            "error": "Invalid motor command"
        }), 400

    if send_arduino_command(command):

        logging.info(
            "Motor command %s from %s",
            command,
            request.remote_addr
        )

        return jsonify({
            "message": f"Command sent: {command}"
        })

    return jsonify({
        "error": "Arduino unavailable"
    }), 503


# ==========================================
# MOTOR SPEED CONTROL
# ==========================================

@app.route("/api/motor/speed", methods=["POST"])
def motor_speed_control():

    if not session.get("authenticated"):

        logging.warning(
            "Unauthorized speed change attempt from %s",
            request.remote_addr
        )

        return jsonify({
            "error": "Unauthorized"
        }), 401

    if not validate_csrf_token():

        logging.warning(
            "Invalid CSRF token from %s",
            request.remote_addr
        )

        return jsonify({
            "error": "Invalid security token"
        }), 403

    payload = request.get_json(silent=True)

    if not isinstance(payload, dict):
        return jsonify({
            "error": "Invalid JSON"
        }), 400

    speed = payload.get("speed")

    if type(speed) is not int:
        return jsonify({
            "error": "Speed must be an integer"
        }), 400

    if speed < MIN_SPEED or speed > MAX_SPEED:
        return jsonify({
            "error": "Speed must be between 50 and 100"
        }), 400

    command = f"SPEED:{speed}"

    if send_arduino_command(command):

        logging.info(
            "Motor speed set to %s by %s",
            speed,
            request.remote_addr
        )

        return jsonify({
            "message": f"Speed command sent: {speed}%"
        })

    return jsonify({
        "error": "Arduino unavailable"
    }), 503


# ==========================================
# LOGOUT
# ==========================================

@app.route("/logout", methods=["POST"])
@login_required
def logout():

    if not validate_csrf_token():

        return jsonify({
            "error": "Invalid security token"
        }), 403

    session.clear()

    return redirect(url_for("login"))


# ==========================================
# START
# ==========================================

if __name__ == "__main__":

    threading.Thread(
        target=read_arduino,
        daemon=True
    ).start()

    print("===================================")
    print(" OT SECURITY DASHBOARD V6")
    print("===================================")

    app.run(
        host="0.0.0.0",
        port=5050,
        debug=False,
        use_reloader=False
    )
