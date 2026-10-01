"""Zugangsprobe und Zugangsabnahme A-B2 (ADR-022) — nach den drei Instrumenten.

Entscheid des Maintainers 2026-09-30: Der Zugang eines abgenommenen
Bestands in die produktive Ablage wird abgenommen. Die Zugangsprobe
(``betrieb.zugangsprobe``) faehrt eine Kopie der Ablage einmal ohne, einmal
mit dem Eingang; die Differenz muss exakt der abgenommene Bestand sein. Das
Gate A-B2 zeichnet sie, die Registrierung verlangt die Abnahme fuer GENAU
ihren Eingang und den Stand, auf dem sie schreibt, und der Tageslauf haelt
sie beim Eintritt noch einmal gegen den Stand.

Die drei Instrumente (Skill ``teste-adversarial``):

* **Ratsche** ueber die hergeleiteten Mengen, mit ``==``: die verglichenen
  Groessen gegen die Liste im Beleg und im Vertrag, die Belegrollen von
  A-B2 (``test_belegrollen_und_zeichnung_t2603``).
* **Zaehltest je Groesse**: ein Cent im Abschluss oder Journal der
  "mit"-Kopie, ein Vertrag mehr oder weniger — die Probe wird rot, und
  zwar in genau den Groessen, die davon zeugen (fuer die Stueckgroessen ist
  das Bewegungskonto ein zweiter, abhaengiger Zeuge; das steht im Soll).
* **Positivkontrolle**: echte Ablage, echter Fall (die Fixtures von
  ``test_betrieb_uebernahme``), aktuartest.json und migrationssuite.json
  aus den ECHTEN Produzenten (``qa.aktuarieller_test``,
  ``qa.migrationssuite``), gepinnt von A-M1 und A-M4 — die Probe besteht,
  und der echte Tageslauf nach der Registrierung schreibt byte-gleich die
  Abschluesse der "mit"-Kopie. Die Istwerte haelt der Test zusaetzlich
  gegen Kern-Primitive (``_dk``, ``_jb``).

Block F, Nachbesserung (Pruefer-Befunde 1-9): Soll-Bindung an die
geltenden Abnahmen, der tatsaechliche Eintritt eines vorausdatierten
Eingangs, Jahresbeitrag ueber den ganzen Zugang, je Abwehrstelle ein
Angreifer ohne Schluessel, der Code-Stand der Probe, die Rolle der
A-B2-Freigabe.

Seit 2026-10-01 (Entscheid des Maintainers: Abschluss monatsgenau,
Fuehrungswert in A-M4) vergleicht die Probe Deckungskapital,
Rueckkaufswert und Korrekturschicht gegen den Fuehrungswert der Suite; die
vorher erwartet roten DK-Tests (xfail, strict) sind echte Tests mit
Rueckrichtung (Vergleich ausgebaut -> unbemerkt) und Positivkontrolle
(Toleranz unendlich -> unbemerkt), dazu Angriffe auf die Ablagekopie je
Angriffsart und die maximale Manipulation.

Knoten: system/betrieb
"""

from __future__ import annotations

import datetime as dt
import hashlib
import json
import shutil
from pathlib import Path

import pandas as pd
import pytest

from rechner_pipeline.bestand.config import load_config
from rechner_pipeline.bestand.parquet_io import read_portfolio, write_portfolio
from rechner_pipeline.betrieb import tageslauf as tl
from rechner_pipeline.betrieb import uebernahme as ueb
from rechner_pipeline.betrieb import zugangsprobe as zpb
from rechner_pipeline.betrieb.tageslauf import EXIT_OK, Ablage, tageslauf
from rechner_pipeline.models import zugangsprobe as zp
from tests.freigabe_testschluessel import BETRIEB_FREIGABEKEY, TESTKEY
from tests.test_betrieb_uebernahme import PLV, STICHTAG, _fall, _mit_config
from tests.zugangsabnahme_testhelfer import ab2_snapshot

FOLGETERMIN = dt.date(2026, 2, 1)


# --------------------------------------------------------------------------- #
# Das Soll aus den echten Produzenten
# --------------------------------------------------------------------------- #


def _kern(start: str):
    """Der Kern eines Vertrags des Test-Zugangsstands (x=35, F, n=25, t=20,
    VS 60.000, monatlich; Generation KLV-2017 der PLV-Config)."""
    from rechner_pipeline.kern import ModelPoint, Rechenkern

    return Rechenkern(ModelPoint(**_modellpunkt()))


def _modellpunkt() -> dict:
    gen = next(g for g in load_config(PLV).generationen if g.name == "KLV-2017")
    return dict(x=35, sex="F", n=25, t=20, sum_insured=60000.0, zw=12, **gen.generation_fields())


#: Die drei Vertraege des Zugangsstands (test_betrieb_uebernahme._zugangsstand):
#: Beginn, und ob beitragsfrei seit Vertragsjahr 6.
VERTRAEGE = {7_000_001: ("2018-03-01", None), 7_000_002: ("2019-07-01", None),
             7_000_003: ("2017-11-01", 6)}


def _monate(beginn: str, tag: dt.date) -> int:
    b = dt.date.fromisoformat(beginn)
    return (tag.year - b.year) * 12 + tag.month - b.month


def _dk(police: int, tag: dt.date) -> float:
    """Deckungskapital aus den Kern-Primitiven — monatsgenau (die Konvention
    des Abschlusses seit 2026-10-01): beitragspflichtig die Deckungs-
    rueckstellung der Monatsreserve, beitragsfrei die beitragsfreie
    Monatsreserve. Kein Aufruf der Bewertungsstrecke des Betriebs."""
    beginn, pex = VERTRAEGE[police]
    kern, monate = _kern(beginn), _monate(beginn, tag)
    if pex is not None:
        return float(kern.monatsreserve_beitragsfrei(pex, monate))
    return float(kern.monatsreserve(monate).drx_bpfl)


def _rkw(police: int, tag: dt.date) -> float:
    """Rueckkaufswert aus der Monatsreserve (beitragsfrei: keiner)."""
    beginn, pex = VERTRAEGE[police]
    return 0.0 if pex is not None else float(
        _kern(beginn).monatsreserve(_monate(beginn, tag)).rkw)


def _jb(police: int) -> float:
    beginn, pex = VERTRAEGE[police]
    return 0.0 if pex is not None else float(_kern(beginn).gross_annual_premium())


def _lieferung_dk(police: int, tag: dt.date) -> float:
    """Der GELIEFERTE Stichtagswert der abgebenden Gesellschaft: die
    Monatsreserve (so rechnet die Pruefstrecke den Systemwert). Nur die
    Erwartung der Lieferung — die Probe liest die SYSTEMwerte."""
    beginn, pex = VERTRAEGE[police]
    kern, monate = _kern(beginn), _monate(beginn, tag)
    if pex is not None:
        return float(kern.monatsreserve_beitragsfrei(pex, monate))
    return float(kern.monatsreserve(monate).vx_mrv)


