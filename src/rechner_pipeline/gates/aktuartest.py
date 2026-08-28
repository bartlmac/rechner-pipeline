"""``aktuartest`` toolbox command — Vorlage fuer die drei aktuariellen Abnahmen.

Rendert aus dem Ergebnis des aktuariellen Tests (``qa.aktuarieller_test``,
als JSON persistiert) die Entscheidungsvorlage fuer den Verantwortlichen
Aktuar. Es gibt drei Abnahmen mit je eigener Stichprobe, eigenen Kriterien
und eigenem Bericht (ADR-010, ADR-012), und alle drei gehen dem
Migrationscontrolling ``A-M4`` voraus:

``A-M1`` Stichtagstest, ``A-M2`` Verlaufstest, ``A-M3``
Geschaeftsvorfalltest. Welcher gerendert wird, sagt das Ergebnis selbst
ueber sein Profil — das Kommando erfindet keinen Test, es liest den, der
gelaufen ist.

Dabei wird der Ergebnis-Vertrag von innen nach aussen neu geprueft:
Einzelurteile gegen die Toleranzen DES PROFILS, Vertragsurteile gegen ihre
Einzelvergleiche, Zaehler und Stichproben-Vollstaendigkeit, zuletzt
saemtliche Verteilungsgroessen samt Abnahmegrenzen. Eine gruene
Zusammenfassung ueber einem roten Einzelvergleich ist damit auch auf dem
Bibliothekspfad unmoeglich. Die Werte selbst rechnet ausschliesslich die
Engine; der Zusammenbau der Pruefauftraege ist Sache des Falls.

Die Transportsicherung (Datei-Hashes, gelieferte Kontrollsummen) wird im
Bericht GETRENNT ausgewiesen und ist nie Teil des fachlichen Urteils
(ADR-010). Der Bericht ist deterministisch: gleiche Eingaben ergeben
byte-identisches HTML, keine Zeitstempel.

Exit-Codes: 0 = Vorlage vollstaendig und Test bestanden; 30 = Test nicht
bestanden (Wertabweichung oder Stichprobe nicht abgearbeitet); 20 =
Ergebnis-Datei verletzt den Vertrag; 2 = Bedienfehler.

Run via::

    python -m rechner_pipeline.gates.aktuartest \\
        --fall faelle/<fall> --titel "Aktuarieller Test <Fall>" \\
        [--test <pfad>.json] [--bericht <pfad>.html]

Knoten: klv
"""

from __future__ import annotations

import json
import math
import sys
from pathlib import Path
from typing import Any, Dict, List, Mapping, Optional

from rechner_pipeline.gates._common import (
    Exit,
    GATE_LEDGER_SUFFIX,
    GateCliContract,
    GateArgumentParser,
    add_request_json_arg,
    begin_gate_ledger_attempt,
    build_result,
    finalize_gate_ledger,
    hash_files,
    parse_gate_args,
    run_command,
    utc_now,
)
from rechner_pipeline.qa.aktuarieller_test import (
    KRITERIUM_PLAUSIBILITAET,
    KRITERIUM_VERGLEICH,
    _KORRIDOR_TOL,
    PERZENTILE,
    verteilung,
    verteilungsbefunde,
)
from rechner_pipeline.qa.testprofil import Kriterium, ProfilFehler, Testprofil

COMMAND = "aktuartest"

#: Die drei Tests und ihre Gate-Kennungen (ADR-012). Das Kommando liefert
#: je Test die VORLAGE; die aktuarielle Abnahme ist der menschliche
#: Entscheid am jeweiligen Gate. Alle drei gehen dem Migrationscontrolling
#: (A-M4) voraus.
GATES: Dict[str, str] = {
    "A-M1": "A-M1.stichtagstest",
    "A-M2": "A-M2.verlaufstest",
    "A-M3": "A-M3.geschaeftsvorfalltest",
}
#: Der Vorgabetest, wenn das Kommando ohne ``--test`` laeuft: der
#: Stichtagstest, mit dem jede Migration beginnt.
GATE = GATES["A-M1"]
GATE_VERSION = "2.0.0"
CLI_CONTRACT = GateCliContract(
    command=COMMAND,
    gate=GATE,
    gate_version=GATE_VERSION,
    diagnostics_from="fall",
)

_ERGEBNIS_FELDER = {
    "profil", "stichprobe", "anzahl", "bestanden", "fehlgeschlagen",
    "mengenbefunde", "grenzbefunde", "stichprobe_vollstaendig",
    "verteilung", "gruppen", "nach_anlass", "nach_kriterium",
    "vertraege", "test_bestanden",
}
_PROFIL_FELDER = {
    "kennung", "titel", "weite", "grundtoleranz", "kriterien", "bemerkung",
}
_STICHPROBEN_FELDER = {
    "profil", "parameter", "umfang", "grundgesamtheit", "vollerhebung",
    "police_ids",
}
_VERTRAGS_FELDER = {
    "police_id", "historientyp", "anlaesse", "bestanden", "pruefungen",
    "befunde",
}
_PRUEFUNGS_FELDER = {
    "anlass", "monate", "groesse", "system", "erwartet", "residuum", "ok",
}

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
    return (
        str(text)
        .replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")
        .replace('"', "&quot;")
    )


def _ok(ist: float, soll: float, k: Kriterium) -> bool:
    return math.isclose(ist, soll, rel_tol=k.rel_tol, abs_tol=k.abs_tol)


def _profil_aus_beleg(beleg: Mapping[str, Any]) -> Testprofil:
    """Das Profil aus seinem eigenen Beleg zurueckbauen.

    Damit rechnet das Gate mit GENAU den Kriterien nach, die im Ergebnis
    ausgewiesen sind — nicht mit einer Konstante, die anderswo steht. Ein
    Ergebnis, das seine Toleranzen nicht mitbringt, ist nicht pruefbar.
    """
    return Testprofil(
        kennung=beleg["kennung"],
        weite=beleg["weite"],
        bemerkung=beleg.get("bemerkung", ""),
        grundtoleranz=Kriterium(**beleg["grundtoleranz"]),
        kriterien={s: Kriterium(**k) for s, k in beleg["kriterien"].items()},
    )


