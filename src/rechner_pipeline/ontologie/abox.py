"""A-Box-Ablage und Kreuz-Objekt-Validierung.

Kanonischer Speicher sind versionierte JSON-Dateien (Git bzw. der
Fall-Arbeitsbereich) — ein Graph-Store waere eine jederzeit neu
baubare Projektion, nie die Wahrheit. Serialisierung ist
deterministisch (sortierte Schluessel, festes Format): gleiche A-Box
ergibt byte-gleiche Datei, Laeufe bleiben diff- und hashbar.

Die Kreuz-Objekt-Constraints laufen im Repo-Idiom
``validate() -> List[str]`` AUF den Pydantic-Objekten (P5): Pydantic
traegt Struktur, dieser Code die Fachregeln — inklusive der Bindung
der Quellen im Eingang-Register des Falls (P1 bis zur Wurzel).

Knoten: klv
"""

from __future__ import annotations

import json
import re
from pathlib import Path
from typing import List, Optional

from rechner_pipeline.models.zeichnung import validiere_zeichnung
from rechner_pipeline.ontologie.aussage import Zustand
from rechner_pipeline.ontologie.tbox import ABOX_SCHEMA_VERSION, ABox, PFLICHT_PARAMETER, TBOX_VERSION

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


def lade_aus_bytes(roh: bytes) -> ABox:
    """A-Box aus bereits gelesenen Bytes.

    Damit ein Gate Beleg-Hash und Verarbeitung aus DENSELBEN Bytes bildet
    (Review T23-01) — es liest einmal, hasht die Bytes und parst sie hier,
    statt die Datei fuer das Parsen ein zweites Mal zu lesen.

    Fail-closed bei fehlender Versionsdeklaration (Review T23-02): Der
    Modell-Default gilt fuer die KONSTRUKTION (eine frisch gebaute A-Box
    spricht das aktuelle Vokabular), nie fuer die DESERIALISIERUNG — eine
    Datei ohne ``tbox_version``/``schema_version`` wuerde sonst still als
    aktuell eingestuft, und der Versionsvergleich der Gates liefe ins Leere.
    """
    daten = json.loads(roh)
    if not isinstance(daten, dict):
        raise ValueError("A-Box: kein JSON-Objekt")
    fehlend = [k for k in ("schema_version", "tbox_version") if k not in daten]
    if fehlend:
        raise ValueError(
            f"A-Box ohne Versionsdeklaration ({', '.join(fehlend)}) — sie "
            "spricht kein bekanntes Vokabular; aus den Fragmenten neu "
            "erzeugen (gates.abox_merge), nicht still als aktuell einstufen"
        )
    return ABox.model_validate_json(roh)


def lade(fall: Path) -> ABox:
    return lade_aus_bytes(abox_pfad(fall).read_bytes())


def validate_abox(
    abox: ABox, eingang_register: Optional[dict] = None
) -> List[str]:
    """Kreuz-Objekt-Regeln; leere Liste = in Ordnung.

    ``eingang_register`` ist das geladene ``eingang.json`` des Falls:
    damit wird jede A-Box-Quelle bis zur registrierten, gehashten
    Eingangsdatei gebunden — eine Aussage, deren Quelle nicht im
    Eingang liegt, ist keine belegte Aussage.
    """
    fehler: List[str] = []
    # Die A-Box spricht das Vokabular GENAU EINER T-Box-Version (Review
    # T22-02): Eine A-Box mit fremder Version ist unter dem geltenden
    # Vokabular nicht auslegbar — neu erzeugen (abox_merge) oder die
    # T-Box-Aenderung ueber A-K1 zeichnen.
    if abox.schema_version != ABOX_SCHEMA_VERSION:
        fehler.append(
            f"schema_version: A-Box-Datei traegt {abox.schema_version!r}, "
            f"geltend ist {ABOX_SCHEMA_VERSION!r} — Datei stammt aus einem "
            "anderen Dateischema; aus den Fragmenten neu erzeugen"
        )
    if abox.tbox_version != TBOX_VERSION:
        fehler.append(
            f"tbox_version: A-Box traegt {abox.tbox_version!r}, geltend ist "
            f"{TBOX_VERSION!r} — A-Box aus den Fragmenten neu erzeugen "
            "(gates.abox_merge) oder die T-Box-Aenderung ueber A-K1 zeichnen"
        )
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

    # Fachliche Wertebereiche (P5-Minimum; Systempruefung Befund 19).
    # Grobe Plausibilitaet, kein Tarifwissen: Verletzungen sind fast
    # sicher Extraktions- oder Einheitenfehler (Prozent vs. Promille).
    _BEREICHE = {
        "zins": (0.0, 0.10), "alpha": (0.0, 0.10), "beta1": (0.0, 0.20),
        "gamma1": (0.0, 0.05), "gamma2": (0.0, 0.05), "gamma3": (0.0, 0.05),
        "stoab_satz": (0.0, 0.10),
    }
    for gen in abox.generationen:
        for zelle in gen.zellen:
            werte = {
                feld: a.wert for feld, a in zelle.parameter.items()
                if a.zustand is Zustand.BELEGT
                and isinstance(a.wert, (int, float))
                and not isinstance(a.wert, bool)
            }
            for feld, (lo, hi) in _BEREICHE.items():
                if feld in werte and not (lo <= werte[feld] <= hi):
                    fehler.append(
                        f"{gen.id}/{zelle.id}/{feld}: {werte[feld]!r} "
                        f"ausserhalb des plausiblen Bereichs [{lo}, {hi}] "
                        "— Einheiten pruefen (Prozent/Promille)"
                    )
            if ("stoab_min" in werte and "stoab_max" in werte
                    and werte["stoab_min"] > werte["stoab_max"]):
                fehler.append(
                    f"{gen.id}/{zelle.id}: stoab_min > stoab_max "
                    f"({werte['stoab_min']} > {werte['stoab_max']})"
                )

    for d in abox.diskrepanzen:
        if d.status == "offen" and d.id not in referenzierte:
            fehler.append(
                f"Diskrepanz {d.id} ist offen, aber keine Aussage "
                "referenziert sie (verwaister Konflikt)"
            )
        # Verteidigung in der Tiefe (Review T23-06): dieselbe Regel wie der
        # Modell-Validator, hier fuer den Fall, dass eine A-Box je an
        # Pydantic vorbei entsteht — die Gate-Pruefung P-Q3 laeuft fuer
        # JEDE A-Box, unabhaengig vom Schreibweg.
        if d.entscheidung is not None and d.entscheidung.zeichnung is not None:
            for f in validiere_zeichnung(d.entscheidung.zeichnung, form="beide"):
                fehler.append(f"Diskrepanz {d.id}: {f}")

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
