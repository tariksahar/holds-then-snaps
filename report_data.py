"""Derive the report's figure data from the primary results, once.

Every figure in `figures/` reads one of the CSVs written here, and every CSV is
computed from a primary artefact in `results/` — the sweep grid, the saved
matrices, or a run log. Nothing is typed in by hand, so regenerating a figure
is a check on the numbers rather than a chore, and any value quoted in a
caption can be traced to a named file.

Run: python report_data.py

Two of the outputs are expensive because they re-derive maps from the saved
matrices (a few minutes each); the rest are seconds. The expensive ones are
still recomputed rather than parsed, because a number that was recomputed is
evidence and a number that was copied is a claim.

The one exception is `fig5_sensitivity.csv`, which is parsed out of
`results/roster_analysis.log`. That sweep runs 120 sub-rosters over the whole
grid and takes hours; the log is its record, and the CSV is a machine-readable
view of that record rather than an independent recomputation. It is labelled as
such in the manifest.
"""

from __future__ import annotations

import csv
import re
from pathlib import Path

import numpy as np

from config import (
    CONTROL_ROSTER,
    DEFAULT_CONFIG,
    ERROR_RATE_GRID,
    PROVISIONAL_EVOLUTION_CONFIG,
)
from evolution import run_replicator
from roster_analysis import (
    COOPERATION_CUTOFF,
    SUBSET_REPLICATES,
    ceiling_is_censored,
    epsilon_ceiling,
    load_sweep,
    map_distance,
    measure_influence,
    normalised_cooperation,
    roster_map,
)
from tournament import run_round_robin

RESULTS = Path(__file__).parent / "results"

# The column of the map the report reads along. w = 0.99 is the longest horizon
# on the grid, so it is where cooperation survives the most noise and where the
# edge is sharpest.
EDGE_W = 0.99


def _write(path: Path, header: list[str], rows: list[list]) -> Path:
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.writer(handle, lineterminator="\n")
        writer.writerow(header)
        writer.writerows(rows)
    print(f"  wrote {path.name} ({len(rows)} rows)")
    return path


def _grid_cells(csv_path: Path) -> dict[tuple[float, float], list[float]]:
    cells: dict[tuple[float, float], list[float]] = {}
    with csv_path.open(encoding="utf-8") as handle:
        for row in csv.DictReader(handle):
            key = (
                float(row["error_rate"]),
                float(row["continuation_probability"]),
            )
            cells.setdefault(key, []).append(float(row["cooperation_rate"]))
    return cells


def phase_a_leaderboard() -> Path:
    """The Phase A tournament, the one result the report quoted from no file.

    Everything else in the report traces to an artefact under `results/`; the
    noiseless seven-strategy leaderboard did not, because it predates the sweep
    machinery and was only ever printed. It is recomputed here from
    `DEFAULT_CONFIG` and written out, so the numbers in Section 4.1 can be
    checked without running anything.

    Three quantities in one table, because they are one argument: the
    leaderboard with Random, the same leaderboard with Random removed, and the
    opponent-by-opponent difference between the Grim Trigger and Tit-for-Tat
    rows. The third column is what makes the first two make sense - the entire
    margin between the top two strategies sits in a single opponent.
    """
    full = run_round_robin(DEFAULT_CONFIG)
    reduced = run_round_robin(
        DEFAULT_CONFIG.with_(
            roster=tuple(n for n in DEFAULT_CONFIG.roster if n != "Random")
        )
    )
    with_random = {e.name: e.mean_per_round for e in full.leaderboard}
    without_random = {e.name: e.mean_per_round for e in reduced.leaderboard}
    rank_with = {e.name: i for i, e in enumerate(full.leaderboard, 1)}
    rank_without = {e.name: i for i, e in enumerate(reduced.leaderboard, 1)}

    grim = full.index_of("Grim Trigger")
    tft = full.index_of("Tit-for-Tat")

    rows = []
    for name in sorted(full.names, key=lambda n: -with_random[n]):
        column = full.payoff_matrix[grim, full.index_of(name)] -             full.payoff_matrix[tft, full.index_of(name)]
        rows.append(
            [
                name,
                rank_with[name],
                f"{with_random[name]:.4f}",
                "" if name not in rank_without else rank_without[name],
                "" if name not in without_random else f"{without_random[name]:.4f}",
                f"{column:+.4f}",
            ]
        )

    gap = with_random["Grim Trigger"] - with_random["Tit-for-Tat"]
    total = full.payoff_matrix[grim].sum() - full.payoff_matrix[tft].sum()
    print(
        f"    leaderboard gap {gap:.4f}; Grim-TFT row difference sums to "
        f"{total:.4f} over {len(full.names)} opponents = {total/len(full.names):.4f}"
    )
    return _write(
        RESULTS / "phase_a_leaderboard.csv",
        ["strategy", "rank_with_random", "mean_per_round_with_random",
         "rank_without_random", "mean_per_round_without_random",
         "grim_minus_tft_against_this_opponent"],
        rows,
    )