def _ist_wertvergleich(pruefung: Mapping[str, Any]) -> bool:
    """Ob eine Pruefung in die Residuum-Verteilung eingeht.

    Nur Wertvergleiche tun das. Eine Plausibilitaetspruefung hat keinen
    gemeinsamen Massstab mit der Lieferung; ihr Residuum in dieselbe
    Verteilung zu werfen hiesse, die Aussage ueber die Methode mit einer
    Groesse zu verduennen, die gar nicht verglichen wurde.
    """
    return pruefung.get("kriterium", KRITERIUM_VERGLEICH) != (
        KRITERIUM_PLAUSIBILITAET)


def test_fehler(test: Any) -> List[str]:
    """Ergebnis-Vertrag von innen nach aussen neu ableiten.

    Rueckgabe: Befundliste (leer = konsistent). Geprueft wird alles, was
    sich ohne die Modellpunkte nachrechnen laesst — in vier Schritten, von
    denen jeder auf dem vorigen aufsetzt:

    1. jeden Einzelvergleich gegen die Toleranz des Profils,
    2. jedes Vertragsurteil gegen seine Einzelvergleiche,
    3. Zaehler und Mengenabgleich gegen die Stichprobe,
    4. saemtliche Verteilungsgroessen und Abnahmegrenzen.

    Der Sinn ist die Reihenfolge: Ein gruenes Gesamturteil kann nicht ueber
    einem roten Einzelvergleich stehen, weil das Urteil aus den
    Einzelvergleichen entsteht und nicht daneben.
    """
    if not isinstance(test, dict):
        return ["Ergebnis ist kein Objekt"]
    fehler: List[str] = []
    fehlend = sorted(_ERGEBNIS_FELDER - set(test))
    if fehlend:
        return [f"Pflichtfelder fehlen: {fehlend}"]

    profil_beleg = test["profil"]
    if not isinstance(profil_beleg, dict) or (_PROFIL_FELDER - set(profil_beleg)):
        return fehler + ["profil: Beleg-Felder unvollstaendig"]
    if profil_beleg["kennung"] not in GATES:
        return fehler + [
            f"profil: unbekannter Test {profil_beleg['kennung']!r} — "
            f"bekannt sind {sorted(GATES)}"
        ]
    try:
        profil = _profil_aus_beleg(profil_beleg)
    except (KeyError, TypeError, ProfilFehler) as exc:
        return fehler + [f"profil: nicht rekonstruierbar ({exc})"]
    if profil.als_beleg() != profil_beleg:
        fehler.append(
            "profil: Beleg ist nicht die Darstellung des Profils, mit dem "
            "geprueft wurde"
        )

    stichprobe = test["stichprobe"]
    if not isinstance(stichprobe, dict) or (
        _STICHPROBEN_FELDER - set(stichprobe)
    ):
        fehler.append("stichprobe: Beleg-Felder unvollstaendig")
        return fehler
    if stichprobe["umfang"] != len(stichprobe["police_ids"]):
        fehler.append("stichprobe: umfang deckt police_ids nicht")
    if len(set(stichprobe["police_ids"])) != len(stichprobe["police_ids"]):
        fehler.append(
            "stichprobe: doppelte police_ids — die Abdeckungsbehauptung "
            "waere aufgeblasen"
        )
    if stichprobe["umfang"] > stichprobe["grundgesamtheit"]:
        fehler.append("stichprobe: umfang uebersteigt die Grundgesamtheit")
    if stichprobe["vollerhebung"] != (
        stichprobe["umfang"] == stichprobe["grundgesamtheit"]
    ):
        fehler.append("stichprobe: vollerhebung widerspricht den Zahlen")

    vertraege = test["vertraege"]
    ids = [v.get("police_id") for v in vertraege]
    if len(ids) != len(set(ids)):
        fehler.append("vertraege: doppelte police_id")
    alle_residuen: List[float] = []
    fehlgeschlagen = 0
    feld_fehler = False
    plausibilitaets_zahl = 0
    for v in vertraege:
        v_fehlend = sorted(_VERTRAGS_FELDER - set(v))
        if v_fehlend:
            fehler.append(f"vertrag {v.get('police_id')}: {v_fehlend} fehlt")
            feld_fehler = True
            continue
        alle_ok = bool(v["pruefungen"])
        for p in v["pruefungen"]:
            p_fehlend = sorted(_PRUEFUNGS_FELDER - set(p))
            if p_fehlend:
                fehler.append(
                    f"police {v['police_id']}: Vergleich ohne {p_fehlend}"
                )
                feld_fehler = True
                continue
            if p["anlass"] not in v["anlaesse"]:
                fehler.append(
                    f"police {v['police_id']}: Vergleich am Anlass "
                    f"{p['anlass']!r}, den die Vertragszeile nicht auffuehrt"
                )
            residuum = p["system"] - p["erwartet"]
            if p["residuum"] != residuum:
                fehler.append(
                    f"police {v['police_id']} {p['groesse']}: residuum "
                    "ist nicht system - erwartet"
                )
            if p.get("kriterium") == KRITERIUM_PLAUSIBILITAET:
                # Ersetzter Wertvergleich: geprueft wird gegen den
                # ausgewiesenen Korridor, und zwar auf BEIDEN Seiten.
                # Sein Residuum bleibt aus der Verteilung heraus — sonst
                # verzerrte eine Groesse ohne gemeinsamen Massstab die
                # Aussage ueber die Methode.
                korridor = p.get("korridor")
                begruendung = str(p.get("begruendung", "")).strip()
                if (not isinstance(korridor, list) or len(korridor) != 2
                        or korridor[0] > korridor[1]):
                    fehler.append(
                        f"police {v['police_id']} {p['groesse']}: "
                        "Plausibilitaetspruefung ohne gueltigen Korridor"
                    )
                    feld_fehler = True
                    continue
                if not begruendung:
                    fehler.append(
                        f"police {v['police_id']} {p['groesse']}: "
                        "Plausibilitaetspruefung ohne Begruendung — eine "
                        "Ausnahme ohne Beleg ist keine"
                    )
                if v["police_id"] not in test.get(
                        "plausibilitaet_statt_vergleich", {}):
                    fehler.append(
                        f"police {v['police_id']} {p['groesse']}: "
                        "Plausibilitaetspruefung ohne Ausweis in der "
                        "Zusammenfassung"
                    )
                unten, oben = float(korridor[0]), float(korridor[1])
                system_ok = unten - _KORRIDOR_TOL <= p["system"] <= oben + _KORRIDOR_TOL
                erwartet_ok = (
                    unten - _KORRIDOR_TOL <= p["erwartet"] <= oben + _KORRIDOR_TOL)
                if bool(p.get("erwartet_im_korridor")) != erwartet_ok:
                    fehler.append(
                        f"police {v['police_id']} {p['groesse']}: "
                        "erwartet_im_korridor widerspricht dem Korridor"
                    )
                soll_ok = system_ok and erwartet_ok
                if bool(p["ok"]) != soll_ok:
                    fehler.append(
                        f"police {v['police_id']} {p['groesse']}: ok-Urteil "
                        "widerspricht dem Plausibilitaets-Korridor"
                    )
                alle_ok = alle_ok and soll_ok
                plausibilitaets_zahl += 1
                continue
            # Beim Geschaeftsvorfalltest entscheidet die Vorfallart ueber
            # die Toleranz, sonst die Vergleichsgroesse — dieselbe Regel
            # wie in der Engine, hier unabhaengig nachvollzogen.
            schluessel = (
                p["anlass"] if profil.kennung == "A-M3" else p["groesse"]
            )
            soll_ok = _ok(p["system"], p["erwartet"], profil.fuer(schluessel))
            if bool(p["ok"]) != soll_ok:
                fehler.append(
                    f"police {v['police_id']} {p['groesse']}: ok-Urteil "
                    "widerspricht den Toleranzen des Profils"
                )
            alle_ok = alle_ok and soll_ok
            alle_residuen.append(residuum)
        if bool(v["bestanden"]) != (alle_ok and not v["befunde"]):
            fehler.append(
                f"police {v['police_id']}: bestanden widerspricht den "
                "Einzelurteilen"
            )
        if not v["bestanden"]:
            fehlgeschlagen += 1

    if feld_fehler:
        # Ohne vollstaendige Vertragszeilen sind die nachgelagerten
        # Aggregate nicht ableitbar — die Feld-Befunde stehen fuer sich.
        return fehler
    if test.get("plausibilitaets_pruefungen", 0) != plausibilitaets_zahl:
        fehler.append(
            "plausibilitaets_pruefungen widerspricht den Einzelpruefungen")
    if test["anzahl"] != len(vertraege):
        fehler.append("anzahl deckt vertraege nicht")
    if test["fehlgeschlagen"] != fehlgeschlagen:
        fehler.append("fehlgeschlagen-Zaehler widerspricht den Urteilen")
    if test["bestanden"] != len(vertraege) - fehlgeschlagen:
        fehler.append("bestanden-Zaehler widerspricht den Urteilen")

    gezogen = set(stichprobe["police_ids"])
    geliefert = set(ids)
    soll_vollstaendig = gezogen == geliefert
    if bool(test["stichprobe_vollstaendig"]) != soll_vollstaendig:
        fehler.append(
            "stichprobe_vollstaendig widerspricht dem Mengenabgleich"
        )
    if bool(test["stichprobe_vollstaendig"]) != (not test["mengenbefunde"]):
        fehler.append("mengenbefunde widersprechen stichprobe_vollstaendig")

    if test["verteilung"] != verteilung(alle_residuen):
        fehler.append("verteilung ist nicht die Nachrechnung der Residuen")
    for typ, gruppe in sorted(test["gruppen"].items()):
        im_typ = [v for v in vertraege if v.get("historientyp") == typ]
        residuen = [
            p["system"] - p["erwartet"]
            for v in im_typ for p in v.get("pruefungen", [])
            if _ist_wertvergleich(p)
        ]
        soll = {
            "anzahl": len(im_typ),
            "bestanden": sum(1 for v in im_typ if v.get("bestanden")),
            **verteilung(residuen),
        }
        if gruppe != soll:
            fehler.append(f"gruppe {typ}: Aggregat ist nicht nachgerechnet")
    if sorted(test["gruppen"]) != sorted(
        {v.get("historientyp") for v in vertraege}
    ):
        fehler.append("gruppen decken die Historientypen nicht")

    # Zweite Cluster-Achse: der Anlass sagt, WO im Vertragsleben die
    # Residuen liegen. Ein Residuum bei der Uebernahme und eines beim
    # Ablauf sind verschiedene Befunde.
    alle_pruefungen = [
        p for v in vertraege for p in v.get("pruefungen", [])
        if _ist_wertvergleich(p)
    ]
    for anlass, aggregat in sorted(test["nach_anlass"].items()):
        residuen = [
            p["system"] - p["erwartet"]
            for p in alle_pruefungen if p["anlass"] == anlass
        ]
        soll = {"anzahl_vergleiche": len(residuen), **verteilung(residuen)}
        if aggregat != soll:
            fehler.append(f"nach_anlass {anlass}: Aggregat ist nicht nachgerechnet")
    if sorted(test["nach_anlass"]) != sorted({p["anlass"] for p in alle_pruefungen}):
        fehler.append("nach_anlass deckt die Anlaesse nicht")

    schluessel_von = (
        (lambda p: p["anlass"])
        if profil.kennung == "A-M3"
        else (lambda p: p["groesse"])
    )
    nach_schluessel: Dict[str, Any] = {}
    for s in sorted({schluessel_von(p) for p in alle_pruefungen}):
        residuen = [
            p["system"] - p["erwartet"]
            for p in alle_pruefungen if schluessel_von(p) == s
        ]
        nach_schluessel[s] = verteilung(residuen)
    if test["nach_kriterium"] != nach_schluessel:
        fehler.append("nach_kriterium ist nicht die Nachrechnung der Residuen")

    soll_grenzbefunde = verteilungsbefunde(nach_schluessel, profil)
    if sorted(test["grenzbefunde"]) != sorted(soll_grenzbefunde):
        fehler.append(
            "grenzbefunde widersprechen der Nachrechnung der Abnahmegrenzen"
        )

    soll_bestanden = (
        bool(test["stichprobe_vollstaendig"])
        and fehlgeschlagen == 0
        and not soll_grenzbefunde
    )
    if bool(test["test_bestanden"]) != soll_bestanden:
        fehler.append("test_bestanden widerspricht der Neuableitung")
    return fehler


