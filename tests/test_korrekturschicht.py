"""Korrekturschicht des Migrationszugangs (Grundsatzdokumentation Abschnitt 9).

Die Tests pruefen die Behauptungen des Abschnitts, nicht die Implementierung:

* Die Kollapsform ist die vorhandene Thiele-Rekursion mit weggelassenen
  wertkontinuierlichen Uebergaengen (9.6) — gegen eine unabhaengige
  Handformel gerechnet.
* Der Verankerungsoperator trifft das Residuum exakt (9.8).
* Optionsunabhaengigkeit: Storno und Beitragsfreistellung koennen rho
  nicht beeinflussen (9.8) — mit Gegenprobe, dass die Messung ueberhaupt
  etwas messen kann.
* Die Guardrails greifen ueber den ganzen Pfad, nicht nur am
  Verankerungspunkt (9.10).

Knoten: klv
"""

from __future__ import annotations

import math

import pytest

from rechner_pipeline.kern import KLV_DEFAULT
from rechner_pipeline.kern.korrekturschicht import (
    SCHICHT_CONV,
    Degeneration,
    KeinAmortisationsraum,
    FloorVerletzung,
    Formfunktion,
    Korrekturschicht,
    KorrekturschichtFehler,
    Schichtparameter,
    form_konstantes_fenster,
    form_proportional_zur_basis,
    vererbende_dynamik,
)
from rechner_pipeline.kern.rechenkern import Rechenkern
from rechner_pipeline.kern.zustandsmodell import Zustandsmodell

QX = 0.01
ZINS = 0.0175
AKTIV, TOT, STORNIERT = "aktiv", "tot", "storniert"


def _modell(storno: float = 0.0) -> Zustandsmodell:
    """Zweizustandsmodell wie KLV, wahlweise mit Storno als drittem Zustand."""
    zustaende = (AKTIV, TOT) if storno == 0.0 else (AKTIV, TOT, STORNIERT)

    def uebergang(von: str, nach: str, alter: int, dauer: int) -> float:
        if (von, nach) == (AKTIV, TOT):
            return QX
        if (von, nach) == (AKTIV, STORNIERT):
            return storno
        return 0.0

    return Zustandsmodell(zustaende, ZINS, uebergang)


def _schicht(storno: float = 0.0) -> Korrekturschicht:
    """Nur der Tod ist vererbend: die Leistung ist Anker (9.7, Klasse B)."""
    return Korrekturschicht(_modell(storno), ((AKTIV, TOT),))


# --------------------------------------------------------------------------- #
# 1. Die Kollapsform ist die vorhandene Rekursion
# --------------------------------------------------------------------------- #


def test_pi_stimmt_mit_der_geschlossenen_handformel():
    """Gegenrechnung ohne die Engine.

    Fuer eine vorschuessige Einheitszahlung ueber n Jahre auf dem
    Zweizustandsmodell ist der Barwert die geometrische Reihe
    ``sum (v (1-qx))^j`` — 9.8 sagt ausdruecklich, dass keine geschlossene
    Form noetig ist, aber hier gibt es eine, und sie ist das Orakel.
    """
    n = 10
    pi = _schicht().pi(form_konstantes_fenster(n, n), 45, AKTIV)
    v = 1.0 / (1.0 + ZINS)
    hand = sum((v * (1.0 - QX)) ** j for j in range(n))
    assert pi == pytest.approx(hand, rel=1e-14)


def test_wertkontinuierliche_uebergaenge_fallen_aus_der_dynamik():
    """Die reduzierte Uebergangsfunktion laesst nur vererbende Ursachen durch."""
    roh = _modell(storno=0.08).uebergang
    reduziert = vererbende_dynamik(roh, ((AKTIV, TOT),))
    assert reduziert(AKTIV, TOT, 45, 0) == QX
    assert roh(AKTIV, STORNIERT, 45, 0) == 0.08
    assert reduziert(AKTIV, STORNIERT, 45, 0) == 0.0


# --------------------------------------------------------------------------- #
# 2. Der Verankerungsoperator
# --------------------------------------------------------------------------- #


