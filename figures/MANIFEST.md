# Figure manifest

Which file holds which numbers. Every figure is rendered by
`figures.py` from a CSV written by `report_data.py`, which in turn
derives it from a primary artefact in `results/`. No number in a
figure or its caption is typed in by hand.

Regenerate with `python report_data.py && python figures.py`.

| figure | data file | derived from | key values |
|---|---|---|---|
| `fig1_map_pool.pdf` | `results/fig1_map_pool.csv` | `phase_c_grid.csv` | mean cooperation rate per cell; bistable cells ringed |
| `fig2_edge_profile.pdf` | `results/fig2_edge_profile.csv` | `phase_c_grid.csv`, w = 0.99 column | normalised 0.788 / 0.628 / 0.162 at ε = 0.28 / 0.30 / 0.32 |
| `fig3_roster_comparison.pdf` | `results/fig3_roster_comparison.csv` | `phase_c_matrices.npz` | pool and control maps from one sample |
| `fig4_influence.pdf` | `results/fig4_influence.csv` | `phase_c_matrices.npz` | mean |Δ map| and ε-ceiling cost per strategy |
| `fig5_sensitivity.pdf` | `results/fig5_sensitivity.csv` | `roster_analysis.log` | mean |Δ map| 0.177 → 0.037 over sizes 5 → 13 |
| `fig6_phase_b_trajectory.pdf` | `results/fig6_phase_b_trajectory.csv` | `tournament.py` + `evolution.py`, control roster | shares by generation; AllD and Random eliminated |

## Censoring

A ceiling is *censored* when the roster was still cooperating in the
last column of the grid: the measurement ran out before the
phenomenon did, and the value is a lower bound rather than a
location. Figure 5 draws those as open upward triangles, never as
points. `fig5_sensitivity.csv` carries an explicit `*_censored`
column for each ceiling statistic; `fig2_edge_profile.csv` carries
one too, and it is `no` throughout because the pool collapses at
0.30, inside the grid.

## Primary artefacts

- `results/phase_c_grid.csv` — 760 rows, one per (ε, w, replicate) on
  the 15-strategy pool, ε to 0.35. Realised cooperation rate, mean
  payoff, survivors, convergence generation.
- `results/phase_c_matrices.npz` — the payoff and cooperation matrices
  behind that grid. Every sub-roster result is a submatrix of these.
- `results/control7_grid.csv`, `results/control7_matrices.npz` — the
  frozen pre-expansion control, ε to 0.20.
- `results/roster_analysis.log` — the roster sweep's own record.
- `results/phase_c_metadata.json` — seed, roster, payoffs, grid,
  generation limit, library versions.
