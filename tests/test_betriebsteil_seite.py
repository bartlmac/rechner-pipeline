"""Der Betriebsteil der Seite: ``betrieb/`` ohne Fall, aus Paket, Anker und A-B1.

Entscheid des Maintainers 09.10.2026 (Weg C): Die Seite hat zwei Teile. Der
Rahmen aendert sich nur per Pull Request; der Betriebsteil jeden Abend, gebaut
im Workflow von plv-fiktion aus dem, was der Tagesbetrieb in den Zweig
``betrieb`` legt (``paket/`` mit den oeffentlichen Dateien, ``anker.jsonl``,
``A-B1.json``). Dort gibt es keinen Fall-Arbeitsbereich und kein Tagesjournal.

Gebaut wird hier, was der Workflow baut: ein Paket im Schema 6 als
Auslieferung, die A-B1 durch den echten Gate-Pfad, beides mit Testschluesseln.

Knoten: system/betrieb
"""
from __future__ import annotations

import datetime as dt
import hashlib
import json
import re
import shutil
import sys
import xml.etree.ElementTree as ET
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "werkzeuge"))

import falldaten as fd  # noqa: E402
import grafik  # noqa: E402
import unternehmensseite as us  # noqa: E402
from vorzeigeseite import VeroeffentlichungFehler  # noqa: E402

from rechner_pipeline.betrieb import seite as st  # noqa: E402
from rechner_pipeline.models import anker as ak  # noqa: E402
from tests.test_betrieb_seite import _ablage  # noqa: E402
from tests.test_paket_anker_t2404 import _agentenordnung, _kopie_mit, _zug_betrag_verdoppeln  # noqa: E402

QUELLEN = ROOT / "plv" / "seite"


def _ab1(fall: Path, anker: Path, satz: str) -> Path:
    from rechner_pipeline.gates import gate_entscheid
    from tests.zeichnung_fixture import annahme_args

    ergebnis = gate_entscheid.main([
        "--fall", str(fall), "--gate", "A-B1", "--entscheid", "angenommen",
        "--entscheider", "Betriebsverantwortung", "--begruendung", "Stand geht nach aussen.",
        "--anker", str(anker), "--ankersatz", satz, "--repo-root", str(ROOT),
        *annahme_args(fall, rolle="mensch/betrieb", gates=["A-B1"])])
    assert ergebnis.exit_code == 0, ergebnis.errors
    return Path(ergebnis.paths["snapshot"])


@pytest.fixture(scope="module")
def auslieferung(tmp_path_factory):
    """Paket (Schema 6, Auslieferung), Ankerdatei und die A-B1, die genau
    seinen Ankersatz bindet — wie die Routine sie in den Zweig betrieb legt.
    Dazu eine zweite A-B1, die einen anderen Satz bindet."""
    from rechner_pipeline.betrieb.tageslauf import tageslauf
    from rechner_pipeline.gates.abox_validate import main as pq3
    from tests.e2e_fixture import bereite_pk1_fall

    basis = tmp_path_factory.mktemp("betriebsteil")
    ablage = _ablage(basis / "plv")
    # Schluessel und Ordnung des Exports liegen fuer sich; neben dem Fall legt
    # annahme_args die Ordnung der menschlichen Rollen an.
    (basis / "export").mkdir()
    schluessel, ordnung = _agentenordnung(basis / "export")
    anker_dir = basis / "anker"
    ankerdatei = anker_dir / ak.ANKER_DATEI
    fall = bereite_pk1_fall(basis, ("klv/tg2012",), scope="bestand")
    assert pq3(["--fall", str(fall), "--repo-root", str(ROOT)]).exit_code == 0

    def ausliefern(tag: dt.date, name: str):
        assert tageslauf(ablage, tag)[0] == 0
        paket = st.stands_paket(ablage, basis / name, anker_verzeichnis=anker_dir,
                                art=ak.ART_AUSLIEFERUNG, schluessel=schluessel,
                                zeichnungsordnung=ordnung)
        stand = json.loads((paket / "stand.json").read_text(encoding="utf-8"))
        assert stand["schema_version"] == st.PAKET_SCHEMA_VERSION == 6
        return paket, stand["anker"]["sha256"]

    # Die Freigabe von gestern: echt gezeichnet, aber fuer einen anderen
    # Ankersatz derselben Ankerdatei. Dann der Stand von heute und seine A-B1.
    _, satz_gestern = ausliefern(dt.date(2026, 2, 3), "paket-gestern")
    fremd = _ab1(fall, ankerdatei, satz_gestern)
    paket, satz = ausliefern(dt.date(2026, 2, 4), "paket")
    assert satz != satz_gestern
    ab1 = _ab1(fall, ankerdatei, satz)
    # Der Zweig betrieb traegt nur die oeffentlichen Dateien: ohne Parquet.
    oeffentlich = basis / "zweig" / "paket"
    shutil.copytree(paket, oeffentlich, ignore=shutil.ignore_patterns("*.parquet"))
    assert not list(oeffentlich.rglob("*.parquet")) and list(paket.rglob("*.parquet"))
    return {"paket": paket, "oeffentlich": oeffentlich, "anker": ankerdatei, "ab1": ab1,
            "fremd": fremd, "satz": satz}


