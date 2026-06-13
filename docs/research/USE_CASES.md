# Use Cases — Co-Work Memory Journeys (Phase 1)

Concrete journeys where a human **and** an agent (or several of each) share one
brain. Each names the actors, the shared-memory need, the failure if the brain
is naive, and the **CH capability** that serves it (✓ exists, ◐ partial,
**✗ → phase**). Grounded in `USER_RESEARCH.md` and Shahriar's own portfolio
([[virtual-brain-vision]]: letX, Quantum Sketch, aibhai, offSchool, comikola).

The north-star: every journey below is *broken by a single-user memory* and
*served by a co-work memory*. They are the acceptance criteria the CH-Bench
co-work suite encodes.

---

## 1. Dev + coding agent on a team (the flagship)

**Actors:** several developers, each with a coding agent (Claude Code / IDE),
one shared repo brain.
**Need:** coding conventions, architectural decisions, and debugging rules that
one dev+agent discover become instantly available to every other dev+agent —
with the *why*, *who decided*, and *when* attached.
**Failure if naive:** dev B's agent re-derives a rule dev A's agent already
learned (tribal-knowledge loss, P3); or follows a convention that was
superseded last week (staleness, P1); or two agents wrote opposite style rules
and the reader can't tell which won (conflict, P2).
**CH serves it:** episodes→distill ✓, graph ✓, communities ✓, **supersession/
as-of** ✓ (kills "follows the old rule"). **P1 adds:** team scope + provenance
("dev A decided, 3 wk ago, here's the PR") + cross-actor conflict surfacing +
**who-knows-what** ("who owns the auth module's conventions").
**Bridge:** [[common-knowledge]] already pushes a local agent's learnings up to
the shared CH brain (API-key = workspace identity).

## 2. Founder + agent across a company's life

**Actors:** founder + an "exec" agent; later, early hires + their agents.
**Need:** decisions and their rationale, customer facts, strategy that *changes
over time* — the agent must answer "what did we decide about pricing in Q1, and
has it changed?" not just "what is pricing."
**Failure if naive:** the agent confidently quotes a pivoted-away-from strategy
(stale high-relevance memory — the literature's hard case, P1); or a new hire's
agent can't find *who* knows the deal history.
**CH serves it:** **temporal truth (as-of / valid_until)** ✓ is the headline fit
— "as of Q1 vs now." **P1 adds:** provenance (founder-vetted vs agent-scraped
trust tier) + who-knows. **P4 adds:** decay so dead strategies fade in ranking.

## 3. Research / engineering team with conflicting findings

**Actors:** several researchers + agents writing into one corpus.
**Need:** cross-actor recall (find a colleague's result), provenance (whose
experiment, what conditions), and **conflict surfacing** when two findings
disagree — *both* shown with evidence, not silently merged.
**Failure if naive:** the brain picks one finding arbitrarily and hides the
contradiction (Rashomon problem, P2); or attributes a result to the wrong
person (provenance, P4).
**CH serves it:** contradiction detection ◐ + supersession ✓. **P1 adds:**
cross-actor conflict surfacing with dual provenance + trust-tier; **P2** (graph
ranking) helps corroboration ("3 independent sources agree").

## 4. Writer + agent across separate universes (comikola / creative)

**Actors:** a writer + a writing agent, working on **two** canons.
**Need:** per-project memory of voice, characters, and canon — and *strict
non-contamination*: universe A's facts never leak into universe B, and the same
agent adopts a different persona per project.
**Failure if naive:** a character from one story appears in another (cross-
project contamination, P6); or the agent's voice is generic because persona
isn't memory-resolved.
**CH serves it:** `workspace_id` isolation ✓ + **profiles/personas** ◐
([[per-project-persona-vision]] — the unclaimed differentiator). **P1 adds:**
persona resolves into retrieval + write + **exposure** scope (personal vs
shared), so the brain *behaves differently per project*.

## 5. PM + agent over a shifting spec

**Actors:** a PM + agent, plus eng/design stakeholders writing context.
**Need:** requirements that change over time (temporal), stakeholder positions
(provenance: "design wants X, eng pushed back"), and create-safety so the agent
doesn't write a duplicate "decision" node over a developed one.
**Failure if naive:** the agent answers from a requirement that was revised
(staleness, P1); or writes a near-duplicate decision because it read one blended
score and thought "no match, safe to create" (gbrain's documented failure mode).
**CH serves it:** versioning/as-of ✓. **P1 adds:** **create-safety hints**
(exists / probable / unknown) on writes + provenance on every source.

## 6. Agent + agent (no human in the loop)

**Actors:** two automated agents (e.g. an ingest agent + an answer agent, or two
specialist agents) sharing the brain.
**Need:** trust boundaries — a low-trust ingest agent's writes are quarantined/
down-weighted so they can't steer a high-trust answer agent; fail-closed scope.
**Failure if naive:** a compromised or naive agent poisons the shared memory and
hijacks the other agent's output (the Lethal Trifecta, P5).
**CH serves it:** scopes (read/write/admin) ✓ + OAuth-per-token ✓. **P1 adds:**
**H1 injection hardening** (delimit notes, instruction-hierarchy) + **H2 trust-
tier** so low-trust writes are visibly low-trust at answer time. **P5** adds the
hosted-MCP cross-tenant isolation test.

---

## What every journey needs from P1 (the build checklist)

| capability | journeys that need it | audit/plan link |
| --- | --- | --- |
| shared **+** personal/team scoping | 1,2,3,4,6 | plan P1 |
| **provenance** on every source (actor/source/when/why-matched) | all | audit **H2** |
| **trust-tier** (vetted vs scraped vs low) | 1,2,3,6 | audit **H2** |
| **cross-actor conflict surfacing** | 1,2,3,5 | plan P1 |
| **who-knows-what** over the graph | 1,2,3 | plan P1 + gbrain ref |
| **create-safety hints** (exists/probable/unknown) | 1,5 | plan P1 + gbrain evidence contract |
| **per-agent/human persona** → retrieval/write/exposure policy | 1,2,4,6 | plan P1, reuse `profile_service` |
| **prompt-injection hardening** of the answer path | 5,6 (all shared) | audit **H1** |
| temporal as-of / supersession (already ✓) | 1,2,3,5 | keep + *surface* the age |

**Read-out:** the P1 deliverables (scoping, provenance/trust-tier, conflict
surfacing, who-knows, create-safety, persona policy, H1 hardening) are not a
grab-bag — every one is load-bearing for ≥3 of these six journeys. CH's existing
temporal model is the moat under journeys 1/2/3/5; P1 builds the co-work surface
on top of it. These journeys become the CH-Bench **co-work suite** test cases.

---

## Sources

Use cases synthesized from `USER_RESEARCH.md` (sourced there) + the portfolio
context in [[virtual-brain-vision]] / [[per-project-persona-vision]] /
[[product-ecosystem-strategy]]. Competitor capability anchors (gbrain `whoknows`
+ evidence/create-safety contract; supermemory profiles) from
`ARCHITECTURE_REVIEW.md`.
