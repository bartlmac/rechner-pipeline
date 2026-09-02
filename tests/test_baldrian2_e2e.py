"""Der zweite Baldrian-Lauf als Regressionstest: die Serien-Kette am Stueck.

Gesamtfixture des ZWEITEN Migrationslaufs (Lieferung baldrian-2, 834
Vertraege, Serien als Regelfall) — Muster und Begruendung wie
``tests/test_baldrian_e2e.py``: eingefroren sind die fachlichen
EINGABEN und die unabhaengig gelieferten ERWARTUNGSWERTE der abgebenden
Gesellschaft; die Laufartefakte entstehen je Test neu unter
``tmp_path``.

**Was der zweite Lauf zusaetzlich sichert.** Die Faehigkeiten, die der
Lauf erzwungen hat, laufen hier als Kette: Serien-Rekonstruktion aus
dem Dynamiksatz, Kandidaten-Bestimmung offener Herabsetzungsanteile
(Beitrags- und Anker-Gleichung), Anteils-Unerheblichkeit, dokumentierte
Arbeits-Lesarten je Police, Teilkuendigungs-Semantik, volle
Beitragsformel je Scheibe, Stornoabzug je Baustein, die
Jahrestags-Konvention des DK-Vergleichs und die Korrekturschicht bis in
das Migrationscontrolling. Der Schnitt (26 von 834) haelt alle
Verlaufsklassen der Vorgeschichte und die vier namentlich
entscheidenden Policen; erzeugt von
``tests/fixtures/baldrian2_e2e/schneide.py``.

Knoten: klv/tg2015
"""

from __future__ import annotations

import json
import shutil
from pathlib import Path

import pytest

from rechner_pipeline.fall import anlegen, registrieren
from rechner_pipeline.gates import (
    aktuartest_lauf,
    bestand_uebernehmen,
    bestand_validate,
    migrationssuite_lauf,
    transformation_anwenden,
    verankerung_belegen,
)

REPO_ROOT = Path(__file__).resolve().parents[1]
FIXTURE = REPO_ROOT / "tests" / "fixtures" / "baldrian2_e2e"

GENERATION = "klv/tg2015"
STICHTAG_1 = "2026-01-01"
STICHTAG_2 = "2027-01-01"
ABZUG_1 = "baldrian_bestandsabzug_2026-01-01.csv"
ABZUG_2 = "baldrian_bestandsabzug_2027-01-01.csv"
METADATEN = "baldrian_gevo_metadaten.csv"
PROTOKOLL = "baldrian_gevo_protokoll_2026.csv"
STICHPROBE = "baldrian_erwartungswerte_stichprobe.json"
ANKER = "baldrian_erwartungswerte_stichtag.json"

#: Die Laufparameter des abgenommenen zweiten Laufs — Eigenschaften der
#: LIEFERUNG, festgestellt und gezeichnet (A-Q1), nicht der Engine:
#: Teilkuendigungs-Semantik der Herabsetzung (Ziffer 6), volle
#: Beitragsformel je Erhoehungsbaustein (Ziffer 3), Stornoabzug je
#: Baustein (Ziffer 4), Deckungskapital zum Vertragsjahrestag
#: (Mitteilung 143 Abschnitt 6), Dynamiksatz 5 Prozent (Auskunft 1),
#: Kandidatenmenge der Herabsetzungsstufen (Auskunft 2) und die
#: dokumentierte Arbeits-Lesart f=0,60 der zwei unbestimmbaren Policen
#: (mit Falsifizierbarkeits-Auflage, Abschlussbericht Abschnitt 5).
ERHOEHUNGSSATZ = "0.05"
RED_VERFAHREN = "teilkuendigung"
KANDIDATEN = ("0.50", "0.60", "0.75")
RED_ANTEILE = ("7000396=0.60", "7000679=0.60")

ABNAHMEN = (
    ("A-M1", "baldrian_erwartungswerte_stichtag.json"),
    ("A-M2", "baldrian_erwartungswerte_verlauf.json"),
    ("A-M3", "baldrian_erwartungswerte_geschaeftsvorfaelle.json"),
)


def _lieferungs_flags() -> list[str]:
    flags = [
        "--erhoehungssatz", ERHOEHUNGSSATZ,
        "--red-verfahren", RED_VERFAHREN,
        "--scheiben-mit-gamma1",
    ]
    for k in KANDIDATEN:
        flags += ["--red-anteil-kandidat", k]
    for a in RED_ANTEILE:
        flags += ["--red-anteil", a]
    return flags


def _registriere_alles(fall: Path) -> None:
    for pfad in sorted(FIXTURE.glob("*")):
        if pfad.suffix in (".csv", ".json") and pfad.name not in (
                "policen.json", "transformation.spec.json",
                "klv-tg2015.spez.json"):
            registrieren(fall, pfad)


