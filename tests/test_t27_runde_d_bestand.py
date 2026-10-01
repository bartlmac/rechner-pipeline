"""Runde D, Bereich Kern/Bestand — vier Funde der Herabsetzung und ihrer Nachweise.

1. **Abzug je Baustein bei der Herabsetzung (mit Abzug).** In einer
   Generation mit ``stoab_je_baustein = true`` (Bedingungswerk Ziffer 4)
   bildete ``reduziere_geschichtet`` den Umwandlungsabzug vertragsweit und
   ignorierte den Schalter; die Teilkuendigung hielt ihn schon richtig. Soll
   (klv.md 6, 7.1): umgewandelt wird (1-f) x RKW, der RKW nach dem Tarifwerk
   der Generation — dieselbe Groesse, die ein Storno am selben Tag zahlt.
   Messung des Angreifers: KLV_DEFAULT mit Abzug 0,005 / 50 / 200, Scheiben
   in Jahr 2 und 3, a0 = 6, f = 0,3: ist 54.578,30, soll 54.485,43.
2. **Bericht und Horizont.** ``bestand_report`` rief P-B1 ohne Manifest und
   rendert damit eine RED hinter dem belegten Horizont, die P-B1 auf denselben
   Bytes abweist.
3. **Probe und Reduktionsjahr.** Die Fuehrungsprobe hielt eine RED-Zeile
   ausserhalb des registrierten Reduktionsjahres gegen das Soll des
   Buchungsjahres bzw. ungekuerzt und zaehlte sie als geprueft.
4. **Bericht nur mit Stamm.** Ohne ``--historie``/``--ledger`` suchte der
   Bericht ``reduktionen.parquet`` nicht und bewertete herabgesetzte
   Vertraege ungekuerzt.

Jede Aussage hat ihre Positivkontrolle (derselbe Aufruf an zulaessiger
Stelle bleibt gruen).

Knoten: klv
"""

from __future__ import annotations

import dataclasses

import pytest

from rechner_pipeline.bestand.ereignisse import _Vertrag
from rechner_pipeline.kern import KLV_DEFAULT, Rechenkern
from rechner_pipeline.kern.beitragsreduktion import (
    MIT_ABZUG,
    PROSPEKTIV,
    reduzierte_teile,
    reduziere_geschichtet,
)

# --------------------------------------------------------------------------- #
# Fund 1: Abzug je Baustein bei der Herabsetzung mit Abzug
# --------------------------------------------------------------------------- #

#: Der Fall des Angreifers: Abzug 0,5 % / min 50 / max 200, zwei Scheiben.
_MP = dataclasses.replace(KLV_DEFAULT, stoab_satz=0.005, stoab_min=50.0, stoab_max=200.0)
_S = _MP.sum_insured
_SCHEIBEN = [
    (2, dataclasses.replace(_MP, x=_MP.x + 2, n=_MP.n - 2, t=_MP.t - 2,
                            sum_insured=0.05 * _S, gamma1=0.0)),
    (3, dataclasses.replace(_MP, x=_MP.x + 3, n=_MP.n - 3, t=_MP.t - 3,
                            sum_insured=0.05 * 1.05 * _S, gamma1=0.0)),
]
_A0, _F = 6, 0.3
#: Die unabhaengige Sollrechnung des Angreifers (eigene Tafelarithmetik,
#: klv.md 4 bis 7.1), je Schalter.
_VS_SOLL_JE_BAUSTEIN = 54485.4311
_VS_SOLL_VERTRAGSWEIT = 54578.2976


def _vertrag(je_baustein: bool) -> _Vertrag:
    return _Vertrag(
        _MP,
        tarifwerk={"scheiben_mit_gamma1": False, "stoab_je_baustein": je_baustein,
                   "red_verfahren": "mit_abzug"},
        mitgebracht=[(e, m.sum_insured, Rechenkern(m)) for e, m in _SCHEIBEN],
    )


