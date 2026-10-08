"""Das Gate-Register: welche Pruef- und Abnahmegates es gibt, was jedes
prueft, wer entscheidet und was ihm vorausgehen muss.

Lesefassung der Gate-Namensordnung (ADR-012) als Code, damit eine
Darstellung — die Seite "Unsere Pruefgates", ein Bericht — nicht abgetippt
wird. Die Namen der Programmgates sind hier Literale; die Testdatei bindet
sie an die ``GATE``-Konstanten der Gate-Module und die Abnahmen an
``models.zeichnung.GUELTIGE_GATES`` — weicht eines ab, faellt der Test,
nicht die Seite. Die Vorgaenger der Abschlussabnahme A-M4 kommen nicht aus
diesem Register, sondern aus ``models.belegrollen.BELEGROLLEN`` — dort werden sie
erzwungen; eine Belegrolle ohne Zuordnung hier ist ein harter Fehler.

Kommando::

    python -m rechner_pipeline.gates.register --format markdown|json

Knoten: system/assurance
"""

from __future__ import annotations

import argparse
import json
import sys
from dataclasses import asdict, dataclass
from typing import Dict, List, Optional, Tuple

from rechner_pipeline.models.belegrollen import BELEGROLLEN

ART = {"P": "Pruefung durch das Programm", "A": "Abnahme durch einen Menschen"}
GEGENSTAND = {"Q": "Quellen und Ontologie", "K": "Rechenkern",
              "B": "Bestand", "M": "Migration als Ganzes",
              "O": "Ontologie als Vertrag", "T": "Tarifwerk"}


@dataclass(frozen=True)
class Gate:
    kennung: str          # "P-Q3"
    name: str             # fachliche Kennung, wie im Ledger: "fachliche-pruefung"
    stufe: int            # 1 Quellen -> A-Box, 2 A-Box -> Spez, 3 Abnahme, 4 Betrieb
    gegenstand_satz: str  # was geprueft bzw. abgenommen wird (Unternehmenssprache)
    werkzeug: str         # Kommando, das das Gate faehrt bzw. die Vorlage erzeugt
    beleg: str            # was das Gate hinterlaesst

    @property
    def art(self) -> str:
        return self.kennung[0]

    @property
    def gegenstand(self) -> str:
        return self.kennung[2]

    @property
    def kennung_voll(self) -> str:
        return f"{self.kennung}.{self.name}"


