"""Ende-zu-Ende: gelieferte Vertraege mit Alt-Herabsetzung nach dem Beitragsende.

Entscheid des Maintainers vom 2026-10-01: Der Migrationszugang muss
gelieferte Vertraege, die im ausfinanzierten Nachlauf (``t <= Jahr < n``)
abgesetzt wurden, in JEDER Generation integrieren ("ein Problem des Ziels,
nicht der Migration"). Beitragsherabsetzung und Teilkuendigung sind zwei
Geschaeftsvorfaelle (ADR-023); eine gelieferte Absetzung nach t war eine
Teilkuendigung (Annahme A2, klv.md 7.2): Der gelieferte Vertrag ist der
zustandslose Vertrag mit der gelieferten Summe (Einzelfall), oder seine
Grundsumme traegt den Anteil f und die Erhoehungsscheiben laufen
unveraendert (Serie; f kommt als registrierte Auskunft, die die Struktur
DECKT und den Vertrag zur Pflichtschicht der Abnahmen macht).

Fertig ist das erst an der Naht. Dieser Test faehrt die GANZE Kette des
zweiten Baldrian-Laufs (``tests/test_baldrian2_e2e.py``) — Transformation,
Uebernahme mit Anfangszustand, Verankerung, P-B1, aktuarieller Test A-M1 bis
A-M3, Migrationscontrolling, Fortschreibung, P-B1, Fuehrungsprobe, Berichte,
Migrationsabnahme — je einmal fuer eine Generation mit ``prospektiv``,
``mit_abzug`` und ``teilkuendigung``, und danach eine Fortschreibung, in der
die Fuehrung selbst im Nachlauf teilkuendigt (eigener Strom, eigene Rate),
mit Abschluss.

**Die Angriffe des Pruefers** (Befunde B1, B2 zur gebauten Regel A): Eine
Serie ohne Auskunft, eine Absetzung nach dem Stichtag oder am Ablauf, eine
Absetzung vor t ohne Wirkung — vorher lief jede davon mit Exit 0 durch die
ganze Kette. Jetzt verweigert die Uebernahme benannt.

**Die Lieferung.** Der Schnitt des zweiten Laufs ohne die Policen, deren
Vorgeschichte oder Pruefzeitraum eine Herabsetzung VOR dem Beitragsende
traegt (unter prospektiv/mit Abzug waere das ein geteilter Vertrag, den die
Uebernahme benannt nicht freischaltet — eine andere Frage), dazu drei
ausfinanzierte Vertraege derselben Tarifzelle (Beginn 01.01.2015, n = 18,
t = 8):

* 7100001 ohne Vorgeschichte (Gegenstueck),
* 7100002 mit Herabsetzung am 01.01.2024 (Jahr 9 >= t),
* 7100003 mit Erhoehungen 2017 und 2019 und Herabsetzung am 01.01.2024,
  fortgefuehrter Anteil 0,6 als registrierte Auskunft.

Ihre Erwartungswerte (Deckungskapital in beiden Abzuegen, A-M1, A-M2) sind
hier aus Kern-Primitiven gerechnet — dem zustandslosen Vertrag mit der
gelieferten Summe bzw. Grund f x G plus unveraenderten Scheiben
(``Rechenkern``, ``erhoehungs_scheibe``, ``vertrags_monatsreserve``), ohne
den Herabsetzungs- und Uebernahmepfad. Das ist die Zusage der
Teilkuendigung (Bedingungswerk Ziffer 6), nicht ein Wert einer abgebenden
Gesellschaft; gegenstand dieses Tests ist, dass die Kette den Fall TRAEGT.
Die Gegenprobe ist differentiell: 7100002 und 7100001 sind in jedem Beleg
gleich.

Knoten: klv/tg2015
"""

from __future__ import annotations

import csv
import dataclasses
import hashlib
import io
import json
import shutil
from pathlib import Path

import pytest

from rechner_pipeline.bestand import cli_abschluss, cli_fortschreibung, cli_report
from rechner_pipeline.bestand.parquet_io import read_portfolio
from rechner_pipeline.fall import anlegen, registrieren
from rechner_pipeline.gates import (
    abnahmebericht,
    aktuartest_lauf,
    bestand_uebernehmen,
    bestand_validate,
    fuehrungsprobe,
    migrationssuite_lauf,
    transformation_anwenden,
    verankerung_belegen,
)
from rechner_pipeline.gates.migrationssuite_lauf import _zelle
from rechner_pipeline.kern import ModelPoint, Rechenkern, vertrags_monatsreserve
from rechner_pipeline.kern.beitragsreduktion import MIT_ABZUG, PROSPEKTIV, TEILKUENDIGUNG
from rechner_pipeline.kern.rechenkern import erhoehungs_scheibe
from rechner_pipeline.models.bestand import model_point_kwargs
from rechner_pipeline.spez.validierung import lade_spez_aus_bytes
from tests.e2e_fixture import zellen_config
from tests.tarifregeln_testhelfer import spez_variante
from tests.test_baldrian2_e2e import (
    ABZUG_1,
    ABZUG_2,
    ANKER,
    FIXTURE,
    GENERATION,
    KANDIDATEN,
    METADATEN,
    PROTOKOLL,
    REPO_ROOT,
    STICHPROBE,
    STICHTAG_1,
    STICHTAG_2,
    TARIF_GENERATION,
)

