"""Migrationsabnahmebericht (gates/abnahmebericht): A-M4-Vorlage als HTML.

Die Suite-Urteile kommen aus der echten Migrationssuite (Kern-eigene,
centgerundete Erwartungen). Diese Tests können deshalb KEINEN
Rechenfehler finden — der Bericht rechnet auch keinen Wert. Geprüft
wird die Berichts-Mechanik: Verdikt, Prüfgrößen-Zusammenfassung,
vollständige Fehlschläge/Befunde, Befunde der Prüfmenge und
ausgewiesene Prüflücken, Mapping-Tabelle, Bestandsbericht-Verweise,
Determinismus und HTML-Escaping. Die Erwartungen an das URTEIL (welches
Verdikt, welcher Exit-Code, was im Bericht stehen MUSS) sind vom Kern
unabhängig.

Dazu das Kommando (Toolbox-Gate-Vertrag): genau EIN JSON auf stdout,
``abnahmebericht.gate.json`` auf JEDEM Pfad, Standard-Exit-Codes
(0 / 2 / 20 / 30), Fall-Vorgaben — und die Grenze, die das Kommando
nicht überschreitet: es nimmt nicht ab (Gate A-M4 bleibt beim Menschen).

Knoten: klv
"""

from __future__ import annotations

import csv
import dataclasses
import json
from pathlib import Path

import pytest

from rechner_pipeline.gates._common import (
    Exit,
    load_gate_ledger,
    run_command,
)
from rechner_pipeline.gates.abnahmebericht import (
    GATE,
    baue_bericht,
    main,
    renderer_artefaktrollen,
    schreibe_bericht,
)
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
            FeldMapping(ziel="beginn", typ="direkt", quellen=["BEGINN"],
                        begruendung="bereits im Zielformat"),
            FeldMapping(ziel="entry_age", typ="direkt", quellen=["ALTER"],
                        begruendung="Eintrittsalter"),
            FeldMapping(ziel="sex", typ="direkt", quellen=["GESCHL"],
                        begruendung="bereits M/F"),
            FeldMapping(ziel="duration", typ="direkt", quellen=["n"],
                        begruendung="Vertragsdauer"),
            FeldMapping(ziel="premium_duration", typ="direkt", quellen=["t"],
                        begruendung="Beitragsdauer"),
            FeldMapping(ziel="sum_insured", typ="direkt", quellen=["SUMME"],
                        begruendung="Versicherungssumme"),
            FeldMapping(ziel="zahlweise", typ="direkt", quellen=["ZAHLW"],
                        begruendung="Raten pro Jahr"),
            FeldMapping(ziel="status", typ="kodierung", quellen=["RK"],
                        kodierung={"NR": "nichtraucher", "R": "raucher"},
                        begruendung="Risikoklasse"),
            FeldMapping(ziel="tarifart", typ="direkt", quellen=["TARIFART"],
                        begruendung="Bestandsgruppe"),
            FeldMapping(typ="nicht_uebernommen", quellen=["IGNORIERT"],
                        begruendung="<Tarif rechnet unisex>"),
        ],
        offene_konflikte=[OffenerKonflikt(
            quellspalte="STORNO_KZ", frage="Bedeutung von 'S'?",
            entscheidung="<entschieden durch den Menschen>",
            entscheider="fachverantwortliche-rolle")],
    )


def _vollstaendige_suite(*pruefungen: VertragsPruefung):
    """Eine von den Berichtsartefakten unabhaengig vollstaendige Suite."""
    vollstaendig = [
        dataclasses.replace(
            pruefung,
            bjb_erwartet_1=round(KERN.gross_annual_premium(), 2),
        )
        for pruefung in pruefungen
    ]
    return pruefe_bestand(vollstaendig, erwartete_anzahl=len(vollstaendig))


def _bericht_artefakte():
    """Deklarative Artefakte fuer den bewusst roten Renderer-Pfad."""
    return {
        "spec": _spec(),
        "transformation_ergebnis": {
            "zeilen_quelle": 500,
            "zeilen_ziel": 500,
            "befunde": [],
        },
        "bestandsbericht_vor": "vor/index.html",
        "bestandsbericht_nach": "nach/index.html",
    }


def _gebundene_bericht_artefakte(tmp_path, anzahl):
    """Quellbeleg samt physisch registrierter CSV fuer positive Berichte."""
    from rechner_pipeline.fall import anlegen, registrieren

    spec = _spec()
    quellspalten = []
    for spalte in [
        *(q for feld in spec.felder for q in feld.quellen),
        *(konflikt.quellspalte for konflikt in spec.offene_konflikte),
    ]:
        if spalte not in quellspalten:
            quellspalten.append(spalte)
    lieferung = tmp_path / spec.quelle_datei
    with lieferung.open("w", encoding="utf-8", newline="") as datei:
        writer = csv.DictWriter(datei, fieldnames=quellspalten, delimiter=";")
        writer.writeheader()
        writer.writerows(
            {spalte: f"wert-{index}" for spalte in quellspalten}
            for index in range(anzahl)
        )
    fall = tmp_path / "fall"
    anlegen(fall)
    registrierung = registrieren(fall, lieferung)
    spec.quelle_sha256 = registrierung["sha256"]
    return fall, {
        "spec": spec,
        "transformation_ergebnis": {
            "quelle_sha256": registrierung["sha256"],
            "quellspalten": quellspalten,
            "zeilen_quelle": anzahl,
            "zeilen_ziel": anzahl,
            "befunde": [],
        },
        "bestandsbericht_vor": "vor/index.html",
        "bestandsbericht_nach": "nach/index.html",
    }


def test_fallloser_renderer_bleibt_rot_mit_allen_abschnitten(tmp_path) -> None:
    suite = _vollstaendige_suite(_pruefung("P-1"), _pruefung("P-2"))
    pfad = schreibe_bericht(
        tmp_path / "bericht.html", titel="Abnahme Testfall",
        stichtag_1="2026-01-01", stichtag_2="2027-01-01", suite=suite,
        **_bericht_artefakte(),
    )
    text = pfad.read_text(encoding="utf-8")
    assert "ABNAHMEBERICHT NICHT BESTANDEN" in text
    assert "ohne Fallbindung nicht autoritativ" in text
    assert "ALLE ABNAHMETESTS BESTANDEN" not in text
    assert "menschliche Entscheidung" in text and "A-M4" in text
    assert "dk_stichtag_1" in text and "dk_stichtag_2" in text
    assert "POLNR" in text and "police_id" in text
    assert "NR -&gt; nichtraucher" in text          # Kodierung, escaped
    assert "&lt;Tarif rechnet unisex&gt;" in text   # HTML-Escaping
    assert ("entschieden (fachverantwortliche-rolle): "
            "&lt;entschieden durch den Menschen&gt;") in text
    assert "Transformationsergebnis" in text
    assert text.count("<b>500</b>") >= 2
    assert "vor/index.html" in text and "nach/index.html" in text
    assert "Keine." in text                          # keine Fehlschlaege
    # Einzelvergleiche: jeder Wert erscheint als echte Zahl im Bericht
    assert "Einzelvergleiche (alle Werte)" in text
    dk1 = KERN.monatsreserve(S1).vx_mrv
    assert f"{dk1:.2f}" in text
    assert text.count("<td class='gruen'>OK</td>") == 6  # 2 x (2 DK + BJB)


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


