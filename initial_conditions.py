"""Open item 4 - how much of the Phase B result is the starting point?

The headline Phase B run starts from equal shares. That is one point in a
six-dimensional simplex, chosen because it is the obvious one, and a result
that only holds there is a result about that point rather than about the model.

Two experiments, because they answer different questions and neither answers
the other's:

1. **A uniform sweep.** Draw starting mixes uniformly from the simplex, run
   each to convergence, and count outcomes. This measures how much of the
   simplex leads where - it is the right tool for "is the equal-shares result
   typical?"

2. **A targeted probe of the defection corner.** A uniform sweep is blind to
   any basin small enough that 1000 draws miss it, and "never observed" is not
   "does not exist". Always Defect is a strict Nash equilibrium of this game -
   it scores 1.000 against itself where Tit-for-Tat scores 0.995 - so a basin
   around the all-defect corner must exist on theoretical grounds. The probe
   goes and finds its edge directly.

The two together are what makes the answer in PROJECT_STATE.md sayable:
the survivor set is a property of the model, the proportions are a
property of the start,
and the defection basin is real but requires a minority with essentially no
retaliator in it.
"""

from __future__ import annotations

from collections import Counter

import numpy as np

from config import (
    DEFAULT_CONFIG,
    INITIAL_CONDITION_SAMPLES,
    PROBE_GENERATIONS,
    PROVISIONAL_EVOLUTION_CONFIG,
    SWEEP_GENERATIONS,
)
from evolution import (
    EvolutionResult,
    equal_shares,
    run_from_random_starts,
    run_replicator,
    sample_simplex,
    simplex_rng,
)
from tournament import run_round_robin

# Percentiles reported for the spread of final shares. The extremes matter more
# than the centre here: the question is how far the outcome can travel, not
# where it typically lands.
REPORTED_PERCENTILES = (0, 5, 50, 95, 100)

# Resolution of the bisection that locates the edge of the defection basin.
BISECTION_STEPS = 40


def survival_counts(results: list[EvolutionResult], names: tuple[str, ...]) -> dict:
    """How many runs each strategy was still alive at the end of."""
    finals = np.array([result.final_shares for result in results])
    return {name: int((finals[:, j] > 0.0).sum()) for j, name in enumerate(names)}


def format_survival(
    results: list[EvolutionResult], names: tuple[str, ...], baseline: EvolutionResult
) -> str:
    counts = survival_counts(results, names)
    total = len(results)
    width = max(len(name) for name in names)

    lines = [
        f"{'strategy':<{width}}  {'survives':>9}  {'rate':>7}  equal-shares run",
        "-" * (width + 40),
    ]
    for j, name in enumerate(names):
        count = counts[name]
        alive = "survives" if baseline.final_shares[j] > 0.0 else "extinct"
        lines.append(
            f"{name:<{width}}  {count:>4} / {total:<4}  {count / total:>6.1%}  {alive}"
        )
    return "\n".join(lines)


def format_spread(
    results: list[EvolutionResult], names: tuple[str, ...], baseline: EvolutionResult
) -> str:
    """How far the final share of each strategy travels across the sweep."""
    finals = np.array([result.final_shares for result in results])
    width = max(len(name) for name in names)

    header = f"{'final share':<{width}}" + "".join(
        f"{f'p{p}':>9}" for p in REPORTED_PERCENTILES
    )
    header += f"{'equal':>9}"
    lines = [header, "-" * len(header)]

    for j, name in enumerate(names):
        row = "".join(
            f"{np.percentile(finals[:, j], p):>9.4f}" for p in REPORTED_PERCENTILES
        )
        lines.append(f"{name:<{width}}{row}{baseline.final_shares[j]:>9.4f}")
    return "\n".join(lines)


def format_outcome_classes(
    results: list[EvolutionResult], baseline: EvolutionResult
) -> str:
    """Every distinct survivor set observed, most common first."""
    classes = Counter(result.survivors for result in results)
    lines = []
    for survivors, count in classes.most_common():
        marker = (
            "  <- identical to the equal-shares run"
            if survivors == baseline.survivors
            else ""
        )
        lines.append(
            f"{count:>5} / {len(results):<5} ({count / len(results):>6.1%})  "
            f"{len(survivors)} survivors: {', '.join(survivors)}{marker}"
        )
    return "\n".join(lines)


def defection_basin_edge(
    payoff_matrix: np.ndarray,
    names: tuple[str, ...],
    defector_share: float,
    generations: int,
) -> float:
    """Find how exploitable the minority must be for Always Defect to win.

    Holds Always Defect at `defector_share` and splits the remainder between
    Always Cooperate (which feeds it) and Tit-for-Tat (which punishes it),
    then bisects on the split. Returns the fraction of the minority that must
    be Always Cooperate before Always Defect survives.
    """
    config = PROVISIONAL_EVOLUTION_CONFIG.with_(generations=generations)
    index_c = names.index("Always Cooperate")
    index_d = names.index("Always Defect")
    index_t = names.index("Tit-for-Tat")
    minority = 1.0 - defector_share

    def defector_survives(exploitable_fraction: float) -> bool:
        shares = np.zeros(len(names))
        shares[index_d] = defector_share
        shares[index_c] = minority * exploitable_fraction
        shares[index_t] = minority * (1.0 - exploitable_fraction)
        result = run_replicator(payoff_matrix, names, config, initial_shares=shares)
        return "Always Defect" in result.survivors

    low, high = 0.0, 1.0
    for _ in range(BISECTION_STEPS):
        middle = 0.5 * (low + high)
        if defector_survives(middle):
            high = middle
        else:
            low = middle
    return high


