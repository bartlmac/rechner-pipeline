"""Migrationsabnahmebericht: deterministisches HTML als G-2-Vorlage.

Die Entscheidungsvorlage der menschlichen Migrationsabnahme, aus drei
deterministischen Bausteinen:

1. Abnahmetests der Migrationssuite (``qa/migrationssuite``):
   Deckungskapital an ZWEI Stichtagen, Bruttojahresbeitrag am
   Migrationsstichtag und GeVo-Beträge dazwischen — als
   Zusammenfassung je Prüfgröße UND als vollständige
   Einzelvergleichs-Tabelle (jeder Vertrag, jeder Wert, jedes
   Residuum); Fehlschläge, Befunde, Befunde der PRÜFMENGE
   (Vollständigkeit, Duplikate) und PRÜFLÜCKEN gesondert.
2. Transformations-Tabelle (``ontologie/transformation``): das
   fachlich abzunehmende Mapping Quellfeld -> Zielfeld samt
   Begründungen und (entschiedenen) Konflikten.
3. Verweise auf die Bestandsberichte VOR und NACH der Migration —
   der visuelle Vergleich ist Teil der Abnahme.

Der Bericht RECHNET nichts und ENTSCHEIDET nichts: gleiche Eingaben
ergeben byte-identisches HTML (keine Zeitstempel), und das Verdikt ist
ausdrücklich eine maschinelle Prüfaussage — die Abnahme selbst ist
Gate G-2 (Mensch, Entscheid-Snapshot).

Als Kommando (``python -m rechner_pipeline.gates.abnahmebericht``) ist
das Modul zugleich ein Toolbox-Gate nach dem Vertrag der übrigen Gates:
EIN JSON auf stdout, ein ``abnahmebericht.gate.json``-Ledger in den
Diagnostics-Ordner, Standard-Exit-Codes. Es NIMMT DIE MIGRATION NICHT
AB — es stellt fest, ob die deterministische Migrationssuite ohne
Fehlschlag geurteilt hat, und legt die Entscheidungsvorlage als
Fall-Artefakt mit Provenienz (Eingabe-Hashes) ab. Die Abnahme bleibt
Gate G-2 beim Menschen (``gates/gate_entscheid``); ein
Exit-Code ``0`` heißt "ohne Fehlschlag und ohne Befund der Prüfmenge",
nicht "abgenommen" — und auch nicht "lückenlos geprüft": PRÜFLÜCKEN
der Suite (nicht gelieferte Erwartungswerte, fehlende erwartete
Vertragszahl) blockieren nicht, stehen aber im Verdikt, im Bericht und
in der Zusammenfassung des Ledgers. Was nicht geprüft wurde, wird
ausgewiesen, nie verschwiegen.

In einem als ``bestand`` deklarierten Fall ist das Kommando zugleich der
deterministische Produzent des unveraenderlichen G-2-Scope-Belegs. Dann sind
Spec, gebundenes Transformationsergebnis, gruener B1-Beleg, vollstaendige
Suite und beide Bestandsberichte Pflicht. Der Scope-Beleg bindet sie und den
HTML-Bericht gemeinsam an Eingangsregister, A-Box, Systemstand und beide
Stichtage. Ein ``tarif``-Fall verlangt diese Bestandsartefakte nicht.

Die Suite-Urteile kommen als JSON herein — genau das, was
:func:`rechner_pipeline.qa.migrationssuite.pruefe_bestand` zurückgibt
(``json.dump``-fähige Primitive). Der Zusammenbau der Prüfaufträge
(Modellpunkte aus der Spez, Erwartungswerte aus der Lieferung) bleibt
Sache des Falls; das Kommando rendert, protokolliert und urteilt.

Run via::

    python -m rechner_pipeline.gates.abnahmebericht \\
        --fall faelle/<fall> --suite <suite_ergebnis.json> \\
        --titel "Migrationsabnahme <Fall>" \\
        --stichtag-1 2026-01-01 --stichtag-2 2027-01-01 \\
        --spec <transformationsspec.json> \\
        --transformation-ergebnis <ergebnis.json> \\
        --bestandsbericht-vor vor/index.html \\
        --bestandsbericht-nach nach/index.html \\
        [--bericht <ziel.html>] [--diagnostics-dir <dir>]

Knoten: klv
"""

from __future__ import annotations

import argparse
import html
import json
import sys
from hashlib import sha256
from pathlib import Path
from typing import Any, Dict, List, Optional

from rechner_pipeline import fall as fall_mod
from rechner_pipeline.gates import bestand_validate
from rechner_pipeline.gates._common import (
    Exit,
    add_request_json_arg,
    build_result,
    hash_files,
    log,
    merge_request_into_args,
    read_request_json,
    run_command,
    utc_now,
    write_gate_ledger,
)
from rechner_pipeline.gates._fall_scope import (
    SCOPE_BELEG_GATE_VERSION,
    artefakt_eintrag,
    bestands_belegrollen,
    scope_bindung,
    schreibe_scope_beleg,
)
from rechner_pipeline.models.schemas import GateLedgerEntry
from rechner_pipeline.ontologie.transformation import (
    TransformationsSpec,
    validate_spec,
)

COMMAND = "abnahmebericht"
#: Kein Gate "G2": die Abnahme ist der MENSCHLICHE Gate G-2. Dieses
#: Kommando erzeugt und protokolliert dessen Vorlage — der Gate-Name
#: sagt das, damit ein Ledger-Leser die beiden nie verwechselt.
GATE = "G2-vorlage.migrationsabnahme"
GATE_VERSION = SCOPE_BELEG_GATE_VERSION

_STIL = """
body { font-family: sans-serif; margin: 2em; color: #222; }
h1 { border-bottom: 2px solid #444; padding-bottom: 0.2em; }
table { border-collapse: collapse; margin: 1em 0; }
th, td { border: 1px solid #999; padding: 0.3em 0.7em; text-align: left; }
th { background: #eee; }
.gruen { color: #060; font-weight: bold; }
.rot { color: #a00; font-weight: bold; }
.hinweis { background: #ffd; border: 1px solid #cc9; padding: 0.6em; }
td.zahl { text-align: right; }
"""


def _e(text: Any) -> str:
    return html.escape(str(text))


