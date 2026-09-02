"""Den Fixture-Schnitt des ZWEITEN Baldrian-Laufs erzeugen.

EINMALWERKZEUG, nicht Teil der Testsuite — Muster und Begruendung wie
``tests/fixtures/baldrian_e2e/schneide.py``: Der eingecheckte Schnitt
braucht sein Erzeugungsrezept, sonst ist er nach einem Jahr eine
Blackbox.

**Was der zweite Schnitt zusaetzlich sichern muss.** Die zweite
Lieferung machte SERIEN zum Regelfall und brachte die Faehigkeiten des
zweiten Laufs; der Schnitt haelt deshalb ueber die vier Historientypen
hinaus je VERLAUFSKLASSE der Vorgeschichte mindestens zwei Vertraege
(reine Erhoehungsserie, terminale Beitragsfreistellung mit und ohne
Serie, Herabsetzung vor und nach Erhoehungen, kombinierte Verlaeufe)
und vier namentlich entscheidende Policen: 7000396 und 7000679 (die
dokumentierte Arbeits-Lesart f=0,60 mit Falsifizierbarkeits-Auflage),
7000586 (Anteils-Bestimmung ueber den Ankerwert) und 7000569
(nachgewiesene Anteils-Unerheblichkeit).

Aufruf (aus der Repo-Wurzel)::

    python tests/fixtures/baldrian2_e2e/schneide.py
"""

from __future__ import annotations

import csv
import hashlib
import json
import shutil
from collections import defaultdict
from pathlib import Path

REPO = Path(__file__).resolve().parents[3]
LIEFERUNG = REPO / "lieferungen" / "baldrian-2"
FALL = REPO / "faelle" / "baldrian-klv-tg2015-lauf2"
ZIEL = Path(__file__).resolve().parent

#: Vertraege je Historientyp aus der gelieferten Stichprobe — wie im
#: ersten Schnitt: die Verzweigungen, nicht die Verteilungsmasse.
JE_TYP = 4
#: Vertraege je Verlaufsklasse der Vorgeschichte (zusaetzlich).
JE_KLASSE = 2
#: Namentlich entscheidende Policen des zweiten Laufs (siehe Docstring).
PFLICHT = ("7000396", "7000679", "7000586", "7000569")


def _lies_csv(pfad: Path):
    with pfad.open(encoding="utf-8") as datei:
        leser = csv.DictReader(datei, delimiter=";")
        return list(leser.fieldnames or []), list(leser)


def _schreib_csv(pfad: Path, spalten, zeilen) -> None:
    with pfad.open("w", encoding="utf-8", newline="") as datei:
        schreiber = csv.DictWriter(datei, fieldnames=spalten, delimiter=";")
        schreiber.writeheader()
        schreiber.writerows(zeilen)


def _verlaufsklassen() -> dict[str, list[str]]:
    """Jede Police mit Vorgeschichte ihrer Verlaufsklasse zuordnen."""
    _, zeilen = _lies_csv(LIEFERUNG / "baldrian_gevo_metadaten.csv")
    folgen: dict[str, list[str]] = defaultdict(list)
    for z in zeilen:
        folgen[z["POLNR"]].append(z["GEVO"])

    def klasse(arten: list[str]) -> str:
        if "RED" in arten and "ERH" in arten:
            if arten[-1] == "PEX":
                return "serie+red+pex"
            if arten.index("RED") < arten.index("ERH"):
                return "red-vor-erh"
            return "serie+red"
        if "RED" in arten:
            return "nur-red"
        if arten[-1] == "PEX" and len(arten) > 1:
            return "serie+pex"
        if arten == ["PEX"]:
            return "nur-pex"
        return "nur-erh"

    klassen: dict[str, list[str]] = defaultdict(list)
    for polnr, arten in sorted(folgen.items()):
        klassen[klasse(arten)].append(polnr)
    return klassen


def waehle_policen() -> dict[str, list[str]]:
    """Stichproben-Kern plus Verlaufsklassen plus Pflicht-Policen.

    Der Kern kommt aus der GELIEFERTEN Stichprobe (nur dort gibt es
    A-M1/A-M2-Erwartungswerte); die Klassen- und Pflicht-Policen
    kommen notfalls von ausserhalb — sie werden dann vom
    Migrationscontrolling gegen die Abzuege geprueft, das den ganzen
    Schnitt traegt.
    """
    stichtag = json.loads(
        (LIEFERUNG / "baldrian_erwartungswerte_stichtag.json")
        .read_text(encoding="utf-8"))
    verlauf = json.loads(
        (LIEFERUNG / "baldrian_erwartungswerte_verlauf.json")
        .read_text(encoding="utf-8"))
    vorfaelle = json.loads(
        (LIEFERUNG / "baldrian_erwartungswerte_geschaeftsvorfaelle.json")
        .read_text(encoding="utf-8"))

    gemeinsam = ({str(v["police_id"]) for v in stichtag["vertraege"]}
                 & {str(v["police_id"]) for v in verlauf["vertraege"]})

    je_typ: dict[str, list[str]] = defaultdict(list)
    for v in stichtag["vertraege"]:
        polnr = str(v["police_id"])
        if polnr in gemeinsam:
            je_typ[v.get("historientyp", "unbekannt")].append(polnr)

    gewaehlt: list[str] = []
    for typ in sorted(je_typ):
        gewaehlt.extend(sorted(je_typ[typ])[:JE_TYP])

    klassen = _verlaufsklassen()
    for name in sorted(klassen):
        # Bevorzugt Policen, die schon im Stichproben-Kern liegen; erst
        # dann von aussen auffuellen.
        drin = [p for p in klassen[name] if p in gewaehlt]
        for polnr in sorted(klassen[name]):
            if len(drin) >= JE_KLASSE:
                break
            if polnr not in gewaehlt:
                gewaehlt.append(polnr)
                drin.append(polnr)

    for polnr in PFLICHT:
        if polnr not in gewaehlt:
            gewaehlt.append(polnr)

    je_art: dict[str, list[str]] = defaultdict(list)
    for v in vorfaelle["vertraege"]:
        for p in v["punkte"]:
            je_art[p["anlass"]].append(str(v["police_id"]))
    for art in sorted(je_art):
        if not any(p in gewaehlt for p in je_art[art]):
            gewaehlt.append(sorted(je_art[art])[0])

    return {
        "policen": sorted(set(gewaehlt)),
        "je_typ": JE_TYP,
        "je_klasse": JE_KLASSE,
        "pflicht": list(PFLICHT),
        "klassen": {k: sorted(set(v) & set(gewaehlt))
                    for k, v in sorted(klassen.items())},
    }


