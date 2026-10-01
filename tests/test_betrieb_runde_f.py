"""Der Betrieb nach dem blinden Angriff, Runde F: Probenkopie, Probenbeleg, Anker.

Vier bestaetigte Funde, je ein roter Test vor dem Fix (Vorlagen: die
Repro-Skripte der Angreifer, hier als pytest nachgebaut):

* F9 — Die Kopie "mit" einer Zugangsprobe lief ohne Schluessel als
  produktive Ablage weiter: Kennzeichen geloescht, Kopie an die Stelle der
  Ablage gesetzt, und der naechste Tageslauf fuehrte einen Eingang, der nie
  durch A-B2 gegangen war — mit Zeilen, die der produktive
  Betriebsschluessel gezeichnet hatte. Das Kennzeichen ist eine
  ungezeichnete Datei; was ohne Schluessel verschwinden kann, unterscheidet
  nichts. Jetzt traegt jede Zeile eines Probelaufs GEZEICHNET das Feld
  ``zugangsprobe``, und jeder Leser ausser der Probe selbst verweigert eine
  Kette, die eine solche Zeile enthaelt.
* F6 — Die Probe kopierte erst und kennzeichnete dann; ein Prozessende
  dazwischen hinterliess eine ungekennzeichnete Vollkopie, auf der der
  Tageslauf gruen fuhr.
* F7 — Ein Ein-/Ausgabefehler beim Schreiben des Probenbelegs endete als
  Traceback mit Exit 1 — fuer einen Aufrufer dasselbe wie "nicht
  bestanden" — und hinterliess einen abgeschnittenen Beleg am festen Ort.
* F8 — Der Export haengte den Ankersatz an, bevor das Paket an seinem Ort
  stand; ein Abbruch danach liess den Konsumenten das unveraenderte,
  gueltige Paket als "umgeschrieben" abweisen.

Knoten: system/betrieb
"""

from __future__ import annotations

import ast
import dataclasses
import datetime as dt
import errno
import io
import json
import os
import re
import shutil
import subprocess
import sys
from pathlib import Path

import pytest

from rechner_pipeline.betrieb import seite as st
from rechner_pipeline.betrieb import tageslauf as tl
from rechner_pipeline.betrieb import uebernahme as ueb
from rechner_pipeline.betrieb import zugangsprobe as zpb
from rechner_pipeline.betrieb.tageslauf import EXIT_OK, Ablage, tageslauf
from rechner_pipeline.models import anker as ak
from rechner_pipeline.models import zugangsprobe as zp
from tests.freigabe_testschluessel import betriebsargs
from tests.test_betrieb_seite import _ablage
from tests.test_betrieb_uebernahme import STICHTAG
from tests.test_zugangsabnahme_ab2 import _welt

REPO_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO_ROOT / "werkzeuge"))
import falldaten as fd  # noqa: E402

#: Der erste Tag nach dem Fenster der Probe (Zugang 1.1., Abschluss 1.2.).
NACH_DER_PROBE = dt.date(2026, 2, 2)


# --------------------------------------------------------------------------- #
# F9 — eine Probenkopie bleibt eine, auch ohne ihr Kennzeichen
# --------------------------------------------------------------------------- #


@pytest.fixture(scope="module")
def probe_kopien(tmp_path_factory):
    """Echte Ablage, echter Fall, echte Probe; die Kopien bleiben stehen."""
    wurzel = tmp_path_factory.mktemp("runde-f-probe")
    fall, stand = _welt(wurzel)
    zpb.zugangsprobe(stand, fall, STICHTAG, arbeit=wurzel / "arbeit")
    return wurzel, fall, stand


def _befoerdert(probe_kopien, ziel: Path, kopie: str = zpb.KOPIE_MIT) -> Ablage:
    """Der Angreifer ohne Schluessel: Kopie an einen neuen Ort, Kennzeichen weg."""
    wurzel, _, _ = probe_kopien
    shutil.copytree(wurzel / "arbeit" / kopie, ziel, symlinks=True)
    (ziel / tl.ZUGANGSPROBE_KOPIE_DATEI).unlink()
    return Ablage(ziel)


def _zeilen(pfad: Path) -> list:
    return [json.loads(z) for z in pfad.read_text(encoding="utf-8").splitlines() if z.strip()]


def test_jede_zeile_eines_probelaufs_ist_gezeichnet_als_probezeile(probe_kopien):
    """Positivkontrolle der Kennung: Die Zeilen der Ablage tragen das Feld
    nicht, die Zeile des Probelaufs in JEDER Kopie traegt es — mit Fall,
    Kennung, Kopie und Zeitpunkt, und gezeichnet (die Probe selbst liest
    ihre Kette mit Schluessel)."""
    wurzel, _, stand = probe_kopien
    protokoll = Ablage(stand).protokoll_pfad
    original = _zeilen(protokoll) if protokoll.is_file() else []
    assert all(tl.ZUGANGSPROBE_FELD not in z for z in original)
    kennungen = set()
    for kopie in (zpb.KOPIE_OHNE, zpb.KOPIE_MIT):
        ablage = Ablage(wurzel / "arbeit" / kopie)
        zeilen = _zeilen(ablage.protokoll_pfad)
        assert len(zeilen) == len(original) + 1
        assert zeilen[: len(original)] == original
        probe = zeilen[-1][tl.ZUGANGSPROBE_FELD]
        assert probe["fall"] == "probe-uebernahme" and probe["kopie"] == kopie
        assert set(probe) == {"fall", "kennung", "kopie", "zeitpunkt"}
        kennungen.add(probe["kennung"])
        dt.datetime.fromisoformat(probe["zeitpunkt"])
        z = tl.betriebszeichner(ablage)
        tl.lies_protokoll(ablage.protokoll_pfad, schluesselring=z.ring, ordnung=z.ordnung,
                          zugangsprobe=True)
    assert len(kennungen) == 1, "beide Kopien einer Probe tragen dieselbe Kennung"


