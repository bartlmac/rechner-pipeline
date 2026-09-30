"""Klasse: Bericht ohne Journal — Runde E.

Die Invariante: ``cli_report`` weist einen Aufruf nur mit ``--portfolio`` (und
``--config``) ab, sobald neben dem Stamm irgendeine Nebentabelle liegt oder
ausdruecklich genannt wird, die den gefuehrten Zustand veraendert — nicht nur
``reduktionen.parquet`` (Runde D, Fund 4). Ohne Ledger bewertet der Bericht
den Stamm, als haette sich nichts bewegt: Herabsetzungen ungekuerzt,
Erhoehungsscheiben und Korrekturschichten ueberlesen, Exit 0.

Die Menge: alle Rollen von ``bestand.manifest.ROLLEN_DATEIEN`` ausser dem
Portfolio (``NEBENTABELLEN`` plus historie/ledger/scheiben) — hergeleitet, nicht
abgetippt (``journal_pflichtige_rollen``). Die Ausnahmen stehen als Mengen im
Code, mit Grund: ``OHNE_JOURNAL_GELESEN`` (merkmale: der Bericht liest sie ueber
``--merkmale`` und verlangt sie, sobald Zellen im Spiel sind). Eine zweite
Ausnahme (schichten, verankerung neben dem Portfolio des Migrationszugangs)
gab es bis zur Nachbesserung der Runde E; sie griff in der echten
Verzeichnisform nie, weil ``bestand_uebernehmen`` ``historie.parquet`` und
``ledger.parquet`` immer daneben schreibt — sie ist gestrichen, und
``test_baldrian2_e2e`` misst die echte Form.

Drei Instrumente: Ratsche (statisch, ``==``, mit Positivkontrolle), Zaehltest
(je Rolle und je Weg — Nachbardatei, ausdrucksliches Flag — gemessen am
oeffentlichen CLI-Weg) und die Mutationsprobe je Rolle in den Docstrings.

Knoten: klv
"""

from __future__ import annotations

import inspect
from pathlib import Path

import pandas as pd
import pytest

from rechner_pipeline.bestand import cli_report
from rechner_pipeline.bestand import manifest
from rechner_pipeline.bestand.manifest import (
    ERZEUGER_MIGRATIONSZUGANG,
    NEBENTABELLEN,
    OHNE_JOURNAL_GELESEN,
    PORTFOLIO_JE_ERZEUGER,
    ROLLEN_DATEIEN,
    journal_pflichtige_rollen,
)
from rechner_pipeline.bestand.parquet_io import write_portfolio
from rechner_pipeline.models.bestand import MERKMALE_SPALTEN
from tests.test_bestand_uebernommen_fortschreiben import _stamm

GESAMT = "bestand_gesamt.parquet"
MIGRATION = PORTFOLIO_JE_ERZEUGER[ERZEUGER_MIGRATIONSZUGANG]
ROLLEN = [r for r in ROLLEN_DATEIEN if r != "portfolio"]

#: Die Erwartung, von Hand und unabhaengig von den Mengen im Code: Exit-Code
#: des Berichts mit der Rolle als NACHBARDATEI des Stamms (ohne Ledger), je
#: Portfolio-Name (gefuehrter Gesamtbestand, Migrationszugang). 2 = abgewiesen.
NEBEN = {
    "historie": {GESAMT: 2, MIGRATION: 2},
    "ledger": {GESAMT: 2, MIGRATION: 2},
    "scheiben": {GESAMT: 2, MIGRATION: 2},
    "reduktionen": {GESAMT: 2, MIGRATION: 2},
    "schichten": {GESAMT: 2, MIGRATION: 2},
    "verankerung": {GESAMT: 2, MIGRATION: 2},
    "merkmale": {GESAMT: 0, MIGRATION: 0},
}
#: Dasselbe fuer das AUSDRUECKLICHE Flag ``--<rolle>`` ohne ``--ledger``: Es
#: wird nie still ignoriert — nur ``--merkmale`` wird ohne Ledger gelesen.
FLAG = {
    "historie": 2, "ledger": 2, "scheiben": 2, "reduktionen": 2,
    "schichten": 2, "verankerung": 2, "merkmale": 0,
}


# --------------------------------------------------------------------------- #
# 1. Ratsche (statisch)
# --------------------------------------------------------------------------- #


def _ungeklaert(rollen, pflicht, frei):
    """Rollen, die weder journalpflichtig noch als Ausnahme benannt sind — oder
    beides zugleich."""
    sowohl = sorted(set(pflicht) & set(frei))
    weder = sorted(set(rollen) - set(pflicht) - set(frei))
    fremd = sorted((set(pflicht) | set(frei)) - set(rollen))
    return sowohl + weder + fremd


