"""Fall-Arbeitsbereich: Anlegen, Eingang-Register, Integritaet, CLI-Naht.

Knoten: system/fall
"""

from __future__ import annotations

import json
import os
import stat
import threading
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

import pytest

from rechner_pipeline import fall as fall_mod
from rechner_pipeline.fall import (
    FallFehler,
    anlegen,
    eingang_datei,
    pruefen,
    registrieren,
    status,
    verzeichnisse,
)


@pytest.fixture()
def quelle(tmp_path: Path) -> Path:
    q = tmp_path / "quellen" / "Tarifrechner_X.xlsm"
    q.parent.mkdir()
    q.write_bytes(b"excel-bytes-v1")
    return q


def test_anlegen_erzeugt_layout_und_ueberschreibt_nie(tmp_path: Path) -> None:
    f = tmp_path / "faelle" / "plv"
    ergebnis = anlegen(f, beschreibung="Testfall")
    assert ergebnis["angelegt"] is True
    assert (f / "fall.json").is_file()
    assert (f / "eingang.json").is_file()
    assert (f / "eingang").is_dir()
    assert (f / "abgeleitet").is_dir()
    manifest = json.loads((f / "fall.json").read_text(encoding="utf-8"))
    assert manifest["name"] == "plv"
    assert manifest["beschreibung"] == "Testfall"
    assert manifest["scope"] == {
        "schema_version": 2,
        "typ": "tarif",
    }
    with pytest.raises(FallFehler, match="existiert bereits"):
        anlegen(f)


def test_scope_legt_die_am4_pflichten_fuer_tarif_und_bestand_fest(
    tmp_path: Path,
) -> None:
    tarif = tmp_path / "tarif"
    bestand = tmp_path / "bestand"
    anlegen(tarif, scope="tarif")
    anlegen(bestand, scope="bestand")

    assert fall_mod.lade_scope(tarif) == "tarif"
    assert fall_mod.lade_scope(bestand) == "bestand"
    assert fall_mod.am4_belegrollen("tarif") == [
        "pq3_ledger", "aq1_snapshot", "am1_snapshot", "pk1_belege",
    ]
    assert fall_mod.am4_belegrollen("bestand") == [
        "pq3_ledger", "aq1_snapshot",
        # Alle drei aktuariellen Abnahmen (Entscheidung 2026-08-31) --
        # im Tarif-Scope nur A-M1, dort gibt es keinen Bestand.
        "am1_snapshot", "am2_snapshot", "am3_snapshot",
        "pk1_belege", "pb1_ledger", "migrationssuite", "abnahmebericht",
    ]
    # Belegrollen JE GATE (ADR-010): A-M1 pinnt im Bestands-Scope die
    # Testartefakte, im Tarif-Scope ist die Rollenmenge leer.
    assert fall_mod.belegrollen("A-M1", "tarif") == []
    assert fall_mod.belegrollen("A-M1", "bestand") == [
        "aktuartest", "aktuartest_bericht",
    ]
    with pytest.raises(FallFehler, match="kein Belegrollen-Vertrag"):
        fall_mod.belegrollen("A-Q1", "tarif")
    ungueltig = tmp_path / "ungueltig"
    with pytest.raises(FallFehler, match="unbekannter Fall-Scope"):
        anlegen(ungueltig, scope="geraten")
    assert not ungueltig.exists()


def test_scope_v1_mit_alter_dag_metadatei_bleibt_lesbar(tmp_path: Path) -> None:
    fall = tmp_path / "legacy"
    anlegen(fall, scope="bestand")
    manifest = json.loads((fall / "fall.json").read_text(encoding="utf-8"))
    manifest["scope"] = {
        "schema_version": 1,
        "typ": "bestand",
        "gate_dag_version": "1.0.0",
    }
    (fall / "fall.json").write_text(json.dumps(manifest), encoding="utf-8")

    assert fall_mod.lade_scope(fall) == "bestand"

