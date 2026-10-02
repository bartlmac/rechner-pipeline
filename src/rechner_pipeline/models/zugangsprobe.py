"""Der Beleg der Zugangsprobe — ein Vertrag, drei Leser (ADR-022).

Die Zugangsprobe (``betrieb.zugangsprobe``) schreibt ihn, das Gate A-B2
(``gates.gate_entscheid``) nimmt ihn ab, die Registrierung
(``betrieb.uebernahme``) haelt ihre eigene ``eingang.json`` und den Stand
der Ablage dagegen. Die Schichtenkarte laesst ``gates -> betrieb`` nicht
zu, und ``betrieb -> gates`` ebenso wenig; der Vertrag wohnt deshalb hier,
wie der Belegrollen-Vertrag (``models.belegrollen``) und der Ankersatz
(``models.anker``). Einmal definiert, kann das Urteil, das der Producer
faellt, und das Urteil, das das Gate nachrechnet, nicht auseinanderlaufen.

**Was der Beleg aussagt** (Entscheid des Maintainers 2026-09-30). Zwei
deterministische Laeufe auf einer Kopie der produktiven Ablage, einmal
ohne und einmal mit dem Eingang, vom gefuehrten Tag ueber den
Zugangsstichtag bis zum naechsten Monatsabschluss. Ihre Differenz muss
exakt der abgenommene Bestand sein. Die verglichenen Groessen stehen in
:data:`GROESSEN` — und im Beleg selbst, damit ein Leser sieht, WAS
verglichen wurde, und eine Ratsche die beiden Listen gegeneinander haelt.

**Der Stand der Ablage** (:func:`stand_sha256`) ist der GEFUEHRTE Stand:
die letzte gruene Protokollzeile, das Manifest des Stands, die Config.
Ein roter Lauf aendert ihn nicht, ein gruener schon. Der Tageslauf
rechnet ihn beim Eintritt eines Eingangs nach; bindet die Abnahme einen
anderen Stand, tritt der Eingang nicht ein ("Probe auf einer Ablage, die
danach weiterlief", ADR-022).

Knoten: system/entscheid
"""

from __future__ import annotations

import datetime as _dt
import hashlib
import json
import math
import re
from typing import Any, Dict, List, Mapping, Optional, Sequence, Tuple

#: Schema des Belegs. 2 (2026-10-01): Deckungskapital, Rueckkaufswert und
#: Korrekturschicht werden je Vertrag gegen den Fuehrungswert der
#: Migrationssuite verglichen (``models.fuehrungswert``); Fassung 1 fuehrte
#: das Deckungskapital "nicht vergleichbar" und ist keine Zugangsprobe mehr.
SCHEMA_VERSION = 2
#: Die Art des Belegs — steht im Beleg, damit ein fremder JSON-Beleg an
#: seinem Ort nicht als Zugangsprobe durchgeht.
ART = "zugangsprobe"
#: Der feste Ort im Fall (relativ zur Fallwurzel). Wie bei A-O1 und A-K2
#: kein Kommandozeilen-Pfad fuer das Gate: Ein Beleg, der dorthin zeigen
#: kann, wo es gerade passt, bindet nichts.
BELEG_RELATIV = "abgeleitet/berichte/zugangsprobe.json"