@pytest.mark.parametrize("kopie", [zpb.KOPIE_MIT, zpb.KOPIE_OHNE])
def test_repro_f9_befoerderte_kopie_ohne_kennzeichen_der_tageslauf_verweigert(
        probe_kopien, tmp_path, kopie):
    """Das Repro des Angreifers: Kennzeichen geloescht, Kopie an die Stelle
    der Ablage, der planmaessige Tageslauf. Vorher Exit 0, der Eingang ohne
    A-B2 gefuehrt.

    Mutationsprobe: die Probezeilen-Pruefung in lies_protokoll_text
    entfernen -> rot."""
    ablage = _befoerdert(probe_kopien, tmp_path / "daten", kopie)
    vorher = ablage.protokoll_pfad.read_bytes()
    with pytest.raises(tl.TageslaufError, match="Probenkopie"):
        tageslauf(ablage, NACH_DER_PROBE)
    assert ablage.protokoll_pfad.read_bytes() == vorher, "die Verweigerung schreibt nichts"


def test_die_probezeile_ist_gezeichnet_ohne_feld_bricht_die_signatur(probe_kopien, tmp_path):
    """Das Feld steht im gezeichneten Inhalt: Wer es ohne Schluessel
    entfernt, bricht die Zeichnung — der Lauf verweigert dann daran."""
    ablage = _befoerdert(probe_kopien, tmp_path / "daten")
    zeilen = ablage.protokoll_pfad.read_text(encoding="utf-8").splitlines()
    letzte = json.loads(zeilen[-1])
    assert tl.ZUGANGSPROBE_FELD in letzte
    del letzte[tl.ZUGANGSPROBE_FELD]
    zeilen[-1] = json.dumps(letzte, ensure_ascii=False, sort_keys=True)
    ablage.protokoll_pfad.chmod(0o644)
    ablage.protokoll_pfad.write_text("\n".join(zeilen) + "\n", encoding="utf-8")
    with pytest.raises(tl.TageslaufError, match="Signatur stimmt nicht"):
        tageslauf(ablage, NACH_DER_PROBE)


def _export(ablage: Ablage, tmp: Path, fall: Path) -> None:
    st.stands_paket(ablage, tmp / "paket", anker_verzeichnis=tmp / "anker")


def _neuaufsetzen(ablage: Ablage, tmp: Path, fall: Path) -> None:
    from rechner_pipeline.betrieb import neuaufsetzen as na

    try:
        na.neu_aufsetzen(ablage.wurzel, fall, STICHTAG)
    except na.NeuaufsetzenError as exc:
        raise tl.TageslaufError(str(exc)) from exc


def _registrierung(ablage: Ablage, tmp: Path, fall: Path) -> None:
    try:
        ueb.eingang_anlegen(ablage.wurzel, fall, STICHTAG)
    except ueb.UebernahmeError as exc:
        raise tl.TageslaufError(str(exc)) from exc


def _zugangsprobe(ablage: Ablage, tmp: Path, fall: Path) -> None:
    try:
        zpb.zugangsprobe(ablage.wurzel, fall, STICHTAG, arbeit=tmp / "arbeit2")
    except zpb.ZugangsprobeError as exc:
        raise tl.TageslaufError(str(exc)) from exc


def _konsument(ablage: Ablage, tmp: Path, fall: Path) -> None:
    """Der Konsument eines Pakets haelt keinen Schluessel; er liest die
    Kette mit derselben Funktion (werkzeuge/falldaten.py)."""
    tl.lies_protokoll_text(ablage.protokoll_pfad.read_text(encoding="utf-8"),
                           str(ablage.protokoll_pfad))


def _seite(ablage: Ablage, tmp: Path, fall: Path) -> None:
    st.rendere_bestand_heute(ablage)


#: Je Modul, das eine Ablage als Betrieb liest oder beschreibt, eine Instanz
#: (die Ratsche unten haelt die Menge gegen den Code).
INSTANZEN = {
    "tageslauf": lambda a, t, f: tageslauf(a, NACH_DER_PROBE),
    "seite": _export,
    "seite (Tagesseite ohne Schluessel)": _seite,
    "neuaufsetzen": _neuaufsetzen,
    "uebernahme": _registrierung,
    "zugangsprobe": _zugangsprobe,
    "falldaten": _konsument,
}


@pytest.mark.parametrize("instanz", sorted(INSTANZEN))
def test_zaehltest_jeder_leser_verweigert_die_befoerderte_probenkopie(
        probe_kopien, tmp_path, instanz):
    """Je Instanz: dieselbe befoerderte Kopie (die "ohne", damit die
    Registrierung nicht schon am vorhandenen Eingang scheitert), jeder Weg
    verweigert mit 'Probenkopie'.

    Mutationsprobe je Instanz: die jeweilige Pruefung entfernen -> rot."""
    _, fall, _ = probe_kopien
    ablage = _befoerdert(probe_kopien, tmp_path / "daten", zpb.KOPIE_OHNE)
    with pytest.raises((tl.TageslaufError, st.SeiteError, ValueError), match="Probenkopie"):
        INSTANZEN[instanz](ablage, tmp_path, fall)


