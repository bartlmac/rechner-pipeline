"""Deterministischer Rueck-Check der IF-Staffeln (P4 auf Formelwerte).

Knoten: klv/tg2012, klv/tg2015
"""

from __future__ import annotations

from pathlib import Path

import pytest

from rechner_pipeline.quellen.formeln import (
    FormelCheckFehler,
    lese_if_staffel,
    pruefe_ratzu_staffeln,
)

def test_if_staffel_parser_liest_prozent_und_default():
    staffel, default = lese_if_staffel(
        "=IF(zw=2,2%,IF(zw=4,3%,IF(zw=12,5%,0)))", "zw")
    assert staffel == {2: 0.02, 4: 0.03, 12: 0.05}
    assert default == 0.0
    staffel, _ = lese_if_staffel(
        "=IF(zw=2,1%,IF(zw=4,1.5%,IF(zw=12,2.5%,0)))", "zw")
    assert staffel == {4: 0.015, 12: 0.025, 2: 0.01}


def test_if_staffel_parser_ist_fail_fast():
    with pytest.raises(FormelCheckFehler, match="erwartet 'zw'"):
        lese_if_staffel("=IF(alter=2,2%,0)", "zw")
    with pytest.raises(FormelCheckFehler, match="IF-Staffel"):
        lese_if_staffel("=A1*P-B1", "zw")
    with pytest.raises(FormelCheckFehler, match="doppelt"):
        lese_if_staffel("=IF(zw=2,2%,IF(zw=2,3%,0))", "zw")
    with pytest.raises(FormelCheckFehler, match="Default"):
        lese_if_staffel("=IF(zw=2,2%,IF(zw=4,3%,abc", "zw")
    # Wrapper-/Praefix-Formeln werden NICHT still als Staffel gelesen:
    with pytest.raises(FormelCheckFehler, match="beginnt nicht mit IF"):
        lese_if_staffel("=2*IF(zw=2,2%,0)", "zw")
    with pytest.raises(FormelCheckFehler, match="nicht vollstaendig"):
        lese_if_staffel("=IF(zw=2,2%,IF(OR(zw=4),3%,0))", "zw")
    with pytest.raises(FormelCheckFehler, match="unparsebarer Zahlwert"):
        lese_if_staffel("=IF(zw=2,2.3.4,0)", "zw")


# --------------------------------------------------------------------------- #
# Regression: der Blattname ist Sache des Quellsystems (Review-Befund P-Q3)
#
# Der Rueck-Check verdrahtete "Kalkulation" hart. Ein Quellsystem, das
# sein Kalkulationsblatt anders nennt (Baldrian: "Tarifrechnung"), lief
# damit still an jeder Pruefung vorbei, waehrend Gate P-Q3 gruen blieb.
# Die Fixture ist bewusst selbst erzeugt und haengt an KEINEM Fall unter
# faelle/ (die Arbeitsbereiche sind gitignored).
# --------------------------------------------------------------------------- #

ZEIT = "2026-08-19T06:00:00+00:00"

#: Vollstaendiger Pflichtumfang, damit Gate P-Q3 an nichts anderem scheitert.
PFLICHT_WERTE = {
    "zins": 0.0175, "tafel": "DAV2008_T", "alpha": 0.025, "beta1": 0.03,
    "gamma1": 0.001, "gamma2": 0.00125, "gamma3": 0.0025,
    "policy_fee": 12.0, "stoab_satz": 0.005, "stoab_min": 50.0,
    "stoab_max": 150.0, "min_alter_flex": 60, "min_rlz_flex": 5,
}

STAFFEL = "=IF(zw=2,2%,IF(zw=4,3%,IF(zw=12,5%,0)))"


