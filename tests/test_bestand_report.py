"""Bestandsbericht: Kennzahlen-Korrektheit, Determinismus, CLI."""

from __future__ import annotations

import datetime as dt
from pathlib import Path

import pytest

from rechner_pipeline.bestand import report
from rechner_pipeline.bestand.config import load_config
from rechner_pipeline.bestand.generator import generate
from rechner_pipeline.bestand.kennzahlen import (
    generationsnamen,
    jahresraster,
    stichtags_kennzahlen,
    verlauf,
)
from rechner_pipeline.bestand.parquet_io import write_portfolio
from rechner_pipeline.bestand.zeitscheibe import zeitscheibe
from rechner_pipeline.toolbox import bestand_report as cli

REPO_ROOT = Path(__file__).resolve().parents[1]
EXAMPLE = REPO_ROOT / "examples" / "bestand_klv.toml"


@pytest.fixture(scope="module")
def config():
    return load_config(EXAMPLE)


@pytest.fixture(scope="module")
def portfolio(config):
    return generate(config)


@pytest.fixture(scope="module")
def fortschreibung(portfolio, config):
    from rechner_pipeline.bestand.ereignisse import fortschreiben

    return fortschreiben(portfolio, config, dt.date(2035, 1, 1))


@pytest.fixture(scope="module")
def gemischter_bestand(config):
    """Ein Bestand mit beiden Versicherungsarten (KLV und BU)."""
    import copy

    from rechner_pipeline.bestand.ereignisse import fortschreiben

    bu = load_config(REPO_ROOT / "examples" / "bestand_bu.toml")
    gemischt = copy.deepcopy(config)
    gemischt.generationen = [config.generationen[-1], bu.generationen[0]]
    gemischt.annahmen = bu.annahmen
    df = generate(gemischt)
    bis = dt.date(2040, 1, 1)
    return df, gemischt, fortschreiben(df, gemischt, bis), bis


# --------------------------------------------------------------------------- #
# Kennzahlen
# --------------------------------------------------------------------------- #


def test_jahresraster_spans_contract_period(portfolio):
    raster = jahresraster(portfolio)
    assert raster[0].year == int(portfolio["insurance_start"].dt.year.min())
    assert raster[-1].year == int(portfolio["insurance_end"].dt.year.max())
    assert all(d.month == 1 and d.day == 1 for d in raster)


def test_stichtags_kennzahlen_match_slice(portfolio):
    stichtag = dt.date(2010, 1, 1)
    scheibe = zeitscheibe(portfolio, stichtag)
    kz = stichtags_kennzahlen(scheibe, stichtag)
    assert kz["vertraege"] == len(scheibe)
    assert kz["summe_vs"] == pytest.approx(float(scheibe["sum_insured"].sum()))
    assert sum(kz["generationen"].values()) == len(scheibe)


def test_stichtags_kennzahlen_empty_slice_is_zero(portfolio):
    stichtag = dt.date(1970, 1, 1)
    kz = stichtags_kennzahlen(zeitscheibe(portfolio, stichtag), stichtag)
    assert kz["vertraege"] == 0 and kz["summe_vs"] == 0.0
    assert kz["generationen"] == {}


def test_verlauf_covers_all_stichtage(portfolio):
    stichtage = [dt.date(2000, 1, 1), dt.date(2010, 1, 1), dt.date(2020, 1, 1)]
    reihe = verlauf(portfolio, stichtage)
    assert [r["stichtag"] for r in reihe] == [s.isoformat() for s in stichtage]
    assert all(r["vertraege"] >= 0 for r in reihe)


# --------------------------------------------------------------------------- #
# Rendering
# --------------------------------------------------------------------------- #


@pytest.fixture(scope="module")
def html(portfolio):
    stichtage = [dt.date(j, 1, 1) for j in range(2000, 2021, 5)]
    return report.render_html(portfolio, stichtage=stichtage, quelle_hash="ab" * 32)


def test_render_is_deterministic(portfolio):
    stichtage = [dt.date(2005, 1, 1), dt.date(2012, 1, 1)]
    a = report.render_html(portfolio, stichtage=stichtage)
    b = report.render_html(portfolio, stichtage=stichtage)
    assert a == b  # byte-identisch — Golden-Master-faehig


