"""Tagesgranulares Neugeschaeft der Vorzeige (Fachkonzept Tagesbetrieb, Abschnitt 4).

Ein Versicherer verkauft jeden Werktag. Dieses Modul entscheidet
deterministisch, WIE VIELE Vertraege eine Generation an einem Kalendertag
abschliesst und WELCHE — es rechnet nichts Aktuarielles (die Betraege
kommen wie ueberall aus dem Kern), es bestimmt nur den Zugang.

Drei Regeln, alle aus der Config:

* **Jahresziel mit Trend.** Das Ziel des Kalenderjahres J einer
  Generation ist ``neuzugang_pro_jahr * (1 + neuzugang_trend) ** (J -
  gueltig_von.year)``; so schrumpft (oder waechst) das Unternehmen, ohne
  dass jemand jedes Jahr eine Zahl pflegt.
* **Wochentagsgewichte.** Jeder Kalendertag traegt ein Gewicht
  (``[tagesbetrieb] wochentagsgewichte``: Wochenende 0, Montag 1,3, sonst
  1,0). Der Erwartungswert eines Tages ist ``Jahresziel * Gewicht(Tag) /
  Summe der Gewichte des Kalenderjahres`` — die Summe ueber ALLE Tage des
  Jahres, nicht nur die im Verkaufsfenster: Ein Fenster, das mitten im
  Jahr beginnt, traegt anteilig weniger, genau wie beim jaehrlichen
  Erzeuger.
* **Bernoulli-Rest statt Poisson.** Die Zahl eines Tages ist der
  ganzzahlige Anteil des Erwartungswerts plus ein Bernoulli-Zug auf den
  Rest. Das trifft das Jahresziel im Erwartungswert exakt, und ein Tag
  weicht hoechstens um einen Vertrag vom Erwartungswert ab — deutlich
  stetiger als ein Poisson-Zug, wie das Konzept es verlangt.

Determinismus: je (Config-Seed, Generation, Kalendertag) ein eigener
Substream ``SeedSequence([seed, NEUGESCHAEFT_STREAM, hash(name),
tag.toordinal()])``. Die Generation geht ueber ihren NAMEN ein (SHA-256,
auf 32 Bit gekuerzt), nicht ueber ihre Position in der Config: Eine
spaeter eingefuegte Generation — etwa eine uebernommene — darf die
Verkaufstage der anderen nicht verschieben. Der erste Zug entscheidet
den Bernoulli-Rest, danach folgen die Vertragsmerkmale in derselben
Reihenfolge wie beim Batch-Erzeuger
(:func:`rechner_pipeline.bestand.generator._ziehe_attribute`). Ein Tag
ist damit fuer sich reproduzierbar — unabhaengig davon, ob er allein, im
Nachholen oder als Teil eines Jahres erzeugt wird — und kein Tag
verschiebt einen anderen.

Police-Nummern tragen den Verkaufstag: ``(gen_index + 1) * 10_000_000 +
5_000_000 + Fensterjahr * 100_000 + Tag_des_Jahres * 100 + k``. Der
Bereich ab 5 Mio liegt ueber dem Batch (bis 1 Mio) und dem jaehrlichen
Neuzugang (ab 2 Mio); mehr als 99 Vertraege an einem Tag oder ein
Fenster ueber 30 Jahre sind ein harter Fehler, kein stiller Ueberlauf.

Versicherungsbeginn ist der naechste Monatserste NACH dem Verkaufstag
(Konzept, Abschnitt 3): Die Police ist ab dem Verkaufstag policiert, ab
dem Beginn beitragspflichtig. Der Stamm traegt den Beginn als
``bestandszugang`` (Monatserster-Konvention, unveraendert); den
Verkaufstag fuehrt das Tagesjournal.

Knoten: klv, bu
"""

from __future__ import annotations

import datetime as _dt
import hashlib
import math
from functools import lru_cache
from typing import Dict, List, Tuple

import numpy as np
import pandas as pd

from rechner_pipeline.bestand.config import BestandConfig, TarifGeneration
from rechner_pipeline.bestand.generator import _baue_frame, _ziehe_attribute
from rechner_pipeline.models.bestand import STAMM_NAMES, STAMM_SPALTEN, stamm_dtypes

#: SeedSequence-Konstante des Tagesneugeschaefts — getrennt vom Batch
#: ([seed, gen_index]), vom jaehrlichen Neuzugang ([seed, 771177, ...])
#: und von der Ereignis-Engine ([seed, 424242, police_id]).
NEUGESCHAEFT_STREAM = 918273

