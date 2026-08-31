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


def test_das_bewegungskonto_beginnt_am_uebernahmestichtag(
    gefahrener_fall: Path,
):
    """In den Buechern des aufnehmenden Unternehmens beginnt der Vertrag
    am Uebernahmestichtag — nicht an seinem Vertragsbeginn.

    Zuvor lagen ALLE Buchungen davor: der Zugang auf dem Vertragsbeginn
    (2015/2016) und die Vorgeschichte als eigene Bewegungen (bis 2023).
    In den Buechern der PLV hat 2017 aber keine Beitragsfreistellung
    stattgefunden; der Vertrag war da noch gar nicht da. Was die
    abgebende Gesellschaft gebucht hat, steht in IHREM Journal.

    Die Vorgeschichte erklaert den Zustand und bleibt in der
    Statushistorie — dort traegt sie die Bewertung. Eine Bewegung des
    aufnehmenden Unternehmens ist sie nicht.
    """
    import pandas as pd

    from rechner_pipeline.bestand.parquet_io import read_portfolio
    from rechner_pipeline.models.bestand import (
        LEDGER_NAMES,
        STATUS_HISTORIE_NAMES,
    )

    bestand = gefahrener_fall / "abgeleitet" / "bestand"
    ledger = read_portfolio(bestand / "ledger.parquet",
                            expected_columns=LEDGER_NAMES)
    stichtag = pd.Timestamp(STICHTAG_1)

    assert (pd.to_datetime(ledger["status_date"]) >= stichtag).all(), (
        "Buchungen vor dem Uebernahmestichtag: "
        + str(sorted(set(
            str(d)[:10] for d in ledger["status_date"]
            if pd.Timestamp(d) < stichtag))[:5]))
    assert set(ledger["ereignis"]) == {"ZUG"}, (
        "die Vorgeschichte gehoert nicht ins Journal des aufnehmenden "
        "Unternehmens")
    assert set(ledger["betrag_herkunft"]) == {"geliefert"}

    # Die Statushistorie fuehrt sie sehr wohl: Sie beschreibt den
    # Vertrag, und ohne sie waere sein Zustand am Stichtag unbestimmt.
    historie = read_portfolio(bestand / "historie.parquet",
                              expected_columns=STATUS_HISTORIE_NAMES)
    assert "PEX" in set(historie["status_code"])
    assert (pd.to_datetime(historie["status_date"]) < stichtag).any(), (
        "die Vorgeschichte liegt vor dem Stichtag — genau das ist ihr Sinn")


def test_die_merkmale_stehen_in_einer_nebentabelle(gefahrener_fall: Path):
    """Die Tarifzelle je Vertrag — als eigene Tabelle, nicht als
    Stammspalten.

    Die uebernommene Generation fuehrt sechs Zellen ueber zwei
    Dimensionen; der Stamm kannte sie nicht, also fielen sie bei der
    Uebernahme weg und der Bestandsbericht bewertete alles mit EINEM
    Parametersatz. Sie in den Stamm zu legen haette Spalten erzeugt, die
    fuer den Eigenbestand dauerhaft leer waeren — und ``NULL`` hiesse
    dort zweierlei, "trifft nicht zu" und "unbekannt".

    Deshalb eine Nebentabelle wie ``scheiben`` und ``historie``: Keine
    Datei heisst, der Bestand hat keine Zellen.
    """
    from rechner_pipeline.bestand.parquet_io import read_portfolio
    from rechner_pipeline.models.bestand import (
        MERKMALE_NAMES,
        STAMM_NAMES,
        validate_merkmale,
    )

    bestand = gefahrener_fall / "abgeleitet" / "bestand"
    merkmale = read_portfolio(bestand / "merkmale.parquet",
                              expected_columns=MERKMALE_NAMES)
    stamm = read_portfolio(bestand / "bestand.parquet",
                           expected_columns=STAMM_NAMES)

    assert set(merkmale["dimension"]) == {"status", "tarifart"}
    # Je Vertrag genau eine Auspraegung je Dimension.
    assert len(merkmale) == 2 * len(stamm)
    assert validate_merkmale(stamm, merkmale) == []

    # Das Vokabular ist kontrolliert — genau das unterscheidet die
    # Tabelle von einem Attribut-Beutel.
    erlaubt = {"status": {"raucher", "nichtraucher"},
               "tarifart": {"einzel", "kollektiv", "haus"}}
    assert validate_merkmale(stamm, merkmale, erlaubt) == []

    eng = {"status": {"nichtraucher"}, "tarifart": {"einzel"}}
    befunde = validate_merkmale(stamm, merkmale, eng)
    assert befunde and any("nicht" in b for b in befunde)

    # Und der Stamm bleibt frei davon.
    assert "status" not in STAMM_NAMES and "tarifart" not in STAMM_NAMES


