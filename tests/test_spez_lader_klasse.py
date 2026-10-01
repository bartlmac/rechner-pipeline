"""Nichts rechnet auf einer Spez, deren Vokabular es nicht kennt.

Invariante (Nachzug zur T-Box 0.2.0): Jede Spez, die irgendein Teil des
Systems liest, spricht die geltende T-Box und das geltende Spez-Schema —
sonst wird sie verweigert, mit Ausweg. Bis hierher hielten das nur P-Q3
(A-Box) und P-K1 (``validate_spez``); die Bestandsstrecke
(Uebernahme, Verankerung, aktuarieller Test, Migrationscontrolling,
Fuehrungsprobe) las die Spez ohne jede Versionspruefung, und die
eingefrorenen Baldrian-Spez mit T-Box 0.1.0 liefen dort gruen durch — ein
Test, der seine Eingabe in der alten Gestalt mitbringt, auf einem Pfad, den
niemand prueft.

Bauform: EIN Lader (``spez.validierung.lade_spez_aus_bytes``; ``lade_spez``
delegiert) prueft beide Versionen; jeder Leser geht durch ihn.

* Ratsche (statisch, ``==``): je Modul unter ``src/rechner_pipeline`` und
  ``werkzeuge/`` die Aufrufe des Laders, die Zugriffe auf Spez-Dateien und
  jede Validierung einer ``TarifSpez`` am Lader vorbei — mit
  Positivkontrolle. Kein Modul oeffnet eine Spez, ohne den Lader zu rufen,
  ausser den benannten Ausnahmen.
* Verhalten je Leser: eine Spez mit fremder Version -> Verweigerung mit der
  Meldung des Laders, nicht gruen.
* Die eingefrorenen Fixtures: in ihrer ALTEN Gestalt (SHA-256 festgehalten)
  verweigert, ueber den benannten Weg gehoben.

Knoten: klv
"""

from __future__ import annotations

import ast
import hashlib
import json
import shutil
from pathlib import Path

import pytest

from rechner_pipeline.ontologie import tbox
from rechner_pipeline.spez import validierung as sv

REPO = Path(__file__).resolve().parents[1]
SRC = REPO / "src" / "rechner_pipeline"
WERKZEUGE = REPO / "werkzeuge"

LADER = {"lade_spez", "lade_spez_aus_bytes"}
PFAD = {"spez_pfad"}
DIREKT = {"model_validate", "model_validate_json"}


def _messen(quelle: str):
    """(Lader-Aufrufe, Zugriffe auf Spez-Dateien, Validierung am Lader vorbei)."""
    lader = pfad = direkt = 0
    for k in ast.walk(ast.parse(quelle)):
        if isinstance(k, ast.Call):
            name = (k.func.id if isinstance(k.func, ast.Name)
                    else k.func.attr if isinstance(k.func, ast.Attribute) else None)
            if name in LADER:
                lader += 1
            if name in PFAD:
                pfad += 1
            if (isinstance(k.func, ast.Attribute) and k.func.attr in DIREKT
                    and isinstance(k.func.value, ast.Name)
                    and k.func.value.id == "TarifSpez"):
                direkt += 1
            if isinstance(k.func, ast.Name) and k.func.id == "TarifSpez":
                direkt += 1
        if isinstance(k, ast.Constant) and isinstance(k.value, str) and (
                k.value.endswith("spez.json")):
            pfad += 1
        if (isinstance(k, ast.BinOp) and isinstance(k.op, ast.Div)
                and isinstance(k.right, ast.Constant) and k.right.value == "spez"):
            pfad += 1
    return lader, pfad, direkt


