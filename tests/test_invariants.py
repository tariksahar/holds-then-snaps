"""The five invariants listed in PROJECT_STATE.md.

These are not smoke tests. Each one pins down a property that, if it broke,
would break quietly and poison everything downstream — the Phase A to Phase
B handoff being the worst offender.

Invariants 4 and 5 concern the replicator dynamics. Invariant 5 is asserted
against `replicator_step`, the pure dynamics, rather than against a full run:
extinction culling can and does take share away from a strategy that is beating
the population mean, so asserting it end-to-end would be asserting something
false. That interaction gets its own test below rather than being papered over.
"""

from __future__ import annotations

import itertools

import numpy as np
import pytest

from config import (
    DEFAULT_CONFIG,
    DEFAULT_PAYOFFS,
    PROVISIONAL_EVOLUTION_CONFIG,
    SELECTION_INTENSITY_SWEEP,
)
from evolution import (
    apply_extinction,
    equal_shares,
    fitness,
    replicator_step,
    run_replicator,
)
from strategies import STRATEGIES, Move
from tournament import match_rng, play_match, run_round_robin

ROUNDS = 200

# Every strategy whose behaviour does not depend on the generator. Used for
# the swap invariant, where an exact equality is only meaningful if the two
# orderings cannot diverge through the RNG.
DETERMINISTIC = (
    "Always Cooperate",
    "Always Defect",
    "Tit-for-Tat",
    "Grim Trigger",
    "Pavlov",
    "Tit-for-Two-Tats",
)


@pytest.fixture
def rng() -> np.random.Generator:
    return np.random.default_rng(DEFAULT_CONFIG.root_seed)


# --- 1 -----------------------------------------------------------------------


@pytest.mark.parametrize("rounds", [1, 2, 17, ROUNDS])
def test_tft_against_itself_scores_n_times_r(rounds: int, rng) -> None:
    """TFT vs TFT over N rounds = N * R, for both players.

    Two Tit-for-Tats never defect, so the whole match is mutual cooperation.
    """
    tft = STRATEGIES["Tit-for-Tat"]
    result = play_match(tft, tft, rounds, DEFAULT_PAYOFFS, rng)

    expected = rounds * DEFAULT_PAYOFFS.reward
    assert result.total_a == pytest.approx(expected)
    assert result.total_b == pytest.approx(expected)
    assert all(move is Move.COOPERATE for move in result.moves_a)
    assert all(move is Move.COOPERATE for move in result.moves_b)


# --- 2 -----------------------------------------------------------------------


@pytest.mark.parametrize("rounds", [2, 17, ROUNDS])
def test_grim_against_all_defect(rounds: int, rng) -> None:
    """Grim vs AllD = S + (N-1) * P.

    Grim cooperates into a defection once, is triggered, and both defect for
    the rest of the match. The opponent's mirror score, T + (N-1) * P, is
    asserted at the same time: it is the same claim seen from the other side.
    """
    grim = STRATEGIES["Grim Trigger"]
    all_d = STRATEGIES["Always Defect"]
    payoffs = DEFAULT_PAYOFFS
    result = play_match(grim, all_d, rounds, payoffs, rng)

    assert result.total_a == pytest.approx(
        payoffs.sucker + (rounds - 1) * payoffs.punishment
    )
    assert result.total_b == pytest.approx(
        payoffs.temptation + (rounds - 1) * payoffs.punishment
    )


# --- 3 -----------------------------------------------------------------------


@pytest.mark.parametrize(
    "name_a,name_b", list(itertools.combinations_with_replacement(DETERMINISTIC, 2))
)
def test_pairwise_payoffs_are_consistent_under_swap(
    name_a: str, name_b: str, rng
) -> None:
    """Swapping who is player A and who is player B swaps the scores.

    The game is symmetric: nothing about a strategy's payoff should depend on
    which argument slot it was passed in. This is what makes a single match
    legitimately fill both M[i, j] and M[j, i].
    """
    a = STRATEGIES[name_a]
    b = STRATEGIES[name_b]

    forward = play_match(a, b, ROUNDS, DEFAULT_PAYOFFS, rng)
    backward = play_match(b, a, ROUNDS, DEFAULT_PAYOFFS, rng)

    assert forward.total_a == pytest.approx(backward.total_b)
    assert forward.total_b == pytest.approx(backward.total_a)
    assert forward.moves_a == backward.moves_b
    assert forward.moves_b == backward.moves_a


def test_matrix_diagonal_matches_direct_self_play() -> None:
    """The matrix diagonal really is self-play, not something else.

    Phase B reads M[i, i] as the payoff a strategy gets in a population made
    entirely of itself. Cheap to get subtly wrong, silent when it is.
    """
    config = DEFAULT_CONFIG.with_(roster=DETERMINISTIC, trials=1)
    result = run_round_robin(config)

    for i, name in enumerate(result.names):
        player = STRATEGIES[name]
        direct = play_match(
            player,
            player,
            config.rounds,
            config.payoffs,
            match_rng(config.root_seed, i, i, 0),
        )
        assert result.payoff_matrix[i, i] == pytest.approx(direct.mean_a)


# --- 4 -----------------------------------------------------------------------


@pytest.fixture(scope="module")
def phase_a():
    """One Phase A run, shared by the Phase B invariants."""
    return run_round_robin(DEFAULT_CONFIG.with_(rounds=50, trials=3))


