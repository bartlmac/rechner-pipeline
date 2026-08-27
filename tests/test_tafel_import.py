"""Tafel-Import: CSV-Vektoren, Unisex-Ableitung, Konflikt-Schutz, Kern-Integration.

Knoten: klv
"""

from __future__ import annotations

import json
from pathlib import Path
from types import SimpleNamespace

import pytest

from rechner_pipeline.quellen.tafel_import import (
    TafelImportFehler,
    fuege_tafeln_ein,
    importiere_fuer_spez,
    leite_unisex_ab,
    lese_tafel_vektoren,
)
from rechner_pipeline.models.manifest import file_sha256

REPO_ROOT = Path(__file__).resolve().parents[1]
TG2015_XLSM_SHA256 = (
    "e9047bbab1b04209a9eac753903b201153f1cd3f34f4af5fdf414bfaa92e8f5f"
)
TG2015_EXPORTMANIFEST_SHA256 = (
    "14778a5c4d8c5d95a2c559a35e936d80e0e2a6f196cbe72288e949fca6290a3c"
)
TG2015_TAFELN_CSV_SHA256 = (
    "1ce920935ce25701ecf3a3af86e94da7552f5d44e39ee3e1cc0728a8d67af6c5"
)
TG2015_TAFELN = (
    "DAV2008_T_NR_F",
    "DAV2008_T_NR_M",
    "DAV2008_T_NR_U70",
    "DAV2008_T_R_F",
    "DAV2008_T_R_M",
    "DAV2008_T_R_U70",
)
def _csv(tmp_path: Path, zeilen: str) -> Path:
    p = tmp_path / "Tafeln.csv"
    p.write_text(zeilen, encoding="utf-8")
    return p


def test_lese_vektoren_aus_kopfzeile_und_altersspalte(tmp_path: Path):
    from rechner_pipeline.kern.konventionen import MAX_ALTER

    zeilen = [
        "Tafeln;$A$3;x/y;x/y",
        "Tafeln;$B$3;T_M;T_M",
        "Tafeln;$C$3;T_F;T_F",
    ]
    erwartet_m = {}
    erwartet_f = {}
    for alter in range(MAX_ALTER + 1):
        excel_zeile = alter + 4
        qx_m = 0.0 if alter == 0 else 1.0 if alter == MAX_ALTER else 0.01
        qx_f = 1.0 if alter == MAX_ALTER else 0.008
        erwartet_m[alter] = qx_m
        erwartet_f[alter] = qx_f
        zeilen.extend([
            f"Tafeln;$A${excel_zeile};{alter};{alter}",
            f"Tafeln;$B${excel_zeile};{qx_m};{qx_m}",
            f"Tafeln;$C${excel_zeile};{qx_f};{qx_f}",
        ])
    csv = _csv(tmp_path, "\n".join(zeilen))
    vektoren = lese_tafel_vektoren(csv)
    assert vektoren == {"T_M": erwartet_m, "T_F": erwartet_f}


@pytest.mark.parametrize(
    ("roh_qx", "muster"),
    [
        ("nan", "nicht endlich"),
        ("inf", "nicht endlich"),
        ("-inf", "nicht endlich"),
        ("-0.0000001", r"ausserhalb des Bereichs \[0, 1\]"),
        ("1.0000001", r"ausserhalb des Bereichs \[0, 1\]"),
    ],
)
def test_csv_import_lehnt_ungueltige_qx_ab(
    tmp_path: Path, roh_qx: str, muster: str
):
    from rechner_pipeline.kern.konventionen import MAX_ALTER

    zeilen = ["Tafeln;$B$3;T_M;T_M"]
    for alter in range(MAX_ALTER + 1):
        excel_zeile = alter + 4
        qx = roh_qx if alter == 42 else "0.01"
        zeilen.extend([
            f"Tafeln;$A${excel_zeile};{alter};{alter}",
            f"Tafeln;$B${excel_zeile};{qx};{qx}",
        ])

    with pytest.raises(TafelImportFehler, match=muster):
        lese_tafel_vektoren(_csv(tmp_path, "\n".join(zeilen)))


