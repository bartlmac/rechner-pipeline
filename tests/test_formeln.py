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

REPO_ROOT = Path(__file__).resolve().parents[1]
# Eingefrorener Vorlauf-Fall als lokales Regressions-Fixture; skipt sauber,
# wo faelle/ fehlt (z.B. frischer Clone).
FALL = REPO_ROOT / "faelle" / "archiv" / "baldrian-klv-tg2015"


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
        lese_if_staffel("=A1*B1", "zw")
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


@pytest.mark.skipif(not FALL.is_dir(), reason="kein Archiv-Fall faelle/archiv/baldrian-klv-tg2015")
def test_ratzu_extraktion_des_falls_haelt_dem_rueckcheck_stand():
    """Die LLM-gelesenen Staffeln (18 Werte: 3 zw x 6 Zellen) stimmen
    mit den deterministisch geparsten Formeln ueberein."""
    pruefung = pruefe_ratzu_staffeln(FALL, "klv/tg2015")
    assert pruefung.fehler == ()
    assert pruefung.status == "geprueft"
    assert pruefung.geprueft == 18              # 3 zw x 6 Zellen
    # Auch TG2012 fuehrt eine Staffel-Formel (eine Zelle, 3 zw-Werte):
    pruefung = pruefe_ratzu_staffeln(FALL, "klv/tg2012")
    assert pruefung.fehler == () and pruefung.geprueft == 3


# --------------------------------------------------------------------------- #
# Regression: der Blattname ist Sache des Quellsystems (Review-Befund O1)
#
# Der Rueck-Check verdrahtete "Kalkulation" hart. Ein Quellsystem, das
# sein Kalkulationsblatt anders nennt (Baldrian: "Tarifrechnung"), lief
# damit still an jeder Pruefung vorbei, waehrend Gate O1 gruen blieb.
# Die Fixture ist bewusst selbst erzeugt und haengt an KEINEM Fall unter
# faelle/ (die Arbeitsbereiche sind gitignored).
# --------------------------------------------------------------------------- #

ZEIT = "2026-08-19T06:00:00+00:00"

#: Vollstaendiger Pflichtumfang, damit Gate O1 an nichts anderem scheitert.
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
    """
    import json

    verzeichnis = fall / "abgeleitet" / "vorverdichtung" / "xlsm-TG2012"
    verzeichnis.mkdir(parents=True, exist_ok=True)
    blatt_csv = verzeichnis / f"{blattname}.csv"
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
    komprimiert = verzeichnis / f"{blattname}_compressed.csv"
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


def _fall_mit_abox(tmp_path: Path, fundstellen_blatt: str, ratzu2=0.02) -> Path:
    """Fall-Arbeitsbereich mit einer A-Box, deren ratzu-Aussagen auf
    ``<fundstellen_blatt>!$G$12`` zeigen."""
    import json as _json

    from rechner_pipeline.fall import anlegen, registrieren
    from rechner_pipeline.ontologie.abox import speichere
    from rechner_pipeline.ontologie.befuellung import (
        FragmentWert, FragmentZelle, QuellFragment, baue_abox,
    )

    fall = tmp_path / "fall"
    anlegen(fall, beschreibung="Fixture Blattname")
    quelle = tmp_path / "rechner.xlsm"
    quelle.write_bytes(b"rechner-bytes")
    registrieren(fall, quelle)

    parameter = {
        feld: FragmentWert(wert=wert, fundstelle=f"rechner.xlsm:{feld}")
        for feld, wert in PFLICHT_WERTE.items()
    }
    for feld, wert in (("ratzu_zw2", ratzu2), ("ratzu_zw4", 0.03),
                       ("ratzu_zw12", 0.05)):
        parameter[feld] = FragmentWert(
            wert=wert, fundstelle=f"{fundstellen_blatt}!$G$12"
        )
    fragment = QuellFragment(
        generation="tg2012", quelle_datei="rechner.xlsm",
        quelle_art="tarifrechner",
        zellen=[FragmentZelle(parameter=parameter)],
    )
    register = _json.loads((fall / "eingang.json").read_text(encoding="utf-8"))
    abox = baue_abox(
        str(fall), [fragment], register, ["test/extraktion@abc1234"], ZEIT
    )
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


def test_fehlende_vorverdichtung_bleibt_ehrlich_nicht_pruefbar(tmp_path: Path):
    """Ohne Vorverdichtung gibt es nichts nachzurechnen — das ist ein
    ausgewiesener Zustand, kein Befund."""
    fall = _fall_mit_abox(tmp_path, "Tarifrechnung")

    pruefung = pruefe_ratzu_staffeln(fall, "klv/tg2012")
    assert pruefung.status == "nicht_pruefbar"
    assert pruefung.geprueft == 0
    assert pruefung.befunde == () and pruefung.fehler == ()


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


def test_gate_o1_macht_den_ausgefallenen_rueckcheck_sichtbar(tmp_path: Path):
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


def test_gate_o1_meldet_den_gelaufenen_rueckcheck_mit_zahl(tmp_path: Path):
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
