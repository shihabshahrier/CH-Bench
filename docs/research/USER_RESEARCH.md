# User Research — Co-Work Memory Pain (Phase 1)

What people *actually* struggle with when a human and an agent — or several
people and several agents — share one memory. Mined from forums, vendor
post-mortems, security write-ups, and the 2026 agent-memory literature.
**Evidence tags:** `[field]` = practitioner report / vendor post / forum,
`[paper]` = research literature, `[sec]` = security disclosure/analysis,
`[inf]` = our inference. Each pain is mapped to the **CH mechanism** that
answers it (existing ✓, partial ◐, or **missing ✗ → which phase builds it**).

The thesis this validates: a single-user memory is mostly a *recall* problem;
a **co-work** memory is a **trust, freshness, and isolation** problem. That is
the unclaimed space and the north-star.

---

## P1 — Stale shared knowledge degrades the whole team, not one user

> "Old, stale memory can actually degrade agent performance… if the system
> never updates or retires old memories, it will eventually return stale
> context." `[field]`
> "A highly-retrieved memory about details (like a user's employer) becomes
> confidently wrong when circumstances change — staleness in high-relevance
> memories is a harder, open problem." `[field]`

In a shared brain the blast radius multiplies: one stale "architectural
decision" memory steers *every* teammate's agent wrong, silently. Governance
becomes a liability concern, not just an efficiency one `[field]`.

- **CH mechanism:** **versioning + `as-of` + `valid_until` + supersession** ✓
  — CH already models temporal truth most rivals lack (the literature is
  *converging on* SUPERSEDES edges CH shipped). **Gap:** no *decay*/recency
  weighting so stale-but-unsuperseded memories still rank high → **P4**. And
  retrieval must *show* the as-of/age so a reader can distrust it → **P1 (H2
  provenance)**.

## P2 — Multiple versions of the truth; conventions agreed with one agent are invisible to the rest

> "Multiple team members can have different versions of the truth — one
> developer's agreed conventions with an agent are unknown to others,
> resulting in inconsistent code styles." `[field]`
> "Different agents may write facts that contradict each other, and outdated
> information may not be removed and still retrieved later, which can mislead
> reasoning." `[paper]`

The literature is actively chasing this: **Rashomon Memory** (parallel
goal-conditioned agents negotiate at query time) `[paper]`, **sheaf-theoretic
contradiction detection at store time → SUPERSEDES edges** `[paper]`, Mem0's
LLM dedup/update `[field]`.

- **CH mechanism:** contradiction detection + supersession ◐ (exists, but tuned
  for self-conflict). **Gap:** **cross-actor** conflict surfacing — "you wrote X,
  a teammate wrote not-X" with both provenances — is the co-work form → **P1
  (conflict surfacing + H2)**.

## P3 — Tribal knowledge evaporates; onboarding restarts from zero

> "When senior engineers leave, they take tribal knowledge with them; AI
> coding assistants inherit this problem in a more acute form — a model reads a
> file in isolation with no access to the organizational memory that explains
> the *why*." `[field]`
> "Implicit rules discovered during debugging are never documented, forcing
> teams to restart when similar problems appear." `[field]`
> "If one developer establishes a new pattern in a conversation with the AI,
> other team members benefit from that decision in their own sessions." `[field]`

`AGENTS.md` is the low-tech version of this — centralize tribal knowledge so
agents behave consistently `[field]`. CH's bet: a *queryable, temporal,
cross-actor* brain beats a flat file that nobody updates.

- **CH mechanism:** episodes → distill ✓ (debugging sessions become semantic
  nodes), graph edges ✓, communities ✓. **Gap:** the *shared* surface —
  team scoping + **who-knows-what** ("who decided this / who's the expert on X")
  → **P1**. Plus the [[common-knowledge]] bridge already lets a local agent
  push learnings up.

## P4 — Nobody can tell a vetted decision from an unverified scrape

> Shared knowledge needs access control "without exposing private data";
> "stale or conflicting definitions are not just inefficient — they are
> liability." `[field]`

When the brain holds a teammate's signed-off decision *and* an agent's
half-confident web scrape with equal weight, the reader can't calibrate trust.
gbrain's `whoknows`/evidence contract exists precisely for this `[inf]`.

- **CH mechanism:** nodes carry `created_by` ◐ but retrieval/answer ignore it.
  **Gap:** **provenance + trust-tier on every retrieved source** (actor,
  source, time, why-matched) → **P1 (H2)** — also the H1 injection mitigation.

## P5 — Shared + untrusted memory is a live attack surface (the co-work security tax)

> The **"Lethal Trifecta"** — access to private data, exposure to untrusted
> input, and a path to exfiltrate — turns prompt injection into a practical
> incident, not theory. `[sec]`
> "Five carefully crafted documents can manipulate AI responses 90% of the
> time through RAG poisoning." `[sec]`
> Documented incident: a Google Docs file triggered an AI IDE agent to fetch
> instructions from a malicious MCP server and run a Python payload that
> harvested secrets — **no user interaction.** `[sec]`