def test_bericht_markiert_pruefluecken_im_kopf_als_nicht_bestanden() -> None:
    """Eine Prüflücke darf nicht neben einem grünen Kopfsatz stehen."""
    suite = pruefe_bestand([_pruefung("P-1")])
    text = baue_bericht(titel="t", stichtag_1="s1", stichtag_2="s2",
                        suite=suite, **_bericht_artefakte())
    assert "ABNAHMEBERICHT NICHT BESTANDEN" in text
    assert "ALLE ABNAHMETESTS BESTANDEN" not in text
    assert "Prüflücken (was NICHT geprüft wurde)" in text
    assert "bjb_stichtag_1" in text
    assert "nicht angegeben" in text            # keine erwartete Vertragszahl

    # Mit vollständiger Lieferung verschwindet die Lücke, aber ohne physische
    # Fallbindung darf daraus weiterhin kein grüner Bericht werden:
    voll = pruefe_bestand(
        [dataclasses.replace(
            _pruefung("P-1"),
            bjb_erwartet_1=round(KERN.gross_annual_premium(), 2))],
        erwartete_anzahl=1)
    text_voll = baue_bericht(titel="t", stichtag_1="s1", stichtag_2="s2",
                             suite=voll, **_bericht_artefakte())
    assert "ALLE ABNAHMETESTS BESTANDEN" not in text_voll
    assert "ohne Fallbindung nicht autoritativ" in text_voll
    assert "Keine — jede Prüfgröße war geliefert." in text_voll
    assert "bjb_stichtag_1" in text_voll        # als Prüfgröße, nicht als Lücke


def test_gruenes_verdikt_braucht_physisch_registrierte_quelle(tmp_path) -> None:
    fall, artefakte = _gebundene_bericht_artefakte(tmp_path, 1)
    gebunden = baue_bericht(
        titel="t", stichtag_1="s1", stichtag_2="s2",
        suite=_vollstaendige_suite(_pruefung("P-1")),
        fall=fall, **artefakte)
    assert "(1 von 1 Verträgen).</p>" in gebunden


@pytest.mark.parametrize(
    ("aenderung", "erwarteter_text"),
    [
        ("zeilenverlust", "2 Quellzeilen stehen nur 1 transformierte Zeile"),
        ("transformationsbefund", "Zeile 2 kann nicht transformiert werden"),
        ("offener_konflikt", "STORNO_KZ"),
        ("fehlende_spec", "Transformationsspecifikation fehlt"),
        ("fehlender_vorbericht", "Bestandsbericht VOR der Migration fehlt"),
    ],
)
def test_bericht_zeigt_jedes_abnahmehindernis_rot(
        aenderung, erwarteter_text) -> None:
    artefakte = _bericht_artefakte()
    if aenderung == "zeilenverlust":
        artefakte["transformation_ergebnis"] = {
            "zeilen_quelle": 2, "zeilen_ziel": 1, "befunde": []}
    elif aenderung == "transformationsbefund":
        artefakte["transformation_ergebnis"] = {
            "zeilen_quelle": 2, "zeilen_ziel": 2,
            "befunde": ["Zeile 2 kann nicht transformiert werden"]}
    elif aenderung == "offener_konflikt":
        spec = _spec()
        spec.offene_konflikte[0].entscheidung = None
        artefakte["spec"] = spec
    elif aenderung == "fehlende_spec":
        artefakte["spec"] = None
    else:
        artefakte["bestandsbericht_vor"] = None

    text = baue_bericht(
        titel="t", stichtag_1="s1", stichtag_2="s2",
        suite=_vollstaendige_suite(_pruefung("P-1")), **artefakte)

    assert "ABNAHMEBERICHT NICHT BESTANDEN" in text
    assert "ALLE ABNAHMETESTS BESTANDEN" not in text
    assert erwarteter_text in text


def test_bericht_weist_mengenbefunde_aus() -> None:
    """Unvollständige oder doppelte Prüfmenge: rot, mit Begründung."""
    suite = pruefe_bestand([_pruefung("P-1"), _pruefung("P-1")],
                           erwartete_anzahl=500)
    text = baue_bericht(titel="t", stichtag_1="s1", stichtag_2="s2",
                        suite=suite)
    assert "Prüfmenge (Vollständigkeit und Duplikate)" in text
    assert "0 von 2 Verträgen FEHLGESCHLAGEN" in text
    assert "2 Befund(e) der Prüfmenge" in text
    assert "498 Verträge fehlen" in text
    assert "2-mal" in text and "P-1" in text
    assert "ALLE ABNAHMETESTS BESTANDEN" not in text


def test_bericht_ist_deterministisch() -> None:
    suite = _vollstaendige_suite(_pruefung("P-1"))
    args = dict(titel="t", stichtag_1="s1", stichtag_2="s2",
                suite=suite, **_bericht_artefakte())
    assert baue_bericht(**args) == baue_bericht(**args)


# --------------------------------------------------------------------- #
# Das Kommando (Toolbox-Gate-Vertrag)
# --------------------------------------------------------------------- #


def _suite_datei(tmp_path, *pruefungen, name: str = "suite.json"):
    """Suite-Ergebnis so ablegen, wie das Kommando es erwartet."""
    pfad = tmp_path / name
    pfad.write_text(
        json.dumps(pruefe_bestand(list(pruefungen))), encoding="utf-8")
    return pfad


def _ledger(diagnostics_dir):
    eintraege, lesefehler = load_gate_ledger(diagnostics_dir)
    assert lesefehler == []
    assert len(eintraege) == 1
    return eintraege[0]


def _basis_argv(tmp_path, suite_pfad):
    return [
        "--suite", str(suite_pfad), "--titel", "Abnahme Testfall",
        "--stichtag-1", "2026-01-01", "--stichtag-2", "2027-01-01",
        "--bericht", str(tmp_path / "berichte" / "abnahme.html"),
        "--diagnostics-dir", str(tmp_path / "diagnostics"),
    ] + _pflicht_argv(tmp_path)


