"""deploy/welt: eigene Schluessel entstehen sicher, und der Ring eines Gates passt zur Ordnung.

Die Skripte stellen eine Welt auf und fuehren darin einen Fall. Rechnen und
zeichnen tut das System; was die Skripte selbst entscheiden — und was ein
Test deshalb halten kann —, ist Mechanik:

* Die Phase ``schluessel`` erzeugt je Rolle einen Schluessel, den niemand
  sieht (0600, nie in der Ausgabe), ueberschreibt nie einen vorhandenen und
  legt nichts in Welt oder Codebaum. Die erzeugte Zeichnungsordnung besteht
  die Regeln des Systems (``models.zeichnung.pruefe_ordnung``) und nennt je
  Rolle den Fingerabdruck genau ihres Schluessels.
* Die Einstellungsdatei liest spaeter die Shell. Ein Wert, der dort Code
  wuerde, wird verweigert, BEVOR ein Schluessel entsteht.
* ``fall_zeichnen.sh`` reicht je Gate einen Ring. Der letzte Schluessel
  zeichnet — er muss der Rolle gehoeren, der die Ordnung das Gate gibt; sonst
  verweigert das Gate erst beim Zeichnen, mitten im Fall.
* ``fall_starten.sh`` haelt an, bevor es etwas anlegt, und ein gescheitertes
  Anlegen blockiert keinen zweiten Versuch.
* ``fall_nachfahren.sh`` faehrt ein Paket Schritt fuer Schritt: Es faehrt
  nichts doppelt (auch nach Haltepunkt oder Fehler nicht), legt nie ueber eine
  andere Datei, nimmt nur ein Paket, das seinen Pruefsummen entspricht, und
  haelt an, wenn ein Ergebnis andere Bytes traegt als festgehalten.
  Den abgenommenen Stand, gegen den ein Beleg seine Aenderung zeigt, nennt
  das Rezept nicht selbst: ``abgenommen <gate>`` liest ihn aus der Linie der
  Welt, in der nachgefahren wird. Hat ein Mensch an einem Haltepunkt selbst
  gezeichnet, zeichnet das Rezept nicht noch einmal — und nie ueber eine
  Ablehnung hinweg.
* ``zugang.sh`` bringt den abgenommenen Bestand in die Ablage: Es haelt,
  bevor es etwas anfasst (keine Migrationsabnahme, keine Zugangsabnahme, eine
  Probe, die schon liegt, ein unsauberer Baum), und reicht je Phase den Ring,
  den ihr Kommando braucht.
* ``paket_bauen.sh`` baut aus einem gefuehrten Fall ein Paket, das
  ``fall_nachfahren.sh`` annimmt: Rezept und Paket gehoeren zusammen,
  Zeichnungen kommen nie hinein, nichts wird ueberschrieben. Das Paket nennt
  den Stand, auf dem die Linie des Falls abgenommen war — aus der Linie
  gelesen, nie erfunden.
* ``laufzeit_aufstellen.sh`` stellt die Welt auf DIESEM Stand auf (als eigener
  Baum in der Welt) und faehrt den Fall auf dem Stand danach; es haelt, bevor
  es etwas anlegt, und stellt eine stehende Welt nicht zweimal auf.
* Jedes Systemkommando, das ein Skript faehrt, nimmt der Parser seines Moduls
  an (dieselbe Pruefung wie fuer die Dokumente,
  ``tests/test_dokumentierte_kommandos.py``): Ein Skript, das einen entfallenen
  Schalter nennt, scheitert sonst erst beim Aufstellen — nach Minuten.

* Ohne Argument zeigt jedes Skript genau seinen Kommentarkopf.

Ob eine Welt aufgestellt werden kann, prueft kein Unit-Test: Das rechnet
Minuten und ist die Probe dessen, der sie aufstellt.

Knoten: system/betrieb
"""

from __future__ import annotations

import hashlib
import json
import os
import re
import shutil
import stat
import subprocess
import sys
from pathlib import Path

import pytest

from rechner_pipeline.models.zeichnung import pruefe_ordnung
from tests.test_dokumentierte_kommandos import Kommando, pruefe

REPO = Path(__file__).resolve().parents[1]
WELT_SKRIPTE = REPO / "deploy" / "welt"
FALLDATEI = WELT_SKRIPTE / "fall-baldrian-klv-tg2015.conf"

ROLLEN = ("betrieb", "vorstand", "rechenkern", "architektur", "aktuariat", "betrieb-mensch")
#: Welche Rolle welches Gate in der erzeugten Ordnung traegt.
ORDNUNG_GATES = {
    "betrieb/tageslauf": [],
    "mensch/vorstand": ["A-Z1", "A-M6"],
    "mensch/rechenkern": ["A-K2"],
    "mensch/architektur": ["A-O1"],
    "mensch/aktuariat": ["A-Q1", "A-M1", "A-M2", "A-M3", "A-M4", "A-T1"],
    "mensch/betrieb": ["A-B1", "A-B2", "A-B3"],
}
SCHLUESSEL_DER_ROLLE = {
    "betrieb/tageslauf": "betrieb", "mensch/vorstand": "vorstand", "mensch/rechenkern": "rechenkern",
    "mensch/architektur": "architektur", "mensch/aktuariat": "aktuariat", "mensch/betrieb": "betrieb-mensch",
}
#: Der Ring je Gate des Falls: wessen Ketten das Gate liest, der zeichnende
#: Schluessel zuletzt (ADR-026).
RING = {
    "A-M6": ["vorstand"],
    "A-Q1": ["vorstand", "aktuariat"],
    "A-M1": ["vorstand", "aktuariat"],
    "A-M2": ["vorstand", "aktuariat"],
    "A-M3": ["vorstand", "aktuariat"],
    "A-T1": ["vorstand", "aktuariat"],
    "A-O1": ["vorstand", "architektur"],
    "A-K2": ["vorstand", "rechenkern"],
    "A-B1": ["vorstand", "betrieb-mensch"],
    "A-M4": ["vorstand", "rechenkern", "architektur", "aktuariat"],
    "A-B2": ["vorstand", "aktuariat", "betrieb-mensch"],
    "A-M5": ["vorstand", "programmleitung"],
}


def _git(wo: Path, *args: str) -> None:
    umgebung = dict(os.environ, GIT_AUTHOR_NAME="t", GIT_AUTHOR_EMAIL="t@t.invalid",
                    GIT_COMMITTER_NAME="t", GIT_COMMITTER_EMAIL="t@t.invalid",
                    GIT_CONFIG_GLOBAL=os.devnull, GIT_CONFIG_SYSTEM=os.devnull)
    subprocess.run(["git", "-C", str(wo), *args], capture_output=True, text=True, check=True, env=umgebung)


@pytest.fixture
def baum(tmp_path):
    """Ein sauberer Stellvertreter des Codebaums: Die Skripte verlangen einen
    sauberen Git-Baum mit dem Paketverzeichnis — der Baum des Repositorys ist
    waehrend der Entwicklung nicht sauber."""
    b = tmp_path / "baum"
    (b / "src" / "rechner_pipeline").mkdir(parents=True)
    (b / "src" / "rechner_pipeline" / "__init__.py").write_text("")
    (b / ".gitignore").write_text("faelle/\n")    # wie im Repository: Faelle sind nicht Teil des Baums
    (b / "lieferungen").mkdir()
    shutil.copytree(REPO / "lieferungen" / "baldrian-2", b / "lieferungen" / "baldrian-2")
    _git(b, "init", "--quiet", "--initial-branch=main")
    _git(b, "add", "-A")
    _git(b, "commit", "--quiet", "-m", "stand")
    return b


def _lauf(skript: str, *args: str, baum: Path, **umgebung: str) -> subprocess.CompletedProcess:
    env = dict(os.environ, BAUM=str(baum), PYTHON=sys.executable, HOME=str(baum.parent / "heim"),
               GIT_CONFIG_GLOBAL=os.devnull, GIT_CONFIG_SYSTEM=os.devnull)
    for name in ("SCHLUESSEL", "BIS", "VON", "MANDATGEBER", "ENTSCHEIDER"):
        env.pop(name, None)
    env.update(umgebung)
    return subprocess.run(["bash", str(WELT_SKRIPTE / skript), *args], capture_output=True, env=env)


@pytest.fixture
def welt(tmp_path, baum):
    """Eine Welt nach der Phase schluessel: Schluessel, Ordnung, Mandat,
    Einstellungen — ohne Ablage und Linie."""
    w = tmp_path / "welt"
    lauf = _lauf("welt_aufstellen.sh", str(w), "schluessel", baum=baum,
                 SCHLUESSEL=str(tmp_path / "schluessel"), MANDATGEBER="die Leitung der Probe")
    assert lauf.returncode == 0, lauf.stderr.decode() + lauf.stdout.decode()
    (tmp_path / "ausgabe").write_bytes(lauf.stdout + lauf.stderr)
    return w


def _einstellung(welt: Path, name: str) -> str:
    lauf = subprocess.run(["bash", "-c", f'. "$1"; printf %s "${{{name}}}"', "-", str(welt / "einstellungen.conf")],
                          capture_output=True, text=True, check=True)
    return lauf.stdout


# --------------------------------------------------------------------------- #
# welt_aufstellen.sh, Phase schluessel
# --------------------------------------------------------------------------- #

def test_je_rolle_ein_schluessel_den_niemand_sieht(tmp_path, welt):
    k = tmp_path / "schluessel"
    assert stat.S_IMODE(k.stat().st_mode) == 0o700
    dateien = sorted(p.name for p in k.glob("*.key"))
    assert dateien == sorted(f"{r}.key" for r in ROLLEN)
    ausgabe = (tmp_path / "ausgabe").read_bytes()
    inhalte = set()
    for name in dateien:
        datei = k / name
        roh = datei.read_bytes()
        assert len(roh) == 64
        assert stat.S_IMODE(datei.stat().st_mode) == 0o600
        assert datei.stat().st_nlink == 1
        # Weder der Schluessel noch sein Fingerabdruck stehen in der Ausgabe.
        assert roh not in ausgabe and roh.hex().encode() not in ausgabe
        assert hashlib.sha256(roh).hexdigest().encode() not in ausgabe
        inhalte.add(roh)
    assert len(inhalte) == len(ROLLEN)


def test_die_erzeugte_ordnung_besteht_die_regeln_des_systems_und_bindet_jede_rolle_an_ihren_schluessel(tmp_path, welt):
    k = tmp_path / "schluessel"
    ordnung = json.loads((k / "zeichnungsordnung.json").read_text(encoding="utf-8"))
    assert pruefe_ordnung(ordnung) == []
    assert {rolle: e["gates"] for rolle, e in ordnung["rollen"].items()} == ORDNUNG_GATES
    for rolle, eintrag in ordnung["rollen"].items():
        roh = (k / f"{SCHLUESSEL_DER_ROLLE[rolle]}.key").read_bytes()
        assert eintrag["schluessel_sha256"] == hashlib.sha256(roh).hexdigest(), rolle
        assert eintrag["schluesselklasse"] == ("betrieb" if rolle == "betrieb/tageslauf" else "simulation")
    # Die Programmleitung steht in keiner Ordnung (ADR-026).
    assert not any("programmleitung" in rolle for rolle in ordnung["rollen"])


