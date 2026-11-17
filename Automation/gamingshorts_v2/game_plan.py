"""Novel full-game stories, inspected evidence and bounded production batches."""

import json
from pathlib import Path

from common import HERE, digest, key, now, read, save, state, config
import editorial
import creative_history
import gaming_shorts as gs
import shared_index
import story_policy
from game_store import GameStore, interval, overlaps
from game_index import cached_ai, checked_recording, authorize_analysis_retry

WINDOW = editorial.obj({"scene_id": editorial.S, "start": editorial.N, "duration": editorial.N})
CONCEPT = editorial.obj(
    dict(
        editorial.CANDIDATE["properties"],
        windows={"type": "array", "minItems": 3, "maxItems": 8, "items": WINDOW},
    )
)
SCAN = editorial.obj(
    dict(
        editorial.SCAN["properties"],
        candidates={"type": "array", "minItems": 3, "maxItems": 3, "items": CONCEPT},
    )
)
CLIP = editorial.obj(
    dict(
        editorial.PLAN["properties"]["clips"]["items"]["properties"],
        scene_id=editorial.S,
        support={"type": "string", "enum": ["direct", "uncertain"]},
    )
)
PLAN = editorial.obj(
    dict(
        editorial.PLAN["properties"],
        editorial=editorial.obj(dict(
            editorial.PLAN["properties"]["editorial"]["properties"],
        )),
        clips={"type": "array", "minItems": 3, "maxItems": 10, "items": CLIP},
    )
)
REVIEW = editorial.obj(
    {
        "supported": {"type": "boolean"},
        "immediate_action": {"type": "boolean"},
        "distinct_story": {"type": "boolean"},
        "issues": {"type": "array", "items": editorial.S},
    }
)
PLAN["properties"]["editorial"]=editorial.obj(dict(PLAN["properties"]["editorial"]["properties"],**story_policy.properties(editorial.obj,editorial.S)))
PLAN["properties"]["music"]=editorial.obj({"mood":{"type":"string","enum":["suspense","epic","funny","relaxed","action"]},"allow_vocals":{"type":"boolean"}})
PLAN=editorial.obj(PLAN['properties'])
REVIEW=editorial.obj(dict(REVIEW["properties"],**{k:{"type":"boolean"} for k in ("adds_value","hook_paid_off","not_dialogue_dub","cta_after_payoff","visual_story")}))


def evidence_review_passes(review):
    required=("supported","immediate_action","distinct_story")
    return all(review.get(k) is True for k in required) and not review.get('issues')


def context(project, r):
    return {
        "game": r["game"],
        "source_sha256": r["sha256"],
        "history": editorial.history(project),
        "preferences": read(HERE / "preferences.json"),
        "quality_reference": __import__('quality_reference').context(),
        "research": story_policy.references(project),
        "creative_history": [dict(id=h['id'],facts=h['facts'],ranges=[(c['start'],c['duration']) for c in h['plan']['clips']]) for h in creative_history.history(project)],
        "rules": [
            "A different central observable event and conclusion are mandatory; music, rewritten synonyms or generic mountain difficulty do not make a new story.",
            "Seek distinct failures, close calls, recoveries, humor, mechanics, discoveries, successes or moving atmospheric reveals, with honest visible outcomes.",
            story_policy.BRIEF,
            "No bridge scenes in Cairn, including approaches and repeated camera angles.",
            "No fabricated outcome, invented lore or unsupported narration.",
            "Open with a concrete discovery, demonstrated mechanic, environmental lore clue or striking scene; minimize setup. Do not select conversations as the main story.",
            "Different narration over repeated footage is not a new story.",
            "Never publish automatically. No warning cards.",
        ],
    }


def validate_windows(windows, scenes, r, inspected=None):
    ranges = []
    for window in windows:
        scene = next((s for s in scenes if s["id"] == window["scene_id"]), None)
        if scene is None:
            raise ValueError("Concept references unknown/unavailable scene")
        a, b = interval(
            window["start"], float(window["start"]) + float(window["duration"]), r["duration"]
        )
        if a < scene["start"] or b > scene["end"]:
            raise ValueError("Concept is outside indexed evidence")
        if inspected is not None and not any(
            scene["id"] == sid and a >= x and b <= y for sid, x, y in inspected
        ):
            raise ValueError("Narrative uses footage outside dense inspection")
        if any(overlaps(a, b, x, y) for x, y in ranges):
            raise ValueError("Repeated footage inside concept")
        ranges.append((a, b))


