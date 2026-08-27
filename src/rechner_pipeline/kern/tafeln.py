"""Sterbetafel-Zugriff: die Rechnungsgrundlagen-Schicht des Kerns.

Laedt ``tafeln.xml`` (Alterstafeln und Select-Tafeln) und stellt den
fail-fast-Zugriff bereit: fehlt eine Tafel oder ein Alter, wird niemals
eine qx-Kurve erfunden. :class:`Tafelbasis` ist die aufgeloeste Basis
(Geschlecht + Tafel) fuer den Thiele-Wertepfad — reine qx, keinerlei
Kommutations-Ableitungen: der Zielkern rechnet vollstaendig in der
Zustandsmodell-Welt. Die Tafel-Erschoepfung (ab dem ersten Alter nach
qx = 1 sind bedingte Barwerte nicht definiert) ist hier als
Domaenenregel festgehalten (:class:`TafelBereichError`).

Namensaufloesung: exakter Tafelname gewinnt (so tragen abgeleitete
Unisex-Mischtafeln wie ``DAV2008_T_NR_U70`` ohne Code-Aenderung);
sonst VBA-treues Geschlechts-Suffix (nicht-"M" -> Frauentafel).

Knoten: klv, bu
"""

from __future__ import annotations

import math
import xml.etree.ElementTree as ET
from dataclasses import dataclass, field
from importlib import resources
from types import MappingProxyType
from typing import Dict, List, Mapping, Optional, Tuple

from rechner_pipeline.kern.konventionen import MAX_ALTER


class MissingMortalityTableError(NotImplementedError):
    """Die angeforderte Sterbetafel fehlt in ``tafeln.xml``."""


class TafelBereichError(ValueError):
    """Eine Rechnung erreicht Alter jenseits der Tafel-Erschoepfung.

    Sprechender Domaenenfehler: ab dem ersten Alter nach qx = 1 gibt es
    keine Lebenden mehr — bedingte Barwerte sind dort nicht definiert
    (z. B. DAV1994_T: qx = 1 ab Alter 100, erschoepft ab 101).
    """


def _qx_wert(roh: object, kontext: str) -> float:
    """qx strikt als endliche Wahrscheinlichkeit lesen.

    Rechnungsgrundlagen sind Vertrauensanker des Kerns. Deshalb werden
    IEEE-Sonderwerte und Werte ausserhalb des Wahrscheinlichkeitsbereichs
    bereits beim Laden verworfen, nicht erst als Folgefehler in einer
    Barwertrechnung.
    """
    try:
        wert = float(roh)
    except (TypeError, ValueError) as exc:
        raise ValueError(f"{kontext}: qx {roh!r} ist keine Zahl") from exc
    if not math.isfinite(wert):
        raise ValueError(f"{kontext}: qx {roh!r} ist nicht endlich")
    if not 0.0 <= wert <= 1.0:
        raise ValueError(
            f"{kontext}: qx {wert!r} liegt ausserhalb des Bereichs [0, 1]"
        )
    return wert


def validiere_alterstafel(name: str, werte: Mapping[int, float]) -> None:
    """Exakten Altersbereich und qx-Domaene einer Alterstafel pruefen."""
    alter_menge = set()
    for alter, qx in werte.items():
        if isinstance(alter, bool) or not isinstance(alter, int):
            raise ValueError(
                f"Tafel {name!r}: Alter {alter!r} ist nicht ganzzahlig"
            )
        if isinstance(qx, bool) or not isinstance(qx, (int, float)):
            raise ValueError(
                f"Tafel {name!r}, Alter {alter}: qx {qx!r} ist keine Zahl"
            )
        alter_menge.add(alter)
        _qx_wert(qx, f"Tafel {name!r}, Alter {alter}")

    erwartet = set(range(0, MAX_ALTER + 1))
    fehlend = sorted(erwartet - alter_menge)
    zusaetzlich = sorted(alter_menge - erwartet)
    if fehlend or zusaetzlich:
        teile = []
        if fehlend:
            teile.append(
                f"Alter {fehlend[:5]}{'…' if len(fehlend) > 5 else ''} fehlen"
            )
        if zusaetzlich:
            teile.append(
                f"zusaetzliche Alter {zusaetzlich[:5]}"
                f"{'…' if len(zusaetzlich) > 5 else ''}; eine "
                "Tafel-Erweiterung ist ein eigener Vorgang"
            )
        raise ValueError(
            f"Tafel {name!r}: {'; '.join(teile)} "
            f"(erwartet exakt 0..{MAX_ALTER})"
        )


def _ganzzahl_attribut(roh: object, kontext: str) -> int:
    try:
        return int(roh)
    except (TypeError, ValueError) as exc:
        raise ValueError(f"{kontext}: {roh!r} ist nicht ganzzahlig") from exc


