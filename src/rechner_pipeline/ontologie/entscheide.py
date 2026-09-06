"""``entscheide`` — die endgueltige Diskrepanz-Aufloesung als CLI (A-Q1).

Der Vorgang, den das Gate A-Q1 meint: Die fachlich ZEICHNENDE Instanz
waehlt zwischen den Lesarten einer Diskrepanz und begruendet die Wahl.
WER entscheiden darf (ADR-018): ``--zeichnungsordnung`` und
``--freigabe-schluessel`` sind Pflicht; die Rolle wird aus dem
Schluessel-Fingerabdruck BESTIMMT, nicht behauptet — zugelassen ist,
wer die fachliche Abnahme A-Q1 zeichnen darf (die Entscheidungen sind
deren Substanz). Die Bindung (Rolle, Ordnungs-Hash, Schluesselklasse
Mensch oder Simulation, optional das Mandat) wandert in die
Entscheidung. Einen Alt-Weg ohne Ordnung gibt es nicht mehr: Eine
behauptete Rolle entscheidet nichts. Eine VORLAEUFIGE
(Agenten-)Aufloesung wird dabei ersetzt — das ist der
einzige erlaubte Weg, eine Aufloesung zu aendern; eine endgueltige
menschliche Entscheidung ist nur ueber eine neue T-Box-/A-Box-Revision
revidierbar, nicht durch Ueberschreiben.

Run via::

    python -m rechner_pipeline.ontologie.entscheide --fall faelle/baldrian-klv-tg2015 \\
        --diskrepanz "klv/tg2015/zelle:nichtraucher,einzel#zins" \\
        --wert 0.0125 --entscheider "Verantwortlicher Aktuar" \\
        --zeichnungsordnung faelle/zeichnungsordnung.json \\
        --freigabe-schluessel <pfad-zum-rollen-schluessel> \\
        --begruendung "Meldung massgeblich; Abzugsabgleich stuetzt 0,0125"

    # oder alle auf einmal derselben Lesart-Quelle folgend:
    ... --alle-vorlaeufigen --quelle Tarifrechner_KLV_TG2015.xlsm ...

    # VORLAEUFIG durch einen Agenten (kein Schluessel, keine Ordnung,
    # blockt jede Annahme, wird protokolliert — U1 Z1-06):
    python -m rechner_pipeline.ontologie.entscheide --fall faelle/<fall> \\
        --vorlaeufig --akteur claude-fable-5-1/migrationsfall-durchfuehren@abc1234 \\
        --alle-offenen --quelle Tarifrechner_KLV_TG2015.xlsm \\
        --begruendung "Golden Master reproduziert den Rechner; A-Q1 entscheidet"

Die vorlaeufige Aufloesung war bis dahin die einzige A-Box-Mutation ohne
Kommando und Ledger (ein Ad-hoc-Skript des Skills). Jetzt ist sie ein
Kommando mit Akteur-Konvention (P1), schreibt die Entscheidung mit
``vorlaeufig=True`` und ohne Zeichnung in die A-Box und haengt eine Zeile
an ``abgeleitet/protokoll/vorlaeufige_entscheide.jsonl`` (Akteur, Zeit,
Diskrepanzen, Quelle, A-Box-Hash vorher/nachher). Eine endgueltige
Entscheidung ersetzt sie; sie ersetzt nie eine endgueltige.

Knoten: klv
"""

from __future__ import annotations

import argparse
import datetime as _dt
import hashlib
import json
import sys
from pathlib import Path
from typing import List, Optional

from rechner_pipeline.ontologie.abox import lade, speichere, validate_abox
from rechner_pipeline.ontologie.diskrepanz import Beleg
from rechner_pipeline.ontologie.befuellung import (
    BefuellungsFehler,
    loese_diskrepanz_auf,
)


def _jetzt() -> str:
    return _dt.datetime.now(_dt.timezone.utc).isoformat(timespec="seconds")


PROTOKOLL = Path("abgeleitet") / "protokoll" / "vorlaeufige_entscheide.jsonl"


def _abox_sha256(fall: Path) -> Optional[str]:
    from rechner_pipeline.ontologie.abox import abox_pfad

    pfad = abox_pfad(fall)
    return hashlib.sha256(pfad.read_bytes()).hexdigest() if pfad.is_file() else None