REGISTER: Tuple[Gate, ...] = (
    Gate("P-Q1", "quellfragment", 1,
         "Ein geliefertes Quellwerk (Tarifrechner, Tarifbeschreibung) wird "
         "deterministisch vorverdichtet — nichts wird umgeschrieben oder "
         "ergänzt, derselbe Lauf ergibt dieselben Bytes — und die Extraktion "
         "geprüft: Manifest gültig, Eingaben nicht leer, Altstände entfernt. "
         "Dabei misst das Gate, ob die Quelle Sollwerte für die spätere "
         "Nachrechnung mitbringt (Erwartungswert-Abdeckung full, sparse, "
         "none). Das Fragment selbst deutet danach ein Modell; die Prüfung "
         "P-Q3 fängt die Deutung.",
         "gates.extract", "Extraktionsmanifest mit Prüfsummen und Erwartungswert-Abdeckung"),
    Gate("P-Q2", "zusammenfuehrung", 1,
         "Die Fragmente aller Quellen werden zu einer Faktenbasis "
         "zusammengeführt; widersprechen sich zwei Quellen, entsteht eine "
         "Diskrepanz — sie wird festgehalten, nicht aufgelöst.",
         "gates.abox_merge", "Faktenbasis (A-Box) mit Diskrepanzen"),
    Gate("P-Q3", "fachliche-pruefung", 1,
         "Die Faktenbasis wird gegen den fachlichen Vertrag, das "
         "Eingangsregister und den Pflichtumfang geprüft; offene "
         "Diskrepanzen blockieren.",
         "gates.abox_validate", "Ledger P-Q3"),
    Gate("A-Q1", "quellenabnahme", 2,
         "Ein Mensch nimmt die aus den Quellen abgeleitete Fachspezifikation "
         "ab — einschließlich der Entscheide zu jeder Diskrepanz und der "
         "Abdeckung des Pflichtumfangs.",
         "gates.gate_entscheid --gate A-Q1", "signierter Entscheid-Snapshot"),
    Gate("A-M6", "fallauftrag", 1,
         "Der Vorstand beauftragt den Fall: wer ihn führt, was migriert wird, "
         "wer unter welchem Mandat zeichnet und auf welchem "
         "abgenommenen Stand des Zielsystems. Jede weitere Abnahme des Falls "
         "setzt den angenommenen Auftrag voraus.",
         "gates.fall_belegen auftrag, Vollzug gates.gate_entscheid --gate A-M6",
         "Fallauftrag, Entscheid-Snapshot"),
    Gate("A-O1", "tbox-aenderung", 2,
         "Ein Mensch nimmt den Stand der Ontologie ab — des Vertrags, auf den "
         "sich Quellen, Spezifikation und Rechenwerk beziehen. Einmal "
         "außerhalb jedes Falls (Erstabnahme), danach im Fall nur, was sich "
         "durch ihn ändert; sonst verweist der Fall auf die geltende Abnahme.",
         "gates.gate_entscheid --gate A-O1, Verweis gates.stand_belegen verweisen",
         "Entscheid-Snapshot oder Verweis auf die geltende Abnahme"),
    Gate("A-T1", "tarifwerk", 2,
         "Ein Mensch nimmt das Tarifwerk ab — Tarifpläne und Parametrierung "
         "der eigenen Tarifgenerationen —, mit jedem geänderten Feld neben "
         "seinem alten Wert.",
         "gates.tarifwerk_belegen, Vollzug gates.gate_entscheid --gate A-T1",
         "Änderungsbeleg des Tarifwerks, Entscheid-Snapshot"),
    Gate("P-K1", "generations-golden-master", 3,
         "Der aus der Spezifikation parametrierte Rechenkern wird gegen die "
         "Erwartungswerte des Quellrechners gerechnet; je Generation entsteht "
         "ein inhaltsadressierter Beleg mit Faktenbasis- und Systemstand.",
         "gates.generation_golden", "Golden-Master-Beleg je Generation"),
    Gate("P-B1", "bestandspruefung", 3,
         "Der Bestand wird gegen seinen Vertrag geprüft: Stamm, Historie, "
         "Ledger und Scheiben passen zusammen, jede Buchung trägt ihren "
         "Betrag aus dem Rechenkern; im Tagesbetrieb die nächtliche Wache.",
         "gates.bestand_validate", "Ledger P-B1"),
    Gate("A-M1", "stichtagstest", 3,
         "Aktuarielle Abnahme am Stichtag: Test je Vertrag am eigenen "
         "Verankerungszeitpunkt auf einer belegten Stichprobe.",
         "gates.aktuartest --abnahme A-M1", "Testergebnis, Bericht, Entscheid-Snapshot"),
    Gate("A-M2", "verlaufstest", 3,
         "Aktuarielle Abnahme des Verlaufs: die Deckungsrückstellung ueber "
         "die Laufzeit gegen die Referenz.",
         "gates.aktuartest --abnahme A-M2", "Testergebnis, Bericht, Entscheid-Snapshot"),
    Gate("A-M3", "geschaeftsvorfalltest", 3,
         "Aktuarielle Abnahme der Geschäftsvorfälle: jeder Vorfall an der "
         "Änderung des Deckungskapitals, als Vollerhebung.",
         "gates.aktuartest --abnahme A-M3", "Testergebnis, Bericht, Entscheid-Snapshot"),
    Gate("A-M4", "migrationscontrolling", 3,
         "Abschlussabnahme der Migration: bindet die Pflichtbelege aller "
         "vorangehenden Gates und prueft sie erneut auf demselben Eingangs-, "
         "Faktenbasis-, System- und Stichtagsstand.",
         "gates.abnahmebericht, Vollzug gates.gate_entscheid --gate A-M4",
         "Abnahmebericht, Entscheid-Snapshot mit Artefakt-Hashes"),
    Gate("A-K2", "kernaenderung", 3,
         "Ein Mensch nimmt den Stand des Rechenkerns ab, auf dem ein Fall "
         "rechnet — mit jeder Änderung seit der letzten Abnahme, je Modul. "
         "Der Regressionsbeleg sagt, was die Änderung für den laufenden "
         "Bestand bedeutet; solange sein Werkzeug fehlt, steht er als "
         "benannte Ausnahme im Beleg, nie als Urteil.",
         "gates.kernstand_belegen, Vollzug gates.gate_entscheid --gate A-K2",
         "Änderungsbeleg des Kerns, Regressionsbeleg, Entscheid-Snapshot"),
    Gate("A-M5", "fallabbruch", 3,
         "Das entschiedene Ende eines Falls ohne Abnahme: Die Programmleitung "
         "des Falls hält fest, warum er abgebrochen wird. Ein Fall endet mit "
         "der Migrationsabnahme oder mit diesem Entscheid, nicht im Sande.",
         "gates.fall_belegen abbruch, Vollzug gates.gate_entscheid --gate A-M5",
         "Abbruchbeleg, Entscheid-Snapshot"),
    Gate("A-B1", "auslieferung", 4,
         "Der Betrieb nimmt ab, dass ein Stand nach außen sichtbar wird. Die "
         "erste Abnahme der laufenden Linie statt eines Falls: Der Bestand "
         "wird täglich geführt, ob eine Migration läuft oder nicht.",
         "gates.gate_entscheid --gate A-B1", "signierter Entscheid-Snapshot"),
    Gate("A-B2", "zugangsabnahme", 4,
         "Der Betrieb nimmt den Zugang eines abgenommenen Bestands in die "
         "geführte Ablage ab: Eine Zugangsprobe fährt auf einer Kopie der "
         "Ablage zwei Läufe, mit und ohne den Eingang, und vergleicht, was "
         "der Zugang bewirkt, mit dem, was abgenommen wurde — vor der "
         "Registrierung, nicht erst am ersten Monatsabschluss.",
         "betrieb.zugangsprobe, Vollzug gates.gate_entscheid --gate A-B2",
         "Zugangsprobe, Entscheid-Snapshot"),
    Gate("A-B3", "anfangsbestand", 4,
         "Der Betrieb nimmt den Bestand ab, den eine neu aufgesetzte Ablage "
         "nach ihrem ersten Lauf führt — einmal, außerhalb jedes Falls.",
         "betrieb.anfangsbestand belegen, Vollzug gates.gate_entscheid --gate A-B3",
         "Beleg des Anfangsbestands, Entscheid-Snapshot"),
)

