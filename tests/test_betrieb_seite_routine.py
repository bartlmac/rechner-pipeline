"""Die Routine des Betriebsteils der Seite (ADR-029): plv/betrieb/betrieb_seite.sh.

Was die Routine zusichert, laesst sich ohne Docker und ohne GitHub pruefen:
Der Zweig betrieb traegt genau paket/ (die oeffentlichen Dateien des Pakets),
anker.jsonl und A-B1.json; ein Paket, das nicht zu stand.json passt, wird
nicht geschoben; die Vorpruefung haelt an, wenn der Tageslauf den Tag nicht
uebernommen hat oder das Image nicht der Code-Stand ist, mit dem die Seite
rendert. Origin ist hier ein lokales Repository, docker und systemctl sind
Attrappen. Export und A-B1 im Image misst der Trockenlauf (Phase 3).

Knoten: system/betrieb
"""

from __future__ import annotations

import datetime as dt
import json
import os
import re
import subprocess
from pathlib import Path

import pytest

from rechner_pipeline.betrieb import seite as st
from rechner_pipeline.betrieb.tageslauf import EXIT_OK, tageslauf
from rechner_pipeline.models import anker as ak
from tests.test_betrieb_seite import _ablage

REPO = Path(__file__).resolve().parents[1]
DEPLOY = REPO / "plv" / "betrieb"
SKRIPT = DEPLOY / "betrieb_seite.sh"
HEUTE = "2026-02-03"


def _git(*args: str, cwd: Path | None = None) -> str:
    return subprocess.run(["git", *args], cwd=cwd, check=True, capture_output=True,
                          text=True).stdout.strip()


def _origin_mit_main(wurzel: Path, codestand: str) -> Path:
    """Ein leeres Repository als origin, dessen main nur CODESTAND traegt."""
    origin = wurzel / "origin.git"
    _git("init", "-q", "--bare", "-b", "main", str(origin))
    blob = subprocess.run(["git", "--git-dir", str(origin), "hash-object", "-w", "--stdin"],
                          input=codestand + "\n", check=True, capture_output=True,
                          text=True).stdout.strip()
    baum = subprocess.run(["git", "--git-dir", str(origin), "mktree"],
                          input=f"100644 blob {blob}\tCODESTAND\n", check=True,
                          capture_output=True, text=True).stdout.strip()
    umgebung = dict(os.environ, GIT_AUTHOR_NAME="t", GIT_AUTHOR_EMAIL="t@t",
                    GIT_COMMITTER_NAME="t", GIT_COMMITTER_EMAIL="t@t")
    commit = subprocess.run(["git", "--git-dir", str(origin), "commit-tree", baum, "-m", "Rahmen"],
                            check=True, capture_output=True, text=True,
                            env=umgebung).stdout.strip()
    _git("--git-dir", str(origin), "update-ref", "refs/heads/main", commit)
    return origin


def _einstellungen(wurzel: Path, **mehr: str) -> Path:
    werte = {
        "PLV": str(wurzel / "plv"), "AUSGABE": str(wurzel / "ausgabe"),
        "ANKER_DIR": str(wurzel / "anker"), "KLON": str(wurzel / "klon.git"),
        "FALL": str(wurzel / "fall"), "LINIE": str(wurzel / "linie"),
        "ORDNUNG": str(wurzel / "ring" / "ordnung.json"),
        "MANDAT": str(wurzel / "ring" / "mandat.txt"),
        "VORSTAND_KEY": str(wurzel / "ring" / "vorstand.key"),
        "BETRIEB_MENSCH_KEY": str(wurzel / "ring" / "betrieb-mensch.key"),
        "ENTSCHEIDER": "Probe", "HEUTE": HEUTE, "AUSLIEFERUNG": "ja",
    }
    werte.update(mehr)
    datei = wurzel / "betrieb-seite.conf"
    datei.write_text("".join(f'{k}="{v}"\n' for k, v in werte.items()), encoding="utf-8")
    return datei


