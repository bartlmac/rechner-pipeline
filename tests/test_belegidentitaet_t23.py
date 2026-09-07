"""Belegidentitaet ueber alle Gates (Review T23-01): Eine Datei, deren Hash
im Beleg steht, wird GENAU EINMAL gelesen.

Der Reviewer fand in P-Q3, P-K1 und A-K1 die Read/Hash-Naht aus T18-03 an
neuer Stelle: Die Datei wurde einmal zum Hashen und ein zweites Mal zum
Parsen gelesen; der protokollierte Hash bezeugt dann irgendeinen Zustand
der Datei, nicht den geprueften. Die Mustersuche fand dieselbe Klasse in
abox_merge, Abnahmebericht, Aktuartest, verankerung_belegen, im GM-Loader
und im P9-Gate selbst.

Dieser Test flickt nicht das Reviewer-Beispiel, sondern prueft die
KLASSE, indem er die Gates tatsaechlich fahren laesst: ``Path.open`` wird
zum Zaehlpunkt (``read_text``/``read_bytes`` laufen in CPython darueber,
``file_sha256`` oeffnet ``rb``), Schreibmodi zaehlen nicht. Nach dem Lauf
darf keine Datei, die zweimal gelesen wurde, mit ihrem Hash im Beleg
stehen — vor der Korrektur war genau das bei abox.json, eingang.json,
Spez, Names-Manager, Erwartungswerten, Fragmenten, Suite, Spec,
P-B1-Ledger, Testergebnis und den P9-Pflichtbelegen der Fall.

Zwei bewusste Ausnahmen der Zusicherung: Dateien, die das Gate in diesem
Lauf selbst SCHREIBT, sind Ausgaben — ihr Hash nach dem Schreiben ist ein
Ausgabe-Hash, keine Eingabe-Identitaet (der Aktuartest-Bericht wird fuer
Beleg, Ausgabe-Hash und Determinismus mehrfach gelesen). Und Dateien
unter ``src/`` sind Quellcode (``kern/tafeln.xml``): der Kern liest sie
ueber seinen eigenen Kanal, und der Systemstand (``quellcode_sha256``)
bindet sie — die benannte Reichweitengrenze aus ``generation_golden``.

Reichweite, ehrlich benannt: ``fall.json`` liest der gehaertete Leser ueber
``os.open`` (nicht ueber ``Path.open``) — seine Einmal-Lesung
(``fall.lade_scope_gehasht``) ist hier unsichtbar; ``verankerung_belegen``
braucht Parquet-Tabellen und Erwartungswerte und wird nicht gefahren.
Beide sind durch die Konventions-Ratsche (test_konvention_belegidentitaet)
und die Umstellung selbst abgedeckt.

Knoten: system/assurance
"""

from __future__ import annotations

import hashlib
import json
from collections import Counter
from pathlib import Path
from typing import Callable, Dict, Iterable, List

import pytest

from rechner_pipeline.gates import abnahmebericht, abox_merge, abox_validate
from rechner_pipeline.gates import aktuartest, gate_entscheid, generation_golden
from tests.e2e_fixture import bereite_pk1_fall
from tests.test_abnahmebericht import _basis_argv, _pruefung, _suite_datei
from tests.test_aktuartest_gate import _fall as _aktuartest_fall
from tests.test_aktuartest_gate import _testergebnis
from tests.test_kette_und_vorbedingungen import AKTEUR, _fragment_json
from tests.test_tbox_version_ak1 import _beleg as _tbox_beleg
from tests.zeichnung_fixture import annahme_args

REPO_ROOT = Path(__file__).resolve().parents[1]


# --------------------------------------------------------------------------- #
# Zaehlpunkt: jede LESENDE Oeffnung einer Datei, je aufgeloestem Pfad
# --------------------------------------------------------------------------- #

def _zaehle_lesungen(monkeypatch) -> tuple:
    """Lesende Oeffnungen je Pfad zaehlen und geschriebene Pfade merken."""
    zaehler: Counter = Counter()
    geschrieben: set = set()
    original = Path.open

    def gezaehlt(self, mode="r", *args, **kwargs):
        try:
            pfad = self.resolve()
        except OSError:
            pfad = None
        if pfad is not None:
            if any(c in str(mode) for c in "wax+"):
                geschrieben.add(pfad)
            else:
                zaehler[pfad] += 1
        return original(self, mode, *args, **kwargs)

    monkeypatch.setattr(Path, "open", gezaehlt)
    return zaehler, geschrieben


def _sha(pfad: Path) -> str:
    return hashlib.sha256(pfad.read_bytes()).hexdigest()