def _gruppe(groesse: str) -> str:
    """Prüfgrößen-Gruppe einer Einzelprüfung (gevo_sto_monat_137 -> gevo_sto)."""
    if groesse.startswith("gevo_"):
        return "_".join(groesse.split("_")[:2])
    return groesse


def _pruefgroessen_zeilen(suite: Dict[str, Any]) -> List[str]:
    gruppen: Dict[str, Dict[str, float]] = {}
    for urteil in suite["vertraege"]:
        for p in urteil["pruefungen"]:
            g = gruppen.setdefault(
                _gruppe(p["groesse"]), {"anzahl": 0, "ok": 0, "max_res": 0.0})
            g["anzahl"] += 1
            g["ok"] += 1 if p["ok"] else 0
            g["max_res"] = max(g["max_res"], abs(p["residuum"]))
    zeilen = []
    for name in sorted(gruppen):
        g = gruppen[name]
        zeilen.append(
            f"<tr><td>{_e(name)}</td><td class='zahl'>{g['anzahl']:.0f}</td>"
            f"<td class='zahl'>{g['ok']:.0f}</td>"
            f"<td class='zahl'>{g['max_res']:.4f}</td></tr>"
        )
    return zeilen


def _mapping_zeilen(spec: TransformationsSpec) -> List[str]:
    zeilen = []
    for f in spec.felder:
        if f.typ == "kodierung":
            detail = "; ".join(f"{k} -> {v}" for k, v in f.kodierung.items())
        elif f.typ == "berechnung":
            detail = f.berechnung
        else:
            detail = "—"
        ziel = f.ziel if f.typ != "nicht_uebernommen" else "(nicht übernommen)"
        zeilen.append(
            f"<tr><td>{_e(', '.join(f.quellen))}</td><td>{_e(ziel)}</td>"
            f"<td>{_e(f.typ)}</td><td>{_e(detail)}</td>"
            f"<td>{_e(f.begruendung)}</td></tr>"
        )
    return zeilen


