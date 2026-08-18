"""Migrationsabnahmebericht (gates/abnahmebericht): G-2-Vorlage als HTML.

Die Suite-Urteile kommen aus der echten Migrationssuite (Kern-eigene,
centgerundete Erwartungen); geprüft wird die Berichts-Mechanik:
Verdikt, Prüfgrößen-Zusammenfassung, vollständige Fehlschläge/Befunde,
Mapping-Tabelle, Bestandsbericht-Verweise, Determinismus und
HTML-Escaping.

Knoten: klv
"""

from __future__ import annotations

import dataclasses

from rechner_pipeline.gates.abnahmebericht import baue_bericht, schreibe_bericht
from rechner_pipeline.kern import KLV_DEFAULT, Rechenkern
from rechner_pipeline.ontologie.transformation import (
    FeldMapping,
    OffenerKonflikt,
    TransformationsSpec,
)
from rechner_pipeline.qa.migrationssuite import (
    GeVoErwartung,
    VertragsPruefung,
    pruefe_bestand,
)

MP = dataclasses.asdict(KLV_DEFAULT)
KERN = Rechenkern(KLV_DEFAULT)
S1, S2 = 12 * 9 + 5, 12 * 10 + 5


def _pruefung(police_id: str, dk1_versatz: float = 0.0,
              gevos=()) -> VertragsPruefung:
    return VertragsPruefung(
        police_id=police_id, model_point=MP,
        monate_stichtag_1=S1, monate_stichtag_2=S2,
        dk_erwartet_1=round(KERN.monatsreserve(S1).vx_mrv, 2) + dk1_versatz,
        dk_erwartet_2=round(KERN.monatsreserve(S2).vx_mrv, 2),
        gevos=gevos,
    )


def _spec() -> TransformationsSpec:
    return TransformationsSpec(
        quelle_datei="abzug.csv", quelle_sha256="ab" * 32,
        akteur="test/skill@abc1234", erhoben_am="2026-08-18",
        felder=[
            FeldMapping(ziel="police_id", typ="direkt", quellen=["POLNR"],
                        begruendung="eindeutige Nummer"),
            FeldMapping(ziel="status", typ="kodierung", quellen=["RK"],
                        kodierung={"NR": "nichtraucher", "R": "raucher"},
                        begruendung="Risikoklasse"),
            FeldMapping(typ="nicht_uebernommen", quellen=["GESCHL"],
                        begruendung="<Tarif rechnet unisex>"),
        ],
        offene_konflikte=[OffenerKonflikt(
            quellspalte="STORNO_KZ", frage="Bedeutung von 'S'?",
            entscheidung="storniert", entscheider="bartek")],
    )


def test_gruener_bericht_mit_allen_abschnitten(tmp_path) -> None:
    suite = pruefe_bestand([_pruefung("P-1"), _pruefung("P-2")])
    pfad = schreibe_bericht(
        tmp_path / "bericht.html", titel="Abnahme Testfall",
        stichtag_1="2026-01-01", stichtag_2="2027-01-01", suite=suite,
        spec=_spec(),
        transformation_ergebnis={
            "zeilen_quelle": 500, "zeilen_ziel": 498,
            "befunde": ["Zeile 7, Feld status: Wert 'X' fehlt"]},
        bestandsbericht_vor="vor/index.html",
        bestandsbericht_nach="nach/index.html",
    )
    text = pfad.read_text(encoding="utf-8")
    assert "ALLE ABNAHMETESTS BESTANDEN (2 von 2" in text
    assert "menschliche Entscheidung" in text and "G-2" in text
    assert "dk_stichtag_1" in text and "dk_stichtag_2" in text
    assert "POLNR" in text and "police_id" in text
    assert "NR -&gt; nichtraucher" in text          # Kodierung, escaped
    assert "&lt;Tarif rechnet unisex&gt;" in text   # HTML-Escaping
    assert "entschieden (bartek): storniert" in text
    assert "Transformationsergebnis" in text
    assert "<b>500</b>" in text and "<b>498</b>" in text
    assert "Wert &#x27;X&#x27; fehlt" in text or "Wert 'X' fehlt" in text
    assert "vor/index.html" in text and "nach/index.html" in text
    assert "Keine." in text                          # keine Fehlschlaege
    # Einzelvergleiche: jeder Wert erscheint als echte Zahl im Bericht
    assert "Einzelvergleiche (alle Werte)" in text
    dk1 = KERN.monatsreserve(S1).vx_mrv
    assert f"{dk1:.2f}" in text
    assert text.count("<td class='gruen'>OK</td>") == 4  # 2 Vertraege x 2 DK


def test_roter_bericht_weist_fehlschlaege_und_befunde_aus() -> None:
    suite = pruefe_bestand([
        _pruefung("P-1"),
        _pruefung("P-2", dk1_versatz=500.0),
        # Befund: fehlender Folgewert ohne Abgangs-GeVo
        dataclasses.replace(_pruefung("P-3"), dk_erwartet_2=None),
    ])
    text = baue_bericht(
        titel="t", stichtag_1="s1", stichtag_2="s2", suite=suite)
    assert "2 von 3 Verträgen FEHLGESCHLAGEN" in text
    assert "P-2" in text and "-500.00" in text
    assert "Befund:" in text and "keinen Abgang" in text
    assert "<td class='rot'>FEHLER</td>" in text      # Einzelvergleichs-Marke


def test_gevo_pruefgroessen_erscheinen_gruppiert() -> None:
    m_sto = S1 + 4
    gevo = GeVoErwartung("STO", m_sto, round(KERN.monatsreserve(m_sto).rkw, 2))
    v = dataclasses.replace(_pruefung("P-1", gevos=(gevo,)),
                            dk_erwartet_2=None)
    text = baue_bericht(titel="t", stichtag_1="s1", stichtag_2="s2",
                        suite=pruefe_bestand([v]))
    assert "gevo_sto" in text


def test_bericht_ist_deterministisch() -> None:
    suite = pruefe_bestand([_pruefung("P-1")])
    args = dict(titel="t", stichtag_1="s1", stichtag_2="s2",
                suite=suite, spec=_spec())
    assert baue_bericht(**args) == baue_bericht(**args)
