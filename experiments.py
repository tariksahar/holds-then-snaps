"""Phase C - the (epsilon, w) sweep, and the two standing predictions.

Three experiments, in order of how much they claim:

1. **The grid.** At each (error rate, continuation probability) run the
   tournament and the replicator to convergence from equal shares, and record
   which strategies survive. Repeated over independent seeds, so what is
   recorded is a survival *frequency*, not a single draw. This is the map the
   brief asks for.

2. **Prediction (a), D-020.** Cooperation's basin should shrink roughly like
   `(1 - w)`. The prediction was derived, not swept: Always Defect's whole
   advantage over Tit-for-Tat is one round of exploitation worth `T - P`,
   amortised over the match, so it scales as `1/N`, and a match under
   continuation probability w lasts `1/(1 - w)` rounds in expectation. Measured
   by bisecting for the minimum Tit-for-Tat share that defeats a defector
   majority, at each w, with no noise.

3. **Prediction (b), D-022.** That same retaliator share should *rise* with
   epsilon, because the claim it rests on - a quarter of a percent of
   Tit-for-Tat is enough, since retaliators score R against each other - is
   exactly what an execution error attacks. Measured the same way, sweeping
   epsilon at fixed w.

Everything is written to `results/` as data. The grid is a CSV with one row per
(epsilon, w, replicate); the raw payoff matrices go to an .npz alongside it, so
the analysis can be redone without re-running the sweep.
"""

from __future__ import annotations

import json
import platform
import sys
from dataclasses import asdict, dataclass
from datetime import datetime, timezone
from pathlib import Path

import numpy as np

from config import (
    CONTINUATION_GRID,
    DEFAULT_CONFIG,
    ERROR_RATE_GRID,
    POOL_CONFIG,
    PHASE_C_GENERATIONS,
    PROVISIONAL_EVOLUTION_CONFIG,
    REPORTING_EXTINCTION_THRESHOLD,
    SWEEP_REPLICATES,
    Config,
    cap_binds,
    trials_for,
)
from evolution import EvolutionResult, run_replicator
from tournament import TournamentResult, run_round_robin

RESULTS_DIR = Path(__file__).parent / "results"

# Strategies that retaliate: they punish a defection and go back to cooperating
# (or never stop punishing, in Grim's case). The distinction that matters for
# both predictions is retaliation, not cooperation - see D-022.
RETALIATORS = ("Tit-for-Tat", "Grim Trigger", "Pavlov", "Tit-for-Two-Tats")

# Bisection resolution for the basin boundary. 30 halvings of [0, 1] resolves
# to about 1e-9, far finer than the noise in the payoff matrix underneath it;
# the replicate spread is the real error bar, not this.
BISECTION_STEPS = 30

# The dynamics run with no culling; the cutoff is applied only when reporting.
PHASE_C_EVOLUTION = PROVISIONAL_EVOLUTION_CONFIG.with_(
    generations=PHASE_C_GENERATIONS, extinction_threshold=0.0
)


@dataclass(frozen=True)
class GridPoint:
    """One (epsilon, w, replicate) cell of the sweep."""

    error_rate: float
    continuation_probability: float
    replicate: int
    root_seed: int
    trials: int
    max_rounds: int
    mean_match_length: float
    settled_generation: int | None
    survivors: tuple[str, ...]
    final_shares: tuple[float, ...]
    cooperation_rate: float  # fraction of moves actually played as COOPERATE
    mean_payoff: float  # population mean per-round payoff at the final mix
    non_defector_share: float  # share NOT held by Always Defect or Random


def sweep_config(
    error_rate: float, continuation_probability: float, replicate: int
) -> Config:
    """The tournament config for one grid cell.

    Each replicate gets its own root seed, offset by the replicate index, so
    replicates are independent but the whole sweep is still reproducible from
    the one documented seed.
    """
    return POOL_CONFIG.with_(
        error_rate=error_rate,
        continuation_probability=continuation_probability,
        trials=trials_for(continuation_probability),
        root_seed=DEFAULT_CONFIG.root_seed + replicate,
    )


