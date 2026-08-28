"""Zahlungspfade: die allgemeine Form muss die skalare exakt treffen.

Der Zielkern rechnet die KLV heute ueber drei EINHEITS-Barwerte und
skaliert sie mit Versicherungssumme und Beitrag — darin steckt die
Annahme, beide seien ueber die Laufzeit konstant (ADR-013). Die
allgemeine Form gibt dem Rueckgrat stattdessen ein Profil je Jahr.

Der erste Meilenstein und zugleich die Sperre: Fuer den unveraenderten
Vertrag muss die allgemeine Form die skalare BIT-EXAKT reproduzieren.
Nicht "nahe genug" — die eingefrorenen Referenzwerte vergleichen exakt,
und die Summationsreihenfolge ist Teil dessen, was sie festhalten.

Knoten: klv
"""

from __future__ import annotations

import glob
import json
from pathlib import Path

import pytest

from rechner_pipeline.kern import KLV_DEFAULT, tafeln
from rechner_pipeline.kern.produkte import hole
from rechner_pipeline.kern.produkte.klv import KLV
from rechner_pipeline.kern.zahlungspfad import (
    Zahlungspfad,
    ZahlungspfadFehler,
    paesse,
    standardpfad,
)

REFERENZWERTE = Path(__file__).resolve().parent / "fixtures" / "kern_referenzwerte"


def _referenzpunkte():
    aus = [(KLV_DEFAULT, "KLV_DEFAULT")]
    for pfad in sorted(REFERENZWERTE.glob("referenz_*.json")):
        d = json.loads(pfad.read_text(encoding="utf-8"))
        if d.get("produkt", "klv") != "klv":
            continue
        aus.append((hole("klv").model_point_cls(**d["model_point"]), pfad.stem))
    return aus


@pytest.mark.parametrize("mp,etikett", _referenzpunkte(),
                         ids=[e for _, e in _referenzpunkte()])
def test_standardpfad_trifft_den_skalaren_weg_bit_exakt(mp, etikett):
    """Die Sperre: ohne diese Gleichheit darf die allgemeine Form nicht
    produktiv werden."""
    kern = KLV(mp)
    p = paesse(mp, standardpfad(mp), tafeln.basis(mp.sex, mp.tafel))

    for a in range(0, mp.n + 1):
        z = kern.verlaufszeile(a)
        assert p.rente_n(a) == z.axn, f"axn weicht ab bei a={a}"
        assert p.rente_t(a) == z.axt, f"axt weicht ab bei a={a}"
        assert p.leistungsbarwert(a) == z.leistungsbarwert, (
            f"Leistungsbarwert weicht ab bei a={a}")


def test_ablauf_braucht_den_horizont_n_plus_eins():
    """werte[horizont] ist immer 0.0 — der Off-by-one des ersten Versuchs.

    Faellt dieser Test, liefert der Erlebensfall exakt null statt seines
    Barwerts, und die ganze Reserve ist zu niedrig.
    """
    mp = KLV_DEFAULT
    p = paesse(mp, standardpfad(mp), tafeln.basis(mp.sex, mp.tafel))

    assert p.erleben[0] > 0.0
    # Der Pass reicht ein Jahr weiter als die Versicherungsdauer.
    assert len(p.erleben) == mp.n + 2


def test_todesfalldeckung_endet_mit_dem_vorletzten_jahr():
    """Die Deckung laeuft ueber die Jahre 0 bis n-1.

    Wird das Leistungsprofil auf n+1 Jahre gezogen, kommt ein Jahr
    Deckung dazu und der Leistungsbarwert wird zu gross.
    """
    mp = KLV_DEFAULT
    pfad = standardpfad(mp)

    assert len(pfad.leistung) == mp.n
    with pytest.raises(ZahlungspfadFehler, match="Leistungsprofil"):
        Zahlungspfad(leistung=(1.0,) * (mp.n + 1), ablauf=1.0,
                     beitrag=(1.0,) * mp.t).pruefe(mp)


def test_beitragsprofil_muss_zur_beitragszahlungsdauer_passen():
    mp = KLV_DEFAULT
    with pytest.raises(ZahlungspfadFehler, match="Beitragsprofil"):
        Zahlungspfad(leistung=(1.0,) * mp.n, ablauf=1.0,
                     beitrag=(1.0,) * (mp.t + 3)).pruefe(mp)


def test_standardpfad_ist_als_konstant_erkennbar():
    """Nur der konstante Pfad hat einen eingefrorenen Referenzwert."""
    mp = KLV_DEFAULT
    assert standardpfad(mp).ist_konstant

    beitragsfrei = Zahlungspfad(
        leistung=(1.0,) * mp.n, ablauf=1.0,
        beitrag=tuple(1.0 if j < 5 else 0.0 for j in range(mp.t)))
    assert not beitragsfrei.ist_konstant


def test_beitragsfreistellung_senkt_den_beitragsbarwert():
    """Ein Profil, das ab Jahr 5 auf null faellt, muss sich zeigen."""
    mp = KLV_DEFAULT
    basis = tafeln.basis(mp.sex, mp.tafel)
    voll = paesse(mp, standardpfad(mp), basis)
    frei = paesse(mp, Zahlungspfad(
        leistung=(1.0,) * mp.n, ablauf=1.0,
        beitrag=tuple(1.0 if j < 5 else 0.0 for j in range(mp.t))), basis)

    # Bis Jahr 5 identisch, danach kleiner — und ab Jahr 5 null.
    assert frei.rente_t(0) < voll.rente_t(0)
    assert frei.rente_t(5) == 0.0
    assert voll.rente_t(5) > 0.0


def test_herabsetzung_senkt_den_beitragsbarwert_anteilig():
    """Der fortgefuehrte Anteil f schlaegt linear durch.

    Die Beitragsrente ist linear im Profil; ein ab Jahr 5 halbierter
    Beitrag ergibt genau den halben Restbarwert.
    """
    mp = KLV_DEFAULT
    basis = tafeln.basis(mp.sex, mp.tafel)
    voll = paesse(mp, standardpfad(mp), basis)
    halb = paesse(mp, Zahlungspfad(
        leistung=(1.0,) * mp.n, ablauf=1.0,
        beitrag=tuple(1.0 if j < 5 else 0.5 for j in range(mp.t))), basis)

    assert halb.rente_t(5) == pytest.approx(voll.rente_t(5) * 0.5, rel=1e-12)
