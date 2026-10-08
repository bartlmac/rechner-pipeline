"""``betrieb.anfangsbestand`` — den Anfangsbestand einer Ablage belegen, binden, verlangen.

Entscheid des Maintainers 2026-10-01 (ADR-025, Vertrag in
``models.anfangsbestand``): Der Bestand, den der Betrieb nach dem Aufsetzen
einer Ablage fuehrt, wird von ``mensch/betrieb`` abgenommen (A-B3) — einmal,
ausserhalb jedes Falls, im Linienbereich. Drei Kommandos, in dieser
Reihenfolge, nach dem Aufbaulauf (dem ersten Tageslauf einer neu
aufgesetzten Ablage)::

    python -m rechner_pipeline.betrieb.anfangsbestand belegen --stand <daten> \\
        --linie <linie> --schluessel <betriebsschluessel> --zeichnungsordnung <ordnung>
    python -m rechner_pipeline.gates.gate_entscheid --linie <linie> --gate A-B3 ...
    python -m rechner_pipeline.betrieb.anfangsbestand binden --stand <daten> \\
        --linie <linie> --freigabe-schluessel <schluessel mensch/betrieb> \\
        --schluessel <betriebsschluessel> --zeichnungsordnung <ordnung>

* ``belegen`` liest die Ablage unter ihrer Lauf-Sperre (nie schreibend) und
  legt den Beleg samt lesbarer Sicht in den Linienbereich: Tabellen, Config,
  Code-Stand, einen NEU gefahrenen P-B1-Befund auf genau diesen Bytes,
  Kennzahlen — und bei einem erneuten Aufsetzen die Abweichung zum zuletzt
  abgenommenen Anfangsbestand (aus der Bindung im Archiv der alten Ablage,
  das ``neuaufsetzen.json`` nennt).
* ``binden`` liest den A-B3-Snapshot (geltende Spitze, Signatur,
  Rollenregel — ueber den einen Leser ``uebernahme.lies_abnahme_snapshot``),
  haelt seinen ``stand`` per ``==`` gegen den lebenden Anfangsbestand der
  Ablage, baut den Beleg auf den Bytes der Ablage neu (Wache P-B1 und
  Kennzahlen mit denselben Funktionen wie ``belegen``) und haelt jedes Feld
  gegen den gezeichneten (Pruefrunde H, H08); erst dann schreibt es die
  Bindung ``anfangsbestand.json`` in die Ablage, gezeichnet mit dem
  Betriebsschluessel.
* :func:`anfangsbestand_fehler` — die Pruefung des Tageslaufs: Nach dem
  Aufbaulauf laeuft kein Tag ohne gezeichnete Bindung an eine gruene Zeile
  dieser Ablage.

Knoten: klv, bu
"""

from __future__ import annotations

import argparse
import hashlib
import json
import sys
from pathlib import Path
from typing import Any, Callable, Dict, List, Mapping, Optional

from rechner_pipeline.betrieb import tageslauf as tl
from rechner_pipeline.betrieb._zeichnung import Zeichner, betriebszeichnung_fehler
from rechner_pipeline.models import anfangsbestand as ab
from rechner_pipeline.models.anker import jsonl_zeilen as _jsonl

#: Die Naht der Tests (Muster ``uebernahme._STANDARD_ZUGANGSABNAHME``): Ein
#: Tageslauf, der die Bindung verlangt und keine findet, ruft sie mit
#: ``(ablage, zeichner)`` — im Testlauf legt sie Beleg, A-B3-Snapshot und
#: Bindung ueber die echten Wege an; geprueft wird danach wie jede andere.
#: Produktiv ist sie None.
_STANDARD_ANFANGSBESTAND: Optional[Callable[[tl.Ablage, Zeichner], None]] = None


class AnfangsbestandFehler(ValueError):
    """Der Anfangsbestand ist nicht belegbar, nicht bindbar oder nicht abgenommen."""


def _datei_sha(pfad: Path) -> str:
    return hashlib.sha256(pfad.read_bytes()).hexdigest()


def _gruene_zeilen(ablage: tl.Ablage) -> List[tuple]:
    """``(hash, zeile)`` jeder gruenen Protokollzeile, in Reihenfolge."""
    if not ablage.protokoll_pfad.is_file():
        return []
    ergebnis = []
    for roh in _jsonl(ablage.protokoll_pfad.read_text(encoding="utf-8")):
        try:
            zeile = json.loads(roh)
        except ValueError:
            continue
        if isinstance(zeile, dict) and zeile.get("uebernommen"):
            ergebnis.append((hashlib.sha256(roh.encode("utf-8")).hexdigest(), zeile))
    return ergebnis