#: Die verglichenen Groessen, in der Reihenfolge des Berichts.
#:
#: * ``in_kraft``, ``versicherungssumme``, ``deckungskapital``,
#:   ``rueckkaufswert``, ``korrekturschicht``, ``jahresbeitrag`` — je
#:   Monatsabschluss die Differenz der Abschluesse "mit" minus "ohne"
#:   (Zeilen, die nur "mit" traegt), am Zugangsstichtag gegen die Uebernahme
#:   und die Migrationssuite (je Vertrag des ganzen Zugangs), am Folgetermin
#:   gegen die Migrationssuite, soweit der Termin gedeckt ist. Deckungs-
#:   kapital, Rueckkaufswert und Korrekturschicht gegen den FUEHRUNGSWERT
#:   der Suite (``models.fuehrungswert``): was die Bestandsfuehrung in der
#:   Welt der Abnahme fuer den Vertrag fuehrt, in der Konvention des
#:   Abschlusses (Entscheid des Maintainers 2026-10-01);
#: * ``zugang`` — die Zugaenge der uebernommenen Vertraege im Fenster gegen
#:   ihre Anzahl;
#: * ``zugangsbuchungen`` — die Buchungen der uebernommenen Vertraege bis
#:   zum Stichtag gegen den Ledger der Uebernahme;
#: * ``bewegungskonto`` — Anfang + Zugang - Abgang = Ende der Differenz je
#:   Abschlussperiode;
#: * ``ausserhalb_des_zugangs`` — alles, was nicht den Zugang betrifft
#:   (Abschlusszeilen fremder Vertraege, Abschluesse vor dem Stichtag,
#:   Journalzeilen fremder Vertraege), ist in beiden Laeufen gleich.
GROESSEN = (
    "in_kraft", "versicherungssumme", "deckungskapital", "rueckkaufswert",
    "korrekturschicht", "jahresbeitrag",
    "zugang", "zugangsbuchungen", "bewegungskonto", "ausserhalb_des_zugangs",
)

#: Die Groessen, die gegen den Fuehrungswert der Suite gehalten werden.
#:
#: Bis 2026-10-01 stand das Deckungskapital hier "nicht vergleichbar": Der
#: Abschluss fuehrte die Jahreszeile, A-M1 und die Suite rechneten die
#: Monatsreserve — zwei verschiedene Groessen. Entschieden ist seitdem
#: zweierlei: Der Abschluss rechnet monatsgenau (ADR-011 Nachtrag), und
#: die Abnahme weist den Wert aus, den die Fuehrung fuehrt (A-M4,
#: Fuehrungswert). Verglichen wird damit dieselbe Groesse in derselben
#: Konvention, je Vertrag ueber den ganzen Zugang.
FUEHRUNGSWERT_VERGLICHEN = ("deckungskapital", "rueckkaufswert", "korrekturschicht")
#: Groessen, die am Zugangsstichtag ein Soll haben MUESSEN — ohne sie ist
#: die Differenz nicht gegen die Abnahme gehalten, sondern nur berichtet.
PFLICHT_AM_STICHTAG = ("in_kraft", "versicherungssumme", "deckungskapital",
                       "rueckkaufswert", "korrekturschicht", "jahresbeitrag")

#: Jede Bewertungsgroesse des Abschlusses (``models.bestand.ABSCHLUSS_ZAHLEN``,
#: aus dem Spaltentyp hergeleitet) ist entweder einer verglichenen Groesse
#: zugeordnet oder mit Grund als "nicht belegt" ausgenommen (Block F,
#: Nachbesserung, Pruefer-Befund 8). Eine Ratsche haelt beide Mengen mit
#: ``==`` gegen die Spalten: Wer dem Abschluss eine Bewertungsgroesse gibt,
#: muss hier sagen, ob die Zugangsprobe sie haelt.
ABSCHLUSS_VERGLICHEN: Dict[str, str] = {
    "leistung": "versicherungssumme",
    "deckungskapital": "deckungskapital",
    "rueckkaufswert": "rueckkaufswert",
    "korrekturschicht": "korrekturschicht",
    "jahresbeitrag": "jahresbeitrag",
}
ABSCHLUSS_NICHT_BELEGT: Dict[str, str] = {
    "vs_bfr": (
        "nicht belegt als Abschlussspalte: die beitragsfreie Summe haelt die Probe "
        "ueber die PEX-Umbuchung der Uebernahme (zugangsbuchungen)"),
}


def abdeckung() -> Dict[str, Dict[str, str]]:
    """Die Abdeckung der Abschlussspalten, wie sie im Beleg steht."""
    return {
        **{s: {"groesse": g} for s, g in ABSCHLUSS_VERGLICHEN.items()},
        **{s: {"nicht_belegt": grund} for s, grund in ABSCHLUSS_NICHT_BELEGT.items()},
    }


