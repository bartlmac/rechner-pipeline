"""Der Vertrag der Kernabnahme A-K2 — Gegenstand, Belegorte, Ausnahme.

Entscheid des Maintainers 2026-10-01 (ADR-018, Nachtrag 2026-10-01):
``A-K2.kernaenderung`` nimmt den KERNSTAND ab, auf dem ein Fall rechnet —
einschliesslich der Aenderungen, die ausserhalb eines Falls entstanden
sind (wie A-M4 ihn verlangt, regelt ``models.standabnahme``). Zwei
Pruefungen: (1) die qualitative Pruefung der Aenderungen am
Rechenkern entlang seiner Module, mit den Commits des Zweigs; (2) das
Ergebnis der Regression. Die Regression ist noch nicht gebaut; bis dahin
steht sie als benannte AUSNAHME im Beleg, nie als Ergebnis.

Hier steht, was mehrere Schichten lesen: der Produzent
(``gates.kernstand_belegen``), das Gate (``gates.gate_entscheid``: A-K2
und die Vorbedingung von A-M4) und die Darstellung (``werkzeuge/``). Die
Schichtenkarte laesst ``gates -> betrieb`` und umgekehrt nicht zu; der
Vertrag wohnt deshalb in ``models`` wie Belegrollen und Zugangsprobe.

Knoten: system/entscheid
"""

from __future__ import annotations

from typing import Optional, Tuple

#: Die Belegorte im Fall (relativ zur Fallwurzel). Fest wie bei A-O1 und
#: A-B2: Ein Beleg, der dorthin zeigen kann, wo es gerade passt, bindet
#: nichts.
AENDERUNG_RELATIV = "abgeleitet/kern/aenderung.json"
REGRESSION_RELATIV = "abgeleitet/kern/regression.json"
#: Die lesbare Sicht fuer den Pruefer — aus dem Aenderungsbeleg erzeugt,
#: nie umgekehrt; das Gate liest sie nicht.
SICHT_RELATIV = "abgeleitet/kern/aenderung.md"

#: Das Rechenkern-Paket (Code des Kerns, einschliesslich der
#: Rechnungsgrundlagen ``tafeln.xml``).
KERN_PAKET = "src/rechner_pipeline/kern"
#: Die eingefrorenen Referenzwerte des Kerns (Abnahme-Protokoll Nr. 1 in
#: ``kern/__init__``) — die Charakterisierung dessen, was der Kern rechnet.
KERN_REFERENZWERTE = "tests/fixtures/kern_referenzwerte"

#: DER GEGENSTAND VON A-K2 — "Code und Dokumentation des Rechenkerns"
#: (ADR-012, ADR-018), als Pfadmenge EINMAL bestimmt. Je Eintrag: Pfad
#: (relativ zur Repo-Wurzel), Gliederung der Sicht und Begruendung.
#:
#: Gliederung ``je_eintrag``: jeder direkte Eintrag darunter (Datei oder
#: Unterpaket) ist ein Modul der Sicht; ``gesamt``: der Pfad ist ein Modul.
#:
#: Bewusst NICHT im Gegenstand:
#:
#: * ``kommutationskern`` — der Zweitkern ist seit ADR-013 kein Teil des
#:   Kerns, sondern ein unabhaengiger Zeuge der algebraischen Tests.
#: * ``spez/`` und die Tarif-Spez eines Falls — Parametrierung (ADR-006),
#:   abgenommen von P-K1 und A-M4, nicht von A-K2.
#: * ``bestand/``, ``betrieb/``, ``gates/`` — sie benutzen den Kern, sie
#:   sind es nicht; ihre Aenderungen nimmt die Suite und der Fall ab.
#: * die uebrigen Tests — sie sind Mittel der Regression, nicht ihr
#:   Gegenstand; ``plv/mathematik/README.md`` — ein Verzeichnis der
#:   Dokumente, keine Beschreibung des Kerns.
#: * ``plv/tarifplaene`` — seit ADR-025 Teil des TARIFWERKS
#:   (``models.tarifwerkabnahme``, A-T1, ``mensch/aktuariat``): Was die PLV
#:   ihren Kunden verspricht, verantwortet das Aktuariat, nicht die
#:   Rechenkern-Verantwortung; vorher zeichnete A-K2 die Tarifplaene mit.
KERNSTAND: Tuple[Tuple[str, str, str], ...] = (
    (KERN_PAKET, "je_eintrag",
     "Code des Rechenkerns: was der Kern rechnet und wie (Thiele-Rueckgrat, "
     "Produkte, Rechnungsgrundlagen)"),
    (KERN_REFERENZWERTE, "gesamt",
     "eingefrorene Referenzwerte: der Massstab, an dem eine Aenderung des "
     "Kerns sichtbar wird; wer sie verschiebt, verschiebt den Massstab"),
    ("plv/mathematik/grundsatzdokumentation.md", "gesamt",
     "Grundsatzdokumentation: die normative Mathematik, der die "
     "Implementierung folgt"),
)


