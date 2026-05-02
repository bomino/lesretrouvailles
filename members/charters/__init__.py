"""Versioned charter content. Old versions remain in repo for audit."""

from pathlib import Path

CHARTER_DIR = Path(__file__).resolve().parent

CHARTER_CURRENT_VERSION = "1.0"

CHARTER_VERSIONS: dict[str, str] = {
    "1.0": "v1_0.md",
}


def get_charter_text(version: str) -> str:
    if version not in CHARTER_VERSIONS:
        raise KeyError(f"Unknown charter version: {version}")
    return (CHARTER_DIR / CHARTER_VERSIONS[version]).read_text(encoding="utf-8")
