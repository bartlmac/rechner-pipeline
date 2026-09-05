"""TOML configuration for the Bestandsdaten generator.

Text-based config (no Excel), read with stdlib ``tomllib`` and validated with
plain dataclasses returning error lists — the repo's schema idiom, no external
schema library. The category structure follows the DAV reference toolchain's
parameter semantics (tariff master data, distributions, correlations,
simulation/plausibility) with our own parameter values.

Layout (see ``configs/bestand_klv.toml``)::

    [meta]                      seed, beschreibung
    [[generation]]              tariff generation (validity window, produkt,
                                zins, tafel(n), cost loadings, sample_size, ...)
    [generation.verteilungen.<merkmal>]   distribution spec per attribute
    [[generation.korrelation]]  pairwise Spearman rank correlations
    [plausibilitaet]            value bands for the sanity gate
    [annahmen]                  Erfahrungsannahmen (3. Ordnung) je Ereignisart
                                als affine Transformation der ersten Ordnung
    [tagesbetrieb]              Tagesbetrieb der Vorzeige (Fachkonzept
                                docs/simulation/tagesbetrieb.md): Betriebsbeginn,
                                Wochentagsgewichte des Neugeschaefts, Meldeverzug

Knoten: klv, bu
"""

from __future__ import annotations

import datetime as _dt
import re
import tomllib
import dataclasses as _dc
import math
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Dict, List, Mapping, Optional, Tuple

from rechner_pipeline.models.bestand import (
    BU_GENERATION_FIELDS,
    GENERATION_FIELD_DEFAULTS,
    GENERATION_FIELDS,
    PRODUKT_VALUES,
)

_D = GENERATION_FIELD_DEFAULTS  # Kernel-Defaults der Tarif-Stellschrauben

#: Attributes every generation must configure a distribution for — je Produkt
#: (BU zieht die Jahresrente statt Versicherungssumme; Beitragsdauer und
#: Zahlweise sind beim BU-Beispielprodukt fachlich festgelegt).
REQUIRED_MERKMALE_JE_PRODUKT: Dict[str, Tuple[str, ...]] = {
    "klv": ("entry_age", "sex", "duration", "premium_duration", "sum_insured", "zahlweise"),
    "bu": ("entry_age", "sex", "duration", "bu_rente"),
}
#: Rueckwaertskompatibler Alias (KLV-Merkmale).
REQUIRED_MERKMALE: Tuple[str, ...] = REQUIRED_MERKMALE_JE_PRODUKT["klv"]

#: Distribution types implemented without scipy (project decision 2026-08-11:
#: full takeover of the reference generation incl. copula, lean dependencies).
#: gamma/beta would need scipy and raise NotImplementedError when configured.
SUPPORTED_TYPES: Tuple[str, ...] = (
    "normal",
    "normal_trunc",
    "lognormal",
    "weibull",
    "poisson",
    "empirical_discrete",
)

#: Attributes allowed in the correlation matrix (transformed via latent
#: normal; categorical attributes work like the reference does gender) —
#: je Produkt genau die Merkmale seiner Zugreihenfolge. Ein Paar ausserhalb
#: davon waere im Generator ein nackter KeyError.
CORRELATABLE_JE_PRODUKT: Dict[str, Tuple[str, ...]] = {
    "klv": ("entry_age", "sex", "duration", "premium_duration", "sum_insured"),
    "bu": ("entry_age", "sex", "duration", "bu_rente"),
}
#: Rueckwaertskompatibler Alias (KLV-Merkmale).
CORRELATABLE: Tuple[str, ...] = CORRELATABLE_JE_PRODUKT["klv"]


@dataclass
class VerteilungsSpec:
    merkmal: str
    typ: str
    params: Dict[str, Any] = field(default_factory=dict)

    def validate(self) -> List[str]:
        errors: List[str] = []
        p = self.params
        if self.typ not in SUPPORTED_TYPES:
            errors.append(
                f"verteilung {self.merkmal}: typ {self.typ!r} nicht unterstuetzt "
                f"(unterstuetzt: {list(SUPPORTED_TYPES)}; gamma/beta erst bei realem Bedarf)"
            )
            return errors
        # Endlichkeit VOR den Bandpruefungen (Review T20-05): TOML laesst
        # ``sdlog = nan`` zu, und ``nan <= 0`` ist falsch — der Produzent
        # erzeugte 600 Vertraege mit sum_insured = NaN, Exit 0, Manifest
        # geschrieben. Jeder Zahlparameter und jedes Gewicht muss endlich
        # sein, bevor irgendein Vergleich etwas aussagt.
        for name, wert in p.items():
            werte = wert if isinstance(wert, (list, tuple)) else [wert]
            for einzel in werte:
                if isinstance(einzel, bool) or not isinstance(einzel, (int, float)):
                    continue
                if not math.isfinite(float(einzel)):
                    errors.append(
                        f"verteilung {self.merkmal}: {name} ist nicht endlich "
                        f"({einzel!r}) — TOML laesst nan/inf zu, ein "
                        "Verteilungsparameter nicht"
                    )
        if errors:
            return errors
        if self.typ in ("normal", "normal_trunc"):
            for k in ("mean", "sd"):
                if k not in p:
                    errors.append(f"verteilung {self.merkmal}: {k} fehlt")
            if "sd" in p and float(p["sd"]) <= 0:
                errors.append(f"verteilung {self.merkmal}: sd <= 0")
        if self.typ == "normal_trunc":
            for k in ("min", "max"):
                if k not in p:
                    errors.append(f"verteilung {self.merkmal}: {k} fehlt")
            if "min" in p and "max" in p and float(p["min"]) >= float(p["max"]):
                errors.append(f"verteilung {self.merkmal}: min >= max")
        if self.typ == "lognormal":
            for k in ("meanlog", "sdlog"):
                if k not in p:
                    errors.append(f"verteilung {self.merkmal}: {k} fehlt")
            if "sdlog" in p and float(p["sdlog"]) <= 0:
                errors.append(f"verteilung {self.merkmal}: sdlog <= 0")
        if self.typ == "weibull":
            for k in ("shape", "scale"):
                if k not in p or float(p[k]) <= 0:
                    errors.append(f"verteilung {self.merkmal}: {k} fehlt oder <= 0")
        if self.typ == "poisson":
            if "lambda" not in p or float(p["lambda"]) <= 0:
                errors.append(f"verteilung {self.merkmal}: lambda fehlt oder <= 0")
        if self.typ == "empirical_discrete":
            values = p.get("values")
            probs = p.get("probs")
            if not values or not probs:
                errors.append(f"verteilung {self.merkmal}: values/probs fehlen")
            elif len(values) != len(probs):
                errors.append(f"verteilung {self.merkmal}: values/probs ungleich lang")
            elif any(float(w) < 0 for w in probs) or sum(float(w) for w in probs) <= 0:
                errors.append(f"verteilung {self.merkmal}: probs muessen >= 0 sein, Summe > 0")
        return errors