def _routine(einstellungen: Path, *args: str, path: str | None = None):
    umgebung = dict(os.environ)
    umgebung.pop("GIT_INDEX_FILE", None)
    if path is not None:
        umgebung["PATH"] = path
    return subprocess.run(["bash", str(SKRIPT), str(einstellungen), *args],
                          capture_output=True, text=True, env=umgebung)


#: Der Digest, den der Tageslauf im Image aus der .env bekommt (compose.yml,
#: --image-digest); ohne ihn weist das Paket eine Luecke aus.
DIGEST = "ghcr.io/x/rechner-pipeline-plv@sha256:" + "d" * 64


def _wie_im_image(monkeypatch) -> None:
    """Revision und Tag traegt das Image (Umgebung des Containers)."""
    monkeypatch.setenv("PLV_IMAGE_REVISION", "a" * 40)
    monkeypatch.setenv("PLV_IMAGE_TAG", "probe")


@pytest.fixture()
def welt(tmp_path_factory, monkeypatch):
    """Ein echtes Paket (Auslieferung) aus einem gefuehrten Stand, der Anker,
    eine A-B1, die den Satz bindet, ein origin mit main und ein Klon."""
    wurzel = tmp_path_factory.mktemp("routine")
    _wie_im_image(monkeypatch)
    ablage = _ablage(wurzel / "plv" / "daten")
    assert tageslauf(ablage, dt.date(2026, 2, 3), image_digest=DIGEST)[0] == EXIT_OK
    paket = st.stands_paket(ablage, wurzel / "ausgabe" / "paket",
                            anker_verzeichnis=wurzel / "anker", art=ak.ART_AUSLIEFERUNG)
    stand = json.loads((paket / "stand.json").read_text("utf-8"))
    satz = stand["anker"]["sha256"]
    (wurzel / "fall" / "entscheide").mkdir(parents=True)
    ab1 = {"gate": "A-B1", "entscheid": "angenommen", "pflichtbelege": {"anker": [satz]},
           "zeichnung": {"rolle": "mensch/betrieb", "schluesselklasse": "simulation"}}
    (wurzel / "fall" / "entscheide" / f"A-B1-{'a' * 64}.json").write_text(
        json.dumps(ab1), encoding="utf-8")
    origin = _origin_mit_main(wurzel, "a" * 40)
    _git("clone", "-q", "--bare", str(origin), str(wurzel / "klon.git"))
    return wurzel, origin, paket, stand


def _baum(origin: Path, ref: str = "betrieb") -> set:
    return set(_git("--git-dir", str(origin), "ls-tree", "-r", "--name-only", ref).splitlines())


def test_der_zweig_traegt_genau_paket_anker_und_ab1(welt):
    """Genau die oeffentlichen Dateien, byteweise, und nichts sonst: keine
    .parquet (Vertragsebene), keine Datei, die stand.json nicht nennt.

    Mutationsprobe: den Ausschluss von .parquet in oeffentliche_dateien
    entfernen -> rot."""
    wurzel, origin, paket, stand = welt
    (paket / "fremd.txt").write_text("nicht im Paket", encoding="utf-8")
    lauf = _routine(_einstellungen(wurzel), "zweig")
    assert lauf.returncode == 0, lauf.stderr
    oeffentlich = {f"paket/{n}" for n in stand["dateien"] if not n.endswith(".parquet")}
    assert any(n.endswith(".parquet") for n in stand["dateien"])
    assert _baum(origin) == oeffentlich | {"paket/stand.json", "anker.jsonl", "A-B1.json"}
    for name in ("paket/stand.json", "paket/index.html", "anker.jsonl"):
        quelle = {"anker.jsonl": wurzel / "anker" / ak.ANKER_DATEI}.get(
            name, paket / name.removeprefix("paket/"))
        inhalt = subprocess.run(["git", "--git-dir", str(origin), "show", f"betrieb:{name}"],
                                check=True, capture_output=True).stdout
        assert inhalt == quelle.read_bytes(), name
    autor = _git("--git-dir", str(origin), "log", "-1", "--format=%an <%ae>|%s", "betrieb")
    assert autor == f"Betriebsdienst PLV <betrieb@plv-fiktion.invalid>|Stand vom {HEUTE}"

    # Derselbe Stand ein zweites Mal: kein neuer Commit.
    vorher = _git("--git-dir", str(origin), "rev-parse", "betrieb")
    nochmal = _routine(_einstellungen(wurzel), "zweig")
    assert nochmal.returncode == 0 and "nichts zu schieben" in nochmal.stdout
    assert _git("--git-dir", str(origin), "rev-parse", "betrieb") == vorher


