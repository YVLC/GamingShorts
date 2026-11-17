#!/usr/bin/env python3
"""Import a human-authored Cairn edit plan into the EXISTING GamingShorts 2.1.2 pipeline.

Default is read-only. --apply creates one NEW variant project, never overwrites a plan,
never calls Codex, never generates audio, and never uploads anything.
"""
from __future__ import annotations
import argparse, json, os, sys, tempfile
from pathlib import Path

HERE = Path(__file__).resolve().parent
AUTOMATION = Path('/mnt/d/GamingShorts/Automation/gamingshorts_v2')
DEFAULT_SOURCE = Path('/mnt/d/GamingShorts/Sources/videoplayback (2).mp4')
CHOICES = ('storm_v2', 'shelter_v2')


def load(which):
    p = HERE / 'plans' / (which + '.json')
    return json.loads(p.read_text(encoding='utf-8'))


def static_check(plan, src_duration):
    clips = plan['clips']
    if not 3 <= len(clips) <= 10:
        raise ValueError('Clip count must be 3–10')
    total = sum(float(c['duration']) for c in clips)
    if not 25 <= total <= 40:
        raise ValueError(f'Short length {total:.2f} must be 25–40 seconds')
    for i, c in enumerate(clips, 1):
        start, dur = float(c['start']), float(c['duration'])
        if not (0 <= start and 2 <= dur <= 12 and start + dur <= src_duration):
            raise ValueError(f'Invalid source timing: clip {i}')
        if not c['narration'].strip() or len(c['caption']) > 90:
            raise ValueError(f'Invalid narration/caption: clip {i}')
    intervals = sorted((float(c['start']), float(c['start']) + float(c['duration'])) for c in clips)
    if any(b[0] < a[1] for a, b in zip(intervals, intervals[1:])):
        raise ValueError('Overlapping source ranges within the Short')
    if not clips[-1]['narration'].endswith('Subscribe for more.'):
        raise ValueError('Last line missing CTA')
    return total


def run():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('--plan', choices=CHOICES, default='storm_v2')
    p.add_argument('--source', type=Path, default=DEFAULT_SOURCE)
    p.add_argument('--apply', action='store_true', help='Actually import a NEW project without generating any audio')
    args = p.parse_args()
    plan = load(args.plan)
    total = static_check(plan, 5430.783)
    print(f'Plan: {args.plan} | {len(plan["clips"])} clips | {total:.1f} sec | spoilers: {plan["editorial"]["spoilers"]["level"]}')
    for idx, c in enumerate(plan['clips'],1):
        print(f' {idx}. source {c["start"]:.1f}–{c["start"] + c["duration"]:.1f}s | {c["narration"]}')
    if not args.apply:
        print('\nREAD-ONLY PREVIEW. Run again with --apply to check footage history and create a new project.')
        return
    if not AUTOMATION.is_dir():
        raise RuntimeError(f'GamingShorts 2.1.2 folder missing: {AUTOMATION}')
    if not args.source.is_file():
        raise RuntimeError(f'Original source missing: {args.source}')
    sys.path.insert(0, str(AUTOMATION))
    import start, editorial, gaming_shorts as gs
    from common import locked, key, save, state, config
    # Use the real server's global workflow lock to prevent edits racing with a renderer.
    with locked(gs.ROOT / 'Database' / '.workflow_v2.lock'):
        project = start.prepare(args.source, f'chatgpt_{args.plan}')
        dest = project / 'edit_plan.json'
        if dest.exists():
            raise RuntimeError(f'Existing edit plan protected, not overwritten: {dest}')
        # Real DB checks include V1 and V2 footage reservations; this cannot be
        # done from the short low-quality review ZIP alone.
        editorial.check_ranges(project, plan)
        editorial.check_blueprint(project, plan)
        if not (config()['min_seconds'] <= total <= config()['max_seconds']):
            raise RuntimeError('Runtime config does not permit this duration')
        # Atomic install; any validation failure removes only our newly written plan.
        tmp = dest.with_suffix('.json.partial')
        try:
            save(tmp, plan)
            os.replace(tmp, dest)
            gs.validate(project)
        except Exception:
            tmp.unlink(missing_ok=True)
            dest.unlink(missing_ok=True)
            raise
        editorial.remember(project, 'planned')
        state(project, 'planned', plan_key=key(plan))
        print(f'\nIMPORTED: {dest}')
        print('No Codex call, no new narration, no rendering, no publishing.')
        print(f'Next: cd "{AUTOMATION}"')
        print(f'      python3 start.py --project "{project}" --stop-after plan')
        print(f'When ready to render: python3 start.py --project "{project}"')


if __name__=='__main__':
    try:
        run()
    except Exception as exc:
        print(f'IMPORT STOPPED SAFELY: {exc}',file=sys.stderr)
        sys.exit(1)