@dataclass
class Korrelation:
    var_i: str
    var_j: str
    rho: float

    def validate(self, erlaubt: Tuple[str, ...] = CORRELATABLE) -> List[str]:
        errors: List[str] = []
        for v in (self.var_i, self.var_j):
            if v not in erlaubt:
                errors.append(
                    f"korrelation {self.var_i}/{self.var_j}: {v} nicht "
                    f"korrelierbar (erlaubt: {list(erlaubt)})"
                )
        if self.var_i == self.var_j:
            errors.append(f"korrelation {self.var_i}: var_i == var_j")
        if not -1.0 < float(self.rho) < 1.0:
            errors.append(f"korrelation {self.var_i}/{self.var_j}: rho ausserhalb (-1, 1)")
        return errors


#: Knoten-ID-Form (identisch zur Segment-Konvention in ontologie.ids;
#: bewusst lokal dupliziert — bestand importiert ontologie nicht, die
#: Schichtenkarte laesst diese Kante nicht zu).
_KNOTEN_ID = re.compile(r"^[a-z0-9_]+(/[a-z0-9_]+)+$")


@dataclass
class TarifZelle:
    """Eine Tarifzelle: Merkmalskombination + die Grundlagen, die dort gelten.

    Eine Generation ist nicht immer ein einziger Parametersatz. Die
    uebernommene TG2015 fuehrt sechs Zellen ueber ``status`` und
    ``tarifart``; zwoelf der siebzehn Kernfelder unterscheiden sich
    zwischen ihnen — bis zur Sterbetafel (Raucher/Nichtraucher) und zum
    Stornoabzug (der Haustarif hat keinen). Wer den Bestand mit EINEM
    Satz bewertet, rechnet die Raucher mit der Nichtrauchertafel.

    ``felder`` traegt nur die ABWEICHENDEN Kernfelder; alles Uebrige
    kommt aus der Generation. So bleibt sichtbar, was die Zelle
    ausmacht, statt siebzehn Werte je Zelle zu wiederholen.

    Welche Zelle ein Vertrag hat, sagt ``merkmale.parquet`` — nicht
    diese Datei. Hier stehen die Grundlagen, dort die Zuordnung.
    """

    auspraegungen: Dict[str, str]
    felder: Dict[str, Any] = field(default_factory=dict)

    @property
    def schluessel(self) -> Tuple[Tuple[str, str], ...]:
        """Kanonische, sortierte Form — die Reihenfolge darf nicht zaehlen."""
        return tuple(sorted((str(k), str(v)) for k, v in self.auspraegungen.items()))

    def validate(self) -> List[str]:
        errors: List[str] = []
        if not self.auspraegungen:
            errors.append("zelle: auspraegungen fehlen")
        unbekannt = sorted(set(self.felder) - set(GENERATION_FIELDS))
        if unbekannt:
            errors.append(
                f"zelle {dict(self.schluessel)}: unbekannte Kernfelder "
                f"{unbekannt} (erlaubt: {sorted(GENERATION_FIELDS)})"
            )
        return errors