def test_registrieren_hasht_schuetzt_und_ist_idempotent(
    tmp_path: Path, quelle: Path
) -> None:
    f = tmp_path / "fall"
    anlegen(f)
    ergebnis = registrieren(f, quelle)
    assert ergebnis["status"] == "registriert"
    kopie = f / "eingang" / quelle.name
    assert kopie.read_bytes() == quelle.read_bytes()
    # Schreibschutz: keine Schreib-Bits mehr
    assert not kopie.stat().st_mode & (stat.S_IWUSR | stat.S_IWGRP | stat.S_IWOTH)
    # Provenance im Register: Hash, Groesse, Herkunft
    register = json.loads((f / "eingang.json").read_text(encoding="utf-8"))
    [eintrag] = register["quellen"]
    assert eintrag["sha256"] == ergebnis["sha256"] and len(eintrag["sha256"]) == 64
    assert eintrag["quelle_pfad"] == str(quelle)
    # Idempotent bei gleichem Inhalt:
    assert registrieren(f, quelle)["status"] == "bereits_registriert"
    assert pruefen(f) == []


def test_gleicher_name_anderer_inhalt_ist_harter_konflikt(
    tmp_path: Path, quelle: Path
) -> None:
    f = tmp_path / "fall"
    anlegen(f)
    alt_hash = registrieren(f, quelle)["sha256"]
    quelle.write_bytes(b"excel-bytes-v2 (geaendert)")
    with pytest.raises(FallFehler) as exc:
        registrieren(f, quelle)
    # Beide Lesarten in der Meldung (kein stiller Overwrite):
    assert alt_hash in str(exc.value)
    # --als loest den Konflikt als expliziten Vorgang:
    assert registrieren(f, quelle, als="Tarifrechner_X_v2.xlsm")["status"] == "registriert"


def test_pruefen_findet_drift_und_fremddateien(tmp_path: Path, quelle: Path) -> None:
    f = tmp_path / "fall"
    anlegen(f)
    registrieren(f, quelle)
    kopie = f / "eingang" / quelle.name
    kopie.chmod(0o644)
    kopie.write_bytes(b"manipuliert")
    (f / "eingang" / "unbekannt.csv").write_text("x", encoding="utf-8")
    fehler = pruefen(f)
    assert any("weicht vom Register ab" in e for e in fehler)
    assert any("ohne Registrierung" in e for e in fehler)
    # Kein Lauf auf unklarem Eingang:
    with pytest.raises(FallFehler, match="kein Lauf auf unklarem Eingang"):
        eingang_datei(f, quelle.name)


def test_eingang_datei_nur_fuer_registrierte(tmp_path: Path, quelle: Path) -> None:
    f = tmp_path / "fall"
    anlegen(f)
    registrieren(f, quelle)
    pfad = eingang_datei(f, quelle.name)
    assert pfad == f / "eingang" / quelle.name
    with pytest.raises(FallFehler, match="nicht registriert"):
        eingang_datei(f, "gibts-nicht.xlsm")


def test_status_meldet_register_und_integritaet(tmp_path: Path, quelle: Path) -> None:
    f = tmp_path / "fall"
    anlegen(f)
    registrieren(f, quelle)
    s = status(f)
    assert s["eingang_integritaet"]["in_ordnung"] is True
    assert [q["datei"] for q in s["quellen"]] == [quelle.name]
    assert s["abgeleitet"]["generated_dir"] is False  # entsteht erst im Lauf


def test_cli_roundtrip_jede_ausgabe_ist_ein_json_objekt(
    tmp_path: Path, quelle: Path, capsys
) -> None:
    """Jedes Kommando gibt genau EIN JSON-Objekt auf stdout — nachgeschaltete
    Werkzeuge parsen die Ausgabe, deshalb wird der Vertrag geprueft."""
    f = tmp_path / "fall"
    for argv, erwartet in (
        (["anlegen", "--fall", str(f), "--beschreibung", "b"], {"angelegt": True}),
        (["registrieren", "--fall", str(f), "--datei", str(quelle)],
         {"status": "registriert"}),
        (["status", "--fall", str(f)], None),
    ):
        capsys.readouterr()
        assert fall_mod.main(argv) == 0
        ausgabe = capsys.readouterr().out
        objekt = json.loads(ausgabe)          # genau ein Objekt, kein Beiwerk
        assert isinstance(objekt, dict)
        assert ausgabe.count("\n{") == 0     # kein zweites Objekt
        for schluessel, wert in (erwartet or {}).items():
            assert objekt[schluessel] == wert
    assert objekt["eingang_integritaet"]["in_ordnung"] is True