def _parse_tables(text: str):
    """Kern-XML mit allen Tafel-Invarianten parsen."""
    root = ET.fromstring(text)
    tables: Dict[str, Dict[int, float]] = {}
    select_tables: Dict[str, Dict[Tuple[int, int], float]] = {}
    for table in root.findall("table"):
        name = table.get("name")
        if name in tables or name in select_tables:
            raise ValueError(f"Tafelname {name!r} ist im Kern-XML doppelt")
        if table.get("select_max") is not None:
            select_max = _ganzzahl_attribut(
                table.get("select_max"), f"Select-Tafel {name!r}: select_max"
            )
            if select_max < 0:
                raise ValueError(
                    f"Select-Tafel {name!r}: select_max={select_max} ist negativ"
                )
            by_key: Dict[Tuple[int, int], float] = {}
            for entry in table.findall("entry"):
                if entry.get("dauer") is None:
                    raise ValueError(
                        f"Select-Tafel {name!r}: Eintrag ohne dauer-Attribut"
                    )
                alter = _ganzzahl_attribut(
                    entry.get("age"), f"Select-Tafel {name!r}: Alter"
                )
                dauer = _ganzzahl_attribut(
                    entry.get("dauer"), f"Select-Tafel {name!r}: Dauer"
                )
                key = (alter, dauer)
                if key in by_key:
                    raise ValueError(f"Select-Tafel {name!r}: Duplikat {key}")
                by_key[key] = _qx_wert(
                    entry.get("qx"),
                    f"Select-Tafel {name!r}, Alter {alter}, Dauer {dauer}",
                )
            # Exaktes Gitter fail-fast beim Laden (nicht erst mitten in der
            # Thiele-Rekursion). So bleiben auch negative oder ueberzaehlige
            # Alter/Dauern nicht als unbenutzte Schattenwerte im Kern-XML.
            erwartet = {
                (alter, dauer)
                for alter in range(0, MAX_ALTER + 1)
                for dauer in range(0, select_max + 1)
            }
            fehlend = sorted(erwartet - set(by_key))
            zusaetzlich = sorted(set(by_key) - erwartet)
            if fehlend or zusaetzlich:
                raise ValueError(
                    f"Select-Tafel {name!r}: Gitter nicht exakt; "
                    f"fehlend {fehlend[:3]}, zusaetzlich {zusaetzlich[:3]}"
                )
            select_tables[name] = by_key
        else:
            by_age: Dict[int, float] = {}
            for entry in table.findall("entry"):
                if entry.get("dauer") is not None:
                    raise ValueError(
                        f"Tafel {name!r}: dauer-Eintrag ohne select_max-Attribut "
                        "— Select-Tafeln muessen als solche deklariert sein"
                    )
                age = _ganzzahl_attribut(
                    entry.get("age"), f"Tafel {name!r}: Alter"
                )
                if age in by_age:
                    raise ValueError(f"Tafel {name!r}: Duplikat Alter {age}")
                by_age[age] = _qx_wert(
                    entry.get("qx"), f"Tafel {name!r}, Alter {age}"
                )
            validiere_alterstafel(name, by_age)
            tables[name] = by_age
    return tables, select_tables


def _load_tables():
    """``tafeln.xml`` (Paket-Daten) parsen.

    Rückgabe: (Alterstafeln ``{name: {alter: qx}}``, Select-Tafeln
    ``{name: {(alter, dauer): wert}}``). Select-Tafeln (Einträge mit
    ``dauer``-Attribut, Tabellen-Attribut ``select_max``) tragen
    dauerabhängige Ausscheidewahrscheinlichkeiten — das
    Select-Perioden-Prinzip der DAV-Tafeln (z. B. Reaktivierung/
    Invalidensterblichkeit nach BU-Dauer).
    """
    text = (resources.files("rechner_pipeline.kern") / "tafeln.xml").read_text(
        encoding="utf-8"
    )
    return _parse_tables(text)


_TABLES, _SELECT_TABLES = _load_tables()


def _select_key(name: str, sex: str | None) -> str:
    """Select-Tafel-Id auflösen — wie :func:`_tafel_key` für Sterbetafeln.

    Exakter Name gewinnt (geschlechtsunabhängige Tafeln wie die
    synthetischen Platzhalter); sonst entscheidet das Suffix ``_M``/``_F``
    (geschlechtsabhängige Tafeln wie die DAV-Ausscheideordnungen). Ohne
    ``sex`` bleibt es beim exakten Namen — dann muss die Tafel unisex sein.
    """
    if name in _SELECT_TABLES or sex is None:
        return name
    return name + "_" + ("M" if sex.upper() == "M" else "F")


def select_tafel(
    name: str, sex: str | None = None
) -> Mapping[Tuple[int, int], float]:
    """Select-Tafel ``{(alter, dauer): wert}`` — fail-fast wenn unbekannt.

    Rückgabe ist eine unveränderliche Sicht (MappingProxy) auf die
    Prozess-globalen Tafeldaten — Aufrufer können sie nicht mutieren
    (Bit-Exaktheit der Referenzwerte). ``sex`` löst geschlechtsabhängige Tafeln auf
    (siehe :func:`_select_key`).
    """
    key = _select_key(name, sex)
    tafel = _SELECT_TABLES.get(key)
    if tafel is None:
        raise MissingMortalityTableError(
            f"Select-Tafel {key!r} fehlt in tafeln.xml; es wird keine "
            "Ausscheideordnung erfunden"
        )
    return MappingProxyType(tafel)


