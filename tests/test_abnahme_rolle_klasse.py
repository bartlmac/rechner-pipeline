"""Wer auf einem Abnahme-Snapshot etwas gruendet, haelt die Rolle des Schluessels gegen die Ordnung.

Entscheid des Maintainers 2026-10-01. Die Invariante: Wer einen
Abnahme-Snapshot liest, um darauf etwas zu gruenden, haelt die ZEICHNENDE
Rolle gegen die Ordnung — und die Rolle ist die des Schluessels, nicht die
behauptete. Bis dahin hielt nur die Registrierung den Fingerabdruck der
A-B2-Freigabe gegen die Zeichnungsordnung des Betriebs (Block F,
Pruefer-Befund 9); ein gueltig signierter A-M4-Snapshot eines Schluessels,
dem die Ordnung nur A-B2 gibt, begruendete eine Uebernahme, und kein Leser
verglich das Rollenfeld eines Snapshots mit der Rolle seines Schluessels.

Die Menge (Gate x Lesestelle), gemessen am Stand ca61419:

* Betrieb, Registrierung (``uebernahme.eingang_anlegen``, auch in der
  Probenkopie): A-M4, A-B2, A-M1 (den A-M4 pinnt; Soll-Bindung).
* Betrieb, Zugangsprobe (``zugangsprobe.lies_soll``): A-M4 und A-M1.
* Gate A-B2 (``gates.gate_entscheid``): A-M4 und A-M1 fuer die
  Soll-Bindung der Probe — vorher ohne Rollenpruefung.
* Gate A-M4: seine Vorbedingungen A-Q1, A-M1 (A-M2, A-M3 im
  Bestands-Scope) — vorher mit Rollen-, aber ohne Rollenfeldpruefung.
* Eintritt im Tageslauf: liest KEINEN Snapshot, sondern die
  betriebsgezeichneten Saetze der Registrierung (ADR-022, Nachtrag
  2026-10-01: Konvention); die Ratsche unten haelt, dass das so bleibt.

Danach gehen alle durch EINE Regel, ``models.zeichnung.zeichnende_rolle_fehler``
(der Betrieb ueber ``uebernahme.zeichnende_rolle``).

Die drei Instrumente:

* Angriff je Gate und Lesestelle: eine Ordnung, die der Rolle des
  Schluessels genau dieses Gate NICHT gibt; ein Snapshot, dessen Rollenfeld
  nicht die Rolle seines Schluessels ist (gefaelscht und neu signiert, oder
  eine Ordnung, die dieselbe Rolle anders nennt); ein Schluessel ohne
  Rolle. Positivkontrolle: dieselbe Welt mit der Standardordnung registriert.
* Ein Zaehltest des VERHALTENS: die Einstiege des Betriebs fahren und jedes
  lesende Oeffnen unter ``entscheide/`` dem Aufrufer zuschreiben (Pruefer-
  Befund: die statische Pfad-Ratsche sah Konkatenation, glob und iterdir
  nicht).
* Ratschen mit ``==``: die Aufrufe des Betriebslesers, die Lesestellen im
  Gate samt Regelaufrufen, jede Erwaehnung von ``entscheide`` im Betrieb,
  die Test-Ordnungen (kein Allzweck-Schluessel) — jede mit Positivkontrolle.
* Die Schluesselklasse ist die der Ordnung (vierte Frage der Regel).
* Mutationsproben: im Bauprotokoll (Regel je Stelle ausgesetzt -> rot).

Knoten: system/betrieb
"""

from __future__ import annotations

import ast
import hashlib
import inspect
import json
from collections import Counter
from functools import partial
from pathlib import Path

import pytest

from rechner_pipeline.bestand.parquet_io import read_portfolio
from rechner_pipeline.betrieb import uebernahme as ueb
from rechner_pipeline.betrieb import zugangsprobe as zpb
from rechner_pipeline.models.bestand import STAMM_NAMES
from rechner_pipeline.models import zeichnung as zmod
from tests.freigabe_testschluessel import (
    AB2_ROLLE,
    AKTUARIAT_ROLLE,
    BETRIEB_FREIGABEKEY,
    FREMDER_SCHLUESSEL,
    TESTKEY,
    TESTRING,
    betriebsordnung,
    freigaberollen,
    suitelinie_anlegen,
    suitelinie_glied,
    suitelinie_pin,
)
from tests.test_betrieb_uebernahme import STICHTAG, _fall, _mit_config

REPO_ROOT = Path(__file__).resolve().parents[1]
SRC = REPO_ROOT / "src" / "rechner_pipeline"
TESTS = REPO_ROOT / "tests"

#: Die Abnahmen, auf denen ein Zugang steht (ADR-022) — und wer sie in der
#: Suite zeichnet (getrennte Schluessel wie produktiv).
ROLLE_VON = {"A-M1": AKTUARIAT_ROLLE, "A-M4": AKTUARIAT_ROLLE, "A-B2": AB2_ROLLE}
GATES = tuple(ROLLE_VON)
#: Die Rolle, die ein Faelscher statt der richtigen ins Rollenfeld schreibt.
FALSCHE_ROLLE = {AKTUARIAT_ROLLE: AB2_ROLLE, AB2_ROLLE: AKTUARIAT_ROLLE}


def _schreibe(verzeichnis: Path, name: str, daten: dict) -> Path:
    verzeichnis.mkdir(parents=True, exist_ok=True)
    pfad = verzeichnis / name
    pfad.write_text(json.dumps(daten, sort_keys=True), encoding="utf-8")
    return pfad


def _ordnung_ohne(gate: "str | None") -> dict:
    """Die Test-Betriebsordnung, deren zeichnende Rolle fuer ``gate`` dieses
    eine Gate NICHT mehr hat (None: die Standardordnung)."""
    daten = betriebsordnung()
    if gate is not None:
        eintrag = daten["rollen"][ROLLE_VON[gate]]
        eintrag["gates"] = [g for g in eintrag["gates"] if g != gate]
    return daten


def _ordnung_umbenannt(rolle: str, neu: str = "mensch/va") -> dict:
    """Dieselbe Ordnung, dieselben Schluessel — aber ``rolle`` heisst ``neu``.
    Ein Snapshot, der ``rolle`` traegt, behauptet dann eine Rolle, die die
    Ordnung seinem Schluessel nicht gibt (die Lage zweier Ordnungen, die
    dieselbe Rolle verschieden nennen)."""
    daten = betriebsordnung()
    daten["rollen"][neu] = daten["rollen"].pop(rolle)
    return daten


@pytest.fixture()
def betriebsschluessel(_testbetriebsschluessel):
    return _testbetriebsschluessel[0]


def _neu_signiert(daten: dict, schluessel: bytes, **felder) -> dict:
    from rechner_pipeline.models.freigabe import freigabe_fuer
    from rechner_pipeline.models.schemas import p9_snapshot_sha256

    rest = {k: v for k, v in daten.items() if k not in ("freigabe", "snapshot_sha256")}
    rest.update(felder)
    rest["freigabe"] = freigabe_fuer(rest, schluessel)
    rest["snapshot_sha256"] = p9_snapshot_sha256(rest)
    return rest


def _behauptet(daten: dict, rolle: str) -> dict:
    """Beide Rollenfelder auf ``rolle`` — der Inhalt eines Faelschers."""
    return {"rolle": rolle, "zeichnung": {**daten["zeichnung"], "rolle": rolle}}


