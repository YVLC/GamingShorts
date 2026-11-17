# GamingShorts

Creative repetition guards and the blocked three-Short acceptance result: [creative diversity report](docs/CREATIVE_DIVERSITY_2026-11-13.md).

Music selection, excerpt evidence and preview: [music intelligence guide](docs/MUSIC_INTELLIGENCE_2026-11-13.md). Full recording analysis has resumed; see the [live mission guide](docs/FULL_ANALYSIS_RESUME_2026-11-13.md).

Full-game V3 production supports a single authoritative original per game,
checkpointed seven-hour analysis and small review batches. Start with the
[V3 full-game guide](docs/V3_FULL_GAME_2026-11-12.md). The active Cairn original is `Sources/videoplayback.webm`; preserve it in place.
See [source activation](docs/SOURCE_ACTIVATION_2026-11-12.md) for validation and launch commands.

Turn existing gameplay recordings into narrated YouTube Shorts. The active
workflow runs in Ubuntu/WSL and saves versioned videos for manual review.

```bash
cd /mnt/d/GamingShorts
python3 start.py --help
python3 start.py --list-projects
python3 start.py --doctor
```

Add a completed recording to `Sources/`, then create a plan:

```bash
python3 start.py --stop-after plan
```

For continuous automation, run `python3 start.py --watch` in Ubuntu. It waits for
new recordings to settle, processes a durable queue and stops failed jobs for
explicit recovery. Inspect jobs with `python3 start.py --queue`. Use
`--watch --stop-after plan` if you want to review each plan before speech/rendering.
See the [runtime guide](Automation/gamingshorts_v2/START_HERE.md) for queue commands
and the optional user-service setup.

Review the printed project's `edit_plan.json`, then resume using that exact path:

```bash
python3 start.py --project "/mnt/d/GamingShorts/Projects/V2/PROJECT_NAME"
```

The normal workflow uses Codex planning and the existing Garret voice through
free HeyGen MCP. Uncertain speech calls require explicit recovery; no paid
fallback is enabled. Final videos go to `ReadyForReview/`. Watch and listen
before approving the exact output; publication remains manual.

| Location | Purpose |
| --- | --- |
| `Automation/gamingshorts_v2/` | Active Python application and tests |
| `Sources/` | Original recordings; preserve these |
| `Projects/V2/` | Plans, state, versioned narration, renders and approval |
| `Database/` | Shared editorial history, feedback and footage reservations |
| `AutomationLogs/` | Durable queue attempt logs, created when jobs run |
| `FootageIndex/` | Reusable whole-recording survey cache |
| `ReadyForReview/` | Current workflow's final exports |
| `ChatGPTPlans/` | Saved manual plans and one-off import helpers |
| `docs/` | Architecture and maintenance notes |
| `tools/` | Workspace maintenance utilities |
| `Releases/` | Complete maintenance snapshots and integrity manifests |

Obsolete workers and upgrade packages are checksum-archived in `Releases/`.
See [the full project map](docs/PROJECT_STRUCTURE.md) and the
[automation release report](docs/AUTOMATION_2026-11-12.md).
For recovery, captions and approvals, read the
[runtime guide](Automation/gamingshorts_v2/START_HERE.md).
See the [maintenance report](docs/MAINTENANCE_2026-11-12.md) for changes and validation.
Current validation behavior and remaining limits are in the
[staged-integrity report](docs/INTEGRITY_PIPELINE_2026-11-12.md).

Offline checks (no AI generation):

```bash
python3 start.py --self-test
python3 Automation/gamingshorts_v2/tests/render_smoke.py
python3 tools/workspace_report.py
```