def test_ratsche_die_instanzen_sind_die_module_die_eine_ablage_als_betrieb_lesen():
    """Statische Ratsche (benannt): Wer den Betriebsschluessel aufloest oder
    das Protokoll liest, steht im Zaehltest — mit ==, damit ein neuer Leser
    die Ratsche rot macht, bis er eine Instanz hat."""
    muster = re.compile(r"\b(betriebszeichner|lies_protokoll|lies_protokoll_text)\(")
    gefunden = set()
    for wurzel in (REPO_ROOT / "src", REPO_ROOT / "werkzeuge"):
        for pfad in wurzel.rglob("*.py"):
            if pfad.name == "_zeichnung.py":
                continue
            if muster.search(pfad.read_text(encoding="utf-8")):
                gefunden.add(pfad.stem)
    assert gefunden == {name.split(" ")[0] for name in INSTANZEN}


def test_die_probe_verweigert_auf_einer_gekennzeichneten_kopie(probe_kopien, tmp_path):
    """Die Probe kopiert IN ein gekennzeichnetes Verzeichnis (F6) — eine
    Ablage, die selbst ein Kennzeichen traegt, wuerde es dabei
    ueberschreiben. Sie ist keine Ablage fuer eine Probe — auch dann, wenn
    sie noch keine Probezeile traegt (eine Kopie, deren Probe vor dem ersten
    Lauf endete, F6)."""
    _, fall, stand = probe_kopien
    kopie = tmp_path / "kopie"
    shutil.copytree(stand, kopie, symlinks=True)
    (kopie / tl.ZUGANGSPROBE_KOPIE_DATEI).write_text('{"fall": "probe-uebernahme"}', encoding="utf-8")
    with pytest.raises(zpb.ZugangsprobeError, match="Probenkopie"):
        zpb.zugangsprobe(kopie, fall, STICHTAG, arbeit=tmp_path / "arbeit")
    assert not (tmp_path / "arbeit").exists() or not any((tmp_path / "arbeit").iterdir())


def test_der_eintritt_ohne_a_b2_gilt_nur_fuer_eine_als_probe_gezeichnete_zeile(probe_kopien, tmp_path):
    """Die Ausnahme vom A-B2 im Probelauf haengt an der Probezeile: Ein Lauf,
    dessen Zeichner keine Probe ist, tritt auch mit ``zugangsprobe_fall``
    nicht ohne Abnahme ein.

    Bezeugt den Waechter in _tageslauf (Parameter gegen Zeichner), nicht die
    Bindung in _stand_bauen — die verweigert hinter ihm und bezeugt sich im
    direkten Aufruf (Runde F, Nachbesserung:
    test_stand_bauen_bindet_die_ausnahme_an_den_zeichner_nicht_an_den_parameter).

    Mutationsprobe: den Waechter in _tageslauf entfernen -> rot."""
    _, fall, stand = probe_kopien
    kopie = tmp_path / "kopie"
    shutil.copytree(stand, kopie, symlinks=True)
    (kopie / tl.ZUGANGSPROBE_KOPIE_DATEI).write_text("{}", encoding="utf-8")
    ueb.eingang_anlegen(kopie, fall, STICHTAG, probe_kopie=True)
    ablage = Ablage(kopie)
    zeichner = tl.betriebszeichner(ablage)
    assert zeichner.zugangsprobe is None
    with pytest.raises(tl.TageslaufError, match="Probezeile"):
        tl._tageslauf(ablage, NACH_DER_PROBE, zeichner, zugangsprobe_fall="probe-uebernahme")


def test_die_tagesseite_einer_probenkopie_liest_nur_der_probezeichner(probe_kopien):
    """Die Tagesseite rendert im Probelauf auf der Kopie (Tageslauf mit
    Probe-Zeichner); ohne ihn verweigert sie die Probezeilen.

    Mutationsprobe: das Durchreichen in seite.stand_modell_mit_bytes
    entfernen -> rot."""
    wurzel, _, _ = probe_kopien
    ablage = Ablage(wurzel / "arbeit" / zpb.KOPIE_MIT)
    zeichner = tl.betriebszeichner(ablage)
    probe = dataclasses.replace(zeichner, zugangsprobe=tl._probe_angaben(
        ablage.wurzel / tl.ZUGANGSPROBE_KOPIE_DATEI, "probe-uebernahme"))
    assert st.rendere_bestand_heute(ablage, zeichner=probe).is_file()
    with pytest.raises(st.SeiteError, match="Probenkopie"):
        st.rendere_bestand_heute(ablage, zeichner=zeichner)


# --------------------------------------------------------------------------- #
# F9, Nachbesserung — Bindung, Form und Herkunft der Probezeile; die Tueren
# --------------------------------------------------------------------------- #


#: Vollstaendige Angaben einer Probezeile (die Form, die die Probe schreibt).
VOLLE_ANGABEN = {"fall": "probe-uebernahme", "kennung": "ab" * 32, "kopie": zpb.KOPIE_MIT,
                 "zeitpunkt": "2026-02-01T08:00:00+00:00"}


def _kopie_mit_eingang(stand: Path, fall: Path, ziel: Path, kennzeichen: dict) -> Ablage:
    """Eine gekennzeichnete Kopie der Ablage, in der der Eingang des Falls
    ohne A-B2 registriert ist — wie die Probe sie anlegt."""
    shutil.copytree(stand, ziel, symlinks=True)
    (ziel / tl.ZUGANGSPROBE_KOPIE_DATEI).write_text(json.dumps(kennzeichen), encoding="utf-8")
    ueb.eingang_anlegen(ziel, fall, STICHTAG, probe_kopie=True)
    return Ablage(ziel)