def _vorlaeufig(args, fall: Path) -> int:
    """Vorlaeufige Aufloesung durch einen Agenten — Kommando statt Skript.

    Kein Schluessel, keine Ordnung, keine Zeichnung: Der Akteur
    (<modell>/<skill>@<sha>) ist der Entscheider, die Entscheidung traegt
    ``vorlaeufig=True`` und blockt damit jede Annahme (P2/P4). Was sie
    ist, steht im Protokoll des Falls — nicht nur in der A-Box, die eine
    endgueltige Entscheidung spaeter ueberschreibt (die ersetzte bleibt in
    der Entscheidungshistorie).
    """
    from rechner_pipeline.ontologie.befuellung import pruefe_akteur

    if args.zeichnungsordnung or args.freigabe_schluessel or args.rolle:
        print("entscheide: --vorlaeufig traegt weder Ordnung noch Schluessel "
              "noch Rolle — ein Agent zeichnet nicht, er legt vor",
              file=sys.stderr)
        return 2
    if not args.akteur:
        print("entscheide: --vorlaeufig verlangt --akteur "
              "<modell>/<skill>@<git-sha-kurz> (P1)", file=sys.stderr)
        return 2
    try:
        akteur = pruefe_akteur(args.akteur)
    except BefuellungsFehler as exc:
        print(f"entscheide: {exc}", file=sys.stderr)
        return 2
    if args.alle_offenen and (args.diskrepanz or args.wert is not None):
        print("entscheide: --alle-offenen schliesst --diskrepanz/--wert aus",
              file=sys.stderr)
        return 2
    if args.alle_offenen and not args.quelle:
        print("entscheide: --alle-offenen braucht --quelle", file=sys.stderr)
        return 2
    if not args.alle_offenen and (not args.diskrepanz or args.wert is None):
        print("entscheide: --diskrepanz und --wert sind erforderlich (oder "
              "--alle-offenen --quelle)", file=sys.stderr)
        return 2
    try:
        abox = lade(fall)
    except Exception as exc:  # noqa: BLE001
        print(f"entscheide: A-Box unlesbar: {exc}", file=sys.stderr)
        return 1
    vorher = _abox_sha256(fall)
    jetzt = _jetzt()
    entschieden: List[dict] = []
    try:
        if args.alle_offenen:
            for d in list(abox.diskrepanzen):
                if d.status == "aufgeloest" and not (
                    d.entscheidung is not None and d.entscheidung.vorlaeufig
                ):
                    continue
                lesart = next(
                    (l for l in d.lesarten
                     if any(p.quelle_datei == args.quelle for p in l.provenienz)),
                    None,
                )
                if lesart is None:
                    print(f"entscheide: {d.id}: keine Lesart aus "
                          f"{args.quelle!r} — einzeln entscheiden",
                          file=sys.stderr)
                    return 1
                _ersetze_vorlaeufig(abox, d.id)
                loese_diskrepanz_auf(
                    abox, d.id, lesart.wert, akteur, args.begruendung, jetzt,
                    vorlaeufig=True,
                )
                entschieden.append({"diskrepanz": d.id, "wert": lesart.wert})
        else:
            wert = _wert_parsen(args.wert)
            _ersetze_vorlaeufig(abox, args.diskrepanz)
            loese_diskrepanz_auf(
                abox, args.diskrepanz, wert, akteur, args.begruendung, jetzt,
                vorlaeufig=True,
            )
            entschieden.append({"diskrepanz": args.diskrepanz, "wert": wert})
    except BefuellungsFehler as exc:
        print(f"entscheide: {exc}", file=sys.stderr)
        return 1
    fehler = validate_abox(abox)
    if fehler:
        print("entscheide: A-Box nach Aufloesung inkonsistent: "
              + "; ".join(fehler), file=sys.stderr)
        return 1
    speichere(abox, fall)
    eintrag = {
        "zeit": jetzt,
        "akteur": akteur,
        "vorlaeufig": True,
        "quelle": args.quelle,
        "begruendung": args.begruendung,
        "entschieden": entschieden,
        "abox_sha256_vorher": vorher,
        "abox_sha256_nachher": _abox_sha256(fall),
    }
    protokoll = fall / PROTOKOLL
    protokoll.parent.mkdir(parents=True, exist_ok=True)
    with protokoll.open("a", encoding="utf-8") as fh:
        fh.write(json.dumps(eintrag, ensure_ascii=False, sort_keys=True,
                            default=str) + "\n")
    print(json.dumps({
        "fall": str(fall),
        "vorlaeufig": True,
        "akteur": akteur,
        "entschieden": [e["diskrepanz"] for e in entschieden],
        "protokoll": str(protokoll.relative_to(fall)),
        "verbleibend_offen": sorted(
            d.id for d in abox.diskrepanzen if d.status == "offen"),
    }, ensure_ascii=False, indent=2, sort_keys=True))
    return 0