def schneide_erwartung(name: str, policen: set[str]) -> dict:
    d = json.loads((LIEFERUNG / name).read_text(encoding="utf-8"))
    d["vertraege"] = [v for v in d["vertraege"]
                      if str(v["police_id"]) in policen]
    behalten = sorted(str(v["police_id"]) for v in d["vertraege"])
    d["stichprobe"] = {
        **d["stichprobe"],
        "police_ids": behalten,
        "umfang": len(behalten),
        "grundgesamtheit": len(behalten),
        "vollerhebung": True,
    }
    return d


def main() -> int:
    auswahl = waehle_policen()
    menge = set(auswahl["policen"])
    ZIEL.mkdir(parents=True, exist_ok=True)

    for name in ("baldrian_bestandsabzug_2026-01-01.csv",
                 "baldrian_bestandsabzug_2027-01-01.csv",
                 "baldrian_gevo_metadaten.csv",
                 "baldrian_gevo_protokoll_2026.csv"):
        spalten, zeilen = _lies_csv(LIEFERUNG / name)
        behalten = [z for z in zeilen if z["POLNR"] in menge]
        _schreib_csv(ZIEL / name, spalten, behalten)
        print(f"  {name}: {len(behalten)} von {len(zeilen)} Zeilen")

    for name in ("baldrian_erwartungswerte_stichtag.json",
                 "baldrian_erwartungswerte_verlauf.json",
                 "baldrian_erwartungswerte_geschaeftsvorfaelle.json"):
        d = schneide_erwartung(name, menge)
        (ZIEL / name).write_text(
            json.dumps(d, indent=2, ensure_ascii=False, sort_keys=True) + "\n",
            encoding="utf-8")
        print(f"  {name}: {len(d['vertraege'])} Vertraege")

    beleg = json.loads(
        (LIEFERUNG / "baldrian_erwartungswerte_stichprobe.json")
        .read_text(encoding="utf-8"))
    vorfaelle = json.loads(
        (ZIEL / "baldrian_erwartungswerte_geschaeftsvorfaelle.json")
        .read_text(encoding="utf-8"))
    stichtag = json.loads(
        (ZIEL / "baldrian_erwartungswerte_stichtag.json")
        .read_text(encoding="utf-8"))
    beleg["A-M1_A-M2"] = stichtag["stichprobe"]
    beleg["A-M3"] = vorfaelle["stichprobe"]
    beleg["hinweis"] = (
        beleg.get("hinweis", "")
        + " Fuer den Testschnitt auf eine Teilmenge gekuerzt; die Ziehung "
          "selbst blieb unveraendert.")
    (ZIEL / "baldrian_erwartungswerte_stichprobe.json").write_text(
        json.dumps(beleg, indent=2, ensure_ascii=False, sort_keys=True) + "\n",
        encoding="utf-8")

    # Die Parametrierung des abgenommenen Laufs (A-Q1-gezeichnete Spez):
    # eingefroren, damit der Test die MIGRATION prueft und nicht noch
    # einmal die Quellenauswertung.
    spez = next((FALL / "abgeleitet" / "spez").glob("*.spez.json"), None)
    if spez is not None:
        shutil.copy2(spez, ZIEL / spez.name)
        print(f"  {spez.name}: Parametrierung eingefroren")
    else:
        print("  WARNUNG: keine Spez im Fall gefunden")

    spec_quelle = next(
        (FALL / "abgeleitet" / "transformation").glob("*.spec.json"), None)
    if spec_quelle is not None:
        spec = json.loads(spec_quelle.read_text(encoding="utf-8"))
        abzug = ZIEL / "baldrian_bestandsabzug_2026-01-01.csv"
        spec["quelle_datei"] = abzug.name
        spec["quelle_sha256"] = hashlib.sha256(abzug.read_bytes()).hexdigest()
        spec.setdefault("anmerkungen", []).append(
            "Fuer den Testschnitt auf den gekuerzten Abzug gebunden; die "
            "Feldabbildung ist unveraendert.")
        (ZIEL / "transformation.spec.json").write_text(
            json.dumps(spec, indent=2, ensure_ascii=False, sort_keys=True)
            + "\n", encoding="utf-8")
        print(f"  transformation.spec.json: {len(spec['felder'])} Felder, "
              "Quellbindung angepasst")
    else:
        print("  WARNUNG: keine TransformationsSpec im Fall gefunden")

    (ZIEL / "policen.json").write_text(
        json.dumps(auswahl, indent=2, ensure_ascii=False, sort_keys=True)
        + "\n", encoding="utf-8")
    print(f"\n  {len(auswahl['policen'])} Policen im Schnitt")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
