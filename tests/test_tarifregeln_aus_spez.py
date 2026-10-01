"""Die Tarifregeln stehen EINMAL, belegt — jedes Kommando rechnet mit ihnen.

Invariante (Entscheid des Maintainers 2026-10-01, ADR-024, Nachtrag): Die
Regeln eines uebernommenen Tarifs stehen einmal, belegt (A-Box -> Spez), und
jedes Kommando der Bestandsstrecke rechnet mit genau dieser Fassung. Kein
Kommando rechnet mit einer Vorgabe, die niemand belegt hat.

Vorher: ``--red-verfahren``, ``--stoab-je-baustein``,
``--scheiben-mit-gamma1``, ``--tku-umfang``, ``--erhoehungssatz``,
``--dk-stichtag``, ``--formfunktion``/``--fenster`` an fuenf Kommandos, mit
der Regel des eigenen Geschaefts als Vorgabe. Ein vergessener Schalter
rechnete still die PLV-Regel (stiller Default), und dieselbe Tatsache
musste fuenfmal gleich getippt werden (Zweitwissen).

Instrumente (Skill ``teste-adversarial``, drei Instrumente):

* Ratschen (statisch, ``==`` mit Positivkontrolle): kein Kommando unter
  ``gates/`` deklariert einen Schalter fuer ein Merkmal, das die Spez fuehrt;
  genau die fuenf Kommandos beziehen die Regeln ueber
  ``tarifregeln_der_spez`` und verweigern die alten Schalter ueber
  ``verweigere_entfallene_schalter``; keines nennt die PLV-Vorgabe.
* Verhalten je Kommando: dieselbe Lieferung mit zwei belegten Regelwerken
  ergibt die zwei erwarteten Ergebnisse (die Regel WIRKT), eine Spez ohne
  Tarifwerk wird verweigert, ein alter Schalter wird sprechend verweigert.
* P-Q3: im Scope ``bestand`` Pflicht, im Scope ``tarif`` nicht.

Knoten: klv/tg2015
"""

from __future__ import annotations

import ast
import json
import shutil
import sys
from pathlib import Path
from typing import Dict, List, Tuple

import pytest

from rechner_pipeline.ontologie import tbox
from rechner_pipeline.spez import tarifregeln as tr
from rechner_pipeline.spez.validierung import spez_pfad
from tests.tarifregeln_testhelfer import spez_variante
from tests.test_auskunft_registriert_klasse import MAINS, _aufruf
from tests.test_baldrian2_e2e import (  # noqa: F401  (Modul-Fixture)
    AUSKUNFT,
    FIXTURE,
    GENERATION,
    gefahrener_fall,
)

REPO = Path(__file__).resolve().parents[1]
GATES = REPO / "src" / "rechner_pipeline" / "gates"
SRC = REPO / "src" / "rechner_pipeline"

#: Die Kommandos der Bestandsstrecke, die Tarifregeln rechnen.
KOMMANDOS = ("bestand_uebernehmen", "verankerung_belegen", "aktuartest_lauf",
             "migrationssuite_lauf", "fuehrungsprobe")


# --------------------------------------------------------------------------- #
# Ratschen (statisch)
# --------------------------------------------------------------------------- #

def _spez_schalter() -> set:
    """Jeder denkbare Schalter fuer ein Merkmal, das die Spez fuehrt — aus
    dem Vokabular abgeleitet, nicht abgetippt: ein neues Merkmal der T-Box
    ist sofort mitgemeint."""
    namen = {f"--{m.replace('_', '-')}" for bloecke in tbox.GENERATIONS_BLOECKE.values()
             for m in bloecke}
    return namen | set(tr.ENTFALLENE_SCHALTER)


def _deklarierte_schalter(quelle: str) -> List[str]:
    aus = []
    for k in ast.walk(ast.parse(quelle)):
        if (isinstance(k, ast.Call) and isinstance(k.func, ast.Attribute)
                and k.func.attr == "add_argument"):
            aus += [a.value for a in k.args
                    if isinstance(a, ast.Constant) and isinstance(a.value, str)]
    return aus