@pytest.mark.parametrize(
    ("fall", "muster"),
    [
        ("dezimal", "nicht ganzzahlig"),
        ("doppelt", "Alter 42.*doppelt"),
        ("fehlend", "Alter .*fehlen"),
        ("zusaetzlich", "zusaetzliche Alter"),
    ],
)
def test_csv_import_verlangt_exakte_eindeutige_ganzzahlalter(
    tmp_path: Path, fall: str, muster: str
):
    from rechner_pipeline.kern.konventionen import MAX_ALTER

    alterswerte = list(range(MAX_ALTER + 1))
    if fall == "dezimal":
        alterswerte[42] = "42.5"
    elif fall == "doppelt":
        alterswerte[43] = 42
    elif fall == "fehlend":
        alterswerte.remove(42)
    else:
        alterswerte.append(MAX_ALTER + 1)

    zeilen = ["Tafeln;$B$3;T_M;T_M"]
    for index, alter in enumerate(alterswerte, start=4):
        zeilen.extend([
            f"Tafeln;$A${index};{alter};{alter}",
            f"Tafeln;$B${index};0.01;0.01",
        ])

    with pytest.raises(TafelImportFehler, match=muster):
        lese_tafel_vektoren(_csv(tmp_path, "\n".join(zeilen)))


def test_vektor_mit_loch_ist_fail_fast(tmp_path: Path):
    csv = _csv(tmp_path, "\n".join([
        "Tafeln;$B$3;T_M;T_M",
        "Tafeln;$A$4;0;0", "Tafeln;$B$4;0.01;0.01",
        "Tafeln;$A$5;1;1",  # B5 fehlt
    ]))
    with pytest.raises(TafelImportFehler, match="ohne Wert"):
        lese_tafel_vektoren(csv)


def test_unisex_ableitung_ist_die_vba_formel_mit_kappung():
    qx_m = {0: 0.5, 1: 0.9}
    qx_f = {0: 0.1, 1: 0.9}
    gemischt = leite_unisex_ab(qx_m, qx_f, 0.7)
    assert gemischt[0] == min(1.0, 0.7 * 0.5 + 0.3 * 0.1)
    # Kappung bei 1 (Tafelende):
    assert leite_unisex_ab({0: 1.0}, {0: 1.5}, 0.7)[0] == 1.0
    with pytest.raises(TafelImportFehler, match="Altersbereiche"):
        leite_unisex_ab({0: 0.1}, {0: 0.1, 1: 0.2}, 0.7)


def _voll(qx: float) -> dict:
    """Vollstaendiger Vektor 0..MAX_ALTER (Einfuege-Vorbedingung)."""
    from rechner_pipeline.kern.konventionen import MAX_ALTER

    return {alter: qx for alter in range(0, MAX_ALTER + 1)}


def _fall_mit_exportkette(tmp_path: Path, monkeypatch):
    """Minimalfall mit echter XLSM -> Manifest -> Tafeln.csv-Hashkette."""
    from rechner_pipeline.kern.konventionen import MAX_ALTER
    from rechner_pipeline.spez import validierung

    fall = tmp_path / "fall"
    eingang = fall / "eingang"
    vorverdichtung = (
        fall / "abgeleitet" / "vorverdichtung" / "xlsm-TG2015"
    )
    eingang.mkdir(parents=True)
    vorverdichtung.mkdir(parents=True)

    xlsm = eingang / "Tarifrechner_KLV_TG2015.xlsm"
    xlsm.write_bytes(b"registrierte-synthetische-xlsm")
    xlsm_sha256 = file_sha256(xlsm)
    (fall / "eingang.json").write_text(
        json.dumps({
            "quellen": [{"datei": xlsm.name, "sha256": xlsm_sha256}],
        }),
        encoding="utf-8",
    )

    tafeln_csv = vorverdichtung / "Tafeln.csv"
    zeilen = [
        "Blatt;Adresse;Formel;Wert",
        "Tafeln;$B$3;T_M;T_M",
    ]
    for alter in range(MAX_ALTER + 1):
        excel_zeile = alter + 4
        zeilen.extend([
            f"Tafeln;$A${excel_zeile};{alter};{alter}",
            f"Tafeln;$B${excel_zeile};0.01;0.01",
        ])
    tafeln_csv.write_text("\n".join(zeilen) + "\n", encoding="utf-8")

    manifest_pfad = vorverdichtung / "export_manifest.json"
    manifest = {
        "out_dir": str(vorverdichtung),
        "sheet_csvs": [str(tafeln_csv)],
        "vba_txts": [],
        "names_manager_csv": "",
        "replacements": {},
        "llm_inputs": [str(tafeln_csv)],
        "all_outputs": [str(tafeln_csv)],
        "warnings": [],
        "prompt_runs": [],
        "output_hashes": [{
            "path": str(tafeln_csv),
            "bytes": tafeln_csv.stat().st_size,
            "sha256": file_sha256(tafeln_csv),
        }],
        "source": {
            "path": str(xlsm),
            "bytes": xlsm.stat().st_size,
            "sha256": xlsm_sha256,
        },
    }
    manifest_pfad.write_text(json.dumps(manifest), encoding="utf-8")

    tafeln_xml = tmp_path / "tafeln.xml"
    tafeln_xml.write_text("<tafeln>\n</tafeln>\n", encoding="utf-8")
    monkeypatch.setattr(
        validierung,
        "lade_spez",
        lambda _fall, _generation: SimpleNamespace(
            tafel_importe=["T_M"], tafel_ableitungen=[], unisex=None
        ),
    )
    return fall, xlsm, tafeln_csv, manifest_pfad, tafeln_xml, manifest


