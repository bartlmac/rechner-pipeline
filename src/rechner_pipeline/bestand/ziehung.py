"""Die Ziehung: was in der simulierten Welt geschieht, als Ereignisliste (ADR-031).

Bis ADR-031 zog die Ereignis-Engine (``bestand.ereignisse``) je Vertragsjahr
aus ihren Stroemen und buchte im selben Schritt mit Betraegen aus dem Kern.
Ziehen und Buchen sind hier getrennt: Dieses Modul (Ebene 4, Vorzeige-
Werkzeug) zieht und liefert eine :class:`Ereignisliste`; die Buchung
(``bestand.ereignisse``, Ebene 3) wendet sie mit Betraegen aus dem Kern an.
Was zwischen beiden liegt, ist genau ein Datentyp.

Die Ziehung braucht keinen Rechenwert des Kerns. Ob gezogen wird, haengt
am Zustand des Vertrags (beitragsfrei oder nicht), an seinen Laufzeiten,
am Tarifwerk-Schalter ``red_verfahren``, an den Erfahrungsannahmen und
fuer den Tod an der Rechnungsgrundlage ``qx`` der Tafel
(:func:`rechner_pipeline.kern.tafeln.basis`, dieselbe Basis, die der
Rechenkern des Vertrags traegt). Fuer die BU an den Uebergangswahrschein-
lichkeiten des Produkts, transformiert durch die Annahmen
(:func:`bu_uebergang`). Kein Betrag, keine Reserve, kein Beitrag.

Die Ziehung ist bitgleich zur Engine vor ADR-031: dieselben Stroeme
(Register ``bestand.zufallsstroeme``), dieselben Seeds
``SeedSequence([seed, STROM, police_id])``, dieselbe feste Draw-
Reihenfolge je Vertragsjahr (Tod; beitragspflichtig: Storno solange
``j+1 < n``, Beitragsfreistellung solange ``j+1 < t``; Herabsetzung aus
ihrem Strom, nur ohne Freistellung, solange ``j+1 < t`` und nur in einem
Tarif, der sie kennt; Teilkuendigung aus ihrem Strom solange ``j+1 < n``;
dynamische Erhoehung solange ``j+1 < t``, nie im Jahr der Freistellung
und nie danach). Eine Rate von 0 verbraucht ihren Draw (Common Random
Numbers). Die Ziehung endet mit dem Tod oder dem Storno; der Ablauf ist
kein gezogenes Ereignis, ihn bucht die Fuehrung aus den Vertragsdaten.

Die Liste traegt je Zeile Police, laufende Nummer (die Reihenfolge der
Ziehung), Vertragsjahr, Ereignis, Wirkungstag und die gezogenen Parameter:
den fortgefuehrten Anteil und das Verfahren einer Herabsetzung oder
Teilkuendigung, den Erhoehungssatz einer dynamischen Erhoehung. Den
Ledger-Code eines Vorgangs bestimmt die Buchung aus dem Verfahren
(``models.bestand.reduktion_ereignis``), wie vor ADR-031.

Knoten: klv, bu
"""

from __future__ import annotations

import datetime as _dt
from typing import Any, Dict, List, Mapping, NamedTuple, Optional

import numpy as np
import pandas as pd

from rechner_pipeline.bestand.config import BestandConfig
from rechner_pipeline.bestand.zufallsstroeme import STROEME
from rechner_pipeline.kern import tafeln
from rechner_pipeline.kern.beitragsreduktion import TEILKUENDIGUNG
from rechner_pipeline.models.bestand import (
    STAMM_SPALTEN,
    bu_model_point_kwargs,
    model_point_kwargs,
)