#: Gemessen auf dem Stand des Nachzugs. ``==``: ein neuer Leser, ein neuer
#: Zugriff auf eine Spez-Datei oder eine Validierung am Lader vorbei ist ein
#: Befund — der Leser muss den Lader rufen und hier eingetragen werden.
INVENTAR = {
    "gates/aktuartest_lauf.py": (1, 1, 0),
    "gates/bestand_uebernehmen.py": (1, 1, 0),
    "gates/fuehrungsprobe.py": (1, 1, 0),
    "gates/gate_entscheid.py": (0, 1, 0),
    "gates/generation_golden.py": (1, 1, 0),
    "gates/migrationssuite_lauf.py": (1, 1, 0),
    "gates/verankerung_belegen.py": (1, 1, 0),
    "quellen/tafel_import.py": (1, 0, 0),
    "spez/erzeugen.py": (0, 0, 1),
    "spez/validierung.py": (2, 4, 1),
}
#: Module, die eine Spez-Datei beruehren, OHNE auf ihr zu rechnen — je mit
#: Grund. Alle anderen mit Zugriff muessen den Lader rufen.
OHNE_LADER = {
    "gates/gate_entscheid.py": "hasht den Spez-Ordner fuer den Snapshot (Bytes, keine Rechnung)",
    "spez/erzeugen.py": "KONSTRUIERT die Spez aus der A-Box (Produzent, kein Leser)",
}


def _inventar():
    gemessen = {}
    for wurzel, praefix in ((SRC, ""), (WERKZEUGE, "werkzeuge/")):
        for p in sorted(wurzel.rglob("*.py")):
            wert = _messen(p.read_text(encoding="utf-8"))
            if any(wert):
                gemessen[praefix + str(p.relative_to(wurzel))] = wert
    return gemessen


def test_ratsche_positivkontrolle():
    probe = ('s = lade_spez(f, g)\np = spez_pfad(f, g)\nx = TarifSpez.model_validate(d)\n'
             'y = fall / "abgeleitet" / "spez"\nz = "klv-tg2015.spez.json"\n'
             'w = TarifSpez(**d)\n')
    assert _messen(probe) == (1, 3, 2)
    assert _messen("lade_abox(x)\nTarifSpezial.model_validate(d)\n") == (0, 0, 0)


def test_ratsche_kein_leser_am_lader_vorbei():
    gemessen = _inventar()
    assert gemessen == INVENTAR
    for modul, (lader, pfad, direkt) in gemessen.items():
        if modul == "spez/validierung.py" or modul in OHNE_LADER:
            continue
        assert lader >= 1, f"{modul} oeffnet eine Spez ohne den Lader"
        assert direkt == 0, f"{modul} validiert eine TarifSpez am Lader vorbei"


# --------------------------------------------------------------------------- #
# Der Lader selbst
# --------------------------------------------------------------------------- #

FIXTURES = {
    "baldrian_e2e": "cd68a9bb014441d702e952d7773cb3b02be3439eba853cabdcfb107c48d454ba",
    "baldrian2_e2e": "4763f7839c48816fd9508bcd0ad57e9674bc8319a5d5916d5e73255c3dceb1d2",
}


def _fixture(name: str) -> Path:
    return REPO / "tests" / "fixtures" / name / "klv-tg2015.spez.json"


def _alte_gestalt(roh: bytes) -> bytes:
    """Die Bytes vor der Hebung: Die Hebung 0.1.0 -> 0.2.0 aendert genau die
    Versionszeile; sie zurueckzusetzen ergibt die eingefrorene Datei."""
    alt = roh.replace(b'"tbox_version": "0.2.0"', b'"tbox_version": "0.1.0"')
    assert alt.count(b'"tbox_version": "0.1.0"') == 1
    return alt


@pytest.mark.parametrize("name", sorted(FIXTURES))
def test_die_eingefrorenen_spez_sind_in_alter_gestalt_verweigert_und_gehoben(name):
    """Der Beleg fuer den blinden Fleck: genau diese Bytes (SHA-256 vor dem
    Nachzug) liefen durch die Bestandsstrecke. Jetzt verweigert der Lader
    sie; der benannte Weg hebt sie byte-genau zur heutigen Fixture."""
    heute = _fixture(name).read_bytes()
    alt = _alte_gestalt(heute)
    assert hashlib.sha256(alt).hexdigest() == FIXTURES[name]
    with pytest.raises(sv.SpezVersionFehler, match="0.1.0"):
        sv.lade_spez_aus_bytes(alt)
    assert sv.hebe_spez_auf_geltende_version(alt) == heute
    assert sv.lade_spez_aus_bytes(heute).tbox_version == tbox.TBOX_VERSION


