# Cairn AI analysis resumption — 14 November 2026

The installed WSL worker was stopped after 14 of 47 selected AI inspections.
Fresh read-only Codex rate-limit checks confirmed both usage windows had reset.
The stopped request was a definite quota rejection, not an uncertain speech call.
Its original request, log and empty output were preserved before resumption.

The quota detector now recognizes Unicode apostrophes in the provider's
“You've hit your usage limit” message. Local screening checkpoints are reused
directly during resumption; selected proxy receipts are still checked before AI
use, and complete native integrity validation remains required for production.

One later response proposed scenes outside its inspected chunk. Strict validation
rejected it before any scene commit. A single separately cached correction used
the same images and original bounds; the invalid original receipt remains intact.
No timestamp was silently shifted or clipped to force acceptance.

The 47 selected chunks span all 12 equal-duration time bands (at least three per
band). Their union is 5,460.146 seconds, about 91 minutes or 22.1% of the source.
The largest unsampled gap is 1,476 seconds. This is broad candidate sampling,
not exhaustive AI interpretation of the full 6h50 recording. All 217 chunks were
locally screened. Semantic/visual originality and footage reservation checks still
run against historical projects before speech or rendering. Major spoilers remain
held, and only eligible spoiler-free evidence enters automatic production.

Live artifacts:

- `Releases/2026-11-13-full-analysis/progress.json`
- `Releases/2026-11-14-ai-resume/coverage.json`
- `Releases/2026-11-14-ai-resume/review-status.json`
- `Releases/2026-11-14-ai-resume/preservation.json`
- `ReadyForReview/cairn_first_three_1b28a5dd9e1b/AI_RESUME_REPORT.md`

The release includes a consistent SQLite backup, runtime-source archive, file
checksums, and regression evidence (`tests.log`: 217 passing tests).
Preservation checks compare the original 217 local metrics and 47 selections,
prior complete chunks and prior scene identities, plus the source fingerprint.

After an interruption, first check for an existing worker. With no mission worker
running, resume using:

```bash
cd /mnt/d/GamingShorts
python3 -u tools/resume_full_workflow.py
```

Do not start a second worker or use broad `--retry-ai` to discard completed work.
The existing mission lock prevents parallel mission controllers. Narration,
licensing, synchronized captions, originality, spoiler and technical QA gates are
retained. Outputs are for review; no uploader is invoked. Technical QC does not
constitute human editorial approval.
