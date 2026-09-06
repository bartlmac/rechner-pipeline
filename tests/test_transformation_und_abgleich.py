"""Plan P5+P6: Transformations-Spec und Abzugsabgleich.

Sichert die beiden Migrations-Maschinerien VOR ihrem ersten echten
Einsatz (Baldrian-Fall): das Mapping ist beidseitig geprueft und
deterministisch angewandt; der Abgleich loest eine Diskrepanz nur dann
automatisch auf, wenn die Belege genau EINE Lesart stuetzen und die
verworfene Lesart NICHT aus der Meldung stammt (harte Regel der
Projektleitung 2026-08-18). Sonst bleibt die Aufloesung beim Menschen.

Die Zahlen der Testfaelle sind Mechanik-Beispiele, keine Aussage ueber
die Aufloesung eines konkreten Migrationsfalls.

EHRLICHKEIT UEBER DIE ERWARTUNGSQUELLE (Abgleich-Haelfte): Die Belege
der Abgleich-Tests entstehen ueber ``berechne`` — denselben Kern, den
der Abgleich intern rechnet. Ein Rechenfehler des Kerns faellt hier
also NICHT auf; das leisten Golden Master und die eingefrorenen
Fall-Referenzwerte. Geprueft wird die URTEILSLOGIK: wann automatisch aufgeloest werden darf, wann
die Beleglage zu duenn ist, wann ein Ausreisser keine Verwerfung ist
und welcher Beleg als schlechtester benannt wird. Diese Erwartungen
sind vom Kern unabhaengig — sie folgen aus den Schwellwerten und aus
der Konstruktion des jeweiligen Belegsatzes.

Knoten: klv

"""

from __future__ import annotations

import csv
import dataclasses

import pytest

from rechner_pipeline.kern import KLV_DEFAULT, berechne
from rechner_pipeline.ontologie.transformation import (
    BERECHNUNGEN,
    FeldMapping,
    OffenerKonflikt,
    TransformationsSpec,
    _parse_datum,
    validate_spec,
)
from rechner_pipeline.gates.transformation_anwenden import wende_an
from rechner_pipeline.qa.abzugsabgleich import (
    MIND_BELEGE,
    VERWERFUNGS_QUOTE,
    Lesart,
    VertragsBeleg,
    gleiche_ab,
    pruefe_lesart,
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
            FeldMapping(ziel="sex", typ="kodierung", quellen=["GESCHL"],
                        kodierung={"M": "M", "W": "F"},
                        begruendung="Quelle schreibt M/W, der Kern-Contract "
                                    "fuehrt M/F"),
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


QUELLSPALTEN = ["POLNR", "BEGINN", "GEBDAT", "GESCHL", "n", "t", "ERLSUMME",
                "ZAHLW", "RK", "BGRP", "TARIF"]

ZEILE = {
    "POLNR": "7000001", "BEGINN": "01.06.2015", "GEBDAT": "01.06.1976",
    "GESCHL": "W", "n": "20", "t": "15", "ERLSUMME": "87000",
    "ZAHLW": "monatlich", "RK": "NR", "BGRP": "K", "TARIF": "KLV15",
}


def _registriere_testquelle(tmp_path, spec, zeilen, *, quellspalten=None):
    """CSV registrieren und ihren Fall fuer die Transformations-API liefern."""
    nummer = len(list(tmp_path.glob("fall-*")))
    lieferung = tmp_path / f"lieferung-{nummer}"
    lieferung.mkdir()
    quelle = lieferung / spec.quelle_datei
    spalten = list(quellspalten or QUELLSPALTEN)
    with quelle.open("w", encoding="utf-8", newline="") as datei:
        writer = csv.DictWriter(
            datei, fieldnames=spalten, delimiter=";", extrasaction="ignore")
        writer.writeheader()
        writer.writerows(zeilen)
    from rechner_pipeline.fall import anlegen, registrieren

    fall = tmp_path / f"fall-{nummer}"
    anlegen(fall)
    registrierung = registrieren(fall, quelle)
    spec.quelle_sha256 = registrierung["sha256"]
    return fall


def _wende_testquelle(tmp_path, spec, zeilen, *, quellspalten=None):
    """Die Transformations-API stets ueber den Fall selbst testen."""
    fall = _registriere_testquelle(
        tmp_path, spec, zeilen, quellspalten=quellspalten)
    return wende_an(spec, fall)


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
        entscheider="fachverantwortliche-rolle")])
    assert validate_spec(spec, QUELLSPALTEN + ["STORNO_KZ"]) == []


@pytest.mark.parametrize(
    ("entscheidung", "entscheider", "meldung"),
    [
        ("", "fachverantwortliche-rolle", "leere Entscheidung"),
        ("   ", "fachverantwortliche-rolle", "leere Entscheidung"),
        ("fachlich entschieden", "", "ohne nichtleeren"),
        ("fachlich entschieden", "   ", "ohne nichtleeren"),
    ],
)
def test_leere_entscheidung_oder_entscheider_blockiert(
        entscheidung, entscheider, meldung):
    spec = _spec(offene_konflikte=[OffenerKonflikt(
        quellspalte="STORNO_KZ",
        frage="Bedeutung fachlich klaeren",
        entscheidung=entscheidung,
        entscheider=entscheider,
    )])

    fehler = validate_spec(spec, QUELLSPALTEN + ["STORNO_KZ"])

    assert any(meldung in eintrag for eintrag in fehler), fehler


@pytest.mark.parametrize("wert", ["z" * 64, "AB" * 32, "0" * 63 + "g"])
def test_ungueltiger_sha256_blockiert(wert):
    fehler = validate_spec(_spec(quelle_sha256=wert), QUELLSPALTEN)

    assert any("quelle_sha256" in eintrag and "SHA-256" in eintrag
               for eintrag in fehler), fehler


