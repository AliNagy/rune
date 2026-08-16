---
name: rune-research
context: fork
allowed-tools: Skill, Read, Glob, Grep, Write, WebSearch, WebFetch
user-invocable: false
description: Use when a question needs evidence from outside this repository - prior art, library or vendor evaluation, spec and protocol detail, security advisories, benchmark claims, current best practice, or "how does everyone else solve this". Runs a systematic search, grades every source, and terminates in a cited written answer.
---

# Research protocol

**Governing rule: every claim traces to a source you actually retrieved, and every source
is graded. An ungraded claim is an opinion wearing a citation.**

This protocol exists because of one specific failure mode. A model asked a factual
question will answer from training data, write it in the confident register of something
looked up, and attach a plausible-looking link it never opened. The answer is often
roughly right, which is what makes it dangerous — it is wrong in the details that made
the question worth asking, and nothing in the output distinguishes it from real research.

The dispatch includes absolute `main_root`, a parent-assigned `RES-nnn`, and exact absolute
staging and final output pointers. Resolve every coordination write against it; never use
the research worker's starting directory, scan for the next id, or derive a report path.

Before the first query, require the staging path to be
`<main_root>/.rune/notes/open/RES-nnn.md`, the final path to be
`<main_root>/.rune/notes/RES-nnn.md`, and both paths to use the assigned id and be absent.
A missing, relative, mismatched, or occupied assignment is `research: blocked` before any
search begins.

Everything below is machinery for making that failure impossible to commit silently.

## 0. Capabilities, not tools

**This protocol names no tools, and must not be edited to name any.** Rune runs under
more than one harness and they expose different ones. What is required is three
capabilities:

| Capability | What it means here |
|---|---|
| **search** | Issue a query against a web index and get back candidate results |
| **retrieve** | Fetch the actual content at a specific address |
| **record** | Write files under `<main_root>/.rune/` |

Use whatever your harness provides for the first two. If it provides neither, or they are
blocked, **stop and report that** — see §9. Do not fall back to memory and do not
improvise a substitute.

**Run as a subagent, and take exactly one question.** Research burns context by design;
that cost is quarantined in a worker that returns a digest and dies. Two questions means
two dispatches — sources gathered for one question bias the reading of the next, and a
single certainty grade cannot honestly cover two bodies of evidence.

## 1. Fix the question before you search

Write the question down first, and the criteria with it. Searching first and stating the
question afterwards guarantees the question drifts to match whatever you happened to find.

Record, before the first query:

- **Question** — in a shape that admits an answer, per `rune-investigate` §1.
- **Scope** — versions, dates, platforms, languages the answer must cover. "Is this
  library maintained" is unanswerable; "has this library shipped a release or merged a
  non-trivial PR in the last 12 months" is answerable.
- **Inclusion / exclusion criteria** — what kind of source you will accept before you
  know what they say. Deciding this after seeing the results is how you end up admitting
  exactly the sources that agree with you.
- **What would change the answer** — name the finding that would flip your conclusion.
  If nothing could, you are not researching, you are confirming.
- **Budget** — queries and time. Research expands to fill whatever it is given.

Examples of shaping:

- "Is Postgres or Mongo better" → "for our access pattern — 50 writes/sec, heavy
  relational reads, single region — which of these two has the more direct support, and
  what do teams who switched report as the cost"
- "Is this npm package safe" → "what advisories exist against this package or its
  transitive dependencies, what is its maintenance signal, and who else depends on it"
- "Best way to do auth" → too broad. Split it, or bound it to your stack and threat model.

## 2. Search strategy

Breadth before depth, exactly as in `rune-survey`. One query formulation finds one
neighbourhood of the web and you will mistake it for the whole map.

Run **at least five distinct formulations**, covering these angles. They are not optional
variations on each other — each one surfaces a different population of sources:

1. **Plain language** — the question as a user would type it.
2. **Term of art** — the name the field uses. Vendors, academics, and practitioners name
   the same thing differently; each vocabulary has its own literature.
3. **The negative case** — "<thing> limitations", "<thing> considered harmful", "why we
   moved off <thing>", "<thing> postmortem", "<thing> vs". This angle is mandatory, not
   optional. Advocacy is over-published and criticism is under-indexed, so the balanced
   picture requires asking for the second half explicitly.
4. **Primary source** — the spec, RFC, standard, official documentation, changelog,
   release notes, issue tracker, or source repository. Always attempt this angle. Most
   technical questions have an authoritative answer that secondary coverage garbles.
5. **Time-bounded** — bound to a recent window, and separately to the period when the
   thing was introduced. Comparing the two is how you detect that the consensus moved.
6. **Adjacent field** — the same problem as another ecosystem or discipline states it.

Then follow the citation graph in both directions:

- **Backward** — what does a good source cite? Read its sources, not its summary of them.
- **Forward** — who cites it since? This is how you find the retraction, the correction,
  the benchmark that failed to replicate, or the advisory filed against it.

**Log every query verbatim as you go.** The search log is part of the deliverable (§10).
An answer nobody can re-derive is not a finding, it is a claim.

