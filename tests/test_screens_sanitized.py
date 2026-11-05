# Copyright 2026 Ghaith Abdessalem
# SPDX-License-Identifier: Apache-2.0
"""Guards against committing a screen capture that still holds live-system values."""
import json
import re
from pathlib import Path

import pytest

SCREENS = sorted((Path(__file__).resolve().parent.parent / "screens").glob("[0-9]*.json"))

EMAIL = re.compile(r"[\w.+-]+@[\w-]+\.[\w.-]+")
IPV4 = re.compile(r"\b(?:\d{1,3}\.){3}\d{1,3}\b")
# GuiStatusPane text showing "<system> (<session>) <client>", as on a live session.
STATUS_SYSTEM = re.compile(r"^(\w{3}) \(\d+\) (\d{3})$")


def _strings(node):
    if isinstance(node, dict):
        for value in node.values():
            yield from _strings(value)
    elif isinstance(node, list):
        for value in node:
            yield from _strings(value)
    elif isinstance(node, str):
        yield node


def test_screens_exist():
    assert SCREENS


@pytest.mark.parametrize("path", SCREENS, ids=lambda p: p.name)
def test_screen_uses_placeholder_identity(path):
    data = json.loads(path.read_text(encoding="utf-8"))
    assert data["system"] == "SBX"
    assert data["client"] == "000"
    assert data["user"] == "USER_STANDARD"


@pytest.mark.parametrize("path", SCREENS, ids=lambda p: p.name)
def test_screen_has_no_identifying_strings(path):
    data = json.loads(path.read_text(encoding="utf-8"))
    for value in _strings(data):
        assert not EMAIL.search(value), value
        assert not IPV4.search(value), value
        match = STATUS_SYSTEM.match(value)
        if match:
            assert match.groups() == ("SBX", "000"), value


@pytest.mark.parametrize("path", SCREENS, ids=lambda p: p.name)
def test_screen_text_is_plain_english(path):
    """Accented text means a localised capture slipped in; samples are ASCII English."""
    data = json.loads(path.read_text(encoding="utf-8"))
    for value in _strings(data):
        assert value.isascii(), value


def test_screens_match_generator():
    from tools.generate_screens import OUT_DIR, expected_files

    for name, text in expected_files().items():
        assert (OUT_DIR / name).read_text(encoding="utf-8") == text, name