AUSKUNFT = "regel_a_red_anteile_auskunft.csv"
OHNE, MIT, SERIE = "7100001", "7100002", "7100003"
NEU = (OHNE, MIT, SERIE)
#: Vorlage der neuen Zeilen: Tarifzelle, Geschlecht, Geburtstag, Beginn und
#: Zahlweise wie 7000001 — nur Laufzeit, Beitragsdauer und Summen anders.
VORLAGE = "7000001"
N_NEU, T_NEU = 18, 8
F = 0.6
#: Die Serie: Grundsumme G = 50.000 vor der Herabsetzung, Dynamik 5 Prozent
#: in den Jahren 2 und 4, Herabsetzung im Jahr 9: Grund danach 30.000,
#: Scheiben 2.500 und 2.625, ERLSUMME 35.125.
G_SERIE = 50_000.0
SCHEIBEN_SERIE = ((2, 2_500.0), (4, 2_625.0))
SUMME = {OHNE: 30_000.0, MIT: 30_000.0, SERIE: 35_125.0}
VORGESCHICHTE_NEU = (
    (MIT, "RED", "01.01.2024"),
    (SERIE, "ERH", "01.01.2017"),
    (SERIE, "ERH", "01.01.2019"),
    (SERIE, "RED", "01.01.2024"),
)
MONATE_TA, MONATE_2 = 132, 144


def _lies(pfad: Path):
    with pfad.open(encoding="utf-8") as datei:
        leser = csv.DictReader(datei, delimiter=";")
        return list(leser.fieldnames or []), list(leser)


def _schreib(pfad: Path, spalten, zeilen) -> None:
    puffer = io.StringIO()
    schreiber = csv.DictWriter(puffer, fieldnames=spalten, delimiter=";",
                               lineterminator="\n")
    schreiber.writeheader()
    schreiber.writerows(zeilen)
    pfad.write_text(puffer.getvalue(), encoding="utf-8")


def _ausgeschlossen() -> set:
    """Policen mit einer Herabsetzung in Vorgeschichte oder Pruefzeitraum."""
    raus = set()
    for name in (METADATEN, PROTOKOLL):
        for z in _lies(FIXTURE / name)[1]:
            if z["GEVO"] == "RED":
                raus.add(z["POLNR"])
    return raus


def _kerne(spez):
    """Die Zusage je neuem Vertrag, aus Kern-Primitiven: (Grund, Scheiben)."""
    zeile = {"entry_age": 49, "sex": "F", "duration": N_NEU,
             "premium_duration": T_NEU, "sum_insured": 1.0, "zahlweise": 12}
    felder = dict(_zelle(spez, {"status": "nichtraucher", "tarifart": "haus"}).model_point)
    basis = ModelPoint(**model_point_kwargs(zeile, felder))
    aus = {}
    for pid in (OHNE, MIT):
        aus[pid] = (Rechenkern(dataclasses.replace(basis, sum_insured=SUMME[pid])), [])
    grund_mp = dataclasses.replace(basis, sum_insured=F * G_SERIE)
    scheiben = [(j, Rechenkern(erhoehungs_scheibe(grund_mp, j, vs, gamma1_uebernehmen=True)))
                for j, vs in SCHEIBEN_SERIE]
    aus[SERIE] = (Rechenkern(grund_mp), scheiben)
    return aus


def _werte(kerne, pid: str, monate: int) -> dict:
    grund, scheiben = kerne[pid]
    m = vertrags_monatsreserve(grund, scheiben, monate, stoab_je_baustein=True)
    return {"kVx_MRV": round(m.vx_mrv, 2), "RKW": round(m.rkw, 2), "BJB": 0.0}