def select_max_dauer(name: str, sex: str | None = None) -> int:
    """Höchste tabulierte Dauer einer Select-Tafel (Select-Periode)."""
    return max(dauer for _, dauer in select_tafel(name, sex))


def _tafel_key(sex: str, tafel: str) -> str:
    """Tafel-Id in ``tafeln.xml`` auflösen.

    Exakter Tafelname gewinnt (macht geschlechtsunabhängige Tafeln — Unisex —
    ohne Kern-Änderung möglich, sobald ``tafeln.xml`` eine solche enthält);
    sonst VBA-treues Suffix ``Act_qx``: nicht-"M" -> Frauentafel.
    """
    if tafel in _TABLES:
        return tafel
    return tafel + "_" + ("M" if sex.upper() == "M" else "F")


def qx_vector(sex: str, tafel: str) -> List[float]:
    """qx-Liste für Alter 0..MAX_ALTER (Auflösung siehe :func:`_tafel_key`)."""
    key = _tafel_key(sex, tafel)
    table = _TABLES.get(key)
    if table is None:
        raise MissingMortalityTableError(
            f"Sterbetafel {key!r} fehlt in tafeln.xml; es wird keine qx-Kurve erfunden"
        )
    vector = []
    for age in range(0, MAX_ALTER + 1):
        if age not in table:
            raise MissingMortalityTableError(
                f"Sterbetafel {key!r}: Alter {age} fehlt in tafeln.xml"
            )
        vector.append(table[age])
    return vector




def verfuegbare_tafeln() -> frozenset:
    """Alle Alterstafel-Namen (xml-Ebene) — fuer Spez/Struktur-Urteil."""
    return frozenset(_TABLES)


def erschoepft_ab(qx: Tuple[float, ...]) -> Optional[int]:
    """Erstes Alter OHNE Lebende: eins nach dem ersten qx = 1.

    Aequivalent zur klassischen Dx = 0-Grenze (die l_x-Kette faellt
    genau dann auf 0, wenn ein qx = 1 durchlaufen wurde), aber rein aus
    den Tafelwerten abgeleitet — ohne Kommutationsspalten.
    """
    for alter, wert in enumerate(qx):
        if wert >= 1.0:
            return alter + 1
    return None


@dataclass(frozen=True)
class Tafelbasis:
    """Aufgeloeste Sterbetafel-Basis (Geschlecht + Tafel) des Wertepfads."""

    sex: str
    tafel: str
    qx: Tuple[float, ...] = field(repr=False)
    #: Erstes Alter jenseits der Erschoepfung (None = Tafel traegt bis
    #: MAX_ALTER Lebende).
    erschoepft: Optional[int] = None

    @property
    def key(self) -> Tuple[str, str]:
        """Cache-Schluessel: die AUFGELOESTE Tafel-Id plus Normgeschlecht."""
        return (_tafel_key(self.sex, self.tafel), self.tafel)

    def qx_at(self, age: int) -> float:
        if age < 0 or age > MAX_ALTER:
            raise IndexError(
                f"Alter {age} ausserhalb des Tafelbereichs [0, {MAX_ALTER}]"
            )
        return self.qx[age]

    def pruefe_alter(self, age: int, hoechstes_alter: Optional[int] = None) -> None:
        """Domaenen-Check des Wertepfads (fail-fast).

        ``age`` muss vor der Erschoepfung liegen (bedingte Barwerte);
        ``hoechstes_alter`` (z. B. Endalter eines Barwerts) muss im
        Tafelbereich liegen.
        """
        if self.erschoepft is not None and age >= self.erschoepft:
            raise TafelBereichError(
                f"Alter {age}: Tafel {self.tafel} erschoepft ab "
                f"{self.erschoepft} — bedingte Barwerte sind dort nicht "
                "definiert"
            )
        grenze = hoechstes_alter if hoechstes_alter is not None else age
        if grenze < 0 or grenze > MAX_ALTER:
            raise IndexError(
                f"Alter {grenze} ausserhalb des Tafelbereichs [0, {MAX_ALTER}]"
            )


_BASIS_CACHE: Dict[Tuple[str, str], Tafelbasis] = {}


def basis(sex: str, tafel: str) -> Tafelbasis:
    """Tafelbasis einer Rechnungsgrundlage — deterministisch gecacht.

    Cache-Schluessel ist die AUFGELOESTE Tafel: zwei Geschlechter auf
    einer Unisex-Tafel teilen sich dieselbe Basis.
    """
    sex_norm = "M" if sex.upper() == "M" else "F"
    key = (_tafel_key(sex_norm, tafel), tafel)
    vorhanden = _BASIS_CACHE.get(key)
    if vorhanden is not None:
        return vorhanden
    qx = tuple(qx_vector(sex_norm, tafel))
    neu = Tafelbasis(
        sex=sex_norm, tafel=tafel, qx=qx, erschoepft=erschoepft_ab(qx)
    )
    _BASIS_CACHE[key] = neu
    return neu
