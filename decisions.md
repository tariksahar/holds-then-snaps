# Decision log

Append-only record of methodological choices. One entry per decision, newest
at the bottom. Every entry states what was decided, why, and what was
rejected — the rejected option is usually the more interesting half.

Written from both sessions, build and methodology. Nothing is decided
until it appears here.

---

### D-001 — The project is organised around a question, not a demo

**Date:** 2026-09-01
**Decided:** The build is framed around "when does cooperation survive, and
when does it collapse?" rather than "implement a tournament and an
evolutionary model".

**Why:** A round-robin tournament plus replicator dynamics reproduces results
that have been known since 1984. Reproducing them is a reasonable exercise but
not a finding. Framing the work around a boundary — where cooperation is
viable and where it is not — turns the same code into an experiment with an
answer.

**Rejected:** The original v1 scope, which specified the apparatus and left
the question implicit.

---

### D-002 — Two parameters added that the original scope did not have

**Date:** 2026-09-01
**Decided:** An error rate (ε: agents sometimes play a move they did not
intend) and a continuation probability (w: each round continues with
probability w, instead of a fixed publicly known N).

**Why:** Without ε, several strategies are behaviourally indistinguishable and
the model is far more forgiving than any real interaction. Without w, the
fixed known horizon makes defection the backward-induction solution, which
quietly undercuts the premise of the whole simulation. Both are a few lines in
the match loop and both are prerequisites for Phase C.

**Rejected:** Keeping a fixed N for simplicity. The simplicity is not worth a
model whose central assumption is unsound.

---

### D-003 — Payoff values: T=5, R=3, P=1, S=0 as default, not as constant

**Date:** 2026-09-01
**Decided:** Axelrod's canonical set as the default, with the payoff matrix
remaining a configurable parameter and at least one alternative set run as a
sensitivity check.

**Why:** It is the set the literature is written against, so results are
directly comparable. It satisfies both required conditions — `T > R > P > S`
and `2R > T + S` — though the second only narrowly (6 > 5), which makes it a
useful place to probe: pushing T to 6 breaks the condition and changes the
character of the game.

Keeping S = 0 rather than moving to a donation-game parametrisation is also
deliberate: the replicator update `x_i · f_i / f̄` is not defined in any
sensible way on negative payoffs.

**Rejected:** Hard-coding the values, and the (b, c) donation-game form.

---

### D-004 — Repo name deferred

**Date:** 2026-09-01
**Decided:** No repo name until Phase C results exist. Working folder name is
`evolutionary-game-sim`, explicitly provisional.

**Why:** Prior projects in this series are named after their finding. Naming
before the finding exists risks bending the analysis to fit the title.
Renaming a GitHub repo later is cheap and redirects old links.

---

### D-005 — Working method: the repository is the source of truth

**Date:** 2026-09-01
**Decided:** The build session does the building; the methodology session
does literature, method, report and this log. `PROJECT_STATE.md` holds
current state and is read by both.
Sessions run sequentially on a given topic, never in parallel on the same one.

**Why:** Two sessions with separate context drift apart within a day. Routing
every decision through one file in the repo is the only mechanism that keeps
them aligned — and that file is a deliverable anyway, so the coordination
overhead is zero.

**Rejected:** Keeping state in the chat transcripts.

---

### D-006 — Configuration is a Python module, not YAML

**Date:** 2026-09-02
**Decided:** `config.py`, holding a frozen `Config` dataclass plus
`DEFAULT_CONFIG`, rather than `config.yaml`.

**Why:** The payoff constraints (`T > R > P > S`, `2R > T + S`, `S >= 0`) and
the roster-against-registry check are validation, and validation wants to live
next to the values it guards. A dataclass gets that plus a `with_()` helper for
sweeps — Phase C is a sweep, so building configs programmatically is the normal
case, not the exception. It also avoids a fourth dependency.

**Rejected:** YAML. The argument for it is editability by a non-programmer,
which is not a constraint this project has.

---

### D-007 — RNG streams are keyed by match coordinates, not drawn in sequence

**Date:** 2026-09-02
**Decided:** Each match gets `default_rng(SeedSequence(root_seed,
spawn_key=(i, j, trial)))` — a stream addressed by where the match sits in the
tournament, rather than the next stream off a running generator.

**Why:** A running stream makes every result depend on how many matches were
played before it, so adding a strategy to the roster silently changes numbers
elsewhere and no single cell can be reproduced in isolation. Coordinate keying
makes the tournament order-independent and lets any one matchup be re-run and
inspected on its own. Within a match, the two players draw from independent
substreams (`rng.spawn(2)`), so a stochastic strategy in self-play does not
mirror its own moves.

**Rejected:** One global generator threaded through the tournament loop.

---

### D-008 — Phase A outputs a per-round average payoff matrix; one match fills both cells

**Date:** 2026-09-02
**Decided:** `run_round_robin` returns `M[i, j]` = mean payoff *per round* to
strategy `i` against `j`, self-play on the diagonal, averaged over `trials`.
Each unordered pair is played once and fills both `M[i, j]` and `M[j, i]`. The
diagonal averages the two sides of the self-play match. The leaderboard is
computed as the row mean of that matrix, so it cannot drift away from it.

**Why:** This settles open item 1, the flagged highest-risk item. Per-round
rather than per-match means fitness does not scale with `N`, so changing the
round count does not change the speed of the Phase B dynamics. Self-play on the
diagonal is required: a population model needs the payoff a strategy earns when
it meets a copy of itself. Filling both cells from one match makes the matrix
consistent under player swap by construction rather than by coincidence — the
swap invariant is still tested, but against `play_match` directly, where it can
actually fail.

**Rejected:** Reporting match totals and dividing later (invites an off-by-N
that would be invisible), and computing the leaderboard from a separate tally
(two sources of truth for one number).

---

### D-009 — Invariants 4 and 5 are staged as skipped tests, not omitted

**Date:** 2026-09-02
**Decided:** `tests/test_invariants.py` contains all five named invariants.
The two that concern the replicator dynamics — shares summing to 1, and
above-average fitness strictly gaining share — are present with their
reasoning written out and marked `skip` pending Phase B.

**Why:** A test list that silently contains three of five items reads as
complete. A skipped test with a stated reason reports the gap on every run.

**Rejected:** Leaving them out until `evolution.py` exists.

---

### D-010 — The leaderboard is reported with and without Random

> **Corrected 2026-09-04.** This entry quoted two different runs in a single
> sentence. The leaderboard values below — 2.713 and 2.612 — are from the
> default 20-trial tournament. The column difference, originally given as
> 0.7409, and the 0.1058 gap derived from it, are from a 500-trial run. Each
> pair is internally consistent on its own: at 500 trials the leaderboard reads
> 2.7115 against 2.6056, a gap of 0.1058, and 0.7409 / 7 = 0.1058; at 20 trials
> it reads 2.7130 against 2.6117, a gap of 0.1013, and 0.7090 / 7 = 0.1013.
> Quoted together they were arithmetic that did not close. The table and the
> sentence now use the 20-trial figures throughout: **0.7090** and **0.1013**.
>
> Nothing about the ordering or the finding moves. Grim Trigger and Tit-for-Tat
> remain identical against every opponent that is not a coin flip, the entire
> leaderboard margin remains that one column, and removing Random still
> collapses the ranking into a tie. Only the magnitude changes — and only
> because the magnitude was being read off a different run from the one the
> rest of the sentence described.

**Date:** 2026-09-02
**Decided:** Random stays in the roster, but every reported ranking is shown
both with and without it, and the report states plainly that the tournament
winner changes depending on which version you look at.

**Why:** Grim Trigger tops the Phase A leaderboard at 2.713 against
Tit-for-Tat's 2.612. Subtracting the two strategies' rows opponent by opponent
shows where that margin comes from:

| opponent | Grim − TFT |
|---|---|
| Always Cooperate | +0.0000 |
| Always Defect | +0.0000 |
| Tit-for-Tat | +0.0000 |
| Grim Trigger | +0.0000 |
| **Random** | **+0.7090** |
| Pavlov | +0.0000 |
| Tit-for-Two-Tats | +0.0000 |

The two strategies are *identical* against every opponent that is not a coin
flip. The entire 0.1013 leaderboard gap is one column divided by seven
(0.7090 / 7 = 0.1013). Grim's advantage is that Random defects early, which
trips Grim's trigger and licenses it to harvest 0.5·T + 0.5·P ≈ 3.0 for the
remaining rounds, while Tit-for-Tat keeps mirroring the coin and averages 2.25.

Removing Random from the roster collapses the ranking into a three-way tie:
Tit-for-Tat 2.6658, Grim Trigger 2.6658, Tit-for-Two-Tats 2.6650.

Reporting only the headline "Grim wins" would therefore be reporting an
artifact of roster composition, not a property of the strategy. This is open
item 5 answered concretely rather than in principle, and it arrived on the
first run.

Two consequences worth carrying forward. First, the near-exact ties are
themselves the mechanism behind the ESS caution in this file: strategies that
tie everywhere are free to drift into each other's populations. Second, Grim
and Tit-for-Tat can only be separated by an opponent that defects
intermittently — which is exactly what the Phase C error rate introduces. The
question "what actually distinguishes these two" is Phase C's to answer.

**Rejected:** Dropping Random (it is a standard baseline and its distorting
effect is itself a finding), and reporting the single leaderboard without
qualification.

---

### D-011 — Generous Tit-for-Tat enters at Phase C as a family, not now as a fixture

**Date:** 2026-09-02
**Decided:** GTFT is not added to the Phase A roster. It enters in Phase C as
`generous_tft(p)`, swept over forgiveness probability p.

**Why:** A fixed GTFT needs a hard-coded forgiveness probability, which is the
magic number the project has ruled out. It also adds nothing in a noiseless
tournament: with no errors, every defection it forgives was deliberate, so it
is strictly worse than Tit-for-Tat against Always Defect and identical to it
everywhere else — a dominated row in the matrix. Forgiveness only starts paying
once mistakes exist, which is Phase C.

**Rejected:** Adding it now with p fixed at some conventional value.

---

### D-012 — Axelrod library cross-check is a development-only dependency

**Date:** 2026-09-02
**Decided:** `requirements-dev.txt` carries the `Axelrod` package; the
comparison tests are marked `skipif` on import so the main suite runs without
it.

