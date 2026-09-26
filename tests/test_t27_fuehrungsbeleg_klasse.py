"""Der Fuehrungsbeleg wird nachgerechnet, nicht geglaubt — Pruefrunde T27, Befund 06.

Die Klasse: Ein Beleg, dessen Urteil der Konsument nur auf Form prueft
(Zaehler positiv, Felder nicht leer, Hashes der Eingaben), ist eine
Selbstaussage des Erzeugers. Der Gutachter aenderte nur den Beleg —
Stichtag "kein-Datum", erfundene Generation und Tarifwerk, Fortschreibung
weg, fortschreibung_geprueft = true — und Abnahmebericht wie A-M4-Entscheid
nahmen ihn an. Der Konsument faehrt die Probe jetzt mit dem Aufruf, den
der Beleg nennt, auf den gebundenen Eingaben neu und haelt das Ergebnis
Feld fuer Feld gegen den Beleg — dieselbe Figur wie _b1_fehler.

Knoten: system/abnahme
"""

from __future__ import annotations

import copy
import json
from pathlib import Path

import pytest

from tests.test_pk1_am4_beweisvertrag import _abnahmebericht, _bereite_bestandsfall


@pytest.fixture(scope="module")
def fall(tmp_path_factory):
    return _bereite_bestandsfall(tmp_path_factory.mktemp("fuehrungsbeleg"))


def _probe_pfad(fall: Path) -> Path:
    return fall / "abgeleitet" / "berichte" / "fuehrungsprobe.json"


def _mit_beleg(fall: Path, beleg: dict):
    pfad = _probe_pfad(fall)
    gut = pfad.read_bytes()
    pfad.write_text(json.dumps(beleg, sort_keys=True), encoding="utf-8")
    try:
        return _abnahmebericht(fall)
    finally:
        pfad.write_bytes(gut)


def test_der_selbst_behauptete_fuehrungsbeleg_des_gutachters_wird_abgewiesen(fall):
    gut = json.loads(_probe_pfad(fall).read_text(encoding="utf-8"))
    assert _abnahmebericht(fall).exit_code == 0, "Positivkontrolle"
    ueber = gut["provenienz"]["parameter"]["uebernahme"]
    beleg = copy.deepcopy(gut)
    beleg.update({
        "stichtag": "kein-Datum", "generation": "nicht-vorhandene-Generation",
        "tarifwerk": {"frei_erfunden": True}, "buchungen_geprueft": None,
        "fortschreibung_geprueft": True,
    })
    beleg["provenienz"]["parameter"]["fortschreibung"] = None
    beleg["provenienz"]["eingaben"] = {
        k: v for k, v in gut["provenienz"]["eingaben"].items() if k.startswith(ueber + "/")}
    bericht = _mit_beleg(fall, beleg)
    assert bericht.exit_code != 0, "der selbst behauptete Beleg kam durch"


def _anders(wert):
    if isinstance(wert, bool):
        return not wert
    if isinstance(wert, int):
        return wert + 1
    if isinstance(wert, float):
        return wert + 1.0
    if isinstance(wert, str):
        return wert + "-x"
    if isinstance(wert, list):
        return wert[:-1] if wert else [{"police_id": "1", "art": "x", "text": "x"}]
    if isinstance(wert, dict):
        return {**wert, "zusatz": 1}
    return "gesetzt"


def _felder(beleg: dict):
    """Jedes Blatt der obersten Ebene und der Provenienz — ganze Tabelle,
    nicht eine Auswahl."""
    for k in sorted(beleg):
        if k == "provenienz":
            for unter in sorted(beleg[k]):
                if isinstance(beleg[k][unter], dict):
                    for blatt in sorted(beleg[k][unter]):
                        yield ("provenienz", unter, blatt)
                else:
                    yield ("provenienz", unter)
        else:
            yield (k,)