def test_cli_konflikt_ist_exit_1(tmp_path: Path, quelle: Path, capsys) -> None:
    f = tmp_path / "fall"
    fall_mod.main(["anlegen", "--fall", str(f)])
    fall_mod.main(["registrieren", "--fall", str(f), "--datei", str(quelle)])
    quelle.write_bytes(b"anders")
    rc = fall_mod.main(["registrieren", "--fall", str(f), "--datei", str(quelle)])
    assert rc == 1
    assert "Eingangs-Konflikt" in capsys.readouterr().err




# --------------------------------------------------------------------------- #
# Review-Fixes: Zonen-Trennung, Register-gegen-Dateisystem, CLI-Robustheit
# --------------------------------------------------------------------------- #


@pytest.mark.parametrize(
    "name",
    ["../fall.json", "sub/x.bin", "/tmp/absolut.bin", "..", ".", "a\\b.bin"],
)
def test_als_muss_einfacher_dateiname_sein(
    tmp_path: Path, quelle: Path, name: str
) -> None:
    """Ohne diese Pruefung schreibt --als ausserhalb von eingang/: '..'
    zerstoert das Manifest, ein absoluter Pfad schreibt irgendwohin — und
    pruefen() meldet weiter gruen, weil es den Traversal-Namen aufloest."""
    f = tmp_path / "fall"
    anlegen(f)
    manifest_vorher = (f / "fall.json").read_bytes()
    with pytest.raises(FallFehler, match="unzulaessiger Eingangsname"):
        registrieren(f, quelle, als=name)
    assert (f / "fall.json").read_bytes() == manifest_vorher
    assert list((f / "eingang").iterdir()) == []
    assert pruefen(f) == []


def test_unregistrierte_datei_gleichen_namens_wird_nicht_ueberschrieben(
    tmp_path: Path, quelle: Path
) -> None:
    """Der Konflikt-Check darf nicht nur das Register befragen: eine
    manuell abgelegte Datei im Eingang ist nicht regenerierbar."""
    f = tmp_path / "fall"
    anlegen(f)
    fremd = f / "eingang" / quelle.name
    fremd.write_bytes(b"manuell abgelegt, noch nicht registriert")
    with pytest.raises(FallFehler, match="unregistrierte Datei"):
        registrieren(f, quelle)
    assert fremd.read_bytes() == b"manuell abgelegt, noch nicht registriert"


def test_abbruchfenster_wird_durch_nachtragen_repariert(
    tmp_path: Path, quelle: Path
) -> None:
    """Kopie da, Registereintrag fehlt (Abbruch zwischen beiden Schritten):
    erneutes Registrieren traegt nach, statt den Fall unbenutzbar zu lassen."""
    f = tmp_path / "fall"
    anlegen(f)
    ziel = f / "eingang" / quelle.name
    ziel.write_bytes(quelle.read_bytes())
    ziel.chmod(0o444)                       # wie nach dem Schreibschutz-Schritt
    assert any("ohne Registrierung" in e for e in pruefen(f))
    ergebnis = registrieren(f, quelle)
    assert ergebnis["status"] == "nachgetragen"
    assert pruefen(f) == []


def test_fehlende_kopie_wird_wiederhergestellt_statt_erfolg_zu_melden(
    tmp_path: Path, quelle: Path
) -> None:
    """'bereits_registriert' darf nicht gemeldet werden, wenn die Kopie
    fehlt — sonst deckt die Idempotenz-Zusage den kaputten Fall zu."""
    f = tmp_path / "fall"
    anlegen(f)
    registrieren(f, quelle)
    kopie = f / "eingang" / quelle.name
    kopie.chmod(0o644)
    kopie.unlink()
    assert any("Datei fehlt" in e for e in pruefen(f))
    assert registrieren(f, quelle)["status"] == "wiederhergestellt"
    assert pruefen(f) == []


def test_abgewichene_kopie_wird_nicht_still_ersetzt(
    tmp_path: Path, quelle: Path
) -> None:
    """Eine Integritaetsverletzung wird nicht durch erneutes Registrieren
    zugedeckt — die Aufloesung ist ein eigener Vorgang."""
    f = tmp_path / "fall"
    anlegen(f)
    registrieren(f, quelle)
    kopie = f / "eingang" / quelle.name
    kopie.chmod(0o644)
    kopie.write_bytes(b"drift")
    with pytest.raises(FallFehler, match="weicht vom Register ab"):
        registrieren(f, quelle)
    assert kopie.read_bytes() == b"drift"   # nichts wurde stillschweigend geheilt


