"""Ein DOCX aus Ueberschriften und Absaetzen schreiben — ohne Fremdpaket.

Warum das hier steht: Die Quellsimulation erzeugt Unterlagen eines
abgebenden Unternehmens — Mitteilungen, aktuarielle Notizen, Anschreiben.
Bisher entstanden sie auf der Windows-Seite. Damit lag ein Teil des
Werkzeugs ausserhalb dieses Repos, obwohl die Vorfuehrung beansprucht,
dass sich alles hier nachvollziehen laesst.

Ein DOCX ist ein ZIP mit drei Pflichtteilen. Das reicht fuer Prosa mit
Ueberschriften, Absaetzen und einfachen Tabellen — mehr braucht eine
aktuarielle Notiz nicht. Wer Formatvorlagen, Kopfzeilen oder Bilder
braucht, nimmt ein richtiges Paket; dieses Modul soll klein bleiben.

**Deterministisch**: feste Zeitstempel im ZIP, feste Reihenfolge der
Eintraege. Derselbe Text ergibt dieselbe Datei — sonst wechselte der
sha256 im Eingangs-Register bei jedem Lauf, und die Registrierung wuerde
wertlos.

Versionierter Bestandteil des Quellsystems seit 2026-08-31 (Beschluss:
Quellsimulations-Tooling ist Code und wird wie das Ziel-Tooling
versioniert; nur die Regie — Aufloesungen, Seeds, absichtliche Defekte —
bleibt in simulation/). Uebernommen aus simulation/quellwerkzeug/
docx_schreiben.py, dort bleibt die Regie-Andockung.
"""

from __future__ import annotations

import zipfile
from pathlib import Path
from typing import Iterable, Sequence, Tuple, Union

_W = "http://schemas.openxmlformats.org/wordprocessingml/2006/main"

#: Fester Zeitstempel aller ZIP-Eintraege (Y, M, D, h, m, s).
_ZEITSTEMPEL = (2020, 1, 1, 0, 0, 0)

Block = Union[Tuple[str, str], Tuple[str, Sequence[Sequence[str]]]]

_CONTENT_TYPES = """<?xml version="1.0" encoding="UTF-8" standalone="yes"?>
<Types xmlns="http://schemas.openxmlformats.org/package/2006/content-types">
<Default Extension="rels" ContentType="application/vnd.openxmlformats-package.relationships+xml"/>
<Default Extension="xml" ContentType="application/xml"/>
<Override PartName="/word/document.xml" ContentType="application/vnd.openxmlformats-officedocument.wordprocessingml.document.main+xml"/>
<Override PartName="/word/styles.xml" ContentType="application/vnd.openxmlformats-officedocument.wordprocessingml.styles+xml"/>
</Types>"""

_DOC_RELS = """<?xml version="1.0" encoding="UTF-8" standalone="yes"?>
<Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships">
<Relationship Id="rId1" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/styles" Target="styles.xml"/>
</Relationships>"""

# Nur was gebraucht wird: ein Grundstil und zwei Ueberschriftenebenen.
# Ohne styles.xml setzt Word die Verweise auf pStyle still auf die
# Standardschrift zurueck — das Dokument saehe dann wie unformatierter
# Fliesstext aus.
_STYLES = """<?xml version="1.0" encoding="UTF-8" standalone="yes"?>
<w:styles xmlns:w="{w}">
<w:docDefaults><w:rPrDefault><w:rPr>
<w:rFonts w:ascii="Calibri" w:hAnsi="Calibri"/><w:sz w:val="22"/>
</w:rPr></w:rPrDefault></w:docDefaults>
<w:style w:type="paragraph" w:default="1" w:styleId="Normal">
<w:name w:val="Normal"/>
<w:pPr><w:spacing w:after="120"/></w:pPr>
</w:style>
<w:style w:type="paragraph" w:styleId="Title">
<w:name w:val="Title"/><w:basedOn w:val="Normal"/>
<w:pPr><w:spacing w:before="240" w:after="120"/></w:pPr>
<w:rPr><w:b/><w:sz w:val="36"/></w:rPr>
</w:style>
<w:style w:type="paragraph" w:styleId="Heading1">
<w:name w:val="heading 1"/><w:basedOn w:val="Normal"/>
<w:pPr><w:outlineLvl w:val="0"/><w:spacing w:before="240" w:after="120"/></w:pPr>
<w:rPr><w:b/><w:sz w:val="26"/></w:rPr>
</w:style>
</w:styles>""".format(w=_W)