def test_jedes_feld_des_belegs_wird_nachgerechnet(fall):
    """Mutationsprobe als Test: Ein einzelnes geaendertes Feld, sonst der
    echte Beleg — jede Aenderung muss abgewiesen werden. Wer ein Feld nicht
    nachrechnet, glaubt es."""
    gut = json.loads(_probe_pfad(fall).read_text(encoding="utf-8"))
    durch = []
    felder = list(_felder(gut))
    assert len(felder) > 20, "der Beleg hat weniger Felder, als der Test annimmt"
    for pfad in felder:
        beleg = copy.deepcopy(gut)
        ziel = beleg
        for teil in pfad[:-1]:
            ziel = ziel[teil]
        ziel[pfad[-1]] = _anders(ziel[pfad[-1]])
        if _mit_beleg(fall, beleg).exit_code == 0:
            durch.append("/".join(pfad))
    assert durch == [], f"diese Felder werden geglaubt, nicht nachgerechnet: {durch}"


def test_ein_stimmig_gefaelschter_aufruf_mit_fremdem_stichtag_besteht_nicht(fall):
    """Wer Aufruf UND Beleg gemeinsam aendert, bekommt eine echte Probe
    eines anderen Aufrufs. Der Stichtag ist darum keine Angabe des
    Aufrufs, sondern eine Eigenschaft des Bestands (Bestandszugang):
    Ein anderer Stichtag besteht nicht."""
    import contextlib
    import io

    from rechner_pipeline.gates import fuehrungsprobe
    from tests.test_pk1_am4_beweisvertrag import REPO_ROOT

    gut = json.loads(_probe_pfad(fall).read_text(encoding="utf-8"))
    aufruf = list(gut["provenienz"]["aufruf"])
    i = aufruf.index("--stichtag") + 1
    aufruf[i] = "2026-02-01"
    argv = ["--fall", str(fall), "--repo-root", str(REPO_ROOT)]
    for j, wert in enumerate(aufruf):
        if j and aufruf[j - 1] in fuehrungsprobe.PFAD_OPTIONEN and not Path(wert).is_absolute():
            wert = str(fall / wert)
        argv.append(wert)
    with contextlib.redirect_stderr(io.StringIO()):
        _code, neu = fuehrungsprobe.fuehre_probe(fuehrungsprobe.parser().parse_args(argv))
    assert neu is not None and not neu["bestanden"]
    assert any(b["art"] == "stichtag" for b in neu["befunde"])


# --------------------------------------------------------------------------- #
# Angriffsrunde nach T27: WORUEBER die Probe urteilt, bestimmt nicht der Beleg
# --------------------------------------------------------------------------- #


def _probe_neu(fall: Path, ersetze: dict) -> None:
    """Die Probe mit ihrem eigenen Aufruf neu fahren — ehrlich, auf dem,
    was der Aufruf nennt; ``ersetze`` tauscht Optionswerte."""
    from rechner_pipeline.gates import fuehrungsprobe
    from tests.test_pk1_am4_beweisvertrag import REPO_ROOT

    beleg = json.loads(_probe_pfad(fall).read_text(encoding="utf-8"))
    aufruf = list(beleg["provenienz"]["aufruf"])
    for option, wert in ersetze.items():
        aufruf[aufruf.index(option) + 1] = wert
    argv = ["--fall", str(fall), "--repo-root", str(REPO_ROOT)]
    for j, wert in enumerate(aufruf):
        if j and aufruf[j - 1] in fuehrungsprobe.PFAD_OPTIONEN and not Path(wert).is_absolute():
            wert = str(fall / wert)
        argv.append(wert)
    fuehrungsprobe.main(argv)


