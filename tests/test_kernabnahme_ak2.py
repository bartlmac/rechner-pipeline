"""A-K2 im Ablauf: der Kernstand des Falls, zwei Pruefungen, eine benannte Ausnahme.

Entscheid des Maintainers 2026-10-01 (ADR-018, Nachtrag 2026-10-01):
"Zeichnung Rechenkernentwickler — wir sollten dieses Gate formell
einpflegen. Das sollten zwei Pruefungen sein: (1) Code-Diffs qualitative
Pruefung entlang der Module mit den Commits; (2) Ergebnis des
Regressionstests — das ist noch nicht fertig, nur ein Platzhalter mit dem
Verweis." Und: "bitte als Ausnahme erfassen und nicht als 'bestanden'."
Zeitpunkt: vor dem Merge — A-M4 verlangt die A-K2-Annahme.

Gemessen vor dem Bau (Stand e72a3ed): A-K2 war im Gate und im
Belegvertrag vorhanden, aber unwirksam — kein Produzent, kein Gate
verlangte es, der Kern wuchs ausserhalb jedes Falls von 3.6.0 auf 3.15.0.

Was hier gehalten wird:

* Prozess: A-M4 ohne A-K2 wird verweigert; mit A-K2 angenommen und
  gepinnt (``kernstand``), in jedem Scope; die Rollenregel gilt auch
  fuer A-K2 (Rolle ``mensch/rechenkern``, eigener Schluessel).
* Pruefung 1: der Aenderungsbeleg entlang der Module, mit Commits — gegen
  ein eigenes kleines Git-Repo (die CI klont flach, ``HEAD~1`` gibt es
  dort nicht); die Nachrechnung im Gate faengt erfundene Commits und
  geschoente Diffstats; Commit-Betreffzeilen sind Fremdtext.
* Pruefung 2: die Ausnahme — woertlich in Beleg, Sicht, Snapshot, Ledger,
  und kein Artefakt der Kette nennt die Regression "bestanden"; zwei
  Waechter halten Konstante und Produzent zusammen; ein echter Beleg wird
  nach der alten Regel geprueft.

Knoten: system/entscheid
"""

from __future__ import annotations

import json
import re
import subprocess
from pathlib import Path

import pytest

from rechner_pipeline.gates import gate_entscheid, kernstand_belegen
from rechner_pipeline.gates.gate_entscheid import (
    kernstand_belege_pruefen,
    pruefe_kernaenderung,
    pruefe_kernregression,
)
from rechner_pipeline.models import kernabnahme as ka
from rechner_pipeline.models import standabnahme as sa
from rechner_pipeline.models.belegrollen import belegrollen
from tests.zeichnung_fixture import RECHENKERN, annahme_args, zeichne_kernstand

REPO = Path(__file__).resolve().parents[1]
SRC = REPO / "src" / "rechner_pipeline"

#: Woerter, mit denen ein Artefakt eine Regression als gelaufen ausgaebe.
ERGEBNISWORTE = re.compile(
    r"\b(bestanden|gruen|grün|ok|passed|erfolgreich|geprueft|geprüft)\b", re.I)


# --------------------------------------------------------------------------- #
# Hilfen
# --------------------------------------------------------------------------- #


def _tariffall(tmp_path: Path) -> Path:
    from tests.test_pk1_am4_beweisvertrag import _bereite_fall, _o3_tg2012

    fall = _bereite_fall(tmp_path, ("klv/tg2012",), mit_kernstand=False)
    assert _o3_tg2012(fall).exit_code == 0
    return fall


def _am4(fall: Path):
    from tests.test_pk1_am4_beweisvertrag import _p9_annahme

    return _p9_annahme(fall, "A-M4", "Migration abgenommen")


def _git(repo: Path, *argv: str) -> str:
    return subprocess.run(
        ["git", "-c", "user.name=Pruefung", "-c", "user.email=p@example.invalid",
         "-c", "commit.gpgsign=false", *argv],
        cwd=repo, capture_output=True, text=True, check=True).stdout


def _schreibe(pfad: Path, text: str) -> None:
    pfad.parent.mkdir(parents=True, exist_ok=True)
    pfad.write_text(text, encoding="utf-8")


@pytest.fixture()
def kernrepo(tmp_path):
    """Ein kleines Repo mit dem Gegenstand von A-K2: Kern, Referenzwerte,
    Grundsatzdokumentation, Tarifplan — und zwei Commits darauf."""
    repo = tmp_path / "repo"
    kern = repo / ka.KERN_PAKET
    _schreibe(kern / "__init__.py", '__version__ = "1.0.0"\n')
    _schreibe(kern / "rechenkern.py", "x = 1\n")
    _schreibe(kern / "tafeln.xml", "<tafeln/>\n")
    _schreibe(repo / ka.KERN_REFERENZWERTE / "referenz_a.json", "{}\n")
    _schreibe(repo / "docs/mathematik/grundsatzdokumentation.md", "# Grundsatz\n")
    _schreibe(repo / "docs/tarifplaene/klv.md", "# KLV\n")
    _schreibe(repo / "README.md", "ausserhalb des Gegenstands\n")
    _git(repo.parent, "init", "-q", "-b", "main", str(repo))
    _git(repo, "add", "-A")
    _git(repo, "commit", "-q", "-m", "feat: Ausgangsstand")
    _git(repo, "tag", "abgenommen")
    _schreibe(kern / "__init__.py", '__version__ = "1.1.0"\n')
    _schreibe(kern / "rechenkern.py", "x = 1\ny = 2\n")
    _schreibe(repo / ka.KERN_REFERENZWERTE / "referenz_a.json", '{"a": 1}\n')
    _schreibe(repo / "README.md", "geaendert, aber nicht Gegenstand\n")
    _git(repo, "add", "-A")
    _git(repo, "commit", "-q", "-m", "fix(kern)!: <b>fett</b> | `code` **x** [a](b) ~~s~~")
    return repo


