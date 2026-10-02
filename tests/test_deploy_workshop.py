"""deploy/workshop: dieselben Pins wie die CI auf einem festen System, und kein Nachziehen verwirft Arbeit.

Die Dateien sind Text und Shell. Was ein Test hier halten kann, ist Mechanik:

* Das Image der Arbeitsumgebung steht auf einem FESTEN System (Debian 12 mit
  dessen Python) und nimmt dieselbe Pin-Datei wie die CI; die Selbstpruefung
  verlangt den Interpreter der CI. Sonst rechnet ein eingerichteter Rechner
  in einer anderen Umgebung als die, gegen die er verglichen wird — und
  nichts meldet es.
* Die Bauwerkzeuge kommen aus ``pyproject.toml``, nicht aus einer zweiten
  Liste; das Paket wird ohne Aufloesung und ohne Netz installiert.
* ``plv-einrichten stand`` zieht einen Baum nur nach, wenn darin keine eigene
  Arbeit liegt. Nicht committete Dateien und eigene Commits halten es an, und
  der Baum bleibt, wie er war: Auf dem Rechner eines Teilnehmers liegt ein
  Fall, und ein Werkzeug der Einrichtung darf ihn nie kosten.
* Das Abbild traegt nur veroeffentlichte Marken auf fremde Rechner, und die
  Baeume entstehen in einem Container ohne Netz.
* Das Windows-Skript ist reines ASCII: Windows PowerShell 5.1 liest eine
  Datei ohne BOM nicht als UTF-8.

Ob das Abbild baut und sich auf einem Windows-Rechner importieren laesst,
prueft kein Unit-Test — das tut ``abbild_bauen.sh`` mit der Selbstpruefung im
Container, und wer es einrichtet.

Knoten: system/architektur
"""

from __future__ import annotations

import os
import re
import subprocess
from pathlib import Path

import pytest

REPO = Path(__file__).resolve().parents[1]
WORKSHOP = REPO / "deploy" / "workshop"
EINRICHTEN = WORKSHOP / "einrichten.sh"


def _text(name: str) -> str:
    return (WORKSHOP / name).read_text(encoding="utf-8")


# --------------------------------------------------------------------------- #
# Das Image
# --------------------------------------------------------------------------- #

def test_arbeitsumgebung_steht_auf_festem_system_mit_den_pins_der_ci():
    workshop = _text("Dockerfile")
    # Ein benanntes Debian, kein wandernder Tag: python:3.11-slim wechselte
    # das System unter derselben Bezeichnung.
    assert re.findall(r"^FROM (\S+)", workshop, re.M) == ["debian:12-slim"]
    assert re.search(r"pip install[^\n]* -r /tmp/pins/requirements-dev\.txt", workshop)
    # Kein zweiter Aufloesungsweg: pyproject-Extras werden nicht installiert.
    assert "[dev]" not in workshop
    # Der Interpreter der CI ist der, den die Selbstpruefung verlangt.
    workflow = (REPO / ".github" / "workflows" / "tests.yml").read_text(encoding="utf-8")
    gross, klein = re.search(r'python-version:\s*"(\d+)\.(\d+)"', workflow).groups()
    assert f"sys.version_info[:2] == ({gross}, {klein})" in _text("einrichten.sh")


def test_bauwerkzeuge_kommen_aus_pyproject_und_das_paket_ohne_netz():
    workshop = _text("Dockerfile")
    # Die Pins des Baus stehen an EINER Stelle; das Image liest sie dort.
    assert "['build-system']['requires']" in workshop
    assert not re.search(r"setuptools==|wheel==", workshop)
    einrichten = _text("einrichten.sh")
    aufruf = re.search(r"-m pip install[^|]*?-e \"\$ziel\"", einrichten, re.S).group(0)
    for schalter in ("--no-deps", "--no-index", "--no-build-isolation"):
        assert schalter in aufruf, schalter
    # Ein .venv mit eigenem pip braechte ein ungepinntes setuptools VOR das
    # gepinnte der Umgebung.
    assert re.search(r"-m venv --system-site-packages --without-pip", einrichten)


