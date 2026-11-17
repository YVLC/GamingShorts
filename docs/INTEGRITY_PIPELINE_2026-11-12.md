# Staged recording integrity: 12 November 2026

The durable queue now validates a recording's structure and identity before
admission, then verifies its bytes and decodes its video before planning or speech.
It preserves the previous queue API and adds columns/tables without replacing jobs.

## Before queueing

- Require an existing supported local recording and at least 60 seconds since
  its last modification. The watcher additionally observes unchanged file
  metadata across its settling window. Prefer copying to `.partial`, closing the
  file, then atomically renaming to `.mp4`.
- Run FFprobe with strict error detection and a complete packet-count walk,
  checking streams, recognized audio/video codecs, dimensions, nonempty video
  packet streams, and finite positive duration.
- Check top-level MP4/MOV atom extents, including required self-contained
  `moov`/`mdat` media, to detect truncation even when fast-start metadata survives.
  Do not decode frames at this stage.
- Compute full SHA256, verifying size, nanosecond mtime/ctime, inode and device
  before and after validation. Save only completed successful receipts.
- Deduplicate by content SHA256 plus requested story variant, atomically under
  a SQLite unique index. Renamed copies return the canonical job; same-path
  resubmission cannot reset attempts or uncertain speech. Explicit variants still
  allow a deliberately different story.
- Recognize renamed copies belonging to projects that predate the queue. Return
  their existing project for explicit resume without creating another job or
  altering existing project files.

Invalid inputs never enter the runnable queue. Their rejection JSON includes
the actual tool name, stderr and return code. Watcher discovery isolates failures
per file and continues checking other recordings. An unchanged rejected file is
not repeatedly probed during that watcher session.

## Before processing

Verify the queued size/mtime and full saved filesystem fingerprint. On a first
processing attempt, verify the SHA256 against the admission baseline, then fully
decode all video streams to FFmpeg's null muxer. Decode errors are fatal to that
job. Also require completed progress, positive frame output and completion to
the declared duration/frame count where available.

Decoding uses two decoder threads, creates no media output, and has both a
wall-clock deadline and a watchdog for non-advancing frame/timestamp progress.
Defaults (override in runtime `config.json` if needed):

| Setting | Default |
| --- | --- |
| `source_probe_timeout_seconds` | 300 seconds |
| `source_decode_timeout_seconds` | 7200 seconds |
| `source_decode_stall_seconds` | 60 seconds without advancing video progress |

Detected timeout or handled interruption kills/reaps the decoder subprocess. Complete FFmpeg
stderr is retained in the per-input rejection report and the job's attempt log,
and appears in the job's `error`. Failed jobs become `needs_attention`; the worker
continues with the next runnable job. Worker interruption still requires explicit
recovery and never authorizes another uncertain speech call.

## Avoiding repeated work

Successful admission receipts are keyed by path, complete filesystem fingerprint,
validator policy and FFprobe executable checksum. Successful decode receipts are
keyed by content SHA256 and FFmpeg executable checksum/policy. A verified
processing receipt is reused only for the identical file fingerprint and content.
Different explicit story variants can reuse a completed decode of identical bytes.

First admission requires a packet walk and checksum read. First processing
requires an independent checksum verification and one decode. Unchanged retries
reuse the successful receipt rather than repeating these full-file operations.
Project preparation receives the worker's verified digest, avoiding its former
redundant hash. The renderer's independent final source checksum remains intact.

## Backward compatibility and preservation

Old queue IDs, statuses, attempts, project/log pointers and errors survive the
additive migration. Old rows lacking checksums are validated and bound lazily on
first processing. Legacy duplicate rows remain as non-runnable history with a
`duplicate_of` reference, rather than being deleted. Existing project checksums
are consulted when available. Missing historical checksums cannot be reconstructed
retroactively; the current successfully validated bytes become that row's baseline.

Installed migration verification backed up the queue and preserved both existing
jobs and both separate history databases. Renderer, captions, config and standing
preferences are byte-identical to the pre-change snapshot, preserving existing
render identities and approvals. No user media, narration, project history,
approved export or published video was deleted or overwritten.

## Verification and remaining limitations

All 110 offline regressions passed. They cover real corrupt MP4s, missing `moov`,
fast-start truncation, actual FFprobe/FFmpeg diagnostics, metadata/checksum
changes, duplicates and racing submissions, old schemas and legacy duplicate
rows, interrupted hashing/decoding, decoder deadlines, child cleanup, receipt
reuse/invalidation, approved/published project preservation, and a failed input
followed by a healthy queued job. A real 25-second media smoke fixture passed
complete decoding, mixed-audio QC and missing-narration rejection.

Remaining limits:

- FFprobe's admission check establishes container/packet integrity, not a complete
  frame decode. Latent bitstream corruption can enter the queue but is rejected
  by the full video decode before any planning/speech work.
- First validation of long/high-resolution recordings necessarily reads the
  recording multiple times and may decode slowly. Configurable deadlines bound
  validation latency; a broken file can occupy its current validation slot until
  that deadline/watchdog fires.
- Readiness checks cannot prove that a producer will never write again. Close
  the recording and use atomic rename. Cached receipts rely on filesystem metadata
  changing on ordinary writes. Adversarial metadata restoration or silent storage
  corruption can evade a cache hit; the final renderer independently hashes source
  bytes. Receipt keys fingerprint tool binaries, not every dynamically linked library.
- Original gameplay audio is muted by production and is checked at container/
  packet level, not fully sample-decoded. Full pre-processing decode covers video.
- The supported/tested runtime remains Ubuntu/WSL. No live Codex/HeyGen generation,
  service enablement or publication was performed during these checks.
- A hard OS kill cannot execute Python cleanup. The provided service's
  `KillMode=control-group` is recommended for unattended process cleanup; queue
  recovery still treats interrupted jobs as needing explicit attention.

Complete source, queue backup, installed migration proof, logs and checksums are
under `Releases/2026-11-12-integrity-pipeline/`.