def _wert_parsen(roh: str):
    try:
        return json.loads(roh)
    except json.JSONDecodeError:
        return roh


def main(argv: Optional[List[str]] = None) -> int:
    parser = argparse.ArgumentParser(
        prog="python -m rechner_pipeline.ontologie.entscheide",
        description="Diskrepanz(en) menschlich aufloesen (Gate A-Q1).",
    )
    parser.add_argument("--fall", required=True)
    parser.add_argument("--entscheider", default=None,
                        help="Pflicht fuer endgueltige Entscheide.")
    parser.add_argument("--begruendung", required=True)
    parser.add_argument(
        "--vorlaeufig", action="store_true",
        help="VORLAEUFIGE Aufloesung durch einen Agenten (kein Schluessel, "
        "keine Ordnung; blockt jede Annahme; wird unter "
        "abgeleitet/protokoll/ protokolliert). Verlangt --akteur.",
    )
    parser.add_argument(
        "--akteur", default=None,
        help="Akteur-Konvention <modell>/<skill>@<git-sha-kurz> (P1), nur "
        "mit --vorlaeufig.",
    )
    parser.add_argument(
        "--alle-offenen", action="store_true",
        help="Mit --vorlaeufig: alle offenen (oder bereits vorlaeufig "
        "aufgeloesten) Diskrepanzen zur Lesart der --quelle aufloesen.",
    )
    parser.add_argument(
        "--rolle", default=None,
        help="Optional: Rollenkennung (mensch/<funktion>); die Rolle wird "
        "aus dem Schluessel BESTIMMT, ein gesetzter Wert muss "
        "uebereinstimmen.",
    )
    parser.add_argument(
        "--zeichnungsordnung", default=None,
        help="Rollenbindung AUSSERHALB des Falls (wie gate_entscheid); "
        "Pflicht, zusammen mit --freigabe-schluessel (ADR-018).",
    )
    parser.add_argument(
        "--freigabe-schluessel", dest="freigabe_schluessel", default=None,
        help="Schluesseldatei der entscheidenden Rolle; ihr SHA-256 "
        "bestimmt die Rolle ueber die Ordnung. Pflicht.",
    )
    parser.add_argument(
        "--mandat", default=None,
        help="Mandatsdokument einer simulierten Rolle; sein SHA-256 wandert "
        "in die Zeichnung der Entscheidung (ADR-018).",
    )
    parser.add_argument("--diskrepanz", default=None,
                        help="ID (<knoten>#<feld>); alternativ --alle-vorlaeufigen.")
    parser.add_argument("--wert", default=None,
                        help="Gewaehlter Wert (JSON-Literal oder String).")
    parser.add_argument(
        "--alle-vorlaeufigen", action="store_true",
        help="Alle vorlaeufig aufgeloesten Diskrepanzen endgueltig "
        "entscheiden, jeweils zur Lesart der --quelle.",
    )
    parser.add_argument("--quelle", default=None,
                        help="Quelldatei, deren Lesart bei --alle-vorlaeufigen gilt.")
    parser.add_argument(
        "--beleg", default=None,
        help="FALL-RELATIVER Pfad der deterministischen Rechnung, die die "
             "Lesart stuetzt (z. B. abgeleitet/berichte/abzugsabgleich.json). "
             "Ihre Pruefsumme wird in die Entscheidung aufgenommen und von "
             "Gate P-Q3 nachgerechnet. Ohne Angabe traegt die Entscheidung "
             "nur ihre Begruendung -- eine Prosa-Nennung im Text sichert "
             "nichts.",
    )
    args = parser.parse_args(argv)

    fall = Path(args.fall)
    if args.vorlaeufig:
        return _vorlaeufig(args, fall)
    if args.akteur or args.alle_offenen:
        print("entscheide: --akteur und --alle-offenen gehoeren zu "
              "--vorlaeufig", file=sys.stderr)
        return 2
    if not args.entscheider:
        print("entscheide: --entscheider ist fuer eine endgueltige "
              "Entscheidung erforderlich", file=sys.stderr)
        return 2
    if not (args.zeichnungsordnung and args.freigabe_schluessel):
        print("entscheide: --zeichnungsordnung und --freigabe-schluessel "
              "sind Pflicht — die entscheidende Rolle wird aus dem "
              "Schluessel bestimmt, nicht behauptet (ADR-018); einen "
              "Alt-Weg --rolle mensch ohne Ordnung gibt es nicht mehr",
              file=sys.stderr)
        return 2
    from rechner_pipeline.models.zeichnung import (
        lade_zeichnungsordnung,
        rolle_darf_gate,
        zeichnung_fuer,
        zeichnungsrolle,
    )

    ordnung, ordnung_sha, fehler = lade_zeichnungsordnung(
        args.zeichnungsordnung, fall)
    if fehler:
        for f in fehler:
            print(f"entscheide: {f}", file=sys.stderr)
        return 2
    schluessel = Path(args.freigabe_schluessel)
    if not schluessel.is_file():
        print(f"entscheide: Schluesseldatei fehlt: {schluessel}",
              file=sys.stderr)
        return 2
    fingerprint = hashlib.sha256(schluessel.read_bytes()).hexdigest()
    rolle = zeichnungsrolle(ordnung, fingerprint)
    if rolle is None:
        print("entscheide: der Schluessel gehoert keiner Rolle der "
              "Zeichnungsordnung — Entscheide werden nicht anonym "
              "vollzogen", file=sys.stderr)
        return 1
    if not rolle_darf_gate(ordnung, rolle, "A-Q1"):
        print(f"entscheide: Rolle {rolle!r} zeichnet A-Q1 nicht — "
              "Diskrepanz-Entscheide vollzieht, wer die fachliche "
              "Abnahme zeichnet (ihre Substanz sind diese "
              "Entscheidungen); Agentenrollen legen vor", file=sys.stderr)
        return 1
    if args.rolle and args.rolle != rolle:
        print(f"entscheide: --rolle {args.rolle!r} widerspricht der "
              f"aus dem Schluessel bestimmten Rolle {rolle!r}",
              file=sys.stderr)
        return 2
    mandat_sha256 = None
    if args.mandat:
        mandat = Path(args.mandat)
        if not mandat.is_file():
            print(f"entscheide: --mandat {args.mandat!r} ist keine Datei",
                  file=sys.stderr)
            return 2
        mandat_sha256 = hashlib.sha256(mandat.read_bytes()).hexdigest()
    zeichnung = zeichnung_fuer(ordnung, ordnung_sha, fingerprint, mandat_sha256)
    try:
        abox = lade(fall)
    except Exception as exc:  # noqa: BLE001
        # Eine Fehlermeldung nennt den Weg hinaus: die A-Box ist kein
        # Handarbeitsartefakt, sie entsteht aus den Quellfragmenten.
        print(
            f"entscheide: A-Box unlesbar: {exc} — A-Box erzeugen bzw. "
            "erneuern mit: python -m rechner_pipeline.gates.abox_merge "
            f"--fall {fall} (die Fragmente unter "
            f"{fall}/abgeleitet/abox/fragmente kommen aus der "
            "Stufe-1-Extraktion je Quelle)",
            file=sys.stderr,
        )
        return 1

    beleg = None
    if args.beleg:
        beleg_pfad = fall / args.beleg
        if not beleg_pfad.is_file():
            print(f"entscheide: Beleg {args.beleg!r} liegt nicht im Fall "
                  f"({beleg_pfad})", file=sys.stderr)
            return 2
        beleg = Beleg(
            datei=args.beleg,
            sha256=hashlib.sha256(beleg_pfad.read_bytes()).hexdigest(),
        )

    jetzt = _jetzt()
    entschieden: List[str] = []
    try:
        if args.alle_vorlaeufigen:
            if args.diskrepanz or args.wert is not None:
                print("entscheide: --alle-vorlaeufigen schliesst "
                      "--diskrepanz/--wert aus (still ignorieren waere "
                      "eine halbe Anweisung)", file=sys.stderr)
                return 2
            if not args.quelle:
                print("entscheide: --alle-vorlaeufigen braucht --quelle",
                      file=sys.stderr)
                return 2
            for d in list(abox.diskrepanzen):
                if d.entscheidung is None or not d.entscheidung.vorlaeufig:
                    continue
                lesart = next(
                    (l for l in d.lesarten
                     if any(p.quelle_datei == args.quelle
                            for p in l.provenienz)),
                    None,
                )
                if lesart is None:
                    print(
                        f"entscheide: {d.id}: keine Lesart aus "
                        f"{args.quelle!r} — einzeln entscheiden",
                        file=sys.stderr,
                    )
                    return 1
                _ersetze_vorlaeufig(abox, d.id)
                loese_diskrepanz_auf(
                    abox, d.id, lesart.wert, args.entscheider,
                    args.begruendung, jetzt, vorlaeufig=False, beleg=beleg,
                    zeichnung=zeichnung,
                )
                entschieden.append(d.id)
        else:
            if not args.diskrepanz or args.wert is None:
                print("entscheide: --diskrepanz und --wert sind "
                      "erforderlich (oder --alle-vorlaeufigen)",
                      file=sys.stderr)
                return 2
            _ersetze_vorlaeufig(abox, args.diskrepanz)
            loese_diskrepanz_auf(
                abox, args.diskrepanz, _wert_parsen(args.wert),
                args.entscheider, args.begruendung, jetzt, vorlaeufig=False,
                beleg=beleg, zeichnung=zeichnung,
            )
            entschieden.append(args.diskrepanz)
    except BefuellungsFehler as exc:
        print(f"entscheide: {exc}", file=sys.stderr)
        return 1

    fehler = validate_abox(abox)
    if fehler:
        print("entscheide: A-Box nach Aufloesung inkonsistent: "
              + "; ".join(fehler), file=sys.stderr)
        return 1
    speichere(abox, fall)
    print(json.dumps({
        "fall": str(fall),
        "entschieden": entschieden,
        "entscheider": args.entscheider,
        "rolle": (zeichnung or {}).get("rolle", args.rolle),
        "verbleibend_vorlaeufig": sorted(
            d.id for d in abox.diskrepanzen
            if d.entscheidung is not None and d.entscheidung.vorlaeufig
        ),
        # OFFENE Diskrepanzen ebenfalls ausweisen: --alle-vorlaeufigen
        # beruehrt sie nicht, und der Bediener soll nicht "alles
        # erledigt" lesen, wenn Ungeloestes bleibt.
        "verbleibend_offen": sorted(
            d.id for d in abox.diskrepanzen if d.status == "offen"
        ),
    }, ensure_ascii=False, indent=2, sort_keys=True))
    return 0


