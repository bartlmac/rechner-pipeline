"""A-Box-Ablage und Kreuz-Objekt-Validierung.

Kanonischer Speicher sind versionierte JSON-Dateien (Git bzw. der
Fall-Arbeitsbereich) — ein Graph-Store waere eine jederzeit neu
baubare Projektion, nie die Wahrheit. Serialisierung ist
deterministisch (sortierte Schluessel, festes Format): gleiche A-Box
ergibt byte-gleiche Datei, Laeufe bleiben diff- und hashbar.

Die Kreuz-Objekt-Constraints laufen im Repo-Idiom
``validate() -> List[str]`` AUF den Pydantic-Objekten (P5): Pydantic
traegt Struktur, dieser Code die Fachregeln — inklusive der Verankerung
der Quellen im Eingang-Register des Falls (P1 bis zur Wurzel).
"""

from __future__ import annotations

import json
import re
from pathlib import Path
from typing import List, Optional

from rechner_pipeline.ontologie.aussage import Zustand
from rechner_pipeline.ontologie.tbox import ABox, PFLICHT_PARAMETER

ABOX_DATEI = "abox.json"


def abox_pfad(fall: Path) -> Path:
    return fall / "abgeleitet" / "abox" / ABOX_DATEI


def speichere(abox: ABox, fall: Path) -> Path:
    """A-Box deterministisch in den Fall-Arbeitsbereich schreiben."""
    pfad = abox_pfad(fall)
    pfad.parent.mkdir(parents=True, exist_ok=True)
    daten = abox.model_dump(mode="json", exclude_none=True)
    pfad.write_text(
        json.dumps(daten, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    return pfad


def lade(fall: Path) -> ABox:
    pfad = abox_pfad(fall)
    return ABox.model_validate_json(pfad.read_text(encoding="utf-8"))


def validate_abox(
    abox: ABox, eingang_register: Optional[dict] = None
) -> List[str]:
    """Kreuz-Objekt-Regeln; leere Liste = in Ordnung.

    ``eingang_register`` ist das geladene ``eingang.json`` des Falls:
    damit wird jede A-Box-Quelle bis zur registrierten, gehashten
    Eingangsdatei verankert — eine Aussage, deren Quelle nicht im
    Eingang liegt, ist keine belegte Aussage.
    """
    fehler: List[str] = []
    gen_ids = [g.id for g in abox.generationen]
    if len(set(gen_ids)) != len(gen_ids):
        fehler.append("doppelte Generations-IDs")

    bekannte_diskrepanzen = {d.id for d in abox.diskrepanzen}
    referenzierte: set = set()

    def _pruefe_widerspruch(knoten: str, feld: str, aussage) -> None:
        if aussage.zustand is Zustand.WIDERSPRUECHLICH:
            referenzierte.add(aussage.diskrepanz_id)
            if aussage.diskrepanz_id not in bekannte_diskrepanzen:
                fehler.append(
                    f"{knoten}/{feld}: widerspruechlich, aber "
                    f"Diskrepanz {aussage.diskrepanz_id!r} fehlt"
                )

    for gen in abox.generationen:
        for zelle in gen.zellen:
            knoten = f"{gen.id}/{zelle.id}"
            for feld, aussage in zelle.parameter.items():
                _pruefe_widerspruch(knoten, feld, aussage)
        if gen.unisex is not None:
            # Auch die unisex-Aussage traegt Widersprueche wie jedes
            # andere Feld — sie ist kein Sonderweg an der Pruefung vorbei.
            _pruefe_widerspruch(gen.id, "unisex", gen.unisex)
            if gen.unisex.zustand is Zustand.BELEGT:
                wert = str(gen.unisex.wert)
                # ASCII-strikt: isdigit() akzeptiert auch Unicode-Ziffern
                # (z. B. hochgestellte), int() dann nicht — Crash statt Befund.
                if not re.fullmatch(r"U\d{1,3}", wert) or int(wert[1:]) > 100:
                    fehler.append(
                        f"{gen.id}: unisex {wert!r} ist kein 'U<0..100>'"
                    )

    for d in abox.diskrepanzen:
        if d.status == "offen" and d.id not in referenzierte:
            fehler.append(
                f"Diskrepanz {d.id} ist offen, aber keine Aussage "
                "referenziert sie (verwaister Konflikt)"
            )

    if eingang_register is not None:
        registriert = {
            q["datei"]: q["sha256"]
            for q in eingang_register.get("quellen", [])
        }
        for gen in abox.generationen:
            for quelle in gen.quellen:
                if quelle.datei not in registriert:
                    fehler.append(
                        f"{gen.id}: Quelle {quelle.datei!r} ist im "
                        "Eingang-Register nicht registriert (P1 bricht "
                        "an der Wurzel)"
                    )
                elif registriert[quelle.datei] != quelle.sha256:
                    fehler.append(
                        f"{gen.id}: Quelle {quelle.datei!r} traegt "
                        f"sha256={quelle.sha256[:12]}…, registriert ist "
                        f"{registriert[quelle.datei][:12]}…"
                    )
    return fehler


def roundtrip_stabil(abox: ABox) -> bool:
    """Dump -> Load -> Dump muss byte-identisch sein (Determinismus)."""
    einmal = json.dumps(
        abox.model_dump(mode="json", exclude_none=True), sort_keys=True
    )
    wieder = ABox.model_validate_json(einmal)
    zweimal = json.dumps(
        wieder.model_dump(mode="json", exclude_none=True), sort_keys=True
    )
    return einmal == zweimal
