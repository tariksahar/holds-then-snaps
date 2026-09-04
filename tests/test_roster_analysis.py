"""The submatrix claim, and the machinery built on it.

Everything in `roster_analysis.py` rests on one assertion from D-027: a
sub-roster's tournament is the corresponding submatrix of the pool's, so no
sub-roster needs re-simulating. If that is false, every roster result is wrong.
It is tested here directly.
"""

from __future__ import annotations

import numpy as np
import pytest

from config import DEFAULT_CONFIG, POOL_CONFIG, trials_for
from roster_analysis import (
    COOPERATION_CUTOFF,
    Sweep,
    cooperation_rate_of,
    draw_sub_rosters,
    epsilon_ceiling,
    lowest_w_by_epsilon,
    map_distance,
)
from evolution import run_replicator
from strategies import STOCHASTIC
from tournament import run_round_robin

DETERMINISTIC_POOL = tuple(n for n in POOL_CONFIG.roster if n not in STOCHASTIC)


def test_a_sub_roster_tournament_is_exactly_the_submatrix_when_play_is_deterministic() -> None:
    """D-027's implementation note, asserted rather than assumed.

    With deterministic strategies, no error and a fixed horizon, nothing in the
    match consults the generator, so the equality is exact. `M[i, j]` is a
    property of the pair and the game parameters and cannot depend on who else
    entered - if the tournament ever started sharing state across pairs, this
    is the test that would catch it.
    """
    full_config = POOL_CONFIG.with_(
        roster=DETERMINISTIC_POOL,
        error_rate=0.0,
        continuation_probability=1.0,
    )
    full = run_round_robin(full_config)

    subset = DETERMINISTIC_POOL[::3]
    sub = run_round_robin(full_config.with_(roster=subset))
    indices = np.array([full.index_of(name) for name in subset])

    np.testing.assert_allclose(
        sub.payoff_matrix, full.payoff_matrix[np.ix_(indices, indices)]
    )
    np.testing.assert_allclose(
        sub.cooperation_matrix, full.cooperation_matrix[np.ix_(indices, indices)]
    )


def test_under_noise_a_re_run_sub_roster_matches_only_in_distribution() -> None:
    """The honest limit of the submatrix shortcut, and why it does not bite.

    Match RNG is keyed by roster position, and once epsilon > 0 or w < 1 every
    match consults the generator - for the error flips and the continuation
    draw - even between two deterministic strategies. So re-running a
    sub-roster draws a *different sample* of the same quantity, and the
    submatrix identity holds in distribution rather than exactly.

    This is not a defect for what the analysis does with it, because the
    analysis never re-runs anything. Every sub-roster is read off the same
    saved matrices, so all rosters share one sample, and a difference between
    two rosters cannot be sampling noise - it is the roster. Re-simulating per
    roster would have introduced exactly the noise this avoids.
    """
    noisy = POOL_CONFIG.with_(
        roster=DETERMINISTIC_POOL,
        error_rate=0.1,
        continuation_probability=0.9,
        trials=trials_for(0.9),
    )
    full = run_round_robin(noisy)
    subset = DETERMINISTIC_POOL[::3]
    sub = run_round_robin(noisy.with_(roster=subset))
    indices = np.array([full.index_of(name) for name in subset])
    restricted = full.payoff_matrix[np.ix_(indices, indices)]

    difference = np.abs(sub.payoff_matrix - restricted)
    assert difference.max() > 0, "expected two independent samples, not one"
    # Same quantity, sampled twice: close, on a payoff scale spanning 0 to 5.
    assert difference.max() < 0.25, difference


def test_stochastic_pairs_match_only_in_distribution() -> None:
    """The same limit, from the strategy side rather than the game side."""
    config = POOL_CONFIG.with_(trials=40)
    full = run_round_robin(config)
    subset = ("Always Cooperate", "Random", "Tit-for-Tat")
    sub = run_round_robin(config.with_(roster=subset))
    indices = np.array([full.index_of(name) for name in subset])
    restricted = full.payoff_matrix[np.ix_(indices, indices)]

    random_row = subset.index("Random")
    assert not np.allclose(sub.payoff_matrix, restricted), (
        "expected the Random rows to differ between samples"
    )
    # But close, because they are the same quantity sampled twice.
    assert np.abs(sub.payoff_matrix - restricted)[random_row].max() < 0.6
    # And the deterministic block is exact regardless.
    deterministic = [i for i in range(len(subset)) if i != random_row]
    np.testing.assert_allclose(
        sub.payoff_matrix[np.ix_(deterministic, deterministic)],
        restricted[np.ix_(deterministic, deterministic)],
    )


# --- the derived quantities ---------------------------------------------------


def _toy_sweep() -> Sweep:
    """Two strategies, two cells: one cooperative, one collapsed."""
    names = ("Nice", "Nasty")
    # Nice does well with itself; Nasty dominates.
    payoff = np.array([[[3.0, 0.0], [5.0, 1.0]], [[3.0, 0.0], [5.0, 1.0]]])
    cooperation = np.array([[[1.0, 1.0], [0.0, 0.0]], [[1.0, 1.0], [0.0, 0.0]]])
    return Sweep(
        names=names,
        keys=[(0.0, 0.9, 0), (0.2, 0.5, 0)],
        payoff=payoff,
        cooperation=cooperation,
    )


def test_cooperation_rate_of_a_single_strategy_roster() -> None:
    sweep = _toy_sweep()
    nice_only = np.array([0])
    rate, survivors = cooperation_rate_of(
        sweep.payoff[0], sweep.cooperation[0], nice_only
    )
    assert rate == pytest.approx(1.0)
    assert survivors == (0,)


