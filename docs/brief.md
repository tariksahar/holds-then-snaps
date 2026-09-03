# Project Brief v2: Evolutionary Game Theory Simulation

> **How to read this brief.** v1 tried to decide everything up front. This
> version separates what is *settled* from what is *deliberately open*.
> The open items are not oversights — they are decisions that are cheaper and
> better made with running code and a plot in front of us. Each one, once
> settled, becomes an entry in the decision log (which is itself a
> deliverable). Nothing here is binding; if the build says otherwise, the
> build wins.

## Guiding question

**When does cooperation survive, and when does it collapse?**

The tournament and the evolutionary model are not the point — they are the
apparatus. The point is to find where the boundary sits and what pushes a
population across it.

The exact sharpening of this question is an open item (see *Open
explorations*). The final framing should be decided once Phase A and B are
running and we can see what the model actually does.

## Settled

- Iterated Prisoner's Dilemma, well-mixed population, hand-coded strategies.
- Python, CPU-only. Code and comments in English.
- Payoff ordering `T > R > P > S`, with `2R > T + S`. Starting point:
  T=5, R=3, P=1, S=0 (Axelrod's canonical set), treated as a default to be
  varied, not a constant.
- No magic numbers: payoffs, roster, round count, generation count, and every
  parameter introduced later are configuration, not literals in the code.
- Reproducibility: explicit RNG objects seeded from a single documented root
  seed, not a global seed. Any stochastic result averaged over repeated
  trials, never a single run.
- Public repo, written report, decision log, README.

## Phase A — Round-robin tournament

Fixed roster, every strategy against every other and against itself, N rounds,
configurable payoff matrix. Output: per-strategy total and average score, plus
the full pairwise matrix (the matrix matters more than the leaderboard — Phase
B consumes it).

Starting roster: Always Cooperate, Always Defect, Tit-for-Tat, Grim Trigger,
Random, Pavlov (Win-Stay-Lose-Shift), Tit-for-Two-Tats, Generous Tit-for-Tat.
The roster is expected to change as the question sharpens.

## Phase B — Replicator dynamics

Population shares evolve by `x_i(t+1) = x_i(t) · f_i(t) / f̄(t)`, where
`f_i` is strategy i's average payoff against the current mix, computed from
the Phase A pairwise matrix.

Track shares over G generations. Report which strategies vanish, which
dominate, which coexist.

## Phase C — The actual experiment

Phase A and B reproduce known results. Phase C is where the project earns its
keep. Two parameters, neither present in v1:

- **Error rate (ε):** agents sometimes play a move they did not intend.
- **Continuation probability (w):** each round continues with probability w
  instead of running a fixed, publicly known N. This matters for more than
  realism — with a known finite N, backward induction makes defection the
  rational play throughout, which quietly undermines the whole setup.

Sweep both, record which strategy survives at each point, and produce the
resulting map of where cooperation is viable.

## Open explorations — pick during the build, not before

Three candidate layers on top of Phase C. One is probably enough; two is
ambitious; three is a different project. Decide once Phase C runs.

1. **Two kinds of error.** Split ε into an *execution* error (you played the
   wrong move, and you know it) and a *perception* error (you misread your
   opponent, and the two players now hold different histories of the same
   match). Hypothesis: strategies that react to outcomes rather than to the
   opponent's last move can absorb their own mistakes but not misreadings.

2. **The optimal amount of forgiveness.** Replace the fixed Generous
   Tit-for-Tat with a family parametrised by forgiveness probability p, sweep
   p, and find the best p at each noise level. A closed-form optimum exists in
   the literature for this payoff set — recovering it independently would be
   strong validation as well as a result.

3. **A world that changes.** Evolve the population under low noise, then raise
   the noise abruptly and ask whether it can recover. Requires adding a small
   mutation/immigration term so extinct strategies can re-enter — which also
   removes the artifact that extinction under pure replicator dynamics is
   permanent and absolute.

## Decisions to make in flight

Open on purpose. Each becomes a decision-log entry once resolved.

- **Phase A → Phase B handoff.** Fitness must be built from *per-round
  average* payoffs, self-play included. Confirm this is what the code does
  before trusting any Phase B output.
- **Selection intensity.** `f_i / f̄` is sensitive to the absolute level of
  the payoffs: adding a constant to every payoff changes how fast the dynamics
  run. Introduce `fitness = (1−s) + s · payoff` and document the chosen s.
  Note that the formula breaks outright on negative payoffs — a reason to keep
  S = 0 rather than switch to a donation-game parametrisation.
- **What counts as extinct.** Shares approach zero but never reach it. Pick a
  threshold, apply it consistently, state it in the report.
- **Initial conditions.** Equal shares is one point in the simplex. Sample
  many random starting mixes and report how much the outcome depends on where
  you begin.
- **Roster sensitivity.** Tournament rankings are partly an artifact of who
  entered. Re-run with perturbed rosters and report how stable the ranking is.
- **Rounds and generations.** Start at N=200, G=200. Raise if runs have not
  converged; the model is cheap.

## Testing

Beyond a smoke test, assert the invariants:

- `TFT vs TFT` over N rounds = `N · R`; `Grim vs AllD` = `S + (N−1) · P`.
- The pairwise matrix is consistent under player swap.
- Population shares sum to 1 at every generation.
- A strategy with above-average fitness strictly gains share.

Cross-check a few matchups against the `Axelrod` Python library. Keep our own
implementation — the point is to write it — but being able to state that it
agrees with a reference implementation costs little and buys a lot.

## Suggested structure

Suggested, not mandated. Split differently if the code wants to.

`strategies.py` · `tournament.py` · `evolution.py` · `experiments.py`
(Phase C sweeps) · `visualize.py` · `tests/` · `run_all.py` ·
`config.yaml` (or a config module) · `app.py` (optional Streamlit)

## Deliverables

1. Public GitHub repo with README.
2. Written report: question, method, results, discussion.
3. Decision log covering every in-flight decision above.
4. Optional Streamlit dashboard — a stretch item, not a v1 requirement.

Report format and repo name: open.

## Definition of done

- Phases A, B and C run end-to-end from one entry point, no manual steps.
- The report states the leaderboard, what survived under evolution, the Phase
  C result, and one honest paragraph on evolutionary stability — honest
  meaning it does not claim the tournament winner is an ESS. In the repeated
  Prisoner's Dilemma no pure strategy is evolutionarily stable: a strategy
  that ties with the incumbent can drift in for free, and once it is common
  enough the incumbent is open to invasion. If the model can be made to show
  this happening, show it.

## Out of scope (v1)

- Spatial or network-structured populations.
- Learned / reinforcement-learning strategies.
- Linear-programming computation of mixed-strategy equilibria, unless the
  results demand it.

## Working method

Two parallel sessions, one repository, coordinating only through a shared
state file. The repository is the source of truth; neither transcript is.

- **The build session (local, in the repo):** writing and running code,
  tests, git, regenerating figures. The build lives here.
- **The methodology session:** literature, methodology arguments,
  reviewing results, drafting the report and decision log. Reachable
  from the phone.
- `PROJECT_STATE.md` holds the current state of every settled decision.
  Both sessions read it; whichever session makes a decision writes it
  there immediately.
  A decision that exists only in a chat transcript does not exist.
- `decisions.md` is the append-only record and doubles as deliverable #3.

## Background reading

- Axelrod, R. (1984). *The Evolution of Cooperation.*
- Maynard Smith, J. (1982). *Evolution and the Theory of Games.*
- Nowak & Sigmund (1993), on win-stay-lose-shift under noise.
- Boyd & Lorberbaum (1987), on the absence of evolutionarily stable pure
  strategies.
