# Creative diversity repair - 13 November 2026

**Acceptance: 0/3 new Shorts produced.** This is a deliberate insufficient-evidence
stop, not three remixes presented as new work. The full recording scan remains
paused, no speech or music was generated for a new batch, and nothing was published.
The 59.5 GiB original and all previous media/approvals/history are preserved.

The prior 33-second Royalty preview was an audio-mix demonstration of an existing
story. It retained the route overview, bridge and night-climbing sequence and
narration. It was not a new editorial Short. Future music-demo reports explicitly
carry `new_story=false`, `delivery_kind=music_mix_demo` and their source project.
Existing reports and videos were not rewritten to change their historical identity.

## Historical index and comparison

The additive SQLite ledger now indexes eight project plans in six exact normalized
script/range families, including the quality derivative absent from the old edits
table. These are **not** six certified unique events: some historical families also
share bridge/climbing material. Music, caption wording, audio bytes and a decorative
opening cannot create a new family. Retained music demos are linked to their source
family rather than counted as new stories.

`story_history_v1` stores hooks, narration transcripts, concrete beats, premise,
structure, conclusion, evidence/location/topic descriptions, original source identity
and provenance. `story_footage_v1` stores each original-relative range and a bounded
visual fingerprint from the corresponding encoded Short. `story_outputs_v1` records
export identities and mapping status. Standalone exports without an exact plan
receipt are explicitly unmapped; their unknown source timestamps are not invented.
Transcripts/descriptions come from saved plans, not a new speech transcription or
an unsupported claim that every historical narration was accurate.

Historical events already covered include:

| Hook | Structure | Existing conclusion | Original-recording ranges (not the active 6h50 timeline) |
| --- | --- | --- | --- |
| Would you cross this bridge above the clouds? | legacy / unspecified | Would you keep climbing, or call it here? | 00:26.000-00:31.000, 00:48.000-00:52.000, 04:06.000-04:11.000, 05:21.000-05:25.000, 08:38.000-08:42.000, 15:06.000-15:10.000, 16:46.000-16:51.000 |
| How far up would you dare to go? | legacy / unspecified | Would you climb this high? Be honest. | 50:21.000-50:25.000, 31:58.000-32:02.000, 43:09.000-43:13.000, 61:34.000-61:38.000, 77:33.000-77:38.000, 82:21.000-82:25.000, 84:45.000-84:50.000 |
| Why did my climbing game suddenly become a cartoon? | before_after | The colorful path eventually reaches a sterile-looking room. | 43:26.300-43:31.100, 43:32.300-43:37.500, 43:40.000-43:45.500, 44:10.000-44:15.500, 44:28.000-44:33.500, 44:34.000-44:39.000 |
| Cairn turned a blizzard into this. | escalating_attempts | The climber is surrounded by bright blue and purple effects during a dramatic fall-like transition. | 67:26.700-67:31.700, 66:16.000-66:21.000, 66:29.000-66:34.000, 66:41.500-66:46.500, 67:20.000-67:26.000, 67:32.000-67:37.000 |
| Wait, you can make hot chocolate in Cairn? | cause_and_effect | The small, ordinary routine makes the extreme climb feel tangible and human. | 35:45.000-35:49.200, 35:49.200-35:53.400, 35:53.400-35:57.600, 35:57.600-36:01.800, 36:01.800-36:06.000, 36:06.000-36:10.000 |
| This tangled line records a climb across the mountain. | discovery_reveal | Returning to the route view turns isolated climbing moves into a readable record across the mountain, without claiming summit arrival or completion. | 17:13.400-17:18.400, 00:31.000-00:36.000, 05:58.267-06:03.267, 13:54.000-13:59.000, 16:35.600-16:40.600, 17:59.267-18:06.267 |

Full plan/source metadata is in
[historical-index.json](../Releases/2026-11-13-creative-diversity/historical-index.json).
Representative shelter and rainbow review sheets were visually inspected. The
known music remix independently matches **all six** of the quality derivative's
ordered gameplay signatures; four ordered samples also match the earlier route
render. The comparison is retained in
[known-remix-rejection.json](../Releases/2026-11-13-creative-diversity/known-remix-rejection.json).

## Enforcement

`creative_history.py` adds two distinct layers before any new-production music
selection or TTS:

1. Deterministic rejection of identical script/range families, substantially similar
   hooks or substantive endings (the common CTA is excluded), protected/central
   source overlap, and multi-shot ordered visual reuse. Single similar rock faces
   do not establish a repeated sequence. Perceptual matching is heuristic and can
   still over- or under-reject. Topic/keyword retrieval is explicitly **not** proof
   of semantic originality.
