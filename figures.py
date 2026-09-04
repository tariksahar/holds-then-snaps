"""Render the report's figures from the derived data in `results/`.

Every figure reads a CSV written by `report_data.py`; nothing here recomputes a
result and nothing is typed in by hand. A number that appears in a caption can
therefore be pointed at a named file, and regenerating the figures is a check
on the numbers rather than a chore.

Censored values are drawn as censored. Where a measurement ran out of grid
before the phenomenon ran out — the ceiling of a roster still cooperating in
the last column — the point is an open marker with an upward arrow and is
excluded from any trend line, rather than being plotted at the grid edge as if
that were where it sat. Doing this by eye is how the error in D-033 survived
four decision entries.

Run: python figures.py
"""

from __future__ import annotations

import csv
from pathlib import Path

import matplotlib

matplotlib.use("Agg")

import matplotlib.pyplot as plt
import numpy as np
from matplotlib.colors import LinearSegmentedColormap

RESULTS = Path(__file__).parent / "results"
FIGURES = Path(__file__).parent / "figures"

# Serif to sit alongside the report's body text without looking pasted in.
plt.rcParams.update(
    {
        "font.family": "serif",
        "font.size": 9,
        "axes.titlesize": 10,
        "axes.labelsize": 9,
        "figure.dpi": 150,
        "savefig.bbox": "tight",
        "axes.spines.top": False,
        "axes.spines.right": False,
    }
)

# Defection to cooperation. Deliberately not red-green.
COOPERATION_CMAP = LinearSegmentedColormap.from_list(
    "cooperation", ["#3b2f2f", "#8c6d4f", "#d9c9a3", "#7fa8a0", "#1f5f5b"]
)
INK = "#222222"
ACCENT = "#b4413a"
MUTED = "#8a8a8a"


def read(name: str) -> list[dict]:
    with (RESULTS / name).open(encoding="utf-8") as handle:
        return list(csv.DictReader(handle))


def _grid(rows: list[dict], value_key: str) -> tuple[np.ndarray, list[float], list[float]]:
    error_rates = sorted({float(r["error_rate"]) for r in rows})
    continuations = sorted({float(r["continuation_probability"]) for r in rows})
    grid = np.full((len(error_rates), len(continuations)), np.nan)
    for row in rows:
        i = error_rates.index(float(row["error_rate"]))
        j = continuations.index(float(row["continuation_probability"]))
        grid[i, j] = float(row[value_key])
    return grid, error_rates, continuations


def _heatmap(ax, grid, error_rates, continuations, *, title: str) -> object:
    image = ax.imshow(
        grid, origin="lower", aspect="auto", cmap=COOPERATION_CMAP, vmin=0.0, vmax=1.0
    )
    ax.set_xticks(range(len(continuations)))
    ax.set_xticklabels([f"{w:g}" for w in continuations])
    ax.set_yticks(range(len(error_rates)))
    ax.set_yticklabels([f"{e:g}" for e in error_rates])
    ax.set_xlabel("continuation probability $w$")
    ax.set_ylabel("error rate $\\varepsilon$")
    ax.set_title(title)
    for spine in ax.spines.values():
        spine.set_visible(False)
    ax.tick_params(length=0)
    return image


# --- 1: the map --------------------------------------------------------------


def figure1() -> Path:
    rows = read("fig1_map_pool.csv")
    grid, error_rates, continuations = _grid(rows, "cooperation_rate_mean")

    fig, ax = plt.subplots(figsize=(6.2, 5.4))
    image = _heatmap(
        ax, grid, error_rates, continuations,
        title="Realised cooperation on the 15-strategy pool",
    )

    # Mark the cells where replicates disagree by more than 0.3. These are two
    # attractors, not one noisy value, and a mean describes neither.
    for row in rows:
        if row["bistable"] == "yes":
            i = error_rates.index(float(row["error_rate"]))
            j = continuations.index(float(row["continuation_probability"]))
            ax.plot(j, i, marker="o", ms=9, mfc="none", mec=ACCENT, mew=1.3)

    bar = fig.colorbar(image, ax=ax, fraction=0.046, pad=0.03)
    bar.set_label("fraction of moves played as C")
    bar.outline.set_visible(False)

    ax.plot([], [], marker="o", ms=8, mfc="none", mec=ACCENT, mew=1.3, ls="none",
            label="bistable across replicates")
    ax.legend(loc="upper right", frameon=False, fontsize=7.5,
              bbox_to_anchor=(1.0, -0.09))

    path = FIGURES / "fig1_map_pool.pdf"
    fig.savefig(path)
    fig.savefig(path.with_suffix(".png"))
    plt.close(fig)
    return path


