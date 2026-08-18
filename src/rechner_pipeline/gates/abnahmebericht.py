"""Migrationsabnahmebericht: deterministisches HTML als G-2-Vorlage.

Die Entscheidungsvorlage der menschlichen Migrationsabnahme, aus drei
deterministischen Bausteinen:

1. Abnahmetests der Migrationssuite (``qa/migrationssuite``):
   Deckungskapital an ZWEI Stichtagen plus GeVo-Beträge dazwischen —
   als Zusammenfassung je Prüfgröße UND als vollständige
   Einzelvergleichs-Tabelle (jeder Vertrag, jeder Wert, jedes
   Residuum); Fehlschläge und Befunde gesondert.
2. Transformations-Tabelle (``ontologie/transformation``): das
   fachlich abzunehmende Mapping Quellfeld -> Zielfeld samt
   Begründungen und (entschiedenen) Konflikten.
3. Verweise auf die Bestandsberichte VOR und NACH der Migration —
   der visuelle Vergleich ist Teil der Abnahme.

Der Bericht RECHNET nichts und ENTSCHEIDET nichts: gleiche Eingaben
ergeben byte-identisches HTML (keine Zeitstempel), und das Verdikt ist
ausdrücklich eine maschinelle Prüfaussage — die Abnahme selbst ist
Gate G-2 (Mensch, Entscheid-Snapshot).

Knoten: klv
"""

from __future__ import annotations

import html
from pathlib import Path
from typing import Any, Dict, List, Optional

from rechner_pipeline.ontologie.transformation import TransformationsSpec

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
    if suite["suite_bestanden"]:
        teile.append(
            f"<p class='gruen'>ALLE ABNAHMETESTS BESTANDEN "
            f"({suite['bestanden']:.0f} von {suite['anzahl']:.0f} "
            "Verträgen).</p>")
    else:
        teile.append(
            f"<p class='rot'>{suite['fehlgeschlagen']:.0f} von "
            f"{suite['anzahl']:.0f} Verträgen FEHLGESCHLAGEN.</p>")
    teile.append(
        "<p class='hinweis'>Maschinelle Prüfaussage der deterministischen "
        "Migrationssuite. Die ABNAHME ist eine menschliche Entscheidung "
        "(Gate G-2) auf Grundlage dieses Berichts.</p>")

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