def _verteilungs_zellen(v: Mapping[str, Any], *, mit_anzahl: bool = True) -> str:
    """Die Verteilungsgroessen als Tabellenzellen.

    ``mit_anzahl=False`` laesst die Zaehlspalte weg — dort, wo die Tabelle
    schon eine eigene Zaehlung fuehrt.
    """
    spalten = 2 + len(PERZENTILE)
    if not v.get("anzahl_werte"):
        vorn = "<td class='zahl'>0</td>" if mit_anzahl else ""
        return vorn + "<td>—</td>" * spalten
    zellen = []
    if mit_anzahl:
        zellen.append(f"<td class='zahl'>{v['anzahl_werte']:d}</td>")
    zellen.append(f"<td class='zahl'>{v['max_abs_residuum']:.6f}</td>")
    zellen.extend(
        f"<td class='zahl'>{v[f'p{p}_abs_residuum']:.6f}</td>"
        for p in PERZENTILE
    )
    zellen.append(f"<td class='zahl'>{v['summe_abs_residuum']:.6f}</td>")
    return "".join(zellen)


def _profil_abschnitt(profil: Mapping[str, Any]) -> str:
    """Weite und Abnahmekriterien — beides traegt den Beleg.

    Wer nur das Ergebnis sieht, weiss nicht, wie weit gezogen und wie eng
    gemessen wurde. Ein gruener Test ueber eine enge Stichprobe mit weiten
    Toleranzen sagt etwas anderes als derselbe Test ueber den Vollbestand.
    """
    zeilen = [
        "<h2>Testprofil (Beleg)</h2>",
        "<table><tr><th>Test</th><th>Stichprobenweite</th></tr>"
        f"<tr><td>{_e(profil['kennung'])} — {_e(profil['titel'])}</td>"
        f"<td>{_e(profil['weite'])}</td></tr></table>",
    ]
    if profil.get("bemerkung"):
        zeilen.append(f"<p>{_e(profil['bemerkung'])}</p>")
    zeilen.append(
        "<table><tr><th>gilt für</th><th>abs. Toleranz</th>"
        "<th>rel. Toleranz</th><th>Grenze max |R|</th>"
        "<th>Grenze p95 |R|</th></tr>"
    )
    def _zeile(name: str, k: Mapping[str, Any]) -> str:
        def g(wert: Any) -> str:
            return "nicht gefordert" if wert is None else f"{wert:g}"
        return (
            f"<tr><td>{_e(name)}</td>"
            f"<td class='zahl'>{k['abs_tol']:g}</td>"
            f"<td class='zahl'>{k['rel_tol']:g}</td>"
            f"<td class='zahl'>{g(k['max_abs_residuum'])}</td>"
            f"<td class='zahl'>{g(k['p95_abs_residuum'])}</td></tr>"
        )
    zeilen.append(_zeile("alle übrigen", profil["grundtoleranz"]))
    for name, k in sorted(profil["kriterien"].items()):
        zeilen.append(_zeile(name, k))
    zeilen.append("</table>")
    return "".join(zeilen)