@pytest.mark.parametrize("je_baustein,soll", [
    (True, _VS_SOLL_JE_BAUSTEIN),
    (False, _VS_SOLL_VERTRAGSWEIT),     # Positivkontrolle: die Vorgabe bleibt bitgleich
])
def test_die_herabsetzung_mit_abzug_folgt_dem_tarifwerk_der_generation(je_baustein, soll):
    """Runde D, Fund 1. Mutationsprobe: ``stoab_je_baustein`` in
    ``reduziere_geschichtet`` ignorieren -> der Fall je Baustein ist rot."""
    vs_neu = _vertrag(je_baustein).vorgang(_A0, _F, MIT_ABZUG, None).vs_neu
    assert vs_neu == pytest.approx(soll, abs=0.01)


@pytest.mark.parametrize("je_baustein", [True, False])
def test_umgewandelt_wird_ein_minus_f_mal_der_rueckkaufswert_des_storno(je_baustein):
    """Die Invariante hinter Fund 1, unabhaengig von der Verteilung auf die
    Schichten: die Summe der umgewandelten Teile (dk_nach - f x dk_vor) ist
    (1-f) x RKW, und der RKW ist der, den ein Storno am selben Tag zahlt
    (``_Vertrag.rkw``, vor der Herabsetzung gelesen)."""
    v = _vertrag(je_baustein)
    rkw_storno = v.rkw(_A0)
    erg = v.vorgang(_A0, _F, MIT_ABZUG, None)
    umgewandelt = sum(r.dk_nach - _F * r.dk_vor for _, r in erg.reduktionen)
    assert umgewandelt == pytest.approx((1.0 - _F) * rkw_storno, rel=1e-9)


def test_ein_klemmender_baustein_subventioniert_die_anderen_nicht():
    """Der Rueckkaufswert je Baustein ist die Summe der auf NULL begrenzten
    Baustein-Werte, nicht ``max(0, V^MRV - Summe der Abzuege)``: Eine junge,
    kleine Scheibe, deren Wert unter ihrem Mindestabzug liegt, klemmt bei null.
    Mutationsprobe: in ``reduziere_geschichtet`` den Faktor aus
    ``vx_mrv - stoab`` statt aus ``rkw`` bilden -> rot."""
    klein = dataclasses.replace(
        _MP, x=_MP.x + 5, n=_MP.n - 5, t=_MP.t - 5, sum_insured=0.002 * _S, gamma1=0.0)
    scheiben = _SCHEIBEN + [(5, klein)]

    def vertrag():
        return _Vertrag(
            _MP, tarifwerk={"scheiben_mit_gamma1": False, "stoab_je_baustein": True,
                            "red_verfahren": "mit_abzug"},
            mitgebracht=[(e, m.sum_insured, Rechenkern(m)) for e, m in scheiben])

    v = vertrag()
    bausteine = [Rechenkern(m).monatsreserve(12 * (_A0 - e)) for e, m in [(0, _MP)] + scheiben]
    assert bausteine[-1].vx_mrv < _MP.stoab_min, "Positivkontrolle: der Baustein klemmt"
    rkw_storno = v.rkw(_A0)
    assert rkw_storno > sum(b.vx_mrv for b in bausteine) - sum(
        min(_MP.stoab_max, max(_MP.stoab_min, _MP.stoab_satz * (m.sum_insured - b.drx_bpfl)))
        for b, (_e, m) in zip(bausteine, [(0, _MP)] + scheiben)) + 1e-6
    erg = v.vorgang(_A0, _F, MIT_ABZUG, None)
    umgewandelt = sum(r.dk_nach - _F * r.dk_vor for _, r in erg.reduktionen)
    assert umgewandelt == pytest.approx((1.0 - _F) * rkw_storno, rel=1e-9)


def test_der_fall_unterscheidet_die_beiden_schalter():
    """Positivkontrolle: Ohne Unterschied zwischen je Baustein und
    vertragsweit waeren die Tests oben blind."""
    assert abs(_VS_SOLL_VERTRAGSWEIT - _VS_SOLL_JE_BAUSTEIN) > 50.0
    assert _vertrag(True).rkw(_A0) != pytest.approx(_vertrag(False).rkw(_A0), abs=1.0)


