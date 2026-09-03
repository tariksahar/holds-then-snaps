"""Supporting tests for Phase B: the maths, the guards, and the reported result.

Separate from `test_invariants.py`, which is reserved for the five named
invariants.
"""

from __future__ import annotations

import numpy as np
import pytest

from config import DEFAULT_CONFIG, PROVISIONAL_EVOLUTION_CONFIG, EvolutionConfig
from evolution import (
    apply_extinction,
    equal_shares,
    fitness,
    largest_disagreement,
    population_payoff,
    replicator_step,
    run_replicator,
)
from tournament import run_round_robin

SMALL_TOURNAMENT = DEFAULT_CONFIG.with_(rounds=50, trials=3)

# A minimal two-strategy game used where the real matrix would obscure the
# point: row 0 always earns 2, row 1 always earns 1, whatever the mix.
FLAT = np.array([[2.0, 2.0], [1.0, 1.0]])


@pytest.fixture(scope="module")
def phase_a():
    return run_round_robin(SMALL_TOURNAMENT)


# --- the fitness map ---------------------------------------------------------


def test_selection_intensity_zero_freezes_the_population(phase_a) -> None:
    """At s = 0 every fitness is 1, so nothing can move. The degenerate case."""
    result = run_replicator(
        phase_a.payoff_matrix,
        phase_a.names,
        PROVISIONAL_EVOLUTION_CONFIG.with_(selection_intensity=0.0),
    )
    np.testing.assert_allclose(
        result.final_shares, result.initial_shares, rtol=0, atol=1e-15
    )
    assert result.settled_generation == 0


def test_selection_intensity_one_is_the_raw_payoff(phase_a) -> None:
    shares = equal_shares(len(phase_a.names))
    np.testing.assert_allclose(
        fitness(phase_a.payoff_matrix, shares, 1.0),
        population_payoff(phase_a.payoff_matrix, shares),
    )


def test_adding_a_constant_to_every_payoff_changes_the_pace_not_the_order():
    """Why s exists at all.

    Shifting every payoff by a constant is not a change to the game, but it
    does change how fast the bare replicator ratio moves. The ranking of the
    step must survive it even though the step sizes do not.
    """
    shares = np.array([0.5, 0.5])
    stepped = replicator_step(FLAT, shares, selection_intensity=1.0)
    shifted = replicator_step(FLAT + 10.0, shares, selection_intensity=1.0)

    assert stepped[0] > shares[0] and shifted[0] > shares[0]
    # Same direction, materially different speed.
    assert stepped[0] - shares[0] > 3 * (shifted[0] - shares[0])


def test_non_positive_mean_fitness_is_refused() -> None:
    """A zero payoff matrix at s = 1 has no defined update. Fail, do not NaN."""
    with pytest.raises(ValueError, match="mean fitness"):
        replicator_step(np.zeros((2, 2)), np.array([0.5, 0.5]), selection_intensity=1.0)


# --- extinction --------------------------------------------------------------


def test_threshold_of_zero_culls_nothing() -> None:
    shares = np.array([1e-30, 1.0 - 1e-30])
    culled, mask = apply_extinction(shares, 0.0)
    assert not mask.any()
    np.testing.assert_array_equal(culled, shares)


def test_extinction_renormalises_the_survivors() -> None:
    shares = np.array([1e-9, 0.4, 0.6 - 1e-9])
    culled, mask = apply_extinction(shares, 1e-6)
    assert mask.tolist() == [True, False, False]
    assert culled[0] == 0.0
    assert culled.sum() == pytest.approx(1.0)
    # The survivors keep their relative proportions.
    assert culled[1] / culled[2] == pytest.approx(shares[1] / shares[2])


def test_a_threshold_that_would_cull_everything_is_refused() -> None:
    with pytest.raises(ValueError, match="entire population"):
        apply_extinction(np.array([0.5, 0.5]), 0.9)


def test_extinction_is_recorded_at_the_generation_it_happens(phase_a) -> None:
    result = run_replicator(
        phase_a.payoff_matrix, phase_a.names, PROVISIONAL_EVOLUTION_CONFIG
    )
    for name, generation in result.extinct_at.items():
        index = result.names.index(name)
        if generation is None:
            assert result.final_shares[index] > 0.0
            continue
        assert result.trajectory[generation - 1, index] > 0.0
        assert (result.trajectory[generation:, index] == 0.0).all()


# --- validation --------------------------------------------------------------


