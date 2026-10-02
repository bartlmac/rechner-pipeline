"""Der Endzustand wird hergeleitet, nicht auf Form geprueft — Pruefrunde T27, Befund 07.

Die Klasse: Die Fuehrungsprobe verglich im Endbestand die Identitaets-
spalten und die Vokabel der Historie. Was sich bewegen darf — Zustand,
Historie, Scheiben —, pruefte sie nicht gegen das, woraus es entsteht.
Der Gutachter ersetzte die Endscheiben durch eine leere Tabelle, die
Endhistorie durch eine leere, und setzte eine aktive Police auf den
Ablaufzustand einer anderen: dreimal bestanden. Jetzt gilt:

* Endhistorie = Historie der Uebernahme + je Zustands-GeVo nach dem
  Stichtag eine Zeile (models.bestand.EREIGNIS_ZUSTAND);
* Zustand im Endstamm = juengste Zeile dieser Historie, sonst der
  uebernommene Zustand;
* Endscheiben = Scheiben der Uebernahme unveraendert + je Erhoehung nach
  dem Stichtag eine Scheibe.

Knoten: system/abnahme
"""

from __future__ import annotations

from pathlib import Path

import pandas as pd
import pytest

from rechner_pipeline.gates.fuehrungsprobe import pruefe_fuehrung
from tests.test_baldrian2_e2e import _probe_material, gefahrener_fall  # noqa: F401


@pytest.fixture(scope="module")
def material(gefahrener_fall):  # noqa: F811
    ueb, fort, basis = _probe_material(gefahrener_fall)
    gut = pruefe_fuehrung(uebernahme=ueb, fortschreibung=fort, **basis)
    assert gut["bestanden"], ("Positivkontrolle", gut["befunde"][:3])
    return ueb, fort, basis


def _urteil(material, **ersetzt):
    ueb, fort, basis = material
    return pruefe_fuehrung(uebernahme=ueb, fortschreibung={**fort, **ersetzt}, **basis)


def _nach(fort, stichtag):
    return pd.to_datetime(fort["ledger"]["status_date"]) > pd.Timestamp(stichtag)


def test_leere_endscheiben_fallen(material):
    _ueb, fort, _b = material
    assert len(fort["scheiben"]) > 0, "ohne Endscheiben sieht der Test nichts"
    assert not _urteil(material, scheiben=fort["scheiben"].iloc[0:0])["bestanden"]


def test_leere_endhistorie_faellt(material):
    _ueb, fort, _b = material
    assert len(fort["historie"]) > 0
    assert not _urteil(material, historie=fort["historie"].iloc[0:0])["bestanden"]


def test_ein_fremder_ablaufzustand_im_endstamm_faellt(material):
    ueb, fort, _b = material
    bestand = fort["bestand"].copy()
    uebernommen = set(int(p) for p in ueb["bestand"]["police_id"])
    aktiv = bestand[(bestand["status_code"] == "POL") & bestand["police_id"].isin(uebernommen)]
    abl = bestand[bestand["status_code"] == "ABL"]
    assert len(aktiv) and len(abl), "die Welt traegt keine aktive oder keine abgelaufene Police"
    i, quelle = aktiv.index[0], abl.iloc[0]
    for spalte in ("status_id", "status_code", "status_date"):
        bestand.loc[i, spalte] = quelle[spalte]
    assert not _urteil(material, bestand=bestand)["bestanden"]


