"""Tests for the shared toolbox foundation (:mod:`rechner_pipeline.gates._common`).

Covers two hardening fixes:

* Fix 1 — :func:`_common.write_gate_ledger` writes a valid ``<command>.gate.json``
  ledger entry that ``orchestrate.dossier``'s loader reads back and lists
  in ``gates_present`` (on both the pass and fail paths).
* Fix 2 — UTF-8 stdout: a command whose result carries a BOM / non-cp1252 char
  emits valid UTF-8 JSON on stdout (decodable, ``json.loads``-able) with the
  correct exit code — never a ``UnicodeEncodeError`` / empty stdout.

Knoten: system/assurance
"""

from __future__ import annotations

import io
import json
from pathlib import Path

import pytest

from rechner_pipeline.models.schemas import GateLedgerEntry
from rechner_pipeline.gates import _common


# --------------------------------------------------------------------------- #
# Fix 1 — write_gate_ledger round-trip
# --------------------------------------------------------------------------- #


def _golden_master_result(*, status: str, exit_code: int) -> _common.ToolboxResult:
    """A ToolboxResult mimicking what the ``golden_master`` gate (G5) emits."""
    return _common.build_result(
        command="golden_master",
        gate="G5.golden-master",
        gate_version="1.0.0",
        status=status,
        exit_code=exit_code,
        input_hashes={"generated/actuarial.py": "a" * 64},
        output_hashes={"generated/golden.json": "b" * 64},
        summary={"compared": 12, "mismatches": 0 if status == "passed" else 3},
        metrics={"runtime_ms": 42},
        errors=[] if status == "passed" else [{"code": "gm.mismatch", "message": "x"}],
    )


def test_write_gate_ledger_writes_expected_filename(tmp_path: Path) -> None:
    result = _golden_master_result(status="passed", exit_code=_common.Exit.OK)
    out = _common.write_gate_ledger(result, tmp_path)

    assert out == tmp_path / f"golden_master{_common.GATE_LEDGER_SUFFIX}"
    assert out.name == "golden_master.gate.json"
    assert out.is_file()


def test_write_gate_ledger_entry_is_schema_valid(tmp_path: Path) -> None:
    result = _golden_master_result(status="passed", exit_code=_common.Exit.OK)
    out = _common.write_gate_ledger(result, tmp_path, attempt=2)

    payload = json.loads(out.read_text(encoding="utf-8"))
    entry = GateLedgerEntry.from_dict(payload)
    assert entry.validate() == []
    # Ledger entry field mapping.
    assert entry.gate == "G5.golden-master"
    assert entry.command == "golden_master"
    assert entry.gate_version == "1.0.0"
    assert entry.required is True
    assert entry.status == "passed"
    assert entry.attempt == 2
    assert entry.started_at  # real ISO-8601 timestamp
    assert entry.input_hashes == {"generated/actuarial.py": "a" * 64}
    # Schema-fixed extras preserved under summary.
    assert entry.summary["exit_code"] == 0
    assert entry.summary["output_hashes"] == {"generated/golden.json": "b" * 64}
    assert "ended_at" in entry.summary


def test_write_gate_ledger_roundtrips_into_gates_present(tmp_path: Path) -> None:
    """The file write is read back by the dossier loader and counted."""
    result = _golden_master_result(status="passed", exit_code=_common.Exit.OK)
    _common.write_gate_ledger(result, tmp_path)

    entries, read_errors = _common.load_gate_ledger(tmp_path)
    assert read_errors == []
    assert len(entries) == 1
    gates_present = sorted({e.gate for e in entries})
    assert "G5.golden-master" in gates_present


def test_write_gate_ledger_failed_path(tmp_path: Path) -> None:
    """Must be callable on the fail path too; status is taken verbatim."""
    result = _golden_master_result(
        status="failed", exit_code=_common.Exit.GOLDEN_MASTER
    )
    out = _common.write_gate_ledger(result, tmp_path, attempt=3)

    payload = json.loads(out.read_text(encoding="utf-8"))
    entry = GateLedgerEntry.from_dict(payload)
    assert entry.validate() == []
    assert entry.status == "failed"
    assert entry.summary["exit_code"] == _common.Exit.GOLDEN_MASTER
    assert entry.summary["errors"][0]["code"] == "gm.mismatch"

    entries, read_errors = _common.load_gate_ledger(tmp_path)
    assert read_errors == []
    assert sorted({e.gate for e in entries}) == ["G5.golden-master"]