def _fall_faelschen(fall: Path, *, am1: "dict | None" = None, am4: "dict | None" = None,
                    am4_schluessel: bytes = TESTKEY) -> None:
    """A-M1 und/oder A-M4 eines Falls umschreiben und neu signieren (A-M4
    pinnt danach den neuen A-M1). ``am1``/``am4``: ersetzte Felder."""
    from tests.test_betrieb_uebernahme import am1_snapshot

    entscheide = fall / "entscheide"
    (am4_pfad,) = list(entscheide.glob("A-M4-*.json"))
    am4_alt = json.loads(am4_pfad.read_text(encoding="utf-8"))
    am1_pin = am4_alt["pflichtbelege"]["am1_snapshot"][0]
    am1_pfad = entscheide / f"A-M1-{am1_pin}.json"
    am1_alt = (json.loads(am1_pfad.read_text(encoding="utf-8")) if am1_pfad.is_file()
               else am1_snapshot(json.loads((fall / "fall.json").read_text())["name"]))
    assert am1_alt["snapshot_sha256"] == am1_pin
    am1_neu = _neu_signiert(am1_alt, TESTKEY, **(am1 or {}))
    pins = {**am4_alt["pflichtbelege"], "am1_snapshot": [am1_neu["snapshot_sha256"]]}
    am4_neu = _neu_signiert(am4_alt, am4_schluessel, pflichtbelege=pins, **(am4 or {}))
    for alt in list(entscheide.glob("A-M4-*.json")) + list(entscheide.glob("A-M1-*.json")):
        alt.unlink()
    for daten in (am1_neu, am4_neu):
        (entscheide / f"{daten['gate']}-{daten['snapshot_sha256']}.json").write_text(
            json.dumps(daten, ensure_ascii=False), encoding="utf-8")
    (fall / "abgeleitet" / "diagnostics" / "gate_entscheid_am4.gate.json").write_text(
        json.dumps({"summary": {"snapshot_sha256": am4_neu["snapshot_sha256"]}}), encoding="utf-8")


#: Die Schluessel, mit denen die Suite Abnahmen signiert — fuer das Neuzeichnen.
_SCHLUESSEL_NACH_FP = {hashlib.sha256(k).hexdigest(): k
                       for k in (TESTKEY, BETRIEB_FREIGABEKEY, FREMDER_SCHLUESSEL)}


def _unter_glied(fall: Path, pin: dict) -> None:
    """A-M1 und A-M4 des Falls unter dem Glied ``pin`` neu zeichnen (dieselben
    Schluessel, dieselben Felder): Seit die Linie Pflicht ist (ADR-025,
    Nachtrag 2026-10-01), gilt fuer die Rollenregel die Ordnung, unter der
    gezeichnet wurde — ein Angriff ueber "eine andere Ordnung" ist ein
    Snapshot unter einem anderen Glied."""
    from tests.test_betrieb_uebernahme import am1_snapshot

    entscheide = fall / "entscheide"
    (am4_pfad,) = list(entscheide.glob("A-M4-*.json"))
    am4 = json.loads(am4_pfad.read_text(encoding="utf-8"))
    am1_pfad = entscheide / f"A-M1-{am4['pflichtbelege']['am1_snapshot'][0]}.json"
    am1 = (json.loads(am1_pfad.read_text(encoding="utf-8")) if am1_pfad.is_file()
           else am1_snapshot(json.loads((fall / "fall.json").read_text())["name"]))
    _fall_faelschen(fall, am1={"zeichnung": {**am1["zeichnung"], **pin}},
                    am4={"zeichnung": {**am4["zeichnung"], **pin}},
                    am4_schluessel=_SCHLUESSEL_NACH_FP[am4["freigabe"]["schluessel_sha256"]])


def _unter_ordnung(fall: Path, ordnung: dict, linie: Path) -> Path:
    """Eine Linie mit ``ordnung`` als erstem Glied, und A-M1/A-M4 darunter."""
    linie = suitelinie_anlegen(linie, ordnung)
    if ordnung != betriebsordnung():
        _unter_glied(fall, suitelinie_pin(ordnung))
    return linie


def _registriere(tmp_path: Path, fall: Path, betriebsschluessel: Path, ordnung: dict, **kw):
    """Die Registrierung unter der Linie, deren Glied ``ordnung`` ist — die
    Abnahmen des Falls sind unter genau diesem Glied gezeichnet."""
    stand = _mit_config(tmp_path / "daten")
    pfad = _schreibe(tmp_path / "schluessel", "ordnung.json", ordnung)
    linie = _unter_ordnung(fall, ordnung, tmp_path / "linie-betrieb")
    return stand, partial(ueb.eingang_anlegen, stand, fall, STICHTAG,
                          betriebsschluessel=betriebsschluessel, zeichnungsordnung=pfad,
                          linie=linie, **kw)


# --------------------------------------------------------------------------- #
# Registrierung
# --------------------------------------------------------------------------- #


def test_positivkontrolle_die_standardordnung_registriert(tmp_path, betriebsschluessel):
    """Dieselbe Welt wie die Angriffe, die Standardordnung: Die Registrierung
    geht durch, und sie haelt die Rolle des Schluessels fest — fuer A-M4 im
    Eingang (Rollenfeld == Rolle des Schluessels, Fingerabdruck-Praefix),
    fuer A-B2 in der Zugangsabnahme (ADR-022, Nachtrag 2026-10-01)."""
    fall = _fall(tmp_path)
    _, registriere = _registriere(tmp_path, fall, betriebsschluessel, _ordnung_ohne(None))
    ziel = registriere()
    eingang = json.loads((ziel / ueb.EINGANG_DATEI).read_text(encoding="utf-8"))
    assert eingang["zeichnung"]["rolle"] == AKTUARIAT_ROLLE
    assert eingang["zeichnung"]["schluessel_sha256"] == hashlib.sha256(TESTKEY).hexdigest()[:16]
    abnahme = json.loads((ziel / ueb.ZUGANGSABNAHME_DATEI).read_text(encoding="utf-8"))
    assert abnahme["a_b2"]["freigabe_rolle"] == AB2_ROLLE == abnahme["a_b2"]["rolle"]


@pytest.mark.parametrize("gate", GATES)
def test_registrierung_verweigert_eine_abnahme_deren_rolle_das_gate_nicht_zeichnen_darf(
        tmp_path, betriebsschluessel, gate):
    """Schluessel gueltig, Signatur stimmt — aber die Ordnung des Betriebs
    gibt seiner Rolle dieses Gate nicht: keine Registrierung, kein Eingang."""
    fall = _fall(tmp_path)
    stand, registriere = _registriere(tmp_path, fall, betriebsschluessel, _ordnung_ohne(gate))
    with pytest.raises(ueb.UebernahmeError) as fehler:
        registriere()
    meldung = str(fehler.value)
    assert f"nicht fuer {gate} berechtigt" in meldung, meldung
    assert repr(ROLLE_VON[gate]) in meldung and "Ausweg" in meldung, meldung
    assert not (stand / "uebernahme" / fall.name).exists()


@pytest.mark.parametrize("gate", GATES)
def test_registrierung_verweigert_ein_rollenfeld_das_nicht_die_rolle_des_schluessels_ist(
        tmp_path, betriebsschluessel, monkeypatch, gate):
    """Der Snapshot behauptet eine andere Rolle, als die Ordnung seinem
    (gueltigen) Schluessel gibt — neu signiert, die Signatur stimmt. Die
    Rolle ist die des Schluessels; die behauptete zaehlt nicht.

    Mutationsprobe: in models.zeichnung.zeichnende_rolle_fehler den
    Vergleich der Rollenfelder entfernen -> rot."""
    from tests.zugangsabnahme_testhelfer import schreibe_zugangsabnahme

    fall = _fall(tmp_path)
    richtig = ROLLE_VON[gate]
    falsch = FALSCHE_ROLLE[richtig]
    if gate == "A-B2":
        monkeypatch.setattr(ueb, "_STANDARD_ZUGANGSABNAHME",
                            partial(schreibe_zugangsabnahme, rolle=falsch))
    else:
        alt = json.loads(next((fall / "entscheide").glob("A-M4-*.json")).read_text())
        felder = _behauptet(alt, falsch)
        _fall_faelschen(fall, **({"am1": felder} if gate == "A-M1" else {"am4": felder}))
    stand, registriere = _registriere(tmp_path, fall, betriebsschluessel, _ordnung_ohne(None))
    with pytest.raises(ueb.UebernahmeError) as fehler:
        registriere()
    meldung = str(fehler.value)
    assert f"{gate}-" in meldung and "behauptet als Rolle" in meldung, meldung
    assert repr(falsch) in meldung and repr(richtig) in meldung and "Ausweg" in meldung, meldung
    assert not (stand / "uebernahme" / fall.name).exists()