#: SeedSequence-Konstante: separates event streams from the generator's
#: generation streams ([seed, gen_index]) — never reuse for other purposes.
#: Separation assumptions (SeedSequence normalizes trailing zeros, so
#: [seed, X] == [seed, X, 0]): police_id must be > 0 (enforced in
#: ``ereignisse.fortschreiben``; the generator issues >= 10_000_001) and
#: gen_index stays small — a third stream family needs a NEW distinct constant.
EREIGNIS_STREAM = STROEME["ereignis"]  # Register: bestand.zufallsstroeme
#: EIGENER Substrom der Herabsetzung. Die feste Draw-Reihenfolge des
#: Hauptstroms ist der Grund, warum Laeufe verschiedener Configs
#: pfadweise vergleichbar sind — ein neuer Draw in ihr haette JEDEN
#: bestehenden Bestand verschoben, obwohl sich fachlich nichts aendert.
HERABSETZUNG_STREAM = STROEME["herabsetzung"]  # Register: bestand.zufallsstroeme
#: EIGENER Substrom der Teilkuendigung (eigener Geschaeftsvorfall TKU seit
#: dem Entscheid des Maintainers 2026-10-01) — aus demselben Grund.
TEILKUENDIGUNG_STREAM = STROEME["teilkuendigung"]  # Register: bestand.zufallsstroeme

#: Die Ereignisse der Liste, einzeln benannt. Die Codes sind die des
#: Ledgers (``models.bestand.EREIGNIS_VALUES``); hier stehen sie als Namen,
#: damit die Buchung nach ihnen verzweigt, ohne ein Literal zu nennen.
TOD = "TOD"
STO = "STO"
PEX = "PEX"
ERH = "ERH"
RED = "RED"
TKU = "TKU"
INV = "INV"
REA = "REA"

#: Schema der Ereignisliste (Spalte, dtype).
EREIGNISLISTE_SPALTEN = (
    ("police_id", "int64"),
    # Reihenfolge der Ziehung je Police (1, 2, ...): Die Buchung wendet die
    # Ereignisse eines Vertrags genau in dieser Reihenfolge an.
    ("lfd", "int64"),
    ("vertragsjahr", "int64"),       # gebuchter Jahrestag (vollendete Jahre)
    ("ereignis", "object"),
    ("wirkungstag", "datetime64[ns]"),
    # Herabsetzung/Teilkuendigung: fortgefuehrter Anteil; Erhoehung: Satz
    # der Erhoehung (Anteil der gefuehrten Summe); sonst NaN.
    ("anteil", "float64"),
    # Herabsetzung/Teilkuendigung: das Verfahren (prospektiv, mit_abzug,
    # teilkuendigung); sonst leer.
    ("verfahren", "object"),
)
EREIGNISLISTE_NAMES = tuple(name for name, _ in EREIGNISLISTE_SPALTEN)
#: Anteil und Verfahren eines Ereignisses, das keine traegt (Tod, Storno,
#: Beitragsfreistellung, BU-Uebergaenge; die Erhoehung traegt einen Satz,
#: aber kein Verfahren).
OHNE_ANTEIL = float("nan")
OHNE_VERFAHREN = ""


class EreignisError(ValueError):
    """Raised when the portfolio and config do not fit the simulation.

    Der eine Fehler von Ziehung und Buchung (``bestand.ereignisse`` fuehrt
    ihn unter demselben Namen): Was die Welt nicht ziehen kann, kann die
    Fuehrung nicht buchen.
    """


class Ereignisliste(NamedTuple):
    """Was die Welt bis zum Horizont geschehen laesst: die Zugaenge (neue
    Vertraege als POL-Basiszeilen, Schema ``STAMM_SPALTEN``) und die
    gezogenen Ereignisse aller Vertraege (Schema
    :data:`EREIGNISLISTE_SPALTEN`). Die Buchung braucht nichts weiter."""

    zugaenge: pd.DataFrame
    ereignisse: pd.DataFrame


def leere_ereignisse() -> pd.DataFrame:
    return pd.DataFrame({name: pd.Series(dtype=dtype) for name, dtype in EREIGNISLISTE_SPALTEN})


def leere_zugaenge() -> pd.DataFrame:
    return pd.DataFrame({name: pd.Series(dtype=dtype) for name, dtype in STAMM_SPALTEN})


def _add_years(d: _dt.date, years: int) -> _dt.date:
    return _dt.date(d.year + years, d.month, 1)


