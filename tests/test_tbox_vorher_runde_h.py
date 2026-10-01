"""Die Vergleichsgrundlage der T-Box-Sicht rechnet das Gate selbst — eine fruehere Abnahme wird nie still zur Erstabnahme.

Befund der blinden Pruefrunde H (H09, niedrig): ``stand_belegen tbox --fall
... --vorher-linie <ein leerer Linienbereich>`` erfuellte die Pflichtangabe,
der Beleg trug ``vorher = None``, die Sicht sagte "Erstabnahme", und das Gate
zeichnete A-O1 — es pruefte an ``vorher`` nur die innere Stimmigkeit, obwohl
die Linie des Auftrags die T-Box schon abgenommen hatte.

Invariante: Die Vergleichsgrundlage der Sicht ist die zuletzt angenommene
T-Box in Fall und Linie DES GATES (im Linienbereich: der Linie). Eine Stelle:
``gates.sichten.sicht_fehler`` (Register-Eintrag ``grundlage`` von A-O1) ruft
``stand_belegen.tbox_vorher_fehler`` mit den Bereichen des Aufrufs; dieselbe
Funktion wie der Produzent (``_vorher_tbox``), ohne die Annahmen, die genau
diesen Beleg pinnen (Idempotenz).

Mutationsproben: den Aufruf der Grundlage in ``sicht_fehler`` entfernen ->
``test_die_leere_vorher_linie_*`` rot; den Ausschluss ``ohne_beleg`` entfernen
-> ``test_die_wiederholung_*`` rot.

Knoten: system/entscheid
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from rechner_pipeline.gates import gate_entscheid, stand_belegen
from rechner_pipeline.ontologie import tbox
from tests.test_erstabnahme_linie import _fall_mit_linie, _zeichne_in_linie
from tests.zeichnung_fixture import annahme_args

REPO = Path(__file__).resolve().parents[1]


def _vorlage(fall: Path, vorher_linie: Path):
    vermerk = fall / "abgeleitet" / "tbox" / "vermerk.md"
    vermerk.parent.mkdir(parents=True, exist_ok=True)
    vermerk.write_text("Vermerk der T-Box im Fall.\n", encoding="utf-8")
    ergebnis = stand_belegen.main([
        "tbox", "--fall", str(fall), "--vorher-linie", str(vorher_linie),
        "--repo-root", str(REPO), "--artefakt", "abgeleitet/tbox/vermerk.md",
        "--begruendung", "T-Box im Fall (Runde H)"])
    assert ergebnis.exit_code == 0, ergebnis.errors
    (fall / stand_belegen.TBOX_STELLUNGNAHME_RELATIV).write_text(json.dumps({
        "schema_version": 1, "nach_version": tbox.TBOX_VERSION,
        "verfasser_rolle": "mensch/aktuariat",
        "felder": [{"name": "tarifwerk", "wirkung": "bewertungsrelevant",
                    "begruendung": "Runde H"}]}), encoding="utf-8")
    return json.loads((fall / stand_belegen.TBOX_AENDERUNG_RELATIV).read_text(encoding="utf-8"))


def _ao1(fall: Path):
    return gate_entscheid.main([
        "--fall", str(fall), "--gate", "A-O1", "--entscheid", "angenommen",
        "--entscheider", "architektur", "--begruendung", "A-O1 im Fall (Runde H)",
        "--repo-root", str(REPO), *annahme_args(fall, fuer="A-O1")])


@pytest.fixture()
def welt(tmp_path):
    """Die Linie hat die T-Box abgenommen (A-O1, Erstabnahme); ein beauftragter
    Fall unter ihr; daneben ein leerer Linienbereich."""
    linie, fall = _fall_mit_linie(tmp_path, gates=("A-O1",))
    leer = tmp_path / "leer" / "linie"
    assert stand_belegen.main(["linie", "--linie", str(leer)]).exit_code == 0
    return linie, fall, leer


def test_die_leere_vorher_linie_macht_keine_erstabnahme(welt):
    """Das Repro des Pruefers ueber die echten Kommandos. Rot vor dem Fix:
    A-O1 im Fall Exit 0 auf einer Sicht "Erstabnahme"."""
    linie, fall, leer = welt
    beleg = _vorlage(fall, leer)
    assert beleg["vorher"] is None
    assert "Erstabnahme" in (fall / stand_belegen.TBOX_SICHT_RELATIV).read_text(encoding="utf-8")
    ergebnis = _ao1(fall)
    assert ergebnis.exit_code != 0, ergebnis.summary
    assert ergebnis.errors[0]["code"] == "sicht", ergebnis.errors
    meldung = ergebnis.errors[0]["message"]
    assert "Vergleichsgrundlage" in meldung and "keine fruehere Abnahme (Erstabnahme)" in meldung
    [ao1_linie] = [json.loads(p.read_text(encoding="utf-8"))
                   for p in (linie / "entscheide").glob("A-O1-*.json")]
    assert ao1_linie["snapshot_sha256"][:16] in meldung, meldung
    assert "--vorher-linie" in meldung, meldung
    assert not list((fall / "entscheide").glob("A-O1-*.json"))


def test_die_wiederholung_mit_der_linie_des_falls_nimmt_an_und_ist_idempotent(welt):
    """Positivkontrolle und Idempotenz: mit der Linie des Falls neu erzeugt,
    nimmt das Gate an; derselbe Aufruf danach findet die eigene Annahme in der
    Kette und meldet ``bereits_vorhanden`` — die Grundlage ist die Abnahme VOR
    diesem Beleg, nicht die eigene."""
    linie, fall, _ = welt
    beleg = _vorlage(fall, linie)
    assert beleg["vorher"] is not None
    erst = _ao1(fall)
    assert erst.exit_code == 0, erst.errors
    nochmal = _ao1(fall)
    assert nochmal.exit_code == 0, nochmal.errors
    assert nochmal.summary.get("bereits_vorhanden") is True


def test_im_linienbereich_gilt_dieselbe_regel(tmp_path):
    """Die zweite A-O1-Abnahme der Linie nennt die erste als Grundlage; ein Beleg,
    der sie verschweigt (von Hand ``vorher`` entfernt, Sicht nachgezogen), wird
    nicht gezeichnet. Die Wiederholung der ersten Abnahme bleibt idempotent."""
    from tests.zeichnung_fixture import handbeleg_sicht_nachziehen, linie_anlegen

    def zeichnen(begruendung):
        return gate_entscheid.main([
            "--linie", str(linie), "--gate", "A-O1", "--entscheid", "angenommen",
            "--entscheider", "verantwortung", "--begruendung", begruendung,
            "--repo-root", str(REPO), *annahme_args(linie, fuer="A-O1")])

    linie = linie_anlegen(tmp_path)
    erst = _zeichne_in_linie(linie, "A-O1")
    assert erst.exit_code == 0, erst.errors
    nochmal = zeichnen("Erstabnahme A-O1")
    assert nochmal.exit_code == 0 and nochmal.summary.get("bereits_vorhanden") is True
    beleg_pfad = linie / stand_belegen.TBOX_AENDERUNG_RELATIV
    beleg = json.loads(beleg_pfad.read_text(encoding="utf-8"))
    beleg["begruendung"] = "zweite Abnahme"
    beleg["vorher"] = None
    beleg_pfad.write_text(json.dumps(beleg, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
                          encoding="utf-8")
    handbeleg_sicht_nachziehen(linie, "A-O1")
    zweit = zeichnen("zweite Abnahme")
    assert zweit.exit_code != 0 and zweit.errors[0]["code"] == "sicht", zweit.errors
    assert erst.summary["snapshot_sha256"][:16] in zweit.errors[0]["message"]