#: police_id-Offset des Tagesneugeschaefts im Nummernkreis der Generation.
_TAGES_ID_OFFSET = 5_000_000
#: Nummern je Verkaufstag (k = 1..99) und je Fensterjahr.
_JE_TAG = 100
_JE_JAHR = 100_000
#: Obergrenze des Nummernkreises (Generation belegt 10 Mio; der
#: jaehrliche Neuzugang endet vor 8 Mio, das Tagesneugeschaeft ab 5 Mio
#: darf also bis unter 8 Mio reichen).
_ID_GRENZE = 8_000_000


class NeugeschaeftError(ValueError):
    """Config oder Tag passen nicht zum Tagesneugeschaeft (fail-fast)."""


def generationsseed(name: str) -> int:
    """Der Seed-Beitrag einer Generation: ihr Name, nicht ihre Position."""
    return int.from_bytes(hashlib.sha256(name.encode("utf-8")).digest()[:4], "big")


def jahresziel(gen: TarifGeneration, jahr: int) -> float:
    """Das Jahresziel einer Generation fuer das Kalenderjahr ``jahr``.

    Dieselbe Zahl, die der jaehrliche Erzeuger rundet
    (:meth:`~rechner_pipeline.bestand.config.TarifGeneration.jahresziel`)
    — hier unverkuerzt, weil sie auf die Tage verteilt wird.
    """
    return gen.jahresziel(jahr)


@lru_cache(maxsize=None)
def _gewichtssumme(jahr: int, gewichte: Tuple[Tuple[str, float], ...]) -> float:
    """Summe der Wochentagsgewichte ueber alle Kalendertage des Jahres."""
    from rechner_pipeline.bestand.config import WOCHENTAGE

    je_wochentag = dict(gewichte)
    tag = _dt.date(jahr, 1, 1)
    summe = 0.0
    while tag.year == jahr:
        summe += float(je_wochentag[WOCHENTAGE[tag.weekday()]])
        tag += _dt.timedelta(days=1)
    return summe


def gewichtssumme(config: BestandConfig, jahr: int) -> float:
    return _gewichtssumme(
        jahr, tuple(sorted(config.tagesbetrieb.wochentagsgewichte.items()))
    )


def tagesziel(config: BestandConfig, gen: TarifGeneration, tag: _dt.date) -> float:
    """Erwartungswert des Neugeschaefts einer Generation an ``tag``.

    0 ausserhalb des Verkaufsfensters und an Tagen mit Gewicht 0.
    """
    if not gen.gueltig_von <= tag <= gen.gueltig_bis:
        return 0.0
    ziel = jahresziel(gen, tag.year)
    if ziel <= 0.0:
        return 0.0
    gewicht = config.tagesbetrieb.gewicht(tag)
    if gewicht <= 0.0:
        return 0.0
    return ziel * gewicht / gewichtssumme(config, tag.year)


def naechster_monatserster(tag: _dt.date) -> _dt.date:
    """Der erste Tag des auf ``tag`` folgenden Monats (Versicherungsbeginn)."""
    if tag.month == 12:
        return _dt.date(tag.year + 1, 1, 1)
    return _dt.date(tag.year, tag.month + 1, 1)


def _police_ids(gen: TarifGeneration, gen_index: int, tag: _dt.date, anzahl: int) -> np.ndarray:
    fensterjahr = tag.year - gen.gueltig_von.year
    if anzahl >= _JE_TAG:
        raise NeugeschaeftError(
            f"generation {gen.name}: {anzahl} Vertraege am {tag.isoformat()} "
            f"— der Nummernkreis traegt {_JE_TAG - 1} je Tag; das Jahresziel "
            "oder die Wochentagsgewichte sind fuer einen Tagesbetrieb unplausibel"
        )
    basis = (
        (gen_index + 1) * 10_000_000
        + _TAGES_ID_OFFSET
        + fensterjahr * _JE_JAHR
        + tag.timetuple().tm_yday * _JE_TAG
    )
    if basis + _JE_TAG > (gen_index + 1) * 10_000_000 + _ID_GRENZE:
        raise NeugeschaeftError(
            f"generation {gen.name}: Verkaufsfenster ab {gen.gueltig_von.isoformat()} "
            f"reicht im Jahr {tag.year} ueber den Nummernkreis des "
            "Tagesneugeschaefts hinaus (hoechstens 30 Fensterjahre)"
        )
    return basis + np.arange(1, anzahl + 1, dtype=np.int64)


def _leerer_stamm() -> pd.DataFrame:
    return pd.DataFrame({name: pd.Series(dtype=dtype) for name, dtype in STAMM_SPALTEN})


