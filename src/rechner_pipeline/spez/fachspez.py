"""Fachspezifikation: das menschenlesbare A-Q1-Abnahmedokument (P7).

Deterministisch aus Spez + A-Box + Coverage generiert — Gliederung in
der Art der Zielkern-Tarifplaene, aber hier ist das Dokument
PROJEKTION der Daten, nie die Quelle: jede Zahl traegt ihre Herkunft
(Quelle + Fundstelle + Quellenlage), jeder Widerspruch steht mit beiden
Lesarten und dem Stand seiner Aufloesung im Text. Der Leser des Gates
A-Q1 entscheidet auf dieser Grundlage — nicht auf Code, nicht auf JSON.

Kein Markup-Ehrgeiz: Markdown, Tabellen, Klartext. Gerendert wird bei
Bedarf ueber die Doku-Engine (wie die Tarifplaene).

Knoten: klv
"""

from __future__ import annotations

from pathlib import Path
from typing import Dict, List

from rechner_pipeline.ontologie.aussage import Zustand
from rechner_pipeline.ontologie.coverage import coverage_bericht
from rechner_pipeline.ontologie.tbox import (
    ABox,
    PFLICHT_PARAMETER,
    Tarifgeneration,
)
from rechner_pipeline.spez.schema import TarifSpez

FACHSPEZ_VERSION = "0.1.0"

_FELD_LABELS = {
    "zins": "Rechnungszins",
    "tafel": "Sterbetafel",
    "alpha": "Abschlusskosten (Zillmer)",
    "beta1": "Inkassokosten",
    "gamma1": "Verwaltungskosten 1 (bpfl.)",
    "gamma2": "Verwaltungskosten 2",
    "gamma3": "Verwaltungskosten 3 (bfr.)",
    "policy_fee": "Stueckkosten p. a.",
    "stoab_satz": "Stornoabzug-Satz",
    "stoab_min": "Stornoabzug-Untergrenze",
    "stoab_max": "Stornoabzug-Obergrenze",
    "min_alter_flex": "flexible Phase: Mindestalter",
    "min_rlz_flex": "flexible Phase: Mindest-Restlaufzeit",
    "zillmer_dauer": "Zillmer-Amortisationsdauer",
    "ratzu_zw2": "Ratenzuschlag zw=2",
    "ratzu_zw4": "Ratenzuschlag zw=4",
    "ratzu_zw12": "Ratenzuschlag zw=12",
}


def _md(wert) -> str:
    """Zellinhalt Markdown-tabellensicher machen (Pipes, Zeilenumbrueche).

    Werte und Begruendungen stammen aus Quellen und Agenten — ein ``|``
    oder Zeilenumbruch darin wuerde die A-Q1-Tabellen zerlegen.
    """
    text = str(wert)
    return text.replace("|", "\\|").replace("\n", " ").replace("\r", " ")


def fachspez_pfad(fall: Path, generation: str) -> Path:
    name = generation.replace("/", "-")
    return fall / "abgeleitet" / "fachspez" / f"{name}.md"


def _gen(abox: ABox, gen_id: str) -> Tarifgeneration:
    return next(g for g in abox.generationen if g.id == gen_id)


def _quellenlage(aussage, arten: Dict[str, str]) -> str:
    quellen = sorted({
        arten.get(p.quelle_datei, "?") for p in aussage.provenienz
    })
    return "+".join(quellen) if quellen else "-"


def _fundstellen(aussage) -> str:
    return "; ".join(sorted({
        f"{p.quelle_datei.split('.')[0]}:{p.fundstelle}"
        for p in aussage.provenienz
    }))


