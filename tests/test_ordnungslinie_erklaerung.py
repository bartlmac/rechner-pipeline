"""Ein Glied, das ein Recht mindert, sagt gezeichnet, was mit den frueheren Zeichnungen geschieht.

Befund der blinden Pruefrunde H (H10, hoch; H06, mittel; eine Klasse):
"Gezeichnet wird nur unter der Spitze der Versionslinie" hielt nur gegen die
Linie, die der Aufruf bekam. Eine AELTERE KOPIE der Linie (Stand vor einem
spaeter angehaengten Glied) bestand die Identitaetspruefung des Auftrags; der
Vorstand entzog einer Rolle mit Glied 2 den Schluessel, unter der Kopie
zeichnete der entzogene Schluessel A-Q1, A-M1 und A-M4, und der Leser des
Betriebs nahm die A-M4 unter der ECHTEN Linie an (er hielt die Rolle gegen das
gepinnte Glied 1). H06 ebenso mit einem Gate-Entzug: A-T1 unter der Kopie,
A-M4 unter der echten Linie nahm an.

Invariante: Eine Annahme gilt einem gruendenden Leser nur, wenn die Linie, die
ER haelt, sie traegt — fuer jede Rolle, die ein spaeteres Glied mindert, nach
der gezeichneten Erklaerung des Vorstands in diesem Glied: ``verfallen``
verweigert, gleich wann gezeichnet wurde; ``gueltig`` traegt Zeichnungen VOR
der Abloesung (Zeitregel als Plausibilitaet). Menge: jeder gruendende Leser
geht durch ``models.zeichnung.zeichnende_rolle_fehler`` ->
``models.ordnungslinie.damalige_ordnung`` (Ratsche unten). Die Glieder der
Linie selbst prueft ``lade_linie`` Glied fuer Glied; die Erklaerung wirkt auf
Abnahmen, nicht auf Glieder.

Mutationsproben (Rueckmeldung der Runde): Zweig "verfallen" entfernt ->
``test_a_*`` rot; Zeitregel entfernt -> ``test_c_*`` und ``test_e_*`` rot;
Pruefung der Erklaerung in ``glied_fehler`` entfernt -> ``test_d_*`` rot;
Erklaerung auf die Glieder angewandt -> ``test_vorstand_a_*`` rot.

Knoten: system/entscheid
"""

from __future__ import annotations

import ast
import datetime as dt
import hashlib
import inspect
import json
import secrets
import shutil
from pathlib import Path

import pytest

from rechner_pipeline.betrieb import uebernahme as ueb
from rechner_pipeline.gates import gate_entscheid, stand_belegen, tarifwerk_belegen
from rechner_pipeline.models import ordnungslinie as ol
from rechner_pipeline.models.freigabe import lade_schluesselring
from tests.test_erstabnahme_linie import _fall_mit_linie, _verweise, _zeichne_in_linie
from tests.zeichnung_fixture import (
    VA,
    VORSTAND_SCHLUESSEL_DATEI,
    annahme_args,
    linie_anlegen,
)

REPO = Path(__file__).resolve().parents[1]
SRC = REPO / "src" / "rechner_pipeline"


# --------------------------------------------------------------------------- #
# Helfer
# --------------------------------------------------------------------------- #


def _schluessel(datei: Path) -> Path:
    datei.parent.mkdir(parents=True, exist_ok=True)
    datei.write_bytes(secrets.token_bytes(64))
    datei.chmod(0o600)
    return datei


def _fp(datei: Path) -> str:
    return hashlib.sha256(datei.read_bytes()).hexdigest()


def _ordnung(verzeichnis: Path) -> dict:
    return json.loads((verzeichnis / "zeichnungsordnung.json").read_text(encoding="utf-8"))


