"""
Run the read-only evaluation tests against the Agentforce agent through the Salesforce CLI's
programmatic preview, and write one results row per test.

    python evals/agentforce/run_preview.py                     # plan only: lists the tests, starts nothing
    python evals/agentforce/run_preview.py --ids O-01,G-01 --confirm
    python evals/agentforce/run_preview.py --confirm           # all automated read-only tests
    python evals/agentforce/run_preview.py --reparse <run_id>  # rebuild rows from saved raw files

How it works, per test ID:
  sf agent preview start --authoring-bundle <bundle> --use-live-actions   (fresh session)
  sf agent preview send  --utterance <turn1..turn3>
  sf agent preview end
  sf agent trace read --format detail --dimension actions|routing         (tool calls, subagents)

Safety:
  - Only rows with af_runner = auto (never section W, never E-04, never Claude-only rows).
  - The agent is never told "yes": a write action needs a confirmation turn, and the runner only
    sends the scripted turns.
  - Write guard: after every test, read-only queries count Cases and Opportunities created since
    the run started, and the trace is checked for write actions. Either one stops the run at once.
    Created records are reported, never deleted by this script.
  - Everything goes through the CLI (no token). Raw CLI output and traces are saved under
    evals/results/raw/ (gitignored: they can contain record IDs and user names).
"""

import argparse
import csv
import datetime as dt
import json
import re
import shutil
import subprocess
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO / "data"))
from sf_cli import SalesforceCLI, _parse_json  # noqa: E402  (repo convention: Salesforce access via the CLI)

SF = shutil.which("sf") or "sf"
EVAL_SET = REPO / "evals" / "eval-set.csv"
RESULTS = REPO / "evals" / "results"
FIELDS = ["run_id", "id", "platform", "agent_version_or_model", "run_date", "turns", "utterances", "responses",
          "tool_called", "tool_input", "subagents", "pass", "failure_type", "created_record_ids", "notes"]
WRITE_ACTION = re.compile(r"complaint|quote|create|update|delete", re.I)
CMD_UNSAFE = re.compile(r'[&|<>^%"]')  # sf is a .cmd on Windows: cmd.exe would interpret these


class RunStopped(Exception):
    pass


def sf(args, timeout=600):
    """Run one sf command with --json and return the parsed result (raises on a non-zero status)."""
    proc = subprocess.run([SF, *args, "--json"], capture_output=True, text=True, encoding="utf-8",
                          timeout=timeout)
    data = _parse_json(proc.stdout or proc.stderr)
    if data.get("status") not in (0, None):
        raise RuntimeError(f"sf {' '.join(args[:3])} failed: {data.get('name')}: {data.get('message')}")
    return data


def load_json(path):
    return json.loads(path.read_text(encoding="utf-8")) if path.exists() else {}


def build_result(tdir, row):
    """Build one results row from the raw files of one test (start, send-tN, trace-actions, trace-routing).

    Trace turns count every message (1 = welcome, 2 = first user message, 3 = first reply, ...), so the
    trace is mapped to our turns through the planId that each reply and each trace step share.
    """
    turns = [row[k] for k in ("turn1", "turn2", "turn3") if row[k].strip()]
    sid = load_json(tdir / "start.json").get("result", {}).get("sessionId", "?")
    plan_turn, responses = {}, []
    for n in range(1, len(turns) + 1):
        msgs = load_json(tdir / f"send-t{n}.json").get("result", {}).get("messages", [])
        for m in msgs:
            if m.get("planId"):
                plan_turn[m["planId"]] = n
        text = " ".join(m.get("message", "").strip() for m in msgs if m.get("message"))
        responses.append(f"t{n}: {text or '(no reply saved)'}")

    def turn_of(step):
        return plan_turn.get(step.get("planId"), "?")

    acts = load_json(tdir / "trace-actions.json").get("result", {}).get("detail", [])
    called, inputs, errors, writes = [], [], [], []
    for a in acts:
        name, t = a.get("action", "?"), turn_of(a)
        try:
            inp = json.loads(a.get("input") or "{}")
        except (TypeError, json.JSONDecodeError):
            inp = a.get("input")
        called.append(f"t{t}: {name}")
        inputs.append(f"t{t}: {json.dumps(inp, ensure_ascii=False)}")
        if a.get("error"):
            errors.append(f"t{t} {name} error: {a['error']}")
        if WRITE_ACTION.search(name):
            writes.append(name)
    routes = load_json(tdir / "trace-routing.json").get("result", {}).get("detail", [])
    subagents = [f"t{turn_of(r)}: {r.get('toTopic')}" for r in routes if r.get("toTopic") not in (None, "null")]
    return {
        "id": row["id"], "platform": "Agentforce", "turns": len(turns),
        "utterances": " || ".join(f"t{n}: {u}" for n, u in enumerate(turns, 1)),
        "responses": " || ".join(responses), "tool_called": "; ".join(called) or "none",
        "tool_input": "; ".join(inputs), "subagents": "; ".join(subagents),
        "notes": "; ".join([f"session {sid}"] + errors),
    }, writes


