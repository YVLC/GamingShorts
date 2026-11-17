# GamingShorts quality repair — 12 November 2026

New delivery: [33-second gameplay render](../ReadyForReview/cairn_review_02_f7393e6c_main_quality_v1_v2_e49439cc.mp4).
It has no spoiler card. Classification and warning gates are disabled by default;
historical approved videos and warning assets remain intact.

## Root causes and measured results

The old project rendered its inspection proxy: 1280×676, 15 FPS, CRF 30.
The renderer promoted those frames to nominal 60 FPS and enlarged a narrow crop
about 2.84 times. VideoCache consequently retained already degraded shots.
The deleted original cannot be restored as a complete recording, but retained
3840×2026 AV1 stream-copy fragments cover every selected timestamp. Their hashes
match the earlier preservation ledger. The new project maps global timestamps
to those fragments and renders from them, never from the inspection proxy.

| Measurement | Before | New version |
| --- | --- | --- |
| Active visual updates/second, sampled scenes | 14–15 | 55–60 |
| Mean near-duplicate adjacent frames, six 3-second samples | 76% | 5% |
| Bridge reference PSNR, caption-free aligned crop | 29.05 dB | 40.71 dB |
| Stone reference PSNR, caption-free aligned crop | 22.85 dB | 37.47 dB |
| Detached narration tail, line-six opening RMS | −27.28 dBFS | −65.19 dBFS |

Gameplay crops now downscale from native pixels. Maps use a sharp contained
foreground over a blurred background; foreground is never enlarged. A one-second
bridge gameplay opening precedes the retained narration. Cache identity includes
original source hashes, timestamps, captions, filters and quality code. Cached and
final frames receive motion-aware cadence checks; static footage is exempt and
native lower frame rates remain lower rather than being advertised as 60 FPS.

The recurring “ts” was the end of “adjustments,” split at 16.134 seconds using
service word timestamps. Its remaining consonant was detached into the next
narration segment. Waveform inspection moves only that unsafe cut to the quiet
gap at 16.328854 seconds. All original speech samples are retained; reconstruction
error is −91.9 dBFS after PCM quantization and quiet-edge fades. No de-esser,
consonant removal, synthesis or new AI calls were used. One constant master gain
replaces per-line loudness changes, float PCM is retained through mixing, and
delivery audio is AAC-encoded once. Peak protection takes precedence over the
−16 LUFS target: this master uses −1.5 dB gain (approximately −19.08 LUFS).
Minimum measured voice-over-music separation is 10.79 dB.

## Verification and evidence

The full 128-test suite passes, including corrupt/truncated/missing-moov sources,
duplicates, changed sources, interrupted workers, waveform boundaries, false
cadence and poisoned caches. The media smoke test passes full decoding and
positive/negative narration-mix QC. The real delivery passes technical QC and
full decode; its six existing scene encodes were reused after refining the opening.

Evidence is in [the release folder](../Releases/2026-11-12-quality-repair):
[measurements](../Releases/2026-11-12-quality-repair/before-after.json),
[picture comparison](../Releases/2026-11-12-quality-repair/picture-comparison-line-3.png),
[waveform](../Releases/2026-11-12-quality-repair/boundary-waveform.svg),
[before audio](../Releases/2026-11-12-quality-repair/boundary-before.wav) and
[after audio](../Releases/2026-11-12-quality-repair/boundary-after.wav).

## Preservation and limitations

The derivative lives in a separate `quality_v1` project. Original candidate,
narration, plan, approvals and database history are preserved. No publication or
render approval was granted automatically. Keep the surviving source fragments:
they are now the only retained high-resolution source for this recording.

Listening review was **not performed**. Audio conclusions use waveform, spectral
and mix measurements; a person should audition the result before approval.
Representative encoded frames were inspected, but sampled cadence/sharpness QC
does not prove every moment's editorial quality. The existing narration and map
explanations remain; this repair does not rewrite the AI plan. Source timestamp
alignment against the old proxy is accurate within approximately one proxy frame
(67 ms). Static-scene exemptions and thresholds remain heuristic.