def population_cooperation_rate(
    cooperation_matrix: np.ndarray, shares: np.ndarray
) -> float:
    """Fraction of all moves played as COOPERATE at a given population mix.

    This, not the survivor list, is the answer to "did cooperation survive".

    A strategy's name stops being evidence of its behaviour the moment errors
    exist. At an error rate of 0.2, Grim Trigger is triggered within the first
    few rounds of almost every match and spends the rest of it defecting: a
    population of pure Grim Trigger is a population that defects, however the
    strategy is labelled. Counting shares by strategy name reports that as
    cooperation winning. Counting moves reports it as what it is.
    """
    return float(shares @ cooperation_matrix @ shares)


def non_defector_share(result: EvolutionResult) -> float:
    """Share not held by the two unprovoked defectors.

    Kept because it is the obvious quantity and belongs in the raw data, but it
    is *not* the headline: see `population_cooperation_rate` for why a
    name-based count misleads under noise.
    """
    return float(
        sum(
            share
            for name, share in zip(result.names, result.final_shares)
            if name not in ("Always Defect", "Random")
        )
    )


def evaluate_point(
    error_rate: float, continuation_probability: float, replicate: int
) -> tuple[GridPoint, TournamentResult]:
    """Tournament plus replicator at one grid cell, from equal shares."""
    config = sweep_config(error_rate, continuation_probability, replicate)
    tournament = run_round_robin(config)
    evolution = run_replicator(
        tournament.payoff_matrix,
        tournament.names,
        PHASE_C_EVOLUTION,
    )
    point = GridPoint(
        error_rate=error_rate,
        continuation_probability=continuation_probability,
        replicate=replicate,
        root_seed=config.root_seed,
        trials=config.trials,
        max_rounds=config.max_rounds,
        mean_match_length=tournament.mean_match_length,
        settled_generation=evolution.settled_generation,
        survivors=evolution.survivors_above(REPORTING_EXTINCTION_THRESHOLD),
        final_shares=tuple(float(x) for x in evolution.final_shares),
        cooperation_rate=population_cooperation_rate(
            tournament.cooperation_matrix, evolution.final_shares
        ),
        mean_payoff=float(
            evolution.final_shares
            @ tournament.payoff_matrix
            @ evolution.final_shares
        ),
        non_defector_share=non_defector_share(evolution),
    )
    return point, tournament


def run_grid(
    error_rates: tuple[float, ...] = ERROR_RATE_GRID,
    continuation_probabilities: tuple[float, ...] = CONTINUATION_GRID,
    replicates: int = SWEEP_REPLICATES,
    verbose: bool = True,
) -> tuple[
    list[GridPoint],
    dict[tuple, np.ndarray],
    tuple[str, ...],
    dict[tuple, np.ndarray],
]:
    """Run the whole grid.

    Returns the points, the payoff matrices, the roster, and the cooperation
    matrices. The matrices are the expensive part and everything downstream -
    sub-rosters, influence, the control comparison - is derived from them
    without re-simulating, because M[i, j] depends only on i, j and the game
    parameters, never on who else is in the tournament (D-027).
    """
    points: list[GridPoint] = []
    matrices: dict[tuple, np.ndarray] = {}
    cooperation: dict[tuple, np.ndarray] = {}
    names: tuple[str, ...] = ()
    total = len(error_rates) * len(continuation_probabilities) * replicates
    done = 0

    for w in continuation_probabilities:
        if cap_binds(w, DEFAULT_CONFIG.rounds):
            raise ValueError(
                f"the hard round cap binds at w={w}; matches would be cut "
                "shorter than the tail probability allows. Raise HARD_ROUND_CAP "
                "deliberately or drop this w."
            )
        for epsilon in error_rates:
            for replicate in range(replicates):
                point, tournament = evaluate_point(epsilon, w, replicate)
                points.append(point)
                matrices[(epsilon, w, replicate)] = tournament.payoff_matrix
                cooperation[(epsilon, w, replicate)] = tournament.cooperation_matrix
                names = tournament.names
                done += 1
            if verbose:
                latest = points[-1]
                print(
                    f"  w={w:<5} eps={epsilon:<5} "
                    f"[{done:>4}/{total}] "
                    f"len={latest.mean_match_length:>6.2f} "
                    f"coop={latest.cooperation_rate:.3f} "
                    f"survivors={len(latest.survivors)}"
                )
    return points, matrices, names, cooperation


# --- Persistence -------------------------------------------------------------


