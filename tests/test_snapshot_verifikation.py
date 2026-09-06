"""Schluessellose Snapshot-Verifikation fuer Darstellungs-Leser.

Externer Review-Befund T19-02: Die Darstellungswerkzeuge lasen
Entscheid-Snapshots roh und wiesen sie als "gezeichnet" und "signiert"
aus — eine frei erfundene Datei erschien als gezeichnete Abnahme. Die
Werkzeuge duerfen aber keinen Schluesselring bekommen; die Frage ist
also, was OHNE Geheimnis pruefbar ist.

Die Antwort ist der Gegenstand dieser Tests: Schema, Selbstadressierung
und Dateiname. Wer diese drei besteht, ist nicht "gezeichnet", aber
auch nicht frei erfunden — und genau diese Unterscheidung muss die
Darstellung treffen koennen.

Knoten: klv
"""

from __future__ import annotations

import hashlib
import json

from rechner_pipeline.gates.gate_entscheid import (
    pruefe_snapshot_ohne_schluessel,
)
from rechner_pipeline.models.schemas import p9_snapshot_sha256


def _snapshot(**abweichungen) -> dict:
    """Ein schema-gueltiger, selbstadressierter Snapshot."""
    daten = {
        "schema_version": 6,
        "command": "gate_entscheid",
        "gate_version": "0.6.0",
        "gate": "A-M1",
        "entscheid": "angenommen",
        "entscheider": "plv-aktuar",
        "rolle": "mensch",
        "begruendung": "Stichtagstest bestanden",
        "fall": "ein-fall",
        "artefakt_hashes": {"eingang.json": "ab" * 32,
                            "abgeleitet/abox/abox.json": "cd" * 32},
        "system": {"branch": "fallbericht", "commit": "abc1234",
                   "dirty": "nein", "quellcode_sha256": "ef" * 32},
        "vorgaenger": [],
        "entschieden_am": "2026-09-01T10:00:00+00:00",
        "fall_scope": "bestand",
        "pflichtbelege": {"aktuartest": ["ab" * 32],
                          "aktuartest_bericht": ["cd" * 32]},
        "freigabe": {"schluessel_sha256": "cd" * 32,
                     "signatur": "ef" * 32, "verfahren": "hmac-sha256-v1"},
    }
    daten.update(abweichungen)
    daten["snapshot_sha256"] = p9_snapshot_sha256(daten)
    return daten


def _name(daten: dict) -> str:
    return f"{daten['gate']}-{daten['snapshot_sha256']}.json"


def test_echter_snapshot_ist_strukturell_unversehrt():
    daten = _snapshot()
    assert pruefe_snapshot_ohne_schluessel(daten, _name(daten)) == []


def test_frei_erfundene_datei_faellt_durch():
    """Der Repro des externen Reviews: freie Behauptungen ohne Deckung."""
    fake = {
        "gate": "A-M4", "entscheid": "angenommen", "rolle": "plv-aktuar",
        "entscheider": "wer auch immer", "begruendung": "alles bestens",
        "freigabe": {"schluessel_sha256": "00" * 32, "signatur": "00" * 32},
    }
    befunde = pruefe_snapshot_ohne_schluessel(fake, "A-M4-egal.json")
    assert befunde, "eine erfundene Datei muss auffallen"


def test_veraenderter_inhalt_bricht_die_selbstadressierung():
    """Mutationsfaenger: DAS ist der Kern der schluessellosen Pruefung.

    Wer die Begruendung nachtraeglich aendert, ohne den Hash neu zu
    bilden, faellt auf. Wer ihn neu bildet, aendert den Dateinamen —
    und faellt im naechsten Test auf.
    """
    daten = _snapshot()
    name = _name(daten)
    daten["begruendung"] = "nachtraeglich umgeschrieben"

    befunde = pruefe_snapshot_ohne_schluessel(daten, name)
    assert befunde, "eine nachtraegliche Aenderung muss auffallen"
    # Auf die SACHE geprueft, nicht auf den Wortlaut: Das Schema faengt
    # den Fall bereits, die eigene Hash-Pruefung der Funktion ist die
    # zweite Linie. Welche der beiden zuerst greift, ist eine
    # Implementierungsfrage — dass es auffaellt, ist die Zusicherung.
    assert any("canonical" in b or "Selbstadressierung" in b
               for b in befunde), befunde


def test_umbenannte_datei_faellt_auf():
    """Hash neu gebildet, aber unter altem Namen abgelegt."""
    daten = _snapshot(begruendung="andere Begruendung")
    befunde = pruefe_snapshot_ohne_schluessel(daten, "A-M1-fremdername.json")
    assert any("Dateiname" in b for b in befunde), befunde


def test_gate_im_namen_muss_zum_inhalt_passen():
    """Ein A-M1-Snapshot darf nicht als A-M4 auftreten — sonst zaehlte
    die Darstellung ihn in der falschen Abnahme."""
    daten = _snapshot(gate="A-M1")
    falsch = f"A-M4-{daten['snapshot_sha256']}.json"
    assert pruefe_snapshot_ohne_schluessel(daten, falsch)


def test_die_signatur_wird_ausdruecklich_NICHT_geprueft():
    """Die Grenze der Funktion, als Test festgeschrieben.

    Sie ist der Grund, warum Leser dieser Funktion einen Snapshot nie
    als 'gezeichnet' ausweisen duerfen: Eine falsche Signatur passiert
    sie, solange die Struktur stimmt. Wer das vergisst, baut den
    Review-Befund neu.
    """
    daten = _snapshot()
    daten["freigabe"] = {"schluessel_sha256": "00" * 32,
                         "signatur": "ff" * 32,
                         "verfahren": "hmac-sha256-v1"}
    daten["snapshot_sha256"] = p9_snapshot_sha256(daten)

    assert pruefe_snapshot_ohne_schluessel(daten, _name(daten)) == []


def test_hash_ist_der_kanonische_ueber_alle_anderen_felder():
    """Unabhaengige Nachrechnung: nicht die Implementierung befragen."""
    daten = _snapshot()
    ohne = {k: v for k, v in daten.items() if k != "snapshot_sha256"}
    erwartet = hashlib.sha256(
        json.dumps(ohne, sort_keys=True, separators=(",", ":"),
                   ensure_ascii=False).encode("utf-8")).hexdigest()
    assert daten["snapshot_sha256"] == erwartet