def _anhaengen(linie: Path, ordnung: dict, datei: Path, *, erklaerung: dict,
               vorstand: list, eingetragen: "str | None" = None):
    """Ein Glied ueber den echten Produzenten anhaengen (der letzte Schluessel
    des Vorstands zeichnet)."""
    datei.write_text(json.dumps(ordnung, sort_keys=True), encoding="utf-8")
    glieder, fehler = ol.lade_linie_strukturell_zur_anzeige(linie)
    assert not fehler, fehler
    argv = ["ordnung", "--linie", str(linie), "--ordnung", str(datei),
            "--vorgaenger", glieder[-1]["glied_sha256"]]
    for v in vorstand:
        argv += ["--vorstand-schluessel", str(v)]
    for rolle, wert in erklaerung.items():
        argv += ["--fruehere-zeichnungen", f"{rolle}={wert}"]
    if eingetragen is not None:
        argv += ["--eingetragen-am", eingetragen]
    return stand_belegen.main(argv)


def _ersetze(args: list, schalter: str, wert) -> list:
    neu = list(args)
    neu[neu.index(schalter) + 1] = str(wert)
    return neu


def _entscheid(fall: Path, gate: str, args: list):
    return gate_entscheid.main([
        "--fall", str(fall), "--gate", gate, "--entscheid", "angenommen",
        "--entscheider", "rolle", "--begruendung", f"{gate} (Runde H)",
        "--repo-root", str(REPO), *args])


def _ring(tmp_path: Path) -> dict:
    dateien = sorted(tmp_path.glob("*.key")) + sorted((tmp_path / "aussen").glob("*.key"))
    ring, fehler, _ = lade_schluesselring([str(p) for p in dateien], ausserhalb=tmp_path / "fall")
    assert not fehler, fehler
    return ring


def _betrieb_liest_am4(tmp_path: Path, fall: Path, linie: Path, sha: str):
    """Der eine Leser des Betriebs, unter der ECHTEN Linie."""
    ring = _ring(tmp_path)
    glieder, fehler = ol.lade_linie(linie, ring=ring)
    assert not fehler, fehler
    return ueb.lies_am4_snapshot(fall, sha, schluesselring=ring, ordnung=None,
                                 ordnungslinie=glieder)


def _uhr_zurueck(monkeypatch, vor: str, stunden: int = 1) -> None:
    """Die Naht der Uhr des Gates: ``entschieden_am`` vor ``vor`` stellen —
    der Angreifer mit zurueckgestellter Uhr."""
    zeit = (dt.datetime.fromisoformat(vor) - dt.timedelta(hours=stunden)).isoformat()
    monkeypatch.setattr(gate_entscheid, "utc_now", lambda: zeit)


def _welt(tmp_path: Path):
    """Linie (Glied 1), Erstabnahmen A-K2/A-O1/A-T1, ein beauftragter Fall
    mit A-Q1, A-M1, P-K1 und den drei Verweisen — bereit fuer A-M4. Dazu die
    Argumente des Normalwegs, EINMAL vor jedem neuen Glied gebaut (der Helfer
    haengte sonst die alte Ordnung wieder an)."""
    linie, fall = _fall_mit_linie(tmp_path)
    _verweise(fall, linie)
    return linie, fall, annahme_args(fall)


def _schluesselwechsel_va(tmp_path: Path, linie: Path, erklaerung: str):
    """Glied 2: mensch/aktuariat bekommt einen neuen Schluessel (der alte ist
    ENTZOGEN), mit der Erklaerung ``erklaerung`` fuer ihre frueheren Zeichnungen."""
    neu = _schluessel(tmp_path / "aussen" / "aktuariat-neu.key")
    o2 = _ordnung(tmp_path)
    o2["rollen"][VA]["schluessel_sha256"] = _fp(neu)
    ergebnis = _anhaengen(linie, o2, tmp_path / "o2.json", erklaerung={VA: erklaerung},
                          vorstand=[tmp_path / VORSTAND_SCHLUESSEL_DATEI])
    assert ergebnis.exit_code == 0, ergebnis.errors
    [_, zwei] = ol.lade_linie_strukturell_zur_anzeige(linie)[0]
    return neu, zwei


# --------------------------------------------------------------------------- #
# (a) "verfallen": der entzogene Schluessel unter der aelteren Kopie, mit
#     zurueckgestellter Uhr — der Leser mit der echten Linie verweigert
# --------------------------------------------------------------------------- #