def test_prospektiv_kennt_keinen_abzug_und_der_schalter_aendert_nichts():
    """Beim verlustfreien Verfahren entfaellt die Frage: derselbe Betrag mit
    und ohne Schalter."""
    a = reduzierte_teile(Rechenkern(_MP), [(e, Rechenkern(m)) for e, m in _SCHEIBEN],
                         _A0, _F, PROSPEKTIV, stoab_je_baustein=True)
    b = reduzierte_teile(Rechenkern(_MP), [(e, Rechenkern(m)) for e, m in _SCHEIBEN],
                         _A0, _F, PROSPEKTIV)
    assert [r.reduktion.vs_neu for _, r in a] == [r.reduktion.vs_neu for _, r in b]


def test_reduziere_geschichtet_nimmt_den_schalter_an():
    teile = reduziere_geschichtet(
        Rechenkern(_MP), [(e, Rechenkern(m)) for e, m in _SCHEIBEN], _A0, _F,
        verfahren=MIT_ABZUG, stoab_je_baustein=True)
    assert sum(r.vs_neu for _, r in teile) == pytest.approx(_VS_SOLL_JE_BAUSTEIN, abs=0.01)


def test_p_b1_herleitung_rekonstruiert_denselben_herabgesetzten_vertrag():
    """Der Schalter muss an JEDER Stelle der einen Rekonstruktion ankommen
    (Klasse 'Vertrag verschaerft, Produzent vergessen'): die Herleitung von
    P-B1 haelt die Buchung gegen die Engine. Mutationsprobe: den Schalter in
    ``_Herleitung.setze_vorgaenge`` weglassen -> rot."""
    from rechner_pipeline.bestand.ledger_bindung import _Herleitung

    row = {"entry_age": _MP.x, "sex": _MP.sex, "duration": _MP.n,
           "premium_duration": _MP.t, "sum_insured": _MP.sum_insured,
           "zahlweise": _MP.zw, "police_id": 1}
    felder = {n: getattr(_MP, n) for n in (
        "zins", "tafel", "alpha", "beta1", "gamma1", "gamma2", "gamma3", "policy_fee",
        "min_alter_flex", "min_rlz_flex", "stoab_satz", "stoab_min", "stoab_max")}
    tarifwerk = {"scheiben_mit_gamma1": False, "stoab_je_baustein": True,
                 "red_verfahren": MIT_ABZUG, "tku_umfang": "alle_bausteine"}
    h = _Herleitung(row, felder, [(2, 0.05 * _S), (3, 0.05 * 1.05 * _S)], tarifwerk)
    h.setze_vorgaenge([(_A0, _F, MIT_ABZUG)], None, None)
    # Die Summe NACH dem Vorgang (vor einer Erhoehung desselben Jahrestags).
    assert h.gesamt_vs(_A0, "ERH") == pytest.approx(_VS_SOLL_JE_BAUSTEIN, abs=0.01)


# --------------------------------------------------------------------------- #
# Laeufe fuer die Berichtsfunde (2 und 4): eigenes Geschaeft mit Herabsetzungen
# --------------------------------------------------------------------------- #

import hashlib
import json
import shutil
from pathlib import Path

import pandas as pd

from rechner_pipeline.bestand import cli_fortschreibung as _fs
from rechner_pipeline.bestand import cli_report as _bericht
from rechner_pipeline.bestand.manifest import ROLLEN_DATEIEN
from rechner_pipeline.bestand.parquet_io import read_portfolio, write_portfolio
from tests.test_bestand_uebernommen_fortschreiben import _CONFIG_TOML, _stamm

_POLICEN = list(range(900_001, 900_041))


def _config_text(anteil: float = 0.6, rate: float = 0.10) -> str:
    return _CONFIG_TOML.replace(
        "[annahmen]\nerh_prozent = 0.05",
        f"[annahmen]\nerh_prozent = 0.05\nred_anteil = {anteil}",
    ) + f"\n[annahmen.herabsetzung]\na = {rate}\nb = 0.0\n"


def _lauf(tmp_path: Path, bis: str, config_text: str | None = None) -> tuple[Path, Path]:
    cfg = tmp_path / "cfg.toml"
    cfg.write_text(config_text or _config_text(), encoding="utf-8")
    portfolio = tmp_path / "eigen.parquet"
    write_portfolio(_stamm([{"id": p, "beginn": "2015-01-01"} for p in _POLICEN]), portfolio)
    out = tmp_path / "lauf"
    assert _fs.main(["--config", str(cfg), "--bis", bis, "--portfolio", str(portfolio),
                     "--out-dir", str(out)]) == 0
    return out, cfg