#: Die Belege der Abnahmen, aus denen die Probe ihr Soll liest — je Rolle
#: der Snapshot, der sie pinnt, und ihr fester Ort im Fall (Block F,
#: Nachbesserung, Pruefer-Befund 1). Das Soll ist nur dann das der
#: Abnahme, wenn seine Bytes die sind, die der GELTENDE, angenommene
#: Snapshot als Pflichtbeleg pinnt: ``aktuartest`` im A-M1-Snapshot, den
#: der A-M4-Snapshot als ``am1_snapshot`` pinnt, ``migrationssuite`` im
#: A-M4-Snapshot selbst. Sonst rechnete die Probe gegen eine Datei, die
#: jeder ohne Schluessel ersetzen kann.
SOLL_BELEGE: Dict[str, Tuple[str, str]] = {
    "aktuartest": ("A-M1", "abgeleitet/berichte/aktuartest.json"),
    "migrationssuite": ("A-M4", "abgeleitet/berichte/migrationssuite.json"),
}


def soll_bindung_fehler(
    abnahmen: Any, *, am4: Mapping[str, Any], am1: Optional[Mapping[str, Any]],
) -> List[str]:
    """Die Soll-Bindung eines Belegs gegen die Pins der Snapshots.

    ``am4`` ist der geltende, angenommene A-M4-Snapshot, ``am1`` der
    A-M1-Snapshot, den er als ``am1_snapshot`` pinnt (None: nicht
    gefunden). Probe, Gate und Registrierung fragen dieselbe Funktion —
    eine Regel, drei Leser. Leer = gebunden.
    """
    fehler: List[str] = []
    if not isinstance(abnahmen, dict) or set(abnahmen) != set(SOLL_BELEGE):
        return [f"abnahmen: erwartet genau {sorted(SOLL_BELEGE)}"]
    pins4 = am4.get("pflichtbelege") or {}
    suite = abnahmen["migrationssuite"]
    if pins4.get("migrationssuite") != [suite.get("sha256")]:
        fehler.append(
            f"migrationssuite.json {str(suite.get('sha256'))[:16]}… ist nicht die Suite, "
            f"die der A-M4-Snapshot pinnt ({pins4.get('migrationssuite')})")
    if suite.get("snapshot_sha256") != am4.get("snapshot_sha256"):
        fehler.append("migrationssuite: gebunden an einen anderen A-M4-Snapshot")
    at = abnahmen["aktuartest"]
    if pins4.get("am1_snapshot") != [at.get("snapshot_sha256")]:
        fehler.append(
            f"aktuartest: gebunden an den A-M1-Snapshot {str(at.get('snapshot_sha256'))[:16]}…, "
            f"der A-M4-Snapshot pinnt {pins4.get('am1_snapshot')}")
    if am1 is None:
        fehler.append("der A-M1-Snapshot, den A-M4 pinnt, liegt nicht vor")
    else:
        if am1.get("snapshot_sha256") != at.get("snapshot_sha256"):
            fehler.append("aktuartest: der gelesene A-M1-Snapshot ist nicht der gebundene")
        if (am1.get("pflichtbelege") or {}).get("aktuartest") != [at.get("sha256")]:
            fehler.append(
                f"aktuartest.json {str(at.get('sha256'))[:16]}… ist nicht das Testergebnis, "
                f"das der A-M1-Snapshot pinnt ({(am1.get('pflichtbelege') or {}).get('aktuartest')})")
    return fehler


#: Die Felder des Code-Stands, die Probe, Protokollzeile und Zugangsabnahme
#: tragen (Block F, Nachbesserung, Pruefer-Befund 6): Image-Digest und
#: Revision, soweit erfasst, und der Hash des ausfuehrbaren Pakets. Ein
#: Versionsstring allein ist keine Identitaet — zwei Staende mit derselben
#: Kern-Version rechnen verschieden, wenn der Code darum herum ein anderer ist.
CODE_STAND_FELDER = ("image_digest", "image_revision", "quellcode_sha256")