def test_stand_bauen_bindet_die_ausnahme_an_den_zeichner_nicht_an_den_parameter(
        probe_kopien, tmp_path):
    """Runde F, Nachbesserung: Der Test oben bezeugte den Waechter in
    _tageslauf; die Bindung in _stand_bauen dahinter war blind (Mutation
    "Bindung weg" blieb gruen). Hier _stand_bauen DIREKT, mit
    ``zugangsprobe_fall`` und einem Zeichner ohne Probe: Der Eingang tritt
    nicht ohne A-B2 ein. Positivkontrolle: Mit dem Probe-Zeichner baut
    derselbe Aufruf den Stand.

    Mutationsprobe: die Bindung in _stand_bauen entfernen -> rot."""
    _, fall, stand = probe_kopien
    ablage = _kopie_mit_eingang(stand, fall, tmp_path / "kopie", VOLLE_ANGABEN)
    config = tl.load_config(ablage.config_pfad)
    zeichner = tl.betriebszeichner(ablage)
    assert zeichner.zugangsprobe is None
    with pytest.raises(ueb.UebernahmeError, match="A-B2"):
        tl._stand_bauen(config, ablage.config_pfad, ablage, NACH_DER_PROBE, zeichner,
                        zugangsprobe_fall="probe-uebernahme")
    probe = dataclasses.replace(zeichner, zugangsprobe=dict(VOLLE_ANGABEN))
    arbeit, _ = tl._stand_bauen(config, ablage.config_pfad, ablage, NACH_DER_PROBE, probe,
                                zugangsprobe_fall="probe-uebernahme")
    assert Path(arbeit).is_dir()


#: Je Angabe des Kennzeichens (der Fall kommt aus dem Auftrag, nicht aus
#: dem Kennzeichen) und je Art, sie zu verfehlen.
KENNZEICHEN_ANGABEN = ("kennung", "kopie", "zeitpunkt")
VERFEHLUNGEN = {"fehlt": None, "leer": "", "kein Text": 20260201}


def _verfehlt(angaben: dict, feld: str, art: str) -> dict:
    kaputt = dict(angaben)
    if art == "fehlt":
        del kaputt[feld]
    else:
        kaputt[feld] = VERFEHLUNGEN[art]
    return kaputt


def test_zaehltest_kennzeichen_angaben_decken_die_probezeile():
    """Die Menge unten ist die der Probezeile ohne den Fall — eine neue
    Angabe ohne Fall im Zaehltest macht das rot."""
    assert set(KENNZEICHEN_ANGABEN) == set(tl.ZUGANGSPROBE_ANGABEN) - {"fall"}


@pytest.mark.parametrize("art", sorted(VERFEHLUNGEN))
@pytest.mark.parametrize("feld", KENNZEICHEN_ANGABEN)
def test_ein_kennzeichen_ohne_volle_angaben_bezeugt_keine_probe(probe_kopien, tmp_path, feld, art):
    """Runde F, Nachbesserung: Die Formpruefung der Probezeile war blind
    (Mutation "Formpruefung weg" blieb gruen). Ein Kennzeichen, dem Kennung,
    Kopie oder Zeitpunkt fehlt — oder leer, oder kein Text —, ergibt keine
    Probezeile: Der Probelauf verweigert, bevor er die Kopie anfasst.
    Positivkontrolle: dasselbe Kennzeichen vollstaendig traegt.

    Mutationsprobe: die Formpruefung in probezeile_fehler entfernen -> rot."""
    _, _, stand = probe_kopien
    kopie = tmp_path / "kopie"
    shutil.copytree(stand, kopie, symlinks=True)
    kennzeichen = kopie / tl.ZUGANGSPROBE_KOPIE_DATEI
    kennzeichen.write_text(json.dumps(VOLLE_ANGABEN), encoding="utf-8")
    assert tl._probe_angaben(kennzeichen, "probe-uebernahme") == VOLLE_ANGABEN
    kennzeichen.write_text(json.dumps(_verfehlt(VOLLE_ANGABEN, feld, art)), encoding="utf-8")
    ablage = Ablage(kopie)
    vorher = sorted(str(p.relative_to(kopie)) for p in kopie.rglob("*"))
    with pytest.raises(tl.TageslaufError, match="bezeugt keine Probe"):
        tageslauf(ablage, NACH_DER_PROBE, zugangsprobe_fall="probe-uebernahme")
    assert sorted(str(p.relative_to(kopie)) for p in kopie.rglob("*")) == vorher


def _probekette_mit(probe_kopien, feld_wert) -> tuple:
    """Die Kette der Kopie "mit", ihre Probezeile mit ``feld_wert`` als
    Probefeld NEU GEZEICHNET — die Signatur stimmt, nur die Form nicht."""
    wurzel, _, _ = probe_kopien
    ablage = Ablage(wurzel / "arbeit" / zpb.KOPIE_MIT)
    zeichner = tl.betriebszeichner(ablage)
    rohe = ablage.protokoll_pfad.read_text(encoding="utf-8").splitlines()
    letzte = json.loads(rohe[-1])
    letzte[tl.ZUGANGSPROBE_FELD] = feld_wert
    del letzte["zeichnung"]
    letzte["zeichnung"] = zeichner.zeichne(letzte)
    rohe[-1] = json.dumps(letzte, ensure_ascii=False, sort_keys=True)
    return "\n".join(rohe) + "\n", zeichner


#: Je Angabe der Probezeile jede Verfehlung, dazu eine fremde Angabe und
#: ein Feld, das kein Objekt ist.
FORMFEHLER = {f"{feld} {art}": (feld, art) for feld in tl.ZUGANGSPROBE_ANGABEN
              for art in VERFEHLUNGEN}
