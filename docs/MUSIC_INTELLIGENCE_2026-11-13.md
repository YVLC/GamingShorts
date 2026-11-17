# Music intelligence and excerpt selection - 13 November 2026

Implemented as an extension of the existing renderer, queue and editorial SQLite
history. Full Cairn recording analysis remains **paused at the user's request**.
No original gameplay recording, supplied MP3, narration asset, prior Short or
approval was moved, renamed, modified or deleted. Nothing was uploaded/published.

## Review preview

[Open the 33-second Royalty excerpt preview](../ReadyForReview/music_segments_2026-11-13/cairn_segment_preview_05262422077c.mp4).
[Machine-readable review](../ReadyForReview/music_segments_2026-11-13/review_report.json).
Exact Windows output: `D:/GamingShorts/ReadyForReview/music_segments_2026-11-13/cairn_segment_preview_05262422077c.mp4`.

Music: **Royalty**, the local regular vocal release; not an instrumental,
sped-up, slowed or remix clearance. Selected interval: **50.262-83.262 seconds**.
The inferred source transition at 71.712s aligns to the estimated
story climax at 21.450s. The story marker is a narrative heuristic,
not a measured guarantee of the most exciting gameplay moment. Music moves;
footage cuts, narration and the original word-aligned captions never move.

This interval is **INFERRED**, with popularity confidence 0. It is not presented as
a verified trending excerpt. Current research found song-level Royalty chart
support but no reliable exact-version excerpt-popularity timestamps for these files.

The preview passes the existing full-decode, dimensions, duration, narration
presence/correlation and music-separation QC. Measured minimum speech separation:
**14.58 dB**; minimum speech correlation: **0.983**;
final integrated loudness: **-16.53 LUFS**;
true peak: **-1.38 dBTP**.
No clipping or isolated-impulse indicators were found. Original retained video and
narration checksums remain unchanged. Video packets were stream-copied from the
retained quality-repair render; the 59.5 GiB recording was not read for this preview.

Listening review was **not performed**. Measurements do not establish perceptual
intelligibility, musical suitability or editorial approval. Watch/listen before approval.

## Library, rights and rotation

The managed schema supports 20+ tracks (a 25-track fixture is tested); it does not
pretend 20 distinct licensed commercial recordings are installed. There are five
previous original generated cues, fresh per-Short compositions and the three
user-provided NCS releases. The three supplied files fully decode and remain in
`music/`. Their exact SHA256, version identifiers and metadata are retained in
`Releases/2026-11-13-music-segments/local-files.json`.

Each track has title/artist/source, genre, mood, energy, BPM/optional beat markers,
local path/source URL, license evidence, usage scope, attribution and approval.
Changed audio/evidence hashes, expired approval, missing required credit and
platform-only rights fail closed. Current NCS releases were checked individually:

- [Royalty](https://ncs.io/royalty): regular vocal version supplied locally;
  the separately offered instrumental is not substituted or presumed identical.
- [IN MY HEAD](https://ncs.io/s_inmyhead): SFRNG, Aizu and SOVAGI, not another same-title release.
- [FEEL THE RUSH](https://ncs.io/feeltherush): tonytonychopper999.

[NCS terms](https://ncs.io/usage-policy/terms) authorize synchronization for qualifying
independent-creator UGC subject to their conditions and restrictions. This review
is scoped to this GamingShorts creator use, not standalone music redistribution,
unreviewed branded endorsements or all commercial contexts. Credits are stored
per release, emitted in `.music.txt`, added to enabled spoiler/upload metadata and
checked during the existing read-only publication verification. Approval evidence
is dated and pins the local bytes. Metadata matches the named releases, but no
authoritative publisher byte checksum was available; no forensic authenticity claim
is made. Rights approvals are configured for review by 13 December 2026.

Selections and successful usage use additive `music_*_v2` tables in the existing
`Database/editorial_v2.sqlite3`. Reservations do not count as uses. Immutable
selection/render receipts retain history; the current successful render per Short
counts once even across caption/music versions. Failed rerenders preserve the last
success. Consecutive-track exclusion, least-used ranking, mood/energy, recent cleared
song trends and recency apply. Existing legacy tables remain intact; historical
provisional legacy selections are not falsely backfilled as successful uses.

Default strategy: `segments_then_new_original`. Prefer externally verified,
approved exact-version excerpts; otherwise use suitable **inferred** highlights
from approved songs. If no suitable cleared excerpt exists, compose fresh original
instrumental music for that Short, as requested. A deterministic per-Short identity
reuses that new composition on retries. Its source code, note choices and audio
hashes are retained under `MusicLibrary/Originals/`. No external samples or music
services are used. If composition/approval is unavailable, continue without music
and record the reason; no unlicensed legacy bed is substituted.

## Structure and excerpt evidence

`music_segments.py` uses a single cached 8 kHz music decode (tracks limited to
4-600 seconds), spectral onset flux, approximate tempo/beat grid, energy-transition
contrast and phrase-grid hypotheses. Drops, phrases and transitions remain
**inferred**. Neither a loud section nor a detected drop establishes popularity.
Seventeen version-bound inferred highlight ranges were indexed across the three
songs; no externally verified trending range was fabricated.

The additive `music_versions_v1`, `music_segments_v1`, `music_segment_pins_v1`,
`music_segment_results_v1` and `music_segment_feedback_v1` tables store versions,
multiple excerpt ranges, start/end/climax, confidence, evidence, dates, pins and
results. Verified imports require exact hash/version, valid range, an identified
reviewer, confidence 0.6-1, dates and external evidence explicitly supporting the
same excerpt timestamps. Song-level chart evidence cannot verify an excerpt.
Import validation checks structure and consistency; the named reviewer must have
actually checked the cited evidence. URLs alone are not automatic proof.

Source climax is aligned within excerpt bounds to an explicit `music.climax_at`
when present, otherwise a disclosed narrative/clip-marker heuristic. No clip or
speech is stretched, moved or discarded for music. Exact excerpt rendering does
not loop beyond approved bounds. Existing pins remain stable after feedback;
new projects can favor better-rated excerpts, with eligible audience observations
(100+ views) and editor ratings used only as tie-breaks. Technical measurements
are labeled technical and never fabricated as views, retention or popularity.

## Trends and manual management

The trend catalog is separate from render rights. Three dated references were
seeded from [ClipMusic's identification chart](https://clipmusic.ai/charts/youtube-shorts)
for 6-13 November 2026. This is a user-submitted recognition sample, **not** an
official YouTube usage chart or Netherlands ranking. No reliable exact timestamp
was established. Royalty's rights route was separately bound to the reviewed local
NCS version; other commercial references remain conditional platform-only metadata.
Platform-only sounds may only be added manually in the platform's licensed tools
when available to the account/region. They never enter FFmpeg automatically.

Run in Ubuntu/WSL:

```bash
cd /mnt/d/GamingShorts
python3 tools/music.py list
python3 tools/music.py trends
python3 tools/music.py segments --track-id ncs_royalty_regular
python3 tools/music.py analyze-segments ncs_feeltherush_regular
python3 tools/music.py import-trends /path/to/trends.json
python3 tools/music.py import-segments /path/to/reviewed-excerpts.json
python3 tools/music.py segment-feedback /path/to/observed-results.json
python3 tools/music.py import-library /path/to/local-tracks.json
python3 tools/music.py approve TRACK_ID --youtube-ugc --basis "Reviewed exact applicable rights evidence"
```

Imports of new library tracks stay pending; approval is an evidence-review
attestation, not an automatic legal judgement. Templates are in the runtime:
`music_catalog.example.json`, `music_trends.example.json`,
`music_segments.example.json`, `music_segment_feedback.example.json`.
No paid API is needed. No automatic trend refresh or publication is enabled.

## Mixing and preserved behavior

`music_mix.py` normalizes the bed, applies speech-sidechain ducking, smooth start/end
fades and one constant master gain constrained by loudness and true peak. Existing
speech-versus-music correlation/separation checks remain active; final encoded peak
is also checked. Sidechain threshold, ratio, attack/release, fades, output target,
ceiling and gameplay gain are configurable in `config.json` under `audio_mix`.
Actual gameplay sound streams are retained through aligned, faded audio-only stems;
this source contains no gameplay audio, so none is fabricated. Narration request
identity remains unchanged when music changes. Cached video can be reused.

## Files and evidence

Runtime changes: `music_library.py`, new `music_mix.py`, `music_composer.py`,
`music_segments.py`, renderer integration in `gaming_shorts.py`, credit propagation
in `spoilers.py`/`publication.py`, configuration, catalog and templates.
Management/preview tools: `tools/music.py`, `tools/music_segment_preview.py` and
retained original-music utilities. New unit/integration tests cover rights,
rotation, recovery, real mixing, versions, evidence and feedback; existing tests
were adjusted to supply explicit approvals instead of implicit license assumptions.

Logs, database backups and source snapshots are under
`Releases/2026-11-13-music-intelligence/` and
`Releases/2026-11-13-music-segments/`. Initial timestamp-validator repair evidence
is separate in `Releases/2026-11-13-timestamp-validation/`.

No Certified Unsafe project was accessed or modified. Full recording analysis
remains paused; this upgrade does not claim that five new Shorts were produced.

## Final verification results

All **193 regression tests pass**. The existing full render smoke test passes
full decode, positive mixed-narration QC, missing-narration negative rejection,
cache invalidation and contact sheets. The dedicated music retry render passes
narration-only fallback, unchanged narration checksums, no TTS, zero video encodes
on a music-only change and one counted successful Short. The saved-word handoff
fixture passes through splitting, verified timestamps, karaoke, sidecars and final
QC. Its words are synthetic fixture data, not evidence of natural-speech accuracy.
The real 33-second Royalty preview separately passes technical QC with retained
real narration and unchanged captions. Representative preview frames were inspected;
full listening review remains outstanding.

Final logs: `Releases/2026-11-13-music-segments/tests-final.log`,
`render-smoke.log`, `music-retry-render.log`, `word-render.log`, and `preview.log`.
The complete current runtime/source/music snapshot is under that release's `after/`,
with `release-manifest.json` checksums. Database backups and `state-summary.json`
retain the paused recording state and confirmed unchanged source fingerprint.
