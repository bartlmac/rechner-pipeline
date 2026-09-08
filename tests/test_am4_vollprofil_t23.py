"""A-M4-Vollprofil: jede P-B1-Eingabe ist an den Fall gebunden, und ein
Zaehler, der eine Pruefung bezeugt, darf nicht null sein (Review T23-04,
T23-05; Block 3).

T23-04: A-M4 erzwang die Fallgrenze nur fuer die Portfolio-Rolle. Historie,
Bewegungskonto (ledger) und vor allem die Config — die Rechnungsgrundlagen
der Kern-Herleitung — durften von irgendwo kommen; der P-B1-Hash belegte
nur, WELCHE Bytes benutzt wurden, nicht ihre Herkunft. Jetzt gilt die
Fallgrenze fuer JEDE Rolle des Belegs (Klasse, nicht die eine Rolle).

T23-05: ``betraege_hergeleitet == 0`` bestand die Pruefung (nur der Typ
wurde geprueft), und die generische Schleife hielt jeden Zaehler nur auf
GLEICHHEIT mit der Nachrechnung: 0 == 0 war konsistent gruen. "Geprueft"
und "nie gelaufen" sahen im Beleg gleich aus. Jetzt gibt es einen Katalog
"Pflicht-positiv" (``PB1_PFLICHT_POSITIV``): ein solcher Zaehler, der
null ist, ist ein Befund — auch wenn Beleg und Nachrechnung sich einig
sind.

Knoten: system/bestand
"""

from __future__ import annotations

import json
import shutil
from pathlib import Path

import pytest

from rechner_pipeline.bestand import cli_fortschreibung
from rechner_pipeline.gates import abnahmebericht, bestand_validate
from tests.test_pk1_am4_beweisvertrag import pb1_vollprofil_argv

REPO_ROOT = Path(__file__).resolve().parents[1]
HORIZONT = "2020-01-01"


@pytest.fixture(scope="module")
def bestandsfall(tmp_path_factory) -> Path:
    """Ein Fortschreibungslauf, dessen Config IM Fall liegt (wie der echte
    Bestandsfall seit T22-01) — die Positivkontrolle fuer beide Klassen."""
    fall = tmp_path_factory.mktemp("fall")
    (fall / "abgeleitet").mkdir()
    config = fall / "abgeleitet" / "bestand-config.toml"
    shutil.copy(REPO_ROOT / "configs" / "bestand_klv.toml", config)
    assert cli_fortschreibung.main([
        "--config", str(config), "--bis", HORIZONT,
        "--out-dir", str(fall / "lauf"),
    ]) == 0
    return fall


def _kopie(fall: Path, tmp_path: Path) -> Path:
    ziel = tmp_path / "fall"
    shutil.copytree(fall, ziel)
    return ziel


def _pb1(fall: Path, argv: list, diag: Path):
    ergebnis = bestand_validate.main(argv + [
        "--repo-root", str(REPO_ROOT), "--diagnostics-dir", str(diag),
    ])
    assert ergebnis.exit_code == 0, ergebnis.errors
    ledger_pfad = diag / "bestand_validate.gate.json"
    eintrag = json.loads(ledger_pfad.read_text(encoding="utf-8"))
    suite = {
        "bestand_sha256": eintrag["summary"]["portfolio_sha256"],
        "anzahl": eintrag["summary"]["portfolio_zeilen"],
        "erwartete_anzahl": eintrag["summary"]["portfolio_zeilen"],
    }
    return ledger_pfad, eintrag, suite


def _b1(fall: Path, ledger_pfad: Path, eintrag: dict, suite: dict) -> list:
    return abnahmebericht._b1_fehler(
        ledger_pfad=ledger_pfad, fall=fall, repo_root=REPO_ROOT,
        suite=suite, erwartetes_system=eintrag["summary"]["system"],
    )


# --------------------------------------------------------------------------- #
# T23-04: die Fallgrenze gilt fuer JEDE Rolle
# --------------------------------------------------------------------------- #

def test_vollprofil_im_fall_ist_ein_am4_beleg(bestandsfall, tmp_path):
    fall = _kopie(bestandsfall, tmp_path)
    ledger_pfad, eintrag, suite = _pb1(
        fall, pb1_vollprofil_argv(fall / "lauf", fall / "abgeleitet" / "bestand-config.toml"),
        tmp_path / "diag",
    )
    assert _b1(fall, ledger_pfad, eintrag, suite) == []