def _pflicht_argv(tmp_path):
    """Vier vorhandene Pflichtartefakte fuer einen erfolgreichen CLI-Lauf."""
    spec_pfad = tmp_path / "spec.json"
    transformation_pfad = tmp_path / "transformation.json"
    vor_pfad = tmp_path / "vor" / "index.html"
    nach_pfad = tmp_path / "nach" / "index.html"
    spec_pfad.write_text(_spec().model_dump_json(), encoding="utf-8")
    transformation_pfad.write_text(json.dumps({
        "zeilen_quelle": 2, "zeilen_ziel": 2, "befunde": [],
    }), encoding="utf-8")
    vor_pfad.parent.mkdir(parents=True, exist_ok=True)
    nach_pfad.parent.mkdir(parents=True, exist_ok=True)
    vor_pfad.write_text("<html>vor</html>", encoding="utf-8")
    nach_pfad.write_text("<html>nach</html>", encoding="utf-8")
    return [
        "--spec", str(spec_pfad),
        "--transformation-ergebnis", str(transformation_pfad),
        "--bestandsbericht-vor", str(vor_pfad),
        "--bestandsbericht-nach", str(nach_pfad),
    ]


def _gebundene_plicht_argv(tmp_path, anzahl):
    """CLI-Artefakte mit erneut pruefbarer registrierter Quellbindung."""
    fall, artefakte = _gebundene_bericht_artefakte(tmp_path, anzahl)
    spec_pfad = tmp_path / "spec.json"
    transformation_pfad = tmp_path / "transformation.json"
    vor_pfad = tmp_path / "vor" / "index.html"
    nach_pfad = tmp_path / "nach" / "index.html"
    spec_pfad.write_text(
        artefakte["spec"].model_dump_json(), encoding="utf-8")
    transformation_pfad.write_text(
        json.dumps(artefakte["transformation_ergebnis"]), encoding="utf-8")
    vor_pfad.parent.mkdir(parents=True, exist_ok=True)
    nach_pfad.parent.mkdir(parents=True, exist_ok=True)
    vor_pfad.write_text("<html>vor</html>", encoding="utf-8")
    nach_pfad.write_text("<html>nach</html>", encoding="utf-8")
    return fall, [
        "--spec", str(spec_pfad),
        "--transformation-ergebnis", str(transformation_pfad),
        "--bestandsbericht-vor", str(vor_pfad),
        "--bestandsbericht-nach", str(nach_pfad),
    ]


def test_fallloses_kommando_schreibt_nur_roten_bericht_und_ledger(
        tmp_path) -> None:
    suite_pfad = tmp_path / "suite.json"
    suite_pfad.write_text(json.dumps(_vollstaendige_suite(
        _pruefung("P-1"), _pruefung("P-2"))), encoding="utf-8")

    result = main(_basis_argv(tmp_path, suite_pfad))

    assert (result.exit_code, result.status) == (Exit.GOLDEN_MASTER, "failed")
    assert result.gate == GATE
    bericht = tmp_path / "berichte" / "abnahme.html"
    text = bericht.read_text(encoding="utf-8")
    assert "ABNAHMEBERICHT NICHT BESTANDEN" in text
    assert "ohne Fallbindung nicht autoritativ" in text
    assert "POLNR" in text and "vor/index.html" in text
    # Provenienz: Eingaben UND Ausgabe gehasht (ein bestandenes Gate ohne
    # input_hashes wuerde das Dossier blockieren).
    assert result.input_hashes and str(suite_pfad) in str(result.input_hashes)
    assert list(result.output_hashes) == [str(bericht)]
    assert result.summary["bestanden"] == 2
    assert result.summary["mapping_tabelle"] is True
    renderer_artefakte = result.summary["renderer_artefakte"]
    assert set(renderer_artefakte) == set(renderer_artefaktrollen())
    assert all(
        result.input_hashes[eintrag["pfad"]] == eintrag["sha256"]
        for eintrag in renderer_artefakte.values()
    )
    # Das Kommando nimmt NICHT ab — die Entscheidung bleibt beim Menschen.
    assert "A-M4" in result.summary["abnahme"]

    eintrag = _ledger(tmp_path / "diagnostics")
    assert (eintrag.gate, eintrag.command) == (GATE, "abnahmebericht")
    assert (eintrag.status, eintrag.summary["exit_code"]) == ("failed", 30)
    assert eintrag.required is True
    assert (tmp_path / "diagnostics" / "abnahmebericht.gate.json").is_file()


def test_kommando_gruen_nur_mit_physisch_registrierter_quelle(tmp_path) -> None:
    suite_pfad = tmp_path / "suite.json"
    suite_pfad.write_text(json.dumps(_vollstaendige_suite(
        _pruefung("P-1"), _pruefung("P-2"))), encoding="utf-8")
    fall, pflicht = _gebundene_plicht_argv(tmp_path, 2)

    result = main([
        "--fall", str(fall), "--suite", str(suite_pfad),
        "--titel", "Abnahme Testfall",
        "--stichtag-1", "2026-01-01", "--stichtag-2", "2027-01-01",
        "--bericht", str(tmp_path / "berichte" / "abnahme.html"),
        "--diagnostics-dir", str(tmp_path / "diagnostics"),
        *pflicht,
    ])

    assert (result.exit_code, result.status) == (Exit.OK, "passed")
    assert result.summary["bericht_bestanden"] is True
    assert "ALLE ABNAHMETESTS BESTANDEN" in (
        tmp_path / "berichte" / "abnahme.html").read_text(encoding="utf-8")


def test_kommando_rot_blockiert_und_schreibt_den_bericht_trotzdem(
        tmp_path) -> None:
    suite_pfad = _suite_datei(
        tmp_path, _pruefung("P-1"), _pruefung("P-2", dk1_versatz=500.0))

    result = main(_basis_argv(tmp_path, suite_pfad))

    assert (result.exit_code, result.status) == (Exit.GOLDEN_MASTER, "failed")
    # Gerade der rote Bericht ist das Beweisstueck fuer die A-M4-Vorlage.
    text = (tmp_path / "berichte" / "abnahme.html").read_text(encoding="utf-8")
    assert "1 von 2 Verträgen FEHLGESCHLAGEN" in text
    meldungen = [e["message"] for e in result.errors]
    assert any("P-2" in m and "dk_stichtag_1" in m for m in meldungen)
    assert result.repair_hints and "Toleranzen" in str(result.repair_hints)
    assert _ledger(tmp_path / "diagnostics").status == "failed"


def test_kommando_ohne_suite_ist_usage_mit_ledger(tmp_path) -> None:
    result = main(["--titel", "T", "--stichtag-1", "a", "--stichtag-2", "b",
                   "--bericht", str(tmp_path / "b.html"),
                   "--diagnostics-dir", str(tmp_path / "diagnostics")])

    assert (result.exit_code, result.status) == (Exit.USAGE, "failed")
    assert "--suite" in result.errors[0]["message"]
    assert not (tmp_path / "b.html").exists()
    # Auch der Usage-Abbruch hinterlaesst eine Spur.
    assert _ledger(tmp_path / "diagnostics").status == "failed"


