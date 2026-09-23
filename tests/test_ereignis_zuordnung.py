"""Jeder Geschaeftsvorfall ist Zugang, Leistung oder benannte Ausnahme.

Die Zuordnung ist fachlich (Maintainer, 2026-09-17) und wird von zwei
Seiten gebraucht: Der Tagesbetrieb zaehlt damit die Monatskennzahlen, die
Unternehmensseite zeichnet damit ihre Bewegungsreihen. Genau daraus
entsteht die Gefahr, die dieser Test abdeckt — dieselbe fachliche Menge
an zwei Orten gepflegt.

Diese Klasse hat im Repo mehrfach zugeschlagen: A-B1 war funktional tot,
weil dieselbe Gate-Menge an sechs Stellen stand und an einer fehlte; die
Bewegungsrechnung laesst RED aus, waehrend die Einzelbewertung es kennt
(externer Befund T26-11). Ein neuer GeVo-Code muss deshalb eingeordnet
oder ausdruecklich als Ausnahme benannt werden — stillschweigend
herausfallen kann er nicht.

Knoten: klv, bu
"""

from __future__ import annotations

from rechner_pipeline.models.bestand import (
    EREIGNIS_VALUES,
    LEISTUNG_EREIGNISSE,
    WEDER_ZUGANG_NOCH_LEISTUNG,
    ZUGANG_EREIGNISSE,
)


def test_jeder_gevo_ist_eingeordnet():
    """Die drei Mengen decken EREIGNIS_VALUES vollstaendig ab.

    Wer einen Code ergaenzt, ohne ihn einzuordnen, faellt hier auf und
    nicht erst an einer Kennzahl, die ihn nicht mitzaehlt.
    """
    eingeordnet = (set(ZUGANG_EREIGNISSE) | set(LEISTUNG_EREIGNISSE)
                   | set(WEDER_ZUGANG_NOCH_LEISTUNG))
    assert eingeordnet == set(EREIGNIS_VALUES), (
        f"nicht eingeordnet: {sorted(set(EREIGNIS_VALUES) - eingeordnet)}; "
        f"unbekannt: {sorted(eingeordnet - set(EREIGNIS_VALUES))}")


def test_die_mengen_ueberschneiden_sich_nicht():
    """Ein GeVo ist nicht zugleich Zugang und Leistung."""
    assert not set(ZUGANG_EREIGNISSE) & set(LEISTUNG_EREIGNISSE)
    assert not set(ZUGANG_EREIGNISSE) & set(WEDER_ZUGANG_NOCH_LEISTUNG)
    assert not set(LEISTUNG_EREIGNISSE) & set(WEDER_ZUGANG_NOCH_LEISTUNG)


def test_jede_ausnahme_traegt_einen_grund():
    """Positivkontrolle der Ausnahmeliste: Ein leerer Grund waere eine
    Ausnahme, die sich als begruendet ausgibt."""
    for code, grund in WEDER_ZUGANG_NOCH_LEISTUNG.items():
        assert code in EREIGNIS_VALUES, code
        assert isinstance(grund, str) and len(grund.strip()) > 20, code


def test_keine_der_mengen_ist_leer():
    """Eine leere Menge waere ein Detektor ohne Sehvermoegen: Zaehler
    ueber ihr blieben stumm null, und das saehe aus wie 'nichts
    geschehen'."""
    assert ZUGANG_EREIGNISSE
    assert LEISTUNG_EREIGNISSE
    assert WEDER_ZUGANG_NOCH_LEISTUNG