def _aufrufe(quelle: str, namen: Tuple[str, ...]) -> Tuple[int, ...]:
    zaehler = dict.fromkeys(namen, 0)
    for k in ast.walk(ast.parse(quelle)):
        if isinstance(k, ast.Call):
            name = (k.func.id if isinstance(k.func, ast.Name)
                    else k.func.attr if isinstance(k.func, ast.Attribute) else None)
            if name in zaehler:
                zaehler[name] += 1
    return tuple(zaehler[n] for n in namen)


#: Namen, die eine Vorgabe des eigenen Geschaefts tragen: die PLV-Regel als
#: Ersatz einer nicht belegten Regel. ``tku_umfang_fuer`` leitet den Umfang
#: aus dem Verfahren ab — fuer einen uebernommenen Tarif ist er belegt.
VORGABE_NAMEN = {"PROSPEKTIV", "TARIFWERK_EIGENES_GESCHAEFT", "tku_umfang_fuer"}


def _vorgabe_namen(quelle: str) -> List[str]:
    gefunden = []
    for k in ast.walk(ast.parse(quelle)):
        if isinstance(k, ast.Name) and k.id in VORGABE_NAMEN:
            gefunden.append(k.id)
        elif isinstance(k, ast.Attribute) and k.attr in VORGABE_NAMEN:
            gefunden.append(k.attr)
        elif isinstance(k, ast.alias) and k.name in VORGABE_NAMEN:
            gefunden.append(k.name)
    return gefunden


def _direkter_blockzugriff(quelle: str) -> int:
    """``spez.tarifwerk`` / ``spez.quellverfahren`` am Weg vorbei."""
    return sum(1 for k in ast.walk(ast.parse(quelle))
               if isinstance(k, ast.Attribute) and k.attr in tbox.GENERATIONS_BLOECKE
               and isinstance(k.value, ast.Name) and k.value.id == "spez")


def test_ratsche_positivkontrolle():
    probe = ('p.add_argument("--stoab-je-baustein", action="store_true")\n'
             'p.add_argument("--dk-stichtag", default="kalendertag")\n'
             'p.add_argument("--fall")\n'
             'r = tarifregeln_der_spez(spez)\nverweigere_entfallene_schalter(p)\n'
             'x = PROSPEKTIV\nfrom m import tku_umfang_fuer\ny = spez.tarifwerk\n')
    assert set(_deklarierte_schalter(probe)) & _spez_schalter() == {
        "--stoab-je-baustein", "--dk-stichtag"}
    assert _aufrufe(probe, ("tarifregeln_der_spez", "verweigere_entfallene_schalter")) == (1, 1)
    assert sorted(_vorgabe_namen(probe)) == ["PROSPEKTIV", "tku_umfang_fuer"]
    assert _direkter_blockzugriff(probe) == 1
    # Die abgeleitete Schaltermenge kennt jedes Merkmal der T-Box.
    assert {"--erhoehungssatz", "--fenster", "--formfunktion", "--red-verfahren",
            "--tku-umfang", "--scheiben-mit-gamma1"} <= _spez_schalter()


def test_ratsche_kein_kommando_deklariert_einen_schalter_fuer_ein_merkmal_der_spez():
    verstoesse = {
        p.name: sorted(set(_deklarierte_schalter(p.read_text(encoding="utf-8")))
                       & _spez_schalter())
        for p in sorted(GATES.glob("*.py"))
    }
    assert {k: v for k, v in verstoesse.items() if v} == {}


#: Wer die Regeln ueber die EINE Funktion bezieht und die alten Schalter
#: verweigert — gemessen, ``==``. ``spez/validierung.py`` prueft mit der
#: Funktion das Ergebnis des Fixture-Wegs (ergaenze_tarifregeln).
INVENTAR = {
    "gates/aktuartest_lauf.py": (1, 1),
    "gates/bestand_uebernehmen.py": (1, 1),
    "gates/fuehrungsprobe.py": (1, 1),
    "gates/migrationssuite_lauf.py": (1, 1),
    "gates/verankerung_belegen.py": (1, 1),
    "spez/validierung.py": (1, 0),
}


