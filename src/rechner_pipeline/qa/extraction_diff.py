"""
Vergleich zweier ``info_from_excel``-Extraktionen (z. B. COM vs. openpyxl).

Trennt **materielle** Unterschiede (andere Formeln/Werte, fehlende Zellen,
fehlende VBA-Module, abweichende Defined-Name-Werte) von **kosmetischen**
Unterschieden (``$`` in Adressen, ``int`` vs. ``float`` wie ``5`` vs ``5.0``,
fuehrendes ``=`` in ``RefersTo``, CRLF vs. LF, COM-spezifische Anreicherungs-
spalten im Name-Manager).

Genutzt als Golden-Master-Harness: ist der materielle Befund leer, sind beide
Backends funktional aequivalent — die verbleibenden Diffs sind reine Form.
"""

from __future__ import annotations

import csv
import math
from dataclasses import dataclass, field
from pathlib import Path
from typing import Dict, List, Optional, Tuple


def _try_float(s: str) -> Optional[float]:
    try:
        return float(s)
    except (TypeError, ValueError):
        return None


def tokens_equal(a: str, b: str) -> bool:
    """Vergleiche zwei Zell-/Feld-Token tolerant gegen Zahlformat."""
    a = (a or "").strip()
    b = (b or "").strip()
    if a == b:
        return True
    fa, fb = _try_float(a), _try_float(b)
    if fa is not None and fb is not None:
        return math.isclose(fa, fb, rel_tol=1e-9, abs_tol=1e-12)
    return False


def _norm_addr(addr: str) -> str:
    return (addr or "").replace("$", "").strip()


def _read_sheet_csv(path: Path) -> Dict[Tuple[str, str], Tuple[str, str]]:
    """(_Blatt_, _Adresse_) -> (_Formel_, _Wert_); Adresse ohne ``$``."""
    rows: Dict[Tuple[str, str], Tuple[str, str]] = {}
    with path.open(encoding="utf-8", newline="") as f:
        reader = csv.reader(f, delimiter=";")
        next(reader, None)  # header
        for r in reader:
            if len(r) < 4:
                continue
            rows[(r[0], _norm_addr(r[1]))] = (r[2], r[3])
    return rows


@dataclass
class FileDiff:
    name: str
    material: List[str] = field(default_factory=list)
    accepted: List[str] = field(default_factory=list)
    cosmetic: List[str] = field(default_factory=list)


@dataclass
class DiffReport:
    files: List[FileDiff] = field(default_factory=list)

    def material_count(self) -> int:
        return sum(len(f.material) for f in self.files)

    def accepted_count(self) -> int:
        return sum(len(f.accepted) for f in self.files)

    def cosmetic_count(self) -> int:
        return sum(len(f.cosmetic) for f in self.files)

    def has_material_differences(self) -> bool:
        return self.material_count() > 0

    def render(self, max_per_file: int = 12) -> str:
        out: List[str] = []
        out.append(
            f"Materielle Unterschiede: {self.material_count()} | "
            f"akzeptiert (Praezision/Range/intern): {self.accepted_count()} | "
            f"kosmetisch: {self.cosmetic_count()}"
        )
        for fd in self.files:
            if not (fd.material or fd.accepted or fd.cosmetic):
                out.append(f"  [=] {fd.name}: identisch (nach Normalisierung)")
                continue
            out.append(
                f"  [{'X' if fd.material else '~'}] {fd.name}: "
                f"{len(fd.material)} materiell, {len(fd.accepted)} akzeptiert, "
                f"{len(fd.cosmetic)} kosmetisch"
            )
            for line in fd.material[:max_per_file]:
                out.append(f"      MATERIELL: {line}")
            if len(fd.material) > max_per_file:
                out.append(f"      … +{len(fd.material) - max_per_file} weitere materielle")
            for line in fd.accepted[:5]:
                out.append(f"      akzeptiert: {line}")
            if len(fd.accepted) > 5:
                out.append(f"      … +{len(fd.accepted) - 5} weitere akzeptierte")
        return "\n".join(out)


def _close_precision(a: str, b: str) -> bool:
    """Gleiche Zahl bis auf Anzeige-/Rundungspraezision (~4 Dezimalen)."""
    fa, fb = _try_float(a), _try_float(b)
    if fa is None or fb is None:
        return False
    return math.isclose(fa, fb, rel_tol=1e-4, abs_tol=1e-3)