def validate_concepts(scan,scenes,r,inspected):
    editorial.check_candidates(scan)
    if len(scan['candidates'])!=3 or not isinstance(scan['selected'],int) or not 0<=scan['selected']<3:
        raise ValueError('Invalid concept selection')
    for candidate in scan['candidates']:validate_windows(candidate['windows'],scenes,r,inspected)
    for i,candidate in enumerate(scan['candidates']):
        ids={w['scene_id'] for w in candidate['windows']}
        for prior in scan['candidates'][:i]:
            previous={w['scene_id'] for w in prior['windows']}
            if len(ids & previous)/max(1,len(ids | previous))>.6:
                raise ValueError('Alternative concepts substantially reuse the same visual scenes')


def shortlist(project, r, store):
    """Rank first, then inspect up to 12 unused scenes; never scan seven hours again."""
    candidates = []
    from event_discovery import prioritized
    for scene in prioritized(store.scenes(r["id"]),r):
        if scene["end"] - scene["start"] >= 4 and store.eligible(scene, extra=candidates):
            candidates.append(scene)
        if len(candidates) == config().get('creative_scene_budget',12):
            break
    if len(candidates) < 3:
        raise ValueError(
            "Material exhausted: fewer than three sufficiently interesting, distinct unused scenes. No speech requested."
        )
    images, inspected = [], []
    for scene in candidates:
        # Include the supported outcome rather than truncating every event at 14s.
        a = scene["start"]
        b = min(scene["end"], a + 40)
        cursor=a
        while cursor<b:
            span=min(14,b-cursor)
            images.append(shared_index.dense_proxy(project,scene,cursor,span))
            cursor+=span
        inspected.append((scene["id"], a, b))
    return candidates, images, inspected