def baue_lieferung(ziel: Path, vorgeschichte=VORGESCHICHTE_NEU,
                   auskunft=((MIT, "01.01.2024", F), (SERIE, "01.01.2024", F))) -> None:
    """Die Lieferung: Schnitt ohne Herabsetzung vor t plus die drei Neuen;
    Vorgeschichte und Auskunft der Neuen sind fuer die Angriffe waehlbar."""
    ziel.mkdir(parents=True, exist_ok=True)
    raus = _ausgeschlossen()
    spez = lade_spez_aus_bytes((FIXTURE / "klv-tg2015.spez.json").read_bytes())
    kerne = _kerne(spez)

    for name, monate in ((ABZUG_1, MONATE_TA), (ABZUG_2, MONATE_2)):
        spalten, zeilen = _lies(FIXTURE / name)
        behalten = [z for z in zeilen if z["POLNR"] not in raus]
        vorlage = next(z for z in zeilen if z["POLNR"] == VORLAGE)
        for pid in NEU:
            neu = dict(vorlage)
            neu.update(POLNR=pid, ABLAUF="01.01.2033", BZDAUER=str(T_NEU),
                       ERLSUMME=f"{SUMME[pid]:.2f}", JBRUTTO="0.00",
                       DECKKAP=f"{_werte(kerne, pid, monate)['kVx_MRV']:.2f}")
            behalten.append(neu)
        _schreib(ziel / name, spalten, behalten)

    spalten, zeilen = _lies(FIXTURE / METADATEN)
    zeilen = [z for z in zeilen if z["POLNR"] not in raus]
    zeilen += [{"POLNR": p, "GEVO": g, "DATUM": d} for p, g, d in vorgeschichte]
    _schreib(ziel / METADATEN, spalten, zeilen)

    spalten, zeilen = _lies(FIXTURE / PROTOKOLL)
    _schreib(ziel / PROTOKOLL, spalten, [z for z in zeilen if z["POLNR"] not in raus])

    _schreib(ziel / AUSKUNFT, ["POLNR", "GEVO", "DATUM", "ANTEIL", "BEZUG"], [
        {"POLNR": p, "GEVO": "RED", "DATUM": d, "ANTEIL": str(a),
         "BEZUG": "Auskunft der Quelle zur Absetzung nach dem Beitragsende"}
        for p, d, a in auskunft])

    def _eintraege(name: str, punkte_neu) -> None:
        d = json.loads((FIXTURE / name).read_text(encoding="utf-8"))
        d["vertraege"] = [v for v in d["vertraege"] if str(v["police_id"]) not in raus]
        for pid in (punkte_neu and NEU or ()):
            d["vertraege"].append({
                "beitragsfrei_seit_jahr": None,
                "historientyp": "ohne_vorgeschichte" if pid == OHNE else "reduziert",
                "monate_ta": MONATE_TA, "police_id": pid,
                "punkte": [{"anlass": anlass, "erwartet": _werte(kerne, pid, m),
                            "groessen": ["kVx_MRV", "RKW", "BJB"], "monate": m}
                           for anlass, m in punkte_neu]})
        if "stichprobe" in d:
            ids = [str(v["police_id"]) for v in d["vertraege"]]
            d["stichprobe"]["police_ids"] = ids
            d["stichprobe"]["grundgesamtheit"] = len(ids)
        (ziel / name).write_text(json.dumps(d, ensure_ascii=False, indent=1), encoding="utf-8")

    _eintraege(ANKER, (("uebernahme", MONATE_TA), ("fortschreibung", MONATE_2)))
    _eintraege("baldrian_erwartungswerte_verlauf.json",
               (("verlauf", MONATE_TA + 60), ("verlauf", 12 * N_NEU)))
    _eintraege("baldrian_erwartungswerte_geschaeftsvorfaelle.json", ())

    s = json.loads((FIXTURE / STICHPROBE).read_text(encoding="utf-8"))
    for schluessel in ("A-M1_A-M2", "A-M3"):
        ids = [p for p in s[schluessel]["police_ids"] if p not in raus]
        if schluessel == "A-M1_A-M2":
            ids += list(NEU)
        s[schluessel].update(police_ids=ids, grundgesamtheit=len(ids), umfang=len(ids))
    (ziel / STICHPROBE).write_text(json.dumps(s, ensure_ascii=False, indent=1), encoding="utf-8")


def _flags(verfahren: str, kandidaten: bool = True) -> list:
    # Das Verfahren ist eine Regel des Tarifs und der Quelle und steht seit
    # dem Nachtrag zu ADR-024 in der Spez (``fahre_kette`` legt die Variante
    # je Verfahren); am Aufruf bleiben Auskunft und Arbeitsannahme. Die
    # Tarifzelle ist die des uebernommenen Tarifs: Seine Teilkuendigung
    # kuendigt nur die Grundversicherung (Entscheid B1 vom 2026-10-01) — so
    # traegt es die Spez der Fixture.
    flags = ["--red-anteile-datei", AUSKUNFT]
    for k in (KANDIDATEN if kandidaten else ()):
        flags += ["--red-anteil-kandidat", k]
    return flags