def compare_sheet_csv(name: str, com_path: Path, other_path: Path) -> FileDiff:
    fd = FileDiff(name=name)
    if not other_path.exists():
        fd.material.append("Datei fehlt im openpyxl-Output")
        return fd
    com = _read_sheet_csv(com_path)
    oth = _read_sheet_csv(other_path)

    only_com = sorted(set(com) - set(oth))
    only_oth = sorted(set(oth) - set(com))
    for key in only_com:
        fd.material.append(f"Adresse nur in COM: {key[0]}!{key[1]}")
    for key in only_oth:
        fd.material.append(f"Adresse nur in openpyxl: {key[0]}!{key[1]}")

    for key in sorted(set(com) & set(oth)):
        cf, cv = com[key]
        of, ov = oth[key]
        addr = f"{key[0]}!{key[1]}"
        f_eq = tokens_equal(cf, of)
        v_eq = tokens_equal(cv, ov)
        if f_eq and v_eq:
            # exakt-gleich? sonst kosmetisch (Zahlformat/$)
            if (cf, cv) != (of, ov):
                fd.cosmetic.append(f"{addr}: Format Formel/Wert ({cf!r}/{cv!r} vs {of!r}/{ov!r})")
            continue
        if not f_eq:
            fd.material.append(f"{addr}: Formel {cf!r} vs {of!r}")
        if not v_eq:
            if _close_precision(cv, ov):
                fd.accepted.append(f"{addr}: Wert-Praezision {cv!r} vs {ov!r}")
            else:
                fd.material.append(f"{addr}: Wert {cv!r} vs {ov!r}")
    return fd


def _read_lines_universal(path: Path) -> List[str]:
    text = path.read_text(encoding="utf-8", errors="replace")
    lines = [ln.rstrip() for ln in text.splitlines()]
    while lines and lines[-1] == "":
        lines.pop()
    return lines


def compare_vba(com_dir: Path, other_dir: Path) -> FileDiff:
    fd = FileDiff(name="vba/")
    com_vba = com_dir / "vba"
    oth_vba = other_dir / "vba"
    com_mods = {p.name for p in com_vba.glob("*.txt")} if com_vba.is_dir() else set()
    oth_mods = {p.name for p in oth_vba.glob("*.txt")} if oth_vba.is_dir() else set()

    for m in sorted(com_mods - oth_mods):
        fd.material.append(f"VBA-Modul nur in COM: {m}")
    for m in sorted(oth_mods - com_mods):
        fd.material.append(f"VBA-Modul nur in openpyxl: {m}")

    for m in sorted(com_mods & oth_mods):
        cl = _read_lines_universal(com_vba / m)
        ol = _read_lines_universal(oth_vba / m)
        if cl == ol:
            continue
        if len(cl) != len(ol):
            fd.material.append(f"{m}: Zeilenzahl {len(cl)} vs {len(ol)}")
        diffs = [i for i in range(min(len(cl), len(ol))) if cl[i] != ol[i]]
        if diffs:
            i = diffs[0]
            fd.material.append(
                f"{m}: erste Abweichung Zeile {i + 1}: {cl[i]!r} vs {ol[i]!r} "
                f"(+{len(diffs)} Zeilen gesamt)"
            )
    return fd


def _read_names_csv(path: Path) -> Dict[str, Dict[str, str]]:
    out: Dict[str, Dict[str, str]] = {}
    with path.open(encoding="utf-8", newline="") as f:
        reader = csv.DictReader(f, delimiter=";")
        for row in reader:
            out[row.get("Name", "")] = row
    return out


def _norm_refers_to(s: str) -> str:
    s = (s or "").strip()
    if s.startswith("="):
        s = s[1:]
    return s