def test_ein_paket_das_nicht_zu_stand_json_passt_wird_nicht_geschoben(welt):
    """Mutationsprobe: den Vergleich der Pruefsumme entfernen -> rot."""
    wurzel, origin, paket, _stand = welt
    seite = paket / "index.html"
    seite.write_bytes(seite.read_bytes() + b"<!-- veraendert -->")
    lauf = _routine(_einstellungen(wurzel), "zweig")
    assert lauf.returncode != 0
    assert "index.html: weicht von stand.json ab" in lauf.stderr and "HALT" in lauf.stderr
    assert "betrieb" not in _git("--git-dir", str(origin), "branch", "--list", "betrieb")


def test_ohne_a_b1_von_mensch_betrieb_wird_nicht_geschoben(welt):
    """Die A-B1 muss den Satz binden UND von mensch/betrieb sein (ADR-029,
    Entscheid e: die Routine prueft die Rolle nach dem Zeichnen)."""
    wurzel, origin, _paket, _stand = welt
    datei = next((wurzel / "fall" / "entscheide").glob("A-B1-*.json"))
    ab1 = json.loads(datei.read_text("utf-8"))
    ab1["zeichnung"]["rolle"] = "mensch/vorstand"
    datei.write_text(json.dumps(ab1), encoding="utf-8")
    lauf = _routine(_einstellungen(wurzel), "zweig")
    assert lauf.returncode != 0 and "keine angenommene A-B1 von mensch/betrieb" in lauf.stderr
    assert "betrieb" not in _git("--git-dir", str(origin), "branch", "--list", "betrieb")


def test_ein_paket_mit_luecke_wird_nicht_geschoben(tmp_path_factory, monkeypatch):
    """Der Workflow liefert ein Paket, das eine Luecke ausweist, nicht aus
    (vorzeige-url, Probe 15.10.: Image-Digest "nicht erfasst"). Die Routine
    haelt deshalb vorher an und nennt die Luecke.

    Mutationsprobe: die Pruefung der Luecken in pruefe_paket entfernen ->
    rot."""
    wurzel = tmp_path_factory.mktemp("luecke")
    _wie_im_image(monkeypatch)
    ablage = _ablage(wurzel / "plv" / "daten")
    assert tageslauf(ablage, dt.date(2026, 2, 3))[0] == EXIT_OK   # ohne Digest
    st.stands_paket(ablage, wurzel / "ausgabe" / "paket", anker_verzeichnis=wurzel / "anker")
    origin = _origin_mit_main(wurzel, "a" * 40)
    _git("clone", "-q", "--bare", str(origin), str(wurzel / "klon.git"))
    lauf = _routine(_einstellungen(wurzel, AUSLIEFERUNG="nein"), "zweig")
    assert lauf.returncode != 0
    assert "das Paket weist Luecken aus (Image-Digest des Laufs)" in lauf.stderr
    assert "betrieb" not in _git("--git-dir", str(origin), "branch", "--list", "betrieb")


