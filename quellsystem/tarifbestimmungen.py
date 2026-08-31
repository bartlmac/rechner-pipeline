"""Die Tarifbestimmungen der Quelle — Markdown-Quelle, PDF-Artefakt.

Was der Vertrag GARANTIERT, steht nicht im Rechenkern, sondern in den
Tarifbestimmungen — und bei einer Bestandsuebertragung gehen die
Vertraege MIT ihren Bedingungen ueber: Das aufnehmende Unternehmen muss
abbilden, was hier zugesagt ist. Die beiden Konventionen, die die Quelle
vom Zielsystem unterscheiden, stehen deshalb als ZUSAGEN im Dokument
(Ziffer 4: Stornoabzug je Versicherungsbaustein gesondert; Ziffer 6:
Herabsetzung als Teilkuendigung der Grundversicherung mit Auszahlung).

**Quelle ist Markdown** (``tarifbestimmungen.md``), gerendert ueber die
gepinnte Doku-Engine des Repos (``docs/engine/render.sh``, Quarto/Typst)
— derselbe Weg wie die Zieltarifplaene. Beschluss 2026-08-31: "Es ist
wie mit COBOL — am Ende kriegen wir eh meist PDFs, Word war
Bequemlichkeit. Am Ende sehen wir ein binaeres Artefakt, und fuer die
Simulation haben wir eine Textquelle." Die Optik traegt das Altsystem:
Schreibmaschinenschrift (DejaVu Sans Mono, per Frontmatter), damit sich
das Quell-Dokument auch visuell vom modernen Zieltarifplan abhebt.

Der Formelanhang uebernimmt die Zeichenerklaerung der Tarifmeldung
(A.2) eins zu eins — einschliesslich ihres INDEXFEHLERS (Regie F3): Die
Kommutationszahl N(x) ist als Summe ab j=1 statt j=0 definiert, M(x)
korrekt. Der Fehler steckt NUR in der Doku; das Rechenwerk (VBA wie die
Python-Kopie) rechnet richtig. Zweck: Ein Fehler in der Tarifmeldung
wird nie maschinell "wegentschieden" — er erzwingt die menschliche
Abnahme. Wer ihn hier still repariert, nimmt der Vorfuehrung den Fall.

Das PDF ist nicht byte-deterministisch; massgeblich ist der registrierte
Hash des einmal erzeugten Artefakts — Wiederholbarkeit liefert die
Versionierung der Lieferung.
"""

from __future__ import annotations

import shutil
import subprocess
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
MD = Path(__file__).with_name("tarifbestimmungen.md")


def quelle() -> Path:
    """Die Markdown-Quelle — massgeblich, versioniert, editierbar."""
    return MD


def text() -> str:
    return MD.read_text(encoding="utf-8")


def als_pdf(ziel: Path) -> Path:
    """Das PDF ueber die Doku-Engine rendern und nach ``ziel`` legen.

    Rendert im Repo der Quelle (die Engine mountet das Repo-Root ihres
    eigenen Checkouts — Aufruf und Datei muessen im selben Baum liegen).
    """
    subprocess.run(
        ["bash", str(REPO_ROOT / "docs" / "engine" / "render.sh"),
         str(MD.relative_to(REPO_ROOT))],
        check=True, capture_output=True, timeout=300, cwd=REPO_ROOT,
    )
    erzeugt = MD.with_suffix(".pdf")
    if not erzeugt.is_file():
        raise FileNotFoundError(f"Die Engine hat kein PDF erzeugt: {erzeugt}")
    ziel = Path(ziel)
    ziel.parent.mkdir(parents=True, exist_ok=True)
    shutil.copyfile(erzeugt, ziel)
    return ziel
