# Automation and cleanup release: 12 November 2026

The workspace now uses one active workflow with a durable recording queue.
`python3 start.py --watch` replaces the old collection of queue, splitter and
renderer watchers. It waits for recordings to settle, saves jobs in SQLite,
executes one child workflow at a time, and stops failures for explicit recovery.
The pipeline still ends with manual review and manual publication.

## Changes

- Added stable-file discovery, persistent job IDs, atomic claims, attempt logs,
  explicit resumption and interrupted-worker recovery. A busy manual workflow
  leaves queued jobs untouched. Existing, rejected, approved and published
  projects are protected from automatic rediscovery/restart.
- Preserved source survey caches, plan history, footage reservations, narration
  provenance and versioned media. The queue never authorizes `--retry-voice`,
  `--new-voice`, a paid fallback, source recycling or publication.
- Fixed the speech handoff to retain real returned word timestamps. They are
  checked against the exact transcript, phrase boundaries, audio duration and
  audio checksum, then used by the existing karaoke alignment path. Older
  results without word timings retain their optional local-alignment fallback.
- Removed 13 unused imports, a dead variable and a dead constant. Reused the
  common durable atomic JSON writer for speech-attempt markers and results.
- Replaced the installed runtime's historical installation/PC-audit guide with
  a current operations guide. Added an optional WSL user-service template.
- Fixed an intermittent FFmpeg speech-stem truncation: sample-count padding and
  trimming replace output-duration cutting. The baseline graph failed 1 of 30
  isolated trials (24.9 seconds instead of 25); the fixed graph passed 100 of 100.

The renderer change intentionally changes future render identities. Existing
videos, narration and approval files are preserved; resuming an old render under
the new renderer requires a new validated version and review. Visual shot-cache
identity remains unchanged because the fix only changes the mixed audio tail.
Caption code and production settings are unchanged.

## Cleanup evidence

The old workers were not running, no user crontab was present, and user timers
contained no GamingShorts job. Active imports retain their standalone V1-history
compatibility module, so they do not need the old V1 code directory.

- Archived and SHA256-verified 132 obsolete tool/package files before removing
  their loose copies. Original paths and hashes are in `retired-manifest.json`.
- Scanned 579 project/database string references before selecting duplicate
  failed-split fragments. Deleted 18 unreferenced, SHA256-identical copies,
  reclaiming 4.652 GiB. Every fragment has a retained identical copy.
- Left originals, unique fragments, voice assets, databases, project metadata,
  previous final exports and manual-plan helpers in place. Missing original
  recordings make some old split fragments worth retaining.

Cleanup used native PowerShell literal paths, workspace boundary/reparse-point
checks, verified ZIP extraction streams and a second SHA256 check immediately
before deleting duplicates. It did not run the old source-recycling code.

## Operation

From Ubuntu:

```bash
cd /mnt/d/GamingShorts
python3 start.py --doctor
python3 start.py --watch
```

`--queue` lists job states. `--enqueue --source PATH` records a chosen job;
`--work` drains queued jobs once. `--watch --stop-after plan` creates a planning
inbox for newly discovered recordings. `--retry-job ID` explicitly resumes a
stopped/planned/voiced job; speech uncertainty still requires separate recovery.

The service template is validated but not enabled. No live AI generation,
background watcher or publishing was started during maintenance. The runtime
guide contains optional service installation and stop commands.

## Verification artifacts

All 72 regression tests passed in Ubuntu/WSL. Fresh 25-second 1080x1920 phrase
and 720x1280 karaoke fixtures passed complete decoding and final mixed-audio QC;
the phrase fixture's deliberately music-only negative control failed all five
narration checks. The karaoke review sheet was visually inspected. Environment
checks also passed under the optional service template's exact PATH. The actual
queue was initialized empty and its no-work path completed without AI calls.

The first smoke attempt exposed the intermittent baseline speech-tail failure.
Its failure log and the retained 24.9-second counterexample remain alongside
the diagnostic rerender, 30 baseline audio trials, 100 corrected trials, and
fresh post-fix media results. The validation record includes that failure.

`Releases/2026-11-12-automation/` holds the complete before/after source release,
checksums, archived tools, cleanup ledger, test logs and synthetic media evidence.
Tests cover queue persistence, copy stability, source changes, failed children,
manual-workflow locking, rejection preservation, explicit retry, speech-timeout
protection, timestamp validation and cleanup reference guards.

Real fixture renders exercise phrase captions and the complete saved-result to
karaoke path. Synthetic tones and hand-authored fixture word times establish
plumbing and QC behavior; they do not establish real speech intelligibility,
creative quality or live tool compatibility. The actual new HeyGen word-array
handoff still needs its first live generation. No fabricated timings are accepted
as substitutes for missing live results.
