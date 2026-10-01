"""Die Tarifregeln einer Generation, wie die Spez sie fuehrt — EINE Tuer.

Invariante (Entscheid des Maintainers 2026-10-01, ADR-024, Nachtrag): Die
Regeln eines uebernommenen Tarifs stehen EINMAL, belegt — A-Box, daraus die
Spez —, und jedes Kommando der Bestandsstrecke rechnet mit genau dieser
Fassung. Kein Kommando rechnet mit einer Vorgabe, die niemand belegt hat.

Vorher nahmen Uebernahme, Verankerung, aktuarieller Test, Migrations-
controlling und Fuehrungsprobe dieselben Regeln als Schalter am Aufruf
(``--red-verfahren``, ``--stoab-je-baustein``, ``--scheiben-mit-gamma1``,
``--tku-umfang``, ``--erhoehungssatz``, ``--dk-stichtag``,
``--formfunktion``/``--fenster``), mit der Regel des eigenen Geschaefts als
Vorgabe. Ein vergessener Schalter rechnete still die PLV-Regel, und dieselbe
Tatsache musste an fuenf Kommandos gleich eingetippt werden — stiller
Default und Zweitwissen in einem.

Jetzt bezieht jedes dieser Kommandos die Regeln ueber
:func:`tarifregeln_der_spez` aus der Spez, die es ohnehin ueber den EINEN
Lader liest; fehlt eine, verweigert es mit Ausweg. Die alten Schalter
entfallen und melden sich sprechend (:func:`verweigere_entfallene_schalter`)
— ein Schalter, der die belegte Regel ueberstimmen koennte, waere wieder
Zweitwissen.

Was bewusst Schalter bleibt, ist keine Regel des Tarifs oder der Quelle,
sondern eine Arbeitsannahme des Laufs (``--red-anteil-kandidat``) oder eine
registrierte Eingabe (``--red-anteile-datei``, ``--anker-erwartungswerte``).

Knoten: klv
"""

from __future__ import annotations

import argparse
from dataclasses import dataclass, field
from typing import Any, Dict, Optional

from rechner_pipeline.ontologie.tbox import (
    BLOCK_TITEL,
    GENERATIONS_BLOECKE,
    TARIFWERK_MERKMALE,
    bereich_text,
    tarifregeln_luecken,
    wert_im_bereich,
)


class TarifregelnFehler(ValueError):
    """Die Spez fuehrt die Tarifregeln einer Bestandsmigration nicht belegt."""


@dataclass(frozen=True)
class Tarifregeln:
    """Die belegten Regeln einer Generation — Tarifwerk und Quellverfahren.

    ``tarifwerk`` traegt die vier Merkmale unter den Namen der Bestand-Config
    (``bestand.config.TarifGeneration.tarifwerk()``): nach ihnen FUEHRT das
    Ziel den Vertrag. ``quellverfahren`` sagt, wie die Quelle verfuhr: die
    Lesart einer gelieferten Absetzung (``red_verfahren``, nicht dasselbe
    wie das des Tarifwerks), Dynamiksatz, Stichtag ihres Deckungskapitals
    und die Ausgestaltung der Korrekturschicht.
    """

    generation: str
    tarifwerk: Dict[str, Any] = field(default_factory=dict)
    quellverfahren: Dict[str, Any] = field(default_factory=dict)

    # -- Tarifwerk (Fuehrung) ------------------------------------------------
    @property
    def scheiben_mit_gamma1(self) -> bool:
        return bool(self.tarifwerk["scheiben_mit_gamma1"])

    @property
    def stoab_je_baustein(self) -> bool:
        return bool(self.tarifwerk["stoab_je_baustein"])

    @property
    def red_verfahren(self) -> str:
        """Verfahren der Herabsetzung des TARIFS (Fuehrung)."""
        return str(self.tarifwerk["red_verfahren"])

    @property
    def tku_umfang(self) -> str:
        return str(self.tarifwerk["tku_umfang"])

    # -- Quellverfahren (Lesart der Lieferung, Migration) --------------------
    @property
    def quell_red_verfahren(self) -> str:
        """Wie die Quelle eine gelieferte Absetzung gemeint hat."""
        return str(self.quellverfahren["red_verfahren"])

    @property
    def erhoehungssatz(self) -> Optional[float]:
        """Der belegte Dynamiksatz der Quelle; None = nicht belegt (der Tarif
        kennt keine planmaessige Erhoehung, P-Q3 hat es als erhoben
        gesehen) — dann zerlegt die Strecke je Vertrag aus dem Beitrag."""
        wert = self.quellverfahren.get("erhoehungssatz")
        return None if wert is None else float(wert)

    @property
    def dk_stichtag(self) -> str:
        return str(self.quellverfahren["dk_stichtag"])

    @property
    def formfunktion(self) -> str:
        return str(self.quellverfahren["formfunktion"])

    @property
    def fenster(self) -> Optional[int]:
        wert = self.quellverfahren.get("fenster")
        return None if wert is None else int(wert)

    def als_beleg(self) -> Dict[str, Any]:
        """Die Regeln, mit denen gerechnet wurde, fuer den Beleg eines Laufs."""
        return {"generation": self.generation,
                "tarifwerk": dict(sorted(self.tarifwerk.items())),
                "quellverfahren": dict(sorted(self.quellverfahren.items()))}


