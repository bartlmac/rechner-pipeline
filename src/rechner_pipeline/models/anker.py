"""Die Verankerung eines Stands-Pakets AUSSERHALB des Pakets.

Ein Stands-Paket traegt seine eigenen Belege: Protokoll, Manifest,
Tagesjournal. Der Konsument rechnet jede veroeffentlichte Kennzahl daraus
nach (Review T24-04, Teil 1). Das schuetzt gegen ein erfundenes Paket —
aber nicht gegen ein in sich stimmiges gefaelschtes: Die Protokollkette
bindet jede Zeile an ihre Vorgaengerin und schuetzt damit ALLES AUSSER
DER LETZTEN. Genau aus der letzten Zeile leitet ``stand.json`` ab. Wer
beide zusammen umschreibt, bekommt ein Paket, das sich selbst bestaetigt.

Der Anker ist der Ausweg: der Hash der letzten Protokollzeile, abgelegt
an einem Ort, den der schreibende Prozess nicht anfasst. Der Tagesbetrieb
schreibt in die Ablage; der Anker liegt im Fall-Datenraum. Ein Wert, den
der schreibende Prozess selbst aendern kann, ist kein Anker — das ist die
ganze Idee, und sie ist der Grund, warum die Zeichnung jeder Zeile beim
Lauf VERWORFEN wurde: Sie haette einen Schluessel in einen
unbeaufsichtigten Nachtlauf gelegt.

Die Ankerdatei ist NUR ANFUEGBAR (JSON Lines), wie das Protokoll selbst.
Ein ersetzter Anker waere kein Anker; die Reihe der Anker ist die
Geschichte der Auslieferungen.

Das Angreifermodell ist ausdruecklich nicht der boeswillige Mensch
allein (Entscheid des Maintainers 2026-09-16): Der wahrscheinliche Fall
ist ein Lauf oder ein Agent, der etwas Falsches KONSISTENT hinschreibt.
Gegen den hilft keine innere Stimmigkeit, sondern nur ein Bezug nach
aussen.

**Warum hier und nicht in ``betrieb``:** Der Ankersatz ist ein
Datenvertrag zwischen DREI Beteiligten — dem Export, der ihn schreibt
(``betrieb.seite``), der Abnahme, die ihn bindet
(``gates.gate_entscheid --gate A-B1``), und dem Konsumenten, der dagegen
prueft (``werkzeuge/falldaten.py``). In ``betrieb`` gelegen, waere er
fuer die Gates unerreichbar: Die Schichtenkarte laesst ``gates ->
betrieb`` nicht zu, und aus gutem Grund — ein Gate, das den Betrieb
importiert, prueft nicht mehr, es fuehrt mit.

Knoten: klv, bu
"""

from __future__ import annotations

import datetime as _dt
import hashlib
import hmac
import json
from pathlib import Path
from typing import Any, Dict, List, Optional

ANKER_DATEI = "anker.jsonl"
#: Schema 2 (Entscheid des Maintainers 2026-09-16): Der Satz sagt, WAS er
#: ist und WER ihn gezeichnet hat.
ANKER_SCHEMA_VERSION = 2

#: Ein gewoehnlicher Export: eine Momentaufnahme des Stands. Der
#: Betriebsagent zeichnet sie — eine Aussage ueber Urheberschaft.
ART_MOMENTAUFNAHME = "momentaufnahme"
#: Eine Auslieferung: Der Stand wird nach AUSSEN sichtbar. Sie braucht
#: zusaetzlich die menschliche Abnahme A-B1 (mensch/betriebsverantwortung; im
#: Vorzeigebetrieb der simulierte Mensch). Ein Agent kann sie NICHT
#: ersetzen: Was nach aussen geht, verantwortet ein Mensch.
ART_AUSLIEFERUNG = "auslieferung"
ARTEN = (ART_MOMENTAUFNAHME, ART_AUSLIEFERUNG)

#: Dasselbe Verfahren wie bei den Abnahmen (P9_FREIGABE_VERFAHREN). Ein
#: zweiter Mechanismus waere eine zweite Wahrheit ueber dasselbe.
VERFAHREN = "hmac-sha256-v1"


class AnkerFehler(ValueError):
    """Der Anker fehlt, widerspricht dem Paket oder ist unlesbar."""


