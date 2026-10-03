"""Der Commit, auf dem eine Linie ein Gate angenommen hat.

    python deploy/welt/abgenommen.py <linie>/entscheide <gate> [<fallauftrag.json>]

Ohne Fallauftrag: die juengste ANNAHME des Gates in der Linie (eine Ablehnung
zaehlt nicht). Mit Fallauftrag: genau die Annahme, auf die der Auftrag den
Fall gestellt hat (``zielsystem.abnahmen``) — auch wenn die Linie seither
weitergegangen ist.

Gelesen von ``fall_nachfahren.sh`` (Helfer ``abgenommen`` im Rezept: das
``--von`` eines Belegs, der die Aenderung gegen den abgenommenen Stand zeigt)
und von ``paket_bauen.sh`` (der Stand, auf dem die Welt eines festgehaltenen
Falls aufgestellt war). Liegt keine solche Annahme, endet das Skript mit einer
Meldung und Exit ungleich null.
"""
import json
import pathlib
import sys

if len(sys.argv) not in (3, 4):
    sys.exit(__doc__)
ort, gate = pathlib.Path(sys.argv[1]), sys.argv[2]


def lies(datei: pathlib.Path) -> dict:
    return json.loads(datei.read_text(encoding="utf-8"))


if len(sys.argv) == 4:
    kennung = (lies(pathlib.Path(sys.argv[3])).get("zielsystem") or {}).get("abnahmen", {}).get(gate)
    datei = ort / f"{gate}-{kennung}.json"
    if not kennung or not datei.is_file():
        sys.exit(f"abgenommen: der Fallauftrag nennt keine Annahme von {gate}, die in der Linie liegt")
    glieder = [lies(datei)]
else:
    glieder = [lies(p) for p in ort.glob(gate + "-*.json")]
glieder = [g for g in glieder if g.get("entscheid") == "angenommen"]
if not glieder:
    sys.exit("abgenommen: in der Linie liegt keine Annahme von " + gate)
print(max(glieder, key=lambda g: g["entschieden_am"])["system"]["commit"])
