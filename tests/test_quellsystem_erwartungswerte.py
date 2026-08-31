"""Erwartungswerte der Lieferung: Schema, Kopplungen, Fachkontrollen.

Die vier JSON-Dateien sind das Pruefprogramm der Migrationsabnahme —
ihr Schema ist ein Vertrag mit der Zielseite (Alt-Lieferung als
Referenz). Die Fachkontrollen laufen ueber KREUZ gegen die anderen
Lieferartefakte (Abzug, Protokoll) und gegen produktweite Wahrheiten
(am Ablauf ist die Reserve die Versicherungssumme) — nicht gegen die
erzeugende Funktion selbst.

Knoten: klv
"""

from __future__ import annotations

import csv
import datetime as dt
import json
import sys
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO_ROOT))

from quellsystem.bestandsfuehrung import lauf  # noqa: E402
from quellsystem.erwartungswerte import (  # noqa: E402
    HISTORIENTYPEN,
    Erwartungswerte,
)
from quellsystem.export import Export  # noqa: E402

SEED = 20260831
S1 = dt.date(2026, 1, 1)
S2 = dt.date(2027, 1, 1)

VERTRAGSFELDER = {"police_id", "historientyp", "monate_ta",
                  "beitragsfrei_seit_jahr", "punkte"}
PUNKTFELDER = {"anlass", "monate", "groessen", "erwartet"}


@pytest.fixture(scope="module")
def paket(tmp_path_factory):
    buch = lauf(SEED, S2)
    ziel = tmp_path_factory.mktemp("lieferung")
    export = Export(buch)
    export.lieferung(ziel, S1, S2, mit_pdf=False)
    return export, ziel


def _lade(ziel: Path, name: str) -> dict:
    return json.loads(
        (ziel / f"baldrian_erwartungswerte_{name}.json").read_text(
            encoding="utf-8"))


def _abzug(ziel: Path) -> dict:
    with (ziel / "baldrian_bestandsabzug_2026-01-01.csv").open(
            encoding="utf-8") as f:
        return {z["POLNR"]: z for z in csv.DictReader(f, delimiter=";")}


def test_das_schema_traegt_den_alt_vertrag(paket):
    """Dateinamen, Top-Level-Struktur und Feldmengen wie geliefert."""
    _, ziel = paket
    for name, test in (("stichtag", "A-M1"), ("verlauf", "A-M2"),
                       ("geschaeftsvorfaelle", "A-M3")):
        j = _lade(ziel, name)
        assert set(j) == {"test", "profil", "stichprobe", "vertraege"}
        assert j["test"] == test
        assert set(j["profil"]) == {"kennung", "titel", "weite",
                                    "grundtoleranz", "kriterien",
                                    "bemerkung"}
        assert j["profil"]["kennung"] == test
        assert set(j["profil"]["grundtoleranz"]) == {
            "abs_tol", "rel_tol", "max_abs_residuum", "p95_abs_residuum"}
        erwartete_felder = (VERTRAGSFELDER - {"beitragsfrei_seit_jahr"}
                            if name == "geschaeftsvorfaelle"
                            else VERTRAGSFELDER)
        for v in j["vertraege"]:
            assert set(v) == erwartete_felder
            assert isinstance(v["police_id"], str)
            assert v["historientyp"] in HISTORIENTYPEN
            assert v["punkte"], "ein Vertrag ohne Punkte prueft nichts"
            for p in v["punkte"]:
                assert set(p) - {"parameter"} == PUNKTFELDER
                assert sorted(p["erwartet"]) == sorted(p["groessen"])
    sp = _lade(ziel, "stichprobe")
    assert set(sp) == {"bestand", "gezogen_am", "hinweis",
                       "A-M1_A-M2", "A-M3"}
    assert sp["bestand"] == "baldrian_bestandsabzug_2026-01-01.csv"
    assert sp["gezogen_am"] == "2026-01-01"


