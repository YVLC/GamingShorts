"""Story-led gaming Shorts: evidence, added-value narration and explicit payoffs."""
import re
from pathlib import Path
from common import read, digest, key

def reuse_allowed(source_sha256):
    """User authorization is tied to the exact recording, not all future sources."""
    from common import config
    return bool(source_sha256) and source_sha256 in config().get('footage_reuse_sources',[])

VERSION='gaming-stories-v2'
ANGLES=('lore','secret','easter_egg','beginner_tip','game_fact','funny_moment','scary_moment','scenery','emotional_story','gaming_trend')
BRIEF=(
    'Create an interesting gaming story, not a replacement voice for the footage. '
    'Explore evidenced lore, secrets, easter eggs, practical tricks for beginners, '
    'interesting game facts, funny moments (such as the rainbow walk), emotional '
    'environmental mysteries, scary discoveries, beautiful scenery, or a verified gaming trend. '
    'These examples guide discovery; they are not proof that an event exists in the selected footage. '
    'Use an appropriate specific spoken hook immediately, develop the explanation or emotional/comedic '
    'arc, and resolve the hook with a supported payoff. End with Subscribe for more. over continuing '
    'relevant gameplay. Narration adds context, insight, a useful lesson or a distinct comedic perspective; '
    'do not dub characters, read subtitles as the script, or merely describe obvious action. '
    'Lore and relationship claims require visible dialogue or supplied verified references. '
    'A beginner tip must show the actual procedure and result. A secret/easter egg needs observable '
    'evidence; an inference must be qualified, never asserted as canon. '
    'Do not invent motives, facts, game mechanics, outcomes or current popularity. '
    'Prefer a fitting cleared trending instrumental; a vocal track is allowed when it supports the '
    'moment and leaves Garret intelligible. Keep the existing free Garret voice and real-timestamp '
    'yellow active-word captions throughout the narration. No static end card. '
    'Do not build the story around conversations, dialogue exchanges or interpretations of relationships. '
    'Focus on Cairn lore itself, environmental clues, demonstrated mechanics and visually interesting gameplay. '
    'Conversation may corroborate a fact but is not the story foundation or primary footage. '
    'Create original angles and hooks, never fictional secrets or mechanics presented as real. '
    'Use full-screen 9:16 subject-tracked framing from the original source, with captions over the footage. No blur filler. '
)

def properties(obj,string):
    return {
        'policy':{'type':'string','enum':[VERSION]},
        'story_type':{'type':'string','enum':list(ANGLES)},
        'story_basis':{'type':'string','enum':['world_lore','gameplay_demonstration','visual_discovery','scenery']},
        'viewer_value':string,'hook_promise':string,'payoff_evidence':string,
        'narration_added_value':string,
        'claims':{'type':'array','minItems':1,'items':obj({
            'claim':string,'evidence':string,
            'basis':{'type':'string','enum':['footage','reference','qualified_inference']},
            'reference_id':string})},
    }

def references(project):
    """Optional local research receipts. URLs alone are never factual evidence.

    The planner sees verified excerpts only. Trend claims additionally require
    dated platform-specific evidence. No network or automatic discovery here.
    """
    p=Path(project)/'research.json'
    if not p.exists():return []
    from datetime import date
    rows=read(p).get('sources',[]);seen=set()
    for row in rows:
        if not row.get('id') or row['id'] in seen:raise ValueError('Duplicate/missing research reference')
        seen.add(row['id'])
        if row.get('verified') is not True or not row.get('url','').startswith('https://') or not row.get('excerpt','').strip():raise ValueError('Research needs verified excerpt and source URL')
        date.fromisoformat(row['checked_date'])
    return rows