def plan(project):
    if config().get('editorial_policy')=='dialogue-editorial-v1':
        from dialogue_mission import plan_next
        return plan_next(project)
    creative_history.refresh()
    p = Path(project)
    m = read(p / "manifest.json")
    data = m["full_game"]
    store = GameStore()
    r = store.recording(data["recording"])
    checked_recording(r)
    if store.recording()["id"] != r["id"]:
        raise ValueError("Another game is active; explicitly select this game before production")
    if r["status"] != "indexed" or r["index_key"] != data["index_key"]:
        raise ValueError("Full recording index is incomplete or changed")
    scenes, images, inspected = shortlist(p, r, store)
    ctx = context(p, r)
    summary = [
        {k: s[k] for k in ("id", "start", "end", "description", "category", "evidence", "score")}
        for s in scenes
    ]
    prompt = (
        "Inspect the dense timestamped ORIGINAL gameplay windows. Propose exactly three SUBSTANTIALLY DIFFERENT "
        "story concepts with different canonical narrative structures; select the strongest entertaining, clear, "
        "novel and visually evidenced one. Every candidate window must reference a listed scene_id and fit the "
        "dense inspected range, 4–12 seconds. No inference of unseen action or outcome. If evidence cannot "
        "support a concept, do not fabricate: leave no valid candidate and let production stop. "
        "Return schema JSON only, no tools. Context: "
        + json.dumps(ctx)
        + " Scenes: "
        + json.dumps(summary)
        + " Inspected scene_id/start/end: "
        + json.dumps(inspected)
    )
    scan = cached_ai(p / "FullGameAnalysis", prompt, SCAN, images, "concepts")
    try:validate_concepts(scan,scenes,r,inspected)
    except ValueError as error:
        save(p/'rejected_concepts.json',{'response':scan,'reason':str(error)})
        correction=(prompt+' A completed prior response failed strict validation: '+str(error)+
            '. Correct the concepts. Within EACH concept, sort source intervals and make them disjoint; '
            'a hook cannot replay source frames later in that same Short. Every window must remain inside inspected ranges. '
            'Preserve distinct central events and truthful outcomes, with room for the final CTA after the payoff. '
            'Do not shift ranges outside the supplied evidence. Return schema JSON only. Rejected response: '+json.dumps(scan))
        scan=cached_ai(p/'FullGameAnalysis',correction,SCAN,images,'concepts_correction')
        validate_concepts(scan,scenes,r,inspected)
    save(p / "story_candidates.json", scan)
    selected = scan["candidates"][scan["selected"]]
    # Inspect exact selected windows again, caching across projects by source/time.
    dense = [shared_index.dense(p, w["start"], w["duration"]) for w in selected["windows"]]
    selected_ranges = [
        (w["scene_id"], float(w["start"]), float(w["start"]) + float(w["duration"]))
        for w in selected["windows"]
    ]
    prompt = (
        "Write the final evidence-supported 25–40-second Short, 3–10 clips of 2–12 seconds, "
        "using only the selected inspected windows. Every shot includes scene_id, direct visual evidence, "
        "support. Narration must fit at about two words per second, with no invented "
        "Use tracked_cover fullscreen 9:16, tracking keyframes at camera changes or subject movement, and safe caption_y per shot. No blurred filler. The story foundation must be world lore, demonstrated mechanics, visual discovery or scenery; do not select conversations as the main story. "
        "events, intent, lore or outcome. Captions 2–7 words, synchronized later to real speech timestamps. "
        "Start with a compelling story-specific hook and relevant gameplay or discovery. Explain three concrete beats and "
        "pay off the hook before the final 1–2-second CTA. Last narration ends exactly Subscribe for more. "
        + story_policy.BRIEF + " Choose a structure different from the last two stories. " +
        "Return schema JSON only, no tools. Context: "
        + json.dumps(ctx)
        + " Concept: "
        + json.dumps(selected)
    )
    doc = cached_ai(p / "FullGameAnalysis", prompt, PLAN, dense, "narrative")
    validate_windows(doc["clips"], scenes, r, selected_ranges)
    editorial.check_blueprint(p, doc)
    story_policy.validate(doc,story_policy.references(p))
    if doc.get("opening_action"):
        raise ValueError("Unreviewed extra opening footage is not allowed")
    if any(
        c.get("support") != "direct" or not c["evidence"].strip()
        for c in doc["clips"]
    ):
        raise ValueError("Unsupported shot; no voice requested")
    # Independent visual review is an AI editorial screen, never human approval.
    review = cached_ai(
        p / "FullGameAnalysis",
        "Independently verify each narration claim, hook and payoff against ONLY the attached timestamped "
        "gameplay frames. Reject invented actions/outcomes, ambiguous evidence, bridges in Cairn, "
        "irrelevant openings, conversation-led stories or reused story ideas. Be conservative about evidence: uncertainty is a failure. "
        + story_policy.BRIEF + " Require added-value explanation, a paid-off hook, no dialogue dubbing, and CTA after payoff. immediate_action means a compelling immediate story opening; physical motion is not required. Verified research excerpts in Context may support reference claims; reject other outside claims. "
        + "Do not treat the proposed script as evidence. Return schema JSON, no tools. Plan: "
        + json.dumps(doc)
        + " Context: "
        + json.dumps(ctx),
        REVIEW,
        dense,
        "evidence_review",
    )
    if not story_policy.review_passes(review):
        save(p / "rejected_evidence.json", {"plan": doc, "review": review})
        raise ValueError("Editorial evidence review rejected the story: " + json.dumps(review))
    # gs.validate requires a file; the ledger is committed before making the plan resumable.
    save(p / "edit_plan.candidate.json", doc)
    total = sum(float(c["duration"]) for c in doc["clips"])
    if not 25 <= total <= 40 or any(not 2 <= float(c["duration"]) <= 12 for c in doc["clips"]):
        raise ValueError("Invalid final story duration")
    creative_history.require_review(p, doc, invoke=True, images=dense)
    store.reserve(p, doc, scenes)
    save(
        p / "evidence_review.json",
        {
            "plan_key": key(doc),
            "story_identity": story_policy.receipt_identity(p,doc),
            "index_key": r["index_key"],
            "review": review,
            "inspected": selected_ranges,
            "scenes": [s["id"] for s in scenes],
        },
    )
    save(p / "edit_plan.json", doc)
    gs.validate(p)
    editorial.remember(p)
    state(p, "planned", plan_key=key(doc), full_game_batch=data["batch"])


