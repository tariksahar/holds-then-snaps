"""Configuration for the simulation.

Every quantity the experiment depends on is declared here. Nothing in
`strategies.py` or `tournament.py` contains a literal payoff, round count,
seed or roster entry — they take a `Config` and read it.

`DEFAULT_CONFIG` is a default, not a constant: Phase C varies the payoffs
and Phase B may vary the roster, so treat it as the starting point of a
sweep rather than a fixed setting.
"""

from __future__ import annotations

import math
from dataclasses import dataclass, replace

from strategies import CONTROL_ROSTER, STRATEGIES, Move


@dataclass(frozen=True)
class Payoffs:
    """A Prisoner's Dilemma payoff specification.

    Named after the standard letters: T(emptation) for defecting against a
    cooperator, R(eward) for mutual cooperation, P(unishment) for mutual
    defection, S(ucker) for cooperating against a defector.
    """

    temptation: float  # T
    reward: float  # R
    punishment: float  # P
    sucker: float  # S

    def __post_init__(self) -> None:
        if not (
            self.temptation > self.reward > self.punishment > self.sucker
        ):
            raise ValueError(
                "payoffs must satisfy T > R > P > S, got "
                f"T={self.temptation}, R={self.reward}, "
                f"P={self.punishment}, S={self.sucker}"
            )
        if not 2 * self.reward > self.temptation + self.sucker:
            raise ValueError(
                "payoffs must satisfy 2R > T + S (otherwise alternating "
                "exploitation beats mutual cooperation), got "
                f"2R={2 * self.reward}, T+S={self.temptation + self.sucker}"
            )
        if self.sucker < 0:
            # The replicator update x_i * f_i / f_bar is not meaningful on
            # negative fitness. Since S is the lowest payoff, S >= 0 keeps
            # every payoff non-negative. See decisions.md D-003.
            raise ValueError(f"payoffs must be non-negative, got S={self.sucker}")

    def payoff_for(self, mine: Move, theirs: Move) -> float:
        """Return *my* payoff for one round, given both moves."""
        if mine is Move.COOPERATE:
            return self.reward if theirs is Move.COOPERATE else self.sucker
        return self.temptation if theirs is Move.COOPERATE else self.punishment


@dataclass(frozen=True)
class Config:
    """Everything one tournament run needs."""

    payoffs: Payoffs
    roster: tuple[str, ...]
    rounds: int
    trials: int
    root_seed: int
    # Phase C. Defaults reproduce the noiseless fixed-horizon game exactly.
    error_rate: float = 0.0  # epsilon
    continuation_probability: float = 1.0  # w

    def __post_init__(self) -> None:
        unknown = [name for name in self.roster if name not in STRATEGIES]
        if unknown:
            raise ValueError(
                f"roster names not found in the strategy registry: {unknown}"
            )
        if len(set(self.roster)) != len(self.roster):
            raise ValueError(f"roster contains duplicates: {self.roster}")
        if self.rounds < 1:
            raise ValueError(f"rounds must be at least 1, got {self.rounds}")
        if self.trials < 1:
            raise ValueError(f"trials must be at least 1, got {self.trials}")
        if not 0.0 <= self.error_rate <= 1.0:
            raise ValueError(
                f"error_rate must lie in [0, 1], got {self.error_rate}"
            )
        if not 0.0 < self.continuation_probability <= 1.0:
            raise ValueError(
                "continuation_probability must lie in (0, 1], got "
                f"{self.continuation_probability}"
            )

    @property
    def max_rounds(self) -> int:
        """The cap on match length. See `max_rounds_for`."""
        return max_rounds_for(self.continuation_probability, self.rounds)

    @property
    def expected_rounds(self) -> float:
        """Mean match length, accounting for the cap."""
        w = self.continuation_probability
        if w >= 1.0:
            return float(self.rounds)
        # Mean of a geometric truncated at max_rounds.
        return (1.0 - w**self.max_rounds) / (1.0 - w)

    def with_(self, **changes) -> "Config":
        """Return a copy with fields replaced — for sweeps."""
        return replace(self, **changes)