def test_html_is_self_contained_with_svg(html, portfolio):
    assert html.startswith("<!doctype html>")
    assert html.count("<svg") >= 6  # Verlauf x2, Struktur x3, Scatter
    assert "http://" not in html.split("xmlns")[0]  # keine externen Ressourcen im Kopf
    for gen in generationsnamen(portfolio):
        assert gen in html
    assert "Kennzahlen je Stichtag" in html
    assert "abababab" in html  # gekuerzter Quelle-Hash


def test_html_has_no_meta_commentary(html):
    lower = html.lower()
    for banned in ("ehrlich", "honest"):
        assert banned not in lower


# --------------------------------------------------------------------------- #
# Ereignis-/Abgangs-Sichten
# --------------------------------------------------------------------------- #


def test_ereignis_kennzahlen_summen_und_jahresreihe(fortschreibung):
    from rechner_pipeline.bestand.kennzahlen import (
        EREIGNIS_REIHENFOLGE,
        ereignis_summen,
        ereignisse_je_jahr,
    )

    _, ledger, *_ = fortschreibung
    summen = ereignis_summen(ledger)
    assert [s["ereignis"] for s in summen] == [
        c for c in EREIGNIS_REIHENFOLGE if (ledger["ereignis"] == c).any()
    ]
    for s in summen:
        rows = ledger[ledger["ereignis"] == s["ereignis"]]
        assert s["anzahl"] == len(rows)
        assert s["summe_betrag"] == pytest.approx(float(rows["betrag"].sum()))
    reihe = ereignisse_je_jahr(ledger)
    jahre = [r["jahr"] for r in reihe]
    assert jahre == list(range(jahre[0], jahre[-1] + 1))  # lueckenlos
    assert sum(sum(r[c] for c in EREIGNIS_REIHENFOLGE) for r in reihe) == len(ledger)


def test_status_verlauf_zaehlt_pol_und_pex(portfolio, fortschreibung):
    from rechner_pipeline.bestand.ereignisse import bestand_mit_historie
    from rechner_pipeline.bestand.kennzahlen import status_verlauf
    from rechner_pipeline.bestand.zeitscheibe import zeitscheibe

    historie, _, *_ = fortschreibung
    sicht = bestand_mit_historie(portfolio, historie)
    stichtag = dt.date(2020, 1, 1)
    reihe = status_verlauf(sicht, [stichtag])
    scheibe = zeitscheibe(sicht, stichtag)
    assert reihe[0]["POL"] + reihe[0]["PEX"] == len(scheibe)
    assert reihe[0]["PEX"] > 0  # Beispielraten erzeugen Beitragsfreistellungen


def test_render_mit_historie_zeigt_abgangssichten(portfolio, fortschreibung):
    historie, ledger, scheiben, *_ = fortschreibung
    stichtage = [dt.date(j, 1, 1) for j in range(2005, 2031, 5)]
    ohne = report.render_html(portfolio, stichtage=stichtage)
    mit = report.render_html(
        portfolio, stichtage=stichtage, historie=historie, ledger=ledger,
        scheiben=scheiben, bis=dt.date(2035, 1, 1),
    )
    assert "Geschäftsvorfälle" in mit
    assert "Beitragsfreistellung (PEX)" in mit
    assert "Storno (STO)" in mit
    assert "abgangsbereinigt" in mit
    assert "Geschäftsvorfälle" not in ohne  # Default unverändert
    # Zusaetzliche Grafiken: Status- und Ereignisverlauf plus je eine je
    # Traeger-Bestand der Nachweisung (beitragspflichtig, beitragsfrei).
    assert mit.count("<svg") == ohne.count("<svg") + 4
    # Bestandsbewegung nur mit Horizont; Identitaet auf gesunden Daten ok:
    assert "Bestandsbewegung: Kapitalversicherung" in mit
    assert "Beitragspflichtiger Bestand" in mit and "Beitragsfreier Bestand" in mit
    assert "WARNUNG" not in mit
    ohne_bis = report.render_html(
        portfolio, stichtage=stichtage, historie=historie, ledger=ledger,
        scheiben=scheiben,
    )
    assert "Bestandsbewegung" not in ohne_bis
    # Determinismus auch mit Historie:
    nochmal = report.render_html(
        portfolio, stichtage=stichtage, historie=historie, ledger=ledger,
        scheiben=scheiben, bis=dt.date(2035, 1, 1),
    )
    assert mit == nochmal


