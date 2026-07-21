"""Static AST security gate for LLM-generated calculation code (gate **G2**).

This module is the migrated + EXTENDED static security scanner (MIGRATION.md
§2.4 lines 1155-1204, §3.5 G2, disposition §4.1 "security.py MIGRATE"). It scans
generated Python *statically* (AST only -- it never imports or executes the
target code, MIGRATION.md §2.6) and reports every violation as
``file:line:column`` + rule id (``category``/``symbol``) + ``message``.

The AS-IS rule set (network/subprocess/dynamic-exec/write-I/O/filesystem) is
preserved verbatim. On top of it this gate adds three EXTENSION rule families
required by §3.5 G2 / §3.3 ``security`` row:

* ``nondeterministic`` -- time / random / environment-dependent calculation
  paths (``random``, ``time``, ``datetime.now``/``utcnow``/``today``,
  ``os.environ``/``os.getenv``, ``uuid``, ``secrets``, ...). A KLV calculation
  must be a pure function of its inputs; a wall-clock or RNG read makes the
  golden master non-reproducible.
* ``swallowed_exception`` -- bare ``except:`` and ``except Exception: pass``
  (and ``... : ...`` only) handlers that could hide a wrong calculation behind a
  silent fallback.
* ``self_approval`` -- generated-test self-approval patterns: a generated test
  that hard-codes ``assert True`` / ``pass`` instead of comparing values, or
  unconditionally writes its own "expected" outputs.

Public surface used by the toolbox command and tests:

* :func:`scan_python_source`, :func:`scan_python_items`, :func:`scan_python_paths`
* :class:`SecurityViolation`, :class:`StaticSecurityError`
* :func:`security_report`, :func:`write_security_report`, :func:`raise_for_violations`
* :data:`GATE_VERSION`, :data:`RULES` (the canonical id -> description map)
"""

from __future__ import annotations

import ast
import json
from dataclasses import dataclass
from pathlib import Path
from typing import Iterable


#: Bumped from the AS-IS implicit "1.0.0" to reflect the EXTENSION rule families.
GATE_VERSION = "2.0.0"


# --------------------------------------------------------------------------- #
# AS-IS rules (preserved verbatim from rechner-pipeline qa/security.py)
# --------------------------------------------------------------------------- #

DANGEROUS_IMPORT_ROOTS = {
    "ftplib": "network access",
    "http": "network access",
    "httpx": "network access",
    "importlib": "dynamic import",
    "pathlib": "filesystem access",
    "requests": "network access",
    "runpy": "dynamic execution",
    "shutil": "filesystem access",
    "socket": "network access",
    "subprocess": "subprocess execution",
    "tempfile": "filesystem access",
    "urllib": "network access",
}

# `import os` allein ist harmlos -- gefährlich sind erst konkrete Calls
# (os.system, os.remove, os.popen, ...), die weiterhin über DANGEROUS_CALL_
# PREFIXES blockiert werden. Reine os.path-Stringfunktionen führen KEIN
# Dateisystem-I/O aus (sie rechnen nur auf Pfad-Strings) und werden daher
# explizit erlaubt -- das ist präziser, nicht schwächer.
SAFE_CALL_NAMES = {
    "os.path.join",
    "os.path.dirname",
    "os.path.basename",
    "os.path.abspath",
    "os.path.normpath",
    "os.path.split",
    "os.path.splitext",
    "os.path.relpath",
    "os.path.commonpath",
    "os.path.commonprefix",
    "os.fspath",
    # Read-only Verzeichnis-Listing; Pfad-Scope via Laufzeit-Confinement.
    "glob.glob",
    "glob.iglob",
}

DANGEROUS_BUILTIN_CALLS = {
    "__import__": "dynamic import",
    "eval": "dynamic execution",
    "exec": "dynamic execution",
}
# `open` wird gesondert behandelt: Lesen ist erlaubt (Pfad-Scope erzwingt das
# Laufzeit-Confinement, qa.fs_confine), Schreib-/Append-Modi bleiben blockiert.
_OPEN_WRITE_FLAGS = ("w", "a", "x", "+")

FILESYSTEM_METHODS = {
    "chmod",
    "exists",
    "glob",
    "is_dir",
    "is_file",
    "iterdir",
    "mkdir",
    "open",
    "read_bytes",
    "read_text",
    "rename",
    "replace",
    "resolve",
    "rglob",
    "rmdir",
    "stat",
    "touch",
    "unlink",
    "write_bytes",
    "write_text",
}

