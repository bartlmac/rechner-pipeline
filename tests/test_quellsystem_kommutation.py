"""Quellsystem-Basiskalkulation gegen den Excel-Golden-Master.

Das Quellsystem rechnet mit einer EINGEFRORENEN Kopie des
Kommutationskerns (VBA-treu: gerundete l_x-Kette, Excel-Rundung). Der
Golden Master der Basiskalkulation sind die Ergebnisse des
Quell-Tarifrechners selbst: simulation/baldrian/excel_ergebnis_*.csv,
717 Vertragszeilen mit Barwerten je Verlaufsjahr. Diese Tests halten
zwei Dinge:

1. Die Kopie trifft Excel — Erlebens-/Todesfall-Barwert (Axn_B) und
   die Rentenbarwerte (axn_C, axt_D) je Zeile, auf < 1e-11 relativ.
   Bitgleichheit ist NICHT der Massstab (reine Float-Kettenreihenfolge
   zwischen VBA und Python); der abgenommene Vergleichsmassstab der
   Migration sind ohnehin die Testtoleranzen, und 1e-11 liegt
   Groessenordnungen darunter.
2. Die harte Paketregel: KEIN Import aus rechner_pipeline. Die
   Unabhaengigkeit der Rechenwege — Kommutation hier, Thiele im Ziel —
   ist der Wert der Vorfuehrung; ein einziger Import zerstoerte sie
   still.

Die Tests laufen nur, wo die Regie-Dateien liegen (simulation/ ist
gitignored): auf einer frischen Klon-Umgebung ohne Regie wird uebersprungen,
nicht gruen gelogen.

Knoten: klv
"""

from __future__ import annotations

import csv
import sys
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO_ROOT))

from quellsystem.barwerte import Barwerte  # noqa: E402
from quellsystem.kommutation import fuer  # noqa: E402

GOLDEN = (
    REPO_ROOT / "simulation" / "baldrian" / "excel_ergebnis_k2.csv",
    REPO_ROOT / "simulation" / "baldrian" / "excel_ergebnis_at.csv",
)

#: Tarifzellen-Tafel der TG2015: unisex, nach Raucherstatus.
TAFEL = {"Nichtraucher": "DAV2008_T_NR_U70", "Raucher": "DAV2008_T_R_U70"}
ZINS = 0.0125


def _zeilen():
    aus = []
    for pfad in GOLDEN:
        if not pfad.is_file():
            return None
        with pfad.open(encoding="utf-8") as datei:
            aus.extend(list(csv.DictReader(datei, delimiter=";")))
    return aus


def test_die_kopie_trifft_den_excel_tarifrechner():
    zeilen = _zeilen()
    if zeilen is None:
        pytest.skip("Regie-Dateien (simulation/baldrian) nicht vorhanden")
    assert len(zeilen) > 700, "der Golden Master ist der volle Bestand"

    geprueft = 0
    for z in zeilen:
        x, n, t, k = int(z["x"]), int(z["n"]), int(z["t"]), int(z["k"])
        b = Barwerte(fuer("M", TAFEL[z["Status"]], ZINS), ZINS)
        alter, restn, restt = x + k, n - k, max(t - k, 0)

        assert b.endowment_benefit_pv(alter, restn) == pytest.approx(
            float(z["Axn_B"]), rel=1e-11, abs=1e-11
        ), f"Zeile {z['TestNr']} ({z['Status']}/{z['Tarifart']}): Axn_B"
        assert b.axn_k(alter, restn, 1) == pytest.approx(
            float(z["axn_C"]), rel=1e-11, abs=1e-11
        ), f"Zeile {z['TestNr']}: axn_C"
        axt = b.axn_k(alter, restt, 1) if restt > 0 else 0.0
        assert axt == pytest.approx(
            float(z["axt_D"]), rel=1e-11, abs=1e-11
        ), f"Zeile {z['TestNr']}: axt_D"
        geprueft += 1
    assert geprueft == len(zeilen)


def test_kein_import_aus_rechner_pipeline():
    """Die eine harte Regel des Pakets, maschinell gehalten.

    Ein Import aus rechner_pipeline liesse Zielsystem-Aenderungen still
    in die Quelle durchsickern — und die Migration pruefte am Ende die
    eigene Arithmetik gegen sich selbst.
    """
    quell = REPO_ROOT / "quellsystem"
    treffer = [
        f"{pfad.name}:{nr}: {zeile.strip()}"
        for pfad in sorted(quell.glob("*.py"))
        for nr, zeile in enumerate(pfad.read_text("utf-8").splitlines(), 1)
        if "rechner_pipeline" in zeile
        and (zeile.strip().startswith("import ")
             or zeile.strip().startswith("from "))
    ]
    assert treffer == [], (
        "quellsystem importiert aus rechner_pipeline: " + "; ".join(treffer)
    )


def test_die_tafelkopie_ist_eigenstaendig_ladbar():
    """Fail-fast wie das Original: unbekannte Tafel wird abgelehnt."""
    from quellsystem.tafeln import MissingMortalityTableError, qx_vector

    assert len(qx_vector("M", "DAV2008_T_NR_U70")) == 124
    with pytest.raises(MissingMortalityTableError):
        qx_vector("M", "GIBTS_NICHT")
