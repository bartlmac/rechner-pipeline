"""Eine Loeschung braucht eine feststehende Lebenszyklus-Identitaet.

Nicht einen plausiblen Namen, nicht eine plausible Form. Diese Klasse hat
im Betrieb dreimal zugeschlagen, jedes Mal mit demselben Muster: Ein
Aufraeumer schliesst aus der GESTALT eines Pfades auf seinen Zustand und
loescht etwas Gueltiges.

* T24-01/T24-07 — ``stand`` war ein haengender Symlink, also galt jedes
  ``stand-*`` als Waise; aufgeraeumt wurde der einzige Stand der Ablage.
* T26-01 — ``fall.neu`` sah aus wie der Arbeitsrest eines Anlegens von
  ``fall``. Es war der regulaer registrierte Eingang eines Falls, der
  zufaellig so heisst; geloescht wurden auch schreibgeschuetzte Dateien.
* T26-02 Szenario 2 — ``stand`` war ein echtes Verzeichnis (Legacy),
  damit war wieder alles Waise; verschwunden ist ``stand-erstfassung``,
  der letzte belegte alte Stand.

Die Tests hier pruefen deshalb nicht die drei gemeldeten Faelle, sondern
die Klasse: eine Menge von Namens- und Zustandspaaren, darunter die
gemeldeten. Und jeder Negativfall hat seine Positivkontrolle — eine
Aufraeumung, die NIE etwas loescht, waere genauso kaputt und saehe hier
gruen aus.

Knoten: klv, bu
"""

from __future__ import annotations

import datetime as dt
import os
from pathlib import Path

import pytest

from rechner_pipeline.betrieb import tageslauf as tl
from rechner_pipeline.betrieb import uebernahme as ueb
from rechner_pipeline.betrieb._loeschen import LoeschFehler, entferne_verzeichnis
from rechner_pipeline.betrieb.tageslauf import STAND_DIR, Ablage
from rechner_pipeline.betrieb.uebernahme import (
    EINGANG_DATEI, STAGING_DIR, UEBERNAHME_DIR,
)

from tests.test_betrieb_uebernahme import STICHTAG, _fall


# --------------------------------------------------------------------------- #
# T26-01 — der Namensraum des Anlegens und der der Eingaenge
# --------------------------------------------------------------------------- #

#: Namenspaare, bei denen der zweite Eingang den ersten frueher geloescht
#: haette. Die ersten beiden sind der gemeldete Fall in beiden
#: Reihenfolgen, dann zwei Staffelungen, dann ein Paar, das den Namen der
#: Staging-Wurzel selbst benutzt. Zuletzt ein unbeteiligtes Paar als
#: Kontrolle, damit der Test nicht nur Sonderfaelle kennt.
NAMENSPAARE = [
    ("fall.neu", "fall"),
    ("fall", "fall.neu"),
    ("a.neu.neu", "a.neu"),
    ("a.neu", "a.neu.neu"),
    (STAGING_DIR, UEBERNAHME_DIR),
    ("erster", "zweiter"),
]


@pytest.mark.parametrize("erst,zweit", NAMENSPAARE)
def test_ein_neuer_eingang_loescht_keinen_fremden(tmp_path, erst, zweit):
    """Zwei regulaere Registrierungen, keine Manipulation — und beide
    Eingaenge stehen danach vollstaendig da.

    Frueher entstand der Eingang als ``<name>.neu`` NEBEN seinem Ziel, im
    selben Verzeichnis; das Suffix war die einzige Unterscheidung zwischen
    Arbeitsrest und Eingang.
    """
    stand = tmp_path / "daten"
    ziel_erst = ueb.eingang_anlegen(stand, _fall(tmp_path, erst), STICHTAG)
    inhalt_vorher = sorted(p.name for p in ziel_erst.iterdir())
    assert EINGANG_DATEI in inhalt_vorher

    ziel_zweit = ueb.eingang_anlegen(stand, _fall(tmp_path, zweit), STICHTAG)

    assert ziel_erst.is_dir(), f"{erst} wurde beim Anlegen von {zweit} geloescht"
    assert sorted(p.name for p in ziel_erst.iterdir()) == inhalt_vorher
    assert ziel_zweit.is_dir() and ziel_erst != ziel_zweit


