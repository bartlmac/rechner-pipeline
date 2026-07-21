"""Static AST architecture / import-convention gate (gate **G3**).

This module is the pure-AST engine behind the ``conventions`` toolbox command
(MIGRATION.md §3.3 ``conventions`` row, §3.5 G3, §6.7 "complete allowed import
graph (MANDATORY)" lines 2568-2587). It scans the generated calculation code
*statically* (AST only -- it never imports or executes the target code) and
BLOCKS (exit ``22``) on any architecture / convention violation.

Enforced rules (all blocking, category ids in :data:`RULES`):

* ``disallowed_edge`` -- an inter-module import edge that is not in the allowed
  production import graph (§6.7). The only permitted inter-layer edge involving
  the actuarial layers is ``actuarial.py -> commutation.py``;
  ``commutation.py -> actuarial.py`` (the back-edge) and every other
  table-forbidden edge fail.
* ``circular_import`` -- a cycle in the module import graph.
* ``function_local_import`` -- an ``import`` / ``from ... import`` statement
  nested inside a function / method / lambda body (deferred imports hide the
  real dependency graph and are forbidden everywhere).
* ``try_except_importerror`` -- a ``try/except ImportError`` (or
  ``ModuleNotFoundError``) construct (optional-dependency tricks are forbidden).
* ``type_checking_trick`` -- a ``if TYPE_CHECKING:`` (or
  ``typing.TYPE_CHECKING``) guarded import block (hides a real edge from the
  runtime graph).
* ``dynamic_import`` -- a dynamic-import construct that hides an edge from the
  static AST scan: ``__import__(...)``, ``importlib.import_module(...)``,
  ``importlib.__import__(...)``, a bare ``import importlib`` / ``import
  importlib.<sub>``, or ``from importlib import import_module`` (and friends).
  Generated kernel code has no legitimate need for dynamic import (the spec
  forbids dynamic import outright), so any such usage FAILS regardless of the
  argument -- a forbidden edge could otherwise be smuggled past the graph scan.
* ``unhashable_lru_cache`` -- an ``@lru_cache`` / ``@functools.cache`` decorated
  function whose arguments are not *provably* hashable. Conservative: unknown
  hashability is a FAIL, not a silent pass.

Public surface used by the toolbox command and tests:

* :func:`build_import_graph`, :func:`scan_conventions`
* :class:`ConventionViolation`, :class:`ConventionsReport`
* :func:`conventions_report`, :func:`write_conventions_report`
* :data:`GATE_VERSION`, :data:`RULES`, :data:`ALLOWED_IMPORTS`,
  :data:`PRODUCTION_MODULES`
"""

from __future__ import annotations

import ast
import json
from dataclasses import dataclass, field
from pathlib import Path
from typing import Dict, Iterable, List, Mapping, Optional, Set, Tuple


GATE_VERSION = "1.0.0"


# --------------------------------------------------------------------------- #
# Allowed production import graph (§6.7 lines 2568-2587) -- authoritative
# --------------------------------------------------------------------------- #
#
# The six generated files are ``inputs.py``, ``params.py``, ``commutation.py``,
# ``actuarial.py``, ``test_run.py`` (Python) plus ``tafeln.xml`` (data, never
# imported). The mapping below is the COMPLETE set of permitted inter-module
# edges between the five Python modules. ``inputs`` has no inbound stdlib-only
# rows; every module may also import stdlib (stdlib edges are never restricted).
#
# Each value is the set of *generated* modules that the key module is allowed to
# import. Any generated-module edge not present here is a ``disallowed_edge``.
ALLOWED_IMPORTS: Dict[str, Set[str]] = {
    "inputs": set(),
    "params": {"inputs"},
    "commutation": {"inputs", "params"},
    "actuarial": {"inputs", "params", "commutation"},
    "test_run": {"inputs", "params", "commutation", "actuarial"},
}

#: The generated production module names (without the ``.py`` suffix). A module
#: discovered under ``--generated-dir`` that is NOT in this set is treated as an
#: unknown module: its import edges are still graphed, but it has no allowed-edge
#: row, so any inbound/outbound generated edge it participates in is reported.
PRODUCTION_MODULES: Tuple[str, ...] = (
    "inputs",
    "params",
    "commutation",
    "actuarial",
    "test_run",
)