# Axelrod's canonical payoff set. Default, not constant: see decisions.md D-003.
DEFAULT_PAYOFFS = Payoffs(temptation=5.0, reward=3.0, punishment=1.0, sucker=0.0)

# The Phase A roster. Expected to change as the question sharpens.
DEFAULT_ROSTER: tuple[str, ...] = (
    "Always Cooperate",
    "Always Defect",
    "Tit-for-Tat",
    "Grim Trigger",
    "Random",
    "Pavlov",
    "Tit-for-Two-Tats",
)

# The single documented root seed. Every generator in the project is derived
# from this one number; nothing seeds global random state.
ROOT_SEED = 20260902

DEFAULT_CONFIG = Config(
    payoffs=DEFAULT_PAYOFFS,
    roster=DEFAULT_ROSTER,
    rounds=200,  # N; see docs/brief.md — raise if runs have not converged
    trials=20,  # stochastic results are averaged, never single runs
    root_seed=ROOT_SEED,
)


# --- Phase B -----------------------------------------------------------------


@dataclass(frozen=True)
class EvolutionConfig:
    """Everything one replicator run needs.

    `selection_intensity` and `extinction_threshold` are **not settled**. They
    are open items 2 and 3 in PROJECT_STATE.md, deliberately left as
    parameters so the sensitivity can be measured before a value is
    chosen. The values in
    `PROVISIONAL_EVOLUTION_CONFIG` are placeholders for making runs comparable,
    not decisions.
    """

    generations: int
    selection_intensity: float  # s in fitness = (1 - s) + s * payoff
    extinction_threshold: float  # shares below this are zeroed and the rest renormalised

    def __post_init__(self) -> None:
        if self.generations < 1:
            raise ValueError(f"generations must be at least 1, got {self.generations}")
        if not 0.0 <= self.selection_intensity <= 1.0:
            # s > 1 can drive fitness negative on low payoffs; s < 0 inverts
            # selection. Neither is a thing this model means.
            raise ValueError(
                f"selection_intensity must lie in [0, 1], got {self.selection_intensity}"
            )
        if not 0.0 <= self.extinction_threshold < 1.0:
            raise ValueError(
                f"extinction_threshold must lie in [0, 1), got {self.extinction_threshold}"
            )

    def with_(self, **changes) -> "EvolutionConfig":
        return replace(self, **changes)


# PROVISIONAL. See the docstring above: these are placeholders that make the
# comparison runs commensurable, not settled values. s = 0.5 sits in the middle
# of the range being swept; the threshold is well above float64 noise and well
# below any share the dynamics linger at.
PROVISIONAL_SELECTION_INTENSITY = 0.5
PROVISIONAL_EXTINCTION_THRESHOLD = 1e-6

# The values of s the sensitivity run compares.
SELECTION_INTENSITY_SWEEP: tuple[float, ...] = (0.1, 0.5, 1.0)

# The thresholds the sensitivity run compares. Spans "cull early" to
# "effectively never cull".
EXTINCTION_THRESHOLD_SWEEP: tuple[float, ...] = (1e-3, 1e-4, 1e-6, 1e-9, 0.0)

PROVISIONAL_EVOLUTION_CONFIG = EvolutionConfig(
    generations=200,  # G; see docs/brief.md - raise if runs have not converged
    selection_intensity=PROVISIONAL_SELECTION_INTENSITY,
    extinction_threshold=PROVISIONAL_EXTINCTION_THRESHOLD,
)


# --- Open item 4: initial conditions -----------------------------------------

