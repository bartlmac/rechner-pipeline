"""``migrationssuite_lauf`` — das Migrationscontrolling ueber den Fall fahren.

Produzent, kein Gate: Er baut je Vertrag einen Pruefauftrag, laesst
:func:`rechner_pipeline.qa.migrationssuite.pruefe_bestand` rechnen und
schreibt das zurueckgegebene Dict UNVERAENDERT als JSON. Geprueft wird
es von Gate A-M4 (``gates.abnahmebericht --suite``), das die Bindungen
nachrechnet, statt ihnen zu glauben.

Er liegt in ``gates/``, nicht in ``bestand/``: Nur diese Schicht darf
``fall``, ``spez`` und ``qa`` zugleich importieren.

**Die Spaltenbindung ist ein Parameter, keine Annahme.** Welche Spalte
eines Abzugs das Deckungskapital traegt, weiss nur der Fall. Die
Vorgaben passen zur Baldrian-Lieferung; jede andere Lieferung setzt sie
um. Sie im Code festzuschreiben hiesse, eine Lieferungskonvention zur
Systemeigenschaft zu machen.

**Was der Lauf NICHT tut: er glaettet nichts.** Eine Herabsetzung mit
geliefertem Anteil wird seit Kern 3.1.0 als geteilter Vertrag
fortgeschrieben (``--red-verfahren`` ist die dokumentierte Eigenschaft
des Quellsystems, Vorgabe: Zielverfahren prospektiv); OHNE Anteil
bleibt der Folgestichtag eine ausgewiesene Pruefluecke, und der
Bestands-Scope von A-M4 duldet keine — der Lauf endet dann mit einem
Befund statt mit einer Zahl, die aussieht wie geprueft.

Knoten: klv
"""

from __future__ import annotations

import argparse
import csv
import datetime as dt
import hashlib
import json
import sys
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

from rechner_pipeline import fall as fall_mod
from rechner_pipeline.bestand.parquet_io import read_portfolio
from rechner_pipeline.gates._provenienz import systemstand
from rechner_pipeline.models.bestand import model_point_kwargs
from rechner_pipeline.kern.beitragsreduktion import PROSPEKTIV, VERFAHREN
from rechner_pipeline.qa.migrationssuite import (
    GeVoErwartung,
    VertragsPruefung,
    pruefe_bestand,
)
from rechner_pipeline.spez.validierung import lade_spez

#: Vorgabe-Spaltennamen der Lieferung. Sie passen zur
#: Baldrian-Lieferung; jede andere setzt sie ueber die Schalter um.
VORGABE = {
    "police": "POLNR",
    "deckkap": "DECKKAP",
    "jbrutto": "JBRUTTO",
    "beginn": "BEGINN",
    "gevo": "GEVO",
    "datum": "DATUM",
    "betrag": "BETRAG",
    "param": "PARAM",
}


def _lies_csv(fall: Path, name: str) -> List[Dict[str, str]]:
    """Eine REGISTRIERTE Lieferdatei lesen (ADR-002: kein freier Pfad)."""
    with fall_mod.eingang_datei(fall, name).open(encoding="utf-8") as datei:
        return list(csv.DictReader(datei, delimiter=";"))


def _parse(wert: str) -> dt.date:
    for fmt in ("%d.%m.%Y", "%Y-%m-%d"):
        try:
            return dt.datetime.strptime(str(wert).strip(), fmt).date()
        except ValueError:
            continue
    raise SystemExit(f"kein bekanntes Datumsformat: {wert!r}")


def _monate(von: dt.date, bis: dt.date) -> int:
    return (bis.year - von.year) * 12 + (bis.month - von.month) - (
        1 if bis.day < von.day else 0)


def _zelle(spez, auspraegungen: Dict[str, str]):
    gesucht = {k: str(v).strip().lower() for k, v in auspraegungen.items() if v}
    treffer = [z for z in spez.zellen if z.auspraegungen == gesucht]
    if not treffer:
        raise SystemExit(
            f"keine Spez-Zelle fuer {gesucht!r} — vorhanden sind "
            f"{[z.auspraegungen for z in spez.zellen]}")
    return treffer[0]


