"""Der Vertrag der Abnahme des Anfangsbestands A-B3 — Beleg, Stand, Bindung.

Entscheid des Maintainers 2026-10-01 (ADR-025): Der Anfangsbestand einer
Ablage — der Bestand, den der Betrieb nach dem Aufsetzen fuehrt — ist einer
der vier Gegenstaende der Erstabnahme des Zielsystems, gezeichnet von
``mensch/betrieb``. Bis hierher zeichnete der Betrieb nur jeden ZUGANG
(A-B2) und die Auslieferung (A-B1); was die Ablage nach dem Aufsetzen als
ersten gefuehrten Stand traegt, nahm niemand ab.

**Was abgenommen wird.** Der GEFUEHRTE Stand der Ablage nach ihrem
Aufbaulauf (dem ersten gruenen Tageslauf, der den Bestand vom
Betriebsbeginn bis zum gefuehrten Tag in einem Lauf baut): die Bindung an
die Tabellen des Stands (Hash je Datei), die Config (Hash), den Code-Stand
(Kern-Version, Paket-Hash, Image), den gefuehrten Stand der Ablage
(``tageslauf.ablage_stand``: letzte gruene Protokollzeile, Manifest,
Config), die registrierten Eingaenge und einen NEU gefahrenen Befund der
Bestandswache P-B1 auf genau diesen Bytes; dazu Kennzahlen zur Ansicht und,
bei einem erneuten Aufsetzen, die Abweichung zum zuletzt abgenommenen
Anfangsbestand.

**Wo was liegt.** Der Beleg entsteht im LINIENBEREICH (``betrieb.anfangsbestand
belegen``), dort zeichnet ``mensch/betrieb`` A-B3. Die Bindung liegt IN DER
ABLAGE (:data:`BINDUNG_DATEI`, neben ``configs/`` — wie
``zugangsabnahme.json`` neben dem Eingang), gezeichnet mit dem
Betriebsschluessel: Der Tageslauf kennt die Linie nicht und haelt keinen
Freigabeschluessel; die Bindung schreibt ``betrieb.anfangsbestand binden``,
nachdem es den A-B3-Snapshot (Kette, Signatur, Rollenregel) gelesen und
seinen ``stand`` per ``==`` gegen den lebenden Anfangsbestand der Ablage
gehalten hat.

**Was der Betrieb damit verlangt.** Der Aufbaulauf (erster Lauf einer
Ablage ohne gruene Zeile) laeuft ohne Abnahme — er erzeugt erst, was
abgenommen wird. Jeder weitere Lauf verlangt die gezeichnete Bindung, deren
Stand eine gruene Zeile DIESER Ablage ist (Exit 2 mit Ausweg). Eine
bestehende Ablage ohne Bindung ist ein benannter Zustand: Sie laeuft nicht
weiter, bis der Betrieb ihren gefuehrten Stand als Anfangsbestand
nachtraeglich abnimmt (dieselben drei Kommandos).

Lesen tun das Gate (Form und Urteil des Belegs), der Betrieb (Bindung,
Tageslauf) und die Darstellung — deshalb wohnt der Vertrag in ``models``.

Knoten: system/entscheid
"""

from __future__ import annotations

import hashlib
import json
import re
from typing import Any, Dict, List, Mapping, Optional

#: Fester Ort des Belegs und seiner Sicht im Linienbereich.
BELEG_RELATIV = "abgeleitet/anfangsbestand/beleg.json"
SICHT_RELATIV = "abgeleitet/anfangsbestand/beleg.md"
#: Die Bindung in der Ablage.
BINDUNG_DATEI = "anfangsbestand.json"

SCHEMA_VERSION = 1
ART = "anfangsbestand"
BINDUNG_SCHEMA_VERSION = 1
BINDUNG_ART = "anfangsbestand_abnahme"

BELEG_FELDER = frozenset({
    "schema_version", "art", "ablage", "ablage_stand", "tabellen", "config_sha256",
    "code", "pb1", "eingaenge", "kennzahlen", "vorher", "abweichung",
})
BINDUNG_FELDER = frozenset({
    "schema_version", "art", "linie", "snapshot_sha256", "beleg_sha256", "stand",
    "kennzahlen", "freigabe_rolle", "zeichnung",
})
#: Die Kennzahlen zur Ansicht (Anzahl, Summen) — Zahlen, kein Urteil.
KENNZAHLEN = ("vertraege", "in_kraft", "versicherungssumme", "bu_rente", "jahresbeitrag")
#: Die Felder des abgenommenen Stands (Snapshot-Feld ``stand``).
STAND_FELDER = ("gefuehrter_tag", "letzte_gruene_zeile_sha256", "stand_manifest_sha256",
                "config_sha256", "tabellen_sha256", "kern_version", "quellcode_sha256")

_SHA = re.compile(r"^[0-9a-f]{64}$")


def tabellen_sha256(tabellen: Mapping[str, str]) -> str:
    roh = json.dumps(dict(sorted(tabellen.items())), sort_keys=True,
                     separators=(",", ":")).encode("utf-8")
    return hashlib.sha256(roh).hexdigest()