def _unter(tmp_path: Path, name: str) -> Path:
    ziel = tmp_path / name
    ziel.mkdir()
    return ziel


def _sha(pfad: Path) -> str:
    return hashlib.sha256(pfad.read_bytes()).hexdigest()


def _manifest_nachfuehren(out: Path, cfg: Path) -> None:
    """Die Bytes des Laufs neu in das Manifest eintragen — der Angreifer, der
    den Lauf stimmig faelscht (sonst finge schon die Identitaet)."""
    pfad = out / "laufmanifest.json"
    m = json.loads(pfad.read_text(encoding="utf-8"))
    for datei in ROLLEN_DATEIEN.values():
        if (out / datei).is_file():
            m["ausgaben"][datei] = _sha(out / datei)
    m["config"]["sha256"] = _sha(cfg)
    pfad.write_text(json.dumps(m, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
                    encoding="utf-8")


def _red_einfuegen(out: Path, cfg: Path, datum: str) -> int:
    """Eine Herabsetzung (Tabelle + Buchung mit dem Betrag, den die Herleitung
    von P-B1 selbst erwartet) fuer eine aktive, nicht herabgesetzte Police."""
    from rechner_pipeline.bestand.auswertung import grundlagen_je_police
    from rechner_pipeline.bestand.config import load_config
    from rechner_pipeline.bestand.ledger_bindung import _Herleitung

    st = read_portfolio(out / "bestand_gesamt.parquet")
    red = read_portfolio(out / "reduktionen.parquet")
    le = read_portfolio(out / "ledger.parquet")
    kandidaten = [int(p) for p in st[st.status_code == "POL"].police_id
                  if p not in set(red.police_id)
                  and not len(le[(le.police_id == p) & (le.ereignis == "ERH")])]
    pid = kandidaten[0]
    zeile = st.set_index("police_id").loc[pid]
    datum_ts = pd.Timestamp(datum)
    jahr = datum_ts.year - pd.Timestamp(zeile["insurance_start"]).year
    config = load_config(cfg)
    felder = grundlagen_je_police(config, None)(pid, str(zeile["tarif_generation"]))
    h = _Herleitung(zeile.to_dict() | {"police_id": pid}, felder, [],
                    config.generationen[0].tarifwerk())
    h.setze_vorgaenge([(jahr, 0.6, "prospektiv")], None, None)
    neu_red = pd.DataFrame([{"police_id": pid, "reduktion_jahr": jahr,
                             "reduktion_datum": datum_ts, "anteil": 0.6,
                             "verfahren": "prospektiv"}]).astype(red.dtypes.to_dict())
    zeilen = [{"police_id": pid, "tarif_generation": zeile["tarif_generation"],
               "ereignis": "RED", "vertragsjahr": jahr, "status_date": datum_ts,
               "betrag_art": art, "betrag": b, "betrag_herkunft": "gerechnet"}
              for art, b in h.vorgang_buchungen(jahr, "RED").items()]
    red = pd.concat([red, neu_red]).sort_values("police_id").reset_index(drop=True)
    le = pd.concat([le, pd.DataFrame(zeilen).astype(le.dtypes.to_dict())]).sort_values(
        ["police_id", "status_date"], kind="stable").reset_index(drop=True)
    write_portfolio(red, out / "reduktionen.parquet")
    write_portfolio(le, out / "ledger.parquet")
    _manifest_nachfuehren(out, cfg)
    return pid


def _pb1_fehler(out: Path, cfg: Path, bis: _dt.date) -> list:
    from rechner_pipeline.bestand.manifest import lauf_eingaben, lies_manifest
    from rechner_pipeline.bestand.vorbedingungen import lies_und_pruefe_pb1

    _t, _g, fehler, usage = lies_und_pruefe_pb1(
        lauf_eingaben(out, cfg), bis=bis, manifest=lies_manifest(out))
    return fehler + usage


def _bericht_argv(out: Path, cfg: Path, bis: str, ziel: Path) -> list[str]:
    return ["--portfolio", str(out / "bestand_gesamt.parquet"),
            "--historie", str(out / "historie.parquet"),
            "--ledger", str(out / "ledger.parquet"),
            "--scheiben", str(out / "scheiben.parquet"),
            "--config", str(cfg), "--bis", bis, "--out", str(ziel)]


import datetime as _dt  # noqa: E402  (oben im Modul nicht gebraucht)


# --------------------------------------------------------------------------- #
# Fund 2: der Bericht haelt das Laufmanifest wie P-B1
# --------------------------------------------------------------------------- #


def test_der_bericht_rendert_keine_herabsetzung_hinter_dem_belegten_horizont(tmp_path):
    """Runde D, Fund 2. Der Bericht rief P-B1 ohne das Laufmanifest neben dem
    Ledger und damit ohne belegten Horizont: Eine RED hinter dem Laufende
    (stimmiger Betrag, Manifest nachgefuehrt) rendete mit Exit 0, die P-B1
    auf denselben Bytes abweist. Mutationsprobe: ``manifest=`` im Aufruf von
    ``lies_und_pruefe_pb1`` in cli_report weglassen -> rot."""
    out, cfg = _lauf(tmp_path, "2030-01-01")
    ziel = tmp_path / "bericht.html"
    # Positivkontrolle 1: der unveraenderte Lauf rendert.
    assert _bericht.main(_bericht_argv(out, cfg, "2030-01-01", ziel)) == 0
    # Positivkontrolle 2: dieselbe Mutation VOR dem Horizont ist fuer P-B1 und
    # Bericht gleich gruen — der Unterschied liegt allein am Horizont.
    vor, vor_cfg = _lauf(_unter(tmp_path, "vor"), "2030-01-01")
    _red_einfuegen(vor, vor_cfg, "2029-01-01")
    assert _pb1_fehler(vor, vor_cfg, _dt.date(2030, 1, 1)) == []
    assert _bericht.main(_bericht_argv(vor, vor_cfg, "2030-01-01", tmp_path / "vor.html")) == 0
    # Die Mutation hinter dem Horizont.
    hinter, hinter_cfg = _lauf(_unter(tmp_path, "hinter"), "2030-01-01")
    _red_einfuegen(hinter, hinter_cfg, "2031-01-01")
    fehler = _pb1_fehler(hinter, hinter_cfg, _dt.date(2030, 1, 1))
    assert any("Horizont" in f["message"] for f in fehler), fehler[:2]
    assert _bericht.main(_bericht_argv(hinter, hinter_cfg, "2030-01-01", tmp_path / "hinter.html")) != 0
    assert not (tmp_path / "hinter.html").exists()


def test_der_bericht_haelt_die_bytes_gegen_das_manifest(tmp_path, capsys):
    """Dieselbe Identitaet wie P-B1: Eine nachtraeglich veraenderte Datei des
    Laufs (hier die Config, Manifest NICHT nachgefuehrt) rendert nicht —
    ohne das Manifest waere sie ein gueltiger, nur anderer Lauf."""
    out, cfg = _lauf(tmp_path, "2030-01-01")
    assert _bericht.main(_bericht_argv(out, cfg, "2030-01-01", tmp_path / "ok.html")) == 0
    cfg.write_text(cfg.read_text(encoding="utf-8") + "\n# nachtraeglich\n", encoding="utf-8")
    assert _bericht.main(_bericht_argv(out, cfg, "2030-01-01", tmp_path / "x.html")) != 0
    assert "Laufmanifest" in capsys.readouterr().err


def test_ein_lauf_ohne_manifest_bleibt_ohne_belegten_horizont_renderbar(tmp_path):
    """Kein Manifest belegt keinen Horizont (wie in P-B1): Haendisch gebaute
    Verzeichnisse ohne Lieferschein bleiben renderbar."""
    out, cfg = _lauf(tmp_path, "2030-01-01")
    (out / "laufmanifest.json").unlink()
    assert _bericht.main(_bericht_argv(out, cfg, "2030-01-01", tmp_path / "x.html")) == 0


# --------------------------------------------------------------------------- #
# Fund 4: Bericht nur mit Stamm und Config neben herabgesetzten Vertraegen
# --------------------------------------------------------------------------- #


def _lauf_nur_herabsetzungen(tmp_path: Path) -> tuple[Path, Path]:
    """Ein Lauf, in dem es nur Herabsetzungen gibt (kein Zustandswechsel,
    keine Erhoehung): Der Stamm ist sonst ohne Folgezustaende, und allein
    die Nachbardatei reduktionen.parquet unterscheidet ihn vom Stamm eines
    Bestands ohne Herabsetzung."""
    t = _config_text(0.6, 0.3)
    for alt, neu in (("[annahmen.tod]\na = 0.0\nb = 1.0", "[annahmen.tod]\na = 0.0\nb = 0.0"),
                     ("[annahmen.storno]\na = 0.02", "[annahmen.storno]\na = 0.0"),
                     ("[annahmen.beitragsfreistellung]\na = 0.02",
                      "[annahmen.beitragsfreistellung]\na = 0.0"),
                     ("[annahmen.erhoehung]\na = 0.05", "[annahmen.erhoehung]\na = 0.0")):
        assert alt in t, alt
        t = t.replace(alt, neu)
    out, cfg = _lauf(tmp_path, "2019-01-01", t)
    st = read_portfolio(out / "bestand_gesamt.parquet")
    assert set(st.status_id) == {1}, "Welt ohne Zustandswechsel"
    assert len(read_portfolio(out / "reduktionen.parquet")), "Welt mit Herabsetzungen"
    return out, cfg


def test_der_bericht_nur_mit_stamm_weist_einen_herabgesetzten_lauf_ab(tmp_path, capsys):
    """Runde D, Fund 4. Mit ``--portfolio``/``--config`` allein las der Bericht
    ``reduktionen.parquet`` nicht und bewertete herabgesetzte Vertraege
    ungekuerzt, Exit 0. Mutationsprobe: die Abweisung in cli_report entfernen
    -> rot."""
    out, cfg = _lauf_nur_herabsetzungen(tmp_path)
    nur_stamm = ["--portfolio", str(out / "bestand_gesamt.parquet"), "--config", str(cfg),
                 "--stichtage", "2019-01-01"]
    assert _bericht.main(nur_stamm + ["--out", str(tmp_path / "a.html")]) == 2
    err = capsys.readouterr().err
    assert "reduktionen.parquet" in err and "--ledger" in err       # Ausweg genannt
    assert not (tmp_path / "a.html").exists()
    # Auch das ausdrueckliche Flag ohne Lauf wird nicht still ignoriert — der
    # Stamm liegt hier in einem Verzeichnis OHNE reduktionen.parquet.
    woanders = tmp_path / "woanders"
    woanders.mkdir()
    shutil.copy(out / "bestand_gesamt.parquet", woanders / "bestand_gesamt.parquet")
    ohne_nachbar = ["--portfolio", str(woanders / "bestand_gesamt.parquet"), "--config", str(cfg),
                    "--stichtage", "2019-01-01"]
    assert _bericht.main(ohne_nachbar + ["--out", str(tmp_path / "e.html")]) == 0
    assert _bericht.main(ohne_nachbar + ["--reduktionen", str(out / "reduktionen.parquet"),
                                         "--out", str(tmp_path / "b.html")]) == 2


def test_der_bericht_mit_dem_lauf_rendert_den_herabgesetzten_bestand(tmp_path):
    """Positivkontrolle: derselbe Lauf MIT Historie und Ledger rendert (Exit 0),
    und die Weiche liegt allein an den fehlenden Buchungen."""
    out, cfg = _lauf_nur_herabsetzungen(tmp_path)
    assert _bericht.main(_bericht_argv(out, cfg, "2019-01-01", tmp_path / "c.html")) == 0


def test_der_bericht_nur_mit_stamm_bleibt_ohne_herabsetzungen_moeglich(tmp_path):
    """Positivkontrolle: Ein Stamm ohne reduktionen.parquet daneben rendert
    weiter allein (der Bericht ueber einen frischen Bestand)."""
    stamm = _stamm([{"id": p, "beginn": "2015-01-01"} for p in _POLICEN[:5]])
    pfad = tmp_path / "eigen.parquet"
    write_portfolio(stamm, pfad)
    assert _bericht.main(["--portfolio", str(pfad), "--stichtage", "2019-01-01",
                          "--out", str(tmp_path / "d.html")]) == 0


# --------------------------------------------------------------------------- #
# Fund 3: die Fuehrungsprobe haelt jede RED-Zeile gegen das Reduktionsjahr
# --------------------------------------------------------------------------- #

from tests.test_baldrian2_e2e import gefahrener_fall  # noqa: E402,F401
from tests.test_t27_pruefstrecke_runde_c import (  # noqa: E402,F401
    POL,
    ZUGANGSJAHR,
    _mit_red,
    _texte,
    _urteil as _probe_urteil,
    welt,
)
from rechner_pipeline.models.bestand import LEDGER_NAMES, LEDGER_SPALTEN  # noqa: E402


def _red_zeile_in(tab, pid: int, jahr: int, betrag: float) -> dict:
    """Eine Summenzeile der registrierten Herabsetzung bzw. Teilkuendigung
    (RED/VS_herabsetzung oder TKU/VS_teilkuendigung, ADR-023) im Vertragsjahr
    ``jahr`` (Jahrestag), gleiche Form wie die der Engine — nur der Ort ist
    der Fehler."""
    le = tab["ledger"]
    vorlage = le[(le.police_id == pid) & le.ereignis.isin(["RED", "TKU"])
                 & le.betrag_art.isin(["VS_herabsetzung", "VS_teilkuendigung"])].iloc[0]
    datum = pd.Timestamp(vorlage["status_date"]) + pd.DateOffset(years=jahr - int(vorlage["vertragsjahr"]))
    zeile = pd.DataFrame([{
        "police_id": pid, "tarif_generation": vorlage["tarif_generation"],
        "ereignis": vorlage["ereignis"],
        "vertragsjahr": jahr, "status_date": datum, "betrag_art": vorlage["betrag_art"],
        "betrag": float(betrag), "betrag_herkunft": "gerechnet"}])[list(LEDGER_NAMES)].astype(
            dict(LEDGER_SPALTEN))
    ledger = pd.concat([le, zeile], ignore_index=True).sort_values(
        ["police_id", "status_date"], kind="stable").reset_index(drop=True)
    return dict(tab, ledger=ledger, horizont=max(tab["horizont"], datum.date()))


@pytest.mark.parametrize("fremdjahr,betrag", [
    (ZUGANGSJAHR + 1, 100_000.0),     # davor, ungekuerzte Summe
    (ZUGANGSJAHR + 3, None),          # danach, Kopie der registrierten Buchung
])
def test_eine_red_zeile_ausserhalb_des_reduktionsjahres_ist_unbelegt(welt, fremdjahr, betrag):
    """Runde D, Fund 3. Die Probe hielt eine RED-Zeile im falschen Jahr gegen
    das Soll des BUCHUNGSjahres bzw. ungekuerzt und zaehlte sie als geprueft;
    P-B1 weist beide ab ('RED-Buchung(en), die keine registrierte
    Herabsetzung erzeugt'). Soll: unbelegt (bestanden=False), nicht als
    geprueft gezaehlt. Mutationsprobe: die Jahresweiche vor der Nachrechnung
    in pruefe_fuehrung entfernen -> rot."""
    reg = ZUGANGSJAHR + 2
    kontrolle = _mit_red(welt, POL, reg)
    kontrolle = dict(kontrolle, horizont=_dt.date(2029, 1, 1))
    gut = _probe_urteil(welt, kontrolle)
    assert gut["bestanden"], gut["befunde"][:3]                       # Positivkontrolle
    if betrag is None:
        le = kontrolle["ledger"]
        betrag = float(le[(le.police_id == POL) & (le.ereignis == "TKU")
                          & (le.betrag_art == "VS_teilkuendigung")].iloc[0]["betrag"])
    urteil = _probe_urteil(welt, _red_zeile_in(kontrolle, POL, fremdjahr, betrag))
    assert not urteil["bestanden"]
    assert any(f"Vertragsjahr {fremdjahr}" in t and f"im Jahr {reg}" in t
               for t in _texte(urteil, "herabsetzung")), urteil["befunde"][:4]
    assert urteil["buchungen_geprueft"]["TKU"] == gut["buchungen_geprueft"]["TKU"]


def test_p_b1_weist_dieselbe_fremdjahr_zeile_ab(welt):
    """Die Gegenprobe der Gleichheit: P-B1 sagt zu derselben Fremdjahr-Zeile
    dasselbe (keine Probe, die strenger oder laxer ist als die Herleitung)."""
    from rechner_pipeline.bestand.ledger_bindung import pruefe_ledger_betraege

    reg = ZUGANGSJAHR + 2
    tab = _red_zeile_in(dict(_mit_red(welt, POL, reg), horizont=_dt.date(2029, 1, 1)),
                        POL, ZUGANGSJAHR + 1, 100_000.0)
    ueb = welt["ueb"]
    stamm = ueb["bestand"]
    gesamt = pd.concat([ueb["ledger"], tab["ledger"][
        pd.to_datetime(tab["ledger"]["status_date"]) > pd.Timestamp("2026-01-01")]],
        ignore_index=True)
    fehler = pruefe_ledger_betraege(
        stamm, gesamt, welt["config"], scheiben=pd.concat(
            [ueb["scheiben"], tab["scheiben"]]).drop_duplicates(),
        historie=tab["historie"], schichten=ueb["schichten"],
        verankerung=ueb["verankerung"], reduktionen=tab["reduktionen"],
        merkmale=ueb["merkmale"])
    assert any("keine registrierte Herabsetzung" in f for f in fehler), fehler[:3]


def test_die_bewertung_reicht_den_schalter_je_police_an_die_rekonstruktion():
    """Fund 1 an der Naht der Bewertung (``_vorgangsfolgen``): dieselbe
    Summe wie die Engine, je nach Schalter der Generation der Police.
    Mutationsprobe: den Schalter in ``_vorgangsfolgen`` nicht
    weiterreichen -> rot."""
    from rechner_pipeline.bestand.auswertung import _vorgangsfolgen

    red = pd.DataFrame([{"police_id": 1, "reduktion_jahr": _A0, "anteil": _F,
                         "verfahren": MIT_ABZUG}])
    scheiben = {1: [{"erh_jahr": e, "kern": Rechenkern(m)} for e, m in _SCHEIBEN]}
    for je_baustein, soll in ((True, _VS_SOLL_JE_BAUSTEIN), (False, _VS_SOLL_VERTRAGSWEIT)):
        folgen = _vorgangsfolgen(red, {1: Rechenkern(_MP)}, scheiben, {}, {1: {
            "stoab_je_baustein": je_baustein, "tku_umfang": "alle_bausteine"}})
        assert folgen[1].stand_am(12 * _A0).gesamt_vs() == pytest.approx(soll, abs=0.01)


def test_eine_red_zeile_ohne_registrierte_herabsetzung_wird_nicht_gezaehlt(welt):
    """Fund 3, die Police ohne Tabellenzeile: Zwei RED-Jahre, keine Zeile in
    reduktionen.parquet. Die spaetere Zeile meldete der Befund 'ohne Zeile';
    die FRUEHERE fiel in den Zweig des ungekuerzten Vertrags und zaehlte als
    geprueft. Mutationsprobe: die Weiche fuer fehlende Registrierung entfernen
    -> rot (TypeError beim Jahresvergleich)."""
    grundlinie = _probe_urteil(welt, welt["tab"])["buchungen_geprueft"]["TKU"]
    tab = _mit_red(welt, POL, ZUGANGSJAHR + 2)
    tab = _red_zeile_in(dict(tab, horizont=_dt.date(2029, 1, 1)), POL, ZUGANGSJAHR + 1, 100_000.0)
    tab = dict(tab, reduktionen=welt["tab"]["reduktionen"])
    urteil = _probe_urteil(welt, tab)
    assert not urteil["bestanden"]
    assert any("ohne Zeile in reduktionen.parquet" in t for t in _texte(urteil, "herabsetzung"))
    assert urteil["buchungen_geprueft"]["TKU"] == grundlinie
