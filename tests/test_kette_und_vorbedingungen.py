"""Systempruefungs-Fixes: Merge-Ledger-Kette, Gate-Vorbedingungen, Rollen.

Knoten: klv
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from rechner_pipeline.fall import anlegen, registrieren
from rechner_pipeline.gates.abox_merge import main as merge_cli
from rechner_pipeline.gates.abox_validate import main as pq3
from rechner_pipeline.gates.gate_entscheid import main as p9
from rechner_pipeline.ontologie import PFLICHT_PARAMETER, belegt
from rechner_pipeline.ontologie.abox import abox_pfad, lade, speichere
from rechner_pipeline.ontologie.befuellung import loese_diskrepanz_auf
from rechner_pipeline.ontologie.kette import fragmente_ordner, pruefe_kette

PLAUSIBEL = {
    "zins": 0.0175, "tafel": "DAV2008_T", "alpha": 0.025, "beta1": 0.03,
    "gamma1": 0.001, "gamma2": 0.00125, "gamma3": 0.0025,
    "policy_fee": 12.0, "stoab_satz": 0.005, "stoab_min": 50.0,
    "stoab_max": 150.0, "min_alter_flex": 60, "min_rlz_flex": 5,
}
AKTEUR = "test/extrahiere-quellfragment@abc1234"


def _freigabe_arg(fall: Path) -> list[str]:
    schluessel = fall.parent / "p9-freigabe.key"
    if not schluessel.exists():
        schluessel.write_bytes(b"test-only-p9-authorization-key!" * 2)
        schluessel.chmod(0o600)
    return ["--freigabe-schluessel", str(schluessel)]


def _fragment_json(datei: str, art: str, **override) -> dict:
    parameter = {
        feld: {"wert": PLAUSIBEL[feld], "fundstelle": f"{datei}:{feld}"}
        for feld in PFLICHT_PARAMETER
    }
    for feld, wert in override.items():
        parameter[feld] = {"wert": wert, "fundstelle": f"{datei}:{feld}"}
    return {
        "generation": "tg2012", "quelle_datei": datei, "quelle_art": art,
        "zellen": [{"auspraegungen": {}, "parameter": parameter}],
        "anmerkungen": [f"Beobachtung aus {datei}"],
    }


@pytest.fixture()
def fall_mit_fragmenten(tmp_path: Path) -> Path:
    f = tmp_path / "fall"
    anlegen(f)
    for name in ("rechner.xlsm", "meldung.docx"):
        q = tmp_path / name
        q.write_bytes(name.encode())
        registrieren(f, q)
    ordner = fragmente_ordner(f)
    ordner.mkdir(parents=True)
    (ordner / "tg2012-meldung.json").write_text(json.dumps(
        _fragment_json("meldung.docx", "tarifmeldung", beta1=0.025)),
        encoding="utf-8")
    (ordner / "tg2012-rechner.json").write_text(json.dumps(
        _fragment_json("rechner.xlsm", "tarifrechner", beta1=0.03)),
        encoding="utf-8")
    (ordner / "akteure.json").write_text(json.dumps({
        "tg2012-meldung.json": AKTEUR,
        "tg2012-rechner.json": AKTEUR.replace("quellfragment", "quellfragment-b"),
    }), encoding="utf-8")
    return f


def test_merge_cli_schreibt_abox_und_ketten_ledger(fall_mit_fragmenten):
    f = fall_mit_fragmenten
    result = merge_cli(["--fall", str(f)])
    assert result.exit_code == 0
    assert result.summary["diskrepanzen"] == 1        # beta1-Konflikt
    assert set(result.summary["fragment_hashes"]) == {
        "tg2012-meldung.json", "tg2012-rechner.json"}
    assert abox_pfad(f).is_file()
    # Anmerkungen der Agenten sind in der A-Box erhalten (P7):
    abox = lade(f)
    assert any("Beobachtung aus meldung.docx" in a
               for a in abox.generationen[0].anmerkungen)
    # Kette ist geschlossen:
    assert pruefe_kette(f) == []


def test_kette_faengt_direkte_abox_edits(fall_mit_fragmenten):
    f = fall_mit_fragmenten
    merge_cli(["--fall", str(f)])
    abox = lade(f)
    # Manipulation 1: Widerspruch lautlos loeschen
    abox.diskrepanzen.clear()
    zelle = abox.generationen[0].zellen[0]
    from rechner_pipeline.ontologie import belegt, Provenienz
    prov = zelle.parameter["zins"].provenienz[0]
    zelle.parameter["beta1"] = belegt(0.03, [prov])
    speichere(abox, f)
    befunde = pruefe_kette(f)
    assert any("Diskrepanzenmenge" in b for b in befunde)
    # ... und Gate P-Q3 faellt darauf:
    result = pq3(["--fall", str(f)])
    assert result.exit_code == 20
    assert any(e["code"] == "kette" for e in result.errors)


def test_kette_akzeptiert_dokumentierte_aufloesung(fall_mit_fragmenten):
    f = fall_mit_fragmenten
    merge_cli(["--fall", str(f)])
    abox = lade(f)
    [d] = abox.diskrepanzen
    loese_diskrepanz_auf(abox, d.id, 0.03, "agent (vorlaeufig)", "GM-Zweck",
                         "2026-08-15T12:00:00+00:00", vorlaeufig=True)
    speichere(abox, f)
    assert pruefe_kette(f) == []
    # ... aber ein ERFUNDENER Wert (keine Lesart) faellt:
    abox = lade(f)
    zelle = abox.generationen[0].zellen[0]
    from rechner_pipeline.ontologie import belegt
    prov = zelle.parameter["beta1"].provenienz[0]
    zelle.parameter["beta1"] = belegt(0.0275, [prov])   # Mittelwert erfunden
    speichere(abox, f)
    assert any("entspricht nicht dem entschiedenen Wert" in b
               for b in pruefe_kette(f))


def test_pq3_akzeptiert_beleg_der_gewaehlten_lesart(fall_mit_fragmenten):
    f = fall_mit_fragmenten
    merge_cli(["--fall", str(f)])
    abox = lade(f)
    [diskrepanz] = abox.diskrepanzen
    gewaehlte_lesart = next(
        lesart for lesart in diskrepanz.lesarten if lesart.wert == 0.03
    )

    loese_diskrepanz_auf(
        abox, diskrepanz.id, 0.03, "agent (vorlaeufig)", "GM-Zweck",
        "2026-08-15T12:00:00+00:00", vorlaeufig=True,
    )
    speichere(abox, f)

    result = pq3(["--fall", str(f)])
    assert result.exit_code == 0
    aussage = lade(f).generationen[0].zellen[0].parameter["beta1"]
    assert aussage.provenienz == gewaehlte_lesart.provenienz


def test_pq3_lehnt_beleg_der_verworfenen_lesart_ab(fall_mit_fragmenten):
    f = fall_mit_fragmenten
    merge_cli(["--fall", str(f)])
    abox = lade(f)
    [diskrepanz] = abox.diskrepanzen
    verworfene_lesart = next(
        lesart for lesart in diskrepanz.lesarten if lesart.wert == 0.025
    )
    loese_diskrepanz_auf(
        abox, diskrepanz.id, 0.03, "agent (vorlaeufig)", "GM-Zweck",
        "2026-08-15T12:00:00+00:00", vorlaeufig=True,
    )
    zelle = abox.generationen[0].zellen[0]
    zelle.parameter["beta1"] = belegt(
        0.03, list(verworfene_lesart.provenienz)
    )
    speichere(abox, f)

    result = pq3(["--fall", str(f)])
    assert result.exit_code == 20
    assert any(
        error["code"] == "kette"
        and "kein Beleg aus einer Lesart mit dem entschiedenen Wert" in
        error["message"]
        for error in result.errors
    )


def test_pq3_lehnt_zusaetzlichen_beleg_der_verworfenen_lesart_ab(
    fall_mit_fragmenten,
):
    f = fall_mit_fragmenten
    merge_cli(["--fall", str(f)])
    abox = lade(f)
    [diskrepanz] = abox.diskrepanzen
    gewaehlte_lesart = next(
        lesart for lesart in diskrepanz.lesarten if lesart.wert == 0.03
    )
    verworfene_lesart = next(
        lesart for lesart in diskrepanz.lesarten if lesart.wert == 0.025
    )
    loese_diskrepanz_auf(
        abox, diskrepanz.id, 0.03, "agent (vorlaeufig)", "GM-Zweck",
        "2026-08-15T12:00:00+00:00", vorlaeufig=True,
    )
    zelle = abox.generationen[0].zellen[0]
    zelle.parameter["beta1"] = belegt(
        0.03,
        list(gewaehlte_lesart.provenienz + verworfene_lesart.provenienz),
    )
    speichere(abox, f)

    result = pq3(["--fall", str(f)])
    assert result.exit_code == 20
    assert any(
        error["code"] == "kette"
        and "Beleg einer verworfenen Lesart" in error["message"]
        for error in result.errors
    )


def test_kette_faengt_manipulierte_fragmente(fall_mit_fragmenten):
    f = fall_mit_fragmenten
    merge_cli(["--fall", str(f)])
    frag = fragmente_ordner(f) / "tg2012-rechner.json"
    daten = json.loads(frag.read_text(encoding="utf-8"))
    daten["zellen"][0]["parameter"]["beta1"]["wert"] = 0.025  # nachtraeglich
    frag.write_text(json.dumps(daten), encoding="utf-8")
    assert any("Hash weicht vom Merge-Ledger ab" in b for b in pruefe_kette(f))


def test_merge_cli_erzwingt_akteur_konvention(fall_mit_fragmenten):
    f = fall_mit_fragmenten
    akteure = fragmente_ordner(f) / "akteure.json"
    akteure.write_text(json.dumps({
        "tg2012-meldung.json": "claude",              # verletzt Konvention
        "tg2012-rechner.json": AKTEUR,
    }), encoding="utf-8")
    result = merge_cli(["--fall", str(f)])
    assert result.exit_code == 20
    assert any("Konvention" in e["message"] for e in result.errors)


def test_am4_verlangt_pk1_und_geltenden_aq1(fall_mit_fragmenten):
    """Befund 1 der Systempruefung: A-M4 ohne P-K1 oder ohne A-Q1-Annahme
    auf demselben Stand ist nicht mehr snapshotbar."""
    f = fall_mit_fragmenten
    merge_cli(["--fall", str(f)])
    abox = lade(f)
    [d] = abox.diskrepanzen
    loese_diskrepanz_auf(abox, d.id, 0.03, "Bartek", "entschieden",
                         "2026-08-15T12:00:00+00:00", vorlaeufig=False)
    speichere(abox, f)
    assert pq3(["--fall", str(f)]).exit_code == 0

    basis = ["--fall", str(f), "--rolle", "mensch", "--entscheider", "B",
             "--begruendung", "x", "--repo-root", ".", *_freigabe_arg(f)]
    # A-M4 ohne P-K1:
    result = p9(["--gate", "A-M4", "--entscheid", "angenommen", *basis])
    assert result.exit_code == 20
    assert any("P-K1" in e["message"] for e in result.errors)
    # A-Q1-Annahme geht (P-Q3 gruen + an den geprueften A-Box-Stand gebunden):
    assert p9(["--gate", "A-Q1", "--entscheid", "angenommen", *basis]).exit_code == 0
    # A-M4 scheitert weiter an P-K1 (nie gelaufen) — nicht an A-Q1:
    result = p9(["--gate", "A-M4", "--entscheid", "angenommen", *basis])
    assert any("P-K1" in e["message"] for e in result.errors)


def test_aq1_annahme_verlangt_gebundenes_pq3(fall_mit_fragmenten):
    f = fall_mit_fragmenten
    merge_cli(["--fall", str(f)])
    abox = lade(f)
    [d] = abox.diskrepanzen
    loese_diskrepanz_auf(abox, d.id, 0.03, "Bartek", "entschieden",
                         "2026-08-15T12:00:00+00:00", vorlaeufig=False)
    speichere(abox, f)
    basis = ["--fall", str(f), "--rolle", "mensch", "--entscheider", "B",
             "--begruendung", "x", "--repo-root", "."]
    # Ohne P-Q3-Lauf:
    result = p9(["--gate", "A-Q1", "--entscheid", "angenommen", *basis])
    assert result.exit_code == 20
    assert any(e["code"] == "vorbedingung" for e in result.errors)
    # P-Q3 gruen, dann A-Box VERAENDERN -> Provenienzbindung bricht:
    assert pq3(["--fall", str(f)]).exit_code == 0
    abox = lade(f)
    abox.generationen[0].anmerkungen.append("nachtraeglich")
    speichere(abox, f)
    result = p9(["--gate", "A-Q1", "--entscheid", "angenommen", *basis])
    assert result.exit_code == 20
    assert any("Provenienzvertrag" in e["message"] for e in result.errors)


def test_agent_rolle_darf_nur_ablehnen(fall_mit_fragmenten):
    f = fall_mit_fragmenten
    merge_cli(["--fall", str(f)])
    basis = ["--fall", str(f), "--entscheider", "claude-fable-5",
             "--begruendung", "Zwischenstand", "--repo-root", "."]
    result = p9(["--gate", "A-Q1", "--entscheid", "angenommen",
                 "--rolle", "agent", *basis])
    assert result.exit_code == 2
    assert any("Menschen vorbehalten" in e["message"] for e in result.errors)
    # Nicht nur der Exit-Code zaehlt, sondern die Wirkung: es darf kein
    # angenommener Snapshot entstanden sein, gleich mit welchem Code der
    # Aufruf abbricht.
    entscheide_dir = Path(f) / "entscheide"
    angenommen = [
        pfad for pfad in entscheide_dir.rglob("*.json")
        if json.loads(pfad.read_text(encoding="utf-8")).get("entscheid")
        == "angenommen"
    ]
    assert angenommen == []
    result = p9(["--gate", "A-Q1", "--entscheid", "abgelehnt",
                 "--rolle", "agent", *basis])
    assert result.exit_code == 0
    snapshot = json.loads(Path(result.paths["snapshot"]).read_text(encoding="utf-8"))
    assert snapshot["rolle"] == "agent"


def test_entscheide_verlangt_rolle_mensch_und_archiviert(fall_mit_fragmenten, capsys):
    from rechner_pipeline.ontologie.entscheide import main as entscheide

    f = fall_mit_fragmenten
    merge_cli(["--fall", str(f)])
    abox = lade(f)
    [d] = abox.diskrepanzen
    loese_diskrepanz_auf(abox, d.id, 0.03, "agent (vorlaeufig)", "GM",
                         "2026-08-15T12:00:00+00:00", vorlaeufig=True)
    speichere(abox, f)
    # Ohne --rolle mensch: argparse lehnt ab (SystemExit 2)
    with pytest.raises(SystemExit):
        entscheide(["--fall", str(f), "--diskrepanz", d.id, "--wert", "0.025",
                    "--entscheider", "B", "--begruendung", "x"])
    capsys.readouterr()
    rc = entscheide(["--fall", str(f), "--rolle", "mensch",
                     "--diskrepanz", d.id, "--wert", "0.025",
                     "--entscheider", "Bartek", "--begruendung", "Meldung gilt"])
    assert rc == 0
    capsys.readouterr()
    abox = lade(f)
    [d2] = abox.diskrepanzen
    # Der Weg vorlaeufig -> endgueltig ist auditierbar (append-only):
    assert d2.entscheidung.entscheider == "Bartek"
    assert len(d2.entscheidungs_historie) == 1
    assert d2.entscheidungs_historie[0].vorlaeufig is True
    assert d2.entscheidungs_historie[0].entscheider == "agent (vorlaeufig)"
    # Und die Kette akzeptiert den neu entschiedenen Wert:
    assert pruefe_kette(f) == []