def code_stand_abweichungen(
    referenz: Mapping[str, Any], jetzt: Mapping[str, Any], *, nicht_erfasst: str,
) -> List[str]:
    """Was die Referenz vom Code-Stand belegt, muss ``jetzt`` wieder belegen.

    Ein Feld, das die Referenz nicht erfasst hat, ist nicht vergleichbar
    (kein Befund); eines, das sie erfasst hat, muss gleich sein — auch
    "nicht erfasst" auf der anderen Seite ist dann eine Abweichung: Wer
    das produktive Image nennt, dem genuegt keine Probe ohne Image.
    """
    abweichend: List[str] = []
    for feld in CODE_STAND_FELDER:
        wert = referenz.get(feld)
        if wert in (None, "", nicht_erfasst):
            continue
        if jetzt.get(feld) != wert:
            abweichend.append(f"{feld} {str(jetzt.get(feld))[:24]!r} statt {str(wert)[:24]!r}")
    return abweichend


def code_stand_belegt(referenz: Mapping[str, Any], *, nicht_erfasst: str) -> bool:
    """Ob die Referenz ueberhaupt einen Code-Stand belegt."""
    return any(referenz.get(f) not in (None, "", nicht_erfasst) for f in CODE_STAND_FELDER)
#: Zeitbezug eines Vergleichs.
TERMINE = ("zugangsstichtag", "folgetermin", "zwischen", "fenster")
#: Die Toleranz eines Betragsvergleichs: ein halber Cent. Beide Laeufe
#: sind deterministisch (ADR-020) und rechnen mit demselben Kern; was
#: darueber liegt, ist kein Rundungsrauschen, sondern ein Unterschied —
#: ein Cent muss auffallen (Zaehltest je Groesse).
TOLERANZ = 0.005
#: Wie viele abweichende Vertraege ein Vergleich namentlich nennt.
NENNUNGEN = 20

_SHA256 = re.compile(r"^[0-9a-f]{64}$")


def ist_sha256(wert: Any) -> bool:
    return isinstance(wert, str) and _SHA256.match(wert) is not None


def kanonisch(obj: Any) -> bytes:
    """Kanonisches JSON (sortiert, ohne Leerraum) — die Bytes der Hashes."""
    return json.dumps(obj, ensure_ascii=False, sort_keys=True,
                      separators=(",", ":")).encode("utf-8")


def stand_sha256(inhalt: Mapping[str, Any]) -> str:
    """Der Hash des gefuehrten Stands einer Ablage (Inhalt aus
    ``betrieb.tageslauf.ablage_stand``)."""
    return hashlib.sha256(kanonisch(dict(inhalt))).hexdigest()


def vergleich(
    groesse: str, termin: str, stichtag: Optional[str], soll: Optional[float],
    ist: float, *, umfang: int, abweichend: Sequence[Mapping[str, Any]] = (),
    grund: Optional[str] = None, ausgenommen: Sequence[Mapping[str, Any]] = (),
) -> Dict[str, Any]:
    """Ein Vergleich Soll gegen Ist — das Urteil folgt aus den Zahlen.

    ``soll`` None ist ein benannter Zustand ("nicht belegt"): Die Groesse
    wird berichtet, aber nicht gegen eine Abnahme gehalten; ``grund``
    sagt, warum. ``abweichend`` sind die Vertraege (oder Zeilen), die
    einzeln nicht stimmen — eine Summe kann zwei gegenlaeufige Fehler
    verdecken, die Einzelliste nicht. ``ausgenommen`` sind Vertraege, fuer
    die das Soll nicht gilt, je mit Grund (am Folgetermin: ein gebuchter
    Geschaeftsvorfall im Fenster — der Fuehrungswert gilt ohne ihn); sie
    stehen namentlich im Beleg, nicht still ausserhalb.
    """
    differenz = None if soll is None else float(ist) - float(soll)
    return {
        "groesse": groesse,
        "termin": termin,
        "stichtag": stichtag,
        "soll": soll,
        "ist": ist,
        "differenz": differenz,
        "umfang": int(umfang),
        "abweichend_anzahl": len(abweichend),
        "abweichend": [dict(a) for a in list(abweichend)[:NENNUNGEN]],
        "ausgenommen": [dict(a) for a in ausgenommen],
        "ok": _urteil(soll, differenz, len(abweichend)),
        "grund": grund,
    }


