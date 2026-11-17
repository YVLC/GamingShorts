# Expanded Cairn discovery and spoiler policy

The user disabled spoiler restrictions on 14 November 2026. Installed configuration
sets `spoiler_filtering: false` and `spoiler_warnings: false`. V3 eligibility,
planning prompts, evidence-review acceptance, major-ending guards and review-file
delivery honor this policy. Stored labels remain unchanged; spoilers are not
relabelled as ordinary gameplay. Warning titles/cards and special major-spoiler
approval are disabled. Publication still requires separate human approval.

The original mission `1b28a5dd9e1b` remains active. The earlier story request timed
out before this change; its request/logs remain untouched. The held planning batch
is resumed with new policy, candidate pool and evidence, without `--retry-ai` or a
voice retry. Mission/workflow locks prevent duplicate controllers. A one-time
policy-resumption marker permits only a planning batch with no queued job and no
accepted edit plan; it cannot retry production or uncertain speech.

All 260 existing observations are reevaluated. Base eligibility expands from 20 to
95 scenes. These are not 95 distinct stories. A cached semantic pass accounts for
every technically eligible scene, grouping repeated observations and repeated core
mechanics into 25 provisional event families. Eighteen families are provisionally
suitable in the first pool; these counts do not constitute independent visual originality approval.
The current unused pool can shrink after reservations, holds and history updates;
timestamped `CREATIVE_DISCOVERY_REPORT_*.md` snapshots distinguish that pool from
all completed production stories. Physical-event categories are ranking hints,
not evidence or originality approval. All availability/duplicate gates still run.
Additional source-wide analysis is not necessary while this pool remains viable.

One model metadata warning referred to a nonexistent rejected identifier. It is
retained as a warning, not counted as real footage or a real rejection. Unknown
members of an event family are rejected, and all real eligible IDs must still be
accounted for exactly once. Raw model receipts remain unchanged.

Discovery ranks across event families rather than twelve versions of one routine.
Families with reserved footage are excluded. Cached 2 fps proxies provide bounded,
absolute-timestamp discovery sheets. Up to 40 seconds of a promising scene are
covered in adjacent windows of at most 14 seconds, so its outcome is not always
truncated. Selected exact windows are re-inspected from original footage before
approval; final rendering also uses the original. No source copy or intermediate
4K analysis render is created.

All footage, evidence, originality, payoff, music-licensing and technical gates
remain mandatory. One separately cached corrective response is allowed after a
completed concept response fails validation; the same validators run again. An
all-positive independent review with advisory issues is not accepted: at most one
clarification review may distinguish actual script violations from hypothetical
claims. The final acceptance predicate is unchanged: all required checks true,
confidence at least 0.85, supported event/outcome/evidence and no unresolved issues.
No uncertain model or speech request is blindly repeated.

The live report is in the existing review folder:

- `ReadyForReview/cairn_first_three_1b28a5dd9e1b/CREATIVE_DISCOVERY_STATUS.md`
- `ReadyForReview/cairn_first_three_1b28a5dd9e1b/CREATIVE_DISCOVERY_STATUS.json`

It lists each premise, exact source ranges, independent review state/reason,
rendering state, actual QC and preview paths. Candidate families remain labelled
provisional until independently reviewed. Synthetic regression/render fixtures are
reported separately from actual Cairn output QA. Nothing is published automatically.

Release evidence, regression results, render smoke evidence and the pre-change
SQLite/config/code snapshot are in `Releases/2026-11-14-expanded-discovery`.

Do not launch another mission while one is running. After interruption, inspect
existing pending outcomes before resuming; the ordinary authorized continuation
entry point remains `python3 tools/resume_full_workflow.py` in WSL.
