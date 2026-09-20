"""Die Grenze der Korrekturschicht steht EINMAL im Code.

Die Aussage: *eine Schicht traegt ab ihrem Verankerungsmonat, davor
nicht.* Sie stand in sieben Modulen abgetippt — Ereignis-Engine,
Ledger-Herleitung, Herabsetzung (zweimal), Absorption, Fuehrungsprobe
und zuletzt die Uebernahme. Eine Abschrift zu vergessen kostet nichts,
solange niemand den Betrag nachrechnet; sobald ein Gate ihn herleitet,
faellt der Lauf. Genau so kam der Blocker der Vorzeige-Laufzeit
zustande: Die Fuehrung buchte die Beitragsfreistellung uebernommener
Vertraege mit Schichtzuschlag, die Uebernahme ohne — vier Buchungen, je
ein Cent, und P-B1 hielt an.

Drei Instrumente, weil eines nicht reicht (Muster aus T24):

1. **Die Grenze selbst**, in beide Richtungen gemessen — nicht nur
   "irgendwo dazwischen".
2. **Ein Klassentest ueber die Konsumenten**: wird die eine Grenze
   verbogen, biegt sich JEDER Konsument mit. Wer seine eigene Kopie
   fuehrt, faellt hier auf.
3. **Eine Ratsche gegen die achte Abschrift** — statisch ueber den
   Quelltext, mit Positivkontrolle, damit ein Detektor ohne Treffer
   nicht als Beweis durchgeht.

Knoten: klv
"""

from __future__ import annotations

import ast
from pathlib import Path

import pytest

from rechner_pipeline.kern import KLV_DEFAULT
from rechner_pipeline.kern.beitragsreduktion import absorbierte_schicht
from rechner_pipeline.kern.korrekturschicht import (
    Korrekturschicht,
    ab_verankerung,
    form_proportional_zur_basis,
    schicht_traegt,
    zuschlag_bei_pex,
)
from rechner_pipeline.kern.rechenkern import Rechenkern

REPO_ROOT = Path(__file__).resolve().parents[1]
SRC = REPO_ROOT / "src" / "rechner_pipeline"

#: Der Verankerungsmonat des Testvertrags (Vertragsjahr 9).
ANKER = 108
RESIDUUM = -850.0