def test_a_verfallen_verweigert_auch_mit_zurueckgestellter_uhr(tmp_path, monkeypatch):
    """Das Repro des Pruefers (H10) samt dem Fall, den die Zeitregel allein
    nicht faengt: ``entschieden_am`` liegt VOR der Abloesung. Rot vor dem Fix:
    der Leser des Betriebs nahm an (verifiziert, Rolle mensch/aktuariat, alter
    Schluessel)."""
    linie, fall, basis = _welt(tmp_path)
    kopie = tmp_path / "kopie" / "linie"
    shutil.copytree(linie, kopie)
    _, zwei = _schluesselwechsel_va(tmp_path, linie, "verfallen")
    _uhr_zurueck(monkeypatch, zwei["eingetragen_am"])
    ist = _entscheid(fall, "A-M4", _ersetze(basis, "--linie", kopie))
    # Benannte Grenze: Das Gate unter der Kopie sieht das Glied nicht.
    assert ist.exit_code == 0, ist.errors
    sha = ist.summary["snapshot_sha256"]
    snap = json.loads((fall / "entscheide" / f"A-M4-{sha}.json").read_text(encoding="utf-8"))
    assert (dt.datetime.fromisoformat(snap["entschieden_am"])
            < dt.datetime.fromisoformat(zwei["eingetragen_am"]))
    with pytest.raises(ueb.UebernahmeError) as fehler:
        _betrieb_liest_am4(tmp_path, fall, linie, sha)
    meldung = str(fehler.value)
    assert "Glied 2" in meldung and VA in meldung and "verfallen erklaert" in meldung, meldung
    assert "neu zeichnen" in meldung, meldung


# --------------------------------------------------------------------------- #
# (b) "gueltig" traegt eine rechtmaessig fruehere Zeichnung; "verfallen" nicht
# --------------------------------------------------------------------------- #


@pytest.mark.parametrize("erklaerung,traegt", [("gueltig", True), ("verfallen", False)])
def test_b_eine_zeichnung_vor_der_abloesung(tmp_path, erklaerung, traegt):
    """A-M4 unter Glied 1, danach der Schluesselwechsel. ``gueltig``: der Leser
    nimmt an (ein spaeterer Wechsel wirkt nicht zurueck). ``verfallen``: auch
    die rechtmaessig fruehere Abnahme traegt nichts mehr — die Folge, die die
    Ausgabe des Produzenten nennt (neu zeichnen)."""
    linie, fall, basis = _welt(tmp_path)
    am4 = _entscheid(fall, "A-M4", basis)
    assert am4.exit_code == 0, am4.errors
    _schluesselwechsel_va(tmp_path, linie, erklaerung)
    if traegt:
        daten, _, verifiziert = _betrieb_liest_am4(tmp_path, fall, linie,
                                                   am4.summary["snapshot_sha256"])
        assert verifiziert and daten["zeichnung"]["rolle"] == VA
    else:
        with pytest.raises(ueb.UebernahmeError, match="verfallen erklaert"):
            _betrieb_liest_am4(tmp_path, fall, linie, am4.summary["snapshot_sha256"])


# --------------------------------------------------------------------------- #
# (c) "gueltig", aber gezeichnet NACH der Abloesung (unter der Kopie): Zeitregel
# --------------------------------------------------------------------------- #


def test_c_gueltig_und_nach_der_abloesung_gezeichnet_verweigert(tmp_path):
    """Der Befund H10 mit der echten Uhr: Der alte Schluessel zeichnet A-M4
    unter der Kopie, NACHDEM Glied 2 eingetragen ist."""
    linie, fall, basis = _welt(tmp_path)
    kopie = tmp_path / "kopie" / "linie"
    shutil.copytree(linie, kopie)
    _, zwei = _schluesselwechsel_va(tmp_path, linie, "gueltig")
    ist = _entscheid(fall, "A-M4", _ersetze(basis, "--linie", kopie))
    assert ist.exit_code == 0, ist.errors
    with pytest.raises(ueb.UebernahmeError) as fehler:
        _betrieb_liest_am4(tmp_path, fall, linie, ist.summary["snapshot_sha256"])
    meldung = str(fehler.value)
    assert "unter einem abgeloesten Glied gezeichnet: Glied 1 wurde" in meldung, meldung
    assert f"am {zwei['eingetragen_am']} durch Glied 2 abgeloest" in meldung, meldung
    assert "gezeichnet wird nur unter der Spitze" in meldung, meldung