#: ``functools`` decorators that memoize on the *call arguments*; flagged when
#: the decorated function's args are not provably hashable.
_LRU_CACHE_NAMES = {"lru_cache", "cache"}

#: ``ImportError`` family caught by a ``try/except`` optional-import trick.
_IMPORT_ERROR_NAMES = {"ImportError", "ModuleNotFoundError"}

#: Dynamic-import callables that resolve a module at runtime from a (possibly
#: computed) name, invisible to the static import-graph scan. The final dotted
#: component is matched so both ``importlib.import_module`` and a re-bound
#: ``import_module`` (``from importlib import import_module``) are caught.
_DYNAMIC_IMPORT_CALLS = {"__import__", "import_module"}

#: The dynamic-import module itself; importing it (in any form) is forbidden in
#: generated kernel code because its only purpose is runtime/dynamic import.
_DYNAMIC_IMPORT_MODULE = "importlib"

#: Type names whose parameter annotation is NOT provably hashable. Mutable
#: builtins + the typing aliases for them. Anything we cannot positively prove
#: hashable is treated as unhashable (conservative).
_UNHASHABLE_ANNOTATIONS = {
    "list",
    "dict",
    "set",
    "List",
    "Dict",
    "Set",
    "MutableMapping",
    "MutableSequence",
    "MutableSet",
    "bytearray",
    "DefaultDict",
    "defaultdict",
    "OrderedDict",
    "Counter",
}

#: Annotations that ARE provably hashable (immutable builtins / common
#: hashable typing constructs). ``Optional``/``Union`` are unwrapped to their
#: members before this check. NOTE: ``tuple``/``Tuple`` are deliberately NOT
#: here -- a tuple is hashable ONLY if every element type is provably hashable,
#: so it is handled structurally in :func:`_is_provably_hashable_annotation`. A
#: *bare* ``tuple``/``Tuple`` (no element types) has unknown element
#: hashability and therefore FAILS (conservative, per spec §6.7 "unknown
#: lru_cache hashability fails").
_HASHABLE_ANNOTATIONS = {
    "int",
    "float",
    "str",
    "bool",
    "bytes",
    "complex",
    "frozenset",
    "Hashable",
    "None",
    "NoneType",
}

#: ``tuple`` container annotation names. A tuple is hashable iff every declared
#: element type is hashable; a bare (un-parameterized) tuple is unknown -> FAIL.
_TUPLE_ANNOTATIONS = {"tuple", "Tuple"}

#: Canonical rule registry: id -> human description.
RULES: Dict[str, str] = {
    "disallowed_edge": "Import edge not in the allowed production import graph (§6.7).",
    "circular_import": "Modules form an import cycle.",
    "function_local_import": "Import statement nested inside a function/method body.",
    "try_except_importerror": "try/except ImportError optional-import trick.",
    "type_checking_trick": "if TYPE_CHECKING: guarded import hides a real edge.",
    "dynamic_import": "Dynamic import (__import__ / importlib.import_module / import importlib) hides an edge from the static scan.",
    "unhashable_lru_cache": "@lru_cache on a function with non-provably-hashable args.",
    "syntax_error": "Source could not be parsed.",
}


@dataclass(frozen=True)
class ConventionViolation:
    path: str
    line: int
    column: int
    category: str
    symbol: str
    message: str
    snippet: str = ""

    def to_dict(self) -> Dict[str, object]:
        return {
            "path": self.path,
            "line": self.line,
            "column": self.column,
            "category": self.category,
            "symbol": self.symbol,
            "message": self.message,
            "snippet": self.snippet,
        }


# --------------------------------------------------------------------------- #
# Import-graph data classes
# --------------------------------------------------------------------------- #


@dataclass
class _ModuleImports:
    """All import facts extracted from a single generated module."""

    module: str
    path: Path
    #: Top-level edges to OTHER generated modules: {target_module: first lineno}.
    edges: Dict[str, int] = field(default_factory=dict)
    #: All generated-module references regardless of where they appear (used for
    #: the graph; function-local ones are also reported separately).
    violations: List[ConventionViolation] = field(default_factory=list)


