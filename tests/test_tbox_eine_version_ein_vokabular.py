"""Eine Version, ein Vokabular (ADR-024, dritter Nachtrag 2026-10-01).

Invariante: Innerhalb einer ABGENOMMENEN Version der T-Box gibt es genau
ein Vokabular. Vor der ersten A-O1-Zeichnung ist die Version ein Entwurf,
danach ein Vertrag; jede weitere Vokabularaenderung hebt die Version.

Menge, an der die Regel haengt: der Produzent des Aenderungsbelegs
(``stand_belegen tbox``), das Gate (``gate_entscheid --gate A-O1``, im Fall
und im Linienbereich) und der lebende Stand von A-O1, der den Abdruck in
jeden signierten Snapshot traegt. EINE Regel fuer beide:
``stand_belegen.tbox_vokabular_fehler``.

Die Tests bauen ihre Abnahmen ueber die echten Kommandos; veraendert wird
nur das Vokabular des geladenen Moduls (``tbox.vokabular``), nicht die
Version — genau die Lage, die die Regel verbietet.

Knoten: system/entscheid
"""

from __future__ import annotations

import ast
import json
from pathlib import Path

import pytest

from rechner_pipeline.gates import gate_entscheid, stand_belegen
from rechner_pipeline.ontologie import tbox
from tests.test_erstabnahme_linie import _fall_mit_linie, _zeichne_in_linie
from tests.test_standabnahme import _fall, _zeichne_tboxstand
from tests.zeichnung_fixture import ARCHITEKTUR, annahme_args, linie_anlegen, linie_args

REPO = Path(__file__).resolve().parents[1]
SRC = REPO / "src" / "rechner_pipeline"


def _anderes_vokabular(monkeypatch) -> str:
    """Das Vokabular des geladenen Moduls aendern, die Version nicht."""
    original = tbox.vokabular

    def geaendert():
        v = original()
        v["quelle_arten"] = list(v["quelle_arten"]) + ["nachgetragene_quellenart"]
        return v

    vorher = tbox.vokabular_sha256()
    monkeypatch.setattr(tbox, "vokabular", geaendert)
    assert tbox.vokabular_sha256() != vorher  # Positivkontrolle der Mutation
    return vorher


def _lege_vor(fall: Path, linie: Path):
    vermerk = fall / "abgeleitet" / "tbox" / "vermerk.md"
    vermerk.parent.mkdir(parents=True, exist_ok=True)
    vermerk.write_text("Aenderungsvermerk.\n", encoding="utf-8")
    return stand_belegen.main([
        "tbox", "--fall", str(fall), "--vorher-linie", str(linie),
        "--repo-root", str(REPO), "--artefakt", "abgeleitet/tbox/vermerk.md",
        "--begruendung", "Aenderung"])


def _zeichne_ao1(fall: Path):
    return gate_entscheid.main([
        "--fall", str(fall), *linie_args(fall), "--gate", "A-O1", "--entscheid", "angenommen",
        "--entscheider", "it-verantwortung", "--begruendung", "Diffs der T-Box gesehen",
        "--repo-root", str(REPO), *annahme_args(fall, fuer="A-O1")])


def _meldung(ergebnis) -> str:
    assert ergebnis.exit_code != 0
    return ergebnis.errors[0]["message"]


# --------------------------------------------------------------------------- #
# Der lebende Stand traegt den Abdruck — und damit jeder signierte Snapshot
# --------------------------------------------------------------------------- #

def test_der_lebende_stand_von_a_o1_traegt_den_abdruck():
    stand = stand_belegen.lebender_stand("A-O1", REPO)
    assert stand == {"version": tbox.TBOX_VERSION,
                     "tbox_sha256": stand_belegen.tbox_modul_sha256(),
                     "vokabular_sha256": tbox.vokabular_sha256()}


def test_die_abnahme_zeichnet_den_abdruck(tmp_path):
    fall = _fall(tmp_path, mit_tboxstand=False)
    ao1 = _zeichne_tboxstand(fall)
    assert ao1.exit_code == 0, ao1.errors
    snap = json.loads(Path(ao1.paths["snapshot"]).read_text(encoding="utf-8"))
    assert snap["stand"]["vokabular_sha256"] == tbox.vokabular_sha256()


# --------------------------------------------------------------------------- #
# Abnahme im Fall, dann anderes Vokabular unter derselben Version
# --------------------------------------------------------------------------- #

