"""Abzugsabgleich Zins und Haus-beta1 im Fall — AD-HOC-SKRIPT DES AGENTEN, KEIN SYSTEMWERKZEUG.

Kein Kommando des Pakets, kein Gate. Rechnet nur ueber ``qa.abzugsabgleich`` (``gleiche_ab``, ``pruefe_lesart``);
Toleranzen unveraendert. Schreibt nur die Beleg-Datei; loest nichts auf, aendert die A-Box nicht.

Eingaben (nur aus dem Fall): transformierte Zeilen, A-Box (belegte Parameter der Zellen; die Lesarten der
Diskrepanzen zu zins und beta1), registrierte Vorgeschichte, ``eingang.json``.

Aufruf (aus der Wurzel des Baums, mit dem Paket, das rechnen soll, auf PYTHONPATH):
    python abzugsabgleich_fall.py --fall faelle/baldrian-klv-tg2015-fall3 --out <beleg.json> [--tafeln-quelle <text>]
"""
from __future__ import annotations

import argparse
import collections
import csv
import hashlib
import json
import subprocess
import sys
from pathlib import Path

from rechner_pipeline import fall as fall_mod
from rechner_pipeline.kern import __version__ as KERN_VERSION
from rechner_pipeline.models.bestand import model_point_kwargs
from rechner_pipeline.ontologie.abox import lade
from rechner_pipeline.qa import abzugsabgleich as aa
from rechner_pipeline.qa.abzugsabgleich import Lesart, VertragsBeleg, gleiche_ab, pruefe_lesart

AKTEUR = "claude-sonnet-5-5/abzugsabgleich-fall@{sha}"
GEPRUEFTE_FELDER = ("zins", "beta1")
ZEILEN = "abgeleitet/transformation/baldrian_bestandsabzug_2026-01-01.zeilen.json"
VORGESCHICHTE = "baldrian_gevo_metadaten.csv"


def sha256(pfad) -> str:
    return hashlib.sha256(Path(pfad).read_bytes()).hexdigest()


def git(*args: str) -> str:
    return subprocess.run(["git", *args], capture_output=True, text=True, check=True).stdout.strip()


def zahl(x):
    return float(x)


def urteil_dict(u):
    return {
        "wert": u["wert"], "quelle_art": u["quelle_art"], "geprueft": u["geprueft"], "verletzt": u["verletzt"],
        "passt": u["passt"], "quote_stuetzend": u["quote_stuetzend"],
        "max_relative_abweichung": u["max_relative_abweichung"],
        "max_relative_abweichung_verletzt": u["max_relative_abweichung_verletzt"],
        "verletzende_belege": u["verletzende_belege"],
    }


