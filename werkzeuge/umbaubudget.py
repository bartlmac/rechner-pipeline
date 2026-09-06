"""``umbaubudget`` — wie weit ein Lauf das System umgebaut hat.

Beobachtungshilfe, **kein Gate**: Sie schreibt keinen Ledger-Eintrag und
haelt niemanden auf. Sie beantwortet eine Frage, die sonst niemand
stellt — wie viel vom System hat dieser Lauf ersetzt?

**Warum eine Schranke, wo doch alles erlaubt ist.** Der Operator eines
Vorfuehrlaufs darf den Fall loesen, und dazu gehoert, Code zu aendern,
die Ontologie zu erweitern und Gates umzubauen. Was er NICHT soll, ist
das System nebenbei durch ein anderes ersetzen — etwa den Rechenkern
von der Thiele-Rekursion auf Kommutationszahlen zurueckdrehen, weil das
gerade der kuerzere Weg zum gruenen Gate waere. Der Unterschied
zwischen beidem ist keine Absicht, die man abfragen kann, sondern ein
Umfang, den man messen kann.

**Loeschen wiegt schwerer als Hinzufuegen.** Hinzufuegen ist der
Auftrag: Was den Fall loesbar macht, soll entstehen. Loeschen ist
Ersetzen — und nur dort liegt die Gefahr. Deshalb traegt das
Gesamtbudget viel und die Loeschbudgets wenig, je Schicht getrennt.

**Ueberschreiten ist erlaubt, Verschweigen nicht.** Wer die Schranke
reisst, gibt ``--ueberschreitung-begruendet`` mit einem Satz an. Dann
laeuft das Werkzeug durch — und die Begruendung steht im Ergebnis, das
auf die Vorfuehrseite kommt. Aus einer Nebenwirkung von vierzig Commits
wird so eine benannte Entscheidung. Genau das ist der Zweck: nicht
verhindern, sondern sichtbar machen.
"""

from __future__ import annotations

import argparse
import html
import json
import re
import subprocess
import sys
from pathlib import Path
from typing import Dict, List, Optional, Tuple

#: Gesamtaenderung in ``src/`` und ``tests/`` (Zeilen rein plus raus).
#: Reichlich bemessen: Die Vorbereitung dieses Falls umfasste rund
#: 11.000 Zeilen Code. Endlich bleibt sie trotzdem.
VORGABE_GESAMT = 18_000

#: Loeschbudgets je Schicht. ``kern/`` und ``ontologie/`` tragen das
#: Rueckgrat; wer dort in Groessenordnungen loescht, ersetzt es.
VORGABE_LOESCHUNG = {
    "kern": 450,
    "ontologie": 450,
}
#: Loeschbudget fuer alles uebrige unter ``src/`` zusammengenommen.
VORGABE_LOESCHUNG_UEBRIGE = 1_200

#: Beruehrungen, die keine Budgetfrage sind, sondern eine
#: Architekturfrage. Sie verbieten nichts — sie verlangen, dass die
#: Entscheidung benannt wird.
STOLPERDRAEHTE: Tuple[Tuple[str, str], ...] = (
    (
        "tests/fixtures/kern_referenzwerte/",
        "Charakterisierungs-Referenzwerte des Rechenkerns: Sie sind der "
        "Beweis, dass der Kern noch dasselbe rechnet. Wer sie aendert, "
        "aendert den Massstab, nicht das Gemessene.",
    ),
    (
        "src/rechner_pipeline/ontologie/code_karte.py",
        "Schicht-Allowlist: Eine neue Kante zwischen zwei Schichten ist "
        "eine Architektur-Entscheidung (ADR-001, ADR-005).",
    ),
)


#: Bereichs-Namen der gruppierten Korrekturliste: Commit-Scope -> Sprache
#: des Berichts. Die Gruppierung ist ABGELEITET (erster passender Scope
#: der Botschaft), nicht kuratiert; Unbekanntes laeuft unter "Weitere".
BEREICHE: Tuple[Tuple[str, str], ...] = (
    ("kern", "Rechenkern"),
    ("bestand", "Bestandsfuehrung und Uebernahme"),
    ("qa", "Pruef-Engines"),
    ("gates", "Abnahme-Werkzeuge"),
    ("ontologie", "Wissensmodell"),
    ("models", "Datenvertraege"),
)