@pytest.mark.parametrize(
    "kwargs",
    [
        dict(generations=0, selection_intensity=0.5, extinction_threshold=1e-6),
        dict(generations=10, selection_intensity=-0.1, extinction_threshold=1e-6),
        dict(generations=10, selection_intensity=1.5, extinction_threshold=1e-6),
        dict(generations=10, selection_intensity=0.5, extinction_threshold=1.0),
        dict(generations=10, selection_intensity=0.5, extinction_threshold=-1e-6),
    ],
)
def test_invalid_evolution_config_is_rejected(kwargs: dict) -> None:
    with pytest.raises(ValueError):
        EvolutionConfig(**kwargs)


def test_mismatched_matrix_and_names_are_refused() -> None:
    with pytest.raises(ValueError, match="expected"):
        run_replicator(FLAT, ("only one name",), PROVISIONAL_EVOLUTION_CONFIG)


def test_initial_shares_are_normalised_not_rejected(phase_a) -> None:
    """Unnormalised starting weights are a convenience, not an error."""
    n = len(phase_a.names)
    result = run_replicator(
        phase_a.payoff_matrix,
        phase_a.names,
        PROVISIONAL_EVOLUTION_CONFIG,
        initial_shares=np.full(n, 7.0),
    )
    np.testing.assert_allclose(result.initial_shares, equal_shares(n))


def test_negative_initial_shares_are_refused(phase_a) -> None:
    shares = equal_shares(len(phase_a.names))
    shares[0] = -0.1
    with pytest.raises(ValueError, match="non-negative"):
        run_replicator(
            phase_a.payoff_matrix,
            phase_a.names,
            PROVISIONAL_EVOLUTION_CONFIG,
            initial_shares=shares,
        )


# --- the reported result -----------------------------------------------------


def test_the_headline_run_ends_in_a_neutral_cooperative_mixture(phase_a) -> None:
    """The Phase B result, pinned.

    Every defecting strategy is eliminated, the survivors are exactly the
    strategies that cooperate with each other, and their fitness spread is zero
    — meaning selection has nothing left to act on and the final proportions
    are frozen rather than chosen. This is the ESS point in
    PROJECT_STATE.md, made concrete: no single strategy wins, and the
    mixture that remains is neutral.
    """
    result = run_replicator(
        phase_a.payoff_matrix, phase_a.names, PROVISIONAL_EVOLUTION_CONFIG
    )

    assert "Always Defect" not in result.survivors
    assert "Random" not in result.survivors
    assert set(result.survivors) == {
        "Always Cooperate",
        "Tit-for-Tat",
        "Grim Trigger",
        "Pavlov",
        "Tit-for-Two-Tats",
    }
    assert result.surviving_fitness_spread == pytest.approx(0.0, abs=1e-12)
    assert result.settled_generation is not None


def test_without_random_grim_and_tit_for_tat_are_indistinguishable() -> None:
    """D-010 carried into Phase B.

    Grim only out-scores Tit-for-Tat against a coin flipper. Remove the coin
    flipper and the two are identical in the tournament, so evolution has no
    way to separate them either: they must end on exactly equal shares.
    """
    roster = tuple(n for n in DEFAULT_CONFIG.roster if n != "Random")
    reduced = run_round_robin(SMALL_TOURNAMENT.with_(roster=roster))
    result = run_replicator(
        reduced.payoff_matrix, reduced.names, PROVISIONAL_EVOLUTION_CONFIG
    )
    assert result.share_of("Grim Trigger") == pytest.approx(
        result.share_of("Tit-for-Tat"), abs=1e-12
    )


def test_the_outcome_barely_depends_on_selection_intensity(phase_a) -> None:
    """The claim run (b) prints, asserted rather than eyeballed."""
    runs = {
        f"s={s}": run_replicator(
            phase_a.payoff_matrix,
            phase_a.names,
            PROVISIONAL_EVOLUTION_CONFIG.with_(selection_intensity=s),
        )
        for s in (0.1, 0.5, 1.0)
    }
    survivor_sets = {result.survivors for result in runs.values()}
    assert len(survivor_sets) == 1, "s must not change who survives"
    assert largest_disagreement(runs) < 0.005

    # It does change the pace, and that is the whole point of the parameter.
    settled = [result.settled_generation for result in runs.values()]
    assert max(settled) > 2 * min(settled)


def test_the_outcome_barely_depends_on_the_extinction_threshold(phase_a) -> None:
    """The claim run (d) prints, asserted rather than eyeballed."""
    runs = {
        f"t={t}": run_replicator(
            phase_a.payoff_matrix,
            phase_a.names,
            PROVISIONAL_EVOLUTION_CONFIG.with_(extinction_threshold=t),
        )
        for t in (1e-3, 1e-4, 1e-6, 1e-9)
    }
    survivor_sets = {result.survivors for result in runs.values()}
    assert len(survivor_sets) == 1
    assert largest_disagreement(runs) < 0.001