def _kern_und_schicht():
    """Ein echter KLV-Vertrag mit einer Schicht, im Vertragsmonat 108
    verankert — die Lage der zwoelf Baldrian-Vertraege, deren
    Beitragsfreistellung GENAU auf dem Verankerungspunkt liegt."""
    kern = Rechenkern(KLV_DEFAULT)
    mp = KLV_DEFAULT
    basis = [kern.verlaufszeile(a).drx_bpfl for a in range(ANKER // 12, mp.n + 1)]
    bw = kern.produkt.bw
    schicht = Korrekturschicht(bw.modell, ((bw.AKTIV, bw.TOT),))
    form = form_proportional_zur_basis(basis)
    parameter = schicht.verankere(form, mp.x + ANKER // 12, bw.AKTIV, RESIDUUM)
    return kern, (parameter, ANKER)


# --------------------------------------------------------------------------- #
# 1. Die Grenze, in beide Richtungen
# --------------------------------------------------------------------------- #


@pytest.mark.parametrize(
    "monate, traegt, lage",
    [
        (0, False, "Vertragsbeginn — lange vor der Verankerung"),
        (ANKER - 12, False, "ein Jahr davor"),
        (ANKER - 1, False, "einen Monat davor"),
        (ANKER, True, "GENAU auf dem Verankerungspunkt"),
        (ANKER + 1, True, "einen Monat danach"),
        (ANKER + 12, True, "ein Jahr danach"),
    ],
)
def test_die_grenze_liegt_auf_dem_verankerungsmonat(
    monate: int, traegt: bool, lage: str
):
    """Einschliesslich, nicht ausschliesslich.

    Der Grenzfall ist kein Randfall: Alle zwoelf beitragsfreien
    Baldrian-Vertraege mit Zuschlag liegen GENAU auf ihm
    (``12 * pex_jahr == monate_ta``), weil die Lieferung solche
    Vertraege auf ihrer Beitragsfreistellung verankert. Wer die Grenze
    hier auf ``>`` stellt, aendert nicht einen Ausnahmefall, sondern
    jeden einzelnen davon.
    """
    assert ab_verankerung(ANKER, monate) is traegt, lage
    assert schicht_traegt(("egal", ANKER), monate) is traegt, lage


def test_ohne_schicht_traegt_nichts():
    """Der Nullfall ist Teil derselben Frage — ein nicht uebernommener
    Vertrag hat keine Schicht, und das ist keine Grenze, sondern ein
    Fehlen."""
    for monate in (0, ANKER - 1, ANKER, ANKER + 120):
        assert schicht_traegt(None, monate) is False


# --------------------------------------------------------------------------- #
# 2. Klassentest: jeder Konsument fragt DIESELBE Grenze
# --------------------------------------------------------------------------- #


@pytest.mark.parametrize("antwort", [True, False])
def test_jeder_konsument_folgt_der_einen_grenze(monkeypatch, antwort: bool):
    """Die Grenze wird verbogen — wer mitgeht, hat keine eigene Kopie.

    Gemessen an zwei Konsumenten aus zwei Modulen, die beide einen von
    null verschiedenen Wert liefern, sobald die Schicht traegt: die
    Absorption bei Beitragsfreistellung (``kern.korrekturschicht``) und
    die Aufnahme bei Herabsetzung (``kern.beitragsreduktion``). Sie
    haben nichts miteinander zu tun ausser dieser einen Frage — genau
    deshalb taugen sie als Probe. Die uebrigen Fundstellen deckt die
    Ratsche unten ab; sie haben keinen so billigen Aufruf.
    """
    kern, schicht = _kern_und_schicht()
    monkeypatch.setattr(
        "rechner_pipeline.kern.korrekturschicht.ab_verankerung",
        lambda monate_anker, monate: antwort,
    )
    jahr = ANKER // 12
    zuschlag = zuschlag_bei_pex(schicht, kern, jahr)
    aufnahme = absorbierte_schicht(kern, jahr, schicht)
    if antwort:
        assert zuschlag != 0.0
        assert aufnahme != 0.0
    else:
        assert zuschlag == 0.0
        assert aufnahme == 0.0


def test_die_probe_misst_ueberhaupt_etwas():
    """Positivkontrolle zum Test darueber: Ungepatcht traegt die Schicht
    im Verankerungsmonat, beide Konsumenten liefern einen Wert. Ohne
    diese Zeile waere ein durchgehend nulliger Vertrag eine gruene
    Bestaetigung ohne Aussage."""
    kern, schicht = _kern_und_schicht()
    jahr = ANKER // 12
    assert zuschlag_bei_pex(schicht, kern, jahr) != 0.0
    assert absorbierte_schicht(kern, jahr, schicht) != 0.0


# --------------------------------------------------------------------------- #
# 3. Ratsche: keine achte Abschrift
# --------------------------------------------------------------------------- #

VERGLEICH = (ast.Lt, ast.LtE, ast.Gt, ast.GtE)


def _ist_verankerungsmonat(knoten: ast.AST) -> bool:
    """Steht dieser Ausdruck fuer den Verankerungsmonat einer Schicht?

    Zwei Schreibweisen kommen vor: der benannte Parameter
    ``monate_anker`` und der Zugriff ``<irgendeine schicht>[1]`` auf das
    Paar (Parameter, Verankerungsmonat) — auch durch ``int(...)``
    verpackt.
    """
    if isinstance(knoten, ast.Name) and knoten.id == "monate_anker":
        return True
    if isinstance(knoten, ast.Call) and knoten.args:
        return any(_ist_verankerungsmonat(a) for a in knoten.args)
    if isinstance(knoten, ast.Subscript):
        index = knoten.slice
        if isinstance(index, ast.Constant) and index.value == 1:
            return "schicht" in ast.unparse(knoten.value).lower()
    return False


def _abschriften(quelle: str) -> list:
    """Jeder Vergleich gegen einen Verankerungsmonat in diesem Quelltext."""
    treffer = []
    for knoten in ast.walk(ast.parse(quelle)):
        if not isinstance(knoten, ast.Compare):
            continue
        if not any(isinstance(o, VERGLEICH) for o in knoten.ops):
            continue
        if any(_ist_verankerungsmonat(x)
               for x in (knoten.left, *knoten.comparators)):
            treffer.append((knoten.lineno, ast.unparse(knoten)))
    return treffer


def test_die_grenze_steht_genau_einmal_im_quelltext():
    """Genau EINE Fundstelle, und zwar die Definition.

    ``==``, nicht ``<=``: Eine Ratsche, die "hoechstens so viele wie
    heute" sagt, laesst die achte Abschrift durch, sobald jemand
    gleichzeitig eine alte entfernt. Die Ausnahme steht namentlich da,
    wo sie hingehoert.
    """
    gefunden = {
        str(p.relative_to(REPO_ROOT)): treffer
        for p in sorted(SRC.rglob("*.py"))
        if (treffer := _abschriften(p.read_text("utf-8")))
    }
    assert set(gefunden) == {"src/rechner_pipeline/kern/korrekturschicht.py"}, (
        "neue Abschrift der Schichtgrenze — ab_verankerung() fragen", gefunden)
    (_, ausdruck), = gefunden["src/rechner_pipeline/kern/korrekturschicht.py"]
    assert ausdruck == "monate >= monate_anker", ausdruck


def test_die_ratsche_findet_eine_abschrift():
    """Positivkontrolle: Ein Detektor ohne Treffer beweist nichts.

    Die vier Bauformen, in denen die Grenze frueher stand — alle vier
    muessen auffallen, sonst haelt die Ratsche nur die eine Schreibweise
    fest, die ich zufaellig im Kopf hatte."""
    bauformen = [
        "if schicht is not None and 12 * jahr >= int(schicht[1]):\n    pass\n",
        "if schicht is None or 12 * jahr < int(schicht[1]):\n    pass\n",
        "if self.schicht is not None and 12 * jahr >= self.schicht[1]:\n    pass\n",
        "if 12 * pex_jahr < monate_anker:\n    pass\n",
    ]
    for quelle in bauformen:
        assert _abschriften(quelle), quelle


def test_die_ratsche_schlaegt_nicht_auf_beliebige_vergleiche_an():
    """Gegenprobe zur Positivkontrolle: Ein Detektor, der alles findet,
    findet nichts. Monatsvergleiche ohne Verankerungsbezug bleiben
    unberuehrt."""
    for quelle in ("if 12 * jahr >= monate_stichtag:\n    pass\n",
                   "if monate < 12 * jahr_ta:\n    pass\n",
                   "if punkte[1] >= 3:\n    pass\n"):
        assert _abschriften(quelle) == [], quelle