def test_render_historie_ohne_ledger_ist_fehler(portfolio, fortschreibung):
    historie, ledger, *_ = fortschreibung
    with pytest.raises(ValueError, match="gehoeren zusammen"):
        report.render_html(portfolio, historie=historie)
    with pytest.raises(ValueError, match="gehoeren zusammen"):
        report.render_html(portfolio, ledger=ledger)


def test_render_mit_config_zeigt_aktuarielle_kennzahlen(portfolio, config, fortschreibung):
    historie, ledger, scheiben, *_ = fortschreibung
    stichtage = [dt.date(j, 1, 1) for j in range(2010, 2031, 10)]
    mit = report.render_html(
        portfolio, stichtage=stichtage, historie=historie, ledger=ledger,
        config=config, scheiben=scheiben,
    )
    assert "Aktuarielle Kennzahlen je Stichtag" in mit
    assert "Deckungskapital" in mit and "Rückkaufswert" in mit
    ohne = report.render_html(
        portfolio, stichtage=stichtage, historie=historie, ledger=ledger,
        scheiben=scheiben,
    )
    assert "Aktuarielle Kennzahlen" not in ohne
    # Auch ohne Historie (reiner Basisbestand) rendert die Sektion:
    basis = report.render_html(portfolio, stichtage=stichtage, config=config)
    assert "Aktuarielle Kennzahlen je Stichtag" in basis
    # Determinismus:
    nochmal = report.render_html(
        portfolio, stichtage=stichtage, historie=historie, ledger=ledger,
        config=config, scheiben=scheiben,
    )
    assert mit == nochmal


def test_render_erh_ledger_ohne_scheiben_ist_fehler(portfolio, config, fortschreibung):
    """Review-Fix: ERH im Ledger + aktuarielle Kennzahlen ohne Scheiben
    waeren still zu niedrig — fail-fast statt widerspruechlicher Bericht."""
    historie, ledger, scheiben, *_ = fortschreibung
    assert (ledger["ereignis"] == "ERH").any()
    with pytest.raises(ValueError, match="ERH"):
        report.render_html(
            portfolio, historie=historie, ledger=ledger, config=config
        )


def test_render_ohne_ereignisse_im_horizont(portfolio, config):
    from rechner_pipeline.bestand.ereignisse import fortschreiben

    frueh = portfolio["insurance_start"].min().date()
    historie, ledger, *_ = fortschreiben(portfolio, config, frueh)
    assert len(ledger) == 0
    html = report.render_html(
        portfolio,
        stichtage=[dt.date(2010, 1, 1)],
        historie=historie,
        ledger=ledger,
    )
    assert "Keine Ereignisse im Berichtszeitraum" in html


# --------------------------------------------------------------------------- #
# CLI
# --------------------------------------------------------------------------- #


def test_cli_writes_report(portfolio, tmp_path):
    parquet = write_portfolio(portfolio, tmp_path / "b.parquet")
    out = tmp_path / "bericht.html"
    code = cli.main(
        ["--portfolio", str(parquet), "--out", str(out),
         "--stichtage", "2005-01-01,2012-01-01", "--titel", "KLV-Testbestand"]
    )
    assert code == 0
    text = out.read_text(encoding="utf-8")
    assert "KLV-Testbestand" in text and "<svg" in text


def test_cli_missing_portfolio_exits_2(tmp_path):
    assert cli.main(["--portfolio", str(tmp_path / "fehlt.parquet")]) == 2


def test_cli_bad_stichtag_exits_2(portfolio, tmp_path):
    parquet = write_portfolio(portfolio, tmp_path / "b.parquet")
    assert cli.main(["--portfolio", str(parquet), "--stichtage", "kein-datum"]) == 2