DANGEROUS_CALL_PREFIXES = {
    "ftplib.",
    "glob.",
    "http.",
    "httpx.",
    "importlib.",
    "os.",
    "pathlib.",
    "requests.",
    "runpy.",
    "shutil.",
    "socket.",
    "subprocess.",
    "tempfile.",
    "urllib.",
}


# --------------------------------------------------------------------------- #
# EXTENSION rules (beyond AS-IS, required by §3.5 G2)
# --------------------------------------------------------------------------- #

#: Import roots that make a calculation non-deterministic (time / RNG / entropy /
#: environment). Category ``nondeterministic``.
NONDETERMINISTIC_IMPORT_ROOTS = {
    "random": "non-deterministic randomness",
    "secrets": "non-deterministic randomness",
    "uuid": "non-deterministic randomness",
    "time": "wall-clock time dependency",
}

#: Fully-qualified (alias-resolved) calls that read wall-clock time or the
#: environment. These are blocked even though their import root (``datetime``,
#: ``os``) is otherwise allowed. Category ``nondeterministic``.
NONDETERMINISTIC_CALL_NAMES = {
    "time.time": "wall-clock time dependency",
    "time.monotonic": "wall-clock time dependency",
    "time.perf_counter": "wall-clock time dependency",
    "time.process_time": "wall-clock time dependency",
    "time.localtime": "wall-clock time dependency",
    "time.gmtime": "wall-clock time dependency",
    "datetime.now": "wall-clock time dependency",
    "datetime.utcnow": "wall-clock time dependency",
    "datetime.today": "wall-clock time dependency",
    "datetime.datetime.now": "wall-clock time dependency",
    "datetime.datetime.utcnow": "wall-clock time dependency",
    "datetime.datetime.today": "wall-clock time dependency",
    "datetime.date.today": "wall-clock time dependency",
    "os.getenv": "environment dependency",
    "os.getenvb": "environment dependency",
    "os.urandom": "non-deterministic randomness",
}

#: Attribute access (not necessarily a call) that reads the environment.
#: ``os.environ[...]`` / ``os.environ.get(...)`` are both caught via the
#: ``os.environ`` attribute chain. Category ``nondeterministic``.
NONDETERMINISTIC_ATTRIBUTES = {
    "os.environ": "environment dependency",
}

#: Final-attribute method names that read wall-clock time on a ``datetime``-like
#: object regardless of how it was imported (``dt.now()`` after
#: ``from datetime import datetime as dt``). Category ``nondeterministic``.
NONDETERMINISTIC_METHODS = {
    "now": "wall-clock time dependency",
    "utcnow": "wall-clock time dependency",
}

#: Canonical rule registry: id -> human description. Exported so the
#: end-to-end-generation author knows exactly what generated KLV code must avoid.
RULES: dict[str, str] = {
    "dangerous_import": "Import of a network/subprocess/dynamic/filesystem module.",
    "dangerous_call": "Call enabling network, subprocess, dynamic exec/import, or write I/O.",
    "filesystem_access": "Filesystem method call (read/write/stat/listing) on a path object.",
    "nondeterministic": "Time/random/environment-dependent value in a calculation path.",
    "swallowed_exception": "Exception handler that silently swallows errors (hides wrong results).",
    "self_approval": "Generated test that self-approves instead of comparing real values.",
    "syntax_error": "Source could not be parsed.",
}


@dataclass(frozen=True)
class SecurityViolation:
    path: str
    line: int
    column: int
    category: str
    symbol: str
    message: str
    snippet: str = ""

    def to_dict(self) -> dict[str, object]:
        return {
            "path": self.path,
            "line": self.line,
            "column": self.column,
            "category": self.category,
            "symbol": self.symbol,
            "message": self.message,
            "snippet": self.snippet,
        }


class StaticSecurityError(RuntimeError):
    def __init__(self, violations: Iterable[SecurityViolation]) -> None:
        self.violations = list(violations)
        formatted = "; ".join(
            f"{Path(item.path).name}:{item.line}:{item.column} "
            f"{item.category} {item.symbol}"
            for item in self.violations[:5]
        )
        more = "" if len(self.violations) <= 5 else f"; +{len(self.violations) - 5} more"
        super().__init__(
            "Static security check failed for generated Python code: "
            f"{formatted}{more}"
        )


def _location(path: Path, node: ast.AST) -> tuple[str, int, int]:
    return str(path), int(getattr(node, "lineno", 0)), int(getattr(node, "col_offset", 0))


def _root(module: str) -> str:
    return module.split(".", 1)[0]