FORMFEHLER_SONST = {"fremde Angabe": {**VOLLE_ANGABEN, "fremd": "x"},
                    "kein Objekt": "probe-uebernahme", "leeres Objekt": {}}


@pytest.mark.parametrize("fehler", sorted(FORMFEHLER) + sorted(FORMFEHLER_SONST))
def test_der_probeleser_bricht_an_einer_probezeile_ohne_volle_angaben(probe_kopien, fehler):
    """Runde F, Nachbesserung: Auch der Leser, der Probezeilen liest, nimmt
    nur eine vollstaendige — gezeichnet oder nicht: Ein Feld ohne Fall,
    Kennung, Kopie und Zeitpunkt als Text bezeugt keine Probe, die Kette
    bricht. Die Zeile ist neu gezeichnet; es urteilt die Form, nicht die
    Signatur. Positivkontrolle: dieselbe Zeile mit vollen Angaben liest er.

    Mutationsprobe: die Formpruefung in probezeile_fehler entfernen -> rot."""
    wert = (_verfehlt(VOLLE_ANGABEN, *FORMFEHLER[fehler]) if fehler in FORMFEHLER
            else FORMFEHLER_SONST[fehler])
    text, zeichner = _probekette_mit(probe_kopien, dict(VOLLE_ANGABEN))
    tl.lies_protokoll_text(text, "p", schluesselring=zeichner.ring, ordnung=zeichner.ordnung,
                           zugangsprobe=True)
    text, zeichner = _probekette_mit(probe_kopien, wert)
    with pytest.raises(tl.TageslaufError, match="bricht die Kette.*bezeugt keine Probe"):
        tl.lies_protokoll_text(text, "p", schluesselring=zeichner.ring,
                               ordnung=zeichner.ordnung, zugangsprobe=True)


def test_zaehltest_formfehler_decken_jede_angabe():
    assert {feld for feld, _ in FORMFEHLER.values()} == set(tl.ZUGANGSPROBE_ANGABEN)
    assert len(FORMFEHLER) == len(tl.ZUGANGSPROBE_ANGABEN) * len(VERFEHLUNGEN)


FREMDE_ANGABEN = {"fall": "fremd", "kennung": "cd" * 32, "kopie": zpb.KOPIE_OHNE,
                  "zeitpunkt": "2026-01-15T08:00:00+00:00"}


@pytest.mark.parametrize("mit_feld", [False, True], ids=["zeile ohne Feld", "zeile mit fremdem Feld"])
@pytest.mark.parametrize("probe", [False, True], ids=["betriebszeichner", "probezeichner"])
def test_die_probezeile_entsteht_nur_aus_dem_zeichner(tmp_path, probe, mit_feld):
    """Runde F, Nachbesserung: _anfuegen nahm das Probefeld der Zeile weg,
    und kein Test sah es (Mutation "pop weg" blieb gruen). Je Zeichner und
    Zeile: Das Feld der geschriebenen Zeile ist das des Zeichners — beim
    Betriebszeichner keines, auch wenn die Zeile eines mitbringt; beim
    Probezeichner seines, nie das der Zeile. Der zugehoerige Leser liest
    die Kette.

    Mutationsprobe: zeile.pop(ZUGANGSPROBE_FELD) in _anfuegen entfernen -> rot."""
    pfad = tmp_path / "daten" / "journal" / "protokoll.jsonl"
    zeichner = tl.betriebszeichner(Ablage(tmp_path / "daten"))
    if probe:
        zeichner = dataclasses.replace(zeichner, zugangsprobe=dict(VOLLE_ANGABEN))
    zeile = {"heute": NACH_DER_PROBE.isoformat(), "exit_code": EXIT_OK}
    if mit_feld:
        zeile[tl.ZUGANGSPROBE_FELD] = dict(FREMDE_ANGABEN)
    tl._anfuegen(pfad, zeile, zeichner)
    geschrieben = _zeilen(pfad)[-1]
    assert geschrieben.get(tl.ZUGANGSPROBE_FELD) == zeichner.zugangsprobe
    tl.lies_protokoll(pfad, schluesselring=zeichner.ring, ordnung=zeichner.ordnung,
                      zugangsprobe=probe)


def probe_tueren(quelltext: str) -> set:
    """Jede Stelle, die einen Leser oder Zeichner zur PROBE macht: ein
    Aufruf mit ``zugangsprobe=`` und einem anderen Wert als dem Standard
    ``False``, eine Zuweisung an ``.zugangsprobe`` und ``setattr`` darauf.
    Rueckgabe je Stelle (Funktion, Aufgerufenes, Wert)."""
    gefunden = set()

    def besuch(knoten, funktion):
        for kind in ast.iter_child_nodes(knoten):
            f = kind.name if isinstance(kind, (ast.FunctionDef, ast.AsyncFunctionDef)) else funktion
            if isinstance(kind, ast.Call):
                name = ast.unparse(kind.func)
                for kw in kind.keywords:
                    if kw.arg == "zugangsprobe" and not (
                            isinstance(kw.value, ast.Constant) and kw.value.value is False):
                        gefunden.add((f, name, ast.unparse(kw.value)))
                if (name in ("setattr", "object.__setattr__") and len(kind.args) >= 2
                        and isinstance(kind.args[1], ast.Constant)
                        and kind.args[1].value == "zugangsprobe"):
                    gefunden.add((f, name, ast.unparse(kind.args[2]) if len(kind.args) > 2 else ""))
            if isinstance(kind, (ast.Assign, ast.AnnAssign, ast.AugAssign)):
                ziele = kind.targets if isinstance(kind, ast.Assign) else [kind.target]
                for ziel in ziele:
                    if isinstance(ziel, ast.Attribute) and ziel.attr == "zugangsprobe":
                        gefunden.add((f, "=", ast.unparse(kind.value) if kind.value else ""))
            besuch(kind, f)

    besuch(ast.parse(quelltext), "<modul>")
    return gefunden