# --------------------------------------------------------------------------- #
# Prozess: A-M4 verlangt A-K2
# --------------------------------------------------------------------------- #


def test_a_m4_ohne_a_k2_wird_verweigert_und_mit_a_k2_angenommen(tmp_path):
    """DIE Prozessregel: Jeder Fall traegt die Abnahme seines Kernstands.

    Rot vor dem Bau: A-M4 nahm an, ohne dass irgendwer den Kern abgenommen
    hatte. Mutationsprobe: den A-K2-Block im A-M4-Zweig auskommentieren ->
    die erste Annahme geht durch -> rot."""
    fall = _tariffall(tmp_path)
    ohne = _am4(fall)
    assert ohne.exit_code != 0
    meldung = ohne.errors[0]["message"]
    assert "A-K2" in meldung and "kernstand_belegen" in meldung, meldung
    assert not list((fall / "entscheide").glob("A-M4-*.json"))

    ak2 = zeichne_kernstand(fall, REPO)
    mit = _am4(fall)
    assert mit.exit_code == 0, mit.errors
    (am4_pfad,) = list((fall / "entscheide").glob("A-M4-*.json"))
    am4 = json.loads(am4_pfad.read_text(encoding="utf-8"))
    assert am4["pflichtbelege"]["kernstand"] == [ak2.summary["snapshot_sha256"]]
    eintrag = am4["standabnahmen"]["kernstand"]
    assert eintrag["weg"] == sa.ABNAHME_IM_FALL
    assert eintrag["anzeige"] == (sa.anzeige_im_fall("A-K2", ak2.summary["snapshot_sha256"])
                                  + "; " + ka.ANZEIGE_REGRESSION)
    assert mit.summary["standabnahmen"] == am4["standabnahmen"]
    # Der T-Box-Stand: die A-O1-Annahme, die die Fall-Fixture zeichnet
    # (zeichne_tboxstand); die Basislinie (Weg c) ist mit der Erstabnahme
    # entfallen (ADR-025).
    (ao1,) = list((fall / "entscheide").glob("A-O1-*.json"))
    ao1_sha = json.loads(ao1.read_text(encoding="utf-8"))["snapshot_sha256"]
    assert am4["standabnahmen"]["tboxstand"]["weg"] == sa.ABNAHME_IM_FALL
    assert am4["pflichtbelege"]["tboxstand"] == [ao1_sha]


def test_die_pflichtrolle_steht_in_beiden_scopes():
    for scope in ("tarif", "bestand"):
        assert {"kernstand", "tboxstand", "tarifwerkstand"} <= set(belegrollen("A-M4", scope))


def test_a_k2_zeichnet_nur_die_rolle_mensch_rechenkern(tmp_path):
    """Der Schluessel des Aktuariats zeichnet A-K2 nicht (getrennt je Rolle)."""
    fall = _tariffall(tmp_path)
    assert kernstand_belegen.main([
        "--fall", str(fall), "--repo-root", str(REPO), "--von", "HEAD",
        "--begruendung", "Probe"]).exit_code == 0
    falsch = gate_entscheid.main([
        "--fall", str(fall), "--gate", "A-K2", "--entscheid", "angenommen",
        "--entscheider", "x", "--begruendung", "y", "--repo-root", str(REPO),
        *annahme_args(fall)])
    assert falsch.exit_code != 0
    assert "A-K2" in falsch.errors[0]["message"], falsch.errors
    richtig = zeichne_kernstand(fall, REPO)
    snapshot = json.loads(Path(richtig.paths["snapshot"]).read_text(encoding="utf-8"))
    assert snapshot["rolle"] == RECHENKERN


