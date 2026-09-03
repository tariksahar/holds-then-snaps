"""Phase C: the two new match-loop parameters.

The first thing asserted here, and the most important, is that the defaults
change nothing. Everything after that is about the new behaviour.
"""

from __future__ import annotations

import numpy as np
import pytest

from config import (
    DEFAULT_CONFIG,
    DEFAULT_PAYOFFS,
    HARD_ROUND_CAP,
    Config,
    cap_binds,
    max_rounds_for,
    trials_for,
)
from strategies import STRATEGIES, Move
from tournament import play_match, run_round_robin

ROUNDS = 200
TFT = STRATEGIES["Tit-for-Tat"]
ALL_C = STRATEGIES["Always Cooperate"]
ALL_D = STRATEGIES["Always Defect"]


def rng(seed: int = 0) -> np.random.Generator:
    return np.random.default_rng(seed)


# --- the defaults change nothing ---------------------------------------------


@pytest.mark.parametrize(
    "name_a,name_b",
    [
        ("Tit-for-Tat", "Always Defect"),
        ("Grim Trigger", "Random"),
        ("Pavlov", "Tit-for-Two-Tats"),
        ("Random", "Random"),
    ],
)
def test_explicit_defaults_are_the_implicit_defaults(name_a: str, name_b: str) -> None:
    """Passing the Phase C parameters at their defaults is a no-op.

    This is the guarantee that Phase A and B results are untouched: at
    epsilon = 0 and w = 1 the new code paths are skipped entirely rather than
    executed with neutral values, so not one draw is taken from the generator
    that was not taken before.
    """
    a, b = STRATEGIES[name_a], STRATEGIES[name_b]
    plain = play_match(a, b, ROUNDS, DEFAULT_PAYOFFS, rng())
    explicit = play_match(
        a,
        b,
        ROUNDS,
        DEFAULT_PAYOFFS,
        rng(),
        error_rate=0.0,
        continuation_probability=1.0,
    )
    assert plain.moves_a == explicit.moves_a
    assert plain.moves_b == explicit.moves_b
    assert plain.total_a == explicit.total_a
    assert plain.rounds == explicit.rounds == ROUNDS


def test_a_default_config_is_the_noiseless_fixed_horizon_game() -> None:
    assert DEFAULT_CONFIG.error_rate == 0.0
    assert DEFAULT_CONFIG.continuation_probability == 1.0
    assert DEFAULT_CONFIG.max_rounds == DEFAULT_CONFIG.rounds
    assert DEFAULT_CONFIG.expected_rounds == DEFAULT_CONFIG.rounds


# --- execution error ----------------------------------------------------------


def test_certain_error_flips_every_move() -> None:
    """At epsilon = 1 the players do the exact opposite of what they intend."""
    result = play_match(
        ALL_C, ALL_D, 20, DEFAULT_PAYOFFS, rng(), error_rate=1.0
    )
    assert all(move is Move.DEFECT for move in result.moves_a)
    assert all(move is Move.COOPERATE for move in result.moves_b)


def test_the_error_is_execution_not_perception() -> None:
    """Both players see the same match. That is the whole distinction.

    Tit-for-Tat copies what its opponent *played*. If the two players held
    different histories - a perception error - Tit-for-Tat's move at round n+1
    would not always equal the opponent's actual move at round n. Here it must.
    """
    result = play_match(
        TFT, STRATEGIES["Random"], 300, DEFAULT_PAYOFFS, rng(7), error_rate=0.1
    )
    intended_replies = result.moves_b[:-1]  # what B actually played
    actual_replies = result.moves_a[1:]  # what A played in response
    disagreements = sum(
        1 for want, got in zip(intended_replies, actual_replies) if want is not got
    )
    # The only disagreements are A's own execution errors, which occur at
    # roughly epsilon. Anything much above that means the histories diverged.
    assert disagreements / len(actual_replies) < 0.2


def test_error_degrades_mutual_cooperation() -> None:
    """The classic echo effect, and the mechanism D-022 said epsilon would attack.

    Two Tit-for-Tats score exactly R against each other with no noise. One
    mistaken defection starts an alternating echo that neither can stop, so the
    score falls towards the fully-randomised average (T+R+P+S)/4 = 2.25.
    """
    scores = []
    for epsilon in (0.0, 0.01, 0.05, 0.2):
        total = rounds = 0
        for seed in range(60):
            result = play_match(
                TFT, TFT, ROUNDS, DEFAULT_PAYOFFS, rng(seed), error_rate=epsilon
            )
            total += result.total_a
            rounds += result.rounds
        scores.append(total / rounds)

    assert scores[0] == pytest.approx(DEFAULT_PAYOFFS.reward)
    assert all(b < a for a, b in zip(scores, scores[1:])), (
        f"expected monotone degradation, got {scores}"
    )
    randomised = (
        DEFAULT_PAYOFFS.temptation
        + DEFAULT_PAYOFFS.reward
        + DEFAULT_PAYOFFS.punishment
        + DEFAULT_PAYOFFS.sucker
    ) / 4
    assert scores[-1] == pytest.approx(randomised, abs=0.05)