def tarifregeln_der_spez(spez: Any) -> Tarifregeln:
    """Die Tarifregeln aus einer (ueber den Lader gelesenen) Spez.

    Verweigert (:class:`TarifregelnFehler`), wenn ein Pflichtmerkmal einer
    Bestandsmigration fehlt (:data:`tbox.BESTAND_PFLICHT`), ein Merkmal
    unbekannt ist oder ausserhalb seines Wertebereichs liegt — dieselbe
    Regel, mit der P-Q3 die A-Box im Scope ``bestand`` haelt
    (:func:`tbox.tarifregeln_luecken`). Eine Vorgabe gibt es nicht.
    """
    belegt = {block: dict(getattr(spez, block) or {}) for block in GENERATIONS_BLOECKE}
    befunde = []
    for block, bereiche in GENERATIONS_BLOECKE.items():
        for merkmal, wert in sorted(belegt[block].items()):
            if merkmal not in bereiche:
                befunde.append(f"{block}.{merkmal} ist kein Merkmal des "
                               f"{BLOCK_TITEL[block]}s (bekannt: {list(bereiche)})")
            elif not wert_im_bereich(wert, bereiche[merkmal]):
                befunde.append(f"{block}.{merkmal} = {wert!r} liegt nicht im "
                               f"Wertebereich {bereich_text(bereiche[merkmal])}")
    befunde.extend(tarifregeln_luecken(belegt))
    if befunde:
        raise TarifregelnFehler(
            f"Spez {spez.generation}: Tarifregeln der Bestandsmigration nicht "
            "vollstaendig belegt — " + "; ".join(befunde) + ". Die "
            "Bestandsstrecke rechnet nur mit den belegten Regeln des "
            "uebernommenen Tarifs; kein Schalter und keine Vorgabe des eigenen "
            "Geschaefts ersetzt sie. Ausweg: Tarifwerk und Quellverfahren in "
            "der A-Box belegen (aus Bedingungswerk und Tarifmeldung, Skill "
            "extrahiere-quellfragment), Gate P-Q3 im Scope bestand, Spez neu "
            "erzeugen (spez.erzeugen).")
    return Tarifregeln(
        generation=str(spez.generation),
        tarifwerk={m: belegt["tarifwerk"][m] for m in TARIFWERK_MERKMALE},
        quellverfahren=dict(sorted(belegt["quellverfahren"].items())),
    )


#: Die entfallenen Schalter der Bestandsstrecke -> der Abschnitt der Spez, in
#: dem die Regel jetzt steht. Ein Aufruf mit einem davon wird verweigert,
#: nicht still ignoriert und nicht als Uebersteuerung angenommen.
ENTFALLENE_SCHALTER: Dict[str, str] = {
    "--red-verfahren": "tarifwerk.red_verfahren (Fuehrung) und "
                       "quellverfahren.red_verfahren (Lesart der Lieferung)",
    "--scheiben-mit-gamma1": "tarifwerk.scheiben_mit_gamma1",
    "--stoab-je-baustein": "tarifwerk.stoab_je_baustein",
    "--tku-umfang": "tarifwerk.tku_umfang",
    "--erhoehungssatz": "quellverfahren.erhoehungssatz",
    "--dk-stichtag": "quellverfahren.dk_stichtag",
    "--formfunktion": "quellverfahren.formfunktion",
    "--fenster": "quellverfahren.fenster",
}


def entfallen_text(schalter: str) -> str:
    return (
        f"{schalter} entfaellt: die Regel steht jetzt in der Spez der "
        f"Generation, Abschnitt {ENTFALLENE_SCHALTER[schalter]} — belegt in "
        "der A-Box, nicht am Aufruf (ADR-024, Nachtrag). Ein Schalter, der "
        "die belegte Regel ueberstimmen koennte, waere Zweitwissen; eine "
        "andere Regel heisst: in der A-Box belegen, P-Q3, Spez neu erzeugen.")


class _Entfallen(argparse.Action):
    def __call__(self, parser, namespace, values, option_string=None):
        parser.error(entfallen_text(str(option_string)))


def verweigere_entfallene_schalter(parser: argparse.ArgumentParser) -> None:
    """Die entfallenen Schalter am Parser eines Kommandos sprechend verweigern.

    Entschieden gegen den nackten argparse-Fehler ("unrecognized
    arguments"): Die Schalter stehen in Laufnotizen, Skills und Aufrufen
    frueherer Faelle; wer einen davon tippt, soll erfahren, wo die Regel
    jetzt steht und wie man sie aendert. Die Meldung verweigert — sie
    nimmt den Wert nicht an. Exit 2 wie jeder Aufruffehler.
    """
    for schalter in ENTFALLENE_SCHALTER:
        parser.add_argument(schalter, nargs="?", action=_Entfallen,
                            default=argparse.SUPPRESS, help=argparse.SUPPRESS)