# --------------------------------------------------------------------------- #
# (d) ein Glied mit Minderung ohne Erklaerung: nicht anhaengbar, nicht lesbar
# --------------------------------------------------------------------------- #


def test_d_minderung_ohne_erklaerung_ist_nicht_anhaengbar(tmp_path):
    linie = linie_anlegen(tmp_path)
    o2 = _ordnung(tmp_path)
    o2["rollen"][VA]["gates"] = [g for g in o2["rollen"][VA]["gates"] if g != "A-T1"]
    vorstand = tmp_path / VORSTAND_SCHLUESSEL_DATEI
    ohne = _anhaengen(linie, o2, tmp_path / "o2.json", erklaerung={}, vorstand=[vorstand])
    assert ohne.exit_code != 0
    meldung = ohne.errors[0]["message"]
    assert f"mindert ['{VA}']" in meldung and "--fruehere-zeichnungen" in meldung, meldung
    fremd = _anhaengen(linie, o2, tmp_path / "o2.json",
                       erklaerung={VA: "gueltig", "mensch/rechenkern": "gueltig"},
                       vorstand=[vorstand])
    assert fremd.exit_code != 0 and "nicht mindert" in fremd.errors[0]["message"]
    falsch = _anhaengen(linie, o2, tmp_path / "o2.json", erklaerung={VA: "vielleicht"},
                        vorstand=[vorstand])
    assert falsch.exit_code != 0
    assert len(ol.lade_linie_strukturell_zur_anzeige(linie)[0]) == 1


def test_d_minderung_ohne_erklaerung_wird_beim_laden_verweigert(tmp_path):
    """Ein von Hand gebautes Glied, richtig vom Vorstand gezeichnet, ohne
    Erklaerung: Die Linie ist nicht verwendbar."""
    linie = linie_anlegen(tmp_path)
    [eins], _ = ol.lade_linie_strukturell_zur_anzeige(linie)
    o2 = _ordnung(tmp_path)
    o2["rollen"][VA]["gates"] = [g for g in o2["rollen"][VA]["gates"] if g != "A-T1"]
    vorstand = (tmp_path / VORSTAND_SCHLUESSEL_DATEI).read_bytes()
    glied = ol.baue_glied(json.dumps(o2, sort_keys=True).encode(), nummer=2,
                          vorgaenger=eins["glied_sha256"], eingetragen_am="2026-10-02T00:00:00+00:00",
                          vorstand=(vorstand, "simulation"), vorher=ol.ordnung_aus(eins))
    (linie / ol.VERZEICHNIS / ol.dateiname(glied)).write_text(json.dumps(glied), encoding="utf-8")
    glieder, fehler = ol.lade_linie(linie, ring={hashlib.sha256(vorstand).hexdigest(): vorstand})
    assert glieder == [] and any("erklaert aber nicht" in f for f in fehler), fehler


# --------------------------------------------------------------------------- #
# (e) H06: Gate-Entzug bei unveraendertem Schluessel
# --------------------------------------------------------------------------- #