def test_a_m4_verweigert_ein_a_k2_dessen_rollenfeld_nicht_die_rolle_des_schluessels_ist(tmp_path):
    """Dieselbe Regel wie fuer A-Q1 und A-M1 (Entscheid 2026-10-01):
    Rollenfeld gefaelscht, mit dem echten Schluessel neu signiert.

    Mutationsprobe: den zeichnende_rolle_fehler-Aufruf fuer A-K2 im A-M4-Zweig
    aussetzen -> Annahme -> rot."""
    from tests.test_abnahme_rolle_klasse import _behauptet, _neu_signiert

    fall = _tariffall(tmp_path)
    zeichne_kernstand(fall, REPO)
    (pfad,) = list((fall / "entscheide").glob("A-K2-*.json"))
    daten = json.loads(pfad.read_text(encoding="utf-8"))
    schluessel = (fall.parent / "p9-rechenkern.key").read_bytes()
    neu = _neu_signiert(daten, schluessel, **_behauptet(daten, "mensch/aktuariat"))
    pfad.unlink()
    (pfad.parent / f"A-K2-{neu['snapshot_sha256']}.json").write_text(
        json.dumps(neu, ensure_ascii=False), encoding="utf-8")
    am4 = _am4(fall)
    assert am4.exit_code != 0
    meldung = am4.errors[0]["message"]
    assert "A-K2" in meldung and "behauptet als Rolle" in meldung, meldung


def test_a_m4_haelt_die_gepinnten_belege_gegen_den_festen_ort(tmp_path):
    """Ein nach der A-K2-Zeichnung neu erzeugter Aenderungsbeleg (andere
    Begruendung) ist nicht der, den A-K2 gezeichnet hat."""
    fall = _tariffall(tmp_path)
    zeichne_kernstand(fall, REPO)
    assert kernstand_belegen.main([
        "--fall", str(fall), "--repo-root", str(REPO), "--von", "HEAD",
        "--begruendung", "eine andere Vorlage"]).exit_code == 0
    am4 = _am4(fall)
    assert am4.exit_code != 0
    assert "nicht die Fassung, die A-K2 pinnt" in am4.errors[0]["message"], am4.errors


# --------------------------------------------------------------------------- #
# Pruefung 2: die Ausnahme
# --------------------------------------------------------------------------- #


def test_a_k2_fuehrt_die_ausnahme_woertlich_in_beleg_sicht_snapshot_und_ledger(tmp_path):
    fall = _tariffall(tmp_path)
    ergebnis = zeichne_kernstand(fall, REPO)
    regression = json.loads((fall / ka.REGRESSION_RELATIV).read_text(encoding="utf-8"))
    assert regression["zustand"] == "nicht_gefahren"
    assert regression["grund"] == "Werkzeug noch nicht erstellt"
    sicht = (fall / ka.SICHT_RELATIV).read_text(encoding="utf-8")
    assert "Regression: Ausnahme — nicht gefahren, Werkzeug noch nicht erstellt" in sicht
    snapshot = json.loads(Path(ergebnis.paths["snapshot"]).read_text(encoding="utf-8"))
    assert snapshot["ausnahmen"] == {
        "regression": "Ausnahme — nicht gefahren, Werkzeug noch nicht erstellt"}
    assert ergebnis.summary["anzeige"] == [ka.ANZEIGE_REGRESSION]
    assert ergebnis.summary["deckung"] == ka.DECKUNG_UNTER_AUSNAHME


def _regressionstexte(fall: Path, ak2, am4) -> dict:
    """Jede Stelle der Kette, die etwas ueber die Regression sagt."""
    sicht = (fall / ka.SICHT_RELATIV).read_text(encoding="utf-8")
    abschnitt = sicht.split("## Pruefung 2 — Regression", 1)[1].split("\n## ", 1)[0]
    snapshot = json.loads(Path(ak2.paths["snapshot"]).read_text(encoding="utf-8"))
    diagnostics = fall / "abgeleitet" / "diagnostics"
    ledger = json.loads((diagnostics / "gate_entscheid_am4.gate.json").read_text(encoding="utf-8"))
    ledger_ak2 = json.loads((diagnostics / "gate_entscheid_ak2.gate.json").read_text(
        encoding="utf-8"))
    return {
        "ledger_ak2.summary": json.dumps({k: (ledger_ak2.get("summary") or {}).get(k) for k in
                                          ("ausnahmen", "anzeige", "deckung")},
                                         ensure_ascii=False),
        "regression.json": (fall / ka.REGRESSION_RELATIV).read_text(encoding="utf-8"),
        "sicht": abschnitt,
        "snapshot.ausnahmen": json.dumps(snapshot["ausnahmen"], ensure_ascii=False),
        "ak2.summary": json.dumps({k: ak2.summary.get(k) for k in
                                   ("ausnahmen", "anzeige", "deckung")}, ensure_ascii=False),
        "am4.summary.standabnahmen": json.dumps(am4.summary["standabnahmen"]["kernstand"],
                                                ensure_ascii=False),
        "ledger.summary": json.dumps(
            ((ledger.get("summary") or {}).get("standabnahmen") or {}).get("kernstand"),
                                     ensure_ascii=False),
    }


