"""Die Sichten der Abnahmebelege — EIN Register, EINE Regel beim Zeichnen.

Runde G (Linse betrieb-ausfall, Fund G26, eine Klasse): Jeder Produzent
eines Belegs, den ein Mensch zeichnet, schrieb erst den Beleg bzw. die
Vorlage und danach die lesbare Sicht. Fiel das Schreiben der Sicht aus, lag
die neue Vorlage neben der alten Sicht, und das Gate zeichnete die neue
Vorlage, die der Mensch nie gesehen hatte — gemessen fuer A-K2, A-O1, A-T1,
A-B3, A-M6 und A-M5 (beim Fallauftrag bekam so eine andere Programmleitung
das Recht auf den Abbruch, als der Vorstand gesehen hatte). Kein Gate pinnte
oder pruefte die Sicht.

**Die Invariante.** Gezeichnet wird nur eine Vorlage, deren Sicht am festen
Ort byte-gleich die aus genau dieser Vorlage erzeugte ist (ADR-025,
Abschnitt 1: "deterministisch aus dem Beleg erzeugt"; ADR-026: erst ansehen,
dann zeichnen).

**Die Regel.** Beim Zeichnen einer ANNAHME erzeugt das Gate die Sicht aus
den Belegen, die es pinnt — aus den Bytes seiner einen Lesung (Review
T23-01), nicht aus einer zweiten —, mit derselben Renderfunktion wie der
Produzent neu und vergleicht sie mit der Datei am festen Ort
(:func:`sicht_fehler`, gerufen an EINER Stelle in ``gate_entscheid.main``).
Fehlt sie oder weicht sie ab, verweigert es benannt, mit dem Ausweg "Vorlage
neu erzeugen". Die Reihenfolge im Produzenten ist damit unerheblich: Die
Regel faengt beide Richtungen (Beleg neu und Sicht alt, Sicht neu und Beleg
alt) und die fehlende Sicht. Eine Ablehnung zeichnet nichts ab und braucht
keine Sicht.

Verworfen: (i) die Sicht als weiteren Pflichtbeleg pinnen — das bindet die
alte Sicht an den Snapshot, prueft aber nicht, dass sie zur Vorlage gehoert;
(ii) nur die Schreibreihenfolge drehen — das schliesst eine Richtung, die
andere bleibt offen.

**Das Register** (:data:`SICHTEN`): je Gate mit Sicht die Pflichtbelege, aus
denen sie entsteht (Rolle und fester Ort), der Ort der Sicht, die
Renderfunktion und der Produzent. A-O1 nennt dazu das Archiv: Gezeichnet
wird nur, wenn die Archivkopie des gepinnten Belegs liegt und zum Pin passt
(Fund G24 — sonst behauptet die naechste Vorlage still "Erstabnahme").
Die Ordnungsaenderung A-Z1 steht NICHT im Register: Sie ist kein Gate dieses
Kommandos, der Vorstand zeichnet das Glied im Produzenten selbst
(``stand_belegen ordnung``); ihre Sicht ist dort nachziehbar.

Schichten: Die Renderfunktion des Anfangsbestands wohnt beim Vertrag
(``models.anfangsbestand.rendere_sicht``), weil ``gates`` ``betrieb`` nicht
importieren darf und beide ``models`` erreichen — keine neue Kante.

Knoten: system/entscheid
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any, Callable, Dict, Mapping, Optional, Sequence, Tuple

from rechner_pipeline.gates import stand_belegen as _stand
from rechner_pipeline.models import anfangsbestand as _ab
from rechner_pipeline.models import fallauftrag as _fa
from rechner_pipeline.models import kernabnahme as _ka
from rechner_pipeline.models import tarifwerkabnahme as _tw
from rechner_pipeline.models.zeichnung import ABBRUCH_GATE, AUFTRAG_GATE


@dataclass(frozen=True)
class Sicht:
    """Ein Gate mit Sicht: woraus sie entsteht, wo sie liegt, wer sie erzeugt."""

    gate: str
    #: (Pflichtbelegrolle, fester Ort relativ zum Bereich) — die Bytes, die
    #: das Gate pinnt und aus denen die Sicht entsteht.
    belege: Tuple[Tuple[str, str], ...]
    sicht_relativ: str
    #: Rolle -> geparster Beleg  =>  Text der Sicht.
    rendere: Callable[[Mapping[str, Any]], str]
    #: der Produzent (wie ``models.standabnahme.Gegenstand.werkzeug``).
    werkzeug: str
    #: Pflichtbelegrolle, deren gepinnte Fassung zusaetzlich im Archiv des
    #: Bereichs liegen muss, mit der Pruefung des Produzenten
    #: ``(bereich, pin) -> Befund oder None``; None = kein Archiv.
    archiv: Optional[Tuple[str, Callable[[Path, object], Optional[str]]]] = None


def _kern(b: Mapping[str, Any]) -> str:
    from rechner_pipeline.gates.kernstand_belegen import rendere_sicht

    return rendere_sicht(b["kernaenderung"], b["regression"])


def _tbox(b: Mapping[str, Any]) -> str:
    return _stand.rendere_tbox_sicht(b["tbox_aenderung"])


def _tarifwerk(b: Mapping[str, Any]) -> str:
    from rechner_pipeline.gates.tarifwerk_belegen import rendere_sicht

    return rendere_sicht(b["tarifwerk_aenderung"])


def _auftrag(b: Mapping[str, Any]) -> str:
    from rechner_pipeline.gates.fall_belegen import rendere_auftrag

    return rendere_auftrag(b["fallauftrag"])


def _abbruch(b: Mapping[str, Any]) -> str:
    from rechner_pipeline.gates.fall_belegen import rendere_abbruch

    return rendere_abbruch(b["fallabbruch"])


def _anfangsbestand(b: Mapping[str, Any]) -> str:
    return _ab.rendere_sicht(b["anfangsbestand"])


#: Das Register — abschliessend. Die Ratsche haelt es mit == gegen die Menge
#: der Gates, deren Produzent eine Sicht schreibt (die Gegenstaende der
#: Standabnahme und die Vorlagen des Lebenslaufs) und gegen jede Konstante
#: ``*SICHT_RELATIV`` des Pakets (tests/test_sicht_beleg_ausfall.py).
SICHTEN: Dict[str, Sicht] = {s.gate: s for s in (
    Sicht("A-K2", (("kernaenderung", _ka.AENDERUNG_RELATIV),
                   ("regression", _ka.REGRESSION_RELATIV)),
          _ka.SICHT_RELATIV, _kern, "rechner_pipeline.gates.kernstand_belegen"),
    Sicht("A-O1", (("tbox_aenderung", _stand.TBOX_AENDERUNG_RELATIV),),
          _stand.TBOX_SICHT_RELATIV, _tbox, "rechner_pipeline.gates.stand_belegen tbox",
          archiv=("tbox_aenderung", _stand.tbox_archiv_fehler)),
    Sicht("A-T1", (("tarifwerk_aenderung", _tw.AENDERUNG_RELATIV),),
          _tw.SICHT_RELATIV, _tarifwerk, "rechner_pipeline.gates.tarifwerk_belegen"),
    Sicht("A-B3", (("anfangsbestand", _ab.BELEG_RELATIV),),
          _ab.SICHT_RELATIV, _anfangsbestand,
          "rechner_pipeline.betrieb.anfangsbestand belegen"),
    Sicht(AUFTRAG_GATE, (("fallauftrag", _fa.AUFTRAG_RELATIV),),
          _fa.AUFTRAG_SICHT_RELATIV, _auftrag, "rechner_pipeline.gates.fall_belegen auftrag"),
    Sicht(ABBRUCH_GATE, (("fallabbruch", _fa.ABBRUCH_RELATIV),),
          _fa.ABBRUCH_SICHT_RELATIV, _abbruch, "rechner_pipeline.gates.fall_belegen abbruch"),
)}


def _kommando(eintrag: Sicht) -> str:
    return f"python -m {eintrag.werkzeug} ..."


def sicht_fehler(gate: str, bereich: Path, pflichtbelege: Mapping[str, Sequence[str]],
                 gelesen: Mapping[str, Any]) -> Optional[str]:
    """Die Regel (None = die Sicht am festen Ort ist die aus den gepinnten
    Belegen erzeugte). Fuer Gates ohne Registereintrag: None.

    ``gelesen``: je Pflichtbelegrolle der geparste Beleg aus der EINEN Lesung
    des Gates, deren SHA-256 der Pin ist (``pflichtbelege``). Die Regel liest
    die Belege nicht ein zweites Mal von der Platte (Review T23-01: eine
    Datei, deren Hash im Beleg steht, wird genau einmal gelesen); sie liest
    nur die Sicht (kein Beleg, kein Hash im Snapshot) und fuer A-O1 die
    Archivkopie (eine andere Datei, gegen den Pin gehalten). Fehlt eine Rolle
    in ``gelesen``, verweigert sie — die Sicht entstuende sonst aus Bytes,
    die dieser Lauf nicht geprueft hat."""
    eintrag = SICHTEN.get(gate)
    if eintrag is None:
        return None
    ausweg = f"Ausweg: Vorlage neu erzeugen ({_kommando(eintrag)}), ansehen, dann zeichnen"
    geparst: Dict[str, Any] = {}
    for rolle, relativ in eintrag.belege:
        if not (pflichtbelege.get(rolle) and rolle in gelesen):
            return (f"{relativ} ist in diesem Lauf nicht als Pflichtbeleg {rolle!r} gelesen — "
                    f"die Sicht ist nicht pruefbar. {ausweg}")
        geparst[rolle] = gelesen[rolle]
    try:
        soll = eintrag.rendere(geparst).encode("utf-8")
    except (KeyError, TypeError, AttributeError, ValueError) as exc:
        return f"die Sicht ist aus den Belegen nicht erzeugbar ({type(exc).__name__}: {exc}) — {ausweg}"
    ort = Path(bereich) / eintrag.sicht_relativ
    try:
        ist = ort.read_bytes()
    except FileNotFoundError:
        return (f"die Sicht {eintrag.sicht_relativ} fehlt — gezeichnet wird nur, was der Mensch "
                f"gesehen haben kann. {ausweg}")
    except OSError as exc:
        return f"die Sicht {eintrag.sicht_relativ} ist nicht lesbar ({exc}) — {ausweg}"
    if ist != soll:
        return (f"die Sicht {eintrag.sicht_relativ} ist nicht die aus der Vorlage erzeugte — "
                "sie zeigt eine andere Fassung als die, die gezeichnet wuerde (ein Ausfall "
                f"zwischen Beleg und Sicht, oder eine Hand). {ausweg}")
    if eintrag.archiv is not None:
        rolle, pruefe = eintrag.archiv
        fehler = pruefe(Path(bereich), (list(pflichtbelege.get(rolle) or []) or [None])[0])
        if fehler is not None:
            return (f"{fehler} — ohne die Archivkopie des gepinnten Belegs zeigte die naechste "
                    f"Vorlage still 'Erstabnahme'. {ausweg}")
    return None