def test_die_a_b1_als_datei_bindet_genau_ihren_ankersatz(auslieferung):
    """Der Betriebsteil nimmt die A-B1 als Datei (die Routine legt sie neben
    das Paket), nicht aus einem Fall. Sie muss den Ankersatz des Pakets
    binden; eine A-B1 fuer einen anderen Satz bindet nichts. Die Pruefsumme
    der Datei steht im Modell, damit der Bau genau diese Bytes veroeffentlicht.

    Mutationsprobe: in ``falldaten._pruefe_auslieferung`` die Pruefung der
    Bindung entfernen -> die fremde A-B1 geht durch, rot."""
    a = auslieferung
    modell = fd.betrieb(a["paket"], a["anker"], a["ab1"])
    abnahme = modell["verankerung"]["abnahme"]
    assert abnahme["datei_sha256"] == hashlib.sha256(a["ab1"].read_bytes()).hexdigest()
    assert abnahme["rolle"] == "mensch/betrieb" and abnahme["entschieden_am"]
    with pytest.raises(fd.FalldatenFehler, match="bindet seinen Ankersatz"):
        fd.betrieb(a["paket"], a["anker"], a["fremd"])
    with pytest.raises(fd.FalldatenFehler, match="ohne Abnahme"):
        fd.betrieb(a["paket"], a["anker"], None)


def test_ein_oeffentliches_paket_ist_gebunden_nicht_nachgerechnet(auslieferung, tmp_path):
    """Ohne Tagesjournal und Abschluesse rechnet niemand Geschaeftsentwicklung
    und Abschlusskennzahlen nach; sie gelten, weil der Ankersatz stand.json
    als Ganzes bindet. Dieselben Zahlen wie mit allen Dateien; eine
    geaenderte Zahl faellt am Anker. Fehlt eine oeffentliche Datei, faellt
    das Paket weiter; ohne ``oeffentlich`` faellt es am fehlenden Journal.

    Mutationsprobe: in ``falldaten.betrieb`` die Bloecke im oeffentlichen
    Modus aus einer leeren Vorgabe statt aus stand.json nehmen -> die Zahlen
    weichen ab, rot."""
    a = auslieferung
    voll = fd.betrieb(a["paket"], a["anker"], a["ab1"])
    offen = fd.betrieb(a["oeffentlich"], a["anker"], a["ab1"], oeffentlich=True)
    for feld in ("geschaeftsentwicklung", "abschluss_kennzahlen", "abschluesse", "bestand",
                 "buchungen", "neugeschaeft", "verankerung"):
        assert offen[feld] == voll[feld], feld
    with pytest.raises(fd.FalldatenFehler, match="parquet' fehlt"):
        fd.betrieb(a["oeffentlich"], a["anker"], a["ab1"])

    gefaelscht = tmp_path / "zahl"
    _kopie_mit(a["oeffentlich"], gefaelscht, _zug_betrag_verdoppeln)
    with pytest.raises(fd.FalldatenFehler, match="stand.json ist nicht die, die der Anker bindet"):
        fd.betrieb(gefaelscht, a["anker"], a["ab1"], oeffentlich=True)

    ohne_seite = tmp_path / "ohne-index"
    shutil.copytree(a["oeffentlich"], ohne_seite)
    (ohne_seite / "index.html").unlink()
    with pytest.raises(fd.FalldatenFehler, match="'index.html' fehlt"):
        fd.betrieb(ohne_seite, a["anker"], a["ab1"], oeffentlich=True)


