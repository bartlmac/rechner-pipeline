"""A-K2: die Abnahme einer Rechenkern-Aenderung, und warum sie ohne
Regression nicht zeichenbar ist.

Entscheid des Maintainers 2026-09-16. Bis dahin war das folgenreichste,
was am Zielsystem geschieht — eine Formelaenderung, ein verschobener
Referenzwert — nur durch Commit-Disziplin geregelt (Abnahme-Protokoll in
``kern/__init__``): keine Zeichnung, kein Schluessel, kein Snapshot.

Der Kern der Sache steht in ``test_eine_stichprobe_ist_keine_regression``:
Eine Kern-Aenderung entsteht im Fall, aber der geaenderte Kern bewertet
danach den LAUFENDEN Bestand weiter. Wer nur eine Stichprobe rechnet,
findet den Fehler nicht, der einen von tausend Vertraegen trifft — und
genau der ist der gesuchte.

Knoten: system/entscheid
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from rechner_pipeline.fall import FALL_SCOPES, belegrollen
from rechner_pipeline.gates.gate_entscheid import (
    KERN_AENDERUNG_SCHEMA_VERSION,
    KERN_REGRESSION_SCHEMA_VERSION,
    kern_modul_hash,
    pruefe_kernaenderung,
    pruefe_kernregression,
    referenzwerte_hash,
)
from rechner_pipeline.models.zeichnung import GUELTIGE_GATES

REPO = Path(__file__).resolve().parents[1]

NULL = "0" * 64


def _aenderung(**abweichend):
    daten = {
        "schema_version": KERN_AENDERUNG_SCHEMA_VERSION,
        "von_version": "3.5.0",
        "nach_version": "3.6.0",
        "kern_sha256": kern_modul_hash(REPO),
        "referenzwerte_sha256": referenzwerte_hash(REPO),
        "geaenderte_referenzwerte": ["referenz_jung.json"],
        "begruendung": "PEX wertstetig absorbiert (Entscheid 2026-09-15).",
    }
    daten.update(abweichend)
    return daten


def _regression(**abweichend):
    daten = {
        "schema_version": KERN_REGRESSION_SCHEMA_VERSION,
        "von_version": "3.5.0",
        "nach_version": "3.6.0",
        "bestand_sha256": "a" * 64,
        "vertraege_gesamt": 834,
        "vertraege_geprueft": 834,
        "abweichungen": [
            {
                "police_id": "P-0001",
                "groesse": "dk",
                "vorher": 1000.0,
                "nachher": 1000.5,
                "differenz": 0.5,
            }
        ],
    }
    daten.update(abweichend)
    return daten


def _schreibe(pfad: Path, daten) -> Path:
    pfad.parent.mkdir(parents=True, exist_ok=True)
    pfad.write_text(json.dumps(daten), encoding="utf-8")
    return pfad


# --------------------------------------------------------------- Vokabel


def test_ak2_ist_zeichenbar_und_hat_einen_belegvertrag():
    assert "A-K2" in GUELTIGE_GATES
    for scope in FALL_SCOPES:
        assert belegrollen("A-K2", scope) == ["kernaenderung", "regression"]


def test_die_regression_ist_pflicht_in_jedem_scope():
    """Die eigentliche Entscheidung: nicht 'ausweisen', sondern 'erzwingen'.

    Derselbe Fehler war A-M4 im Bestands-Scope schon einmal unterlaufen
    (T21-02/T22-01) — ein optionaler Beleg nimmt jedes Teilprofil an.
    """
    for scope in FALL_SCOPES:
        assert "regression" in belegrollen("A-K2", scope)


# ------------------------------------------------- Beleg der Aenderung


def test_ein_gueltiger_aenderungsbeleg_geht_durch(tmp_path):
    pfad = _schreibe(tmp_path / "aenderung.json", _aenderung())
    assert pruefe_kernaenderung(pfad, tmp_path, repo_root=REPO) == []


def test_fehlende_datei_ist_ein_befund(tmp_path):
    assert pruefe_kernaenderung(
        tmp_path / "fehlt.json", tmp_path, repo_root=REPO
    ) == ["Datei fehlt"]


@pytest.mark.parametrize(
    "abweichend, erwartet",
    [
        ({"schema_version": 99}, "schema_version"),
        ({"von_version": "3.6.0"}, "keine Aenderung"),
        ({"von_version": "3.7.0"}, "laeuft aufwaerts"),
        ({"von_version": "drei"}, "von_version muss eine Version"),
        ({"kern_sha256": NULL}, "kern_sha256 stimmt nicht"),
        ({"kern_sha256": "kurz"}, "kern_sha256 fehlt oder ist kein SHA-256"),
        ({"referenzwerte_sha256": NULL}, "referenzwerte_sha256 stimmt nicht"),
        ({"geaenderte_referenzwerte": "eine"}, "geaenderte_referenzwerte"),
        ({"begruendung": "   "}, "begruendung fehlt"),
    ],
)
def test_der_aenderungsbeleg_faengt_die_naheliegenden_faelschungen(
    tmp_path, abweichend, erwartet
):
    pfad = _schreibe(tmp_path / "aenderung.json", _aenderung(**abweichend))
    fehler = pruefe_kernaenderung(pfad, tmp_path, repo_root=REPO)
    assert any(erwartet in f for f in fehler), (abweichend, fehler)


def test_ohne_repo_root_ist_der_kern_nicht_pruefbar_und_das_steht_da(tmp_path):
    """Kein stiller Durchlauf: Fehlt die Wurzel, sagt der Befund das."""
    pfad = _schreibe(tmp_path / "aenderung.json", _aenderung())
    fehler = pruefe_kernaenderung(pfad, tmp_path, repo_root=None)
    assert any("nicht pruefbar" in f for f in fehler), fehler


def test_die_leere_liste_geaenderter_referenzwerte_ist_erlaubt(tmp_path):
    """Nicht jede Kern-Aenderung verschiebt einen Referenzwert — fehlen
    darf die Liste aber nicht, sonst bliebe offen, ob niemand hingesehen
    oder niemand etwas gefunden hat."""
    pfad = _schreibe(
        tmp_path / "aenderung.json", _aenderung(geaenderte_referenzwerte=[])
    )
    assert pruefe_kernaenderung(pfad, tmp_path, repo_root=REPO) == []


# ------------------------------------------------------ Der Modulhash


def test_der_kernhash_sieht_jede_aenderung(tmp_path):
    """Positivkontrolle des Detektors: Ein Hash, der sich nie aendert,
    bezeugt nichts. Geprueft wird Inhalt UND Name."""
    paket = tmp_path / "src" / "rechner_pipeline" / "kern"
    paket.mkdir(parents=True)
    (paket / "a.py").write_text("x = 1\n", encoding="utf-8")
    vorher = kern_modul_hash(tmp_path)
    assert vorher is not None

    (paket / "a.py").write_text("x = 2\n", encoding="utf-8")
    assert kern_modul_hash(tmp_path) != vorher, "Inhaltsaenderung bleibt unsichtbar"

    (paket / "a.py").write_text("x = 1\n", encoding="utf-8")
    assert kern_modul_hash(tmp_path) == vorher, "Ruecknahme fuehrt nicht zurueck"

    (paket / "a.py").rename(paket / "b.py")
    assert kern_modul_hash(tmp_path) != vorher, "Umbenennung bleibt unsichtbar"


def test_ohne_kernpaket_gibt_es_keinen_hash(tmp_path):
    assert kern_modul_hash(tmp_path) is None


# ---------------------------------------------- Beleg der Regression


def test_ein_gueltiger_regressionsbeleg_geht_durch(tmp_path):
    pfad = _schreibe(tmp_path / "regression.json", _regression())
    assert pruefe_kernregression(
        pfad, tmp_path, aenderung=_aenderung()
    ) == []


def test_eine_stichprobe_ist_keine_regression(tmp_path):
    """DIE Regel dieses Gates.

    833 von 834 gerechnet heisst: Der eine, auf den es ankommt, kann der
    ungerechnete sein. Ein Beleg, der das zulaesst, bezeugt ein gutes
    Gefuehl, keine Regression.
    """
    pfad = _schreibe(
        tmp_path / "regression.json", _regression(vertraege_geprueft=833)
    )
    fehler = pruefe_kernregression(pfad, tmp_path, aenderung=_aenderung())
    assert any("Stichprobe ist keine Regression" in f for f in fehler), fehler


@pytest.mark.parametrize(
    "abweichend, erwartet",
    [
        ({"schema_version": 99}, "schema_version"),
        ({"vertraege_gesamt": 0, "vertraege_geprueft": 0}, "bezeugt nichts"),
        ({"vertraege_geprueft": -1}, "nicht-negative ganze Zahl"),
        ({"vertraege_geprueft": True}, "ganze Zahl"),
        ({"bestand_sha256": "kurz"}, "bestand_sha256"),
        ({"abweichungen": {}}, "keine Liste"),
        ({"abweichungen": [{"police_id": "P"}]}, "fehlt"),
        ({"nach_version": "9.9.9"}, "anderen Uebergang"),
    ],
)
def test_der_regressionsbeleg_faengt_die_naheliegenden_faelschungen(
    tmp_path, abweichend, erwartet
):
    pfad = _schreibe(tmp_path / "regression.json", _regression(**abweichend))
    fehler = pruefe_kernregression(pfad, tmp_path, aenderung=_aenderung())
    assert any(erwartet in f for f in fehler), (abweichend, fehler)


def test_eine_differenz_die_nicht_die_differenz_ist_faellt_auf(tmp_path):
    """Der Beleg darf sich nicht selbst widersprechen: Wer vorher,
    nachher und eine dritte Zahl schreibt, koennte die dritte schoenen."""
    pfad = _schreibe(
        tmp_path / "regression.json",
        _regression(
            abweichungen=[
                {
                    "police_id": "P-0001",
                    "groesse": "dk",
                    "vorher": 1000.0,
                    "nachher": 1500.0,
                    "differenz": 0.5,
                }
            ]
        ),
    )
    fehler = pruefe_kernregression(pfad, tmp_path, aenderung=_aenderung())
    assert any("ist nicht" in f and "nachher - vorher" in f for f in fehler), fehler


def test_die_regression_muss_zum_selben_uebergang_gehoeren(tmp_path):
    """Sonst legt man die Regression eines alten Uebergangs neben eine
    neue Aenderung — beide fuer sich stimmig, zusammen eine Luege."""
    pfad = _schreibe(
        tmp_path / "regression.json", _regression(von_version="3.0.0")
    )
    fehler = pruefe_kernregression(pfad, tmp_path, aenderung=_aenderung())
    assert any("anderen Uebergang" in f for f in fehler), fehler
