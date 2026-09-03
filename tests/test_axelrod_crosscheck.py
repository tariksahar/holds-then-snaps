"""Cross-check our match engine against the `Axelrod` library (D-012).

We keep our own implementation - writing it is the point of the project - but
agreeing with an established reference implementation costs one optional
dependency and is worth a sentence in the report.

The whole module skips when `axelrod` is not installed, so the main suite runs
on the three pinned runtime dependencies alone. Install it with::

    python -m pip install -r requirements-dev.txt

Only the deterministic strategies are compared. Two stochastic strategies
cannot be expected to agree move for move across independent RNG streams, and
a comparison of their *distributions* would be a test of the random number
generators, not of the match engine.
"""

from __future__ import annotations

import itertools

import numpy as np
import pytest

from config import DEFAULT_CONFIG, DEFAULT_PAYOFFS
from strategies import STRATEGIES, Move
from tournament import play_match

axelrod = pytest.importorskip(
    "axelrod",
    reason="optional cross-check dependency; install requirements-dev.txt",
)

ROUNDS = 200

# Our name -> the equivalent Axelrod strategy class. Each pairing is a claim
# about behaviour, and every one of them is checked move-by-move below.
EQUIVALENTS = {
    "Always Cooperate": "Cooperator",
    "Always Defect": "Defector",
    "Tit-for-Tat": "TitForTat",
    "Grim Trigger": "Grudger",
    "Pavlov": "WinStayLoseShift",
    "Tit-for-Two-Tats": "TitFor2Tats",
}

TO_AXELROD_ACTION = {
    Move.COOPERATE: axelrod.Action.C,
    Move.DEFECT: axelrod.Action.D,
}


def reference_game() -> "axelrod.Game":
    """An Axelrod game built from *our* payoffs, not from their defaults.

    Built explicitly so the comparison stays honest if the project ever varies
    the payoff set, which D-003 says it will.
    """
    return axelrod.Game(
        r=DEFAULT_PAYOFFS.reward,
        s=DEFAULT_PAYOFFS.sucker,
        t=DEFAULT_PAYOFFS.temptation,
        p=DEFAULT_PAYOFFS.punishment,
    )


def reference_match(name_a: str, name_b: str, rounds: int):
    """Play the same matchup in the reference implementation."""
    players = (
        getattr(axelrod, EQUIVALENTS[name_a])(),
        getattr(axelrod, EQUIVALENTS[name_b])(),
    )
    match = axelrod.Match(players, turns=rounds, game=reference_game())
    match.play()
    return match


def test_the_reference_default_game_is_our_default_payoff_set() -> None:
    """Not required, but if it ever stops being true we want to know why."""
    r, p, s, t = axelrod.Game().RPST()
    assert (float(r), float(p), float(s), float(t)) == (
        DEFAULT_PAYOFFS.reward,
        DEFAULT_PAYOFFS.punishment,
        DEFAULT_PAYOFFS.sucker,
        DEFAULT_PAYOFFS.temptation,
    )


def test_every_mapped_reference_strategy_is_deterministic() -> None:
    """Guards the premise of the comparison rather than assuming it."""
    for our_name, their_name in EQUIVALENTS.items():
        player = getattr(axelrod, their_name)()
        assert not player.classifier["stochastic"], (
            f"{their_name}, mapped to {our_name}, is stochastic in the "
            "reference implementation; the move-by-move comparison is invalid"
        )


@pytest.mark.parametrize(
    "name_a,name_b", list(itertools.combinations_with_replacement(EQUIVALENTS, 2))
)
def test_matches_agree_move_for_move_with_the_reference(
    name_a: str, name_b: str
) -> None:
    """The strong form: not just the same score, the same match.

    Two implementations can reach an identical total by different routes, so
    comparing only the score would let a real behavioural difference through
    whenever it happened to be payoff-neutral.
    """
    ours = play_match(
        STRATEGIES[name_a],
        STRATEGIES[name_b],
        ROUNDS,
        DEFAULT_PAYOFFS,
        np.random.default_rng(DEFAULT_CONFIG.root_seed),
    )
    theirs = reference_match(name_a, name_b, ROUNDS)

    our_moves = [
        (TO_AXELROD_ACTION[a], TO_AXELROD_ACTION[b])
        for a, b in zip(ours.moves_a, ours.moves_b)
    ]
    assert our_moves == theirs.result, (
        f"{name_a} vs {name_b}: our match diverges from the reference"
    )


@pytest.mark.parametrize(
    "name_a,name_b", list(itertools.combinations_with_replacement(EQUIVALENTS, 2))
)
def test_per_round_scores_agree_with_the_reference(name_a: str, name_b: str) -> None:
    """The per-round averages are what Phase B consumes, so check those too."""
    ours = play_match(
        STRATEGIES[name_a],
        STRATEGIES[name_b],
        ROUNDS,
        DEFAULT_PAYOFFS,
        np.random.default_rng(DEFAULT_CONFIG.root_seed),
    )
    their_a, their_b = reference_match(name_a, name_b, ROUNDS).final_score_per_turn()

    assert ours.mean_a == pytest.approx(float(their_a))
    assert ours.mean_b == pytest.approx(float(their_b))


def test_the_two_named_invariants_hold_in_the_reference_too() -> None:
    """The invariants from PROJECT_STATE.md, checked against other code.

    If our TFT-vs-TFT identity were an artifact of our own implementation, this
    is where that would show up.
    """
    payoffs = DEFAULT_PAYOFFS

    tft = reference_match("Tit-for-Tat", "Tit-for-Tat", ROUNDS).final_score()
    assert float(tft[0]) == pytest.approx(ROUNDS * payoffs.reward)
    assert float(tft[1]) == pytest.approx(ROUNDS * payoffs.reward)

    grim, all_d = reference_match("Grim Trigger", "Always Defect", ROUNDS).final_score()
    assert float(grim) == pytest.approx(
        payoffs.sucker + (ROUNDS - 1) * payoffs.punishment
    )
    assert float(all_d) == pytest.approx(
        payoffs.temptation + (ROUNDS - 1) * payoffs.punishment
    )
