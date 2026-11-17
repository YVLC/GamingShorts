"""One-time versioned upgrade: retire warning feature and enable story planning."""
from pathlib import Path
import ast,json,shutil

ROOT=Path(__file__).resolve().parents[1]
APP=ROOT/'Automation/gamingshorts_v2'
RELEASE=ROOT/'Releases/2026-11-14-gaming-stories'
BEFORE=RELEASE/'before'

def edit(name,fn):
    p=APP/name;old=p.read_text(encoding='utf-8');backup=BEFORE/name
    backup.parent.mkdir(parents=True,exist_ok=True)
    if not backup.exists():shutil.copy2(p,backup)
    p.write_text(fn(old),encoding='utf-8')

def replace(text,old,new):
    if old not in text:raise ValueError('Missing upgrade anchor: '+old[:90])
    return text.replace(old,new)

def span(text,start,end,new=''):
    a=text.index(start);b=text.index(end,a)
    return text[:a]+new+text[b:]

def remove_methods(text,names):
    tree=ast.parse(text);lines=text.splitlines(keepends=True);ranges=[]
    for node in ast.walk(tree):
        if isinstance(node,(ast.FunctionDef,ast.AsyncFunctionDef)) and node.name in names:
            start=min([node.lineno]+[d.lineno for d in node.decorator_list])-1
            ranges.append((start,node.end_lineno))
    for a,b in sorted(ranges,reverse=True):del lines[a:b]
    return ''.join(lines)