def test_ratsche_jede_rolle_ist_journalpflichtig_oder_begruendet_ausgenommen():
    """Statische Ratsche, ``==``: Die journalpflichtigen Rollen und die
    benannten Ausnahmen sind zusammen GENAU die Rollen von ROLLEN_DATEIEN ausser
    dem Portfolio — eine neue Nebentabelle ist dadurch von Anfang an
    journalpflichtig, bis jemand sie mit Grund ausnimmt. Mutationsprobe: eine
    Rolle aus journal_pflichtige_rollen streichen, ohne sie in
    OHNE_JOURNAL_GELESEN zu nennen -> rot."""
    pflicht = journal_pflichtige_rollen()
    assert _ungeklaert(ROLLEN, pflicht, OHNE_JOURNAL_GELESEN) == []
    assert set(NEBENTABELLEN) | {"historie", "ledger", "scheiben"} == set(ROLLEN)
    assert set(NEBEN) == set(ROLLEN) == set(FLAG)
    assert all(isinstance(g, str) and len(g) > 20 for g in OHNE_JOURNAL_GELESEN.values())


def test_ratsche_die_ausnahmen_sind_genau_diese_und_keine_hangt_am_portfolio_namen():
    """Runde E, Nachbesserung: Die Ausnahme ``OHNE_JOURNAL_ERLAUBT_MIGRATIONSZUGANG``
    war eine Ausnahme fuer eine Verzeichnisform, die es nicht gibt — der
    Migrationszugang schreibt Historie und Ledger immer neben den Stamm, ein
    Stamm mit NUR schichten/verankerung daneben entsteht nicht. Die Menge der
    ausgenommenen Rollen ist ``==`` ``{"merkmale"}``, und die Antwort haengt
    nicht mehr am Namen des Portfolios (kein Parameter, kein Sonderweg).
    Mutationsprobe: die Ausnahme mit schichten/verankerung wieder einfuehren
    (Menge und Weiche) -> rot."""
    assert set(OHNE_JOURNAL_GELESEN) == {"merkmale"}
    assert not hasattr(manifest, "OHNE_JOURNAL_ERLAUBT_MIGRATIONSZUGANG")
    assert inspect.signature(journal_pflichtige_rollen).parameters == {}
    assert set(journal_pflichtige_rollen()) == set(ROLLEN) - {"merkmale"}
    # Positivkontrolle: schichten und verankerung sind journalpflichtig.
    assert {"schichten", "verankerung"} <= set(journal_pflichtige_rollen())


def test_ratsche_positivkontrolle_sie_findet_eine_nicht_eingeordnete_rolle():
    rollen = ROLLEN + ["neue_tabelle"]
    pflicht = journal_pflichtige_rollen()
    assert _ungeklaert(rollen, pflicht, OHNE_JOURNAL_GELESEN) == ["neue_tabelle"]
    assert _ungeklaert(ROLLEN, pflicht, dict(OHNE_JOURNAL_GELESEN, ledger="x")) == ["ledger"]
    assert _ungeklaert(ROLLEN, [r for r in pflicht if r != "scheiben"], OHNE_JOURNAL_GELESEN) == ["scheiben"]


def test_ratsche_der_bericht_leitet_die_menge_ab_statt_sie_abzutippen():
    """Statisch: ``cli_report.main`` ruft die abgeleitete Menge und nennt keine
    Datei der Rollentabelle im Klartext."""
    quelle = inspect.getsource(cli_report.main)
    assert "journal_pflichtige_rollen(" in quelle
    nebendateien = [ROLLEN_DATEIEN[r] for r in ROLLEN]       # das Portfolio ist keine Nebentabelle
    assert [d for d in nebendateien if d in quelle] == []
    # Positivkontrolle: der Scanner findet einen abgetippten Dateinamen.
    assert [d for d in nebendateien
            if d in quelle + ' (p.parent / "reduktionen.parquet")'] == ["reduktionen.parquet"]


# --------------------------------------------------------------------------- #
# 2. Zaehltest am oeffentlichen CLI-Weg
# --------------------------------------------------------------------------- #


def _portfolio(verzeichnis: Path, name: str) -> Path:
    verzeichnis.mkdir(parents=True, exist_ok=True)
    pfad = verzeichnis / name
    write_portfolio(_stamm([{"id": p, "beginn": "2015-01-01"} for p in range(900_001, 900_006)]), pfad)
    return pfad


def _lauf_bericht(pfad: Path, *zusatz: str) -> int:
    return cli_report.main(
        ["--portfolio", str(pfad), "--stichtage", "2019-01-01",
         "--out", str(pfad.parent / "bericht.html"), *zusatz])


def _merkmale_datei(verzeichnis: Path) -> Path:
    """Eine formal gueltige, leere Merkmalstabelle — der Bericht liest sie."""
    leer = pd.DataFrame({n: pd.Series(dtype=d) for n, d in MERKMALE_SPALTEN})
    pfad = verzeichnis / "merkmale-frei.parquet"
    write_portfolio(leer, pfad)
    return pfad


