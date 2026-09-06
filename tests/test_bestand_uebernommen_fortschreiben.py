"""Einen uebernommenen Bestand fortschreiben — ab dem Zugang, nicht ab Null.

Nach einer Migration lebt der Bestand in den Buechern des aufnehmenden
Unternehmens weiter. Die Ereignis-Engine konnte das nicht: Sie nahm nur
einen Ursprungsbestand (alles POL, ``status_id`` 1) und simulierte ab dem
Versicherungsbeginn. Auf einen uebernommenen Vertrag angewandt haette sie
die Jahre beim abgebenden Unternehmen neu erfunden und als unsere
gebucht.

Der Befund, der das erzwang: Im zusammengesetzten Bestand liefen 477 der
500 uebernommenen Vertraege vor dem Horizont ab, ohne Abgangsbuchung. Die
Nachweisung brach in jedem Jahr ab 2026 die Identitaet
``Anfang + Zugang - Abgang - Umbuchung = Ende``.

Knoten: system/bestand
"""

from __future__ import annotations

import datetime as _dt

import pandas as pd
import pytest

from rechner_pipeline.bestand.ereignisse import EreignisError, fortschreiben
from rechner_pipeline.models.bestand import STAMM_NAMES, STAMM_SPALTEN

BIS = _dt.date(2046, 1, 1)
ZUGANG = _dt.date(2026, 1, 1)


def _stamm(zeilen) -> pd.DataFrame:
    """Stammzeilen aus knappen Angaben; Vorgaben wie beim eigenen Geschaeft."""
    rohe = []
    for v in zeilen:
        beginn = pd.Timestamp(v["beginn"])
        n, t = v.get("n", 25), v.get("t", 25)
        zugang = pd.Timestamp(v.get("zugang", beginn))
        status_date = pd.Timestamp(v.get("status_date", beginn))
        rohe.append({
            "police_id": v["id"],
            "tarif_generation": v.get("gen", "klv/zellen"),
            "produkt": "klv",
            "status_id": v.get("status_id", 1),
            "status_code": v.get("status", "POL"),
            "status_date": status_date,
            "sex": "M",
            "date_of_birth": beginn - pd.DateOffset(years=40),
            "entry_age": 40,
            "duration": n,
            "premium_duration": t,
            "sum_insured": 100_000.0,
            "bu_rente": 0.0,
            "zahlweise": 1,
            "insurance_start": beginn,
            "insurance_end": beginn + pd.DateOffset(years=n),
            "payment_end": beginn + pd.DateOffset(years=t),
            "bestandszugang": zugang,
        })
    return pd.DataFrame(rohe)[list(STAMM_NAMES)].astype(dict(STAMM_SPALTEN))


#: Eine Generation ohne Zellen — hier geht es um den Zugang, nicht um
#: Tarife. Als Modulkonstante, weil auch die CLI-Tests sie auf die Platte
#: schreiben muessen.
_CONFIG_TOML = """
[meta]
seed = 7
beschreibung = "Uebernahme"
referenzstichtag = 2026-01-01

[[generation]]
name = "klv/zellen"
knoten = "klv/zellen"
gueltig_von = 2000-01-01
gueltig_bis = 2040-12-31
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

[annahmen.tod]
a = 0.0
b = 1.0

[annahmen.storno]
a = 0.02
b = 0.0

[annahmen.beitragsfreistellung]
a = 0.02
b = 0.0

[annahmen]
erh_prozent = 0.05

[annahmen.erhoehung]
a = 0.05
b = 0.0
"""


@pytest.fixture(scope="module")
def config(tmp_path_factory):
    from rechner_pipeline.bestand.config import load_config

    pfad = tmp_path_factory.mktemp("cfg") / "uebernahme.toml"
    pfad.write_text(_CONFIG_TOML, encoding="utf-8")
    cfg = load_config(pfad)
    assert cfg.validate() == []
    return cfg