def test_mandat_und_einstellungen_nennen_diese_welt(tmp_path, welt):
    mandat = welt / "mandate" / "mandat.txt"
    text = mandat.read_text(encoding="utf-8")
    assert stat.S_IMODE(mandat.stat().st_mode) == 0o444
    assert "@" not in text
    assert str(welt) in text and "die Leitung der Probe" in text
    k = tmp_path / "schluessel"
    assert _einstellung(welt, "ORDNUNG") == str(k / "zeichnungsordnung.json")
    assert _einstellung(welt, "VORSTAND_KEY") == str(k / "vorstand.key")
    assert _einstellung(welt, "MANDAT_FALL") == str(mandat)
    assert _einstellung(welt, "LINIE") == str(welt / "linie")
    # Der Schluessel der Programmleitung ist nur benannt; er entsteht mit dem Fallauftrag.
    assert _einstellung(welt, "PROGRAMMLEITUNG_KEY") == str(k / "programmleitung.key")
    assert not (k / "programmleitung.key").exists()
    # Die Stellungnahme, auf die die Einstellungen zeigen, ist die versionierte.
    assert Path(_einstellung(welt, "STELLUNGNAHME")) == WELT_SKRIPTE / "stellungnahme-tbox-020.json"


def test_ein_schluessel_wird_nie_ueberschrieben(tmp_path, baum, welt):
    k = tmp_path / "schluessel"
    vorher = {p.name: p.read_bytes() for p in k.iterdir()}
    # Dieselbe Welt noch einmal: Die Phase wird uebersprungen.
    lauf = _lauf("welt_aufstellen.sh", str(welt), "schluessel", baum=baum, SCHLUESSEL=str(k))
    assert lauf.returncode == 0 and b"uebersprungen" in lauf.stdout
    # Eine zweite Welt auf dasselbe Schluesselverzeichnis: verweigert.
    zweite = tmp_path / "zweite-welt"
    lauf = _lauf("welt_aufstellen.sh", str(zweite), "schluessel", baum=baum, SCHLUESSEL=str(k))
    assert lauf.returncode != 0 and b"traegt schon eine Zeichnungsordnung" in lauf.stdout
    assert not (zweite / "einstellungen.conf").exists()
    assert {p.name: p.read_bytes() for p in k.iterdir()} == vorher


@pytest.mark.parametrize("ort", ["welt", "baum"])
def test_schluessel_liegen_nie_in_welt_oder_codebaum(tmp_path, baum, ort):
    w = tmp_path / "welt"
    k = (w if ort == "welt" else baum) / "schluessel"
    lauf = _lauf("welt_aufstellen.sh", str(w), "schluessel", baum=baum, SCHLUESSEL=str(k))
    assert lauf.returncode != 0 and b"ausserhalb von Welt und Codebaum" in lauf.stdout
    assert not k.exists() and not (w / "einstellungen.conf").exists()


@pytest.mark.parametrize("name,wert", [
    ("ENTSCHEIDER", 'x"; touch gekapert; "'),
    ("MANDATGEBER", "$(touch gekapert)"),
    ("ENTSCHEIDER", "`touch gekapert`"),
    ("BIS", "2025-12-31\nZEILE=zwei"),
], ids=["anfuehrungszeichen", "kommandoersetzung", "rueckstrich", "zeilenumbruch"])
def test_ein_wert_der_in_den_einstellungen_code_wuerde_wird_verweigert_bevor_etwas_entsteht(tmp_path, baum, name, wert):
    w = tmp_path / "welt"
    k = tmp_path / "schluessel"
    lauf = _lauf("welt_aufstellen.sh", str(w), "schluessel", baum=baum, SCHLUESSEL=str(k), **{name: wert})
    assert lauf.returncode != 0 and f"HALT: {name}".encode() in lauf.stdout
    assert not k.exists() and not (w / "einstellungen.conf").exists()
    assert not list(tmp_path.rglob("gekapert"))


def test_eine_kopierte_welt_wird_von_keinem_skript_gefuehrt(tmp_path, welt, baum):
    # Die Einstellungen nennen ihre Welt. Wuerde ein Skript ihnen folgen statt
    # dem Aufruf, arbeitete es in der ALTEN Welt, waehrend der Mensch die neue meint.
    (welt / "linie" / "ordnung").mkdir(parents=True)
    shutil.copy(FALLDATEI, welt / "fall.conf")
    kopie = tmp_path / "kopie"
    shutil.copytree(welt, kopie)
    paket = _paket(tmp_path, 'schritt "Fall anlegen" mkdir -p faelle/probe\n')
    laeufe = {
        "welt_aufstellen.sh": _lauf("welt_aufstellen.sh", str(kopie), "linie", baum=baum),
        "fall_starten.sh": _lauf("fall_starten.sh", str(kopie), "vorlage", baum=baum),
        "fall_zeichnen.sh": _lauf("fall_zeichnen.sh", str(kopie), "ring", "A-M6", baum=baum),
        "fall_nachfahren.sh": _lauf("fall_nachfahren.sh", str(kopie), str(paket), baum=baum),
        "zugang.sh": _lauf("zugang.sh", str(kopie), "probe", baum=baum),
    }
    for skript, lauf in laeufe.items():
        assert lauf.returncode == 2 and b"gehoert zur Welt" in lauf.stdout, (skript, lauf.stdout)
    assert not (baum / "faelle").exists()


def test_ein_unsauberer_codebaum_haelt_an(tmp_path, baum):
    (baum / "neu.txt").write_text("nicht committet\n")
    lauf = _lauf("welt_aufstellen.sh", str(tmp_path / "welt"), "schluessel", baum=baum,
                 SCHLUESSEL=str(tmp_path / "schluessel"))
    assert lauf.returncode != 0 and b"nicht sauber" in lauf.stdout
    assert not (tmp_path / "schluessel").exists()


def test_die_welt_liegt_nie_im_codebaum(tmp_path, baum):
    lauf = _lauf("welt_aufstellen.sh", str(baum / "welt"), "schluessel", baum=baum,
                 SCHLUESSEL=str(tmp_path / "schluessel"))
    assert lauf.returncode != 0 and b"nicht im Codebaum" in lauf.stdout
    assert not (baum / "welt").exists()


# --------------------------------------------------------------------------- #
# fall_zeichnen.sh: der Ring je Gate
# --------------------------------------------------------------------------- #

@pytest.fixture
def welt_mit_fall(tmp_path, welt):
    shutil.copy(FALLDATEI, welt / "fall.conf")
    (tmp_path / "schluessel" / "programmleitung.key").write_bytes(b"p" * 64)
    return welt


def _ring(welt: Path, gate: str, baum: Path) -> list[str]:
    lauf = _lauf("fall_zeichnen.sh", str(welt), "ring", gate, baum=baum)
    assert lauf.returncode == 0, lauf.stdout.decode()
    return [Path(p).stem for p in re.findall(r"--freigabe-schluessel (\S+)", lauf.stdout.decode())]


@pytest.mark.parametrize("gate", sorted(RING))
def test_der_ring_je_gate(welt_mit_fall, baum, gate):
    assert _ring(welt_mit_fall, gate, baum) == RING[gate]
    ausgabe = _lauf("fall_zeichnen.sh", str(welt_mit_fall), "ring", gate, baum=baum).stdout.decode()
    for schalter in ("--linie ", "--zeichnungsordnung ", "--mandat "):
        assert schalter in ausgabe


def test_der_letzte_schluessel_im_ring_gehoert_der_rolle_die_das_gate_in_der_ordnung_traegt(tmp_path, welt_mit_fall, baum):
    ordnung = json.loads((tmp_path / "schluessel" / "zeichnungsordnung.json").read_text(encoding="utf-8"))
    gate_zu_rolle = {gate: rolle for rolle, e in ordnung["rollen"].items() for gate in e["gates"]}
    for gate in RING:
        zeichner = _ring(welt_mit_fall, gate, baum)[-1]
        if gate == "A-M5":      # die Programmleitung steht in keiner Ordnung
            assert zeichner == "programmleitung"
            continue
        assert zeichner == SCHLUESSEL_DER_ROLLE[gate_zu_rolle[gate]], gate
        # ... und jeder Ring beginnt mit dem Schluessel des Vorstands (Fallauftrag, Linie).
        assert _ring(welt_mit_fall, gate, baum)[0] == "vorstand"


def test_der_abbruch_liest_die_migrationsabnahme_sobald_eine_im_fall_liegt(welt_mit_fall, baum):
    entscheide = baum / "faelle" / "baldrian-klv-tg2015" / "entscheide"
    entscheide.mkdir(parents=True)
    assert _ring(welt_mit_fall, "A-M5", baum) == ["vorstand", "programmleitung"]
    (entscheide / ("A-M4-" + "a" * 64 + ".json")).write_text("{}")
    assert _ring(welt_mit_fall, "A-M5", baum) == ["vorstand", "aktuariat", "programmleitung"]


@pytest.mark.parametrize("gate", ["A-B3", "A-Z1", "A-X9"])
def test_ein_gate_das_nicht_im_fall_gezeichnet_wird_wird_verweigert(welt_mit_fall, baum, gate):
    lauf = _lauf("fall_zeichnen.sh", str(welt_mit_fall), "ring", gate, baum=baum)
    assert lauf.returncode == 2 and b"unbekanntes Gate" in lauf.stdout


# --------------------------------------------------------------------------- #
# fall_starten.sh und die Falldatei der Vorfuehrung
# --------------------------------------------------------------------------- #

def test_die_falldatei_nennt_den_lieferschein_und_seine_elf_dateien():
    lauf = subprocess.run(["bash", "-c", '. "$1"; printf "%s\\n" "$LIEFERUNG" $LIEFERDATEIEN', "-", str(FALLDATEI)],
                          capture_output=True, text=True, check=True)
    lieferung, *dateien = lauf.stdout.split()
    assert len(dateien) == 12 and len(set(dateien)) == 12 and "LIEFERSCHEIN.md" in dateien
    for name in dateien:
        assert (REPO / lieferung / name).is_file(), name
    # Auskunftsschreiben entstehen erst auf Rueckfrage und gehoeren nicht zur Lieferung.
    assert not any("auskunft" in name for name in dateien)


def _welt_mit_linie(welt: Path) -> Path:
    (welt / "linie" / "ordnung").mkdir(parents=True)
    return welt