@pytest.mark.parametrize("erklaerung", ["gueltig", "verfallen"])
def test_e_gate_entzug_a_t1_unter_der_kopie_traegt_keine_am4(tmp_path, erklaerung):
    """Glied 2 entzieht mensch/aktuariat A-T1 (Schluessel unveraendert). A-T1
    im Fall unter der Kopie (Spitze Glied 1), danach A-M4 unter der ECHTEN
    Linie: verweigert — bei ``gueltig`` ueber die Zeitregel (A-T1 entstand
    nach der Abloesung), bei ``verfallen`` ohnehin. Rot vor dem Fix: A-M4
    Exit 0, tarifwerkstand "abgenommen im Fall"."""
    linie, fall, basis = _welt(tmp_path)
    kopie = tmp_path / "kopie" / "linie"
    shutil.copytree(linie, kopie)
    o2 = _ordnung(tmp_path)
    o2["rollen"][VA]["gates"] = [g for g in o2["rollen"][VA]["gates"] if g != "A-T1"]
    assert _anhaengen(linie, o2, tmp_path / "o2.json", erklaerung={VA: erklaerung},
                      vorstand=[tmp_path / VORSTAND_SCHLUESSEL_DATEI]).exit_code == 0
    assert tarifwerk_belegen.main(["--fall", str(fall), "--repo-root", str(REPO), "--von", "HEAD",
                                   "--begruendung", "Tarifwerk im Fall"]).exit_code == 0
    at1 = _entscheid(fall, "A-T1", _ersetze(basis, "--linie", kopie))
    assert at1.exit_code == 0, at1.errors
    am4 = _entscheid(fall, "A-M4", _ersetze(basis, "--zeichnungsordnung", tmp_path / "o2.json"))
    assert am4.exit_code != 0, am4.summary
    meldung = am4.errors[0]["message"]
    assert "A-T1" in meldung and "Glied 2" in meldung, meldung
    assert ("verfallen erklaert" if erklaerung == "verfallen"
            else "unter einem abgeloesten Glied gezeichnet") in meldung, meldung


def test_e_positivkontrolle_a_t1_vor_dem_entzug_traegt_bei_gueltig(tmp_path):
    linie, fall, basis = _welt(tmp_path)
    assert tarifwerk_belegen.main(["--fall", str(fall), "--repo-root", str(REPO), "--von", "HEAD",
                                   "--begruendung", "Tarifwerk im Fall"]).exit_code == 0
    assert _entscheid(fall, "A-T1", basis).exit_code == 0
    o2 = _ordnung(tmp_path)
    o2["rollen"][VA]["gates"] = [g for g in o2["rollen"][VA]["gates"] if g != "A-T1"]
    assert _anhaengen(linie, o2, tmp_path / "o2.json", erklaerung={VA: "gueltig"},
                      vorstand=[tmp_path / VORSTAND_SCHLUESSEL_DATEI]).exit_code == 0
    am4 = _entscheid(fall, "A-M4", _ersetze(basis, "--zeichnungsordnung", tmp_path / "o2.json"))
    assert am4.exit_code == 0, am4.errors
    assert am4.summary["standabnahmen"]["tarifwerkstand"]["weg"] == "abnahme_im_fall"


# --------------------------------------------------------------------------- #
# Der Vorstand: die Erklaerung wirkt auf Abnahmen, nicht auf die Glieder
# --------------------------------------------------------------------------- #


def _vorstandswechsel(tmp_path: Path, linie: Path, erklaerung: str) -> Path:
    neu = _schluessel(tmp_path / "aussen" / "vorstand-neu.key")
    o2 = _ordnung(tmp_path)
    o2["rollen"][ol.WURZELROLLE]["schluessel_sha256"] = _fp(neu)
    ergebnis = _anhaengen(linie, o2, tmp_path / "o2.json",
                          erklaerung={ol.WURZELROLLE: erklaerung},
                          vorstand=[tmp_path / VORSTAND_SCHLUESSEL_DATEI])
    assert ergebnis.exit_code == 0, ergebnis.errors
    return neu


def test_vorstand_a_schluesselwechsel_verfallen_die_linie_bleibt_gueltig(tmp_path):
    """Der wichtigste Fall (Wurzelschluessel nicht mehr vertrauenswuerdig) muss
    ausdrueckbar sein: Glied 2 wird mit dem ALTEN Schluessel gezeichnet und
    erklaert dessen fruehere Zeichnungen fuer verfallen. Die Linie laedt, die
    Spitze gilt, unter ihr wird gezeichnet, und der NEUE Schluessel zeichnet
    das naechste Glied.

    Mutationsprobe: die Erklaerung auf die Glieder selbst anwenden -> Glied 2
    (vom alten Schluessel gezeichnet) faellt -> rot."""
    linie = linie_anlegen(tmp_path)
    neu = _vorstandswechsel(tmp_path, linie, "verfallen")
    ring = _ring(tmp_path)
    glieder, fehler = ol.lade_linie(linie, ring=ring)
    assert fehler == [] and len(glieder) == 2, fehler
    (tmp_path / "zeichnungsordnung.json").write_text(
        glieder[-1]["ordnung_text"], encoding="utf-8")
    ergebnis = _zeichne_in_linie(linie, "A-T1")
    assert ergebnis.exit_code == 0, ergebnis.errors
    assert ergebnis.summary["ordnungslinie"].startswith("Glied 2 ")
    o3 = json.loads(glieder[-1]["ordnung_text"])
    o3["rollen"]["mensch/revision"] = {"schluessel_sha256": "ab" * 32,
                                      "schluesselklasse": "simulation", "gates": []}
    drei = _anhaengen(linie, o3, tmp_path / "o3.json", erklaerung={},
                      vorstand=[tmp_path / VORSTAND_SCHLUESSEL_DATEI, neu])
    assert drei.exit_code == 0, drei.errors
    assert ol.lade_linie(linie, ring=_ring(tmp_path))[1] == []


