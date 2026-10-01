"""Jedes Glied der Ordnungslinie nach dem ersten ist vom Vorstand gezeichnet — und wird so gelesen.

Befund der Pruefrunde G (G09, Schwere hoch): ``models.ordnungslinie.lade_linie``
prueft die Signatur eines Glieds nur, wenn ihr ein Ring uebergeben wird, und
KEIN gruendender Leser uebergab einen — auch das Gate nicht, das den
Schluessel des Vorstands fuer jede Annahme im Fall ohnehin im Ring haelt
(ADR-026). Wer ``linie/ordnung/`` beschreiben konnte, haengte ein Glied mit
gefaelschter Zeichnung an (richtiger Fingerabdruck, Signatur geraten),
vergab sich darin eine Rolle und zeichnete darunter.

Invariante: Keine Annahme, kein Verweis, keine Registrierung und keine
Bindung gruendet auf einer Linie, deren Glieder nicht gegen den Schluessel
des Vorstands geprueft sind. Menge: jeder gruendende Leser der Linie (Gate,
die vier Betriebskommandos mit ``--linie``, der Produzent, der ein Glied
anhaengt) — gehalten als Ratsche in ``tests/test_linie_pflicht.py``.

Die Faelschungen hier sind von Hand gebaut wie im Repro des Pruefers: das
Glied selbst ist formal stimmig (Kette, Hash, gerechnete Aenderungsliste,
Fingerabdruck der Spitze davor), nur die Signatur ist nicht die des
Vorstands.

Knoten: system/entscheid
"""

from __future__ import annotations

import hashlib
import json
import secrets
import shutil
from pathlib import Path

from rechner_pipeline.gates import gate_entscheid, kernstand_belegen
from rechner_pipeline.models import ordnungslinie as ol
from tests.zeichnung_fixture import (
    RECHENKERN,
    RECHENKERN_SCHLUESSEL_DATEI,
    VORSTAND_SCHLUESSEL_DATEI,
    annahme_args,
    linie_anlegen,
)

REPO = Path(__file__).resolve().parents[1]
EINGETRAGEN = "2026-10-01T09:00:00+00:00"


def _glieder_roh(linie: Path) -> list:
    """Die Glieder, wie sie auf der Platte liegen (ohne jede Pruefung)."""
    return sorted((json.loads(p.read_text(encoding="utf-8"))
                   for p in (linie / ol.VERZEICHNIS).glob("*.json")),
                  key=lambda g: g["nummer"])


