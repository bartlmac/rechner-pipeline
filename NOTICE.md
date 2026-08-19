# NOTICE — Drittmaterial

## Lizenzgrenze

Die MIT-Lizenz dieses Repositoriums (`LICENSE`) deckt den **Code** und
die hier selbst verfassten **Dokumente**. Sie deckt **nicht** die
Rechnungsgrundlagen in Form von Tafelvektoren, die unter
`src/rechner_pipeline/kern/tafeln.xml` liegen.

Sterbe- und Ausscheidetafeln der Deutschen Aktuarvereinigung (DAV)
sind Werke Dritter. Die Nutzungsrechte daran liegen beim jeweiligen
Rechteinhaber, nicht bei diesem Projekt. Wer dieses Repository oder
Teile davon nutzt, hat die Zulaessigkeit der Nutzung dieser Tafeln
selbst zu klaeren. Dieser Hinweis ist eine Tatsachenangabe und eine
Zustaendigkeitszuweisung — er ist keine Rechtsberatung und raeumt
keine Rechte ein.

## Was in `tafeln.xml` enthalten ist

Die Datei fuehrt 21 qx-Vektoren, jeder als reine Alter-zu-qx-Liste
(Alter 0 bis 123); Select-Tafeln zusaetzlich nach Auswahldauer. Der
Kern rechnet ausschliesslich auf diesen Vektoren, es gibt keine
Kommutationswerte in der Datei.

**DAV 1994 T** (2 Vektoren)

* `DAV1994_T_F`, `DAV1994_T_M`

**DAV 1997** (8 Vektoren, Ausscheideordnungen des BU-Produkts)

* `DAV1997_I_M`, `DAV1997_I_F` — Invalidisierung
* `DAV1997_TAA_M`, `DAV1997_TAA_F` — Aktivensterblichkeit
* `DAV1997_RI_M`, `DAV1997_RI_F` — Reaktivierung (Select, Periode 5)
* `DAV1997_TI_M`, `DAV1997_TI_F` — Invalidensterblichkeit (Select,
  Periode 5)

**DAV 2008 T** (6 Vektoren, inkl. Raucher-/Nichtraucher-Varianten)

* `DAV2008_T_F`, `DAV2008_T_M`
* `DAV2008_T_NR_F`, `DAV2008_T_NR_M` — Nichtraucher
* `DAV2008_T_R_F`, `DAV2008_T_R_M` — Raucher

**Abgeleitete Unisex-Mischungen** (2 Vektoren)

* `DAV2008_T_NR_U70`, `DAV2008_T_R_U70` — je Alter berechnet als
  `qx_U = min(1, 0.7 * qx_M + 0.3 * qx_F)` aus den beiden
  Geschlechtsvektoren derselben Raucher-Variante (Mischformel aus dem
  VBA des Quell-Rechners, Double-Arithmetik bit-treu nachgebildet).
  Sie sind keine eigenstaendige Tafel, sondern eine Rechenregel auf
  den darunterliegenden DAV-2008-T-Vektoren — die Rechtelage der
  Basisvektoren wird davon nicht beruehrt.

**SYNTH_\*** (3 Vektoren, frei erfunden)

* `SYNTH_BU_I`, `SYNTH_BU_RI`, `SYNTH_BU_TI` — im XML mit
  `quelle="synthetisch"` gekennzeichnet. Sie waren die Platzhalter des
  BU-Beispielprodukts, bevor die DAV-1997-Ordnungen vorlagen; sie sind
  kein Drittmaterial.

## Wie die Vektoren in dieses Repository kamen

Die Datei traegt ihre Herkunft so weit mit, wie sie belegt ist:

* Die **DAV-2008-T-Raucher-/Nichtraucher-Vektoren** und die daraus
  **abgeleiteten U70-Mischungen** wurden deterministisch aus der
  Vorverdichtung der synthetischen Quell-Arbeitsmappe
  `Tarifrechner_KLV_TG2015.xlsm` (Showcase-Lieferung der fiktiven
  Baldrian Leben, `lieferungen/baldrian/`) importiert — ueber
  `python -m rechner_pipeline.quellen.tafel_import`. Jeder dieser
  Vektoren traegt unmittelbar davor einen XML-Kommentar mit Quelldatei,
  SHA-256, Fundstelle (Blatt und Vektorname) bzw. der Ableitungsregel.
* Die **DAV-1997-Vektoren** wurden aus einer Beispiel-Arbeitsmappe
  DAV 1997 I uebernommen, die im Projekt bereitgestellt wurde; die
  Mappe selbst liegt nicht im Repository. Sie tragen die Herkunft im
  `quelle`-Attribut, einschliesslich des Hinweises, dass die Werte
  unveraendert sind und dass nur die Alter 0 bis 85 aus der Quelle
  stammen, waehrend 86 bis 123 mit dem Randwert fortgeschrieben sind
  (das Gitter des Loaders verlangt den vollen Altersbereich).
* Die vier Vektoren `DAV1994_T_F/M` und `DAV2008_T_F/M` stammen aus
  dem Anfangsbestand des Kerns: sie kamen mit der Uebersetzung des
  Excel/VBA-Rechners in das Python-Paket (Kern-Promotion) und tragen
  im XML **keinen** Provenienz-Vermerk. Das ist eine Luecke der
  Nachweiskette, kein Beleg fuer eine andere Herkunft.

## Offener Klaerungspunkt

Die abschliessende rechtliche Einordnung dieser Vektoren im
Projektkontext steht **noch aus** — insbesondere die Frage, in welcher
Form Tafelwerte der DAV in einem oeffentlichen Repository mitgeliefert
werden duerfen und ob die betroffenen Vektoren hier durch Vektoren
ohne Drittrechte ersetzt oder aus dem Repository ausgelagert werden
sollten.

Sachdienliche Hinweise, Korrekturen und Rueckmeldungen von Anwendern
sind ausdruecklich willkommen: bitte als Issue im Repository. Bis zu
einer Klaerung gilt der Hinweis oben — Nutzungsrechte an den
DAV-Tafeln sind von Anwendern selbst zu klaeren.
