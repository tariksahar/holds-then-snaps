# holds-then-snaps

An agent-based study of the Iterated Prisoner's Dilemma, asking **when
cooperation survives and when it collapses**.

Named for the answer. Cooperation does not erode as noise rises: it holds at
0.788 of what the noise allows through an error rate of 28%, and then falls to
0.628 and 0.162 over the next two grid steps. It holds, and then it snaps.

> **Status: all three phases run.** The report is not written yet. This README
> will be rewritten around the result once it is.

## What this is

Three phases:

1. **Tournament** — a round-robin between hand-coded strategies (Tit-for-Tat,
   Grim Trigger, Pavlov, and others), producing a leaderboard and, more
   importantly, the full pairwise payoff matrix.
2. **Evolution** — that matrix drives a population model: strategies that do
   better than average grow their share, generation over generation. Some go
   extinct, some dominate, some coexist.
3. **The experiment** — two dials the textbook version leaves out. Agents
   sometimes make mistakes, and the game is not guaranteed to continue. Sweep
   both and map where cooperation is still viable.

The first two phases reproduce well-established results and exist to earn
trust in the machinery. The third is the point.

## Repo layout

- `docs/brief.md` — full project brief: scope, open questions, what is
  deliberately undecided
- `PROJECT_STATE.md` — current state of every settled decision, shared between
  working sessions
- `decisions.md` — the decision log: what was chosen, why, and what was
  rejected
- `strategies.py` — the strategies and the name-to-strategy registry
- `config.py` — payoffs, roster, rounds, trials, root seed
- `tournament.py` — Phase A: `play_match` and the round robin
- `evolution.py` — Phase B: the replicator dynamics, plus the sensitivity runs
- `initial_conditions.py` — how much of the Phase B result is the starting mix
- `experiments.py` — Phase C: the (ε, w) sweep and the two standing predictions
- `roster_analysis.py` — roster sensitivity and per-strategy influence
- `trim_check.py` — verifies the trimmed roster against the full pool
- `report_data.py` — derives the figure data from `results/`
- `figures.py` — renders the figures from that data
- `figures/` — the figures, plus `MANIFEST.md` saying which file holds which
  numbers
- `report/` — the LaTeX report and its bibliography
- `results/` — the raw sweep data, committed: grid CSV, payoff matrices, metadata
- `watch.py` — a viewing tool: one match, round by round
- `tests/` — the named invariants, plus reproducibility and validation

## Running it

```
python -m pip install -r requirements.txt
python tournament.py     # Phase A: pairwise matrix + leaderboard
python evolution.py      # Phase B: trajectories and parameter sensitivity
python initial_conditions.py   # robustness of Phase B to the starting mix
python experiments.py    # Phase C: the map, plus both predictions tested
python experiments.py --only report   # re-read results/ without re-running
python roster_analysis.py      # roster sensitivity, influence, the ε ceiling
python trim_check.py           # check the recommended roster against the pool
python build_report.py         # data, figures, then the PDF
python build_report.py --figures   # stop after the figures
python -m pytest         # invariants and supporting tests

# optional: cross-check the match engine against the Axelrod library
python -m pip install -r requirements-dev.txt
```

Every number is reproducible from the single root seed in `config.py`.
