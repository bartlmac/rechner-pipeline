"""Fall-Arbeitsbereich: Anlegen, Eingang-Register, Integritaet, CLI-Naht.

Knoten: system/fall
"""

from __future__ import annotations

import json
import stat
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
        "schema_version": 1,
        "typ": "tarif",
        "gate_dag_version": fall_mod.GATE_DAG_VERSION,
    }
    with pytest.raises(FallFehler, match="existiert bereits"):
        anlegen(f)


def test_gate_dag_leitet_scope_spezifische_g2_pflichten_ab(tmp_path: Path) -> None:
    tarif = tmp_path / "tarif"
    bestand = tmp_path / "bestand"
    anlegen(tarif, scope="tarif")
    anlegen(bestand, scope="bestand")

    assert fall_mod.lade_scope(tarif) == "tarif"
    assert fall_mod.lade_scope(bestand) == "bestand"
    assert fall_mod.validate_gate_dag() == []
    assert fall_mod.g2_belegrollen("tarif") == [
        "o1_ledger", "g1_snapshot", "o3_belege",
    ]
    assert fall_mod.g2_belegrollen("bestand") == [
        "o1_ledger", "g1_snapshot", "o3_belege", "transformationsspec",
        "transformationsergebnis", "b1_ledger", "migrationssuite",
        "bestandsbericht_vor", "bestandsbericht_nach", "abnahmebericht",
    ]
    # Der Vertrag ist ohne Python-Sonderobjekte als JSON publizierbar.
    assert json.loads(json.dumps(fall_mod.GATE_DAG)) == fall_mod.GATE_DAG
    ungueltig = tmp_path / "ungueltig"
    with pytest.raises(FallFehler, match="unbekannter Fall-Scope"):
        anlegen(ungueltig, scope="geraten")
    assert not ungueltig.exists()


@pytest.mark.parametrize(
    ("aenderung", "erwartet"),
    [
        (lambda dag: dag.__setitem__("ziel", []), "Gate-DAG.ziel"),
        (
            lambda dag: dag["kanten"][0].__setitem__("von", {}),
            "Kante 0 referenziert",
        ),
        (
            lambda dag: dag["kanten"][0].__setitem__("nach", []),
            "Kante 0 referenziert",
        ),
        (
            lambda dag: dag["kanten"][0].__setitem__("scopes", 7),
            "Kante 0.scopes",
        ),
        (
            lambda dag: dag["knoten"]["o1"].__setitem__("scopes", [{}]),
            "Knoten 'o1'.scopes",
        ),
        (
            lambda dag: dag["knoten"]["o1"].__setitem__("scopes", 7),
            "Knoten 'o1'.scopes",
        ),
        (
            lambda dag: dag.__setitem__("schema_version", True),
            "schema_version",
        ),
    ],
)
def test_gate_dag_validator_meldet_typfehler_statt_abzustuerzen(
    aenderung, erwartet: str
) -> None:
    kaputt = json.loads(json.dumps(fall_mod.GATE_DAG))
    aenderung(kaputt)
    assert any(
        erwartet in fehler for fehler in fall_mod.validate_gate_dag(kaputt)
    )


def test_gate_dag_validator_blockiert_abgetrennte_pflichtrolle() -> None:
    kaputt = json.loads(json.dumps(fall_mod.GATE_DAG))
    kaputt["kanten"] = [
        kante for kante in kaputt["kanten"]
        if kante["von"] != "bestandsbericht_vor"
    ]

    assert any(
        "'bestandsbericht_vor'" in fehler and "keinen Pfad" in fehler
        for fehler in fall_mod.validate_gate_dag(kaputt)
    )


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
