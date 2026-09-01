"""Der Export der Quelle: das Lieferformat ist ein Vertrag.

Auf den Spalten, Datums- und Betragsformaten der Alt-Lieferung stehen
die Parser der Zielseite (transformation.spec, Vorgeschichte-Leser,
Migrationssuite). Diese Tests halten den Export exakt auf diesem
Vertrag — und die Stellen, an denen die SAUBERE Lieferung bewusst von
der Vorfuehr-Lieferung abweicht (STORNO_KZ leer: M2 ist Regie).

Die Rueckwirkungs-Tests pruefen ueber KREUZ zwischen den Artefakten
(Abzug S1, Abzug S2, Protokoll), nicht gegen die Rekonstruktions-
funktion selbst — sonst bestaetigte der Test nur f(x) == f(x).

Knoten: klv
"""

from __future__ import annotations

import csv
import datetime as dt
import sys
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO_ROOT))

from quellsystem.bestandsfuehrung import lauf  # noqa: E402
from quellsystem.export import Export  # noqa: E402
from quellsystem.konventionen import excel_round  # noqa: E402

SEED = 20260831
S1 = dt.date(2026, 1, 1)
S2 = dt.date(2027, 1, 1)

ABZUG_KOPF = (
    "POLNR;TARIF;VTG_STATUS;GESCHL;RK;BGRP;GEBDAT;BEGINN;ABLAUF;"
    "BZDAUER;ERLSUMME;ZAHLW;JBRUTTO;DECKKAP;STORNO_KZ"
)


@pytest.fixture(scope="module")
def paket(tmp_path_factory):
    buch = lauf(SEED, S2)
    ziel = tmp_path_factory.mktemp("lieferung")
    export = Export(buch)
    export.lieferung(ziel, S1, S2, mit_pdf=False)
    return export, ziel


def _zeilen(pfad: Path):
    with pfad.open(encoding="utf-8") as f:
        return list(csv.DictReader(f, delimiter=";"))


def _je_police(zeilen):
    return {z["POLNR"]: z for z in zeilen}


def test_der_abzug_traegt_das_alt_format(paket):
    """Kopfzeile, Enums, Datums- und Betragsformate — exakt wie geliefert."""
    _, ziel = paket
    pfad = ziel / "baldrian_bestandsabzug_2026-01-01.csv"
    assert pfad.read_text(encoding="utf-8").splitlines()[0] == ABZUG_KOPF
    zeilen = _zeilen(pfad)
    assert len(zeilen) > 500
    for z in zeilen:
        assert z["TARIF"] == "KLV15"
        assert z["VTG_STATUS"] in ("AKT", "BFR")
        assert z["GESCHL"] in ("M", "W")
        assert z["RK"] in ("NR", "R")
        assert z["BGRP"] in ("E", "K", "H")
        assert z["ZAHLW"] in ("jaehrlich", "halbjaehrlich",
                              "vierteljaehrlich", "monatlich")
        for feld in ("GEBDAT", "BEGINN", "ABLAUF"):
            dt.datetime.strptime(z[feld], "%d.%m.%Y")
        for feld in ("ERLSUMME", "JBRUTTO", "DECKKAP"):
            assert "." in z[feld] and len(z[feld].rsplit(".", 1)[1]) == 2
        # M2 (undokumentiertes R/S-Kennzeichen) ist Regie, nicht Quelle.
        assert z["STORNO_KZ"] == ""


def test_beitragsfreie_zeilen_liefern_bfr_summe_und_keinen_beitrag(paket):
    export, ziel = paket
    zeilen = _zeilen(ziel / "baldrian_bestandsabzug_2026-01-01.csv")
    bfr = [z for z in zeilen if z["VTG_STATUS"] == "BFR"]
    assert len(bfr) > 50
    for z in bfr:
        police = export.buch.policen[int(z["POLNR"])]
        assert z["JBRUTTO"] == "0.00"
        assert float(z["ERLSUMME"]) == pytest.approx(
            sum(s.vs_bfr for s in police.scheiben), abs=0.02)


def test_das_deckungskapital_ist_die_letzte_standmitteilung(paket):
    """DECKKAP == Wert am letzten Vertragsjahrestag (t_a) — die Kopplung,
    aus der die monate_ta/dk_ta der Erwartungswerte entstehen."""
    export, ziel = paket
    zeilen = _zeilen(ziel / "baldrian_bestandsabzug_2026-01-01.csv")
    for z in zeilen[:40]:
        police = export.buch.policen[int(z["POLNR"])]
        v = export.verankerung(police, S1)
        assert v["monate_ta"] % 12 == 0
        assert float(z["DECKKAP"]) == pytest.approx(v["dk_ta"], abs=0.01)


def test_rueckwirkender_abzug_und_protokoll_passen_zusammen(paket):
    """Ein 2026 beendeter Vertrag steht im 2026er-Abzug, fehlt im 2027er
    — und sein Abgang steht mit Betrag im Protokoll."""
    _, ziel = paket
    abzug1 = {z["POLNR"] for z in _zeilen(
        ziel / "baldrian_bestandsabzug_2026-01-01.csv")}
    abzug2 = {z["POLNR"] for z in _zeilen(
        ziel / "baldrian_bestandsabzug_2027-01-01.csv")}
    proto = _zeilen(ziel / "baldrian_gevo_protokoll_2026.csv")

    terminal = [z for z in proto if z["GEVO"] in ("STO", "TOD", "ABL")]
    assert terminal, "ein Jahr ohne einen einzigen Abgang waere verdaechtig"
    for z in terminal:
        assert z["POLNR"] in abzug1
        assert z["POLNR"] not in abzug2
        assert float(z["BETRAG"]) >= 0.0

    red = [z for z in proto if z["GEVO"] == "RED"]
    for z in red:
        assert z["PARAM"] in ("0.5", "0.6", "0.75")
    for z in proto:
        datum = dt.datetime.strptime(z["DATUM"], "%d.%m.%Y").date()
        assert S1 < datum <= S2


