"""Plan P5+P6: Transformations-Spec und Abzugsabgleich.

Verankert die beiden Migrations-Maschinerien VOR ihrem ersten echten
Einsatz (Baldrian-Fall): das Mapping ist beidseitig geprueft und
deterministisch angewandt; der Abgleich loest eine Diskrepanz nur dann
automatisch auf, wenn die Belege genau EINE Lesart stuetzen und die
verworfene Lesart NICHT aus der Meldung stammt (harte Regel der
Projektleitung 2026-08-18). Sonst bleibt die Aufloesung beim Menschen.

Die Zahlen der Testfaelle sind Mechanik-Beispiele, keine Aussage ueber
die Aufloesung eines konkreten Migrationsfalls.

Knoten: klv

"""

from __future__ import annotations

import dataclasses

import pytest

from rechner_pipeline.kern import KLV_DEFAULT, berechne
from rechner_pipeline.ontologie.transformation import (
    FeldMapping,
    OffenerKonflikt,
    TransformationsSpec,
    validate_spec,
    wende_an,
)
from rechner_pipeline.qa.abzugsabgleich import (
    Lesart,
    VertragsBeleg,
    gleiche_ab,
)

SHA = "b" * 64
AKTEUR = "test/transformiere-quellbestand@abc1234"


def _spec(**override) -> TransformationsSpec:
    basis = dict(
        quelle_datei="baldrian_abzug.csv", quelle_sha256=SHA,
        akteur=AKTEUR, erhoben_am="2026-08-18T12:00:00+00:00",
        felder=[
            FeldMapping(ziel="police_id", typ="direkt", quellen=["POLNR"],
                        begruendung="Policennummer, eindeutig"),
            FeldMapping(ziel="beginn", typ="berechnung", quellen=["BEGINN"],
                        berechnung="datum_nach_iso",
                        begruendung="deutsches Datumsformat"),
            FeldMapping(ziel="entry_age", typ="berechnung",
                        quellen=["GEBDAT", "BEGINN"],
                        berechnung="alter_aus_geburtsdatum_und_beginn",
                        begruendung="Abzug traegt kein Alter, nur Daten"),
            FeldMapping(ziel="duration", typ="berechnung", quellen=["n"],
                        berechnung="ganzzahl", begruendung="Jahre"),
            FeldMapping(ziel="premium_duration", typ="berechnung",
                        quellen=["t"], berechnung="ganzzahl",
                        begruendung="Jahre"),
            FeldMapping(ziel="sum_insured", typ="berechnung",
                        quellen=["ERLSUMME"], berechnung="zahl",
                        begruendung="Erlebensfallsumme = Versicherungssumme"),
            FeldMapping(ziel="zahlweise", typ="kodierung", quellen=["ZAHLW"],
                        kodierung={"monatlich": 12, "vierteljaehrlich": 4,
                                   "halbjaehrlich": 2, "jaehrlich": 1},
                        begruendung="Textform -> Raten je Jahr"),
            FeldMapping(ziel="status", typ="kodierung", quellen=["RK"],
                        kodierung={"R": "Raucher", "NR": "Nichtraucher"},
                        begruendung="Risikoklasse"),
            FeldMapping(ziel="tarifart", typ="kodierung", quellen=["BGRP"],
                        kodierung={"E": "Einzel", "K": "Kollektiv",
                                   "H": "Haus"},
                        begruendung="Bestandsgruppe"),
            FeldMapping(ziel="", typ="nicht_uebernommen", quellen=["TARIF"],
                        begruendung="konstantes Tarifkuerzel, traegt keine "
                                    "eigene Information"),
        ],
    )
    basis.update(override)
    return TransformationsSpec(**basis)


QUELLSPALTEN = ["POLNR", "BEGINN", "GEBDAT", "n", "t", "ERLSUMME",
                "ZAHLW", "RK", "BGRP", "TARIF"]

ZEILE = {
    "POLNR": "7000001", "BEGINN": "01.06.2015", "GEBDAT": "01.06.1976",
    "n": "20", "t": "15", "ERLSUMME": "87000", "ZAHLW": "monatlich",
    "RK": "NR", "BGRP": "K", "TARIF": "KLV15",
}


# --------------------------------------------------------------------------- #
# P5: Spec-Validierung und Anwendung
# --------------------------------------------------------------------------- #


def test_vollstaendige_spec_ist_anwendbar():
    assert validate_spec(_spec(), QUELLSPALTEN) == []


def test_ungedecktes_pflichtfeld_faellt():
    spec = _spec()
    spec = TransformationsSpec(**{
        **spec.model_dump(),
        "felder": [f.model_dump() for f in spec.felder
                   if f.ziel != "sum_insured"],
    })
    fehler = validate_spec(spec, QUELLSPALTEN)
    assert any("'sum_insured' ist nicht gedeckt" in f for f in fehler)


def test_stille_auslassung_einer_quellspalte_faellt():
    fehler = validate_spec(_spec(), QUELLSPALTEN + ["STORNO_KZ"])
    assert any("'STORNO_KZ'" in f and "stillen Auslassungen" in f
               for f in fehler)


