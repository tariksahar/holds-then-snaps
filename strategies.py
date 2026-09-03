"""Hand-coded strategies for the Iterated Prisoner's Dilemma.

A strategy is a function of the match history so far::

    strategy(my_history, their_history, rng, state) -> Move

`my_history` and `their_history` are equal-length sequences of the moves
already played, oldest first, written from the deciding player's point of
view. Both are passed to every strategy so that outcome-based strategies
(Pavlov) and opponent-based strategies (Tit-for-Tat) share one signature.

`rng` is an explicit generator supplied by the caller; deterministic
strategies ignore it. No strategy touches global random state.

`state` is an optional per-match scratch dict, and it is an optimisation
rather than hidden memory. Everything in it is derived from the two histories
and nothing else, so a strategy called with `state=None` recomputes from
scratch and returns the same move - just in O(n) instead of O(1). The
tournament passes a persistent dict so that Contrite Tit-for-Tat, Gradual and
Soft Majority do not turn every match into an O(n^2) loop. Correctness never
depends on it; only speed does.

The pool is chosen by mechanism rather than by variety - see D-027. Each entry
represents a distinct way of deciding, so that a result can be attributed to a
behaviour rather than to a name.
"""

from __future__ import annotations

from enum import Enum
from typing import Callable, Sequence

import numpy as np


class Move(Enum):
    """The two available moves."""

    COOPERATE = "C"
    DEFECT = "D"

    def __str__(self) -> str:
        return self.value


History = Sequence[Move]
Strategy = Callable[[History, History, np.random.Generator, dict | None], Move]

C = Move.COOPERATE
D = Move.DEFECT


def flip(move: Move) -> Move:
    """The other move. Used by Pavlov, and by the Phase C execution error."""
    return Move.DEFECT if move is Move.COOPERATE else Move.COOPERATE


# --- Unconditional -----------------------------------------------------------


def always_cooperate(
    my_history: History,
    their_history: History,
    rng: np.random.Generator,
    state: dict | None = None,
) -> Move:
    """Cooperate unconditionally."""
    return C


def always_defect(
    my_history: History,
    their_history: History,
    rng: np.random.Generator,
    state: dict | None = None,
) -> Move:
    """Defect unconditionally."""
    return D


# --- Reciprocal, varying tolerance -------------------------------------------


def tit_for_tat(
    my_history: History,
    their_history: History,
    rng: np.random.Generator,
    state: dict | None = None,
) -> Move:
    """Cooperate first, then copy the opponent's previous move."""
    if not their_history:
        return C
    return their_history[-1]


def tit_for_two_tats(
    my_history: History,
    their_history: History,
    rng: np.random.Generator,
    state: dict | None = None,
) -> Move:
    """Defect only after the opponent has defected twice in a row.

    One unanswered defection is absorbed, which is what makes this strategy
    interesting once an error rate is introduced.
    """
    if len(their_history) < 2:
        return C
    if their_history[-1] is D and their_history[-2] is D:
        return D
    return C


def two_tits_for_tat(
    my_history: History,
    their_history: History,
    rng: np.random.Generator,
    state: dict | None = None,
) -> Move:
    """Answer one defection with two. The impatient end of the reciprocal range.

    The mirror image of Tit-for-Two-Tats, and on the pool for that reason: it
    marks the over-reacting end of the same axis, where Tit-for-Two-Tats marks
    the over-forgiving one.
    """
    if D in their_history[-2:]:
        return D
    return C


def grim_trigger(
    my_history: History,
    their_history: History,
    rng: np.random.Generator,
    state: dict | None = None,
) -> Move:
    """Cooperate until the opponent defects once, then defect forever."""
    if D in their_history:
        return D
    return C


# --- Error-aware --------------------------------------------------------------

# Nowak and Sigmund's optimum for Generous Tit-for-Tat is
# min(1 - (T-R)/(R-S), (R-P)/(T-P)), which for T=5 R=3 P=1 S=0 is min(1/3, 1/2)
# = 1/3. Used as the pool's default so the entry is a named quantity rather
# than a guess; `generous_tit_for_tat(p)` remains available for sweeping p,
# which is what D-011 deferred to Phase C.
DEFAULT_GENEROSITY = 1.0 / 3.0


def generous_tit_for_tat(forgiveness_probability: float) -> Strategy:
    """Tit-for-Tat that forgives a defection with probability p.

    Answers noise statistically: it cannot tell a mistake from a deliberate
    defection, so it forgives a fixed fraction of both and relies on the
    arithmetic working out.
    """
    if not 0.0 <= forgiveness_probability <= 1.0:
        raise ValueError(
            f"forgiveness_probability must lie in [0, 1], got "
            f"{forgiveness_probability}"
        )

    def play(
        my_history: History,
        their_history: History,
        rng: np.random.Generator,
        state: dict | None = None,
    ) -> Move:
        if not their_history:
            return C
        if their_history[-1] is D and rng.random() < forgiveness_probability:
            return C
        return their_history[-1]

    play.__name__ = f"generous_tit_for_tat_p{forgiveness_probability:.4f}"
    play.__doc__ = (
        f"Tit-for-Tat, forgiving a defection with probability "
        f"{forgiveness_probability:.4f}."
    )
    return play


