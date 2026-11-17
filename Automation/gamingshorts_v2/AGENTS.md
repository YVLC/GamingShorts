# GamingShorts maintenance requirements

Read START_HERE.md (copied into the installed folder) and preferences.json before changes.
The installed runtime is WSL Ubuntu; Windows paths are /mnt/d/... here.

- Do authorized work to a tested outcome; do not keep offering the next step.
- Preserve free-only HeyGen, voice identity, and manual publication.
- Never introduce a paid REST fallback or automatic retry after an uncertain TTS call.
- Preserve source files and previous outputs. Do not revive V1 raw-source cleanup.
- Keep narration identity bound to exact text/settings and audio byte checksums.
- Keep render identity bound to plan, audio bytes, config, music, font and renderer.
- Do not describe basic lexical guards as proof of editorial quality.
- Remember user rejections across projects and within replans of the same project.
- Deliver complete versioned releases rather than stacking string-replacement patches.
- Do not delete/recreate existing output to demonstrate a fix; use isolated fixtures.
- Run regression tests after state/cache/history changes and render_smoke.py after media changes.
- Verify actual final media; Python compilation alone does not establish correctness.
- Report tested results separately from untested Codex/HeyGen or Windows behavior.
- Keep approval tied to exact output bytes. Do not label technical QC as editorial approval.
- Do not spawn extra agents unless the user explicitly requests it.