@pytest.fixture(scope="module")
def gefahrener_fall(tmp_path_factory) -> Path:
    """Die Lauf-2-Kette einmal je Testmodul fahren, dann darauf pruefen."""
    basis = tmp_path_factory.mktemp("baldrian2_e2e")
    fall = basis / "fall"
    anlegen(fall, scope="bestand")
    _registriere_alles(fall)

    spez_ziel = fall / "abgeleitet" / "spez"
    spez_ziel.mkdir(parents=True, exist_ok=True)
    shutil.copy2(FIXTURE / "klv-tg2015.spez.json",
                 spez_ziel / "klv-tg2015.spez.json")

    spec = fall / "abgeleitet" / "transformation" / "abzug.spec.json"
    spec.parent.mkdir(parents=True, exist_ok=True)
    shutil.copy2(FIXTURE / "transformation.spec.json", spec)

    zeilen = fall / "abgeleitet" / "transformation" / "zeilen.json"
    ergebnis = fall / "abgeleitet" / "transformation" / "ergebnis.json"
    assert transformation_anwenden.main([
        "--fall", str(fall), "--spec", str(spec),
        "--anwenden", "--zeilen", str(zeilen),
    ]) == 0, "Transformation der Quellzeilen"

    bestand = fall / "abgeleitet" / "bestand"
    assert bestand_uebernehmen.main([
        "--fall", str(fall), "--zeilen", str(zeilen),
        "--tarif-generation", GENERATION, "--stichtag", STICHTAG_1,
        "--vorgeschichte", METADATEN,
        "--generation-spez", GENERATION,
        "--out-dir", str(bestand),
    ]) == 0, "Uebernahme in das Zielmodell"

    assert transformation_anwenden.main([
        "--fall", str(fall), "--spec", str(spec),
        "--anwenden", "--zeilen", str(zeilen),
        "--ziel", str(bestand / "bestand.parquet"),
        "--ergebnis", str(ergebnis),
    ]) == 0, "Transformationsergebnis mit Zielbindung"

    diagnostics = fall / "abgeleitet" / "diagnostics"
    assert bestand_validate.main([
        "--portfolio", str(bestand / "bestand.parquet"),
        "--historie", str(bestand / "historie.parquet"),
        "--repo-root", str(REPO_ROOT),
        "--diagnostics-dir", str(diagnostics),
    ]).exit_code == 0, "Gate P-B1 auf dem uebernommenen Bestand"

    # Verankerung: Zustands-Welten rechnen, Residuen auf die
    # Korrekturschicht legen — die Suite liest daraus Schichtparameter
    # und Verankerungsmonate.
    assert verankerung_belegen.main([
        "--fall", str(fall), "--repo-root", str(REPO_ROOT),
        "--generation", GENERATION,
        "--formfunktion", "proportional_zur_basis",
        "--zeilen", str(zeilen), "--vorgeschichte", METADATEN,
        "--anker-erwartungswerte", ANKER,
    ] + _lieferungs_flags()) == 0, "Verankerung mit Schichtbeleg"
    schichten = fall / "abgeleitet" / "schichten" / "verankerung_schichten.json"
    assert schichten.is_file(), "Schichtbeleg der Verankerung"

    for abnahme, erwartung in ABNAHMEN:
        assert aktuartest_lauf.main([
            "--fall", str(fall), "--abnahme", abnahme,
            "--generation", GENERATION,
            "--erwartungswerte", erwartung, "--stichprobe", STICHPROBE,
            "--bestand", str(bestand / "bestand.parquet"),
            "--zeilen", str(zeilen), "--vorgeschichte", METADATEN,
            "--stoab-je-baustein",
            "--schicht", str(schichten),
            "--repo-root", str(REPO_ROOT),
        ] + _lieferungs_flags()) == 0, f"Aktuarieller Test {abnahme}"

    assert migrationssuite_lauf.main([
        "--fall", str(fall), "--generation", GENERATION,
        "--abzug-1", ABZUG_1, "--abzug-2", ABZUG_2,
        "--gevo-protokoll", PROTOKOLL,
        "--bestand", str(bestand / "bestand.parquet"),
        "--stichtag-1", STICHTAG_1, "--stichtag-2", STICHTAG_2,
        "--zeilen", str(zeilen), "--vorgeschichte", METADATEN,
        "--anker-erwartungswerte", ANKER,
        "--stoab-je-baustein",
        "--dk-stichtag", "jahrestag",
        "--schicht", str(schichten),
        "--repo-root", str(REPO_ROOT),
    ] + _lieferungs_flags()) == 0, "Migrationscontrolling"
    return fall


def _bericht(fall: Path, name: str) -> dict:
    return json.loads(
        (fall / "abgeleitet" / "berichte" / name).read_text(encoding="utf-8"))


def _policen() -> dict:
    return json.loads((FIXTURE / "policen.json").read_text(encoding="utf-8"))


def test_die_uebernahme_erzeugt_den_erwarteten_bestand(gefahrener_fall: Path):
    """Zeilenzahl, Tabellen — und die Serien als Scheiben-Nebentabelle."""
    from rechner_pipeline.bestand.parquet_io import read_portfolio

    bestand = gefahrener_fall / "abgeleitet" / "bestand"
    policen = _policen()["policen"]

    df = read_portfolio(bestand / "bestand.parquet")
    assert len(df) == len(policen)
    assert sorted(str(p) for p in df["police_id"]) == sorted(policen)
    assert set(df["tarif_generation"]) == {GENERATION}
    for tabelle in ("bestand", "historie", "ledger", "verankerung"):
        assert (bestand / f"{tabelle}.parquet").is_file()