def _urteil(soll: Any, differenz: Any, abweichend: int) -> Optional[bool]:
    if soll is None:
        return None
    return bool(abs(float(differenz)) <= TOLERANZ and abweichend == 0)


def bestanden_aus(vergleiche: Sequence[Mapping[str, Any]], befunde: Sequence[str]) -> bool:
    """Das Urteil der Probe — aus den Vergleichen, nie behauptet.

    Bestanden heisst: kein Befund, kein roter Vergleich, jede Groesse
    mindestens einmal gegen ein Soll gehalten, und die Abschlussgroessen
    am Zugangsstichtag gegen die Abnahme gruen — das Deckungskapital, der
    Rueckkaufswert und die Korrekturschicht eingeschlossen (bis 2026-10-01
    standen sie "nicht vergleichbar" bzw. "nicht belegt" im Beleg).
    """
    if befunde:
        return False
    if any(v.get("ok") is False for v in vergleiche):
        return False
    for g in GROESSEN:
        if not any(v.get("groesse") == g and v.get("ok") is True for v in vergleiche):
            return False
    for g in PFLICHT_AM_STICHTAG:
        if not any(v.get("groesse") == g and v.get("termin") == "zugangsstichtag"
                   and v.get("ok") is True for v in vergleiche):
            return False
    return True


def _iso(wert: Any) -> Optional[_dt.date]:
    try:
        return _dt.date.fromisoformat(str(wert))
    except ValueError:
        return None


def zeichnung_form_fehler(
    zeichnung: Any, ordnung: Optional[Mapping[str, Any]] = None,
) -> Optional[str]:
    """Die FORM der Betriebszeichnung (None = in Ordnung).

    Die Signatur rechnet nur nach, wer den Betriebsschluessel haelt — die
    Registrierung tut es (``betrieb._zeichnung``). Das Gate haelt ihn
    nicht; es prueft Form und Rolle und sagt nicht mehr, als es weiss.
    """
    from rechner_pipeline.models.anker import VERFAHREN
    from rechner_pipeline.models.zeichnung import schluesselklasse, zeichnungsrolle

    felder = {"verfahren", "rolle", "schluesselklasse", "schluessel_sha256", "signatur"}
    if not isinstance(zeichnung, dict) or set(zeichnung) != felder:
        return f"betriebszeichnung fehlt oder ist unvollstaendig ({sorted(felder)})"
    if zeichnung.get("verfahren") != VERFAHREN:
        return f"betriebszeichnung: Verfahren {zeichnung.get('verfahren')!r}, erwartet {VERFAHREN!r}"
    if (zeichnung.get("schluesselklasse") != "betrieb"
            or not str(zeichnung.get("rolle")).startswith("betrieb/")):
        return (f"betriebszeichnung von {zeichnung.get('rolle')!r} (Klasse "
                f"{zeichnung.get('schluesselklasse')!r}) — die Probe zeichnet der Betrieb")
    if not (ist_sha256(zeichnung.get("schluessel_sha256")) and ist_sha256(zeichnung.get("signatur"))):
        return "betriebszeichnung: Fingerabdruck oder Signatur ist keine SHA-256"
    if ordnung is not None:
        rolle = zeichnungsrolle(dict(ordnung), str(zeichnung.get("schluessel_sha256")))
        if rolle != zeichnung.get("rolle") or schluesselklasse(dict(ordnung), str(rolle)) != "betrieb":
            return (f"betriebszeichnung: Rolle {zeichnung.get('rolle')!r} passt nicht zur "
                    f"Zeichnungsordnung (dort: {rolle!r})")
    return None


