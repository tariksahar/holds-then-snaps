"""Supporting tests: reproducibility, configuration validation, roster shape.

Separate from `test_invariants.py`, which is reserved for the five named
invariants.
"""

from __future__ import annotations

import numpy as np
import pytest

from config import DEFAULT_CONFIG, DEFAULT_PAYOFFS, Config, Payoffs
from strategies import STRATEGIES, Move, random_player
from tournament import play_match, run_round_robin

SMALL = DEFAULT_CONFIG.with_(rounds=50, trials=3)


def test_round_robin_is_reproducible_from_the_root_seed() -> None:
    """Same config, same numbers - including the stochastic strategies."""
    first = run_round_robin(SMALL)
    second = run_round_robin(SMALL)
    np.testing.assert_array_equal(first.payoff_matrix, second.payoff_matrix)


def test_a_different_root_seed_moves_the_stochastic_entries_only() -> None:
    other = SMALL.with_(root_seed=SMALL.root_seed + 1)
    baseline = run_round_robin(SMALL)
    shifted = run_round_robin(other)

    random_index = baseline.names.index("Random")
    deterministic = [i for i in range(len(baseline.names)) if i != random_index]

    # Deterministic pairings ignore the generator entirely.
    np.testing.assert_array_equal(
        baseline.payoff_matrix[np.ix_(deterministic, deterministic)],
        shifted.payoff_matrix[np.ix_(deterministic, deterministic)],
    )
    assert baseline.payoff_matrix[random_index].tolist() != (
        shifted.payoff_matrix[random_index].tolist()
    )


def test_matrix_shape_and_bounds() -> None:
    result = run_round_robin(SMALL)
    n = len(SMALL.roster)
    assert result.payoff_matrix.shape == (n, n)
    assert result.payoff_matrix.min() >= DEFAULT_PAYOFFS.sucker
    assert result.payoff_matrix.max() <= DEFAULT_PAYOFFS.temptation


def test_leaderboard_covers_the_roster_and_is_sorted() -> None:
    result = run_round_robin(SMALL)
    assert {entry.name for entry in result.leaderboard} == set(SMALL.roster)
    scores = [entry.mean_per_round for entry in result.leaderboard]
    assert scores == sorted(scores, reverse=True)


def test_leaderboard_score_is_the_row_mean_of_the_matrix() -> None:
    """The leaderboard must be a view of the matrix, not a parallel tally."""
    result = run_round_robin(SMALL)
    for entry in result.leaderboard:
        row = result.payoff_matrix[result.index_of(entry.name)]
        assert entry.mean_per_round == pytest.approx(row.mean())
        assert entry.total == pytest.approx(row.sum() * result.rounds)


@pytest.mark.parametrize(
    "kwargs",
    [
        dict(temptation=3.0, reward=5.0, punishment=1.0, sucker=0.0),  # R > T
        dict(temptation=5.0, reward=3.0, punishment=0.0, sucker=1.0),  # S > P
        dict(temptation=7.0, reward=3.0, punishment=1.0, sucker=0.0),  # 2R < T+S
        dict(temptation=5.0, reward=3.0, punishment=0.0, sucker=-1.0),  # S < 0
    ],
)
def test_invalid_payoffs_are_rejected(kwargs: dict) -> None:
    with pytest.raises(ValueError):
        Payoffs(**kwargs)


def test_unknown_roster_name_is_rejected() -> None:
    with pytest.raises(ValueError, match="registry"):
        DEFAULT_CONFIG.with_(roster=("Tit-for-Tat", "Nonexistent Strategy"))


def test_duplicate_roster_entry_is_rejected() -> None:
    with pytest.raises(ValueError, match="duplicates"):
        DEFAULT_CONFIG.with_(roster=("Tit-for-Tat", "Tit-for-Tat"))


def test_registry_names_match_the_default_roster() -> None:
    assert set(DEFAULT_CONFIG.roster) <= set(STRATEGIES)


def test_random_players_do_not_mirror_each_other_in_self_play() -> None:
    """Self-play must give the two sides independent streams."""
    player = random_player(0.5)
    result = play_match(
        player, player, 200, DEFAULT_PAYOFFS, np.random.default_rng(0)
    )
    assert result.moves_a != result.moves_b


def test_pavlov_alternates_against_all_defect() -> None:
    """Win-stay-lose-shift never settles against an unconditional defector."""
    result = play_match(
        STRATEGIES["Pavlov"],
        STRATEGIES["Always Defect"],
        6,
        DEFAULT_PAYOFFS,
        np.random.default_rng(0),
    )
    assert result.moves_a == (
        Move.COOPERATE,
        Move.DEFECT,
        Move.COOPERATE,
        Move.DEFECT,
        Move.COOPERATE,
        Move.DEFECT,
    )


def test_tit_for_two_tats_absorbs_a_single_defection() -> None:
    tf2t = STRATEGIES["Tit-for-Two-Tats"]
    assert tf2t([Move.COOPERATE], [Move.DEFECT], np.random.default_rng(0)) is Move.COOPERATE
    assert (
        tf2t(
            [Move.COOPERATE, Move.COOPERATE],
            [Move.DEFECT, Move.DEFECT],
            np.random.default_rng(0),
        )
        is Move.DEFECT
    )