@pytest.mark.parametrize(
    ("berechnung", "quellen"),
    [
        ("alter_aus_geburtsdatum_und_beginn", ["GEBDAT"]),
        ("alter_aus_geburtsdatum_und_beginn", ["GEBDAT", "BEGINN", "n"]),
        ("jahre_aus_datumsdifferenz", ["BEGINN"]),
        ("jahre_aus_datumsdifferenz", ["BEGINN", "GEBDAT", "n"]),
        ("datum_nach_iso", []),
        ("datum_nach_iso", ["BEGINN", "GEBDAT"]),
        ("zahl", []),
        ("zahl", ["ERLSUMME", "n"]),
        ("ganzzahl", []),
        ("ganzzahl", ["n", "t"]),
    ],
)
def test_berechnungen_verlangen_ihre_exakte_aritaet(berechnung, quellen):
    spec = _spec(felder=[FeldMapping(
        ziel="entry_age",
        typ="berechnung",
        quellen=quellen,
        berechnung=berechnung,
        begruendung="adversarial falsche Operandenanzahl",
    )])

    fehler = validate_spec(spec, QUELLSPALTEN)

    assert any(berechnung in eintrag and "braucht genau" in eintrag
               for eintrag in fehler), fehler


@pytest.mark.parametrize("quellen", [[], ["BEGINN", "GEBDAT"]])
def test_monate_letzter_jahrestag_verlangt_genau_eine_quellspalte(quellen):
    spec = _spec(felder=[FeldMapping(
        ziel="monate_ta", typ="berechnung", quellen=quellen,
        berechnung="monate_letzter_jahrestag_vor_stichtag",
        parameter={"stichtag": "2026-01-01"},
        begruendung="adversarial falsche Operandenanzahl",
    )])

    fehler = validate_spec(spec, QUELLSPALTEN)

    assert any("monate_letzter_jahrestag_vor_stichtag" in f
               and "braucht genau" in f for f in fehler), fehler


def test_monate_letzter_jahrestag_ohne_parameter_blockiert():
    spec = _spec(felder=[FeldMapping(
        ziel="monate_ta", typ="berechnung", quellen=["BEGINN"],
        berechnung="monate_letzter_jahrestag_vor_stichtag",
        begruendung="Verankerungszeitpunkt t_a",
    )])

    fehler = validate_spec(spec, QUELLSPALTEN)

    assert any("braucht den Parameter 'stichtag'" in f for f in fehler), fehler


def test_monate_letzter_jahrestag_mit_unlesbarem_datum_blockiert():
    spec = _spec(felder=[FeldMapping(
        ziel="monate_ta", typ="berechnung", quellen=["BEGINN"],
        berechnung="monate_letzter_jahrestag_vor_stichtag",
        parameter={"stichtag": "31. Dezember 2025"},
        begruendung="Verankerungszeitpunkt t_a",
    )])

    fehler = validate_spec(spec, QUELLSPALTEN)

    assert any("kein bekanntes Datumsformat" in f for f in fehler), fehler