## 3. Source tiers

Grade every source before you use it. The tier caps the certainty of any claim resting on
it — a Tier 4 source cannot support a High-certainty claim no matter how well written.

| Tier | What it is | Examples |
|---|---|---|
| **1 · Primary / authoritative** | The thing itself, or its maintainers speaking officially | Spec, RFC, standard, source code, official docs, changelog, advisory database, filed issue |
| **2 · Peer-reviewed or formally reviewed** | Published under adversarial review | Journal or conference paper, standards-body draft, audit report |
| **3 · Practitioner report with method** | First-hand experience, method stated, numbers shown | Engineering blog with reproducible benchmark, detailed postmortem, conference talk with data |
| **4 · Secondary synthesis** | Someone summarising others' work | Tutorials, listicles, news write-ups, forum answers, documentation aggregators |
| **5 · Unverifiable** | Undated, anonymous, method-free, or plausibly machine-generated | Content farms, SEO pages, undated "best X of" posts, unattributed claims |

**Tier 5 is not evidence.** It may be used as a lead — something to go verify at a higher
tier — and never cited in support of a conclusion.

Note the asymmetry: a vendor's own documentation is Tier 1 for *what their product does*
and Tier 5 for *whether it is better than a competitor's*. Tier is per claim, not per
domain.

## 4. Assessing a source

Five checks on every source you intend to cite. This is ordinary source criticism; the
discipline is in doing it every time rather than for the ones that feel doubtful.

- **Authority** — who wrote it, and what makes them able to know this? A named engineer
  at the project beats an anonymous post. Check whether they are describing something
  they did or something they read.
- **Currency** — when was it written, and what version was it about? Undated technical
  content is nearly worthless; a correct answer about v2 is a wrong answer about v5.
  Record the date and the version with the citation, always.
- **Purpose and interest** — what does the author gain if you believe this? Vendor
  benchmarks favour the vendor. Migration stories are written by people who migrated.
  This does not disqualify a source; it means corroborate it from somewhere with a
  different interest.
- **Method** — for any quantitative claim: is the method stated well enough to repeat?
  A number without a method is a vibe with a decimal point.
- **Corroboration** — does anything independent agree? See §5, which is where "independent"
  gets defined, because it is the check most often faked.

## 5. Triangulation, and what independence actually means

**Any load-bearing claim needs at least two independent sources.** Load-bearing means the
answer changes if the claim is wrong.

Most apparent corroboration is not independent. Ten pages saying the same thing usually
means one origin and nine copies — and the count feels like evidence while adding none.
Before counting two sources as agreeing, check:

- **Do they share an origin?** Follow each back. If both trace to the same benchmark,
  same paper, same original post, that is **one** source with two mouths.
- **Do they share an author, employer, or funder?**
- **Does the wording match?** Copied phrasing means a copied source, not agreement.
- **Which came first?** If B postdates A and cites nothing else, B is an echo.

When you cannot establish independence, say so and grade the claim down. "Widely
reported" is a description of the internet, not a form of verification.

## 6. Look for the refutation

Before concluding, **spend part of the budget trying to break your own answer.** Not a
gesture — a real attempt, with its own queries, run after you know what your conclusion
is and aimed squarely at it.

- Search the negation of your conclusion directly.
- Find the strongest source that disagrees and read it properly, at full strength.
- For any benchmark or performance claim: search for a failed replication.
- For any recommendation: search for who regretted following it.

Then report what you found in the mandatory contradicting-evidence section (§10) — even
when it did not change your conclusion, and *especially* when it did not. A research
document with no contradicting evidence section is one that did not look.

## 7. When to stop

Stop at whichever comes first, and **record which one stopped you**:

- **Saturation** — two consecutive new query formulations, from different angles in §2,
  surface no source you have not already seen. This is the good ending; the field has
  been covered.
- **Budget** — you hit the limit set in §1. This is a legitimate ending, but it means
  coverage is unknown and the certainty grade must reflect that.

Stopping because you found an answer you like is not a stopping rule. The first solid
finding is where confirmation bias starts, not where research ends.

## 8. Grading certainty

Grade the **answer**, and any claim that carries it. Four levels, and the grade must come
with its reasons.

| Grade | Means |
|---|---|
| **High** | Multiple independent Tier 1–2 sources agree; you searched for and found no substantive contradiction |
| **Moderate** | Good sources, but one of the downgrades below applies |
| **Low** | Thin, indirect, dated, or contested evidence |
| **Very low** | One source, uncorroborated, or Tier 4 only. Report it as a lead, not an answer |

**Downgrade for any of these, and name the one that applied:**

- **Interest** — the sources benefit from the conclusion.
- **Inconsistency** — good sources disagree and you cannot explain why.
- **Indirectness** — the evidence is about a near neighbour: different version, different
  scale, different platform, a lab benchmark standing in for production.
- **Imprecision** — a single data point, tiny sample, or no error bars.
- **Silence bias** — only successes get written up. Nobody blogs the migration that was
  uneventful, or the library that was fine.

