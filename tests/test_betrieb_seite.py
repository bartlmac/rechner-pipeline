"""Bestand heute und Stands-Paket: aus Protokoll und Journal, nach der Wache.

Fachkonzept docs/simulation/tagesbetrieb.md, Abschnitt 8.3, Block B8. Die
interne Sicht rendert der Tageslauf nach jedem gruenen Lauf; das
Stands-Paket ist die Quelle der Vorzeigeseite — nichts davon rechnet,
alles ist gebucht und gestempelt.

Knoten: system/betrieb
"""

from __future__ import annotations

import datetime as dt
import json
import re
import shutil
from pathlib import Path

import pytest

from rechner_pipeline.betrieb import seite as st
from rechner_pipeline.betrieb.tageslauf import EXIT_OK, Ablage, lies_protokoll, tageslauf

REPO_ROOT = Path(__file__).resolve().parents[1]
PLV = REPO_ROOT / "configs" / "bestand_gesamt.toml"


def _ablage(wurzel: Path) -> Ablage:
    ablage = Ablage(wurzel)
    ablage.configs.mkdir(parents=True, exist_ok=True)
    text = PLV.read_text(encoding="utf-8")
    ablage.config_pfad.write_text(
        re.sub(r"^sample_size = [1-9]\d*$", "sample_size = 8", text, flags=re.M),
        encoding="utf-8")
    return ablage


@pytest.fixture(scope="module")
def gefuehrt(tmp_path_factory):
    ablage = _ablage(tmp_path_factory.mktemp("plv"))
    assert tageslauf(ablage, dt.date(2026, 2, 3))[0] == EXIT_OK
    return ablage


def test_der_tageslauf_rendert_die_seite_nach_dem_nachweis(gefuehrt):
    zeile = lies_protokoll(gefuehrt.protokoll_pfad)[-1]
    assert zeile["seite"] == "index.html"
    html = (gefuehrt.wurzel / "seite" / "index.html").read_text("utf-8")
    assert "Bestand heute" in html and "Stand 2026-02-03" in html
    assert f"<b>{zeile['bestand']['in_force']}</b><span>Vertraege in Kraft" in html
    assert "abschluss_2026-02-01.parquet" in html and "bestandsbericht_2026-02-01.html" in html
    assert "Wache P-B1: gruen" in html
    assert "nicht erfasst" in html                      # Image ausserhalb des Containers
    # Dieselbe Ehrlichkeit wie die Fall-Seite: Banderole, Stand und Manifest
    # im Kopf, Luecken sichtbar.
    assert "Dies ist eine Vorfuehrung, kein echter Bestand." in html
    assert f"Manifest <code>{zeile['manifest_sha256'][:16]}</code>" in html
    assert "Was diese Seite NICHT zeigt" in html and "Image-Digest des Laufs" in html


def test_modell_und_seite_sind_deterministisch(gefuehrt):
    a, b = st.stand_modell(gefuehrt), st.stand_modell(gefuehrt)
    assert a == b
    assert st.rendere_html(a) == st.rendere_html(b)
    assert a["stand"] == "2026-02-03" and a["gefuehrt_seit"] == "2026-01-01"
    assert a["provenienz"]["pb1"] == "gruen" and a["provenienz"]["manifest_sha256"]
    assert a["buchungen"]["gesamt"] > 0 and a["neugeschaeft"]["seit_betriebsbeginn"] > 0
    assert [x["stichtag"] for x in a["abschluesse"]] == ["2026-01-01", "2026-02-01"]
    assert a["abschluesse"][-1]["bericht"] == "bestandsbericht_2026-02-01.html"


def test_stands_paket_traegt_stempel_und_berichte(gefuehrt, tmp_path):
    paket = st.stands_paket(gefuehrt, tmp_path / "paket")
    stand = json.loads((paket / "stand.json").read_text("utf-8"))
    assert stand["schema_version"] == 1 and stand["stand"] == "2026-02-03"
    assert set(stand["dateien"]) == {"index.html", "bestandsbericht_2026-02-01.html"}
    for name, summe in stand["dateien"].items():
        assert (paket / name).is_file() and len(summe) == 64
    # Ein Paket wird ersetzt, nie angesammelt:
    (paket / "fremd.txt").write_text("x", encoding="utf-8")
    st.stands_paket(gefuehrt, paket)
    assert not (paket / "fremd.txt").exists()
    assert st.main(["--stand", str(gefuehrt.wurzel), "--paket", str(tmp_path / "p2")]) == 0
    assert (tmp_path / "p2" / "stand.json").is_file()