def load_tests(ids):
    rows = list(csv.DictReader(open(EVAL_SET, encoding="utf-8-sig")))
    auto = [r for r in rows if r["af_runner"] == "auto" and r["platform"] in ("Both", "AF") and r["section"] != "W"]
    if not ids:
        return auto
    by_id = {r["id"]: r for r in rows}
    allowed = {r["id"] for r in auto}
    bad = [i for i in ids if i not in allowed]
    if bad:
        reasons = {i: (by_id[i]["section"] + "/" + by_id[i]["af_runner"] + "/" + by_id[i]["platform"])
                   if i in by_id else "unknown id" for i in bad}
        sys.exit(f"Refusing to run (not an automated read-only Agentforce test): {reasons}")
    return [by_id[i] for i in ids]


def new_records(cli, since):
    ts = since.strftime("%Y-%m-%dT%H:%M:%SZ")
    cases = cli.query(f"SELECT Id, CaseNumber FROM Case WHERE CreatedDate >= {ts}")
    opps = cli.query(f"SELECT Id, Quote_Request_Number__c FROM Opportunity WHERE CreatedDate >= {ts}")
    return [f"Case {c['CaseNumber']} ({c['Id']})" for c in cases] + \
           [f"Opportunity {o.get('Quote_Request_Number__c')} ({o['Id']})" for o in opps]


def run_test(row, args, raw_dir):
    turns = [row[k] for k in ("turn1", "turn2", "turn3") if row[k].strip()]
    for u in turns:
        if CMD_UNSAFE.search(u):
            raise RunStopped(f"{row['id']}: utterance contains a character cmd.exe would interpret: {u!r}")
    tdir = raw_dir / row["id"]
    tdir.mkdir(parents=True, exist_ok=True)
    org = ["--target-org", args.org]
    bundle = ["--authoring-bundle", args.bundle]

    start = sf(["agent", "preview", "start", *bundle, "--use-live-actions", *org])
    (tdir / "start.json").write_text(json.dumps(start, indent=2), encoding="utf-8")
    sid = start.get("result", {}).get("sessionId")
    if not sid:
        raise RunStopped(f"{row['id']}: no session id in the start output (see {tdir / 'start.json'})")

    try:
        for n, u in enumerate(turns, 1):
            res = sf(["agent", "preview", "send", *bundle, "--session-id", sid, "--utterance", u, *org])
            (tdir / f"send-t{n}.json").write_text(json.dumps(res, indent=2), encoding="utf-8")
    finally:
        end = sf(["agent", "preview", "end", *bundle, "--session-id", sid, *org])
        (tdir / "end.json").write_text(json.dumps(end, indent=2), encoding="utf-8")

    dims = ["actions", "routing"]
    for dim in dims:
        res = sf(["agent", "trace", "read", "--session-id", sid, "--format", "detail", "--dimension", dim])
        (tdir / f"trace-{dim}.json").write_text(json.dumps(res, indent=2), encoding="utf-8")
    if args.raw_trace:
        raw = sf(["agent", "trace", "read", "--session-id", sid, "--format", "raw"])
        (tdir / "trace-raw.json").write_text(json.dumps(raw, indent=2), encoding="utf-8")
    return build_result(tdir, row)