@pytest.mark.parametrize("dangling", [False, True], ids=["gueltig", "dangling"])
def test_registrieren_lehnt_symlink_als_quelle_ab(
    tmp_path: Path, quelle: Path, dangling: bool
) -> None:
    f = tmp_path / "fall"
    anlegen(f)
    ziel = tmp_path / "fehlt.bin" if dangling else quelle
    link = tmp_path / "quellen-link.bin"
    link.symlink_to(ziel)

    with pytest.raises(FallFehler, match="Quelle ist ein Symlink"):
        registrieren(f, link)

    assert list((f / "eingang").iterdir()) == []
    assert json.loads((f / "eingang.json").read_text(encoding="utf-8"))[
        "quellen"
    ] == []


@pytest.mark.parametrize("dangling", [False, True], ids=["gueltig", "dangling"])
def test_registrieren_schreibt_nicht_durch_eingangs_symlink_nach_aussen(
    tmp_path: Path, quelle: Path, dangling: bool
) -> None:
    """Regression fuer T6-10: exists() ist bei dangling Links kein Guard."""
    f = tmp_path / "fall"
    anlegen(f)
    extern = tmp_path / "ausserhalb" / "ziel.xlsm"
    extern.parent.mkdir()
    if not dangling:
        extern.write_bytes(b"extern-vorher")
    kopie = f / "eingang" / quelle.name
    kopie.symlink_to(extern)

    with pytest.raises(FallFehler, match="Eingangsziel.*Symlink"):
        registrieren(f, quelle)

    assert kopie.is_symlink()
    if dangling:
        assert not extern.exists()
    else:
        assert extern.read_bytes() == b"extern-vorher"
    assert json.loads((f / "eingang.json").read_text(encoding="utf-8"))[
        "quellen"
    ] == []


@pytest.mark.parametrize("dangling", [False, True], ids=["gueltig", "dangling"])
def test_registrieren_lehnt_symlink_als_eingangsregister_ab(
    tmp_path: Path, quelle: Path, dangling: bool
) -> None:
    f = tmp_path / "fall"
    anlegen(f)
    register = f / "eingang.json"
    register.unlink()
    extern = tmp_path / "externes-register.json"
    if not dangling:
        extern.write_text('{"quellen": [], "schema_version": 1}\n', encoding="utf-8")
        vorher = extern.read_bytes()
    register.symlink_to(extern)

    with pytest.raises(FallFehler, match="Eingangs-Register ist ein Symlink"):
        registrieren(f, quelle)

    if dangling:
        assert not extern.exists()
    else:
        assert extern.read_bytes() == vorher
    assert list((f / "eingang").iterdir()) == []


def test_symlink_im_nachtragen_zeitfenster_wird_abgelehnt(
    tmp_path: Path, quelle: Path, monkeypatch
) -> None:
    f = tmp_path / "fall"
    anlegen(f)
    kopie = f / "eingang" / quelle.name
    extern = tmp_path / "extern.bin"
    extern.write_bytes(quelle.read_bytes())
    original = fall_mod._sha256

    def hash_mit_angriff(pfad: Path) -> str:
        wert = original(pfad)
        if pfad == quelle and not kopie.exists() and not kopie.is_symlink():
            kopie.symlink_to(extern)
        return wert

    monkeypatch.setattr(fall_mod, "_sha256", hash_mit_angriff)

    with pytest.raises(FallFehler, match="Symlink"):
        registrieren(f, quelle)
    assert kopie.is_symlink()
    assert json.loads((f / "eingang.json").read_text(encoding="utf-8"))[
        "quellen"
    ] == []


def test_quellwechsel_zwischen_hash_und_kopie_bricht_registrierung_ab(
    tmp_path: Path, quelle: Path, monkeypatch
) -> None:
    f = tmp_path / "fall"
    anlegen(f)
    original = fall_mod._sha256

    def hash_mit_quellwechsel(pfad: Path) -> str:
        wert = original(pfad)
        if pfad == quelle:
            quelle.write_bytes(b"nach-dem-hash-geaendert")
        return wert

    original_unlink = Path.unlink

    def windows_artiges_unlink(pfad: Path, *args, **kwargs) -> None:
        if pfad == f / "eingang" / quelle.name and not (
            pfad.stat().st_mode & stat.S_IWUSR
        ):
            raise PermissionError("read-only")
        original_unlink(pfad, *args, **kwargs)

    monkeypatch.setattr(fall_mod, "_sha256", hash_mit_quellwechsel)
    monkeypatch.setattr(Path, "unlink", windows_artiges_unlink)

    with pytest.raises(FallFehler, match="waehrend der Registrierung geaendert"):
        registrieren(f, quelle)
    assert not (f / "eingang" / quelle.name).exists()
    assert json.loads((f / "eingang.json").read_text(encoding="utf-8"))[
        "quellen"
    ] == []