@pytest.mark.parametrize("name", [GESAMT, MIGRATION])
def test_positivkontrolle_der_stamm_allein_rendert(tmp_path, name):
    """Ohne Nebentabellen rendert der Bericht weiter — die Abweisung sitzt an
    den Tabellen, nicht am Stamm."""
    pfad = _portfolio(tmp_path, name)
    assert _lauf_bericht(pfad) == 0
    assert (tmp_path / "bericht.html").is_file()


@pytest.mark.parametrize("name", [GESAMT, MIGRATION])
@pytest.mark.parametrize("rolle", ROLLEN)
def test_jede_nebentabelle_neben_dem_stamm_weist_den_bericht_ohne_ledger_ab(
        tmp_path, capsys, rolle, name):
    """Zaehltest je Rolle und Portfolio-Name, gegen die Erwartung von Hand:
    Eine Nebendatei der Rolle neben dem Stamm wird abgewiesen (Exit 2, mit
    Dateiname und Ausweg), ausser der benannten Ausnahme (merkmale), die
    weiter rendert.
    Mutationsprobe: die Rolle aus journal_pflichtige_rollen nehmen -> genau
    die Faelle dieser Rolle rot."""
    pfad = _portfolio(tmp_path / "lauf", name)
    (pfad.parent / ROLLEN_DATEIEN[rolle]).write_bytes(b"egal - wird nicht gelesen")
    code = _lauf_bericht(pfad)
    assert code == NEBEN[rolle][name], (rolle, name)
    err = capsys.readouterr().err
    if code == 2:
        assert ROLLEN_DATEIEN[rolle] in err and "--ledger" in err, err
        assert not (pfad.parent / "bericht.html").exists()
    else:
        assert (pfad.parent / "bericht.html").is_file()


@pytest.mark.parametrize("name", [GESAMT, MIGRATION])
@pytest.mark.parametrize("rolle", ROLLEN)
def test_jedes_ausdrueckliche_flag_ohne_ledger_wird_nicht_still_ignoriert(
        tmp_path, capsys, rolle, name):
    """Zaehltest je Rolle fuer den zweiten Weg: ``--<rolle> <datei>`` ohne
    ``--ledger`` (der Stamm liegt in einem Verzeichnis OHNE Nachbarn). Wer eine
    Rolle nennt, meint, dass sie zaehlt — auch beim Migrationszugang.
    Nur ``--merkmale`` wird ohne Ledger gelesen.
    Mutationsprobe: die Rolle aus journal_pflichtige_rollen nehmen -> rot."""
    pfad = _portfolio(tmp_path / "stamm", name)
    extern = tmp_path / "extern"
    extern.mkdir()
    datei = (_merkmale_datei(extern) if rolle == "merkmale"
             else extern / ROLLEN_DATEIEN[rolle])
    if rolle != "merkmale":
        datei.write_bytes(b"egal - wird nicht gelesen")
    code = _lauf_bericht(pfad, f"--{rolle}", str(datei))
    assert code == FLAG[rolle], (rolle, name, capsys.readouterr().err)
    if code == 2:
        assert not (pfad.parent / "bericht.html").exists()


def test_der_ausweg_nennt_alle_betroffenen_dateien(tmp_path, capsys):
    """Die Meldung nennt jede Nebentabelle, die den Bericht zum Stamm allein
    machen wuerde — nicht nur die erste."""
    pfad = _portfolio(tmp_path / "lauf", GESAMT)
    for rolle in ("reduktionen", "schichten", "scheiben"):
        (pfad.parent / ROLLEN_DATEIEN[rolle]).write_bytes(b"x")
    assert _lauf_bericht(pfad) == 2
    err = capsys.readouterr().err
    assert all(ROLLEN_DATEIEN[r] in err for r in ("reduktionen", "schichten", "scheiben"))


def test_mit_dem_lauf_greift_die_weiche_nicht(tmp_path, capsys):
    """Die Abweisung gilt dem Stamm OHNE Journal: Mit ``--historie`` und
    ``--ledger`` greift sie nicht (der Lauf ist angegeben; ob seine Tabellen
    zueinander passen, prueft P-B1, nicht diese Weiche). Die Positivkontrolle
    mit einem echten Lauf steht in ``test_t27_runde_d_bestand``; hier die
    Weiche allein: Der Aufruf scheitert erst an den Bytes, nicht an ihr."""
    pfad = _portfolio(tmp_path / "lauf", GESAMT)
    (pfad.parent / ROLLEN_DATEIEN["reduktionen"]).write_bytes(b"x")
    hist = pfad.parent / "h.parquet"
    led = pfad.parent / "l.parquet"
    hist.write_bytes(b"x")
    led.write_bytes(b"x")
    cli_report.main(["--portfolio", str(pfad), "--historie", str(hist), "--ledger", str(led)])
    assert "gehoert zu diesem Portfolio" not in capsys.readouterr().err