def fahre_kette(basis: Path, verfahren: str, *, bis_uebernahme: bool = False,
                kandidaten: bool = True, **lieferung_kw) -> dict:
    """Die Kette des zweiten Laufs auf der Lieferung, Exit-Codes gesammelt."""
    lieferung = basis / "lieferung"
    baue_lieferung(lieferung, **lieferung_kw)
    fall = basis / "fall"
    anlegen(fall, scope="bestand")
    for pfad in sorted(lieferung.iterdir()):
        registrieren(fall, pfad)

    ab = fall / "abgeleitet"
    # Die Spez der Fixture, mit dem Verfahren dieser Kette als belegte Regel
    # des Tarifs UND Lesart der Quelle (vorher: --red-verfahren an jedem
    # Kommando).
    spez_variante(FIXTURE / "klv-tg2015.spez.json", fall, GENERATION,
                  tarifwerk={"red_verfahren": verfahren},
                  quellverfahren={"red_verfahren": verfahren})
    spec = ab / "transformation" / "abzug.spec.json"
    spec.parent.mkdir(parents=True, exist_ok=True)
    # Dieselbe Feldabbildung, gebunden an DIESEN Abzug (die Spec bindet die
    # Bytes ihrer Quelle; der Schnitt ist ein anderer).
    spez_json = json.loads((FIXTURE / "transformation.spec.json").read_text(encoding="utf-8"))
    spez_json["quelle_sha256"] = hashlib.sha256((lieferung / ABZUG_1).read_bytes()).hexdigest()
    spez_json["anmerkungen"] = list(spez_json["anmerkungen"]) + [
        "Fuer den Test der Alt-Absetzung nach t auf den gekuerzten Abzug mit drei neuen "
        "Vertraegen gebunden; die Feldabbildung ist unveraendert."]
    spec.write_text(json.dumps(spez_json, ensure_ascii=False, indent=1), encoding="utf-8")
    zeilen = ab / "transformation" / "zeilen.json"
    ergebnis = ab / "transformation" / "ergebnis.json"
    bestand, nach = ab / "bestand", ab / "bestand-nach"
    config_pfad = ab / "bestand-config.toml"
    schichten = ab / "schichten" / "verankerung_schichten.json"
    berichte = ab / "berichte"
    codes = {}

    codes["transformation"] = transformation_anwenden.main([
        "--fall", str(fall), "--spec", str(spec), "--anwenden", "--zeilen", str(zeilen)])
    codes["uebernahme"] = bestand_uebernehmen.main([
        "--fall", str(fall), "--zeilen", str(zeilen),
        "--tarif-generation", TARIF_GENERATION, "--stichtag", STICHTAG_1,
        "--vorgeschichte", METADATEN, "--generation-spez", GENERATION,
        "--anfangszustand", "materialisieren", "--anker-erwartungswerte", ANKER,
        "--out-dir", str(bestand)] + _flags(verfahren, kandidaten))
    if bis_uebernahme:
        return {"codes": codes, "fall": fall, "bestand": bestand}
    codes["transformation_ziel"] = transformation_anwenden.main([
        "--fall", str(fall), "--spec", str(spec), "--anwenden", "--zeilen", str(zeilen),
        "--ziel", str(bestand / "bestand.parquet"), "--ergebnis", str(ergebnis)])
    config_pfad.write_text(zellen_config(
        (bestand / "generation-zellen.toml").read_text("utf-8"),
        name=TARIF_GENERATION, knoten=GENERATION), encoding="utf-8")
    codes["verankerung"] = verankerung_belegen.main([
        "--fall", str(fall), "--repo-root", str(REPO_ROOT), "--generation", GENERATION,
        "--zeilen", str(zeilen),
        "--vorgeschichte", METADATEN, "--anker-erwartungswerte", ANKER,
        "--config", str(config_pfad), "--stichtag", STICHTAG_1] + _flags(verfahren))

    def pb1(lauf: Path, portfolio: str, bis: str, cfg: Path, diag: str):
        red = (["--reduktionen", str(lauf / "reduktionen.parquet")]
               if (lauf / "reduktionen.parquet").is_file() else [])
        return bestand_validate.main(red + [
            "--portfolio", str(lauf / portfolio),
            "--historie", str(lauf / "historie.parquet"),
            "--ledger", str(lauf / "ledger.parquet"),
            "--scheiben", str(lauf / "scheiben.parquet"),
            "--merkmale", str(lauf / "merkmale.parquet"),
            "--schichten", str(lauf / "schichten.parquet"),
            "--verankerung", str(lauf / "verankerung.parquet"),
            "--config", str(cfg), "--bis", bis,
            "--manifest", str(lauf / "laufmanifest.json"),
            "--repo-root", str(REPO_ROOT), "--diagnostics-dir", str(ab / diag)])

    erg = pb1(bestand, "bestand.parquet", STICHTAG_1, config_pfad, "diagnostics")
    codes["pb1_vor"] = (erg.exit_code, erg.errors)
    for abnahme, erwartung in (("A-M1", ANKER),
                               ("A-M2", "baldrian_erwartungswerte_verlauf.json"),
                               ("A-M3", "baldrian_erwartungswerte_geschaeftsvorfaelle.json")):
        codes[abnahme] = aktuartest_lauf.main([
            "--fall", str(fall), "--abnahme", abnahme, "--generation", GENERATION,
            "--erwartungswerte", erwartung, "--stichprobe", STICHPROBE,
            "--bestand", str(bestand / "bestand.parquet"), "--zeilen", str(zeilen),
            "--vorgeschichte", METADATEN, "--schicht", str(schichten), "--repo-root", str(REPO_ROOT)] + _flags(verfahren))
    codes["migrationssuite"] = migrationssuite_lauf.main([
        "--fall", str(fall), "--generation", GENERATION,
        "--abzug-1", ABZUG_1, "--abzug-2", ABZUG_2, "--gevo-protokoll", PROTOKOLL,
        "--bestand", str(bestand / "bestand.parquet"),
        "--stichtag-1", STICHTAG_1, "--stichtag-2", STICHTAG_2,
        "--zeilen", str(zeilen), "--vorgeschichte", METADATEN,
        "--anker-erwartungswerte", ANKER, "--schicht", str(schichten),
        "--config", str(config_pfad),
        "--repo-root", str(REPO_ROOT)] + _flags(verfahren))
    codes["fortschreibung"] = cli_fortschreibung.main([
        "--config", str(config_pfad), "--bis", STICHTAG_2,
        "--uebernahme", str(bestand), "--out-dir", str(nach)])
    erg = pb1(nach, "bestand_gesamt.parquet", STICHTAG_2, config_pfad, "diagnostics-nach")
    codes["pb1_nach"] = (erg.exit_code, erg.errors)
    probe_argv = [
        "--fall", str(fall), "--repo-root", str(REPO_ROOT), "--generation", GENERATION,
        "--uebernahme", str(bestand), "--config", str(config_pfad),
        "--zeilen", str(zeilen), "--vorgeschichte", METADATEN, "--stichtag", STICHTAG_1,
        "--anker-erwartungswerte", ANKER, "--schicht", str(schichten),
    ] + _flags(verfahren)
    codes["fuehrungsprobe"] = fuehrungsprobe.main(["--fortschreibung", str(nach)] + probe_argv)
    for name, lauf, portfolio, bis in (
            ("bestandsbericht-vor.html", bestand, "bestand.parquet", STICHTAG_1),
            ("bestandsbericht-nach.html", nach, "bestand_gesamt.parquet", STICHTAG_2)):
        codes[name] = cli_report.main([
            "--portfolio", str(lauf / portfolio), "--historie", str(lauf / "historie.parquet"),
            "--ledger", str(lauf / "ledger.parquet"), "--bis", bis,
            "--out", str(berichte / name)])
    am4 = abnahmebericht.main([
        "--fall", str(fall), "--suite", str(berichte / "migrationssuite.json"),
        "--titel", "Migrationsabnahme Alt-Absetzung nach t",
        "--stichtag-1", STICHTAG_1, "--stichtag-2", STICHTAG_2,
        "--spec", str(spec), "--transformation-ergebnis", str(ergebnis),
        "--bestandsbericht-vor", str(berichte / "bestandsbericht-vor.html"),
        "--bestandsbericht-nach", str(berichte / "bestandsbericht-nach.html"),
        "--repo-root", str(REPO_ROOT), "--diagnostics-dir", str(ab / "diagnostics")])
    codes["A-M4"] = {e["code"] for e in am4.errors}

    # Die Fuehrung kuendigt selbst im Nachlauf teil: dieselbe Config mit
    # Teilkuendigungs- und Herabsetzungsrate, Fortschreibung bis zum Ablauf
    # der Neuen, P-B1, Probe und Abschluss.
    nachlauf_cfg = ab / "cfg-nachlauf.toml"
    nachlauf_cfg.write_text(config_pfad.read_text(encoding="utf-8") + (
        f"\n[annahmen]\nred_anteil = {F}\ntk_anteil = {F}\n"
        "[annahmen.herabsetzung]\na = 0.5\nb = 0.0\n"
        "[annahmen.teilkuendigung]\na = 0.5\nb = 0.0\n"),
        encoding="utf-8")
    nachlauf = ab / "bestand-nachlauf"
    bis_nachlauf = "2032-01-01"
    codes["fortschreibung_nachlauf"] = cli_fortschreibung.main([
        "--config", str(nachlauf_cfg), "--bis", bis_nachlauf,
        "--uebernahme", str(bestand), "--out-dir", str(nachlauf)])
    erg = pb1(nachlauf, "bestand_gesamt.parquet", bis_nachlauf, nachlauf_cfg,
              "diagnostics-nachlauf")
    codes["pb1_nachlauf"] = (erg.exit_code, erg.errors)
    probe_nachlauf = list(probe_argv)
    probe_nachlauf[probe_nachlauf.index("--config") + 1] = str(nachlauf_cfg)
    codes["fuehrungsprobe_nachlauf"] = fuehrungsprobe.main(
        ["--fortschreibung", str(nachlauf)] + probe_nachlauf)
    codes["abschluss_nachlauf"] = cli_abschluss.main([
        "--config", str(nachlauf_cfg), "--lauf", str(nachlauf),
        "--stichtag", "2031-01-01", "--bis", bis_nachlauf,
        "--out-dir", str(ab / "abschluss-nachlauf")])
    return {"codes": codes, "fall": fall, "bestand": bestand, "nach": nach,
            "nachlauf": nachlauf, "berichte": berichte}


