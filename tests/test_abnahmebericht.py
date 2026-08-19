"""Migrationsabnahmebericht (gates/abnahmebericht): G-2-Vorlage als HTML.

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
nicht überschreitet: es nimmt nicht ab (Gate G-2 bleibt beim Menschen).

Knoten: klv
"""

from __future__ import annotations

import dataclasses
import json

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
            FeldMapping(ziel="status", typ="kodierung", quellen=["RK"],
                        kodierung={"NR": "nichtraucher", "R": "raucher"},
                        begruendung="Risikoklasse"),
            FeldMapping(typ="nicht_uebernommen", quellen=["GESCHL"],
                        begruendung="<Tarif rechnet unisex>"),
        ],
        offene_konflikte=[OffenerKonflikt(
            quellspalte="STORNO_KZ", frage="Bedeutung von 'S'?",
            entscheidung="<entschieden durch den Menschen>",
            entscheider="bartek")],
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
    assert ("entschieden (bartek): "
            "&lt;entschieden durch den Menschen&gt;") in text
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


def test_bericht_weist_pruefluecken_neben_dem_gruenen_verdikt_aus() -> None:
    """Grün heißt nicht lückenlos — und der Bericht sagt es.

    Ohne gelieferten Jahresbeitrag ist die Prüfung unvollständig. Das
    Verdikt bleibt grün (kein Fehlschlag), muss die Lücke aber neben
    sich stehen haben, sonst liest ein Gremium eine Urkunde über eine
    Prüfung, die so nie stattgefunden hat.
    """
    suite = pruefe_bestand([_pruefung("P-1")])
    text = baue_bericht(titel="t", stichtag_1="s1", stichtag_2="s2",
                        suite=suite)
    assert "ALLE ABNAHMETESTS BESTANDEN (1 von 1 Verträgen)" in text
    assert "PRÜFLÜCKE(N)" in text
    assert "Prüflücken (was NICHT geprüft wurde)" in text
    assert "bjb_stichtag_1" in text
    assert "nicht angegeben" in text            # keine erwartete Vertragszahl

    # Mit vollständiger Lieferung verschwindet der Lückenblock:
    voll = pruefe_bestand(
        [dataclasses.replace(
            _pruefung("P-1"),
            bjb_erwartet_1=round(KERN.gross_annual_premium(), 2))],
        erwartete_anzahl=1)
    text_voll = baue_bericht(titel="t", stichtag_1="s1", stichtag_2="s2",
                             suite=voll)
    assert "PRÜFLÜCKE(N)" not in text_voll
    assert "Keine — jede Prüfgröße war geliefert." in text_voll
    assert "bjb_stichtag_1" in text_voll        # als Prüfgröße, nicht als Lücke


def test_gruenes_verdikt_hat_genau_einen_schlusspunkt() -> None:
    """Der Kopfsatz wird projiziert — kein doppelter Punkt nach "s. u.".

    Der Lückenzusatz endet selbst auf einem Punkt; die Vorlage darf
    keinen zweiten anhängen. Ohne Lücken muss der Satz dagegen sehr wohl
    mit Punkt enden.
    """
    mit_luecke = baue_bericht(
        titel="t", stichtag_1="s1", stichtag_2="s2",
        suite=pruefe_bestand([_pruefung("P-1")]))
    assert "s. u..." not in mit_luecke and "s. u..</p>" not in mit_luecke
    assert "PRÜFLÜCKE(N), s. u.</p>" in mit_luecke

    ohne_luecke = baue_bericht(
        titel="t", stichtag_1="s1", stichtag_2="s2",
        suite=pruefe_bestand(
            [dataclasses.replace(
                _pruefung("P-1"),
                bjb_erwartet_1=round(KERN.gross_annual_premium(), 2))],
            erwartete_anzahl=1))
    assert "(1 von 1 Verträgen).</p>" in ohne_luecke


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
    suite = pruefe_bestand([_pruefung("P-1")])
    args = dict(titel="t", stichtag_1="s1", stichtag_2="s2",
                suite=suite, spec=_spec())
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
    ]


def test_kommando_gruen_schreibt_bericht_und_ledger(tmp_path) -> None:
    suite_pfad = _suite_datei(tmp_path, _pruefung("P-1"), _pruefung("P-2"))
    spec_pfad = tmp_path / "spec.json"
    spec_pfad.write_text(_spec().model_dump_json(), encoding="utf-8")

    result = main(_basis_argv(tmp_path, suite_pfad)
                  + ["--spec", str(spec_pfad),
                     "--bestandsbericht-vor", "vor/index.html"])

    assert (result.exit_code, result.status) == (Exit.OK, "passed")
    assert result.gate == GATE
    bericht = tmp_path / "berichte" / "abnahme.html"
    text = bericht.read_text(encoding="utf-8")
    assert "ALLE ABNAHMETESTS BESTANDEN (2 von 2" in text
    assert "POLNR" in text and "vor/index.html" in text
    # Provenienz: Eingaben UND Ausgabe gehasht (ein bestandenes Gate ohne
    # input_hashes wuerde das Dossier blockieren).
    assert result.input_hashes and str(suite_pfad) in str(result.input_hashes)
    assert list(result.output_hashes) == [str(bericht)]
    assert result.summary["bestanden"] == 2
    assert result.summary["mapping_tabelle"] is True
    # Das Kommando nimmt NICHT ab — die Entscheidung bleibt beim Menschen.
    assert "G-2" in result.summary["abnahme"]

    eintrag = _ledger(tmp_path / "diagnostics")
    assert (eintrag.gate, eintrag.command) == (GATE, "abnahmebericht")
    assert (eintrag.status, eintrag.summary["exit_code"]) == ("passed", 0)
    assert eintrag.required is True
    assert (tmp_path / "diagnostics" / "abnahmebericht.gate.json").is_file()


def test_kommando_rot_blockiert_und_schreibt_den_bericht_trotzdem(
        tmp_path) -> None:
    suite_pfad = _suite_datei(
        tmp_path, _pruefung("P-1"), _pruefung("P-2", dk1_versatz=500.0))

    result = main(_basis_argv(tmp_path, suite_pfad))

    assert (result.exit_code, result.status) == (Exit.GOLDEN_MASTER, "failed")
    # Gerade der rote Bericht ist das Beweisstueck fuer die G-2-Vorlage.
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
    assert result.exit_code == Exit.OK                # Lücke blockiert nicht
    assert result.summary["vollstaendig_geprueft"] is False
    assert any("bjb_stichtag_1" in l for l in result.summary["pruefluecken"])
    eintrag = _ledger(tmp_path / "diagnostics")
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
    pfad.write_text(json.dumps(pruefe_bestand(
        [_pruefung("P-1")], erwartete_anzahl=1)), encoding="utf-8")
    result = main(_basis_argv(tmp_path, pfad))
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
    fall = tmp_path / "fall"
    suite_pfad = _suite_datei(tmp_path, _pruefung("P-1"))
    result = main(["--fall", str(fall), "--suite", str(suite_pfad),
                   "--titel", "T", "--stichtag-1", "a", "--stichtag-2", "b"])
    assert result.exit_code == Exit.OK
    bericht = fall / "abgeleitet" / "berichte" / "migrationsabnahme.html"
    assert bericht.is_file()
    assert result.paths["bericht"] == str(bericht)
    assert (fall / "abgeleitet" / "diagnostics"
            / "abnahmebericht.gate.json").is_file()


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
