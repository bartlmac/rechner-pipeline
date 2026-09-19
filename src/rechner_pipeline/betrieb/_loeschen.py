"""Die eine VERZEICHNIS-Loeschfunktion des Betriebs (Klassenbeobachtung der
merge-session zur Nachmessung T24-07).

Reichweite, ehrlich: Verzeichnisse. Dateiloeschungen (``unlink``,
``os.remove``) betreffen im Betrieb nur eigene Temp- und Symlink-Dateien
(Symlink-Tausch, Sperrdatei) und liegen ausserhalb dieser Ratsche —
bewusst, nicht vergessen.

Und ehrlich auch im Umfang: Die Ratsche liest ``betrieb/*.py``. Wuerde
der Betrieb eine Loeschung ueber einen Helfer AUSSERHALB dieses Pakets
fuehren, saehe sie ihn nicht — dieselbe Grenze wie bei der Import-Ratsche
(T23 Block 5). Sie sichert also die Klasse innerhalb des Betriebs, nicht
die Abwesenheit jeder Loeschung ueberhaupt. Wer den Betrieb um ein
Hilfsmodul erweitert, das loescht, erweitert auch den Umfang hier.

Nach T24-07 gab es in ``betrieb/`` drei ``rmtree`` mit drei verschiedenen
Wachen — und eine Ratsche, die sie ZAEHLTE statt zu pruefen, was sie zu
pruefen vorgab: eine vierte Fundstelle fiel auf, eine ungewachte an einer
der drei erlaubten nicht. Jetzt geht jede Loeschung eines Verzeichnisses
im Betrieb durch :func:`entferne_verzeichnis`, und die Ratsche prueft per
AST, dass ``shutil.rmtree`` ausserhalb dieses Moduls nicht vorkommt.

Die Regel der Funktion ist die von T24-07: Ein Produzent loescht nur, was
er selbst erzeugt hat — ein echtes Verzeichnis (kein Symlink), unmittelbar
oder tiefer INNERHALB einer benannten Wurzel, mit dem Namen, den der
Produzent vergibt, und wo es einen Marker gibt, mit diesem Marker. Alles
andere bleibt stehen und ist ein benannter Fehler.

Knoten: klv, bu
"""

from __future__ import annotations

import shutil
from pathlib import Path
from typing import Callable, Optional


class LoeschFehler(ValueError):
    """Ein Verzeichnis, das der Betrieb NICHT loescht — mit Grund."""


def _unter(pfad: Path, wurzel: Path) -> bool:
    return pfad != wurzel and wurzel in pfad.parents


def entferne_verzeichnis(
    pfad: Path,
    *,
    innerhalb: Path,
    name_ok: Optional[Callable[[str], bool]] = None,
    marker: Optional[str] = None,
    ohne_marker: Optional[str] = None,
    grund: str = "",
) -> None:
    """``pfad`` entfernen — wenn es ein eigenes Verzeichnis des Produzenten ist.

    ``innerhalb``: die Wurzel, unter der das Verzeichnis liegen muss
    (aufgeloest, strikt darunter — die Wurzel selbst wird nie geloescht).
    ``name_ok``: Namensregel des Produzenten (z. B. ``stand-<kennung>``).
    ``marker``: Datei, die das Verzeichnis als Erzeugnis ausweist (z. B.
    ``stand.json`` des Stands-Pakets). ``grund``: fuer die Meldung.

    ``ohne_marker``: Datei, die das Verzeichnis als VEROEFFENTLICHT
    ausweist und deren Anwesenheit die Loeschung verbietet (z. B.
    ``eingang.json`` eines registrierten Eingangs). Die beiden Marker
    sind die zwei Richtungen derselben Frage, und beide braucht es:
    ``marker`` sagt "das hier ist meins", ``ohne_marker`` sagt "das hier
    ist noch nicht veroeffentlicht".

    Der Anlass ist Befund T26-01. Ein Arbeitsverzeichnis wurde am
    NAMENSSUFFIX erkannt — und ein regulaer registrierter Eingang, der
    zufaellig so hiess, wurde geloescht, schreibgeschuetzte Dateien
    eingeschlossen. Ein Name ist keine Aussage ueber den Lebenszyklus.
    Vor jeder Bereinigung muss die Lebenszyklus-Identitaet FESTSTEHEN,
    nicht plausibel sein.
    """
    ziel = Path(pfad)
    wurzel = Path(innerhalb).resolve()
    if ziel.is_symlink():
        raise LoeschFehler(f"verweigert: {ziel} ist ein Symlink — nur ein echtes Verzeichnis wird entfernt ({grund})")
    if not ziel.is_dir():
        raise LoeschFehler(f"verweigert: {ziel} ist kein Verzeichnis ({grund})")
    aufgeloest = ziel.resolve()
    if not _unter(aufgeloest, wurzel):
        raise LoeschFehler(
            f"verweigert: {ziel} liegt nicht innerhalb von {innerhalb} — nicht geloescht ({grund})"
        )
    if name_ok is not None and not name_ok(aufgeloest.name):
        raise LoeschFehler(
            f"verweigert: {ziel} traegt keinen Namen, den dieser Produzent vergibt — nicht geloescht ({grund})"
        )
    verboten = aufgeloest / ohne_marker if ohne_marker is not None else None
    # ``is_symlink`` mitgefragt: Ein HAENGENDER Symlink dieses Namens ist
    # ``exists() == False``. Er saehe aus wie ein Verzeichnis ohne Marker,
    # und genau in die Richtung darf der Zweifel nicht ausschlagen.
    if verboten is not None and (verboten.exists() or verboten.is_symlink()):
        raise LoeschFehler(
            f"verweigert: {ziel} traegt {ohne_marker} und ist damit ein "
            f"veroeffentlichtes Erzeugnis, kein Arbeitsrest — nicht geloescht ({grund})"
        )
    if marker is not None and (
        (aufgeloest / marker).is_symlink() or not (aufgeloest / marker).is_file()
    ):
        raise LoeschFehler(
            f"verweigert: {ziel} traegt keine {marker} und ist damit kein Erzeugnis dieses Produzenten — nicht geloescht ({grund})"
        )
    shutil.rmtree(aufgeloest)
