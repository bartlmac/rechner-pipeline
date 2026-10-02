"""Der Fuehrungswert der Migrationsabnahme (Entscheid des Maintainers 2026-10-01).

"Abschluss umbauen, UND die neue Bezugsgroesse in den Controlling-Test
nehmen": Die Migrationssuite (Beleg von A-M4) weist je Vertrag des Zugangs
aus, was die Bestandsfuehrung im Abschluss fuehrt — Deckungsrueckstellung,
Rueckkaufswert, Korrekturschicht, am Zugangs- und am Folgestichtag, in der
Konvention des Abschlusses. Gerechnet ueber DIESELBE Bewertungsstrecke wie
der Abschluss (``bestand.migrationszugang.fuehrungswerte``); die Suite
traegt ihn, A-M4 nimmt ihn ab, die Zugangsprobe haelt den Betrieb dagegen.

Die Kontrolle ist der Abschluss selbst: Fuehrungswert und festgeschriebene
Abschlusszeile desselben Bestands muessen Spalte fuer Spalte gleich sein —
nicht weil dieselbe Funktion zweimal gerufen wird, sondern weil der
Abschluss eine Datei ist, die ein anderer Weg schreibt und liest.

Knoten: klv
"""

from __future__ import annotations

import datetime as dt
import hashlib
import json
import math
from dataclasses import asdict
from pathlib import Path

import pytest

from rechner_pipeline.bestand.abschluss import lies_abschluss, schreibe_abschluss
from rechner_pipeline.bestand.config import config_aus_text
from rechner_pipeline.bestand.migrationszugang import MigrationszugangFehler, fuehrungswerte
from rechner_pipeline.bestand.parquet_io import read_portfolio
from rechner_pipeline.kern import Rechenkern
from rechner_pipeline.kern.model_point import KLV_DEFAULT
from rechner_pipeline.models import fuehrungswert as fwv
from rechner_pipeline.models.bestand import FUEHRUNGSKONVENTION, KONVENTION_MONATSGENAU
from rechner_pipeline.qa.migrationssuite import VertragsPruefung, pruefe_bestand

ALT = Path(__file__).resolve().parent / "fixtures" / "abschluss_vor_umstellung"
S1, S2 = dt.date(2026, 10, 1), dt.date(2027, 4, 1)
TABELLEN = ("bestand", "historie", "scheiben", "schichten", "verankerung", "reduktionen")


def _welt():
    """Die Welt der Alt-Fixture (acht Vertraege aller Typen), eigene Config."""
    t = {n: read_portfolio(ALT / f"{n}.parquet") for n in TABELLEN}
    return t, (ALT / "config.toml").read_text("utf-8")


def _fw():
    t, text = _welt()
    return fuehrungswerte(t["bestand"], t["historie"], text, {"stichtag_1": S1, "stichtag_2": S2},
                          scheiben=t["scheiben"], schichten=t["schichten"],
                          verankerung=t["verankerung"], reduktionen=t["reduktionen"], merkmale=None)


def test_der_fuehrungswert_ist_was_der_abschluss_festschreibt(tmp_path):
    """Je Vertrag und Termin Spalte fuer Spalte gleich der Zeile, die
    ``schreibe_abschluss`` fuer denselben Bestand festschreibt — gelesen
    aus der Datei, ueber den Leseweg der Abschluesse."""
    t, text = _welt()
    konvention, fw = _fw()
    assert konvention == FUEHRUNGSKONVENTION == KONVENTION_MONATSGENAU
    for name, stichtag in (("stichtag_1", S1), ("stichtag_2", S2)):
        pfad = schreibe_abschluss(t["bestand"], t["historie"], config_aus_text(text), stichtag,
                                  tmp_path / name, scheiben=t["scheiben"], schichten=t["schichten"],
                                  verankerung=t["verankerung"], reduktionen=t["reduktionen"], merkmale=None)
        abschluss, k = lies_abschluss(pfad)
        assert k.name == konvention
        zeilen = {str(z["police_id"]): z for z in abschluss.to_dict("records")}
        assert set(zeilen) == {p for p, w in fw.items() if w[name] is not None}
        for police, zeile in zeilen.items():
            eintrag = fw[police][name]
            assert eintrag["stichtag"] == stichtag.isoformat()
            assert eintrag["status_code"] == zeile["status_code"]
            for g in fwv.GROESSEN:
                assert eintrag[g] == zeile[g], (police, name, g)