#: Belegrollen der Abschlussabnahme (models.belegrollen.BELEGROLLEN) -> Gate, dessen
#: Beleg sie sind. Rollen ohne Gate (die Migrationssuite, der
#: Abnahmebericht selbst) sind Artefakte des Controllings.
_BELEGROLLE_GATE: Dict[str, Optional[str]] = {
    "pq3_ledger": "P-Q3", "aq1_snapshot": "A-Q1", "am1_snapshot": "A-M1",
    "am2_snapshot": "A-M2", "am3_snapshot": "A-M3", "pk1_belege": "P-K1",
    "pb1_ledger": "P-B1", "migrationssuite": None, "abnahmebericht": None,
    # Fuehrungsprobe (Freischaltung des uebernommenen Bestands): Beleg eines
    # Produzenten ohne eigenes Gate, wie die Migrationssuite.
    "fuehrungsprobe": None,
    # Schichten und Verankerung (DORA-Triage Block A): Erzeugnisse von
    # verankerung_belegen, ebenfalls ohne eigenes Gate.
    "schichten": None,
    "verankerung": None,
    # Standabnahme (ADR-018 Nachtrag 2026-10-01, ADR-025): Der Stand, auf dem
    # der Fall rechnet, ist abgenommen — im Fall gezeichnet oder per Verweis
    # auf eine fruehere Abnahme. Vorgaenger ist das Gate des Gegenstands.
    "kernstand": "A-K2",
    "tboxstand": "A-O1",
    "tarifwerkstand": "A-T1",
}