def test_eine_momentaufnahme_traegt_keine_a_b1(tmp_path_factory, monkeypatch):
    """AUSLIEFERUNG=nein (Entscheid e, Weg 2): Paket und Anker, keine A-B1,
    und die Routine verlangt keinen der Schluessel fuer A-B1."""
    wurzel = tmp_path_factory.mktemp("moment")
    _wie_im_image(monkeypatch)
    ablage = _ablage(wurzel / "plv" / "daten")
    assert tageslauf(ablage, dt.date(2026, 2, 3), image_digest=DIGEST)[0] == EXIT_OK
    st.stands_paket(ablage, wurzel / "ausgabe" / "paket", anker_verzeichnis=wurzel / "anker")
    origin = _origin_mit_main(wurzel, "a" * 40)
    _git("clone", "-q", "--bare", str(origin), str(wurzel / "klon.git"))
    einstellungen = wurzel / "betrieb-seite.conf"
    einstellungen.write_text(
        f'PLV="{wurzel}/plv"\nAUSGABE="{wurzel}/ausgabe"\nANKER_DIR="{wurzel}/anker"\n'
        f'KLON="{wurzel}/klon.git"\nHEUTE="{HEUTE}"\nAUSLIEFERUNG=nein\n', encoding="utf-8")
    lauf = _routine(einstellungen, "zweig")
    assert lauf.returncode == 0, lauf.stderr
    baum = _baum(origin)
    assert "A-B1.json" not in baum and "anker.jsonl" in baum and "paket/stand.json" in baum


def test_trockenlauf_schiebt_nicht(welt):
    wurzel, origin, _paket, _stand = welt
    lauf = _routine(_einstellungen(wurzel), "zweig", "--ohne-push")
    assert lauf.returncode == 0, lauf.stderr
    assert "Trockenlauf" in lauf.stdout
    assert "betrieb" not in _git("--git-dir", str(origin), "branch", "--list", "betrieb")
    assert _baum(wurzel / "klon.git", "betrieb-routine") >= {"anker.jsonl", "A-B1.json"}


# --- Vorpruefung, mit Attrappen fuer docker und systemctl --------------------


def _attrappen(wurzel: Path, revision: str) -> str:
    bin_ = wurzel / "bin"
    bin_.mkdir(exist_ok=True)
    (bin_ / "docker").write_text(
        "#!/usr/bin/env bash\n"
        'case "$*" in\n'
        '  *"config --images tageslauf"*) echo "ghcr.io/x/rechner-pipeline-plv:probe" ;;\n'
        f'  "image inspect"*) echo "{revision}" ;;\n'
        '  *) echo "docker-Attrappe: $*" >&2; exit 9 ;;\n'
        "esac\n", encoding="utf-8")
    (bin_ / "systemctl").write_text("#!/usr/bin/env bash\necho inactive\n", encoding="utf-8")
    for f in bin_.iterdir():
        f.chmod(0o755)
    return f"{bin_}:{os.environ['PATH']}"


def _protokoll(wurzel: Path, **zeile) -> None:
    pfad = wurzel / "plv" / "daten" / "journal" / "protokoll.jsonl"
    pfad.parent.mkdir(parents=True, exist_ok=True)
    werte = {"heute": HEUTE, "uebernommen": True, "pb1": {"urteil": "gruen"},
             "image_revision": "b" * 40}
    werte.update(zeile)
    pfad.write_text(json.dumps({"heute": "2026-02-02"}) + "\n" + json.dumps(werte) + "\n",
                    encoding="utf-8")


@pytest.fixture()
def vorpruefung(tmp_path):
    origin = _origin_mit_main(tmp_path, "b" * 40)
    _git("clone", "-q", "--bare", str(origin), str(tmp_path / "klon.git"))
    return tmp_path


def test_die_vorpruefung_geht_durch_wenn_alles_stimmt(vorpruefung):
    _protokoll(vorpruefung)
    lauf = _routine(_einstellungen(vorpruefung), "pruefen", path=_attrappen(vorpruefung, "b" * 40))
    assert lauf.returncode == 0, lauf.stderr
    assert f"Tageslauf {HEUTE} uebernommen" in lauf.stdout and "= CODESTAND" in lauf.stdout