def test_die_beiden_wurzeln_koennen_sich_nicht_ueberschneiden():
    """Die Ratsche zur Klasse: getrennte Wurzeln statt einer Namensregel.

    Solange Anlegen und Eingang dieselbe Wurzel teilen, ist jede Regel,
    die sie auseinanderhaelt, eine Konvention ueber Namen — und ein
    Fallname ist frei. Zwei Wurzeln machen die Ueberschneidung unmoeglich.
    """
    assert STAGING_DIR != UEBERNAHME_DIR
    wurzel = Path("/beliebig")
    for name in [n for paar in NAMENSPAARE for n in paar] + ["", ".", "..", "x" * 200]:
        assert (wurzel / STAGING_DIR / name) != (wurzel / UEBERNAHME_DIR / name)
        # Und kein Fallname fuehrt aus der einen Wurzel in die andere:
        assert (wurzel / UEBERNAHME_DIR) not in (wurzel / STAGING_DIR / name).parents


# --------------------------------------------------------------------------- #
# T26-15 — was der Leser sieht
# --------------------------------------------------------------------------- #

def test_ein_abgebrochenes_anlegen_blockiert_den_leser_nicht(tmp_path, monkeypatch):
    """Ein Rest des Anlegens ist kein Pflichtinput.

    Frueher las ``lies_uebernahmen`` unterschiedslos JEDES Verzeichnis
    unter ``uebernahme/`` und verlangte von jedem eine ``eingang.json``.
    Ein abgebrochenes Anlegen machte damit den Tagesbetrieb dauerhaft rot,
    und nur ein erneut gestarteter Eingangsschreiber raeumte ihn weg.
    """
    from rechner_pipeline.bestand.config import load_config

    from tests.test_betrieb_uebernahme import _kleine_config

    stand = tmp_path / "daten"
    gut = ueb.eingang_anlegen(stand, _fall(tmp_path, "gut"), STICHTAG)

    aufrufe = {"n": 0}
    echt = ueb.write_portfolio

    def _bricht(tabelle, pfad, *a, **k):
        # Beim SCHREIBEN abbrechen: Seit der Eingang seine Tabellen an den
        # Beleggraphen bindet (T26-03), wird schon vor dem Anlegen
        # gehasht — ein Zaehler auf sha256_bytes traefe eine Stelle ohne
        # Arbeitsverzeichnis.
        aufrufe["n"] += 1
        if aufrufe["n"] == 2:
            raise OSError("Platte weg")
        return echt(tabelle, pfad, *a, **k)

    monkeypatch.setattr(ueb, "write_portfolio", _bricht)
    with pytest.raises(OSError):
        ueb.eingang_anlegen(stand, _fall(tmp_path, "abgebrochen"), STICHTAG)
    monkeypatch.undo()

    rest = stand / STAGING_DIR / "abgebrochen"
    assert rest.is_dir(), "der Rest soll liegen bleiben — er ist die Spur des Abbruchs"
    assert (stand / UEBERNAHME_DIR / "abgebrochen").exists() is False

    cfg_pfad = tmp_path / "bestand.toml"
    cfg_pfad.write_text(_kleine_config(), encoding="utf-8")
    config = load_config(cfg_pfad)
    gelesen = ueb.lies_uebernahmen(stand / UEBERNAHME_DIR, config)
    assert [u.verzeichnis for u in gelesen] == [gut]


# --------------------------------------------------------------------------- #
# Das Werkzeug selbst: beide Richtungen des Markers
# --------------------------------------------------------------------------- #

def _verzeichnis(wurzel: Path, name: str, *, marker: str | None = None) -> Path:
    pfad = wurzel / name
    pfad.mkdir(parents=True)
    (pfad / "inhalt.txt").write_text("x", encoding="utf-8")
    if marker:
        (pfad / marker).write_text("{}", encoding="utf-8")
    return pfad


