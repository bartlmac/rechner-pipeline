"""Das Darstellungs-Werkzeug glaubt Entscheid-Dateien nicht mehr blind.

Nachstellung des externen Review-Repros (T19-02): Eine frei erfundene
``entscheide/*.json`` ohne Signatur und ohne kanonischen Hash erschien
im Fallbericht als gezeichnete Abnahme, samt frei eingegebener
Begruendung. Der Fix prueft, was ohne Schluessel pruefbar ist; diese
Tests halten fest, dass die Unterscheidung im Modell ankommt.

Knoten: klv
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "werkzeuge"))

import falldaten  # noqa: E402

from rechner_pipeline.models.schemas import p9_snapshot_sha256  # noqa: E402


def _echter_snapshot(gate: str = "A-M1") -> dict:
    daten = {
        "schema_version": 6,
        "command": "gate_entscheid",
        "gate_version": "0.6.0",
        "gate": gate,
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
        "pflichtbelege": {"aktuartest": ["ab" * 32]},
        "freigabe": {"schluessel_sha256": "cd" * 32, "signatur": "ef" * 32,
                     "verfahren": "hmac-sha256-v1"},
    }
    daten["snapshot_sha256"] = p9_snapshot_sha256(daten)
    return daten


@pytest.fixture()
def fall(tmp_path: Path) -> Path:
    (tmp_path / "entscheide").mkdir()
    (tmp_path / "abgeleitet" / "diagnostics").mkdir(parents=True)
    echt = _echter_snapshot()
    name = f"{echt['gate']}-{echt['snapshot_sha256']}.json"
    (tmp_path / "entscheide" / name).write_text(
        json.dumps(echt, ensure_ascii=False), encoding="utf-8")
    return tmp_path


def test_echter_snapshot_gilt_als_strukturell_verifiziert(fall: Path):
    kette = falldaten.kette(fall)

    assert kette["entscheide_strukturell_verifiziert"] == 1
    assert kette["entscheide_mit_befund"] == 0
    eintrag, = kette["entscheide"]
    assert eintrag["strukturell_verifiziert"] is True
    assert eintrag["verifikationsbefunde"] == []


def test_frei_erfundene_datei_wird_nicht_mitgezaehlt(fall: Path):
    """Der Repro des Reviews — jetzt mit Befund statt mit Siegel."""
    (fall / "entscheide" / "A-M4-fake.json").write_text(json.dumps({
        "gate": "A-M4", "entscheid": "angenommen", "rolle": "plv-aktuar",
        "entscheider": "wer auch immer",
        "begruendung": "Alles bestens gelaufen.",
        "entschieden_am": "2026-09-04T10:00:00+00:00",
        "freigabe": {"schluessel_sha256": "00" * 32, "signatur": "0000"},
    }), encoding="utf-8")

    kette = falldaten.kette(fall)

    assert kette["entscheide_strukturell_verifiziert"] == 1, (
        "die erfundene Datei darf nicht als verifiziert zaehlen")
    assert kette["entscheide_mit_befund"] == 1
    fake = next(e for e in kette["entscheide"] if e["gate"] == "A-M4")
    assert fake["strukturell_verifiziert"] is False
    assert fake["verifikationsbefunde"], "der Befund muss benannt sein"


def test_nachtraeglich_geaenderte_begruendung_faellt_auf(fall: Path):
    """Die Begruendung ist der Text, den Menschen lesen — genau deshalb
    darf sie sich nicht unbemerkt aendern lassen."""
    pfad, = (fall / "entscheide").glob("*.json")
    daten = json.loads(pfad.read_text(encoding="utf-8"))
    daten["begruendung"] = "in Wahrheit nie so entschieden"
    pfad.write_text(json.dumps(daten, ensure_ascii=False), encoding="utf-8")

    kette = falldaten.kette(fall)

    assert kette["entscheide_mit_befund"] == 1
    assert kette["entscheide"][0]["strukturell_verifiziert"] is False


def test_die_signatur_gilt_ausdruecklich_als_ungeprueft(fall: Path):
    """Ehrlichkeit statt Siegel: Das Werkzeug hat keinen Schluessel und
    sagt das — die Darstellung darf daraus kein 'gezeichnet' machen."""
    kette = falldaten.kette(fall)

    assert kette["entscheide"][0]["signatur_verifiziert"] is False
    assert "nicht durchgefuehrt" in kette["signaturpruefung"]


# --------------------------------------------------------------------------- #
# T19-03: Vollstaendigkeit als MENGE, und Luecken im Dokument statt auf stderr
# --------------------------------------------------------------------------- #

def _volles_modell() -> dict:
    """Ein Modell, das alle Erwartungen erfuellt."""
    return {
        "fall": {"name": "ein-fall", "scope": "bestand"},
        "lieferung": {"quellen": [{"datei": "abzug.csv"}]},
        "bestand": {"anzahl": 834},
        "transformation": {"felder": [{"ziel": "police_id"}]},
        "parameter": {"generationen": ["klv/tg2015"]},
        "abnahmen": {
            "aktuariell": [{"kennung": k} for k in ("A-M1", "A-M2", "A-M3")],
            "controlling": {"anzahl": 834},
        },
        "kette": {
            "entscheide": [{"gate": g, "strukturell_verifiziert": True}
                           for g in ("A-M1", "A-M2", "A-M3", "A-M4")],
            "entscheide_mit_befund": 0,
        },
        "umbau": {"vorhanden": True},
    }


def test_vollstaendiges_modell_hat_keine_luecken():
    assert falldaten.luecken(_volles_modell()) == []


def test_fehlende_abnahme_faellt_auf_auch_wenn_die_liste_nichtleer_ist():
    """Der Kern des Befunds: 'irgendeine Abnahme' ist nicht 'die Abnahmen'."""
    modell = _volles_modell()
    modell["abnahmen"]["aktuariell"] = [{"kennung": "A-M1"}]

    felder = {l["feld"] for l in falldaten.luecken(modell)}

    assert "aktuariell:A-M2" in felder and "aktuariell:A-M3" in felder


def test_fehlendes_controlling_faellt_auf():
    modell = _volles_modell()
    modell["abnahmen"]["controlling"] = {}

    assert any(l["feld"] == "controlling"
               for l in falldaten.luecken(modell))


def test_snapshot_mit_befund_belegt_sein_gate_nicht():
    """Ein unstimmiger Snapshot darf keine Abnahme belegen — sonst waere
    die Verifikation aus T19-02 folgenlos."""
    modell = _volles_modell()
    modell["kette"]["entscheide"] = [
        {"gate": g, "strukturell_verifiziert": g != "A-M4"}
        for g in ("A-M1", "A-M2", "A-M3", "A-M4")]
    modell["kette"]["entscheide_mit_befund"] = 1

    felder = {l["feld"] for l in falldaten.luecken(modell)}

    assert "entscheide:A-M4" in felder
    assert "verifikation" in felder


def test_der_bericht_zeigt_seine_luecken_im_dokument():
    """T19-03, zweite Haelfte: nicht nur nach stderr, sondern in die Seite."""
    sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "werkzeuge"))
    import fallbericht

    modell = _volles_modell()
    modell["abnahmen"]["aktuariell"] = [{"kennung": "A-M1"}]

    block = fallbericht._luecken_block(modell)

    assert "Was dieser Bericht NICHT zeigt" in block
    assert "A-M2" in block and "A-M3" in block
    # Die Wirkung steht dabei, nicht nur der Feldname — der Leser soll
    # verstehen, was fehlt, nicht raten.
    assert "nicht vollstaendig abgenommen" in block


def test_vollstaendiger_bericht_traegt_keinen_luecken_block():
    """Gegenprobe: Der Block erscheint nur, wenn es etwas zu melden gibt."""
    sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "werkzeuge"))
    import fallbericht

    assert fallbericht._luecken_block(_volles_modell()) == ""


# --------------------------------------------------------------------------- #
# T20-03: Sollmengen folgen dem Fall-Scope; Luecken enden nicht mit Exit 0;
# die Vorzeigeseite zeigt sie. T20-02: kein "gezeichnet" ohne Verifikation.
# --------------------------------------------------------------------------- #

def test_tarif_scope_verlangt_keine_bestandsabnahmen():
    """Der Nachweis des Reviews: Ein vertragsgemaesser Tarif-Fall (A-M1 und
    A-M4) bekam vier falsche Bestands-Scope-Luecken. Die Sollmenge folgt
    jetzt derselben Vertragsquelle wie gates.gate_entscheid."""
    modell = _volles_modell()
    modell["fall"]["scope"] = "tarif"
    modell["abnahmen"] = {"aktuariell": [{"kennung": "A-M1"}]}
    modell["bestand"] = {}
    modell["transformation"] = {}
    modell["kette"]["entscheide"] = [
        {"gate": g, "strukturell_verifiziert": True} for g in ("A-M1", "A-M4")]

    assert falldaten.luecken(modell) == []


def test_bestand_scope_verlangt_alle_drei_abnahmen():
    modell = _volles_modell()
    modell["abnahmen"]["aktuariell"] = [{"kennung": "A-M1"}]
    felder = {l["feld"] for l in falldaten.luecken(modell)}
    assert {"aktuariell:A-M2", "aktuariell:A-M3"} <= felder


def _leerer_fall(tmp_path: Path, scope: str = "bestand") -> Path:
    """Ein echter, leerer Fall-Arbeitsbereich — so, wie ihn das Review durch
    alle drei Werkzeug-CLIs geschickt hat (15 Luecken, Renderer Exit 0)."""
    fall = tmp_path / "fall"
    (fall / "abgeleitet" / "berichte").mkdir(parents=True)
    (fall / "abgeleitet" / "diagnostics").mkdir(parents=True)
    (fall / "entscheide").mkdir()
    (fall / "fall.json").write_text(
        json.dumps({"name": "ein-fall", "scope": {"typ": scope}}), encoding="utf-8")
    (fall / "eingang.json").write_text(json.dumps({"quellen": []}), encoding="utf-8")
    return fall


def test_fallbericht_mit_luecken_endet_nicht_mit_null(tmp_path: Path, capsys):
    """Geschrieben wird der Bericht — mit Lueckenblock —, aber der Exit-Code
    sagt es: 3 statt 0. Wer nur den Exit-Code weiterreicht, sieht es."""
    import fallbericht

    fall = _leerer_fall(tmp_path)
    modell = falldaten.sammle(fall, [])
    assert modell["luecken"], "Vorbedingung: der leere Fall hat Luecken"
    daten = tmp_path / "d.json"
    daten.write_text(json.dumps(modell, default=str), encoding="utf-8")
    out = tmp_path / "b.html"

    assert fallbericht.main(["--daten", str(daten), "--out", str(out)]) == 3
    assert out.is_file() and "Was dieser Bericht NICHT zeigt" in out.read_text(encoding="utf-8")
    assert "LUECKE" in capsys.readouterr().err


def test_vorzeigeseite_zeigt_luecken_und_endet_nicht_mit_null(tmp_path: Path):
    """Der Nachweis des Reviews: 15 Luecken, die Seite zeigte keine und
    endete mit Exit 0. Jetzt stehen sie auf der Seite, und der Exit ist 3."""
    import vorzeigeseite as vz

    fall = _leerer_fall(tmp_path)
    modell = falldaten.sammle(fall, [])
    daten = tmp_path / "d.json"
    daten.write_text(json.dumps(modell, default=str), encoding="utf-8")

    seite = vz._seite(fall, modell, tmp_path, [], None)
    assert "Was diese Seite NICHT zeigt" in seite
    assert "aktuarielle Abnahme A-M2" in seite

    out = tmp_path / "seite"
    assert vz.main(["--fall", str(fall), "--daten", str(daten), "--out", str(out),
                    "--repo", str(tmp_path)]) == 3
    assert "Was diese Seite NICHT zeigt" in (out / "index.md").read_text(encoding="utf-8")


def test_vorzeigeseite_nennt_nichts_gezeichnet_ohne_verifizierte_signatur(tmp_path: Path):
    """T20-02: Ein strukturell gueltiger Snapshot mit frei gewaehltem HMAC —
    das Modell sagt signatur_verifiziert=False, die Seite sagte trotzdem
    'HMAC-signiert' und 'gezeichnet'."""
    import vorzeigeseite as vz

    fall = _leerer_fall(tmp_path)
    modell = falldaten.sammle(fall, [])
    modell["kette"]["entscheide"] = [
        {"gate": g, "entscheid": "angenommen", "entscheider": "plv-aktuar",
         "rolle": "mensch", "entschieden_am": "2026-09-01T10:00:00+00:00",
         "schluessel_sha256": "cd" * 8, "pflichtbelege": [], "artefakte_gebunden": 2,
         "begruendung": "x", "strukturell_verifiziert": True,
         "verifikationsbefunde": [], "signatur_verifiziert": False}
        for g in ("A-M1", "A-M4")]

    seite = vz._seite(fall, modell, tmp_path, [], None)
    assert "Signatur hier nicht verifiziert" in seite
    assert "HMAC-signiert" not in seite
    assert "gezeichnet" not in seite.replace("nichts gezeichnet", "")

    # Gegenprobe: Erst eine verifizierte Signatur traegt das Wort.
    for e in modell["kette"]["entscheide"]:
        e["signatur_verifiziert"] = True
    seite = vz._seite(fall, modell, tmp_path, [], None)
    assert "Signatur verifiziert, gezeichnet" in seite