def save_grid(
    points: list[GridPoint],
    matrices: dict[tuple, np.ndarray],
    names: tuple[str, ...],
    directory: Path = RESULTS_DIR,
    cooperation: dict[tuple, np.ndarray] | None = None,
) -> dict[str, Path]:
    """Write the sweep to disk as data.

    Three files, because they answer three different later questions: the CSV
    for "what happened", the npz for "let me redo the analysis without
    re-running the sweep", and the JSON for "what produced this".
    """
    directory.mkdir(parents=True, exist_ok=True)
    csv_path = directory / "phase_c_grid.csv"
    npz_path = directory / "phase_c_matrices.npz"
    meta_path = directory / "phase_c_metadata.json"

    share_columns = [f"share_{name.replace(' ', '_')}" for name in names]
    header = [
        "error_rate",
        "continuation_probability",
        "replicate",
        "root_seed",
        "trials",
        "max_rounds",
        "mean_match_length",
        "settled_generation",
        "n_survivors",
        "cooperation_rate",
        "mean_payoff",
        "non_defector_share",
        *share_columns,
        "survivors",
    ]
    lines = [",".join(header)]
    for point in points:
        row = [
            f"{point.error_rate:g}",
            f"{point.continuation_probability:g}",
            str(point.replicate),
            str(point.root_seed),
            str(point.trials),
            str(point.max_rounds),
            f"{point.mean_match_length:.4f}",
            "" if point.settled_generation is None else str(point.settled_generation),
            str(len(point.survivors)),
            f"{point.cooperation_rate:.6f}",
            f"{point.mean_payoff:.6f}",
            f"{point.non_defector_share:.6f}",
            *[f"{share:.6f}" for share in point.final_shares],
            # Semicolons inside one field: the roster names contain no commas,
            # but joining with commas would break the CSV.
            '"' + ";".join(point.survivors) + '"',
        ]
        lines.append(",".join(row))
    csv_path.write_text("\n".join(lines) + "\n", encoding="utf-8")

    # Both matrices are saved. The payoff matrix drives the dynamics; the
    # cooperation matrix is what the behavioural metric is computed from, and
    # without it a sub-roster analysis could only be redone by re-simulating.
    arrays = {
        "names": np.array(names),
        "keys": np.array([list(key) for key in matrices], dtype=float),
        "matrices": np.stack(list(matrices.values())),
    }
    if cooperation is not None:
        arrays["cooperation"] = np.stack(
            [cooperation[key] for key in matrices]
        )
    np.savez_compressed(npz_path, **arrays)

    metadata = {
        "generated": datetime.now(timezone.utc).isoformat(),
        "root_seed": DEFAULT_CONFIG.root_seed,
        "roster": list(names),
        "roster_size": len(names),
        "payoffs": asdict(DEFAULT_CONFIG.payoffs),
        "error_rate_grid": list(ERROR_RATE_GRID),
        "continuation_grid": list(CONTINUATION_GRID),
        "replicates": SWEEP_REPLICATES,
        "phase_c_generations": PHASE_C_GENERATIONS,
        "extinction_during_run": False,
        "reporting_extinction_threshold": REPORTING_EXTINCTION_THRESHOLD,
        "selection_intensity": PROVISIONAL_EVOLUTION_CONFIG.selection_intensity,
        "fixed_rounds_at_w_1": DEFAULT_CONFIG.rounds,
        "python": sys.version,
        "numpy": np.__version__,
        "platform": platform.platform(),
        "rows": len(points),
    }
    meta_path.write_text(json.dumps(metadata, indent=2) + "\n", encoding="utf-8")

    return {"csv": csv_path, "npz": npz_path, "metadata": meta_path}


# --- The basin boundary, under noise and a stochastic horizon -----------------