def test_ohne_marker_verweigert_veroeffentlichtes(tmp_path):
    """``ohne_marker`` sperrt, wenn die Datei da ist — und nur dann.

    Mutationsprobe in beide Richtungen: Eine Regel, die immer sperrt,
    waere genauso falsch wie eine, die nie sperrt, und beide saehen in
    einem Test mit nur einer Richtung gleich aus.
    """
    veroeffentlicht = _verzeichnis(tmp_path, "publiziert", marker=EINGANG_DATEI)
    with pytest.raises(LoeschFehler, match=EINGANG_DATEI):
        entferne_verzeichnis(veroeffentlicht, innerhalb=tmp_path,
                             ohne_marker=EINGANG_DATEI, grund="Probe")
    assert veroeffentlicht.is_dir() and (veroeffentlicht / "inhalt.txt").is_file()

    rest = _verzeichnis(tmp_path, "arbeitsrest")
    entferne_verzeichnis(rest, innerhalb=tmp_path,
                         ohne_marker=EINGANG_DATEI, grund="Probe")
    assert not rest.exists(), "ohne Marker muss geloescht werden, sonst sperrt die Regel alles"


def test_ein_haengender_marker_zaehlt_als_veroeffentlicht(tmp_path):
    """Ein Symlink ins Leere ist ``exists() == False``.

    Er saehe aus wie ein Verzeichnis ohne Marker — und genau in diese
    Richtung darf der Zweifel nicht ausschlagen.
    """
    rest = _verzeichnis(tmp_path, "mit-haengendem-marker")
    os.symlink(tmp_path / "gibt-es-nicht", rest / EINGANG_DATEI)
    with pytest.raises(LoeschFehler, match=EINGANG_DATEI):
        entferne_verzeichnis(rest, innerhalb=tmp_path,
                             ohne_marker=EINGANG_DATEI, grund="Probe")
    assert rest.is_dir()


# --------------------------------------------------------------------------- #
# T26-02 Szenario 2 — die Praemisse der Aufraeumung
# --------------------------------------------------------------------------- #

def _ablage_mit_waise(tmp_path: Path, zustand: str) -> tuple[Ablage, Path]:
    """Eine Ablage mit einem versionierten Stand und ``stand`` im
    angegebenen Zustand."""
    ablage = Ablage(tmp_path / "daten")
    ablage.wurzel.mkdir(parents=True)
    waise = ablage.wurzel / f"{STAND_DIR}-erstfassung"
    waise.mkdir()
    (waise / "bestand_gesamt.parquet").write_text("belegt", encoding="utf-8")
    if zustand == "symlink":
        gefuehrt = ablage.wurzel / f"{STAND_DIR}-gefuehrt"
        gefuehrt.mkdir()
        os.symlink(gefuehrt.name, ablage.stand)
    elif zustand == "verzeichnis":
        ablage.stand.mkdir()
        (ablage.stand / "bestand_gesamt.parquet").write_text("legacy", encoding="utf-8")
    elif zustand == "fehlt":
        pass
    elif zustand == "datei":
        ablage.stand.write_text("kein Verzeichnis", encoding="utf-8")
    else:  # pragma: no cover
        raise AssertionError(zustand)
    return ablage, waise


@pytest.mark.parametrize("zustand", ["verzeichnis", "fehlt", "datei"])
def test_ohne_klare_praemisse_wird_nichts_aufgeraeumt(tmp_path, zustand, capsys):
    """Kein Symlink, kein Aufraeumen.

    ``verzeichnis`` ist der gemeldete Legacy-Fall (T26-02), ``fehlt`` der
    aeltere aus T24-01, ``datei`` ein nie beobachteter Zustand derselben
    Bauart — er ist mitgeprueft, weil eine Aufzaehlung der BEKANNTEN
    Ausnahmen genau so den zweiten Fall durchgelassen hat.
    """
    ablage, waise = _ablage_mit_waise(tmp_path, zustand)
    tl._verwaiste_staende_entfernen(ablage)
    assert waise.is_dir(), f"{zustand}: der belegte Stand wurde geloescht"
    assert (waise / "bestand_gesamt.parquet").is_file()
    assert "nichts" in capsys.readouterr().err


def test_mit_klarer_praemisse_wird_aufgeraeumt(tmp_path):
    """Positivkontrolle. Ohne sie waere eine Aufraeumung, die NIE etwas
    entfernt, von einer richtigen nicht zu unterscheiden."""
    ablage, waise = _ablage_mit_waise(tmp_path, "symlink")
    tl._verwaiste_staende_entfernen(ablage)
    assert not waise.exists(), "die echte Waise muss verschwinden"
    assert ablage.stand.resolve().is_dir(), "der gefuehrte Stand bleibt"
