"""Tafel-Import: CSV-Vektoren, Unisex-Ableitung, Konflikt-Schutz, Kern-Integration."""

from __future__ import annotations

from pathlib import Path

import pytest

from rechner_pipeline.quellen.tafel_import import (
    TafelImportFehler,
    fuege_tafeln_ein,
    leite_unisex_ab,
    lese_tafel_vektoren,
)

REPO_ROOT = Path(__file__).resolve().parents[1]
FALL = REPO_ROOT / "faelle" / "klv-tg2015"


def _csv(tmp_path: Path, zeilen: str) -> Path:
    p = tmp_path / "Tafeln.csv"
    p.write_text(zeilen, encoding="utf-8")
    return p


def test_lese_vektoren_aus_kopfzeile_und_altersspalte(tmp_path: Path):
    csv = _csv(tmp_path, "\n".join([
        "Tafeln;$A$3;x/y;x/y",
        "Tafeln;$B$3;T_M;T_M",
        "Tafeln;$C$3;T_F;T_F",
        "Tafeln;$A$4;0;0", "Tafeln;$B$4;0.01;0.01", "Tafeln;$C$4;0.008;0.008",
        "Tafeln;$A$5;1;1", "Tafeln;$B$5;0.02;0.02", "Tafeln;$C$5;0.016;0.016",
    ]))
    vektoren = lese_tafel_vektoren(csv)
    assert vektoren == {"T_M": {0: 0.01, 1: 0.02}, "T_F": {0: 0.008, 1: 0.016}}


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


def test_einfuegen_ist_deterministisch_und_konfliktfrei(tmp_path: Path):
    xml = tmp_path / "tafeln.xml"
    xml.write_text(
        "<?xml version='1.0' encoding='UTF-8'?>\n<tafeln>\n"
        '  <table name="ALT">\n    <entry age="0" qx="0.01" />\n  </table>\n'
        "</tafeln>\n", encoding="utf-8",
    )
    neu = {"NEU_B": {0: 0.2}, "NEU_A": {0: 0.1}}
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
    with pytest.raises(TafelImportFehler, match="kein stiller Overwrite"):
        fuege_tafeln_ein(xml, {"ALT": {0: 0.02}}, {"ALT": "x"})


def test_kern_fuehrt_die_tg2015_tafeln_mit_korrekter_mischung():
    """Integration: die importierten R/NR-Vektoren und die U70-Ableitungen
    liegen in den Paket-Rechnungsgrundlagen; die Mischung stimmt je Alter."""
    from rechner_pipeline.kern import kommutation

    for basis in ("DAV2008_T_R", "DAV2008_T_NR"):
        qx_m = kommutation.qx_vector("M", basis)
        qx_f = kommutation.qx_vector("F", basis)
        qx_u = kommutation.qx_vector("M", f"{basis}_U70")
        for alter in (0, 30, 45, 67, 100, 123):
            # VBA-treu: (1# - FaktorM), NICHT das Literal 0.3 —
            # 1.0-0.7 = 0.30000000000000004 in Doubles.
            erwartet = min(1.0, 0.7 * qx_m[alter] + (1.0 - 0.7) * qx_f[alter])
            assert qx_u[alter] == erwartet, (basis, alter)


@pytest.mark.skipif(not FALL.is_dir(), reason="kein Fall-Arbeitsbereich faelle/klv-tg2015")
def test_gate_o3_tg2015_golden_master_besteht():
    """DER v0.1-Test: Kern (Spez-parametriert) reproduziert Dirks
    TG2015-Excel — 4 Skalare + komplette Verlaufswerte-Tabelle."""
    from rechner_pipeline.gates.generation_golden import main

    result = main(["--fall", str(FALL), "--generation", "klv/tg2015",
                   "--repo-root", str(REPO_ROOT)])
    assert result.exit_code == 0, result.errors
    assert result.summary["werte_verglichen"] >= 600
    assert result.summary["abweichungen"] == 0
    assert result.summary["modellpunkt"]["tafel"] == "DAV2008_T_NR_U70"
    # Nicht zuordenbare Erwartungsreste sind AUSGEWIESEN, nicht verschwiegen:
    assert "Tafel" in result.summary["erwartung_uebersprungen"]
