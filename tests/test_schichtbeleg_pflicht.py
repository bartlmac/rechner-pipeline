"""Schichtbeleg-Pflicht beim uebernommenen Bestand mit Verankerung.

Die Probe nutzt die echten Erzeugeraufrufe der Baldrian-zwei-Testwelt.
Ein Lauf ohne Schichtbeleg darf bei derselben Verankerung nicht mehr rechnen.

Knoten: klv
"""

from __future__ import annotations

import json
import hashlib
import copy
import shutil
from pathlib import Path

import pytest

from rechner_pipeline.gates import (
    abnahmebericht, aktuartest, aktuartest_lauf, fuehrungsprobe,
    migrationssuite_lauf,
)
from rechner_pipeline.gates._common import Eingangsbindung
from tests.test_baldrian2_e2e import gefahrener_fall

REPO_ROOT = Path(__file__).resolve().parents[1]


def _aufruf_aus_beleg(modul, beleg: dict, fall: Path, *, ohne_schicht: bool):
    aufruf = list(beleg["provenienz"]["aufruf"] if modul is fuehrungsprobe
                  else beleg["aufruf"])
    if ohne_schicht:
        stelle = aufruf.index("--schicht")
        del aufruf[stelle:stelle + 2]
    argv = ["--fall", str(fall), "--repo-root", str(REPO_ROOT)]
    for i, wert in enumerate(aufruf):
        if (i and aufruf[i - 1] in modul.PFAD_OPTIONEN
                and not Path(wert).is_absolute()):
            wert = str(fall / wert)
        argv.append(wert)
    return modul.parser().parse_args(argv)


@pytest.mark.parametrize("modul,datei,funktion", [
    (aktuartest_lauf, "aktuartest.json", "fuehre_test"),
    (migrationssuite_lauf, "migrationssuite.json", "fuehre_suite"),
    (fuehrungsprobe, "fuehrungsprobe.json", "fuehre_probe"),
])
def test_verankerung_ohne_schichtbeleg_stoppt_den_lauf(
    gefahrener_fall: Path, modul, datei: str, funktion: str,
) -> None:
    fall = gefahrener_fall
    bestand = fall / "abgeleitet" / "bestand"
    assert (bestand / "verankerung.parquet").is_file()
    assert (bestand / "laufmanifest.json").is_file()
    beleg = json.loads((fall / "abgeleitet" / "berichte" / datei).read_text("utf-8"))
    assert "--schicht" in (beleg["provenienz"]["aufruf"] if modul is fuehrungsprobe
                           else beleg["aufruf"])
    args = _aufruf_aus_beleg(modul, beleg, fall, ohne_schicht=True)
    with pytest.raises(SystemExit, match="Schichtbeleg"):
        getattr(modul, funktion)(args)


@pytest.fixture()
def fallkopie(gefahrener_fall: Path, tmp_path: Path) -> Path:
    ziel = tmp_path / "fall"
    shutil.copytree(gefahrener_fall, ziel)
    return ziel


def _pflicht(fall: Path, schicht: str | None):
    return aktuartest_lauf._schichtpflicht(
        fall, fall / "abgeleitet" / "bestand" / "bestand.parquet",
        schicht, Eingangsbindung(fall))


def _manifest_ohne_verankerung(fall: Path) -> None:
    pfad = fall / "abgeleitet" / "bestand" / "laufmanifest.json"
    daten = json.loads(pfad.read_text("utf-8"))
    del daten["ausgaben"]["verankerung.parquet"]
    pfad.write_text(json.dumps(daten), encoding="utf-8")


def test_gueltiger_beleg_und_verankerungsfreier_bestand(fallkopie: Path) -> None:
    fall = fallkopie
    schicht = str(fall / "abgeleitet" / "schichten" / "verankerung_schichten.json")
    assert _pflicht(fall, schicht) is True
    (fall / "abgeleitet" / "bestand" / "verankerung.parquet").unlink()
    _manifest_ohne_verankerung(fall)
    assert _pflicht(fall, None) is False


@pytest.mark.parametrize("abweichung", ["ohne_manifest", "ohne_datei", "ohne_rolle",
                                            "falscher_hash", "leer", "beschaedigt"])
