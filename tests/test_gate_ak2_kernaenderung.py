"""A-K2: die Abnahme des Kernstands — Belegvertrag und Pruefer.

Entscheid des Maintainers 2026-09-16, formell in den Ablauf eingepflegt am
2026-10-01 (ADR-018, Nachtrag 2026-10-01; der Ablauf selbst steht in
``tests/test_kernabnahme_ak2.py``). Bis dahin war das folgenreichste, was
am Zielsystem geschieht — eine Formelaenderung, ein verschobener
Referenzwert — nur durch Commit-Disziplin geregelt (Abnahme-Protokoll in
``kern/__init__``): keine Zeichnung, kein Schluessel, kein Snapshot.

Der Kern der Regressionsregel steht in
``test_eine_stichprobe_ist_keine_regression``: Wer nur eine Stichprobe
rechnet, findet den Fehler nicht, der einen von tausend Vertraegen trifft —
und genau der ist der gesuchte. Sie gilt fuer jeden ECHTEN Regressionsbeleg;
bis zum Produzenten steht an seiner Stelle die benannte Ausnahme.

Seit Schema 3 des Aenderungsbelegs (2026-10-01) gilt geaendert: Ein
unveraenderter Kern ist ein gueltiger Beleg (jeder Fall traegt sein A-K2),
und ``dirty`` sperrt nicht mehr die qualitative Pruefung, sondern die
Regression.

Knoten: system/entscheid
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from rechner_pipeline.fall import FALL_SCOPES
from rechner_pipeline.models.belegrollen import belegrollen
from rechner_pipeline.gates import kernstand_belegen
from rechner_pipeline.gates._provenienz import (
    PRODUKTIVER_ZWEIG,
    git_stand,
)
from rechner_pipeline.gates.gate_entscheid import (
    KERN_AENDERUNG_SCHEMA_VERSION,
    KERN_REGRESSION_SCHEMA_VERSION,
    kern_modul_hash,
    pruefe_kernaenderung,
    pruefe_kernregression,
    referenzwerte_hash,
)
from rechner_pipeline.models.zeichnung import GUELTIGE_GATES

REPO = Path(__file__).resolve().parents[1]

NULL = "0" * 64

#: Der lebende Git-Stand. Die POSITIVEN Proben brauchen ihn, weil der
#: Aenderungsbeleg gegen ihn nachgerechnet wird. Fehlt Git, wird
#: ausdruecklich uebersprungen — ein gruener Test waere hier eine Luege
#: ueber die Umgebung.
_STAND = git_stand(REPO)
ohne_git = pytest.mark.skipif(
    _STAND.get("commit") == "unbekannt",
    reason=f"kein lesbarer Git-Stand im Repo ({_STAND})",
)


def _aenderung(**abweichend):
    """Ein echter Aenderungsbeleg dieses Repos — vom lebenden Commit aus
    (die CI klont flach; ein frueherer Commit ist dort nicht da)."""
    daten = kernstand_belegen.baue_aenderungsbeleg(REPO, "HEAD", "Probe des Belegvertrags")
    daten.update(abweichend)
    return daten


def _bindung():
    """Die Bindungsfelder eines Uebergangs, fuer die Regressionsproben; der
    Arbeitsbaum beim Belegen sauber (sonst greift die dirty-Regel)."""
    return {
        "schema_version": KERN_AENDERUNG_SCHEMA_VERSION,
        "von_version": "3.5.0",
        "nach_version": "3.6.0",
        "kern_sha256": "c" * 64,
        "kern_alt_sha256": "b" * 64,
        "git": {"dirty": "nein"},
    }


def _regression(**abweichend):
    daten = {
        "schema_version": KERN_REGRESSION_SCHEMA_VERSION,
        "von_version": "3.5.0",
        "nach_version": "3.6.0",
        "bestand_sha256": "a" * 64,
        "kern_sha256": "c" * 64,
        "kern_alt_sha256": "b" * 64,
        "vertraege_gesamt": 834,
        "vertraege_geprueft": 834,
        "abweichungen": [
            {
                "police_id": "P-0001",
                "groesse": "dk",
                "vorher": 1000.0,
                "nachher": 1000.5,
                "differenz": 0.5,
            }
        ],
    }
    daten.update(abweichend)
    return daten


def _schreibe(pfad: Path, daten) -> Path:
    pfad.parent.mkdir(parents=True, exist_ok=True)
    pfad.write_text(json.dumps(daten), encoding="utf-8")
    return pfad


# --------------------------------------------------------------- Vokabel


def test_ak2_ist_zeichenbar_und_hat_einen_belegvertrag():
    assert "A-K2" in GUELTIGE_GATES
    for scope in FALL_SCOPES:
        assert belegrollen("A-K2", scope) == ["kernaenderung", "regression"]


def test_die_regression_ist_pflicht_in_jedem_scope():
    """Die eigentliche Entscheidung: nicht 'ausweisen', sondern 'erzwingen'.

    Derselbe Fehler war A-M4 im Bestands-Scope schon einmal unterlaufen
    (T21-02/T22-01) — ein optionaler Beleg nimmt jedes Teilprofil an. Bis
    zum Produzenten belegt die Rolle die Ausnahme, sie entfaellt nicht.
    """
    for scope in FALL_SCOPES:
        assert "regression" in belegrollen("A-K2", scope)


# ------------------------------------------------- Beleg der Aenderung


@ohne_git
def test_ein_gueltiger_aenderungsbeleg_geht_durch(tmp_path):
    pfad = _schreibe(tmp_path / "aenderung.json", _aenderung())
    assert pruefe_kernaenderung(pfad, tmp_path, repo_root=REPO) == []


def test_fehlende_datei_ist_ein_befund(tmp_path):
    assert pruefe_kernaenderung(
        tmp_path / "fehlt.json", tmp_path, repo_root=REPO
    ) == ["Datei fehlt"]


@ohne_git
@pytest.mark.parametrize(
    "abweichend, erwartet",
    [
        ({"schema_version": 2}, "schema_version"),
        ({"von_version": "99.0.0"}, "laeuft nicht abwaerts"),
        ({"von_version": "drei"}, "von_version muss eine Version"),
        ({"nach_version": "0.0.1"}, "nicht die Version, die der Kern traegt"),
        ({"kern_sha256": NULL}, "kern_sha256 stimmt nicht"),
        ({"kern_sha256": "kurz"}, "kern_sha256 fehlt oder ist kein SHA-256"),
        ({"referenzwerte_sha256": NULL}, "referenzwerte_sha256 stimmt nicht"),
        ({"geaenderte_referenzwerte": "eine"}, "geaenderte_referenzwerte"),
        ({"begruendung": "   "}, "begruendung fehlt"),
        ({"kern_alt_sha256": "kurz"}, "kern_alt_sha256 fehlt"),
        ({"git": "keins"}, "git fehlt oder ist kein Objekt"),
    ],
)
def test_der_aenderungsbeleg_faengt_die_naheliegenden_faelschungen(
    tmp_path, abweichend, erwartet
):
    pfad = _schreibe(tmp_path / "aenderung.json", _aenderung(**abweichend))
    fehler = pruefe_kernaenderung(pfad, tmp_path, repo_root=REPO)
    assert any(erwartet in f for f in fehler), (abweichend, fehler)


@ohne_git
def test_ohne_repo_root_ist_der_kern_nicht_pruefbar_und_das_steht_da(tmp_path):
    """Kein stiller Durchlauf: Fehlt die Wurzel, sagt der Befund das."""
    pfad = _schreibe(tmp_path / "aenderung.json", _aenderung())
    fehler = pruefe_kernaenderung(pfad, tmp_path, repo_root=None)
    assert any("nicht pruefbar" in f for f in fehler), fehler


# ------------------------------------------------------ Der Modulhash


def test_der_kernhash_sieht_jede_aenderung(tmp_path):
    """Positivkontrolle des Detektors: Ein Hash, der sich nie aendert,
    bezeugt nichts. Geprueft wird Inhalt UND Name — und seit 2026-10-01
    auch Dateien, die kein Python sind (``tafeln.xml``)."""
    paket = tmp_path / "src" / "rechner_pipeline" / "kern"
    paket.mkdir(parents=True)
    (paket / "a.py").write_text("x = 1\n", encoding="utf-8")
    vorher = kern_modul_hash(tmp_path)
    assert vorher is not None

    (paket / "a.py").write_text("x = 2\n", encoding="utf-8")
    assert kern_modul_hash(tmp_path) != vorher, "Inhaltsaenderung bleibt unsichtbar"

    (paket / "a.py").write_text("x = 1\n", encoding="utf-8")
    assert kern_modul_hash(tmp_path) == vorher, "Ruecknahme fuehrt nicht zurueck"

    (paket / "tafeln.xml").write_text("<t/>\n", encoding="utf-8")
    assert kern_modul_hash(tmp_path) != vorher, "Rechnungsgrundlagen bleiben unsichtbar"
    (paket / "tafeln.xml").unlink()

    (paket / "__pycache__").mkdir()
    (paket / "__pycache__" / "a.cpython-311.pyc").write_bytes(b"\x00")
    assert kern_modul_hash(tmp_path) == vorher, "der Bytecode-Cache ist kein Kern"

    (paket / "a.py").rename(paket / "b.py")
    assert kern_modul_hash(tmp_path) != vorher, "Umbenennung bleibt unsichtbar"


def test_ohne_kernpaket_gibt_es_keinen_hash(tmp_path):
    assert kern_modul_hash(tmp_path) is None
    assert referenzwerte_hash(tmp_path) is None


# ---------------------------------------------- Beleg der Regression


def test_ein_gueltiger_regressionsbeleg_geht_durch(tmp_path):
    pfad = _schreibe(tmp_path / "regression.json", _regression())
    assert pruefe_kernregression(pfad, tmp_path, aenderung=_bindung()) == []


def test_eine_stichprobe_ist_keine_regression(tmp_path):
    """DIE Regel des Regressionsbelegs.

    833 von 834 gerechnet heisst: Der eine, auf den es ankommt, kann der
    ungerechnete sein. Ein Beleg, der das zulaesst, bezeugt ein gutes
    Gefuehl, keine Regression.
    """
    pfad = _schreibe(
        tmp_path / "regression.json", _regression(vertraege_geprueft=833)
    )
    fehler = pruefe_kernregression(pfad, tmp_path, aenderung=_bindung())
    assert any("Stichprobe ist keine Regression" in f for f in fehler), fehler


@pytest.mark.parametrize(
    "abweichend, erwartet",
    [
        ({"schema_version": 99}, "schema_version"),
        ({"vertraege_gesamt": 0, "vertraege_geprueft": 0}, "bezeugt nichts"),
        ({"vertraege_geprueft": -1}, "nicht-negative ganze Zahl"),
        ({"vertraege_geprueft": True}, "ganze Zahl"),
        ({"bestand_sha256": "kurz"}, "bestand_sha256"),
        ({"abweichungen": {}}, "keine Liste"),
        ({"abweichungen": [{"police_id": "P"}]}, "fehlt"),
        ({"nach_version": "9.9.9"}, "anderen Uebergang"),
    ],
)
def test_der_regressionsbeleg_faengt_die_naheliegenden_faelschungen(
    tmp_path, abweichend, erwartet
):
    pfad = _schreibe(tmp_path / "regression.json", _regression(**abweichend))
    fehler = pruefe_kernregression(pfad, tmp_path, aenderung=_bindung())
    assert any(erwartet in f for f in fehler), (abweichend, fehler)


def test_eine_differenz_die_nicht_die_differenz_ist_faellt_auf(tmp_path):
    """Der Beleg darf sich nicht selbst widersprechen: Wer vorher,
    nachher und eine dritte Zahl schreibt, koennte die dritte schoenen."""
    pfad = _schreibe(
        tmp_path / "regression.json",
        _regression(
            abweichungen=[
                {
                    "police_id": "P-0001",
                    "groesse": "dk",
                    "vorher": 1000.0,
                    "nachher": 1500.0,
                    "differenz": 0.5,
                }
            ]
        ),
    )
    fehler = pruefe_kernregression(pfad, tmp_path, aenderung=_bindung())
    assert any("ist nicht" in f and "nachher - vorher" in f for f in fehler), fehler


def test_die_regression_muss_zum_selben_uebergang_gehoeren(tmp_path):
    """Sonst legt man die Regression eines alten Uebergangs neben eine
    neue Aenderung — beide fuer sich stimmig, zusammen eine Luege."""
    pfad = _schreibe(
        tmp_path / "regression.json", _regression(von_version="3.0.0")
    )
    fehler = pruefe_kernregression(pfad, tmp_path, aenderung=_bindung())
    assert any("anderen Uebergang" in f for f in fehler), fehler


def test_die_regression_ist_an_dieselben_kernhashes_gebunden(tmp_path):
    """Versionsstrings sind Behauptungen, Hashes nicht. Eine Regression
    mit fremdem Kern-Hash gehoert zu einem anderen Uebergang."""
    pfad = _schreibe(
        tmp_path / "regression.json", _regression(kern_alt_sha256="e" * 64)
    )
    fehler = pruefe_kernregression(pfad, tmp_path, aenderung=_bindung())
    assert any("kern_alt_sha256" in f and "anderen Uebergang" in f
               for f in fehler), fehler


def test_eine_regression_gegen_einen_schmutzigen_arbeitsbaum_sperrt(tmp_path):
    """Eine Regression gegen uncommittete Aenderungen ist nicht
    reproduzierbar — also bezeugt sie nichts. Die Regel stand bis
    2026-10-01 im Aenderungsbeleg und sperrte damit auch die qualitative
    Pruefung; sie gehoert zur Regression."""
    pfad = _schreibe(tmp_path / "regression.json", _regression())
    schmutzig = {**_bindung(), "git": {"dirty": "ja"}}
    fehler = pruefe_kernregression(pfad, tmp_path, aenderung=schmutzig)
    assert any("nicht reproduzierbar" in f for f in fehler), fehler


# ------------------------------------- Bindung an den abgenommenen Stand


@ohne_git
def test_ein_zweig_neben_dem_abgenommenen_stand_sperrt(tmp_path):
    """Enthaelt der lebende Stand den zuletzt abgenommenen Kernstand nicht,
    mischt die Differenz die eigene Aenderung mit einer fremden."""
    beleg = _aenderung()
    danebenliegend = dict(beleg["git"], merge_base="c" * 40)
    pfad = _schreibe(tmp_path / "aenderung.json", _aenderung(git=danebenliegend))
    fehler = pruefe_kernaenderung(pfad, tmp_path, repo_root=REPO)
    assert any("merge_base != referenz_commit" in f for f in fehler), fehler


@ohne_git
def test_der_beleg_wird_gegen_den_lebenden_git_stand_gehalten(tmp_path):
    """Innere Stimmigkeit beweist nichts: Ein Beleg, der einen fremden,
    in sich schluessigen Commit nennt, muss auffallen — geprueft wird
    ``aktuell`` gegen den gegenwaertigen Commit des Arbeitsbaums."""
    beleg = _aenderung()
    fremd = dict(beleg["git"], aktuell="d" * 40)
    pfad = _schreibe(tmp_path / "aenderung.json", _aenderung(git=fremd))
    fehler = pruefe_kernaenderung(pfad, tmp_path, repo_root=REPO)
    assert any("gegenwaertige Commit" in f for f in fehler), fehler


@ohne_git
def test_dirty_sperrt_die_qualitative_pruefung_nicht(tmp_path):
    """Die Sicht zeigt nicht committete Aenderungen ausdruecklich; die
    Sperre gehoert zur Regression (oben)."""
    beleg = _aenderung()
    assert "dirty" in beleg["git"]
    pfad = _schreibe(tmp_path / "aenderung.json", beleg)
    assert pruefe_kernaenderung(pfad, tmp_path, repo_root=REPO) == []


def test_der_produktive_zweig_ist_der_ferne_ref():
    """Entscheid des Maintainers 2026-09-16: Was geteilt ist, ist
    produktiv.

    Ein lokaler ``main``-Ref kann hinter dem fernen liegen, ohne dass es
    auffaellt. Seit 2026-10-01 nennt der Beleg den zuletzt abgenommenen
    Kernstand ausdruecklich (``--von``); wer ``origin/main`` meint, nennt
    den fernen Ref.
    """
    assert PRODUKTIVER_ZWEIG.startswith("origin/"), (
        "ein lokaler Ref taugt nicht als Massstab fuer 'produktiv'")