@pytest.mark.parametrize("rolle, datei", [
    ("config", "abgeleitet/bestand-config.toml"),
    ("historie", "lauf/historie.parquet"),
    ("ledger", "lauf/ledger.parquet"),
])
def test_rolle_ausserhalb_des_falls_ist_kein_am4_beleg(bestandsfall, tmp_path, rolle, datei):
    """Vorher war nur das Portfolio gebunden — eine fremde Config oder ein
    fremdes Bewegungskonto konnte Rechnungsgrundlagen und Ledgerbetraege
    passend machen."""
    fall = _kopie(bestandsfall, tmp_path)
    aussen = tmp_path / "anderswo" / Path(datei).name
    aussen.parent.mkdir()
    shutil.copy(fall / datei, aussen)
    argv = pb1_vollprofil_argv(fall / "lauf", fall / "abgeleitet" / "bestand-config.toml")
    argv[argv.index(f"--{rolle}") + 1] = str(aussen)
    ledger_pfad, eintrag, suite = _pb1(fall, argv, tmp_path / "diag")
    fehler = _b1(fall, ledger_pfad, eintrag, suite)
    assert any(f"{rolle!r}" in f and "ausserhalb des Falls" in f for f in fehler), fehler


# --------------------------------------------------------------------------- #
# T23-05: ein bezeugender Zaehler darf nicht null sein
# --------------------------------------------------------------------------- #

def test_katalog_der_pflicht_positiven_zaehler_ist_benannt():
    assert {"betraege_hergeleitet", "portfolio_zeilen", "manifest_gebunden"} <= abnahmebericht.PB1_PFLICHT_POSITIV
    # Entscheid des Maintainers 2026-09-07: A-M4 verlangt im Bestands-Scope
    # ein volles Bewegungsjahr und Plausibilitaetsbaender — beide koennen
    # bei einem gueltigen Lauf null sein, sind aber Abnahmevoraussetzung.
    assert {"bewegungsjahre", "sanity_baender"} <= abnahmebericht.PB1_PFLICHT_POSITIV
    # Ein Bestand ohne Vorgeschichte oder Erhoehungen ist fachlich moeglich.
    assert not {"historie_zeilen", "scheiben_zeilen", "ledger_zeilen"} & abnahmebericht.PB1_PFLICHT_POSITIV
    # Jeder Pflichtzaehler hat eine benannte Ursache mit Ausweg.
    assert set(abnahmebericht.PB1_PFLICHT_POSITIV_URSACHE) == set(abnahmebericht.PB1_PFLICHT_POSITIV)


def test_am4_rechnet_die_manifestbindung_nach(bestandsfall, tmp_path):
    """Der Beleg traegt ein Manifest, also muss die Nachrechnung es auch
    binden — sonst bliebe manifest_gebunden unverglichen (adversarialer
    Review Block 3: der Zaehler war im Katalog, aber unerreichbar)."""
    fall = _kopie(bestandsfall, tmp_path)
    ledger_pfad, eintrag, suite = _pb1(
        fall, pb1_vollprofil_argv(fall / "lauf", fall / "abgeleitet" / "bestand-config.toml"),
        tmp_path / "diag",
    )
    assert isinstance(eintrag["summary"].get("manifest_gebunden"), int)
    assert eintrag["summary"]["manifest_gebunden"] > 0
    unversehrt = _b1(fall, ledger_pfad, eintrag, suite)
    assert unversehrt == [], unversehrt
    eintrag["summary"]["manifest_gebunden"] = 99
    ledger_pfad.write_text(json.dumps(eintrag, indent=2), encoding="utf-8")
    fehler = _b1(fall, ledger_pfad, eintrag, suite)
    assert any("manifest_gebunden" in f and "stimmt nicht" in f for f in fehler), fehler
    # Und die Bytes des Manifests sind an den Beleg gebunden.
    eintrag["summary"]["manifest_gebunden"] = unversehrt_wert = json.loads(
        Path(ledger_pfad).read_text(encoding="utf-8"))["summary"]["manifest_gebunden"]
    manifest_pfad = fall / "lauf" / "laufmanifest.json"
    manifest_pfad.write_bytes(manifest_pfad.read_bytes() + b"\n")
    fehler = _b1(fall, ledger_pfad, eintrag, suite)
    assert any("anderen SHA-256" in f for f in fehler), fehler


