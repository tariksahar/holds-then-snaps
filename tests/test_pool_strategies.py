"""The eight strategies added for the D-027 pool.

One test per defining behaviour: the thing that makes the strategy a distinct
mechanism rather than a variant name. Contrite Tit-for-Tat gets the most
attention because it is the one the ε axis was missing, and because its
defining property - not counter-retaliating against a punishment its own error
provoked - is invisible unless you construct the error deliberately.
"""

from __future__ import annotations

import numpy as np
import pytest

from config import DEFAULT_CONFIG, DEFAULT_PAYOFFS
from strategies import (
    C,
    D,
    DEFAULT_GENEROSITY,
    STRATEGIES,
    Move,
    alternator,
    contrite_tit_for_tat,
    generous_tit_for_tat,
    gradual,
    prober,
    soft_majority,
    suspicious_tit_for_tat,
    two_tits_for_tat,
)
from tournament import play_match


def rng(seed: int = 0) -> np.random.Generator:
    return np.random.default_rng(seed)


def moves(strategy, mine: str, theirs: str, generator=None, state=None) -> Move:
    """Call a strategy on histories written as 'CDC' strings."""
    to_move = {"C": C, "D": D}
    return strategy(
        [to_move[c] for c in mine],
        [to_move[c] for c in theirs],
        generator if generator is not None else rng(),
        state,
    )


def play(strategy, opponent, rounds: int, seed: int = 0, **kwargs):
    return play_match(
        strategy, opponent, rounds, DEFAULT_PAYOFFS, rng(seed), **kwargs
    )


# --- Two-Tits-for-Tat ---------------------------------------------------------


def test_two_tits_for_tat_answers_one_defection_with_two() -> None:
    assert moves(two_tits_for_tat, "", "") is C
    assert moves(two_tits_for_tat, "C", "D") is D
    assert moves(two_tits_for_tat, "CD", "DC") is D  # still punishing
    assert moves(two_tits_for_tat, "CDD", "DCC") is C  # two answered, done


# --- Generous Tit-for-Tat -----------------------------------------------------


def test_generous_tft_never_forgives_at_p_zero_and_always_at_p_one() -> None:
    assert moves(generous_tit_for_tat(0.0), "C", "D") is D
    assert moves(generous_tit_for_tat(1.0), "C", "D") is C
    # Generosity applies only after a defection; cooperation is still mirrored.
    assert moves(generous_tit_for_tat(1.0), "C", "C") is C


def test_generous_tft_forgives_at_about_the_stated_rate() -> None:
    strategy = generous_tit_for_tat(DEFAULT_GENEROSITY)
    generator = rng(11)
    forgiven = sum(
        1 for _ in range(4000) if moves(strategy, "C", "D", generator) is C
    )
    assert forgiven / 4000 == pytest.approx(DEFAULT_GENEROSITY, abs=0.03)


def test_generous_tft_default_is_the_nowak_sigmund_optimum() -> None:
    """min(1 - (T-R)/(R-S), (R-P)/(T-P)) for our payoff set."""
    p = DEFAULT_PAYOFFS
    expected = min(
        1 - (p.temptation - p.reward) / (p.reward - p.sucker),
        (p.reward - p.punishment) / (p.temptation - p.punishment),
    )
    assert DEFAULT_GENEROSITY == pytest.approx(expected)


# --- Contrite Tit-for-Tat -----------------------------------------------------


def test_contrite_tft_is_tit_for_tat_when_nobody_errs() -> None:
    """With no error, contrition costs nothing and changes nothing."""
    for opponent in ("Always Cooperate", "Always Defect", "Tit-for-Tat", "Pavlov"):
        contrite = play(contrite_tit_for_tat, STRATEGIES[opponent], 50)
        plain = play(STRATEGIES["Tit-for-Tat"], STRATEGIES[opponent], 50)
        assert contrite.moves_a == plain.moves_a, opponent


def test_contrite_tft_does_not_counter_retaliate_for_its_own_mistake() -> None:
    """The defining behaviour, constructed by hand.

    History: this strategy defected once (an execution error - it looks
    identical to a deliberate defection in the record), and the opponent has
    just answered it. The opponent's defection is a justified punishment, so
    the correct move is to cooperate through it, not to answer back.
    """
    # Round 1 we (mistakenly) defected while they cooperated.
    # Round 2 they retaliate, we accept it.
    assert moves(contrite_tit_for_tat, "D", "C") is C, (
        "after its own unprovoked defection it must make amends, not persist"
    )
    assert moves(contrite_tit_for_tat, "DC", "CD") is C, (
        "the opponent's answer was deserved; answering it back is the echo "
        "this strategy exists to avoid"
    )
    # Amends made, both in good standing, back to cooperation.
    assert moves(contrite_tit_for_tat, "DCC", "CDC") is C