@dataclass
class TarifGeneration:
    name: str
    gueltig_von: _dt.date
    gueltig_bis: _dt.date
    sample_size: int
    max_endalter: int
    #: Produkt der Generation (Kern-Registry-Kennung, vgl. PRODUKT_VALUES).
    #: "klv" = Kapitallebensversicherung (Default, Bestandsaufbau Stufe 1),
    #: "bu" = Berufsunfaehigkeit (Zustandsmodell-Konfiguration).
    produkt: str = "klv"
    #: Ontologie-Knoten dieser Generation (Pflicht): dieselbe ID-Konvention
    #: wie A-Box und Gate P-K1 (familie/generation, z. B. "klv/plv_1994" fuer
    #: PLV-eigene, "klv/tg2015" fuer migrierte Generationen). Jede
    #: Generation, die der Bestand rechnet, ist damit ein Knoten der
    #: Ontologie — keine Parametrierung am System vorbei. Die Wurzel muss
    #: dem Produkt entsprechen.
    knoten: str = ""
    #: Simulierter Neuzugang je Kalenderjahr (Fortschreibung ab
    #: Referenzstichtag); 0 = kein Neuzugang. Wirkt nur innerhalb des
    #: Gueltigkeitsfensters der Generation.
    neuzugang_pro_jahr: int = 0
    #: Jahresfaktor des Neuzugangs (Fachkonzept Tagesbetrieb, Abschnitt 4):
    #: Das Ziel des Kalenderjahres J ist
    #: ``neuzugang_pro_jahr * (1 + neuzugang_trend) ** (J - gueltig_von.year)``.
    #: Negativ laesst das Unternehmen schrumpfen, ohne dass jemand jedes
    #: Jahr eine Zahl pflegt; 0 (Default) ist der bisherige konstante Satz.
    neuzugang_trend: float = 0.0
    # Kernel-Tarifparameter (GENERATION_FIELDS des ModelPoint-Contracts):
    zins: float = 0.0
    tafel: str = ""
    alpha: float = 0.0
    beta1: float = 0.0
    gamma1: float = 0.0
    gamma2: float = 0.0
    gamma3: float = 0.0
    policy_fee: float = 0.0
    min_alter_flex: int = 0
    min_rlz_flex: int = 0
    # Tarifwerk-Stellschrauben; Defaults = Kernel-Defaults (Blattwerte):
    stoab_satz: float = _D["stoab_satz"]
    stoab_min: float = _D["stoab_min"]
    stoab_max: float = _D["stoab_max"]
    zillmer_dauer: int = _D["zillmer_dauer"]
    ratzu_zw2: float = _D["ratzu_zw2"]
    ratzu_zw4: float = _D["ratzu_zw4"]
    ratzu_zw12: float = _D["ratzu_zw12"]
    # BU-Rechnungsgrundlagen (nur fuer produkt = "bu"; Defaults = die des
    # BU-Beispielprodukts, siehe kern/produkte/bu.py):
    tafel_aktiv: str = "DAV1997_TAA"
    tafel_i: str = "DAV1997_I"
    tafel_ri: str = "DAV1997_RI"
    tafel_ti: str = "DAV1997_TI"
    zuschlag: float = 0.05
    #: Tarifzellen dieser Generation (leer = ein einziger Parametersatz).
    #: Die Werte oben sind dann die der Generation als ganzer; mit Zellen
    #: sind sie der gemeinsame Rumpf, den die Zellen ueberschreiben.
    zellen: List[TarifZelle] = field(default_factory=list)
    verteilungen: Dict[str, VerteilungsSpec] = field(default_factory=dict)
    korrelationen: List[Korrelation] = field(default_factory=list)

    def generation_fields(self) -> Dict[str, Any]:
        """The kernel-side tariff parameters (joined into ModelPoint kwargs)."""
        return {name: getattr(self, name) for name in GENERATION_FIELDS}

    def dimensionen(self) -> Tuple[str, ...]:
        """Die Merkmalsdimensionen, ueber die diese Generation aufgeteilt ist."""
        return tuple(sorted({k for z in self.zellen for k in z.auspraegungen}))

    def felder_fuer(self, auspraegungen: Mapping[str, str]) -> Dict[str, Any]:
        """Die Rechnungsgrundlagen der Zelle, die ``auspraegungen`` benennt.

        Ohne Zellen gilt der Satz der Generation — der heutige Zustand,
        unveraendert. Mit Zellen ist eine nicht getroffene Kombination ein
        harter Fehler und kein stiller Rueckfall auf den Rumpf: Der Rumpf
        ist bei mehrzelligen Generationen kein gueltiger Tarif, sondern
        nur der gemeinsame Teil. Ein Vertrag ohne Zelle waere sonst
        klaglos mit Grundlagen bewertet, die fuer ihn nie galten.
        """
        felder = self.generation_fields()
        if not self.zellen:
            return felder
        dims = self.dimensionen()
        gesucht = tuple(sorted(
            (d, str(auspraegungen[d])) for d in dims if d in auspraegungen
        ))
        for zelle in self.zellen:
            if zelle.schluessel == gesucht:
                felder.update(zelle.felder)
                return felder
        raise KeyError(
            f"generation {self.name}: keine Tarifzelle fuer {dict(gesucht)} "
            f"(Dimensionen {list(dims)}; bekannt: "
            f"{[dict(z.schluessel) for z in self.zellen]})"
        )

    def bu_generation_fields(self) -> Dict[str, Any]:
        """Die BU-Rechnungsgrundlagen (fuer BUModelPoint-kwargs)."""
        return {name: getattr(self, name) for name in BU_GENERATION_FIELDS}

    def required_merkmale(self) -> Tuple[str, ...]:
        return REQUIRED_MERKMALE_JE_PRODUKT.get(self.produkt, REQUIRED_MERKMALE)

    def validate(self) -> List[str]:
        errors: List[str] = []
        if not self.name:
            errors.append("generation: name fehlt")
        prefix = f"generation {self.name or '?'}"
        # Endlichkeit dort, wo Zahlen eintreten (externes Review T18-04):
        # TOML erlaubt ``gamma2 = nan`` und ``zins = inf``; beides passierte
        # die Config-Pruefung, und der Abschluss publizierte hunderte
        # nichtendlicher Zahlfelder, bevor die Kontrolle rot wurde. Eine
        # Rechnungsgrundlage ist eine Zahl — jede, auch in den Zellen.
        for feld in _dc.fields(self):
            wert = getattr(self, feld.name)
            if isinstance(wert, float) and not math.isfinite(wert):
                errors.append(
                    f"{prefix}: {feld.name} ist nicht endlich ({wert!r}) — "
                    "TOML laesst nan/inf zu, eine Rechnungsgrundlage nicht"
                )
        for zelle in self.zellen:
            for name, wert in zelle.felder.items():
                if isinstance(wert, float) and not math.isfinite(wert):
                    errors.append(
                        f"{prefix}: zelle {dict(zelle.schluessel)}: {name} "
                        f"ist nicht endlich ({wert!r})"
                    )
        if self.gueltig_von >= self.gueltig_bis:
            errors.append(f"{prefix}: gueltig_von >= gueltig_bis")
        if self.gueltig_bis.year > 2200:
            errors.append(
                f"{prefix}: gueltig_bis nach 2200 (Zeitachse: pandas-Timestamps "
                "enden 2262; Vertragsenden muessen darstellbar bleiben)"
            )
        if self.sample_size < 0:
            errors.append(f"{prefix}: sample_size negativ")
        # sample_size = 0 ist der UEBERNOMMENE Fall: Eine Generation, die
        # aus einer Migration in den Bestand kommt, wird nicht erzeugt —
        # ihre Vertraege liegen schon vor. Ihre Rechnungsgrundlagen
        # braucht die Config trotzdem, sonst kann der Bericht sie nicht
        # bewerten. Das Verbot der Null stammte aus der Zeit, in der jede
        # Generation eine erzeugte war.
        if not self.knoten:
            errors.append(
                f"{prefix}: knoten fehlt — jede Generation traegt ihre "
                "Ontologie-Knoten-ID (familie/generation, z. B. "
                f"'{self.produkt}/plv_2000'; migrierte Generationen die "
                "ID ihres Migrationsfalls)"
            )
        elif not _KNOTEN_ID.match(self.knoten):
            errors.append(
                f"{prefix}: knoten {self.knoten!r} ist keine gueltige "
                "Knoten-ID (Segmente aus Kleinbuchstaben/Ziffern/'_', "
                "mindestens familie/generation)"
            )
        elif self.knoten.split("/", 1)[0] != self.produkt:
            errors.append(
                f"{prefix}: knoten {self.knoten!r} hat die Wurzel "
                f"{self.knoten.split('/', 1)[0]!r}, das Produkt ist aber "
                f"{self.produkt!r} — die Knoten-Wurzel ist die Produktfamilie"
            )
        if self.sample_size > 1_000_000:
            errors.append(
                f"{prefix}: sample_size > 1_000_000 (police_id-Nummernkreis je "
                "Generation ist 10 Mio; Obergrenze schuetzt vor Kollisionen)"
            )
        if not 0 <= self.neuzugang_pro_jahr <= 10_000:
            errors.append(f"{prefix}: neuzugang_pro_jahr ausserhalb [0, 10000]")
        # Der Trend ist ein Faktor je Jahr: -1 waere ab dem zweiten Jahr
        # kein Verkauf mehr (und darunter ein negatives Ziel), ueber +1
        # eine Verdopplung je Jahr — beides ist kein Vertrieb, sondern ein
        # Tippfehler. Nichtendlich wird oben schon gemeldet.
        if math.isfinite(self.neuzugang_trend) and not (
            -1.0 < self.neuzugang_trend <= 1.0
        ):
            errors.append(
                f"{prefix}: neuzugang_trend {self.neuzugang_trend} ausserhalb "
                "(-1, 1] (Jahresfaktor des Neuzugangs)"
            )
        if not 0 < self.max_endalter <= 121:
            errors.append(f"{prefix}: max_endalter ausserhalb (0, 121]")
        if self.produkt not in PRODUKT_VALUES:
            errors.append(f"{prefix}: produkt {self.produkt!r} ausserhalb {list(PRODUKT_VALUES)}")
        errors.extend(self._validate_zellen(prefix))
        if self.zins <= -1.0:
            errors.append(f"{prefix}: zins <= -100%")
        if self.produkt == "bu":
            errors.extend(self._validate_bu(prefix))
        # Die Tarifwerte gelten je ZELLE. Ist die Generation aufgeteilt,
        # muss jede Zelle fuer sich stimmen; die Generation traegt dann nur
        # den gemeinsamen Rumpf, und dessen Tafel darf leer sein, weil sie
        # ohnehin aus der Zelle kommt. Ohne Zellen ist der Rumpf der Tarif
        # — dann pruefen dieselben Regeln ihn selbst.
        if self.produkt == "bu":
            errors.extend(self._validate_tarifwerte(
                prefix, self.tafel_aktiv, self.generation_fields()))
        elif not self.zellen:
            errors.extend(self._validate_tarifwerte(
                prefix, self.tafel, self.generation_fields()))
        else:
            for zelle in self.zellen:
                felder = {**self.generation_fields(), **zelle.felder}
                errors.extend(self._validate_tarifwerte(
                    f"{prefix}, zelle {dict(zelle.schluessel)}",
                    str(felder.get("tafel", "")), felder))
        for merkmal in self.required_merkmale():
            if merkmal not in self.verteilungen:
                errors.append(f"{prefix}: verteilung fuer {merkmal} fehlt")
        for spec in self.verteilungen.values():
            errors.extend(f"{prefix}: {e}" for e in spec.validate())
        seen = set()
        korrelierbar = CORRELATABLE_JE_PRODUKT.get(self.produkt, CORRELATABLE)
        for korr in self.korrelationen:
            errors.extend(f"{prefix}: {e}" for e in korr.validate(korrelierbar))
            key = tuple(sorted((korr.var_i, korr.var_j)))
            if key in seen:
                errors.append(f"{prefix}: korrelation {key} doppelt")
            seen.add(key)
        # Die Korrelations-Kombination muss als Matrix realisierbar sein —
        # sonst wuerde die PSD-Reparatur der Copula die konfigurierten Werte
        # stillschweigend (bis ~Faktor 2) verfaelschen. Nicht-PSD = Config-Fehler.
        if self.korrelationen and not any("korrelation" in e for e in errors):
            import numpy as np

            from rechner_pipeline.bestand.stochastik import build_corr_matrix

            matrix = build_corr_matrix(korrelierbar, self.korrelationen)
            min_eig = float(np.linalg.eigvalsh((matrix + matrix.T) / 2.0).min())
            if min_eig < -1e-8:
                errors.append(
                    f"{prefix}: Korrelations-Kombination nicht realisierbar "
                    f"(Matrix nicht positiv semidefinit, min. Eigenwert {min_eig:.3f}) "
                    "— rhos abschwaechen oder Paare entfernen"
                )
        return errors

    def _validate_tarifwerte(
        self, prefix: str, sterbetafel: str, felder: Mapping[str, Any]
    ) -> List[str]:
        """Die Regeln EINES Tarifs — der Generation oder einer ihrer Zellen."""
        errors: List[str] = []
        if not sterbetafel:
            errors.append(f"{prefix}: tafel fehlt")
        else:
            # max_endalter muss vor der Tafel-Erschoepfung liegen, sonst
            # kann ein voll validiertes Setup Vertraege erzeugen, deren
            # Fortschreibung im Kern an der Tafelgrenze scheitert.
            from rechner_pipeline.kern import MissingMortalityTableError
            from rechner_pipeline.kern.konventionen import MAX_ALTER
            from rechner_pipeline.kern.tafeln import basis as tafelbasis

            try:
                grenze = min(
                    (b.erschoepft - 1 if b.erschoepft is not None
                     else MAX_ALTER)
                    for b in (
                        tafelbasis("M", sterbetafel),
                        tafelbasis("F", sterbetafel),
                    )
                )
            except MissingMortalityTableError as exc:
                errors.append(f"{prefix}: {exc}")
            else:
                if self.max_endalter > grenze:
                    errors.append(
                        f"{prefix}: max_endalter {self.max_endalter} liegt hinter "
                        f"der Tafel-Erschoepfung von {sterbetafel} "
                        f"(letztes Alter mit Dx > 0: {grenze})"
                    )
        if float(felder.get("stoab_min", 0.0)) > float(felder.get("stoab_max", 0.0)):
            errors.append(f"{prefix}: stoab_min > stoab_max")
        if float(felder.get("stoab_satz", 0.0)) < 0:
            errors.append(f"{prefix}: stoab_satz < 0")
        if int(felder.get("zillmer_dauer", 0)) <= 0:
            errors.append(f"{prefix}: zillmer_dauer <= 0")
        for name in ("ratzu_zw2", "ratzu_zw4", "ratzu_zw12"):
            if float(felder.get(name, 0.0)) < 0:
                errors.append(f"{prefix}: {name} < 0")
        return errors

    def _validate_zellen(self, prefix: str) -> List[str]:
        """Die Zellen muessen EINEN Merkmalsraum aufspannen, luecken- und
        doppelfrei.

        Zwei Zellen mit demselben Schluessel machen die Auswahl von der
        Reihenfolge abhaengig; eine Zelle, die eine Dimension auslaesst,
        macht sie mehrdeutig. Beides faellt sonst erst bei der Bewertung
        auf — und dann als falsche Zahl, nicht als Fehler.
        """
        errors: List[str] = []
        if not self.zellen:
            return errors
        dims = self.dimensionen()
        gesehen: Dict[Tuple[Tuple[str, str], ...], int] = {}
        for i, zelle in enumerate(self.zellen):
            errors.extend(f"{prefix}, {e}" for e in zelle.validate())
            fehlend = sorted(set(dims) - set(zelle.auspraegungen))
            if fehlend:
                errors.append(
                    f"{prefix}: zelle {dict(zelle.schluessel)} laesst die "
                    f"Dimensionen {fehlend} offen — jede Zelle muss den "
                    "ganzen Merkmalsraum benennen, sonst ist die Zuordnung "
                    "eines Vertrags mehrdeutig"
                )
            if zelle.schluessel in gesehen:
                errors.append(
                    f"{prefix}: zelle {dict(zelle.schluessel)} doppelt "
                    f"(Position {gesehen[zelle.schluessel]} und {i}) — welche "
                    "gilt, waere Reihenfolge, nicht Fachlichkeit"
                )
            gesehen[zelle.schluessel] = i
        return errors

    def _validate_bu(self, prefix: str) -> List[str]:
        """BU-Rechnungsgrundlagen pruefen (Tafeln ladbar, Perioden stimmig)."""
        from rechner_pipeline.kern.tafeln import (
            MissingMortalityTableError,
            qx_vector,
            select_max_dauer,
            select_tafel,
        )

        errors: List[str] = []
        if self.zuschlag < 0.0:
            errors.append(f"{prefix}: zuschlag < 0")
        # Der Generator kappt die Laufzeit auf max_endalter - entry_age;
        # bei entry_age = max_endalter - 1 entsteht zwingend ein
        # Einjahresvertrag. Im Jahresmodell beginnt die BU-Rente aber
        # fruehestens am Jahrestag 1 — ein solcher Vertrag hat
        # Leistungsbarwert 0 und ist nicht tarifierbar (BU.netto_rate
        # wirft). Die Alters-Obergrenze muss also mindestens zwei Jahre
        # unter dem Endalter liegen.
        spec = self.verteilungen.get("entry_age")
        max_alter = None
        if spec is not None:
            if spec.typ == "normal_trunc" and "max" in spec.params:
                max_alter = int(float(spec.params["max"]))
            elif spec.typ == "empirical_discrete" and spec.params.get("values"):
                max_alter = int(max(float(v) for v in spec.params["values"]))
        if max_alter is not None and max_alter > self.max_endalter - 2:
            errors.append(
                f"{prefix}: entry_age bis {max_alter} laesst bei "
                f"max_endalter {self.max_endalter} Vertraege mit Laufzeit 1 zu "
                "— die BU-Rente beginnt fruehestens am Jahrestag 1, solche "
                "Vertraege sind nicht tarifierbar (entry_age-Obergrenze auf "
                f"{self.max_endalter - 2} senken oder max_endalter anheben)"
            )
        try:
            for sex in ("M", "F"):
                i_vektor = qx_vector(sex, self.tafel_i)
                q_vektor = qx_vector(sex, self.tafel_aktiv)
                # Markov-Grenze: die Wegzuege aus dem Anwaerterstand duerfen
                # sich nicht auf mehr als 1 summieren. Die DAV 1997 I setzt
                # die Invalidisierung ab Alter 70 auf 1 (Konvention) — ein
                # zu hohes max_endalter fuehrt sonst erst zur Laufzeit zum
                # Abbruch der Zustandsmodell-Engine.
                letztes_alter = self.max_endalter - 1
                verletzt = [
                    a for a in range(0, letztes_alter + 1)
                    if i_vektor[a] + q_vektor[a] > 1.0
                ]
                if verletzt:
                    errors.append(
                        f"{prefix}: Invalidisierung + Aktivensterblichkeit > 1 "
                        f"({sex}, Alter {verletzt[0]}..{verletzt[-1]}) — "
                        f"max_endalter {self.max_endalter} reicht in einen "
                        "Bereich, den die Tafel nicht als Uebergangs-"
                        "wahrscheinlichkeiten fuehrt"
                    )
        except MissingMortalityTableError as exc:
            errors.append(f"{prefix}: Invalidisierungstafel: {exc}")
        # Select-Tafeln je Geschlecht aufloesen (die DAV-Ausscheideordnungen
        # sind geschlechtsabhaengig, die synthetischen Platzhalter unisex).
        dauern = {}
        for feld in ("tafel_ri", "tafel_ti"):
            name = getattr(self, feld)
            for sex in ("M", "F"):
                try:
                    select_tafel(name, sex)
                    dauern[feld] = select_max_dauer(name, sex)
                except MissingMortalityTableError as exc:
                    errors.append(f"{prefix}: {feld} ({sex}): {exc}")
        if len(dauern) == 2 and dauern["tafel_ri"] != dauern["tafel_ti"]:
            errors.append(
                f"{prefix}: Select-Perioden ungleich (tafel_ri "
                f"{dauern['tafel_ri']}, tafel_ti {dauern['tafel_ti']}) — "
                "das BU-Produkt verlangt eine gemeinsame Periode"
            )
        return errors