def erzeuge_fachspez(spez: TarifSpez, abox: ABox) -> str:
    """Die Fachspezifikation als Markdown-Text (deterministisch)."""
    gen = _gen(abox, spez.generation)
    arten = {q.datei: q.art for q in gen.quellen}
    coverage = next(
        g for g in coverage_bericht(abox)["generationen"]
        if g["generation"] == gen.id
    )
    z: List[str] = []
    z.append(f"# Fachspezifikation {gen.name} (Produktfamilie KLV)")
    z.append("")
    z.append(
        f"> GENERIERT aus der A-Box des Falls `{abox.fall}` "
        f"(T-Box {abox.tbox_version}, Spez {spez.spez_version}, "
        f"Fachspez-Generator {FACHSPEZ_VERSION}). Dieses Dokument ist "
        "Projektion der belegten Aussagen — Aenderungen gehoeren in die "
        "Quellen bzw. die Diskrepanz-Aufloesung, nicht in den Text."
    )
    z.append("")

    z.append("## 1 Quellen und Provenienzbindung")
    z.append("")
    z.append("| Quelle | Art | SHA-256 |")
    z.append("|---|---|---|")
    for q in gen.quellen:
        z.append(f"| {q.datei} | {q.art} | `{q.sha256[:16]}...` |")
    z.append("")

    z.append("## 2 Struktur-Urteil (berechnet)")
    z.append("")
    u = spez.urteil
    z.append(f"Ergebnis: **{u.ergebnis}**"
             + (f" (Referenz: {u.referenz_generation})"
                if u.referenz_generation else ""))
    z.append("")
    for b in u.begruendung:
        z.append(f"- {b}")
    z.append("")

    if gen.dimensionen:
        z.append("## 3 Merkmalsdimensionen")
        z.append("")
        z.append("| Dimension | Auspraegungen |")
        z.append("|---|---|")
        for d in gen.dimensionen:
            z.append(f"| {d.name} ({d.id}) | {', '.join(d.auspraegungen)} |")
        z.append("")

    if spez.unisex:
        z.append("## 4 Unisex-Kalkulation")
        z.append("")
        anteil = int(spez.unisex[1:])
        z.append(
            f"Vorgabe **{spez.unisex}** (Maenneranteil {anteil} %); "
            "Quellenlage: "
            + (_quellenlage(gen.unisex, arten) if gen.unisex else "-")
            + ". Umsetzung als abgeleitete Mischtafel je Basis: "
            "`qx = min(1, f*qx_M + (1-f)*qx_F)` je Alter — Daten-Ableitung, "
            "keine Kern-Formelaenderung."
        )
        z.append("")
        z.append("| Abgeleitete Tafel | Basis M | Basis F | Maenneranteil |")
        z.append("|---|---|---|---|")
        for a in spez.tafel_ableitungen:
            z.append(f"| {a.name} | {a.basis_m} | {a.basis_f} "
                     f"| {a.maenneranteil} |")
        z.append("")

    z.append("## 5 Parametrierung je Merkmalskombination")
    z.append("")
    for zelle in spez.zellen:
        abox_zelle = next(
            (az for az in gen.zellen
             if f"{gen.id}/{az.id}" == zelle.knoten), None,
        )
        if abox_zelle is None:
            raise ValueError(
                f"Fachspez: Spez-Zelle {zelle.knoten!r} hat keine "
                "A-Box-Entsprechung — erst validate_spez klaeren"
            )
        titel = ", ".join(
            f"{k}={v}" for k, v in sorted(zelle.auspraegungen.items())
        ) or "einheitlich (keine Differenzierung)"
        z.append(f"### Zelle: {titel}")
        z.append("")
        z.append(f"Knoten: `{zelle.knoten}`")
        z.append("")
        z.append("| Parameter | Wert | Quellenlage | Fundstellen |")
        z.append("|---|---|---|---|")
        for feld in list(PFLICHT_PARAMETER) + sorted(
            set(zelle.model_point) - set(PFLICHT_PARAMETER)
        ):
            if feld not in zelle.model_point:
                continue
            aussage = abox_zelle.parameter.get(feld)
            label = _FELD_LABELS.get(feld, feld)
            wert = zelle.model_point[feld]
            if aussage is not None and aussage.zustand is Zustand.BELEGT:
                z.append(
                    f"| {label} (`{feld}`) | {_md(wert)} "
                    f"| {_quellenlage(aussage, arten)} "
                    f"| {_md(_fundstellen(aussage))} |"
                )
            else:
                z.append(f"| {label} (`{feld}`) | {_md(wert)} | ? | ? |")
        z.append("")

    z.append("## 6 Coverage (Pflichtumfang der T-Box)")
    z.append("")
    z.append(
        f"Belegt: {coverage['zaehler']['belegt']} von "
        f"{coverage['pflicht_gesamt']} Pflichtfeldern "
        f"({coverage['belegt_quote']:.0%}); "
        f"gesucht-nicht-gefunden: {coverage['zaehler']['nicht_belegt']}; "
        f"von der Extraktion uebersehen: "
        f"{coverage['zaehler']['fehlt_in_extraktion']}; "
        f"widerspruechlich: {coverage['zaehler']['widerspruechlich']}."
    )
    z.append("")

    z.append("## 7 Diskrepanzen zwischen den Quellen")
    z.append("")
    relevante = [
        d for d in abox.diskrepanzen
        if d.knoten == gen.id or d.knoten.startswith(gen.id + "/")
    ]
    if not relevante:
        z.append("Keine.")
    else:
        z.append("| Knoten/Feld | Lesarten | Status | Entscheidung |")
        z.append("|---|---|---|---|")
        for d in relevante:
            lesarten = " vs. ".join(
                f"{_md(l.wert)} ({_quellenlage(l, arten)})" for l in d.lesarten
            )
            if d.entscheidung is None:
                entscheid = "OFFEN"
            else:
                e = d.entscheidung
                entscheid = (
                    f"{_md(e.gewaehlter_wert)} — {_md(e.entscheider)}"
                    + (" **[VORLAEUFIG — A-Q1-Entscheidung steht aus]**"
                       if e.vorlaeufig else "")
                )
            z.append(f"| `{d.knoten.split('/', 2)[-1]}#{d.feld}` "
                     f"| {lesarten} | {d.status} | {entscheid} |")
    z.append("")

    vorlaeufige = [
        d for d in relevante
        if d.entscheidung is not None and d.entscheidung.vorlaeufig
    ]
    if vorlaeufige:
        z.append(
            f"**Achtung:** {len(vorlaeufige)} Aufloesung(en) sind "
            "VORLAEUFIG (Arbeitsstand fuer den Golden-Master-Lauf; der "
            "GM reproduziert den gelieferten Rechner). Die fachliche "
            "Entscheidung ist Gegenstand dieses Gates — ohne sie gibt es "
            "keine menschliche Abnahme (der P9-Snapshot blockt)."
        )
        z.append("")

    z.append("## 8 Tafel-Anforderungen an den Kern")
    z.append("")
    if spez.tafel_importe:
        z.append("Importe (aus dem Quell-Rechner, mit Provenienz im XML): "
                 + ", ".join(f"`{n}`" for n in spez.tafel_importe))
    if spez.tafel_ableitungen:
        z.append("")
        z.append("Ableitungen: "
                 + ", ".join(f"`{a.name}`" for a in spez.tafel_ableitungen))
    if not spez.tafel_importe and not spez.tafel_ableitungen:
        z.append("Keine — alle Tafeln sind im Kern vorhanden.")
    z.append("")

    z.append("## 9 Erweiterungsstellen")
    z.append("")
    if spez.erweiterungsstellen:
        for e in spez.erweiterungsstellen:
            z.append(f"- {e.id} ({e.status}): {e.beschreibung}")
    else:
        z.append(
            "Keine — die Generation ist vollstaendig als Parametrierung "
            f"des Rueckgrats `{spez.backbone}` ausgedrueckt."
        )
    z.append("")

    z.append("## 10 Quellnamen-Mapping (fremde Benennungslogik)")
    z.append("")
    if gen.quellnamen:
        z.append("| Quellname | Zielfeld |")
        z.append("|---|---|")
        for name in sorted(gen.quellnamen):
            z.append(f"| {_md(name)} | `{_md(gen.quellnamen[name])}` |")
    else:
        z.append("Keines erfasst.")
    z.append("")

    z.append("## 11 Anmerkungen der Extraktion (ohne Schemafeld)")
    z.append("")
    anmerkungen = list(getattr(gen, "anmerkungen", None) or [])
    if anmerkungen:
        for a in anmerkungen:
            z.append(f"- {_md(a)}")
        z.append("")
        z.append(
            "Diese Beobachtungen der Extraktion haben KEIN Schemafeld — "
            "sie sind weder belegt noch widerlegt und deshalb menschlich "
            "zu wuerdigen (Herkunft in eckigen Klammern, soweit erfasst)."
        )
    else:
        z.append("keine")
        z.append("")
        z.append(
            "Auch die Abwesenheit ist eine Aussage: die Extraktion hat "
            "nichts ausserhalb des Schemas festgehalten."
        )
    z.append("")
    return "\n".join(z) + "\n"


def speichere_fachspez(spez: TarifSpez, abox: ABox, fall: Path) -> Path:
    pfad = fachspez_pfad(fall, spez.generation)
    pfad.parent.mkdir(parents=True, exist_ok=True)
    pfad.write_text(erzeuge_fachspez(spez, abox), encoding="utf-8")
    return pfad