@pytest.mark.parametrize("erklaerung,traegt", [("verfallen", False), ("gueltig", True)])
def test_vorstand_b_c_der_fallauftrag_des_alten_schluessels(tmp_path, erklaerung, traegt):
    """(b) Eine A-M6, die der alte Vorstandsschluessel VOR dem Wechsel
    gezeichnet hat, traegt nach ``verfallen`` keine Annahme mehr — die
    Kaskade: jede Annahme jedes Falls gruendet auf A-M6. (c) Mit ``gueltig``
    traegt sie weiter."""
    linie, fall, basis = _welt(tmp_path)
    _vorstandswechsel(tmp_path, linie, erklaerung)
    am4 = _entscheid(fall, "A-M4", _ersetze(basis, "--zeichnungsordnung", tmp_path / "o2.json"))
    if traegt:
        assert am4.exit_code == 0, am4.errors
    else:
        assert am4.exit_code != 0
        meldung = am4.errors[0]["message"]
        assert am4.errors[0]["code"] == "fallauftrag", am4.errors
        assert ol.WURZELROLLE in meldung and "verfallen erklaert" in meldung, meldung


# --------------------------------------------------------------------------- #
# Der Produzent: die Folge vor der Wahl, die monotone Uhr
# --------------------------------------------------------------------------- #


def test_der_produzent_nennt_die_folge_von_verfallen(tmp_path):
    """Ausgabe und Sicht nennen je Rolle die neu zu zeichnenden Gates — aus der
    Ordnung des Vorgaengers —, fuer den Vorstand die Kaskade."""
    linie = linie_anlegen(tmp_path)
    neu = _schluessel(tmp_path / "aussen" / "vorstand-neu.key")
    o2 = _ordnung(tmp_path)
    o2["rollen"][ol.WURZELROLLE]["schluessel_sha256"] = _fp(neu)
    o2["rollen"][VA]["gates"] = [g for g in o2["rollen"][VA]["gates"] if g != "A-T1"]
    ergebnis = _anhaengen(linie, o2, tmp_path / "o2.json",
                          erklaerung={ol.WURZELROLLE: "verfallen", VA: "gueltig"},
                          vorstand=[tmp_path / VORSTAND_SCHLUESSEL_DATEI])
    assert ergebnis.exit_code == 0, ergebnis.errors
    folge = ergebnis.summary["fruehere_zeichnungen"]
    assert set(folge) == {ol.WURZELROLLE, VA}
    assert folge[ol.WURZELROLLE].startswith("verfallen: jede fruehere Abnahme ['A-M6']")
    assert "jeder Fallauftrag (A-M6) und alles, was darauf gruendet" in folge[ol.WURZELROLLE]
    assert "die Glieder der Linie bleiben gueltig" in folge[ol.WURZELROLLE]
    assert folge[VA].startswith("gueltig: Abnahmen ['A-T1']"), folge[VA]
    sicht = (linie / "abgeleitet" / "ordnung" / "linie.md").read_text(encoding="utf-8")
    assert f"- {ol.WURZELROLLE}: {folge[ol.WURZELROLLE]}" in sicht
    assert f"- {VA}: {folge[VA]}" in sicht


