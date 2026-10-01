"""Die Zugangsabnahme A-B2 fuer Tests — eine Naht, keine Abkuerzung der Pruefung.

Seit ADR-022 (Entscheid des Maintainers 2026-09-30) registriert
``betrieb.uebernahme`` nur mit einer angenommenen Zugangsabnahme A-B2, die
GENAU den Eingang bindet, den die Registrierung schreibt, und den Stand der
Ablage, auf dem sie ihn schreibt. Die meisten Tests der Suite haben einen
anderen Gegenstand und registrieren trotzdem. Fuer sie legt dieser Helfer
— ueber die Naht ``uebernahme._STANDARD_ZUGANGSABNAHME``, die ``conftest``
sessionweit setzt — den Beleg der Probe und einen gezeichneten
A-B2-Snapshot im Fall an, gebunden an die Werte, die die Registrierung ihm
reicht. Danach prueft die Registrierung den Snapshot auf demselben Weg wie
jeden anderen: Schema, Kette, Freigabesignatur, Bindungen, Beleg samt
Betriebszeichnung und nachgerechnetem Urteil.

Der Beleg ist SYNTHETISCH: Seine Vergleiche sind gruen gesetzt, gefahren
wird die Probe hier nicht (zwei Tageslaeufe je Registrierung kosteten die
Suite Minuten). Die echte Probe hat ihre eigenen Tests
(``tests/test_zugangsabnahme_ab2.py``: Positivkontrolle, Zaehltest je
Groesse). Dasselbe Muster wie ``test_betrieb_uebernahme.am4_snapshot``:
Die Pflichtbelege der Abnahmen davor tragen dort Platzhalter, hier buergt
die Signatur.

Tests, deren Gegenstand die Verweigerung ohne A-B2 ist, setzen die Naht per
``monkeypatch`` auf None.

Knoten: system/betrieb
"""

from __future__ import annotations

import hashlib
import json
from pathlib import Path
from typing import Any, Dict, Mapping, Optional

from rechner_pipeline.models import zugangsprobe as zp
from tests.freigabe_testschluessel import BETRIEB_FREIGABEKEY, suitelinie_pin


def abnahmen_aus_fall(fall: Path, am4_snapshot_sha256: str) -> Dict[str, Dict[str, str]]:
    """Die Soll-Bindung eines synthetischen Belegs: genau die Hashes, die
    der A-M4-Snapshot des Falls (``migrationssuite``) und der A-M1-Snapshot,
    den er pinnt (``aktuartest``), als Pflichtbelege tragen (Block F,
    Nachbesserung). Liegt der A-M1-Snapshot nicht im Fall und ist der Pin
    der deterministische aus ``test_betrieb_uebernahme.am1_snapshot``, wird
    er angelegt — sonst prueft die Registrierung ihn und verweigert."""
    from tests.test_betrieb_uebernahme import am1_snapshot

    fall = Path(fall)
    fallname = json.loads((fall / "fall.json").read_text(encoding="utf-8"))["name"]
    am4 = json.loads((fall / "entscheide" / f"A-M4-{am4_snapshot_sha256}.json").read_text(
        encoding="utf-8"))
    pins = am4.get("pflichtbelege") or {}
    am1_sha = (pins.get("am1_snapshot") or [None])[0]
    am1_pfad = fall / "entscheide" / f"A-M1-{am1_sha}.json"
    if not am1_pfad.is_file():
        kandidat = am1_snapshot(fallname)
        if kandidat["snapshot_sha256"] == am1_sha:
            am1_pfad.write_text(json.dumps(kandidat, ensure_ascii=False), encoding="utf-8")
    am1 = json.loads(am1_pfad.read_text(encoding="utf-8")) if am1_pfad.is_file() else {}
    return {
        "aktuartest": {"datei": zp.SOLL_BELEGE["aktuartest"][1], "gate": "A-M1",
                       "sha256": ((am1.get("pflichtbelege") or {}).get("aktuartest") or [None])[0],
                       "snapshot_sha256": am1_sha},
        "migrationssuite": {"datei": zp.SOLL_BELEGE["migrationssuite"][1], "gate": "A-M4",
                            "sha256": (pins.get("migrationssuite") or [None])[0],
                            "snapshot_sha256": am4_snapshot_sha256},
    }


