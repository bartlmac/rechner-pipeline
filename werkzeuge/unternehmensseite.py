"""``unternehmensseite`` — die Seiten des fiktiven Unternehmens zusammenbauen.

Die Vorfuehrung tritt als Unternehmensauftritt der (frei erfundenen)
Pfefferminzia Lebensversicherung AG auf: eine Startseite, Bereiche
(Aktuariat, IT, ...) und darunter die generierten Migrationsberichte
(``vorzeigeseite.py``, je Fall unter ``migrationen/<fall>/``).

Die Unternehmensseiten sind HANDGESCHRIEBENE, versionierte Quellen
unter ``vorzeige-seite/`` — im Gegensatz zu den Fall-Seiten, die je
Lauf aus den Artefakten entstehen. Dieses Werkzeug kopiert sie in den
Push-Baum und erzwingt dabei zwei Dinge:

*Die Banderole.* Je echter der Auftritt wirkt, desto wichtiger die
Kennzeichnung: JEDE Seite muss den Fiktions-Hinweis tragen. Eine Seite
ohne ihn wird nicht gebaut — eine oeffentliche Seite, die wie ein
echter Versicherer aussieht, waere keine Vorfuehrung mehr, sondern
eine Behauptung.

*Die Regie-Sperre.* Wie bei der Fall-Seite gelangt nichts aus den
Spielleiter-Bereichen in die Veroeffentlichung.

Aufruf (nach dem Bau der Fall-Seiten in denselben Baum)::

    python werkzeuge/unternehmensseite.py --quellen vorzeige-seite \\
        --out runs/seite
"""

from __future__ import annotations

import argparse
import shutil
import sys
from pathlib import Path
from typing import List, Optional

from vorzeigeseite import VeroeffentlichungFehler, _pruefe_regie

#: Jede Unternehmensseite muss diesen Hinweis woertlich tragen — die
#: Banderole oben auf der Seite. Fehlt er, wird nicht gebaut.
BANDEROLE = "Fiktives Unternehmen"

#: Fachdokumente, die der Auftritt beim Bau importiert. Eine Quelle,
#: eine Heimat (``docs/``) — der Auftritt kopiert beim Bau, statt eine
#: zweite Fassung zu pflegen. Zielort ist ``aktuariat/<pfad>`` mit dem
#: Pfad UNTER docs/: so bleiben die relativen Querverweise der
#: Dokumente untereinander (Tarifplan -> Grundsatzdokumentation)
#: unveraendert gueltig.
FACHDOKUMENTE = (
    "tarifplaene/klv.md",
    "tarifplaene/bu.md",
    "mathematik/grundsatzdokumentation.md",
)

#: MathJax fuer Fachdokumente mit TeX-Formeln. Die Wiedergabe ist
#: best-effort: Markdown und TeX teilen sich Sonderzeichen, einzelne
#: Formeln koennen im Gerenderten leiden — das Dokument im Repo bleibt
#: die massgebliche Fassung.
MATHJAX = (
    '<script>window.MathJax={tex:{inlineMath:[["$","$"],'
    '["\\\\(","\\\\)"]]}};</script>\n'
    '<script defer src="https://cdn.jsdelivr.net/npm/mathjax@3/es5/'
    'tex-mml-chtml.js"></script>\n'
)


def _titel_und_rumpf(text: str) -> tuple:
    """YAML-Vorspann eines Fachdokuments abtrennen.

    Der Titel des Vorspanns wird zur Ueberschrift der importierten
    Seite; der Rest des Vorspanns (Druckformat u. ae.) betrifft nur die
    Dokument-Erzeugung und faellt weg.
    """
    if not text.startswith("---\n"):
        return "", text
    kopf, _, rumpf = text[4:].partition("\n---\n")
    zeilen = kopf.splitlines()
    for i, zeile in enumerate(zeilen):
        if not zeile.startswith("title:"):
            continue
        wert = zeile.split(":", 1)[1].strip()
        # Ein YAML-Titel darf umbrochen sein — Folgezeilen anhaengen,
        # bis das schliessende Anfuehrungszeichen erreicht ist.
        while not (len(wert) > 1 and wert.endswith('"')):
            i += 1
            wert += " " + zeilen[i].strip()
        return wert.strip('"'), rumpf
    return "", rumpf


