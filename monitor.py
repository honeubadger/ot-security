from datetime import datetime
import random
import time

TEMP_MIN = 20
TEMP_MAX = 70

RPM_MIN = 800
RPM_MAX = 1800

CURRENT_MIN = 1
CURRENT_MAX = 5

print("OT/ICS SECURITY MONITOR")
print("-----------------------")

while True:

    temperature = random.randint(35, 80)
    rpm = random.randint(1000, 2200)
    current = round(random.uniform(2, 6), 1)

    timestamp = datetime.now().strftime("%H:%M:%S")

    print(f"\n[{timestamp}]")
    print(f"Temperature: {temperature} C")
    print(f"Motor RPM:   {rpm}")
    print(f"Current:     {current} A")

    alert = False

    if temperature > TEMP_MAX:
        print("ALERT: High temperature")
        alert = True

    if rpm > RPM_MAX:
        print("ALERT: Abnormal motor speed")
        alert = True

    if current > CURRENT_MAX:
        print("ALERT: Abnormal current")
        alert = True

    if not alert:
        print("STATUS: NORMAL")

    time.sleep(2)
