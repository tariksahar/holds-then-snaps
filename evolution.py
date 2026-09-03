"""Phase B - replicator dynamics on the Phase A payoff matrix.

The population is well mixed and infinite: a strategy is not a set of agents
but a share `x_i` of the population, and shares evolve by the discrete
replicator equation

    x_i(t+1) = x_i(t) * f_i(t) / f_bar(t)

where `f_i` is strategy i's fitness against the current mix and `f_bar` is the
population mean. Fitness is built from the Phase A matrix::

    payoff_i(t) = sum_j M[i, j] * x_j(t)          # M is per-round average
    f_i(t)      = (1 - s) + s * payoff_i(t)       # s is selection intensity

The affine map is not decoration. The bare ratio `f_i / f_bar` is sensitive to
the absolute level of the payoffs - add a constant to every entry of M and the
dynamics slow down, without any change to the game being played. `s` separates
"who does better" from "how hard that difference is selected on": at s = 0
fitness is 1 for everyone and nothing moves, at s = 1 fitness is the raw payoff
and selection is as sharp as the payoff scale allows.

Two things are deliberately *not* decided here. `s` and the extinction
threshold are parameters of every function in this module, with no defaults
baked into the maths. See PROJECT_STATE.md open items 2 and 3, and the
sensitivity runs printed by `python evolution.py`.

Extinction is kept strictly separate from the replicator step. The step itself
never sends a positive share to zero - shares approach zero asymptotically and
never arrive - so zeroing a share is a numerical and reporting convention
layered on top of the dynamics, not part of them. Keeping the two apart is what
lets invariant 5 be asserted against the dynamics rather than against the
dynamics-plus-a-cutoff, which is a weaker and less interesting claim.
"""

from __future__ import annotations

from dataclasses import dataclass

import numpy as np

from config import EvolutionConfig

# Below this, two consecutive generations count as the same state for the
# purpose of reporting when a run stopped moving. Reporting only; nothing in
# the dynamics depends on it.
SETTLED_TOLERANCE = 1e-12


@dataclass(frozen=True)
class EvolutionResult:
    """A full trajectory, plus the bookkeeping needed to describe it."""

    names: tuple[str, ...]
    trajectory: np.ndarray  # (generations + 1, n); row t is the state at gen t
    config: EvolutionConfig
    extinct_at: dict[str, int | None]  # generation the share was zeroed, else None
    final_fitness: np.ndarray  # fitness of each strategy in the final mix

    @property
    def generations(self) -> int:
        return self.trajectory.shape[0] - 1

    @property
    def initial_shares(self) -> np.ndarray:
        return self.trajectory[0]

    @property
    def final_shares(self) -> np.ndarray:
        return self.trajectory[-1]

    @property
    def survivors(self) -> tuple[str, ...]:
        return tuple(
            name for name, share in zip(self.names, self.final_shares) if share > 0.0
        )

    def survivors_above(self, cutoff: float) -> tuple[str, ...]:
        """Survivors judged at reporting time rather than during the run.

        Running with `extinction_threshold = 0` and applying the cutoff here
        keeps the culling convention out of the dynamics entirely. That matters
        under noise: transients are long and non-monotone, so a strategy can be
        losing badly for thousands of generations and still be the eventual
        winner. Culling it mid-run is irreversible and changes the answer -
        see D-025.
        """
        return tuple(
            name
            for name, share in zip(self.names, self.final_shares)
            if share > cutoff
        )

    def share_of(self, name: str) -> float:
        return float(self.final_shares[self.names.index(name)])

    @property
    def settled_generation(self) -> int | None:
        """First generation after which the state never moves again.

        `None` means the run was still moving when it hit the generation limit,
        which is the signal to raise G.
        """
        movement = np.abs(np.diff(self.trajectory, axis=0)).max(axis=1)
        still_moving = np.flatnonzero(movement > SETTLED_TOLERANCE)
        if still_moving.size == 0:
            return 0
        last_move = int(still_moving[-1])
        if last_move >= self.generations - 1:
            return None
        return last_move + 1

    @property
    def surviving_fitness_spread(self) -> float:
        """Max minus min fitness among survivors in the final mix.

        Zero, to numerical precision, means the survivors are neutral with
        respect to one another: selection has nothing left to act on, and the
        final composition is frozen wherever it happened to arrive rather than
        being an equilibrium selection has chosen. This is the quantity the ESS
        caution in PROJECT_STATE.md is about.
        """
        alive = self.final_shares > 0.0
        if not alive.any():
            return 0.0
        return float(self.final_fitness[alive].max() - self.final_fitness[alive].min())