@dataclass(frozen=True)
class Annahme:
    """Eine Erfahrungsannahme (3. Ordnung) als affine Transformation.

    Alle Ereignisannahmen der Fortschreibung entstehen nach EINER Regel
    aus den Rechnungsgrundlagen erster Ordnung::

        annahme(x) = a + b * x        (geklemmt auf [0, 1])

    Dabei ist ``x`` die Wahrscheinlichkeit erster Ordnung des Ereignisses.
    Der multiplikative Teil ``b`` rechnet die Sicherheitsmarge heraus — und
    zwar richtungsrichtig: bei belastenden Ausscheideordnungen (Tod mit
    Todesfallleistung, Invalidisierung) ist die erste Ordnung vorsichtig
    HOCH, also ``b < 1``; bei entlastenden (Reaktivierung) vorsichtig
    NIEDRIG, also ``b > 1``. Der additive Teil ``a`` trägt Ereignisse, für
    die es gar keine Rechnungsgrundlage gibt (Storno, Beitragsfreistellung,
    dynamische Erhöhung): dort ist ``b = 0`` und ``a`` die Rate selbst.

    Der Default ``a = 0, b = 1`` bedeutet „Annahme = Rechnungsgrundlage".

    WICHTIG: Diese Schicht verändert NUR die Simulation des Bestands, nie
    die Bewertung. Beiträge und Reserven rechnet der Kern unverändert auf
    erster Ordnung — die Trennung ist der Zweck der Schicht. Ebenso gilt:
    eine Annahme darf keine Gültigkeitsgrenze einer Tafel wegtransformieren
    (die Grenzprüfungen laufen auf der untransformierten Tafel).
    """

    a: float = 0.0
    b: float = 1.0

    def __call__(self, erste_ordnung: float) -> float:
        return min(1.0, max(0.0, self.a + self.b * erste_ordnung))

    def validate(self, name: str) -> List[str]:
        errors: List[str] = []
        # NaN vergleicht immer falsch und passierte jede Bandpruefung.
        for feld in ("a", "b"):
            if not math.isfinite(getattr(self, feld)):
                errors.append(f"annahmen {name}: {feld} ist nicht endlich")
        if errors:
            return errors
        if self.a < 0.0:
            errors.append(f"annahmen {name}: a < 0")
        if self.b < 0.0:
            errors.append(f"annahmen {name}: b < 0")
        if self.a >= 1.0:
            errors.append(f"annahmen {name}: a >= 1 (jedes Jahr sicheres Ereignis)")
        return errors