def kernstand_pfade() -> Tuple[str, ...]:
    """Die Pfade des Gegenstands, in der Reihenfolge von :data:`KERNSTAND`."""
    return tuple(pfad for pfad, _, _ in KERNSTAND)


def kernmodul(pfad: str) -> Optional[str]:
    """Das Modul der Sicht, zu dem ein Repo-Pfad gehoert (None = keins).

    Die eine Zuordnung fuer Diffstat, Commits und nicht committete
    Aenderungen — drei Quellen, ein Schluessel.
    """
    for wurzel, gliederung, _ in KERNSTAND:
        if pfad == wurzel:
            return wurzel
        if pfad.startswith(wurzel + "/"):
            if gliederung == "gesamt":
                return wurzel
            return wurzel + "/" + pfad[len(wurzel) + 1:].split("/", 1)[0]
    return None


#: Der Zustand eines Regressionsbelegs, der KEIN Ergebnis ist.
ZUSTAND_NICHT_GEFAHREN = "nicht_gefahren"
#: Der Grund, woertlich (Entscheid des Maintainers 2026-10-01).
GRUND_NICHT_GEFAHREN = "Werkzeug noch nicht erstellt"
#: Wie Snapshot und Ledger die Ausnahme fuehren (Feld ``ausnahmen``).
AUSNAHME_REGRESSION = "Ausnahme — nicht gefahren, " + GRUND_NICHT_GEFAHREN
#: Wie jede Anzeige sie fuehrt — woertlich, mit dem Gegenstand davor.
ANZEIGE_REGRESSION = "Regression: " + AUSNAHME_REGRESSION
#: Was die Zeichnung von A-K2 unter der Ausnahme deckt.
DECKUNG_UNTER_AUSNAHME = (
    "Die Zeichnung deckt nur die qualitative Pruefung der Aenderungen am "
    "Kernstand; die Regression ist nicht gefahren.")
#: Die Fundstelle der Ausnahme im Beleg selbst.
AUSNAHME_GRUNDLAGE = "ADR-018, Nachtrag 2026-10-01"

#: DIE Konstante (ADR-018, Nachtrag 2026-10-01): Solange sie ``True`` ist,
#: nimmt A-K2 einen Regressionsbeleg mit Zustand ``nicht_gefahren`` an —
#: genau diesen, mit genau diesem Grund, und nichts anderes
#: Unvollstaendiges. Sie kippt, sobald der Regressionsproduzent gebaut ist
#: (dev-docs/offene-punkte.md); zwei Waechter in
#: ``tests/test_kernabnahme_ak2.py`` halten beides zusammen — die Konstante
#: kippt nicht ohne Produzenten, und ein Produzent laesst die Ausnahme
#: nicht stehen.
#:
#: Verworfen (Entscheid 2026-10-01): "ohne Regression keine Abnahme" (der
#: Entscheid vom 16.09.) — dann gibt es das Gate weiter nicht, waehrend der
#: Kern sich aendert; und "der Platzhalter als bestanden" — ein gezeichneter
#: Beleg darf nichts behaupten, was niemand gefahren hat.
REGRESSION_AUSNAHME_ERLAUBT = True

#: Die Felder des Ausnahmebelegs, abschliessend. Ein Feld mehr (etwa ein
#: ``vertraege_geprueft`` mit Nullen) saehe wie ein Ergebnis aus.
AUSNAHME_FELDER = frozenset({
    "schema_version", "zustand", "grund", "grundlage",
    "von_version", "nach_version", "kern_alt_sha256", "kern_sha256",
})
#: Die Felder, die den Ausnahmebeleg an den Uebergang des Aenderungsbelegs
#: binden.
BINDUNGSFELDER = ("von_version", "nach_version", "kern_alt_sha256", "kern_sha256")


def ist_ausnahme(regression: object) -> bool:
    """Ob ein Regressionsbeleg die Ausnahme ist (und kein Ergebnis)."""
    return isinstance(regression, dict) and regression.get("zustand") == ZUSTAND_NICHT_GEFAHREN


def ausnahmen_fuer(regression: object) -> dict:
    """Das Feld ``ausnahmen`` des A-K2-Snapshots, aus dem Regressionsbeleg.

    Leer, wenn der Beleg ein Ergebnis ist. Eine Ableitung, keine Angabe:
    Gate und Leser rechnen sie aus demselben Beleg.
    """
    return {"regression": AUSNAHME_REGRESSION} if ist_ausnahme(regression) else {}
