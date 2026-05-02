from members.charters import (
    CHARTER_CURRENT_VERSION,
    CHARTER_VERSIONS,
    get_charter_text,
)


def test_current_version_is_listed_in_registry():
    assert CHARTER_CURRENT_VERSION in CHARTER_VERSIONS


def test_get_charter_text_returns_markdown_for_known_version():
    text = get_charter_text("1.0")
    assert text.startswith("#")
    assert "CEG" in text


def test_get_charter_text_raises_for_unknown_version():
    import pytest

    with pytest.raises(KeyError):
        get_charter_text("99.9")
