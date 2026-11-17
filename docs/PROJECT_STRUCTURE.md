# Project structure

## Active workflow

`start.py` at the workspace root forwards arguments to the installed V2 CLI.
Existing commands from `Automation/gamingshorts_v2/` continue to work.
Runtime configuration is `Automation/gamingshorts_v2/config.json`; standing
editorial requirements are in `preferences.json` beside it.
`GAMING_SHORTS_HOME` can override the configured data root.

V3 adds explicit full-game production through `start.py --v3`. Originals go in
`GameSources/GAME_ID/`, outside legacy auto-discovery. See the
[full-game guide](V3_FULL_GAME_2026-11-12.md) for registration, complete-recording
indexing, recovery and controlled batches. `game_store.py`, `game_index.py`,
`game_plan.py` and `full_game.py` extend the existing SQLite history and queue;
the renderer, audio/caption pipeline and manual publication remain shared.

```text
Sources -> settle observation -> durable queue -> prepare manifest -> survey/cache -> edit plan
     -> verified narration -> captions -> original-source render
     -> technical QC -> ReadyForReview -> human approval -> manual publication
```

| Module | Responsibility |
| --- | --- |
| `start.py` | CLI, project preparation, migration and stage orchestration |
| `automation.py`, `job_store.py` | Stable-file discovery, serialized worker, durable SQLite jobs and explicit recovery |
| `common.py` | Configuration, atomic JSON writes, hashing and process lock |
| `editorial.py` | Planning, novelty, SQLite feedback and footage reservations |
| `shared_index.py` | Shared source survey cache |
| `gaming_shorts.py` | Media validation, render identity, rendering and QC |
| `voices.py`, `voice_bridge.py` | Voice provenance, free HeyGen handoff and retained real word timestamps |
| `captions.py`, `align_worker.py` | Local word alignment and caption sidecars |
| `spoilers.py` | Historical warning compatibility; new warning/classification flow disabled |
| `render_sources.py`, `quality_checks.py` | Original fragment mapping, scale limits, cache provenance and motion-aware cadence QC |
| `audio_pipeline.py` | Waveform-safe narration boundaries and constant master gain |
| `music_library.py` | Music selection and license evidence |
| `publication.py` | Explicit publication verification and guarded intermediates cleanup |
| `benchmark.py`, `audio_checks.py` | Quality measurements |
| `inspect_recording.py`, `legacy_footage_db.py` | Recording inspection and older-history compatibility |

## Archived tools and retained data

Obsolete V1 code, old split/render workers, installers, patch packages and code
backups were removed from their loose locations after every file was verified
inside `Releases/2026-11-12-automation/retired-tools.zip`. The corresponding
`retired-manifest.json` records original paths, sizes and SHA256 values.
The duplicate root inspection script is archived; its active equivalent is
`Automation/gamingshorts_v2/inspect_recording.py`.

These data folders remain because they contain project history, unique footage,
outputs or still-useful manual-plan helpers:

| Location | Role |
| --- | --- |
| `ChatGPTPlans/` | Manual imports, direct-voice installers and quality experiments |
| `QualityAB_2026_11/` | Unique quality-comparison outputs |
| `SplitRetry/` | Retained split manifests/logs; duplicate MP4s removed with checksum evidence |
| `Ready/`, `Review/`, `Exports/`, `ReviewCopies/`, `ReviewExports/` | Outputs from separate tools or review experiments |
| `_QueueState/`, `_Processing/` | Old job records and surviving unique split fragments |
| `Audio/`, `Models/` | Shared audio assets and local models |
| Root Cairn manifests, images and preview scripts | Recording inspection artifacts |

Do not merge output folders or move project folders without migrating recorded
paths: manifests, SQLite rows, voice provenance and QC reports reference them.
Do not discard surviving split fragments: some original source recordings are
absent, making those fragments potentially irreplaceable. Eighteen unused
byte-identical copies were removed, retaining one verified copy of every fragment.

## Maintenance

Run `python3 tools/workspace_report.py` for a read-only inventory of top-level
folders, file counts and logical sizes. It excludes maintenance environments and
does not hash footage. Filesystem changes during a scan are reported as errors.

The root `.gitignore` separates source from generated media, secrets, databases
and local tooling if version control is introduced. This workspace currently has
no Git repository. Ignoring files does not back them up: retain the project,
database, source and output folders in normal backups.

Keep render/caption source byte checksums meaningful. Even cosmetic changes to
those modules invalidate existing render identities. A broad package relocation
also needs compatibility tests for saved importers and installed patch tools.