def _anlass_abschnitt(test: Mapping[str, Any]) -> str:
    """Die zweite Cluster-Achse: WO im Vertragsleben liegen die Residuen.

    Der Historientyp sagt, welche Verträge auseinanderlaufen; der Anlass
    sagt, an welcher Stelle. Ein Residuum bei der Übernahme und eines beim
    Ablauf sind verschiedene Befunde.
    """
    kopf = (
        "<th>Vergleiche</th><th>max |R|</th>"
        + "".join(f"<th>p{p} |R|</th>" for p in PERZENTILE)
        + "<th>Summe |R|</th>"
    )
    zeilen = [
        "<h2>Residuum nach Anlass</h2>",
        f"<table><tr><th>Anlass</th>{kopf}</tr>",
    ]
    for anlass, a in sorted(test["nach_anlass"].items()):
        zeilen.append(
            f"<tr><td>{_e(anlass)}</td>"
            f"<td class='zahl'>{a['anzahl_vergleiche']:d}</td>"
            + _verteilungs_zellen(a, mit_anzahl=False)
            + "</tr>"
        )
    zeilen.append("</table>")
    if test["grenzbefunde"]:
        zeilen.append(
            "<table><tr><th class='rot'>Verletzte Abnahmegrenze</th></tr>"
            + "".join(
                f"<tr><td class='rot'>{_e(b)}</td></tr>"
                for b in test["grenzbefunde"]
            )
            + "</table>"
        )
    return "".join(zeilen)


def _schwerpunkt(test: Mapping[str, Any]) -> str:
    """Der Abschnitt, der je Test ein anderer ist.

    Die drei Tests beantworten verschiedene Fragen und brauchen deshalb
    verschiedene Darstellungen: Der Stichtagstest lebt von der
    Gegenüberstellung zweier Zeitpunkte, der Verlaufstest von der
    Entwicklung über die Restlaufzeit, der Geschäftsvorfalltest von der
    Beurteilung je Vorfallart — dort ist eine lange Tabelle mit Werten
    nahe null weniger wert als die Aussage, ob jede Vorfallart getroffen
    und plausibel gerechnet wurde.
    """
    kennung = test["profil"]["kennung"]
    if kennung == "A-M3":
        return _gevo_beurteilung(test)
    if kennung == "A-M2":
        return _verlauf_uebersicht(test)
    return _stichtag_uebersicht(test)


