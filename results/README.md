# Results

Committed, not gitignored: this is the experimental record the report cites.
Everything here is reproducible from the single root seed in `config.py`, but
being reproducible is not a reason to leave it out — a reader should be able to
check the analysis without re-running a half-hour sweep.

## Two sweeps, and why both are kept

| prefix | roster | what it is |
|---|---|---|
| `control7_` | the original 7 (Phase A/B roster) | **the pre-expansion control**, frozen |
| `phase_c_` | the 15-strategy pool (D-027) | the current sweep |

The control is not superseded output. D-028's central finding — that Grim
Trigger re-emerges at high ε as *a defector wearing a cooperative name* —
was measured on the seven, and the claim is about what that particular cast
does. Keeping the control means the finding stays checkable against the data it
was drawn from, and means the effect of enlarging the roster can be stated as a
difference between two measured maps rather than asserted.

`roster_analysis.py` also re-derives the seven-strategy map from the *pool's*
matrices. That is a third thing again, and the more useful one for comparison:
it holds the sampled matrices fixed, so the difference between the two maps is
the roster and cannot be sampling noise. The frozen `control7_` files are the
historical record; the re-derived map is the controlled comparison.

## Files

- `*_grid.csv` — one row per (ε, w, replicate): survivors, final shares, the
  realised cooperation rate, mean payoff, match length, convergence generation.
- `*_matrices.npz` — the raw payoff matrices, and (Phase C pool only) the
  cooperation-rate matrices. `keys` holds the (ε, w, replicate) coordinates in
  the same order as `matrices`. Every sub-roster result in the analysis is a
  submatrix of these; nothing downstream re-simulates a match.
- `*_metadata.json` — what produced the run: seed, roster, payoffs, grid,
  generation limit, library versions, platform.
- `*_run.log`, `*_predictions.log` — the printed reports, kept so the numbers
  quoted in `decisions.md` can be traced to the run that produced them.
- `phase_a_leaderboard.csv` — the noiseless seven-strategy tournament: the
  leaderboard with Random, the same leaderboard with Random removed, and the
  opponent-by-opponent difference between the Grim Trigger and Tit-for-Tat
  rows. That last column is where the reported 0.7090 comes from: the two
  strategies are identical against every opponent but Random. Produced by
  `python report_data.py --phase-a` (seconds), and by a full
  `python report_data.py` along with everything else.
  Phase A predates the sweep machinery and was previously only ever printed,
  so its numbers were the one part of the report not backed by a file.

The prediction tests (D-020 and D-022) appear only under `control7_`. They were
not re-run on the pool because they do not depend on it: the basin probe puts
weight on Always Cooperate, Always Defect and Tit-for-Tat and zero on every
other strategy, and a zero share never re-enters under replicator dynamics, so
the trajectory is the three-strategy sub-game whatever else is on the roster.

## Reading the cooperation rate

It is the fraction of moves **actually played** as `C`, not a count of shares
held by cooperative-sounding strategies. The difference is the point of D-024:
at ε ≥ 0.16 the name-based measure reports total victory for cooperation in a
population that is 78% defecting.

A cooperation rate equal to ε is the signature of total collapse — everyone
intends to defect, and the only cooperative moves left on the board are
execution errors. Verified across all 215 pure-defector cells of the control
sweep (mean deviation 0.0029, D-028).

## The roster analysis

- `roster_analysis.log` — the pool map, the control-7 map re-derived from the
  same matrices, per-strategy influence, the Contrite TFT comparison, and the
  120-draw sub-roster sensitivity sweep.
- `roster_trimmed.log` — the influence ranking and the trimmed rosters
  (8/10/12) measured against the pool.
- `phase_c_extend.log` — the ε axis extended from 0.20 to 0.35 (D-033, D-034),
  including the integrity check that the 320 new cells were merged into the
  440 existing ones only after the current code reproduced a saved cell bit for
  bit.

**The ε axis runs to 0.35, and it matters that it does.** The grid originally
stopped at 0.20, where the pool was still cooperating at 0.67–0.70 — so every
"ceiling = 0.20" recorded the edge of the ruler rather than a property of the
roster. The pool's actual ceiling is 0.30.

Both are produced from `phase_c_matrices.npz` alone. No match is re-simulated,
which is why every roster in them shares one sample and a difference between
two rosters cannot be sampling noise — see D-027 and D-030.
