# PROJECT_STATE.md — shared state

This file is the single source of truth for this project. Neither chat
transcript is authoritative — this file is.

**Rule: the moment a decision is made in either session, write it here and
append an entry to `decisions.md`. A decision that exists only in a chat does
not exist.**

## Project

Agent-based Iterated Prisoner's Dilemma simulation, in three phases:
round-robin tournament → replicator dynamics → a parameter sweep that is the
actual experiment. Full brief: `docs/brief.md`.

**Guiding question: when does cooperation survive, and when does it collapse?**

The tournament and the evolutionary model are apparatus, not the result. The
result is where the boundary sits and what pushes a population across it.

## Status

- [x] Phase A — round-robin tournament
- [x] Phase B — replicator dynamics
- [x] Phase C — (ε, w) sweep
- [ ] Report
- [ ] Decision log written up
- [ ] Public repo

Phases A, B and C are built, run and tested, and the roster work of D-027 is
complete. Entry points: `python tournament.py`, `python evolution.py`,
`python initial_conditions.py`, `python experiments.py`
(`--only grid|predictions|report`), `python roster_analysis.py`,
`python trim_check.py`, `python -m pytest`.

Next step: **the report**, plus open item 7 (which Phase C layer, if any).
Nothing outstanding from earlier phases.

Two corrections Phase C forced on earlier conclusions, both in the log:
D-024 (cooperation must be measured from moves, not strategy names) and
D-025 (D-015's "the extinction threshold barely matters" is false under
noise). Neither changes the Phase A or B results; both change how they may
be described.

## Settled

- Python, CPU-only. Code and comments in English.
- Payoff ordering `T > R > P > S` with `2R > T + S`. Default T=5, R=3, P=1,
  S=0 — a default to vary, not a constant.
- No magic numbers. Every parameter is configuration.
- RNG: explicit generator objects seeded from one documented root seed. No
  global seeding. Stochastic results always averaged over repeated trials.
- **Repo: `tariksahar/evolutionary-game-sim`, private.** It stays private until
  the report is finished. The name is still provisional — D-004 defers the
  final name until the finding is settled, and renaming on GitHub is cheap and
  redirects old links.
- **Version control starts at the initial commit, which is after the roster
  expansion.** There is therefore no commit containing exactly the code that
  produced the seven-strategy control map. What exists is its *data*, frozen
  under `results/control7_*`, plus the ability to re-derive the seven from the
  current code (`strategies.CONTROL_ROSTER`) — and `roster_analysis.py` does
  exactly that, re-deriving the control map from the pool's own matrices. Do
  not describe the control as having a clean commit of its own; it does not.
- From here on, **commit at the end of every phase.** `decisions.md` records
  what was decided and why; git records what changed and when. The two are not
  substitutes.
- **Authorship: Tarık, alone.**
- Report format: undecided.
- Configuration is `config.py` (frozen `Config` dataclass + `DEFAULT_CONFIG`),
  not YAML — D-006.
- RNG: one generator per match, keyed by `(i, j, trial)` off the root seed, so
  the tournament is order-independent — D-007. Root seed is `20260902`.
- Phase A roster was 7 strategies. **Phase C runs on the 15-strategy pool of
  D-027**; the 7 are kept as `CONTROL_ROSTER` and their sweep is frozen under
  `results/control7_*`. Generous TFT is in the pool at Nowak and Sigmund's
  optimum p = 1/3, with the factory kept for sweeping — D-011, D-029.
- Strategies take a per-match scratch dict as a fourth argument. It is an
  optimisation, never hidden state: everything in it is derived from the
  histories, and `state=None` recomputes the same move — D-029.
- Roster composition is a measured result, not a setting — D-030. Sub-roster
  and influence analyses are read off the saved matrices; nothing is
  re-simulated, so no roster difference can be sampling noise.
- The recommended roster is the 10 most influential, **verified** against the
  pool rather than read off the ranking — D-031. Leave-one-out does not
  compose.