def test_abbild_nimmt_nur_veroeffentlichte_marken_und_baut_ohne_netz():
    bauen = _text("abbild_bauen.sh")
    # Ohne den ausdruecklichen Schalter haelt jede Marke ausserhalb von
    # origin/main den Bau an.
    assert re.search(r'if \[ "\$UNVEROEFFENTLICHT" -eq 0 \]; then\s+git [^\n]*merge-base --is-ancestor "\$m" origin/main',
                     bauen)
    assert re.search(r"docker run [^\n]*--network none", bauen)
    # Ein Abbild wird nie ueberschrieben.
    assert re.search(r'\[ -e "\$ZIEL" \] && halt', bauen)


def test_das_image_traegt_weder_repository_noch_fall():
    workshop = _text("Dockerfile")
    kopiert = re.findall(r"^COPY (.+)$", workshop, re.M)
    quellen = {teil for zeile in kopiert for teil in zeile.split()[:-1]}
    assert quellen == {"requirements.txt", "requirements-dev.txt", "pyproject.toml",
                       "deploy/workshop/wsl.conf", "deploy/workshop/profil.sh",
                       "deploy/workshop/einrichten.sh"}
    assert re.search(r"^USER plv", workshop, re.M)


def test_windows_skript_ist_reines_ascii():
    roh = (WORKSHOP / "einrichten.ps1").read_bytes()
    fremd = sorted({b for b in roh if b > 127})
    assert fremd == [], f"Bytes ausserhalb ASCII: {fremd[:5]}"
    # Der Import laeuft nie als Administrator, und nichts wird still ersetzt.
    text = roh.decode("ascii")
    assert "--unregister" in text and text.index("-not $Ersetzen") < text.index("--unregister")


@pytest.mark.parametrize("skript", ["einrichten.sh", "abbild_bauen.sh"])
def test_shell_skripte_sind_syntaktisch_gueltig(skript):
    lauf = subprocess.run(["bash", "-n", str(WORKSHOP / skript)], capture_output=True, text=True)
    assert lauf.returncode == 0, lauf.stderr


def test_ohne_argument_zeigt_plv_einrichten_genau_seinen_kopf():
    """Die Hilfe ist der Kommentarkopf des Skripts, ganz und ohne eine Zeile
    Code — nicht ein von Hand gezaehlter Zeilenbereich, der beim naechsten
    Absatz im Kopf nicht mitwandert (dieselbe Regel wie in deploy/welt)."""
    kopf = []
    for zeile in EINRICHTEN.read_text(encoding="utf-8").splitlines()[1:]:
        if not zeile.startswith("#"):
            break
        kopf.append(re.sub(r"^# ?", "", zeile))
    lauf = subprocess.run(["bash", str(EINRICHTEN)], capture_output=True, text=True)
    assert lauf.returncode == 2 and len(kopf) > 5
    assert lauf.stdout.splitlines() == kopf


# --------------------------------------------------------------------------- #
# plv-einrichten stand: anlegen, nachziehen, anhalten
# --------------------------------------------------------------------------- #

def _git(wo: Path, *args: str) -> str:
    umgebung = dict(os.environ, GIT_AUTHOR_NAME="t", GIT_AUTHOR_EMAIL="t@t.invalid",
                    GIT_COMMITTER_NAME="t", GIT_COMMITTER_EMAIL="t@t.invalid",
                    GIT_CONFIG_GLOBAL=os.devnull, GIT_CONFIG_SYSTEM=os.devnull)
    return subprocess.run(["git", "-C", str(wo), *args], capture_output=True, text=True,
                          check=True, env=umgebung).stdout.strip()