def test_ratsche_jedes_kommando_bezieht_die_regeln_ueber_dieselbe_funktion():
    gemessen = {}
    for p in sorted(SRC.rglob("*.py")):
        rel = str(p.relative_to(SRC))
        if rel == "spez/tarifregeln.py":
            continue
        wert = _aufrufe(p.read_text(encoding="utf-8"),
                        ("tarifregeln_der_spez", "verweigere_entfallene_schalter"))
        if any(wert):
            gemessen[rel] = wert
    assert gemessen == INVENTAR
    assert {f"gates/{k}.py" for k in KOMMANDOS} == {
        m for m, (bezug, _) in INVENTAR.items() if m.startswith("gates/") and bezug}


def test_ratsche_kein_kommando_nennt_die_vorgabe_des_eigenen_geschaefts():
    for kommando in KOMMANDOS:
        quelle = (GATES / f"{kommando}.py").read_text(encoding="utf-8")
        assert _vorgabe_namen(quelle) == [], kommando
        assert _direkter_blockzugriff(quelle) == 0, kommando


# --------------------------------------------------------------------------- #
# Die Funktion und die Regel (rein)
# --------------------------------------------------------------------------- #

class _Spez:
    def __init__(self, tarifwerk, quellverfahren, generation="klv/tg2015"):
        self.tarifwerk, self.quellverfahren, self.generation = (
            tarifwerk, quellverfahren, generation)


def _regeln_der_fixture() -> Dict[str, Dict]:
    roh = json.loads((FIXTURE / "klv-tg2015.spez.json").read_text(encoding="utf-8"))
    return {"tarifwerk": roh["tarifwerk"], "quellverfahren": roh["quellverfahren"]}


def test_die_funktion_liefert_die_belegten_regeln_ohne_vorgabe():
    r = _regeln_der_fixture()
    regeln = tr.tarifregeln_der_spez(_Spez(r["tarifwerk"], r["quellverfahren"]))
    assert regeln.tarifwerk == r["tarifwerk"]
    assert (regeln.red_verfahren, regeln.quell_red_verfahren) == ("teilkuendigung",) * 2
    assert regeln.dk_stichtag == "jahrestag" and regeln.erhoehungssatz == 0.05
    assert regeln.fenster is None
    # Ohne Dynamiksatz: None, nicht eine Zahl.
    ohne = dict(r["quellverfahren"])
    del ohne["erhoehungssatz"]
    assert tr.tarifregeln_der_spez(_Spez(r["tarifwerk"], ohne)).erhoehungssatz is None


@pytest.mark.parametrize("block, merkmal", [
    (b, m) for b, ms in tbox.BESTAND_PFLICHT.items() for m in ms])
def test_jedes_pflichtmerkmal_fehlt_mit_namen(block, merkmal):
    """Kein Pflichtmerkmal hat eine Vorgabe: Fehlt eines, verweigert die
    Funktion und nennt es — fuer JEDES Merkmal der Pflicht."""
    r = _regeln_der_fixture()
    r[block] = {k: v for k, v in r[block].items() if k != merkmal}
    with pytest.raises(tr.TarifregelnFehler, match=f"{block}.{merkmal} nicht belegt"):
        tr.tarifregeln_der_spez(_Spez(r["tarifwerk"], r["quellverfahren"]))


