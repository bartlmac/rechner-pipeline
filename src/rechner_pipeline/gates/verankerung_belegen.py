"""``verankerung_belegen`` — der Schichtbeleg der Uebernahme (Producer).

Schliesst die Luecke zwischen Konzept und Werkzeug (Maintainer-Go
2026-09-01, gefunden im zweiten Baldrian-Lauf): Die Kern-API der
Verankerung existiert seit dem Migrationszugang
(:func:`rechner_pipeline.bestand.migrationszugang.uebernehmen` —
Residuum bilden, Schicht verankern), und der aktuarielle Test verlangt
den Schichtbeleg zu Recht als BINDBARE Quelle ("ein Residuum, das der
Pruefer selbst setzen koennte, waere kein Beweis, sondern ein Regler").
Das Kommando dazwischen fehlte; die Belege des ersten Laufs kamen aus
einer Fall-Sonderstrecke.

Der Producer rechnet je Police DETERMINISTISCH aus vier gebundenen
Eingaben — Verankerungstabelle (``verankerung.parquet``), Stamm,
Merkmalstabelle (Zellwahl) und der Fall-Spez — Residuum und
Schichtparameter, und schreibt den Beleg mit PROVENIENZBLOCK:
SHA-256 je Eingabe plus Systemstand. Der Konsument
(``aktuartest_lauf --schicht``) akzeptiert das Artefakt nur, wenn er
diese Bindungen NACHRECHNEN kann — nicht, weil es irgendwo liegt.
Genau das loest das Regler-Problem: nicht Registrierung, sondern
Nachrechenbarkeit; Test und Beleg duerfen dann sogar vom selben
Operator gefahren werden, weil keiner von beiden einen freien Wert
setzen kann.

Die AUSGESTALTUNG (Formfunktion, ggf. Fenster) ist eine Entscheidung
des Operators (Skill-Pflichtschritt Tarifplan-Ausgestaltung) und wird
als Parameter im Beleg dokumentiert — der Producer trifft sie nicht.

Producer, kein Gate: Exit 0 nur, wenn JEDE Police getragen ist; sonst
Exit 1 mit Befundliste im Beleg — eine halbe Schichttabelle liesse die
Korrekturschicht den Rest fuer verankerungsfrei halten.

Knoten: klv
"""

from __future__ import annotations

import argparse
import hashlib
import json
import sys
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

from rechner_pipeline.bestand.migrationszugang import (
    FORMEN,
    MigrationszugangFehler,
    Uebernahme,
    uebernehmen,
)
from rechner_pipeline.gates._provenienz import systemstand
from rechner_pipeline.models.bestand import model_point_kwargs

#: Zustandsuebersetzung Verankerungstabelle -> Uebernahme-Zustand.
#: Die Tabelle spricht die Sprache des Zustandsmodells; die
#: Uebernahme-API dieselbe — die Identitaet steht hier trotzdem
#: explizit, damit ein neuer Tabellenwert hart faellt statt still
#: durchzulaufen.
ZUSTAENDE = ("beitragspflichtig", "beitragsfrei")


def _sha256(pfad: Path) -> str:
    return hashlib.sha256(pfad.read_bytes()).hexdigest()


def auspraegungen_aus_merkmalen(merkmale) -> Dict[str, Dict[str, str]]:
    """Zellwahl je Police aus der Merkmalstabelle (long-Format)."""
    aus: Dict[str, Dict[str, str]] = {}
    for _, zeile in merkmale.iterrows():
        aus.setdefault(str(zeile["police_id"]), {})[
            str(zeile["dimension"])] = str(zeile["auspraegung"])
    return aus


def _zelle(spez, auspraegungen: Dict[str, str]):
    gesucht = {k: str(v).strip().lower()
               for k, v in auspraegungen.items() if v}
    treffer = [z for z in spez.zellen if z.auspraegungen == gesucht]
    if not treffer:
        raise SystemExit(
            f"keine Spez-Zelle fuer {gesucht!r} — vorhanden sind "
            f"{[z.auspraegungen for z in spez.zellen]}")
    return treffer[0]


