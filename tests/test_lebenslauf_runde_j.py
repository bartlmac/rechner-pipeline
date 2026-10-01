"""Lebenslauf eines Falls, Fix-Runde nach der blinden Pruefrunde J (ADR-026,
Nachtrag Pruefrunde J).

Befund (J02, J03, eine Klasse): Seit Pruefrunde I ist eine gezeichnete
Ablehnung eine ZEICHNUNG im Fall. Die Pruefungen der Zeichnung im Fall hingen
aber an "Entscheid ist angenommen": Ein gezeichneter A-M4-Widerruf unter einem
Mandat, das der Fallauftrag der Rolle nicht nennt (J02), und ein Widerruf mit
dem Schluessel der Programmleitung als mensch/aktuariat (J03) wurden mit
Exit 0 gezeichnet und gaben danach den Abbruch A-M5 frei.

Invariante: Jede Zeichnung in einem Fall, Annahme ODER gezeichnete Ablehnung,
geht durch dieselben Pruefungen des Falls (``fallauftrag_pruefen``: geltender
Auftrag, Lieferung, Linie, Trennung der Programmleitung; das Mandat der Rolle
wie im Auftrag genannt) und nennt signiert den Auftrag, auf dem sie steht.
Der Leser, dem eine gezeichnete Ablehnung etwas FREIGIBT
(``gezeichneter_widerruf_fehler``, nur der Abbruch nach A-M4), rechnet nach,
was er nachrechnen kann: geltender Auftrag, Mandat des Auftrags, Schluessel
ist nicht der der Programmleitung.

Menge: jede Bedingung ``args.entscheid == "angenommen"`` in
``gate_entscheid.main`` (AST; 14 auf 90ee7e9, 12 nach dem Fix: eine gilt jetzt
der Zeichnung, zwei gleiche Meldungsweichen sind eine) plus die gleichwertigen
``auftrag_spitze is not None`` (2); je Stelle entschieden in der Tabelle des
ADR-Nachtrags. Ratsche mit ``==`` und Positivkontrolle des Detektors.

Gemessen vor der Verschaerfung (instrumentierter Suitenlauf auf 90ee7e9):
32 Ablehnungen erreichten das Schreiben, 14 davon gezeichnet, 8 gezeichnet im
Fall ausser an A-M6; alle 8 bestanden die neuen Pruefungen — kein Testweg
umgestellt.

Rot auf 90ee7e9: 10 der 14 Tests (die beiden J02-, die beiden J03-Tests, der
Leser-Auftrag, der berechtigte Widerruf, die Ablehnung ohne Auftrag, das
Schema, beide Ratschen); gruen blieben die Positivkontrollen.

Mutationsproben (je aus der eigenen .bak-Kopie zurueckgenommen):
* in ``main`` die Bedingung von ``fallauftrag_pruefen`` zurueck auf
  ``args.entscheid == "angenommen"`` -> 7 rot;
* im Leser die Mandatspruefung entfernt -> 1 rot (Leser-Mandat);
* im Leser die Trennungspruefung entfernt -> 1 rot (Leser-Trennung);
* im Leser die Pruefung des genannten Auftrags entfernt -> 1 rot (Leser-Auftrag);
* im Schema ``fallauftrag`` fuer die gezeichnete Ablehnung nicht verlangt ->
  5 rot.

Knoten: system/entscheid
"""

from __future__ import annotations

import ast
import hashlib
import json
from pathlib import Path

import pytest

from rechner_pipeline import fall as fall_mod
from rechner_pipeline.gates import fall_belegen, gate_entscheid, stand_belegen
from rechner_pipeline.models import ordnungslinie as ol
from rechner_pipeline.models.freigabe import freigabe_fuer
from rechner_pipeline.models.schemas import (
    P9_GATE_VERSION,
    P9_SNAPSHOT_SCHEMA_VERSION,
    P9Snapshot,
    p9_snapshot_sha256,
)

