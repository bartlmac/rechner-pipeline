"""Pruefrunde G, Tageslauf — vorgefundener Alt-Abschluss (G06), Config-Wache am gefuehrten Tag (G07).

**G06.** Ein Abschluss fuer einen Stichtag, den diese Ablage ERSTMALS fuehrt,
steht in der Konvention, in der die Ablage jetzt schreibt (monatsgenau). Der
Tageslauf nahm eine vorab gelegte Datei der alten Gestalt (Jahreszeile, ohne
Spalte ``bewertungskonvention``) fuer einen solchen Monatsersten ohne Befund
an: Er rechnete in der Konvention DER DATEI nach, und jede in sich stimmige
Jahreszeilen-Datei war "deckungsgleich" — eine Konventionsnaht in der
Monatsreihe, die nirgends gekennzeichnet war. Jetzt ist eine solche Datei ein
Befund mit Exit ungleich 0, bevor der Lauf etwas veroeffentlicht; die Naht
benennt ``models.bestand.konventionsbruch`` (bis dahin ohne Aufrufer).
Nachbarfaelle: fehlende Spalte, unbekannte Konvention, gemischte Datei.
Positivkontrolle: eine vorgefundene Datei in der heutigen Konvention (der
Wiederanlauf nach einem gescheiterten Publish, T24-01) wird nachgerechnet und
angenommen; aeltere, im Protokoll bezeugte Abschluesse bleiben, wie sie sind.

**G07.** Die Config-Wache laeuft vor dem No-op des gefuehrten Tages: Mit
geaenderter Config endet ein erneuter Lauf desselben Tages mit Exit 2 und einer
roten Protokollzeile (auch zweimal hintereinander); mit der Config, mit der
das Protokoll gerechnet hat, ist er wieder ein No-op ohne Zeile, und der
naechste Tag laeuft gruen.

Knoten: system/betrieb
"""

from __future__ import annotations

import datetime as dt
import shutil
from pathlib import Path

import pandas as pd
import pytest

from rechner_pipeline.bestand.abschluss import _rechne, abschluss_pfad, lies_abschluss
from rechner_pipeline.bestand.config import load_config
from rechner_pipeline.bestand.parquet_io import read_portfolio, write_portfolio
from rechner_pipeline.betrieb import tageslauf as tl
from rechner_pipeline.betrieb.tageslauf import (
    EXIT_OK,
    EXIT_USAGE,
    Ablage,
    gefuehrter_tag,
    lies_protokoll,
    tageslauf,
)
from rechner_pipeline.models.bestand import (
    ABSCHLUSS_NAMES_VOR_UMSTELLUNG,
    KONVENTION_JAHRESZEILE,
    KONVENTION_MONATSGENAU,
)
from tests.freigabe_testschluessel import betriebsargs
from tests.test_betrieb_tageslauf import _ablage

# Spaet im Jahr: Im Februar des ersten Betriebsjahres decken sich die beiden
# Fassungen noch (gemessen: kein Vertrag verschieden), im November nicht.
VORHER = dt.date(2026, 10, 31)
STICHTAG = dt.date(2026, 11, 1)
HEUTE = dt.date(2026, 11, 3)


@pytest.fixture(scope="module")
def welt(tmp_path_factory):
    """Zwilling Z (ungestoert bis HEUTE: der echte Abschluss zum STICHTAG) und
    eine Vorlage V (bis VORHER gefuehrt), die jeder Test kopiert."""
    basis = tmp_path_factory.mktemp("g06")
    vorlage = _ablage(basis / "vorlage")
    assert tageslauf(vorlage, VORHER)[0] == EXIT_OK
    zwilling = Ablage(basis / "zwilling")
    shutil.copytree(vorlage.wurzel, zwilling.wurzel, symlinks=True)
    assert tageslauf(zwilling, HEUTE)[0] == EXIT_OK
    echt, konvention = lies_abschluss(abschluss_pfad(zwilling.abschluesse, STICHTAG))
    assert konvention.name == KONVENTION_MONATSGENAU and len(echt) > 0
    # Die Jahreszeilen-Fassung DESSELBEN Stichtags aus dem Stand des Zwillings,
    # in der alten Gestalt (ohne Spalte) — in sich stimmig.
    cfg = load_config(zwilling.config_pfad)
    stand = zwilling.stand.resolve()
    tabellen = {rolle: read_portfolio(stand / datei)
                for rolle, datei in (("portfolio", "bestand_gesamt.parquet"),
                                     ("historie", "historie.parquet"),
                                     ("ledger", "ledger.parquet"),
                                     ("scheiben", "scheiben.parquet"),
                                     ("reduktionen", "reduktionen.parquet"),
                                     ("merkmale", "merkmale.parquet"),
                                     ("schichten", "schichten.parquet"),
                                     ("verankerung", "verankerung.parquet"))
                if (stand / datei).is_file()}
    sicht = tl._stichtagssicht(tabellen, cfg, STICHTAG, cfg.tagesbetrieb.betriebsbeginn)
    alt = _rechne(sicht["portfolio"], sicht["historie"], cfg, STICHTAG, sicht["scheiben"],
                  sicht.get("merkmale"), sicht.get("schichten"), sicht.get("verankerung"),
                  sicht.get("reduktionen"), konvention=KONVENTION_JAHRESZEILE)
    alt = alt[list(ABSCHLUSS_NAMES_VOR_UMSTELLUNG)]
    # Vorbedingung: Die beiden Fassungen sind verschieden (sonst blind).
    verschieden = (echt.set_index("police_id")["deckungskapital"]
                   - alt.set_index("police_id")["deckungskapital"]).abs() > 0.005
    assert verschieden.any()
    return vorlage, zwilling, echt, alt