def test_ein_glied_wird_nicht_frueher_datiert_als_sein_vorgaenger(tmp_path):
    linie = linie_anlegen(tmp_path)   # Glied 1: 2026-10-01T08:00:00+00:00
    o2 = _ordnung(tmp_path)
    o2["rollen"]["mensch/revision"] = {"schluessel_sha256": "ab" * 32,
                                      "schluesselklasse": "simulation", "gates": []}
    vorstand = [tmp_path / VORSTAND_SCHLUESSEL_DATEI]
    frueher = _anhaengen(linie, o2, tmp_path / "o2.json", erklaerung={}, vorstand=vorstand,
                         eingetragen="2026-10-01T07:59:59+00:00")
    assert frueher.exit_code != 0 and "nicht frueher datiert" in frueher.errors[0]["message"]
    ohne_zone = _anhaengen(linie, o2, tmp_path / "o2.json", erklaerung={}, vorstand=vorstand,
                           eingetragen="2026-10-02T00:00:00")
    assert ohne_zone.exit_code != 0 and "Zeitzone" in ohne_zone.errors[0]["message"]
    gleich = _anhaengen(linie, o2, tmp_path / "o2.json", erklaerung={}, vorstand=vorstand,
                        eingetragen="2026-10-01T10:00:00+02:00")   # == 08:00 UTC
    assert gleich.exit_code == 0, gleich.errors


def test_die_wiederholung_eines_glieds_verlangt_dieselbe_erklaerung(tmp_path):
    linie = linie_anlegen(tmp_path)
    o2 = _ordnung(tmp_path)
    o2["rollen"][VA]["gates"] = [g for g in o2["rollen"][VA]["gates"] if g != "A-T1"]
    vorstand = [tmp_path / VORSTAND_SCHLUESSEL_DATEI]
    [eins], _ = ol.lade_linie_strukturell_zur_anzeige(linie)

    def nochmal(erklaerung):
        return stand_belegen.main([
            "ordnung", "--linie", str(linie), "--ordnung", str(tmp_path / "o2.json"),
            "--vorgaenger", eins["glied_sha256"], "--vorstand-schluessel", str(vorstand[0]),
            "--fruehere-zeichnungen", f"{VA}={erklaerung}"])

    assert _anhaengen(linie, o2, tmp_path / "o2.json", erklaerung={VA: "gueltig"},
                      vorstand=vorstand).exit_code == 0
    assert nochmal("gueltig").summary["bereits_vorhanden"] is True
    anders = nochmal("verfallen")
    assert anders.exit_code != 0 and "nie umgeschrieben" in anders.errors[0]["message"]


# --------------------------------------------------------------------------- #
# Ratschen
# --------------------------------------------------------------------------- #


def _arten_aus_aenderungen(quelle: str) -> set:
    """Die Literale, die ``aenderungen`` als ``"art"`` erzeugen kann (AST)."""
    baum = ast.parse(quelle)
    arten = set()
    for knoten in ast.walk(baum):
        if isinstance(knoten, ast.FunctionDef) and knoten.name == "aenderungen":
            for d in ast.walk(knoten):
                if isinstance(d, ast.Dict):
                    for k, v in zip(d.keys, d.values):
                        if isinstance(k, ast.Constant) and k.value == "art" \
                                and isinstance(v, ast.Constant):
                            arten.add(v.value)
    return arten