#: Die Tueren zur Probe, wie sie heute stehen: drei Leser, die den Zeichner
#: fragen, zwei Durchreichungen, die Formpruefung des Kennzeichens und der
#: eine Ort, der einen Probe-Zeichner baut (``tageslauf`` auf der
#: gekennzeichneten Kopie).
PROBE_TUEREN = {
    ("src/rechner_pipeline/betrieb/seite.py", "_gepruefte_zeilen", "lies_protokoll",
     "getattr(zeichner, 'zugangsprobe', None) is not None"),
    ("src/rechner_pipeline/betrieb/tageslauf.py", "_anfuegen", "lies_protokoll_text",
     "zeichner.zugangsprobe is not None"),
    ("src/rechner_pipeline/betrieb/tageslauf.py", "_protokoll", "lies_protokoll",
     "z.zugangsprobe is not None"),
    ("src/rechner_pipeline/betrieb/tageslauf.py", "lies_protokoll", "lies_protokoll_text",
     "zugangsprobe"),
    ("src/rechner_pipeline/betrieb/tageslauf.py", "lies_protokoll_text", "probezeile_fehler",
     "zugangsprobe"),
    ("src/rechner_pipeline/betrieb/tageslauf.py", "_probe_angaben", "probezeile_fehler", "True"),
    ("src/rechner_pipeline/betrieb/tageslauf.py", "tageslauf", "dataclasses.replace",
     "_probe_angaben(kopie, zugangsprobe_fall)"),
}


def test_ratsche_probe_tueren_detektor_positivkontrolle():
    """Der Detektor findet jede Bauform, die er zaehlt — und den Standard
    ``zugangsprobe=False`` nicht."""
    quelle = (
        "def a(p, z):\n"
        "    lies_protokoll(p, zugangsprobe=True)\n"
        "    lies_protokoll_text(p, 'x', zugangsprobe=False)\n"
        "    dataclasses.replace(z, zugangsprobe={})\n"
        "def b(z):\n"
        "    z.zugangsprobe = 1\n"
        "    object.__setattr__(z, 'zugangsprobe', 2)\n"
    )
    assert probe_tueren(quelle) == {
        ("a", "lies_protokoll", "True"), ("a", "dataclasses.replace", "{}"),
        ("b", "=", "1"), ("b", "object.__setattr__", "2")}


def test_ratsche_die_tueren_zur_probe_sind_genau_die_heutigen():
    """Runde F, Nachbesserung — statische Ratsche (==): Wer einen Leser
    oder Zeichner zur Probe macht, liest eine Kette mit Probezeilen oder
    schreibt sie; eine neue solche Stelle umginge F9 still. Sie macht die
    Ratsche rot, bis sie hier steht (und einen Test hat). Positivkontrolle:
    die Menge ist nicht leer, jede heutige Stelle wird gefunden (==)."""
    gefunden = set()
    for wurzel in (REPO_ROOT / "src", REPO_ROOT / "werkzeuge"):
        for pfad in sorted(wurzel.rglob("*.py")):
            rel = pfad.relative_to(REPO_ROOT).as_posix()
            gefunden |= {(rel, *t) for t in probe_tueren(pfad.read_text(encoding="utf-8"))}
    assert PROBE_TUEREN and gefunden == PROBE_TUEREN


# --------------------------------------------------------------------------- #
# F6 — das Kennzeichen besteht vor dem ersten kopierten Byte
# --------------------------------------------------------------------------- #


_PROZESSENDE_NACH_COPYTREE = """
import os, shutil, sys, datetime as dt
from pathlib import Path
from rechner_pipeline.betrieb import tageslauf as tl
from rechner_pipeline.betrieb import uebernahme as ueb
from rechner_pipeline.betrieb import zugangsprobe as zpb
from tests.freigabe_testschluessel import TESTRING
ueb._STANDARD_SCHLUESSELRING = TESTRING
tl._STANDARD_BETRIEBSZEICHNUNG = (Path(sys.argv[4]), Path(sys.argv[5]))
echt = shutil.copytree
tiefe = [0]
def stirbt(*a, **k):
    # copytree ruft sich fuer Unterverzeichnisse selbst: Ende erst nach dem aeussersten.
    tiefe[0] += 1
    try:
        echt(*a, **k)
    finally:
        tiefe[0] -= 1
    if tiefe[0] == 0:
        sys.stderr.flush()
        os._exit(77)
zpb.shutil.copytree = stirbt
zpb.zugangsprobe(Path(sys.argv[1]), Path(sys.argv[2]), dt.date(2026, 1, 1), arbeit=Path(sys.argv[3]))
"""


