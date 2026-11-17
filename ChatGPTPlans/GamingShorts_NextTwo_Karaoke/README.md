# GamingShorts – Snowstorm + Shelter: yellow karaoke and high-quality render

This package is **for the two remaining Cairn Shorts**, not a replacement for the published Rainbow project.

- **Snowstorm**: 31.0 s, 6 scenes, minor-spoiler classification (the existing policy adds a 2 s warning). Real Garret voice recording 16.58 s, 45 word timestamps.
- **Shelter**: 25.0 s, 6 scenes, no spoilers. Real Garret voice recording 16.36 s, 43 word timestamps.
- **No paid APIs**: the voice was ALREADY generated via authenticated HeyGen `heygen-voice-1-turbo-free`; the supplied URLs are the returned voice files. No more calls to HeyGen/Codex are required to download/split and render these two stories.
- **Caption enhancement**: use actual speech word timestamps rather than estimated or evenly distributed timings. Text stays on-screen through between-word pauses; the actively spoken word is highlighted yellow. Other words stay white. The accompanying timing JSON/SRT is retained.
- **Higher-quality editing configuration**: 1080x1920, **60 FPS**, H.264 **CRF 18**, `medium` x264 preset, Lanczos scaling. The final output will be larger and more expensive to encode than prior 30 FPS / CRF 22. Source-specific limits and YouTube recompression still apply.
- The original gameplay, original V1/V2 caches, Codex automation, already-produced Rainbow video, and published content are NOT changed. No script here publishes to YouTube.

## Install

Extract **the whole directory** to:

`D:\GamingShorts\ChatGPTPlans\GamingShorts_NextTwo_Karaoke`

In Ubuntu:

```bash
cd /mnt/d/GamingShorts/ChatGPTPlans/GamingShorts_NextTwo_Karaoke
python3 install_upgrade.py           # read-only verification
python3 install_upgrade.py --apply   # backup + upgrade renderer/captions/config
```

The upgrade installer checks that the existing two modules match the **tested GamingShorts 2.1.2a version**. If you have manually edited them, it stops safely instead of overwriting them. `--apply` saves dated backups in `Automation/gamingshorts_v2/Backups` and preserves unrelated settings.

## Snowstorm – import, use the saved Garret audio, render

```bash
cd /mnt/d/GamingShorts/ChatGPTPlans/GamingShorts_NextTwo_Karaoke
python3 import_plans.py --plan storm_v2             # preview
python3 import_plans.py --plan storm_v2 --apply     # new project
python3 install_saved_voices.py --plan storm_v2     # preview
python3 install_saved_voices.py --plan storm_v2 --apply

cd /mnt/d/GamingShorts/Automation/gamingshorts_v2
python3 start.py --project "/mnt/d/GamingShorts/Projects/V2/videoplayback_2_c8aec7b5_chatgpt_storm_v2" --stop-after voice
python3 start.py --project "/mnt/d/GamingShorts/Projects/V2/videoplayback_2_c8aec7b5_chatgpt_storm_v2"
```

The first `start.py` command downloads an **existing** HeyGen WAV and splits it into 6 segment files, checking provenance. The second aligns words using the saved original HeyGen word timestamps and renders the video. It does not invoke an external speech service.

## Shelter – repeat

```bash
cd /mnt/d/GamingShorts/ChatGPTPlans/GamingShorts_NextTwo_Karaoke
python3 import_plans.py --plan shelter_v2
python3 import_plans.py --plan shelter_v2 --apply
python3 install_saved_voices.py --plan shelter_v2
python3 install_saved_voices.py --plan shelter_v2 --apply

cd /mnt/d/GamingShorts/Automation/gamingshorts_v2
python3 start.py --project "/mnt/d/GamingShorts/Projects/V2/videoplayback_2_c8aec7b5_chatgpt_shelter_v2" --stop-after voice
python3 start.py --project "/mnt/d/GamingShorts/Projects/V2/videoplayback_2_c8aec7b5_chatgpt_shelter_v2"
```

The original 90-minute source can be hashed for each rendered project, even when the visual inspection cache is reused. More frames and CRF 18 will increase encoder CPU load. **Do not run both rendering commands simultaneously**.

## Approval, soundtrack and spoiler policy

The outputs are placed under `D:\GamingShorts\ReadyForReview`. Watch/listen before approving:

- Captions should move word-by-word with yellow emphasis. Check the opening line and words with long pauses.
- Check the action/crops at each of the 6 cuts and whether the visual transition supports the script.
- Listen for sound artifacts, background-music balance, pronunciation, and narration completion.
- Snowstorm remains **minor-spoiler** (existing safety rule) and should have the 2-second warning. Shelter is **no-spoiler** without a warning. You can review the classification before publishing.
- Music is the existing licensed local project track; this package does not download unrelated music.

If everything looks good, upload both final MP4s here for review. **No automatic publication occurs**.

## If upgrading fails

`STOP: gaming_shorts.py differs from tested 2.1.2a` means your local pipeline changed; do not force-copy the patch. Share the displayed text and a current copy of the module.

The audio URLs can expire. In that case, keep the saved result and do not re-synthesize without checking. 

## Verification performed on this package

- Unit test suite with renderer upgraded: **50/50 passed**, including both 6-line saved timings and FFmpeg real subtitle rendering.
- Filename/path mapping uses the verified `start.project_for` naming algorithm.
- Source gameplay and YouTube publication were not accessible/executed in the test environment. Complete on your Ubuntu host before approval.