def auspraegungen_je_police(
    spez, zeilen: List[Dict[str, Any]]
) -> Dict[str, Dict[str, str]]:
    """Die Zellwahl-Auspraegungen je Police aus den transformierten Zeilen.

    Welche Dimensionen es gibt, sagen die Auspraegungs-Schluessel der
    Spez-Zellen; die Werte je Vertrag tragen die transformierten Zeilen
    (``gates.transformation_anwenden --zeilen``) unter genau diesen
    Feldnamen. Eine Zeile ohne Dimensionswert waere eine Police, deren
    Zelle sich nicht bestimmen laesst — harter Fehler, kein stilles
    Zurueckfallen auf irgendeine Zelle.
    """
    dimensionen = sorted({k for z in spez.zellen for k in z.auspraegungen})
    aus: Dict[str, Dict[str, str]] = {}
    for zeile in zeilen:
        police = str(zeile.get("police_id", "")).strip()
        if not police:
            raise SystemExit(
                "transformierte Zeile ohne police_id — die Zeilenliste "
                "gehoert aus gates.transformation_anwenden --zeilen")
        fehlend = [d for d in dimensionen if not str(zeile.get(d, "")).strip()]
        if fehlend:
            raise SystemExit(
                f"Police {police}: transformierte Zeile traegt keine "
                f"Auspraegung fuer {fehlend} — ohne sie ist keine "
                "Spez-Zelle bestimmbar")
        aus[police] = {d: str(zeile[d]) for d in dimensionen}
    return aus


def beitragsfrei_seit_jahr_je_police(
    vorgeschichte: List[Dict[str, str]], bestand, *, spalten: Dict[str, str],
) -> Dict[str, int]:
    """Anfangszustand aus der Vorgeschichte: PEX-Vertragsjahr je Police.

    Eine Beitragsfreistellung VOR dem Migrationsstichtag ist kein GeVo
    des Pruefzeitraums, sondern der Zustand, in dem der Vertrag
    uebernommen wird (``VertragsPruefung.beitragsfrei_seit_jahr``). Sie
    wirkt am Vertragsjahrestag; ein PEX-Datum abseits des Jahrestags
    ist eine Lieferungs-Inkonsistenz und faellt hart, statt still
    gerundet zu werden.
    """
    s = spalten
    beginne = {
        str(z["police_id"]): z["insurance_start"].date()
        for _, z in bestand.iterrows()
    }
    aus: Dict[str, int] = {}
    for zeile in vorgeschichte:
        if zeile[s["gevo"]] != "PEX":
            continue
        police = str(zeile[s["police"]])
        beginn = beginne.get(police)
        if beginn is None:
            # Vorgeschichte zu einer Police, die nicht uebernommen wurde
            # (z. B. verworfene Zeile) — hier kein Urteil, die
            # Mengenpruefung der Suite meldet Bestandsluecken selbst.
            continue
        monate = _monate(beginn, _parse(zeile[s["datum"]]))
        if monate % 12:
            raise SystemExit(
                f"Police {police}: PEX der Vorgeschichte bei Monat {monate} "
                "liegt nicht auf dem Vertragsjahrestag — Beitragsfreistellung "
                "wirkt am Jahrestag (Lieferung klaeren, nicht runden)")
        if police in aus:
            raise SystemExit(
                f"Police {police}: zwei PEX in der Vorgeschichte — eine "
                "zweite Beitragsfreistellung gibt es nicht")
        aus[police] = monate // 12
    return aus


