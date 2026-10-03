"""Hat ein Mensch das Gate schon selbst gezeichnet?

    python deploy/welt/gezeichnet.py <entscheide> <gate> <k>
    python deploy/welt/gezeichnet.py <entscheide> <gate> --beleg <rolle> <datei>

Gelesen von ``fall_nachfahren.sh``, bevor ein Rezept zeichnet: Wer an einem
Haltepunkt selbst gezeichnet hat, dessen Zeichnung gilt — das Rezept zeichnet
nicht ein zweites Mal, und nie ueber eine Ablehnung hinweg. Antwort auf stdout:

    gezeichnet   die Annahme liegt schon
    abgelehnt    die juengste Zeichnung des Gates ist eine Ablehnung
    offen        das Rezept zeichnet

Erste Form (Gates des Falls): Liegen im Fall mindestens ``k`` Annahmen des
Gates, ist die ``k``-te Zeichnung des Rezepts schon geleistet. Zweite Form
(A-B3 in der Linie, die schon eine Erstabnahme traegt): Es liegt eine Annahme,
die unter der Rolle genau diese Datei pinnt (SHA-256).

Eine Anzeige, kein Urteil: Ob eine Zeichnung GILT, pruefen die Gates, wenn
der Fall weitergeht.
"""
import hashlib
import json
import pathlib
import sys

if len(sys.argv) not in (4, 6) or (len(sys.argv) == 6 and sys.argv[3] != "--beleg"):
    sys.exit(__doc__)
ort, gate = pathlib.Path(sys.argv[1]), sys.argv[2]
glieder = [json.loads(p.read_text(encoding="utf-8")) for p in ort.glob(gate + "-*.json")]
annahmen = [g for g in glieder if g.get("entscheid") == "angenommen"]
if len(sys.argv) == 6:
    rolle, datei = sys.argv[4], pathlib.Path(sys.argv[5])
    summe = hashlib.sha256(datei.read_bytes()).hexdigest()
    liegt = any(summe in (g.get("pflichtbelege") or {}).get(rolle, []) for g in annahmen)
else:
    liegt = len(annahmen) >= int(sys.argv[3])
if liegt:
    print("gezeichnet")
elif glieder and max(glieder, key=lambda g: g["entschieden_am"]).get("entscheid") == "abgelehnt":
    print("abgelehnt")
else:
    print("offen")