def test_ratsche_jede_aenderungsart_ist_minderung_oder_erweiterung():
    """Ratsche mit ==: Eine neue Aenderungsart erzwingt die Entscheidung, ob
    sie ein Recht mindert (dann braucht sie eine Erklaerung) — statisch (AST
    ueber ``aenderungen``) UND an der Naht (jede Art wird erzeugt)."""
    assert set(ol.MINDERUNGSARTEN) | set(ol.ERWEITERUNGSARTEN) == set(ol.AENDERUNGSARTEN)
    assert not set(ol.MINDERUNGSARTEN) & set(ol.ERWEITERUNGSARTEN)
    assert _arten_aus_aenderungen(Path(ol.__file__).read_text(encoding="utf-8")) \
        == set(ol.AENDERUNGSARTEN)
    alt = {"rollen": {"a": {"schluessel_sha256": "1", "schluesselklasse": "mensch", "gates": ["X"]},
                      "b": {"schluessel_sha256": "2", "schluesselklasse": "mensch", "gates": ["X"]},
                      "c": {"schluessel_sha256": "3", "schluesselklasse": "mensch", "gates": []}}}
    neu = {"rollen": {"a": {"schluessel_sha256": "9", "schluesselklasse": "simulation",
                            "gates": ["Y"]},
                      "c": {"schluessel_sha256": "3", "schluesselklasse": "mensch", "gates": []},
                      "d": {"schluessel_sha256": "4", "schluesselklasse": "mensch", "gates": []}}}
    erzeugt = {e["art"] for e in ol.aenderungen(alt, neu)}
    assert erzeugt == set(ol.AENDERUNGSARTEN)
    assert ol.geminderte_rollen(ol.aenderungen(alt, neu)) == ["a", "b"]


def test_ratsche_positivkontrolle_des_artendetektors():
    quelle = ("def aenderungen(a, n):\n    x = {'art': 'eins', 'rolle': 1}\n"
              "    return [x, {'art': 'zwei'}, {'andere': 'drei'}]\n"
              "def sonst():\n    return {'art': 'vier'}\n")
    assert _arten_aus_aenderungen(quelle) == {"eins", "zwei"}


def _aufrufe_damalige_ordnung(quelle: str) -> list:
    aus = []

    class B(ast.NodeVisitor):
        funktion = "<modul>"

        def visit_FunctionDef(self, k):
            vorher, self.funktion = self.funktion, k.name
            self.generic_visit(k)
            self.funktion = vorher

        def visit_Call(self, k):
            f = k.func
            if (f.id if isinstance(f, ast.Name) else getattr(f, "attr", "")) == "damalige_ordnung":
                aus.append((self.funktion,
                            tuple(a.id if isinstance(a, ast.Name) else "?" for a in k.args),
                            tuple(sorted((kw.arg, kw.value.id if isinstance(kw.value, ast.Name)
                                          else "?") for kw in k.keywords))))
            self.generic_visit(k)

    B().visit(ast.parse(quelle))
    return aus


def test_ratsche_die_eine_stelle_der_leser_haelt_was_sie_uebergibt():
    """Statische Ratsche (AST, benannt): ``damalige_ordnung`` — die Stelle, an
    der die Abloesung gerechnet wird — hat im Paket genau EINEN Aufrufer,
    ``zeichnende_rolle_fehler``, und der uebergibt den Snapshot, die Linie DES
    LESERS und das Gate, das er liest (nicht eines aus dem Snapshot). Die Menge
    der Leser hinter ``zeichnende_rolle_fehler`` haelt
    tests/test_linie_pflicht.py. ``gate`` hat keinen Standardwert."""
    gefunden = []
    for pfad in sorted(SRC.rglob("*.py")):
        for aufruf in _aufrufe_damalige_ordnung(pfad.read_text(encoding="utf-8")):
            gefunden.append((pfad.relative_to(SRC).as_posix(), *aufruf))
    assert gefunden == [("models/zeichnung.py", "zeichnende_rolle_fehler",
                         ("daten", "linie"), (("gate", "gate"),))]
    sig = inspect.signature(ol.damalige_ordnung)
    assert sig.parameters["gate"].kind is inspect.Parameter.KEYWORD_ONLY
    assert sig.parameters["gate"].default is inspect.Parameter.empty
    sig = inspect.signature(ol.neues_glied)
    p = sig.parameters["fruehere_zeichnungen"]
    assert p.kind is inspect.Parameter.KEYWORD_ONLY and p.default is inspect.Parameter.empty


def test_ratsche_positivkontrolle_des_aufrufdetektors():
    quelle = ("def f(daten, linie, gate):\n    damalige_ordnung(daten, linie, gate=gate)\n"
              "def g(s):\n    x.damalige_ordnung(s, [], gate='A')\n")
    assert _aufrufe_damalige_ordnung(quelle) == [
        ("f", ("daten", "linie"), (("gate", "gate"),)),
        ("g", ("s", "?"), (("gate", "?"),))]

