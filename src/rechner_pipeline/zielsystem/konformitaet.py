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
Rechnungsgrundlagen, Stufe 2: die Bewertung).

Knoten: system/zielsystem
"""

from __future__ import annotations

import re
from types import MappingProxyType
from typing import Callable, List, Mapping

from rechner_pipeline.zielsystem.bewertung import Vorgangsregeln
from rechner_pipeline.zielsystem.rechnungsgrundlagen import Parametersatz
from rechner_pipeline.zielsystem.version import VERTRAG_VERSION, vertraeglich, zerlege
from rechner_pipeline.zielsystem.vertrag import FAEHIGKEITEN, PROTOKOLL_JE_FAEHIGKEIT, Zielsystem

__all__ = [
    "PRUEFUNG_JE_FAEHIGKEIT", "pruefe", "pruefe_bewertung", "pruefe_rechnungsgrundlagen",
]

_NAME = re.compile(r"^[a-z][a-z0-9_]*$")


def _ausnahme(exc: BaseException) -> str:
    return f"{type(exc).__name__}: {exc}"


def pruefe_rechnungsgrundlagen(umsetzung: object) -> List[str]:
    """Was das Protokoll ``Rechnungsgrundlagen`` in Worten verlangt: ein
    Produkt mindestens, je Produkt ein Parametersatz mit eindeutigen
    Feldern, dessen Defaults Felder sind, ``KeyError`` fuer ein unbekanntes
    Produkt, Tafelnamen als frozenset von str, ``ValueError`` fuer eine
    leere Alterstafel und fuer einen leeren Tafelspeicher (A-054, H1)."""
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
    for aufruf, text in (
            (lambda: umsetzung.pruefe_alterstafel("leer", {}), "pruefe_alterstafel('leer', {})"),  # type: ignore[attr-defined]
            (lambda: umsetzung.tafeln_lesen(""), "tafeln_lesen('')")):  # type: ignore[attr-defined]
        try:
            aufruf()
        except ValueError:
            pass
        except Exception as exc:  # noqa: BLE001
            befunde.append(f"{text} wirft {_ausnahme(exc)}, erwartet ValueError")
        else:
            befunde.append(f"{text} geht durch, erwartet ValueError")
    return befunde


def pruefe_bewertung(umsetzung: object) -> List[str]:
    """Was das Protokoll ``Bewertung`` in Worten verlangt, ohne Wissen
    ueber das Zielsystem: Vorgangsregeln mit Rang je Art (eindeutig),
    einem Verfahren Teilkuendigung unter den Verfahren und mindestens
    einem Umfang; ``ValueError`` fuer einen unbekannten Umfang; eine
    Schicht traegt nie vor ihrer Verankerung und ohne Schicht nie; ein
    Vertrag ohne Felder ist keiner (``TypeError``)."""
    befunde: List[str] = []
    try:
        regeln = umsetzung.vorgangsregeln()  # type: ignore[attr-defined]
    except Exception as exc:  # noqa: BLE001
        befunde.append(f"vorgangsregeln() wirft {_ausnahme(exc)}")
        regeln = None
    if regeln is not None and not isinstance(regeln, Vorgangsregeln):
        befunde.append(f"vorgangsregeln() liefert {type(regeln).__name__}, erwartet Vorgangsregeln")
        regeln = None
    if regeln is not None:
        raenge = list(regeln.rang.values())
        if (not raenge or not all(isinstance(a, str) for a in regeln.rang)
                or not all(isinstance(r, int) for r in raenge) or len(set(raenge)) != len(raenge)):
            befunde.append(f"vorgangsregeln().rang {dict(regeln.rang)!r}: erwartet Art -> eindeutiger Rang")
        if regeln.teilkuendigung not in regeln.verfahren:
            befunde.append(
                f"vorgangsregeln(): teilkuendigung {regeln.teilkuendigung!r} ist keines der "
                f"Verfahren {list(regeln.verfahren)}")
        if not regeln.umfaenge:
            befunde.append("vorgangsregeln(): keine Umfaenge der Teilkuendigung")
        else:
            try:
                umsetzung.tku_umfang(regeln.verfahren[0], "kein_umfang")  # type: ignore[attr-defined]
            except ValueError:
                pass
            except Exception as exc:  # noqa: BLE001
                befunde.append(f"tku_umfang(.., 'kein_umfang') wirft {_ausnahme(exc)}, erwartet ValueError")
            else:
                befunde.append("tku_umfang(.., 'kein_umfang') liefert etwas, erwartet ValueError")
    try:
        if umsetzung.schicht_traegt(None, 0) is not False:  # type: ignore[attr-defined]
            befunde.append("schicht_traegt(None, 0) ist nicht False")
        if umsetzung.ab_verankerung(5, 4) is not False:  # type: ignore[attr-defined]
            befunde.append("ab_verankerung(5, 4) ist nicht False: vor der Verankerung traegt nichts")
        if umsetzung.ab_verankerung(5, 5) is not True:  # type: ignore[attr-defined]
            befunde.append("ab_verankerung(5, 5) ist nicht True: ab dem Verankerungsmonat traegt die Schicht")
    except Exception as exc:  # noqa: BLE001
        befunde.append(f"schicht_traegt/ab_verankerung wirft {_ausnahme(exc)}")
    try:
        umsetzung.vertrag({}, gamma1_uebernehmen=False, stoab_je_baustein=False)  # type: ignore[attr-defined]
    except TypeError:
        pass
    except Exception as exc:  # noqa: BLE001
        befunde.append(f"vertrag({{}}) wirft {_ausnahme(exc)}, erwartet TypeError")
    else:
        befunde.append("vertrag({}) liefert etwas, erwartet TypeError")
    return befunde


#: Faehigkeit -> Pruefung ueber die Form des Protokolls hinaus.
PRUEFUNG_JE_FAEHIGKEIT: Mapping[str, Callable[[object], List[str]]] = MappingProxyType({
    "rechnungsgrundlagen": pruefe_rechnungsgrundlagen,
    "bewertung": pruefe_bewertung,
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