def _zustands_dk_prosp(
    mp_kwargs: Dict[str, Any],
    zustand: Dict[str, Any],
    monate_ta: int,
    *,
    scheiben_mit_gamma1: bool,
) -> Optional[float]:
    """Prospektiver Wert am t_a auf der ZUSTANDS-Welt (None = Stamm).

    Dieselben Welten wie in den Pruefstrecken: Erhoehungsscheiben,
    beitragsfreie Uebernahme, geteilter Vertrag. BASIS ist der
    GEFUEHRTE Wert (vx_mrv) — die Basis der gelieferten DECKKAP-Spalte
    und der Vergleichs-Engines. Bei Ein-Baustein-Welten faellt er mit
    der Deckungsrueckstellung zusammen (dort rechnet ``uebernehmen``
    selbst, drx-Konvention, identisch); bei Scheiben-Welten differieren
    beide um den Zillmer-/Zuschlagsrest der jungen Scheiben — auf der
    falschen Basis wuerde GENAU diese Differenz zum Phantom-rho
    (zweiter Baldrian-Lauf: 254 dynamik-Policen mit 400-750 EUR,
    7000286: exakt 744,01).
    """
    scheiben = tuple(zustand.get("scheiben", ()))
    pex = zustand.get("beitragsfrei_seit_jahr")
    reduktion = zustand.get("reduktion")
    if not scheiben and pex is None and reduktion is None:
        return None
    from rechner_pipeline.kern import ModelPoint, Rechenkern
    from rechner_pipeline.kern.rechenkern import (
        erhoehungs_scheibe,
        vertrags_monatsreserve,
    )

    grund_mp = ModelPoint(**mp_kwargs)
    kern = Rechenkern(grund_mp)
    if reduktion is not None:
        # Nur die PLV-Teilungsverfahren liefern diesen Zustand; unter
        # der Teilkuendigungs-Semantik fuehrt der Zustandsbau die
        # Police zustandslos (Ausweitung 16/17).
        from rechner_pipeline.kern.beitragsreduktion import (
            ReduzierterVertrag,
        )

        rv = ReduzierterVertrag.nach(
            kern, int(reduktion[0]), float(reduktion[1]))
        return rv.monatsreserve(monate_ta).vx_mrv
    if pex is not None:
        # Die beitragsfreie Reserve kennt im Kern nur einen Begriff.
        return kern.monatsreserve_beitragsfrei(int(pex), monate_ta)
    kerne = [
        (int(j), Rechenkern(erhoehungs_scheibe(
            grund_mp, int(j), float(s),
            gamma1_uebernehmen=scheiben_mit_gamma1)))
        for j, s in scheiben
    ]
    return vertrags_monatsreserve(kern, kerne, monate_ta).vx_mrv