# A spread of starting mixes: the centre of the simplex, three corners-ish
# states, and a set of random draws. Invariants have to hold everywhere in the
# simplex, not just at the one point the headline run starts from.
def _starting_mixes(n: int) -> list[np.ndarray]:
    rng = np.random.default_rng(DEFAULT_CONFIG.root_seed)
    mixes = [equal_shares(n)]

    lopsided = np.full(n, 0.01)
    lopsided[0] = 1.0
    mixes.append(lopsided / lopsided.sum())

    # A mix with a strategy genuinely absent, not merely rare: zero shares must
    # stay zero, since the replicator update multiplies by the current share.
    absent = equal_shares(n).copy()
    absent[1] = 0.0
    mixes.append(absent / absent.sum())

    mixes.extend(rng.dirichlet(np.ones(n)) for _ in range(8))
    return mixes


@pytest.mark.parametrize("selection_intensity", SELECTION_INTENSITY_SWEEP)
@pytest.mark.parametrize("extinction_threshold", [0.0, 1e-9, 1e-6, 1e-3])
def test_population_shares_sum_to_one_every_generation(
    phase_a, selection_intensity: float, extinction_threshold: float
) -> None:
    """Shares sum to 1 at every generation, and never go negative.

    The replicator update divides by the mean fitness, which normalises by
    construction — so a failure here means a bug in the update, not drift. The
    extinction cutoff renormalises after culling for the same reason, and it is
    swept here because it is the one operation that could break the sum.
    """
    config = PROVISIONAL_EVOLUTION_CONFIG.with_(
        generations=120,
        selection_intensity=selection_intensity,
        extinction_threshold=extinction_threshold,
    )
    for shares in _starting_mixes(len(phase_a.names)):
        result = run_replicator(
            phase_a.payoff_matrix, phase_a.names, config, initial_shares=shares
        )
        totals = result.trajectory.sum(axis=1)
        np.testing.assert_allclose(totals, 1.0, rtol=0, atol=1e-12)
        assert (result.trajectory >= 0.0).all()


def test_an_absent_strategy_never_reappears(phase_a) -> None:
    """A zero share stays zero: the replicator equation has no mutation term.

    Worth pinning down explicitly, because Phase C open exploration 3 proposes
    adding immigration precisely to remove this property. When that lands, this
    test should start failing and be rewritten, not deleted quietly.
    """
    shares = equal_shares(len(phase_a.names))
    shares[phase_a.index_of("Always Defect")] = 0.0
    shares /= shares.sum()

    result = run_replicator(
        phase_a.payoff_matrix,
        phase_a.names,
        PROVISIONAL_EVOLUTION_CONFIG,
        initial_shares=shares,
    )
    column = result.trajectory[:, phase_a.index_of("Always Defect")]
    assert (column == 0.0).all()


# --- 5 -----------------------------------------------------------------------


@pytest.mark.parametrize("selection_intensity", SELECTION_INTENSITY_SWEEP)
def test_above_average_fitness_strictly_gains_share(
    phase_a, selection_intensity: float
) -> None:
    """A strategy with f_i > f_bar and a non-zero share strictly gains share.

    Directly from x_i(t+1) = x_i(t) * f_i / f_bar: the multiplier exceeds 1
    exactly when the strategy beats the population mean. Asserted against the
    pure replicator step — see this module's docstring for why not against a
    full run.

    The converse is asserted at the same time. A test that only checks winners
    grow would pass on an implementation that grows everybody.
    """
    matrix = phase_a.payoff_matrix
    checked_gain = 0
    checked_loss = 0

    for shares in _starting_mixes(len(phase_a.names)):
        f = fitness(matrix, shares, selection_intensity)
        mean_fitness = float(shares @ f)
        nxt = replicator_step(matrix, shares, selection_intensity)

        for i in range(len(shares)):
            if shares[i] <= 0.0:
                continue
            if f[i] > mean_fitness:
                assert nxt[i] > shares[i], (
                    f"strategy {phase_a.names[i]} has fitness {f[i]} above the "
                    f"mean {mean_fitness} but its share fell"
                )
                checked_gain += 1
            elif f[i] < mean_fitness:
                assert nxt[i] < shares[i]
                checked_loss += 1
            else:
                assert nxt[i] == pytest.approx(shares[i])

    # Guard against the assertions above being vacuous.
    assert checked_gain > 0 and checked_loss > 0


def test_extinction_culling_can_override_invariant_5(phase_a) -> None:
    """The cutoff is a convention, and conventions have costs. This is the cost.

    A strategy can be beating the population mean and still be zeroed, if its
    share is below the threshold at the moment it is winning. The replicator
    dynamics never do this; the cutoff layered on top does. Documented as a
    test so the report can state the limitation rather than discover it.
    """
    names = ("winner", "loser")
    # The rare strategy scores 2 against everything; the common one scores 1.
    matrix = np.array([[2.0, 2.0], [1.0, 1.0]])
    threshold = 1e-3
    shares = np.array([threshold / 2, 1.0 - threshold / 2])

    stepped = replicator_step(matrix, shares, selection_intensity=1.0)
    assert stepped[0] > shares[0], "the pure dynamics must grow the winner"

    culled, mask = apply_extinction(stepped, threshold)
    assert mask[0], "the winner is below the cutoff and gets zeroed anyway"
    assert culled[0] == 0.0
    assert culled.sum() == pytest.approx(1.0)

    result = run_replicator(
        matrix,
        names,
        PROVISIONAL_EVOLUTION_CONFIG.with_(extinction_threshold=threshold),
        initial_shares=shares,
    )
    assert result.survivors == ("loser",)