def test_kommando_ohne_zielpfad_nennt_den_ausweg(tmp_path) -> None:
    suite_pfad = _suite_datei(tmp_path, _pruefung("P-1"))
    result = main(["--suite", str(suite_pfad), "--titel", "T",
                   "--stichtag-1", "a", "--stichtag-2", "b",
                   "--diagnostics-dir", str(tmp_path / "diagnostics")])
    assert result.exit_code == Exit.USAGE
    meldung = result.errors[0]["message"]
    assert "--bericht" in meldung and "--fall" in meldung


def test_kommando_meldet_fehlende_suite_datei(tmp_path) -> None:
    result = main(_basis_argv(tmp_path, tmp_path / "gibt_es_nicht.json"))
    assert result.exit_code == Exit.USAGE
    assert "gibt_es_nicht.json" in result.errors[0]["message"]


@pytest.mark.parametrize(
    "flag",
    [
        "--spec",
        "--transformation-ergebnis",
        "--bestandsbericht-vor",
        "--bestandsbericht-nach",
    ],
)
def test_kommando_blockiert_bei_fehlendem_pflichtartefakt(tmp_path, flag) -> None:
    suite_pfad = tmp_path / "suite.json"
    suite_pfad.write_text(json.dumps(
        _vollstaendige_suite(_pruefung("P-1"))), encoding="utf-8")
    argv = _basis_argv(tmp_path, suite_pfad)
    index = argv.index(flag)
    del argv[index:index + 2]

    result = main(argv)

    assert (result.exit_code, result.status) == (Exit.USAGE, "failed")
    assert flag in result.errors[0]["message"]
    assert not (tmp_path / "berichte" / "abnahme.html").exists()


def test_kommando_blockiert_bei_nicht_vorhandenem_pflichtartefakt(tmp_path) -> None:
    suite_pfad = tmp_path / "suite.json"
    suite_pfad.write_text(json.dumps(
        _vollstaendige_suite(_pruefung("P-1"))), encoding="utf-8")
    argv = _basis_argv(tmp_path, suite_pfad)
    argv[argv.index("--bestandsbericht-nach") + 1] = str(
        tmp_path / "nach" / "fehlt.html")

    result = main(argv)

    assert (result.exit_code, result.status) == (Exit.USAGE, "failed")
    assert "fehlt.html" in result.errors[0]["message"]


@pytest.mark.parametrize(
    "kollision",
    [
        "vor_nach_alias",
        "vor_ausgabe_alias",
        "spec_ausgabe_alias",
        "spec_vor_alias",
    ],
)
def test_kommando_blockiert_kanonisch_gleiche_berichtsrollen(
        tmp_path, kollision) -> None:
    """Keine Datei darf mehrere Pflicht- oder Ausgaberollen ersetzen."""
    suite_pfad = tmp_path / "suite.json"
    suite_pfad.write_text(json.dumps(
        _vollstaendige_suite(_pruefung("P-1"))), encoding="utf-8")
    argv = _basis_argv(tmp_path, suite_pfad)
    vor_alias = tmp_path / "vor" / ".." / "vor" / "index.html"
    if kollision == "vor_nach_alias":
        argv[argv.index("--bestandsbericht-nach") + 1] = str(vor_alias)
    elif kollision == "vor_ausgabe_alias":
        argv[argv.index("--bericht") + 1] = str(vor_alias)
    elif kollision == "spec_ausgabe_alias":
        argv[argv.index("--bericht") + 1] = argv[argv.index("--spec") + 1]
    else:
        argv[argv.index("--bestandsbericht-vor") + 1] = argv[
            argv.index("--spec") + 1
        ]

    result = main(argv)

    assert result.status == "failed"
    assert result.exit_code != Exit.OK
    assert "paarweise verschiedene Dateien" in result.errors[0]["message"]
    bericht = Path(argv[argv.index("--bericht") + 1])
    if bericht.exists():
        assert "ALLE ABNAHMETESTS BESTANDEN" not in bericht.read_text(
            encoding="utf-8"
        )


def test_kommando_blockiert_hardlink_zwischen_eingabe_und_ausgabe(
        tmp_path) -> None:
    """Verschiedene Pfade duerfen nicht dasselbe Dateiobjekt bezeichnen."""
    suite_pfad = tmp_path / "suite.json"
    suite_pfad.write_text(json.dumps(
        _vollstaendige_suite(_pruefung("P-1"))), encoding="utf-8")
    argv = _basis_argv(tmp_path, suite_pfad)
    spec_pfad = Path(argv[argv.index("--spec") + 1])
    bericht_pfad = tmp_path / "berichte" / "abnahme.html"
    bericht_pfad.parent.mkdir(parents=True, exist_ok=True)
    bericht_pfad.hardlink_to(spec_pfad)

    result = main(argv)

    assert (result.status, result.exit_code) == ("failed", Exit.USAGE)
    assert "paarweise verschiedene Dateien" in result.errors[0]["message"]
    assert spec_pfad.read_text(encoding="utf-8") == _spec().model_dump_json()


@pytest.mark.parametrize("kollision", ["bericht", "spec"])
def test_kommando_blockiert_kollision_mit_eigenem_gate_ledger(
        tmp_path, kollision) -> None:
    """Das Ledger darf weder Bericht noch ein Pflichtartefakt ueberschreiben."""
    suite_pfad = tmp_path / "suite.json"
    suite_pfad.write_text(json.dumps(
        _vollstaendige_suite(_pruefung("P-1"))), encoding="utf-8")
    argv = _basis_argv(tmp_path, suite_pfad)
    ledger_pfad = tmp_path / "diagnostics" / "abnahmebericht.gate.json"
    ledger_pfad.parent.mkdir(parents=True, exist_ok=True)
    if kollision == "bericht":
        argv[argv.index("--bericht") + 1] = str(ledger_pfad)
    else:
        ledger_pfad.write_text(_spec().model_dump_json(), encoding="utf-8")
        argv[argv.index("--spec") + 1] = str(ledger_pfad)

    result = main(argv)

    assert (result.status, result.exit_code) == ("failed", Exit.USAGE)
    assert "Gate-Ledger" in result.errors[0]["message"]
    if kollision == "bericht":
        assert not ledger_pfad.exists()
    else:
        assert ledger_pfad.read_text(encoding="utf-8") == _spec().model_dump_json()
    # Der Lauf laesst das kollidierende Artefakt bewusst unangetastet und
    # schreibt deshalb KEINEN Ledger — dann kann an diesem Pfad ein aelterer
    # Beleg stehen bleiben. Das muss in der Antwort stehen, sonst haelt eine
    # Automatisierung den Altbeleg fuer das Ergebnis dieses Laufs.
    assert any(
        eintrag["code"] == "ledger_nicht_geschrieben"
        for eintrag in result.errors
    ), "Der ungeschriebene Ledger muss im Ergebnis ausgewiesen sein"