def baue_bericht(
    *,
    titel: str,
    stichtag_1: str,
    stichtag_2: str,
    suite: Dict[str, Any],
    spec: Optional[TransformationsSpec] = None,
    transformation_ergebnis: Optional[Dict[str, Any]] = None,
    bestandsbericht_vor: Optional[str] = None,
    bestandsbericht_nach: Optional[str] = None,
) -> str:
    """Den Abnahmebericht als HTML-Dokument bauen (deterministisch)."""
    teile: List[str] = [
        "<!DOCTYPE html>", "<html lang='de'><head><meta charset='utf-8'>",
        f"<title>{_e(titel)}</title><style>{_STIL}</style></head><body>",
        f"<h1>{_e(titel)}</h1>",
        f"<p>Migrationsstichtag: <b>{_e(stichtag_1)}</b> — "
        f"Folgestichtag: <b>{_e(stichtag_2)}</b></p>",
    ]
    mengenbefunde = list(suite["mengenbefunde"])
    pruefluecken = list(suite["pruefluecken"])
    if suite["suite_bestanden"]:
        # Der Zusatz bringt seinen eigenen Schlusspunkt mit ("s. u."),
        # sonst stünde im projizierten Kopfsatz ein doppelter Punkt.
        zusatz = ("." if not pruefluecken
                  else f" — MIT {len(pruefluecken)} PRÜFLÜCKE(N), s. u.")
        teile.append(
            f"<p class='gruen'>ALLE ABNAHMETESTS BESTANDEN "
            f"({suite['bestanden']:.0f} von {suite['anzahl']:.0f} "
            f"Verträgen){zusatz}</p>")
    else:
        teile.append(
            f"<p class='rot'>{suite['fehlgeschlagen']:.0f} von "
            f"{suite['anzahl']:.0f} Verträgen FEHLGESCHLAGEN"
            + (f", {len(mengenbefunde)} Befund(e) der Prüfmenge"
               if mengenbefunde else "") + ".</p>")
    teile.append(
        "<p class='hinweis'>Maschinelle Prüfaussage der deterministischen "
        "Migrationssuite. Die ABNAHME ist eine menschliche Entscheidung "
        "(Gate G-2) auf Grundlage dieses Berichts.</p>")

    # Die Klammer um die Menge: geprüft ist nur, was auch drin war.
    teile.append("<h2>Prüfmenge (Vollständigkeit und Duplikate)</h2>")
    erwartet = suite["erwartete_anzahl"]
    teile.append(
        f"<p>Geprüfte Verträge: <b>{suite['anzahl']:.0f}</b> — erwartete "
        "Vertragszahl der Lieferung: <b>"
        + (f"{int(erwartet):d}" if erwartet is not None
           else "nicht angegeben") + "</b></p>")
    if mengenbefunde:
        teile.append("<table><tr><th>Befund der Prüfmenge</th></tr>")
        teile.extend(f"<tr><td class='rot'>{_e(b)}</td></tr>"
                     for b in mengenbefunde)
        teile.append("</table>")
    else:
        teile.append("<p>Keine Befunde der Prüfmenge.</p>")

    teile.append("<h2>Prüflücken (was NICHT geprüft wurde)</h2>")
    if pruefluecken:
        teile.append(
            "<p class='hinweis'>Zu diesen Größen lag kein Erwartungswert "
            "vor. Sie sind WEDER bestanden NOCH fehlgeschlagen — sie sind "
            "ungeprüft und beim Lesen des Verdikts abzuziehen.</p><ul>")
        teile.extend(f"<li>{_e(l)}</li>" for l in pruefluecken)
        teile.append("</ul>")
    else:
        teile.append("<p>Keine — jede Prüfgröße war geliefert.</p>")

    teile.append("<h2>Abnahmetests je Prüfgröße</h2>")
    teile.append("<table><tr><th>Prüfgröße</th><th>Anzahl</th><th>OK</th>"
                 "<th>max. |Residuum|</th></tr>")
    teile.extend(_pruefgroessen_zeilen(suite))
    teile.append("</table>")

    teile.append("<h2>Einzelvergleiche (alle Werte)</h2>")
    teile.append(
        "<p>Je Vertrag und Prüfgröße: der vom Zielsystem gerechnete Wert "
        "gegen den gelieferten Erwartungswert.</p>")
    teile.append("<table><tr><th>Police</th><th>Prüfgröße</th>"
                 "<th>Zielsystem</th><th>Lieferung</th><th>Residuum</th>"
                 "<th>Urteil</th></tr>")
    for urteil in suite["vertraege"]:
        for p in urteil["pruefungen"]:
            marke = ("<td class='gruen'>OK</td>" if p["ok"]
                     else "<td class='rot'>FEHLER</td>")
            teile.append(
                f"<tr><td>{_e(urteil['police_id'])}</td>"
                f"<td>{_e(p['groesse'])}</td>"
                f"<td class='zahl'>{p['system']:.2f}</td>"
                f"<td class='zahl'>{p['erwartet']:.2f}</td>"
                f"<td class='zahl'>{p['residuum']:.4f}</td>{marke}</tr>")
    teile.append("</table>")

    teile.append("<h2>Fehlschläge und Befunde</h2>")
    problem_zeilen = []
    for urteil in suite["vertraege"]:
        for p in urteil["pruefungen"]:
            if not p["ok"]:
                problem_zeilen.append(
                    f"<tr><td>{_e(urteil['police_id'])}</td>"
                    f"<td>{_e(p['groesse'])}</td>"
                    f"<td class='zahl'>{p['system']:.2f}</td>"
                    f"<td class='zahl'>{p['erwartet']:.2f}</td>"
                    f"<td class='zahl'>{p['residuum']:.2f}</td></tr>")
        for befund in urteil["befunde"]:
            problem_zeilen.append(
                f"<tr><td>{_e(urteil['police_id'])}</td>"
                f"<td colspan='4'>Befund: {_e(befund)}</td></tr>")
    if problem_zeilen:
        teile.append("<table><tr><th>Police</th><th>Prüfgröße</th>"
                     "<th>Zielsystem</th><th>Lieferung</th>"
                     "<th>Residuum</th></tr>")
        teile.extend(problem_zeilen)
        teile.append("</table>")
    else:
        teile.append("<p>Keine.</p>")

    if spec is not None:
        teile.append("<h2>Transformation (fachliche Abnahme des Mappings)"
                     "</h2>")
        teile.append(
            f"<p>Quelle: {_e(spec.quelle_datei)} "
            f"(SHA-256 {_e(spec.quelle_sha256[:16])}…), "
            f"Akteur: {_e(spec.akteur)}</p>")
        teile.append("<table><tr><th>Quellspalten</th><th>Zielfeld</th>"
                     "<th>Art</th><th>Details</th><th>Begründung</th></tr>")
        teile.extend(_mapping_zeilen(spec))
        teile.append("</table>")
        if spec.offene_konflikte:
            teile.append("<h3>Konflikte und Entscheidungen</h3><ul>")
            for k in spec.offene_konflikte:
                status = (
                    f"entschieden ({_e(k.entscheider)}): {_e(k.entscheidung)}"
                    if k.entscheidung is not None else
                    "<span class='rot'>OFFEN — blockiert die Anwendung</span>")
                teile.append(
                    f"<li><b>{_e(k.quellspalte)}</b>: {_e(k.frage)} — "
                    f"{status}</li>")
            teile.append("</ul>")

    if transformation_ergebnis is not None:
        te = transformation_ergebnis
        teile.append("<h3>Transformationsergebnis (Anwendung des Mappings)"
                     "</h3>")
        befunde = list(te.get("befunde", []))
        klasse = "gruen" if not befunde else "rot"
        teile.append(
            f"<p>Quellzeilen: <b>{int(te['zeilen_quelle']):d}</b> — "
            f"transformiert: <b>{int(te['zeilen_ziel']):d}</b> — "
            f"Zeilen mit Befund (nicht ausgegeben): "
            f"<span class='{klasse}'>{len(befunde):d}</span></p>")
        if befunde:
            teile.append("<ul>")
            teile.extend(f"<li>{_e(b)}</li>" for b in befunde)
            teile.append("</ul>")

    if bestandsbericht_vor or bestandsbericht_nach:
        teile.append("<h2>Bestandsberichte (visueller Vergleich)</h2><ul>")
        if bestandsbericht_vor:
            teile.append(f"<li>VOR der Migration: <a href="
                         f"'{_e(bestandsbericht_vor)}'>"
                         f"{_e(bestandsbericht_vor)}</a></li>")
        if bestandsbericht_nach:
            teile.append(f"<li>NACH der Migration: <a href="
                         f"'{_e(bestandsbericht_nach)}'>"
                         f"{_e(bestandsbericht_nach)}</a></li>")
        teile.append("</ul>")

    teile.append("</body></html>")
    return "\n".join(teile) + "\n"


def schreibe_bericht(pfad: Path, **kwargs: Any) -> Path:
    """Bericht bauen und schreiben; gibt den Pfad zurück."""
    pfad = Path(pfad)
    pfad.parent.mkdir(parents=True, exist_ok=True)
    pfad.write_text(baue_bericht(**kwargs), encoding="utf-8")
    return pfad


# --------------------------------------------------------------------------- #
# Kommando (Toolbox-Gate-Vertrag) — die Bibliotheks-API oben bleibt unberührt.
# --------------------------------------------------------------------------- #

#: Pflichtfelder eines Einzelvergleichs im Suite-Ergebnis.
_PRUEFUNG_FELDER = ("groesse", "system", "erwartet", "residuum", "ok")