**Why:** Agreement with an established reference implementation is worth
stating in the report and costs one optional dependency. Making it optional
keeps the runtime requirements at three packages and means the repo still
installs and tests cleanly for anyone who does not want it.

---

### D-013 — Twenty trials per matchup, verified rather than assumed

**Date:** 2026-09-02
**Decided:** `trials = 20`.

**Why:** Re-running the full tournament at 500 trials moves no leaderboard
position and shifts every score by less than 0.01 (Grim 2.7130 → 2.7115, TFT
2.6117 → 2.6056). Only matchups involving Random carry any variance at all;
the other 36 cells are deterministic and identical across trials. Twenty is
therefore not a guess — it is a number checked against a run twenty-five times
larger.

**Rejected:** The 50 originally specified, which the check shows buys nothing,
and a single run, which would leave the Random column unquantified.

---

### D-014 — Extinction is layered on top of the replicator step, never inside it

**Date:** 2026-09-02
**Decided:** `replicator_step()` implements the pure dynamics and never sends a
positive share to zero. `apply_extinction()` is a separate function, applied
after each step by `run_replicator()`. Invariant 5 is asserted against the
step, not against a full run.

**Why:** The replicator equation drives shares towards zero asymptotically and
never reaches it, so zeroing a share is a numerical and reporting convention,
not part of the model. Fusing the two would make the code unable to state which
of its behaviours are the mathematics and which are the cutoff.

It also matters for what can honestly be tested. Invariant 5 — a strategy with
above-average fitness strictly gains share — is *false* for the dynamics plus
the cutoff: a strategy can be beating the population mean and still be culled,
if its share happens to sit below the threshold while it is winning. Asserting
the invariant end-to-end would therefore be asserting something untrue, and the
only ways to make it pass would be to weaken it into vacuity or to quietly
exempt the cutoff. Keeping them apart lets the invariant be asserted at full
strength where it holds, and the exception is itself pinned by a test
(`test_extinction_culling_can_override_invariant_5`) so the report can state
the limitation rather than trip over it.

**Rejected:** Culling inside the step, which is the shorter implementation and
would have quietly weakened the strongest invariant in the suite.

---

### D-015 — s and the extinction threshold stay open, but they are now measured

**Date:** 2026-09-02
**Decided:** No value is chosen for either. Both remain parameters with no
default baked into the maths; `config.PROVISIONAL_*` values exist only to make
runs comparable and are labelled as placeholders. What is settled is the
evidence, printed by `python evolution.py`.

**Selection intensity s**, swept over 0.1 / 0.5 / 1.0 with everything else
fixed:

| | s=0.1 | s=0.5 | s=1.0 |
|---|---|---|---|
| survivors | 5 | 5 | 5 |
| settles at generation | 190 | 59 | 42 |
| largest share disagreement | — | — | 1.9e-03 |

s sets the pace, not the destination. Across an order of magnitude it changes
the time to settle by a factor of about four and the mixture it settles on by
less than a fifth of a percentage point, with an identical survivor set. The
one value that behaves differently is s = 0, where every fitness is 1 and the
population is frozen; that is the degenerate case, and it has its own test.

**Extinction threshold**, swept over 1e-3 / 1e-4 / 1e-6 / 1e-9 / 0:

| | 1e-3 | 1e-4 | 1e-6 | 1e-9 | 0 |
|---|---|---|---|---|---|
| survivors | 5 | 5 | 5 | 5 | 7 |
| settles at generation | 27 | 38 | 59 | 90 | 114 |
| largest share disagreement (non-zero thresholds) | | | 2.8e-04 | | |

A share only ever falls below the threshold on its way to zero, so the cutoff
cannot change *which* strategies are dying — only when they stop being counted.
Culling earlier does perturb the final mixture, because a defector on its way
out is still being paid by the cooperators it has not finished eating, but over
six orders of magnitude that perturbation stays in the fourth decimal place.

The t = 0 column is the control and shows why some cutoff is needed: with no
threshold nothing is ever declared extinct, so the run reports seven survivors
while holding Always Defect at 5e-28 and Random at 3e-20. The apparently
non-zero fitness spread in that column is the same artifact — it is measuring
strategies that are extinct in everything but the bookkeeping.

**What this implies, for whoever picks the values:** neither parameter is load
bearing for any result reported so far, which is the useful finding. Choose s
for the timescale wanted and the threshold for legibility, and say in the
report that both were swept and neither moved the answer. The caveat is that
this is measured at one starting point — equal shares — and open item 4 is
still open.

**Rejected:** Picking a value now and justifying it afterwards. The sweep costs
seconds and turns a defensible guess into a measurement.

---

### D-016 — Phase B result: a neutral cooperative mixture, not a winner

**Date:** 2026-09-02
**Decided:** Recorded as the Phase B finding, and as the concrete form of the
ESS caution that has been carried in PROJECT_STATE.md since the brief.

From equal shares over the full seven-strategy roster, Always Defect is
eliminated at generation 44 and Random at generation 59. The five remaining
strategies settle and stop moving:

| strategy | final share |
|---|---|
| Grim Trigger | 0.2677 |
| Tit-for-Tat | 0.2184 |
| Tit-for-Two-Tats | 0.1934 |
| Pavlov | 0.1869 |
| Always Cooperate | 0.1337 |

**The fitness spread among the survivors is exactly zero.** Once the defectors
are gone, every surviving strategy scores R against every other, so all five
have identical fitness and selection has nothing left to act on. The final
composition is not an equilibrium selection has chosen — it is wherever the
population happened to be standing when the last defector died. Run the same
model at a different s and the proportions shift slightly for exactly this
reason: they are a record of the race, not a solution to it.

This is the ESS point made concrete rather than asserted. No strategy wins;
a neutral set coexists, and within that set drift is free. It is also why
**Always Cooperate survives at 13%** — a fact worth stating plainly in the
report, because it is the clearest possible demonstration that survival here is
not evidence of a strategy's quality. Always Cooperate is exploitable by
anything that defects; it survives only because nothing that defects is left
alive. That is a fragile equilibrium, and Phase C's error rate is precisely the
perturbation that should break it.

Removing Random (run c) sharpens D-010: Grim Trigger and Tit-for-Tat finish on
*exactly* equal shares, to 1e-12. Without a coin flipper to separate them they
are the same strategy as far as the model can tell — in the tournament and in
the evolution alike.

**Rejected:** Reporting the final ranking as a leaderboard. The ordering of the
five survivors is an artifact of the transient, and presenting it as a result
would repeat the D-010 mistake one phase later.

---

### D-017 — Axelrod cross-check written, and it agrees move for move

**Date:** 2026-09-02
**Decided:** D-012 implemented. `requirements-dev.txt` pins `axelrod==4.14.0`
on top of `requirements.txt`; `tests/test_axelrod_crosscheck.py` skips the
whole module via `importorskip` when the package is absent.

**Result:** all 21 unordered pairings of the six deterministic strategies agree
with the reference implementation **move for move over 200 rounds**, not merely
on the final score. The two named match invariants were re-checked inside the
reference implementation as well, so `TFT vs TFT = N·R` and
`Grim vs AllD = S + (N−1)·P` are not artifacts of our own code.

Mapping used: Always Cooperate→`Cooperator`, Always Defect→`Defector`,
Tit-for-Tat→`TitForTat`, Grim Trigger→`Grudger`, Pavlov→`WinStayLoseShift`,
Tit-for-Two-Tats→`TitFor2Tats`. A test asserts every mapped reference strategy
is classified non-stochastic, so the move-by-move comparison cannot silently
become invalid if the library changes.

Random is excluded. Two stochastic strategies cannot agree move for move across
independent RNG streams, and comparing their distributions would test the
random number generators rather than the match engine.

**Why the comparison is move-by-move rather than score-only:** two
implementations can reach the same total by different routes, so comparing
scores alone would let any payoff-neutral behavioural difference through.

**Vindicating D-012's dev-only call:** installing `axelrod` pulls in torch,
scipy, dask, sympy and networkx. Keeping it out of `requirements.txt` was
right, and by a wider margin than expected.

---

### D-018 — G raised from 200 to 1000 for simplex sweeps

**Date:** 2026-09-02
**Decided:** `config.SWEEP_GENERATIONS = 1000`. The equal-shares headline run
in `evolution.py` keeps G = 200, which is ample for it (it settles at 59).

**Why:** This is open item 6, answered by the thing it was waiting for. Of 1000
uniformly drawn starting mixes, 20 had not converged at G = 200 and produced
five apparent "outcomes" that were really just unfinished runs. At G = 1000
every run converges, and the result is identical to a G = 5000 run — so 1000 is
sufficient, not merely larger.

The corner probe uses G = 5000 (`config.PROBE_GENERATIONS`) for a separate
reason: trajectories deliberately started near a basin boundary begin close to
an unstable fixed point and move slowly by construction. The measured boundary
shifts between G = 1000 and G = 5000 (96.97% → 97.24%) and is unchanged at
G = 20000.

**Rejected:** Reading the G = 200 sweep at face value. It would have reported
five distinct outcomes where there are two, and the extra three would have been
written up as roster-dependent basins.

---

### D-019 — Open item 4 answered: the survivor set is the model, the proportions are the starting point

**Date:** 2026-09-02
**Decided:** Closed. 1000 starting mixes drawn uniformly from the simplex
(symmetric Dirichlet with all concentrations 1 — the actual uniform
distribution, not the draw-and-normalise construction, which concentrates near
the centre), each run to G = 1000. Reproduced by `python initial_conditions.py`.

**The survivor set is a property of the model.**

| strategy | survives in |
|---|---|
| Tit-for-Tat, Grim Trigger, Pavlov, Tit-for-Two-Tats | 1000 / 1000 |
| Always Cooperate | 999 / 1000 |
| **Always Defect** | **0 / 1000** |
| **Random** | **0 / 1000** |

Only two distinct outcomes occur in 1000 draws: the equal-shares survivor set
(999) and the same set minus Always Cooperate (1). The single exception started
from 51% Always Defect with only 0.9% of the population in retaliators, and
Always Cooperate was eaten before the defectors died. Every run ends with a
fitness spread of exactly zero among survivors, so the neutral-mixture result of
D-016 is not an artifact of the equal-shares start either.