@pytest.mark.parametrize("zeile, revision, meldung", [
    ({"heute": "2026-02-02"}, "b" * 40, "der Tageslauf fuehrt 2026-02-02, nicht 2026-02-03"),
    ({"uebernommen": False}, "b" * 40, "ist nicht uebernommen"),
    ({"pb1": {"urteil": "rot"}}, "b" * 40, "ist nicht uebernommen (P-B1 rot)"),
    ({}, "c" * 40, "der Tageslauf lief mit " + "b" * 40),
    ({"image_revision": "c" * 40}, "c" * 40, "erst CODESTAND per Pull Request nachziehen"),
])
def test_die_vorpruefung_haelt_an(vorpruefung, zeile, revision, meldung):
    """Ein Tag, der nicht uebernommen ist, ein Image, das nicht das des
    Tageslaufs ist, ein Image, das nicht CODESTAND ist: je ein HALT.

    Mutationsprobe: den Vergleich mit CODESTAND entfernen -> der letzte Fall
    wird rot."""
    _protokoll(vorpruefung, **zeile)
    lauf = _routine(_einstellungen(vorpruefung), "pruefen", path=_attrappen(vorpruefung, revision))
    assert lauf.returncode != 0
    assert meldung in lauf.stderr


# --- Was die Dateien zusichern ----------------------------------------------


def _text(name: str) -> str:
    return (DEPLOY / name).read_text(encoding="utf-8")


def test_timer_um_2330_nach_dem_tageslauf():
    timer = _text("betrieb-seite.timer")
    assert re.search(r"^OnCalendar=\*-\*-\* 23:30:00", timer, re.M)
    assert re.search(r"^Persistent=true", timer, re.M)
    service = _text("betrieb-seite.service")
    assert re.search(r"^Type=oneshot", service, re.M)
    assert re.search(r"^After=.*\btageslauf\.service\b", service, re.M)
    assert "ExecStart=%h/apps/plv/betrieb_seite.sh %h/apps/plv/betrieb-seite.conf" in service


def test_das_skript_schiebt_nur_betrieb_ohne_force_und_nur_mit_dem_deploy_key():
    """Was sich nicht ohne GitHub ausprobieren laesst, steht als Text fest:
    ein Push, nur auf refs/heads/betrieb, ohne Force; ssh nur mit dem
    Deploy-Key und ohne ~/.ssh/config; Schluessel nur lesend im Container;
    kein rekursives Loeschen."""
    skript = SKRIPT.read_text(encoding="utf-8")
    pushes = re.findall(r"^\s*git_klon push .*$", skript, re.M)
    assert pushes == ['  git_klon push origin "$commit:refs/heads/betrieb" || halt "Push auf betrieb abgewiesen"']
    assert "--force" not in skript and not re.search(r"push[^\n]* -f\b", skript)
    assert 'ssh -F /dev/null -o IdentitiesOnly=yes' in skript
    assert "set -u -o pipefail" in skript
    for bind in ("$ORDNUNG:/ring/zeichnungsordnung.json:ro", "$VORSTAND_KEY:/ring/vorstand.key:ro",
                 "$BETRIEB_MENSCH_KEY:/ring/betrieb-mensch.key:ro", "$MANDAT:/ring/mandat.txt:ro",
                 "$LINIE:/linie:ro"):
        assert bind in skript, bind
    assert not re.search(r"\brm\s+(-[a-zA-Z]*r|--recursive)", skript)
    assert os.access(SKRIPT, os.X_OK)
    beispiel = _text("betrieb-seite.beispiel.conf")
    for schluessel in ("PLV", "AUSGABE", "ANKER_DIR", "AUSLIEFERUNG", "FALL", "LINIE", "ORDNUNG",
                       "MANDAT", "VORSTAND_KEY", "BETRIEB_MENSCH_KEY", "ENTSCHEIDER", "KLON",
                       "DEPLOY_KEY"):
        assert re.search(rf"^{schluessel}=", beispiel, re.M), schluessel
