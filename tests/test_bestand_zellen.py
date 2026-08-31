"""Tarifzellen: eine Generation, mehrere Rechnungsgrundlagen.

Eine uebernommene Generation ist selten ein einziger Parametersatz. Die
TG2015 der Baldrian-Uebernahme fuehrt sechs Zellen ueber ``status`` und
``tarifart``; zwoelf von siebzehn Kernfeldern unterscheiden sich zwischen
ihnen -- bis zur Sterbetafel und zum Stornoabzug. Solange die Config nur
EINEN Satz kannte, bewertete der Bestandsbericht jeden uebernommenen
Vertrag mit der Zelle, die zufaellig in der Datei stand.

Diese Tests halten drei Dinge fest: dass die Zelle die Zahl aendert, dass
eine fehlende Zuordnung ein Fehler ist und kein stiller Rueckfall, und
dass ein unvollstaendiger Merkmalsraum beim Lesen der Config auffaellt --
nicht erst bei der Bewertung.

Knoten: system/bestand
"""

from __future__ import annotations

import datetime as _dt
from pathlib import Path

import pandas as pd
import pytest

from rechner_pipeline.bestand.auswertung import einzelwerte_am
from rechner_pipeline.bestand.config import TarifGeneration, TarifZelle, load_config
from rechner_pipeline.models.bestand import STAMM_NAMES, STAMM_SPALTEN

STICHTAG = _dt.date(2026, 1, 1)

#: Zwei Zellen, die sich nur in der Sterbetafel unterscheiden -- der
#: kleinste Unterschied, der eine andere Zahl erzwingt.
TOML = """
[meta]
seed = 1
beschreibung = "Zwei Tarifzellen"
referenzstichtag = 2026-01-01

[[generation]]
name = "klv/zellen"
knoten = "klv/zellen"
gueltig_von = 2015-01-01
gueltig_bis = 2016-12-31
sample_size = 0
max_endalter = 85
zins = 0.0125
tafel = "DAV2008_T_NR_U70"
alpha = 0.025
beta1 = 0.03
gamma1 = 0.001
gamma2 = 0.00125
gamma3 = 0.0025
policy_fee = 12.0
min_alter_flex = 60
min_rlz_flex = 5

[generation.verteilungen.entry_age]
typ = "normal_trunc"
mean = 40.0
sd = 12.0
min = 18.0
max = 62.0
round = 0

[generation.verteilungen.sex]
typ = "empirical_discrete"
values = ["M", "F"]
probs = [0.5, 0.5]

[generation.verteilungen.duration]
typ = "empirical_discrete"
values = [25]
probs = [1.0]

[generation.verteilungen.premium_duration]
typ = "empirical_discrete"
values = [25]
probs = [1.0]

[generation.verteilungen.sum_insured]
typ = "lognormal"
meanlog = 11.2
sdlog = 0.5
round = -3

[generation.verteilungen.zahlweise]
typ = "empirical_discrete"
values = [1]
probs = [1.0]

[[generation.zelle]]
auspraegungen = { status = "nichtraucher" }
tafel = "DAV2008_T_NR_U70"

[[generation.zelle]]
auspraegungen = { status = "raucher" }
tafel = "DAV2008_T_R_U70"
"""


def _config(tmp_path: Path, toml: str = TOML):
    pfad = tmp_path / "zellen.toml"
    pfad.write_text(toml, encoding="utf-8")
    return load_config(pfad)


def _stamm() -> pd.DataFrame:
    """Zwei baugleiche Vertraege -- der einzige Unterschied ist die Zelle."""
    zeilen = []
    for pid in (1, 2):
        zeilen.append({
            "police_id": pid,
            "produkt": "klv",
            "tarif_generation": "klv/zellen",
            "entry_age": 40,
            "sex": "M",
            "duration": 25,
            "premium_duration": 25,
            "sum_insured": 100_000.0,
            "zahlweise": 1,
            "insurance_start": pd.Timestamp("2015-01-01"),
            "insurance_end": pd.Timestamp("2040-01-01"),
            "payment_end": pd.Timestamp("2040-01-01"),
            "date_of_birth": pd.Timestamp("1975-01-01"),
            "status_id": 1,
            "status_code": "POL",
            "status_date": pd.Timestamp("2015-01-01"),
            "bu_rente": 0.0,
        })
    return pd.DataFrame(zeilen)[list(STAMM_NAMES)].astype(dict(STAMM_SPALTEN))


def _merkmale(*auspraegungen: str) -> pd.DataFrame:
    return pd.DataFrame([
        {"police_id": pid, "dimension": "status", "auspraegung": a}
        for pid, a in enumerate(auspraegungen, start=1)
    ]).astype({"police_id": "int64"})


