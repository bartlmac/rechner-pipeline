"""Der Anker bindet eine Reihe und ein ganzes Paket — Angriffsrunde nach T27.

Die Klasse: Ein externer Bezug schuetzt nur, was er nennt, und nur auf
den Bytes, auf denen geprueft wird. Die Ankerreihe wurde nie als Reihe
gelesen (eine verankerte Zeile liess sich umschreiben und neu verankern),
der Konsument pruefte Kette und Anker auf zwei Lesungen, Bericht und
Seite hingen nur an stand.json, und ein Anker im Bauort des Exports
verschwand mit ihm.

Knoten: system/betrieb
"""

from __future__ import annotations

import datetime as dt
import hashlib
import json
import sys
from pathlib import Path

import pytest

from tests.freigabe_testschluessel import zeichne_neu

from rechner_pipeline.betrieb import seite as st
from rechner_pipeline.betrieb.tageslauf import EXIT_OK, tageslauf
from rechner_pipeline.models import anker as ak
from tests.test_betrieb_seite import _ablage

REPO_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO_ROOT / "werkzeuge"))
import falldaten as fd  # noqa: E402


@pytest.fixture()
def gefuehrt(tmp_path):
    ablage = _ablage(tmp_path / "plv")
    assert tageslauf(ablage, dt.date(2026, 2, 3))[0] == EXIT_OK
    return ablage


def _schreibe_letzte_zeile_um(protokoll: Path) -> None:
    """Die letzte Zeile umgeschrieben, die Kette bleibt heil (die letzte
    Zeile hat keinen Nachfolger, der sie bindet). Geaendert wird ein Feld,
    das nicht aus dem Stand nachgerechnet wird — so sieht es allein die
    Reihe der Anker. Neu gezeichnet mit dem Betriebsschluessel (Runde C):
    Gegenstand ist die Reihe, nicht die Signatur — der Faelscher hier hat
    den Schluessel."""
    zeilen = protokoll.read_text(encoding="utf-8").split("\n")
    zeilen = [z for z in zeilen if z.strip()]
    letzte = json.loads(zeilen[-1])
    letzte["image_tag"] = "umgeschrieben"
    zeilen[-1] = json.dumps(zeichne_neu(letzte), ensure_ascii=False, sort_keys=True)
    protokoll.chmod(0o644)
    protokoll.write_text("\n".join(zeilen) + "\n", encoding="utf-8")


def test_eine_verankerte_zeile_laesst_sich_nicht_umschreiben_und_neu_verankern(gefuehrt, tmp_path):
    """Mutationsprobe: pruefe_reihe im Export und in pruefe nicht rufen -> rot."""
    anker = tmp_path / "anker"
    st.stands_paket(gefuehrt, tmp_path / "p1", anker_verzeichnis=anker)
    _schreibe_letzte_zeile_um(gefuehrt.protokoll_pfad)
    with pytest.raises(st.SeiteError, match="nicht mehr im Protokoll"):
        st.stands_paket(gefuehrt, tmp_path / "p2", anker_verzeichnis=anker)
    assert len(ak.lies_anker(anker / ak.ANKER_DATEI)) == 1


def test_der_konsument_liest_die_reihe(gefuehrt, tmp_path, monkeypatch):
    """Auch wenn ein Export die Reihe nicht prueft: der Konsument tut es."""
    anker = tmp_path / "anker"
    st.stands_paket(gefuehrt, tmp_path / "p1", anker_verzeichnis=anker)
    _schreibe_letzte_zeile_um(gefuehrt.protokoll_pfad)
    monkeypatch.setattr(st, "pruefe_reihe", lambda *a, **k: None)
    paket = st.stands_paket(gefuehrt, tmp_path / "p2", anker_verzeichnis=anker)
    monkeypatch.undo()
    with pytest.raises(fd.FalldatenFehler, match="nicht mehr im Protokoll"):
        fd.betrieb(paket, anker / ak.ANKER_DATEI)