_KONVENTION = re.compile(r"^(fix|feat|refactor)(!)?(\(([^)]*)\))?")


class BudgetFehler(RuntimeError):
    """Das Werkzeug kann nicht messen — nicht: das Budget ist gerissen."""


def _git(repo: Path, *args: str) -> str:
    try:
        fertig = subprocess.run(
            ["git", *args], cwd=repo, capture_output=True, text=True,
            check=True)
    except OSError as exc:
        raise BudgetFehler(f"git nicht ausfuehrbar: {exc}") from exc
    except subprocess.CalledProcessError as exc:
        raise BudgetFehler(
            f"git {' '.join(args)} scheitert: {exc.stderr.strip()}") from exc
    return fertig.stdout


def _schicht(pfad: str) -> Optional[str]:
    """Die Schicht unter ``src/rechner_pipeline/``, sonst None."""
    teile = pfad.split("/")
    if teile[:2] == ["src", "rechner_pipeline"] and len(teile) > 3:
        return teile[2]
    return None


def messe(repo: Path, basis: str) -> Dict[str, object]:
    """Den Umfang der Aenderung gegen die Basis erheben."""
    numstat = _git(repo, "diff", "--numstat", f"{basis}...HEAD")
    namestatus = _git(repo, "diff", "--name-status", f"{basis}...HEAD")

    gesamt_plus = gesamt_minus = 0
    loeschung: Dict[str, int] = {}
    loeschung_uebrige = 0
    for zeile in numstat.splitlines():
        felder = zeile.split("\t")
        if len(felder) != 3 or felder[0] == "-":
            continue  # Binaerdatei oder Umbenennung ohne Zeilenzahlen
        plus, minus, pfad = int(felder[0]), int(felder[1]), felder[2]
        if pfad.startswith(("src/", "tests/")):
            gesamt_plus += plus
            gesamt_minus += minus
        schicht = _schicht(pfad)
        if schicht is None:
            continue
        if schicht in VORGABE_LOESCHUNG:
            loeschung[schicht] = loeschung.get(schicht, 0) + minus
        else:
            loeschung_uebrige += minus

    beruehrt: List[Dict[str, str]] = []
    for zeile in namestatus.splitlines():
        felder = zeile.split("\t")
        if len(felder) < 2:
            continue
        status, pfad = felder[0], felder[-1]
        # Nur AENDERN und LOESCHEN reisst einen Draht, nicht Hinzufuegen.
        # Ein neuer Referenzwert ist gewoehnliche Arbeit: Er stellt einen
        # weiteren Massstab daneben. Einen bestehenden umzuschreiben
        # verschiebt den Massstab selbst — und nur das ist die Frage.
        if not status.startswith(("M", "D")):
            continue
        for muster, warum in STOLPERDRAEHTE:
            if pfad.startswith(muster):
                beruehrt.append({"datei": pfad, "status": status,
                                 "warum": warum})
        # Ein BESTEHENDER ADR wird geaendert (nicht: ein neuer kommt
        # dazu). Ein ADR haelt eine getroffene Entscheidung fest; ihn
        # umzuschreiben heisst, die Entscheidung zu ersetzen, statt eine
        # neue danebenzustellen.
        if (pfad.startswith("docs/architektur/adr-")
                and status.startswith("M")):
            beruehrt.append({
                "datei": pfad, "status": status,
                "warum": "Bestehender ADR geaendert: Eine getroffene "
                         "Entscheidung wird ersetzt statt ergaenzt. Ein "
                         "neuer ADR daneben waere der uebliche Weg.",
            })
    return {
        "basis": basis,
        "gesamt": {"plus": gesamt_plus, "minus": gesamt_minus,
                   "summe": gesamt_plus + gesamt_minus,
                   "vorgabe": VORGABE_GESAMT},
        "loeschung_je_schicht": {
            schicht: {"gemessen": loeschung.get(schicht, 0),
                      "vorgabe": vorgabe}
            for schicht, vorgabe in sorted(VORGABE_LOESCHUNG.items())
        },
        "loeschung_uebrige_schichten": {
            "gemessen": loeschung_uebrige,
            "vorgabe": VORGABE_LOESCHUNG_UEBRIGE,
        },
        "stolperdraehte": beruehrt,
    }


