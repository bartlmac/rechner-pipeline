"""Konformitaet: was jede Implementierung des Zielvertrags bestehen muss.

``pruefe`` liefert Befunde (leer = konform), die Tests fahren sie gegen
den Anbieter (``tests/test_zielsystem.py``). Jede Regel hat dort eine
Positivkontrolle mit einer absichtlich falschen Implementierung.

Eine Implementierung, die statt zu antworten eine Ausnahme wirft, ist
ein Befund und kein Absturz des Pruefers (A-053, B1): Der Vertrag
verspricht Befunde, und eine fehlerhafte Implementierung ist genau das,
was die Pruefung finden soll.

Je Faehigkeit mit Protokoll prueft ``PRUEFUNG_JE_FAEHIGKEIT`` ueber die
Form hinaus, was das Protokoll in Worten verlangt (Stufe 1: die
Rechnungsgrundlagen).

Knoten: system/zielsystem
"""

from __future__ import annotations

import re
from types import MappingProxyType
from typing import Callable, List, Mapping

from rechner_pipeline.zielsystem.rechnungsgrundlagen import Parametersatz
from rechner_pipeline.zielsystem.version import VERTRAG_VERSION, vertraeglich, zerlege
from rechner_pipeline.zielsystem.vertrag import FAEHIGKEITEN, PROTOKOLL_JE_FAEHIGKEIT, Zielsystem

__all__ = ["PRUEFUNG_JE_FAEHIGKEIT", "pruefe", "pruefe_rechnungsgrundlagen"]

_NAME = re.compile(r"^[a-z][a-z0-9_]*$")


def _ausnahme(exc: BaseException) -> str:
    return f"{type(exc).__name__}: {exc}"


def pruefe_rechnungsgrundlagen(umsetzung: object) -> List[str]:
    """Was das Protokoll ``Rechnungsgrundlagen`` in Worten verlangt: ein
    Produkt mindestens, je Produkt ein Parametersatz mit eindeutigen
    Feldern, dessen Defaults Felder sind, ``KeyError`` fuer ein unbekanntes
    Produkt, und Tafelnamen als frozenset von str."""
    befunde: List[str] = []
    produkte: frozenset = frozenset()
    try:
        roh = umsetzung.produkte()  # type: ignore[attr-defined]
    except Exception as exc:  # noqa: BLE001 - die Ausnahme ist der Befund
        befunde.append(f"produkte() wirft {_ausnahme(exc)}")
    else:
        if isinstance(roh, frozenset) and roh and all(isinstance(p, str) for p in roh):
            produkte = roh
        else:
            befunde.append(f"produkte() liefert {roh!r}, erwartet ein nicht leeres frozenset von str")
    for produkt in sorted(produkte):
        try:
            satz = umsetzung.parametersatz(produkt)  # type: ignore[attr-defined]
        except Exception as exc:  # noqa: BLE001
            befunde.append(f"parametersatz({produkt!r}) wirft {_ausnahme(exc)}")
            continue
        if not isinstance(satz, Parametersatz):
            befunde.append(
                f"parametersatz({produkt!r}) liefert {type(satz).__name__}, erwartet Parametersatz")
            continue
        if satz.produkt != produkt:
            befunde.append(f"parametersatz({produkt!r}) nennt das Produkt {satz.produkt!r}")
        namen = satz.feldnamen()
        if not namen or len(set(namen)) != len(namen):
            befunde.append(f"parametersatz({produkt!r}): Felder leer oder doppelt: {namen}")
        fremd = sorted(set(satz.defaults) - set(namen))
        if fremd:
            befunde.append(f"parametersatz({produkt!r}): Defaults ohne Feld: {fremd}")
    try:
        umsetzung.parametersatz("kein_produkt")  # type: ignore[attr-defined]
    except KeyError:
        pass
    except Exception as exc:  # noqa: BLE001
        befunde.append(f"parametersatz('kein_produkt') wirft {_ausnahme(exc)}, erwartet KeyError")
    else:
        befunde.append("parametersatz('kein_produkt') liefert etwas, erwartet KeyError")
    try:
        tafeln = umsetzung.verfuegbare_tafeln()  # type: ignore[attr-defined]
    except Exception as exc:  # noqa: BLE001
        befunde.append(f"verfuegbare_tafeln() wirft {_ausnahme(exc)}")
    else:
        if not isinstance(tafeln, frozenset) or not all(isinstance(t, str) for t in tafeln):
            befunde.append(
                f"verfuegbare_tafeln() liefert {type(tafeln).__name__}, erwartet frozenset von str")
    return befunde