def test_ein_schluessel_mit_nur_a_b2_scheitert_an_a_m4(tmp_path, betriebsschluessel):
    """Positivkontrolle der getrennten Test-Schluessel: Der Freigabeschluessel
    von mensch/betrieb signiert A-M4 (Rollenfeld stimmig: mensch/betrieb).
    Signatur gueltig, Rollenfeld gleich der Rolle — aber die Rolle darf A-M4
    nicht zeichnen. Ein Allzweck-Schluessel haette genau das verdeckt."""
    fall = _fall(tmp_path)
    alt = json.loads(next((fall / "entscheide").glob("A-M4-*.json")).read_text())
    _fall_faelschen(fall, am4=_behauptet(alt, AB2_ROLLE), am4_schluessel=BETRIEB_FREIGABEKEY)
    _, registriere = _registriere(tmp_path, fall, betriebsschluessel, _ordnung_ohne(None))
    with pytest.raises(ueb.UebernahmeError, match=r"A-M4-.*'mensch/betrieb' .*nicht fuer A-M4"):
        registriere()


def test_registrierung_verweigert_einen_a_m4_schluessel_ohne_rolle(tmp_path, betriebsschluessel):
    """Signiert mit einem Schluessel, der im Ring steht (die Signatur ist
    gueltig), den die Ordnung aber keiner Rolle zuordnet."""
    fall = _fall(tmp_path)
    _fall_faelschen(fall, am4_schluessel=FREMDER_SCHLUESSEL)
    ring = {**TESTRING, hashlib.sha256(FREMDER_SCHLUESSEL).hexdigest(): FREMDER_SCHLUESSEL}
    stand, registriere = _registriere(tmp_path, fall, betriebsschluessel, _ordnung_ohne(None),
                                      schluesselring=ring)
    with pytest.raises(ueb.UebernahmeError, match=r"A-M4-.*keiner Rolle zuordnet.*Ausweg"):
        registriere()
    assert not (stand / "uebernahme" / fall.name).exists()


# --------------------------------------------------------------------------- #
# Zugangsprobe
# --------------------------------------------------------------------------- #


@pytest.fixture(scope="module")
def welt(tmp_path_factory):
    """Fall mit den Belegen der echten Produzenten und A-M1/A-M4, die sie
    pinnen, dazu eine noch nie gefuehrte Ablage (test_zugangsabnahme_ab2)."""
    from tests.test_zugangsabnahme_ab2 import _welt

    return _welt(tmp_path_factory.mktemp("rolle-welt"))


def _kopie_unter(fall: Path, ordnung: dict, tmp_path: Path):
    """Eine Kopie des Falls der Welt (die Welt bleibt unberuehrt), deren
    A-M1/A-M4 unter dem Glied von ``ordnung`` gezeichnet sind, und die Linie."""
    import shutil

    kopie = tmp_path / "welt-kopie" / fall.name
    shutil.copytree(fall, kopie)
    return kopie, _unter_ordnung(kopie, ordnung, tmp_path / "linie-probe")


def _lies_soll(fall: Path, ordnung: dict, tmp_path: Path):
    from rechner_pipeline.models.ordnungslinie import lade_linie

    fall, linie = _kopie_unter(fall, ordnung, tmp_path)
    sha = json.loads((fall / "abgeleitet" / "diagnostics" / "gate_entscheid_am4.gate.json")
                     .read_text(encoding="utf-8"))["summary"]["snapshot_sha256"]
    bestand = read_portfolio(fall / "abgeleitet" / "bestand" / "bestand.parquet",
                             expected_columns=STAMM_NAMES)
    identitaet = {int(p): int(p) for p in bestand["police_id"]}
    return zpb.lies_soll(fall, STICHTAG, identitaet, am4_snapshot_sha256=sha, ordnung=ordnung,
                         ordnungslinie=lade_linie(linie, ring=TESTRING)[0])


@pytest.mark.parametrize("gate", ("A-M1", "A-M4"))
def test_lies_soll_verweigert_eine_abnahme_deren_rolle_das_gate_nicht_zeichnen_darf(
        welt, gate, tmp_path):
    """Das Soll der Probe steht auf A-M4 und dem A-M1, den A-M4 pinnt. Ein
    Soll aus einer Abnahme, die eine unberechtigte Rolle gezeichnet hat, ist
    kein Soll."""
    with pytest.raises(zpb.ZugangsprobeError) as fehler:
        _lies_soll(welt[0], _ordnung_ohne(gate), tmp_path)
    assert f"nicht fuer {gate} berechtigt" in str(fehler.value), str(fehler.value)


def test_lies_soll_verweigert_ein_rollenfeld_das_die_ordnung_dem_schluessel_nicht_gibt(
        welt, tmp_path):
    """Die Ordnung nennt die Rolle des A-M4-Schluessels anders als der
    Snapshot. Welche der beiden Ordnungen recht hat, weiss der Leser nicht —
    also gruendet er nichts darauf."""
    with pytest.raises(zpb.ZugangsprobeError) as fehler:
        _lies_soll(welt[0], _ordnung_umbenannt(AKTUARIAT_ROLLE), tmp_path)
    meldung = str(fehler.value)
    assert "behauptet als Rolle" in meldung and "'mensch/va'" in meldung, meldung


@pytest.mark.parametrize("gate", ("A-M1", "A-M4"))
def test_die_zugangsprobe_verweigert_eine_abnahme_deren_rolle_das_gate_nicht_zeichnen_darf(
        welt, tmp_path, betriebsschluessel, gate):
    """Durch den Eingang der Probe: A-M4 faellt schon bei der Registrierung in
    der Probenkopie, A-M1 beim Soll — beides, bevor ein Lauf faehrt."""
    fall, stand = welt
    fall, linie = _kopie_unter(fall, _ordnung_ohne(gate), tmp_path)
    with pytest.raises(zpb.ZugangsprobeError) as fehler:
        zpb.zugangsprobe(stand, fall, STICHTAG, schluessel=betriebsschluessel,
                         zeichnungsordnung=_schreibe(tmp_path / "s", "o.json", _ordnung_ohne(gate)),
                         linie=linie)
    assert f"nicht fuer {gate} berechtigt" in str(fehler.value), str(fehler.value)


# --------------------------------------------------------------------------- #
# Gate A-B2: die Abnahmen unter dem Soll der Probe
# --------------------------------------------------------------------------- #

from tests.test_zugangsabnahme_ab2 import _ab2, gatefall  # noqa: E402,F401  (Fixture)


def _gate_unter(fall: Path, pfad: Path) -> Path:
    """Die Ordnung ``pfad`` wird Spitze der Linie des Falls; A-M1/A-M4 werden
    unter ihr neu gezeichnet und die Probe darauf neu belegt (dieselbe
    Gestalt wie in ``gatefall``) — das Gate liest die Abnahmen gegen die
    Ordnung, unter der sie gezeichnet wurden (ADR-025: die Linie ist Pflicht)."""
    from rechner_pipeline.betrieb import tageslauf as tl
    from rechner_pipeline.betrieb.tageslauf import Ablage
    from rechner_pipeline.models import zugangsprobe as zp
    from rechner_pipeline.models.ordnungslinie import lade_linie
    from tests.zeichnung_fixture import auftrag_args
    from tests.zugangsabnahme_testhelfer import abnahmen_aus_fall, probenbeleg

    auftrag_args(fall, pfad)
    spitze = lade_linie(fall.parent / "linie", ring=TESTRING)[0][-1]
    _unter_glied(fall, {"ordnung_sha256": spitze["ordnung_sha256"],
                        "ordnungsglied_sha256": spitze["glied_sha256"]})
    (am4,) = [json.loads(p.read_text(encoding="utf-8"))
              for p in (fall / "entscheide").glob("A-M4-*.json")]
    eingang = {"fall": fall.name, "snapshot_sha256": am4["snapshot_sha256"],
               "stichtag": STICHTAG.isoformat()}
    beleg = probenbeleg(fall.name, ablage_stand={"gefuehrter_tag": None, "config_sha256": "ab" * 32},
                        eingang_roh=json.dumps(eingang).encode("utf-8"),
                        am4_snapshot_sha256=am4["snapshot_sha256"],
                        zeichner=tl.betriebszeichner(Ablage(fall.parent / "irgendeine-ablage")),
                        abnahmen=abnahmen_aus_fall(fall, am4["snapshot_sha256"]))
    (fall / zp.BELEG_RELATIV).write_text(json.dumps(beleg), encoding="utf-8")
    return pfad