def _ersetze_vorlaeufig(abox, diskrepanz_id: str) -> None:
    """Eine vorlaeufige Aufloesung zuruecknehmen, damit neu entschieden wird.

    Nur vorlaeufige Entscheidungen sind ersetzbar; eine endgueltige
    menschliche Entscheidung wird nie ueberschrieben.
    """
    for i, d in enumerate(abox.diskrepanzen):
        if d.id != diskrepanz_id:
            continue
        if d.status == "aufgeloest":
            if d.entscheidung is None or not d.entscheidung.vorlaeufig:
                raise BefuellungsFehler(
                    f"{diskrepanz_id}: endgueltig entschieden von "
                    f"{d.entscheidung.entscheider if d.entscheidung else '?'} "
                    "— wird nie ueberschrieben"
                )
            abox.diskrepanzen[i] = d.model_copy(update={
                "status": "offen",
                "entscheidung": None,
                # Die ersetzte vorlaeufige Entscheidung bleibt Teil der
                # Nachweiskette (append-only), sie wird nie vernichtet.
                "entscheidungs_historie": [*d.entscheidungs_historie,
                                           d.entscheidung],
            })
        return
    raise BefuellungsFehler(f"Diskrepanz {diskrepanz_id!r} unbekannt")


if __name__ == "__main__":  # pragma: no cover
    raise SystemExit(main())