@pytest.fixture
def quelle(tmp_path):
    """Ein kleines Repository mit zwei Marken: v1 und, einen Commit weiter, v2."""
    q = tmp_path / "quelle"
    q.mkdir()
    _git(q, "init", "--quiet", "--initial-branch=main")
    (q / "datei.txt").write_text("eins\n")
    _git(q, "add", "datei.txt")
    _git(q, "commit", "--quiet", "-m", "eins")
    _git(q, "tag", "v1")
    (q / "datei.txt").write_text("zwei\n")
    _git(q, "commit", "--quiet", "-am", "zwei")
    _git(q, "tag", "v2")
    return q


def _stand(heim: Path, *args: str) -> subprocess.CompletedProcess:
    umgebung = dict(os.environ, HOME=str(heim), GIT_CONFIG_GLOBAL=os.devnull,
                    GIT_CONFIG_SYSTEM=os.devnull)
    return subprocess.run(["bash", str(EINRICHTEN), "stand", *args], capture_output=True,
                          text=True, env=umgebung)


def _baum(tmp_path, quelle, marke="v1", *weitere: str) -> Path:
    heim = tmp_path / "heim"
    heim.mkdir(exist_ok=True)
    lauf = _stand(heim, "--quelle", str(quelle), "--marke", marke, "--name", "baum", *weitere)
    assert lauf.returncode == 0, lauf.stderr
    return heim / "baum"


def test_stand_legt_den_baum_auf_der_marke_an(tmp_path, quelle):
    baum = _baum(tmp_path, quelle, "v1", "--herkunft", "https://beispiel.invalid/r.git")
    assert _git(baum, "rev-parse", "HEAD") == _git(quelle, "rev-parse", "v1^{commit}")
    assert (baum / "datei.txt").read_text() == "eins\n"
    assert _git(baum, "branch", "--format=%(refname:short)") == "arbeit"
    assert (baum / ".git" / "plv-marke").read_text().strip() == "v1"
    # Die Quelle des Baus ist auf dem Zielrechner nicht erreichbar: origin
    # zeigt auf die genannte Herkunft, nie auf den Pfad.
    assert _git(baum, "remote", "get-url", "origin") == "https://beispiel.invalid/r.git"
    # Nur die Geschichte der Marke, keine weitere Referenz der Quelle.
    assert _git(baum, "rev-list", "--count", "--all") == "1"


def test_stand_zieht_einen_unberuehrten_baum_auf_die_neue_marke(tmp_path, quelle):
    baum = _baum(tmp_path, quelle, "v1")
    lauf = _stand(tmp_path / "heim", "--quelle", str(quelle), "--marke", "v2", "--name", "baum")
    assert lauf.returncode == 0, lauf.stderr
    assert _git(baum, "rev-parse", "HEAD") == _git(quelle, "rev-parse", "v2^{commit}")
    assert (baum / "datei.txt").read_text() == "zwei\n"
    assert (baum / ".git" / "plv-marke").read_text().strip() == "v2"


@pytest.mark.parametrize("arbeit", ["geaendert", "neu"])
def test_stand_haelt_bei_nicht_committeter_arbeit_und_laesst_sie_stehen(tmp_path, quelle, arbeit):
    baum = _baum(tmp_path, quelle, "v1")
    datei = baum / ("datei.txt" if arbeit == "geaendert" else "notiz.txt")
    datei.write_text("Arbeit des Teilnehmers\n")
    vorher = _git(baum, "rev-parse", "HEAD")
    lauf = _stand(tmp_path / "heim", "--quelle", str(quelle), "--marke", "v2", "--name", "baum")
    assert lauf.returncode == 2
    assert "nicht committete Arbeit" in lauf.stderr
    assert _git(baum, "rev-parse", "HEAD") == vorher
    assert datei.read_text() == "Arbeit des Teilnehmers\n"
    assert (baum / ".git" / "plv-marke").read_text().strip() == "v1"