def test_spaeter_symlink_im_nachtragen_zeitfenster_wird_abgelehnt(
    tmp_path: Path, quelle: Path, monkeypatch
) -> None:
    f = tmp_path / "fall"
    anlegen(f)
    kopie = f / "eingang" / quelle.name
    kopie.write_bytes(quelle.read_bytes())
    extern = tmp_path / "extern.bin"
    extern.write_bytes(quelle.read_bytes())
    original = fall_mod._schuetze_datei

    def schuetzen_mit_angriff(pfad: Path) -> None:
        original(pfad)
        pfad.chmod(0o644)
        pfad.unlink()
        pfad.symlink_to(extern)

    monkeypatch.setattr(fall_mod, "_schuetze_datei", schuetzen_mit_angriff)

    with pytest.raises(FallFehler, match="waehrend der Registrierung geaendert"):
        registrieren(f, quelle)
    assert kopie.is_symlink()
    assert json.loads((f / "eingang.json").read_text(encoding="utf-8"))[
        "quellen"
    ] == []


def test_symlink_nach_finalem_zielhash_wird_abgelehnt(
    tmp_path: Path, quelle: Path, monkeypatch
) -> None:
    f = tmp_path / "fall"
    anlegen(f)
    kopie = f / "eingang" / quelle.name
    extern = tmp_path / "extern.bin"
    extern.write_bytes(quelle.read_bytes())
    original = fall_mod._sha256

    def hash_mit_spaetem_angriff(pfad: Path) -> str:
        wert = original(pfad)
        if pfad == kopie and not kopie.is_symlink():
            kopie.chmod(0o644)
            kopie.unlink()
            kopie.symlink_to(extern)
        return wert

    monkeypatch.setattr(fall_mod, "_sha256", hash_mit_spaetem_angriff)

    with pytest.raises(FallFehler, match="Dateigroesse kann nicht sicher"):
        registrieren(f, quelle)
    assert kopie.is_symlink()
    assert json.loads((f / "eingang.json").read_text(encoding="utf-8"))[
        "quellen"
    ] == []


def test_registrieren_nutzt_portablen_fallback_ohne_dir_fd(
    tmp_path: Path, quelle: Path, monkeypatch
) -> None:
    f = tmp_path / "fall"
    anlegen(f)
    monkeypatch.setattr(os, "supports_dir_fd", set())

    assert registrieren(f, quelle)["status"] == "registriert"
    assert pruefen(f) == []


@pytest.mark.parametrize("dangling", [False, True], ids=["gueltig", "dangling"])
def test_pruefen_meldet_registrierten_symlink_statt_gruen(
    tmp_path: Path, quelle: Path, dangling: bool
) -> None:
    f = tmp_path / "fall"
    anlegen(f)
    registrieren(f, quelle)
    kopie = f / "eingang" / quelle.name
    kopie.chmod(0o644)
    kopie.unlink()
    extern = tmp_path / "extern.bin"
    if not dangling:
        extern.write_bytes(quelle.read_bytes())
    kopie.symlink_to(extern)

    fehler = pruefen(f)

    assert any(quelle.name in meldung and "Symlink" in meldung for meldung in fehler)
    with pytest.raises(FallFehler, match="kein Lauf auf unklarem Eingang"):
        eingang_datei(f, quelle.name)


def test_pruefen_bleibt_bei_symlink_im_hash_zeitfenster_rot(
    tmp_path: Path, quelle: Path, monkeypatch
) -> None:
    f = tmp_path / "fall"
    anlegen(f)
    registrieren(f, quelle)
    kopie = f / "eingang" / quelle.name
    extern = tmp_path / "extern.bin"
    extern.write_bytes(quelle.read_bytes())
    original = fall_mod._sha256

    def hash_mit_angriff(pfad: Path) -> str:
        if pfad == kopie and not kopie.is_symlink():
            kopie.chmod(0o644)
            kopie.unlink()
            kopie.symlink_to(extern)
        return original(pfad)

    monkeypatch.setattr(fall_mod, "_sha256", hash_mit_angriff)

    assert any("Symlink" in meldung for meldung in pruefen(f))


