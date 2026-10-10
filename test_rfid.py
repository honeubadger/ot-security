import spidev
import time

# ==========================================
# OT/ICS CYBERSECURITY PROJECT
# RFID RC522 HARDWARE TEST
# Raspberry Pi 5
# ==========================================

spi = spidev.SpiDev()

try:
    spi.open(0, 0)
    spi.max_speed_hz = 1000000
    spi.mode = 0

    print("================================")
    print("OT SECURITY - RFID HARDWARE TEST")
    print("================================")

    print("Checking RC522 communication...")

    # MFRC522 VersionReg address: 0x37
    register = 0x37

    # SPI register read command
    address = ((register << 1) & 0x7E) | 0x80

    response = spi.xfer2([address, 0x00])

    version = response[1]

    print(f"RC522 Version Register: 0x{version:02X}")

    if version in (0x91, 0x92):
        print("RFID reader detected successfully!")

    elif version in (0x00, 0xFF):
        print("RFID reader not responding.")
        print("Check wiring and 3.3V power.")

    else:
        print("Unexpected version value.")
        print("Check module compatibility and wiring.")

except Exception as error:
    print(f"RFID communication error: {error}")

finally:
    spi.close()

