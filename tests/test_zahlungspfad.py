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


# --------------------------------------------------------------------------- #
# Die zusammengesetzte Reserve
# --------------------------------------------------------------------------- #


@pytest.mark.parametrize("mp,etikett", _referenzpunkte(),
                         ids=[e for _, e in _referenzpunkte()])
def test_reserve_aus_dem_pfad_trifft_den_skalaren_weg_bit_exakt(mp, etikett):
    """Die zweite Haelfte der Sperre: nicht nur die Paesse, auch die
    daraus gebildete Reserve muss exakt stimmen."""
    from rechner_pipeline.kern.zahlungspfad import verlaufszeile

    kern = KLV(mp)
    basis = tafeln.basis(mp.sex, mp.tafel)
    pfad = standardpfad(mp)

    for a in range(0, mp.n + 1):
        z = kern.verlaufszeile(a)
        pz = verlaufszeile(mp, pfad, basis, a)
        for name in ("vx_bpfl", "drx_bpfl", "vx_bfr", "vx_mrv"):
            assert getattr(pz, name) == getattr(z, name), (
                f"{name} weicht ab bei a={a}")


def test_herabgesetzter_vertrag_zahlt_am_ablauf_die_herabgesetzte_summe():
    """Der Zweck der ganzen Umstellung, an einer Zahl.

    Ohne Zahlungspfade rechnet der Kern den Vertrag mit seinen
    Ursprungsparametern und zahlte am Ablauf die volle Summe — im
    Beispiel 100.000 statt 69.531, ein knappes Drittel zu viel an den
    Kunden.
    """
    from rechner_pipeline.kern.beitragsreduktion import PROSPEKTIV, reduziere
    from rechner_pipeline.kern.zahlungspfad import (
        Zahlungspfad, verlaufszeile, vertragskonstanten)

    mp = KLV_DEFAULT
    basis = tafeln.basis(mp.sex, mp.tafel)
    jahr, f = 5, 0.6
    neu = reduziere(KLV(mp), jahr, f, verfahren=PROSPEKTIV).vs_neu
    anteil = neu / mp.sum_insured

    pfad = Zahlungspfad(
        leistung=tuple(1.0 if j < jahr else anteil for j in range(mp.n)),
        ablauf=anteil,
        beitrag=tuple(1.0 if j < jahr else f for j in range(mp.t)),
    )
    am_ablauf = verlaufszeile(
        mp, pfad, basis, mp.n, skalare=vertragskonstanten(mp, basis))

    assert am_ablauf.drx_bpfl == pytest.approx(neu, abs=0.01)
    # Und deutlich unter der ungekuerzten Summe — das ist der Punkt.
    assert am_ablauf.drx_bpfl < mp.sum_insured * 0.75


def test_die_verlustfreiheit_ist_im_pfadmodell_eine_gleichung():
    """Ein naiv gewaehlter Leistungsfaktor haelt sie NICHT.

    Kuenftige Beitraege zu senken erhoeht die prospektive Reserve,
    solange die Leistung nicht entsprechend faellt. Welcher Faktor sie
    unveraendert laesst, haengt an der Kostenzuordnung — die steht im
    Tarifwerk, nicht im Code. Dieser Test haelt fest, dass das Modell
    die Frage STELLT, statt sie stillschweigend zu beantworten.
    """
    from rechner_pipeline.kern.beitragsreduktion import PROSPEKTIV, reduziere
    from rechner_pipeline.kern.zahlungspfad import (
        Zahlungspfad, verlaufszeile, vertragskonstanten)

    mp = KLV_DEFAULT
    basis = tafeln.basis(mp.sex, mp.tafel)
    jahr, f = 5, 0.6
    r = reduziere(KLV(mp), jahr, f, verfahren=PROSPEKTIV)
    anteil = r.vs_neu / mp.sum_insured

    pfad = Zahlungspfad(
        leistung=tuple(1.0 if j < jahr else anteil for j in range(mp.n)),
        ablauf=anteil,
        beitrag=tuple(1.0 if j < jahr else f for j in range(mp.t)),
    )
    im_vorfalljahr = verlaufszeile(
        mp, pfad, basis, jahr, skalare=vertragskonstanten(mp, basis))

    # Die Reserve springt — der naive Faktor ist nicht der verlustfreie.
    assert im_vorfalljahr.drx_bpfl != pytest.approx(r.dk_nach, abs=0.01)
    assert im_vorfalljahr.drx_bpfl > r.dk_nach