def test_anlegen_haelt_bei_fehlender_lieferdatei_und_blockiert_keinen_zweiten_versuch(tmp_path, welt, baum):
    _welt_mit_linie(welt)
    (baum / "lieferungen" / "baldrian-2" / "LIEFERSCHEIN.md").unlink()
    _git(baum, "commit", "--quiet", "-am", "ohne Lieferschein")
    lauf = _lauf("fall_starten.sh", str(welt), "anlegen", str(FALLDATEI), baum=baum)
    assert lauf.returncode == 2 and b"LIEFERSCHEIN.md fehlt" in lauf.stdout
    assert not (welt / "fall.conf").exists()
    assert not (baum / "faelle").exists()


def test_die_falldatei_gilt_relativ_zum_verzeichnis_des_aufrufs(tmp_path, welt, baum):
    # Das Skript wechselt in den Codebaum; eine relativ genannte Falldatei darf
    # es danach nicht dort suchen. Gemessen wird am Halt HINTER dem Lesen der
    # Falldatei: Die Lieferung fehlt — also wurde die Datei gefunden und gelesen.
    _welt_mit_linie(welt)
    (baum / "lieferungen" / "baldrian-2" / "LIEFERSCHEIN.md").unlink()
    _git(baum, "commit", "--quiet", "-am", "ohne Lieferschein")
    ort = tmp_path / "anderswo"
    ort.mkdir()
    shutil.copy(FALLDATEI, ort / "fall.conf")
    env = dict(os.environ, BAUM=str(baum), PYTHON=sys.executable, GIT_CONFIG_GLOBAL=os.devnull,
               GIT_CONFIG_SYSTEM=os.devnull)
    lauf = subprocess.run(["bash", str(WELT_SKRIPTE / "fall_starten.sh"), str(welt), "anlegen", "fall.conf"],
                          capture_output=True, env=env, cwd=ort)
    assert lauf.returncode == 2 and b"LIEFERSCHEIN.md fehlt" in lauf.stdout, lauf.stdout


def test_eine_welt_fuehrt_einen_fall(tmp_path, welt, baum):
    _welt_mit_linie(welt)
    shutil.copy(FALLDATEI, welt / "fall.conf")
    lauf = _lauf("fall_starten.sh", str(welt), "anlegen", str(FALLDATEI), baum=baum)
    assert lauf.returncode == 2 and b"fuehrt schon einen Fall" in lauf.stdout


def test_ein_fallname_verlaesst_nie_das_fallverzeichnis(tmp_path, welt, baum):
    _welt_mit_linie(welt)
    boese = tmp_path / "boese.conf"
    boese.write_text(FALLDATEI.read_text(encoding="utf-8").replace(
        "FALLNAME=baldrian-klv-tg2015", "FALLNAME=../../draussen"), encoding="utf-8")
    lauf = _lauf("fall_starten.sh", str(welt), "anlegen", str(boese), baum=baum)
    assert lauf.returncode == 2 and b"FALLNAME" in lauf.stdout
    assert not (welt / "fall.conf").exists() and not (tmp_path / "draussen").exists()


def test_ohne_aufgestellte_welt_startet_kein_fall(tmp_path, welt, baum):
    # Schluessel und Einstellungen liegen, die Linie nicht.
    lauf = _lauf("fall_starten.sh", str(welt), "anlegen", str(FALLDATEI), baum=baum)
    assert lauf.returncode == 2 and b"Linie" in lauf.stdout
    assert not (welt / "fall.conf").exists()


SKRIPTE = tuple(sorted(s.name for s in WELT_SKRIPTE.glob("*.sh")))


def test_die_skripte_des_verzeichnisses_sind_die_bekannten():
    # Positivkontrolle der beiden Tests darunter: Sie laufen ueber das, was im
    # Verzeichnis liegt — ein leeres Muster liesse sie ohne einen Fall gruen.
    assert SKRIPTE == ("fall_nachfahren.sh", "fall_starten.sh", "fall_zeichnen.sh", "laufzeit_aufstellen.sh",
                       "paket_bauen.sh", "welt_aufstellen.sh", "zugang.sh")


@pytest.mark.parametrize("skript", SKRIPTE)
def test_shell_skripte_sind_syntaktisch_gueltig(skript):
    lauf = subprocess.run(["bash", "-n", str(WELT_SKRIPTE / skript)], capture_output=True, text=True)
    assert lauf.returncode == 0, lauf.stderr


@pytest.mark.parametrize("skript", SKRIPTE)
def test_ohne_argument_zeigt_jedes_skript_genau_seinen_kopf(skript, baum):
    """Die Hilfe ist der Kommentarkopf des Skripts — ganz, und ohne eine Zeile
    Code. Ein von Hand gezaehlter Zeilenbereich wandert nicht mit, wenn der
    Kopf waechst: Er schneidet dann die letzten Absaetze ab oder zeigt Code."""
    kopf = []
    for zeile in (WELT_SKRIPTE / skript).read_text(encoding="utf-8").splitlines()[1:]:
        if not zeile.startswith("#"):
            break
        kopf.append(re.sub(r"^# ?", "", zeile))
    assert len(kopf) > 5
    lauf = _lauf(skript, baum=baum)
    assert lauf.returncode == 2
    assert lauf.stdout.decode().splitlines() == kopf


# --------------------------------------------------------------------------- #
# zugang.sh: der abgenommene Bestand kommt in die Ablage
# --------------------------------------------------------------------------- #

#: Der Ring je Phase des Zugangs, der zeichnende Schluessel zuletzt — so
#: gefahren im Zugang des Falls vom 02.10.2026. Ein falscher Ring scheitert
#: sonst erst im Gate: bei der Probe nach einer Viertelstunde Rechnen.
ZUGANG_RING = {
    "probe": ["vorstand", "aktuariat"],
    "aufsetzen": ["vorstand", "aktuariat", "betrieb-mensch"],
    "ab3": ["vorstand", "betrieb-mensch"],
    "binden": ["vorstand", "betrieb-mensch"],
}


def _fall_des_zugangs(baum: Path, *gates: str) -> Path:
    entscheide = baum / "faelle" / "baldrian-klv-tg2015" / "entscheide"
    entscheide.mkdir(parents=True, exist_ok=True)
    for gate in gates:
        (entscheide / (f"{gate}-" + "a" * 64 + ".json")).write_text("{}")
    return entscheide.parent


def _zugang(welt: Path, baum: Path, *args: str, **umgebung: str) -> subprocess.CompletedProcess:
    lauf = _lauf("zugang.sh", str(welt), *args, baum=baum, **umgebung)
    lauf.text = (lauf.stdout + lauf.stderr).decode()  # type: ignore[attr-defined]
    return lauf


@pytest.fixture
def stellvertreter(tmp_path, baum):
    """Ein Interpreter, der nichts rechnet und jeden Aufruf mitschreibt: Die
    Systemkommandos des Zugangs rechnen Minuten; was das Skript selbst
    entscheidet, ist, WOMIT es sie ruft."""
    (baum / "configs").mkdir()
    (baum / "configs" / "bestand_gesamt.toml").write_text("# Config des Falls\n")
    _git(baum, "add", "-A")
    _git(baum, "commit", "--quiet", "-m", "config")
    spur = tmp_path / "aufrufe.txt"
    skript = tmp_path / "interpreter.sh"
    skript.write_text(f'#!/usr/bin/env bash\nprintf \'%s\\n\' "$*" >> "{spur}"\n')
    skript.chmod(0o755)
    return skript, spur


def test_der_zugang_beginnt_nicht_ohne_migrationsabnahme(welt_mit_fall, baum):
    lauf = _zugang(welt_mit_fall, baum, "probe")
    assert lauf.returncode == 2 and "keine Migrationsabnahme A-M4" in lauf.text, lauf.text
    assert not (welt_mit_fall / "zugangsprobe").exists() and not (welt_mit_fall / "zugang.log").exists()


def test_der_zugang_haelt_bevor_er_etwas_anfasst(tmp_path, welt_mit_fall, baum, stellvertreter):
    skript, spur = stellvertreter
    _fall_des_zugangs(baum, "A-M4")
    welt = welt_mit_fall
    # Eine Phase, die es nicht gibt; eine Abnahme ohne Begruendung.
    assert _zugang(welt, baum, "gibtsnicht", PYTHON=str(skript)).returncode == 2
    lauf = _zugang(welt, baum, "ab3", PYTHON=str(skript))
    assert lauf.returncode == 2 and "Begruendung fehlt" in lauf.text
    # Neu aufgesetzt wird erst nach der Zugangsabnahme.
    lauf = _zugang(welt, baum, "aufsetzen", PYTHON=str(skript))
    assert lauf.returncode == 1 and "keine Zugangsabnahme A-B2" in lauf.text
    # Eine Probe, die schon liegt, wird nicht ueberschrieben.
    (welt / "zugangsprobe").mkdir()
    (welt / "zugangsprobe" / "frueher").write_text("x")
    lauf = _zugang(welt, baum, "probe", PYTHON=str(skript))
    assert lauf.returncode == 1 and "liegt schon" in lauf.text
    assert [d.name for d in (welt / "zugangsprobe").iterdir()] == ["frueher"]
    # Ein unsauberer Codebaum: Probe und Aufbaulauf muessen auf demselben Stand rechnen.
    (baum / "neu.txt").write_text("nicht committet\n")
    lauf = _zugang(welt, baum, "belegen", PYTHON=str(skript))
    assert lauf.returncode == 2 and "nicht sauber" in lauf.text
    assert not spur.exists()            # kein Systemkommando wurde gerufen


def test_der_ring_je_phase_des_zugangs(tmp_path, welt_mit_fall, baum, stellvertreter):
    skript, spur = stellvertreter
    _fall_des_zugangs(baum, "A-M4", "A-B2")
    welt = welt_mit_fall
    ringe = {}
    for phase, argumente in (("probe", []), ("aufsetzen", []), ("aufbau", ["2026-03-15"]), ("belegen", []),
                             ("ab3", ["der Beleg traegt"]), ("binden", [])):
        vorher = len(spur.read_text().splitlines()) if spur.exists() else 0
        lauf = _zugang(welt, baum, phase, *argumente, PYTHON=str(skript))
        assert lauf.returncode == 0, (phase, lauf.text)
        aufrufe = spur.read_text().splitlines()[vorher:]
        ringe[phase] = [Path(k).stem for k in re.findall(r"--freigabe-schluessel (\S+)", aufrufe[0])]
        if phase == "aufbau":
            assert "--heute 2026-03-15" in aufrufe[0]
        if phase == "ab3":
            assert "--gate A-B3" in aufrufe[0] and "--begruendung der Beleg traegt" in aufrufe[0]
            assert f"--linie {welt / 'linie'}" in aufrufe[0] and "--fall" not in aufrufe[0]
        if phase == "binden":           # danach ein Tageslauf
            assert len(aufrufe) == 2 and "rechner_pipeline.betrieb.tageslauf" in aufrufe[1]
    assert {p: r for p, r in ringe.items() if r} == ZUGANG_RING
    assert ringe["aufbau"] == ringe["belegen"] == []       # der Betrieb rechnet, niemand zeichnet
    # Die Probe rechnet auf einem leeren Verzeichnis, das nur die Config des Falls traegt.
    assert (welt / "zugangsprobe" / "configs" / "bestand.toml").read_text() == "# Config des Falls\n"