@pytest.mark.parametrize("zaehler", sorted(abnahmebericht.PB1_PFLICHT_POSITIV))
def test_nullzaehler_ist_kein_beleg_auch_wenn_beleg_und_nachrechnung_einig_sind(
    bestandsfall, tmp_path, monkeypatch, zaehler,
):
    """Der Reviewer-Fall verallgemeinert: Beleg UND Nachrechnung sagen 0 —
    konsistent, aber vakuos. Vorher gruen, jetzt ein Befund je Zaehler."""
    fall = _kopie(bestandsfall, tmp_path)
    ledger_pfad, eintrag, suite = _pb1(
        fall, pb1_vollprofil_argv(fall / "lauf", fall / "abgeleitet" / "bestand-config.toml"),
        tmp_path / "diag",
    )
    if zaehler not in eintrag["summary"]:
        pytest.skip(f"{zaehler} kommt in diesem Profil nicht vor")
    eintrag["summary"][zaehler] = 0
    ledger_pfad.write_text(json.dumps(eintrag, indent=2), encoding="utf-8")
    echt = abnahmebericht.lies_und_pruefe_pb1

    def _nachrechnung_einig(eingaben, **kwargs):
        tabellen, geprueft, errors, usage = echt(eingaben, **kwargs)
        # Der ECHTE Nachrechnungspfad muss den Zaehler liefern — sonst
        # bescheinigte dieser Test einem toten Katalogeintrag ein Gruen.
        assert zaehler in geprueft, (zaehler, sorted(geprueft))
        geprueft = dict(geprueft)
        geprueft[zaehler] = 0
        return tabellen, geprueft, errors, usage

    monkeypatch.setattr(abnahmebericht, "lies_und_pruefe_pb1", _nachrechnung_einig)
    fehler = _b1(fall, ledger_pfad, eintrag, suite)
    assert not any("stimmt nicht mit der erneuten" in f and zaehler in f for f in fehler), (
        "Vorbedingung: Beleg und Nachrechnung sind einig — der Befund muss aus der "
        "Positivschwelle kommen, nicht aus dem Gleichheitsvergleich"
    )
    assert any(zaehler in f and ("null" in f or " 0" in f) for f in fehler), fehler
    # Die Meldung nennt die Ursache, nicht nur den Zaehler.
    assert any(abnahmebericht.PB1_PFLICHT_POSITIV_URSACHE[zaehler][:40] in f for f in fehler), fehler


def test_reviewer_beispiel_betraege_hergeleitet_null(bestandsfall, tmp_path, monkeypatch):
    """Das woertliche Gegenbeispiel T23-05: kein Vollprofil ohne mindestens
    eine gegen den Kern hergeleitete Buchung."""
    fall = _kopie(bestandsfall, tmp_path)
    ledger_pfad, eintrag, suite = _pb1(
        fall, pb1_vollprofil_argv(fall / "lauf", fall / "abgeleitet" / "bestand-config.toml"),
        tmp_path / "diag",
    )
    assert eintrag["summary"]["betraege_hergeleitet"] > 0
    eintrag["summary"]["betraege_hergeleitet"] = 0
    ledger_pfad.write_text(json.dumps(eintrag, indent=2), encoding="utf-8")
    echt = abnahmebericht.lies_und_pruefe_pb1

    def _keine_buchung(eingaben, **kwargs):
        tabellen, geprueft, errors, usage = echt(eingaben, **kwargs)
        return tabellen, {**geprueft, "betraege_hergeleitet": 0}, errors, usage

    monkeypatch.setattr(abnahmebericht, "lies_und_pruefe_pb1", _keine_buchung)
    fehler = _b1(fall, ledger_pfad, eintrag, suite)
    assert any("betraege_hergeleitet" in f for f in fehler), fehler


# --------------------------------------------------------------------------- #
# N-01, fuenfter Aufrufer: der Abnahmebericht nimmt die Rollen der Engine
# --------------------------------------------------------------------------- #

