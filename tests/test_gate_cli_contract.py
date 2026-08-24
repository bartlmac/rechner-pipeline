"""Gemeinsamer Argumentfehler-Vertrag aller Gate-CLIs.

Knoten: system/assurance
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Callable, List, Optional

import pytest

from rechner_pipeline.gates import (
    abnahmebericht,
    abox_merge,
    abox_validate,
    bestand_validate,
    extract,
    gate_entscheid,
    generation_golden,
)
from rechner_pipeline.gates._common import Exit, ToolboxResult, run_command
from rechner_pipeline.models.schemas import GateLedgerEntry

GateMain = Callable[[Optional[List[str]]], ToolboxResult]


GATE_CLIS = (
    pytest.param(
        extract.main,
        "extract",
        "G0.extraction-manifest",
        Exit.EXTRACTION,
        ["--adapter", "unbekannt"],
        id="g0-extract",
    ),
    pytest.param(
        abox_merge.main,
        "abox_merge",
        "O0.abox-merge",
        Exit.USAGE,
        ["--unbekannt"],
        id="o0-abox-merge",
    ),
    pytest.param(
        abox_validate.main,
        "abox_validate",
        "O1.abox-contract",
        Exit.USAGE,
        ["--unbekannt"],
        id="o1-abox-validate",
    ),
    pytest.param(
        generation_golden.main,
        "generation_golden",
        "O3.generation-golden-master",
        Exit.USAGE,
        ["--unbekannt"],
        id="o3-generation-golden",
    ),
    pytest.param(
        gate_entscheid.main,
        "gate_entscheid",
        "P9.?",
        Exit.USAGE,
        ["--gate", "ungueltig"],
        id="p9-gate-entscheid",
    ),
    pytest.param(
        bestand_validate.main,
        "bestand_validate",
        "B1.bestand-contract",
        Exit.USAGE,
        ["--unbekannt"],
        id="b1-bestand-validate",
    ),
    pytest.param(
        abnahmebericht.main,
        "abnahmebericht",
        "G2-vorlage.migrationsabnahme",
        Exit.USAGE,
        ["--unbekannt"],
        id="g2-abnahmebericht",
    ),
)


def _assert_usage_contract(
    *,
    exit_code: int,
    stdout: str,
    ledger_path: Path,
    command: str,
    gate: str,
    expected_exit: int = Exit.USAGE,
) -> None:
    lines = stdout.splitlines()
    assert len(lines) == 1
    result = json.loads(lines[0])
    assert result["command"] == command
    assert result["gate"] == gate
    assert result["status"] == "failed"
    assert result["exit_code"] == expected_exit == exit_code
    assert len(result["errors"]) == 1

    ledger = GateLedgerEntry.from_dict(
        json.loads(ledger_path.read_text(encoding="utf-8"))
    )
    assert ledger.validate() == []
    assert ledger.command == command
    assert ledger.gate == gate
    assert ledger.status == "failed"
    assert ledger.summary["exit_code"] == expected_exit
    assert len(ledger.summary["errors"]) == 1


@pytest.mark.parametrize("main,command,gate,missing_exit,invalid_args", GATE_CLIS)
def test_fehlende_argumente_schreiben_genau_ein_json_und_roten_beleg(
    main: GateMain,
    command: str,
    gate: str,
    missing_exit: int,
    invalid_args: List[str],
    tmp_path: Path,
    capsys: pytest.CaptureFixture[str],
) -> None:
    del invalid_args
    diagnostics = tmp_path / "diagnostics"
    exit_code = run_command(
        main,
        ["--diagnostics-dir", str(diagnostics)],
    )

    captured = capsys.readouterr()
    _assert_usage_contract(
        exit_code=exit_code,
        stdout=captured.out,
        ledger_path=diagnostics / f"{command}.gate.json",
        command=command,
        gate=gate,
        expected_exit=missing_exit,
    )


@pytest.mark.parametrize("main,command,gate,missing_exit,invalid_args", GATE_CLIS)
def test_ungueltige_argumente_ersetzen_altgruen_durch_roten_beleg(
    main: GateMain,
    command: str,
    gate: str,
    missing_exit: int,
    invalid_args: List[str],
    tmp_path: Path,
    capsys: pytest.CaptureFixture[str],
) -> None:
    del missing_exit
    diagnostics = tmp_path / "diagnostics"
    diagnostics.mkdir()
    ledger_path = diagnostics / f"{command}.gate.json"
    ledger_path.write_text('{"status":"passed","stale":true}\n', encoding="utf-8")

    exit_code = run_command(
        main,
        ["--diagnostics-dir", str(diagnostics), *invalid_args],
    )

    captured = capsys.readouterr()
    _assert_usage_contract(
        exit_code=exit_code,
        stdout=captured.out,
        ledger_path=ledger_path,
        command=command,
        gate=gate,
    )
    assert "stale" not in json.loads(ledger_path.read_text(encoding="utf-8"))


@pytest.mark.parametrize("main,command,gate,missing_exit,invalid_args", GATE_CLIS)
def test_help_bleibt_erfolgreich_und_startet_keinen_gate_lauf(
    main: GateMain,
    command: str,
    gate: str,
    missing_exit: int,
    invalid_args: List[str],
    tmp_path: Path,
    capsys: pytest.CaptureFixture[str],
) -> None:
    del command, gate, missing_exit, invalid_args
    diagnostics = tmp_path / "diagnostics"

    with pytest.raises(SystemExit) as exc_info:
        run_command(
            main,
            ["--diagnostics-dir", str(diagnostics), "--help"],
        )

    captured = capsys.readouterr()
    assert exc_info.value.code == Exit.OK
    assert captured.out == ""
    assert "usage:" in captured.err
    assert not diagnostics.exists()


def test_kaputtes_request_json_ist_usage_statt_internal_error(
    tmp_path: Path,
    capsys: pytest.CaptureFixture[str],
) -> None:
    diagnostics = tmp_path / "diagnostics"
    request = tmp_path / "request.json"
    request.write_text("{kaputt", encoding="utf-8")

    exit_code = run_command(
        extract.main,
        [
            "--diagnostics-dir",
            str(diagnostics),
            "--request-json",
            str(request),
        ],
    )

    captured = capsys.readouterr()
    _assert_usage_contract(
        exit_code=exit_code,
        stdout=captured.out,
        ledger_path=diagnostics / "extract.gate.json",
        command="extract",
        gate="G0.extraction-manifest",
    )
    assert "--request-json" in json.loads(captured.out)["errors"][0]["message"]


def test_p9_parsefehler_bindet_gueltiges_gate_und_redigiert_schluesselpfad(
    tmp_path: Path,
    capsys: pytest.CaptureFixture[str],
) -> None:
    diagnostics = tmp_path / "diagnostics"
    geheim = tmp_path / "nicht-in-den-ledger.key"

    exit_code = run_command(
        gate_entscheid.main,
        [
            "--diagnostics-dir",
            str(diagnostics),
            "--gate",
            "G-2",
            "--rolle",
            "ungueltig",
            "--freigabe-schluessel",
            str(geheim),
        ],
    )

    captured = capsys.readouterr()
    ledger_path = diagnostics / "gate_entscheid_g2.gate.json"
    _assert_usage_contract(
        exit_code=exit_code,
        stdout=captured.out,
        ledger_path=ledger_path,
        command="gate_entscheid_g2",
        gate="P9.G-2",
    )
    ledger_text = ledger_path.read_text(encoding="utf-8")
    assert str(geheim) not in ledger_text
    assert "<extern-redigiert>" in ledger_text


def test_p9_request_json_mit_ungueltigem_gate_bleibt_im_diagnostics_ordner(
    tmp_path: Path,
    capsys: pytest.CaptureFixture[str],
) -> None:
    diagnostics = tmp_path / "diagnostics"
    request = tmp_path / "request.json"
    request.write_text(
        json.dumps(
            {
                "gate": "../../ausbruch",
                "entscheid": "abgelehnt",
                "rolle": "agent",
                "entscheider": "Agent",
                "begruendung": "ungueltige Testeingabe",
            }
        ),
        encoding="utf-8",
    )

    exit_code = run_command(
        gate_entscheid.main,
        [
            "--diagnostics-dir",
            str(diagnostics),
            "--request-json",
            str(request),
        ],
    )

    captured = capsys.readouterr()
    _assert_usage_contract(
        exit_code=exit_code,
        stdout=captured.out,
        ledger_path=diagnostics / "gate_entscheid.gate.json",
        command="gate_entscheid",
        gate="P9.?",
    )
    assert not (tmp_path / "ausbruch.gate.json").exists()
