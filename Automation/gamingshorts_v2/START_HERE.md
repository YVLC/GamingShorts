# GamingShorts: daily operation

New projects use [story-led gaming Shorts](../../docs/GAMING_STORIES_2026-11-14.md):
lore, secrets, easter eggs, beginner tips, facts, funny or scary gameplay and
beautiful scenery. Stories develop environmental discoveries and demonstrated
mechanics rather than character conversations. Garret adds original commentary.
Each story has a specific hook, supported payoff and final Subscribe for more.
The free voice and yellow active-word captions remain enabled.
New v2 plans use full-frame 9:16 crops with explicit subject-tracking keyframes,
original production footage and high-quality encoding. Do not add blurred filler.
Creative hooks are welcome; factual lore, secrets and tricks need evidence.

The user approved the two [visual-stories-v2 clips](../../Releases/2026-11-15-visual-stories-v2/DELIVERY_REPORT.md)
on 15 November. `approved_quality_reference.json` freezes their exact output
hashes, plans and explicit approvals. Both planning routes use these as examples
of story quality and finish, never as facts or scripts to recycle. Older prompts
that encouraged conversation-led stories have been removed. Scene retrieval
demotes conversation observations and does not trust an older dialogue-oriented
catalog as a selection mandate.

Before new v2 narration, `visual_preflight.py` renders actual start/middle/end
source crops with a representative narration phrase at the planned caption
position. Independent visual review must accept subject visibility, full-frame
footage, clear samples and clearance from important native UI. A rejection stops
before TTS. Layout changes invalidate that review. The two exact user-approved
reference plans retain their existing approval; derivatives require new checks.
The preview is sampled visual evidence, not proof of continuous tracking or
audio quality. Final playback and publication approval remain separate.

The user authorized uploading those two approved exports. Future videos are
not automatically approved for publication. Upload readiness is recorded in
`Releases/2026-11-15-approved-pipeline/upload_manifest.json`.

The user has authorized footage reuse for the current Cairn recording. Exact
recording hashes are listed in `config.json` under `footage_reuse_sources`.
Prior source ranges and events can support new commentary; identical scripts,
unsupported claims, explicit rejections and duplicated ranges inside one Short
remain blocked. Other recordings keep their existing reservation protections.

For dialogue-aware narration, continuous gameplay-first edits and the current
Cairn review previews, see [editorial repair](../../docs/DIALOGUE_EDITORIAL_REPAIR_2026-11-14.md).

Earlier dialogue revisions and discovery reports are historical releases.

For the resumed 47-chunk Cairn AI queue and preservation evidence, see
[14 November resumption](../../docs/AI_ANALYSIS_RESUME_2026-11-14.md).

For autonomous local indexing and persisted AI-capacity pauses, see
[AI capacity resilience](../../docs/AI_CAPACITY_RESILIENCE_2026-11-13.md).

For approved music, verified/inferred excerpts, new composition fallback and management commands, see [the music guide](../../docs/MUSIC_INTELLIGENCE_2026-11-13.md). Analysis is running under the [resumed local-first mission](../../docs/FULL_ANALYSIS_RESUME_2026-11-13.md).

For full-game originals and controlled V3 batches, use
[`--v3` and the full-game guide](../../docs/V3_FULL_GAME_2026-11-12.md).
The active original is `Sources/videoplayback.webm`, configured relative to the
workspace root and retained in place. The legacy watcher skips this explicitly
selected full-game source; use the V3 indexing and batch commands. See
[source activation](../../docs/SOURCE_ACTIVATION_2026-11-12.md).

Run in Ubuntu/WSL. The installed application is this folder; the root launcher
forwards all arguments here. Previous installation guides and obsolete workers
are archived under `Releases/2026-11-12-automation/retired-tools.zip`.

```bash
cd /mnt/d/GamingShorts
python3 start.py --doctor
python3 start.py --help
```

## Automatic recording queue

