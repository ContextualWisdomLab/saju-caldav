import configparser
from pathlib import Path

import bcrypt
import pytest

from scripts.run_radicale import build_htpasswd

ROOT = Path(__file__).parents[1]


def test_radicale_htpasswd_is_bcrypt_and_rejects_delimiters() -> None:
    line = build_htpasswd("caluser", "long-random-password")

    username, hashed = line.rstrip().split(":", 1)
    assert username == "caluser"
    assert bcrypt.checkpw(b"long-random-password", hashed.encode())
    with pytest.raises(ValueError, match="invalid CalDAV username"):
        build_htpasswd("bad:user", "password")


def test_radicale_configuration_is_owner_only() -> None:
    parser = configparser.ConfigParser()
    parser.read(ROOT / "radicale" / "config")

    assert parser["server"]["hosts"] == "0.0.0.0:5232"
    assert parser["auth"]["type"] == "htpasswd"
    assert parser["auth"]["htpasswd_encryption"] == "bcrypt"
    assert parser["rights"]["type"] == "owner_only"


def test_container_runs_unprivileged_and_compose_has_no_literal_secrets() -> None:
    dockerfile = (ROOT / "Dockerfile").read_text()
    compose = (ROOT / "compose.yaml").read_text()

    assert "USER saju" in dockerfile
    assert "services:" in compose
    assert "web:" in compose
    assert "radicale:" in compose
    assert "APP_PASSWORD: ${APP_PASSWORD:?" in compose
    assert "CALDAV_PASSWORD: ${CALDAV_PASSWORD:?" in compose
    assert "correct-horse-battery-staple" not in compose