@pytest.mark.parametrize("block, merkmal, wert, text", [
    ("tarifwerk", "stoab_je_baustein", 1, "Wertebereich"),
    ("tarifwerk", "red_verfahren", "irgendwie", "Wertebereich"),
    ("quellverfahren", "erhoehungssatz", 5, "Wertebereich"),
    ("quellverfahren", "erhoehungssatz", 1.5, "Wertebereich"),
    ("quellverfahren", "dk_stichtag", "monatsende", "Wertebereich"),
    ("quellverfahren", "fenster", 10, "kennt kein Fenster"),
    ("quellverfahren", "stichtag_der_quelle", "x", "kein Merkmal"),
])
def test_ein_wert_ausserhalb_der_regel_wird_verweigert(block, merkmal, wert, text):
    r = _regeln_der_fixture()
    r[block] = {**r[block], merkmal: wert}
    with pytest.raises(tr.TarifregelnFehler, match=text):
        tr.tarifregeln_der_spez(_Spez(r["tarifwerk"], r["quellverfahren"]))


def test_das_fenster_folgt_der_formfunktion():
    r = _regeln_der_fixture()
    qv = {**r["quellverfahren"], "formfunktion": "konstantes_fenster"}
    with pytest.raises(tr.TarifregelnFehler, match="fenster nicht belegt"):
        tr.tarifregeln_der_spez(_Spez(r["tarifwerk"], qv))
    assert tr.tarifregeln_der_spez(_Spez(r["tarifwerk"], {**qv, "fenster": 10})).fenster == 10


def test_pflicht_und_erhebung_im_vokabular():
    """Die Pflicht ist Vokabular (Abdruck), nicht Prosa; jedes Merkmal der
    Bloecke ist Pflicht, zu erheben oder folgt der Formfunktion."""
    alle = {(b, m) for b, ms in tbox.GENERATIONS_BLOECKE.items() for m in ms}
    pflicht = {(b, m) for b, ms in tbox.BESTAND_PFLICHT.items() for m in ms}
    erhoben = {(b, m) for b, ms in tbox.BESTAND_ERHOBEN.items() for m in ms}
    assert alle == pflicht | erhoben | {("quellverfahren", "fenster")}
    assert tbox.vokabular()["bestand_pflicht"] == {
        b: list(ms) for b, ms in tbox.BESTAND_PFLICHT.items()}
    from rechner_pipeline.bestand.migrationszugang import FORMEN

    assert tuple(sorted(FORMEN)) == tuple(sorted(tbox.FORMFUNKTIONEN))
    assert tbox.QUELLVERFAHREN_WERTE["formfunktion"] == tbox.FORMFUNKTIONEN


# --------------------------------------------------------------------------- #
# Verhalten je Kommando, auf dem zweiten Baldrian-Lauf
# --------------------------------------------------------------------------- #

@pytest.fixture()
def kopie(tmp_path, gefahrener_fall):
    fall = tmp_path / "fall"
    shutil.copytree(gefahrener_fall, fall)
    return fall


def _fahre(kommando: str, fall: Path, name: str) -> int:
    """Das Kommando wie im Lauf; Ausgaben unter ``<fall>/abgeleitet/probe/<name>``
    (die Uebernahme schreibt nur in den Fall)."""
    argv = _aufruf(kommando, fall, ["--red-anteile-datei", AUSKUNFT], _ziel(fall, name))
    try:
        code = MAINS[kommando](argv)
    except SystemExit as exc:
        # Ein Abbruch mit Meldung ist Exit 1 an der Kommandozeile.
        if not isinstance(exc.code, int):
            print(exc.code, file=sys.stderr)
        return exc.code if isinstance(exc.code, int) else 1
    return int(getattr(code, "exit_code", code))


def _ziel(fall: Path, name: str) -> Path:
    return fall / "abgeleitet" / "probe" / name


def _neu_verankern(fall: Path) -> None:
    """Der Schichtbeleg bindet die Bytes der Spez: Nach einer anderen Spez
    ist er nicht mehr der dieses Standes (die Konsumenten verweigern ihn).
    Also wird er auf der neuen Spez neu erzeugt — wie im Lauf."""
    from rechner_pipeline.gates import verankerung_belegen

    argv = _aufruf("verankerung_belegen", fall, ["--red-anteile-datei", AUSKUNFT],
                   _ziel(fall, "verankerung"))
    argv[argv.index("--out") + 1] = str(
        fall / "abgeleitet" / "schichten" / "verankerung_schichten.json")
    assert verankerung_belegen.main(argv) == 0