def _standings(
    my_history: History, their_history: History, state: dict | None
) -> tuple[bool, bool]:
    """Both players' standing after the rounds played so far.

    Standing is Boyd's bookkeeping for whose fault a defection was. A player is
    in good standing if it cooperated last round, or if it defected against an
    opponent who was already in bad standing - that is, if its defection was a
    *justified punishment* rather than a fresh offence.

    Computed from the played moves alone, so it needs no access to what anyone
    intended. That is the point: an execution error is indistinguishable from a
    deliberate defection to everyone including its author, and standing still
    assigns it correctly, because it is defined on what happened.
    """
    scratch = {} if state is None else state
    processed = scratch.get("standing_processed", 0)
    mine_good = scratch.get("my_standing", True)
    theirs_good = scratch.get("their_standing", True)

    for index in range(processed, len(my_history)):
        mine, theirs = my_history[index], their_history[index]
        # Both standings update from the standings that held *before* this
        # round, so a simultaneous exchange is judged simultaneously.
        was_mine_good, was_theirs_good = mine_good, theirs_good
        mine_good = True if mine is C else not was_theirs_good
        theirs_good = True if theirs is C else not was_mine_good

    scratch["standing_processed"] = len(my_history)
    scratch["my_standing"] = mine_good
    scratch["their_standing"] = theirs_good
    return mine_good, theirs_good


def contrite_tit_for_tat(
    my_history: History,
    their_history: History,
    rng: np.random.Generator,
    state: dict | None = None,
) -> Move:
    """Tit-for-Tat that keeps track of whose fault a defection was.

    Defects only against an opponent in bad standing. The consequence that
    matters under an execution error: when this strategy's own move is flipped
    and the opponent retaliates, it is *itself* in bad standing and the
    opponent's defection is a justified punishment - so it cooperates through
    the punishment instead of answering it. One error costs a single exchange
    and cooperation resumes, where plain Tit-for-Tat would start an echo that
    neither player can stop.

    This is the theoretically correct response to execution error, and the
    reason D-027 put it on the pool.
    """
    if not their_history:
        return C
    _, theirs_good = _standings(my_history, their_history, state)
    return C if theirs_good else D


def pavlov(
    my_history: History,
    their_history: History,
    rng: np.random.Generator,
    state: dict | None = None,
) -> Move:
    """Win-Stay, Lose-Shift.

    Repeat the previous move after a good outcome, switch after a bad one.
    Under the required ordering ``T > R > P > S`` the two good outcomes are
    exactly those where the opponent cooperated, so the rule can be expressed
    without reference to the payoff values themselves.
    """
    if not my_history:
        return C
    if their_history[-1] is C:
        return my_history[-1]
    return flip(my_history[-1])


# --- Opening variant ----------------------------------------------------------


def suspicious_tit_for_tat(
    my_history: History,
    their_history: History,
    rng: np.random.Generator,
    state: dict | None = None,
) -> Move:
    """Defect on the first move, then play Tit-for-Tat.

    A one-move difference from Tit-for-Tat, worth 1/N and therefore almost
    nothing at N = 200. It is on the pool for the w axis rather than the ε
    axis: as w falls and matches shorten, the opening move becomes a growing
    fraction of the whole game.
    """
    if not their_history:
        return D
    return their_history[-1]


# --- Probing / exploitative ---------------------------------------------------


def prober(
    my_history: History,
    their_history: History,
    rng: np.random.Generator,
    state: dict | None = None,
) -> Move:
    """Open D, C, C; then exploit if the opponent let it pass, else Tit-for-Tat.

    Tests whether retaliation is present and adapts. Distinct from every other
    pool entry in that its behaviour is *contingent on a measurement it makes*
    rather than on a fixed rule.
    """
    opening = (D, C, C)
    if len(their_history) < len(opening):
        return opening[len(their_history)]
    # Rounds 2 and 3 are the probe: the opponent saw a defection and had two
    # chances to answer it.
    if their_history[1] is C and their_history[2] is C:
        return D
    return their_history[-1]