**The proportions are a property of the starting point, and almost entirely so.**

| strategy | p0 | p50 | p100 | equal-shares |
|---|---|---|---|---|
| Grim Trigger | 0.0005 | 0.2519 | 0.9455 | 0.2677 |
| Tit-for-Tat | 0.0004 | 0.2086 | 0.8562 | 0.2184 |
| Tit-for-Two-Tats | 0.0002 | 0.1649 | 0.7518 | 0.1934 |
| Pavlov | 0.0001 | 0.1516 | 0.7981 | 0.1869 |
| Always Cooperate | 0.0000 | 0.0757 | 0.4373 | 0.1337 |

Grim Trigger finishes anywhere from 0.05% to 94.6% of the population depending
only on where the run began. The equal-shares figures sit near the median but
are one draw from that range, not a fixed point. **Consequence for the report:
state that cooperation wins and that the survivors are mutually neutral; do not
present the five final shares as a result.** They are a record of the transient.

**The defection basin is real, and narrow.** Always Defect scores 1.000 against
itself where Tit-for-Tat scores 0.995, so it is a strict Nash equilibrium and a
basin must exist on theoretical grounds. Uniform sampling entered it zero times
in 1000 draws, which bounds its size without addressing its existence — so it
was probed directly, holding Always Defect fixed and splitting the remainder
between Always Cooperate and Tit-for-Tat:

| Always Defect share | Always Defect wins once the minority is at least | equivalently, Tit-for-Tat below this share of the whole population |
|---|---|---|
| 0.50 | 99.2% AllC | 0.38% |
| 0.80 | 98.5% AllC | 0.30% |
| 0.90 | 97.2% AllC | 0.28% |
| 0.95 | 94.7% AllC | 0.26% |
| 0.99 | 74.6% AllC | 0.25% |

The right-hand column is the finding: expressed as a fraction of the whole
population, the retaliator share needed to save cooperation is roughly constant
at a quarter to four tenths of a percent, across defector shares from 50% to
99%. What defeats defection is not the number of cooperators but the presence
of retaliators, and how much retaliator is required barely depends on how
dominant the defectors are. A population that is 99% Always Defect still turns
cooperative given 0.25% Tit-for-Tat.

Scope caveat, stated because it would be easy to overclaim: the probe holds the
minority to Always Cooperate and Tit-for-Tat only. It establishes that the
basin is real and narrow along that axis. It is not a measurement of the
basin's volume, which would need a sweep over the whole boundary.

**Rejected:** Reporting the equal-shares run alone. It would have been correct
about who survives and badly misleading about by how much.

---

### D-020 — The defection basin scales as 1/N, which hands Phase C its mechanism

**Date:** 2026-09-02
**Decided:** Recorded now, acted on in Phase C.

Found while fixing a test that failed only because it used the reduced
50-round tournament matrix. The size of the defection basin depends on the
round count. Holding Always Defect at 0.90 and measuring the retaliator share
needed to save cooperation:

| rounds | AllD vs TFT | Tit-for-Tat needed |
|---|---|---|
| 10 | 1.4000 | 6.11% |
| 25 | 1.1600 | 2.29% |
| 50 | 1.0800 | 1.12% |
| 100 | 1.0400 | 0.56% |
| 200 | 1.0200 | 0.28% |
| 400 | 1.0100 | 0.14% |

Double the rounds, halve the retaliator share required. The mechanism is
visible in the middle column: Always Defect's whole advantage over Tit-for-Tat
is the single round of exploitation before retaliation begins, worth `T − P`
once and amortised over N rounds, so the advantage is `(T − P)/N = 4/N` and the
invasion barrier scales with it.

**Why this matters more than it looks:** Phase C's continuation probability w
*is* the round count, in expectation — a match lasts `1/(1 − w)` rounds. So this
is the (ε, w) map's w axis appearing a phase early, derived rather than swept,
and it predicts the shape of the answer: cooperation's basin should shrink
roughly like `(1 − w)` as w falls. Phase C should check that prediction
explicitly rather than only reporting the map — a swept result that matches a
derived one is worth considerably more than either alone.

This also explains the backward-induction concern in the brief from the other
direction. A short known horizon does not merely make defection rational in
theory; it measurably widens defection's basin in the dynamics.

---

### D-021 — Payoff level is a free choice; S = 0 is kept for the replicator's sake, not the game's

**Date:** 2026-09-02
**Decided:** Keep `S = 0` and, with it, non-negative payoffs throughout.
Document why, because the obvious alternative — making the sucker payoff
negative, as the donation-game parametrisation does — is a reasonable thing to
expect and the reason to decline it is not the one a reader would guess.

**Why:** Adding a constant to all four payoffs changes nothing about the game.
The ordering `T > R > P > S` and the condition `2R > T + S` are preserved, so
every best response, every exploitation, every matchup outcome is identical.
Measured across four levels of the same game, the tournament ranking is
unchanged in all of them:

| payoffs | ranking | Always Defect extinct | Random extinct |
|---|---|---|---|
| T=5 R=3 P=1 S=0 (ours) | unchanged | gen 44 | gen 59 |
| T=4 R=2 P=0 S=-1 | unchanged | gen 31 | gen 42 |
| T=6 R=4 P=2 S=1 | unchanged | gen 56 | gen 75 |
| T=105 R=103 P=101 S=100 | unchanged | never | never |

What the level *does* change is the speed of the replicator dynamics, and
dramatically. The discrete update is a ratio, `f_i / f̄`; inflating every payoff
by a constant pushes that ratio toward 1 and selection stalls. In the last row
nothing goes extinct in 200 generations — same game, no evolution. This is the
concrete justification for having a selection-intensity parameter at all: it
makes the timescale an explicit choice instead of an accident of how the payoff
numbers happen to be written.

The objection to negative payoffs is narrower than "the formula breaks". With
`fitness = (1 − s) + s · payoff`, the `(1 − s)` term is a cushion that can hold
a negative payoff above zero, so negatives are workable at low selection
intensity. They are not *guaranteed* workable, and the failure is silent.
Measured in the `S = -1` world, from an ordinary population state (mostly
Always Defect):

- at `s = 0.5`, minimum fitness is `+0.165` and the step is fine;
- at `s = 1.0`, minimum fitness is `-0.670` and the update assigns negative
  population shares to Always Cooperate (`-0.1009`), Random (`-0.0417`) and
  Pavlov (`-0.0326`).

A negative share is not a small numerical error, it is a meaningless quantity,
and whether it occurs depends on the population mix, which changes every
generation. Keeping `S >= 0` makes the guarantee unconditional rather than
conditional on a bound that would have to be re-checked at every step.

The deeper point belongs in the report: this model has no break-even line.
Nothing here is profit or loss. A strategy dies by falling below the
*population average*, not below zero, so moving the sucker payoff to a negative
number adds none of the moral weight it appears to — it relabels the axis. The
punishment for being exploited is already present as "earns less than
everyone else".

**Rejected:** The donation-game form (`T=b, R=b−c, P=0, S=−c`), which is the
cleaner parametrisation if one wants to talk explicitly about the cost of
cooperating and the benefit conferred, and would be the right choice if the
project moved toward a kin-selection or Hamilton's-rule framing. It is not
rejected as wrong, only as unnecessary here and less safe under the update rule
we use. If the report wants it, it belongs as a sensitivity appendix with `s`
bounded and the minimum fitness asserted positive at every step.

---

### D-022 — Naive cooperators raise the bar for cooperation; retaliators are what defeat defection

**Date:** 2026-09-02
**Decided:** Recorded as a sharpening of D-019, and as a headline claim the
report should carry.

Verifying D-019's defection-corner probe independently reproduced its numbers,
including the 1/N scaling of D-020 (Tit-for-Tat needed × N ≈ 0.50 across
N = 10 to 400) and Always Defect's strict-Nash status (1.000 against itself
versus Tit-for-Tat's 0.995). One test appeared to contradict the log —
0.25% Tit-for-Tat against 99% Always Defect left defection in control — until
bisection put the true boundary at 0.254%. The probe was landing a thousandth
of a percent on the wrong side of it. The logged figure is right; it is simply
sharper than "about a quarter of a percent" suggests.

Running the boundary against populations D-019 did not compare gives the
result worth reporting. Minimum Tit-for-Tat share for cooperation to win, at
N = 200:

| population | Tit-for-Tat needed |
|---|---|
| 99.75% Always Defect, no naive cooperators | **0.252%** |
| 80% Always Defect, 20% Always Cooperate | 0.302% |
| 50% Always Defect, 50% Always Cooperate | **0.377%** |

A population that is half cooperators already needs *more* retaliators to save
cooperation than a population that is essentially all defectors. Naive
cooperation does not help the cooperative cause; it is a subsidy to defection.
Every Always Cooperate in the mix pays a defector T = 5 per round, while a
Tit-for-Tat pays it P = 1 after the first round. Cooperators feed defectors;
retaliators starve them.

The claim to make, then, is not "cooperation needs a critical mass". It is
narrower and stronger: **what defeats defection is the presence of retaliation,
not the amount of cooperation** — and a quarter of one percent of it is enough,
because retaliators do well against each other while defectors do badly against
each other.

This is also the mechanism Phase C should be expected to attack. The whole
argument rests on retaliators reliably recognising each other and scoring R
against each other. Introduce an error rate and they will punish each other by
mistake, which is precisely the assumption that makes 0.25% sufficient.

---

### D-023 — Phase C match loop: execution error, stochastic horizon, and how the two are bounded

**Date:** 2026-09-02
**Decided:** `play_match` gains `error_rate` (epsilon) and
`continuation_probability` (w), both defaulting to the Phase A/B behaviour.

**The defaults are a no-op, not a neutral value.** At epsilon = 0 and w = 1 the
new code paths are skipped rather than executed with harmless parameters, so
not one draw is taken from the generator that was not taken before. Every
pre-Phase-C test passes unchanged and bit-identically, which is asserted
directly rather than assumed.

**Execution error, not perception error.** With probability epsilon a player's
intended move is flipped on the way out, and *both* histories record what was
actually played. The two players never disagree about what happened. Splitting
execution from perception is open exploration 1 in the brief and stays unbuilt.