def test_cli_mit_historie_und_ledger(portfolio, fortschreibung, tmp_path):
    historie, ledger, scheiben, *_ = fortschreibung
    parquet = write_portfolio(portfolio, tmp_path / "b.parquet")
    h = write_portfolio(historie, tmp_path / "h.parquet")
    l = write_portfolio(ledger, tmp_path / "l.parquet")
    s = write_portfolio(scheiben, tmp_path / "s.parquet")
    out = tmp_path / "bericht.html"
    code = cli.main(
        ["--portfolio", str(parquet), "--out", str(out),
         "--historie", str(h), "--ledger", str(l), "--scheiben", str(s),
         "--config", str(EXAMPLE), "--bis", "2035-01-01",
         "--stichtage", "2010-01-01,2020-01-01,2030-01-01"]
    )
    assert code == 0
    text = out.read_text(encoding="utf-8")
    assert "Geschäftsvorfälle" in text
    assert "Aktuarielle Kennzahlen je Stichtag" in text
    assert "Dynamische Erhöhung (ERH)" in text
    assert "Bestandsbewegung" in text
    # Nur eines von beiden ist ein Fehler:
    assert cli.main(
        ["--portfolio", str(parquet), "--historie", str(h)]
    ) == 2
    # Scheiben ohne Historie ist ein Fehler:
    assert cli.main(
        ["--portfolio", str(parquet), "--scheiben", str(s)]
    ) == 2
    # ERH im Ledger ohne Scheiben: Engine-Guard, sauber als Exit 2:
    assert cli.main(
        ["--portfolio", str(parquet), "--historie", str(h), "--ledger", str(l)]
    ) == 2
    # Scheiben ohne Config sind gueltig (Bewegungs-Summen brauchen sie):
    ohne_config = tmp_path / "ohne_config.html"
    assert cli.main(
        ["--portfolio", str(parquet), "--historie", str(h), "--ledger", str(l),
         "--scheiben", str(s), "--bis", "2035-01-01", "--out", str(ohne_config)]
    ) == 0
    assert "Bestandsbewegung" in ohne_config.read_text(encoding="utf-8")
    # --bis nur mit --historie/--ledger; ungueltiges Datum ist ein Fehler:
    assert cli.main(
        ["--portfolio", str(parquet), "--bis", "2035-01-01"]
    ) == 2
    assert cli.main(
        ["--portfolio", str(parquet), "--historie", str(h), "--ledger", str(l),
         "--bis", "kein-datum"]
    ) == 2
    # Fehlende Config-Datei ist ein Fehler:
    assert cli.main(
        ["--portfolio", str(parquet), "--config", str(tmp_path / "fehlt.toml")]
    ) == 2


def test_svg_ids_sind_inhaltsbasiert_und_stabil():
    """Regression: matplotlib leitet Clip-Pfad- und Marker-Ids teils aus
    Objektadressen ab (id(obj)) — zwei Renderings derselben Grafik waeren
    dann nicht byte-identisch. Der Bericht normalisiert sie inhaltsbasiert."""
    import re

    roh = '<path clip-path="url(#pd425d0d61f)"/><use xlink:href="#m1a2b3c4d5e"/>'
    stabil = report._stabile_ids(roh)
    assert stabil == report._stabile_ids(roh)
    assert "pd425d0d61f" not in stabil and "m1a2b3c4d5e" not in stabil
    # Praefix bleibt erhalten (Clip-Pfad p..., Marker m...), Ids eindeutig:
    ids = re.findall(r"#([mp][0-9a-f]+)", stabil)
    assert len(ids) == len(set(ids)) == 2
    assert ids[0].startswith("p") and ids[1].startswith("m")
    # Anderer Inhalt -> anderes Praefix (keine Kollision zwischen Grafiken):
    anders = report._stabile_ids('<path clip-path="url(#pd425d0d61f)"/>')
    assert anders != stabil


# --------------------------------------------------------------------------- #
# Vereinheitlichte Nachweisung: Historie und Prognose
# --------------------------------------------------------------------------- #


def test_stichtag_teilt_die_nachweisung_in_historie_und_prognose(
    portfolio, config, fortschreibung
):
    """Ein Bericht, zwei Perioden: der Referenzstichtag trennt den
    beobachteten Bestandsaufbau von der Projektion."""
    historie, ledger, scheiben, *_ = fortschreibung
    stichtag = dt.date(2026, 1, 1)
    kw = dict(historie=historie, ledger=ledger, scheiben=scheiben,
              config=config, bis=dt.date(2035, 1, 1),
              stichtage=[dt.date(2020, 1, 1), dt.date(2030, 1, 1)])

    mit = report.render_html(portfolio, stichtag=stichtag, **kw)
    ohne = report.render_html(portfolio, **kw)

    assert f"Stichtag {stichtag.isoformat()} — ab hier Prognose" in mit
    assert "Referenzstichtag" in mit
    assert "ab hier Prognose" not in ohne
    # Genau EINE Trennstelle je Bewegungstabelle (zwei Traeger-Bestaende
    # mal Stueck und Summe), nicht je Zeile:
    assert mit.count("ab hier Prognose") == 4
    # Determinismus bleibt:
    assert mit == report.render_html(portfolio, stichtag=stichtag, **kw)