def probenbeleg(
    fallname: str, *, ablage_stand: Mapping[str, Any], eingang_roh: bytes,
    am4_snapshot_sha256: str, zeichner: Any, abnahmen: Mapping[str, Mapping[str, str]],
    stichtag: Optional[str] = None,
) -> Dict[str, Any]:
    """Ein vertragsgerechter, gezeichneter Beleg mit gruenen Vergleichen —
    Kern-Version und Code-Stand die des laufenden Tests, damit der Eintritt
    ihn gegen den Lauf halten kann wie einen echten."""
    import datetime as dt

    from rechner_pipeline.betrieb import tageslauf as tl
    from rechner_pipeline.kern import __version__ as kern_version

    eingang = json.loads(eingang_roh.decode("utf-8"))
    tag = stichtag or str(eingang.get("stichtag"))
    from rechner_pipeline.models.bestand import FUEHRUNGSKONVENTION

    vergleiche = [
        zp.vergleich(g, "zugangsstichtag" if g in zp.PFLICHT_AM_STICHTAG else "fenster",
                     tag, 1.0, 1.0, umfang=1)
        for g in zp.GROESSEN
    ]
    bis = (dt.date.fromisoformat(tag).replace(day=28) + dt.timedelta(days=4)).replace(day=1)
    beleg: Dict[str, Any] = {
        "schema_version": zp.SCHEMA_VERSION, "art": zp.ART, "fall": fallname,
        "stichtag": tag, "bis": bis.isoformat(), "gefuehrt_vorher": ablage_stand.get("gefuehrter_tag"),
        "ablage_stand": {"sha256": zp.stand_sha256(ablage_stand), "inhalt": dict(ablage_stand)},
        "eingang": {"sha256": hashlib.sha256(eingang_roh).hexdigest(), "inhalt": eingang},
        "am4_snapshot_sha256": am4_snapshot_sha256,
        "laeufe": {}, "config_sha256": ablage_stand.get("config_sha256"),
        "kern_version": kern_version, "kern_version_betrieb": None,
        "system": tl.code_stand(None),
        "eingaben": {b["datei"]: b["sha256"] for b in abnahmen.values()},
        "abnahmen": {k: dict(v) for k, v in abnahmen.items()},
        "abdeckung": zp.abdeckung(), "konvention": FUEHRUNGSKONVENTION,
        "folgetermin": {"stichtag": None, "gedeckt": False, "grund": "Testhelfer"},
        "groessen": list(zp.GROESSEN), "vergleiche": vergleiche, "befunde": [],
        "bestanden": zp.bestanden_aus(vergleiche, []),
    }
    beleg["betriebszeichnung"] = zeichner.zeichne({"zugangsprobe": beleg})
    return beleg


def ab2_snapshot(
    fallname: str, *, pflichtbelege: Dict[str, list], vorgaenger: list,
    schluessel: bytes, entscheid: str = "angenommen", rolle: str = "mensch/betrieb",
    pin: Optional[Mapping[str, str]] = None,
) -> Dict[str, Any]:
    """Ein gueltiger A-B2-Snapshot, wie das Gate ihn schreibt — unter dem Glied
    ``pin`` (Default: das erste Glied der Test-Linie)."""
    from rechner_pipeline.models.freigabe import freigabe_fuer
    from rechner_pipeline.models.schemas import P9_GATE_VERSION, P9_SNAPSHOT_SCHEMA_VERSION, p9_snapshot_sha256

    daten: Dict[str, Any] = {
        "schema_version": P9_SNAPSHOT_SCHEMA_VERSION, "command": "gate_entscheid",
        "gate_version": P9_GATE_VERSION, "gate": "A-B2", "entscheid": entscheid,
        "entscheider": "Betriebsverantwortung", "rolle": rolle,
        "begruendung": "Zugangsprobe bestanden", "fall": fallname,
        "artefakt_hashes": {"eingang.json": "ab" * 32, "abgeleitet/abox/abox.json": "cd" * 32},
        "system": {"branch": "main", "commit": "abc1234", "dirty": "nein",
                   "quellcode_sha256": "ef" * 32},
        "vorgaenger": sorted(vorgaenger), "entschieden_am": "2026-01-01T11:00:00+00:00",
        "fall_scope": "bestand", "pflichtbelege": pflichtbelege,
        # unter der Test-Linie gezeichnet (ADR-025: die Linie ist Pflicht)
        "zeichnung": {"rolle": rolle, **(dict(pin) if pin else suitelinie_pin()),
                      "schluesselklasse": "mensch"},
    }
    if entscheid == "angenommen":
        # Der Auftrag, auf dem die Annahme steht (ADR-026); die Signatur buergt.
        daten["fallauftrag"] = hashlib.sha256(b"fallauftrag der Suite").hexdigest()
        daten["freigabe"] = freigabe_fuer(daten, schluessel)
    daten["snapshot_sha256"] = p9_snapshot_sha256(daten)
    return daten