@pytest.mark.parametrize("kommando", KOMMANDOS)
def test_eine_spez_ohne_tarifwerk_wird_verweigert(kommando, kopie, capsys):
    """Im Scope bestand rechnet kein Kommando ohne belegte Regel — vorher
    rechnete es mit der Vorgabe des eigenen Geschaefts weiter."""
    spez_variante(FIXTURE / "klv-tg2015.spez.json", kopie, GENERATION,
                  ohne=["tarifwerk.stoab_je_baustein"], pruefen=False)
    assert _fahre(kommando, kopie, "aus") == 2
    meldung = capsys.readouterr().err
    assert "tarifwerk.stoab_je_baustein nicht belegt" in meldung, meldung
    assert "Ausweg" in meldung


@pytest.mark.parametrize("kommando", KOMMANDOS)
@pytest.mark.parametrize("schalter", sorted(tr.ENTFALLENE_SCHALTER))
def test_ein_entfallener_schalter_wird_sprechend_verweigert(kommando, schalter, capsys):
    """Kein Schalter ueberstimmt die belegte Regel; wer einen tippt, erfaehrt,
    wo sie jetzt steht. Exit 2, bevor irgendetwas gelesen wird."""
    with pytest.raises(SystemExit) as exc:
        MAINS[kommando]([schalter, "wert"])
    assert exc.value.code == 2
    meldung = capsys.readouterr().err
    assert f"{schalter} entfaellt" in meldung
    assert f"Abschnitt {tr.ENTFALLENE_SCHALTER[schalter]}" in meldung


def _bericht(pfad: Path) -> dict:
    return json.loads(pfad.read_text(encoding="utf-8"))


def _variante(fall: Path, **regeln) -> None:
    """Dieselbe Lieferung unter einer anderen belegten Regel: Spez ersetzen,
    Schichtbeleg auf ihr neu erzeugen."""
    spez_variante(FIXTURE / "klv-tg2015.spez.json", fall, GENERATION, **regeln)
    _neu_verankern(fall)


def test_uebernahme_zwei_tarifwerke_zwei_bestaende(kopie, capsys):
    """Die Regel wirkt: Mit ``scheiben_mit_gamma1`` (Bedingungswerk Ziffer 3)
    traegt jede Alt-Scheibe das gamma1 ihrer Zelle, und der Config-Abschnitt
    sagt es. Mit der Regel des eigenen Geschaefts (ohne gamma1) reproduziert
    keine Zerlegung den gelieferten Beitrag der Serien — die Uebernahme
    verweigert, statt einen falschen Anfangszustand zu fuehren. Vorher war
    genau das der stille Weg: Schalter vergessen, PLV-Regel gerechnet."""
    from rechner_pipeline.bestand.parquet_io import read_portfolio

    assert _fahre("bestand_uebernehmen", kopie, "a") == 0
    ua = _ziel(kopie, "a") / "uebernahme"
    a = read_portfolio(ua / "scheiben.parquet")
    assert len(a) > 0 and (a["gamma1"] > 0).all()
    assert "scheiben_mit_gamma1 = true" in (ua / "generation-zellen.toml").read_text("utf-8")
    capsys.readouterr()
    spez_variante(FIXTURE / "klv-tg2015.spez.json", kopie, GENERATION,
                  tarifwerk={"scheiben_mit_gamma1": False})
    assert _fahre("bestand_uebernehmen", kopie, "b") == 1
    assert "ohne ableitbaren Anfangszustand" in capsys.readouterr().err
    assert not (_ziel(kopie, "b") / "uebernahme" / "bestand.parquet").exists()


