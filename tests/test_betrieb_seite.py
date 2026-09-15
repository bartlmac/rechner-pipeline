"""Bestand heute und Stands-Paket: aus Protokoll und Journal, nach der Wache.

Fachkonzept docs/simulation/tagesbetrieb.md, Abschnitt 8.3, Block B8. Die
interne Sicht rendert der Tageslauf nach jedem gruenen Lauf; das
Stands-Paket ist die Quelle der Vorzeigeseite — nichts davon rechnet,
alles ist gebucht und gestempelt.

Knoten: system/betrieb
"""

from __future__ import annotations

import datetime as dt
import json
import re
import shutil
from pathlib import Path

import pytest

from rechner_pipeline.betrieb import seite as st
from rechner_pipeline.betrieb.tageslauf import EXIT_OK, Ablage, lies_protokoll, tageslauf

REPO_ROOT = Path(__file__).resolve().parents[1]
PLV = REPO_ROOT / "configs" / "bestand_gesamt.toml"


def _ablage(wurzel: Path) -> Ablage:
    """Die schnelle Testwelt von :func:`tests.test_betrieb_tageslauf._kleine_config`
    — eine Fassung, nicht zwei: acht Vertraege je Generation und die
    Erzeugungsgrenze am 1.1.2026 statt am Betriebsbeginn 1994 der echten PLV."""
    from tests.test_betrieb_tageslauf import _kleine_config

    ablage = Ablage(wurzel)
    ablage.configs.mkdir(parents=True, exist_ok=True)
    ablage.config_pfad.write_text(_kleine_config(), encoding="utf-8")
    return ablage


@pytest.fixture(scope="module")
def gefuehrt(tmp_path_factory):
    ablage = _ablage(tmp_path_factory.mktemp("plv"))
    assert tageslauf(ablage, dt.date(2026, 2, 3))[0] == EXIT_OK
    return ablage


def test_der_tageslauf_rendert_die_seite_nach_dem_nachweis(gefuehrt):
    zeile = lies_protokoll(gefuehrt.protokoll_pfad)[-1]
    assert zeile["seite"] == "index.html"
    html = (gefuehrt.wurzel / "seite" / "index.html").read_text("utf-8")
    assert "Bestand heute" in html and "Stand 2026-02-03" in html
    assert f"<b>{zeile['bestand']['in_force']}</b><span>Vertraege in Kraft" in html
    assert "abschluss_2026-02-01.parquet" in html and "bestandsbericht_2026-02-01.html" in html
    assert "Wache P-B1: gruen" in html
    assert "nicht erfasst" in html                      # Image ausserhalb des Containers
    # Dieselbe Ehrlichkeit wie die Fall-Seite: Banderole, Stand und Manifest
    # im Kopf, Luecken sichtbar.
    assert "Dies ist eine Vorfuehrung, kein echter Bestand." in html
    assert f"Manifest <code>{zeile['manifest_sha256'][:16]}</code>" in html
    assert "Was diese Seite NICHT zeigt" in html and "Image-Digest des Laufs" in html


def test_modell_und_seite_sind_deterministisch(gefuehrt):
    a, b = st.stand_modell(gefuehrt), st.stand_modell(gefuehrt)
    assert a == b
    assert st.rendere_html(a) == st.rendere_html(b)
    assert a["stand"] == "2026-02-03" and a["gefuehrt_seit"] == "2026-01-01"
    assert a["provenienz"]["pb1"] == "gruen" and a["provenienz"]["manifest_sha256"]
    assert a["buchungen"]["gesamt"] > 0 and a["neugeschaeft"]["seit_betriebsbeginn"] > 0
    assert [x["stichtag"] for x in a["abschluesse"]] == ["2026-01-01", "2026-02-01"]
    assert a["abschluesse"][-1]["bericht"] == "bestandsbericht_2026-02-01.html"