def test_import_bindet_blatt_csv_und_xlsm_mit_vollhash(
    tmp_path: Path, monkeypatch
):
    fall, _xlsm, tafeln_csv, manifest_pfad, tafeln_xml, manifest = (
        _fall_mit_exportkette(tmp_path, monkeypatch)
    )
    ergebnis = importiere_fuer_spez(
        fall, "klv/tg2015", tafeln_xml, dry_run=False
    )

    assert ergebnis["eingefuegt"] == ["T_M"]
    assert ergebnis["quellbeleg"] == {
        "xlsm_sha256": manifest["source"]["sha256"],
        "exportmanifest_sha256": file_sha256(manifest_pfad),
        "blatt_csv_sha256": file_sha256(tafeln_csv),
    }
    xml_text = tafeln_xml.read_text(encoding="utf-8")
    for sha256 in ergebnis["quellbeleg"].values():
        assert len(sha256) == 64
        assert f"sha256 {sha256}" in xml_text
    assert "..." not in xml_text


def test_import_loest_kollidierenden_tafeln_dateinamen_ueber_manifest_auf(
    tmp_path: Path, monkeypatch
):
    fall, _xlsm, tafeln_csv, manifest_pfad, tafeln_xml, manifest = (
        _fall_mit_exportkette(tmp_path, monkeypatch)
    )
    echte_tafeln_csv = tafeln_csv.with_name("Tafeln__2.csv")
    tafeln_csv.rename(echte_tafeln_csv)
    tafeln_csv.write_text(
        "Blatt;Adresse;Formel;Wert\nTafeln ;$A$1;DECOY;DECOY\n",
        encoding="utf-8",
    )
    manifest["sheet_csvs"] = [str(tafeln_csv), str(echte_tafeln_csv)]
    manifest["sheet_artifacts"] = [
        {"original_name": "Tafeln ", "file_name": "Tafeln.csv"},
        {"original_name": "Tafeln", "file_name": "Tafeln__2.csv"},
    ]
    manifest["llm_inputs"] = [str(tafeln_csv), str(echte_tafeln_csv)]
    manifest["all_outputs"] = [str(tafeln_csv), str(echte_tafeln_csv)]
    manifest["output_hashes"] = [
        {
            "path": str(path),
            "bytes": path.stat().st_size,
            "sha256": file_sha256(path),
        }
        for path in (tafeln_csv, echte_tafeln_csv)
    ]
    manifest_pfad.write_text(json.dumps(manifest), encoding="utf-8")

    ergebnis = importiere_fuer_spez(
        fall, "klv/tg2015", tafeln_xml, dry_run=True
    )

    assert ergebnis["angefordert"] == ["T_M"]
    assert ergebnis["eingefuegt"] == []
    assert ergebnis["quellbeleg"]["blatt_csv_sha256"] == file_sha256(
        echte_tafeln_csv
    )