def main() -> int:
    p = argparse.ArgumentParser()
    p.add_argument("--fall", required=True)
    p.add_argument("--out", required=True)
    p.add_argument("--tafeln-quelle", default="")
    args = p.parse_args()
    fall = Path(args.fall).resolve()
    skript = Path(__file__).resolve()

    # --- Eingaben, nur aus dem Fall (Integritaet ueber das Fallregister) ---
    vorgeschichte_pfad = fall_mod.eingang_datei(fall, VORGESCHICHTE)
    zeilen_pfad = fall / ZEILEN
    abox_pfad = fall / "abgeleitet" / "abox" / "abox.json"
    eingang_json = fall / "eingang.json"
    zeilen = json.loads(zeilen_pfad.read_text(encoding="utf-8"))
    abox = lade(fall)
    gen = abox.generationen[0]
    art_je_datei = {q.datei: q.art for q in gen.quellen}
    unisex = str(gen.unisex.wert) if gen.unisex is not None else None

    hist = collections.defaultdict(list)
    with Path(vorgeschichte_pfad).open(encoding="utf-8", newline="") as f:
        for r in csv.DictReader(f, delimiter=";"):
            hist[r["POLNR"]].append(r["GEVO"])
    rein = [z for z in zeilen if z["police_id"] not in hist and z["brutto_jahresbeitrag"] > 0]

    # --- Modellpunkte der Zellen aus den BELEGTEN Parametern der A-Box; strittige Felder: Lesarten ---
    zellen = {}
    for z in gen.zellen:
        s = {}
        strittig = {}
        for feld, a in z.parameter.items():
            if a.zustand.value == "belegt":
                s[feld] = a.wert
            elif feld in GEPRUEFTE_FELDER:
                strittig[feld] = None
        basis = str(s["tafel"])
        s["tafel"] = f"{basis}_{unisex}" if unisex else basis
        zellen[z.id] = (dict(z.auspraegungen), s, strittig)
    lesarten = {}  # (zell-id, feld) -> [(wert, art, fundstelle)]
    for d in abox.diskrepanzen:
        zid = d.knoten.split("/", 2)[2]
        if d.feld in GEPRUEFTE_FELDER:
            ls = []
            for l in d.lesarten:
                prov = l.provenienz[0]
                ls.append((l.wert, art_je_datei[prov.quelle_datei], prov.quelle_datei, prov.fundstelle))
            lesarten[(zid, d.feld)] = ls

    def lesart_wert(zid, feld, art):
        t = [w for w, a, _, _ in lesarten[(zid, feld)] if a == art]
        if len(t) != 1:
            raise SystemExit(f"{zid}/{feld}: keine eindeutige Lesart der Art {art}")
        return t[0]

    def belege(zid, gruppe, ueber):
        _, s, strittig = zellen[zid]
        mp_basis = dict(s)
        # strittige Felder: Meldungs-Lesart als Grundstellung (wie Messung 04), Ueberschreibung gewinnt
        for feld in strittig:
            mp_basis[feld] = lesart_wert(zid, feld, "tarifmeldung")
        mp_basis.update(ueber)
        return [VertragsBeleg(
            police_id=z["police_id"], model_point=model_point_kwargs(z, mp_basis),
            vertragsjahr=z["monate_ta"] // 12,
            erwartet={"BJB": z["brutto_jahresbeitrag"], "kVx_MRV": z["dk_ta"]}) for z in gruppe]

    ergebnis = []
    for zid in sorted(zellen):
        ausp, s, strittig = zellen[zid]
        gruppe = [z for z in rein if z["status"] == ausp["status"] and z["tarifart"] == ausp["tarifart"]]
        eintrag = {"zelle": zid, "auspraegungen": ausp, "vertraege": len(gruppe), "pruefungen": []}
        for feld in sorted(f for (zz, f) in lesarten if zz == zid):
            lt = [(w, a) for w, a, _, _ in lesarten[(zid, feld)]]
            if len(lt) != 2:
                raise SystemExit(f"{zid}/{feld}: genau zwei Lesarten erwartet")
            u = gleiche_ab(feld, [Lesart(w, a) for w, a in lt], belege(zid, gruppe, {}))
            eintrag["pruefungen"].append({
                "feld": feld,
                "lesarten": [{"wert": w, "quelle_art": a, "quelle_datei": qd, "fundstelle": fs}
                             for w, a, qd, fs in lesarten[(zid, feld)]],
                "belegte_werte_der_anderen_strittigen_felder": "Lesart der Tarifmeldung (Grundstellung)",
                "automatisch_aufloesbar": u["automatisch_aufloesbar"],
                "menschlich_erforderlich": u["menschlich_erforderlich"],
                "gewaehlter_wert": u["gewaehlter_wert"], "begruendung_werkzeug": u["begruendung"],
                "urteile": [urteil_dict(x) for x in u["urteile"]],
            })
        # Rechner-Lesart GESAMT: alle strittigen Felder der Zelle auf der Rechner-Lesart
        felder = sorted(f for (zz, f) in lesarten if zz == zid)
        if len(felder) > 1:
            ueber = {f: lesart_wert(zid, f, "tarifrechner") for f in felder}
            erstes = felder[0]
            r = pruefe_lesart(erstes, Lesart(ueber[erstes], "tarifrechner"),
                              belege(zid, gruppe, {k: v for k, v in ueber.items() if k != erstes}))
            eintrag["rechner_lesart_gesamt"] = {"felder": ueber, "urteil": urteil_dict(r)}
        ergebnis.append(eintrag)

    commit = git("rev-parse", "HEAD")
    dirty = git("status", "--porcelain", "--", "src", "configs")
    beleg = {
        "kopf": {
            "werkzeug": "Ad-hoc-Skript des Agenten, kein Systemwerkzeug (kein Kommando des Pakets, kein Gate)",
            "skript": {"pfad": str(skript.relative_to(Path.cwd())) if skript.is_relative_to(Path.cwd()) else str(skript),
                       "sha256": sha256(skript)},
            "akteur": AKTEUR.format(sha=commit[:7]),
            "rechnet_ueber": "rechner_pipeline.qa.abzugsabgleich (gleiche_ab, pruefe_lesart); Toleranzen: REL_TOL "
                             f"{aa.REL_TOL!r}, ABS_TOL {aa.ABS_TOL!r} (unveraendert)",
            "eingaben_sha256": {
                str(zeilen_pfad.relative_to(fall)): sha256(zeilen_pfad),
                str(abox_pfad.relative_to(fall)): sha256(abox_pfad),
                "eingang.json": sha256(eingang_json),
                "eingang/" + VORGESCHICHTE: sha256(vorgeschichte_pfad),
            },
            "systemstand": {
                "kern_version": KERN_VERSION, "git_commit_baum": commit,
                "baum_src_configs_geaendert": bool(dirty),
                "kern_tafeln_xml_sha256": sha256(Path(sys.modules["rechner_pipeline.kern"].__file__).parent / "tafeln.xml"),
                "tafeln_quelle": args.tafeln_quelle,
            },
            "grenzen": [
                f"Gepruefte Belege: {len(rein)} Vertraege OHNE Vorgeschichte (kein ERH, PEX, RED) mit laufendem Beitrag "
                f"(JBRUTTO > 0) aus {len(zeilen)} Zeilen; je Vertrag zwei Werte (BJB gegen JBRUTTO, kVx_MRV gegen DECKKAP am Jahrestag).",
                "Vertraege mit Erhoehungen sind ueber die Dynamikprobe (Messung 04) gestuetzt, nicht hier; Vertraege ohne Beitrag "
                "haben keine Beitragsgleichung.",
                "Strittige Felder: Beim Pruefen eines Felds steht das andere strittige Feld auf der Lesart der Tarifmeldung; "
                "die Rechner-Lesart gesamt ist gesondert ausgewiesen.",
            ],
            "hinweis": "Dieser Beleg ersetzt die Aufloesung der Diskrepanzen nicht; sie ist menschlich (A-Q1). "
                       "Eine verworfene Meldungs-Lesart gaebe immer an den Menschen (harte Regel).",
        },
        "zeilen_gesamt": len(zeilen),
        "vertraege_gepruefte": len(rein),
        "zellen": ergebnis,
    }
    Path(args.out).parent.mkdir(parents=True, exist_ok=True)
    Path(args.out).write_text(json.dumps(beleg, indent=1, sort_keys=True, ensure_ascii=False) + "\n", encoding="utf-8")
    print(f"abzugsabgleich_fall: {len(rein)} Vertraege, {len(ergebnis)} Zellen -> {args.out}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
