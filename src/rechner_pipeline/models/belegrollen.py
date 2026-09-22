"""Der Belegrollen-Vertrag: Pflichtbelegrollen je Gate und Scope (ADR-009).

Einmal definiert, ueberall lesbar — das ist der Zweck dieser Schicht.
Bis zum Entscheid des Maintainers vom 2026-09-22 (Befund T26-03, Weg 2)
wohnte der Vertrag in ``fall``, und die Schichtenkarte laesst
``betrieb -> fall`` nicht zu: Der Betriebseingang konnte die Rollenmenge
einer A-M4-Abnahme nicht pruefen, ein Snapshot mit einer einzigen
Pflichtrolle wurde uebernommen. ``fall`` beherbergte den Vertrag nur, es
nutzte ihn nie; hier lesen ihn Gate (``gates.gate_entscheid``) und
Betriebseingang (``betrieb.uebernahme``) gleichermassen — eine Definition,
beide koennen nicht auseinanderlaufen. Dasselbe Muster wie die
P-B1-Engine in ``bestand.vorbedingungen``.

``SCOPES`` spiegelt ``fall.FALL_SCOPES`` (``fall`` darf nichts importieren,
also auch nicht dies); eine Ratsche in den Tests haelt beide gleich.

Knoten: system/entscheid
"""

from __future__ import annotations

from typing import List

#: Die Scopes eines Falls — Spiegel von ``fall.FALL_SCOPES`` (Ratsche:
#: tests/test_belegrollen_und_zeichnung_t2603.py).
SCOPES = ("tarif", "bestand")


class BelegrollenFehler(ValueError):
    """Ein Gate ohne Vertrag oder ein Scope, den es nicht gibt."""