def baue_schichtbeleg(
    verankerung,
    bestand,
    merkmale,
    spez,
    *,
    formfunktion: str,
    fenster: Optional[int] = None,
    anfangszustaende: Optional[Dict[str, Dict[str, Any]]] = None,
    scheiben_mit_gamma1: bool = False,
) -> Dict[str, Any]:
    """Schichtparameter je Police — der rechnende Kern des Producers.

    Rueckgabe: ``{"schichten": {police: {"hist": felder}},
    "befunde": [...], "summary": {...}}`` — das ``hist``-Format des
    Konsumenten (:func:`gates.aktuartest_lauf._schichten`); die Felder
    sind konstruktorkompatibel zu
    :class:`kern.korrekturschicht.Schichtparameter`.
    """
    stammzeilen = {str(z["police_id"]): z for _, z in bestand.iterrows()}
    mehrzellig = len(spez.zellen) > 1
    auspraegungen: Dict[str, Dict[str, str]] = {}
    if mehrzellig:
        if merkmale is None or len(merkmale) == 0:
            raise SystemExit(
                f"Spez traegt {len(spez.zellen)} Zellen — ohne "
                "Merkmalstabelle ist die Zellwahl je Police nicht "
                "bestimmbar")
        auspraegungen = auspraegungen_aus_merkmalen(merkmale)

    vertraege: List[Uebernahme] = []
    for _, zeile in verankerung.iterrows():
        police = str(zeile["police_id"])
        stamm = stammzeilen.get(police)
        if stamm is None:
            raise SystemExit(
                f"Police {police} steht in der Verankerungstabelle, aber "
                "nicht im Stamm — die Tabellen gehoeren zum selben Lauf")
        zustand = str(zeile["zustand_ta"])
        if zustand not in ZUSTAENDE:
            raise SystemExit(
                f"Police {police}: Verankerungszustand {zustand!r} ist "
                f"nicht abgebildet (bekannt: {list(ZUSTAENDE)})")
        if mehrzellig and police not in auspraegungen:
            raise SystemExit(
                f"Police {police}: keine Merkmalszeile — die Zellwahl ist "
                "nicht bestimmbar")
        generation = dict(_zelle(
            spez, auspraegungen.get(police, {})).model_point)
        mp = model_point_kwargs(stamm, generation)
        anfangszustand = (anfangszustaende or {}).get(police, {})
        if "sum_insured" in anfangszustand:
            # Die Bewertungs-Welt der Pruefstrecke: Ursprungs- bzw.
            # Grundsumme statt der aktuellen Gesamtsumme des Stamms.
            mp["sum_insured"] = float(anfangszustand["sum_insured"])
        vertraege.append(Uebernahme(
            police_id=int(police),
            model_point=mp,
            monate_ta=int(zeile["monate_ta"]),
            dk_ist=float(zeile["dk_ta"]),
            zustand=zustand,
            verweildauer=int(zeile["verweildauer_ta"]),
            # Zustands-Vertraege verankern auf ihrer ZUSTANDS-Welt —
            # sonst traegt die Schicht die Weltendifferenz als
            # Phantom-Residuum (zweiter Baldrian-Lauf, rho bis 0,04).
            dk_prosp_extern=_zustands_dk_prosp(
                mp, anfangszustand, int(zeile["monate_ta"]),
                scheiben_mit_gamma1=scheiben_mit_gamma1),
        ))

    ergebnisse = uebernehmen(
        vertraege, formfunktion=formfunktion, fenster=fenster)

    schichten: Dict[str, Any] = {}
    befunde: List[Dict[str, Any]] = []
    residuen: List[float] = []
    for e in ergebnisse:
        if e.getragen:
            schichten[str(e.police_id)] = {"hist": e.parameter.als_beleg()}
            residuen.append(e.residuum)
        else:
            befunde.append({"police_id": e.police_id, "befund": e.befund,
                            "residuum": e.residuum})
    summary = {
        "vertraege": len(ergebnisse),
        "getragen": len(schichten),
        "befunde": len(befunde),
        "residuum_summe": round(sum(residuen), 2),
        "residuum_max_abs": round(
            max((abs(r) for r in residuen), default=0.0), 2),
    }
    return {"schichten": schichten, "befunde": befunde, "summary": summary}