def test_import_parst_genau_die_zuvor_gehashten_tafel_bytes(
    tmp_path: Path, monkeypatch
):
    from rechner_pipeline.quellen import tafel_import

    fall, _xlsm, tafeln_csv, _manifest_pfad, tafeln_xml, _manifest = (
        _fall_mit_exportkette(tmp_path, monkeypatch)
    )
    original_parser = tafel_import.lese_tafel_vektoren

    def ersetze_pfad_vor_parser(
        path: Path,
        inhalt: bytes | None = None,
    ):
        path.write_text(
            path.read_text(encoding="utf-8").replace("0.01", "0.02"),
            encoding="utf-8",
        )
        return original_parser(path, inhalt)

    monkeypatch.setattr(
        tafel_import,
        "lese_tafel_vektoren",
        ersetze_pfad_vor_parser,
    )

    ergebnis = importiere_fuer_spez(
        fall, "klv/tg2015", tafeln_xml, dry_run=False
    )

    assert ergebnis["eingefuegt"] == ["T_M"]
    xml_text = tafeln_xml.read_text(encoding="utf-8")
    assert 'qx="0.01"' in xml_text
    assert 'qx="0.02"' not in xml_text
    assert ergebnis["quellbeleg"]["blatt_csv_sha256"] != file_sha256(tafeln_csv)


def test_dry_run_lehnt_in_hashgueltiger_csv_ungueltige_qx_ab(
    tmp_path: Path, monkeypatch
):
    fall, _xlsm, tafeln_csv, manifest_pfad, tafeln_xml, manifest = (
        _fall_mit_exportkette(tmp_path, monkeypatch)
    )
    tafeln_csv.write_text(
        tafeln_csv.read_text(encoding="utf-8").replace(
            "Tafeln;$B$46;0.01;0.01", "Tafeln;$B$46;nan;nan"
        ),
        encoding="utf-8",
    )
    manifest["output_hashes"][0].update({
        "bytes": tafeln_csv.stat().st_size,
        "sha256": file_sha256(tafeln_csv),
    })
    manifest_pfad.write_text(json.dumps(manifest), encoding="utf-8")
    vorher = tafeln_xml.read_bytes()

    with pytest.raises(TafelImportFehler, match="nicht endlich"):
        importiere_fuer_spez(fall, "klv/tg2015", tafeln_xml, dry_run=True)
    assert tafeln_xml.read_bytes() == vorher


def test_wertgleicher_reimport_ersetzt_gekuerzte_bestandsprovenienz(
    tmp_path: Path, monkeypatch
):
    fall, _xlsm, _tafeln_csv, _manifest_pfad, tafeln_xml, _manifest = (
        _fall_mit_exportkette(tmp_path, monkeypatch)
    )
    erster_lauf = importiere_fuer_spez(
        fall, "klv/tg2015", tafeln_xml, dry_run=False
    )
    vollstaendig = tafeln_xml.read_text(encoding="utf-8")
    vollkommentar = next(
        zeile for zeile in vollstaendig.splitlines() if "<!-- Provenienz:" in zeile
    )
    altkommentar = (
        "  <!-- Provenienz: Tarifrechner_KLV_TG2015.xlsm "
        f"(sha256 {erster_lauf['quellbeleg']['xlsm_sha256'][:16]}...), "
        "Blatt Tafeln, Vektor T_M; importiert via quellen.tafel_import -->"
    )
    tafeln_xml.write_text(
        vollstaendig.replace(vollkommentar, altkommentar), encoding="utf-8"
    )

    trockenlauf = importiere_fuer_spez(
        fall, "klv/tg2015", tafeln_xml, dry_run=True
    )
    assert trockenlauf["bereits_vorhanden_wertgleich"] == ["T_M"]
    assert altkommentar in tafeln_xml.read_text(encoding="utf-8")

    reimport = importiere_fuer_spez(
        fall, "klv/tg2015", tafeln_xml, dry_run=False
    )
    assert reimport["eingefuegt"] == []
    assert tafeln_xml.read_text(encoding="utf-8") == vollstaendig


def test_import_lehnt_fehlendes_exportmanifest_ab(tmp_path: Path, monkeypatch):
    fall, _xlsm, _csv_pfad, manifest_pfad, tafeln_xml, _manifest = (
        _fall_mit_exportkette(tmp_path, monkeypatch)
    )
    manifest_pfad.unlink()

    with pytest.raises(TafelImportFehler, match="ohne Exportmanifest"):
        importiere_fuer_spez(fall, "klv/tg2015", tafeln_xml, dry_run=True)


def test_import_lehnt_nachtraeglich_veraenderte_blatt_csv_ab(
    tmp_path: Path, monkeypatch
):
    fall, _xlsm, tafeln_csv, _manifest_pfad, tafeln_xml, _manifest = (
        _fall_mit_exportkette(tmp_path, monkeypatch)
    )
    tafeln_csv.write_text(
        tafeln_csv.read_text(encoding="utf-8").replace("0.01", "0.02"),
        encoding="utf-8",
    )

    with pytest.raises(TafelImportFehler, match="nach dem Export veraendert"):
        importiere_fuer_spez(fall, "klv/tg2015", tafeln_xml, dry_run=True)