def test_der_betriebsteil_schreibt_nur_unter_betrieb(auslieferung, tmp_path, monkeypatch):
    """Der Bau des Abends (``--teil betrieb``) in einen Baum, der den Rahmen
    traegt: Bestandsfuehrung, Stands-Paket, die drei Grafiken in zwei Breiten
    als eigene SVG-Dateien und die A-B1, byteweise. Ausserhalb von
    ``betrieb/`` bleibt jede Datei, wie sie war; ein Rest im Betriebsteil
    vom Vortag verschwindet."""
    a = auslieferung
    for u in json.loads((a["paket"] / "stand.json").read_text("utf-8"))["uebernahmen"]:
        monkeypatch.setitem(us.UEBERNAHMEN, u["fall"], ("probe", "Probe"))
    daten = tmp_path / "betriebsdaten.json"
    daten.write_text(json.dumps(fd.sammle_betrieb(a["oeffentlich"], a["anker"], a["ab1"], True)),
                     encoding="utf-8")
    ziel = tmp_path / "seite"
    (ziel / "betrieb").mkdir(parents=True)
    (ziel / "betrieb" / "vom-vortag.html").write_text("alt", encoding="utf-8")
    (ziel / "index.md").write_text("# Rahmen\n", encoding="utf-8")
    vorher = {p.relative_to(ziel): p.read_bytes() for p in ziel.rglob("*")
              if p.is_file() and "betrieb" not in p.relative_to(ziel).parts}
    assert us.main(["--teil", "betrieb", "--quellen", str(QUELLEN), "--daten", str(daten),
                    "--out", str(ziel)]) == 0
    nachher = {p.relative_to(ziel): p.read_bytes() for p in ziel.rglob("*")
               if p.is_file() and "betrieb" not in p.relative_to(ziel).parts}
    assert nachher == vorher
    betrieb = ziel / "betrieb"
    assert not (betrieb / "vom-vortag.html").exists()
    assert (betrieb / "A-B1.json").read_bytes() == a["ab1"].read_bytes()
    assert (betrieb / "plv" / "index.html").is_file()
    assert not list(betrieb.rglob("*.parquet"))
    seite = (betrieb / "index.md").read_text(encoding="utf-8")
    assert "{{" not in seite and "Angaben der Snapshot-Datei zur Auslieferung A-B1" in seite
    assert "([Snapshot](A-B1.json))" in seite and "Signatur geprüft" not in seite
    klasse = json.loads(a["ab1"].read_text(encoding="utf-8"))["zeichnung"]["schluesselklasse"]
    assert ("Gezeichnet mit einem Simulationsschlüssel" in seite) == (klasse == "simulation")
    for name in us.BILDER:
        for datei in (f"{name}.svg", f"{name}-handy.svg"):
            text = (betrieb / datei).read_text(encoding="utf-8")
            wurzel = ET.fromstring(text.encode("utf-8"))
            assert wurzel.tag == "{http://www.w3.org/2000/svg}svg", datei
            assert wurzel.get("width") and wurzel.get("height"), datei
            assert "var(" not in text, f"{datei}: eine Farbe, die als Bild niemand aufloest"
            # Die Farben der Seite, nicht die Rueckfallwerte der Variablen.
            assert "#6a7075" in text and "#5f6663" not in text, datei