def test_dropping_a_strategy_can_change_the_verdict() -> None:
    """The whole premise of the influence measurement."""
    sweep = _toy_sweep()
    both = cooperation_rate_of(sweep.payoff[0], sweep.cooperation[0], np.array([0, 1]))[0]
    nice_alone = cooperation_rate_of(
        sweep.payoff[0], sweep.cooperation[0], np.array([0])
    )[0]
    assert both < COOPERATION_CUTOFF < nice_alone


def test_epsilon_ceiling_reads_the_highest_viable_error_rate() -> None:
    assert epsilon_ceiling({(0.0, 0.9): 0.9, (0.1, 0.9): 0.8, (0.2, 0.9): 0.2}) == 0.1
    assert epsilon_ceiling({(0.0, 0.9): 0.1}) == -1.0


def test_epsilon_ceiling_ignores_a_cell_that_only_looks_cooperative() -> None:
    """A rate equal to ε is total collapse (D-028), not marginal cooperation."""
    collapsed = {(0.2, 0.99): 0.20, (0.18, 0.99): 0.18}
    assert epsilon_ceiling(collapsed) == -1.0


def test_lowest_w_by_epsilon_recovers_a_staircase() -> None:
    cell_map = {
        (0.0, 0.7): 0.9, (0.0, 0.9): 0.9,
        (0.1, 0.7): 0.1, (0.1, 0.9): 0.8,
        (0.2, 0.7): 0.2, (0.2, 0.9): 0.2,
    }
    assert lowest_w_by_epsilon(cell_map) == {0.0: 0.7, 0.1: 0.9, 0.2: None}


def test_map_distance_is_zero_between_a_map_and_itself() -> None:
    cell_map = {(0.0, 0.9): 0.5, (0.1, 0.9): 0.2}
    assert map_distance(cell_map, cell_map) == (0.0, 0.0)


def test_drawn_sub_rosters_are_valid_and_reproducible() -> None:
    rng = np.random.default_rng(DEFAULT_CONFIG.root_seed)
    first = draw_sub_rosters(15, (5, 9), 20, rng)
    rng = np.random.default_rng(DEFAULT_CONFIG.root_seed)
    second = draw_sub_rosters(15, (5, 9), 20, rng)

    assert len(first) == len(second) == 20
    for left, right in zip(first, second):
        np.testing.assert_array_equal(left, right)
    for roster in first:
        assert len(set(roster.tolist())) == len(roster), "no duplicates"
        assert roster.min() >= 0 and roster.max() < 15
        assert len(roster) in (5, 9)


def test_batched_replicator_matches_run_replicator() -> None:
    """The analysis's fast path must be the same maths as the slow one.

    `batched_final_shares` moves the per-cell loop into numpy so hundreds of
    rosters are affordable. If it drifted from `run_replicator`, every roster
    result would be wrong in a way nothing else would catch - so the two are
    compared directly on real saved matrices.
    """
    from pathlib import Path

    import roster_analysis as ra

    path = Path(__file__).parent.parent / "results" / "phase_c_matrices.npz"
    if not path.exists():
        pytest.skip("no saved sweep to check against")

    sweep = ra.load_sweep(path)
    indices = np.arange(len(sweep.names))
    sample = [0, 7, 40, 137]

    batched = ra.batched_final_shares(sweep.payoff[sample])
    for row, position in enumerate(sample):
        one = run_replicator(
            sweep.payoff[position],
            sweep.names,
            ra.EVOLUTION,
            initial_shares=np.full(len(indices), 1.0 / len(indices)),
        )
        np.testing.assert_allclose(
            batched[row], one.final_shares, rtol=0, atol=1e-12
        )


def test_roster_map_agrees_with_the_per_cell_path() -> None:
    from pathlib import Path

    import roster_analysis as ra

    path = Path(__file__).parent.parent / "results" / "phase_c_matrices.npz"
    if not path.exists():
        pytest.skip("no saved sweep to check against")

    sweep = ra.load_sweep(path)
    subset = np.array([0, 1, 2, 5, 7])
    cell_map, survivors = ra.roster_map(sweep, subset, replicates=1)

    for position, (epsilon, w, replicate) in enumerate(sweep.keys):
        if replicate != 0:
            continue
        rate, survived = ra.cooperation_rate_of(
            sweep.payoff[position], sweep.cooperation[position], subset
        )
        assert cell_map[(epsilon, w)] == pytest.approx(rate, abs=1e-9)
        assert survivors[(epsilon, w, replicate)] == survived
        break


def test_a_ceiling_at_the_edge_of_the_grid_is_reported_as_censored() -> None:
    """D-033's error, made impossible to repeat silently.

    A roster still cooperating in the last column has not shown a ceiling; it
    has shown that the grid stopped first. The two must not render the same.
    """
    import roster_analysis as ra

    still_going = {(0.0, 0.9): 0.9, (0.1, 0.9): 0.8, (0.2, 0.9): 0.7}
    assert ra.epsilon_ceiling(still_going) == 0.2
    assert ra.ceiling_is_censored(still_going)
    assert ra.format_ceiling(still_going) == "> 0.20"

    broke_first = {(0.0, 0.9): 0.9, (0.1, 0.9): 0.8, (0.2, 0.9): 0.2}
    assert ra.epsilon_ceiling(broke_first) == 0.1
    assert not ra.ceiling_is_censored(broke_first)
    assert ra.format_ceiling(broke_first) == "0.10"

    never = {(0.0, 0.9): 0.05, (0.2, 0.9): 0.2}
    assert ra.format_ceiling(never) == "none"
