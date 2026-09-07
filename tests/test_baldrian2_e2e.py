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

from rechner_pipeline.bestand import cli_fortschreibung
from rechner_pipeline.fall import anlegen, registrieren
from rechner_pipeline.gates import (
    aktuartest_lauf,
    bestand_uebernehmen,
    bestand_validate,
    migrationssuite_lauf,
    transformation_anwenden,
    verankerung_belegen,
)
from tests.e2e_fixture import zellen_config

REPO_ROOT = Path(__file__).resolve().parents[1]
FIXTURE = REPO_ROOT / "tests" / "fixtures" / "baldrian2_e2e"

GENERATION = "klv/tg2015"
# Wert der Stammspalte tarif_generation (Name der Generation in der
# PLV-Config) — nicht der Ontologie-Knoten; so lief auch der echte Lauf 2.
TARIF_GENERATION = "TG2015"
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
    # Freischaltung (Schritt 3): Die Uebernahme rechnet den Anfangszustand
    # mit DENSELBEN Lieferungs-Schaltern wie die Pruefstrecke und schreibt
    # ihn in die Tabellen — Grundsumme im Stamm, Alt-Erhoehungen als
    # Scheiben, Ursprungssumme der beitragsfreien Vertraege.
    assert bestand_uebernehmen.main([
        "--fall", str(fall), "--zeilen", str(zeilen),
        "--tarif-generation", TARIF_GENERATION, "--stichtag", STICHTAG_1,
        "--vorgeschichte", METADATEN,
        "--generation-spez", GENERATION,
        "--anfangszustand", "materialisieren",
        "--anker-erwartungswerte", ANKER,
        "--stoab-je-baustein",
        "--out-dir", str(bestand),
    ] + _lieferungs_flags()) == 0, "Uebernahme in das Zielmodell"

    assert transformation_anwenden.main([
        "--fall", str(fall), "--spec", str(spec),
        "--anwenden", "--zeilen", str(zeilen),
        "--ziel", str(bestand / "bestand.parquet"),
        "--ergebnis", str(ergebnis),
    ]) == 0, "Transformationsergebnis mit Zielbindung"

    diagnostics = fall / "abgeleitet" / "diagnostics"
    # Vollprofil (Review T22-01): Journal, Ledger, Merkmale (Tarifzellen),
    # die PLV-Config mit der uebernommenen Generation und der Horizont —
    # nur so prueft P-B1 Bewegungs-Identitaet, Ledger-Semantik und die
    # Kern-Herleitung jeder Buchung, die A-M4 im Bestands-Scope verlangt.
    # Die Config der Kern-Herleitung ist die dieses Falls (zellen_config):
    # Der Zellen-Abschnitt der Uebernahme traegt die Grundlagen, aus denen
    # sie gebucht hat. Die PLV-Config des Repos gehoert zum ECHTEN zweiten
    # Lauf; diese Fixture ist eine reduzierte Scheibe mit eigener Spez.
    config_pfad = fall / "abgeleitet" / "bestand-config.toml"
    config_pfad.write_text(
        zellen_config((bestand / "generation-zellen.toml").read_text("utf-8"),
                      name=TARIF_GENERATION, knoten=GENERATION),
        encoding="utf-8")
    pb1 = bestand_validate.main([
        "--portfolio", str(bestand / "bestand.parquet"),
        "--historie", str(bestand / "historie.parquet"),
        "--ledger", str(bestand / "ledger.parquet"),
        "--scheiben", str(bestand / "scheiben.parquet"),
        "--merkmale", str(bestand / "merkmale.parquet"),
        "--config", str(config_pfad),
        "--bis", STICHTAG_1,
        "--repo-root", str(REPO_ROOT),
        "--diagnostics-dir", str(diagnostics),
    ])
    assert pb1.exit_code == 0, ("Gate P-B1 auf dem uebernommenen Bestand", pb1.errors)

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
    assert (bestand / "schichten.parquet").is_file(), (
        "die Schicht als Vertragsattribut des Bestands (Freischaltung, Schritt 5)")

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

    # Freischaltung (Schritt 4 und 5): Der uebernommene Bestand wird mit
    # der Config des Falls fortgeschrieben — auf seinen Bausteinen, mit
    # seinem Tarifwerk und seiner Korrekturschicht — und P-B1 prueft das
    # Vollprofil des Laufs, Schicht und Verankerung eingeschlossen.
    nach = fall / "abgeleitet" / "bestand-nach"
    assert cli_fortschreibung.main([
        "--config", str(config_pfad), "--bis", STICHTAG_2,
        "--uebernahme", str(bestand), "--out-dir", str(nach),
    ]) == 0, "Fortschreibung des uebernommenen Bestands"
    pb1_nach = bestand_validate.main([
        "--portfolio", str(nach / "bestand_gesamt.parquet"),
        "--historie", str(nach / "historie.parquet"),
        "--ledger", str(nach / "ledger.parquet"),
        "--scheiben", str(nach / "scheiben.parquet"),
        "--merkmale", str(nach / "merkmale.parquet"),
        "--schichten", str(nach / "schichten.parquet"),
        "--verankerung", str(nach / "verankerung.parquet"),
        "--config", str(config_pfad),
        "--bis", STICHTAG_2,
        "--manifest", str(nach / "laufmanifest.json"),
        "--repo-root", str(REPO_ROOT),
        "--diagnostics-dir", str(fall / "abgeleitet" / "diagnostics-nach"),
    ])
    assert pb1_nach.exit_code == 0, ("Gate P-B1 auf dem fortgeschriebenen Bestand",
                                     pb1_nach.errors)
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
    assert set(df["tarif_generation"]) == {TARIF_GENERATION}
    for tabelle in ("bestand", "historie", "ledger", "verankerung", "scheiben"):
        assert (bestand / f"{tabelle}.parquet").is_file()


