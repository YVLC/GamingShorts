# Dialogue and storytelling repair — 14 November 2026

This revision continues mission `1b28a5dd9e1b`; it does not restart indexing.
The original silent 4K recording, 217 local chunks, 47 selected AI inspections,
260 observations and previous outputs remain in place. The rejected robot
recap is retained, including the user's rejection in creative history.

## Editorial policy

`Automation/gamingshorts_v2/config.json` selects `dialogue-editorial-v1`.
Legacy projects retain their renderer. New plans support narrated, hybrid and
gameplay-first modes. Narration needs useful, visually supported added value.
Literal dialogue-echo checks are only preliminary blockers; independent visual
and semantic reviews remain mandatory. Dialogue hooks, a character's pointed
question and a completed joke are valid payoffs. Physical action, a montage,
25-second minimum and a subscription CTA are not mandatory.

Continuous events remain chronological. One interaction is one event. Source
reservations and historical originality checks still apply. Old automated
action/length-based holds can be reassessed with plan-bound proofs, preserving
their historical database records; user rejections cannot be overridden.
Spoiler metadata remains, with the previously requested restrictions off.

## Silent-source handling and captions

The source has no audio stream. Gameplay-first plans do not call speech
generation and never recreate character voices. Faithful visible dialogue is
verified against original frames and a high-resolution subtitle strip, including
an exact end-frame check. It is displayed once in a readable portrait text area;
the original lower subtitle UI strip is excluded from the picture and blur.
The sharp original picture occupies about 64% of the portrait height.

Evidence windows remain unchanged. Accessible caption presentation starts no
earlier than the verified original onset and may linger through a gap, stopping
before the next line. An explicit final-frame reading hold is allowed only at
the end of a gameplay-first edit, capped at two seconds and included in plan,
render identity and review metadata. It is not additional source footage.
No invented word alignment is claimed for silent game dialogue. Real narrated
and hybrid portions still require saved speech audio and real word timestamps.

Music selection uses the existing cleared instrumental library, evidence,
rotation and original-composition fallback. Unlicensed trending tracks remain
excluded. Speech ducking applies where speech actually exists.

## Compared events

| Event | Source | Decision |
| --- | --- | --- |
| Crystal-cutter's burial explanation and Aava's cemetery question | 02:52:11–02:52:27.500 | Gameplay-first: the dialogue supplies discovery and dry humor. No recap needed. |
| Birthday message and “with or without you here” joke | 00:39:43–00:39:56 | Gameplay-first: the affectionate joke supplies its own setup and payoff. No invented friend voices. |
| Avalanche / sweeping snow | 05:34:32–05:35:04 | Held: the inspected footage does not establish a resolved escape, fall or death. |

The two proposed dialogue edits each have an explicit 1.5-second final reading
hold. Final acceptance is determined by the saved reviews, not this proposal.

## Resume and results

Run in WSL from `/mnt/d/GamingShorts`:

```bash
python3 tools/run_dialogue_editorial.py
```

The mission lock prevents concurrent controllers; checkpoints skip completed
and held candidates. Do not rerun one-time repair helpers to reset a rejection.
No TTS requests are automatically retried and no publishing route is invoked.

Authoritative status and preview paths:
`ReadyForReview/cairn_first_three_1b28a5dd9e1b/DIALOGUE_EDITORIAL_REPORT.md`.
Accepted previews go into its `dialogue_editorial_v1` subfolder. Technically
passing but editorially held drafts elsewhere are not accepted deliveries.

Release receipts, cached AI results, archived superseded plans/reviews, test
logs and the preservation audit are under
`Releases/2026-11-14-dialogue-editorial`. The suite includes actual unvoiced,
narrated and hybrid media fixtures, caption dwell, explicit freeze rendering, duplicate
history, source cadence and missing-speech rejection. Fixture speech is offline
synthetic test audio; it does not establish a new live HeyGen call. Automated
audio checks do not replace human listening or publication approval.
