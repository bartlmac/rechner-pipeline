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
import os
from pathlib import Path
from typing import Any, Dict, List, Optional

ANKER_DATEI = "anker.jsonl"
#: Schema 2 (Entscheid des Maintainers 2026-09-16): Der Satz sagt, WAS er
#: ist und WER ihn gezeichnet hat.
#: Schema 3 (Angriffsrunde nach T27): Der Satz bindet zusaetzlich die
#: vollstaendige Dateiliste des Pakets (``dateien_sha256``) — jede
#: mitgelieferte Datei haengt damit am externen Anker, nicht nur Manifest,
#: Journal und die letzte Protokollzeile.
ANKER_SCHEMA_VERSION = 3

#: Ein gewoehnlicher Export: eine Momentaufnahme des Stands. Der
#: Betriebsagent zeichnet sie — eine Aussage ueber Urheberschaft.
ART_MOMENTAUFNAHME = "momentaufnahme"
#: Eine Auslieferung: Der Stand wird nach AUSSEN sichtbar. Sie braucht
#: zusaetzlich die menschliche Abnahme A-B1 (mensch/betrieb; im
#: Vorzeigebetrieb der simulierte Mensch). Ein Agent kann sie NICHT
#: ersetzen: Was nach aussen geht, verantwortet ein Mensch.
ART_AUSLIEFERUNG = "auslieferung"
ARTEN = (ART_MOMENTAUFNAHME, ART_AUSLIEFERUNG)

#: Dasselbe Verfahren wie bei den Abnahmen (P9_FREIGABE_VERFAHREN). Ein
#: zweiter Mechanismus waere eine zweite Wahrheit ueber dasselbe.
#: Das Zeichenverfahren. v1 signierte den Satz OHNE das gesamte
#: ``zeichnung``-Objekt: Rolle und Schluesselklasse standen UNSIGNIERT
#: daneben und liessen sich austauschen, ohne dass die Signatur fiel —
#: aus ``agent/betrieb``/``agent`` wurde ``mensch/betrieb``/``mensch``,
#: und der Schluesselring bestaetigte es (Befund T26-16). Genau diese
#: Klasse ist es, um derentwillen ADR-018 die Trennung von Agent und
#: Mensch am BELEG ablesbar macht.
#:
#: v2 signiert Rolle, Klasse, Verfahren und Schluesselkennung mit;
#: ausgenommen ist nur das Signaturfeld selbst, denn eine Signatur ueber
#: sich selbst gibt es nicht.
VERFAHREN = "hmac-sha256-v2"
#: Aeltere Saetze bleiben PRUEFBAR. Ein Verfahren zu wechseln darf nicht
#: heissen, dass die Geschichte unlesbar wird; die Ankerreihe ist nur
#: anfuegbar, und was einmal gezeichnet wurde, bleibt stehen. Was v1
#: NICHT deckt, sagt :func:`deckt_urheberschaft`.
VERFAHREN_ALT = "hmac-sha256-v1"
BEKANNTE_VERFAHREN = (VERFAHREN, VERFAHREN_ALT)


def deckt_urheberschaft(zeichnung: Dict[str, Any]) -> bool:
    """Ob das Verfahren dieser Zeichnung Rolle und Klasse mitsigniert.

    Der Unterschied ist keine Feinheit: Eine v1-Zeichnung bezeugt den
    INHALT des Ankersatzes, aber nicht, WER ihn erzeugt hat. Wer die
    Urheberklassifikation liest, muss wissen, ob sie getragen ist.
    """
    return isinstance(zeichnung, dict) and zeichnung.get("verfahren") == VERFAHREN


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


def jsonl_zeilen(text: str) -> List[str]:
    """Die Zeilen einer JSONL-Datei — getrennt an LF, genau wie geschrieben.

    ``str.splitlines`` trennt auch an U+2028, U+0085 und anderen Zeichen,
    die ``json.dumps(..., ensure_ascii=False)`` roh in eine Zeile schreibt
    (Angriffsrunde nach T27: ein Fallname mit U+2028 machte das Protokoll
    ab dem zweiten Lauf unlesbar). Schreiber und Leser benutzen dieselbe
    Zeilengrenze; leere Zeilen zaehlen nicht. Ein Rest ohne LF am Ende ist
    nie eine Zeile geworden (der Tageslauf schneidet ihn ab) und zaehlt
    auch hier nicht (Angriffsrunde nach T27: der Export verankerte ein
    solches Fragment, und nach dem Schnitt fehlte die verankerte Zeile).
    """
    return [z for z in text[: text.rfind("\n") + 1].split("\n") if z.strip()]


