"""Das Paket ist an etwas gebunden, das nicht im Paket liegt (T24-04 b).

Ein Stands-Paket belegt sich bis hierher SELBST: Jede Kennzahl wird aus
den mitgelieferten Belegen nachgerechnet, die Protokollkette ist
ungebrochen. Was dabei prinzipiell nicht geprueft werden kann, ist die
LETZTE Zeile der Kette — sie hat keinen Nachfolger, der sie bindet, und
genau aus ihr leitet ``stand.json`` ab.

Wer beide zusammen umschreibt, bekommt ein Paket, das sich selbst
bestaetigt. Der Test unten baut genau dieses Paket. Ohne Anker kommt es
durch; mit Anker faellt es.

Entscheid des Maintainers 2026-09-16: externer Anker im Fall-Datenraum
plus Zeichnung des Exports. Angreifermodell ist ausdruecklich nicht der
boeswillige Mensch allein — der wahrscheinliche Fall ist ein Lauf oder
ein Agent, der etwas Falsches KONSISTENT hinschreibt.

Knoten: klv
"""

from __future__ import annotations

import datetime as dt
import hashlib
import json
import sys
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO_ROOT / "werkzeuge"))

import falldaten as fd  # noqa: E402

from rechner_pipeline.models import anker as ak  # noqa: E402
from rechner_pipeline.betrieb import seite as st  # noqa: E402
from tests.test_betrieb_seite import _ablage  # noqa: E402


@pytest.fixture(scope="module")
def paket_und_anker(tmp_path_factory):
    from rechner_pipeline.betrieb.tageslauf import tageslauf

    basis = tmp_path_factory.mktemp("anker")
    ablage = _ablage(basis / "plv")
    assert tageslauf(ablage, dt.date(2026, 2, 3))[0] == 0
    paket = st.stands_paket(ablage, basis / "paket",
                            anker_verzeichnis=basis / "anker")
    return paket, basis / "anker" / ak.ANKER_DATEI


def test_der_hash_der_ankerzeile_ist_der_der_protokollkette():
    """Zwei Module rechnen denselben Hash — hier steht, dass sie es
    gleich tun. Der Anker bindet eine PROTOKOLLZEILE; liefe seine
    Rechnung der der Kette davon, bezeugte er etwas anderes als das,
    was er zu bezeugen meint."""
    from rechner_pipeline.betrieb.tageslauf import _zeilen_hash

    for roh in ('{"a": 1}', "", "mit Umlaut: ae oe ue", '{"b": [1, 2]}'):
        assert ak.zeilen_hash(roh) == _zeilen_hash(roh)


def test_ein_unveraendertes_paket_geht_durch(paket_und_anker):
    paket, anker = paket_und_anker
    assert fd.betrieb(paket, anker)["vorhanden"]


def test_ohne_anker_wird_nichts_veroeffentlicht(paket_und_anker):
    paket, _anker = paket_und_anker
    with pytest.raises(fd.FalldatenFehler, match="kein Anker uebergeben"):
        fd.betrieb(paket, None)