@dataclass
class ConventionsReport:
    """Aggregate result of a conventions scan (serialized into the JSON summary)."""

    checked_files: List[str]
    import_graph: Dict[str, List[str]]
    layer_edges: List[Dict[str, object]]
    cache_audit: List[Dict[str, object]]
    cycles: List[List[str]]
    violations: List[ConventionViolation]

    def to_dict(self) -> Dict[str, object]:
        return {
            "status": "failed" if self.violations else "passed",
            "checked_files": list(self.checked_files),
            "import_graph": {k: list(v) for k, v in self.import_graph.items()},
            "layer_edges": list(self.layer_edges),
            "cache_audit": list(self.cache_audit),
            "circular_imports": [list(c) for c in self.cycles],
            "violations": [v.to_dict() for v in self.violations],
        }


# --------------------------------------------------------------------------- #
# AST helpers
# --------------------------------------------------------------------------- #


def _module_name(path: Path) -> str:
    """Generated module name = file stem (the six files are flat, no packages)."""
    return path.stem


def _root(module: str) -> str:
    return module.split(".", 1)[0]


def _resolved_target(name: str, known_modules: Set[str]) -> Optional[str]:
    """Return the generated module a (possibly dotted/relative) import refers to.

    The six files are a flat module set, so an import resolves to a generated
    module iff its first dotted component is a known generated module name (e.g.
    ``import commutation``, ``from commutation import D_x``, ``import
    rechner.commutation`` -> ``commutation`` only when ``commutation`` is the
    leading or trailing known component). We match the leading component first
    (flat layout), then any component, to be robust to a package-qualified emit.
    """
    parts = name.split(".")
    if parts and parts[0] in known_modules:
        return parts[0]
    for part in parts:
        if part in known_modules:
            return part
    return None


def _attr_chain(node: ast.AST) -> Optional[str]:
    if isinstance(node, ast.Name):
        return node.id
    if isinstance(node, ast.Attribute):
        parent = _attr_chain(node.value)
        if parent:
            return f"{parent}.{node.attr}"
    return None


def _annotation_names(node: Optional[ast.AST]) -> List[str]:
    """Flatten an annotation AST into the set of bare type names it references.

    ``Optional[int]`` / ``Union[int, str]`` -> their members; subscripts unwrap
    to base + element names; a string (forward-ref) annotation yields its parsed
    names; an unannotated parameter yields ``[]`` (caller treats that as
    unknown).
    """
    if node is None:
        return []
    if isinstance(node, ast.Name):
        return [node.id]
    if isinstance(node, ast.Attribute):
        return [node.attr]
    if isinstance(node, ast.Constant) and isinstance(node.value, str):
        # Forward reference: parse the string as an expression.
        try:
            parsed = ast.parse(node.value, mode="eval").body
        except SyntaxError:
            return [node.value]
        return _annotation_names(parsed)
    if isinstance(node, ast.Subscript):
        base = _annotation_names(node.value)
        # Optional / Union: only the element types matter for hashability.
        base_name = base[0] if base else ""
        elt = node.slice
        members: List[str] = []
        if isinstance(elt, ast.Tuple):
            for e in elt.elts:
                members.extend(_annotation_names(e))
        else:
            members.extend(_annotation_names(elt))
        if base_name in {"Optional", "Union"}:
            return members
        # e.g. List[int] -> ["List", "int"]; the container name decides.
        return base + members
    if isinstance(node, ast.BinOp) and isinstance(node.op, ast.BitOr):
        # PEP 604 union: int | None
        return _annotation_names(node.left) + _annotation_names(node.right)
    return []


