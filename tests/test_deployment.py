import configparser
import tomllib
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

    assert "USER 10001:10001" in dockerfile
    assert "apt-get" not in dockerfile
    assert "--require-hashes -r requirements.lock" in dockerfile
    assert "pip install --no-cache-dir ." not in dockerfile
    assert "COPY lunar_python ./lunar_python" in dockerfile
    assert "services:" in compose
    assert "web:" in compose
    assert "radicale:" in compose
    assert "APP_PASSWORD: ${APP_PASSWORD:?" in compose
    assert "CALDAV_PASSWORD: ${CALDAV_PASSWORD:?" in compose
    assert "correct-horse-battery-staple" not in compose


def test_runtime_lock_matches_exact_project_dependencies() -> None:
    """Keep the image's hash lock aligned with every exact runtime dependency."""

    project = tomllib.loads((ROOT / "pyproject.toml").read_text())
    runtime_versions: dict[str, str] = {}
    for line in (ROOT / "requirements.lock").read_text().splitlines():
        if not line or line[0].isspace() or line.startswith("#") or "==" not in line:
            continue
        package_name, version_with_suffix = line.split("==", 1)
        runtime_versions[package_name.casefold().replace("_", "-")] = version_with_suffix.split()[0]

    mismatches: list[str] = []
    for requirement in project["project"]["dependencies"]:
        package_name, separator, expected_version = requirement.partition("==")
        assert separator == "==", f"runtime dependency must be exactly pinned: {requirement}"
        normalized_name = package_name.casefold().replace("_", "-")
        actual_version = runtime_versions.get(normalized_name)
        if actual_version != expected_version:
            mismatches.append(f"{package_name}: expected {expected_version}, locked {actual_version}")

    assert not mismatches, "requirements.lock is stale: " + "; ".join(mismatches)


def test_location_refresh_preserves_manual_timezone_choice() -> None:
    script = (ROOT / "app" / "static" / "app.js").read_text()

    assert "const selected = select.value;" in script
    assert 'select.value || "seoul"' not in script


def test_korean_lunar_calendar_notice_is_complete() -> None:
    notice = (ROOT / "THIRD_PARTY_NOTICES.md").read_text()
    license_text = (
        ROOT / "licenses" / "korean-lunar-calendar-MIT.txt"
    ).read_text()

    assert "korean-lunar-calendar 0.4.0" in notice
    assert "https://github.com/usingsky/korean_lunar_calendar_py" in notice
    assert "https://pypi.org/project/korean-lunar-calendar/0.4.0/" in notice
    assert "be56f27bc0594fdbbdf7bbe00f504a9f929a31e311bd7d9bb93561b645afade7" in notice
    assert "c042e20de0bb702add6bec8d0f6da1ea8d3b170838e63846f70420cf341fe4e7" in notice
    assert "licenses/korean-lunar-calendar-MIT.txt" in notice
    assert "Copyright (c) 2018-2026 Jinil Lee" in license_text
    assert "Permission is hereby granted" in license_text
