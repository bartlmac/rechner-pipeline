"""Das Stands-Paket als Quelle der Falldarstellung (Fachkonzept Tagesbetrieb, 8.3).

Knoten: system/betrieb
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

import pytest

REPO = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO / "werkzeuge"))

import falldaten as fd  # noqa: E402
import fallbericht as fb  # noqa: E402


import datetime as dt

from rechner_pipeline.betrieb import seite as st
from rechner_pipeline.betrieb.tageslauf import EXIT_OK, tageslauf
from tests.test_betrieb_seite import _ablage


@pytest.fixture(scope="module")
def paket(tmp_path_factory) -> Path:
    """Ein ECHTES Stands-Paket aus einem gefuehrten Stand (Review T22-05):
    Vorher schrieb der Test ein komplett erfundenes stand.json ohne
    Belegdateien und erwartete Veroeffentlichung — genau die Luecke."""
    ablage = _ablage(tmp_path_factory.mktemp("plv"))
    assert tageslauf(ablage, dt.date(2026, 2, 3))[0] == EXIT_OK
    basis = tmp_path_factory.mktemp("paket")
    return st.stands_paket(ablage, basis / "paket",
                           anker_verzeichnis=basis / "anker")


def _erfunden(tmp_path: Path, pb1: str = "gruen") -> Path:
    """Das erfundene Paket von frueher — jetzt der Negativfall."""
    paket = tmp_path / "erfunden"
    paket.mkdir()
    stand = {
        # Schema der GELTENDEN Fassung (4 seit T24-04 Teil 2): Das Paket
        # soll an den Belegen scheitern, nicht schon an der Versionszahl —
        # sonst prueft der Test den Schema-Pin statt die Belegpflicht.
        "schema_version": 5, "stand": "2026-09-05", "gefuehrt_seit": "2026-01-01",
        "bestand": {"in_force": 2556, "je_produkt": {"klv": 1893, "bu": 663},
                    "uebernommen_in_force": 818, "policiert_beginn_folgt": 2},
        "neugeschaeft": {"seit_betriebsbeginn": 99, "woche": {}, "woche_summe": 0},
        "buchungen": {"gesamt": 1460, "je_ereignis": {}, "letzte": []},
        "abschluesse": [], "uebernahmen": [],
        "provenienz": {"manifest_sha256": "ed" * 32, "config_sha256": "d5" * 32,
                       "kern_version": "3.4.0", "pb1": pb1, "image_digest": "nicht erfasst",
                       "image_revision": "nicht erfasst", "image_tag": "nicht erfasst"},
        "dateien": {"index.html": "00" * 32, "protokoll.jsonl": "11" * 32,
                    "laufmanifest.json": "22" * 32},
    }
    (paket / "stand.json").write_text(json.dumps(stand), encoding="utf-8")
    return paket


def _mit_anker(paket):
    """``betrieb`` mit dem Anker, den das Paket NENNT.

    Der Anker liegt ausserhalb des Pakets und reist nicht mit — auch eine
    Kopie des Pakets wird gegen die eine Ankerdatei geprueft, die der
    Export geschrieben hat. Genau das ist seine Aufgabe."""
    import json as _json

    try:
        stand = _json.loads((paket / "stand.json").read_text("utf-8"))
        datei = (stand.get("anker") or {}).get("datei")
    except (OSError, ValueError, AttributeError):
        datei = None
    return fd.betrieb(paket, Path(datei) if datei else None)


def test_das_paket_wird_zum_abschnitt_der_darstellung(paket):
    b = _mit_anker(paket)
    assert b["vorhanden"] and b["stand"] == "2026-02-03"
    assert b["bestand"]["in_force"] > 0 and b["provenienz"]["pb1"] == "gruen"
    assert set(b["dateien"]) >= {"index.html", "protokoll.jsonl", "laufmanifest.json"}
    html = fb._betrieb({"betrieb": b})
    assert "Der lebende Bestand (Stand 2026-02-03)" in html
    assert "Wache P-B1 gruen" in html
    # Die Luecken des Stands wandern in die Darstellung (T22-05).
    assert any(l["was"] == "Image-Digest des Laufs" for l in b["luecken"])
    assert any(l["gruppe"] == "betrieb" and "Image-Digest" in l["was"]
               for l in fd.luecken({"betrieb": b}))
    # Ohne Paket kein Abschnitt und keine Luecke:
    assert fd.betrieb(None) == {"vorhanden": False}
    assert fb._betrieb({"betrieb": {"vorhanden": False}}) == ""
    assert not any(l["gruppe"] == "betrieb" for l in fd.luecken({"betrieb": {"vorhanden": False}}))


def test_ein_erfundenes_paket_wird_nicht_veroeffentlicht(tmp_path):
    """Nachweis des Reviews: stand.json ohne Belegdateien mit pb1 = "gruen"
    wurde veroeffentlicht. Mutationsprobe: die Existenzpruefung der
    Belegdateien in _pruefe_stands_paket entfernen -> rot (die Hash-Pruefung
    faengt test_ein_veraendertes_protokoll_im_paket_faellt_auf)."""
    with pytest.raises(fd.FalldatenFehler, match="Belegdatei"):
        _mit_anker(_erfunden(tmp_path))
    with pytest.raises(fd.FalldatenFehler, match="kein Stands-Paket"):
        _mit_anker(tmp_path)


def test_ein_roter_stand_wird_nicht_dargestellt(paket, tmp_path):
    """Veroeffentlicht wird nichts, was nicht durch P-B1 ging — auch wenn
    nur stand.json das behauptet und das Protokoll etwas anderes sagt."""
    import shutil

    kopie = tmp_path / "rot"
    shutil.copytree(paket, kopie)
    stand = json.loads((kopie / "stand.json").read_text(encoding="utf-8"))
    stand["provenienz"]["pb1"] = "rot"
    (kopie / "stand.json").write_text(json.dumps(stand), encoding="utf-8")
    with pytest.raises(fd.FalldatenFehler, match="nicht durch P-B1"):
        _mit_anker(kopie)


def test_ein_veraendertes_protokoll_im_paket_faellt_auf(paket, tmp_path):
    """Nachweis des Reviews: mittlere Zeile entfernt bzw. Betrag geaendert,
    der letzte Tag galt weiter. Hier: Zeile veraendert -> Belegdatei-Hash;
    Zeile veraendert UND Hash in stand.json nachgezogen -> Protokollkette."""
    import hashlib
    import shutil

    kopie = tmp_path / "manipuliert"
    shutil.copytree(paket, kopie)
    protokoll = kopie / "protokoll.jsonl"
    zeilen = protokoll.read_text(encoding="utf-8").splitlines()
    zeile = json.loads(zeilen[-1])
    zeile["bestand"]["in_force"] = 999999
    zeilen[-1] = json.dumps(zeile, ensure_ascii=False, sort_keys=True)
    protokoll.write_text("\n".join(zeilen) + "\n", encoding="utf-8")
    with pytest.raises(fd.FalldatenFehler, match="Belegdatei 'protokoll.jsonl'"):
        _mit_anker(kopie)
    # Wer auch den Hash in stand.json nachzieht, scheitert an der Kette,
    # sobald er eine mittlere Zeile antastet:
    stand = json.loads((kopie / "stand.json").read_text(encoding="utf-8"))
    if len(zeilen) >= 2:
        del zeilen[0]
        protokoll.write_text("\n".join(zeilen) + "\n", encoding="utf-8")
        stand["dateien"]["protokoll.jsonl"] = hashlib.sha256(protokoll.read_bytes()).hexdigest()
        (kopie / "stand.json").write_text(json.dumps(stand), encoding="utf-8")
        with pytest.raises(fd.FalldatenFehler, match="Protokollkette|passen nicht"):
            _mit_anker(kopie)


def test_die_kette_reicht_das_paket_durch(tmp_path, monkeypatch):
    import auftritt

    aufrufe = []
    monkeypatch.setattr(auftritt, "_schritt", lambda kommando, erlaubt=(0,): aufrufe.append(kommando) or 0)
    auftritt.main(["--fall", "f", "--name", "n", "--stands-paket", str(tmp_path / "paket"),
                   "--vorschau", ""])
    assert "--stands-paket" in aufrufe[0] and str(tmp_path / "paket") in aufrufe[0]


@pytest.mark.parametrize("feld", ["gesamt", "je_ereignis"])
def test_eine_buchungszahl_ohne_deckung_im_journal_faellt_auf(paket, tmp_path, feld):
    """T24-04 Teil 1, Konsumentenseite: Die Zahl muss aus dem Beleg folgen.

    Bis Paketschema 2 lagen Protokoll und Manifest im Paket — damit waren
    die protokollgespeisten Bloecke von stand.json gedeckt. ``buchungen.*``
    kommt aber aus dem Tagesjournal, das nicht mitkam: Die Zahl stand da
    und war zu glauben. Ein Paket, dessen stand.json die Buchungen frei
    behauptet, kam auf die Seite.

    Manipuliert wird hier NUR stand.json, nicht das Journal — das Journal
    haengt ueber seinen Hash an der Protokollkette und ist damit schon
    gedeckt. Offen war die Luecke zwischen einem echten Beleg und einer
    Zahl, die nicht zu ihm passt.
    """
    import shutil

    kopie = tmp_path / f"kopie-{feld}"
    shutil.copytree(paket, kopie)
    stand = json.loads((kopie / "stand.json").read_text(encoding="utf-8"))
    assert _mit_anker(kopie)["vorhanden"], "die unveraenderte Kopie muss durchgehen"
    if feld == "gesamt":
        stand["buchungen"]["gesamt"] = int(stand["buchungen"]["gesamt"]) + 1
    else:
        stand["buchungen"]["je_ereignis"] = {"ZUG": 999999}
    (kopie / "stand.json").write_text(json.dumps(stand, ensure_ascii=False), encoding="utf-8")
    with pytest.raises(fd.FalldatenFehler, match="Tagesjournal"):
        _mit_anker(kopie)


@pytest.mark.parametrize("pfad, wert", [
    (("bestand", "in_force"), 1067),
    (("neugeschaeft", "seit_betriebsbeginn"), 4711),
    (("verankerung", "registriert"), 99),
    (("provenienz", "kern_version"), "9.9.9"),
    (("provenienz", "image_revision"), "deadbeef"),
    (("provenienz", "config_sha256"), "ab" * 32),
])
def test_ein_feld_ohne_deckung_im_protokoll_faellt_auf(paket, tmp_path, pfad, wert):
    """T24-04, die protokollgespeiste Haelfte: Geprueft waren Stand, Urteil,
    Manifest- und Journal-Hash. Alles andere aus der Protokollzeile stand
    ungeprueft daneben — Bestandszahlen, Uebernahmen, Verankerung,
    Abschluesse, Neugeschaeft und die uebrigen Provenienzfelder.

    Der Reviewer hat genau das nachgestellt: in_force von 68 auf 1067
    gesetzt, eine einzige Datei angefasst, Paket ANGENOMMEN, Konsument
    liefert 1067. Der Beleg lag daneben und wurde nicht gelesen.

    Geaendert wird auch hier NUR stand.json: Das Protokoll haengt an seiner
    Kette, es zu faelschen ist ein anderer Angriff (Teil 2, Block C).
    """
    import shutil

    kopie = tmp_path / ("kopie-" + "-".join(pfad))
    shutil.copytree(paket, kopie)
    assert _mit_anker(kopie)["vorhanden"], "die unveraenderte Kopie muss durchgehen"
    stand = json.loads((kopie / "stand.json").read_text(encoding="utf-8"))
    gruppe, feld = pfad
    assert stand[gruppe][feld] != wert, "die Mutation muss etwas veraendern"
    stand[gruppe][feld] = wert
    (kopie / "stand.json").write_text(json.dumps(stand, ensure_ascii=False), encoding="utf-8")
    with pytest.raises(fd.FalldatenFehler, match="Protokoll"):
        _mit_anker(kopie)


def test_ein_verschwiegener_abschluss_faellt_auf(paket, tmp_path):
    """Dieselbe Klasse an der Liste statt am Einzelwert: Ein Paket, das einen
    Monatsabschluss unterschlaegt, widerspricht seinem Protokoll."""
    import shutil

    kopie = tmp_path / "kopie-abschluesse"
    shutil.copytree(paket, kopie)
    stand = json.loads((kopie / "stand.json").read_text(encoding="utf-8"))
    assert stand["abschluesse"], "die Testwelt hat keinen Abschluss — nichts zu unterschlagen"
    stand["abschluesse"] = stand["abschluesse"][:-1]
    (kopie / "stand.json").write_text(json.dumps(stand, ensure_ascii=False), encoding="utf-8")
    with pytest.raises(fd.FalldatenFehler, match="abschluesse"):
        _mit_anker(kopie)


#: Die Felder, die der Konsument bisher UNGEPRUEFT weitergereicht hat —
#: bei unveraendertem Journal, unveraendertem Protokoll und korrekt
#: externem, unveraendertem Anker (Befund T26-09).
WEITERGEREICHTE_FELDER = [
    ("woche_summe", ("neugeschaeft", "woche_summe"), 1_000_000),
    ("woche_je_tag", ("neugeschaeft", "woche"), {"2026-02-03": 1_000_000}),
    ("luecken_geleert", ("luecken",), []),
]


@pytest.mark.parametrize("was,pfad,wert", WEITERGEREICHTE_FELDER,
                         ids=[w for w, _, _ in WEITERGEREICHTE_FELDER])
def test_eine_weitergereichte_zahl_wird_abgeleitet_statt_geglaubt(
    paket, tmp_path, was, pfad, wert
):
    """Befund T26-09: Der Anker war korrekt extern und unveraendert, das
    Journal unveraendert, das Protokoll unveraendert — und trotzdem ging
    ``woche_summe = 1.000.000`` durch, und der Lueckenblock liess sich
    leeren.

    Der oeffentliche Fallbericht baut seinen sichtbaren Lueckenblock aus
    genau dieser Funktion: Ein geleerter Block verschweigt den
    Image-Digest-Vorbehalt, den der Leser sehen soll.

    Abgeleitet wird jetzt mit DERSELBEN Funktion wie beim Erzeuger —
    ``neugeschaeft_der_woche`` und ``luecken``. Zwei Ableitungen waeren
    zwei Regeln, die auseinanderlaufen.
    """
    import shutil

    kopie = tmp_path / ("kopie-" + was)
    shutil.copytree(paket, kopie)
    assert _mit_anker(kopie)["vorhanden"], "die unveraenderte Kopie muss durchgehen"
    stand = json.loads((kopie / "stand.json").read_text(encoding="utf-8"))
    ziel = stand
    for schluessel in pfad[:-1]:
        ziel = ziel[schluessel]
    assert ziel[pfad[-1]] != wert, "die Mutation muss etwas veraendern"
    ziel[pfad[-1]] = wert
    (kopie / "stand.json").write_text(json.dumps(stand, ensure_ascii=False),
                                      encoding="utf-8")
    with pytest.raises(fd.FalldatenFehler):
        _mit_anker(kopie)
