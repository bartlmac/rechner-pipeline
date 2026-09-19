"""Zwei Faelle sprechen nie ueber dieselben Policennummern.

Das Register der Nummernbaender ist die Summe der Eingaenge selbst: Jeder
nennt sein Band in ``eingang.json``, und das naechste wird daraus
abgeleitet. Lesen und Fortschreiben sind damit ZWEI Schritte — und was
dazwischen passiert, hat niemand verhindert.

Befund T26-14: Zwei gleichzeitige Registrierungen bekamen dasselbe Band
und veroeffentlichten beide erfolgreich. Aufgefallen ist es erst im
Tagesbetrieb, als "police_id-Kollision zwischen eigenem und uebernommenem
Bestand". Die Trennung der Zahlenraeume war bis dahin nur behauptet.

Geprueft wird deshalb auf beiden Seiten: die Sperre, die den Schreiber
haelt, UND die Nachrechnung beim Lesen. Eine Sperre schuetzt nur
Prozesse, die sie nehmen; ob die Baender disjunkt SIND, steht in den
Eingaengen.

Knoten: klv, bu
"""

from __future__ import annotations

import json

import pytest

from rechner_pipeline.betrieb import uebernahme as ueb
from rechner_pipeline.betrieb.uebernahme import (
    EINGANG_DATEI, UEBERNAHME_DIR, UebernahmeError, baender_fehler,
    eingang_sperre,
)

from tests.test_betrieb_uebernahme import STICHTAG, _fall, _kleine_config


# --------------------------------------------------------------------------- #
# Die Regel selbst — an ihren Grenzen, in beide Richtungen
# --------------------------------------------------------------------------- #

#: (Beschreibung, Baender, erwartet_fehlerhaft)
BANDLAGEN = [
    ("getrennt mit Luecke", [(1, 100), (200, 300)], False),
    ("buendig aneinander", [(1, 100), (101, 200)], False),
    ("um genau eins ueberlappend", [(1, 100), (100, 200)], True),
    ("vollstaendig gleich", [(1, 100), (1, 100)], True),
    ("eines im anderen", [(1, 1000), (400, 500)], True),
    ("verkehrte Reihenfolge, ueberlappend", [(200, 300), (250, 400)], True),
    ("drei, nur das letzte Paar stoert", [(1, 10), (11, 20), (20, 30)], True),
    ("drei, alle getrennt", [(1, 10), (11, 20), (21, 30)], False),
    ("ein einziges Band", [(1, 10)], False),
    ("gar keines", [], False),
]


@pytest.mark.parametrize("was,baender,fehlerhaft", BANDLAGEN)
def test_die_bandregel_trifft_ihre_grenze_in_beide_richtungen(was, baender, fehlerhaft):
    """Buendig ist erlaubt, um eins ueberlappend nicht.

    Beide Richtungen, weil nur die zweite den Geltungsbereich bindet: Eine
    Regel, die man verschaerfen kann, ohne dass etwas rot wird, gilt
    weniger weit, als ihr Name behauptet.
    """
    eintraege = [{"fall": f"fall{i}", "von": v, "bis": b}
                 for i, (v, b) in enumerate(baender)]
    fehler = baender_fehler(eintraege)
    assert bool(fehler) is fehlerhaft, (was, fehler)


# --------------------------------------------------------------------------- #
# Die Schreibseite: eine Sperre um Lesen und Fortschreiben
# --------------------------------------------------------------------------- #

def test_ein_zweiter_schreiber_kommt_nicht_dazwischen(tmp_path):
    """Haelt jemand die Sperre, wird nicht registriert — mit Meldung.

    Deterministisch geprueft: Die Sperre wird im Test selbst gehalten,
    nicht ueber ein Zeitfenster erhofft.
    """
    stand = tmp_path / "daten"
    with eingang_sperre(stand):
        with pytest.raises(UebernahmeError, match="registriert"):
            ueb.eingang_anlegen(stand, _fall(tmp_path, "waehrenddessen"), STICHTAG)
    # Danach geht es wieder — sonst waere die Sperre ein Dauerzustand.
    ziel = ueb.eingang_anlegen(stand, _fall(tmp_path, "danach"), STICHTAG)
    assert ziel.is_dir()


