# ADR-008: Signierte P9-Freigaben ausserhalb des Falls

Status: Angenommen  
Datum: 2026-08-20  
Entscheider: Auftraggeber durch ToDo 10.2

## Kontext

Ein P9-Snapshot lag bisher ausschliesslich im frei editierbaren
Fall-Arbeitsbereich. Sein gespeicherter Eigenhash wurde beim Lesen nicht
nachgerechnet; Gate, Command, Version, Dateiname und Vorgaengergraph waren
ebenfalls nicht vollstaendig validiert. Ein handgeschriebener G-1-Snapshot
und ein minimales als gruen bezeichnetes O1-Ledger konnten deshalb G-2
freischalten, obwohl die behaupteten Gates nie gelaufen waren.

Ein kanonischer Hash erkennt versehentliche oder nachtraegliche Aenderungen,
beweist allein aber keine menschliche Autorisierung: Wer den Fall aendern
kann, kann auch einen neuen Hash berechnen. Die Autoritaet muss deshalb
ausserhalb des Falls liegen oder asymmetrisch signieren. Das Python-Paket
soll zugleich SDK-frei bleiben und keine neue Kryptografie-Abhaengigkeit
erhalten.

## Entscheidung

1. Das allgemeine Gate-Ledger-Schema ist strikt. Pflicht- und Fremdfelder,
   echte boolesche und ganzzahlige Typen, ISO-8601-Zeiten, Status/Exit-Code
   sowie SHA-256-Maps werden vor jeder Beweisverwendung validiert. G-1/G-2
   bindet das O1-Ledger zusaetzlich exakt an Gate `O1.abox-contract`, Command
   `abox_validate`, die aktuelle Gate-Version und die Rollen-Hashschluessel
   `eingang.json` sowie `abgeleitet/abox/abox.json`.
2. P9-Snapshot-Schema ab v2 bindet Schema, Command `gate_entscheid`,
   Gate-Version, Gate, Entscheid, Rolle, Begruendung, Fall, Artefakt-Hashes,
   Systemstand, Entscheidungszeit, Vorgaenger und bei G-2 die O3-Belegmenge.
   Der kanonische SHA-256 umfasst alle persistierten Felder ausser sich
   selbst. Der Dateiname ist `<gate>-<vollstaendiger-sha256>.json`.
3. Beim Lesen wird jeder Snapshot des Gates validiert. Jeder Vorgaenger muss
   existieren, der Graph muss zyklenfrei sein und genau eine Spitze besitzen.
   Ein korrupter historischer Snapshot blockiert die gesamte Kette.
4. Jede menschliche Annahme traegt eine HMAC-SHA-256-Freigabe. Der HMAC
   autorisiert den vollstaendigen Snapshot-Inhalt vor Aufnahme des
   Freigabeobjekts; Domain-Separation verhindert die Wiederverwendung fuer
   andere Protokolle. Der Snapshot speichert nur Verfahren, SHA-256-ID des
   Schluessels und Signatur, niemals Schluesselbytes oder -pfad.
5. `--freigabe-schluessel <datei>` ist fuer eine Annahme erforderlich. Die
   Datei muss mindestens 32 kryptografisch zufaellige Byte lang sein,
   ausserhalb des Falls liegen und unter POSIX Rechte 0600 sowie genau einen
   Hardlink besitzen. Das Flag ist fuer einen Schluesselring
   wiederholbar: alle angegebenen Schluessel pruefen historische Snapshots,
   der letzte signiert einen neuen. Pfade werden im Gate-Ledger redigiert.
   Agenten erhalten keinen Zugriff auf dieses Schluesselmaterial; der Mensch
   fuehrt den Annahmeaufruf in seiner Autoritaetsumgebung aus.
6. Eine Ablehnung bleibt ohne Signatur moeglich. Das erhaelt den sicheren
   Agentenpfad `--rolle agent --entscheid abgelehnt`, ohne ihm eine
   Annahmeautoritaet zu geben.

## Konsequenzen

- Eine reine Fallmanipulation kann keine gueltige menschliche Annahme mehr
  erzeugen. Inhalt, Dateiname, Kette und Signatur werden bei G-2 neu
  berechnet statt geglaubt.
- Alte P9-Snapshots vor dem jeweils aktuellen Schema sind keine gueltigen
  Abnahmebelege fuer den neuen Vertrag. Offene Faelle muessen O1 erneut fahren
  und durch den Menschen auf dem aktuellen Stand neu entschieden werden.
  Vorher verschiebt der Mensch die Altdateien unveraendert in ein
  revisionsfestes Legacy-Verzeichnis; sie werden nicht automatisch
  umgedeutet, geloescht oder ueberschrieben.
- Schluesselbereitstellung, Backup und Zugriffskontrolle sind Betriebsaufgabe.
  Bei Rotation werden alte und neue Schluessel gemeinsam uebergeben, solange
  die Historie den alten Schluessel referenziert. Ein verlorener historischer
  Schluessel macht die betroffene Kette absichtlich nicht mehr verifizierbar.
- Wer eine Historie mit einer Annahme prueft oder fortschreibt, benoetigt den
  zugehoerigen Schluesselring. Ein Agent ohne Schluessel kann deshalb eine
  noch unentschiedene Kette ablehnen, aber keine bereits signierte Historie
  fortschreiben. Das ist die beabsichtigte Autoritaetsgrenze des
  symmetrischen Verfahrens.
- HMAC weist die Autorisierung der verwalteten Schluesselrolle nach, nicht
  die persoenliche Identitaet einer natuerlichen Person. Entscheider, Rolle
  und Begruendung bleiben deshalb Pflichtfelder des signierten Inhalts.

## Bewusst nicht Bestandteil dieser Entscheidung

- Hardware-Sicherheitsmodule, Betriebssystem-Keychains, Zertifikate und
  asymmetrische Mehrpersonen-Signaturen werden nicht eingebaut. Sie brauchen
  einen eigenen Betriebs- und Abhaengigkeitsentscheid; das Schema benennt
  sein Verfahren explizit und kann spaeter versioniert erweitert werden.
- Unveraenderliche Attempt-Ledger und ein atomarer Latest-Verweis sind ToDo
  10.12. Diese ADR macht den aktuell verwendeten Ledger strikt, ersetzt aber
  nicht dessen Speichersemantik.
- Der deklarative Fall-Scope und daraus abgeleitete G-2-Pflichtbelege sind in
  ADR-009 entschieden. Diese ADR sichert deren menschliche Freigabe, waehrend
  ADR-009 bestimmt, welche Belege ein konkreter Scope verlangt.

## Verworfene Alternativen

- Nur Eigenhash und inhaltsadressierter Dateiname: verworfen, weil ein
  Fallschreiber beides neu berechnen kann.
- Eine zweite frei beschreibbare Ankerdatei ausserhalb `entscheide/` aber im
  selben Fall: verworfen, weil sie dieselbe Autoritaetsgrenze haette.
- Eine neue asymmetrische Kryptografie-Abhaengigkeit: fuer diese Version
  verworfen, weil sie Paket-, ADR- und Betriebsaufwand erzeugt, obwohl eine
  extern verwahrte HMAC-Autoritaet den aktuellen Einzelrollenvertrag erfuellt.
