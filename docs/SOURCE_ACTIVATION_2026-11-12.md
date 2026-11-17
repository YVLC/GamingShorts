# Full recording activation — 12 November 2026

The selected original is `Sources/videoplayback.webm`, resolved from the workspace
root on Windows and Ubuntu/WSL. It was never moved, renamed, copied or modified.
`config.json` now selects this source and game `cairn`. The V3 registration guard
accepts this exact configured source in addition to its existing GameSources
namespace. Other inbox files are not implicitly admitted to V3. The legacy watcher
skips the configured original to avoid a competing full-file legacy analysis.
Direct legacy selection also uses the configured original instead of newest-file order.

Metadata: 63,959,292,291 bytes (59.57 GiB), WebM, VP9 Profile 0, 3840×2160,
19001/317 FPS (59.9401), 24,654.146 seconds (6:50:54.146). No audio streams.
Narration and music remain available; original gameplay sound is absent.

The existing V3 workflow retains checkpointed decoding, bounded 640px/2 FPS proxies,
compatible proxy/artifact reuse, timestamped contact sheets, source-relative efficient
seeks, original-only final rendering and SQLite analysis/scene/shot reservations.
No AI requests, speech generation, full-file decode, full indexing or publication
were initiated. The initial full-file packet scan was stopped to keep validation bounded; no
strict integrity receipt or checksum was fabricated. The source is active in
configuration, pending strict catalog registration. The explicit `index --start`
command first completes existing strict registration (packet scan and streaming
checksum), selects the configured game, then indexes it. It creates no original copy.

Spoiler warnings and classification/major-spoiler approval gates are enabled again.
Historical output bytes and approvals are retained. Existing V3 policy still excludes
uncertain and major-spoiler scenes. Voice identity, captions, audio checks, narrative
history and final review requirements remain in the existing production workflow.

## Verification

Evidence: `Releases/2026-11-12-source-activation/`.
The real-source smoke check extracts frames at 60, 12,327.073 and 24,639.146 seconds,
creates/reuses an eight-second analysis proxy with existing artifact receipts, and
renders three seconds directly from the original through the existing portrait
framing filters. The resulting render fully decodes. Original filesystem fingerprint
is unchanged. Rerun this bounded check with `python3 tools/activate_source_smoke.py`.

Windows configuration/path resolution was tested; production media checks run in
Ubuntu. Sampled checks do not prove complete recording integrity. Full checkpointed
decode remains part of `index --start`. All 163 regression tests pass on rerun. An earlier concurrent run failed a
timing-sensitive stall fixture; both logs are retained. The normal render smoke test passes positive
and negative audio QC, full decode and cache invalidation. Logs contain test-mocked
speech messages; no real speech service was invoked by the offline suite.

## Launch

In Ubuntu/WSL:

```bash
cd /mnt/d/GamingShorts
python3 start.py --v3 estimate
python3 start.py --v3 index --start
```

Indexing deliberately starts the full validation/proxy/AI workload. Once complete:

```bash
python3 start.py --v3 batch --count 3 --start
python3 start.py --v3 run --batch BATCH_ID --start
```

Use the printed batch ID. Outputs require human watch/listen and explicit approval;
publication remains manual. Do not run the legacy watcher to process this source.

## Remaining limitations

Only `music/original_tension.mp3` is installed; music rotation code is preserved,
but rotation is disabled and there is no populated licensed-track catalog. Enabling
licensed rotation requires at least two distinct tracks and their license evidence
in the existing `music_catalog.json` format. No rights evidence was fabricated.
The optional local word aligner is absent; genuine HeyGen returned word timings
remain the primary caption path. Authenticated free HeyGen availability is checked
at the actual speech call, not by this non-generating validation.

No Certified Unsafe Unity project was accessed or changed.
