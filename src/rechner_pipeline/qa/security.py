from __future__ import annotations

import ast
import json
from dataclasses import dataclass
from pathlib import Path
from typing import Iterable


DANGEROUS_IMPORT_ROOTS = {
    "ftplib": "network access",
    "glob": "filesystem access",
    "http": "network access",
    "httpx": "network access",
    "importlib": "dynamic import",
    "os": "filesystem/process access",
    "pathlib": "filesystem access",
    "requests": "network access",
    "runpy": "dynamic execution",
    "shutil": "filesystem access",
    "socket": "network access",
    "subprocess": "subprocess execution",
    "tempfile": "filesystem access",
    "urllib": "network access",
}

DANGEROUS_BUILTIN_CALLS = {
    "__import__": "dynamic import",
    "eval": "dynamic execution",
    "exec": "dynamic execution",
    "open": "filesystem access",
}

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


@dataclass(frozen=True)
class SecurityViolation:
    path: str
    line: int
    column: int
    category: str
    symbol: str
    message: str

    def to_dict(self) -> dict[str, object]:
        return {
            "path": self.path,
            "line": self.line,
            "column": self.column,
            "category": self.category,
            "symbol": self.symbol,
            "message": self.message,
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


def _violation(
    path: Path,
    node: ast.AST,
    *,
    category: str,
    symbol: str,
    message: str,
) -> SecurityViolation:
    path_str, line, column = _location(path, node)
    return SecurityViolation(
        path=path_str,
        line=line,
        column=column,
        category=category,
        symbol=symbol,
        message=message,
    )


class _SecurityVisitor(ast.NodeVisitor):
    def __init__(self, path: Path) -> None:
        self.path = path
        self.aliases: dict[str, str] = {}
        self.violations: list[SecurityViolation] = []

    def visit_Import(self, node: ast.Import) -> None:
        for alias in node.names:
            root = _root(alias.name)
            local_name = alias.asname or root
            self.aliases[local_name] = alias.name
            reason = DANGEROUS_IMPORT_ROOTS.get(root)
            if reason:
                self.violations.append(
                    _violation(
                        self.path,
                        node,
                        category="dangerous_import",
                        symbol=alias.name,
                        message=f"Import is blocked because it enables {reason}.",
                    )
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
            self.violations.append(
                _violation(
                    self.path,
                    node,
                    category="dangerous_import",
                    symbol=module,
                    message=f"Import is blocked because it enables {reason}.",
                )
            )
        self.generic_visit(node)

    def visit_Call(self, node: ast.Call) -> None:
        name = _call_name(node.func, self.aliases)
        if name:
            self._check_call(node, name)
        self.generic_visit(node)

    def _check_call(self, node: ast.Call, name: str) -> None:
        root = name.split(".", 1)[0]
        builtin_reason = DANGEROUS_BUILTIN_CALLS.get(name)
        if builtin_reason:
            self.violations.append(
                _violation(
                    self.path,
                    node,
                    category="dangerous_call",
                    symbol=name,
                    message=f"Call is blocked because it enables {builtin_reason}.",
                )
            )
            return

        attr = name.rsplit(".", 1)[-1]
        if attr in FILESYSTEM_METHODS:
            self.violations.append(
                _violation(
                    self.path,
                    node,
                    category="filesystem_access",
                    symbol=name,
                    message="Filesystem method calls are blocked in generated code.",
                )
            )
            return

        if any(name.startswith(prefix) for prefix in DANGEROUS_CALL_PREFIXES):
            reason = DANGEROUS_IMPORT_ROOTS.get(root, "unsafe side effects")
            self.violations.append(
                _violation(
                    self.path,
                    node,
                    category="dangerous_call",
                    symbol=name,
                    message=f"Call is blocked because it enables {reason}.",
                )
            )


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
                message=exc.msg,
            )
        ]

    visitor = _SecurityVisitor(path)
    visitor.visit(tree)
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
