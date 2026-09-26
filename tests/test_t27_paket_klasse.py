"""Paket, Anker und Eingabenbindung — Pruefrunde T27, Befunde 08, 09 und 11.

Die Klasse: Geprueft wird das Pfadobjekt, das geschrieben wird (nicht nur
sein Verzeichnis); ein Export teilt sich die Transaktion mit dem Lauf,
den er bezeugt; und jeder Unterleser eines Gates geht durch dieselbe
Bindung wie der Beleg.

Knoten: system/betrieb
"""

from __future__ import annotations

import ast
import datetime as dt
import fcntl
import hashlib
import json
import shutil
import sys
from pathlib import Path

import pytest

from rechner_pipeline.betrieb import seite as st
from rechner_pipeline.betrieb.tageslauf import EXIT_OK, tageslauf
from rechner_pipeline.models import anker as ak
from tests.test_betrieb_seite import _ablage

REPO_ROOT = Path(__file__).resolve().parents[1]


@pytest.fixture()
def gefuehrt(tmp_path):
    ablage = _ablage(tmp_path / "plv")
    assert tageslauf(ablage, dt.date(2026, 2, 3))[0] == EXIT_OK
    return ablage


# --------------------------------------------------------------------------- #
# T27-09: die Ankerdatei ist das Pfadobjekt, das geprueft wird
# --------------------------------------------------------------------------- #


def test_ein_dateisymlink_als_anker_wird_vor_dem_export_abgewiesen(gefuehrt, tmp_path):
    """Externes Verzeichnis, darin anker.jsonl als Symlink in die Ablage:
    Der Export folgte ihm und schrieb in die Ablage. Mutationsprobe: die
    Dateipruefung in ankerziel_fehler entfernen -> rot."""
    ablage = gefuehrt
    anker = tmp_path / "anker"
    anker.mkdir()
    ziel_in_ablage = ablage.wurzel / "versteckt.jsonl"
    (anker / ak.ANKER_DATEI).symlink_to(ziel_in_ablage)
    with pytest.raises(st.SeiteError, match="Symlink"):
        st.stands_paket(ablage, tmp_path / "paket", anker_verzeichnis=anker)
    assert not ziel_in_ablage.exists() and not (tmp_path / "paket").exists()


def test_ein_dateisymlink_in_ein_paket_loescht_keine_ankerhistorie(gefuehrt, tmp_path):
    """Der zweite Fall des Gutachters: Symlink auf eine Datei in einem
    vorhandenen Paket — der Reexport loeschte das Paket und mit ihm zwei
    belegte Ankerzeilen. Jetzt: abgewiesen, das Paket bleibt."""
    ablage = gefuehrt
    paket = st.stands_paket(ablage, tmp_path / "paket", anker_verzeichnis=tmp_path / "anker-echt")
    st.stands_paket(ablage, tmp_path / "paket", anker_verzeichnis=tmp_path / "anker-echt")
    saetze_vorher = ak.lies_anker(tmp_path / "anker-echt" / ak.ANKER_DATEI)
    assert len(saetze_vorher) == 2
    fremd = tmp_path / "anker-fremd"
    fremd.mkdir()
    (fremd / ak.ANKER_DATEI).symlink_to(paket / "stand.json")
    with pytest.raises(st.SeiteError, match="Symlink"):
        st.stands_paket(ablage, tmp_path / "paket", anker_verzeichnis=fremd)
    assert (paket / "stand.json").is_file()
    assert ak.lies_anker(tmp_path / "anker-echt" / ak.ANKER_DATEI) == saetze_vorher


def test_ein_gewoehnlicher_anker_bleibt_exportierbar(gefuehrt, tmp_path):
    """Positivkontrolle: gewoehnliche Datei im externen Verzeichnis."""
    ablage = gefuehrt
    st.stands_paket(ablage, tmp_path / "paket", anker_verzeichnis=tmp_path / "anker")
    assert (tmp_path / "anker" / ak.ANKER_DATEI).is_file()
    assert len(ak.lies_anker(tmp_path / "anker" / ak.ANKER_DATEI)) == 1


# --------------------------------------------------------------------------- #
# T27-11: der Export laeuft unter der Lauf-Sperre
# --------------------------------------------------------------------------- #


def test_der_export_laeuft_nicht_neben_einem_tageslauf(gefuehrt, tmp_path):
    """Haelt ein Lauf die Sperre, wartet der Export nicht und mischt nichts
    — er bricht ab, mit Meldung; danach laeuft er. Mutationsprobe: die
    Sperre im Export entfernen -> rot."""
    ablage = gefuehrt
    with open(ablage.sperre, "a+") as fremd:
        fcntl.flock(fremd.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)
        with pytest.raises(st.SeiteError, match="Sperre"):
            st.stands_paket(ablage, tmp_path / "paket", anker_verzeichnis=tmp_path / "anker")
        assert not (tmp_path / "paket").exists()
    paket = st.stands_paket(ablage, tmp_path / "paket", anker_verzeichnis=tmp_path / "anker")
    assert (paket / "stand.json").is_file()


