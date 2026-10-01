"""Der Testschluessel der Freigabesignatur — eine Naht, kein Geheimnis.

Seit die Zeichnungsschicht im Betriebseingang zu Ende gebaut ist (T26-03,
2026-09-22), prueft ``eingang_anlegen`` die Freigabesignatur eines A-M4-
Snapshots. Die Test-Snapshots (``test_betrieb_uebernahme.am4_snapshot``)
signieren mit diesem Schluessel, und ``conftest`` reicht den Ring an den
Betriebseingang — deterministisch, ohne dass eine der vielen
Registrierungsstellen in den Tests einen Ring tragen muss.
"""

from __future__ import annotations

import hashlib

TESTKEY: bytes = hashlib.sha256(b"rechner-pipeline: testschluessel der freigabe").digest()
TESTRING: dict = {hashlib.sha256(TESTKEY).hexdigest(): TESTKEY}
FREMDER_SCHLUESSEL: bytes = hashlib.sha256(b"ein anderer schluessel").digest()

#: Der Test-Betriebsschluessel (Rolle ``betrieb/tageslauf``, Klasse
#: ``betrieb``; ADR-018, Nachtrag 2026-09-30). ``conftest`` legt ihn als
#: Datei 0600 in ein Session-Verzeichnis AUSSERHALB jeder Ablage und setzt
#: die Naht ``tageslauf._STANDARD_BETRIEBSZEICHNUNG`` — damit die vielen
#: ``tageslauf()``-Aufrufe der Suite unveraendert laufen und trotzdem jede
#: Zeile gezeichnet und geprueft wird.
BETRIEBSKEY: bytes = hashlib.sha256(b"rechner-pipeline: testschluessel des betriebs").digest()
BETRIEBSROLLE = "betrieb/tageslauf"


#: Die Rolle, die im Test die Zugangsabnahme A-B2 zeichnet — mit dem
#: Freigabe-Testschluessel, mit dem die Naht der Zugangsabnahme ihre
#: A-B2-Snapshots signiert. Die Registrierung haelt den Fingerabdruck der
#: Freigabe gegen eine Rolle mit A-B2 in dieser Ordnung (Block F,
#: Nachbesserung, Pruefer-Befund 9).
AB2_ROLLE = "mensch/betrieb"


def betriebsordnung(weitere: "dict | None" = None) -> dict:
    """Die Test-Zeichnungsordnung (Schema 2) mit der Betriebsrolle und der
    Rolle, die A-B2 zeichnet."""
    rollen = {BETRIEBSROLLE: {
        "schluessel_sha256": hashlib.sha256(BETRIEBSKEY).hexdigest(),
        "schluesselklasse": "betrieb", "gates": []},
        AB2_ROLLE: {
        "schluessel_sha256": hashlib.sha256(TESTKEY).hexdigest(),
        "schluesselklasse": "mensch", "gates": ["A-B2"]}}
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
