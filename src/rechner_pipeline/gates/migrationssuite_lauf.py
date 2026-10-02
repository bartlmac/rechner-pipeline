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
fortgeschrieben (das Verfahren ist die belegte Eigenschaft des
Quellsystems, ``quellverfahren.red_verfahren`` der Spez — ohne Vorgabe,
ADR-024, Nachtrag); OHNE Anteil
bleibt der Folgestichtag eine ausgewiesene Pruefluecke, und der
Bestands-Scope von A-M4 duldet keine — der Lauf endet dann mit einem
Befund statt mit einer Zahl, die aussieht wie geprueft.

Knoten: klv
"""

from __future__ import annotations

import argparse
import csv
import io as _io
import datetime as dt
import hashlib
import json
import math
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

from rechner_pipeline.gates._provenienz import lebendes_repo  # --repo-root (G12)
from rechner_pipeline import fall as fall_mod
from rechner_pipeline.bestand.parquet_io import (
    read_portfolio,
    read_portfolio_aus_bytes,
)
from rechner_pipeline.gates._common import Eingangsbindung
from rechner_pipeline.gates._provenienz import systemstand
from rechner_pipeline.models.bestand import (
    alt_absetzung_ist_teilkuendigung,
    model_point_kwargs,
)
from rechner_pipeline.kern.beitragsreduktion import TEILKUENDIGUNG
from rechner_pipeline.qa.migrationssuite import (
    GeVoErwartung,
    VertragsPruefung,
    pruefe_bestand,
)
from rechner_pipeline.spez.tarifregeln import (
    Tarifregeln,
    TarifregelnFehler,
    tarifregeln_der_spez,
    verweigere_entfallene_schalter,
)
from rechner_pipeline.spez.validierung import (
    lade_spez,
    lade_spez_aus_bytes,
    spez_pfad,
)

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


def _lies_csv(fall: Path, name: str, bindung=None) -> List[Dict[str, str]]:
    """Eine REGISTRIERTE Lieferdatei lesen (ADR-002: kein freier Pfad).

    Mit ``bindung`` GENAU EINMAL gelesen und im Beleg registriert
    (Review T25-05): Diese Zeilen tragen das Urteil, also nennt der Beleg
    ihren Hash.
    """
    pfad = fall_mod.eingang_datei(fall, name)
    if bindung is not None:
        return list(csv.DictReader(
            _io.StringIO(bindung.binde(pfad).text()), delimiter=";"))
    with pfad.open(encoding="utf-8") as datei:
        return list(csv.DictReader(datei, delimiter=";"))


def tarifregeln_des_falls(fall: Path, spez: Any) -> Tarifregeln:
    """Die Tarifregeln, mit denen ein Kommando der Bestandsstrecke rechnet —
    die EINE Stelle, an der Uebernahme, Verankerung, aktuarieller Test,
    Migrationscontrolling und Fuehrungsprobe (und A-M4 fuer sein Soll) sie
    beziehen (Pruefrunde G, ADR-024, vierter Nachtrag).

    Zwei Regeln an einem Ort: Der Fall muss im Scope ``bestand`` stehen (ein
    Tariffall fuehrt keinen Bestand; ADR-024, zweiter Nachtrag, Punkt 2 —
    vorher lief die ganze Strecke im Scope ``tarif`` ohne jede Regelpflicht),
    und die Spez muss die Regeln belegt fuehren
    (:func:`spez.tarifregeln.tarifregeln_der_spez`, dieselbe Regel wie P-Q3
    im Scope ``bestand``). Hier und nicht in ``spez``: Die Schicht ``spez``
    kennt keinen Fall. Kein Schalter schaltet die Regel ab.
    """
    try:
        scope = fall_mod.lade_scope(Path(fall))
    except (fall_mod.FallFehler, OSError) as exc:
        raise TarifregelnFehler(
            f"Fall {fall}: Scope nicht lesbar ({exc}) — die Bestandsstrecke rechnet "
            "nur in einem Fall mit Scope 'bestand' (fall.json)") from exc
    if scope != "bestand":
        raise TarifregelnFehler(
            f"Fall {fall}: Scope {scope!r} — die Bestandsstrecke (Uebernahme, "
            "Verankerung, aktuarieller Test, Migrationscontrolling, Fuehrungsprobe) "
            "rechnet nur in einem Fall mit Scope 'bestand'. Ein Tariffall fuehrt "
            "keinen Bestand, und seine A-Box muss die Tarifregeln nicht tragen "
            "(P-Q3 verlangt sie nur im Scope bestand). Ausweg: die Migration eines "
            "Bestands als eigenen Fall mit --scope bestand anlegen.")
    return tarifregeln_der_spez(spez)


@dataclass(frozen=True)
class Auskuenfte:
    """Die gelesene Auskunft: Anteile, Anteile je Ereignis, Belegblock."""

    #: POLNR -> fortgefuehrter Beitragsanteil (Pauschalwert je Police; bei
    #: mehreren Ereignissen gewinnt die letzte Zeile der Datei).
    anteile: Dict[str, float]
    #: POLNR -> DATUM -> Anteil (nur Zeilen mit Datum).
    je_datum: Dict[str, Dict[str, float]]
    #: ``{name, sha256, bezug}`` — der Block, den der Beleg des Kommandos
    #: unter ``red_anteile_datei`` fuehrt.
    beleg: Dict[str, Any]


def lies_auskuenfte(
    fall: Path, name: str, bindung,
    vorgeschichte: List[Dict[str, str]],
    spalten: Optional[Dict[str, str]] = None,
) -> Auskuenfte:
    """Die Auskunft der Quelle zu den Herabsetzungsanteilen lesen.

    Entscheid des Maintainers (2026-09-30): Eine Auskunft der abgebenden
    Gesellschaft — der fortgefuehrte Beitragsanteil einer Alt-Herabsetzung,
    dessen Beitragsgleichung entfaellt — ist eine REGISTRIERTE Datei im
    Fall, nie ein Kommandozeilenparameter je Police: Die menschlichen
    Gates hashen den Eingang, nicht den Aufruf. Die Datei geht ueber die
    Bindung (genau einmal gelesen, mit ihrem Hash im Beleg); der Beleg
    nennt sie zusaetzlich als ``red_anteile_datei`` mit Name, SHA-256 und
    dem Bezug je Police.

    Format (CSV, Trenner ``;``): ``POLNR;GEVO;DATUM;ANTEIL`` und optional
    ``BEZUG`` — Freitext, woher der Wert stammt (Auskunftsschreiben oder
    Arbeits-Lesart). BEZUG ist rueckwaertskompatibel: Eine Datei ohne die
    Spalte bleibt lesbar, ihr ``bezug`` ist dann leer. Gelesen werden die
    Zeilen mit ``GEVO = RED`` und einem ANTEIL; ohne DATUM gilt der Anteil
    als Pauschalwert der Police.

    Fail-fast statt stillem Verwerfen: Eine Datei, der eine der Spalten
    POLNR, GEVO, ANTEIL fehlt, ohne eine einzige RED-Zeile mit Anteil, mit
    nichtnumerischem Anteil oder mit zwei Zeilen fuer dieselbe Police und
    dasselbe Datum, die sich widersprechen, wird verweigert — sonst sieht
    eine leer gelesene Auskunft aus wie eine gelesene. Eine nicht
    registrierte Datei wird mit dem Ausweg verweigert.

    Block F, Nachbesserung — drei weitere Verweigerungen, alle mit Ausweg:

    * Ein ANTEIL muss endlich sein und echt zwischen 0 und 1 liegen
      (``float()`` liess ``nan`` und ``inf`` durch).
    * Jede RED-Zeile muss einem RED-Ereignis der ``vorgeschichte`` des
      Laufs entsprechen: Police und — wenn die Zeile ein DATUM traegt — das
      Datum, SO GESCHRIEBEN wie in der Vorgeschichte (``_serienzustand``
      schlaegt den Anteil je Datum nach Text nach; ein anderes Format bliebe
      dort still ohne Wirkung). Ohne DATUM genuegt die Police. Eine Zeile
      ohne Ereignis stuende sonst im Beleg mit Hash und Bezug, als haette
      sie getragen.
    * Eine leere POLNR traegt nichts.

    ``spalten`` nennt die Spaltennamen der Vorgeschichte (Vorgabe:
    :data:`VORGABE`); die Auskunft selbst hat feste Spalten.
    """
    try:
        pfad = fall_mod.eingang_datei(fall, name)
    except fall_mod.FallFehler as exc:
        raise SystemExit(
            f"--red-anteile-datei {name!r}: {exc}. Eine Auskunft gilt nur "
            "als registrierte Datei: erst registrieren (python -m "
            "rechner_pipeline.fall registrieren --fall <fall> --datei "
            "<auskunft.csv>), dann --red-anteile-datei <Dateiname>; ein "
            "Anteil je Police am Aufruf wird nicht angenommen") from exc
    gelesen = bindung.binde(pfad)
    sp = spalten or VORGABE
    red_ereignisse: Dict[str, set] = {}
    for ereignis in vorgeschichte:
        if ereignis.get(sp["gevo"]) == "RED":
            red_ereignisse.setdefault(
                str(ereignis[sp["police"]]), set()).add(
                    str(ereignis.get(sp["datum"]) or ""))
    leser = csv.DictReader(_io.StringIO(gelesen.text()), delimiter=";")
    fehlend = [s for s in ("POLNR", "GEVO", "ANTEIL")
               if s not in (leser.fieldnames or [])]
    if fehlend:
        raise SystemExit(
            f"Auskunft {name!r}: Spalte(n) {', '.join(fehlend)} fehlt — "
            "erwartet POLNR;GEVO;DATUM;ANTEIL (optional BEZUG)")
    anteile: Dict[str, float] = {}
    je_datum: Dict[str, Dict[str, float]] = {}
    gesehen: Dict[Tuple[str, str], float] = {}
    bezug: Dict[str, List[str]] = {}
    for zeile in leser:
        if zeile.get("GEVO") != "RED" or not zeile.get("ANTEIL"):
            continue
        police = str(zeile["POLNR"])
        if not police.strip():
            raise SystemExit(
                f"Auskunft {name!r}: eine RED-Zeile mit ANTEIL "
                f"{zeile['ANTEIL']!r} ohne POLNR traegt nichts — die "
                "Auskunft berichtigen und neu registrieren")
        try:
            anteil = float(zeile["ANTEIL"])
        except ValueError:
            raise SystemExit(
                f"Auskunft {name!r}: ANTEIL {zeile['ANTEIL']!r} der Police "
                f"{police} ist keine Zahl") from None
        datum = str(zeile.get("DATUM") or "")
        # Block F, Nachbesserung: ein Anteil ist ein echter Bruchteil des
        # Beitrags. ``float()`` laesst ``nan`` und ``inf`` durch (beide
        # wanderten ungeprueft in den Anfangszustand); 0 waere eine
        # Kuendigung, 1 keine Herabsetzung, 60 ein Prozentwert.
        if not (math.isfinite(anteil) and 0.0 < anteil < 1.0):
            raise SystemExit(
                f"Auskunft {name!r}: Police {police}"
                f"{f' am {datum}' if datum else ''}: ANTEIL "
                f"{zeile['ANTEIL']!r} liegt nicht echt zwischen 0 und 1 "
                "(endlich, als Bruchteil, nicht als Prozent) — die Auskunft "
                "berichtigen und neu registrieren")
        if police not in red_ereignisse or (
                datum and datum not in red_ereignisse[police]):
            wo = (f"Police {police} hat in der Vorgeschichte kein "
                  "RED-Ereignis" if police not in red_ereignisse else
                  f"Police {police} hat in der Vorgeschichte kein "
                  f"RED-Ereignis am {datum} (vorhanden: "
                  f"{', '.join(sorted(d for d in red_ereignisse[police] if d))}"
                  ")")
            raise SystemExit(
                f"Auskunft {name!r}: {wo} — die Zeile (ANTEIL "
                f"{zeile['ANTEIL']!r}) bliebe ohne Wirkung und stuende doch "
                "im Beleg. Police und DATUM so schreiben wie in der "
                "Vorgeschichte, oder die Zeile streichen; die Auskunft "
                "berichtigen und neu registrieren")
        vorher = gesehen.setdefault((police, datum), anteil)
        if vorher != anteil:
            raise SystemExit(
                f"Auskunft {name!r}: Police {police} am {datum!r} mit "
                f"ANTEIL {vorher} und {anteil} — die Zeilen widersprechen "
                "sich; die Auskunft berichtigen und neu registrieren")
        anteile[police] = anteil
        if datum:
            je_datum.setdefault(police, {})[datum] = anteil
        text = (zeile.get("BEZUG") or "").strip()
        if text and text not in bezug.setdefault(police, []):
            bezug[police].append(text)
    if not anteile:
        raise SystemExit(
            f"Auskunft {name!r}: keine RED-Zeile mit ANTEIL — eine Auskunft "
            "ohne Anteil traegt nichts")
    return Auskuenfte(
        anteile=anteile, je_datum=je_datum,
        beleg={"name": name, "sha256": gelesen.sha256,
               "bezug": {p: sorted(t) for p, t in sorted(bezug.items())}})


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


def vorgeschichte_jahrestag_fehler(art: str, beginn: dt.date, datum: dt.date) -> Optional[str]:
    """Die Jahrestags-Konvention eines gelieferten Vorgangs der Vorgeschichte —
    die EINE Stelle (Pruefrunde J, J06) fuer die Uebernahme in JEDEM Modus
    (``gates.bestand_uebernehmen.baue``) und die Pruefstrecke
    (:func:`anfangszustaende_je_police`, :func:`beitragsfrei_seit_jahr_je_police`).

    Ein Vorgang wirkt am Vertragsjahrestag (Tarifplan KLV 7.3; die
    Ereignis-Engine bucht jeden Vorgang dort). Eine Beitragsfreistellung
    zwischen zwei Jahrestagen pruefte vorher nur der Modus ``materialisieren``;
    ohne Erhoehung oder Herabsetzung in der Lieferung rundete die Uebernahme
    das Jahr still ab, und P-B1, Fortschreibung und Abschluss rechneten mit
    dem abgerundeten Jahr. Rueckgabe: der Befund mit Ausweg, oder None."""
    monate = _monate(beginn, datum)
    if monate % 12:
        return (f"{art} der Vorgeschichte bei Monat {monate} liegt nicht auf dem "
                "Vertragsjahrestag — Lieferung klaeren, nicht runden")
    return None


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
        fehler_j = vorgeschichte_jahrestag_fehler("PEX", beginn, _parse(zeile[s["datum"]]))
        if fehler_j:
            raise SystemExit(f"Police {police}: {fehler_j}")
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
    anker_wert: Optional[Tuple[int, float]] = None,
    red_verfahren: str = TEILKUENDIGUNG,
    tku_umfang: Optional[str] = None,
    stoab_je_baustein: bool = False,
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
        leite_pex_serie_mit_bausteinen_ab,
        leite_serie_ueber_folge_ab,
        serie_braucht_folge,
        tarifwerk_homogen_in_bfr_summe,
    )

    arten = [a for a, _, _ in folge]
    if "PEX" in arten:
        # Nach der Beitragsfreistellung stellt die Quelle nichts mehr um —
        # ausser Absetzungen: Jede gelieferte Absetzung danach war eine
        # Teilkuendigung der beitragsfreien Summe (Uebersetzungsregel
        # ``zielverfahren``, Annahme B5; Entscheid des Maintainers 2026-10-01:
        # TKU auch nach PEX).
        pex_pos = arten.index("PEX")
        nach_pex = arten[pex_pos + 1:]
        if arten.count("PEX") > 1 or any(a != "RED" for a in nach_pex):
            raise SystemExit(
                f"Police {police}: nach der Beitragsfreistellung folgt in der "
                f"Vorgeschichte etwas anderes als Teilkuendigungen ({arten}) — "
                "die Quelle stellt danach nichts mehr um; Lieferung klaeren")
        pex_jahr = folge[pex_pos][1]
        if "ERH" in arten and not tarifwerk_homogen_in_bfr_summe(
                stoab_je_baustein=stoab_je_baustein, red_verfahren=red_verfahren,
                tku_umfang=tku_umfang):
            # Pruefrunde J, J04: Greift eine Regel des Tarifwerks je Baustein
            # (Stornoabzug je Baustein, Teilkuendigung nur der
            # Grundversicherung), ist kein Wert homogen in der beitragsfreien
            # Gesamtsumme — die Zusammenfassung zu einem Baustein rechnete den
            # Rueckkauf ohne die Mindestabzuege der Scheiben und kuerzte bei
            # einer Teilkuendigung die ganze Summe. Die Uebernahme schreibt
            # die Bausteine, oder sie verweigert benannt.
            if any(a == "RED" for a in nach_pex):
                raise MigrationszugangFehler(
                    "Teilkuendigung nach der Freistellung in einer Erhoehungsserie "
                    "unter einem Tarifwerk mit Regeln je Baustein: die Bausteine "
                    "sind daraus nicht bestimmt (nicht gebaut) — Lieferung klaeren")
            ereignisse_vor = []
            for art, jahr, datum in folge[:pex_pos]:
                anteil = None
                if art == "RED":
                    anteil = red_anteile_je_datum.get(police, {}).get(
                        datum, red_anteile.get(police))
                ereignisse_vor.append((art, jahr, anteil))
            serie_b = leite_pex_serie_mit_bausteinen_ab(
                mp_felder, ereignisse=ereignisse_vor, pex_jahr=pex_jahr,
                vs_bfr=erlsumme, satz=erhoehungssatz, red_verfahren=red_verfahren,
                tku_umfang=tku_umfang, stoab_je_baustein=stoab_je_baustein,
                scheiben_mit_gamma1=scheiben_mit_gamma1)
            zustand_b: Dict[str, Any] = {
                "beitragsfrei_seit_jahr": pex_jahr,
                "sum_insured": serie_b.grundsumme,
                "scheiben": serie_b.scheiben,
                "quell_komponenten": 1 + len(serie_b.scheiben),
            }
            if serie_b.absetzungen:
                zustand_b["alt_absetzungen"] = serie_b.absetzungen
                zustand_b["gedeckt_durch"] = GEDECKT_AUSKUNFT
            if serie_b.anteil_unbestimmt:
                zustand_b["absetzungsanteil_unbestimmt"] = serie_b.anteil_unbestimmt
            return zustand_b
        # Ein-Punkt-Inversion auch mit Teilkuendigungen nach der
        # Freistellung und Herabsetzungen davor: Jeder Vorgang nach PEX
        # kuerzt beitragsfreie Summen, und Bausteine desselben Ablauftermins
        # tragen je Einheit beitragsfreier Summe denselben Reservesatz — die
        # gelieferte (gekuerzte) Gesamtsumme bleibt die bestimmende Groesse.
        return {
            "beitragsfrei_seit_jahr": pex_jahr,
            "sum_insured": leite_pex_ursprungssumme_ab(
                mp_felder, pex_jahr=pex_jahr, vs_bfr=erlsumme),
            # Die Ein-Punkt-Inversion kollabiert die Bausteine der
            # Quelle. Wert-aequivalent ist das NUR unter einem Tarifwerk
            # ohne Regel je Baustein (oben gefragt, Pruefrunde J, J04):
            # dort ist nach terminalem PEX jede erreichbare Pruefgroesse
            # homogen in der beitragsfreien GESAMTSUMME — NICHT weil die
            # Umwandlungsfaktoren der Bausteine gleich waeren (sie
            # sind es nicht; sum_insured ist hier eine
            # Aequivalenzgroesse, keine historische Bausteinsumme).
            # Fuer die Rundungs-Skalierung des Wertvergleichs bleibt
            # massgeblich, aus wie vielen je fuer sich gerundeten
            # Baustein-Werten der gelieferte Wert besteht
            # (Bedingungswerk Ziffer 5: je Baustein ermittelt).
            "quell_komponenten": 1 + sum(
                1 for a, _, _ in folge if a == "ERH"),
        }
    if erhoehungssatz is None:
        # Pruefrunde G (G21): Die Regel steht in der Spez, nicht am Aufruf —
        # die Meldung schickte zu einem Schalter, den dasselbe Kommando
        # verweigert.
        raise SystemExit(
            f"Police {police}: mehrere Alt-Ereignisse sind ohne Dynamiksatz "
            "unterbestimmt — die Spez stellt quellverfahren.erhoehungssatz als "
            "'nicht belegt' fest, die Lieferung traegt aber eine Serie. Ausweg: "
            "den Dynamiksatz der Quelle in der A-Box belegen (Fundstelle: "
            "Bedingungswerk oder registrierte Auskunft der Quelle), Gate P-Q3 im "
            "Scope bestand, Spez neu erzeugen (spez.erzeugen)")
    ereignisse: List[Tuple[str, int, Optional[float]]] = []
    for art, jahr, datum in folge:
        anteil = None
        if art == "RED":
            anteil = red_anteile_je_datum.get(police, {}).get(
                datum, red_anteile.get(police))
        ereignisse.append((art, jahr, anteil))
    # Die geschlossene Serien-Ableitung traegt nur die Teilkuendigung der
    # Grundversicherung (jede Folge linear in der Ursprungssumme). Ist eine
    # gelieferte Absetzung nach der Uebersetzungsregel eine echte
    # Herabsetzung (Annahme B5: Quelle mit Herabsetzung, vor dem
    # Beitragsende) oder trifft die Teilkuendigung nach dem Tarifwerk alle
    # Bausteine (Entscheid B1 vom 2026-10-01), rechnet die Vorgangsfolge des Kerns den
    # Zustand — der Vertrag ist dann geteilt und traegt seine Vorgaenge.
    mit_folge, umfang = serie_braucht_folge(
        ereignisse, red_verfahren=red_verfahren, tku_umfang=tku_umfang,
        beitragsdauer=int(mp_felder["t"]))
    if mit_folge:
        serie_f = leite_serie_ueber_folge_ab(
            mp_felder, ereignisse=ereignisse, erlsumme=erlsumme,
            satz=erhoehungssatz, red_verfahren=red_verfahren, tku_umfang=umfang,
            stoab_je_baustein=stoab_je_baustein,
            scheiben_mit_gamma1=scheiben_mit_gamma1)
        zustand_f: Dict[str, Any] = {
            "sum_insured": serie_f.grundsumme,
            "scheiben": serie_f.scheiben,
            # Jeder Anteil ist registrierte Auskunft (ohne sie verweigert die
            # Ableitung): Pflichtziehung der Abnahmen.
            "gedeckt_durch": GEDECKT_AUSKUNFT,
        }
        if serie_f.vorgaenge:
            # Ein GETEILTER Vertrag: Ursprungssummen plus Vorgaenge.
            zustand_f["vorgaenge"] = serie_f.vorgaenge
        else:
            # Nur Teilkuendigungen: zustandslos in IST-Summen; die
            # Teilkuendigungen stehen als Beleg wie in der geschlossenen Form.
            zustand_f["alt_absetzungen"] = serie_f.teilkuendigungen
        return zustand_f
    offene_red = any(
        art == "RED" and anteil is None for art, _, anteil in ereignisse)
    if offene_red and red_anteil_kandidaten:
        serie = bestimme_serie_mit_kandidaten(
            mp_felder, ereignisse=ereignisse, erlsumme=erlsumme,
            satz=erhoehungssatz, jbrutto=jbrutto,
            kandidaten=red_anteil_kandidaten,
            scheiben_mit_gamma1=scheiben_mit_gamma1,
            anker=anker_wert)
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
    if serie.anteil_unbestimmt:
        # Ebenfalls Beleg: Herabsetzungsjahre, deren Anteil aus der
        # IST-Welt nicht identifizierbar und fuer sie unerheblich ist.
        zustand["absetzungsanteil_unbestimmt"] = serie.anteil_unbestimmt
    if any(art == "RED" and anteil is not None for art, _, anteil in ereignisse):
        # Die Struktur traegt ein Anteil aus der registrierten Auskunft —
        # nicht die eigene Ableitung: Pflichtziehung der Abnahmen.
        zustand["gedeckt_durch"] = GEDECKT_AUSKUNFT
    return zustand


#: Kennung eines Anfangszustands, dessen Struktur die registrierte Auskunft
#: der Quelle traegt (``--red-anteile-datei``), nicht die eigene Ableitung
#: aus der Lieferung. Solche Policen sind PFLICHTZIEHUNG der aktuariellen
#: Abnahmen und der Migrationssuite (Pruefer-Befund B1 zur Alt-Absetzung): Nach dem
#: Beitragsende sind die Wertvergleiche gegen die Zerlegung blind — eine
#: falsche Auskunft faellt an keinem Bewertungspunkt auf, nur an einer
#: Police, die eine Abnahme tatsaechlich ansieht.
GEDECKT_AUSKUNFT = "auskunft"


def gedeckte_policen(zustaende: Dict[str, Dict[str, Any]]) -> Dict[str, str]:
    """Police -> wodurch ihr Anfangszustand gedeckt ist (nur die gedeckten)."""
    return {p: str(z["gedeckt_durch"]) for p, z in sorted(zustaende.items())
            if z.get("gedeckt_durch")}


def deckungsbeleg(
    zustaende: Dict[str, Dict[str, Any]], auskunft: Optional[Dict[str, Any]]
) -> Dict[str, Dict[str, Any]]:
    """Je gedeckter Police, WODURCH ihr Anfangszustand gedeckt ist: die
    Auskunft mit Name, SHA-256 und dem Bezug dieser Police. Dieselbe Form in
    Uebernahmebeleg, aktuariellem Test und Migrationssuite — A-M4 haelt die
    Mengen gleich."""
    aus: Dict[str, Dict[str, Any]] = {}
    for police, durch in gedeckte_policen(zustaende).items():
        eintrag: Dict[str, Any] = {"durch": durch}
        if durch == GEDECKT_AUSKUNFT and auskunft:
            eintrag.update(datei=auskunft.get("name"), sha256=auskunft.get("sha256"),
                           bezug=(auskunft.get("bezug") or {}).get(police))
        aus[police] = eintrag
    return aus


class AnfangszustandUnbestimmt(SystemExit):
    """Ein Vertrag mit Vorgeschichte, dessen Anfangszustand nicht ableitbar ist."""


def verweigere_unbestimmte(warnungen: List[str]) -> None:
    """Pruefer-Befund B1 zur Alt-Absetzung, als Klasse: Ein Vertrag, dessen
    Anfangszustand NICHT ableitbar ist, wird nicht still als zustandsloser
    Vertrag mit der gelieferten Summe weitergefuehrt — vorher lief die
    ganze Kette mit Exit 0, nur eine Warnung und ein Eintrag im Beleg sagten
    es, und eine spaetere Teilkuendigung zahlte falsch aus. Jede Ursache,
    aus der ``MigrationszugangFehler`` in der Ableitung entsteht, fuehrt hier
    zur Verweigerung (Annahme des Auftrags; ADR-002-Nachtrag 2026-10-01).

    Gedeckt ist ein solcher Vertrag nur durch das, was seine STRUKTUR
    bestimmt: die registrierte Auskunft der Quelle je Ereignis
    (``--red-anteile-datei``, mit ``BEZUG`` auch eine dokumentierte
    Arbeits-Lesart des Aktuars). "Die Werte an den Bewertungspunkten
    stimmen" ist keine Deckung — nach dem Beitragsende sind A-M1, A-M2 und
    die Suite gegen die Zerlegung blind. Ein ganzer Fall ohne Anfangszustand
    bleibt ``--anfangszustand grundvertrag`` (nicht freigeschaltet, im Beleg
    benannt)."""
    if not warnungen:
        return
    raise AnfangszustandUnbestimmt(
        f"{len(warnungen)} Vertrag/Vertraege mit Vorgeschichte ohne ableitbaren "
        "Anfangszustand — nicht still als Grundvertrag uebernommen: "
        + " | ".join(warnungen[:5]) + (" ..." if len(warnungen) > 5 else "")
        + ". Ausweg: den fortgefuehrten Anteil je Ereignis als registrierte "
        "Auskunft der Quelle nennen (--red-anteile-datei, POLNR;GEVO;DATUM;"
        "ANTEIL;BEZUG) oder den Fall mit --anfangszustand grundvertrag als nicht "
        "freigeschaltet fuehren")


def vorgeschichte_grenzfehler(
    art: str, jahr: int, datum: "dt.date", stammzeile: Any
) -> Optional[str]:
    """Die Grenzen eines gelieferten Vorgangs der Vorgeschichte — fuer jeden
    Vorgang (PEX, ERH, RED) und jede Generation dieselben; die
    Jahrestags-Konvention prueft der Aufrufer davor.

    * ``0 < Jahr``: am Versicherungsbeginn gibt es keinen Vorgang.
    * ``Jahr < n``: am oder nach dem Ablauf gibt es den Vertrag nicht mehr.
    * ``Datum <= Bestandszugang``: Die Vorgeschichte endet am Stichtag der
      Uebernahme; was danach liegt, ist ein Geschaeftsvorfall des
      Pruefzeitraums (Protokoll), kein Anfangszustand.

    Rueckgabe: der Befundtext mit dem Ausweg, oder None."""
    import pandas as pd

    n = int(stammzeile["duration"])
    if int(jahr) <= 0:
        return (f"{art} der Vorgeschichte im Vertragsjahr {jahr} — am "
                "Versicherungsbeginn gibt es keinen Vorgang; Lieferung klaeren")
    if int(jahr) >= n:
        return (f"{art} der Vorgeschichte im Vertragsjahr {jahr} liegt am oder nach "
                f"dem Ablauf (n = {n}) — den Vertrag gibt es dort nicht mehr; "
                "Lieferung klaeren")
    zugang = stammzeile.get("bestandszugang") if hasattr(stammzeile, "get") else None
    if zugang is not None and not pd.isna(zugang) \
            and pd.Timestamp(datum) > pd.Timestamp(zugang):
        return (f"{art} der Vorgeschichte am {datum} liegt nach dem Stichtag der "
                f"Uebernahme {pd.Timestamp(zugang).date()} — ein Vorgang des "
                "Pruefzeitraums gehoert ins Geschaeftsvorfall-Protokoll, nicht in "
                "die Vorgeschichte; Lieferung klaeren")
    return None


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
    tku_umfang: Optional[str] = None,
    stoab_je_baustein: bool = False,
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
            fehler_j = vorgeschichte_jahrestag_fehler(
                art_e, beginn, _parse(ereignis[s["datum"]]))
            if fehler_j:
                raise SystemExit(f"Police {police}: {fehler_j}")
            folge.append((art_e, monate_e // 12, ereignis[s["datum"]]))
        # Die Grenzen der Vorgeschichte, an EINER Stelle und VOR jeder
        # Verzweigung nach Vorgang oder Verfahren (Pruefer-Befund B2,
        # 2026-10-01: eine Alt-Herabsetzung nach dem Stichtag, am oder nach dem
        # Ablauf wurde bei der Teilkuendigung ohne Meldung uebernommen, weil
        # der Zweig ``continue`` vor jeder Grenzpruefung stand).
        for art_e, jahr_e, datum_e in folge:
            fehler_g = vorgeschichte_grenzfehler(
                art_e, jahr_e, _parse(datum_e), stammzeilen[police])
            if fehler_g:
                raise SystemExit(f"Police {police}: {fehler_g}")

        # Dubletten-Wache: eine doppelt gelieferte Ereigniszeile wuerde
        # unten still als zusaetzliche Quell-Komponente zaehlen und der
        # Rundungstoleranz eine unverdiente Stufe geben — eine
        # Datenanomalie darf keine Toleranz kaufen.
        gesehen: set = set()
        for art_e, jahr_e, datum_e in folge:
            if (art_e, jahr_e) in gesehen:
                raise SystemExit(
                    f"Police {police}: {art_e} am {datum_e} "
                    f"(Vertragsjahr {jahr_e}) ist in der Vorgeschichte "
                    "doppelt geliefert — Lieferung klaeren, nicht "
                    "doppelt zaehlen")
            gesehen.add((art_e, jahr_e))

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
                    scheiben_mit_gamma1=scheiben_mit_gamma1,
                    anker_wert=(anker or {}).get(police),
                    red_verfahren=red_verfahren, tku_umfang=tku_umfang,
                    stoab_je_baustein=stoab_je_baustein)
            except MigrationszugangFehler as exc:
                warnungen.append(f"Police {police} (Serie): {exc}")
            continue

        art = folge[0][0]
        jahr = folge[0][1]

        if art == "RED" and alt_absetzung_ist_teilkuendigung(
                red_verfahren, jahr, int(mp_felder["t"]), beitragsfrei_ab=None):
            # Unter der Teilkuendigungs-Semantik (Bedingungswerk
            # Ziffer 6, Ausweitung 16) fuehrt die Quelle nach der
            # Herabsetzung ZUSTANDSLOS mit der kleineren Grundsumme
            # weiter — und die steht bereits im gelieferten Stamm. Es
            # gibt keinen geteilten Anfangszustand zu rekonstruieren;
            # die Teilungs-Rueckwege (leite_absetzung_ab,
            # Anker-Kalibrierung) sind Artefakte der PLV-Verfahren.
            #
            # Dasselbe gilt fuer eine Absetzung NACH dem Beitragsende in
            # JEDER Generation (Entscheid des Maintainers 2026-10-01: der
            # Zugang integriert sie; Annahme A2, klv.md 7.2): Sie
            # war eine Teilkuendigung, der gelieferte
            # Vertrag ist f x Ursprungssumme = ERLSUMME und wird als dieser
            # zustandslose Vertrag gefuehrt. Der fortgefuehrte Anteil wird
            # dafuer nicht gebraucht — der Rechenkern ist homogen in der
            # Summe; die Ursprungssumme bestimmt eine registrierte Auskunft
            # (``leite_ursprungssumme_ab``), wo sie gefragt ist.
            continue

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
                        jbrutto=jbrutto,
                        scheiben_mit_gamma1=scheiben_mit_gamma1)
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
                if red_anteile.get(police) is not None:
                    zustaende[police]["gedeckt_durch"] = GEDECKT_AUSKUNFT
        except MigrationszugangFehler as exc:
            warnungen.append(f"Police {police} ({art}, Jahr {jahr}): {exc}")
    return zustaende, warnungen


def _schicht_teile(
    police: str, eintrag: Any, monate_ta: Optional[int]
) -> Dict[str, Any]:
    """Schicht-Felder eines Belegeintrags fuer den Pruefauftrag.

    Wiederverwendet die Zerlegung des aktuariellen Tests
    (_schicht_felder); der Verankerungszeitpunkt kommt aus
    verankerung.parquet — derselben Datei, deren SHA der Schichtbeleg
    per Provenienz bindet.
    """
    if eintrag is None:
        return {}
    from rechner_pipeline.gates.aktuartest_lauf import _schicht_felder

    felder = dict(_schicht_felder(eintrag))
    if monate_ta is None:
        raise SystemExit(
            f"Police {police}: Schichtbeleg ohne Verankerungszeitpunkt — "
            "verankerung.parquet traegt die Police nicht"
        )
    felder["monate_ta"] = int(monate_ta)
    return felder


def baue_auftraege(
    bestand, spez, abzug_1, abzug_2, protokoll, *,
    stichtag_1: dt.date, stichtag_2: dt.date, spalten: Dict[str, str],
    auspraegungen: Optional[Dict[str, Dict[str, str]]] = None,
    beitragsfrei_seit: Optional[Dict[str, int]] = None,
    anfangszustaende: Optional[Dict[str, Dict[str, Any]]] = None,
    scheiben_mit_gamma1: bool = False,
    stoab_je_baustein: bool = False,
    tku_umfang: Optional[str] = None,
    schichten: Optional[Dict[str, Any]] = None,
    monate_ta_je_police: Optional[Dict[str, int]] = None,
    dk_am_jahrestag: bool = False,
    summen: Optional[Dict[str, float]] = None,
) -> List[VertragsPruefung]:
    """Je Vertrag genau einen Pruefauftrag.

    ``tku_umfang`` (Tarifwerk der Spez) geht in jeden Auftrag; vorher leitete
    die Engine ihn aus dem Verfahren ab, und ``--tku-umfang`` wirkte nur auf
    den Anfangszustand (gefunden beim Nachzug ADR-024).

    ``summen`` (police -> gelieferte Versicherungssumme aus den
    transformierten Zeilen) ist die Grundlage des Modellpunkts, wo kein
    Anfangszustand eine Grund- oder Ursprungssumme liefert. Die Welt der
    Pruefstrecke ist die LIEFERUNG; der Stamm (``--bestand``) traegt seit
    der Freischaltung die Grundsumme der Fuehrung und ist fuer eine Police
    ohne ableitbaren Zustand keine Vergleichsbasis mehr.
    """
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
            # Die Bewertung der Vorgeschichts-Welt rechnet auf dem
            # Ursprungs- bzw. Grund-Modellpunkt (Fall-Ableitungsregel).
            mp_kwargs["sum_insured"] = float(zustand["sum_insured"])
        elif summen is not None and police in summen:
            # Ohne Zustand gilt die GELIEFERTE Summe als ein Vertrag —
            # nicht die Stammsumme der Fuehrung (Freischaltung).
            mp_kwargs["sum_insured"] = float(summen[police])
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
            tku_umfang=tku_umfang,
            reduktion=zustand.get("reduktion"),
            quell_komponenten=zustand.get("quell_komponenten"),
            dk_am_jahrestag=dk_am_jahrestag,
            **_schicht_teile(
                police, (schichten or {}).get(police),
                (monate_ta_je_police or {}).get(police)),
        ))
    return auftraege


#: Die Nebentabellen der Uebernahme, die der Fuehrungswert liest: im
#: Verzeichnis des Bestands, gelesen, wenn sie dort liegen; die Historie ist
#: Pflicht (beitragsfreie Vertraege).
FUEHRUNGSWERT_NEBENTABELLEN = ("historie.parquet", "scheiben.parquet", "merkmale.parquet",
                               "schichten.parquet", "verankerung.parquet",
                               "reduktionen.parquet")


def fuehrungswert_rechnen(
    bestand: Any,
    lies_neben: Any,
    config_text: str,
    stichtage: Dict[str, dt.date],
    *,
    tarifwerk_der_spez: Dict[str, Dict[str, Any]],
) -> Tuple[str, Dict[str, Dict[str, Optional[Dict[str, Any]]]]]:
    """Der Fuehrungswert aus Bestand, Nebentabellen und Config — EIN Weg fuer
    die Produzentin (diese Suite) und fuer A-M4, das ihn nachrechnet
    (:func:`fuehrungswert_nachgerechnet`; Pruefrunde G, G03).

    ``lies_neben(name)`` gibt die Bytes einer Nebentabelle oder ``None``, wenn
    sie nicht neben dem Bestand liegt — die Produzentin bindet sie dabei, A-M4
    haelt sie gegen die Bindung der Suite. Gerechnet wird in der
    Bestandsschicht (``bestand.migrationszugang.fuehrungswerte``, die
    Bewertungsstrecke des Abschlusses; Kante dieses Moduls).
    """
    from rechner_pipeline.bestand.migrationszugang import (
        MigrationszugangFehler,
        fuehrungswerte,
    )

    tabellen: Dict[str, Any] = {}
    for name in FUEHRUNGSWERT_NEBENTABELLEN:
        roh = lies_neben(name)
        tabellen[name] = None if roh is None else read_portfolio_aus_bytes(roh)
    if tabellen["historie.parquet"] is None:
        raise MigrationszugangFehler(
            "historie.parquet fehlt neben dem Bestand — ohne die Historie der "
            "Uebernahme ist der Fuehrungswert nicht zu rechnen (beitragsfreie Vertraege)")
    return fuehrungswerte(
        bestand, tabellen["historie.parquet"], config_text, stichtage,
        scheiben=tabellen["scheiben.parquet"], merkmale=tabellen["merkmale.parquet"],
        schichten=tabellen["schichten.parquet"], verankerung=tabellen["verankerung.parquet"],
        reduktionen=tabellen["reduktionen.parquet"],
        tarifwerk_der_spez=tarifwerk_der_spez)


def fuehrungswert_nachgerechnet(suite: Dict[str, Any], fall: Path,
                                tarifregeln: Tarifregeln) -> List[str]:
    """Den Fuehrungswert eines Suite-Belegs auf den GEBUNDENEN Bytes nachrechnen
    und Feld fuer Feld gegen den Beleg halten (leer = derselbe Wert).

    Pruefrunde G, G03: A-M4 sah bisher nur die Form — Felder, endliche
    Zahlen, eine bekannte Konvention, Bindungshashes. Ein verdoppeltes
    Deckungskapital, eine falsche Konvention und ein Vertrag, der am
    Folgestichtag "nicht mehr in Kraft" sein sollte, gingen durch, und A-M4
    pinnte damit das Soll der Zugangsprobe (ADR-022). Jetzt wird
    hergeleitet, nicht gelesen — dieselbe Figur wie bei der Fuehrungsprobe
    und P-B1: der Bestand mit ``bestand_sha256``, jede Nebentabelle, die neben
    ihm liegt (sie muss gebunden sein, und eine gebundene muss dort liegen),
    die Config mit ``config_sha256``, die Stichtage der Suite und das
    Tarifwerk der Spez, die A-M4 bindet. Eine Datei, deren Bytes nicht mehr
    die gebundenen sind, wird nicht nachgerechnet, sondern genannt.
    """
    from rechner_pipeline.bestand.migrationszugang import MigrationszugangFehler

    fall = Path(fall).resolve()
    eingaben = suite.get("eingaben")
    kopf = suite.get("fuehrungswert") or {}
    if not isinstance(eingaben, dict):
        return ["Fuehrungswert nicht nachgerechnet: die Suite nennt ihre Eingaben nicht"]

    def pfad_von(schluessel: str) -> Path:
        p = Path(schluessel)
        return p if p.is_absolute() else fall / p

    def schluessel_von(pfad: Path) -> str:
        pfad = pfad.resolve()
        return str(pfad.relative_to(fall)) if fall in pfad.parents else str(pfad)

    def gebunden_lesen(schluessel: str) -> Tuple[Optional[bytes], Optional[str]]:
        pfad = pfad_von(schluessel)
        if not pfad.is_file():
            return None, f"{schluessel} (fehlt)"
        roh = pfad.read_bytes()
        if hashlib.sha256(roh).hexdigest() != eingaben.get(schluessel):
            return None, f"{schluessel} (Bytes nicht die gebundenen)"
        return roh, None

    bestand_schluessel = sorted(k for k, v in eingaben.items()
                                if v == suite.get("bestand_sha256") and k.endswith(".parquet"))
    verzeichnisse = {pfad_von(k).resolve().parent for k in bestand_schluessel}
    if len(verzeichnisse) != 1:
        return [f"Fuehrungswert nicht nachgerechnet: der Bestand (bestand_sha256) steht "
                f"nicht eindeutig unter den Eingaben der Suite ({bestand_schluessel[:3]})"]
    verzeichnis = verzeichnisse.pop()
    config_schluessel = sorted(k for k, v in eingaben.items()
                               if v == kopf.get("config_sha256"))
    if not config_schluessel:
        return ["Fuehrungswert nicht nachgerechnet: die Config (config_sha256) steht "
                "nicht unter den Eingaben der Suite"]
    befunde: List[str] = []
    bestand_roh, fehler = gebunden_lesen(bestand_schluessel[0])
    if fehler:
        befunde.append(fehler)
    config_roh, fehler = gebunden_lesen(config_schluessel[0])
    if fehler:
        befunde.append(fehler)
    neben: Dict[str, Optional[bytes]] = {}
    for name in FUEHRUNGSWERT_NEBENTABELLEN:
        schluessel = schluessel_von(verzeichnis / name)
        if (verzeichnis / name).is_file() or schluessel in eingaben:
            if schluessel not in eingaben:
                befunde.append(f"{schluessel} (liegt neben dem Bestand, von der Suite "
                               "nicht gelesen)")
                continue
            neben[name], fehler = gebunden_lesen(schluessel)
            if fehler:
                befunde.append(fehler)
        else:
            neben[name] = None
    if befunde:
        return ["Fuehrungswert nicht nachgerechnet — die Eingaben sind nicht die, auf "
                f"denen die Suite rechnete: {befunde[:5]}; die Suite neu ausfuehren"]
    try:
        konvention, werte = fuehrungswert_rechnen(
            read_portfolio_aus_bytes(bestand_roh), neben.get, config_roh.decode("utf-8"),
            {t: _parse(str(suite.get(t))) for t in ("stichtag_1", "stichtag_2")},
            tarifwerk_der_spez={tarifregeln.generation: dict(tarifregeln.tarifwerk)})
    except (MigrationszugangFehler, ValueError) as exc:
        return [f"Fuehrungswert nicht nachgerechnet: {exc}"]
    abweichend: List[str] = []
    if kopf.get("konvention") != konvention:
        abweichend.append(f"Konvention {kopf.get('konvention')!r} statt {konvention!r}")
    beleg = {str(u.get("police_id")): u.get("fuehrungswert")
             for u in suite.get("vertraege") or [] if isinstance(u, dict)}
    if set(beleg) != set(werte):
        abweichend.append(f"Policen {sorted(set(beleg) ^ set(werte))[:5]}")
    for police in sorted(set(beleg) & set(werte)):
        gerechnet = json.loads(json.dumps(werte[police], sort_keys=True))
        if json.loads(json.dumps(beleg[police], sort_keys=True)) != gerechnet:
            termine = sorted(t for t in gerechnet
                             if (beleg[police] or {}).get(t) != gerechnet[t])
            abweichend.append(f"{police} {termine}")
    if abweichend:
        return [f"Fuehrungswert weicht vom nachgerechneten ab (Bestand und Config der "
                f"Suite, Tarifwerk der Spez): {abweichend[:5]}"
                + (f" und {len(abweichend) - 5} weitere" if len(abweichend) > 5 else "")
                + " — der Beleg nennt nicht den Wert, den die Fuehrung fuehren wird"]
    return []


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
                   help="transformierter Bestand (Parquet), von P-B1 geprueft; sein "
                        "Verzeichnis ist das der Uebernahme (historie.parquet und die "
                        "Nebentabellen daneben tragen den Fuehrungswert)")
    p.add_argument("--config", required=True,
                   help="Bestand-Config der Fuehrung (TOML) — mit ihr rechnet der "
                        "Fuehrungswert, was der Monatsabschluss fuer jeden Vertrag "
                        "fuehrt (Entscheid 2026-10-01)")
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
                   help="REGISTRIERTE Auskunft der Quelle zu den fortgefuehrten "
                        "Beitragsanteilen (POLNR;GEVO;DATUM;ANTEIL, optional "
                        "BEZUG) — der einzige Weg, sie zu nennen; wirkt mit "
                        "--vorgeschichte")
    p.add_argument("--anker-erwartungswerte", dest="anker_quelle",
                   default=None, metavar="REGISTRIERTE_DATEI",
                   help="REGISTRIERTE Erwartungswerte am Verankerungs"
                        "zeitpunkt. Aus ihnen wird der Zustand einer "
                        "Absetzung kalibriert, deren Beitragsgleichung "
                        "entfaellt — eine ANDERE Quelle als die hier "
                        "geprueften Abzugswerte, der Vergleich bleibt also "
                        "unabhaengig.")
    p.add_argument("--red-anteil-kandidat", dest="red_anteil_kandidaten",
                   action="append", type=float, default=[],
                   metavar="ANTEIL",
                   help="ARBEITSANNAHME des Laufs: Kandidat des "
                        "Herabsetzungsanteils (wiederholbar); offene Anteile "
                        "in Ereignis-Serien werden dann ueber die "
                        "Beitragsgleichung bestimmt (eindeutiger Treffer oder "
                        "benannter Fehler) — siehe aktuartest_lauf.")
    p.add_argument(
        "--schicht", dest="schicht", default=None,
        metavar="SCHICHTBELEG",
        help="ABGELEITETER Schichtbeleg (gates.verankerung_belegen) "
             "unter <fall>/abgeleitet/ — derselbe Beleg wie beim "
             "aktuariellen Test, mit nachgerechneter Provenienz-Bindung. "
             "Ohne ihn bleibt der rohe Wertvergleich: gueltig, solange "
             "der Fall keine Schichten fuehrt; sonst zeigt jeder "
             "Vertrag sein unabsorbiertes Verankerungs-Residuum.")
    p.add_argument("--repo-root", type=lebendes_repo, dest="repo_root", default=".")
    p.add_argument("--out", default=None)
    for name, vorgabe in VORGABE.items():
        p.add_argument(f"--spalte-{name}", dest=f"spalte_{name}",
                       default=vorgabe,
                       help=f"Spaltenname der Lieferung (Vorgabe: {vorgabe})")
    # Tarifwerk, Verfahren der Quelle, Dynamiksatz und Stichtag des
    # gelieferten Deckungskapitals stehen in der Spez (ADR-024, Nachtrag).
    verweigere_entfallene_schalter(p)
    args = p.parse_args(argv)

    fall = Path(args.fall).resolve()
    if not (fall / "fall.json").is_file():
        print(f"Kein Fall-Arbeitsbereich: {fall}", file=sys.stderr)
        return 2

    spalten = {n: getattr(args, f"spalte_{n}") for n in VORGABE}
    # Jede Eingabe genau einmal lesen und binden (Review T25-05,
    # Haelfte b). Vorher band dieses Kommando GENAU EINE Eingabe — den
    # Bestand — und las ausgerechnet die zweimal: einmal zum Verarbeiten
    # (read_portfolio vom Pfad), viel spaeter noch einmal zum Hashen.
    # Dazwischen lag der ganze Lauf; der Beleg bezeugte damit nicht die
    # verarbeiteten Bytes.
    bindung = Eingangsbindung(fall)
    bestand_pfad = Path(args.bestand)
    bestand_gelesen = bindung.binde(bestand_pfad)
    bestand = read_portfolio_aus_bytes(bestand_gelesen.roh)
    # Laden und Regeln in EINEM Fang (Pruefrunde H): Auch der Lader verweigert
    # benannt (Version, Regelwert); ein Traceback waere ein Fehler ohne Ausweg.
    try:
        spez = lade_spez_aus_bytes(
            bindung.binde(spez_pfad(fall, args.generation)).roh)
        regeln = tarifregeln_des_falls(fall, spez)
    except ValueError as exc:
        print(f"migrationssuite_lauf: {exc}", file=sys.stderr)
        return 2
    abzug_1 = _lies_csv(fall, args.abzug_1, bindung)

    auspraegungen = None
    summen: Optional[Dict[str, float]] = None
    if args.zeilen is not None:
        zeilen = bindung.binde(Path(args.zeilen)).json()
        if not isinstance(zeilen, list):
            print(f"{args.zeilen}: erwartet wird die Zeilenliste aus "
                  "gates.transformation_anwenden --zeilen", file=sys.stderr)
            return 2
        auspraegungen = auspraegungen_je_police(spez, zeilen)
        summen = {str(z["police_id"]): float(z["sum_insured"]) for z in zeilen}

    beitragsfrei_seit = None
    anfangszustaende = None
    zustandswarnungen: List[str] = []
    # Der Belegblock der Auskunft DIESES Laufs (None ohne Auskunft), fuer
    # die Welt-Gleichheit mit dem Schichtbeleg (aktuartest_lauf._schichten).
    auskunft_beleg: Optional[Dict[str, Any]] = None
    if args.red_anteile_datei is not None and args.vorgeschichte is None:
        print("--red-anteile-datei wirkt nur mit --vorgeschichte (die "
              "Anteile gehoeren zu den Ereignissen der Vorgeschichte) — "
              "ohne sie wuerde die Auskunft weder gelesen noch gebunden",
              file=sys.stderr)
        return 2
    if args.vorgeschichte is not None:
        vorgeschichte = _lies_csv(fall, args.vorgeschichte, bindung)
        beitragsfrei_seit = beitragsfrei_seit_jahr_je_police(
            vorgeschichte, bestand, spalten=spalten)
        red_anteile: Dict[str, float] = {}
        red_anteile_je_datum: Dict[str, Dict[str, float]] = {}
        if args.red_anteile_datei is not None:
            auskuenfte = lies_auskuenfte(
                fall, args.red_anteile_datei, bindung, vorgeschichte,
                spalten)
            red_anteile = dict(auskuenfte.anteile)
            red_anteile_je_datum = {
                pol: dict(d) for pol, d in auskuenfte.je_datum.items()}
            auskunft_beleg = auskuenfte.beleg
        anker: Dict[str, Any] = {}
        if args.anker_quelle is not None:
            quelle = bindung.binde(
                fall_mod.eingang_datei(fall, args.anker_quelle)).json()
            for eintrag in quelle.get("vertraege", []):
                erster = next(
                    (x for x in (eintrag.get("punkte") or [])
                     if x.get("anlass") == "uebernahme"), None)
                if erster and "kVx_MRV" in (erster.get("erwartet") or {}):
                    anker[str(eintrag["police_id"])] = (
                        int(erster["monate"]),
                        float(erster["erwartet"]["kVx_MRV"]))
        anfangszustaende, zustandswarnungen = anfangszustaende_je_police(
            spez, zeilen if args.zeilen is not None else [],
            vorgeschichte, bestand, spalten=spalten,
            red_verfahren=regeln.quell_red_verfahren, red_anteile=red_anteile,
            auspraegungen=auspraegungen,
            erhoehungssatz=regeln.erhoehungssatz, anker=anker,
            red_anteile_je_datum=red_anteile_je_datum,
            red_anteil_kandidaten=tuple(args.red_anteil_kandidaten),
            scheiben_mit_gamma1=regeln.scheiben_mit_gamma1,
            tku_umfang=regeln.tku_umfang,
            stoab_je_baustein=regeln.stoab_je_baustein)

    schichten: Optional[Dict[str, Any]] = None
    monate_ta_je_police: Optional[Dict[str, int]] = None
    if args.schicht is not None:
        # Dieselbe bindbare Quelle wie beim aktuariellen Test —
        # Provenienz-Pruefung inklusive (spaeter Import: aktuartest_lauf
        # importiert seinerseits lazy aus diesem Modul).
        from rechner_pipeline.gates.aktuartest_lauf import _schichten

        schichten = _schichten(fall, args.schicht, bindung=bindung,
                               repo_root=Path(args.repo_root).resolve(),
                               auskunft=auskunft_beleg)
        ver = read_portfolio_aus_bytes(bindung.binde(
            fall / "abgeleitet" / "bestand" / "verankerung.parquet").roh)
        monate_ta_je_police = {
            str(z.police_id): int(z.monate_ta) for z in ver.itertuples()}

    # Pruefer-Befund B1: ein Vertrag ohne ableitbaren Anfangszustand wird
    # verweigert — NACH der Bindung des Schichtbelegs, damit ein Lauf mit
    # fremder Auskunft deren eigenen Befund behaelt.
    verweigere_unbestimmte(zustandswarnungen)
    auftraege = baue_auftraege(
        bestand,
        spez,
        abzug_1,
        _lies_csv(fall, args.abzug_2, bindung),
        _lies_csv(fall, args.protokoll, bindung),
        stichtag_1=_parse(args.stichtag_1),
        stichtag_2=_parse(args.stichtag_2),
        spalten=spalten,
        auspraegungen=auspraegungen,
        beitragsfrei_seit=beitragsfrei_seit,
        anfangszustaende=anfangszustaende,
        scheiben_mit_gamma1=regeln.scheiben_mit_gamma1,
        stoab_je_baustein=regeln.stoab_je_baustein,
        tku_umfang=regeln.tku_umfang,
        schichten=schichten,
        monate_ta_je_police=monate_ta_je_police,
        dk_am_jahrestag=(regeln.dk_stichtag == "jahrestag"),
        summen=summen,
    )

    # Der Fuehrungswert (Entscheid 2026-10-01): was der Monatsabschluss fuer
    # jeden Vertrag des Zugangs fuehren wird — ueber die Bewertungsstrecke
    # des Abschlusses, aus dem Bestand der Uebernahme und der Config der
    # Fuehrung, alles gebunden. Gerechnet in der Bestandsschicht
    # (bestand.migrationszugang, eine gemessene Kante), nicht hier.
    from rechner_pipeline.bestand.migrationszugang import MigrationszugangFehler
    from rechner_pipeline.models.fuehrungswert import kopf as _fw_kopf

    uebernahme_dir = bestand_pfad.resolve().parent

    def _neben(name: str) -> Optional[bytes]:
        pfad = uebernahme_dir / name
        return bindung.binde(pfad).roh if pfad.is_file() else None

    config_gelesen = bindung.binde(Path(args.config))
    try:
        fw_konvention, fw_werte = fuehrungswert_rechnen(
            bestand, _neben, config_gelesen.text(),
            {"stichtag_1": _parse(args.stichtag_1), "stichtag_2": _parse(args.stichtag_2)},
            # Der Fuehrungswert rechnet mit dem Tarifwerk der CONFIG; es muss
            # das der Spez sein, mit dem diese Suite prueft (ADR-024,
            # Nachtrag) — sonst stuende im selben Beleg ein Wert nach einer
            # anderen Regel.
            tarifwerk_der_spez={args.generation: regeln.tarifwerk})
    except (MigrationszugangFehler, ValueError) as exc:
        print(f"Fuehrungswert nicht rechenbar: {exc}", file=sys.stderr)
        return 2

    # Die Pruefmenge wird an der LIEFERUNG gemessen, nicht an sich
    # selbst: erwartete Anzahl ist die Zeilenzahl des Abzugs zum
    # Migrationsstichtag. Scope-Bindung (Stichtage, Bestand-Hash,
    # Systemstand) laeuft durch die validierende Suite-Signatur.
    ergebnis = pruefe_bestand(
        auftraege,
        erwartete_anzahl=len(abzug_1),
        red_verfahren=regeln.quell_red_verfahren,
        stichtag_1=_parse(args.stichtag_1).isoformat(),
        stichtag_2=_parse(args.stichtag_2).isoformat(),
        bestand_sha256=bestand_gelesen.sha256,
        system=systemstand(Path(args.repo_root).resolve()),
        red_anteile_datei=auskunft_beleg,
        # Pflichtschicht (Pruefer-Befund B1): die Policen, deren
        # Anfangszustand die Auskunft traegt — A-M4 haelt die Menge gegen die
        # der Uebernahme und der Abnahmen.
        pflichtschicht=deckungsbeleg(anfangszustaende or {}, auskunft_beleg),
        fuehrungswert=_fw_kopf(fw_konvention, bestand_sha256=bestand_gelesen.sha256,
                               config_sha256=config_gelesen.sha256),
        fuehrungswerte=fw_werte,
    )
    # Der Beleg nennt, worueber geurteilt wurde — nicht nur den Bestand —
    # und mit welchen Regeln.
    ergebnis["eingaben"] = bindung.als_beleg()
    ergebnis["tarifregeln"] = regeln.als_beleg()

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
