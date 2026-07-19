"""Create a bcrypt htpasswd file and launch Radicale."""

from __future__ import annotations

import os
from pathlib import Path

import bcrypt


def build_htpasswd(username: str, password: str) -> str:
    if not username or any(character in username for character in ":\r\n"):
        raise ValueError("invalid CalDAV username")
    if not password or any(character in password for character in "\r\n"):
        raise ValueError("invalid CalDAV password")
    hashed = bcrypt.hashpw(password.encode(), bcrypt.gensalt(rounds=12)).decode()
    return f"{username}:{hashed}\n"


def main() -> None:
    username = os.environ.get("CALDAV_USERNAME", "")
    password = os.environ.get("CALDAV_PASSWORD", "")
    destination = Path("/data/radicale/users")
    destination.parent.mkdir(parents=True, exist_ok=True)
    destination.write_text(build_htpasswd(username, password))
    destination.chmod(0o600)
    os.execvp("radicale", ["radicale", "--config", "/srv/saju-caldav/radicale/config"])


if __name__ == "__main__":
    main()
