"""Spez-Erzeugung: A-Box -> TarifSpez (deterministische Projektion).

Vorbedingungen sind hart (Gate O1 zuerst): die Generation muss
vollstaendig belegt sein und darf keine offenen Diskrepanzen tragen —
eine Spez aus unklaren Aussagen waere eine stille Entscheidung.

Das Struktur-Urteil (:class:`~rechner_pipeline.spez.schema.StrukturUrteil`)
wird hier BERECHNET, aus dem Vergleich zweier A-Box-Generationen und
den Faehigkeiten des Kern-Rueckgrats (verfuegbare Tafeln) — es ist ein
Ergebnis der Pipeline, keine Behauptung eines Agenten (P4).

Knoten: klv
"""

from __future__ import annotations

from typing import Dict, List, Optional, Set

from rechner_pipeline.ontologie.aussage import Wert, Zustand
from rechner_pipeline.ontologie.merge import werte_gleich
from rechner_pipeline.ontologie.tbox import (
    ABox,
    PFLICHT_PARAMETER,
    Parametrierungszelle,
    Tarifgeneration,
)
from rechner_pipeline.spez.schema import (
    Erweiterungsstelle,
    StrukturUrteil,
    TafelAbleitung,
    TarifSpez,
    ZellSpez,
)


class SpezFehler(ValueError):
    """Spez nicht erzeugbar — Vorbedingung verletzt (fail-fast)."""


def kern_tafeln() -> Set[str]:
    """Die Tafeln (xml-Ebene), die der Kern heute fuehrt."""
    from rechner_pipeline.kern import kommutation

    return set(kommutation._TABLES)  # noqa: SLF001 — bewusste Introspektion


def _generation(abox: ABox, gen_id: str) -> Tarifgeneration:
    treffer = [g for g in abox.generationen if g.id == gen_id]
    if not treffer:
        raise SpezFehler(
            f"Generation {gen_id!r} nicht in der A-Box "
            f"(vorhanden: {[g.id for g in abox.generationen]})"
        )
    return treffer[0]


def _pruefe_vorbedingungen(abox: ABox, gen: Tarifgeneration) -> None:
    offene = {d.id for d in abox.diskrepanzen if d.status == "offen"}
    probleme: List[str] = []
    for zelle in gen.zellen:
        for feld in PFLICHT_PARAMETER:
            aussage = zelle.parameter.get(feld)
            if aussage is None or aussage.zustand is not Zustand.BELEGT:
                zustand = aussage.zustand.value if aussage else "fehlt_in_extraktion"
                probleme.append(f"{gen.id}/{zelle.id}/{feld}: {zustand}")
            if aussage is not None and aussage.diskrepanz_id in offene:
                probleme.append(
                    f"{gen.id}/{zelle.id}/{feld}: offene Diskrepanz "
                    f"{aussage.diskrepanz_id}"
                )
    if gen.unisex is not None and gen.unisex.zustand is not Zustand.BELEGT:
        probleme.append(f"{gen.id}/unisex: {gen.unisex.zustand.value}")
    if probleme:
        raise SpezFehler(
            "Spez nicht erzeugbar — erst Gate O1 bestehen (Coverage + "
            "Diskrepanzen-Aufloesung): " + "; ".join(probleme[:10])
            + (f" (+{len(probleme) - 10} weitere)" if len(probleme) > 10 else "")
        )


def _wert(zelle: Parametrierungszelle, feld: str) -> Wert:
    return zelle.parameter[feld].wert


def _finaler_tafelname(basis: str, unisex: Optional[str]) -> str:
    """Der Tafelname, den der ModelPoint traegt (xml-exakt bei Unisex)."""
    return f"{basis}_{unisex}" if unisex else basis