def signierter_satz(beleg: Mapping[str, Any]) -> Dict[str, Any]:
    """Was die Betriebszeichnung deckt: alle Felder ausser ihr selbst —
    in der Form, die ``models.anker.zeichne`` erwartet (wie eingang.json)."""
    rest = {k: v for k, v in beleg.items() if k != "betriebszeichnung"}
    return {"zugangsprobe": rest, "zeichnung": beleg.get("betriebszeichnung")}


def beleg_fehler(
    beleg: Any, *, ordnung: Optional[Mapping[str, Any]] = None,
) -> List[str]:
    """Der Beleg gegen seinen Vertrag — Form, Bindungen und das Urteil,
    NACHGERECHNET aus den Vergleichen. Leer = in Ordnung."""
    if not isinstance(beleg, dict):
        return ["Zugangsprobe: kein JSON-Objekt"]
    fehler: List[str] = []
    if beleg.get("schema_version") != SCHEMA_VERSION:
        fehler.append(f"schema_version {beleg.get('schema_version')!r}, erwartet {SCHEMA_VERSION}")
    if beleg.get("art") != ART:
        fehler.append(f"art {beleg.get('art')!r}, erwartet {ART!r}")
    fall = beleg.get("fall")
    if not isinstance(fall, str) or not fall.strip():
        fehler.append("fall fehlt")
    stichtag, bis = _iso(beleg.get("stichtag")), _iso(beleg.get("bis"))
    if stichtag is None or bis is None or bis <= stichtag:
        fehler.append("stichtag/bis sind keine ISO-Daten mit bis nach dem Stichtag")
    stand = beleg.get("ablage_stand")
    if not (isinstance(stand, dict) and isinstance(stand.get("inhalt"), dict)
            and stand.get("sha256") == stand_sha256(stand["inhalt"])):
        fehler.append("ablage_stand: sha256 ist nicht der Hash seines Inhalts")
    eingang = beleg.get("eingang")
    if not (isinstance(eingang, dict) and ist_sha256(eingang.get("sha256"))
            and isinstance(eingang.get("inhalt"), dict)):
        fehler.append("eingang: {sha256, inhalt} fehlt")
    elif eingang["inhalt"].get("fall") != fall:
        fehler.append(f"eingang gehoert zum Fall {eingang['inhalt'].get('fall')!r}, nicht {fall!r}")
    elif eingang["inhalt"].get("snapshot_sha256") != beleg.get("am4_snapshot_sha256"):
        fehler.append("eingang nennt einen anderen A-M4-Snapshot als der Beleg")
    if not ist_sha256(beleg.get("am4_snapshot_sha256")):
        fehler.append("am4_snapshot_sha256 ist keine SHA-256")
    abnahmen = beleg.get("abnahmen")
    eingaben = beleg.get("eingaben")
    if not isinstance(abnahmen, dict) or set(abnahmen) != set(SOLL_BELEGE):
        fehler.append(
            f"abnahmen: erwartet die Bindung {sorted(SOLL_BELEGE)} — ein Soll, das an "
            "keine Abnahme gebunden ist, bindet nichts")
    else:
        for rolle, (gate, datei) in SOLL_BELEGE.items():
            b = abnahmen.get(rolle)
            if not (isinstance(b, dict) and b.get("datei") == datei and b.get("gate") == gate
                    and ist_sha256(b.get("sha256")) and ist_sha256(b.get("snapshot_sha256"))):
                fehler.append(f"abnahmen.{rolle}: erwartet {{datei: {datei}, gate: {gate}, "
                              "sha256, snapshot_sha256}")
                continue
            if not isinstance(eingaben, dict) or eingaben.get(datei) != b["sha256"]:
                fehler.append(
                    f"eingaben: {datei} ist nicht mit den gebundenen Bytes gelesen "
                    f"({str((eingaben or {}).get(datei) if isinstance(eingaben, dict) else None)[:16]}… "
                    f"statt {b['sha256'][:16]}…)")
        if (isinstance(abnahmen.get("migrationssuite"), dict)
                and abnahmen["migrationssuite"].get("snapshot_sha256") != beleg.get("am4_snapshot_sha256")):
            fehler.append("abnahmen.migrationssuite ist an einen anderen A-M4-Snapshot gebunden "
                          "als der Beleg")
    if beleg.get("abdeckung") != abdeckung():
        fehler.append("abdeckung: nicht die Abdeckung der Abschlussspalten dieses Vertrags")
    if "nicht_verglichen" in beleg:
        fehler.append(
            "nicht_verglichen: ein Beleg der Fassung 1 — Deckungskapital, Rueckkaufswert und "
            "Korrekturschicht werden seit 2026-10-01 verglichen, keine Groesse steht mehr "
            "'nicht vergleichbar' im Beleg")
    from rechner_pipeline.models.bestand import BEWERTUNGSKONVENTIONEN

    if beleg.get("konvention") not in BEWERTUNGSKONVENTIONEN:
        fehler.append("konvention: der Beleg nennt nicht, in welcher Bewertungskonvention "
                      "Abschluss und Fuehrungswert verglichen wurden")
    if beleg.get("groessen") != list(GROESSEN):
        fehler.append(
            f"groessen {beleg.get('groessen')!r} sind nicht die verglichenen Groessen "
            f"{list(GROESSEN)} — ein Beleg, der andere Groessen nennt, vergleicht anderes")
    vergleiche = beleg.get("vergleiche")
    befunde = beleg.get("befunde")
    if not isinstance(vergleiche, list) or not isinstance(befunde, list):
        fehler.append("vergleiche und befunde muessen Listen sein")
        return fehler
    for i, v in enumerate(vergleiche):
        if not isinstance(v, dict) or v.get("groesse") not in GROESSEN or v.get("termin") not in TERMINE:
            fehler.append(f"vergleiche[{i}]: unbekannte Groesse oder unbekannter Termin")
            continue
        soll, ist = v.get("soll"), v.get("ist")
        if not isinstance(ist, (int, float)) or (soll is not None and not isinstance(soll, (int, float))):
            fehler.append(f"vergleiche[{i}] ({v['groesse']}): soll/ist sind keine Zahlen")
            continue
        differenz = None if soll is None else float(ist) - float(soll)
        if (differenz is None) != (v.get("differenz") is None) or (
                differenz is not None and not math.isclose(
                    differenz, float(v.get("differenz")), rel_tol=0.0, abs_tol=1e-9)):
            fehler.append(f"vergleiche[{i}] ({v['groesse']}): differenz ist nicht ist - soll")
        if v.get("abweichend_anzahl") != len(v.get("abweichend") or []) and not (
                isinstance(v.get("abweichend_anzahl"), int)
                and v["abweichend_anzahl"] > NENNUNGEN):
            fehler.append(f"vergleiche[{i}] ({v['groesse']}): abweichend_anzahl passt nicht zur Liste")
        if (v["groesse"] in PFLICHT_AM_STICHTAG and v["termin"] == "zugangsstichtag"
                and soll is None):
            fehler.append(
                f"vergleiche[{i}] ({v['groesse']}): am Zugangsstichtag ohne Soll — die "
                "Groesse wird gegen die Abnahme gehalten, nicht nur berichtet")
        if v.get("ok") != _urteil(soll, differenz, int(v.get("abweichend_anzahl") or 0)):
            fehler.append(
                f"vergleiche[{i}] ({v['groesse']}): das Urteil ok={v.get('ok')!r} folgt "
                "nicht aus Soll, Ist und Toleranz")
    if beleg.get("bestanden") is not bestanden_aus(vergleiche, befunde):
        fehler.append(
            f"bestanden={beleg.get('bestanden')!r} folgt nicht aus den Vergleichen — "
            "das Urteil wird nachgerechnet, nicht geglaubt")
    form = zeichnung_form_fehler(beleg.get("betriebszeichnung"), ordnung)
    if form:
        fehler.append(form)
    return fehler
