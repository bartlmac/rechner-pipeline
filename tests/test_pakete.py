"""pakete/: jeder festgehaltene Fall ist ein Paket, das seinen Pruefsummen entspricht.

Ein Paket ist die Eingabe des deterministischen Nachfahrens
(werkzeuge/welt/fall_nachfahren.sh). Das Skript faehrt nur ein Paket, das
seinen Pruefsummen entspricht und keine Datei darueber hinaus traegt. Liegt
ein Paket im Repository, gilt dieselbe Bedingung schon fuer den Baum —
sonst faellt eine verletzte Datei erst auf, wenn jemand den Fall nachfaehrt,
und das dauert vierzig Minuten.

Geprueft wird Mechanik: Pflichtdateien, Pruefsummen, keine fremde Datei.
Ob der Commit unter STAND in der Geschichte liegt, prueft dieser Test NICHT:
Die CI holt nur den letzten Commit; das prueft das Nachfahren selbst.

Dazu die zweite Bedingung des Nachfahrens: Das Rezept uebernimmt die Urteile
der Zeichnungen A-K2 und A-T1 und haelt dafuer Kern und Tarifwerk des Baums
gegen die Fingerabdruecke des festgehaltenen Falls. Aendert ein Commit einen
dieser gezeichneten Gegenstaende, haelt das Nachfahren an — oder, bei der
Grundsatzdokumentation, die das Rezept nicht einzeln prueft, zeichnete es
A-K2 ueber einen anderen Gegenstand. Beides faellt hier schon am Baum auf.

Knoten: klv
"""

from __future__ import annotations

import hashlib
import re
import shutil
from pathlib import Path

from rechner_pipeline.gates import kernstand_belegen, tarifwerk_belegen
from rechner_pipeline.models import kernabnahme, tarifwerkabnahme

REPO = Path(__file__).resolve().parents[1]
PAKETE = REPO / "pakete"
PFLICHT = ("fall.conf", "rezept.sh", "ERWARTUNG", "STAND", "SHA256SUMS")

#: Die Schritte des Rezepts, die einen gezeichneten Gegenstand gegen den
#: festgehaltenen Fall halten, und was die drei Fingerabdruecke dahinter
#: bedeuten (in der Reihenfolge des Rezepts).
PRUEFSCHRITTE = {
    "kern": ("Der belegte Kern ist der des festgehaltenen Falls",
             ("kern_der_linie", "kern", "referenzwerte")),
    "tarifwerk": ("Das belegte Tarifwerk ist das des festgehaltenen Falls",
                  ("tarifwerk_der_linie", "tarifwerk", "parametrierung")),
}

#: Der ganze Kernstand (Code, Referenzwerte, Grundsatzdokumentation —
#: ``models.kernabnahme.KERNSTAND``) je Paket, gemessen am Stand, den der
#: Fall hinterlassen hat. Das Rezept prueft Code und Referenzwerte einzeln;
#: die Grundsatzdokumentation deckt nur dieser Wert.
#: baldrian-klv-tg2015-fall3: gemessen am 2026-10-08 nach der redaktionellen
#: Ueberarbeitung von Kern-Docstrings und Grundsatzdokumentation, mit der das
#: Paket neu festgehalten wurde (vorher Stand 6aa7c14: 90705868...;
#: ``kernstand_belegen.kernstand_hash``).
KERNSTAND_DES_FALLS = {
    "baldrian-klv-tg2015-fall3":
        "c4d5a35cfb139af4ad1b9df1ddcbbcd48fa7289c9f56f5c22df310dc71f8f105",
}

AUSWEG = (
    "Der Baum traegt einen anderen gezeichneten Gegenstand als der "
    "festgehaltene Fall. Kern (src/rechner_pipeline/kern, die Referenzwerte, "
    "die Grundsatzdokumentation) und Tarifwerk (docs/tarifplaene, "
    "configs/*.toml) sind abgenommen (A-K2, A-T1); wer sie aendert, aendert "
    "den Gegenstand einer Zeichnung, und das Paket ist auf diesem Stand nicht "
    "mehr nachfahrbar. Ausweg: die Aenderung zuruecknehmen — oder sie als "
    "Aenderung des Zielsystems fuehren: Abnahme in der Linie, das Paket auf "
    "dem neuen Stand neu festhalten (ADR-027)."
)


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