def test_zweites_vokabular_unter_abgenommener_version_im_fall(tmp_path, monkeypatch):
    """Produzent UND Gate verweigern, beide mit dem Ausweg "Version heben".

    Mutationsproben: die Regel im Produzenten auslassen -> der erste Teil
    rot; die Regel im Gate auslassen -> der zweite Teil rot."""
    fall = _fall(tmp_path, mit_tboxstand=False)
    assert _zeichne_tboxstand(fall).exit_code == 0
    belegt = (fall / stand_belegen.TBOX_AENDERUNG_RELATIV).read_bytes()
    alt = _anderes_vokabular(monkeypatch)

    vorlage = _lege_vor(fall, Path(linie_args(fall)[1]))
    meldung = _meldung(vorlage)
    assert "genau ein Vokabular" in meldung and "TBOX_VERSION heben" in meldung, meldung
    assert alt[:16] in meldung and tbox.vokabular_sha256()[:16] in meldung, meldung
    # Der Produzent hat nichts geschrieben: der alte Beleg liegt unveraendert.
    assert (fall / stand_belegen.TBOX_AENDERUNG_RELATIV).read_bytes() == belegt

    # Das Gate rechnet selbst — auch wenn ihm jemand einen Beleg hinlegt.
    meldung = _meldung(_zeichne_ao1(fall))
    assert "genau ein Vokabular" in meldung and "TBOX_VERSION heben" in meldung, meldung


def test_auch_eine_abgeloeste_annahme_zaehlt(tmp_path, monkeypatch):
    """Annahme, dann Ablehnung, dann anderes Vokabular: Die Spitze ist eine
    Ablehnung, die Version war trotzdem gezeichnet.

    Mutationsprobe: nur die geltende Spitze ansehen -> rot."""
    fall = _fall(tmp_path, mit_tboxstand=False)
    assert _zeichne_tboxstand(fall).exit_code == 0
    abgelehnt = gate_entscheid.main([
        "--fall", str(fall), *linie_args(fall), "--gate", "A-O1", "--entscheid", "abgelehnt",
        "--rolle", ARCHITEKTUR, "--entscheider", "it-verantwortung",
        "--begruendung", "zurueckgenommen", "--repo-root", str(REPO),
        *annahme_args(fall, fuer="A-O1")])
    assert abgelehnt.exit_code == 0, abgelehnt.errors
    spitze, _ = stand_belegen.geltende_spitze(fall, "A-O1")
    assert spitze["entscheid"] == "abgelehnt"
    _anderes_vokabular(monkeypatch)
    assert "genau ein Vokabular" in _meldung(_lege_vor(fall, Path(linie_args(fall)[1])))


# --------------------------------------------------------------------------- #
# Abnahme in der Linie, der Fall hat keine eigene Kette
# --------------------------------------------------------------------------- #

def test_zweites_vokabular_gegen_die_abnahme_der_linie(tmp_path, monkeypatch):
    """Die Erstabnahme der Linie bindet die Version auch fuer jeden Fall.

    Mutationsprobe: das Gate haelt nur den Fall, nicht die Linie -> rot."""
    linie, fall = _fall_mit_linie(tmp_path)
    assert not list((fall / "entscheide").glob("A-O1-*.json"))
    _anderes_vokabular(monkeypatch)

    meldung = _meldung(_lege_vor(fall, linie))
    assert "genau ein Vokabular" in meldung and str(linie) in meldung, meldung
    meldung = _meldung(_zeichne_ao1(fall))
    assert "genau ein Vokabular" in meldung and str(linie) in meldung, meldung