def _teile(ablage: tl.Ablage) -> Dict[str, Any]:
    """Was den Stand ausmacht — ohne P-B1 und Kennzahlen (billig, fuer den
    ersten Vergleich in ``binden``; Urteil und Kennzahlen rechnet ``binden``
    danach ueber :func:`baue_beleg` nach, Pruefrunde H, H08)."""
    ablage_stand = tl.ablage_stand(ablage)
    if not ablage_stand.get("letzte_gruene_zeile_sha256"):
        raise AnfangsbestandFehler(
            f"{ablage.wurzel}: die Ablage traegt keine gruene Zeile — abgenommen wird der "
            "Stand NACH dem Aufbaulauf. Ausweg: den Tageslauf fahren (Erstbefuellung), dann "
            "belegen")
    gruene = _gruene_zeilen(ablage)
    letzte = gruene[-1][1]
    stand = ablage.stand.resolve()
    tabellen = {d.relative_to(stand).as_posix(): _datei_sha(d)
                for d in sorted(stand.rglob("*")) if d.is_file()}
    return {
        "ablage_stand": ablage_stand,
        "tabellen": tabellen,
        "config_sha256": ablage_stand.get("config_sha256"),
        "code": {"kern_version": letzte.get("kern_version"),
                 "quellcode_sha256": letzte.get("quellcode_sha256"),
                 "image_digest": letzte.get("image_digest"),
                 "image_revision": letzte.get("image_revision")},
    }


def lebender_stand(ablage: tl.Ablage) -> Dict[str, str]:
    """Der Anfangsbestand, den die Ablage JETZT traegt (``models.anfangsbestand``)."""
    return ab.stand_aus_beleg(_teile(ablage))


def _kennzahlen(tabellen: Mapping[str, Any], tag: str) -> Dict[str, Any]:
    import datetime as dt

    from rechner_pipeline.bestand.fuehrung import bestand_am

    portfolio, historie = tabellen["portfolio"], tabellen["historie"]
    schnitt = bestand_am(portfolio, historie, dt.date.fromisoformat(tag))

    def summe(spalte: str) -> Optional[float]:
        return round(float(schnitt[spalte].sum()), 2) if spalte in schnitt else None

    return {"vertraege": int(len(portfolio)), "in_kraft": int(len(schnitt)),
            "versicherungssumme": summe("sum_insured"), "bu_rente": summe("bu_rente"),
            "jahresbeitrag": summe("jahresbeitrag")}


#: Der Ausweg, wenn die Vorgaenger-Bindung da, aber nicht verwendbar ist.
_VORHER_AUSWEG = (
    "Ausweg: die Bindung des zuletzt abgenommenen Anfangsbestands im Archiv der alten Ablage "
    "wiederherstellen (bzw. den Schluessel bereitstellen, mit dem sie gezeichnet ist), dann "
    "erneut belegen — die Vorlage zeigt die Abweichung dagegen (ADR-025, Abschnitt 1); eine "
    "'erste Abnahme' waere hier eine Behauptung")