def guard(project, doc, *, require_active=True):
    """Runs before narration/render/approval; old projects bypass this additive guard."""
    p = Path(project)
    if doc.get('editorial',{}).get('policy')=='dialogue-editorial-v1':
        from dialogue_editorial import guard as dialogue_guard
        return dialogue_guard(p,doc,require_active=require_active)
    m = read(p / "manifest.json")
    data = m.get("full_game")
    if not data:
        return
    story_policy.validate(doc,story_policy.references(p))
    store = GameStore()
    r = store.recording(data["recording"])
    checked_recording(r)
    if m.get("source_bundle") or m["source"] != r["source"] or m["source_sha256"] != r["sha256"]:
        raise ValueError("New full-game Shorts must use only the authoritative original recording")
    if require_active and store.recording()["id"] != r["id"]:
        raise ValueError("Active game differs; no automatic game switch")
    receipt = read(p / "evidence_review.json")
    if (
        key(doc) != receipt["plan_key"]
        or data["index_key"] != receipt["index_key"]
        or r["index_key"] != data["index_key"]
    ):
        raise ValueError("Plan/index changed since visual evidence review; no speech requested")
    if doc.get("editorial",{}).get("policy")==story_policy.VERSION:
        if receipt.get("story_identity")!=story_policy.receipt_identity(p,doc) or not story_policy.review_passes(receipt["review"]):raise ValueError("Story policy/research review changed; replan before speech")
    scenes = store.scenes(r["id"])
    validate_windows(doc["clips"], scenes, r, receipt["inspected"])
    for clip in doc["clips"]:
        scene = next(s for s in scenes if s["id"] == clip["scene_id"])
        if not store.eligible(scene, project=p):
            raise ValueError("Shot is reserved elsewhere, excluded or repeated")
    with store.connect() as db:
        reservations = [
            dict(x) for x in db.execute("SELECT * FROM game_shots WHERE project=?", (str(p),))
        ]
    if any(
        not any(
            x["scene"] == c["scene_id"]
            and abs(x["start"] - c["start"]) < 0.001
            and abs(x["end"] - c["start"] - c["duration"]) < 0.001
            for x in reservations
        )
        for c in doc["clips"]
    ):
        raise ValueError("Missing durable footage reservation")


def create_batch(count=3, *, resume=None, retry_ai=False):
    if not 1 <= count <= 3:
        raise ValueError("Controlled batches contain one to three Shorts")
    from start import prepare
    from job_store import JobStore

    store = GameStore()
    r = store.recording()
    checked_recording(r)
    if r["status"] != "indexed":
        raise ValueError("Index the complete authoritative recording first")
    queue = JobStore(gs.ROOT)
    proof = queue.admit_source(r["source"])
    if proof["sha256"] != r["sha256"]:
        raise ValueError("Source identity changed")
    identity = resume or key({"recording": r["id"], "created": now()})[:20]
    if resume:
        old = store.batch(identity)
        if (
            old["recording"] != r["id"]
            or old["index_key"] != r["index_key"]
            or old["status"] not in ("planning", "needs_attention")
        ):
            raise ValueError("Batch is not resumable under the active source/index")
        count = old["count"]
    with store.connect() as db:
        if (
            not resume
            and db.execute(
                "SELECT 1 FROM game_batches WHERE status IN ('planning','running','needs_attention')"
            ).fetchone()
        ):
            raise ValueError(
                "Recover the existing unfinished batch explicitly before starting another"
            )
        db.execute(
            "INSERT OR IGNORE INTO game_batches VALUES (?,?,?,?,?,'planning',NULL,?)",
            (identity, r["game"], r["id"], r["index_key"], count, now()),
        )
        db.execute("UPDATE game_batches SET status='planning',error=NULL WHERE id=?", (identity,))
    print("Batch:", identity, flush=True)
    try:
        for i in range(count):
            p = prepare(
                Path(r["source"]),
                f"game_{identity}_{i + 1}",
                verified_source=proof,
                full_game_context={
                    "game": r["game"],
                    "recording": r["id"],
                    "index_key": r["index_key"],
                    "batch": identity,
                },
            )
            manifest = read(p / "manifest.json")
            manifest["full_game"] = {
                "game": r["game"],
                "recording": r["id"],
                "index_key": r["index_key"],
                "batch": identity,
            }
            save(p / "manifest.json", manifest)
            with store.connect() as db:
                db.execute(
                    "INSERT OR IGNORE INTO game_batch_items VALUES (?,?,?,?,NULL)",
                    (identity, i, str(p), "{}"),
                )
            if not (p / "edit_plan.json").exists():
                if retry_ai:
                    authorize_analysis_retry(p / "FullGameAnalysis", include_completed=True)
                plan(p)
            guard(p, gs.validate(p))
            with store.connect() as db:
                db.execute(
                    "UPDATE game_batch_items SET candidate_json=? WHERE batch=? AND ordinal=?",
                    (json.dumps(read(p / "story_candidates.json")), identity, i),
                )
        with store.connect() as db:
            db.execute("UPDATE game_batches SET status='planned' WHERE id=?", (identity,))
    except (Exception, KeyboardInterrupt) as error:
        with store.connect() as db:
            db.execute(
                "UPDATE game_batches SET status='needs_attention',error=? WHERE id=?",
                (str(error), identity),
            )
        raise
    return store.batch(identity)