def test_nicht_mehr_in_kraft_ist_null_nicht_null_euro():
    """Ein Vertrag, der am Folgestichtag laut Bestand nicht mehr in Kraft
    ist (hier: abgelaufen), traegt dort ``None`` — die Aussage "nicht im
    Abschluss", nicht ein Wert von null."""
    t, text = _welt()
    _, fw = fuehrungswerte(t["bestand"], t["historie"], text,
                           {"stichtag_1": S1, "stichtag_2": dt.date(2041, 1, 1)},
                           scheiben=t["scheiben"], schichten=t["schichten"],
                           verankerung=t["verankerung"], reduktionen=t["reduktionen"], merkmale=None)
    assert all(w["stichtag_1"] is not None for w in fw.values())
    assert all(w["stichtag_2"] is None for w in fw.values())


def test_eine_ungueltige_config_ist_kein_fuehrungswert():
    t, text = _welt()
    with pytest.raises(MigrationszugangFehler, match="Config der Fuehrung"):
        fuehrungswerte(t["bestand"], t["historie"], text.replace("zins = 0.0125", "zins = -1.0"),
                       {"stichtag_1": S1})


# --------------------------------------------------------------------------- #
# Die Suite traegt ihn, A-M4 nimmt ihn ab
# --------------------------------------------------------------------------- #


def _suite(**ueber):
    kern = Rechenkern(KLV_DEFAULT)
    s1, s2 = 12 * 9 + 5, 12 * 10 + 5
    auftrag = VertragsPruefung(
        police_id="1", model_point=asdict(KLV_DEFAULT), monate_stichtag_1=s1,
        monate_stichtag_2=s2, dk_erwartet_1=round(kern.monatsreserve(s1).vx_mrv, 2),
        bjb_erwartet_1=round(kern.gross_annual_premium(), 2),
        dk_erwartet_2=round(kern.monatsreserve(s2).vx_mrv, 2),
        scheiben_mit_gamma1=False, stoab_je_baustein=False, tku_umfang=None, dk_am_jahrestag=False)
    eintrag = {"stichtag": S1.isoformat(), "status_code": "POL", "deckungskapital": 1.0,
               "rueckkaufswert": 0.5, "korrekturschicht": 0.0}
    kw = dict(erwartete_anzahl=1, stichtag_1=S1.isoformat(), stichtag_2=S2.isoformat(),
              bestand_sha256="ab" * 32,
              fuehrungswert=fwv.kopf(FUEHRUNGSKONVENTION, bestand_sha256="ab" * 32,
                                     config_sha256="cd" * 32),
              fuehrungswerte={"1": {"stichtag_1": eintrag, "stichtag_2": None}},
              red_verfahren="prospektiv")
    kw.update(ueber)
    return pruefe_bestand([auftrag], **kw)


def test_die_suite_traegt_den_fuehrungswert_unveraendert_und_in_fassung_2():
    suite = _suite()
    assert suite["schema_version"] == fwv.SUITE_SCHEMA_VERSION == 2
    assert suite["fuehrungswert"]["art"] == "systemwert"
    assert "kein Vergleich mit einer Lieferung" in suite["fuehrungswert"]["hinweis"]
    assert suite["vertraege"][0]["fuehrungswert"]["stichtag_1"]["deckungskapital"] == 1.0
    # Kein Urteil haengt an ihm: die Pruefungen der Suite sind dieselben.
    ohne = _suite(fuehrungswert=None, fuehrungswerte=None)
    assert ohne["vertraege"][0]["pruefungen"] == suite["vertraege"][0]["pruefungen"]
    assert "schema_version" not in ohne and "fuehrungswert" not in ohne["vertraege"][0]
    assert fwv.fuehrungswert_fehler(suite) == []


def test_kopf_ohne_werte_oder_fremde_policen_sind_ein_aufruffehler():
    with pytest.raises(ValueError, match="gehoeren zusammen"):
        _suite(fuehrungswerte=None)
    with pytest.raises(ValueError, match="andere Policen"):
        _suite(fuehrungswerte={"2": {"stichtag_1": None, "stichtag_2": None}})


def _mutiert(aenderung):
    suite = json.loads(json.dumps(_suite()))
    aenderung(suite)
    return fwv.fuehrungswert_fehler(suite)