def _pin_der_spitze(zeichner: Any) -> Optional[Dict[str, str]]:
    """Gezeichnet wird unter der Spitze der Linie, die der Betrieb liest."""
    glieder = getattr(zeichner, "ordnungslinie", None)
    if not glieder:
        return None
    return {"ordnung_sha256": glieder[-1]["ordnung_sha256"],
            "ordnungsglied_sha256": glieder[-1]["glied_sha256"]}


def schreibe_zugangsabnahme(
    fall: Path, *, ablage_stand: Mapping[str, Any], eingang_roh: bytes,
    am4_snapshot_sha256: str, zeichner: Any, schluesselring: Mapping[str, bytes],
    rolle: str = "mensch/betrieb",
) -> str:
    """Die Naht: Beleg und A-B2-Snapshot im Fall anlegen, Hash des Snapshots liefern.

    Signiert mit dem Freigabeschluessel von ``mensch/betrieb``
    (``BETRIEB_FREIGABEKEY``); ``rolle`` setzt das Rollenfeld (ein Angriff
    behauptet eine andere Rolle als die des Schluessels).

    Der neue Snapshot pinnt alle vorhandenen A-B2-Snapshots des Falls als
    Vorgaenger — so ist er die geltende Spitze, auch wenn ein Test denselben
    Fall in mehrere Ablagen registriert.
    """
    fall = Path(fall)
    fallname = json.loads((fall / "fall.json").read_text(encoding="utf-8"))["name"]
    beleg = probenbeleg(fallname, ablage_stand=ablage_stand, eingang_roh=eingang_roh,
                        am4_snapshot_sha256=am4_snapshot_sha256, zeichner=zeichner,
                        abnahmen=abnahmen_aus_fall(fall, am4_snapshot_sha256))
    roh = (json.dumps(beleg, ensure_ascii=False, indent=2, sort_keys=True) + "\n").encode("utf-8")
    pfad = fall / zp.BELEG_RELATIV
    pfad.parent.mkdir(parents=True, exist_ok=True)
    pfad.write_bytes(roh)
    entscheide = fall / "entscheide"
    entscheide.mkdir(exist_ok=True)
    vorher = [json.loads(p.read_text(encoding="utf-8"))["snapshot_sha256"]
              for p in sorted(entscheide.glob("A-B2-*.json"))]
    daten = ab2_snapshot(fallname, pflichtbelege={
        "zugangsprobe": [hashlib.sha256(roh).hexdigest()],
        "am4_snapshot": [am4_snapshot_sha256],
        "eingang": [hashlib.sha256(eingang_roh).hexdigest()],
    }, vorgaenger=vorher, schluessel=BETRIEB_FREIGABEKEY, rolle=rolle,
       pin=_pin_der_spitze(zeichner))
    (entscheide / f"A-B2-{daten['snapshot_sha256']}.json").write_text(
        json.dumps(daten, ensure_ascii=False), encoding="utf-8")
    return str(daten["snapshot_sha256"])