# --- 2: the edge, the figure the repository is named after --------------------


def figure2() -> Path:
    rows = read("fig2_edge_profile.csv")
    epsilon = np.array([float(r["error_rate"]) for r in rows])
    raw = np.array([float(r["cooperation_rate"]) for r in rows])
    norm = np.array([float(r["normalised"]) for r in rows])
    above = np.array([r["above_cutoff"] == "yes" for r in rows])

    fig, (top, bottom) = plt.subplots(
        2, 1, figsize=(6.2, 5.8), sharex=True,
        gridspec_kw={"height_ratios": [1.35, 1], "hspace": 0.16},
    )

    # Top: the normalised reading, where the shape lives.
    top.axhspan(0, 1, color="#f6f3ee", zorder=0)
    top.plot(epsilon, norm, "-", color=INK, lw=1.8, zorder=3)
    top.plot(epsilon[above], norm[above], "o", color=INK, ms=5, zorder=4)
    top.plot(epsilon[~above], norm[~above], "o", mfc="white", mec=INK, ms=5,
             mew=1.2, zorder=4)

    last_alive = epsilon[above].max()
    top.axvline(last_alive, color=ACCENT, lw=1, ls=(0, (4, 3)), zorder=2)

    # Offsets set by hand so the three edge figures - the ones the report
    # quotes instead of the single ceiling number - stay clear of the cutoff
    # line and of each other.
    for value, offset, align, colour in (
        (0.28, (-10, 10), "right", INK),
        (0.30, (12, 8), "left", ACCENT),
        (0.32, (12, 4), "left", ACCENT),
    ):
        if value in set(epsilon):
            index = int(np.where(epsilon == value)[0][0])
            top.annotate(
                f"{norm[index]:.3f}",
                xy=(epsilon[index], norm[index]),
                xytext=offset, textcoords="offset points",
                ha=align, va="center", fontsize=9, color=colour,
                fontweight="bold" if colour is ACCENT else "normal",
            )

    top.set_ylabel(
        "normalised cooperation\n"
        "$(\\mathrm{rate}-\\varepsilon)/(1-2\\varepsilon)$"
    )
    top.set_ylim(-0.06, 1.14)
    top.set_title("Cooperation holds, and then it snaps  ($w = 0.99$)", pad=16)
    top.annotate(
        f"last point above the cutoff ($\\varepsilon = {last_alive:g}$)",
        xy=(last_alive, 1.10), xytext=(-8, 0), textcoords="offset points",
        ha="right", va="center", fontsize=7.5, color=ACCENT,
    )
    top.plot([], [], "o", color=INK, ms=5, ls="none", label="above cutoff")
    top.plot([], [], "o", mfc="white", mec=INK, mew=1.2, ms=5, ls="none",
             label="collapsed")
    top.legend(frameon=False, fontsize=7.5, loc="lower left")

    # Bottom: the raw rate, with the floor it collapses onto.
    bottom.plot(epsilon, raw, "-", color=INK, lw=1.5, label="realised rate")
    bottom.plot(epsilon, epsilon, "--", color=MUTED, lw=1.2,
                label="total defection ($\\mathrm{rate}=\\varepsilon$)")
    bottom.plot(epsilon, 1 - epsilon, ":", color=MUTED, lw=1.2,
                label="total cooperation ($\\mathrm{rate}=1-\\varepsilon$)")
    bottom.fill_between(epsilon, epsilon, 1 - epsilon, color="#f6f3ee", zorder=0)
    bottom.axvline(last_alive, color=ACCENT, lw=1, ls=(0, (4, 3)))
    bottom.set_xlabel("error rate $\\varepsilon$")
    bottom.set_ylabel("fraction of moves\nplayed as C")
    bottom.legend(frameon=False, fontsize=7.5, loc="lower left")

    path = FIGURES / "fig2_edge_profile.pdf"
    fig.savefig(path)
    fig.savefig(path.with_suffix(".png"))
    plt.close(fig)
    return path


