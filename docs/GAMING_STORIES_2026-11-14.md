# Story-led gaming Shorts

New projects use `gaming-stories-v1`. This supersedes the earlier dialogue-hook
and read-aloud preferences. Existing projects, original footage, saved evidence,
voice recordings, outputs and approval records are preserved.

The planner seeks lore, secrets, easter eggs, beginner tricks, game facts, funny
moments, emotional character arcs and verified gaming trends. The rainbow walk
and Marco/Aava relationship are examples of angles, not evidence that can be
copied into an unrelated edit. An emotional or readable dialogue scene can be a
strong opening; physical action is not mandatory.

Each generated plan records its story type, viewer benefit, hook promise,
payoff evidence, narration's added value and evidence-linked claims. The script
develops a story instead of reading character dialogue or describing obvious
action. It resolves the hook and ends with `Subscribe for more.` over relevant
gameplay. Exact subtitle-reading scripts fail a literal guard; independent
semantic/visual review must also approve added value, the payoff, absence of
dialogue dubbing and CTA placement. These screens are not human approval.

Lore, secrets, tips and relationship claims need evidence from inspected footage
or supplied research. The planner does not invent canon, motives, outcomes or
mechanics. Optional `<project>/research.json` holds `sources`: each has a unique
`id`, HTTPS `url`, nonempty verified `excerpt`, `verified: true` and ISO
`checked_date`. Current-trend claims also need `platform` and evidence checked
within 30 days. A URL alone is not evidence. Research changes invalidate the
story review and render identity. Automatic web research is not implemented;
without supplied evidence the planner must not claim external facts or trends.

Music uses approved local tracks and existing rights/attribution checks. New
story plans specify `music.mood` and `music.allow_vocals`. Selection prefers mood
fit, instrumentals, recent cleared YouTube trend evidence, energy and rotation.
Vocal tracks are eligible only if explicitly allowed. A single fitting cleared
track can be reused instead of dropping the music. No fitting cleared track
stops before synthesis; no paid or generated substitute is silently introduced.
Local audio analysis does not prove a track is trending. Existing trend imports
and segment evidence distinguish verified popularity from inferred audio peaks.

Garret's existing voice and `heygen-voice-1-turbo-free` remain mandatory.
Narration is not sped up to fit footage. Actual returned word timestamps drive
yellow active-word captions across all spoken beats, including the final CTA.
No new HeyGen request is part of this code upgrade.

The old content-warning module, CLI flags, generated classifications, warning
cards and production/publication gates are removed. Its prior code/tests are
archived under `Releases/2026-11-14-gaming-stories/before`. The database migration
backs up the existing database, drops the retired scene column and retains all
other scene evidence and reservations. Historical exports remain untouched.
Plain manual-upload metadata continues to include exact rendered music credits.

Run normally in WSL from `/mnt/d/GamingShorts`. New plans use the new policy;
existing projects retain their saved plans and are never silently replanned.
Publication remains manual and approval remains tied to exact output bytes.

Validation artifacts, source snapshot and change manifest are under
`Releases/2026-11-14-gaming-stories`. Offline fixtures test generated-media
integrity; they do not establish live HeyGen delivery, editorial quality or
pronunciation.
