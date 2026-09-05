"""Das Stands-Paket als Quelle der Falldarstellung (Fachkonzept Tagesbetrieb, 8.3).

Knoten: system/betrieb
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

import pytest

REPO = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO / "werkzeuge"))

import falldaten as fd  # noqa: E402
import fallbericht as fb  # noqa: E402


def _paket(tmp_path: Path, pb1: str = "gruen") -> Path:
    paket = tmp_path / "paket"
    paket.mkdir()
    stand = {
        "schema_version": 1, "stand": "2026-09-05", "gefuehrt_seit": "2026-01-01",
        "bestand": {"in_force": 2556, "je_produkt": {"klv": 1893, "bu": 663},
                    "uebernommen_in_force": 818, "policiert_beginn_folgt": 2},
        "neugeschaeft": {"seit_betriebsbeginn": 99, "woche": {"2026-09-01": 2}, "woche_summe": 2},
        "buchungen": {"gesamt": 1460, "je_ereignis": {"ZUG": 933, "PEX": 174}, "letzte": []},
        "abschluesse": [{"stichtag": "2026-09-01", "datei": "abschluss_2026-09-01.parquet",
                         "sha256": "9b" * 32, "bericht": "bestandsbericht_2026-09-01.html"}],
        "uebernahmen": [{"fall": "probe", "stichtag": "2026-01-01", "vertraege": 834,
                         "snapshot_sha256": "32" * 32}],
        "provenienz": {"manifest_sha256": "ed" * 32, "config_sha256": "d5" * 32,
                       "kern_version": "3.4.0", "pb1": pb1, "image_digest": "nicht erfasst",
                       "image_revision": "nicht erfasst", "image_tag": "nicht erfasst"},
        "dateien": {"index.html": "00" * 32},
    }
    (paket / "stand.json").write_text(json.dumps(stand), encoding="utf-8")
    return paket


def test_das_paket_wird_zum_abschnitt_der_darstellung(tmp_path):
    b = fd.betrieb(_paket(tmp_path))
    assert b["vorhanden"] and b["stand"] == "2026-09-05"
    assert b["bestand"]["in_force"] == 2556 and b["uebernahmen"][0]["vertraege"] == 834
    html = fb._betrieb({"betrieb": b})
    assert "Der lebende Bestand (Stand 2026-09-05)" in html
    assert "<b>2.556</b><span>Verträge in Kraft" in html.replace("2,556", "2.556")
    assert "abschluss_2026-09-01.parquet" in html and "Wache P-B1 gruen" in html
    assert "Übernahme <b>probe</b>" in html
    # Ohne Paket kein Abschnitt und keine Luecke:
    assert fd.betrieb(None) == {"vorhanden": False}
    assert fb._betrieb({"betrieb": {"vorhanden": False}}) == ""
    assert not any(l["gruppe"] == "betrieb" for l in fd.luecken({"betrieb": {"vorhanden": False}}))


def test_ein_roter_stand_wird_nicht_dargestellt(tmp_path):
    """Veroeffentlicht wird nichts, was nicht durch P-B1 ging."""
    with pytest.raises(fd.FalldatenFehler, match="nicht durch P-B1"):
        fd.betrieb(_paket(tmp_path, pb1="rot"))
    with pytest.raises(fd.FalldatenFehler, match="kein Stands-Paket"):
        fd.betrieb(tmp_path)


def test_die_kette_reicht_das_paket_durch(tmp_path, monkeypatch):
    import auftritt

    aufrufe = []
    monkeypatch.setattr(auftritt, "_schritt", lambda kommando, erlaubt=(0,): aufrufe.append(kommando) or 0)
    auftritt.main(["--fall", "f", "--name", "n", "--stands-paket", str(tmp_path / "paket"),
                   "--vorschau", ""])
    assert "--stands-paket" in aufrufe[0] and str(tmp_path / "paket") in aufrufe[0]