def test_historie_und_stamm_gemeinsam_gefaelscht_ohne_buchung_fallen(material):
    """Stamm und Historie in sich stimmig (Stornozustand), aber kein STO
    im Ledger: Der Zustand kommt aus den GeVos, nicht aus sich selbst."""
    ueb, fort, basis = material
    bestand, historie = fort["bestand"].copy(), fort["historie"].copy()
    uebernommen = set(int(p) for p in ueb["bestand"]["police_id"])
    aktiv = bestand[(bestand["status_code"] == "POL") & bestand["police_id"].isin(uebernommen)]
    assert len(aktiv)
    i = aktiv.index[0]
    pid = int(bestand.loc[i, "police_id"])
    datum = pd.Timestamp(basis["stichtag"]) + pd.DateOffset(months=5)
    naechste = int(historie.loc[historie["police_id"] == pid, "status_id"].max()) + 1 \
        if (historie["police_id"] == pid).any() else 2
    zeile = {c: historie[c].iloc[0] for c in historie.columns}
    zeile.update({"police_id": pid, "status_id": naechste, "status_code": "STO", "status_date": datum})
    historie = pd.concat([historie, pd.DataFrame([zeile])[historie.columns]], ignore_index=True)
    historie = historie.astype(fort["historie"].dtypes.to_dict())
    bestand.loc[i, ["status_id", "status_code", "status_date"]] = [naechste, "STO", datum]
    assert not _urteil(material, bestand=bestand, historie=historie)["bestanden"]


def test_eine_erhoehungsscheibe_ohne_erh_buchung_faellt(material):
    _ueb, fort, basis = material
    scheiben = fort["scheiben"].copy()
    assert len(scheiben), "die Welt traegt keine Scheibe"
    extra = scheiben.iloc[[0]].copy()
    extra["erhoehung_datum"] = pd.Timestamp(basis["stichtag"]) + pd.DateOffset(months=4)
    extra["scheiben_id"] = int(scheiben["scheiben_id"].max()) + 1
    scheiben = pd.concat([scheiben, extra], ignore_index=True).astype(fort["scheiben"].dtypes.to_dict())
    assert not _urteil(material, scheiben=scheiben)["bestanden"]


def test_eine_erh_buchung_ohne_scheibe_faellt(material):
    ueb, fort, basis = material
    ledger = fort["ledger"].copy()
    uebernommen = set(int(p) for p in ueb["bestand"]["police_id"])
    aktiv = fort["bestand"][(fort["bestand"]["status_code"] == "POL")
                            & fort["bestand"]["police_id"].isin(uebernommen)]
    assert len(aktiv)
    zeile = {c: ledger[c].iloc[0] for c in ledger.columns}
    zeile.update({"police_id": int(aktiv["police_id"].iloc[0]), "ereignis": "ERH",
                  "betrag_art": "VS_erhoehung", "betrag": 1234.0,
                  "status_date": pd.Timestamp(basis["stichtag"]) + pd.DateOffset(months=4)})
    ledger = pd.concat([ledger, pd.DataFrame([zeile])[ledger.columns]], ignore_index=True)
    ledger = ledger.astype(fort["ledger"].dtypes.to_dict())
    assert not _urteil(material, ledger=ledger)["bestanden"]


def test_eine_veraenderte_uebernommene_scheibe_faellt(material):
    ueb, fort, basis = material
    scheiben = fort["scheiben"].copy()
    alt = scheiben[pd.to_datetime(scheiben["erhoehung_datum"]) <= pd.Timestamp(basis["stichtag"])]
    assert len(alt), "die Uebernahme traegt keine Scheibe"
    scheiben.loc[alt.index[0], "sum_insured"] = float(scheiben.loc[alt.index[0], "sum_insured"]) + 1000.0
    assert not _urteil(material, scheiben=scheiben)["bestanden"]


def test_eine_verlorene_historienzeile_der_uebernahme_faellt(material):
    """Nur die Historie ist falsch, der juengste Zustand stimmt: Eine
    Umbuchungszeile der Uebernahme fehlt, deren Police danach nichts mehr
    erlebt hat — der Stamm traegt denselben Zustand wie vorher. Das sieht
    nur die Herleitung der Historie, nicht die des Zustands."""
    ueb, fort, basis = material
    historie = fort["historie"]
    nach = _nach(fort, basis["stichtag"])
    bewegt = set(int(p) for p in fort["ledger"][nach]["police_id"])
    kandidaten = historie[~historie["police_id"].isin(bewegt)
                          & historie["police_id"].isin(set(int(p) for p in ueb["historie"]["police_id"]))]
    einzeln = kandidaten.groupby("police_id").filter(lambda g: len(g) == 1)
    assert len(einzeln), "keine Police mit genau einer uebernommenen Historienzeile"
    assert not _urteil(material, historie=historie.drop(index=einzeln.index[0]))["bestanden"]