**The cap on match length.** A geometric horizon is unbounded, so runs need a
cap. The obvious choice - cap at the fixed `rounds` - is wrong in a way that
would not have announced itself: at w = 0.99 a cap of 200 truncates 13% of the
length distribution and pulls the mean from 100 down to about 86, quietly
making the game shorter than w says it is. Instead the cap is derived from w so
that the *same* negligible fraction is truncated at every w:
`ceil(log(tail) / log(w))` with `tail = 1e-4`, bounded by a hard ceiling of
5000 that `cap_binds()` reports on rather than applying silently.

**Pooled averaging.** With variable-length matches the per-round payoff is the
total payoff over all trials divided by the total rounds over all trials, not
the mean of each match's own per-round average. `E[total]/E[length]`, not
`E[total/length]`: a one-round match must not count as heavily as a
hundred-round one. Under a fixed horizon the two are identical, which is
exactly why this was worth catching before it mattered.

**Trials scale with w.** A fixed trial count would give w = 0.5 a hundred times
less play than w = 0.99. `trials_for(w)` targets a round budget per pair
instead, so every grid point buys comparable evidence.

**Rejected:** Capping at `rounds` (see above), and averaging per-match means.

---

### D-024 — Cooperation is measured from moves played, not from strategy names

**Date:** 2026-09-02
**Decided:** The Phase C map reports the **realised cooperation rate** - the
fraction of moves actually played as COOPERATE in the final population,
computed as `x . C . x` from a cooperation-rate matrix measured alongside the
payoff matrix. The name-based count is kept in the raw data as
`non_defector_share` but is not the headline.

**Why, and this one was found the hard way.** The first version of the map
scored a cell as cooperative if Always Defect and Random were extinct. At
epsilon >= 0.16, w >= 0.9 that measure reported a *total victory for
cooperation*: `non_defector_share = 0.999`, defectors eliminated. The realised
cooperation rate in the same cell is **0.223**. The population was Grim
Trigger, which at that error rate is tripped within the first few rounds of
almost every match and spends the rest of it defecting. A population of pure
Grim Trigger is a population that defects, whatever the strategy is called.

The general point is worth stating in the report: **once errors exist, a
strategy's name stops being evidence of its behaviour.** Phase A and B could
get away with counting shares by name because a noiseless Grim Trigger really
does cooperate. Phase C cannot. A cooperation rate close to epsilon is the
signature of total defection - the only cooperative moves left are mistakes -
and that is what the low-w rows of the map show.

**Rejected:** `non_defector_share` as the headline metric. It is the obvious
quantity, it is easy to compute, and in the region the experiment is actually
about it says the opposite of the truth.

---

### D-025 — Extinction culling must not feed back into the dynamics

**Date:** 2026-09-02
**Decided:** Phase C runs the replicator with `extinction_threshold = 0` and
applies the cutoff only at reporting time, via
`EvolutionResult.survivors_above()`. `PHASE_C_GENERATIONS = 60000`.

**Why.** D-015 concluded that the extinction threshold barely matters. That was
measured at epsilon = 0, and it does not survive contact with noise. At
epsilon = 0.02, w = 0.99:

| extinction threshold | cooperation rate | survivors |
|---|---|---|
| 1e-3 | 0.213 | Grim Trigger |
| 1e-6 | 0.213 | Grim Trigger |
| 1e-9 | 0.213 | Grim Trigger |
| **0 (none)** | **0.741** | **Tit-for-Tat, Random, Tit-for-Two-Tats** |

Grim Trigger's apparent victory is an artifact of culling. Under noise the
transient is long and *non-monotone*: the forgiving strategies are badly
behind while Grim is still harvesting the naive cooperators, dip below any
sensible cutoff, get zeroed irreversibly, and can never come back. Left alone
they recover and win. The payoff matrix says as much on inspection - Grim
scores 1.449 against itself while Tit-for-Two-Tats scores 1.656 against Grim,
so a Grim population is invadable and Grim-only cannot be the attractor.

Culling is a reporting convention (D-014). D-014 kept it out of
`replicator_step`; this keeps it out of the run as well, which is where it was
still doing damage.

**Convergence.** Noise makes convergence enormously slower: at epsilon = 0 the
equal-shares run settles by generation 116, and the same cell at epsilon = 0.02
settles at generation **25603**. G = 60000 is therefore the Phase C setting,
and it is still marginal - the slowest converged run settles at 59896, and
21 of 440 runs (4.8%) were still moving at the limit. Those cells are listed in
the output and their map entries flagged as provisional rather than quietly
reported as final.

**One optimisation, and one rejected.** Runs stop early when a generation
reproduces its predecessor **bit for bit**, which is exact: the update is
deterministic, so a bitwise fixed point is a fixed point forever. A
tolerance-based early stop was tried and is wrong - some trajectories creep
along a saddle with per-generation steps below 1e-15 for thousands of
generations and then accelerate away. Stopping on "barely moving" reported the
saddle as the answer and changed a grid cell from 0.74 cooperation to 0.98.

**Rejected:** Culling during the run at any non-zero threshold, and any
convergence test weaker than bitwise equality.

---

### D-026 — Phase C result: both standing predictions hold, and the boundary is bistable

**Date:** 2026-09-02
**Decided:** Recorded as the Phase C finding. Raw data in `results/`;
reproduced by `python experiments.py`.

**The map.** Realised cooperation rate, mean of 5 replicates, from equal shares:

| eps \ w | 0.5 | 0.6 | 0.7 | 0.8 | 0.9 | 0.95 | 0.98 | 0.99 |
|---|---|---|---|---|---|---|---|---|
| 0.00 | 0.00 | 0.00 | 1.00 | 1.00 | 1.00 | 1.00 | 1.00 | 1.00 |
| 0.02 | 0.02 | 0.02 | 0.02 | 0.76 | 0.93 | 0.90 | 0.88 | 0.71 |
| 0.04 | 0.04 | 0.04 | 0.04 | 0.72 | 0.88 | 0.82 | 0.75 | 0.79 |
| 0.06 | 0.06 | 0.06 | 0.06 | 0.52 | 0.84 | 0.78 | 0.81 | 0.37 |
| 0.08 | 0.08 | 0.08 | 0.08 | 0.48 | 0.80 | 0.78 | 0.73 | 0.71 |
| 0.10 | 0.10 | 0.10 | 0.10 | 0.10 | 0.76 | 0.73 | 0.65 | 0.56 |
| 0.12 | 0.12 | 0.12 | 0.12 | 0.12 | 0.64 | 0.65 | 0.64 | 0.54 |
| 0.14 | 0.14 | 0.14 | 0.14 | 0.14 | 0.44 | 0.53 | 0.61 | 0.51 |
| 0.16 | 0.16 | 0.16 | 0.16 | 0.16 | 0.29 | 0.28 | 0.21 | 0.19 |
| 0.18 | 0.18 | 0.18 | 0.18 | 0.18 | 0.25 | 0.24 | 0.22 | 0.20 |
| 0.20 | 0.20 | 0.20 | 0.19 | 0.20 | 0.20 | 0.22 | 0.22 | 0.22 |

**Corrected in D-028: the boundary is a staircase, not the rectangle this
entry first described.** "w >= 0.8 and epsilon <= 0.14" is a bounding box drawn
round a stepped region and understates the structure - the two dials trade
against each other:

| epsilon | lowest w at which cooperation survives |
|---|---|
| 0.00 | 0.7 |
| 0.02 - 0.08 | 0.8 |
| 0.10 - 0.14 | 0.9 |
| >= 0.16 | no w rescues it |

More noise demands a longer shadow of the future, and past epsilon ~ 0.15 no
horizon compensates at all. Read the collapsed cells carefully - where the rate
equals epsilon, *everything* defects and the only cooperative moves left are
execution errors. That identity is the cleanest possible reading of total
collapse, and D-028 verifies it across all 215 pure-defector cells (mean
deviation 0.0029).

**Prediction (a), D-020 - HOLDS.** Minimum Tit-for-Tat share needed to defeat a
90% Always Defect population, at epsilon = 0:

| w | 1-w | E[length] | TFT needed | needed/(1-w) |
|---|---|---|---|---|
| 0.9 | 0.10 | 10 | 6.286% | 0.629 |
| 0.95 | 0.05 | 20 | 2.916% | 0.583 |
| 0.98 | 0.02 | 50 | 1.107% | 0.553 |
| 0.99 | 0.01 | 100 | 0.568% | 0.568 |

Log-log slope of (TFT needed) against (1-w) is **1.046** against a predicted
1.000, and the ratio varies by a factor of only 1.14 across the range. Below
w = 0.9 cooperation never wins from that start at any retaliator share. This
was derived from the payoff structure in D-020 *before the sweep existed* and
the sweep reproduces it.

**Prediction (b), D-022 - HOLDS, and more sharply than stated.** The same probe
at w = 0.99, sweeping epsilon:

| epsilon | TFT needed | vs epsilon=0 |
|---|---|---|
| 0.00 | 0.568% | 1.0x |
| 0.02 | 5.253% | 9.3x |
| 0.04 | 5.932% | 10.4x |
| 0.06 | 9.530% | 16.8x |
| 0.08 | 10.000% | 17.6x |
| >= 0.10 | **never wins** | - |

Monotonically non-decreasing throughout, 17.6x over the measured range, and
past epsilon = 0.10 the answer is not a larger number but **no number**: no
retaliator share defeats a 90% defector majority. D-022 predicted the rise on
the grounds that its own 0.25% figure depended on retaliators reliably
recognising each other, which is precisely what an execution error breaks. The
mechanism is visible in a single matchup - two Tit-for-Tats score exactly R
against each other at epsilon = 0, and fall to 2.46 at epsilon = 0.01 and
towards the fully-randomised 2.25 thereafter, because one mistaken defection
starts an echo neither can stop.

**The boundary is bistable, not fuzzy.** In 17 cells the cooperation rate
varies by more than 0.3 across replicates that differ *only* in the tournament
seed - for example epsilon = 0.02, w = 0.8 gives [0.02, 0.93, 0.94, 0.95,
0.98]. Four sampled payoff matrices lead to cooperation and one to total
collapse. That is not measurement noise around a value; it is two attractors
with the sampling deciding which one is reached. Reporting a single number for
those cells would be reporting an average of two outcomes that never occur.

