"""Der Baldrian-Lauf als Regressionstest: die Migrationskette am Stueck.

Dies ist das Gesamtfixture eines Fallverlaufs. Es friert die fachlichen
EINGABEN und die unabhaengig gelieferten ERWARTUNGSWERTE der abgebenden
Gesellschaft ein; die Laufartefakte entstehen je Test neu unter
``tmp_path``. Sonst waere ein gitignorierter Fall-Arbeitsbereich eine
versteckte Vorbedingung, und der Test bewiese nur, dass eine alte Datei
noch da ist.

**Warum das gebraucht wird.** Die Kette besteht aus Kommandos, die
einander ueber JSON-Artefakte fuettern. Kein Typsystem haelt diese
Uebergaenge; wer in einem Erzeuger einen Schluessel umbenennt, merkt es
erst im naechsten echten Lauf — also womoeglich Monate spaeter. Dieser
Test laesst die Kette bei jedem Suite-Lauf einmal wirklich rechnen.

**Was er prueft und was nicht.** Er prueft, dass die Kette laeuft und
dieselben Werte trifft wie im abgenommenen Lauf. Er prueft NICHT die
Verteilungsmasse der Abnahme — dafuer waere die Stichprobe zu klein. Er
ersetzt also die aktuarielle Abnahme nicht, er sichert den Rechenweg.

**Warum ein Schnitt.** 25 statt 500 Vertraege, aber alle vier
Historientypen und alle vorkommenden Vorfallarten: die Verzweigungen des
Rechenwegs, nicht seine Wiederholungen. Erzeugt von
``tests/fixtures/baldrian_e2e/schneide.py``.

Knoten: klv/tg2015
"""

from __future__ import annotations

import json
import shutil
from pathlib import Path

import pytest

from rechner_pipeline.fall import anlegen, registrieren
from rechner_pipeline.gates import (
    aktuartest,
    aktuartest_lauf,
    bestand_uebernehmen,
    bestand_validate,
    migrationssuite_lauf,
    transformation_anwenden,
)

REPO_ROOT = Path(__file__).resolve().parents[1]
FIXTURE = REPO_ROOT / "tests" / "fixtures" / "baldrian_e2e"

GENERATION = "klv/tg2015"
STICHTAG_1 = "2026-01-01"
STICHTAG_2 = "2027-01-01"
ABZUG_1 = "baldrian_bestandsabzug_2026-01-01.csv"
ABZUG_2 = "baldrian_bestandsabzug_2027-01-01.csv"
METADATEN = "baldrian_gevo_metadaten.csv"
PROTOKOLL = "baldrian_gevo_protokoll_2026.csv"
STICHPROBE = "baldrian_erwartungswerte_stichprobe.json"
#: Die registrierte Auskunft, dass der Rueckkaufswert herabgesetzter
#: Vertraege bei der abgebenden Gesellschaft keiner Regel folgt. Ohne
#: diesen Beleg wird die Groesse wertverglichen — und scheitert, weil es
#: den Vergleichsmassstab nicht gibt.
PLAUSIBILITAETSBELEG = "Aktuarielle_Notiz_Stornoabzug.docx"

#: Die Laufparameter des abgenommenen Laufs. Sie sind Eigenschaften des
#: QUELLSYSTEMS, nicht der Engine: Ein anderes abgebendes Unternehmen
#: rechnet die Absetzung anders und erhoeht mit einem anderen Satz.
ERHOEHUNGSSATZ = "0.05"
RED_VERFAHREN = "mit_abzug"

ABNAHMEN = (
    ("A-M1", "baldrian_erwartungswerte_stichtag.json"),
    ("A-M2", "baldrian_erwartungswerte_verlauf.json"),
    ("A-M3", "baldrian_erwartungswerte_geschaeftsvorfaelle.json"),
)


def _registriere_alles(fall: Path) -> None:
    for pfad in sorted(FIXTURE.glob("*")):
        if pfad.suffix in (".csv", ".json", ".docx") and pfad.name not in (
                "policen.json", "transformation.spec.json",
                "klv-tg2015.spez.json"):
            registrieren(fall, pfad)