def _attribute_name(node: ast.AST) -> str | None:
    if isinstance(node, ast.Name):
        return node.id
    if isinstance(node, ast.Attribute):
        parent = _attribute_name(node.value)
        if parent:
            return f"{parent}.{node.attr}"
    return None


def _call_name(node: ast.AST, aliases: dict[str, str]) -> str | None:
    if isinstance(node, ast.Name):
        return aliases.get(node.id, node.id)
    if isinstance(node, ast.Attribute):
        parent = _call_name(node.value, aliases)
        if parent:
            return f"{parent}.{node.attr}"
        parent_attr = _attribute_name(node.value)
        if parent_attr:
            return f"{aliases.get(parent_attr, parent_attr)}.{node.attr}"
    if isinstance(node, ast.Call):
        called = _call_name(node.func, aliases)
        if called:
            return called
    return None


class _SecurityVisitor(ast.NodeVisitor):
    def __init__(self, path: Path, source_lines: list[str]) -> None:
        self.path = path
        self.source_lines = source_lines
        self.aliases: dict[str, str] = {}
        self.violations: list[SecurityViolation] = []

    # -- snippet + violation helper ---------------------------------------- #

    def _snippet(self, node: ast.AST) -> str:
        line = int(getattr(node, "lineno", 0))
        if 1 <= line <= len(self.source_lines):
            return self.source_lines[line - 1].strip()
        return ""

    def _add(self, node: ast.AST, *, category: str, symbol: str, message: str) -> None:
        path_str, line, column = _location(self.path, node)
        self.violations.append(
            SecurityViolation(
                path=path_str,
                line=line,
                column=column,
                category=category,
                symbol=symbol,
                message=message,
                snippet=self._snippet(node),
            )
        )

    # -- imports ----------------------------------------------------------- #

    def visit_Import(self, node: ast.Import) -> None:
        for alias in node.names:
            root = _root(alias.name)
            local_name = alias.asname or root
            self.aliases[local_name] = alias.name
            reason = DANGEROUS_IMPORT_ROOTS.get(root)
            if reason:
                self._add(
                    node,
                    category="dangerous_import",
                    symbol=alias.name,
                    message=f"Import is blocked because it enables {reason}.",
                )
            nd_reason = NONDETERMINISTIC_IMPORT_ROOTS.get(root)
            if nd_reason:
                self._add(
                    node,
                    category="nondeterministic",
                    symbol=alias.name,
                    message=f"Import is blocked because it introduces {nd_reason}.",
                )
        self.generic_visit(node)

    def visit_ImportFrom(self, node: ast.ImportFrom) -> None:
        module = node.module or ""
        root = _root(module)
        for alias in node.names:
            imported_name = f"{module}.{alias.name}" if module else alias.name
            local_name = alias.asname or alias.name
            self.aliases[local_name] = imported_name
        reason = DANGEROUS_IMPORT_ROOTS.get(root)
        if reason:
            self._add(
                node,
                category="dangerous_import",
                symbol=module,
                message=f"Import is blocked because it enables {reason}.",
            )
        nd_reason = NONDETERMINISTIC_IMPORT_ROOTS.get(root)
        if nd_reason:
            self._add(
                node,
                category="nondeterministic",
                symbol=module,
                message=f"Import is blocked because it introduces {nd_reason}.",
            )
        self.generic_visit(node)

    # -- calls ------------------------------------------------------------- #

    def visit_Call(self, node: ast.Call) -> None:
        name = _call_name(node.func, self.aliases)
        if name:
            self._check_call(node, name)
        self.generic_visit(node)

    def _is_write_open(self, node: ast.Call) -> bool:
        mode_node = None
        if len(node.args) >= 2:
            mode_node = node.args[1]
        else:
            for kw in node.keywords:
                if kw.arg == "mode":
                    mode_node = kw.value
                    break
        if mode_node is None:
            return False  # Default-Modus "r" -> Lesen
        if isinstance(mode_node, ast.Constant) and isinstance(mode_node.value, str):
            return any(flag in mode_node.value for flag in _OPEN_WRITE_FLAGS)
        return True  # nicht-literaler Modus -> konservativ als Schreiben werten

    def _check_call(self, node: ast.Call, name: str) -> None:
        # EXTENSION: time/random/environment calls are blocked even when their
        # import root is otherwise allowed (datetime, os) -- check before the
        # SAFE_CALL_NAMES short-circuit so os.getenv is never accidentally safe.
        nd_reason = NONDETERMINISTIC_CALL_NAMES.get(name)
        if nd_reason:
            self._add(
                node,
                category="nondeterministic",
                symbol=name,
                message=f"Call is blocked because it introduces {nd_reason}.",
            )
            return
        # EXTENSION: a final-attribute method like `.now()`/`.utcnow()` on an
        # unknown receiver (e.g. `dt.now()` after `from datetime import datetime
        # as dt`) -- alias resolution already rewrites the head, but guard the
        # tail too for receivers we cannot statically resolve.
        attr_tail = name.rsplit(".", 1)[-1]
        if attr_tail in NONDETERMINISTIC_METHODS and (
            name.startswith("datetime") or "datetime" in self.aliases.get(name.split(".", 1)[0], "")
        ):
            self._add(
                node,
                category="nondeterministic",
                symbol=name,
                message=(
                    "Call is blocked because it introduces "
                    f"{NONDETERMINISTIC_METHODS[attr_tail]}."
                ),
            )
            return

        if name in SAFE_CALL_NAMES:
            return
        if name == "open":
            if self._is_write_open(node):
                self._add(
                    node,
                    category="dangerous_call",
                    symbol="open",
                    message="Write/append open() is blocked in generated code.",
                )
            # Read-Modus erlaubt; den Pfad begrenzt das Laufzeit-Confinement.
            return
        root = name.split(".", 1)[0]
        builtin_reason = DANGEROUS_BUILTIN_CALLS.get(name)
        if builtin_reason:
            self._add(
                node,
                category="dangerous_call",
                symbol=name,
                message=f"Call is blocked because it enables {builtin_reason}.",
            )
            return

        attr = name.rsplit(".", 1)[-1]
        if attr in FILESYSTEM_METHODS:
            self._add(
                node,
                category="filesystem_access",
                symbol=name,
                message="Filesystem method calls are blocked in generated code.",
            )
            return

        if any(name.startswith(prefix) for prefix in DANGEROUS_CALL_PREFIXES):
            reason = DANGEROUS_IMPORT_ROOTS.get(root, "unsafe side effects")
            self._add(
                node,
                category="dangerous_call",
                symbol=name,
                message=f"Call is blocked because it enables {reason}.",
            )
            return

        # EXTENSION: any call into a nondeterministic root (random.*, secrets.*,
        # uuid.*, time.*) is non-deterministic, not just the named ones above.
        nd_root_reason = NONDETERMINISTIC_IMPORT_ROOTS.get(root)
        if nd_root_reason and "." in name:
            self._add(
                node,
                category="nondeterministic",
                symbol=name,
                message=f"Call is blocked because it introduces {nd_root_reason}.",
            )

    # -- attribute reads (os.environ[...] / os.environ.get(...)) ----------- #

    def visit_Attribute(self, node: ast.Attribute) -> None:
        name = _call_name(node, self.aliases)
        if name:
            for chain, reason in NONDETERMINISTIC_ATTRIBUTES.items():
                # Flag the exact `os.environ` chain (and `os.environ.<x>`), but
                # only report once at the `os.environ` node itself to avoid a
                # duplicate report for `os.environ.get`.
                if name == chain:
                    self._add(
                        node,
                        category="nondeterministic",
                        symbol=name,
                        message=f"Access is blocked because it introduces {reason}.",
                    )
        self.generic_visit(node)

    # -- swallowed exceptions (EXTENSION) ---------------------------------- #

    def visit_ExceptHandler(self, node: ast.ExceptHandler) -> None:
        if self._is_swallowing(node):
            symbol = "except:" if node.type is None else "except Exception"
            self._add(
                node,
                category="swallowed_exception",
                symbol=symbol,
                message=(
                    "Exception handler swallows errors silently; a hidden failure "
                    "could mask a wrong calculation. Let it propagate or re-raise."
                ),
            )
        self.generic_visit(node)

    @staticmethod
    def _is_broad(node: ast.ExceptHandler) -> bool:
        # Bare `except:` is broad.
        if node.type is None:
            return True
        # `except Exception` / `except BaseException` (optionally a tuple
        # containing one of them) is broad.
        broad_names = {"Exception", "BaseException"}
        types = node.type.elts if isinstance(node.type, ast.Tuple) else [node.type]
        for t in types:
            tname = t.id if isinstance(t, ast.Name) else None
            if tname in broad_names:
                return True
        return False

    @classmethod
    def _is_swallowing(cls, node: ast.ExceptHandler) -> bool:
        if not cls._is_broad(node):
            return False
        body = node.body
        # `pass` only, or `...` only -> swallowing.
        if len(body) == 1:
            stmt = body[0]
            if isinstance(stmt, ast.Pass):
                return True
            if isinstance(stmt, ast.Expr) and isinstance(stmt.value, ast.Constant) and (
                stmt.value.value is Ellipsis
            ):
                return True
        # A handler that neither re-raises nor logs anywhere in its body, and
        # whose statements are all trivial (pass / constant expr / bare continue
        # / bare break), is treated as swallowing. A handler that raises, returns
        # a value, or does real work is allowed.
        has_raise = any(isinstance(n, ast.Raise) for n in ast.walk(node))
        if has_raise:
            return False
        only_trivial = all(
            isinstance(stmt, ast.Pass)
            or isinstance(stmt, (ast.Continue, ast.Break))
            or (
                isinstance(stmt, ast.Expr)
                and isinstance(stmt.value, ast.Constant)
            )
            for stmt in body
        )
        return only_trivial

    # -- generated-test self-approval (EXTENSION) -------------------------- #

    def visit_FunctionDef(self, node: ast.FunctionDef) -> None:
        if self._is_self_approving_test(node):
            self._add(
                node,
                category="self_approval",
                symbol=node.name,
                message=(
                    "Generated test self-approves (no real value comparison / "
                    "asserts a constant truth) instead of checking computed output."
                ),
            )
        self.generic_visit(node)

    @staticmethod
    def _is_self_approving_test(node: ast.FunctionDef) -> bool:
        if not node.name.startswith("test"):
            return False
        statements = [s for s in node.body if not _is_docstring(s)]
        if not statements:
            # `def test_x(): ...`  (only a docstring or empty body) -> vacuous.
            return True
        # Any `assert True` / `assert <truthy-constant>` is a self-approval.
        for stmt in statements:
            if isinstance(stmt, ast.Assert):
                test = stmt.test
                if isinstance(test, ast.Constant) and bool(test.value):
                    return True
        # A test whose body is only pass / constant expressions (no assert, no
        # call, no comparison) approves nothing.
        only_inert = all(
            isinstance(stmt, ast.Pass)
            or (isinstance(stmt, ast.Expr) and isinstance(stmt.value, ast.Constant))
            for stmt in statements
        )
        return only_inert