def test_die_sperre_deckt_das_fenster_zwischen_lesen_und_veroeffentlichen(tmp_path):
    """Der Befund selbst, deterministisch nachgestellt.

    Die Luecke lag GENAU zwischen dem Lesen des Registers und der
    Publikation: Beide Registrierungen lasen denselben Stand, beide
    rechneten dasselbe naechste Band aus, beide veroeffentlichten.

    Nachgestellt wird sie von innen — waehrend der erste Schreiber im
    Register liest, versucht ein zweiter zu registrieren. Ohne Sperre
    gelingt ihm das; mit Sperre nicht. Kein Zeitfenster, keine Threads,
    kein Zufall.
    """
    stand = tmp_path / "daten"
    zweiter_fall = _fall(tmp_path, "dazwischen")
    gesehen = {}
    echt = ueb.vergebene_baender

    def _dazwischen(wurzel):
        if "n" not in gesehen:
            gesehen["n"] = True
            try:
                ueb.eingang_anlegen(stand, zweiter_fall, STICHTAG)
                gesehen["zweiter"] = "durchgekommen"
            except UebernahmeError as exc:
                gesehen["zweiter"] = str(exc)
        return echt(wurzel)

    ueb.vergebene_baender = _dazwischen
    try:
        erst = ueb.eingang_anlegen(stand, _fall(tmp_path, "erst"), STICHTAG)
    finally:
        ueb.vergebene_baender = echt

    assert gesehen.get("n"), "der Zwischenruf ist nie gelaufen — der Test saehe nichts"
    assert "registriert" in gesehen["zweiter"], gesehen["zweiter"]
    assert erst.is_dir()
    # Und der zweite ist auch nicht halb entstanden:
    assert not (stand / UEBERNAHME_DIR / "dazwischen").exists()


# --------------------------------------------------------------------------- #
# Die Leseseite: nachgerechnet, nicht geglaubt
# --------------------------------------------------------------------------- #

def _ueberschneide(ziel, von: int, bis: int) -> None:
    """Das Band eines registrierten Eingangs von Hand verbiegen."""
    pfad = ziel / EINGANG_DATEI
    pfad.chmod(0o644)
    daten = json.loads(pfad.read_text(encoding="utf-8"))
    daten["band"] = {"von": von, "bis": bis}
    pfad.write_text(json.dumps(daten, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
                    encoding="utf-8")


def test_der_leser_rechnet_die_baender_nach(tmp_path):
    """Ueberlappende Baender fallen beim Lesen auf, nicht erst im Lauf.

    Die Positivkontrolle steht davor: Dieselben zwei Eingaenge unveraendert
    werden anstandslos gelesen. Ohne sie koennte die Pruefung alles
    ablehnen und saehe genauso gruen aus.
    """
    from rechner_pipeline.bestand.config import load_config

    stand = tmp_path / "daten"
    erst = ueb.eingang_anlegen(stand, _fall(tmp_path, "erst"), STICHTAG)
    zweit = ueb.eingang_anlegen(stand, _fall(tmp_path, "zweit"), STICHTAG)
    cfg_pfad = tmp_path / "bestand.toml"
    cfg_pfad.write_text(_kleine_config(), encoding="utf-8")
    config = load_config(cfg_pfad)

    gelesen = ueb.lies_uebernahmen(stand / UEBERNAHME_DIR, config)
    assert len(gelesen) == 2
    assert all(u.band for u in gelesen), "das Band gehoert in den gelesenen Eingang"

    erstes_band = json.loads((erst / EINGANG_DATEI).read_text(encoding="utf-8"))["band"]
    _ueberschneide(zweit, int(erstes_band["von"]), int(erstes_band["bis"]))
    with pytest.raises(UebernahmeError, match="ueberschneiden"):
        ueb.lies_uebernahmen(stand / UEBERNAHME_DIR, config)