def test_die_ziehung_ist_geschichtet_deterministisch_und_gedeckt(paket):
    export, ziel = paket
    sp = _lade(ziel, "stichprobe")["A-M1_A-M2"]
    st = _lade(ziel, "stichtag")

    # Dieselbe Saat zieht dieselben Policen — die Ziehung haengt an der
    # dokumentierten Saat, nicht an verstecktem Zustand.
    nochmal = Erwartungswerte(export, S1, S2)
    assert [str(n) for n in nochmal._gezogen] == sp["police_ids"]

    assert sp["profil"] == "geschichtet"
    assert sp["umfang"] == len(sp["police_ids"]) == len(st["vertraege"])
    assert [v["police_id"] for v in st["vertraege"]] == sp["police_ids"]
    abdeckung = sp["parameter"]["abdeckung"]
    assert set(abdeckung) == set(HISTORIENTYPEN)
    je_typ = {t: 0 for t in HISTORIENTYPEN}
    for v in st["vertraege"]:
        je_typ[v["historientyp"]] += 1
    for typ, zaehlung in abdeckung.items():
        assert je_typ[typ] == zaehlung["gezogen"] <= zaehlung["vorhanden"]
        assert zaehlung["gezogen"] == min(
            sp["parameter"]["je_schicht"], zaehlung["vorhanden"])
    assert sum(z["vorhanden"] for z in abdeckung.values()) == sp[
        "grundgesamtheit"]
    # Alle vier Historientypen muessen im Lauf tatsaechlich vorkommen —
    # sonst prueft die Schichtung des Falls nichts.
    assert all(z["vorhanden"] >= 25 for z in abdeckung.values())


def test_der_uebernahmepunkt_ist_das_gelieferte_deckkap(paket):
    """Kreuz-Kopplung Erwartungswerte <-> Bestandsabzug: derselbe Wert."""
    _, ziel = paket
    abzug = _abzug(ziel)
    st = _lade(ziel, "stichtag")
    mit_abzug = 0
    for v in st["vertraege"]:
        zeile = abzug[v["police_id"]]
        uebernahme = v["punkte"][0]
        assert uebernahme["anlass"] == "uebernahme"
        assert uebernahme["monate"] == v["monate_ta"]
        assert uebernahme["erwartet"]["kVx_MRV"] == pytest.approx(
            float(zeile["DECKKAP"]), abs=0.005)
        fortschreibung = v["punkte"][1]
        assert fortschreibung["anlass"] == "fortschreibung"
        assert fortschreibung["monate"] == v["monate_ta"] + 12
        if v["historientyp"] == "beitragsfrei":
            assert zeile["VTG_STATUS"] == "BFR"
            assert uebernahme["groessen"] == ["kVx_MRV", "VS_bfr"]
            assert uebernahme["erwartet"]["VS_bfr"] == pytest.approx(
                float(zeile["ERLSUMME"]), abs=0.005)
            assert v["beitragsfrei_seit_jahr"] is not None
            assert 12 * v["beitragsfrei_seit_jahr"] <= v["monate_ta"]
        else:
            assert uebernahme["groessen"] == ["kVx_MRV", "RKW", "BJB"]
            assert uebernahme["erwartet"]["BJB"] == pytest.approx(
                float(zeile["JBRUTTO"]), abs=0.005)
            # Gleichheit ist erlaubt: die Haus-Zelle erhebt keinen
            # Abzug, und in der Flex-Phase entfaellt er tariflich.
            assert uebernahme["erwartet"]["RKW"] <= uebernahme[
                "erwartet"]["kVx_MRV"]
            if uebernahme["erwartet"]["RKW"] < uebernahme[
                    "erwartet"]["kVx_MRV"]:
                mit_abzug += 1
            assert v["beitragsfrei_seit_jahr"] is None
    assert mit_abzug > 20, "der Stornoabzug muss in der Stichprobe sichtbar sein"


def test_der_verlauf_endet_am_ablauf_mit_der_versicherungssumme(paket):
    """Produktweite Wahrheit der gemischten Versicherung: am Ablauf ist
    die Reserve die Versicherungssumme. Der letzte Verlaufspunkt jedes
    Vertrags muss auf dem Ablauf liegen und diesen Wert tragen —
    gekreuzt gegen die ERLSUMME des Abzugs, nicht gegen die Engine."""
    export, ziel = paket
    abzug = _abzug(ziel)
    vl = _lade(ziel, "verlauf")
    assert {len(v["punkte"]) for v in vl["vertraege"]} <= {1, 2, 3}
    for v in vl["vertraege"]:
        police = export.buch.policen[int(v["police_id"])]
        ablauf = 12 * police.grund.n
        monate = [p["monate"] for p in v["punkte"]]
        assert monate == sorted(set(monate)), "Punkte doppelt/unsortiert"
        assert monate[-1] == ablauf, "der Ablauf ist immer dabei"
        assert all(m <= ablauf for m in monate)
        letzter = v["punkte"][-1]
        assert letzter["erwartet"]["kVx_MRV"] == pytest.approx(
            float(abzug[v["police_id"]]["ERLSUMME"]), abs=0.3)
        if v["historientyp"] == "beitragsfrei":
            # Die beitragsfreie Summe ist fixiert — an jedem Punkt gleich.
            werte = {p["erwartet"]["VS_bfr"] for p in v["punkte"]}
            assert len(werte) == 1


