# Prequeue video validation: 12 November 2026

Every new production-queue entry and explicit requeue now passes a central
FFprobe guard in `JobStore`. It checks probe success, error-level diagnostics,
a usable video stream, finite positive duration and unchanged file metadata
during probing. The worker also probes pre-existing queued inputs before planning.

Corrupt inputs remain outside the queue. Exceptions include the actual FFprobe
stderr and exit code; rejection reports retain them in
`AutomationLogs/rejected-inputs/`. Watcher discovery reports a rejection once per
unchanged size/mtime and continues processing other recordings. A repaired file
is reconsidered after it settles again, or after watcher restart.

Validation: all 81 offline regressions passed, including real FFprobe tests for
valid video, corrupt MP4, empty file, audio-only MP4, manual CLI rejection,
watcher continuation, repaired inputs, requeue protection, probe timeout and a
source changing during probing. A fresh media smoke render passed full decode,
mixed-audio QC and deliberate missing-narration rejection. No AI calls were made.

The admission check validates container/stream metadata, not every encoded frame.
Existing final decoding and render QC remain required. Renderer, caption code,
production config and standing preferences are unchanged. Complete before/after
source and checksums are in `Releases/2026-11-12-prequeue-validation/`.
