"""Ein Bezug, der Vertrauen stiften soll, liegt ausserhalb des Schreibers.

Was der schreibende Prozess selbst umschreiben kann, belegt nichts. Die
Regel galt bisher fuer alles, was eine ZEICHNUNG autorisiert — Ordnung,
Freigabeschluessel, Mandat (ADR-018) — und war dafuer zweimal
implementiert: einmal als ``ausserhalb_des_falls``, einmal woertlich in
``lade_zeichnungsordnung``. Der ANKER eines Stands-Pakets, der genau
derselben Regel folgt, war von keiner der beiden gedeckt.

Befund T26-08 hat gezeigt, was daran haengt: Ein Anker im Paket wird beim
naechsten Export mitgeloescht (gemessen zwei Saetze vorher, einer
nachher, obwohl die Reihe nur wachsen darf), und der Konsument prueft die
Faelschung dann gegen ihre eigene Beilage — eine konsistent von 68 auf
1068 Vertraege umgeschriebene Lieferung kam durch.

Geprueft wird deshalb die REGEL in allen Lagen, in denen sie umgangen
werden kann, und danach ihre Anwendung auf beiden Seiten des Pakets.

Knoten: klv, bu
"""

from __future__ import annotations

import datetime as dt
import json
import os
from pathlib import Path

import pytest

from rechner_pipeline.betrieb import seite as st
from rechner_pipeline.betrieb.tageslauf import EXIT_OK, Ablage, tageslauf
from rechner_pipeline.models.zeichnung import ausserhalb_von


# --------------------------------------------------------------------------- #
# Die Regel selbst — in beide Richtungen
# --------------------------------------------------------------------------- #

def test_die_regel_kennt_jede_lage(tmp_path):
    """Tabelle statt Einzelfall: drinnen, gleich, ueber Umwege drinnen,
    per Symlink drinnen — und die Gegenprobe, die draussen ist.

    Eine Regel, die alles ablehnt, waere von einer richtigen nicht zu
    unterscheiden, solange man nur die Ablehnungen prueft.
    """
    bereich = tmp_path / "bereich"
    (bereich / "tief").mkdir(parents=True)
    (bereich / "datei.txt").write_text("x", encoding="utf-8")
    (bereich / "tief" / "datei.txt").write_text("x", encoding="utf-8")
    draussen = tmp_path / "draussen"
    draussen.mkdir()
    (draussen / "datei.txt").write_text("x", encoding="utf-8")
    # Ein Symlink INNERHALB des Bereichs, der nach aussen zeigt: lexikalisch
    # drinnen, aufgeloest draussen — muss drinnen zaehlen.
    os.symlink(draussen / "datei.txt", bereich / "zeigt_raus.txt")
    # Und einer DRAUSSEN, der nach innen zeigt: lexikalisch draussen,
    # aufgeloest drinnen — muss ebenfalls drinnen zaehlen.
    os.symlink(bereich / "datei.txt", draussen / "zeigt_rein.txt")

    drinnen_faelle = [
        bereich,
        bereich / "datei.txt",
        bereich / "tief" / "datei.txt",
        bereich / "tief" / ".." / "datei.txt",
        bereich / "zeigt_raus.txt",
        draussen / "zeigt_rein.txt",
    ]
    for pfad in drinnen_faelle:
        assert not ausserhalb_von(Path(pfad), bereich), pfad

    assert ausserhalb_von(draussen / "datei.txt", bereich)
    assert ausserhalb_von(bereich / ".." / "draussen" / "datei.txt", bereich)


def test_was_es_nicht_gibt_autorisiert_nichts_darf_aber_ziel_sein(tmp_path):
    """Die zwei Faelle, die frueher verschwommen.

    Ein BELEG, den es nicht gibt, autorisiert nichts — er gilt nicht als
    aussen. Ein VERZEICHNIS, in das erst geschrieben werden soll, gibt es
    bei der Pruefung regelmaessig noch nicht; dort wird der vorhandene
    Anfang des Pfades aufgeloest.
    """
    bereich = tmp_path / "bereich"
    bereich.mkdir()
    fehlt_draussen = tmp_path / "gibt-es-nicht"
    assert not ausserhalb_von(fehlt_draussen, bereich)
    assert ausserhalb_von(fehlt_draussen, bereich, muss_existieren=False)
    # Auch ohne Existenz bleibt drinnen drinnen:
    assert not ausserhalb_von(bereich / "noch-nicht", bereich, muss_existieren=False)


# --------------------------------------------------------------------------- #
# Der Erzeuger: kein Anker im Paket, keiner in der Ablage
# --------------------------------------------------------------------------- #