def test_vor_dem_zugang_wird_nichts_gebucht(config):
    """Die Jahre beim abgebenden Unternehmen gehoeren nicht uns.

    Der Vertrag laeuft seit 2015; wir haben ihn seit 2026. Alles, was die
    Engine bucht, muss danach liegen — sonst erfaende sie eine Geschichte,
    die anderswo stattfand, und schriebe sie in unser Journal.
    """
    stamm = _stamm([{"id": 1, "beginn": "2015-01-01", "zugang": "2026-01-01"}])
    f = fortschreiben(stamm, config, BIS)

    assert len(f.ledger), "der Vertrag laeuft noch 14 Jahre, da passiert etwas"
    assert (f.ledger["status_date"].dt.date > ZUGANG).all(), (
        "Buchung vor dem Zugang: "
        + str(sorted(set(str(d)[:10] for d in f.ledger["status_date"]))[:3]))
    # Und die Vertragsjahre zaehlen weiter ab dem BEGINN, nicht ab dem
    # Zugang: Der Kern rechnet den Vertrag, nicht die Zugehoerigkeit.
    assert (f.ledger["vertragsjahr"] >= 11).all()


def test_eigenes_geschaeft_bleibt_unveraendert(config):
    """Zugang = Beginn heisst: exakt der Lauf von vorher.

    Die Verallgemeinerung darf den Eigenbestand nicht bewegen — sonst
    waere jede bestehende Reihe stillschweigend eine andere.
    """
    zeilen = [{"id": i, "beginn": "2015-01-01"} for i in range(1, 21)]
    eigen = fortschreiben(_stamm(zeilen), config, BIS)
    nochmal = fortschreiben(_stamm(zeilen), config, BIS)
    pd.testing.assert_frame_equal(eigen.ledger, nochmal.ledger)

    # Der Beweis, dass der Versatz wirkt UND nur beim uebernommenen
    # Geschaeft: dieselben Vertraege, einmal mit Zugang beim Beginn und
    # einmal mit Zugang 2026. Der Eigenbestand bucht in den Jahren davor,
    # der uebernommene nicht.
    spaet = fortschreiben(
        _stamm([{**z, "zugang": "2026-01-01"} for z in zeilen]), config, BIS)
    frueh = eigen.ledger[eigen.ledger["status_date"].dt.date <= ZUGANG]
    assert len(frueh), "der Eigenbestand lebt seit 2015 und bucht auch davor"
    assert not len(spaet.ledger[spaet.ledger["status_date"].dt.date <= ZUGANG])


def test_beitragsfrei_uebernommen_wird_nicht_erneut_freigestellt(config):
    """Der mitgebrachte Zustand bleibt, er wird nicht neu gebucht.

    Ein Vertrag, der 2022 beitragsfrei gestellt wurde, kommt beitragsfrei
    an. Die Engine darf ihn nicht noch einmal freistellen — und sie darf
    ihn auch nicht als beitragspflichtig weiterfuehren, sonst zoege er
    Storno- und Erhoehungsereignisse, die es fuer ihn nicht mehr gibt.
    """
    stamm = _stamm([{
        "id": 1, "beginn": "2015-01-01", "zugang": "2026-01-01",
        "status": "PEX", "status_id": 2, "status_date": "2022-01-01",
    }])
    f = fortschreiben(stamm, config, BIS)

    assert "PEX" not in set(f.ledger["ereignis"])
    assert "STO" not in set(f.ledger["ereignis"]), (
        "ein beitragsfreier Vertrag storniert nicht")
    assert "ERH" not in set(f.ledger["ereignis"]), (
        "ein beitragsfreier Vertrag erhoeht nicht dynamisch")


def test_die_statusnummern_setzen_den_mitgebrachten_stand_fort(config):
    """Keine zwei Zeilen mit derselben Nummer.

    Der beitragsfrei uebernommene Vertrag traegt bereits ``status_id`` 2.
    Numerierte die Fortschreibung wieder ab 2, koennte der Stamm seinen
    juengsten Journalstand nicht mehr bestimmen.
    """
    stamm = _stamm([
        {"id": 1, "beginn": "2015-01-01", "zugang": "2026-01-01"},
        {"id": 2, "beginn": "2015-01-01", "zugang": "2026-01-01",
         "status": "PEX", "status_id": 2, "status_date": "2022-01-01"},
    ])
    f = fortschreiben(stamm, config, BIS)

    fuer = lambda pid: sorted(f.historie.loc[f.historie["police_id"] == pid,
                                             "status_id"])
    assert fuer(1) and min(fuer(1)) == 2, "auf die Basis-POL (1) folgt 2"
    assert fuer(2) and min(fuer(2)) == 3, "auf die PEX-Zeile (2) folgt 3"