@pytest.mark.parametrize("feld, wert", [
    ("tbox_version", "0.1.0"), ("tbox_version", "999.0.0"), ("spez_version", "0.0.9")])
def test_der_lader_verweigert_jede_fremde_version(feld, wert):
    """Mutationsprobe: die Versionspruefung im Lader entfernen -> rot."""
    daten = json.loads(_fixture("baldrian2_e2e").read_bytes())
    daten[feld] = wert
    with pytest.raises(sv.SpezVersionFehler, match="Ausweg"):
        sv.lade_spez_aus_bytes(sv.spez_bytes(daten))


def test_jeder_schritt_der_linie_hat_eine_spez_hebung():
    linie = tbox.TBOX_VERSIONEN
    assert set(sv.SPEZ_HEBUNGEN) == set(zip(linie, linie[1:]))


def test_heben_kennt_nur_deklarierte_uebergaenge():
    daten = json.loads(_fixture("baldrian2_e2e").read_bytes())
    with pytest.raises(ValueError, match="bereits"):
        sv.hebe_spez_auf_geltende_version(sv.spez_bytes(daten))
    with pytest.raises(ValueError, match="Uebergang"):
        sv.hebe_spez_auf_geltende_version(sv.spez_bytes({**daten, "tbox_version": "0.0.9"}))
    with pytest.raises(ValueError, match="Spez-Schema"):
        sv.hebe_spez_auf_geltende_version(sv.spez_bytes(
            {**daten, "tbox_version": "0.1.0", "spez_version": "0.0.9"}))


# --------------------------------------------------------------------------- #
# Verhalten je Leser: fremde Version -> Verweigerung
# --------------------------------------------------------------------------- #

def _verweigert(aufruf, capsys) -> str:
    """Die Verweigerung eines Lesers: der Fehler des Laders als Ausnahme oder
    als Meldung eines nicht-gruenen Ergebnisses. Gruen ist ein Befund."""
    try:
        ergebnis = aufruf()
    except sv.SpezVersionFehler as exc:
        return str(exc)
    code = getattr(ergebnis, "exit_code", ergebnis)
    assert code != 0, "Spez fremder Version gruen verarbeitet"
    text = json.dumps(getattr(ergebnis, "errors", []), ensure_ascii=False)
    return text + capsys.readouterr().err


def _alte_spez_in(fall: Path, generation: str) -> None:
    pfad = sv.spez_pfad(fall, generation)
    daten = json.loads(pfad.read_bytes())
    daten["tbox_version"] = "0.1.0"
    pfad.write_bytes(sv.spez_bytes(daten))


def test_p_k1_verweigert_eine_spez_fremder_version(tmp_path, capsys):
    from rechner_pipeline.gates.generation_golden import main as pk1
    from tests.e2e_fixture import bereite_pk1_fall

    fall = bereite_pk1_fall(tmp_path, ("klv/tg2012",))
    _alte_spez_in(fall, "klv/tg2012")
    meldung = _verweigert(lambda: pk1([
        "--fall", str(fall), "--generation", "klv/tg2012",
        "--repo-root", str(REPO)]), capsys)
    assert "geltend sind" in meldung, meldung


def test_der_tafelimport_verweigert_eine_spez_fremder_version(tmp_path, capsys):
    from rechner_pipeline.quellen.tafel_import import importiere_fuer_spez
    from tests.e2e_fixture import bereite_pk1_fall

    fall = bereite_pk1_fall(tmp_path, ("klv/tg2012",))
    _alte_spez_in(fall, "klv/tg2012")
    meldung = _verweigert(lambda: importiere_fuer_spez(
        fall, "klv/tg2012", tmp_path / "tafeln.xml", dry_run=True), capsys)
    assert "geltend sind" in meldung, meldung