```bash
python3 start.py --watch
```

Leave this foreground worker running. Copy recordings into `Sources/`. A recording
must have unchanged size and modification time across at least 60 seconds of
observation, and must not have been modified in the last 60 seconds. Copying a
file with a `.partial` extension and renaming it to `.mp4` after completion is
preferred. The watcher processes one job at a time, saving state in
`Database/automation.sqlite3` and attempt logs in `AutomationLogs/`.

Before enqueueing, every input must pass FFprobe container/codec/packet integrity
checks and gets a full SHA256 identity. Before processing, queued metadata/checksum
must still match and a full video decode must complete successfully. Successful
receipts are reused only for unchanged fingerprints, content and validator builds.
Manual enqueue and explicit requeue use the same guard. Renamed duplicate files
do not create another job; old project files are preserved for explicit resume.
Rejected files never become queued jobs: actual FFprobe stderr is printed and
saved under `AutomationLogs/rejected-inputs/`. The watcher continues with other
files and retries a rejected path only after its size/mtime changes or the watcher
restarts. Full decode has a 60-second non-advancing-progress watchdog and a
configurable total deadline. A failed input becomes `needs_attention` while other
jobs continue. See [the staged-integrity report](../../docs/INTEGRITY_PIPELINE_2026-11-12.md)
for validation stages, deadline settings, caching and limitations.

The worker reuses the existing source survey, planning, verified narration,
caption and render caches. It creates one default story per source path.
Existing V1/V2 projects require explicit enqueue or direct resume. Previously
rejected, approved or published projects are never restarted by the queue.

For a plan-only inbox, use `--watch --stop-after plan`. That setting applies to
newly discovered jobs; already queued jobs retain their saved settings.

```bash
python3 start.py --queue
python3 start.py --enqueue --source "/mnt/d/GamingShorts/Sources/recording.mp4" --stop-after plan
python3 start.py --work
python3 start.py --retry-job JOB_ID
python3 start.py --work
```

Replace `JOB_ID` with the ID shown by `--queue`. Enqueue records work without
generating anything. `--work` drains existing queued jobs and exits; `--watch`
also discovers files. Queue retries are explicit and never add `--retry-voice`
or `--new-voice`. Resuming a planned/voiced job without `--stop-after` continues
the full workflow. Failed or interrupted jobs become `needs_attention` and do
not loop. Their source size/mtime must still match before they can resume.

For a second story, explicitly enqueue `--variant second`. The same recording's
prior footage reservations and rejection history remain in force. There is no
automatic story multiplication or automatic YouTube posting.

## Review and direct commands

```bash
python3 start.py --list-projects
python3 start.py --stop-after plan
python3 start.py --project "PROJECT_PATH" --status
python3 start.py --project "PROJECT_PATH"
python3 start.py --project "PROJECT_PATH" --feedback "Make future openings more specific"
python3 start.py --project "PROJECT_PATH" --reject "This repeats the previous hook"
python3 start.py --project "PROJECT_PATH" --replan --stop-after plan
python3 start.py --project "PROJECT_PATH" --approve
```

Use the exact printed WSL project path in place of `PROJECT_PATH`. Direct commands
remain available for manual recovery and individual renders. Watch/listen to the
final video in `ReadyForReview/` and its upload metadata before
approving. Approval binds to exact output bytes. Technical QC and queue completion
do not establish editorial quality, rights or publication readiness.

## Voice, captions and recovery

`config.json` contains runtime settings; `preferences.json` contains standing
editorial constraints. Speech uses the existing Garret voice and only
`heygen-voice-1-turbo-free`, through authenticated Codex/HeyGen MCP. No paid
fallback or blind automatic retry is allowed.

New speech requests retain the actual returned word timestamps for karaoke.
They are checked against the exact transcript, phrase boundaries, audio duration
and audio checksum. Missing timestamps are never invented. Older results without
word timestamps can use the optional local aligner installed by
`bash setup_alignment.sh`; this machine currently has no local aligner installed.