def zeilen_hash(roh: str) -> str:
    """Der Hash EINER Zeile — dieselbe Rechnung wie in der Protokollkette.

    Hier, nicht importiert: ``betrieb.tageslauf`` importiert dieses Modul
    nicht, und ein Import in der Gegenrichtung waere ein Ring. Die
    Rechnung ist ein SHA-256 ueber die UTF-8-Bytes; ein Test haelt beide
    gegeneinander, damit sie nicht auseinanderlaufen.
    """
    return hashlib.sha256(roh.encode("utf-8")).hexdigest()


def _letzte_zeile(protokoll: Path) -> str:
    """Der ROHTEXT der letzten Protokollzeile.

    Roh, nicht geparst: Gehasht wird, was auf der Platte steht. Eine
    Zeile, die beim Parsen und Wiederausgeben dieselbe Bedeutung, aber
    andere Bytes ergibt, waere sonst derselbe Anker.
    """
    zeilen = [z for z in protokoll.read_text(encoding="utf-8").splitlines()
              if z.strip()]
    if not zeilen:
        raise AnkerFehler(f"{protokoll}: leeres Protokoll — nichts zu verankern")
    return zeilen[-1]


def ankersatz(
    protokoll: Path, stand: str, manifest_sha256: str, journal_sha256: str,
    *, art: str = ART_MOMENTAUFNAHME, erstellt: Optional[str] = None,
) -> Dict[str, Any]:
    """Der Satz, der ein Paket bindet — ohne ihn irgendwo abzulegen."""
    if art not in ARTEN:
        raise AnkerFehler(f"unbekannte Art {art!r} (bekannt: {list(ARTEN)})")
    return {
        "schema_version": ANKER_SCHEMA_VERSION,
        "art": art,
        "stand": str(stand),
        "protokoll_letzte_sha256": zeilen_hash(_letzte_zeile(protokoll)),
        "manifest_sha256": str(manifest_sha256),
        "journal_sha256": str(journal_sha256),
        "erstellt": erstellt or _dt.datetime.now(
            _dt.timezone.utc).replace(microsecond=0).isoformat(),
    }


def _ohne_zeichnung(satz: Dict[str, Any]) -> Dict[str, Any]:
    """Der Satz OHNE seine Zeichnung — das, was gezeichnet wird.

    Eine Signatur ueber sich selbst gibt es nicht; gezeichnet wird der
    Inhalt, und die Zeichnung kommt daneben.
    """
    return {k: v for k, v in satz.items() if k != "zeichnung"}


def zeichne(
    satz: Dict[str, Any], schluessel: bytes, *, rolle: str, klasse: str,
) -> Dict[str, Any]:
    """Den Ankersatz zeichnen — URHEBERSCHAFT, keine Abnahme.

    Ein Agent darf das (ADR-018, Nachtrag 2026-09-16): Er sagt "ich habe
    dieses Paket erzeugt", nicht "ich stehe dafuer ein". Der Beleg traegt
    die Klasse, also verwechselt es niemand. Was ein Agent NICHT zeichnet,
    ist eine Abnahme — dafuer gibt es Gates, und seine gates-Liste ist
    leer.
    """
    nachricht = json.dumps(_ohne_zeichnung(satz), ensure_ascii=False,
                           sort_keys=True, separators=(",", ":")).encode("utf-8")
    return {
        "verfahren": VERFAHREN,
        "rolle": str(rolle),
        "schluesselklasse": str(klasse),
        "schluessel_sha256": hashlib.sha256(schluessel).hexdigest(),
        "signatur": hmac.new(schluessel, nachricht, hashlib.sha256).hexdigest(),
    }


def pruefe_zeichnung(
    satz: Dict[str, Any], schluesselring: Dict[str, bytes],
) -> List[str]:
    """Die Zeichnung eines Ankersatzes gegen einen Schluesselring halten.

    Ohne passenden Schluessel wird NICHT bestaetigt und nicht abgelehnt,
    sondern gesagt, dass es nicht prueflbar war — dieselbe Ehrlichkeit wie
    beim A-M4-Snapshot des Betriebseingangs, der ohne Schluesselring
    "Angaben der Datei" heisst und nie "gezeichnet".
    """
    zeichnung = satz.get("zeichnung")
    if not isinstance(zeichnung, dict):
        return ["Ankersatz ohne Zeichnung"]
    if zeichnung.get("verfahren") != VERFAHREN:
        return [f"unbekanntes Verfahren {zeichnung.get('verfahren')!r}"]
    kennung = zeichnung.get("schluessel_sha256")
    schluessel = schluesselring.get(str(kennung))
    if schluessel is None:
        return [f"Schluessel {str(kennung)[:16]}… nicht bereitgestellt"]
    nachricht = json.dumps(_ohne_zeichnung(satz), ensure_ascii=False,
                           sort_keys=True, separators=(",", ":")).encode("utf-8")
    erwartet = hmac.new(schluessel, nachricht, hashlib.sha256).hexdigest()
    if not hmac.compare_digest(erwartet, str(zeichnung.get("signatur", ""))):
        return ["Signatur stimmt nicht mit dem Inhalt des Ankersatzes ueberein"]
    return []