@pytest.fixture(scope="module")
def kopie_mit_alter_spez(tmp_path_factory, gefahrener_fall):
    """Der gefahrene Baldrian-Fall (Lauf 2), kopiert, mit der Spez in ihrer
    eingefrorenen Gestalt (T-Box 0.1.0). Alles andere ist der gruene Lauf —
    eine Verweigerung kommt also aus der Spez, nicht aus einer fehlenden
    Eingabe; das zeigt die Meldung."""
    from tests.test_baldrian2_e2e import GENERATION

    basis = tmp_path_factory.mktemp("spez_alt")
    fall = basis / "fall"
    shutil.copytree(gefahrener_fall, fall)
    pfad = sv.spez_pfad(fall, GENERATION)
    pfad.write_bytes(_alte_gestalt(pfad.read_bytes()))
    return fall


from tests.test_baldrian2_e2e import gefahrener_fall  # noqa: E402,F401  (Modul-Fixture)


def _e2e():
    import tests.test_baldrian2_e2e as e2e

    return e2e


def test_die_uebernahme_verweigert_eine_spez_fremder_version(kopie_mit_alter_spez, capsys):
    from rechner_pipeline.gates import bestand_uebernehmen

    e2e, fall = _e2e(), kopie_mit_alter_spez
    meldung = _verweigert(lambda: bestand_uebernehmen.main([
        "--fall", str(fall),
        "--zeilen", str(fall / "abgeleitet" / "transformation" / "zeilen.json"),
        "--tarif-generation", e2e.TARIF_GENERATION, "--stichtag", e2e.STICHTAG_1,
        "--vorgeschichte", e2e.METADATEN, "--generation-spez", e2e.GENERATION,
        "--anfangszustand", "materialisieren", "--anker-erwartungswerte", e2e.ANKER,
        "--stoab-je-baustein", "--out-dir", str(fall / "abgeleitet" / "bestand-probe"),
    ] + e2e._lieferungs_flags()), capsys)
    assert "geltend sind" in meldung, meldung


def test_die_verankerung_verweigert_eine_spez_fremder_version(kopie_mit_alter_spez, capsys):
    from rechner_pipeline.gates import verankerung_belegen

    e2e, fall = _e2e(), kopie_mit_alter_spez
    meldung = _verweigert(lambda: verankerung_belegen.main([
        "--fall", str(fall), "--repo-root", str(REPO), "--generation", e2e.GENERATION,
        "--formfunktion", "proportional_zur_basis",
        "--zeilen", str(fall / "abgeleitet" / "transformation" / "zeilen.json"),
        "--vorgeschichte", e2e.METADATEN, "--anker-erwartungswerte", e2e.ANKER,
        "--config", str(fall / "abgeleitet" / "bestand-config.toml"),
        "--stichtag", e2e.STICHTAG_1,
    ] + e2e._lieferungs_flags()), capsys)
    assert "geltend sind" in meldung, meldung


def test_der_aktuarielle_test_verweigert_eine_spez_fremder_version(kopie_mit_alter_spez, capsys):
    from rechner_pipeline.gates import aktuartest_lauf

    e2e, fall = _e2e(), kopie_mit_alter_spez
    bestand = fall / "abgeleitet" / "bestand"
    abnahme, erwartung = e2e.ABNAHMEN[0]
    meldung = _verweigert(lambda: aktuartest_lauf.main([
        "--fall", str(fall), "--abnahme", abnahme, "--generation", e2e.GENERATION,
        "--erwartungswerte", erwartung, "--stichprobe", e2e.STICHPROBE,
        "--bestand", str(bestand / "bestand.parquet"),
        "--zeilen", str(fall / "abgeleitet" / "transformation" / "zeilen.json"),
        "--vorgeschichte", e2e.METADATEN, "--stoab-je-baustein",
        "--anker-erwartungswerte", e2e.ANKER,
        "--schicht", str(fall / "abgeleitet" / "schichten" / "verankerung_schichten.json"),
        "--repo-root", str(REPO),
    ] + e2e._lieferungs_flags()), capsys)
    assert "geltend sind" in meldung, meldung