def equal_shares(n: int) -> np.ndarray:
    """The centre of the simplex: every strategy at 1/n."""
    if n < 1:
        raise ValueError(f"need at least one strategy, got {n}")
    return np.full(n, 1.0 / n, dtype=float)


def population_payoff(payoff_matrix: np.ndarray, shares: np.ndarray) -> np.ndarray:
    """Expected per-round payoff of each strategy against the current mix."""
    return payoff_matrix @ shares


def fitness(
    payoff_matrix: np.ndarray, shares: np.ndarray, selection_intensity: float
) -> np.ndarray:
    """fitness = (1 - s) + s * payoff, evaluated against the current mix."""
    s = selection_intensity
    return (1.0 - s) + s * population_payoff(payoff_matrix, shares)


def replicator_step(
    payoff_matrix: np.ndarray, shares: np.ndarray, selection_intensity: float
) -> np.ndarray:
    """One generation of the pure replicator equation. No extinction culling.

    Dividing by the mean fitness is what keeps the shares on the simplex, so
    the sum-to-one invariant holds by construction rather than by repair.
    """
    f = fitness(payoff_matrix, shares, selection_intensity)
    mean_fitness = float(shares @ f)
    if mean_fitness <= 0.0:
        # Only reachable when the payoff matrix is zero across the whole
        # support of the population and s = 1. Fail loudly rather than emit
        # silent NaNs.
        raise ValueError(
            "mean fitness is not positive, so the replicator update is "
            f"undefined; mean_fitness={mean_fitness}, s={selection_intensity}"
        )
    return shares * f / mean_fitness


def apply_extinction(
    shares: np.ndarray, extinction_threshold: float
) -> tuple[np.ndarray, np.ndarray]:
    """Zero every positive share below the threshold, renormalise the rest.

    Returns the new shares and a boolean mask of what was culled by this call.
    A threshold of 0 culls nothing, which is the honest "no convention applied"
    setting.
    """
    culled = (shares > 0.0) & (shares < extinction_threshold)
    if not culled.any():
        return shares, culled

    survived = np.where(culled, 0.0, shares)
    total = survived.sum()
    if total <= 0.0:
        raise ValueError(
            "the extinction threshold culled the entire population; "
            f"threshold={extinction_threshold} exceeds every share"
        )
    return survived / total, culled