def _vorspann(rel: Path, titel: str, mit_mathe: bool,
              zurueck: tuple = ("Aktuariat", "../")) -> str:
    """Kopf einer importierten Seite: Stil, Banderole, Titel, MathJax."""
    wurzel = "../" * len(rel.parts)
    z = [f'<link rel="stylesheet" href="{wurzel}assets/stil.css">']
    z.append(f'<div class="banderole">{BANDEROLE} — eine Vorführung '
             'agentischer Bestandsmigration. '
             f'<a href="{wurzel}">Zur Startseite.</a></div>')
    if mit_mathe:
        z.append(MATHJAX.rstrip("\n"))
    z.append("")
    z.append(f"[← {zurueck[0]}]({zurueck[1]})")
    z.append("")
    if titel:
        z.append(f"# {titel}")
        z.append("")
    return "\n".join(z) + "\n"


def fachdokumente(docs: Path, ziel: Path,
                  dokumente=FACHDOKUMENTE) -> List[tuple]:
    """Die Fachdokumente unter ``aktuariat/`` in den Auftritt einbinden.

    Ein gelistetes Dokument, das fehlt, bricht den Bau ab: Eine Seite,
    die still ohne ihre Tarifplaene erschiene, saehe vollstaendig aus
    und waere es nicht.
    """
    aus: List[tuple] = []
    for name in dokumente:
        quelle = docs / name
        if not quelle.is_file():
            raise VeroeffentlichungFehler(
                f"Fachdokument fehlt: {quelle}. Der Auftritt wuerde ohne "
                "es vollstaendig aussehen und waere es nicht.")
        _pruefe_regie(quelle)
        text = quelle.read_text(encoding="utf-8")
        titel, rumpf = _titel_und_rumpf(text)
        rel = Path("aktuariat") / name
        zielpfad = ziel / rel
        zielpfad.parent.mkdir(parents=True, exist_ok=True)
        zielpfad.write_text(
            _vorspann(Path(name), titel, "$" in rumpf) + rumpf,
            encoding="utf-8")
        aus.append((name, titel))
    _tarifplan_uebersicht(ziel, aus)
    return aus


def _tarifplan_uebersicht(ziel: Path, importiert: List[tuple]) -> None:
    """Generierte Uebersichtsseite der importierten Tarifplaene."""
    plaene = [(Path(name), titel) for name, titel in importiert
              if Path(name).parts[0] == "tarifplaene"]
    if not plaene:
        return
    z = ['<link rel="stylesheet" href="../../assets/stil.css">',
         f'<div class="banderole">{BANDEROLE} — eine Vorführung '
         'agentischer Bestandsmigration. '
         '<a href="../../">Zur Startseite.</a></div>',
         "", "[← Aktuariat](../)", "", "# Tarifpläne", "",
         "Die Bewertung jedes Vertrags folgt einem dokumentierten",
         "Tarifplan. Die geführten Tarifgenerationen:", ""]
    for pfad, titel in plaene:
        z.append(f"* [{titel or pfad.stem}]({pfad.stem}.html)")
    z += ["",
          "Das gemeinsame mathematische Rückgrat — Zustandsraum,",
          "Thiele-Rekursion, Rechnungsgrundlagen — steht einmal in der",
          "[Grundsatzdokumentation](../mathematik/grundsatzdokumentation.html).",
          ""]
    pfad = ziel / "aktuariat" / "tarifplaene" / "index.md"
    pfad.parent.mkdir(parents=True, exist_ok=True)
    pfad.write_text("\n".join(z), encoding="utf-8")


