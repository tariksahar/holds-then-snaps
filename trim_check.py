"""One-off: verify a trimmed roster against the pool rather than assert it.

Kept in the repo because the recommendation in decisions.md rests on it.
Run: python trim_check.py
"""

import numpy as np

import roster_analysis as ra


def main() -> None:
    sweep = ra.load_sweep()
    full = np.arange(len(sweep.names))
    baseline, baseline_survivors = ra.roster_map(sweep, full)
    influences = ra.measure_influence(
        sweep, baseline, baseline_survivors, replicates=ra.SUBSET_REPLICATES
    )
    print("Influence order (most to least):")
    for rank, influence in enumerate(influences, 1):
        print(f"  {rank:>2}. {influence.name:<20} {influence.mean_shift:.4f}")

    for keep in (8, 10, 12):
        ra._banner(f"Trimmed roster: keep {keep}")
        ra.verify_trimmed_roster(sweep, baseline, influences, keep)


if __name__ == "__main__":
    main()