- A failed render can resume with the same project command and verified narration.
- An uncertain speech timeout requires inspecting `VoiceVersions/<hash>/voice_codex.log`
  and recovering a genuine saved result where possible. Only use `--retry-voice`
  when another free generation is intended. The queue never sets this flag.
- A changed spoken script selects new audio; caption-only changes can reuse verified audio.
- If narration does not fit, extend its scene within source bounds or shorten the
  script. Shortened spoken text requires new audio.
- `--align-captions` operates on saved audio only. Invalid real word timestamps
  stop for inspection; they do not trigger replacement speech.
- If a workflow lock is held, wait or stop its process normally. Do not remove
  a live lock file. The OS releases locks on process exit.

## Migration and publication

Content classifications, warning cards and their approval gates have been removed.
Historical outputs and byte-bound approvals remain preserved.

`--migrate OLD_PROJECT_PATH` copies a legacy project into V2 without changing the
original. Listen and compare exact text before `--adopt-legacy-voice`; this records
your attestation, not automatic transcription verification. `--new-voice` explicitly
requests new free audio. `--import-history` indexes legacy project history.

Publication stays manual. `--verify-publication YOUTUBE_ID` verifies an already
public owner video, using environment variables `YOUTUBE_ACCESS_TOKEN` and
`YOUTUBE_CHANNEL_ID`. `--cleanup` previews enumerated render intermediates only
after committed publication verification; `--apply-cleanup` applies that list.
Source recordings, narration, final exports, plans and history are retained.

## Optional user service

The [service template](deploy/gamingshorts.service) is validated but not installed
or started. To install it yourself in Ubuntu:

```bash
mkdir -p ~/.config/systemd/user
install -m 644 Automation/gamingshorts_v2/deploy/gamingshorts.service ~/.config/systemd/user/
systemctl --user daemon-reload
systemctl --user enable --now gamingshorts.service
journalctl --user -u gamingshorts.service -f
```

Run those commands from `/mnt/d/GamingShorts`. Stop with
`systemctl --user stop gamingshorts.service`. The service runs while WSL and the
user service manager are running; this does not configure Windows boot, prevent
sleep or make WSL permanent. Interrupted jobs require explicit recovery after a
service restart. The template assumes D: and Codex in `~/.local/bin`, as checked here.

## Offline verification

```bash
python3 start.py --self-test
python3 Automation/gamingshorts_v2/tests/render_smoke.py
python3 Automation/gamingshorts_v2/tests/render_word_handoff.py /tmp/gamingshorts-word-review
```

These use isolated fixtures and no AI services. See [VALIDATION.md](VALIDATION.md).
Back up source footage, `Projects/`, `Database/`, `ReadyForReview/` and the runtime.

## Picture, cadence and narration quality

Render only original gameplay (or explicitly verified original fragment bundles).
Files under `ReviewCopies/` and other inspection-cache directories are rejected
as production inputs. The renderer preserves source cadence up to the chosen
cap and never promotes a 15 FPS source to a fake 60 FPS stream. Motion-aware QC
compares original, cached-shot and final visual updates; static footage is reported
separately. Sharp foregrounds are never excessively enlarged to fill portrait.

Quality analysis uses NumPy, already present in the tested Ubuntu environment;
`requirements-quality.txt` declares it. `--doctor` checks availability before a
production run. Narration is normalized with one constant master gain. New
segment boundaries are verified against actual quiet waveform regions.

To version repaired boundaries from existing continuous narration, without TTS:

```bash
python3 start.py --project "PROJECT_PATH" --repair-audio-boundaries
python3 start.py --project "PROJECT_PATH" --align-captions
```

Existing generated bytes remain in their prior voice version. The new version
records original master identity, corrected cuts and fresh segment checksums.
See the quality-repair report in `docs/` for the real before/after comparison.