def test_die_geschaeftsvorfaelle_sind_die_vollerhebung_des_jahres(paket):
    """Kreuz-Kopplung Erwartungswerte <-> GeVo-Protokoll — und die
    dDK-Fachkontrollen: Terminale raeumen (negativ), die Dynamik traegt
    am Buchungstag nichts, RED nennt den Anteil des Protokolls."""
    _, ziel = paket
    gv = _lade(ziel, "geschaeftsvorfaelle")
    with (ziel / "baldrian_gevo_protokoll_2026.csv").open(
            encoding="utf-8") as f:
        proto = list(csv.DictReader(f, delimiter=";"))

    assert gv["stichprobe"]["vollerhebung"] is True
    assert gv["stichprobe"]["police_ids"] == sorted(
        {z["POLNR"] for z in proto}, key=int)
    assert [v["police_id"] for v in gv["vertraege"]] == gv[
        "stichprobe"]["police_ids"]

    punkte_je_police = {v["police_id"]: v["punkte"]
                        for v in gv["vertraege"]}
    assert sum(len(p) for p in punkte_je_police.values()) == len(proto)
    for v in gv["vertraege"]:
        for p in v["punkte"]:
            assert p["monate"] % 12 == 0, "Jahrestagsbuchung"
            assert p["groessen"] == ["dDK"]
            if p["anlass"] in ("STO", "TOD", "ABL"):
                assert p["erwartet"]["dDK"] < 0.0
            if p["anlass"] == "ERH":
                assert p["erwartet"]["dDK"] == 0.0
            if p["anlass"] == "PEX":
                assert p["erwartet"]["dDK"] <= 0.5
    for z in proto:
        if z["GEVO"] != "RED":
            continue
        red_punkte = [p for p in punkte_je_police[z["POLNR"]]
                      if p["anlass"] == "RED"]
        assert any(p["parameter"]["anteil"] == float(z["PARAM"])
                   for p in red_punkte)


def test_ein_storno_raeumt_mehr_als_es_auszahlt(paket):
    """|dDK| - Auszahlung ist der Stornoabzug — je SCHEIBE begrenzt,
    also zwischen 50 und 200 mal der Scheibenzahl (Kreuzprobe gegen
    das Protokoll; die Untergrenze greift mehrfach)."""
    export, ziel = paket
    gv = _lade(ziel, "geschaeftsvorfaelle")
    with (ziel / "baldrian_gevo_protokoll_2026.csv").open(
            encoding="utf-8") as f:
        betrag = {(z["POLNR"], z["GEVO"]): float(z["BETRAG"])
                  for z in csv.DictReader(f, delimiter=";")}
    geprueft = 0
    for v in gv["vertraege"]:
        for p in v["punkte"]:
            if p["anlass"] != "STO":
                continue
            auszahlung = betrag[(v["police_id"], "STO")]
            if auszahlung == 0.0:
                continue  # Abzug haette den RKW aufgezehrt (Untergrenze 0)
            police = export.buch.policen[int(v["police_id"])]
            abzugsspanne = -p["erwartet"]["dDK"] - auszahlung
            # Nach dem Storno kommen keine Scheiben mehr dazu — die
            # Scheibenzahl der Police IST die zum Stornozeitpunkt.
            scheiben = len(police.scheiben)
            if abzugsspanne <= 0.01:
                # Kein Abzug erhoben: Haus-Zelle (Abzug 0) oder
                # Flex-Phase. Alles dazwischen (0 < Spanne < 50) waere
                # ein Formfehler der Grenzen.
                assert abzugsspanne == pytest.approx(0.0, abs=0.01)
                continue
            assert 50.0 - 0.01 <= abzugsspanne <= 200.0 * scheiben + 0.01
            geprueft += 1
    assert geprueft > 0