@pytest.mark.parametrize("error_rate", [-0.01, 1.01])
def test_invalid_error_rate_is_refused(error_rate: float) -> None:
    with pytest.raises(ValueError, match="error_rate"):
        play_match(TFT, TFT, 10, DEFAULT_PAYOFFS, rng(), error_rate=error_rate)


# --- continuation probability -------------------------------------------------


@pytest.mark.parametrize("w", [0.5, 0.8, 0.9, 0.99])
def test_match_length_is_geometric_with_the_right_mean(w: float) -> None:
    cap = max_rounds_for(w, ROUNDS)
    lengths = [
        play_match(
            TFT,
            TFT,
            ROUNDS,
            DEFAULT_PAYOFFS,
            rng(seed),
            continuation_probability=w,
            max_rounds=cap,
        ).rounds
        for seed in range(4000)
    ]
    expected = 1.0 / (1.0 - w)
    assert np.mean(lengths) == pytest.approx(expected, rel=0.06)
    assert min(lengths) >= 1
    assert max(lengths) <= cap


def test_the_cap_is_required_when_the_horizon_is_stochastic() -> None:
    """Refuse to run an unbounded loop rather than pick a cap silently."""
    with pytest.raises(ValueError, match="max_rounds is required"):
        play_match(
            TFT, TFT, ROUNDS, DEFAULT_PAYOFFS, rng(), continuation_probability=0.9
        )


def test_the_cap_truncates_only_the_intended_tail() -> None:
    """The cap is sized from w, not from N.

    The point of `max_rounds_for` is that the truncated probability mass is the
    same negligible fraction at every w. Using the fixed round count instead
    would cut 13% of the distribution at w = 0.99, which is what this asserts
    against.
    """
    for w in (0.5, 0.9, 0.99):
        cap = max_rounds_for(w, ROUNDS)
        truncated = w**cap
        assert truncated <= 1e-4 * 1.001

    # The trap being avoided, stated as a number.
    assert 0.99**200 > 0.13


def test_hard_cap_is_reported_when_it_binds() -> None:
    assert not cap_binds(0.99, ROUNDS)
    assert cap_binds(0.9999, ROUNDS)
    assert max_rounds_for(0.9999, ROUNDS) == HARD_ROUND_CAP


@pytest.mark.parametrize("w", [0.0, -0.1, 1.5])
def test_invalid_continuation_probability_is_refused(w: float) -> None:
    with pytest.raises(ValueError, match="continuation_probability"):
        play_match(
            TFT, TFT, 10, DEFAULT_PAYOFFS, rng(), continuation_probability=w
        )


# --- the tournament under Phase C parameters ----------------------------------


def test_per_round_payoffs_are_pooled_not_averaged_per_match() -> None:
    """The Phase C analogue of the D-008 handoff risk.

    With variable-length matches, the mean of per-match averages is not the
    pooled per-round average, and only the pooled one is payoff per unit of
    time played. A one-round match must not count as heavily as a hundred-round
    one. Constructed here so the two answers differ visibly.
    """
    payoffs = DEFAULT_PAYOFFS
    results = [
        play_match(
            TFT,
            ALL_D,
            ROUNDS,
            payoffs,
            rng(seed),
            continuation_probability=0.7,
            max_rounds=max_rounds_for(0.7, ROUNDS),
        )
        for seed in range(400)
    ]
    pooled = sum(r.total_a for r in results) / sum(r.rounds for r in results)
    per_match = float(np.mean([r.mean_a for r in results]))

    # TFT vs AllD earns S once then P forever, so a short match scores worse per
    # round. Averaging per-match means over-weights those short matches.
    assert per_match < pooled
    assert pooled == pytest.approx(
        run_round_robin(
            DEFAULT_CONFIG.with_(
                roster=("Tit-for-Tat", "Always Defect"),
                continuation_probability=0.7,
                trials=400,
                root_seed=DEFAULT_CONFIG.root_seed,
            )
        ).payoff_matrix[0, 1],
        rel=0.15,
    )


def test_tournament_reports_the_measured_match_length() -> None:
    for w in (1.0, 0.9, 0.99):
        config = DEFAULT_CONFIG.with_(
            continuation_probability=w, trials=trials_for(w)
        )
        result = run_round_robin(config)
        expected = config.rounds if w >= 1.0 else 1.0 / (1.0 - w)
        assert result.mean_match_length == pytest.approx(expected, rel=0.08)


