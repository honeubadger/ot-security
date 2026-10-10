import serial
import time
from datetime import datetime

# ====================================
# OT/ICS INDUSTRIAL MONITOR
# ====================================

PORT = "/dev/ttyACM0"
BAUD_RATE = 9600

MAX_TEMP_F = 120.0

temperature_f = None
motor_status = "UNKNOWN"
motor_speed = 0

print("================================")
print("   OT/ICS INDUSTRIAL MONITOR")
print("================================")

arduino = serial.Serial(
    PORT,
    BAUD_RATE,
    timeout=2
)

time.sleep(3)

print("Arduino connected!")
print("Monitoring industrial system...\n")

try:
    while True:

        line = arduino.readline().decode(
            "utf-8",
            errors="replace"
        ).strip()

        if line.startswith("TEMP="):

            value = line.split("=", 1)[1]

            if value == "ERROR":
                temperature_f = None
            else:
                try:
                    temperature_c = float(value)
                    temperature_f = temperature_c * 1.8 + 32
                except ValueError:
                    temperature_f = None

        elif line.startswith("MOTOR="):

            motor_status = line.split("=", 1)[1]

        elif line.startswith("SPEED="):

            try:
                motor_speed = int(line.split("=", 1)[1])
            except ValueError:
                continue

            timestamp = datetime.now().strftime("%H:%M:%S")

            print("\n--------------------------------")
            print(f"Time: {timestamp}")

            if temperature_f is None:
                print("Temperature: SENSOR ERROR")
            else:
                print(f"Temperature: {temperature_f:.1f} °F")

            print(f"Motor: {motor_status}")
            print(f"Speed: {motor_speed}% PWM")

            if temperature_f is not None and temperature_f > MAX_TEMP_F:
                print("WARNING: HIGH TEMPERATURE!")
            else:
                print("STATUS: NORMAL")

except KeyboardInterrupt:
    print("\nMonitoring stopped.")

finally:
    arduino.close()
    print("Serial connection closed.")