def _mit_schicht(lauf: Path, police_id: int) -> None:
    """Korrekturschicht und Verankerung fuer EINE Police des Laufs — wie ein
    Freischaltungs-Fall sie neben den Lauf legt."""
    import pandas as pd
    from rechner_pipeline.bestand.parquet_io import write_portfolio
    from rechner_pipeline.models.bestand import (
        SCHICHTEN_NAMES, SCHICHTEN_SPALTEN, VERANKERUNG_NAMES, VERANKERUNG_SPALTEN,
    )

    schichten = pd.DataFrame([{
        "police_id": police_id, "schichttyp": "hist", "verankerungszustand": "aktiv",
        "verweildauer": 0, "rho": 0.02, "formfunktion": "konstant", "formparameter": "{}",
        "vererbend": "[]", "kohorte": "t_a", "in_ueberschuss": False, "in_zzr": False,
        "rumpfmonate": 0,
    }])[list(SCHICHTEN_NAMES)].astype(dict(SCHICHTEN_SPALTEN))
    verankerung = pd.DataFrame([{
        "police_id": police_id, "monate_ta": 24, "zustand_ta": "beitragspflichtig",
        "verweildauer_ta": 0, "dk_ta": 1.0,
    }])[list(VERANKERUNG_NAMES)].astype(dict(VERANKERUNG_SPALTEN))
    write_portfolio(schichten, lauf / "schichten.parquet")
    write_portfolio(verankerung, lauf / "verankerung.parquet")


def test_ein_beleg_mit_schicht_und_verankerung_ist_kein_ungueltiger_rollenblock(bestandsfall, tmp_path):
    """Der ehrliche Nach-Beleg eines Freischaltungs-Falls traegt acht Rollen.
    Die abgetippte Positivliste des Abnahmeberichts kannte zwei davon nicht
    und wies den Beleg als 'ungueltig' ab (Review T25-03, Testat 5ca0306).
    Mutationsprobe: erlaubte_rollen wieder als Literal ohne die beiden -> rot."""
    from rechner_pipeline.bestand.parquet_io import read_portfolio

    fall = _kopie(bestandsfall, tmp_path)
    lauf = fall / "lauf"
    stamm = read_portfolio(lauf / "bestand_gesamt.parquet")
    ledger = read_portfolio(lauf / "ledger.parquet")
    # Eine Police OHNE Storno: der Lauf hat seine Stornos ohne Schicht
    # gebucht, eine nachtraeglich angelegte Schicht widerlegte sie zu Recht.
    storniert = set(ledger.loc[ledger["ereignis"] == "STO", "police_id"])
    kandidaten = stamm[(stamm["duration"] >= 10) & ~stamm["police_id"].isin(storniert)]
    police = int(kandidaten["police_id"].iloc[0])
    _mit_schicht(lauf, police)
    argv = [a for a in pb1_vollprofil_argv(lauf, fall / "abgeleitet" / "bestand-config.toml")
            if not a.endswith("laufmanifest.json") and a != "--manifest"]
    argv += ["--schichten", str(lauf / "schichten.parquet"),
             "--verankerung", str(lauf / "verankerung.parquet")]
    ledger_pfad, eintrag, suite = _pb1(fall, argv, tmp_path / "diag")
    assert {"schichten", "verankerung"} <= set(eintrag["summary"]["eingangsrollen"])
    fehler = _b1(fall, ledger_pfad, eintrag, suite)          # kein Absturz
    assert not any("eingangsrollen" in f for f in fehler), fehler
    assert not any("Neupruefung" in f for f in fehler), fehler


def test_ein_ungueltiger_rollenblock_ist_ein_befund_kein_absturz(bestandsfall, tmp_path):
    """Testat 5ca0306, Paar A/B: mit leerem Rollenblock waren ``rollen`` und
    ``aktuelle_eingaben`` beide leer, die Nachrechnung lief an und brach mit
    KeyError 'portfolio' ab — A-M4 konnte den Beleg nicht einmal ablehnen."""
    fall = _kopie(bestandsfall, tmp_path)
    ledger_pfad, eintrag, suite = _pb1(
        fall, pb1_vollprofil_argv(fall / "lauf", fall / "abgeleitet" / "bestand-config.toml"),
        tmp_path / "diag",
    )
    assert "manifest" in eintrag["summary"]                     # der Absturzpfad braucht es
    eintrag["summary"]["eingangsrollen"]["fremd"] = "irgendwo/fremd.parquet"
    ledger_pfad.write_text(json.dumps(eintrag), encoding="utf-8")
    fehler = _b1(fall, ledger_pfad, eintrag, suite)
    assert any("eingangsrollen ist ungueltig" in f for f in fehler), fehler