def _faelsche_glied(linie: Path, neu: dict, *, zeichnender_fp: str | None = None) -> dict:
    """Ein Glied an die Spitze haengen, dessen Zeichnung der Vorstand nie
    geleistet hat: Fingerabdruck der Spitze davor, Signatur geraten."""
    spitze = _glieder_roh(linie)[-1]
    vorher = ol.ordnung_aus(spitze)
    roh = json.dumps(neu, sort_keys=True).encode("utf-8")
    # Der Faelscher legt auch die Erklaerung je geminderter Rolle bei
    # (Pruefrunde H): Gefangen werden soll er an der Signatur, nicht an der Form.
    glied = ol.baue_glied(roh, nummer=spitze["nummer"] + 1, vorgaenger=spitze["glied_sha256"],
                          eingetragen_am=EINGETRAGEN, vorher=vorher,
                          fruehere_zeichnungen=_gueltig(vorher, neu))
    glied.pop("glied_sha256")
    glied["zeichnung"] = {
        "gate": ol.ORDNUNGS_GATE, "rolle": ol.WURZELROLLE,
        "schluesselklasse": vorher["rollen"][ol.WURZELROLLE]["schluesselklasse"],
        "schluessel_sha256": zeichnender_fp or ol.vorstand_schluessel_sha256(vorher),
        "verfahren": ol.ZEICHEN_VERFAHREN, "signatur": "0" * 64}
    glied["glied_sha256"] = ol.glied_sha256(glied)
    (linie / ol.VERZEICHNIS / ol.dateiname(glied)).write_text(
        json.dumps(glied, ensure_ascii=False, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    return glied


def _gueltig(vorher: dict, neu: dict) -> dict:
    """Je geminderter Rolle die Erklaerung "gueltig" (Pruefrunde H)."""
    return {r: "gueltig" for r in ol.geminderte_rollen(ol.aenderungen(vorher, neu))}


def _angreifer(verzeichnis: Path) -> Path:
    datei = verzeichnis / "aussen" / "angreifer.key"
    datei.parent.mkdir(parents=True, exist_ok=True)
    datei.write_bytes(secrets.token_bytes(64))
    datei.chmod(0o600)
    return datei


def _fp(datei: Path) -> str:
    return hashlib.sha256(datei.read_bytes()).hexdigest()


def _vorstandsring(verzeichnis: Path) -> dict:
    key = (verzeichnis / VORSTAND_SCHLUESSEL_DATEI).read_bytes()
    return {hashlib.sha256(key).hexdigest(): key}


# --------------------------------------------------------------------------- #
# Das Gate: unter einem gefaelschten Glied zeichnet niemand
# --------------------------------------------------------------------------- #


def test_unter_einem_gefaelschten_glied_wird_nicht_gezeichnet(tmp_path):
    """Der Angriff des Pruefers ueber das echte Gate: Ein gefaelschtes Glied
    gibt der Rolle ``mensch/rechenkern`` den Schluessel des Angreifers, er
    zeichnet A-K2 im Linienbereich. Rot vor dem Fix: exit 0.

    Mutationsprobe: im Gate ``lade_linie`` den Ring nicht reichen (leerer
    Ring) -> die Linie hat zwei Glieder, der Leser verweigert benannt "nicht
    pruefbar" statt "Signatur" -> die erste Meldungspruefung rot; den
    Signaturvergleich in ``zeichnung_fehler`` entfernen -> exit 0 -> rot."""
    linie = linie_anlegen(tmp_path)
    angreifer = _angreifer(tmp_path)
    ordnung = json.loads((tmp_path / "zeichnungsordnung.json").read_text(encoding="utf-8"))
    ordnung["rollen"][RECHENKERN]["schluessel_sha256"] = _fp(angreifer)
    glied = _faelsche_glied(linie, ordnung)
    # Der Angreifer zeichnet unter "seiner" Spitze: die Ordnungsdatei des
    # Aufrufs ist die des gefaelschten Glieds, der zeichnende Schluessel seiner.
    (tmp_path / "zeichnungsordnung.json").write_text(glied["ordnung_text"], encoding="utf-8")
    assert kernstand_belegen.main(["--linie", str(linie), "--repo-root", str(REPO),
                                   "--von", "HEAD", "--begruendung", "x"]).exit_code == 0
    args = annahme_args(linie, fuer="A-K2")
    args[args.index(str(tmp_path / RECHENKERN_SCHLUESSEL_DATEI))] = str(angreifer)
    assert str(tmp_path / VORSTAND_SCHLUESSEL_DATEI) in args   # der Ring HAT den Vorstand
    ergebnis = gate_entscheid.main([
        "--linie", str(linie), "--gate", "A-K2", "--entscheid", "angenommen",
        "--entscheider", "angreifer", "--begruendung", "unter eigenem Glied",
        "--repo-root", str(REPO), *args])
    assert ergebnis.exit_code != 0, "unter einem gefaelschten Glied gezeichnet"
    meldung = ergebnis.errors[0]["message"]
    assert f"Glied {glied['nummer']}: die Signatur stimmt nicht" in meldung, meldung
    assert not list((linie / "entscheide").glob("A-K2-*.json"))


def test_im_fall_gruendet_keine_annahme_auf_einem_gefaelschten_glied(tmp_path):
    """Dieselbe Regel im Fall: Jede Annahme liest die Linie, unter der sie
    zeichnet, MIT dem Ring — der Vorstandsschluessel liegt dort ohnehin
    (der Fallauftrag wird damit geprueft, ADR-026)."""
    from tests.test_pk1_am4_beweisvertrag import _bereite_fall, _p9_annahme

    fall = _bereite_fall(tmp_path, ("klv/tg2012",))
    linie = tmp_path / "linie"
    ordnung = json.loads((tmp_path / "zeichnungsordnung.json").read_text(encoding="utf-8"))
    ordnung["rollen"]["mensch/revision"] = {
        "schluessel_sha256": "ab" * 32, "schluesselklasse": "simulation", "gates": []}
    glied = _faelsche_glied(linie, ordnung)
    (tmp_path / "zeichnungsordnung.json").write_text(glied["ordnung_text"], encoding="utf-8")
    ergebnis = _p9_annahme(fall, "A-M1", "unter gefaelschtem Glied")
    assert ergebnis.exit_code != 0, "im Fall unter einem gefaelschten Glied gezeichnet"
    assert "die Signatur stimmt nicht" in ergebnis.errors[0]["message"], ergebnis.errors


def test_ein_glied_das_den_vorstand_selbst_austauscht(tmp_path):
    """Der abgeleitete, vom Pruefer nicht gemessene Fall: Das gefaelschte
    Glied gibt der Wurzelrolle den Schluessel des Angreifers. Jedes Glied
    danach zeichnet er "richtig" — mit dem Schluessel, den die (gefaelschte)
    Spitze davor ihm gibt. Gefangen wird es am gefaelschten Glied: Seine
    Signatur prueft der Schluessel des ALTEN Vorstands, den der Ring traegt.
    Haelt der Leser auch den Angreiferschluessel, aendert das nichts.

    Gemessen: Diese Probe des LESERS war schon vor dem Fix gruen, wenn man
    ihm den Ring gab — rot war, dass kein gruendender Leser ihn gab (die
    Proben ueber Gate und Betrieb in diesem Modul)."""
    linie = linie_anlegen(tmp_path)
    angreifer = _angreifer(tmp_path)
    ordnung = json.loads((tmp_path / "zeichnungsordnung.json").read_text(encoding="utf-8"))
    ordnung["rollen"][ol.WURZELROLLE]["schluessel_sha256"] = _fp(angreifer)
    gefaelscht = _faelsche_glied(linie, ordnung)
    zweiter = _angreifer(tmp_path / "zwei")
    weiter = json.loads(json.dumps(ordnung))
    weiter["rollen"][RECHENKERN]["schluessel_sha256"] = _fp(zweiter)
    glieder = _glieder_roh(linie)
    folge = ol.neues_glied(glieder, json.dumps(weiter, sort_keys=True).encode("utf-8"),
                           vorgaenger=gefaelscht["glied_sha256"], eingetragen_am=EINGETRAGEN,
                           fruehere_zeichnungen=_gueltig(ordnung, weiter),
                           vorstand_schluessel=angreifer.read_bytes())
    (linie / ol.VERZEICHNIS / ol.dateiname(folge)).write_text(json.dumps(folge),
                                                              encoding="utf-8")
    ring = _vorstandsring(tmp_path)
    for mit_angreifer in (False, True):
        r = dict(ring, **({_fp(angreifer): angreifer.read_bytes()} if mit_angreifer else {}))
        glieder, fehler = ol.lade_linie(linie, ring=r)
        assert glieder == [] and any(
            f.startswith(f"Glied {gefaelscht['nummer']}: die Signatur stimmt nicht")
            for f in fehler), fehler


# --------------------------------------------------------------------------- #
# Der Leser: Ring ist Pflicht, und ohne den Vorstandsschluessel nichts
# --------------------------------------------------------------------------- #


def test_ohne_den_schluessel_des_vorstands_gruendet_keine_linie_mit_zwei_gliedern(tmp_path):
    """Kein stiller Verzicht: Ein Leser, der den Vorstandsschluessel nicht
    haelt, prueft nicht "nur die Form", er verweigert benannt mit Ausweg.
    Ein einzelnes Glied (die unsignierte Wurzel) braucht keinen.

    Mutationsprobe: den Zweig "Schluessel nicht im Ring" in
    ``zeichnung_fehler`` entfernen -> die Linie laedt -> rot."""
    linie = linie_anlegen(tmp_path)
    assert ol.lade_linie(linie, ring={})[1] == []           # nur die Wurzel
    ordnung = json.loads((tmp_path / "zeichnungsordnung.json").read_text(encoding="utf-8"))
    ordnung["rollen"]["mensch/revision"] = {
        "schluessel_sha256": "ab" * 32, "schluesselklasse": "simulation", "gates": []}
    glied = ol.neues_glied(_glieder_roh(linie), json.dumps(ordnung, sort_keys=True).encode(),
                           vorgaenger=_glieder_roh(linie)[-1]["glied_sha256"],
                           eingetragen_am=EINGETRAGEN, fruehere_zeichnungen={},
                           vorstand_schluessel=(tmp_path / VORSTAND_SCHLUESSEL_DATEI).read_bytes())
    (linie / ol.VERZEICHNIS / ol.dateiname(glied)).write_text(json.dumps(glied), encoding="utf-8")
    glieder, fehler = ol.lade_linie(linie, ring={})
    assert glieder == [] and len(fehler) == 1, fehler
    assert "Glied 2" in fehler[0] and "nicht im Ring" in fehler[0] and "Ausweg" in fehler[0]
    glieder, fehler = ol.lade_linie(linie, ring=_vorstandsring(tmp_path))
    assert fehler == [] and len(glieder) == 2


# --------------------------------------------------------------------------- #
# Der Betrieb: die Kommandos mit --linie lesen sie mit dem Ring
# --------------------------------------------------------------------------- #


def _gefaelschte_suitelinie(tmp_path: Path) -> Path:
    """Eine Kopie der Linie der Session mit einem gefaelschten zweiten Glied."""
    from rechner_pipeline.betrieb import tageslauf as tl
    from tests.freigabe_testschluessel import betriebsordnung

    linie = tmp_path / "linie-gefaelscht"
    shutil.copytree(tl._STANDARD_LINIE, linie)
    neu = betriebsordnung({"mensch/revision": {
        "schluessel_sha256": "ab" * 32, "schluesselklasse": "mensch", "gates": []}})
    _faelsche_glied(linie, neu)
    return linie


def _vorstand_der_suite(tmp_path: Path) -> Path:
    from tests.freigabe_testschluessel import VORSTANDKEY

    datei = tmp_path / "aussen" / "vorstand.key"
    datei.parent.mkdir(parents=True, exist_ok=True)
    datei.write_bytes(VORSTANDKEY)
    datei.chmod(0o600)
    return datei


def test_die_bindung_des_anfangsbestands_liest_die_linie_mit_dem_ring(tmp_path, capsys):
    """``anfangsbestand binden`` loest den Schluessel der Ablage unter der
    Linie auf — unter einem gefaelschten Glied nicht."""
    from rechner_pipeline.betrieb import anfangsbestand as anf
    from tests.freigabe_testschluessel import betriebsargs

    linie = _gefaelschte_suitelinie(tmp_path)
    vorstand = _vorstand_der_suite(tmp_path)
    code = anf.main(["binden", "--stand", str(tmp_path / "daten"), "--linie", str(linie),
                     *betriebsargs(), "--freigabe-schluessel", str(vorstand)])
    assert code == 2
    assert "die Signatur stimmt nicht" in capsys.readouterr().err


def test_die_zugangsprobe_liest_die_linie_mit_dem_ring(tmp_path, capsys):
    from rechner_pipeline.betrieb import zugangsprobe as zpb
    from tests.freigabe_testschluessel import betriebsargs

    linie = _gefaelschte_suitelinie(tmp_path)
    vorstand = _vorstand_der_suite(tmp_path)
    (tmp_path / "fall").mkdir()
    (tmp_path / "daten").mkdir()
    code = zpb.main(["--stand", str(tmp_path / "daten"), "--fall", str(tmp_path / "fall"),
                     "--stichtag", "2026-02-01", *betriebsargs(),
                     "--freigabe-schluessel", str(vorstand), "--linie", str(linie)])
    assert code == 2
    assert "die Signatur stimmt nicht" in capsys.readouterr().err


def test_ohne_vorstandsschluessel_nennt_der_betrieb_den_ausweg(tmp_path, capsys):
    """Ohne den Vorstandsschluessel im Ring verweigert das Kommando benannt —
    mit dem Ausweg, ihn als weiteren ``--freigabe-schluessel`` zu reichen."""
    from rechner_pipeline.betrieb import zugangsprobe as zpb
    from tests.freigabe_testschluessel import TESTKEY, betriebsargs

    linie = _gefaelschte_suitelinie(tmp_path)
    anderer = tmp_path / "aussen" / "aktuariat.key"
    anderer.parent.mkdir(parents=True, exist_ok=True)
    anderer.write_bytes(TESTKEY)
    anderer.chmod(0o600)
    (tmp_path / "fall").mkdir()
    (tmp_path / "daten").mkdir()
    code = zpb.main(["--stand", str(tmp_path / "daten"), "--fall", str(tmp_path / "fall"),
                     "--stichtag", "2026-02-01", *betriebsargs(),
                     "--freigabe-schluessel", str(anderer), "--linie", str(linie)])
    assert code == 2
    err = capsys.readouterr().err
    assert "nicht im Ring" in err and "--freigabe-schluessel" in err, err
