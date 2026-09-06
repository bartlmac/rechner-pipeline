"""Die Dokumente der Quelle — Markdown-Quellen, PDF-Artefakte.

Die Quelle liefert ZWEI Dokumente, sauber getrennt (Beschluss
2026-09-01, vorher stand beides vermischt in einer Datei
"Tarifbestimmungen"):

* **AVB** (``avb.md``): die vertraglichen ZUSAGEN — rudimentaer, ohne
  eine einzige Formel. Bei einer Bestandsuebertragung gehen die
  Vertraege MIT ihren Bedingungen ueber; was hier zugesagt ist (Abzug
  je Baustein GESONDERT, Herabsetzung als Teilkuendigung MIT
  AUSZAHLUNG, Dynamik-Schranke), muss das aufnehmende Unternehmen
  abbilden.
* **Tarifplan / Mitteilung 143** (``tarifplan.md``): der aktuarielle
  Teil — Rechnungsgrundlagen, Kostensaetze je Bestandsgruppe,
  Kommutationsformeln, Rundungsvorschrift. Nachfolger des
  Alt-Artefakts ``Mitteilung_143_KLV_TG2015`` (dort DOCX, jetzt
  Markdown ueber dieselbe Doku-Engine wie die Zieltarifplaene).

Der Formelabschnitt des Tarifplans uebernimmt die Zeichenerklaerung
der Tarifmeldung eins zu eins — einschliesslich ihres INDEXFEHLERS
(Regie F3): Die Kommutationszahl N(x) ist als Summe ab j=1 statt j=0
definiert, M(x) korrekt. Der Fehler steckt NUR in der Doku; das
Rechenwerk (VBA wie die Python-Kopie) rechnet richtig. Zweck: Ein
Fehler in der Tarifmeldung wird nie maschinell "wegentschieden" — er
erzwingt die menschliche Abnahme. Wer ihn hier still repariert, nimmt
der Vorfuehrung den Fall.

**Quelle ist Markdown**, gerendert ueber die gepinnte Doku-Engine des
Repos (``docs/engine/render.sh``, Quarto/Typst) — derselbe Weg wie die
Zieltarifplaene. Die Optik traegt das Altsystem: Schreibmaschinenschrift
(DejaVu Sans Mono per Frontmatter), Absatzabstand genau eine Leerzeile,
Ueberschriften in Textgroesse (Typst-Vorspann in den Quellen).

Die PDFs sind nicht byte-deterministisch; massgeblich ist der
registrierte Hash des einmal erzeugten Artefakts — Wiederholbarkeit
liefert die Versionierung der Lieferung.
"""

from __future__ import annotations

import shutil
import subprocess
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
AVB = Path(__file__).with_name("avb.md")
TARIFPLAN = Path(__file__).with_name("tarifplan.md")


def text(md: Path) -> str:
    """Der massgebliche Inhalt eines Quell-Dokuments."""
    return Path(md).read_text(encoding="utf-8")


def als_pdf(md: Path, ziel: Path) -> Path:
    """Das PDF ueber die Doku-Engine rendern und nach ``ziel`` legen.

    Rendert im Repo der Quelle (die Engine mountet das Repo-Root ihres
    eigenen Checkouts — Aufruf und Datei muessen im selben Baum liegen).
    """
    md = Path(md)
    subprocess.run(
        ["bash", str(REPO_ROOT / "docs" / "engine" / "render.sh"),
         str(md.relative_to(REPO_ROOT))],
        check=True, capture_output=True, timeout=300, cwd=REPO_ROOT,
    )
    erzeugt = md.with_suffix(".pdf")
    if not erzeugt.is_file():
        raise FileNotFoundError(f"Die Engine hat kein PDF erzeugt: {erzeugt}")
    ziel = Path(ziel)
    ziel.parent.mkdir(parents=True, exist_ok=True)
    shutil.copyfile(erzeugt, ziel)
    return ziel