def test_ein_bereits_fortgeschriebener_bestand_wird_abgewiesen(config):
    """Zweimal simulieren ist kein Lauf, sondern ein Fehler.

    Traegt ein uebernommener Vertrag einen Zustandswechsel NACH seinem
    Zugang, ist er schon fortgeschrieben. Ihn erneut zu fahren erzeugte
    Ereignisse doppelt.
    """
    stamm = _stamm([{
        "id": 1, "beginn": "2015-01-01", "zugang": "2026-01-01",
        "status": "PEX", "status_id": 2, "status_date": "2030-01-01",
    }])
    with pytest.raises(EreignisError) as exc:
        fortschreiben(stamm, config, BIS)
    assert "bereits fortgeschrieben" in str(exc.value)


def test_ein_beendeter_vertrag_wird_nicht_uebernommen(config):
    """Ein stornierter Vertrag ist kein Bestand."""
    stamm = _stamm([{
        "id": 1, "beginn": "2015-01-01", "zugang": "2026-01-01",
        "status": "STO", "status_id": 2, "status_date": "2022-01-01",
    }])
    with pytest.raises(EreignisError) as exc:
        fortschreiben(stamm, config, BIS)
    assert "Endzustand" in str(exc.value)


def test_der_eigenbestand_bleibt_gegen_journalsichten_geschuetzt(config):
    """Die alte Wache steht weiter.

    Eine Zeitscheiben- oder Journalsicht des EIGENEN Bestands hat
    Folgezustaende bei gleichem Zugang und Beginn — sie darf nicht als
    Basisbestand durchgehen, sonst simulierte die Engine sie ab dem
    Versicherungsbeginn ein zweites Mal.
    """
    stamm = _stamm([{
        "id": 1, "beginn": "2015-01-01",
        "status": "PEX", "status_id": 2, "status_date": "2022-01-01",
    }])
    with pytest.raises(EreignisError) as exc:
        fortschreiben(stamm, config, BIS)
    assert "kein Basisbestand" in str(exc.value)


# --------------------------------------------------------------------------- #
# Das Kommando: eigener und uebernommener Bestand in EINEM Lauf
# --------------------------------------------------------------------------- #


def _schreibe_uebernahme(verzeichnis):
    """Ein Uebernahme-Verzeichnis wie gates.bestand_uebernehmen es schreibt."""
    from rechner_pipeline.bestand.parquet_io import write_portfolio
    from rechner_pipeline.models.bestand import (
        LEDGER_SPALTEN,
        STATUS_HISTORIE_SPALTEN,
    )

    verzeichnis.mkdir(parents=True, exist_ok=True)
    stamm = _stamm([
        {"id": 900_001, "beginn": "2015-01-01", "zugang": "2026-01-01"},
        {"id": 900_002, "beginn": "2015-01-01", "zugang": "2026-01-01",
         "status": "PEX", "status_id": 2, "status_date": "2022-01-01"},
    ])
    historie = pd.DataFrame([{
        "police_id": 900_002, "status_id": 2, "status_code": "PEX",
        "status_date": pd.Timestamp("2022-01-01"),
    }])[[n for n, _ in STATUS_HISTORIE_SPALTEN]].astype(dict(STATUS_HISTORIE_SPALTEN))
    ledger = pd.DataFrame([
        {"police_id": pid, "tarif_generation": "klv/zellen", "ereignis": ev,
         "vertragsjahr": 11, "status_date": pd.Timestamp("2026-01-01"),
         "betrag_art": "VS", "betrag": betrag, "betrag_herkunft": herkunft}
        for pid, ev, betrag, herkunft in (
            (900_001, "ZUG", 100_000.0, "geliefert"),
            (900_002, "ZUG", 100_000.0, "geliefert"),
            (900_002, "PEX", 61_000.0, "gerechnet"),
        )
    ])[[n for n, _ in LEDGER_SPALTEN]].astype(dict(LEDGER_SPALTEN))

    write_portfolio(stamm, verzeichnis / "bestand.parquet")
    write_portfolio(historie, verzeichnis / "historie.parquet")
    write_portfolio(ledger, verzeichnis / "ledger.parquet")
    return stamm, historie, ledger


