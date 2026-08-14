"""Deterministischer Rueck-Check der IF-Staffeln (P4 auf Formelwerte)."""

from __future__ import annotations

from pathlib import Path

import pytest

from rechner_pipeline.quellen.formeln import (
    FormelCheckFehler,
    lese_if_staffel,
    pruefe_ratzu_staffeln,
)

REPO_ROOT = Path(__file__).resolve().parents[1]
FALL = REPO_ROOT / "faelle" / "klv-tg2015"


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
    with pytest.raises(FormelCheckFehler, match="keine IF-Staffel"):
        lese_if_staffel("=A1*B1", "zw")
    with pytest.raises(FormelCheckFehler, match="doppelt"):
        lese_if_staffel("=IF(zw=2,2%,IF(zw=2,3%,0))", "zw")
    with pytest.raises(FormelCheckFehler, match="Default"):
        lese_if_staffel("=IF(zw=2,2%,IF(zw=4,3%", "zw")


@pytest.mark.skipif(not FALL.is_dir(), reason="kein Fall-Arbeitsbereich")
def test_ratzu_extraktion_des_falls_haelt_dem_rueckcheck_stand():
    """Die LLM-gelesenen Staffeln (18 Werte: 3 zw x 6 Zellen) stimmen
    mit den deterministisch geparsten Formeln ueberein."""
    assert pruefe_ratzu_staffeln(FALL, "klv/tg2015") == []
    assert pruefe_ratzu_staffeln(FALL, "klv/tg2012") == []