def _vorher(ablage: tl.Ablage, zeichner: Zeichner) -> Optional[Dict[str, Any]]:
    """Der zuletzt abgenommene Anfangsbestand — aus der Bindung im Archiv der
    alten Ablage, das ``neuaufsetzen.json`` nennt.

    None heisst genau eines: Es gab keine Ablage davor (keine Provenienz,
    oder sie nennt kein Archiv), oder keine Ablage der Kette davor traegt
    eine Bindung — eine archivierte Ablage ohne Bindung hatte hoechstens
    ihren Aufbaulauf, dann gilt die Bindung IHRER Vorgaengerin. Eine
    Provenienz, ein Archiv oder eine Bindung, die genannt bzw. da, aber nicht
    lesbar oder nicht pruefbar ist, ist ein benannter Fehler mit Ausweg
    (Runde G, G25: vorher fing ein breites ``except`` sie ab, und die Sicht
    behauptete "erste Abnahme dieser Ablage" mit Exit 0). Gelesen wird nur
    eine gezeichnete Bindung; eine ungezeichnete oder fremd gezeichnete waere
    eine Behauptung — und ist deshalb auch keine Abwesenheit."""
    from rechner_pipeline.betrieb.neuaufsetzen import PROVENIENZ_DATEI

    wurzel, gesehen = ablage.wurzel, set()
    while True:
        prov = wurzel / PROVENIENZ_DATEI
        if not prov.exists() and not prov.is_symlink():
            return None
        try:
            angabe = json.loads(prov.read_text(encoding="utf-8"))
        except (OSError, ValueError) as exc:
            raise AnfangsbestandFehler(
                f"{prov}: nicht lesbar ({exc}) — ob es einen zuletzt abgenommenen "
                f"Anfangsbestand gibt, ist nicht bestimmbar. {_VORHER_AUSWEG}") from exc
        archiv = angabe.get("archiv") if isinstance(angabe, dict) else None
        if archiv is None:
            return None
        if not isinstance(archiv, str) or not archiv:
            raise AnfangsbestandFehler(
                f"{prov}: 'archiv' ist kein Pfad ({archiv!r}) — der zuletzt abgenommene "
                f"Anfangsbestand ist nicht auffindbar. {_VORHER_AUSWEG}")
        archiv_pfad = Path(archiv)
        if archiv_pfad.resolve() in gesehen:
            raise AnfangsbestandFehler(
                f"{prov}: die Kette der Archive kehrt zu {archiv_pfad} zurueck — der zuletzt "
                f"abgenommene Anfangsbestand ist nicht bestimmbar. {_VORHER_AUSWEG}")
        gesehen.add(archiv_pfad.resolve())
        if not archiv_pfad.is_dir():
            raise AnfangsbestandFehler(
                f"{prov} nennt das Archiv der alten Ablage {archiv_pfad}, es ist nicht da — "
                f"ob dort ein zuletzt abgenommener Anfangsbestand gebunden war, ist nicht "
                f"bestimmbar. {_VORHER_AUSWEG}")
        datei = archiv_pfad / ab.BINDUNG_DATEI
        if not datei.exists() and not datei.is_symlink():
            wurzel = archiv_pfad
            continue
        try:
            bindung = json.loads(datei.read_text(encoding="utf-8"))
        except (OSError, ValueError) as exc:
            raise AnfangsbestandFehler(
                f"{datei}: die Bindung des zuletzt abgenommenen Anfangsbestands ist nicht "
                f"lesbar ({exc}). {_VORHER_AUSWEG}") from exc
        zf = (betriebszeichnung_fehler(bindung, zeichner.ring, zeichner.ordnung,
                                       was="die alte Bindung")
              if isinstance(bindung, dict) else "kein JSON-Objekt")
        if zf is not None:
            raise AnfangsbestandFehler(
                f"{datei}: die Bindung des zuletzt abgenommenen Anfangsbestands ist nicht "
                f"pruefbar: {zf}. {_VORHER_AUSWEG}")
        return {k: bindung.get(k)
                for k in ("snapshot_sha256", "beleg_sha256", "stand", "kennzahlen")}


def _gesperrt(ablage: tl.Ablage, gehalten: bool):
    """Die Lauf-Sperre — oder nichts, wenn der Aufrufer sie schon haelt (der
    Tageslauf, der die Naht der Tests ruft; flock ist je Dateibeschreibung)."""
    import contextlib

    return contextlib.nullcontext() if gehalten else tl.lauf_sperre(ablage)