def figure1_map(source: Path = RESULTS / "phase_c_grid.csv") -> Path:
    """Mean realised cooperation rate per (epsilon, w) on the pool."""
    cells = _grid_cells(source)
    rows = []
    for (epsilon, w), values in sorted(cells.items()):
        array = np.array(values)
        rows.append(
            [
                f"{epsilon:g}",
                f"{w:g}",
                len(values),
                f"{array.mean():.6f}",
                f"{array.min():.6f}",
                f"{array.max():.6f}",
                # A cell where the replicates disagree this much is bistable,
                # not noisy: same parameters, different attractor.
                "yes" if array.max() - array.min() > 0.3 else "no",
            ]
        )
    return _write(
        RESULTS / "fig1_map_pool.csv",
        ["error_rate", "continuation_probability", "replicates",
         "cooperation_rate_mean", "cooperation_rate_min", "cooperation_rate_max",
         "bistable"],
        rows,
    )


def figure2_edge(source: Path = RESULTS / "phase_c_grid.csv") -> Path:
    """The hold-then-snap profile along the longest horizon.

    Both readings are written. The raw rate is what was played; the normalised
    one rescales it onto `[eps, 1 - eps]`, the band the error rate leaves
    available, so that 1 is total cooperation and 0 total defection at every
    error rate. The shape is only visible in the normalised column.
    """
    cells = _grid_cells(source)
    error_rates = sorted({e for e, w in cells if w == EDGE_W})
    grid_max = max(error_rates)

    rows = []
    for epsilon in error_rates:
        values = np.array(cells[(epsilon, EDGE_W)])
        raw = float(values.mean())
        rows.append(
            [
                f"{epsilon:g}",
                f"{raw:.6f}",
                f"{normalised_cooperation(raw, epsilon):.6f}",
                f"{values.min():.6f}",
                f"{values.max():.6f}",
                "yes" if raw > COOPERATION_CUTOFF else "no",
                # True only if the last column is still cooperative, i.e. the
                # grid ran out before the population did.
                "yes" if (epsilon == grid_max and raw > COOPERATION_CUTOFF) else "no",
            ]
        )
    return _write(
        RESULTS / "fig2_edge_profile.csv",
        ["error_rate", "cooperation_rate", "normalised", "rate_min", "rate_max",
         "above_cutoff", "censored"],
        rows,
    )


def figure3_roster_comparison(sweep) -> Path:
    """Pool and pre-expansion control, re-derived from the same matrices.

    Both maps come from one set of sampled tournaments, so the difference
    between them cannot be sampling noise between two runs. It is the roster.
    """
    full = np.arange(len(sweep.names))
    control = np.sort(np.array([sweep.index_of(n) for n in CONTROL_ROSTER]))
    pool_map, _ = roster_map(sweep, full)
    control_map, _ = roster_map(sweep, control)

    rows = []
    for key in sorted(pool_map):
        epsilon, w = key
        rows.append(
            [
                f"{epsilon:g}",
                f"{w:g}",
                f"{pool_map[key]:.6f}",
                f"{control_map[key]:.6f}",
                f"{pool_map[key] - control_map[key]:.6f}",
            ]
        )
    mean_shift, max_shift = map_distance(pool_map, control_map)
    print(
        f"    pool ceiling {epsilon_ceiling(pool_map):.2f}"
        f"{' (censored)' if ceiling_is_censored(pool_map) else ''}, "
        f"control ceiling {epsilon_ceiling(control_map):.2f}"
        f"{' (censored)' if ceiling_is_censored(control_map) else ''}, "
        f"mean |delta| {mean_shift:.4f}, max {max_shift:.4f}"
    )
    return _write(
        RESULTS / "fig3_roster_comparison.csv",
        ["error_rate", "continuation_probability", "pool15", "control7", "difference"],
        rows,
    )