def test_contrite_tft_still_punishes_an_unprovoked_defection() -> None:
    """Contrition is not pacifism."""
    assert moves(contrite_tit_for_tat, "C", "D") is D
    assert moves(contrite_tit_for_tat, "", "") is C


def test_contrite_tft_recovers_from_error_where_tit_for_tat_echoes() -> None:
    """The whole point, measured rather than asserted.

    Two Tit-for-Tats that make a mistake fall into an alternating echo neither
    can stop. Two Contrite Tit-for-Tats settle the incident and resume. At the
    same error rate the contrite pair must score materially better against
    itself.
    """
    error_rate = 0.02
    scores = {}
    for name, strategy in (
        ("TFT", STRATEGIES["Tit-for-Tat"]),
        ("CTFT", contrite_tit_for_tat),
    ):
        total = rounds = 0
        for seed in range(40):
            result = play(strategy, strategy, 200, seed, error_rate=error_rate)
            total += result.total_a
            rounds += result.rounds
        scores[name] = total / rounds

    assert scores["CTFT"] > scores["TFT"] + 0.2, scores
    # And it should stay close to full mutual cooperation.
    assert scores["CTFT"] > 0.9 * DEFAULT_PAYOFFS.reward, scores


def test_contrite_tft_state_is_only_an_optimisation() -> None:
    """Called without the scratch dict it must return the same moves."""
    generator = rng(3)
    history_mine, history_theirs = [], []
    state: dict = {}
    for _ in range(60):
        with_state = contrite_tit_for_tat(
            history_mine, history_theirs, generator, state
        )
        without = contrite_tit_for_tat(history_mine, history_theirs, generator, None)
        assert with_state is without
        history_mine.append(with_state)
        history_theirs.append(D if len(history_theirs) % 3 == 0 else C)


# --- Suspicious Tit-for-Tat ---------------------------------------------------


def test_suspicious_tft_opens_with_a_defection_then_mirrors() -> None:
    assert moves(suspicious_tit_for_tat, "", "") is D
    assert moves(suspicious_tit_for_tat, "D", "C") is C
    assert moves(suspicious_tit_for_tat, "DC", "CD") is D


def test_suspicious_tft_differs_from_tit_for_tat_only_at_the_opening() -> None:
    """Worth 1/N against a forgiving opponent, which is why it is on the pool
    for the w axis rather than the ε axis."""
    against = STRATEGIES["Always Cooperate"]
    suspicious = play(suspicious_tit_for_tat, against, 100)
    plain = play(STRATEGIES["Tit-for-Tat"], against, 100)
    assert suspicious.moves_a[1:] == plain.moves_a[1:]
    assert suspicious.moves_a[0] is not plain.moves_a[0]


# --- Prober -------------------------------------------------------------------


def test_prober_opens_with_the_probe() -> None:
    assert moves(prober, "", "") is D
    assert moves(prober, "D", "C") is C
    assert moves(prober, "DC", "CC") is C


def test_prober_exploits_an_opponent_that_let_the_probe_pass() -> None:
    result = play(prober, STRATEGIES["Always Cooperate"], 30)
    assert all(move is D for move in result.moves_a[3:])


def test_prober_reverts_to_tit_for_tat_against_a_retaliator() -> None:
    result = play(prober, STRATEGIES["Tit-for-Tat"], 30)
    # TFT answers the probe on round 2, so Prober backs off and mirrors.
    assert result.moves_a[3:] == result.moves_b[2:-1]


# --- Gradual ------------------------------------------------------------------


def test_gradual_escalates_then_calms() -> None:
    """nth defection buys n rounds of punishment and two of calm."""
    result = play(gradual, STRATEGIES["Always Defect"], 12)
    # Round 1 cooperate; then punish once, calm twice; then punish twice, etc.
    assert result.moves_a[0] is C
    assert result.moves_a[1] is D
    assert result.moves_a[2] is C and result.moves_a[3] is C
    assert result.moves_a[4] is D and result.moves_a[5] is D