def test_register_symlink_im_lesezeitfenster_wird_nicht_gefolgt(
    tmp_path: Path, quelle: Path, monkeypatch
) -> None:
    f = tmp_path / "fall"
    anlegen(f)
    register = f / "eingang.json"
    extern = tmp_path / "externes-register.json"
    extern.write_bytes(register.read_bytes())
    original_exists = Path.exists

    def exists_mit_angriff(pfad: Path) -> bool:
        vorhanden = original_exists(pfad)
        if pfad == register and not pfad.is_symlink():
            pfad.unlink()
            pfad.symlink_to(extern)
        return vorhanden

    monkeypatch.setattr(Path, "exists", exists_mit_angriff)

    with pytest.raises(FallFehler, match="kann nicht sicher gelesen werden"):
        pruefen(f)


def test_pruefen_meldet_unregistrierten_dangling_symlink(
    tmp_path: Path, quelle: Path
) -> None:
    f = tmp_path / "fall"
    anlegen(f)
    registrieren(f, quelle)
    fremd = f / "eingang" / "fremd.csv"
    fremd.symlink_to(tmp_path / "nicht-vorhanden.csv")

    assert any(
        "fremd.csv" in meldung and "Symlink ohne Registrierung" in meldung
        for meldung in pruefen(f)
    )


def test_eingangszone_als_symlink_blockiert_registrierung_und_pruefung(
    tmp_path: Path, quelle: Path
) -> None:
    f = tmp_path / "fall"
    anlegen(f)
    eingang = f / "eingang"
    eingang.rmdir()
    extern = tmp_path / "externer-eingang"
    extern.mkdir()
    eingang.symlink_to(extern, target_is_directory=True)

    with pytest.raises(FallFehler, match="Eingangszone ist ein Symlink"):
        registrieren(f, quelle)

    assert list(extern.iterdir()) == []
    assert any("Symlink statt Eingangsverzeichnis" in meldung for meldung in pruefen(f))


def test_nachtragen_schuetzt_datei_und_pruefen_meldet_schreibbare_kopie(
    tmp_path: Path, quelle: Path
) -> None:
    f = tmp_path / "fall"
    anlegen(f)
    kopie = f / "eingang" / quelle.name
    kopie.write_bytes(quelle.read_bytes())
    kopie.chmod(0o644)

    assert registrieren(f, quelle)["status"] == "nachgetragen"
    assert not kopie.stat().st_mode & (
        stat.S_IWUSR | stat.S_IWGRP | stat.S_IWOTH
    )
    assert pruefen(f) == []

    kopie.chmod(0o644)
    assert any("registrierte Kopie ist schreibbar" in fehler for fehler in pruefen(f))
    with pytest.raises(FallFehler, match="Eingangs-Kopie.*schreibbar"):
        registrieren(f, quelle)


def test_pruefen_sieht_unregistrierte_verzeichnisse(
    tmp_path: Path, quelle: Path
) -> None:
    """Ein ganzer Ordner unregistrierter Quellen darf nicht durchrutschen."""
    f = tmp_path / "fall"
    anlegen(f)
    registrieren(f, quelle)
    (f / "eingang" / "kundendaten").mkdir()
    (f / "eingang" / "kundendaten" / "abzug.csv").write_text("x", encoding="utf-8")
    fehler = pruefen(f)
    assert any("kundendaten" in e and "Verzeichnis" in e for e in fehler)
    with pytest.raises(FallFehler, match="unklarem Eingang"):
        eingang_datei(f, quelle.name)


def test_halber_arbeitsbereich_ist_kein_stiller_reset(
    tmp_path: Path, quelle: Path
) -> None:
    """Fehlt das Manifest, darf 'anlegen' das Register nicht leeren —
    dort steht die Provenance der bereits registrierten Quellen."""
    f = tmp_path / "fall"
    anlegen(f)
    registrieren(f, quelle)
    register_vorher = (f / "eingang.json").read_text(encoding="utf-8")
    (f / "fall.json").unlink()
    with pytest.raises(FallFehler, match="unvollstaendiger Fall"):
        anlegen(f)
    assert (f / "eingang.json").read_text(encoding="utf-8") == register_vorher
    # Umgekehrt: Manifest ohne Register ist ebenfalls kein 'existiert bereits'
    g = tmp_path / "fall2"
    anlegen(g)
    (g / "eingang.json").unlink()
    with pytest.raises(FallFehler, match="unvollstaendiger Fall"):
        anlegen(g)