@pytest.mark.parametrize("hashrolle", ["source", "blatt_csv"])
def test_import_lehnt_manipulierten_manifest_hash_ab(
    tmp_path: Path, monkeypatch, hashrolle: str
):
    fall, _xlsm, _csv_pfad, manifest_pfad, tafeln_xml, manifest = (
        _fall_mit_exportkette(tmp_path, monkeypatch)
    )
    if hashrolle == "source":
        manifest["source"]["sha256"] = "f" * 64
        muster = "Eingang-Register"
    else:
        manifest["output_hashes"][0]["sha256"] = "f" * 64
        muster = "nach dem Export veraendert"
    manifest_pfad.write_text(json.dumps(manifest), encoding="utf-8")

    with pytest.raises(TafelImportFehler, match=muster):
        importiere_fuer_spez(fall, "klv/tg2015", tafeln_xml, dry_run=True)


@pytest.mark.parametrize("entfernt", ["source", "output_hashes"])
def test_import_lehnt_unvollstaendige_hashkette_ab(
    tmp_path: Path, monkeypatch, entfernt: str
):
    fall, _xlsm, _csv_pfad, manifest_pfad, tafeln_xml, manifest = (
        _fall_mit_exportkette(tmp_path, monkeypatch)
    )
    manifest[entfernt] = None if entfernt == "source" else []
    manifest_pfad.write_text(json.dumps(manifest), encoding="utf-8")

    muster = "keine Quell-XLSM" if entfernt == "source" else "SHA-256-Beleg"
    with pytest.raises(TafelImportFehler, match=muster):
        importiere_fuer_spez(fall, "klv/tg2015", tafeln_xml, dry_run=True)


def test_import_lehnt_veraenderte_registrierte_xlsm_ab(
    tmp_path: Path, monkeypatch
):
    fall, xlsm, _csv_pfad, _manifest_pfad, tafeln_xml, _manifest = (
        _fall_mit_exportkette(tmp_path, monkeypatch)
    )
    xlsm.write_bytes(b"manipuliert")

    with pytest.raises(TafelImportFehler, match="XLSM.*wurde veraendert"):
        importiere_fuer_spez(fall, "klv/tg2015", tafeln_xml, dry_run=True)


def test_einfuegen_ist_deterministisch_und_konfliktfrei(tmp_path: Path):
    from rechner_pipeline.kern.konventionen import MAX_ALTER

    xml = tmp_path / "tafeln.xml"
    alt_eintraege = "\n".join(
        f'    <entry age="{a}" qx="0.01" />' for a in range(0, MAX_ALTER + 1)
    )
    select_eintraege = "\n".join(
        f'    <entry age="{a}" dauer="0" qx="0.5" />'
        for a in range(0, MAX_ALTER + 1)
    )
    xml.write_text(
        "<?xml version='1.0' encoding='UTF-8'?>\n<tafeln>\n"
        f'  <table name="ALT">\n{alt_eintraege}\n  </table>\n'
        f'  <table name="SEL" select_max="0">\n{select_eintraege}\n  </table>\n'
        "</tafeln>\n", encoding="utf-8",
    )
    neu = {"NEU_B": _voll(0.2), "NEU_A": _voll(0.1)}
    prov = {n: f"Provenienz {n}" for n in neu}
    eingefuegt = fuege_tafeln_ein(xml, neu, prov)
    assert eingefuegt == ["NEU_A", "NEU_B"]          # sortiert
    inhalt1 = xml.read_text(encoding="utf-8")
    assert inhalt1.index("NEU_A") < inhalt1.index("NEU_B")
    assert "Provenienz NEU_A" in inhalt1
    # Idempotent bei wertgleichem Bestand:
    assert fuege_tafeln_ein(xml, neu, prov) == []
    assert xml.read_text(encoding="utf-8") == inhalt1
    # Wert-Konflikt ist hart (kein stiller Overwrite):
    konflikt = dict(_voll(0.01)); konflikt[0] = 0.02
    with pytest.raises(TafelImportFehler, match="kein stiller Overwrite"):
        fuege_tafeln_ein(xml, {"ALT": konflikt}, {"ALT": "x"})
    # Namens-Kollision mit einer Select-Tafel ist hart:
    with pytest.raises(TafelImportFehler, match="Select-Tafel"):
        fuege_tafeln_ein(xml, {"SEL": _voll(0.3)}, {"SEL": "x"})
    # Unvollstaendige Tafel landet nie im XML:
    with pytest.raises(TafelImportFehler, match="fehlen"):
        fuege_tafeln_ein(xml, {"KURZ": {0: 0.1}}, {"KURZ": "x"})
    # Obermengen-Vektor wird nicht still verworfen:
    ober = dict(_voll(0.01)); ober[MAX_ALTER + 1] = 0.5
    with pytest.raises(TafelImportFehler, match="eigener Vorgang"):
        fuege_tafeln_ein(xml, {"ALT": ober}, {"ALT": "x"})