# How many starting mixes to draw uniformly from the simplex. 1000 is enough to
# put a tight bound on the frequency of any outcome that is not vanishingly
# rare: an outcome not seen once in 1000 draws occupies less than about 0.3% of
# the simplex at 95% confidence. It says nothing about outcomes that are rarer
# still, which is why the sweep is paired with a targeted probe of the
# defection corner - see initial_conditions.py.
INITIAL_CONDITION_SAMPLES = 1000

# G for the sweep. Raised from 200 after 20 of 1000 random starts had not
# converged at 200; at 1000 none remain unconverged and the outcome is
# identical to a 5000-generation run - D-018.
SWEEP_GENERATIONS = 1000

# G for the corner probe. Trajectories that start near the boundary between two
# basins move slowly by construction, because they begin close to an unstable
# fixed point, so the probe needs a longer run than the sweep. The measured
# boundary is unchanged between 5000 and 20000 generations.
PROBE_GENERATIONS = 5000


# --- Phase C: the match-length cap -------------------------------------------

# Under continuation probability w a match length is geometric, which has no
# upper bound, so a cap is needed for runs to terminate. The cap is chosen from
# w rather than fixed, so that the *same* negligible fraction of the length
# distribution is truncated at every w.
#
# CONTINUATION_TAIL_PROBABILITY is that fraction: the probability that a match
# would have run longer than the cap. At 1e-4, one match in ten thousand is cut
# short, and the effect on the mean length is of the same order - well below
# the sampling noise from any practical number of trials.
#
# The alternative, capping at the fixed `rounds`, looks harmless and is not: at
# w = 0.99, a cap of 200 truncates 13% of the mass and pulls the mean length
# from 100 to about 86, quietly making the game shorter than w says it is.
CONTINUATION_TAIL_PROBABILITY = 1e-4

# Absolute ceiling, so that a w very close to 1 cannot produce an unusable run
# time. w = 0.999 would ask for 9207 rounds; this stops it. If a sweep ever
# needs w that high, raise this deliberately rather than let it bind silently -
# `max_rounds_for` reports when it does.
HARD_ROUND_CAP = 5000


def max_rounds_for(
    continuation_probability: float,
    fixed_rounds: int,
    tail_probability: float = CONTINUATION_TAIL_PROBABILITY,
    hard_cap: int = HARD_ROUND_CAP,
) -> int:
    """Cap on match length for a given continuation probability.

    At w = 1 the game has a fixed horizon and the cap is just `fixed_rounds`.
    Below 1, the cap is the smallest n with `w**n <= tail_probability`, bounded
    by `hard_cap`.
    """
    w = continuation_probability
    if w >= 1.0:
        return fixed_rounds
    if not 0.0 < w < 1.0:
        raise ValueError(f"continuation_probability must lie in (0, 1], got {w}")
    if not 0.0 < tail_probability < 1.0:
        raise ValueError(
            f"tail_probability must lie in (0, 1), got {tail_probability}"
        )
    needed = math.ceil(math.log(tail_probability) / math.log(w))
    return min(max(needed, 1), hard_cap)


def cap_binds(
    continuation_probability: float,
    fixed_rounds: int,
    tail_probability: float = CONTINUATION_TAIL_PROBABILITY,
    hard_cap: int = HARD_ROUND_CAP,
) -> bool:
    """True when HARD_ROUND_CAP, not the tail probability, is setting the cap.

    Worth checking before trusting a sweep: if this is True at some w, matches
    there are being cut shorter than the tail probability asks for.
    """
    w = continuation_probability
    if w >= 1.0:
        return False
    needed = math.ceil(math.log(tail_probability) / math.log(w))
    return needed > hard_cap


# --- Phase C: the (epsilon, w) sweep -----------------------------------------

