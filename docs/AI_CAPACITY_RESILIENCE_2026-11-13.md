# Local indexing and AI capacity

The full-recording controller runs locally in WSL, independently of the Codex
desktop conversation. Keep Windows and WSL running; completed SQLite checkpoints
survive an interruption. No uploader is invoked.

Local proxy generation, scene-change screening and native integrity validation
finish before the worker waits for pending shortlisted AI event inspection.
A pilot AI failure does not stop that local phase. Existing successful AI receipts
remain usable even while capacity is paused.

Definite quota rejections are recorded in `ai_capacity_v1` in
`Database/editorial_v2.sqlite3`, with a request-specific
`capacity_deferred.json` alongside the preserved request. Read-only
`account/rateLimits/read` checks run no more often than every 15 minutes during a
pause. No model turn is started by those checks. If a rejection-time capacity
snapshot was available, a later positive result must also show improved headroom
or replenished credits before another generation attempt. Unknown capacity leaves
the circuit paused. No paid fallback or credit purchase/reset is performed.

When recovered, the rejected request/logs are retained in `CapacityAttempts/`
before retrying the exact pending analysis. Unknown timeouts, malformed outputs,
transport errors and uncertain speech attempts are not automatically replayed.
Local work can finish while such an AI request remains held for inspection.

The scheduling update deliberately retains the previous sampling-controller
identity. Automated tests compare unchanged screening, selection, artifact and
AI-prompt functions against the archived controller; the actual installed build
is recorded in the release manifest. Change that identity when sampling or prompt
semantics change in a future release.

Current progress: `Releases/2026-11-13-full-analysis/progress.json`.
Worker log after the controlled handoff:
`Releases/2026-11-13-ai-resilience/mission-final.log`.

Resume after a system interruption, with no other mission worker running:

```bash
cd /mnt/d/GamingShorts
python3 -u tools/resume_full_workflow.py
```

The existing locks reject concurrent workers. Completed checkpoints and original
source bytes must remain in place. Major-spoiler approval, creative diversity,
licensing, voice and quality gates remain active. Future production failures
outside the capacity-aware analysis calls retain their existing inspection rules.

Protocol reference: [Codex app-server rate limits](https://learn.chatgpt.com/docs/app-server#6-rate-limits-chatgpt).
