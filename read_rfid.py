from mfrc522 import SimpleMFRC522

# ==========================================
# OT/ICS CYBERSECURITY PROJECT
# RFID CARD READER TEST
# Raspberry Pi 5
# ==========================================

reader = None

try:
    print("================================")
    print("OT SECURITY - RFID READER")
    print("================================")

    reader = SimpleMFRC522()

    print("Waiting for RFID card...")
    print("Press Ctrl+C to stop.")

    while True:
        card_id, text = reader.read()

        print("\nCARD DETECTED!")
        print(f"Card UID: {card_id}")
        print(f"Card Data: {text.strip()}")
        print("--------------------------------")
        print("Waiting for next card...")

except KeyboardInterrupt:
    print("\nRFID monitoring stopped.")

except Exception as error:
    print(f"RFID error: {error}")

finally:
    if reader is not None:
        try:
            reader.READER.Close_MFRC522()
        except (AttributeError, RuntimeError):
            pass
