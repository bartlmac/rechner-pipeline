# ADR-008: Signierte P9-Freigaben außerhalb des Falls

**Status:** angenommen am 2026-08-20 (Maintainer).

## Kontext

Ein P9-Snapshot lag bisher ausschließlich im frei editierbaren
Fall-Arbeitsbereich. Sein gespeicherter Eigenhash wurde beim Lesen nicht
nachgerechnet; Gate, Command, Version, Dateiname und Vorgängergraph waren
ebenfalls nicht vollständig validiert. Ein handgeschriebener A-Q1-Snapshot
und ein minimales als grün bezeichnetes P-Q3-Ledger konnten deshalb A-M4
freischalten, obwohl die behaupteten Gates nie gelaufen waren.

Ein kanonischer Hash erkennt versehentliche oder nachträgliche Änderungen,
beweist allein aber keine menschliche Autorisierung: Wer den Fall ändern
kann, kann auch einen neuen Hash berechnen. Die Autorität muss deshalb
außerhalb des Falls liegen oder asymmetrisch signieren. Das Python-Paket
soll zugleich SDK-frei bleiben und keine neue Kryptografie-Abhängigkeit
erhalten.

## Entscheidung

1. Das allgemeine Gate-Ledger-Schema ist strikt. Pflicht- und Fremdfelder,
   echte boolesche und ganzzahlige Typen, ISO-8601-Zeiten, Status/Exit-Code
   sowie SHA-256-Maps werden vor jeder Beweisverwendung validiert. A-Q1/A-M4
   bindet das P-Q3-Ledger zusätzlich exakt an Gate `P-Q3.fachliche-pruefung`, Command
   `abox_validate`, die aktuelle Gate-Version und die Rollen-Hashschlüssel
   `eingang.json` sowie `abgeleitet/abox/abox.json`.
2. P9-Snapshot-Schema ab v2 bindet Schema, Command `gate_entscheid`,
   Gate-Version, Gate, Entscheid, Rolle, Begründung, Fall, Artefakt-Hashes,
   Systemstand, Entscheidungszeit, Vorgänger und bei A-M4 die P-K1-Belegmenge.
   Der kanonische SHA-256 umfasst alle persistierten Felder außer sich
   selbst. Der Dateiname ist `<gate>-<vollstaendiger-sha256>.json`.
3. Beim Lesen wird jeder Snapshot des Gates validiert. Jeder Vorgänger muss
   existieren, der Graph muss zyklenfrei sein und genau eine Spitze besitzen.
   Ein korrupter historischer Snapshot blockiert die gesamte Kette.
4. Jede menschliche Annahme trägt eine HMAC-SHA-256-Freigabe. Der HMAC
   autorisiert den vollständigen Snapshot-Inhalt vor Aufnahme des
   Freigabeobjekts; Domain-Separation verhindert die Wiederverwendung für
   andere Protokolle. Der Snapshot speichert nur Verfahren, SHA-256-ID des
   Schlüssels und Signatur, niemals Schlüsselbytes oder -pfad.
5. `--freigabe-schluessel <datei>` ist für eine Annahme erforderlich. Die
   Datei muss mindestens 32 kryptografisch zufällige Byte lang sein,
   außerhalb des Falls liegen und unter POSIX Rechte 0600 sowie genau einen
   Hardlink besitzen. Das Flag ist für einen Schlüsselring
   wiederholbar: alle angegebenen Schlüssel prüfen historische Snapshots,
   der letzte signiert einen neuen. Pfade werden im Gate-Ledger redigiert.
   Agenten erhalten keinen Zugriff auf dieses Schlüsselmaterial; der Mensch
   führt den Annahmeaufruf in seiner Autoritätsumgebung aus.
6. Eine Ablehnung bleibt ohne Signatur möglich. Das erhält den sicheren
   Agentenpfad `--rolle agent/<name> --entscheid abgelehnt` (seit ADR-018
   mit Ebene), ohne ihm eine Annahmeautorität zu geben.

## Konsequenzen

- Eine reine Fallmanipulation kann keine gültige menschliche Annahme mehr
  erzeugen. Inhalt, Dateiname, Kette und Signatur werden bei A-M4 neu
  berechnet statt geglaubt.
- Alte P9-Snapshots vor dem jeweils aktuellen Schema sind keine gültigen
  Abnahmebelege für den neuen Vertrag. Offene Fälle müssen P-Q3 erneut fahren
  und durch den Menschen auf dem aktuellen Stand neu entschieden werden.
  Vorher verschiebt der Mensch die Altdateien unverändert in ein
  revisionsfestes Legacy-Verzeichnis; sie werden nicht automatisch
  umgedeutet, gelöscht oder überschrieben.
- Schlüsselbereitstellung, Backup und Zugriffskontrolle sind Betriebsaufgabe.
  Bei Rotation werden alte und neue Schlüssel gemeinsam übergeben, solange
  die Historie den alten Schlüssel referenziert. Ein verlorener historischer
  Schlüssel macht die betroffene Kette absichtlich nicht mehr verifizierbar.
- Wer eine Historie mit einer Annahme prüft oder fortschreibt, benötigt den
  zugehörigen Schlüsselring. Ein Agent ohne Schlüssel kann deshalb eine
  noch unentschiedene Kette ablehnen, aber keine bereits signierte Historie
  fortschreiben. Das ist die beabsichtigte Autoritätsgrenze des
  symmetrischen Verfahrens.
- HMAC weist die Autorisierung der verwalteten Schlüsselrolle nach, nicht
  die persönliche Identität einer natürlichen Person. Entscheider, Rolle
  und Begründung bleiben deshalb Pflichtfelder des signierten Inhalts.

## Bewusst nicht Bestandteil dieser Entscheidung

- Hardware-Sicherheitsmodule, Betriebssystem-Keychains, Zertifikate und
  asymmetrische Mehrpersonen-Signaturen werden nicht eingebaut. Sie brauchen
  einen eigenen Betriebs- und Abhängigkeitsentscheid; das Schema benennt
  sein Verfahren explizit und kann später versioniert erweitert werden.
- Unveränderliche Attempt-Ledger und ein atomarer Latest-Verweis sind ToDo
  10.12. Dieses ADR macht den aktuell verwendeten Ledger strikt, ersetzt aber
  nicht dessen Speichersemantik.
- Der deklarative Fall-Scope und daraus abgeleitete A-M4-Pflichtbelege sind in
  ADR-009 entschieden. Dieses ADR sichert deren menschliche Freigabe, während
  ADR-009 bestimmt, welche Belege ein konkreter Scope verlangt.

## Verworfene Alternativen

- Nur Eigenhash und inhaltsadressierter Dateiname: verworfen, weil ein
  Fallschreiber beides neu berechnen kann.
- Eine zweite frei beschreibbare Referenzdatei außerhalb `entscheide/` aber im
  selben Fall: verworfen, weil sie dieselbe Autoritätsgrenze hätte.
- Eine neue asymmetrische Kryptografie-Abhängigkeit: für diese Version
  verworfen, weil sie Paket-, ADR- und Betriebsaufwand erzeugt, obwohl eine
  extern verwahrte HMAC-Autorität den aktuellen Einzelrollenvertrag erfüllt.