@pytest.mark.parametrize("R", [-1234.56, -1.0, 1.0, 5000.0])
def test_verankerung_trifft_das_residuum_exakt(R: float):
    """rho * Pi == R, weil die Rekursion linear in der Zahlung ist (9.8).

    Das ist der Selbsttest, der ohne Zusatzaufwand mitlaeuft: Der
    Schichtwert AM Verankerungspunkt IST das Residuum.
    """
    s = _schicht()
    form = form_konstantes_fenster(10, 10)
    p = s.verankere(form, 45, AKTIV, R)
    assert s.verlauf(p, form, 45)[0] == pytest.approx(R, rel=1e-12)


def test_terminalbedingung_ist_null():
    """V_korr(T) = 0 — nicht verhandelbar (9.7), sonst waere die
    Ablaufleistung ungleich dem Deckungskapital."""
    s = _schicht()
    form = form_konstantes_fenster(10, 10)
    p = s.verankere(form, 45, AKTIV, -500.0)
    assert s.verlauf(p, form, 45)[-1] == 0.0


def test_residuum_null_ergibt_eine_leere_schicht():
    """Klasse-A-Geschaeftsvorfall: nach der Absorption ist rho null (9.8)."""
    s = _schicht()
    form = form_konstantes_fenster(10, 10)
    p = s.verankere(form, 45, AKTIV, 0.0)
    assert p.rho == 0.0
    assert all(w == 0.0 for w in s.verlauf(p, form, 45))


# --------------------------------------------------------------------------- #
# 3. Optionsunabhaengigkeit (9.8)
# --------------------------------------------------------------------------- #


@pytest.mark.parametrize("storno", [0.02, 0.08, 0.25])
def test_stornoannahmen_beeinflussen_rho_nicht(storno: float):
    """Der Kern der Methode: Storno ist wertkontinuierlich, also unsichtbar.

    "Stornoannahmen spielen in der Migrationsbewertung keine Rolle"
    (9.8) — hier ist es keine Behauptung, sondern eine Eigenschaft der
    Konstruktion.
    """
    form = form_konstantes_fenster(10, 10)
    ohne = _schicht().verankere(form, 45, AKTIV, -1000.0)
    mit = _schicht(storno).verankere(form, 45, AKTIV, -1000.0)
    assert mit.rho == pytest.approx(ohne.rho, rel=1e-14)


def test_gegenprobe_vererbender_storno_wuerde_sehr_wohl_wirken():
    """Ohne diesen Test misst der vorige moeglicherweise gar nichts.

    Wird derselbe Uebergang faelschlich als vererbend gefuehrt, aendert
    sich Pi deutlich — die Messung ist also empfindlich.
    """
    form = form_konstantes_fenster(10, 10)
    falsch = Korrekturschicht(_modell(0.08), ((AKTIV, TOT), (AKTIV, STORNIERT)))
    richtig = _schicht(0.08)
    assert falsch.pi(form, 45, AKTIV) < richtig.pi(form, 45, AKTIV) - 1.0


def test_biometrie_wirkt_sehr_wohl():
    """Die vererbende Sterblichkeit finanziert die Amortisation mit (9.7)."""
    form = form_konstantes_fenster(10, 10)

    def modell_mit(qx: float) -> Zustandsmodell:
        return Zustandsmodell(
            (AKTIV, TOT), ZINS,
            lambda v, n, a, d: qx if (v, n) == (AKTIV, TOT) else 0.0,
        )

    hoch = Korrekturschicht(modell_mit(0.05), ((AKTIV, TOT),))
    niedrig = Korrekturschicht(modell_mit(0.001), ((AKTIV, TOT),))
    assert hoch.pi(form, 45, AKTIV) < niedrig.pi(form, 45, AKTIV)


# --------------------------------------------------------------------------- #
# 4. Guardrails (9.10)
# --------------------------------------------------------------------------- #