def test_manifest_und_verankerungsbytes_sind_pflicht(
    fallkopie: Path, abweichung: str,
) -> None:
    fall = fallkopie
    lauf = fall / "abgeleitet" / "bestand"
    verankerung = lauf / "verankerung.parquet"
    manifest = lauf / "laufmanifest.json"
    if abweichung == "ohne_manifest":
        manifest.unlink()
    elif abweichung == "ohne_datei":
        verankerung.unlink()
    elif abweichung == "ohne_rolle":
        _manifest_ohne_verankerung(fall)
    else:
        if abweichung in ("leer", "beschaedigt"):
            verankerung.write_bytes(b"" if abweichung == "leer" else b"kein Parquet")
        daten = json.loads(manifest.read_text("utf-8"))
        daten["ausgaben"]["verankerung.parquet"] = (
            "0" * 64 if abweichung == "falscher_hash"
            else hashlib.sha256(verankerung.read_bytes()).hexdigest())
        manifest.write_text(json.dumps(daten), encoding="utf-8")
    with pytest.raises(SystemExit, match="[Vv]erankerung|Laufmanifest"):
        _pflicht(fall, None)


def test_registrierter_schichtbeleg_zaehlt_nicht(fallkopie: Path) -> None:
    fall = fallkopie
    quelle = fall / "eingang" / "schichtbeleg.json"
    quelle.write_bytes((fall / "abgeleitet" / "schichten"
                        / "verankerung_schichten.json").read_bytes())
    with pytest.raises(SystemExit, match="abgeleitet"):
        _pflicht(fall, str(quelle))


def test_beleg_muss_verankerung_und_bestand_binden(fallkopie: Path) -> None:
    fall = fallkopie
    beleg = fall / "abgeleitet" / "schichten" / "verankerung_schichten.json"
    original = beleg.read_bytes()
    for name in ("verankerung.parquet", "bestand.parquet"):
        daten = json.loads(beleg.read_text("utf-8"))
        eingaben = daten["provenienz"]["eingaben"]
        del eingaben[f"abgeleitet/bestand/{name}"]
        beleg.write_text(json.dumps(daten), encoding="utf-8")
        with pytest.raises(SystemExit, match="[Vv]erankerung|Bestand"):
            _pflicht(fall, str(beleg))
        # Jede Probe beginnt wieder beim echten Producerbeleg.
        beleg.write_bytes(original)


@pytest.mark.parametrize("datei", [
    "aktuartest.json", "aktuartest-A-M2.json", "aktuartest-A-M3.json",
])
def test_aktuartest_vorlage_prueft_die_pflicht_vor_der_nachrechnung(
        gefahrener_fall: Path, monkeypatch, datei: str) -> None:
    fall = gefahrener_fall
    original = json.loads((fall / "abgeleitet" / "berichte" / datei).read_text("utf-8"))
    assert aktuartest.test_nachgerechnet(original, fall, REPO_ROOT) == []
    kaputt = copy.deepcopy(original)
    aufruf = kaputt["aufruf"]
    stelle = aufruf.index("--schicht")
    del aufruf[stelle:stelle + 2]

    # Diese Gegenprobe schaltet nur die zweite Sicherung aus. Die Vorlage
    # muss die Fallrolle trotzdem vor dem Rendern erkennen.
    monkeypatch.setattr(aktuartest_lauf, "fuehre_test", lambda _args: (0, kaputt))
    assert aktuartest.test_nachgerechnet(kaputt, fall, REPO_ROOT)


@pytest.mark.parametrize("datei,pruefer,erzeuger", [
    ("migrationssuite.json", abnahmebericht._suite_nachgerechnet, migrationssuite_lauf),
    ("fuehrungsprobe.json", abnahmebericht._fuehrungsprobe_nachgerechnet, fuehrungsprobe),
])
def test_am4_vorlage_prueft_die_pflicht_vor_der_nachrechnung(
        gefahrener_fall: Path, monkeypatch, datei, pruefer, erzeuger) -> None:
    fall = gefahrener_fall
    original = json.loads((fall / "abgeleitet" / "berichte" / datei).read_text("utf-8"))
    assert pruefer(original, fall, REPO_ROOT) == []
    kaputt = copy.deepcopy(original)
    aufruf = kaputt["provenienz"]["aufruf"] if erzeuger is fuehrungsprobe else kaputt["aufruf"]
    stelle = aufruf.index("--schicht")
    del aufruf[stelle:stelle + 2]
    methode = "fuehre_probe" if erzeuger is fuehrungsprobe else "fuehre_suite"
    monkeypatch.setattr(erzeuger, methode, lambda _args: (0, kaputt))
    assert pruefer(kaputt, fall, REPO_ROOT)