def figure4_influence(sweep) -> Path:
    """Leave-one-out influence for all fifteen strategies."""
    full = np.arange(len(sweep.names))
    baseline, baseline_survivors = roster_map(sweep, full)
    influences = measure_influence(
        sweep, baseline, baseline_survivors, replicates=SUBSET_REPLICATES
    )
    pool_ceiling = epsilon_ceiling(baseline)

    # A ceiling sitting on the last column of the grid is a lower bound, not a
    # location. Comparing against the grid edge is exactly equivalent to
    # re-deriving the map and asking `ceiling_is_censored`, and avoids paying
    # for fifteen extra maps to learn something already in hand.
    grid_edge = max(ERROR_RATE_GRID)

    rows = []
    for rank, influence in enumerate(influences, start=1):
        rows.append(
            [
                rank,
                influence.name,
                f"{influence.mean_shift:.6f}",
                f"{influence.max_shift:.6f}",
                influence.cells_flipped,
                influence.survivor_changes,
                f"{influence.ceiling_without:g}",
                "yes" if influence.ceiling_without >= grid_edge else "no",
                f"{pool_ceiling - influence.ceiling_without:.4f}",
            ]
        )
    return _write(
        RESULTS / "fig4_influence.csv",
        ["rank", "strategy", "mean_shift", "max_shift", "cells_flipped",
         "survivor_changes", "ceiling_without", "ceiling_without_censored",
         "ceiling_cost"],
        rows,
    )


SENSITIVITY_ROW = re.compile(
    r"^\s*(\d+)\s+(\d+)\s+([\d.]+)\s+([\d.]+)\s+([\d.]+)\s+([\d.]+)\s*$"
)


def figure5_sensitivity(log_path: Path = RESULTS / "roster_analysis.log") -> Path:
    """Roster sensitivity by size, read out of the sweep's own log.

    Parsed rather than recomputed: the sweep behind it runs 120 sub-rosters
    over the whole grid and takes hours. The log is the primary record; this is
    a machine-readable view of it.
    """
    text = log_path.read_text(encoding="utf-8")
    section = text.split("Roster sensitivity")[1]
    grid_max = 0.35  # the last error rate on the extended grid

    rows = []
    for line in section.splitlines():
        match = SENSITIVITY_ROW.match(line)
        if not match:
            continue
        size, draws, low, median, high, shift = match.groups()
        rows.append(
            [
                int(size),
                int(draws),
                f"{float(shift):.6f}",
                f"{float(low):g}",
                f"{float(median):g}",
                f"{float(high):g}",
                "yes" if float(low) >= grid_max else "no",
                "yes" if float(median) >= grid_max else "no",
                "yes" if float(high) >= grid_max else "no",
            ]
        )
    if not rows:
        raise ValueError(f"no sensitivity rows parsed from {log_path}")
    return _write(
        RESULTS / "fig5_sensitivity.csv",
        ["roster_size", "draws", "mean_abs_map_delta", "ceiling_min",
         "ceiling_median", "ceiling_max", "ceiling_min_censored",
         "ceiling_median_censored", "ceiling_max_censored"],
        rows,
    )


def figure6_phase_b_trajectory() -> Path:
    """The Phase B run: the control roster, no noise, fixed horizon.

    Context for everything that follows. This is how the apparatus behaves
    before either Phase C dial is turned, and it is the run D-016 is about.
    """
    tournament = run_round_robin(DEFAULT_CONFIG.with_(roster=CONTROL_ROSTER))
    result = run_replicator(
        tournament.payoff_matrix,
        tournament.names,
        PROVISIONAL_EVOLUTION_CONFIG,
    )
    print(
        f"    survivors {result.survivors}, settled at generation "
        f"{result.settled_generation}, fitness spread "
        f"{result.surviving_fitness_spread:.2e}"
    )
    rows = [
        [generation] + [f"{share:.8f}" for share in result.trajectory[generation]]
        for generation in range(result.generations + 1)
    ]
    return _write(
        RESULTS / "fig6_phase_b_trajectory.csv",
        ["generation"] + [name.replace(" ", "_") for name in result.names],
        rows,
    )


def main() -> None:
    print("Deriving figure data from results/\n")
    print("figure 1 - the (epsilon, w) map on the pool")
    figure1_map()
    print("figure 2 - the edge profile along w = 0.99")
    figure2_edge()

    sweep = load_sweep()
    print("figure 3 - pool against the pre-expansion control")
    figure3_roster_comparison(sweep)
    print("figure 4 - leave-one-out influence (slow: re-derives 15 maps)")
    figure4_influence(sweep)
    print("figure 5 - roster sensitivity by size")
    figure5_sensitivity()
    print("figure 6 - Phase B trajectory")
    figure6_phase_b_trajectory()
    print("\nDone.")


if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument(
        "--phase-a", action="store_true",
        help="write only results/phase_a_leaderboard.csv (seconds, not minutes)",
    )
    args = parser.parse_args()
    if args.phase_a:
        phase_a_leaderboard()
    else:
        main()