def stand_aus_beleg(beleg: Mapping[str, Any]) -> Dict[str, str]:
    """Der Stand, den A-B3 abnimmt — aus dem Beleg ABGELEITET. Der Betrieb
    leitet ihn aus einem frisch gebauten Beleg derselben Ablage genauso ab
    und haelt beide per ``==``."""
    ablage_stand = beleg.get("ablage_stand") or {}
    code = beleg.get("code") or {}
    return {
        "gefuehrter_tag": str(ablage_stand.get("gefuehrter_tag")),
        "letzte_gruene_zeile_sha256": str(ablage_stand.get("letzte_gruene_zeile_sha256")),
        "stand_manifest_sha256": str(ablage_stand.get("stand_manifest_sha256")),
        "config_sha256": str(beleg.get("config_sha256")),
        "tabellen_sha256": tabellen_sha256(beleg.get("tabellen") or {}),
        "kern_version": str(code.get("kern_version")),
        "quellcode_sha256": str(code.get("quellcode_sha256")),
    }


def abweichung(vorher: Optional[Mapping[str, Any]],
               kennzahlen: Mapping[str, Any]) -> Optional[Dict[str, Dict[str, Any]]]:
    """Die Abweichung zum zuletzt abgenommenen Anfangsbestand je Kennzahl
    (None = es gibt keinen)."""
    if not vorher:
        return None
    alt = vorher.get("kennzahlen") or {}
    ergebnis: Dict[str, Dict[str, Any]] = {}
    for name in KENNZAHLEN:
        a, n = alt.get(name), kennzahlen.get(name)
        diff = (round(n - a, 2) if isinstance(a, (int, float)) and isinstance(n, (int, float))
                and not isinstance(a, bool) and not isinstance(n, bool) else None)
        ergebnis[name] = {"vorher": a, "jetzt": n, "differenz": diff}
    return ergebnis


def beleg_fehler(beleg: object) -> List[str]:
    """Was am Beleg nicht stimmt (leer = in Ordnung) — ohne die Ablage.

    Das Gate prueft damit Form, Urteil und innere Ableitungen; gegen die
    Ablage haelt den Stand der Betrieb (``betrieb.anfangsbestand binden``).
    """
    if not isinstance(beleg, dict):
        return ["kein JSON-Objekt"]
    fehler: List[str] = []
    if set(beleg) != BELEG_FELDER:
        return [f"der Beleg traegt genau die Felder {sorted(BELEG_FELDER)} — fehlen="
                f"{sorted(BELEG_FELDER - set(beleg))}, fremd={sorted(set(beleg) - BELEG_FELDER)}"]
    if beleg.get("schema_version") != SCHEMA_VERSION or beleg.get("art") != ART:
        fehler.append(f"schema_version {SCHEMA_VERSION} und art {ART!r} erwartet")
    st = beleg.get("ablage_stand")
    if not isinstance(st, dict) or not st.get("letzte_gruene_zeile_sha256"):
        fehler.append("ablage_stand traegt keine gruene Zeile — abgenommen wird der Stand "
                      "NACH dem Aufbaulauf; erst den Tageslauf fahren")
    tabellen = beleg.get("tabellen")
    if not (isinstance(tabellen, dict) and tabellen
            and all(isinstance(k, str) and _SHA.match(str(v)) for k, v in tabellen.items())):
        fehler.append("tabellen muss je Datei des Stands einen SHA-256 tragen")
    if not _SHA.match(str(beleg.get("config_sha256"))):
        fehler.append("config_sha256 fehlt")
    elif isinstance(st, dict) and st.get("config_sha256") != beleg.get("config_sha256"):
        fehler.append("config_sha256 ist nicht die Config des gefuehrten Stands")
    code = beleg.get("code")
    if not (isinstance(code, dict) and code.get("kern_version")
            and _SHA.match(str(code.get("quellcode_sha256")))):
        fehler.append("code muss kern_version und quellcode_sha256 tragen")
    pb1 = beleg.get("pb1")
    if not (isinstance(pb1, dict) and pb1.get("urteil") == "gruen" and pb1.get("befunde") == []):
        fehler.append("die Bestandswache P-B1 ist auf diesem Stand nicht gruen — ein roter "
                      "Anfangsbestand wird nicht abgenommen")
    if not isinstance(beleg.get("eingaenge"), list):
        fehler.append("eingaenge muss eine Liste sein")
    kz = beleg.get("kennzahlen")
    if not (isinstance(kz, dict) and set(kz) == set(KENNZAHLEN)):
        fehler.append(f"kennzahlen traegt genau {list(KENNZAHLEN)}")
    elif beleg.get("abweichung") != abweichung(beleg.get("vorher"), kz):
        fehler.append("abweichung ist nicht aus vorher und kennzahlen abgeleitet")
    return fehler


def bindung_inhalt(*, linie: str, snapshot: Mapping[str, Any], beleg_sha256: str,
                   kennzahlen: Mapping[str, Any], freigabe_rolle: str) -> Dict[str, Any]:
    """Der ungezeichnete Satz der Bindung in der Ablage."""
    return {
        "schema_version": BINDUNG_SCHEMA_VERSION,
        "art": BINDUNG_ART,
        "linie": linie,
        "snapshot_sha256": snapshot["snapshot_sha256"],
        "beleg_sha256": beleg_sha256,
        "stand": dict(snapshot["stand"]),
        "kennzahlen": dict(kennzahlen),
        "freigabe_rolle": freigabe_rolle,
    }


def anzeige_bindung(bindung: Mapping[str, Any]) -> str:
    return (f"Anfangsbestand abgenommen (A-B3-Snapshot "
            f"{str(bindung.get('snapshot_sha256'))[:16]}, Linie {bindung.get('linie')}, "
            f"gefuehrter Tag {(bindung.get('stand') or {}).get('gefuehrter_tag')})")