def run_batch(identity, *, retry=False):
    """Dispatch only this batch through the existing serialized queue worker."""
    from common import locked
    from job_store import JobStore
    import automation
    from start import slug

    store = GameStore()
    batch = store.batch(identity)
    if batch["recording"] != store.recording()["id"]:
        raise ValueError("Select the batch game explicitly before running it")
    if batch["status"] == "running" and not retry:
        raise ValueError("Interrupted batch requires --retry; no automatic speech retry")
    if batch["status"] not in ("planned", "running", "needs_attention"):
        raise ValueError("Batch is not ready for production")
    if len(batch["items"]) != batch["count"] or any(
        not (Path(x["project"]) / "edit_plan.json").exists() for x in batch["items"]
    ):
        raise ValueError("Batch planning incomplete; use batch --retry first")
    queue = JobStore(gs.ROOT)
    with locked(gs.ROOT / "Database/.automation.lock"):
        with store.connect() as db:
            db.execute(
                "UPDATE game_batches SET status='running',error=NULL WHERE id=?", (identity,)
            )
        try:
            item_errors = []
            for item in batch["items"]:
                p = Path(item["project"])
                try:
                    guard(p, gs.validate(p))
                except Exception as error:
                    item_errors.append({"project": str(p), "error": str(error)})
                    if item["job"] and queue.get(item["job"])["status"] == "queued":
                        queue.finish(item["job"], "needs_attention", error=str(error))
                    print(
                        f"Project needs attention: {p}: {error}; continuing other batch items",
                        flush=True,
                    )
                    continue
                if (p / "state.json").exists() and read(p / "state.json").get("stage") in (
                    "rejected",
                    "approved",
                    "published",
                ):
                    continue
                variant = slug(f"game_{identity}_{item['ordinal'] + 1}")
                job = (
                    queue.get(item["job"])
                    if item["job"]
                    else queue.enqueue(store.recording()["source"], variant)
                )
                if job.get("duplicate_submission") and job.get("project") not in (None, str(p)):
                    raise ValueError("Queue duplicate belongs to another project")
                with store.connect() as db:
                    db.execute(
                        "UPDATE game_batch_items SET job=? WHERE batch=? AND ordinal=?",
                        (job["id"], identity, item["ordinal"]),
                    )
                if job["status"] == "running":
                    if not retry:
                        raise ValueError("Interrupted job requires --retry")
                    queue.finish(
                        job["id"],
                        "needs_attention",
                        error="Explicit recovery of interrupted V3 batch",
                    )
                    job = queue.get(job["id"])
                if job["status"] == "needs_attention":
                    if not retry:
                        raise ValueError(
                            "Job needs attention; inspect logs then explicitly --retry"
                        )
                    job = queue.retry(job["id"])
                if job["status"] == "ready_for_review":
                    if not gs.completed(p):
                        raise ValueError(
                            "Completed output changed; inspect instead of silently regenerating"
                        )
                    continue
                claimed = queue.claim_id(job["id"])
                if claimed is None:
                    raise ValueError("Job could not be claimed")
                automation.run_job(queue, claimed)
                if queue.get(job["id"])["status"] != "ready_for_review":
                    # Continue other valid items; never retry uncertain speech automatically.
                    print(
                        f"Job {job['id']} needs attention; continuing other batch items", flush=True
                    )
            outcomes = [
                queue.get(x["job"])["status"] for x in store.batch(identity)["items"] if x["job"]
            ]
            complete = (
                not item_errors
                and len(outcomes) == batch["count"]
                and all(s == "ready_for_review" for s in outcomes)
            )
            with store.connect() as db:
                db.execute(
                    "UPDATE game_batches SET status=?,error=? WHERE id=?",
                    (
                        "ready_for_review" if complete else "needs_attention",
                        None
                        if complete
                        else json.dumps(
                            item_errors
                            or ["Inspect individual projects/jobs before explicit retry"]
                        ),
                        identity,
                    ),
                )
        except (Exception, KeyboardInterrupt) as error:
            with store.connect() as db:
                db.execute(
                    "UPDATE game_batches SET status='needs_attention',error=? WHERE id=?",
                    (str(error), identity),
                )
            raise
    return store.batch(identity)