def _suite_fehler(daten: Any) -> List[str]:
    """Struktur- und Konsistenzfehler eines Suite-Ergebnis-JSON.

    Geprüft wird nicht nur das Vorhandensein der Felder, sondern auch,
    dass die Zusammenfassung zu den Einzelurteilen PASST: ein von Hand
    nachgebessertes ``suite_bestanden`` würde sonst eine Urkunde über
    ein Urteil erzeugen, das die Suite nie gefällt hat. Leere Liste =
    verwendbar.
    """
    if not isinstance(daten, dict):
        return ["Suite-Ergebnis ist kein JSON-Objekt"]
    fehler: List[str] = []
    for feld in ("anzahl", "bestanden", "fehlgeschlagen", "suite_bestanden",
                 "erwartete_anzahl", "mengenbefunde", "pruefluecken",
                 "vollstaendig_geprueft", "vertraege"):
        if feld not in daten:
            fehler.append(f"Feld {feld!r} fehlt")
    if fehler:
        return fehler
    for feld in ("mengenbefunde", "pruefluecken"):
        if not isinstance(daten[feld], list):
            fehler.append(f"Feld {feld!r} ist keine Liste")
    # Die erwartete Vertragszahl wird im Bericht als ganze Zahl gesetzt
    # (``int(...)``) und im Ledger gefuehrt: ein falscher Typ waere dort
    # ein Absturz oder eine stille Abschneidung (4.7 -> 4) statt eines
    # benannten Contract-Bruchs.
    erwartet = daten["erwartete_anzahl"]
    if erwartet is not None and (isinstance(erwartet, bool)
                                 or not isinstance(erwartet, int)):
        fehler.append(
            "Feld 'erwartete_anzahl' ist weder eine ganze Zahl noch null")
    if fehler:
        return fehler
    vertraege = daten["vertraege"]
    if not isinstance(vertraege, list):
        return ["Feld 'vertraege' ist keine Liste"]
    if not vertraege:
        return [
            "Suite-Ergebnis ohne einen einzigen Vertrag: eine leere "
            "Prüfmenge ist keine bestandene Abnahme — prüfe Lieferung "
            "und Transformation (wurden 0 Verträge übernommen?)"
        ]
    for i, u in enumerate(vertraege):
        wo = f"vertraege[{i}]"
        if not isinstance(u, dict):
            fehler.append(f"{wo} ist kein Objekt")
            continue
        for feld in ("police_id", "bestanden", "befunde", "pruefungen",
                     "nicht_geprueft"):
            if feld not in u:
                fehler.append(f"{wo}: Feld {feld!r} fehlt")
        for feld in ("befunde", "nicht_geprueft"):
            if feld in u and not isinstance(u[feld], list):
                fehler.append(f"{wo}: {feld!r} ist keine Liste")
        pruefungen = u.get("pruefungen")
        if not isinstance(pruefungen, list):
            fehler.append(f"{wo}: 'pruefungen' ist keine Liste")
            continue
        for j, p in enumerate(pruefungen):
            if not isinstance(p, dict):
                fehler.append(f"{wo}.pruefungen[{j}] ist kein Objekt")
                continue
            for feld in _PRUEFUNG_FELDER:
                if feld not in p:
                    fehler.append(
                        f"{wo}.pruefungen[{j}]: Feld {feld!r} fehlt")
            for feld in ("system", "erwartet", "residuum"):
                wert = p.get(feld)
                if feld in p and (isinstance(wert, bool)
                                  or not isinstance(wert, (int, float))):
                    fehler.append(
                        f"{wo}.pruefungen[{j}]: {feld!r} ist keine Zahl")
    if fehler:
        return fehler

    n = len(vertraege)
    n_ok = sum(1 for u in vertraege if u["bestanden"])
    if daten["anzahl"] != n:
        fehler.append(
            f"'anzahl' ({daten['anzahl']}) passt nicht zu {n} Urteilen")
    if daten["bestanden"] != n_ok:
        fehler.append(
            f"'bestanden' ({daten['bestanden']}) passt nicht zu {n_ok} "
            "bestandenen Urteilen")
    if daten["fehlgeschlagen"] != n - n_ok:
        fehler.append(
            f"'fehlgeschlagen' ({daten['fehlgeschlagen']}) passt nicht zu "
            f"{n - n_ok} fehlgeschlagenen Urteilen")
    ohne_mengenbefund = not daten["mengenbefunde"]
    if bool(daten["suite_bestanden"]) != (n_ok == n and ohne_mengenbefund):
        fehler.append(
            f"'suite_bestanden' ({daten['suite_bestanden']}) passt nicht zu "
            f"{n_ok} von {n} bestandenen Urteilen und "
            f"{len(daten['mengenbefunde'])} Befund(en) der Prüfmenge")
    if bool(daten["vollstaendig_geprueft"]) != (not daten["pruefluecken"]):
        fehler.append(
            f"'vollstaendig_geprueft' ({daten['vollstaendig_geprueft']}) "
            f"passt nicht zu {len(daten['pruefluecken'])} Prüflücke(n)")
    return fehler


def _bestands_suite_fehler(
    suite: Dict[str, Any],
    *,
    stichtag_1: str,
    stichtag_2: str,
    bestand_sha256: str,
) -> List[str]:
    """Zusaetzliche Bindung der Suite im deklarativen Bestands-Scope."""
    fehler: List[str] = []
    erwartet = {
        "stichtag_1": stichtag_1,
        "stichtag_2": stichtag_2,
        "bestand_sha256": bestand_sha256,
    }
    for feld, wert in erwartet.items():
        if suite.get(feld) != wert:
            fehler.append(f"{feld!r} muss {wert!r} binden")
    if type(suite.get("vollstaendig_geprueft")) is not bool:
        fehler.append("'vollstaendig_geprueft' muss ein boolescher Wert sein")
    elif not suite["vollstaendig_geprueft"]:
        fehler.append(
            "Bestands-Scope verlangt eine vollstaendig gepruefte "
            "Migrationssuite ohne Pruefluecken"
        )
    return fehler


