"""Vorlaeufige Diskrepanz-Aufloesung als Kommando mit Protokoll (U1, Z1-06).

Bis dahin war die vorlaeufige Aufloesung die einzige A-Box-Mutation
ohne Kommando und Ledger: ein Ad-hoc-Skript des Skills rief
loese_diskrepanz_auf(vorlaeufig=True). Jetzt ist sie ein Kommando mit
Akteur-Konvention, das protokolliert — und zeichnet nichts.

Knoten: klv
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from rechner_pipeline.fall import anlegen, registrieren
from rechner_pipeline.ontologie import PFLICHT_PARAMETER, entscheide
from rechner_pipeline.ontologie.abox import lade, speichere
from rechner_pipeline.ontologie.befuellung import (
    FragmentWert,
    FragmentZelle,
    QuellFragment,
    baue_abox,
)

from tests.zeichnung_fixture import annahme_args

ZEIT = "2026-08-15T09:00:00+00:00"
PLAUSIBEL = {
    "zins": 0.0175, "tafel": "DAV2008_T", "alpha": 0.025, "beta1": 0.03,
    "gamma1": 0.001, "gamma2": 0.00125, "gamma3": 0.0025,
    "policy_fee": 12.0, "stoab_satz": 0.005, "stoab_min": 50.0,
    "stoab_max": 150.0, "min_alter_flex": 60, "min_rlz_flex": 5,
}
AKTEUR = "claude-fable-5-1/migrationsfall-durchfuehren@abc1234"


@pytest.fixture()
def fall(tmp_path: Path):
    f = tmp_path / "fall"
    anlegen(f)
    for name in ("rechner.xlsm", "meldung.docx"):
        q = tmp_path / name
        q.write_bytes(name.encode())
        registrieren(f, q)
    register = json.loads((f / "eingang.json").read_text(encoding="utf-8"))

    def frag(datei, art, beta1):
        parameter = {feld: FragmentWert(wert=PLAUSIBEL[feld], fundstelle=f"{datei}:x")
                     for feld in PFLICHT_PARAMETER}
        parameter["beta1"] = FragmentWert(wert=beta1, fundstelle=f"{datei}:beta1")
        return QuellFragment(generation="tg2012", quelle_datei=datei, quelle_art=art,
                             zellen=[FragmentZelle(parameter=parameter)])

    abox = baue_abox(str(f), [frag("meldung.docx", "tarifmeldung", 0.025),
                              frag("rechner.xlsm", "tarifrechner", 0.03)],
                     register, ["test/extraktion@abc1234", "test/extraktion-b@abc1234"], ZEIT)
    speichere(abox, f)
    return f


def test_vorlaeufig_loest_alle_offenen_zur_quelle_und_protokolliert(fall, capsys):
    rc = entscheide.main([
        "--fall", str(fall), "--vorlaeufig", "--akteur", AKTEUR,
        "--alle-offenen", "--quelle", "rechner.xlsm",
        "--begruendung", "GM reproduziert den Rechner; A-Q1 entscheidet",
    ])
    assert rc == 0
    ausgabe = json.loads(capsys.readouterr().out)
    assert ausgabe["vorlaeufig"] is True and ausgabe["akteur"] == AKTEUR
    [d] = lade(fall).diskrepanzen
    assert d.status == "aufgeloest" and d.entscheidung.vorlaeufig is True
    assert d.entscheidung.entscheider == AKTEUR
    assert d.entscheidung.zeichnung is None, "ein Agent zeichnet nicht"
    assert d.entscheidung.gewaehlter_wert == 0.03

    protokoll = fall / "abgeleitet" / "protokoll" / "vorlaeufige_entscheide.jsonl"
    [zeile] = protokoll.read_text(encoding="utf-8").splitlines()
    eintrag = json.loads(zeile)
    assert eintrag["akteur"] == AKTEUR and eintrag["vorlaeufig"] is True
    assert eintrag["entschieden"] == [{"diskrepanz": d.id, "wert": 0.03}]
    assert eintrag["abox_sha256_vorher"] != eintrag["abox_sha256_nachher"]


def test_vorlaeufig_verlangt_akteur_konvention_und_traegt_keinen_schluessel(fall, capsys):
    basis = ["--fall", str(fall), "--vorlaeufig", "--alle-offenen",
             "--quelle", "rechner.xlsm", "--begruendung", "x"]
    assert entscheide.main(basis) == 2
    assert "--akteur" in capsys.readouterr().err
    assert entscheide.main(basis + ["--akteur", "irgendwer"]) == 2
    assert "Konvention" in capsys.readouterr().err
    assert entscheide.main(basis + ["--akteur", AKTEUR, *annahme_args(fall)]) == 2
    assert "zeichnet nicht" in capsys.readouterr().err
    [d] = lade(fall).diskrepanzen
    assert d.status == "offen", "nichts davon hat entschieden"


def test_vorlaeufig_ueberschreibt_keine_endgueltige_entscheidung(fall, capsys):
    [d] = lade(fall).diskrepanzen
    assert entscheide.main([
        "--fall", str(fall), "--diskrepanz", d.id, "--wert", "0.025",
        "--entscheider", "Verantwortlicher Aktuar", "--begruendung", "Meldung gilt",
        *annahme_args(fall),
    ]) == 0
    capsys.readouterr()
    rc = entscheide.main([
        "--fall", str(fall), "--vorlaeufig", "--akteur", AKTEUR,
        "--diskrepanz", d.id, "--wert", "0.03", "--begruendung", "y",
    ])
    assert rc == 1
    assert "nie ueberschrieben" in capsys.readouterr().err
    [d2] = lade(fall).diskrepanzen
    assert d2.entscheidung.vorlaeufig is False and d2.entscheidung.gewaehlter_wert == 0.025


def test_endgueltige_entscheidung_ersetzt_die_vorlaeufige_und_blockt_vorher(fall, capsys):
    """Die vorlaeufige Aufloesung blockt die Annahme (P2/P4) — geprueft
    ueber den Weg, den das Gate nimmt: verbleibend_vorlaeufig."""
    assert entscheide.main([
        "--fall", str(fall), "--vorlaeufig", "--akteur", AKTEUR,
        "--alle-offenen", "--quelle", "rechner.xlsm", "--begruendung", "GM",
    ]) == 0
    capsys.readouterr()
    [d] = lade(fall).diskrepanzen
    assert entscheide.main([
        "--fall", str(fall), "--diskrepanz", d.id, "--wert", "0.025",
        "--entscheider", "Verantwortlicher Aktuar", "--begruendung", "Meldung gilt",
        *annahme_args(fall),
    ]) == 0
    ausgabe = json.loads(capsys.readouterr().out)
    assert ausgabe["verbleibend_vorlaeufig"] == []
    [d2] = lade(fall).diskrepanzen
    assert d2.entscheidung.vorlaeufig is False
    assert [e.entscheider for e in d2.entscheidungs_historie] == [AKTEUR]