def neugeschaeft_am(config: BestandConfig, tag: _dt.date) -> pd.DataFrame:
    """Die an ``tag`` abgeschlossenen Vertraege aller Generationen (POL-Basiszeilen).

    Reine Funktion von (Config, Kalendertag); das Ergebnis haengt weder
    davon ab, welche Tage vorher erzeugt wurden, noch wann der Aufruf
    stattfindet. Eine ungueltige Config ist ein Fehler, kein leerer Tag.
    """
    fehler = config.validate()
    if fehler:
        raise NeugeschaeftError("Config ungueltig: " + "; ".join(fehler))
    tag = pd.Timestamp(tag).date()
    frames: List[pd.DataFrame] = []
    for idx, gen in enumerate(config.generationen):
        erwartung = tagesziel(config, gen, tag)
        rng = np.random.Generator(np.random.PCG64(np.random.SeedSequence(
            [config.seed, NEUGESCHAEFT_STREAM, generationsseed(gen.name),
             tag.toordinal()]
        )))
        # Der erste Zug ist der Bernoulli-Rest — auch bei Erwartung 0, damit
        # die Merkmalszuege eines Tages nicht davon abhaengen, ob das
        # Jahresziel gerade eine Ganzzahl trifft (Common Random Numbers).
        u = rng.random()
        ganz = int(math.floor(erwartung))
        anzahl = ganz + (1 if u < erwartung - ganz else 0)
        if anzahl == 0:
            continue
        police_ids = _police_ids(gen, idx, tag, anzahl)
        attribute = _ziehe_attribute(gen, rng, anzahl)
        beginn = naechster_monatserster(tag)
        frames.append(_baue_frame(gen, attribute, [beginn] * anzahl, police_ids))
    if not frames:
        return _leerer_stamm()
    df = pd.concat(frames, ignore_index=True)
    df = df[list(STAMM_NAMES)].astype(stamm_dtypes())
    return df.sort_values("police_id", kind="stable").reset_index(drop=True)


def neugeschaeft_zwischen(
    config: BestandConfig, von: _dt.date, bis: _dt.date
) -> pd.DataFrame:
    """Alle Vertraege mit Verkaufstag in ``[von, bis]`` (beide einschliesslich).

    Tag fuer Tag ueber :func:`neugeschaeft_am` — dadurch ist das Ergebnis
    fuer jeden Teilbereich die exakte Teilmenge des groesseren (Praefix-
    und Suffix-Stabilitaet), was der Tageslauf beim Nachholen braucht.
    """
    von, bis = pd.Timestamp(von).date(), pd.Timestamp(bis).date()
    if bis < von:
        raise NeugeschaeftError(
            f"neugeschaeft_zwischen: bis {bis.isoformat()} liegt vor von "
            f"{von.isoformat()} (vertauschte Argumente?)"
        )
    frames = []
    tag = von
    while tag <= bis:
        frame = neugeschaeft_am(config, tag)
        if len(frame):
            frames.append(frame)
        tag += _dt.timedelta(days=1)
    if not frames:
        return _leerer_stamm()
    df = pd.concat(frames, ignore_index=True)
    if df["police_id"].duplicated().any():
        raise NeugeschaeftError("police_id-Kollision im Tagesneugeschaeft")
    return df.sort_values("police_id", kind="stable").reset_index(drop=True)


def verkaufstag(gen: TarifGeneration, gen_index: int, police_id: int) -> _dt.date:
    """Den Verkaufstag aus der Police-Nummer zurueckrechnen (Umkehrung).

    Die Nummer traegt Fensterjahr und Tag des Jahres; das Tagesjournal
    prueft damit, dass eine ZUG-Buchung des Tagesneugeschaefts an dem Tag
    gebucht ist, an dem die Police verkauft wurde.
    """
    rest = int(police_id) - (gen_index + 1) * 10_000_000 - _TAGES_ID_OFFSET
    if not 0 <= rest < _ID_GRENZE - _TAGES_ID_OFFSET:
        raise NeugeschaeftError(
            f"police {police_id} liegt nicht im Nummernkreis des "
            f"Tagesneugeschaefts der Generation {gen.name}"
        )
    fensterjahr, rest = divmod(rest, _JE_JAHR)
    tag_des_jahres, k = divmod(rest, _JE_TAG)
    if k == 0 or tag_des_jahres == 0:
        raise NeugeschaeftError(
            f"police {police_id}: keine Tagesneugeschaefts-Nummer (k={k}, "
            f"Tag {tag_des_jahres})"
        )
    return _dt.date(gen.gueltig_von.year + fensterjahr, 1, 1) + _dt.timedelta(
        days=tag_des_jahres - 1
    )