def test_kein_artefakt_der_kette_nennt_die_regression_bestanden(tmp_path):
    """(a) des Auftrags: Die Ausnahme ist kein Ergebnis — nirgends.

    Positivkontrolle: Der Detektor findet das Wort in einem Text, der die
    Regression als bestanden fuehrte."""
    assert ERGEBNISWORTE.search('{"regression": "bestanden"}')
    assert ERGEBNISWORTE.search("Regression: ok")
    fall = _tariffall(tmp_path)
    ak2 = zeichne_kernstand(fall, REPO)
    am4 = _am4(fall)
    assert am4.exit_code == 0, am4.errors
    texte = _regressionstexte(fall, ak2, am4)
    assert all(texte.values()), texte
    befunde = {name: ERGEBNISWORTE.findall(text) for name, text in texte.items()
               if ERGEBNISWORTE.search(text)}
    assert befunde == {}
    regression = json.loads(texte["regression.json"])
    assert set(regression) == ka.AUSNAHME_FELDER
    assert not {"vertraege_geprueft", "vertraege_gesamt", "abweichungen",
                "bestanden"} & set(regression)


def _belege(tmp_path: Path):
    fall = tmp_path / "fall"
    (fall / "abgeleitet" / "kern").mkdir(parents=True)
    aenderung = kernstand_belegen.baue_aenderungsbeleg(REPO, "HEAD", "Probe")
    return fall, aenderung


@pytest.mark.parametrize("abweichend, erwartet", [
    ({"vertraege_geprueft": 0, "vertraege_gesamt": 0}, "saehe wie ein Ergebnis aus"),
    ({"grund": "spaeter"}, "grund muss"),
    ({"zustand": "teilweise_gefahren"}, "zustand muss"),
    ({"grundlage": "keine"}, "grundlage muss"),
    ({"kern_sha256": "e" * 64}, "anderen Uebergang"),
])
def test_die_ausnahme_nimmt_nichts_anderes_unvollstaendiges_an(tmp_path, abweichend, erwartet):
    fall, aenderung = _belege(tmp_path)
    daten = {**kernstand_belegen.regressionsausnahme(aenderung), **abweichend}
    pfad = fall / ka.REGRESSION_RELATIV
    pfad.write_text(json.dumps(daten), encoding="utf-8")
    fehler = pruefe_kernregression(pfad, fall, aenderung=aenderung)
    assert any(erwartet in f for f in fehler), fehler
    sauber = kernstand_belegen.regressionsausnahme(aenderung)
    pfad.write_text(json.dumps(sauber), encoding="utf-8")
    assert pruefe_kernregression(pfad, fall, aenderung=aenderung) == []


def test_ohne_die_konstante_nimmt_weder_a_k2_noch_a_m4_die_ausnahme_an(tmp_path, monkeypatch):
    """Kippt die Konstante, faellt die Ausnahme ueberall — auch unter einer
    A-K2-Annahme, die schon gezeichnet ist (A-M4 rechnet die Belege nach).

    Mutationsprobe: in _pruefe_regressionsausnahme die Abfrage der Konstante
    entfernen -> beide Annahmen gehen durch -> rot."""
    fall = _tariffall(tmp_path)
    zeichne_kernstand(fall, REPO)
    monkeypatch.setattr(ka, "REGRESSION_AUSNAHME_ERLAUBT", False)
    am4 = _am4(fall)
    assert am4.exit_code != 0
    assert "nicht mehr erlaubt" in am4.errors[0]["message"], am4.errors
    fehler, _, _ = kernstand_belege_pruefen(fall, REPO)
    assert any("nicht mehr erlaubt" in f for f in fehler), fehler


def _echte_regression(aenderung: dict, **abweichend) -> dict:
    daten = {
        "schema_version": kernstand_belegen.KERN_REGRESSION_SCHEMA_VERSION,
        **{feld: aenderung[feld] for feld in ka.BINDUNGSFELDER},
        "bestand_sha256": "a" * 64, "vertraege_gesamt": 3, "vertraege_geprueft": 3,
        "abweichungen": [{"police_id": "P-1", "groesse": "dk", "vorher": 1.0,
                          "nachher": 1.5, "differenz": 0.5}],
    }
    daten.update(abweichend)
    return daten


def test_solange_es_kein_werkzeug_gibt_ist_jedes_ergebnis_eine_behauptung(tmp_path):
    """Pruefrunde G (G10, als Haertung gebaut; Entscheid des Maintainers):
    Bis zu ihrem Werkzeug ist die Regression eine benannte AUSNAHME, nie
    "bestanden". Ein handgeschriebener Ergebnis-Beleg — formal stimmig,
    gebunden, sauberer Arbeitsbaum — hat niemand gefahren; A-K2 nimmt ihn
    nicht an, sonst verschwaende die Ausnahme aus dem signierten Snapshot,
    waehrend die Sicht des Pruefers sie weiter zeigt.

    Rot vor dem Fix: ``[]``. Mutationsprobe: die Abfrage der Konstante im
    Ergebnis-Zweig von ``pruefe_kernregression`` entfernen -> rot."""
    assert ka.REGRESSION_AUSNAHME_ERLAUBT is True
    fall, aenderung = _belege(tmp_path)
    sauber = {**aenderung, "git": {**aenderung["git"], "dirty": "nein"}}
    pfad = fall / ka.REGRESSION_RELATIV
    pfad.write_text(json.dumps(_echte_regression(sauber)), encoding="utf-8")
    fehler = pruefe_kernregression(pfad, fall, aenderung=sauber)
    assert len(fehler) == 1 and "kein Werkzeug" in fehler[0], fehler
    assert "Ausnahme" in fehler[0] and "kernstand_belegen" in fehler[0], fehler
    # Die Ausnahme selbst bleibt die eine angenommene Form.
    pfad.write_text(json.dumps(kernstand_belegen.regressionsausnahme(aenderung)),
                    encoding="utf-8")
    assert pruefe_kernregression(pfad, fall, aenderung=aenderung) == []


