"""``aktuartest_lauf`` — den aktuariellen Test einer Abnahme fahren.

Produzent, kein Gate: Er baut die Pruefauftraege, laesst
:func:`rechner_pipeline.qa.aktuarieller_test.pruefe_stichprobe` rechnen
und schreibt das zurueckgegebene Dict UNVERAENDERT als JSON dorthin, wo
``gates.aktuartest`` es erwartet. Das Gate rechnet die Zusammenfassung
gegen die Einzelurteile nach; ein von Hand nachgebessertes JSON faellt
dort auf.

Er ersetzt Schritt 5 des Skills ``aktuartest-durchfuehren``, der diesen
Zusammenbau bisher je Lauf als Agentenarbeit beschrieb.

Er liegt in ``gates/``, nicht in ``bestand/``: Nur diese Schicht darf
``fall``, ``spez`` und ``qa`` zugleich importieren
(``ontologie/code_karte.py``).

**Woher die Teile kommen — und warum von dort.**

*Die Erwartungswerte* sind eine REGISTRIERTE Quelle des Falls, kein
freier Dateipfad. Sie tragen je Vertrag die Pruefpunkte mit Zeitpunkt,
Anlass und den gelieferten Werten; das abgebende Unternehmen rechnet
nicht den ganzen Bestand nach, sondern die vereinbarte Stichprobe.

*Die Stichprobe* ist ebenfalls geliefert und wird NICHT hier gezogen.
Sie wurde vor der Wertbeschaffung festgeschrieben — andersherum liesse
sie sich nach ihren Ergebnissen aussuchen, und der Nachweis waere
wertlos.

*Die Rechnungsgrundlagen* kommen aus der Tarif-Spez des Falls
(Projektion der A-Box), nicht aus einer Bestands-Config. Eine Config
beschreibt den synthetischen Zielbestand; der uebernommene Vertrag
rechnet mit den Grundlagen, die aus SEINEN Quellen abgeleitet wurden.

*Die Vertragsfelder* kommen aus dem transformierten Bestand
(``gates.bestand_uebernehmen``), zusammengefuehrt ueber
``models.bestand.model_point_kwargs`` — dieselbe Projektion, die auch
Bericht und Fortschreibung verwenden.

Knoten: klv
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any, Dict, List, Optional

from rechner_pipeline import fall as fall_mod
from rechner_pipeline.bestand.parquet_io import read_portfolio
from rechner_pipeline.gates._provenienz import systemstand
from rechner_pipeline.models.bestand import model_point_kwargs
from rechner_pipeline.kern.beitragsreduktion import PROSPEKTIV, VERFAHREN
from rechner_pipeline.qa.aktuarieller_test import (
    Pruefpunkt,
    Vertragspruefung,
    pruefe_stichprobe,
)
from rechner_pipeline.kern.korrekturschicht import (
    KorrekturschichtFehler,
    Schichtparameter,
)
from rechner_pipeline.qa.stichprobe import Stichprobe
from rechner_pipeline.qa.testprofil import vorlage
from rechner_pipeline.spez.validierung import lade_spez

#: Zieldateiname je Abnahme. A-M1 traegt den nackten Namen, die anderen
#: ihr Suffix — genauso liest ``gates.aktuartest`` sie
#: (``aktuartest.py``: kennung = COMMAND if A-M1 else COMMAND-<abnahme>).
ZIELNAME = {
    "A-M1": "aktuartest.json",
    "A-M2": "aktuartest-A-M2.json",
    "A-M3": "aktuartest-A-M3.json",
}


def _zelle(spez, auspraegungen: Dict[str, str]):
    """Die Spez-Zelle einer Merkmalskombination.

    Die Auswahl folgt ``gates.generation_golden``: klein geschrieben,
    sonst unveraendert. Eine falsch benannte Auspraegung findet KEINE
    Zelle — und das ist gewollt, statt still auf eine beliebige zu
    fallen.
    """
    gesucht = {k: str(v).strip().lower() for k, v in auspraegungen.items() if v}
    treffer = [z for z in spez.zellen if z.auspraegungen == gesucht]
    if not treffer:
        raise SystemExit(
            f"keine Spez-Zelle fuer {gesucht!r} — vorhanden sind "
            f"{[z.auspraegungen for z in spez.zellen]}"
        )
    return treffer[0]


def _generationsfelder(zelle) -> Dict[str, Any]:
    # Die Spez traegt die Modellpunkt-Felder als schlichte Werte
    # (spez/schema.py: Wert ist ein Typ-Alias, kein Traeger-Objekt).
    return dict(zelle.model_point)


def _lies_registriert(fall: Path, name: str) -> Any:
    """Eine registrierte Quelle des Falls lesen (ADR-002)."""
    return json.loads(
        fall_mod.eingang_datei(fall, name).read_text(encoding="utf-8")
    )


def baue_auftraege(
    lieferung: Dict[str, Any],
    bestand,
    spez,
    *,
    auspraegungen_je_police: Dict[str, Dict[str, str]],
    schichten: Optional[Dict[str, Any]] = None,
    anfangszustaende: Optional[Dict[str, Dict[str, Any]]] = None,
    plausibilitaet: Optional[Dict[str, Dict[str, str]]] = None,
    scheiben_mit_gamma1: bool = False,
    stoab_je_baustein: bool = False,
    red_anteil_kandidaten: Tuple[float, ...] = (),
) -> Tuple[List[Vertragspruefung], List[str], List[str]]:
    """Aus Lieferung und Bestand die Pruefauftraege je Vertrag.

    Rueckgabe ``(auftraege, schicht_ausgelassen, zustandslos)``: Fuer
    Policen mit Herabsetzungs-Anfangszustand UND ersetztem
    Wertvergleich (Plausibilitaets-Beleg, Aktuars-Entscheid) wird die
    Korrekturschicht AUSGEWIESEN ausgelassen — die Kombination ist in
    der Engine bewusst undefiniert, und wo der Wertvergleich ersetzt
    ist, rechnet die Schicht ohnehin in kein Urteil. OHNE Ersetzung
    bleibt der harte Engine-Waechter (kein stilles Weglassen).

    ``zustandslos`` sind Policen mit Vorgeschichte, aber ohne
    ableitbaren Anfangszustand: eine AUSGEWIESENE Pruefluecke, kein
    Abbruch (etabliertes Verhalten der ersten Lieferung — die Police
    faellt sichtbar rot, statt dass ein geratener Zustand still
    richtig aussieht). Ein Plausibilitaets-Antrag wird diesen Policen
    NICHT gewaehrt, sondern ausgewiesen verworfen: Ihr Systemwert
    rechnet mangels Zustand die Stammwelt, ein Korridor darum urteilt
    nichts, und die Kandidaten-Regeln brauchen den
    Herabsetzungszustand (im zweiten Lauf brach die blind ueber die
    Vorfallart-Reichweite verteilte Ersetzung den ganzen Lauf an der
    Engine-Wache ab, statt die rechenbaren Policen zu liefern).
    """
    zeilen = {str(r["police_id"]): r for _, r in bestand.iterrows()}
    auftraege: List[Vertragspruefung] = []
    schicht_ausgelassen: List[str] = []
    zustandslos: List[str] = []

    for eintrag in lieferung["vertraege"]:
        police = str(eintrag["police_id"])
        if police not in zeilen:
            raise SystemExit(
                f"Police {police} steht in der Erwartungswert-Lieferung, "
                "aber nicht im transformierten Bestand — die Stichprobe "
                "muss vom gelieferten Bestand gedeckt sein"
            )
        zeile = zeilen[police]
        if len(spez.zellen) > 1 and police not in auspraegungen_je_police:
            raise SystemExit(
                f"Police {police}: keine Auspraegungen fuer die Zellwahl — "
                "die transformierten Zeilen (--zeilen) decken sie nicht")
        zelle = _zelle(spez, auspraegungen_je_police.get(police, {}))
        mp = model_point_kwargs(zeile, _generationsfelder(zelle))
        zustand = (anfangszustaende or {}).get(police, {})
        if "sum_insured" in zustand:
            # Der Stamm fuehrt die aktuelle Gesamtsumme; die Bewertung
            # der Vorgeschichts-Welt rechnet auf dem Ursprungs- bzw.
            # Grund-Modellpunkt (Fall-Ableitungsregel der
            # Uebernahmestrecke).
            mp["sum_insured"] = float(zustand["sum_insured"])

        punkte = []
        for p in eintrag["punkte"]:
            if not p.get("erwartet"):
                raise SystemExit(
                    f"Police {police}: Pruefpunkt {p['anlass']} ohne "
                    "gelieferte Werte — eine leere Erwartung ist kein "
                    "bestandener Vergleich"
                )
            punkte.append(Pruefpunkt(
                monate=int(p["monate"]),
                erwartet={k: float(v) for k, v in p["erwartet"].items()},
                anlass=str(p["anlass"]),
                parameter={k: float(v)
                           for k, v in (p.get("parameter") or {}).items()},
            ))

        historientyp = str(eintrag.get("historientyp", "unbekannt"))
        beitragsfrei = eintrag.get(
            "beitragsfrei_seit_jahr", zustand.get("beitragsfrei_seit_jahr"))
        ohne_zustand = (
            historientyp not in ("ohne_vorgeschichte", "unbekannt")
            and not zustand.get("scheiben")
            and zustand.get("reduktion") is None
            and beitragsfrei is None)
        if ohne_zustand:
            zustandslos.append(police)
        gewaehrt = dict((plausibilitaet or {}).get(police, {}))
        if gewaehrt and zustand.get("reduktion") is None:
            # Die Reichweite des Belegs (Vorfallart) trifft mehr
            # Policen, als die Ersetzungs-Regeln tragen: ALLE
            # Regel-Tatbestaende (Kandidaten-Rechnung fuer
            # kVx_MRV/BJB/RKW, Abzugskonventions-Bound fuer RKW)
            # beziehen sich auf den Herabsetzungs-ANFANGSZUSTAND. Ohne
            # ihn entfaellt der Antrag ausgewiesen — zwei Faelle:
            # (a) kein ableitbarer Zustand (zustandslos, Korrektur 9):
            #     der Systemwert rechnet eine falsche Welt, ein
            #     Korridor darum urteilt nichts;
            # (b) VOLLSTAENDIG bestimmter Zustand ohne reduktion
            #     (Serien-IST-Struktur, Ausweitung 11): der
            #     Wertvergleich ist wieder tauglich, eine Ersetzung
            #     hat keinen Tatbestand mehr — im zweiten Lauf brach
            #     A-M1 sonst an der Engine-Wache (Korrektur 12).
            # main weist die Policen im Ergebnis aus.
            gewaehrt = {}

        auftraege.append(Vertragspruefung(
            police_id=police,
            model_point=mp,
            historientyp=historientyp,
            punkte=tuple(punkte),
            beitragsfrei_seit_jahr=beitragsfrei,
            monate_ta=eintrag.get("monate_ta"),
            scheiben=tuple(zustand.get("scheiben", ())),
            quell_komponenten=zustand.get("quell_komponenten"),
            reduktion=zustand.get("reduktion"),
            # Die Kandidatenmenge ist eine Eigenschaft der QUELL-LAGE
            # (eine Auskunft je Fall), kein Policen-Datum — sie greift
            # genau dort, wo ein Herabsetzungs-Anfangszustand behauptet
            # wird; die Engine wehrt sie ohne einen solchen ab.
            reduktion_kandidaten=(
                tuple(red_anteil_kandidaten)
                if zustand.get("reduktion") else ()),
            plausibilitaet=gewaehrt,
            scheiben_mit_gamma1=scheiben_mit_gamma1,
            stoab_je_baustein=stoab_je_baustein,
            **_schicht_felder(_schicht_fuer(
                police, zustand, (schichten or {}).get(police),
                gewaehrt, schicht_ausgelassen)),
        ))
    # Der Ausweis der Prueflueke gehoert in den BELEG, nicht nur nach
    # stderr — im zweiten Lauf hielt der Aktuar 20 solcher Policen fuer
    # einen Systemfehler, weil das Ergebnis-JSON die Ursache nirgends
    # nannte (main haengt die Zustandswarnungen deshalb an das
    # Ergebnis an).
    return auftraege, schicht_ausgelassen, sorted(zustandslos)


def _schicht_fuer(
    police: str,
    zustand: Dict[str, Any],
    schicht_eintrag: Any,
    plausibilitaet: Optional[Dict[str, str]],
    schicht_ausgelassen: List[str],
) -> Any:
    """Ob die Schicht dieser Police in den Pruefauftrag geht.

    Herabsetzungs-Anfangszustand + Korrekturschicht ist in der Engine
    bewusst undefiniert: Die Schicht wurde auf der gelieferten
    Ist-Summe verankert, der Herabsetzungs-Pfad rechnet die
    Ursprungs-Welt im Zielverfahren. Ist der Wertvergleich der Police
    durch einen registrierten Plausibilitaets-Beleg ERSETZT
    (Aktuars-Entscheid), wird die Schicht ausgewiesen ausgelassen;
    ohne Ersetzung bleibt der Eintrag stehen und der Engine-Waechter
    benennt die Kombination hart.
    """
    if (zustand.get("reduktion") is not None
            and schicht_eintrag is not None and plausibilitaet):
        schicht_ausgelassen.append(police)
        return None
    return schicht_eintrag


def _schicht_felder(eintrag: Any) -> Dict[str, Any]:
    """Die Schicht-Felder einer Vertragspruefung aus dem Registereintrag.

    Flach = nur R_hist (rueckwaerts kompatibel); getrennt = hist/conv mit
    eigenem t_0. Die Engine haelt die beiden Residuen auseinander (9.13);
    hier werden nur die Felder verteilt.
    """
    if eintrag is None:
        return {}
    if isinstance(eintrag, Schichtparameter):
        return {"schicht": eintrag}
    aus: Dict[str, Any] = {}
    if "hist" in eintrag:
        aus["schicht"] = eintrag["hist"]
    if "conv" in eintrag:
        aus["schicht_conv"] = eintrag["conv"]
        aus["monate_t0"] = eintrag["monate_t0"]
    return aus


def _schichten(
    fall: Path, name: Optional[str], repo_root: Optional[Path] = None
) -> Dict[str, Any]:
    """Die Korrekturschicht je Police aus einer BINDBAREN Quelle.

    Die Schicht ist ein VERTRAGSATTRIBUT, das die Uebernahmestrecke
    ableitet (Grundsatzdokumentation 9.14: der Rechenkern bleibt
    historienfrei). Sie muss deshalb von aussen in den Pruefauftrag
    kommen — aus einer Quelle, die der Pruefer nicht selbst setzen
    kann: Ein freies Residuum waere kein Beweis, sondern ein Regler.

    Zwei bindbare Wege (Erweiterung 2026-09-01, Maintainer-Go):

    * eine REGISTRIERTE Quelle (wie bisher), oder
    * das ABGELEITETE Artefakt des System-Producers
      (``gates.verankerung_belegen``) unter ``<fall>/abgeleitet/`` —
      akzeptiert NUR mit Provenienzblock, dessen Bindungen dieser Lauf
      NACHRECHNET: Systemstand identisch, SHA-256 jeder Eingabe
      unveraendert. Nicht die Ablage macht den Beleg vertrauenswuerdig,
      sondern die Nachrechenbarkeit seiner Kette.

    Format je Police entweder FLACH (nur R_hist, rueckwaerts
    kompatibel)::

        {"<police_id>": {<Felder von Schichtparameter>}}

    oder GETRENNT nach den beiden Residuen (9.13, Entscheidung E2
    2026-08-31: separat erfassen)::

        {"<police_id>": {"hist": {...}, "conv": {..., "monate_t0": <n>}}}

    ``conv`` traegt seinen eigenen Verankerungszeitpunkt ``monate_t0``
    (Vertragsmonate am Migrationsstichtag — je Vertrag verschieden,
    obwohl der Kalendertag derselbe ist).
    """
    if not name:
        return {}
    kandidat = Path(name) if Path(name).is_absolute() else fall / name
    abgeleitet = (fall / "abgeleitet").resolve()
    if kandidat.is_file() and kandidat.resolve().is_relative_to(abgeleitet):
        roh = json.loads(kandidat.read_text(encoding="utf-8"))
        prov = roh.get("provenienz") if isinstance(roh, dict) else None
        if not isinstance(prov, dict) or "schichten" not in roh:
            raise SystemExit(
                f"abgeleitete Schichtdatei {name!r} ohne Provenienzblock "
                "— bindbare Belege erzeugt nur der Producer "
                "gates.verankerung_belegen")
        if repo_root is None:
            raise SystemExit(
                "abgeleitete Schichtdatei verlangt --repo-root fuer die "
                "Systemstand-Nachrechnung")
        ist_stand = systemstand(Path(repo_root).resolve())
        if prov.get("systemstand") != ist_stand:
            raise SystemExit(
                f"Schichtbeleg {name!r} traegt einen anderen Systemstand "
                "als diesen Lauf — nach jeder Codeaenderung neu erzeugen "
                "(gates.verankerung_belegen), nicht weiterverwenden")
        import hashlib as _hashlib

        for rel, soll in (prov.get("eingaben") or {}).items():
            pfad = fall / rel
            if not pfad.is_file():
                raise SystemExit(
                    f"Schichtbeleg-Eingabe fehlt: {rel} — die Kette ist "
                    "nicht nachrechenbar")
            ist = _hashlib.sha256(pfad.read_bytes()).hexdigest()
            if ist != soll:
                raise SystemExit(
                    f"Schichtbeleg-Eingabe {rel} wurde veraendert "
                    "(SHA-256 weicht ab) — Beleg neu erzeugen, nicht "
                    "weiterverwenden")
        roh = roh["schichten"]
    else:
        roh = _lies_registriert(fall, name)
    if not isinstance(roh, dict):
        raise SystemExit(
            f"Schichtdatei {name!r} traegt kein Objekt "
            "police_id -> Schichtparameter")

    def _parameter(police: str, felder: Dict[str, Any]) -> Schichtparameter:
        try:
            return Schichtparameter(
                **{k: (tuple(tuple(x) for x in v) if k == "vererbend" else v)
                   for k, v in felder.items()})
        except (TypeError, KorrekturschichtFehler) as exc:
            raise SystemExit(
                f"Schicht fuer Police {police} unbrauchbar: {exc}") from exc

    aus: Dict[str, Any] = {}
    for police, felder in roh.items():
        if not isinstance(felder, dict):
            raise SystemExit(f"Schicht fuer Police {police}: kein Objekt")
        if "hist" in felder or "conv" in felder:
            fremd = set(felder) - {"hist", "conv"}
            if fremd:
                raise SystemExit(
                    f"Schicht fuer Police {police}: unbekannte Teile "
                    f"{sorted(fremd)} neben hist/conv")
            eintrag: Dict[str, Any] = {}
            if "hist" in felder:
                eintrag["hist"] = _parameter(police, felder["hist"])
            if "conv" in felder:
                conv_felder = dict(felder["conv"])
                monate_t0 = conv_felder.pop("monate_t0", None)
                if monate_t0 is None:
                    raise SystemExit(
                        f"Schicht fuer Police {police}: conv ohne monate_t0 "
                        "— die Zweitverankerung rechnet ab t_0")
                eintrag["conv"] = _parameter(police, conv_felder)
                eintrag["monate_t0"] = int(monate_t0)
            aus[str(police)] = eintrag
        else:
            aus[str(police)] = _parameter(police, felder)
    return aus


def verweigerungs_grund(
    police: str, *, im_auftrag, zustandslos
) -> str:
    """Warum ein Plausibilitaets-Beleg fuer eine Police NICHT gilt.

    Drei getrennte Lagen: Der Beleg reicht ueber die Vorgeschichte
    weiter als der gepruefte Auftragsbestand — eine Police ausserhalb
    der Stichprobe/Lieferung hat gar keinen Auftrag, und ihr einen
    Zustands-Grund zu nennen waere eine irrefuehrende Auskunft an den
    Verantwortlichen Aktuar (Review-Befund B10).
    """
    if police not in im_auftrag:
        return "nicht_im_gepruefteten_auftragsbestand"
    if police in zustandslos:
        return "anfangszustand_nicht_ableitbar"
    return "kein_herabsetzungs_anfangszustand"


_VERWEIGERUNGS_TEXT = {
    "nicht_im_gepruefteten_auftragsbestand":
        "die Police steht nicht im gepruefteten Auftragsbestand "
        "(Stichprobe/Lieferung)",
    "anfangszustand_nicht_ableitbar":
        "kein ableitbarer Anfangszustand",
    "kein_herabsetzungs_anfangszustand":
        "Zustand vollstaendig bestimmt, kein "
        "Herabsetzungs-Anfangszustand (Serien-IST-Struktur)",
}


def _stichprobe(beleg: Dict[str, Any], abnahme: str) -> Stichprobe:
    """Die GELIEFERTE Stichprobe, nicht eine hier gezogene."""
    schluessel = "A-M3" if abnahme == "A-M3" else "A-M1_A-M2"
    if schluessel not in beleg:
        raise SystemExit(
            f"Stichprobenbeleg kennt {schluessel!r} nicht "
            f"(vorhanden: {sorted(k for k in beleg if not k.islower())})"
        )
    d = beleg[schluessel]
    return Stichprobe(
        profil=d["profil"],
        parameter=d.get("parameter", {}),
        police_ids=tuple(d["police_ids"]),
        grundgesamtheit=int(d["grundgesamtheit"]),
    )


def main(argv: Optional[List[str]] = None) -> int:
    p = argparse.ArgumentParser(
        prog="python -m rechner_pipeline.gates.aktuartest_lauf",
        description="Den aktuariellen Test einer Abnahme fahren "
                    "(Produzent, kein Gate).")
    p.add_argument("--fall", required=True)
    p.add_argument("--abnahme", required=True, choices=sorted(ZIELNAME))
    p.add_argument("--generation", required=True,
                   help="Knoten-Id der Tarifgeneration, z. B. klv/tg2015")
    p.add_argument("--erwartungswerte", required=True,
                   help="REGISTRIERTE Quelle mit den Pruefpunkten")
    p.add_argument("--stichprobe", required=True,
                   help="REGISTRIERTE Quelle mit dem Ziehungsbeleg")
    p.add_argument("--bestand", required=True,
                   help="transformierter Bestand (Parquet)")
    p.add_argument("--zeilen", default=None,
                   help="transformierte Zeilen (gates.transformation_anwenden "
                        "--zeilen) — Pflicht, sobald die Spez mehr als eine "
                        "Zelle traegt (Zellwahl je Police)")
    p.add_argument("--vorgeschichte", default=None,
                   help="REGISTRIERTE Metadatenliste der Geschaeftsvorfaelle "
                        "vor dem Stichtag (POLNR;GEVO;DATUM) — traegt die "
                        "Anfangszustaende (Alt-Scheiben, Alt-Absetzung) je "
                        "Police der Stichprobe")
    p.add_argument("--red-anteile-datei", dest="red_anteile_datei",
                   default=None, metavar="REGISTRIERTE_DATEI",
                   help="REGISTRIERTE Nachlieferung der fortgefuehrten "
                        "Beitragsanteile (POLNR;GEVO;DATUM;ANTEIL) — fuer "
                        "die Zeichnung bindbar, anders als --red-anteil")
    p.add_argument("--red-anteil", dest="red_anteile", action="append",
                   default=[], metavar="POLNR=ANTEIL",
                   help="nachgelieferter fortgefuehrter Beitragsanteil einer "
                        "Alt-Absetzung, deren Beitragsgleichung entfaellt "
                        "(wiederholbar)")
    p.add_argument("--plausibilitaet-beleg", dest="plausibilitaet_beleg",
                   default=None, metavar="REGISTRIERTE_DATEI",
                   help="REGISTRIERTE Auskunft der abgebenden Gesellschaft, "
                        "dass der gelieferte Wert einer Groesse kein "
                        "herleitbarer Erwartungswert ist. Ohne diesen Beleg "
                        "wird jede Groesse wertverglichen.")
    p.add_argument("--plausibilitaet-groesse", dest="plausibilitaet_groessen",
                   action="append", default=[], metavar="GROESSE",
                   help="Groesse, deren Wertvergleich der Beleg ersetzt "
                        "(wiederholbar; nur Groessen mit Plausibilitaetsregel).")
    p.add_argument("--plausibilitaet-vorfallart",
                   dest="plausibilitaet_vorfallart", default=None,
                   metavar="ART",
                   help="Reichweite des Belegs als KRITERIUM: alle Vertraege "
                        "mit dieser Vorfallart in der Vorgeschichte — so, wie "
                        "die Auskunft ihre Reichweite bestimmt, statt ueber "
                        "eine getippte Policenliste.")
    p.add_argument("--red-anteil-kandidat", dest="red_anteil_kandidaten",
                   action="append", type=float, default=[],
                   metavar="ANTEIL",
                   help="BELEGTER Tarif-Kandidat des Herabsetzungsanteils "
                        "(wiederholbar), wenn der exakte Anteil bei der "
                        "Quelle endgueltig nicht feststellbar ist. Die "
                        "Plausibilitaetsregeln rechnen dann den Korridor "
                        "ueber die Kandidatenmenge statt um einen "
                        "Punktwert; gilt fuer alle Vertraege mit "
                        "Herabsetzungs-Anfangszustand.")
    p.add_argument("--erhoehungssatz", dest="erhoehungssatz", type=float,
                   default=None, metavar="SATZ",
                   help="BELEGTER Dynamiksatz der Alt-Erhoehungen (Tarifwerk: "
                        "S' = e * S^ges); ohne ihn wird je Vertrag aus dem "
                        "Jahresbeitrag zerlegt")
    p.add_argument(
        "--scheiben-mit-gamma1", dest="scheiben_mit_gamma1",
        action="store_true",
        help="Erhoehungsscheiben rechnen die VOLLE Beitragsformel "
             "(mit gamma1) — Tarifwerks-Eigenschaft der Lieferung laut "
             "ihren Dokumenten (Lieferung 2: eigenstaendiger Baustein "
             "mit eigener Wertermittlung); ohne Flag gilt die "
             "GrundVS-Regel der ersten Lieferung.")
    p.add_argument(
        "--stoab-je-baustein", dest="stoab_je_baustein",
        action="store_true",
        help="Stornoabschlag-Grenzen greifen JE BAUSTEIN (Grund und "
             "jede Erhoehungsscheibe einzeln, RKW = Summe der "
             "Baustein-Rueckkaufswerte) — Tarifwerks-Eigenschaft der "
             "Lieferung laut Bedingungswerk Ziffer 4; ohne Flag gelten "
             "die Grenzen je Vertrag (PLV-Regel, Tarifplan 6).")
    p.add_argument("--red-verfahren", dest="red_verfahren",
                   default=PROSPEKTIV, choices=sorted(VERFAHREN),
                   help="Verfahren der Beitragsherabsetzung (Eigenschaft "
                        "des Migrationsfalls; Vorgabe: Zielverfahren "
                        "prospektiv)")
    p.add_argument(
        "--schicht", dest="schicht", default=None,
        help="REGISTRIERTE Quelle mit der Korrekturschicht je Police "
             "(police_id -> Schichtparameter). Sie ist ein Vertragsattribut, "
             "das die Uebernahmestrecke ableitet (9.14) — der Rechenkern "
             "bleibt historienfrei. Ohne Angabe rechnet der Test ohne "
             "Schicht; das Residuum am Verankerungspunkt bleibt dann eine "
             "Restgroesse statt einer getragenen.")
    p.add_argument("--repo-root", dest="repo_root", default=".")
    p.add_argument("--out", default=None,
                   help="Zielpfad (Vorgabe: <fall>/abgeleitet/berichte/...)")
    args = p.parse_args(argv)

    fall = Path(args.fall).resolve()
    if not (fall / "fall.json").is_file():
        print(f"Kein Fall-Arbeitsbereich: {fall}", file=sys.stderr)
        return 2

    lieferung = _lies_registriert(fall, args.erwartungswerte)
    beleg = _lies_registriert(fall, args.stichprobe)
    spez = lade_spez(fall, args.generation)
    bestand = read_portfolio(Path(args.bestand))

    gemeldet = lieferung.get("test")
    if gemeldet and gemeldet != args.abnahme:
        print(f"Die Lieferung gehoert zu {gemeldet}, gefahren werden soll "
              f"{args.abnahme}", file=sys.stderr)
        return 2

    # Die Merkmalsauspraegungen je Police waehlen die Spez-Zelle. Sie
    # kommen aus den transformierten Zeilen (der Stamm traegt sie nicht);
    # ohne --zeilen entscheidet nur eine einzellige Spez von selbst.
    from rechner_pipeline.gates.migrationssuite_lauf import (
        auspraegungen_je_police,
    )

    if args.zeilen is not None:
        zeilen = json.loads(Path(args.zeilen).read_text(encoding="utf-8"))
        if not isinstance(zeilen, list):
            print(f"{args.zeilen}: erwartet wird die Zeilenliste aus "
                  "gates.transformation_anwenden --zeilen", file=sys.stderr)
            return 2
        auspraegungen = auspraegungen_je_police(spez, zeilen)
    elif len(spez.zellen) > 1:
        print(f"Spez traegt {len(spez.zellen)} Zellen — ohne --zeilen ist "
              "die Zellwahl je Police nicht bestimmbar", file=sys.stderr)
        return 2
    else:
        auspraegungen = {
            str(r["police_id"]): {}
            for _, r in bestand.iterrows()
        }

    # Die REGISTRIERTE Vorgeschichte einmal lesen: Sie traegt die
    # Anfangszustaende UND die Reichweite eines Plausibilitaets-Belegs.
    import csv

    vorgeschichte: List[Dict[str, str]] = []
    if args.vorgeschichte is not None:
        with fall_mod.eingang_datei(fall, args.vorgeschichte).open(
                encoding="utf-8") as datei:
            vorgeschichte = list(csv.DictReader(datei, delimiter=";"))

    anfangszustaende = None
    if args.vorgeschichte is not None:
        from rechner_pipeline.gates.migrationssuite_lauf import (
            VORGABE,
            anfangszustaende_je_police,
        )

        red_anteile: Dict[str, float] = {}
        red_anteile_je_datum: Dict[str, Dict[str, float]] = {}
        if args.red_anteile_datei is not None:
            with fall_mod.eingang_datei(
                    fall, args.red_anteile_datei).open(encoding="utf-8") as d:
                for zeile in csv.DictReader(d, delimiter=";"):
                    if zeile.get("GEVO") == "RED" and zeile.get("ANTEIL"):
                        red_anteile[str(zeile["POLNR"])] = float(
                            zeile["ANTEIL"])
                        if zeile.get("DATUM"):
                            red_anteile_je_datum.setdefault(
                                str(zeile["POLNR"]), {})[
                                    str(zeile["DATUM"])] = float(
                                        zeile["ANTEIL"])
        for eintrag in args.red_anteile:
            police, _, wert = eintrag.partition("=")
            if not police or not wert:
                print(f"--red-anteil {eintrag!r}: erwartet POLNR=ANTEIL",
                      file=sys.stderr)
                return 2
            red_anteile[police.strip()] = float(wert)
        # Ankerwerte fuer den Rueckfallweg: der gelieferte Wert am
        # Verankerungszeitpunkt je Vertrag der Stichprobe.
        anker: Dict[str, Any] = {}
        for eintrag in lieferung["vertraege"]:
            punkte = eintrag.get("punkte") or []
            erster = next(
                (p for p in punkte if p.get("anlass") == "uebernahme"), None)
            if erster and "kVx_MRV" in (erster.get("erwartet") or {}):
                anker[str(eintrag["police_id"])] = (
                    int(erster["monate"]),
                    float(erster["erwartet"]["kVx_MRV"]))
        anfangszustaende, zustandswarnungen = anfangszustaende_je_police(
            spez, zeilen if args.zeilen is not None else [],
            vorgeschichte, bestand, spalten=dict(VORGABE),
            red_verfahren=args.red_verfahren, red_anteile=red_anteile,
            red_anteile_je_datum=red_anteile_je_datum,
            auspraegungen=auspraegungen,
            erhoehungssatz=args.erhoehungssatz, anker=anker,
            red_anteil_kandidaten=tuple(args.red_anteil_kandidaten),
            scheiben_mit_gamma1=args.scheiben_mit_gamma1)
        for w in zustandswarnungen:
            print(f"WARNUNG Anfangszustand nicht ableitbar: {w}",
                  file=sys.stderr)

    # Ersetzter Wertvergleich: NUR aus einer registrierten Quelle. Ein
    # Kommandozeilen-Text waere fuer die Zeichnung nicht bindbar — die
    # menschlichen Gates hashen den Eingang, nicht den Aufruf.
    plausibilitaet: Dict[str, Dict[str, str]] = {}
    if args.plausibilitaet_beleg is not None:
        if not args.plausibilitaet_groessen or not args.plausibilitaet_vorfallart:
            print("--plausibilitaet-beleg verlangt --plausibilitaet-groesse "
                  "und --plausibilitaet-vorfallart — ein Beleg ohne Groesse "
                  "und Reichweite ist keiner", file=sys.stderr)
            return 2
        if not vorgeschichte:
            print("--plausibilitaet-vorfallart verlangt --vorgeschichte: die "
                  "Reichweite folgt aus der Metadatenliste", file=sys.stderr)
            return 2
        # Der Beleg muss REGISTRIERT sein — eine unregistrierte Datei
        # faellt hier hart auf, bevor irgendein Vergleich entfaellt.
        beleg_pfad = fall_mod.eingang_datei(fall, args.plausibilitaet_beleg)
        art = args.plausibilitaet_vorfallart
        betroffen = sorted({
            str(z["POLNR"]) for z in vorgeschichte if z.get("GEVO") == art
        })
        if not betroffen:
            print(f"Vorfallart {art!r} kommt in der Vorgeschichte nicht vor — "
                  "der Beleg traefe keinen Vertrag", file=sys.stderr)
            return 2
        quelle = (
            f"Kein herleitbarer Erwartungswert laut {beleg_pfad.name} "
            f"(Reichweite: Vorgeschichte mit Vorfallart {art})"
        )
        plausibilitaet = {
            police: {g: quelle for g in args.plausibilitaet_groessen}
            for police in betroffen
        }

    schichten = _schichten(fall, args.schicht,
                           repo_root=Path(args.repo_root).resolve())
    auftraege, schicht_ausgelassen, zustandslos = baue_auftraege(
        lieferung, bestand, spez, auspraegungen_je_police=auspraegungen,
        anfangszustaende=anfangszustaende, plausibilitaet=plausibilitaet,
        schichten=schichten,
        scheiben_mit_gamma1=args.scheiben_mit_gamma1,
        stoab_je_baustein=args.stoab_je_baustein,
        red_anteil_kandidaten=tuple(args.red_anteil_kandidaten))
    for police in schicht_ausgelassen:
        print(f"WARNUNG Police {police}: Korrekturschicht nicht im "
              "Pruefpfad — Herabsetzungs-Anfangszustand, Wertvergleich "
              "durch Plausibilitaets-Beleg ersetzt", file=sys.stderr)
    # Die Wahrheit ueber gewaehrte Ersetzungen steht im AUFTRAG — von
    # dort rekonstruieren, nicht die Verteil-Logik nachbauen.
    vergeben = {a.police_id: bool(a.plausibilitaet) for a in auftraege}
    plaus_verweigert = sorted(
        p for p in plausibilitaet if not vergeben.get(p, False))
    for police in plaus_verweigert:
        grund = _VERWEIGERUNGS_TEXT[verweigerungs_grund(
            police, im_auftrag=vergeben.keys(), zustandslos=zustandslos)]
        print(f"WARNUNG Police {police}: Plausibilitaets-Beleg nicht "
              f"angewandt — {grund}; die Police bleibt sichtbar im "
              "Wertvergleich", file=sys.stderr)
    stichprobe = _stichprobe(beleg, args.abnahme)
    profil = vorlage(args.abnahme, weite=str(
        stichprobe.parameter.get("weite") or stichprobe.profil))

    ergebnis = pruefe_stichprobe(
        auftraege, stichprobe, profil,
        transportsicherung={"lieferung": args.erwartungswerte},
        system=systemstand(Path(args.repo_root).resolve()),
        red_verfahren=args.red_verfahren,
    )
    if schicht_ausgelassen:
        # Ausgewiesene Auslassung gehoert in den Beleg, nicht nur nach
        # stderr — A-M1 liest das Ergebnis, nicht das Terminal.
        ergebnis["schicht_ausgelassen"] = sorted(schicht_ausgelassen)
    if zustandslos:
        ergebnis["anfangszustand_nicht_ableitbar"] = {
            "policen": zustandslos,
            "hinweis": (
                "Vorgeschichte vorhanden, Anfangszustand nicht ableitbar "
                "(siehe Zustandswarnungen des Laufs) — der Wertvergleich "
                "dieser Policen rechnet die Stammwelt und faellt "
                "erwartbar rot; Ursache beheben (z. B. Herabsetzungs-"
                "Anteile je Ereignis nachliefern: POLNR;GEVO;DATUM;"
                "ANTEIL), nicht Toleranzen weiten."),
        }
    if plaus_verweigert:
        # Eigenes Feld statt Unterpunkt der Zustandslos-Prueflueke:
        # Der Antrag entfaellt auch fuer Policen mit VOLLSTAENDIG
        # bestimmtem Zustand (Serien-IST-Struktur) — dort ist nichts
        # "nicht ableitbar", der Wertvergleich ist schlicht wieder
        # der Massstab.
        ergebnis["plausibilitaet_nicht_angewandt"] = {
            police: verweigerungs_grund(
                police, im_auftrag=vergeben.keys(),
                zustandslos=zustandslos)
            for police in plaus_verweigert
        }

    ziel = Path(args.out) if args.out else (
        fall / "abgeleitet" / "berichte" / ZIELNAME[args.abnahme])
    ziel.parent.mkdir(parents=True, exist_ok=True)
    with ziel.open("w", encoding="utf-8") as datei:
        json.dump(ergebnis, datei, indent=2, ensure_ascii=False, sort_keys=True)
        datei.write("\n")

    print(f"{args.abnahme}: {ergebnis['anzahl']} Vertraege, "
          f"{ergebnis['bestanden']} bestanden, "
          f"{ergebnis['fehlgeschlagen']} mit Befund")
    print(f"  Urteil: {'bestanden' if ergebnis['test_bestanden'] else 'NICHT bestanden'}")
    print(f"  {ziel}")
    return 0


if __name__ == "__main__":  # pragma: no cover
    raise SystemExit(main())
