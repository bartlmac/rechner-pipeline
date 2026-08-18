"""Migrationsstaging: DOCX-Extraktion — Determinismus, Struktur, Fehlerpfade.

Knoten: klv
"""

from __future__ import annotations

import json
import zipfile
from pathlib import Path

from rechner_pipeline.quellen import tarifplan_staging as staging

REPO_ROOT = Path(__file__).resolve().parents[1]
KLV_DOCX = REPO_ROOT / "tests" / "fixtures" / "Mitteilung_143_KLV_TG2012.docx"

_W = "http://schemas.openxmlformats.org/wordprocessingml/2006/main"
_M = "http://schemas.openxmlformats.org/officeDocument/2006/math"


def _mini_docx(pfad: Path, body_xml: str) -> Path:
    dokument = (
        f'<?xml version="1.0" encoding="UTF-8"?>'
        f'<w:document xmlns:w="{_W}" xmlns:m="{_M}">'
        f"<w:body>{body_xml}</w:body></w:document>"
    )
    with zipfile.ZipFile(pfad, "w") as archiv:
        archiv.writestr("word/document.xml", dokument)
    return pfad


def _absatz(text: str, stil: str = "") -> str:
    stil_xml = f'<w:pPr><w:pStyle w:val="{stil}"/></w:pPr>' if stil else ""
    return f"<w:p>{stil_xml}<w:r><w:t>{text}</w:t></w:r></w:p>"


def test_beispiel_artefakt_deterministisch(tmp_path):
    a, b = tmp_path / "a.json", tmp_path / "b.json"
    assert staging.main(["--docx", str(KLV_DOCX), "--out", str(a)]) == 0
    assert staging.main(["--docx", str(KLV_DOCX), "--out", str(b)]) == 0
    assert a.read_bytes() == b.read_bytes()  # byte-gleich, keine Zeitstempel
    daten = json.loads(a.read_text(encoding="utf-8"))
    assert len(daten["formeln"]) == 46
    assert daten["quelle_sha256"]


def test_sdt_inhalte_werden_erfasst(tmp_path):
    """Review-Fix: Absaetze/Tabellen in w:sdt (Content Controls) zaehlen mit."""
    body = (
        f"<w:sdt><w:sdtContent>{_absatz('Im Content-Control', 'Heading1')}"
        f"<w:tbl><w:tr><w:tc>{_absatz('Zelle-A')}</w:tc></w:tr></w:tbl>"
        f"</w:sdtContent></w:sdt>"
        f"{_absatz('Normaler Absatz')}"
    )
    docx = _mini_docx(tmp_path / "sdt.docx", body)
    daten = staging.extrahiere(docx)
    assert [a["text"] for a in daten["absaetze"]] == [
        "Im Content-Control", "Normaler Absatz",
    ]
    assert daten["absaetze"][0]["stil"] == "Heading1"
    assert daten["tabellen"][0]["zeilen"] == [["Zelle-A"]]


def test_zellen_separatoren_und_leere_zeilen(tmp_path):
    """Review-Fix: Mehrfach-Absaetze/verschachtelte Tabellen mit Umbruechen;
    leere Zeilen bleiben (Indizes entsprechen der Quelltabelle)."""
    innere = f"<w:tbl><w:tr><w:tc>{_absatz('INNEN')}</w:tc></w:tr></w:tbl>"
    body = (
        f"<w:tbl>"
        f"<w:tr><w:tc>{_absatz('Zeile1')}{_absatz('Zeile2')}{innere}</w:tc></w:tr>"
        f"<w:tr><w:tc><w:p/></w:tc></w:tr>"
        f"<w:tr><w:tc>{_absatz('Danach')}</w:tc></w:tr>"
        f"</w:tbl>"
    )
    daten = staging.extrahiere(_mini_docx(tmp_path / "t.docx", body))
    zeilen = daten["tabellen"][0]["zeilen"]
    assert zeilen[0] == ["Zeile1\nZeile2\nINNEN"]
    assert zeilen[1] == [""]          # leere Zeile bleibt erhalten
    assert zeilen[2] == ["Danach"]
    assert len(daten["tabellen"]) == 1  # innere Tabelle nicht doppelt gezaehlt


def test_formeln_global_auch_in_zellen(tmp_path):
    body = (
        f"<w:tbl><w:tr><w:tc><w:p><m:oMath><m:r><m:t>P=A/a</m:t></m:r>"
        f"</m:oMath></w:p></w:tc></w:tr></w:tbl>"
    )
    daten = staging.extrahiere(_mini_docx(tmp_path / "f.docx", body))
    assert daten["formeln"] == ["P=A/a"]


def test_fehlerpfade_exit_2(tmp_path, capsys):
    kaputt = tmp_path / "kaputt.docx"
    kaputt.write_bytes(b"kein zip")
    assert staging.main(["--docx", str(kaputt), "--out", str(tmp_path / "x.json")]) == 2
    # ZIP ohne document.xml:
    leer = tmp_path / "leer.docx"
    with zipfile.ZipFile(leer, "w") as archiv:
        archiv.writestr("irgendwas.txt", "x")
    assert staging.main(["--docx", str(leer), "--out", str(tmp_path / "y.json")]) == 2
    # document.xml ohne w:body (Review-Fix: rc 2 statt Traceback):
    ohne_body = tmp_path / "ohne_body.docx"
    with zipfile.ZipFile(ohne_body, "w") as archiv:
        archiv.writestr(
            "word/document.xml",
            f'<?xml version="1.0"?><w:document xmlns:w="{_W}"/>',
        )
    assert staging.main(
        ["--docx", str(ohne_body), "--out", str(tmp_path / "z.json")]
    ) == 2
    assert staging.main(
        ["--docx", str(tmp_path / "fehlt.docx"), "--out", str(tmp_path / "w.json")]
    ) == 2