def validate(doc,refs=()):
    ed=doc.get('editorial',{})
    if ed.get('policy')!=VERSION:return
    if ed.get('story_type') not in ANGLES:raise ValueError('Choose a supported gaming story type')
    if ed.get('story_basis') not in ('world_lore','gameplay_demonstration','visual_discovery','scenery'):raise ValueError('Choose a visual story foundation, not a conversation')
    for field in ('viewer_value','hook_promise','payoff_evidence','narration_added_value'):
        if not isinstance(ed.get(field),str) or not ed[field].strip():raise ValueError('Story needs '+field)
    clips=doc.get('clips',[])
    if not clips or any(not c.get('narration','').strip() for c in clips):raise ValueError('Story needs narration through every beat')
    for c in clips:
        if c.get('framing')!='tracked_cover':raise ValueError('New visual stories require full-screen subject-tracked framing')
    if not clips[-1]['narration'].strip().endswith('Subscribe for more.'):raise ValueError('Missing final Subscribe for more.')
    if any('subscribe' in c['narration'].lower() for c in clips[:-1]):raise ValueError('CTA belongs after the payoff')
    claims=ed.get('claims',[])
    if not claims:raise ValueError('Story needs evidence-linked claims')
    sources={r['id']:r for r in refs}
    for claim in claims:
        if not claim.get('claim','').strip() or not claim.get('evidence','').strip():raise ValueError('Unsupported story claim')
        if claim.get('basis') not in ('footage','reference','qualified_inference'):raise ValueError('Unknown claim evidence basis')
        if claim['basis']=='reference' and claim.get('reference_id') not in sources:raise ValueError('Unknown research reference')
    if ed['story_type']=='gaming_trend':
        from datetime import datetime,timezone,date
        current=datetime.now(timezone.utc).date()
        verified=[sources[c['reference_id']] for c in claims if c['basis']=='reference']
        if not any(r.get('platform') and 0<=(current-date.fromisoformat(r['checked_date'])).days<=30 for r in verified):raise ValueError('Gaming trends require recent platform-specific evidence')
    # A transparent literal guard; independent semantic review still decides
    # whether narration explains a story rather than paraphrasing subtitles.
    dialogue=' '.join(x['text'] for x in ed.get('dialogue',[]))
    normalize=lambda s:re.findall(r"[a-z0-9]+",s.lower())
    spoken=' '.join(c['narration'] for c in clips).removesuffix('Subscribe for more.')
    if dialogue and normalize(spoken)==normalize(dialogue):raise ValueError('Subtitle reading is not a story-led script')

def review_passes(review):
    flags=('supported','immediate_action','distinct_story','adds_value','hook_paid_off','not_dialogue_dub','cta_after_payoff','visual_story')
    return all(review.get(k) is True for k in flags) and not review.get('issues')

def receipt_identity(project,doc):
    return key({'policy':digest(__file__),'plan':doc,'research':references(project)})

def require_review(project,doc,images=None):
    """Legacy-input planning uses the same independent story-quality screen."""
    if doc.get('editorial',{}).get('policy')!=VERSION:return
    p=Path(project);identity=receipt_identity(p,doc);receipt=p/'story_evidence_review.json'
    if receipt.exists():
        old=read(receipt)
        if old.get('identity')==identity and review_passes(old.get('review',{})) and all(Path(n).is_file() and digest(n)==sha for n,sha in old.get('images',{}).items()):return old
    if not images:raise ValueError('Current independent story evidence review required before speech')
    import editorial,json
    from common import save
    schema=editorial.obj({**{k:{'type':'boolean'} for k in ('supported','immediate_action','distinct_story','adds_value','hook_paid_off','not_dialogue_dub','cta_after_payoff','visual_story')},'issues':{'type':'array','items':editorial.S}})
    review=editorial.ai(p,BRIEF+' Independently check every claim against the attached exact gameplay windows and verified research excerpts. Treat script as a proposal, not evidence. immediate_action means a compelling immediate opening, including dialogue or emotional evidence; physical motion is not mandatory. Reject unsupported lore, a subtitle dub, unfulfilled hook or CTA before payoff. Return schema JSON only. Plan: '+json.dumps(doc)+' Research: '+json.dumps(references(p)),schema,images,'story_evidence_review')
    if not review_passes(review):raise ValueError('Independent story evidence review failed: '+json.dumps(review))
    result={'identity':identity,'review':review,'images':{str(n):digest(n) for n in images}}
    save(receipt,result);return result