@pytest.mark.parametrize(
    ("qx", "muster"),
    [
        (float("nan"), "nicht endlich"),
        (float("inf"), "nicht endlich"),
        (-1e-12, r"ausserhalb des Bereichs \[0, 1\]"),
        (1.0 + 1e-12, r"ausserhalb des Bereichs \[0, 1\]"),
        (True, "ist keine Zahl"),
        ("0.5", "ist keine Zahl"),
    ],
)
def test_programmatisches_einfuegen_lehnt_ungueltige_qx_ab(
    tmp_path: Path, qx: object, muster: str
):
    xml = tmp_path / "tafeln.xml"
    xml.write_text("<tafeln>\n</tafeln>\n", encoding="utf-8")
    vektor = _voll(0.01)
    vektor[42] = qx

    with pytest.raises(TafelImportFehler, match=muster):
        fuege_tafeln_ein(xml, {"NEU": vektor}, {"NEU": "x"})
    assert xml.read_text(encoding="utf-8") == "<tafeln>\n</tafeln>\n"


def test_kern_fuehrt_die_tg2015_tafeln_mit_korrekter_mischung():
    """Integration: die importierten R/NR-Vektoren und die U70-Ableitungen
    liegen in den Paket-Rechnungsgrundlagen; die Mischung stimmt je Alter."""
    from rechner_pipeline.kern import tafeln as kommutation

    for basis in ("DAV2008_T_R", "DAV2008_T_NR"):
        qx_m = kommutation.qx_vector("M", basis)
        qx_f = kommutation.qx_vector("F", basis)
        qx_u = kommutation.qx_vector("M", f"{basis}_U70")
        for alter in (0, 30, 45, 67, 100, 123):
            # VBA-treu: (1# - FaktorM), NICHT das Literal 0.3 —
            # 1.0-0.7 = 0.30000000000000004 in Doubles.
            erwartet = min(1.0, 0.7 * qx_m[alter] + (1.0 - 0.7) * qx_f[alter])
            assert qx_u[alter] == erwartet, (basis, alter)


def test_ausgelieferte_tg2015_tafeln_tragen_reale_vollhashkette():
    """Die sechs Bestandsbelege duerfen nicht auf Kurzprovenienz regredieren.

    Die Konstanten stammen aus zwei bytegleichen P-Q1-1.1.0-Exporten des unter
    seinem vollstaendigen Git-Blob rekonstruierten und registrierten TG2015-
    Workbooks. Die vier Quellvektoren und zwei U70-Ableitungen wurden dabei
    vollstaendig gegen das ausgelieferte Kern-XML verglichen.
    """
    xml_text = (
        REPO_ROOT / "src" / "rechner_pipeline" / "kern" / "tafeln.xml"
    ).read_text(encoding="utf-8")
    erwartete_hashes = (
        TG2015_XLSM_SHA256,
        TG2015_EXPORTMANIFEST_SHA256,
        TG2015_TAFELN_CSV_SHA256,
    )

    for name in TG2015_TAFELN:
        marker = f'<table name="{name}">'
        assert xml_text.count(marker) == 1
        tabellenzeile = xml_text.rfind("\n", 0, xml_text.index(marker))
        kommentar = xml_text[:tabellenzeile].splitlines()[-1]
        assert "..." not in kommentar
        for sha256 in erwartete_hashes:
            assert len(sha256) == 64
            assert f"sha256 {sha256}" in kommentar

    for sha256 in erwartete_hashes:
        assert xml_text.count(f"sha256 {sha256}") == len(TG2015_TAFELN)