def test_register_bleibt_sortiert(tmp_path: Path) -> None:
    """Das Register ist ein Provenance-Artefakt: gleiche Quellen ergeben
    dieselbe Datei, unabhaengig von der Registrierungsreihenfolge."""
    f = tmp_path / "fall"
    anlegen(f)
    for name, inhalt in (("z.bin", b"z"), ("a.bin", b"a"), ("m.bin", b"m")):
        q = tmp_path / name
        q.write_bytes(inhalt)
        registrieren(f, q)
    namen = [q["datei"] for q in json.loads(
        (f / "eingang.json").read_text(encoding="utf-8"))["quellen"]]
    assert namen == sorted(namen) == ["a.bin", "m.bin", "z.bin"]


def test_parallele_registrierungen_verlieren_keinen_registereintrag(
    tmp_path: Path, monkeypatch
) -> None:
    """Deterministische T6-15-Regression fuer den alten Lost-Update-Ablauf.

    Der erste Writer wird an der Publikationsnaht kurz angehalten. Ohne den
    fallbezogenen Lock erreicht der zweite Writer dieselbe Naht mit seinem
    ebenfalls aus dem leeren Register abgeleiteten Stand; der letzte Replace
    verliert dann genau einen Eintrag. Mit Lock darf es dort keine
    Ueberlappung geben, und der zweite Writer liest den publizierten Stand neu.
    """
    fall = tmp_path / "fall"
    anlegen(fall)
    quellen = []
    for name, inhalt in (("a.bin", b"a"), ("b.bin", b"b")):
        quelle = tmp_path / name
        quelle.write_bytes(inhalt)
        quellen.append(quelle)

    original = fall_mod._schreibe_json
    register_pfad = fall / "eingang.json"
    erste_an_schreibnaht = threading.Event()
    zweite_an_schreibnaht = threading.Event()
    zaehler_lock = threading.Lock()
    schreibaufrufe = 0
    ueberlappungen = []

    def kontrolliert_schreiben(pfad: Path, daten: dict) -> None:
        nonlocal schreibaufrufe
        if pfad == register_pfad:
            with zaehler_lock:
                schreibaufrufe += 1
                aufruf = schreibaufrufe
            if aufruf == 1:
                erste_an_schreibnaht.set()
                ueberlappungen.append(zweite_an_schreibnaht.wait(timeout=0.25))
            else:
                zweite_an_schreibnaht.set()
        original(pfad, daten)

    monkeypatch.setattr(fall_mod, "_schreibe_json", kontrolliert_schreiben)

    with ThreadPoolExecutor(max_workers=2) as pool:
        erster = pool.submit(registrieren, fall, quellen[0])
        assert erste_an_schreibnaht.wait(timeout=2)
        zweiter = pool.submit(registrieren, fall, quellen[1])
        ergebnisse = [erster.result(timeout=3), zweiter.result(timeout=3)]

    assert ueberlappungen == [False]
    assert [ergebnis["status"] for ergebnis in ergebnisse] == [
        "registriert", "registriert",
    ]
    register = json.loads(register_pfad.read_text(encoding="utf-8"))
    assert [eintrag["datei"] for eintrag in register["quellen"]] == [
        "a.bin", "b.bin",
    ]
    assert pruefen(fall) == []