def test_kollision_laesst_alten_gruenen_ledger_stehen_und_sagt_es(
        tmp_path) -> None:
    """Dokumentierte Ausnahme, festgenagelt (ADR-009 Nachtrag).

    Zeigt eine Artefaktrolle auf den Ledger-Pfad, schreibt das Kommando
    keinen Ledger — auch keinen roten Startbeleg. Ein dort liegender
    gruener Altbeleg ueberlebt den roten Lauf also unveraendert. Das ist
    gewollt (sonst zerstoerte der Lauf das Pflichtartefakt), darf aber
    nicht still passieren.
    """
    suite_pfad = tmp_path / "suite.json"
    suite_pfad.write_text(json.dumps(
        _vollstaendige_suite(_pruefung("P-1"))), encoding="utf-8")
    argv = _basis_argv(tmp_path, suite_pfad)
    ledger_pfad = tmp_path / "diagnostics" / "abnahmebericht.gate.json"
    ledger_pfad.parent.mkdir(parents=True, exist_ok=True)
    altbeleg = json.dumps({"status": "passed", "exit_code": 0}, sort_keys=True)
    ledger_pfad.write_text(altbeleg, encoding="utf-8")
    argv[argv.index("--spec") + 1] = str(ledger_pfad)

    result = main(argv)

    assert result.exit_code == Exit.USAGE
    assert ledger_pfad.read_text(encoding="utf-8") == altbeleg
    hinweis = [
        eintrag for eintrag in result.errors
        if eintrag["code"] == "ledger_nicht_geschrieben"
    ]
    assert hinweis, "Der Lauf muss den ungeschriebenen Ledger ausweisen"
    assert "belegt NICHT diesen Lauf" in hinweis[0]["message"]


@pytest.mark.parametrize(
    ("aenderung", "code", "meldung"),
    [
        ("zeilenverlust", "zeilenverlust", "2 Quellzeilen"),
        ("transformationsbefund", "transformationsbefund", "Zeile 2"),
        ("offener_konflikt", "offener_konflikt", "STORNO_KZ"),
    ],
)
def test_kommando_blockiert_transformationshindernisse_sichtbar(
        tmp_path, aenderung, code, meldung) -> None:
    suite_pfad = tmp_path / "suite.json"
    suite_pfad.write_text(json.dumps(
        _vollstaendige_suite(_pruefung("P-1"))), encoding="utf-8")
    argv = _basis_argv(tmp_path, suite_pfad)
    if aenderung == "offener_konflikt":
        spec = _spec()
        spec.offene_konflikte[0].entscheidung = None
        (tmp_path / "spec.json").write_text(
            spec.model_dump_json(), encoding="utf-8")
    else:
        transformation = {
            "zeilen_quelle": 2,
            "zeilen_ziel": 1 if aenderung == "zeilenverlust" else 2,
            "befunde": (
                ["Zeile 2 kann nicht transformiert werden"]
                if aenderung == "transformationsbefund" else []
            ),
        }
        (tmp_path / "transformation.json").write_text(
            json.dumps(transformation), encoding="utf-8")

    result = main(argv)

    assert (result.exit_code, result.status) == (Exit.GOLDEN_MASTER, "failed")
    assert code in [fehler["code"] for fehler in result.errors]
    assert meldung in " ".join(fehler["message"] for fehler in result.errors)
    assert result.summary["abnahmehindernisse"]
    text = (tmp_path / "berichte" / "abnahme.html").read_text(encoding="utf-8")
    assert "ABNAHMEBERICHT NICHT BESTANDEN" in text
    assert "ALLE ABNAHMETESTS BESTANDEN" not in text


@pytest.mark.parametrize(
    "transformation",
    [
        {"zeilen_quelle": 2, "zeilen_ziel": 2},
        {"zeilen_quelle": True, "zeilen_ziel": 2, "befunde": []},
        {"zeilen_quelle": 2, "zeilen_ziel": -1, "befunde": []},
        {"zeilen_quelle": 2, "zeilen_ziel": 2, "befunde": "keine"},
    ],
)
def test_kommando_weist_unpruefbares_transformationsergebnis_zurueck(
        tmp_path, transformation) -> None:
    suite_pfad = tmp_path / "suite.json"
    suite_pfad.write_text(json.dumps(
        _vollstaendige_suite(_pruefung("P-1"))), encoding="utf-8")
    argv = _basis_argv(tmp_path, suite_pfad)
    (tmp_path / "transformation.json").write_text(
        json.dumps(transformation), encoding="utf-8")

    result = main(argv)

    assert (result.exit_code, result.status) == (Exit.FILE_CONTRACT, "failed")
    assert result.errors[0]["code"] == "transformation_ergebnis_contract"
    assert not (tmp_path / "berichte" / "abnahme.html").exists()


@pytest.mark.parametrize(
    ("aenderung", "meldung"),
    [
        ("leere_entscheidung", "leere Entscheidung"),
        ("leerer_entscheider", "ohne nichtleeren"),
        ("ungueltiger_sha", "quelle_sha256"),
        ("falsche_aritaet", "braucht genau 1 Quellspalte"),
    ],
)
def test_kommando_fuehrt_validate_spec_vor_dem_rendern_aus(
        tmp_path, aenderung, meldung) -> None:
    suite_pfad = tmp_path / "suite.json"
    suite_pfad.write_text(json.dumps(
        _vollstaendige_suite(_pruefung("P-1"))), encoding="utf-8")
    argv = _basis_argv(tmp_path, suite_pfad)
    spec = _spec()
    if aenderung == "leere_entscheidung":
        spec.offene_konflikte[0].entscheidung = "   "
    elif aenderung == "leerer_entscheider":
        spec.offene_konflikte[0].entscheider = ""
    elif aenderung == "ungueltiger_sha":
        spec.quelle_sha256 = "z" * 64
    else:
        spec.felder = [
            (
                FeldMapping(
                    ziel="duration",
                    typ="berechnung",
                    quellen=[],
                    berechnung="ganzzahl",
                    begruendung="ungueltige Null-Arity",
                )
                if feld.ziel == "duration" else feld
            )
            for feld in spec.felder
        ]
    (tmp_path / "spec.json").write_text(
        spec.model_dump_json(), encoding="utf-8")

    result = main(argv)

    assert (result.exit_code, result.status) == (Exit.FILE_CONTRACT, "failed")
    assert result.errors[0]["code"] == "spec_contract"
    assert meldung in " ".join(fehler["message"] for fehler in result.errors)
    assert not (tmp_path / "berichte" / "abnahme.html").exists()