def gradual(
    my_history: History,
    their_history: History,
    rng: np.random.Generator,
    state: dict | None = None,
) -> Move:
    """Punish the nth defection with n defections, then two calming cooperations.

    Escalating retaliation with an explicit de-escalation phase. The two
    cooperations at the end of each punishment are what stop it locking into
    mutual defection the way Grim Trigger does.
    """
    scratch = {} if state is None else state
    processed = scratch.get("gradual_processed", 0)
    defections = scratch.get("gradual_defections", 0)
    punishing = scratch.get("gradual_punishing", 0)
    calming = scratch.get("gradual_calming", 0)

    # Replay every round not yet accounted for. The schedule is advanced by
    # *completed* rounds only, never by the act of deciding the current move -
    # otherwise asking twice what to play this round would consume two slots,
    # and the cached state would stop being a pure function of the history.
    for index in range(processed, len(their_history)):
        if punishing > 0:
            punishing -= 1
        elif calming > 0:
            calming -= 1
        if their_history[index] is D:
            defections += 1
            if punishing == 0 and calming == 0:
                # A fresh offence, not one already being answered. The nth
                # defection buys n rounds of punishment, then two of calm.
                punishing = defections
                calming = 2

    scratch["gradual_processed"] = len(their_history)
    scratch["gradual_defections"] = defections
    scratch["gradual_punishing"] = punishing
    scratch["gradual_calming"] = calming

    return D if punishing > 0 else C


# --- Aggregate history --------------------------------------------------------


def soft_majority(
    my_history: History,
    their_history: History,
    rng: np.random.Generator,
    state: dict | None = None,
) -> Move:
    """Cooperate while the opponent has cooperated at least as often as not.

    Judges the whole record rather than the last move or two, so a single
    mistake is diluted by everything that came before it. The only pool entry
    whose memory is unbounded in this way, and the one that should be least
    disturbed by a low error rate.
    """
    scratch = {} if state is None else state
    processed = scratch.get("majority_processed", 0)
    cooperations = scratch.get("majority_cooperations", 0)
    defections = scratch.get("majority_defections", 0)

    for index in range(processed, len(their_history)):
        if their_history[index] is C:
            cooperations += 1
        else:
            defections += 1

    scratch["majority_processed"] = len(their_history)
    scratch["majority_cooperations"] = cooperations
    scratch["majority_defections"] = defections

    return C if cooperations >= defections else D


# --- Baselines ----------------------------------------------------------------

# Defines the "Random" pool entry. Named rather than a literal so that a sweep
# over cooperation probability needs no code change.
DEFAULT_RANDOM_COOPERATION_PROBABILITY = 0.5


def random_player(cooperation_probability: float) -> Strategy:
    """Ignore history; cooperate with a fixed probability."""
    if not 0.0 <= cooperation_probability <= 1.0:
        raise ValueError(
            f"cooperation_probability must lie in [0, 1], got "
            f"{cooperation_probability}"
        )

    def play(
        my_history: History,
        their_history: History,
        rng: np.random.Generator,
        state: dict | None = None,
    ) -> Move:
        return C if rng.random() < cooperation_probability else D

    play.__name__ = f"random_player_p{cooperation_probability}"
    play.__doc__ = (
        f"Cooperate with probability {cooperation_probability}, ignoring history."
    )
    return play


def alternator(
    my_history: History,
    their_history: History,
    rng: np.random.Generator,
    state: dict | None = None,
) -> Move:
    """Cooperate, defect, cooperate, defect - ignoring the opponent entirely.

    A control: perfectly predictable, perfectly unresponsive. Anything that
    cannot beat it is not using the history it is given.
    """
    return C if len(my_history) % 2 == 0 else D


# --- Registry -----------------------------------------------------------------

# The full pool (D-027), grouped by mechanism. The roster actually played is
# chosen in config.py; this dict is the set available to choose from.
STRATEGIES: dict[str, Strategy] = {
    # unconditional
    "Always Cooperate": always_cooperate,
    "Always Defect": always_defect,
    # reciprocal, varying tolerance
    "Tit-for-Tat": tit_for_tat,
    "Tit-for-Two-Tats": tit_for_two_tats,
    "Two-Tits-for-Tat": two_tits_for_tat,
    "Grim Trigger": grim_trigger,
    # error-aware
    "Generous TFT": generous_tit_for_tat(DEFAULT_GENEROSITY),
    "Contrite TFT": contrite_tit_for_tat,
    "Pavlov": pavlov,
    # opening variant
    "Suspicious TFT": suspicious_tit_for_tat,
    # probing / exploitative
    "Prober": prober,
    "Gradual": gradual,
    # aggregate history
    "Soft Majority": soft_majority,
    # baselines
    "Random": random_player(DEFAULT_RANDOM_COOPERATION_PROBABILITY),
    "Alternator": alternator,
}

# The seven that Phases A and B ran on, kept as the pre-expansion control.
CONTROL_ROSTER: tuple[str, ...] = (
    "Always Cooperate",
    "Always Defect",
    "Tit-for-Tat",
    "Grim Trigger",
    "Random",
    "Pavlov",
    "Tit-for-Two-Tats",
)

# Strategies whose behaviour depends on the generator.
STOCHASTIC = frozenset({"Random", "Generous TFT"})