def baue_beleg(ablage: tl.Ablage, zeichner: Zeichner, *,
               sperre_gehalten: bool = False) -> Dict[str, Any]:
    """Den Beleg des Anfangsbestands bauen — unter der Lauf-Sperre, lesend."""
    fehler = tl.probenkopie_fehler(ablage)
    if fehler:
        raise AnfangsbestandFehler(f"{fehler} — abgenommen wird der Anfangsbestand der "
                                   "produktiven Ablage, nie eine Probenkopie")
    with _gesperrt(ablage, sperre_gehalten):
        if ablage.publish_marker.exists():
            raise AnfangsbestandFehler(
                f"{ablage.publish_marker}: ein Publish ist unterbrochen — erst den Tageslauf "
                "fahren")
        teile = _teile(ablage)
        tag = str(teile["ablage_stand"]["gefuehrter_tag"])
        import datetime as _dt

        tabellen, geprueft, befunde = tl._wache(
            ablage.stand.resolve(), ablage.config_pfad, _dt.date.fromisoformat(tag))
        kennzahlen = _kennzahlen(tabellen, tag)
        eingaenge = sorted(
            ({"name": d.name, "eingang_sha256": _datei_sha(d / "eingang.json")}
             for d in ablage.uebernahme.iterdir() if (d / "eingang.json").is_file()),
            key=lambda e: e["name"]) if ablage.uebernahme.is_dir() else []
        vorher = _vorher(ablage, zeichner)
    return {
        "schema_version": ab.SCHEMA_VERSION, "art": ab.ART,
        "ablage": {"name": ablage.wurzel.name},
        **teile,
        "pb1": {"urteil": "gruen" if not befunde else "rot",
                "geprueft": {k: int(v) for k, v in sorted(geprueft.items())},
                "befunde": [b["message"] for b in befunde][:20]},
        "eingaenge": eingaenge,
        "kennzahlen": kennzahlen,
        "vorher": vorher,
        "abweichung": ab.abweichung(vorher, kennzahlen),
    }


#: Die Sicht des Pruefers wohnt beim Vertrag (``models.anfangsbestand``):
#: Das Gate erzeugt sie beim Zeichnen von A-B3 neu (``gates.sichten``).
rendere_sicht = ab.rendere_sicht


def _schreibe(ziel: Path, daten: bytes) -> None:
    """Vollstaendig daneben, dann in einem Zug an ``ziel`` — und vorher die
    Schreibreste desselben Ziels raeumen (Pruefrunde H, H17).

    Ein Prozessende zwischen Tempdatei und Einhaengen liess
    ``.<ziel>.<zufall>.tmp`` fuer immer neben Beleg und Sicht liegen; der
    Produzent von A-B3 war der einzige Produzent einer Sicht ohne Raeumen.
    Erkennung und Raeumen sind die des Betriebs
    (``tageslauf.raeume_schreibreste_von``), die Tempdatei das Primitiv des
    Betriebs (``neue_datei``). Aufgerufen wird nur unter der Lauf-Sperre der
    Ablage (``belegen``): Ein zweites ``belegen`` derselben Ablage schreibt
    nicht gleichzeitig."""
    import os

    from rechner_pipeline.bestand.parquet_io import neue_datei

    ziel.parent.mkdir(parents=True, exist_ok=True)
    tl.raeume_schreibreste_von(ziel.parent, ziel.name)
    tmp = neue_datei(ziel.parent, ziel.name)
    try:
        tmp.write_bytes(daten)
        os.replace(tmp, ziel)
    finally:
        tmp.unlink(missing_ok=True)


def _linie_pruefen(linie: Path) -> str:
    from rechner_pipeline.models.standabnahme import bereich_art, LINIE_MARKER

    if bereich_art(linie) != "linie":
        raise AnfangsbestandFehler(
            f"{linie}: kein Linienbereich ({LINIE_MARKER} fehlt) — anlegen mit python -m "
            "rechner_pipeline.gates.stand_belegen linie --linie <linie>")
    return str(json.loads((linie / LINIE_MARKER).read_text(encoding="utf-8")).get("name"))


def belegen(stand: Path, linie: Path, zeichner: Zeichner, *,
            sperre_gehalten: bool = False) -> Dict[str, Any]:
    """Beleg und Sicht in den Linienbereich legen; Rueckgabe: der Beleg."""
    _linie_pruefen(Path(linie))
    ablage = tl.Ablage(Path(stand))
    # Gebaut UND geschrieben unter der Lauf-Sperre (Pruefrunde H, H17): Das
    # Raeumen der Schreibreste vor dem Schreiben trifft dann nie die
    # Tempdatei eines gleichzeitigen ``belegen`` derselben Ablage.
    with _gesperrt(ablage, sperre_gehalten):
        beleg = baue_beleg(ablage, zeichner, sperre_gehalten=True)
        fehler = ab.beleg_fehler(beleg)
        if fehler:
            raise AnfangsbestandFehler(
                "der Anfangsbestand ist nicht abnehmbar: " + "; ".join(fehler[:3]))
        roh = (json.dumps(beleg, ensure_ascii=False, indent=2, sort_keys=True)
               + "\n").encode("utf-8")
        # Die Sicht aus genau den Bytes des Belegs, wie das Gate sie beim
        # Zeichnen neu erzeugt (gates.sichten): Faellt eine der beiden
        # Schreibstellen aus, gehoeren Beleg und Sicht nicht zusammen, und
        # A-B3 wird nicht gezeichnet.
        sicht = ab.rendere_sicht(json.loads(roh)).encode("utf-8")
        _schreibe(Path(linie) / ab.BELEG_RELATIV, roh)
        _schreibe(Path(linie) / ab.SICHT_RELATIV, sicht)
    return beleg