def test_spaetere_vorfaelle_sind_im_frueheren_abzug_unsichtbar(paket):
    """Rueckwirkung ueber Kreuz: Abzug S1 + Protokoll 2026 == Abzug S2.

    Das Buch ist bis 2027 gefuehrt; der S1-Abzug darf davon nichts
    wissen. Drei Wirkrichtungen, jede an ECHTEN Faellen des Laufs:

    * ERH 2026: die S1-Summe plus die protokollierten Erhoehungsbetraege
      ergibt die S2-Summe.
    * RED 2026 (Einscheiber): die S2-Summe ist die S1-Summe mal dem
      protokollierten Anteil — am S1 steht noch die volle Summe.
    * PEX 2026: am S1 AKT und beitragspflichtig, am S2 BFR ohne Beitrag.
    """
    export, ziel = paket
    z1 = _je_police(_zeilen(ziel / "baldrian_bestandsabzug_2026-01-01.csv"))
    z2 = _je_police(_zeilen(ziel / "baldrian_bestandsabzug_2027-01-01.csv"))
    proto = _zeilen(ziel / "baldrian_gevo_protokoll_2026.csv")
    je_art = {}
    for z in proto:
        je_art.setdefault(z["POLNR"], []).append(z)

    erh = red = pex = 0
    for polnr, vorfaelle in je_art.items():
        arten = {z["GEVO"] for z in vorfaelle}
        if polnr not in z1 or polnr not in z2:
            continue
        if arten == {"ERH"}:
            summe = float(z1[polnr]["ERLSUMME"]) + sum(
                float(z["BETRAG"]) for z in vorfaelle)
            assert float(z2[polnr]["ERLSUMME"]) == pytest.approx(
                summe, abs=0.02)
            erh += 1
        elif arten == {"RED"}:
            police = export.buch.policen[int(polnr)]
            if len(police.scheiben) == 1:
                f = float(vorfaelle[0]["PARAM"])
                assert float(z2[polnr]["ERLSUMME"]) == pytest.approx(
                    excel_round(float(z1[polnr]["ERLSUMME"]) * f, 2),
                    abs=0.01)
            assert float(z2[polnr]["ERLSUMME"]) < float(
                z1[polnr]["ERLSUMME"])
            red += 1
        elif arten == {"PEX"}:
            assert z1[polnr]["VTG_STATUS"] == "AKT"
            assert z1[polnr]["JBRUTTO"] != "0.00"
            assert z2[polnr]["VTG_STATUS"] == "BFR"
            assert z2[polnr]["JBRUTTO"] == "0.00"
            pex += 1
    assert erh > 20 and red > 0 and pex > 0, (
        f"zu wenige Rueckwirkungsfaelle im Lauf (ERH {erh}, RED {red}, "
        f"PEX {pex}) — der Test prueft dann nichts")


def test_die_metadaten_sind_die_vorgeschichte_der_abzugspolicen(paket):
    _, ziel = paket
    abzug = {z["POLNR"] for z in _zeilen(
        ziel / "baldrian_bestandsabzug_2026-01-01.csv")}
    meta = _zeilen(ziel / "baldrian_gevo_metadaten.csv")
    assert len(meta) > 1000, "die Dynamikserien muessen sichtbar sein"
    for z in meta:
        assert z["GEVO"] in ("PEX", "ERH", "RED")
        assert z["POLNR"] in abzug
        datum = dt.datetime.strptime(z["DATUM"], "%d.%m.%Y").date()
        assert datum <= S1
    # Der alte Lieferungsdefekt (max. ein GeVo je Vertrag) bleibt tot,
    # auch durch den Export-Filter hindurch.
    import collections

    je = collections.Counter(z["POLNR"] for z in meta)
    assert max(je.values()) >= 5


def test_das_kalenderjahres_alter_liegt_in_der_lieferung(paket):
    """GEBDAT folgt der Kalenderjahres-Konvention der Quelle: Jahr(Beginn)
    - Jahr(Geburt) = rechnungsmaessiges Alter; Monat/Tag frei. Ein Teil
    der Vertraege weicht damit beim vollendeten Alter des Zielsystems um
    1 ab — genau die Meldungs-Konvention (M1)."""
    export, ziel = paket
    zeilen = _zeilen(ziel / "baldrian_bestandsabzug_2026-01-01.csv")
    abweichungen = 0
    for z in zeilen:
        police = export.buch.policen[int(z["POLNR"])]
        geb = dt.datetime.strptime(z["GEBDAT"], "%d.%m.%Y").date()
        beginn = dt.datetime.strptime(z["BEGINN"], "%d.%m.%Y").date()
        assert beginn.year - geb.year == police.grund.x
        vollendet = police.grund.x - (
            1 if (geb.month, geb.day) > (beginn.month, beginn.day) else 0)
        if vollendet != police.grund.x:
            abweichungen += 1
    assert abweichungen > len(zeilen) // 4, (
        "die Kalenderjahres-Konvention muss sichtbar abweichen")