2. Independent semantic and visual review through the existing cached Codex adapter.
   The candidate's timestamped images and historical summaries/review sheets are
   compared for a different central event, concrete arc, hook, payoff and observable
   outcome. Generic mountain difficulty, invented events, merely rewritten synonyms
   and forced cliffhangers are rejected. Uncertain judgement or confidence below
   0.85 fails before speech. Review binds to exact plan, manifest, current history,
   code and candidate/historical image checksums. Missing/stale evidence cannot
   silently approve a story.

V3 concept prompts now include the complete indexed historical event summaries
and require failures, close calls, recoveries, humor, mechanics, discoveries,
successes or moving atmospheric reveals grounded in visible outcomes. Canonical
structures may recur only when their concrete event and beats differ. Existing
structure rotation, spoiler rules, source guards and footage reservations remain.
The creative comparison permits at most min(2 seconds, 8% of a Short) explicitly
marked context from non-protected history, but **does not weaken existing stricter
SQLite reservations**. Approved/published footage is never permitted by this allowance.

The normal launcher runs this review before selecting music and calling
`voices.ensure`; V3 planning records it before reserving the final plan, and V3
rendering requires a current receipt. Music selection/segment alignment, original
footage rendering, narration identity, word-aligned captions and technical QC remain
in their existing modules. Technical fixtures and explicit music-demo tools are
not labeled creative production and are not evidence of new-story success.

The real semantic model was **not** asked to certify invented or unobserved new
events in this run. Its acceptance/rejection protocol is tested with controlled
fixtures; accuracy on genuine future unseen events still requires review. AI
review is a screen, not human editorial approval.

## Three-Short acceptance attempt

The actual existing command `python3 start.py --v3 batch --count 3 --start`
stopped at its normal preflight with:

> Index the complete authoritative recording first

The active source is `Sources/videoplayback.webm`, SHA256
`bd18af221a4ea5e4b71d805bcb511decaf10c1eda6093ba38959a8b52618e643`.
It has **0 analyzed scenes, 0 eligible scenes, 0 completed analysis chunks and
217 pending chunks**. Seven completed strict-decode windows are integrity receipts,
not event/scene analysis. The active FootageIndex namespace has no completed story
analysis proxies. Its existing eight-second smoke proxy and three isolated sample
frames do not establish three distinct 25-40-second events or their outcomes.

Older caches contain 24 timestamped contact sheets of a 90.5-minute recording and
separate surveys of the older 90.5- and 18.7-minute recordings. Their hashes and
source timelines differ from the current 6h50 file. No verified mapping makes their
timestamps valid for the new original, and the renderer correctly refuses proxies
as final inputs. Previously used drink, rainbow, storm and route sequences were
not recycled to satisfy the requested quota.

| Requested Short | New source timestamps | New narrative | Result |
| --- | --- | --- | --- |
| 1 | Not established | Not fabricated | Blocked: no eligible analyzed event |
| 2 | Not established | Not fabricated | Blocked: no eligible analyzed event |
| 3 | Not established | Not fabricated | Blocked: no eligible analyzed event |

Additional scene analysis of **new portions of this exact recording**, with dense
event/outcome evidence and history comparison, is required. At least three distinct
central events and sufficient non-overlapping supporting material must be found;
raw seconds alone cannot guarantee worthwhile stories. A bounded targeted survey
would need an explicit workflow extension/authorization; the current V3 production
path requires complete source validation and full indexing. Neither was resumed.
No five- or three-video completion is claimed.

The machine-readable attempt is
[acceptance.json](../Releases/2026-11-13-creative-diversity/acceptance.json), also stored
in `story_attempts_v1`. The actual preflight log is `batch-attempt.log`.

## Verification and operation

All **205 regression tests pass**, including new checks for music/caption remixes,
rewritten narration over used footage, common CTAs, protected overlap, limited
context, ordered visual matches, semantic rejection, stale image receipts and
prohibition on treating the original recording as a historical Short. The existing
render smoke test passes full decoding, narration/mix QC, the missing-narration
negative case and render/cache checks. There was no production voice call.

To refresh the historical index and repeat the safe cache-only acceptance audit:

```bash
cd /mnt/d/GamingShorts
python3 tools/creative_audit.py
```

This command does **not** start source indexing or new narration. It does write
additive audit/history records and reuse bounded historical Short frame caches.
New AI review occurs only when a real new candidate is being planned/produced.

Changed production files: new `creative_history.py`, `game_plan.py`, `start.py`;
new tests and `tools/creative_audit.py`; metadata-only labeling in the two music
preview utilities. Music/mixing/licensing modules were preserved. Evidence, full
source snapshots, checksums and SQLite backups are under
`Releases/2026-11-13-creative-diversity/`. Certified Unsafe was not accessed.
