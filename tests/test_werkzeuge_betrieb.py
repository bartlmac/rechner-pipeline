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


import datetime as dt

from rechner_pipeline.betrieb import seite as st
from rechner_pipeline.betrieb.tageslauf import EXIT_OK, tageslauf
from tests.test_betrieb_seite import _ablage


@pytest.fixture(scope="module")
def paket(tmp_path_factory) -> Path:
    """Ein ECHTES Stands-Paket aus einem gefuehrten Stand (Review T22-05):
    Vorher schrieb der Test ein komplett erfundenes stand.json ohne
    Belegdateien und erwartete Veroeffentlichung — genau die Luecke."""
    ablage = _ablage(tmp_path_factory.mktemp("plv"))
    assert tageslauf(ablage, dt.date(2026, 2, 3))[0] == EXIT_OK
    return st.stands_paket(ablage, tmp_path_factory.mktemp("paket") / "paket")


def _erfunden(tmp_path: Path, pb1: str = "gruen") -> Path:
    """Das erfundene Paket von frueher — jetzt der Negativfall."""
    paket = tmp_path / "erfunden"
    paket.mkdir()
    stand = {
        "schema_version": 2, "stand": "2026-09-05", "gefuehrt_seit": "2026-01-01",
        "bestand": {"in_force": 2556, "je_produkt": {"klv": 1893, "bu": 663},
                    "uebernommen_in_force": 818, "policiert_beginn_folgt": 2},
        "neugeschaeft": {"seit_betriebsbeginn": 99, "woche": {}, "woche_summe": 0},
        "buchungen": {"gesamt": 1460, "je_ereignis": {}, "letzte": []},
        "abschluesse": [], "uebernahmen": [],
        "provenienz": {"manifest_sha256": "ed" * 32, "config_sha256": "d5" * 32,
                       "kern_version": "3.4.0", "pb1": pb1, "image_digest": "nicht erfasst",
                       "image_revision": "nicht erfasst", "image_tag": "nicht erfasst"},
        "dateien": {"index.html": "00" * 32, "protokoll.jsonl": "11" * 32,
                    "laufmanifest.json": "22" * 32},
    }
    (paket / "stand.json").write_text(json.dumps(stand), encoding="utf-8")
    return paket


def test_das_paket_wird_zum_abschnitt_der_darstellung(paket):
    b = fd.betrieb(paket)
    assert b["vorhanden"] and b["stand"] == "2026-02-03"
    assert b["bestand"]["in_force"] > 0 and b["provenienz"]["pb1"] == "gruen"
    assert set(b["dateien"]) >= {"index.html", "protokoll.jsonl", "laufmanifest.json"}
    html = fb._betrieb({"betrieb": b})
    assert "Der lebende Bestand (Stand 2026-02-03)" in html
    assert "Wache P-B1 gruen" in html
    # Die Luecken des Stands wandern in die Darstellung (T22-05).
    assert any(l["was"] == "Image-Digest des Laufs" for l in b["luecken"])
    assert any(l["gruppe"] == "betrieb" and "Image-Digest" in l["was"]
               for l in fd.luecken({"betrieb": b}))
    # Ohne Paket kein Abschnitt und keine Luecke:
    assert fd.betrieb(None) == {"vorhanden": False}
    assert fb._betrieb({"betrieb": {"vorhanden": False}}) == ""
    assert not any(l["gruppe"] == "betrieb" for l in fd.luecken({"betrieb": {"vorhanden": False}}))


def test_ein_erfundenes_paket_wird_nicht_veroeffentlicht(tmp_path):
    """Nachweis des Reviews: stand.json ohne Belegdateien mit pb1 = "gruen"
    wurde veroeffentlicht. Mutationsprobe: die Existenzpruefung der
    Belegdateien in _pruefe_stands_paket entfernen -> rot (die Hash-Pruefung
    faengt test_ein_veraendertes_protokoll_im_paket_faellt_auf)."""
    with pytest.raises(fd.FalldatenFehler, match="Belegdatei"):
        fd.betrieb(_erfunden(tmp_path))
    with pytest.raises(fd.FalldatenFehler, match="kein Stands-Paket"):
        fd.betrieb(tmp_path)


def test_ein_roter_stand_wird_nicht_dargestellt(paket, tmp_path):
    """Veroeffentlicht wird nichts, was nicht durch P-B1 ging — auch wenn
    nur stand.json das behauptet und das Protokoll etwas anderes sagt."""
    import shutil

    kopie = tmp_path / "rot"
    shutil.copytree(paket, kopie)
    stand = json.loads((kopie / "stand.json").read_text(encoding="utf-8"))
    stand["provenienz"]["pb1"] = "rot"
    (kopie / "stand.json").write_text(json.dumps(stand), encoding="utf-8")
    with pytest.raises(fd.FalldatenFehler, match="nicht durch P-B1"):
        fd.betrieb(kopie)


def test_ein_veraendertes_protokoll_im_paket_faellt_auf(paket, tmp_path):
    """Nachweis des Reviews: mittlere Zeile entfernt bzw. Betrag geaendert,
    der letzte Tag galt weiter. Hier: Zeile veraendert -> Belegdatei-Hash;
    Zeile veraendert UND Hash in stand.json nachgezogen -> Protokollkette."""
    import hashlib
    import shutil

    kopie = tmp_path / "manipuliert"
    shutil.copytree(paket, kopie)
    protokoll = kopie / "protokoll.jsonl"
    zeilen = protokoll.read_text(encoding="utf-8").splitlines()
    zeile = json.loads(zeilen[-1])
    zeile["bestand"]["in_force"] = 999999
    zeilen[-1] = json.dumps(zeile, ensure_ascii=False, sort_keys=True)
    protokoll.write_text("\n".join(zeilen) + "\n", encoding="utf-8")
    with pytest.raises(fd.FalldatenFehler, match="Belegdatei 'protokoll.jsonl'"):
        fd.betrieb(kopie)
    # Wer auch den Hash in stand.json nachzieht, scheitert an der Kette,
    # sobald er eine mittlere Zeile antastet:
    stand = json.loads((kopie / "stand.json").read_text(encoding="utf-8"))
    if len(zeilen) >= 2:
        del zeilen[0]
        protokoll.write_text("\n".join(zeilen) + "\n", encoding="utf-8")
        stand["dateien"]["protokoll.jsonl"] = hashlib.sha256(protokoll.read_bytes()).hexdigest()
        (kopie / "stand.json").write_text(json.dumps(stand), encoding="utf-8")
        with pytest.raises(fd.FalldatenFehler, match="Protokollkette|passen nicht"):
            fd.betrieb(kopie)


def test_die_kette_reicht_das_paket_durch(tmp_path, monkeypatch):
    import auftritt

    aufrufe = []
    monkeypatch.setattr(auftritt, "_schritt", lambda kommando, erlaubt=(0,): aufrufe.append(kommando) or 0)
    auftritt.main(["--fall", "f", "--name", "n", "--stands-paket", str(tmp_path / "paket"),
                   "--vorschau", ""])
    assert "--stands-paket" in aufrufe[0] and str(tmp_path / "paket") in aufrufe[0]