def _transformation_fehler(
    *,
    fall: Path,
    spec_pfad: Path,
    spec: TransformationsSpec,
    ergebnis: Any,
) -> tuple[List[str], Optional[Path], Optional[str]]:
    """Spec und Anwendung als geschlossene, B1-pruefbare Kette validieren."""
    fehler: List[str] = []
    felder = {
        "schema_version", "spec_sha256", "quelle_sha256", "quellspalten",
        "ziel_datei", "ziel_sha256", "zeilen_quelle", "zeilen_ziel", "befunde",
    }
    if not isinstance(ergebnis, dict) or set(ergebnis) != felder:
        return ([f"Transformationsergebnis muss exakt {sorted(felder)} enthalten"],
                None, None)
    if type(ergebnis.get("schema_version")) is not int or ergebnis[
        "schema_version"
    ] != 1:
        fehler.append("Transformationsergebnis.schema_version muss 1 sein")
    spec_hash = sha256(spec_pfad.read_bytes()).hexdigest()
    if ergebnis.get("spec_sha256") != spec_hash:
        fehler.append("Transformationsergebnis bindet nicht den aktuellen Spec-SHA-256")
    if ergebnis.get("quelle_sha256") != spec.quelle_sha256:
        fehler.append("Transformationsergebnis und Spec binden verschiedene Quellen")

    quellspalten = ergebnis.get("quellspalten")
    if (
        not isinstance(quellspalten, list) or not quellspalten
        or any(not isinstance(wert, str) or not wert for wert in quellspalten)
        or len(quellspalten) != len(set(quellspalten))
    ):
        fehler.append(
            "Transformationsergebnis.quellspalten muss eine nichtleere, "
            "duplikatfreie Stringliste sein"
        )
    else:
        fehler.extend(validate_spec(spec, quellspalten))

    for feld in ("zeilen_quelle", "zeilen_ziel"):
        wert = ergebnis.get(feld)
        if type(wert) is not int or wert < 0:
            fehler.append(f"Transformationsergebnis.{feld} muss eine Zahl >= 0 sein")
    befunde = ergebnis.get("befunde")
    if not isinstance(befunde, list) or any(
        not isinstance(wert, str) for wert in befunde
    ):
        fehler.append("Transformationsergebnis.befunde muss eine Stringliste sein")

    ziel_roh = ergebnis.get("ziel_datei")
    ziel: Optional[Path] = None
    if (
        not isinstance(ziel_roh, str) or not ziel_roh
        or Path(ziel_roh).is_absolute() or ".." in Path(ziel_roh).parts
    ):
        fehler.append("Transformationsergebnis.ziel_datei ist kein sicherer Fallpfad")
    else:
        ziel = (fall / ziel_roh).resolve()
        try:
            ziel.relative_to(fall.resolve())
        except ValueError:
            fehler.append("Transformationsergebnis.ziel_datei verlaesst den Fall")
            ziel = None
        if ziel is not None and not ziel.is_file():
            fehler.append(f"transformiertes Zielartefakt fehlt: {ziel_roh}")
            ziel = None

    ziel_hash: Optional[str] = None
    if ziel is not None:
        ziel_hash = sha256(ziel.read_bytes()).hexdigest()
        if ergebnis.get("ziel_sha256") != ziel_hash:
            fehler.append(
                "Transformationsergebnis.ziel_sha256 weicht vom Zielartefakt ab"
            )
    elif not isinstance(ergebnis.get("ziel_sha256"), str):
        fehler.append("Transformationsergebnis.ziel_sha256 fehlt")

    try:
        register = json.loads((fall / "eingang.json").read_text(encoding="utf-8"))
        registriert = {
            eintrag["datei"]: eintrag["sha256"] for eintrag in register["quellen"]
            if isinstance(eintrag, dict)
            and isinstance(eintrag.get("datei"), str)
            and isinstance(eintrag.get("sha256"), str)
        }
    except (OSError, ValueError, KeyError, TypeError) as exc:
        fehler.append(f"Eingangsregister fuer Transformationsquelle unlesbar: {exc}")
    else:
        if registriert.get(spec.quelle_datei) != spec.quelle_sha256:
            fehler.append(
                "TransformationsSpec.quelle_datei/quelle_sha256 bindet keine "
                "aktuell registrierte Eingangsquelle"
            )
    return fehler, ziel, ziel_hash


def _b1_fehler(
    *,
    ledger_pfad: Path,
    fall: Path,
    repo_root: Path,
    ziel: Path,
    ziel_sha256: str,
    erwartetes_system: Dict[str, str],
) -> List[str]:
    """B1-Ledger strikt laden und alle von B1 gehashten Bytes nachrechnen."""
    try:
        payload = json.loads(ledger_pfad.read_text(encoding="utf-8"))
        entry = GateLedgerEntry.from_dict(payload)
    except (OSError, UnicodeError, ValueError, TypeError) as exc:
        return [f"B1-Ledger ungueltig: {exc}"]
    fehler: List[str] = []
    erwartet = {
        "gate": bestand_validate.GATE,
        "command": "bestand_validate",
        "gate_version": bestand_validate.GATE_VERSION,
        "required": True,
        "status": "passed",
    }
    for feld, wert in erwartet.items():
        if getattr(entry, feld) != wert:
            fehler.append(f"B1-Ledger.{feld} ist {getattr(entry, feld)!r} statt {wert!r}")
    if entry.summary.get("exit_code") != 0 or entry.summary.get("all_passed") is not True:
        fehler.append("B1-Ledger traegt kein konsistentes gruenes Einzelurteil")
    if entry.summary.get("system") != erwartetes_system:
        fehler.append("B1-Ledger bindet nicht den aktuellen Systemstand")

    ziel_gebunden = False
    for name, erwartet_hash in entry.input_hashes.items():
        roh = Path(name)
        kandidaten = [roh] if roh.is_absolute() else [fall / roh, repo_root / roh]
        vorhanden = next((pfad.resolve() for pfad in kandidaten if pfad.is_file()), None)
        if vorhanden is None:
            fehler.append(f"B1-Eingangsartefakt {name!r} fehlt")
            continue
        gefunden = sha256(vorhanden.read_bytes()).hexdigest()
        if gefunden != erwartet_hash:
            fehler.append(f"B1-Eingangsartefakt {name!r} hat einen anderen SHA-256")
        if vorhanden == ziel.resolve() and erwartet_hash == ziel_sha256:
            ziel_gebunden = True
    if not ziel_gebunden:
        fehler.append(
            "B1-Ledger bindet das aktuelle transformierte Zielartefakt nicht"
        )
    return fehler


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="python -m rechner_pipeline.gates.abnahmebericht",
        description=(
            "Migrationsabnahmebericht rendern und protokollieren — die "
            "Entscheidungsvorlage des MENSCHLICHEN Gates G-2, keine "
            "Abnahme."
        ),
    )
    parser.add_argument(
        "--fall", default=None,
        help="Fall-Arbeitsbereich; setzt die Vorgaben fuer --bericht und "
        "--diagnostics-dir.")
    parser.add_argument(
        "--suite", default=None,
        help="JSON-Ergebnis von qa.migrationssuite.pruefe_bestand (Pflicht).")
    parser.add_argument("--titel", default=None, help="Berichtstitel (Pflicht).")
    parser.add_argument(
        "--stichtag-1", dest="stichtag_1", default=None,
        help="Migrationsstichtag, ISO-Datum (Pflicht).")
    parser.add_argument(
        "--stichtag-2", dest="stichtag_2", default=None,
        help="Folgestichtag, ISO-Datum (Pflicht).")
    parser.add_argument(
        "--spec", default=None,
        help="TransformationsSpec als JSON (optional; Mapping-Tabelle).")
    parser.add_argument(
        "--transformation-ergebnis", dest="transformation_ergebnis",
        default=None,
        help="JSON der Mapping-Anwendung (zeilen_quelle/zeilen_ziel/befunde).")
    parser.add_argument(
        "--bestandsbericht-vor", dest="bestandsbericht_vor", default=None,
        help="Verweis auf den Bestandsbericht VOR der Migration.")
    parser.add_argument(
        "--bestandsbericht-nach", dest="bestandsbericht_nach", default=None,
        help="Verweis auf den Bestandsbericht NACH der Migration.")
    parser.add_argument(
        "--b1-ledger", dest="b1_ledger", default=None,
        help="Gruenes B1-Ledger; im Bestands-Scope Default: "
        "<fall>/abgeleitet/diagnostics/bestand_validate.gate.json.")
    parser.add_argument(
        "--bericht", default=None,
        help="Zielpfad des HTML-Berichts (Vorgabe mit --fall: "
        "<fall>/abgeleitet/berichte/migrationsabnahme.html).")
    parser.add_argument("--repo-root", dest="repo_root", default=None)
    parser.add_argument(
        "--diagnostics-dir", dest="diagnostics_dir", default=None,
        help="Verzeichnis fuer den Gate-Ledger-Eintrag.")
    add_request_json_arg(parser)
    return parser