def _gate_ordnung(ordnung_pfad: Path, ziel: Path, *, ohne: "str | None" = None,
                  umbenannt: bool = False, fall: "Path | None" = None) -> Path:
    daten = json.loads(Path(ordnung_pfad).read_text(encoding="utf-8"))
    if ohne is not None:
        daten["rollen"][AKTUARIAT_ROLLE]["gates"] = [
            g for g in daten["rollen"][AKTUARIAT_ROLLE]["gates"] if g != ohne]
    if umbenannt:
        daten["rollen"]["mensch/va"] = daten["rollen"].pop(AKTUARIAT_ROLLE)
    pfad = _schreibe(ziel, "gate-ordnung.json", daten)
    return _gate_unter(fall, pfad) if fall is not None else pfad


def test_positivkontrolle_das_gate_a_b2_nimmt_mit_der_vollen_ordnung_an(gatefall, tmp_path):
    fall, _, _, schluessel, testkey, ordnung = gatefall
    ergebnis = _ab2(fall, schluessel=schluessel["mensch"], testkey=testkey,
                    ordnung=_gate_ordnung(ordnung, tmp_path / "o", fall=fall))
    assert ergebnis.exit_code == 0, ergebnis.errors


@pytest.mark.parametrize("gate", ("A-M1", "A-M4"))
def test_das_gate_a_b2_verweigert_eine_abnahme_deren_rolle_das_gate_nicht_zeichnen_darf(
        gatefall, tmp_path, gate):
    """A-B2 nimmt die Probe nur auf Abnahmen an, die eine dafuer berechtigte
    Rolle gezeichnet hat — gehalten gegen die Ordnung DIESER Zeichnung.

    Mutationsprobe: im A-B2-Zweig von gate_entscheid die Regel nicht rufen
    -> Annahme -> rot."""
    fall, _, _, schluessel, testkey, ordnung = gatefall
    ergebnis = _ab2(fall, schluessel=schluessel["mensch"], testkey=testkey,
                    ordnung=_gate_ordnung(ordnung, tmp_path / "o", ohne=gate, fall=fall))
    assert ergebnis.exit_code != 0
    meldung = ergebnis.errors[0]["message"]
    assert f"{gate}-Snapshot" in meldung and f"nicht fuer {gate} berechtigt" in meldung, meldung
    assert not list((fall / "entscheide").glob("A-B2-*.json"))


def test_das_gate_a_b2_verweigert_ein_rollenfeld_das_die_ordnung_dem_schluessel_nicht_gibt(
        gatefall, tmp_path):
    fall, _, _, schluessel, testkey, ordnung = gatefall
    ergebnis = _ab2(fall, schluessel=schluessel["mensch"], testkey=testkey,
                    ordnung=_gate_ordnung(ordnung, tmp_path / "o", umbenannt=True, fall=fall))
    assert ergebnis.exit_code != 0
    meldung = ergebnis.errors[0]["message"]
    assert "A-M4-Snapshot" in meldung and "behauptet als Rolle" in meldung, meldung


# --------------------------------------------------------------------------- #
# Gate A-M4: seine Vorbedingungen
# --------------------------------------------------------------------------- #


@pytest.mark.parametrize("vorbedingung", ("A-Q1", "A-M1"))
def test_a_m4_verweigert_eine_vorbedingung_deren_rollenfeld_nicht_die_rolle_des_schluessels_ist(
        tmp_path, vorbedingung):
    """A-M4 gruendet auf A-Q1 und A-M1. Hatte er schon gehalten, ob ihre Rolle
    das Gate zeichnen darf — aber nicht, ob das Rollenfeld die Rolle des
    Schluessels ist. Hier: Rollenfeld gefaelscht, mit dem echten Schluessel
    neu signiert (die Signatur stimmt).

    Mutationsprobe: im A-M4-Zweig die Vorbedingungen wieder mit dem alten
    _zeichnungsfehler (nur Erlaubnis) pruefen -> Annahme -> rot."""
    from tests.test_pk1_am4_beweisvertrag import _bereite_fall, _o3_tg2012, _p9_annahme

    fall = _bereite_fall(tmp_path, ("klv/tg2012",))
    assert _o3_tg2012(fall).exit_code == 0
    (pfad,) = list((fall / "entscheide").glob(f"{vorbedingung}-*.json"))
    daten = json.loads(pfad.read_text(encoding="utf-8"))
    schluessel = (fall.parent / "p9-freigabe.key").read_bytes()
    neu = _neu_signiert(daten, schluessel, **_behauptet(daten, "mensch/programmleitung"))
    pfad.unlink()
    (pfad.parent / f"{vorbedingung}-{neu['snapshot_sha256']}.json").write_text(
        json.dumps(neu, ensure_ascii=False), encoding="utf-8")
    am4 = _p9_annahme(fall, "A-M4", "darf nicht auf einer fremden Rolle gruenden")
    assert am4.exit_code != 0
    meldung = am4.errors[0]["message"]
    assert vorbedingung in meldung and "behauptet als Rolle" in meldung, meldung
    assert not list((fall / "entscheide").glob("A-M4-*.json"))


# --------------------------------------------------------------------------- #
# Die Schluesselklasse ist die der Ordnung, nicht die behauptete
# --------------------------------------------------------------------------- #
#
# Pruefer-Befund (Angriffsrunde 2026-10-01): Klasse und Mandat kamen aus dem
# Snapshot. Gab die Ordnung der Rolle die Klasse ``simulation`` und
# behauptete der Snapshot ``mensch`` ohne Mandat, registrierte der Betrieb,
# die Mandatspflicht griff nie, und die Seite meldete eine menschliche
# Zeichnung. Dieselbe Invariante wie das Rollenfeld: Was der Schluessel ist,
# sagt die Ordnung.


def _ordnung_klasse(rolle: str, klasse: str, basis: "dict | None" = None) -> dict:
    daten = basis if basis is not None else betriebsordnung()
    daten["rollen"][rolle]["schluesselklasse"] = klasse
    return daten


def _klasse_behauptet(daten: dict, klasse: str, mandat: "str | None" = None) -> dict:
    zeichnung = {k: v for k, v in daten["zeichnung"].items() if k != "mandat_sha256"}
    zeichnung["schluesselklasse"] = klasse
    if mandat is not None:
        zeichnung["mandat_sha256"] = mandat
    return {"zeichnung": zeichnung}


@pytest.mark.parametrize("gate", GATES)
def test_registrierung_verweigert_eine_schluesselklasse_die_nicht_die_der_ordnung_ist(
        tmp_path, betriebsschluessel, gate):
    """A-M1/A-M4: der Snapshot behauptet ``simulation`` (mit Mandat), die
    Ordnung gibt ``mensch`` (neu signiert, die Signatur stimmt). A-B2: die
    Ordnung gibt ``simulation``, der Snapshot behauptet ``mensch`` — das
    Szenario des Pruefers. Beides: keine Registrierung.

    Mutationsprobe: in models.zeichnung.zeichnende_rolle_fehler den
    Klassenvergleich entfernen -> rot."""
    fall = _fall(tmp_path)
    ordnung = _ordnung_ohne(None)
    if gate == "A-B2":
        ordnung = _ordnung_klasse(AB2_ROLLE, "simulation", ordnung)
        behauptet, gilt = "mensch", "simulation"
    else:
        alt = json.loads(next((fall / "entscheide").glob("A-M4-*.json")).read_text())
        felder = _klasse_behauptet(alt, "simulation", mandat="ab" * 32)
        _fall_faelschen(fall, **({"am1": felder} if gate == "A-M1" else {"am4": felder}))
        behauptet, gilt = "simulation", "mensch"
    stand, registriere = _registriere(tmp_path, fall, betriebsschluessel, ordnung)
    with pytest.raises(ueb.UebernahmeError) as fehler:
        registriere()
    meldung = str(fehler.value)
    assert f"{gate}-" in meldung and f"Schluesselklasse {behauptet!r}" in meldung, meldung
    assert repr(gilt) in meldung and "Ausweg" in meldung, meldung
    assert not (stand / "uebernahme" / fall.name).exists()


