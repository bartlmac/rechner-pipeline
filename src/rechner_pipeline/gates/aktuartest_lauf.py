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
    anfangszustaende: Optional[Dict[str, Dict[str, Any]]] = None,
    plausibilitaet: Optional[Dict[str, Dict[str, str]]] = None,
) -> List[Vertragspruefung]:
    """Aus Lieferung und Bestand die Pruefauftraege je Vertrag."""
    zeilen = {str(r["police_id"]): r for _, r in bestand.iterrows()}
    auftraege: List[Vertragspruefung] = []

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

        auftraege.append(Vertragspruefung(
            police_id=police,
            model_point=mp,
            historientyp=str(eintrag.get("historientyp", "unbekannt")),
            punkte=tuple(punkte),
            beitragsfrei_seit_jahr=eintrag.get(
                "beitragsfrei_seit_jahr",
                zustand.get("beitragsfrei_seit_jahr")),
            monate_ta=eintrag.get("monate_ta"),
            scheiben=tuple(zustand.get("scheiben", ())),
            reduktion=zustand.get("reduktion"),
            plausibilitaet=(plausibilitaet or {}).get(police, {}),
        ))
    return auftraege


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
    p.add_argument("--red-anteil", dest="red_anteile", action="append",
                   default=[], metavar="POLNR=ANTEIL",
                   help="nachgelieferter fortgefuehrter Beitragsanteil einer "
                        "Alt-Absetzung, deren Beitragsgleichung entfaellt "
                        "(wiederholbar)")
    p.add_argument("--plausibilitaet-statt-vergleich",
                   dest="plausibilitaet", default=None,
                   metavar="REGISTRIERTE_DATEI",
                   help="REGISTRIERTE Auskunft der abgebenden Gesellschaft, "
                        "die je Police und Groesse belegt, dass der "
                        "gelieferte Wert kein tauglicher Vergleichsmassstab "
                        "ist (JSON: {\"begruendung\": ..., \"groessen\": "
                        "[...], \"policen\": [...]}). Ohne diesen Beleg "
                        "wird jede Groesse wertverglichen.")
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

    anfangszustaende = None
    if args.vorgeschichte is not None:
        from rechner_pipeline.gates.migrationssuite_lauf import (
            VORGABE,
            anfangszustaende_je_police,
        )
        import csv

        with fall_mod.eingang_datei(fall, args.vorgeschichte).open(
                encoding="utf-8") as datei:
            vorgeschichte = list(csv.DictReader(datei, delimiter=";"))
        red_anteile: Dict[str, float] = {}
        for eintrag in args.red_anteile:
            police, _, wert = eintrag.partition("=")
            if not police or not wert:
                print(f"--red-anteil {eintrag!r}: erwartet POLNR=ANTEIL",
                      file=sys.stderr)
                return 2
            red_anteile[police.strip()] = float(wert)
        anfangszustaende, zustandswarnungen = anfangszustaende_je_police(
            spez, zeilen if args.zeilen is not None else [],
            vorgeschichte, bestand, spalten=dict(VORGABE),
            red_verfahren=args.red_verfahren, red_anteile=red_anteile,
            auspraegungen=auspraegungen,
            erhoehungssatz=args.erhoehungssatz)
        for w in zustandswarnungen:
            print(f"WARNUNG Anfangszustand nicht ableitbar: {w}",
                  file=sys.stderr)

    # Ersetzter Wertvergleich: NUR aus einer registrierten Quelle. Ein
    # Kommandozeilen-Text waere fuer die Zeichnung nicht bindbar — die
    # menschlichen Gates hashen den Eingang, nicht den Aufruf.
    plausibilitaet: Dict[str, Dict[str, str]] = {}
    if args.plausibilitaet is not None:
        beleg = _lies_registriert(fall, args.plausibilitaet)
        begruendung = str(beleg.get("begruendung", "")).strip()
        groessen = [str(g) for g in beleg.get("groessen", [])]
        policen = [str(x) for x in beleg.get("policen", [])]
        if not begruendung or not groessen or not policen:
            print(f"{args.plausibilitaet}: erwartet werden nichtleere Felder "
                  "begruendung, groessen und policen", file=sys.stderr)
            return 2
        quelle = f"{begruendung} [Beleg: {args.plausibilitaet}]"
        plausibilitaet = {
            police: {groesse: quelle for groesse in groessen}
            for police in policen
        }

    auftraege = baue_auftraege(
        lieferung, bestand, spez, auspraegungen_je_police=auspraegungen,
        anfangszustaende=anfangszustaende, plausibilitaet=plausibilitaet)
    stichprobe = _stichprobe(beleg, args.abnahme)
    profil = vorlage(args.abnahme, weite=str(
        stichprobe.parameter.get("weite") or stichprobe.profil))

    ergebnis = pruefe_stichprobe(
        auftraege, stichprobe, profil,
        transportsicherung={"lieferung": args.erwartungswerte},
        system=systemstand(Path(args.repo_root).resolve()),
        red_verfahren=args.red_verfahren,
    )

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
