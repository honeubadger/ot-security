import json
from pathlib import Path
from werkzeug.security import generate_password_hash

def create_user(username, password):
    USER_FILE = Path("users.json")

    user = {
        "username": username,
        "password_hash": generate_password_hash(password),
        "role": "admin"
    }

    with USER_FILE.open("r") as file:
        users = json.load(file)

    users.append(user)

    with USER_FILE.open("w") as file:
        json.dump(users, file, indent=4)

    USER_FILE.chmod(0o600)

    print("\nAdministrator account created!")