def test_register_wird_erst_als_vollstaendiges_json_atomar_publiziert(
    tmp_path: Path, monkeypatch
) -> None:
    fall = tmp_path / "fall"
    anlegen(fall)
    quelle = tmp_path / "quelle.bin"
    quelle.write_bytes(b"inhalt")
    register_pfad = fall / "eingang.json"
    register_vorher = json.loads(register_pfad.read_text(encoding="utf-8"))
    echtes_ersetzen = fall_mod.os.replace
    beobachtet = []

    def pruefendes_ersetzen(temp_pfad, ziel_pfad) -> None:
        if Path(ziel_pfad) == register_pfad:
            alt = json.loads(register_pfad.read_text(encoding="utf-8"))
            neu = json.loads(Path(temp_pfad).read_text(encoding="utf-8"))
            beobachtet.append((alt, neu, Path(temp_pfad).parent))
        echtes_ersetzen(temp_pfad, ziel_pfad)

    monkeypatch.setattr(fall_mod.os, "replace", pruefendes_ersetzen)

    registrieren(fall, quelle)

    [(alt, neu, temp_verzeichnis)] = beobachtet
    assert alt == register_vorher
    assert [eintrag["datei"] for eintrag in neu["quellen"]] == ["quelle.bin"]
    assert temp_verzeichnis == fall
    assert json.loads(register_pfad.read_text(encoding="utf-8")) == neu


def test_fehlgeschlagene_atomare_publikation_laesst_register_unveraendert(
    tmp_path: Path, monkeypatch
) -> None:
    fall = tmp_path / "fall"
    anlegen(fall)
    quelle = tmp_path / "quelle.bin"
    quelle.write_bytes(b"inhalt")
    register_pfad = fall / "eingang.json"
    vorher = register_pfad.read_bytes()
    echtes_ersetzen = fall_mod.os.replace

    def verweigertes_ersetzen(temp_pfad, ziel_pfad) -> None:
        if Path(ziel_pfad) == register_pfad:
            raise OSError("Publikation verweigert")
        echtes_ersetzen(temp_pfad, ziel_pfad)

    monkeypatch.setattr(fall_mod.os, "replace", verweigertes_ersetzen)

    with pytest.raises(FallFehler, match="Publikation verweigert"):
        registrieren(fall, quelle)

    assert register_pfad.read_bytes() == vorher
    assert json.loads(register_pfad.read_text(encoding="utf-8"))["quellen"] == []
    assert list(fall.glob(".eingang.json.*.tmp")) == []


def test_registrierungs_lock_folgt_keinem_symlink(
    tmp_path: Path, quelle: Path
) -> None:
    fall = tmp_path / "fall"
    anlegen(fall)
    extern = tmp_path / "externes-lockziel"
    extern.write_bytes(b"unveraendert")
    (fall / fall_mod.EINGANG_REGISTER_LOCK).symlink_to(extern)

    with pytest.raises(FallFehler, match="Registrierungs-Lock ist ein Symlink"):
        registrieren(fall, quelle)

    assert extern.read_bytes() == b"unveraendert"
    assert json.loads((fall / "eingang.json").read_text(encoding="utf-8"))[
        "quellen"
    ] == []


@pytest.mark.parametrize("kommando", ["status", "registrieren"])
def test_defekter_oder_fehlender_fall_ergibt_meldung_statt_traceback(
    tmp_path: Path, quelle: Path, kommando: str, capsys
) -> None:
    """Fehlender Pfad und kaputtes JSON sind FallFehler mit exit 1 — die
    CLI faengt sie, statt einen Traceback zu zeigen."""
    argv = {"status": ["status", "--fall", str(tmp_path / "tippfehler")],
            "registrieren": ["registrieren", "--fall", str(tmp_path / "tippfehler"),
                             "--datei", str(quelle)]}[kommando]
    assert fall_mod.main(argv) == 1
    assert "kein Fall-Arbeitsbereich" in capsys.readouterr().err

    f = tmp_path / "kaputt"
    anlegen(f)
    (f / "eingang.json").write_text("{kein json", encoding="utf-8")
    argv = [a.replace(str(tmp_path / "tippfehler"), str(f)) for a in argv]
    assert fall_mod.main(argv) == 1
    assert "unlesbar" in capsys.readouterr().err


@pytest.mark.parametrize("kommando", ["status", "registrieren"])
def test_defekter_registereintrag_bleibt_innerhalb_der_fallfehler_grenze(
    tmp_path: Path, quelle: Path, kommando: str, capsys
) -> None:
    f = tmp_path / "fall"
    anlegen(f)
    (f / "eingang.json").write_text(
        json.dumps({"schema_version": 1, "quellen": [{}]}), encoding="utf-8"
    )
    argv = [kommando, "--fall", str(f)]
    if kommando == "registrieren":
        argv.extend(["--datei", str(quelle)])

    assert fall_mod.main(argv) == 1
    assert "Eingangs-Registereintrag 0" in capsys.readouterr().err