def _is_provably_hashable_annotation(node: Optional[ast.AST]) -> Tuple[bool, str]:
    """Return ``(provably_hashable, reason)`` for one parameter annotation.

    Conservative: an unannotated parameter, an unknown type name, or any name in
    :data:`_UNHASHABLE_ANNOTATIONS` is NOT provably hashable.

    Tuples are handled *structurally* because a tuple is hashable iff every
    element type is hashable: ``Tuple[int, ...]`` / ``tuple[str, int]`` PASS,
    but a *bare* ``tuple`` / ``Tuple`` (no element types) is UNKNOWN and FAILS,
    as does ``Tuple[list, ...]`` (unhashable element type).
    """
    if node is None:
        return False, "unannotated parameter (hashability unknown)"

    # Forward reference: parse the string and re-check structurally.
    if isinstance(node, ast.Constant) and isinstance(node.value, str):
        try:
            parsed = ast.parse(node.value, mode="eval").body
        except SyntaxError:
            return False, f"forward-ref annotation {node.value!r} could not be parsed"
        return _is_provably_hashable_annotation(parsed)

    # PEP 604 / typing union: every member must be hashable.
    if isinstance(node, ast.BinOp) and isinstance(node.op, ast.BitOr):
        for member in (node.left, node.right):
            ok, reason = _is_provably_hashable_annotation(member)
            if not ok:
                return False, reason
        return True, ""

    base = _attr_chain(node) if not isinstance(node, ast.Subscript) else None

    # A bare (un-subscripted) tuple has unknown element hashability -> FAIL.
    if base is not None and base.split(".")[-1] in _TUPLE_ANNOTATIONS:
        return False, (
            f"bare '{base}' has unknown element hashability; annotate the element "
            "types (e.g. Tuple[int, ...]) or use a different hashable key"
        )

    if isinstance(node, ast.Subscript):
        container = _attr_chain(node.value)
        container_name = container.split(".")[-1] if container else ""
        elts = node.slice.elts if isinstance(node.slice, ast.Tuple) else [node.slice]
        # Optional / Union: only the member types matter.
        if container_name in {"Optional", "Union"}:
            for elt in elts:
                ok, reason = _is_provably_hashable_annotation(elt)
                if not ok:
                    return False, reason
            return True, ""
        # Parameterized tuple: hashable iff every (non-Ellipsis) element is.
        if container_name in _TUPLE_ANNOTATIONS:
            checked = False
            for elt in elts:
                if isinstance(elt, ast.Constant) and elt.value is Ellipsis:
                    continue  # the `...` in Tuple[int, ...] is variadic marker
                checked = True
                ok, reason = _is_provably_hashable_annotation(elt)
                if not ok:
                    return False, f"tuple element {reason}"
            if not checked:
                return False, (
                    "tuple has no declared element types; element hashability is "
                    "unknown"
                )
            return True, ""
        # Any other container (List[int], Dict[...], ...): the container name
        # decides; an unhashable container fails outright.
        if container_name in _UNHASHABLE_ANNOTATIONS:
            return False, f"{container_name} is not hashable"
        if container_name not in _HASHABLE_ANNOTATIONS:
            return False, f"{container_name} is not provably hashable"
        return True, ""

    names = _annotation_names(node)
    if not names:
        return False, "annotation hashability could not be determined"
    for n in names:
        if n in _UNHASHABLE_ANNOTATIONS:
            return False, f"{n} is not hashable"
    for n in names:
        if n not in _HASHABLE_ANNOTATIONS:
            return False, f"{n} is not provably hashable"
    return True, ""


# --------------------------------------------------------------------------- #
# Per-module AST visitor
# --------------------------------------------------------------------------- #