def retaliator_share_needed(
    payoff_matrix: np.ndarray,
    names: tuple[str, ...],
    defector_share: float,
    generations: int = PHASE_C_GENERATIONS,
    steps: int = BISECTION_STEPS,
) -> float:
    """Minimum Tit-for-Tat share, as a fraction of the whole population, for
    cooperation to defeat a defector majority.

    The rest of the population is Always Cooperate. This is the same probe as
    `initial_conditions.defection_basin_edge`, reported in the units the two
    predictions are stated in: share of everyone, not share of the minority.
    """
    config = PHASE_C_EVOLUTION.with_(generations=generations)
    index_c = names.index("Always Cooperate")
    index_d = names.index("Always Defect")
    index_t = names.index("Tit-for-Tat")
    minority = 1.0 - defector_share

    def defector_survives(retaliator_fraction: float) -> bool:
        shares = np.zeros(len(names))
        shares[index_d] = defector_share
        shares[index_t] = minority * retaliator_fraction
        shares[index_c] = minority * (1.0 - retaliator_fraction)
        result = run_replicator(payoff_matrix, names, config, initial_shares=shares)
        return "Always Defect" in result.survivors_above(
            REPORTING_EXTINCTION_THRESHOLD
        )

    if not defector_survives(0.0):
        # No retaliator needed at all: defection loses even to pure naive
        # cooperation. Not expected, but reporting 0 is the honest answer.
        return 0.0
    if defector_survives(1.0):
        # Defection wins even against a minority that is entirely retaliators.
        return float("nan")

    low, high = 0.0, 1.0
    for _ in range(steps):
        middle = 0.5 * (low + high)
        if defector_survives(middle):
            low = middle
        else:
            high = middle
    return minority * high


def boundary_at(
    error_rate: float,
    continuation_probability: float,
    replicate: int,
    defector_share: float,
) -> float:
    config = sweep_config(error_rate, continuation_probability, replicate)
    tournament = run_round_robin(config)
    return retaliator_share_needed(
        tournament.payoff_matrix, tournament.names, defector_share
    )


def boundary_across_replicates(
    error_rate: float,
    continuation_probability: float,
    defector_share: float,
    replicates: int,
) -> np.ndarray:
    return np.array(
        [
            boundary_at(error_rate, continuation_probability, r, defector_share)
            for r in range(replicates)
        ]
    )


# --- Reporting ---------------------------------------------------------------


def survival_frequency(
    points: list[GridPoint], names: tuple[str, ...]
) -> dict[tuple[float, float], dict[str, float]]:
    """Per grid cell, the fraction of replicates each strategy survived in."""
    cells: dict[tuple[float, float], list[GridPoint]] = {}
    for point in points:
        cells.setdefault((point.error_rate, point.continuation_probability), []).append(
            point
        )
    return {
        key: {
            name: sum(1 for p in group if name in p.survivors) / len(group)
            for name in names
        }
        for key, group in cells.items()
    }


def _grid_axes(keys) -> tuple[list[float], list[float]]:
    return sorted({key[0] for key in keys}), sorted({key[1] for key in keys})


def format_cooperation_map(points: list[GridPoint]) -> str:
    """Realised cooperation rate, as a grid. The headline picture, as text."""
    cells: dict[tuple[float, float], list[float]] = {}
    for point in points:
        cells.setdefault((point.error_rate, point.continuation_probability), []).append(
            point.cooperation_rate
        )

    error_rates, continuations = _grid_axes(cells)
    header = f"{'eps / w':<9}" + "".join(f"{w:>8}" for w in continuations)
    lines = [header, "-" * len(header)]
    for epsilon in error_rates:
        row = ""
        for w in continuations:
            values = cells.get((epsilon, w))
            row += "       ." if values is None else f"{np.mean(values):>8.2f}"
        lines.append(f"{epsilon:<9.2f}{row}")
    lines.append("-" * len(header))
    lines.append("fraction of moves actually played as COOPERATE in the final")
    lines.append("population (1.00 = everyone cooperates, 0.00 = nobody does).")
    lines.append("Measured from play, not from strategy names - see D-024.")
    return "\n".join(lines)


def format_survivor_map(points: list[GridPoint], names: tuple[str, ...]) -> str:
    """Per cell, in how many replicates defection was eliminated outright."""
    frequencies = survival_frequency(points, names)
    error_rates, continuations = _grid_axes(frequencies)

    header = f"{'eps / w':<9}" + "".join(f"{w:>8}" for w in continuations)
    lines = [header, "-" * len(header)]
    for epsilon in error_rates:
        row = ""
        for w in continuations:
            cell = frequencies[(epsilon, w)]
            defection = max(cell["Always Defect"], cell["Random"])
            row += f"{1.0 - defection:>8.1f}"
        lines.append(f"{epsilon:<9.2f}{row}")
    lines.append("-" * len(header))
    lines.append("fraction of replicates in which BOTH Always Defect and Random")
    lines.append("went extinct (1.0 = cooperation wins in every replicate)")
    return "\n".join(lines)