def _ab3_aus_ledger(linie: Path) -> Optional[str]:
    pfad = linie / "abgeleitet" / "diagnostics" / "gate_entscheid_ab3.gate.json"
    try:
        daten = json.loads(pfad.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return None
    summary = daten.get("summary") or {}
    if daten.get("status") != "passed" or summary.get("entscheid") != "angenommen":
        return None
    sha = summary.get("snapshot_sha256")
    return sha if isinstance(sha, str) else None


def _gezeichneter_beleg(pfad: Path, beleg_sha: object, snap_name: str) -> Dict[str, Any]:
    """Der Beleg, den der A-B3-Snapshot pinnt — am festen Ort, mit genau dem
    Hash, oder :class:`AnfangsbestandFehler` (Pruefrunde H, H08).

    Was nicht neben dem Snapshot liegt, kann niemand nachrechnen. Vorher
    band ``binden`` dann mit leeren Kennzahlen."""
    ausweg = ("Ausweg: belegen neu fahren, A-B3 auf dem neuen Beleg zeichnen, dann binden")
    if not (pfad.is_file() and not pfad.is_symlink()):
        raise AnfangsbestandFehler(
            f"{pfad}: der gezeichnete Beleg ({snap_name}) liegt nicht am festen Ort — "
            f"ohne ihn ist nichts nachzurechnen. {ausweg}")
    roh = pfad.read_bytes()
    if hashlib.sha256(roh).hexdigest() != beleg_sha:
        raise AnfangsbestandFehler(
            f"{pfad}: nicht der gezeichnete Beleg (Hash {hashlib.sha256(roh).hexdigest()[:16]}, "
            f"{snap_name} pinnt {str(beleg_sha)[:16]}) — er wurde nach dem Zeichnen ersetzt. "
            f"{ausweg}")
    try:
        beleg = json.loads(roh.decode("utf-8"))
    except ValueError as exc:
        raise AnfangsbestandFehler(f"{pfad}: der gezeichnete Beleg ist nicht lesbar ({exc})") \
            from exc
    fehler = ab.beleg_fehler(beleg)
    if fehler:
        raise AnfangsbestandFehler(
            f"{pfad}: der gezeichnete Beleg verletzt den Vertrag: {'; '.join(fehler[:3])}. "
            f"{ausweg}")
    return beleg


def betriebsschluessel_der_linie(zeichner: Zeichner, ordnungslinie: list) -> str:
    """Der Fingerabdruck, den die SPITZE der Ordnungslinie der Rolle des
    Betriebszeichners gibt — oder :class:`AnfangsbestandFehler`.

    Der Anker des Betriebsschluessels (Entscheid 2026-10-01): Der Nachtlauf
    kennt die Linie nicht und soll sie nicht brauchen; er prueft seine Rolle
    gegen die Ordnungsdatei, die ihm uebergeben wird. Wer diese Datei tauscht,
    tauscht die Rolle. ``binden`` loest deshalb UNTER der Linie einmal auf,
    welcher Schluessel der Betriebsrolle gehoert, und schreibt ihn in die
    gezeichnete Bindung; der Nachtlauf haelt seinen Schluessel gegen diese
    Zahl, nicht gegen die Datei (``anfangsbestand_fehler``).
    """
    from rechner_pipeline.models.ordnungslinie import ordnung_aus

    if not ordnungslinie:
        raise AnfangsbestandFehler(
            "ohne Ordnungslinie ist nicht bestimmbar, welcher Schluessel die Ablage fuehrt "
            "(ADR-025, Nachtrag 2026-10-01) — Ausweg: --linie <linienbereich>")
    spitze = ordnungslinie[-1]
    eintrag = (ordnung_aus(spitze).get("rollen") or {}).get(zeichner.rolle) or {}
    fp = eintrag.get("schluessel_sha256")
    if fp != zeichner.schluessel_sha256:
        raise AnfangsbestandFehler(
            f"die Spitze der Ordnungslinie (Glied {spitze['nummer']}) gibt der Rolle "
            f"{zeichner.rolle!r} den Schluessel {str(fp)[:16]}, gezeichnet wird mit "
            f"{zeichner.schluessel_sha256[:16]} — die Ordnungsdatei des Betriebs ist nicht die "
            "der Linie. Ausweg: die Ordnung der Spitze verwenden oder die Ordnung in die Linie "
            "eintragen (ADR-025)")
    return str(fp)


def binden(
    stand: Path, linie: Path, zeichner: Zeichner, *,
    schluesselring: Mapping[str, bytes], snapshot_sha256: Optional[str] = None,
    ordnungslinie: Optional[list], sperre_gehalten: bool = False,
) -> Dict[str, Any]:
    """Die A-B3-Abnahme an die Ablage binden; Rueckgabe: die Bindung."""
    from rechner_pipeline.betrieb import uebernahme as ueb

    linie = Path(linie)
    name = _linie_pruefen(linie)
    betriebsschluessel = betriebsschluessel_der_linie(zeichner, ordnungslinie or [])
    sha = snapshot_sha256 or _ab3_aus_ledger(linie)
    try:
        snap, snap_name, _ = ueb.lies_abnahme_snapshot(
            linie, "A-B3", sha, schluesselring=schluesselring, ordnung=zeichner.ordnung,
            ordnungslinie=ordnungslinie)
    except ueb.UebernahmeError as exc:
        raise AnfangsbestandFehler(str(exc)) from exc
    ablage = tl.Ablage(Path(stand))
    fehler = tl.probenkopie_fehler(ablage)
    if fehler:
        raise AnfangsbestandFehler(f"{fehler} — gebunden wird nur an die produktive Ablage")
    with _gesperrt(ablage, sperre_gehalten):
        jetzt = lebender_stand(ablage)
        if snap.get("stand") != jetzt:
            abw = sorted(k for k in set(jetzt) | set(snap.get("stand") or {})
                         if jetzt.get(k) != (snap.get("stand") or {}).get(k))
            raise AnfangsbestandFehler(
                f"{snap_name}: der abgenommene Anfangsbestand ist nicht der, den die Ablage "
                f"traegt (abweichend: {abw}) — ein Lauf seit dem Belegen oder eine andere "
                "Ablage. Ausweg: belegen, A-B3 neu zeichnen, binden")
        # Die Rolle hat der Leser nach der Rollenregel geprueft: Sie ist die
        # des Schluessels (ADR-022, Nachtrag 2026-10-01).
        rolle = str(snap.get("rolle"))
        beleg_sha = (snap.get("pflichtbelege") or {}).get("anfangsbestand", [None])[0]
        gezeichnet = _gezeichneter_beleg(linie / ab.BELEG_RELATIV, beleg_sha, snap_name)
        # Pruefrunde H (H08): Das Gate sieht die Ablage nicht und glaubt
        # Urteil und Kennzahlen des Belegs; hier, wo Ablage UND gezeichneter
        # Beleg vorliegen, wird der Beleg auf den Bytes der Ablage NEU gebaut
        # — mit denselben Funktionen wie ``belegen`` (Wache P-B1, Kennzahlen,
        # Vorgaenger), keine zweite Rechnung — und jedes Feld gegen den
        # gezeichneten gehalten (``models.anfangsbestand``:
        # BELEG_BEIM_BINDEN_NACHGERECHNET). Vorher band ``binden`` einen
        # Beleg mit geschoentem Urteil: gezeichnet, gebunden, die Wache auf
        # dem gebundenen Stand rot.
        frisch = baue_beleg(ablage, zeichner, sperre_gehalten=True)
        abweichend = ab.nachrechnung_abweichungen(gezeichnet, frisch)
        if abweichend:
            urteil = (frisch.get("pb1") or {}).get("urteil")
            raise AnfangsbestandFehler(
                f"{snap_name}: der gezeichnete Beleg ist nicht der, den die Ablage JETZT "
                f"ergibt — neu gerechnet weichen ab: {abweichend} (Bestandswache P-B1 auf "
                f"diesen Bytes: {urteil}; Kennzahlen jetzt {frisch.get('kennzahlen')}). "
                "Gebunden wird nur ein Anfangsbestand, dessen Urteil und Kennzahlen beim "
                "Binden nachgerechnet sind. Ausweg: belegen neu fahren (ist die Wache rot, "
                "wird nichts abgenommen: erst den Stand klaeren), A-B3 auf dem neuen Beleg "
                "zeichnen, dann binden")
        kennzahlen = dict(frisch["kennzahlen"])
        satz = ab.bindung_inhalt(linie=name, snapshot=snap, beleg_sha256=str(beleg_sha),
                                 kennzahlen=kennzahlen, freigabe_rolle=rolle,
                                 betriebsschluessel_sha256=betriebsschluessel,
                                 ordnungsglied_sha256=str(ordnungslinie[-1]["glied_sha256"]))
        bindung = {**satz, "zeichnung": zeichner.zeichne(satz)}
        tl._schreibe_json_atomar(tl.schreibziel(ablage, ablage.wurzel / ab.BINDUNG_DATEI), bindung)
    return bindung


def anfangsbestand_fehler(ablage: tl.Ablage, zeichner: Zeichner) -> Optional[str]:
    """Die Pruefung des Tageslaufs (None = in Ordnung).

    Ohne gruene Zeile ist der Lauf der Aufbaulauf — er erzeugt erst, was
    abgenommen wird. Danach verlangt jeder Lauf die gezeichnete Bindung, deren
    abgenommener Stand eine gruene Zeile DIESER Ablage ist (ueber die Kette
    bindet sie alles davor). Eine Ablage ohne Bindung laeuft nicht weiter:
    benannter Zustand, mit Ausweg.
    """
    gruene = _gruene_zeilen(ablage)
    if not gruene:
        return None
    pfad = ablage.wurzel / ab.BINDUNG_DATEI
    if not pfad.is_file() and _STANDARD_ANFANGSBESTAND is not None:
        _STANDARD_ANFANGSBESTAND(ablage, zeichner)
    ausweg = (
        "Ausweg: den gefuehrten Stand als Anfangsbestand abnehmen — python -m "
        "rechner_pipeline.betrieb.anfangsbestand belegen --stand <daten> --linie <linie> ..., "
        "A-B3 zeichnen (python -m rechner_pipeline.gates.gate_entscheid --linie <linie> "
        "--gate A-B3 ...), python -m rechner_pipeline.betrieb.anfangsbestand binden ... "
        "(plv/betrieb/README.md, ADR-025)")
    if not pfad.is_file():
        return (f"{ablage.wurzel}: kein abgenommener Anfangsbestand ({ab.BINDUNG_DATEI} fehlt) "
                "— nach dem Aufbaulauf laeuft kein Tag ohne die Abnahme A-B3 durch den "
                f"Betrieb. {ausweg}")
    try:
        bindung = json.loads(pfad.read_text(encoding="utf-8"))
    except (OSError, ValueError) as exc:
        return f"{pfad}: nicht lesbar ({exc}). {ausweg}"
    if not isinstance(bindung, dict) or set(bindung) != ab.BINDUNG_FELDER \
            or bindung.get("schema_version") != ab.BINDUNG_SCHEMA_VERSION:
        return (f"{pfad}: keine Bindung nach dem Vertrag (Schema "
                f"{ab.BINDUNG_SCHEMA_VERSION}, {sorted(ab.BINDUNG_FELDER)}) — eine Bindung nach "
                "Schema 1 traegt den Schluessel der Ablage nicht, eine nach Schema 2 ist ohne "
                "Nachrechnung von Urteil und Kennzahlen entstanden (Pruefrunde H); beide "
                f"werden neu gebunden. {ausweg}")
    # Der Anker (Entscheid 2026-10-01): Der Schluessel, mit dem dieser Lauf
    # zeichnet, muss der sein, den die Linie beim Binden der Betriebsrolle gab.
    # Eine ausgetauschte Ordnungsdatei tauscht die Rolle, nicht diese Zahl.
    if bindung.get("betriebsschluessel_sha256") != zeichner.schluessel_sha256:
        return (f"{pfad}: der Betriebsschluessel {zeichner.schluessel_sha256[:16]} ist nicht "
                "der gebundene "
                f"({str(bindung.get('betriebsschluessel_sha256'))[:16]}, aufgeloest unter der "
                "Ordnungslinie beim Binden) — die Ordnungsdatei des Laufs gibt die Rolle einem "
                "anderen Schluessel als die Linie. Ausweg: mit dem gebundenen Schluessel "
                "fahren; ein Wechsel des Betriebsschluessels braucht eine neue Bindung unter "
                f"der Linie. {ausweg}")
    zf = betriebszeichnung_fehler(bindung, zeichner.ring, zeichner.ordnung, was="die Bindung")
    if zf is not None:
        return f"{pfad}: {zf}. {ausweg}"
    zeile = (bindung.get("stand") or {}).get("letzte_gruene_zeile_sha256")
    if zeile not in {h for h, _ in gruene}:
        return (f"{pfad}: der abgenommene Anfangsbestand (Zeile {str(zeile)[:16]}) ist keine "
                "gruene Zeile dieser Ablage — die Bindung gehoert zu einer anderen Ablage oder "
                f"einem verworfenen Stand. {ausweg}")
    return None


def main(argv: Optional[List[str]] = None) -> int:
    p = argparse.ArgumentParser(
        prog="python -m rechner_pipeline.betrieb.anfangsbestand",
        description="Den Anfangsbestand einer Ablage belegen und die Abnahme A-B3 binden (ADR-025).")
    unter = p.add_subparsers(dest="aktion", required=True)
    for name in ("belegen", "binden"):
        u = unter.add_parser(name)
        u.add_argument("--stand", required=True, help="Datenverzeichnis der Ablage")
        u.add_argument("--linie", required=True, help="Linienbereich (ADR-025)")
        u.add_argument("--schluessel", required=True, help="Betriebsschluessel")
        u.add_argument("--zeichnungsordnung", required=True)
        if name == "binden":
            u.add_argument("--freigabe-schluessel", action="append", required=True,
                           help="Schluessel von mensch/betrieb (prueft die A-B3-Freigabe)")
            u.add_argument("--abnahme", default=None,
                           help="Snapshot-Hash von A-B3 (Default: das A-B3-Gate-Ledger der Linie)")
    a = p.parse_args(argv)
    ablage = tl.Ablage(Path(a.stand))
    try:
        zeichner = tl.betriebszeichner(ablage, Path(a.schluessel), Path(a.zeichnungsordnung),
                                       wofuer="der Anfangsbestand", ohne="kein Beleg")
        if a.aktion == "belegen":
            beleg = belegen(ablage.wurzel, Path(a.linie), zeichner)
            print(f"anfangsbestand: Beleg -> {Path(a.linie) / ab.BELEG_RELATIV} "
                  f"(Sicht {ab.SICHT_RELATIV}); P-B1 {beleg['pb1']['urteil']}", file=sys.stderr)
            return 0
        from rechner_pipeline.models.freigabe import lade_schluesselring

        ring, fehler, _ = lade_schluesselring(list(a.freigabe_schluessel), ausserhalb=ablage.wurzel)
        if fehler:
            print("anfangsbestand: " + "; ".join(fehler), file=sys.stderr)
            return 2
        # Die Ordnungslinie der Linie ist Pflicht (ADR-025, Nachtrag
        # 2026-10-01): A-B3 wird gegen den Stand der Ordnung gelesen, unter dem
        # es gezeichnet wurde, und der Schluessel der Ablage wird unter ihr
        # aufgeloest. Gelesen mit dem Ring der Freigabeschluessel — der des
        # Vorstands prueft die Glieder nach dem ersten (Pruefrunde G, G09).
        from rechner_pipeline.models.ordnungslinie import lade_linie

        glieder, lf = lade_linie(Path(a.linie), ring=ring)
        if lf or not glieder:
            print("anfangsbestand: Ordnungslinie " + ("; ".join(lf[:3]) or "leer"),
                  file=sys.stderr)
            return 2
        bindung = binden(ablage.wurzel, Path(a.linie), zeichner, schluesselring=ring,
                         snapshot_sha256=a.abnahme, ordnungslinie=glieder)
        print(f"anfangsbestand: {ab.anzeige_bindung(bindung)}", file=sys.stderr)
        return 0
    except (AnfangsbestandFehler, tl.TageslaufError, ValueError, OSError) as exc:
        print(f"anfangsbestand: {exc}", file=sys.stderr)
        return 2


if __name__ == "__main__":  # pragma: no cover
    raise SystemExit(main())