# --------------------------------------------------------------------------- #
# fall_nachfahren.sh: ein Paket Schritt fuer Schritt
# --------------------------------------------------------------------------- #

def _paket(wo: Path, rezept: str, *, erarbeitet: dict | None = None, erwartung: dict | None = None,
           fallname: str = "probe", stand: str | None = None) -> Path:
    """Ein Paket mit gueltigen Pruefsummen. Das Rezept der Tests nutzt nur
    Shell-Kommandos: Was die Systemkommandos tun, ist nicht Sache des Skripts."""
    p = wo / f"paket-{fallname}"
    p.mkdir()
    (p / "fall.conf").write_text(f'FALLNAME={fallname}\nSTICHTAG=2026-01-01\n')
    (p / "rezept.sh").write_text(rezept)
    for rel, inhalt in (erarbeitet or {}).items():
        ziel = p / "erarbeitet" / rel
        ziel.parent.mkdir(parents=True, exist_ok=True)
        ziel.write_text(inhalt)
    (p / "ERWARTUNG").write_text("".join(
        f"{hashlib.sha256(inhalt.encode()).hexdigest()}  {rel}\n" for rel, inhalt in (erwartung or {}).items()))
    if stand is not None:
        (p / "STAND").write_text(f"VOR={stand}\n")
    _summen(p)
    return p


def _summen(p: Path) -> None:
    dateien = sorted(d for d in p.rglob("*") if d.is_file() and d.name != "SHA256SUMS")
    (p / "SHA256SUMS").write_text("".join(
        f"{hashlib.sha256(d.read_bytes()).hexdigest()}  {d.relative_to(p)}\n" for d in dateien))


def _nachfahren(welt: Path, paket: Path, baum: Path, *args: str) -> subprocess.CompletedProcess:
    lauf = _lauf("fall_nachfahren.sh", str(welt), str(paket), *args, baum=baum)
    lauf.text = (lauf.stdout + lauf.stderr).decode()  # type: ignore[attr-defined]
    return lauf


REZEPT = """# Probe
schritt "Fall anlegen" mkdir -p faelle/probe/abgeleitet
schritt "eins" bash -c 'echo eins >> faelle/probe/spur'
einlegen abgeleitet/abox/abox.json
haltepunkt mitte
schritt "zwei, ueber zwei Zeilen" bash -c \\
    'echo zwei >> faelle/probe/spur'
schritt "Ergebnis" bash -c 'printf ergebnis > faelle/probe/abgeleitet/bericht.txt'
erwarte abgeleitet/bericht.txt
haltepunkt ende
"""


def test_nachfahren_faehrt_das_rezept_in_reihenfolge_bis_zum_ende(tmp_path, welt, baum):
    paket = _paket(tmp_path, REZEPT, erarbeitet={"abgeleitet/abox/abox.json": "{}"},
                   erwartung={"abgeleitet/bericht.txt": "ergebnis"})
    lauf = _nachfahren(welt, paket, baum)
    assert lauf.returncode == 0, lauf.text
    fall = baum / "faelle" / "probe"
    assert (fall / "spur").read_text() == "eins\nzwei\n"
    assert (fall / "abgeleitet" / "abox" / "abox.json").read_text() == "{}"
    assert "NACHGEFAHREN: probe, 8 Schritte" in lauf.text and "erwarte abgeleitet/bericht.txt (byte-gleich)" in lauf.text


def test_ein_haltepunkt_endet_den_lauf_und_der_naechste_faehrt_nichts_doppelt(tmp_path, welt, baum):
    paket = _paket(tmp_path, REZEPT, erarbeitet={"abgeleitet/abox/abox.json": "{}"},
                   erwartung={"abgeleitet/bericht.txt": "ergebnis"})
    fall = baum / "faelle" / "probe"
    erster = _nachfahren(welt, paket, baum, "--bis", "mitte")
    assert erster.returncode == 0 and "Haltepunkt mitte erreicht" in erster.text, erster.text
    assert (fall / "spur").read_text() == "eins\n"
    assert not (fall / "abgeleitet" / "bericht.txt").exists()
    zweiter = _nachfahren(welt, paket, baum)
    assert zweiter.returncode == 0, zweiter.text
    # "eins" lief genau einmal: Der zweite Lauf setzt hinter dem Haltepunkt an.
    assert (fall / "spur").read_text() == "eins\nzwei\n"
    assert zweiter.text.count("(schon gefahren)") == 4
    # Ein Haltepunkt, der schon hinter dem Lauf liegt, wird benannt verweigert.
    dritter = _nachfahren(welt, paket, baum, "--bis", "mitte")
    assert dritter.returncode == 2 and "liegt schon hinter diesem Lauf" in dritter.text


def test_einen_haltepunkt_den_das_rezept_nicht_kennt_gibt_es_nicht(tmp_path, welt, baum):
    paket = _paket(tmp_path, REZEPT, erarbeitet={"abgeleitet/abox/abox.json": "{}"},
                   erwartung={"abgeleitet/bericht.txt": "ergebnis"})
    lauf = _nachfahren(welt, paket, baum, "--bis", "gibtsnicht")
    assert lauf.returncode == 2 and "gibt es im Rezept nicht" in lauf.text and "mitte" in lauf.text
    assert not (baum / "faelle").exists()


def test_nach_einem_fehler_faehrt_derselbe_aufruf_beim_gescheiterten_schritt_weiter(tmp_path, welt, baum):
    rezept = ('schritt "Fall anlegen" mkdir -p faelle/probe\n'
              "schritt \"eins\" bash -c 'echo eins >> faelle/probe/spur'\n"
              'schritt "braucht eine Datei" test -f faelle/probe/behoben\n'
              "schritt \"drei\" bash -c 'echo drei >> faelle/probe/spur'\n")
    paket = _paket(tmp_path, rezept)
    erster = _nachfahren(welt, paket, baum)
    assert erster.returncode == 1 and "HALT   3  braucht eine Datei (Exit 1)" in erster.text, erster.text
    assert (baum / "faelle" / "probe" / "spur").read_text() == "eins\n"
    (baum / "faelle" / "probe" / "behoben").write_text("")
    zweiter = _nachfahren(welt, paket, baum)
    assert zweiter.returncode == 0, zweiter.text
    assert (baum / "faelle" / "probe" / "spur").read_text() == "eins\ndrei\n"


def test_einlegen_legt_nie_ueber_eine_andere_datei(tmp_path, welt, baum):
    rezept = ('schritt "Fall anlegen" mkdir -p faelle/probe/abgeleitet/abox\n'
              "schritt \"fremde Datei\" bash -c 'printf anders > faelle/probe/abgeleitet/abox/abox.json'\n"
              "einlegen abgeleitet/abox\n")
    paket = _paket(tmp_path, rezept, erarbeitet={"abgeleitet/abox/abox.json": "aus dem Paket",
                                                 "abgeleitet/abox/fragmente/a.json": "a"})
    lauf = _nachfahren(welt, paket, baum)
    assert lauf.returncode == 1 and "im Fall liegt schon eine andere Datei" in lauf.text, lauf.text
    assert (baum / "faelle" / "probe" / "abgeleitet" / "abox" / "abox.json").read_text() == "anders"
    # Dieselbe Datei noch einmal einzulegen ist kein Fehler (Fortsetzung nach einem Abbruch).
    (baum / "faelle" / "probe" / "abgeleitet" / "abox" / "abox.json").write_text("aus dem Paket")
    lauf = _nachfahren(welt, paket, baum)
    assert lauf.returncode == 0, lauf.text
    assert (baum / "faelle" / "probe" / "abgeleitet" / "abox" / "fragmente" / "a.json").read_text() == "a"


@pytest.mark.parametrize("fall", ["andere_bytes", "nicht_entstanden", "ohne_erwartung"])
def test_erwarte_haelt_an_wenn_das_ergebnis_nicht_das_festgehaltene_ist(tmp_path, welt, baum, fall):
    schreibt = {"andere_bytes": "printf anders", "nicht_entstanden": "true", "ohne_erwartung": "printf ergebnis"}[fall]
    rezept = ('schritt "Fall anlegen" mkdir -p faelle/probe/abgeleitet\n'
              f"schritt \"Ergebnis\" bash -c '{schreibt} > faelle/probe/abgeleitet/"
              f"{'anderswo' if fall == 'nicht_entstanden' else 'bericht'}.txt'\n"
              "erwarte abgeleitet/bericht.txt\n"
              "schritt \"danach\" bash -c 'echo danach >> faelle/probe/spur'\n")
    erwartung = {} if fall == "ohne_erwartung" else {"abgeleitet/bericht.txt": "ergebnis"}
    paket = _paket(tmp_path, rezept, erwartung=erwartung)
    lauf = _nachfahren(welt, paket, baum)
    assert lauf.returncode == 1, lauf.text
    assert {"andere_bytes": "andere Bytes als im festgehaltenen Fall", "nicht_entstanden": "ist nicht entstanden",
            "ohne_erwartung": "steht nichts in ERWARTUNG"}[fall] in lauf.text
    assert not (baum / "faelle" / "probe" / "spur").exists()


@pytest.mark.parametrize("eingriff", ["veraendert", "dazugelegt"])
def test_ein_paket_das_nicht_seinen_pruefsummen_entspricht_wird_nicht_gefahren(tmp_path, welt, baum, eingriff):
    paket = _paket(tmp_path, 'schritt "Fall anlegen" mkdir -p faelle/probe\n',
                   erarbeitet={"abgeleitet/abox/abox.json": "{}"})
    if eingriff == "veraendert":
        (paket / "erarbeitet" / "abgeleitet" / "abox" / "abox.json").write_text('{"x": 1}')
    else:
        (paket / "erarbeitet" / "abgeleitet" / "abox" / "untergeschoben.json").write_text("{}")
    lauf = _nachfahren(welt, paket, baum)
    assert lauf.returncode == 2, lauf.text
    assert ("stimmt nicht mit seinen Pruefsummen" if eingriff == "veraendert" else "ohne Pruefsumme") in lauf.text
    assert not (baum / "faelle").exists() and not (welt / "nachfahren.stand").exists()


@pytest.mark.parametrize("zeile", ["rm -rf faelle", "PY=/bin/false", "echo hallo; schritt \"x\" true"])
def test_im_rezept_stehen_nur_helfer(tmp_path, welt, baum, zeile):
    paket = _paket(tmp_path, f'schritt "Fall anlegen" mkdir -p faelle/probe\n{zeile}\n')
    lauf = _nachfahren(welt, paket, baum)
    assert lauf.returncode == 2 and "kein Helfer" in lauf.text, lauf.text
    assert not (baum / "faelle").exists()