REPO_ROOT = Path(__file__).resolve().parents[1]
GATE_QUELLE = REPO_ROOT / "src" / "rechner_pipeline" / "gates" / "gate_entscheid.py"
FALL = "fallj"
VA = "mensch/aktuariat"
SCHLUESSEL = {
    "vorstand": b"J-test vorstand schluessel ......" * 2,
    "aktuariat": b"J-test aktuariat schluessel ....." * 2,
    "rechenkern": b"J-test rechenkern schluessel ...." * 2,
    "betrieb": b"J-test betrieb schluessel ......." * 2,
    "pl": b"J-test programmleitung schluessel" * 2,
    "aktuariat2": b"J-test aktuariat neuer schluessel" * 2,
}


# --------------------------------------------------------------------------- #
# Testwelt ueber die echten Kommandos (Linie, Fall, Auftrag)
# --------------------------------------------------------------------------- #


def _fp(name: str) -> str:
    return hashlib.sha256(SCHLUESSEL[name]).hexdigest()


def _key(welt: Path, name: str) -> Path:
    p = welt / "keys" / f"{name}.key"
    if not p.exists():
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_bytes(SCHLUESSEL[name])
        p.chmod(0o600)
    return p


def _ordnung(welt: Path, name: str, *, aktuariat_key: str = "aktuariat") -> Path:
    rollen = {
        "mensch/vorstand": {"schluessel_sha256": _fp("vorstand"), "schluesselklasse": "mensch",
                            "gates": ["A-Z1", "A-M6"]},
        VA: {"schluessel_sha256": _fp(aktuariat_key), "schluesselklasse": "simulation",
             "gates": ["A-Q1", "A-M1", "A-M2", "A-M3", "A-M4", "A-T1"]},
        "mensch/rechenkern": {"schluessel_sha256": _fp("rechenkern"), "schluesselklasse": "mensch",
                              "gates": ["A-K2"]},
        "mensch/betrieb": {"schluessel_sha256": _fp("betrieb"), "schluesselklasse": "mensch",
                           "gates": ["A-B2", "A-B3"]},
    }
    p = welt / "ordnungen" / f"{name}.json"
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(json.dumps({"schema_version": 2, "rollen": rollen}, sort_keys=True),
                 encoding="utf-8")
    return p


def _ok(ergebnis, was: str):
    assert ergebnis.exit_code == 0, (was, ergebnis.errors)
    return ergebnis


def _glieder(welt: Path):
    g, f = ol.lade_linie_strukturell_zur_anzeige(welt / "linie")
    assert not f, f
    return g


def _glied_anhaengen(welt: Path, ordnung_pfad: Path, erklaerungen: dict):
    argv = ["ordnung", "--linie", str(welt / "linie"), "--ordnung", str(ordnung_pfad),
            "--vorgaenger", _glieder(welt)[-1]["glied_sha256"],
            "--vorstand-schluessel", str(_key(welt, "vorstand"))]
    for rolle, erklaerung in erklaerungen.items():
        argv += ["--fruehere-zeichnungen", f"{rolle}={erklaerung}"]
    return _ok(stand_belegen.main(argv), "Glied")


def _entscheid(welt: Path, gate: str, entscheid: str, *, keys=(), ordnung=None,
               rolle=None, mandat=None):
    argv = ["--fall", str(welt / FALL), "--linie", str(welt / "linie"), "--gate", gate,
            "--entscheid", entscheid, "--entscheider", "Pruefer J",
            "--begruendung", "Runde J", "--repo-root", str(REPO_ROOT)]
    if ordnung is not None:
        argv += ["--zeichnungsordnung", str(ordnung)]
    for k in keys:
        argv += ["--freigabe-schluessel", str(_key(welt, k))]
    if rolle:
        argv += ["--rolle", rolle]
    if mandat:
        argv += ["--mandat", str(mandat)]
    return gate_entscheid.main(argv)