# Die Mandatspflicht rechnet damit auf der Klasse der Ordnung: Ist die
# behauptete Klasse die der Ordnung und lautet sie ``simulation``, verlangt
# schon das P9-Schema das Mandat (gemessen: "zeichnung mit schluesselklasse
# simulation braucht mandat_sha256"); die Regel prueft es zusaetzlich selbst
# (Einheitstest unten), damit sie ohne das Schema vollstaendig ist.


def test_lies_soll_verweigert_eine_schluesselklasse_die_nicht_die_der_ordnung_ist(welt, tmp_path):
    with pytest.raises(zpb.ZugangsprobeError, match="Schluesselklasse 'mensch'.*'simulation'"):
        _lies_soll(welt[0], _ordnung_klasse(AKTUARIAT_ROLLE, "simulation"), tmp_path)


def test_das_gate_a_b2_verweigert_eine_schluesselklasse_die_nicht_die_der_ordnung_ist(
        gatefall, tmp_path):
    fall, _, _, schluessel, testkey, ordnung = gatefall
    daten = json.loads(Path(ordnung).read_text(encoding="utf-8"))
    daten["rollen"][AKTUARIAT_ROLLE]["schluesselklasse"] = "simulation"
    ergebnis = _ab2(fall, schluessel=schluessel["mensch"], testkey=testkey,
                    ordnung=_gate_unter(fall, _schreibe(tmp_path / "o", "gate-ordnung.json",
                                                        daten)))
    assert ergebnis.exit_code != 0
    meldung = ergebnis.errors[0]["message"]
    assert "A-M4-Snapshot" in meldung and "Schluesselklasse 'mensch'" in meldung, meldung


@pytest.mark.parametrize("vorbedingung", ("A-Q1", "A-M1"))
def test_a_m4_verweigert_eine_vorbedingung_deren_klasse_nicht_die_der_ordnung_ist(
        tmp_path, vorbedingung):
    """Die Ordnung der Gate-Tests gibt der Aktuariatsrolle ``simulation`` mit
    Mandat; die Vorbedingung behauptet ``mensch`` ohne Mandat (neu signiert)."""
    from tests.test_pk1_am4_beweisvertrag import _bereite_fall, _o3_tg2012, _p9_annahme

    fall = _bereite_fall(tmp_path, ("klv/tg2012",))
    assert _o3_tg2012(fall).exit_code == 0
    (pfad,) = list((fall / "entscheide").glob(f"{vorbedingung}-*.json"))
    daten = json.loads(pfad.read_text(encoding="utf-8"))
    assert daten["zeichnung"]["schluesselklasse"] == "simulation"
    neu = _neu_signiert(daten, (fall.parent / "p9-freigabe.key").read_bytes(),
                        **_klasse_behauptet(daten, "mensch"))
    pfad.unlink()
    (pfad.parent / f"{vorbedingung}-{neu['snapshot_sha256']}.json").write_text(
        json.dumps(neu, ensure_ascii=False), encoding="utf-8")
    am4 = _p9_annahme(fall, "A-M4", "darf nicht auf einer fremden Klasse gruenden")
    assert am4.exit_code != 0
    meldung = am4.errors[0]["message"]
    assert vorbedingung in meldung and "Schluesselklasse 'mensch'" in meldung, meldung


def test_ein_einzelner_freigabeschluessel_reicht_nicht(tmp_path, betriebsschluessel):
    """Pruefer-Befund zur Doku: Mit getrennten Schluesseln (Aktuariat fuer
    A-M1/A-M4, mensch/betrieb fuer A-B2) braucht die Registrierung BEIDE im
    Ring — mit nur dem Aktuariatsschluessel verweigert sie am A-B2-Snapshot.
    deploy/plv/README.md zeigt den Schalter deshalb zweifach."""
    fall = _fall(tmp_path)
    _, registriere = _registriere(tmp_path, fall, betriebsschluessel, _ordnung_ohne(None),
                                  schluesselring={hashlib.sha256(TESTKEY).hexdigest(): TESTKEY})
    with pytest.raises(ueb.UebernahmeError, match=r"A-B2-.*nicht bereitgestellten Schluessel"):
        registriere()


# --------------------------------------------------------------------------- #
# Die Regel selbst
# --------------------------------------------------------------------------- #


def test_die_regel_ist_eine_funktion_fuer_alle_gates():
    """Fuer jedes Gate der Menge: berechtigte Rolle mit stimmigem Rollenfeld
    und stimmiger Schluesselklasse -> Rolle; ohne Erlaubnis, mit fremdem
    Rollenfeld, ohne Rollenfeld, mit fremder oder fehlender Klasse, als
    Simulation ohne Mandat, ohne Ordnung -> Meldung mit Ausweg. Der
    Betriebsweg liefert dasselbe."""
    def unter(daten: dict, ordnung: dict):
        # gezeichnet unter dem Glied dieser Ordnung, gelesen mit genau ihm
        z = {**(daten.get("zeichnung") or {}), **suitelinie_pin(ordnung)}
        return {**daten, "zeichnung": z}, [suitelinie_glied(ordnung)]

    for gate in GATES:
        rolle = ROLLE_VON[gate]
        fp = freigaberollen()[rolle]["schluessel_sha256"]
        daten = {"freigabe": {"schluessel_sha256": fp}, "rolle": rolle,
                 "zeichnung": {"rolle": rolle, "schluesselklasse": "mensch"}}
        d, linie = unter(daten, betriebsordnung())
        assert zmod.zeichnende_rolle_fehler(d, gate, None, linie=linie) == (rolle, None)
        assert ueb.zeichnende_rolle(d, gate, None, "x.json", ordnungslinie=linie) == rolle
        simuliert = _ordnung_klasse(rolle, "simulation")
        mit_mandat = {**daten, "zeichnung": {**daten["zeichnung"], "schluesselklasse": "simulation",
                                             "mandat_sha256": "ab" * 32}}
        d, linie = unter(mit_mandat, simuliert)
        assert zmod.zeichnende_rolle_fehler(d, gate, None, linie=linie) == (rolle, None)
        ohne_mandat = {**daten, "zeichnung": {**daten["zeichnung"], "schluesselklasse": "simulation"}}
        for ordnung, daten_x, muster in (
                (_ordnung_ohne(gate), daten, f"nicht fuer {gate} berechtigt"),
                (betriebsordnung(), {**daten, "zeichnung": {"rolle": "mensch/va"}},
                 "behauptet als Rolle zeichnung.rolle='mensch/va'"),
                (betriebsordnung(), {"freigabe": daten["freigabe"]}, "behauptet als Rolle nichts"),
                (simuliert, daten, "Schluesselklasse 'mensch'"),
                (betriebsordnung(), {**daten, "zeichnung": {"rolle": rolle}}, "Schluesselklasse None"),
                (simuliert, ohne_mandat, "ohne Mandat")):
            d, linie = unter(daten_x, ordnung)
            rolle_x, fehler = zmod.zeichnende_rolle_fehler(d, gate, None, linie=linie)
            assert rolle_x is None and muster in fehler and "Ausweg" in fehler, fehler
            with pytest.raises(ueb.UebernahmeError, match="Ausweg"):
                ueb.zeichnende_rolle(d, gate, None, "x.json", ordnungslinie=linie)
        # Ohne Linie begruendet die Abnahme nichts — kein Weg ueber die
        # heutige Ordnung des Lesers (ADR-025, Nachtrag 2026-10-01).
        d, _ = unter(daten, betriebsordnung())
        for ohne in (None, []):
            rolle_x, fehler = zmod.zeichnende_rolle_fehler(d, gate, betriebsordnung(), linie=ohne)
            assert rolle_x is None and "ohne Ordnungslinie" in fehler and "Ausweg" in fehler
            with pytest.raises(ueb.UebernahmeError, match="ohne Ordnungslinie"):
                ueb.zeichnende_rolle(d, gate, betriebsordnung(), "x.json", ordnungslinie=ohne)