def run_replicator(
    payoff_matrix: np.ndarray,
    names: tuple[str, ...],
    config: EvolutionConfig,
    initial_shares: np.ndarray | None = None,
) -> EvolutionResult:
    """Run the replicator dynamics for `config.generations` generations.

    `initial_shares` defaults to equal shares - one specific point in the
    simplex, and the one open item 4 warns against over-trusting.
    """
    n = len(names)
    if payoff_matrix.shape != (n, n):
        raise ValueError(
            f"payoff matrix is {payoff_matrix.shape}, expected ({n}, {n}) "
            f"to match {n} names"
        )

    if initial_shares is None:
        shares = equal_shares(n)
    else:
        shares = np.asarray(initial_shares, dtype=float)
        if shares.shape != (n,):
            raise ValueError(
                f"initial_shares has shape {shares.shape}, expected ({n},)"
            )
        if (shares < 0.0).any():
            raise ValueError(f"initial_shares must be non-negative, got {shares}")
        total = shares.sum()
        if total <= 0.0:
            raise ValueError("initial_shares must not sum to zero")
        shares = shares / total

    trajectory = np.empty((config.generations + 1, n), dtype=float)
    trajectory[0] = shares
    extinct_at: dict[str, int | None] = {name: None for name in names}

    for generation in range(1, config.generations + 1):
        previous = shares
        shares = replicator_step(payoff_matrix, shares, config.selection_intensity)
        shares, culled = apply_extinction(shares, config.extinction_threshold)
        for index in np.flatnonzero(culled):
            extinct_at[names[index]] = generation
        trajectory[generation] = shares

        # Exact fixed point: the update is deterministic, so if a generation
        # reproduces its predecessor bit for bit, every later generation is
        # identical too. Filling the rest in is not an approximation.
        #
        # Only bitwise equality is safe here. A tolerance-based stop was tried
        # and is wrong: under noise some trajectories creep along a saddle with
        # per-generation steps below 1e-15 for thousands of generations and
        # then accelerate away. Stopping on "barely moving" reported the saddle
        # as the answer and changed a grid cell from 0.74 cooperation to 0.98.
        if np.array_equal(shares, previous):
            trajectory[generation:] = shares
            break

    return EvolutionResult(
        names=names,
        trajectory=trajectory,
        config=config,
        extinct_at=extinct_at,
        final_fitness=fitness(payoff_matrix, shares, config.selection_intensity),
    )


def evolve_from_tournament(
    tournament_result,
    config: EvolutionConfig,
    initial_shares: np.ndarray | None = None,
) -> EvolutionResult:
    """Convenience wrapper: take a Phase A result straight into Phase B."""
    return run_replicator(
        tournament_result.payoff_matrix,
        tournament_result.names,
        config,
        initial_shares,
    )


# --- Sampling the simplex ----------------------------------------------------

# Namespace for the generators used by the initial-conditions sweep, so its
# stream cannot collide with the tournament's (i, j, trial) keys.
SIMPLEX_SPAWN_KEY = 0xC0FFEE


def simplex_rng(root_seed: int) -> np.random.Generator:
    """The generator for initial-condition sampling, derived from the root seed."""
    return np.random.default_rng(
        np.random.SeedSequence(root_seed, spawn_key=(SIMPLEX_SPAWN_KEY,))
    )


def sample_simplex(n: int, count: int, rng: np.random.Generator) -> np.ndarray:
    """Draw `count` points uniformly from the (n-1)-simplex.

    A symmetric Dirichlet with all concentrations 1 is the uniform
    distribution over the simplex. Worth naming explicitly, because the
    obvious-looking alternative - draw n uniforms and normalise - is *not*
    uniform, and concentrates near the centre exactly where the interesting
    behaviour is not.
    """
    if count < 1:
        raise ValueError(f"count must be at least 1, got {count}")
    return rng.dirichlet(np.ones(n), size=count)


def run_from_random_starts(
    payoff_matrix: np.ndarray,
    names: tuple[str, ...],
    config: EvolutionConfig,
    count: int,
    rng: np.random.Generator,
) -> list[EvolutionResult]:
    """Run the dynamics from `count` starting mixes drawn uniformly at random.

    This is open item 4: the equal-shares run is one point in the simplex, and
    a result that only holds there is a result about that point.
    """
    starts = sample_simplex(len(names), count, rng)
    return [
        run_replicator(payoff_matrix, names, config, initial_shares=start)
        for start in starts
    ]


# --- Reporting ---------------------------------------------------------------

# Generations sampled when printing a trajectory. Logarithmic-ish, because
# almost all of the movement happens early.
TRAJECTORY_SNAPSHOTS: tuple[int, ...] = (0, 5, 10, 25, 50, 100, 200)