def architektur(docs: Path, ziel: Path) -> int:
    """``docs/architektur`` unter ``it/architektur/`` einspielen.

    Vollstaendig — ADRs, Prinzipien, Migrations-Pipeline —, damit die
    Querverweise der Dokumente untereinander gelten. ``README.md`` wird
    zur Uebersicht ``index.md``. Nur ``landkarte.md`` bleibt draussen:
    Die Landkarte wird beim Bau FRISCH aus dem Code erzeugt
    (``landkarten``); eine eingecheckte Fassung zu kopieren waere
    genau die Drift, die der Import vermeiden soll.
    """
    verzeichnis = docs / "architektur"
    if not verzeichnis.is_dir():
        raise VeroeffentlichungFehler(
            f"Architektur-Dokumente fehlen: {verzeichnis}")
    anzahl = 0
    for quelle in sorted(verzeichnis.glob("*.md")):
        if quelle.name == "landkarte.md":
            continue
        _pruefe_regie(quelle)
        titel, rumpf = _titel_und_rumpf(
            quelle.read_text(encoding="utf-8"))
        # Verweise auf die eingecheckte Landkarte zeigen im Auftritt auf
        # die beim Bau frisch erzeugte Fassung.
        rumpf = rumpf.replace("](landkarte.md)", "](landkarte-schichten.html)")
        name = "index.md" if quelle.name == "README.md" else quelle.name
        zielpfad = ziel / "it" / "architektur" / name
        zielpfad.parent.mkdir(parents=True, exist_ok=True)
        zielpfad.write_text(
            _vorspann(Path("architektur") / name, titel, "$" in rumpf,
                      zurueck=("IT", "../")) + rumpf,
            encoding="utf-8")
        anzahl += 1
    return anzahl


def landkarten(repo: Path, ziel: Path) -> None:
    """Die Landkarten des Codes beim Bau frisch erzeugen.

    ``ontologie.landkarte`` liefert selbsttragende HTML-Artefakte; als
    Stand wird der Commit gestempelt, aus dem gebaut wurde. Ein
    fehlgeschlagener Lauf bricht den Bau ab — eine IT-Seite mit einer
    Landkarte von vorgestern waere Drift mit Ansage.
    """
    import subprocess
    stand = subprocess.run(
        ["git", "rev-parse", "--short", "HEAD"], cwd=repo,
        capture_output=True, text=True).stdout.strip()
    for umfang, name in (("schichten", "landkarte-schichten.html"),
                         ("modul", "landkarte-module.html")):
        aus = ziel / "it" / "architektur" / name
        aus.parent.mkdir(parents=True, exist_ok=True)
        lauf = subprocess.run(
            [sys.executable, "-m", "rechner_pipeline.ontologie.landkarte",
             "--format", "html", "--umfang", umfang,
             "--stand", stand, "--out", str(aus)],
            cwd=repo, capture_output=True, text=True)
        if lauf.returncode != 0:
            raise VeroeffentlichungFehler(
                f"Landkarte ({umfang}) liess sich nicht erzeugen: "
                f"{lauf.stderr.strip()[:300]}")


def techstack(repo: Path, ziel: Path) -> None:
    """``it/techstack.md`` beim Bau aus ``pyproject.toml`` erzeugen."""
    import tomllib
    with (repo / "pyproject.toml").open("rb") as datei:
        projekt = tomllib.load(datei)["project"]

    z = [_vorspann(Path("techstack.md"), "Techstack", False,
                   zurueck=("IT", "./")).rstrip("\n"), ""]
    z += ["Beim Bau aus `pyproject.toml` erzeugt — die Liste kann dem",
          "Repo nicht davonlaufen.", "",
          f"Python {projekt.get('requires-python', '?')}, keine",
          "Laufzeit-Abhaengigkeit zu Office-Produkten oder zu",
          "KI-Diensten: Der Rechenkern und alle Gates laufen ohne",
          "Netz. Versionen exakt gepinnt:", "",
          "| Laufzeit | Version |", "|---|---|"]
    for eintrag in projekt.get("dependencies", []):
        name, _, version = eintrag.partition("==")
        z.append(f"| `{name}` | {version or '—'} |")
    z += ["", "| Entwicklung | Version |", "|---|---|"]
    for eintrag in (projekt.get("optional-dependencies") or {}).get("dev", []):
        name, _, version = eintrag.partition("==")
        z.append(f"| `{name}` | {version or '—'} |")
    z += ["",
          "Die KI-Agenten arbeiten AUSSERHALB dieser Laufzeit: Sie lesen",
          "Lieferungen und schlagen vor; gerechnet und geurteilt wird",
          "ausschliesslich im deterministischen Kern.", ""]
    pfad = ziel / "it" / "techstack.md"
    pfad.parent.mkdir(parents=True, exist_ok=True)
    pfad.write_text("\n".join(z), encoding="utf-8")