def _stichtag_uebersicht(test: Mapping[str, Any]) -> str:
    """A-M1: Übernahmestand und Fortschreibung nebeneinander."""
    na = test["nach_anlass"]
    u = na.get("uebernahme", {})
    f = na.get("fortschreibung", {})
    if not f:
        return (
            "<h2>Übernahme und Fortschreibung</h2>"
            "<p class='hinweis'>Dieser Lauf enthält nur den "
            "Übernahmestichtag. Der Stichtagstest ist erst vollständig, "
            "wenn auch der nächste Vertragsstichtag laut Fortschreibung "
            "verglichen wurde — sonst belegt er den Übernahmeakt, aber "
            "nicht die Fortschreibungsregel.</p>"
        )
    return (
        "<h2>Übernahme und Fortschreibung</h2>"
        "<p>Der erste Punkt belegt den Übernahmeakt, der zweite die "
        "Fortschreibungsregel. Ein Vertrag, der am Verankerungszeitpunkt "
        "stimmt und beim nächsten Stichtag nicht, hat einen Fehler, den "
        "eine Korrekturschicht verdeckt hätte.</p>"
        "<table><tr><th>Punkt</th><th>Vergleiche</th><th>max |R|</th></tr>"
        f"<tr><td>Übernahmestand</td>"
        f"<td class='zahl'>{u.get('anzahl_vergleiche', 0):d}</td>"
        f"<td class='zahl'>{u.get('max_abs_residuum', 0.0):.6f}</td></tr>"
        f"<tr><td>nächster Vertragsstichtag</td>"
        f"<td class='zahl'>{f.get('anzahl_vergleiche', 0):d}</td>"
        f"<td class='zahl'>{f.get('max_abs_residuum', 0.0):.6f}</td></tr>"
        "</table>"
    )


def _verlauf_uebersicht(test: Mapping[str, Any]) -> str:
    """A-M2: Entwicklung des Residuums über die Prüfzeitpunkte."""
    punkte: Dict[int, List[float]] = {}
    for v in test["vertraege"]:
        for p in v.get("pruefungen", []):
            punkte.setdefault(p["monate"], []).append(abs(p["residuum"]))
    zeilen = [
        "<h2>Verlauf über die Prüfzeitpunkte</h2>",
        "<p>Ein systematischer Fehler des Verlaufs wächst mit der Dauer. "
        "Wächst das Residuum von Zeitpunkt zu Zeitpunkt, liegt der Verdacht "
        "auf der Ausscheideordnung oder dem Kostenverlauf — nicht auf dem "
        "Übernahmestand.</p>",
        "<table><tr><th>Vertragsmonat</th><th>Vertragsjahr</th>"
        "<th>Verträge mit diesem Punkt</th><th>max |R|</th></tr>",
    ]
    for monate in sorted(punkte):
        betraege = punkte[monate]
        zeilen.append(
            f"<tr><td class='zahl'>{monate:d}</td>"
            f"<td class='zahl'>{monate // 12:d}</td>"
            f"<td class='zahl'>{len(betraege):d}</td>"
            f"<td class='zahl'>{max(betraege):.6f}</td></tr>"
        )
    zeilen.append("</table>")
    zeilen.append(
        "<p class='hinweis'>Nicht jeder Vertrag trägt jeden Zeitpunkt: "
        "Bei einer Restlaufzeit unter fünf bzw. zehn Jahren gibt es den "
        "Punkt nicht. Das ist kein Befund — aber die Spalte "
        "&quot;Verträge mit diesem Punkt&quot; zeigt, worüber die Aussage "
        "an dieser Stelle überhaupt reicht.</p>"
    )
    return "".join(zeilen)


def _gevo_beurteilung(test: Mapping[str, Any]) -> str:
    """A-M3: Beurteilung je Vorfallart statt einer langen Wertetabelle.

    Beim Geschäftsvorfalltest geht es um Plausibilität: Ist jede Vorfallart
    überhaupt getroffen, wie viele Fälle stützen die Aussage, und rechnet
    das System die Veränderung des Deckungskapitals so, wie die Vorfallart
    es verlangt. Eine Tabelle mit hunderten Werten nahe null trägt dazu
    weniger bei als diese Übersicht.
    """
    from rechner_pipeline.qa.aktuarieller_test import GEVO_ARTEN

    getroffen = {
        a: v for a, v in test["nach_anlass"].items() if a in GEVO_ARTEN
    }
    zeilen = [
        "<h2>Beurteilung je Geschäftsvorfall</h2>",
        "<table><tr><th>Vorfall</th><th>Vergleiche</th><th>max |R|</th>"
        "<th>Beurteilung</th></tr>",
    ]
    for art in GEVO_ARTEN:
        a = getroffen.get(art)
        if not a:
            zeilen.append(
                f"<tr><td>{_e(art)}</td><td class='zahl'>0</td>"
                "<td class='zahl'>—</td>"
                "<td>nicht in der Stichprobe — über diese Vorfallart sagt "
                "der Test nichts</td></tr>"
            )
            continue
        max_r = a.get("max_abs_residuum", 0.0)
        anzahl = a.get("anzahl_vergleiche", 0)
        if max_r == 0.0:
            urteil = "exakt getroffen"
        elif max_r < 0.005:
            urteil = "im Rundungsrauschen der Lieferung"
        else:
            urteil = "Abweichung über dem Rundungsrauschen — begründen"
        if anzahl < 3:
            urteil += f" (nur {anzahl} Fall/Fälle — schmale Grundlage)"
        zeilen.append(
            f"<tr><td>{_e(art)}</td><td class='zahl'>{anzahl:d}</td>"
            f"<td class='zahl'>{max_r:.6f}</td><td>{_e(urteil)}</td></tr>"
        )
    zeilen.append("</table>")
    fehlend = [a for a in GEVO_ARTEN if a not in getroffen]
    if fehlend:
        zeilen.append(
            "<p class='hinweis'>Nicht geprüfte Vorfallarten: "
            f"{_e(', '.join(fehlend))}. Der Test belegt sie nicht. Ob das "
            "hinnehmbar ist, entscheidet der Verantwortliche Aktuar — im "
            "laufenden Bestand können sie jederzeit auftreten.</p>"
        )
    return "".join(zeilen)