def compare_names_csv(com_path: Path, other_path: Path) -> FileDiff:
    fd = FileDiff(name="names_manager.csv")
    if not other_path.exists():
        fd.material.append("Datei fehlt im openpyxl-Output")
        return fd
    com = _read_names_csv(com_path)
    oth = _read_names_csv(other_path)

    for nm in sorted(set(com) - set(oth)):
        bucket = fd.accepted if nm.startswith("_xl") else fd.material
        bucket.append(f"Name nur in COM: {nm}")
    for nm in sorted(set(oth) - set(com)):
        bucket = fd.accepted if nm.startswith("_xl") else fd.material
        bucket.append(f"Name nur in openpyxl: {nm}")

    for nm in sorted(set(com) & set(oth)):
        c, o = com[nm], oth[nm]
        ce, oe = c.get("ValueEvaluated", ""), o.get("ValueEvaluated", "")
        if not tokens_equal(ce, oe):
            # Akzeptiert: COM-evaluierter Mehrzell-Bereich (RefersTo = Range) bzw.
            # interner _xl-Name. Die Referenz bleibt via RefersTo erhalten, die
            # Werte stehen in den Sheet-CSVs -> kein Informationsverlust.
            is_range = ":" in _norm_refers_to(c.get("RefersTo", ""))
            if nm.startswith("_xl") or (is_range and oe.strip() == ""):
                fd.accepted.append(f"{nm}: ValueEvaluated nur in COM (Range/intern)")
            else:
                fd.material.append(
                    f"{nm}: ValueEvaluated {ce!r} vs {oe!r}"
                )
        if _norm_refers_to(c.get("RefersTo", "")) != _norm_refers_to(o.get("RefersTo", "")):
            fd.material.append(
                f"{nm}: RefersTo {c.get('RefersTo','')!r} vs {o.get('RefersTo','')!r}"
            )
        # Anreicherungs-/Quirk-Spalten: nur kosmetisch vermerken
        for col in ("Scope", "Visible", "RefersToLocal", "RefersToRangeAddress", "Comment"):
            if (c.get(col, "") or "") != (o.get(col, "") or ""):
                fd.cosmetic.append(
                    f"{nm}.{col}: {c.get(col,'')!r} vs {o.get(col,'')!r}"
                )
    return fd


# Roh-Sheet-CSVs = alles ausser den abgeleiteten/anreichernden Dateien.
_DERIVED_SUFFIXES = ("_compressed.csv", "_scalar.json", "_table_values.csv")


def _sheet_csv_names(com_dir: Path) -> List[str]:
    names: List[str] = []
    for p in sorted(com_dir.glob("*.csv")):
        if p.name == "names_manager.csv":
            continue
        if any(p.name.endswith(s) for s in _DERIVED_SUFFIXES):
            continue
        names.append(p.name)
    return names


def compare_dirs(com_dir: Path, other_dir: Path) -> DiffReport:
    """Vergleiche COM- und openpyxl-``info_from_excel``-Verzeichnisse.

    Verglichen werden die Roh-Artefakte (Sheet-CSVs, ``names_manager.csv``,
    ``vba/``). Abgeleitete Dateien (``*_compressed.csv``, ``*_scalar.json``,
    ``*_table_values.csv``) bleiben aussen vor, da sie aus identischem
    pure-python-Code entstehen und damit kein Backend-Merkmal sind.
    """
    com_dir = Path(com_dir)
    other_dir = Path(other_dir)
    report = DiffReport()

    for csv_name in _sheet_csv_names(com_dir):
        report.files.append(
            compare_sheet_csv(csv_name, com_dir / csv_name, other_dir / csv_name)
        )

    if (com_dir / "names_manager.csv").exists():
        report.files.append(
            compare_names_csv(
                com_dir / "names_manager.csv", other_dir / "names_manager.csv"
            )
        )

    report.files.append(compare_vba(com_dir, other_dir))
    return report


def main(argv: Optional[List[str]] = None) -> int:
    import argparse

    ap = argparse.ArgumentParser(
        prog="extraction-diff",
        description="Vergleiche zwei info_from_excel-Verzeichnisse (z. B. COM vs openpyxl).",
    )
    ap.add_argument("com_dir", help="Referenz (z. B. COM-Golden-Master)")
    ap.add_argument("other_dir", help="Vergleich (z. B. openpyxl-Lauf)")
    ns = ap.parse_args(argv)

    report = compare_dirs(Path(ns.com_dir), Path(ns.other_dir))
    print(report.render())
    return 1 if report.has_material_differences() else 0


if __name__ == "__main__":  # pragma: no cover
    raise SystemExit(main())