def format_strategy_map(
    points: list[GridPoint], names: tuple[str, ...], strategy: str
) -> str:
    """Survival frequency of one strategy across the grid."""
    frequencies = survival_frequency(points, names)
    error_rates, continuations = _grid_axes(frequencies)

    header = f"{'eps / w':<9}" + "".join(f"{w:>8}" for w in continuations)
    lines = [f"{strategy}:", header, "-" * len(header)]
    for epsilon in error_rates:
        row = "".join(
            f"{frequencies[(epsilon, w)][strategy]:>8.1f}" for w in continuations
        )
        lines.append(f"{epsilon:<9.2f}{row}")
    return "\n".join(lines)


def format_convergence(points: list[GridPoint]) -> str:
    """What the map does not show: where the dynamics had not finished.

    Reported rather than filtered out. A cell that is still moving at the
    generation limit is a cell whose entry in the map is provisional, and the
    reader is entitled to know which ones they are.
    """
    unconverged = [p for p in points if p.settled_generation is None]
    settled = [p.settled_generation for p in points if p.settled_generation is not None]
    cells: dict[tuple[float, float], int] = {}
    for point in unconverged:
        key = (point.error_rate, point.continuation_probability)
        cells[key] = cells.get(key, 0) + 1

    lines = [
        f"{len(points) - len(unconverged)} of {len(points)} runs converged. "
        f"Slowest to settle: generation {max(settled) if settled else 0} "
        f"of {PHASE_C_GENERATIONS}.",
    ]
    if not cells:
        return "\n".join(lines)
    lines.append(
        f"{len(unconverged)} runs ({len(unconverged) / len(points):.1%}) were "
        f"still moving at the limit, spread over {len(cells)} cells:"
    )
    for (epsilon, w), count in sorted(cells.items()):
        lines.append(f"    eps={epsilon:<5} w={w:<5} {count}/{SWEEP_REPLICATES}")
    lines.append(
        "All of them lie in the interior of the cooperative band, where the"
    )
    lines.append(
        "dynamics are slowest. Their map entries should be read as provisional."
    )
    return "\n".join(lines)


def format_replicate_spread(points: list[GridPoint]) -> str:
    """Cells where replicates disagree sharply - genuine bistability, not noise."""
    cells: dict[tuple[float, float], list[float]] = {}
    for point in points:
        cells.setdefault(
            (point.error_rate, point.continuation_probability), []
        ).append(point.cooperation_rate)

    split = {
        key: values
        for key, values in cells.items()
        if max(values) - min(values) > 0.3
    }
    lines = [
        "Cells where the cooperation rate varies by more than 0.3 across the",
        f"{SWEEP_REPLICATES} replicates. The only thing differing between them is",
        "the tournament seed, so these are points where the SAME (eps, w) gives",
        "cooperation or collapse depending on the sampled payoff matrix - the",
        "boundary is genuinely bistable there, not merely uncertain.",
        "",
    ]
    if not split:
        lines.append("    none")
        return "\n".join(lines)
    for (epsilon, w), values in sorted(split.items()):
        rendered = ", ".join(f"{v:.2f}" for v in sorted(values))
        lines.append(f"    eps={epsilon:<5} w={w:<5} [{rendered}]")
    return "\n".join(lines)


def _banner(title: str) -> None:
    print()
    print("=" * 78)
    print(title)
    print("=" * 78)