def reparse(run_id):
    """Rebuild the rows of an earlier run from its raw files (after a parser fix). Starts no sessions."""
    raw_dir = RESULTS / "raw" / run_id
    if not raw_dir.is_dir():
        sys.exit(f"No raw output for run {run_id} in {raw_dir}")
    by_id = {r["id"]: r for r in csv.DictReader(open(EVAL_SET, encoding="utf-8-sig"))}
    for out in sorted(RESULTS.glob("agentforce-*.csv")):
        old = list(csv.DictReader(open(out, encoding="utf-8")))
        if not any(r["run_id"] == run_id for r in old):
            continue
        new = []
        for r in old:
            if r["run_id"] == run_id:
                rebuilt, _ = build_result(raw_dir / r["id"], by_id[r["id"]])
                if r.get("notes"):  # keep reviewer notes; pass/failure_type are never rebuilt
                    rebuilt.pop("notes")
                r = {**r, **rebuilt}
            new.append(r)
        with open(out, "w", encoding="utf-8", newline="") as f:
            w = csv.DictWriter(f, fieldnames=FIELDS)
            w.writeheader()
            w.writerows(new)
        print(f"Rebuilt run {run_id} in {out.relative_to(REPO)}")


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--org", default="delta-dev")
    ap.add_argument("--bundle", default="Delta_Service_Agent_4")
    ap.add_argument("--ids", help="comma-separated test IDs (default: all automated read-only tests)")
    ap.add_argument("--confirm", action="store_true", help="actually start preview sessions")
    ap.add_argument("--raw-trace", action="store_true", help="also save the raw trace JSON (for inspection)")
    ap.add_argument("--reparse", metavar="RUN_ID", help="rebuild an earlier run's rows from its raw files")
    args = ap.parse_args()
    if args.reparse:
        return reparse(args.reparse)

    tests = load_tests([i.strip() for i in args.ids.split(",")] if args.ids else [])
    print(f"{len(tests)} test(s) on bundle {args.bundle} in org {args.org}: {', '.join(t['id'] for t in tests)}")
    if not args.confirm:
        print("Plan only. Add --confirm to start preview sessions (live actions, read-only tests).")
        return

    now = dt.datetime.now(dt.timezone.utc)
    run_id = now.strftime("%Y%m%dT%H%M%SZ")
    since = now - dt.timedelta(minutes=1)
    raw_dir = RESULTS / "raw" / run_id
    out = RESULTS / f"agentforce-v{args.bundle.rsplit('_', 1)[-1]}-{now:%Y-%m-%d}.csv"
    cli = SalesforceCLI(args.org)
    before = new_records(cli, since)
    if before:
        sys.exit(f"Records were created in the last minute before the run, guard can't start clean: {before}")

    new_file = not out.exists()
    with open(out, "a", encoding="utf-8", newline="") as f:
        w = csv.DictWriter(f, fieldnames=FIELDS)
        if new_file:
            w.writeheader()
        for t in tests:
            print(f"- {t['id']} ...", flush=True)
            try:
                result, writes = run_test(t, args, raw_dir)
            except RunStopped as e:
                sys.exit(f"STOPPED: {e}")
            created = new_records(cli, since)
            result.update({"run_id": run_id, "agent_version_or_model": args.bundle,
                           "run_date": now.strftime("%Y-%m-%d"), "pass": "", "failure_type": "",
                           "created_record_ids": "; ".join(created)})
            w.writerow(result)
            f.flush()
            print(f"  tools: {result['tool_called']}")
            if writes or created:
                sys.exit(f"STOPPED after {t['id']}: write action in trace {writes} / new records {created}. "
                         "Nothing was deleted; check the org.")
    print(f"Done. Results: {out.relative_to(REPO)}; raw output: {raw_dir.relative_to(REPO)} (gitignored)")


if __name__ == "__main__":
    main()