def test_cli_faehrt_eigenen_und_uebernommenen_bestand_in_einem_lauf(tmp_path):
    """Ein GeVo-Strom, ein Erzeuger — auch nach einer Migration.

    Zwei getrennte Laeufe zu mischen ergaebe einen Bestand, in dem ein
    Teil fortgeschrieben ist und der andere nicht: Die uebernommenen
    Vertraege verschwaenden ueber ``insurance_end`` aus dem Schnitt, ohne
    dass sie jemand ausbucht, und die Bestandsbewegung ginge nicht auf
    (ADR-015). Deshalb nimmt das Kommando die Uebernahme MIT hinein.
    """
    from rechner_pipeline.bestand import cli_fortschreibung as fs_cli
    from rechner_pipeline.bestand.parquet_io import read_portfolio, write_portfolio
    from rechner_pipeline.models.bestand import LEDGER_NAMES, STAMM_NAMES

    eigen = _stamm([{"id": i, "beginn": "2015-01-01"} for i in range(1, 11)])
    eigen_pfad = tmp_path / "eigen.parquet"
    write_portfolio(eigen, eigen_pfad)
    uebernahme = tmp_path / "uebernahme"
    _schreibe_uebernahme(uebernahme)

    cfg_pfad = tmp_path / "cfg.toml"
    cfg_pfad.write_text(_CONFIG_TOML, encoding="utf-8")

    out = tmp_path / "lauf"
    assert fs_cli.main([
        "--config", str(cfg_pfad), "--bis", "2046-01-01",
        "--portfolio", str(eigen_pfad),
        "--uebernahme", str(uebernahme),
        "--out-dir", str(out),
    ]) == 0

    gesamt = read_portfolio(out / "bestand_gesamt.parquet",
                            expected_columns=STAMM_NAMES)
    ledger = read_portfolio(out / "ledger.parquet", expected_columns=LEDGER_NAMES)
    assert len(gesamt) == 12, "zehn eigene und zwei uebernommene"

    # Die Buchungen der Uebernahme stehen voran und sind erhalten.
    uebern = ledger[ledger["police_id"] >= 900_000]
    assert {"ZUG", "PEX"} <= set(uebern["ereignis"])
    assert "gerechnet" in set(uebern["betrag_herkunft"])
    # Und die Fortschreibung hat die uebernommenen Vertraege ausgebucht --
    # genau das fehlte vorher.
    abgang = uebern[uebern["ereignis"].isin(("ABL", "STO", "TOD"))]
    assert len(abgang) == 2, "beide uebernommenen Vertraege enden vor 2046"
    assert (abgang["status_date"].dt.date > ZUGANG).all()


def test_cli_weist_kollidierende_policennummern_ab(tmp_path):
    """Eine Nummer, ein Vertrag.

    Kollidieren die Nummernkreise, bezeichnete dieselbe Nummer zwei
    verschiedene Vertraege — und jede Auswertung waehlte zufaellig einen.
    """
    from rechner_pipeline.bestand import cli_fortschreibung as fs_cli
    from rechner_pipeline.bestand.parquet_io import write_portfolio

    eigen = _stamm([{"id": 900_001, "beginn": "2015-01-01"}])
    eigen_pfad = tmp_path / "eigen.parquet"
    write_portfolio(eigen, eigen_pfad)
    uebernahme = tmp_path / "uebernahme"
    _schreibe_uebernahme(uebernahme)
    cfg_pfad = tmp_path / "cfg.toml"
    cfg_pfad.write_text(_CONFIG_TOML, encoding="utf-8")

    assert fs_cli.main([
        "--config", str(cfg_pfad), "--bis", "2046-01-01",
        "--portfolio", str(eigen_pfad),
        "--uebernahme", str(uebernahme),
        "--out-dir", str(tmp_path / "lauf"),
    ]) == 2


def test_cli_verlangt_die_pflichttabellen_der_uebernahme(tmp_path):
    """Ein halbes Uebernahme-Verzeichnis ist kein uebernommener Bestand."""
    from rechner_pipeline.bestand import cli_fortschreibung as fs_cli

    leer = tmp_path / "leer"
    leer.mkdir()
    cfg_pfad = tmp_path / "cfg.toml"
    cfg_pfad.write_text(_CONFIG_TOML, encoding="utf-8")

    assert fs_cli.main([
        "--config", str(cfg_pfad), "--bis", "2046-01-01",
        "--uebernahme", str(leer),
        "--out-dir", str(tmp_path / "lauf"),
    ]) == 2
