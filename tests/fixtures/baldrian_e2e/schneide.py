"""Den Baldrian-Fixture-Schnitt aus der vollen Lieferung erzeugen.

EINMALWERKZEUG, nicht Teil der Testsuite. Es liegt beim Fixture, damit
nachvollziehbar bleibt, WIE der Schnitt entstanden ist — ein eingecheckter
Datensatz ohne sein Erzeugungsrezept ist nach einem Jahr eine Blackbox.

**Warum ein Schnitt und nicht der ganze Bestand.** Der volle Fall traegt
500 Vertraege; als Regressionstest kostete er Laufzeit und Repo-Groesse,
ohne mehr zu zeigen. Der Schnitt haelt dagegen ALLE vier Historientypen
und alle vorkommenden Geschaeftsvorfallarten — die Verzweigungen des
Rechenwegs, nicht seine Wiederholungen.

**Was mitgeht und was nicht.** Mit gehen die fachlichen Eingaben und die
UNABHAENGIG gelieferten Erwartungswerte der abgebenden Gesellschaft. Nicht
mit gehen die Laufartefakte: Sie entstehen im Test neu unter ``tmp_path``,
sonst waere ein gitignorierter Fall-Arbeitsbereich eine versteckte
Vorbedingung des Tests.

Aufruf (aus der Repo-Wurzel)::

    python tests/fixtures/baldrian_e2e/schneide.py
"""

from __future__ import annotations

import csv
import hashlib
import json
import shutil
from collections import defaultdict
from pathlib import Path

REPO = Path(__file__).resolve().parents[3]
LIEFERUNG = REPO / "lieferungen" / "baldrian"
FALL = REPO / "faelle" / "baldrian-uebernahme"
ZIEL = Path(__file__).resolve().parent

#: Vertraege je Historientyp. Fuenf reichen fuer die Verzweigungen; die
#: Verteilungsmasse der Abnahme braucht mehr, aber die prueft dieser Test
#: nicht — er prueft, dass die Kette rechnet und dieselben Werte trifft.
JE_TYP = 5


def _lies_csv(pfad: Path):
    with pfad.open(encoding="utf-8") as datei:
        leser = csv.DictReader(datei, delimiter=";")
        return list(leser.fieldnames or []), list(leser)


def _schreib_csv(pfad: Path, spalten, zeilen) -> None:
    with pfad.open("w", encoding="utf-8", newline="") as datei:
        schreiber = csv.DictWriter(datei, fieldnames=spalten, delimiter=";")
        schreiber.writeheader()
        schreiber.writerows(zeilen)


def waehle_policen() -> list[str]:
    """Je Historientyp die ersten Vertraege der GELIEFERTEN Stichprobe.

    Aus der Stichprobe und nicht aus dem Bestand: Nur fuer diese Vertraege
    hat die abgebende Gesellschaft Erwartungswerte geliefert, und ohne
    unabhaengige Erwartung ist ein Vertrag im Fixture wertlos.
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

    # Nur Vertraege, die in BEIDEN Stichtagstests stehen — sonst faellt
    # der Verlaufstest im Fixture auf eine andere Menge.
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

    # Je Vorfallart mindestens einen Vertrag mit Geschaeftsvorfall, damit
    # der Geschaeftsvorfalltest alle Verzweigungen trifft.
    je_art: dict[str, list[str]] = defaultdict(list)
    for v in vorfaelle["vertraege"]:
        for p in v["punkte"]:
            je_art[p["anlass"]].append(str(v["police_id"]))
    for art in sorted(je_art):
        for polnr in sorted(je_art[art]):
            if polnr not in gewaehlt:
                gewaehlt.append(polnr)
                break

    return sorted(set(gewaehlt))


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
    policen = waehle_policen()
    menge = set(policen)
    ZIEL.mkdir(parents=True, exist_ok=True)

    # Bestandsabzuege
    for name in ("baldrian_bestandsabzug_2026-01-01.csv",
                 "baldrian_bestandsabzug_2027-01-01.csv"):
        spalten, zeilen = _lies_csv(LIEFERUNG / name)
        behalten = [z for z in zeilen if z["POLNR"] in menge]
        _schreib_csv(ZIEL / name, spalten, behalten)
        print(f"  {name}: {len(behalten)} von {len(zeilen)} Zeilen")

    # Vorgeschichte und Vorfaelle
    for name in ("baldrian_gevo_metadaten.csv",
                 "baldrian_gevo_protokoll_2026.csv"):
        spalten, zeilen = _lies_csv(LIEFERUNG / name)
        behalten = [z for z in zeilen if z["POLNR"] in menge]
        _schreib_csv(ZIEL / name, spalten, behalten)
        print(f"  {name}: {len(behalten)} von {len(zeilen)} Zeilen")

    # Erwartungswerte je Abnahme
    for name in ("baldrian_erwartungswerte_stichtag.json",
                 "baldrian_erwartungswerte_verlauf.json",
                 "baldrian_erwartungswerte_geschaeftsvorfaelle.json"):
        d = schneide_erwartung(name, menge)
        (ZIEL / name).write_text(
            json.dumps(d, indent=2, ensure_ascii=False, sort_keys=True) + "\n",
            encoding="utf-8")
        print(f"  {name}: {len(d['vertraege'])} Vertraege")

    # Ziehungsbeleg: beide Abnahmemengen auf den Schnitt
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

    # Die nachgereichte Auskunft, dass der Rueckkaufswert herabgesetzter
    # Vertraege kein herleitbarer Erwartungswert ist. Ohne sie wuerde die
    # Kette diese Groesse wertvergleichen und scheitern — zu Recht: Die
    # Ausnahme gilt nur mit REGISTRIERTEM Beleg.
    notiz = LIEFERUNG / "Aktuarielle_Notiz_Stornoabzug.docx"
    if notiz.is_file():
        shutil.copy2(notiz, ZIEL / notiz.name)
        print(f"  {notiz.name}: Plausibilitaetsbeleg uebernommen")

    # Die Parametrierung des Falls: eingefroren, damit der Test die
    # MIGRATION prueft und nicht noch einmal die Quellenauswertung.
    spez = next((FALL / "abgeleitet" / "spez").glob("*.spez.json"), None)
    if spez is not None:
        shutil.copy2(spez, ZIEL / spez.name)
        print(f"  {spez.name}: Parametrierung eingefroren")
    else:
        print("  WARNUNG: keine Spez im Fall gefunden")

    # Die TransformationsSpec: Das MAPPING bleibt unveraendert, nur seine
    # Quellbindung zeigt auf den geschnittenen Abzug. Ohne die Anpassung
    # wiese wende_an den Schnitt zurueck — zu Recht, denn die Spec bindet
    # ihre Quelle per Pruefsumme. Der fachliche Inhalt wird NICHT
    # angefasst; genau er ist der Pruefgegenstand.
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
        json.dumps({"policen": policen, "je_typ": JE_TYP}, indent=2) + "\n",
        encoding="utf-8")
    print(f"\n  {len(policen)} Policen im Schnitt")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