def _faelsche_paket(paket: Path) -> bytes:
    """Letzte Zeile, stand.json-Hash — alles, was der Erzeuger selbst
    schreibt. Rueckgabe: die echten Protokollbytes."""
    echt = (paket / "protokoll.jsonl").read_bytes()
    _schreibe_letzte_zeile_um(paket / "protokoll.jsonl")
    stand = json.loads((paket / "stand.json").read_text(encoding="utf-8"))
    stand["dateien"]["protokoll.jsonl"] = hashlib.sha256(
        (paket / "protokoll.jsonl").read_bytes()).hexdigest()
    (paket / "stand.json").chmod(0o644)
    (paket / "stand.json").write_text(json.dumps(stand, sort_keys=True), encoding="utf-8")
    return echt


def test_die_ankerpruefung_urteilt_ueber_die_uebergebenen_bytes(gefuehrt, tmp_path):
    """Isoliert: Die Platte traegt das echte Protokoll, uebergeben werden
    gefaelschte Bytes — geprueft werden muss, was uebergeben wurde, nicht
    eine zweite Lesung. Mutationsprobe: in _pruefe_anker den Text nicht
    weiterreichen -> rot."""
    anker = tmp_path / "anker"
    paket = st.stands_paket(gefuehrt, tmp_path / "p", anker_verzeichnis=anker)
    stand = json.loads((paket / "stand.json").read_text(encoding="utf-8"))
    echt = (paket / "protokoll.jsonl").read_bytes()
    fd._pruefe_anker(paket, stand, anker / ak.ANKER_DATEI, None, echt)   # Positivkontrolle
    gefaelscht = echt.rstrip(b"\n") + b" \n"
    with pytest.raises(fd.FalldatenFehler):
        fd._pruefe_anker(paket, stand, anker / ak.ANKER_DATEI, None, gefaelscht)


def test_kette_und_anker_laufen_auf_einer_lesung(gefuehrt, tmp_path, monkeypatch):
    """Der Angreifer tauscht beim Oeffnen der Ankerdatei die echten Bytes
    zurueck ins Paket. Mutationsprobe: in _pruefe_anker den Text nicht
    weiterreichen -> rot."""
    anker = tmp_path / "anker"
    paket = st.stands_paket(gefuehrt, tmp_path / "p", anker_verzeichnis=anker)
    echt = _faelsche_paket(paket)
    lies = ak.lies_anker

    def tauscht(pfad):
        (paket / "protokoll.jsonl").write_bytes(echt)
        return lies(pfad)

    monkeypatch.setattr(ak, "lies_anker", tauscht)
    with pytest.raises(fd.FalldatenFehler):
        fd.betrieb(paket, anker / ak.ANKER_DATEI)


@pytest.mark.parametrize("datei", ["index.html", "bericht"])
def test_jede_mitgelieferte_datei_haengt_am_anker(gefuehrt, tmp_path, datei):
    """Mutationsprobe: dateien_sha256 im Konsumenten nicht vergleichen -> rot."""
    anker = tmp_path / "anker"
    paket = st.stands_paket(gefuehrt, tmp_path / "p", anker_verzeichnis=anker)
    assert fd.betrieb(paket, anker / ak.ANKER_DATEI)["vorhanden"]   # Positivkontrolle
    stand = json.loads((paket / "stand.json").read_text(encoding="utf-8"))
    name = datei if datei == "index.html" else next(
        n for n in stand["dateien"] if n.startswith("bestandsbericht"))
    ziel = paket / name
    ziel.chmod(0o644)
    ziel.write_bytes(ziel.read_bytes() + b"<!-- gefaelscht -->")
    stand["dateien"][name] = hashlib.sha256(ziel.read_bytes()).hexdigest()
    (paket / "stand.json").chmod(0o644)
    (paket / "stand.json").write_text(json.dumps(stand, sort_keys=True), encoding="utf-8")
    with pytest.raises(fd.FalldatenFehler, match="Dateiliste"):
        fd.betrieb(paket, anker / ak.ANKER_DATEI)


def test_ein_anker_im_bauort_des_exports_wird_abgewiesen(gefuehrt, tmp_path):
    with pytest.raises(st.SeiteError, match="Bauort"):
        st.stands_paket(gefuehrt, tmp_path / "paket",
                        anker_verzeichnis=tmp_path / ".paket.im-bau" / "anker")