def test_der_betriebsteil_braucht_eine_freigabe(auslieferung, tmp_path, capsys, monkeypatch):
    """Eine Momentaufnahme ohne A-B1 kommt nicht in den Betriebsteil: Was
    nach aussen geht, hat die Betriebsverantwortung freigegeben. Und
    veroeffentlicht werden genau die Bytes, die gegen den Ankersatz gingen:
    Ein Snapshot, der seit der Pruefung andere Bytes traegt, haelt an.

    Mutationsprobe: in ``unternehmensseite._main_betrieb`` den Aufruf von
    ``freigabe`` auslassen -> der zweite Fall baut, rot."""
    a = auslieferung
    for u in json.loads((a["paket"] / "stand.json").read_text("utf-8"))["uebernahmen"]:
        monkeypatch.setitem(us.UEBERNAHMEN, u["fall"], ("probe", "Probe"))
    modell = fd.sammle_betrieb(a["paket"], a["anker"], a["ab1"])
    ohne = json.loads(json.dumps(modell))
    ohne["betrieb"]["verankerung"].pop("abnahme")
    daten = tmp_path / "betriebsdaten.json"
    daten.write_text(json.dumps(ohne), encoding="utf-8")
    assert us.main(["--teil", "betrieb", "--quellen", str(QUELLEN), "--daten", str(daten),
                    "--out", str(tmp_path / "seite")]) == 1
    assert "ohne A-B1 wird der Betriebsteil nicht veroeffentlicht" in capsys.readouterr().err

    getauscht = tmp_path / "A-B1.json"
    getauscht.write_bytes(a["ab1"].read_bytes() + b"\n")
    modell["betrieb"]["verankerung"]["abnahme"]["datei"] = str(getauscht)
    daten.write_text(json.dumps(modell), encoding="utf-8")
    assert us.main(["--teil", "betrieb", "--quellen", str(QUELLEN), "--daten", str(daten),
                    "--out", str(tmp_path / "seite2")]) == 1
    assert "andere Bytes als die, die gegen den Ankersatz gingen" in capsys.readouterr().err
    modell["betrieb"]["verankerung"]["abnahme"]["datei"] = str(a["ab1"])
    daten.write_text(json.dumps(modell), encoding="utf-8")
    assert us.main(["--teil", "betrieb", "--quellen", str(QUELLEN), "--daten", str(daten),
                    "--out", str(tmp_path / "seite3")]) == 0, "Positivkontrolle"


def _platzhalter(teil: str):
    for datei in sorted(QUELLEN.rglob("*.md")):
        rel = datei.relative_to(QUELLEN)
        if (rel.parts[0] == us.BETRIEB_DIR) != (teil == "betrieb"):
            continue
        for m in us.KENNZAHL.finditer(datei.read_text(encoding="utf-8")):
            yield rel, m.group(1), m.group(2)


def test_kein_platzhalter_des_rahmens_braucht_das_stands_paket():
    """Der Rahmen aendert sich nur per Pull Request; eine Zahl des gefuehrten
    Bestands darin stuende bis zum naechsten Pull Request still. Jeder
    Platzhalter des Rahmens wird gegen ein Modell OHNE Paket aufgeloest: Er
    darf an fehlenden Falldaten scheitern, nie am fehlenden Paket.

    Mutationsprobe: auf der Startseite wieder {{svg:bestand_vergleich}}
    einsetzen -> rot."""
    gesehen = 0
    for rel, art, pfad in _platzhalter("rahmen"):
        gesehen += 1
        try:
            if art in ("svg", "tabelle", "html", "bild"):
                us._generiert(art, pfad, {"betrieb": {"vorhanden": False}}, None, "")
            else:
                us._aufloesen({"betrieb": {"vorhanden": False}}, pfad)
        except (KeyError, ValueError, TypeError, IndexError, AttributeError) as exc:
            assert "kein Stands-Paket" not in str(exc), f"{rel}: {{{{{art}:{pfad}}}}}"
    assert gesehen > 5


def test_jede_grafik_des_rahmens_schreibt_der_betriebsteil():
    """Der Rahmen kennt nur die Dateinamen der Grafiken; der Betriebsteil
    schreibt sie. Beide Mengen sind dieselbe (``==``): Eine Grafik, die nur
    der Rahmen kennt, waere ein toter Verweis, eine, die nur der Betriebsteil
    schreibt, eine Datei, die niemand zeigt."""
    im_rahmen = {pfad for _, art, pfad in _platzhalter("rahmen") if art == "bild"}
    assert im_rahmen == set(us.BILDER)
    assert not any(art == "bild" for _, art, _ in _platzhalter("betrieb"))
    markup = us._bild("zugang", "")
    assert 'srcset="betrieb/zugang-handy.svg"' in markup and 'src="betrieb/zugang.svg"' in markup
    assert us.BILD_HANDY in markup and "<figcaption>Zugang · Verträge</figcaption>" in markup
    with pytest.raises(KeyError):
        us._bild("unbekannt", "")


