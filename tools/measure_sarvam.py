"""Measure Sarvam speech-to-text through a local Bolo Line server (task T10). Spends live Sarvam credit.

From the repository root, with a local server whose environment has SARVAM_API_KEY:
    .venv/bin/python tools/measure_sarvam.py --base http://127.0.0.1:8000
Offline check of the guards and the scoring (fake Sarvam, no network, no key):
    .venv/bin/python tools/measure_sarvam.py --self-test

Each clip in web/samples/ goes through /api/stt and then /api/parse, the way the operator screen
sends it (s3b answers s3's question for the temperature). Then --repeat more calls on s1 time the
replies. Guards: at most MAX_CALLS /api/stt calls a run; a second run on the same commit is refused
unless --again; only a local server is called. The raw results go to .data-measure/ (git-ignored),
one JSON file per run, which is also the record the second-run guard reads. Prints a Markdown report.
"""
import argparse
import json
import statistics
import subprocess
import sys
import time
from datetime import datetime
from pathlib import Path
from urllib.parse import urlparse
from zoneinfo import ZoneInfo

import httpx

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
from server import config, stt_sarvam  # noqa: E402  the settings the server sends, read from this checkout

MAX_CALLS = 20  # /api/stt calls a run; each one is a paid Sarvam call
RUNS = ROOT / ".data-measure"
LOCAL_HOSTS = {"127.0.0.1", "localhost", "::1"}
STATION = "oven-line"
LANGUAGE = "hi-IN"
# What each sample must save as (PRD section 3). Written down here, not derived from the parser,
# so the parser is checked against it too (the "control" below, on the reference text).
EXPECTED = {
    "s1": {"batch_no": 14, "machine": "Oven 2", "temperature_c": 180, "rejects": 3},
    "s2": {"batch_no": 15, "machine": "Oven 1", "temperature_c": 210, "rejects": 2},
    "s3": {"batch_no": 16, "machine": "Oven 2", "temperature_c": 175, "rejects": 4},
    "s4": {"batch_no": 17, "machine": "Oven 2", "temperature_c": 185, "rejects": 7},
}
FOLLOW_UP = {"s3": "s3b"}  # s3 leaves out the temperature; s3b is the spoken answer
REFERENCE = {s["id"]: s["text"] for s in config.SAMPLES}  # the sentence each clip says


class Refused(Exception):
    """The run must not start or go on: spend guard, second run, or a server that is not local."""


def check_local(base):
    if urlparse(base).hostname not in LOCAL_HOSTS:
        raise Refused(f"{base} is not a local server; this script spends the credit of the server it calls")


def check_second_run(runs_dir, commit, again):
    done = sorted(runs_dir.glob(f"{commit}-*.json"))
    if done and not again:
        raise Refused(f"commit {commit[:7]} was measured already ({done[0].name}); pass --again to spend more")


class Meter:
    """Sends /api/stt calls and refuses the one past the cap. A call counts when it is sent, failed or not."""

    def __init__(self, client, cap=MAX_CALLS):
        self.client, self.cap, self.sent = client, cap, 0

    def stt(self, clip):
        if self.sent >= self.cap:
            raise Refused(f"spend guard: {self.cap} /api/stt calls already sent in this run")
        self.sent += 1
        call = {"call": self.sent, "clip": clip}
        audio = (config.WEB_DIR / "samples" / f"{clip}.m4a").read_bytes()
        start = time.perf_counter()
        try:
            r = self.client.post("/api/stt", files={"file": (f"{clip}.m4a", audio, "audio/mp4")},
                                 data={"language": LANGUAGE})
        except httpx.HTTPError as exc:
            return {**call, "seconds": time.perf_counter() - start, "error": f"local server: {type(exc).__name__}"}
        call["seconds"] = time.perf_counter() - start
        try:
            body = r.json()
        except ValueError:
            body = {}
        if r.status_code != 200:  # key, credit, rate limit, network: listed as an error, never as a wrong answer
            return {**call, "error": f"{r.status_code} {body.get('error')}: {body.get('message')}"}
        return {**call, "text": body["text"]}


def parse(client, text, draft=None, expect=None):
    r = client.post("/api/parse", json={"station_id": STATION, "text": text, "draft": draft,
                                        "expect": expect, "lang": "hi"})
    r.raise_for_status()
    return r.json()


def flow(client, hear, sample):
    """One sample as the operator screen runs it. Returns (clips heard, final fields or None on an error).
    Each clip gets `right`: its own part of the row was understood (s3: its three values with the
    temperature still empty; s3b: the finished row)."""
    first = hear(sample)
    heard = [first]
    if "error" in first:
        return heard, None
    body = parse(client, first["text"])
    if sample not in FOLLOW_UP:
        first["right"] = body["fields"] == EXPECTED[sample]
        return heard, body["fields"]
    first["right"] = body["fields"] == {**EXPECTED[sample], "temperature_c": None}
    if body.get("ask") == "temperature_c":  # the screen sends the answer only when the parser asked for it
        second = hear(FOLLOW_UP[sample])
        heard.append(second)
        if "error" in second:
            return heard, None
        body = parse(client, second["text"], draft=body["fields"], expect="temperature_c")
        second["right"] = body["fields"] == EXPECTED[sample]
    return heard, body["fields"]