def _annahme(linie: Path, gate: str, kennung: str, entschieden_am: str, commit: str, entscheid: str = "angenommen",
             pflichtbelege: dict | None = None) -> None:
    """Ein Snapshot, wie ihn ein Gate schreibt — in einer Linie oder einem Fall."""
    (linie / "entscheide").mkdir(parents=True, exist_ok=True)
    (linie / "entscheide" / f"{gate}-{kennung * 64}.json").write_text(json.dumps(
        {"gate": gate, "entscheid": entscheid, "entschieden_am": entschieden_am, "system": {"commit": commit},
         "pflichtbelege": pflichtbelege or {}}))


@pytest.mark.parametrize("erste,juengste", [("a", "b"), ("b", "a")])
def test_abgenommen_nennt_den_commit_der_juengsten_annahme_des_gates_in_der_linie(tmp_path, welt, baum, erste, juengste):
    # Ein Beleg zeigt die Aenderung gegen den abgenommenen Stand (--von). Das
    # Rezept nennt dafuer keinen Commit der Welt, in der es festgehalten wurde,
    # sondern fragt die Linie der Welt, in der es nachgefahren wird. Die
    # juengste Annahme ist die nach der Zeit — mit beiden Namensverteilungen
    # faellt jede Wahl nach der Reihenfolge des Verzeichnisses in einer davon.
    linie = _welt_mit_linie(welt) / "linie"
    _annahme(linie, "A-K2", erste, "2026-10-01T10:00:00+00:00", "erste")
    _annahme(linie, "A-K2", juengste, "2026-10-02T10:00:00+00:00", "juengste")
    _annahme(linie, "A-K2", "c", "2026-10-03T10:00:00+00:00", "abgelehnte", entscheid="abgelehnt")
    _annahme(linie, "A-T1", "d", "2026-10-04T10:00:00+00:00", "anderes-gate")
    rezept = ('schritt "Fall anlegen" mkdir -p faelle/probe\n'
              'schritt "von" bash -c \'printf %s "$1" > faelle/probe/von\' - "$(abgenommen A-K2)"\n')
    lauf = _nachfahren(welt, _paket(tmp_path, rezept), baum)
    assert lauf.returncode == 0, lauf.text
    assert (baum / "faelle" / "probe" / "von").read_text() == "juengste"


def test_abgenommen_ohne_annahme_in_der_linie_wird_benannt_und_der_schritt_haelt(tmp_path, welt, baum):
    linie = _welt_mit_linie(welt) / "linie"
    _annahme(linie, "A-K2", "c", "2026-10-03T10:00:00+00:00", "abgelehnte", entscheid="abgelehnt")
    rezept = ('schritt "Fall anlegen" mkdir -p faelle/probe\n'
              'schritt "braucht den Stand" test -n "$(abgenommen A-K2)"\n'
              "schritt \"danach\" bash -c 'echo danach >> faelle/probe/spur'\n")
    lauf = _nachfahren(welt, _paket(tmp_path, rezept), baum)
    assert lauf.returncode == 1, lauf.text
    assert "in der Linie liegt keine Annahme von A-K2" in lauf.text
    assert not (baum / "faelle" / "probe" / "spur").exists()


def test_der_zugang_im_rezept_ist_je_phase_ein_schritt_und_haelt_wenn_die_phase_haelt(tmp_path, welt, baum, stellvertreter):
    skript, spur = stellvertreter
    (tmp_path / "schluessel" / "programmleitung.key").write_bytes(b"p" * 64)
    (welt / "fall.conf").write_text("FALLNAME=probe\nSTICHTAG=2026-01-01\n")
    rezept = ('schritt "Fall anlegen" mkdir -p faelle/probe/entscheide\n'
              'zugang belegen\n'
              'zugang aufbau 2026-03-15\n'
              "schritt \"danach\" bash -c 'echo danach >> faelle/probe/spur'\n")
    paket = _paket(tmp_path, rezept)
    # Ohne Migrationsabnahme haelt die Phase — und mit ihr das Rezept, an diesem Schritt.
    erster = _lauf("fall_nachfahren.sh", str(welt), str(paket), baum=baum, PYTHON=str(skript))
    text = (erster.stdout + erster.stderr).decode()
    assert erster.returncode == 1 and "HALT   2  Zugang: belegen" in text and "keine Migrationsabnahme A-M4" in text, text
    assert not (baum / "faelle" / "probe" / "spur").exists()
    # Behoben: Derselbe Aufruf faehrt die Phase und danach weiter.
    (baum / "faelle" / "probe" / "entscheide" / ("A-M4-" + "a" * 64 + ".json")).write_text("{}")
    zweiter = _lauf("fall_nachfahren.sh", str(welt), str(paket), baum=baum, PYTHON=str(skript))
    text = (zweiter.stdout + zweiter.stderr).decode()
    assert zweiter.returncode == 0 and "ok     2  Zugang: belegen" in text, text
    belegen, aufbau = spur.read_text().splitlines()
    assert "rechner_pipeline.betrieb.anfangsbestand belegen" in belegen
    # Das Argument der Phase kommt an: Der Aufbaulauf fuehrt bis zum Tag des
    # Rezepts, nicht bis zum Tag, an dem nachgefahren wird (ohne Argument
    # naehme die Phase den heutigen — der Tag im Rezept ist deshalb keiner,
    # an dem dieser Test je laeuft).
    assert "rechner_pipeline.betrieb.tageslauf" in aufbau and "--heute 2026-03-15" in aufbau
    assert "ok     3  Zugang: aufbau" in text
    assert (baum / "faelle" / "probe" / "spur").read_text() == "danach\n"


@pytest.fixture
def halbsystem(tmp_path, welt):
    """Ein Interpreter, der die Skripte der Welt wirklich faehrt (abgenommen.py,
    gezeichnet.py) und jedes Systemkommando nur mitschreibt — und eine Welt,
    in der fall_zeichnen.sh bis zum Gate kommt."""
    spur = tmp_path / "systemaufrufe.txt"
    skript = tmp_path / "halbsystem.sh"
    skript.write_text(f"""#!/usr/bin/env bash
if [ "$1" = -m ]; then printf '%s\\n' "$*" >> "{spur}"; else exec "{sys.executable}" "$@"; fi
""")
    skript.chmod(0o755)
    (welt / "fall.conf").write_text("FALLNAME=probe\nSTICHTAG=2026-01-01\n")
    (tmp_path / "schluessel" / "programmleitung.key").write_bytes(b"p" * 64)
    return skript, spur


def _gezeichnet(spur: Path, gate: str) -> int:
    """Wie oft das Rezept das Gate gezeichnet hat (Aufrufe des Gates)."""
    if not spur.exists():
        return 0
    return sum(1 for z in spur.read_text().splitlines() if "gates.gate_entscheid" in z and f"--gate {gate} " in z)


REZEPT_ZEICHNEN = ('schritt "Fall anlegen" mkdir -p faelle/probe/entscheide\n'
                   'haltepunkt vor-A-M4\n'
                   'zeichne A-M4 "das Urteil des festgehaltenen Falls"\n'
                   "schritt \"danach\" bash -c 'echo danach >> faelle/probe/spur'\n")


def test_das_rezept_zeichnet_was_kein_mensch_gezeichnet_hat(tmp_path, welt, baum, halbsystem):
    skript, spur = halbsystem
    lauf = _lauf("fall_nachfahren.sh", str(welt), str(_paket(tmp_path, REZEPT_ZEICHNEN)), baum=baum, PYTHON=str(skript))
    text = (lauf.stdout + lauf.stderr).decode()
    assert lauf.returncode == 0 and "ok     3  A-M4 zeichnen" in text, text
    assert _gezeichnet(spur, "A-M4") == 1
    aufruf = spur.read_text().splitlines()[0]
    assert "--entscheid angenommen" in aufruf and "--begruendung das Urteil des festgehaltenen Falls" in aufruf


def test_wer_am_haltepunkt_selbst_zeichnet_dessen_zeichnung_gilt(tmp_path, welt, baum, halbsystem):
    skript, spur = halbsystem
    paket = _paket(tmp_path, REZEPT_ZEICHNEN)
    erster = _lauf("fall_nachfahren.sh", str(welt), str(paket), "--bis", "vor-A-M4", baum=baum, PYTHON=str(skript))
    assert erster.returncode == 0, erster.stdout.decode()
    # Der Mensch liest die Vorlage und zeichnet selbst.
    _annahme(baum / "faelle" / "probe", "A-M4", "a", "2026-10-06T10:00:00+00:00", "x" * 40)
    zweiter = _lauf("fall_nachfahren.sh", str(welt), str(paket), baum=baum, PYTHON=str(skript))
    text = (zweiter.stdout + zweiter.stderr).decode()
    assert zweiter.returncode == 0, text
    assert "A-M4 zeichnen (liegt schon: von Hand gezeichnet)" in text
    assert _gezeichnet(spur, "A-M4") == 0                   # das Rezept hat NICHT noch einmal gezeichnet
    assert (baum / "faelle" / "probe" / "spur").read_text() == "danach\n"


def test_ueber_eine_ablehnung_zeichnet_das_rezept_nie_hinweg(tmp_path, welt, baum, halbsystem):
    skript, spur = halbsystem
    paket = _paket(tmp_path, REZEPT_ZEICHNEN)
    _lauf("fall_nachfahren.sh", str(welt), str(paket), "--bis", "vor-A-M4", baum=baum, PYTHON=str(skript))
    _annahme(baum / "faelle" / "probe", "A-M4", "a", "2026-10-06T10:00:00+00:00", "x" * 40, entscheid="abgelehnt")
    for _ in range(2):                                      # auch der zweite Versuch haelt
        lauf = _lauf("fall_nachfahren.sh", str(welt), str(paket), baum=baum, PYTHON=str(skript))
        text = (lauf.stdout + lauf.stderr).decode()
        assert lauf.returncode == 1 and "Ablehnung" in text and "HALT   3  A-M4 zeichnen" in text, text
    assert _gezeichnet(spur, "A-M4") == 0
    assert not (baum / "faelle" / "probe" / "spur").exists()
    # Zeichnet der Mensch danach doch an, gilt DAS — die Ablehnung liegt dann hinter einer Annahme.
    _annahme(baum / "faelle" / "probe", "A-M4", "b", "2026-10-06T11:00:00+00:00", "x" * 40)
    lauf = _lauf("fall_nachfahren.sh", str(welt), str(paket), baum=baum, PYTHON=str(skript))
    assert lauf.returncode == 0 and _gezeichnet(spur, "A-M4") == 0