def _vertragsjahr(beginn: _dt.date, datum: _dt.date) -> int:
    monate = (datum.year - beginn.year) * 12 + (datum.month - beginn.month)
    return max(0, monate // 12)


def zugangslage(row: Mapping[str, Any]) -> tuple:
    """(erstes zu simulierendes Vertragsjahr, Zustand beim Zugang, Jahr des
    Zustandswechsels) — dieselbe Lesart wie ``ereignisse._zugangslage``:
    ein uebernommener Vertrag tritt mit seinem Alter und Zustand ein, die
    Jahre davor gehoeren dem abgebenden Unternehmen."""
    beginn = pd.Timestamp(row["insurance_start"]).date()
    zugang = pd.Timestamp(row["bestandszugang"]).date()
    ab_jahr = _vertragsjahr(beginn, zugang)
    zustand = str(row.get("status_code", "POL"))
    seit = _vertragsjahr(beginn, pd.Timestamp(row["status_date"]).date())
    return ab_jahr, zustand, seit


def _eintrag(
    police_id: int, lfd: int, jahr: int, start: _dt.date, ereignis: str,
    anteil: float, verfahren: str,
) -> Dict[str, Any]:
    """Ein Eintrag der Liste. Anteil und Verfahren werden immer genannt
    (``nan`` und leer, wo das Ereignis keine traegt) — keine stille Vorgabe
    fuer eine Regelgroesse (Pruefrunde I, I14)."""
    return {
        "police_id": police_id,
        "lfd": lfd,
        "vertragsjahr": jahr,
        "ereignis": ereignis,
        "wirkungstag": pd.Timestamp(_add_years(start, jahr)),
        "anteil": float(anteil),
        "verfahren": verfahren,
    }


def ziehe_vertrag(
    row: Mapping[str, Any],
    generation_fields: Mapping[str, Any],
    annahmen,
    seed: int,
    bis: _dt.date,
    ab_jahr: int = 0,
    pex_jahr: Optional[int] = None,
    *,
    tarifwerk: Mapping[str, Any],
) -> List[Dict[str, Any]]:
    """Die Ereignisse EINES KLV-Vertrags bis ``bis``, in Zugreihenfolge.

    ``ab_jahr`` ist das erste zu simulierende Vertragsjahr, ``pex_jahr``
    das Jahr einer beim abgebenden Unternehmen geschehenen Beitrags-
    freistellung (sie wird nicht noch einmal gezogen). ``tarifwerk`` sind
    die Schalter der Generation; gebraucht wird ``red_verfahren``.
    """
    police_id = int(row["police_id"])
    start = pd.Timestamp(row["insurance_start"]).date()
    n = int(row["duration"])
    t = int(row["premium_duration"])
    x = int(row["entry_age"])
    # Die Rechnungsgrundlage des Vertrags: dieselbe Tafelbasis, die sein
    # Rechenkern traegt (``KLV(mp).basis``), ohne den Kern zu bauen.
    kw = model_point_kwargs(row, generation_fields)
    basis = tafeln.basis(str(kw["sex"]), str(kw["tafel"]))
    # Der uebernommene Tarif (``red_verfahren = teilkuendigung``) kennt
    # keine Beitragsherabsetzung (Entscheid des Maintainers 2026-10-01).
    kennt_herabsetzung = str(tarifwerk["red_verfahren"]) != TEILKUENDIGUNG

    rng = np.random.Generator(
        np.random.PCG64(np.random.SeedSequence([seed, EREIGNIS_STREAM, police_id]))
    )
    rng_red = np.random.Generator(
        np.random.PCG64(np.random.SeedSequence([seed, HERABSETZUNG_STREAM, police_id]))
    )
    rng_tk = np.random.Generator(
        np.random.PCG64(np.random.SeedSequence([seed, TEILKUENDIGUNG_STREAM, police_id]))
    )
    aus: List[Dict[str, Any]] = []

    def zug(jahr: int, ereignis: str, anteil: float, verfahren: str) -> None:
        aus.append(_eintrag(police_id, len(aus) + 1, jahr, start, ereignis, anteil, verfahren))

    beitragsfrei_ab: Optional[int] = pex_jahr
    for j in range(ab_jahr, n):
        if _add_years(start, j + 1) > bis:
            break
        # Feste Draw-Reihenfolge je Jahr (Raten sind nur Schwellen, siehe
        # Modul-Docstring): eine Rate von 0 verbraucht ihren Draw trotzdem.
        # 1. Tod im Vertragsjahr j: Erfahrungsannahme auf der Tafel-qx
        #    erster Ordnung. Bei b = 0 wird die Tafel gar nicht angefasst.
        qx_erste_ordnung = basis.qx_at(x + j) if annahmen.tod.b else 0.0
        if rng.random() < annahmen.tod(qx_erste_ordnung):
            zug(j + 1, TOD, OHNE_ANTEIL, OHNE_VERFAHREN)
            return aus
        if beitragsfrei_ab is None:
            # 2. Storno (nur beitragspflichtig, nicht im Ablaufjahr):
            if j + 1 < n and rng.random() < annahmen.storno(0.0):
                zug(j + 1, STO, OHNE_ANTEIL, OHNE_VERFAHREN)
                return aus
            # 3. Beitragsfreistellung (nur solange Beitraege laufen):
            if j + 1 < t and rng.random() < annahmen.beitragsfreistellung(0.0):
                beitragsfrei_ab = j + 1
                zug(j + 1, PEX, OHNE_ANTEIL, OHNE_VERFAHREN)
        if beitragsfrei_ab is None:
            # 4. Beitragsherabsetzung aus ihrem eigenen Strom: nur ohne
            #    Freistellung, nur solange Beitraege laufen, nur in einem
            #    Tarif, der sie kennt. Die Ziehung steht HINTER der
            #    Jahresbedingung (Kurzschluss), chronologisch je Vertragsjahr.
            if (kennt_herabsetzung and (j + 1 < t)
                    and rng_red.random() < annahmen.herabsetzung(0.0)):
                zug(j + 1, RED, float(annahmen.red_anteil), str(tarifwerk["red_verfahren"]))
        # 4b. Teilkuendigung aus ihrem eigenen Strom: in jeder Generation,
        #    in jedem Vertragsjahr vor dem Ablauf, auch nach Freistellung.
        if (j + 1 < n) and rng_tk.random() < annahmen.teilkuendigung(0.0):
            zug(j + 1, TKU, float(annahmen.tk_anteil), TEILKUENDIGUNG)
        if beitragsfrei_ab is None:
            # 5. Dynamische Erhoehung (nur beitragspflichtig, solange
            #    Beitraege laufen): der Satz bezieht sich auf die gefuehrte
            #    Summe NACH den Vorgaengen des Jahres.
            if j + 1 < t and rng.random() < annahmen.erhoehung(0.0):
                zug(j + 1, ERH, float(annahmen.erh_prozent), OHNE_VERFAHREN)
    return aus


def bu_uebergang(produkt, annahmen):
    """Übergangsfunktion des BU-Zustandsprozesses auf Erfahrungsannahmen.

    Legt die Erfahrungsschicht (3. Ordnung) über die vier
    Ausscheideordnungen des Produkts: jede Übergangswahrscheinlichkeit
    erster Ordnung wird durch ihre :class:`~rechner_pipeline.bestand.config.Annahme`
    transformiert. Die Ziehung der Fortschreibung nutzt genau diese
    Funktion — sie ist damit auch der Ansatzpunkt, um die simulierte
    Zustandsverteilung gegen ein Modell derselben Ordnung zu prüfen
    (statt gegen die Bewertungsgrundlage erster Ordnung).
    """
    from rechner_pipeline.kern.produkte.bu import AKTIV, BU_ZUSTAND, TOT

    zuordnung = {
        (AKTIV, BU_ZUSTAND): annahmen.invalidisierung,
        (AKTIV, TOT): annahmen.aktivensterblichkeit,
        (BU_ZUSTAND, AKTIV): annahmen.reaktivierung,
        (BU_ZUSTAND, TOT): annahmen.invalidensterblichkeit,
    }

    def uebergang(von: str, nach: str, alter: int, dauer: int) -> float:
        annahme = zuordnung.get((von, nach))
        if annahme is None:
            return 0.0
        return annahme(produkt._uebergang(von, nach, alter, dauer))

    return uebergang


def _pruefe_wegzuege(
    police_id: int, zustand: str, alter: int, dauer: int, summe: float
) -> None:
    """Markov-Bedingung nach der Transformation: die Wegzuege aus einem
    Zustand duerfen sich nicht auf mehr als 1 summieren (dieselbe Grenze
    wie ``kern.zustandsmodell.Zustandsmodell._wegzuege``; die Ziehung
    wuerde das letzte Risiko sonst still stutzen)."""
    if summe > 1.0 + 1e-12:
        raise EreignisError(
            f"police {police_id}: transformierte Wegzuege aus {zustand} "
            f"(Alter {alter}, Dauer {dauer}) summieren auf {summe} > 1 — "
            "die Erfahrungsannahmen heben die Uebergangswahrscheinlichkeiten "
            "ueber die Markov-Grenze (b zu gross)"
        )


def ziehe_bu_vertrag(
    row: Mapping[str, Any],
    generation_fields: Mapping[str, Any],
    annahmen,
    seed: int,
    bis: _dt.date,
    ab_jahr: int = 0,
    bu_seit: Optional[int] = None,
) -> List[Dict[str, Any]]:
    """Die Ereignisse EINES BU-Vertrags bis ``bis`` (Invalidisierung,
    Reaktivierung, Tod), in Zugreihenfolge.

    Draw-Contract wie vor ADR-031: EIN Uniform-Draw je simuliertem
    Vertragsjahr, Schwellen in fester Reihenfolge — aus ``aktiv`` erst
    Invalidisierung, dann Tod; aus ``bu`` erst Reaktivierung, dann Tod.
    Die Uebergangswahrscheinlichkeiten kommen aus den Rechnungsgrundlagen
    des Produkts, transformiert durch die Annahmen; die BU-Dauer wird bei
    der Select-Periode gekappt.
    """
    from rechner_pipeline.kern.produkte.bu import (
        AKTIV,
        BU,
        BU_ZUSTAND,
        TOT as TOT_ZUSTAND,
        BUModelPoint,
    )

    police_id = int(row["police_id"])
    start = pd.Timestamp(row["insurance_start"]).date()
    n = int(row["duration"])
    x = int(row["entry_age"])
    produkt = BU(BUModelPoint(**bu_model_point_kwargs(row, generation_fields)))
    uebergang = bu_uebergang(produkt, annahmen)
    max_dauer = produkt.modell.max_dauer
    rng = np.random.Generator(
        np.random.PCG64(np.random.SeedSequence([seed, EREIGNIS_STREAM, police_id]))
    )
    aus: List[Dict[str, Any]] = []

    def zug(jahr: int, ereignis: str) -> None:
        aus.append(_eintrag(police_id, len(aus) + 1, jahr, start, ereignis,
                            OHNE_ANTEIL, OHNE_VERFAHREN))

    zustand = BU_ZUSTAND if bu_seit is not None else AKTIV
    dauer = min(ab_jahr - bu_seit, max_dauer) if bu_seit is not None else 0
    for j in range(ab_jahr, n):
        if _add_years(start, j + 1) > bis:
            break
        alter = x + j
        u = rng.random()
        if zustand == AKTIV:
            p_inv = uebergang(AKTIV, BU_ZUSTAND, alter, 0)
            p_tod = uebergang(AKTIV, TOT_ZUSTAND, alter, 0)
            _pruefe_wegzuege(police_id, AKTIV, alter, 0, p_inv + p_tod)
            if u < p_inv:
                zug(j + 1, INV)
                zustand, dauer = BU_ZUSTAND, 0
            elif u < p_inv + p_tod:
                zug(j + 1, TOD)
                return aus
        else:
            p_rea = uebergang(BU_ZUSTAND, AKTIV, alter, dauer)
            p_tod = uebergang(BU_ZUSTAND, TOT_ZUSTAND, alter, dauer)
            _pruefe_wegzuege(police_id, BU_ZUSTAND, alter, dauer, p_rea + p_tod)
            if u < p_rea:
                zug(j + 1, REA)
                zustand, dauer = AKTIV, 0
            elif u < p_rea + p_tod:
                zug(j + 1, TOD)
                return aus
            else:
                dauer = min(dauer + 1, max_dauer)
    return aus


def ziehe(
    gesamt: pd.DataFrame,
    config: BestandConfig,
    bis: _dt.date,
    *,
    merkmale: Optional[pd.DataFrame] = None,
) -> pd.DataFrame:
    """Die Ereignisse ALLER Vertraege in ``gesamt`` (Basisbestand plus
    Zugaenge, POL-Basiszeilen) bis ``bis`` als Tabelle nach
    :data:`EREIGNISLISTE_SPALTEN`, in Stammreihenfolge und je Police in
    Zugreihenfolge.

    Die Eingaben sind geprueft (``ereignisse.fortschreiben`` haelt die
    Waechter VOR der Ziehung); hier wird nur gezogen. Die Rechnungs-
    grundlagen je Police kommen aus derselben Aufloesung wie in der
    Bewertung (``auswertung.grundlagen_je_police``: Zelle statt
    Generationsrumpf, wo eine Generation Zellen fuehrt).
    """
    from rechner_pipeline.bestand.auswertung import grundlagen_je_police

    bis = pd.Timestamp(bis).date()
    grundlagen = grundlagen_je_police(config, merkmale)
    bu_generationen = {
        g.name: g.bu_generation_fields() for g in config.generationen if g.produkt == "bu"
    }
    tarifwerk_je_generation = {g.name: g.tarifwerk() for g in config.generationen}
    zeilen: List[Dict[str, Any]] = []
    for row in gesamt.to_dict("records"):
        name = str(row["tarif_generation"])
        ab_jahr, zustand, seit = zugangslage(row)
        try:
            if str(row.get("produkt", "klv")) == "bu":
                zeilen.extend(ziehe_bu_vertrag(
                    row, bu_generationen[name], config.annahmen, config.seed, bis,
                    ab_jahr=ab_jahr, bu_seit=seit if zustand == "BU" else None,
                ))
            else:
                zeilen.extend(ziehe_vertrag(
                    row, grundlagen(int(row["police_id"]), name), config.annahmen,
                    config.seed, bis, ab_jahr=ab_jahr,
                    pex_jahr=seit if zustand == "PEX" else None,
                    tarifwerk=tarifwerk_je_generation[name],
                ))
        except EreignisError:
            raise
        except Exception as exc:
            # Dieselbe Einordnung wie in der Buchung: Der Vertrag, nicht die
            # Zeile im Stapel, benennt den Fehler.
            raise EreignisError(
                f"police {row['police_id']}: {type(exc).__name__}: {exc}"
            ) from exc
    return als_tabelle(zeilen)


def als_tabelle(zeilen: List[Mapping[str, Any]]) -> pd.DataFrame:
    """Eine Liste von Eintraegen (wie :func:`ziehe_vertrag` sie liefert)
    als Tabelle nach :data:`EREIGNISLISTE_SPALTEN`."""
    if not zeilen:
        return leere_ereignisse()
    df = pd.DataFrame(list(zeilen))[list(EREIGNISLISTE_NAMES)]
    return df.astype(dict(EREIGNISLISTE_SPALTEN)).reset_index(drop=True)


def neuzugaenge(config: BestandConfig, von: _dt.date, bis: _dt.date) -> pd.DataFrame:
    """Der jaehrliche Zugangsstrom der Simulation (``bestand.generator``):
    neue Vertraege mit Beginn in ``[von, bis]``. Der eine Weg, auf dem die
    Buchung (Ebene 3) den Erzeuger erreicht — ueber die Ziehung."""
    from rechner_pipeline.bestand.generator import neuzugaenge as _neuzugaenge

    return _neuzugaenge(config, von, bis)
