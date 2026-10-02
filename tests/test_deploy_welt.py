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
* Jedes Systemkommando, das ein Skript faehrt, nimmt der Parser seines Moduls
  an (dieselbe Pruefung wie fuer die Dokumente,
  ``tests/test_dokumentierte_kommandos.py``): Ein Skript, das einen entfallenen
  Schalter nennt, scheitert sonst erst beim Aufstellen — nach Minuten.

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


@pytest.mark.parametrize("skript", ["welt_aufstellen.sh", "fall_starten.sh", "fall_zeichnen.sh", "fall_nachfahren.sh"])
def test_shell_skripte_sind_syntaktisch_gueltig(skript):
    lauf = subprocess.run(["bash", "-n", str(WELT_SKRIPTE / skript)], capture_output=True, text=True)
    assert lauf.returncode == 0, lauf.stderr


# --------------------------------------------------------------------------- #
# fall_nachfahren.sh: ein Paket Schritt fuer Schritt
# --------------------------------------------------------------------------- #

def _paket(wo: Path, rezept: str, *, erarbeitet: dict | None = None, erwartung: dict | None = None,
           fallname: str = "probe") -> Path:
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
# Die Systemkommandos in den Skripten
# --------------------------------------------------------------------------- #

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
            rest = re.sub(r"(?<![\w\"])\$R(?![\w])", "--freigabe-schluessel <schluessel>", rest)
            rest = re.sub(r"\$\{?(\w+)\}?", lambda m: f"<{m.group(1)}>", rest)
            aus.append(Kommando(name, nr, " ".join(f"python -m {treffer.group(1)}{rest}".split())))
    return aus


SKRIPT_KOMMANDOS = {name: _systemkommandos((WELT_SKRIPTE / name).read_text(encoding="utf-8"), f"deploy/welt/{name}")
                    for name in ("welt_aufstellen.sh", "fall_starten.sh", "fall_zeichnen.sh", "fall_nachfahren.sh")}


@pytest.mark.parametrize("kommando", [k for ks in SKRIPT_KOMMANDOS.values() for k in ks], ids=str)
def test_jedes_systemkommando_der_skripte_besteht_den_parser(kommando):
    befund = pruefe(kommando)
    assert befund is None, f"{kommando}\n  -> {befund}"


def test_der_detektor_sieht_jedes_kommando_und_faellt_was_falsch_ist():
    # Die Menge, mit == gehalten: Ein Kommando, das die Extraktion nicht mehr
    # sieht, faellt hier auf statt still aus der Pruefung.
    assert {name: len(ks) for name, ks in SKRIPT_KOMMANDOS.items()} == {
        "welt_aufstellen.sh": 10, "fall_starten.sh": 4, "fall_zeichnen.sh": 1, "fall_nachfahren.sh": 1}
    module = {k.modul for ks in SKRIPT_KOMMANDOS.values() for k in ks}
    assert {"rechner_pipeline.betrieb.tageslauf", "rechner_pipeline.gates.gate_entscheid",
            "rechner_pipeline.gates.fall_belegen", "rechner_pipeline.fall"} <= module
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