def render(project, voice_folder):
    """Keep the proven renderer; reuse only this original's strict integrity receipt."""
    from common import verified_source_receipts
    from game_index import verify_integrity, require_disk

    p = Path(project)
    guard(p, gs.validate(p))
    from creative_history import require_review
    require_review(p, gs.validate(p))
    preflight(p, gs.validate(p))
    store = GameStore()
    r = store.recording(read(p / "manifest.json")["full_game"]["recording"])
    require_disk(r, pending=set())
    verify_integrity(r)
    with verified_source_receipts(
        {r["source"]: {"sha256": r["sha256"], "fingerprint": json.loads(r["fingerprint"])}}
    ):
        result = gs.render(p, voice_folder)
        checked_recording(r)
    return result


def preflight(project, doc):
    """Sample only selected originals before speech; cached and static-aware."""
    from quality_checks import measure_cadence, rate

    p = Path(project)
    data = read(p / "manifest.json")["full_game"]
    r = GameStore().recording(data["recording"])
    source = checked_recording(r)
    video = next(
        s for s in json.loads(r["probe_json"])["streams"] if s.get("codec_type") == "video"
    )
    fps = rate(video["avg_frame_rate"])
    code = digest(Path(__file__).with_name("quality_checks.py"))
    for clip in doc["clips"]:
        seconds = min(3, float(clip["duration"]))
        token = key(
            {
                "source": r["sha256"],
                "start": clip["start"],
                "duration": seconds,
                "fps": str(fps),
                "qc": code,
            }
        )
        receipt = (
            gs.ROOT
            / "FootageIndex"
            / ("sha256_" + r["sha256"])
            / "ProductionCadence"
            / (token + ".json")
        )
        if receipt.exists():
            saved = read(receipt)
            if saved.get("key") != token or key(saved["result"]) != saved.get("result_key"):
                raise ValueError("Source cadence receipt changed; inspect before speech")
            result = saved["result"]
        else:
            result = measure_cadence(source, clip["start"], seconds, fps)
            checked_recording(r)
            save(receipt, {"key": token, "result_key": key(result), "result": result})
        if result.get("active_windows") and result.get("cadence_limited"):
            from source_context_cadence import accepted as accepted_context
            if accepted_context(p,doc,clip,r,result):
                print(f"Retaining measured source-native ambient cadence: {result['active_updates_per_second']:.2f} visual updates/second; no interpolation.",flush=True)
                continue
            raise ValueError(
                f"Original source reports {fps} FPS but selected moving footage has only "
                f"{result['active_updates_per_second']:.2f} visual updates/second. No speech requested; select genuine-cadence footage."
            )
    from visual_preflight import require_review as require_visual_review
    require_visual_review(p,doc)
