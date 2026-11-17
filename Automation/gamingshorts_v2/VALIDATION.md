# Current maintenance validation

The [V3 full-game release](../../docs/V3_FULL_GAME_2026-11-12.md) passes 160 tests,
including accelerated seven-hour/60 GB metadata, overlap, validation/index/batch
recovery, source identity, visual diversity and explicit analysis retry fixtures.
Real H.264, HEVC and AV1 decode fixtures pass. Index media, complete render/mix
and karaoke handoff checks pass without AI calls. A real 60 GB throughput/RAM
benchmark and AI editorial production remain untested until the source is supplied.

The [quality repair](../../docs/QUALITY_REPAIR_2026-11-12.md) passes 128 regression
tests, the full media smoke test and the synthetic word-to-karaoke render test.
The real source-fragment delivery passes full decoding, narration and cadence QC.
All 98 baseline project/export/database files retain their original hashes.
New exports have no spoiler card; historical approvals remain intact.

The [staged-integrity release](../../docs/INTEGRITY_PIPELINE_2026-11-12.md) passed
110 regressions and a real 25-second render/QC fixture. It adds full checksums,
content deduplication, packet integrity, cached full video decoding, bounded
progress watchdogs, additive old-queue migration and unchanged-output checks.

The [prequeue validation release](../../docs/PREQUEUE_VALIDATION_2026-11-12.md)
passed 81 regression tests and the real media smoke fixture. Admission failures
include actual FFprobe stderr, with real corrupt, empty and audio-only fixtures.

The later [automation release](../../docs/AUTOMATION_2026-11-12.md) adds durable
queue, word-timestamp retention and a targeted FFmpeg tail fix. Its test logs
and full release evidence are in `Releases/2026-11-12-automation/` at the workspace
root. The earlier validation below describes the preceding formatting release.
The automation release passed 72 regressions, fresh phrase/karaoke renders,
missing-narration rejection, and 100 corrected audio-graph duration trials.

12 November 2026: 49 offline regression tests and the real synthetic media smoke
test passed in Ubuntu/WSL. See [the maintenance report](../../docs/MAINTENANCE_2026-11-12.md)
for exact scope, artifacts and limitations. The smoke fixture now pins phrase
caption settings independently of the production karaoke configuration.

## Historical validation — GamingShorts 2.0.0 / PC Audit V2

Build date: 11 November 2026.

## Executed checks

- 20 Python regression tests passed. Cases cover changed narration, altered WAVs,
  duration changes, unverified legacy WAV/full-audio reuse, failed QC, repeated hooks,
  same-project rejection memory, preservation of multiple feedback notes, footage
  overlap, retained reservations after feedback, atomic writes, and process locking.
- A real 25-second, 1080×1920 FFmpeg fixture rendered and fully decoded successfully.
  It used five separately generated synthetic audio signals and the supplied music.
  No external AI/TTS service was called for this test.
- All five final audio windows passed: narration-to-music RMS margins approximately
  12.5–13.2 dB, correlation with the narration stem approximately 0.973–0.980.
- A deliberately broken music-only final video was rejected for all five missing
  narration windows despite still having a valid audio track.
- Changed plan content invalidated the completed-render check.
- Whole/dense contact-sheet generation ran; source timestamps and caption/CTA frames
  were visually inspected. Timestamps are burned before resampling to avoid rounding
  them to the contact-sheet frame interval.
- The Windows audit script parsed with the official PowerShell parser and executed
  its synthetic collection/export path under portable PowerShell 7.4.6 on Linux.
- The resulting XLSX was independently reopened with openpyxl. Tested fields include
  literal '=1+1' text (not a formula), Unicode, an empty section, and a row retained
  before a deliberately thrown collection error.
- Installer checks source checksums/syntax, installs into a separate directory, and
  refuses to overwrite an existing V2 directory. A temporary-root installation and
  second-install preservation check are part of release verification.

## Problems caught while building

- A multi-input FFmpeg loudness-filter graph produced incorrect narration timing on
  the test build. The final renderer normalizes each voice file to a finite WAV first,
  then mixes those files with explicit duration limits. The end-to-end test passed.
- A SQLite literal/column-name ambiguity could discard validated status when adding
  feedback. SQL literals were corrected and a regression test now protects this.
- Contact-sheet timestamp resampling shifted displayed times. Burning source timestamps
  before temporal resampling corrected this, verified on a known 5-second offset.

## Explicit limits

- Live Codex planning and HeyGen MCP speech generation were not executed here. They
  depend on the already-configured CLI/login/plugin on the user's WSL environment.
  `--doctor` checks local CLI support/login but does not spend speech generations.
- The actual Windows system collectors and Windows PowerShell 5.1 have not been run
  on the user's PC. Run Test-Audit-V2.cmd first, then the real administrator audit.
- Audio fixture tests establish mixing/routing/QC behavior, not human speech quality
  or transcript correctness. Review real narration before publication.
- Novelty combines stored history, model instructions and lexical checks; it cannot
  guarantee creative originality. Rejection feedback remains available for replanning.
- Video crops are centered; review whether the important gameplay stays in frame.
- CTA uses a returned word onset if available and valid, otherwise an explicitly
  reported approximate final 1.7-second overlay. Legacy audio generally uses fallback.
- Black/freeze detections are warnings because intentional game footage can contain
  dark or still moments. They are not an automatic artistic judgement.
- Technical validation and user approval are separate. No automatic publishing,
  source deletion, paid REST API fallback, or Windows scheduled task is included.

## Reproduce the offline tests in Ubuntu

From the installed GamingShorts V2 directory:

```bash
python3 start.py --self-test
python3 tests/render_smoke.py
```

The render fixture uses temporary files and no external AI service. It takes longer
than the unit tests and generates a full-resolution synthetic video for validation.

For the audit fixture, double-click Test-Audit-V2.cmd in Windows. It writes a temporary
synthetic report and must finish with SELF-TEST PASSED before running the real audit.