@pytest.fixture(scope="module")
def gefuehrt(tmp_path_factory):
    from tests.test_betrieb_tageslauf import _kleine_config

    ablage = Ablage(tmp_path_factory.mktemp("plv"))
    ablage.configs.mkdir(parents=True, exist_ok=True)
    ablage.config_pfad.write_text(_kleine_config(), encoding="utf-8")
    assert tageslauf(ablage, dt.date(2026, 2, 3))[0] == EXIT_OK
    return ablage


def _ankerlagen(ablage: Ablage, paket: Path):
    """Jede Lage, in der ein Anker keiner waere — mit sprechendem Namen."""
    return [
        ("im Paket", paket / "anker"),
        ("das Paket selbst", paket),
        ("tief im Paket", paket / "a" / "b"),
        ("ueber einen Umweg im Paket", paket / ".." / paket.name / "anker"),
        ("in der Ablage", ablage.wurzel / "anker"),
        ("die Ablage selbst", ablage.wurzel),
        ("tief in der Ablage", ablage.journal / "anker"),
    ]


def test_der_export_nimmt_keinen_anker_im_eigenen_bereich(gefuehrt, tmp_path):
    """Sieben Lagen, eine Regel — und das vorhandene Paket ueberlebt jede.

    Wichtig ist nicht nur die Ablehnung, sondern ihr ZEITPUNKT: Der Export
    loescht sein Zielverzeichnis, bevor er neu schreibt. Eine Pruefung
    danach haette das alte Paket schon gekostet.
    """
    paket = tmp_path / "paket"
    anker = tmp_path / "anker"
    st.stands_paket(gefuehrt, paket, anker_verzeichnis=anker)
    vorher = sorted(p.name for p in paket.iterdir())

    for was, lage in _ankerlagen(gefuehrt, paket):
        with pytest.raises(st.SeiteError, match="Anker"):
            st.stands_paket(gefuehrt, paket, anker_verzeichnis=lage)
        assert sorted(p.name for p in paket.iterdir()) == vorher, (
            f"{was}: das vorhandene Paket wurde vor der Ablehnung angetastet")


def test_ein_symlink_fuehrt_nicht_am_anker_vorbei(gefuehrt, tmp_path):
    """Lexikalisch draussen, aufgeloest drinnen — die zweite Haelfte der
    Regel. Ohne sie genuegte ein Symlink neben dem Paket."""
    paket = tmp_path / "paket"
    st.stands_paket(gefuehrt, paket, anker_verzeichnis=tmp_path / "anker")
    alias = tmp_path / "sieht-aus-wie-draussen"
    os.symlink(paket, alias)
    with pytest.raises(st.SeiteError, match="Anker"):
        st.stands_paket(gefuehrt, paket, anker_verzeichnis=alias / "anker")


def test_die_ankerhistorie_waechst_ueber_reexporte(gefuehrt, tmp_path):
    """Die Reihe der Anker ist die Geschichte der Auslieferungen.

    Gemessener Befund: zwei Saetze vor dem Reexport, einer danach — weil
    der Anker im Paket lag und mit ihm ersetzt wurde. Ausserhalb kann das
    nicht passieren, und genau das haelt dieser Test fest.
    """
    paket = tmp_path / "paket"
    anker = tmp_path / "anker"
    st.stands_paket(gefuehrt, paket, anker_verzeichnis=anker)
    st.stands_paket(gefuehrt, paket, anker_verzeichnis=anker)
    st.stands_paket(gefuehrt, paket, anker_verzeichnis=anker)
    zeilen = [z for z in (anker / "anker.jsonl").read_text("utf-8").splitlines() if z.strip()]
    assert len(zeilen) == 3, "jeder Export fuegt genau einen Satz an"
    assert all(json.loads(z)["stand"] == "2026-02-03" for z in zeilen)


# --------------------------------------------------------------------------- #
# Der Konsument: eine Beilage ist kein Bezug
# --------------------------------------------------------------------------- #

def test_der_konsument_weist_einen_anker_aus_dem_paket_ab(gefuehrt, tmp_path):
    """Selbst wenn ein Paket mit einem passenden Anker daherkommt: Ein
    Bezug, der mit dem Paket reist, bindet es nicht."""
    import sys

    sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
    from werkzeuge import falldaten as fd

    paket = tmp_path / "paket"
    anker = tmp_path / "anker"
    st.stands_paket(gefuehrt, paket, anker_verzeichnis=anker)
    # Die Positivkontrolle zuerst: mit dem echten externen Anker geht es.
    assert fd.betrieb(paket, anker / "anker.jsonl")["vorhanden"] is True

    beilage = paket / "anker.jsonl"
    beilage.write_bytes((anker / "anker.jsonl").read_bytes())
    with pytest.raises(fd.FalldatenFehler, match="IM Paket"):
        fd.betrieb(paket, beilage)