def test_ein_echter_regressionsbeleg_wird_nach_der_alten_regel_geprueft(tmp_path, monkeypatch):
    """(c) des Auftrags: Stichprobe, Bindung, sauberer Arbeitsbaum. Der
    Ergebnis-Zweig gilt erst, wenn die Konstante kippt (es ein Werkzeug
    gibt) — der Test stellt sie ausdruecklich um (Pruefrunde G, G10)."""
    monkeypatch.setattr(ka, "REGRESSION_AUSNAHME_ERLAUBT", False)
    fall, aenderung = _belege(tmp_path)
    sauber = {**aenderung, "git": {**aenderung["git"], "dirty": "nein"}}
    pfad = fall / ka.REGRESSION_RELATIV
    pfad.write_text(json.dumps(_echte_regression(sauber)), encoding="utf-8")
    assert pruefe_kernregression(pfad, fall, aenderung=sauber) == []
    pfad.write_text(json.dumps(_echte_regression(sauber, vertraege_geprueft=2)), encoding="utf-8")
    assert any("Stichprobe" in f for f in pruefe_kernregression(pfad, fall, aenderung=sauber))
    schmutzig = {**aenderung, "git": {**aenderung["git"], "dirty": "ja"}}
    pfad.write_text(json.dumps(_echte_regression(schmutzig)), encoding="utf-8")
    assert any("nicht reproduzierbar" in f
               for f in pruefe_kernregression(pfad, fall, aenderung=schmutzig))
    assert ka.ausnahmen_fuer(_echte_regression(sauber)) == {}


# --------------------------------------------------------------------------- #
# Waechter: Konstante und Produzent gehoeren zusammen
# --------------------------------------------------------------------------- #

#: Wer ein Feld des echten Regressionsbelegs nennt. Heute nur der Pruefer.
PRUEFER_DER_REGRESSION = {"gates/gate_entscheid.py"}


def _baut_regressionsergebnis(quelle: str) -> bool:
    """Ob ein Modul ein Ergebnis der Regression BAUT: ein Dict-Literal oder
    ``dict(...)`` mit dem Schluessel ``vertraege_geprueft``. Lesen
    (``beleg.get("vertraege_geprueft")``) und Erwaehnen zaehlen nicht."""
    import ast

    for knoten in ast.walk(ast.parse(quelle)):
        if isinstance(knoten, ast.Dict) and any(
                isinstance(k, ast.Constant) and k.value == "vertraege_geprueft"
                for k in knoten.keys):
            return True
        if (isinstance(knoten, ast.Call) and isinstance(knoten.func, ast.Name)
                and knoten.func.id == "dict"
                and any(k.arg == "vertraege_geprueft" for k in knoten.keywords)):
            return True
    return False


def _regressionsproduzenten(wurzel: Path) -> set:
    """Module unter ``wurzel``, die ein Regressionsergebnis bauen, ausser dem
    Pruefer — also echte Produzenten."""
    return {str(p.relative_to(wurzel)) for p in wurzel.rglob("*.py")
            if _baut_regressionsergebnis(p.read_text(encoding="utf-8"))
            } - PRUEFER_DER_REGRESSION


def test_waechter_positivkontrolle_des_produzentendetektors(tmp_path):
    (tmp_path / "gates").mkdir()
    (tmp_path / "gates" / "lesend.py").write_text(
        'n = beleg.get("vertraege_geprueft")  # vertraege_geprueft\n', encoding="utf-8")
    assert _regressionsproduzenten(tmp_path) == set()
    (tmp_path / "gates" / "regression_lauf.py").write_text(
        'beleg = {"vertraege_geprueft": n}\n', encoding="utf-8")
    (tmp_path / "gates" / "regression_zwei.py").write_text(
        'beleg = dict(vertraege_geprueft=n)\n', encoding="utf-8")
    assert _regressionsproduzenten(tmp_path) == {"gates/regression_lauf.py",
                                                 "gates/regression_zwei.py"}


def test_waechter_die_konstante_kippt_nicht_ohne_produzenten():
    """(b), erste Haelfte: Ohne Produzent und ohne Ausnahme ist A-K2 wieder
    nicht zeichenbar — und damit A-M4 nicht."""
    if not ka.REGRESSION_AUSNAHME_ERLAUBT:
        assert _regressionsproduzenten(SRC), (
            "REGRESSION_AUSNAHME_ERLAUBT ist False, aber kein Modul erzeugt einen "
            "Regressionsbeleg — A-K2 und A-M4 waeren nicht zeichenbar")