# --------------------------------------------------------------------------- #
# Ratsche: die Lesestellen im Betrieb
# --------------------------------------------------------------------------- #

#: Jeder Aufruf des Betriebslesers in src/: (Datei, umschliessende Funktion,
#: Gate). lies_am4_snapshot ist der Leser fuer A-M4; sein Aufruf zaehlt mit.
LESESTELLEN = Counter({
    ("betrieb/uebernahme.py", "pruefe_am4_snapshot", "A-M4"): 1,
    ("betrieb/uebernahme.py", "lies_am4_snapshot", "A-M4"): 1,
    ("betrieb/uebernahme.py", "_zugangsabnahme_binden", "A-M1"): 1,
    # Vor jedem Seiteneffekt (auch fuer das Neuaufsetzen, Angriffsrunde
    # 2026-10-01); die zweite A-B2-Lesung ist die der Test-Naht unter der Sperre.
    ("betrieb/uebernahme.py", "registrierung_vorbedingungen", "A-M4"): 1,
    ("betrieb/uebernahme.py", "registrierung_vorbedingungen", "A-B2"): 1,
    ("betrieb/uebernahme.py", "eingang_anlegen", "A-B2"): 1,
    ("betrieb/zugangsprobe.py", "lies_soll", "A-M4"): 1,
    ("betrieb/zugangsprobe.py", "lies_soll", "A-M1"): 1,
    # Die Bindung der Abnahme des Anfangsbestands (ADR-025): derselbe Leser,
    # im Linienbereich.
    ("betrieb/anfangsbestand.py", "binden", "A-B3"): 1,
})

LESER = ("lies_abnahme_snapshot", "lies_am4_snapshot")


def _name(knoten: ast.Call) -> "str | None":
    return getattr(knoten.func, "attr", None) or getattr(knoten.func, "id", None)


def _aufrufe(quelle: str, datei: str):
    """(Datei, Funktion, Gate, hat_ordnung) je Aufruf eines Lesers."""
    treffer = []
    for funktion in ast.walk(ast.parse(quelle)):
        if not isinstance(funktion, (ast.FunctionDef, ast.AsyncFunctionDef)):
            continue
        for knoten in ast.walk(funktion):
            if not isinstance(knoten, ast.Call) or _name(knoten) not in LESER:
                continue
            if _name(knoten) == "lies_am4_snapshot":
                gate = "A-M4"
            elif len(knoten.args) >= 2 and isinstance(knoten.args[1], ast.Constant):
                gate = knoten.args[1].value
            else:
                gate = "?"
            treffer.append((datei, funktion.name, gate,
                            any(k.arg == "ordnung" for k in knoten.keywords)))
    return treffer


def test_ratsche_jede_lesestelle_des_betriebs_reicht_die_ordnung():
    """Die Menge der Lesestellen ist genau die gemessene (== statt >=), und
    jede reicht die Zeichnungsordnung an den Leser. Eine neue Lesestelle muss
    hier eingetragen werden und damit sagen, gegen welche Ordnung sie haelt."""
    alle = []
    for pfad in sorted(SRC.rglob("*.py")):
        alle += _aufrufe(pfad.read_text(encoding="utf-8"), str(pfad.relative_to(SRC)))
    assert Counter((d, f, g) for d, f, g, _ in alle) == LESESTELLEN
    assert [(d, f, g) for d, f, g, mit in alle if not mit] == []
    # A-B3 (ADR-025) liest der Betrieb beim Binden des Anfangsbestands; die
    # Angriffe darauf stehen in tests/test_erstabnahme_linie.py.
    assert {g for _, _, g in LESESTELLEN} == set(GATES) | {"A-B3"} == set(ueb._ABNAHME)


def test_ratsche_der_leser_verlangt_die_ordnung_ohne_default():
    """``ordnung`` ist Pflicht (keyword-only, kein Default): Ein Aufrufer,
    der sie vergisst, faellt mit TypeError statt still ohne Rollenpruefung."""
    for leser in (ueb.lies_abnahme_snapshot, ueb.lies_am4_snapshot, ueb.pruefe_am4_snapshot,
                  zpb.lies_soll):
        parameter = inspect.signature(leser).parameters["ordnung"]
        assert parameter.kind is inspect.Parameter.KEYWORD_ONLY, leser.__name__
        assert parameter.default is inspect.Parameter.empty, leser.__name__


def test_ratsche_positivkontrolle_des_aufrufdetektors():
    quelle = (
        "def a(fall, sha):\n"
        "    return ueb.lies_abnahme_snapshot(fall, 'A-M1', sha)\n"
        "def b(fall, sha, gate):\n"
        "    return lies_abnahme_snapshot(fall, gate, sha, ordnung=o)\n"
        "def c(fall, sha):\n"
        "    return lies_am4_snapshot(fall, sha, ordnung=o)\n")
    assert _aufrufe(quelle, "x.py") == [
        ("x.py", "a", "A-M1", False), ("x.py", "b", "?", True), ("x.py", "c", "A-M4", True)]


# --------------------------------------------------------------------------- #
# Ratsche: eine Regel, zwei Schichten
# --------------------------------------------------------------------------- #

#: Wer die Regel ruft — je Datei das Gate-Argument (Quelltext). Der Betrieb
#: ruft sie EINMAL (uebernahme.zeichnende_rolle, durch die jeder Leser geht);
#: das Gate je fremder Abnahme, auf die es gruendet.
REGEL_AUFRUFE = Counter({
    ("betrieb/uebernahme.py", "gate"): 1,
    ("gates/gate_entscheid.py", "abnahme_gate"): 2,   # A-B2: A-M4/A-M1; A-M4: A-M1..A-M3
    ("gates/gate_entscheid.py", "'A-Q1'"): 1,         # A-M4: A-Q1
    # A-M4: die Standabnahme je Gegenstand (A-K2, A-O1; Entscheid 2026-10-01)
    # — der Snapshot im Fall (a) und der fruehere Snapshot des Verweises (b).
    ("gates/gate_entscheid.py", "gegenstand.gate"): 2,
    # Jede Annahme eines Falls: der geltende Fallauftrag (ADR-026).
    ("gates/gate_entscheid.py", "AUFTRAG_GATE"): 1,
})

#: Die Kettenleser im Gate — je Gate-Argument. ``args.gate`` ist die EIGENE
#: Kette (Vorgaenger, Idempotenz), auf ihr gruendet keine fremde Abnahme;
#: jede andere steht in REGEL_AUFRUFE mit einem Regelaufruf. Ausnahme mit
#: Grund: Der Fallabbruch liest die A-M4-Kette ein zweites Mal, um eine
#: geltende Migrationsabnahme zu ERKENNEN und den Abbruch zu VERWEIGERN — er
#: gruendet nichts auf ihr, die Lesung kann nur sperren (ADR-026).
#: ``gate``: die Kette der LINIE, auf die ein Verweis (Weg b) zeigt — er
#: traegt nur ihre geltende Spitze (Pruefrunde G, G11; ``_verweis_gilt_fehler``),
#: gelesen ueber denselben Kettenleser mit Signaturpruefung.
GATE_KETTENLESER = Counter({"'A-M4'": 2, "'A-M1'": 1, "'A-Q1'": 1, "gegenstand.gate": 1,
                            "abnahme_gate": 1, "args.gate": 1, "AUFTRAG_GATE": 1,
                            "gate": 1})