def befunde(messung: Dict[str, object]) -> List[str]:
    """Was die Vorgaben reisst — leer heisst: alles im Rahmen."""
    aus: List[str] = []
    gesamt = messung["gesamt"]  # type: ignore[index]
    if gesamt["summe"] > gesamt["vorgabe"]:
        aus.append(
            f"Gesamtaenderung {gesamt['summe']} Zeilen in src/ und tests/ "
            f"ueber der Vorgabe {gesamt['vorgabe']}")
    for schicht, werte in messung["loeschung_je_schicht"].items():  # type: ignore[union-attr]
        if werte["gemessen"] > werte["vorgabe"]:
            aus.append(
                f"Loeschungen in {schicht}/: {werte['gemessen']} Zeilen "
                f"ueber der Vorgabe {werte['vorgabe']} — das ist Ersetzen, "
                "nicht Erweitern")
    uebrige = messung["loeschung_uebrige_schichten"]  # type: ignore[index]
    if uebrige["gemessen"] > uebrige["vorgabe"]:
        aus.append(
            f"Loeschungen in den uebrigen Schichten: {uebrige['gemessen']} "
            f"Zeilen ueber der Vorgabe {uebrige['vorgabe']}")
    for draht in messung["stolperdraehte"]:  # type: ignore[union-attr]
        aus.append(f"{draht['datei']}: {draht['warum']}")
    return aus


def _gruppiere(log_zeilen: List[str]) -> List[Tuple[str, List[Dict[str, str]]]]:
    """fix/feat/refactor-Zeilen (``hash<TAB>betreff``) je Bereich buendeln.

    Nur Commits der Konventionsform zaehlen als Korrektur — Doku- und
    Merge-Commits gehoeren nicht in die Liste. Der ERSTE bekannte Scope
    der Botschaft bestimmt den Bereich; das ist ableitbar und damit
    drift-frei, auch wenn eine Botschaft mehrere Schichten nennt.
    """
    gruppen: Dict[str, List[Dict[str, str]]] = {
        name: [] for _, name in BEREICHE}
    gruppen["Weitere"] = []
    for zeile in log_zeilen:
        kurz, _, betreff = zeile.partition("\t")
        treffer = _KONVENTION.match(betreff)
        if not treffer:
            continue
        scopes = [s.strip() for s in (treffer.group(4) or "").split(",")]
        ziel = "Weitere"
        for scope, name in BEREICHE:
            if any(s == scope or s.startswith(scope + "/") for s in scopes):
                ziel = name
                break
        gruppen[ziel].append({"commit": kurz, "betreff": betreff})
    return [(name, eintraege) for name, eintraege in gruppen.items()
            if eintraege]


def korrekturliste(repo: Path, basis: str) -> List[Tuple[str, List[Dict[str, str]]]]:
    """Die Korrekturen des Messfensters, chronologisch, je Bereich."""
    log = _git(repo, "log", "--no-merges", "--reverse",
               "--format=%h\t%s", f"{basis}..HEAD")
    return _gruppiere(log.splitlines())


