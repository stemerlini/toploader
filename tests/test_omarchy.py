"""The Omarchy integration: `toploader summary` and the bar widget plugin."""

import json
import re
from pathlib import Path

import pytest

from toploader import __main__ as cli

ROOT = Path(__file__).resolve().parents[1]


@pytest.mark.parametrize("value, text", [
    (0, "€0"), (842.4, "€842"), (2727.47, "€2.7k"), (12_345, "€12k"),
])
def test_compact_money(value, text):
    assert cli.compact_money(value, "EUR") == text


def test_summary_of_an_empty_collection(tmp_path, monkeypatch):
    monkeypatch.setattr("toploader.db.DATA_DIR", tmp_path)
    monkeypatch.setattr("toploader.config.CONFIG_FILE", tmp_path / "config.json")
    monkeypatch.setattr("toploader.games.tcgcsv.CACHE_DIR", tmp_path)
    data = cli.summary()
    assert data == {"copies": 0, "unique": 0, "value": 0.0, "currency": "EUR",
                    "text": "€0.00", "short": "€0"}


def test_summary_command_prints_json(monkeypatch, capsys):
    monkeypatch.setattr(cli, "summary", lambda: {"copies": 1})
    cli.main(["summary"])
    assert json.loads(capsys.readouterr().out) == {"copies": 1}


def test_plugin_manifest():
    manifest = json.loads((ROOT / "omarchy" / "manifest.json").read_text())
    assert manifest["id"] == "smerlini.toploader"
    assert manifest["kinds"] == ["bar-widget"]
    assert (ROOT / "omarchy" / manifest["entryPoints"]["barWidget"]).exists()
    defaults = manifest["barWidget"]["defaults"]
    assert {field["key"] for field in manifest["barWidget"]["schema"]} == set(defaults)


def test_bar_widget_uses_the_poke_ball_glyph():
    # U+F041D is nf-md-pokeball; U+F0432 right next to it is a QR code.
    qml = (ROOT / "omarchy" / "BarWidget.qml").read_text()
    high, low = re.search(r'pokeball: "\\u([0-9A-F]{4})\\u([0-9A-F]{4})"', qml).groups()
    code_point = 0x10000 + ((int(high, 16) - 0xD800) << 10) + (int(low, 16) - 0xDC00)
    assert code_point == 0xF041D