def _regel_und_ketten(quelle: str, datei: str):
    regel, ketten = Counter(), Counter()
    for knoten in ast.walk(ast.parse(quelle)):
        if not isinstance(knoten, ast.Call):
            continue
        if _name(knoten) == "zeichnende_rolle_fehler" and len(knoten.args) >= 2:
            regel[(datei, ast.unparse(knoten.args[1]))] += 1
        if _name(knoten) == "_lade_snapshot_kette" and len(knoten.args) >= 2:
            ketten[ast.unparse(knoten.args[1])] += 1
    return regel, ketten


def test_ratsche_eine_regel_in_beiden_schichten():
    regel, ketten = Counter(), Counter()
    for pfad in sorted(SRC.rglob("*.py")):
        r, k = _regel_und_ketten(pfad.read_text(encoding="utf-8"), str(pfad.relative_to(SRC)))
        regel += r
        if pfad.name == "gate_entscheid.py":
            ketten += k
    assert regel == REGEL_AUFRUFE
    assert ketten == GATE_KETTENLESER


def test_ratsche_positivkontrolle_regel_und_kettendetektor():
    quelle = ("def f(a):\n"
              "    k = _lade_snapshot_kette(v, 'A-M4', f, r, s)\n"
              "    zeichnende_rolle_fehler(k, 'A-M4', o)\n"
              "    _lade_snapshot_kette(v, args.gate, f, r, s)\n")
    regel, ketten = _regel_und_ketten(quelle, "x.py")
    assert regel == Counter({("x.py", "'A-M4'"): 1})
    assert ketten == Counter({"'A-M4'": 1, "args.gate": 1})


# --------------------------------------------------------------------------- #
# Zaehltest: wer im Betrieb eine Datei unter entscheide/ oeffnet
# --------------------------------------------------------------------------- #
#
# Pruefer-Befund (Angriffsrunde 2026-10-01): Eine statische Ratsche auf
# Pfad-Vorlagen sah Konkatenation, glob-Praefix, iterdir, %-Formatierung und
# Pfade auf Modulebene nicht. Gezaehlt wird jetzt das VERHALTEN: Jeder
# Einstieg des Betriebs wird gefahren, und jedes Oeffnen einer Datei unter
# ``entscheide/`` zum Lesen wird dem innersten Aufrufer aus src/ zugeschrieben.

#: Wer lesen darf: der Leser, die Kettenpruefung, die er ruft, und
#: ``belegte_tabellen`` — dieser oeffnet die gepinnten Belege nur, um ihre
#: Eingabenbloecke zu lesen; ein P9-Snapshot traegt keinen, gegruendet wird
#: auf ihm dort nichts.
ERLAUBTE_LESER = {
    ("rechner_pipeline.betrieb.uebernahme", "lies_abnahme_snapshot"),
    ("rechner_pipeline.betrieb.uebernahme", "_pruefe_geltende_spitze"),
    ("rechner_pipeline.betrieb.uebernahme", "belegte_tabellen"),
}
#: Was eine Registrierung mit EINEM Snapshot je Kette tatsaechlich oeffnet:
#: Die Kettenpruefung liest den geprueften Snapshot nicht ein zweites Mal
#: (T24-06), bei einem einzigen Glied also nichts.
REGISTRIERUNG_LIEST = ERLAUBTE_LESER - {
    ("rechner_pipeline.betrieb.uebernahme", "_pruefe_geltende_spitze")}

_DURCHREICHER = {"pathlib", "io", "codecs", "json", "_io", "builtins", "contextlib"}


class _Spion:
    """Zaehlt jedes lesende Oeffnen unter ``entscheide/`` je (Modul, Funktion)."""

    def __init__(self, original):
        self.original = original
        self.gelesen: Counter = Counter()

    def __call__(self, datei, mode="r", *args, **kwargs):
        import sys

        if ("r" in str(mode) or "+" in str(mode)) and isinstance(datei, (str, Path)) \
                and "entscheide" in Path(datei).parts:
            rahmen = sys._getframe(1)
            while rahmen is not None and \
                    rahmen.f_globals.get("__name__", "").split(".")[0] in _DURCHREICHER:
                rahmen = rahmen.f_back
            modul = rahmen.f_globals.get("__name__", "") if rahmen is not None else ""
            if modul.startswith("rechner_pipeline"):
                self.gelesen[(modul, rahmen.f_code.co_name)] += 1
        return self.original(datei, mode, *args, **kwargs)


@pytest.fixture()
def spion(monkeypatch):
    import builtins
    import io

    s = _Spion(io.open)
    monkeypatch.setattr(io, "open", s)
    monkeypatch.setattr(builtins, "open", s)
    return s


def test_zaehltest_positivkontrolle_konkatenation_und_glob(tmp_path, spion):
    """Ein kuenstlicher Leser in einem Modul des Betriebs — Konkatenation und
    glob-Praefix, die die alte Pfad-Ratsche nicht sah — wird gefangen."""
    (tmp_path / "entscheide").mkdir()
    (tmp_path / "entscheide" / ("A-M4-" + "ab" * 32 + ".json")).write_text("{}", encoding="utf-8")
    quelle = ("import json\n"
              "def konkateniert(fall, sha):\n"
              "    return json.loads((fall / 'entscheide' / ('A-M4-' + sha + '.json')).read_text())\n"
              "def globt(fall):\n"
              "    for p in (fall / 'entscheide').glob('A-M4-*'):\n"
              "        p.read_bytes()\n")
    namensraum = {"__name__": "rechner_pipeline.betrieb.kuenstlich"}
    exec(compile(quelle, "kuenstlich.py", "exec"), namensraum)
    namensraum["konkateniert"](tmp_path, "ab" * 32)
    namensraum["globt"](tmp_path)
    assert set(spion.gelesen) == {("rechner_pipeline.betrieb.kuenstlich", "konkateniert"),
                                  ("rechner_pipeline.betrieb.kuenstlich", "globt")}
    assert not set(spion.gelesen) <= ERLAUBTE_LESER


def test_zaehltest_registrierung_eintritt_export(tmp_path, spion):
    """Registrierung liest nur ueber den Leser; Eintritt im Tageslauf (samt
    Seite) und Export lesen GAR KEINE Datei unter entscheide/ (Konvention,
    ADR-022 Nachtrag 2026-10-01)."""
    from rechner_pipeline.betrieb import seite as st
    from rechner_pipeline.betrieb.tageslauf import EXIT_OK, Ablage, tageslauf
    from tests.test_betrieb_uebernahme import _kleine_config

    fall = _fall(tmp_path)
    stand = _mit_config(tmp_path / "daten", _kleine_config())
    ueb.eingang_anlegen(stand, fall, STICHTAG)
    assert set(spion.gelesen) == REGISTRIERUNG_LIEST
    spion.gelesen.clear()
    code, zeile = tageslauf(Ablage(stand), STICHTAG.replace(day=9))
    assert code == EXIT_OK and zeile["uebernommen"] is True, zeile
    st.stands_paket(Ablage(stand), tmp_path / "paket", anker_verzeichnis=tmp_path / "anker")
    assert set(spion.gelesen) == set()


def test_zaehltest_zugangsprobe(welt, spion):
    """Die Probe (Registrierung in der Probenkopie, Soll) liest nur ueber
    den Leser."""
    fall, stand = welt
    beleg = zpb.zugangsprobe(stand, fall, STICHTAG)
    assert beleg["bestanden"] is True
    assert set(spion.gelesen) == REGISTRIERUNG_LIEST


def test_zaehltest_neuaufsetzen(tmp_path, spion):
    import datetime as dt

    from rechner_pipeline.betrieb import neuaufsetzen as na
    from rechner_pipeline.betrieb.tageslauf import EXIT_OK, tageslauf
    from tests.test_betrieb_neuaufsetzen import _ablage, _fall_mit_nebentabellen

    ablage = _ablage(tmp_path / "daten")
    assert tageslauf(ablage, dt.date(2026, 2, 3))[0] == EXIT_OK
    spion.gelesen.clear()
    na.neu_aufsetzen(ablage.wurzel, _fall_mit_nebentabellen(tmp_path), STICHTAG,
                     jetzt=dt.datetime(2026, 9, 8, 6, 0, tzinfo=dt.timezone.utc))
    assert set(spion.gelesen) == REGISTRIERUNG_LIEST


