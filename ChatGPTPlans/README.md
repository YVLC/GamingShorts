# Cairn manual batch — temporary ChatGPT planning, no Codex planning calls

This archive contains three timestamped, editable story plans based on the
9 uploaded moving-video previews from the 90-minute Cairn gameplay recording.
It does NOT include the original 1440p footage or any finished video.

## Install

Extract the ZIP contents DIRECTLY into `D:\GamingShorts\ChatGPTPlans`.
Confirm this file exists: `D:\GamingShorts\ChatGPTPlans\import_plans.py`

From Ubuntu/WSL, with no other GamingShorts job running:

```bash
python3 /mnt/d/GamingShorts/ChatGPTPlans/import_plans.py --plan rainbow_v1
python3 /mnt/d/GamingShorts/ChatGPTPlans/import_plans.py --plan rainbow_v1 --apply
```

The first command is read-only. The second will:
- verify the original source is present;
- check novelty and source-range conflicts against the real local V1/V2 DBs;
- create a new, separate V2 project without replacing any existing plan;
- print the new project path;
- not invoke Codex, HeyGen, rendering, or YouTube publication.

If `--apply` reports an overlap, leave the protected history intact and report
the error. Do not delete anything or bypass the range guard.

You can import `storm_v1` and `shelter_v1` the same way. Prefer validating the
rainbow video first rather than running several voice jobs concurrently.

## Next after import

Use the path printed by importer (not a guessed path):

```bash
cd /mnt/d/GamingShorts/Automation/gamingshorts_v2
python3 start.py --project "PASTE_IMPORTED_PROJECT_PATH" --stop-after plan
```

That command reviews the plan and spoiler classification without voice/rendering.
When ready to generate narration & render:

```bash
python3 start.py --project "PASTE_IMPORTED_PROJECT_PATH"
```

IMPORTANT: The existing voice bridge invokes Codex for the free HeyGen MCP
speech call. If Codex credits are exhausted, *plan import works*, but new voice
synthesis will still stop until access resets. The script never silently swaps
the approved Garret voice or uses a paid alternative.

Once finished, review/listen to the full-resolution Short and its spoiler
warning, title/description metadata, and technical QC before approval. Major
spoilers require explicit confirmation. No posting occurs automatically.

## Contents

- `plans/`: three editing plans (rainbow, storm, shelter)
- `import_plans.py`: read-only preview by default, safe `--apply` import
- `youtube_metadata.json`: suggested titles, descriptions, and tags for later review

All content is a temporary replacement for the story-planning stage only.
**Do not disable Codex in GamingShorts 2.1.2**. Once its allowance resets,
new recordings and variants should use the normal automated planner.