def test_repro_f6_prozessende_nach_der_kopie_hinterlaesst_eine_gekennzeichnete_kopie(tmp_path):
    """Das Repro des Angreifers: Prozessende (os._exit) unmittelbar nach dem
    Kopieren der ersten Kopie. Vorher lag dort eine Ablage ohne Kennzeichen,
    und der Tageslauf fuehrte sie gruen.

    Mutationsprobe: das Kennzeichen wieder nach copytree schreiben -> rot."""
    fall, stand = _welt(tmp_path)
    assert tageslauf(Ablage(stand), dt.date(2025, 12, 10))[0] == EXIT_OK
    arbeit = tmp_path / "arbeit"
    schluessel, ordnung = tl._STANDARD_BETRIEBSZEICHNUNG
    umgebung = dict(os.environ, PYTHONPATH=os.pathsep.join(
        [str(REPO_ROOT / "src"), str(REPO_ROOT)]))
    r = subprocess.run([sys.executable, "-c", _PROZESSENDE_NACH_COPYTREE, str(stand), str(fall),
                        str(arbeit), str(schluessel), str(ordnung)],
                       capture_output=True, text=True, cwd=str(REPO_ROOT), env=umgebung)
    assert r.returncode == 77, r.stderr[-2000:]
    kopie = arbeit / zpb.KOPIE_OHNE
    assert (kopie / "journal" / "protokoll.jsonl").is_file(), "die Kopie ist vollstaendig"
    assert (kopie / tl.ZUGANGSPROBE_KOPIE_DATEI).is_file()
    with pytest.raises(tl.TageslaufError, match="Kopie einer Zugangsprobe"):
        tageslauf(Ablage(kopie), dt.date(2025, 12, 11))


# --------------------------------------------------------------------------- #
# F7 — ein Fehler beim Beleg ist Exit 2, und der feste Ort bleibt ganz
# --------------------------------------------------------------------------- #


_BELEG = {"bestanden": True, "vergleiche": [], "befunde": [], "art": zp.ART}


def _fall_fuer_main(tmp_path: Path) -> Path:
    fall = tmp_path / "fall"
    (fall / "abgeleitet" / "berichte").mkdir(parents=True)
    return fall


def _main(fall: Path, stand: Path, *extra) -> int:
    return zpb.main(["--stand", str(stand), "--fall", str(fall), "--stichtag", STICHTAG.isoformat(),
                     *betriebsargs("--schluessel"), *extra])


def test_repro_f7_der_beleg_ort_ist_nicht_anlegbar_exit_2(tmp_path, monkeypatch, capsys):
    """Ein OSError beim Anlegen des Belegverzeichnisses: vorher Traceback mit
    Exit 1 (= "nicht bestanden"), jetzt Exit 2 mit Meldung.

    Mutationsprobe: das Schreiben wieder hinter den try-Block -> rot."""
    fall = _fall_fuer_main(tmp_path)
    monkeypatch.setattr(zpb, "zugangsprobe", lambda *a, **k: dict(_BELEG))
    (tmp_path / "datei").write_text("x", encoding="utf-8")
    code = _main(fall, tmp_path / "daten", "--out", str(tmp_path / "datei" / "beleg.json"))
    assert code == 2
    assert "Ein-/Ausgabefehler" in capsys.readouterr().err