def test_stands_paket_traegt_stempel_und_berichte(gefuehrt, tmp_path):
    paket = st.stands_paket(gefuehrt, tmp_path / "paket")
    stand = json.loads((paket / "stand.json").read_text("utf-8"))
    # Die Zahl steht hier ABSICHTLICH als Literal: Der Paketvertrag ist ein
    # Vertrag mit einem Konsumenten ausserhalb dieses Repos (vorzeige-url).
    # Eine Aenderung soll hier auffallen und abgestimmt werden, nicht
    # stillschweigend mitwandern. Schema 3 seit T24-04 Teil 1 (Journal).
    assert stand["schema_version"] == 3 and stand["stand"] == "2026-02-03"
    # Belege: Protokoll mit Kette und Manifest (T22-05), Tagesjournal
    # (T24-04 Teil 1) fahren mit.
    assert set(stand["dateien"]) == {"index.html", "bestandsbericht_2026-02-01.html",
                                     "protokoll.jsonl", "laufmanifest.json",
                                     "tagesjournal.parquet"}
    assert stand["provenienz"]["manifest_sha256"] == stand["dateien"]["laufmanifest.json"]
    for name, summe in stand["dateien"].items():
        assert (paket / name).is_file() and len(summe) == 64
    # Ein Paket wird ersetzt, nie angesammelt:
    (paket / "fremd.txt").write_text("x", encoding="utf-8")
    st.stands_paket(gefuehrt, paket)
    assert not (paket / "fremd.txt").exists()
    assert st.main(["--stand", str(gefuehrt.wurzel), "--paket", str(tmp_path / "p2")]) == 0
    assert (tmp_path / "p2" / "stand.json").is_file()


def test_luecken_werden_benannt():
    modell = {"provenienz": {"image_digest": "nicht erfasst"},
              "uebernahmen": [{"fall": "x", "snapshot_sha256": None,
                               "zeichnung": {"schluesselklasse": "nicht ausgewiesen"}}],
              "abschluesse": []}
    was = [l["was"] for l in st.luecken(modell)]
    assert was == ["Image-Digest des Laufs", "A-M4-Snapshot der Uebernahme x",
                   "Schluesselklasse der A-M4-Zeichnung (x)", "Monatsabschluss"]
    voll = {"provenienz": {"image_digest": "sha256:abc"},
            "uebernahmen": [{"fall": "x", "snapshot_sha256": "ab" * 32,
                             "zeichnung": {"schluesselklasse": "simulation"}}],
            "abschluesse": [{"stichtag": "2026-02-01"}]}
    assert st.luecken(voll) == []


def test_ohne_uebernommenen_stand_gibt_es_keine_seite(tmp_path):
    ablage = _ablage(tmp_path / "leer")
    with pytest.raises(st.SeiteError, match="kein uebernommener Lauf"):
        st.stand_modell(ablage)
    assert st.main(["--stand", str(ablage.wurzel)]) == 2
    # Stand und Protokoll muessen zusammenpassen — sonst spricht die Seite
    # von einem anderen Stand als dem Nachweis.
    kopie = Ablage(tmp_path / "kopie")
    shutil.copytree(_ablage(tmp_path / "quelle").wurzel, kopie.wurzel)