def test_die_k_te_zeichnung_des_rezepts_gilt_als_geleistet_wenn_k_annahmen_liegen(tmp_path, welt, baum, halbsystem):
    # Der Auftrag wird nach jeder Nachlieferung neu gezeichnet: Eine Annahme
    # von Hand ersetzt genau EINE Zeichnung des Rezepts, nicht alle — auch wenn
    # der Lauf dazwischen an einem Haltepunkt endete.
    skript, spur = halbsystem
    rezept = ('schritt "Fall anlegen" mkdir -p faelle/probe/entscheide\n'
              'haltepunkt auftrag\n'
              'zeichne A-M6 "erster Auftrag"\n'
              'haltepunkt nachlieferung\n'
              'zeichne A-M6 "Neubeauftragung"\n')
    paket = _paket(tmp_path, rezept)
    _lauf("fall_nachfahren.sh", str(welt), str(paket), "--bis", "auftrag", baum=baum, PYTHON=str(skript))
    _annahme(baum / "faelle" / "probe", "A-M6", "a", "2026-10-06T10:00:00+00:00", "x" * 40)
    mitte = _lauf("fall_nachfahren.sh", str(welt), str(paket), "--bis", "nachlieferung", baum=baum, PYTHON=str(skript))
    assert mitte.returncode == 0 and b"von Hand gezeichnet" in mitte.stdout and _gezeichnet(spur, "A-M6") == 0
    ende = _lauf("fall_nachfahren.sh", str(welt), str(paket), baum=baum, PYTHON=str(skript))
    text = (ende.stdout + ende.stderr).decode()
    assert ende.returncode == 0 and "ok     5  A-M6 zeichnen" in text, text
    assert _gezeichnet(spur, "A-M6") == 1
    assert "--begruendung Neubeauftragung" in spur.read_text()


@pytest.mark.parametrize("ablehnung,annahme", [("a", "b"), ("b", "a")])
def test_die_juengste_zeichnung_entscheidet_nach_der_zeit(tmp_path, welt, baum, halbsystem, ablehnung, annahme):
    # Erst angenommen, spaeter abgelehnt: Fuer die ZWEITE Zeichnung des Rezepts
    # liegt eine Annahme zu wenig, und die juengste Zeichnung ist die
    # Ablehnung — Halt. "Juengste" heisst nach der Zeit der Zeichnung, nicht
    # nach der Reihenfolge, in der das Verzeichnis seine Dateien nennt: Mit
    # beiden Namensverteilungen faellt jede Wahl nach Position in einer davon.
    skript, spur = halbsystem
    rezept = ('schritt "Fall anlegen" mkdir -p faelle/probe/entscheide\n'
              'zeichne A-M6 "erster Auftrag"\n'
              'zeichne A-M6 "Neubeauftragung"\n')
    fall = baum / "faelle" / "probe"
    _annahme(fall, "A-M6", ablehnung, "2026-10-06T11:00:00+00:00", "x" * 40, entscheid="abgelehnt")
    _annahme(fall, "A-M6", annahme, "2026-10-06T10:00:00+00:00", "x" * 40)
    lauf = _lauf("fall_nachfahren.sh", str(welt), str(_paket(tmp_path, rezept)), baum=baum, PYTHON=str(skript))
    text = (lauf.stdout + lauf.stderr).decode()
    assert lauf.returncode == 1 and "HALT   3  A-M6 zeichnen" in text and "Ablehnung" in text, text
    assert "A-M6 zeichnen (liegt schon: von Hand gezeichnet)" in text       # die erste war geleistet
    assert _gezeichnet(spur, "A-M6") == 0


@pytest.mark.parametrize("lage", ["nur_erstabnahme", "von_hand", "abgelehnt"])
def test_der_anfangsbestand_gilt_als_gezeichnet_wenn_eine_annahme_genau_diesen_beleg_pinnt(tmp_path, welt, baum, halbsystem, lage):
    # Die Linie traegt schon eine A-B3 (die Erstabnahme der Welt): Zaehlen
    # hilft hier nicht. Gezeichnet ist der Anfangsbestand, wenn eine Annahme
    # den Beleg pinnt, der jetzt in der Linie liegt.
    skript, spur = halbsystem
    linie = welt / "linie"
    (linie / "abgeleitet" / "anfangsbestand").mkdir(parents=True)
    beleg = linie / "abgeleitet" / "anfangsbestand" / "beleg.json"
    beleg.write_text('{"stand": "nach dem Zugang"}')
    _annahme(linie, "A-B3", "a", "2026-10-01T10:00:00+00:00", "x" * 40, pflichtbelege={"anfangsbestand": ["0" * 64]})
    summe = hashlib.sha256(beleg.read_bytes()).hexdigest()
    if lage == "von_hand":
        _annahme(linie, "A-B3", "b", "2026-10-06T10:00:00+00:00", "x" * 40, pflichtbelege={"anfangsbestand": [summe]})
    if lage == "abgelehnt":
        _annahme(linie, "A-B3", "b", "2026-10-06T10:00:00+00:00", "x" * 40, entscheid="abgelehnt",
                 pflichtbelege={"anfangsbestand": [summe]})
    (baum / "configs").mkdir()
    (baum / "configs" / "bestand_gesamt.toml").write_text("# Config\n")
    _git(baum, "add", "-A")
    _git(baum, "commit", "--quiet", "-m", "config")
    rezept = ('schritt "Fall anlegen" mkdir -p faelle/probe/entscheide\n'
              "schritt \"abgenommen\" bash -c 'echo {} > faelle/probe/entscheide/A-M4-" + "a" * 64 + ".json'\n"
              'zugang ab3 "das Urteil des festgehaltenen Falls"\n')
    lauf = _lauf("fall_nachfahren.sh", str(welt), str(_paket(tmp_path, rezept)), baum=baum, PYTHON=str(skript))
    text = (lauf.stdout + lauf.stderr).decode()
    if lage == "nur_erstabnahme":
        assert lauf.returncode == 0 and "ok     3  Zugang: ab3" in text and _gezeichnet(spur, "A-B3") == 1, text
    elif lage == "von_hand":
        assert lauf.returncode == 0 and "Zugang: ab3 (liegt schon: von Hand gezeichnet)" in text, text
        assert _gezeichnet(spur, "A-B3") == 0
    else:
        assert lauf.returncode == 1 and "Ablehnung" in text and _gezeichnet(spur, "A-B3") == 0, text


def test_eine_welt_faehrt_ein_paket_nach_und_wechselt_den_fall_nur_auf_wunsch(tmp_path, welt, baum):
    # Die Welt fuehrt schon einen anderen Fall: Halt, bis --wechseln es erlaubt.
    (welt / "fall.conf").write_text("FALLNAME=live\n")
    paket = _paket(tmp_path, 'schritt "Fall anlegen" mkdir -p faelle/probe\nhaltepunkt eins\n'
                             "schritt \"zwei\" bash -c 'echo zwei >> faelle/probe/spur'\n")
    lauf = _nachfahren(welt, paket, baum)
    assert lauf.returncode == 2 and "fuehrt den Fall live" in lauf.text and "--wechseln" in lauf.text
    assert (welt / "fall.conf").read_text() == "FALLNAME=live\n" and not (baum / "faelle").exists()
    lauf = _nachfahren(welt, paket, baum, "--wechseln", "--bis", "eins")
    assert lauf.returncode == 0, lauf.text
    assert (welt / "fall-frueher-live.conf").read_text() == "FALLNAME=live\n"
    # Ein anderes Paket in derselben Welt: verweigert, der Stand gehoert dem ersten.
    anderes = _paket(tmp_path, 'schritt "Fall anlegen" mkdir -p faelle/zweiter\n', fallname="zweiter")
    lauf = _nachfahren(welt, anderes, baum, "--wechseln")
    assert lauf.returncode == 2 and "gehoert zu einem anderen Paket oder Fall" in lauf.text
    assert not (baum / "faelle" / "zweiter").exists()


# --------------------------------------------------------------------------- #
# paket_bauen.sh: aus einem gefuehrten Fall ein Paket
# --------------------------------------------------------------------------- #

REZEPT_PAKET = """schritt "Fall anlegen" mkdir -p faelle/gefuehrt/abgeleitet/berichte
einlegen abgeleitet/abox
einlegen abgeleitet/transformation/abzug.spec.json
schritt "Ergebnis" bash -c 'printf ergebnis > faelle/gefuehrt/abgeleitet/berichte/bericht.html'
erwarte abgeleitet/berichte/bericht.html
"""


@pytest.fixture
def gefuehrt(tmp_path, welt, baum):
    """Ein Fall, wie er nach einem Lauf liegt: Lieferung und eine Nachlieferung
    im Eingang, Erarbeitetes, ein Ergebnis und eine Zeichnung."""
    fall = baum / "faelle" / "gefuehrt"
    for rel, inhalt in {
        "eingang/LIEFERSCHEIN.md": "Lieferschein", "eingang/abzug.csv": "POLNR;X",
        "eingang/auskunft-1.md": "Auskunft der Quelle",
        "abgeleitet/abox/abox.json": "{}", "abgeleitet/abox/fragmente/a.json": "a",
        "abgeleitet/transformation/abzug.spec.json": "spec",
        "abgeleitet/berichte/bericht.html": "ergebnis",
        "abgeleitet/diagnostics/x.gate.json": "beleg mit zeit",
        "entscheide/A-M6-" + "a" * 64 + ".json": "zeichnung",
    }.items():
        (fall / rel).parent.mkdir(parents=True, exist_ok=True)
        (fall / rel).write_text(inhalt)
    (welt / "fall.conf").write_text('FALLNAME=gefuehrt\nLIEFERUNG=lieferungen/x\n'
                                    'LIEFERDATEIEN="LIEFERSCHEIN.md abzug.csv"\nSTICHTAG=2026-01-01\n')
    (tmp_path / "rezept.sh").write_text(REZEPT_PAKET)
    (tmp_path / "erarbeitet.txt").write_text("# was erarbeitet wurde\nabgeleitet/abox\n\nabgeleitet/transformation/abzug.spec.json\n")
    (tmp_path / "erwartung.txt").write_text("abgeleitet/berichte/bericht.html\n")
    return fall


def _bauen(welt, ziel, tmp_path, baum, **listen) -> subprocess.CompletedProcess:
    args = [str(welt), str(ziel), "--rezept", str(listen.get("rezept", tmp_path / "rezept.sh"))]
    for schalter in ("erarbeitet", "erwartung"):
        wert = listen.get(schalter, tmp_path / f"{schalter}.txt")
        if wert is not None:
            args += [f"--{schalter}", str(wert)]
    lauf = _lauf("paket_bauen.sh", *args, baum=baum)
    lauf.text = (lauf.stdout + lauf.stderr).decode()  # type: ignore[attr-defined]
    return lauf