class _ConventionVisitor(ast.NodeVisitor):
    def __init__(self, module: str, path: Path, source_lines: List[str], known_modules: Set[str]) -> None:
        self.module = module
        self.path = path
        self.source_lines = source_lines
        self.known_modules = known_modules
        self.edges: Dict[str, int] = {}
        self.violations: List[ConventionViolation] = []
        self._func_depth = 0

    def _snippet(self, node: ast.AST) -> str:
        line = int(getattr(node, "lineno", 0))
        if 1 <= line <= len(self.source_lines):
            return self.source_lines[line - 1].strip()
        return ""

    def _add(self, node: ast.AST, *, category: str, symbol: str, message: str) -> None:
        self.violations.append(
            ConventionViolation(
                path=str(self.path),
                line=int(getattr(node, "lineno", 0)),
                column=int(getattr(node, "col_offset", 0)),
                category=category,
                symbol=symbol,
                message=message,
                snippet=self._snippet(node),
            )
        )

    # -- function bodies (track depth for function-local imports) ----------- #

    def _enter_function(self, node: ast.AST) -> None:
        self._func_depth += 1
        self.generic_visit(node)
        self._func_depth -= 1

    def visit_FunctionDef(self, node: ast.FunctionDef) -> None:
        self._check_lru_cache(node)
        self._enter_function(node)

    def visit_AsyncFunctionDef(self, node: ast.AsyncFunctionDef) -> None:
        self._check_lru_cache(node)
        self._enter_function(node)

    def visit_Lambda(self, node: ast.Lambda) -> None:
        self._enter_function(node)

    # -- imports ------------------------------------------------------------ #

    def _record_edge(self, target: str, node: ast.AST) -> None:
        if target == self.module:
            return  # self-import noise; not an inter-module edge
        if target not in self.edges:
            self.edges[target] = int(getattr(node, "lineno", 0))

    def visit_Import(self, node: ast.Import) -> None:
        if self._func_depth > 0:
            self._add(
                node,
                category="function_local_import",
                symbol=", ".join(a.name for a in node.names),
                message="Import statement nested inside a function body; "
                "imports must be at module top level.",
            )
        for alias in node.names:
            # `import importlib` / `import importlib.util` -> dynamic-import module.
            if _root(alias.name) == _DYNAMIC_IMPORT_MODULE:
                self._add(
                    node,
                    category="dynamic_import",
                    symbol=alias.name,
                    message="'import importlib' is a dynamic-import construct; "
                    "dynamic import is forbidden and hides edges from the static "
                    "import-graph scan. Import the target module directly.",
                )
            target = _resolved_target(alias.name, self.known_modules)
            if target and self._func_depth == 0:
                self._record_edge(target, node)
        self.generic_visit(node)

    def visit_ImportFrom(self, node: ast.ImportFrom) -> None:
        if self._func_depth > 0:
            self._add(
                node,
                category="function_local_import",
                symbol=node.module or "(relative import)",
                message="Import statement nested inside a function body; "
                "imports must be at module top level.",
            )
        module = node.module or ""
        # `from importlib import import_module` / `from importlib.x import ...`.
        if module and _root(module) == _DYNAMIC_IMPORT_MODULE:
            self._add(
                node,
                category="dynamic_import",
                symbol=f"from {module} import "
                + ", ".join(a.name for a in node.names),
                message="'from importlib import ...' is a dynamic-import "
                "construct; dynamic import is forbidden and hides edges from the "
                "static import-graph scan. Import the target module directly.",
            )
        target = _resolved_target(module, self.known_modules) if module else None
        # `from <pkg> import commutation` -> the imported name may BE a module.
        if target is None:
            for alias in node.names:
                t = _resolved_target(alias.name, self.known_modules)
                if t:
                    target = t
                    break
        if target and self._func_depth == 0:
            self._record_edge(target, node)
        self.generic_visit(node)

    # -- try/except ImportError + TYPE_CHECKING ----------------------------- #

    def visit_Try(self, node: ast.Try) -> None:
        for handler in node.handlers:
            if self._handler_catches_importerror(handler):
                self._add(
                    handler if handler.lineno else node,
                    category="try_except_importerror",
                    symbol="except ImportError",
                    message="try/except ImportError optional-import trick is "
                    "forbidden; declare the dependency directly.",
                )
        self.generic_visit(node)

    @staticmethod
    def _handler_catches_importerror(handler: ast.ExceptHandler) -> bool:
        if handler.type is None:
            return False
        types = handler.type.elts if isinstance(handler.type, ast.Tuple) else [handler.type]
        for t in types:
            name = _attr_chain(t)
            if name and name.split(".")[-1] in _IMPORT_ERROR_NAMES:
                return True
        return False

    def visit_If(self, node: ast.If) -> None:
        if self._is_type_checking_test(node.test):
            self._add(
                node,
                category="type_checking_trick",
                symbol="TYPE_CHECKING",
                message="if TYPE_CHECKING: guarded imports hide a real edge from "
                "the runtime import graph; import unconditionally.",
            )
        self.generic_visit(node)

    @staticmethod
    def _is_type_checking_test(test: ast.AST) -> bool:
        name = _attr_chain(test)
        if name and name.split(".")[-1] == "TYPE_CHECKING":
            return True
        return False

    # -- dynamic import calls (__import__ / importlib.import_module) --------- #

    def visit_Call(self, node: ast.Call) -> None:
        name = _attr_chain(node.func)
        if name and name.split(".")[-1] in _DYNAMIC_IMPORT_CALLS:
            self._add(
                node,
                category="dynamic_import",
                symbol=f"{name}(...)",
                message=(
                    f"'{name}(...)' is a dynamic-import construct; dynamic import "
                    "is forbidden and hides the resolved edge from the static "
                    "import-graph scan. Import the target module directly at "
                    "module top level."
                ),
            )
        self.generic_visit(node)

    # -- lru_cache hashability ---------------------------------------------- #

    def _check_lru_cache(self, node: ast.AST) -> None:
        decorators = getattr(node, "decorator_list", [])
        if not any(self._is_lru_cache_decorator(d) for d in decorators):
            return
        func_name = getattr(node, "name", "<func>")
        args = node.args  # type: ignore[attr-defined]
        params: List[Tuple[str, Optional[ast.AST]]] = []
        for a in list(args.posonlyargs) + list(args.args) + list(args.kwonlyargs):
            params.append((a.arg, a.annotation))
        # *args / **kwargs accept arbitrary (possibly unhashable) values.
        if args.vararg is not None:
            params.append((f"*{args.vararg.arg}", None))
        if args.kwarg is not None:
            params.append((f"**{args.kwarg.arg}", None))

        # `self`/`cls` on a method: the receiver instance must itself be hashable
        # for an lru_cache key; an unannotated `self` is unknown -> FAIL
        # (conservative). We do not special-case it away.
        unhashable: List[str] = []
        for pname, ann in params:
            ok, reason = _is_provably_hashable_annotation(ann)
            if not ok:
                unhashable.append(f"{pname}: {reason}")

        if unhashable:
            self._add(
                node,
                category="unhashable_lru_cache",
                symbol=func_name,
                message=(
                    f"@lru_cache on '{func_name}' whose arguments are not provably "
                    f"hashable ({'; '.join(unhashable)}); use string IDs or remove "
                    "the cache. Unknown hashability is a failure, not a pass."
                ),
            )

    @staticmethod
    def _is_lru_cache_decorator(dec: ast.AST) -> bool:
        # @lru_cache  /  @functools.lru_cache  /  @lru_cache(maxsize=None)  /  @cache
        target = dec.func if isinstance(dec, ast.Call) else dec
        name = _attr_chain(target)
        if not name:
            return False
        return name.split(".")[-1] in _LRU_CACHE_NAMES


