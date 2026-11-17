# Complete Garret dialogue readings

The user rejected the hook-only Crystal and Birthday previews because voice and
yellow highlights stopped after the opening. They explicitly requested that
Garret read all verified on-screen dialogue with yellow word highlights.

`tools/repair_dialogue_readaloud.py` creates versioned revisions of those same
accepted edits. It reuses the existing hook recordings and exact music files,
then adds saved free-model Garret readings of every verified dialogue line.
It does not request speech, rescan gameplay, change speech speed, or publish.
The resulting voices are narrator readings of text, not original character audio.

Real returned word timestamps are checked against every exact dialogue line and
the downloaded audio. Readings start at or after the verified source onset;
overflow delays later readings without cutting speech. Excessive final holds
fail rather than hiding missing footage. The original source bounds and framing
are retained. Every spoken section must pass audio presence, correlation and
voice/music balance checks in the encoded final video.

This is an authorized repair of the same delivered stories. Its admission checks
pin the accepted plan, review evidence bytes, original export bytes and original
recording identity. It does not claim a new originality review against later
history entries. Existing project plans and prior approvals are not overwritten.

Run from `/mnt/d/GamingShorts` in WSL:

```bash
python3 tools/repair_dialogue_readaloud.py
python3 tools/verify_dialogue_readaloud.py
```

The second command samples a spoken word in every dialogue line from the final
encoded files and checks actual yellow caption pixels. Reports and saved original
speech results are in `Releases/2026-11-14-dialogue-readaloud`. Review videos are
in `ReadyForReview/cairn_first_three_1b28a5dd9e1b/dialogue_readaloud_v1`.

Human listening and editorial review remain unperformed. Technical checks and
pixel checks do not establish pronunciation or natural delivery.