def test_der_rahmen_zeigt_kein_stands_paket(tmp_path, capsys):
    """Ein Modell mit Paket wird als Rahmen nicht gebaut: Sonst trueg der
    Rahmen eine Zahl des Tages, die bis zum naechsten Pull Request stehen
    bliebe. Und ``baue`` trennt die Quellen: der Rahmen ohne ``betrieb/``.

    Mutationsprobe: die Abweisung in ``unternehmensseite.main`` entfernen ->
    der Bau scheitert an etwas anderem, die Meldung fehlt, rot."""
    daten = tmp_path / "falldaten.json"
    daten.write_text(json.dumps({"betrieb": {"vorhanden": True}}), encoding="utf-8")
    film = tmp_path / "film.mp4"
    film.write_bytes(b"")
    assert us.main(["--teil", "rahmen", "--quellen", str(QUELLEN), "--daten", str(daten),
                    "--out", str(tmp_path / "seite"), "--film", str(film)]) == 1
    assert "Das Modell des Rahmens traegt ein Stands-Paket" in capsys.readouterr().err
    quellen = tmp_path / "quellen"
    (quellen / "betrieb").mkdir(parents=True)
    (quellen / "_config.yml").write_text("", encoding="utf-8")
    (quellen / "index.md").write_text("Fiktives Unternehmen\n# A\n", encoding="utf-8")
    (quellen / "betrieb" / "index.md").write_text("Fiktives Unternehmen\n# B\n", encoding="utf-8")
    assert us.baue(quellen, tmp_path / "r", {}, "rahmen") == ["_config.yml", "index.md"]
    assert us.baue(quellen, tmp_path / "b", {}, "betrieb") == ["betrieb/index.md"]


def test_die_uebernahme_im_betriebsteil_heisst_wie_im_rahmen(tmp_path):
    """Der Betriebsteil nennt eine Uebernahme mit dem Namen aus UEBERNAHMEN,
    der Rahmen haelt diesen Eintrag gegen den Fall, den er baut."""
    ziel = tmp_path / "seite"
    (ziel / "migrationen" / "baldrian").mkdir(parents=True)
    (ziel / "migrationen" / "baldrian" / "index.md").write_text("# F\n", encoding="utf-8")
    modell = {"fall": {"name": "baldrian-klv-tg2015-fall3"},
              "bestand": {"verteilungen": {"produkt": {"klv": 834},
                                           "tarif_generation": {"TG2015": 834}}}}
    us._pruefe_uebernahme(modell, ziel)   # Positivkontrolle: der Eintrag passt
    modell["bestand"]["verteilungen"]["tarif_generation"] = {"TG2012": 834}
    with pytest.raises(VeroeffentlichungFehler, match="UEBERNAHMEN"):
        us._pruefe_uebernahme(modell, ziel)


def test_eine_grafik_als_eigene_datei_bringt_alles_mit():
    """Ein Bild sieht weder das Stylesheet noch die CSS-Variablen der Seite:
    jede Farbe als Wert, Namensraum und Groesse in der Datei. Eine Farbe
    ohne Rueckfall haelt an."""
    svg = grafik.anteil([("KLV", 3), ("BU", 1)], "Verträge")
    farben = grafik.css_farben((QUELLEN / "assets" / "stil.css").read_text(encoding="utf-8"))
    assert farben["text-matt"] == "#6a7075" and farben["serie-1"] == "#2a78d6"
    assert "#6a7075" in grafik.datei(svg, farben) and "#5f6663" in grafik.datei(svg)
    datei = grafik.datei(svg)
    wurzel = ET.fromstring(datei.encode("utf-8"))
    assert wurzel.get("width") == str(grafik.BREITE_SCHMAL)
    assert "var(" not in datei and grafik.SERIE[0].split(", ")[1].rstrip(")") in datei
    assert re.search(r"<title>KLV 3, BU 1</title>", datei)
    with pytest.raises(ValueError, match="Rueckfall"):
        grafik.datei(svg.replace("var(--serie-1, #2a78d6)", "var(--serie-1)"))
    with pytest.raises(ValueError):
        grafik.datei("<svg></svg>")