@pytest.fixture(scope="module", params=[PROSPEKTIV, MIT_ABZUG, TEILKUENDIGUNG])
def kette(request, tmp_path_factory):
    basis = tmp_path_factory.mktemp(f"alt_absetzung_{request.param}")
    return request.param, fahre_kette(basis, request.param)


def test_die_ganze_kette_traegt_die_alt_herabsetzung_nach_t(kette):
    """Jeder Schritt der Kette laeuft durch, fuer jede Generation. Vorher
    (Kern 3.15.0) brach unter prospektiv/mit Abzug die Serie in der
    Ableitung ab ("Serie mit Herabsetzung unter Verfahren"), und die
    Fuehrung zog im Nachlauf nichts."""
    verfahren, k = kette
    c = k["codes"]
    for schritt in ("transformation", "uebernahme", "transformation_ziel", "verankerung",
                    "A-M1", "A-M2", "A-M3", "migrationssuite", "fortschreibung",
                    "fuehrungsprobe", "bestandsbericht-vor.html",
                    "bestandsbericht-nach.html", "fortschreibung_nachlauf",
                    "fuehrungsprobe_nachlauf", "abschluss_nachlauf"):
        assert c[schritt] == 0, (verfahren, schritt, c[schritt])
    for gate in ("pb1_vor", "pb1_nach", "pb1_nachlauf"):
        assert c[gate][0] == 0, (verfahren, gate, c[gate][1][:3])
    assert "pb1_contract" not in c["A-M4"] and c["A-M4"] <= {"scope_bindung"}, c["A-M4"]