@pytest.mark.parametrize("jahre", [20, 10, 5, 3, 2, 1])
def test_kurze_restlaufzeit_rechnet_korrekt_ohne_jede_grenze(jahre: int):
    """Es gibt keine eingebaute Schwelle — und es braucht auch keine.

    Ein frueherer Entwurf lehnte kurze Restlaufzeiten ab, weil "rho
    explodiert". Das traegt nicht: rho ist ein Zwischenwert und waechst
    zwar, wird aber mit einer im selben Mass kleineren Formfunktion
    multipliziert. Der Schichtwert bleibt exakt das Residuum, der
    Terminalwert exakt null — bei JEDER Restlaufzeit.
    """
    s = _schicht()
    form = form_konstantes_fenster(jahre, jahre)
    R = -850.0
    p = s.verankere(form, 45, AKTIV, R)
    v = s.verlauf(p, form, 45)
    assert v[0] == pytest.approx(R, rel=1e-12)
    assert v[-1] == 0.0


def test_ohne_amortisationsraum_faellt_es_hart_aus():
    """Der einzige zwingende Grenzfall: Pi = 0, also Division durch null.

    Er entsteht nicht aus kurzer Restlaufzeit, sondern daraus, dass ueber
    den erlebten Zeitraum gar kein Einheitsstrom laeuft.
    """
    s = _schicht()
    # Sterblichkeit 1: nach dem ersten Jahr lebt niemand mehr, und die Form
    # zahlt erst danach.
    tot_sofort = Zustandsmodell(
        (AKTIV, TOT), ZINS,
        lambda v, n, a, d: 1.0 if (v, n) == (AKTIV, TOT) else 0.0,
    )
    schicht = Korrekturschicht(tot_sofort, ((AKTIV, TOT),))
    spaet = Formfunktion(kennung="erst_spaeter", werte=(0.0, 0.0, 1.0))
    with pytest.raises(KeinAmortisationsraum, match="keinen Einheitsstrom"):
        schicht.verankere(spaet, 45, AKTIV, -1000.0)


def test_ausbuchungsgrenze_ist_eine_entscheidung_des_aufrufers():
    """Wer kurze Laufzeiten ausbuchen WILL, sagt es — die Methode nicht.

    Ohne Grenze rechnet derselbe Fall durch. Das ist der Unterschied
    zwischen einer Bilanzentscheidung und einer Eigenschaft der Methode.
    """
    s = _schicht()
    form = form_konstantes_fenster(2, 2)
    pi = s.pi(form, 45, AKTIV)

    ohne = s.verlauf(s.verankere(form, 45, AKTIV, -850.0), form, 45)
    assert ohne[0] == pytest.approx(-850.0, rel=1e-12)

    with pytest.raises(Degeneration, match="Ausbuchungsgrenze"):
        s.verankere(form, 45, AKTIV, -850.0, ausbuchungsgrenze=pi + 1.0)


def test_floor_wird_ueber_den_ganzen_pfad_geprueft():
    """9.10 verlangt ausdruecklich ALLE Zeitpunkte, nicht nur t_a.

    Der Fall ist so gebaut, dass er am Verankerungspunkt bestehen wuerde
    und erst spaeter unter den Floor taucht — genau die Luecke, die eine
    Pruefung nur am Anker offenliesse.
    """
    s = _schicht()
    n = 10
    form = form_konstantes_fenster(n, n)
    p = s.verankere(form, 45, AKTIV, -300.0)
    basis = [1000.0] * (n + 1)

    nur_am_anker = [0.0] * (n + 1)
    nur_am_anker[5] = 999.0  # ab hier reisst Basis+Korrektur den Floor
    with pytest.raises(FloorVerletzung) as exc:
        s.pruefe_floor(p, form, 45, basis, nur_am_anker)
    assert exc.value.jahr == 5

    # Ohne den scharfen Mindestwert ist derselbe Pfad zulaessig.
    s.pruefe_floor(p, form, 45, basis, [0.0] * (n + 1))


def test_positives_residuum_verletzt_keinen_floor():
    """R > 0 ist aufsichtsrechtlich unkritisch (9.10)."""
    s = _schicht()
    form = form_konstantes_fenster(10, 10)
    p = s.verankere(form, 45, AKTIV, +500.0)
    s.pruefe_floor(p, form, 45, [1000.0] * 11, [900.0] * 11)


# --------------------------------------------------------------------------- #
# 5. Formfunktion und Parameter
# --------------------------------------------------------------------------- #