def test_die_uebernahme_materialisiert_den_anfangszustand_der_pruefstrecke(
    gefahrener_fall: Path,
):
    """Freischaltung, Schritt 3: Was die Abnahmen rechnen, steht in den
    Tabellen — nicht nur im Pruefauftrag.

    Die Alt-Erhoehungen jeder Serien-Police sind Scheiben mit dem gamma1
    ihrer Zelle (volle Beitragsformel, Ziffer 3 der Lieferung); der Stamm
    traegt die Grundsumme, der Zugang die Gesamtsumme; die beitragsfrei
    gelieferten Vertraege buchen ihre GELIEFERTE beitragsfreie Summe um,
    nicht eine zweite Umwandlung davon; der Beleg nennt Modus und Schalter.
    Vorher: Gesamtsumme als ein Vertrag ab Beginn, keine Scheiben,
    beitragsfreier Bestand um den Umwandlungsfaktor zu klein.
    """
    import csv

    from rechner_pipeline.bestand.parquet_io import read_portfolio
    from rechner_pipeline.models.bestand import SCHEIBEN_NAMES, validate_scheiben

    bestand = gefahrener_fall / "abgeleitet" / "bestand"
    klassen = _policen()["klassen"]
    stamm = read_portfolio(bestand / "bestand.parquet")
    ledger = read_portfolio(bestand / "ledger.parquet")
    scheiben = read_portfolio(bestand / "scheiben.parquet",
                              expected_columns=SCHEIBEN_NAMES)
    zeilen = {
        int(z["police_id"]): z for z in json.loads(
            (gefahrener_fall / "abgeleitet" / "transformation" / "zeilen.json")
            .read_text(encoding="utf-8"))
    }
    vorgeschichte = {}
    with (FIXTURE / METADATEN).open(encoding="utf-8") as datei:
        for z in csv.DictReader(datei, delimiter=";"):
            vorgeschichte.setdefault(int(z["POLNR"]), []).append(z["GEVO"])

    # Scheiben: jede Serie ohne terminale Beitragsfreistellung ist als
    # Bausteine im Bestand; PEX-Serien kollabieren (Ein-Punkt-Inversion).
    mit_scheiben = set(int(p) for p in scheiben["police_id"])
    erwartet = {
        pid for pid, arten in vorgeschichte.items()
        if "ERH" in arten and "PEX" not in arten
    }
    assert mit_scheiben == erwartet, (sorted(mit_scheiben), sorted(erwartet))
    assert validate_scheiben(stamm, scheiben) == []
    assert (scheiben["gamma1"] > 0.0).all(), "volle Beitragsformel je Baustein"
    haupt = stamm.set_index("police_id")
    zug = ledger[ledger["ereignis"] == "ZUG"].set_index("police_id")["betrag"]
    for pid in sorted(mit_scheiben):
        eigene = scheiben[scheiben["police_id"] == pid]
        gesamt = float(haupt.loc[pid, "sum_insured"]) + float(eigene["sum_insured"].sum())
        assert abs(gesamt - float(zeilen[pid]["sum_insured"])) <= 0.05, pid
        assert abs(float(zug.loc[pid]) - gesamt) <= 0.005, pid
        assert float(haupt.loc[pid, "sum_insured"]) < float(zeilen[pid]["sum_insured"])
        assert list(eigene["scheiben_id"]) == list(range(1, len(eigene) + 1))
    # Beitragsfrei geliefert: Umbuchung = gelieferte Summe, Stamm = Ursprung.
    pex = ledger[ledger["ereignis"] == "PEX"].set_index("police_id")["betrag"]
    assert set(int(p) for p in pex.index) == {
        pid for pid, arten in vorgeschichte.items() if "PEX" in arten}
    for pid, betrag in pex.items():
        assert abs(float(betrag) - float(zeilen[int(pid)]["sum_insured"])) <= 0.005
        assert float(haupt.loc[pid, "sum_insured"]) > float(betrag)
        assert abs(float(zug.loc[pid]) - float(haupt.loc[pid, "sum_insured"])) <= 0.005
    # Der Beleg der Uebernahme.
    beleg = json.loads((bestand / "uebernahme.json").read_text(encoding="utf-8"))
    assert beleg["anfangszustand"] == "materialisieren"
    assert beleg["tarifwerk"] == {
        "scheiben_mit_gamma1": True, "stoab_je_baustein": True,
        "red_verfahren": RED_VERFAHREN,
    }
    assert beleg["mit_scheiben"] == len(mit_scheiben)
    assert beleg["scheiben"] == len(scheiben)
    assert beleg["beitragsfrei"] == len(pex)
    assert beleg["ohne_anfangszustand"] == [] and beleg["nicht_freigeschaltet"] == []
    # Und der Config-Abschnitt traegt die Schalter, die die Fuehrung liest.
    abschnitt = (bestand / "generation-zellen.toml").read_text(encoding="utf-8")
    for zeile in ("scheiben_mit_gamma1 = true", "stoab_je_baustein = true",
                  f'red_verfahren = "{RED_VERFAHREN}"'):
        assert zeile in abschnitt, zeile


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
