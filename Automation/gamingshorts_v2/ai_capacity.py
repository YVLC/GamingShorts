"""Persistent Codex circuit breaker. Capacity reads never start a model turn.

Only definite quota rejections may be replayed automatically; unknown outcomes
remain subject to the existing explicit-inspection rule. No speech retries.
"""
import json
import queue
import sqlite3
import subprocess
import threading
import time
from pathlib import Path
from common import now
import gaming_shorts as gs

INTERVAL = 900

class Deferred(RuntimeError):
    pass

def connection():
    db = sqlite3.connect(gs.ROOT/'Database/editorial_v2.sqlite3', timeout=30)
    db.execute('CREATE TABLE IF NOT EXISTS ai_capacity_v1 (id INTEGER PRIMARY KEY CHECK(id=1), state TEXT NOT NULL)')
    return db

def state():
    with connection() as db:
        row = db.execute('SELECT state FROM ai_capacity_v1 WHERE id=1').fetchone()
    return json.loads(row[0]) if row else {}

def persist(value):
    with connection() as db:
        db.execute('INSERT INTO ai_capacity_v1 VALUES (1,?) ON CONFLICT(id) DO UPDATE SET state=excluded.state', (json.dumps(value),))

def quota_failure(error):
    message = str(error).lower().replace('\u2019', "'").replace('\u2018', "'")
    return any(x in message for x in ('usage_limit_reached', 'usage limit reached', 'insufficient_quota',
        'rate_limit_exceeded', 'rate limit reached', 'insufficient_credits',
        'subscription_sharing_usage_limit_exceeded', 'you have hit your usage limit',
        "you've hit your usage limit", 'credits exhausted', 'credit balance is exhausted',
        'workspace credits depleted'))

def capacity_read():
    """Read-only JSON-RPC; stdout is parsed in memory, never logged wholesale."""
    process = subprocess.Popen(['codex','app-server'], stdin=subprocess.PIPE,
        stdout=subprocess.PIPE, stderr=subprocess.DEVNULL, text=True)
    responses = queue.Queue()
    def collect():
        for line in process.stdout:
            try: responses.put(json.loads(line))
            except ValueError: pass
        responses.put(None)
    thread = threading.Thread(target=collect, daemon=True);thread.start()
    def send(value):
        process.stdin.write(json.dumps(value)+'\n');process.stdin.flush()
    def receive(identifier):
        deadline = time.monotonic()+25
        while time.monotonic()<deadline:
            result = responses.get(timeout=max(.1,deadline-time.monotonic()))
            if result is None:raise RuntimeError('Capacity reader closed')
            if result.get('id')==identifier:
                if 'error' in result:raise RuntimeError('Capacity endpoint unavailable')
                return result['result']
        raise TimeoutError('Capacity read timed out')
    try:
        send({'id':1,'method':'initialize','params':{'clientInfo':{'name':'gamingshorts_capacity','version':'1.0'}}})
        receive(1);send({'method':'initialized','params':{}})
        send({'id':2,'method':'account/rateLimits/read','params':{}})
        return receive(2)
    finally:
        process.terminate()
        try:process.wait(timeout=5)
        except subprocess.TimeoutExpired:process.kill();process.wait()
        process.stdin.close();process.stdout.close();thread.join(timeout=1)

def available(result):
    buckets = result.get('rateLimitsByLimitId') or {'codex':result.get('rateLimits')}
    # Conservative across reported buckets: never infer capacity from missing data.
    windows = []
    for bucket in buckets.values():
        if not bucket:return False
        if bucket.get('rateLimitReachedType') or bucket.get('spendControlReached'):return False
        # A zero add-on-credit balance alone does not exhaust included windows.
        for name in ('primary','secondary'):
            window = bucket.get(name)
            if window:
                used = window.get('usedPercent')
                if not isinstance(used,(int,float)) or not 0<=used<100:return False
                windows.append(window)
    return bool(windows)

def recovered(previous, current):
    if not available(current):return False
    if not previous:return True
    old = previous.get('rateLimitsByLimitId') or {'codex':previous.get('rateLimits')}
    new = current.get('rateLimitsByLimitId') or {'codex':current.get('rateLimits')}
    for identifier,bucket in new.items():
        before=old.get(identifier) or {}
        for name in ('primary','secondary'):
            a=before.get(name) or {};b=bucket.get(name) or {}
            if isinstance(a.get('usedPercent'),(int,float)) and isinstance(b.get('usedPercent'),(int,float)):
                if b['usedPercent']<a['usedPercent']:return True
        if (bucket.get('credits') or {}).get('hasCredits') and not (before.get('credits') or {}).get('hasCredits'):return True
    return False

def reject(error, observed=None):
    # Store a bounded explanation rather than raw CLI logs or credentials.
    persist({'blocked':True,'reason':'Codex quota/credit rejection','updated_utc':now(),
             'next_check':time.time()+INTERVAL,'rejected_limits':observed})

def require_capacity():
    current = state()
    if not current.get('blocked'):return
    if time.time()>=current.get('next_check',0):
        try:ready = recovered(current.get('rejected_limits'),capacity_read())
        except Exception:ready = False
        current.update(blocked=not ready,updated_utc=now(),next_check=time.time()+INTERVAL)
        persist(current)
        if ready:return
    raise Deferred('AI capacity paused; local checkpoints retained. Read-only capacity checks every 15 minutes.')

def wait(operation, on_wait):
    """Used after local work is exhausted; never repeatedly submit generation."""
    while True:
        try:return operation()
        except Deferred as error:
            on_wait(str(error))
            time.sleep(30)