def baue(quellen: Path, ziel: Path) -> List[str]:
    """Die Quellseiten in den Push-Baum spiegeln, mit beiden Zwaengen."""
    if not (quellen / "index.md").is_file():
        raise VeroeffentlichungFehler(
            f"Keine Unternehmensseiten unter {quellen} (index.md fehlt).")
    if not (quellen / "_config.yml").is_file():
        raise VeroeffentlichungFehler(
            f"{quellen}/_config.yml fehlt — ohne Jekyll-Konfiguration "
            "nimmt GitHub Pages ein Vorgabethema, das die Seiten bricht.")

    kopiert: List[str] = []
    for datei in sorted(quellen.rglob("*")):
        if not datei.is_file():
            continue
        _pruefe_regie(datei)
        if datei.suffix == ".md" and BANDEROLE not in datei.read_text(
                encoding="utf-8"):
            raise VeroeffentlichungFehler(
                f"{datei.relative_to(quellen)} traegt die Banderole "
                f"({BANDEROLE!r}) nicht. Jede Unternehmensseite muss den "
                "Fiktions-Hinweis tragen — sonst saehe der Auftritt aus "
                "wie ein echter Versicherer.")
        zielpfad = ziel / datei.relative_to(quellen)
        zielpfad.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(datei, zielpfad)
        kopiert.append(str(zielpfad.relative_to(ziel)))
    return kopiert


def main(argv: Optional[List[str]] = None) -> int:
    p = argparse.ArgumentParser(
        prog="python werkzeuge/unternehmensseite.py",
        description="Unternehmensseiten der Vorfuehrung in den Push-Baum "
                    "zusammenbauen.")
    p.add_argument("--quellen", default="vorzeige-seite",
                   help="versionierte Quellseiten (Vorgabe: vorzeige-seite)")
    p.add_argument("--docs", default="docs",
                   help="Wurzel der Fachdokumente (Vorgabe: docs); von "
                        "dort werden Tarifplaene und Grundsatz-"
                        "dokumentation importiert")
    p.add_argument("--repo", default=".",
                   help="Repo-Wurzel (pyproject.toml, Landkarten-Erzeugung)")
    p.add_argument("--out", required=True,
                   help="Push-Baum der Seite; die Fall-Seiten liegen dort "
                        "unter migrationen/<fall>/")
    args = p.parse_args(argv)

    quellen = Path(args.quellen).resolve()
    repo = Path(args.repo).resolve()
    ziel = Path(args.out).resolve()
    ziel.mkdir(parents=True, exist_ok=True)
    try:
        kopiert = baue(quellen, ziel)
        doku = fachdokumente(Path(args.docs).resolve(), ziel)
        adrs = architektur(Path(args.docs).resolve(), ziel)
        landkarten(repo, ziel)
        techstack(repo, ziel)
    except VeroeffentlichungFehler as exc:
        print(f"ABBRUCH: {exc}", file=sys.stderr)
        return 1

    print(f"{ziel}: {len(kopiert)} Unternehmensseiten-Dateien, "
          f"{len(doku)} Fachdokumente, {adrs} Architektur-Dokumente, "
          "2 Landkarten und der Techstack erzeugt")
    faelle = sorted(
        p.parent.name for p in (ziel / "migrationen").glob("*/index.md")
    ) if (ziel / "migrationen").is_dir() else []
    if faelle:
        print(f"  eingehaengte Migrationsberichte: {', '.join(faelle)}")
    else:
        print("  noch KEIN Migrationsbericht eingehaengt "
              "(vorzeigeseite.py --out <ziel>/migrationen/<fall>)")
    return 0


if __name__ == "__main__":  # pragma: no cover
    raise SystemExit(main())