def test_kommando_weist_frisierte_zusammenfassung_zurueck(tmp_path) -> None:
    """Eine nachgebesserte Suite-Zusammenfassung ist ein Contract-Bruch.

    Ohne diese Pruefung koennte ein von Hand auf ``suite_bestanden:
    true`` gesetztes JSON eine gruene Urkunde ueber ein Urteil erzeugen,
    das die Suite nie gefaellt hat.
    """
    suite_pfad = _suite_datei(
        tmp_path, _pruefung("P-1"), _pruefung("P-2", dk1_versatz=500.0))
    daten = json.loads(suite_pfad.read_text(encoding="utf-8"))
    daten["suite_bestanden"] = True
    daten["bestanden"], daten["fehlgeschlagen"] = 2, 0
    suite_pfad.write_text(json.dumps(daten), encoding="utf-8")

    result = main(_basis_argv(tmp_path, suite_pfad))

    assert (result.exit_code, result.status) == (Exit.FILE_CONTRACT, "failed")
    meldungen = " ".join(e["message"] for e in result.errors)
    assert "suite_bestanden" in meldungen and "bestanden" in meldungen
    assert not (tmp_path / "berichte" / "abnahme.html").exists()
    assert _ledger(tmp_path / "diagnostics").status == "failed"


def test_kommando_weist_roten_einzelvergleich_unter_gruener_zusammenfassung_zurueck(
        tmp_path) -> None:
    """Ein roter atomarer Vergleich darf nicht als gruen umetikettiert werden."""
    suite_pfad = _suite_datei(
        tmp_path, _pruefung("P-1"), _pruefung("P-2", dk1_versatz=500.0))
    daten = json.loads(suite_pfad.read_text(encoding="utf-8"))
    assert daten["vertraege"][1]["pruefungen"][0]["ok"] is False
    daten["vertraege"][1]["pruefungen"][0]["ok"] = True
    daten["vertraege"][1]["bestanden"] = True
    daten["bestanden"], daten["fehlgeschlagen"] = 2, 0
    daten["suite_bestanden"] = True
    suite_pfad.write_text(json.dumps(daten), encoding="utf-8")

    result = main(_basis_argv(tmp_path, suite_pfad))

    assert (result.exit_code, result.status) == (Exit.FILE_CONTRACT, "failed")
    meldungen = " ".join(e["message"] for e in result.errors)
    assert "vertraege[1]" in meldungen and "'ok'" in meldungen
    assert "bestanden" in meldungen
    assert "suite_bestanden" in meldungen
    assert not (tmp_path / "berichte" / "abnahme.html").exists()


def test_kommando_weist_gruenes_urteil_ohne_einzelpruefung_zurueck(
        tmp_path) -> None:
    """``all([])`` darf keine Urkunde ueber null Vergleiche begruenen."""
    suite_pfad = _suite_datei(tmp_path, _pruefung("P-1"))
    daten = json.loads(suite_pfad.read_text(encoding="utf-8"))
    urteil = daten["vertraege"][0]
    urteil["pruefungen"] = []
    urteil["nicht_geprueft"] = []
    daten["pruefluecken"] = []
    daten["vollstaendig_geprueft"] = True
    suite_pfad.write_text(json.dumps(daten), encoding="utf-8")

    result = main(_basis_argv(tmp_path, suite_pfad))

    assert (result.exit_code, result.status) == (Exit.FILE_CONTRACT, "failed")
    meldungen = " ".join(e["message"] for e in result.errors)
    assert "bestanden" in meldungen and "Einzelprüfungen" in meldungen
    assert not (tmp_path / "berichte" / "abnahme.html").exists()


def test_kommando_weist_widerspruechliches_residuum_zurueck(tmp_path) -> None:
    suite_pfad = _suite_datei(tmp_path, _pruefung("P-1"))
    daten = json.loads(suite_pfad.read_text(encoding="utf-8"))
    daten["vertraege"][0]["pruefungen"][0]["residuum"] += 1.0
    suite_pfad.write_text(json.dumps(daten), encoding="utf-8")

    result = main(_basis_argv(tmp_path, suite_pfad))

    assert (result.exit_code, result.status) == (Exit.FILE_CONTRACT, "failed")
    assert "residuum" in " ".join(e["message"] for e in result.errors)
    assert not (tmp_path / "berichte" / "abnahme.html").exists()


def test_kommando_weist_nicht_darstellbare_json_ganzzahl_zurueck(
        tmp_path) -> None:
    """Ein syntaktisch gueltiger Riesen-Integer ist ein Contract-Fehler."""
    suite_pfad = _suite_datei(tmp_path, _pruefung("P-1"))
    daten = json.loads(suite_pfad.read_text(encoding="utf-8"))
    daten["vertraege"][0]["pruefungen"][0]["system"] = 10 ** 400
    suite_pfad.write_text(json.dumps(daten), encoding="utf-8")

    result = main(_basis_argv(tmp_path, suite_pfad))

    assert (result.exit_code, result.status) == (Exit.FILE_CONTRACT, "failed")
    assert "endliche Zahl" in " ".join(e["message"] for e in result.errors)


@pytest.mark.parametrize(
    ("feld", "wert"),
    [("suite_bestanden", 1), ("vollstaendig_geprueft", 0)],
)
def test_kommando_weist_nicht_boolesche_suiteurteile_zurueck(
        tmp_path, feld, wert) -> None:
    suite_pfad = _suite_datei(tmp_path, _pruefung("P-1"))
    daten = json.loads(suite_pfad.read_text(encoding="utf-8"))
    daten[feld] = wert
    suite_pfad.write_text(json.dumps(daten), encoding="utf-8")

    result = main(_basis_argv(tmp_path, suite_pfad))

    assert (result.exit_code, result.status) == (Exit.FILE_CONTRACT, "failed")
    assert feld in " ".join(e["message"] for e in result.errors)


@pytest.mark.parametrize("feld", ["anzahl", "bestanden", "fehlgeschlagen"])
def test_kommando_weist_nicht_ganzzahlige_zaehler_zurueck(
        tmp_path, feld) -> None:
    suite_pfad = _suite_datei(tmp_path, _pruefung("P-1"))
    daten = json.loads(suite_pfad.read_text(encoding="utf-8"))
    daten[feld] = True
    suite_pfad.write_text(json.dumps(daten), encoding="utf-8")

    result = main(_basis_argv(tmp_path, suite_pfad))

    assert (result.exit_code, result.status) == (Exit.FILE_CONTRACT, "failed")
    assert feld in " ".join(e["message"] for e in result.errors)