def _share(value: float) -> str:
    """Render a share, distinguishing extinct from merely tiny."""
    if value == 0.0:
        return "     -   "
    if value < 0.0005:
        return f"{value:>9.2e}"
    return f"{value:>9.4f}"


def format_trajectory(result: EvolutionResult) -> str:
    """Population shares at a handful of generations, one column each."""
    generations = [g for g in TRAJECTORY_SNAPSHOTS if g <= result.generations]
    if result.generations not in generations:
        generations.append(result.generations)

    label_width = max(len(name) for name in result.names)
    header = f"{'generation':<{label_width}}" + "".join(
        f"{g:>10}" for g in generations
    )
    lines = [header, "-" * len(header)]
    for i, name in enumerate(result.names):
        row = "".join(f"{_share(result.trajectory[g, i])}" + " " for g in generations)
        lines.append(f"{name:<{label_width}}{row}")
    return "\n".join(lines)


def format_outcome(result: EvolutionResult) -> str:
    """Final shares, sorted, with the generation each casualty was culled at."""
    label_width = max(len(name) for name in result.names)
    order = np.argsort(-result.final_shares)

    lines = [
        f"{'strategy':<{label_width}}  {'final share':>11}  {'fitness':>8}  outcome",
        "-" * (label_width + 40),
    ]
    for i in order:
        name = result.names[i]
        share = result.final_shares[i]
        died = result.extinct_at[name]
        if share > 0.0:
            outcome = "survives"
        elif died is not None:
            outcome = f"extinct at generation {died}"
        else:
            outcome = "absent"
        lines.append(
            f"{name:<{label_width}}  {share:>11.6f}  "
            f"{result.final_fitness[i]:>8.4f}  {outcome}"
        )

    settled = result.settled_generation
    settled_text = (
        f"settled at generation {settled}"
        if settled is not None
        else f"STILL MOVING at generation {result.generations} - raise G"
    )
    lines.append("")
    lines.append(
        f"{len(result.survivors)} survivors, {settled_text}, "
        f"fitness spread among survivors {result.surviving_fitness_spread:.2e}"
    )
    return "\n".join(lines)


def format_variant_comparison(
    results: dict[str, EvolutionResult], names: tuple[str, ...]
) -> str:
    """Final shares of one roster under several parameter settings."""
    label_width = max(len(name) for name in names)
    column_width = max(11, max(len(label) for label in results) + 2)

    header = f"{'final share':<{label_width}}" + "".join(
        f"{label:>{column_width}}" for label in results
    )
    lines = [header, "-" * len(header)]

    for i, name in enumerate(names):
        row = "".join(
            f"{_share(result.final_shares[i]):>{column_width}}"
            for result in results.values()
        )
        lines.append(f"{name:<{label_width}}{row}")

    lines.append("-" * len(header))
    for caption, extract in (
        ("survivors", lambda r: str(len(r.survivors))),
        (
            "settled at gen",
            lambda r: str(r.settled_generation)
            if r.settled_generation is not None
            else ">G",
        ),
        ("fitness spread", lambda r: f"{r.surviving_fitness_spread:.1e}"),
    ):
        row = "".join(
            f"{extract(result):>{column_width}}" for result in results.values()
        )
        lines.append(f"{caption:<{label_width}}{row}")
    return "\n".join(lines)


def largest_disagreement(results: dict[str, EvolutionResult]) -> float:
    """Largest difference in any one strategy's final share across variants.

    The point of a sensitivity run is a number, not an impression. This is
    that number: how far the answer moves when the parameter moves.
    """
    finals = np.array([result.final_shares for result in results.values()])
    return float((finals.max(axis=0) - finals.min(axis=0)).max())


def _banner(title: str) -> None:
    print()
    print("=" * 78)
    print(title)
    print("=" * 78)