def test_uebernahme_traegt_rolle_und_schluesselklasse_der_zeichnung(tmp_path):
    """Wie die Fall-Seite: Rolle und Entscheider aus dem Snapshot, die
    Schluesselklasse eines Altsnapshots (Schema 6) als "nicht ausgewiesen"."""
    import sys

    sys.path.insert(0, str(REPO_ROOT / "tests"))
    import test_betrieb_uebernahme as tu
    from rechner_pipeline.betrieb import uebernahme as ueb

    # Der Fall traegt einen strukturell gueltigen Schema-6-Snapshot (T22-06:
    # ein frei erfundener, wie ihn dieser Test frueher schrieb, wird
    # abgewiesen — siehe test_betrieb_uebernahme).
    fall = tu._fall(tmp_path)
    ziel = ueb.eingang_anlegen(tmp_path / "daten", fall, dt.date(2026, 1, 1))
    eingang = json.loads((ziel / "eingang.json").read_text("utf-8"))
    z = eingang["zeichnung"]
    assert z["rolle"] == "mensch" and z["entscheider"] == "Verantwortlicher Aktuar"
    assert z["schluesselklasse"] == "nicht ausgewiesen" and z["schema_version"] == 6
    assert z["schluessel_sha256"] == "cd" * 8 and z["signatur_verifiziert"] is False
    gelesen = ueb.lies_uebernahmen(tmp_path / "daten" / "uebernahme",
                                   __import__("rechner_pipeline.bestand.config", fromlist=["load_config"]).load_config(PLV))
    assert gelesen[0].zeichnung == z
    # Ohne Snapshot im Fall: alles "nicht ausgewiesen", nichts leer.
    ohne = ueb.zeichnung_aus_snapshot(fall, "cd" * 32)
    assert ohne["rolle"] == "nicht ausgewiesen" and "kein A-M4-Snapshot" in ohne["quelle"]
    # Auf der Seite erscheint die Zeichnung der Uebernahme:
    html = st.rendere_html({
        "stand": "2026-02-03", "gefuehrt_seit": "2026-01-01",
        "bestand": {"in_force": 1, "je_produkt": {"klv": 1}},
        "neugeschaeft": {"woche": {}, "woche_summe": 0, "seit_betriebsbeginn": 0},
        "buchungen": {"gesamt": 0, "je_ereignis": {}, "letzte": []},
        "abschluesse": [], "provenienz": {"pb1": "gruen", "manifest_sha256": "ed" * 32},
        "uebernahmen": [{"fall": "probe", "stichtag": "2026-01-01", "vertraege": 3,
                         "snapshot_sha256": eingang["snapshot_sha256"], "zeichnung": z}],
    })
    assert "<td>mensch</td><td>Verantwortlicher Aktuar</td><td>nicht ausgewiesen</td>" in html
    assert "Signatur hier nicht verifiziert" in html


def test_die_banderole_behauptet_nur_was_die_uebernahmen_ausweisen(gefuehrt):
    """Review T22-06: Die Banderole nannte unabhaengig von den Daten einen
    Simulationsschluessel. Ohne Uebernahme steht da keiner; mit einer
    simulierten Zeichnung steht er da; gemischt wird es benannt."""
    modell = st.stand_modell(gefuehrt)
    assert modell["uebernahmen"] == []
    assert "Simulationsschluessel" not in st.rendere_html(modell)
    modell["uebernahmen"] = [{"fall": "x", "stichtag": "2026-01-01", "vertraege": 1,
                              "snapshot_sha256": "ab" * 32,
                              "zeichnung": {"schluesselklasse": "simulation"}}]
    assert "Simulationsschluessel" in st.rendere_html(modell)
    modell["uebernahmen"].append({"fall": "y", "stichtag": "2026-01-01", "vertraege": 1,
                                  "snapshot_sha256": "cd" * 32,
                                  "zeichnung": {"schluesselklasse": "mensch"}})
    html = st.rendere_html(modell)
    assert "Simulationsschluessel" not in html and "mensch, simulation" in html