def _html_bericht(messung: Dict[str, object], offene: List[str],
                  begruendung: Optional[str],
                  gruppen: List[Tuple[str, List[Dict[str, str]]]],
                  titel: str, stand: str) -> str:
    """Der Umbaubericht als selbst-enthaltene Seite, VU-Ton.

    Vollstaendig aus Messung und Versionsbestand erzeugt — keine
    gepflegte Zeile, damit der naechste Fall ihn unveraendert neu
    tragen kann. Bewusst ohne Zeitstempel: gleiche Eingaben, gleiche
    Bytes.
    """
    e = html.escape
    gesamt = messung["gesamt"]  # type: ignore[index]
    z: List[str] = []
    z.append("<!DOCTYPE html>")
    z.append('<html lang="de"><head><meta charset="utf-8">')
    z.append(f"<title>{e(titel)}</title>")
    z.append("<style>")
    z.append("body{font-family:Georgia,serif;max-width:52rem;margin:2rem "
             "auto;padding:0 1rem;color:#222;line-height:1.5}")
    z.append("h1{font-size:1.6rem} h2{font-size:1.2rem;margin-top:2rem}")
    z.append("table{border-collapse:collapse;width:100%}")
    z.append("td,th{border:1px solid #bbb;padding:.35rem .6rem;"
             "text-align:left;vertical-align:top}")
    z.append("th{background:#f0efe9} code{font-size:.9em}")
    z.append(".befund{background:#fdf3e3;border:1px solid #d9b06b;"
             "padding:.7rem 1rem;margin:.6rem 0}")
    z.append(".begruendung{background:#eef3ec;border:1px solid #9dbb95;"
             "padding:.7rem 1rem;margin:.6rem 0}")
    z.append(".hinweis{color:#555;font-size:.92em}")
    z.append("</style></head><body>")
    z.append(f"<h1>{e(titel)}</h1>")
    z.append(f'<p class="hinweis">Messfenster {e(messung["basis"])} bis '
             f"{e(stand)} &middot; Beobachtungshilfe, kein Abnahme-Gate. "
             "Ein Migrationslauf darf das System erweitern, um den Fall "
             "zu loesen; er soll es nicht nebenbei ersetzen. Der "
             "Unterschied ist keine Absicht, sondern ein messbarer "
             "Umfang &mdash; Ueberschreiten ist erlaubt, Verschweigen "
             "nicht.</p>")

    z.append("<h2>Umfang in Zahlen</h2>")
    z.append("<table><tr><th>Groesse</th><th>gemessen</th>"
             "<th>Vorgabe</th></tr>")
    z.append(f"<tr><td>Gesamtaenderung Fachcode und Tests</td>"
             f"<td>{gesamt['summe']} Zeilen (+{gesamt['plus']} / "
             f"&minus;{gesamt['minus']})</td>"
             f"<td>{gesamt['vorgabe']}</td></tr>")
    for schicht, werte in messung["loeschung_je_schicht"].items():  # type: ignore[union-attr]
        z.append(f"<tr><td>Loeschungen {e(schicht)}/</td>"
                 f"<td>{werte['gemessen']} Zeilen</td>"
                 f"<td>{werte['vorgabe']}</td></tr>")
    uebrige = messung["loeschung_uebrige_schichten"]  # type: ignore[index]
    z.append(f"<tr><td>Loeschungen uebrige Schichten</td>"
             f"<td>{uebrige['gemessen']} Zeilen</td>"
             f"<td>{uebrige['vorgabe']}</td></tr></table>")

    z.append("<h2>Befunde</h2>")
    if not offene:
        z.append("<p>Im Rahmen &mdash; keine Vorgabe gerissen, kein "
                 "Stolperdraht beruehrt.</p>")
    else:
        for befund in offene:
            z.append(f'<div class="befund">{e(befund)}</div>')
        if begruendung:
            z.append('<div class="begruendung"><strong>Als '
                     "Menschentscheidung begruendet:</strong> "
                     f"{e(begruendung)}</div>")

    if gruppen:
        z.append("<h2>Die Schritte des Umbaus</h2>")
        z.append('<p class="hinweis">Chronologisch je Bereich, aus den '
                 "Aenderungs-Botschaften des Versionsbestands erzeugt "
                 "&mdash; jede nennt den Grund vor der Aenderung.</p>")
        for name, eintraege in gruppen:
            z.append(f"<h3>{e(name)} ({len(eintraege)})</h3><ul>")
            for eintrag in eintraege:
                z.append(f"<li><code>{e(eintrag['commit'])}</code> "
                         f"{e(eintrag['betreff'])}</li>")
            z.append("</ul>")
    z.append("</body></html>")
    return "\n".join(z) + "\n"