def test_die_zelle_aendert_die_bewertung(tmp_path: Path):
    """Raucher und Nichtraucher duerfen nicht dieselbe Zahl bekommen.

    Beide Vertraege sind bis aufs Merkmal identisch. Kaeme die
    Sterbetafel weiter aus der Generation, waeren beide Deckungskapitale
    gleich -- genau der Zustand, den die Zellen beenden.
    """
    config = _config(tmp_path)
    assert not config.validate()

    zeilen = einzelwerte_am(
        _stamm(), None, config, STICHTAG,
        merkmale=_merkmale("nichtraucher", "raucher"),
    )
    je_police = {z["police_id"]: z for z in zeilen}
    assert len(je_police) == 2

    nr, r = je_police[1], je_police[2]
    assert nr["deckungskapital"] > 0 and r["deckungskapital"] > 0
    assert nr["deckungskapital"] != r["deckungskapital"], \
        "gleiche Zahl heisst: die Zelle wirkt nicht"

    # Richtung: Bei der gemischten Versicherung ist die Todesfall- gleich
    # der Erlebensfallleistung. Die hoehere Sterblichkeit hebt deshalb vor
    # allem den Beitrag -- und mit ihm die Reserve, in die er einzahlt.
    assert r["jahresbeitrag"] > nr["jahresbeitrag"]
    assert r["deckungskapital"] > nr["deckungskapital"]


def test_ohne_merkmale_bricht_die_bewertung_ab(tmp_path: Path):
    """Kein stiller Rueckfall auf den Rumpf der Generation.

    Der Rumpf gilt bei einer aufgeteilten Generation fuer keinen
    einzigen Vertrag. Ihn hilfsweise zu nehmen ergaebe eine Bilanzzahl,
    die niemand als falsch erkennt -- deshalb ein harter Abbruch mit dem
    Ausweg in der Meldung.
    """
    config = _config(tmp_path)
    with pytest.raises(ValueError) as exc:
        einzelwerte_am(_stamm(), None, config, STICHTAG)
    assert "merkmale.parquet" in str(exc.value)


def test_unbekannte_auspraegung_ist_keine_zelle(tmp_path: Path):
    """Ein Tippfehler waehlt keine Zelle -- er ist einer."""
    config = _config(tmp_path)
    with pytest.raises(KeyError) as exc:
        einzelwerte_am(
            _stamm(), None, config, STICHTAG,
            merkmale=_merkmale("nichtraucher", "raucherin"),
        )
    assert "keine Tarifzelle" in str(exc.value)


def test_ohne_zellen_bleibt_alles_wie_bisher(tmp_path: Path):
    """Der Eigenbestand kennt keine Zellen -- und merkt nichts von ihnen.

    Eine Config ohne ``[[generation.zelle]]`` muss exakt dieselben Werte
    liefern wie vor dem Umbau, auch wenn eine Merkmalstabelle danebenliegt.
    """
    ohne = TOML.split("[[generation.zelle]]")[0]
    config = _config(tmp_path, ohne)
    assert not config.validate()
    assert config.generationen[0].zellen == []

    a = einzelwerte_am(_stamm(), None, config, STICHTAG)
    b = einzelwerte_am(_stamm(), None, config, STICHTAG,
                       merkmale=_merkmale("nichtraucher", "raucher"))
    assert a == b


def test_luecke_und_doppelung_im_merkmalsraum_fallen_beim_lesen_auf():
    """Beim Validieren, nicht erst bei der Bewertung.

    Eine Zelle, die eine Dimension auslaesst, macht die Zuordnung
    mehrdeutig; zwei gleiche Zellen machen sie von der Reihenfolge in der
    Datei abhaengig. Beides ist ein Config-Fehler.
    """
    gen = TarifGeneration(
        name="klv/x", gueltig_von=_dt.date(2015, 1, 1),
        gueltig_bis=_dt.date(2016, 1, 1), sample_size=0, max_endalter=85,
        knoten="klv/x", tafel="DAV2008_T_NR_U70",
        zellen=[
            TarifZelle({"status": "raucher", "tarifart": "einzel"}),
            TarifZelle({"status": "raucher"}),                  # Luecke
            TarifZelle({"status": "raucher", "tarifart": "einzel"}),  # doppelt
            TarifZelle({"status": "nichtraucher", "tarifart": "einzel"},
                       {"erfundenes_feld": 1.0}),
        ],
    )
    befunde = " | ".join(gen.validate())
    assert "laesst die Dimensionen ['tarifart'] offen" in befunde
    assert "doppelt" in befunde
    assert "unbekannte Kernfelder" in befunde


def test_die_zelle_ueberschreibt_nur_ihre_eigenen_felder(tmp_path: Path):
    """Sie traegt die Abweichung, nicht den ganzen Satz.

    Sonst muesste jede der sechs Baldrian-Zellen siebzehn Werte
    wiederholen, und ein spaeter geaenderter Zins waere an sechs Stellen
    zu pflegen -- fuenf davon wuerde jemand vergessen.
    """
    gen = _config(tmp_path).generationen[0]
    felder = gen.felder_fuer({"status": "raucher"})
    assert felder["tafel"] == "DAV2008_T_R_U70"   # aus der Zelle
    assert felder["zins"] == 0.0125               # aus der Generation
    assert felder["alpha"] == 0.025
    assert set(felder) == set(gen.generation_fields())