def test_die_uebernahme_fuehrt_die_alt_herabsetzung_als_teilkuendigung(kette):
    """Einzelfall: kein Anfangszustand, Stammsumme = gelieferte Summe (f x
    Ursprungssumme), wie das Gegenstueck ohne Vorgeschichte. Serie: Grund f x G
    = 30.000, die Scheiben unveraendert aus dem Dynamiksatz."""
    verfahren, k = kette
    stamm = read_portfolio(k["bestand"] / "bestand.parquet").set_index("police_id")
    scheiben = read_portfolio(k["bestand"] / "scheiben.parquet")
    assert float(stamm.loc[int(MIT), "sum_insured"]) == SUMME[MIT]
    assert float(stamm.loc[int(OHNE), "sum_insured"]) == SUMME[OHNE]
    assert float(stamm.loc[int(SERIE), "sum_insured"]) == pytest.approx(F * G_SERIE, abs=0.005)
    eigene = scheiben[scheiben["police_id"] == int(SERIE)]
    assert sorted(zip(eigene["erhoehung_jahr"], eigene["sum_insured"])) == [
        (j, pytest.approx(vs, abs=0.005)) for j, vs in SCHEIBEN_SERIE]
    assert scheiben[scheiben["police_id"] == int(MIT)].empty


def test_kein_vertrag_mit_alt_herabsetzung_bleibt_ohne_ableitung(kette):
    """Die Ableitung GELINGT, sie wird nicht nur ueberlebt: Bis Kern 3.15.0
    stand die Police mit Einzel-Herabsetzung unter prospektiv/mit Abzug im
    Uebernahmebeleg unter "ohne_anfangszustand" (Abbruch "Absetzungsjahr
    liegt nicht in der Beitragszahlungsdauer", zur Warnung degradiert) und
    lief nur zufaellig wertgleich als zustandsloser Vertrag weiter; die
    Serie verlor ihre Scheiben. Jetzt ist der zustandslose Vertrag die
    Aussage der Annahme A2, nicht der Rueckfall einer gescheiterten
    Ableitung — und eine gescheiterte Ableitung waere eine Verweigerung."""
    verfahren, k = kette
    beleg = json.loads((k["bestand"] / "uebernahme.json").read_text(encoding="utf-8"))
    ohne = {str(e.get("police_id")) for e in beleg.get("ohne_anfangszustand") or []}
    assert not ohne & set(NEU), (verfahren, ohne)


def _urteile(pfad: Path) -> dict:
    beleg = json.loads(pfad.read_text(encoding="utf-8"))
    return {str(u["police_id"]): u for u in beleg["vertraege"]}


def test_controlling_und_abnahme_bestehen_und_der_mit_gleicht_dem_ohne(kette):
    """Migrationscontrolling (beide Stichtage) und A-M1/A-M2: die drei Neuen
    bestanden — und die Police mit Alt-Herabsetzung hat dieselben System-
    werte wie das Gegenstueck ohne Vorgeschichte (gleiche Summe, gleiche
    Zelle): die Teilkuendigung hinterlaesst den zustandslosen Vertrag."""
    verfahren, k = kette
    berichte = k["berichte"]
    suite = _urteile(berichte / "migrationssuite.json")
    for pid in NEU:
        assert suite[pid]["bestanden"], (verfahren, pid, suite[pid].get("befunde"))

    def system(u):
        return [(p["groesse"], p["system"]) for p in u["pruefungen"]]

    assert system(suite[MIT]) == system(suite[OHNE])
    for abnahme, name in (("A-M1", "aktuartest.json"), ("A-M2", "aktuartest-A-M2.json")):
        at = _urteile(berichte / name)
        for pid in NEU:
            assert at[pid]["bestanden"], (verfahren, abnahme, pid, at[pid])