# --- open item 4: initial conditions ------------------------------------------

# Smaller than the reported sweep so the suite stays fast. The reported figures
# come from `python initial_conditions.py`; these assertions pin the shape of
# the finding, not its fourth decimal.
TEST_SAMPLES = 120
TEST_SWEEP_GENERATIONS = 1000


@pytest.fixture(scope="module")
def sweep(phase_a):
    from evolution import run_from_random_starts, simplex_rng

    return run_from_random_starts(
        phase_a.payoff_matrix,
        phase_a.names,
        PROVISIONAL_EVOLUTION_CONFIG.with_(generations=TEST_SWEEP_GENERATIONS),
        TEST_SAMPLES,
        simplex_rng(DEFAULT_CONFIG.root_seed),
    )


def test_sampled_starting_mixes_are_valid_populations(phase_a) -> None:
    from evolution import sample_simplex, simplex_rng

    n = len(phase_a.names)
    starts = sample_simplex(n, 500, simplex_rng(DEFAULT_CONFIG.root_seed))
    assert starts.shape == (500, n)
    assert (starts > 0.0).all()
    np.testing.assert_allclose(starts.sum(axis=1), 1.0, rtol=0, atol=1e-12)


def test_the_simplex_sample_is_reproducible(phase_a) -> None:
    from evolution import sample_simplex, simplex_rng

    n = len(phase_a.names)
    first = sample_simplex(n, 50, simplex_rng(DEFAULT_CONFIG.root_seed))
    second = sample_simplex(n, 50, simplex_rng(DEFAULT_CONFIG.root_seed))
    np.testing.assert_array_equal(first, second)


def test_defectors_never_survive_a_uniform_random_start(sweep) -> None:
    """The survivor-set half of the open item 4 answer.

    Always Defect and Random are eliminated from every uniformly drawn start.
    This is the claim the report rests on, so it is asserted rather than
    eyeballed off a printout.
    """
    for result in sweep:
        assert "Always Defect" not in result.survivors
        assert "Random" not in result.survivors


def test_every_uniform_run_converges_and_ends_neutral(sweep) -> None:
    for result in sweep:
        assert result.settled_generation is not None, "raise G"
        assert result.surviving_fitness_spread == pytest.approx(0.0, abs=1e-12)


def test_the_final_proportions_depend_heavily_on_the_start(sweep, phase_a) -> None:
    """The other half of the answer, and the one that constrains the report.

    The survivor set is a property of the model; the proportions are not. If
    this ever stops being true the report's framing needs revisiting, so it is
    asserted in the direction of *large* variation on purpose.
    """
    finals = np.array([result.final_shares for result in sweep])
    grim = finals[:, phase_a.index_of("Grim Trigger")]
    assert grim.max() - grim.min() > 0.5, (
        "expected the final composition to range widely across starting mixes"
    )


def test_the_defection_basin_exists_but_needs_an_unretaliating_minority() -> None:
    """Always Defect is a strict Nash equilibrium, so a basin must exist.

    Uniform sampling never finds it, which is a statement about its size, not
    its existence. Here it is directly: with the minority entirely Always
    Cooperate the defectors sweep, and adding a small share of Tit-for-Tat to
    that same minority flips the outcome.

    Run against the full DEFAULT_CONFIG matrix rather than the reduced one the
    other tests share, because the basin's size depends on the round count.
    At 50 rounds Always Defect's single round of exploitation is amortised over
    four times fewer rounds, so it scores better and its basin is wider - which
    is worth knowing, and is Phase C's territory once w controls the effective
    game length.
    """
    full = run_round_robin(DEFAULT_CONFIG)
    names = full.names
    matrix = full.payoff_matrix
    config = PROVISIONAL_EVOLUTION_CONFIG.with_(generations=TEST_SWEEP_GENERATIONS)
    index_c = names.index("Always Cooperate")
    index_d = names.index("Always Defect")
    index_t = names.index("Tit-for-Tat")

    exploitable = np.zeros(len(names))
    exploitable[index_d] = 0.9
    exploitable[index_c] = 0.1
    swept = run_replicator(matrix, names, config, initial_shares=exploitable)
    assert swept.survivors == ("Always Defect",)

    # The probe in initial_conditions.py puts the edge at 2.8% of the minority
    # for this matrix; 10% is comfortably clear of it without being so far
    # clear that the test stops testing anything.
    defended = np.zeros(len(names))
    defended[index_d] = 0.9
    defended[index_c] = 0.09
    defended[index_t] = 0.01
    rescued = run_replicator(matrix, names, config, initial_shares=defended)
    assert "Always Defect" not in rescued.survivors