def baue_bericht(*, titel: str, test: Dict[str, Any]) -> str:
    """Entscheidungsvorlage fuer A-M1 — deterministisch, byte-identisch.

    Nur aus einem intern konsistenten Ergebnis (``test_fehler`` leer);
    sonst ``ValueError`` — derselbe fail-fast Contract wie im Kommando.
    """
    fehler = test_fehler(test)
    if fehler:
        raise ValueError(
            "Testergebnis verletzt den Aktuartest-Vertrag: "
            + "; ".join(fehler)
        )
    s = test["stichprobe"]
    teile: List[str] = [
        "<!DOCTYPE html>", "<html lang='de'><head><meta charset='utf-8'>",
        f"<title>{_e(titel)}</title><style>{_STIL}</style></head><body>",
        f"<h1>{_e(titel)}</h1>",
        "<p>Aktuarieller Test: Vergleich je Vertrag am EIGENEN "
        "Verankerungszeitpunkt t_a — am Rechenpunkt, ohne Interpolation, "
        "ohne Summation der Vergleichsgr&ouml;&szlig;en (ADR-010).</p>",
    ]
    if test["test_bestanden"]:
        teile.append(
            f"<p class='gruen'>AKTUARIELLER TEST BESTANDEN "
            f"({test['bestanden']:.0f} von {test['anzahl']:.0f} "
            "Verträgen, Stichprobe vollständig abgearbeitet).</p>"
        )
    else:
        gruende: List[str] = []
        if test["fehlgeschlagen"]:
            gruende.append(
                f"{test['fehlgeschlagen']:.0f} von {test['anzahl']:.0f} "
                "Verträgen FEHLGESCHLAGEN"
            )
        if not test["stichprobe_vollstaendig"]:
            gruende.append("Stichprobe nicht vollständig abgearbeitet")
        teile.append(
            "<p class='rot'>AKTUARIELLER TEST NICHT BESTANDEN — "
            + ", ".join(gruende) + ".</p>"
        )
    teile.append(
        "<p class='hinweis'>Maschinelle Prüfaussage des deterministischen "
        "aktuariellen Tests. Die AKTUARIELLE ABNAHME ist eine menschliche "
        "Entscheidung (Gate A-M1, Verantwortlicher Aktuar) auf Grundlage "
        "dieses Berichts.</p>"
    )

    teile.append(_profil_abschnitt(test["profil"]))

    teile.append("<h2>Stichprobe (Beleg)</h2>")
    parameter = ", ".join(
        f"{k}={v}" for k, v in sorted(s["parameter"].items())
    ) or "keine"
    teile.append(
        "<table><tr><th>Profil</th><th>Parameter</th><th>Umfang</th>"
        "<th>Grundgesamtheit</th><th>Vollerhebung</th></tr>"
        f"<tr><td>{_e(s['profil'])}</td><td>{_e(parameter)}</td>"
        f"<td class='zahl'>{s['umfang']:d}</td>"
        f"<td class='zahl'>{s['grundgesamtheit']:d}</td>"
        f"<td>{'ja' if s['vollerhebung'] else 'nein'}</td></tr></table>"
        "<p>Die vollständige Police-Liste der Ziehung steht im "
        "Test-Ergebnis (JSON) und gehört zum Beleg.</p>"
    )
    if test["mengenbefunde"]:
        teile.append("<table><tr><th>Befund der Stichprobe</th></tr>")
        teile.extend(
            f"<tr><td class='rot'>{_e(b)}</td></tr>"
            for b in test["mengenbefunde"]
        )
        teile.append("</table>")
    else:
        teile.append(
            "<p>Die Stichprobe wurde vollständig abgearbeitet. Die "
            "Nichtprüfung der Nicht-Stichprobe ist kein Befund, sondern "
            "die Definition des Tests.</p>"
        )

    kopf = (
        "<th>Werte</th><th>max |R|</th>"
        + "".join(f"<th>p{p} |R|</th>" for p in PERZENTILE)
        + "<th>Summe |R|</th>"
    )
    teile.append(
        "<h2>Verteilung des Residuums</h2>"
        "<p>Ausschließlich Verteilungsgrößen der Abweichungen — keine "
        "Summe der Vergleichswerte, kein Mittelwert (Grundsatzdokumentation 9.15).</p>"
        f"<table><tr><th>Gruppe</th><th>Verträge</th><th>bestanden</th>{kopf}"
        "</tr>"
        f"<tr><td>alle</td><td class='zahl'>{test['anzahl']:d}</td>"
        f"<td class='zahl'>{test['bestanden']:d}</td>"
        + _verteilungs_zellen(test["verteilung"]) + "</tr>"
    )
    for typ, gruppe in sorted(test["gruppen"].items()):
        teile.append(
            f"<tr><td>{_e(typ)}</td>"
            f"<td class='zahl'>{gruppe['anzahl']:d}</td>"
            f"<td class='zahl'>{gruppe['bestanden']:d}</td>"
            + _verteilungs_zellen(gruppe) + "</tr>"
        )
    teile.append("</table>")

    teile.append(_anlass_abschnitt(test))
    teile.append(_schwerpunkt(test))

    ausnahmen = test.get("plausibilitaet_statt_vergleich") or {}
    if ausnahmen:
        # VOR den Fehlschlaegen: Wer das Urteil liest, muss zuerst
        # wissen, wo NICHT gegen die Lieferung verglichen wurde.
        teile.append(
            "<h2>Ersetzter Wertvergleich (Einschränkung des Urteils)</h2>"
            "<p>Für die folgenden Verträge ist der gelieferte Wert der "
            "genannten Größe <strong>kein tauglicher Vergleichsmaßstab</strong>. "
            "An die Stelle des centgenauen Vergleichs tritt die "
            "Plausibilitätsregel des Tarifwerks; geprüft wird dabei auch "
            "der gelieferte Wert selbst. Das Urteil dieser Verträge trägt "
            f"insoweit weniger als das der übrigen — betroffen sind "
            f"{len(ausnahmen)} von {test['anzahl']} Verträgen mit "
            f"{test.get('plausibilitaets_pruefungen', 0)} Einzelprüfungen."
            "</p><table><tr><th>Police</th><th>Größe</th>"
            "<th>Begründung</th></tr>"
        )
        for police in sorted(ausnahmen):
            for groesse, grund in sorted(dict(ausnahmen[police]).items()):
                teile.append(
                    f"<tr><td>{_e(police)}</td><td>{_e(groesse)}</td>"
                    f"<td>{_e(grund)}</td></tr>"
                )
        teile.append("</table>")

    fehlgeschlagene = [v for v in test["vertraege"] if not v["bestanden"]]
    teile.append("<h2>Fehlschläge und Befunde</h2>")
    if fehlgeschlagene:
        teile.append(
            "<table><tr><th>Police</th><th>Historientyp</th>"
            "<th>Anlässe</th><th>Befunde</th></tr>"
        )
        teile.extend(
            f"<tr><td>{_e(v['police_id'])}</td>"
            f"<td>{_e(v['historientyp'])}</td>"
            f"<td>{_e(', '.join(v['anlaesse']))}</td>"
            f"<td class='rot'>{_e('; '.join(v['befunde']))}</td></tr>"
            for v in fehlgeschlagene
        )
        teile.append("</table>")
    else:
        teile.append("<p>Keine.</p>")

    teile.append(
        "<h2>Einzelvergleiche</h2>"
        "<table><tr><th>Police</th><th>Historientyp</th>"
        "<th>Anlass</th><th>Monat</th><th>Größe</th><th>System</th>"
        "<th>Lieferung</th><th>Residuum</th><th>Urteil</th></tr>"
    )
    for v in test["vertraege"]:
        for p in v["pruefungen"]:
            urteil = (
                "<td class='gruen'>OK</td>" if p["ok"]
                else "<td class='rot'>ABWEICHUNG</td>"
            )
            teile.append(
                f"<tr><td>{_e(v['police_id'])}</td>"
                f"<td>{_e(v['historientyp'])}</td>"
                f"<td>{_e(p['anlass'])}</td>"
                f"<td class='zahl'>{p['monate']:d}</td>"
                f"<td>{_e(p['groesse'])}</td>"
                f"<td class='zahl'>{p['system']:.6f}</td>"
                f"<td class='zahl'>{p['erwartet']:.6f}</td>"
                f"<td class='zahl'>{p['residuum']:.6f}</td>{urteil}</tr>"
            )
    teile.append("</table>")

    teile.append("<h2>Transportsicherung (kein Teil des Urteils)</h2>")
    transport = test.get("transportsicherung")
    if transport:
        teile.append(
            "<p>Mitgelieferte Prüfsummen und Bindungen sichern den "
            "Transport der Lieferung. Sie werden hier ausgewiesen und "
            "fließen NICHT in das fachliche Urteil ein (ADR-010).</p>"
            "<table><tr><th>Schlüssel</th><th>Wert</th></tr>"
        )
        teile.extend(
            f"<tr><td>{_e(k)}</td><td>{_e(v)}</td></tr>"
            for k, v in sorted(transport.items())
        )
        teile.append("</table>")
    else:
        teile.append("<p>Keine Transportangaben mitgeliefert.</p>")

    system = test.get("system")
    if system:
        teile.append("<h2>Systemstand</h2><table>")
        teile.extend(
            f"<tr><th>{_e(k)}</th><td>{_e(v)}</td></tr>"
            for k, v in sorted(system.items())
        )
        teile.append("</table>")
    teile.append("</body></html>")
    return "\n".join(teile) + "\n"