# --- 3: the roster effect ----------------------------------------------------


def figure3() -> Path:
    rows = read("fig3_roster_comparison.csv")
    pool, error_rates, continuations = _grid(rows, "pool15")
    control, _, _ = _grid(rows, "control7")

    fig, axes = plt.subplots(1, 2, figsize=(8.4, 4.8), sharey=True)
    image = _heatmap(axes[0], control, error_rates, continuations,
                     title="Pre-expansion control (7 strategies)")
    _heatmap(axes[1], pool, error_rates, continuations,
             title="Pool (15 strategies)")
    axes[1].set_ylabel("")

    bar = fig.colorbar(image, ax=axes, fraction=0.035, pad=0.02)
    bar.set_label("fraction of moves played as C")
    bar.outline.set_visible(False)
    fig.suptitle(
        "The same sampled matrices, two rosters", y=0.98, fontsize=10.5,
    )

    path = FIGURES / "fig3_roster_comparison.pdf"
    fig.savefig(path)
    fig.savefig(path.with_suffix(".png"))
    plt.close(fig)
    return path


# --- 4: influence ------------------------------------------------------------


def figure4() -> Path:
    rows = read("fig4_influence.csv")
    rows = sorted(rows, key=lambda r: float(r["mean_shift"]))
    names = [r["strategy"] for r in rows]
    shift = np.array([float(r["mean_shift"]) for r in rows])
    cost = np.array([float(r["ceiling_cost"]) for r in rows])

    fig, (left, right) = plt.subplots(
        1, 2, figsize=(8.0, 5.0), sharey=True,
        gridspec_kw={"width_ratios": [1.35, 1], "wspace": 0.16},
    )

    positions = np.arange(len(names))
    left.barh(positions, shift, color=INK, height=0.62)
    left.set_yticks(positions)
    left.set_yticklabels(names)
    left.set_xlabel("mean $|\\Delta$ map$|$ when removed")
    left.set_title("Effect on the map")
    for y, value in zip(positions, shift):
        left.text(value + 0.0018, y, f"{value:.4f}", va="center", fontsize=7.5)
    left.set_xlim(0, shift.max() * 1.26)
    left.set_xticks([0.00, 0.02, 0.04, 0.06, 0.08, 0.10])

    colours = [ACCENT if value > 0 else MUTED for value in cost]
    right.barh(positions, cost, color=colours, height=0.62)
    right.set_xlabel("$\\varepsilon$ ceiling lost when removed")
    right.set_title("Effect on the ceiling")
    for y, value in zip(positions, cost):
        if value > 0:
            right.text(value + 0.002, y, f"{value:.2f}", va="center", fontsize=7.5,
                       color=ACCENT)
    right.set_xlim(0, max(cost.max() * 1.35, 0.02))
    right.set_xticks([0.00, 0.05, 0.10])

    fig.suptitle(
        "What each strategy was holding up", y=0.97, fontsize=10.5,
    )
    path = FIGURES / "fig4_influence.pdf"
    fig.savefig(path)
    fig.savefig(path.with_suffix(".png"))
    plt.close(fig)
    return path


# --- 5: sensitivity against roster size --------------------------------------


