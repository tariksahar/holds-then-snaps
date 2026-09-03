"""Phase A — the round-robin tournament.

Two outputs, and the less obvious one matters more:

* the **per-round average payoff matrix** `M`, where `M[i, j]` is the mean
  payoff *per round* that strategy `i` earns against strategy `j`. Phase B
  consumes this matrix and nothing else. Per-round rather than per-match so
  that fitness does not silently scale with the round count, and including
  self-play on the diagonal because a population model needs the payoff a
  strategy gets when it meets a copy of itself.

* the **leaderboard**, which is a summary of the matrix and is reported
  because it is legible, not because it is the result.

Randomness: every match gets its own generator, derived deterministically
from the root seed and the match's coordinates `(i, j, trial)`. Results
therefore do not depend on the order matches are played in, and re-running
any single cell reproduces it exactly.
"""

from __future__ import annotations

from dataclasses import dataclass

import numpy as np

from config import Config, Payoffs
from strategies import STRATEGIES, Move, Strategy, flip


@dataclass(frozen=True)
class MatchResult:
    """The outcome of one match between two players, A and B."""

    rounds: int
    total_a: float
    total_b: float
    moves_a: tuple[Move, ...]
    moves_b: tuple[Move, ...]

    @property
    def mean_a(self) -> float:
        """A's average payoff per round."""
        return self.total_a / self.rounds

    @property
    def mean_b(self) -> float:
        """B's average payoff per round."""
        return self.total_b / self.rounds


@dataclass(frozen=True)
class LeaderboardEntry:
    name: str
    mean_per_round: float
    total: float


@dataclass(frozen=True)
class TournamentResult:
    names: tuple[str, ...]
    payoff_matrix: np.ndarray  # (n, n); [i, j] = mean per-round payoff to i vs j
    leaderboard: tuple[LeaderboardEntry, ...]
    rounds: int  # the configured N; the cap, not the length, when w < 1
    trials: int
    mean_match_length: float = 0.0  # measured, equals `rounds` when w = 1
    # [i, j] = fraction of the moves i actually played against j that were
    # COOPERATE. Behaviour, not intent: an execution error that turns a
    # cooperation into a defection is counted as the defection it was.
    cooperation_matrix: np.ndarray | None = None

    def index_of(self, name: str) -> int:
        return self.names.index(name)