#: Die Ereignisarten der Fortschreibung — Name und fachliche Einordnung
#: (der Text nennt, ob es zu der Art ueberhaupt eine Rechnungsgrundlage
#: erster Ordnung gibt). Die Reihenfolge ist die Ausgabereihenfolge.
ANNAHME_FELDER: Tuple[Tuple[str, str], ...] = (
    ("tod", "Sterblichkeit des Versicherten (KLV: Todesfallleistung)"),
    ("storno", "Storno (keine Rechnungsgrundlage)"),
    ("beitragsfreistellung", "Beitragsfreistellung (keine Rechnungsgrundlage)"),
    ("erhoehung", "dynamische Erhoehung (keine Rechnungsgrundlage)"),
    ("invalidisierung", "Invalidisierung (BU)"),
    ("reaktivierung", "Reaktivierung (BU)"),
    ("aktivensterblichkeit", "Sterblichkeit im Anwaerterstand (BU)"),
    ("invalidensterblichkeit", "Sterblichkeit im Leistungsbezug (BU)"),
)


@dataclass
class Annahmen:
    """Erfahrungsannahmen (3. Ordnung) der Fortschreibung.

    Eine eigene Annahmenschicht neben den Rechnungsgrundlagen erster
    Ordnung (Tarifkalkulation) und den Bewertungsannahmen zweiter Ordnung
    (Bilanz, Ueberschussbeteiligung): sie beschreibt, wie sich der Bestand
    in der Modellwelt TATSAECHLICH entwickelt. Jede Ereignisart ist eine
    :class:`Annahme` — dieselbe affine Regel fuer alle, auch dort, wo es
    keine erste Ordnung gibt (dann ``b = 0``).

    ``erh_prozent`` ist keine Wahrscheinlichkeit, sondern die HOEHE der
    dynamischen Erhoehung (Anteil der aktuellen Versicherungssumme) und
    bleibt daher ein einfacher Wert.
    """

    # Default je Ereignisart ist die NULL-Annahme (a = 0, b = 0): eine
    # nicht konfigurierte Ereignisart findet nicht statt. Das ist bewusst
    # nicht die Identitaet (b = 1) — eine fehlende Annahme ist keine
    # Annahme, und ein stillschweigend simuliertes Ereignis waere die
    # gefaehrlichere Voreinstellung. Wer die erste Ordnung unveraendert
    # uebernehmen will, schreibt sie hin: ``tod = { a = 0.0, b = 1.0 }``
    # (im TOML genuegt ``tod = { a = 0.0 }``, denn dort ist b = 1 der
    # Default der EINZELNEN Annahme).
    tod: Annahme = field(default_factory=lambda: Annahme(a=0.0, b=0.0))
    storno: Annahme = field(default_factory=lambda: Annahme(a=0.0, b=0.0))
    beitragsfreistellung: Annahme = field(default_factory=lambda: Annahme(a=0.0, b=0.0))
    erhoehung: Annahme = field(default_factory=lambda: Annahme(a=0.0, b=0.0))
    invalidisierung: Annahme = field(default_factory=lambda: Annahme(a=0.0, b=0.0))
    reaktivierung: Annahme = field(default_factory=lambda: Annahme(a=0.0, b=0.0))
    aktivensterblichkeit: Annahme = field(default_factory=lambda: Annahme(a=0.0, b=0.0))
    invalidensterblichkeit: Annahme = field(default_factory=lambda: Annahme(a=0.0, b=0.0))
    erh_prozent: float = 0.0

    def validate(self) -> List[str]:
        errors: List[str] = []
        for name, _ in ANNAHME_FELDER:
            errors.extend(getattr(self, name).validate(name))
        if not math.isfinite(self.erh_prozent):
            errors.append("annahmen: erh_prozent ist nicht endlich")
        elif self.erh_prozent < 0.0:
            errors.append("annahmen: erh_prozent < 0")
        if self.erhoehung.a > 0.0 and self.erh_prozent == 0.0:
            errors.append(
                "annahmen: erhoehung mit Rate > 0 verlangt erh_prozent > 0"
            )
        return errors