def test_kommando_blockiert_bei_befund_der_pruefmenge(tmp_path) -> None:
    """Alle Verträge bestanden, aber die Menge stimmt nicht -> rot."""
    pfad = tmp_path / "suite.json"
    pfad.write_text(json.dumps(pruefe_bestand(
        [_pruefung("P-1"), _pruefung("P-2")], erwartete_anzahl=500)),
        encoding="utf-8")

    result = main(_basis_argv(tmp_path, pfad))

    assert (result.exit_code, result.status) == (Exit.GOLDEN_MASTER, "failed")
    assert result.summary["fehlgeschlagen"] == 0      # kein Vertrag ist schuld
    assert result.summary["mengenbefunde"] == 1
    assert result.summary["erwartete_anzahl"] == 500
    codes = [e["code"] for e in result.errors]
    assert codes[0] == "mengenbefund"
    assert "498 Verträge fehlen" in result.errors[0]["message"]


def test_kommando_traegt_die_pruefluecken_in_den_ledger(tmp_path) -> None:
    suite_pfad = _suite_datei(tmp_path, _pruefung("P-1"))
    result = main(_basis_argv(tmp_path, suite_pfad))
    assert (result.exit_code, result.status) == (Exit.GOLDEN_MASTER, "failed")
    assert result.summary["vollstaendig_geprueft"] is False
    assert any("bjb_stichtag_1" in l for l in result.summary["pruefluecken"])
    assert "pruefluecke" in [fehler["code"] for fehler in result.errors]
    text = (tmp_path / "berichte" / "abnahme.html").read_text(encoding="utf-8")
    assert "ABNAHMEBERICHT NICHT BESTANDEN" in text
    eintrag = _ledger(tmp_path / "diagnostics")
    assert eintrag.status == "failed"
    assert eintrag.summary["vollstaendig_geprueft"] is False


def test_kommando_weist_suite_ohne_mengenangaben_zurueck(tmp_path) -> None:
    """Ein Suite-JSON ohne die Mengen-Felder ist ein Contract-Bruch.

    Sonst könnte ein altes oder von Hand gebautes Ergebnis eine Vorlage
    erzeugen, in der Vollständigkeit und Prüflücken schlicht fehlen.
    """
    suite_pfad = _suite_datei(tmp_path, _pruefung("P-1"))
    daten = json.loads(suite_pfad.read_text(encoding="utf-8"))
    for feld in ("erwartete_anzahl", "mengenbefunde", "pruefluecken",
                 "vollstaendig_geprueft"):
        del daten[feld]
    suite_pfad.write_text(json.dumps(daten), encoding="utf-8")

    result = main(_basis_argv(tmp_path, suite_pfad))

    assert result.exit_code == Exit.FILE_CONTRACT
    meldungen = " ".join(e["message"] for e in result.errors)
    for feld in ("erwartete_anzahl", "mengenbefunde", "pruefluecken",
                 "vollstaendig_geprueft"):
        assert feld in meldungen
    assert not (tmp_path / "berichte" / "abnahme.html").exists()


@pytest.mark.parametrize("wert", ["500", 4.7, True, [500]])
def test_kommando_weist_falsche_erwartete_anzahl_zurueck(
        tmp_path, wert) -> None:
    """Falscher Typ ist ein Contract-Bruch, kein Absturz.

    Der Bericht setzt die erwartete Vertragszahl als ganze Zahl
    (``int(...)``): ein Text oder eine Liste liesse das Kommando mit
    einem Traceback statt mit Exit 20 enden, ein Float schnitte still ab
    (4.7 -> 4). Beides ist im Kopf einer Abnahme-Urkunde nicht
    hinnehmbar.
    """
    suite_pfad = _suite_datei(tmp_path, _pruefung("P-1"))
    daten = json.loads(suite_pfad.read_text(encoding="utf-8"))
    daten["erwartete_anzahl"] = wert
    suite_pfad.write_text(json.dumps(daten), encoding="utf-8")

    result = main(_basis_argv(tmp_path, suite_pfad))

    assert (result.exit_code, result.status) == (Exit.FILE_CONTRACT, "failed")
    assert "erwartete_anzahl" in result.errors[0]["message"]
    assert not (tmp_path / "berichte" / "abnahme.html").exists()
    assert _ledger(tmp_path / "diagnostics").status == "failed"


def test_kommando_traegt_die_gelieferte_erwartete_anzahl(tmp_path) -> None:
    """Die Gegenprobe: eine ganze Zahl und ``null`` bleiben zulaessig."""
    pfad = tmp_path / "suite.json"
    pfad.write_text(json.dumps(
        _vollstaendige_suite(_pruefung("P-1"))), encoding="utf-8")
    fall, pflicht = _gebundene_plicht_argv(tmp_path, 1)
    result = main([
        "--fall", str(fall), "--suite", str(pfad), "--titel", "T",
        "--stichtag-1", "2026-01-01", "--stichtag-2", "2027-01-01",
        "--bericht", str(tmp_path / "berichte" / "abnahme.html"),
        "--diagnostics-dir", str(tmp_path / "diagnostics"),
        *pflicht,
    ])
    assert result.exit_code == Exit.OK
    assert result.summary["erwartete_anzahl"] == 1
    text = (tmp_path / "berichte" / "abnahme.html").read_text(encoding="utf-8")
    assert "<b>1</b>" in text


def test_kommando_weist_frisierte_luecken_zurueck(tmp_path) -> None:
    """``vollstaendig_geprueft`` muss zu den Lücken passen."""
    suite_pfad = _suite_datei(tmp_path, _pruefung("P-1"))
    daten = json.loads(suite_pfad.read_text(encoding="utf-8"))
    assert daten["pruefluecken"]                      # es GIBT Lücken ...
    daten["vollstaendig_geprueft"] = True             # ... behauptet wird nein
    suite_pfad.write_text(json.dumps(daten), encoding="utf-8")

    result = main(_basis_argv(tmp_path, suite_pfad))

    assert result.exit_code == Exit.FILE_CONTRACT
    assert "vollstaendig_geprueft" in result.errors[0]["message"]


def test_kommando_weist_leere_pruefmenge_zurueck(tmp_path) -> None:
    suite_pfad = tmp_path / "leer.json"
    suite_pfad.write_text(json.dumps({
        "anzahl": 0, "bestanden": 0, "fehlgeschlagen": 0,
        "suite_bestanden": True, "erwartete_anzahl": 0,
        "mengenbefunde": [], "pruefluecken": [],
        "vollstaendig_geprueft": True, "vertraege": []}), encoding="utf-8")
    result = main(_basis_argv(tmp_path, suite_pfad))
    assert result.exit_code == Exit.FILE_CONTRACT
    assert "leere" in result.errors[0]["message"]