def test_write_gate_ledger_derives_gate_from_command(tmp_path: Path) -> None:
    """When result.gate is unset, the gate id is derived from the catalogue."""
    result = _common.build_result(
        command="extract",  # -> P-Q1.quellfragment in ALL_GATES
        gate_version="1.0.0",
        exit_code=_common.Exit.OK,
        input_hashes={"generated/x.py": "c" * 64},
    )
    out = _common.write_gate_ledger(result, tmp_path)
    entry = GateLedgerEntry.from_dict(json.loads(out.read_text(encoding="utf-8")))
    assert entry.gate == "P-Q1.quellfragment"
    assert entry.required is True
    assert entry.validate() == []


def test_write_gate_ledger_creates_diagnostics_dir(tmp_path: Path) -> None:
    nested = tmp_path / "runs" / "r1" / "diagnostics"
    result = _golden_master_result(status="passed", exit_code=_common.Exit.OK)
    out = _common.write_gate_ledger(result, nested)
    assert out.is_file()
    assert nested.is_dir()


def test_write_gate_ledger_records_command_line(tmp_path: Path) -> None:
    result = _golden_master_result(status="passed", exit_code=_common.Exit.OK)
    out = _common.write_gate_ledger(
        result, tmp_path, command_line=["python", "-m", "x.golden_master", "--flag"]
    )
    entry = GateLedgerEntry.from_dict(json.loads(out.read_text(encoding="utf-8")))
    assert entry.summary["command_line"] == [
        "python",
        "-m",
        "x.golden_master",
        "--flag",
    ]


@pytest.mark.parametrize(
    ("feld", "wert"),
    [
        ("required", "false"),
        ("attempt", True),
        ("schema_version", 999),
        ("input_hashes", {"x": "kein-hash"}),
    ],
)
def test_load_gate_ledger_lehnt_schema_manipulation_ab(
    tmp_path: Path, feld: str, wert: object
) -> None:
    result = _golden_master_result(status="passed", exit_code=_common.Exit.OK)
    pfad = _common.write_gate_ledger(result, tmp_path)
    payload = json.loads(pfad.read_text(encoding="utf-8"))
    payload[feld] = wert
    pfad.write_text(json.dumps(payload), encoding="utf-8")

    entries, read_errors = _common.load_gate_ledger(tmp_path)

    assert entries == []
    assert len(read_errors) == 1
    assert "ungueltiger Gate-Ledger" in read_errors[0]["error"]


def test_load_gate_ledger_lehnt_fremdes_feld_ab(tmp_path: Path) -> None:
    result = _golden_master_result(status="passed", exit_code=_common.Exit.OK)
    pfad = _common.write_gate_ledger(result, tmp_path)
    payload = json.loads(pfad.read_text(encoding="utf-8"))
    payload["nachtraeglich_gruen"] = True
    pfad.write_text(json.dumps(payload), encoding="utf-8")

    entries, read_errors = _common.load_gate_ledger(tmp_path)

    assert entries == []
    assert "unknown fields" in read_errors[0]["error"]


def test_load_gate_ledger_lehnt_negative_laufzeit_ab(tmp_path: Path) -> None:
    result = _golden_master_result(status="passed", exit_code=_common.Exit.OK)
    pfad = _common.write_gate_ledger(result, tmp_path)
    payload = json.loads(pfad.read_text(encoding="utf-8"))
    payload["summary"]["ended_at"] = "2000-01-01T00:00:00+00:00"
    pfad.write_text(json.dumps(payload), encoding="utf-8")

    entries, read_errors = _common.load_gate_ledger(tmp_path)

    assert payload["summary"]["ended_at"] < payload["started_at"]
    assert entries == []
    assert "must not precede" in read_errors[0]["error"]


def test_gate_katalog_traegt_die_tatsaechlichen_vertrags_ids() -> None:
    katalog, _ = _common._gate_catalogue()
    assert katalog["abox_validate"] == "P-Q3.fachliche-pruefung"
    assert katalog["generation_golden"] == "P-K1.generations-golden-master"
    assert katalog["bestand_validate"] == "P-B1.bestandspruefung"
    assert katalog["abnahmebericht"] == "A-M4.migrationscontrolling"


# --------------------------------------------------------------------------- #
# Fix 2 — UTF-8 stdout, emit cannot crash
# --------------------------------------------------------------------------- #

# A BOM (U+FEFF) plus an em-dash — both unrepresentable in cp1252 (the BOM is;
# the em-dash IS in cp1252 but the combination + a real non-cp1252 char below is).
_BOM = "﻿"
_NON_CP1252 = "☃"  # SNOWMAN — not in cp1252