#: Wochentage der Neugeschaefts-Gewichtung, in der Reihenfolge von
#: ``datetime.date.weekday()`` (Montag = 0).
WOCHENTAGE: Tuple[str, ...] = ("mo", "di", "mi", "do", "fr", "sa", "so")

#: Vorgabe des Fachkonzepts (docs/simulation/tagesbetrieb.md, Abschnitt 4):
#: kein Verkauf am Wochenende, etwas mehr am Montag, sonst gleichmaessig.
WOCHENTAGSGEWICHTE_VORGABE: Dict[str, float] = {
    "mo": 1.3, "di": 1.0, "mi": 1.0, "do": 1.0, "fr": 1.0, "sa": 0.0, "so": 0.0,
}

#: Verteilungen, die der Meldeverzug ziehen kann. Nur die lognormale ist
#: gebaut (Median und 95-Prozent-Quantil bestimmen sie vollstaendig);
#: eine weitere waere eine Erweiterung des Tagesjournals, keine Config.
MELDEVERZUG_VERTEILUNGEN: Tuple[str, ...] = ("lognormal",)


@dataclass(frozen=True)
class Meldeverzug:
    """Wie lange das Unternehmen von einem Vorfall NICHT weiss.

    Fachkonzept Tagesbetrieb, Abschnitt 3: Ein Tod wirkt am Wirkungstag,
    gebucht wird er erst, wenn er gemeldet ist. Der Verzug wird je Police
    und Jahr deterministisch aus dieser Verteilung gezogen — Median und
    95-Prozent-Quantil in Tagen legen die lognormale Verteilung fest.

    VORLAEUFIG (Abschnitt 10 des Konzepts, offene Fachentscheidung):
    Median 14 Tage, 95 Prozent unter 60 Tagen sind der Vorschlag des
    Konzepts, nicht die Entscheidung des Aktuariats der Vorzeige.
    """

    verteilung: str = "lognormal"
    median_tage: float = 14.0
    p95_tage: float = 60.0

    def validate(self, name: str) -> List[str]:
        errors: List[str] = []
        if self.verteilung not in MELDEVERZUG_VERTEILUNGEN:
            errors.append(
                f"{name}: verteilung {self.verteilung!r} nicht unterstuetzt "
                f"(unterstuetzt: {list(MELDEVERZUG_VERTEILUNGEN)})"
            )
        for feld in ("median_tage", "p95_tage"):
            if not math.isfinite(getattr(self, feld)):
                errors.append(f"{name}: {feld} ist nicht endlich")
        if errors:
            return errors
        if self.median_tage <= 0.0:
            errors.append(f"{name}: median_tage <= 0")
        if self.p95_tage <= self.median_tage:
            errors.append(
                f"{name}: p95_tage ({self.p95_tage}) muss ueber median_tage "
                f"({self.median_tage}) liegen — sonst ist die Verteilung "
                "keine"
            )
        return errors


@dataclass
class Tagesbetrieb:
    """Der Tagesbetrieb der Vorzeige (Fachkonzept docs/simulation/tagesbetrieb.md).

    * ``betriebsbeginn``: der erste Kalendertag, an dem taeglich verkauft
      wird. Der Basisbestand entsteht bis einschliesslich dieses Tages aus
      dem Batch-Erzeuger (Beginn <= betriebsbeginn), danach bringt jeder
      Werktag sein Neugeschaeft — ein Erzeuger je Zeitfenster, wie beim
      Referenzstichtag der Fortschreibung. Ohne Angabe gibt es keinen
      Tagesbetrieb; der Tageslauf bricht dann hart ab.
    * ``wochentagsgewichte``: relatives Gewicht je Wochentag fuer die
      Verteilung des Jahresziels auf die Kalendertage (Abschnitt 4).
    * ``meldeverzug_tod``: Verteilung des Meldeverzugs bei Tod (Abschnitt 3).

    Die Werte gehoeren in die Config, nicht in den Code; ohne Abschnitt
    ``[tagesbetrieb]`` gelten die Vorgaben des Konzepts fuer Gewichte und
    Meldeverzug, und ``betriebsbeginn`` bleibt leer.
    """

    betriebsbeginn: Optional[_dt.date] = None
    wochentagsgewichte: Dict[str, float] = field(
        default_factory=lambda: dict(WOCHENTAGSGEWICHTE_VORGABE)
    )
    meldeverzug_tod: Meldeverzug = field(default_factory=Meldeverzug)

    def gewicht(self, tag: _dt.date) -> float:
        """Das Gewicht eines Kalendertags (nur vom Wochentag abhaengig)."""
        return float(self.wochentagsgewichte[WOCHENTAGE[tag.weekday()]])

    def validate(self) -> List[str]:
        errors: List[str] = []
        prefix = "tagesbetrieb"
        if self.betriebsbeginn is not None and not isinstance(
            self.betriebsbeginn, _dt.date
        ):
            errors.append(f"{prefix}: betriebsbeginn ist kein Datum")
        fehlend = sorted(set(WOCHENTAGE) - set(self.wochentagsgewichte))
        fremd = sorted(set(self.wochentagsgewichte) - set(WOCHENTAGE))
        if fehlend or fremd:
            errors.append(
                f"{prefix}: wochentagsgewichte brauchen genau die Schluessel "
                f"{list(WOCHENTAGE)} (fehlend {fehlend}, unbekannt {fremd})"
            )
            return errors + self.meldeverzug_tod.validate(f"{prefix} meldeverzug_tod")
        for tag in WOCHENTAGE:
            wert = self.wochentagsgewichte[tag]
            if isinstance(wert, bool) or not isinstance(wert, (int, float)):
                errors.append(f"{prefix}: wochentagsgewicht {tag} ist keine Zahl")
            elif not math.isfinite(float(wert)):
                errors.append(f"{prefix}: wochentagsgewicht {tag} ist nicht endlich")
            elif float(wert) < 0.0:
                errors.append(f"{prefix}: wochentagsgewicht {tag} < 0")
        if not errors and sum(float(v) for v in self.wochentagsgewichte.values()) <= 0.0:
            errors.append(
                f"{prefix}: wochentagsgewichte summieren auf 0 — an keinem "
                "Tag wuerde verkauft, das Jahresziel waere unerreichbar"
            )
        errors.extend(self.meldeverzug_tod.validate(f"{prefix} meldeverzug_tod"))
        return errors