@pytest.mark.parametrize("was", ["journal", "manifest"])
def test_seite_und_paket_lehnen_einen_stand_ohne_passenden_nachweis_ab(gefuehrt, tmp_path, was):
    """T24-03: Eine Wache schuetzt nur den, der sie durchlaeuft.

    ``gefuehrter_tag`` prueft den Nachweisvertrag und lehnt ein veraendertes
    Tagesjournal ab. Seite und Stands-Paket lasen dieselben Bytes danach
    ohne jede Pruefung erneut: Der manipulierte Betrag stand in den
    Buchungen, waehrend die Provenienz daneben weiter den Journal-Hash der
    Protokollzeile nannte — die Seite widersprach sich selbst und merkte es
    nicht. Manipuliert wird hier ueber den GUELTIGEN Schreibpfad
    (``write_portfolio``), nicht durch ein kaputtes Byte: Der Fall, den es
    zu fangen gilt, ist der wohlgeformte.
    """
    from rechner_pipeline.bestand.manifest import MANIFEST_DATEI
    from rechner_pipeline.bestand.parquet_io import read_portfolio, write_portfolio
    from rechner_pipeline.models.bestand import TAGESJOURNAL_NAMES

    kopie = tmp_path / f"kopie-{was}"
    shutil.copytree(gefuehrt.wurzel, kopie, symlinks=True)
    ablage = Ablage(kopie)
    # Vorprobe: Die unveraenderte Kopie traegt ihren Nachweis — sonst
    # pruefte der Test die Kopiererei statt die Wache.
    assert st.stand_modell(ablage)["stand"]

    if was == "journal":
        journal = read_portfolio(ablage.tagesjournal_pfad, expected_columns=TAGESJOURNAL_NAMES)
        journal.loc[0, "betrag"] = 999999.0
        write_portfolio(journal, ablage.tagesjournal_pfad)
    else:
        pfad = ablage.stand / MANIFEST_DATEI
        manifest = json.loads(pfad.read_text(encoding="utf-8"))
        rolle = sorted(manifest["ausgaben"])[0]
        manifest["ausgaben"][rolle] = "ff" * 32
        pfad.write_text(json.dumps(manifest, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
                        encoding="utf-8")

    with pytest.raises(st.SeiteError, match="Nachweis"):
        st.stand_modell(ablage)
    with pytest.raises(st.SeiteError, match="Nachweis"):
        st.stands_paket(ablage, tmp_path / f"paket-{was}")


def test_das_paket_belegt_seine_buchungszahlen_mit_dem_journal(gefuehrt, tmp_path):
    """T24-04 Teil 1: Ein Beleg, der nur danebenliegt, belegt nichts.

    Schema 2 trug Protokoll und Manifest — damit waren die
    protokollgespeisten Bloecke von stand.json belegt, die
    journalgespeisten nicht: Geschaeftsentwicklung, buchungen.* und das
    Neugeschaeft der Woche standen als blosse Behauptung im Paket. Wer sie
    las, musste dem Feld glauben.

    Geprueft wird deshalb dreierlei: dass das Journal im Paket liegt, dass
    sein Hash zu seinen Bytes passt, und dass es GENAU das Journal ist, auf
    das der gruene Lauf sich festgelegt hat. Das dritte ist das
    eigentliche: ein beliebiges Journal neben einer beliebigen Zahl ergaebe
    ein Paket, das sich selbst bezeugt.
    """
    from rechner_pipeline.bestand.manifest import sha256_bytes
    from rechner_pipeline.bestand.parquet_io import read_portfolio
    from rechner_pipeline.models.bestand import TAGESJOURNAL_NAMES

    paket = st.stands_paket(gefuehrt, tmp_path / "paket")
    modell = json.loads((paket / st.PAKET_DATEI).read_text(encoding="utf-8"))
    assert modell["schema_version"] == st.PAKET_SCHEMA_VERSION

    beleg = paket / st.PAKET_JOURNAL
    assert beleg.is_file(), "das Tagesjournal fehlt im Paket"
    roh = beleg.read_bytes()
    assert modell["dateien"][st.PAKET_JOURNAL] == sha256_bytes(roh)

    gruen = [z for z in lies_protokoll(gefuehrt.protokoll_pfad) if z.get("uebernommen")][-1]
    assert gruen["tagesjournal"]["sha256"] == sha256_bytes(roh), (
        "das Paket traegt ein anderes Journal als der gruene Lauf")

    journal = read_portfolio(beleg, expected_columns=TAGESJOURNAL_NAMES)
    assert len(journal) == modell["buchungen"]["gesamt"]
    assert sorted(journal["ereignis"].unique()) == sorted(modell["buchungen"]["je_ereignis"])