def main():
    if (RELEASE/'upgrade-complete.json').exists():raise SystemExit('Already applied; do not replay an upgrade over later changes')
    RELEASE.mkdir(parents=True,exist_ok=True)
    def config(s):
        d=json.loads(s)
        for k in ('spoiler_warnings','spoiler_filtering','dialogue_narration_preference','dialogue_music_track_ids'):d.pop(k,None)
        d.update(editorial_policy='gaming-stories-v1',music_strategy='story_music',music_prefer_instrumental=True,music_prefer_trending=True,caption_mode='karaoke')
        return json.dumps(d,indent=2)+'\n'
    edit('config.json',config)
    def prefs(s):
        d=json.loads(s);d.pop('dialogue_reading',None)
        d.update(editorial='Create evidence-backed gaming stories with added-value commentary: lore, secrets, easter eggs, beginner tricks, facts, funny moments, emotional character arcs and verified gaming trends. Do not replace dialogue voices or simply read subtitles. Deliver a specific opening hook, a developed story and payoff, then Subscribe for more. over relevant gameplay.',
                 story_examples=['Rainbow walk: humor or a surprising visual reveal','Marco and Aava: a supported emotional relationship arc'],
                 music='Prefer fitting cleared trending instrumental tracks. Vocal music is allowed when appropriate and intelligibility is preserved. Never claim a trend without recent evidence.',
                 captions='Real speech-timestamp yellow active-word highlighting across all narration.')
        return json.dumps(d,indent=2)+'\n'
    edit('preferences.json',prefs)
    def start(s):
        s=replace(s,'import editorial, voices, spoilers','import editorial, voices')
        s=span(s,'    ap.add_argument(\n        "--set-spoiler-level",','    ap.add_argument(\n        "--align-captions",')
        for line in ('                a.set_spoiler_level,\n','                a.spoiler_note,\n','                a.confirm_major_spoilers,\n','                a.game_title,\n'):s=s.replace(line,'')
        s=span(s,'        if a.set_spoiler_level:','        if a.align_captions:')
        s=span(s,'            if (p / "edit_plan.json").exists() and spoilers.warnings_enabled():','            return\n        if a.approve:')
        s=s.replace('            classification = spoilers.require_ready(p, approval_for_major=a.confirm_major_spoilers)\n','').replace('                "spoiler_policy": "off",\n','')
        s=span(s,'            if spoilers.warnings_enabled():','            save(\n                p / "approval.json",')
        s=s.replace('            classification = spoilers.assess(p)\n','')
        s=span(s,'                if spoilers.warnings_enabled():','            if gs.completed(p):','                return\n')
        s=s.replace('spoilers.apply(p)','Path(read(p / "qc_report.json")["output"])')
        # Manual metadata retains music attribution without a warning wrapper.
        s=s.replace('            final = Path(read(p / "qc_report.json")["output"])','            final = Path(read(p / "qc_report.json")["output"])\n            from upload_metadata import write_metadata\n            write_metadata(p)')
        return s
    edit('start.py',start)
    def pub(s):
        s=replace(s,'import editorial, spoilers','import editorial')
        s=span(s,'    classification = spoilers.require_ready(','    if approval["output_sha256"]')
        return s.replace('    spoilers.validate_youtube(data["items"][0], classification["level"])\n','')
    edit('publication.py',pub)
    def gp(s):
        s=s.replace('from spoilers import filtering_enabled\n','import story_policy\n')
        s=s.replace('        spoiler={"type": "string", "enum": ["none", "possible", "major"]},\n','')
        s=span(s,'            spoilers=editorial.obj({','        )),')
        s=s.replace('        "spoiler_free": {"type": "boolean"},\n','')
        s=s.replace('    if filtering_enabled():required+=("spoiler_free",)\n','')
        s=s.replace('("Spoiler-free ordinary gameplay only: no endings, revelations or important secrets." if filtering_enabled() else "Spoilers, late-game content and endings are allowed. Retain honest spoiler metadata, but do not reject content or add warnings because of spoilers."),','story_policy.BRIEF,')
        s=s.replace('"Open on action; minimize maps, menus, exposition and establishing shots.",','"Open with a compelling supported hook and relevant visuals, including dialogue, lore or emotional scenes; minimize irrelevant setup.",')
        s=s.replace('"support and spoiler judgement. Narration must fit','"support. Narration must fit')
        s=s.replace('"Start on immediate gameplay action, no maps or introductions. Explain three concrete beats and "','"Start with a compelling story-specific hook and relevant gameplay, dialogue or discovery. Explain three concrete beats and "')
        s=s.replace('        + ("No spoiler footage. " if filtering_enabled() else "Spoiler footage and endings are allowed. ")\n','')
        s=s.replace('        + "No warning cards. Retain honest editorial.spoilers metadata; never relabel spoilers as none to gain eligibility. Choose a structure different from the last two stories. "','        + story_policy.BRIEF + " Choose a structure different from the last two stories. " +')
        s=s.replace('c.get("support") != "direct" or (filtering_enabled() and c.get("spoiler") != "none") or not c["evidence"].strip()','c.get("support") != "direct" or not c["evidence"].strip()')
        s=s.replace('Unsupported or spoiler-uncertain shot','Unsupported shot').replace('excluded, repeated or spoiler-uncertain','excluded or repeated')
        s=s.replace('        + ("Reject spoilers. " if filtering_enabled() else "Spoilers are allowed. Set spoiler_free truthfully, but spoilers alone are not an issue or rejection reason. ")','        + story_policy.BRIEF + " Require added-value explanation, a paid-off hook, no dialogue dubbing, and CTA after payoff. "')
        s=s.replace('"static openings or reused story ideas. Be conservative about evidence: uncertainty is a failure. "','"irrelevant openings or reused story ideas. A dialogue or emotional scene can be compelling. Be conservative about evidence: uncertainty is a failure. "')
        s=span(s,'    declaration=doc.get("editorial",{}).get("spoilers",{})','    store = GameStore()', '    story_policy.validate(doc,story_policy.references(p))\n')
        s=s.replace('        "preferences": read(HERE / "preferences.json"),','        "preferences": read(HERE / "preferences.json"),\n        "research": story_policy.references(project),')
        s=s.replace('    editorial.check_blueprint(p, doc)','    editorial.check_blueprint(p, doc)\n    story_policy.validate(doc,story_policy.references(p))')
        s=s.replace('    if not evidence_review_passes(review):','    if not story_policy.review_passes(review):')
        s=s.replace('            "plan_key": key(doc),','            "plan_key": key(doc),\n            "story_identity": story_policy.receipt_identity(p,doc),')
        s=s.replace('    scenes = store.scenes(r["id"])','    if doc.get("editorial",{}).get("policy")==story_policy.VERSION:\n        if receipt.get("story_identity")!=story_policy.receipt_identity(p,doc) or not story_policy.review_passes(receipt["review"]):raise ValueError("Story policy/research review changed; replan before speech")\n    scenes = store.scenes(r["id"])')
        # Extend the strict generated schema, leaving legacy plans readable.
        at='\n\ndef evidence_review_passes(review):'
        schema='\nPLAN["properties"]["editorial"]=editorial.obj(dict(PLAN["properties"]["editorial"]["properties"],**story_policy.properties(editorial.obj,editorial.S)))\nPLAN["properties"]["music"]=editorial.obj({"mood":{"type":"string","enum":["suspense","epic","funny","relaxed","action"]},"allow_vocals":{"type":"boolean"}})\nREVIEW=editorial.obj(dict(REVIEW["properties"],**{k:{"type":"boolean"} for k in ("adds_value","hook_paid_off","not_dialogue_dub","cta_after_payoff")}))\n'
        return replace(s,at,schema+at)
    edit('game_plan.py',gp)
    def discovery(s):
        s=s.replace('from spoilers import filtering_enabled','import story_policy')
        s=s.replace("    if filtering_enabled() and scene['spoiler']!='none':reasons.append('spoiler_policy')\n",'')
        s=s.replace("'filtering':filtering_enabled(),","'story_policy':story_policy.VERSION,")
        s=s.replace(",'score','spoiler'",",'score'")
        s=s.replace("        'Spoilers and endings are allowed under current policy; retain that context without excluding them. '\n",'        + story_policy.BRIEF +\n')
        s=s.replace("    weights={'failure':5,'action':5,'mechanic':4,'discovery':3,'unusual':2,'climb':1}","    weights={k:5 for k in story_policy.ANGLES};weights.update(failure=4,action=4,mechanic=5,discovery=5,unusual=4,climb=1)")
        s=s.replace("CreativeDiscovery_v2","CreativeDiscovery_v3")
        return s
    edit('event_discovery.py',discovery)
    def store(s):
        s=s.replace(' spoiler TEXT NOT NULL, evidence TEXT NOT NULL, tags_json TEXT NOT NULL,',' evidence TEXT NOT NULL, tags_json TEXT NOT NULL,')
        s=s.replace('        from spoilers import filtering_enabled\n','')
        s=s.replace('            (filtering_enabled() and scene["spoiler"] != "none")\n            or scene["confidence"] < 0.75','            scene["confidence"] < 0.75')
        s=s.replace('unused or spoiler-free','unused or eligible')
        s=s.replace('            db.executescript(SCHEMA)','            db.executescript(SCHEMA)\n            if "spoiler" in {r[1] for r in db.execute("PRAGMA table_info(game_scenes)")}:\n                backup=gs.ROOT/"Releases/2026-11-14-gaming-stories/legacy-database.sqlite3"\n                backup.parent.mkdir(parents=True,exist_ok=True)\n                if not backup.exists():\n                    with sqlite3.connect(backup) as target:db.backup(target)\n                db.execute("ALTER TABLE game_scenes DROP COLUMN spoiler")')
        return s
    edit('game_store.py',store)
    def index(s):
        s=s.replace('        "spoiler": {"type": "string", "enum": ["none", "possible", "major"]},\n','')
        s=s.replace('            or scene["spoiler"] not in ("none", "possible", "major")\n','').replace('confidence/category/spoiler review','confidence/category review')
        s=s.replace('                scene["spoiler"],\n','')
        s=span(s,'                "Major revelations, endings and important secret discoveries are spoilers.','                "Tag EVERY visible bridge')
        s=s.replace('?,?,?,?,?,?,?,?,?,?,?,?,?,?,?','?,?,?,?,?,?,?,?,?,?,?,?,?,?')
        s=s.replace('    "action",','    "lore", "secret", "easter_egg", "beginner_tip", "game_fact", "funny_moment", "emotional_story", "gaming_trend",\n    "action",')
        s=s.replace('"Identify distinct action, climbing challenges, failures, mechanics, discoveries or unusual moments; "','"Identify lore in readable dialogue, secrets, easter eggs, demonstrated beginner tricks, facts, humor, emotional relationship scenes, action, failures and unusual discoveries; "')
        return s
    edit('game_index.py',index)
    edit('local_index.py',lambda s:s.replace("      'Classify spoilers none, possible, or major; none requires positive confidence of ordinary spoiler-free gameplay. All bridge scenes/approaches must be tagged bridge and are excluded. '","      'Look for lore, secrets, easter eggs, beginner tricks, facts, funny and emotional character moments, including readable dialogue. All bridge scenes/approaches must be tagged bridge and are excluded. '").replace('?,?,?,?,?,?,?,?,?,?,?,?,?,?,?','?,?,?,?,?,?,?,?,?,?,?,?,?,?').replace('or spoiler assertion','or story assertion'))
    def editorial(s):
        s=s.replace('Assess spoiler risk conservatively; exclude uncertain ending footage. ','')
        s=s.replace('Declare editorial.spoilers with level none, minor or major and a rationale; the existing renderer handles warning cards. ','')
        s=s.replace('from common import config, read, save, key, now, run, state, HERE','from common import config, read, save, key, now, run, state, HERE\nimport story_policy')
        s=s.replace('    prompt = (\n','    prompt = (\n        story_policy.BRIEF +\n')
        s=s.replace('                "game_title": S,','                "game_title": S,\n                **story_policy.properties(obj,S),')
        # Both legacy-input and full-game planning now request the same story contract.
        s=s.replace('    check_blueprint(p, doc)','    check_blueprint(p, doc)\n    story_policy.validate(doc,story_policy.references(p))')
        return s
    edit('editorial.py',editorial)
    def dm(s):
        s=s.replace("    level={'none':'none','possible':'minor','major':'major'}[scene['spoiler']]\n",'')
        s=s.replace("        'spoilers':{'level':level,'rationale':'Historical source classification retained; filtering is disabled','contains_ending':False}},","        },")
        return s.replace(' Spoiler filtering remains off.','')
    edit('dialogue_mission.py',dm)
    edit('dialogue_editorial.py',lambda s:s.replace(",spoiler_policy='off'",''))
    # Preserve retired source/tests as release artifacts, outside runtime imports.
    for name in ('spoilers.py','tests/test_spoilers.py','tests/test_spoilers_disabled.py'):
        p=APP/name;target=BEFORE/name;target.parent.mkdir(parents=True,exist_ok=True);shutil.copy2(p,target);p.unlink()
    # Update tests tied exclusively to removed behavior; keep other integrity checks.
    edit('tests/test_expanded_discovery.py',lambda s:remove_methods(s,{
        'test_disabled_warnings_do_not_add_spoiler_titles','test_spoiler_filtering_can_be_disabled_without_disabling_other_guards',
        'test_evidence_and_originality_not_disabled_with_spoilers','test_major_guard_off_still_reaches_source_integrity'}).replace('gs,spoilers,game_plan','gs,game_plan'))
    edit('tests/test_local_first.py',lambda s:remove_methods(s,{'test_v3_requires_explicit_spoiler_fields_in_generated_schema','test_major_spoiler_guard_holds_before_production'}))
    edit('tests/test_full_game.py',lambda s:s.replace('            "spoiler": "none",\n','').replace('?,?,?,?,?,?,?,?,?,?,?,?,?,?,?','?,?,?,?,?,?,?,?,?,?,?,?,?,?').replace("    @patch('spoilers.filtering_enabled',return_value=True)\n",'').replace('def test_spoilers_static_unknown_and_bridge_excluded(self,_spoiler_policy):','def test_static_unknown_and_bridge_excluded(self):').replace('                {"spoiler": "major"},\n','').replace('                {"spoiler": "possible"},\n',''))
    edit('tests/test_music_intelligence.py',lambda s:s.replace('import spoilers,publication','import upload_metadata,publication').replace("spoilers.music_metadata(self.p,{'level':'none','game':'Fixture'})","upload_metadata.music_metadata(self.p,{'game':'Fixture'})"))
    save={'version':'gaming-stories-v1','archived_before':str(BEFORE),'status':'applied; validation pending'}
    (RELEASE/'upgrade-complete.json').write_text(json.dumps(save,indent=2)+'\n')

if __name__=='__main__':main()