def _producer_belege(fall: Path) -> None:
    """aktuartest.json und migrationssuite.json aus den ECHTEN Produzenten
    (``qa.aktuarieller_test`` und ``qa.migrationssuite`` ueber den
    Zugangsstand, wie der Baldrian-e2e-Test sie fuehrt) — Block F,
    Nachbesserung, Pruefer-Befund 3: Vorher baute der Test beide Dateien
    selbst, in der Konvention des Abschlusses; die Positivkontrolle war
    damit blind fuer genau den Unterschied zwischen Abnahme- und
    Betriebswelt, den die Probe zeigen soll.

    Die Stichprobe des aktuariellen Tests ist geschichtet (je Historientyp
    EIN Vertrag): Ein Vertrag des Zugangs liegt ausserhalb — an ihm zeigt
    der Zaehltest, dass die Probe ueber den GANZEN Zugang vergleicht."""
    from rechner_pipeline.qa import aktuarieller_test as at
    from rechner_pipeline.qa import migrationssuite as ms
    from rechner_pipeline.qa.stichprobe import ziehe
    from rechner_pipeline.qa.testprofil import vorlage

    mp = _modellpunkt()
    typ = {str(p): ("beitragsfrei" if pex else "aktiv") for p, (_, pex) in VERTRAEGE.items()}
    stichprobe = ziehe("geschichtet", sorted(typ), schichten=typ, je_schicht=1)
    auftraege = []
    for p, (beginn, pex) in VERTRAEGE.items():
        if str(p) not in stichprobe.police_ids:
            continue
        ta = 12 * (_monate(beginn, STICHTAG) // 12)
        kern = _kern(beginn)
        erwartet = (kern.reserve_beitragsfrei(pex, ta // 12) if pex
                    else kern.verlaufszeile(ta // 12).vx_mrv)
        auftraege.append(at.Vertragspruefung(
            police_id=str(p), model_point=dict(mp), historientyp=typ[str(p)],
            punkte=(at.verankerungspunkt(ta, {"kVx_MRV": round(float(erwartet), 2)}),),
            beitragsfrei_seit_jahr=pex))
    aktuartest = at.pruefe_stichprobe(
        auftraege, stichprobe, vorlage("A-M1", weite="je Historientyp ein Vertrag"))
    bestand = fall / "abgeleitet" / "bestand" / "bestand.parquet"
    # Der Fuehrungswert, wie gates.migrationssuite_lauf ihn liefert: ueber die
    # Bewertungsstrecke des Abschlusses, aus dem Bestand des Falls, mit der
    # Config der Fuehrung (Entscheid 2026-10-01).
    from rechner_pipeline.bestand.migrationszugang import fuehrungswerte
    from rechner_pipeline.models.fuehrungswert import kopf

    tabellen = fall / "abgeleitet" / "bestand"
    config_text = PLV.read_text(encoding="utf-8")
    konvention, fw = fuehrungswerte(
        read_portfolio(bestand), read_portfolio(tabellen / "historie.parquet"), config_text,
        {"stichtag_1": STICHTAG, "stichtag_2": FOLGETERMIN})
    suite = ms.pruefe_bestand([
        ms.VertragsPruefung(
            police_id=str(p), model_point=dict(mp),
            monate_stichtag_1=_monate(beginn, STICHTAG),
            monate_stichtag_2=_monate(beginn, FOLGETERMIN),
            dk_erwartet_1=round(_lieferung_dk(p, STICHTAG), 2),
            dk_erwartet_2=round(_lieferung_dk(p, FOLGETERMIN), 2),
            bjb_erwartet_1=round(_jb(p), 2), beitragsfrei_seit_jahr=pex)
        for p, (beginn, pex) in VERTRAEGE.items()],
        erwartete_anzahl=len(VERTRAEGE), stichtag_1=STICHTAG.isoformat(),
        stichtag_2=FOLGETERMIN.isoformat(),
        bestand_sha256=hashlib.sha256(bestand.read_bytes()).hexdigest(),
        fuehrungswert=kopf(konvention, bestand_sha256=hashlib.sha256(bestand.read_bytes()).hexdigest(),
                           config_sha256=hashlib.sha256(config_text.encode("utf-8")).hexdigest()),
        fuehrungswerte=fw)
    berichte = fall / "abgeleitet" / "berichte"
    berichte.mkdir(parents=True, exist_ok=True)
    (berichte / "aktuartest.json").write_text(json.dumps(aktuartest, sort_keys=True), encoding="utf-8")
    (berichte / "migrationssuite.json").write_text(json.dumps(suite, sort_keys=True), encoding="utf-8")


def _abnahmen_zeichnen(fall: Path) -> str:
    """A-M1 und A-M4 auf den Bytes der Produzenten: A-M1 pinnt
    aktuartest.json, A-M4 pinnt A-M1 und migrationssuite.json — wie das
    Gate sie schreibt (Signatur: Freigabe-Testschluessel). Liefert den Hash
    des A-M4-Snapshots; der alte aus ``_fall`` wird ersetzt."""
    from tests.test_betrieb_uebernahme import _pb1_ledger, am1_snapshot, am4_snapshot, fuehrungsbeleg

    berichte = fall / "abgeleitet" / "berichte"
    sha = {n: hashlib.sha256((berichte / f"{n}.json").read_bytes()).hexdigest()
           for n in ("aktuartest", "migrationssuite")}
    am1 = am1_snapshot(fall.name, aktuartest_sha=sha["aktuartest"])
    am4 = am4_snapshot(fall.name, pb1_ledger_sha=_pb1_ledger(fall),
                       fuehrungsprobe_sha=fuehrungsbeleg(fall),
                       pins={"am1_snapshot": am1["snapshot_sha256"],
                             "migrationssuite": sha["migrationssuite"]})
    entscheide = fall / "entscheide"
    for alt in list(entscheide.glob("A-M4-*.json")) + list(entscheide.glob("A-M1-*.json")):
        alt.unlink()
    for daten in (am1, am4):
        (entscheide / f"{daten['gate']}-{daten['snapshot_sha256']}.json").write_text(
            json.dumps(daten, ensure_ascii=False), encoding="utf-8")
    (fall / "abgeleitet" / "diagnostics" / "gate_entscheid_am4.gate.json").write_text(
        json.dumps({"summary": {"snapshot_sha256": am4["snapshot_sha256"]}}), encoding="utf-8")
    return am4["snapshot_sha256"]


#: Betriebsbeginn der Testablage: einen Monat VOR dem Zugangsstichtag —
#: so gibt es einen Abschluss davor, an dem die Probe zeigen muss, dass der
#: Zugang dort nicht auftaucht.
BETRIEBSBEGINN = dt.date(2025, 12, 1)


def _welt(wurzel: Path, *, betriebsbeginn: dt.date = BETRIEBSBEGINN):
    """Fall, Ablage (Config, noch nie gefuehrt), die Belege der Abnahmen aus
    den echten Produzenten und A-M1/A-M4, die sie pinnen."""
    import re

    from tests.test_betrieb_uebernahme import _kleine_config

    fall = _fall(wurzel)
    _producer_belege(fall)
    _abnahmen_zeichnen(fall)
    stand = _mit_config(wurzel / "daten", re.sub(
        r"^betriebsbeginn = .*$", f"betriebsbeginn = {betriebsbeginn.isoformat()}",
        _kleine_config(), flags=re.M))
    return fall, stand


@pytest.fixture(scope="module")
def probe(tmp_path_factory):
    """Die echte Probe auf der echten Ablage, Kopien unter ``arbeit`` stehen lassen."""
    wurzel = tmp_path_factory.mktemp("zugangsprobe")
    fall, stand = _welt(wurzel)
    beleg = zpb.zugangsprobe(stand, fall, STICHTAG, arbeit=wurzel / "arbeit")
    return wurzel, fall, stand, beleg


def _soll(fall: Path, arbeit: Path) -> zpb.Soll:
    eingang = arbeit / zpb.KOPIE_MIT / "uebernahme" / "probe-uebernahme"
    am4 = json.loads((eingang / "eingang.json").read_text(encoding="utf-8"))["snapshot_sha256"]
    from tests.freigabe_testschluessel import betriebsordnung, suitelinie_glied

    return zpb.lies_soll(fall, STICHTAG, ueb.zielnummern(eingang), am4_snapshot_sha256=am4,
                         ordnung=betriebsordnung(), ordnungslinie=[suitelinie_glied()])


# --------------------------------------------------------------------------- #
# Positivkontrolle
# --------------------------------------------------------------------------- #


def test_die_probe_besteht_auf_echter_ablage_und_echtem_fall(probe):
    """Die Differenz der beiden Laeufe IST der abgenommene Bestand — an beiden
    Terminen, in jeder Groesse, je Vertrag.

    Mutationsprobe: TOLERANZ in models.zugangsprobe auf 0 -> weiter gruen
    (die Laeufe sind exakt); der Soll-Wert des aktuariellen Tests um einen
    Cent verschoben -> rot (Zaehltest unten)."""
    _, fall, stand, beleg = probe
    assert beleg["bestanden"] is True, [
        v for v in beleg["vergleiche"] if v["ok"] is False] or beleg["befunde"]
    assert zp.beleg_fehler(beleg) == []
    am_stichtag = {v["groesse"]: v for v in beleg["vergleiche"]
                   if v["termin"] == "zugangsstichtag"}
    assert am_stichtag["in_kraft"]["soll"] == am_stichtag["in_kraft"]["ist"] == 3
    assert am_stichtag["versicherungssumme"]["ist"] == pytest.approx(180000.0)
    assert am_stichtag["deckungskapital"]["ist"] == pytest.approx(
        sum(_dk(p, STICHTAG) for p in VERTRAEGE), abs=1e-6)
    # Der Abschluss fuehrt monatsgenau — und die Abnahme weist genau das aus.
    assert am_stichtag["deckungskapital"]["soll"] == pytest.approx(
        sum(_dk(p, STICHTAG) for p in VERTRAEGE), abs=1e-6)
    assert am_stichtag["rueckkaufswert"]["ist"] == pytest.approx(
        sum(_rkw(p, STICHTAG) for p in VERTRAEGE), abs=1e-6)
    for g in zp.FUEHRUNGSWERT_VERGLICHEN:
        assert am_stichtag[g]["ok"] is True and am_stichtag[g]["umfang"] == len(VERTRAEGE), g
    assert beleg["konvention"] == "monatsgenau"
    assert am_stichtag["jahresbeitrag"]["ist"] == pytest.approx(
        sum(_jb(p) for p in VERTRAEGE), abs=1e-6)
    # Jahresbeitrag je Vertrag ueber den GANZEN Zugang (Migrationssuite),
    # nicht nur auf der Stichprobe des aktuariellen Tests.
    assert am_stichtag["jahresbeitrag"]["ok"] is True
    assert am_stichtag["jahresbeitrag"]["umfang"] == len(VERTRAEGE)
    folge = {v["groesse"]: v for v in beleg["vergleiche"] if v["termin"] == "folgetermin"}
    assert folge["in_kraft"]["ok"] is True
    assert folge["deckungskapital"]["ok"] is True and folge["deckungskapital"]["ausgenommen"] == []
    assert folge["deckungskapital"]["ist"] == pytest.approx(
        sum(_dk(p, FOLGETERMIN) for p in VERTRAEGE), abs=1e-6)
    assert beleg["folgetermin"]["gedeckt"] is True
    # Das Soll ist an die Abnahmen gebunden: die Bytes, die A-M1 und A-M4 pinnen.
    for rolle, (_, datei) in zp.SOLL_BELEGE.items():
        assert beleg["abnahmen"][rolle]["sha256"] == hashlib.sha256(
            (fall / datei).read_bytes()).hexdigest() == beleg["eingaben"][datei]
    # Die Bindungen: der Stand, auf dem die Probe lief, und der Eingang.
    assert beleg["ablage_stand"]["sha256"] == zp.stand_sha256(tl.ablage_stand(Ablage(stand)))
    assert beleg["eingang"]["inhalt"]["fall"] == "probe-uebernahme"
    assert beleg["am4_snapshot_sha256"] == beleg["eingang"]["inhalt"]["snapshot_sha256"]
    # Das Original wurde nie beschrieben: kein Eingang, kein Protokoll.
    assert not (stand / "uebernahme").exists() and not Ablage(stand).protokoll_pfad.exists()


def test_der_beleg_ist_vom_betrieb_gezeichnet(probe):
    """Urheberschaft, keine Abnahme: gezeichnet mit dem Betriebsschluessel,
    nachrechenbar mit ihm; eine Aenderung faellt der Signatur auf."""
    from rechner_pipeline.betrieb._zeichnung import betriebszeichnung_fehler

    _, _, stand, beleg = probe
    zeichner = tl.betriebszeichner(Ablage(stand))
    assert betriebszeichnung_fehler(zp.signierter_satz(beleg), zeichner.ring, zeichner.ordnung) is None
    verbogen = {**beleg, "bestanden": False}
    assert "Signatur" in str(betriebszeichnung_fehler(
        zp.signierter_satz(verbogen), zeichner.ring, zeichner.ordnung))


# --------------------------------------------------------------------------- #
# Ratsche: die verglichenen Groessen
# --------------------------------------------------------------------------- #


def test_ratsche_die_verglichenen_groessen_sind_die_des_belegs(probe):
    """``==`` in beide Richtungen: Jede Groesse des Vertrags wird verglichen,
    und keine andere; der Beleg nennt genau diese Liste. Eine Groesse, die
    im Vertrag steht, aber nie verglichen wird, waere ein Detektor ohne
    Treffer.

    Mutationsprobe: den Vergleich 'zugangsbuchungen' in vergleiche() streichen
    -> rot (und bestanden_aus verweigert)."""
    _, _, _, beleg = probe
    assert beleg["groessen"] == list(zp.GROESSEN)
    assert {v["groesse"] for v in beleg["vergleiche"]} == set(zp.GROESSEN)
    gegen_soll = {v["groesse"] for v in beleg["vergleiche"] if v["soll"] is not None}
    assert gegen_soll == set(zp.GROESSEN)
    # Keine Groesse steht mehr "nicht vergleichbar" im Beleg (bis 2026-10-01
    # das Deckungskapital).
    assert "nicht_verglichen" not in beleg
    assert not any("nicht vergleichbar" in str(v.get("grund")) for v in beleg["vergleiche"])
    assert set(zp.PFLICHT_AM_STICHTAG) <= {
        v["groesse"] for v in beleg["vergleiche"] if v["termin"] == "zugangsstichtag"}


def test_das_urteil_wird_nachgerechnet_nicht_geglaubt(probe):
    """Der Vertrag rechnet ``ok`` und ``bestanden`` aus Soll, Ist und
    Toleranz nach. Ein umgeschriebenes Urteil, eine fehlende Groesse oder
    eine andere Groessenliste fallen auf."""
    _, _, _, beleg = probe
    rot = json.loads(json.dumps(beleg))
    rot["vergleiche"][0]["ist"] = rot["vergleiche"][0]["ist"] + 1
    assert any("differenz" in f or "Urteil" in f for f in zp.beleg_fehler(rot))
    luecke = json.loads(json.dumps(beleg))
    luecke["vergleiche"] = [v for v in luecke["vergleiche"] if v["groesse"] != "zugang"]
    assert any("bestanden" in f for f in zp.beleg_fehler(luecke))
    anders = json.loads(json.dumps(beleg))
    anders["groessen"] = list(zp.GROESSEN)[:-1]
    assert any("groessen" in f for f in zp.beleg_fehler(anders))


# --------------------------------------------------------------------------- #
# Zaehltest je Groesse
# --------------------------------------------------------------------------- #


def _cent(pfad: Path, spalte: str, police: int, delta: float = 0.01) -> None:
    tabelle = read_portfolio(pfad)
    tabelle.loc[tabelle["police_id"] == police, spalte] += delta
    pfad.chmod(0o644)
    write_portfolio(tabelle, pfad)


def _abschluss(arbeit: Path, tag: dt.date) -> Path:
    return arbeit / zpb.KOPIE_MIT / "abschluesse" / f"abschluss_{tag.isoformat()}.parquet"


def _journal(arbeit: Path) -> Path:
    return arbeit / zpb.KOPIE_MIT / "journal" / "tagesjournal.parquet"


def _ziel_von(arbeit: Path, quelle: int) -> int:
    return ueb.zielnummern(arbeit / zpb.KOPIE_MIT / "uebernahme" / "probe-uebernahme")[quelle]


def _dk_cent(arbeit):
    _cent(_abschluss(arbeit, STICHTAG), "deckungskapital", _ziel_von(arbeit, 7_000_001))


def _vs_cent(arbeit):
    _cent(_abschluss(arbeit, STICHTAG), "leistung", _ziel_von(arbeit, 7_000_002))


def _jb_cent(arbeit):
    _cent(_abschluss(arbeit, STICHTAG), "jahresbeitrag", _ziel_von(arbeit, 7_000_001))


def _dk_gegenlaeufig(arbeit):
    """Ein Cent hin, ein Cent her: Die Summe stimmt, zwei Vertraege nicht —
    nur der Vergleich je Vertrag sieht es."""
    _cent(_abschluss(arbeit, STICHTAG), "deckungskapital", _ziel_von(arbeit, 7_000_001), +0.01)
    _cent(_abschluss(arbeit, STICHTAG), "deckungskapital", _ziel_von(arbeit, 7_000_002), -0.01)


def _dk_folge_cent(arbeit):
    _cent(_abschluss(arbeit, FOLGETERMIN), "deckungskapital", _ziel_von(arbeit, 7_000_003))


def _vertrag_weniger(arbeit):
    pfad = _abschluss(arbeit, STICHTAG)
    tabelle = read_portfolio(pfad)
    pfad.chmod(0o644)
    write_portfolio(tabelle[tabelle["police_id"] != _ziel_von(arbeit, 7_000_001)]
                    .reset_index(drop=True), pfad)


def _vertrag_mehr(arbeit):
    """Ein Vertrag ohne Betraege mehr — nur die Stueckzahl aendert sich."""
    pfad = _abschluss(arbeit, STICHTAG)
    tabelle = read_portfolio(pfad)
    zeile = tabelle.iloc[[0]].copy()
    zeile["police_id"] = 999
    for spalte in ("leistung", "deckungskapital", "rueckkaufswert", "korrekturschicht",
                   "vs_bfr", "jahresbeitrag"):
        zeile[spalte] = 0.0
    pfad.chmod(0o644)
    write_portfolio(pd.concat([tabelle, zeile], ignore_index=True), pfad)


def _zugang_mehr(arbeit):
    """Ein zweiter Zugangsvorfall desselben Vertrags nach dem Stichtag."""
    pfad = _journal(arbeit)
    journal = read_portfolio(pfad)
    ziel = _ziel_von(arbeit, 7_000_001)
    zeile = journal[(journal["police_id"] == ziel) & (journal["ereignis"] == "ZUG")].iloc[[0]].copy()
    zeile["status_date"] = pd.Timestamp("2026-01-15")
    zeile["buchungsdatum"] = pd.Timestamp("2026-01-15")
    write_portfolio(pd.concat([journal, zeile], ignore_index=True), pfad)


def _buchung_cent(arbeit):
    """Ein Cent in der Umbuchung des beitragsfrei uebernommenen Vertrags."""
    pfad = _journal(arbeit)
    journal = read_portfolio(pfad)
    ziel = _ziel_von(arbeit, 7_000_003)
    journal.loc[(journal["police_id"] == ziel) & (journal["ereignis"] == "PEX"), "betrag"] += 0.01
    write_portfolio(journal, pfad)


def _fremde_buchung_cent(arbeit):
    """Ein Cent in einer Buchung des eigenen Geschaefts."""
    pfad = _journal(arbeit)
    journal = read_portfolio(pfad)
    p_ids = set(ueb.zielnummern(arbeit / zpb.KOPIE_MIT / "uebernahme" / "probe-uebernahme").values())
    index = journal.index[~journal["police_id"].isin(sorted(p_ids))][0]
    journal.loc[index, "betrag"] += 0.01
    write_portfolio(journal, pfad)


def _fremde_abschlusszeile_cent(arbeit):
    pfad = _abschluss(arbeit, FOLGETERMIN)
    tabelle = read_portfolio(pfad)
    p_ids = set(ueb.zielnummern(arbeit / zpb.KOPIE_MIT / "uebernahme" / "probe-uebernahme").values())
    fremd = int(tabelle.loc[~tabelle["police_id"].isin(sorted(p_ids)), "police_id"].iloc[0])
    _cent(pfad, "deckungskapital", fremd)


def _zugang_spaeter_gebucht(arbeit):
    """Die Zugangsbuchung eines Vertrags wird erst im Folgemonat sichtbar —
    Wirkungstag, Betrag und Zahl bleiben, nur das Konto der Periode kippt."""
    pfad = _journal(arbeit)
    journal = read_portfolio(pfad)
    ziel = _ziel_von(arbeit, 7_000_002)
    journal.loc[(journal["police_id"] == ziel) & (journal["ereignis"] == "ZUG"),
                "buchungsdatum"] = pd.Timestamp("2026-01-15")
    write_portfolio(journal, pfad)


def _ausserhalb_der_stichprobe(fall: Path) -> int:
    """Ein Vertrag des Zugangs, den der aktuarielle Test NICHT gezogen hat."""
    gezogen = set(json.loads((fall / "abgeleitet" / "berichte" / "aktuartest.json")
                             .read_text(encoding="utf-8"))["stichprobe"]["police_ids"])
    draussen = sorted(p for p, (_, pex) in VERTRAEGE.items() if str(p) not in gezogen and pex is None)
    assert draussen, ("der Zaehltest braucht einen beitragspflichtigen Vertrag ausserhalb "
                      "der Stichprobe", sorted(gezogen))
    return draussen[0]


def _jb_ausserhalb_der_stichprobe(arbeit, fall):
    """Pruefer-Befund 4: ein Cent Jahresbeitrag bei einem Vertrag, den die
    Stichprobe des aktuariellen Tests nicht zieht — vorher blieb das gruen."""
    _cent(_abschluss(arbeit, STICHTAG), "jahresbeitrag", _ziel_von(arbeit, _ausserhalb_der_stichprobe(fall)))


def _jb_gegenlaeufig(arbeit):
    _cent(_abschluss(arbeit, STICHTAG), "jahresbeitrag", _ziel_von(arbeit, 7_000_001), +0.01)
    _cent(_abschluss(arbeit, STICHTAG), "jahresbeitrag", _ziel_von(arbeit, 7_000_002), -0.01)


def _abgang_im_fenster(arbeit):
    """Ein Vertrag des Zugangs geht im Januar ab (STO), und der Abschluss
    zum Folgetermin traegt ihn nicht mehr: Das ist fuer die Migrationssuite
    ein Vertrag zu wenig (sie kennt den Abgang nicht), fuer das
    Bewegungskonto aber stimmig — Anfang 3 + Zugang 0 - Abgang 1 = Ende 2.
    Wer den Abgang nicht zaehlt, sieht einen Fehler im Konto (Mutation P8)."""
    ziel = _ziel_von(arbeit, 7_000_002)
    pfad = _journal(arbeit)
    journal = read_portfolio(pfad)
    zeile = journal[(journal["police_id"] == ziel) & (journal["ereignis"] == "ZUG")].iloc[[0]].copy()
    zeile["ereignis"] = "STO"
    zeile["status_date"] = pd.Timestamp("2026-01-15")
    zeile["buchungsdatum"] = pd.Timestamp("2026-01-15")
    write_portfolio(pd.concat([journal, zeile], ignore_index=True), pfad)
    abschluss = _abschluss(arbeit, FOLGETERMIN)
    tabelle = read_portfolio(abschluss)
    abschluss.chmod(0o644)
    write_portfolio(tabelle[tabelle["police_id"] != ziel].reset_index(drop=True), abschluss)


def _zeile_vor_dem_stichtag(arbeit):
    """Ein Vertrag des Zugangs steht schon im Abschluss VOR dem Stichtag —
    die Differenz dort muss leer sein (Mutation P11)."""
    ziel = _ziel_von(arbeit, 7_000_001)
    zeile = read_portfolio(_abschluss(arbeit, STICHTAG))
    zeile = zeile[zeile["police_id"] == ziel]
    pfad = _abschluss(arbeit, BETRIEBSBEGINN)
    tabelle = read_portfolio(pfad)
    pfad.chmod(0o644)
    write_portfolio(pd.concat([tabelle, zeile], ignore_index=True), pfad)


def _rkw_cent(arbeit):
    _cent(_abschluss(arbeit, STICHTAG), "rueckkaufswert", _ziel_von(arbeit, 7_000_002))


def _schicht_cent(arbeit):
    """Ein Cent Korrekturschicht, wo keine ist — der Vergleich gegen null ist
    kein Detektor ohne Treffer."""
    _cent(_abschluss(arbeit, STICHTAG), "korrekturschicht", _ziel_von(arbeit, 7_000_001))


#: Die Mutationen an Deckungskapital, Rueckkaufswert und Korrekturschicht —
#: bis 2026-10-01 waren die DK-Mutationen erwartet gruen (xfail, strict),
#: weil die Probe das Deckungskapital nicht verglich.
DK_MUTATIONEN = [
    (_dk_cent, {"deckungskapital"}),
    (_dk_gegenlaeufig, {"deckungskapital"}),
    (_dk_folge_cent, {"deckungskapital"}),
    (_rkw_cent, {"rueckkaufswert"}),
    (_schicht_cent, {"korrekturschicht"}),
]


@pytest.mark.parametrize("mutation,rot", DK_MUTATIONEN + [
    (_vs_cent, {"versicherungssumme"}),
    (_jb_cent, {"jahresbeitrag"}),
    (_jb_ausserhalb_der_stichprobe, {"jahresbeitrag"}),
    (_jb_gegenlaeufig, {"jahresbeitrag"}),
    # Die Stueckgroessen haben das Bewegungskonto als zweiten Zeugen, und ein
    # fehlender Vertrag fehlt auch in jeder Summe — seit dem Fuehrungswert
    # auch in Deckungskapital, Rueckkaufswert und Korrekturschicht (dort ist
    # die Summe gleich, null gegen null, aber der Vertrag fehlt einzeln):
    (_vertrag_weniger, {"in_kraft", "versicherungssumme", "deckungskapital",
                        "rueckkaufswert", "korrekturschicht", "jahresbeitrag",
                        "bewegungskonto"}),
    # Ein Vertrag ohne Betraege aendert keine Summe — aber Uebernahme und
    # Migrationssuite nennen JEDEN Vertrag, also fehlt ihm das Soll jeder
    # Groesse, die je Vertrag verglichen wird:
    (_vertrag_mehr, {"in_kraft", "versicherungssumme", "deckungskapital", "rueckkaufswert",
                     "korrekturschicht", "jahresbeitrag", "bewegungskonto",
                     "ausserhalb_des_zugangs"}),
    (_zugang_mehr, {"zugang", "bewegungskonto"}),
    (_buchung_cent, {"zugangsbuchungen"}),
    (_zugang_spaeter_gebucht, {"bewegungskonto"}),
    (_abgang_im_fenster, {"in_kraft"}),
    (_zeile_vor_dem_stichtag, {"ausserhalb_des_zugangs"}),
    (_fremde_buchung_cent, {"ausserhalb_des_zugangs"}),
    (_fremde_abschlusszeile_cent, {"ausserhalb_des_zugangs"}),
], ids=lambda x: getattr(x, "__name__", ""))
def test_zaehltest_eine_mutation_macht_genau_ihre_groessen_rot(probe, tmp_path, mutation, rot):
    """Je Groesse eine Mutation an der Ausgabe des Laufs "mit" — die Probe
    fragt dieselbe Vergleichsfunktion noch einmal und wird rot in GENAU den
    erwarteten Groessen. Positivkontrolle: ohne Mutation ist nichts rot."""
    wurzel, fall, _, _ = probe
    arbeit = tmp_path / "arbeit"
    shutil.copytree(wurzel / "arbeit", arbeit, symlinks=True)
    soll = _soll(fall, arbeit)
    vorher, befunde = zpb.vergleiche(arbeit / zpb.KOPIE_OHNE, arbeit / zpb.KOPIE_MIT, soll,
                                     stichtag=STICHTAG)
    assert not befunde and not [v for v in vorher if v["ok"] is False]
    import inspect

    mutation(*((arbeit, fall) if len(inspect.signature(mutation).parameters) == 2 else (arbeit,)))
    nachher, befunde = zpb.vergleiche(arbeit / zpb.KOPIE_OHNE, arbeit / zpb.KOPIE_MIT, soll,
                                      stichtag=STICHTAG)
    assert {v["groesse"] for v in nachher if v["ok"] is False} == rot
    assert zp.bestanden_aus(nachher, befunde) is False


def test_ein_soll_ohne_werte_ist_kein_gruener_vergleich(probe, tmp_path):
    """Detektor ohne Treffer: Traegt die Migrationssuite keinen
    Jahresbeitrag, waere die Summe ueber nichts 0 = 0 und der Vergleich
    gruen. Er ist dann 'nicht belegt', ein Befund nennt es, und
    die Probe besteht nicht.

    Mutationsprobe: das ``if soll.jb else None`` entfernen -> gruen -> rot."""
    import dataclasses

    wurzel, fall, _, _ = probe
    arbeit = tmp_path / "arbeit"
    shutil.copytree(wurzel / "arbeit", arbeit, symlinks=True)
    soll = _soll(fall, arbeit)
    leer = dataclasses.replace(soll, fw={g: {} for g in zp.FUEHRUNGSWERT_VERGLICHEN}, jb={},
                               ledger=soll.ledger.iloc[0:0])
    vergleiche, befunde = zpb.vergleiche(arbeit / zpb.KOPIE_OHNE, arbeit / zpb.KOPIE_MIT, leer,
                                         stichtag=STICHTAG)
    am_stichtag = {v["groesse"]: v for v in vergleiche if v["termin"] == "zugangsstichtag"}
    assert am_stichtag["jahresbeitrag"]["ok"] is None
    assert am_stichtag["zugangsbuchungen"]["ok"] is None
    # Ein Fuehrungswert ueber nichts gegen drei Abschlusszeilen ist kein
    # "nicht belegt", sondern drei Vertraege ohne Soll: rot, je Vertrag.
    for g in zp.FUEHRUNGSWERT_VERGLICHEN:
        assert am_stichtag[g]["ok"] is False and am_stichtag[g]["abweichend_anzahl"] == 3, g
    assert any("kein Jahresbeitrag" in b for b in befunde)
    assert any("kein Deckungskapital (Fuehrungswert)" in b for b in befunde)
    assert any("Ledger der Uebernahme ist leer" in b for b in befunde)
    assert zp.bestanden_aus(vergleiche, []) is False


# --------------------------------------------------------------------------- #
# Angriffe auf die Ablagekopie: die Fuehrung fuehrt einen anderen Vertrag
# --------------------------------------------------------------------------- #
#
# Der Zaehltest oben verfaelscht die ABSCHLUSSSPALTE. Hier wird die Ablage
# selbst verstuemmelt — der Vertrag, den die Fuehrung fuehrt, ist ein anderer
# als der abgenommene —, und der Abschluss der Kopie "mit" wird daraus ueber
# die Bewertungsstrecke NEU geschrieben, in sich stimmig. Gegen sich selbst
# nachgerechnet ist er deckungsgleich; die Probe muss trotzdem rot werden,
# weil ihr Soll aus der gepinnten Abnahme kommt (Beleg, der nur sich selbst
# bezeugt).


def _stand_tabellen(arbeit: Path) -> dict:
    stand = Ablage(arbeit / zpb.KOPIE_MIT).stand
    return {n: (read_portfolio(stand / f"{n}.parquet") if (stand / f"{n}.parquet").is_file()
                else None)
            for n in ("bestand_gesamt", "historie", "scheiben", "merkmale", "schichten",
                      "verankerung", "reduktionen")}


def _abschluss_aus(arbeit: Path, t: dict, config) -> None:
    """Den Abschluss am Stichtag der Kopie "mit" aus den Tabellen ``t`` neu
    schreiben — die Zeilen der Vertraege des Eingangs, ueber die
    Bewertungsstrecke des Abschlusses (``schreibe_abschluss``)."""
    import tempfile

    from rechner_pipeline.bestand.abschluss import lies_abschluss, schreibe_abschluss

    with tempfile.TemporaryDirectory() as d:
        neu, _ = lies_abschluss(schreibe_abschluss(
            t["bestand_gesamt"], t["historie"], config, STICHTAG, Path(d),
            scheiben=t["scheiben"], merkmale=t["merkmale"], schichten=t["schichten"],
            verankerung=t["verankerung"], reduktionen=t["reduktionen"]))
    p_ids = set(ueb.zielnummern(arbeit / zpb.KOPIE_MIT / "uebernahme" / "probe-uebernahme").values())
    pfad = _abschluss(arbeit, STICHTAG)
    alt, _ = lies_abschluss(pfad)
    tabelle = pd.concat([alt[~alt["police_id"].isin(sorted(p_ids))],
                         neu[neu["police_id"].isin(sorted(p_ids))]], ignore_index=True)
    tabelle = tabelle.sort_values("police_id", kind="stable").reset_index(drop=True)
    pfad.chmod(0o644)
    write_portfolio(tabelle, pfad)


def _tarifparameter(t, ziel):
    """Das Eintrittsalter des Vertrags um ein Jahr verschoben (die Lesart
    der Quelle gegen die des Ziels — der Klassiker der Parametrierung)."""
    s = t["bestand_gesamt"]
    s.loc[s["police_id"] == ziel, "entry_age"] += 1
    s.loc[s["police_id"] == ziel, "date_of_birth"] -= pd.DateOffset(years=1)


def _erhoehungsscheibe(t, ziel):
    """Eine Erhoehungsscheibe, die der abgenommene Vertrag nicht hat."""
    from rechner_pipeline.models.bestand import SCHEIBEN_NAMES, SCHEIBEN_SPALTEN

    zeile = pd.DataFrame([{
        "police_id": ziel, "scheiben_id": 1, "erhoehung_jahr": 7,
        "erhoehung_datum": pd.Timestamp("2025-03-01"), "entry_age": 42, "duration": 18,
        "premium_duration": 13, "sum_insured": 5000.0, "gamma1": 0.0,
    }])[list(SCHEIBEN_NAMES)].astype(dict(SCHEIBEN_SPALTEN))
    alt = t["scheiben"]
    t["scheiben"] = zeile if alt is None or not len(alt) else pd.concat([alt, zeile], ignore_index=True)


def _korrekturschicht(t, ziel):
    """Eine Korrekturschicht, die der abgenommene Vertrag nicht traegt."""
    from rechner_pipeline.models.bestand import (
        SCHICHTEN_NAMES, SCHICHTEN_SPALTEN, VERANKERUNG_SPALTEN, schichten_zeile)
    from tests.test_schicht_in_fuehrung import _parameter

    schicht = pd.DataFrame([schichten_zeile(ziel, _parameter(0.01).als_beleg())],
                           columns=list(SCHICHTEN_NAMES)).astype(dict(SCHICHTEN_SPALTEN))
    anker = pd.DataFrame([{"police_id": ziel, "monate_ta": 84, "zustand_ta": "beitragspflichtig",
                           "verweildauer_ta": 7, "dk_ta": 1.0}])[
        [n for n, _ in VERANKERUNG_SPALTEN]].astype(dict(VERANKERUNG_SPALTEN))
    for name, neu in (("schichten", schicht), ("verankerung", anker)):
        alt = t[name]
        t[name] = neu if alt is None or not len(alt) else pd.concat([alt, neu], ignore_index=True)


def _vertragsbeginn(t, ziel):
    """Der Vertragsbeginn ein Jahr frueher — Dauern und Alter stimmen, der
    Vertrag ist am Stichtag ein Jahr aelter."""
    s = t["bestand_gesamt"]
    for spalte in ("insurance_start", "insurance_end", "payment_end", "date_of_birth"):
        s.loc[s["police_id"] == ziel, spalte] -= pd.DateOffset(years=1)


ANGRIFFE = [_tarifparameter, _erhoehungsscheibe, _korrekturschicht, _vertragsbeginn]


def _angegriffen(probe, tmp_path: Path, angriffe) -> tuple:
    wurzel, fall, _, _ = probe
    arbeit = tmp_path / "arbeit"
    shutil.copytree(wurzel / "arbeit", arbeit, symlinks=True)
    soll = _soll(fall, arbeit)
    t = _stand_tabellen(arbeit)
    config = load_config(Ablage(arbeit / zpb.KOPIE_MIT).config_pfad)
    for angriff in angriffe:
        angriff(t, _ziel_von(arbeit, 7_000_001))
    _abschluss_aus(arbeit, t, config)
    vergleiche, befunde = zpb.vergleiche(arbeit / zpb.KOPIE_OHNE, arbeit / zpb.KOPIE_MIT, soll,
                                         stichtag=STICHTAG)
    return arbeit, t, config, {v["groesse"] for v in vergleiche if v["ok"] is False}, befunde


def test_angriff_positivkontrolle_der_neu_geschriebene_abschluss_ist_gruen(probe, tmp_path):
    """Ohne Verstuemmelung schreibt der Nachbau des Abschlusses dieselben
    Zeilen — sonst waeren die roten Befunde unten Artefakte des Nachbaus."""
    _, _, _, rot, befunde = _angegriffen(probe, tmp_path, [])
    assert rot == set() and befunde == []


@pytest.mark.parametrize("angriff,rot", [
    (_tarifparameter, {"deckungskapital", "rueckkaufswert", "jahresbeitrag"}),
    (_erhoehungsscheibe, {"deckungskapital", "rueckkaufswert", "jahresbeitrag",
                          "versicherungssumme"}),
    # Diese beiden bewegen weder Summe noch Beitrag: Bis 2026-10-01, als die
    # Probe das Deckungskapital nicht verglich, blieben sie gruen.
    (_korrekturschicht, {"deckungskapital", "rueckkaufswert", "korrekturschicht"}),
    (_vertragsbeginn, {"deckungskapital", "rueckkaufswert"}),
], ids=lambda x: getattr(x, "__name__", ""))
def test_zaehltest_je_angriffsart_auf_die_ablage_rot_am_deckungskapital(
        probe, tmp_path, angriff, rot):
    """Tarifparameter, Erhoehungsscheibe, Korrekturschicht, Vertragsbeginn
    eines Vertrags verstuemmelt: Die Fuehrung fuehrt einen anderen Vertrag
    als den abgenommenen, und die Probe sieht es am Deckungskapital — in
    genau den Groessen, die der Angriff bewegt (``==``)."""
    _, _, _, ist, befunde = _angegriffen(probe, tmp_path, [angriff])
    assert ist == rot and befunde == []


def test_maximale_manipulation_ablage_und_abschluss_konsistent_verfaelscht(probe, tmp_path):
    """Alle vier Angriffe zugleich, der Abschluss daraus stimmig neu
    geschrieben: Gegen die verfaelschte Ablage nachgerechnet ist er
    deckungsgleich (``pruefe_abschluss`` ohne Befund) — er bezeugt nur sich
    selbst. Die Probe haelt ihn gegen den Fuehrungswert der gepinnten
    Abnahme und wird rot, an Deckungskapital, Rueckkaufswert und Schicht."""
    from rechner_pipeline.bestand.abschluss import pruefe_abschluss

    arbeit, t, config, rot, _ = _angegriffen(probe, tmp_path, ANGRIFFE)
    p_ids = set(ueb.zielnummern(arbeit / zpb.KOPIE_MIT / "uebernahme" / "probe-uebernahme").values())
    nur_zugang = {k: (v[v["police_id"].isin(sorted(p_ids))] if v is not None else None)
                  for k, v in t.items()}
    gegen_sich = pruefe_abschluss(
        _abschluss(arbeit, STICHTAG), nur_zugang["bestand_gesamt"], nur_zugang["historie"],
        config, scheiben=nur_zugang["scheiben"], merkmale=nur_zugang["merkmale"],
        schichten=nur_zugang["schichten"], verankerung=nur_zugang["verankerung"],
        reduktionen=nur_zugang["reduktionen"])
    assert not [b for b in gegen_sich if f"police {_ziel_von(arbeit, 7_000_001)}:" in b], gegen_sich
    assert {"deckungskapital", "rueckkaufswert", "korrekturschicht"} <= rot, rot


# --------------------------------------------------------------------------- #
# Registrierung: mit A-B2, ohne, fremd, auf verandertem Stand
# --------------------------------------------------------------------------- #


def _ab2_aus_beleg(fall: Path, beleg: dict, *, eingang_sha: "str | None" = None,
                   am4_sha: "str | None" = None, schluessel: bytes = BETRIEB_FREIGABEKEY,
                   roh: "bytes | None" = None) -> str:
    """Den echten Beleg ablegen und einen A-B2-Snapshot, der ihn pinnt —
    ``eingang_sha``/``am4_sha`` setzen fremde Pins, ``schluessel`` zeichnet
    die Freigabe, ``roh`` legt andere Bytes desselben Belegs ab."""
    roh = roh or (json.dumps(beleg, ensure_ascii=False, indent=2, sort_keys=True) + "\n").encode("utf-8")
    pfad = fall / zp.BELEG_RELATIV
    pfad.parent.mkdir(parents=True, exist_ok=True)
    pfad.write_bytes(roh)
    vorher = [json.loads(p.read_text())["snapshot_sha256"]
              for p in sorted((fall / "entscheide").glob("A-B2-*.json"))]
    daten = ab2_snapshot(fall.name, pflichtbelege={
        "zugangsprobe": [hashlib.sha256(roh).hexdigest()],
        "am4_snapshot": [am4_sha or beleg["am4_snapshot_sha256"]],
        "eingang": [eingang_sha or beleg["eingang"]["sha256"]],
    }, vorgaenger=vorher, schluessel=schluessel)
    (fall / "entscheide" / f"A-B2-{daten['snapshot_sha256']}.json").write_text(
        json.dumps(daten), encoding="utf-8")
    return daten["snapshot_sha256"]


@pytest.fixture()
def ohne_naht(monkeypatch):
    """Produktivverhalten: keine Test-Naht der Zugangsabnahme."""
    monkeypatch.setattr(ueb, "_STANDARD_ZUGANGSABNAHME", None)


def test_registrierung_mit_abnahme_und_der_echte_lauf_gleicht_der_probe(tmp_path, ohne_naht):
    """Die volle Kette: Probe, A-B2, Registrierung, Tageslauf. Die
    Registrierung schreibt BYTEGLEICH den Eingang, den die Probe in ihrer
    Kopie schrieb, und der echte Lauf schreibt bytegleich die Abschluesse
    der "mit"-Kopie — die Probe hat gerechnet, was der Betrieb tut."""
    fall, stand = _welt(tmp_path)
    beleg = zpb.zugangsprobe(stand, fall, STICHTAG, arbeit=tmp_path / "arbeit")
    assert beleg["bestanden"] is True
    sha = _ab2_aus_beleg(fall, beleg)
    ziel = ueb.eingang_anlegen(stand, fall, STICHTAG, zugangsabnahme_sha256=sha)
    assert hashlib.sha256((ziel / "eingang.json").read_bytes()).hexdigest() == beleg["eingang"]["sha256"]
    abnahme = json.loads((ziel / ueb.ZUGANGSABNAHME_DATEI).read_text(encoding="utf-8"))
    assert abnahme["a_b2"]["snapshot_sha256"] == sha and abnahme["a_b2"]["signatur_verifiziert"] is True
    assert abnahme["ablage_stand_sha256"] == beleg["ablage_stand"]["sha256"]
    code, zeile = tageslauf(Ablage(stand), FOLGETERMIN)
    assert code == EXIT_OK, zeile.get("fehler")
    assert [u["fall"] for u in zeile["uebernahmen"]] == ["probe-uebernahme"]
    for tag in (STICHTAG, FOLGETERMIN):
        echt = (stand / "abschluesse" / f"abschluss_{tag.isoformat()}.parquet").read_bytes()
        assert echt == _abschluss(tmp_path / "arbeit", tag).read_bytes(), tag


def test_ohne_zugangsabnahme_wird_nichts_registriert(tmp_path, ohne_naht):
    """Ohne A-B2 kein Eintritt — und schon keine Registrierung, mit Ausweg.

    Mutationsprobe: die Verweigerung ohne Snapshot in eingang_anlegen
    entfernen -> rot."""
    fall, stand = _welt(tmp_path)
    with pytest.raises(ueb.UebernahmeError, match="kein A-B2-Snapshot.*Zugangsprobe fahren"):
        ueb.eingang_anlegen(stand, fall, STICHTAG)
    assert not (stand / "uebernahme" / "probe-uebernahme").exists()


def test_eine_abnahme_fuer_einen_anderen_eingang_wird_verweigert(tmp_path, ohne_naht):
    """Zwischen Probe und Registrierung wurde ein anderer Fall registriert:
    Das Nummernband verschiebt sich, der Eingang ist ein anderer als der
    abgenommene. Der Stand der Ablage ist derselbe — nur die Bindung an den
    Eingang faengt es.

    Mutationsprobe: den Vergleich des Eingangs-Hashes in
    _zugangsabnahme_binden entfernen -> rot."""
    fall, stand = _welt(tmp_path)
    beleg = zpb.zugangsprobe(stand, fall, STICHTAG)
    sha = _ab2_aus_beleg(fall, beleg)
    anderer = _fall(tmp_path / "anderer", name="anderer-fall")
    from tests.zugangsabnahme_testhelfer import schreibe_zugangsabnahme

    ueb._STANDARD_ZUGANGSABNAHME = schreibe_zugangsabnahme      # nur fuer diesen einen
    try:
        ueb.eingang_anlegen(stand, anderer, STICHTAG)
    finally:
        ueb._STANDARD_ZUGANGSABNAHME = None
    with pytest.raises(ueb.UebernahmeError, match="nicht der, den A-B2 abgenommen hat.*band"):
        ueb.eingang_anlegen(stand, fall, STICHTAG, zugangsabnahme_sha256=sha)
    assert not (stand / "uebernahme" / "probe-uebernahme").exists()


def test_eine_abnahme_auf_verandertem_stand_wird_verweigert(tmp_path, ohne_naht):
    """Die Ablage lief nach der Probe weiter — hier: ihre Config wurde
    getauscht. Die Abnahme gilt einem anderen Stand.

    Mutationsprobe: den Vergleich des Ablage-Stands in
    _zugangsabnahme_binden entfernen -> rot."""
    fall, stand = _welt(tmp_path)
    beleg = zpb.zugangsprobe(stand, fall, STICHTAG)
    sha = _ab2_aus_beleg(fall, beleg)
    config = Ablage(stand).config_pfad
    config.write_text(config.read_text(encoding="utf-8") + "\n# getauscht\n", encoding="utf-8")
    with pytest.raises(ueb.UebernahmeError, match="lief nach der Probe weiter"):
        ueb.eingang_anlegen(stand, fall, STICHTAG, zugangsabnahme_sha256=sha)


def test_eine_nicht_bestandene_probe_begruendet_keine_registrierung(tmp_path, ohne_naht):
    """Ein A-B2, das eine rote Probe pinnt (etwa von Hand gebaut), traegt nicht."""
    from tests.freigabe_testschluessel import betriebsordnung  # noqa: F401

    fall, stand = _welt(tmp_path)
    beleg = zpb.zugangsprobe(stand, fall, STICHTAG)
    rot = {k: v for k, v in beleg.items() if k != "betriebszeichnung"}
    rot["befunde"] = ["von Hand rot"]
    rot["bestanden"] = False
    rot["betriebszeichnung"] = tl.betriebszeichner(Ablage(stand)).zeichne({"zugangsprobe": rot})
    sha = _ab2_aus_beleg(fall, rot)
    with pytest.raises(ueb.UebernahmeError, match="nicht bestanden"):
        ueb.eingang_anlegen(stand, fall, STICHTAG, zugangsabnahme_sha256=sha)


def test_neuaufsetzen_ohne_zugangsabnahme_baut_nichts(tmp_path, ohne_naht):
    """Das Neuaufsetzen registriert einen Eingang in eine neue Ablage — ohne
    A-B2 verweigert es, BEVOR die neue Ablage angelegt ist.

    Mutationsprobe: die Vorpruefung in neu_aufsetzen entfernen -> die
    Registrierung verweigert erst danach, ein halber Aufbau bleibt liegen -> rot."""
    from rechner_pipeline.betrieb import neuaufsetzen as na

    fall, stand = _welt(tmp_path)
    with pytest.raises(na.NeuaufsetzenError, match="ohne Zugangsabnahme A-B2"):
        na.neu_aufsetzen(stand, fall, STICHTAG)
    assert not list(tmp_path.glob("daten.neu-*"))


# --------------------------------------------------------------------------- #
# Eintritt im Tageslauf
# --------------------------------------------------------------------------- #


def _registriert(tmp_path: Path):
    """Registriert ueber die Test-Naht (Beleg und A-B2 an Eingang und Stand)."""
    fall, stand = _welt(tmp_path)
    ziel = ueb.eingang_anlegen(stand, fall, STICHTAG)
    return fall, stand, ziel


def _neu_zeichnen(pfad: Path, **aenderung) -> None:
    """Die Zugangsabnahme umschreiben UND mit dem Betriebsschluessel neu
    zeichnen — der Faelscher, der den Schluessel hat: Sonst faengt schon die
    Signatur, und der Test sagte nichts ueber die Bindung."""
    daten = json.loads(pfad.read_text(encoding="utf-8"))
    rest = {k: v for k, v in daten.items() if k != "betriebszeichnung"}
    rest.update(aenderung)
    rest["betriebszeichnung"] = tl.betriebszeichner(Ablage(pfad.parents[2])).zeichne(
        {"zugangsabnahme": {k: v for k, v in rest.items() if k != "betriebszeichnung"}})
    pfad.chmod(0o644)
    pfad.write_text(json.dumps(rest), encoding="utf-8")


def test_ohne_zugangsabnahme_tritt_kein_eingang_ein(tmp_path):
    """Ein Eingang ohne zugangsabnahme.json (etwa von Hand kopiert oder vor
    ADR-022 registriert und nie eingetreten) tritt nicht ein; der Lauf ist
    rot, kein Stand wird uebernommen.

    Mutationsprobe: den Aufruf von pruefe_zugangsabnahme in _stand_bauen
    entfernen -> rot."""
    _, stand, ziel = _registriert(tmp_path)
    (ziel / ueb.ZUGANGSABNAHME_DATEI).unlink()
    code, zeile = tageslauf(Ablage(stand), FOLGETERMIN)
    assert code != EXIT_OK and zeile["uebernommen"] is False
    assert "ohne Zugangsabnahme A-B2" in zeile["fehler"]


def test_eine_abnahme_fuer_einen_fremden_eingang_tritt_nicht_ein(tmp_path):
    """Die Abnahme bindet einen anderen Eingang (neu gezeichnet: die
    Signatur stimmt, die Bindung nicht)."""
    _, stand, ziel = _registriert(tmp_path)
    _neu_zeichnen(ziel / ueb.ZUGANGSABNAHME_DATEI, eingang_sha256="ab" * 32)
    code, zeile = tageslauf(Ablage(stand), FOLGETERMIN)
    assert code != EXIT_OK and "fremder oder veraenderter Eingang" in zeile["fehler"]


def test_eine_abnahme_auf_anderem_stand_tritt_nicht_ein(tmp_path):
    """Nach der Registrierung wurde die Config getauscht: Der Eingang traete
    in einen anderen Stand ein als den abgenommenen.

    Mutationsprobe: in pruefe_zugangsabnahme den Vergleich des Stands
    entfernen -> rot."""
    _, stand, _ = _registriert(tmp_path)
    config = Ablage(stand).config_pfad
    config.write_text(config.read_text(encoding="utf-8") + "\n# getauscht\n", encoding="utf-8")
    code, zeile = tageslauf(Ablage(stand), FOLGETERMIN)
    assert code != EXIT_OK and "lief nach der Probe weiter" in zeile["fehler"]


def test_ein_gefuehrter_eingang_wird_nicht_wieder_gefragt(tmp_path):
    """Nach dem Eintritt laeuft der Stand weiter, weil der Eingang gefuehrt
    wird — das ist Betrieb, kein Befund. Ein zweiter Lauf fragt die Abnahme
    nicht mehr (die Zeile bezeugt den Eingang).

    Mutationsprobe: gesichtete_eingaenge leer liefern -> der zweite Lauf ist rot."""
    _, stand, _ = _registriert(tmp_path)
    assert tageslauf(Ablage(stand), STICHTAG)[0] == EXIT_OK
    code, zeile = tageslauf(Ablage(stand), FOLGETERMIN)
    assert code == EXIT_OK, zeile.get("fehler")


# --------------------------------------------------------------------------- #
# Kopie und Ablage bleiben getrennt
# --------------------------------------------------------------------------- #


def test_der_probelauf_verweigert_auf_einer_echten_ablage(tmp_path):
    fall, stand = _welt(tmp_path)
    with pytest.raises(tl.TageslaufError, match="nur auf der gekennzeichneten Kopie"):
        tageslauf(Ablage(stand), STICHTAG, zugangsprobe_fall="probe-uebernahme")
    with pytest.raises(ueb.UebernahmeError, match="nur in der gekennzeichneten Kopie"):
        ueb.eingang_anlegen(stand, fall, STICHTAG, probe_kopie=True)


def test_auf_einer_probenkopie_faehrt_kein_betrieb(probe):
    wurzel, fall, _, _ = probe
    kopie = Ablage(wurzel / "arbeit" / zpb.KOPIE_OHNE)
    with pytest.raises(tl.TageslaufError, match="Kopie einer Zugangsprobe"):
        tageslauf(kopie, dt.date(2026, 2, 2))
    with pytest.raises(ueb.UebernahmeError, match="Kopie einer Zugangsprobe"):
        ueb.eingang_anlegen(kopie.wurzel, fall, STICHTAG)


def test_die_probe_verlangt_einen_monatsersten_und_eine_offene_zeit(tmp_path):
    fall, stand = _welt(tmp_path)
    with pytest.raises(zpb.ZugangsprobeError, match="kein Monatserster"):
        zpb.zugangsprobe(stand, fall, dt.date(2026, 1, 15))
    with pytest.raises(zpb.ZugangsprobeError, match="vor dem naechsten Monatsabschluss"):
        zpb.zugangsprobe(stand, fall, STICHTAG, bis=dt.date(2026, 1, 20))
    with pytest.raises(zpb.ZugangsprobeError, match="ausserhalb der Ablage"):
        zpb.zugangsprobe(stand, fall, STICHTAG, arbeit=stand / "arbeit")


def test_die_cli_schreibt_den_beleg_an_den_festen_ort(tmp_path):
    """Exit 0 bei bestandener Probe, Beleg unter <fall>/abgeleitet/berichte."""
    from tests.freigabe_testschluessel import betriebsargs

    fall, stand = _welt(tmp_path)
    schluessel = tmp_path / "freigabe.key"
    schluessel.write_bytes(TESTKEY)
    schluessel.chmod(0o600)
    from tests.freigabe_testschluessel import linieargs

    code = zpb.main(["--stand", str(stand), "--fall", str(fall), "--stichtag", STICHTAG.isoformat(),
                     "--freigabe-schluessel", str(schluessel), *betriebsargs("--schluessel"),
                     *linieargs()])
    assert code == 0
    beleg = json.loads((fall / zp.BELEG_RELATIV).read_text(encoding="utf-8"))
    assert beleg["bestanden"] is True and zp.beleg_fehler(beleg) == []


# --------------------------------------------------------------------------- #
# Gate A-B2: mensch/betrieb zeichnet, agent/betrieb darf nur ablehnen
# --------------------------------------------------------------------------- #


REPO_ROOT = Path(__file__).resolve().parents[1]


@pytest.fixture()
def gatefall(tmp_path):
    """Ein Bestandsfall durch die echte Registrierung (P-Q3 gruen), darin ein
    angenommener A-M4-Snapshot und der Beleg einer bestandenen Probe; dazu
    die Ordnung mit mensch/betrieb (A-B2), agent/betrieb (keine Gates) und
    der Betriebsrolle, deren Schluessel den Beleg zeichnet."""
    from rechner_pipeline.gates.abox_validate import main as pq3
    from tests.e2e_fixture import bereite_pk1_fall
    from tests.freigabe_testschluessel import (
        AKTUARIAT_GATES,
        AKTUARIAT_ROLLE,
        BETRIEBSKEY,
        BETRIEBSROLLE,
    )
    from tests.test_betrieb_uebernahme import am1_snapshot, am4_snapshot
    from tests.zeichnung_fixture import (
        auftrag_args,
        ordnung_schreiben,
        schluessel_anlegen,
        vorstand_rolle,
    )
    from tests.zugangsabnahme_testhelfer import abnahmen_aus_fall, probenbeleg

    fall = bereite_pk1_fall(tmp_path, ("klv/tg2012",), scope="bestand")
    assert pq3(["--fall", str(fall), "--repo-root", str(REPO_ROOT)]).exit_code == 0
    schluessel = {}
    for name, inhalt in (("mensch", b"betriebsverantwortung-schluessel!" * 2),
                         ("agent", b"betriebs-agent-schluessel-nur-vorlage!" * 2)):
        schluessel[name] = tmp_path / f"{name}-betrieb.key"
        schluessel_anlegen(schluessel[name], inhalt)
    testkey = tmp_path / "am4-freigabe.key"
    testkey.write_bytes(TESTKEY)
    testkey.chmod(0o600)
    ordnung = ordnung_schreiben(tmp_path / "zeichnungsordnung.json", {
        "mensch/betrieb": {"schluessel_sha256": hashlib.sha256(schluessel["mensch"].read_bytes()).hexdigest(),
                           "schluesselklasse": "mensch", "gates": ["A-B1", "A-B2"]},
        "agent/betrieb": {"schluessel_sha256": hashlib.sha256(schluessel["agent"].read_bytes()).hexdigest(),
                          "schluesselklasse": "agent", "gates": []},
        BETRIEBSROLLE: {"schluessel_sha256": hashlib.sha256(BETRIEBSKEY).hexdigest(),
                        "schluesselklasse": "betrieb", "gates": []},
        # Wer A-M1 und A-M4 gezeichnet hat: Das Gate haelt beide gegen
        # DIESE Ordnung (Entscheid 2026-10-01).
        AKTUARIAT_ROLLE: {"schluessel_sha256": hashlib.sha256(TESTKEY).hexdigest(),
                          "schluesselklasse": "mensch", "gates": list(AKTUARIAT_GATES)},
        # Der Vorstand beauftragt den Fall (ADR-026).
        **vorstand_rolle(tmp_path),
    })
    # Erst beauftragen, dann die Annahmen, die auf dem Auftrag stehen: A-B2
    # gruendet auf A-M4 und A-M1, und die nennen den GELTENDEN Auftrag
    # (ADR-026, Nachtrag Runde G).
    auftrag_args(fall)
    from rechner_pipeline.gates.stand_belegen import geltende_spitze

    fallauftrag = geltende_spitze(fall, "A-M6")[0]["snapshot_sha256"]
    # Die Belege der Abnahmen am festen Ort und die Snapshots, die sie pinnen.
    berichte = fall / "abgeleitet" / "berichte"
    berichte.mkdir(parents=True, exist_ok=True)
    (berichte / "aktuartest.json").write_text('{"abnahme": "A-M1"}', encoding="utf-8")
    (berichte / "migrationssuite.json").write_text('{"abnahme": "A-M4"}', encoding="utf-8")
    sha = {n: hashlib.sha256((berichte / f"{n}.json").read_bytes()).hexdigest()
           for n in ("aktuartest", "migrationssuite")}
    am1 = am1_snapshot(fall.name, aktuartest_sha=sha["aktuartest"],
                       fallauftrag=fallauftrag)
    am4 = am4_snapshot(fall.name, fallauftrag=fallauftrag,
                       pins={"am1_snapshot": am1["snapshot_sha256"],
                             "migrationssuite": sha["migrationssuite"]})
    (fall / "entscheide").mkdir(exist_ok=True)
    for daten in (am1, am4):
        (fall / "entscheide" / f"{daten['gate']}-{daten['snapshot_sha256']}.json").write_text(
            json.dumps(daten), encoding="utf-8")
    eingang = {"fall": fall.name, "snapshot_sha256": am4["snapshot_sha256"],
               "stichtag": STICHTAG.isoformat()}
    beleg = probenbeleg(fall.name, ablage_stand={"gefuehrter_tag": None, "config_sha256": "ab" * 32},
                        eingang_roh=json.dumps(eingang).encode("utf-8"),
                        am4_snapshot_sha256=am4["snapshot_sha256"],
                        zeichner=tl.betriebszeichner(Ablage(tmp_path / "irgendeine-ablage")),
                        abnahmen=abnahmen_aus_fall(fall, am4["snapshot_sha256"]))
    (fall / zp.BELEG_RELATIV).parent.mkdir(parents=True, exist_ok=True)
    (fall / zp.BELEG_RELATIV).write_text(json.dumps(beleg), encoding="utf-8")
    return fall, am4, beleg, schluessel, testkey, ordnung


def _ab2(fall, *, schluessel, testkey, ordnung, entscheid="angenommen", extra=()):
    from rechner_pipeline.gates import gate_entscheid
    from tests.zeichnung_fixture import auftrag_args

    args = ["--fall", str(fall), "--gate", "A-B2", "--entscheid", entscheid,
            "--entscheider", "Betriebsverantwortung", "--begruendung", "Zugang geprueft.",
            "--repo-root", str(REPO_ROOT), "--zeichnungsordnung", str(ordnung)]
    if schluessel is None:
        # Auch eine Ablehnung nennt die Linie (ADR-025, Nachtrag 2026-10-01).
        from tests.zeichnung_fixture import linie_sicherstellen

        args += ["--linie", str(linie_sicherstellen(fall, Path(ordnung)))]
    if schluessel is not None:
        # Der Fall ist beauftragt (ADR-026); der Ring traegt den Auftrag mit.
        args += [*auftrag_args(fall, Path(ordnung)), "--freigabe-schluessel", str(testkey),
                 "--freigabe-schluessel", str(schluessel)]
    return gate_entscheid.main(args + list(extra))


def test_mensch_betrieb_zeichnet_die_zugangsabnahme_mit_ihren_drei_belegen(gatefall):
    """Der echte Gate-Pfad: Der geschriebene Snapshot pinnt genau die drei
    Rollen, und die Registrierung liest ihn mit demselben Leser wie A-M4.

    Mutationsprobe: im A-B2-Zweig pflichtbelege['eingang'] nicht setzen ->
    Sperre (Rollenmenge unvollstaendig) -> rot."""
    fall, am4, beleg, schluessel, testkey, ordnung = gatefall
    ergebnis = _ab2(fall, schluessel=schluessel["mensch"], testkey=testkey, ordnung=ordnung)
    assert ergebnis.exit_code == 0, ergebnis.errors
    snapshot = json.loads(Path(ergebnis.paths["snapshot"]).read_text(encoding="utf-8"))
    roh = (fall / zp.BELEG_RELATIV).read_bytes()
    assert snapshot["pflichtbelege"] == {
        "zugangsprobe": [hashlib.sha256(roh).hexdigest()],
        "am4_snapshot": [am4["snapshot_sha256"]],
        "eingang": [beleg["eingang"]["sha256"]],
    }
    assert snapshot["rolle"] == "mensch/betrieb" and snapshot["fall_scope"] == "bestand"
    ledger = json.loads((fall / "abgeleitet" / "diagnostics" / "gate_entscheid_ab2.gate.json")
                        .read_text(encoding="utf-8"))
    assert ledger["summary"]["snapshot_sha256"] == snapshot["snapshot_sha256"]
    ring = {hashlib.sha256(schluessel["mensch"].read_bytes()).hexdigest(): schluessel["mensch"].read_bytes()}
    from rechner_pipeline.models.ordnungslinie import lade_linie
    from tests.freigabe_testschluessel import VORSTANDRING

    daten, _, verifiziert = ueb.lies_abnahme_snapshot(
        fall, "A-B2", snapshot["snapshot_sha256"], schluesselring=ring,
        ordnung=json.loads(Path(ordnung).read_text(encoding="utf-8")),
        ordnungslinie=lade_linie(fall.parent / "linie", ring=VORSTANDRING)[0])
    assert verifiziert is True and daten["gate"] == "A-B2"


def test_a_b2_gruendet_nicht_auf_einer_am4_unter_abgeloestem_auftrag(gatefall):
    """ADR-026, Nachtrag Runde G (G14): Der Vorstand zieht den Auftrag zurueck
    und beauftragt neu. A-M4 und A-M1 stehen auf dem alten Auftrag; A-B2
    gruendet nicht auf ihnen und nennt den Ausweg.

    Mutationsprobe: im A-B2-Zweig die Anmeldung von A-M4 und A-M1 entfernen
    -> A-B2 angenommen -> rot."""
    from rechner_pipeline.gates import gate_entscheid
    from tests.zeichnung_fixture import VORSTAND_SCHLUESSEL_DATEI, fallauftrag_zeichnen

    fall, am4, _, schluessel, testkey, ordnung = gatefall
    zurueck = gate_entscheid.main([
        "--fall", str(fall), "--gate", "A-M6", "--entscheid", "abgelehnt",
        "--entscheider", "vorstand", "--begruendung", "Auftrag zurueckgezogen",
        "--rolle", "mensch/vorstand", "--repo-root", str(REPO_ROOT),
        "--zeichnungsordnung", str(ordnung), "--linie", str(fall.parent / "linie"),
        "--freigabe-schluessel", str(fall.parent / VORSTAND_SCHLUESSEL_DATEI)])
    assert zurueck.exit_code == 0, zurueck.errors
    fallauftrag_zeichnen(fall, ordnung_pfad=Path(ordnung))
    ergebnis = _ab2(fall, schluessel=schluessel["mensch"], testkey=testkey, ordnung=ordnung)
    assert ergebnis.exit_code == 20, ergebnis.errors
    assert ergebnis.errors[0]["code"] == "fallauftrag", ergebnis.errors
    meldung = ergebnis.errors[0]["message"]
    assert "A-M4" in meldung and am4["fallauftrag"][:16] in meldung and "neu zeichnen" in meldung
    assert not list((fall / "entscheide").glob("A-B2-*.json"))


def test_agent_betrieb_darf_nur_ablehnen(gatefall):
    """ADR-018/ADR-022: Der Agent des Betriebs legt vor. Mit seinem Schluessel
    wird die Annahme verweigert (keine Gates in der Ordnung), als Rolle
    behauptet ebenso; eine Ablehnung dokumentiert er."""
    fall, _, _, schluessel, testkey, ordnung = gatefall
    mit_schluessel = _ab2(fall, schluessel=schluessel["agent"], testkey=testkey, ordnung=ordnung)
    assert mit_schluessel.exit_code != 0
    assert "nicht zeichnungsberechtigt" in mit_schluessel.errors[0]["message"]
    behauptet = _ab2(fall, schluessel=None, testkey=testkey, ordnung=ordnung,
                     extra=["--rolle", "agent/betrieb"])
    assert behauptet.exit_code != 0 and "darf nicht annehmen" in behauptet.errors[0]["message"]
    abgelehnt = _ab2(fall, schluessel=None, testkey=testkey, ordnung=ordnung,
                     entscheid="abgelehnt", extra=["--rolle", "agent/betrieb"])
    assert abgelehnt.exit_code == 0, abgelehnt.errors
    assert list((fall / "entscheide").glob("A-B2-*.json"))


def test_eine_rote_oder_umgeschriebene_probe_wird_nicht_angenommen(gatefall):
    """Die Annahme rechnet das Urteil der Probe nach: nicht bestanden ->
    verweigert; 'bestanden' behauptet, aber ein Vergleich rot -> verweigert.

    Mutationsprobe: im A-B2-Zweig beleg_fehler nicht rufen -> der
    umgeschriebene Beleg geht durch -> rot."""
    fall, _, beleg, schluessel, testkey, ordnung = gatefall
    zeichner = tl.betriebszeichner(Ablage(fall.parent / "irgendeine-ablage"))

    def ablegen(daten):
        rest = {k: v for k, v in daten.items() if k != "betriebszeichnung"}
        rest["betriebszeichnung"] = zeichner.zeichne({"zugangsprobe": {
            k: v for k, v in rest.items() if k != "betriebszeichnung"}})
        (fall / zp.BELEG_RELATIV).write_text(json.dumps(rest), encoding="utf-8")

    rot = json.loads(json.dumps(beleg))
    rot["befunde"], rot["bestanden"] = ["der Lauf mit dem Eingang ist rot"], False
    ablegen(rot)
    ergebnis = _ab2(fall, schluessel=schluessel["mensch"], testkey=testkey, ordnung=ordnung)
    assert ergebnis.exit_code != 0 and "nicht bestanden" in ergebnis.errors[0]["message"]
    geschoent = json.loads(json.dumps(beleg))
    jb = next(i for i, v in enumerate(geschoent["vergleiche"]) if v["groesse"] == "jahresbeitrag")
    geschoent["vergleiche"][jb]["ist"] += 1.0         # Differenz gross, ok bleibt True
    ablegen(geschoent)
    ergebnis = _ab2(fall, schluessel=schluessel["mensch"], testkey=testkey, ordnung=ordnung)
    assert ergebnis.exit_code != 0 and "verletzt seinen Vertrag" in ergebnis.errors[0]["message"]
    assert not list((fall / "entscheide").glob("A-B2-*.json"))


def test_eine_probe_auf_einer_ueberholten_migrationsabnahme_wird_nicht_angenommen(gatefall):
    """Die Probe muss auf der GELTENDEN angenommenen A-M4 gelaufen sein: Eine
    spaetere Ablehnung, die die Annahme ueberholt, entzieht ihr die Grundlage."""
    from tests.test_betrieb_uebernahme import am4_snapshot
    from rechner_pipeline.models.schemas import p9_snapshot_sha256

    fall, am4, _, schluessel, testkey, ordnung = gatefall
    ablehnung = am4_snapshot(fall.name, entscheid="abgelehnt")
    ablehnung["vorgaenger"] = [am4["snapshot_sha256"]]
    ablehnung.pop("snapshot_sha256")
    ablehnung["snapshot_sha256"] = p9_snapshot_sha256(ablehnung)
    (fall / "entscheide" / f"A-M4-{ablehnung['snapshot_sha256']}.json").write_text(
        json.dumps(ablehnung), encoding="utf-8")
    ergebnis = _ab2(fall, schluessel=schluessel["mensch"], testkey=testkey, ordnung=ordnung)
    assert ergebnis.exit_code != 0
    assert "geltend und angenommen" in ergebnis.errors[0]["message"]


# --------------------------------------------------------------------------- #
# Block F, Nachbesserung: das Soll ist an die gezeichneten Abnahmen gebunden
# --------------------------------------------------------------------------- #


@pytest.mark.parametrize("rolle", sorted(zp.SOLL_BELEGE))
def test_ein_ersetzter_beleg_der_abnahmen_verweigert_die_probe(tmp_path, rolle):
    """Pruefer-Befund 1, Repro B: migrationssuite.json (bzw. aktuartest.json)
    liegt am festen Ort im Fall und ist ohne Schluessel beschreibbar. Durch
    '{}' ersetzt verschwand der Folgetermin-Vergleich, die Probe blieb gruen.
    Jetzt haelt die Probe die Bytes gegen den Pin des geltenden Snapshots
    (A-M4 bzw. A-M1) und verweigert — mit Ausweg.

    Mutationsprobe: in lies_soll den Aufruf von soll_bindung_fehler
    entfernen -> die Probe laeuft -> rot."""
    fall, stand = _welt(tmp_path)
    (fall / zp.SOLL_BELEGE[rolle][1]).write_text("{}", encoding="utf-8")
    with pytest.raises(zpb.ZugangsprobeError,
                       match="nicht das der geltenden Abnahmen.*Ausweg: die abgenommenen Belege"):
        zpb.zugangsprobe(stand, fall, STICHTAG)


@pytest.mark.parametrize("wo", ["fester_ort", "im_beleg"])
@pytest.mark.parametrize("rolle", sorted(zp.SOLL_BELEGE))
def test_das_gate_haelt_das_soll_gegen_die_pins(gatefall, rolle, wo):
    """Das Gate fragt dieselbe Regel (Repro B, zweite Haelfte): Die Datei am
    festen Ort ist nach der Probe ersetzt — oder der Beleg nennt (sauber
    gezeichnet) ein Soll, das kein Snapshot pinnt.

    Mutationsprobe: im A-B2-Zweig den Soll-Block entfernen -> Annahme -> rot."""
    fall, _, beleg, schluessel, testkey, ordnung = gatefall
    datei = zp.SOLL_BELEGE[rolle][1]
    if wo == "fester_ort":
        (fall / datei).write_text("{}", encoding="utf-8")
    else:
        rest = {k: v for k, v in beleg.items() if k != "betriebszeichnung"}
        rest["abnahmen"][rolle]["sha256"] = "5e" * 32
        rest["eingaben"][datei] = "5e" * 32
        rest["betriebszeichnung"] = tl.betriebszeichner(
            Ablage(fall.parent / "irgendeine-ablage")).zeichne({"zugangsprobe": rest})
        assert zp.beleg_fehler(rest) == []
        (fall / zp.BELEG_RELATIV).write_text(json.dumps(rest), encoding="utf-8")
    ergebnis = _ab2(fall, schluessel=schluessel["mensch"], testkey=testkey, ordnung=ordnung)
    assert ergebnis.exit_code != 0
    assert "nicht das der geltenden Abnahmen" in ergebnis.errors[0]["message"], ergebnis.errors
    assert not list((fall / "entscheide").glob("A-B2-*.json"))


def test_beleg_fehler_verlangt_die_soll_bindung():
    """Pruefer-Repro C: ``eingaben`` war frei — leer oder mit fremden Hashes
    ging der Beleg durch. Jetzt verlangt der Vertrag die Bindung an beide
    Abnahmen und dass das Soll aus genau diesen Bytes gelesen wurde."""
    from tests.zugangsabnahme_testhelfer import probenbeleg

    abnahmen = {
        "aktuartest": {"datei": zp.SOLL_BELEGE["aktuartest"][1], "gate": "A-M1",
                       "sha256": "a1" * 32, "snapshot_sha256": "b1" * 32},
        "migrationssuite": {"datei": zp.SOLL_BELEGE["migrationssuite"][1], "gate": "A-M4",
                            "sha256": "a4" * 32, "snapshot_sha256": "c4" * 32}}
    eingang = json.dumps({"fall": "f", "snapshot_sha256": "c4" * 32,
                          "stichtag": STICHTAG.isoformat()}).encode("utf-8")
    beleg = probenbeleg("f", ablage_stand={"gefuehrter_tag": None}, eingang_roh=eingang,
                        am4_snapshot_sha256="c4" * 32, abnahmen=abnahmen,
                        zeichner=tl.betriebszeichner(Ablage(Path("/nirgends"))))
    assert zp.beleg_fehler(beleg) == []
    for verbiegen in (lambda b: b.update(eingaben={}),
                      lambda b: b["eingaben"].update({zp.SOLL_BELEGE["aktuartest"][1]: "00" * 32}),
                      lambda b: b.pop("abnahmen"),
                      lambda b: b["abnahmen"]["migrationssuite"].update(snapshot_sha256="dd" * 32)):
        b = json.loads(json.dumps(beleg))
        verbiegen(b)
        assert zp.beleg_fehler(b), verbiegen


@pytest.mark.parametrize("fall_art", ["a_m1_neu_entschieden", "soll_nicht_gepinnt"])
def test_die_registrierung_haelt_das_soll_gegen_die_geltenden_abnahmen(tmp_path, ohne_naht, fall_art):
    """Die Registrierung fragt dieselbe Regel wie Probe und Gate:

    * nach A-B2 wird A-M1 neu entschieden (eine Ablehnung ueberholt die
      Annahme) — die Probe stand auf einem Soll, das nicht mehr gilt;
    * der Beleg nennt ein Soll, das kein Snapshot pinnt (neu gezeichnet:
      der Faelscher MIT Betriebsschluessel — ohne ihn faengt schon die
      Signatur, test_p3_...).

    Mutationsprobe: in _zugangsabnahme_binden die Soll-Bindung nicht
    pruefen bzw. den A-M1-Snapshot ohne Kette lesen -> rot."""
    from rechner_pipeline.models.schemas import p9_snapshot_sha256
    from tests.test_betrieb_uebernahme import am1_snapshot

    fall, stand = _welt(tmp_path)
    beleg = zpb.zugangsprobe(stand, fall, STICHTAG)
    if fall_art == "a_m1_neu_entschieden":
        sha = _ab2_aus_beleg(fall, beleg)
        ablehnung = am1_snapshot(fall.name)
        ablehnung.update(entscheid="abgelehnt",
                         vorgaenger=[beleg["abnahmen"]["aktuartest"]["snapshot_sha256"]])
        # Eine Ablehnung traegt weder Freigabe noch Auftragsbezug (ADR-026).
        ablehnung.pop("freigabe"), ablehnung.pop("snapshot_sha256")
        ablehnung.pop("fallauftrag", None)
        ablehnung["snapshot_sha256"] = p9_snapshot_sha256(ablehnung)
        (fall / "entscheide" / f"A-M1-{ablehnung['snapshot_sha256']}.json").write_text(
            json.dumps(ablehnung), encoding="utf-8")
        erwartet = "nicht die geltende Spitze der A-M1-Kette"
    else:
        rest = {k: v for k, v in beleg.items() if k != "betriebszeichnung"}
        datei = zp.SOLL_BELEGE["migrationssuite"][1]
        rest["abnahmen"]["migrationssuite"]["sha256"] = rest["eingaben"][datei] = "5e" * 32
        rest["betriebszeichnung"] = tl.betriebszeichner(Ablage(stand)).zeichne({"zugangsprobe": rest})
        sha = _ab2_aus_beleg(fall, rest)
        erwartet = "nicht das der geltenden Abnahmen"
    with pytest.raises(ueb.UebernahmeError, match=erwartet):
        ueb.eingang_anlegen(stand, fall, STICHTAG, zugangsabnahme_sha256=sha)
    assert not (stand / "uebernahme" / "probe-uebernahme").exists()


# --------------------------------------------------------------------------- #
# Block F, Nachbesserung: das Deckungskapital, benannt statt still
# --------------------------------------------------------------------------- #


def test_kein_beleg_fuehrt_das_deckungskapital_mehr_nicht_vergleichbar(probe):
    """Bis 2026-10-01 stand das Deckungskapital mit dem Grund "nicht
    vergleichbar" im Beleg (Pruefer-Befund 3, Entscheid offen). Der Entscheid
    ist gefallen; ein Beleg, der es noch so fuehrt — als Fassung-1-Feld
    ``nicht_verglichen`` oder als Vergleich ohne Soll am Zugangsstichtag —,
    verletzt den Vertrag und besteht nicht.

    Mutationsprobe: die Pflicht der drei Groessen aus PFLICHT_AM_STICHTAG
    nehmen -> der Vergleich ohne Soll geht durch -> rot."""
    _, _, _, beleg = probe
    alt = json.loads(json.dumps(beleg))
    alt["nicht_verglichen"] = {"deckungskapital": "nicht vergleichbar: Konvention offen"}
    assert any("Fassung 1" in f for f in zp.beleg_fehler(alt))
    for g in zp.FUEHRUNGSWERT_VERGLICHEN:
        ohne = json.loads(json.dumps(beleg))
        for v in ohne["vergleiche"]:
            if v["groesse"] == g and v["termin"] == "zugangsstichtag":
                v.update(soll=None, differenz=None, ok=None, grund="nicht vergleichbar")
        assert any("ohne Soll" in f for f in zp.beleg_fehler(ohne)), g
        assert zp.bestanden_aus([v for v in ohne["vergleiche"] if v["groesse"] != g], []) is False


def test_deckungskapital_rueckkaufswert_und_schicht_werden_je_vertrag_verglichen(probe):
    """Was bis 2026-10-01 erwartet rot war (xfail, strict): Die Probe
    vergleicht Deckungskapital, Rueckkaufswert und Korrekturschicht je
    Vertrag ueber den ganzen Zugang gegen den Fuehrungswert der Suite — und
    in der Positivkontrolle gruen, weil Abschluss und Abnahme dieselbe
    Konvention rechnen."""
    _, _, _, beleg = probe
    am = {v["groesse"]: v for v in beleg["vergleiche"] if v["termin"] == "zugangsstichtag"}
    for g in zp.FUEHRUNGSWERT_VERGLICHEN:
        assert am[g]["ok"] is True and am[g]["umfang"] == len(VERTRAEGE), g
        assert am[g]["soll"] is not None and am[g]["grund"] is None, g


def _rot_nach(probe, tmp_path: Path, mutation) -> set:
    """Die roten Groessen nach einer Mutation an der Kopie "mit"."""
    wurzel, fall, _, _ = probe
    arbeit = tmp_path / "arbeit"
    shutil.copytree(wurzel / "arbeit", arbeit, symlinks=True)
    soll = _soll(fall, arbeit)
    mutation(arbeit)
    nachher, _ = zpb.vergleiche(arbeit / zpb.KOPIE_OHNE, arbeit / zpb.KOPIE_MIT, soll,
                                stichtag=STICHTAG)
    return {v["groesse"] for v in nachher if v["ok"] is False}


@pytest.mark.parametrize("mutation,rot", DK_MUTATIONEN, ids=lambda x: getattr(x, "__name__", ""))
def test_rueckrichtung_ohne_den_vergleich_bliebe_jede_dk_mutation_unbemerkt(
        probe, tmp_path, monkeypatch, mutation, rot):
    """Rueckrichtung des Zaehltests: In einer Kopie des Codes, in der der
    Vergleich gegen den Fuehrungswert ausgebaut ist (dieselben Vergleiche,
    aber ohne Soll — so stand das Deckungskapital bis 2026-10-01 im Beleg),
    wird die Mutation NICHT rot. Der Zaehltest oben haengt also an genau
    diesem Vergleich, nicht an einem Nebeneffekt."""
    echt = zpb.fuehrungswert_vergleiche

    def ausgebaut(diff, soll_fw, termin, iso, *, vorfaelle=None):
        return [dict(v, soll=None, differenz=None, ok=None)
                for v in echt(diff, soll_fw, termin, iso, vorfaelle=vorfaelle)]

    monkeypatch.setattr(zpb, "fuehrungswert_vergleiche", ausgebaut)
    assert not _rot_nach(probe, tmp_path, mutation) & rot


@pytest.mark.parametrize("mutation,rot", DK_MUTATIONEN, ids=lambda x: getattr(x, "__name__", ""))
def test_positivkontrolle_toleranz_unendlich_laesst_jede_dk_mutation_durch(
        probe, tmp_path, monkeypatch, mutation, rot):
    """Positivkontrolle: Mit unendlicher Toleranz faellt keine der
    Mutationen auf — der Zaehltest misst also die Toleranz von einem halben
    Cent und ist nicht aus einem anderen Grund rot."""
    monkeypatch.setattr(zp, "TOLERANZ", float("inf"))
    assert not _rot_nach(probe, tmp_path, mutation) & rot


def test_ratsche_jede_bewertungsgroesse_des_abschlusses_ist_verglichen_oder_benannt(probe):
    """Pruefer-Befund 8: Die Menge der Bewertungsgroessen des Abschlusses
    ist aus ``models.bestand`` HERGELEITET (ABSCHLUSS_ZAHLEN); jede ist
    entweder einer verglichenen Groesse zugeordnet oder mit Grund als
    "nicht belegt" ausgenommen — beides mit ``==``, disjunkt. Der Beleg
    traegt dieselbe Abdeckung, und jede zugeordnete Groesse steht am
    Stichtag gruen oder mit dem Grund, aus dem sie (noch) nicht verglichen
    wird.

    Mutationsprobe: ``vs_bfr`` aus ABSCHLUSS_NICHT_BELEGT streichen -> rot;
    eine neue float-Spalte im Abschluss -> rot."""
    from rechner_pipeline.models.bestand import ABSCHLUSS_ZAHLEN

    verglichen, ausgenommen = set(zp.ABSCHLUSS_VERGLICHEN), set(zp.ABSCHLUSS_NICHT_BELEGT)
    assert verglichen | ausgenommen == set(ABSCHLUSS_ZAHLEN)
    assert not verglichen & ausgenommen
    assert set(zp.ABSCHLUSS_VERGLICHEN.values()) <= set(zp.GROESSEN)
    assert all(g.startswith("nicht belegt") for g in zp.ABSCHLUSS_NICHT_BELEGT.values())
    _, _, _, beleg = probe
    assert beleg["abdeckung"] == zp.abdeckung()
    am = {v["groesse"]: v for v in beleg["vergleiche"] if v["termin"] == "zugangsstichtag"}
    for groesse in zp.ABSCHLUSS_VERGLICHEN.values():
        assert am[groesse]["ok"] is True, groesse


# --------------------------------------------------------------------------- #
# Block F, Nachbesserung: der tatsaechliche Eintritt eines vorausdatierten Eingangs
# --------------------------------------------------------------------------- #


@pytest.fixture(scope="module")
def vorausdatiert(tmp_path_factory):
    """Eine Ablage, die schon fuehrt (bis 2025-12-10); Probe, A-B2 und
    Registrierung zum 2026-01-01; der Lauf am 2025-12-11 nimmt den Eingang
    WARTEND auf. Tests kopieren die Ablage und fahren den Stichtag."""
    import pytest as _pytest

    wurzel = tmp_path_factory.mktemp("vorausdatiert")
    fall, stand = _welt(wurzel)
    assert tageslauf(Ablage(stand), dt.date(2025, 12, 10))[0] == EXIT_OK
    beleg = zpb.zugangsprobe(stand, fall, STICHTAG)
    assert beleg["bestanden"] is True, beleg["befunde"]
    sha = _ab2_aus_beleg(fall, beleg)
    mp = _pytest.MonkeyPatch()
    mp.setattr(ueb, "_STANDARD_ZUGANGSABNAHME", None)
    try:
        ueb.eingang_anlegen(stand, fall, STICHTAG, zugangsabnahme_sha256=sha)
    finally:
        mp.undo()
    code, zeile = tageslauf(Ablage(stand), dt.date(2025, 12, 11))
    assert code == EXIT_OK, zeile.get("fehler")
    assert [u["fall"] for u in zeile["wartende_uebernahmen"]] == ["probe-uebernahme"]
    return stand


def _kopie(stand: Path, ziel: Path) -> Ablage:
    shutil.copytree(stand, ziel, symlinks=True)
    return Ablage(ziel)


def test_ein_vorausdatierter_eingang_tritt_auf_dem_geprobten_stand_ein(vorausdatiert, tmp_path):
    """Positivkontrolle: Nichts geaendert — der Eingang tritt am Stichtag ein."""
    ablage = _kopie(vorausdatiert, tmp_path / "daten")
    code, zeile = tageslauf(ablage, dt.date(2026, 1, 5))
    assert code == EXIT_OK, zeile.get("fehler")
    assert [u["fall"] for u in zeile["uebernahmen"]] == ["probe-uebernahme"]


def test_config_nach_der_wartenden_aufnahme_getauscht_der_eingang_tritt_nicht_ein(
        vorausdatiert, tmp_path):
    """Pruefer-Befund 2, Repro A: Die Stand-Bindung galt der wartenden
    Aufnahme; danach wurde die Config getauscht, und der Lauf am Stichtag
    fuehrte den Eingang mit Exit 0 — auf einem Stand, den niemand geprobt
    hatte. Jetzt haelt der tatsaechliche Eintritt Config, Kern und
    Code-Stand gegen die Zugangsabnahme.

    Mutationsprobe: den Aufruf von pruefe_eintritt in _stand_bauen
    entfernen -> Exit 0 -> rot."""
    ablage = _kopie(vorausdatiert, tmp_path / "daten")
    ablage.config_pfad.write_text(
        ablage.config_pfad.read_text(encoding="utf-8") + "\n# getauscht nach der Probe\n",
        encoding="utf-8")
    code, zeile = tageslauf(ablage, dt.date(2026, 1, 5))
    assert code != EXIT_OK and zeile["uebernommen"] is False
    assert "anderen Stand ein, als die Zugangsprobe geprobt hat" in zeile["fehler"]
    assert "Config" in zeile["fehler"] and "Zugangsprobe und A-B2 auf dem heutigen Stand neu" in zeile["fehler"]


def test_code_nach_der_wartenden_aufnahme_getauscht_der_eingang_tritt_nicht_ein(
        vorausdatiert, tmp_path, monkeypatch):
    """Dasselbe mit einem anderen Code-Stand (Image oder Paket getauscht,
    Kern-Version gleich): Der Hash des Pakets faengt es.

    Mutationsprobe: in pruefe_eintritt code_stand_abweichungen nicht
    rufen -> Exit 0 -> rot."""
    ablage = _kopie(vorausdatiert, tmp_path / "daten")
    monkeypatch.setattr(tl, "quellcode_sha256", lambda: "c0" * 32)
    code, zeile = tageslauf(ablage, dt.date(2026, 1, 5))
    assert code != EXIT_OK and "quellcode_sha256" in zeile["fehler"]


# --------------------------------------------------------------------------- #
# Block F, Nachbesserung: der Code-Stand der Probe gegen den des Betriebs
# --------------------------------------------------------------------------- #


def test_die_probe_haelt_ihren_code_stand_gegen_die_letzte_gruene_zeile(tmp_path, monkeypatch):
    """Pruefer-Befund 6: 'Produktives Image' war auf einen Vergleich der
    Kern-Version geschrumpft. Die Ablage wurde mit dem Image X gefuehrt
    (Digest in der Zeile); die Probe nennt keins, oder ihr Paket ist ein
    anderes — beides ist ein Befund, die Probe besteht nicht.

    Mutationsprobe: in zugangsprobe() code_stand_abweichungen nicht rufen
    -> gruen -> rot."""
    fall, stand = _welt(tmp_path)
    assert tageslauf(Ablage(stand), dt.date(2025, 12, 10),
                     image_digest="sha256:" + "d1" * 32)[0] == EXIT_OK
    ohne_image = zpb.zugangsprobe(stand, fall, STICHTAG)
    assert ohne_image["bestanden"] is False
    assert any("image_digest" in b and "anderen Code-Stand" in b for b in ohne_image["befunde"])
    mit_image = zpb.zugangsprobe(stand, fall, STICHTAG, image_digest="sha256:" + "d1" * 32)
    assert mit_image["bestanden"] is True, mit_image["befunde"]
    monkeypatch.setattr(tl, "quellcode_sha256", lambda: "c0" * 32)
    anderer_code = zpb.zugangsprobe(stand, fall, STICHTAG, image_digest="sha256:" + "d1" * 32)
    assert any("quellcode_sha256" in b for b in anderer_code["befunde"])


def test_die_probe_nennt_eine_andere_kern_version_als_befund(tmp_path, monkeypatch):
    """Die Kern-Version bleibt ein Befund (Mutation P10) — neben dem Code-Stand.

    Die Ablage wurde mit einer anderen Kern-Version gefuehrt (hier: ein
    frueherer Lauf unter vorgeblich altem Kern); dieselbe Probe mit dem
    heutigen besteht nicht."""
    import rechner_pipeline.kern as kern

    fall, stand = _welt(tmp_path)
    with monkeypatch.context() as m:
        m.setattr(kern, "__version__", "0.0.0-alt")
        assert tageslauf(Ablage(stand), dt.date(2025, 12, 10))[0] == EXIT_OK
    beleg = zpb.zugangsprobe(stand, fall, STICHTAG)
    assert beleg["bestanden"] is False
    assert any("Kern 0.0.0-alt" in b for b in beleg["befunde"])


def test_die_probe_verweigert_auf_einer_ablage_die_den_stichtag_schon_fuehrt(tmp_path):
    """Mutation P9: Der Abschluss am Zugangsstichtag steht schon fest (ADR-011)."""
    fall, stand = _welt(tmp_path)
    assert tageslauf(Ablage(stand), STICHTAG)[0] == EXIT_OK
    with pytest.raises(zpb.ZugangsprobeError, match="fuehrt bereits 2026-01-01"):
        zpb.zugangsprobe(stand, fall, STICHTAG)


# --------------------------------------------------------------------------- #
# Block F, Nachbesserung: je Abwehrstelle ein Angreifer OHNE Schluessel
# --------------------------------------------------------------------------- #


@pytest.fixture(scope="module")
def probe_mit_ab2(tmp_path_factory):
    """Welt, bestandene Probe und die A-B2, die sie pinnt — zum Kopieren."""
    wurzel = tmp_path_factory.mktemp("probe-ab2")
    fall, stand = _welt(wurzel / "w")
    beleg = zpb.zugangsprobe(stand, fall, STICHTAG)
    assert beleg["bestanden"] is True, beleg["befunde"]
    return wurzel / "w", beleg


def _welt_kopie(probe_mit_ab2, ziel: Path):
    shutil.copytree(probe_mit_ab2[0], ziel, symlinks=True)
    return ziel / "probe-uebernahme", ziel / "daten", json.loads(json.dumps(probe_mit_ab2[1]))


def test_p1_eine_unsigniert_umgeschriebene_zugangsabnahme_tritt_nicht_ein(tmp_path):
    """Der Angreifer ohne Betriebsschluessel tauscht die Config und schreibt
    zugangsabnahme.json auf die neue Wirklichkeit um (Stand und Config) —
    jede Bindung stimmt, nur die Signatur nicht."""
    from rechner_pipeline.models.zugangsprobe import stand_sha256

    _, stand, ziel = _registriert(tmp_path)
    ablage = Ablage(stand)
    ablage.config_pfad.write_text(ablage.config_pfad.read_text(encoding="utf-8") + "\n# getauscht\n",
                                  encoding="utf-8")
    pfad = ziel / ueb.ZUGANGSABNAHME_DATEI
    daten = json.loads(pfad.read_text(encoding="utf-8"))
    daten["ablage_stand_sha256"] = stand_sha256(tl.ablage_stand(ablage))
    daten["bindung"]["config_sha256"] = hashlib.sha256(ablage.config_pfad.read_bytes()).hexdigest()
    pfad.chmod(0o644)
    pfad.write_text(json.dumps(daten), encoding="utf-8")
    code, zeile = tageslauf(ablage, FOLGETERMIN)
    assert code != EXIT_OK and "Signatur stimmt nicht" in zeile["fehler"]


def test_p2_eine_abnahme_ohne_angenommene_a_b2_tritt_nicht_ein(tmp_path):
    """Hinter der Signatur (neu gezeichnet: der Faelscher MIT Schluessel —
    die einzige Art, diese Stelle zu erreichen): eine abgelehnte A-B2."""
    _, stand, ziel = _registriert(tmp_path)
    pfad = ziel / ueb.ZUGANGSABNAHME_DATEI
    a_b2 = json.loads(pfad.read_text(encoding="utf-8"))["a_b2"]
    _neu_zeichnen(pfad, a_b2={**a_b2, "entscheid": "abgelehnt"})
    code, zeile = tageslauf(Ablage(stand), FOLGETERMIN)
    assert code != EXIT_OK and "keine angenommene A-B2" in zeile["fehler"]


def test_p3_ein_beleg_mit_falscher_betriebssignatur(tmp_path, ohne_naht, probe_mit_ab2):
    """Der Angreifer ohne Betriebsschluessel faelscht einen gruenen Beleg
    (Signatur mit gueltiger Form). Das Gate kann die Signatur nicht
    nachrechnen und SAGT das (Befund 7) — die Registrierung rechnet sie nach
    und verweigert."""
    fall, stand, beleg = _welt_kopie(probe_mit_ab2, tmp_path / "w")
    beleg["betriebszeichnung"]["signatur"] = "00" * 32
    sha = _ab2_aus_beleg(fall, beleg)
    with pytest.raises(ueb.UebernahmeError, match="Signatur stimmt nicht"):
        ueb.eingang_anlegen(stand, fall, STICHTAG, zugangsabnahme_sha256=sha)


def test_p4_ein_nach_a_b2_ersetzter_beleg(tmp_path, ohne_naht, probe_mit_ab2):
    """Derselbe Beleg in anderen Bytes (umformatiert, Signatur weiter
    gueltig): A-B2 pinnt Bytes, nicht Inhalte."""
    fall, stand, beleg = _welt_kopie(probe_mit_ab2, tmp_path / "w")
    sha = _ab2_aus_beleg(fall, beleg)
    (fall / zp.BELEG_RELATIV).write_text(json.dumps(beleg), encoding="utf-8")
    with pytest.raises(ueb.UebernahmeError, match="nicht der Beleg, den A-B2 pinnt"):
        ueb.eingang_anlegen(stand, fall, STICHTAG, zugangsabnahme_sha256=sha)


def test_p5_eine_a_b2_mit_fremdem_am4_pin(tmp_path, ohne_naht, probe_mit_ab2):
    fall, stand, beleg = _welt_kopie(probe_mit_ab2, tmp_path / "w")
    sha = _ab2_aus_beleg(fall, beleg, am4_sha="a4" * 32)
    with pytest.raises(ueb.UebernahmeError, match="gilt einer anderen Migrationsabnahme"):
        ueb.eingang_anlegen(stand, fall, STICHTAG, zugangsabnahme_sha256=sha)


def test_p6_eine_a_b2_mit_fremdem_eingang_pin(tmp_path, ohne_naht, probe_mit_ab2):
    fall, stand, beleg = _welt_kopie(probe_mit_ab2, tmp_path / "w")
    sha = _ab2_aus_beleg(fall, beleg, eingang_sha="e1" * 32)
    with pytest.raises(ueb.UebernahmeError, match="pinnt einen anderen Eingang als die Probe"):
        ueb.eingang_anlegen(stand, fall, STICHTAG, zugangsabnahme_sha256=sha)


def test_p7_das_gate_nimmt_keine_probe_eines_fremden_falls_an(gatefall):
    """Ein vertragsgerechter, gezeichneter Beleg eines anderen Falls — auf
    derselben Migrationsabnahme, also ohne Widerspruch sonst."""
    from tests.zugangsabnahme_testhelfer import probenbeleg

    fall, am4, beleg, schluessel, testkey, ordnung = gatefall
    eingang = {"fall": "anderer-fall", "snapshot_sha256": am4["snapshot_sha256"],
               "stichtag": STICHTAG.isoformat()}
    fremd = probenbeleg("anderer-fall", ablage_stand=beleg["ablage_stand"]["inhalt"],
                        eingang_roh=json.dumps(eingang).encode("utf-8"),
                        am4_snapshot_sha256=am4["snapshot_sha256"], abnahmen=beleg["abnahmen"],
                        zeichner=tl.betriebszeichner(Ablage(fall.parent / "irgendeine-ablage")))
    assert zp.beleg_fehler(fremd) == []
    (fall / zp.BELEG_RELATIV).write_text(json.dumps(fremd), encoding="utf-8")
    ergebnis = _ab2(fall, schluessel=schluessel["mensch"], testkey=testkey, ordnung=ordnung)
    assert ergebnis.exit_code != 0 and "gehoert zum Fall 'anderer-fall'" in ergebnis.errors[0]["message"]


@pytest.mark.parametrize("abweichung", ["quelle", "stichtag"])
def test_die_registrierung_braucht_dieselben_angaben_wie_die_probe(
        tmp_path, ohne_naht, probe_mit_ab2, abweichung):
    """Registriert mit einer anderen Quelle (dieselben Bytes, anderer Ort)
    oder einem anderen Stichtag als die Probe: Der Eingang ist ein anderer
    als der abgenommene, die Meldung nennt das Feld."""
    fall, stand, beleg = _welt_kopie(probe_mit_ab2, tmp_path / "w")
    sha = _ab2_aus_beleg(fall, beleg)
    kwargs = {}
    tag = STICHTAG
    if abweichung == "quelle":
        kwargs["quelle"] = tmp_path / "anderswo"
        shutil.copytree(fall / "abgeleitet" / "bestand", kwargs["quelle"])
    else:
        tag = FOLGETERMIN
    with pytest.raises(ueb.UebernahmeError, match=f"verschieden: .*{abweichung}"):
        ueb.eingang_anlegen(stand, fall, tag, zugangsabnahme_sha256=sha, **kwargs)


def test_die_a_b2_freigabe_braucht_eine_rolle_mit_a_b2(tmp_path, ohne_naht, probe_mit_ab2):
    """Pruefer-Befund 9: Die Registrierung haelt den Fingerabdruck der
    A-B2-Freigabe gegen die Zeichnungsordnung des Betriebs — ein Schluessel,
    den sie keiner Rolle mit A-B2 zuordnet, zeichnet keine Zugangsabnahme,
    auch wenn seine Signatur stimmt.

    Mutationsprobe: uebernahme.zeichnende_rolle verweigert nie (die eine
    Regel fuer A-M1, A-M4 und A-B2, Entscheid 2026-10-01; gerufen im Leser
    und in _zugangsabnahme_binden) -> die Registrierung geht durch -> rot."""
    from tests.freigabe_testschluessel import FREMDER_SCHLUESSEL, TESTRING

    fall, stand, beleg = _welt_kopie(probe_mit_ab2, tmp_path / "w")
    sha = _ab2_aus_beleg(fall, beleg, schluessel=FREMDER_SCHLUESSEL)
    ring = {**TESTRING, hashlib.sha256(FREMDER_SCHLUESSEL).hexdigest(): FREMDER_SCHLUESSEL}
    with pytest.raises(ueb.UebernahmeError, match="keiner Rolle zuordnet"):
        ueb.eingang_anlegen(stand, fall, STICHTAG, zugangsabnahme_sha256=sha, schluesselring=ring)
    assert not (stand / "uebernahme" / "probe-uebernahme").exists()


def test_das_gate_sagt_dass_es_die_betriebssignatur_nicht_verifiziert(gatefall):
    """Pruefer-Befund 7: Das Gate haelt den Betriebsschluessel nicht. Es
    nimmt einen Beleg mit gefaelschter Betriebssignatur an (Form stimmt),
    SAGT aber in seiner Ausgabe, dass es sie nicht verifiziert hat — die
    Registrierung rechnet sie nach (test_p3_...)."""
    from rechner_pipeline.gates.gate_entscheid import BETRIEBSSIGNATUR_NICHT_VERIFIZIERT

    fall, _, beleg, schluessel, testkey, ordnung = gatefall
    beleg["betriebszeichnung"]["signatur"] = "00" * 32
    (fall / zp.BELEG_RELATIV).write_text(json.dumps(beleg), encoding="utf-8")
    ergebnis = _ab2(fall, schluessel=schluessel["mensch"], testkey=testkey, ordnung=ordnung)
    assert ergebnis.exit_code == 0, ergebnis.errors
    ledger = json.loads((fall / "abgeleitet" / "diagnostics" / "gate_entscheid_ab2.gate.json")
                        .read_text(encoding="utf-8"))
    assert ledger["summary"]["betriebssignatur"] == BETRIEBSSIGNATUR_NICHT_VERIFIZIERT
    assert BETRIEBSSIGNATUR_NICHT_VERIFIZIERT.startswith("nicht verifiziert")
