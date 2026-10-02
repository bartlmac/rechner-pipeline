"""Wer im Betrieb zeichnet — Rolle und Klasse aus Schluessel und Ordnung.

Der Tagesbetrieb hatte keinen Zeugen ausser sich selbst (Pruefrunde nach
T27, Runde C): Wer die Ablage beschreiben konnte, schrieb Protokoll und
Eingaenge stimmig um, und jede Pruefung las nur, was derselbe Schreiber
hinterlassen hatte. Der Ausweg ist derselbe wie bei den Abnahmen
(ADR-018): ein Schluessel, der ausserhalb der Ablage beim Menschen liegt,
eine Zeichnungsordnung, die seinen Fingerabdruck einer Rolle zuordnet,
und eine HMAC-Zeichnung nach ``models.anker`` ueber jede Zeile. Neu ist
nur die Rolle: ``betrieb/tageslauf`` mit der Schluesselklasse ``betrieb``
(Nachtrag 2026-09-30).

Die Rolle wird aus dem SCHLUESSEL bestimmt, nie behauptet — vorher tat
das der Export allein (``seite._zeichnung_des_exports``), jetzt tun es
Export, Tageslauf, Registrierung und Neuaufsetzen mit EINER Regel. Fuer
den Schluessel gelten die Regeln des Freigabe-Schluesselrings
(``models.freigabe.lade_schluesselring``): 32 bis 4096 Byte, Modus 0600,
genau ein Hardlink, nicht in der Ablage. Was der schreibende Prozess
selbst umschreiben kann, belegt nichts.

Knoten: klv, bu
"""

from __future__ import annotations

import dataclasses
from pathlib import Path
from typing import Any, Dict, Optional

from rechner_pipeline.models.anker import VERFAHREN as _VERFAHREN
from rechner_pipeline.models.anker import pruefe_zeichnung as _pruefe_zeichnung
from rechner_pipeline.models.anker import zeichne as _zeichne

#: Die Klasse, deren Schluessel Protokollzeilen und Eingaenge zeichnet.
BETRIEBSKLASSE = "betrieb"


class ZeichnungFehler(ValueError):
    """Schluessel oder Ordnung tragen keine Zeichnung — mit Ausweg."""


@dataclasses.dataclass(frozen=True)
class Zeichner:
    """Ein geladener Schluessel mit der Rolle, die ihm die Ordnung gibt.

    Die Schluesselbytes stehen nie in einer Ausgabe (``repr=False``); in
    Belegen erscheint nur ihr Fingerabdruck.
    """

    schluessel: bytes = dataclasses.field(repr=False)
    rolle: str
    klasse: str
    ordnung: Dict[str, Any] = dataclasses.field(repr=False)
    ordnung_sha256: str
    #: Nur der Zeichner eines Probelaufs (``betrieb.zugangsprobe``, Runde F,
    #: F9): Fall, Kennung und Kopie der Probe und ihr Zeitpunkt. Wer ihn
    #: haelt, schreibt jede Protokollzeile als PROBEZEILE (Feld
    #: ``zugangsprobe`` im gezeichneten Inhalt) und liest eine Kette, die
    #: solche Zeilen traegt; jeder andere Zeichner verweigert sie. Das
    #: Kennzeichen der Kopie ist eine ungezeichnete Datei und verschwindet
    #: ohne Schluessel — die Probezeile nicht, ohne die Signatur zu brechen.
    zugangsprobe: Optional[Dict[str, str]] = None
    #: Die Versionslinie der Zeichnungsordnung (ADR-025; geprueft aus
    #: ``models.ordnungslinie.lade_linie``), wenn der Aufrufer eine Linie
    #: angibt: Dann haelt jeder Leser des Betriebs eine Abnahme gegen die
    #: Ordnung, unter der sie gezeichnet wurde. None = bisheriger Weg.
    ordnungslinie: Optional[list] = dataclasses.field(default=None, repr=False)

    @property
    def schluessel_sha256(self) -> str:
        import hashlib

        return hashlib.sha256(self.schluessel).hexdigest()

    @property
    def ring(self) -> Dict[str, bytes]:
        """Der Schluesselring, gegen den eine Zeichnung dieses Schluessels
        geprueft wird."""
        return {self.schluessel_sha256: self.schluessel}

    def zeichne(self, satz: Dict[str, Any]) -> Dict[str, Any]:
        """Den Satz zeichnen (``models.anker.zeichne``, Verfahren v2)."""
        return _zeichne(satz, self.schluessel, rolle=self.rolle, klasse=self.klasse)


