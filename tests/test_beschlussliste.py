"""Form der Beschlussliste (docs/architektur/adr-beschlussliste.md).

Die Liste sagt von sich: eine Zeile je Beschluss, mit Datum, neueste oben,
und ein Beleg, der auf das ADR oder die Regel verweist. Dieser Test prueft
genau diese Form, nicht den Inhalt der Beschluesse.

Knoten: system/architektur
"""

import datetime as dt
import re
from pathlib import Path

WURZEL = Path(__file__).resolve().parents[1]
LISTE = WURZEL / "docs" / "architektur" / "adr-beschlussliste.md"
KOPF = ("Datum", "Beschluss", "Beleg")
_DATUM = re.compile(r"\d{2}\.\d{2}\.\d{4}")
_LINK = re.compile(r"\]\(([^)#\s]+)(?:#[^)\s]*)?\)")


def _zellen(zeile: str) -> tuple:
    return tuple(z.strip() for z in zeile.strip().strip("|").split("|"))


def befunde(text: str, ordner: Path) -> list:
    """Alle Verstoesse gegen die Form; leer heisst: die Liste stimmt."""
    tabelle = [z for z in text.splitlines() if z.startswith("|")]
    if len(tabelle) < 2 or _zellen(tabelle[0]) != KOPF:
        return [f"Tabellenkopf fehlt oder lautet nicht {KOPF}"]
    befund, vorher = [], None
    for nr, zeile in enumerate(tabelle[2:], start=1):
        zellen = _zellen(zeile)
        if len(zellen) != 3:
            befund.append(f"Zeile {nr}: {len(zellen)} statt 3 Spalten")
            continue
        datum, beschluss, beleg = zellen
        if not _DATUM.fullmatch(datum):
            befund.append(f"Zeile {nr}: Datum {datum!r} nicht in der Form TT.MM.JJJJ")
            continue
        tag = dt.datetime.strptime(datum, "%d.%m.%Y").date()
        if vorher is not None and tag > vorher:
            befund.append(f"Zeile {nr}: {datum} steht unter einem aelteren Datum")
        vorher = tag
        if not beschluss:
            befund.append(f"Zeile {nr}: ohne Beschluss")
        ziele = _LINK.findall(beleg)
        if not ziele:
            befund.append(f"Zeile {nr}: ohne Beleg-Link")
        for ziel in ziele:
            if not (ordner / ziel).resolve().is_file():
                befund.append(f"Zeile {nr}: Beleg {ziel} zeigt auf keine Datei")
    return befund


def _liste(*zeilen: str) -> str:
    return "| Datum | Beschluss | Beleg |\n|---|---|---|\n" + "".join(z + "\n" for z in zeilen)


_GUT_NEU = "| 10.11.2026 | Neuer Beschluss. | [ADR-028](adr-028-ordnung-nach-ebenen.md) |"
_GUT_ALT = "| 09.11.2026 | Alter Beschluss. | [ADR-007](adr-007-parallele-migrationen-ein-kern.md) |"


def test_die_beschlussliste_hat_ihre_form():
    text = LISTE.read_text(encoding="utf-8")
    assert befunde(text, LISTE.parent) == []
    assert len([z for z in text.splitlines() if z.startswith("|")]) > 2, "Liste ohne Zeile"


def test_eine_gueltige_liste_ist_ohne_befund():
    assert befunde(_liste(_GUT_NEU, _GUT_ALT), LISTE.parent) == []


def test_aeltere_zeile_oben_wird_gemeldet():
    assert befunde(_liste(_GUT_ALT, _GUT_NEU), LISTE.parent) == [
        "Zeile 2: 10.11.2026 steht unter einem aelteren Datum"]


def test_beleg_auf_fehlende_datei_wird_gemeldet():
    zeile = "| 10.11.2026 | Beschluss. | [ADR-999](adr-999-gibt-es-nicht.md) |"
    assert befunde(_liste(zeile), LISTE.parent) == [
        "Zeile 1: Beleg adr-999-gibt-es-nicht.md zeigt auf keine Datei"]


def test_zeile_ohne_beleg_wird_gemeldet():
    assert befunde(_liste("| 10.11.2026 | Beschluss. | ADR-028 |"), LISTE.parent) == [
        "Zeile 1: ohne Beleg-Link"]


def test_datum_in_anderer_form_wird_gemeldet():
    zeile = "| 2026-11-10 | Beschluss. | [ADR-028](adr-028-ordnung-nach-ebenen.md) |"
    assert befunde(_liste(zeile), LISTE.parent) == [
        "Zeile 1: Datum '2026-11-10' nicht in der Form TT.MM.JJJJ"]