def test_monate_letzter_jahrestag_rundet_auf_volle_vertragsjahre_ab():
    """Unabhaengige Kontrolle: roh ueber die Monatskonvention der
    Controlling-Suite (``gates.migrationssuite_lauf._monate``) rechnen und
    von Hand auf das letzte volle Vertragsjahr abrunden — die Katalog-
    funktion muss auf denselben Wert kommen. Quellsysteme wie Baldrians
    fuehren das Deckungskapital nur am Vertragsjahrestag (Mitteilung 143
    Abschnitt 6) und interpolieren nicht; der Stichtag der Lieferung
    selbst ist meist KEIN Jahrestag."""
    from rechner_pipeline.gates.migrationssuite_lauf import _monate as kontrolle

    monate_ta = BERECHNUNGEN["monate_letzter_jahrestag_vor_stichtag"]
    faelle = [
        ("01.06.2015", "01.01.2026"),   # Stichtag zwischen zwei Jahrestagen
        ("15.03.2020", "01.03.2026"),   # Stichtag-Tag < Beginn-Tag
        ("01.01.2020", "01.01.2020"),   # Beginn == Stichtag: 0 Monate
        ("01.06.2015", "01.06.2025"),   # Stichtag IST der Jahrestag
    ]
    for beginn, stichtag in faelle:
        zeile = {"BEGINN": beginn}
        roh = kontrolle(_parse_datum(beginn), _parse_datum(stichtag))
        erwartet = (roh // 12) * 12
        assert monate_ta(zeile, ["BEGINN"], {"stichtag": stichtag}) == erwartet
        assert erwartet % 12 == 0


def test_monate_letzter_jahrestag_vor_beginn_ist_unplausibel():
    monate_ta = BERECHNUNGEN["monate_letzter_jahrestag_vor_stichtag"]
    with pytest.raises(ValueError, match="< 0"):
        monate_ta(
            {"BEGINN": "01.06.2027"}, ["BEGINN"], {"stichtag": "01.01.2026"})


def test_monate_ta_und_dk_ta_werden_end_zu_end_transformiert(tmp_path):
    """Die Verankerungsattribute laufen als optionale Zielfelder durch die
    volle Anwendung — belegt am Fall, nicht nur an der Katalogfunktion.
    BEGINN 01.06.2015, Stichtag 01.01.2026: letzter Jahrestag davor ist
    01.06.2025, also 120 Monate (10 volle Vertragsjahre), nicht die rohen
    127 Monate bis zum Stichtag."""
    spec = _spec(felder=list(_spec().felder) + [
        FeldMapping(ziel="monate_ta", typ="berechnung", quellen=["BEGINN"],
                    berechnung="monate_letzter_jahrestag_vor_stichtag",
                    parameter={"stichtag": "01.01.2026"},
                    begruendung="letzter exakter Rechenpunkt der Quelle "
                                "(Mitteilung 143 Abschnitt 6: DECKKAP nur "
                                "am Vertragsjahrestag, keine Interpolation)"),
        FeldMapping(ziel="dk_ta", typ="berechnung", quellen=["DECKKAP"],
                    berechnung="zahl",
                    begruendung="dort gelieferter Deckungskapitalwert"),
    ])
    zeile = dict(ZEILE, DECKKAP="21068.41")
    ziel, befunde = _wende_testquelle(
        tmp_path, spec, [zeile], quellspalten=QUELLSPALTEN + ["DECKKAP"])

    assert befunde == []
    assert ziel[0]["monate_ta"] == 120
    assert ziel[0]["dk_ta"] == pytest.approx(21068.41)


def test_jede_katalogberechnung_hat_einen_aritaetsvertrag():
    from rechner_pipeline.ontologie.transformation import (
        BERECHNUNGEN,
        BERECHNUNGS_ARITAETEN,
    )

    assert set(BERECHNUNGEN) == set(BERECHNUNGS_ARITAETEN)


def test_unbekanntes_zielfeld_ist_ak1_grenze():
    spec = _spec()
    felder = [f.model_dump() for f in spec.felder]
    felder.append(FeldMapping(
        ziel="provisionssatz", typ="direkt", quellen=["TARIF"],
        begruendung="?").model_dump())
    fehler = validate_spec(
        TransformationsSpec(**{**spec.model_dump(), "felder": felder}),
        QUELLSPALTEN)
    assert any("provisionssatz" in f and "A-K1" in f for f in fehler)


def test_anwendung_ist_deterministisch_und_vollstaendig(tmp_path):
    spec = _spec()
    fall = _registriere_testquelle(tmp_path, spec, [ZEILE])
    ziel, befunde = wende_an(spec, fall)
    assert befunde == []
    [v] = ziel
    assert v["entry_age"] == 39                # 1976 -> 2015, Juni
    assert v["duration"] == 20 and v["premium_duration"] == 15
    assert v["sum_insured"] == 87000.0
    assert v["zahlweise"] == 12
    assert v["status"] == "Nichtraucher" and v["tarifart"] == "Kollektiv"
    assert v["beginn"] == "2015-06-01"
    assert v["sex"] == "F"                     # Quelle "W" -> Kern-Contract
    # Determinismus:
    assert wende_an(spec, fall) == (ziel, [])


def test_unbekannter_kodierungswert_verwirft_die_zeile_laut(tmp_path):
    kaputt = dict(ZEILE, RK="X")
    ziel, befunde = _wende_testquelle(tmp_path, _spec(), [ZEILE, kaputt])
    assert len(ziel) == 1                      # halbe Vertraege gibt es nicht
    assert any("'X'" in b and "Kodierung" in b for b in befunde)


def test_wende_an_blockiert_eine_nicht_validierte_spec(tmp_path):
    spec = _spec(felder=[f for f in _spec().felder if f.ziel != "sum_insured"])

    with pytest.raises(ValueError, match="sum_insured.*nicht gedeckt"):
        _wende_testquelle(tmp_path, spec, [ZEILE])


def test_wende_an_blockiert_nachtraeglich_veraenderte_quellbytes(tmp_path):
    spec = _spec()
    fall = _registriere_testquelle(tmp_path, spec, [ZEILE])
    quelle = fall / "eingang" / spec.quelle_datei
    quelle.chmod(0o600)
    quelle.write_text(
        quelle.read_text(encoding="utf-8").replace("87000", "99999"),
        encoding="utf-8",
    )

    with pytest.raises(ValueError, match="Inhalt weicht vom Register ab"):
        wende_an(spec, fall)


def test_wende_an_bindet_die_spec_an_die_tatsaechlich_gelesenen_bytes(
        tmp_path):
    """Die Spec muss zu DEN Bytes passen, die transformiert werden.

    Die Registerpruefung in ``fall.eingang_datei`` faengt nur den Fall,
    dass die registrierte Datei nachtraeglich veraendert wurde. Zeigt
    eine Spec dagegen auf eine unversehrt registrierte Datei, aber mit
    fremdem ``quelle_sha256``, ist dieser Abgleich im Anwendungspfad die
    einzige Instanz — und er war ungetestet: Entfernt man ihn, bleibt
    die Suite gruen.
    """
    echte_spec = _spec()
    fall = _registriere_testquelle(tmp_path, echte_spec, [ZEILE])
    fremde_spec = _spec(quelle_sha256="b" * 64)

    with pytest.raises(ValueError) as exc_info:
        wende_an(fremde_spec, fall)

    meldung = str(exc_info.value)
    assert "quelle_sha256 der Spec passt nicht" in meldung
    # Die Meldung nennt den tatsaechlichen Hash, damit der Mensch die
    # Verwechslung aufloesen kann.
    assert echte_spec.quelle_sha256 in meldung


def test_berichtsweg_prueft_quellenbindung_gegen_die_registrierte_datei(
        tmp_path):
    """Auch der schmale Berichtsweg muss physisch neu lesen.

    Der Abnahmebericht prueft die Quellenbindung auf JEDEM Weg, nicht nur
    im Bestands-Scope. Verglichen ein Umbau nur noch Spec- und
    Ergebnis-Hash miteinander, blieben beide in sich stimmig und die
    Suite gruen — obwohl keiner von beiden zur registrierten Datei
    passt. Genau diese in sich stimmige Faelschung stellt der Test her.
    """
    from rechner_pipeline.gates.abnahmebericht import (
        _registrierte_quellenbindung_fehler,
    )

    echte_spec = _spec()
    fall = _registriere_testquelle(tmp_path, echte_spec, [ZEILE])
    echtes_ergebnis = {
        "quelle_sha256": echte_spec.quelle_sha256,
        "quellspalten": list(QUELLSPALTEN),
        "zeilen_quelle": 1,
        "zeilen_ziel": 1,
        "befunde": [],
    }
    assert _registrierte_quellenbindung_fehler(
        fall=fall, spec=echte_spec, ergebnis=echtes_ergebnis
    ) == []

    fremder_hash = "c" * 64
    fremde_spec = _spec(quelle_sha256=fremder_hash)
    stimmiges_falsches_ergebnis = {**echtes_ergebnis, "quelle_sha256": fremder_hash}

    fehler = _registrierte_quellenbindung_fehler(
        fall=fall, spec=fremde_spec, ergebnis=stimmiges_falsches_ergebnis
    )

    assert any("TransformationsSpec.quelle_sha256 weicht" in m for m in fehler)
    assert any(
        "Transformationsergebnis.quelle_sha256 weicht" in m for m in fehler
    )


def test_wende_an_prueft_die_physischen_quellspalten(tmp_path):
    spec = _spec()
    fehlende_summe = [spalte for spalte in QUELLSPALTEN if spalte != "ERLSUMME"]
    with pytest.raises(ValueError, match="ERLSUMME.*existiert nicht"):
        _wende_testquelle(
            tmp_path, spec, [ZEILE], quellspalten=fehlende_summe)


def test_wende_an_weist_eine_unregistrierte_datei_zurueck(tmp_path):
    from rechner_pipeline.fall import anlegen

    spec = _spec()
    fall = tmp_path / "fall"
    anlegen(fall)
    unregistriert = fall / "eingang" / spec.quelle_datei
    unregistriert.write_text("POLNR\n7000001\n", encoding="utf-8")

    with pytest.raises(ValueError, match="nicht registriert"):
        wende_an(spec, fall)


def test_wende_an_transformiert_den_vom_fall_geprueften_eingang(tmp_path):
    spec = _spec()
    fall = _registriere_testquelle(tmp_path, spec, [ZEILE])

    ziel, befunde = wende_an(spec, fall)

    assert befunde == []
    assert [zeile["police_id"] for zeile in ziel] == ["7000001"]


# --------------------------------------------------------------------------- #
# Die Klammer Transformation -> Kern: das Geschlecht (Systempruefung 19.08.)
# --------------------------------------------------------------------------- #


def test_ziel_ontologie_deckt_den_kern_contract_vollstaendig():
    """Jedes Vertragsfeld des Kern-Contracts hat ein Zielfeld.

    ``models/bestand.CONTRACT_FIELDS`` fuehrt die Kern-Namen (x, sex, n,
    t, sum_insured, zw), die Transformation die Portfolio-Namen — die
    Uebersetzung steht in ``model_point_kwargs``. Fehlt hier eines, ist
    ein transformierter Vertrag nicht rechenbar, ohne dass die
    Spec-Pruefung es merkt (so gefunden fuer ``sex``).
    """
    from rechner_pipeline.models.bestand import CONTRACT_FIELDS
    from rechner_pipeline.ontologie.transformation import ZIEL_PFLICHT

    kern_zu_ziel = {"x": "entry_age", "sex": "sex", "n": "duration",
                    "t": "premium_duration", "sum_insured": "sum_insured",
                    "zw": "zahlweise"}
    assert set(kern_zu_ziel) == set(CONTRACT_FIELDS)     # Uebersetzung aktuell
    fehlend = [k for k, z in kern_zu_ziel.items() if z not in ZIEL_PFLICHT]
    assert fehlend == [], f"Kern-Contract-Felder ohne Zielfeld: {fehlend}"


def test_sex_zielwerte_sind_die_des_bestandskontrakts():
    """Die Konstanten-Dopplung (Schichtenkarte) ist hier test-gebunden."""
    from rechner_pipeline.models.bestand import SEX_VALUES
    from rechner_pipeline.ontologie.transformation import SEX_ZIELWERTE

    assert SEX_ZIELWERTE == SEX_VALUES


def test_ungemapptes_geschlecht_faellt_als_pflichtfeld():
    spec = _spec()
    spec = TransformationsSpec(**{
        **spec.model_dump(),
        "felder": [f.model_dump() for f in spec.felder if f.ziel != "sex"],
    })
    fehler = validate_spec(spec, QUELLSPALTEN)
    assert any("'sex' ist nicht gedeckt" in f for f in fehler), fehler


def test_geschlechts_kodierung_auf_quellcodes_faellt():
    """"W" durchreichen ist kein Fehler im Kern — sondern ein stiller.

    ``kern/tafeln._tafel_key`` loest jedes Nicht-"M" zur Frauentafel auf.
    Ein Mapping ``{"M": "M", "W": "W"}`` waere damit fuer Maenner falsch,
    ohne je aufzufallen; die Spec-Pruefung muss es abfangen.
    """
    spec = _spec(felder=[
        f if f.ziel != "sex" else FeldMapping(
            ziel="sex", typ="kodierung", quellen=["GESCHL"],
            kodierung={"M": "M", "W": "W"},
            begruendung="Quellcodes durchgereicht")
        for f in _spec().felder
    ])
    fehler = validate_spec(spec, QUELLSPALTEN)
    assert any(f.startswith("sex: Kodierung") and "'W'" in f
               for f in fehler), fehler


def test_direkt_durchgereichtes_geschlecht_ausserhalb_m_f_ist_ein_befund(
        tmp_path):
    """Auch ohne Kodierung endet ein Fremdwert nicht im Kern."""
    spec = _spec(felder=[
        f if f.ziel != "sex" else FeldMapping(
            ziel="sex", typ="direkt", quellen=["GESCHL"],
            begruendung="Quelle fuehrt bereits M/F")
        for f in _spec().felder
    ])
    assert validate_spec(spec, QUELLSPALTEN) == []      # Spec ist zulaessig
    ziel, befunde = _wende_testquelle(
        tmp_path,
        spec,
        [dict(ZEILE, GESCHL="F"), dict(ZEILE, GESCHL="W")],
    )
    assert len(ziel) == 1 and ziel[0]["sex"] == "F"
    assert len(befunde) == 1 and "Geschlecht 'W'" in befunde[0]


def test_transformierte_zeile_baut_einen_kern_modelpoint(tmp_path):
    """Die heute fehlende Klammer: Ausgabe -> ModelPoint -> Rechnung.

    Kontrollrechnung gegen einen unabhaengigen Pfad: derselbe Vertrag
    wird einmal ueber die Transformation und einmal direkt als
    ModelPoint gebaut — beide muessen denselben Bruttojahresbeitrag
    ergeben. Damit haengt die Transformation nachweisbar am Kern und
    nicht nur an ihrem eigenen Feldnamen-Vokabular.
    """
    from rechner_pipeline.kern.model_point import ModelPoint
    from rechner_pipeline.models.bestand import (
        GENERATION_FIELDS, model_point_kwargs,
    )

    generation = {name: getattr(KLV_DEFAULT, name) for name in GENERATION_FIELDS}
    ziel, befunde = _wende_testquelle(tmp_path, _spec(), [ZEILE])
    assert befunde == []
    mp = ModelPoint(**model_point_kwargs(ziel[0], generation))
    assert (mp.x, mp.sex, mp.n, mp.t, mp.zw) == (39, "F", 20, 15, 12)
    assert mp.sum_insured == 87000.0
    erwartet = dataclasses.replace(
        KLV_DEFAULT, x=39, sex="F", n=20, t=15, sum_insured=87000.0, zw=12)
    assert berechne(mp)["scalars"]["Kalkulation"]["BJB"] == \
        berechne(erwartet)["scalars"]["Kalkulation"]["BJB"]
    # Das Geschlecht ist keine Kosmetik: dieselbe Police als "M" gerechnet
    # ergibt einen anderen Beitrag (Tafel-Suffix _M/_F). Ein falsch
    # gemapptes oder fehlendes Geschlecht verschiebt also Werte.
    assert berechne(dataclasses.replace(erwartet, sex="M"))["scalars"][
        "Kalkulation"]["BJB"] != berechne(mp)["scalars"]["Kalkulation"]["BJB"]


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


def test_beleglage_steht_in_jedem_urteil():
    """Anteil stuetzender Belege je Lesart — Grundlage jeder Begruendung."""
    belege = _belege("zins", 0.0125)
    urteil = gleiche_ab("zins", [
        Lesart(0.0125, "tarifmeldung"), Lesart(0.0175, "tarifrechner"),
    ], belege)
    gewinner = next(u for u in urteil["urteile"] if u["passt"])
    verlierer = next(u for u in urteil["urteile"] if not u["passt"])
    assert gewinner["geprueft"] == 6          # 3 Vertraege x 2 Werte
    assert gewinner["quote_stuetzend"] == 1.0
    assert verlierer["quote_verletzt"] == 1.0
    assert verlierer["verletzende_belege"][0].startswith("700000")
    assert "100.0%" in urteil["begruendung"]


def test_ein_ausreisser_kippt_das_urteil_nicht_stillschweigend():
    """Ein einzelner abweichender Beleg -> Mensch MIT Beleglage.

    Die wahre Lesart wird durch 5 von 6 Werten getragen; ein Wert ist
    verfaelscht. Das Urteil bleibt beim Menschen (keine Lesart passt
    lueckenlos) — aber die Begruendung muss sagen, dass es an EINEM
    Beleg liegt, sonst ist sie fuer eine Entscheidung wertlos.
    """
    belege = _belege("zins", 0.0125)
    verfaelscht = dataclasses.replace(
        belege[0],
        erwartet={**belege[0].erwartet,
                  "kVx_MRV": belege[0].erwartet["kVx_MRV"] * 1.05})
    urteil = gleiche_ab("zins", [
        Lesart(0.0125, "tarifmeldung"), Lesart(0.0175, "tarifrechner"),
    ], [verfaelscht] + belege[1:])
    assert urteil["automatisch_aufloesbar"] is False
    assert urteil["menschlich_erforderlich"] is True
    wahre = next(u for u in urteil["urteile"] if u["wert"] == 0.0125)
    assert (wahre["verletzt"], wahre["geprueft"]) == (1, 6)
    assert wahre["quote_stuetzend"] == pytest.approx(5 / 6)
    assert wahre["verletzende_belege"] == ["7000000/kVx_MRV"]
    assert "83.3%" in urteil["begruendung"]
    assert "7000000/kVx_MRV" in urteil["begruendung"]


def test_duenne_beleglage_loest_nicht_automatisch_auf():
    """Ein einziger Belegwert ist kein Bestandsbeweis."""
    beleg = _belege("zins", 0.0125, anzahl=1)[0]
    einzeln = dataclasses.replace(
        beleg, erwartet={"BJB": beleg.erwartet["BJB"]})
    urteil = gleiche_ab("zins", [
        Lesart(0.0125, "tarifmeldung"), Lesart(0.0175, "tarifrechner"),
    ], [einzeln])
    assert urteil["urteile"][0]["geprueft"] == 1 < MIND_BELEGE
    assert urteil["urteile"][0]["passt"] is True     # genau eine Lesart passt
    assert urteil["automatisch_aufloesbar"] is False
    assert urteil["menschlich_erforderlich"] is True
    assert "zu duenn" in urteil["begruendung"]


def test_vereinzelt_verletzte_gegenlesart_ist_keine_verwerfung():
    """Die Gegenlesart muss BREIT verworfen sein, nicht punktuell.

    ``policy_fee`` wirkt nur auf den Zahlbeitrag BZB — von drei
    Belegwerten je Vertrag verletzt die falsche Lesart also genau
    einen. Ein Drittel der Belege ist keine Verwerfung: ohne die
    Schranke wuerde hier automatisch entschieden, obwohl zwei Drittel
    der Lieferung zwischen den Lesarten gar nicht unterscheiden.
    """
    belege = []
    for i, (x, n, t) in enumerate([(35, 20, 15), (45, 25, 20), (30, 30, 30)]):
        params = dataclasses.asdict(
            dataclasses.replace(KLV_DEFAULT, x=x, n=n, t=t, policy_fee=24.0))
        ergebnis = berechne(type(KLV_DEFAULT)(**params))
        belege.append(VertragsBeleg(
            police_id=f"700000{i}", model_point=params, vertragsjahr=5,
            erwartet={
                "BJB": ergebnis["scalars"]["Kalkulation"]["BJB"],
                "BZB": ergebnis["scalars"]["Kalkulation"]["BZB"],
                "kVx_MRV": ergebnis["tables"]["Kalkulation"][5]["kVx_MRV"],
            }))
    urteil = gleiche_ab("policy_fee", [
        Lesart(24.0, "tarifmeldung"), Lesart(0.0, "tarifrechner"),
    ], belege)
    gewinner = next(u for u in urteil["urteile"] if u["wert"] == 24.0)
    verlierer = next(u for u in urteil["urteile"] if u["wert"] == 0.0)
    assert gewinner["passt"] and gewinner["geprueft"] == 9
    assert verlierer["verletzt"] == 3                 # nur die BZB-Werte
    assert verlierer["quote_verletzt"] == pytest.approx(1 / 3)
    assert verlierer["quote_verletzt"] < VERWERFUNGS_QUOTE
    assert urteil["automatisch_aufloesbar"] is False
    assert urteil["menschlich_erforderlich"] is True
    assert "Ausreisser" in urteil["begruendung"]


def test_schlechtester_beleg_ist_der_schlimmste_VERLETZENDE():
    """Ein nicht verletzender Vergleich darf den Ausreisser nicht decken.

    Die relative Abweichung wird gegen ``max(|soll|, 1.0)`` gemessen.
    Bei einer Groesse unter 1 (Beitragsrate ``Bxt``) faellt sie dadurch
    gross aus, ohne je die Toleranz zu verletzen — waehrend der
    tatsaechlich verletzende Betragswert eine viel kleinere relative
    Abweichung hat. Der benannte Beleg muss der verletzende sein.
    """
    beleg = _belege("zins", 0.0125, anzahl=1)[0]
    params = dict(beleg.model_point)
    ergebnis = berechne(type(KLV_DEFAULT)(**params))
    bxt = ergebnis["scalars"]["Kalkulation"]["Bxt"]
    bjb = ergebnis["scalars"]["Kalkulation"]["BJB"]
    gemischt = dataclasses.replace(beleg, erwartet={
        "Bxt": bxt + 1e-3,      # grosse rel. Abweichung, aber innerhalb ABS_TOL
        "BJB": bjb + 0.05,      # kleine rel. Abweichung, aber verletzend
    })
    urteil = pruefe_lesart("zins", Lesart(0.0125, "tarifmeldung"), [gemischt])
    assert urteil["verletzt"] == 1
    assert urteil["schlechtester_beleg"] == f"{beleg.police_id}/BJB"
    assert urteil["max_relative_abweichung"] > \
        urteil["max_relative_abweichung_verletzt"]


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
# P5: Vorverdichter (Spaltenprofil) und Skill-Absicherung
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


@pytest.mark.parametrize(
    ("daten", "zeilennummer", "gefunden"),
    [
        ("1\n", 2, 1),
        ("1;2;3\n", 2, 3),
        ("1;2\n3\n", 3, 1),
    ],
)
def test_bestand_profil_faellt_bei_falscher_zeilenbreite(
        tmp_path, daten, zeilennummer, gefunden):
    from rechner_pipeline.quellen.bestand_profil import baue_profil

    csv_datei = tmp_path / "abzug.csv"
    csv_datei.write_text(f"A;B\n{daten}", encoding="utf-8")

    with pytest.raises(ValueError) as exc_info:
        baue_profil(csv_datei)

    meldung = str(exc_info.value)
    assert f"CSV-Zeile {zeilennummer}" in meldung
    assert "erwartete Feldzahl 2" in meldung
    assert f"gefundene Feldzahl {gefunden}" in meldung


@pytest.mark.parametrize(
    ("daten", "zeilennummer", "gefunden"),
    [
        ("1;2\n", 2, 2),
        ("1;2;3;4\n", 2, 4),
        ("1;2;3\n4;5\n", 3, 2),
    ],
)
def test_transformationsquelle_faellt_bei_falscher_zeilenbreite(
        tmp_path, daten, zeilennummer, gefunden):
    """Zerfranste Zeilen sind ein Befund, kein stiller Default (P2).

    Zu kurze Zeilen wurden frueher mit None aufgefuellt und landeten als
    leerer Zielwert im Ergebnis; ueberzaehlige Felder verschwanden
    spurlos. Dieselbe Fehlerklasse ist im Bestandsprofil bereits
    geschlossen — hier fehlte sie noch.
    """
    from rechner_pipeline.ontologie.transformation import (
        lese_transformationsquelle,
    )

    csv_datei = tmp_path / "quelle.csv"
    csv_datei.write_text(f"A;B;C\n{daten}", encoding="utf-8")

    with pytest.raises(ValueError) as exc_info:
        lese_transformationsquelle(csv_datei)

    meldung = str(exc_info.value)
    assert f"Zeile {zeilennummer}" in meldung
    assert f"{gefunden} Felder" in meldung
    assert "erwartet 3" in meldung


def test_transformationsquelle_laesst_leerfeld_und_gequoteten_trenner_zu(
        tmp_path):
    """Die Breitenpruefung darf legitime Zeilen nicht mitreissen."""
    from rechner_pipeline.ontologie.transformation import (
        lese_transformationsquelle,
    )

    csv_datei = tmp_path / "quelle.csv"
    csv_datei.write_text('A;B;C\n1;;3\n4;"x;y";6\n', encoding="utf-8")

    _, spalten, zeilen = lese_transformationsquelle(csv_datei)

    assert spalten == ["A", "B", "C"]
    assert zeilen == [
        {"A": "1", "B": "", "C": "3"},
        {"A": "4", "B": "x;y", "C": "6"},
    ]


def test_bestand_profil_zaehlt_gequoteten_trenner_als_ein_feld(tmp_path):
    from rechner_pipeline.quellen.bestand_profil import baue_profil

    csv_datei = tmp_path / "abzug.csv"
    csv_datei.write_text(
        'POLNR;HINWEIS\n7000001;"regulaer; gequotet"\n',
        encoding="utf-8",
    )

    profil = baue_profil(csv_datei)

    spalten = {spalte["name"]: spalte for spalte in profil["spalten"]}
    assert profil["zeilen"] == 1
    assert spalten["HINWEIS"]["beispiele"] == ["regulaer; gequotet"]


def test_bestand_profil_cli_meldet_falsche_zeilenbreite(
        tmp_path, capsys):
    from rechner_pipeline.quellen.bestand_profil import main

    csv_datei = tmp_path / "abzug.csv"
    profil_datei = tmp_path / "profil.json"
    csv_datei.write_text("A;B\n1;2;3\n", encoding="utf-8")

    exit_code = main([
        "--input", str(csv_datei),
        "--out", str(profil_datei),
    ])

    ausgabe = capsys.readouterr()
    assert exit_code == 20
    assert ausgabe.out == ""
    assert "CSV-Zeile 2" in ausgabe.err
    assert "erwartete Feldzahl 2, gefundene Feldzahl 3" in ausgabe.err
    assert not profil_datei.exists()


def test_transformations_skill_ist_abgesichert():
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
    assert "A-K1" in claude
    assert "Abbruchkriterien" in claude
    konflikt = (repo / ".claude/skills/bereite-fachkonflikt-auf/SKILL.md"
                ).read_text(encoding="utf-8")
    assert "Bestandsabzug-Abgleich" in konflikt
    assert "NIEMALS automatisch" in konflikt
    assert konflikt == (repo / ".agents/skills/bereite-fachkonflikt-auf/"
                        "SKILL.md").read_text(encoding="utf-8")


def test_runbook_fuehrt_die_bestands_haelfte_der_pipeline():
    """Das Orchestrierungs-Runbook kennt beide Haelften der Lieferung.

    Die Bestandsmaschinerie (Spaltenprofil, Transformation, Abgleich,
    Zwei-Stichtags-Abnahme, Abnahmebericht) existiert als Code und als
    eigene Skills; ohne Einstieg im Runbook wird sie in einem echten
    Fall schlicht nicht ausgefuehrt (Systempruefung 19.08.). Sichert
    sind die Uebergaben, nicht die Formulierung.
    """
    from pathlib import Path

    repo = Path(__file__).resolve().parents[1]
    runbook = (repo / ".claude/skills/migrationsfall-durchfuehren/SKILL.md"
               ).read_text(encoding="utf-8")
    assert runbook == (repo / ".agents/skills/migrationsfall-durchfuehren/"
                       "SKILL.md").read_text(encoding="utf-8")      # Paritaet
    for marke in ("Stufe 1b", "Stufe 3b",
                  "rechner_pipeline.quellen.bestand_profil",
                  "transformiere-quellbestand", "validate_spec", "wende_an",
                  "qa.abzugsabgleich", "pruefe-migrationscontrolling",
                  "aktuartest-durchfuehren",
                  "rechner_pipeline.gates.bestand_validate",
                  "qa.migrationssuite", "rechner_pipeline.gates.abnahmebericht",
                  "rechner_pipeline.bestand.cli_report"):
        assert marke in runbook, marke


def test_runbook_und_architektur_nennen_die_formel_grenze():
    """Die bewusste v0.1-Grenze steht dort, wo sie jemand liest.

    Das QuellFragment traegt keine Formeln — ein Formelwiderspruch
    zwischen Meldung und Rechner wird nie eine Diskrepanz. Diese Grenze
    muss als ENTSCHEIDUNG lesbar sein (Architektur-Dokument) und im
    Ablauf stehen (Runbook), sonst wird sie fuer ein Versehen gehalten.
    """
    from pathlib import Path

    repo = Path(__file__).resolve().parents[1]
    runbook = (repo / ".claude/skills/migrationsfall-durchfuehren/SKILL.md"
               ).read_text(encoding="utf-8")
    architektur = (repo / "docs/architektur/migrations-pipeline-v01.md"
                   ).read_text(encoding="utf-8")
    assert "GRENZE DIESER STUFE" in runbook
    assert "keine FORMELN" in runbook
    assert "8.1" in runbook                       # Verweis auf die Begruendung
    assert "### 8.1" in architektur
    assert "Formelidentitaet" in architektur


# --------------------------------------------------------------------------- #
# Berechnungs-Katalog: die Stellen, an denen ein Mapping still falsch
# werden kann. Der Katalog ist die einzige Rechenstelle der
# Transformation — ohne diese Tests bleibt die Suite genau dort gruen,
# wo eine Migration die Semantik der Quelle trifft (Systempruefung
# 19.08.: Alterskorrektur, Dauerberechnung und Katalogtreue liessen sich
# entfernen, ohne einen Test rot zu faerben).
# --------------------------------------------------------------------------- #


def _entry_age(tmp_path, gebdat: str, beginn: str) -> int:
    """entry_age ueber den Katalog, nicht ueber eine Testrechnung."""
    zeile = dict(ZEILE, GEBDAT=gebdat, BEGINN=beginn)
    ziel, befunde = _wende_testquelle(tmp_path, _spec(), [zeile])
    assert befunde == [], befunde
    return ziel[0]["entry_age"]


def test_entry_age_ist_das_vollendete_alter_nicht_die_jahresdifferenz(
        tmp_path):
    """Geburtstag NACH dem Beginn im Jahr: ein Jahr weniger.

    Die Jahresdifferenz allein waere 37 — der Katalog rechnet das
    VOLLENDETE Alter (36). Genau diese Korrektur ist der Unterschied
    zwischen Zielsystem-Konvention und der Kalenderjahresmethode, die
    Quellsysteme fuehren koennen.
    """
    assert _entry_age(tmp_path, "08.12.1979", "01.02.2016") == 36
    assert _entry_age(tmp_path, "08.01.1979", "01.02.2016") == 37
    assert _entry_age(tmp_path, "01.02.1979", "01.02.2016") == 37


def test_jahre_aus_datumsdifferenz_rechnet_und_faellt_hart_aus(tmp_path):
    """Die Dauerberechnung des Katalogs — inklusive ihrer Fehlergrenze."""
    zeile = dict(ZEILE)
    spec = _spec(felder=[
        (
            FeldMapping(
                ziel="duration",
                typ="berechnung",
                quellen=["BEGINN", "ABLAUF"],
                berechnung="jahre_aus_datumsdifferenz",
                begruendung="Laufzeit aus Beginn und Ablauf",
            )
            if feld.ziel == "duration" else feld
        )
        for feld in _spec().felder
    ] + [FeldMapping(
        typ="nicht_uebernommen",
        quellen=["n"],
        begruendung="Dauer wird stattdessen aus Beginn und Ablauf berechnet",
    )])
    ziel, befunde = _wende_testquelle(
        tmp_path,
        spec,
        [dict(zeile, ABLAUF="01.06.2035")],
        quellspalten=QUELLSPALTEN + ["ABLAUF"],
    )
    assert befunde == [] and ziel[0]["duration"] == 20
    # Nicht-positive Dauer ist ein Befund je Zeile, kein stiller Wert:
    ziel, befunde = _wende_testquelle(
        tmp_path,
        spec,
        [dict(zeile, ABLAUF="01.06.2015")],
        quellspalten=QUELLSPALTEN + ["ABLAUF"],
    )
    assert ziel == [] and len(befunde) == 1
    assert "duration" in befunde[0]


def test_validate_spec_weist_unbekannte_berechnung_zurueck():
    """Katalogtreue: der Agent WAEHLT, er erfindet keine Rechenregel.

    Eine Quellkonvention, die der Katalog nicht kennt (z. B. eine
    Halbjahres-Altersregel), muss als Befund auffallen — sonst
    entstuende sie stillschweigend als nicht implementierte Absicht.
    (Die Kalenderjahresmethode war das urspruengliche Beispiel dieses
    Tests; sie ist seit dem Baldrian-Abzugsabgleich BELEGTE
    Katalogfunktion — das unbekannte Beispiel ist nachgerueckt.)
    """
    spec = _spec(felder=[
        FeldMapping(ziel="entry_age", typ="berechnung",
                    quellen=["GEBDAT", "BEGINN"],
                    berechnung="alter_zum_naechsten_geburtstag",
                    begruendung="Quellkonvention des abgebenden Systems"),
    ])
    fehler = validate_spec(spec, QUELLSPALTEN)
    assert any("alter_zum_naechsten_geburtstag" in f and "Berechnung" in f
               for f in fehler), fehler


def test_kalenderjahresmethode_zaehlt_die_jahresdifferenz():
    """Die Quellkonvention 'Beginnjahr minus Geburtsjahr' — unabhaengig
    davon, ob der Geburtstag im Beginnjahr schon erreicht war. Der
    Unterschied zum vollendeten Alter ist genau der Fall 'Geburtstag
    nach Beginn'."""
    from rechner_pipeline.ontologie.transformation import BERECHNUNGEN

    kalender = BERECHNUNGEN["alter_kalenderjahresmethode"]
    vollendet = BERECHNUNGEN["alter_aus_geburtsdatum_und_beginn"]
    zeile = {"GEBDAT": "15.09.1980", "BEGINN": "01.05.2015"}
    assert kalender(zeile, ["GEBDAT", "BEGINN"], {}) == 35
    assert vollendet(zeile, ["GEBDAT", "BEGINN"], {}) == 34
    zeile2 = {"GEBDAT": "15.03.1980", "BEGINN": "01.05.2015"}
    assert kalender(zeile2, ["GEBDAT", "BEGINN"], {}) == 35
    assert vollendet(zeile2, ["GEBDAT", "BEGINN"], {}) == 35