class _Cp1252Stream(io.TextIOBase):
    """A text stream that encodes to cp1252 and exposes a UTF-8-capable buffer.

    Models a Windows console default code page: writing a non-cp1252 char raises
    ``UnicodeEncodeError`` unless reconfigured. ``reconfigure(encoding=...)`` and
    ``buffer`` are supported so :func:`_common.emit_json` can recover.
    """

    def __init__(self) -> None:
        self.buffer = io.BytesIO()
        self._encoding = "cp1252"

    @property
    def encoding(self) -> str:  # type: ignore[override]
        return self._encoding

    def reconfigure(self, *, encoding: str | None = None, **_: object) -> None:
        if encoding is not None:
            self._encoding = encoding

    def write(self, s: str) -> int:
        # Raises UnicodeEncodeError for non-cp1252 chars while encoding is cp1252.
        self.buffer.write(s.encode(self._encoding))
        return len(s)

    def flush(self) -> None:  # pragma: no cover - trivial
        pass

    def getvalue_utf8(self) -> bytes:
        return self.buffer.getvalue()


def _result_with_unicode() -> _common.ToolboxResult:
    return _common.build_result(
        command="golden_master",
        gate="G5.golden-master",
        gate_version="1.0.0",
        exit_code=_common.Exit.OK,
        summary={"note": f"{_BOM}snowman {_NON_CP1252} ok"},
    )


def test_emit_json_recovers_via_reconfigure() -> None:
    """A cp1252 stream is reconfigured to UTF-8 so emission never crashes."""
    stream = _Cp1252Stream()
    _common.emit_json(_result_with_unicode().to_dict(), stream=stream)

    raw = stream.getvalue_utf8()
    decoded = raw.decode("utf-8")
    obj = json.loads(decoded)
    assert obj["summary"]["note"] == f"{_BOM}snowman {_NON_CP1252} ok"


def test_emit_json_falls_back_to_buffer_when_reconfigure_unavailable() -> None:
    """A cp1252 stream with no reconfigure still emits valid UTF-8 via .buffer."""

    class _NoReconfigure(_Cp1252Stream):
        reconfigure = None  # type: ignore[assignment]

    stream = _NoReconfigure()
    _common.emit_json(_result_with_unicode().to_dict(), stream=stream)
    obj = json.loads(stream.getvalue_utf8().decode("utf-8"))
    assert obj["summary"]["note"].endswith("ok")


def test_emit_json_pure_text_sink_falls_back_to_ascii() -> None:
    """A pure text sink (no buffer, cp1252, no working reconfigure) still emits
    valid JSON (ASCII-escaped) rather than raising."""

    class _PureText(io.TextIOBase):
        def __init__(self) -> None:
            self._parts: list[str] = []

        def reconfigure(self, **_: object) -> None:
            # Pretend reconfigure does nothing (encoding stays cp1252-like).
            pass

        def write(self, s: str) -> int:
            s.encode("cp1252")  # raises UnicodeEncodeError on non-cp1252
            self._parts.append(s)
            return len(s)

        def value(self) -> str:
            return "".join(self._parts)

    stream = _PureText()
    _common.emit_json(_result_with_unicode().to_dict(), stream=stream)
    obj = json.loads(stream.value())
    # ASCII-escaped fallback still yields the same logical content.
    assert obj["summary"]["note"] == f"{_BOM}snowman {_NON_CP1252} ok"


def test_run_command_emits_valid_json_with_unicode(monkeypatch: pytest.MonkeyPatch) -> None:
    """End-to-end: run_command with a cp1252 stdout emits valid UTF-8 JSON and
    the correct exit code — no UnicodeEncodeError, no empty stdout."""
    fake_stdout = _Cp1252Stream()
    monkeypatch.setattr("sys.stdout", fake_stdout)

    def main(argv: object) -> _common.ToolboxResult:
        return _result_with_unicode()

    exit_code = _common.run_command(main, argv=[])
    assert exit_code == _common.Exit.OK

    raw = fake_stdout.getvalue_utf8()
    assert raw, "stdout must not be empty"
    obj = json.loads(raw.decode("utf-8"))
    assert obj["command"] == "golden_master"
    assert obj["exit_code"] == 0
    assert obj["summary"]["note"] == f"{_BOM}snowman {_NON_CP1252} ok"