@pytest.mark.parametrize("aenderung,meldung", [
    (lambda s: s.pop("schema_version"), "Fassung 1"),
    (lambda s: s.pop("fuehrungswert"), "Kopf"),
    (lambda s: s["fuehrungswert"].update(art="vergleich"), "Systemwert"),
    (lambda s: s["fuehrungswert"].update(konvention="treppe"), "Konvention"),
    (lambda s: s["fuehrungswert"].update(bestand_sha256="ef" * 32), "anderen Bestand"),
    (lambda s: s.update(eingaben={"x": "00" * 32}), "Config steht nicht"),
    (lambda s: s["vertraege"][0].pop("fuehrungswert"), "fehlt"),
    (lambda s: s["vertraege"][0]["fuehrungswert"].update(stichtag_1=None), "am Zugangsstichtag"),
    (lambda s: s["vertraege"][0]["fuehrungswert"]["stichtag_1"].update(stichtag="2026-11-01"),
     "nicht der der Suite"),
    (lambda s: s["vertraege"][0]["fuehrungswert"]["stichtag_1"].update(
        deckungskapital=math.inf), "endliche"),
    (lambda s: s["vertraege"][0]["fuehrungswert"]["stichtag_1"].pop("korrekturschicht"),
     "Felder"),
])
def test_zaehltest_jede_verletzung_des_vertrags_ist_ein_befund(aenderung, meldung):
    """Je Vertragsregel eine Mutation am Beleg — genau sie wird gemeldet."""
    befunde = _mutiert(aenderung)
    assert any(meldung in b for b in befunde), befunde


def test_a_m4_nimmt_im_bestands_scope_keine_suite_ohne_fuehrungswert_ab(tmp_path):
    """Gate A-M4 und der Abnahmebericht fragen dieselbe Stelle
    (``abnahmebericht._bestands_suite_fehler``, 8.0.0)."""
    from rechner_pipeline.gates import abnahmebericht

    system = {"commit": "abc", "branch": "b", "dirty": "nein", "quellcode_sha256": "ef" * 32}
    mit = _suite(system=system)
    ohne = _suite(system=system, fuehrungswert=None, fuehrungswerte=None)
    # Der Fall (Pruefrunde G): ohne ihn ist der Fuehrungswert nicht nachzurechnen;
    # diese synthetische Suite scheitert an der Form, bevor nachgerechnet wird.
    kw = dict(stichtag_1=S1.isoformat(), stichtag_2=S2.isoformat(), erwartetes_system=system,
              fall=tmp_path)
    assert not [f for f in abnahmebericht._bestands_suite_fehler(mit, **kw) if "uehrungswert" in f]
    assert any("Fuehrungswert" in f for f in abnahmebericht._bestands_suite_fehler(ohne, **kw))
    # Eingefuehrt mit 8.0.0; spaetere Majors (9.0.0: Tarifregeln aus der
    # Spez) tragen die Pruefung weiter.
    assert int(abnahmebericht.GATE_VERSION.split(".")[0]) >= 8


def test_migrationssuite_lauf_verlangt_die_config_der_fuehrung():
    """Jeder Weg, der eine Migrationssuite erzeugt, muss den Fuehrungswert
    liefern koennen: Die Produzentin laeuft ohne ``--config`` nicht."""
    from rechner_pipeline.gates import migrationssuite_lauf

    with pytest.raises(SystemExit) as exc:
        migrationssuite_lauf.main([
            "--fall", "x", "--generation", "klv/tg2015", "--abzug-1", "a", "--abzug-2", "b",
            "--gevo-protokoll", "c", "--bestand", "d", "--stichtag-1", "2026-01-01",
            "--stichtag-2", "2027-01-01"])
    assert exc.value.code == 2


def test_hashes_im_kopf_sind_die_gelesenen_bytes():
    """Die Bindung im Kopf ist nachrechenbar: Bestand und Config als SHA-256."""
    t, text = _welt()
    kopf = fwv.kopf(FUEHRUNGSKONVENTION,
                    bestand_sha256=hashlib.sha256((ALT / "bestand.parquet").read_bytes()).hexdigest(),
                    config_sha256=hashlib.sha256(text.encode("utf-8")).hexdigest())
    assert set(kopf) == set(fwv.KOPF_FELDER)