def dateien_hash(dateien: Dict[str, Any]) -> str:
    """Der Hash der Dateiliste eines Pakets (Name -> SHA-256), kanonisch."""
    return hashlib.sha256(json.dumps(
        {str(k): str(v) for k, v in dict(dateien).items()},
        sort_keys=True, ensure_ascii=True).encode("ascii")).hexdigest()


def _protokolltext(protokoll: Path) -> str:
    return Path(protokoll).read_text(encoding="utf-8")


def _letzte_zeile(protokoll: Path, *, text: Optional[str] = None) -> str:
    """Der ROHTEXT der letzten Protokollzeile.

    Roh, nicht geparst: Gehasht wird, was auf der Platte steht. Eine
    Zeile, die beim Parsen und Wiederausgeben dieselbe Bedeutung, aber
    andere Bytes ergibt, waere sonst derselbe Anker.
    """
    zeilen = jsonl_zeilen(text if text is not None else _protokolltext(protokoll))
    if not zeilen:
        raise AnkerFehler(f"{protokoll}: leeres Protokoll — nichts zu verankern")
    return zeilen[-1]


def ankersatz(
    protokoll: Path, stand: str, manifest_sha256: str, journal_sha256: str,
    *, art: str = ART_MOMENTAUFNAHME, erstellt: Optional[str] = None,
    dateien: Optional[Dict[str, Any]] = None,
) -> Dict[str, Any]:
    """Der Satz, der ein Paket bindet — ohne ihn irgendwo abzulegen.

    ``dateien``: die Dateiliste des Pakets (stand.json["dateien"]); der
    Satz bindet ihren Hash, damit auch Bericht und Seite am Anker haengen.
    """
    if art not in ARTEN:
        raise AnkerFehler(f"unbekannte Art {art!r} (bekannt: {list(ARTEN)})")
    satz = {
        "schema_version": ANKER_SCHEMA_VERSION,
        "art": art,
        "stand": str(stand),
        "protokoll_letzte_sha256": zeilen_hash(_letzte_zeile(protokoll)),
        "manifest_sha256": str(manifest_sha256),
        "journal_sha256": str(journal_sha256),
        "erstellt": erstellt or _dt.datetime.now(
            _dt.timezone.utc).replace(microsecond=0).isoformat(),
    }
    if dateien is not None:
        satz["dateien_sha256"] = dateien_hash(dateien)
    return satz


def pruefe_reihe(saetze: List[Dict[str, Any]], protokoll_text: str, quelle: str) -> None:
    """Jeder Satz der Ankerdatei bezeugt eine Zeile, die im Protokoll steht.

    Angriffsrunde nach T27: Die Reihe wurde nie als Reihe gelesen. Eine
    schon verankerte letzte Protokollzeile liess sich in der Ablage
    umschreiben (in_force 16 -> 1016), neu exportieren und verankern — der
    frueheren Satz, der die echte Zeile bezeugte, fragte niemand. Das
    Protokoll ist nur-anfuegbar: Was einmal verankert war, steht in jeder
    spaeteren Fassung noch da. Fehlt eine bezeugte Zeile, wurde die Kette
    umgeschrieben — oder die Ankerdatei gehoert zu einer anderen Ablage
    (nach einem Neuaufsetzen gehoert ein neues Ankerverzeichnis dazu).
    """
    vorhanden = {zeilen_hash(z) for z in jsonl_zeilen(protokoll_text)}
    fehlend = [s for s in saetze if s.get("protokoll_letzte_sha256") not in vorhanden]
    if fehlend:
        raise AnkerFehler(
            f"{quelle}: {len(fehlend)} verankerte Protokollzeile(n) stehen nicht "
            f"mehr im Protokoll (z. B. Stand {fehlend[0].get('stand')!r}, "
            f"{str(fehlend[0].get('protokoll_letzte_sha256'))[:16]}…) — die Kette "
            "wurde nach der Verankerung umgeschrieben, oder die Ankerdatei gehoert "
            "zu einer anderen Ablage (nach einem Neuaufsetzen ein neues "
            "Ankerverzeichnis waehlen)")