def test_kommando_nutzt_die_fall_vorgaben(tmp_path) -> None:
    suite_pfad = tmp_path / "suite.json"
    suite_pfad.write_text(json.dumps(
        _vollstaendige_suite(_pruefung("P-1"))), encoding="utf-8")
    fall, pflicht = _gebundene_plicht_argv(tmp_path, 1)
    result = main([
        "--fall", str(fall), "--suite", str(suite_pfad),
        "--titel", "T", "--stichtag-1", "a", "--stichtag-2", "b",
        *pflicht,
    ])
    assert result.exit_code == Exit.OK
    bericht = fall / "abgeleitet" / "berichte" / "migrationsabnahme.html"
    assert bericht.is_file()
    assert result.paths["bericht"] == str(bericht)
    assert (fall / "abgeleitet" / "diagnostics"
            / "abnahmebericht.gate.json").is_file()


def test_kommando_mit_fall_aber_ohne_registrierte_quelle_bleibt_rot(
        tmp_path) -> None:
    from rechner_pipeline.fall import anlegen

    fall = tmp_path / "fall"
    anlegen(fall)
    suite_pfad = tmp_path / "suite.json"
    suite_pfad.write_text(json.dumps(
        _vollstaendige_suite(_pruefung("P-1"))), encoding="utf-8")

    result = main([
        "--fall", str(fall), "--suite", str(suite_pfad),
        "--titel", "T", "--stichtag-1", "a", "--stichtag-2", "b",
        *_pflicht_argv(tmp_path),
    ])

    assert (result.exit_code, result.status) == (Exit.GOLDEN_MASTER, "failed")
    assert result.summary["bericht_bestanden"] is False
    meldungen = " ".join(fehler["message"] for fehler in result.errors)
    assert "nicht registriert" in meldungen
    text = (fall / "abgeleitet" / "berichte" / "migrationsabnahme.html").read_text(
        encoding="utf-8")
    assert "ALLE ABNAHMETESTS BESTANDEN" not in text


def test_kommando_gibt_genau_ein_json_auf_stdout(tmp_path, capsys) -> None:
    suite_pfad = _suite_datei(
        tmp_path, _pruefung("P-1"), _pruefung("P-2", dk1_versatz=500.0))

    rc = run_command(main, _basis_argv(tmp_path, suite_pfad))

    ausgabe = capsys.readouterr().out
    assert ausgabe.count("\n") == 1
    daten = json.loads(ausgabe)
    assert daten["command"] == "abnahmebericht" and daten["gate"] == GATE
    assert daten["exit_code"] == rc == Exit.GOLDEN_MASTER
    assert daten["status"] == "failed"
    assert daten["schema_version"] == 1


def test_gate_rechnet_die_komponentenskalierte_toleranz_nach(
        tmp_path) -> None:
    """Ausweitung Nr. 22 des zweiten Laufs: Das Gate verwarf exakt die
    vier Urteile, die die Suite seit Korrektur 21 komponentenskaliert
    richtig faellt — seine eigene Nachrechnung nutzte das flache
    Toleranzpaar. Jetzt steht die Komponentenzahl als Zaehler an jeder
    Pruefung und das Gate rechnet mit ihr nach: Ein 0,023-Residuum bei
    sechs Komponenten ist gruen, OHNE den Zaehler bleibt es rot."""
    import json

    suite_pfad = _suite_datei(tmp_path, _pruefung("P-1"))
    daten = json.loads(suite_pfad.read_text(encoding="utf-8"))
    p = daten["vertraege"][0]["pruefungen"][0]
    # Delta ZWISCHEN der flachen Grenze (max aus abs 0,02 und
    # rel 1e-6) und der 6-Komponenten-Grenze — nur die Skalierung
    # entscheidet dann das Urteil (Zonen-Beleg).
    flach = max(0.02, abs(p["erwartet"]) * 1e-6)
    skaliert = max(0.02 + 5 * 0.005, abs(p["erwartet"]) * 1e-6)
    assert flach < skaliert, "Fixture-Wert zu gross fuer den Zonen-Test"
    delta = (flach + skaliert) / 2
    p["system"] = p["erwartet"] + delta
    p["residuum"] = p["system"] - p["erwartet"]
    p["komponenten"] = 6
    p["ok"] = True
    suite_pfad.write_text(json.dumps(daten), encoding="utf-8")
    result = main(_basis_argv(tmp_path, suite_pfad))
    meldungen = " ".join(e["message"] for e in result.errors)
    assert "'ok'" not in meldungen, meldungen
    assert result.exit_code != Exit.FILE_CONTRACT

    # Ohne den Zaehler ist dasselbe Urteil eine Umetikettierung —
    # der suite_contract-Fehler steht in den Meldungen (der Exit-Code
    # kann von anderen, hier unbeteiligten Blockern der Fixture
    # dominiert werden).
    p.pop("komponenten")
    suite_pfad.write_text(json.dumps(daten), encoding="utf-8")
    result = main(_basis_argv(tmp_path, suite_pfad))
    meldungen = " ".join(e["message"] for e in result.errors)
    assert "'ok'" in meldungen


def test_eingebettete_spec_ist_die_dateiform(tmp_path) -> None:
    """Ausweitung Nr. 23 des zweiten Laufs (A-M4-Zeichnungsblocker):
    Der Entscheid vergleicht bericht_erzeugung.spec strukturell mit
    der per SHA gebundenen Datei — eine SPARSE geschriebene Spec
    (Default-Felder ausgelassen, wie transformiere-quellbestand sie
    erzeugt) kann einer vollstaendigen model_dump_json-Zweitform NIE
    gleich sein (im Lauf: 17 fehlende Default-Felder). Eingebettet
    wird jetzt die geparste DATEI-Form."""
    import json

    suite_pfad = _suite_datei(tmp_path, _pruefung("P-1"))
    argv = _basis_argv(tmp_path, suite_pfad)
    spec_pfad = tmp_path / "spec.json"
    sparse = _spec().model_dump_json(exclude_defaults=True)
    spec_pfad.write_text(sparse, encoding="utf-8")
    assert json.loads(sparse) != json.loads(_spec().model_dump_json()), \
        "Fixture-Spec traegt keine Default-Felder — Zonen-Beleg leer"

    main(argv)

    ledger_pfade = sorted((tmp_path / "diagnostics").glob("*.json"))
    assert ledger_pfade, "kein Diagnostics-Ledger geschrieben"
    daten = json.loads(ledger_pfade[-1].read_text(encoding="utf-8"))
    def _finde_spec(obj):
        if isinstance(obj, dict):
            if "bericht_erzeugung" in obj:
                return obj["bericht_erzeugung"]["spec"]
            for wert in obj.values():
                treffer = _finde_spec(wert)
                if treffer is not None:
                    return treffer
        if isinstance(obj, list):
            for wert in obj:
                treffer = _finde_spec(wert)
                if treffer is not None:
                    return treffer
        return None
    eingebettet = _finde_spec(daten)
    assert eingebettet is not None, "bericht_erzeugung.spec nicht im Ledger"
    assert eingebettet == json.loads(sparse)