def _snapshots(welt: Path, gate: str):
    return [json.loads(p.read_text(encoding="utf-8"))
            for p in sorted((welt / FALL / "entscheide").glob(f"{gate}-*.json"))]


def _geltender_auftrag(welt: Path) -> dict:
    spitze, f = stand_belegen.geltende_spitze(welt / FALL, "A-M6")
    assert spitze is not None and spitze["entscheid"] == "angenommen", f
    return spitze


def _handsnapshot(welt: Path, gate: str, *, entscheid: str = "angenommen", key: str,
                  rolle: str = VA, mandat_sha: str | None = None,
                  fallauftrag: str | None = "geltend", glied_index: int = -1) -> dict:
    """Ein Snapshot, wie das Gate ihn schreibt (Schema 10), gezeichnet mit ``key``."""
    fall = welt / FALL
    glied = _glieder(welt)[glied_index]
    kette = sorted(d["snapshot_sha256"] for d in _snapshots(welt, gate))
    daten = {
        "schema_version": P9_SNAPSHOT_SCHEMA_VERSION, "command": "gate_entscheid",
        "gate_version": P9_GATE_VERSION, "gate": gate, "entscheid": entscheid,
        "entscheider": "Hand", "rolle": rolle, "begruendung": "von Hand", "fall": FALL,
        "artefakt_hashes": {
            "eingang.json": hashlib.sha256((fall / "eingang.json").read_bytes()).hexdigest(),
            "abgeleitet/abox/abox.json": "cd" * 32},
        "system": {"branch": "t27", "commit": "abc1234", "dirty": "nein",
                   "quellcode_sha256": "ef" * 32},
        "vorgaenger": kette, "entschieden_am": "2026-10-01T09:30:00+00:00",
    }
    if gate == "A-M4":
        daten.update({"fall_scope": "tarif", "standabnahmen": {},
                      "pflichtbelege": {"x": ["aa" * 32]} if entscheid == "angenommen" else {},
                      "pk1_belege": {"klv/tg2012": ["bb" * 32]} if entscheid == "angenommen"
                      else {}})
    zeichnung = {"rolle": rolle, "ordnung_sha256": glied["ordnung_sha256"],
                 "schluesselklasse": "simulation", "ordnungsglied_sha256": glied["glied_sha256"],
                 "mandat_sha256": mandat_sha or _mandat_sha(welt)}
    daten["zeichnung"] = zeichnung
    if fallauftrag is not None:
        daten["fallauftrag"] = (_geltender_auftrag(welt)["snapshot_sha256"]
                                if fallauftrag == "geltend" else fallauftrag)
    daten["freigabe"] = freigabe_fuer(daten, SCHLUESSEL[key])
    daten["snapshot_sha256"] = p9_snapshot_sha256(daten)
    (fall / "entscheide").mkdir(exist_ok=True)
    (fall / "entscheide" / f"{gate}-{daten['snapshot_sha256']}.json").write_text(
        json.dumps(daten, ensure_ascii=False, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    return daten


def _mandat(welt: Path) -> Path:
    return welt / "mandate" / "mandat-aktuariat.md"


def _mandat_sha(welt: Path) -> str:
    return hashlib.sha256(_mandat(welt).read_bytes()).hexdigest()


def _welt(welt: Path) -> Path:
    """Linie (ein Glied), Fall (Scope tarif), Fallauftrag; das Aktuariat ist
    simuliert und hat im Auftrag sein Mandat; die Programmleitung ist ein
    Mensch mit eigenem Schluessel ausserhalb der Ordnung."""
    welt.mkdir(parents=True, exist_ok=True)
    for name in SCHLUESSEL:
        _key(welt, name)
    _mandat(welt).parent.mkdir(parents=True, exist_ok=True)
    _mandat(welt).write_text("Mandat: das simulierte Aktuariat zeichnet die Gates dieses "
                             "Falls.\n", encoding="utf-8")
    o1 = _ordnung(welt, "o1")
    _ok(stand_belegen.main(["linie", "--linie", str(welt / "linie")]), "linie")
    _ok(stand_belegen.main(["ordnung", "--linie", str(welt / "linie"), "--ordnung", str(o1),
                            "--vorgaenger", "keiner",
                            "--eingetragen-am", "2026-10-01T08:00:00+00:00"]), "ordnung")
    fall = welt / FALL
    fall_mod.anlegen(fall, scope="tarif")
    quelle = welt / "quelle-tarifmeldung.txt"
    quelle.write_text("Tarifmeldung (synthetisch)\n", encoding="utf-8")
    fall_mod.registrieren(fall, quelle)
    _ok(fall_belegen.main([
        "auftrag", "--fall", str(fall), "--linie", str(welt / "linie"),
        "--zeichnungsordnung", str(o1), "--programmleitung-schluessel", str(_key(welt, "pl")),
        "--programmleitung-klasse", "mensch", "--auftrag", "Fall J migrieren",
        "--mandat", f"{VA}={_mandat(welt)}"]), "Auftrag (Vorlage)")
    _ok(_entscheid(welt, "A-M6", "angenommen", keys=("vorstand",), ordnung=o1), "A-M6")
    return o1


def _abbruch(welt: Path, ordnung: Path, keys=("vorstand", "aktuariat", "pl")):
    _ok(fall_belegen.main(["abbruch", "--fall", str(welt / FALL), "--repo-root", str(REPO_ROOT),
                           "--grund", "Runde J", "--bestand", "bleibt",
                           "--uebergabe", "keine"]), "Abbruch (Vorlage)")
    return _entscheid(welt, "A-M5", "angenommen", keys=keys, ordnung=ordnung)


@pytest.fixture()
def abgenommen(tmp_path):
    """Fall mit Auftrag und geltender A-M4-Annahme des simulierten Aktuariats."""
    welt = tmp_path / "welt"
    o1 = _welt(welt)
    _handsnapshot(welt, "A-M4", key="aktuariat")
    return welt, o1


def _fremdes_mandat(welt: Path) -> Path:
    fremd = welt / "mandate" / "fremdes-mandat.md"
    fremd.write_text("Mandat eines anderen Falls.\n", encoding="utf-8")
    return fremd


def _widerruf(welt: Path, ordnung: Path, *, keys=("vorstand", "aktuariat"), mandat=None):
    return _entscheid(welt, "A-M4", "abgelehnt", keys=keys, ordnung=ordnung, rolle=VA,
                      mandat=mandat or _mandat(welt))


def _ablehnungen(welt: Path, gate: str = "A-M4"):
    return [d for d in _snapshots(welt, gate) if d["entscheid"] == "abgelehnt"]


# --------------------------------------------------------------------------- #
# J02: das Mandat der gezeichneten Ablehnung ist das des Auftrags
# --------------------------------------------------------------------------- #


def test_j02_gezeichneter_widerruf_unter_fremdem_mandat_wird_verweigert(abgenommen):
    """Rot auf 90ee7e9: Exit 0, danach ging der Abbruch."""
    welt, o1 = abgenommen
    ergebnis = _widerruf(welt, o1, mandat=_fremdes_mandat(welt))
    assert ergebnis.exit_code == 20, ergebnis.errors
    fehler = ergebnis.errors[0]
    assert fehler["code"] == "mandat", fehler
    assert fehler["message"].startswith("Gezeichnete Ablehnung verweigert:"), fehler
    assert "unsigniert" in fehler["message"] and "Mandat" in fehler["message"]
    assert _ablehnungen(welt) == []
    assert _abbruch(welt, o1).exit_code == 20


def test_j02_leser_rechnet_das_mandat_des_widerrufs_nach(abgenommen):
    """Ein gezeichneter Widerruf unter fremdem Mandat, am Gate vorbei hingelegt
    (Signatur echt, Rolle berechtigt, Auftrag genannt): Der Abbruch glaubt dem
    Gate nicht, er rechnet das Mandat gegen den geltenden Auftrag nach."""
    welt, o1 = abgenommen
    fremd = hashlib.sha256(_fremdes_mandat(welt).read_bytes()).hexdigest()
    _handsnapshot(welt, "A-M4", entscheid="abgelehnt", key="aktuariat", mandat_sha=fremd)
    ergebnis = _abbruch(welt, o1)
    assert ergebnis.exit_code == 20, ergebnis.errors
    meldung = ergebnis.errors[0]["message"]
    assert ergebnis.errors[0]["code"] == "vorbedingung" and "Mandat" in meldung, meldung
    assert _snapshots(welt, "A-M5") == []


def test_j02_leser_verlangt_den_geltenden_auftrag_im_widerruf(abgenommen):
    """Ein Widerruf, der einen anderen Auftrag nennt, gibt nichts frei."""
    welt, o1 = abgenommen
    _handsnapshot(welt, "A-M4", entscheid="abgelehnt", key="aktuariat", fallauftrag="ab" * 32)
    ergebnis = _abbruch(welt, o1)
    assert ergebnis.exit_code == 20, ergebnis.errors
    assert "Fallauftrag" in ergebnis.errors[0]["message"], ergebnis.errors


# --------------------------------------------------------------------------- #
# J03: die Trennung der Programmleitung gilt fuer jede Zeichnung
# --------------------------------------------------------------------------- #


def test_j03_widerruf_mit_dem_schluessel_der_programmleitung_wird_verweigert(abgenommen):
    """Rot auf 90ee7e9: Glied 2 gibt dem Aktuariat den Schluessel der
    Programmleitung; der Widerruf als mensch/aktuariat ging mit Exit 0."""
    welt, _ = abgenommen
    o2 = _ordnung(welt, "o2", aktuariat_key="pl")
    _glied_anhaengen(welt, o2, {VA: "gueltig"})
    ergebnis = _widerruf(welt, o2, keys=("vorstand", "aktuariat", "pl"))
    assert ergebnis.exit_code == 20, ergebnis.errors
    fehler = ergebnis.errors[0]
    assert fehler["code"] == "fallauftrag", fehler
    assert fehler["message"].startswith("Gezeichnete Ablehnung verweigert:"), fehler
    assert "Programmleitung" in fehler["message"] and "unsigniert" in fehler["message"]
    assert _ablehnungen(welt) == []


def test_j03_leser_rechnet_die_trennung_des_widerrufs_nach(abgenommen):
    """Ein Widerruf mit dem Schluessel der Programmleitung, unter Glied 2 als
    Aktuariat gezeichnet (am Gate vorbei); Glied 3 gibt dem Aktuariat einen
    eigenen Schluessel und erklaert fruehere Zeichnungen fuer gueltig. Unter
    Glied 3 haelt die Annahme des Abbruchs die Trennung — nur der Leser des
    Widerrufs sieht, dass derselbe Schluessel widerrief und abbraeche."""
    welt, _ = abgenommen
    o2 = _ordnung(welt, "o2", aktuariat_key="pl")
    _glied_anhaengen(welt, o2, {VA: "gueltig"})
    _handsnapshot(welt, "A-M4", entscheid="abgelehnt", key="pl")
    o3 = _ordnung(welt, "o3", aktuariat_key="aktuariat2")
    _glied_anhaengen(welt, o3, {VA: "gueltig"})
    ergebnis = _abbruch(welt, o3, keys=("vorstand", "aktuariat", "aktuariat2", "pl"))
    assert ergebnis.exit_code == 20, ergebnis.errors
    meldung = ergebnis.errors[0]["message"]
    assert ergebnis.errors[0]["code"] == "vorbedingung" and "Programmleitung" in meldung, meldung
    assert _snapshots(welt, "A-M5") == []


# --------------------------------------------------------------------------- #
# Positivkontrollen: was offen bleiben muss
# --------------------------------------------------------------------------- #


def test_berechtigter_widerruf_unter_dem_mandat_des_auftrags_gibt_den_abbruch_frei(abgenommen):
    welt, o1 = abgenommen
    _ok(_widerruf(welt, o1), "Widerruf")
    (widerruf,) = _ablehnungen(welt)
    assert widerruf["fallauftrag"] == _geltender_auftrag(welt)["snapshot_sha256"]
    assert widerruf["zeichnung"]["mandat_sha256"] == _mandat_sha(welt)
    _ok(_abbruch(welt, o1), "Abbruch")
    assert len(_snapshots(welt, "A-M5")) == 1


def test_unsignierte_ablehnung_bleibt_moeglich_und_gibt_nichts_frei(abgenommen):
    """ADR-008, Punkt 6: ohne Schluessel ablehnen, auch unter fremdem Mandat;
    die Ablehnung traegt weder Zeichnung noch Auftrag und sperrt nur. Der Ring
    dient nur dem Lesen der Kette; ohne Ordnung wird nicht gezeichnet."""
    welt, o1 = abgenommen
    _ok(_entscheid(welt, "A-M4", "abgelehnt", keys=("vorstand", "aktuariat"),
                   rolle="agent/aktuariat", mandat=_fremdes_mandat(welt)),
        "unsignierte Ablehnung")
    (ablehnung,) = _ablehnungen(welt)
    assert not {"freigabe", "zeichnung", "fallauftrag"} & set(ablehnung)
    ergebnis = _abbruch(welt, o1)
    assert ergebnis.exit_code == 20 and "unsignierte Ablehnung" in ergebnis.errors[0]["message"]


def test_unsignierte_ablehnung_ohne_geltenden_auftrag_bleibt_moeglich(tmp_path):
    """Ohne Auftrag gibt es keine gezeichnete Ablehnung im Fall — unsigniert
    ablehnen geht weiter (der Ausweg, den die Meldung nennt)."""
    welt = tmp_path / "welt"
    o1 = _welt(welt)
    _ok(_entscheid(welt, "A-M6", "abgelehnt", keys=("vorstand",), rolle="mensch/vorstand"),
        "Rueckzug unsigniert")
    gezeichnet = _entscheid(welt, "A-Q1", "abgelehnt", keys=("vorstand", "aktuariat"),
                            ordnung=o1, rolle=VA, mandat=_mandat(welt))
    assert gezeichnet.exit_code == 20, gezeichnet.errors
    assert gezeichnet.errors[0]["code"] == "fallauftrag"
    assert gezeichnet.errors[0]["message"].startswith("Gezeichnete Ablehnung verweigert:")
    assert "unsigniert" in gezeichnet.errors[0]["message"]
    _ok(_entscheid(welt, "A-Q1", "abgelehnt", keys=("vorstand", "aktuariat"), rolle=VA),
        "A-Q1 unsigniert")


@pytest.mark.parametrize("gezeichnet", [True, False])
def test_rueckzug_des_auftrags_bleibt_moeglich(tmp_path, gezeichnet):
    """A-M6 abgelehnt steht nicht unter einem Auftrag — er ist der Akt auf dem
    Auftrag. Gezeichnet und unsigniert, auch wenn der Auftrag nicht mehr gilt
    (die Lieferung hat sich geaendert)."""
    welt = tmp_path / "welt"
    o1 = _welt(welt)
    quelle = welt / "zweite-quelle.txt"
    quelle.write_text("nachgereicht\n", encoding="utf-8")
    fall_mod.registrieren(welt / FALL, quelle)
    if gezeichnet:
        ergebnis = _entscheid(welt, "A-M6", "abgelehnt", keys=("vorstand",), ordnung=o1,
                              rolle="mensch/vorstand")
    else:
        ergebnis = _entscheid(welt, "A-M6", "abgelehnt", keys=("vorstand",),
                              rolle="mensch/vorstand")
    _ok(ergebnis, "Rueckzug")
    (rueckzug,) = _ablehnungen(welt, "A-M6")
    assert ("freigabe" in rueckzug) is gezeichnet
    assert "fallauftrag" not in rueckzug


def test_schema_verlangt_den_auftrag_in_der_gezeichneten_ablehnung_im_fall(abgenommen):
    welt, o1 = abgenommen
    _ok(_widerruf(welt, o1), "Widerruf")
    (widerruf,) = _ablehnungen(welt)
    assert P9Snapshot.validate_payload(widerruf) == []
    ohne = {k: v for k, v in widerruf.items() if k != "fallauftrag"}
    assert any("fallauftrag" in f for f in P9Snapshot.validate_payload(ohne))


# --------------------------------------------------------------------------- #
# Ratsche: jede Bedingung "angenommen" in main ist entschieden
# --------------------------------------------------------------------------- #


def test_nach_einer_nachgereichten_quelle_fuehrt_der_weg_ueber_den_neuen_auftrag(abgenommen):
    """Kein toter Weg (bei der Vereinigung von Hand gefahren, hier festgehalten):
    Wird NACH der Migrationsabnahme eine Quelle nachgereicht, gilt der Auftrag
    nicht mehr. Der gezeichnete Widerruf wird dann benannt verweigert und nennt
    den Ausweg; nach der neuen Beauftragung tragen Widerruf und Abbruch."""
    welt, o1 = abgenommen
    quelle = welt / "zweite-quelle.txt"
    quelle.write_text("nachgereicht\n", encoding="utf-8")
    fall_mod.registrieren(welt / FALL, quelle)
    verweigert = _widerruf(welt, o1)
    assert verweigert.exit_code == 20 and verweigert.errors[0]["code"] == "fallauftrag"
    meldung = verweigert.errors[0]["message"]
    assert meldung.startswith("Gezeichnete Ablehnung verweigert")
    assert "die Lieferung hat sich geaendert" in meldung and "unsigniert ablehnen" in meldung
    assert _abbruch(welt, o1).exit_code == 20            # die Annahme sperrt weiter
    _ok(fall_belegen.main([
        "auftrag", "--fall", str(welt / FALL), "--linie", str(welt / "linie"),
        "--zeichnungsordnung", str(o1), "--programmleitung-schluessel", str(_key(welt, "pl")),
        "--programmleitung-klasse", "mensch", "--auftrag", "Fall J, zweite Fassung",
        "--mandat", f"{VA}={_mandat(welt)}"]), "Auftrag neu (Vorlage)")
    _ok(_entscheid(welt, "A-M6", "angenommen", keys=("vorstand",), ordnung=o1), "A-M6 neu")
    _ok(_widerruf(welt, o1), "Widerruf unter dem neuen Auftrag")
    _ok(_abbruch(welt, o1), "Abbruch")
    assert len(_snapshots(welt, "A-M5")) == 1


def _annahme_bedingungen(quelle: str, funktion: str = "main"):
    """Je Vergleich ``args.entscheid == 'angenommen'`` in ``funktion`` der
    groesste umschliessende Ausdruck (Quelltext) — die Bedingung, an der er haengt."""
    baum = ast.parse(quelle)
    (ziel,) = [k for k in ast.walk(baum)
               if isinstance(k, ast.FunctionDef) and k.name == funktion]
    eltern = {kind: k for k in ast.walk(ziel) for kind in ast.iter_child_nodes(k)}
    gefunden = []
    for k in ast.walk(ziel):
        if (isinstance(k, ast.Compare) and ast.unparse(k.left) == "args.entscheid"
                and len(k.ops) == 1 and isinstance(k.ops[0], ast.Eq)
                and ast.unparse(k.comparators[0]) == "'angenommen'"):
            ausdruck = k
            while isinstance(eltern.get(ausdruck), ast.expr):
                ausdruck = eltern[ausdruck]
            gefunden.append(ast.unparse(ausdruck))
    return sorted(gefunden)


#: Jede Stelle in ``main``, die an "angenommen" haengt — entschieden (ADR-026,
#: Nachtrag Pruefrunde J, Tabelle): Sie gilt NUR der Annahme. Was der
#: Zeichnung gilt, haengt an ``gezeichnet``.
NUR_ANNAHME = sorted([
    # Agentenrolle: ein Agent darf ablehnen, nicht annehmen
    "args.rolle is not None and args.rolle.startswith('agent/') and "
    "(args.entscheid == 'angenommen')",
    # Definition der Zeichnung selbst
    "args.entscheid == 'angenommen' or ablehnung_gezeichnet_von is not None",
    # Vorlage von Auftrag/Abbruch: eine Ablehnung bindet keine Vorlage
    "args.entscheid == 'angenommen' and args.gate in LEBENSLAUF_GATES",
    # A-O1-Vokabular: nur Angenommenes wird Vokabular
    "args.entscheid == 'angenommen' and args.gate == 'A-O1'",
    # Belege des Linienbereichs: eine Ablehnung pinnt keine Belege
    "args.entscheid == 'angenommen' and linie_modus",
    # Eingang, A-Box, gate-eigene Vorbedingungen, Pflichtbelege
    "args.entscheid == 'angenommen' and (not linie_modus) and "
    "(args.gate not in LEBENSLAUF_GATES)",
    # Sicht der gepinnten Belege
    "args.entscheid == 'angenommen'",
    # Schluessel ohne Rolle: bei der gezeichneten Ablehnung per Konstruktion bestimmt
    "bestimmt is None and args.entscheid == 'angenommen'",
    # Wortlaut der Meldung jeder Zeichnung (beide Faelle, EINE Stelle)
    "'Annahme verweigert' if args.entscheid == 'angenommen' else "
    "'Gezeichnete Ablehnung verweigert'",
    # Inhalt von Auftrag/Abbruch im Snapshot
    "args.entscheid == 'angenommen' and args.gate in P9_LEBENSLAUF_FELDER",
    # Ausgabe
    "args.gate == AUFTRAG_GATE and args.entscheid == 'angenommen'",
    "args.gate == ABBRUCH_GATE and args.entscheid == 'angenommen'",
])


def test_ratsche_jede_annahme_bedingung_in_main_ist_entschieden():
    assert _annahme_bedingungen(GATE_QUELLE.read_text(encoding="utf-8")) == NUR_ANNAHME


def test_ratsche_fallauftrag_pruefen_haengt_an_der_zeichnung():
    """Der Aufruf von ``fallauftrag_pruefen`` in ``main`` steht unter einer
    Bedingung, die ``gezeichnet`` liest — nicht unter "angenommen"."""
    baum = ast.parse(GATE_QUELLE.read_text(encoding="utf-8"))
    (main,) = [k for k in ast.walk(baum) if isinstance(k, ast.FunctionDef) and k.name == "main"]
    bedingungen = [ast.unparse(k.test) for k in ast.walk(main) if isinstance(k, ast.If)
                   and any(isinstance(c, ast.Call)
                           and getattr(c.func, "id", None) == "fallauftrag_pruefen"
                           for s in k.body for c in ast.walk(s))]
    assert bedingungen == ["gezeichnet and (not linie_modus) and (args.gate != AUFTRAG_GATE)"]


def test_ratsche_positivkontrolle_des_detektors():
    quelle = ("def main(args, x):\n"
              "    if args.entscheid == 'angenommen' and x:\n        pass\n"
              "    y = 'a' if args.entscheid == 'angenommen' else 'b'\n"
              "    if args.entscheid == 'abgelehnt':\n        pass\n"
              "def andere(args):\n    return args.entscheid == 'angenommen'\n")
    assert _annahme_bedingungen(quelle) == sorted([
        "args.entscheid == 'angenommen' and x",
        "'a' if args.entscheid == 'angenommen' else 'b'"])