def test_waechter_ein_produzent_laesst_die_ausnahme_nicht_stehen():
    """(b), zweite Haelfte: Sobald ein echter Produzent existiert, darf der
    Platzhalter nicht verrotten."""
    if _regressionsproduzenten(SRC):
        assert not ka.REGRESSION_AUSNAHME_ERLAUBT, (
            f"ein Regressionsproduzent existiert ({sorted(_regressionsproduzenten(SRC))}), "
            "die Ausnahme ist aber noch erlaubt — REGRESSION_AUSNAHME_ERLAUBT auf False "
            "und ADR-018/offene-punkte nachziehen")


def test_waechter_stand_heute():
    """Messung des Stands, damit die beiden Waechter nicht leer laufen."""
    assert ka.REGRESSION_AUSNAHME_ERLAUBT is True
    assert _regressionsproduzenten(SRC) == set()


# --------------------------------------------------------------------------- #
# Pruefung 1: die Aenderungen entlang der Module (eigenes Repo)
# --------------------------------------------------------------------------- #


def test_der_beleg_zeigt_die_aenderungen_je_modul_mit_den_commits(kernrepo):
    beleg = kernstand_belegen.baue_aenderungsbeleg(kernrepo, "abgenommen", "Probe")
    assert (beleg["von_version"], beleg["nach_version"]) == ("1.0.0", "1.1.0")
    assert beleg["veraendert"] is True
    module = {m["modul"]: m for m in beleg["module"]}
    assert set(module) == {
        f"{ka.KERN_PAKET}/__init__.py", f"{ka.KERN_PAKET}/rechenkern.py",
        f"{ka.KERN_PAKET}/tafeln.xml", ka.KERN_REFERENZWERTE,
        "docs/mathematik/grundsatzdokumentation.md"}
    rk = module[f"{ka.KERN_PAKET}/rechenkern.py"]
    assert (rk["hinzu"], rk["weg"], len(rk["commits"])) == (1, 0, 1)
    assert module[f"{ka.KERN_PAKET}/tafeln.xml"]["commits"] == []
    assert beleg["geaenderte_referenzwerte"] == ["referenz_a.json"]
    assert len(beleg["commits"]) == 1 and "README.md" not in json.dumps(beleg["module"])
    assert beleg["kern_alt_sha256"] != beleg["kern_sha256"]
    assert beleg["git"]["merge_base"] == beleg["git"]["referenz_commit"]


def test_ohne_aenderung_sagt_der_beleg_genau_das(kernrepo):
    beleg = kernstand_belegen.baue_aenderungsbeleg(kernrepo, "HEAD", "Probe")
    assert beleg["veraendert"] is False
    assert beleg["kern_alt_sha256"] == beleg["kern_sha256"]
    assert beleg["commits"] == [] and beleg["von_version"] == beleg["nach_version"]
    sicht = kernstand_belegen.rendere_sicht(beleg, kernstand_belegen.regressionsausnahme(beleg))
    assert "hat sich am Rechenkern nichts geaendert" in sicht


def test_nicht_committete_aenderungen_stehen_in_beleg_und_sicht(kernrepo):
    _schreibe(kernrepo / ka.KERN_PAKET / "rechenkern.py", "x = 1\ny = 2\nz = 3\n")
    _schreibe(kernrepo / ka.KERN_PAKET / "neu.py", "neu = True\n")
    beleg = kernstand_belegen.baue_aenderungsbeleg(kernrepo, "HEAD", "Probe")
    module = {m["modul"]: m for m in beleg["module"]}
    assert beleg["veraendert"] is True
    assert module[f"{ka.KERN_PAKET}/rechenkern.py"]["hinzu"] == 1
    assert module[f"{ka.KERN_PAKET}/neu.py"]["nicht_committet"] == [
        {"status": "??", "pfad": f"{ka.KERN_PAKET}/neu.py"}]
    sicht = kernstand_belegen.rendere_sicht(beleg, None)
    assert "nicht committet" in sicht and "ohne Commit-Beschreibung" in sicht


def test_die_commit_betreffzeile_ist_fremdtext(kernrepo):
    """HTML und Markdown aus einem Betreff werden maskiert, nicht gerendert."""
    beleg = kernstand_belegen.baue_aenderungsbeleg(kernrepo, "abgenommen", "Probe")
    betreff = beleg["commits"][0]["betreff"]
    assert betreff.startswith("fix(kern)!: <b>fett</b>")   # im Beleg: Daten, unveraendert
    sicht = kernstand_belegen.rendere_sicht(beleg, None)
    assert "<b>" not in sicht and "&lt;b&gt;fett&lt;/b&gt;" in sicht
    zeile = next(z for z in sicht.splitlines() if "fett" in z)
    assert "\\|" in zeile and "\\*\\*x\\*\\*" in zeile and "\\[a\\]" in zeile