def _build_parser() -> GateArgumentParser:
    parser = GateArgumentParser(
        gate_contract=CLI_CONTRACT,
        prog=f"python -m rechner_pipeline.gates.{COMMAND}",
        description=(
            "Vorlage fuer eine der drei aktuariellen Abnahmen: prueft das "
            "Ergebnis des Tests und rendert die Entscheidungsvorlage."
        ),
    )
    parser.add_argument(
        "--abnahme", default=None, choices=sorted(GATES),
        help="Welche Abnahme (A-M1 Stichtagstest, A-M2 Verlaufstest, "
             "A-M3 Geschaeftsvorfalltest). Muss zum Profil des Ergebnisses "
             "passen.",
    )
    parser.add_argument("--fall", default=None, help="Fall-Arbeitsbereich.")
    parser.add_argument(
        "--test", default=None,
        help="Testergebnis-JSON (Default: <fall>/abgeleitet/berichte/"
        "aktuartest.json).",
    )
    parser.add_argument("--titel", default=None, help="Berichtstitel.")
    parser.add_argument(
        "--bericht", default=None,
        help="Zielpfad des HTML-Berichts (Default: <fall>/abgeleitet/"
        "berichte/aktuartest.html).",
    )
    parser.add_argument("--repo-root", default=None)
    parser.add_argument("--diagnostics-dir", default=None)
    add_request_json_arg(parser)
    return parser