def test_beide_produkte_teilen_dieselbe_nachweisungs_struktur(config):
    """KLV und BU werden gleich aufgebaut ausgewiesen — je Traeger-Bestand
    eine Grafik und zwei Bewegungstabellen (Stueck, Bezugsgroesse)."""
    import copy

    from rechner_pipeline.bestand.config import load_config
    from rechner_pipeline.bestand.ereignisse import fortschreiben

    bu = load_config(REPO_ROOT / "examples" / "bestand_bu.toml")
    gemischt = copy.deepcopy(config)
    gemischt.generationen = [config.generationen[-1], bu.generationen[0]]
    gemischt.annahmen = bu.annahmen
    df = generate(gemischt)
    bis = dt.date(2040, 1, 1)
    erg = fortschreiben(df, gemischt, bis)
    html = report.render_html(
        df, historie=erg.historie, ledger=erg.ledger, scheiben=erg.scheiben,
        config=gemischt, bis=bis, stichtag=dt.date(2026, 1, 1),
        stichtage=[dt.date(2026, 1, 1)],
    )
    # Beide Nachweisungen, jede mit ihren zwei Traeger-Bestaenden:
    assert "Bestandsbewegung: Kapitalversicherung" in html
    assert "Bestandsbewegung: Berufsunfähigkeit" in html
    for ueberschrift in ("Beitragspflichtiger Bestand", "Beitragsfreier Bestand",
                         "Anwärter", "Leistungsbezieher"):
        assert f"<h3>{ueberschrift}</h3>" in html
    # Bezugsgroessen bleiben getrennt benannt:
    assert "Bewegung in Versicherungssumme:" in html
    assert "Bewegung in versicherte Jahresrente:" in html
    # Rechnungsgrundlagen und Erfahrungsannahmen stehen je Nachweisung:
    assert html.count("<strong>Rechnungsgrundlagen</strong>") == 2
    assert html.count("<strong>Erfahrungsannahmen</strong>") == 2


def test_cli_stichtag(portfolio, fortschreibung, tmp_path):
    historie, ledger, scheiben, *_ = fortschreibung
    parquet = write_portfolio(portfolio, tmp_path / "b.parquet")
    h = write_portfolio(historie, tmp_path / "h.parquet")
    l = write_portfolio(ledger, tmp_path / "l.parquet")
    s = write_portfolio(scheiben, tmp_path / "s.parquet")
    out = tmp_path / "b.html"
    assert cli.main([
        "--portfolio", str(parquet), "--historie", str(h), "--ledger", str(l),
        "--scheiben", str(s), "--bis", "2035-01-01", "--stichtag", "2026-01-01",
        "--out", str(out),
    ]) == 0
    assert "ab hier Prognose" in out.read_text(encoding="utf-8")
    assert cli.main([
        "--portfolio", str(parquet), "--stichtag", "kein-datum",
    ]) == 2


def test_stichtag_am_horizont_und_ausserhalb(portfolio, config, fortschreibung):
    """Review-Fix: ein Stichtag genau am Fortschreibungs-Horizont liess den
    Lauf mit ValueError abbrechen (das Konto endet bei bis.year - 1, die
    Chart-Position suchte das Jahr trotzdem in der Liste)."""
    historie, ledger, scheiben, *_ = fortschreibung
    kw = dict(historie=historie, ledger=ledger, scheiben=scheiben,
              stichtage=[dt.date(2020, 1, 1)])
    for stichtag, erwartet_trennung in (
        (dt.date(2035, 1, 1), False),   # am Horizont: alles Historie
        (dt.date(1990, 1, 1), True),    # vor dem Bestand: alles Prognose
        (dt.date(2050, 1, 1), False),   # weit dahinter
        (dt.date(2026, 1, 1), True),    # mittendrin: Trennung
    ):
        html = report.render_html(
            portfolio, bis=dt.date(2035, 1, 1), stichtag=stichtag, **kw
        )
        assert ("ab hier Prognose" in html) is erwartet_trennung, stichtag