def test_luecken_werden_benannt():
    modell = {"provenienz": {"image_digest": "nicht erfasst"},
              "uebernahmen": [{"fall": "x", "snapshot_sha256": None,
                               "zeichnung": {"schluesselklasse": "nicht ausgewiesen"}}],
              "abschluesse": []}
    was = [l["was"] for l in st.luecken(modell)]
    assert was == ["Image-Digest des Laufs", "A-M4-Snapshot der Uebernahme x",
                   "Schluesselklasse der A-M4-Zeichnung (x)", "Monatsabschluss"]
    voll = {"provenienz": {"image_digest": "sha256:abc"},
            "uebernahmen": [{"fall": "x", "snapshot_sha256": "ab" * 32,
                             "zeichnung": {"schluesselklasse": "simulation"}}],
            "abschluesse": [{"stichtag": "2026-02-01"}]}
    assert st.luecken(voll) == []


def test_ohne_uebernommenen_stand_gibt_es_keine_seite(tmp_path):
    ablage = _ablage(tmp_path / "leer")
    with pytest.raises(st.SeiteError, match="kein uebernommener Lauf"):
        st.stand_modell(ablage)
    assert st.main(["--stand", str(ablage.wurzel)]) == 2
    # Stand und Protokoll muessen zusammenpassen — sonst spricht die Seite
    # von einem anderen Stand als dem Nachweis.
    kopie = Ablage(tmp_path / "kopie")
    shutil.copytree(_ablage(tmp_path / "quelle").wurzel, kopie.wurzel)


def test_uebernahme_traegt_rolle_und_schluesselklasse_der_zeichnung(tmp_path):
    """Wie die Fall-Seite: Rolle und Entscheider aus dem Snapshot, die
    Schluesselklasse eines Altsnapshots (Schema 6) als "nicht ausgewiesen"."""
    import sys

    sys.path.insert(0, str(REPO_ROOT / "tests"))
    import test_betrieb_uebernahme as tu
    from rechner_pipeline.betrieb import uebernahme as ueb

    fall = tu._fall(tmp_path)
    snapshot = "ab" * 32
    (fall / "entscheide").mkdir()
    (fall / "entscheide" / f"A-M4-{snapshot}.json").write_text(json.dumps({
        "gate": "A-M4", "entscheid": "angenommen", "rolle": "mensch",
        "entscheider": "plv-aktuar", "schema_version": 6,
        "freigabe": {"schluessel_sha256": "16" * 32, "verfahren": "hmac-sha256-v1"},
        "zeichnung": {"rolle": "plv-aktuar"},
    }), encoding="utf-8")
    ziel = ueb.eingang_anlegen(tmp_path / "daten", fall, dt.date(2026, 1, 1))
    eingang = json.loads((ziel / "eingang.json").read_text("utf-8"))
    z = eingang["zeichnung"]
    assert z["rolle"] == "mensch" and z["entscheider"] == "plv-aktuar"
    assert z["schluesselklasse"] == "nicht ausgewiesen" and z["schema_version"] == 6
    assert z["schluessel_sha256"] == "16" * 8 and z["signatur_verifiziert"] is False
    gelesen = ueb.lies_uebernahmen(tmp_path / "daten" / "uebernahme",
                                   __import__("rechner_pipeline.bestand.config", fromlist=["load_config"]).load_config(PLV))
    assert gelesen[0].zeichnung == z
    # Ohne Snapshot im Fall: alles "nicht ausgewiesen", nichts leer.
    ohne = ueb.zeichnung_aus_snapshot(fall, "cd" * 32)
    assert ohne["rolle"] == "nicht ausgewiesen" and "kein A-M4-Snapshot" in ohne["quelle"]
    # Auf der Seite erscheint die Zeichnung der Uebernahme:
    html = st.rendere_html({
        "stand": "2026-02-03", "gefuehrt_seit": "2026-01-01",
        "bestand": {"in_force": 1, "je_produkt": {"klv": 1}},
        "neugeschaeft": {"woche": {}, "woche_summe": 0, "seit_betriebsbeginn": 0},
        "buchungen": {"gesamt": 0, "je_ereignis": {}, "letzte": []},
        "abschluesse": [], "provenienz": {"pb1": "gruen", "manifest_sha256": "ed" * 32},
        "uebernahmen": [{"fall": "probe", "stichtag": "2026-01-01", "vertraege": 3,
                         "snapshot_sha256": snapshot, "zeichnung": z}],
    })
    assert "<td>mensch</td><td>plv-aktuar</td><td>nicht ausgewiesen</td>" in html
    assert "Signatur hier nicht verifiziert" in html