def test_stand_nimmt_eine_buendeldatei_als_quelle(tmp_path, quelle):
    # Der dokumentierte Weg, einen neuen Stand ohne Netz auf den Rechner zu
    # bringen: git bundle auf dem Quellrechner, die Datei als --quelle.
    buendel = tmp_path / "stand.bundle"
    _git(quelle, "bundle", "create", "--quiet", str(buendel), "v2")
    baum = _baum(tmp_path, quelle, "v1")
    lauf = _stand(tmp_path / "heim", "--quelle", str(buendel), "--marke", "v2", "--name", "baum")
    assert lauf.returncode == 0, lauf.stderr
    assert _git(baum, "rev-parse", "HEAD") == _git(quelle, "rev-parse", "v2^{commit}")


def test_stand_haelt_bei_eigenen_commits(tmp_path, quelle):
    baum = _baum(tmp_path, quelle, "v1")
    (baum / "datei.txt").write_text("eigener Stand\n")
    _git(baum, "commit", "--quiet", "-am", "eigener Commit")
    eigener = _git(baum, "rev-parse", "HEAD")
    lauf = _stand(tmp_path / "heim", "--quelle", str(quelle), "--marke", "v2", "--name", "baum")
    assert lauf.returncode == 2
    assert "eigene Commits" in lauf.stderr and "--name" in lauf.stderr
    assert _git(baum, "rev-parse", "HEAD") == eigener
    assert (baum / "datei.txt").read_text() == "eigener Stand\n"


def test_unbekannte_marke_laesst_den_baum_wie_er_war_und_blockiert_keinen_zweiten_versuch(tmp_path, quelle):
    # Auf einem bestehenden Baum: nichts bewegt sich.
    baum = _baum(tmp_path, quelle, "v1")
    vorher = _git(baum, "rev-parse", "HEAD")
    lauf = _stand(tmp_path / "heim", "--quelle", str(quelle), "--marke", "gibt-es-nicht", "--name", "baum")
    assert lauf.returncode == 2 and "liess sich aus" in lauf.stderr
    assert _git(baum, "rev-parse", "HEAD") == vorher
    assert (baum / ".git" / "plv-marke").read_text().strip() == "v1"
    # Auf einem neuen Baum: Der gescheiterte erste Versuch hinterlaesst einen
    # Baum ohne Commit — der zweite Versuch mit der richtigen Marke gelingt.
    heim = tmp_path / "heim"
    lauf = _stand(heim, "--quelle", str(quelle), "--marke", "gibt-es-nicht", "--name", "zweiter")
    assert lauf.returncode == 2
    lauf = _stand(heim, "--quelle", str(quelle), "--marke", "v2", "--name", "zweiter")
    assert lauf.returncode == 0, lauf.stderr
    assert _git(heim / "zweiter", "rev-parse", "HEAD") == _git(quelle, "rev-parse", "v2^{commit}")


def test_stand_legt_keinen_baum_ueber_ein_fremdes_verzeichnis(tmp_path, quelle):
    heim = tmp_path / "heim"
    (heim / "baum").mkdir(parents=True)
    (heim / "baum" / "fremd.txt").write_text("gehoert jemand anderem\n")
    lauf = _stand(heim, "--quelle", str(quelle), "--marke", "v1", "--name", "baum")
    assert lauf.returncode == 2 and "kein Git-Baum" in lauf.stderr
    assert sorted(p.name for p in (heim / "baum").iterdir()) == ["fremd.txt"]


def test_stand_nimmt_keinen_namen_der_das_heimatverzeichnis_verlaesst(tmp_path, quelle):
    heim = tmp_path / "heim"
    heim.mkdir()
    lauf = _stand(heim, "--quelle", str(quelle), "--marke", "v1", "--name", "../draussen")
    assert lauf.returncode == 2 and "--name" in lauf.stderr
    assert not (tmp_path / "draussen").exists()