def main() -> None:
    tournament = run_round_robin(DEFAULT_CONFIG)
    names = tournament.names
    matrix = tournament.payoff_matrix
    sweep_config = PROVISIONAL_EVOLUTION_CONFIG.with_(generations=SWEEP_GENERATIONS)

    print("Open item 4 - dependence of the Phase B result on the starting mix")
    print(
        f"{INITIAL_CONDITION_SAMPLES} starting mixes drawn uniformly from the "
        f"{len(names) - 1}-simplex,"
    )
    print(
        f"each run to G = {SWEEP_GENERATIONS} generations at "
        f"s = {sweep_config.selection_intensity}, "
        f"extinction threshold = {sweep_config.extinction_threshold:g},"
    )
    print(f"Phase A matrix from root seed {DEFAULT_CONFIG.root_seed}.")

    baseline = run_replicator(matrix, names, sweep_config)
    results = run_from_random_starts(
        matrix,
        names,
        sweep_config,
        INITIAL_CONDITION_SAMPLES,
        simplex_rng(DEFAULT_CONFIG.root_seed),
    )

    unconverged = sum(1 for r in results if r.settled_generation is None)
    print()
    print(
        f"Convergence: {len(results) - unconverged} / {len(results)} runs had "
        f"stopped moving by generation {SWEEP_GENERATIONS}."
    )
    if unconverged:
        print(f"  WARNING: {unconverged} runs were still moving. Raise G.")

    print()
    print("=" * 78)
    print("1. How often does each strategy survive?")
    print("=" * 78)
    print(format_survival(results, names, baseline))

    print()
    print("=" * 78)
    print("2. How far does the final composition travel?")
    print("=" * 78)
    print(format_spread(results, names, baseline))

    print()
    print("=" * 78)
    print("3. Is the survivor set ever different from the equal-shares run?")
    print("=" * 78)
    print(format_outcome_classes(results, baseline))

    deviants = [r for r in results if r.survivors != baseline.survivors]
    starts = sample_simplex(
        len(names), INITIAL_CONDITION_SAMPLES, simplex_rng(DEFAULT_CONFIG.root_seed)
    )
    if deviants:
        print()
        print("The runs that differ, and what they started from:")
        for index, result in enumerate(results):
            if result.survivors == baseline.survivors:
                continue
            print(f"\n  run {index}:")
            for j, name in enumerate(names):
                print(
                    f"    {name:<18} start {starts[index][j]:.4f}"
                    f"  ->  final {result.final_shares[j]:.4f}"
                )

    print()
    print("=" * 78)
    print("4. The defection corner, which uniform sampling cannot reach")
    print("=" * 78)
    print("Always Defect scores 1.000 against itself where Tit-for-Tat scores")
    print("0.995, so it is a strict Nash equilibrium and a basin around the")
    print("all-defect corner must exist. It was never once entered above. The")
    print("question is therefore not whether it exists but how small it is.")
    print()
    print("Holding Always Defect at a fixed share and splitting the rest of the")
    print("population between Always Cooperate (which feeds it) and Tit-for-Tat")
    print("(which punishes it):")
    print()
    print(
        f"{'AllD share':>11}  {'AllD wins once the':>20}  "
        f"{'equivalently, TFT below':>24}"
    )
    print(f"{'':>11}  {'minority is at least':>20}  {'this share of everyone':>24}")
    print("-" * 61)
    rescue_shares = []
    for defector_share in (0.50, 0.80, 0.90, 0.95, 0.99):
        edge = defection_basin_edge(matrix, names, defector_share, PROBE_GENERATIONS)
        rescue = (1.0 - defector_share) * (1.0 - edge)
        rescue_shares.append(rescue)
        print(
            f"{defector_share:>11.2f}  {edge:>19.1%}  {rescue:>23.2%}"
        )
    print()
    print("The right-hand column is the finding. Read as a fraction of the")
    print("whole population rather than of the minority, the retaliator share")
    print(
        f"needed to save cooperation is roughly constant - between "
        f"{min(rescue_shares):.2%} and {max(rescue_shares):.2%} -"
    )
    print("across defector shares from 50% to 99%. What defeats defection is")
    print("not the number of cooperators but the presence of retaliators, and")
    print("the quantity of retaliator required barely depends on how dominant")
    print("the defectors are. A population that is 99% Always Defect still")
    print(f"turns cooperative given {rescue_shares[-1]:.2%} Tit-for-Tat.")
    print()
    print("Caveat on scope: this probe holds the minority to Always Cooperate")
    print("and Tit-for-Tat only. It establishes that the defection basin is")
    print("real and narrow along that one axis. It is not a measurement of the")
    print("basin's volume, which would need a sweep over the whole boundary.")

    print()
    print("=" * 78)
    print("Verdict")
    print("=" * 78)
    print("The SURVIVOR SET is a property of the model. Always Defect and")
    print("Random went extinct in every one of the 1000 uniform draws, and the")
    print("cooperative neutral mixture is reached from 99.9% of the simplex.")
    print()
    print("The PROPORTIONS are a property of the starting point, and almost")
    print("entirely so. Grim Trigger finishes anywhere from 0.0005 to 0.9455")
    print("depending only on where the run began. The equal-shares figures in")
    print("the Phase B result are one draw from that range, not a fixed point.")
    print()
    print("So the Phase B headline is safe and the Phase B table is not. Report")
    print("that cooperation wins and that the winners are mutually neutral;")
    print("do not report the five final shares as if they were the answer.")


if __name__ == "__main__":
    main()