def _belegte_hashes(ergebnis) -> set:
    """Alle Hashes, die das Gate als Beleg protokolliert: input_hashes und
    die Beleg-Hashes der Zusammenfassung (fragment_hashes, belege,
    pflichtbelege)."""
    hashes = set((ergebnis.input_hashes or {}).values())
    summary = ergebnis.summary or {}
    for schluessel in ("fragment_hashes", "belege"):
        wert = summary.get(schluessel)
        if isinstance(wert, dict):
            hashes.update(v for v in wert.values() if isinstance(v, str))
    pflicht = summary.get("pflichtbelege")
    if isinstance(pflicht, dict):
        for liste in pflicht.values():
            if isinstance(liste, list):
                hashes.update(h for h in liste if isinstance(h, str))
    return hashes


QUELLCODE = (REPO_ROOT / "src").resolve()


def _ist_eingabe(pfad: Path, geschrieben: set) -> bool:
    """Weder eine in diesem Lauf geschriebene Ausgabe noch Quellcode."""
    if pfad in geschrieben:
        return False
    try:
        pfad.relative_to(QUELLCODE)
        return False
    except ValueError:
        return True


def _pruefe_belegidentitaet(
    zaehler: Counter, geschrieben: set, ergebnis, *, mindestens: int = 1,
):
    # Stand der Zaehlung EINFRIEREN, bevor die Verifikation selbst liest —
    # sonst zaehlt der eigene _sha-Aufruf mit.
    stand = dict(zaehler)
    belegt = _belegte_hashes(ergebnis)
    assert belegt, "das Gate protokolliert keine Beleg-Hashes — Test greift ins Leere"
    doppelt = sorted(
        p for p, n in stand.items()
        if n >= 2 and p.is_file() and _ist_eingabe(p, geschrieben)
    )
    verletzt = [
        (p, stand[p]) for p in doppelt if _sha(p) in belegt
    ]
    assert not verletzt, (
        "Beleg-Hash aus einer anderen Lesung als die Verarbeitung: "
        + "; ".join(f"{p.name} {n}x gelesen" for p, n in verletzt)
    )
    einmal = [p for p, n in stand.items() if n == 1 and p.is_file() and _sha(p) in belegt]
    assert len(einmal) >= mindestens, (
        f"erwartet mindestens {mindestens} belegte Datei(en) mit genau einer "
        f"Lesung, gefunden {len(einmal)} — der Zaehlpunkt sieht das Gate nicht"
    )


# --------------------------------------------------------------------------- #
# Fixtures: der P-K1-Fall traegt P-Q3, P-K1 und A-K1; Fragmente fuer den Merge
# --------------------------------------------------------------------------- #

@pytest.fixture()
def pk1_fall(tmp_path: Path) -> Path:
    return bereite_pk1_fall(tmp_path, ("klv/tg2012",), scope="tarif")


def _merge_fall(tmp_path: Path) -> Path:
    from rechner_pipeline.fall import anlegen, registrieren
    from rechner_pipeline.ontologie.kette import fragmente_ordner

    fall = tmp_path / "fall"
    anlegen(fall)
    for name in ("rechner.xlsm", "meldung.docx"):
        quelle = tmp_path / name
        quelle.write_bytes(name.encode())
        registrieren(fall, quelle)
    ordner = fragmente_ordner(fall)
    ordner.mkdir(parents=True)
    (ordner / "tg2012-meldung.json").write_text(json.dumps(
        _fragment_json("meldung.docx", "tarifmeldung", beta1=0.025)),
        encoding="utf-8")
    (ordner / "tg2012-rechner.json").write_text(json.dumps(
        _fragment_json("rechner.xlsm", "tarifrechner", beta1=0.03)),
        encoding="utf-8")
    (ordner / "akteure.json").write_text(json.dumps({
        "tg2012-meldung.json": AKTEUR,
        "tg2012-rechner.json": AKTEUR.replace("quellfragment", "quellfragment-b"),
    }), encoding="utf-8")
    return fall


# --------------------------------------------------------------------------- #
# Die Klasse, Gate fuer Gate — derselbe Zaehlpunkt, dieselbe Zusicherung
# --------------------------------------------------------------------------- #

def test_pq3_liest_abox_und_eingang_genau_einmal(pk1_fall, monkeypatch):
    zaehler, geschrieben = _zaehle_lesungen(monkeypatch)
    ergebnis = abox_validate.main(
        ["--fall", str(pk1_fall), "--repo-root", str(REPO_ROOT)])
    assert ergebnis.exit_code == 0, ergebnis.errors
    _pruefe_belegidentitaet(zaehler, geschrieben, ergebnis, mindestens=2)