**Rejected:** Reporting the map as a clean contour. The band has a bistable
edge and 21 of 440 runs had not converged at G = 60000; both are stated in the
output rather than smoothed away.

---

### D-027 — The roster becomes a measured variable, drawn from a pool chosen by mechanism

**Date:** 2026-09-02
**Decided:** Phase C runs against a 15-strategy pool. The (ε, w) map is
produced once with the full pool as the fixed reference roster, then re-produced
across randomly drawn sub-rosters to measure how much the map depends on who
entered. Roster composition stops being a setting and becomes a reported
result.

**Why:** D-010 found, on the first run of Phase A, that removing one strategy
changes the tournament winner. That finding indicts our own seven-strategy
roster: if composition drives the outcome, then any single roster — including
ours — is an arbitrary basis for a conclusion. The consistent response is not to
pick a larger arbitrary roster, which only moves the arbitrariness from seven to
fifteen, but to sweep it and report the sensitivity.

There is also a specific defect this repairs. Every strategy in the Phase A
roster was selected for a world without mistakes. Phase C introduces an error
rate and asks who survives it — of a cast with no member designed for a noisy
world. The answer would partly measure that absence. Three of the additions
below exist precisely to answer error, and without them the ε axis is asked of
a field that cannot respond to it.

**Pool membership is by mechanism, not by variety.** Each entry represents a
distinct way of deciding, so that a result can be attributed to a behaviour
rather than to a name:

| mechanism | strategies |
|---|---|
| unconditional | Always Cooperate, Always Defect |
| reciprocal, varying tolerance | Tit-for-Tat, Tit-for-Two-Tats, Two-Tits-for-Tat, Grim Trigger |
| error-aware | Generous TFT(p), Contrite TFT, Pavlov |
| opening variant | Suspicious TFT |
| probing / exploitative | Prober, Gradual |
| aggregate-history | Soft Majority |
| baselines | Random(p), Alternator |

Contrite Tit-for-Tat matters most of the three error-aware entries: it
recognises its *own* mistake and accepts the resulting punishment without
counter-retaliating, which is the theoretically correct response to execution
error and has no counterpart in the current roster. Suspicious TFT is near-
irrelevant at N = 200, where a first-round difference is worth 1/N, but becomes
substantive as w falls and matches shorten — it is on the pool for the w axis,
not the ε axis.

**Sequencing.** The map is produced on the fixed pool first. Roster is a third
dimension and adding it to ε and w simultaneously produces a result nobody can
read; the robustness check follows the map rather than replacing it.

**Implementation note that makes this cheap.** `M[i, j]` depends only on
strategies i and j and on (payoffs, ε, w, rounds) — never on who else is in the
tournament. So the full 15×15 matrix computed once per (ε, w) grid point serves
every sub-roster: a drawn roster's matrix is the corresponding submatrix, and
its leaderboard the row means of that submatrix. The roster sweep therefore
costs almost nothing beyond the map itself, and comparing rosters against one
shared matrix removes sampling noise from the comparison as a side effect.

**Rejected:** Keeping the seven (asks the ε question of a field that cannot
answer it), and expanding to a larger fixed roster (relocates the arbitrariness
without removing it).

**Not in scope, and worth saying plainly in the report:** enlarging the roster
does not make the model more realistic. The model's real distance from life is
structural — a well-mixed population with no neighbourhoods or networks, and
agents that cannot learn. Neither is addressed by adding hand-coded rules, and
both remain out of scope for v1.

**The pool is a starting set, and the sweep is also the selection.** Fifteen is
where Phase C begins, not where the project ends. Once the map exists, each
strategy gets an influence measurement — the same test D-010 applied to Random,
generalised: re-run with that strategy removed and record how much the map, the
survivor set and the ranking move. A strategy that changes nothing measurable
did not earn its place and is dropped.

This makes the final roster defensible in a way no chosen number can be. Instead
of "we used ten strategies", the report says: we began with fifteen selected by
mechanism, measured what each one contributed, and kept the ones that changed
the answer. Ten is a plausible landing point; the number is an output of the
procedure, not an input to it.

The influence measurement is nearly free for the same reason the roster sweep
is: dropping a strategy is dropping a row and column from a matrix already
computed.

---

### D-028 — Past ε ≈ 0.15 cooperation does not lose; it stops meaning anything

**Date:** 2026-09-02
**Decided:** This is the reading the report leads with. Independently verified
against `results/phase_c_grid.csv` and `phase_c_matrices.npz`.

**The boundary is a staircase, not a rectangle.** Summarising it as "w ≥ 0.8 and
ε ≲ 0.14" understates the structure. The two dials trade against each other:

| ε | lowest w at which cooperation survives |
|---|---|
| 0.00 | 0.7 |
| 0.02 – 0.08 | 0.8 |
| 0.10 – 0.14 | 0.9 |
| ≥ 0.16 | no w rescues it |

More noise demands a longer shadow of the future — but the trade is bounded.
Past ε ≈ 0.15, no horizon however long compensates.

**Total collapse verifies itself.** In every cell where Always Defect is the
sole survivor, the realised cooperation rate equals ε — mean deviation 0.0029,
maximum 0.0100 across 215 runs. When nobody intends to cooperate, the only
cooperative moves left on the board are mistakes, and the metric says exactly
that. This is a strong check that D-024's behavioural measure is measuring what
it claims to.

**The mechanism, from the saved matrices at w = 0.99.** Noise closes a scissors
from both blades at once:

| ε | TFT vs TFT | AllD vs AllD | gap | AllD vs TFT | Grim vs Grim |
|---|---|---|---|---|---|
| 0.00 | 3.000 | 1.000 | 2.000 | 1.038 | 3.000 |
| 0.02 | 2.455 | 1.061 | 1.394 | 1.172 | **1.449** |
| 0.08 | 2.297 | 1.237 | 1.060 | 1.535 | 1.341 |
| 0.14 | 2.257 | 1.407 | 0.850 | 1.815 | 1.465 |
| 0.20 | 2.260 | 1.565 | 0.695 | 2.034 | 1.611 |

Retaliators earn less from each other, defectors earn *more* from each other,
and defectors earn much more from retaliators. The retaliators' entire
structural advantage — the 2.000 gap at ε = 0 — is down 65% by ε = 0.2. Note
also that a 2% error rate alone destroys Grim Trigger's mutual payoff, 3.000 →
1.449: one mistake between two Grims ends cooperation permanently.

**The finding.** Tracking who actually survives shows the collapse is not
strategies dying. It is strategies emptying out.

| ε (at high w) | survivors | behaviour |
|---|---|---|
| 0.00 | AllC, TFT, Grim, Pavlov, TF2T | genuinely cooperative |
| 0.08 | TFT, TF2T, Random | tolerant retaliators only — AllC and Grim gone |
| 0.14 – 0.20 | **Grim Trigger alone** | a defector wearing a cooperative name |

Grim's re-emergence at high ε is not Grim improving. Grim is triggered within a
few rounds at any appreciable error rate and defects thereafter, so it *is* a
defector — and at ε = 0.2 it happens to be a marginally better one than Always
Defect (1.611 against itself versus 1.565). The environment stopped being a
cooperation game and became a defection game, and Grim plays the second one
slightly better.

So the honest statement of the result is not "cooperation collapses at
ε ≈ 0.15". It is: **cooperation stops happening well before the strategies that
represent it stop winning.** Reciprocity survives as a label after it has ceased
to function as a behaviour.

**Why this is the report's spine.** It is the third time this project has caught
the same error in different clothing: D-010, where the tournament winner was an
artifact of the roster rather than a property of the strategy; D-019, where the
final population shares recorded a transient rather than a result; and here,
where a name-based metric reported total victory for cooperation in a population
that was 78% defecting. The recurring finding is not about cooperation at all —
it is that **the indicators fail before the thing they measure does**, and each
time the failure is only visible by going back to the underlying behaviour.

**Two caveats that stay in the report, unsmoothed.**

> **Corrected 2026-09-04.** Both caveats were computed on the seven-strategy
> sweep that occupied `results/phase_c_grid.csv` when this entry was written.
> That path now holds the fifteen-strategy pool; the seven are frozen under
> `results/control7_*`. The original figures were 17 bistable cells of 88, with
> ε = 0.02, w = 0.8 giving [0.02, 0.93, 0.94, 0.95, 0.98], and 21 of 440 runs
> unsettled with the latest at generation 59,896 — all correct for the control
> roster, and still readable there. Restated below against the file the entry
> names. The caveats themselves stand: the boundary is bistable and a residue
> of runs does not settle. Only the roster they are measured on changed.

Twelve of the 152 cells are bistable rather than noisy: at ε = 0.10, w = 0.7 the
five replicates give [0.10, 0.10, 0.10, 0.45, 0.83] — three runs collapse to
total defection, one reaches a cooperative world and one sits between them,
differing only in the tournament seed. Reporting a mean there would describe an
outcome that never occurs. And 17 of 760 runs had not settled at G = 60,000,
with the latest settling at generation 58,760. They cluster along the boundary,
which is what one expects where two attractors compete, but they are flagged
provisional rather than presented.

---

### D-029 — Building the pool: fifteen mechanisms, and the one refactor they forced

**Date:** 2026-09-03
**Decided:** D-027's pool is implemented. Eight strategies added to the seven:
Two-Tits-for-Tat, Generous TFT, Contrite TFT, Suspicious TFT, Prober, Gradual,
Soft Majority, Alternator. The Phase A/B seven are kept as
`strategies.CONTROL_ROSTER` and their sweep output is frozen under `control7_`
in `results/`.

**Generous TFT's forgiveness probability is not a free parameter.** It defaults
to Nowak and Sigmund's optimum, `min(1 - (T-R)/(R-S), (R-P)/(T-P))`, which for
T=5 R=3 P=1 S=0 is exactly 1/3. The factory `generous_tit_for_tat(p)` remains
for sweeping p, which is what D-011 deferred to Phase C.

**Contrite TFT needs no access to intent, and that is the interesting part.**
The obvious objection to implementing it is that "recognise your own mistake"
seems to require knowing what you meant to play, which the match loop does not
expose. It does not. Boyd's *standing* is defined on the played moves alone: a
player is in good standing if it cooperated last round, or if it defected
against an opponent already in bad standing - a justified punishment rather
than a fresh offence. An execution error is indistinguishable from a deliberate
defection to everyone including its author, and standing still assigns it
correctly, because it is defined on what happened rather than on what was
meant.