def strukturvergleich(
    neu: Tarifgeneration,
    referenz: Optional[Tarifgeneration],
    vorhandene_tafeln: Set[str],
    unisex: Optional[str],
) -> StrukturUrteil:
    """Das Struktur-Urteil berechnen (deterministisch, belegbar)."""
    begruendung: List[str] = []
    neue_dimensionen: List[str] = []
    geaenderte: List[str] = []
    formel_erweiterungen: List[str] = []

    if referenz is not None:
        ref_dims = {d.id for d in referenz.dimensionen}
        neue_dimensionen = sorted(
            d.id for d in neu.dimensionen if d.id not in ref_dims
        )
        if neue_dimensionen:
            begruendung.append(
                "neue Merkmalsdimensionen (nur Parametrierungs-Aufloesung, "
                "kein Kern-Konzept): " + ", ".join(neue_dimensionen)
            )
        # Parameter-Aenderungen: je Pflichtfeld gegen die Referenzzelle(n).
        ref_werte = {
            feld: {_wert(z, feld) for z in referenz.zellen
                   if feld in z.parameter}
            for feld in PFLICHT_PARAMETER
        }
        for feld in PFLICHT_PARAMETER:
            neu_werte = {
                _wert(z, feld) for z in neu.zellen if feld in z.parameter
            }
            if not ref_werte.get(feld):
                continue
            if not any(
                werte_gleich(a, b)
                for a in neu_werte for b in ref_werte[feld]
            ) or len(neu_werte) > 1:
                geaenderte.append(feld)
        if geaenderte:
            begruendung.append(
                "geaenderte/differenzierte Parameter: " + ", ".join(geaenderte)
            )

    benoetigt: Set[str] = set()
    for zelle in neu.zellen:
        basis = str(_wert(zelle, "tafel"))
        # xml-Ebene: geschlechtsspezifische Vektoren der Basis …
        benoetigt.update({f"{basis}_M", f"{basis}_F"})
        # … und bei Unisex die abgeleitete Mischtafel.
        if unisex:
            benoetigt.add(_finaler_tafelname(basis, unisex))
    neue_tafeln = sorted(benoetigt - vorhandene_tafeln)
    if neue_tafeln:
        begruendung.append("neue Tafeln (Import/Ableitung): " + ", ".join(neue_tafeln))
    if unisex:
        begruendung.append(
            f"Unisex-Vorgabe {unisex}: als abgeleitete Mischtafel "
            "(min(1, f*qx_M + (1-f)*qx_F)) — Daten-Ableitung, keine "
            "Kern-Formelaenderung (exakter Tafelname gewinnt in der "
            "Kern-Aufloesung)"
        )
    if not begruendung:
        begruendung.append("keine strukturellen Unterschiede gefunden")

    ergebnis = (
        "parametrierung_mit_erweiterung" if formel_erweiterungen
        else "parametrierung"
    )
    return StrukturUrteil(
        ergebnis=ergebnis,
        referenz_generation=referenz.id if referenz else None,
        neue_dimensionen=neue_dimensionen,
        neue_tafeln=neue_tafeln,
        geaenderte_parameter=geaenderte,
        formel_erweiterungen=formel_erweiterungen,
        begruendung=begruendung,
    )


def baue_spez(
    abox: ABox,
    generation_id: str,
    referenz_id: Optional[str] = None,
    vorhandene_tafeln: Optional[Set[str]] = None,
) -> TarifSpez:
    """Die Tarif-Spez einer Generation aus der A-Box projizieren."""
    gen = _generation(abox, generation_id)
    referenz = _generation(abox, referenz_id) if referenz_id else None
    _pruefe_vorbedingungen(abox, gen)
    if vorhandene_tafeln is None:
        vorhandene_tafeln = kern_tafeln()

    unisex = str(gen.unisex.wert) if gen.unisex is not None else None
    urteil = strukturvergleich(gen, referenz, vorhandene_tafeln, unisex)

    zellen: List[ZellSpez] = []
    ableitungen: Dict[str, TafelAbleitung] = {}
    for zelle in sorted(gen.zellen, key=lambda z: z.id):
        model_point: Dict[str, Wert] = {}
        for feld, aussage in sorted(zelle.parameter.items()):
            if aussage.zustand is Zustand.BELEGT:
                model_point[feld] = aussage.wert
        basis = str(model_point["tafel"])
        final = _finaler_tafelname(basis, unisex)
        model_point["tafel"] = final
        if unisex:
            ableitungen[final] = TafelAbleitung(
                name=final,
                basis_m=f"{basis}_M",
                basis_f=f"{basis}_F",
                maenneranteil=int(unisex[1:]) / 100.0,
            )
        zellen.append(ZellSpez(
            knoten=f"{gen.id}/{zelle.id}",
            auspraegungen=dict(zelle.auspraegungen),
            model_point=model_point,
        ))

    tafel_importe = sorted(
        name for name in urteil.neue_tafeln if name not in ableitungen
    )
    erweiterungen = [
        Erweiterungsstelle(id=e, beschreibung=e)
        for e in urteil.formel_erweiterungen
    ]
    return TarifSpez(
        generation=gen.id,
        familie=gen.familie,
        urteil=urteil,
        unisex=unisex,
        zellen=zellen,
        tafel_importe=tafel_importe,
        tafel_ableitungen=[ableitungen[k] for k in sorted(ableitungen)],
        erweiterungsstellen=erweiterungen,
    )