def test_a_m4_haelt_die_regel_gegen_seine_linie(tmp_path, monkeypatch):
    """Pruefrunde G (G13, Teil 1): Die Regel lief nur beim Zeichnen von A-O1,
    gegen die Bereiche, die DIESES Zeichnen sah. Fall und Linie sehen
    einander beim Zeichnen nicht immer: Der Fall nimmt die T-Box 0.2.0 ab,
    solange die Linie noch keine A-O1 traegt; danach nimmt die Linie dieselbe
    Version mit einem ANDEREN Vokabular ab (sie sieht den Fall nicht). Zwei
    Vokabulare unter einer abgenommenen Version — A-M4 bekommt Fall und
    Linie und haelt die Regel jetzt selbst nach.

    Der Weg des Pruefers (A-O1 im Fall unter einer Kopie der Linie ohne
    Entscheide) ist seit Teil 2 schon beim Zeichnen zu: die Kopie ist nicht
    die Linie des Auftrags (``tests/test_lebenslauf_runde_g.py``).

    Rot vor dem Fix: A-M4 exit 0 ("abgenommen im Fall"). Mutationsprobe: den
    Aufruf der Regel in ``standabnahme_pruefen`` entfernen -> rot."""
    linie, fall = _fall_mit_linie(tmp_path, gates=("A-K2", "A-T1"))
    _verweise_ohne_tbox(fall, linie)
    assert not list((linie / "entscheide").glob("A-O1-*.json"))

    assert _lege_vor(fall, linie).exit_code == 0
    (fall / stand_belegen.TBOX_STELLUNGNAHME_RELATIV).write_text(json.dumps({
        "schema_version": 1, "nach_version": tbox.TBOX_VERSION,
        "verfasser_rolle": "mensch/aktuariat",
        "felder": [{"name": "tarifwerk", "wirkung": "bewertungsrelevant",
                    "begruendung": "Tarifwerk der Generation"}]}), encoding="utf-8")
    ao1 = _zeichne_ao1(fall)
    assert ao1.exit_code == 0, ao1.errors

    # Die Linie nimmt dieselbe Version mit einem anderen Vokabular ab.
    with monkeypatch.context() as m:
        _anderes_vokabular(m)
        zweites = tbox.vokabular_sha256()
        in_linie = _zeichne_in_linie(linie, "A-O1")
        assert in_linie.exit_code == 0, in_linie.errors
    assert tbox.vokabular_sha256() != zweites  # der Code traegt wieder das erste

    am4 = gate_entscheid.main([
        "--fall", str(fall), "--gate", "A-M4", "--entscheid", "angenommen",
        "--entscheider", "fachrolle", "--begruendung", "Migration abgenommen",
        "--repo-root", str(REPO), *annahme_args(fall)])
    meldung = _meldung(am4)
    assert "genau ein Vokabular" in meldung and str(linie) in meldung, meldung
    assert zweites[:16] in meldung, meldung


def _verweise_ohne_tbox(fall: Path, linie: Path) -> None:
    for gate in ("A-K2", "A-T1"):
        ergebnis = stand_belegen.main([
            "verweisen", "--fall", str(fall), "--gate", gate, "--linie", str(linie),
            "--repo-root", str(REPO)])
        assert ergebnis.exit_code == 0, (gate, ergebnis.errors)


def test_zweites_vokabular_in_der_linie_selbst(tmp_path, monkeypatch):
    linie = linie_anlegen(tmp_path)
    assert _zeichne_in_linie(linie, "A-O1").exit_code == 0
    _anderes_vokabular(monkeypatch)
    vorlage = stand_belegen.main([
        "tbox", "--linie", str(linie), "--repo-root", str(REPO),
        "--artefakt", "abgeleitet/tbox/vermerk.md", "--begruendung", "Aenderung"])
    assert "genau ein Vokabular" in _meldung(vorlage)
    zeichnung = gate_entscheid.main([
        "--linie", str(linie), "--gate", "A-O1", "--entscheid", "angenommen",
        "--entscheider", "verantwortung", "--begruendung", "zweite Abnahme",
        "--repo-root", str(REPO), *annahme_args(linie, fuer="A-O1")])
    assert "genau ein Vokabular" in _meldung(zeichnung)


# --------------------------------------------------------------------------- #
# Was zulaessig bleibt
# --------------------------------------------------------------------------- #

def test_gleiches_vokabular_bei_bewegtem_modul_bleibt_zeichenbar(tmp_path, monkeypatch):
    """Das Modul bewegt sich (Pruefregel, Kommentar), das Vokabular nicht:
    Die alte Abnahme gilt nicht mehr (Stand ==), eine neue ist zeichenbar,
    und ihre Sicht sagt, dass sich am Vokabular nichts geaendert hat.

    Mutationsprobe: die Regel vergleicht den Modul-Hash statt des Abdrucks -> rot."""
    fall = _fall(tmp_path, mit_tboxstand=False)
    assert _zeichne_tboxstand(fall).exit_code == 0
    monkeypatch.setattr(stand_belegen, "tbox_modul_sha256", lambda: "f" * 64)
    assert stand_belegen.tbox_vokabular_fehler(
        [fall, Path(linie_args(fall)[1])]) == []
    vorlage = _lege_vor(fall, Path(linie_args(fall)[1]))
    assert vorlage.exit_code == 0, vorlage.errors
    sicht = (fall / stand_belegen.TBOX_SICHT_RELATIV).read_text(encoding="utf-8")
    assert "Keine Aenderung am Vokabular." in sicht


