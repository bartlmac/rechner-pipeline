"""
Fester Golden-Master-Harness (reviewter Code, NICHT LLM-generiert).

Validiert den generierten Rechenkern gegen die deterministisch aus dem Excel
extrahierten Erwartungswerte (``info_from_excel/*_scalar.json`` und
``*_table_values.csv``). Ersetzt den bisher pro Lauf LLM-generierten
``test_run_advanced.py`` (siehe ``dev/CR-002-fixed-golden-master-harness.md``).

**Contract:** Der generierte Rechenkern muss in ``test_run.py`` eine Funktion
``golden_master_outputs() -> dict`` exponieren, die die berechneten Werte mit
Namen identisch zu den Erwartungsdateien liefert::

    {
      "scalars": {"<prefix>": {"<name>": <float>, ...}},
      "tables":  {"<prefix>": [ {"<spalte>": <float>, ...}, ... ]},
    }

Die Vergleichs-Engine selbst ist idiom-stabil und unabhängig von der
LLM-gewählten Implementierung -- sie ordnet ausschließlich über die Namen in
den Erwartungsdateien zu.

**Migrationsfix (§2.6 / §4.2 Schritt 6).** Die AS-IS-Engine wertete
``Report.ok`` nur über ``deviations`` aus und ignorierte ``unmatched_columns``;
zudem konnte ein Lauf ohne jeden Vergleich ("zero comparison") fälschlich als
bestanden ("false green") gemeldet werden. Beide Falsch-Akzeptanzen sind hier
behoben:

* Jede erwartete Spalte mit Daten, die im berechneten Output nicht zugeordnet
  werden kann, ist jetzt eine **harte Abweichung** (``Report.ok`` ist False).
* ``Report.compared_anything`` macht sichtbar, ob überhaupt ein Skalar oder
  eine Tabellenzelle verglichen wurde. Der ``golden_master``-Befehl wertet das
  als Coverage-Frage (sparse/none) aus und akzeptiert einen Null-Vergleich
  nicht als vollwertigen Golden-Master.
"""

from __future__ import annotations

import csv
import json
import sys
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

ROUND_DECIMALS = 4


def _norm_colname(name: str) -> str:
    """Trennzeichen entfernen, Groß-/Kleinschreibung BEHALTEN (case-sensitiv).

    `Axn` und `A_xn` gelten als gleich, `Axn` und `axn` NICHT.
    """
    return name.replace("_", "").replace(" ", "").replace(".", "")


def _to_float(x: Any) -> Optional[float]:
    if x is None or x == "":
        return None
    try:
        return float(x)
    except (TypeError, ValueError):
        return None


def _eq4(a: float, b: float) -> bool:
    return round(a, ROUND_DECIMALS) == round(b, ROUND_DECIMALS)


# --- Erwartungswerte laden -------------------------------------------------


def load_expected_scalars(info_dir: Path) -> Dict[str, Dict[str, Optional[float]]]:
    out: Dict[str, Dict[str, Optional[float]]] = {}
    for p in sorted(info_dir.glob("*_scalar.json")):
        prefix = p.name[: -len("_scalar.json")]
        data = json.loads(p.read_text(encoding="utf-8"))
        out[prefix] = {k: _to_float(v) for k, v in data.items()}
    return out


def load_expected_tables(info_dir: Path) -> Dict[str, Tuple[List[str], List[Dict[str, str]]]]:
    out: Dict[str, Tuple[List[str], List[Dict[str, str]]]] = {}
    for p in sorted(info_dir.glob("*_table_values.csv")):
        prefix = p.name[: -len("_table_values.csv")]
        with p.open(encoding="utf-8", newline="") as f:
            reader = csv.DictReader(f)
            header = list(reader.fieldnames or [])
            rows = [dict(r) for r in reader]
        out[prefix] = (header, rows)
    return out


# --- Vergleich -------------------------------------------------------------


@dataclass
class Report:
    scalars_tested: int = 0
    scalars_skipped: int = 0
    table_cells_tested: int = 0
    unmatched_columns: List[str] = field(default_factory=list)
    deviations: List[str] = field(default_factory=list)
    # je Skalar: (prefix, name, erwartet, berechnet, status) — für die Anzeige
    scalar_rows: List[Tuple[str, str, Optional[float], Optional[float], str]] = field(
        default_factory=list
    )
    # Tabellen-Stichprobe: (prefix, spalte, zeile, erwartet, berechnet, status)
    table_samples: List[Tuple[str, str, int, Optional[float], Optional[float], str]] = field(
        default_factory=list
    )

    @property
    def ok(self) -> bool:
        """Gate-Verdikt OHNE die AS-IS-Falsch-Akzeptanz.

        FIX (§2.6): Eine erwartete Spalte mit Daten, die nicht zugeordnet werden
        kann, ist eine harte Abweichung. Der AS-IS-Code prüfte nur
        ``self.deviations`` und ließ ``unmatched_columns`` durchrutschen
        (false-green). ``ok`` ist jetzt nur True, wenn weder echte Abweichungen
        noch nicht zugeordnete erwartete Spalten vorliegen.

        Hinweis: Die Null-Vergleichs-Coverage (``compared_anything``) wird hier
        bewusst NICHT eingerechnet -- der ``golden_master``-Befehl behandelt sie
        als Coverage-/Human-Review-Frage (exit 31), nicht als Abweichung.
        """
        return not self.deviations and not self.unmatched_columns

    @property
    def compared_anything(self) -> bool:
        """True, wenn mindestens ein Skalar oder eine Tabellenzelle verglichen wurde.

        Ein Lauf mit ``compared_anything == False`` hat keine numerische
        Validierung geleistet (z. B. keine Erwartungsdateien vorhanden) und darf
        laut §2.6 NICHT als vollwertiger Golden-Master akzeptiert werden.
        """
        return (self.scalars_tested + self.table_cells_tested) > 0

    def render(self) -> str:
        lines = [
            "=" * 60,
            "GOLDEN-MASTER (fester Harness)",
            "=" * 60,
            f"  Skalare:      getestet={self.scalars_tested} "
            f"übersprungen={self.scalars_skipped}",
            f"  Tabellen:     Zellen getestet={self.table_cells_tested} "
            f"nicht zugeordnete Spalten={len(self.unmatched_columns)}",
            f"  Abweichungen: {len(self.deviations)}",
        ]
        for d in self.deviations[:20]:
            lines.append(f"    ABWEICHUNG: {d}")
        if len(self.deviations) > 20:
            lines.append(f"    … +{len(self.deviations) - 20} weitere")
        if self.unmatched_columns:
            lines.append(f"  nicht zugeordnet: {', '.join(self.unmatched_columns[:10])}")
        for prefix, name, ev, cv, status in self.scalar_rows:
            lines.append(
                f"  SKALAR: {prefix}:{name} status={status} erwartet={ev} berechnet={cv}"
            )
        for prefix, col, ri, ev, cv, status in self.table_samples:
            lines.append(
                f"  TABELLE: {prefix}:{col}[{ri}] status={status} erwartet={ev} berechnet={cv}"
            )
        total = self.scalars_tested + self.table_cells_tested
        lines.append(
            f"  RESULT: {'ALLE ' + str(total) + ' TESTS BESTANDEN' if self.ok else 'FEHLGESCHLAGEN'}"
        )
        return "\n".join(lines)