**Upgrade only for:**

- Independent replication by parties with opposing interests — a competitor confirming a
  claim is worth more than ten neutral repetitions.
- A primary measurement you ran yourself and can re-run.

## 9. Fabrication rules — absolute

These are not guidelines and there is no case where they bend.

- **Never cite a source you did not retrieve in this session.** Not one you are confident
  exists. Not one you remember reading.
- **Never reconstruct an address from memory.** If you believe a page exists, search for
  it and retrieve it. If retrieval fails, it does not exist for the purposes of this
  document.
- **Load-bearing claims carry a verbatim quote** from the retrieved text, so a reader can
  check that the source says what you say it says.
- **Mark every statement as sourced or inferred.** Inference is welcome and often the
  most valuable part — labelled. Unlabelled inference in a cited document reads as fact.
- **Training data is not a source.** It is a lead generator: useful for knowing what to
  search for, never admissible as evidence. It is also stale by construction and cannot
  tell you it is stale.
- **If search or retrieval is unavailable, stop.** Say plainly that the capability was
  missing or blocked, report what could not be established, and return. Answering from
  memory while formatted as research is the single worst outcome this protocol can
  produce — worse than no answer, because it is indistinguishable from a real one.

## 10. Output

Write the complete report only to the assigned
`<main_root>/.rune/notes/open/RES-nnn.md` staging path. Validate it in a collision-resistant
sibling candidate and atomically install it at staging with no-replace semantics; the
operation must fail if staging exists, and the worker also refuses an existing final. The
parent validates and atomically promotes that unchanged staging file to
`<main_root>/.rune/notes/RES-nnn.md` after return. `RES-` is its own ID space and does not
collide with task or drift IDs.

```markdown
# RES-007 · Is `fastjson` safe to adopt for the ingest path
asked: 2026-08-06     researched: 2026-08-06

## Question
Does fastjson have unresolved security advisories, and is it maintained well enough to
depend on for untrusted input?

## Answer
No — two unpatched deserialisation advisories affect all released versions, and the last
maintainer commit was 14 months ago. Do not use it on untrusted input.

## Certainty
**High.** Two independent Tier 1 sources (the advisory database entry and the project's
own issue thread acknowledging it), plus directly observable repository activity.
No downgrade applied.

## Evidence
| Claim | Source | Tier | Dated | Independent of |
|---|---|---|---|---|
| CVE open against all versions | advisory DB entry | 1 | 2026-03-11 | project |
| Maintainer acknowledged, no fix | project issue #4412 | 1 | 2026-04-02 | advisory DB |
| Last commit 14 months ago | repository history | 1 | retrieved 2026-08-06 | both |

> "We are aware of the deserialisation issue and do not currently have capacity to
> address it." — issue #4412, maintainer, 2026-04-02

## What contradicts this
One Tier 3 engineering post (2026-05) reports running it in production safely — but only
behind a schema validator on trusted input, which is a different threat model, not a
counter-example. No source claims the advisories are fixed.

## What I could not establish
Whether the fork `fastjson-ng` carries the fix. Its README claims so; I could not find a
commit implementing it and did not read the full diff.

## Search log
1. "fastjson vulnerability" — plain
2. "fastjson CVE deserialization" — term of art
3. "migrating off fastjson" / "fastjson considered harmful" — negative case
4. advisory database, direct — primary
5. "fastjson 2026" — time-bounded
6. forward citations from the advisory entry
Stopped on: saturation (queries 5 and 6 surfaced nothing new)

## Sources
1. <address> — advisory DB entry, retrieved 2026-08-06
2. <address> — project issue #4412, retrieved 2026-08-06
3. <address> — repository commit history, retrieved 2026-08-06
4. <address> — engineering post, Tier 3, retrieved 2026-08-06
```

**Five sections are mandatory: answer, certainty, what contradicts this, what I could not
establish, search log.**

The last three are what separate research from assertion. An answer that reports uniform
confidence, names nothing against itself, and cannot be re-derived is exactly what a
fabricated one looks like — so a real one must be visibly different.

## 11. Research does not schedule work

Findings are findings. They do not enter the ledger, do not become task files, and do not
get an ID in the `T-` space.

If the research settles an open decision, it belongs in `decisions.md` as the evidence
behind that decision — recorded by whoever owns that file, per `rune-taskfmt`, not by you.
If it says the plan is wrong, that is `rune-drift`. If the user wants the recommendation
built, that is a separate `rune-work` invocation which will triage it properly.

The gap between "here is what the evidence says" and "I have begun acting on it" is the
point of this protocol, exactly as in `rune-investigate`. Do not close it on your own
initiative.

## 12. Return (≤200 tokens)

```rune-return
work: RES-007
summary: two unresolved advisories make the package unsafe for untrusted input
research: answered | blocked
worktree: none
artifact: /workspace/acme/.rune/notes/open/RES-007.md # answered only
```

Return only the assigned id and staging pointer. Never write the final report path or
substitute a nearby unused number.