def test_verankerung_zwei_ausgestaltungen_zwei_schichten(kopie):
    """Die Formfunktion der Korrekturschicht steht in der Spez: Mit
    ``konstantes_fenster`` traegt jede Schicht diese Form und ihr Fenster."""
    assert _fahre("verankerung_belegen", kopie, "a") == 0
    spez_variante(FIXTURE / "klv-tg2015.spez.json", kopie, GENERATION,
                  quellverfahren={"formfunktion": "konstantes_fenster", "fenster": 30})
    _fahre("verankerung_belegen", kopie, "b")
    a = _bericht(_ziel(kopie, "a") / "verankerung_schichten.json")
    b = _bericht(_ziel(kopie, "b") / "verankerung_schichten.json")
    assert {s["hist"]["formfunktion"] for s in a["schichten"].values()} == {
        "proportional_zur_basis"}
    formen_b = {s["hist"]["formfunktion"] for s in b["schichten"].values()}
    assert formen_b == {"konstantes_fenster"}, formen_b
    assert b["provenienz"]["parameter"]["fenster"] == 30


def test_aktuarieller_test_zwei_tarifwerke_zwei_urteile(kopie):
    """Stornoabzug je Baustein oder je Vertrag: dieselbe Stichprobe, zwei
    Rueckkaufswerte — der Lauf mit der belegten Regel besteht."""
    assert _fahre("aktuartest_lauf", kopie, "a") == 0
    _variante(kopie, tarifwerk={"stoab_je_baustein": False})
    assert _fahre("aktuartest_lauf", kopie, "b") == 0
    a = _bericht(_ziel(kopie, "a") / "at.json")
    b = _bericht(_ziel(kopie, "b") / "at.json")
    assert a["test_bestanden"] is True
    assert a["tarifregeln"]["tarifwerk"]["stoab_je_baustein"] is True
    assert b["tarifregeln"]["tarifwerk"]["stoab_je_baustein"] is False
    assert b["bestanden"] < a["bestanden"]


def test_migrationscontrolling_zwei_stichtage_der_quelle_zwei_urteile(kopie):
    """Das Deckungskapital der Lieferung zum Vertragsjahrestag oder
    kalendertaeglich: Auf dem falschen Zeitpunkt misst das Controlling
    Reservezuwachs als Residuum."""
    assert _fahre("migrationssuite_lauf", kopie, "a") == 0
    _variante(kopie, quellverfahren={"dk_stichtag": "kalendertag"})
    assert _fahre("migrationssuite_lauf", kopie, "b") == 0
    a = _bericht(_ziel(kopie, "a") / "suite.json")
    b = _bericht(_ziel(kopie, "b") / "suite.json")
    assert a["bestanden"] == a["anzahl"]
    assert b["bestanden"] < a["bestanden"]
    assert b["tarifregeln"]["quellverfahren"]["dk_stichtag"] == "kalendertag"


def test_migrationscontrolling_verweigert_eine_config_mit_anderem_tarifwerk(kopie, capsys):
    """Der Fuehrungswert rechnet mit dem Tarifwerk der Config; es muss das der
    Spez sein, sonst stuende im selben Beleg ein Wert nach einer anderen
    Regel."""
    _variante(kopie, tarifwerk={"stoab_je_baustein": False})
    capsys.readouterr()
    assert _fahre("migrationssuite_lauf", kopie, "b") == 2
    assert "Config der Fuehrung" in capsys.readouterr().err


def test_fuehrungsprobe_zwei_tarifwerke_zwei_urteile(kopie):
    """Die Probe haelt Config und Uebernahmebeleg gegen das Tarifwerk der
    SPEZ: mit der belegten Regel bestanden, mit einer anderen ein Befund."""
    assert _fahre("fuehrungsprobe", kopie, "a") == 0
    _variante(kopie, tarifwerk={"stoab_je_baustein": False})
    assert _fahre("fuehrungsprobe", kopie, "b") == 1
    b = _bericht(_ziel(kopie, "b") / "probe.json")
    assert "tarifwerk" in {f["art"] for f in b["befunde"]}
    assert "--stoab-je-baustein" not in b["provenienz"]["aufruf"]
    assert b["provenienz"]["parameter"]["tarifregeln"]["tarifwerk"]["stoab_je_baustein"] is False