def test_neugeschaeft_wird_aus_den_daten_abgeleitet(portfolio, config):
    """Review-Fix: die Zugangs-Aussage kam aus der Config und konnte der
    Zugangszeile derselben Tabelle widersprechen (ein Lauf ohne
    neuzugang_ab hat kein simuliertes Neugeschaeft, die Config sagt aber
    eins zu). Jetzt wird sie aus dem Konto gelesen."""
    from rechner_pipeline.bestand.ereignisse import fortschreiben, mit_zugaengen
    from rechner_pipeline.bestand.generator import generate

    ref = dt.date(2026, 1, 1)
    bis = dt.date(2045, 1, 1)
    basis = generate(config, bis=ref)

    mit = fortschreiben(basis, config, bis, neuzugang_ab=ref)
    html_mit = report.render_html(
        mit_zugaengen(basis, mit.zugaenge), historie=mit.historie,
        ledger=mit.ledger, scheiben=mit.scheiben, config=config,
        bis=bis, stichtag=ref, stichtage=[ref],
    )
    assert "Die Projektion enthält" in html_mit
    assert f"{len(mit.zugaenge)} Zugänge" in html_mit

    # Derselbe Basisbestand ohne simulierten Neuzugang: der Bericht darf
    # kein Neugeschaeft behaupten.
    ohne = fortschreiben(basis, config, bis)
    html_ohne = report.render_html(
        basis, historie=ohne.historie, ledger=ohne.ledger,
        scheiben=ohne.scheiben, config=config, bis=bis, stichtag=ref,
        stichtage=[ref],
    )
    assert "keinen Zugang" in html_ohne and "Abwicklung" in html_ohne


def test_annahmen_text_zeigt_die_volle_affine_form(portfolio, config, fortschreibung):
    """Review-Fix: der additive Teil verschwand, sobald auch b wirkte."""
    import copy

    from rechner_pipeline.bestand.config import Annahme, Annahmen

    historie, ledger, scheiben, *_ = fortschreibung
    cfg = copy.copy(config)
    cfg.annahmen = Annahmen(
        tod=Annahme(a=0.005, b=0.8),          # beide Teile wirksam
        storno=Annahme(a=0.03, b=0.0),
        erhoehung=Annahme(a=0.3, b=0.0),
        erh_prozent=0.05,
    )
    html = report.render_html(
        portfolio, historie=historie, ledger=ledger, scheiben=scheiben,
        config=cfg, bis=dt.date(2035, 1, 1), stichtage=[dt.date(2026, 1, 1)],
    )
    assert "Rechnungsgrundlage × 0,80 zuzüglich 0,50 % p. a." in html
    assert "Storno 3,00 % p. a." in html
    # Die Hoehe der Erhoehung steht neben ihrer Wahrscheinlichkeit:
    assert "Erhöhung um je 5,00 %" in html


def test_bu_bericht_fuehrt_die_jahresrente_als_leistungsspalte():
    """Review-Fix: der Kopfteil war auf sum_insured verdrahtet — bei einem
    BU-Bestand drei Sichten, die strukturell null sind."""
    from rechner_pipeline.bestand.config import load_config
    from rechner_pipeline.bestand.ereignisse import fortschreiben
    from rechner_pipeline.bestand.generator import generate

    cfg = load_config(REPO_ROOT / "examples" / "bestand_bu.toml")
    df = generate(cfg, bis=dt.date(2026, 1, 1))
    erg = fortschreiben(df, cfg, dt.date(2050, 1, 1))
    html = report.render_html(
        df, historie=erg.historie, ledger=erg.ledger, config=cfg,
        bis=dt.date(2050, 1, 1), stichtage=[dt.date(2020, 1, 1)],
    )
    assert "Σ versicherte Jahresrente" in html
    assert "Σ Versicherungssumme" not in html
    # Die Kennzahlen-Spalte traegt echte Werte (nicht strukturell 0):
    import re

    zeile = re.search(
        r"<h2>Kennzahlen je Stichtag[^<]*</h2>.*?<tbody><tr>(.*?)</tr>",
        html, re.S,
    )
    werte = re.findall(r">([\d.,]+)<", zeile.group(1))
    assert float(werte[2].replace(".", "").replace(",", ".")) > 0


# --------------------------------------------------------------------------- #
# Zugaenge der Historie und Volumen je Versicherungsart
# --------------------------------------------------------------------------- #