def _schreibe_vorverdichtung(fall: Path, blattname: str) -> Path:
    """Minimale, aber contract-treue Vorverdichtung mit frei waehlbarem Blatt.

    Zwei Blaetter (ein formeltragendes plus ein Tafelblatt ohne Formeln),
    damit die Ermittlung wirklich waehlen muss und nicht zufaellig das
    einzige Blatt trifft.

    Die Dateinamen entstehen wie in der echten Extraktion ueber
    ``safe_filename`` — der Blattname des Workbooks steht in der Spalte
    ``Blatt``, der Dateistamm ist nur seine dateisystemsichere Fassung.
    Beides faellt bei Sonderzeichen auseinander, und genau das muss die
    Fixture abbilden koennen.
    """
    import json

    from rechner_pipeline.quellen.extract.excel import safe_filename

    verzeichnis = fall / "abgeleitet" / "vorverdichtung" / "xlsm-TG2012"
    verzeichnis.mkdir(parents=True, exist_ok=True)
    stamm = safe_filename(blattname)
    blatt_csv = verzeichnis / f"{stamm}.csv"
    blatt_csv.write_text(
        "Blatt;Adresse;Formel;Wert\n"
        f"{blattname};$A$1;Tarifrechner;Tarifrechner\n"
        f"{blattname};$G$12;{STAFFEL};0\n",
        encoding="utf-8",
    )
    tafeln_csv = verzeichnis / "Tafeln.csv"
    tafeln_csv.write_text(
        "Blatt;Adresse;Formel;Wert\nTafeln;$A$3;x/y;x/y\n", encoding="utf-8"
    )
    komprimiert = verzeichnis / f"{stamm}_compressed.csv"
    komprimiert.write_text("Adresse;Formel;Wert\n", encoding="utf-8")
    (verzeichnis / "export_manifest.json").write_text(
        json.dumps({
            "out_dir": str(verzeichnis),
            "sheet_csvs": [str(blatt_csv), str(tafeln_csv)],
            "vba_txts": [],
            "names_manager_csv": "",
            "replacements": {str(blatt_csv): str(komprimiert)},
            "llm_inputs": [str(komprimiert)],
            "all_outputs": [str(blatt_csv), str(tafeln_csv), str(komprimiert)],
            "warnings": [],
            "prompt_runs": [],
            "output_hashes": [],
        }, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    return verzeichnis


def _fall_mit_abox(
    tmp_path: Path,
    fundstellen_blatt: str,
    ratzu2=0.02,
    ratzu_quelle: str = "tarifrechner",
    mit_rechner: bool = True,
) -> Path:
    """Fall-Arbeitsbereich mit einer A-Box, deren ratzu-Aussagen auf
    ``<fundstellen_blatt>!$G$12`` zeigen.

    ``ratzu_quelle="tarifmeldung"`` baut denselben Fall fachlich korrekt
    anders: die ratzu-Staffel ist dann NUR aus der Tarifmeldung belegt
    (Fundstelle ist eine Tabellenzelle des Dokuments, kein Blatt-Praefix)
    — der Rechner traegt sie nicht. ``fundstellen_blatt`` ist in diesem
    Fall bedeutungslos.

    ``mit_rechner=False`` laesst den Tarifrechner ganz weg (die
    Generation kennt dann nur die Meldung als Quelle) — der Fall, in dem
    es gar keinen Quellrechner zu verdichten gibt.
    """
    import json as _json

    from rechner_pipeline.fall import anlegen, registrieren
    from rechner_pipeline.ontologie.abox import speichere
    from rechner_pipeline.ontologie.befuellung import (
        FragmentWert, FragmentZelle, QuellFragment, baue_abox,
    )

    fall = tmp_path / "fall"
    anlegen(fall, beschreibung="Fixture Blattname")

    parameter = {
        feld: FragmentWert(wert=wert, fundstelle=f"quelle:{feld}")
        for feld, wert in PFLICHT_WERTE.items()
    }
    ratzu = {
        feld: FragmentWert(wert=wert, fundstelle=f"{fundstellen_blatt}!$G$12")
        for feld, wert in (("ratzu_zw2", ratzu2), ("ratzu_zw4", 0.03),
                           ("ratzu_zw12", 0.05))
    }
    meldungs_ratzu = {
        feld: FragmentWert(
            wert=fw.wert, fundstelle=f"tabellen[0].zeilen[{84 + i}][2]"
        )
        for i, (feld, fw) in enumerate(sorted(ratzu.items()))
    }
    fragmente = []
    akteure = []
    if mit_rechner:
        quelle = tmp_path / "rechner.xlsm"
        quelle.write_bytes(b"rechner-bytes")
        registrieren(fall, quelle)
        rechner_parameter = dict(parameter)
        if ratzu_quelle == "tarifrechner":
            rechner_parameter.update(ratzu)
        fragmente.append(QuellFragment(
            generation="tg2012", quelle_datei="rechner.xlsm",
            quelle_art="tarifrechner",
            zellen=[FragmentZelle(parameter=rechner_parameter)],
        ))
        akteure.append("test/extraktion@abc1234")
    if ratzu_quelle == "tarifmeldung":
        meldung = tmp_path / "meldung.docx"
        meldung.write_bytes(b"meldung-bytes")
        registrieren(fall, meldung)
        meldungs_parameter = dict(meldungs_ratzu)
        if not mit_rechner:
            # Ohne Rechner traegt die Meldung auch den Pflichtumfang,
            # sonst waere die A-Box unvollstaendig (Gate P-Q3).
            meldungs_parameter.update(parameter)
        fragmente.append(QuellFragment(
            generation="tg2012", quelle_datei="meldung.docx",
            quelle_art="tarifmeldung",
            zellen=[FragmentZelle(parameter=meldungs_parameter)],
        ))
        akteure.append("test/meldung@abc1234")
    register = _json.loads((fall / "eingang.json").read_text(encoding="utf-8"))
    abox = baue_abox(str(fall), fragmente, register, akteure, ZEIT)
    speichere(abox, fall)
    return fall


def test_rueckcheck_laeuft_bei_fremdem_blattnamen(tmp_path: Path):
    """Kernregression: das Blatt heisst NICHT "Kalkulation" — der
    Rueck-Check laeuft trotzdem und rechnet die Staffel nach."""
    fall = _fall_mit_abox(tmp_path, "Tarifrechnung")
    _schreibe_vorverdichtung(fall, "Tarifrechnung")

    pruefung = pruefe_ratzu_staffeln(fall, "klv/tg2012")
    assert pruefung.status == "geprueft"
    assert pruefung.geprueft == 3            # zw 2/4/12 einer Zelle
    assert pruefung.fehler == ()
    assert pruefung.befunde == ()
    assert pruefung.blatt == "Tarifrechnung"


def test_rueckcheck_faengt_falsch_gelesenen_wert_auf_fremdem_blatt(
    tmp_path: Path,
):
    """Der Check darf nicht nur laufen, er muss auch beissen: die A-Box
    behauptet 4 % fuer zw=2, die Formel sagt 2 %."""
    fall = _fall_mit_abox(tmp_path, "Tarifrechnung", ratzu2=0.04)
    _schreibe_vorverdichtung(fall, "Tarifrechnung")

    pruefung = pruefe_ratzu_staffeln(fall, "klv/tg2012")
    assert pruefung.status == "geprueft" and pruefung.geprueft == 3
    assert len(pruefung.fehler) == 1
    assert "0.04" in pruefung.fehler[0] and "0.02" in pruefung.fehler[0]


def test_fehlende_vorverdichtung_ist_ein_sichtbarer_ausfall(tmp_path: Path):
    """Ohne Vorverdichtung faellt der Check VOLLSTAENDIG aus.

    Kein Fehler (es liegt nichts vor, was falsch sein koennte), aber
    auch kein stiller Zustand: der Ausfall traegt einen Hinweis, der das
    Kommando nennt, das die Vorverdichtung erzeugt. Ein Fall ohne
    Vorverdichtung darf nicht aussehen wie einer, in dem es nichts
    nachzurechnen gab.
    """
    fall = _fall_mit_abox(tmp_path, "Tarifrechnung")

    pruefung = pruefe_ratzu_staffeln(fall, "klv/tg2012")
    assert pruefung.status == "keine_vorverdichtung"
    assert pruefung.geprueft == 0
    assert pruefung.befunde == () and pruefung.fehler == ()
    assert len(pruefung.hinweise) == 1
    hinweis = pruefung.hinweise[0]
    assert "rechner_pipeline.gates.extract" in hinweis
    assert "eingang/rechner.xlsm" in hinweis
    assert "xlsm-TG2012" in hinweis


def test_fehlende_vorverdichtung_ohne_quellrechner_nennt_die_lage(
    tmp_path: Path,
):
    """Gibt es gar keine Rechner-Quelle, taugt kein extract-Kommando —
    dann sagt der Hinweis genau das, statt ein Kommando zu erfinden."""
    fall = _fall_mit_abox(
        tmp_path, "Tarifrechnung", ratzu_quelle="tarifmeldung",
        mit_rechner=False,
    )

    pruefung = pruefe_ratzu_staffeln(fall, "klv/tg2012")
    assert pruefung.status == "keine_vorverdichtung"
    assert len(pruefung.hinweise) == 1
    assert "tarifrechner" in pruefung.hinweise[0]
    assert "gates.extract" not in pruefung.hinweise[0]


def test_gate_pq3_warnt_bei_fehlender_vorverdichtung(tmp_path: Path):
    """Gate-Ebene zu C6: der Ausfall erreicht Summary UND Warnungen.

    Vorher stand hier nur ein Status im Summary und keine einzige
    Warnung — der komplett ausgefallene Rueck-Check war damit still.
    """
    from rechner_pipeline.gates.abox_validate import main

    fall = _fall_mit_abox(tmp_path, "Tarifrechnung")   # ohne Vorverdichtung

    ergebnis = main(["--fall", str(fall)])
    eintrag = ergebnis.summary["formel_checks"]["klv/tg2012"]
    assert eintrag["status"] == "keine_vorverdichtung"
    assert eintrag["geprueft"] == 0
    assert len(eintrag["hinweise"]) == 1
    warnungen = [
        w for w in ergebnis.warnings
        if w["code"] == "formel_check_ohne_vorverdichtung"
    ]
    assert len(warnungen) == 1
    assert "rechner_pipeline.gates.extract" in warnungen[0]["message"]
    # Sichtbar, aber nicht blockierend (wie beim Befund-Zweig).
    assert ergebnis.exit_code == 0


def test_vorverdichtung_ohne_passende_fundstelle_ist_befund(tmp_path: Path):
    """Der eigentliche Fix: Vorverdichtung DA, aber keine Fundstelle
    liegt auf dem ermittelten Kalkulationsblatt. Frueher fiel das mit
    "keine Vorverdichtung" zu einer stillen Null zusammen."""
    fall = _fall_mit_abox(tmp_path, "Kalkulation")     # A-Box zeigt woanders hin
    _schreibe_vorverdichtung(fall, "Tarifrechnung")    # Blatt heisst anders

    pruefung = pruefe_ratzu_staffeln(fall, "klv/tg2012")
    assert pruefung.status == "befund"
    assert pruefung.geprueft == 0
    assert len(pruefung.befunde) == 3                  # je zw-Aussage einer
    assert "Tarifrechnung" in pruefung.befunde[0]
    assert "Kalkulation!$G$12" in pruefung.befunde[0]


def test_nur_aus_der_meldung_belegte_staffel_ist_kein_befund(tmp_path: Path):
    """Falsch-Positiv-Regression (C7): eine Tarifaussage, die NUR aus der
    Tarifmeldung belegt ist, hat keine Rechner-Fundstelle — und ist
    trotzdem fachlich einwandfrei belegt.

    Der Rueck-Check kann nur Rechner-Fundstellen nachrechnen; alles
    andere liegt ausserhalb seiner Zustaendigkeit. Er zaehlt solche
    Aussagen, bemaengelt sie aber nicht.
    """
    fall = _fall_mit_abox(tmp_path, "Tarifrechnung",
                          ratzu_quelle="tarifmeldung")
    _schreibe_vorverdichtung(fall, "Tarifrechnung")

    pruefung = pruefe_ratzu_staffeln(fall, "klv/tg2012")
    assert pruefung.status == "keine_aussagen"
    assert pruefung.befunde == () and pruefung.fehler == ()
    assert pruefung.geprueft == 0
    assert pruefung.ausserhalb == 3          # zw 2/4/12, je aus der Meldung
    assert pruefung.blatt == "Tarifrechnung"


def test_gate_pq3_warnt_nicht_bei_reiner_meldungs_aussage(tmp_path: Path):
    """Gate-Ebene zu C7: der fachlich korrekte Fall erzeugt KEINE
    Warnung, die Zaehlung steht trotzdem im Summary."""
    from rechner_pipeline.gates.abox_validate import main

    fall = _fall_mit_abox(tmp_path, "Tarifrechnung",
                          ratzu_quelle="tarifmeldung")
    _schreibe_vorverdichtung(fall, "Tarifrechnung")

    ergebnis = main(["--fall", str(fall)])
    eintrag = ergebnis.summary["formel_checks"]["klv/tg2012"]
    assert eintrag == {
        "status": "keine_aussagen", "geprueft": 0, "blatt": "Tarifrechnung",
        "ausserhalb": 3,
    }
    assert ergebnis.warnings == []
    assert ergebnis.exit_code == 0


def test_vorverdichtung_ohne_manifest_ist_befund_nicht_nicht_pruefbar(
    tmp_path: Path,
):
    """Halb vorhandener Export darf nicht wie "nicht vorhanden" aussehen."""
    fall = _fall_mit_abox(tmp_path, "Tarifrechnung")
    verzeichnis = _schreibe_vorverdichtung(fall, "Tarifrechnung")
    (verzeichnis / "export_manifest.json").unlink()

    pruefung = pruefe_ratzu_staffeln(fall, "klv/tg2012")
    assert pruefung.status == "befund"
    assert "export_manifest.json" in pruefung.befunde[0]


def test_gate_pq3_macht_den_ausgefallenen_rueckcheck_sichtbar(tmp_path: Path):
    """Gate-Ebene: der Befund erreicht Summary UND Warnungen — auch wenn
    das Gate im Uebrigen gruen ist (blockieren waere eine fachliche
    Verschaerfung und ist bewusst nicht Teil dieses Fixes)."""
    from rechner_pipeline.gates.abox_validate import main

    fall = _fall_mit_abox(tmp_path, "Kalkulation")
    _schreibe_vorverdichtung(fall, "Tarifrechnung")

    ergebnis = main(["--fall", str(fall)])
    eintrag = ergebnis.summary["formel_checks"]["klv/tg2012"]
    assert eintrag["status"] == "befund"
    assert eintrag["geprueft"] == 0
    assert eintrag["blatt"] == "Tarifrechnung"
    assert any(w["code"] == "formel_check_ausgefallen" for w in ergebnis.warnings)
    # Sichtbar, aber nicht blockierend: das Gate bleibt gruen.
    assert ergebnis.exit_code == 0


def test_gate_pq3_meldet_den_gelaufenen_rueckcheck_mit_zahl(tmp_path: Path):
    """Gegenprobe: passt das Blatt, steht die Pruefzahl im Summary und
    es gibt keine Ausfall-Warnung."""
    from rechner_pipeline.gates.abox_validate import main

    fall = _fall_mit_abox(tmp_path, "Tarifrechnung")
    _schreibe_vorverdichtung(fall, "Tarifrechnung")

    ergebnis = main(["--fall", str(fall)])
    eintrag = ergebnis.summary["formel_checks"]["klv/tg2012"]
    assert eintrag == {
        "status": "geprueft", "geprueft": 3, "blatt": "Tarifrechnung",
    }
    assert ergebnis.warnings == []
    assert ergebnis.exit_code == 0


# --------------------------------------------------------------------------- #
# Blattname GEGEN Dateistamm (C8)
#
# Der Workbook-Blattname ist das Fundstellen-Praefix (``<name>!$G$12``),
# der Dateistamm benennt die abgeleiteten Artefakte
# (``<stamm>_compressed.csv``). Beide fallen auseinander, sobald der
# Blattname Zeichen traegt, die ``safe_filename`` ersetzen muss — genau
# dann traegt die Unterscheidung, und genau das prueft dieser Block.
# --------------------------------------------------------------------------- #

#: Excel erlaubt < > in Blattnamen, das Dateisystem nicht — safe_filename
#: ersetzt sie. Das Leerzeichen bleibt, der Name bleibt also lesbar.
BLATT_MIT_SONDERZEICHEN = "Kalkulation <2015>"
STAMM_MIT_SONDERZEICHEN = "Kalkulation _2015_"


def test_blattname_und_dateistamm_fallen_auseinander(tmp_path: Path):
    """Beide Verwendungen an EINER Vorverdichtung belegt: der Blattname
    kommt aus der Spalte ``Blatt``, der Stamm aus dem Dateinamen — wer
    beide gleichsetzt, greift mit einem davon ins Leere."""
    from rechner_pipeline.quellen.extract.excel import safe_filename
    from rechner_pipeline.quellen.vorverdichtung import lies_vorverdichtung

    fall = _fall_mit_abox(tmp_path, BLATT_MIT_SONDERZEICHEN)
    verzeichnis = _schreibe_vorverdichtung(fall, BLATT_MIT_SONDERZEICHEN)

    # Die Fixture bildet die echte Namensbildung ab, sie erfindet sie nicht.
    assert safe_filename(BLATT_MIT_SONDERZEICHEN) == STAMM_MIT_SONDERZEICHEN
    assert STAMM_MIT_SONDERZEICHEN != BLATT_MIT_SONDERZEICHEN

    blatt = lies_vorverdichtung(verzeichnis).kalkulationsblatt
    assert blatt.name == BLATT_MIT_SONDERZEICHEN     # Fundstellen-Praefix
    assert blatt.stamm == STAMM_MIT_SONDERZEICHEN    # Artefakt-Praefix

    # Verwendung 1 (Artefakte, z. B. Gate P-K1): der STAMM adressiert die
    # abgeleiteten Dateien, der Blattname tut es nicht.
    assert (verzeichnis / f"{blatt.stamm}_compressed.csv").is_file()
    assert not (verzeichnis / f"{blatt.name}_compressed.csv").exists()


def test_rueckcheck_nutzt_den_blattnamen_nicht_den_dateistamm(tmp_path: Path):
    """Verwendung 2 (Rueck-Check): das Fundstellen-Praefix ist der
    BLATTNAME. Mit dem Dateistamm als Praefix faende der Check keine
    einzige Fundstelle und fiele stumm auf null zurueck."""
    fall = _fall_mit_abox(tmp_path, BLATT_MIT_SONDERZEICHEN)
    _schreibe_vorverdichtung(fall, BLATT_MIT_SONDERZEICHEN)

    pruefung = pruefe_ratzu_staffeln(fall, "klv/tg2012")
    assert pruefung.blatt == BLATT_MIT_SONDERZEICHEN
    assert pruefung.status == "geprueft"
    assert pruefung.geprueft == 3
    assert pruefung.fehler == () and pruefung.befunde == ()