class RegisterFehler(ValueError):
    """Das Register passt nicht zu dem, was der Code erzwingt."""


def vorgaenger(kennung: str, scope: str) -> List[str]:
    """Erzwungene Vorgaenger eines Gates im Scope, aus ``models.belegrollen.BELEGROLLEN``.

    Nur A-M4 hat erzwungene Vorgaenger; alle anderen liefern ``[]`` —
    behauptet wird nur, was ein Gate tatsaechlich verlangt.
    """
    if kennung != "A-M4":
        return []  # die Belegrollen der Abnahmen A-M1..A-M3 sind ihre EIGENEN Belege
    rollen = (BELEGROLLEN.get(kennung) or {}).get(scope)
    if rollen is None:
        return []
    aus: List[str] = []
    for rolle in rollen:
        if rolle not in _BELEGROLLE_GATE:
            raise RegisterFehler(
                f"Belegrolle {rolle!r} von {kennung} ({scope}) ist keinem Gate "
                "zugeordnet — _BELEGROLLE_GATE im Register nachziehen"
            )
        gate = _BELEGROLLE_GATE[rolle]
        if gate and gate not in aus:
            aus.append(gate)
    return aus


def als_dicts() -> List[Dict[str, object]]:
    aus = []
    for g in REGISTER:
        d = asdict(g)
        d.update({
            "art": g.art, "art_text": ART[g.art],
            "gegenstand": g.gegenstand, "gegenstand_text": GEGENSTAND[g.gegenstand],
            "kennung_voll": g.kennung_voll,
            "vorgaenger": {"tarif": vorgaenger(g.kennung, "tarif"),
                           "bestand": vorgaenger(g.kennung, "bestand")},
        })
        aus.append(d)
    return aus


def als_markdown() -> str:
    z = ["| Gate | Art | Stufe | Was geprueft bzw. abgenommen wird | Werkzeug | Hinterlaesst | Vorgaenger (Tarif / Bestand) |",
         "|---|---|---:|---|---|---|---|"]
    for d in als_dicts():
        v = d["vorgaenger"]
        vor = (" / ".join(", ".join(v[s]) or "—" for s in ("tarif", "bestand"))
               if v["tarif"] or v["bestand"] else "—")
        z.append(f"| **{d['kennung']}** `{d['name']}` | {d['art_text']} | {d['stufe']} "
                 f"| {d['gegenstand_satz']} | `{d['werkzeug']}` | {d['beleg']} | {vor} |")
    return "\n".join(z) + "\n"


def main(argv: Optional[List[str]] = None) -> int:
    p = argparse.ArgumentParser(
        prog="python -m rechner_pipeline.gates.register",
        description="Das Gate-Register ausgeben (ADR-012 als Code).")
    p.add_argument("--format", choices=("markdown", "json"), default="markdown")
    args = p.parse_args(argv)
    try:
        if args.format == "json":
            sys.stdout.write(json.dumps(als_dicts(), ensure_ascii=False, indent=2, sort_keys=True) + "\n")
        else:
            sys.stdout.write(als_markdown())
    except RegisterFehler as exc:
        print(f"register: {exc}", file=sys.stderr)
        return 2
    return 0


if __name__ == "__main__":  # pragma: no cover
    raise SystemExit(main())