def test_die_fuehrung_kuendigt_im_nachlauf_selbst_teil(kette):
    """Die Fortschreibung mit Teilkuendigungsrate zieht im Nachlauf in jeder
    Generation eine Teilkuendigung — gebucht als TKU mit Auszahlungszeile,
    nie als RED; eine Herabsetzung (RED) faellt nur vor t. P-B1,
    Fuehrungsprobe und Abschluss bestehen (oben)."""
    verfahren, k = kette
    red = read_portfolio(k["nachlauf"] / "reduktionen.parquet")
    stamm = read_portfolio(k["bestand"] / "bestand.parquet").set_index("police_id")
    t = stamm.loc[red["police_id"], "premium_duration"].to_numpy()
    ab_t = red[red["reduktion_jahr"].to_numpy() >= t]
    assert len(ab_t) >= 1, verfahren
    assert set(ab_t["verfahren"]) == {TEILKUENDIGUNG}
    led = read_portfolio(k["nachlauf"] / "ledger.parquet")
    for z in ab_t.to_dict("records"):
        eigene = led[(led["police_id"] == z["police_id"])
                     & (led["vertragsjahr"] == z["reduktion_jahr"])]
        assert "RED" not in set(eigene["ereignis"]), z
        assert "RKW_teilkuendigung" in set(
            eigene[eigene["ereignis"] == "TKU"]["betrag_art"]), z
    reds = led[led["ereignis"] == "RED"]
    assert (reds["vertragsjahr"].to_numpy()
            < stamm.loc[reds["police_id"], "premium_duration"].to_numpy()).all()


def test_die_gedeckten_vertraege_sind_pflichtschicht_jeder_abnahme(kette):
    """Pruefer-Befund B1, Bauauflage: Der Vertrag, dessen Anfangszustand die
    registrierte Auskunft traegt (die Serie 7100003: Grund f x G und
    Scheiben), ist Pflichtziehung von A-M1, A-M2 und der Migrationssuite;
    der Uebernahmebeleg nennt, WODURCH er gedeckt ist (Datei, SHA-256,
    Bezug); die Fuehrungsprobe fuehrt dieselbe Menge. Die Einzel-Absetzung
    7100002 ist NICHT gedeckt: Ihr zustandsloser Vertrag folgt aus Annahme
    A2 und der gelieferten Summe, die Auskunft bestimmt an ihm nichts."""
    verfahren, k = kette
    beleg = json.loads((k["bestand"] / "uebernahme.json").read_text(encoding="utf-8"))
    gedeckt = {str(p): g for p, g in beleg["gedeckt"].items()}
    assert sorted(gedeckt) == [SERIE], gedeckt
    assert gedeckt[SERIE]["durch"] == "auskunft" and gedeckt[SERIE]["datei"] == AUSKUNFT
    assert gedeckt[SERIE]["sha256"] and gedeckt[SERIE]["bezug"]
    berichte = k["berichte"]
    suite = json.loads((berichte / "migrationssuite.json").read_text(encoding="utf-8"))
    assert sorted(map(str, suite["pflichtschicht"])) == [SERIE]
    assert not suite.get("pflichtschicht_fehlt")
    for name in ("aktuartest.json", "aktuartest-A-M2.json"):
        at = json.loads((berichte / name).read_text(encoding="utf-8"))
        assert sorted(map(str, at["pflichtschicht"])) == [SERIE], name
        assert not at.get("pflichtschicht_fehlt"), name
    probe = json.loads((berichte / "fuehrungsprobe.json").read_text(encoding="utf-8"))
    assert sorted(map(str, probe["gedeckt"])) == [SERIE]
    assert abnahmebericht._pflichtschicht_fehler(probe, suite, k["fall"]) == []


@pytest.mark.parametrize("mutation", ["beleg_ohne_serie", "suite_leer", "probe_leer"])
def test_a_m4_wird_rot_wenn_ein_gedeckter_vertrag_der_abnahme_fehlt(kette, mutation, tmp_path):
    """Mutation auf den blinden Fleck, an den echten Belegen der Kette: der
    A-M1-Beleg ohne 7100003 (gedeckte Police nicht gezogen), die
    Pflichtschicht der Suite leer, oder die Probe ohne gedeckte Police — die
    Regel von A-M4 (``_pflichtschicht_fehler``, gerufen aus der Pruefung der
    Fuehrungsprobe) meldet es. Die Kette dieses Tests endet in A-M4 an der
    fehlenden A-Box (``scope_bindung``) vor dieser Regel; deshalb wird sie
    hier direkt auf den Belegen gefahren, in einer Kopie des Falls."""
    # Die Regel haengt nicht am Verfahren der Generation; die Probe laeuft
    # deshalb auf jeder Kette statt auf einer und den Rest zu ueberspringen
    # (ein Skip waere hier eine Zahl ohne Aussage).
    _verfahren, k = kette
    fall = tmp_path / "fall"
    shutil.copytree(k["fall"], fall)
    berichte = fall / "abgeleitet" / "berichte"
    suite = json.loads((berichte / "migrationssuite.json").read_text(encoding="utf-8"))
    probe = json.loads((berichte / "fuehrungsprobe.json").read_text(encoding="utf-8"))
    if mutation == "beleg_ohne_serie":
        pfad = berichte / "aktuartest.json"
        at = json.loads(pfad.read_text(encoding="utf-8"))
        ps = at["pflichtschicht"]
        at["pflichtschicht"] = ({p: v for p, v in ps.items() if str(p) != SERIE}
                                if isinstance(ps, dict) else [p for p in ps if str(p) != SERIE])
        pfad.write_text(json.dumps(at, ensure_ascii=False), encoding="utf-8")
    elif mutation == "suite_leer":
        suite["pflichtschicht"] = {}
    else:
        probe["gedeckt"] = []
    assert abnahmebericht._pflichtschicht_fehler(probe, suite, fall)