def test_offener_konflikt_blockiert_bis_zur_menschlichen_entscheidung():
    spec = _spec(offene_konflikte=[OffenerKonflikt(
        quellspalte="STORNO_KZ",
        frage="Werte leer/R/S — was bedeutet 'S'? Nicht dokumentiert.")])
    fehler = validate_spec(spec, QUELLSPALTEN + ["STORNO_KZ"])
    assert any("MENSCHLICHE Entscheidung noetig" in f for f in fehler)
    # ... entschieden ist der Konflikt kein Blocker mehr:
    spec = _spec(offene_konflikte=[OffenerKonflikt(
        quellspalte="STORNO_KZ", frage="was bedeutet 'S'?",
        entscheidung="<entschieden durch den Menschen>",
        entscheider="Bartek")])
    assert validate_spec(spec, QUELLSPALTEN + ["STORNO_KZ"]) == []


def test_unbekanntes_zielfeld_ist_gt_grenze():
    spec = _spec()
    felder = [f.model_dump() for f in spec.felder]
    felder.append(FeldMapping(
        ziel="provisionssatz", typ="direkt", quellen=["TARIF"],
        begruendung="?").model_dump())
    fehler = validate_spec(
        TransformationsSpec(**{**spec.model_dump(), "felder": felder}),
        QUELLSPALTEN)
    assert any("provisionssatz" in f and "G-T" in f for f in fehler)


def test_anwendung_ist_deterministisch_und_vollstaendig():
    ziel, befunde = wende_an(_spec(), [ZEILE])
    assert befunde == []
    [v] = ziel
    assert v["entry_age"] == 39                # 1976 -> 2015, Juni
    assert v["duration"] == 20 and v["premium_duration"] == 15
    assert v["sum_insured"] == 87000.0
    assert v["zahlweise"] == 12
    assert v["status"] == "Nichtraucher" and v["tarifart"] == "Kollektiv"
    assert v["beginn"] == "2015-06-01"
    # Determinismus:
    assert wende_an(_spec(), [ZEILE]) == (ziel, [])


def test_unbekannter_kodierungswert_verwirft_die_zeile_laut():
    kaputt = dict(ZEILE, RK="X")
    ziel, befunde = wende_an(_spec(), [ZEILE, kaputt])
    assert len(ziel) == 1                      # halbe Vertraege gibt es nicht
    assert any("'X'" in b and "Kodierung" in b for b in befunde)


# --------------------------------------------------------------------------- #
# P6: Abzugsabgleich — Beleg, Verweigerung, harte Meldungs-Regel
# --------------------------------------------------------------------------- #


def _belege(feld: str, wahrer_wert, anzahl: int = 3):
    """Abzug-Belege aus dem Kern erzeugen — mit der im Testfall als
    zutreffend gesetzten Lesart.

    Kontrollrechnung gegen unabhaengigen Pfad: die Belege entstehen
    ueber ``berechne`` (Golden-Master-View), der Abgleich rechnet
    intern denselben Kern — was hier getestet wird, ist die
    URTEILSLOGIK, nicht die Zahlen.
    """
    belege = []
    for i, (x, n, t) in enumerate([(35, 20, 15), (45, 25, 20), (30, 30, 30)][:anzahl]):
        mp = dataclasses.replace(KLV_DEFAULT, x=x, n=n, t=t)
        params = dataclasses.asdict(mp)
        params[feld] = wahrer_wert
        mp_wahr = type(mp)(**params)
        ergebnis = berechne(mp_wahr)
        k = 5
        belege.append(VertragsBeleg(
            police_id=f"700000{i}",
            model_point=params,
            vertragsjahr=k,
            erwartet={
                "BJB": ergebnis["scalars"]["Kalkulation"]["BJB"],
                "kVx_MRV": ergebnis["tables"]["Kalkulation"][k]["kVx_MRV"],
            },
        ))
    return belege


def test_abgleich_belegt_rechnerfehler_automatisch():
    """Genau eine Lesart passt zu den Belegen -> automatische Aufloesung.

    Die verworfene Lesart stammt aus dem Rechner; das Protokoll fuehrt
    beide Residuen. Welcher Wert in einem echten Fall der richtige ist,
    sagt dieser Test nicht — er prueft die Urteilslogik.
    """
    belege = _belege("zins", 0.0125)
    urteil = gleiche_ab("zins", [
        Lesart(0.0125, "tarifmeldung"),
        Lesart(0.0175, "tarifrechner"),
    ], belege)
    assert urteil["automatisch_aufloesbar"] is True
    assert urteil["menschlich_erforderlich"] is False
    assert urteil["gewaehlter_wert"] == 0.0125
    assert "deterministisch belegt" in urteil["begruendung"]
    # Beide Residuen stehen im Protokoll:
    verlierer = next(u for u in urteil["urteile"] if not u["passt"])
    assert verlierer["quelle_art"] == "tarifrechner"
    assert verlierer["max_relative_abweichung"] > 0.01


