"""Migrationszugang: konstruktive Neuberechnung eines uebernommenen Vertrags.

Das ist der Vorgang, um den es in diesem Branch geht. Geprueft wird, was
ihn ausmacht:

* Das Zielsystem rechnet SELBST aus den Ursprungsparametern — der
  gelieferte Wert geht nur ins Residuum ein, nie in die Bewertung.
* Der Zugang ist ein eigener Geschaeftsvorfall mit dem Residuum als
  Betrag, kein Neuzugang aus dem Nichts.
* Was nicht verankert werden kann, wird nicht still uebernommen.

Knoten: klv
"""

from __future__ import annotations

import dataclasses
import datetime as _dt

import pytest

from rechner_pipeline.kern import KLV_DEFAULT
from rechner_pipeline.kern.rechenkern import Rechenkern
from rechner_pipeline.bestand.migrationszugang import (
    BETRAG_ART,
    MIG,
    MigrationszugangFehler,
    Uebernahme,
    uebernehmen,
    zugangsbericht,
    zugangsjournal,
)
from rechner_pipeline.models.bestand import LEDGER_NAMES

MP = dataclasses.asdict(KLV_DEFAULT)
KERN = Rechenkern(KLV_DEFAULT)
TA_JAHR = 9
TA = 12 * TA_JAHR
PROSP = KERN.verlaufszeile(TA_JAHR).drx_bpfl
STICHTAG = _dt.date(2026, 1, 1)


def _uebernahme(police_id: int = 1, delta: float = -850.0, **kwargs) -> Uebernahme:
    kwargs.setdefault("monate_ta", TA)
    return Uebernahme(
        police_id=police_id, model_point=MP, dk_ist=PROSP + delta, **kwargs
    )


# --------------------------------------------------------------------------- #
# 1. Konstruktive Neuberechnung
# --------------------------------------------------------------------------- #


def test_das_zielsystem_rechnet_selbst_statt_den_wert_zu_uebernehmen():
    """Der Kern der Methode: der gelieferte Wert ist nicht der Bewertungswert.

    Zwei Vertraege mit identischen Ursprungsparametern und verschiedenen
    gelieferten Staenden bekommen denselben prospektiven Wert. Nur das
    Residuum unterscheidet sie.
    """
    a, b = uebernehmen([_uebernahme(1, -850.0), _uebernahme(2, +420.0)])
    assert a.dk_prosp == b.dk_prosp == pytest.approx(PROSP)
    assert a.residuum == pytest.approx(-850.0)
    assert b.residuum == pytest.approx(+420.0)


def test_residuum_ist_geliefert_minus_prospektiv():
    e, = uebernehmen([_uebernahme(delta=-333.33)])
    assert e.residuum == pytest.approx(e.dk_ist - e.dk_prosp, rel=1e-12)


def test_ohne_differenz_bleibt_die_schicht_leer():
    """Ein Vertrag, den beide Systeme gleich sehen, traegt keine Schicht."""
    e, = uebernehmen([_uebernahme(delta=0.0)])
    assert e.getragen
    assert e.parameter.rho == 0.0


@pytest.mark.parametrize("delta", [-2000.0, -1.0, 1.0, 5000.0])
def test_die_schicht_traegt_das_residuum_exakt(delta: float):
    """Die Verankerung trifft den gelieferten Stand auf den Cent.

    Das ist der Sinn: Nach der Uebernahme zeigt das Zielsystem denselben
    Wert wie die Lieferung — aber es hat ihn gerechnet, nicht kopiert.
    """
    from rechner_pipeline.kern.korrekturschicht import (
        Korrekturschicht,
        form_proportional_zur_basis,
    )

    e, = uebernehmen([_uebernahme(delta=delta)])
    basis = [KERN.verlaufszeile(a).drx_bpfl for a in range(TA_JAHR, KLV_DEFAULT.n + 1)]
    bw = KERN.produkt.bw
    schicht = Korrekturschicht(bw.modell, ((bw.AKTIV, bw.TOT),))
    verlauf = schicht.verlauf(
        e.parameter, form_proportional_zur_basis(basis), KLV_DEFAULT.x + TA_JAHR
    )
    assert e.dk_prosp + verlauf[0] == pytest.approx(e.dk_ist, rel=1e-12)


# --------------------------------------------------------------------------- #
# 2. Der Zugang ist ein eigener Geschaeftsvorfall
# --------------------------------------------------------------------------- #


def test_zugangsjournal_traegt_das_residuum_als_betrag():
    """MIG ist kein ZUG: Der Betrag ist die Veraenderung des Deckungskapitals."""
    erg = uebernehmen([_uebernahme(1, -850.0), _uebernahme(2, +420.0)])
    j = zugangsjournal(erg, STICHTAG, "KLV-1994")

    assert list(j.columns) == list(LEDGER_NAMES)
    assert set(j["ereignis"]) == {MIG}
    assert set(j["betrag_art"]) == {BETRAG_ART}
    assert sorted(j["betrag"]) == pytest.approx([-850.0, 420.0])
    assert set(j["vertragsjahr"]) == {TA_JAHR}