def _ablage_mit(welt, tmp_path, datei: pd.DataFrame | bytes | None) -> Ablage:
    vorlage = welt[0]
    ablage = Ablage(tmp_path / "m")
    shutil.copytree(vorlage.wurzel, ablage.wurzel, symlinks=True)
    if datei is not None:
        ziel = abschluss_pfad(ablage.abschluesse, STICHTAG)
        if isinstance(datei, bytes):
            ziel.write_bytes(datei)
        else:
            write_portfolio(datei, ziel)
    return ablage


def _varianten(welt):
    _, _, echt, alt = welt
    unbekannt = echt.copy()
    unbekannt["bewertungskonvention"] = "treppe"
    gemischt = echt.copy()
    gemischt.loc[gemischt.index[0], "bewertungskonvention"] = KONVENTION_JAHRESZEILE
    umetikettiert = echt[list(ABSCHLUSS_NAMES_VOR_UMSTELLUNG)]
    jahreszeile_mit_spalte = alt.copy()
    jahreszeile_mit_spalte["bewertungskonvention"] = KONVENTION_JAHRESZEILE
    return {
        "jahreszeile_alte_gestalt": alt,
        "jahreszeile_mit_spalte": jahreszeile_mit_spalte[list(echt.columns)],
        "monatsgenau_ohne_spalte": umetikettiert,
        "unbekannte_konvention": unbekannt,
        "gemischte_datei": gemischt,
    }


@pytest.mark.parametrize("variante", [
    "jahreszeile_alte_gestalt", "jahreszeile_mit_spalte", "monatsgenau_ohne_spalte",
    "unbekannte_konvention", "gemischte_datei"])
def test_ein_vorgefundener_abschluss_fremder_konvention_ist_ein_befund(welt, tmp_path, variante):
    """Auf eab5a57 rot: Exit 0, ``neu False, nachgerechnet True`` (fuer die
    in sich stimmige Jahreszeile ohne Befund). Soll: Exit ungleich 0, nichts
    uebernommen, die Datei bleibt (festgeschrieben wird nie ueberschrieben),
    die Protokollzeile nennt den Konventionsbruch bzw. die unbestimmbare
    Konvention, und der gestrige Tag bleibt der gefuehrte."""
    ablage = _ablage_mit(welt, tmp_path, _varianten(welt)[variante])
    datei = abschluss_pfad(ablage.abschluesse, STICHTAG)
    vorher = datei.read_bytes()
    code, zeile = tageslauf(ablage, HEUTE)
    assert code != EXIT_OK, zeile
    assert zeile["uebernommen"] is False
    assert "erstmals" in zeile["fehler"] and "Ausweg" in zeile["fehler"], zeile["fehler"]
    if variante in ("jahreszeile_alte_gestalt", "jahreszeile_mit_spalte"):
        assert "Konventionsbruch" in zeile["fehler"]
    assert datei.read_bytes() == vorher
    assert gefuehrter_tag(ablage) == VORHER
    # Nichts veroeffentlicht: kein Publish-Marker liegt (der Befund faellt
    # vor dem ersten irreversiblen Schritt).
    assert not ablage.publish_marker.exists()