- `trials = 20`, checked against a 500-trial run that moves nothing — D-013.
- The `Axelrod` cross-check is a dev-only dependency, tests `skipif` on
  import — D-012. **Written and passing — D-017:** all 21 deterministic
  pairings agree with the reference implementation *move for move* over 200
  rounds, not merely on score.
- Every reported ranking is shown both with and without Random — D-010.
- Extinction culling is layered on top of the replicator step, never inside
  it — D-014. Invariant 5 is asserted against the pure step.
- `s` and `extinction_threshold` are *still open*, but both have been swept and
  neither moves the result **at ε = 0** — D-015. `config.PROVISIONAL_*` are
  placeholders, not decisions. **Under noise the threshold does matter and the
  fix is not to pick a better one** — Phase C runs with no culling at all and
  applies the cutoff only when reporting, D-025.
- Cooperation is measured from moves played, never from strategy names —
  D-024. A cooperation rate equal to ε means total defection: the only
  cooperative moves left are mistakes.
- Phase C match loop: execution error only; the length cap is derived from w,
  not from N; per-round payoffs are pooled across trials — D-023.
- G = 1000 for simplex sweeps, G = 5000 for basin probes; the equal-shares
  headline run keeps G = 200 — D-018.
- Report the survivor set, never the final proportions — D-019. The
  proportions are a property of the starting mix.

## Phase A result — read before starting Phase B

Grim Trigger tops the leaderboard (2.713) ahead of Tit-for-Tat (2.612), but
the two are **identical against every opponent except Random**. The whole
margin is one column: Grim beats TFT by 0.741 against the coin-flipper and by
exactly 0.000 against the other six. Drop Random and the ranking is a
three-way tie — TFT 2.6658, Grim 2.6658, TF2T 2.6650.

Two things follow, and both matter downstream:

- The tournament "winner" is a roster artifact, not a property of the
  strategy. Open item 5 is therefore already answered in part — concretely,
  on the first run. Do not let the report say "Grim wins" unqualified.
- The near-exact ties are the mechanism behind the ESS warning at the bottom
  of this file. Strategies that tie everywhere drift into each other for
  free. Phase B should be expected to show drift, not a clean winner, and the
  only thing that can separate Grim from TFT is an opponent that defects
  intermittently — which is exactly what the Phase C error rate introduces.

## Phase B result — read before starting Phase C

From equal shares over the full roster: Always Defect is eliminated at
generation 44, Random at generation 59, and the remaining five settle.

| strategy | final share |
|---|---|
| Grim Trigger | 0.2677 |
| Tit-for-Tat | 0.2184 |
| Tit-for-Two-Tats | 0.1934 |
| Pavlov | 0.1869 |
| Always Cooperate | 0.1337 |

**The fitness spread among survivors is exactly zero.** Once no defector is
left, every survivor scores R against every other, so selection has nothing
left to act on and the final proportions are a record of the transient, not an
equilibrium that was selected. This is the ESS caution at the bottom of this
file, demonstrated rather than asserted — D-016. Do not report these five as a
leaderboard; the ordering is an artifact of the race.

Three things to carry into Phase C:

- **Always Cooperate survives at 13%.** It is exploitable by anything that
  defects and survives only because nothing that defects is still alive. The
  clearest available proof that surviving here is not evidence of quality, and
  the most fragile thing in the result. Phase C's ε is exactly the perturbation
  that should break it.
- **Without Random, Grim and Tit-for-Tat finish on exactly equal shares**
  (to 1e-12). D-010 was not only about the tournament: nothing in the model
  can separate those two without an opponent that defects intermittently.
- **The neutral set is where drift lives.** If Phase C is to show an incumbent
  being invaded for free, this mixture is the place it will happen.

## Is the Phase B result real? — open item 4, answered

1000 starting mixes drawn uniformly from the simplex, each run to G = 1000
(`python initial_conditions.py`). D-019.