def test_journalzeilen_haben_die_dtypes_des_ledgers():
    """Sonst faellt der Zugang erst beim Schreiben auf."""
    from rechner_pipeline.models.bestand import LEDGER_SPALTEN

    j = zugangsjournal(uebernehmen([_uebernahme()]), STICHTAG, "KLV-1994")
    for name, dtype in LEDGER_SPALTEN:
        assert str(j[name].dtype) == dtype, name


def test_leeres_journal_behaelt_seine_form():
    """Auch ohne uebernommenen Vertrag ist das Ergebnis ein gueltiger Rahmen."""
    j = zugangsjournal([], STICHTAG, "KLV-1994")
    assert list(j.columns) == list(LEDGER_NAMES)
    assert len(j) == 0


# --------------------------------------------------------------------------- #
# 3. Was nicht getragen werden kann, wird nicht still uebernommen
# --------------------------------------------------------------------------- #


def test_nicht_verankerbarer_vertrag_traegt_einen_befund():
    """Ein Vertrag am Ablauftag hat keinen Amortisationsraum.

    Er wird NICHT ohne Schicht durchgewinkt — sonst waere sein Residuum
    still verschwunden.
    """
    letztes_jahr = KLV_DEFAULT.n
    e, = uebernehmen([
        Uebernahme(
            police_id=9, model_point=MP, monate_ta=12 * letztes_jahr,
            dk_ist=KERN.verlaufszeile(letztes_jahr).drx_bpfl - 500.0,
        )
    ])
    assert not e.getragen
    assert e.befund
    assert e.residuum == pytest.approx(-500.0)


def test_vertrag_mit_befund_kommt_nicht_ins_journal():
    """Was nicht verankert wurde, ist nicht uebernommen."""
    letztes_jahr = KLV_DEFAULT.n
    erg = uebernehmen([
        _uebernahme(1, -850.0),
        Uebernahme(police_id=2, model_point=MP, monate_ta=12 * letztes_jahr,
                   dk_ist=KERN.verlaufszeile(letztes_jahr).drx_bpfl - 500.0),
    ])
    j = zugangsjournal(erg, STICHTAG, "KLV-1994")
    assert list(j["police_id"]) == [1]
    bericht = zugangsbericht(erg)
    assert bericht["uebernommen"] == 1
    assert bericht["mit_befund"] == 1
    assert bericht["befunde"][0]["police_id"] == 2


def test_unterjaehriger_verankerungszeitpunkt_faellt_hart_aus():
    """Verankert wird am Rechenpunkt (9.12) — schon der Auftrag muss stimmen."""
    with pytest.raises(MigrationszugangFehler, match="kein Rechenpunkt"):
        Uebernahme(police_id=1, model_point=MP, monate_ta=TA + 5, dk_ist=1.0)


def test_doppelte_police_faellt_hart_aus():
    with pytest.raises(MigrationszugangFehler, match="doppelte police_id"):
        uebernehmen([_uebernahme(1), _uebernahme(1)])


def test_leere_uebernahme_ist_ein_aufruffehler():
    with pytest.raises(MigrationszugangFehler, match="leere Uebernahme"):
        uebernehmen([])


def test_verankerung_hinter_dem_vertragsende_faellt_hart_aus():
    with pytest.raises(MigrationszugangFehler, match="hinter dem Vertragsende"):
        uebernehmen([
            Uebernahme(police_id=1, model_point=MP,
                       monate_ta=12 * (KLV_DEFAULT.n + 1), dk_ist=1.0)
        ])


# --------------------------------------------------------------------------- #
# 4. Beleg
# --------------------------------------------------------------------------- #


def test_bericht_weist_verteilung_und_bilanzgroesse_getrennt_aus():
    """Die Summe der Residuen ist hier eine echte Bilanzgroesse.

    Anders als im aktuariellen Test, wo Summen verboten sind: Was die
    Korrekturschicht insgesamt traegt, gehoert in die Ueberleitung.
    """
    erg = uebernehmen([_uebernahme(1, -850.0), _uebernahme(2, +420.0)])
    b = zugangsbericht(erg)
    assert b["summe_residuum"] == pytest.approx(-430.0)
    assert b["max_abs_residuum"] == pytest.approx(850.0)
    assert b["vertraege"] == 2


def test_ergebnis_ist_als_beleg_serialisierbar():
    """Der Zugang muss in einen Fall geschrieben werden koennen."""
    import json

    e, = uebernehmen([_uebernahme()])
    beleg = e.als_beleg()
    json.dumps(beleg)  # wirft, wenn etwas nicht serialisierbar ist
    assert beleg["schicht"]["formfunktion"] == "proportional_zur_basis"
    assert beleg["schicht"]["kohorte"] == "t_a"


def test_fallback_kohorte_wird_durchgereicht():
    """9.12: Wer nur den Stand am Migrationsstichtag hat, ist eigene Kohorte."""
    e, = uebernehmen([_uebernahme(kohorte="t_0-fallback")])
    assert e.parameter.kohorte == "t_0-fallback"
