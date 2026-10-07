"""Where the data lives: the project folder from source, the platform folder otherwise."""

import sys
from pathlib import Path

from toploader import paths


def test_source_checkout_keeps_data_in_the_project():
    assert paths.default_root() == paths.SOURCE_ROOT


def test_standalone_mac_build_uses_application_support(monkeypatch):
    monkeypatch.setattr(sys, "frozen", True, raising=False)
    monkeypatch.setattr(sys, "platform", "darwin")
    assert paths.default_root() == Path.home() / "Library" / "Application Support" / "Toploader"


def test_standalone_linux_build_uses_xdg_data_home(monkeypatch, tmp_path):
    monkeypatch.setattr(sys, "frozen", True, raising=False)
    monkeypatch.setattr(sys, "platform", "linux")
    monkeypatch.setenv("XDG_DATA_HOME", str(tmp_path))
    assert paths.default_root() == tmp_path / "toploader"