def _serienzustand(
    police: str,
    folge: List[Tuple[str, int, str]],
    mp_felder: Dict[str, Any],
    *,
    erlsumme: float,
    erhoehungssatz: Optional[float],
    red_anteile: Dict[str, float],
    red_anteile_je_datum: Dict[str, Dict[str, float]],
    jbrutto: float = 0.0,
    red_anteil_kandidaten: Tuple[float, ...] = (),
    scheiben_mit_gamma1: bool = False,
) -> Dict[str, Any]:
    """Anfangszustand einer Ereignis-SERIE (Lieferung-2-Regelfall).

    Terminale Beitragsfreistellung: Gesamtsummen-Inversion — die
    beitragsfreien Faktoren aller Bausteine desselben Ablauftermins
    sind identisch, die Zerlegung ist fuer den beitragsfreien Wert
    unerheblich (Ein-Punkt-Weg, Beschluss des Maintainers im zweiten
    Lauf; die Erhoehungen der Vorgeschichte stecken in der gelieferten
    beitragsfreien Gesamtsumme). Sonst IST-Struktur aus dem belegten
    Dynamiksatz. Ein fehlender Satz ist ein harter Abbruch (betraefe
    jede Serien-Police), ein fehlender Absetzungs-Anteil eine
    Warnung je Police — es sei denn, eine BELEGTE Kandidatenmenge ist
    uebergeben: dann bestimmt die Beitragsgleichung den Anteil
    (bestimme_serie_mit_kandidaten; eindeutiger Treffer oder benannter
    Fehler, kein Raten).
    """
    from rechner_pipeline.bestand.migrationszugang import (
        MigrationszugangFehler,
        bestimme_serie_mit_kandidaten,
        leite_pex_ursprungssumme_ab,
        leite_serie_aus_satz_ab,
    )

    arten = [a for a, _, _ in folge]
    if "PEX" in arten:
        if arten.count("PEX") > 1 or arten[-1] != "PEX":
            raise SystemExit(
                f"Police {police}: Beitragsfreistellung ist in der "
                f"Vorgeschichte nicht terminal ({arten}) — die Quelle "
                "stellt danach nichts mehr um; Lieferung klaeren")
        pex_jahr = folge[-1][1]
        return {
            "beitragsfrei_seit_jahr": pex_jahr,
            "sum_insured": leite_pex_ursprungssumme_ab(
                mp_felder, pex_jahr=pex_jahr, vs_bfr=erlsumme),
        }
    if erhoehungssatz is None:
        raise SystemExit(
            f"Police {police}: mehrere Alt-Ereignisse sind ohne "
            "--erhoehungssatz unterbestimmt — den Dynamiksatz als "
            "registrierte Auskunft der Quelle beschaffen")
    ereignisse: List[Tuple[str, int, Optional[float]]] = []
    for art, jahr, datum in folge:
        anteil = None
        if art == "RED":
            anteil = red_anteile_je_datum.get(police, {}).get(
                datum, red_anteile.get(police))
        ereignisse.append((art, jahr, anteil))
    offene_red = any(
        art == "RED" and anteil is None for art, _, anteil in ereignisse)
    if offene_red and red_anteil_kandidaten:
        serie = bestimme_serie_mit_kandidaten(
            mp_felder, ereignisse=ereignisse, erlsumme=erlsumme,
            satz=erhoehungssatz, jbrutto=jbrutto,
            kandidaten=red_anteil_kandidaten,
            scheiben_mit_gamma1=scheiben_mit_gamma1)
    else:
        serie = leite_serie_aus_satz_ab(
            ereignisse=ereignisse, erlsumme=erlsumme, satz=erhoehungssatz)
    zustand: Dict[str, Any] = {
        "sum_insured": serie.grundsumme,
        "scheiben": serie.scheiben,
    }
    if serie.absetzungen:
        # Beleg fuer Vorlage und Protokoll; kein Konsument rechnet damit.
        zustand["alt_absetzungen"] = serie.absetzungen
    return zustand