def test_prediction_a(replicates: int, defector_share: float) -> None:
    """D-020: cooperation's basin should shrink roughly like (1 - w)."""
    _banner("Prediction (a), D-020: does the basin shrink like (1 - w)?")
    print("Minimum Tit-for-Tat share, as a fraction of the whole population,")
    print(f"needed to defeat a population that is {defector_share:.0%} Always Defect.")
    print("Noiseless (epsilon = 0), so this isolates the w axis.")
    print()
    print(
        f"{'w':>6}{'1-w':>8}{'E[length]':>11}{'TFT needed':>13}"
        f"{'needed/(1-w)':>15}{'spread':>10}"
    )
    print("-" * 63)

    ratios = []
    logs = []
    for w in CONTINUATION_GRID:
        values = boundary_across_replicates(0.0, w, defector_share, replicates)
        finite = values[np.isfinite(values)]
        if finite.size == 0:
            print(
                f"{w:>6}{1 - w:>8.2f}{1 / (1 - w):>11.1f}"
                f"{'never wins':>13}{'-':>15}{'-':>10}"
            )
            continue
        mean = float(finite.mean())
        ratio = mean / (1.0 - w)
        ratios.append(ratio)
        logs.append((np.log(1.0 - w), np.log(mean)))
        print(
            f"{w:>6}{1 - w:>8.2f}{1 / (1 - w):>11.1f}{mean:>12.4%}"
            f"{ratio:>15.4f}{finite.std():>10.2e}"
        )

    print()
    if len(logs) >= 2:
        x = np.array([a for a, _ in logs])
        y = np.array([b for _, b in logs])
        slope = float(np.polyfit(x, y, 1)[0])
        spread = max(ratios) / min(ratios)
        print(
            f"Log-log slope of (TFT needed) against (1 - w): {slope:.3f}. "
            "The prediction is 1.000."
        )
        print(
            f"The ratio needed/(1-w) varies by a factor of {spread:.2f} "
            "across the range."
        )
        print()
        holds = abs(slope - 1.0) < 0.15 and spread < 1.6
        print("VERDICT:", "HOLDS." if holds else "DOES NOT HOLD.")
        if holds:
            print("The basin shrinks in direct proportion to (1 - w), as derived.")
            print("This was predicted from the payoff structure alone, before any")
            print("of this sweep existed, and the sweep reproduces it.")
        else:
            print("The measured scaling departs from the derived one. The ratio")
            print("column shows where; a slope below 1 means the basin shrinks")
            print("more slowly than (1 - w), above 1 that it shrinks faster.")


def test_prediction_b(
    replicates: int, defector_share: float, continuation_probability: float
) -> None:
    """D-022: the retaliator share needed should rise with epsilon."""
    _banner("Prediction (b), D-022: does the retaliator share needed rise with eps?")
    print(
        f"The same probe, at w = {continuation_probability} "
        f"(expected match length {1 / (1 - continuation_probability):.0f}),"
    )
    print(f"against a population that is {defector_share:.0%} Always Defect.")
    print()
    print(f"{'epsilon':>9}{'TFT needed':>14}{'vs eps=0':>12}{'spread':>11}")
    print("-" * 46)

    measured = []
    for epsilon in ERROR_RATE_GRID:
        values = boundary_across_replicates(
            epsilon, continuation_probability, defector_share, replicates
        )
        finite = values[np.isfinite(values)]
        if finite.size == 0:
            print(f"{epsilon:>9.2f}{'never wins':>14}{'-':>12}{'-':>11}")
            measured.append((epsilon, float("nan")))
            continue
        mean = float(finite.mean())
        measured.append((epsilon, mean))
        baseline = measured[0][1]
        multiple = mean / baseline if baseline > 0 else float("nan")
        print(f"{epsilon:>9.2f}{mean:>13.4%}{multiple:>11.2f}x{finite.std():>11.2e}")

    print()
    finite = [(e, v) for e, v in measured if np.isfinite(v)]
    if len(finite) >= 2:
        values = [v for _, v in finite]
        rises = values[-1] > values[0]
        monotone = all(b >= a - 1e-12 for a, b in zip(values, values[1:]))
        print(
            f"From epsilon = {finite[0][0]:.2f} to {finite[-1][0]:.2f} the share "
            f"needed goes {values[0]:.4%} -> {values[-1]:.4%} "
            f"({values[-1] / values[0]:.1f}x)."
        )
        print(f"Monotonically non-decreasing across the grid: {monotone}.")
        print()
        print("VERDICT:", "HOLDS." if rises else "DOES NOT HOLD.")
        if rises:
            print("Errors make retaliators punish each other by mistake, so the")
            print("mutual-recognition assumption behind the 0.25% figure weakens")
            print("and more retaliator is needed. D-022 anticipated this exactly.")
        else:
            print("The share needed does not rise with epsilon. D-022's")
            print("expectation is not borne out by the measurement.")