def test_das_migrationscontrolling_verweigert_eine_spez_fremder_version(kopie_mit_alter_spez, capsys):
    from rechner_pipeline.gates import migrationssuite_lauf

    e2e, fall = _e2e(), kopie_mit_alter_spez
    meldung = _verweigert(lambda: migrationssuite_lauf.main([
        "--fall", str(fall), "--generation", e2e.GENERATION,
        "--abzug-1", e2e.ABZUG_1, "--abzug-2", e2e.ABZUG_2,
        "--gevo-protokoll", e2e.PROTOKOLL,
        "--bestand", str(fall / "abgeleitet" / "bestand" / "bestand.parquet"),
        "--config", str(fall / "abgeleitet" / "bestand-config.toml"),
        "--stichtag-1", e2e.STICHTAG_1, "--stichtag-2", e2e.STICHTAG_2,
        "--zeilen", str(fall / "abgeleitet" / "transformation" / "zeilen.json"),
        "--vorgeschichte", e2e.METADATEN, "--anker-erwartungswerte", e2e.ANKER,
        "--stoab-je-baustein", "--dk-stichtag", "jahrestag",
        "--schicht", str(fall / "abgeleitet" / "schichten" / "verankerung_schichten.json"),
        "--repo-root", str(REPO),
    ] + e2e._lieferungs_flags()), capsys)
    assert "geltend sind" in meldung, meldung


def test_die_fuehrungsprobe_verweigert_eine_spez_fremder_version(kopie_mit_alter_spez, capsys):
    from rechner_pipeline.gates import fuehrungsprobe

    e2e, fall = _e2e(), kopie_mit_alter_spez
    meldung = _verweigert(lambda: fuehrungsprobe.main([
        "--fall", str(fall), "--repo-root", str(REPO), "--generation", e2e.GENERATION,
        "--uebernahme", str(fall / "abgeleitet" / "bestand"),
        "--fortschreibung", str(fall / "abgeleitet" / "bestand-nach"),
        "--config", str(fall / "abgeleitet" / "bestand-config.toml"),
        "--zeilen", str(fall / "abgeleitet" / "transformation" / "zeilen.json"),
        "--vorgeschichte", e2e.METADATEN, "--stichtag", e2e.STICHTAG_1,
        "--anker-erwartungswerte", e2e.ANKER,
        "--schicht", str(fall / "abgeleitet" / "schichten" / "verankerung_schichten.json"),
        "--stoab-je-baustein",
    ] + e2e._lieferungs_flags()), capsys)
    assert "geltend sind" in meldung, meldung


def test_jeder_leser_hat_seinen_verhaltenstest():
    """Die Menge der Leser (Ratsche) und die Menge der Verhaltenstests sind
    dieselbe: ein neuer Leser ohne Verhaltenstest ist rot."""
    leser = {m for m, (lader, _, _) in INVENTAR.items()
             if lader and m != "spez/validierung.py"}
    assert leser == set(VERHALTENSTESTS)
    for name in VERHALTENSTESTS.values():
        assert name in globals(), name


VERHALTENSTESTS = {
    "gates/generation_golden.py": "test_p_k1_verweigert_eine_spez_fremder_version",
    "quellen/tafel_import.py": "test_der_tafelimport_verweigert_eine_spez_fremder_version",
    "gates/bestand_uebernehmen.py": "test_die_uebernahme_verweigert_eine_spez_fremder_version",
    "gates/verankerung_belegen.py": "test_die_verankerung_verweigert_eine_spez_fremder_version",
    "gates/aktuartest_lauf.py": "test_der_aktuarielle_test_verweigert_eine_spez_fremder_version",
    "gates/migrationssuite_lauf.py":
        "test_das_migrationscontrolling_verweigert_eine_spez_fremder_version",
    "gates/fuehrungsprobe.py": "test_die_fuehrungsprobe_verweigert_eine_spez_fremder_version",
}
