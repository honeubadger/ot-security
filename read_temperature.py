import serial
import time
from datetime import datetime

# =====================================
# OT/ICS CYBERSECURITY
# TEMPERATURE MONITOR
# RASPBERRY PI 5
# =====================================

# SERIAL CONFIGURATION
PORT = "/dev/ttyACM0"
BAUD_RATE = 9600

# TEMPERATURE LIMIT
MAX_TEMPERATURE_F = 95.0

print("=================================")
print("   OT/ICS SECURITY MONITOR")
print("=================================")
print("Connecting to Arduino...")

# Connect to Arduino
try:
    arduino = serial.Serial(
        port=PORT,
        baudrate=BAUD_RATE,
        timeout=2
    )

except serial.SerialException as error:
    print(f"Connection error: {error}")
    raise SystemExit(1)

# Wait for Arduino to restart
time.sleep(3)

print("Arduino connected successfully!")
print("Waiting for temperature data...")
print("---------------------------------")


# =====================================
# CELSIUS TO FAHRENHEIT
# =====================================

def celsius_to_fahrenheit(celsius):
    return (celsius * 9 / 5) + 32


# =====================================
# TEMPERATURE MONITORING
# =====================================

try:
    while True:

        # Read data from Arduino
        line = arduino.readline().decode(
            "utf-8",
            errors="replace"
        ).strip()

        if not line:
            continue

        # Arduino sends TEMP=25.5
        if line.startswith("TEMP="):

            value = line.split("=", 1)[1]

            # Check sensor error
            if value == "ERROR":
                print("WARNING: Temperature sensor error!")
                continue

            try:
                # Temperature in Celsius
                temperature_c = float(value)

                # Convert to Fahrenheit
                temperature_f = celsius_to_fahrenheit(
                    temperature_c
                )

                # Timestamp
                timestamp = datetime.now().strftime(
                    "%H:%M:%S"
                )

                print(f"\n[{timestamp}]")

                print(
                    f"Temperature: "
                    f"{temperature_f:.1f} °F"
                )

                # Temperature warning
                if temperature_f > MAX_TEMPERATURE_F:

                    print(
                        "WARNING: HIGH TEMPERATURE!"
                    )

                else:

                    print("STATUS: NORMAL")

            except ValueError:
                print("Invalid temperature reading")

except KeyboardInterrupt:
    print("\nTemperature monitoring stopped.")

finally:
    arduino.close()
    print("Serial connection closed.")