def test_formfunktion_weist_unbrauchbare_stroeme_zurueck():
    with pytest.raises(KorrekturschichtFehler, match="leerer Einheitsstrom"):
        Formfunktion(kennung="leer", werte=())
    with pytest.raises(KorrekturschichtFehler, match="negativ"):
        Formfunktion(kennung="neg", werte=(1.0, -1.0))
    with pytest.raises(KorrekturschichtFehler, match="durchweg null"):
        Formfunktion(kennung="null", werte=(0.0, 0.0))
    with pytest.raises(KorrekturschichtFehler, match="ist nan"):
        Formfunktion(kennung="nan", werte=(float("nan"),))


def test_basisproportionale_form_klemmt_negative_basiswerte():
    """Ein Residuum auf einem negativen Basiswert zu verteilen ergibt nichts."""
    form = form_proportional_zur_basis([-500.0, 0.0, 1000.0, 2000.0])
    assert form.werte == (0.0, 0.0, 1000.0, 2000.0)


def test_unbekannter_vererbender_uebergang_faellt_hart_aus():
    with pytest.raises(KorrekturschichtFehler, match="ausserhalb des Zustandsraums"):
        Korrekturschicht(_modell(), ((AKTIV, "erfunden"),))


def test_parameter_tragen_den_beleg_ohne_zwischenwerte():
    """9.11: persistiert werden Parameter, nie Zwischenwerte."""
    s = _schicht()
    form = form_konstantes_fenster(10, 6)
    p = s.verankere(form, 45, AKTIV, -800.0, schichttyp=SCHICHT_CONV,
                    kohorte="t_0-fallback", in_zzr=False)
    beleg = p.als_beleg()
    assert beleg["schichttyp"] == SCHICHT_CONV
    assert beleg["kohorte"] == "t_0-fallback"
    assert beleg["in_zzr"] is False
    assert beleg["formparameter"] == {"fenster": 6}
    assert beleg["vererbend"] == [[AKTIV, TOT]]
    # Kein Wertevektor im Beleg — die Schicht ist aus den Parametern
    # reproduzierbar, nicht aus gespeicherten Zwischenstaenden.
    assert not any(isinstance(v, list) and len(v) > 5 for v in beleg.values())


def test_unbekannter_schichttyp_faellt_hart_aus():
    with pytest.raises(KorrekturschichtFehler, match="unbekannter Schichttyp"):
        Schichtparameter(
            schichttyp="erfunden", verankerungszustand=AKTIV,
            verweildauer=0, rho=1.0, formfunktion="x",
        )


# --------------------------------------------------------------------------- #
# 6. Am echten KLV-Kern
# --------------------------------------------------------------------------- #


def test_verankerung_am_echten_klv_vertrag():
    """Der Migrationszugang auf dem produktiven Rechenkern.

    Ein uebernommener Vertrag bringt einen Ist-Wert unter dem prospektiven
    mit (ungetilgter Abschlusskostenanteil). Die Schicht traegt die
    Differenz und baut sie ueber die Restlaufzeit ab.
    """
    kern = Rechenkern(KLV_DEFAULT)
    mp = KLV_DEFAULT
    ta = 9
    basis = [kern.verlaufszeile(a).drx_bpfl for a in range(ta, mp.n + 1)]
    residuum = -850.0

    bw = kern.produkt.bw
    schicht = Korrekturschicht(bw.modell, ((bw.AKTIV, bw.TOT),))
    form = form_proportional_zur_basis(basis)
    p = schicht.verankere(form, mp.x + ta, bw.AKTIV, residuum)
    korr = schicht.verlauf(p, form, mp.x + ta)

    assert korr[0] == pytest.approx(residuum, rel=1e-12)
    assert korr[-1] == 0.0
    # Der Betrag baut sich monoton ab — kein Wiederanwachsen.
    betraege = [abs(w) for w in korr]
    assert all(a >= b - 1e-9 for a, b in zip(betraege, betraege[1:]))
    # Und die Gesamtreserve liegt unter der prospektiven, wie es ein
    # negatives Residuum verlangt.
    assert basis[0] + korr[0] < basis[0]
