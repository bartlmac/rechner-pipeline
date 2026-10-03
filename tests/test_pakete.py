"""pakete/: jeder festgehaltene Fall ist ein Paket, das seinen Pruefsummen entspricht.

Ein Paket ist die Eingabe des deterministischen Nachfahrens
(deploy/welt/fall_nachfahren.sh). Das Skript faehrt nur ein Paket, das
seinen Pruefsummen entspricht und keine Datei darueber hinaus traegt. Liegt
ein Paket im Repository, gilt dieselbe Bedingung schon fuer den Baum —
sonst faellt eine verletzte Datei erst auf, wenn jemand den Fall nachfaehrt,
und das dauert vierzig Minuten.

Geprueft wird Mechanik: Pflichtdateien, Pruefsummen, keine fremde Datei.
Ob der Commit unter STAND in der Geschichte liegt, prueft dieser Test NICHT:
Die CI holt nur den letzten Commit; das prueft das Nachfahren selbst.

Knoten: klv
"""

from __future__ import annotations

import hashlib
import shutil
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
PAKETE = REPO / "pakete"
PFLICHT = ("fall.conf", "rezept.sh", "ERWARTUNG", "STAND", "SHA256SUMS")


def _befunde(paket: Path) -> list[str]:
    befunde = [f"{name} fehlt" for name in PFLICHT if not (paket / name).is_file()]
    if befunde:
        return befunde
    eingetragen = set()
    for zeile in (paket / "SHA256SUMS").read_text(encoding="utf-8").splitlines():
        summe, _, pfad = zeile.partition("  ")
        eingetragen.add(pfad)
        datei = paket / pfad
        if not datei.is_file():
            befunde.append(f"{pfad} steht in SHA256SUMS, fehlt im Paket")
        elif hashlib.sha256(datei.read_bytes()).hexdigest() != summe:
            befunde.append(f"{pfad} weicht von seiner Pruefsumme ab")
    vorhanden = {p.relative_to(paket).as_posix() for p in paket.rglob("*") if p.is_file()}
    for pfad in sorted(vorhanden - eingetragen - {"SHA256SUMS"}):
        befunde.append(f"{pfad} liegt im Paket, steht nicht in SHA256SUMS")
    if not (paket / "STAND").read_text(encoding="utf-8").startswith("VOR="):
        befunde.append("STAND nennt keinen Stand VOR=<commit>")
    return befunde


def test_der_festgehaltene_fall_3_liegt_als_paket_im_repository():
    assert (PAKETE / "baldrian-klv-tg2015-fall3").is_dir()


def test_jedes_paket_entspricht_seinen_pruefsummen():
    pakete = sorted(p for p in PAKETE.iterdir() if p.is_dir())
    assert pakete
    for paket in pakete:
        assert _befunde(paket) == [], paket.name


def test_die_pruefung_sieht_eine_veraenderte_und_eine_fremde_datei(tmp_path):
    kopie = tmp_path / "paket"
    shutil.copytree(PAKETE / "baldrian-klv-tg2015-fall3", kopie)
    assert _befunde(kopie) == []

    rezept = kopie / "rezept.sh"
    rezept.write_bytes(rezept.read_bytes() + b"\n")
    assert _befunde(kopie) == ["rezept.sh weicht von seiner Pruefsumme ab"]

    shutil.rmtree(kopie)
    shutil.copytree(PAKETE / "baldrian-klv-tg2015-fall3", kopie)
    (kopie / "nachlieferung" / "dazugelegt.md").write_text("x", encoding="utf-8")
    assert _befunde(kopie) == [
        "nachlieferung/dazugelegt.md liegt im Paket, steht nicht in SHA256SUMS"
    ]
