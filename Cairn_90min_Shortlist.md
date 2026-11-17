# Cairn — 90-minute footage: Shorts shortlist

**Source:** `videoplayback (2).mp4` • 01:30:30.783 • AV1 2560×1440 @ 60 fps • 3.93 GB.

This editorial shortlist is based on 384 sampled still frames (one approximately every 14.1 seconds), **not** a full playback review. Exact cuts, actions, audio, and causality require inspecting the short moving-video previews.

## Storage and repeat-use audit

- 51 video files occupy 4.40 GB total. The source accounts for ~89.5% of that. No second multi-GB source copy appears in the top-file inventory.
- A 54.8 MB full-length review proxy is already present, which is not another 3.93 GB source copy.
- V2 lists 7 reserved intervals. All preview windows in this pack are outside those V2 intervals. V1 footage usage needs to be checked independently.
- The recording_report.json lists the AV1 video stream only. Do not assume game audio is present until separately verified with ffprobe.

## Ranked concepts

### 1. A mountain climb turns into a cartoon nightmare
- **Relevant source period:** 00:43:21–00:44:44
- **Suggested hook (draft):** “Why is there a rainbow tunnel in a climbing game?”
- **Visible basis:** A rainbow road appears around 00:43:01; cartoon figures and a laboratory-like room are visible until about 00:44:40.
- **Editorial structure:** `discovery_reveal` · **Confidence:** high for visuals; exact transition requires video
- **Important:** The existing V2 edit reserves 00:43:09–00:43:13, so keep all new cuts outside it.
- **Review clip IDs:** rainbow_entry, rainbow_payoff

### 2. The mountain nearly disappears in the storm
- **Relevant source period:** 01:06:00–01:07:43
- **Suggested hook (draft):** “The visibility got so bad I could barely see the wall.”
- **Visible basis:** Snow and ice climbing across 01:05:50–01:07:17; a sudden bright, multicolored sequence appears around 01:07:31.
- **Editorial structure:** `escalating_attempts` · **Confidence:** high for weather/visual transformation; danger needs verification
- **Important:** Do not claim an avalanche or a death without reviewing actual motion.
- **Review clip IDs:** storm_climb, storm_transition

### 3. Crossing the glowing ice with two climbing picks
- **Relevant source period:** 01:17:40–01:19:05
- **Suggested hook (draft):** “This ice section looks impossible to cross.”
- **Visible basis:** The player clings to bright icy formations near 01:17:40–01:18:51, with ice-tool prompts onscreen.
- **Editorial structure:** `close_call` · **Confidence:** medium-high for traverse; close call unverified
- **Important:** The already-reserved 01:17:33–01:17:38 segment must be excluded.
- **Review clip IDs:** ice_traverse

### 4. At the top of Cairn: an extraordinary landscape
- **Relevant source period:** 01:23:05–01:25:15
- **Suggested hook (draft):** “After all that climbing, this is what the summit looks like.”
- **Visible basis:** A luminous snowy summit ridge and star field from about 01:23:05–01:25:12; the character appears to reach the top.
- **Editorial structure:** `cause_and_effect` · **Confidence:** high for summit view; chronology needs verification
- **Important:** The already-reserved 01:24:45–01:24:50 segment must be excluded. This is a major ending spoiler.
- **Review clip IDs:** summit_ridge

### 5. Cairn's ending goes beyond the mountain
- **Relevant source period:** 01:25:20–01:28:20
- **Suggested hook (draft):** “I thought reaching the peak was the end. Then this happened.”
- **Visible basis:** The character floats amid stars around 01:25:26 onward; colorful comet-like streaks and Cairn credits follow around 01:27–01:29.
- **Editorial structure:** `unexpected_solution` · **Confidence:** high for visual ending sequence; interpretive meaning unknown
- **Important:** Major finale spoilers; review actual video before describing the ending's meaning.
- **Review clip IDs:** space_float, comet_sequence

### 6. The unexpected calm between climbs
- **Relevant source period:** 00:35:28–00:37:10
- **Suggested hook (draft):** “After all that climbing, this is where I ended up.”
- **Visible basis:** A close-up of the climber indoors, drinking or preparing items at around 00:35:28–00:37:07, with inventory overlays.
- **Editorial structure:** `before_after` · **Confidence:** medium; static menu screens might not retain viewers
- **Important:** Confirm motion and game context; avoid claiming a scripted narrative not shown.
- **Review clip IDs:** shelter_scene

## Exact preview requests

| ID | Source start–end | What to inspect |
|---|---|---|
| `rainbow_entry` | 00:43:26–00:43:49 | Rainbow tunnel and cartoon figures |
| `rainbow_payoff` | 00:44:07–00:44:42 | Cartoon montage and strange room |
| `shelter_scene` | 00:35:43–00:36:10 | Shelter close-up and inventory |
| `storm_climb` | 01:06:15–01:06:50 | Whiteout and icy rock climb |
| `storm_transition` | 01:07:15–01:07:38 | Bright transformation near storm |
| `ice_traverse` | 01:17:50–01:18:25 | Ice crossing with climbing tools |
| `summit_ridge` | 01:23:51–01:24:29 | Final snowy ridge, wide landscape |
| `space_float` | 01:25:20–01:26:02 | Character lifts off into the stars |
| `comet_sequence` | 01:27:20–01:28:00 | Comet trails near end credits |

## Next production steps

1. **Do not edit the original AV1 recording.** Install the previously prepared GamingShorts Multi-Clip 2.1.1 patch after confirming that no rendering/planning job is running (dry-run first).
2. Run `export_cairn_previews.py` in Ubuntu to generate short, lightweight 960-pixel-wide review MP4s directly from the source. The script reads only the selected windows and creates a separate ZIP.
3. Upload the focused preview ZIP for motion-level confirmation. Check visible action, game audio, hook accuracy, and whether the candidate is already represented by an old V1 Short.
4. Select 3–5 candidates with distinctive story payoffs; produce separate `--variant` jobs and validate the editor’s actual frame selections. Reject repetitive concepts rather than forcing every idea into a Short.
5. Keep narrator voice, music loudness, and publishing approval controls unchanged. No uploading or deleting originals as part of this review.

### Preview command

```bash
python3 /mnt/d/GamingShorts/export_cairn_previews.py
```

The script defaults to `/mnt/d/GamingShorts/Sources/videoplayback (2).mp4` and writes its output under `/mnt/d/GamingShorts/ReviewExports`. Download `export_cairn_previews.py` and `Cairn_90min_Review_Manifest.json` into `D:\GamingShorts` before running it.

### Important distinction

The 2.1.1 editor currently generates a fresh AI survey when asked for `--variant ... --stop-after plan`; it does not automatically consume this shortlist JSON as an enforced creative brief. Avoid assuming it selected these exact moments without reviewing `edit_plan.json` and the rendered Short.
