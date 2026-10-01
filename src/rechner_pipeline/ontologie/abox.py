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
import os
import re
import tempfile
from pathlib import Path
from typing import List, Optional

from rechner_pipeline.models.zeichnung import validiere_zeichnung
from rechner_pipeline.ontologie.aussage import Zustand
from rechner_pipeline.ontologie.tbox import (
    ABOX_SCHEMA_VERSION,
    ABox,
    BLOCK_TITEL,
    GENERATIONS_BLOECKE,
    PFLICHT_PARAMETER,
    TBOX_VERSION,
    TBOX_VERSIONEN,
    bereich_text,
    block_knoten,
    wert_im_bereich,
)

ABOX_DATEI = "abox.json"


class ABoxFehler(ValueError):
    """Die A-Box laesst sich nicht schreiben oder nicht auslegen."""


def abox_pfad(fall: Path) -> Path:
    return fall / "abgeleitet" / "abox" / ABOX_DATEI


def speichere(abox: ABox, fall: Path) -> Path:
    """A-Box deterministisch und ATOMAR in den Fall-Arbeitsbereich schreiben.

    Vollstaendig daneben, dann in einem Zug an den Zielpfad (Review
    T25-11). Vorher schrieb ein einfaches ``write_text`` direkt: Ein
    Absturz waehrend des Schreibens hinterliess eine halbe ``abox.json``
    — die Datei machte sich damit selbst zu der Beschaedigung, gegen die
    ihre Leser sich wappnen. Dasselbe Muster wie ``fall._schreibe_json``;
    dort liegt es ausserhalb dieser Schicht (``ontologie`` darf ``fall``
    nicht importieren), deshalb hier noch einmal statt einer Abstraktion
    ueber eine Schichtgrenze hinweg.

    Ein Symlink als Ziel wird verweigert: Ein Schreibvorgang, der einem
    Symlink folgt, schreibt woanders hin, als er meint.
    """
    pfad = abox_pfad(fall)
    if pfad.is_symlink():
        raise ABoxFehler(f"A-Box-Ziel ist ein Symlink ({pfad}) — Schreiben verweigert")
    pfad.parent.mkdir(parents=True, exist_ok=True)
    daten = abox.model_dump(mode="json", exclude_none=True)
    inhalt = (json.dumps(daten, ensure_ascii=False, indent=2, sort_keys=True)
              + "\n").encode("utf-8")
    fd, temp_name = tempfile.mkstemp(dir=pfad.parent, prefix=f".{pfad.name}.", suffix=".tmp")
    temp_pfad = Path(temp_name)
    try:
        with os.fdopen(fd, "wb") as datei:
            datei.write(inhalt)
            datei.flush()
            os.fsync(datei.fileno())
        os.replace(temp_pfad, pfad)
    except BaseException:
        temp_pfad.unlink(missing_ok=True)
        raise
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
    # T-Box-Aenderung ueber A-O1 zeichnen.
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
            "(gates.abox_merge) oder die T-Box-Aenderung ueber A-O1 zeichnen"
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
        # Generationsweite Bloecke (Tarifwerk, Quellverfahren; T-Box 0.2.0):
        # Widersprueche tragen ihre Diskrepanz wie jedes Zellfeld, und ein
        # belegter Wert liegt im Wertebereich der T-Box — typstreng, denn
        # ``1`` ist kein Schalter und ``"ja"`` kein Verfahren.
        for block, bereiche in GENERATIONS_BLOECKE.items():
            for merkmal, aussage in gen.block(block).items():
                _pruefe_widerspruch(block_knoten(gen.id, block), merkmal, aussage)
                if (aussage.zustand is Zustand.BELEGT
                        and not wert_im_bereich(aussage.wert, bereiche[merkmal])):
                    fehler.append(
                        f"{gen.id}: {BLOCK_TITEL[block]} {block}.{merkmal} = "
                        f"{aussage.wert!r} liegt nicht im Wertebereich "
                        f"{bereich_text(bereiche[merkmal])}"
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


def _hebe_0_1_0_auf_0_2_0(abox: ABox) -> ABox:
    """0.1.0 -> 0.2.0 ist rein ADDITIV: Tarifwerk und Quellverfahren kommen
    als leere Bloecke hinzu (nicht erhoben, die Coverage zeigt es), kein
    vorhandener Begriff aendert Namen, Typ oder Wertebereich. Der Inhalt
    bleibt deshalb byte-gleich; nur die Version wandert.

    Eine Hebung traegt nur, was im alten Artefakt stehen kann (Pruefrunde H,
    H13; ADR-024, Nachtrag "Regel der Hebung"): Eine A-Box, die sich 0.1.0
    nennt und Aussagen in einem Block von 0.2.0 fuehrt, ist keine 0.1.0-A-Box.
    Vorher wurden solche Aussagen still mitgehoben (gemessen: alle acht
    Tarifregeln eines Falls), entgegen der Zusage "leere Bloecke"; ihre
    Provenienz trugen sie zwar, aber aus einem Artefakt, das sie nicht tragen
    kann. Verweigert, mit Ausweg."""
    fremd = sorted(f"{gen.id}/{block}" for gen in abox.generationen
                   for block in GENERATIONS_BLOECKE if gen.block(block))
    if fremd:
        raise ValueError(
            f"A-Box nennt T-Box '0.1.0', fuehrt aber Aussagen in {fremd} aus dem "
            "Vokabular von 0.2.0 — das kann eine 0.1.0-A-Box nicht tragen; eine "
            "Hebung traegt nur, was im alten Artefakt steht. Ausweg: aus den "
            "Fragmenten neu erzeugen (gates.abox_merge) und die Tarifregeln "
            "dort belegen (Skill extrahiere-quellfragment, P-Q3).")
    return abox.model_copy(update={"tbox_version": "0.2.0"})


#: Die Hebungsregeln der Versionslinie: (von, nach) -> Regel. Jeder Schritt
#: von ``TBOX_VERSIONEN`` hat genau eine (Test). Eine Hebung ist der Weg fuer
#: eine A-Box, die ENTSCHEIDUNGEN traegt (aufgeloeste Diskrepanzen, A-Q1):
#: Der Neu-Merge aus den Fragmenten (``gates.abox_merge``) verwirft sie und
#: verweigert deshalb ohne ``--ueberschreiben``. Eine Regel, die einen Begriff
#: umdeutet statt ergaenzt, gehoert nicht hierher — dann ist der Neu-Merge
#: mit neuer A-Q1-Entscheidung der Weg.
HEBUNGEN = {
    ("0.1.0", "0.2.0"): _hebe_0_1_0_auf_0_2_0,
}


def hebe_auf_geltende_version(abox: ABox) -> ABox:
    """Eine A-Box der Vorversion(en) Schritt fuer Schritt auf die geltende
    T-Box heben — nur ueber deklarierte Uebergaenge der Linie.

    Schreibt nichts; der Aufrufer legt die gehobene A-Box ab und faehrt die
    Pruef-Gates auf dem neuen Stand neu (P-Q3, P-K1, ...). Die Zeichnungen
    des Falls, die die alte A-Box pinnen, gelten fuer den neuen Stand nicht
    — Neuzeichnung wie nach jeder Code-Aenderung.
    """
    if abox.tbox_version == TBOX_VERSION:
        raise ValueError(
            f"A-Box spricht bereits die geltende T-Box {TBOX_VERSION!r} — "
            "nichts zu heben")
    linie = tuple(TBOX_VERSIONEN)
    if abox.tbox_version not in linie:
        raise ValueError(
            f"A-Box traegt {abox.tbox_version!r}; die Versionslinie {linie!r} "
            "kennt keinen Uebergang von dort — aus den Fragmenten neu "
            "erzeugen (gates.abox_merge)")
    stand = abox
    for von, nach in zip(linie[linie.index(abox.tbox_version):],
                         linie[linie.index(abox.tbox_version) + 1:]):
        regel = HEBUNGEN.get((von, nach))
        if regel is None:
            raise ValueError(
                f"kein deklarierter Uebergang {von} -> {nach} (HEBUNGEN)")
        stand = regel(stand)
        if stand.tbox_version != nach:
            raise ValueError(
                f"Hebungsregel {von} -> {nach} liefert {stand.tbox_version!r}")
    # Die gehobene A-Box muss sich unter dem geltenden Vokabular auslegen
    # lassen — dieselbe Pydantic-Pruefung wie beim Laden.
    return ABox.model_validate(stand.model_dump(mode="json", exclude_none=True))


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