def test_zugaenge_des_ausgangsbestands_fehlen_in_der_ereignis_sicht_nicht(
    portfolio, fortschreibung
):
    """Die Engine bucht ZUG nur fuer Neuzugaenge — der Ausgangsbestand ist
    zum Simulationsbeginn schon da. In einer Ereignis-Sicht ueber den
    ganzen Zeitraum sagte das etwas Falsches: alle Abgaenge ab dem ersten
    Vertragsjahr, der Zugang erst ab dem Neugeschaeftsjahr."""
    from rechner_pipeline.bestand.ereignisse import mit_zugaengen
    from rechner_pipeline.bestand.kennzahlen import (
        ereignis_summen,
        ereignisse_je_jahr,
        ledger_mit_bestandszugang,
    )

    erg = fortschreibung
    gesamt = mit_zugaengen(portfolio, erg.zugaenge)
    roh = ereignisse_je_jahr(erg.ledger)
    voll = ereignisse_je_jahr(ledger_mit_bestandszugang(gesamt, erg.ledger))

    # Ohne Ergaenzung zeigt die Sicht nur die simulierten Neuzugaenge ...
    assert sum(r["ZUG"] for r in roh) == len(erg.zugaenge) < len(gesamt)
    # ... mit Ergaenzung ist jeder Vertrag genau einmal zugegangen, und der
    # Zugang beginnt im ersten Jahr des Berichtszeitraums.
    assert sum(r["ZUG"] for r in voll) == len(gesamt)
    assert min(r["jahr"] for r in voll if r["ZUG"]) == min(r["jahr"] for r in voll)
    # Betrag und Bezugsgroesse bleiben die der Engine (hier: KLV):
    zug = [s for s in ereignis_summen(
        ledger_mit_bestandszugang(gesamt, erg.ledger)) if s["ereignis"] == "ZUG"]
    assert [s["betrag_art"] for s in zug] == ["VS"]
    assert zug[0]["summe_betrag"] == pytest.approx(
        float(gesamt["sum_insured"].sum())
    )


def test_leerer_ledger_bleibt_leer(portfolio, config):
    """Dass die Fortschreibung nichts gebucht hat, ist die Aussage des
    Abschnitts — sie darf nicht von einer Zugangsliste verdeckt werden."""
    from rechner_pipeline.bestand.ereignisse import fortschreiben

    frueh = portfolio["insurance_start"].min().date()
    historie, ledger, *_ = fortschreiben(portfolio, config, frueh)
    html = report.render_html(
        portfolio, stichtage=[dt.date(2010, 1, 1)],
        historie=historie, ledger=ledger,
    )
    assert "Keine Ereignisse im Berichtszeitraum" in html


def test_volumen_verlauf_steht_je_versicherungsart(gemischter_bestand):
    """Versicherungssumme und Jahresrente sind nicht addierbar: eine
    gemeinsame Kurve waere entweder eine falsche Summe oder — wie zuvor —
    die reine KLV-Kurve neben einem Balken ueber alle Vertraege."""
    df, cfg, erg, bis = gemischter_bestand
    html = report.render_html(
        df, historie=erg.historie, ledger=erg.ledger, scheiben=erg.scheiben,
        config=cfg, bis=bis, stichtag=dt.date(2026, 1, 1),
        stichtage=[dt.date(2026, 1, 1), dt.date(2030, 1, 1)],
    )
    # Je Art eine Volumen-Spalte, beide benannt:
    assert "Σ Versicherungssumme (Kapitalversicherung)" in html
    assert "Σ versicherte Jahresrente (Berufsunfähigkeit)" in html
    # Jede Spalte fuehrt ihren Teilbestand, nicht den Gesamtbestand:
    from rechner_pipeline.bestand.berichtstexte import teilbestand
    from rechner_pipeline.bestand.ereignisse import bestand_mit_historie

    bestand = bestand_mit_historie(df, erg.historie)
    werte = {
        produkt: verlauf(
            teilbestand(bestand, produkt), [dt.date(2026, 1, 1)], spalte
        )[0]["summe_vs"]
        for produkt, spalte in (("klv", "sum_insured"), ("bu", "bu_rente"))
    }
    assert werte["klv"] > 0 and werte["bu"] > 0
    assert werte["klv"] != werte["bu"]
    assert report._zahl(werte["klv"]) in html
    assert report._zahl(werte["bu"]) in html