def _compare_scalars(expected, computed, report: Report) -> None:
    for prefix, exp in expected.items():
        comp = (computed.get("scalars") or {}).get(prefix, {})
        for name, ev in exp.items():
            if ev is None:
                report.scalars_skipped += 1
                report.scalar_rows.append((prefix, name, None, None, "kein-soll"))
                continue
            cv = _to_float(comp.get(name))
            if cv is None:
                report.deviations.append(f"{prefix}:{name} ohne berechneten Wert")
                report.scalar_rows.append((prefix, name, ev, None, "fehlt"))
                continue
            report.scalars_tested += 1
            if not _eq4(cv, ev):
                report.deviations.append(
                    f"{prefix}:{name} berechnet={cv} erwartet={ev}"
                )
                report.scalar_rows.append((prefix, name, ev, cv, "abw"))
            else:
                report.scalar_rows.append((prefix, name, ev, cv, "ok"))


def _compare_tables(expected, computed, report: Report) -> None:
    for prefix, (header, rows) in expected.items():
        comp_rows = (computed.get("tables") or {}).get(prefix, [])
        comp_cols = set()
        for r in comp_rows:
            comp_cols.update(r.keys())
        norm_to_comp: Dict[str, str] = {}
        for c in comp_cols:
            norm_to_comp.setdefault(_norm_colname(c), c)

        for col in header:
            ccol = norm_to_comp.get(_norm_colname(col))
            col_has_data = any((row.get(col) or "") != "" for row in rows)
            if ccol is None:
                if col_has_data:
                    report.unmatched_columns.append(f"{prefix}:{col}")
                continue
            for ri, erow in enumerate(rows):
                ev = _to_float(erow.get(col))
                if ev is None:
                    continue
                cv = _to_float(comp_rows[ri].get(ccol)) if ri < len(comp_rows) else None
                report.table_cells_tested += 1
                if cv is None or not _eq4(cv, ev):
                    report.deviations.append(
                        f"{prefix}:{col}[{ri}] berechnet={cv} erwartet={ev}"
                    )
                    status = "fehlt" if cv is None else "abw"
                else:
                    status = "ok"
                # Rohmaterial für die Anzeige (erste Zeilen, mehrere Spalten);
                # die Begrenzung auf konkrete Zeilen/Spalten macht die Anzeige-Seite
                if ri < 20 and len(report.table_samples) < 400:
                    report.table_samples.append((prefix, col, ri, ev, cv, status))


def compare(expected: Dict[str, Any], computed: Dict[str, Any]) -> Report:
    report = Report()
    _compare_scalars(expected.get("scalars", {}), computed, report)
    _compare_tables(expected.get("tables", {}), computed, report)
    return report


def load_expected(info_dir: Path) -> Dict[str, Any]:
    return {
        "scalars": load_expected_scalars(info_dir),
        "tables": load_expected_tables(info_dir),
    }


# --- Launcher (wird von run_compare via fs_confine ausgeführt) -------------


def main() -> None:
    generated = Path.cwd()
    repo_root = generated.parent
    info_dir = repo_root / "info_from_excel"

    sys.path.insert(0, str(generated))
    try:
        import test_run  # generierter Rechenkern
    except Exception as exc:
        print(f"[FAIL] Konnte generierten Rechenkern (test_run) nicht importieren: {exc}")
        raise SystemExit(2)

    if not hasattr(test_run, "golden_master_outputs"):
        print(
            "[FAIL] Contract verletzt: test_run.golden_master_outputs() fehlt. "
            "Der Rechenkern muss berechnete Werte über diese Funktion liefern "
            "(siehe dev/CR-002)."
        )
        raise SystemExit(3)

    computed = test_run.golden_master_outputs()
    expected = load_expected(info_dir)
    report = compare(expected, computed)
    print(report.render())
    raise SystemExit(0 if report.ok else 1)


if __name__ == "__main__":  # pragma: no cover
    main()