def test_ein_in_sich_stimmiges_gefaelschtes_paket_faellt_am_anker(
    paket_und_anker, tmp_path
):
    """DER Fall, fuer den der Anker gebaut ist.

    Gefaelscht wird so, wie es ein Faelscher taete: die letzte
    Protokollzeile umschreiben (sie hat keinen Nachfolger, die Kette
    bleibt also heil), stand.json auf denselben Wert nachziehen und den
    Hash der Protokolldatei in ``dateien`` erneuern. Danach widerspricht
    sich das Paket an keiner Stelle mehr — jede Pruefung, die nur im
    Paket nachsieht, bestaetigt es.
    """
    import shutil

    paket, anker = paket_und_anker
    kopie = tmp_path / "gefaelscht"
    shutil.copytree(paket, kopie)

    protokoll = kopie / "protokoll.jsonl"
    zeilen = [z for z in protokoll.read_text("utf-8").splitlines() if z.strip()]
    letzte = json.loads(zeilen[-1])
    echt = int(letzte["bestand"]["in_force"])
    letzte["bestand"]["in_force"] = echt + 1000
    zeilen[-1] = json.dumps(letzte, ensure_ascii=False, sort_keys=True)
    protokoll.write_text("\n".join(zeilen) + "\n", encoding="utf-8")

    stand = json.loads((kopie / "stand.json").read_text("utf-8"))
    stand["bestand"]["in_force"] = echt + 1000
    stand["dateien"]["protokoll.jsonl"] = hashlib.sha256(
        protokoll.read_bytes()).hexdigest()
    (kopie / "stand.json").write_text(
        json.dumps(stand, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
        encoding="utf-8")

    # ZUERST die Positivkontrolle: Die Faelschung ist in sich stimmig.
    # Jede Pruefung, die nur IM Paket nachsieht, bestaetigt sie — ohne
    # diesen Nachweis faenge der Test vielleicht etwas ganz anderes, und
    # der Anker waere ueberfluessig.
    stand_neu = json.loads((kopie / "stand.json").read_text("utf-8"))
    fd._pruefe_stands_paket(kopie, stand_neu, stand_neu.get("provenienz") or {})

    # Und jetzt der Bezug nach aussen: Er kennt die echte Zeile.
    with pytest.raises(fd.FalldatenFehler, match="letzte Protokollzeile"):
        fd.betrieb(kopie, anker)


def test_ein_fremder_ankersatz_hilft_dem_faelscher_nicht(
    paket_und_anker, tmp_path
):
    """Geprueft wird gegen den Anker, den stand.json NENNT — nicht gegen
    irgendeinen passenden. Sonst genuegte ein beliebiger alter Satz
    derselben Ablage."""
    import shutil

    paket, anker = paket_und_anker
    kopie = tmp_path / "fremder-anker"
    shutil.copytree(paket, kopie)
    stand = json.loads((kopie / "stand.json").read_text("utf-8"))
    stand["anker"]["sha256"] = "f" * 64
    (kopie / "stand.json").write_text(
        json.dumps(stand, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
        encoding="utf-8")

    with pytest.raises(fd.FalldatenFehler, match="steht nicht in der Ankerdatei"):
        fd.betrieb(kopie, anker)


def test_die_ankerdatei_wird_nur_angefuegt(paket_und_anker, tmp_path):
    """Ein ersetzter Anker waere kein Anker. Die Reihe der Saetze ist die
    Geschichte der Auslieferungen."""
    paket, anker = paket_und_anker
    vorher = len(ak.lies_anker(anker))
    satz = ak.ankersatz(paket / "protokoll.jsonl", "2026-02-03", "a" * 64,
                        "b" * 64, erstellt="2026-02-03T00:00:00+00:00")
    ak.haenge_an(anker.parent, satz)
    nachher = ak.lies_anker(anker)
    assert len(nachher) == vorher + 1
    assert nachher[-1] == satz


# --- Die Auslieferung (Entscheid des Maintainers 2026-09-16) ------------
#
# Zwei Akte, die bisher einer waren: Der EXPORT wird vom Betriebsagenten
# gezeichnet — eine Aussage ueber Urheberschaft. Die AUSLIEFERUNG, bei
# der ein Stand nach aussen sichtbar wird, braucht zusaetzlich die
# menschliche Abnahme A-B1. Ein Agent kann sie nicht ersetzen.

import hmac  # noqa: E402

from tests.zeichnung_fixture import schluessel_anlegen, ordnung_schreiben  # noqa: E402


def _agentenordnung(tmp_path):
    """Eine Ordnung mit einem Betriebsagenten — gates-Liste LEER.

    Was ein Agent zeichnet, ist kein Gate (ADR-018, Nachtrag)."""
    schluessel = tmp_path / "agent.key"
    fp = schluessel_anlegen(schluessel, b"nur-fuer-tests-agent-betrieb!!!!")
    ordnung = ordnung_schreiben(tmp_path / "zeichnungsordnung.json", {
        "agent/betrieb": {"schluessel_sha256": fp,
                          "schluesselklasse": "agent", "gates": []},
    })
    return schluessel, ordnung


def test_der_export_zeichnet_den_ankersatz(paket_und_anker, tmp_path):
    """Die Rolle wird aus dem SCHLUESSEL bestimmt, nicht behauptet."""
    from rechner_pipeline.betrieb.tageslauf import Ablage

    paket, _anker = paket_und_anker
    schluessel, ordnung = _agentenordnung(tmp_path)
    ablage = Ablage(paket.parent / "plv")
    neu = st.stands_paket(ablage, tmp_path / "paket",
                          anker_verzeichnis=tmp_path / "anker",
                          schluessel=schluessel, zeichnungsordnung=ordnung)

    stand = json.loads((neu / "stand.json").read_text("utf-8"))
    z = stand["anker"]["zeichnung"]
    assert z["rolle"] == "agent/betrieb"
    assert z["schluesselklasse"] == "agent"
    # Das Verfahren steht hier ABSICHTLICH als Literal: Es ist ein
    # Vertrag mit jedem, der eine Ankerreihe liest. Seit T26-16 liegen
    # Rolle und Schluesselklasse unter der Signatur — v1 liess sie
    # daneben stehen und austauschbar.
    assert z["verfahren"] == "hmac-sha256-v2"
    # Und die Signatur haelt: gegen den Inhalt, nicht gegen sich selbst.
    satz = ak.lies_anker(tmp_path / "anker" / ak.ANKER_DATEI)[-1]
    ring = {z["schluessel_sha256"]: schluessel.read_bytes()}
    assert ak.pruefe_zeichnung(satz, ring) == []
    satz["stand"] = "1999-01-01"
    assert ak.pruefe_zeichnung(satz, ring) != []


def test_ein_schluessel_ohne_rolle_zeichnet_nicht(paket_und_anker, tmp_path):
    """Eine Zeichnung ohne Ordnung waere eine Rolle, die sich selbst
    vergibt."""
    from rechner_pipeline.betrieb.tageslauf import Ablage

    paket, _anker = paket_und_anker
    ablage = Ablage(paket.parent / "plv")
    fremd = tmp_path / "fremd.key"
    schluessel_anlegen(fremd, b"ein-schluessel-den-niemand-kennt!")
    _s, ordnung = _agentenordnung(tmp_path)

    with pytest.raises(st.SeiteError, match="gehoert zu keiner Rolle"):
        st.stands_paket(ablage, tmp_path / "p-fremd",
                        anker_verzeichnis=tmp_path / "anker-fremd",
                        schluessel=fremd, zeichnungsordnung=ordnung)
    with pytest.raises(st.SeiteError, match="verlangt --zeichnungsordnung"):
        st.stands_paket(ablage, tmp_path / "p-ohne",
                        anker_verzeichnis=tmp_path / "anker-ohne",
                        schluessel=fremd)


def test_eine_auslieferung_ohne_abnahme_wird_nicht_veroeffentlicht(
    paket_und_anker, tmp_path
):
    """Was nach aussen geht, zeichnet ein Mensch. Ein Paket, das sich als
    Auslieferung ausweist und keine angenommene A-B1 im Fall hat, kommt
    nicht auf die Seite — auch wenn der Agent es gezeichnet hat."""
    from rechner_pipeline.betrieb.tageslauf import Ablage

    paket, _anker = paket_und_anker
    schluessel, ordnung = _agentenordnung(tmp_path)
    ablage = Ablage(paket.parent / "plv")
    aus = st.stands_paket(ablage, tmp_path / "auslieferung",
                          anker_verzeichnis=tmp_path / "anker-aus",
                          art=ak.ART_AUSLIEFERUNG,
                          schluessel=schluessel, zeichnungsordnung=ordnung)
    ankerdatei = tmp_path / "anker-aus" / ak.ANKER_DATEI

    fall = tmp_path / "fall"
    (fall / "entscheide").mkdir(parents=True)
    with pytest.raises(fd.FalldatenFehler, match="A-B1"):
        fd.betrieb(aus, ankerdatei, fall)

    # Ohne Fall ist sie erst recht nicht auffindbar — und das sagt der Text.
    with pytest.raises(fd.FalldatenFehler, match="ohne Fall"):
        fd.betrieb(aus, ankerdatei, None)


def test_eine_momentaufnahme_braucht_keine_abnahme(paket_und_anker, tmp_path):
    """Positivkontrolle: Der gewoehnliche Export laeuft weiter durch —
    sonst waere die Regel ein Rundschlag."""
    paket, anker = paket_und_anker
    modell = fd.betrieb(paket, anker, tmp_path / "fall")
    assert modell["verankerung"]["art"] == "momentaufnahme"
    assert "abnahme" not in modell["verankerung"]