def satz_hash(satz: Dict[str, Any]) -> str:
    """Der Hash EINES Ankersatzes — die Kennung, die stand.json nennt.

    Ueber die kanonische Form (sortierte Schluessel), damit derselbe Satz
    denselben Hash ergibt, egal wer ihn serialisiert.
    """
    return zeilen_hash(json.dumps(satz, ensure_ascii=False, sort_keys=True))


def haenge_an(verzeichnis: Path, satz: Dict[str, Any]) -> Path:
    """Den Satz an die Ankerdatei anfuegen (nur anfuegbar)."""
    verzeichnis = Path(verzeichnis)
    verzeichnis.mkdir(parents=True, exist_ok=True)
    pfad = verzeichnis / ANKER_DATEI
    with pfad.open("a", encoding="utf-8") as datei:
        datei.write(json.dumps(satz, ensure_ascii=False, sort_keys=True) + "\n")
    return pfad


def lies_anker(pfad: Path) -> List[Dict[str, Any]]:
    """Alle Ankersaetze einer Datei, in der Reihenfolge ihrer Ablage."""
    pfad = Path(pfad)
    if not pfad.is_file():
        raise AnkerFehler(
            f"{pfad} fehlt — ein Stands-Paket wird gegen einen Anker geprueft, "
            "der NICHT im Paket liegt; ohne ihn belegt das Paket nur sich "
            "selbst (Review T24-04, Teil 2)"
        )
    saetze: List[Dict[str, Any]] = []
    for nr, roh in enumerate(pfad.read_text(encoding="utf-8").splitlines(), 1):
        if not roh.strip():
            continue
        try:
            satz = json.loads(roh)
        except ValueError as exc:
            raise AnkerFehler(f"{pfad}: Zeile {nr} ist kein JSON ({exc})") from exc
        if not isinstance(satz, dict):
            raise AnkerFehler(f"{pfad}: Zeile {nr} ist kein Objekt")
        saetze.append(satz)
    if not saetze:
        raise AnkerFehler(f"{pfad}: keine Ankersaetze")
    return saetze


def pruefe(
    paket: Path, stand_json: Dict[str, Any], protokoll: Path,
    saetze: List[Dict[str, Any]],
) -> Dict[str, Any]:
    """Das Paket gegen die Ankersaetze halten; liefert den treffenden Satz.

    Geprueft wird gegen den Anker, den ``stand.json`` NENNT — nicht gegen
    irgendeinen passenden. Sonst genuegte einem Faelscher ein beliebiger
    alter Satz derselben Ablage.
    """
    genannt = stand_json.get("anker")
    if not isinstance(genannt, dict) or not genannt.get("sha256"):
        raise AnkerFehler(
            f"{paket}: stand.json nennt keinen Anker — ein Paket ohne Bezug "
            "nach aussen belegt nur sich selbst; mit --anker exportieren"
        )
    treffer = [s for s in saetze if satz_hash(s) == genannt["sha256"]]
    if not treffer:
        raise AnkerFehler(
            f"{paket}: der von stand.json genannte Ankersatz "
            f"({str(genannt['sha256'])[:16]}…) steht nicht in der Ankerdatei — "
            "das Paket gehoert zu einer anderen Auslieferung, oder der Anker "
            "wurde nicht mitgefuehrt"
        )
    satz = treffer[-1]
    if satz.get("stand") != stand_json.get("stand"):
        raise AnkerFehler(
            f"{paket}: der Anker bindet den Stand {satz.get('stand')!r}, "
            f"stand.json fuehrt {stand_json.get('stand')!r}"
        )
    ist = zeilen_hash(_letzte_zeile(protokoll))
    if satz.get("protokoll_letzte_sha256") != ist:
        raise AnkerFehler(
            f"{paket}: die letzte Protokollzeile des Pakets traegt "
            f"{ist[:16]}…, der Anker nennt "
            f"{str(satz.get('protokoll_letzte_sha256'))[:16]}… — genau diese "
            "Zeile schuetzt die Kette nicht, und der Anker sagt, dass sie "
            "sich geaendert hat"
        )
    return satz