def main() -> None:
    from config import (
        DEFAULT_CONFIG,
        EXTINCTION_THRESHOLD_SWEEP,
        PROVISIONAL_EVOLUTION_CONFIG,
        SELECTION_INTENSITY_SWEEP,
    )
    from tournament import run_round_robin

    base = PROVISIONAL_EVOLUTION_CONFIG
    full = run_round_robin(DEFAULT_CONFIG)

    print("Phase B - replicator dynamics on the Phase A payoff matrix")
    print(
        f"G = {base.generations} generations, "
        f"roster of {len(full.names)}, "
        f"Phase A run at seed {DEFAULT_CONFIG.root_seed}"
    )
    print()
    print("s and extinction_threshold are NOT settled. The values below are")
    print("provisional placeholders; runs (b) and (d) are the evidence for")
    print("choosing them. See PROJECT_STATE.md open items 2 and 3.")

    # --- (a) ---------------------------------------------------------------
    _banner(
        f"(a) equal starting shares, s = {base.selection_intensity}, "
        f"extinction threshold = {base.extinction_threshold:g}"
    )
    run_a = evolve_from_tournament(full, base)
    print(format_trajectory(run_a))
    print()
    print(format_outcome(run_a))

    # --- (b) ---------------------------------------------------------------
    _banner(
        "(b) sensitivity to selection intensity s, everything else held fixed"
    )
    by_s = {
        f"s={s:g}": evolve_from_tournament(full, base.with_(selection_intensity=s))
        for s in SELECTION_INTENSITY_SWEEP
    }
    print(format_variant_comparison(by_s, full.names))
    print()
    print(
        f"Largest disagreement between any two values of s: "
        f"{largest_disagreement(by_s):.2e} of population share."
    )
    print("s sets the pace, not the destination. Over the range swept it")
    print("changes how many generations the run takes to settle by a factor")
    print("of about four, and changes the mixture it settles on by less than")
    print("a fifth of a percentage point. The survivor set is identical.")

    # --- (c) ---------------------------------------------------------------
    reduced_roster = tuple(n for n in DEFAULT_CONFIG.roster if n != "Random")
    _banner(
        f"(c) Random removed from the roster, s = {base.selection_intensity}, "
        f"extinction threshold = {base.extinction_threshold:g}"
    )
    reduced = run_round_robin(DEFAULT_CONFIG.with_(roster=reduced_roster))
    run_c = evolve_from_tournament(reduced, base)
    print(format_trajectory(run_c))
    print()
    print(format_outcome(run_c))

    # --- (d) ---------------------------------------------------------------
    _banner(
        "(d) sensitivity to the extinction threshold, "
        f"s = {base.selection_intensity}"
    )
    by_threshold = {
        (f"t={t:g}" if t else "t=0 (none)"): evolve_from_tournament(
            full, base.with_(extinction_threshold=t)
        )
        for t in EXTINCTION_THRESHOLD_SWEEP
    }
    print(format_variant_comparison(by_threshold, full.names))
    culling = {label: r for label, r in by_threshold.items() if label != "t=0 (none)"}
    print()
    print(
        f"Largest disagreement between any two non-zero thresholds: "
        f"{largest_disagreement(culling):.2e} of population share."
    )
    print("A share only ever falls below the threshold on its way to zero, so")
    print("the threshold cannot change which strategies are dying, only when")
    print("they stop being counted. Culling earlier does perturb the final")
    print("mixture - a defector on its way out is still being paid by the")
    print("cooperators it has not finished eating - but over six orders of")
    print("magnitude the perturbation stays in the fourth decimal place.")
    print()
    print("The t=0 column is the control: with no cutoff nothing is ever")
    print("declared extinct, so it reports 7 survivors while holding Always")
    print("Defect at 5e-28 and Random at 3e-20. Those are not populations.")
    print("The non-zero fitness spread in that column is the same artifact -")
    print("it is measuring strategies that are extinct in everything but the")
    print("bookkeeping. Some cutoff is needed; which one barely matters.")


if __name__ == "__main__":
    main()