#: Faehigkeit -> Pruefung ueber die Form des Protokolls hinaus.
PRUEFUNG_JE_FAEHIGKEIT: Mapping[str, Callable[[object], List[str]]] = MappingProxyType({
    "rechnungsgrundlagen": pruefe_rechnungsgrundlagen,
})


def pruefe(zielsystem: object) -> List[str]:
    """Befunde zur Konformitaet einer Implementierung mit dem Vertrag
    ``VERTRAG_VERSION``; leer heisst konform."""
    befunde: List[str] = []
    if not isinstance(zielsystem, Zielsystem):
        return [
            f"{type(zielsystem).__name__} erfuellt das Wurzelprotokoll Zielsystem nicht "
            "(name, vertragsversion, faehigkeiten, faehigkeit)"
        ]
    name = zielsystem.name
    if not isinstance(name, str) or not _NAME.match(name):
        befunde.append(f"name {name!r} ist keine Kennung ([a-z][a-z0-9_]*)")
    version = zielsystem.vertragsversion
    try:
        zerlege(version)
    except (ValueError, AttributeError, TypeError):
        befunde.append(f"vertragsversion {version!r} ist keine Vertragsversion")
    else:
        if not vertraeglich(version, VERTRAG_VERSION):
            befunde.append(
                f"vertragsversion {version} ist mit dem Vertrag {VERTRAG_VERSION} nicht "
                "vertraeglich (gleiche Haupt- und Nebenversion verlangt)"
            )
    try:
        angeboten = zielsystem.faehigkeiten()
        if not isinstance(angeboten, frozenset):
            befunde.append(f"faehigkeiten() liefert {type(angeboten).__name__}, erwartet frozenset")
            angeboten = frozenset(angeboten)
    except Exception as exc:  # noqa: BLE001 - B1: die Ausnahme ist der Befund
        befunde.append(f"faehigkeiten() wirft {_ausnahme(exc)}")
        return befunde
    for unbekannt in sorted(angeboten - set(FAEHIGKEITEN)):
        befunde.append(f"bietet die unbekannte Faehigkeit {unbekannt!r} an")
    for ohne in sorted((angeboten & set(FAEHIGKEITEN)) - set(PROTOKOLL_JE_FAEHIGKEIT)):
        befunde.append(
            f"bietet {ohne!r} an, der Vertrag {VERTRAG_VERSION} beschreibt dafuer kein Protokoll"
        )
    for faehigkeit in sorted(angeboten & set(PROTOKOLL_JE_FAEHIGKEIT)):
        try:
            umsetzung = zielsystem.faehigkeit(faehigkeit)
        except KeyError:
            befunde.append(f"bietet {faehigkeit!r} an, liefert dafuer aber KeyError")
            continue
        except Exception as exc:  # noqa: BLE001 - B1
            befunde.append(f"faehigkeit({faehigkeit!r}) wirft {_ausnahme(exc)}")
            continue
        protokoll = PROTOKOLL_JE_FAEHIGKEIT[faehigkeit]
        if not isinstance(umsetzung, protokoll):
            befunde.append(
                f"die Umsetzung von {faehigkeit!r} erfuellt das Protokoll "
                f"{protokoll.__name__} nicht"
            )
            continue
        pruefung = PRUEFUNG_JE_FAEHIGKEIT.get(faehigkeit)
        if pruefung is not None:
            befunde.extend(f"{faehigkeit}: {b}" for b in pruefung(umsetzung))
    for nicht in sorted(set(FAEHIGKEITEN) - angeboten):
        try:
            zielsystem.faehigkeit(nicht)
        except KeyError:
            continue
        except Exception as exc:  # noqa: BLE001 - B1
            befunde.append(f"faehigkeit({nicht!r}) wirft {_ausnahme(exc)}, erwartet KeyError")
            continue
        befunde.append(f"liefert {nicht!r}, obwohl es die Faehigkeit nicht anbietet")
    return befunde