def test_run_command_failed_unicode_result_exit_code(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """The fail path also emits valid JSON with the blocking exit code."""
    fake_stdout = _Cp1252Stream()
    monkeypatch.setattr("sys.stdout", fake_stdout)

    def main(argv: object) -> _common.ToolboxResult:
        return _common.build_result(
            command="golden_master",
            gate="G5.golden-master",
            gate_version="1.0.0",
            exit_code=_common.Exit.GOLDEN_MASTER,
            summary={"note": f"{_NON_CP1252}"},
        )

    exit_code = _common.run_command(main, argv=[])
    assert exit_code == _common.Exit.GOLDEN_MASTER
    obj = json.loads(fake_stdout.getvalue_utf8().decode("utf-8"))
    assert obj["status"] == "failed"
    assert obj["exit_code"] == _common.Exit.GOLDEN_MASTER


def test_force_utf8_stream_handles_none_and_missing_reconfigure() -> None:
    assert _common.force_utf8_stream(None) is None
    plain = io.StringIO()  # no reconfigure attribute
    assert _common.force_utf8_stream(plain) is plain


# --------------------------------------------------------------------------- #
# Der Laufverlauf je Kommando
# --------------------------------------------------------------------------- #


def _fahre_gate(diagnostics: Path, *, status: str, exit_code: int):
    """Einen vollstaendigen Gate-Lauf simulieren (beginnen, abschliessen)."""
    fehlstart = _common.begin_gate_ledger_attempt(
        command="golden_master",
        gate="G5.golden-master",
        gate_version="1.0.0",
        diagnostics_dir=diagnostics,
    )
    assert fehlstart is None
    return _common.finalize_gate_ledger(
        _golden_master_result(status=status, exit_code=exit_code))


def test_die_rot_historie_eines_kommandos_bleibt_erhalten(tmp_path: Path):
    """Das Ledger traegt den GELTENDEN Stand und wird ersetzt — sonst
    laege ein ueberholtes Urteil als aktueller Beleg herum. Die Folge war
    aber, dass jedes Ledger auf "bestanden, erster Versuch" stand, auch
    nach einem Lauf, der mehrfach zurueckschleifen musste. Damit verlor
    die Ablage genau das, was ein Migrationslauf an Erkenntnis erzeugt:
    wo es geklemmt hat.
    """
    _fahre_gate(tmp_path, status="failed", exit_code=_common.Exit.GOLDEN_MASTER)
    _fahre_gate(tmp_path, status="failed", exit_code=_common.Exit.GOLDEN_MASTER)
    _fahre_gate(tmp_path, status="passed", exit_code=_common.Exit.OK)

    historie = _common.lies_gate_historie(tmp_path, "golden_master")
    assert [e["versuch"] for e in historie] == [1, 2, 3]
    assert [e["status"] for e in historie] == ["failed", "failed", "passed"]
    assert historie[0]["fehler"] == ["gm.mismatch"]
    assert historie[-1]["fehler"] == []

    # Das Ledger selbst traegt weiter NUR den geltenden Stand — und seine
    # Versuchsnummer ist jetzt wahr statt immer 1.
    ledger = json.loads(
        (tmp_path / f"golden_master{_common.GATE_LEDGER_SUFFIX}")
        .read_text(encoding="utf-8"))
    assert ledger["status"] == "passed"
    assert ledger["attempt"] == 3


def test_ohne_lauf_gibt_es_keine_historie(tmp_path: Path):
    assert _common.lies_gate_historie(tmp_path, "golden_master") == []


def test_eine_unlesbare_historienzeile_haelt_kein_gate_auf(tmp_path: Path):
    """Die Historie ist ein Zusatzbeleg, kein Vertrag. Sie darf einen
    Gate-Lauf niemals aufhalten — sonst waere die Beobachtung teurer als
    das Beobachtete."""
    pfad = _common.gate_historie_pfad(tmp_path, "golden_master")
    pfad.write_text('{"versuch": 1, "status": "failed"}\nkein json\n\n',
                    encoding="utf-8")

    assert len(_common.lies_gate_historie(tmp_path, "golden_master")) == 1

    ergebnis = _fahre_gate(tmp_path, status="passed", exit_code=_common.Exit.OK)
    assert ergebnis.exit_code == _common.Exit.OK
    # Die kaputte Zeile wird uebersprungen, nicht repariert: Der neue Lauf
    # zaehlt als zweiter, weil eine lesbare Zeile vorlag.
    historie = _common.lies_gate_historie(tmp_path, "golden_master")
    assert [e["versuch"] for e in historie] == [1, 2]
