import serial
import time

arduino = serial.Serial(
    "/dev/ttyACM0",
    9600,
    timeout=2
)

# Esperar a que Arduino reinicie
time.sleep(3)

print("Activando alarma...")

arduino.write(b"ALARM:ON\n")

time.sleep(5)

print("Desactivando alarma...")

arduino.write(b"ALARM:OFF\n")

time.sleep(2)

arduino.close()

print("Prueba terminada.")