def _bericht(messung: Dict[str, object], offene: List[str],
             begruendung: Optional[str]) -> str:
    z: List[str] = []
    gesamt = messung["gesamt"]  # type: ignore[index]
    z.append(f"Umbaubudget gegen {messung['basis']}")
    z.append("")
    z.append(f"  Gesamt src/ + tests/   {gesamt['summe']:>7} von "
             f"{gesamt['vorgabe']} Zeilen "
             f"(+{gesamt['plus']} / -{gesamt['minus']})")
    for schicht, werte in messung["loeschung_je_schicht"].items():  # type: ignore[union-attr]
        z.append(f"  Loeschungen {schicht + '/':<10} {werte['gemessen']:>7} "
                 f"von {werte['vorgabe']}")
    uebrige = messung["loeschung_uebrige_schichten"]  # type: ignore[index]
    z.append(f"  Loeschungen uebrige    {uebrige['gemessen']:>7} von "
             f"{uebrige['vorgabe']}")
    z.append("")
    if not offene:
        z.append("  Im Rahmen.")
    else:
        z.append(f"  {len(offene)} Befund(e):")
        for befund in offene:
            z.append(f"    - {befund}")
        if begruendung:
            z.append("")
            z.append("  Als Menschentscheidung begruendet:")
            z.append(f"    {begruendung}")
    return "\n".join(z)


def main(argv: Optional[List[str]] = None) -> int:
    p = argparse.ArgumentParser(
        prog="python werkzeuge/umbaubudget.py",
        description="Wie weit ein Lauf das System umgebaut hat "
                    "(Beobachtungshilfe, kein Gate).")
    p.add_argument("--repo", default=".", help="Repo-Wurzel")
    p.add_argument("--basis", default="main",
                   help="Vergleichsstand (Vorgabe: main)")
    p.add_argument("--json", dest="json_ziel", default=None,
                   help="Ergebnis zusaetzlich als JSON schreiben")
    p.add_argument("--html", dest="html_ziel", default=None,
                   help="Umbaubericht als selbst-enthaltene HTML-Seite "
                        "schreiben (VU-Ton, mit gruppierter "
                        "Korrekturliste aus den Commit-Botschaften)")
    p.add_argument("--titel", default="Umbaubericht",
                   help="Ueberschrift des HTML-Berichts")
    p.add_argument("--ueberschreitung-begruendet", dest="begruendung",
                   default=None,
                   help="Die Schranke bewusst reissen: ein Satz, warum. "
                        "Er steht danach im Ergebnis und auf der "
                        "Vorfuehrseite — ueberschreiten ja, verschweigen "
                        "nein.")
    args = p.parse_args(argv)

    try:
        messung = messe(Path(args.repo).resolve(), args.basis)
    except BudgetFehler as exc:
        print(f"Messung nicht moeglich: {exc}", file=sys.stderr)
        return 2

    offene = befunde(messung)
    messung["befunde"] = offene
    messung["ueberschreitung_begruendet"] = args.begruendung
    print(_bericht(messung, offene, args.begruendung))

    if args.json_ziel:
        ziel = Path(args.json_ziel)
        ziel.parent.mkdir(parents=True, exist_ok=True)
        with ziel.open("w", encoding="utf-8") as datei:
            json.dump(messung, datei, indent=2, ensure_ascii=False,
                      sort_keys=True)
            datei.write("\n")
        print(f"\n  {ziel}")

    if args.html_ziel:
        repo = Path(args.repo).resolve()
        gruppen = korrekturliste(repo, args.basis)
        stand = _git(repo, "rev-parse", "--short", "HEAD").strip()
        seite = _html_bericht(messung, offene, args.begruendung, gruppen,
                              args.titel, stand)
        ziel = Path(args.html_ziel)
        ziel.parent.mkdir(parents=True, exist_ok=True)
        ziel.write_text(seite, encoding="utf-8")
        print(f"  {ziel}")

    if offene and not args.begruendung:
        return 20
    return 0


if __name__ == "__main__":  # pragma: no cover
    raise SystemExit(main())