**The survivor set is a property of the model.** Always Defect and Random are
eliminated in **1000 / 1000** runs; Tit-for-Tat, Grim Trigger, Pavlov and
Tit-for-Two-Tats survive in 1000 / 1000; Always Cooperate in 999 / 1000. Only
two distinct outcomes occur in the whole sweep. Every run ends with a fitness
spread of exactly zero, so the neutral mixture of D-016 is not an artifact of
starting from the centre either.

**The proportions are a property of the starting point.** Grim Trigger finishes
anywhere between 0.0005 and 0.9455 depending only on where the run began; the
equal-shares figure of 0.2677 sits near the median of that range and means
nothing on its own. **The report must state that cooperation wins and that the
survivors are mutually neutral, and must not present the five final shares as a
result.**

**The defection basin is real but narrow.** Always Defect is a strict Nash
equilibrium (1.000 against itself, against Tit-for-Tat's 0.995), so a basin
must exist; uniform sampling never entered it, which bounds its size rather
than its existence. Probed directly: expressed as a share of the whole
population, the Tit-for-Tat needed to save cooperation is roughly constant at
**0.25%–0.38%** across defector shares from 50% to 99%. What defeats defection
is the presence of retaliators, not the number of cooperators.

## Phase C result — the map, and both predictions confirmed

Realised cooperation rate (fraction of moves actually played as C), mean of 5
replicates, from equal shares. Raw data in `results/`. D-026.

| ε \ w | 0.5 | 0.6 | 0.7 | 0.8 | 0.9 | 0.95 | 0.98 | 0.99 |
|---|---|---|---|---|---|---|---|---|
| 0.00 | 0.00 | 0.00 | 1.00 | 1.00 | 1.00 | 1.00 | 1.00 | 1.00 |
| 0.04 | 0.04 | 0.04 | 0.04 | 0.72 | 0.88 | 0.82 | 0.75 | 0.79 |
| 0.08 | 0.08 | 0.08 | 0.08 | 0.48 | 0.80 | 0.78 | 0.73 | 0.71 |
| 0.12 | 0.12 | 0.12 | 0.12 | 0.12 | 0.64 | 0.65 | 0.64 | 0.54 |
| 0.16 | 0.16 | 0.16 | 0.16 | 0.16 | 0.29 | 0.28 | 0.21 | 0.19 |
| 0.20 | 0.20 | 0.20 | 0.19 | 0.20 | 0.20 | 0.22 | 0.22 | 0.22 |

**The boundary is a staircase, not a rectangle.** The two dials trade against
each other, but the trade is bounded:

| ε | lowest w at which cooperation survives |
|---|---|
| 0.00 | 0.7 |
| 0.02 – 0.08 | 0.8 |
| 0.10 – 0.14 | 0.9 |
| ≥ 0.16 | no w rescues it |

More noise demands a longer shadow of the future. Past ε ≈ 0.15 no horizon,
however long, compensates. Where the rate equals ε, everything defects and the
only cooperative moves left are execution errors.

- **Prediction (a), D-020 — HOLDS.** Log-log slope of the retaliator share
  needed against (1−w) is **1.046**, against a derived 1.000; the ratio
  needed/(1−w) varies by a factor of 1.14 across w = 0.9…0.99. Derived from
  the payoff structure before the sweep existed, and the sweep reproduces it.
- **Prediction (b), D-022 — HOLDS, more sharply than stated.** The retaliator
  share needed rises 0.57% → 10.0% (17.6×) over ε = 0…0.08, monotonically, and
  past ε = 0.10 **no** retaliator share defeats a 90% defector majority.
- **The boundary is bistable, not fuzzy.** In 17 cells the cooperation rate
  varies by more than 0.3 across replicates differing only in the tournament
  seed (ε = 0.02, w = 0.8 gives [0.02, 0.93, 0.94, 0.95, 0.98]). Two
  attractors, with the sampled payoff matrix deciding which is reached. Do not
  report a single number for those cells.
- **Caveats to carry into the report.** 21 of 440 runs (4.8%) had not converged
  at G = 60000; they are listed in the output and their map entries are
  provisional. The whole map is from equal shares — open item 4 was answered
  at ε = 0 only.

## Phase C on the 15-strategy pool — the ε ceiling was the cast

`python roster_analysis.py`. Realised cooperation rate, mean of 5 replicates,
from equal shares. D-030 to D-032.

| ε \ w | 0.5 | 0.6 | 0.7 | 0.8 | 0.9 | 0.95 | 0.98 | 0.99 |
|---|---|---|---|---|---|---|---|---|
| 0.00 | 0.00 | 0.54 | 1.00 | 1.00 | 1.00 | 1.00 | 1.00 | 1.00 |
| 0.04 | 0.10 | 0.34 | 0.90 | 0.92 | 0.93 | 0.93 | 0.93 | 0.92 |
| 0.08 | 0.12 | 0.17 | 0.71 | 0.87 | 0.87 | 0.86 | 0.86 | 0.86 |
| 0.12 | 0.16 | 0.16 | 0.19 | 0.79 | 0.81 | 0.80 | 0.80 | 0.80 |
| 0.16 | 0.16 | 0.16 | 0.16 | 0.39 | 0.75 | 0.75 | 0.75 | 0.75 |
| 0.20 | 0.20 | 0.20 | 0.19 | 0.20 | 0.67 | 0.70 | 0.70 | 0.70 |
| 0.24 | 0.24 | 0.24 | 0.24 | 0.24 | 0.24 | 0.42 | 0.66 | 0.66 |
| 0.28 | 0.28 | 0.28 | 0.28 | 0.28 | 0.28 | 0.28 | 0.63 | 0.63 |
| 0.30 | 0.30 | 0.30 | 0.30 | 0.30 | 0.30 | 0.30 | 0.43 | **0.55** |
| 0.32 | 0.32 | 0.32 | 0.32 | 0.32 | 0.32 | 0.33 | 0.33 | 0.38 |
| 0.35 | 0.35 | 0.35 | 0.35 | 0.35 | 0.35 | 0.36 | 0.36 | 0.35 |

**Cooperation holds, and then it snaps.** That shape is the result. Along
w = 0.99, reading the cooperation rate normalised onto the band the error rate
allows, `(rate − ε)/(1 − 2ε)`, where 1 is total cooperation and 0 is total
defection:

| ε | 0.10 | 0.20 | **0.28** | **0.30** | **0.32** | 0.34 |
|---|---|---|---|---|---|---|
| raw rate | 0.829 | 0.701 | 0.627 | 0.551 | 0.378 | 0.343 |
| normalised | 0.911 | 0.836 | **0.788** | **0.628** | **0.162** | 0.008 |

At an error rate of 28% — more than one move in four going astray — the
population is still cooperating at 79% of what the noise permits. Two grid
steps later almost nothing is left. Cooperation does not erode under noise; it
absorbs it, and then it goes all at once.

**Report the edge, not the single number.** "The ceiling is 0.30" is a
convention — the last ε at which the cooperation rate clears an arbitrary
cutoff — and it hides the finding. The three figures around the edge (0.788,
0.628, 0.162) are the measurement; the single number is a summary of them that
throws away the only interesting part. Raw and normalised readings put the edge
in the same place, so the edge itself is a property of the population and not
of where the cutoff was drawn.

The seven re-derived from the same matrices collapse above ε = 0.14. Expanding
the roster moves the map by 0.153 on average and 0.863 at most.

**Where the ceiling came from.** Across 120 random sub-rosters, sensitivity to
composition falls steeply with size — mean |Δ map| against the pool is 0.177 at
size 5, 0.125 at 7, 0.037 at 13 — and this column is the uncensored one, so it
is what the section should lead with. On ceilings: at size 7 the median roster
breaks at 0.26 and the worst at 0.14, which is what our seven scored, the
minimum of 24 draws. They were at the floor, not merely below typical, because
they were chosen for a world without mistakes. The `max` column is still at the
grid edge for sizes 5–11 and is written `≥ 0.35`.

### What survives noise: three mechanisms, and they are not equal

**Dilution wins.** The largest single contributor to how much noise the
population can take is **Soft Majority** — removing it costs 0.10 of the
ceiling, more than any other strategy. It is the only pool member with
unbounded memory: it answers an opponent by what they have done across the
whole history, so one mistaken move barely moves the verdict at all.

The three error-surviving mechanisms in the pool, weakest last:

| mechanism | strategy | what it does with a mistake | ceiling cost if removed |
|---|---|---|---|
| **dilution** | Soft Majority | judges the whole record, so one slip barely registers | **0.10** |
| **contrition** | Contrite TFT | recognises its own error and accepts the punishment | 0.08 |
| **forgiveness** | Generous TFT | ignores a fixed random fraction, without asking whose fault | 0.003 |

In plain language, and this is the form worth keeping: **judging someone by
their record rather than by their last move is the most robust defence against
noise in this model.** Contrition is next — it repairs a mistake, but only
after the mistake has already cost a round. Blind forgiveness is worth almost
nothing, because it discards information instead of using it.

**Contrite TFT is load-bearing — the correction to D-032.** Adding it alone to
the original seven lifts the ceiling 0.14 → 0.18 with nothing about the noise
changed, and removing it from the pool costs 0.30 → 0.22:

| roster | ε ceiling |
|---|---|
| control 7 | 0.14 |
| control 7 + Contrite TFT | **0.18** |
| pool 15 − Contrite TFT | **0.22** |
| pool 15 | **0.30** |

D-032 read it as "sufficient but not necessary" because the pool with and
without it both showed 0.20 — two numbers pinned at the edge of the old grid,
neither of them a measurement. That is the correction; Soft Majority beating it
is the finding.

**Always Defect gets its own line.** It moves the *map* more than any other
strategy (Δ 0.098) and moves the *ceiling* not at all. The antagonist shapes
the landscape without setting its limit — how much noise cooperation can
survive is decided by the cooperators' machinery, not by the defector's
presence.

Ranking by map shift is not ranking by importance to the ceiling.

**Recommended roster: the 10 most influential** — Always Defect, Contrite TFT,
Soft Majority, Suspicious TFT, Alternator, Tit-for-Tat, Grim Trigger,
Two-Tits-for-Tat, Pavlov, Prober. (Membership changed on the extended grid:
Prober in, Random out.) Verified against the pool: Δ map 0.029, 9 of 152 cells
flip, ceiling unchanged at 0.30. **Trimming to ten changes the map less than
changing the random seed does** — D-029 measured seed noise at up to 0.054.
Twelve is materially cleaner (Δ 0.0145, 4 cells) and is the conservative
choice. Dropped with reasons in D-031, revised in D-034.

**The trim is for Phase C only. Do not apply it backwards.** It drops Always
Cooperate and Tit-for-Two-Tats, both members of the seven on which Phases A and
B were computed — and D-016's "Always Cooperate survives at 13%" is a fact
about that roster, not a claim the trim retracts. Which result belongs to which
roster is tabulated in D-031, and the report must carry that table rather than
let a reader assume one cast from start to finish.

## Open — decide with code in front of us, not in advance

Each becomes a `decisions.md` entry once resolved.

1. ~~**Phase A → B handoff.**~~ **Settled — D-008.** `run_round_robin`
   returns `M[i, j]` = mean per-round payoff to `i` against `j`, self-play on
   the diagonal, averaged over `trials`. The leaderboard is the row mean of
   that same matrix. The diagonal is asserted against a direct self-play match
   in `tests/test_invariants.py`.
2. **Selection intensity.** *Implemented and swept, value still unchosen —
   D-015.* `fitness = (1−s) + s · payoff` is in `evolution.py`; s is a
   parameter with no baked-in default. Swept over 0.1/0.5/1.0: identical
   survivor set, final shares differ by 1.9e-03, time to settle differs by
   about 4x (190/59/42 generations). **s sets the pace, not the destination.**
   Pick it for the timescale wanted.
3. **Extinction threshold.** *Implemented and swept, value still unchosen —
   D-015.* Swept over 1e-3 to 0: identical survivor set for every non-zero
   cutoff, final shares differ by 2.8e-04. At exactly 0 nothing is ever
   declared extinct and the run reports 7 survivors while holding Always
   Defect at 5e-28 — so *some* cutoff is needed and *which* one barely
   matters.
4. ~~**Initial conditions.**~~ **Settled — D-019.** 1000 uniform draws from
   the simplex. The survivor set is the model's; the proportions are the
   starting point's. See the section above.
5. ~~**Roster sensitivity.**~~ **Settled — D-030, D-031.** 120 random
   sub-rosters at five sizes, plus a leave-one-out influence measurement for
   all fifteen. Composition matters most when the roster is small (mean |Δ map|
   0.203 at size 5, 0.045 at size 13), the median ε ceiling is 0.20 at every
   size, and the original seven sat at the size-7 minimum. Recommended roster
   is the 10 most influential, measured rather than asserted.
6. ~~**N and G.**~~ **Settled — D-018.** N = 200 rounds. G = 200 for the
   equal-shares run (settles at 59), G = 1000 for simplex sweeps (20 of 1000
   random starts had not converged at 200; at 1000 none remain, and the result
   matches a 5000-generation run), G = 5000 for basin probes, which start near
   an unstable fixed point and move slowly by design.
7. **Which Phase C layer.** Three candidates in `docs/brief.md`. Pick one
   (maybe two) after the basic sweep runs. Do not start all three.

~~**New, for Phase C — D-020.**~~ **Tested and confirmed — D-026.** The
derived `1/N` scaling predicted that cooperation's basin would shrink like
`(1 − w)`. Measured log-log slope: 1.046 against a predicted 1.000.

**New, for the report and for open item 7.** Three things Phase C leaves open:

- **Initial conditions under noise.** Open item 4 was settled at ε = 0 only.
  The Phase C map is entirely from equal shares, and D-026's bistable cells
  are exactly where a different start would be expected to matter most.
- **G is marginal.** 21 of 440 runs had not converged at G = 60000 and the
  slowest converged run settles at 59896. Raising G is cheap; deciding
  whether the provisional cells change anything is not yet done.
- **Which layer.** D-022's mechanism — retaliators must recognise each other —
  is what ε breaks, and open exploration 2 (a forgiveness family swept over p)
  addresses exactly that. It is the layer the results point at. Generous
  Tit-for-Tat was deferred to Phase C for this purpose in D-011.

## Invariants the tests must assert

- `TFT vs TFT` over N rounds = `N · R`
- `Grim vs AllD` = `S + (N−1) · P`
- Pairwise payoff matrix consistent under player swap
- Population shares sum to 1 every generation *(asserted across 3 values of s
  x 4 thresholds x 11 starting mixes)*
- A strategy with above-average fitness strictly gains share *(asserted against
  the pure replicator step; the converse is asserted too, so the test cannot
  pass on an implementation that grows everybody)*

Cross-check a few matchups against the `Axelrod` Python library. Keep our own
implementation; the point is to write it. Agreement with a reference
implementation is cheap credibility for the report.

## Watch out

Do not claim the tournament winner is an evolutionarily stable strategy. In
the repeated Prisoner's Dilemma no pure strategy is evolutionarily stable: a
strategy that merely ties with the incumbent drifts in for free, and once
common enough the incumbent becomes invadable. If the model can be made to
show this, show it — it is a better result than the leaderboard.
