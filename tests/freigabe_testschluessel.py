"""Die Testschluessel der Freigabesignatur — Nahte, keine Geheimnisse.

Seit die Zeichnungsschicht im Betriebseingang zu Ende gebaut ist (T26-03,
2026-09-22), prueft ``eingang_anlegen`` die Freigabesignatur eines A-M4-
Snapshots; ``conftest`` reicht den Ring an den Betriebseingang —
deterministisch, ohne dass eine der vielen Registrierungsstellen in den
Tests einen Ring tragen muss.

Getrennte Schluessel je Rolle, wie produktiv (Entscheid des Maintainers
2026-10-01): Der Betrieb haelt jede Abnahme, auf der ein Zugang steht,
gegen seine Zeichnungsordnung — Rolle aus dem Schluessel, Gate erlaubt,
Rollenfeld gleich der Rolle des Schluessels. Ein Schluessel, der in der
Suite A-M1, A-M4 UND A-B2 zeichnete, verdeckte genau den Fall, den diese
Regel prueft. Deshalb:

* :data:`TESTKEY` — ``mensch/aktuariat`` (Verantwortlicher Aktuar, ADR-018),
  zeichnet die aktuariellen Abnahmen und die Migrationsabnahme
  (``test_betrieb_uebernahme.am4_snapshot``/``am1_snapshot``);
* :data:`BETRIEB_FREIGABEKEY` — ``mensch/betrieb``, zeichnet die
  Zugangsabnahme A-B2 (``zugangsabnahme_testhelfer``).

Die Ratsche ``test_abnahme_rolle_klasse`` haelt, dass keine Test-Ordnung
des Betriebs einer Rolle beide Seiten gibt.
"""

from __future__ import annotations

import hashlib

TESTKEY: bytes = hashlib.sha256(b"rechner-pipeline: testschluessel der freigabe").digest()
BETRIEB_FREIGABEKEY: bytes = hashlib.sha256(
    b"rechner-pipeline: freigabeschluessel mensch/betrieb").digest()
TESTRING: dict = {hashlib.sha256(k).hexdigest(): k for k in (TESTKEY, BETRIEB_FREIGABEKEY)}
FREMDER_SCHLUESSEL: bytes = hashlib.sha256(b"ein anderer schluessel").digest()

#: Der Test-Betriebsschluessel (Rolle ``betrieb/tageslauf``, Klasse
#: ``betrieb``; ADR-018, Nachtrag 2026-09-30). ``conftest`` legt ihn als
#: Datei 0600 in ein Session-Verzeichnis AUSSERHALB jeder Ablage und setzt
#: die Naht ``tageslauf._STANDARD_BETRIEBSZEICHNUNG`` — damit die vielen
#: ``tageslauf()``-Aufrufe der Suite unveraendert laufen und trotzdem jede
#: Zeile gezeichnet und geprueft wird.
BETRIEBSKEY: bytes = hashlib.sha256(b"rechner-pipeline: testschluessel des betriebs").digest()
BETRIEBSROLLE = "betrieb/tageslauf"

#: Die Rolle des :data:`TESTKEY` und ihre Gates (ADR-018: der
#: Verantwortliche Aktuar zeichnet die aktuariellen Abnahmen und A-M4).
AKTUARIAT_ROLLE = "mensch/aktuariat"
AKTUARIAT_GATES = ["A-M1", "A-M2", "A-M3", "A-M4"]

#: Die Rolle des :data:`BETRIEB_FREIGABEKEY`: Sie zeichnet die
#: Zugangsabnahme A-B2 (ADR-022). Die Registrierung haelt den Fingerabdruck
#: der Freigabe gegen eine Rolle mit A-B2 in dieser Ordnung (Block F,
#: Nachbesserung, Pruefer-Befund 9).
AB2_ROLLE = "mensch/betrieb"
#: A-B3 (Abnahme des Anfangsbestands, ADR-025) zeichnet dieselbe Rolle mit
#: demselben Schluessel — getrennt wird je Rolle, nicht je Gate.
AB2_GATES = ["A-B2", "A-B3"]


def freigaberollen() -> dict:
    """Die beiden zeichnenden Rollen der Test-Ordnungen des Betriebs — EINE
    Quelle fuer jede Ordnung, die die Suite dem Betrieb gibt."""
    return {
        AKTUARIAT_ROLLE: {"schluessel_sha256": hashlib.sha256(TESTKEY).hexdigest(),
                          "schluesselklasse": "mensch", "gates": list(AKTUARIAT_GATES)},
        AB2_ROLLE: {"schluessel_sha256": hashlib.sha256(BETRIEB_FREIGABEKEY).hexdigest(),
                    "schluesselklasse": "mensch", "gates": list(AB2_GATES)},
    }


def betriebsordnung(weitere: "dict | None" = None) -> dict:
    """Die Test-Zeichnungsordnung (Schema 2) mit der Betriebsrolle und den
    beiden zeichnenden Rollen (:func:`freigaberollen`)."""
    rollen = {BETRIEBSROLLE: {
        "schluessel_sha256": hashlib.sha256(BETRIEBSKEY).hexdigest(),
        "schluesselklasse": "betrieb", "gates": []}}
    rollen.update(freigaberollen())
    rollen.update(weitere or {})
    return {"schema_version": 2, "rollen": rollen}


def betriebsargs(flag: str = "--schluessel") -> list:
    """``<flag> <schluessel> --zeichnungsordnung <ordnung>`` fuer die
    Kommandos des Betriebs — der Test-Betriebsschluessel der Session."""
    from rechner_pipeline.betrieb import tageslauf as tl

    schluessel, ordnung = tl._STANDARD_BETRIEBSZEICHNUNG
    return [flag, str(schluessel), "--zeichnungsordnung", str(ordnung)]


def zeichne_neu(zeile: dict) -> dict:
    """Eine umgeschriebene Protokollzeile mit dem Test-Betriebsschluessel NEU
    zeichnen — der Faelscher, der den Schluessel HAT.

    Tests, deren Gegenstand eine zweite Schicht ist (Ankerreihe,
    Nachrechnung aus dem Stand), zeichnen ihre Faelschung damit neu: Sonst
    faengt schon die Signatur sie, und der Test sagt nichts mehr ueber die
    Schicht, fuer die er geschrieben wurde.
    """
    from rechner_pipeline.models.anker import zeichne

    rest = {k: v for k, v in zeile.items() if k != "zeichnung"}
    return {**rest, "zeichnung": zeichne(rest, BETRIEBSKEY, rolle=BETRIEBSROLLE, klasse="betrieb")}