The behaviour that follows is the one the ε axis was missing: when this
strategy's own move is flipped and the opponent retaliates, it is itself in bad
standing, the opponent's defection is deserved, and so it cooperates *through*
the punishment instead of answering it. One error costs a single exchange.
Plain Tit-for-Tat answers back and starts an echo neither player can stop.
Measured at ε = 0.02 in self-play: Tit-for-Tat 2.455, Contrite TFT 2.94 of a
maximum 3.0.

**The refactor.** Contrite TFT, Gradual and Soft Majority all need a running
summary of the history, and recomputing it every round makes each match
O(n^2) - at the w = 0.99 cap that is 810k operations per match. Strategies
therefore take a fourth argument, a per-match scratch dict.

It is an optimisation and not hidden state, and the distinction is enforced
rather than asserted: everything in the dict is derived from the two histories,
a strategy called with `state=None` recomputes and returns the same move, and
three tests check exactly that by calling each stateful strategy both ways at
every step of a match. Writing Gradual the first time got this wrong - the
punishment counter was decremented when the move was produced, so asking twice
what to play this round consumed two slots - and the equivalence test is what
caught it. The schedule is now advanced only by *completed* rounds.

**A test that had to be strengthened twice, and both times said something.**
`test_no_two_pool_strategies_are_behaviourally_identical` is D-027's premise -
fifteen names must be fifteen mechanisms. It first reported Grim Trigger and
Two-Tits-for-Tat as identical, because against an opponent that never stops
defecting an unforgiving strategy and a two-round-memory one behave the same;
separating them needs an opponent that defects *once*. It then reported Contrite
TFT and Tit-for-Tat as identical, which is correct and by design - contrition
is invisible until the strategy errs. Distinctness has to be judged in the
environment the experiment actually runs in, so the panel now includes noisy
matches.

**Rejected:** Exposing intended moves to strategies (unnecessary, and it would
have made contrition a special case rather than a rule about play); and letting
strategies hold genuine internal state (untestable against the pure-function
contract, and the Gradual bug shows why that contract is worth keeping).

---

### D-030 — The roster matters most when it is small, and the ε ceiling was a small-roster artifact

**Date:** 2026-09-03
**Decided:** Roster composition is reported as a measured result. 120 random
sub-rosters, drawn at five sizes, every one re-derived from the *same* saved
matrices so that no difference between rosters can be sampling noise.

> **Corrected by D-033 and D-034. Every `0.20` in the ceiling columns below is
> right-censored — 0.20 was the largest value the grid could produce, so those
> entries record only that the roster had not broken by the last column looked
> at. Read them as "> 0.20, located in D-034". The `mean |Δ map|` column is
> uncensored and unaffected, and it is the column this entry should have led
> with.**

**The uncensored finding, first.** Sensitivity to composition falls steeply and
monotonically with roster size:

| roster size | mean \|Δ map\| vs pool |
|---|---|
| 5 | 0.203 |
| 7 | 0.141 |
| 9 | 0.109 |
| 11 | 0.080 |
| 13 | 0.045 |

A five-strategy roster moves the map by a fifth of the whole scale against the
pool; a thirteen-strategy one by a twenty-second of it. How much the answer
depends on the cast is itself a strong function of how big the cast is, and
this needs no ceiling to state.

**The ceiling columns, with the censoring made explicit:**

| roster size | ε ceiling: min | median | max |
|---|---|---|---|
| 5 | 0.06 | > 0.20 | > 0.20 |
| 7 | **0.14** | > 0.20 | > 0.20 |
| 9 | 0.16 | > 0.20 | > 0.20 |
| 11 | 0.16 | > 0.20 | > 0.20 |
| 13 | > 0.20 | > 0.20 | > 0.20 |

The min column is largely uncensored and shows a real floor rising with size:
the worst roster you can draw gets steadily less bad. That supports the claim
below in direction. What it cannot support is any statement about the *median*
roster, because more than half the rosters at every size survived past the edge
of the ruler.

**The claim this entry was built to make, restated within what was measured.**
At size 7 the worst draw scores 0.14 — and 0.14 is exactly what our original
seven scored. Against an uncensored spread of 0.06 to 0.16 across the size-7
minima, the seven sat at the bottom. The ceiling reported in D-028 was
therefore not typical behaviour for a seven-strategy roster; it was close to
the worst available, because the seven were selected for a world without
mistakes and contained no mechanism for handling one. D-027 predicted this
defect on principle before it was measured. What cannot be said from this table
is *how far* below typical it sat, because the typical value was off-scale.

This also puts a number on D-010, which is where the project started. Removing
one strategy changed the Phase A winner; the same instability, measured
properly across 120 rosters, is what the third column above quantifies.

**Rejected:** Reporting the pool map as *the* map. It is one roster's map, and
the sensitivity table is the honest accompaniment.

---

### D-031 — Influence measured, and a trimmed roster verified rather than recommended

**Date:** 2026-09-03
**Decided:** Every strategy's influence measured by dropping its row and
column and re-deriving the whole map. Recommended roster: **the ten most
influential.** Verified, not asserted.

| rank | strategy | mean shift in map | cells flipped | survivor-set changes |
|---|---|---|---|---|
| 1 | Always Defect | 0.1026 | 13 | 62 |
| 2 | **Contrite TFT** | **0.0868** | 3 | **97** |
| 3 | Suspicious TFT | 0.0483 | 5 | 16 |
| 4 | Soft Majority | 0.0426 | 5 | 13 |
| 5 | Alternator | 0.0359 | 4 | 18 |
| 6 | Tit-for-Tat | 0.0319 | 3 | 18 |
| 7 | Two-Tits-for-Tat | 0.0252 | 2 | 11 |
| 8 | Grim Trigger | 0.0231 | 1 | 14 |
| 9 | Pavlov | 0.0219 | 3 | 9 |
| 10 | Random | 0.0208 | 3 | 10 |
| 11 | Prober | 0.0206 | 0 | 7 |
| 12 | Gradual | 0.0186 | 2 | 7 |
| 13 | Always Cooperate | 0.0177 | 2 | 7 |
| 14 | Tit-for-Two-Tats | 0.0175 | 0 | 2 |
| 15 | Generous TFT | 0.0160 | 0 | 4 |

Always Defect leads, which is a sanity check rather than a finding - the
antagonist should matter most. **Contrite TFT is second, and first by survivor
churn: removing it changes who survives in 97 of 176 cells,** more than the
defector it exists to answer. Suspicious TFT ranking third vindicates D-027's
reasoning for including it: it was put on the pool for the w axis, and at
w = 0.5 a match is two rounds long, so the opening move is half the game.

**Leave-one-out does not compose, and pretending otherwise is the trap here.**
A strategy can measure as uninfluential *because* something else on the pool
covers its mechanism. Generous TFT ranks last precisely because Contrite TFT
and Soft Majority already handle error; drop all three and error-handling goes
with them. So the trimmed roster was not read off the ranking - it was built
from the ranking and then measured:

| roster | mean \|Δ map\| | cells flipped (of 88) | ε ceiling |
|---|---|---|---|
| pool of 15 | — | — | > 0.20 |
| trimmed to 12 | 0.0179 | 2 | > 0.20 |
| **trimmed to 10** | **0.0270** | **3** | > 0.20 |
| trimmed to 8 | 0.0499 | 5 | > 0.20 |

**The yardstick these should be read against is 0.054**, and it was already in
hand. D-029 measured it: re-running a sub-roster instead of taking its
submatrix moves cells by up to 0.054, because the error and continuation draws
are keyed by roster position. That is the scale at which a difference between
two maps stops being a difference and starts being the seed.

So the statement is sharper than "0.027 is small":

| roster | Δ map | against seed noise (0.054) |
|---|---|---|
| trimmed to 12 | 0.0179 | a third of it |
| **trimmed to 10** | **0.0270** | **half of it** |
| trimmed to 8 | 0.0499 | at it |

**Trimming to ten changes the map less than changing the random seed does.**
That is the recommendation's actual justification. Eight sits at the noise
scale, which is a second and independent reason to stop at ten — and it is a
better comparison than setting 0.027 against D-030's 0.045, since both of those
are below 0.054 and neither is a natural unit of anything.

Eight is also where the staircase starts to shift: it sustains cooperation at
w = 0.7 where the pool needs w = 0.8 across ε = 0.10–0.14, which is a change in
the reported answer rather than a rounding difference. Twelve is the
conservative choice at a third of seed noise.

**What each dropped strategy failed to change**, since a dropped strategy is
owed a reason:

- **Generous TFT** — 0 cells flipped, 4 survivor changes, ceiling unmoved. Its
  mechanism is statistical forgiveness: forgive a fixed fraction of defections
  without asking whose fault they were. Contrite TFT does the same job
  structurally and better, by asking. Redundant, not wrong.
- **Tit-for-Two-Tats** — 0 cells flipped, 2 survivor changes, the least of any
  strategy in the pool. Its mirror, Two-Tits-for-Tat, stays and carries the
  tolerance axis from the other end.
- **Always Cooperate** — 2 cells flipped, 7 survivor changes. Worth stating
  plainly because D-016 made it a headline: at ε = 0 it survived at 13% and was
  the clearest evidence that surviving is not the same as being good. Under
  noise it is close to inert. The finding it supported stands; the strategy is
  not needed to reach the map.
- **Prober** — 0 cells flipped, 7 survivor changes. It measures whether
  retaliation is present, and every roster it was tested in had plenty, so the
  measurement never changed its behaviour in a way the population noticed.
- **Gradual** — 2 cells flipped, 7 survivor changes. Escalating punishment with
  a calming phase; between Two-Tits-for-Tat's fixed escalation and Contrite
  TFT's de-escalation, the space it occupies is already covered.

**The trim applies to the Phase C map and to nothing else.** Two of the five
strategies it drops — Always Cooperate and Tit-for-Two-Tats — are members of
the seven-strategy roster on which the Phase A and Phase B results were
computed. Those results are not re-derived here and must not be restated as
though they were: D-016's finding that **Always Cooperate survives at 13%** is
a fact about the seven-strategy roster at ε = 0, and it is one of the sharper
findings in the project precisely because a strategy that cannot defend itself
survived. Dropping Always Cooperate from a Phase C roster does not retract it.

