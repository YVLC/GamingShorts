# Maintenance release: 12 November 2026

The workspace now has a root CLI launcher, a daily-use README, a full project map,
a read-only storage inventory tool, and a shared Ruff configuration. Twenty-three
Python files in the active runtime/tests and new utilities were formatted into
readable blocks. Older workers and saved importers remain at their original paths.

Two small runtime fixes accompany the cleanup:

- Environment diagnostics retain FFmpeg's filter list separately from Codex's help
  output. Karaoke capability checks now reuse that list instead of launching a
  second FFmpeg process. Tests cover both available and missing libass.
- Configuration reads use the common explicit UTF-8 JSON reader.

The media smoke fixture now pins its original phrase-caption defaults rather than
inheriting production karaoke settings without supplying word alignment. Production
configuration, preferences, renderer and caption source bytes are unchanged.
Runtime `VERSION` is retained because it participates in existing render identities;
the maintenance release is identified by its dated directory and SHA256 manifest.

## Verified in Ubuntu/WSL

- All 47 baseline tests passed before changes; all 49 tests passed after changes.
- Ruff's configured critical-error lint and formatting checks passed.
- Nineteen existing Python syntax trees match the baseline after normalizing
  docstring indentation. Intentional code changes are isolated to `common.py`,
  runtime `start.py`, and `tests/render_smoke.py`.
- Renderer, captions, production config and preferences match baseline bytes.
- Root launcher help and self-test dispatch work.
- Read-only inventory completed without scan errors.
- A 25-second 1080x1920 synthetic render passed full decode and mixed-audio QC;
  a music-only negative control failed all five narration checks as expected.
  Changed-plan cache invalidation and contact-sheet generation passed.
- The generated final review sheet was visually inspected for captions and CTA.

The fixture uses synthetic tones and phrase captions. It does not establish real
speech quality, creative quality, live HeyGen/Codex availability, or karaoke word
alignment. No live AI generation or publication was performed. Windows Python is
not the supported runtime; the root launcher directs Windows users to WSL.

## Storage and retained history

The inventory found about 4.65 GiB under `_Processing` and 2.33 GiB under
`SplitRetry`. These are potential space-recovery candidates only after tracing
their owning jobs and confirming what must be retained. No source, media,
database, prior output or historical package was deleted or relocated.

Absolute paths in manifests, provenance and SQLite make indiscriminate directory
merging unsafe. The project map identifies the purpose of each folder while
preserving compatibility with current jobs and saved installers.

## Release artifacts

`Releases/2026-11-12-maintenance/` contains the pre-change runtime snapshot,
complete cleaned source snapshot, source ZIP, SHA256 manifest, test logs,
inventory, behavior-preservation verification, and synthetic media evidence.
The source ZIP is a reviewable snapshot, not an automatic overwrite installer.
Do not run historical patch installers against the maintained runtime.

Developer formatter, installed only under `.tools/maintenance`:

```bash
.tools/maintenance/bin/ruff format --check Automation/gamingshorts_v2 start.py tools
.tools/maintenance/bin/ruff check Automation/gamingshorts_v2 start.py tools
```

Ruff is pinned to 0.14.3 and is not a runtime dependency. The root `.gitignore`
excludes local tooling, credentials and generated assets for future source control.