def _soll(paket: Path) -> dict[str, dict[str, str]]:
    """Die Fingerabdruecke, gegen die das Rezept beim Nachfahren haelt."""
    rezept = (paket / "rezept.sh").read_text(encoding="utf-8")
    soll: dict[str, dict[str, str]] = {}
    for gegenstand, (schritt, namen) in PRUEFSCHRITTE.items():
        if schritt not in rezept:
            continue
        summen = re.findall(r"\b[0-9a-f]{64}\b", rezept.split(schritt, 1)[1])[:3]
        assert len(summen) == 3, f"{paket.name}: {schritt} ohne drei Fingerabdruecke"
        soll[gegenstand] = dict(zip(namen, summen))
    return soll


def _abweichungen(wurzel: Path, paket: Path) -> list[str]:
    """Wo der Baum unter ``wurzel`` nicht der des festgehaltenen Falls ist."""
    soll = _soll(paket)
    ist = {}
    if "kern" in soll:
        ist["kern"] = kernstand_belegen.kern_modul_hash(wurzel)
        ist["referenzwerte"] = kernstand_belegen.referenzwerte_hash(wurzel)
    if "tarifwerk" in soll:
        stand = tarifwerk_belegen.lebender_stand(wurzel)
        ist["tarifwerk"] = stand["tarifwerk_sha256"]
        ist["parametrierung"] = stand["parametrierung_sha256"]
    befunde = [
        f"{name}: {ist[name]} statt {wert}"
        for werte in soll.values() for name, wert in werte.items()
        if name in ist and ist[name] != wert
    ]
    if paket.name in KERNSTAND_DES_FALLS:
        kernstand = kernstand_belegen.kernstand_hash(wurzel)
        if kernstand != KERNSTAND_DES_FALLS[paket.name]:
            befunde.append(
                f"kernstand: {kernstand} statt {KERNSTAND_DES_FALLS[paket.name]}")
    return befunde


def test_jedes_paket_ist_auf_dem_stand_des_baums_nachfahrbar():
    pakete = sorted(p for p in PAKETE.iterdir() if p.is_dir())
    assert pakete
    for paket in pakete:
        assert _abweichungen(REPO, paket) == [], f"{paket.name}: {AUSWEG}"
    # Positivkontrolle: Das Paket von Fall 3 nennt beide Gegenstaende, und
    # sein Kernstand ist gemessen — sonst pruefte die Schleife nichts.
    fall3 = PAKETE / "baldrian-klv-tg2015-fall3"
    assert set(_soll(fall3)) == {"kern", "tarifwerk"}
    assert fall3.name in KERNSTAND_DES_FALLS


def _gezeichnete_gegenstaende(ziel: Path) -> Path:
    """Kopie der Pfade von Kernstand und Tarifwerk — ein Baum zum Verfaelschen."""
    for pfad in (*kernabnahme.kernstand_pfade(), tarifwerkabnahme.TARIFPLAENE,
                 tarifwerkabnahme.CONFIG_VERZEICHNIS):
        quelle = REPO / pfad
        if quelle.is_dir():
            shutil.copytree(quelle, ziel / pfad,
                            ignore=shutil.ignore_patterns("__pycache__"))
        else:
            (ziel / pfad).parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(quelle, ziel / pfad)
    return ziel


def test_die_pruefung_sieht_jeden_veraenderten_gezeichneten_gegenstand(tmp_path):
    fall3 = PAKETE / "baldrian-klv-tg2015-fall3"
    faelle = {
        "src/rechner_pipeline/kern/konventionen.py": {"kern", "kernstand"},
        "tests/fixtures/kern_referenzwerte": {"referenzwerte", "kernstand"},
        "docs/mathematik/grundsatzdokumentation.md": {"kernstand"},
        "docs/tarifplaene/klv.md": {"tarifwerk"},
    }
    for nummer, (pfad, erwartet) in enumerate(faelle.items()):
        baum = _gezeichnete_gegenstaende(tmp_path / str(nummer))
        assert _abweichungen(baum, fall3) == [], "die Kopie ist der Stand des Falls"
        ort = baum / pfad
        if ort.is_dir():
            ort = sorted(ort.glob("*.json"))[0]
        ort.write_bytes(ort.read_bytes() + b"\n")
        getroffen = {b.split(":", 1)[0] for b in _abweichungen(baum, fall3)}
        assert getroffen == erwartet, pfad