def play_match(
    a: Strategy,
    b: Strategy,
    rounds: int,
    payoffs: Payoffs,
    rng: np.random.Generator,
    error_rate: float = 0.0,
    continuation_probability: float = 1.0,
    max_rounds: int | None = None,
) -> MatchResult:
    """Play the Prisoner's Dilemma between `a` and `b`.

    The two players draw from independent streams spawned off `rng`, so a
    stochastic strategy playing against a copy of itself does not mirror its
    own moves.

    Phase C adds two parameters. Both default to the Phase A/B behaviour, and
    when they are at their defaults neither draws from the generator at all, so
    a noiseless fixed-length match is bit-identical to the pre-Phase-C code.

    `error_rate` (epsilon) is an **execution** error: with probability epsilon
    a player's intended move is flipped on the way out. What is recorded in
    *both* histories is what was actually played, including the player's own -
    so a player can see that it defected when it meant to cooperate, and its
    opponent sees the same thing. That is the whole content of "execution
    error, not perception error": the two players never disagree about what
    happened. Splitting the two is open exploration 1 in the brief and is
    deliberately not done here.

    `continuation_probability` (w) replaces the fixed, publicly known horizon:
    after each round the match continues with probability w, so its length is
    geometric with mean `1 / (1 - w)`. At w = 1 the match runs exactly `rounds`
    rounds and `rounds` means what it always did.

    For w < 1, `rounds` is **ignored** and the length is capped by `max_rounds`
    instead. A geometric distribution has no upper bound, so some cap is needed
    for runs to terminate; using `rounds` for it would silently truncate the
    distribution (at w = 0.99, `rounds = 200` would cut off 13% of the
    probability mass and pull the mean length from 100 down to about 86). See
    `config.max_rounds_for`, which sizes the cap from w so that the truncated
    mass is negligible rather than incidental.
    """
    if rounds < 1:
        raise ValueError(f"rounds must be at least 1, got {rounds}")
    if not 0.0 <= error_rate <= 1.0:
        raise ValueError(f"error_rate must lie in [0, 1], got {error_rate}")
    if not 0.0 < continuation_probability <= 1.0:
        raise ValueError(
            "continuation_probability must lie in (0, 1], got "
            f"{continuation_probability}"
        )

    if continuation_probability >= 1.0:
        limit = rounds
    else:
        if max_rounds is None:
            raise ValueError(
                "max_rounds is required when continuation_probability < 1: "
                "the match length is unbounded without it"
            )
        if max_rounds < 1:
            raise ValueError(f"max_rounds must be at least 1, got {max_rounds}")
        limit = max_rounds

    rng_a, rng_b = rng.spawn(2)
    history_a: list[Move] = []
    history_b: list[Move] = []
    # Per-match scratch space. Everything a strategy puts here is derived from
    # the histories, so passing it is an optimisation, not hidden state - see
    # the strategies module docstring.
    state_a: dict = {}
    state_b: dict = {}
    total_a = 0.0
    total_b = 0.0
    played = 0

    for _ in range(limit):
        # Both moves are chosen from the same history: simultaneous play.
        move_a = a(history_a, history_b, rng_a, state_a)
        move_b = b(history_b, history_a, rng_b, state_b)

        # Execution error. Guarded rather than multiplied by zero so that at
        # epsilon = 0 the generator is untouched and the pre-Phase-C streams
        # are reproduced exactly.
        if error_rate > 0.0:
            if rng_a.random() < error_rate:
                move_a = flip(move_a)
            if rng_b.random() < error_rate:
                move_b = flip(move_b)

        total_a += payoffs.payoff_for(move_a, move_b)
        total_b += payoffs.payoff_for(move_b, move_a)
        # Both players record what was *played*, not what was intended.
        history_a.append(move_a)
        history_b.append(move_b)
        played += 1

        if continuation_probability < 1.0:
            # Drawn from a third stream, not from either player's, so that
            # match length is independent of what the players did with theirs.
            if rng.random() >= continuation_probability:
                break

    return MatchResult(
        rounds=played,
        total_a=total_a,
        total_b=total_b,
        moves_a=tuple(history_a),
        moves_b=tuple(history_b),
    )


def match_rng(root_seed: int, i: int, j: int, trial: int) -> np.random.Generator:
    """Generator for one cell of the tournament.

    Keyed by coordinates rather than drawn from a running stream, so the
    result of any match is independent of how many matches preceded it.
    """
    return np.random.default_rng(
        np.random.SeedSequence(root_seed, spawn_key=(i, j, trial))
    )