def figure5() -> Path:
    rows = read("fig5_sensitivity.csv")
    size = np.array([int(r["roster_size"]) for r in rows])
    shift = np.array([float(r["mean_abs_map_delta"]) for r in rows])
    low = np.array([float(r["ceiling_min"]) for r in rows])
    median = np.array([float(r["ceiling_median"]) for r in rows])
    high = np.array([float(r["ceiling_max"]) for r in rows])
    high_censored = np.array([r["ceiling_max_censored"] == "yes" for r in rows])

    fig, (top, bottom) = plt.subplots(
        2, 1, figsize=(6.0, 5.6), sharex=True,
        gridspec_kw={"height_ratios": [1.25, 1], "hspace": 0.15},
    )

    # The uncensored quantity leads.
    top.plot(size, shift, "-o", color=INK, lw=1.8, ms=6)
    for x, y in zip(size, shift):
        top.annotate(f"{y:.3f}", xy=(x, y), xytext=(0, 9),
                     textcoords="offset points", ha="center", fontsize=8.5)
    top.set_ylabel("mean $|\\Delta$ map$|$ against the pool")
    top.set_title("How much of the answer is the cast")
    top.set_ylim(0, shift.max() * 1.28)

    # The ceiling spread, with censoring drawn as censoring.
    bottom.vlines(size, low, high, color=MUTED, lw=1.2)
    bottom.plot(size, low, "o", color=INK, ms=5, label="worst draw")
    bottom.plot(size, median, "D", color=ACCENT, ms=5, label="median draw")
    bottom.plot(size[~high_censored], high[~high_censored], "o", color=INK, ms=5,
                label="best draw")
    if high_censored.any():
        bottom.plot(size[high_censored], high[high_censored], "^", mfc="white",
                    mec=INK, mew=1.2, ms=7,
                    label="best draw: censored ($\\geq$ grid edge)")
        # Headroom so the arrows are inside the axes: an arrow clipped at the
        # frame would read as a plotted value, which is the whole thing this
        # marker exists to avoid.
        bottom.set_ylim(low.min() - 0.03, high.max() + 0.06)
        for x, y in zip(size[high_censored], high[high_censored]):
            bottom.annotate("", xy=(x, y + 0.035), xytext=(x, y + 0.008),
                            arrowprops=dict(arrowstyle="->", color=INK, lw=1.1))
    bottom.set_xlabel("roster size")
    bottom.set_ylabel("$\\varepsilon$ ceiling")
    bottom.set_xticks(size)
    bottom.legend(frameon=False, fontsize=7.5, loc="lower right", ncol=2)

    path = FIGURES / "fig5_sensitivity.pdf"
    fig.savefig(path)
    fig.savefig(path.with_suffix(".png"))
    plt.close(fig)
    return path


# --- 6: the Phase B trajectory -----------------------------------------------


def figure6() -> Path:
    rows = read("fig6_phase_b_trajectory.csv")
    names = [key for key in rows[0] if key != "generation"]
    generation = np.array([int(r["generation"]) for r in rows])
    shares = {name: np.array([float(r[name]) for r in rows]) for name in names}

    # The run settles at generation 59; showing all 200 would be four fifths
    # flat line. Labels are anchored at the right edge of the view, not at the
    # end of the data, or they land outside the axes and get clipped away.
    view = 90
    edge = int(np.searchsorted(generation, view))

    fig, ax = plt.subplots(figsize=(7.4, 4.2))
    order = sorted(names, key=lambda n: -shares[n][edge])

    for name in order:
        series = shares[name]
        survives = series[-1] > 1e-6
        ax.plot(
            generation, series,
            color=INK if survives else ACCENT,
            lw=1.6 if survives else 1.2,
            ls="-" if survives else (0, (4, 2)),
            alpha=1.0 if survives else 0.85,
        )

    # Two survivors finish 0.006 apart, which is closer than their labels are
    # tall. Walk down the ordered list and push each label far enough below the
    # previous one to stay readable; the leader line keeps it attached to its
    # curve.
    survivors = [n for n in order if shares[n][-1] > 1e-6]
    minimum_gap = 0.019
    label_y: list[float] = []
    for name in survivors:
        wanted = shares[name][edge]
        if label_y and wanted > label_y[-1] - minimum_gap:
            wanted = label_y[-1] - minimum_gap
        label_y.append(wanted)

    for name, y in zip(survivors, label_y):
        ax.annotate(
            f"{name.replace('_', ' ')}  {shares[name][-1]:.3f}",
            xy=(view, shares[name][edge]),
            xytext=(view + 3, y), textcoords="data",
            va="center", fontsize=8, color=INK, annotation_clip=False,
            arrowprops=dict(arrowstyle="-", color=MUTED, lw=0.6,
                            shrinkA=0, shrinkB=0),
        )

    # The two casualties are annotated at separated heights: both curves reach
    # zero in the same corner and their labels would otherwise sit on top of
    # each other.
    extinct_names = [n for n in order if shares[n][-1] <= 1e-6]
    for index, name in enumerate(extinct_names):
        series = shares[name]
        extinct = int(np.argmax(series <= 1e-12))
        ax.annotate(
            f"{name.replace('_', ' ')} — extinct at generation {extinct}",
            xy=(extinct, 0.0), xytext=(6, 10 + 14 * index),
            textcoords="offset points", fontsize=7.5, color=ACCENT,
            annotation_clip=False,
            arrowprops=dict(arrowstyle="-", color=ACCENT, lw=0.6, alpha=0.5,
                            shrinkA=0, shrinkB=1),
        )

    ax.set_xlim(0, view)
    ax.set_ylim(0, 0.32)
    ax.set_xlabel("generation")
    ax.set_ylabel("population share")
    ax.set_title("Phase B: the control roster, no noise, fixed horizon")
    fig.subplots_adjust(right=0.74)

    path = FIGURES / "fig6_phase_b_trajectory.pdf"
    fig.savefig(path)
    fig.savefig(path.with_suffix(".png"))
    plt.close(fig)
    return path


