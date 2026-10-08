# Architektur

Architektur-Dokumente und Entscheidungen (ADRs) des **Systems** —
des agentischen KI-Systems für Bestandsmigration und
Rechenkern-Entwicklung. Die Fachdokumente des Beispiel-Rechenkerns
(des Illustrationsobjekts, PLV-Fiktion) liegen getrennt davon unter
`docs/tarifplaene/`.

## Inhalt

- [Prinzipien P1-P10 der Migrations-Pipeline](prinzipien.md)
- [Migrations-Pipeline v0.1: Ontologie als Stage-Interface](migrations-pipeline-v01.md)
- [Skill-Architektur: die Agenten-Rollen des Gesamtsystems](skill-architektur.md)
- [Ablauf eines Migrationsfalls: vom Auftrag bis zur Auslieferung](ablauf-eines-falls.md)
- [Prüf-Gates: Vertrag und Versionen](gate-vertrag-und-versionen.md)
- [ADR-001: Repo-Zielstruktur entlang der Migrations-Pipeline](adr-001-repo-zielstruktur.md)
- [ADR-002: Fall-Arbeitsbereich — das Repo ist das System, nicht der Datenraum](adr-002-fall-arbeitsbereich.md)
- [ADR-003: Pydantic für T-Box und A-Box](adr-003-pydantic-fuer-ontologie.md)
- [ADR-004: Der Zielkern ist Thiele-Welt — Excel-Parität ist Übersetzungsbeleg, kein laufender Referenzwert](adr-004-thiele-kern-ohne-excel-referenzwerte.md)
- [ADR-005: Knoten-Hierarchie, Test-Bindung, Code-Karte und berechneter Impact](adr-005-knoten-hierarchie-und-impact.md)
- [ADR-006: Der Portierungs-Anwendungsfall wird ausser Betrieb genommen](adr-006-portierung-ausser-betrieb.md)
- [ADR-007: Parallele Migrationen in einem Kern — Trunk, knotengebundene Inkremente, Knoten-Lebenszyklus](adr-007-parallele-migrationen-ein-kern.md)
- [ADR-008: Signierte P9-Freigaben ausserhalb des Falls](adr-008-signierte-p9-freigaben.md)
- [ADR-009: Fall-Scope und Bestands-Pflichtbelege für A-M4](adr-009-fall-scope-und-gate-dag.md)
- [ADR-010: Aktuarieller Test und Migrationscontrolling sind getrennte Gates](adr-010-aktuarieller-test-und-controlling.md)
- [ADR-011: Bestandsführung mit geführtem Zustand und Journal](adr-011-bestandsfuehrung.md)
- [ADR-012: Gate-Namen sagen, wer entscheidet und worüber](adr-012-gate-namensordnung.md)
- [ADR-013: Der Kommutations-Kreuzcheck wird ausser Betrieb genommen](adr-013-kommutations-kreuzcheck-ausser-betrieb.md)
- [ADR-014: Bestandszugang getrennt vom Vertragsbeginn](adr-014-bestandszugang-getrennt-vom-vertragsbeginn.md)
- [ADR-015: Übernommenen Bestand fortschreiben — ab dem Zugang](adr-015-uebernommenen-bestand-fortschreiben.md)
- [ADR-016: Vorverdichtung liest Text-PDF (pypdf); OCR bleibt draussen](adr-016-pdf-vorverdichtung.md)
- [ADR-017: Vier Ebenen — Entwickler, KI-Tool, Vorzeige, Vorzeige-Werkzeuge](adr-017-vier-ebenen.md)
- [ADR-018: Rollenmodell des KI-Tools — Agenten legen vor, Menschen zeichnen, der Schluessel sagt, wer besetzt](adr-018-rollenmodell-und-schluesselklassen.md)
- [ADR-019: Die Testsuite laeuft parallel (pytest-xdist)](adr-019-parallele-testsuite.md)
  — `pytest-xdist` exakt gepinnt; der volle Lauf ist `-n 12 --dist loadfile`, eine Testdatei je Arbeiter.
- [ADR-020: Der Bestand entsteht aus dem Zugangsstrom — kein gezogener Anfangsbestand](adr-020-ein-erzeuger-bestand-aus-dem-zugangsstrom.md)
  — der Batch-Erzeuger entfaellt; jeder Vertrag entsteht mit seinem Zugang im Journal.
- [ADR-021: Belegrollen-Vertrag und Freigabesignatur wohnen in `models` — der Betriebseingang liest, was das Gate liest](adr-021-belegrollen-und-freigabe-in-models.md)
  — Belegrollen und Freigabesignatur an einem Ort, den Gate und Betriebseingang gleich lesen.
- [ADR-022: Zugangsabnahme A-B2 — der Betrieb nimmt den Migrationszugang mit einer Zugangsprobe ab](adr-022-zugangsabnahme-a-b2.md)
  — zwei Laeufe auf einer Kopie der Ablage, mit und ohne den Eingang; `mensch/betrieb` zeichnet A-B2 vor der Registrierung.
- [ADR-023: Herabsetzung und Teilkuendigung sind getrennte Geschaeftsvorfaelle](adr-023-herabsetzung-und-teilkuendigung.md)
  — `RED` wandelt den freiwerdenden Beitrag in beitragsfreie Summe, die Teilkuendigung (`TKU`) zahlt den gekuendigten Anteil mit seinem Rueckkaufswert aus.
- [ADR-024: T-Box 0.2.0 — Tarifwerk, Geschaeftsvorfaelle, Zustandsextrakt](adr-024-tbox-020-tarifwerk-gevo-zustandsextrakt.md)
  — Tarifwerk und Quellverfahren als belegte Aussagen der A-Box; jedes Kommando der Bestandsstrecke rechnet mit den Regeln der Spez.
- [ADR-025: Erstabnahme des Zielsystems — vier Gegenstaende, vier Rollen, ein Ort ausserhalb des Falls](adr-025-erstabnahme-des-zielsystems.md)
  — Kernstand, T-Box-Stand, Tarifwerk und Anfangsbestand werden einmal in der Linie abgenommen; ein Fall verweist darauf.
- [ADR-026: Lebenslauf eines Falls — Fallauftrag und Fallabbruch](adr-026-lebenslauf-eines-falls.md)
  — ein Fall beginnt mit dem vom Vorstand gezeichneten Auftrag A-M6 und endet mit Abnahme oder dem Abbruch A-M5.
- [ADR-027: Fünf Gegenstände des Repositorys — keine Infrastruktur](adr-027-fuenf-gegenstaende-keine-infrastruktur.md)
  — Laufzeit der PLV, Migrationssystem, Fall-Definitionen, Routinen, Webseite; die vier Ebenen aus ADR-017 bleiben die Importregel im Paket.

> **Zu den Gate-Namen:** Die Namen in allen älteren ADRs sind auf die
> Ordnung aus ADR-012 umgestellt (`G-2` heisst jetzt `A-M4`, `O3` heisst
> `P-K1` und so fort). Die Beschlüsse selbst sind unverändert; nur die
> Kennungen sind es nicht mehr. Wer einen alten Beleg oder eine ältere
> Notiz liest, findet die Zuordnung im Register in ADR-012.

Die Pakete `rechner_pipeline.ontologie` und `rechner_pipeline.spez`
setzen die Pipeline um; ihr Zusammenspiel und der Präzedenzfall
TG2012 -> TG2015 stehen im Pipeline-Dokument.

Generierte Sicht: [Landkarte des Zielsystems](landkarte.md) (Diagramme aus dem Code, drift-geprüft).