# --------------------------------------------------------------------------- #
# Graph build + cycle detection
# --------------------------------------------------------------------------- #


def _detect_cycles(graph: Mapping[str, Iterable[str]]) -> List[List[str]]:
    """Return all elementary cycles (as node lists) in a directed graph.

    Deterministic DFS; each cycle is normalized to start at its smallest node
    and de-duplicated so a cycle is reported once.
    """
    cycles: Set[Tuple[str, ...]] = set()
    nodes = sorted(graph)

    def _normalize(path: List[str]) -> Tuple[str, ...]:
        # path is the cycle node list (without the repeated closing node).
        i = path.index(min(path))
        rotated = path[i:] + path[:i]
        return tuple(rotated)

    def _dfs(start: str, node: str, stack: List[str], on_stack: Set[str]) -> None:
        for nxt in sorted(graph.get(node, ())):
            if nxt == start and len(stack) >= 1:
                cycles.add(_normalize(list(stack)))
            elif nxt not in on_stack and nxt >= start:
                # only explore nodes >= start to avoid re-finding rotations
                stack.append(nxt)
                on_stack.add(nxt)
                _dfs(start, nxt, stack, on_stack)
                stack.pop()
                on_stack.discard(nxt)

    for start in nodes:
        _dfs(start, start, [start], {start})

    return [list(c) for c in sorted(cycles)]


def build_import_graph(
    modules: Iterable[_ModuleImports],
) -> Dict[str, List[str]]:
    """Return ``{module: sorted[target modules]}`` from extracted import facts."""
    graph: Dict[str, List[str]] = {}
    for m in modules:
        graph[m.module] = sorted(m.edges)
    return graph


# --------------------------------------------------------------------------- #
# Public scan API
# --------------------------------------------------------------------------- #


def _parse_module(source: str, path: Path, known_modules: Set[str]) -> Tuple[_ModuleImports, List[ConventionViolation]]:
    module = _module_name(path)
    try:
        tree = ast.parse(source, filename=str(path))
    except SyntaxError as exc:
        v = ConventionViolation(
            path=str(path),
            line=exc.lineno or 0,
            column=exc.offset or 0,
            category="syntax_error",
            symbol="ast.parse",
            message=exc.msg or "syntax error",
            snippet=(exc.text or "").strip(),
        )
        return _ModuleImports(module=module, path=path), [v]

    visitor = _ConventionVisitor(module, path, source.splitlines(), known_modules)
    visitor.visit(tree)
    mi = _ModuleImports(module=module, path=path, edges=dict(visitor.edges))
    return mi, list(visitor.violations)