# --------------------------------------------------------------------------- #
# T27-08: jeder CSV-Unterleser der Fuehrungsprobe geht durch die Bindung
# --------------------------------------------------------------------------- #


def test_jeder_csv_unterleser_der_fuehrungsprobe_uebergibt_die_bindung():
    """Ratsche (statisch, benannt als solche): ``_lies_csv`` ohne
    ``bindung`` oeffnet die Datei ein zweites Mal — das war der Befund. Ein
    Verhaltenstest an der tatsaechlichen Oeffnung fehlt hier noch; er
    braucht die Fuehrungsprobe-Welt (Uebernahme, Lauf, Spez, Suite)."""
    quelle = (REPO_ROOT / "src" / "rechner_pipeline" / "gates" / "fuehrungsprobe.py").read_text(encoding="utf-8")
    baum = ast.parse(quelle)
    aufrufe = [
        knoten for knoten in ast.walk(baum)
        if isinstance(knoten, ast.Call)
        and isinstance(knoten.func, ast.Name) and knoten.func.id == "_lies_csv"
    ]
    assert len(aufrufe) >= 2, "die Fuehrungsprobe liest keine CSV mehr?"
    for aufruf in aufrufe:
        assert len(aufruf.args) >= 3 or any(k.arg == "bindung" for k in aufruf.keywords), (
            f"_lies_csv in Zeile {aufruf.lineno} ohne Bindung")


# --------------------------------------------------------------------------- #
# T27-10: die mitgelieferten Abschluesse haengen am verankerten Hash
# --------------------------------------------------------------------------- #

sys.path.insert(0, str(REPO_ROOT / "werkzeuge"))
import falldaten as fd  # noqa: E402


def _paketkopie(paket: Path, ziel: Path):
    shutil.copytree(paket, ziel)
    stand = json.loads((ziel / "stand.json").read_text(encoding="utf-8"))
    return ziel, stand


def _schreibe_stand(kopie: Path, stand: dict) -> None:
    (kopie / "stand.json").write_text(
        json.dumps(stand, ensure_ascii=False, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def test_eine_getauschte_abschlussdatei_mit_nachgezogenem_hash_wird_abgewiesen(gefuehrt, tmp_path):
    """Der Gutachter: Abschluss (16 Vertraege) durch eine gueltige leere
    Tabelle ersetzt, nur stand.json.dateien nachgezogen — das Paket ging
    durch. Mutationsprobe: _pruefe_abschluesse_gegen_das_protokoll nicht
    rufen -> rot."""
    from rechner_pipeline.bestand.parquet_io import read_portfolio, write_portfolio

    paket = st.stands_paket(gefuehrt, tmp_path / "paket", anker_verzeichnis=tmp_path / "anker")
    kopie, stand = _paketkopie(paket, tmp_path / "kopie")
    fd._pruefe_stands_paket(kopie, stand, stand.get("provenienz") or {})   # Positivkontrolle
    namen = [n for n in stand["dateien"] if n.startswith("abschluesse/")]
    assert namen, "das Paket liefert keinen Abschluss mit — der Test saehe nichts"
    name = namen[-1]
    tabelle = read_portfolio(kopie / name)
    assert len(tabelle) > 0
    write_portfolio(tabelle.iloc[0:0], kopie / name)
    stand["dateien"][name] = hashlib.sha256((kopie / name).read_bytes()).hexdigest()
    _schreibe_stand(kopie, stand)
    with pytest.raises(fd.FalldatenFehler, match="Protokollzeile"):
        fd._pruefe_stands_paket(kopie, stand, stand.get("provenienz") or {})


def test_entfernte_abschlussdateien_werden_vermisst(gefuehrt, tmp_path):
    paket = st.stands_paket(gefuehrt, tmp_path / "paket", anker_verzeichnis=tmp_path / "anker")
    kopie, stand = _paketkopie(paket, tmp_path / "kopie")
    namen = [n for n in stand["dateien"] if n.startswith("abschluesse/")]
    assert namen
    for name in namen:
        (kopie / name).unlink()
        del stand["dateien"][name]
    _schreibe_stand(kopie, stand)
    with pytest.raises(fd.FalldatenFehler, match="fehlt im Paket"):
        fd._pruefe_stands_paket(kopie, stand, stand.get("provenienz") or {})


def test_ein_hardlink_als_anker_wird_vor_dem_export_abgewiesen(gefuehrt, tmp_path):
    """Angriffsrunde (Betrieb, dritte Runde): anker.jsonl als Hardlink auf
    das Tagesprotokoll — der Export schrieb in die Protokollkette.
    Mutationsprobe: die nlink-Pruefung entfernen -> rot."""
    import os

    ablage = gefuehrt
    anker = tmp_path / "anker"
    anker.mkdir()
    vorher = ablage.protokoll_pfad.read_bytes()
    os.link(ablage.protokoll_pfad, anker / ak.ANKER_DATEI)
    with pytest.raises(st.SeiteError, match="Hardlink"):
        st.stands_paket(ablage, tmp_path / "paket", anker_verzeichnis=anker)
    assert ablage.protokoll_pfad.read_bytes() == vorher