def run_round_robin(
    config: Config, registry: dict[str, Strategy] | None = None
) -> TournamentResult:
    """Play every strategy against every other and against itself.

    Each unordered pair is played once and fills both `M[i, j]` and
    `M[j, i]`, which makes the matrix consistent under player swap by
    construction rather than by luck.

    **Pooling across trials.** The per-round figure is the total payoff over
    all trials divided by the total rounds over all trials, not the average of
    each match's own per-round mean. Under a fixed horizon the two are the same
    number. Under a continuation probability they are not: matches have
    different lengths, and averaging per-match means would weight a one-round
    match as heavily as a hundred-round one. The quantity a population model
    wants is payoff per unit of time played, which is the pooled ratio
    `E[total] / E[length]`, not `E[total / length]`.
    """
    registry = STRATEGIES if registry is None else registry
    names = tuple(config.roster)
    n = len(names)
    players = [registry[name] for name in names]
    matrix = np.zeros((n, n), dtype=float)
    # Measured alongside the payoffs because a strategy's name stops being
    # evidence of its behaviour once errors exist: under a high error rate Grim
    # Trigger is triggered almost at once and plays as a defector, while still
    # being called Grim Trigger. Any claim about whether *cooperation* survived
    # has to be made from what was played.
    cooperation = np.zeros((n, n), dtype=float)
    max_rounds = config.max_rounds
    total_rounds_played = 0

    for i in range(n):
        for j in range(i, n):  # j == i is self-play, and it counts
            payoff_i = 0.0
            payoff_j = 0.0
            cooperations_i = 0
            cooperations_j = 0
            rounds_played = 0
            for trial in range(config.trials):
                rng = match_rng(config.root_seed, i, j, trial)
                result = play_match(
                    players[i],
                    players[j],
                    config.rounds,
                    config.payoffs,
                    rng,
                    error_rate=config.error_rate,
                    continuation_probability=config.continuation_probability,
                    max_rounds=max_rounds,
                )
                payoff_i += result.total_a
                payoff_j += result.total_b
                cooperations_i += sum(
                    1 for move in result.moves_a if move is Move.COOPERATE
                )
                cooperations_j += sum(
                    1 for move in result.moves_b if move is Move.COOPERATE
                )
                rounds_played += result.rounds
            means_i = payoff_i / rounds_played
            means_j = payoff_j / rounds_played
            coop_i = cooperations_i / rounds_played
            coop_j = cooperations_j / rounds_played
            total_rounds_played += rounds_played

            if i == j:
                # Self-play: both sides are the same strategy, so the two
                # scores are two samples of one quantity. Average them.
                matrix[i, i] = 0.5 * (means_i + means_j)
                cooperation[i, i] = 0.5 * (coop_i + coop_j)
            else:
                matrix[i, j] = means_i
                matrix[j, i] = means_j
                cooperation[i, j] = coop_i
                cooperation[j, i] = coop_j

    # A strategy's tournament score is its mean per-round payoff over the
    # whole roster, self-play included — the same quantity Phase B uses as
    # fitness against a uniform population.
    pairs_played = n * (n + 1) // 2
    mean_match_length = total_rounds_played / (pairs_played * config.trials)

    per_strategy_mean = matrix.mean(axis=1)
    leaderboard = tuple(
        sorted(
            (
                LeaderboardEntry(
                    name=names[i],
                    mean_per_round=float(per_strategy_mean[i]),
                    # Expected total over the round robin. Under a stochastic
                    # horizon there is no single "total", so this is scaled by
                    # the measured mean match length rather than by N.
                    total=float(matrix[i].sum() * mean_match_length),
                )
                for i in range(n)
            ),
            key=lambda entry: entry.mean_per_round,
            reverse=True,
        )
    )

    return TournamentResult(
        names=names,
        payoff_matrix=matrix,
        leaderboard=leaderboard,
        rounds=config.rounds,
        trials=config.trials,
        mean_match_length=mean_match_length,
        cooperation_matrix=cooperation,
    )


# --- Reporting ---------------------------------------------------------------


def format_matrix(result: TournamentResult, width: int = 9) -> str:
    """Render the per-round average payoff matrix as text."""
    label_width = max(len(name) for name in result.names)
    header = " " * label_width + "".join(
        f"{name[:width - 1]:>{width}}" for name in result.names
    )
    lines = [header]
    for i, name in enumerate(result.names):
        row = "".join(f"{result.payoff_matrix[i, j]:>{width}.3f}" for j in range(len(result.names)))
        lines.append(f"{name:<{label_width}}{row}")
    return "\n".join(lines)


def format_leaderboard(result: TournamentResult) -> str:
    label_width = max(len(entry.name) for entry in result.leaderboard)
    lines = [f"{'#':>2}  {'strategy':<{label_width}}  {'per round':>9}  {'total':>10}"]
    for rank, entry in enumerate(result.leaderboard, start=1):
        lines.append(
            f"{rank:>2}  {entry.name:<{label_width}}  "
            f"{entry.mean_per_round:>9.3f}  {entry.total:>10.1f}"
        )
    return "\n".join(lines)


if __name__ == "__main__":
    from config import DEFAULT_CONFIG

    outcome = run_round_robin(DEFAULT_CONFIG)
    print(
        f"Phase A - round robin: {len(outcome.names)} strategies, "
        f"{outcome.rounds} rounds, {outcome.trials} trials, "
        f"seed {DEFAULT_CONFIG.root_seed}\n"
    )
    print("Per-round average payoff to row against column:\n")
    print(format_matrix(outcome))
    print("\nLeaderboard (mean per-round payoff over the roster, self-play included):\n")
    print(format_leaderboard(outcome))