The report has to carry the scoping explicitly rather than leave a reader to
assume one roster throughout:

| result | roster it belongs to |
|---|---|
| Phase A leaderboard, D-010 | the seven |
| Phase B survivors and D-016's neutral mixture | the seven |
| D-019 initial-conditions sweep, D-020 basin scaling | the seven |
| D-026 predictions (a) and (b) | the three-strategy basin probe |
| D-028 ε ceiling and the Grim re-emergence | the seven |
| the Phase C map, D-030 to D-032 | the fifteen-strategy pool |
| **this recommendation** | **Phase C only** |

**Rejected:** Recommending a roster from the ranking without measuring it.
The ranking is a guide to *what to try*, and the composition failure above is
exactly the mistake it would have licensed. Also rejected: applying the trim
backwards to Phases A and B, which would have quietly deleted the population
that produced D-016.

---

### D-032 — Contrite TFT raises the ε ceiling, but is not what holds it up

> **Substantially corrected by D-034.** The "sufficient but not necessary"
> conclusion below rests on comparing two right-censored numbers that only
> looked equal. Uncensored, removing Contrite TFT costs 0.08 of ceiling
> (0.30 → 0.22): it is load-bearing. And the largest single contributor is
> Soft Majority, not Contrite. Read D-034 with this entry.

**Date:** 2026-09-03
**Decided:** D-028's reading is confirmed and refined. The ceiling near
ε ≈ 0.15 was about error-handling, not about noise as such — and error-handling
turns out not to be Contrite TFT's private property.

Four rosters, all read off the same matrices:

| roster | ε ceiling | staircase (ε: lowest viable w) |
|---|---|---|
| control 7 | **0.14** | 0.00:0.7 … 0.14:0.98, then nothing |
| control 7 + Contrite TFT | **0.18** | 0.00:0.7 … 0.18:0.95, then nothing |
| pool 15 − Contrite TFT | **0.20** | 0.00:0.7 … 0.20:0.95 |
| pool 15 | **0.20** | 0.00:0.6 … 0.20:0.9 |

**The answer to the question as asked is yes.** Adding one strategy — Contrite
Tit-for-Tat, and nothing else — to the seven that produced the ε ≈ 0.15 ceiling
moves that ceiling from 0.14 to 0.18. At ε = 0.16 and 0.18, where the original
roster collapsed to total defection at every horizon, the same roster plus
Contrite sustains cooperation. Nothing about the noise changed. What changed is
that one member of the population knows how to absorb its own mistake.

That is the sharpest available confirmation of D-028: the ceiling was a property
of the cast's inability to handle error, not a property of the error rate.

**But Contrite TFT is sufficient, not necessary.** The pool without it still
reaches 0.20 — Soft Majority dilutes an isolated mistake across an unbounded
record, Generous TFT forgives a third of defections outright, Tit-for-Two-Tats
absorbs a single one. Any mechanism that stops one error from starting an
unbreakable echo will do. Contrite TFT is simply the most efficient of them,
which is why it ranks second in D-031 while the others rank near the bottom:
influence is measured with the rest of the pool present, and the rest of the
pool can cover for it.

It does still earn its place inside the full pool, on the staircase rather than
the ceiling: with Contrite, cooperation survives at w = 0.6 at low ε and at
w = 0.9 at ε = 0.20; without it, w = 0.7 and w = 0.95. It buys roughly one grid
step of horizon across the whole range.

**The statement for the report.** Cooperation's tolerance for noise is not a
constant of the game. It is a property of what the population knows how to do
about noise — and it is the *composition* of the population, not the noise
level, that sets where the boundary falls. Which is the same lesson as D-010,
D-019 and D-024, arriving for the fourth time: the measurement kept describing
the roster, the transient or the label, and each time the fix was to go back to
the underlying behaviour.

**Rejected:** Reporting "yes, Contrite TFT lifts the ceiling" without the
second half. It would have been true and would have credited a mechanism to one
strategy that three others also provide.

---

### D-033 — Every "ceiling = 0.20" in D-029 to D-032 is right-censored, and one table must not be read as written

**Date:** 2026-09-03
**Decided:** No headline number leaves this project until the ε axis is
extended. The finding is not wrong; it is unmeasured at the top.

**The problem.** `results/phase_c_metadata.json` still records
`error_rate_grid` ending at 0.20. At that point the pool sustains a 0.67–0.70
cooperation rate at w ≥ 0.9 — nowhere near collapse. So "ceiling = 0.20" does
not name where a roster breaks. It names **the last column we looked at**, and
records only that the roster had not broken by then. In survival-analysis terms
these observations are right-censored, and the whole pool column is censored.

**Where this actually bites.** The sensitivity table reads:

| size | ceiling min | median | max | mean \|Δ map\| |
|---|---|---|---|---|
| 5 | 0.06 | 0.20 | 0.20 | 0.203 |
| 7 | **0.14** | 0.20 | 0.20 | 0.141 |
| 9 | 0.16 | 0.20 | 0.20 | 0.109 |
| 11 | 0.16 | 0.20 | 0.20 | 0.080 |
| 13 | 0.20 | 0.20 | 0.20 | 0.045 |

0.20 is the largest value the grid can produce. A median of 0.20 therefore does
not say the median ceiling is 0.20; it says **more than half the rosters at
every size survived past the edge of the ruler.** The true median could be 0.25
or 0.45 and this table could not tell the difference. The same applies to every
0.20 in the max column, and to the pool's own ceiling in D-030 and D-032.

D-030's claim that the seven's ceiling "was close to the worst available" is
therefore right in direction and unquantified in size: 0.14 against an
uncensored spread of 0.06–0.16 in the min column supports it, but the
comparison against a censored median does not.

**What in that table is solid, and worth leading with instead.** The min column
is largely uncensored and shows a real floor rising with size. The
`mean |Δ map|` column is *entirely* uncensored and monotone: **0.203 at size 5
falling to 0.045 at size 13.** That is the finding — how much the answer depends
on the cast falls steeply as the cast grows — and it needs no ceiling at all to
state.

**A yardstick already in hand, unused.** D-029 found that re-running a
sub-roster rather than taking its submatrix moves cells by up to 0.054, because
the error and continuation draws are keyed by roster position. That is the
scale at which a map difference stops being readable. Set the trimming results
against it:

| roster | Δ map | vs. seed noise (0.054) |
|---|---|---|
| trimmed to 12 | 0.0179 | a third of it |
| trimmed to 10 | 0.0270 | half of it |
| trimmed to 8 | 0.0499 | at it |

So the defensible statement of D-031's recommendation is stronger than the one
made: **trimming to ten changes the map less than changing the random seed
does.** Eight sits at the noise scale, which is a second reason to stop at ten —
independent of, and better than, comparing 0.027 to 0.045, since both of those
are below 0.054 and neither is a natural unit.

**Required before any of this is reported:** extend the ε axis to 0.35 and
locate the pool's actual ceiling. Until then every affected number is stated as
"> 0.20, not located". The cost is a few extra columns on a grid that is already
built.

**The fourth instance, and the first with a proper name.** D-010: the winner
was an artifact of the roster. D-019: the final shares recorded a transient.
D-024/D-028: a name-based metric reported victory for a population that was
78% defecting. Now: the measurement range ends before the phenomenon does, and
the summary statistic reports the edge of the instrument as if it were a
property of the world. The recurring finding of this project is not about
cooperation — it is that **indicators fail before the thing they measure does**,
and every instance has been visible only by returning to what was underneath.
Right-censoring is the textbook name for this one, which makes it the cleanest
of the four to write up.

---

### D-034 — The ε axis extended to 0.35: the pool's ceiling is 0.30, and three earlier readings change

**Date:** 2026-09-04
**Decided:** D-033 acted on. `ERROR_RATE_GRID` runs to 0.35, the 320 new cells
were computed and merged into the existing 440 rather than recomputing them,
and every censored number in D-029 to D-032 is now replaced by a measured one.

**The merge was checked before it was trusted.** A saved cell was recomputed
with the current code and compared bit for bit; the extension refuses to merge
unless it reproduces exactly, because a merged grid spliced from two different
versions of the code would be a silent fabrication. It reproduced.

**The pool breaks at ε = 0.30.** Cooperation rate along w = 0.99:

| ε | 0.20 | 0.24 | 0.28 | **0.30** | 0.32 | 0.34 |
|---|---|---|---|---|---|---|
| rate | 0.70 | 0.66 | 0.63 | **0.55** | 0.38 | 0.34 |
| normalised | 0.84 | 0.81 | 0.79 | **0.63** | 0.16 | 0.01 |

The normalised row is the cooperation rate rescaled onto the range the error
rate permits — a population that always intends to cooperate still only plays C
a fraction `1 − ε` of the time, and one that always intends to defect still
plays C a fraction `ε` of the time, so the observable rate is confined to
`[ε, 1 − ε]`, a band that narrows as ε grows. Rescaling to `(rate − ε)/(1 − 2ε)`
puts 0 at total defection and 1 at total cooperation whatever the error rate.
**Both readings give a ceiling of 0.30**, so it is a property of the population
and not of where the cutoff was drawn.

**And the collapse is a cliff, not an erosion.** The normalised index sits above
0.78 all the way from ε = 0 to ε = 0.28 — a population absorbing more than one
mistaken move in four and still cooperating at four-fifths of what the noise
allows. Then, in two grid steps, 0.63 → 0.16 → 0.01. Cooperation does not
degrade gracefully under noise; it holds and then goes.

**Correction 1 — D-030's sensitivity table, now uncensored.**

| size | ceiling: min | median | max | mean \|Δ map\| |
|---|---|---|---|---|
| 5 | 0.06 | 0.31 | ≥ 0.35 | 0.177 |
| 7 | **0.14** | 0.26 | ≥ 0.35 | 0.125 |
| 9 | 0.16 | 0.30 | ≥ 0.35 | 0.099 |
| 11 | 0.16 | 0.30 | ≥ 0.35 | 0.071 |
| 13 | 0.20 | 0.30 | 0.32 | 0.037 |

