"""Der Monatsbericht zeichnet eine Reihe ueber die Naht der
Bewertungskonvention nie still (Befund merge-session/pipeline-dev,
08.10.2026).

main fuehrt die Konvention eines Abschlusses in ``bewertungskonvention``
und sagt sie an EINER Stelle (``models.bestand.abschluss_konvention`` ueber
``bestand.abschluss.lies_abschluss``). Der Tageslauf las die Abschluesse des
Monatsberichts mit ``lies_abschluss(pfad)[0]`` und verwarf damit genau das
Urteil, das jeder Leser beachten muss; die Ratsche sicherte den Aufruf,
nicht die Verwendung. Hier wird beides geprueft: dass der Renderer die Naht
ausweist (gemischt), dass er es nur dann tut (homogen; ein leerer
Abschluss ist keine Naht), und dass die Aufrufstelle das Urteil des Lesers
weiterreicht.

Knoten: system/betrieb
"""
from __future__ import annotations

import datetime as dt
from pathlib import Path
from types import SimpleNamespace

import pandas as pd

from rechner_pipeline.bestand import monatsbericht as mb
from rechner_pipeline.betrieb import tageslauf as tl
from rechner_pipeline.betrieb.tageslauf import Ablage
from rechner_pipeline.models.bestand import (
    ABSCHLUSS_NAMES,
    ABSCHLUSS_NAMES_VOR_UMSTELLUNG,
    KONVENTION_JAHRESZEILE,
    KONVENTION_MONATSGENAU,
)
from tests.test_bestand_monatsbericht import STICHTAG, _abschluss, _journal, _text

MARKEN = ("Konventionswechsel", "in zwei Konventionen", "Konvention gewechselt")


def _bericht(konventionen):
    raster = mb.monatsraster(STICHTAG)
    abschluesse = {tag: _abschluss(tag, range(1, 11)) for tag in raster}
    return mb.render_html(abschluesse, _journal([]), STICHTAG,
                          konventionen={t: konventionen(i) for i, t in enumerate(raster)})


def test_eine_reihe_ueber_die_naht_wird_ausgewiesen():
    """Die ersten sechs Abschluesse vor der Umstellung, danach monatsgenau:
    Trennlinie, Satz, und keine Veraenderung des Deckungskapitals gegen den
    Vorjahresmonat (andere Konvention); gegen den Vormonat (dieselbe) schon."""
    html = _bericht(lambda i: KONVENTION_JAHRESZEILE if i < 6 else KONVENTION_MONATSGENAU)
    text = _text(html)
    assert "Konventionswechsel (gestrichelt)" in html
    assert "in zwei Konventionen (jahreszeile, monatsgenau)" in text
    zeile = next(z for z in html.split("<tr>") if z.startswith("<td>Σ Deckungskapital<"))
    zellen = [c.split("</td>")[0] for c in zeile.split("<td class='num'>")[1:]]
    assert zellen[2] != "Konvention gewechselt"          # gegen den Vormonat: vergleichbar
    assert zellen[4] == "Konvention gewechselt"          # gegen den Vorjahresmonat: nicht


def test_eine_homogene_reihe_traegt_keine_naht():
    for konvention in (KONVENTION_MONATSGENAU, KONVENTION_JAHRESZEILE):
        html = _bericht(lambda i: konvention)
        assert not any(m in html for m in MARKEN), konvention
        # Ohne Naht bleibt der Bericht, wie er vor der Naht-Pruefung war:
        # keine leere Zeile an der Stelle des Hinweises (pipeline-dev,
        # Nachfahren von Fall 3 am 08.10.2026: sonst unterscheiden sich
        # alle Monatsberichte von den gebundenen um genau diese Zeile).
        assert '\n\n<p class="hinweis">Alle Zahlen' not in html, konvention


def test_ein_leerer_abschluss_in_der_reihe_ist_keine_naht():
    """Ein Abschluss ohne Zeilen traegt keine Konvention (None) — er darf
    weder als Naht gelten noch den Vergleich ueber ihn hinweg verhindern."""
    html = _bericht(lambda i: None if i == 5 else KONVENTION_MONATSGENAU)
    assert not any(m in html for m in MARKEN)
    assert mb.nahtstellen([{"konvention": "monatsgenau"}, {"konvention": None},
                           {"konvention": "monatsgenau"}]) == []
    assert mb.nahtstellen([{"konvention": "jahreszeile"}, {"konvention": None},
                           {"konvention": "monatsgenau"}]) == [2]


def _schreibe(pfad: Path, spalten, zeilen: int, konvention=None) -> None:
    """Ein Abschluss in genau der Gestalt, die abschluss_konvention kennt."""
    df = pd.DataFrame({c: [0] * zeilen for c in spalten})
    if "bewertungskonvention" in spalten:
        df["bewertungskonvention"] = [konvention] * zeilen
    pfad.parent.mkdir(parents=True, exist_ok=True)
    df.to_parquet(pfad)


def test_die_aufrufstelle_reicht_das_urteil_des_lesers_weiter(tmp_path, monkeypatch):
    """_monatsbericht liest jeden Abschluss mit lies_abschluss und gibt dessen
    Konvention an den Renderer — vor der Umstellung, monatsgenau, leer.
    Mutationsprobe: in _monatsbericht wieder ``lies_abschluss(pfad)[0]``
    ohne Konventionen -> rot."""
    ablage = Ablage(tmp_path / "plv")
    raster = mb.monatsraster(STICHTAG)
    for i, tag in enumerate(raster):
        pfad = ablage.abschluesse / f"abschluss_{tag.isoformat()}.parquet"
        if i < 4:
            _schreibe(pfad, ABSCHLUSS_NAMES_VOR_UMSTELLUNG, 3)
        elif i == 6:
            _schreibe(pfad, ABSCHLUSS_NAMES, 0, KONVENTION_MONATSGENAU)
        else:
            _schreibe(pfad, ABSCHLUSS_NAMES, 3, KONVENTION_MONATSGENAU)
    gefangen = {}

    def renderer(abschluesse, journal, stichtag, **kwargs):
        gefangen.update(kwargs, tage=sorted(abschluesse))
        return "<html></html>"

    monkeypatch.setattr(tl, "monatsbericht_html", renderer)
    config = SimpleNamespace(tagesbetrieb=SimpleNamespace(berichtshinweis=""))
    tl._monatsbericht(ablage, None, config, STICHTAG, STICHTAG,
                      tmp_path / "berichte" / "bestandsbericht.html", "00" * 32)
    erwartet = {tag: (KONVENTION_JAHRESZEILE if i < 4 else None if i == 6
                      else KONVENTION_MONATSGENAU) for i, tag in enumerate(raster)}
    assert gefangen["tage"] == raster
    assert gefangen["konventionen"] == erwartet
