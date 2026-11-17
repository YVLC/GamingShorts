# Spoken hooks, yellow words and the existing Music folder

The user requested a revision of the same crystal and birthday edits, restoring
Garret narration and the existing yellow active-word captions. Earlier silent
gameplay-first previews remain preserved; these are revised versions of two
events, not two newly discovered stories.

`dialogue_narration_preference` now records the preferred short added-value hook.
Future uncached story comparisons receive that preference. Narration still
requires independent nonredundancy, visual-evidence and editorial review.
The hook precedes the game dialogue: five contiguous source seconds are added
at the beginning, and actual generated speech must finish before the verified
dialogue captions begin. No character speech is recreated from this silent
recording. Existing real HeyGen word timestamps drive yellow highlighting.
Final reading holds remain explicitly declared and bounded to two seconds.

`dialogue_music_track_ids` records the three approved NCS songs already in
`Music`. Explicit plan `music.track_ids` restricts selection to cleared named
library entries. Audio and evidence hashes, attribution, rotation, segment
selection and publication safeguards remain enforced. A missing or uncleared
requested song fails clearly instead of generating a substitute. The chosen
regular releases can contain vocals; no instrumental version or additional
rights are inferred. Existing segment evidence remains labeled verified or
inferred as appropriate.

Continue this revision in WSL, from `/mnt/d/GamingShorts`:

```bash
python3 tools/resume_hybrid_hooks.py
```

The existing mission and workflow locks prevent concurrent production. The
controller reuses saved hook plans, source reviews, speech and completed
outputs. Uncertain speech attempts are never automatically retried. A blocked
candidate stays blocked until its reported cause is resolved explicitly.

New previews and their actual status are under
`ReadyForReview/cairn_first_three_1b28a5dd9e1b/hybrid_hooks_v1/REVIEW_REPORT.md`.
New checkpoints, tests and logs are under
`Releases/2026-11-14-hybrid-hooks`. No new source index or publication is started.