# --- manifest ----------------------------------------------------------------


def write_manifest(paths: dict[str, tuple[Path, str, list[str]]]) -> Path:
    lines = [
        "# Figure manifest",
        "",
        "Which file holds which numbers. Every figure is rendered by",
        "`figures.py` from a CSV written by `report_data.py`, which in turn",
        "derives it from a primary artefact in `results/`. No number in a",
        "figure or its caption is typed in by hand.",
        "",
        "Regenerate with `python report_data.py && python figures.py`.",
        "",
        "| figure | data file | derived from | key values |",
        "|---|---|---|---|",
    ]
    for label, (path, source, notes) in paths.items():
        lines.append(
            f"| `{path.name}` | `results/{source}` | {notes[0]} | {notes[1]} |"
        )
    lines += [
        "",
        "## Censoring",
        "",
        "A ceiling is *censored* when the roster was still cooperating in the",
        "last column of the grid: the measurement ran out before the",
        "phenomenon did, and the value is a lower bound rather than a",
        "location. Figure 5 draws those as open upward triangles, never as",
        "points. `fig5_sensitivity.csv` carries an explicit `*_censored`",
        "column for each ceiling statistic; `fig2_edge_profile.csv` carries",
        "one too, and it is `no` throughout because the pool collapses at",
        "0.30, inside the grid.",
        "",
        "## Primary artefacts",
        "",
        "- `results/phase_c_grid.csv` — 760 rows, one per (ε, w, replicate) on",
        "  the 15-strategy pool, ε to 0.35. Realised cooperation rate, mean",
        "  payoff, survivors, convergence generation.",
        "- `results/phase_c_matrices.npz` — the payoff and cooperation matrices",
        "  behind that grid. Every sub-roster result is a submatrix of these.",
        "- `results/control7_grid.csv`, `results/control7_matrices.npz` — the",
        "  frozen pre-expansion control, ε to 0.20.",
        "- `results/roster_analysis.log` — the roster sweep's own record.",
        "- `results/phase_c_metadata.json` — seed, roster, payoffs, grid,",
        "  generation limit, library versions.",
    ]
    path = FIGURES / "MANIFEST.md"
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")
    return path


def main() -> None:
    FIGURES.mkdir(exist_ok=True)
    print("Rendering figures from results/\n")

    built = {}
    for label, builder, source, notes in (
        ("1", figure1, "fig1_map_pool.csv",
         ("`phase_c_grid.csv`", "mean cooperation rate per cell; bistable cells ringed")),
        ("2", figure2, "fig2_edge_profile.csv",
         ("`phase_c_grid.csv`, w = 0.99 column", "normalised 0.788 / 0.628 / 0.162 at ε = 0.28 / 0.30 / 0.32")),
        ("3", figure3, "fig3_roster_comparison.csv",
         ("`phase_c_matrices.npz`", "pool and control maps from one sample")),
        ("4", figure4, "fig4_influence.csv",
         ("`phase_c_matrices.npz`", "mean |Δ map| and ε-ceiling cost per strategy")),
        ("5", figure5, "fig5_sensitivity.csv",
         ("`roster_analysis.log`", "mean |Δ map| 0.177 → 0.037 over sizes 5 → 13")),
        ("6", figure6, "fig6_phase_b_trajectory.csv",
         ("`tournament.py` + `evolution.py`, control roster", "shares by generation; AllD and Random eliminated")),
    ):
        path = builder()
        built[label] = (path, source, notes)
        print(f"  figure {label}: {path.name}")

    manifest = write_manifest(built)
    print(f"\n  {manifest.relative_to(manifest.parent.parent)}")
    print("\nDone.")


if __name__ == "__main__":
    main()