def test_positivkontrolle_die_heutige_konvention_wird_nachgerechnet_und_angenommen(welt, tmp_path):
    """Der Wiederanlauf: Eine vorgefundene Datei in der heutigen Konvention
    (dieselben Bytes, die der ungestoerte Lauf schreibt) wird nachgerechnet,
    angenommen und ohne Befund belegt."""
    zwilling = welt[1]
    ablage = _ablage_mit(welt, tmp_path,
                         abschluss_pfad(zwilling.abschluesse, STICHTAG).read_bytes())
    code, zeile = tageslauf(ablage, HEUTE)
    assert code == EXIT_OK, zeile.get("fehler")
    eintrag = [a for a in zeile["abschluesse"] if a["stichtag"] == STICHTAG.isoformat()][0]
    assert eintrag["neu"] is False and eintrag["nachgerechnet"] is True
    assert "befunde" not in eintrag


def test_positivkontrolle_ohne_vorgefundene_datei(welt, tmp_path):
    ablage = _ablage_mit(welt, tmp_path, None)
    code, zeile = tageslauf(ablage, HEUTE)
    assert code == EXIT_OK
    _, konvention = lies_abschluss(abschluss_pfad(ablage.abschluesse, STICHTAG))
    assert konvention.name == KONVENTION_MONATSGENAU


def test_die_cli_meldet_den_befund_mit_exit_ungleich_null(welt, tmp_path, capsys):
    ablage = _ablage_mit(welt, tmp_path, _varianten(welt)["jahreszeile_alte_gestalt"])
    code = tl.main(["--stand", str(ablage.wurzel), "--heute", HEUTE.isoformat(), *betriebsargs()])
    assert code != EXIT_OK
    assert "Konventionsbruch" in capsys.readouterr().err


# --------------------------------------------------------------------------- #
# G07 — Config-Wache am bereits gefuehrten Tag
# --------------------------------------------------------------------------- #


def test_die_config_wache_greift_auch_am_gefuehrten_tag(tmp_path, capsys):
    """Auf eab5a57 rot: Exit 0 "bereits gefuehrt", keine Zeile."""
    ablage = _ablage(tmp_path / "plv")
    assert tageslauf(ablage, VORHER)[0] == EXIT_OK
    alt = ablage.config_pfad.read_bytes()
    manifest = (ablage.stand / "laufmanifest.json").read_bytes()
    journal = ablage.tagesjournal_pfad.read_bytes()
    zeilen_vorher = len(lies_protokoll(ablage.protokoll_pfad))

    ablage.config_pfad.write_bytes(alt + b"# nachgezogen\n")
    code, zeile = tageslauf(ablage, VORHER)
    assert code == EXIT_USAGE
    assert zeile["uebernommen"] is False and zeile["heute"] == VORHER.isoformat()
    assert "Config" in zeile["fehler"] and "neuaufsetzen" in zeile["fehler"]
    zeilen = lies_protokoll(ablage.protokoll_pfad)
    assert len(zeilen) == zeilen_vorher + 1 and zeilen[-1]["uebernommen"] is False
    # Ueber die CLI ein zweites Mal: wieder rot, wieder eine Zeile, und das
    # Protokoll bleibt lesbar und gezeichnet.
    assert tl.main(["--stand", str(ablage.wurzel), "--heute", VORHER.isoformat(),
                    *betriebsargs()]) == EXIT_USAGE
    assert "Config" in capsys.readouterr().err
    assert len(lies_protokoll(ablage.protokoll_pfad)) == zeilen_vorher + 2
    assert gefuehrter_tag(ablage) == VORHER
    assert (ablage.stand / "laufmanifest.json").read_bytes() == manifest
    assert ablage.tagesjournal_pfad.read_bytes() == journal

    # Zurueckgesetzt: wieder ein No-op ohne Zeile, und der naechste Tag laeuft
    # gruen — die roten Zeilen desselben Tages stoeren die Kette nicht.
    ablage.config_pfad.write_bytes(alt)
    code, zeile = tageslauf(ablage, VORHER)
    assert code == EXIT_OK and zeile == {"heute": VORHER.isoformat(), "bereits_gefuehrt": True}
    assert len(lies_protokoll(ablage.protokoll_pfad)) == zeilen_vorher + 2
    code, zeile = tageslauf(ablage, HEUTE)
    assert code == EXIT_OK and zeile["gefuehrt_vorher"] == VORHER.isoformat()
    assert gefuehrter_tag(ablage) == HEUTE