def lade_zeichner(
    schluessel: Path, zeichnungsordnung: Optional[Path], *, ausserhalb: Path,
) -> Zeichner:
    """Schluessel und Ordnung laden und die Rolle aus dem Schluessel bestimmen.

    ``ausserhalb`` ist der Bereich, in dem weder Schluessel noch Ordnung
    liegen duerfen — die Ablage, in die der Aufrufer schreibt.
    """
    from rechner_pipeline.models.freigabe import lade_schluesselring
    from rechner_pipeline.models.zeichnung import (
        lade_zeichnungsordnung,
        schluesselklasse,
        zeichnungsrolle,
    )

    if zeichnungsordnung is None:
        raise ZeichnungFehler(
            "--schluessel verlangt --zeichnungsordnung: Die Rolle wird aus "
            "dem Schluessel BESTIMMT, nicht behauptet (ADR-018)")
    ring, fehler, aktiv = lade_schluesselring([str(schluessel)], ausserhalb=Path(ausserhalb))
    if fehler or aktiv is None:
        raise ZeichnungFehler(
            "Schluessel: " + "; ".join(fehler[:3] or ["nicht geladen"])
            + " — Ausweg: den Schluessel ausserhalb der Ablage verwahren (0600, "
            "ein Hardlink, 32 bis 4096 Byte)")
    ordnung, sha, fehler = lade_zeichnungsordnung(str(zeichnungsordnung), Path(ausserhalb))
    if fehler or ordnung is None or sha is None:
        raise ZeichnungFehler("Zeichnungsordnung: " + "; ".join(fehler[:3]))
    rolle = zeichnungsrolle(ordnung, aktiv)
    if rolle is None:
        raise ZeichnungFehler(
            f"Der Schluessel ({aktiv[:16]}…) gehoert zu keiner Rolle "
            "der Zeichnungsordnung — ohne Rolle keine Zeichnung")
    return Zeichner(
        schluessel=ring[aktiv], rolle=rolle,
        klasse=str(schluesselklasse(ordnung, rolle)),
        ordnung=ordnung, ordnung_sha256=sha,
    )


def verlange_betrieb(zeichner: Zeichner, wofuer: str) -> Zeichner:
    """Protokollzeilen und Eingaenge zeichnet nur die Klasse ``betrieb``.

    Ein Menschen- oder Agentenschluessel zeichnet sie nicht: Ein Mensch
    steht fuer eine Abnahme ein, ein Agent legt vor — keiner von beiden hat
    die Zeile geschrieben. Liesse man es zu, hiesse jede Zeile "ein Mensch
    hat das gezeichnet", und genau diese Verwechslung soll die Klasse
    verhindern (ADR-018).
    """
    if zeichner.klasse != BETRIEBSKLASSE:
        raise ZeichnungFehler(
            f"{wofuer}: der Schluessel gehoert der Rolle {zeichner.rolle!r} "
            f"(Schluesselklasse {zeichner.klasse!r}) — {wofuer} zeichnet nur ein "
            "Betriebsschluessel (Klasse 'betrieb', ADR-018 Nachtrag 2026-09-30). "
            "Ausweg: den Schluessel einer Rolle betrieb/<name> der "
            "Zeichnungsordnung angeben")
    return zeichner


def betriebszeichnung_fehler(
    satz: Dict[str, Any],
    schluesselring: Optional[Dict[str, bytes]],
    ordnung: Optional[Dict[str, Any]],
    *,
    was: str = "die Zeile",
) -> Optional[str]:
    """Was an der Betriebszeichnung eines Satzes nicht stimmt (None = nichts).

    ``satz`` traegt die Zeichnung unter ``zeichnung`` (``models.anker``).
    Ohne Ring wird die FORM geprueft und nichts behauptet: Wer keinen
    Schluessel haelt (der Konsument eines Stands-Pakets), kann die Signatur
    nicht nachrechnen und sagt das auch nicht. Mit Ring ist ein fehlender
    Schluessel ein harter Befund — "nicht pruefbar" ist im Betrieb kein
    Zustand, in dem weitergeschrieben wird.
    """
    from rechner_pipeline.models.zeichnung import schluesselklasse, zeichnungsrolle

    z = satz.get("zeichnung")
    felder = {"verfahren", "rolle", "schluesselklasse", "schluessel_sha256", "signatur"}
    if not isinstance(z, dict) or set(z) != felder:
        return (f"{was} traegt keine vollstaendige Betriebszeichnung "
                f"{sorted(felder)} — was niemand gezeichnet hat, bezeugt nichts")
    if z.get("verfahren") != _VERFAHREN:
        return f"Zeichenverfahren {z.get('verfahren')!r}, erwartet {_VERFAHREN!r}"
    if z.get("schluesselklasse") != BETRIEBSKLASSE or not str(z.get("rolle")).startswith("betrieb/"):
        return (f"{was} ist gezeichnet von {z.get('rolle')!r} (Klasse "
                f"{z.get('schluesselklasse')!r}) — das zeichnet nur der Betrieb "
                "(Klasse 'betrieb')")
    if ordnung is not None:
        rolle = zeichnungsrolle(ordnung, str(z.get("schluessel_sha256")))
        if rolle != z.get("rolle") or schluesselklasse(ordnung, str(rolle)) != BETRIEBSKLASSE:
            return (f"Rolle {z.get('rolle')!r} und Schluessel "
                    f"{str(z.get('schluessel_sha256'))[:16]}… passen nicht zur "
                    f"Zeichnungsordnung (dort: {rolle!r}) — die Rolle wird aus dem "
                    "Schluessel bestimmt")
    if schluesselring is not None:
        if str(z.get("schluessel_sha256")) not in schluesselring:
            return (f"nicht pruefbar: {was} ist mit dem Schluessel "
                    f"{str(z.get('schluessel_sha256'))[:16]}… gezeichnet, der nicht "
                    "bereitgestellt ist — ohne ihn ist sie kein Nachweis. Ausweg: "
                    "den Betriebsschluessel dieser Ablage angeben")
        if _pruefe_zeichnung(satz, schluesselring):
            return (f"die Signatur stimmt nicht mit dem Inhalt ueberein — {was} "
                    "wurde nach dem Zeichnen veraendert")
    return None
