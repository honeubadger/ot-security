import serial
import time

# ==========================================
# OT/ICS CYBERSECURITY PROJECT
# MOTOR CONTROL TEST
# Raspberry Pi 5 + ELEGOO UNO R3
# ==========================================

# Serial communication settings
PORT = "/dev/ttyACM0"
BAUD_RATE = 9600

print("Connecting to Arduino...")

try:
    with serial.Serial(
        port=PORT,
        baudrate=BAUD_RATE,
        timeout=2
    ) as arduino:

        # Wait for Arduino to restart
        time.sleep(3)

        print("Arduino connected successfully!")

        # ==================================
        # TEST 1: TURN MOTOR ON
        # ==================================

        print("Turning motor ON...")

        arduino.write(b"MOTOR:ON\n")
        arduino.flush()

        time.sleep(5)

        # ==================================
        # TEST 2: SET MOTOR SPEED TO 70%
        # ==================================

        print("Setting motor speed to 70%...")

        arduino.write(b"SPEED:70\n")
        arduino.flush()

        time.sleep(5)

        # ==================================
        # TEST 3: SET MOTOR SPEED TO 100%
        # ==================================

        print("Setting motor speed to 100%...")

        arduino.write(b"SPEED:100\n")
        arduino.flush()

        time.sleep(5)

        # ==================================
        # TEST 4: TURN MOTOR OFF
        # ==================================

        print("Turning motor OFF...")

        arduino.write(b"MOTOR:OFF\n")
        arduino.flush()

        time.sleep(2)

        print("Motor control test completed!")

except serial.SerialException as error:
    print(f"Serial communication error: {error}")

except KeyboardInterrupt:
    print("\nTest interrupted by user.")

finally:
    print("Program finished.")
