"""Der Pin-Schluss der Abhaengigkeiten ist vollstaendig (Review T19-04, T20-08).

Die CI installiert ueber die Pin-Dateien, nicht ueber pyproject; pyproject
pinnt nur die direkten Abhaengigkeiten. Zwei Luecken derselben Klasse
hatten den Schluss offen gelassen: eine direkte Abhaengigkeit fehlte in
der Pin-Datei (pypdf, CI-Rot auf PR #11), und neun transitive Pakete
wurden je Lauf frisch aufgeloest (NumPy 2.5.2 statt 2.4.6 machte die
Suite rot). Beides wird hier gemessen statt behauptet — offline, aus der
installierten Umgebung.

Knoten: system/architektur
"""

from __future__ import annotations

import importlib.metadata as md
import re
import tomllib
from pathlib import Path

from packaging.markers import default_environment
from packaging.requirements import Requirement

REPO = Path(__file__).resolve().parents[1]


def _norm(name: str) -> str:
    return re.sub(r"[-_.]+", "-", name).lower()


def _pins(*dateien: str) -> dict[str, str]:
    pins: dict[str, str] = {}
    for datei in dateien:
        for zeile in (REPO / datei).read_text(encoding="utf-8").splitlines():
            zeile = zeile.split("#", 1)[0].strip()
            if not zeile or zeile.startswith("-r"):
                continue
            name, version = zeile.split("==")
            pins[_norm(name)] = version
    return pins


def _direkte() -> dict[str, str]:
    projekt = tomllib.loads((REPO / "pyproject.toml").read_text(encoding="utf-8"))["project"]
    roh = list(projekt["dependencies"]) + list(projekt["optional-dependencies"]["dev"])
    direkte = {}
    for eintrag in roh:
        req = Requirement(eintrag)
        (spec,) = list(req.specifier)
        assert spec.operator == "==", f"{eintrag}: direkte Abhaengigkeiten sind exakt gepinnt"
        direkte[_norm(req.name)] = spec.version
    return direkte


def test_jede_direkte_abhaengigkeit_steht_mit_ihrer_version_in_den_pins():
    pins = _pins("requirements.txt", "requirements-dev.txt")
    fehlend = {n: v for n, v in _direkte().items() if pins.get(n) != v}
    assert not fehlend, f"pyproject und Pin-Dateien laufen auseinander: {fehlend}"


def test_die_installierte_transitive_huelle_ist_gepinnt():
    """Was pip fuer die direkten Abhaengigkeiten wirklich mitinstalliert
    (Marker der laufenden Umgebung ausgewertet), muss in den Pin-Dateien
    stehen — sonst loest die CI es je Lauf neu auf."""
    pins = _pins("requirements.txt", "requirements-dev.txt")
    umgebung = {**default_environment(), "extra": ""}
    huelle: dict[str, str] = {}
    offen = list(_direkte())
    while offen:
        name = offen.pop()
        if _norm(name) in huelle:
            continue
        dist = md.distribution(name)
        huelle[_norm(name)] = dist.version
        for eintrag in dist.requires or []:
            req = Requirement(eintrag)
            if req.marker and not req.marker.evaluate(umgebung):
                continue
            offen.append(req.name)
    ungepinnt = {n: v for n, v in huelle.items() if n not in pins}
    abweichend = {n: (pins[n], v) for n, v in huelle.items() if n in pins and pins[n] != v}
    assert not ungepinnt, f"transitive Pakete ohne Pin: {ungepinnt}"
    assert not abweichend, f"installiert != gepinnt: {abweichend}"