def test_short_matches_hand_the_game_to_defection() -> None:
    """The w axis of the map, at one point, asserted rather than eyeballed.

    At w = 0.5 a match lasts two rounds on average. A defector's single round of
    free exploitation is then half the game, and no amount of retaliation can
    recover it.
    """
    from evolution import run_replicator
    from config import PROVISIONAL_EVOLUTION_CONFIG, SWEEP_GENERATIONS

    config = DEFAULT_CONFIG.with_(continuation_probability=0.5, trials=trials_for(0.5))
    tournament = run_round_robin(config)
    result = run_replicator(
        tournament.payoff_matrix,
        tournament.names,
        PROVISIONAL_EVOLUTION_CONFIG.with_(generations=SWEEP_GENERATIONS),
    )
    assert result.survivors == ("Always Defect",)


# --- config validation --------------------------------------------------------


@pytest.mark.parametrize(
    "kwargs",
    [
        dict(error_rate=-0.1),
        dict(error_rate=1.1),
        dict(continuation_probability=0.0),
        dict(continuation_probability=1.1),
    ],
)
def test_invalid_phase_c_config_is_rejected(kwargs: dict) -> None:
    with pytest.raises(ValueError):
        DEFAULT_CONFIG.with_(**kwargs)


def test_trials_scale_so_each_w_buys_comparable_evidence() -> None:
    """Trials rise as matches get shorter, so every w sees comparable play.

    Without the scaling, a fixed trial count would give w = 0.5 a hundred times
    less play than w = 0.99. The evening-out is not exact: MAX_TRIALS caps the
    shortest-match cells, so they still see the least. That is tolerable
    because those cells are the unambiguous ones - at w = 0.5 every replicate
    ends in total defection - and the replicate spread quantifies what is left.
    """
    rounds_seen = {
        w: trials_for(w) * (1.0 / (1.0 - w)) for w in (0.5, 0.8, 0.9, 0.95, 0.98)
    }
    # Without scaling this ratio would be about 100.
    assert max(rounds_seen.values()) / min(rounds_seen.values()) < 8.0
    assert min(rounds_seen.values()) > 1000


# --- the behavioural cooperation measure --------------------------------------


def test_cooperation_matrix_records_what_was_played() -> None:
    """Unconditional strategies pin the two ends of the scale."""
    result = run_round_robin(DEFAULT_CONFIG.with_(trials=2))
    coop = result.cooperation_matrix
    all_c = result.index_of("Always Cooperate")
    all_d = result.index_of("Always Defect")

    assert np.allclose(coop[all_c], 1.0)
    assert np.allclose(coop[all_d], 0.0)
    assert coop.shape == result.payoff_matrix.shape
    assert (coop >= 0.0).all() and (coop <= 1.0).all()


def test_cooperation_matrix_counts_errors_as_what_they_became() -> None:
    """Behaviour, not intent.

    Always Cooperate intends to cooperate every round. At epsilon = 0.2 it
    succeeds four times in five, and the measured rate must say so - otherwise
    the measure is just reading the strategy's name back.
    """
    result = run_round_robin(
        DEFAULT_CONFIG.with_(
            roster=("Always Cooperate", "Always Defect"), trials=40, error_rate=0.2
        )
    )
    all_c = result.index_of("Always Cooperate")
    all_d = result.index_of("Always Defect")
    assert result.cooperation_matrix[all_c, all_d] == pytest.approx(0.8, abs=0.03)
    assert result.cooperation_matrix[all_d, all_c] == pytest.approx(0.2, abs=0.03)


def test_a_name_based_cooperation_count_would_mislead_under_noise() -> None:
    """The measurement bug this metric exists to avoid, pinned as a test.

    At a high error rate Grim Trigger is tripped almost immediately and spends
    the rest of every match defecting. A population of Grim Trigger is a
    population that defects - but a count of "share not held by Always Defect
    or Random" scores it as a total victory for cooperation. The two numbers
    must be allowed to disagree, and here they must actually disagree, or the
    behavioural measure is not earning its place.

    Asserted against the **control roster**, not the pool. D-024 was found on
    the original seven, and the failure needs a population with no way to
    absorb its own errors - which is exactly what D-030 later showed those
    seven to be. On the fifteen-strategy pool the same cell genuinely
    cooperates (rate 0.70), so running this there would test nothing.
    """
    from config import PROVISIONAL_EVOLUTION_CONFIG, PHASE_C_GENERATIONS
    from evolution import run_replicator
    from experiments import non_defector_share, population_cooperation_rate
    from strategies import CONTROL_ROSTER

    config = DEFAULT_CONFIG.with_(
        roster=CONTROL_ROSTER,
        error_rate=0.2,
        continuation_probability=0.99,
        trials=trials_for(0.99),
    )
    tournament = run_round_robin(config)
    evolution = run_replicator(
        tournament.payoff_matrix,
        tournament.names,
        PROVISIONAL_EVOLUTION_CONFIG.with_(
            generations=PHASE_C_GENERATIONS, extinction_threshold=0.0
        ),
    )

    by_name = non_defector_share(evolution)
    by_behaviour = population_cooperation_rate(
        tournament.cooperation_matrix, evolution.final_shares
    )
    assert by_name > 0.9, "the name-based count says cooperation won"
    assert by_behaviour < 0.5, "what was actually played says otherwise"
