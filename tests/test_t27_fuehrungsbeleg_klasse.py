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