def scan_conventions(items: Iterable[Tuple[str, str]]) -> ConventionsReport:
    """Scan ``(filename, source)`` pairs and return a :class:`ConventionsReport`.

    The full G3 rule set is enforced: allowed import graph, circular imports,
    function-local imports, ``try/except ImportError``, ``TYPE_CHECKING`` tricks,
    and conservative ``lru_cache`` hashability.
    """
    pairs = [(fn, src) for fn, src in items if fn.endswith(".py")]
    paths = [Path(fn) for fn, _ in pairs]
    known_modules = {_module_name(p) for p in paths}

    module_imports: List[_ModuleImports] = []
    all_violations: List[ConventionViolation] = []

    for (fn, src), path in zip(pairs, paths):
        mi, viol = _parse_module(src, path, known_modules)
        module_imports.append(mi)
        all_violations.extend(viol)

    graph = build_import_graph(module_imports)

    # -- allowed-edge check (§6.7) ----------------------------------------- #
    layer_edges: List[Dict[str, object]] = []
    for mi in module_imports:
        allowed = ALLOWED_IMPORTS.get(mi.module)
        for target, lineno in sorted(mi.edges.items()):
            is_allowed = allowed is not None and target in allowed
            layer_edges.append(
                {
                    "from": mi.module,
                    "to": target,
                    "line": lineno,
                    "allowed": bool(is_allowed),
                }
            )
            if not is_allowed:
                if allowed is None:
                    reason = (
                        f"module '{mi.module}' is not one of the six recognized "
                        f"production modules {PRODUCTION_MODULES}"
                    )
                else:
                    reason = (
                        f"'{mi.module}' may only import "
                        f"{sorted(allowed) or '(stdlib only)'}"
                    )
                all_violations.append(
                    ConventionViolation(
                        path=str(mi.path),
                        line=lineno,
                        column=0,
                        category="disallowed_edge",
                        symbol=f"{mi.module} -> {target}",
                        message=(
                            f"Import edge '{mi.module}.py -> {target}.py' is not in "
                            f"the allowed production import graph; {reason}."
                        ),
                        snippet="",
                    )
                )

    # -- cycle detection ---------------------------------------------------- #
    cycles = _detect_cycles(graph)
    for cycle in cycles:
        all_violations.append(
            ConventionViolation(
                path=str(module_imports[0].path) if module_imports else "",
                line=0,
                column=0,
                category="circular_import",
                symbol=" -> ".join(cycle + [cycle[0]]),
                message=(
                    "Circular import detected: "
                    f"{' -> '.join(cycle + [cycle[0]])}. Imports must form a DAG."
                ),
                snippet="",
            )
        )

    # -- cache audit (informational mirror of unhashable_lru_cache) -------- #
    cache_audit: List[Dict[str, object]] = [
        {
            "path": v.path,
            "function": v.symbol,
            "line": v.line,
            "verdict": "unhashable",
            "detail": v.message,
        }
        for v in all_violations
        if v.category == "unhashable_lru_cache"
    ]

    all_violations.sort(key=lambda v: (v.path.lower(), v.line, v.column, v.category, v.symbol))

    return ConventionsReport(
        checked_files=[str(p) for p in paths],
        import_graph=graph,
        layer_edges=layer_edges,
        cache_audit=cache_audit,
        cycles=cycles,
        violations=all_violations,
    )


def scan_conventions_paths(paths: Iterable[Path]) -> ConventionsReport:
    """Read and scan ``*.py`` files at the given paths."""
    items: List[Tuple[str, str]] = []
    for path in paths:
        if path.suffix != ".py" or not path.exists():
            continue
        items.append((str(path), path.read_text(encoding="utf-8")))
    return scan_conventions(items)


def conventions_report(report: ConventionsReport) -> Dict[str, object]:
    """Return the JSON-serializable report dict."""
    return report.to_dict()


def write_conventions_report(path: Path, report: ConventionsReport) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(report.to_dict(), ensure_ascii=False, indent=2),
        encoding="utf-8",
        newline="\n",
    )