def test_meldungsfehler_bleibt_immer_beim_menschen():
    """Harte Regel: verworfene MELDUNGS-Lesart -> nie automatisch."""
    belege = _belege("zins", 0.0175)           # Belege stuetzen den Rechner
    urteil = gleiche_ab("zins", [
        Lesart(0.0125, "tarifmeldung"),
        Lesart(0.0175, "tarifrechner"),
    ], belege)
    assert urteil["automatisch_aufloesbar"] is False
    assert urteil["menschlich_erforderlich"] is True
    assert "aufsichtsrechtlich" in urteil["begruendung"]
    assert urteil["gewaehlter_wert"] == 0.0175  # Beleg liegt trotzdem bei


def test_uneindeutiger_beleg_loest_nie_auf():
    """Zwei nah beieinander liegende Lesarten, Toleranz verschluckt den
    Unterschied nicht -> aber wenn BEIDE passen oder KEINE, bleibt es
    beim Menschen."""
    belege = _belege("zins", 0.02)              # keine der Lesarten wahr
    urteil = gleiche_ab("zins", [
        Lesart(0.0125, "tarifmeldung"),
        Lesart(0.0175, "tarifrechner"),
    ], belege)
    assert urteil["automatisch_aufloesbar"] is False
    assert urteil["menschlich_erforderlich"] is True
    assert "kein eindeutiger" in urteil["begruendung"]


def test_ohne_belege_kein_urteil():
    urteil = gleiche_ab("zins", [
        Lesart(0.0125, "tarifmeldung"), Lesart(0.0175, "tarifrechner"),
    ], [])
    assert urteil["automatisch_aufloesbar"] is False
    assert "keine Belege" in urteil["begruendung"]


def test_beta1_fall_wird_ebenfalls_belegt():
    """Dieselbe Mechanik an einem zweiten Feld (Kostensatz statt Zins)."""
    belege = _belege("beta1", 0.01)
    urteil = gleiche_ab("beta1", [
        Lesart(0.01, "tarifmeldung"),
        Lesart(0.0, "tarifrechner"),
    ], belege)
    assert urteil["automatisch_aufloesbar"] is True
    assert urteil["gewaehlter_wert"] == 0.01


# --------------------------------------------------------------------------- #
# P5: Vorverdichter (Spaltenprofil) und Skill-Verankerung
# --------------------------------------------------------------------------- #


def test_bestand_profil_ist_deterministisch_und_typisiert(tmp_path):
    from rechner_pipeline.quellen.bestand_profil import baue_profil

    csv_datei = tmp_path / "abzug.csv"
    csv_datei.write_text(
        "POLNR;BEGINN;ERLSUMME;RK;STORNO_KZ\n"
        "7000001;01.06.2015;87000;NR;\n"
        "7000002;01.02.2016;66000;R;S\n",
        encoding="utf-8")
    profil = baue_profil(csv_datei)
    assert profil == baue_profil(csv_datei)          # deterministisch
    spalten = {s["name"]: s for s in profil["spalten"]}
    assert spalten["POLNR"]["typ"] == "ganzzahl"
    assert spalten["BEGINN"]["typ"] == "datum"
    assert spalten["RK"]["beispiele"] == ["NR", "R"]
    assert spalten["RK"]["beispiele_vollstaendig"] is True
    assert spalten["STORNO_KZ"]["leeranteil"] == 0.5
    assert profil["zeilen"] == 2 and len(profil["quelle_sha256"]) == 64


def test_bestand_profil_faellt_bei_doppelten_spalten(tmp_path):
    from rechner_pipeline.quellen.bestand_profil import baue_profil

    csv_datei = tmp_path / "abzug.csv"
    csv_datei.write_text("A;B;A\n1;2;3\n", encoding="utf-8")
    with pytest.raises(ValueError, match="doppelte Spaltennamen"):
        baue_profil(csv_datei)


def test_transformations_skill_ist_verankert():
    """Skill-Paritaet und die nicht verhandelbaren Kerne des neuen Skills."""
    from pathlib import Path

    repo = Path(__file__).resolve().parents[1]
    claude = (repo / ".claude/skills/transformiere-quellbestand/SKILL.md"
              ).read_text(encoding="utf-8")
    codex = (repo / ".agents/skills/transformiere-quellbestand/SKILL.md"
             ).read_text(encoding="utf-8")
    assert claude == codex                            # Paritaet
    assert "ERFINDEST nichts" in claude
    assert "OffenerKonflikt" in claude
    assert "G-T" in claude
    assert "Abbruchkriterien" in claude
    konflikt = (repo / ".claude/skills/bereite-fachkonflikt-auf/SKILL.md"
                ).read_text(encoding="utf-8")
    assert "Bestandsabzug-Abgleich" in konflikt
    assert "NIEMALS automatisch" in konflikt
    assert konflikt == (repo / ".agents/skills/bereite-fachkonflikt-auf/"
                        "SKILL.md").read_text(encoding="utf-8")