def measure(client, repeat, out=None):
    """Fills and returns `out`. Stops at the first /api/stt error: it is not the model's, and the
    remaining calls would spend credit on the same failure."""
    out = {} if out is None else out
    planned = len(REFERENCE) + repeat
    if planned > MAX_CALLS:
        raise Refused(f"spend guard: {planned} calls planned, the cap is {MAX_CALLS}")
    reference = lambda clip: {"clip": clip, "text": REFERENCE[clip]}  # noqa: E731
    out["control"] = {s: flow(client, reference, s)[1] == EXPECTED[s] for s in EXPECTED}
    meter = Meter(client)
    out["samples"], out["repeats"] = [], []
    for sample in EXPECTED:
        heard, fields = flow(client, meter.stt, sample)
        out["samples"].append({"sample": sample, "heard": heard, "fields": fields,
                               "right": None if fields is None else fields == EXPECTED[sample]})
        if fields is None:
            break
    else:
        for _ in range(repeat):
            heard, fields = flow(client, meter.stt, "s1")
            out["repeats"].append({"heard": heard[0], "right": None if fields is None else fields == EXPECTED["s1"]})
            if fields is None:
                break
    out["calls_sent"] = meter.sent
    return out


def git(*args):
    return subprocess.run(["git", "-C", str(ROOT), *args], capture_output=True, text=True, check=True).stdout.strip()


def report(r):
    calls = [h for s in r["samples"] for h in s["heard"]] + [x["heard"] for x in r["repeats"]]
    errors = [c for c in calls if "error" in c]
    clips = [c for s in r["samples"] for c in s["heard"] if "error" not in c]
    rows = [s for s in r["samples"] if s["right"] is not None]
    reps = [x for x in r["repeats"] if x["right"] is not None]
    times = [c["seconds"] for c in calls if c["call"] > 1 and "error" not in c]
    first = next((c for c in calls if c["call"] == 1), None)
    fmt = lambda f: "—" if f is None else f"{f['batch_no']}, {f['machine']}, {f['temperature_c']}, {f['rejects']}"  # noqa: E731
    lines = [
        f"- Date: {r['date']}. Commit: `{r['commit']}`{' (uncommitted changes!)' if r['dirty'] else ''}.",
        f"- Server: {r['base']}, `/api/config` Sarvam: {r['sarvam']}.",
        f"- Model `{r['model']}`, mode `{r['mode']}`, language `{LANGUAGE}`, key terms on: {', '.join(r['keyterms'])}.",
        f"- `/api/stt` calls sent: {r['calls_sent']} (cap {MAX_CALLS}). Errors: {len(errors)}"
        + "".join(f"; call {c['call']} ({c['clip']}): {c['error']}" for c in errors) + ".",
        f"- Parser control, reference text from `server/samples.json` (no Sarvam call): "
        f"{sum(r['control'].values())} of {len(r['control'])} rows right.",
        f"- Clips right: {sum(c['right'] for c in clips)} of {len(clips)} evaluated. "
        f"Rows right: {sum(s['right'] for s in rows)} of {len(rows)}. "
        f"Repeats on s1: {sum(x['right'] for x in reps)} of {len(reps)} rows right.",
        "", "| Call | Clip | Said (reference) | Heard (Sarvam) | Clip right | Row saved as | Reply (s) |",
        "|---|---|---|---|---|---|---|",
    ]
    for s in r["samples"]:
        for i, c in enumerate(s["heard"]):
            row = fmt(s["fields"]) if i == len(s["heard"]) - 1 else "asks for the temperature" if c.get("right") else "—"
            lines.append(f"| {c['call']} | {c['clip']} | {REFERENCE[c['clip']]} | {c.get('text', c.get('error'))} | "
                         f"{'error' if 'error' in c else 'yes' if c['right'] else 'no'} | {row} | {c['seconds']:.2f} |")
    for x in r["repeats"]:
        c = x["heard"]
        lines.append(f"| {c['call']} | s1 (repeat) | | {c.get('text', c.get('error'))} | "
                     f"{'error' if 'error' in c else 'yes' if x['right'] else 'no'} | | {c['seconds']:.2f} |")
    lines.append("")
    if first and "error" not in first:
        lines.append(f"- First call of the run (call 1, {first['clip']}): {first['seconds']:.2f} s.")
    if times:
        lines.append(f"- Other calls: n = {len(times)}, min {min(times):.2f} s, median {statistics.median(times):.2f} s, "
                     f"max {max(times):.2f} s.")
    lines.append("- Reply time is measured at this script: upload to the local server, the server's call to "
                 "Sarvam (a new HTTPS connection each time), and the server saving the clip.")
    return "\n".join(lines)


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--base", default="http://127.0.0.1:8000", help="the local server (default %(default)s)")
    ap.add_argument("--repeat", type=int, default=10, help="extra s1 calls for the reply-time range (default 10)")
    ap.add_argument("--again", action="store_true", help="measure a commit that was measured already")
    ap.add_argument("--self-test", action="store_true", help="check the guards and the scoring offline")
    a = ap.parse_args(argv)
    if a.self_test:
        return self_test()
    try:
        check_local(a.base)
        commit = git("rev-parse", "HEAD")
        check_second_run(RUNS, commit, a.again)
    except Refused as exc:
        sys.exit(f"refused: {exc}")
    now = datetime.now(ZoneInfo("Asia/Kolkata"))
    r = {"date": now.strftime("%d %b %Y %H:%M IST"), "commit": commit, "dirty": bool(git("status", "--porcelain")),
         "base": a.base, "model": stt_sarvam.MODEL, "mode": stt_sarvam.MODE, "keyterms": stt_sarvam.KEYTERMS}
    with httpx.Client(base_url=a.base, timeout=60) as client:
        r["sarvam"] = client.get("/api/config").json()["engines"]["sarvam"]["message"]
        if r["sarvam"] != "ready":
            sys.exit(f"refused: the server's /api/config says Sarvam is '{r['sarvam']}'; start it with SARVAM_API_KEY set")
        RUNS.mkdir(exist_ok=True)
        path = RUNS / f"{commit}-{now.strftime('%Y%m%dT%H%M%S')}.json"
        try:
            measure(client, a.repeat, r)
        finally:  # written even when the run stops early: calls were spent, so the second-run guard must see it
            path.write_text(json.dumps(r, ensure_ascii=False, indent=1), encoding="utf-8")
    print(report(r))
    print(f"\nRaw results: {path.relative_to(ROOT)}")