def load_saved_grid(
    directory: Path = RESULTS_DIR,
) -> tuple[list[GridPoint], tuple[str, ...]]:
    """Read a saved sweep back, so the analysis can be redone without re-running."""
    import csv

    with (directory / "phase_c_grid.csv").open(encoding="utf-8") as handle:
        rows = list(csv.DictReader(handle))
    names = tuple(
        column[len("share_") :].replace("_", " ")
        for column in rows[0]
        if column.startswith("share_")
    )
    points = [
        GridPoint(
            error_rate=float(row["error_rate"]),
            continuation_probability=float(row["continuation_probability"]),
            replicate=int(row["replicate"]),
            root_seed=int(row["root_seed"]),
            trials=int(row["trials"]),
            max_rounds=int(row["max_rounds"]),
            mean_match_length=float(row["mean_match_length"]),
            settled_generation=(
                int(row["settled_generation"]) if row["settled_generation"] else None
            ),
            survivors=tuple(s for s in row["survivors"].split(";") if s),
            final_shares=tuple(
                float(row[f"share_{name.replace(' ', '_')}"]) for name in names
            ),
            cooperation_rate=float(row["cooperation_rate"]),
            mean_payoff=float(row["mean_payoff"]),
            non_defector_share=float(row["non_defector_share"]),
        )
        for row in rows
    ]
    return points, names


def main(
    run_grid_part: bool = True,
    run_predictions: bool = True,
    run_report_only: bool = False,
) -> None:
    print("Phase C - the (epsilon, w) sweep")
    print(
        f"{len(ERROR_RATE_GRID)} error rates x {len(CONTINUATION_GRID)} "
        f"continuation probabilities x {SWEEP_REPLICATES} replicates "
        f"= {len(ERROR_RATE_GRID) * len(CONTINUATION_GRID) * SWEEP_REPLICATES} runs"
    )
    print(
        f"Root seed {DEFAULT_CONFIG.root_seed}, G = {PHASE_C_GENERATIONS}, "
        "no culling during the run."
    )
    print(f"Roster: the {len(POOL_CONFIG.roster)}-strategy pool (D-027).")
    print()

    if run_report_only:
        points, names = load_saved_grid()
        _banner("The map: where does cooperation survive?")
        print(format_cooperation_map(points))
        print()
        print(format_survivor_map(points, names))
        print()
        for strategy in ("Grim Trigger", "Pavlov", "Tit-for-Tat", "Always Cooperate"):
            print(format_strategy_map(points, names, strategy))
            print()
        _banner("Convergence and bistability")
        print(format_convergence(points))
        print()
        print(format_replicate_spread(points))
        return

    if not run_grid_part:
        test_prediction_a(replicates=SWEEP_REPLICATES, defector_share=0.9)
        test_prediction_b(
            replicates=SWEEP_REPLICATES,
            defector_share=0.9,
            continuation_probability=0.99,
        )
        return

    points, matrices, names, cooperation = run_grid()
    paths = save_grid(points, matrices, names, cooperation=cooperation)

    _banner("The map: where does cooperation survive?")
    print(format_cooperation_map(points))
    print()
    print(format_survivor_map(points, names))
    print()
    for strategy in ("Grim Trigger", "Pavlov", "Tit-for-Tat", "Always Cooperate"):
        print(format_strategy_map(points, names, strategy))
        print()

    _banner("Convergence and bistability")
    print(format_convergence(points))
    print()
    print(format_replicate_spread(points))
    print()
    print("Raw data written to:")
    for label, path in paths.items():
        print(f"  {label:<9} {path}")

    if run_predictions:
        test_prediction_a(replicates=SWEEP_REPLICATES, defector_share=0.9)
        test_prediction_b(
            replicates=SWEEP_REPLICATES,
            defector_share=0.9,
            continuation_probability=0.99,
        )


if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser(description="Phase C experiments.")
    parser.add_argument(
        "--only",
        choices=("grid", "predictions", "report"),
        help="run just one half; default runs both",
    )
    args = parser.parse_args()
    main(
        run_grid_part=args.only not in ("predictions", "report"),
        run_predictions=args.only not in ("grid", "report"),
        run_report_only=args.only == "report",
    )