def main(argv: Optional[List[str]] = None):
    started_at = utc_now()
    parser = _build_parser()
    args = parser.parse_args(argv)
    request = read_request_json(args.request_json)
    args = merge_request_into_args(args, request)

    fall = Path(args.fall).resolve() if args.fall else None
    diagnostics_dir = (
        Path(args.diagnostics_dir) if args.diagnostics_dir
        else (fall / "abgeleitet" / "diagnostics" if fall
              else Path.cwd() / "runs" / "diagnostics")
    )

    def _finalize(result):
        try:
            write_gate_ledger(
                result, diagnostics_dir,
                repo_root=Path(args.repo_root) if args.repo_root else None,
                started_at=started_at, ended_at=utc_now(),
                command_line=argv if argv is not None else sys.argv[1:],
            )
        except Exception as exc:  # noqa: BLE001 — Ledger maskiert nie das Urteil
            log(f"{COMMAND}: gate-ledger write failed: {exc}")
        return result

    def _usage(message: str):
        return _finalize(build_result(
            command=COMMAND, gate=GATE, gate_version=GATE_VERSION,
            exit_code=Exit.USAGE,
            errors=[{"code": "usage", "message": message}],
        ))

    fall_scope: Optional[str] = None
    if fall is not None and (fall / fall_mod.FALL_MANIFEST).is_file():
        try:
            fall_scope = fall_mod.lade_scope(fall)
        except fall_mod.FallFehler as exc:
            return _usage(f"ungueltiger Fall-Scope: {exc}")
    bestands_scope = fall_scope == "bestand"

    fehlende_flags = [
        name for name, wert in (
            ("--suite", args.suite), ("--titel", args.titel),
            ("--stichtag-1", args.stichtag_1),
            ("--stichtag-2", args.stichtag_2))
        if not wert
    ]
    if fehlende_flags:
        return _usage(f"erforderlich: {', '.join(fehlende_flags)}")
    if not args.bericht and fall is None:
        return _usage(
            "Zielpfad des Berichts unbestimmt: --bericht angeben oder "
            "--fall setzen (dann <fall>/abgeleitet/berichte/"
            "migrationsabnahme.html)")

    if bestands_scope:
        bestands_flags = [
            name for name, wert in (
                ("--spec", args.spec),
                ("--transformation-ergebnis", args.transformation_ergebnis),
                ("--bestandsbericht-vor", args.bestandsbericht_vor),
                ("--bestandsbericht-nach", args.bestandsbericht_nach),
            ) if not wert
        ]
        if bestands_flags:
            return _usage(
                "Bestands-Scope verlangt die DAG-Pflichtbelege: "
                + ", ".join(bestands_flags)
            )
        if args.bestandsbericht_vor == args.bestandsbericht_nach:
            return _usage(
                "Bestands-Scope verlangt zwei verschiedene Vor-/Nachberichte"
            )
        if not args.b1_ledger:
            args.b1_ledger = str(
                fall / "abgeleitet" / "diagnostics" / "bestand_validate.gate.json"
            )

    eingaben: Dict[str, Path] = {"suite": Path(args.suite)}
    if args.spec:
        eingaben["spec"] = Path(args.spec)
    if args.transformation_ergebnis:
        eingaben["transformation_ergebnis"] = Path(args.transformation_ergebnis)
    if bestands_scope:
        eingaben.update({
            "b1_ledger": Path(args.b1_ledger),
            "bestandsbericht_vor": Path(args.bestandsbericht_vor),
            "bestandsbericht_nach": Path(args.bestandsbericht_nach),
        })
    fehlend = [str(p) for p in eingaben.values() if not p.is_file()]
    if fehlend:
        return _usage(f"Datei nicht gefunden: {'; '.join(fehlend)}")

    bericht_pfad = (
        Path(args.bericht) if args.bericht
        else fall / "abgeleitet" / "berichte" / "migrationsabnahme.html"
    )
    paths = {name: str(p) for name, p in eingaben.items()}
    paths["bericht"] = str(bericht_pfad)
    if fall is not None:
        paths["fall"] = str(fall)
    repo_root = Path(args.repo_root).resolve() if args.repo_root else Path.cwd().resolve()
    hash_basis = fall if bestands_scope else (
        repo_root if args.repo_root else None
    )
    input_hashes = hash_files(list(eingaben.values()), base=hash_basis)

    def _contract_fehler(code: str, meldungen: List[str], hinweis: str):
        gezeigt = meldungen[:20]
        if len(meldungen) > len(gezeigt):
            gezeigt.append(
                f"... und weitere {len(meldungen) - len(gezeigt)} von "
                f"{len(meldungen)}")
        return _finalize(build_result(
            command=COMMAND, gate=GATE, gate_version=GATE_VERSION,
            exit_code=Exit.FILE_CONTRACT, paths=paths,
            input_hashes=input_hashes,
            errors=[{"code": code, "message": m} for m in gezeigt],
            repair_hints=[{"code": code, "hint": hinweis}],
        ))

    try:
        suite = json.loads(eingaben["suite"].read_text(encoding="utf-8"))
    except (OSError, ValueError) as exc:
        return _contract_fehler(
            "suite_unlesbar", [f"{type(exc).__name__}: {exc}"],
            "Suite-Ergebnis ist das JSON von "
            "qa.migrationssuite.pruefe_bestand (json.dump des Rueckgabe-"
            "Dicts); erneut erzeugen statt von Hand schreiben.")
    struktur_fehler = _suite_fehler(suite)
    if struktur_fehler:
        return _contract_fehler(
            "suite_contract", struktur_fehler,
            "Das Suite-Ergebnis stammt unveraendert aus "
            "qa.migrationssuite.pruefe_bestand; die Suite erneut laufen "
            "lassen, statt die Zusammenfassung nachzubessern.")

    spec = None
    if "spec" in eingaben:
        try:
            spec = TransformationsSpec.model_validate_json(
                eingaben["spec"].read_text(encoding="utf-8"))
        except (OSError, ValueError) as exc:
            return _contract_fehler(
                "spec_unlesbar", [f"{type(exc).__name__}: {exc}"],
                "Die TransformationsSpec muss dem Schema von "
                "ontologie.transformation.TransformationsSpec genuegen.")

    transformation_ergebnis = None
    transformations_ziel: Optional[Path] = None
    transformations_ziel_hash: Optional[str] = None
    gemeinsame_bindung: Optional[Dict[str, Any]] = None
    if "transformation_ergebnis" in eingaben:
        try:
            transformation_ergebnis = json.loads(
                eingaben["transformation_ergebnis"].read_text(
                    encoding="utf-8"))
        except (OSError, ValueError) as exc:
            return _contract_fehler(
                "transformation_ergebnis_unlesbar",
                [f"{type(exc).__name__}: {exc}"],
                "Erwartet ein JSON-Objekt mit zeilen_quelle, zeilen_ziel "
                "und befunde (Ausgabe von ontologie.transformation.wende_an).")
        if bestands_scope:
            assert fall is not None and spec is not None
            transformation_fehler, transformations_ziel, transformations_ziel_hash = (
                _transformation_fehler(
                    fall=fall,
                    spec_pfad=eingaben["spec"],
                    spec=spec,
                    ergebnis=transformation_ergebnis,
                )
            )
            if transformation_fehler:
                return _contract_fehler(
                    "transformation_contract",
                    transformation_fehler,
                    "TransformationsSpec gegen die im Ergebnis gebundenen "
                    "Quellspalten validieren, Ergebnis mit Quell-, Spec- und "
                    "Ziel-SHA neu aus der deterministischen Anwendung schreiben.",
                )
        else:
            fehlende_felder = [
                f for f in ("zeilen_quelle", "zeilen_ziel")
                if not isinstance(transformation_ergebnis, dict)
                or f not in transformation_ergebnis
            ]
            if fehlende_felder:
                return _contract_fehler(
                    "transformation_ergebnis_contract",
                    [f"Feld {f!r} fehlt" for f in fehlende_felder],
                    "Erwartet ein JSON-Objekt mit zeilen_quelle, zeilen_ziel "
                    "und befunde (Ausgabe von ontologie.transformation.wende_an).")

    if bestands_scope:
        assert fall is not None
        assert transformations_ziel is not None
        assert transformations_ziel_hash is not None
        try:
            gemeinsame_bindung = scope_bindung(
                fall, repo_root, args.stichtag_1, args.stichtag_2
            )
        except fall_mod.FallFehler as exc:
            return _contract_fehler(
                "scope_bindung", [str(exc)],
                "Eingang, A-Box und Scope-Deklaration vervollstaendigen.",
            )
        b1_fehler = _b1_fehler(
            ledger_pfad=eingaben["b1_ledger"],
            fall=fall,
            repo_root=repo_root,
            ziel=transformations_ziel,
            ziel_sha256=transformations_ziel_hash,
            erwartetes_system=gemeinsame_bindung["system"],
        )
        if b1_fehler:
            return _contract_fehler(
                "b1_contract",
                b1_fehler,
                "Gate B1 auf dem transformierten Zielartefakt und aktuellen "
                "Begleitartefakten erneut ausfuehren.",
            )
        suite_scope_fehler = _bestands_suite_fehler(
            suite,
            stichtag_1=args.stichtag_1,
            stichtag_2=args.stichtag_2,
            bestand_sha256=transformations_ziel_hash,
        )
        if suite_scope_fehler:
            return _contract_fehler(
                "suite_scope_contract",
                suite_scope_fehler,
                "Migrationssuite vollstaendig auf genau dem transformierten "
                "Bestand und den beiden Scope-Stichtagen neu ausfuehren.",
            )

    # Der Bericht wird auf BEIDEN Pfaden geschrieben: gerade der rote
    # Bericht ist das Beweisstueck, mit dem der Mensch entscheidet.
    schreibe_bericht(
        bericht_pfad, titel=args.titel,
        stichtag_1=args.stichtag_1, stichtag_2=args.stichtag_2,
        suite=suite, spec=spec,
        transformation_ergebnis=transformation_ergebnis,
        bestandsbericht_vor=args.bestandsbericht_vor,
        bestandsbericht_nach=args.bestandsbericht_nach,
    )
    output_hashes = hash_files([bericht_pfad], base=fall if bestands_scope else repo_root)

    befunde_gesamt = sum(len(u["befunde"]) for u in suite["vertraege"])
    pruefungen_gesamt = sum(len(u["pruefungen"]) for u in suite["vertraege"])
    max_residuum = max(
        (abs(p["residuum"]) for u in suite["vertraege"]
         for p in u["pruefungen"]), default=0.0)
    summary = {
        "anzahl": suite["anzahl"],
        "erwartete_anzahl": suite["erwartete_anzahl"],
        "bestanden": suite["bestanden"],
        "fehlgeschlagen": suite["fehlgeschlagen"],
        "suite_bestanden": bool(suite["suite_bestanden"]),
        "befunde": befunde_gesamt,
        "mengenbefunde": len(suite["mengenbefunde"]),
        "pruefungen": pruefungen_gesamt,
        "max_residuum": max_residuum,
        "mapping_tabelle": spec is not None,
        # Was NICHT geprueft wurde, steht neben dem Urteil (P2).
        "vollstaendig_geprueft": bool(suite["vollstaendig_geprueft"]),
        "pruefluecken": list(suite["pruefluecken"]),
        # Ausdruecklich: dieses Kommando nimmt nichts ab.
        "abnahme": "offen — Gate G-2 (Mensch, gates/gate_entscheid)",
    }
    if gemeinsame_bindung is not None:
        summary["scope_bindung"] = gemeinsame_bindung

    if suite["suite_bestanden"] and befunde_gesamt == 0:
        if bestands_scope:
            assert fall is not None and gemeinsame_bindung is not None
            try:
                artefakte = {
                    "b1_ledger": artefakt_eintrag(fall, eingaben["b1_ledger"]),
                    "migrationssuite": artefakt_eintrag(fall, eingaben["suite"]),
                    "transformationsspec": artefakt_eintrag(fall, eingaben["spec"]),
                    "transformationsergebnis": artefakt_eintrag(
                        fall, eingaben["transformation_ergebnis"]
                    ),
                    "bestandsbericht_vor": artefakt_eintrag(
                        fall, eingaben["bestandsbericht_vor"]
                    ),
                    "bestandsbericht_nach": artefakt_eintrag(
                        fall, eingaben["bestandsbericht_nach"]
                    ),
                    "abnahmebericht": artefakt_eintrag(fall, bericht_pfad),
                }
            except ValueError as exc:
                return _contract_fehler(
                    "scope_artefakt", [str(exc)],
                    "Alle Bestands-Pflichtartefakte innerhalb des Falls ablegen.",
                )
            if set(artefakte) != set(bestands_belegrollen()):
                return _contract_fehler(
                    "gate_dag",
                    ["interne Belegrollen weichen vom deklarativen Gate-DAG ab"],
                    "Gate-DAG und Scope-Beleg-Erzeuger gemeinsam versionieren.",
                )
            try:
                scope_beleg_pfad, scope_beleg = schreibe_scope_beleg(
                    diagnostics_dir,
                    bindung=gemeinsame_bindung,
                    artefakte=artefakte,
                )
            except (OSError, ValueError) as exc:
                return _contract_fehler(
                    "scope_beleg", [str(exc)],
                    "Alle Bestands-Pflichtartefakte innerhalb des Falls "
                    "ablegen und den Scope-Beleg erneut erzeugen.",
                )
            paths["scope_beleg"] = str(scope_beleg_pfad)
            summary["scope_beleg_sha256"] = scope_beleg["beleg_sha256"]
            summary["pflichtbelege"] = {
                rolle: eintrag["sha256"] for rolle, eintrag in artefakte.items()
            }
            output_hashes = hash_files(
                [bericht_pfad, scope_beleg_pfad], base=fall
            )
        log(f"{COMMAND}: Vorlage ohne Fehlschlag ({summary['bestanden']} von "
            f"{summary['anzahl']} Vertraegen, "
            f"{len(suite['pruefluecken'])} Pruefluecke(n)) -> "
            f"{bericht_pfad}")
        return _finalize(build_result(
            command=COMMAND, gate=GATE, gate_version=GATE_VERSION,
            exit_code=Exit.OK, paths=paths, summary=summary,
            input_hashes=input_hashes, output_hashes=output_hashes,
            diagnostics_path=str(bericht_pfad),
        ))

    errors = [
        {"code": "mengenbefund", "message": m}
        for m in suite["mengenbefunde"]
    ] + [
        {"code": "abnahmetest", "message":
         f"{u['police_id']} / {p['groesse']}: System {p['system']:.2f} "
         f"gegen Lieferung {p['erwartet']:.2f} (Residuum "
         f"{p['residuum']:.4f})"}
        for u in suite["vertraege"] for p in u["pruefungen"] if not p["ok"]
    ] + [
        {"code": "befund", "message": f"{u['police_id']}: {b}"}
        for u in suite["vertraege"] for b in u["befunde"]
    ]
    if len(errors) > 50:
        # Der Bericht weist ALLE aus; das JSON bleibt lesbar und nennt die
        # Gesamtzahl, statt sie stillschweigend zu unterschlagen.
        errors = errors[:50] + [{
            "code": "gekuerzt",
            "message": f"... und weitere {len(errors) - 50} von "
                       f"{len(errors)}; vollstaendig im Bericht "
                       f"{bericht_pfad}",
        }]
    log(f"{COMMAND}: {summary['fehlgeschlagen']} von {summary['anzahl']} "
        f"Vertraegen fehlgeschlagen, {befunde_gesamt} Befund(e), "
        f"{summary['mengenbefunde']} Befund(e) der Pruefmenge -> "
        f"{bericht_pfad}")
    return _finalize(build_result(
        command=COMMAND, gate=GATE, gate_version=GATE_VERSION,
        exit_code=Exit.GOLDEN_MASTER, paths=paths, summary=summary,
        input_hashes=input_hashes, output_hashes=output_hashes,
        diagnostics_path=str(bericht_pfad), errors=errors,
        repair_hints=[{
            "code": "abnahme",
            "hint": "Abweichungen und Befunde gehen unveraendert an den "
            "Menschen (Gate G-2): weder Erwartungswerte noch Toleranzen "
            "anpassen. Der Bericht unter 'bericht' weist jeden Einzelwert "
            "aus.",
        }],
    ))


if __name__ == "__main__":  # pragma: no cover
    raise SystemExit(run_command(main))