#: Pflichtbelegrollen JE GATE und Scope (ADR-009, fortgeschrieben durch
#: ADR-010 und ADR-012). Der aktuarielle Test besteht aus drei Abnahmen,
#: die dem Migrationscontrolling alle drei vorausgehen:
#:
#: * ``A-M1`` Stichtagstest, ``A-M2`` Verlaufstest, ``A-M3``
#:   Geschaeftsvorfalltest — jede pinnt im Bestands-Scope ihr eigenes
#:   Testergebnis und ihren eigenen Bericht. Im Tarif-Scope gibt es keine
#:   Vertragslieferung und damit keine eigenen Testartefakte; der Entscheid
#:   stuetzt sich dort auf die ohnehin gepinnten P-K1-Belege.
#: * ``A-M4`` traegt den geltenden ``A-M1``-Snapshot als Pflichtrolle.
#:   Das ist die erzwungene Reihenfolge: Ohne den Stichtagstest ist der
#:   Uebernahmestand nicht belegt, und eine finanzielle Abnahme des
#:   Gesamtbestands naehme etwas ab, dessen Grundlage offen ist.
#:
#: ``A-M2`` und ``A-M3`` sind im Bestands-Scope EBENFALLS
#: Pflichtbelege von ``A-M4`` (Entscheid des Aktuariats
#: 2026-08-31, gebaut mit den drei Abnahmen): Wer den
#: Gesamtbestand finanziell abnimmt, tut das auf Stichtags-,
#: Verlaufs- und Geschaeftsvorfallwerten — ein Bestand, dessen
#: Bewegungen ungeprueft sind, ist nicht abgenommen, sondern nur
#: zum Stichtag betrachtet.
#:
#: Die frueher hier vermerkte Gegenposition (A-M2/A-M3 bewusst
#: KEINE Pflichtbelege, damit eine Migration auf spaeter
#: gelieferten Verlaufsdaten nicht blockiert) ist damit
#: ueberholt; sie stand bis zum externen Review T19-05
#: unmittelbar neben dem Code, der das Gegenteil erzwingt. Wer
#: den Scope aendert, aendert BELEGROLLEN und diesen Absatz
#: gemeinsam.
BELEGROLLEN = {
    "A-M1": {
        "tarif": (),
        "bestand": ("aktuartest", "aktuartest_bericht"),
    },
    "A-M2": {
        "tarif": (),
        "bestand": ("aktuartest_am2", "aktuartest_am2_bericht"),
    },
    "A-M3": {
        "tarif": (),
        "bestand": ("aktuartest_am3", "aktuartest_am3_bericht"),
    },
    # A-O1 (T-Box-Aenderung, Review T22-02): der Beleg ist die
    # Aenderungsdatei abgeleitet/tbox/aenderung.json — alte und neue
    # Version, SHA-256 des T-Box-Moduls, Aenderungsartefakt. Scope-
    # unabhaengig, weil eine T-Box-Aenderung das Vokabular aller Faelle
    # betrifft.
    # Zweiter Pflichtbeleg seit dem Entscheid des Maintainers
    # 2026-09-16: die aktuarielle STELLUNGNAHME zur Wirksamkeit der
    # betroffenen Felder. Gezeichnet wird A-O1 von mensch/architektur —
    # wer verantwortet, welche Begriffe das Zielsystem fuehrt,
    # verantwortet sein Datenmodell. Ob ein Feld tarif- oder
    # bewertungswirksam ist und was verlorengeht, wenn es entfaellt, ist
    # aber eine fachliche Frage und gehoert dem Aktuariat. Dasselbe
    # Muster wie bei A-B1: Die Unterschrift gehoert einer Rolle, der
    # Beleg kommt aus einer anderen.
    "A-O1": {
        "tarif": ("tbox_aenderung", "stellungnahme_aktuariat"),
        "bestand": ("tbox_aenderung", "stellungnahme_aktuariat"),
    },
    # A-K2 (Kern-Aenderung, Entscheid des Maintainers 2026-09-16): ZWEI
    # Pflichtbelege, die verschiedene Dinge bezeugen. Der
    # Aenderungsbeleg sagt, WAS am Kern anders wurde (Versionsuebergang,
    # Sammelhash der eingefrorenen Referenzwerte, welche sich geaendert
    # haben, Begruendung). Der Regressionsbeleg sagt, was das fuer den
    # bestehenden Bestand bedeutet — jeder Vertrag mit altem und neuem
    # Kern durchgerechnet, Differenz JE VERTRAG.
    #
    # Die Regression ist Pflicht, nicht Kuer ("ohne das kann die
    # Aenderung im Rechenkern nicht abgenommen werden"). Solange es den
    # Produzenten nicht gibt, ist A-K2 damit nicht zeichenbar — das ist
    # gewollt. Ein optionaler Beleg waere derselbe Fehler, den A-M4 im
    # Bestands-Scope schon einmal gemacht hat (T21-02/T22-01:
    # "ausweisen statt erzwingen" nahm jedes Teilprofil an).
    #
    # Scope-unabhaengig: Ein geaenderter Kern rechnet in jedem Scope.
    "A-K2": {
        "tarif": ("kernaenderung", "regression"),
        "bestand": ("kernaenderung", "regression"),
    },
    # A-B1 (Auslieferung, Entscheid des Maintainers 2026-09-16): Der
    # Beleg ist der ANKERSATZ des auszuliefernden Pakets — der Satz, der
    # ausserhalb des Pakets liegt und es bindet. Er ist der einzige
    # Pflichtbeleg, und das ist kein Mangel: Was fachlich abgenommen ist,
    # steht bereits gezeichnet IM Paket (A-M1 bis A-M4). Die Auslieferung
    # zeichnet nicht die Zahlen, sondern den Akt: dieser Stand geht nach
    # aussen.
    #
    # Nur im Bestands-Scope. Ein Tarif-Fall liefert keinen Bestand aus.
    "A-B1": {
        "tarif": (),
        "bestand": ("anker",),
    },
    "A-M4": {
        "tarif": ("pq3_ledger", "aq1_snapshot", "am1_snapshot", "pk1_belege"),
        "bestand": (
            "pq3_ledger",
            "aq1_snapshot",
            "am1_snapshot",
            "am2_snapshot",
            "am3_snapshot",
            "pk1_belege",
            "pb1_ledger",
            "migrationssuite",
            # Freischaltung (Schritt 6): der Beleg, dass die Fuehrung die
            # abgenommene Welt traegt — ohne ihn zeichnet A-M4 eine Fiktion.
            "fuehrungsprobe",
            "abnahmebericht",
        ),
    },
}


def belegrollen(gate: str, scope: str) -> List[str]:
    """Stabile Pflichtbelegrollen je Gate fuer den ausdruecklichen Scope."""
    if gate not in BELEGROLLEN:
        raise BelegrollenFehler(
            f"kein Belegrollen-Vertrag fuer Gate {gate!r} "
            f"(deklariert: {sorted(BELEGROLLEN)})"
        )
    if scope not in SCOPES:
        raise BelegrollenFehler(
            f"Scope {scope!r} ist ungueltig — erlaubt: {', '.join(SCOPES)}"
        )
    return list(BELEGROLLEN[gate][scope])


def am4_belegrollen(scope: str) -> List[str]:
    """Stabile A-M4-Pflichtbelegrollen (Kurzform von ``belegrollen``)."""
    return belegrollen("A-M4", scope)