@pytest.fixture(scope="module")
def gefahrener_fall(tmp_path_factory) -> Path:
    """Die Kette einmal je Testmodul fahren, dann darauf pruefen.

    Modulweit statt je Test: Der Lauf ist deterministisch, und ihn fuenfmal
    zu wiederholen kostete Zeit ohne Erkenntnis.
    """
    basis = tmp_path_factory.mktemp("baldrian_e2e")
    fall = basis / "fall"
    anlegen(fall, scope="bestand")
    _registriere_alles(fall)

    # Parametrierung und Mapping sind eingefroren: Der Test prueft die
    # Migration, nicht noch einmal die Quellenauswertung.
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

    # Zweiter Lauf der Transformation: Erst jetzt gibt es den Bestand, auf
    # den die Ergebnisbindung zeigt.
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

    for abnahme, erwartung in ABNAHMEN:
        assert aktuartest_lauf.main([
            "--fall", str(fall), "--abnahme", abnahme,
            "--generation", GENERATION,
            "--erwartungswerte", erwartung, "--stichprobe", STICHPROBE,
            "--bestand", str(bestand / "bestand.parquet"),
            "--zeilen", str(zeilen), "--vorgeschichte", METADATEN,
            "--erhoehungssatz", ERHOEHUNGSSATZ,
            "--red-verfahren", RED_VERFAHREN,
            "--plausibilitaet-beleg", PLAUSIBILITAETSBELEG,
            "--plausibilitaet-groesse", "RKW",
            "--plausibilitaet-vorfallart", "RED",
            "--repo-root", str(REPO_ROOT),
        ]) == 0, f"Aktuarieller Test {abnahme}"

    assert migrationssuite_lauf.main([
        "--fall", str(fall), "--generation", GENERATION,
        "--abzug-1", ABZUG_1, "--abzug-2", ABZUG_2,
        "--gevo-protokoll", PROTOKOLL,
        "--bestand", str(bestand / "bestand.parquet"),
        "--stichtag-1", STICHTAG_1, "--stichtag-2", STICHTAG_2,
        "--zeilen", str(zeilen), "--vorgeschichte", METADATEN,
        "--erhoehungssatz", ERHOEHUNGSSATZ,
        "--red-verfahren", RED_VERFAHREN,
        # Vier Absetzungen der Lieferung sind aus dem gelieferten Stand
        # nicht rueckrechenbar, weil ihre Beitragszahlung am Stichtag
        # endete. Fuer sie kalibriert der Lauf den Anteil aus einer
        # REGISTRIERTEN Ankerquelle.
        "--anker-erwartungswerte", "baldrian_erwartungswerte_stichtag.json",
        "--repo-root", str(REPO_ROOT),
    ]) == 0, "Migrationscontrolling"
    return fall


def _bericht(fall: Path, name: str) -> dict:
    return json.loads(
        (fall / "abgeleitet" / "berichte" / name).read_text(encoding="utf-8"))


def test_die_uebernahme_erzeugt_den_erwarteten_bestand(gefahrener_fall: Path):
    """Zeilenzahl und Tabellen des Zielmodells."""
    from rechner_pipeline.bestand.parquet_io import read_portfolio

    bestand = gefahrener_fall / "abgeleitet" / "bestand"
    policen = json.loads(
        (FIXTURE / "policen.json").read_text(encoding="utf-8"))["policen"]

    df = read_portfolio(bestand / "bestand.parquet")
    assert len(df) == len(policen)
    assert sorted(str(p) for p in df["police_id"]) == sorted(policen)
    assert set(df["tarif_generation"]) == {GENERATION}
    for tabelle in ("bestand", "historie", "ledger"):
        assert (bestand / f"{tabelle}.parquet").is_file()