def test_die_nachrechnung_faengt_einen_geschoenten_beleg(kernrepo, tmp_path):
    """Ein Beleg, der nur in sich stimmt, bezeugt nichts (T24-04): ein
    erfundener Commit, ein verschwiegenes Modul, ein geschoenter Diffstat.

    Mutationsprobe: die Nachrechnung in pruefe_kernaenderung abschalten ->
    die Faelschungen gehen durch -> rot."""
    fall = tmp_path / "fall"
    pfad = fall / ka.AENDERUNG_RELATIV
    echt = kernstand_belegen.baue_aenderungsbeleg(kernrepo, "abgenommen", "Probe")
    _schreibe(pfad, json.dumps(echt))
    assert pruefe_kernaenderung(pfad, fall, repo_root=kernrepo) == []

    def faelsche(aendern):
        daten = json.loads(json.dumps(echt))
        aendern(daten)
        _schreibe(pfad, json.dumps(daten))
        return pruefe_kernaenderung(pfad, fall, repo_root=kernrepo)

    def betreff(d):
        d["commits"][0]["betreff"] = "docs: nur Kommentare"
    def modul_weg(d):
        d["module"] = [m for m in d["module"] if not m["modul"].endswith("rechenkern.py")]
    def diffstat(d):
        for m in d["module"]:
            m["hinzu"] = m["weg"] = 0
    for aendern, feld in ((betreff, "commits"), (modul_weg, "module"), (diffstat, "module")):
        fehler = faelsche(aendern)
        assert fehler and feld in fehler[0] and "nicht der Kernstand" in fehler[0], fehler


@pytest.mark.parametrize("abweichend, erwartet", [
    ({"schema_version": 2}, "schema_version"),
    ({"von_version": "1.2.0"}, "laeuft nicht abwaerts"),
    ({"nach_version": "1.0.0"}, "nicht die Version, die der Kern traegt"),
    ({"kern_sha256": "0" * 64}, "kern_sha256 stimmt nicht"),
    ({"referenzwerte_sha256": "0" * 64}, "referenzwerte_sha256 stimmt nicht"),
    ({"begruendung": " "}, "begruendung fehlt"),
    ({"veraendert": "ja"}, "veraendert"),
])
def test_der_aenderungsbeleg_faengt_die_naheliegenden_faelschungen(
        kernrepo, tmp_path, abweichend, erwartet):
    fall = tmp_path / "fall"
    pfad = fall / ka.AENDERUNG_RELATIV
    _schreibe(pfad, json.dumps({
        **kernstand_belegen.baue_aenderungsbeleg(kernrepo, "abgenommen", "Probe"),
        **abweichend}))
    fehler = pruefe_kernaenderung(pfad, fall, repo_root=kernrepo)
    assert any(erwartet in f for f in fehler), fehler


def test_ein_von_neben_dem_zweig_wird_nicht_belegt(tmp_path):
    """Liegt der zuletzt abgenommene Stand nicht im lebenden Zweig, mischte
    die Differenz fremde Aenderungen hinein — der Produzent verweigert.

    Seit Pruefrunde G (G12) nimmt das Kommando nur einen ``--repo-root``, der
    das ausgefuehrte Paket traegt: Das Repo dieser Probe traegt deshalb eine
    inhaltsgleiche Kopie des Pakets (die Aenderungen liegen neben dem Kern)."""
    import shutil

    repo = tmp_path / "repo"
    shutil.copytree(SRC, repo / "src" / "rechner_pipeline",
                    ignore=shutil.ignore_patterns("__pycache__", "*.pyc"))
    _schreibe(repo / ka.KERN_REFERENZWERTE / "referenz_a.json", "{}\n")
    _schreibe(repo / "docs/mathematik/grundsatzdokumentation.md", "# Grundsatz\n")
    _schreibe(repo / "docs/tarifplaene/klv.md", "# KLV\n")
    _git(repo.parent, "init", "-q", "-b", "main", str(repo))
    _git(repo, "add", "-A")
    _git(repo, "commit", "-q", "-m", "feat: Ausgangsstand")
    _git(repo, "tag", "abgenommen")
    _git(repo, "checkout", "-q", "-b", "nebenzweig", "abgenommen")
    _schreibe(repo / "docs/tarifplaene/klv.md", "# KLV neben\n")
    _git(repo, "commit", "-q", "-am", "docs: daneben")
    _git(repo, "tag", "daneben")
    _git(repo, "checkout", "-q", "main")
    _schreibe(repo / "docs/mathematik/grundsatzdokumentation.md", "# Grundsatz, weiter\n")
    _git(repo, "commit", "-q", "-am", "docs: weiter")
    fall = tmp_path / "fall"
    fall.mkdir()
    (fall / "eingang.json").write_text("{}", encoding="utf-8")
    ergebnis = kernstand_belegen.main([
        "--fall", str(fall), "--repo-root", str(repo), "--von", "daneben",
        "--begruendung", "Probe"])
    assert ergebnis.exit_code != 0
    assert "kein Vorfahre" in ergebnis.errors[0]["message"], ergebnis.errors


def test_eine_von_angabe_wird_nie_eine_option(kernrepo):
    with pytest.raises(kernstand_belegen.KernstandFehler, match="keine Angabe"):
        kernstand_belegen.baue_aenderungsbeleg(kernrepo, "--output=/tmp/x", "Probe")


# --------------------------------------------------------------------------- #
# Darstellung: die Gate-Aufzaehler der Werkzeuge
# --------------------------------------------------------------------------- #