# Error rates. 0 anchors the grid to the Phase A/B result.
#
# The axis originally stopped at 0.20 on the assumption that one move in five
# being wrong was past anything interesting. On the seven-strategy control that
# was true - it collapses by 0.16. On the fifteen-strategy pool it is not: the
# pool was still sustaining a 0.67-0.70 cooperation rate in the last column,
# which means every "ceiling = 0.20" that came out of that grid recorded the
# edge of the ruler rather than the edge of the phenomenon (D-033).
#
# Extended to 0.35. The 0.02 spacing of the original columns is preserved
# exactly so that the cells already computed remain valid and are merged rather
# than recomputed; only the final step, 0.34 to 0.35, is shorter, and it is
# there because 0.35 is the stated endpoint.
ERROR_RATE_GRID: tuple[float, ...] = tuple(
    round(0.02 * k, 2) for k in range(18)
) + (0.35,)

# Continuation probabilities, chosen so that (1 - w) - which is what the D-020
# prediction is stated in terms of - is spread geometrically rather than w
# being spread evenly. Expected match lengths: 2, 2.5, 3.3, 5, 10, 20, 50, 100.
CONTINUATION_GRID: tuple[float, ...] = (0.5, 0.6, 0.7, 0.8, 0.9, 0.95, 0.98, 0.99)

# Rounds of play per pair, per replicate. Trials are derived from this and w so
# that every grid point buys roughly the same amount of evidence: short matches
# get proportionally more of them. Without this, a fixed trial count would give
# 200 rounds of evidence at w = 0.5 and 20000 at w = 0.99.
ROUND_BUDGET_PER_PAIR = 10000
MIN_TRIALS = 200
MAX_TRIALS = 800

# Independent repeats of each grid point, each with its own root seed. The
# tournament matrix is a sample, so the survivor set it implies is a sample
# too; a single run at a grid point would report a boundary as a hard edge and
# hide that it is a coin flip. Replicates turn that into a survival frequency.
SWEEP_REPLICATES = 5


def trials_for(
    continuation_probability: float,
    budget: int = ROUND_BUDGET_PER_PAIR,
    minimum: int = MIN_TRIALS,
    maximum: int = MAX_TRIALS,
) -> int:
    """Trials per pair, sized so each grid point sees a similar round count."""
    w = continuation_probability
    expected_length = 1.0 / (1.0 - w) if w < 1.0 else float(budget)
    wanted = math.ceil(budget / expected_length)
    return min(max(wanted, minimum), maximum)


# Phase C runs the dynamics with NO extinction culling and applies this cutoff
# only when reporting who survived. Culling during the run is irreversible, and
# under noise the transients are long and non-monotone - a strategy can sit
# below any sensible cutoff for thousands of generations and still be the
# eventual winner. See D-025.
REPORTING_EXTINCTION_THRESHOLD = 1e-6

# G for Phase C. Far larger than the noiseless G = 1000 because noise makes
# convergence enormously slower: the worst grid cell measured settles at
# generation 25603. Runs that have still not settled are reported, not hidden.
PHASE_C_GENERATIONS = 60000


# --- The D-027 pool -----------------------------------------------------------

# All fifteen, in mechanism order. This is the fixed reference roster for the
# Phase C map; sub-rosters are drawn from it afterwards, and every sub-roster's
# matrix is a submatrix of the pool's, so nothing is re-simulated.
POOL_ROSTER: tuple[str, ...] = tuple(STRATEGIES)

# The seven Phases A and B ran on, kept as the pre-expansion control. The
# comparison between the two maps is what shows whether the earlier conclusions
# were about cooperation or about the cast.
CONTROL_ROSTER = CONTROL_ROSTER

POOL_CONFIG = DEFAULT_CONFIG.with_(roster=POOL_ROSTER)

# How many random sub-rosters to draw for the roster-sensitivity sweep, and how
# large each one is. Sizes span "small enough that composition dominates" to
# "nearly the whole pool".
SUB_ROSTER_DRAWS = 120
SUB_ROSTER_SIZES: tuple[int, ...] = (5, 7, 9, 11, 13)

# Every sub-roster must be able to produce a game: at least one strategy that
# can cooperate and one that can defect, or the question is meaningless.
MIN_SUB_ROSTER_SIZE = 4