def test_eine_probe_auf_einer_kopie_der_uebernahme_wird_abgewiesen(tmp_path):
    """Mutationsprobe: die Pruefung des Uebernahme-Verzeichnisses entfernen -> rot."""
    import shutil

    fall = _bereite_bestandsfall(tmp_path)
    shutil.copytree(fall / "abgeleitet" / "bestand", fall / "abgeleitet" / "bestand-kopie")
    _probe_neu(fall, {"--uebernahme": "abgeleitet/bestand-kopie"})
    bericht = _abnahmebericht(fall)
    assert bericht.exit_code != 0
    assert "nicht die des Falls" in " ".join(f["message"] for f in bericht.errors)


def test_eine_fortschreibung_vor_dem_folgestichtag_wird_abgewiesen(tmp_path):
    """Mutationsprobe: den Horizontvergleich entfernen -> rot."""
    from rechner_pipeline.bestand import cli_fortschreibung

    fall = _bereite_bestandsfall(tmp_path)
    beleg = json.loads(_probe_pfad(fall).read_text(encoding="utf-8"))
    aufruf = beleg["provenienz"]["aufruf"]
    config = aufruf[aufruf.index("--config") + 1]
    kurz = fall / "abgeleitet" / "bestand-kurz"
    assert cli_fortschreibung.main([
        "--config", str(fall / config if not Path(config).is_absolute() else config),
        "--uebernahme", str(fall / "abgeleitet" / "bestand"),
        "--bis", "2026-01-02", "--out-dir", str(kurz)]) == 0
    _probe_neu(fall, {"--fortschreibung": "abgeleitet/bestand-kurz"})
    bericht = _abnahmebericht(fall)
    assert bericht.exit_code != 0
    assert "Folgestichtag" in " ".join(f["message"] for f in bericht.errors)


def test_eine_fortschreibung_die_p_b1_abweist_wird_abgewiesen(tmp_path):
    """Eine Buchung, die die Probe nicht ansieht (der Zugang am Stichtag),
    stimmig ins Manifest nachgezogen, die Probe ehrlich neu gefahren —
    P-B1 leitet sie her und weist ab. Stellvertretend fuer jede Regel, die
    P-B1 kennt und die Probe nicht nachbaut (RED ausserhalb des
    Reduktionsjahres, Hoehe der Erhoehungen). Mutationsprobe: P-B1 auf
    der Fortschreibung nicht fahren -> rot."""
    import hashlib

    import pandas as pd

    from rechner_pipeline.bestand.parquet_io import read_portfolio, write_portfolio

    import shutil

    fall = _bereite_bestandsfall(tmp_path)
    # Eine ZWEITE Fortschreibung neben der, die der P-B1-Beleg bindet: Der
    # Beleg bleibt gueltig, die Probe wird auf die andere gerichtet.
    lauf = fall / "abgeleitet" / "bestand-falsch"
    shutil.copytree(fall / "abgeleitet" / "bestand-nach", lauf)
    ledger = read_portfolio(lauf / "ledger.parquet")
    zug = ledger.index[ledger["ereignis"] == "ZUG"]
    assert len(zug), "die Welt traegt keinen Zugang"
    neu = ledger.copy()
    neu.loc[zug[0], "betrag"] = float(neu.loc[zug[0], "betrag"]) + 1000.0
    (lauf / "ledger.parquet").chmod(0o644)
    write_portfolio(neu, lauf / "ledger.parquet")
    manifest = json.loads((lauf / "laufmanifest.json").read_text(encoding="utf-8"))
    manifest["ausgaben"]["ledger.parquet"] = hashlib.sha256(
        (lauf / "ledger.parquet").read_bytes()).hexdigest()
    (lauf / "laufmanifest.json").chmod(0o644)
    (lauf / "laufmanifest.json").write_text(json.dumps(manifest, sort_keys=True), encoding="utf-8")
    _probe_neu(fall, {"--fortschreibung": "abgeleitet/bestand-falsch"})
    bericht = _abnahmebericht(fall)
    assert bericht.exit_code != 0
    assert "P-B1 weist die gepruefte Fortschreibung ab" in " ".join(
        f["message"] for f in bericht.errors)