def test_die_verankerung_traegt_jede_police_mit_kleinem_residuum(
    gefahrener_fall: Path,
):
    """Der Schichtbeleg des abgenommenen Laufs, am Schnitt reproduziert.

    Kernaussage des Laufs: Nach Klaerung aller Tarifwerks- und
    Konventionsfragen ist die Korrekturschicht praktisch leer (max.
    Einzelabweichung 0,02 EUR ueber 834 Vertraege). Der Schnitt muss
    dieselbe Groessenordnung zeigen — ein wachsendes Residuum hiesse,
    eine der Faehigkeiten des Laufs ist stillschweigend verlorengegangen.
    """
    beleg = json.loads(
        (gefahrener_fall / "abgeleitet" / "schichten"
         / "verankerung_schichten.json").read_text(encoding="utf-8"))
    assert beleg["befunde"] == []
    bilanz = beleg["summary"]
    policen = _policen()["policen"]
    assert bilanz["befunde"] == 0
    assert bilanz["getragen"] == bilanz["vertraege"] == len(policen)
    assert set(beleg["schichten"]) == set(policen)
    assert abs(bilanz["residuum_max_abs"]) <= 0.05, bilanz


@pytest.mark.parametrize("abnahme,erwartung", ABNAHMEN)
def test_die_aktuarielle_abnahme_trifft_die_gelieferten_werte(
    gefahrener_fall: Path, abnahme: str, erwartung: str,
):
    """Jeder gelieferte Erwartungswert wird getroffen — die Werte stammen
    von der abgebenden Gesellschaft und sind UNABHAENGIG von unserer
    Rechnung."""
    datei = ("aktuartest.json" if abnahme == "A-M1"
             else f"aktuartest-{abnahme}.json")
    bericht = _bericht(gefahrener_fall, datei)

    geliefert = json.loads((FIXTURE / erwartung).read_text(encoding="utf-8"))
    assert bericht["anzahl"] == len(geliefert["vertraege"])
    assert bericht["bestanden"] == bericht["anzahl"], (
        f"{abnahme}: {bericht['fehlgeschlagen']} Vertraege mit Befund — "
        + "; ".join(
            f"{v['police_id']}: {v['befunde']}"
            for v in bericht["vertraege"] if not v["bestanden"])[:600]
    )
    assert bericht["test_bestanden"] is True
    assert bericht["grenzbefunde"] == []
    assert bericht["mengenbefunde"] == []


def test_das_controlling_prueft_jeden_vertrag(gefahrener_fall: Path):
    """Vollbestand des Schnitts, beide Stichtage, ohne Prueflucke."""
    suite = _bericht(gefahrener_fall, "migrationssuite.json")
    policen = _policen()["policen"]

    assert suite["anzahl"] == len(policen)
    assert suite["red_verfahren"] == RED_VERFAHREN
    assert suite["bestanden"] == suite["anzahl"], (
        "; ".join(f"{v['police_id']}: {v['befunde']}"
                  for v in suite["vertraege"] if not v["bestanden"])[:600])
    assert suite["pruefluecken"] == []
    assert suite["vollstaendig_geprueft"] is True
    assert suite["suite_bestanden"] is True


def test_die_namentlichen_policen_des_laufs_bestehen(gefahrener_fall: Path):
    """Die vier entscheidenden Policen des Laufs, einzeln festgehalten.

    7000396/7000679 tragen die dokumentierte Arbeits-Lesart f=0,60
    (Falsifizierbarkeits-Auflage), 7000586 die Anker-Bestimmung,
    7000569 die Anteils-Unerheblichkeit. Faellt eine davon, ist genau
    eine der Datenluecken-Behandlungen des Laufs gebrochen.
    """
    suite = _bericht(gefahrener_fall, "migrationssuite.json")
    je_police = {str(v["police_id"]): v for v in suite["vertraege"]}
    for polnr in _policen()["pflicht"]:
        assert polnr in je_police, f"{polnr} fehlt im Controlling"
        assert je_police[polnr]["bestanden"], (
            f"{polnr}: {je_police[polnr]['befunde']}")


def test_der_schnitt_haelt_alle_verlaufsklassen(gefahrener_fall: Path):
    """Der Schnitt bleibt aussagekraeftig: jede Verlaufsklasse der
    Vorgeschichte mit mindestens zwei Vertraegen — sonst prueft das
    Fixture stillschweigend weniger Verzweigungen, als es behauptet."""
    klassen = _policen()["klassen"]
    erwartet = {"nur-erh", "nur-pex", "nur-red", "red-vor-erh",
                "serie+pex", "serie+red", "serie+red+pex"}
    assert set(klassen) == erwartet
    for name, mitglieder in klassen.items():
        assert len(mitglieder) >= 2, f"Klasse {name}: {mitglieder}"