def _is_docstring(stmt: ast.stmt) -> bool:
    return (
        isinstance(stmt, ast.Expr)
        and isinstance(stmt.value, ast.Constant)
        and isinstance(stmt.value.value, str)
    )


# --------------------------------------------------------------------------- #
# Public scan API
# --------------------------------------------------------------------------- #


def scan_python_source(source: str, path: Path) -> list[SecurityViolation]:
    try:
        tree = ast.parse(source, filename=str(path))
    except SyntaxError as exc:
        return [
            SecurityViolation(
                path=str(path),
                line=exc.lineno or 0,
                column=exc.offset or 0,
                category="syntax_error",
                symbol="ast.parse",
                message=exc.msg or "syntax error",
                snippet=(exc.text or "").strip(),
            )
        ]

    visitor = _SecurityVisitor(path, source.splitlines())
    visitor.visit(tree)
    # Stable order: by (line, column, category, symbol).
    visitor.violations.sort(key=lambda v: (v.line, v.column, v.category, v.symbol))
    return visitor.violations


def scan_python_items(items: Iterable[tuple[str, str]]) -> list[SecurityViolation]:
    violations: list[SecurityViolation] = []
    for filename, source in items:
        if filename.endswith(".py"):
            violations.extend(scan_python_source(source, Path(filename)))
    return violations


def scan_python_paths(paths: Iterable[Path]) -> list[SecurityViolation]:
    violations: list[SecurityViolation] = []
    for path in paths:
        if path.suffix != ".py" or not path.exists():
            continue
        violations.extend(scan_python_source(path.read_text(encoding="utf-8"), path))
    return violations


def security_report(
    *,
    checked_files: Iterable[Path | str],
    violations: Iterable[SecurityViolation],
) -> dict[str, object]:
    violation_list = list(violations)
    return {
        "status": "failed" if violation_list else "passed",
        "checked_files": [str(path) for path in checked_files],
        "violations": [item.to_dict() for item in violation_list],
    }


def write_security_report(
    path: Path,
    *,
    checked_files: Iterable[Path | str],
    violations: Iterable[SecurityViolation],
) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(
            security_report(checked_files=checked_files, violations=violations),
            ensure_ascii=False,
            indent=2,
        ),
        encoding="utf-8",
        newline="\n",
    )


def raise_for_violations(violations: Iterable[SecurityViolation]) -> None:
    violation_list = list(violations)
    if violation_list:
        raise StaticSecurityError(violation_list)