def test_das_paket_traegt_erarbeitetes_nachlieferung_und_erwartung_aber_keine_zeichnung(tmp_path, welt, baum, gefuehrt):
    ziel = tmp_path / "paket"
    lauf = _bauen(welt, ziel, tmp_path, baum)
    assert lauf.returncode == 0, lauf.text
    dateien = sorted(str(p.relative_to(ziel)) for p in ziel.rglob("*") if p.is_file())
    assert dateien == ["ERWARTUNG", "SHA256SUMS", "erarbeitet/abgeleitet/abox/abox.json",
                       "erarbeitet/abgeleitet/abox/fragmente/a.json",
                       "erarbeitet/abgeleitet/transformation/abzug.spec.json", "fall.conf",
                       "nachlieferung/auskunft-1.md", "rezept.sh"]
    assert (ziel / "ERWARTUNG").read_text() == hashlib.sha256(b"ergebnis").hexdigest() + "  abgeleitet/berichte/bericht.html\n"
    summen = dict(reversed(z.split("  ", 1)) for z in (ziel / "SHA256SUMS").read_text().splitlines())
    assert sorted(summen) == [d for d in dateien if d != "SHA256SUMS"]
    for rel, summe in summen.items():
        assert hashlib.sha256((ziel / rel).read_bytes()).hexdigest() == summe, rel
    assert not Path(str(ziel) + ".im-bau").exists()


def test_ein_gebautes_paket_laesst_sich_in_einer_anderen_welt_nachfahren(tmp_path, welt, baum, gefuehrt):
    ziel = tmp_path / "paket"
    assert _bauen(welt, ziel, tmp_path, baum).returncode == 0
    # Eine zweite Welt und ein zweiter Baum: nichts vom ersten Lauf liegt dort.
    zweiter = tmp_path / "zweiter"
    zweiter.mkdir()
    baum2 = zweiter / "baum"
    (baum2 / "src" / "rechner_pipeline").mkdir(parents=True)
    (baum2 / "src" / "rechner_pipeline" / "__init__.py").write_text("")
    _git(baum2, "init", "--quiet", "--initial-branch=main")
    _git(baum2, "add", "-A")
    _git(baum2, "commit", "--quiet", "-m", "stand")
    welt2 = zweiter / "welt"
    assert _lauf("welt_aufstellen.sh", str(welt2), "schluessel", baum=baum2,
                 SCHLUESSEL=str(zweiter / "schluessel")).returncode == 0
    lauf = _nachfahren(welt2, ziel, baum2)
    assert lauf.returncode == 0, lauf.text
    fall2 = baum2 / "faelle" / "gefuehrt"
    assert (fall2 / "abgeleitet" / "abox" / "fragmente" / "a.json").read_text() == "a"
    assert (fall2 / "abgeleitet" / "berichte" / "bericht.html").read_text() == "ergebnis"
    assert not (fall2 / "entscheide").exists()


@pytest.mark.parametrize("eingriff,meldung", [
    ("zeichnung", "Zeichnungen gehoeren nie ins Paket"),
    ("ausbruch", "ohne .."),
    ("einlegen_fehlt", "die Liste --erarbeitet nennt es nicht"),
    ("erwarte_fehlt", "die Liste --erwartung nennt es nicht"),
    ("registriere_fehlt", "keine solche Nachlieferung"),
    ("datei_fehlt", "liegt nicht im Fall"),
])
def test_rezept_und_paket_gehoeren_zusammen_sonst_entsteht_keins(tmp_path, welt, baum, gefuehrt, eingriff, meldung):
    ziel = tmp_path / "paket"
    listen = {}
    if eingriff == "zeichnung":
        (tmp_path / "erarbeitet.txt").write_text("abgeleitet/abox\nentscheide/A-M6-" + "a" * 64 + ".json\n")
    elif eingriff == "ausbruch":
        (tmp_path / "erwartung.txt").write_text("../../etwas\n")
    elif eingriff == "einlegen_fehlt":
        (tmp_path / "erarbeitet.txt").write_text("abgeleitet/abox\n")
    elif eingriff == "erwarte_fehlt":
        listen["erwartung"] = None
    elif eingriff == "registriere_fehlt":
        (tmp_path / "rezept.sh").write_text(REZEPT_PAKET + "registriere auskunft-9.md\n")
    elif eingriff == "datei_fehlt":
        (tmp_path / "erarbeitet.txt").write_text("abgeleitet/abox\nabgeleitet/transformation/abzug.spec.json\nabgeleitet/gibtsnicht.json\n")
    lauf = _bauen(welt, ziel, tmp_path, baum, **listen)
    assert lauf.returncode != 0 and meldung in lauf.text, lauf.text
    assert not ziel.exists()


def test_ein_paket_wird_nie_ueberschrieben(tmp_path, welt, baum, gefuehrt):
    ziel = tmp_path / "paket"
    ziel.mkdir()
    (ziel / "alt.txt").write_text("das fruehere Paket")
    lauf = _bauen(welt, ziel, tmp_path, baum)
    assert lauf.returncode == 2 and "nie ueberschrieben" in lauf.text
    assert sorted(p.name for p in ziel.iterdir()) == ["alt.txt"]


# --------------------------------------------------------------------------- #
# Die Systemkommandos in den Skripten
# --------------------------------------------------------------------------- #

def test_das_paket_nennt_den_stand_auf_dem_die_linie_des_falls_abgenommen_war(tmp_path, welt, baum, gefuehrt):
    # Ein Fall, der das Zielsystem geaendert hat, wird auf dem Stand DANACH
    # nachgefahren; die Welt braucht den Stand DAVOR. Den kennt nur die Linie
    # des festgehaltenen Falls — das Paket nimmt ihn mit.
    linie = welt / "linie"
    _annahme(linie, "A-K2", "a", "2026-10-01T10:00:00+00:00", "a" * 40)
    _annahme(linie, "A-K2", "b", "2026-10-02T10:00:00+00:00", "b" * 40)
    ziel = tmp_path / "paket-juengste"
    lauf = _bauen(welt, ziel, tmp_path, baum)
    assert lauf.returncode == 0, lauf.text
    assert (ziel / "STAND").read_text() == "VOR=" + "b" * 40 + "\n"
    assert "STAND" in (ziel / "SHA256SUMS").read_text()
    # Nennt der Fallauftrag die Annahme, auf die er den Fall stellt, gilt DIE —
    # auch wenn die Linie seither weitergegangen ist.
    auftrag = gefuehrt / "abgeleitet" / "auftrag"
    auftrag.mkdir(parents=True)
    (auftrag / "fallauftrag.json").write_text(json.dumps({"zielsystem": {"abnahmen": {"A-K2": "a" * 64}}}))
    ziel = tmp_path / "paket-auftrag"
    lauf = _bauen(welt, ziel, tmp_path, baum)
    assert lauf.returncode == 0, lauf.text
    assert (ziel / "STAND").read_text() == "VOR=" + "a" * 40 + "\n"
    # Ein Paket mit Stand faehrt das Skript zum Nachfahren wie jedes andere.
    andere = tmp_path / "andere"
    _lauf("welt_aufstellen.sh", str(andere), "schluessel", baum=baum, SCHLUESSEL=str(tmp_path / "schluessel-andere"))
    shutil.rmtree(gefuehrt)
    assert _nachfahren(andere, ziel, baum).returncode == 0


@pytest.mark.parametrize("linie", ["ohne_annahme", "kurzer_commit", "kein_hex", "keine"])
def test_ein_stand_den_die_linie_nicht_traegt_wird_nicht_erfunden(tmp_path, welt, baum, gefuehrt, linie):
    if linie == "ohne_annahme":
        _annahme(welt / "linie", "A-K2", "a", "2026-10-01T10:00:00+00:00", "a" * 40, entscheid="abgelehnt")
    elif linie in ("kurzer_commit", "kein_hex"):    # ein Commit ist 40 Hex-Zeichen, nichts sonst
        _annahme(welt / "linie", "A-K2", "a", "2026-10-01T10:00:00+00:00",
                 "8c1bed3" if linie == "kurzer_commit" else "z" * 40)
    ziel = tmp_path / "paket"
    lauf = _bauen(welt, ziel, tmp_path, baum)
    if linie == "keine":            # eine Welt ohne Linie: ein Paket ohne Stand
        assert lauf.returncode == 0 and not (ziel / "STAND").exists(), lauf.text
        assert "nicht genannt" in lauf.text
    else:
        assert lauf.returncode == 1 and not ziel.exists(), lauf.text
        assert ("keinen abgenommenen Kernstand" if linie == "ohne_annahme" else "keinen Commit") in lauf.text


# --------------------------------------------------------------------------- #
# laufzeit_aufstellen.sh: Welt und Fall in einem Aufruf
# --------------------------------------------------------------------------- #

@pytest.fixture
def system(tmp_path, baum):
    """Ein Interpreter, der mitschreibt und nur das hinlegt, woran die Skripte
    den Fortgang erkennen (Abschluesse, Linienbereich, Snapshots der Gates):
    Das Aufstellen einer Welt rechnet Minuten; was laufzeit_aufstellen.sh
    selbst entscheidet, ist, WELCHER Baum WAS rechnet."""
    (baum / "configs").mkdir()
    (baum / "configs" / "bestand_gesamt.toml").write_text("# Config vor dem Fall\n")
    _git(baum, "add", "-A")
    _git(baum, "commit", "--quiet", "-m", "der Stand vor dem Fall")
    vor = subprocess.run(["git", "-C", str(baum), "rev-parse", "HEAD"], capture_output=True, text=True, check=True).stdout.strip()
    (baum / "configs" / "bestand_gesamt.toml").write_text("# Config nach dem Fall\n")
    _git(baum, "commit", "--quiet", "-am", "der Fall hat das Zielsystem geaendert")
    spur = tmp_path / "aufrufe.txt"
    skript = tmp_path / "system.sh"
    skript.write_text(f"""#!/usr/bin/env bash
printf '%s | %s\\n' "$PYTHONPATH" "$*" >> "{spur}"
linie=""; stand=""; gate=""
while [ $# -gt 0 ]; do
  case "$1" in --linie) linie="$2" ;; --stand) stand="$2" ;; --gate) gate="$2" ;; esac
  shift
done
case "$(tail -1 "{spur}")" in
  *betrieb.tageslauf*) mkdir -p "$stand/abschluesse" ;;
  *"stand_belegen linie"*) mkdir -p "$linie/ordnung" "$linie/entscheide" "$linie/abgeleitet/tbox" ;;
  *gates.gate_entscheid*) : > "$linie/entscheide/$gate-$(printf 'a%.0s' $(seq 64)).json" ;;
esac
""")
    skript.chmod(0o755)
    return skript, spur, vor


def _laufzeit(welt: Path, paket: Path, baum: Path, tmp_path: Path, skript: Path, *args: str,
              **umgebung: str) -> subprocess.CompletedProcess:
    umgebung.setdefault("SCHLUESSEL", str(tmp_path / "schluessel-laufzeit"))
    lauf = _lauf("laufzeit_aufstellen.sh", str(welt), str(paket), *args, baum=baum, PYTHON=str(skript),
                 **{k: v for k, v in umgebung.items() if v})
    lauf.text = (lauf.stdout + lauf.stderr).decode()  # type: ignore[attr-defined]
    return lauf


REZEPT_LAUFZEIT = ('schritt "Fall anlegen" mkdir -p faelle/probe\n'
                   "schritt \"eins\" bash -c 'cat configs/bestand_gesamt.toml >> faelle/probe/spur'\n"
                   'haltepunkt mitte\n'
                   "schritt \"zwei\" bash -c 'echo zwei >> faelle/probe/spur'\n")