def test_gradual_never_punishes_a_pure_cooperator() -> None:
    result = play(gradual, STRATEGIES["Always Cooperate"], 40)
    assert all(move is C for move in result.moves_a)


def test_gradual_state_is_only_an_optimisation() -> None:
    generator = rng(5)
    mine, theirs = [], []
    state: dict = {}
    for step in range(50):
        with_state = gradual(mine, theirs, generator, state)
        without = gradual(mine, theirs, generator, None)
        assert with_state is without, f"diverged at step {step}"
        mine.append(with_state)
        theirs.append(D if step % 7 == 0 else C)


# --- Soft Majority ------------------------------------------------------------


def test_soft_majority_tracks_the_whole_record() -> None:
    assert moves(soft_majority, "", "") is C
    assert moves(soft_majority, "CC", "CD") is C  # 1 vs 1, ties go to cooperate
    assert moves(soft_majority, "CCC", "CDD") is D  # 1 vs 2
    assert moves(soft_majority, "C" * 10, "C" * 8 + "DD") is C  # 8 vs 2


def test_soft_majority_dilutes_an_isolated_mistake() -> None:
    """A single defection in a long cooperative record changes nothing."""
    assert moves(soft_majority, "C" * 50, "C" * 49 + "D") is C


def test_soft_majority_state_is_only_an_optimisation() -> None:
    generator = rng(9)
    mine, theirs = [], []
    state: dict = {}
    for step in range(60):
        assert soft_majority(mine, theirs, generator, state) is soft_majority(
            mine, theirs, generator, None
        )
        mine.append(C)
        theirs.append(D if step % 4 else C)


# --- Alternator ---------------------------------------------------------------


def test_alternator_ignores_the_opponent_entirely() -> None:
    for opponent in ("Always Cooperate", "Always Defect", "Tit-for-Tat"):
        result = play(alternator, STRATEGIES[opponent], 10)
        assert result.moves_a == (C, D) * 5, opponent


# --- The pool as a whole ------------------------------------------------------


def test_the_pool_has_the_fifteen_strategies_of_d027() -> None:
    assert len(STRATEGIES) == 15
    for required in (
        "Two-Tits-for-Tat",
        "Generous TFT",
        "Contrite TFT",
        "Suspicious TFT",
        "Prober",
        "Gradual",
        "Soft Majority",
        "Alternator",
    ):
        assert required in STRATEGIES


def test_every_pool_strategy_returns_a_move_from_any_history() -> None:
    """No strategy may raise or return None on any reachable history."""
    generator = rng(1)
    for name, strategy in STRATEGIES.items():
        mine: list[Move] = []
        theirs: list[Move] = []
        state: dict = {}
        for step in range(40):
            move = strategy(mine, theirs, generator, state)
            assert isinstance(move, Move), f"{name} returned {move!r}"
            mine.append(move)
            theirs.append(D if step % 3 == 0 else C)


def test_no_two_pool_strategies_are_behaviourally_identical() -> None:
    """Fifteen names must be fifteen mechanisms - D-027's premise.

    Compared against a fixed panel of opponents, so two entries that differ
    only in name would show up here.
    """
    def defect_once(my_history, their_history, generator, scratch=None) -> Move:
        """Cooperates always, except for a single defection at round 4.

        On the panel because without it Grim Trigger and Two-Tits-for-Tat are
        indistinguishable: against an opponent that never stops defecting, an
        unforgiving strategy and a two-round-memory one behave identically.
        The difference between them is exactly what happens after a defection
        that is not repeated - which is also the situation an execution error
        creates, so this is the discriminating case for the ε axis too.
        """
        return D if len(my_history) == 3 else C

    panel = [STRATEGIES[n] for n in ("Always Cooperate", "Always Defect",
                                     "Tit-for-Tat", "Alternator")]
    panel.append(defect_once)
    signatures: dict[tuple, str] = {}
    for name, strategy in STRATEGIES.items():
        signature = tuple(
            play(strategy, opponent, 40, seed=2).moves_a for opponent in panel
        ) + tuple(
            # Noiseless play cannot separate Contrite Tit-for-Tat from plain
            # Tit-for-Tat, because contrition only shows when the strategy
            # itself errs. Distinctness has to be judged in the environment the
            # experiment actually runs in, which is the noisy one.
            play(strategy, opponent, 60, seed=4, error_rate=0.05).moves_a
            for opponent in panel
        )
        assert signature not in signatures, (
            f"{name} is behaviourally identical to {signatures[signature]}"
        )
        signatures[signature] = name