def test_pk1_liest_spez_names_und_erwartungswerte_genau_einmal(pk1_fall, monkeypatch):
    assert abox_validate.main(
        ["--fall", str(pk1_fall), "--repo-root", str(REPO_ROOT)]).exit_code == 0
    zaehler, geschrieben = _zaehle_lesungen(monkeypatch)
    ergebnis = generation_golden.main([
        "--fall", str(pk1_fall), "--generation", "klv/tg2012",
        "--repo-root", str(REPO_ROOT),
        "--diagnostics-dir", str(pk1_fall / "abgeleitet" / "diagnostics"),
    ])
    assert ergebnis.exit_code == 0, ergebnis.errors
    _pruefe_belegidentitaet(zaehler, geschrieben, ergebnis, mindestens=3)


def test_abox_merge_liest_fragmente_und_register_genau_einmal(tmp_path, monkeypatch):
    fall = _merge_fall(tmp_path)
    zaehler, geschrieben = _zaehle_lesungen(monkeypatch)
    ergebnis = abox_merge.main(["--fall", str(fall), "--repo-root", str(REPO_ROOT)])
    assert ergebnis.exit_code == 0, ergebnis.errors
    _pruefe_belegidentitaet(zaehler, geschrieben, ergebnis, mindestens=3)


def test_ak1_liest_seine_pflichtbelege_genau_einmal(pk1_fall, monkeypatch):
    assert abox_validate.main(
        ["--fall", str(pk1_fall), "--repo-root", str(REPO_ROOT)]).exit_code == 0
    _tbox_beleg(pk1_fall)
    zaehler, geschrieben = _zaehle_lesungen(monkeypatch)
    ergebnis = gate_entscheid.main([
        "--fall", str(pk1_fall), "--gate", "A-K1", "--entscheid", "angenommen",
        "--entscheider", "IT-Verantwortung", "--begruendung", "T-Box erweitert",
        "--repo-root", str(REPO_ROOT), *annahme_args(pk1_fall),
    ])
    assert ergebnis.exit_code == 0, ergebnis.errors
    _pruefe_belegidentitaet(zaehler, geschrieben, ergebnis, mindestens=3)


def test_aktuartest_liest_das_testergebnis_genau_einmal(tmp_path, monkeypatch):
    fall = _aktuartest_fall(tmp_path, _testergebnis())
    zaehler, geschrieben = _zaehle_lesungen(monkeypatch)
    ergebnis = aktuartest.main([
        "--fall", str(fall), "--abnahme", "A-M1", "--titel", "Stichtagstest",
        "--repo-root", str(REPO_ROOT),
    ])
    assert ergebnis.exit_code == 0, ergebnis.errors
    _pruefe_belegidentitaet(zaehler, geschrieben, ergebnis, mindestens=1)


def test_abnahmebericht_liest_suite_spec_und_ergebnis_genau_einmal(tmp_path, monkeypatch):
    # Suite plus die vier Pflichtartefakte, wie die Abnahmebericht-Tests
    # den falllosen CLI-Lauf aufsetzen.
    argv = _basis_argv(tmp_path, _suite_datei(tmp_path, _pruefung("P-1")))
    zaehler, geschrieben = _zaehle_lesungen(monkeypatch)
    ergebnis = abnahmebericht.main(argv)
    # Das Verdikt ist hier nicht die Frage — die Belegidentitaet gilt fuer
    # jeden Lauf, der seine Pflichteingaben gelesen und protokolliert hat.
    _pruefe_belegidentitaet(zaehler, geschrieben, ergebnis, mindestens=3)


def test_pq3_mit_fragmenten_liest_eingang_und_fragmente_genau_einmal(tmp_path, monkeypatch):
    """Der Fragmente-Pfad von P-Q3: pruefe_kette rechnet den Merge nach und
    braucht Register und A-Box — beides kommt aus den bereits gehashten
    Bytes, nicht aus einer zweiten Lesung (Review-Nachtrag zu Block 1)."""
    fall = _merge_fall(tmp_path)
    assert abox_merge.main(
        ["--fall", str(fall), "--repo-root", str(REPO_ROOT)]).exit_code == 0
    zaehler, geschrieben = _zaehle_lesungen(monkeypatch)
    ergebnis = abox_validate.main(
        ["--fall", str(fall), "--repo-root", str(REPO_ROOT)])
    # Das Verdikt (offene Diskrepanz) ist nicht die Frage — die
    # Belegidentitaet gilt fuer jeden Lauf, der Register und A-Box gelesen,
    # gehasht und die Kette nachgerechnet hat.
    _pruefe_belegidentitaet(zaehler, geschrieben, ergebnis, mindestens=2)