def self_test():
    """Runs the real app in-process with Sarvam replaced by a fake. Nothing leaves the machine."""
    import os
    import tempfile
    os.environ["DATA_DIR"] = tempfile.mkdtemp()
    os.environ["SARVAM_API_KEY"] = "fake-key-for-self-test"
    from fastapi.testclient import TestClient
    from server.main import app

    audio = {c: (config.WEB_DIR / "samples" / f"{c}.m4a").read_bytes() for c in REFERENCE}
    fake = {"sent": 0, "say": dict(REFERENCE), "status": 200}

    def sarvam(request):
        fake["sent"] += 1
        if fake["status"] != 200:
            return httpx.Response(fake["status"], json={"error": {"message": "no credit", "code": "x"}})
        body = request.read()
        clip = next(c for c, data in audio.items() if data in body)
        return httpx.Response(200, json={"transcript": fake["say"][clip]})

    stt_sarvam.TRANSPORT = httpx.MockTransport(sarvam)
    client = TestClient(app)

    def refused(fn):
        try:
            fn()
        except Refused:
            return
        raise AssertionError("not refused")

    # A perfect transcript: every clip and row right, and the parser control agrees with EXPECTED.
    r = measure(client, repeat=2)
    assert all(r["control"].values()), r["control"]
    assert [s["right"] for s in r["samples"]] == [True] * 4 and all(x["right"] for x in r["repeats"]), r
    assert fake["sent"] == r["calls_sent"] == 7, fake
    # A misheard temperature is a wrong answer, not an error.
    fake.update(sent=0, say={**REFERENCE, "s2": "Batch pandrah, oven ek, do sau bees degree, do reject"})
    r = measure(client, repeat=0)
    assert [s["right"] for s in r["samples"]] == [True, False, True, True], r
    # A provider failure (402, no credit) is an error: the run stops and nothing is scored.
    fake.update(sent=0, status=402)
    r = measure(client, repeat=10)
    assert fake["sent"] == 1 and r["samples"][0]["right"] is None and "402" in r["samples"][0]["heard"][0]["error"], r
    # Spend guards: a plan over the cap sends nothing; the meter refuses the call past its cap.
    fake.update(sent=0, status=200, say=dict(REFERENCE))
    refused(lambda: measure(client, repeat=MAX_CALLS))
    assert fake["sent"] == 0, fake
    meter = Meter(client, cap=1)
    meter.stt("s1")
    refused(lambda: meter.stt("s1"))
    assert fake["sent"] == 1, fake
    # A second run on the same commit needs --again; only a local server is called.
    runs = Path(tempfile.mkdtemp())
    check_second_run(runs, "abc123", again=False)
    (runs / "abc123-20261128T100000.json").write_text("{}")
    refused(lambda: check_second_run(runs, "abc123", again=False))
    check_second_run(runs, "abc123", again=True)
    refused(lambda: check_local("https://bolo-line.onrender.com"))
    check_local("http://127.0.0.1:8111")
    print("self-test ok: scoring, error handling, spend guards, second-run guard, local-only guard")


if __name__ == "__main__":
    main()