# --------------------------------------------------------------------------- #
# Die Angriffe des Pruefers (B1, B2): verweigert, nicht still uebernommen
# --------------------------------------------------------------------------- #

NUR_SERIE = ((SERIE, "ERH", "01.01.2017"), (SERIE, "ERH", "01.01.2019"),
             (SERIE, "RED", "01.01.2024"))


@pytest.mark.parametrize("szenario,vorgeschichte,auskunft,kandidaten,teil", [
    # B1: die Serie ohne Auskunft — mit Kandidaten mehrdeutig, ohne
    # Kandidaten ohne Anteil. Vorher: Exit 0, Serie still zustandslos.
    ("serie_ohne_auskunft", VORGESCHICHTE_NEU, ((MIT, "01.01.2024", F),), True,
     "--red-anteile-datei"),
    ("serie_ohne_auskunft_ohne_kand", VORGESCHICHTE_NEU, ((MIT, "01.01.2024", F),), False,
     "--red-anteile-datei"),
    # B1: eine Absetzung vor t ohne Wirkung (JBRUTTO 0 bei RED im Jahr 7).
    # Vorher: Exit 0, Vertrag still zustandslos.
    ("red_vor_t_jbrutto0", ((MIT, "RED", "01.01.2022"),) + NUR_SERIE,
     ((SERIE, "01.01.2024", F),), False, "--red-anteile-datei"),
    # B2: nach dem Stichtag, am und nach dem Ablauf (n = 18 ab 2015).
    # Vorher: Exit 0, die Absetzung des Jahres 15/18/25 still uebernommen.
    ("red_nach_stichtag", ((MIT, "RED", "01.01.2030"),) + NUR_SERIE,
     ((SERIE, "01.01.2024", F),), False, "nach dem Stichtag"),
    ("red_am_ablauf", ((MIT, "RED", "01.01.2033"),) + NUR_SERIE,
     ((SERIE, "01.01.2024", F),), False, "Ablauf"),
    ("red_nach_ablauf", ((MIT, "RED", "01.01.2040"),) + NUR_SERIE,
     ((SERIE, "01.01.2024", F),), False, "Ablauf"),
])
def test_die_uebernahme_verweigert_was_sie_nicht_bestimmen_kann(
        tmp_path, szenario, vorgeschichte, auskunft, kandidaten, teil):
    with pytest.raises(SystemExit) as exc:
        fahre_kette(tmp_path, PROSPEKTIV, bis_uebernahme=True, kandidaten=kandidaten,
                    vorgeschichte=vorgeschichte, auskunft=auskunft)
    assert exc.value.code not in (0, None)
    assert teil in str(exc.value.code), (szenario, str(exc.value.code)[:400])


def test_die_falsche_auskunft_ist_eine_benannte_grenze(tmp_path):
    """Grenze (klv.md 7.2, ADR-002-Nachtrag): Eine registrierte Auskunft, die
    falsch ist (0,75 statt 0,6), bestimmt eine falsche Zerlegung der Serie
    (Grund und Scheiben), deren Summe aber stimmt; nach dem Beitragsende ist
    die Kette dagegen blind (kein Beitrag, die Reserven der Zerlegungen
    liegen innerhalb der Centrundung beieinander). Die Uebernahme fuehrt den
    Vertrag als gedeckt — die Auskunft ist eine Aussage der Quelle mit ihrem
    Bezug, die Verantwortung liegt bei dem, der sie registriert. Der Test
    pinnt die Grenze, damit eine Strukturpruefung, die sie schliesst, ihn
    bewusst aendert."""
    k = fahre_kette(tmp_path, PROSPEKTIV, bis_uebernahme=True,
                    auskunft=((MIT, "01.01.2024", F), (SERIE, "01.01.2024", 0.75)))
    assert k["codes"]["uebernahme"] == 0
    stamm = read_portfolio(k["bestand"] / "bestand.parquet").set_index("police_id")
    assert abs(float(stamm.loc[int(SERIE), "sum_insured"]) - F * G_SERIE) > 100.0
    beleg = json.loads((k["bestand"] / "uebernahme.json").read_text(encoding="utf-8"))
    assert SERIE in {str(p) for p in beleg["gedeckt"]}