Co-work *is* the trifecta: a shared brain holds private data, ingests content
written by other people/agents (untrusted), and answers via an LLM that can be
steered. One poisoned node → every teammate's answer is attacker-controlled.

- **CH mechanism:** perimeter is solid (isolation, SSRF, no RCE — see
  `Context-Heavy/docs/SECURITY_AUDIT.md`). **Gap:** **prompt-injection-via-
  shared-memory** — retrieved notes are concatenated raw into the prompt with
  no delimiting/instruction-hierarchy (audit **H1**) → **P1 build + CH-Bench
  injection track**; trust-tiering (H2) down-weights low-trust sources → **P1**.

## P6 — Cross-project / cross-thread contamination

> "An agent operating across multiple projects or conversation threads may
> accumulate contradictory memories." `[paper]`
> "Episodic memory in AI agents poses risks that should be studied and
> mitigated." `[paper]`

A writer's two universes, a founder's two companies, a dev's two repos — memory
from one must not bleed into another, and the *same* agent should behave
differently per project.

- **CH mechanism:** `workspace_id` isolation ✓ + **profiles/personas** ◐
  ([[per-project-persona-vision]]). **Gap:** persona resolves into
  retrieval/write/**exposure** policy (personal vs shared scope) → **P1**.

---

## Frequency / weight (qualitative, from the corpus above)

| pain | how often it shows up | severity in co-work | CH phase |
| --- | --- | --- | --- |
| P1 stale shared knowledge | very high (every vendor post) | high (team-wide) | P4 decay + P1 show-age |
| P2 conflicting / divergent truth | very high (papers + field) | high | P1 conflict + H2 |
| P3 tribal-knowledge loss / onboarding | very high (dev-focused) | high | P1 who-knows |
| P4 no trust tier on sources | high (governance) | high | P1 H2 |
| P5 poisoned / injected shared memory | high + rising (sec) | **critical** | P1 H1 + bench |
| P6 cross-project contamination | medium (papers) | medium | P1 persona scope |

**Read-out:** five of six top pains are **trust/freshness/isolation**, not raw
recall — exactly where CH's temporal model + the P1 co-work build aim. CH
already ships the hardest-to-build piece (temporal supersession the literature
is still writing papers about); the missing pieces are **provenance display,
cross-actor conflict surfacing, who-knows-what, injection hardening, and decay**
— P1 covers four, P4 covers decay.

---

## Sources

- MindStudio — [Share AI Agent Memory Across a Team](https://www.mindstudio.ai/blog/share-ai-agent-memory-team-access-control),
  [Shared vs Private AI Agent Memory: Access Control](https://www.mindstudio.ai/blog/shared-vs-private-ai-agent-memory-team-access-control) `[field]`
- Mem0 — [State of AI Agent Memory 2026](https://mem0.ai/blog/state-of-ai-agent-memory-2026) `[field]`
- Ai Disruption (Meng Li) — [Small-Team Coding Agent KB Management](https://aidisruption.ai/p/small-team-coding-agent-kb-management) `[field]`
- Cloudflare — [Introducing Agent Memory](https://blog.cloudflare.com/introducing-agent-memory/) `[field]`
- Augment Code — [AI-First Dev Workflows for Enterprise Teams](https://www.augmentcode.com/guides/ai-first-dev-workflows-for-enterprise-teams) `[field]`
- BuildBetter — [AGENTS.md Complete Guide for Engineering Teams (2026)](https://blog.buildbetter.ai/agents-md-complete-guide-for-engineering-teams-in-2026/) `[field]`
- Tech Jacks — [The Context Problem in Enterprise Agentic AI / Meta's Tribal Knowledge](https://techjacksolutions.com/ai-brief/the-context-problem-in-enterprise-agentic-ai-what-metas-trib/) `[field]`
- arXiv — [Rashomon Memory: Argumentation-Driven Retrieval for Multi-Perspective Agent Memory](https://arxiv.org/pdf/2604.03588) `[paper]`
- arXiv — [SuperLocalMemory V3 (sheaf-theoretic contradiction detection)](https://arxiv.org/pdf/2603.14588) `[paper]`
- arXiv — [Episodic memory in AI agents poses risks](https://arxiv.org/pdf/2501.11739) `[paper]`
- arXiv — [Rethinking Memory Mechanisms of Foundation Agents: A Survey](https://arxiv.org/pdf/2602.06052) `[paper]`
- Atlan — [How Prompt Injection Attacks Compromise AI Agents in 2026](https://atlan.com/know/prompt-injection-attacks-ai-agents/) `[sec]`
- Vectra — [Prompt injection: types, real-world CVEs, enterprise defenses](https://www.vectra.ai/topics/prompt-injection) `[sec]`
- Christian Schneider — [From LLM to agentic AI: prompt injection got worse](https://christian-schneider.net/blog/prompt-injection-agentic-amplification/) `[sec]`
- arXiv — [Your LLM Agent Can Leak Your Data: Exfiltration via Backdoored Tool Use](https://arxiv.org/pdf/2604.05432) `[sec]`