class _HalbeSchreibung:
    """Ein Dateiobjekt, das die Haelfte schreibt und dann mit EIO scheitert —
    der kurze Schreibvorgang einer vollen Platte."""

    def __init__(self, datei):
        self._datei = datei

    def write(self, daten):
        self._datei.write(daten[: len(daten) // 2])
        self._datei.flush()
        raise OSError(errno.EIO, "injizierter E/A-Fehler beim Beleg")

    def __enter__(self):
        return self

    def __exit__(self, *exc):
        return self._datei.__exit__(*exc)

    def __getattr__(self, name):
        return getattr(self._datei, name)


def _pfad_von(datei) -> "Path | None":
    if isinstance(datei, int):
        try:
            return Path(os.readlink(f"/proc/self/fd/{datei}"))
        except OSError:
            return None
    try:
        return Path(os.fspath(datei)).absolute()
    except TypeError:
        return None


@pytest.mark.skipif(not Path("/proc/self/fd").is_dir(), reason="braucht /proc (Linux)")
def test_repro_f7_ein_abgebrochener_beleg_laesst_den_alten_am_festen_ort(tmp_path, monkeypatch, capsys):
    """Ein EIO mitten im Schreiben des Belegs: vorher ein abgeschnittener
    Beleg am festen Ort und Exit 1. Jetzt Exit 2, und am festen Ort liegt
    unveraendert, was vorher dort lag — kein Tempfile-Rest daneben.

    Mutationsprobe: wieder direkt an den festen Ort schreiben -> rot."""
    fall = _fall_fuer_main(tmp_path)
    berichte = (fall / "abgeleitet" / "berichte").resolve()
    alt = b'{"alt": "der Beleg der vorigen Probe"}\n'
    (fall / zp.BELEG_RELATIV).write_bytes(alt)
    monkeypatch.setattr(zpb, "zugangsprobe", lambda *a, **k: dict(_BELEG))
    echt = io.open

    def gestoert(datei, modus="r", *a, **k):
        f = echt(datei, modus, *a, **k)
        pfad = _pfad_von(datei)
        if pfad is not None and pfad.parent.resolve() == berichte and set(modus) & set("wax"):
            return _HalbeSchreibung(f)
        return f

    monkeypatch.setattr(io, "open", gestoert)
    code = _main(fall, tmp_path / "daten")
    monkeypatch.undo()
    assert code == 2
    assert "Ein-/Ausgabefehler" in capsys.readouterr().err
    assert (fall / zp.BELEG_RELATIV).read_bytes() == alt
    assert sorted(p.name for p in berichte.iterdir()) == [Path(zp.BELEG_RELATIV).name]


def test_f7_positivkontrolle_der_beleg_steht_vollstaendig_am_festen_ort(tmp_path, monkeypatch):
    fall = _fall_fuer_main(tmp_path)
    monkeypatch.setattr(zpb, "zugangsprobe", lambda *a, **k: dict(_BELEG))
    assert _main(fall, tmp_path / "daten") == 0
    assert json.loads((fall / zp.BELEG_RELATIV).read_text(encoding="utf-8")) == _BELEG


# --------------------------------------------------------------------------- #
# F8 — der Anker kommt erst, wenn das Paket an seinem Ort steht
# --------------------------------------------------------------------------- #


@pytest.fixture(scope="module")
def exportiert(tmp_path_factory):
    """Gefuehrt bis 3.2., exportiert (Paket + Anker), dann der 4.2. gefuehrt."""
    wurzel = tmp_path_factory.mktemp("runde-f-export")
    ablage = _ablage(wurzel / "daten")
    assert tageslauf(ablage, dt.date(2026, 2, 3))[0] == EXIT_OK
    st.stands_paket(ablage, wurzel / "paket", anker_verzeichnis=wurzel / "anker")
    assert tageslauf(ablage, dt.date(2026, 2, 4))[0] == EXIT_OK
    return wurzel


class _Prozessende(BaseException):
    """Ein Prozessende an der Naht: kein except Exception faengt es."""


def _konsument_urteil(welt: Path):
    try:
        return "ok", fd.betrieb(welt / "paket", welt / "anker" / ak.ANKER_DATEI)["stand"]
    except Exception as exc:  # noqa: BLE001 - das Urteil des Konsumenten
        return "abgewiesen", str(exc)


#: Die Operationen des Exports, die der Ankersatz nicht ueberholen darf —
#: je eine Stoerstelle. "haenge_an:nach" ist der Satz auf der Platte und ein
#: Fehler danach (EIO beim Schliessen).
STOERSTELLEN = ("haenge_an:vor", "haenge_an:nach", "stand.json", "bau-marker",
                "rename:beiseite", "rename:an-den-ort")


def _stoere(monkeypatch, stelle: str, fehler: BaseException) -> None:
    if stelle.startswith("haenge_an"):
        echt = st.haenge_an

        def haenge_an(verzeichnis, satz):
            if stelle == "haenge_an:nach":
                echt(verzeichnis, satz)
            raise fehler

        monkeypatch.setattr(st, "haenge_an", haenge_an)
    elif stelle == "stand.json":
        echt_s = st._schreibe

        def schreibe(pfad, text):
            if Path(pfad).name == st.PAKET_DATEI:
                raise fehler
            return echt_s(pfad, text)

        monkeypatch.setattr(st, "_schreibe", schreibe)
    elif stelle == "bau-marker":
        echt_u = Path.unlink

        def unlink(self, *a, **k):
            if self.name == st.PAKET_BAU_MARKER:
                raise fehler
            return echt_u(self, *a, **k)

        monkeypatch.setattr(Path, "unlink", unlink)
    else:
        echt_r = os.rename

        def rename(quelle, ziel, *a, **k):
            beiseite = Path(ziel).name.endswith(".alt")
            an_den_ort = Path(quelle).name.endswith(".im-bau")
            if (stelle == "rename:beiseite" and beiseite) or (stelle == "rename:an-den-ort" and an_den_ort):
                raise fehler
            return echt_r(quelle, ziel, *a, **k)

        monkeypatch.setattr(os, "rename", rename)


@pytest.mark.parametrize("art", ["oserror", "prozessende"])
@pytest.mark.parametrize("stelle", STOERSTELLEN)
def test_repro_f8_kein_abbruch_des_exports_macht_ein_gueltiges_paket_zum_manipulationsbefund(
        exportiert, tmp_path, monkeypatch, stelle, art):
    """Das Repro des Angreifers als Klasse: an jeder Stelle des Exports ein
    E/A-Fehler oder ein Prozessende. Danach sagt der Konsument entweder ja
    (altes oder neues Paket, jeweils mit seinem Anker) oder ehrlich, dass
    der genannte Satz nicht in der Ankerdatei steht — nie "umgeschrieben"
    ueber ein Paket, das niemand veraendert hat. Ein E/A-Fehler ist Exit 2
    mit Ausweg; ein sauberer Export danach stellt alles her.

    Mutationsprobe: haenge_an wieder vor stand.json -> rot."""
    welt = tmp_path / "w"
    shutil.copytree(exportiert, welt, symlinks=True)
    ablage = Ablage(welt / "daten")
    assert _konsument_urteil(welt) == ("ok", "2026-02-03")
    fehler = OSError(errno.EIO, "injiziert") if art == "oserror" else _Prozessende()
    _stoere(monkeypatch, stelle, fehler)
    if art == "oserror":
        code = st.main(["--stand", str(ablage.wurzel), "--paket", str(welt / "paket"),
                        "--anker", str(welt / "anker"), *betriebsargs("--betriebsschluessel")])
        assert code in (0, 2), code
    else:
        with pytest.raises(_Prozessende):
            st.stands_paket(ablage, welt / "paket", anker_verzeichnis=welt / "anker")
    monkeypatch.undo()
    urteil, text = _konsument_urteil(welt)
    if urteil == "abgewiesen":
        assert "nicht mehr im Protokoll" not in text and "umgeschrieben" not in text, text
        assert art == "prozessende", f"ein E/A-Fehler hinterlaesst einen pruefbaren Zustand: {text}"
    elif art == "oserror" and stelle != "haenge_an:nach":
        assert text == "2026-02-03", "gescheitert heisst: das vorige Paket steht"
    st.stands_paket(ablage, welt / "paket", anker_verzeichnis=welt / "anker")
    assert _konsument_urteil(welt) == ("ok", "2026-02-04")
    assert not [p.name for p in welt.iterdir() if p.name.startswith(".paket")]