def test_uebernahme_ohne_spez_laeuft_und_erzeugt_keine_merkmale(
    gefahrener_fall: Path, tmp_path: Path
):
    """Ohne ``--generation-spez`` gibt es keine Zellen -- und keinen Absturz.

    Die Merkmalstabelle liest ihre Dimensionen aus der Spez. Wer ohne sie
    uebernimmt, liefert einen Bestand ohne Zellen; das ist ein zulaessiger
    Fall (der Eigenbestand kennt keine), kein Sonderweg. Der Zweig war
    ungetestet, weil der e2e-Lauf die Spez immer mitgibt.
    """
    zeilen = (gefahrener_fall / "abgeleitet" / "transformation" / "zeilen.json")
    ziel = gefahrener_fall / "abgeleitet" / "ohne_spez"

    assert bestand_uebernehmen.main([
        "--fall", str(gefahrener_fall), "--zeilen", str(zeilen),
        "--tarif-generation", GENERATION, "--stichtag", STICHTAG_1,
        "--vorgeschichte", METADATEN,
        "--out-dir", str(ziel),
    ]) == 0

    assert (ziel / "bestand.parquet").exists()
    assert not (ziel / "merkmale.parquet").exists()


def test_der_lauf_liefert_die_grundlagen_zu_seinen_zellen(gefahrener_fall: Path):
    """Zuordnung UND Grundlagen -- sonst zeigt die Zuordnung ins Leere.

    ``merkmale.parquet`` sagt, welche Zelle ein Vertrag hat. Was in der
    Zelle gilt, muss die Bestand-Config sagen; ohne diesen Abschnitt
    bewertet der Bericht die sechs Zellen weiter mit einem Satz. Von Hand
    waeren es gut hundert Zahlen.

    Der Test prueft nicht nur, dass der Abschnitt da ist, sondern dass er
    ladbar und gueltig ist und dieselben sechs Zellen aufspannt.
    """
    from rechner_pipeline.bestand.config import load_config

    bestand = gefahrener_fall / "abgeleitet" / "bestand"
    abschnitt = (bestand / "generation-zellen.toml").read_text("utf-8")

    # Was alle Zellen teilen, steht oben; was sie unterscheidet, in ihnen.
    kopf, _, zellteil = abschnitt.partition("[[generation.zelle]]")
    assert "zins = 0.0125" in kopf, "gemeinsamer Zins gehoert zur Generation"
    assert "tafel" not in kopf, "die Sterbetafel unterscheidet die Zellen"
    assert abschnitt.count("[[generation.zelle]]") == 6
    assert zellteil.count("auspraegungen = {") == 6

    # Der Abschnitt muss eine gueltige Config ergeben. Kopf in den
    # Generationsblock, Zellen darunter -- genau wie im Kommentar steht.
    vorlage = (FIXTURE / "klv-tg2015.spez.json")
    assert vorlage.exists()
    toml = _zellen_config(abschnitt)
    pfad = gefahrener_fall / "abgeleitet" / "zellen-probe.toml"
    pfad.write_text(toml, encoding="utf-8")
    config = load_config(pfad)
    assert config.validate() == []

    gen = config.generationen[0]
    assert len(gen.zellen) == 6
    assert gen.dimensionen() == ("status", "tarifart")
    # Die Tafel kommt aus der Zelle, der Zins aus der Generation.
    assert gen.felder_fuer({"status": "raucher", "tarifart": "einzel"})["tafel"] \
        == "DAV2008_T_R_U70"
    assert gen.felder_fuer({"status": "nichtraucher", "tarifart": "haus"})["tafel"] \
        == "DAV2008_T_NR_U70"
    # Der Haustarif hat keinen Stornoabzug -- der Einzeltarif schon.
    assert gen.felder_fuer({"status": "raucher", "tarifart": "haus"})["stoab_satz"] == 0.0
    assert gen.felder_fuer({"status": "raucher", "tarifart": "einzel"})["stoab_satz"] > 0.0


def _zellen_config(abschnitt: str) -> str:
    """Den erzeugten Abschnitt in eine vollstaendige Config einbetten."""
    kopf, sep, rest = abschnitt.partition("[[generation.zelle]]")
    gemeinsam = "\n".join(
        z for z in kopf.splitlines() if z and not z.startswith("#")
    )
    return (
        '[meta]\nseed = 1\nbeschreibung = "Probe"\n'
        "referenzstichtag = 2026-01-01\n\n"
        f'[[generation]]\nname = "{GENERATION}"\nknoten = "{GENERATION}"\n'
        "gueltig_von = 2015-01-01\ngueltig_bis = 2016-12-31\n"
        f"sample_size = 0\nmax_endalter = 85\n{gemeinsam}\n\n"
        "[generation.verteilungen.entry_age]\n"
        'typ = "normal_trunc"\nmean = 40.0\nsd = 12.0\nmin = 18.0\n'
        "max = 62.0\nround = 0\n\n"
        '[generation.verteilungen.sex]\ntyp = "empirical_discrete"\n'
        'values = ["M", "F"]\nprobs = [0.5, 0.5]\n\n'
        '[generation.verteilungen.duration]\ntyp = "empirical_discrete"\n'
        "values = [25]\nprobs = [1.0]\n\n"
        '[generation.verteilungen.premium_duration]\n'
        'typ = "empirical_discrete"\nvalues = [25]\nprobs = [1.0]\n\n'
        '[generation.verteilungen.sum_insured]\ntyp = "lognormal"\n'
        "meanlog = 11.2\nsdlog = 0.5\nround = -3\n\n"
        '[generation.verteilungen.zahlweise]\ntyp = "empirical_discrete"\n'
        "values = [1]\nprobs = [1.0]\n\n" + sep + rest
    )