The median is now a number rather than a wall: 0.26 to 0.31, not "0.20". The max
column is *still* censored at sizes 5 to 11, where the best draws survive past
0.35 — marked `≥`, not fixed, and it is not worth another extension to chase.

This is what makes D-030's claim about the original seven quantitative at last.
At size 7 the median roster breaks at 0.26 and the worst observed at 0.14. Our
seven scored **0.14** — the minimum of 24 draws. Before the extension the
comparison was against a censored median and could not be made; now it can:
the seven were not merely below typical, they were at the floor.

**Correction 2 — D-031's trimming, on the wider grid.**

| roster | mean \|Δ map\| | vs seed noise (0.054) | cells flipped (of 152) | ε ceiling |
|---|---|---|---|---|
| trimmed to 12 | 0.0145 | a quarter of it | 4 | 0.30 |
| **trimmed to 10** | **0.0290** | **half of it** | 9 | 0.30 |
| trimmed to 8 | 0.0381 | two thirds of it | 8 | 0.30 |

All three hold the ceiling at 0.30, and all three move the map by less than
changing the random seed does. The recommendation stays at **ten**, with two
caveats now visible that were not before. First, twelve is materially cleaner —
a quarter of seed noise against a half, and 4 flipped cells against 9. Second,
the flip counts do not order themselves (4, 9, 8 for 12, 10, 8), which is what
a measure jittering at the noise scale looks like; they should not be the
deciding criterion on their own.

**The membership of the recommended ten has changed**, because the influence
order changed once the extra columns were included: Prober enters and Random
leaves. The ten are now Always Defect, Contrite TFT, Soft Majority, Suspicious
TFT, Alternator, Tit-for-Tat, Grim Trigger, Two-Tits-for-Tat, Pavlov, Prober.
Always Cooperate and Tit-for-Two-Tats are still dropped, so D-031's scoping
note stands unchanged: **the trim is for the Phase C map only**, and D-016's
Always Cooperate finding belongs to the seven.

**Correction 3, and the largest — D-032 was reading two censored numbers as
equal.** On the old grid, "pool − Contrite = 0.20" and "pool = 0.20" looked
identical and licensed the conclusion that Contrite TFT was *sufficient but not
necessary*. Both were lower bounds. Uncensored, at five replicates:

| roster | ε ceiling |
|---|---|
| control 7 | 0.14 |
| control 7 + Contrite TFT | 0.18 |
| **pool 15 − Contrite TFT** | **0.22** |
| pool 15 | **0.30** |

Removing Contrite Tit-for-Tat from the pool costs **0.08 of ceiling** — more
than a quarter of it. It is load-bearing, not redundant, and the earlier
"not necessary" was an artifact of the ruler.

What survives from D-032 is the weaker and still-correct half: Contrite is not
*solely* responsible, because the pool without it still reaches 0.22, well
above the seven's 0.14. And the single largest contributor is not Contrite at
all:

| strategy removed | ε ceiling | Δ map |
|---|---|---|
| **Soft Majority** | **0.20** | 0.041 |
| Contrite TFT | 0.22 | 0.066 |
| Always Defect | 0.30 | 0.098 |
| Generous TFT | 0.30 | 0.003 |
| Tit-for-Two-Tats | 0.30 | 0.001 |

**Soft Majority costs 0.10 of ceiling when removed, against Contrite's 0.08.**
It is the only pool member with unbounded memory: it judges the whole record
rather than the last move or two, so at high error rates an isolated mistake is
diluted by everything that came before it instead of triggering anything. That
is a second, quite different way of not letting one error start an echo, and at
the top of the ε range it is worth slightly more than contrition.

Note also that Always Defect has the largest effect on the *map* (0.098) and no
effect on the *ceiling*. The two measure different things, and D-031's ranking
by mean map shift should not be read as a ranking by importance to the ceiling.

**The lesson D-033 named, confirmed by its own repair.** Extending the ruler did
not merely fill in a blank — it reversed a published conclusion (Contrite
"unnecessary" → load-bearing) and promoted a strategy that had been ranked
third by map shift to first by ceiling contribution. That is what
right-censoring costs: not imprecision, but wrong answers stated confidently.

**Rejected:** Reporting any ceiling from the 0.20 grid. Also rejected:
extending further to uncensor the `max` column of the sensitivity table — the
quantity that matters there is the minimum and the median, both of which are
now measured, and the best-case roster is not a claim the report needs.

---

### D-035 — The censoring produced a wrong conclusion, not an imprecise one, and that is the report's spine

**Date:** 2026-09-04
**Decided:** How the D-032 reversal is written up, and what the project's
central claim now is. Verified independently against the extended
`results/phase_c_grid.csv` (760 rows, ε to 0.35).

**What was verified.** The cliff is real, and the normalised reading
`(rate − ε)/(1 − 2ε)` is what makes it visible. Along w = 0.99:

| ε | raw rate | normalised |
|---|---|---|
| 0.00 | 1.000 | 1.000 |
| 0.10 | 0.829 | 0.911 |
| 0.20 | 0.701 | 0.836 |
| 0.28 | 0.627 | **0.788** |
| 0.30 | 0.551 | 0.628 |
| 0.32 | 0.378 | **0.162** |
| 0.34 | 0.343 | 0.008 |

Cooperation does not erode. It holds — 79% of the achievable band still
cooperative at an error rate of 28% — and then snaps, losing almost everything
across two grid steps. The collapse invariant holds throughout the new region
too: across 239 newly computed pure-defector cells the realised rate equals ε
to a mean deviation of 0.0033.

Stating the ceiling as a single number is therefore a convention, not a
measurement. The report should give the three figures around the edge, because
the shape of the fall is the finding and "0.30" hides it.

**The reversal, and it went against my own reading.** D-032 concluded that
Contrite TFT was sufficient but not necessary — that the pool without it
reached the same ceiling. Uncensored, removing Contrite costs 0.30 → 0.22. It
is load-bearing. Both numbers had been 0.20 only because both were pinned at
the edge of the grid.

I proposed that reading ("the mechanism matters, the strategy does not"), and
it was wrong. Censoring did not blur a number here; **it manufactured a
qualitative claim out of two values that were not measurements at all.** Two
things pressed against the same ceiling look equal, and there is no way to tell
from inside the table that they are not.

**The better finding underneath it.** The largest single contributor is not
Contrite TFT but **Soft Majority**, at 0.10 — the only pool member with
unbounded memory. It answers an opponent by what they have done *most often
across the whole history*, so an isolated mistake barely moves the verdict.
That makes three distinct ways of surviving error, and they are not equally
good:

- **Contrite TFT** — recognises its own error and accepts the punishment.
  Structural.
- **Generous TFT** — forgives a fixed random fraction, without asking whose
  fault it was. Statistical.
- **Soft Majority** — judges the whole record rather than the last move, so one
  slip is diluted rather than answered. Strongest of the three.

Dilution beating both forgiveness and contrition is the more interesting
result, and it has a plain-language form worth keeping: *judging someone by
their record rather than their last move is the most robust defence against
noise there is.*

**Also separated cleanly, and worth its own line:** Always Defect moves the map
more than anything else and moves the ceiling not at all. The antagonist shapes
the landscape without setting its limit.

**Why this is now the spine of the report.** The recurring finding has occurred
four times, and the fourth is different in kind:

1. D-010 — the tournament winner was an artifact of the roster.
2. D-019 — the final population shares recorded a transient.
3. D-024/D-028 — a name-based metric reported total victory for cooperation in
   a population that was 78% defecting.
4. **D-033/D-034 — the measurement range ended before the phenomenon did, and
   the resulting conclusion was not merely imprecise but wrong.**

The first three were errors the project caught in its own model. The fourth was
an error in the project's own analysis, made by both sessions, endorsed in
writing, and only visible by extending the instrument. That is the honest and
much stronger version of the thesis: **indicators fail before the thing they
measure does — including the ones you built yourself, including after you have
already learned the lesson three times.**

**What remains censored, and stays labelled.** The `max` ceiling column is still
at the grid edge for roster sizes 5–11 and renders as `≥ 0.35`. Not chased
further, which is a reasonable stopping point — but `ceiling_is_censored` /
`format_ceiling` now make the distinction structural rather than a note someone
has to remember, which is the right fix.

---

### D-036 — Repository name and report format, both deferred since the brief, now settled

**Date:** 2026-09-04
**Decided:** The repository is renamed **`holds-then-snaps`**. The report ships
in two forms: a Markdown summary in the repository, and a full LaTeX/PDF
report.

**Why this name.** D-004 deferred it deliberately so the analysis could not be
bent to fit a title, and the prior projects in this series are all named after
their finding rather than their apparatus. The finding is the shape of the
collapse: normalised cooperation holds at 0.788 through an error rate of 28%,
then falls to 0.162 two grid steps later. Cooperation does not erode under
noise — it holds, and then it snaps.

Rejected: `evolutionary-game-sim`, which names the apparatus and would break
the naming pattern; and `the-instrument-fails-first`, which names the
methodological theme. That theme is the discussion section's argument and the
more transferable lesson, but a repository should be named for what it
studied, not for what its author learned about measurement while studying it.

**Why both formats.** They do different jobs and neither substitutes for the
other. The Markdown summary is what a reader meets on the repository front
page — it must be legible without downloading anything, and it carries the
headline figure and the three edge numbers. The LaTeX/PDF is the full argument
with the method, the corrections and the discussion, and matches the delivery
pattern of the earlier projects in this series.

The cost is real and named here so it is not discovered later: two documents
carrying the same claims can drift. The rule is that the Markdown summary
states no number that is not also in the PDF, and every number in both is
traceable to a file under `results/`. If a claim changes, both change in the
same commit.

**Figures the report needs**, all generated from `results/` rather than drawn
by hand, so that regenerating them is a check rather than a chore:

1. The (ε, w) map on the pool, behavioural metric — the headline.
2. The normalised curve along w = 0.99 — the hold-then-snap shape, and the
   figure the name comes from.
3. Pool and pre-expansion control side by side — the roster effect, from the
   same sampled matrices.
4. Influence ranking across the fifteen.
5. Sensitivity against roster size — mean |Δ map| from 0.203 to 0.045.
6. A Phase B trajectory, for context on how the apparatus behaves before noise.