_RELS = """<?xml version="1.0" encoding="UTF-8" standalone="yes"?>
<Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships">
<Relationship Id="rId1" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/officeDocument" Target="word/document.xml"/>
</Relationships>"""



def _text(s: str) -> str:
    return (
        s.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")
    )


def _absatz(inhalt: str, stil: str = "") -> str:
    eigenschaften = f'<w:pPr><w:pStyle w:val="{stil}"/></w:pPr>' if stil else ""
    return (
        f"<w:p>{eigenschaften}"
        f'<w:r><w:t xml:space="preserve">{_text(inhalt)}</w:t></w:r></w:p>'
    )


def _tabelle(zeilen: Sequence[Sequence[str]]) -> str:
    rand = (
        "<w:tblBorders>"
        + "".join(
            f'<w:{k} w:val="single" w:sz="4" w:space="0" w:color="999999"/>'
            for k in ("top", "left", "bottom", "right", "insideH", "insideV")
        )
        + "</w:tblBorders>"
    )
    aus = [f"<w:tbl><w:tblPr>{rand}</w:tblPr>"]
    for zeile in zeilen:
        aus.append("<w:tr>")
        for zelle in zeile:
            aus.append(
                "<w:tc><w:tcPr><w:tcW w:w=\"0\" w:type=\"auto\"/></w:tcPr>"
                + _absatz(zelle)
                + "</w:tc>"
            )
        aus.append("</w:tr>")
    aus.append("</w:tbl>")
    # Word verlangt einen Absatz nach einer Tabelle.
    return "".join(aus) + "<w:p/>"


def schreibe_docx(pfad: Path, bloecke: Iterable[Block]) -> Path:
    """Ein DOCX aus ``(art, inhalt)``-Bloecken schreiben.

    Arten: ``titel``, ``ueberschrift``, ``absatz``, ``tabelle``. Bei
    ``tabelle`` ist ``inhalt`` eine Folge von Zeilen, sonst ein String.
    """
    koerper = []
    for art, inhalt in bloecke:
        if art == "tabelle":
            koerper.append(_tabelle(inhalt))
        elif art == "titel":
            koerper.append(_absatz(inhalt, "Title"))
        elif art == "ueberschrift":
            koerper.append(_absatz(inhalt, "Heading1"))
        elif art == "absatz":
            koerper.append(_absatz(inhalt))
        else:
            raise ValueError(
                f"unbekannte Blockart {art!r} — bekannt sind titel, "
                "ueberschrift, absatz, tabelle"
            )

    dokument = (
        '<?xml version="1.0" encoding="UTF-8" standalone="yes"?>'
        f'<w:document xmlns:w="{_W}"><w:body>'
        + "".join(koerper)
        + "</w:body></w:document>"
    )

    pfad.parent.mkdir(parents=True, exist_ok=True)
    with zipfile.ZipFile(pfad, "w", zipfile.ZIP_DEFLATED) as z:
        for name, inhalt_xml in (
            ("[Content_Types].xml", _CONTENT_TYPES),
            ("_rels/.rels", _RELS),
            ("word/_rels/document.xml.rels", _DOC_RELS),
            ("word/styles.xml", _STYLES),
            ("word/document.xml", dokument),
        ):
            eintrag = zipfile.ZipInfo(name, date_time=_ZEITSTEMPEL)
            eintrag.compress_type = zipfile.ZIP_DEFLATED
            eintrag.external_attr = 0o600 << 16
            z.writestr(eintrag, inhalt_xml.encode("utf-8"))
    return pfad