def _werkzeug(name: str):
    import importlib
    import sys

    pfad = str(REPO / "werkzeuge")
    if pfad not in sys.path:
        sys.path.insert(0, pfad)
    return importlib.import_module(name)


def test_die_darstellung_verlangt_jeden_entscheid_den_a_m4_verlangt():
    """Eine Menge, die die eine Seite erweitert und die andere aufzaehlt,
    laeuft auseinander (Vorfall 27016d1). Die Darstellung leitet ihre
    Sollmenge seit 2026-10-01 aus dem Belegvertrag ab — Positivkontrolle:
    A-Q1 steht darin, ohne dass die Werkzeuge es nennen. Die Standabnahmen
    (A-K2, A-O1) sind keine Pflicht-Entscheide im Fall — bei unveraendertem
    Stand traegt eine fruehere Abnahme; die Darstellung zeigt den Weg aus
    dem A-M4-Snapshot (test_die_darstellung_zeigt_den_stand_des_falls)."""
    from rechner_pipeline.models import standabnahme as sa

    falldaten = _werkzeug("falldaten")
    for scope in ("tarif", "bestand"):
        rollen = belegrollen("A-M4", scope)
        erwartet = {f"A-{r[1].upper()}{r[2]}" for r in rollen if r.endswith("_snapshot")}
        # dazu der Fallauftrag, den jede Annahme nennt (ADR-026)
        assert set(falldaten.erwartete_entscheide(scope)) == erwartet | {"A-M4", "A-M6"}
        assert {"A-Q1", "A-M1"} <= set(falldaten.erwartete_entscheide(scope))
        assert not {g.gate for g in sa.GEGENSTAENDE} & set(falldaten.erwartete_entscheide(scope))
    assert falldaten.erwartete_entscheide(None) == falldaten.erwartete_entscheide("bestand")


def test_die_darstellung_zeigt_den_stand_des_falls(tmp_path):
    """Fallbericht und Modell fuehren je Gegenstand die Anzeige des
    A-M4-Snapshots woertlich."""
    fall = _tariffall(tmp_path)
    zeichne_kernstand(fall, REPO)
    assert _am4(fall).exit_code == 0
    falldaten = _werkzeug("falldaten")
    fallbericht = _werkzeug("fallbericht")
    stand = falldaten.standabnahmen(fall)
    assert [s["gate"] for s in stand] == ["A-K2", "A-O1", "A-T1"]
    assert stand[0]["anzeige"].endswith(ka.ANZEIGE_REGRESSION)
    erwartet = "abgenommen im Fall (A-O1-Snapshot "
    assert stand[1]["anzeige"].startswith(erwartet)
    assert stand[2]["anzeige"].startswith("abgenommen im Fall (A-T1-Snapshot ")
    html = fallbericht._fach({"abnahmen": {"aktuariell": [], "standabnahmen": stand}}, {})
    assert "A-O1" in html and erwartet in html and ka.ANZEIGE_REGRESSION in html


def test_die_darstellung_fuehrt_die_ausnahme_woertlich(tmp_path):
    fall = _tariffall(tmp_path)
    zeichne_kernstand(fall, REPO)
    falldaten = _werkzeug("falldaten")
    fallbericht = _werkzeug("fallbericht")
    kern = falldaten.kernstand(fall)
    assert kern["regression"] == ka.ANZEIGE_REGRESSION
    assert kern["deckung"] == ka.DECKUNG_UNTER_AUSNAHME
    assert not ERGEBNISWORTE.search(kern["regression"] + kern["deckung"])
    kette = falldaten.kette(fall)
    (ak2,) = [e for e in kette["entscheide"] if e["gate"] == "A-K2"]
    assert ak2["ausnahmen"] == {"regression": ka.AUSNAHME_REGRESSION}
    html = fallbericht._fach({"abnahmen": {"aktuariell": [], "kernstand": kern}}, {})
    assert "A-K2" in html and ka.ANZEIGE_REGRESSION in html


def test_der_gegenstand_ist_einmal_bestimmt():
    """Die Pfadmenge steht EINMAL (models.kernabnahme.KERNSTAND); Gate und
    Produzent leiten ihre Pfade daraus ab, statt sie zu wiederholen."""
    assert ka.kernstand_pfade()[:2] == (ka.KERN_PAKET, ka.KERN_REFERENZWERTE)
    assert "/".join(gate_entscheid.KERN_PAKET) == ka.KERN_PAKET
    assert "/".join(gate_entscheid.KERN_REFERENZWERTE) == ka.KERN_REFERENZWERTE
    for pfad in ka.kernstand_pfade():
        assert (REPO / pfad).exists(), pfad
    assert ka.kernmodul("src/rechner_pipeline/kern/produkte/klv.py") == \
        "src/rechner_pipeline/kern/produkte"
    assert ka.kernmodul("tests/fixtures/kern_referenzwerte/referenz_jung.json") == \
        ka.KERN_REFERENZWERTE
    assert ka.kernmodul("src/rechner_pipeline/bestand/x.py") is None
    assert ka.kernmodul("src/rechner_pipeline/kernel.py") is None