@pytest.mark.parametrize("abnahme,erwartung", ABNAHMEN)
def test_die_aktuarielle_abnahme_trifft_die_gelieferten_werte(
    gefahrener_fall: Path, abnahme: str, erwartung: str,
):
    """Jeder Vertrag der Lieferung wird getroffen.

    Das ist der Kern des Fixtures: Die Erwartungswerte stammen von der
    abgebenden Gesellschaft und sind damit UNABHAENGIG von unserer
    Rechnung. Ein Test gegen selbst erzeugte Werte waere Selbstbestaetigung.
    """
    datei = "aktuartest.json" if abnahme == "A-M1" else f"aktuartest-{abnahme}.json"
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
    """Ueber beide Stichtage, ohne Prueflucke."""
    suite = _bericht(gefahrener_fall, "migrationssuite.json")
    policen = json.loads(
        (FIXTURE / "policen.json").read_text(encoding="utf-8"))["policen"]

    assert suite["anzahl"] == len(policen)
    assert suite["bestanden"] == suite["anzahl"], (
        "; ".join(f"{v['police_id']}: {v['befunde']}"
                  for v in suite["vertraege"] if not v["bestanden"])[:600])
    assert suite["pruefluecken"] == []
    assert suite["vollstaendig_geprueft"] is True
    assert suite["suite_bestanden"] is True


def test_das_datenmodell_der_darstellung_ist_vollstaendig(
    gefahrener_fall: Path,
):
    """Der Fallbericht liest, was die Kette produziert.

    Er ist Konsument und kein Vertragsgeber — genau deshalb kann eine
    Formaenderung in einem Erzeuger ihn treffen, ohne dass ein anderer
    Test es merkt. Hier faellt es auf.
    """
    import sys
    sys.path.insert(0, str(REPO_ROOT / "werkzeuge"))
    import falldaten  # noqa: E402

    modell = falldaten.sammle(gefahrener_fall, [ABZUG_1, ABZUG_2])
    fehlend = [l["gruppe"] for l in falldaten.luecken(modell)]
    # Zwei Luecken sind erwartet und benannt. Die ENTSCHEIDE fehlen, weil
    # der Test nicht zeichnet — das ist eine menschliche Handlung. Die
    # PARAMETRIERUNG fehlt, weil das Fixture die A-Box nicht mitfuehrt:
    # Es prueft die Migration ab dem Bestandsabzug, nicht noch einmal die
    # Quellenauswertung. Alles Uebrige muss die Kette liefern.
    assert fehlend == ["parameter", "kette"], (
        f"unerwartete Luecken: {fehlend}")
    assert modell["bestand"]["anzahl"] == 25
    assert modell["transformation"]["zeilen_quelle"] == 25
    assert modell["transformation"]["stumm_weggelassen"] == []


def test_das_bewegungskonto_trennt_beleg_von_eigenrechnung(
    gefahrener_fall: Path,
):
    """Im uebernommenen Bestand stehen zwei Arten von Betraegen
    nebeneinander, und sie sind nicht gleich viel wert.

    Die Zugangssumme steht im Abzug der abgebenden Gesellschaft. Die
    beitragsfreie Summe eines mitgebrachten PEX-Zustands steht dort NICHT
    — die Vorgeschichte fuehrt keine Betraege —, sie wird vom
    AUFNEHMENDEN Unternehmen konstruktiv gerechnet. Das ist richtig, aber
    es ist keine Buchung der Gegenseite. Ohne die Unterscheidung verloere
    das Bewegungskonto genau die Eigenschaft, fuer die man es fuehrt.
    """
    from rechner_pipeline.bestand.parquet_io import read_portfolio
    from rechner_pipeline.models.bestand import BETRAG_HERKUNFT, LEDGER_NAMES

    ledger = read_portfolio(
        gefahrener_fall / "abgeleitet" / "bestand" / "ledger.parquet",
        expected_columns=LEDGER_NAMES,
    )
    assert set(ledger["betrag_herkunft"]) <= set(BETRAG_HERKUNFT)

    zugang = ledger[ledger["ereignis"] == "ZUG"]
    assert len(zugang) > 0
    assert set(zugang["betrag_herkunft"]) == {"geliefert"}

    pex = ledger[ledger["ereignis"] == "PEX"]
    assert len(pex) > 0, "der Schnitt traegt beitragsfreie Vertraege"
    assert set(pex["betrag_herkunft"]) == {"gerechnet"}