def test_die_welt_entsteht_auf_dem_stand_vor_dem_fall_und_der_fall_laeuft_auf_dem_stand_danach(tmp_path, baum, system):
    skript, spur, vor = system
    welt = tmp_path / "laufzeit"
    paket = _paket(tmp_path, REZEPT_LAUFZEIT, stand=vor)
    lauf = _laufzeit(welt, paket, baum, tmp_path, skript, "--bis", "mitte")
    assert lauf.returncode == 0, lauf.text
    assert "WELT STEHT" in lauf.text and "Haltepunkt mitte erreicht" in lauf.text
    # Der Stand vor dem Fall liegt als eigener Baum in der Welt ...
    vorbaum = welt / "baum-vor"
    kopf = subprocess.run(["git", "-C", str(vorbaum), "rev-parse", "HEAD"], capture_output=True, text=True, check=True)
    assert kopf.stdout.strip() == vor
    assert (vorbaum / "configs" / "bestand_gesamt.toml").read_text() == "# Config vor dem Fall\n"
    # ... die Welt ist AUF IHM aufgestellt: jedes Kommando des Aufstellens rechnet mit seinem Paket,
    aufrufe = spur.read_text().splitlines()
    assert len(aufrufe) > 8 and all(z.startswith(f"{vorbaum}/src | ") for z in aufrufe), aufrufe
    assert (welt / "daten" / "configs" / "bestand.toml").read_text() == "# Config vor dem Fall\n"
    # ... und der Fall laeuft auf dem Baum danach, nicht auf dem davor.
    assert (baum / "faelle" / "probe" / "spur").read_text() == "# Config nach dem Fall\n"
    assert not (vorbaum / "faelle").exists()
    # Derselbe Aufruf noch einmal: Die Welt steht, nur das Paket faehrt weiter.
    zweiter = _laufzeit(welt, paket, baum, tmp_path, skript)
    assert zweiter.returncode == 0, zweiter.text
    assert "steht schon" in zweiter.text and "NACHGEFAHREN" in zweiter.text
    assert spur.read_text().splitlines() == aufrufe          # nichts wurde neu aufgestellt
    assert (baum / "faelle" / "probe" / "spur").read_text() == "# Config nach dem Fall\nzwei\n"


def test_je_welt_ein_eigenes_schluesselverzeichnis(tmp_path, baum, system):
    # Ohne Angabe liegen die Schluessel unter ~/.plv-schluessel/<name der welt>.
    # Ein zweiter Versuch unter anderem Namen scheitert so nicht daran, dass
    # das Schluesselverzeichnis des ersten schon eine Ordnung traegt.
    skript, spur, vor = system
    heim = baum.parent / "heim"
    paket = _paket(tmp_path, REZEPT_LAUFZEIT, stand=vor)
    for name in ("erste", "zweite"):
        lauf = _laufzeit(tmp_path / name, paket, baum, tmp_path, skript, "--bis", "mitte", SCHLUESSEL="")
        assert lauf.returncode == 0, (name, lauf.text)
        ort = heim / ".plv-schluessel" / name
        assert sorted(p.name for p in ort.glob("*.key")) == sorted(f"{r}.key" for r in ROLLEN)
        assert _einstellung(tmp_path / name, "VORSTAND_KEY") == str(ort / "vorstand.key")


@pytest.mark.parametrize("fall", ["ohne_stand", "fremder_commit", "kein_vorfahr", "verzeichnis_liegt",
                                  "aufstellen_abgebrochen"])
def test_laufzeit_aufstellen_haelt_bevor_es_etwas_anlegt(tmp_path, baum, system, fall):
    skript, spur, vor = system
    welt = tmp_path / "laufzeit"
    stand = {"ohne_stand": None, "fremder_commit": "c" * 40, "kein_vorfahr": None, "verzeichnis_liegt": vor,
             "aufstellen_abgebrochen": vor}[fall]
    if fall == "kein_vorfahr":      # ein Commit neben der Geschichte des Baums
        _git(baum, "checkout", "--quiet", "-b", "seitenzweig", vor)
        (baum / "seite.txt").write_text("x\n")
        _git(baum, "add", "-A")
        _git(baum, "commit", "--quiet", "-m", "seitenzweig")
        stand = subprocess.run(["git", "-C", str(baum), "rev-parse", "HEAD"], capture_output=True, text=True, check=True).stdout.strip()
        _git(baum, "checkout", "--quiet", "main")
    if fall == "verzeichnis_liegt":
        welt.mkdir()
        (welt / "notiz.txt").write_text("keine Welt\n")
    if fall == "aufstellen_abgebrochen":
        # Alle vier Erstabnahmen liegen, aber das Aufstellen endete davor, den
        # Anfangsbestand zu binden: Das Protokoll traegt sein letztes Wort nicht.
        for gate in ("A-K2", "A-O1", "A-T1", "A-B3"):
            _annahme(welt / "linie", gate, "a", "2026-10-05T14:00:00+00:00", vor)
        (welt / "aufstellen.log").write_text("### ... A-B3 zeichnen (als mensch/betrieb)\n")
    vorher = sorted(str(d.relative_to(welt)) for d in welt.rglob("*")) if welt.exists() else None
    paket = _paket(tmp_path, REZEPT_LAUFZEIT, stand=stand)
    lauf = _laufzeit(welt, paket, baum, tmp_path, skript)
    assert lauf.returncode == 2, lauf.text
    assert {"ohne_stand": "nennt den Stand nicht", "fremder_commit": "kennt dieser Codebaum nicht",
            "kein_vorfahr": "kein Vorfahr", "verzeichnis_liegt": "keine aufgestellte Welt",
            "aufstellen_abgebrochen": "keine aufgestellte Welt"}[fall] in lauf.text
    assert not spur.exists() and not (baum / "faelle").exists()
    assert not (tmp_path / "schluessel-laufzeit").exists()
    if vorher is None:
        assert not welt.exists()
    else:                           # was lag, liegt unveraendert
        assert sorted(str(d.relative_to(welt)) for d in welt.rglob("*")) == vorher


def _systemkommandos(text: str, name: str) -> list[Kommando]:
    """Die Aufrufe ``-m rechner_pipeline....`` eines Shell-Skripts als
    Kommandos mit Platzhaltern: Fortsetzungszeilen verbunden, an ``&&`` und
    ``||`` getrennt, jede Shell-Variable ein Platzhalter (ein Wert, dessen Typ
    und Auswahl nicht geprueft werden)."""
    logisch: list[tuple[int, str]] = []
    puffer, start = "", None
    for nr, zeile in enumerate(text.splitlines(), 1):
        if start is None:
            start = nr
        stueck = zeile.rstrip()
        if stueck.endswith("\\"):
            puffer += stueck[:-1] + " "
            continue
        logisch.append((start, puffer + stueck))
        puffer, start = "", None
    aus: list[Kommando] = []
    for nr, zeile in logisch:
        if zeile.lstrip().startswith("#"):
            continue
        for teil in re.split(r"\s(?:&&|\|\|)\s", zeile):
            treffer = re.search(r"-m (rechner_pipeline\.[\w.]+)(.*)", teil)
            if not treffer:
                continue
            rest = treffer.group(2)
            # Felder, die erst zur Laufzeit Argumente tragen: der Ring, die
            # Mandate je Rolle, die Rolle einer Ablehnung, durchgereichte Argumente.
            rest = rest.replace('"${mandate[@]}"', "--mandat <rolle>=<datei>")
            rest = rest.replace('"${ZUSATZ[@]}"', "").replace('"$@"', "")
            rest = re.sub(r'"\$\{@:\d+\}"', "", rest)      # weitere, durchgereichte Argumente
            rest = re.sub(r"(?<![\w\"])\$R(?![\w])", "--freigabe-schluessel <schluessel>", rest)
            rest = re.sub(r'"\$\{RING_\w+\[@\]\}"', "--freigabe-schluessel <schluessel>", rest)
            rest = re.sub(r"\$\{?(\w+)\}?", lambda m: f"<{m.group(1)}>", rest)
            aus.append(Kommando(name, nr, " ".join(f"python -m {treffer.group(1)}{rest}".split())))
    return aus


SKRIPT_KOMMANDOS = {name: _systemkommandos((WELT_SKRIPTE / name).read_text(encoding="utf-8"), f"deploy/welt/{name}")
                    for name in SKRIPTE}


@pytest.mark.parametrize("kommando", [k for ks in SKRIPT_KOMMANDOS.values() for k in ks], ids=str)
def test_jedes_systemkommando_der_skripte_besteht_den_parser(kommando):
    befund = pruefe(kommando)
    assert befund is None, f"{kommando}\n  -> {befund}"


def test_der_detektor_sieht_jedes_kommando_und_faellt_was_falsch_ist():
    # Die Menge, mit == gehalten: Ein Kommando, das die Extraktion nicht mehr
    # sieht, faellt hier auf statt still aus der Pruefung.
    assert {name: len(ks) for name, ks in SKRIPT_KOMMANDOS.items()} == {
        "welt_aufstellen.sh": 10, "fall_starten.sh": 4, "fall_zeichnen.sh": 1, "fall_nachfahren.sh": 3,
        "zugang.sh": 7, "paket_bauen.sh": 0, "laufzeit_aufstellen.sh": 0}
    module = {k.modul for ks in SKRIPT_KOMMANDOS.values() for k in ks}
    assert {"rechner_pipeline.betrieb.tageslauf", "rechner_pipeline.gates.gate_entscheid",
            "rechner_pipeline.gates.fall_belegen", "rechner_pipeline.fall",
            "rechner_pipeline.betrieb.zugangsprobe", "rechner_pipeline.betrieb.neuaufsetzen",
            "rechner_pipeline.betrieb.anfangsbestand"} <= module
    # Positivkontrolle durch dieselbe Extraktion: ein entfallener Schalter,
    # ein unbekannter Unterbefehl und eine unzulaessige Auswahl fallen.
    falsch = (
        'schritt "x" "$PY" -m rechner_pipeline.fall anlegen --fall "$FALL" --scope bestand \\\n'
        '    --beschreibung "$B" --gibt-es-nicht 1 || return 1\n'
        '  schritt "y" "$PY" -m rechner_pipeline.gates.stand_belegen gibtsnicht --linie "$L" \\\n'
        '  && schritt "z" "$PY" -m rechner_pipeline.fall anlegen --fall "$FALL" --scope alles --beschreibung "$B"\n'
        '# "$PY" -m rechner_pipeline.fall status --fall "$FALL"\n')
    befunde = [pruefe(k) for k in _systemkommandos(falsch, "kontrolle")]
    assert len(befunde) == 3 and all(befunde), befunde
    assert "--gibt-es-nicht" in befunde[0] and "gibtsnicht" in befunde[1] and "alles" in befunde[2]