def _nachricht(satz: Dict[str, Any], *, verfahren: str) -> bytes:
    """Die Bytes, ueber die gezeichnet wird — je nach Verfahren.

    v1 liess das ganze ``zeichnung``-Objekt weg. v2 nimmt es mit und
    laesst nur das Signaturfeld aus: Eine Signatur ueber sich selbst gibt
    es nicht, aber Rolle und Klasse gehoeren in die Aussage.
    """
    rumpf = {k: v for k, v in satz.items() if k != "zeichnung"}
    if verfahren != VERFAHREN_ALT:
        zeichnung = satz.get("zeichnung")
        rumpf["zeichnung"] = {
            k: v for k, v in (zeichnung or {}).items() if k != "signatur"
        }
    return json.dumps(rumpf, ensure_ascii=False, sort_keys=True,
                      separators=(",", ":")).encode("utf-8")


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
    kopf = {
        "verfahren": VERFAHREN,
        "rolle": str(rolle),
        "schluesselklasse": str(klasse),
        "schluessel_sha256": hashlib.sha256(schluessel).hexdigest(),
    }
    nachricht = _nachricht({**satz, "zeichnung": kopf}, verfahren=VERFAHREN)
    return {
        **kopf,
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
    verfahren = str(zeichnung.get("verfahren"))
    if verfahren not in BEKANNTE_VERFAHREN:
        return [f"unbekanntes Verfahren {zeichnung.get('verfahren')!r}"]
    kennung = zeichnung.get("schluessel_sha256")
    schluessel = schluesselring.get(str(kennung))
    if schluessel is None:
        return [f"Schluessel {str(kennung)[:16]}… nicht bereitgestellt"]
    nachricht = _nachricht(satz, verfahren=verfahren)
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


def _schneide_fragment(pfad: Path) -> bool:
    """Ein angefangenes, nie abgeschlossenes Fragment am Ende entfernen.

    Eine Zeile der Ankerdatei gilt als geschrieben, wenn sie mit einem
    Zeilenumbruch endet — die Commitgrenze eines anfuegbaren Journals,
    dieselbe wie im Tagesprotokoll (betrieb.tageslauf._schneide_teilzeile).
    Ein Prozessende mitten im Anfuegen liess ein Fragment ohne Umbruch
    zurueck; ``lies_anker`` brach an ihm ab, und der naechste Export
    schrieb seinen Satz DAHINTER — beide verschmolzen zu einer kaputten
    Zeile, die ganze Ankerhistorie war dauerhaft unlesbar, jede spaetere
    Auslieferung nicht mehr pruefbar (Kalibrierungsfund N8 der Pruefrunde
    T27). Abgeschnitten wird IN der Datei (``os.truncate``): belegte
    Saetze gehen durch keinen Schreibpfad.
    """
    if not pfad.is_file():
        return False
    roh = pfad.read_bytes()
    if not roh or roh.endswith(b"\n"):
        return False
    os.truncate(pfad, roh.rfind(b"\n") + 1)
    return True


def haenge_an(verzeichnis: Path, satz: Dict[str, Any]) -> Path:
    """Den Satz an die Ankerdatei anfuegen (nur anfuegbar).

    Vorher faellt ein Fragment eines abgebrochenen Anfuegens — der neue
    Satz beginnt an einer Commitgrenze, nie hinter einem halben Satz.
    """
    verzeichnis = Path(verzeichnis)
    verzeichnis.mkdir(parents=True, exist_ok=True)
    pfad = verzeichnis / ANKER_DATEI
    _schneide_fragment(pfad)
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
    text = pfad.read_text(encoding="utf-8")
    if text and not text.endswith("\n"):
        # Ein Fragment ohne Umbruch ist nie ein Satz geworden (siehe
        # _schneide_fragment) — es zaehlt nicht, und es macht die
        # belegten Saetze davor nicht unlesbar.
        text = text[: text.rfind("\n") + 1]
    for nr, roh in enumerate(jsonl_zeilen(text), 1):
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
    saetze: List[Dict[str, Any]], *, protokoll_text: Optional[str] = None,
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
    # EINE Lesung (Angriffsrunde nach T27): Der Konsument prueft Kette und
    # Felder auf den Bytes, die er gelesen hat; die Ankerpruefung las das
    # Protokoll ein zweites Mal, und ein Tausch dazwischen liess ein
    # gefaelschtes Paket durch.
    text = protokoll_text if protokoll_text is not None else _protokolltext(protokoll)
    ist = zeilen_hash(_letzte_zeile(protokoll, text=text))
    if satz.get("protokoll_letzte_sha256") != ist:
        raise AnkerFehler(
            f"{paket}: die letzte Protokollzeile des Pakets traegt "
            f"{ist[:16]}…, der Anker nennt "
            f"{str(satz.get('protokoll_letzte_sha256'))[:16]}… — genau diese "
            "Zeile schuetzt die Kette nicht, und der Anker sagt, dass sie "
            "sich geaendert hat"
        )
    pruefe_reihe(saetze, text, str(paket))
    if int(satz.get("schema_version") or 0) >= 3:
        soll = satz.get("dateien_sha256")
        if soll != dateien_hash(stand_json.get("dateien") or {}):
            raise AnkerFehler(
                f"{paket}: die Dateiliste von stand.json ist nicht die, die der "
                "Anker bindet — eine mitgelieferte Datei wurde nach dem Export "
                "ersetzt")
    return satz