def test_vor_der_ersten_zeichnung_ist_die_version_ein_entwurf(tmp_path, monkeypatch):
    """Ohne jede Annahme dieser Version darf sich das Vokabular bewegen."""
    fall = _fall(tmp_path, mit_tboxstand=False)
    _anderes_vokabular(monkeypatch)
    assert stand_belegen.tbox_vokabular_fehler([fall, Path(linie_args(fall)[1])]) == []
    assert _zeichne_tboxstand(fall).exit_code == 0


# --------------------------------------------------------------------------- #
# Fail-closed und Pflichtangabe
# --------------------------------------------------------------------------- #

def test_unlesbare_kette_ist_nicht_entscheidbar(tmp_path):
    fall = _fall(tmp_path, mit_tboxstand=False)
    (fall / "entscheide").mkdir(exist_ok=True)
    (fall / "entscheide" / "A-O1-kaputt.json").write_text("{", encoding="utf-8")
    (fehler,) = stand_belegen.tbox_vokabular_fehler([fall])
    assert "nicht lesbar" in fehler and "nicht entscheiden" in fehler, fehler


def test_annahme_ohne_abdruck_im_stand_ist_nicht_entscheidbar(tmp_path, monkeypatch):
    """Eine Annahme dieser Version, deren Stand keinen Abdruck fuehrt,
    belegt kein Vokabular — verweigert, nicht durchgelassen."""
    fall = _fall(tmp_path, mit_tboxstand=False)
    assert _zeichne_tboxstand(fall).exit_code == 0
    kette, _ = stand_belegen._lade_kette(fall, "A-O1")
    (sha, snap), = kette.items()
    ohne = dict(snap, stand={k: v for k, v in snap["stand"].items() if k != "vokabular_sha256"})
    monkeypatch.setattr(stand_belegen, "_lade_kette", lambda b, g: ({sha: ohne}, []))
    (fehler,) = stand_belegen.tbox_vokabular_fehler([fall])
    assert "ohne Abdruck des Vokabulars" in fehler, fehler


def test_tbox_im_fall_verlangt_die_linie(tmp_path):
    """Was eine Aussage traegt, ist nicht weglassbar: ohne --vorher-linie
    saehe weder die Sicht noch die Regel die Abnahme der Linie."""
    fall = _fall(tmp_path, mit_tboxstand=False)
    ohne = stand_belegen.main([
        "tbox", "--fall", str(fall), "--repo-root", str(REPO),
        "--artefakt", "abgeleitet/tbox/vermerk.md", "--begruendung", "x"])
    assert "--vorher-linie" in _meldung(ohne)
    falsch = stand_belegen.main([
        "tbox", "--fall", str(fall), "--vorher-linie", str(tmp_path / "gibtsnicht"),
        "--repo-root", str(REPO), "--artefakt", "abgeleitet/tbox/vermerk.md",
        "--begruendung", "x"])
    assert "kein Linienbereich" in _meldung(falsch)


# --------------------------------------------------------------------------- #
# Ratsche: die Regel hat genau drei Aufrufer
# --------------------------------------------------------------------------- #

def _aufrufe(name: str) -> dict:
    treffer = {}
    for pfad in sorted(SRC.rglob("*.py")):
        baum = ast.parse(pfad.read_text(encoding="utf-8"))
        n = sum(1 for k in ast.walk(baum) if isinstance(k, ast.Call) and (
            (isinstance(k.func, ast.Name) and k.func.id == name)
            or (isinstance(k.func, ast.Attribute) and k.func.attr == name)))
        if n:
            treffer[pfad.relative_to(SRC).as_posix()] = n
    return treffer


def test_die_regel_hat_genau_ihre_drei_aufrufer():
    """Produzent (einmal) und Gate (zweimal): beim Zeichnen von A-O1 und in
    der Standabnahme von A-M4 gegen Fall UND die Linie, die A-M4 bekommt
    (Pruefrunde G, G13 — die Regel lief vorher nur beim Zeichnen, gegen die
    Bereiche DIESES Zeichnens). Ein weiterer Aufrufer oder ein entfallener
    ist eine Entscheidung, kein Versehen."""
    assert _aufrufe("tbox_vokabular_fehler") == {
        "gates/gate_entscheid.py": 2, "gates/stand_belegen.py": 1}
    # Positivkontrolle des Zaehlers: ein Name mit bekannter Aufrufzahl.
    assert _aufrufe("tbox_modul_sha256").get("gates/stand_belegen.py", 0) >= 2