@dataclass
class BestandConfig:
    seed: int
    beschreibung: str
    generationen: List[TarifGeneration]
    plausibilitaet: Dict[str, Tuple[float, float]] = field(default_factory=dict)
    annahmen: Annahmen = field(default_factory=Annahmen)
    #: Tagesbetrieb der Vorzeige (Fachkonzept docs/simulation/tagesbetrieb.md).
    tagesbetrieb: Tagesbetrieb = field(default_factory=Tagesbetrieb)
    #: Referenzstichtag des Bestands (Historie/Prognose-Grenze im
    #: Bericht): eine Eigenschaft des Bestands, in der Config gefuehrt —
    #: nicht des einzelnen Berichts-Aufrufs.
    referenzstichtag: Optional[_dt.date] = None

    def validate(self) -> List[str]:
        errors: List[str] = []
        if self.seed <= 0:
            errors.append("meta.seed fehlt oder <= 0 (Pflicht fuer Reproduzierbarkeit)")
        if not self.generationen:
            errors.append("mindestens eine [[generation]] erforderlich")
        names = [g.name for g in self.generationen]
        if len(names) != len(set(names)):
            errors.append("generation-Namen nicht eindeutig")
        for gen in self.generationen:
            errors.extend(gen.validate())
        errors.extend(self._validate_verkaufsfenster())
        for merkmal, band in self.plausibilitaet.items():
            if len(band) != 2 or not all(math.isfinite(float(g)) for g in band):
                errors.append(f"plausibilitaet {merkmal}: Band muss (min, max) aus endlichen Zahlen sein")
            elif float(band[0]) >= float(band[1]):
                errors.append(f"plausibilitaet {merkmal}: Band muss (min, max) mit min < max sein")
        errors.extend(self.annahmen.validate())
        errors.extend(self.tagesbetrieb.validate())
        return errors

    def _validate_verkaufsfenster(self) -> List[str]:
        """Ein Tag verkauft je Produkt genau EINE Generation.

        Fachkonzept Tagesbetrieb, Abschnitt 4: Ein Tag verkauft die
        Generation, deren Gueltigkeitsfenster ihn enthaelt — das ist nur
        eindeutig, wenn die Fenster verkaufender Generationen desselben
        Produkts nicht ueberlappen. Generationen, die nichts verkaufen
        (uebernommene: ``sample_size = 0`` ohne Neuzugang), duerfen ihr
        Fenster dagegen frei tragen — es beschreibt die Verkaufszeit beim
        abgebenden Unternehmen. KLV und BU ueberlappen selbstverstaendlich.
        """
        errors: List[str] = []
        verkaufend = [
            g for g in self.generationen
            if g.sample_size > 0 or g.neuzugang_pro_jahr > 0
        ]
        je_produkt: Dict[str, List[TarifGeneration]] = {}
        for gen in verkaufend:
            je_produkt.setdefault(gen.produkt, []).append(gen)
        for produkt, gens in sorted(je_produkt.items()):
            geordnet = sorted(gens, key=lambda g: (g.gueltig_von, g.name))
            for vorher, danach in zip(geordnet, geordnet[1:]):
                if danach.gueltig_von <= vorher.gueltig_bis:
                    errors.append(
                        f"generation {vorher.name} und {danach.name} "
                        f"(produkt {produkt}): Verkaufsfenster ueberlappen "
                        f"({vorher.gueltig_von.isoformat()}..{vorher.gueltig_bis.isoformat()} "
                        f"und {danach.gueltig_von.isoformat()}..{danach.gueltig_bis.isoformat()}) "
                        "— ein Tag verkauft je Produkt genau eine Generation"
                    )
        return errors


# --------------------------------------------------------------------------- #
# Loading
# --------------------------------------------------------------------------- #


def _to_date(value: Any, label: str, errors: List[str]) -> _dt.date:
    if isinstance(value, _dt.datetime):
        return value.date()
    if isinstance(value, _dt.date):
        return value
    errors.append(f"{label}: kein TOML-Datum")
    return _dt.date(1900, 1, 1)


def _lies_tagesbetrieb(roh: Any, errors: List[str]) -> Tagesbetrieb:
    """``[tagesbetrieb]`` lesen — fehlender Abschnitt = Vorgaben des Konzepts.

    Unbekannte Schluessel sind ein Ladefehler und kein stilles Ignorieren:
    ein vertippter ``wochentagsgewicht`` liefe sonst mit der Vorgabe
    durch, und niemand saehe, dass die Config nichts bewirkt.
    """
    if roh is None:
        return Tagesbetrieb()
    if not isinstance(roh, Mapping):
        errors.append("[tagesbetrieb] muss eine Tabelle sein")
        return Tagesbetrieb()
    bekannt = {"betriebsbeginn", "wochentagsgewichte", "meldeverzug_tod"}
    fremd = sorted(set(roh) - bekannt)
    if fremd:
        errors.append(
            f"tagesbetrieb: unbekannte Schluessel {fremd} "
            f"(bekannt: {sorted(bekannt)})"
        )
    kwargs: Dict[str, Any] = {}
    if "betriebsbeginn" in roh:
        kwargs["betriebsbeginn"] = _to_date(
            roh["betriebsbeginn"], "tagesbetrieb.betriebsbeginn", errors
        )
    if "wochentagsgewichte" in roh:
        gewichte = roh["wochentagsgewichte"]
        if not isinstance(gewichte, Mapping):
            errors.append(
                "tagesbetrieb: wochentagsgewichte muss eine Tabelle "
                "{ mo = ..., ..., so = ... } sein"
            )
        else:
            kwargs["wochentagsgewichte"] = {
                str(k): v for k, v in gewichte.items()
            }
    if "meldeverzug_tod" in roh:
        verzug = roh["meldeverzug_tod"]
        if not isinstance(verzug, Mapping):
            errors.append(
                "tagesbetrieb: meldeverzug_tod muss eine Tabelle "
                "{ verteilung = ..., median_tage = ..., p95_tage = ... } sein"
            )
        else:
            fremd = sorted(set(verzug) - {"verteilung", "median_tage", "p95_tage"})
            if fremd:
                errors.append(
                    f"tagesbetrieb meldeverzug_tod: unbekannte Schluessel {fremd}"
                )
            try:
                kwargs["meldeverzug_tod"] = Meldeverzug(
                    verteilung=str(verzug.get("verteilung", "lognormal")),
                    median_tage=float(verzug.get("median_tage", 14.0)),
                    p95_tage=float(verzug.get("p95_tage", 60.0)),
                )
            except (TypeError, ValueError) as exc:
                errors.append(f"tagesbetrieb meldeverzug_tod: {exc}")
    return Tagesbetrieb(**kwargs)


def load_config(path: Path) -> BestandConfig:
    """Load and structurally parse a config; call ``.validate()`` afterwards."""
    return config_aus_text(Path(path).read_text(encoding="utf-8"))