#: Zweite Linie, statisch: jede Erwaehnung von "entscheide" in einer
#: String-Konstante eines Betriebsmoduls, je (Datei, Funktion bzw.
#: <modul>). Eine neue Erwaehnung ist ein neuer moeglicher Leser — sie muss
#: hier und im Zaehltest auftauchen.
ENTSCHEIDE_ERWAEHNUNGEN = Counter({
    ("betrieb/uebernahme.py", "<modul>"): 1,                  # BELEGORTE (belegte_tabellen)
    ("betrieb/uebernahme.py", "lies_abnahme_snapshot"): 2,    # Pfad des Snapshots, Kette
    ("betrieb/uebernahme.py", "zeichnung_aus_snapshot"): 1,   # Berichtsweg (Ausnahme)
})


#: Das Wort, nicht die Silbe: "entscheider"/"entscheidet" sind keine Orte.
_WORT = __import__("re").compile(r"(?<![a-z])entscheide(?![a-z])")


def _erwaehnungen(quelle: str, datei: str) -> Counter:
    baum = ast.parse(quelle)
    eltern = {}
    for knoten in ast.walk(baum):
        for kind in ast.iter_child_nodes(knoten):
            eltern[kind] = knoten
    gefunden: Counter = Counter()
    for knoten in ast.walk(baum):
        if isinstance(knoten, ast.Constant) and isinstance(knoten.value, str) \
                and _WORT.search(knoten.value) and not isinstance(eltern.get(knoten), ast.Expr):
            oben = eltern.get(knoten)
            while oben is not None and not isinstance(oben, (ast.FunctionDef, ast.AsyncFunctionDef)):
                oben = eltern.get(oben)
            gefunden[(datei, oben.name if oben is not None else "<modul>")] += 1
    return gefunden


def test_ratsche_jede_erwaehnung_von_entscheide_im_betrieb():
    gefunden: Counter = Counter()
    for pfad in sorted((SRC / "betrieb").glob("*.py")):
        gefunden += _erwaehnungen(pfad.read_text(encoding="utf-8"), str(pfad.relative_to(SRC)))
    assert gefunden == ENTSCHEIDE_ERWAEHNUNGEN


def test_ratsche_positivkontrolle_der_erwaehnungen():
    quelle = ('P = "entscheide"\n'
              'def x(fall, sha):\n'
              '    """Liest entscheide/ (Docstring zaehlt nicht)."""\n'
              '    wer = "entscheider"\n'
              '    return fall / "entscheide" / ("A-M4-" + sha)\n')
    assert _erwaehnungen(quelle, "x.py") == Counter({("x.py", "<modul>"): 1, ("x.py", "x"): 1})


def test_die_ausnahme_zeichnung_aus_snapshot_begruendet_in_src_nichts():
    aufrufe = []
    for pfad in sorted(SRC.rglob("*.py")):
        for knoten in ast.walk(ast.parse(pfad.read_text(encoding="utf-8"))):
            if isinstance(knoten, ast.Call) and _name(knoten) == "zeichnung_aus_snapshot":
                aufrufe.append((str(pfad.relative_to(SRC)), ast.unparse(knoten.args[1])))
    assert aufrufe == [("betrieb/uebernahme.py", "None")]


# --------------------------------------------------------------------------- #
# Ratsche: kein Allzweck-Schluessel in den Test-Ordnungen
# --------------------------------------------------------------------------- #


def _allzweck(ordnung: dict) -> list:
    """Rollen, die Abnahmen des Falls (A-Q1, A-M*) UND des Betriebs (A-B*)
    zeichnen duerfen — oder alles ('*'); und Rollen, die einen Stand
    (A-K2 mensch/rechenkern, A-O1 mensch/architektur) zusammen mit einer
    anderen Abnahme zeichnen: A-M4 gruendet auf beiden, und ein gemeinsamer
    Schluessel verdeckte, wer den Stand abgenommen hat (Entscheid 2026-10-01)."""
    befund = []
    for name, eintrag in ordnung["rollen"].items():
        gates = set(eintrag.get("gates", []))
        fall = any(g.startswith(("A-M", "A-Q")) for g in gates)
        betrieb = any(g.startswith("A-B") for g in gates)
        kern = bool(gates & {"A-K2", "A-O1"}) and len(gates) > 1
        if "*" in gates or (fall and betrieb) or kern:
            befund.append(name)
    return befund


def test_ratsche_die_test_ordnungen_trennen_fall_und_betrieb(tmp_path):
    """Jede Ordnung, die die Suite dem Betrieb oder einem Fall-Gate gibt, hat
    getrennte Rollen fuer die Abnahmen des Falls und die des Betriebs —
    sonst verdeckte ein Schluessel den Fall, den die Rollenregel prueft."""
    from tests.test_betriebsschluessel_runde_c import _schluessel_und_ordnung
    from tests.zeichnung_fixture import standard_ordnung

    ordnungen = {
        "betriebsordnung": betriebsordnung(),
        "standard_ordnung": json.loads(standard_ordnung(
            tmp_path, tmp_path / "p9.key").read_text(encoding="utf-8")),
        "runde_c": json.loads(_schluessel_und_ordnung(
            tmp_path, "betrieb/nachtlauf", "betrieb")[1].read_text(encoding="utf-8")),
    }
    assert {n: _allzweck(o) for n, o in ordnungen.items()} == {n: [] for n in ordnungen}
    fp = {e["schluessel_sha256"] for e in freigaberollen().values()}
    assert len(fp) == len(freigaberollen())        # ein Schluessel je Rolle


#: Die Stellen, an denen ein Test noch '*' in eine gates-Liste schreibt.
#: Begruendet: Sie pruefen das Merkmal '*' der Ordnung selbst bzw. die
#: Zeichnung im Gate (ADR-018); keine signiert A-B1/A-B2, und keiner ihrer
#: Snapshots wird von einem Leser des Betriebs gelesen. Neue Stellen nicht.
#: ``test_erstabnahme_linie.py``: die Probe, dass eine Ordnung mit '*' NICHT
#: in die Versionslinie kommt (ADR-025) — sie wird nie gezeichnet. Seit die
#: Linie Pflicht ist (Nachtrag 2026-10-01), zeichnet KEINE Ordnung mit '*'
#: mehr: ``test_zeichnungsordnung.py`` prueft genau diese Verweigerung,
#: ``test_rollenmodell_adr018.py`` den Lader der Altform (Schema 1).
STERN_IN_TESTS = Counter({"test_rollenmodell_adr018.py": 1, "test_zeichnungsordnung.py": 1,
                          "test_erstabnahme_linie.py": 1})


def _sterne(quelle: str) -> int:
    return sum(1 for k in ast.walk(ast.parse(quelle)) if isinstance(k, ast.List)
               and any(isinstance(e, ast.Constant) and e.value == "*" for e in k.elts))


def test_ratsche_kein_neuer_stern_in_test_ordnungen():
    gefunden = Counter()
    for pfad in sorted(TESTS.glob("*.py")):
        if pfad.name == Path(__file__).name:
            continue
        anzahl = _sterne(pfad.read_text(encoding="utf-8"))
        if anzahl:
            gefunden[pfad.name] = anzahl
    assert gefunden == STERN_IN_TESTS


def test_ratsche_positivkontrolle_der_allzweck_detektoren():
    assert _allzweck({"rollen": {"a": {"gates": ["A-M4", "A-B2"]}, "b": {"gates": ["*"]},
                                 "c": {"gates": ["A-M4"]}, "d": {"gates": ["A-B2"]},
                                 "e": {"gates": ["A-K2", "A-M4"]},
                                 "f": {"gates": ["A-K2"]},
                                 "g": {"gates": ["A-O1", "A-Q1"]},
                                 "h": {"gates": ["A-O1"]}}}) == ["a", "b", "e", "g"]
    assert _sterne('x = {"gates": ["*"]}\ny = ["A-M4"]\n') == 1