def test_der_umfang_der_teilkuendigung_erreicht_jeden_pruefauftrag(kopie, monkeypatch):
    """Gefunden beim Nachzug: ``--tku-umfang`` wirkte nur auf den
    Anfangszustand; die Auftraege der Pruefstrecke trugen ihn nie, und die
    Engine leitete ihn je Vertrag aus dem Verfahren ab. Jetzt geht der
    belegte Umfang in jeden Auftrag beider Pruefstrecken."""
    from rechner_pipeline.gates import aktuartest_lauf, migrationssuite_lauf

    gesehen = {}

    def faenger(name, echt):
        def f(auftraege, *a, **k):
            gesehen[name] = {v.tku_umfang for v in auftraege}
            return echt(auftraege, *a, **k)
        return f

    monkeypatch.setattr(migrationssuite_lauf, "pruefe_bestand",
                        faenger("suite", migrationssuite_lauf.pruefe_bestand))
    monkeypatch.setattr(aktuartest_lauf, "pruefe_stichprobe",
                        faenger("at", aktuartest_lauf.pruefe_stichprobe))
    assert _fahre("migrationssuite_lauf", kopie, "s") == 0
    assert _fahre("aktuartest_lauf", kopie, "t") == 0
    assert gesehen == {"suite": {"grundversicherung"}, "at": {"grundversicherung"}}


# --------------------------------------------------------------------------- #
# P-Q3: Pflicht im Scope bestand, nicht im Scope tarif
# --------------------------------------------------------------------------- #

def _pq3_fall(tmp_path: Path, scope: str, bloecke: Dict[str, Dict] | None):
    from rechner_pipeline.ontologie.abox import abox_pfad, lade_aus_bytes, speichere
    from rechner_pipeline.ontologie.aussage import Provenienz, belegt, nicht_belegt
    from tests.e2e_fixture import bereite_pk1_fall

    fall = bereite_pk1_fall(tmp_path, scope=scope)
    abox = lade_aus_bytes(abox_pfad(fall).read_bytes())
    gen = abox.generationen[0]
    quelle = gen.quellen[0]
    prov = Provenienz(quelle_datei=quelle.datei, quelle_sha256=quelle.sha256,
                      fundstelle="Bedingungswerk", akteur="test/tarifregeln@abc1234",
                      erhoben_am="2026-10-01T00:00:00Z")
    # Der Produzent der Fixture liefert die Regeln im Scope bestand selbst;
    # hier zaehlt nur, was der Test hinlegt.
    for block in tbox.GENERATIONS_BLOECKE:
        gen.block(block).clear()
    for block, werte in (bloecke or {}).items():
        gen.block(block).update({
            m: (nicht_belegt() if w is None else belegt(w, [prov]))
            for m, w in werte.items()})
    speichere(abox, fall)
    return fall


def _pq3(fall: Path):
    from rechner_pipeline.gates.abox_validate import main as pq3

    return pq3(["--fall", str(fall), "--repo-root", str(REPO)])


def _codes(ergebnis) -> set:
    return {e["code"] for e in ergebnis.errors}


VOLLSTAENDIG = {
    "tarifwerk": {"scheiben_mit_gamma1": False, "stoab_je_baustein": True,
                  "red_verfahren": "mit_abzug", "tku_umfang": "alle_bausteine"},
    "quellverfahren": {"red_verfahren": "mit_abzug", "erhoehungssatz": None,
                       "dk_stichtag": "kalendertag",
                       "formfunktion": "proportional_zur_basis"},
}