def anfangszustaende_je_police(
    spez,
    zeilen: List[Dict[str, Any]],
    vorgeschichte: List[Dict[str, str]],
    bestand,
    *,
    spalten: Dict[str, str],
    red_verfahren: str,
    red_anteile: Optional[Dict[str, float]] = None,
    auspraegungen: Optional[Dict[str, Dict[str, str]]] = None,
    erhoehungssatz: Optional[float] = None,
    anker: Optional[Dict[str, Tuple[int, float]]] = None,
    red_anteile_je_datum: Optional[Dict[str, Dict[str, float]]] = None,
    red_anteil_kandidaten: Tuple[float, ...] = (),
    scheiben_mit_gamma1: bool = False,
) -> Tuple[Dict[str, Dict[str, Any]], List[str]]:
    """Vorgeschichts-Welten je Police ableiten — auch SERIEN.

    Einzel-Ereignisse (genau ein PEX, ERH oder RED) laufen unveraendert
    ueber die Lauf-1-Ableitungen. MEHRERE Ereignisse je Police
    (Lieferung-2-Regelfall: jaehrliche Dynamiken, dazwischen
    Herabsetzungen, terminale Beitragsfreistellung) laufen ueber
    :func:`_serienzustand`: terminale PEX als Gesamtsummen-Inversion,
    sonst IST-Struktur aus dem belegten Dynamiksatz
    (``migrationszugang.leite_serie_aus_satz_ab``);
    ``red_anteile_je_datum`` traegt nachgelieferte Anteile je Ereignis
    (POLNR;GEVO;DATUM;ANTEIL), ``red_anteile`` bleibt der
    Pauschalwert je Police.

    Der Stamm fuehrt die AKTUELLE Gesamtsumme; die Bewertung der
    Vorgeschichts-Welten braucht den URSPRUNGS-Modellpunkt. Je Police
    mit Alt-Erhoehung bzw. Alt-Absetzung liefert diese Funktion den
    Anfangszustand (``scheiben`` bzw. ``reduktion``) UND die
    zugehoerige Ursprungs- bzw. Grundsumme (``sum_insured``), abgeleitet
    aus den transformierten Zeilen (ERLSUMME/JBRUTTO) nach den
    Fall-Ableitungsregeln der Uebernahmestrecke. Ein nachgelieferter
    Anteil (``red_anteile``) ersetzt die Beitragsgleichung.

    Nicht bestimmbare Policen (z. B. Beitragszahlung am Stichtag
    beendet) bekommen KEINEN Zustand und werden als Warnung
    zurueckgegeben — der Wertvergleich der Suite zeigt sie dann rot,
    statt dass ein geratener Zustand still richtig aussieht. PEX
    behandelt :func:`beitragsfrei_seit_jahr_je_police`.
    """
    from rechner_pipeline.bestand.migrationszugang import (
        MigrationszugangFehler,
        leite_absetzung_ab,
        leite_erhoehung_ab,
        leite_erhoehung_aus_satz_ab,
        leite_pex_ursprungssumme_ab,
        leite_ursprungssumme_ab,
        kalibriere_absetzung_aus_dk,
    )

    s = spalten
    red_anteile = red_anteile or {}
    beginne = {
        str(z["police_id"]): z["insurance_start"].date()
        for _, z in bestand.iterrows()
    }
    stammzeilen = {str(z["police_id"]): z for _, z in bestand.iterrows()}
    zeilen_je_police = {str(z.get("police_id", "")): z for z in zeilen}

    ereignisse: Dict[str, List[Dict[str, str]]] = {}
    for zeile in vorgeschichte:
        if zeile[s["gevo"]] in ("PEX", "ERH", "RED"):
            ereignisse.setdefault(str(zeile[s["police"]]), []).append(zeile)

    zustaende: Dict[str, Dict[str, Any]] = {}
    warnungen: List[str] = []
    for police in sorted(ereignisse):
        beginn = beginne.get(police)
        if beginn is None:
            continue
        # Chronologie mit Jahrestags-Wache je Ereignis: die gelieferten
        # Daten muessen auf dem Vertragsjahresgitter liegen.
        folge: List[Tuple[str, int, Optional[str]]] = []
        for ereignis in sorted(
                ereignisse[police], key=lambda e: _parse(e[s["datum"]])):
            art_e = ereignis[s["gevo"]]
            monate_e = _monate(beginn, _parse(ereignis[s["datum"]]))
            if monate_e % 12:
                raise SystemExit(
                    f"Police {police}: {art_e} der Vorgeschichte bei Monat "
                    f"{monate_e} liegt nicht auf dem Vertragsjahrestag — "
                    "Lieferung klaeren, nicht runden")
            folge.append((art_e, monate_e // 12, ereignis[s["datum"]]))

        transformiert = zeilen_je_police.get(police)
        if transformiert is None:
            raise SystemExit(
                f"Police {police}: keine transformierte Zeile — der "
                "Anfangszustand ist nicht ableitbar")
        erlsumme = float(transformiert["sum_insured"])
        jbrutto = float(transformiert.get("brutto_jahresbeitrag") or 0.0)
        zelle = _zelle(spez, (auspraegungen or {}).get(police, {}))
        mp_felder = model_point_kwargs(
            stammzeilen[police], dict(zelle.model_point))

        if len(folge) > 1:
            try:
                zustaende[police] = _serienzustand(
                    police, folge, mp_felder,
                    erlsumme=erlsumme, erhoehungssatz=erhoehungssatz,
                    red_anteile=red_anteile,
                    red_anteile_je_datum=red_anteile_je_datum or {},
                    jbrutto=jbrutto,
                    red_anteil_kandidaten=red_anteil_kandidaten,
                    scheiben_mit_gamma1=scheiben_mit_gamma1)
            except MigrationszugangFehler as exc:
                warnungen.append(f"Police {police} (Serie): {exc}")
            continue

        art = folge[0][0]
        jahr = folge[0][1]

        try:
            if art == "PEX":
                # Der Abzug fuehrt hier die BEITRAGSFREIE Summe; der Kern
                # rechnet aus der Ursprungssumme und wandelt selbst um.
                zustaende[police] = {
                    "beitragsfrei_seit_jahr": jahr,
                    "sum_insured": leite_pex_ursprungssumme_ab(
                        mp_felder, pex_jahr=jahr, vs_bfr=erlsumme),
                }
            elif art == "ERH":
                if erhoehungssatz is not None:
                    # Belegter Dynamiksatz: Zerlegung ohne Beitrag —
                    # traegt auch Vertraege ohne laufenden Beitrag.
                    erh = leite_erhoehung_aus_satz_ab(
                        jahr=jahr, erlsumme=erlsumme, satz=erhoehungssatz)
                else:
                    erh = leite_erhoehung_ab(
                        mp_felder, jahr=jahr, erlsumme=erlsumme,
                        jbrutto=jbrutto)
                zustaende[police] = {
                    "scheiben": ((jahr, erh.erhoehungssumme),),
                    "sum_insured": erh.grundsumme,
                }
            else:
                anteil = red_anteile.get(police)
                kalibriert = False
                if anteil is not None:
                    vs_alt = leite_ursprungssumme_ab(
                        mp_felder, jahr=jahr, erlsumme=erlsumme,
                        anteil=anteil, verfahren=red_verfahren)
                elif jbrutto > 0.0:
                    absetzung = leite_absetzung_ab(
                        mp_felder, jahr=jahr, erlsumme=erlsumme,
                        jbrutto=jbrutto, verfahren=red_verfahren)
                    anteil, vs_alt = absetzung.anteil, absetzung.vs_alt
                elif (anker or {}).get(police):
                    # Rueckfallweg: aus dem gelieferten Wert kalibrieren.
                    # Der Vergleich an DIESEM Punkt wird dadurch
                    # konstruktionsbedingt und traegt keine Aussage mehr.
                    monate_dk, dk_ist = (anker or {})[police]
                    vs_alt, anteil = kalibriere_absetzung_aus_dk(
                        mp_felder, jahr=jahr, erlsumme=erlsumme,
                        dk_ist=dk_ist, monate_dk=monate_dk,
                        verfahren=red_verfahren)
                    kalibriert = True
                else:
                    raise MigrationszugangFehler(
                        "JBRUTTO <= 0 und kein Anteil nachgeliefert: der "
                        "fortgefuehrte Anteil ist nicht bestimmbar — "
                        "nachliefern lassen oder einen Ankerwert uebergeben"
                    )
                zustaende[police] = {
                    "reduktion": (jahr, anteil),
                    "sum_insured": vs_alt,
                    "kalibriert_aus_anker": kalibriert,
                }
        except MigrationszugangFehler as exc:
            warnungen.append(f"Police {police} ({art}, Jahr {jahr}): {exc}")
    return zustaende, warnungen


def baue_auftraege(
    bestand, spez, abzug_1, abzug_2, protokoll, *,
    stichtag_1: dt.date, stichtag_2: dt.date, spalten: Dict[str, str],
    auspraegungen: Optional[Dict[str, Dict[str, str]]] = None,
    beitragsfrei_seit: Optional[Dict[str, int]] = None,
    anfangszustaende: Optional[Dict[str, Dict[str, Any]]] = None,
    scheiben_mit_gamma1: bool = False,
    stoab_je_baustein: bool = False,
) -> List[VertragsPruefung]:
    """Je Vertrag genau einen Pruefauftrag."""
    s = spalten
    ab1 = {z[s["police"]]: z for z in abzug_1}
    ab2 = {z[s["police"]]: z for z in abzug_2}
    gevos: Dict[str, List[Dict[str, str]]] = {}
    for z in protokoll:
        gevos.setdefault(z[s["police"]], []).append(z)

    mehrzellig = len(spez.zellen) > 1
    if mehrzellig and auspraegungen is None:
        raise SystemExit(
            f"Spez traegt {len(spez.zellen)} Zellen — ohne die "
            "transformierten Zeilen (--zeilen) ist die Zellwahl je Police "
            "nicht bestimmbar")
    felder = dict(_zelle(spez, {}).model_point) if not mehrzellig else None

    auftraege: List[VertragsPruefung] = []
    for _, zeile in bestand.iterrows():
        police = str(zeile["police_id"])
        if police not in ab1:
            raise SystemExit(
                f"Police {police} steht im Bestand, aber nicht im Abzug zum "
                "Migrationsstichtag — die Pruefmenge waere keine Bestandsmenge")
        beginn = zeile["insurance_start"].date()
        if felder is not None:
            generation = felder
        else:
            if police not in auspraegungen:
                raise SystemExit(
                    f"Police {police}: keine transformierte Zeile — die "
                    "Zellwahl ist nicht bestimmbar")
            generation = dict(
                _zelle(spez, auspraegungen[police]).model_point)

        vorfaelle = []
        for g in sorted(gevos.get(police, []), key=lambda z: _parse(z[s["datum"]])):
            betrag = g.get(s["betrag"])
            anteil = g.get(s["param"])
            vorfaelle.append(GeVoErwartung(
                art=g[s["gevo"]],
                monate=_monate(beginn, _parse(g[s["datum"]])),
                betrag_erwartet=float(betrag) if betrag else None,
                anteil=float(anteil) if anteil else None,
            ))

        mp_kwargs = model_point_kwargs(zeile, generation)
        zustand = (anfangszustaende or {}).get(police, {})
        if "sum_insured" in zustand:
            # Der Stamm fuehrt die aktuelle Gesamtsumme; die Bewertung
            # der Vorgeschichts-Welt rechnet auf dem Ursprungs- bzw.
            # Grund-Modellpunkt (Fall-Ableitungsregel).
            mp_kwargs["sum_insured"] = float(zustand["sum_insured"])
        auftraege.append(VertragsPruefung(
            police_id=police,
            model_point=mp_kwargs,
            monate_stichtag_1=_monate(beginn, stichtag_1),
            monate_stichtag_2=_monate(beginn, stichtag_2),
            dk_erwartet_1=float(ab1[police][s["deckkap"]]),
            dk_erwartet_2=(float(ab2[police][s["deckkap"]])
                           if police in ab2 else None),
            bjb_erwartet_1=(float(ab1[police][s["jbrutto"]])
                            if ab1[police].get(s["jbrutto"]) else None),
            gevos=tuple(vorfaelle),
            beitragsfrei_seit_jahr=zustand.get(
                "beitragsfrei_seit_jahr",
                (beitragsfrei_seit or {}).get(police)),
            scheiben=tuple(zustand.get("scheiben", ())),
            scheiben_mit_gamma1=scheiben_mit_gamma1,
            stoab_je_baustein=stoab_je_baustein,
            reduktion=zustand.get("reduktion"),
        ))
    return auftraege


def main(argv: Optional[List[str]] = None) -> int:
    p = argparse.ArgumentParser(
        prog="python -m rechner_pipeline.gates.migrationssuite_lauf",
        description="Migrationscontrolling ueber den Fall fahren "
                    "(Produzent, kein Gate).")
    p.add_argument("--fall", required=True)
    p.add_argument("--generation", required=True,
                   help="Knoten-Id der Tarifgeneration, z. B. klv/tg2015")
    p.add_argument("--abzug-1", dest="abzug_1", required=True,
                   help="REGISTRIERTER Abzug zum Migrationsstichtag")
    p.add_argument("--abzug-2", dest="abzug_2", required=True,
                   help="REGISTRIERTER Abzug zum Folgestichtag")
    p.add_argument("--gevo-protokoll", dest="protokoll", required=True,
                   help="REGISTRIERTES Geschaeftsvorfall-Protokoll")
    p.add_argument("--bestand", required=True,
                   help="transformierter Bestand (Parquet), von P-B1 geprueft")
    p.add_argument("--stichtag-1", dest="stichtag_1", required=True)
    p.add_argument("--stichtag-2", dest="stichtag_2", required=True)
    p.add_argument("--zeilen", default=None,
                   help="transformierte Zeilen (gates.transformation_anwenden "
                        "--zeilen) — Pflicht, sobald die Spez mehr als eine "
                        "Zelle traegt (Zellwahl je Police)")
    p.add_argument("--vorgeschichte", default=None,
                   help="REGISTRIERTE Metadatenliste der Geschaeftsvorfaelle "
                        "vor dem Stichtag (POLNR;GEVO;DATUM) — traegt die "
                        "Anfangszustaende (PEX-Jahr, Alt-Scheiben, "
                        "Alt-Absetzung) je Police")
    p.add_argument("--red-anteile-datei", dest="red_anteile_datei",
                   default=None, metavar="REGISTRIERTE_DATEI",
                   help="REGISTRIERTE Nachlieferung der fortgefuehrten "
                        "Beitragsanteile (POLNR;GEVO;DATUM;ANTEIL)")
    p.add_argument("--anker-erwartungswerte", dest="anker_quelle",
                   default=None, metavar="REGISTRIERTE_DATEI",
                   help="REGISTRIERTE Erwartungswerte am Verankerungs"
                        "zeitpunkt. Aus ihnen wird der Zustand einer "
                        "Absetzung kalibriert, deren Beitragsgleichung "
                        "entfaellt — eine ANDERE Quelle als die hier "
                        "geprueften Abzugswerte, der Vergleich bleibt also "
                        "unabhaengig.")
    p.add_argument("--red-anteil", dest="red_anteile", action="append",
                   default=[], metavar="POLNR=ANTEIL",
                   help="nachgelieferter fortgefuehrter Beitragsanteil einer "
                        "Alt-Absetzung, deren Beitragsgleichung entfaellt "
                        "(wiederholbar)")
    p.add_argument("--red-anteil-kandidat", dest="red_anteil_kandidaten",
                   action="append", type=float, default=[],
                   metavar="ANTEIL",
                   help="BELEGTER Tarif-Kandidat des Herabsetzungsanteils "
                        "(wiederholbar); offene Anteile in Ereignis-Serien "
                        "werden dann ueber die Beitragsgleichung bestimmt "
                        "(eindeutiger Treffer oder benannter Fehler) — "
                        "siehe aktuartest_lauf.")
    p.add_argument(
        "--scheiben-mit-gamma1", dest="scheiben_mit_gamma1",
        action="store_true",
        help="Erhoehungsscheiben mit voller Beitragsformel (gamma1) — "
             "Tarifwerks-Eigenschaft der Lieferung, siehe "
             "aktuartest_lauf.")
    p.add_argument(
        "--stoab-je-baustein", dest="stoab_je_baustein",
        action="store_true",
        help="Stornoabschlag-Grenzen je Baustein statt je Vertrag — "
             "Tarifwerks-Eigenschaft der Lieferung, siehe "
             "aktuartest_lauf.")
    p.add_argument("--erhoehungssatz", dest="erhoehungssatz", type=float,
                   default=None, metavar="SATZ",
                   help="BELEGTER Dynamiksatz der Alt-Erhoehungen (Tarifwerk: "
                        "S' = e * S^ges); ohne ihn wird je Vertrag aus dem "
                        "Jahresbeitrag zerlegt")
    p.add_argument("--red-verfahren", dest="red_verfahren",
                   default=PROSPEKTIV, choices=sorted(VERFAHREN),
                   help="Verfahren der Beitragsherabsetzung (Eigenschaft "
                        "des Migrationsfalls; Vorgabe: Zielverfahren "
                        "prospektiv)")
    p.add_argument("--repo-root", dest="repo_root", default=".")
    p.add_argument("--out", default=None)
    for name, vorgabe in VORGABE.items():
        p.add_argument(f"--spalte-{name}", dest=f"spalte_{name}",
                       default=vorgabe,
                       help=f"Spaltenname der Lieferung (Vorgabe: {vorgabe})")
    args = p.parse_args(argv)

    fall = Path(args.fall).resolve()
    if not (fall / "fall.json").is_file():
        print(f"Kein Fall-Arbeitsbereich: {fall}", file=sys.stderr)
        return 2

    spalten = {n: getattr(args, f"spalte_{n}") for n in VORGABE}
    bestand_pfad = Path(args.bestand)
    bestand = read_portfolio(bestand_pfad)
    spez = lade_spez(fall, args.generation)
    abzug_1 = _lies_csv(fall, args.abzug_1)

    auspraegungen = None
    if args.zeilen is not None:
        zeilen = json.loads(Path(args.zeilen).read_text(encoding="utf-8"))
        if not isinstance(zeilen, list):
            print(f"{args.zeilen}: erwartet wird die Zeilenliste aus "
                  "gates.transformation_anwenden --zeilen", file=sys.stderr)
            return 2
        auspraegungen = auspraegungen_je_police(spez, zeilen)

    beitragsfrei_seit = None
    anfangszustaende = None
    if args.vorgeschichte is not None:
        vorgeschichte = _lies_csv(fall, args.vorgeschichte)
        beitragsfrei_seit = beitragsfrei_seit_jahr_je_police(
            vorgeschichte, bestand, spalten=spalten)
        red_anteile: Dict[str, float] = {}
        red_anteile_je_datum: Dict[str, Dict[str, float]] = {}
        if args.red_anteile_datei is not None:
            for zeile in _lies_csv(fall, args.red_anteile_datei):
                if zeile.get("GEVO") == "RED" and zeile.get("ANTEIL"):
                    red_anteile[str(zeile["POLNR"])] = float(zeile["ANTEIL"])
                    if zeile.get("DATUM"):
                        red_anteile_je_datum.setdefault(
                            str(zeile["POLNR"]), {})[str(zeile["DATUM"])] = (
                                float(zeile["ANTEIL"]))
        anker: Dict[str, Any] = {}
        if args.anker_quelle is not None:
            quelle = json.loads(fall_mod.eingang_datei(
                fall, args.anker_quelle).read_text(encoding="utf-8"))
            for eintrag in quelle.get("vertraege", []):
                erster = next(
                    (x for x in (eintrag.get("punkte") or [])
                     if x.get("anlass") == "uebernahme"), None)
                if erster and "kVx_MRV" in (erster.get("erwartet") or {}):
                    anker[str(eintrag["police_id"])] = (
                        int(erster["monate"]),
                        float(erster["erwartet"]["kVx_MRV"]))
        for eintrag in args.red_anteile:
            police, _, wert = eintrag.partition("=")
            if not police or not wert:
                print(f"--red-anteil {eintrag!r}: erwartet POLNR=ANTEIL",
                      file=sys.stderr)
                return 2
            red_anteile[police.strip()] = float(wert)
        anfangszustaende, zustandswarnungen = anfangszustaende_je_police(
            spez, zeilen if args.zeilen is not None else [],
            vorgeschichte, bestand, spalten=spalten,
            red_verfahren=args.red_verfahren, red_anteile=red_anteile,
            auspraegungen=auspraegungen,
            erhoehungssatz=args.erhoehungssatz, anker=anker,
            red_anteile_je_datum=red_anteile_je_datum,
            red_anteil_kandidaten=tuple(args.red_anteil_kandidaten),
            scheiben_mit_gamma1=args.scheiben_mit_gamma1)
        for w in zustandswarnungen:
            print(f"WARNUNG Anfangszustand nicht ableitbar: {w}",
                  file=sys.stderr)

    auftraege = baue_auftraege(
        bestand,
        spez,
        abzug_1,
        _lies_csv(fall, args.abzug_2),
        _lies_csv(fall, args.protokoll),
        stichtag_1=_parse(args.stichtag_1),
        stichtag_2=_parse(args.stichtag_2),
        spalten=spalten,
        auspraegungen=auspraegungen,
        beitragsfrei_seit=beitragsfrei_seit,
        anfangszustaende=anfangszustaende,
        scheiben_mit_gamma1=args.scheiben_mit_gamma1,
        stoab_je_baustein=args.stoab_je_baustein,
    )

    # Die Pruefmenge wird an der LIEFERUNG gemessen, nicht an sich
    # selbst: erwartete Anzahl ist die Zeilenzahl des Abzugs zum
    # Migrationsstichtag. Scope-Bindung (Stichtage, Bestand-Hash,
    # Systemstand) laeuft durch die validierende Suite-Signatur.
    ergebnis = pruefe_bestand(
        auftraege,
        erwartete_anzahl=len(abzug_1),
        red_verfahren=args.red_verfahren,
        stichtag_1=_parse(args.stichtag_1).isoformat(),
        stichtag_2=_parse(args.stichtag_2).isoformat(),
        bestand_sha256=hashlib.sha256(bestand_pfad.read_bytes()).hexdigest(),
        system=systemstand(Path(args.repo_root).resolve()),
    )

    ziel = Path(args.out) if args.out else (
        fall / "abgeleitet" / "berichte" / "migrationssuite.json")
    ziel.parent.mkdir(parents=True, exist_ok=True)
    with ziel.open("w", encoding="utf-8") as datei:
        json.dump(ergebnis, datei, indent=2, ensure_ascii=False,
                  sort_keys=True, default=str)
        datei.write("\n")

    print(f"Migrationssuite: {ergebnis['anzahl']} Vertraege, "
          f"{ergebnis['bestanden']} bestanden")
    luecken = ergebnis.get("pruefluecken") or []
    if luecken:
        print(f"  {len(luecken)} Pruefluecken — der Bestands-Scope von A-M4 "
              "duldet keine:")
        for l in luecken[:5]:
            print(f"    {str(l)[:140]}")
    print(f"  vollstaendig geprueft: {ergebnis.get('vollstaendig_geprueft')}")
    print(f"  {ziel}")
    return 0


if __name__ == "__main__":  # pragma: no cover
    raise SystemExit(main())