def config_aus_text(text: str) -> BestandConfig:
    """Eine Config aus ihrem TOML-Text parsen.

    Getrennt vom Dateizugriff, damit ein Konsument die Bytes, die er
    gehasht hat (Laufmanifest), auch parst — und nicht die Datei ein
    zweites Mal liest (T18-03: kein zweites Lesen zwischen Urteil und
    Verarbeitung).
    """
    raw = tomllib.loads(text)
    errors: List[str] = []
    meta: Mapping[str, Any] = raw.get("meta", {})

    generationen: List[TarifGeneration] = []
    for g in raw.get("generation", []):
        verteilungen: Dict[str, VerteilungsSpec] = {}
        for merkmal, spec in g.get("verteilungen", {}).items():
            params = {k: v for k, v in spec.items() if k != "typ"}
            verteilungen[merkmal] = VerteilungsSpec(
                merkmal=merkmal, typ=str(spec.get("typ", "")), params=params
            )
        korrelationen = [
            Korrelation(
                var_i=str(k.get("var_i", "")),
                var_j=str(k.get("var_j", "")),
                rho=float(k.get("rho", 0.0)),
            )
            for k in g.get("korrelation", [])
        ]
        # [[generation.zelle]] mit auspraegungen = {...} und den
        # abweichenden Kernfeldern direkt daneben. Unbekannte Felder
        # meldet TarifZelle.validate — hier wird nur gelesen.
        zellen = [
            TarifZelle(
                auspraegungen={
                    str(k): str(v)
                    for k, v in (z.get("auspraegungen", {}) or {}).items()
                },
                felder={k: v for k, v in z.items() if k != "auspraegungen"},
            )
            for z in g.get("zelle", [])
        ]
        generationen.append(
            TarifGeneration(
                name=str(g.get("name", "")),
                gueltig_von=_to_date(g.get("gueltig_von"), "gueltig_von", errors),
                gueltig_bis=_to_date(g.get("gueltig_bis"), "gueltig_bis", errors),
                sample_size=int(g.get("sample_size", 0)),
                max_endalter=int(g.get("max_endalter", 85)),
                produkt=str(g.get("produkt", "klv")),
                knoten=str(g.get("knoten", "")),
                neuzugang_pro_jahr=int(g.get("neuzugang_pro_jahr", 0)),
                neuzugang_trend=float(g.get("neuzugang_trend", 0.0)),
                zins=float(g.get("zins", 0.0)),
                tafel=str(g.get("tafel", "")),
                alpha=float(g.get("alpha", 0.0)),
                beta1=float(g.get("beta1", 0.0)),
                gamma1=float(g.get("gamma1", 0.0)),
                gamma2=float(g.get("gamma2", 0.0)),
                gamma3=float(g.get("gamma3", 0.0)),
                policy_fee=float(g.get("policy_fee", 0.0)),
                min_alter_flex=int(g.get("min_alter_flex", 0)),
                min_rlz_flex=int(g.get("min_rlz_flex", 0)),
                stoab_satz=float(g.get("stoab_satz", _D["stoab_satz"])),
                stoab_min=float(g.get("stoab_min", _D["stoab_min"])),
                stoab_max=float(g.get("stoab_max", _D["stoab_max"])),
                zillmer_dauer=int(g.get("zillmer_dauer", _D["zillmer_dauer"])),
                ratzu_zw2=float(g.get("ratzu_zw2", _D["ratzu_zw2"])),
                ratzu_zw4=float(g.get("ratzu_zw4", _D["ratzu_zw4"])),
                ratzu_zw12=float(g.get("ratzu_zw12", _D["ratzu_zw12"])),
                tafel_aktiv=str(g.get("tafel_aktiv", "DAV1997_TAA")),
                tafel_i=str(g.get("tafel_i", "DAV1997_I")),
                tafel_ri=str(g.get("tafel_ri", "DAV1997_RI")),
                tafel_ti=str(g.get("tafel_ti", "DAV1997_TI")),
                zuschlag=float(g.get("zuschlag", 0.05)),
                zellen=zellen,
                verteilungen=verteilungen,
                korrelationen=korrelationen,
            )
        )

    plausibilitaet: Dict[str, Tuple[float, float]] = {}
    for m, b in raw.get("plausibilitaet", {}).items():
        if isinstance(b, (list, tuple)) and len(b) == 2:
            plausibilitaet[str(m)] = (float(b[0]), float(b[1]))
        else:
            errors.append(f"plausibilitaet {m}: Band muss Liste [min, max] sein")

    # Die frühere [ereignisse]-Sektion ist durch [annahmen] abgelöst (die
    # Raten sind dort der a-Teil, tod_faktor der b-Teil). Sprechend
    # abweisen statt still ignorieren — sonst liefe eine alte Config mit
    # lauter Null-Annahmen durch.
    if "ereignisse" in raw:
        errors.append(
            "[ereignisse] wird nicht mehr gelesen — die Erfahrungsannahmen "
            "stehen jetzt unter [annahmen] als affine Transformation der "
            "ersten Ordnung (annahme = a + b * erste_ordnung): aus "
            "storno_rate = 0.03 wird storno = { a = 0.03, b = 0.0 }, aus "
            "tod_faktor = 1.0 wird tod = { a = 0.0, b = 1.0 }"
        )

    roh_annahmen: Mapping[str, Any] = raw.get("annahmen", {})
    annahme_kwargs: Dict[str, Any] = {}
    for name, _zweck in ANNAHME_FELDER:
        eintrag = roh_annahmen.get(name)
        if eintrag is None:
            continue
        if not isinstance(eintrag, Mapping):
            errors.append(
                f"annahmen {name}: erwartet Tabelle {{ a = ..., b = ... }}"
            )
            continue
        unbekannt = sorted(set(eintrag) - {"a", "b"})
        if unbekannt:
            errors.append(f"annahmen {name}: unbekannte Schluessel {unbekannt}")
            continue
        annahme_kwargs[name] = Annahme(
            a=float(eintrag.get("a", 0.0)), b=float(eintrag.get("b", 1.0))
        )
    fremde = sorted(
        set(roh_annahmen) - {n for n, _ in ANNAHME_FELDER} - {"erh_prozent"}
    )
    if fremde:
        errors.append(
            f"annahmen: unbekannte Ereignisarten {fremde} "
            f"(bekannt: {[n for n, _ in ANNAHME_FELDER]})"
        )
    if "erh_prozent" in roh_annahmen:
        annahme_kwargs["erh_prozent"] = float(roh_annahmen["erh_prozent"])
    annahmen = Annahmen(**annahme_kwargs)

    referenzstichtag: Optional[_dt.date] = None
    if "referenzstichtag" in meta:
        referenzstichtag = _to_date(
            meta.get("referenzstichtag"), "meta.referenzstichtag", errors
        )

    tagesbetrieb = _lies_tagesbetrieb(raw.get("tagesbetrieb"), errors)

    config = BestandConfig(
        seed=int(meta.get("seed", 0)),
        beschreibung=str(meta.get("beschreibung", "")),
        generationen=generationen,
        plausibilitaet=plausibilitaet,
        annahmen=annahmen,
        tagesbetrieb=tagesbetrieb,
        referenzstichtag=referenzstichtag,
    )
    if errors:
        raise ValueError("Config-Ladefehler: " + "; ".join(errors))
    return config