def test_pq3_verlangt_im_scope_bestand_die_tarifregeln(tmp_path):
    ergebnis = _pq3(_pq3_fall(tmp_path, "bestand", None))
    assert "tarifregeln" in _codes(ergebnis), ergebnis.errors
    text = next(e["message"] for e in ergebnis.errors if e["code"] == "tarifregeln")
    assert "tarifwerk.red_verfahren nicht belegt" in text and "Ausweg" in text
    assert "quellverfahren.erhoehungssatz nicht erhoben" in text
    assert ergebnis.exit_code != 0


def test_pq3_im_scope_tarif_bleibt_es_ausgewiesen(tmp_path):
    """Im Scope tarif keine Pflicht — die Coverage weist die Luecke aber aus."""
    fall = _pq3_fall(tmp_path, "tarif", None)
    ergebnis = _pq3(fall)
    assert "tarifregeln" not in _codes(ergebnis), ergebnis.errors
    coverage = json.loads((fall / "abgeleitet" / "abox" / "coverage.json").read_text("utf-8"))
    assert coverage["tarifregeln_bestand_vollstaendig"] is False
    assert coverage["generationen"][0]["tarifregeln_bestand"]["luecken"]
    assert ergebnis.summary["scope"] == "tarif"


def test_pq3_nimmt_vollstaendige_tarifregeln_an(tmp_path):
    """Belegt, mit Quelle; der Dynamiksatz ausdruecklich nicht belegt (der
    Tarif kennt keinen) ist erhoben und genuegt."""
    fall = _pq3_fall(tmp_path, "bestand", VOLLSTAENDIG)
    ergebnis = _pq3(fall)
    assert "tarifregeln" not in _codes(ergebnis), ergebnis.errors
    assert ergebnis.summary["tarifregeln_bestand"] == {"klv/tg2012": True}
    coverage = json.loads((fall / "abgeleitet" / "abox" / "coverage.json").read_text("utf-8"))
    assert coverage["tarifregeln_bestand_vollstaendig"] is True


@pytest.mark.parametrize("aenderung, text", [
    ({"tarifwerk": {"tku_umfang": None}}, "tarifwerk.tku_umfang nicht belegt"),
    ({"quellverfahren": {"formfunktion": "konstantes_fenster"}},
     "quellverfahren.fenster nicht belegt"),
])
def test_pq3_findet_jede_luecke(tmp_path, aenderung, text):
    bloecke = {b: dict(w) for b, w in VOLLSTAENDIG.items()}
    for block, werte in aenderung.items():
        bloecke[block].update(werte)
    ergebnis = _pq3(_pq3_fall(tmp_path, "bestand", bloecke))
    meldungen = " ".join(e["message"] for e in ergebnis.errors if e["code"] == "tarifregeln")
    assert text in meldungen, ergebnis.errors


def test_pq3_und_kommando_sprechen_dieselbe_regel():
    """EINE Regel (``tbox.tarifregeln_luecken``): was P-Q3 als vollstaendig
    annimmt, rechnet jedes Kommando; die Funktion der Spez ruft dieselbe."""
    belegt = {b: {m: w for m, w in werte.items() if w is not None}
              for b, werte in VOLLSTAENDIG.items()}
    assert tbox.tarifregeln_luecken(belegt) == []
    regeln = tr.tarifregeln_der_spez(_Spez(belegt["tarifwerk"], belegt["quellverfahren"]))
    assert regeln.erhoehungssatz is None
    quelle = (SRC / "spez" / "tarifregeln.py").read_text(encoding="utf-8")
    assert _aufrufe(quelle, ("tarifregeln_luecken",)) == (1,)
    quelle = (SRC / "ontologie" / "coverage.py").read_text(encoding="utf-8")
    assert _aufrufe(quelle, ("tarifregeln_luecken",)) == (1,)


def test_spez_der_fixture_liegt_im_fall(gefahrener_fall):
    """Der gefahrene Lauf traegt die Spez der Fixture — sie ist die eine
    Fassung, mit der alle fuenf Kommandos oben gerechnet haben."""
    assert spez_pfad(gefahrener_fall, GENERATION).read_bytes() == (
        FIXTURE / "klv-tg2015.spez.json").read_bytes()