def main(argv: Optional[List[str]] = None) -> int:
    p = argparse.ArgumentParser(
        prog="python -m rechner_pipeline.gates.verankerung_belegen",
        description=(
            "Schichtbeleg der Uebernahme erzeugen (Korrekturschicht je "
            "Police aus verankerung.parquet). Producer, kein Gate."))
    p.add_argument("--fall", required=True)
    p.add_argument("--repo-root", dest="repo_root", required=True)
    p.add_argument("--generation", required=True,
                   help="Knoten-Id der Tarifgeneration, z. B. klv/tg2015")
    p.add_argument("--uebernahme", default=None,
                   help="Uebernahme-Verzeichnis (Vorgabe: "
                        "<fall>/abgeleitet/bestand)")
    p.add_argument("--formfunktion", required=True, choices=sorted(FORMEN),
                   help="Ausgestaltungs-Entscheidung des Operators "
                        "(Skill-Pflichtschritt) — wird im Beleg "
                        "dokumentiert")
    p.add_argument("--fenster", type=int, default=None,
                   help="Amortisationsfenster (nur konstantes_fenster)")
    p.add_argument("--zeilen", default=None,
                   help="transformierte Zeilen (fuer den Zustandsbau; "
                        "Pflicht bei mehrzelliger Spez mit Vorgeschichte)")
    p.add_argument("--vorgeschichte", default=None,
                   help="REGISTRIERTE GeVo-Vorgeschichte. Mit ihr "
                        "verankert der Producer jede Police auf ihrer "
                        "ZUSTANDS-Welt (Scheiben, Beitragsfreistellung, "
                        "Herabsetzung) — ohne sie traegt die Schicht die "
                        "Weltendifferenz als Phantom-Residuum.")
    p.add_argument("--erhoehungssatz", dest="erhoehungssatz", type=float,
                   default=None, metavar="SATZ",
                   help="belegter Dynamiksatz (siehe aktuartest_lauf)")
    p.add_argument("--red-verfahren", dest="red_verfahren",
                   default=None,
                   help="Verfahren der Beitragsherabsetzung (siehe "
                        "aktuartest_lauf); Vorgabe: Zielverfahren")
    p.add_argument("--red-anteil", dest="red_anteile", action="append",
                   default=[], metavar="POLNR=ANTEIL",
                   help="dokumentierte Anteils-Lesart je Police "
                        "(wiederholbar)")
    p.add_argument("--red-anteil-kandidat", dest="red_anteil_kandidaten",
                   action="append", type=float, default=[],
                   metavar="ANTEIL",
                   help="belegter Tarif-Kandidat (wiederholbar, siehe "
                        "aktuartest_lauf)")
    p.add_argument("--scheiben-mit-gamma1", dest="scheiben_mit_gamma1",
                   action="store_true",
                   help="volle Beitragsformel der Scheiben (siehe "
                        "aktuartest_lauf)")
    p.add_argument("--anker-erwartungswerte", dest="anker_quelle",
                   default=None, metavar="REGISTRIERTE_DATEI",
                   help="registrierte Erwartungswerte am "
                        "Verankerungszeitpunkt (siehe migrationssuite_lauf)")
    p.add_argument("--out", default=None,
                   help="Zielpfad (Vorgabe: <fall>/abgeleitet/schichten/"
                        "verankerung_schichten.json)")
    args = p.parse_args(argv)

    import pandas as pd

    from rechner_pipeline.bestand.parquet_io import read_portfolio
    from rechner_pipeline.spez.validierung import lade_spez, spez_pfad

    fall = Path(args.fall)
    ueber = Path(args.uebernahme) if args.uebernahme else (
        fall / "abgeleitet" / "bestand")
    pfade = {
        "verankerung": ueber / "verankerung.parquet",
        "bestand": ueber / "bestand.parquet",
    }
    for name, pfad in pfade.items():
        if not pfad.is_file():
            print(f"verankerung_belegen: {name}-Tabelle fehlt: {pfad}",
                  file=sys.stderr)
            return 2
    merkmale_pfad = ueber / "merkmale.parquet"
    merkmale = (pd.read_parquet(merkmale_pfad)
                if merkmale_pfad.is_file() else None)

    spez = lade_spez(fall, args.generation)
    bestand = read_portfolio(pfade["bestand"])

    anfangszustaende: Optional[Dict[str, Dict[str, Any]]] = None
    if args.vorgeschichte is not None:
        # Dieselbe Zustandsbau-Maschinerie wie in den Pruefstrecken —
        # die Verankerung MUSS auf derselben Welt stehen, auf der
        # spaeter bewertet wird (spaete Imports: gates-Geschwister).
        import csv

        from rechner_pipeline import fall as fall_mod
        from rechner_pipeline.gates.migrationssuite_lauf import (
            VORGABE,
            anfangszustaende_je_police,
            auspraegungen_je_police,
        )
        from rechner_pipeline.kern.beitragsreduktion import PROSPEKTIV

        if args.zeilen is not None:
            zeilen = json.loads(
                Path(args.zeilen).read_text(encoding="utf-8"))
            auspraegungen = auspraegungen_je_police(spez, zeilen)
        elif len(spez.zellen) > 1:
            print("verankerung_belegen: mehrzellige Spez mit "
                  "Vorgeschichte verlangt --zeilen", file=sys.stderr)
            return 2
        else:
            zeilen = []
            auspraegungen = {
                str(r["police_id"]): {} for _, r in bestand.iterrows()}
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
        anker: Dict[str, Tuple[int, float]] = {}
        if args.anker_quelle is not None:
            quelle = json.loads(fall_mod.eingang_datei(
                fall, args.anker_quelle).read_text(encoding="utf-8"))
            for v in quelle.get("vertraege", []):
                erster = next(
                    (pkt for pkt in v.get("punkte", [])
                     if pkt.get("anlass") == "uebernahme"
                     and "kVx_MRV" in (pkt.get("erwartet") or {})), None)
                if erster:
                    anker[str(v["police_id"])] = (
                        int(erster["monate"]),
                        float(erster["erwartet"]["kVx_MRV"]))
        anfangszustaende, warnungen = anfangszustaende_je_police(
            spez, zeilen, vorgeschichte, bestand, spalten=dict(VORGABE),
            red_verfahren=args.red_verfahren or PROSPEKTIV,
            red_anteile=red_anteile, auspraegungen=auspraegungen,
            erhoehungssatz=args.erhoehungssatz, anker=anker,
            red_anteil_kandidaten=tuple(args.red_anteil_kandidaten),
            scheiben_mit_gamma1=args.scheiben_mit_gamma1)
        for w in warnungen:
            print(f"WARNUNG Anfangszustand nicht ableitbar: {w}",
                  file=sys.stderr)

    try:
        beleg = baue_schichtbeleg(
            pd.read_parquet(pfade["verankerung"]),
            bestand,
            merkmale,
            spez,
            formfunktion=args.formfunktion,
            fenster=args.fenster,
            anfangszustaende=anfangszustaende,
            scheiben_mit_gamma1=args.scheiben_mit_gamma1,
        )
    except MigrationszugangFehler as exc:
        print(f"verankerung_belegen: {exc}", file=sys.stderr)
        return 2

    eingaben = {
        str(pfade["verankerung"].relative_to(fall)): _sha256(
            pfade["verankerung"]),
        str(pfade["bestand"].relative_to(fall)): _sha256(pfade["bestand"]),
    }
    if merkmale is not None:
        eingaben[str(merkmale_pfad.relative_to(fall))] = _sha256(
            merkmale_pfad)
    eingaben[str(spez_pfad(fall, args.generation).relative_to(fall))] = (
        _sha256(spez_pfad(fall, args.generation)))
    beleg["provenienz"] = {
        "systemstand": systemstand(Path(args.repo_root)),
        "eingaben": eingaben,
        "parameter": {
            "generation": args.generation,
            "formfunktion": args.formfunktion,
            "fenster": args.fenster,
            "vorgeschichte": args.vorgeschichte,
            "erhoehungssatz": args.erhoehungssatz,
            "red_verfahren": args.red_verfahren,
            "red_anteile": sorted(args.red_anteile),
            "red_anteil_kandidaten": sorted(args.red_anteil_kandidaten),
            "scheiben_mit_gamma1": args.scheiben_mit_gamma1,
            "anker_erwartungswerte": args.anker_quelle,
        },
    }

    out = Path(args.out) if args.out else (
        fall / "abgeleitet" / "schichten" / "verankerung_schichten.json")
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(beleg, ensure_ascii=False, indent=1,
                              sort_keys=True) + "\n", encoding="utf-8")
    s = beleg["summary"]
    print(f"verankerung_belegen: {s['getragen']}/{s['vertraege']} Policen "
          f"getragen, Residuum-Summe {s['residuum_summe']}, "
          f"max |R| {s['residuum_max_abs']} -> {out}", file=sys.stderr)
    if beleg["befunde"]:
        print(f"verankerung_belegen: {len(beleg['befunde'])} Befunde — "
              "keine halbe Schichttabelle; Befunde entscheiden, dann neu "
              "erzeugen", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":  # pragma: no cover
    raise SystemExit(main())