def main(argv: Optional[List[str]] = None):
    started_at = utc_now()
    args = parse_gate_args(_build_parser(), argv)

    fall = Path(args.fall).resolve() if args.fall else None
    diagnostics_dir = (
        Path(args.diagnostics_dir) if args.diagnostics_dir
        else (fall / "abgeleitet" / "diagnostics" if fall
              else Path.cwd() / "runs" / "diagnostics")
    )
    # Die Abnahme steht im Namen JEDES Artefakts — Testergebnis, Bericht
    # UND Gate-Ledger. Drei Tests je Fall wuerden sich sonst gegenseitig
    # ueberschreiben, und zwar unbemerkt: Der Ledger traegt den Namen aus
    # ``result.command``, nicht den hier gerechneten Zielpfad. Ein
    # A-M2-Lauf loeschte damit den gruenen A-M1-Beleg, auf dem der
    # Entscheid steht — auch bei einem blossen Aufruffehler, denn schon
    # der rote Startmarker wird unter diesem Namen geschrieben.
    #
    # A-M1 behaelt bewusst den nackten Kommandonamen: Unter ihm bindet
    # der Entscheid den Pflichtbeleg (gate_entscheid, fall.SCOPES).
    abnahme = args.abnahme or "A-M1"
    gate = GATES[abnahme]
    kennung = COMMAND if abnahme == "A-M1" else f"{COMMAND}-{abnahme}"
    fehlstart = begin_gate_ledger_attempt(
        command=kennung, gate=gate, gate_version=GATE_VERSION,
        diagnostics_dir=diagnostics_dir,
        repo_root=Path(args.repo_root) if args.repo_root else None,
        started_at=started_at,
        command_line=argv if argv is not None else sys.argv[1:],
    )
    if fehlstart is not None:
        return fehlstart

    def _finalize(result):
        return finalize_gate_ledger(result)

    def _usage(message: str, *, hints: Optional[List[str]] = None):
        return _finalize(build_result(
            command=kennung, gate=gate, gate_version=GATE_VERSION,
            exit_code=Exit.USAGE,
            errors=[{"code": "usage", "message": message}],
            repair_hints=list(hints or []),
        ))

    if not args.titel:
        return _usage("erforderlich: --titel")
    test_pfad = (
        Path(args.test) if args.test
        else (fall / "abgeleitet" / "berichte" / f"{kennung}.json"
              if fall else None)
    )
    if test_pfad is None:
        return _usage(
            "Testergebnis unbestimmt: --test angeben oder --fall setzen "
            "(dann <fall>/abgeleitet/berichte/aktuartest.json)"
        )
    bericht_pfad = (
        Path(args.bericht) if args.bericht
        else (fall / "abgeleitet" / "berichte" / f"{kennung}.html"
              if fall else None)
    )
    if bericht_pfad is None:
        return _usage(
            "Zielpfad des Berichts unbestimmt: --bericht angeben oder "
            "--fall setzen (dann <fall>/abgeleitet/berichte/"
            "aktuartest.html)"
        )
    ledger_ziel = (diagnostics_dir / f"{kennung}{GATE_LEDGER_SUFFIX}")
    belegte = {
        test_pfad.resolve(), bericht_pfad.resolve(), ledger_ziel.resolve()
    }
    if len(belegte) != 3:
        return _usage(
            "Pfadkollision: --test, --bericht und der Gate-Ledger "
            "muessen drei verschiedene Dateien sein"
        )
    if not test_pfad.is_file():
        return _usage(
            f"Testergebnis nicht gefunden: {test_pfad}",
            hints=[
                "Erst den aktuariellen Test fahren: Pruefauftraege je "
                "Vertrag bauen und qa.aktuarieller_test.pruefe_stichprobe "
                "als JSON persistieren (Skill: aktuartest-durchfuehren)."
            ],
        )

    try:
        test = json.loads(test_pfad.read_text(encoding="utf-8"))
    except (OSError, ValueError) as exc:
        return _finalize(build_result(
            command=kennung, gate=gate, gate_version=GATE_VERSION,
            exit_code=Exit.FILE_CONTRACT,
            errors=[{
                "code": "test_unlesbar",
                "message": f"Testergebnis nicht lesbar: {exc}",
            }],
            input_hashes=hash_files([test_pfad], missing_ok=True),
        ))

    # Fremd erzeugte oder beschaedigte JSONs duerfen die Nachrechnung
    # nicht zu einem Toolbox-Defekt (INTERNAL) machen: ein Typfehler in
    # den Daten ist eine Vertragsverletzung der DATEI.
    gemeldet = (test or {}).get("profil", {}).get("kennung") if isinstance(test, dict) else None
    if gemeldet is not None and gemeldet != abnahme:
        return _finalize(build_result(
            command=kennung, gate=gate, gate_version=GATE_VERSION,
            exit_code=Exit.FILE_CONTRACT,
            errors=[{
                "code": "test_contract",
                "message": (
                    f"Ergebnis gehoert zu {gemeldet}, gerendert werden soll "
                    f"aber {abnahme}. Ein Bericht unter falscher Abnahme "
                    "waere ein Beleg fuer etwas, das nicht geprueft wurde"
                ),
            }],
            paths={"test": str(test_pfad)},
        ))

    try:
        fehler = test_fehler(test)
    except (TypeError, ValueError, KeyError, AttributeError) as exc:
        fehler = [
            "Ergebnis strukturell unlesbar: "
            f"{type(exc).__name__}: {exc}"
        ]
    input_hashes = hash_files(
        [test_pfad] + ([fall / "fall.json"] if fall else []),
        base=fall, missing_ok=True,
    )
    if fehler:
        return _finalize(build_result(
            command=kennung, gate=gate, gate_version=GATE_VERSION,
            exit_code=Exit.FILE_CONTRACT,
            errors=[
                {"code": "test_contract", "message": f}
                for f in fehler[:50]
            ],
            input_hashes=input_hashes,
            paths={"test": str(test_pfad)},
        ))

    try:
        html = baue_bericht(titel=args.titel, test=test)
    except (TypeError, ValueError, KeyError) as exc:
        return _finalize(build_result(
            command=kennung, gate=gate, gate_version=GATE_VERSION,
            exit_code=Exit.FILE_CONTRACT,
            errors=[{
                "code": "test_contract",
                "message": (
                    "Ergebnis nicht renderbar: "
                    f"{type(exc).__name__}: {exc}"
                ),
            }],
            input_hashes=input_hashes,
            paths={"test": str(test_pfad)},
        ))
    bericht_pfad.parent.mkdir(parents=True, exist_ok=True)
    bericht_pfad.write_text(html, encoding="utf-8", newline="\n")

    summary = {
        "test_bestanden": bool(test["test_bestanden"]),
        "anzahl": test["anzahl"],
        "fehlgeschlagen": test["fehlgeschlagen"],
        "stichprobe_vollstaendig": bool(test["stichprobe_vollstaendig"]),
        "stichprobe": {
            k: test["stichprobe"][k]
            for k in ("profil", "umfang", "grundgesamtheit", "vollerhebung")
        },
        "max_abs_residuum": test["verteilung"].get("max_abs_residuum", 0.0),
        "belege": hash_files(
            [test_pfad, bericht_pfad], base=fall, missing_ok=False,
        ),
        # Renderer-Vertrag: mit diesen Eingaben ist der Bericht
        # deterministisch reproduzierbar — A-M1 rendert ihn bytegenau
        # neu, statt dem Ledger-Status zu glauben.
        "bericht_erzeugung": {"titel": args.titel},
    }
    paths = {"test": str(test_pfad), "bericht": str(bericht_pfad)}
    output_hashes = hash_files([bericht_pfad], base=fall)
    if test["test_bestanden"]:
        return _finalize(build_result(
            command=kennung, gate=gate, gate_version=GATE_VERSION,
            exit_code=Exit.OK, paths=paths, summary=summary,
            input_hashes=input_hashes, output_hashes=output_hashes,
        ))
    return _finalize(build_result(
        command=kennung, gate=gate, gate_version=GATE_VERSION,
        exit_code=Exit.GOLDEN_MASTER, paths=paths, summary=summary,
        input_hashes=input_hashes, output_hashes=output_hashes,
        errors=[
            {"code": "aktuartest_nicht_bestanden", "message": m}
            for m in (
                [f"{test['fehlgeschlagen']} von {test['anzahl']} "
                 "Vertraegen fehlgeschlagen"]
                if test["fehlgeschlagen"] else []
            ) + list(test["mengenbefunde"])
        ],
    ))


if __name__ == "__main__":  # pragma: no cover
    raise SystemExit(run_command(main))
