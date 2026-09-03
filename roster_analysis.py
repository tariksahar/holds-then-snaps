"""Roster sensitivity and strategy influence, derived from the saved matrices.

Nothing here re-simulates a match. `M[i, j]` depends only on strategies i and j
and on the game parameters, never on who else entered - so the 15x15 payoff and
cooperation matrices saved at each (epsilon, w, replicate) already contain every
sub-roster's tournament. A drawn roster's matrix is the corresponding
submatrix, and dropping a strategy is dropping a row and a column. That is
D-027's implementation note, and it is what makes measuring the roster
affordable at all.

It also removes a confound for free: every roster is compared against the *same*
sampled matrices, so a difference between two rosters cannot be sampling noise
between two tournaments. It is the roster.

Three questions, in order:

1. **Sensitivity.** Draw random sub-rosters and re-derive the map from each.
   How much of the answer is the cast?
2. **Influence.** Drop each strategy in turn and measure how far the map, the
   survivor set and the cooperation rate move. Rank by influence; a strategy
   that changes nothing measurable did not earn its place.
3. **The Contrite question.** Does a strategy that handles its own mistakes
   correctly push the epsilon ceiling above 0.15? See D-028: the ceiling is
   claimed to be about error-handling rather than about noise as such, and this
   is the sharpest available test of that claim.
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

import numpy as np

from config import (
    CONTINUATION_GRID,
    CONTROL_ROSTER,
    ERROR_RATE_GRID,
    MIN_SUB_ROSTER_SIZE,
    PHASE_C_GENERATIONS,
    PROVISIONAL_EVOLUTION_CONFIG,
    REPORTING_EXTINCTION_THRESHOLD,
    ROOT_SEED,
    SUB_ROSTER_DRAWS,
    SUB_ROSTER_SIZES,
)
from evolution import equal_shares, run_replicator

RESULTS_DIR = Path(__file__).parent / "results"

# A cell counts as cooperative when more than this fraction of moves are
# cooperative. Chosen well clear of both ends: total collapse produces a rate
# equal to epsilon (at most 0.20 on this grid, D-028), and a functioning
# cooperative population sits at 0.5-1.0. Nothing in the results lands near the
# line, so the exact value is not load-bearing - `ceiling_is_robust_to_cutoff`
# checks that.
COOPERATION_CUTOFF = 0.5

# Replicates used for the two expensive sweeps. The headline maps use all five;
# the sub-roster and influence sweeps run hundreds of rosters over every cell,
# so they use fewer. Both quantities being compared use the same number, so the
# comparison stays fair - only the error bars widen.
SUBSET_REPLICATES = 2

# How often the batched replicator retires settled cells. See its use site.
COMPACTION_INTERVAL = 256

EVOLUTION = PROVISIONAL_EVOLUTION_CONFIG.with_(
    generations=PHASE_C_GENERATIONS, extinction_threshold=0.0
)


@dataclass(frozen=True)
class Sweep:
    """The saved sweep: matrices indexed by (epsilon, w, replicate)."""

    names: tuple[str, ...]
    keys: list[tuple[float, float, int]]
    payoff: np.ndarray  # (cells, n, n)
    cooperation: np.ndarray  # (cells, n, n)

    def index_of(self, name: str) -> int:
        return self.names.index(name)

    @property
    def error_rates(self) -> list[float]:
        return sorted({key[0] for key in self.keys})

    @property
    def continuations(self) -> list[float]:
        return sorted({key[1] for key in self.keys})


def load_sweep(path: Path | None = None) -> Sweep:
    """Read the saved matrices back."""
    path = path or (RESULTS_DIR / "phase_c_matrices.npz")
    with np.load(path, allow_pickle=False) as data:
        if "cooperation" not in data:
            raise ValueError(
                f"{path} has no cooperation matrices; it predates D-024 and "
                "cannot support a behavioural analysis. Re-run the grid."
            )
        return Sweep(
            names=tuple(str(n) for n in data["names"]),
            keys=[
                (float(a), float(b), int(c)) for a, b, c in data["keys"]
            ],
            payoff=data["matrices"],
            cooperation=data["cooperation"],
        )


def batched_final_shares(
    payoff_stack: np.ndarray,
    selection_intensity: float = EVOLUTION.selection_intensity,
    generations: int = PHASE_C_GENERATIONS,
) -> np.ndarray:
    """Evolve every grid cell of one roster at once.

    Mathematically identical to calling `run_replicator` on each cell with equal
    starting shares and no culling - the same update, the same bitwise
    fixed-point stop - but with the cell loop moved into numpy. The analysis
    runs hundreds of rosters over hundreds of cells, and at G = 60000 a Python
    loop per cell is the difference between minutes and hours.

    `test_batched_replicator_matches_run_replicator` asserts the equivalence
    rather than trusting this docstring.
    """
    cells, k, _ = payoff_stack.shape
    shares = np.full((cells, k), 1.0 / k)
    s = selection_intensity

    # Cells converge at wildly different speeds - most within a few thousand
    # generations, a few not until fifty thousand. Evolving the whole batch
    # until the slowest one finishes wastes almost all of the work, so settled
    # cells are retired and only the stragglers are carried on. Compaction is
    # periodic rather than every generation because the bookkeeping costs more
    # than the arithmetic it saves when nearly everything is still active.
    active = np.arange(cells)
    working = shares
    working_payoff = payoff_stack

    for generation in range(generations):
        payoff = np.einsum("cij,cj->ci", working_payoff, working)
        fitness = (1.0 - s) + s * payoff
        mean_fitness = np.einsum("ci,ci->c", working, fitness)
        if (mean_fitness <= 0.0).any():
            raise ValueError(
                "mean fitness is not positive in at least one cell; the "
                "replicator update is undefined there"
            )
        stepped = working * fitness / mean_fitness[:, None]

        if np.array_equal(stepped, working):
            # Every remaining cell is at a bitwise fixed point, and a fixed
            # point of a deterministic map stays fixed forever.
            shares[active] = stepped
            return shares

        working = stepped
        if generation % COMPACTION_INTERVAL == COMPACTION_INTERVAL - 1:
            shares[active] = working
            # One extra step, discarded, purely to ask which cells would still
            # move. A cell whose next step reproduces it exactly is finished.
            payoff = np.einsum("cij,cj->ci", working_payoff, working)
            fitness = (1.0 - s) + s * payoff
            mean_fitness = np.einsum("ci,ci->c", working, fitness)
            probe = working * fitness / mean_fitness[:, None]
            moving = ~np.all(probe == working, axis=1)
            if not moving.any():
                return shares
            if not moving.all():
                active = active[moving]
                working = working[moving]
                working_payoff = working_payoff[moving]

    shares[active] = working
    return shares


def roster_map(
    sweep: Sweep, indices: np.ndarray, replicates: int | None = None
) -> tuple[dict[tuple[float, float], float], dict[tuple, tuple[int, ...]]]:
    """The (epsilon, w) map for one sub-roster, and its survivor sets.

    All cells are evolved in one batch. Both returned quantities are read off
    the same saved matrices as every other roster, so differences between
    rosters are the roster.
    """
    selected = [
        position
        for position, (_, _, replicate) in enumerate(sweep.keys)
        if replicates is None or replicate < replicates
    ]
    payoff = sweep.payoff[np.ix_(selected, indices, indices)]
    cooperation = sweep.cooperation[np.ix_(selected, indices, indices)]
    shares = batched_final_shares(payoff)
    rates = np.einsum("ci,cij,cj->c", shares, cooperation, shares)

    cells: dict[tuple[float, float], list[float]] = {}
    survivors: dict[tuple, tuple[int, ...]] = {}
    for row, position in enumerate(selected):
        epsilon, w, replicate = sweep.keys[position]
        cells.setdefault((epsilon, w), []).append(float(rates[row]))
        survivors[(epsilon, w, replicate)] = tuple(
            int(indices[j])
            for j in range(len(indices))
            if shares[row, j] > REPORTING_EXTINCTION_THRESHOLD
        )
    return (
        {key: float(np.mean(values)) for key, values in cells.items()},
        survivors,
    )


def cooperation_rate_of(
    payoff: np.ndarray, cooperation: np.ndarray, indices: np.ndarray
) -> tuple[float, tuple[int, ...]]:
    """Run one sub-roster to convergence and report what it actually plays.

    Returns the realised cooperation rate and the surviving indices (as
    positions in the *full* roster, so results from different sub-rosters stay
    comparable).
    """
    sub_payoff = payoff[np.ix_(indices, indices)]
    sub_cooperation = cooperation[np.ix_(indices, indices)]
    result = run_replicator(
        sub_payoff,
        tuple(str(i) for i in indices),  # names are positional here
        EVOLUTION,
        initial_shares=equal_shares(len(indices)),
    )
    shares = result.final_shares
    rate = float(shares @ sub_cooperation @ shares)
    survivors = tuple(
        int(indices[position])
        for position, share in enumerate(shares)
        if share > REPORTING_EXTINCTION_THRESHOLD
    )
    return rate, survivors


def map_for_roster(
    sweep: Sweep, indices: np.ndarray, replicates: int | None = None
) -> dict[tuple[float, float], float]:
    """Mean cooperation rate per (epsilon, w) for one sub-roster."""
    cells: dict[tuple[float, float], list[float]] = {}
    for position, (epsilon, w, replicate) in enumerate(sweep.keys):
        if replicates is not None and replicate >= replicates:
            continue
        rate, _ = cooperation_rate_of(
            sweep.payoff[position], sweep.cooperation[position], indices
        )
        cells.setdefault((epsilon, w), []).append(rate)
    return {key: float(np.mean(values)) for key, values in cells.items()}


def epsilon_ceiling(cell_map: dict[tuple[float, float], float],
                    cutoff: float = COOPERATION_CUTOFF) -> float:
    """Highest error rate at which *some* horizon still sustains cooperation.

    The single number the whole (epsilon, w) map reduces to when the question
    is "how much noise can cooperation take". Returns -1 if no cell anywhere is
    cooperative.
    """
    cooperative = [
        epsilon for (epsilon, _), rate in cell_map.items() if rate > cutoff
    ]
    return max(cooperative) if cooperative else -1.0


def lowest_w_by_epsilon(
    cell_map: dict[tuple[float, float], float], cutoff: float = COOPERATION_CUTOFF
) -> dict[float, float | None]:
    """The staircase: lowest w that sustains cooperation, per error rate."""
    staircase: dict[float, float | None] = {}
    for epsilon in sorted({key[0] for key in cell_map}):
        viable = [
            w
            for (e, w), rate in cell_map.items()
            if e == epsilon and rate > cutoff
        ]
        staircase[epsilon] = min(viable) if viable else None
    return staircase


def map_distance(
    left: dict[tuple[float, float], float],
    right: dict[tuple[float, float], float],
) -> tuple[float, float]:
    """Mean and maximum absolute difference between two maps, cell by cell."""
    shared = sorted(set(left) & set(right))
    deltas = np.array([abs(left[key] - right[key]) for key in shared])
    return float(deltas.mean()), float(deltas.max())


def draw_sub_rosters(
    n: int,
    sizes: tuple[int, ...],
    draws: int,
    rng: np.random.Generator,
) -> list[np.ndarray]:
    """Random sub-rosters, uniformly over strategies at each size."""
    rosters = []
    per_size = max(1, draws // len(sizes))
    for size in sizes:
        if size < MIN_SUB_ROSTER_SIZE or size > n:
            continue
        for _ in range(per_size):
            rosters.append(np.sort(rng.choice(n, size=size, replace=False)))
    return rosters


# --- Reporting ---------------------------------------------------------------


def format_map(cell_map: dict[tuple[float, float], float], title: str) -> str:
    error_rates = sorted({key[0] for key in cell_map})
    continuations = sorted({key[1] for key in cell_map})
    header = f"{'eps / w':<9}" + "".join(f"{w:>8}" for w in continuations)
    lines = [title, header, "-" * len(header)]
    for epsilon in error_rates:
        row = "".join(
            f"{cell_map[(epsilon, w)]:>8.2f}" if (epsilon, w) in cell_map else "       ."
            for w in continuations
        )
        lines.append(f"{epsilon:<9.2f}{row}")
    return "\n".join(lines)


def format_staircase(cell_map: dict[tuple[float, float], float], label: str) -> str:
    staircase = lowest_w_by_epsilon(cell_map)
    parts = []
    for epsilon, w in staircase.items():
        parts.append(f"{epsilon:.2f}->{'none' if w is None else f'{w:g}'}")
    return f"{label:<28} " + "  ".join(parts)


def _banner(title: str) -> None:
    print()
    print("=" * 78)
    print(title)
    print("=" * 78)


@dataclass(frozen=True)
class Influence:
    name: str
    mean_shift: float
    max_shift: float
    ceiling_without: float
    survivor_changes: int
    cells_flipped: int


def measure_influence(
    sweep: Sweep,
    baseline: dict[tuple[float, float], float],
    baseline_survivors: dict[tuple[float, float, int], tuple[int, ...]],
    replicates: int | None = None,
) -> list[Influence]:
    """Leave one strategy out and measure how far the answer moves.

    D-010 applied exactly this test to Random on the Phase A leaderboard. This
    generalises it: every strategy is dropped in turn, and what is measured is
    not a ranking but the map, the survivor sets, and how many cells change
    their verdict about whether cooperation survives.
    """
    n = len(sweep.names)
    influences = []
    for dropped in range(n):
        kept = np.array([i for i in range(n) if i != dropped])
        reduced_map, reduced_survivors = roster_map(sweep, kept, replicates)
        changes = 0
        for key, survivors in reduced_survivors.items():
            # Compare like with like: the dropped strategy is removed from the
            # baseline's survivor set before comparing, so what is counted is a
            # change among the *remaining* strategies, not the tautology that
            # the dropped one is missing.
            was = set(baseline_survivors[key]) - {dropped}
            if was != set(survivors):
                changes += 1
        mean_shift, max_shift = map_distance(baseline, reduced_map)
        flipped = sum(
            1
            for key in reduced_map
            if (baseline[key] > COOPERATION_CUTOFF)
            != (reduced_map[key] > COOPERATION_CUTOFF)
        )
        influences.append(
            Influence(
                name=sweep.names[dropped],
                mean_shift=mean_shift,
                max_shift=max_shift,
                ceiling_without=epsilon_ceiling(reduced_map),
                survivor_changes=changes,
                cells_flipped=flipped,
            )
        )
    return sorted(influences, key=lambda i: -i.mean_shift)


def main() -> None:
    sweep = load_sweep()
    n = len(sweep.names)
    print(f"Roster analysis over the {n}-strategy pool")
    print(f"{len(sweep.keys)} saved (eps, w, replicate) matrices; nothing re-simulated.")

    full = np.arange(n)
    baseline, baseline_survivors = roster_map(sweep, full)

    _banner("The pool map, and the pre-expansion control")
    print(format_map(baseline, f"Full {n}-strategy pool:"))
    control_indices = np.array(
        sorted(sweep.index_of(name) for name in CONTROL_ROSTER)
    )
    control, _ = roster_map(sweep, control_indices)
    print()
    print(format_map(control, "The original 7, re-derived from the same matrices:"))
    mean_shift, max_shift = map_distance(baseline, control)
    print()
    print(
        f"Expanding the roster from 7 to {n} moves the map by "
        f"{mean_shift:.3f} on average, {max_shift:.3f} at most."
    )
    print("Both maps come from the same sampled matrices, so this difference is")
    print("the roster and nothing else - no sampling noise between them.")
    print()
    print(format_staircase(baseline, f"pool of {n}:"))
    print(format_staircase(control, "control of 7:"))
    print()
    print(
        f"epsilon ceiling: pool {epsilon_ceiling(baseline):.2f}, "
        f"control {epsilon_ceiling(control):.2f}"
    )

    _banner("Influence: what did each strategy change?")
    influences = measure_influence(sweep, baseline, baseline_survivors,
                                   replicates=SUBSET_REPLICATES)
    global LAST_INFLUENCES
    LAST_INFLUENCES = influences
    print(
        f"{'strategy':<20}{'mean shift':>12}{'max':>8}{'cells':>7}"
        f"{'survivor':>10}{'ceiling':>9}"
    )
    print(f"{'':<20}{'in the map':>12}{'':>8}{'flipped':>7}{'changes':>10}{'without':>9}")
    print("-" * 66)
    for influence in influences:
        print(
            f"{influence.name:<20}{influence.mean_shift:>12.4f}"
            f"{influence.max_shift:>8.3f}{influence.cells_flipped:>7}"
            f"{influence.survivor_changes:>10}{influence.ceiling_without:>9.2f}"
        )

    _banner("Does Contrite TFT raise the epsilon ceiling? (D-028)")
    print("D-028 argues the ceiling near epsilon = 0.15 is about error-handling,")
    print("not about noise as such. Contrite TFT is the one pool entry that")
    print("handles its OWN error correctly - it accepts a punishment it provoked")
    print("instead of answering it. If that mechanism is what the ceiling is")
    print("about, adding it should move the ceiling. If not, the ceiling is")
    print("about something else, and that is the more interesting answer.")
    print()
    contrite = sweep.index_of("Contrite TFT")
    comparisons = {
        "control 7": control_indices,
        "control 7 + Contrite": np.sort(np.append(control_indices, contrite)),
        f"pool {n} - Contrite": np.array([i for i in range(n) if i != contrite]),
        f"pool {n}": full,
    }
    print(f"{'roster':<26}{'ceiling':>9}{'best cell':>11}   staircase")
    print("-" * 78)
    for label, indices in comparisons.items():
        cell_map, _ = roster_map(sweep, indices)
        ceiling = epsilon_ceiling(cell_map)
        best = max(cell_map.values())
        stair = lowest_w_by_epsilon(cell_map)
        rendered = " ".join(
            f"{e:.2f}:{'-' if w is None else f'{w:g}'}" for e, w in stair.items()
        )
        print(f"{label:<26}{ceiling:>9.2f}{best:>11.2f}   {rendered}")


    _banner("Roster sensitivity: how much of the answer is the cast?")
    rng = np.random.default_rng(ROOT_SEED)
    rosters = draw_sub_rosters(n, SUB_ROSTER_SIZES, SUB_ROSTER_DRAWS, rng)
    print(
        f"{len(rosters)} random sub-rosters at sizes {SUB_ROSTER_SIZES}, "
        "each re-derived from the pool matrices."
    )
    print()
    print(f"{'size':>6}{'draws':>7}{'ceiling: min':>14}{'median':>9}{'max':>7}"
          f"{'mean |delta map|':>19}")
    print("-" * 62)
    by_size: dict[int, list[tuple[float, float]]] = {}
    for roster in rosters:
        cell_map, _ = roster_map(sweep, roster, replicates=SUBSET_REPLICATES)
        ceiling = epsilon_ceiling(cell_map)
        shift, _ = map_distance(baseline, cell_map)
        by_size.setdefault(len(roster), []).append((ceiling, shift))
    for size in sorted(by_size):
        ceilings = np.array([c for c, _ in by_size[size]])
        shifts = np.array([s for _, s in by_size[size]])
        print(
            f"{size:>6}{len(ceilings):>7}{ceilings.min():>14.2f}"
            f"{np.median(ceilings):>9.2f}{ceilings.max():>7.2f}{shifts.mean():>19.3f}"
        )
    all_ceilings = np.array([c for values in by_size.values() for c, _ in values])
    print()
    print(
        f"Across every draw the epsilon ceiling ranges "
        f"{all_ceilings.min():.2f} to {all_ceilings.max():.2f} "
        f"(pool: {epsilon_ceiling(baseline):.2f})."
    )


def verify_trimmed_roster(
    sweep: Sweep,
    baseline: dict[tuple[float, float], float],
    influences: list[Influence],
    keep: int,
) -> None:
    """Check a trimmed roster against the pool instead of just recommending it.

    Leave-one-out influence does not compose. A strategy can measure as
    uninfluential precisely because something else on the pool covers the same
    mechanism - drop them both and the mechanism goes with them. So the trimmed
    roster is not asserted from the ranking; it is built from the ranking and
    then measured, and if the map moves the ranking was the wrong guide.
    """
    kept_names = [influence.name for influence in influences[:keep]]
    dropped = [influence.name for influence in influences[keep:]]
    indices = np.sort(np.array([sweep.index_of(name) for name in kept_names]))

    trimmed, _ = roster_map(sweep, indices)
    mean_shift, max_shift = map_distance(baseline, trimmed)
    flipped = sum(
        1
        for key in trimmed
        if (baseline[key] > COOPERATION_CUTOFF) != (trimmed[key] > COOPERATION_CUTOFF)
    )

    print()
    print(f"Keeping the {keep} most influential:")
    for name in kept_names:
        print(f"    {name}")
    print(f"Dropping {len(dropped)}: {', '.join(dropped)}")
    print()
    print(
        f"The trimmed map differs from the pool's by {mean_shift:.4f} on "
        f"average, {max_shift:.3f} at most, with {flipped} of {len(trimmed)} "
        "cells changing their verdict."
    )
    print(
        f"epsilon ceiling: pool {epsilon_ceiling(baseline):.2f}, "
        f"trimmed {epsilon_ceiling(trimmed):.2f}"
    )
    print()
    print(format_staircase(baseline, "pool:"))
    print(format_staircase(trimmed, f"trimmed to {keep}:"))


if __name__ == "__main__":
    main()
